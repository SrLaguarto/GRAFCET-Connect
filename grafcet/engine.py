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
from .model import Action, CompiledModel, TemporalSpec, constant_value
from .profile import blocked, normalize_options, profile_ref
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
    """Entorno de evaluación. `options` aplica las lecturas 8.1 y 8.2; `before`/`written` dan, para las variables
    asignadas en el instante, el valor de antes del instante (lecturas 2.3 B y 2.5 B)."""

    def __init__(self, cm: CompiledModel, w: State, events: dict[str, bool] | None,
                 options: dict[str, str] | None = None, before: dict[str, Value] | None = None,
                 written: Any = None) -> None:
        self.cm, self.w, self.events = cm, w, events or {}
        self.options = options or normalize_options(None)
        self.before, self.written = before, written
        self._computing: set[str] = set()

    def var(self, vid: str) -> Value:
        if vid in self.cm.continuous_by_target:  # solo admitido con la lectura 8.2 B o C
            if self.options["8.2"] == "C" and vid not in self._computing:
                self._computing.add(vid)
                try:
                    return any(a.step in self.w.situation and bool(ex.evaluate(self.cm.exprs[a.cond].node, self))
                               for a in self.cm.continuous_by_target[vid])
                finally:
                    self._computing.discard(vid)
            return self.w.outputs.get(vid, False)
        if self.before is not None and self.written is not None and vid in self.written:
            return self.before[vid]
        return self.w.values[vid]

    def active(self, sid: str) -> bool:
        return sid in self.w.situation

    def active_partial(self, pid: str) -> bool:
        steps = set(self.cm.partials[pid]["steps"])
        if self.options["8.1"] == "A":  # 8.1 A: también las etapas de los parciales hijos
            pending = list(self.cm.partials[pid]["children"])
            while pending:
                child = pending.pop()
                steps |= self.cm.partials[child]["steps"]
                pending.extend(self.cm.partials[child]["children"])
        return bool(steps & self.w.situation)

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
        super().__init__(cm, State(frozenset(), {}, {}, {}, {}, {}, 0, 0, 0), None)
        self.values = values

    def var(self, vid: str) -> Value:
        return self.values[vid]


# --- Contexto causal -----------------------------------------------------------------

@dataclass
class Stimulus:
    kind: str  # inicio | lote | vencimiento (un lote puede llevar vencimientos simultáneos: lectura 4.3 A)
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
    options: dict[str, str] = field(default_factory=normalize_options)  # lecturas elegidas (P-IMP-15, P-IMP-21)


@dataclass
class Outcome:
    status: str  # estable | fallo
    state: State | None
    records: list[dict[str, Any]] = field(default_factory=list)
    diagnostic: Diagnostic | None = None


def _start_on(st: TState, spec: TemporalSpec, now: int) -> None:
    if spec.d1 == 0:  # lectura 4.4 A: el retardo cero equivale a la condición
        st.phase, st.start, st.deadline = "on", now, None
    else:
        st.phase, st.start = "on_pending", now
        st.deadline = now + spec.d1 if now + spec.d1 <= MAX_US else None


def _base_change(st: TState, spec: TemporalSpec, new: bool, now: int, element: str, rebound: str = "detener") -> None:
    if new == st.base:
        return
    st.base = new
    if new:
        if st.phase == "off_pending":
            if rebound == "detener":
                raise Blocked(blocked("temporal.coincidencias", "rebote: la base vuelve a ser verdadera durante el "
                                      "retardo de desconexión (cancelar o mantener)", element))
            if rebound == "A":  # 4.2 A: sigue verdadera sin interrupción
                st.phase, st.deadline = "on", None
            return  # 4.2 B: se mantiene el plazo; al vencer, vuelve a contar el retardo de conexión
        if st.phase == "inactive":
            _start_on(st, spec, now)
    elif st.phase == "on_pending":
        st.phase, st.start, st.deadline = "inactive", None, None
    elif st.phase == "on":
        if spec.d2 == 0:
            st.phase, st.start, st.deadline = "inactive", None, None
        else:
            st.phase, st.start = "off_pending", now
            st.deadline = now + spec.d2 if now + spec.d2 <= MAX_US else None


