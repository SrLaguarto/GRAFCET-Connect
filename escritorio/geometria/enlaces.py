"""Ajuste de los recorridos compartidos con el núcleo y sus tramos."""
import copy
from typing import Any

from grafcet import routing
from grafcet.routing import orientacion

from .base import BARRA_GROSOR, DISTANCIA_TRANSICION_BARRA, PASO, REJILLA, SIMUL, SX, Punto, posiciones
from .base import ajustar, distancia_segmento

IMAN = 40


def simul_d(t: dict[str, Any], tx: float, ty: float, otros: list[tuple[float, float]], signo: int) -> float:
    """Distancia de la transición en (tx, ty) a su doble trazo de simultaneidad, por arriba (`signo` -1) o por abajo
    (1), de
    evolución hacia abajo: el hueco exterior se acorta un paso de rejilla al equidistanciar.
    Si no cabe también el paso hacia la etapa, se conserva el trazo compacto."""
    if orientacion(t) != "abajo":
        return SIMUL
    lejos = [signo * (p[1] - ty) for p in otros if signo * (p[1] - ty) > 0]
    return DISTANCIA_TRANSICION_BARRA if lejos and min(lejos) >= PASO + DISTANCIA_TRANSICION_BARRA else SIMUL


def _otros_t(t: dict[str, Any], pos: dict[str, Punto], signo: int) -> list[Punto]:
    ids = t.get("preDib", t["pre"]) if signo < 0 else t.get("postDib", t["post"])
    return [pos[i] for i in ids if i in pos]


# Las listas de las que dependen los recorridos (`grafcet.routing.enlaces` solo lee estas).
_ENTRADAS = ("links", "steps", "macros", "transitions", "bars", "linkStyles")


def _vigentes(M: dict[str, Any]) -> bool:
    """`M["enlaces"]` solo vale mientras `M` siga teniendo **los mismos objetos** de lista con los que se calculó (`M["_enlaces_de"]`):
    quien filtra o sustituye `links`, etapas, transiciones, barras o estilos (una hoja, un plano, una selección) deja de tener recorridos
    vigentes aunque la copia conserve la clave. `deepcopy` conserva la relación porque copia las listas y su referencia a la vez."""
    de = M.get("_enlaces_de")
    return "enlaces" in M and de is not None and all(a is M.get(k) for a, k in zip(de, _ENTRADAS))


def enlaces(M: dict[str, Any]) -> list[dict[str, Any]]:
    """Recorridos de solo lectura, con los extremos ajustados a las simultaneidades de la vista.

    Los recorridos son parte del modelo de la vista: `Edicion.reconstruir` los deja en `M["enlaces"]` (y los sin ajustar en
    `M["links"]`, que ya calculó `Vista`). Si `M` ya no tiene las listas con las que se calcularon (se filtró una copia), se calculan
    desde cero con lo que hay, sin recordarlos. Un modelo que nunca los tuvo (el de la simulación, uno hecho a mano) usa los `links`
    que trae o los calcula. Si se toca `M` a mano sin cambiar sus listas, `recalcular` los rehace."""
    if "enlaces" in M:
        return M["enlaces"] if _vigentes(M) else _ajustar_enlaces(M, routing.enlaces(M))
    return _ajustar_enlaces(M, M["links"] if "links" in M else routing.enlaces(M))


def fijar(M: dict[str, Any]) -> list[dict[str, Any]]:
    """Ajusta los `links` que ya trae `M` y los deja como sus recorridos vigentes."""
    M["enlaces"] = _ajustar_enlaces(M, M["links"])
    M["_enlaces_de"] = tuple(M.get(k) for k in _ENTRADAS)
    return M["enlaces"]


def resolver(M: dict[str, Any]) -> list[dict[str, Any]]:
    """Calcula desde cero los recorridos de las listas que tiene `M` ahora y los deja vigentes en `enlaces`, sin tocar `links`."""
    M["enlaces"] = _ajustar_enlaces(M, routing.enlaces(M))
    M["_enlaces_de"] = tuple(M.get(k) for k in _ENTRADAS)
    return M["enlaces"]


