"""Motor de interpretación del perfil provisional (documentos 04, 05 y 08).

Lo que fija (I provisional por U-01, nunca «conforme»):
- Validación Pre(t) ⊆ S, franqueamiento con receptividad verdadera, conjunto simultáneo
  completo y relación colectiva S' = (S \\ D) ∪ A (REQ-SEM-02..05).
- Recorrido transitorio dentro de un contexto causal sin avance de τ. Las etapas
  virtuales no producen salidas continuas; sus acciones memorizadas se conservan (REQ-SEM-06).
- Flancos sobre entradas evaluados entre el estado anterior y el posterior del lote (REQ-EVT-01).
- delay(d1,p,d2) ordinario, acciones limitadas y salidas continuas por disyunción (REQ-TMP-02, REQ-ACT-01).
- Presupuesto de evoluciones con D-LIM-EVOL recuperable (REQ-SEM-07).

Lo que no fija: cuando el resultado dependería de una cuestión abierta, el contexto se
detiene con D-SEM-PENDIENTE, se conserva el último estado estable y no se elige
ninguna alternativa (U-03, U-04, U-05, U-06, U-07, U-09; hallazgos H-05, H-09).
Regla general: si todas las lecturas posibles dan el mismo resultado (lecturas de un
evento en evoluciones posteriores, orden de vencimientos simultáneos), el resultado no
depende de la cuestión y se acepta; si difieren, se bloquea.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace
from typing import Any, Generator, Iterable

from . import expressions as ex
from .diagnostics import Diagnostic, DiagnosticError
from .model import Action, CompiledModel, TemporalSpec
from .profile import PROFILE_ID, PROFILE_VERSION, blocked, sem_pending
from .scenario import Batch, Scenario
from .timeutil import MAX_US
from .trace import Trace
from .values import Value, check_fits, format_value, in_domain, parse_value, zero

DEFAULT_BUDGET = 10_000
SNAPSHOT_EVERY = 100


# --- Estado Z ------------------------------------------------------------------------

@dataclass
class TState:
    phase: str = "inactive"  # inactive | on_pending | on | off_pending
    base: bool = False
    start: int | None = None
    deadline: int | None = None

    @property
    def value(self) -> bool:
        return self.phase in ("on", "off_pending")

    def to_dict(self) -> dict[str, Any]:
        return {"phase": self.phase, "baseValue": self.base, "effectiveValue": self.value,
                "intervalStart": "inactive" if self.start is None else str(self.start),
                "deadline": "inactive" if self.deadline is None else str(self.deadline)}


@dataclass
class State:
    situation: frozenset[str]
    values: dict[str, Value]
    outputs: dict[str, bool]
    contributors: dict[str, list[str]]
    temporal: dict[str, TState]
    since: dict[str, int]
    time: int
    next_batch: int
    contexts: int
    phase: str = "estable"
    origin: str = "normativa"

    def copy(self) -> "State":
        return replace(self, values=dict(self.values), outputs=dict(self.outputs),
                       contributors={k: list(v) for k, v in self.contributors.items()},
                       temporal={k: replace(v) for k, v in self.temporal.items()}, since=dict(self.since))

    def equivalent(self, other: "State") -> bool:
        return (self.situation == other.situation and self.values == other.values and self.outputs == other.outputs
                and {k: v.to_dict() for k, v in self.temporal.items()} == {k: v.to_dict() for k, v in other.temporal.items()}
                and self.since == other.since)

    def to_dict(self, cm: CompiledModel, pending: list[Batch]) -> dict[str, Any]:
        """Z completo (documento 09, State). Campos no aplicables se declaran explícitamente."""
        return {
            "activeStepRefs": sorted(self.situation),
            "values": {k: format_value(cm.variables[k].type, v) for k, v in sorted(self.values.items())},
            "storedValues": {v.id: format_value(v.type, self.values[v.id]) for v in sorted(cm.stored_vars(), key=lambda x: x.id)},
            "outputs": {k: {"value": v, "contributors": sorted(self.contributors.get(k, []))} for k, v in sorted(self.outputs.items())},
            "eventHistory": {"basis": "estable", "pendingEvents": []},
            "temporalStates": {k: v.to_dict() for k, v in sorted(self.temporal.items())},
            "stepActivationTimes": {k: str(v) for k, v in sorted(self.since.items())},
            "hierarchyState": {"status": "no-aplicable", "reason": "jerarquía no ejecutable en este perfil"},
            "activeForces": [],
            "logicalTimeUs": str(self.time),
            "pendingBatches": [b.to_dict(cm) for b in pending],
            "nextBatchIndex": self.next_batch,
            "completedContexts": self.contexts,
            "phase": self.phase,
            "origin": self.origin,
            "causalContext": None,
        }


def state_from_dict(cm: CompiledModel, d: dict[str, Any]) -> tuple[State, list[Batch]]:
    def t_or_none(v: str) -> int | None:
        return None if v == "inactive" else int(v)
    temporal = {k: TState(v["phase"], v["baseValue"], t_or_none(v["intervalStart"]), t_or_none(v["deadline"]))
                for k, v in d["temporalStates"].items()}
    if set(temporal) != set(cm.temporals) or set(d["values"]) != set(cm.variables) - set(cm.continuous_by_target):
        raise DiagnosticError(Diagnostic("D-INSTANTANEA-INCOMPATIBLE", "el estado no contiene todos los componentes de Z del modelo"))
    pending = [Batch(b["id"], int(b["timeUs"]), b["ordinalAtTime"],
                     tuple((c["variableRef"], parse_value(cm.variables[c["variableRef"]].type, c["value"])) for c in b["changes"]),
                     b["origin"]) for b in d["pendingBatches"]]
    st = State(frozenset(d["activeStepRefs"]),
               {k: parse_value(cm.variables[k].type, v) for k, v in d["values"].items()},
               {k: v["value"] for k, v in d["outputs"].items()},
               {k: list(v["contributors"]) for k, v in d["outputs"].items()},
               temporal, {k: int(v) for k, v in d["stepActivationTimes"].items()}, int(d["logicalTimeUs"]),
               d["nextBatchIndex"], d["completedContexts"], d["phase"], d["origin"])
    return st, pending


# --- Entornos de evaluación ----------------------------------------------------------

class _Env:
    def __init__(self, cm: CompiledModel, w: State, events: dict[str, bool] | None) -> None:
        self.cm, self.w, self.events = cm, w, events or {}

    def var(self, vid: str) -> Value:
        return self.w.values[vid]

    def active(self, sid: str) -> bool:
        return sid in self.w.situation

    def active_partial(self, pid: str) -> bool:
        return bool(self.cm.partials[pid]["steps"] & self.w.situation)

    def active_macro(self, mid: str) -> bool:
        raise DiagnosticError(blocked("jerarquia.macroetapas", "activeMacro no ejecutable"))

    def elapsed(self, sid: str) -> int:
        raise DiagnosticError(blocked("temporal.elapsed", "elapsed no ejecutable"))

    def event(self, key: str) -> bool:
        return self.events.get(key, False)

    def temporal(self, key: str) -> bool:
        return self.w.temporal[key].value


class _InputEnv(_Env):
    def __init__(self, cm: CompiledModel, values: dict[str, Value]) -> None:
        self.cm, self.values = cm, values

    def var(self, vid: str) -> Value:
        return self.values[vid]


# --- Contexto causal -----------------------------------------------------------------

@dataclass
class Stimulus:
    kind: str  # lote | vencimiento
    time: int
    batch: Batch | None = None
    expiring: tuple[str, ...] = ()


class Blocked(Exception):
    def __init__(self, diag: Diagnostic) -> None:
        super().__init__(str(diag))
        self.diag = diag


@dataclass
class Control:
    budget: int = DEFAULT_BUDGET
    abort: bool = False


@dataclass
class Outcome:
    status: str  # estable | fallo
    state: State | None
    records: list[dict[str, Any]] = field(default_factory=list)
    diagnostic: Diagnostic | None = None


def _base_change(st: TState, spec: TemporalSpec, new: bool, now: int, element: str) -> None:
    if new == st.base:
        return
    st.base = new
    if new:
        if st.phase == "off_pending":
            raise Blocked(blocked("temporal.coincidencias", "rebote: la base vuelve a ser verdadera durante el retardo de "
                                  "desconexión (cancelar o mantener)", element))
        st.phase, st.start = "on_pending", now
        st.deadline = now + spec.d1 if now + spec.d1 <= MAX_US else None
    elif st.phase == "on_pending":
        st.phase, st.start, st.deadline = "inactive", None, None
    elif st.phase == "on":
        if spec.d2 == 0:
            st.phase, st.start, st.deadline = "inactive", None, None
        else:
            st.phase, st.start = "off_pending", now
            st.deadline = now + spec.d2 if now + spec.d2 <= MAX_US else None


def _expire(st: TState, now: int) -> None:
    if st.deadline == now:
        if st.phase == "on_pending":
            st.phase, st.deadline = "on", None
        elif st.phase == "off_pending":
            st.phase, st.start, st.deadline = "inactive", None, None


def compute_outputs(cm: CompiledModel, w: State) -> None:
    """Salida continua = disyunción de contribuciones de la situación efectiva (REQ-ACT-01)."""
    env = _Env(cm, w, None)
    for target, acts in sorted(cm.continuous_by_target.items()):
        contrib = []
        for a in acts:
            if a.step not in w.situation:
                continue
            if a.limit_us is not None and not (w.time - w.since[a.step] < a.limit_us):
                continue
            if ex.evaluate(cm.exprs[a.cond].node, env):
                contrib.append(a.id)
        w.outputs[target] = bool(contrib)
        w.contributors[target] = contrib


def _fmt(cm: CompiledModel, vid: str, val: Value) -> Any:
    return format_value(cm.variables[vid].type, val)


def run_context(cm: CompiledModel, z: State, stim: Stimulus, ctl: Control
                ) -> Generator[tuple[str, Any], None, Outcome]:
    """Procesa un estímulo hasta su cierre causal. Produce ("propuesta", E), ("aplicada", registro) y
    ("limite", k); devuelve el resultado. El estado z no se modifica: se trabaja sobre una copia."""
    w = z.copy()
    w.time = stim.time
    records: list[dict[str, Any]] = []
    prior_s = z.situation
    events: dict[str, bool] = {}
    fire: list[str] = []
    try:
        # 1. Aplicar el estímulo
        changed: dict[str, Any] = {}
        if stim.kind == "lote":
            assert stim.batch is not None
            before = dict(w.values)
            for vid, val in stim.batch.changes:
                if w.values[vid] != val:
                    changed[vid] = _fmt(cm, vid, val)
                w.values[vid] = val
            for e in cm.exprs.values():
                for n in e.support.events:
                    b = bool(ex.evaluate(n.kids[0], _InputEnv(cm, before)))
                    a = bool(ex.evaluate(n.kids[0], _InputEnv(cm, w.values)))
                    events[n.key] = (not b and a) if n.op == "rise" else (b and not a)
            for key, spec in sorted(cm.temporals.items()):
                if spec.base_kind == "inputs":
                    _base_change(w.temporal[key], spec, bool(ex.evaluate(spec.base, _InputEnv(cm, w.values))),
                                 w.time, spec.expr)
        else:
            for key in stim.expiring:
                if key in w.temporal:
                    _expire(w.temporal[key], w.time)
        records.append({"kind": "contexto", "timeUs": str(w.time), "stimulus": stim.kind,
                        "batch": stim.batch.id if stim.batch else None,
                        "batchOrdinal": stim.batch.ordinal if stim.batch else None,
                        "origin": stim.batch.origin if stim.batch else "vencimiento",
                        "inputChanges": changed, "expiring": sorted(stim.expiring),
                        "events": sorted(k for k, v in events.items() if v)})
        present = {k for k, v in events.items() if v}
        written: dict[str, tuple[Value, list[str]]] = {}
        deact_ctx: set[str] = set()
        act_ctx: set[str] = set()
        done_event_actions: list[Action] = []
        k = 0
        while True:
            k += 1
            while k > ctl.budget:
                yield ("limite", (k - 1, list(records)))
                if ctl.abort:
                    return Outcome("fallo", None, records, Diagnostic("D-LIM-EVOL", "contexto abandonado tras el límite"))
            s = w.situation
            env = _Env(cm, w, events)
            env0 = _Env(cm, w, None)
            fire: list[str] = []
            info: dict[str, Any] = {}
            for t in sorted(cm.transitions.values(), key=lambda t: t.id):
                if not t.pre <= s:
                    continue
                e = cm.exprs[t.cond]
                if e.support.vars & set(written):
                    raise Blocked(blocked("acciones.lecturas-contexto", "una receptividad lee un valor asignado en el "
                                          f"mismo contexto: {sorted(e.support.vars & set(written))}", t.id))
                val = bool(ex.evaluate(e.node, env))
                if k >= 2 and any(n.key in present for n in e.support.events):
                    if val != bool(ex.evaluate(e.node, env0)):
                        if not t.pre:
                            raise Blocked(blocked("transiciones.fuente-repeticion", "transición fuente: ¿se repite el "
                                                  "mismo evento en evoluciones posteriores del contexto?", t.id))
                        raise Blocked(blocked("eventos.recorrido", "transición que sigue validada o se valida durante el "
                                              "recorrido causado por el propio evento", t.id))
                info[t.id] = val
                if val:
                    fire.append(t.id)
            proposals: list[Action] = []
            if k == 1:
                for a in cm.event_actions:
                    if bool(ex.evaluate(cm.exprs[a.trigger_expr].node, env)):
                        if a.step in prior_s:
                            proposals.append(a)
                            done_event_actions.append(a)
            if not fire and not proposals:
                break
            yield ("propuesta", (k, fire))
            ts = [cm.transitions[t] for t in fire]
            d_set = frozenset().union(*(t.pre for t in ts)) if ts else frozenset()
            a_set = frozenset().union(*(t.post for t in ts)) if ts else frozenset()
            new_s = (s - d_set) | a_set
            activated, deactivated = a_set - s, d_set - a_set
            permanent, reactivated = d_set & a_set, (a_set & s) - d_set
            for sid in sorted(permanent | reactivated):
                if cm.step_dependents.get(sid):
                    why = "permanencia activa (activada y desactivada a la vez)" if sid in permanent \
                        else "activación de una etapa ya activa no incluida en D (H-05)"
                    raise Blocked(blocked("permanencia.efectos", f"{why} con {sorted(cm.step_dependents[sid])}", sid))
            for sid in sorted(activated & deact_ctx):
                deps = [x for x in cm.step_dependents.get(sid, ()) if x.startswith(("condición temporal", "acción limitada"))]
                if deps:
                    raise Blocked(blocked("temporal.reentrada-virtual", f"salida y reentrada en el mismo contexto con {deps}", sid))
            for a in done_event_actions:
                if a.step in deactivated:
                    raise Blocked(blocked("eventos.recorrido", f"acción por evento {a.id} en etapa desactivada por el mismo "
                                          "contexto (U-03/U-05)", a.step))
            for a in cm.event_actions:
                if a.step in activated and any(n.key in present for n in cm.exprs[a.trigger_expr].support.events):
                    raise Blocked(blocked("eventos.recorrido", f"acción por evento {a.id} en etapa activada durante el "
                                          "recorrido de ese evento", a.step))
            for sid in sorted(activated):
                proposals.extend(cm.stored_by_step.get((sid, "activation"), []))
            for sid in sorted(deactivated):
                proposals.extend(cm.stored_by_step.get((sid, "deactivation"), []))
            # Asignaciones memorizadas (REQ-ACT-02, REQ-ACT-03; U-05)
            values: dict[str, list[tuple[Value, str]]] = {}
            for a in proposals:
                reads = cm.exprs[a.value].support.vars
                others = {b.target for b in proposals if b is not a}
                if reads & (set(written) | others):
                    raise Blocked(blocked("acciones.lecturas-contexto", f"la acción {a.id} lee "
                                          f"{sorted(reads & (set(written) | others))}, asignado en el mismo contexto", a.id))
                var = cm.variables[a.target]
                val = check_fits(var.type, ex.evaluate(cm.exprs[a.value].node, env))
                if not in_domain(var.type, var.domain, val):
                    raise DiagnosticError(Diagnostic("D-NUM", f"{a.target} fuera de dominio", element=a.id,
                                                     evidence={"valor": str(val)}))
                values.setdefault(a.target, []).append((val, a.id))
            assignments = []
            for target, props in sorted(values.items()):
                distinct = {p[0] for p in props}
                if len(distinct) > 1:
                    raise DiagnosticError(Diagnostic(
                        "D-ESCRITURA-CONFLICTO", f"valores contradictorios para {target} en la misma evolución",
                        element=target, evidence={"propuestas": "; ".join(f"{a}={_fmt(cm, target, v)}" for v, a in props),
                                                  "contexto": str(w.time)}))
                val = props[0][0]
                if target in written and written[target][0] != val:
                    raise Blocked(blocked("acciones.lecturas-contexto", f"asignaciones sucesivas distintas sobre {target} "
                                          "en el mismo contexto (no se aplica «última escritura gana»)", target))
                authors = sorted(a for _, a in props)
                written[target] = (val, written.get(target, (val, []))[1] + authors)
                w.values[target] = val
                assignments.append({"target": target, "value": _fmt(cm, target, val), "authors": authors})
            w.situation = new_s
            for sid in activated:
                w.since[sid] = w.time
            for sid in deactivated:
                w.since.pop(sid, None)
            for key, spec in sorted(cm.temporals.items()):
                if spec.base_kind == "active" and spec.base_step in (activated | deactivated):
                    _base_change(w.temporal[key], spec, spec.base_step in new_s, w.time, spec.base_step)
            deact_ctx |= deactivated
            act_ctx |= activated
            rec = {"kind": "evolucion", "timeUs": str(w.time), "evolutionIndex": k,
                   "validated": sorted(info), "receptivity": dict(sorted(info.items())), "cleared": sorted(fire),
                   "deactivated": sorted(deactivated), "activated": sorted(activated), "permanent": sorted(permanent),
                   "situation": sorted(new_s), "assignments": assignments}
            records.append(rec)
            yield ("aplicada", rec)
        compute_outputs(cm, w)
        w.contexts += 1
        w.phase = "estable"
        if stim.kind == "lote":
            w.next_batch += 1
        virtual = sorted((act_ctx | deact_ctx | prior_s) - w.situation - prior_s) if (act_ctx or deact_ctx) else []
        records.append({"kind": "estable", "timeUs": str(w.time), "situation": sorted(w.situation),
                        "virtualSteps": virtual,
                        "outputs": {k: v for k, v in sorted(w.outputs.items())},
                        "values": {k: _fmt(cm, k, v) for k, v in sorted(w.values.items()) if v != z.values.get(k)}})
        return Outcome("estable", w, records)
    except Blocked as b:
        records.append({"kind": "fallo", "timeUs": str(w.time), "diagnostics": [b.diag.to_dict()],
                        "proposedSet": sorted(fire), "situationCandidate": sorted(w.situation)})
        return Outcome("fallo", None, records, b.diag)
    except DiagnosticError as exc:
        dg = exc.diagnostics[0]
        records.append({"kind": "fallo", "timeUs": str(w.time), "diagnostics": [d.to_dict() for d in exc.diagnostics],
                        "proposedSet": sorted(fire), "situationCandidate": sorted(w.situation)})
        return Outcome("fallo", None, records, dg)


def run_full(cm: CompiledModel, z: State, stim: Stimulus, budget: int = DEFAULT_BUDGET) -> Outcome:
    gen = run_context(cm, z, stim, Control(budget, abort=True))
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


def check_simultaneous_expiries(cm: CompiledModel, z: State, stim: Stimulus, budget: int) -> Diagnostic | None:
    """Varios vencimientos en el mismo instante: se aceptan solo si el resultado no depende del orden (U-06)."""
    keys = stim.expiring
    if len(keys) < 2:
        return None
    if len(keys) > 4:
        return blocked("temporal.coincidencias", f"{len(keys)} vencimientos simultáneos: demasiados para comparar órdenes")
    ref = run_full(cm, z, stim, budget)
    for perm in itertools.permutations(keys):
        cur: State | None = z
        for key in perm:
            out = run_full(cm, cur, Stimulus("vencimiento", stim.time, None, (key,)), budget)
            if out.status != "estable":
                cur = None
                break
            cur = out.state
        if ref.status != "estable" or cur is None or not cur.equivalent(ref.state):
            return blocked("temporal.coincidencias", "vencimientos simultáneos cuyo resultado depende del orden "
                           f"({', '.join(perm)})")
    return None


# --- Inicialización ------------------------------------------------------------------

def initial_state(cm: CompiledModel, scenario: Scenario) -> tuple[State | None, list[Diagnostic]]:
    """Inicialización normativa provisional: situación inicial explícita (REQ-SEM-01) y
    bloqueo de los casos abiertos en U-07/U-09."""
    diags: list[Diagnostic] = []
    s0 = cm.initial_situation()
    if not s0:
        diags.append(blocked("situacion.inicial.vacia", "no hay etapas iniciales; no se inventa ninguna"))
    values: dict[str, Value] = {}
    for v in cm.variables.values():
        if v.id in cm.continuous_by_target:
            continue
        if v.role == "input":
            if v.id in scenario.initial:
                values[v.id] = scenario.initial[v.id]
        else:
            if v.initial != zero(v.type):
                diags.append(blocked("inicio.memoria-no-nula", f"valor inicial declarado {v.initial!r}; el inicio "
                                     "normativo provisional es falso/cero (H-07)", v.id))
            values[v.id] = zero(v.type)
    for sid in sorted(s0):
        for a in cm.stored_by_step.get((sid, "activation"), []):
            diags.append(blocked("inicio.acciones-activacion", f"acción al activar la etapa inicial {sid}", a.id))
    w = State(s0, values, {}, {}, {}, {sid: 0 for sid in s0}, 0, 0, 0)
    for key, spec in sorted(cm.temporals.items()):
        st = TState()
        if spec.base_kind == "active":
            if spec.base_step in s0:  # capacidad temporal.duracion-etapa-inicial (H-02)
                st = TState("on_pending", True, 0, spec.d1)
        elif bool(ex.evaluate(spec.base, _InputEnv(cm, values))):
            diags.append(blocked("inicio.temporal-entrada-verdadera", "condición temporal sobre una entrada verdadera "
                                 "al iniciar", spec.expr))
        w.temporal[key] = st
    if diags:
        return None, diags
    env = _Env(cm, w, None)
    for t in sorted(cm.transitions.values(), key=lambda t: t.id):
        if t.pre <= s0 and bool(ex.evaluate(cm.exprs[t.cond].node, env)):
            diags.append(blocked("inicio.inestable", "transición franqueable en la situación inicial", t.id))
    if diags:
        return None, diags
    compute_outputs(cm, w)
    return w, []


def declared_state(cm: CompiledModel, situation: Iterable[str], values: dict[str, Value] | None = None,
                   time: int = 0, since: dict[str, int] | None = None) -> State:
    """Estado previo declarado de prueba (ficha común del documento 11; hallazgo H-04).
    No es una inicialización normativa y queda marcado en la traza."""
    s = frozenset(situation)
    vals = {v.id: zero(v.type) for v in cm.variables.values() if v.id not in cm.continuous_by_target}
    vals.update(values or {})
    since = dict(since or {sid: time for sid in s})
    w = State(s, vals, {}, {}, {}, {sid: since[sid] for sid in s}, time, 0, 0, origin="declarado-prueba")
    for key, spec in cm.temporals.items():
        st = TState()
        if spec.base_kind == "active" and spec.base_step in s:
            t0 = w.since[spec.base_step]
            st = TState("on", True, t0, None) if time - t0 >= spec.d1 else TState("on_pending", True, t0, t0 + spec.d1)
        elif spec.base_kind == "inputs" and ex.evaluate(spec.base, _InputEnv(cm, vals)):
            raise ValueError("estado declarado con base temporal de entrada verdadera: declare su estado temporal")
        w.temporal[key] = st
    env = _Env(cm, w, None)
    for t in cm.transitions.values():
        if t.pre <= s and ex.evaluate(cm.exprs[t.cond].node, env):
            raise ValueError(f"estado declarado inestable: {t.id} es franqueable")
    compute_outputs(cm, w)
    return w


# --- Sesión de simulación (controles del documento 08) ---------------------------------

SESSION_STATES = {"preparada", "ejecutando", "pausada-estable", "pausada-recorrido", "detenida", "finalizada", "error"}


class Session:
    def __init__(self, cm: CompiledModel, scenario: Scenario, budget: int = DEFAULT_BUDGET,
                 run_id: str = "run-1", batches: list[Batch] | None = None, parent: str | None = None) -> None:
        self.cm, self.scenario, self.run_id = cm, scenario, run_id
        self.ctl = Control(budget)
        self.batches = list(batches if batches is not None else scenario.batches)
        self.trace = Trace({"runId": run_id, "modelRevision": cm.revision, "scenario": scenario.id,
                            "semanticProfile": {"id": PROFILE_ID, "version": PROFILE_VERSION}, "timeUnit": "us",
                            "limits": {"evolutionBudget": budget}, "parentRun": parent})
        self.status = "preparada"
        self.z: State | None = None
        self.diagnostics: list[Diagnostic] = []
        self.breakpoints: dict[str, str] = {}
        self._gen: Generator[tuple[str, Any], None, Outcome] | None = None
        self._stim: Stimulus | None = None
        self._work: dict[str, Any] | None = None
        self._flushed = 0

    # -- registro
    def _log(self, kind: str, **data: Any) -> dict[str, Any]:
        return self.trace.add(kind, runId=self.run_id, **data)

    def _snapshot_record(self) -> None:
        assert self.z is not None
        self._log("instantanea", timeUs=str(self.z.time), snapshot=self.z.to_dict(self.cm, self.pending()))

    def pending(self) -> list[Batch]:
        return self.batches[self.z.next_batch:] if self.z else list(self.batches)

    # -- inicio
    def start(self) -> list[Diagnostic]:
        if self.status != "preparada":
            raise RuntimeError("la sesión ya se inició")
        z, diags = initial_state(self.cm, self.scenario)
        if z is None:
            self.status, self.diagnostics = "error", diags
            self._log("fallo", timeUs="0", diagnostics=[d.to_dict() for d in diags])
            return diags
        self._begin(z, "inicio")
        return []

    def start_declared(self, z: State) -> None:
        self._begin(z, "inicio-declarado")

    def _begin(self, z: State, kind: str) -> None:
        self.z = z
        self._log("inicio", timeUs=str(z.time), origin=z.origin, mode=kind,
                  situation=sorted(z.situation), outputs=dict(sorted(z.outputs.items())))
        self._snapshot_record()
        self.status = "pausada-estable"

    # -- selección del siguiente hecho
    def _limited_ends(self) -> dict[int, list[str]]:
        ends: dict[int, list[str]] = {}
        for acts in self.cm.continuous_by_target.values():
            for a in acts:
                if a.limit_us is not None and a.step in self.z.situation:
                    end = self.z.since[a.step] + a.limit_us
                    if end > self.z.time and end <= MAX_US:
                        ends.setdefault(end, []).append(f"limit:{a.id}")
        return ends

    def next_stimulus(self) -> Stimulus | Diagnostic | None:
        z = self.z
        deadlines: dict[int, list[str]] = self._limited_ends()
        for key, st in z.temporal.items():
            if st.deadline is not None:
                deadlines.setdefault(st.deadline, []).append(key)
        nd = min(deadlines) if deadlines else None
        nb = self.batches[z.next_batch] if z.next_batch < len(self.batches) else None
        horizon = self.scenario.horizon
        if nd is not None and (nb is None or nd < nb.time):
            return None if horizon is not None and nd > horizon else Stimulus("vencimiento", nd, None, tuple(sorted(deadlines[nd])))
        if nb is not None and nd == nb.time:
            if horizon is not None and nd > horizon:
                return None
            return blocked("temporal.coincidencias", f"lote {nb.id} y vencimientos {sorted(deadlines[nd])} en el mismo "
                           f"instante {nd} µs: no se fija orden de cola")
        if nb is not None:
            return None if horizon is not None and nb.time > horizon else Stimulus("lote", nb.time, nb)
        return None

    # -- controles
    def _open(self) -> bool:
        if self.status != "pausada-estable":
            raise RuntimeError(f"operación no disponible en estado {self.status}")
        if self.z.contexts >= self.scenario.max_contexts:
            self.status = "finalizada"
            self._log("estable", timeUs=str(self.z.time), situation=sorted(self.z.situation), reason="maxContexts")
            return False
        if self.trace.remaining() < self.ctl.budget * 2 + 10:
            self._fail(Diagnostic("D-TRAZA-LIM", "espacio de traza insuficiente para el siguiente contexto"), "pausada-estable")
            return False
        nxt = self.next_stimulus()
        if nxt is None:
            self.status = "finalizada"
            return False
        if isinstance(nxt, Diagnostic):
            self._fail(nxt)
            return False
        if nxt.kind == "vencimiento":
            dg = check_simultaneous_expiries(self.cm, self.z, nxt, self.ctl.budget)
            if dg is not None:
                self._fail(dg)
                return False
        self._stim = nxt
        self._gen = run_context(self.cm, self.z, nxt, self.ctl)
        self._work = None
        self._flushed = 0
        self.status = "ejecutando"
        return True

    def _fail(self, dg: Diagnostic, status: str = "error") -> None:
        self.diagnostics.append(dg)
        self._log("fallo", timeUs=str(self.z.time), diagnostics=[dg.to_dict()])
        self.status = status

    def _pump(self, stop_after_evolution: bool = False) -> None:
        """Avanza el contexto abierto hasta su cierre, un límite, o un punto de parada."""
        assert self._gen is not None
        try:
            while True:
                kind, data = next(self._gen)
                if kind == "limite":
                    done, partial = data
                    self._flush(partial)
                    dg = Diagnostic("D-LIM-EVOL", f"presupuesto de {self.ctl.budget} evoluciones agotado; situación no "
                                    "estabilizada; τ sin cambios", evidence={"tiempoContexto": str(self._stim.time)})
                    self.diagnostics.append(dg)
                    self._log("limite", timeUs=str(self._stim.time), evolutions=done, diagnostics=[dg.to_dict()],
                              stabilized=False)
                    self.status = "pausada-recorrido"
                    self._work = {"phase": "no-estabilizado"}
                    return
                if kind == "propuesta":
                    k, fire = data
                    if any(self.breakpoints.get(t) == "antes" for t in fire) and self._work != {"bp": k}:
                        self._work = {"bp": k, "proposed": fire}
                        self.status = "pausada-recorrido"
                        return
                if kind == "aplicada":
                    self._work = {"last": data}
                    if stop_after_evolution or any(self.breakpoints.get(t) == "despues" for t in data["cleared"]):
                        self.status = "pausada-recorrido"
                        return
        except StopIteration as stop:
            out: Outcome = stop.value
            self._flush(out.records)
            self._gen = None
            if out.status == "estable":
                self.z = out.state
                if self.z.contexts % SNAPSHOT_EVERY == 0:
                    self._snapshot_record()
                self.status = "pausada-estable"
            else:
                self.diagnostics.append(out.diagnostic)
                self.status = "error"

    def _flush(self, records: list[dict[str, Any]]) -> None:
        for r in records[self._flushed:]:
            r = dict(r)
            self._log(r.pop("kind"), contextRef=f"{self.run_id}:{self.z.contexts + 1}", **r)
        self._flushed = len(records)

    def step_external(self) -> None:
        """Avanzar un evento externo: el siguiente hecho y su cierre causal completo."""
        if self.status == "pausada-recorrido":
            self.status = "ejecutando"
            self._pump()
            return
        if self._open():
            self._pump()

    def step_evolution(self) -> None:
        """Avanzar una evolución simultánea completa (microavance)."""
        if self.status == "pausada-estable":
            if not self._open():
                return
        elif self.status == "pausada-recorrido":
            self.status = "ejecutando"
        else:
            raise RuntimeError(f"operación no disponible en estado {self.status}")
        self._pump(stop_after_evolution=True)

    def run_to_stable(self) -> None:
        if self.status == "pausada-recorrido":
            self.status = "ejecutando"
            self._pump()

    def run(self) -> None:
        """Ejecuta hasta finalizar, pausar por punto de parada o detenerse por diagnóstico."""
        while True:
            if self.status == "pausada-recorrido":
                self.run_to_stable()
                if self.status != "pausada-estable":
                    return
            if self.status != "pausada-estable":
                return
            if not self._open():
                return
            self._pump()
            if self.status != "pausada-estable":
                return

    def advance_to(self, t: int) -> None:
        """Procesa todos los hechos anteriores y en t; se detiene antes si hay error o interrupción."""
        while self.status == "pausada-estable":
            nxt = self.next_stimulus()
            if nxt is None or (isinstance(nxt, Stimulus) and nxt.time > t):
                break
            self.step_external()
        if self.status == "pausada-estable" and self.z.time < t:
            self.z.time = t  # avance de reloj sin hechos: no cambia situación ni valores

    def extend_budget(self, budget: int) -> None:
        self.ctl.budget = budget
        self._log("control", timeUs=str(self.z.time), action="ampliar-presupuesto", budget=budget)
        self.trace.header["limits"]["evolutionBudget"] = budget

    # -- entradas manuales e intervenciones
    def manual_input(self, changes: dict[str, Value]) -> Batch:
        if self.status != "pausada-estable":
            raise RuntimeError("las entradas manuales se admiten en pausa estable")
        at = self.z.time
        used = [b.ordinal for b in self.batches if b.time == at]
        b = Batch(f"manual-{len(self.trace.records) + 1}", at, (max(used) + 1) if used else 0,
                  tuple(sorted(changes.items())), "manual")
        for vid in changes:
            if self.cm.variables[vid].role != "input":
                raise DiagnosticError(Diagnostic("D-ESCRITURA-ROL", f"{vid} no es entrada", element=vid))
        idx = next((i for i, x in enumerate(self.batches) if i >= self.z.next_batch and (x.time, x.ordinal) > (b.time, b.ordinal)),
                   len(self.batches))
        self.batches.insert(idx, b)
        self._log("entrada-manual", timeUs=str(at), batch=b.to_dict(self.cm))
        return b

    def debug_set(self, vid: str, value: Value, reason: str, author: str = "local") -> "Session":
        """Intervención E (REQ-SIM-07): solo en pausa estable; crea una rama auditable."""
        if self.status != "pausada-estable":
            raise RuntimeError("la intervención de depuración exige pausa estable")
        var = self.cm.variables[vid]
        if var.role == "input" or vid in self.cm.continuous_by_target:
            raise DiagnosticError(Diagnostic("D-ESCRITURA-ROL", "solo se intervienen memorias internas/memorizadas", element=vid))
        branch = Session(self.cm, self.scenario, self.ctl.budget, f"{self.run_id}.b{len(self.trace.records)}",
                         self.pending(), parent=f"{self.run_id}@{len(self.trace.records)}")
        z = self.z.copy()
        before = z.values[vid]
        z.values[vid] = check_fits(var.type, value)
        z.origin = "intervenido"
        z.next_batch = 0
        compute_outputs(self.cm, z)
        branch.z = z
        branch._log("intervencion", timeUs=str(z.time), target=vid, before=_fmt(self.cm, vid, before),
                    after=_fmt(self.cm, vid, z.values[vid]), reason=reason, author=author)
        branch._snapshot_record()
        branch.status = "pausada-estable"
        return branch

    def stop(self, reason: str) -> None:
        self._log("estable" if self.status == "pausada-estable" else "fallo", timeUs=str(self.z.time if self.z else 0),
                  reason=f"detenida: {reason}")
        self.status = "detenida"

    def close_trace(self) -> dict[str, Any]:
        completion = {"finalizada": "completa", "detenida": "detenida"}.get(self.status, self.status)
        return self.trace.close(completion, f"{self.run_id}:{self.z.contexts if self.z else 0}")

    # -- observación pura (REQ-SIM-03, REQ-SIM-06)
    def observe(self) -> dict[str, Any]:
        z = self.z
        env = _Env(self.cm, z, None)
        trans = {}
        for t in sorted(self.cm.transitions.values(), key=lambda t: t.id):
            validated = t.pre <= z.situation
            rec = bool(ex.evaluate(self.cm.exprs[t.cond].node, env))
            trans[t.id] = {"preActivity": {p: p in z.situation for p in sorted(t.pre)}, "validated": validated,
                           "receptivity": rec, "fireable": validated and rec}
        obs = {"status": self.status, "timeUs": str(z.time), "situation": sorted(z.situation),
               "steps": {s.id: {"active": s.id in z.situation, "initial": s.initial, "partial": s.partial}
                         for s in sorted(self.cm.steps.values(), key=lambda s: s.id)},
               "transitions": trans,
               "outputs": {k: {"value": v, "mode": "continua", "contributors": z.contributors.get(k, [])}
                           for k, v in sorted(z.outputs.items())},
               "values": {k: _fmt(self.cm, k, v) for k, v in sorted(z.values.items())},
               "temporal": {k: v.to_dict() for k, v in sorted(z.temporal.items())}}
        if self.status == "pausada-recorrido" and self._work and "last" in self._work:
            obs["recorrido"] = {"virtualSituation": self._work["last"]["situation"], "note": "situación virtual, no efectiva"}
        return obs

    # -- instantáneas (REQ-SIM-04, REQ-DAT-04)
    def snapshot(self, snapshot_id: str) -> dict[str, Any]:
        from .canonical import digest
        if self.status not in ("pausada-estable", "finalizada", "detenida") or self.z is None:
            raise DiagnosticError(Diagnostic("D-INSTANTANEA-FASE", f"no se exporta un estado en fase «{self.status}»: "
                                             "el perfil no admite instantáneas exactas dentro de un recorrido"))
        body = {"family": "snapshot", "formatVersion": "0.1", "id": snapshot_id, "modelRevision": self.cm.revision,
                "semanticProfile": {"id": PROFILE_ID, "version": PROFILE_VERSION}, "scenarioId": self.scenario.id,
                "runId": self.run_id, "state": self.z.to_dict(self.cm, self.pending())}
        body["integrity"] = {"projection": "file", "digest": digest(body)}
        self._log("instantanea", timeUs=str(self.z.time), snapshot=body["state"], snapshotId=snapshot_id)
        return body

    @classmethod
    def restore(cls, cm: CompiledModel, scenario: Scenario, snap: dict[str, Any], run_id: str = "run-r") -> "Session":
        from .canonical import digest
        prof = snap.get("semanticProfile", {})
        if (snap.get("family") != "snapshot" or snap.get("modelRevision") != cm.revision
                or prof != {"id": PROFILE_ID, "version": PROFILE_VERSION} or snap.get("scenarioId") != scenario.id):
            raise DiagnosticError(Diagnostic("D-INSTANTANEA-INCOMPATIBLE", "revisión, perfil o escenario distintos; "
                                             "no se modifica ninguna sesión",
                                             evidence={"revision": str(snap.get("modelRevision")), "perfil": str(prof)}))
        body = {k: v for k, v in snap.items() if k != "integrity"}
        if snap.get("integrity", {}).get("digest") != digest(body):
            raise DiagnosticError(Diagnostic("D-INTEGRIDAD", "digest de la instantánea no coincide"))
        z, pending = state_from_dict(cm, snap["state"])
        z.origin = "restaurado"
        z.next_batch = 0  # los lotes pendientes viajan completos en la instantánea
        session = cls(cm, scenario, run_id=run_id, batches=pending, parent=snap.get("runId"))
        session.z = z
        session._log("inicio", timeUs=str(z.time), origin="restaurado", situation=sorted(z.situation),
                     outputs=dict(sorted(z.outputs.items())), fromSnapshot=snap["id"])
        session.status = "pausada-estable"
        return session

    def restart(self, run_id: str) -> "Session":
        """Nueva ejecución con el escenario inicial; la traza anterior se conserva en esta sesión."""
        s = Session(self.cm, self.scenario, self.ctl.budget, run_id, parent=self.run_id)
        s.start()
        return s
