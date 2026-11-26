"""Reparto estático de vencimientos simultáneos en grupos que no pueden afectarse entre sí (U-06, L-04, P-IMP-09).

Dos parciales son «dependientes» si lo que ocurre en uno puede cambiar lo que ocurre en el otro dentro de un mismo
instante: uno lee la actividad o el tiempo del otro, uno lee una variable que escribe el otro, dos escriben de forma
no pura la misma variable, o la jerarquía los liga (forzado, macroetapa, encapsulación). Una unión-búsqueda sobre los
parciales reúne los dependientes en componentes; los vencimientos de componentes distintos no interactúan y su orden
no puede importar. El análisis es **conservador**: ante la duda se une, y lo único que se pierde es velocidad.

Solo mira el modelo compilado y se calcula una vez por modelo. No toca el motor ni importa nada de fuera de `grafcet/`.
"""
from __future__ import annotations

from typing import Iterable

from .model import CompiledModel

_ATRIBUTO = "_independencia_cache"


class _Duda(Exception):
    """Algo del modelo que el análisis no sabe interpretar: se une todo."""


class _Union:
    def __init__(self, items: Iterable[str]) -> None:
        self.padre = {x: x for x in items}

    def raiz(self, x: str) -> str:
        if x not in self.padre:
            raise _Duda(x)
        while self.padre[x] != x:
            self.padre[x] = self.padre[self.padre[x]]
            x = self.padre[x]
        return x

    def unir(self, a: str, b: str) -> None:
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            # el representante es siempre el menor, para que el resultado sea determinista
            if rb < ra:
                ra, rb = rb, ra
            self.padre[rb] = ra

    def unir_todos(self, xs: Iterable[str]) -> None:
        xs = list(xs)
        for x in xs[1:]:
            self.unir(xs[0], x)


def _analizar(cm: CompiledModel) -> tuple[dict[str, frozenset[str]], dict[str, str]] | None:
    """(parciales dueños de cada expresión, representante de cada parcial); None si hay que unirlo todo."""
    pids = list(cm.partials)
    uf = _Union(pids)
    h = cm.hier

    def p_etapa(sid: str) -> str:
        st = cm.steps.get(sid)
        if st is None:
            raise _Duda(sid)
        return st.partial

    def p_elemento(ref: str) -> set[str]:
        """Parciales de una referencia a etapa o a macroetapa (con su expansión)."""
        if ref in cm.steps:
            return {cm.steps[ref].partial}
        m = h.macros.get(ref)
        if m is None:
            raise _Duda(ref)
        out = {m.partial, m.expansion}
        out |= {p_etapa(s) for s in h.macro_steps.get(ref, ())}
        return out

    # Escritores de cada variable: parciales de las etapas de las acciones que la tienen de objetivo
    escritores: dict[str, set[str]] = {}
    no_pura: set[str] = set()
    for a in cm.actions.values():
        escritores.setdefault(a.target, set()).add(p_etapa(a.step))
        if a.mode != "continuous" or a.value is not None or a.trigger is not None or a.trigger_expr is not None:
            no_pura.add(a.target)
    for v in no_pura:
        uf.unir_todos(escritores[v])  # c: escritura memorizada, con valor, con disparador, contador o asignación

    # a: dueño de cada expresión (una expresión puede tener varios usuarios)
    duenos: dict[str, set[str]] = {}
    for t in cm.transitions.values():
        duenos.setdefault(t.cond, set()).add(t.partial)
        # Conservador: una transición cuyas etapas están en otros parciales los une con el suyo
        for ref in set(t.pre) | set(t.post):
            uf.unir_todos([t.partial, *p_elemento(ref)])
    for a in cm.actions.values():
        p = p_etapa(a.step)
        for eid in (a.cond, a.value, a.trigger_expr):
            if eid is not None:
                duenos.setdefault(eid, set()).add(p)
    if any(eid not in duenos for eid in cm.exprs):
        raise _Duda("expresión sin dueño conocido")  # unir todo: no se sabe quién podría leerla

    # b: lo que cada expresión lee une su parcial con el de lo leído
    for eid, owners in duenos.items():
        e = cm.exprs.get(eid)
        if e is None:
            raise _Duda(eid)
        sup = e.support  # ya incluye lo que hay dentro de eventos y de bases temporales (support recorre los hijos)
        mios = sorted(owners)
        uf.unir_todos(mios)
        p = mios[0]
        for sid in sup.steps | sup.elapsed:
            uf.unir(p, p_etapa(sid))
        for pid in sup.partials:
            uf.unir(p, pid)
            for hijo in cm.partials[pid].get("children", ()):  # activePartial de un parcial con hijos
                uf.unir(p, hijo)
        for mid in sup.macros:
            for q in p_elemento(mid):
                uf.unir(p, q)
        for vid in sup.vars:
            var = cm.variables.get(vid)
            if var is None:
                raise _Duda(vid)
            if var.role != "input":
                for q in escritores.get(vid, ()):
                    uf.unir(p, q)

    # d: jerarquía
    for f in h.forces:
        uf.unir(p_etapa(f.source), f.target)
        for s in f.steps:
            uf.unir(f.target, p_etapa(s))
    for mid, m in h.macros.items():
        uf.unir_todos(p_elemento(mid))
    for owner, encs in h.enclosures.items():
        po = p_etapa(owner)
        for e in encs:
            uf.unir(po, e.partial)
            for s in e.activation:
                uf.unir(po, p_etapa(s))
        for q in h.content_partials.get(owner, ()):
            uf.unir(po, q)
        for s in h.content.get(owner, ()):
            uf.unir(po, p_etapa(s))
    for pid, info in cm.partials.items():  # parciales anidados: se unen con sus hijos
        for hijo in info.get("children", ()):
            uf.unir(pid, hijo)

    return ({k: frozenset(v) for k, v in duenos.items()}, {p: uf.raiz(p) for p in pids})


