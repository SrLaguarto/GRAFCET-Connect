"""Ejecución jerárquica: macroetapas, encapsulación y forzado (documento 06; REQ-JER-02, REQ-JER-04, REQ-JER-05).

Lo que fija el documento 06 como interpretación I (provisional por U-01):
- Macroetapa (LOC tabla 11): llegar a M activa su etapa de entrada E; las transiciones posteriores de M exigen su
  etapa de salida S y la desactivan. XM = alguna etapa de la expansión activa. Se resuelve al compilar: en las
  transiciones, M como siguiente es E y M como precedente es S («relación expandida»).
- Encapsulación (LOC §7.4): al activarse la encapsulante se activan las etapas marcadas con enlace de activación de
  cada recinto (en el arranque rigen las iniciales); al desactivarse, se desactiva todo su contenido.
- Forzado (LOC tabla 9): mientras su origen está activo, la orden impone una situación al parcial destino, que no
  evoluciona ordinariamente. Formas: explícita, actual (captura al entrar en vigor), vacía e inicial. Dos órdenes
  vigentes con igual destino y objetivo distinto: D-FORZADO-CONFLICTO, sin prioridad por ID.

Lo que no fija (U-08, cuestiones 7.2–7.8 de la hoja 08): cada caso tiene una lectura seleccionable y, mientras el
responsable no la elija, se detiene con D-SEM-PENDIENTE. 3.4 (permanencia de la encapsulante) está decidida.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .diagnostics import Diagnostic, DiagnosticError
from .profile import blocked


@dataclass(frozen=True)
class MacroInfo:
    id: str
    partial: str  # parcial que contiene la macroetapa
    expansion: str  # parcial de la expansión
    entry: str
    exit: str


@dataclass(frozen=True)
class EnclosureInfo:
    id: str
    owner: str  # etapa encapsulante
    partial: str  # recinto
    activation: frozenset[str]


@dataclass(frozen=True)
class ForceInfo:
    id: str
    source: str
    target: str  # parcial destino
    kind: str  # explicit | current | empty | initial
    steps: frozenset[str] = frozenset()


@dataclass
class HierarchyInfo:
    macros: dict[str, MacroInfo] = field(default_factory=dict)
    enclosures: dict[str, list[EnclosureInfo]] = field(default_factory=dict)  # por encapsulante
    forces: list[ForceInfo] = field(default_factory=list)
    partial_steps: dict[str, frozenset[str]] = field(default_factory=dict)
    macro_steps: dict[str, frozenset[str]] = field(default_factory=dict)  # expansión, con anidadas
    content: dict[str, frozenset[str]] = field(default_factory=dict)  # todo lo que contiene cada encapsulante
    content_partials: dict[str, frozenset[str]] = field(default_factory=dict)
    exits: dict[str, list[MacroInfo]] = field(default_factory=dict)  # transición → macroetapas de las que sale
    enclosure_owner: dict[str, str] = field(default_factory=dict)  # recinto → encapsulante
    initial: dict[str, frozenset[str]] = field(default_factory=dict)  # parcial → etapas iniciales

    @property
    def active(self) -> bool:
        return bool(self.macros or self.enclosures or self.forces)


def build(partial_steps: dict[str, frozenset[str]], initial: dict[str, frozenset[str]], macros: list[dict[str, Any]],
          expansions: list[dict[str, Any]], enclosures: list[dict[str, Any]], forces: list[dict[str, Any]],
          kinds: dict[str, str]) -> HierarchyInfo:
    """Estructura compilada; se llama solo con una jerarquía ya validada."""
    h = HierarchyInfo(partial_steps=partial_steps, initial=initial)
    exp = {x["id"]: x for x in expansions}
    for m in macros:
        x = exp[m["expansionRef"]]
        h.macros[m["id"]] = MacroInfo(m["id"], m["partialRef"], x["partialRef"], x["entryRef"], x["exitRef"])
    for x in enclosures:
        e = EnclosureInfo(x["id"], x["ownerStepRef"], x["partialRef"], frozenset(x["activationRefs"]))
        h.enclosures.setdefault(e.owner, []).append(e)
        h.enclosure_owner[e.partial] = e.owner
    for f in forces:
        h.forces.append(ForceInfo(f["id"], f["sourceStepRef"], f["targetPartialRef"], f["targetKind"],
                                  frozenset(f.get("targetSteps", []))))
    h.forces.sort(key=lambda f: f.id)
    macros_in = {}
    for m in h.macros.values():
        macros_in.setdefault(m.partial, []).append(m)

    def closure(pid: str, seen: frozenset[str] = frozenset()) -> tuple[frozenset[str], frozenset[str]]:
        """Etapas y parciales de un parcial y de lo que contiene (expansiones y recintos interiores)."""
        if pid in seen:
            return frozenset(), frozenset()
        steps, parts = set(partial_steps.get(pid, ())), {pid}
        for m in macros_in.get(pid, []):
            s, p = closure(m.expansion, seen | {pid})
            steps |= s
            parts |= p
        for sid in partial_steps.get(pid, ()):
            if kinds.get(sid) == "enclosing":
                for e in h.enclosures.get(sid, []):
                    s, p = closure(e.partial, seen | {pid})
                    steps |= s
                    parts |= p
        return frozenset(steps), frozenset(parts)
    for m in h.macros.values():
        h.macro_steps[m.id] = closure(m.expansion)[0]
    for owner, encs in h.enclosures.items():
        steps, parts = set(), set()
        for e in encs:
            s, p = closure(e.partial)
            steps |= s
            parts |= p
        h.content[owner] = frozenset(steps)
        h.content_partials[owner] = frozenset(parts)
    return h


def expand_refs(pre: list[str], post: list[str], macros: dict[str, dict[str, Any]]) -> tuple[set[str], set[str], list[str]]:
    """Relación expandida de una transición: M como siguiente es su entrada; M como precedente, su salida."""
    p = {macros[r]["exit"] if r in macros else r for r in pre}
    q = {macros[r]["entry"] if r in macros else r for r in post}
    return p, q, [r for r in pre if r in macros]


# --- Ejecución ------------------------------------------------------------------------

@dataclass
class Step:
    """Lo que la jerarquía añade a una evolución, para la traza y para las acciones."""
    events: list[dict[str, Any]] = field(default_factory=list)
    forced_on: set[str] = field(default_factory=set)
    forced_off: set[str] = field(default_factory=set)


def _target(h: HierarchyInfo, f: ForceInfo, situation: frozenset[str]) -> frozenset[str]:
    if f.kind == "explicit":
        return f.steps
    if f.kind == "empty":
        return frozenset()
    if f.kind == "initial":
        return h.initial.get(f.target, frozenset())
    return situation & h.partial_steps.get(f.target, frozenset())  # actual: captura


def register(h: HierarchyInfo, forces: dict[str, frozenset[str]], situation: frozenset[str], cm: Any, now: int,
             frozen: dict[str, int], o: dict[str, str], out: Step) -> None:
    """Pone en vigor las órdenes cuyo origen está activo y aún no lo estaban (captura de «actual»)."""
    for f in h.forces:
        if f.source in situation and f.id not in forces:
            forces[f.id] = _target(h, f, situation)
            out.events.append({"order": f.id, "event": "entra", "source": f.source, "target": f.target,
                               "steps": sorted(forces[f.id])})
            if _has_timing(h, cm, f.target) and f.target not in frozen:
                if o["7.3"] == "detener":
                    raise HierarchyBlocked(blocked("jerarquia.forzado-tiempo", f"el parcial forzado {f.target} tiene "
                                           "temporizadores: ¿siguen contando o se congelan? (7.3)", f.id))
                if o["7.3"] == "B":
                    frozen[f.target] = now


def retire(h: HierarchyInfo, forces: dict[str, frozenset[str]], situation: frozenset[str], out: Step,
           unfreeze: Callable[[str], None]) -> None:
    for f in h.forces:
        if f.id in forces and f.source not in situation:
            del forces[f.id]
            out.events.append({"order": f.id, "event": "retira", "source": f.source, "target": f.target})
            if not any(g.target == f.target and g.id in forces for g in h.forces):
                unfreeze(f.target)


def imposed(h: HierarchyInfo, forces: dict[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """Situación impuesta a cada parcial forzado; órdenes coincidentes se agrupan (sin prioridad por ID)."""
    by_target: dict[str, dict[frozenset[str], list[str]]] = {}
    for f in h.forces:
        if f.id in forces:
            by_target.setdefault(f.target, {}).setdefault(forces[f.id], []).append(f.id)
    out = {}
    for g, targets in sorted(by_target.items()):
        if len(targets) > 1:
            raise DiagnosticError(Diagnostic(
                "D-FORZADO-CONFLICTO", f"órdenes vigentes con el mismo destino {g} y objetivo distinto",
                element=g, evidence={"ordenes": "; ".join(f"{', '.join(ids)} → {{{', '.join(sorted(t))}}}"
                                                           for t, ids in sorted(targets.items(), key=lambda kv: kv[1]))}))
        out[g] = next(iter(targets))
    return out


def _has_timing(h: HierarchyInfo, cm: Any, partial: str) -> bool:
    steps = h.partial_steps.get(partial, frozenset())
    return any(ts.base_kind == "active" and ts.base_step in steps for ts in cm.temporals.values()) or \
        any(a.limit_us is not None and a.step in steps for a in cm.actions.values())


class HierarchyBlocked(Exception):
    def __init__(self, diag: Diagnostic) -> None:
        super().__init__(str(diag))
        self.diag = diag


def prune_fire(h: HierarchyInfo, cm: Any, s: frozenset[str], fire: list[str], forces: dict[str, frozenset[str]],
               o: dict[str, str]) -> list[str]:
    """Quita del conjunto propuesto lo que la jerarquía impide (forzado vigente, lecturas 7.2 y 7.6)."""
    forced = {f.target for f in h.forces if f.id in forces}
    fire = [t for t in fire if cm.transitions[t].partial not in forced]
    for _ in range(len(fire) + 1):
        ts = [cm.transitions[t] for t in fire]
        d = frozenset().union(*(t.pre for t in ts)) if ts else frozenset()
        a = frozenset().union(*(t.post for t in ts)) if ts else frozenset()
        new_s = (s - d) | a
        drop: set[str] = set()
        # 7.2: una orden que entra en vigor en esta evolución y un franqueamiento de su destino
        if o["7.2"] != "B":
            for f in h.forces:
                if f.source in new_s and f.id not in forces:
                    inside = [t for t in fire if cm.transitions[t].partial == f.target]
                    if inside and o["7.2"] == "detener":
                        raise HierarchyBlocked(blocked("jerarquia.forzado-momento", f"la orden {f.id} entra en vigor en la "
                                               f"misma evolución en que {f.target} franquea {inside} (7.2, H-18)", f.id))
                    drop |= set(inside)  # 7.2 A: el forzado gana a la evolución del destino
        # 7.6: una transición interior franquea en la evolución en que se desactiva su encapsulante
        for owner, parts in h.content_partials.items():
            if owner in s and owner not in new_s:
                inside = [t for t in fire if cm.transitions[t].partial in parts]
                if inside:
                    if o["7.6"] == "detener":
                        raise HierarchyBlocked(blocked("jerarquia.encapsulacion-coincidencia", f"{owner} se desactiva en la "
                                               f"misma evolución en que franquea {inside} en su interior (7.6)", owner))
                    if o["7.6"] == "A":
                        drop |= set(inside)  # 7.6 A: gana la desactivación
        if not drop:
            return fire
        fire = [t for t in fire if t not in drop]
    return fire


def close(h: HierarchyInfo, cm: Any, s: frozenset[str], fired: list[str], d: frozenset[str], a: frozenset[str],
          new_s: frozenset[str], forces: dict[str, frozenset[str]], frozen: dict[str, int], now: int,
          o: dict[str, str], unfreeze: Callable[[str], None]) -> tuple[frozenset[str], Step]:
    """Cierre jerárquico de una evolución: salidas de macroetapa, encapsulación y forzado."""
    out = Step()
    ns = set(new_s)
    # Salida de una macroetapa con otras ramas de la expansión activas (7.5)
    for tid in fired:
        for m in h.exits.get(tid, []):
            rest = sorted((h.macro_steps[m.id] - {m.exit}) & ns)
            if rest:
                if o["7.5"] == "detener":
                    raise HierarchyBlocked(blocked("jerarquia.macro-ramas", f"se sale de {m.id} con {rest} aún activas en su "
                                           "expansión (7.5)", tid))
                if o["7.5"] == "C":
                    raise DiagnosticError(Diagnostic("D-JERARQUIA-RAMA", f"se sale de {m.id} con {rest} aún activas en "
                                                     "su expansión: error de diseño (lectura 7.5 C)", element=tid))
                if o["7.5"] == "A":
                    ns -= h.macro_steps[m.id]
                    out.events.append({"macro": m.id, "event": "desactiva-expansion", "steps": rest})
    _enclose(h, s, d, a, ns, o, out)
    # Forzado: entra en vigor (7.2 A o «detener» sin coincidencia), se retira y se impone
    retire(h, forces, frozenset(ns), out, unfreeze)
    if o["7.2"] != "B":
        register(h, forces, frozenset(ns), cm, now, frozen, o, out)
    before = frozenset(ns)
    for g, target in imposed(h, forces).items():
        owner = h.enclosure_owner.get(g)
        if owner is not None and owner not in ns and target:
            if o["7.4"] == "detener":
                raise HierarchyBlocked(blocked("jerarquia.forzado-recinto", f"se fuerza el recinto {g} con su encapsulante "
                                       f"{owner} inactiva (7.4)", g))
            if o["7.4"] == "A":
                raise DiagnosticError(Diagnostic("D-FORZADO-RECINTO", f"se fuerza el recinto {g} con su encapsulante "
                                                 f"{owner} inactiva: error de diseño (lectura 7.4 A)", element=g))
            if o["7.4"] == "C":
                continue  # 7.4 C: el forzado se ignora mientras la encapsulante esté inactiva
        if owner is not None and owner in ns and not target:
            raise HierarchyBlocked(blocked("jerarquia.forzado-recinto", f"forzar vacío el recinto {g} con su encapsulante "
                                   f"{owner} activa deja el recinto sin etapas (no preguntado; U-08)", g))
        ns = (ns - h.partial_steps.get(g, frozenset())) | target
    out.forced_on, out.forced_off = set(ns - before), set(before - ns)
    if out.forced_on or out.forced_off:
        # El forzado puede activar o desactivar encapsulantes del destino
        _enclose(h, before, frozenset(out.forced_off), frozenset(out.forced_on), ns, o, out)
    return frozenset(ns), out


def _enclose(h: HierarchyInfo, s: frozenset[str], d: frozenset[str], a: frozenset[str], ns: set[str],
             o: dict[str, str], out: Step) -> None:
    """Encapsulación: activación por enlace de activación y desactivación de todo el contenido."""
    if not h.enclosures:
        return
    for owner in sorted(h.enclosures):
        if owner in s and owner not in ns:  # sale: se desactiva todo su contenido
            gone = sorted(h.content[owner] & ns)
            ns -= h.content[owner]
            if gone:
                out.events.append({"enclosing": owner, "event": "desactiva-contenido", "steps": gone})
        elif owner in d and owner in a:  # permanencia activa de la encapsulante (3.4)
            if o["3.4"] == "detener":
                raise HierarchyBlocked(blocked("jerarquia.encapsulacion-permanencia", f"la encapsulante {owner} se activa y "
                                       "se desactiva a la vez: ¿su contenido se mantiene o se reinicia? (3.4)", owner))
            if o["3.4"] == "B":
                ns -= h.content[owner]
                ns |= _activation(h, owner)
                out.events.append({"enclosing": owner, "event": "reinicia-contenido"})
    for owner in sorted(h.enclosures):
        if owner not in s and owner in ns:  # entra: se activan las etapas con enlace de activación
            on = _activation(h, owner)
            ns |= on
            out.events.append({"enclosing": owner, "event": "activa-contenido", "steps": sorted(on)})


def _activation(h: HierarchyInfo, owner: str) -> set[str]:
    on: set[str] = set()
    pending = [owner]
    while pending:
        cur = pending.pop()
        for e in h.enclosures.get(cur, []):
            for sid in e.activation:
                if sid not in on:
                    on.add(sid)
                    pending.append(sid)  # una etapa activada que a su vez encapsula activa su contenido (T-19b)
    return on


def forcing_change(h: HierarchyInfo, s: frozenset[str], forces: dict[str, frozenset[str]], o: dict[str, str]) -> bool:
    """¿Hay una situación impuesta que todavía no se cumple? (obliga a una evolución aunque nada franquee)."""
    for g, t in imposed(h, forces).items():
        owner = h.enclosure_owner.get(g)
        if o["7.4"] == "C" and owner is not None and owner not in s and t:
            continue  # 7.4 C: forzado ignorado mientras la encapsulante esté inactiva
        if s & h.partial_steps.get(g, frozenset()) != t:
            return True
    return False
