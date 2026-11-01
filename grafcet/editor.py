"""Operaciones de edición sin interfaz (documento 07; REQ-EDT-01..07, 09, 14; REQ-MOD-03, REQ-MOD-06).

Cada operación es una transacción: se aplica completa o no se aplica; una operación
fallida no entra en el historial; una edición nueva descarta la rama de rehacer
(REQ-EDT-05). Las operaciones de vista solo cambian el documento de presentación y no
cambian la revisión semántica (REQ-EDT-03, REQ-EDT-14). Conectar exige una relación
explícita: cruzar líneas nunca conecta (REQ-MOD-03). Las jerarquías (macroetapas, recintos con su
encapsulante y órdenes de forzado; documento 06, REQ-JER-02, 04, 05, 07) se construyen y se editan con las
operaciones de la sección «jerarquías».
"""
from __future__ import annotations

import copy
import re
from contextlib import contextmanager
from fractions import Fraction
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, NamedTuple

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
    presentation: dict[str, Any] = field(default_factory=dict)
    references: dict[str, tuple[str, dict[str, Any]]] = field(default_factory=dict)
    selected: list[str] = field(default_factory=list)


class MacroIds(NamedTuple):
    """Los IDs de una macroetapa y de su expansión (`Editor.add_macro`, `Editor.macro_info`)."""
    macro: str
    expansion: str  # el elemento de `hierarchy.expansions`
    partial: str  # el parcial de la expansión
    entry: str
    exit: str


class EnclosureIds(NamedTuple):
    """El ID de un recinto y el de su parcial (`Editor.new_enclosure`)."""
    enclosure: str
    partial: str


