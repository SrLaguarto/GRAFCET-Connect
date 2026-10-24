"""Operaciones de edición sin interfaz (documento 07; REQ-EDT-01..07, 09, 14; REQ-MOD-03, REQ-MOD-06).

Cada operación es una transacción: se aplica completa o no se aplica; una operación
fallida no entra en el historial; una edición nueva descarta la rama de rehacer
(REQ-EDT-05). Las operaciones de vista solo cambian el documento de presentación y no
cambian la revisión semántica (REQ-EDT-03, REQ-EDT-14). Conectar exige una relación
explícita: cruzar líneas nunca conecta (REQ-MOD-03).
"""
from __future__ import annotations

import copy
from fractions import Fraction
from dataclasses import dataclass, field
from typing import Any, Callable

from . import expressions as ex
from .diagnostics import Diagnostic, DiagnosticError
from .ids import IdGenerator, label_key, valid_label
from .model import ValidationResult, compute_revision, validate_model
from .profile import FORMAT_VERSION
from .values import TypeSpec, format_value, parse_type, zero


def new_model_document(model_id: str) -> dict[str, Any]:
    return {"family": "model", "formatVersion": FORMAT_VERSION, "id": model_id, "revisionId": "",
            "partials": [], "steps": [], "transitions": [], "variables": [], "expressions": [], "actions": [],
            "forces": [], "hierarchy": {"macros": [], "expansions": [], "enclosures": []}, "draftLinks": []}


def new_presentation(model_id: str) -> dict[str, Any]:
    return {"family": "presentation", "formatVersion": FORMAT_VERSION, "id": f"{model_id}.vista", "modelId": model_id,
            "views": [{"id": f"{model_id}.vista.principal", "label": "principal"}], "elementLayouts": [], "notes": []}


def _coord(v: Any) -> str:
    return format_value(TypeSpec("decimal", 3), Fraction(str(v)))


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
                       at: tuple[Any, Any] | None = None) -> tuple[str, Diagnostic | None]:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> tuple[str, Diagnostic | None]:
            tid = self.ids.new("t")
            expr, diag = self._make_expr(m, condition, partial)
            m["expressions"].append(expr)
            m["transitions"].append({"id": tid, "partialRef": partial, "preRefs": list(pre), "postRefs": list(post),
                                     "conditionRef": expr["id"]})
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

    # -- conexión explícita (REQ-MOD-02, REQ-MOD-03; P-IMP-05)
    def connect(self, src: str, dst: str) -> Diagnostic | None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> Diagnostic | None:
            idx = self._index(m)
            ks, kd = idx[src][0], idx[dst][0]
            if ks == "steps" and kd == "transitions":
                refs = idx[dst][1]["preRefs"]
                item = src
            elif ks == "transitions" and kd == "steps":
                refs = idx[src][1]["postRefs"]
                item = dst
            else:
                did = self.ids.new("l")
                m["draftLinks"].append({"id": did, "fromRef": src, "toRef": dst})
                return Diagnostic("D-ALTERNANCIA", f"{src}→{dst} une dos elementos del mismo tipo; se guarda como "
                                  "borrador no ejecutable", element=did)
            if item in refs:
                raise DiagnosticError(Diagnostic("D-FORMATO", "enlace duplicado entre los mismos extremos", element=dst))
            refs.append(item)
            return None
        return self._txn("conectar", fn)

    # -- vista (solo presentación)
    def move(self, ident: str, x: Any, y: Any) -> None:
        def fn(m: dict[str, Any], p: dict[str, Any]) -> None:
            lay = next((l for l in p["elementLayouts"] if l["elementRef"] == ident), None)
            if lay is None:
                self._layout(p, ident, (x, y))
            else:
                lay["x"], lay["y"] = _coord(x), _coord(y)
        self._txn("mover", fn, view_only=True)

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
            if not keep_dangling:
                for t in m["transitions"]:
                    t["preRefs"] = [s for s in t["preRefs"] if s not in doomed]
                    t["postRefs"] = [s for s in t["postRefs"] if s not in doomed]
            used = {t["conditionRef"] for t in m["transitions"]}
            for a in m["actions"]:
                used |= {a.get("conditionRef"), a.get("valueRef"), (a.get("trigger") or {}).get("expressionRef")}
            m["expressions"] = [e for e in m["expressions"] if e["id"] in used]
            p["elementLayouts"] = [l for l in p["elementLayouts"] if l["elementRef"] not in doomed]
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