def recalcular(M: dict[str, Any]) -> list[dict[str, Any]]:
    """Calcula los recorridos de `M` desde cero y los deja en él: sin ajustar en `links`, ajustados en `enlaces`."""
    M["links"] = routing.enlaces(M)
    return fijar(M)


def _ajustar_enlaces(M: dict[str, Any], base: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = list(base)
    pos = posiciones(M)
    ts = {t["id"]: t for t in M["transitions"]}
    for i, e in enumerate(base):
        t = ts.get(e.get("tid"))
        if t is None or not e.get("simul") or "orient" in e or e["rol"] not in ("pre", "post"):
            continue
        tx, ty = pos[t["id"]]
        signo = -1 if e["rol"] == "pre" else 1
        d = simul_d(t, tx, ty, _otros_t(t, pos, signo), signo)
        if d == SIMUL:
            continue
        viejo, nuevo = ty + signo * (SIMUL + BARRA_GROSOR), ty + signo * (d + BARRA_GROSOR)
        puntos = [(x, nuevo if y == viejo else nuevo - 30 if y == viejo - 30 and signo < 0 else y)
                  for x, y in e["pts"]]
        out[i] = {**e, "pts": puntos}
    return out


def rango_tramo(pts: list[Any], i: int, vertical: bool) -> tuple[float, float]:
    """Lo que ocupa el tramo i de un recorrido a lo largo del otro eje (y si es vertical, x si es horizontal)."""
    e = 1 if vertical else 0
    return min(pts[i][e], pts[i + 1][e]), max(pts[i][e], pts[i + 1][e])


def tramo_en(recorridos, enlace: str, p: Punto):
    for r in recorridos:
        if r["id"] == enlace:
            pts = r["pts"]
            for h in r["handles"]:
                i = h["segment"]
                if distancia_segmento(p, pts[i], pts[i + 1]) <= 7:
                    return r.get("routePts", pts), h
            break
    return None


def _numero(v: float) -> str:
    return str(int(v)) if v == int(v) else str(v)


def ajustar_tramo(pts, marca, ruta, anterior, p, alinear):
    """Recalcula una vía manual a partir del punto arrastrado y de los tramos paralelos."""
    i = marca["segment"]
    if marca.get("orient"):
        vertical = pts[i][0] == pts[i + 1][0]
        eje = 0 if vertical else 1
        valido = isinstance(anterior, dict) and str(anterior.get("n")) == str(len(pts))
        d0 = float(anterior.get(str(i), 0)) if valido else 0.0
        destino = alinear(ajustar(p[eje]), vertical, rango_tramo(pts, i, vertical))
        tramos = dict(anterior) if valido else {}
        tramos.update({"n": str(len(pts)), str(i): _numero(d0 + destino - pts[i][eje])})
        return {**(ruta or {}), "tramos": tramos}
    if len(pts) == 6:
        vias = dict(ruta) if ruta is not None else {
            "laneX": str(pts[2][0] - SX), "exitY": str(pts[1][1]), "entryY": str(pts[3][1]),
        }
        k = marca.get("routeSegment", i)
        clave = {1: "exitY", 2: "laneX", 3: "entryY"}[k]
        vertical = clave == "laneX"
        v = alinear(ajustar(p[0 if vertical else 1]), vertical, rango_tramo(pts, k, vertical))
        vias[clave] = _numero(v - SX if vertical else v)
        return vias
    if len(pts) == 4:
        v = alinear(ajustar(p[1]), False, rango_tramo(pts, i, False))
        return {"middleY": _numero(v)}
    return None


def pegar_a_paralelo(recorridos, valor: float, vertical: bool, propio: str, rango: tuple[float, float]) -> float:
    """Al colocar a mano un tramo (P-IMP-118): si la posición de la rejilla lo deja a media rejilla (10) o menos de
    un tramo
    paralelo de OTRO enlace que de verdad coincide con él a lo largo del otro eje (`rango` y el del otro se cortan,
    con 4 de
    margen), queda exactamente en la coordenada de ese tramo (solo hacia el solape, nunca para apartarse); si no, la
    posición de la rejilla. `vertical`: el tramo es vertical (su x); si no, su y."""
    eje = 0 if vertical else 1
    mejor = None
    for r in recorridos:
        if r["id"] == propio:
            continue
        for u, v in zip(r["pts"], r["pts"][1:]):
            lo, hi = min(u[1 - eje], v[1 - eje]), max(u[1 - eje], v[1 - eje])
            coincide = max(lo, rango[0]) <= min(hi, rango[1]) + 4
            if u != v and u[eje] == v[eje] and abs(u[eje] - valor) <= REJILLA / 2 and coincide:
                if mejor is None or abs(u[eje] - valor) < abs(mejor - valor):
                    mejor = u[eje]
    return valor if mejor is None else mejor


def iman_etapa(M, ident: str, x: float, moviendo: set[str] | frozenset[str] = frozenset()) -> float:
    """Al mover una etapa o una transición cerca de la vertical de un elemento enlazado con ella (a IMAN o menos), se
    alinea con él: el enlace queda recto, sin la S de un desplazamiento de un par de puntos de rejilla. Con varios
    elementos que se mueven juntos (`moviendo`), solo cuentan los enlazados que se quedan donde están."""
    pos = posiciones(M)
    enlazados = set()
    for t in M["transitions"]:
        pasos = set(t.get("preDib", t["pre"])) | set(t.get("postDib", t["post"]))
        if t["id"] == ident:
            enlazados |= pasos
        elif ident in pasos:
            enlazados.add(t["id"])
    xs = [pos[o][0] - SX for o in enlazados if o in pos and o not in moviendo]
    cerca = min(xs, key=lambda v: abs(v - x), default=None)
    return cerca if cerca is not None and 0 < abs(cerca - x) <= IMAN else x


def sumar_coordenada(valor: Any, d: float) -> Any:
    """Un valor de coordenada del estilo de un enlace (un texto) con `d` más; sin cambio si no es un número."""
    try:
        v = float(valor) + d
    except (TypeError, ValueError):
        return valor
    return str(int(v)) if v == int(v) else str(v)


def rutas_con_grupo(estilos, ids: set[str], dx: float, dy: float) -> dict[str, dict[str, Any]]:
    """El estilo nuevo de los enlaces con sus dos extremos en `ids` (lo que se mueve): su recorrido manual, en
    coordenadas
    absolutas (laneX, exitY, entryY, middleY), se desplaza con ellos. Los de un solo extremo movido se quedan como
    están,
    igual que al mover un elemento con `Editor.move`."""
    out: dict[str, dict[str, Any]] = {}
    for lid, estilo in estilos.items():
        extremos = lid.split("|")[:2]
        ruta = estilo.get("route") if isinstance(estilo, dict) else None
        if isinstance(ruta, dict) and len(extremos) == 2 and all(e in ids for e in extremos):
            nuevo = copy.deepcopy(estilo)
            for clave, d in (("laneX", dx), ("exitY", dy), ("entryY", dy), ("middleY", dy)):
                if clave in nuevo["route"]:
                    nuevo["route"][clave] = sumar_coordenada(nuevo["route"][clave], d)
            out[lid] = nuevo
    return out


def separar_ramas(transiciones, pos, origen: str, destino: str) -> tuple[str, float, float] | None:
    """Una etapa con dos transiciones (o dos transiciones hacia una etapa) es una alternativa: si la transición que se
    acaba de enlazar quedó justo encima de una hermana, se aparta a un lado para que se vea la rama."""
    ts = {t["id"]: t for t in transiciones}
    t = ts.get(destino) or ts.get(origen)
    if t is None or t["id"] not in pos:
        return
    etapa = origen if t["id"] == destino else destino
    hermanas = [o for o in ts.values() if o["id"] != t["id"] and o["id"] in pos
                and (etapa in o["preRefs"] if t["id"] == destino else etapa in o["postRefs"])]
    if any(abs(pos[o["id"]][0] - pos[t["id"]][0]) < 40 for o in hermanas):
        x = max(pos[o["id"]][0] for o in hermanas) - SX + 160
        return t["id"], x, pos[t["id"]][1]
    return None