class Editor:
    def __init__(self, model: dict[str, Any], presentation: dict[str, Any] | None = None,
                 ids: IdGenerator | None = None) -> None:
        self.model = model
        self.presentation = presentation or new_presentation(model["id"])
        self.ids = ids or IdGenerator()
        self.undo_stack: list[tuple[str, Any, Any]] = []
        self.redo_stack: list[tuple[str, Any, Any]] = []
        # Reparación al abrir: un borrador sin alguno de sus extremos ya no se puede editar.
        # No se hace al validar ni al deshacer, para conservar intacto el historial de cada operación.
        endpoints = {x["id"] for coll in ("steps", "transitions") for x in model.get(coll, [])}
        endpoints |= {x["id"] for x in model.get("hierarchy", {}).get("macros", [])}
        self.cleaned_draft_link_ids: tuple[str, ...] = tuple(
            d["id"] for d in model.get("draftLinks", [])
            if d["fromRef"] not in endpoints or d["toRef"] not in endpoints)
        if self.cleaned_draft_link_ids:
            self.model = copy.deepcopy(model)
            self.model["draftLinks"] = [d for d in self.model["draftLinks"]
                                        if d["fromRef"] in endpoints and d["toRef"] in endpoints]
        self.dirty = bool(self.cleaned_draft_link_ids)
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
        resultado = validate_model(self.model)
        from .routing import validar_barras
        resultado.diagnostics.extend(validar_barras(self.model, self.bars()))
        return resultado

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
        """Un parcial nuevo. Su nombre es único entre los parciales (D-NOMBRE-COLISION), como al renombrarlo."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            self._free_label(m["partials"], label, "parcial")
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
            if at is not None:
                p["elementLayouts"][-1]["labelVisible"] = False
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
    # desactivacion, evento, forzado) y, si los tienen, variable (ID), condicion, valor, evento y limite (en la notación del
    # usuario), etapa, y grupo y orden: varias acciones sueltas pegadas forman un grupo (mismo `grupo`, ordenadas por
    # `orden`; comparten x, y y la colocación de `actionLayouts[grupo]`). Una orden de forzado sin completar (tipo «forzado»,
    # P-IMP-68) lleva en su lugar `destino` (ID del parcial que se fuerza), `forma` (explicit, current, empty o initial) y
    # `etapas` (ID de las etapas del destino que quedan activas, solo en la forma explícita); no se simula hasta que, unida
    # a una etapa y completa, pasa al modelo con `add_force`.
    DRAFT_TIPOS = ("continua", "condicionada", "limitada", "activacion", "desactivacion", "evento", "forzado")
    DRAFT_CAMPOS = ("variable", "condicion", "valor", "evento", "limite", "etapa", "grupo", "orden", "destino", "forma",
                    "etapas")
    DRAFT_FORMAS = ("explicit", "current", "empty", "initial")  # las formas de una orden de forzado (`add_force`)

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
        if datos.get("destino") and not any(q["id"] == datos["destino"] for q in m["partials"]):
            raise DiagnosticError(Diagnostic("D-REF", f"parcial inexistente: {datos['destino']}", element=datos["destino"]))
        if datos.get("forma") and datos["forma"] not in self.DRAFT_FORMAS:
            raise DiagnosticError(Diagnostic("D-FORMATO", f"forma de forzado desconocida: {datos['forma']!r}"))
        if datos.get("etapas") is not None:
            if not isinstance(datos["etapas"], list) or not all(isinstance(i, str) for i in datos["etapas"]):
                raise DiagnosticError(Diagnostic("D-FORMATO", "las etapas de una orden de forzado son una lista de ID"))
            for i in datos["etapas"]:
                if not any(s["id"] == i for s in m["steps"]):
                    raise DiagnosticError(Diagnostic("D-REF", f"etapa inexistente: {i}", element=i))
        if datos.get("grupo") is not None and not isinstance(datos["grupo"], str):
            raise DiagnosticError(Diagnostic("D-FORMATO", "el grupo de una acción suelta es un texto"))
        if datos.get("orden") is not None and (not isinstance(datos["orden"], int) or isinstance(datos["orden"], bool)):
            raise DiagnosticError(Diagnostic("D-FORMATO", "el orden de una acción suelta es un entero"))

    @staticmethod
    def _poner_campos(d: dict[str, Any], datos: dict[str, Any]) -> None:
        for k in ("tipo",) + Editor.DRAFT_CAMPOS:
            if k in datos:
                if datos[k] in (None, "") or datos[k] == []:
                    d.pop(k, None)
                elif k == "etapas":
                    d[k] = list(dict.fromkeys(datos[k]))
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
        if any(n["id"] == ident for n in self.annotations()):
            self.move_many({ident:(x,y)});return
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            lay = next((l for l in p["elementLayouts"] if l["elementRef"] == ident), None)
            if lay is None:
                self._layout(p, ident, (x, y))
            else:
                lay["x"], lay["y"] = _coord(x), _coord(y)
        self._txn("mover", fn, view_only=True)

    def _place(self, m: dict[str, Any], p: dict[str, Any], moves: dict[str, tuple[Any, Any]]) -> None:
        """Pone cada elemento de `moves` en su posición nueva (dentro de una operación de vista): una barra, una acción suelta
        o cualquier elemento con posición en `elementLayouts` (etapa, macroetapa, transición, marco de un recinto vacío)."""
        barras = {b["id"]: b for b in p.get("barras", [])}
        sueltas = {d["id"]: d for d in p.get("draftActions", []) if isinstance(d, dict) and "id" in d}
        conocidos = self._index(m)
        notas = {n["id"]:n for n in p.get("notes",[]) if n.get("kind") in ("text","image")}
        for ident, (x, y) in moves.items():
            if ident in barras:
                barras[ident]["x"], barras[ident]["y"] = _coord(x), _coord(y)
            elif ident in sueltas:
                sueltas[ident]["x"], sueltas[ident]["y"] = _coord(x), _coord(y)
            elif ident in notas:
                notas[ident]["x"],notas[ident]["y"] = _coord(x),_coord(y)
            elif ident in conocidos:
                lay = next((l for l in p["elementLayouts"] if l["elementRef"] == ident), None)
                if lay is None:
                    self._layout(p, ident, (x, y))
                else:
                    lay["x"], lay["y"] = _coord(x), _coord(y)
            else:
                raise DiagnosticError(Diagnostic("D-REF", f"no se puede mover {ident}: no existe", element=ident))

    @staticmethod
    def _set_styles(p: dict[str, Any], routes: dict[str, dict[str, Any] | None]) -> None:
        styles = p.setdefault("linkStyles", {}) if routes else {}
        for lid, style in routes.items():
            if style:
                styles[lid] = copy.deepcopy(style)
            else:
                styles.pop(lid, None)

    def move_many(self, moves: dict[str, tuple[Any, Any]], routes: dict[str, dict[str, Any] | None] | None = None) -> None:
        """Mueve varios elementos de presentación a la vez, en una sola operación de deshacer. `moves` da la posición
        nueva (x, y) de cada uno: etapas, macroetapas, transiciones, marcos de recintos vacíos (su posición en
        `elementLayouts`), barras (x, y) y acciones sueltas (x, y; todas las de un grupo). `routes` cambia, en la misma
        operación, el estilo de enlaces (ID de enlace -> estilo nuevo, o None para quitarlo): por ejemplo, las rutas con
        coordenadas absolutas de los enlaces cuyos dos extremos se mueven. Un ID que no existe rechaza la operación
        entera (D-REF). Solo presentación: el modelo y su revisión no cambian."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            self._place(m, p, moves)
            self._set_styles(p, routes or {})
        self._txn("mover varios", fn, view_only=True)

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
                aviso = self._link_in(m, a, z, quiet=True)  # (cada pareja se enlaza aunque otra ya haya dejado un borrador)
                diag = diag or aviso
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

    # Una macroetapa se enlaza con las transiciones como una etapa (documento 06: M como siguiente es su entrada y
    # como precedente, su salida; lo resuelve el modelo al compilar)
    _ETAPAS = ("steps", "macros")

    def _link_in(self, m: dict[str, Any], src: str, dst: str, quiet: bool = False) -> Diagnostic | None:
        idx = self._index(m)
        ks, kd = idx[src][0], idx[dst][0]
        if ks in self._ETAPAS and kd == "transitions":
            refs, item = idx[dst][1]["preRefs"], src
        elif ks == "transitions" and kd in self._ETAPAS:
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
        if ks in self._ETAPAS and kd == "transitions":
            t = idx[dst][1]
            t["preRefs"] = [x for x in t["preRefs"] if x != src]
        elif ks == "transitions" and kd in self._ETAPAS:
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

    def annotations(self):
        from .annotations import visual_notes
        return visual_notes(self.presentation)

    def add_annotation(self, kind, at, **properties):
        from .annotations import visual_notes
        def fn(m,p):
            note = {"id": self.ids.new("visual"), "kind": kind, "x": _coord(at[0]), "y": _coord(at[1]),
                    "width": "200", "height": "100", **copy.deepcopy(properties)}
            for k in ("x","y","width","height","size"):
                if k in note:note[k]=_coord(note[k])
            if not visual_notes({"notes":[note]}):
                raise DiagnosticError(Diagnostic("D-FORMATO", "texto o imagen no válidos"))
            p.setdefault("notes",[]).append(note)
            return note["id"]
        return self._txn("añadir texto" if kind == "text" else "añadir imagen",fn,view_only=True)

    def update_annotation(self, ident, **properties):
        from .annotations import visual_notes
        def fn(m,p):
            n=next((n for n in p.get("notes",[]) if n.get("id")==ident and n.get("kind") in ("text","image")),None)
            if n is None:raise DiagnosticError(Diagnostic("D-REF","no existe el texto o la imagen",element=ident))
            n.update({k:copy.deepcopy(v) for k,v in properties.items() if k not in ("id","kind","elementRef")})
            for k in ("x","y","width","height","size"):
                if k in n:n[k]=_coord(n[k])
            if not visual_notes({"notes":[n]}):raise DiagnosticError(Diagnostic("D-FORMATO","texto o imagen no válidos",element=ident))
        self._txn("editar texto o imagen",fn,view_only=True)

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

    # Equidistanciar alturas (solo presentación): cada cadena (los elementos enlazados entre sí, etapas, macroetapas,
    # transiciones y las barras que los unen, dentro de un mismo parcial) se reparte en niveles que alternan etapas y
    # transiciones, con la misma distancia entre niveles consecutivos; la x de cada elemento no cambia.
    @staticmethod
    def _positions(p: dict[str, Any]) -> dict[str, tuple[Fraction, Fraction]]:
        """Posición (x, y) de cada elemento con posición en la primera vista de la presentación."""
        vistas = [v["id"] for v in p.get("views", [])]
        vista = vistas[0] if vistas else None
        out: dict[str, tuple[Fraction, Fraction]] = {}
        for lay in p.get("elementLayouts", []):
            if vista is None or lay.get("viewRef") == vista:
                try:
                    out[lay["elementRef"]] = (Fraction(lay["x"]), Fraction(lay["y"]))
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    continue
        return out

    def _chains(self, scope: Iterable[str] | None, pos: dict[str, tuple[Fraction, Fraction]]) -> tuple[
            dict[str, str], set[tuple[str, str]], dict[str, tuple[list[str], list[str]]], list[tuple[list[str], list[str]]]]:
        """Las cadenas de `scope` (los de `equidistribute`) entre los elementos con posición en `pos`: los elementos
        (ID -> parcial), los enlaces dirigidos de arriba abajo, las barras (ID -> (los de arriba, los de abajo) de su
        parcial) y las cadenas elegidas, cada una con sus elementos y sus barras, de dos elementos o más."""
        m, p = self.model, self.presentation
        nodos = {s["id"]: s["partialRef"] for s in m["steps"]}
        nodos.update({x["id"]: x["partialRef"] for x in m["hierarchy"]["macros"]})
        nodos.update({t["id"]: t["partialRef"] for t in m["transitions"]})
        nodos = {i: parcial for i, parcial in nodos.items() if i in pos}
        aristas: set[tuple[str, str]] = set()
        for t in m["transitions"]:
            aristas |= {(s, t["id"]) for s in t["preRefs"]} | {(t["id"], s) for s in t["postRefs"]}
        barras: dict[str, tuple[list[str], list[str]]] = {}
        for b in p.get("barras", []):
            arriba = [i for i in b.get("arriba", []) if i in nodos]
            abajo = [i for i in b.get("abajo", []) if i in nodos]
            if arriba or abajo:
                parcial = nodos[(arriba + abajo)[0]]
                barras[b["id"]] = ([i for i in arriba if nodos[i] == parcial], [i for i in abajo if nodos[i] == parcial])
                aristas |= {(a, z) for a in barras[b["id"]][0] for z in barras[b["id"]][1]}
        aristas = {(a, z) for a, z in aristas if a != z and a in nodos and z in nodos and nodos[a] == nodos[z]}
        raiz = {i: i for i in [*nodos, *barras]}

        def buscar(i: str) -> str:
            while raiz[i] != i:
                raiz[i] = raiz[raiz[i]]
                i = raiz[i]
            return i
        for a, z in aristas:
            raiz[buscar(a)] = buscar(z)
        for bid, (arriba, abajo) in barras.items():
            for i in arriba + abajo:
                raiz[buscar(bid)] = buscar(i)
        elegidas: set[str] | None = None
        if scope is not None:
            semillas: set[str] = set()
            for ident in scope:
                if ident in raiz:
                    semillas.add(ident)
                elif "|" in ident:  # un enlace: la cadena de cualquiera de sus extremos
                    semillas |= {i for i in ident.split("|")[:2] if i in raiz}
                else:  # un parcial: todas sus cadenas
                    semillas |= {i for i, parcial in nodos.items() if parcial == ident}
            elegidas = {buscar(i) for i in semillas}
        cadenas: dict[str, list[str]] = {}
        for i in raiz:
            cadenas.setdefault(buscar(i), []).append(i)
        out = []
        for r, miembros in sorted(cadenas.items()):
            ns, bs = sorted(i for i in miembros if i in nodos), sorted(i for i in miembros if i in barras)
            if len(ns) >= 2 and (elegidas is None or r in elegidas):
                out.append((ns, bs))
        return nodos, aristas, barras, out

    def chains(self, scope: Iterable[str] | None = None,
               positions: dict[str, tuple[Any, Any]] | None = None) -> list[list[str]]:
        """Las cadenas de `scope` (ver `equidistribute`; None, todas): para cada una, los ID de sus elementos y, al final, de
        sus barras. Solo cuentan los elementos con posición (en la presentación o en `positions`)."""
        pos = self._positions(self.presentation)
        for ident, (x, y) in (positions or {}).items():
            pos.setdefault(ident, (Fraction(str(x)), Fraction(str(y))))
        return [ns + bs for ns, bs in self._chains(scope, pos)[3]]

    def equidistribute(self, scope: Iterable[str] | None, step: Any, extent: dict[str, tuple[Any, Any]] | None = None,
                       margin: Any = 8, grid: Any = 20, positions: dict[str, tuple[Any, Any]] | None = None) -> list[str]:
        """Equidistancia las alturas de las cadenas de `scope`: los ID de elementos (cada uno lleva su cadena entera), de
        enlaces (`transición|etapa|pre` o `post`; la de cualquiera de sus extremos), de barras o de parciales (todas sus
        cadenas); None, todas las cadenas de todos los parciales. Una cadena es la componente conexa de etapas,
        macroetapas y transiciones enlazados dentro de un parcial, más las barras que unen a esos elementos (una barra con
        elementos de varios parciales se une solo a los del primero); una sola etapa o transición sin enlaces no es una
        cadena.

        Cada elemento recibe un nivel: el camino más largo desde los que no reciben ningún enlace, sin contar los enlaces
        de realimentación (los que vuelven hacia arriba en el dibujo; si aun así queda un ciclo, el que lo cierra en una
        búsqueda en profundidad). Los niveles consecutivos distan `step` (la distancia estándar del editor) o más, en
        múltiplos de la rejilla `grid`: lo que pide `extent` ({ID: (arriba, abajo)}: cuánto sobresale por encima y por debajo
        de su centro lo que acompaña al elemento, las acciones de una etapa; lo que no figure cuenta 0), más `margin` entre
        lo que sobresale del nivel de arriba y del de abajo, de modo que no se solapen. Cada barra va a mitad de la
        distancia que le toca, justo debajo del más bajo de sus elementos de arriba (o encima del más alto de los de abajo,
        si no tiene ninguno arriba); su hueco es un múltiplo de 2·grid para que quede en la rejilla. El primer nivel se
        queda donde está el elemento más alto de la cadena (en la rejilla). `positions` da (x, y) de elementos que aún no
        tienen posición guardada.

        Una sola operación de deshacer, solo presentación (el modelo y su revisión no cambian). Descarta, en los enlaces con
        un extremo que se mueve, la parte de su ruta manual en coordenadas absolutas de altura (exitY, entryY, middleY). Si
        no hay nada que cambiar (ya está equidistanciado) no hace nada. Devuelve los ID de lo que se movió (elementos y
        barras)."""
        m, p = self.model, self.presentation
        paso, margen, rejilla = (Fraction(str(v)) for v in (step, margin, grid))
        ext = {i: (Fraction(str(a)), Fraction(str(b))) for i, (a, b) in (extent or {}).items()}
        pos = self._positions(p)
        for ident, (x, y) in (positions or {}).items():
            pos.setdefault(ident, (Fraction(str(x)), Fraction(str(y))))
        nodos, aristas, barras, cadenas = self._chains(scope, pos)
        iniciales = {s["id"] for s in m["steps"] if s["initial"] is True}
        movidos: dict[str, tuple[Fraction, Fraction]] = {}
        bpos = {b["id"]: (Fraction(b["x"]), Fraction(b["y"])) for b in p.get("barras", [])}
        for ns, bs in cadenas:
            propios = set(ns)
            nivel = _niveles(ns, [(a, z) for a, z in aristas if a in propios], {i: pos[i][1] for i in ns},
                             {i: pos[i][0] for i in ns}, iniciales)
            ultimo = max(nivel.values())
            por_nivel: list[list[str]] = [[] for _ in range(ultimo + 1)]
            for n in ns:
                por_nivel[nivel[n]].append(n)
            frontera = {}  # frontera k (entre los niveles k y k+1) en que va cada barra; -1, encima del primero
            for bid in bs:
                arriba, abajo = barras[bid]
                frontera[bid] = max(nivel[i] for i in arriba) if arriba else min(nivel[i] for i in abajo) - 1
            hueco = []
            for k in range(ultimo):
                pide = margen + max((ext.get(n, (0, 0))[1] for n in por_nivel[k]), default=0) \
                    + max((ext.get(n, (0, 0))[0] for n in por_nivel[k + 1]), default=0)
                hueco.append(_techo(max(paso, pide), 2 * rejilla if k in frontera.values() else rejilla))
            alturas = [_a_rejilla(min(pos[n][1] for n in ns), rejilla)]
            for g in hueco:
                alturas.append(alturas[-1] + g)
            for n in ns:
                if pos[n][1] != alturas[nivel[n]]:
                    movidos[n] = (pos[n][0], alturas[nivel[n]])
            medio = _techo(paso / 2, rejilla)
            for bid, k in frontera.items():
                y = alturas[0] - medio if k < 0 else alturas[k] + (hueco[k] / 2 if k < ultimo else medio)
                if bpos[bid][1] != y:
                    movidos[bid] = (bpos[bid][0], y)
        rutas: dict[str, dict[str, Any] | None] = {}
        for lid, estilo in p.get("linkStyles", {}).items():  # las alturas absolutas de una ruta manual ya no valen
            ruta = estilo.get("route") if isinstance(estilo, dict) else None
            if isinstance(ruta, dict) and any(i in movidos for i in lid.split("|")[:2]):
                resto = {k: v for k, v in ruta.items() if k not in ("exitY", "entryY", "middleY")}
                if len(resto) != len(ruta):
                    nuevo = {k: v for k, v in estilo.items() if k != "route"}
                    rutas[lid] = {**nuevo, **({"route": resto} if resto else {})} or None
        if not movidos and not rutas:
            return []

        def fn(m2: dict[str, Any], p2: dict[str, Any]) -> None:
            self._place(m2, p2, movidos)
            self._set_styles(p2, rutas)
        self._txn("equidistanciar alturas", fn, view_only=True)
        return list(movidos)

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
            if coll not in ("variables", "steps", "transitions", "partials", "macros"):
                raise DiagnosticError(Diagnostic("D-FORMATO", "este elemento no tiene nombre", element=ident))
            fld = "name" if coll == "variables" else "label"
            scope_fld = {"variables": "scopeRef", "steps": "partialRef"}.get(coll)
            if scope_fld and any(o is not it and o.get(scope_fld) == it[scope_fld] and label_key(o[fld]) == label_key(new_name)
                                 for o in m[coll]):
                raise DiagnosticError(Diagnostic("D-NOMBRE-COLISION", f"«{new_name}» ya existe en el ámbito; el ID no cambia",
                                                 element=ident))
            if coll in ("partials", "macros"):  # el nombre de un parcial o de una macroetapa es único en el modelo
                same = m["partials"] if coll == "partials" else m["hierarchy"]["macros"]
                if any(o is not it and label_key(o["label"]) == label_key(new_name) for o in same):
                    raise DiagnosticError(Diagnostic("D-NOMBRE-COLISION", f"«{new_name}» ya existe; el ID no cambia",
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

    # -- jerarquías: macroetapas, recintos con su encapsulante y órdenes de forzado (documento 06; P-IMP-23..27)
    # Cada operación deja el modelo como lo declara el documento 09. Si deja algo mal formado (una referencia que no
    # existe, un recinto con dos encapsulantes, un ciclo, una etapa fuera del recinto o del destino), no se aplica y el
    # error trae los diagnósticos que da `validate()` (D-REF, D-PROPIETARIO, D-JERARQUIA-CICLO, D-FORMATO). Lo que se
    # completa después (la etapa inicial de un recinto, un conflicto posible entre órdenes) no se rechaza: lo informa
    # `validate()`. Colocar una macroetapa en el dibujo es presentación: `move` la mueve como a una etapa.
    _ESTRUCTURALES = ("D-REF", "D-PROPIETARIO", "D-JERARQUIA-CICLO", "D-FORMATO", "D-ID")
    # Lo que un diseño a medias aún no cumple (sin etapas iniciales, transición sin un lado, memoria con valor inicial)
    # no es estructura: lo informa `validate()`, pero no impide crear lo primero (una macroetapa en un grafcet vacío)
    _A_MEDIAS = {"1.5": "B", "6.1": "B", "6.2": "B", "6.4": "B"}

    def _estructurales(self, m: dict[str, Any]) -> list[Diagnostic]:
        return [d for d in validate_model(m, self._A_MEDIAS).diagnostics if d.code in self._ESTRUCTURALES and d.blocks_start]

    def _sin_nuevos(self, m: dict[str, Any], antes: list[Diagnostic]) -> None:
        """Rechaza la operación si deja un diagnóstico estructural que antes de ella no estaba."""
        vistos = {(d.code, d.element, d.message) for d in antes}
        nuevos = [d for d in self._estructurales(m) if (d.code, d.element, d.message) not in vistos]
        if nuevos:
            raise DiagnosticError(*nuevos)

    @staticmethod
    def _find(items: list[dict[str, Any]], ident: str, what: str) -> dict[str, Any]:
        it = next((x for x in items if x["id"] == ident), None)
        if it is None:
            raise DiagnosticError(Diagnostic("D-REF", f"no existe {what}: {ident}", element=ident))
        return it

    @staticmethod
    def _free_label(items: list[dict[str, Any]], label: str, what: str) -> None:
        if not valid_label(label):
            raise DiagnosticError(Diagnostic("D-FORMATO", "etiqueta inválida"))
        if any(label_key(x["label"]) == label_key(label) for x in items):
            raise DiagnosticError(Diagnostic("D-NOMBRE-COLISION", f"«{label}» ya existe como {what}"))

    def add_macro(self, partial: str, label: str, at: tuple[Any, Any] | None = None, entry_label: str | None = None,
                  exit_label: str | None = None, expansion_label: str | None = None) -> MacroIds:
        """Una macroetapa en `partial`, con su expansión: un parcial nuevo dentro de `partial` (regla 8.1 C) con su etapa
        de entrada y su etapa de salida (kind entry y exit); una expansión por macroetapa (T-18c). Si no se dan, las
        etiquetas de la entrada y la salida son E<n> y S<n> con el primer n libre, y la del parcial es la de la
        macroetapa. `at` coloca la macroetapa en el dibujo; la entrada y la salida se colocan con `move`."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> MacroIds:
            antes = self._estructurales(m)
            self._find(m["partials"], partial, "el parcial")
            self._free_label(m["hierarchy"]["macros"], label, "macroetapa")
            exp_label = label if expansion_label is None else expansion_label
            self._free_label(m["partials"], exp_label, "parcial")
            usadas = {label_key(s["label"]) for s in m["steps"]} | {s["id"] for s in m["steps"]}
            n = 1
            while f"E{n}" in usadas or f"S{n}" in usadas:
                n += 1
            ent = f"E{n}" if entry_label is None else entry_label
            sal = f"S{n}" if exit_label is None else exit_label
            for lab in (ent, sal):
                if not valid_label(lab):
                    raise DiagnosticError(Diagnostic("D-FORMATO", "etiqueta inválida"))
            if label_key(ent) == label_key(sal):
                raise DiagnosticError(Diagnostic("D-NOMBRE-COLISION", f"la entrada y la salida de la expansión no pueden "
                                                 f"llamarse igual («{ent}»)"))
            xp, mid, xid = self.ids.new("g"), self.ids.new("m"), self.ids.new("x")
            eid, sid = self.ids.new("s"), self.ids.new("s")
            m["partials"].append({"id": xp, "label": exp_label, "stepRefs": [eid, sid], "transitionRefs": [],
                                  "ownerRef": partial})
            for ident, lab, kind in ((eid, ent, "entry"), (sid, sal, "exit")):
                m["steps"].append({"id": ident, "label": lab, "partialRef": xp, "kind": kind, "initial": False,
                                   "actionRefs": []})
            m["hierarchy"]["macros"].append({"id": mid, "label": label, "partialRef": partial, "expansionRef": xid})
            m["hierarchy"]["expansions"].append({"id": xid, "ownerMacroRef": mid, "partialRef": xp, "entryRef": eid,
                                                 "exitRef": sid})
            self._layout(p, mid, at)
            self._sin_nuevos(m, antes)
            return MacroIds(mid, xid, xp, eid, sid)
        return self._txn("crear macroetapa", fn)

    def macro_info(self, macro: str) -> MacroIds:
        """Los IDs de la macroetapa y de su expansión: lo que hace falta para abrirla (REQ-EDT-08, REQ-JER-07)."""
        mac = self._find(self.model["hierarchy"]["macros"], macro, "la macroetapa")
        x = self._find(self.model["hierarchy"]["expansions"], mac["expansionRef"], "la expansión")
        return MacroIds(macro, x["id"], x["partialRef"], x["entryRef"], x["exitRef"])

    def set_step_kind(self, step: str, kind: str) -> None:
        """Convierte una etapa ordinaria en encapsulante («enclosing») o la devuelve a «ordinary». Una encapsulante con
        recintos no vuelve a ordinaria hasta que se borran; la entrada y la salida de una expansión no cambian de tipo."""
        st = self._find(self.model["steps"], step, "la etapa")
        if kind not in ("ordinary", "enclosing"):
            raise DiagnosticError(Diagnostic("D-FORMATO", f"tipo de etapa desconocido: {kind!r}", element=step))
        if st["kind"] in ("entry", "exit"):
            raise DiagnosticError(Diagnostic("D-FORMATO", f"«{st['label']}» es la entrada o la salida de una expansión: "
                                             "no cambia de tipo", element=step))
        if st["kind"] == kind:
            return
        recintos = [x["id"] for x in self.model["hierarchy"]["enclosures"] if x["ownerStepRef"] == step]
        if kind == "ordinary" and recintos:
            raise DiagnosticError(Diagnostic("D-FORMATO", f"«{st['label']}» es la encapsulante de {len(recintos)} "
                                             "recinto(s): bórrelos antes de devolverla a ordinaria", element=step))

        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            self._find(m["steps"], step, "la etapa")["kind"] = kind
        self._txn("convertir en encapsulante" if kind == "enclosing" else "devolver a ordinaria", fn)

    def add_enclosure(self, owner_step: str, partial: str, activation_steps: list[str] = ()) -> str:
        """Un recinto: `partial`, ya creado (por ejemplo con `add_partial(label, owner=…)`), pasa a ser recinto de la
        encapsulante `owner_step` (kind enclosing), con las etapas de `activation_steps` marcadas con el enlace de
        activación. Cada recinto tiene una sola encapsulante; una encapsulante puede tener varios recintos. Si el
        parcial no declara dueño (`ownerRef`), pasa a ser el parcial de la encapsulante (P-IMP-27: así su contenido
        cuenta en X_dueño); si declara otro, se rechaza (D-FORMATO). Devuelve el ID del recinto."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            antes = self._estructurales(m)
            owner = self._find(m["steps"], owner_step, "la etapa")
            part = self._find(m["partials"], partial, "el parcial")
            if owner["kind"] != "enclosing":
                raise DiagnosticError(Diagnostic("D-FORMATO", f"«{owner['label']}» debe ser una etapa encapsulante "
                                                 "(kind=enclosing): conviértala antes", element=owner_step))
            if part.get("ownerRef", owner["partialRef"]) != owner["partialRef"]:
                raise DiagnosticError(Diagnostic("D-FORMATO", f"el parcial «{part['label']}» está dentro de otro parcial "
                                                 f"que el de la encapsulante «{owner['label']}»", element=partial,
                                                 field="ownerRef"))
            part.setdefault("ownerRef", owner["partialRef"])
            rid = self.ids.new("r")
            m["hierarchy"]["enclosures"].append({"id": rid, "ownerStepRef": owner_step, "partialRef": partial,
                                                 "activationRefs": list(dict.fromkeys(activation_steps))})
            self._sin_nuevos(m, antes)
            return rid
        return self._txn("crear recinto", fn)

    def new_enclosure(self, owner_step: str, label: str) -> EnclosureIds:
        """Un recinto nuevo para la encapsulante: un parcial vacío, dentro del de la etapa, sin ninguna etapa marcada
        todavía (`set_activation`). Si la encapsulante es inicial, `validate()` avisa (D-JERARQUIA-INICIAL) hasta que el
        recinto tenga su etapa inicial."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> EnclosureIds:
            antes = self._estructurales(m)
            owner = self._find(m["steps"], owner_step, "la etapa")
            if owner["kind"] != "enclosing":
                raise DiagnosticError(Diagnostic("D-FORMATO", f"«{owner['label']}» debe ser una etapa encapsulante "
                                                 "(kind=enclosing): conviértala antes", element=owner_step))
            self._free_label(m["partials"], label, "parcial")
            pid, rid = self.ids.new("g"), self.ids.new("r")
            m["partials"].append({"id": pid, "label": label, "stepRefs": [], "transitionRefs": [],
                                  "ownerRef": owner["partialRef"]})
            m["hierarchy"]["enclosures"].append({"id": rid, "ownerStepRef": owner_step, "partialRef": pid,
                                                 "activationRefs": []})
            self._sin_nuevos(m, antes)
            return EnclosureIds(rid, pid)
        return self._txn("crear recinto", fn)

    def set_activation(self, step: str, on: bool = True) -> None:
        """Marca (o desmarca) una etapa de un recinto con el enlace de activación: al activarse la encapsulante, esa
        etapa se activa (el «*» del dibujo). Inicial y enlace de activación son cosas distintas (documento 06)."""
        st = self._find(self.model["steps"], step, "la etapa")
        recintos = [x for x in self.model["hierarchy"]["enclosures"] if x["partialRef"] == st["partialRef"]]
        if not recintos:
            raise DiagnosticError(Diagnostic("D-REF", f"«{st['label']}» no está en ningún recinto: el enlace de activación "
                                             "es de las etapas de un recinto", element=step))
        if all((step in x["activationRefs"]) == bool(on) for x in recintos):
            return

        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            for x in m["hierarchy"]["enclosures"]:
                if x["partialRef"] == st["partialRef"]:
                    refs = [s for s in x["activationRefs"] if s != step]
                    x["activationRefs"] = refs + [step] if on else refs
        self._txn("enlace de activación" if on else "quitar el enlace de activación", fn)

    # Órdenes de forzado (LOC tabla 9): `kind` es «explicit» (con el conjunto `steps` de etapas del destino), «current»
    # (la situación que tenga el destino al entrar en vigor), «empty» o «initial»
    def add_force(self, source_step: str, target_partial: str, kind: str, steps: list[str] | None = None) -> str:
        """Una orden de forzado vinculada a `source_step`: mientras esa etapa está activa, impone al parcial destino
        la situación de `kind`. `steps` solo va con «explicit». Un ciclo en la relación superior→inferior se rechaza
        (D-JERARQUIA-CICLO); dos órdenes con igual destino y objetivo distinto se aceptan y `validate()` avisa
        (D-FORZADO-CONFLICTO). Devuelve el ID de la orden."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> str:
            antes = self._estructurales(m)
            fid = self.ids.new("f")
            item: dict[str, Any] = {"id": fid, "sourceStepRef": source_step, "targetPartialRef": target_partial,
                                    "targetKind": kind}
            if steps is not None:
                item["targetSteps"] = list(dict.fromkeys(steps))
            m["forces"].append(item)
            self._sin_nuevos(m, antes)
            return fid
        return self._txn("crear orden de forzado", fn)

    def set_force(self, fid: str, target_partial: str | None = None, kind: str | None = None,
                  steps: list[str] | None = None, source_step: str | None = None) -> None:
        """Cambia el destino, la forma, las etapas o el origen de una orden (lo que sea None no cambia). Con la forma
        «explicit» y sin `steps`, conserva las que tenía; con otra forma, quita las etapas."""
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            antes = self._estructurales(m)
            f = self._find(m["forces"], fid, "la orden de forzado")
            if source_step is not None:
                f["sourceStepRef"] = source_step
            if target_partial is not None:
                f["targetPartialRef"] = target_partial
            if kind is not None:
                f["targetKind"] = kind
            if steps is not None:
                f["targetSteps"] = list(dict.fromkeys(steps))
            elif f["targetKind"] != "explicit":
                f.pop("targetSteps", None)
            self._sin_nuevos(m, antes)
        self._txn("editar orden de forzado", fn)

    def delete_force(self, fid: str) -> None:
        self._find(self.model["forces"], fid, "la orden de forzado")
        self.delete([fid])

    # -- consulta de solo lectura, para mostrar y navegar la jerarquía (REQ-EDT-08, REQ-JER-07)
    def partial_roles(self) -> dict[str, dict[str, Any]]:
        """De qué tipo es cada parcial: «root» (no está dentro de otro), «expansion» (expansión de una macroetapa) o
        «enclosure» (recinto de una encapsulante). Además: `parent` (el parcial que lo contiene, que es el de la
        macroetapa o el de la encapsulante), `text` (para mostrar) y, según el tipo, `macro`, `expansion`, `entry` y `exit`,
        o bien `enclosure`, `ownerStep` y `activation`."""
        m = self.model
        name_of = self._render_names(m)
        steps = {s["id"]: s for s in m["steps"]}
        macros = {x["id"]: x for x in m["hierarchy"]["macros"]}
        roles: dict[str, dict[str, Any]] = {p["id"]: {"kind": "root", "parent": None, "text": "raíz"} for p in m["partials"]}
        for x in m["hierarchy"]["expansions"]:
            if x["partialRef"] in roles and x["ownerMacroRef"] in macros:
                roles[x["partialRef"]] = {
                    "kind": "expansion", "parent": macros[x["ownerMacroRef"]]["partialRef"], "macro": x["ownerMacroRef"],
                    "expansion": x["id"], "entry": x["entryRef"], "exit": x["exitRef"],
                    "text": f"expansión de la macroetapa {name_of(x['ownerMacroRef'])}"}
        for x in m["hierarchy"]["enclosures"]:
            if x["partialRef"] in roles and x["ownerStepRef"] in steps:
                roles[x["partialRef"]] = {
                    "kind": "enclosure", "parent": steps[x["ownerStepRef"]]["partialRef"], "enclosure": x["id"],
                    "ownerStep": x["ownerStepRef"], "activation": list(x["activationRefs"]),
                    "text": f"recinto de la encapsulante {name_of(x['ownerStepRef'])}"}
        return roles

    # -- borrado con dependencias (REQ-EDT-05, documento 07 «Borrado y reparación»)
    def plan_delete(self, ids: list[str]) -> dict[str, list[str]]:
        """Todo lo que se llevaría borrar `ids`. Una macroetapa se va con su expansión (y al revés: sin expansión no hay
        macroetapa) y un recinto con su encapsulante, con todo lo que contienen; un parcial, con lo que tiene dentro. Una
        orden de forzado se va con su etapa de origen o con su parcial destino; los enlaces en borrador, con cualquiera
        de sus extremos. `affectedHierarchy` son los recintos y las
        órdenes que se quedan y pierden una etapa de su enlace de activación o de su conjunto explícito."""
        m = self.model
        doomed = set(ids)
        expansions = {e["id"]: e for e in m["hierarchy"]["expansions"]}
        changed = True
        while changed:
            changed = False
            for x in m["hierarchy"]["enclosures"]:
                own = {x["id"], x["partialRef"]}
                if (x["ownerStepRef"] in doomed or doomed & own) and not own <= doomed:
                    doomed |= own
                    changed = True
            for x in m["hierarchy"]["macros"]:
                exp = expansions.get(x["expansionRef"])
                own = {x["id"]} | ({exp["id"], exp["partialRef"]} if exp else set())
                if (x["partialRef"] in doomed or doomed & own) and not own <= doomed:
                    doomed |= own
                    changed = True
            for pt in m["partials"]:
                if pt["id"] in doomed:
                    new = (set(pt["stepRefs"]) | set(pt["transitionRefs"])) - doomed
                elif pt.get("ownerRef") in doomed:
                    new = {pt["id"]}
                else:
                    continue
                if new:
                    doomed |= new
                    changed = True
        for s in m["steps"]:
            if s["id"] in doomed:
                doomed |= set(s["actionRefs"])
        doomed |= {f["id"] for f in m["forces"] if f["sourceStepRef"] in doomed or f["targetPartialRef"] in doomed}
        doomed |= {d["id"] for d in m.get("draftLinks", []) if d["fromRef"] in doomed or d["toRef"] in doomed}
        doomed |= {n["id"] for n in self.annotations() if n.get("partialRef") in doomed}
        links = [t["id"] for t in m["transitions"] if t["id"] not in doomed and (set(t["preRefs"]) | set(t["postRefs"])) & doomed]
        marks = [x["id"] for x in m["hierarchy"]["enclosures"] if x["id"] not in doomed and set(x["activationRefs"]) & doomed]
        marks += [f["id"] for f in m["forces"] if f["id"] not in doomed and set(f.get("targetSteps", [])) & doomed]
        return {"elements": sorted(doomed), "affectedTransitions": sorted(links), "affectedHierarchy": sorted(marks),
                "sharedVariablesKept": sorted({v["id"] for v in m["variables"]} & {u for e in m["expressions"]
                                                                                    for u in e.get("bindings", {}).values()})}

    def delete(self, ids: list[str], keep_dangling: bool = False) -> dict[str, list[str]]:
        visuales = {n["id"] for n in self.annotations()}
        unknown = set(ids) - set(self._index(self.model)) - visuales
        if unknown:
            raise DiagnosticError(Diagnostic("D-REF", f"no existen {sorted(unknown)}; no se borra nada"))
        plan = self.plan_delete(ids)
        doomed = set(plan["elements"])
        if doomed <= visuales:
            def quitar(m,p):
                p["notes"]=[n for n in p.get("notes",[]) if n.get("id") not in doomed]
                return plan
            return self._txn("borrar textos o imágenes",quitar,view_only=True)
        for x in self.model["hierarchy"]["expansions"]:  # la entrada y la salida de una expansión no se borran solas
            sueltas = sorted({x["entryRef"], x["exitRef"]} & doomed)
            if x["id"] not in doomed and sueltas:
                name_of = self._render_names(self.model)
                raise DiagnosticError(Diagnostic(
                    "D-REF", f"«{name_of(sueltas[0])}» es la entrada o la salida de la expansión de la macroetapa "
                    f"«{name_of(x['ownerMacroRef'])}»: borre la macroetapa entera, no solo esa etapa", element=sueltas[0]))

        def fn(m: dict[str, Any], p: dict[str, Any]) -> dict[str, list[str]]:
            for coll in ("partials", "steps", "transitions", "actions", "forces", "draftLinks"):
                m[coll] = [x for x in m[coll] if x["id"] not in doomed]
            for coll in ("macros", "expansions", "enclosures"):
                m["hierarchy"][coll] = [x for x in m["hierarchy"][coll] if x["id"] not in doomed]
            for x in m["hierarchy"]["enclosures"]:  # el enlace de activación de una etapa borrada desaparece con ella
                x["activationRefs"] = [s for s in x["activationRefs"] if s not in doomed]
            for f in m["forces"]:
                if "targetSteps" in f:
                    f["targetSteps"] = [s for s in f["targetSteps"] if s not in doomed]
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
                p["notes"] = [n for n in p["notes"] if not (isinstance(n, dict) and (n.get("elementRef") in doomed or n.get("id") in doomed))]
            for b in p.get("barras", []):
                b["arriba"] = [x for x in b["arriba"] if x not in doomed]
                b["abajo"] = [x for x in b["abajo"] if x not in doomed]
            huerfanas: dict[str, list[dict[str, Any]]] = {}
            for d in p.get("draftActions", []):  # una acción sin completar unida a una etapa borrada queda suelta
                if d.get("etapa") in doomed:
                    huerfanas.setdefault(d.pop("etapa"), []).append(d)
            for d in p.get("draftActions", []):  # una orden sin completar pierde el destino y las etapas que se borran
                if d.get("destino") in doomed:
                    d.pop("destino", None)
                    d.pop("etapas", None)  # (eran etapas del destino que ya no está)
                elif d.get("etapas"):
                    quedan = [i for i in d["etapas"] if i not in doomed]
                    if quedan:
                        d["etapas"] = quedan
                    else:
                        d.pop("etapas")
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
        """Instantánea de la selección y su contenido propio; los enlaces de frontera se descartan."""
        m, p = self.model, self.presentation
        chosen = set(ids)
        while True:
            before = set(chosen)
            for coll in ("steps", "transitions"):
                chosen.update(x["id"] for x in m[coll] if x["partialRef"] in chosen)
            for x in m["hierarchy"]["macros"]:
                if x["partialRef"] in chosen:
                    chosen.add(x["id"])
                if x["id"] in chosen:
                    chosen.add(x["expansionRef"])
            for x in m["hierarchy"]["expansions"]:
                if x["id"] in chosen:
                    chosen.add(x["partialRef"])
            for x in m["hierarchy"]["enclosures"]:
                if x["ownerStepRef"] in chosen:
                    chosen.update((x["id"], x["partialRef"]))
                elif x["id"] in chosen:
                    chosen.add(x["partialRef"])
            chosen.update(n["id"] for n in self.annotations() if n.get("partialRef") in chosen)
            if chosen == before:
                break
        for st in m["steps"]:
            if st["id"] in chosen:
                chosen.update(st["actionRefs"])
        full_nodes = {x["id"] for c in ("steps", "transitions") for x in m[c] if x["partialRef"] in chosen}
        full_nodes.update(x["id"] for x in m["hierarchy"]["macros"] if x["partialRef"] in chosen)
        chosen.update(b["id"] for b in self.bars() if b["arriba"] + b["abajo"]
                      and set(b["arriba"] + b["abajo"]) <= full_nodes)
        chosen.update(f["id"] for f in m["forces"] if f["sourceStepRef"] in chosen)
        chosen.update(d["id"] for d in self.draft_actions() if d.get("etapa") in chosen)
        entities = {c: [copy.deepcopy(x) for x in m.get(c, []) if x["id"] in chosen]
                    for c in ("partials", "steps", "transitions", "actions", "forces")}
        for c in ("macros", "expansions", "enclosures"):
            entities[c] = [copy.deepcopy(x) for x in m["hierarchy"][c] if x["id"] in chosen]
        # Un marco copiado sin su dueño pasa a ser un parcial independiente.
        entities["expansions"] = [x for x in entities["expansions"] if x["ownerMacroRef"] in chosen]
        entities["enclosures"] = [x for x in entities["enclosures"] if x["ownerStepRef"] in chosen]
        owned_partials = {x["partialRef"] for c in ("expansions", "enclosures") for x in entities[c]}
        for pt in entities["partials"]:
            for k in ("stepRefs", "transitionRefs"):
                pt[k] = [i for i in pt[k] if i in chosen]
            if pt.get("ownerRef") not in chosen and pt["id"] not in owned_partials:
                pt.pop("ownerRef", None)
        for t in entities["transitions"]:
            for k in ("preRefs", "postRefs"):
                t[k] = [i for i in t[k] if i in chosen]
        owned_special = {x[k] for x in entities["expansions"] for k in ("entryRef", "exitRef")}
        for st in entities["steps"]:
            if st["kind"] in ("entry", "exit") and st["id"] not in owned_special:
                st["kind"] = "ordinary"
        expr_ids = {t["conditionRef"] for t in entities["transitions"]}
        for act in entities["actions"]:
            expr_ids.update((act.get("conditionRef"), act.get("valueRef"), (act.get("trigger") or {}).get("expressionRef")))
        entities["expressions"] = [copy.deepcopy(x) for x in m["expressions"] if x["id"] in expr_ids]
        entities["draftLinks"] = [copy.deepcopy(d) for d in m.get("draftLinks", [])
                                  if d["fromRef"] in chosen and d["toRef"] in chosen]
        chosen.update(x["id"] for x in entities["expressions"] + entities["draftLinks"])
        draft_meanings = {}
        view = {"barras": [copy.deepcopy(b) for b in self.bars() if b["id"] in chosen],
                "draftActions": [copy.deepcopy(d) for d in self.draft_actions() if d["id"] in chosen]}
        for b in view["barras"]:
            for k in ("arriba", "abajo"):
                b[k] = [i for i in b[k] if i in chosen]
        def text(eid: str | None) -> str:
            return next((x["text"] for x in m["expressions"] if x["id"] == eid), "")
        # Una acción u orden copiada sola queda suelta en el destino, con sus datos intactos.
        for act in list(entities["actions"]):
            if act["stepRef"] not in chosen:
                trigger = act.get("trigger", {})
                condition = text(act.get("conditionRef"))
                tipo = "condicionada" if condition and condition not in ("true", "1") else "continua"
                if act["mode"] != "continuous":
                    tipo = {"activation": "activacion", "deactivation": "desactivacion", "event": "evento"}[trigger["kind"]]
                draft = {"id": act["id"], "x": "0", "y": "0", "tipo": tipo, "variable": act["targetRef"],
                         "condicion": condition, "valor": text(act.get("valueRef")),
                         "evento": text(trigger.get("expressionRef"))}
                if "limitUs" in act:
                    draft.update(tipo="limitada", limite=f"{act['limitUs']}us")
                view["draftActions"].append(draft)
                entities["actions"].remove(act)
        for f in list(entities["forces"]):
            if f["sourceStepRef"] not in chosen:
                view["draftActions"].append({"id": f["id"], "x": "0", "y": "0", "tipo": "forzado",
                    "destino": f["targetPartialRef"], "forma": f["targetKind"], "etapas": f.get("targetSteps", [])})
                entities["forces"].remove(f)
        for d in view["draftActions"]:
            if d.get("etapa") not in chosen:
                d.pop("etapa", None)
        view["actionLayouts"] = {k: v for k, v in self.action_layouts().items()
                                 if k in chosen or any(d.get("grupo") == k for d in view["draftActions"])}
        view["notes"] = [copy.deepcopy(n) for n in p.get("notes", []) if n.get("elementRef") in chosen or n.get("id") in chosen]
        view["linkStyles"] = {k: copy.deepcopy(v) for k, v in self.link_styles().items()
                              if all(i in chosen for i in k.split("|")[:2])}
        layouts = [copy.deepcopy(l) for l in p["elementLayouts"] if l["elementRef"] in chosen]
        refs = set()
        for e in entities["expressions"]:
            refs.update(e.get("bindings", {}).values())
        for act in entities["actions"]:
            refs.add(act["targetRef"])
        for f in entities["forces"]:
            refs.add(f["targetPartialRef"])
            refs.update(f.get("targetSteps", []))
        for d in view["draftActions"]:
            refs.update(i for i in (d.get("variable"), d.get("destino")) if i)
            refs.update(d.get("etapas", []))
            # Los textos de un borrador pueden usar otras variables además de la asignada.
            from .notation import a_nucleo
            resolve, found = ex.recording_resolver(self._lookup(m, next((st["partialRef"] for st in m["steps"]
                                                                       if st["id"] == d.get("etapa")), None)))
            for k in ("condicion", "valor", "evento"):
                try:
                    draft_meanings.setdefault(d["id"], {})[k] = ex.parse(a_nucleo(d.get(k, "")), resolve)
                except (ex.ParseError, ex.Unresolved):
                    pass
            refs.update(found.values())
        view["draftMeanings"] = draft_meanings
        index = self._index(m)
        external = {i: index[i][0] for i in refs - chosen if i in index}
        return Fragment(entities, layouts, external, view, {i: copy.deepcopy(index[i]) for i in external}, list(ids))

    def plan_paste(self, frag: Fragment) -> dict[str, str]:
        """Referencias externas que requieren decisión explícita antes de confirmar."""
        return dict(sorted(frag.external_refs.items()))

    @staticmethod
    def _paste_label(label: str, used: set[str]) -> str:
        if label_key(label) not in used:
            used.add(label_key(label))
            return label
        match = re.fullmatch(r"(.*?)([0-9]+)", label)
        prefix = match[1] if match else label
        n = max((int(x) for x in used if x.isdecimal()), default=-1) + 1 if label.isdecimal() else 1
        while label_key(f"{prefix}{n}") in used:
            n += 1
        result = f"{prefix}{n}"
        used.add(label_key(result))
        return result

    def paste(self, frag: Fragment, partial: str, decisions: dict[str, str] | None = None,
              at: tuple[Any, Any] | None = None) -> dict[str, str]:
        """Pega con identidades nuevas en una transacción. Sin decisiones, enlaza referencias por nombre."""
        self._find(self.model["partials"], partial, "el parcial")
        external_map: dict[str, str] = {}
        if decisions is None:
            index = self._index(self.model)
            missing = []
            for ident, coll in frag.external_refs.items():
                original = frag.references.get(ident, (coll, {}))[1]
                key = "name" if coll == "variables" else "label"
                name = original.get(key, ident)
                candidates = [(i, x) for i, (c, x) in index.items() if c == coll and x.get(key) == name]
                local = [(i, x) for i, x in candidates if x.get("scopeRef", x.get("partialRef")) in (partial, self.model["id"])]
                candidates = local or candidates
                if ident in index and index[ident][0] == coll and index[ident][1].get(key) == name:
                    candidates = [(ident, index[ident][1])]
                if len(candidates) != 1:
                    missing.append(name)
                else:
                    external_map[ident] = candidates[0][0]
                    if coll == "variables" and any(candidates[0][1].get(k) != original.get(k) for k in ("role", "type")):
                        raise DiagnosticError(Diagnostic("D-REF", f"variable incompatible: {name}"))
            if missing:
                raise DiagnosticError(Diagnostic("D-REF", "Faltan referencias o variables en el proyecto: " + ", ".join(sorted(set(missing)))))
        else:
            missing = set(frag.external_refs) - set(decisions)
            if missing:
                raise DiagnosticError(Diagnostic("D-REF", f"falta decidir las referencias externas {sorted(missing)}"))
            for ident, choice in decisions.items():
                if choice not in ("keep", "pending"):
                    raise DiagnosticError(Diagnostic("D-FORMATO", f"decisión desconocida {choice!r}"))
                external_map[ident] = f"pendiente.{ident}" if choice == "pending" else ident

        def fn(m: dict[str, Any], p: dict[str, Any]) -> dict[str, str]:
            before = self._estructurales(m) if decisions is None else []
            existing = set(self._index(m)) | {b["id"] for b in p.get("barras", [])} | {d["id"] for d in p.get("draftActions", [])}
            existing.update(n["id"] for n in p.get("notes", []) if "id" in n)
            mapping = {}
            groups = {d["grupo"] for d in frag.presentation.get("draftActions", []) if d.get("grupo")}
            copied_ids = {x["id"] for items in frag.entities.values() for x in items}
            copied_ids |= {x["id"] for k in ("barras", "draftActions", "notes") for x in frag.presentation.get(k, []) if "id" in x} | groups
            for ident in sorted(copied_ids):
                new = self.ids.new("c")
                while new in existing:
                    new = self.ids.new("c")
                mapping[ident] = new
                existing.add(new)
            def mp(ident: str) -> str:
                return mapping.get(ident, external_map.get(ident, ident))
            positions = [(Fraction(str(x["x"])), Fraction(str(x["y"]))) for x in frag.layouts]
            positions += [(Fraction(str(x["x"])), Fraction(str(x["y"])))
                          for k in ("barras", "draftActions") for x in frag.presentation.get(k, []) if not x.get("etapa")]
            positions += [(Fraction(str(n["x"])),Fraction(str(n["y"]))) for n in frag.presentation.get("notes",[]) if n.get("kind") in ("text","image")]
            dx = Fraction(str(at[0])) - min(x for x, y in positions) if at is not None and positions else Fraction(0)
            dy = Fraction(str(at[1])) - min(y for x, y in positions) if at is not None and positions else Fraction(0)
            refkeys = {"ownerRef", "partialRef", "stepRef", "targetRef", "conditionRef", "valueRef", "expansionRef",
                       "ownerMacroRef", "entryRef", "exitRef", "ownerStepRef", "sourceStepRef", "targetPartialRef",
                       "fromRef", "toRef", "elementRef", "variable", "etapa", "grupo", "destino"}
            listkeys = {"stepRefs", "transitionRefs", "actionRefs", "preRefs", "postRefs", "activationRefs", "targetSteps",
                        "arriba", "abajo", "etapas"}
            used = {coll: {label_key(x["label"]) for x in (m[coll] if coll in m else m["hierarchy"][coll]) if x.get("label")}
                    for coll in ("steps", "transitions", "partials", "macros")}
            added: dict[str, list[dict[str, Any]]] = {}
            def remap(item: dict[str, Any]) -> dict[str, Any]:
                new = copy.deepcopy(item)
                if "id" in new:
                    new["id"] = mp(new["id"])
                for k in refkeys & new.keys():
                    new[k] = mp(new[k])
                for k in listkeys & new.keys():
                    new[k] = [mp(i) for i in new[k]]
                return new
            for coll, items in frag.entities.items():
                added[coll] = []
                for item in items:
                    new = remap(item)
                    if coll in ("steps", "transitions", "macros") and item.get("partialRef") not in mapping:
                        new["partialRef"] = partial
                    if coll == "partials" and item.get("ownerRef") not in mapping:
                        owned = any(x["partialRef"] == item["id"] for c in ("expansions", "enclosures") for x in frag.entities.get(c, []))
                        if owned:
                            new["ownerRef"] = partial
                        else:
                            new.pop("ownerRef", None)
                    if coll in used and new.get("label"):
                        new["label"] = self._paste_label(new["label"], used[coll])
                    if "trigger" in new and "expressionRef" in new["trigger"]:
                        new["trigger"]["expressionRef"] = mp(new["trigger"]["expressionRef"])
                    if coll == "expressions" and new["mode"] == "executable":
                        new["bindings"] = {k: mp(i) for k, i in new["bindings"].items()}
                        new["meaning"] = _remap_meaning(new["meaning"], mp)
                    (m[coll] if coll in m else m["hierarchy"][coll]).append(new)
                    added[coll].append(new)
            for coll, fieldname in (("steps", "stepRefs"), ("transitions", "transitionRefs")):
                for item in added.get(coll, []):
                    pt = next(x for x in m["partials"] if x["id"] == item["partialRef"])
                    if item["id"] not in pt[fieldname]:
                        pt[fieldname].append(item["id"])
            for act in added.get("actions", []):
                step = next(x for x in m["steps"] if x["id"] == act["stepRef"])
                if act["id"] not in step["actionRefs"]:
                    step["actionRefs"].append(act["id"])
            names = self._render_names(m)
            for expr in added.get("expressions", []):
                if expr["mode"] == "executable" and all(i in self._index(m) for i in expr["bindings"].values()):
                    found = {}
                    def record(i: str) -> str:
                        name = names(i)
                        found[name] = i
                        return name
                    expr["text"] = ex.render(expr["meaning"], record)
                    expr["bindings"] = found
            for item in frag.layouts:
                new = remap(item)
                new["x"], new["y"] = _coord(Fraction(str(new["x"])) + dx), _coord(Fraction(str(new["y"])) + dy)
                new["viewRef"] = p["views"][0]["id"]
                p["elementLayouts"].append(new)
            for k in ("barras", "draftActions", "notes"):
                for item in frag.presentation.get(k, []):
                    new = remap(item)
                    if k in ("barras", "draftActions") or k == "notes" and new.get("kind") in ("text","image"):
                        new["x"], new["y"] = _coord(Fraction(str(new["x"])) + dx), _coord(Fraction(str(new["y"])) + dy)
                    if k == "notes" and new.get("kind") in ("text","image") and item.get("partialRef") not in mapping:
                        new["partialRef"] = partial
                    if k == "draftActions":
                        for fieldname, meaning in frag.presentation.get("draftMeanings", {}).get(item["id"], {}).items():
                            new[fieldname] = ex.render(_remap_meaning(meaning, mp), names)
                    p.setdefault(k, []).append(new)
            for k in ("actionLayouts", "linkStyles"):
                for ident, value in frag.presentation.get(k, {}).items():
                    key = "|".join(mp(i) for i in ident.split("|")) if k == "linkStyles" else mp(ident)
                    value = copy.deepcopy(value)
                    if k == "linkStyles" and isinstance(value, dict):
                        route = value.get("route", {})
                        for f, delta in (("laneX", dx), ("middleY", dy), ("entryY", dy), ("exitY", dy)):
                            if f in route:
                                route[f] = _coord(Fraction(str(route[f])) + delta)
                    p.setdefault(k, {})[key] = value
            if decisions is None:
                self._sin_nuevos(m, before)
            return mapping
        return self._txn("pegar", fn, view_only=not any(frag.entities.values()))



def _techo(valor: Fraction, q: Fraction) -> Fraction:
    """El múltiplo de `q` igual o inmediatamente superior a `valor`."""
    return -((-valor) // q) * q


def _a_rejilla(valor: Fraction, q: Fraction) -> Fraction:
    """El múltiplo de `q` más cercano a `valor`."""
    return ((valor / q + Fraction(1, 2)) // 1) * q


def _niveles(nodos: list[str], aristas: list[tuple[str, str]], y: dict[str, Fraction], x: dict[str, Fraction],
             iniciales: set[str]) -> dict[str, int]:
    """Nivel (0, 1, 2…) de cada nodo de una cadena: el camino más largo desde los nodos que no reciben ningún enlace, sin
    contar los enlaces de realimentación. Es de realimentación el enlace que vuelve hacia arriba en el dibujo actual (como
    las flechas de retorno de `routing.enlaces`) y cierra un ciclo con los demás; un enlace que sube pero no cierra ninguno es
    un enlace mal dibujado y cuenta como descendente. Si entre los demás quedan ciclos (nodos a la misma altura), cierra
    cada uno el enlace que los vuelve a recorrer en una búsqueda en profundidad (se parte de los que no reciben nada,
    después de las etapas iniciales y de los más altos). Tras repartir por niveles todo enlace va hacia abajo salvo los de
    realimentación, que van hacia arriba: volver a repartir da lo mismo."""
    suben = {a for a in aristas if y[a[1]] < y[a[0]]}
    base = set(aristas) - suben
    suc: dict[str, list[str]] = {n: [] for n in nodos}
    recibe: dict[str, int] = {n: 0 for n in nodos}
    for a, b in sorted(base):
        suc[a].append(b)
        recibe[b] += 1
    estado: dict[str, int] = {}  # 1: en la pila de la búsqueda; 2: terminado
    cierran: set[tuple[str, str]] = set()
    for raiz in sorted(nodos, key=lambda n: (recibe[n] > 0, n not in iniciales, y[n], x[n], n)):
        if raiz in estado:
            continue
        estado[raiz] = 1
        pila = [(raiz, iter(suc[raiz]))]
        while pila:
            n, it = pila[-1]
            for hijo in it:
                if estado.get(hijo) == 1:
                    cierran.add((n, hijo))
                elif hijo not in estado:
                    estado[hijo] = 1
                    pila.append((hijo, iter(suc[hijo])))
                    break
            else:
                estado[n] = 2
                pila.pop()
    dag = base - cierran
    suc = {n: [] for n in nodos}
    for a, b in dag:
        suc[a].append(b)

    def alcanza(origen: str, destino: str) -> bool:
        vistos, pendientes = {origen}, [origen]
        while pendientes:
            n = pendientes.pop()
            if n == destino:
                return True
            for hijo in suc[n]:
                if hijo not in vistos:
                    vistos.add(hijo)
                    pendientes.append(hijo)
        return False
    for a, b in sorted(suben):
        if not alcanza(b, a):  # no cierra ningún ciclo: no es de realimentación
            dag.add((a, b))
            suc[a].append(b)
    nivel = {n: 0 for n in nodos}
    faltan = {n: 0 for n in nodos}
    for a, b in dag:
        faltan[b] += 1
    listos = sorted(n for n in nodos if not faltan[n])
    while listos:
        n = listos.pop()
        for b in suc[n]:
            nivel[b] = max(nivel[b], nivel[n] + 1)
            faltan[b] -= 1
            if not faltan[b]:
                listos.append(b)
    return nivel


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