def _expire(st: TState, now: int, spec: TemporalSpec | None = None) -> None:
    if st.deadline == now:
        if st.phase == "on_pending":
            st.phase, st.deadline = "on", None
        elif st.phase == "off_pending":
            st.phase, st.start, st.deadline = "inactive", None, None
            if st.base and spec is not None:  # 4.2 B: la base volvió durante la desconexión
                _start_on(st, spec, now)


def compute_outputs(cm: CompiledModel, w: State, options: dict[str, str] | None = None,
                    before: dict[str, Value] | None = None, written: Any = None) -> None:
    """Salida continua = disyunción de contribuciones de la situación efectiva (REQ-ACT-01). Con la lectura
    2.5 B, las memorias asignadas en el instante se leen con su valor de antes del instante."""
    env = _Env(cm, w, None, options, before, written)
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


def _restart_duration(cm: CompiledModel, w: State, sid: str) -> None:
    """Lectura 3.2 B: la duración de la etapa vuelve a empezar."""
    w.since[sid] = w.time
    for key, spec in cm.temporals.items():
        if spec.base_kind == "active" and spec.base_step == sid:
            st = TState(base=True)
            _start_on(st, spec, w.time)
            w.temporal[key] = st


def run_context(cm: CompiledModel, z: State, stim: Stimulus, ctl: Control
                ) -> Generator[tuple[str, Any], None, Outcome]:
    """Procesa un estímulo hasta su cierre causal. Produce ("propuesta", E), ("aplicada", registro) y
    ("limite", k); devuelve el resultado. El estado z no se modifica: se trabaja sobre una copia."""
    o = ctl.options
    w = z.copy()
    w.time = stim.time
    records: list[dict[str, Any]] = []
    prior_s = z.situation
    events: dict[str, bool] = {}
    fire: list[str] = []
    try:
        # 1. Aplicar el estímulo
        changed: dict[str, Any] = {}
        if stim.kind == "inicio":
            pass  # situación inicial ya fijada; no se inventan flancos de entrada al leer valores iniciales
        elif stim.kind == "lote":
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
                                 w.time, spec.expr, o["4.2"])
        for key in stim.expiring:  # vencimientos (también los que van junto a un lote: lectura 4.3 A)
            if key in w.temporal:
                _expire(w.temporal[key], w.time, cm.temporals[key])
        if stim.kind != "inicio":
            records.append({"kind": "contexto", "timeUs": str(w.time), "stimulus": stim.kind,
                            "batch": stim.batch.id if stim.batch else None,
                            "batchOrdinal": stim.batch.ordinal if stim.batch else None,
                            "origin": stim.batch.origin if stim.batch else "vencimiento",
                            "inputChanges": changed, "expiring": sorted(stim.expiring),
                            "events": sorted(k for k, v in events.items() if v)})
        present = {k for k, v in events.items() if v}
        written: dict[str, tuple[Value, list[str]]] = {}
        deact_ctx: set[str] = set()
        act_ctx: set[str] = set(prior_s) if stim.kind == "inicio" else set()
        hypotheses: list[dict[str, Any]] = []  # decisiones tomadas bajo una lectura elegida

        def apply(proposals: list[Action], env: _Env) -> list[dict[str, Any]]:
            """Asignaciones memorizadas de una evolución (REQ-ACT-02, REQ-ACT-03; lecturas 2.1, 2.2 y 2.4).
            Se evalúan todas con los valores anteriores a esta evolución y después se escriben."""
            by_target: dict[str, list[Action]] = {}
            for a in sorted(proposals, key=lambda a: a.id):
                by_target.setdefault(a.target, []).append(a)
            if o["2.2"] == "B":  # dependencia cruzada entre asignaciones simultáneas
                for a in proposals:
                    cross = cm.exprs[a.value].support.vars & {b.target for b in proposals if b.target != a.target}
                    if cross:
                        raise DiagnosticError(Diagnostic(
                            "D-DEPENDENCIA-CRUZADA", f"{a.id} lee {sorted(cross)}, que otra acción escribe en la misma "
                            "evolución", element=a.id, evidence={"contexto": str(w.time)}))
            results: dict[str, Value] = {}
            for target, acts in by_target.items():
                values = [ex.evaluate(cm.exprs[a.value].node, env) for a in acts]
                if len(acts) > 1:
                    consts = {constant_value(cm.exprs[a.value]) for a in acts}
                    same_constant = None not in consts and len(consts) == 1
                    if o["2.1"] == "B" and not same_constant:  # se acumulan, una detrás de otra
                        saved, cur = w.values[target], w.values[target]
                        try:
                            for a in acts:
                                w.values[target] = cur
                                cur = ex.evaluate(cm.exprs[a.value].node, env)
                        finally:
                            w.values[target] = saved
                        values = [cur]
                    elif not same_constant and (o["2.1"] == "C" or len(set(values)) > 1):
                        raise DiagnosticError(Diagnostic(
                            "D-ESCRITURA-CONFLICTO", f"varias asignaciones simultáneas sobre {target}", element=target,
                            evidence={"propuestas": "; ".join(f"{a.id}={_fmt(cm, target, v)}" for a, v in zip(acts, values)),
                                      "contexto": str(w.time)}))
                var = cm.variables[target]
                val = check_fits(var.type, values[-1])
                if not in_domain(var.type, var.domain, val):
                    raise DiagnosticError(Diagnostic("D-NUM", f"{target} fuera de dominio", element=acts[0].id,
                                                     evidence={"valor": str(val)}))
                results[target] = val
            out = []
            for target, val in sorted(results.items()):
                authors = [a.id for a in by_target[target]]
                entry = {"target": target, "value": _fmt(cm, target, val), "authors": authors}
                if target in written and written[target][0] != val:
                    if o["2.4"] == "B":
                        raise DiagnosticError(Diagnostic(
                            "D-ESCRITURA-CONFLICTO", f"asignaciones sucesivas distintas sobre {target} en el mismo instante",
                            element=target, evidence={"propuestas": f"{_fmt(cm, target, written[target][0])} y "
                                                                    f"{_fmt(cm, target, val)}", "contexto": str(w.time)}))
                    entry["previous"] = _fmt(cm, target, written[target][0])  # 2.4 A: vale la última del recorrido
                written[target] = (val, written.get(target, (val, []))[1] + authors)
                w.values[target] = val
                out.append(entry)
            return out

        if stim.kind == "inicio" and o["1.1"] == "A":
            # 1.1 A: las acciones «al activar» de las etapas iniciales se ejecutan al arrancar (evolución 0)
            initial_actions = [a for sid in sorted(prior_s) for a in cm.stored_by_step.get((sid, "activation"), [])]
            if initial_actions:
                assignments = apply(initial_actions, _Env(cm, w, None, o))
                rec0 = {"kind": "evolucion", "timeUs": str(w.time), "evolutionIndex": 0, "validated": [], "receptivity": {},
                        "cleared": [], "deactivated": [], "activated": sorted(prior_s), "permanent": [],
                        "situation": sorted(w.situation), "assignments": assignments}
                records.append(rec0)
                yield ("aplicada", rec0)
        done_event_actions: list[Action] = []
        # Duración de cada etapa antes de su primera salida en este contexto (P-IMP-18)
        before_exit: dict[str, tuple[int | None, dict[str, TState]]] = {}
        old = z.values if o["2.3"] == "B" else None  # 2.3 B: las receptividades ven el valor de antes del instante
        k = 0
        while True:
            k += 1
            while k > ctl.budget:
                yield ("limite", (k - 1, list(records)))
                if ctl.abort:
                    return Outcome("fallo", None, records, Diagnostic("D-LIM-EVOL", "contexto abandonado tras el límite"))
            if stim.kind == "inicio" and o["1.2"] == "B":
                break  # 1.2 B: la situación inicial espera al primer cambio de entradas
            s = w.situation
            env = _Env(cm, w, events, o)
            renv = _Env(cm, w, events, o, old, written)
            renv0 = _Env(cm, w, None, o, old, written)
            fire: list[str] = []
            info: dict[str, Any] = {}
            for t in sorted(cm.transitions.values(), key=lambda t: t.id):
                if not t.pre <= s or (not t.pre and not t.post):  # 6.4 B: sin etapas, sin efecto
                    continue
                e = cm.exprs[t.cond]
                val = bool(ex.evaluate(e.node, renv))  # 2.3 A: ve los valores asignados antes en el mismo instante
                if k >= 2 and any(n.key in present for n in e.support.events):
                    without_event = bool(ex.evaluate(e.node, renv0))
                    if val != without_event:
                        if not t.pre:
                            if o["6.3"] == "detener":
                                raise Blocked(blocked("transiciones.fuente-repeticion", "transición fuente: ¿se repite "
                                                      "el mismo evento en evoluciones posteriores del contexto?", t.id))
                            val = without_event  # 6.3 A: una sola vez por flanco
                        else:
                            reading = o["U-03"]
                            if reading == "detener":
                                raise Blocked(blocked("eventos.recorrido", "transición que sigue validada o se valida "
                                                      "durante el recorrido causado por el propio evento", t.id))
                            if reading == "situacion-anterior":
                                val = without_event
                            hypotheses.append({"question": "U-03", "reading": reading, "transition": t.id,
                                               "evolutionIndex": k, "receptivity": val})
                info[t.id] = val
                if val and not t.pre and t.post <= s and not e.support.events:
                    continue  # 6.2 B: la imposición continua no cambia nada si sus etapas ya están activas
                if val:
                    fire.append(t.id)
            if stim.kind == "inicio" and o["1.2"] == "C" and fire:
                raise DiagnosticError(Diagnostic("D-FORMATO", f"situación inicial inestable ({', '.join(fire)} "
                                                 "franqueables al arrancar): no se admite (lectura 1.2 C)"))
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
            restart: list[str] = []
            for sid in sorted(permanent | reactivated):  # U-04 (lecturas 3.1, 3.2, 3.3)
                acts_on = cm.stored_by_step.get((sid, "activation"), [])
                acts_off = cm.stored_by_step.get((sid, "deactivation"), [])
                timed = [x for x in cm.step_dependents.get(sid, ()) if x.startswith(("condición temporal", "acción limitada"))]
                if sid in permanent:
                    if (acts_on or acts_off) and o["3.1"] == "detener":
                        raise Blocked(blocked("permanencia.efectos", "permanencia activa (activada y desactivada a la "
                                              f"vez) con acciones {sorted(a.id for a in acts_on + acts_off)}", sid))
                    if o["3.1"] == "B":
                        proposals.extend(acts_on + acts_off)
                elif acts_on:
                    if o["3.3"] == "detener":
                        raise Blocked(blocked("permanencia.efectos", "activación de una etapa ya activa no incluida en D "
                                              f"(H-05) con acciones {sorted(a.id for a in acts_on)}", sid))
                    if o["3.3"] == "B":
                        proposals.extend(acts_on)
                if timed:
                    if o["3.2"] == "detener":
                        raise Blocked(blocked("permanencia.efectos", f"permanencia o reactivación con {timed}", sid))
                    if o["3.2"] == "B":
                        restart.append(sid)
            # Salida y reentrada en el mismo instante: el recorrido no ocupa tiempo, así que la duración de la etapa no
            # se interrumpe (decisión del responsable de producto que cierra H-09, P-IMP-18)
            reentered = activated & deact_ctx
            for a in list(done_event_actions):  # U-03: acción por evento en etapa que sale con ese evento (5.2)
                if a.step in deactivated:
                    if o["5.2"] == "detener":
                        raise Blocked(blocked("eventos.recorrido", f"acción por evento {a.id} en etapa desactivada por el "
                                              "mismo contexto (U-03/U-05)", a.step))
                    if o["5.2"] == "B" and k == 1 and a in proposals:
                        proposals.remove(a)
                    done_event_actions.remove(a)
            for a in cm.event_actions:  # U-03: acción por evento en etapa que entra con ese evento (5.3)
                if a.step in activated and any(n.key in present for n in cm.exprs[a.trigger_expr].support.events):
                    if o["5.3"] == "detener":
                        raise Blocked(blocked("eventos.recorrido", f"acción por evento {a.id} en etapa activada durante "
                                              "el recorrido de ese evento", a.step))
                    if o["5.3"] == "B" and bool(ex.evaluate(cm.exprs[a.trigger_expr].node, env)):
                        proposals.append(a)
            for sid in sorted(activated):
                proposals.extend(cm.stored_by_step.get((sid, "activation"), []))
            for sid in sorted(deactivated):
                proposals.extend(cm.stored_by_step.get((sid, "deactivation"), []))
            assignments = apply(proposals, env)
            w.situation = new_s
            for sid in sorted(deactivated):
                if sid not in before_exit:
                    before_exit[sid] = (w.since.get(sid), {key: replace(w.temporal[key]) for key, spec in cm.temporals.items()
                                                           if spec.base_kind == "active" and spec.base_step == sid})
            for sid in activated:
                w.since[sid] = w.time
            for sid in deactivated:
                w.since.pop(sid, None)
            for key, spec in sorted(cm.temporals.items()):
                if spec.base_kind == "active" and spec.base_step in (activated | deactivated) - reentered:
                    _base_change(w.temporal[key], spec, spec.base_step in new_s, w.time, spec.base_step, o["4.2"])
            for sid in sorted(reentered):
                since, states = before_exit[sid]
                if since is not None:
                    w.since[sid] = since
                for key, st in states.items():
                    w.temporal[key] = replace(st)
            for sid in restart:
                _restart_duration(cm, w, sid)
            deact_ctx |= deactivated
            act_ctx |= activated
            rec = {"kind": "evolucion", "timeUs": str(w.time), "evolutionIndex": k,
                   "validated": sorted(info), "receptivity": dict(sorted(info.items())), "cleared": sorted(fire),
                   "deactivated": sorted(deactivated), "activated": sorted(activated), "permanent": sorted(permanent),
                   "situation": sorted(new_s), "assignments": assignments}
            if reentered:
                rec["durationKept"] = sorted(reentered)
            if restart:
                rec["durationRestarted"] = sorted(restart)
            records.append(rec)
            yield ("aplicada", rec)
        compute_outputs(cm, w, o, z.values if o["2.5"] == "B" else None, written)
        w.contexts += 1
        w.phase = "estable"
        if stim.kind == "lote":
            w.next_batch += 1
        # Etapas inestables: activas solo durante el recorrido (al arrancar, también las iniciales que se abandonan)
        prior_for_virtual = frozenset() if stim.kind == "inicio" else prior_s
        virtual = sorted((act_ctx | deact_ctx) - w.situation - prior_for_virtual) if (act_ctx or deact_ctx) else []
        closing = {"kind": "estable", "timeUs": str(w.time), "situation": sorted(w.situation),
                   "virtualSteps": virtual,
                   "outputs": {k: v for k, v in sorted(w.outputs.items())},
                   "values": {k: _fmt(cm, k, v) for k, v in sorted(w.values.items()) if v != z.values.get(k)}}
        if hypotheses:
            closing["hypotheses"] = hypotheses
        records.append(closing)
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


