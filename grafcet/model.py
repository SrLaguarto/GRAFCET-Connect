"""Modelo GRAFCET: validación estructural y compilación (documentos 03, 05, 06, 09).

La validación no modifica el documento ni completa huecos por defecto (documento 10).
Devuelve diagnósticos localizados, las capacidades que el modelo necesita y, si la
estructura lo permite, un modelo compilado inmutable para el motor.
Requisitos: REQ-MOD-01..07, REQ-EXP-01, REQ-ACT-04, REQ-JER-03, REQ-DAT-01, REQ-DAT-08.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import expressions as ex
from .canonical import digest
from .diagnostics import Diagnostic, DiagnosticError, has_blocking
from .ids import label_key, valid_id, valid_label
from .profile import blocked, normalize_options, unsupported
from .timeutil import parse_time_field
from .values import TypeSpec, Value, in_domain, parse_type, parse_value, zero

LIMITS = {"steps": 5000, "transitions": 5000, "actions": 10000, "variables": 10000,
          "partials": 1000, "hierarchyDepth": 32, "exprDepth": 64, "exprNodes": 100000}

FIELDS = {
    "model": ({"family", "formatVersion", "id", "revisionId", "partials", "steps", "transitions", "variables",
               "expressions", "actions", "forces", "hierarchy"}, {"draftLinks", "extensions", "minorAddsSemantics"}),
    "partial": ({"id", "label", "stepRefs", "transitionRefs"}, {"ownerRef"}),
    "step": ({"id", "label", "partialRef", "kind", "initial", "actionRefs"}, set()),
    "transition": ({"id", "partialRef", "preRefs", "postRefs", "conditionRef"}, {"label"}),
    "variable": ({"id", "name", "scopeRef", "role", "type", "unit", "domain", "initialValue"}, set()),
    "expression": ({"id", "mode", "text", "bindings"}, {"meaning", "resultType"}),
    "action-continuous": ({"id", "stepRef", "mode", "targetRef", "conditionRef"}, {"limitUs"}),
    "action-stored": ({"id", "stepRef", "mode", "targetRef", "trigger", "valueRef"}, set()),
    "trigger": ({"kind", "sourceRefs"}, {"expressionRef"}),
    "force": ({"id", "sourceStepRef", "targetPartialRef", "targetKind"}, {"targetSteps"}),
    "macro": ({"id", "label", "partialRef", "expansionRef"}, set()),
    "expansion": ({"id", "ownerMacroRef", "partialRef", "entryRef", "exitRef"}, set()),
    "enclosure": ({"id", "ownerStepRef", "partialRef", "activationRefs"}, set()),
    "hierarchy": ({"macros", "expansions", "enclosures"}, set()),
    "draftLink": ({"id", "fromRef", "toRef"}, set()),
}
STEP_KINDS = {"ordinary", "enclosing", "entry", "exit"}
ROLES = {"input", "internal", "output"}


# --- Estructuras compiladas ----------------------------------------------------------

@dataclass(frozen=True)
class Step:
    id: str
    label: str
    partial: str
    kind: str
    initial: bool


@dataclass(frozen=True)
class Transition:
    id: str
    partial: str
    pre: frozenset[str]
    post: frozenset[str]
    cond: str


@dataclass(frozen=True)
class Variable:
    id: str
    name: str
    scope: str
    role: str
    type: TypeSpec
    unit: str
    domain: dict[str, Any]
    initial: Value


@dataclass
class Expr:
    id: str
    node: ex.Node
    info: ex.TypeInfo
    support: ex.Support


@dataclass(frozen=True)
class Action:
    id: str
    step: str
    mode: str  # continuous | stored
    target: str
    cond: str | None = None
    limit_us: int | None = None
    trigger: str | None = None  # activation | deactivation | event
    trigger_expr: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class TemporalSpec:
    key: str
    expr: str
    d1: int
    d2: int
    base: ex.Node
    base_kind: str  # inputs | active
    base_step: str | None


@dataclass
class CompiledModel:
    id: str
    revision: str
    steps: dict[str, Step]
    transitions: dict[str, Transition]
    variables: dict[str, Variable]
    exprs: dict[str, Expr]
    actions: dict[str, Action]
    partials: dict[str, dict[str, Any]]
    has_hierarchy: bool
    inputs: frozenset[str] = frozenset()
    continuous_by_target: dict[str, list[Action]] = field(default_factory=dict)
    stored_by_step: dict[tuple[str, str], list[Action]] = field(default_factory=dict)
    event_actions: list[Action] = field(default_factory=list)
    temporals: dict[str, TemporalSpec] = field(default_factory=dict)
    step_dependents: dict[str, set[str]] = field(default_factory=dict)

    def initial_situation(self) -> frozenset[str]:
        return frozenset(s.id for s in self.steps.values() if s.initial)

    def stored_vars(self) -> list[Variable]:
        targets = {a.target for a in self.actions.values() if a.mode == "stored"}
        return [v for v in self.variables.values() if v.role != "input" and v.id in targets]


@dataclass
class ValidationResult:
    diagnostics: list[Diagnostic]
    model: CompiledModel | None
    capabilities: set[str]

    @property
    def can_simulate(self) -> bool:
        return self.model is not None and not has_blocking(self.diagnostics)


# --- Proyección semántica y revisión (documento 09; H-13, P-IMP-04, P-IMP-07) --------

def semantic_projection(doc: dict[str, Any]) -> dict[str, Any]:
    def by_id(items: list[dict[str, Any]], drop: set[str], set_fields: set[str]) -> list[dict[str, Any]]:
        out = []
        for it in sorted((i for i in items if isinstance(i, dict)), key=lambda i: str(i.get("id"))):
            d = {k: (sorted(v) if k in set_fields and isinstance(v, list) else v)
                 for k, v in it.items() if k not in drop}
            out.append(d)
        return out
    exprs = []
    for e in sorted((i for i in doc.get("expressions", []) if isinstance(i, dict)), key=lambda i: str(i.get("id"))):
        if e.get("mode") == "executable":
            exprs.append({"id": e.get("id"), "mode": "executable", "meaning": e.get("meaning"),
                          "boundIds": sorted(set((e.get("bindings") or {}).values()))})
        else:
            exprs.append({"id": e.get("id"), "mode": e.get("mode"), "text": e.get("text")})
    h = doc.get("hierarchy") or {}
    proj = {
        "id": doc.get("id"),
        "partials": by_id(doc.get("partials", []), {"label"}, {"stepRefs", "transitionRefs"}),
        "steps": by_id(doc.get("steps", []), {"label"}, {"actionRefs"}),
        "transitions": by_id(doc.get("transitions", []), {"label"}, {"preRefs", "postRefs"}),
        "variables": by_id(doc.get("variables", []), {"name"}, set()),
        "expressions": exprs,
        "actions": by_id(doc.get("actions", []), set(), set()),
        "forces": by_id(doc.get("forces", []), set(), {"targetSteps"}),
        "macros": by_id(h.get("macros", []), {"label"}, set()),
        "expansions": by_id(h.get("expansions", []), set(), set()),
        "enclosures": by_id(h.get("enclosures", []), set(), {"activationRefs"}),
        "draftLinks": by_id(doc.get("draftLinks", []), set(), set()),
    }
    known = FIELDS["model"][0] | FIELDS["model"][1]
    unknown = {k: v for k, v in doc.items() if k not in known}
    if unknown:
        proj["unknown"] = unknown
    ext = {k: v for k, v in (doc.get("extensions") or {}).items()
           if not (isinstance(v, dict) and v.get("affectsSemantics") is False)}
    if ext:
        proj["semanticExtensions"] = ext
    return proj


def compute_revision(doc: dict[str, Any]) -> str:
    return "rev-" + digest(semantic_projection(doc))[:24]


def unknown_fields(doc: dict[str, Any]) -> list[str]:
    """Rutas de campos no reconocidos en un modelo (se conservan; bloquean simulación y sobrescritura)."""
    out = [k for k in doc if k not in FIELDS["model"][0] | FIELDS["model"][1]]
    plan = [("partials", "partial"), ("steps", "step"), ("transitions", "transition"), ("variables", "variable"),
            ("expressions", "expression"), ("forces", "force")]
    for coll, kind in plan:
        for it in doc.get(coll, []) if isinstance(doc.get(coll), list) else []:
            if isinstance(it, dict):
                known = FIELDS[kind][0] | FIELDS[kind][1]
                out += [f"{coll}.{it.get('id')}.{k}" for k in it if k not in known]
    for it in doc.get("actions", []) if isinstance(doc.get("actions"), list) else []:
        if isinstance(it, dict):
            kind = "action-stored" if it.get("mode") == "stored" else "action-continuous"
            out += [f"actions.{it.get('id')}.{k}" for k in it if k not in FIELDS[kind][0] | FIELDS[kind][1]]
    return out


# --- Validación ----------------------------------------------------------------------

class _V:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.d: list[Diagnostic] = []
        self.caps: set[str] = set()
        self.ids: dict[str, str] = {}  # id -> clase

    def add(self, code: str, msg: str, element: str | None = None, fld: str | None = None, **ev: Any) -> None:
        self.d.append(Diagnostic(code, msg, element=element, field=fld, evidence={k: str(v) for k, v in ev.items()}))

    def fields(self, kind: str, item: Any, where: str) -> bool:
        if not isinstance(item, dict):
            self.add("D-FORMATO", f"{kind} no es un objeto", where)
            return False
        req, opt = FIELDS[kind]
        missing = req - set(item)
        if missing:
            self.add("D-FORMATO", f"campos obligatorios ausentes en {kind}: {sorted(missing)}",
                     item.get("id") if isinstance(item.get("id"), str) else where)
            return False
        unknown = set(item) - req - opt
        if unknown:
            self.d.append(Diagnostic("D-FORMATO", f"campos desconocidos en {kind}: {sorted(unknown)}; se conservan y "
                                     "bloquean la simulación", element=item.get("id"), severity="bloqueo"))
        return True

    def register(self, ident: Any, kind: str) -> bool:
        if not valid_id(ident):
            self.add("D-ID", f"ID inválido para {kind}: {ident!r} (ASCII 1..128: letras, dígitos, . _ -)")
            return False
        if ident in self.ids:
            self.add("D-ID", f"identidad duplicada: {ident} ({self.ids[ident]} y {kind})", ident)
            return False
        self.ids[ident] = kind
        return True

    def ref_set(self, values: Any, where: str, fld: str) -> list[str]:
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            self.add("D-FORMATO", f"{fld} debe ser una lista de IDs", where, fld)
            return []
        if len(set(values)) != len(values):
            self.add("D-FORMATO", f"{fld} contiene duplicados (un enlace duplicado es error de datos)", where, fld)
        return list(dict.fromkeys(values))


def _cycle(graph: dict[str, set[str]]) -> list[str] | None:
    color: dict[str, int] = {}
    stack: list[str] = []

    def dfs(n: str) -> list[str] | None:
        color[n] = 1
        stack.append(n)
        for m in sorted(graph.get(n, ())):
            if color.get(m) == 1:
                return stack[stack.index(m):] + [m]
            if color.get(m) is None:
                found = dfs(m)
                if found:
                    return found
        stack.pop()
        color[n] = 2
        return None
    for n in sorted(graph):
        if color.get(n) is None:
            found = dfs(n)
            if found:
                return found
    return None


def validate_model(doc: dict[str, Any], options: dict[str, str] | None = None) -> ValidationResult:
    """Valida el documento con las lecturas elegidas (P-IMP-21): una alternativa puede hacer que un caso no
    compile, se permita o siga detenido."""
    opt = normalize_options(options)
    v = _V(doc)
    if not v.fields("model", doc, "modelo"):
        return ValidationResult(v.d, None, v.caps)
    model_id = doc["id"]
    if not valid_id(model_id):
        v.add("D-ID", f"ID de modelo inválido: {model_id!r}")
    for coll in ("partials", "steps", "transitions", "variables", "expressions", "actions", "forces"):
        if not isinstance(doc[coll], list):
            v.add("D-FORMATO", f"{coll} debe ser una lista")
            return ValidationResult(v.d, None, v.caps)
    hier = doc["hierarchy"]
    if not v.fields("hierarchy", hier, "hierarchy"):
        return ValidationResult(v.d, None, v.caps)
    for lim_key, coll in (("steps", doc["steps"]), ("transitions", doc["transitions"]),
                          ("actions", doc["actions"]), ("variables", doc["variables"]), ("partials", doc["partials"])):
        if len(coll) > LIMITS[lim_key]:
            v.add("D-LIM-DATOS", f"{lim_key}: {len(coll)} supera el límite declarado {LIMITS[lim_key]}")
    if any(x.code == "D-LIM-DATOS" for x in v.d):
        return ValidationResult(v.d, None, v.caps)

    # Identidades y campos obligatorios
    partials: dict[str, dict[str, Any]] = {}
    for p in doc["partials"]:
        if v.fields("partial", p, "parcial") and v.register(p["id"], "parcial"):
            partials[p["id"]] = p
    raw_steps: dict[str, dict[str, Any]] = {}
    for s in doc["steps"]:
        if v.fields("step", s, "etapa") and v.register(s["id"], "etapa"):
            raw_steps[s["id"]] = s
    raw_trans: dict[str, dict[str, Any]] = {}
    for t in doc["transitions"]:
        if v.fields("transition", t, "transición") and v.register(t["id"], "transición"):
            raw_trans[t["id"]] = t
    raw_vars: dict[str, dict[str, Any]] = {}
    for x in doc["variables"]:
        if v.fields("variable", x, "variable") and v.register(x["id"], "variable"):
            raw_vars[x["id"]] = x
    raw_exprs: dict[str, dict[str, Any]] = {}
    for e in doc["expressions"]:
        if v.fields("expression", e, "expresión") and v.register(e["id"], "expresión"):
            raw_exprs[e["id"]] = e
    raw_actions: dict[str, dict[str, Any]] = {}
    for a in doc["actions"]:
        kind = "action-stored" if isinstance(a, dict) and a.get("mode") == "stored" else "action-continuous"
        if isinstance(a, dict) and a.get("mode") not in ("stored", "continuous"):
            v.add("D-FORMATO", f"modo de acción desconocido: {a.get('mode')!r}", a.get("id"))
            continue
        if v.fields(kind, a, "acción") and v.register(a["id"], "acción"):
            raw_actions[a["id"]] = a
    forces = [f for f in doc["forces"] if v.fields("force", f, "forzado") and v.register(f["id"], "forzado")]
    macros = [m for m in hier["macros"] if v.fields("macro", m, "macroetapa") and v.register(m["id"], "macroetapa")]
    expansions = [x for x in hier["expansions"] if v.fields("expansion", x, "expansión") and v.register(x["id"], "expansión")]
    enclosures = [x for x in hier["enclosures"] if v.fields("enclosure", x, "recinto") and v.register(x["id"], "recinto")]
    drafts = [x for x in doc.get("draftLinks", []) if v.fields("draftLink", x, "enlace borrador") and v.register(x["id"], "enlace")]
    macro_ids = {m["id"] for m in macros}

    # Parciales: propiedad única y acíclica (REQ-MOD-01, REQ-JER-01)
    owner_graph: dict[str, set[str]] = {}
    for pid, p in partials.items():
        if not valid_label(p["label"]):
            v.add("D-FORMATO", "etiqueta de parcial inválida (Unicode 1..256)", pid, "label")
        if "ownerRef" in p:
            if p["ownerRef"] not in partials:
                v.add("D-REF", f"ownerRef inexistente: {p['ownerRef']}", pid, "ownerRef")
            else:
                owner_graph.setdefault(p["ownerRef"], set()).add(pid)
    cyc = _cycle(owner_graph)
    if cyc:
        v.add("D-JERARQUIA-CICLO", "ciclo en la propiedad de parciales", cyc[0], camino=" → ".join(cyc))
    children = {pid: owner_graph.get(pid, set()) for pid in partials}

    def check_membership(kind: str, items: dict[str, dict[str, Any]], list_field: str) -> None:
        for iid, it in items.items():
            pref = it["partialRef"]
            if pref not in partials:
                v.add("D-REF", f"partialRef inexistente: {pref}", iid, "partialRef")
        for pid, p in partials.items():
            listed = v.ref_set(p[list_field], pid, list_field)
            for iid in listed:
                if iid not in items:
                    v.add("D-REF", f"{list_field} referencia {kind} inexistente: {iid}", pid, list_field)
                elif items[iid]["partialRef"] != pid:
                    v.add("D-FORMATO", f"propietario contradictorio: {iid} figura en {pid} pero declara "
                          f"{items[iid]['partialRef']} (las referencias redundantes deben coincidir)", iid)
            for iid, it in items.items():
                if it["partialRef"] == pid and iid not in listed:
                    v.add("D-FORMATO", f"propietario contradictorio: {iid} declara {pid} pero no figura en {list_field}", iid)
    check_membership("etapa", raw_steps, "stepRefs")
    check_membership("transición", raw_trans, "transitionRefs")

    # Etapas
    labels_in_partial: dict[tuple[str, str], str] = {}
    for sid, s in raw_steps.items():
        if not valid_label(s["label"]):
            v.add("D-FORMATO", "etiqueta de etapa inválida (Unicode 1..256)", sid, "label")
        else:
            k = (s["partialRef"], label_key(s["label"]))
            if k in labels_in_partial:
                v.add("D-NOMBRE-COLISION", f"etiqueta «{s['label']}» repetida en el parcial {s['partialRef']}", sid,
                      otro=labels_in_partial[k])
            labels_in_partial[k] = sid
        if s["kind"] not in STEP_KINDS:
            v.add("D-FORMATO", f"kind de etapa desconocido: {s['kind']!r}", sid, "kind")
        if not isinstance(s["initial"], bool):
            v.add("D-FORMATO", "initial debe ser booleano", sid, "initial")
        for aref in v.ref_set(s["actionRefs"], sid, "actionRefs"):
            if aref not in raw_actions:
                v.add("D-REF", f"actionRefs referencia una acción inexistente: {aref}", sid, "actionRefs")
            elif raw_actions[aref]["stepRef"] != sid:
                v.add("D-FORMATO", f"propietario contradictorio: la acción {aref} declara otra etapa", aref)
    for aid, a in raw_actions.items():
        if a["stepRef"] in raw_steps and aid not in raw_steps[a["stepRef"]]["actionRefs"]:
            v.add("D-FORMATO", f"propietario contradictorio: la acción no figura en actionRefs de {a['stepRef']}", aid)

    # Variables (REQ-EXP-01; H-07)
    variables: dict[str, Variable] = {}
    names_in_scope: dict[tuple[str, str], str] = {}
    for vid, x in raw_vars.items():
        ok = True
        if not valid_label(x["name"]):
            v.add("D-FORMATO", "nombre de variable inválido", vid, "name")
            ok = False
        else:
            k = (x["scopeRef"], label_key(x["name"]))
            if k in names_in_scope:
                v.add("D-NOMBRE-COLISION", f"nombre «{x['name']}» repetido en el ámbito {x['scopeRef']}", vid,
                      otro=names_in_scope[k])
            names_in_scope[k] = vid
        if x["scopeRef"] != model_id and x["scopeRef"] not in partials:
            v.add("D-REF", f"scopeRef inexistente: {x['scopeRef']}", vid, "scopeRef")
        if x["role"] not in ROLES:
            v.add("D-FORMATO", f"rol desconocido: {x['role']!r}", vid, "role")
            ok = False
        if not isinstance(x["unit"], str) or not isinstance(x["domain"], dict):
            v.add("D-FORMATO", "unit debe ser texto y domain un objeto", vid)
            ok = False
        try:
            t = parse_type(x["type"])
            init = parse_value(t, x["initialValue"])
            if ok and not in_domain(t, x["domain"], init):
                v.add("D-NUM", "valor inicial fuera de dominio", vid, "initialValue")
            if ok:
                variables[vid] = Variable(vid, x["name"], x["scopeRef"], x["role"], t, x["unit"], x["domain"], init)
        except DiagnosticError as exc:
            for dg in exc.diagnostics:
                dg.element = vid
                v.d.append(dg)

    def var_type(vid: str) -> tuple[TypeSpec, str] | None:
        var = variables.get(vid)
        return (var.type, var.unit) if var else None

    # Expresiones: forma, divergencia texto-significado, profundidad (REQ-MOD-05, REQ-DAT-08)
    exprs: dict[str, Expr] = {}
    executable: dict[str, dict[str, Any]] = {}
    total_nodes = [0]
    for eid, e in raw_exprs.items():
        if e["mode"] not in ("executable", "descriptive"):
            v.add("D-FORMATO", f"mode de expresión desconocido: {e['mode']!r}", eid, "mode")
            continue
        if not isinstance(e["text"], str) or not isinstance(e["bindings"], dict):
            v.add("D-FORMATO", "text debe ser texto y bindings un objeto", eid)
            continue
        if e["mode"] == "descriptive":
            continue
        if "meaning" not in e:
            v.add("D-EXP-PENDIENTE", "expresión ejecutable sin significado", eid)
            continue
        try:
            ex.check_meaning_shape(e["meaning"], max_depth=LIMITS["exprDepth"], counter=total_nodes)
        except DiagnosticError as exc:
            for dg in exc.diagnostics:
                dg.element = eid
                v.d.append(dg)
            continue
        try:
            reparsed = ex.parse(e["text"], ex.bindings_resolver(e["bindings"]))
            if reparsed != e["meaning"]:
                v.add("D-EXP-DIVERGENTE", "el texto no produce el significado guardado; se conservan ambos", eid,
                      texto=e["text"])
        except (ex.ParseError, ex.Unresolved) as exc:
            v.add("D-EXP-DIVERGENTE", f"el texto no se puede analizar con sus vínculos: {exc}", eid, texto=e["text"])
        executable[eid] = e
    if total_nodes[0] > LIMITS["exprNodes"]:
        v.add("D-LIM-DATOS", f"{total_nodes[0]} nodos de expresión superan el límite {LIMITS['exprNodes']}")

    ctx = ex.CheckContext(var_type, lambda sid: sid in raw_steps, lambda pid: pid in partials,
                          lambda mid: mid in macro_ids)
    uses: dict[str, list[str]] = {}

    def use_expr(eid: str, user: str, role: str, target: Variable | None = None) -> Expr | None:
        uses.setdefault(eid, []).append(user)
        if eid not in raw_exprs:
            v.add("D-REF", f"expresión inexistente: {eid}", user)
            return None
        if raw_exprs[eid]["mode"] == "descriptive":
            v.add("D-EXP-PENDIENTE", f"texto sin significado ejecutable: «{raw_exprs[eid]['text']}»", user, expresion=eid)
            return None
        if eid not in executable:
            return None
        ctx.element, before = user, len(ctx.diags)
        info = ex.typecheck(executable[eid]["meaning"], ctx)
        if role in ("receptivity", "continuous", "trigger") and info.kind != "bool":
            ctx.err("D-TIPO", f"la expresión {eid} debe ser booleana")
        if role in ("continuous", "value") and info.event:
            ctx.err("D-TIPO-EVENTO", f"un evento no puede usarse como condición continua o valor ({eid})")
        if role == "trigger" and not ex.is_event_positive(executable[eid]["meaning"]):
            ctx.err("D-TIPO-EVENTO", f"el disparador {eid} debe ser un evento (falso sin eventos)")
        if role == "value" and target is not None:
            if not ex.assignable(target.type, info):
                ctx.err("D-TIPO", f"el valor {eid} no es asignable a {target.id} ({target.type.kind})")
            if info.unit and target.unit and info.unit != target.unit:
                ctx.err("D-UNIDAD", f"unidad {info.unit} asignada a {target.unit}")
        rt = executable[eid].get("resultType")
        if rt is not None and rt != {"bool": "bool", "int": "int", "dec": "decimal", "dur": "duration",
                                      "numlit": "int", "declit": "decimal"}[info.kind]:
            ctx.err("D-TIPO", f"resultType declarado {rt!r} no coincide con el inferido")
        if len(ctx.diags) > before:
            return None
        if eid not in exprs:
            node = ex.build(executable[eid]["meaning"], eid)
            exprs[eid] = Expr(eid, node, info, ex.support(node))
        return exprs[eid]

    # Transiciones (REQ-MOD-02, REQ-MOD-04, REQ-SEM-02)
    transitions: dict[str, Transition] = {}
    for tid, t in raw_trans.items():
        pre = v.ref_set(t["preRefs"], tid, "preRefs")
        post = v.ref_set(t["postRefs"], tid, "postRefs")
        ok = True
        for ref in pre + post:
            if ref in raw_trans:
                v.add("D-ALTERNANCIA", f"transición→transición: {tid} enlaza con la transición {ref}", tid)
                ok = False
            elif ref in macro_ids:
                v.caps.add("jerarquia.macroetapas")
            elif ref not in raw_steps:
                v.add("D-REF", f"referencia de enlace inexistente: {ref}", tid)
                ok = False
        cond = use_expr(t["conditionRef"], tid, "receptivity")
        if not pre and not post:
            if opt["6.4"] == "detener":
                v.d.append(blocked("transiciones.sin-lados", "transición sin precedentes ni siguientes (se conserva como borrador)", tid))
            elif opt["6.4"] == "A":
                v.add("D-FORMATO", "transición sin etapas antes ni después: no se admite (opción 6.4 A)", tid)
        elif not pre:
            if cond is not None and not ex.is_event_positive(raw_exprs[t["conditionRef"]]["meaning"]):
                if opt["6.2"] == "detener":
                    v.d.append(blocked("transiciones.fuente-nivel", "transición fuente con receptividad de nivel", tid))
                elif opt["6.2"] == "A":
                    v.add("D-FORMATO", "transición fuente con receptividad de nivel: no se admite (opción 6.2 A)", tid)
            v.caps.add("transiciones.fuente-evento")
        if not post:
            v.caps.add("transiciones.sumidero")
        if ok:
            transitions[tid] = Transition(tid, t["partialRef"], frozenset(pre), frozenset(post), t["conditionRef"])

    # Acciones (REQ-ACT-01..04)
    actions: dict[str, Action] = {}
    modes_by_target: dict[str, set[str]] = {}
    for aid, a in raw_actions.items():
        if a["stepRef"] not in raw_steps:
            v.add("D-REF", f"stepRef inexistente: {a['stepRef']}", aid, "stepRef")
            continue
        target = variables.get(a["targetRef"])
        if target is None:
            if a["targetRef"] in raw_steps:
                v.add("D-ESCRITURA-ROL", "una acción no puede escribir la actividad de una etapa", aid, "targetRef")
            else:
                v.add("D-REF", f"targetRef inexistente: {a['targetRef']}", aid, "targetRef")
            continue
        if target.role == "input":
            v.add("D-ESCRITURA-ROL", f"una acción no puede escribir la entrada {target.id}", aid, "targetRef")
            continue
        modes_by_target.setdefault(target.id, set()).add(a["mode"])
        if a["mode"] == "continuous":
            if target.type.kind != "bool":
                v.add("D-TIPO", "una acción continua requiere objetivo booleano", aid, "targetRef")
            limit = None
            if "limitUs" in a:
                try:
                    limit = parse_time_field(a["limitUs"])
                except DiagnosticError as exc:
                    v.d.extend(exc.diagnostics)
                v.caps.add("acciones.limitadas")
            cond = use_expr(a["conditionRef"], aid, "continuous")
            v.caps.add("acciones.continuas")
            if cond is not None:
                actions[aid] = Action(aid, a["stepRef"], "continuous", target.id, cond=cond.id, limit_us=limit)
            continue
        trig = a["trigger"]
        if not v.fields("trigger", trig, aid):
            continue
        v.caps.add("acciones.memorizadas")
        kind = trig["kind"]
        sources = v.ref_set(trig["sourceRefs"], aid, "trigger.sourceRefs")
        if kind not in ("activation", "deactivation", "event"):
            v.add("D-FORMATO", f"tipo de disparador desconocido: {kind!r}", aid, "trigger.kind")
            continue
        if any(s in raw_trans for s in sources):
            v.d.append(blocked("eventos.franqueamiento", "disparador por evento de franqueamiento", aid))
            continue
        if any(s != a["stepRef"] for s in sources):
            v.add("D-REF", "sourceRefs solo admite la etapa de la acción o una transición", aid, "trigger.sourceRefs")
            continue
        trig_expr = None
        if kind == "event":
            if "expressionRef" not in trig:
                v.add("D-TIPO-EVENTO", "disparador de evento sin expresión de evento", aid)
                continue
            trig_expr = use_expr(trig["expressionRef"], aid, "trigger")
            if trig_expr is None:
                continue
        elif "expressionRef" in trig:
            v.d.append(unsupported("acciones.activacion-condicionada", "acción al activar/desactivar con condición", aid))
            continue
        value = use_expr(a["valueRef"], aid, "value", target)
        if value is not None:
            actions[aid] = Action(aid, a["stepRef"], "stored", target.id, trigger=kind,
                                  trigger_expr=trig_expr.id if trig_expr else None, value=value.id)
    for vid, modes in modes_by_target.items():
        if len(modes) > 1:
            v.add("D-MODO-SALIDA", f"{vid} recibe acciones continuas y memorizadas", vid)
    continuous_targets = {vid for vid, m in modes_by_target.items() if "continuous" in m}
    _certain_write_conflicts(v, actions, transitions, exprs, executable, opt)
    if opt["6.1"] == "A" and raw_steps and not any(s.get("initial") is True for s in raw_steps.values()):
        v.add("D-FORMATO", "grafcet sin etapas iniciales: no se admite (lectura 6.1 A)")
    # Respuesta 1.5 A de la hoja 08: las variables memorizadas empiezan en 0; otro valor inicial se pone con
    # una acción «al activar» en una etapa inicial, que se ejecuta al arrancar (respuesta 1.1 A)
    for var in sorted(variables.values(), key=lambda x: x.id):
        if opt["1.5"] == "A" and var.role != "input" and var.id not in continuous_targets and var.initial != zero(var.type):
            v.add("D-FORMATO", f"{var.id} declara valor inicial {var.initial!r}, pero las variables memorizadas empiezan "
                  "en 0; para otro valor use una acción «al activar» en una etapa inicial", var.id, "initialValue")

    # Soportes: eventos, tiempo, lecturas no admitidas (U-03, U-06, H-08, H-09, H-10)
    temporals: dict[str, TemporalSpec] = {}
    inputs = frozenset(x.id for x in variables.values() if x.role == "input")
    for eid, e in exprs.items():
        user = uses[eid][0]
        sup = e.support
        if sup.vars & continuous_targets:
            if opt["8.2"] == "detener":
                v.d.append(unsupported("acciones.salidas-continuas-leidas",
                                       f"lectura de salida continua {sorted(sup.vars & continuous_targets)}", user))
            elif opt["8.2"] == "A":
                v.add("D-FORMATO", f"lectura de salida continua {sorted(sup.vars & continuous_targets)}: no se admite "
                      "(opción 8.2 A)", user)
        if sup.elapsed:
            v.d.append(blocked("temporal.elapsed", "elapsed() no ejecutable en este perfil", user))
        if sup.macros:
            v.d.append(unsupported("jerarquia.macroetapas", "activeMacro() requiere ejecución jerárquica", user))
        for pid in sup.partials:
            v.caps.add("parciales.actividad")
            if children.get(pid) and opt["8.1"] == "detener":
                v.d.append(unsupported("parciales.anidados", f"activePartial({pid}) con parciales hijos", user))
        for evn in sup.events:
            v.caps.add("eventos.entradas")
            es = ex.support(evn.kids[0])
            if es.steps or es.partials or es.macros or es.elapsed or es.temporals or (es.vars - inputs):
                v.d.append(blocked("eventos.internos", "flanco sobre una proposición que no es solo de entradas", user))
        for tn in sup.temporals:
            v.caps.add("temporal.delay")
            d1, base, d2 = tn.kids
            if d1.op != "lit" or d2.op != "lit":
                continue
            if d1.value == 0 and opt["4.4"] != "A":
                if opt["4.4"] == "detener":
                    v.d.append(blocked("temporal.delay-cero", "delay con retardo de conexión nulo", user))
                else:
                    v.add("D-FORMATO", "retardo cero: no se admite (opción 4.4 B)", user)
                continue
            bs = ex.support(base)
            if base.op == "active":
                temporals[tn.key] = TemporalSpec(tn.key, eid, d1.value, d2.value, base, "active", base.ref)
            elif not (bs.steps or bs.partials or bs.macros or bs.elapsed or bs.temporals or bs.events) \
                    and bs.vars <= inputs:
                temporals[tn.key] = TemporalSpec(tn.key, eid, d1.value, d2.value, base, "inputs", None)
            else:
                v.d.append(unsupported("temporal.base-compuesta", "base temporal compuesta o no limitada a entradas", user))

    # Jerarquía: estructura, propiedad única, ciclos, coherencia inicial (REQ-MOD-07, REQ-JER-03)
    _validate_hierarchy(v, partials, raw_steps, forces, macros, expansions, enclosures)
    for dl in drafts:
        v.add("D-ALTERNANCIA", f"enlace de borrador {dl['fromRef']}→{dl['toRef']} viola la alternancia "
              "etapa/transición; no ejecutable", dl["id"])

    has_h = bool(forces or macros or expansions or enclosures)
    if forces:
        v.d.append(unsupported("jerarquia.forzado", "órdenes de forzado presentes"))
    if macros or expansions:
        v.d.append(unsupported("jerarquia.macroetapas", "macroetapas presentes"))
    if enclosures:
        v.d.append(unsupported("jerarquia.encapsulacion", "recintos de encapsulación presentes"))
    if has_h:
        v.caps.add("jerarquia.estructura")
    v.d.extend(ctx.diags)

    structural = {"D-FORMATO", "D-ID", "D-REF", "D-PROPIETARIO", "D-JERARQUIA-CICLO", "D-LIM-DATOS"}
    if any(x.code in structural and x.severity == "error" for x in v.d):
        return ValidationResult(v.d, None, v.caps)

    steps = {sid: Step(sid, s["label"], s["partialRef"], s["kind"], s["initial"]) for sid, s in raw_steps.items()}
    cm = CompiledModel(model_id, compute_revision(doc), steps, transitions, variables, exprs, actions,
                       {pid: {"label": p["label"], "children": children.get(pid, set()),
                              "steps": {sid for sid, s in raw_steps.items() if s["partialRef"] == pid}}
                        for pid, p in partials.items()}, has_h, inputs)
    for a in actions.values():
        if a.mode == "continuous":
            cm.continuous_by_target.setdefault(a.target, []).append(a)
        elif a.trigger == "event":
            cm.event_actions.append(a)
            cm.step_dependents.setdefault(a.step, set()).add(f"acción por evento {a.id}")
        else:
            cm.stored_by_step.setdefault((a.step, a.trigger), []).append(a)
            cm.step_dependents.setdefault(a.step, set()).add(f"acción memorizada {a.id}")
        if a.limit_us is not None:
            cm.step_dependents.setdefault(a.step, set()).add(f"acción limitada {a.id}")
    cm.temporals = temporals
    for ts in temporals.values():
        if ts.base_kind == "active":
            cm.step_dependents.setdefault(ts.base_step, set()).add(f"condición temporal {ts.key}")
    for coll in (cm.continuous_by_target.values(), cm.stored_by_step.values()):
        for lst in coll:
            lst.sort(key=lambda a: a.id)
    cm.event_actions.sort(key=lambda a: a.id)
    return ValidationResult(v.d, cm, v.caps)


def constant_value(e: Expr) -> Value | None:
    """Valor de una expresión literal (o literal negado); None si no es constante."""
    n = e.node
    if n.op == "lit":
        return n.value
    if n.op == "neg" and n.kids[0].op == "lit":
        return -n.kids[0].value
    return None


def _certain_write_conflicts(v: _V, actions: dict[str, Action], transitions: dict[str, Transition],
                             exprs: dict[str, Expr], executable: dict[str, dict[str, Any]], opt: dict[str, str]) -> None:
    """Conflictos seguros entre acciones memorizadas que se ejecutan necesariamente en la misma evolución.

    - Mismo objetivo: es conflicto salvo que ambas escriban la misma constante (P-IMP-16; respuesta 2.1 C de la
      hoja 08, que incluye dos `n := n + 1` simultáneos).
    - Una lee lo que la otra escribe: dependencia cruzada (respuesta 2.2 B).
    Ambos casos impiden compilar. Los que dependen del escenario se detectan al ejecutar.
    """
    stored = sorted((a for a in actions.values() if a.mode == "stored"), key=lambda a: a.id)

    def together(a: Action, b: Action) -> str | None:
        if a.trigger == b.trigger and a.step == b.step:
            if a.trigger != "event":
                return f"la misma {'activación' if a.trigger == 'activation' else 'desactivación'} de {a.step}"
            if executable[a.trigger_expr]["meaning"] == executable[b.trigger_expr]["meaning"]:
                return f"el mismo evento en {a.step}"
            return None
        if "event" in (a.trigger, b.trigger):
            return None
        for t in sorted(transitions.values(), key=lambda t: t.id):
            activated, deactivated = t.post - t.pre, t.pre - t.post
            sa = activated if a.trigger == "activation" else deactivated
            sb = activated if b.trigger == "activation" else deactivated
            if a.step in sa and b.step in sb:
                return f"el franqueamiento de {t.id}"
        return None

    def text(a: Action) -> str:
        return executable[a.value]["text"]

    for i, a in enumerate(stored):
        for b in stored[i + 1:]:
            why = together(a, b)
            if not why:
                continue
            if a.target == b.target:
                ca, cb = constant_value(exprs[a.value]), constant_value(exprs[b.value])
                if ca is not None and ca == cb:
                    continue  # la misma constante: un único resultado (T-16b)
                if opt["2.1"] == "B" or (opt["2.1"] == "A" and (ca is None or cb is None)):
                    continue  # 2.1 B se acumulan; 2.1 A con valores no constantes se decide al ejecutar
                v.d.append(Diagnostic(
                    "D-ESCRITURA-CONFLICTO", f"conflicto de escritura seguro sobre {a.target}: {a.id} y {b.id} escriben a "
                    f"la vez en {why}; el programa no puede compilarse", element=a.target, severity="error",
                    evidence={"autores": f"{a.id}, {b.id}", "valores": f"{text(a)}, {text(b)}", "causa": why}))
                continue
            for x, y in ((a, b), (b, a)) if opt["2.2"] == "B" else ():
                if y.target in exprs[x.value].support.vars:
                    v.d.append(Diagnostic(
                        "D-DEPENDENCIA-CRUZADA", f"{x.id} lee {y.target}, que {y.id} escribe a la vez en {why}; "
                        "el programa no puede compilarse", element=x.id, severity="error",
                        evidence={"lee": f"{x.id} ({x.target} := {text(x)})", "escribe": f"{y.id} ({y.target} := {text(y)})",
                                  "causa": why}))
                    break


def _validate_hierarchy(v: _V, partials: dict[str, Any], steps: dict[str, Any], forces: list[dict[str, Any]],
                        macros: list[dict[str, Any]], expansions: list[dict[str, Any]],
                        enclosures: list[dict[str, Any]]) -> None:
    # Forzado: relación superior → inferior acíclica (D-JERARQUIA-CICLO); conflicto posible
    fgraph: dict[str, set[str]] = {}
    by_target: dict[str, list[dict[str, Any]]] = {}
    for f in forces:
        src, dst = f["sourceStepRef"], f["targetPartialRef"]
        if src not in steps:
            v.add("D-REF", f"sourceStepRef inexistente: {src}", f["id"])
            continue
        if dst not in partials:
            v.add("D-REF", f"targetPartialRef inexistente: {dst}", f["id"])
            continue
        if f["targetKind"] not in ("explicit", "current", "empty", "initial"):
            v.add("D-FORMATO", f"targetKind desconocido: {f['targetKind']!r}", f["id"])
            continue
        if (f["targetKind"] == "explicit") != ("targetSteps" in f):
            v.add("D-FORMATO", "targetSteps es obligatorio solo para targetKind=explicit", f["id"])
            continue
        for ts in f.get("targetSteps", []):
            if ts not in steps or steps[ts]["partialRef"] != dst:
                v.add("D-REF", f"targetSteps contiene {ts}, que no es etapa del parcial destino", f["id"])
        fgraph.setdefault(steps[src]["partialRef"], set()).add(dst)
        by_target.setdefault(dst, []).append(f)
    cyc = _cycle(fgraph)
    if cyc:
        v.add("D-JERARQUIA-CICLO", "ciclo en la relación de forzado superior→inferior", cyc[0], camino=" → ".join(cyc))
    for dst, fs in by_target.items():
        targets = {(f["targetKind"], tuple(sorted(f.get("targetSteps", [])))) for f in fs}
        if len(targets) > 1:
            v.d.append(Diagnostic("D-FORZADO-CONFLICTO", "órdenes con igual destino y objetivo distinto: conflicto si "
                                  "sus orígenes coinciden activos (sin prioridad por ID ni posición)", element=dst,
                                  severity="advertencia", evidence={"ordenes": ", ".join(sorted(f["id"] for f in fs))}))
    # Macroetapas: una expansión por macro y propietario único (T-18c)
    exp_by_id = {x["id"]: x for x in expansions}
    used: dict[str, str] = {}
    hgraph: dict[str, set[str]] = {}
    hier_partials: dict[str, str] = {}
    for m in macros:
        if m["partialRef"] not in partials:
            v.add("D-REF", f"partialRef inexistente: {m['partialRef']}", m["id"])
        x = exp_by_id.get(m["expansionRef"])
        if x is None:
            v.add("D-REF", f"expansionRef inexistente: {m['expansionRef']}", m["id"])
            continue
        if m["expansionRef"] in used:
            v.add("D-PROPIETARIO", f"la expansión {m['expansionRef']} es compartida por {used[m['expansionRef']]} y {m['id']}", m["id"])
        used[m["expansionRef"]] = m["id"]
        if x["ownerMacroRef"] != m["id"]:
            v.add("D-PROPIETARIO", f"ownerMacroRef de {x['id']} no coincide con {m['id']}", x["id"])
        hgraph.setdefault(m["partialRef"], set()).add(x["partialRef"])
    for x in expansions:
        if x["partialRef"] not in partials:
            v.add("D-REF", f"partialRef inexistente: {x['partialRef']}", x["id"])
            continue
        if x["partialRef"] in hier_partials:
            v.add("D-PROPIETARIO", f"el parcial {x['partialRef']} ya pertenece a {hier_partials[x['partialRef']]}", x["id"])
        hier_partials[x["partialRef"]] = x["id"]
        for fld, kind in (("entryRef", "entry"), ("exitRef", "exit")):
            st = steps.get(x[fld])
            if st is None or st["partialRef"] != x["partialRef"]:
                v.add("D-REF", f"{fld} debe ser una etapa de la expansión", x["id"], fld)
            elif st["kind"] != kind:
                v.add("D-FORMATO", f"{x[fld]} debe tener kind={kind} (referencias redundantes deben coincidir)", x[fld])
        if x["entryRef"] == x["exitRef"]:
            v.add("D-FORMATO", "entrada y salida de la expansión deben ser distintas", x["id"])
    # Encapsulación: un propietario por recinto, coherencia inicial (T-19c)
    for x in enclosures:
        own = steps.get(x["ownerStepRef"])
        if own is None:
            v.add("D-REF", f"ownerStepRef inexistente: {x['ownerStepRef']}", x["id"])
            continue
        if own["kind"] != "enclosing":
            v.add("D-FORMATO", f"{x['ownerStepRef']} debe tener kind=enclosing", x["ownerStepRef"])
        if x["partialRef"] not in partials:
            v.add("D-REF", f"partialRef inexistente: {x['partialRef']}", x["id"])
            continue
        if x["partialRef"] in hier_partials:
            v.add("D-PROPIETARIO", f"el recinto {x['partialRef']} ya pertenece a {hier_partials[x['partialRef']]}", x["id"])
        hier_partials[x["partialRef"]] = x["id"]
        hgraph.setdefault(own["partialRef"], set()).add(x["partialRef"])
        for ar in x["activationRefs"]:
            if ar not in steps or steps[ar]["partialRef"] != x["partialRef"]:
                v.add("D-REF", f"activationRefs contiene {ar}, que no es etapa del recinto", x["id"])
        inner_initial = [sid for sid, s in steps.items() if s["partialRef"] == x["partialRef"] and s["initial"] is True]
        if own["initial"] is not True and inner_initial:
            v.add("D-JERARQUIA-INICIAL", f"etapas iniciales {inner_initial} dentro de un recinto cuya encapsulante "
                  "no es inicial; no se completa el padre sin aviso", x["id"])
        if own["initial"] is True and not inner_initial:
            v.add("D-JERARQUIA-INICIAL", "encapsulante inicial con recinto sin etapa inicial", x["id"])
    cyc = _cycle(hgraph)
    if cyc:
        v.add("D-JERARQUIA-CICLO", "recursión de expansión o encapsulación", cyc[0], camino=" → ".join(cyc))
    for sid, s in steps.items():
        if s["kind"] in ("entry", "exit") and not any(sid in (x["entryRef"], x["exitRef"]) for x in expansions):
            v.add("D-FORMATO", f"etapa kind={s['kind']} sin expansión que la declare", sid)
