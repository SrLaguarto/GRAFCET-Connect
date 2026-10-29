"""Operaciones de edición sin interfaz (documento 07; REQ-EDT-01..07, 09, 14; REQ-MOD-03, REQ-MOD-06).

Cada operación es una transacción: se aplica completa o no se aplica; una operación
fallida no entra en el historial; una edición nueva descarta la rama de rehacer
(REQ-EDT-05). Las operaciones de vista solo cambian el documento de presentación y no
cambian la revisión semántica (REQ-EDT-03, REQ-EDT-14). Conectar exige una relación
explícita: cruzar líneas nunca conecta (REQ-MOD-03).
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from fractions import Fraction
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from . import expressions as ex
from .diagnostics import Diagnostic, DiagnosticError
from .ids import IdGenerator, label_key, valid_label
from .model import ValidationResult, compute_revision, validate_model
from .profile import FORMAT_VERSION
from .values import TypeSpec, format_value, parse_type, parse_value, zero


def new_model_document(model_id: str) -> dict[str, Any]:
    return {"family": "model", "formatVersion": FORMAT_VERSION, "id": model_id, "revisionId": "",
            "partials": [], "steps": [], "transitions": [], "variables": [], "expressions": [], "actions": [],
            "forces": [], "hierarchy": {"macros": [], "expansions": [], "enclosures": []}, "draftLinks": []}


def new_grafcet_document(model_id: str) -> dict[str, Any]:
    """Modelo vacío con el parcial raíz «g», el de los ejemplos: el grafcet que se dibuja sin marco de parcial."""
    doc = new_model_document(model_id)
    doc["partials"].append({"id": "g", "label": "g", "stepRefs": [], "transitionRefs": []})
    return doc


def new_presentation(model_id: str) -> dict[str, Any]:
    return {"family": "presentation", "formatVersion": FORMAT_VERSION, "id": f"{model_id}.vista", "modelId": model_id,
            "views": [{"id": f"{model_id}.vista.principal", "label": "principal"}], "elementLayouts": [], "notes": []}


def _coord(v: Any) -> str:
    return format_value(TypeSpec("decimal", 3), Fraction(str(v)))


def _check_initial(role: str, t: Any, init: Any) -> None:
    """Hoja 08, 1.5 A y su comentario: fuera del grafcet no se declara ningún valor inicial. Las variables que no
    son entradas empiezan en 0; otro valor se pone con una acción «al activar» en la etapa inicial."""
    if role != "input" and parse_value(t, init) != zero(t):
        raise DiagnosticError(Diagnostic(
            "D-FORMATO", "las variables que no son entradas empiezan en 0: el valor inicial se pone con una acción "
            "«al activar» en la etapa inicial (hoja 08, 1.5)", field="initialValue"))


@dataclass
class Fragment:
    """Fragmento copiado: entidades y relaciones internas; referencias externas explícitas."""
    entities: dict[str, list[dict[str, Any]]]
    layouts: list[dict[str, Any]]
    external_refs: dict[str, str] = field(default_factory=dict)  # id externo -> clase


class Editor:
    def __init__(self, model: dict[str, Any], presentation: dict[str, Any] | None = None,
                 ids: IdGenerator | None = None) -> None:
        self.model = model
        self.presentation = presentation or new_presentation(model["id"])
        self.ids = ids or IdGenerator()
        self.undo_stack: list[tuple[str, Any, Any]] = []
        self.redo_stack: list[tuple[str, Any, Any]] = []
        self.dirty = False
        self.model["revisionId"] = compute_revision(self.model)

    # -- infraestructura de transacciones
    @property
    def revision(self) -> str:
        return self.model["revisionId"]

    def _txn(self, label: str, fn: Callable[[dict[str, Any], dict[str, Any]], Any], view_only: bool = False) -> Any:
        """Aplica fn sobre copias de trabajo. El editor nunca modifica sus documentos en el sitio, así que el
        historial puede compartir los documentos anterior y posterior sin copiarlos otra vez (P-IMP-08).
        Las operaciones de vista solo copian la presentación y no recalculan la revisión semántica."""
        before = (self.model, self.presentation)
        work_m = self.model if view_only else copy.deepcopy(self.model)
        work_p = copy.deepcopy(self.presentation)
        result = fn(work_m, work_p)  # una excepción deja el documento intacto y sin historial
        if not view_only:
            work_m["revisionId"] = compute_revision(work_m)
        self.model, self.presentation = work_m, work_p
        self.undo_stack.append((label, before, (work_m, work_p)))
        self.redo_stack.clear()
        self.dirty = True
        return result

    def undo(self) -> str:
        label, before, after = self.undo_stack.pop()
        self.model, self.presentation = before
        self.redo_stack.append((label, before, after))
        return label

    def redo(self) -> str:
        label, before, after = self.redo_stack.pop()
        self.model, self.presentation = after
        self.undo_stack.append((label, before, after))
        return label

    @contextmanager
    def group(self, label: str) -> Iterator[None]:
        """Varias operaciones que se deshacen y se rehacen de una sola vez (por ejemplo, «añadir debajo»)."""
        n = len(self.undo_stack)
        yield
        if len(self.undo_stack) - n > 1:
            entries = self.undo_stack[n:]
            del self.undo_stack[n:]
            self.undo_stack.append((label, entries[0][1], entries[-1][2]))

    def next_label(self, kind: str) -> str:
        """Etiqueta libre para un elemento nuevo: 0, 1, 2… para etapas (solo el número, como en la norma) y t1, t2… para
        transiciones."""
        coll = self.model["steps"] if kind == "step" else self.model["transitions"]
        used = {label_key(x["label"]) for x in coll if x.get("label")} | {x["id"] for x in coll}  # el ID también cuenta (ejemplos)
        prefix, n = ("", 0) if kind == "step" else ("t", 1)
        while f"{prefix}{n}" in used:
            n += 1
        return f"{prefix}{n}"

    def check_expression(self, text: str, partial: str) -> Diagnostic | None:
        """Comprueba el texto de una receptividad o condición sin cambiar el modelo: None si se interpreta."""
        return self._make_expr(self.model, text, partial)[1]

    def undeclared_variables(self, text: str, partial: str) -> list[str]:
        """Nombres de variable que el texto usa y no existen (vacío si el texto no se interpreta por otra causa)."""
        lookup, missing = self._lookup(self.model, partial), []

        def resolve(kind: str, name: str) -> str:
            ident = lookup(kind, name)
            if ident is None:
                if kind != "var":
                    raise ex.Unresolved(kind, name)
                missing.append(name)
                return "?"
            return ident
        try:
            ex.parse(text, resolve)
        except (ex.ParseError, ex.Unresolved):
            return []
        return list(dict.fromkeys(missing))

    def validate(self) -> ValidationResult:
        return validate_model(self.model)

    # -- búsquedas
    @staticmethod
    def _index(m: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
        out: dict[str, tuple[str, dict[str, Any]]] = {}
        for coll in ("partials", "steps", "transitions", "variables", "expressions", "actions", "forces", "draftLinks"):
            for it in m.get(coll, []):
                out[it["id"]] = (coll, it)
        for coll in ("macros", "expansions", "enclosures"):
            for it in m["hierarchy"][coll]:
                out[it["id"]] = (coll, it)
        return out

    def get(self, ident: str) -> dict[str, Any]:
        return self._index(self.model)[ident][1]

    def find(self, text: str) -> list[dict[str, str]]:
        """Búsqueda sensible a mayúsculas por etiqueta o nombre; devuelve ruta aunque esté plegado."""
        out = []
        for ident, (coll, it) in sorted(self._index(self.model).items()):
            name = it.get("label") or it.get("name") or ""
            if text in name:
                out.append({"id": ident, "kind": coll, "name": name, "partial": it.get("partialRef", it.get("scopeRef", ""))})
        return out

    def usages(self, ident: str) -> list[dict[str, str]]:
        users = []
        for e in self.model["expressions"]:
            if ident in e.get("bindings", {}).values():
                for owner in self._expr_owners(self.model, e["id"]):
                    users.append({"expression": e["id"], "owner": owner, "text": e["text"]})
        return users

    @staticmethod
    def _expr_owners(m: dict[str, Any], eid: str) -> list[str]:
        owners = [t["id"] for t in m["transitions"] if t["conditionRef"] == eid]
        for a in m["actions"]:
            if eid in (a.get("conditionRef"), a.get("valueRef"), (a.get("trigger") or {}).get("expressionRef")):
                owners.append(a["id"])
        return owners

    # -- resolución de nombres para el texto de expresiones (P-IMP-06)
    def _lookup(self, m: dict[str, Any], scope: str | None) -> Callable[[str, str], str | None]:
        partial_by_label = {p["label"]: p["id"] for p in m["partials"]}

        def pick(cands: list[dict[str, Any]], key: str, owner_key: str, name: str) -> str | None:
            if "." in name and name.split(".", 1)[0] in partial_by_label:
                pl, short = name.split(".", 1)
                hits = [c for c in cands if c[key] == short and c[owner_key] == partial_by_label[pl]]
            else:
                local = [c for c in cands if c[key] == name and c[owner_key] == scope]
                hits = local or [c for c in cands if c[key] == name]
            return hits[0]["id"] if len(hits) == 1 else None

        def lookup(kind: str, name: str) -> str | None:
            if kind == "var":
                return pick(m["variables"], "name", "scopeRef", name)
            if kind == "step":
                return pick(m["steps"], "label", "partialRef", name)
            if kind == "partial":
                return partial_by_label.get(name)
            return next((x["id"] for x in m["hierarchy"]["macros"] if x["label"] == name), None)
        return lookup

    def _make_expr(self, m: dict[str, Any], text: str, scope: str | None) -> tuple[dict[str, Any], Diagnostic | None]:
        eid = self.ids.new("e")
        resolve, found = ex.recording_resolver(self._lookup(m, scope))
        try:
            meaning = ex.parse(text, resolve)
            return {"id": eid, "mode": "executable", "text": text, "meaning": meaning, "bindings": dict(found)}, None
        except (ex.ParseError, ex.Unresolved) as exc:
            # Se conserva como texto descriptivo: guardable, no ejecutable (REQ-MOD-05)
            return ({"id": eid, "mode": "descriptive", "text": text, "bindings": {}},
                    Diagnostic("D-EXP-PENDIENTE", f"texto no interpretado: {exc}", element=eid))

    # -- creación
    def add_partial(self, label: str, owner: str | None = None) -> str:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            if not valid_label(label):
                raise DiagnosticError(Diagnostic("D-FORMATO", "etiqueta inválida"))
            pid = self.ids.new("g")
            item = {"id": pid, "label": label, "stepRefs": [], "transitionRefs": []}
            if owner:
                item["ownerRef"] = owner
            m["partials"].append(item)
            return pid
        return self._txn("crear parcial", fn)

    def _layout(self, p: dict[str, Any], ident: str, at: tuple[Any, Any] | None) -> None:
        if at is not None:
            p["elementLayouts"].append({"elementRef": ident, "viewRef": p["views"][0]["id"],
                                        "x": _coord(at[0]), "y": _coord(at[1])})

    def add_step(self, partial: str, label: str, initial: bool = False, kind: str = "ordinary",
                 at: tuple[Any, Any] | None = None) -> str:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            part = next(x for x in m["partials"] if x["id"] == partial)
            if any(s["partialRef"] == partial and label_key(s["label"]) == label_key(label) for s in m["steps"]):
                raise DiagnosticError(Diagnostic("D-NOMBRE-COLISION", f"etiqueta «{label}» ya existe en el parcial"))
            sid = self.ids.new("s")
            m["steps"].append({"id": sid, "label": label, "partialRef": partial, "kind": kind, "initial": initial,
                               "actionRefs": []})
            part["stepRefs"].append(sid)
            self._layout(p, sid, at)
            return sid
        return self._txn("crear etapa", fn)

    def add_transition(self, partial: str, condition: str, pre: list[str] = (), post: list[str] = (),
                       at: tuple[Any, Any] | None = None, label: str | None = None) -> tuple[str, Diagnostic | None]:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> tuple[str, Diagnostic | None]:
            tid = self.ids.new("t")
            expr, diag = self._make_expr(m, condition, partial)
            m["expressions"].append(expr)
            item = {"id": tid, "partialRef": partial, "preRefs": list(pre), "postRefs": list(post),
                    "conditionRef": expr["id"]}
            if label is not None:
                if not valid_label(label):
                    raise DiagnosticError(Diagnostic("D-FORMATO", "etiqueta inválida"))
                item["label"] = label
            m["transitions"].append(item)
            next(x for x in m["partials"] if x["id"] == partial)["transitionRefs"].append(tid)
            self._layout(p, tid, at)
            return tid, diag
        return self._txn("crear transición", fn)

    def add_variable(self, name: str, role: str, type_: dict[str, Any], unit: str = "", domain: dict[str, Any] | None = None,
                     initial: Any = None, scope: str | None = None) -> str:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            sc = scope or m["id"]
            if any(v["scopeRef"] == sc and label_key(v["name"]) == label_key(name) for v in m["variables"]):
                raise DiagnosticError(Diagnostic("D-NOMBRE-COLISION", f"variable «{name}» ya existe en el ámbito"))
            t = parse_type(type_)
            init = initial if initial is not None else format_value(t, zero(t))
            _check_initial(role, t, init)
            vid = self.ids.new("v")
            m["variables"].append({"id": vid, "name": name, "scopeRef": sc, "role": role, "type": type_, "unit": unit,
                                   "domain": domain or {}, "initialValue": init})
            return vid
        return self._txn("crear variable", fn)

    def set_condition(self, tid: str, text: str) -> Diagnostic | None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> Diagnostic | None:
            t = next(x for x in m["transitions"] if x["id"] == tid)
            expr, diag = self._make_expr(m, text, t["partialRef"])
            m["expressions"] = [e for e in m["expressions"] if e["id"] != t["conditionRef"]] + [expr]
            t["conditionRef"] = expr["id"]
            return diag
        return self._txn("editar receptividad", fn)

    def add_continuous_action(self, step: str, target: str, condition: str = "true", limit_us: int | None = None) -> str:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            st = next(x for x in m["steps"] if x["id"] == step)
            expr, diag = self._make_expr(m, condition, st["partialRef"])
            if diag:
                raise DiagnosticError(diag)
            aid = self.ids.new("a")
            item = {"id": aid, "stepRef": step, "mode": "continuous", "targetRef": target, "conditionRef": expr["id"]}
            if limit_us is not None:
                item["limitUs"] = str(limit_us)
            m["expressions"].append(expr)
            m["actions"].append(item)
            st["actionRefs"].append(aid)
            return aid
        return self._txn("crear acción continua", fn)

    def add_stored_action(self, step: str, target: str, trigger: str, value: str, event: str | None = None) -> str:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            st = next(x for x in m["steps"] if x["id"] == step)
            vexpr, diag = self._make_expr(m, value, st["partialRef"])
            if diag:
                raise DiagnosticError(diag)
            trig: dict[str, Any] = {"kind": trigger, "sourceRefs": []}
            m["expressions"].append(vexpr)
            if event is not None:
                eexpr, diag = self._make_expr(m, event, st["partialRef"])
                if diag:
                    raise DiagnosticError(diag)
                m["expressions"].append(eexpr)
                trig["expressionRef"] = eexpr["id"]
            aid = self.ids.new("a")
            m["actions"].append({"id": aid, "stepRef": step, "mode": "stored", "targetRef": target, "trigger": trig,
                                 "valueRef": vexpr["id"]})
            st["actionRefs"].append(aid)
            return aid
        return self._txn("crear acción memorizada", fn)

    def update_action(self, aid: str, target: str, mode: str, condition: str = "true", trigger: str | None = None,
                      value: str | None = None, event: str | None = None, limit_us: int | None = None) -> None:
        """Cambia una acción de arriba abajo (continua, con su límite de tiempo si lo lleva, o memorizada; objetivo,
        condición, disparador, valor, evento): conserva su ID, su etapa y su lugar entre las acciones de la etapa
        (P-IMP-38, P-IMP-41)."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            i, old = next((i, a) for i, a in enumerate(m["actions"]) if a["id"] == aid)
            st = next(x for x in m["steps"] if x["id"] == old["stepRef"])
            viejas = {old.get("conditionRef"), old.get("valueRef"), (old.get("trigger") or {}).get("expressionRef")}
            nuevas = []

            def expr(text: str) -> str:
                e, diag = self._make_expr(m, text, st["partialRef"])
                if diag:
                    raise DiagnosticError(diag)
                nuevas.append(e)
                return e["id"]
            if mode == "continuous":
                item = {"id": aid, "stepRef": st["id"], "mode": "continuous", "targetRef": target,
                        "conditionRef": expr(condition)}
                if limit_us is not None:
                    item["limitUs"] = str(limit_us)
            elif mode == "stored" and trigger in ("activation", "deactivation", "event") and value is not None:
                trig: dict[str, Any] = {"kind": trigger, "sourceRefs": []}
                if trigger == "event":
                    if not event:
                        raise DiagnosticError(Diagnostic("D-TIPO-EVENTO", "una acción por evento necesita su evento", element=aid))
                    trig["expressionRef"] = expr(event)
                item = {"id": aid, "stepRef": st["id"], "mode": "stored", "targetRef": target, "trigger": trig,
                        "valueRef": expr(value)}
            else:
                raise DiagnosticError(Diagnostic("D-FORMATO", "acción continua, o memorizada al activar, al desactivar o "
                                                 "por evento con su valor", element=aid))
            m["actions"][i] = item
            m["expressions"] = [e for e in m["expressions"] if e["id"] not in viejas] + nuevas
        self._txn("editar acción", fn)

    def move_action(self, aid: str, delta: int) -> None:
        """Cambia el lugar de una acción entre las de su etapa (el orden en que se dibujan, de izquierda a derecha)."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            a = next(x for x in m["actions"] if x["id"] == aid)
            refs = next(x for x in m["steps"] if x["id"] == a["stepRef"])["actionRefs"]
            i = refs.index(aid)
            j = max(0, min(len(refs) - 1, i + delta))
            refs.insert(j, refs.pop(i))
        self._txn("ordenar acciones", fn)

    # -- acciones sueltas o sin completar: borradores de la presentación (P-IMP-41)
    # Una acción del modelo exige etapa y variable. Una acción suelta (o unida a una etapa a la que aún le falta algo)
    # no puede serlo: se guarda en `presentation.draftActions`, no se simula y viaja con el proyecto. Cada una lleva
    # id, x, y (el punto medio de su lado izquierdo, donde se une), tipo (continua, condicionada, limitada, activacion,
    # desactivacion, evento) y, si los tienen, variable (ID), condicion, valor, evento y limite (en la notación del
    # usuario), etapa, y grupo y orden: varias acciones sueltas pegadas forman un grupo (mismo `grupo`, ordenadas por
    # `orden`; comparten x, y y la colocación de `actionLayouts[grupo]`).
    DRAFT_TIPOS = ("continua", "condicionada", "limitada", "activacion", "desactivacion", "evento")
    DRAFT_CAMPOS = ("variable", "condicion", "valor", "evento", "limite", "etapa", "grupo", "orden")

    def draft_actions(self) -> list[dict[str, Any]]:
        d = self.presentation.get("draftActions", [])
        return d if isinstance(d, list) else []

    def _check_draft(self, m: dict[str, Any], datos: dict[str, Any]) -> None:
        if "tipo" in datos and datos["tipo"] not in self.DRAFT_TIPOS:
            raise DiagnosticError(Diagnostic("D-FORMATO", f"tipo de acción desconocido: {datos['tipo']!r}"))
        if datos.get("etapa") and not any(s["id"] == datos["etapa"] for s in m["steps"]):
            raise DiagnosticError(Diagnostic("D-REF", f"etapa inexistente: {datos['etapa']}", element=datos["etapa"]))
        if datos.get("variable") and not any(v["id"] == datos["variable"] for v in m["variables"]):
            raise DiagnosticError(Diagnostic("D-REF", f"variable inexistente: {datos['variable']}",
                                             element=datos["variable"]))
        if datos.get("grupo") is not None and not isinstance(datos["grupo"], str):
            raise DiagnosticError(Diagnostic("D-FORMATO", "el grupo de una acción suelta es un texto"))
        if datos.get("orden") is not None and (not isinstance(datos["orden"], int) or isinstance(datos["orden"], bool)):
            raise DiagnosticError(Diagnostic("D-FORMATO", "el orden de una acción suelta es un entero"))

    @staticmethod
    def _poner_campos(d: dict[str, Any], datos: dict[str, Any]) -> None:
        for k in ("tipo",) + Editor.DRAFT_CAMPOS:
            if k in datos:
                if datos[k] in (None, ""):
                    d.pop(k, None)
                else:
                    d[k] = datos[k]

    def add_draft_action(self, at: tuple[Any, Any], datos: dict[str, Any] | None = None) -> str:
        """Una acción suelta (continua sin variable, salvo que `datos` diga otra cosa) con su lado izquierdo en `at`."""
        datos = {"tipo": "continua", **(datos or {})}

        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            self._check_draft(m, datos)
            did = self.ids.new("c")
            d: dict[str, Any] = {"id": did, "x": _coord(at[0]), "y": _coord(at[1])}
            self._poner_campos(d, datos)
            p.setdefault("draftActions", []).append(d)
            return did
        return self._txn("colocar acción", fn, view_only=True)

    @staticmethod
    def _draft(p: dict[str, Any], did: str) -> dict[str, Any]:
        d = next((x for x in p.get("draftActions", []) if x["id"] == did), None)
        if d is None:
            raise DiagnosticError(Diagnostic("D-REF", f"no existe la acción suelta {did}", element=did))
        return d

    def update_draft_action(self, did: str, **datos: Any) -> None:
        """Cambia datos de un borrador; un valor vacío o None quita el dato (etapa vacía: queda suelta)."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            self._check_draft(m, datos)
            if "x" in datos or "y" in datos:
                raise DiagnosticError(Diagnostic("D-FORMATO", "la posición se cambia con move_draft_action"))
            self._poner_campos(self._draft(p, did), datos)
            self._disolver_grupos(m, p)
        self._txn("editar acción suelta", fn, view_only=True)

    def update_draft_actions(self, cambios: dict[str, dict[str, Any]]) -> None:
        """Cambia datos (también la posición, «x» e «y») de varios borradores en una sola operación; los grupos de acciones
        sueltas se revisan al final, no entre un cambio y otro."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            for did, datos in cambios.items():
                datos = dict(datos)
                pos = {k: datos.pop(k) for k in ("x", "y") if k in datos}
                self._check_draft(m, datos)
                d = self._draft(p, did)
                self._poner_campos(d, datos)
                for k, v in pos.items():
                    d[k] = _coord(v)
            self._disolver_grupos(m, p)
        self._txn("editar acciones sueltas", fn, view_only=True)

    def move_draft_action(self, did: str, x: Any, y: Any) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            d = self._draft(p, did)
            d["x"], d["y"] = _coord(x), _coord(y)
        self._txn("mover acción suelta", fn, view_only=True)

    def delete_draft_actions(self, ids: list[str]) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            for did in ids:
                self._draft(p, did)
            p["draftActions"] = [d for d in p["draftActions"] if d["id"] not in ids]
            self._disolver_grupos(m, p)
        self._txn("quitar acción suelta", fn, view_only=True)

    @staticmethod
    def _disolver_grupos(m: dict[str, Any], p: dict[str, Any]) -> None:
        """Un grupo de acciones sueltas con menos de dos miembros deja de serlo; la colocación de un grupo que ya no existe
        se olvida."""
        cuenta: dict[str, int] = {}
        for d in p.get("draftActions", []):
            if d.get("grupo") and not d.get("etapa"):
                cuenta[d["grupo"]] = cuenta.get(d["grupo"], 0) + 1
        for d in p.get("draftActions", []):
            if d.get("grupo") and d.get("etapa"):
                d.pop("grupo", None)  # unida a una etapa: la manda la etapa
            elif d.get("grupo") and cuenta.get(d["grupo"], 0) < 2:
                d.pop("grupo", None)
                d.pop("orden", None)
        if isinstance(p.get("actionLayouts"), dict):
            vivos = {s["id"] for s in m["steps"]} | {g for g, n in cuenta.items() if n >= 2}
            p["actionLayouts"] = {k: v for k, v in p["actionLayouts"].items() if k in vivos}
            if not p["actionLayouts"]:
                del p["actionLayouts"]

    def delete_variable(self, vid: str) -> None:
        """Quita una variable que no se usa en ninguna expresión ni es el objetivo de una acción (REQ-EDT-07)."""
        usos = self.usages(vid) + [{"owner": a["id"]} for a in self.model["actions"] if a["targetRef"] == vid]
        usos += [{"owner": d["id"]} for d in self.draft_actions() if d.get("variable") == vid]  # acciones sin completar
        if usos:
            raise DiagnosticError(Diagnostic("D-REF", f"la variable se usa en {len(usos)} sitio(s): quite antes esos usos",
                                             element=vid))

        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            m["variables"] = [v for v in m["variables"] if v["id"] != vid]
        self._txn("quitar variable", fn)

    # -- conexión explícita (REQ-MOD-02, REQ-MOD-03; P-IMP-05)
    def connect(self, src: str, dst: str) -> Diagnostic | None:
        return self._txn("conectar", lambda m, p: self._link_in(m, src, dst))

    # -- vista (solo presentación)
    def link_styles(self) -> dict[str, Any]:
        return self.presentation.get("linkStyles", {})

    def set_link_style(self, ident: str, style: dict[str, Any]) -> None:
        """Recorrido y flechas manuales; nunca cambia conexiones ni revisión semántica."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            styles = p.setdefault("linkStyles", {})
            if style:
                styles[ident] = copy.deepcopy(style)
            else:
                styles.pop(ident, None)
        self._txn("ajustar dibujo del enlace", fn, view_only=True)

    # Colocación de las acciones de una etapa o de un grupo de acciones sueltas (presentación,
    # `presentation.actionLayouts`: {ID de etapa o de grupo: valor}); sin
    # entrada vale «fila» (cajas pegadas en fila, la representación (2) de la norma).
    ACTION_LAYOUTS = ("fila", "fila-separada", "matriz-2", "columna")

    def action_layouts(self) -> dict[str, str]:
        d = self.presentation.get("actionLayouts", {})
        return d if isinstance(d, dict) else {}

    def set_action_layout(self, step: str, layout: str) -> None:
        """Cómo se colocan las acciones de una etapa: «fila» (pegadas, por defecto), «fila-separada», «matriz-2» o
        «columna». Solo presentación: no cambia el modelo ni la revisión."""
        if layout not in self.ACTION_LAYOUTS:
            raise DiagnosticError(Diagnostic("D-FORMATO", f"colocación de acciones desconocida: {layout!r}"))
        if not any(s["id"] == step for s in self.model["steps"]) and not any(
                d.get("grupo") == step and not d.get("etapa") for d in self.draft_actions()):
            raise DiagnosticError(Diagnostic("D-REF", f"etapa o grupo de acciones inexistente: {step}", element=step))

        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            d = p["actionLayouts"] = dict(p["actionLayouts"]) if isinstance(p.get("actionLayouts"), dict) else {}
            if layout == "fila":
                d.pop(step, None)
            else:
                d[step] = layout
            if not d:
                del p["actionLayouts"]
        self._txn("colocación de las acciones", fn, view_only=True)

    def move(self, ident: str, x: Any, y: Any) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            lay = next((l for l in p["elementLayouts"] if l["elementRef"] == ident), None)
            if lay is None:
                self._layout(p, ident, (x, y))
            else:
                lay["x"], lay["y"] = _coord(x), _coord(y)
        self._txn("mover", fn, view_only=True)

    def set_initial(self, step: str, initial: bool) -> None:
        """Tipo de etapa: inicial o normal."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            next(s for s in m["steps"] if s["id"] == step)["initial"] = bool(initial)
        self._txn("tipo de etapa", fn)

    def invert_link(self, tid: str, sid: str) -> None:
        """Invierte la dirección de un enlace: la etapa pasa de anterior a siguiente de la transición o al revés."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            t = next(x for x in m["transitions"] if x["id"] == tid)
            if sid in t["preRefs"]:
                t["preRefs"].remove(sid)
                t["postRefs"].append(sid)
            elif sid in t["postRefs"]:
                t["postRefs"].remove(sid)
                t["preRefs"].append(sid)
            else:
                raise DiagnosticError(Diagnostic("D-REF", f"{sid} no está enlazada con {tid}", element=tid))
        self._txn("invertir enlace", fn)

    def disconnect(self, tid: str, sid: str) -> None:
        """Quita el enlace entre una transición y una etapa (no borra ninguna de las dos)."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            t = next(x for x in m["transitions"] if x["id"] == tid)
            if sid not in t["preRefs"] and sid not in t["postRefs"]:
                raise DiagnosticError(Diagnostic("D-REF", f"{sid} no está enlazada con {tid}", element=tid))
            t["preRefs"] = [s for s in t["preRefs"] if s != sid]
            t["postRefs"] = [s for s in t["postRefs"] if s != sid]
        self._txn("quitar enlace", fn)

    # -- barras: simultaneidad (Y, doble trazo) y alternativa (O, trazo simple), P-IMP-32
    # La barra es presentación (la forma de dibujar varias etapas o varias transiciones en un mismo punto); lo que
    # une es modelo: cada pareja (elemento de arriba, elemento de abajo) deja su enlace normal en las transiciones, así
    # que el motor no sabe nada de las barras y la simulación es la de siempre.
    def bars(self) -> list[dict[str, Any]]:
        return self.presentation.get("barras", [])

    @staticmethod
    def _bar(p: dict[str, Any], bid: str) -> dict[str, Any]:
        return next(b for b in p.get("barras", []) if b["id"] == bid)

    def add_bar(self, kind: str, at: tuple[Any, Any], width: int = 120) -> str:
        if kind not in ("Y", "O"):
            raise DiagnosticError(Diagnostic("D-FORMATO", "tipo de barra desconocido (Y u O)"))

        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            bid = self.ids.new("b")
            p.setdefault("barras", []).append({"id": bid, "kind": kind, "x": _coord(at[0]), "y": _coord(at[1]),
                                               "ancho": _coord(width), "arriba": [], "abajo": []})
            return bid
        return self._txn("colocar barra", fn, view_only=True)

    def move_bar(self, bid: str, x: Any, y: Any) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            b = self._bar(p, bid)
            b["x"], b["y"] = _coord(x), _coord(y)
        self._txn("mover barra", fn, view_only=True)

    def resize_bar(self, bid: str, x: Any, width: Any) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            if Fraction(str(width)) < 40:
                raise DiagnosticError(Diagnostic("D-FORMATO", "la barra no puede ser más estrecha que 40"))
            b = self._bar(p, bid)
            b["x"], b["ancho"] = _coord(x), _coord(width)
        self._txn("ensanchar barra", fn, view_only=True)

    def set_bar_kind(self, bid: str, kind: str) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            self._bar(p, bid)["kind"] = kind
        self._txn("tipo de barra", fn, view_only=True)

    def bar_link(self, bid: str, side: str, ident: str) -> Diagnostic | None:
        """Une un elemento a una barra, por encima («arriba») o por debajo («abajo»). Con elementos a los dos lados,
        cada pareja queda enlazada en el modelo (etapa → transición o transición → etapa)."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> Diagnostic | None:
            b = self._bar(p, bid)
            if ident in b["arriba"] or ident in b["abajo"]:
                raise DiagnosticError(Diagnostic("D-FORMATO", "el elemento ya está unido a esta barra", element=ident))
            b[side].append(ident)
            diag = None
            for other in b["abajo" if side == "arriba" else "arriba"]:
                a, z = (ident, other) if side == "arriba" else (other, ident)
                diag = diag or self._link_in(m, a, z, quiet=True)
            return diag
        return self._txn("unir a la barra", fn)

    def bar_unlink(self, bid: str, ident: str) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            b = self._bar(p, bid)
            side = "arriba" if ident in b["arriba"] else "abajo"
            b[side].remove(ident)
            for other in b["abajo" if side == "arriba" else "arriba"]:
                self._unlink_in(m, *((ident, other) if side == "arriba" else (other, ident)))
        self._txn("quitar de la barra", fn)

    def delete_bar(self, bid: str) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            b = self._bar(p, bid)
            for a in b["arriba"]:
                for z in b["abajo"]:
                    self._unlink_in(m, a, z)
            p["barras"] = [x for x in p["barras"] if x["id"] != bid]
        self._txn("borrar barra", fn)

    def _link_in(self, m: dict[str, Any], src: str, dst: str, quiet: bool = False) -> Diagnostic | None:
        idx = self._index(m)
        ks, kd = idx[src][0], idx[dst][0]
        if ks == "steps" and kd == "transitions":
            refs, item = idx[dst][1]["preRefs"], src
        elif ks == "transitions" and kd == "steps":
            refs, item = idx[src][1]["postRefs"], dst
        else:
            if quiet and any(d["fromRef"] == src and d["toRef"] == dst for d in m["draftLinks"]):
                return None
            did = self.ids.new("l")
            m["draftLinks"].append({"id": did, "fromRef": src, "toRef": dst})
            return Diagnostic("D-ALTERNANCIA", f"{src}→{dst} une dos elementos del mismo tipo; se guarda como "
                              "borrador no ejecutable", element=did)
        if item in refs:
            if quiet:
                return None
            raise DiagnosticError(Diagnostic("D-FORMATO", "enlace duplicado entre los mismos extremos", element=dst))
        refs.append(item)
        return None

    def _unlink_in(self, m: dict[str, Any], src: str, dst: str) -> None:
        idx = self._index(m)
        ks, kd = idx[src][0], idx[dst][0]
        if ks == "steps" and kd == "transitions":
            t = idx[dst][1]
            t["preRefs"] = [x for x in t["preRefs"] if x != src]
        elif ks == "transitions" and kd == "steps":
            t = idx[src][1]
            t["postRefs"] = [x for x in t["postRefs"] if x != dst]
        else:
            m["draftLinks"] = [d for d in m["draftLinks"] if not (d["fromRef"] == src and d["toRef"] == dst)]

    def hidden_labels(self) -> set[str]:
        """Elementos cuya etiqueta no se dibuja (presentación; no cambia el modelo)."""
        return {l["elementRef"] for l in self.presentation["elementLayouts"] if l.get("labelVisible") is False}

    def set_label_visible(self, ident: str, visible: bool, at: tuple[Any, Any] = (0, 0)) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            lay = next((l for l in p["elementLayouts"] if l["elementRef"] == ident), None)
            if lay is None:
                self._layout(p, ident, at)
                lay = p["elementLayouts"][-1]
            if visible:
                lay.pop("labelVisible", None)
            else:
                lay["labelVisible"] = False
        self._txn("mostrar la etiqueta" if visible else "ocultar la etiqueta", fn, view_only=True)

    # Comentarios de etapas y transiciones (presentación, `presentation.notes` con `kind: "comment"`): texto asociado
    # por ID que nunca es fuente de significado (documento 03, tabla 7 [30]; documento 09). No cambia la revisión.
    def comments(self) -> dict[str, str]:
        """{ID de etapa o transición: comentario}."""
        notas = self.presentation.get("notes", [])
        return {n["elementRef"]: n["text"] for n in notas if isinstance(n, dict) and n.get("kind") == "comment"
                and isinstance(n.get("elementRef"), str) and isinstance(n.get("text"), str) and n["text"]}

    def set_comment(self, ident: str, text: str) -> None:
        """Pone (o, con texto vacío, quita) el comentario de una etapa o transición. Solo presentación."""
        if not any(x["id"] == ident for x in self.model["steps"] + self.model["transitions"]):
            raise DiagnosticError(Diagnostic("D-REF", f"solo las etapas y las transiciones llevan comentario: {ident}", element=ident))
        text = text.strip()

        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            notas = [n for n in p.get("notes", []) if not (isinstance(n, dict) and n.get("kind") == "comment"
                                                           and n.get("elementRef") == ident)]
            if text:
                notas.append({"id": self.ids.new("nota"), "elementRef": ident, "text": text, "kind": "comment"})
            p["notes"] = notas
        self._txn("comentario", fn, view_only=True)

    def align(self, ids: list[str], axis: str = "x") -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            lays = [l for l in p["elementLayouts"] if l["elementRef"] in ids]
            ref = min(Fraction(l[axis]) for l in lays)
            for l in lays:
                l[axis] = _coord(ref)
        self._txn("alinear", fn, view_only=True)

    def distribute(self, ids: list[str], axis: str = "y", gap: int = 80) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            lays = sorted((l for l in p["elementLayouts"] if l["elementRef"] in ids), key=lambda l: Fraction(l[axis]))
            base = Fraction(lays[0][axis])
            for i, l in enumerate(lays):
                l[axis] = _coord(base + i * gap)
        self._txn("distribuir", fn, view_only=True)

    # -- renombrado sin cambio de identidad (REQ-EDT-06, REQ-MOD-06)
    def _render_names(self, m: dict[str, Any]) -> Callable[[str], str]:
        idx = self._index(m)
        partial_label = {p["id"]: p["label"] for p in m["partials"]}

        def name_of(ident: str) -> str:
            coll, it = idx[ident]
            if coll == "variables":
                same = [v for v in m["variables"] if v["name"] == it["name"]]
                return it["name"] if len(same) == 1 else f"{partial_label.get(it['scopeRef'], it['scopeRef'])}.{it['name']}"
            if coll == "steps":
                same = [s for s in m["steps"] if s["label"] == it["label"]]
                return it["label"] if len(same) == 1 else f"{partial_label[it['partialRef']]}.{it['label']}"
            return it.get("label", ident)
        return name_of

    def rename(self, ident: str, new_name: str) -> list[str]:
        """Cambia etiqueta o nombre; conserva el ID y actualiza el texto de los usos."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> list[str]:
            if not valid_label(new_name):
                raise DiagnosticError(Diagnostic("D-FORMATO", "nombre inválido"))
            coll, it = self._index(m)[ident]
            fld = "name" if coll == "variables" else "label"
            scope_fld = {"variables": "scopeRef", "steps": "partialRef"}.get(coll)
            if scope_fld and any(o is not it and o.get(scope_fld) == it[scope_fld] and label_key(o[fld]) == label_key(new_name)
                                 for o in m[coll]):
                raise DiagnosticError(Diagnostic("D-NOMBRE-COLISION", f"«{new_name}» ya existe en el ámbito; el ID no cambia",
                                                 element=ident))
            it[fld] = new_name
            name_of = self._render_names(m)
            touched = []
            for e in m["expressions"]:
                if e["mode"] == "executable" and ident in e["bindings"].values():
                    used: dict[str, str] = {}

                    def record(i: str) -> str:
                        n = name_of(i)
                        used[n] = i
                        return n
                    e["text"] = ex.render(e["meaning"], record)
                    e["bindings"] = used
                    touched.append(e["id"])
            return touched
        return self._txn("renombrar", fn)

    def change_variable(self, vid: str, **changes: Any) -> list[dict[str, str]]:
        """Cambia rol, tipo, unidad, dominio o valor inicial; devuelve los usos afectados (REQ-EDT-07)."""
        impact = self.usages(vid)

        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            var = next(v for v in m["variables"] if v["id"] == vid)
            for k, val in changes.items():
                if k not in ("role", "type", "unit", "domain", "initialValue"):
                    raise DiagnosticError(Diagnostic("D-FORMATO", f"campo no editable: {k}"))
                var[k] = val
            t = parse_type(var["type"])
            if var["role"] != "input" and "initialValue" not in changes:
                var["initialValue"] = format_value(t, zero(t))  # al dejar de ser entrada, empieza en 0
            _check_initial(var["role"], t, var["initialValue"])
        self._txn("cambiar variable", fn)
        return impact

    # -- borrado con dependencias (REQ-EDT-05, documento 07 «Borrado y reparación»)
    def plan_delete(self, ids: list[str]) -> dict[str, list[str]]:
        m = self.model
        doomed = set(ids)
        changed = True
        while changed:
            changed = False
            for x in m["hierarchy"]["enclosures"]:
                if x["ownerStepRef"] in doomed and x["id"] not in doomed:
                    doomed |= {x["id"], x["partialRef"]}
                    changed = True
            for x in m["hierarchy"]["macros"]:
                if x["id"] in doomed and x["expansionRef"] not in doomed:
                    exp = next(e for e in m["hierarchy"]["expansions"] if e["id"] == x["expansionRef"])
                    doomed |= {exp["id"], exp["partialRef"]}
                    changed = True
            for pt in m["partials"]:
                if pt["id"] in doomed:
                    new = (set(pt["stepRefs"]) | set(pt["transitionRefs"])) - doomed
                    if new:
                        doomed |= new
                        changed = True
        for s in m["steps"]:
            if s["id"] in doomed:
                doomed |= set(s["actionRefs"])
        links = [t["id"] for t in m["transitions"] if t["id"] not in doomed and (set(t["preRefs"]) | set(t["postRefs"])) & doomed]
        return {"elements": sorted(doomed), "affectedTransitions": sorted(links),
                "sharedVariablesKept": sorted({v["id"] for v in m["variables"]} & {u for e in m["expressions"]
                                                                                    for u in e.get("bindings", {}).values()})}

    def delete(self, ids: list[str], keep_dangling: bool = False) -> dict[str, list[str]]:
        unknown = set(ids) - set(self._index(self.model))
        if unknown:
            raise DiagnosticError(Diagnostic("D-REF", f"no existen {sorted(unknown)}; no se borra nada"))
        plan = self.plan_delete(ids)
        doomed = set(plan["elements"])

        def fn(m: dict[str, Any], p: dict[str, Any]) -> dict[str, list[str]]:
            for coll in ("partials", "steps", "transitions", "actions", "forces", "draftLinks"):
                m[coll] = [x for x in m[coll] if x["id"] not in doomed]
            for coll in ("macros", "expansions", "enclosures"):
                m["hierarchy"][coll] = [x for x in m["hierarchy"][coll] if x["id"] not in doomed]
            for pt in m["partials"]:
                pt["stepRefs"] = [s for s in pt["stepRefs"] if s not in doomed]
                pt["transitionRefs"] = [t for t in pt["transitionRefs"] if t not in doomed]
            for st in m["steps"]:  # una acción borrada sola deja de figurar en su etapa
                st["actionRefs"] = [a for a in st["actionRefs"] if a not in doomed]
            if not keep_dangling:
                for t in m["transitions"]:
                    t["preRefs"] = [s for s in t["preRefs"] if s not in doomed]
                    t["postRefs"] = [s for s in t["postRefs"] if s not in doomed]
            used = {t["conditionRef"] for t in m["transitions"]}
            for a in m["actions"]:
                used |= {a.get("conditionRef"), a.get("valueRef"), (a.get("trigger") or {}).get("expressionRef")}
            m["expressions"] = [e for e in m["expressions"] if e["id"] in used]
            p["elementLayouts"] = [l for l in p["elementLayouts"] if l["elementRef"] not in doomed]
            if "notes" in p:  # el comentario se va con su elemento
                p["notes"] = [n for n in p["notes"] if not (isinstance(n, dict) and n.get("elementRef") in doomed)]
            for b in p.get("barras", []):
                b["arriba"] = [x for x in b["arriba"] if x not in doomed]
                b["abajo"] = [x for x in b["abajo"] if x not in doomed]
            huerfanas: dict[str, list[dict[str, Any]]] = {}
            for d in p.get("draftActions", []):  # una acción sin completar unida a una etapa borrada queda suelta
                if d.get("etapa") in doomed:
                    huerfanas.setdefault(d.pop("etapa"), []).append(d)
            for sid, ds in huerfanas.items():  # las de una misma etapa quedan juntas, con la colocación que tenían
                if len(ds) > 1:
                    gid = self.ids.new("grupo")
                    ds.sort(key=lambda d: d.get("orden", 0))
                    for i, d in enumerate(ds):
                        d.update(grupo=gid, orden=i, x=ds[0]["x"], y=ds[0]["y"])
                    previa = (p.get("actionLayouts") or {}).get(sid) if isinstance(p.get("actionLayouts"), dict) else None
                    if previa:
                        p["actionLayouts"] = {**p["actionLayouts"], gid: previa}
            if isinstance(p.get("actionLayouts"), dict):  # la colocación de las acciones de una etapa borrada
                p["actionLayouts"] = {k: v for k, v in p["actionLayouts"].items() if k not in doomed}
                if not p["actionLayouts"]:
                    del p["actionLayouts"]
            return plan
        return self._txn("borrar", fn)

    # -- copiar y pegar sin referencias accidentales (REQ-EDT-04)
    def copy(self, ids: list[str]) -> Fragment:
        m = self.model
        chosen = set(ids)
        for s in m["steps"]:
            if s["id"] in chosen:
                chosen |= set(s["actionRefs"])
        ents: dict[str, list[dict[str, Any]]] = {"steps": [], "transitions": [], "actions": [], "expressions": []}
        for coll in ("steps", "transitions", "actions"):
            ents[coll] = [copy.deepcopy(x) for x in m[coll] if x["id"] in chosen]
        expr_ids = {t["conditionRef"] for t in ents["transitions"]}
        for a in ents["actions"]:
            expr_ids |= {a.get("conditionRef"), a.get("valueRef"), (a.get("trigger") or {}).get("expressionRef")}
        ents["expressions"] = [copy.deepcopy(e) for e in m["expressions"] if e["id"] in expr_ids]
        internal = chosen | expr_ids
        external: dict[str, str] = {}
        idx = self._index(m)
        for t in ents["transitions"]:
            for r in t["preRefs"] + t["postRefs"]:
                if r not in internal:
                    external[r] = idx[r][0]
        for a in ents["actions"]:
            if a["targetRef"] not in internal:
                external[a["targetRef"]] = idx[a["targetRef"]][0]
        for e in ents["expressions"]:
            for r in e.get("bindings", {}).values():
                if r not in internal:
                    external[r] = idx[r][0]
        lays = [copy.deepcopy(l) for l in self.presentation["elementLayouts"] if l["elementRef"] in chosen]
        return Fragment(ents, lays, external)

    def plan_paste(self, frag: Fragment) -> dict[str, str]:
        """Referencias externas que requieren decisión explícita antes de confirmar."""
        return dict(sorted(frag.external_refs.items()))

    def paste(self, frag: Fragment, partial: str, decisions: dict[str, str]) -> dict[str, str]:
        missing = set(frag.external_refs) - set(decisions)
        if missing:
            raise DiagnosticError(Diagnostic("D-REF", f"falta decidir las referencias externas {sorted(missing)}"))

        def fn(m: dict[str, Any], p: dict[str, Any]) -> dict[str, str]:
            mapping: dict[str, str] = {}
            for coll, items in frag.entities.items():
                for it in items:
                    mapping[it["id"]] = self.ids.new(coll[0])
            for ext_id, choice in decisions.items():
                if choice == "pending":
                    mapping[ext_id] = f"pendiente.{ext_id}"  # D-REF al validar: bloquea el inicio
                elif choice != "keep":
                    raise DiagnosticError(Diagnostic("D-FORMATO", f"decisión desconocida {choice!r}"))

            def mp(i: str) -> str:
                return mapping.get(i, i)
            for coll, items in frag.entities.items():
                for it in items:
                    new = copy.deepcopy(it)
                    new["id"] = mp(it["id"])
                    for k in ("partialRef",):
                        if k in new:
                            new[k] = partial
                    for k in ("stepRef", "targetRef", "conditionRef", "valueRef"):
                        if k in new:
                            new[k] = mp(new[k])
                    for k in ("preRefs", "postRefs", "actionRefs"):
                        if k in new:
                            new[k] = [mp(x) for x in new[k]]
                    if "trigger" in new and "expressionRef" in new["trigger"]:
                        new["trigger"]["expressionRef"] = mp(new["trigger"]["expressionRef"])
                    if coll == "expressions" and new["mode"] == "executable":
                        new["bindings"] = {k: mp(v) for k, v in new["bindings"].items()}
                        new["meaning"] = _remap_meaning(new["meaning"], mp)
                    if coll == "steps" and any(s["partialRef"] == partial and s["label"] == new["label"] for s in m["steps"]):
                        new["label"] = f"{new['label']} (copia)"
                    m[coll].append(new)
                    if coll in ("steps", "transitions"):
                        tgt = next(x for x in m["partials"] if x["id"] == partial)
                        tgt["stepRefs" if coll == "steps" else "transitionRefs"].append(new["id"])
            for lay in frag.layouts:
                nl = copy.deepcopy(lay)
                nl["elementRef"] = mp(lay["elementRef"])
                p["elementLayouts"].append(nl)
            return {k: v for k, v in mapping.items() if k not in decisions or decisions[k] == "pending"}
        return self._txn("pegar", fn)


def _remap_meaning(m: dict[str, Any], mp: Callable[[str], str]) -> dict[str, Any]:
    out = dict(m)
    if "reference" in out:
        out["reference"] = mp(out["reference"])
    if "operands" in out:
        out["operands"] = [_remap_meaning(o, mp) for o in out["operands"]]
    return out


def duplicate_model(model: dict[str, Any], new_id: str, ids: IdGenerator) -> dict[str, Any]:
    """Duplicado con identidades nuevas y sin referencias al original (REQ-EDT-01, T-21a)."""
    mapping: dict[str, str] = {model["id"]: new_id}
    for ident, (coll, _) in Editor._index(model).items():
        mapping[ident] = ids.new(coll[0])

    def walk(x: Any, key: str | None = None) -> Any:
        if isinstance(x, dict):
            return {k: walk(v, k) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v, key) for v in x]
        if isinstance(x, str) and key not in ("label", "name", "text", "family", "formatVersion", "kind", "mode",
                                               "role", "unit", "operator", "type", "initialValue", "value") and x in mapping:
            return mapping[x]
        return x
    dup = walk(model)
    for e in dup["expressions"]:
        e["bindings"] = {k: mapping.get(v, v) for k, v in e.get("bindings", {}).items()}
    dup["revisionId"] = compute_revision(dup)
    return dup