def _datos(cm: CompiledModel) -> tuple[dict[str, frozenset[str]], dict[str, str]] | None:
    """Resultado del análisis, guardado en el propio modelo (no forma parte de su igualdad ni de su serialización)."""
    try:
        return cm.__dict__[_ATRIBUTO]
    except KeyError:
        pass
    try:
        datos = _analizar(cm)
    except _Duda:
        datos = None
    except Exception:  # cualquier cosa inesperada: se une todo, nunca se arriesga
        datos = None
    try:
        cm.__dict__[_ATRIBUTO] = datos
    except Exception:
        pass
    return datos


def _parcial_de_clave(cm: CompiledModel, key: str, duenos: dict[str, frozenset[str]]) -> str | None:
    """Parcial al que pertenece una clave de vencimiento; None si no se reconoce."""
    if key.startswith("limit:"):
        a = cm.actions.get(key[len("limit:"):])
        return cm.steps[a.step].partial if a is not None and a.step in cm.steps else None
    spec = cm.temporals.get(key)
    if spec is None:
        return None
    owners = duenos.get(spec.expr)
    return min(owners) if owners else None


def grupos_de_vencimientos(cm: CompiledModel, keys: Iterable[str]) -> list[tuple[str, ...]]:
    """Reparte las claves de vencimiento en grupos independientes entre sí.

    Cada grupo va ordenado y los grupos van por su primera clave, así que el resultado es determinista. Si algo no se
    reconoce (una clave de otra forma, un elemento del modelo sin interpretar) todas las claves quedan en un solo
    grupo: es lo que hacía la comprobación antes de repartirlas, y siempre es correcto.
    """
    todas = tuple(sorted(set(keys)))
    if len(todas) < 2:
        return [todas] if todas else []
    datos = _datos(cm)
    if datos is None:
        return [todas]
    duenos, raiz = datos
    grupos: dict[str, list[str]] = {}
    for k in todas:
        p = _parcial_de_clave(cm, k, duenos)
        if p is None or p not in raiz:
            return [todas]
        grupos.setdefault(raiz[p], []).append(k)
    return sorted((tuple(g) for g in grupos.values()), key=lambda g: g[0])