def run_full(cm: CompiledModel, z: State, stim: Stimulus, budget: int = DEFAULT_BUDGET,
             options: dict[str, str] | None = None) -> Outcome:
    gen = run_context(cm, z, stim, Control(budget, abort=True, options=normalize_options(options)))
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


def check_simultaneous_expiries(cm: CompiledModel, z: State, stim: Stimulus, budget: int,
                                options: dict[str, str] | None = None) -> Diagnostic | None:
    """Varios vencimientos en el mismo instante: se aceptan solo si el resultado no depende del orden (U-06)."""
    keys = stim.expiring
    if len(keys) < 2:
        return None
    if len(keys) > 4:
        return blocked("temporal.coincidencias", f"{len(keys)} vencimientos simultáneos: demasiados para comparar órdenes")
    ref = run_full(cm, z, stim, budget, options)
    for perm in itertools.permutations(keys):
        cur: State | None = z
        for key in perm:
            out = run_full(cm, cur, Stimulus("vencimiento", stim.time, None, (key,)), budget, options)
            if out.status != "estable":
                cur = None
                break
            cur = out.state
        if ref.status != "estable" or cur is None or not cur.equivalent(ref.state):
            return blocked("temporal.coincidencias", "vencimientos simultáneos cuyo resultado depende del orden "
                           f"({', '.join(perm)})")
    return None


# --- Inicialización ------------------------------------------------------------------

def initial_state(cm: CompiledModel, scenario: Scenario, options: dict[str, str] | None = None
                  ) -> tuple[State | None, list[Diagnostic]]:
    """Situación inicial elegida (REQ-SEM-01), antes de su cierre causal en τ=0.

    Respuestas de la hoja 08 (U-09): las memorizadas empiezan en 0 (1.5); las condiciones temporales que ya son
    verdaderas al arrancar, sobre la actividad de una etapa inicial (1.4) o sobre entradas (1.3), cuentan desde
    τ=0. Las acciones «al activar» de las etapas iniciales (1.1) y las transiciones ya franqueables (1.2) se
    resuelven en el contexto de inicio (run_context con estímulo «inicio»). El arranque vacío sigue abierto (U-07)
    salvo que se elija una lectura de 6.1; 1.3 B y 1.5 B son alternativas para el comparador (P-IMP-21).
    """
    o = normalize_options(options)
    s0 = cm.initial_situation()
    if not s0:
        if o["6.1"] == "detener":
            return None, [blocked("situacion.inicial.vacia", "no hay etapas iniciales; no se inventa ninguna")]
        if o["6.1"] == "A":
            return None, [Diagnostic("D-FORMATO", "grafcet sin etapas iniciales: no se admite (lectura 6.1 A)")]
    values: dict[str, Value] = {}
    for v in cm.variables.values():
        if v.id in cm.continuous_by_target:
            continue
        if v.role == "input":
            if v.id in scenario.initial:
                values[v.id] = scenario.initial[v.id]
        else:
            values[v.id] = v.initial if o["1.5"] == "B" else zero(v.type)
    w = State(s0, values, {}, {}, {}, {sid: 0 for sid in s0}, 0, 0, 0)
    for key, spec in sorted(cm.temporals.items()):
        if spec.base_kind == "active":
            true_at_start = spec.base_step in s0
        else:
            true_at_start = bool(ex.evaluate(spec.base, _InputEnv(cm, values)))
            if true_at_start and o["1.3"] == "B":  # 1.3 B: hace falta una subida real de la entrada
                w.temporal[key] = TState(base=True)
                continue
        st = TState()
        if true_at_start:
            st.base = True
            _start_on(st, spec, 0)
        w.temporal[key] = st
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
                 run_id: str = "run-1", batches: list[Batch] | None = None, parent: str | None = None,
                 options: dict[str, str] | None = None) -> None:
        self.cm, self.scenario, self.run_id = cm, scenario, run_id
        self.options = normalize_options(options)
        self.ctl = Control(budget, options=self.options)
        self.batches = list(batches if batches is not None else scenario.batches)
        self.trace = Trace({"runId": run_id, "modelRevision": cm.revision, "scenario": scenario.id,
                            "semanticProfile": profile_ref(self.options), "timeUnit": "us",
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
        z, diags = initial_state(self.cm, self.scenario, self.options)
        if z is None:
            self.status, self.diagnostics = "error", diags
            self._log("fallo", timeUs="0", diagnostics=[d.to_dict() for d in diags])
            return diags
        # Cierre causal de la situación inicial en τ=0: acciones al activar y recorrido inicial (hoja 08, 1.1 y 1.2)
        self.z = z
        self._log("inicio", timeUs="0", origin=z.origin, mode="inicio", situation=sorted(z.situation))
        self._stim = Stimulus("inicio", 0)
        self._gen = run_context(self.cm, z, self._stim, self.ctl)
        self._work, self._flushed = None, 0
        self.status = "ejecutando"
        self._pump()
        if self.status == "pausada-estable":
            self._snapshot_record()
            return []
        return self.diagnostics[-1:]

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
            return self._coincidence(nb, nd, tuple(sorted(deadlines[nd])))
        if nb is not None:
            return None if horizon is not None and nb.time > horizon else Stimulus("lote", nb.time, nb)
        return None

    def _coincidence(self, nb: Batch, t: int, keys: tuple[str, ...]) -> Stimulus | Diagnostic:
        """Lote y vencimientos en el mismo instante (U-06). Si el lote cambia la base de un retardo que vence en
        ese instante decide la lectura 4.1; si no, la 4.3. «Detener» sigue siendo el valor por defecto (H-17)."""
        o, z = self.options, self.z
        after = dict(z.values)
        after.update(dict(nb.changes))
        touched = [k for k in keys if k in z.temporal and self.cm.temporals[k].base_kind == "inputs"
                   and bool(ex.evaluate(self.cm.temporals[k].base, _InputEnv(self.cm, after))) != z.temporal[k].base]
        expiry, batch = Stimulus("vencimiento", t, None, keys), Stimulus("lote", t, nb)
        if touched:
            if o["4.1"] == "detener":
                return blocked("temporal.coincidencias", f"el lote {nb.id} cambia la base de {touched} justo cuando "
                               f"vence ({t} µs): no se fija qué va primero")
            return expiry if o["4.1"] == "A" else batch
        if o["4.3"] == "detener":
            return blocked("temporal.coincidencias", f"lote {nb.id} y vencimientos {list(keys)} en el mismo "
                           f"instante {t} µs: no se fija orden de cola")
        together = Stimulus("lote", t, nb, keys)
        if o["4.3"] == "A":
            return together
        if o["4.3"] == "B":
            return expiry
        if o["4.3"] == "C":
            return batch
        # 4.3 D: se comparan los tres órdenes y solo se detiene si el resultado depende del orden
        results = [self._chain(together), self._chain(expiry, batch), self._chain(batch, expiry)]
        if all(r is not None for r in results) and all(r.equivalent(results[0]) for r in results[1:]):
            return together
        return blocked("temporal.coincidencias", f"lote {nb.id} y vencimientos {list(keys)} en {t} µs: el resultado "
                       "depende del orden (lectura 4.3 D)")

    def _chain(self, *stims: Stimulus) -> State | None:
        z: State | None = self.z
        for st in stims:
            if st.kind == "vencimiento":
                st = Stimulus("vencimiento", st.time, None, tuple(k for k in st.expiring
                                                                  if k not in z.temporal or z.temporal[k].deadline == st.time))
                if not st.expiring:
                    continue
            out = run_full(self.cm, z, st, self.ctl.budget, self.options)
            if out.status != "estable":
                return None
            z = out.state
        return z

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
            dg = check_simultaneous_expiries(self.cm, self.z, nxt, self.ctl.budget, self.options)
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
                         self.pending(), parent=f"{self.run_id}@{len(self.trace.records)}", options=self.options)
        z = self.z.copy()
        before = z.values[vid]
        z.values[vid] = check_fits(var.type, value)
        z.origin = "intervenido"
        z.next_batch = 0
        compute_outputs(self.cm, z, self.options)
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
        env = _Env(self.cm, z, None, self.options)
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
                "semanticProfile": profile_ref(self.options), "scenarioId": self.scenario.id,
                "runId": self.run_id, "state": self.z.to_dict(self.cm, self.pending())}
        body["integrity"] = {"projection": "file", "digest": digest(body)}
        self._log("instantanea", timeUs=str(self.z.time), snapshot=body["state"], snapshotId=snapshot_id)
        return body

    @classmethod
    def restore(cls, cm: CompiledModel, scenario: Scenario, snap: dict[str, Any], run_id: str = "run-r",
                options: dict[str, str] | None = None) -> "Session":
        """Restaura solo con el mismo perfil efectivo, incluidas las lecturas elegidas (P-IMP-15)."""
        from .canonical import digest
        prof = snap.get("semanticProfile", {})
        options = normalize_options(options)
        if (snap.get("family") != "snapshot" or snap.get("modelRevision") != cm.revision
                or prof != profile_ref(options) or snap.get("scenarioId") != scenario.id):
            raise DiagnosticError(Diagnostic("D-INSTANTANEA-INCOMPATIBLE", "revisión, perfil (o lecturas elegidas) o escenario distintos; "
                                             "no se modifica ninguna sesión",
                                             evidence={"revision": str(snap.get("modelRevision")), "perfil": str(prof)}))
        body = {k: v for k, v in snap.items() if k != "integrity"}
        if snap.get("integrity", {}).get("digest") != digest(body):
            raise DiagnosticError(Diagnostic("D-INTEGRIDAD", "digest de la instantánea no coincide"))
        z, pending = state_from_dict(cm, snap["state"])
        z.origin = "restaurado"
        z.next_batch = 0  # los lotes pendientes viajan completos en la instantánea
        session = cls(cm, scenario, run_id=run_id, batches=pending, parent=snap.get("runId"), options=options)
        session.z = z
        session._log("inicio", timeUs=str(z.time), origin="restaurado", situation=sorted(z.situation),
                     outputs=dict(sorted(z.outputs.items())), fromSnapshot=snap["id"])
        session.status = "pausada-estable"
        return session

    def restart(self, run_id: str) -> "Session":
        """Nueva ejecución con el escenario inicial; la traza anterior se conserva en esta sesión."""
        s = Session(self.cm, self.scenario, self.ctl.budget, run_id, parent=self.run_id, options=self.options)
        s.start()
        return s
