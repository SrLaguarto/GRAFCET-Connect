"""Choques del lienzo y búsqueda geométrica de sitio libre."""
import copy
from fractions import Fraction
from heapq import heappop, heappush
from math import ceil
from typing import Any, NamedTuple

from .acciones import colocadas, extra, geometria_acciones, situacion
from .base import ACT_MIN, EVOLUCION_HORIZONTAL, H, REJILLA, SX, TB, VACIO_H, VACIO_W
from .base import Rect, ajustar, barra, caja_barra, caja_etapa, cruza, orientaciones, posiciones, rect_marco
from .textos import rects_comentarios, textos_transiciones

MARGEN_SOLAPE = 8
BARRA_ALTO_MIN = 4
DESPLAZA_MAX = 600
DESPLAZA_PASADAS = 4
EXP_DX, EXP_DY, EXP_PASO, EXP_INTENTOS = 280, 320, 160, 40


class Desplazamiento(NamedTuple):
    nodos: list[tuple[str, float, float]]
    barras: list[tuple[str, Fraction, Any, bool]]
    sueltas: dict[str, dict[str, Fraction]]
    estilos: dict[str, dict[str, Any]]


def plan_desplazamiento(M, barras, borradores, estilos, corte, d, propio):
    """Elementos y carriles a desplazar. Una barra cruzada por el corte se ensancha."""
    nodos = [(i, x - SX + d, y) for i, (x, y) in posiciones(M).items() if x >= corte]
    ajustes = []
    for b in barras:
        izq, ancho = Fraction(str(b["x"])), Fraction(str(b["ancho"]))
        if izq + SX >= corte:
            ajustes.append((b["id"], izq + d, b["y"], False))
        elif izq + SX + ancho > corte:
            ajustes.append((b["id"], izq, ancho + d, True))
    sueltas = {
        s["id"]: {"x": Fraction(str(s["x"])) + d}
        for s in borradores
        if not s.get("etapa") and (s.get("grupo") or s["id"]) != propio and Fraction(str(s["x"])) + SX >= corte
    }
    carriles = {}
    for lid, estilo in estilos.items():
        via = estilo.get("route", {}).get("laneX") if isinstance(estilo, dict) else None
        if via is not None and float(via) + SX >= corte:
            nuevo = copy.deepcopy(estilo)
            x = float(via)
            nuevo["route"]["laneX"] = str(int(x + d)) if x == int(x) else str(x + d)
            carriles[lid] = nuevo
    return Desplazamiento(nodos, ajustes, sueltas, carriles)


def proximo_desplazamiento(choques, limite, total, maximo=DESPLAZA_MAX):
    """Corte y desplazamiento en pasos de rejilla, o None si sobrepasa el límite."""
    if min(izq for _, _, izq, _ in choques) < limite:
        return None
    corte = min(ancla for _, ancla, _, _ in choques)
    d = ceil(max(derecha - izq_caja for izq_caja, _, _, derecha in choques) / REJILLA) * REJILLA
    return (corte, d) if total + d <= maximo else None


def candidatos_hueco(antes, despues, etapas):
    return (k for k, v in despues.items() if (k in antes or k in etapas) and antes.get(k) != v)


def posiciones_hueco(punto):
    """Desplazamientos candidatos del pegado, en el orden de distancia del editor."""
    px, py = punto
    px -= SX
    origen_x, origen_y = ajustar(px), ajustar(py)
    cola, vistos = [(0, 0, 0)], {(0, 0)}
    while cola:
        _, ix, iy = heappop(cola)
        for nx, ny in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
            if (nx, ny) not in vistos:
                vistos.add((nx, ny))
                distancia = (origen_x + nx * REJILLA - px) ** 2 + (origen_y + ny * REJILLA - py) ** 2
                heappush(cola, (distancia, nx, ny))
        yield ix * REJILLA, iy * REJILLA


def solapa_marcos(huella, marcos, excluir=(), margen=0):
    otros = [rect_marco(b) for pid, b in marcos.items() if pid not in excluir]
    return [h for h in huella if any(toca(h.adjusted(-margen, -margen, margen, margen), o) for o in otros)]


def columna_expansion(x: int, y: int, libre) -> int | None:
    """Primera columna libre para la expansión, a la derecha de la macroetapa."""
    m = MARGEN_SOLAPE
    for k in range(EXP_INTENTOS):
        xe = x + EXP_DX + k * EXP_PASO
        zona = Rect(xe + SX - H - 26, y - H - 22, 2 * H + 96, EXP_DY + 2 * H + 44)
        if libre(zona.adjusted(-m, -m, m, m)):
            return xe
    return None


def huella_ficha(tipo, x, y):
    if tipo in ("etapa", "etapa_inicial", "encapsulante", "macroetapa"):
        return caja_etapa(x + SX, y)
    if tipo == "transicion":
        return Rect(x + SX - TB, y - 2, 2 * TB, 4)
    if tipo in ("simultaneidad", "simultaneidad:apertura", "simultaneidad:cierre"):
        return Rect(ajustar(x - 60) + SX, y, 120, 4)
    if tipo == "parcial":
        return Rect(x + SX, y, VACIO_W, VACIO_H + 20)
    if tipo == "accion" or tipo.startswith("accion:") or tipo == "forzado":
        return Rect(x + SX, y - H, ACT_MIN, 2 * H)
    return None


def elementos(M, acciones, ordenes, medir, medir_comentario) -> list[tuple[str, Rect, str]]:
    """La caja de cada elemento que no puede quedar tapado, tal como está dibujado (etapas, macroetapas, transiciones,
    barras, acciones y grupos de acciones, y los comentarios de etapas y transiciones, con ID «coment:<elemento>» y como
    «etapa» el elemento al que acompañan; no cuentan los enlaces): (ID, caja, etapa de la acción)."""
    trans = orientaciones(M)
    out = [(i, caja_barra(trans[i], x, y) if i in trans else caja_etapa(x, y), "")
           for i, (x, y) in posiciones(M).items()]
    out += [(b["id"], Rect(*barra(b)), "") for b in M.get("bars", [])]
    out += [(c["id"], Rect(*c["rect"]), c["etapa"] or "")
            for c in acciones]
    out += [(c["id"], Rect(*c["rect"]), c["etapa"]) for c in ordenes]
    out += [(f"coment:{i}", r, i) for i, r in rects_comentarios(M, medir, medir_comentario)]
    return out


def solapa(elementos, huella: list[Rect], propios: set[str]) -> list[Rect]:
    """Las cajas de `huella` que quedan a menos de MARGEN_SOLAPE de otro elemento (no cuentan los `propios`, ni las
    acciones de una etapa que se mueve)."""
    m = MARGEN_SOLAPE
    otros = [r for i, r, etapa in elementos if i not in propios and etapa not in propios]
    ampliadas = ((h, h.adjusted(-m, -m, m, m)) for h in huella)
    return [h for h, ampliada in ampliadas if any(ampliada.intersects(r) for r in otros)]


def choques(M, clave: str, disposicion: str, previas, medir,
            medir_comentario, alto_barra=BARRA_ALTO_MIN) -> list[tuple[Rect, float, float, float]]:
    """Con qué choca la colocación `disposicion` de las acciones de la etapa (o del grupo suelto) `clave`: las etapas,
    transiciones, barras, textos de transición y acciones de lo demás que quedan a menos de MARGEN_SOLAPE de sus
    cajas, o
    que sus trazos cruzan. Cada choque: (caja del obstáculo, `ancla`, `izq`, hasta dónde llega por la derecha lo
    suyo que
    toca, con el margen). `ancla` es la referencia con la que `_desplazar` decide qué se mueve: el centro x de la etapa
    o transición que lleva el obstáculo (una acción, el de su etapa; un texto, el de su transición), de modo que toda
    una columna se mueve junta; para una barra o un grupo suelto, su borde izquierdo (se mueven si ese borde llega al
    corte). `izq` es el borde izquierdo de ese mismo elemento, solo para saber si el obstáculo empieza antes que las
    acciones (`_despejar`). Las barras cuentan con un alto mínimo (BARRA_ALTO_MIN) aunque midan 0. Vacío: cabe. Con
    `_previas`
    (la firma de `_firmas` que tenía la etapa antes de la operación; solo lo pone `_asegurar_hueco` para el aviso de
    «quedan
    encima») no se cuenta lo que ya chocaba entonces (cajas con la misma firma), solo lo que la operación añade o
    mueve."""
    sit = situacion(M, clave)
    if sit is None:
        return []
    x, y, acciones, suelto = sit
    cajas, trazos = geometria_acciones(x, y, acciones, disposicion, suelto, medir=medir)
    huella, lineas = huella_acciones(cajas, trazos, previas)
    obstaculos = obstaculos_acciones(M, clave, medir, medir_comentario, alto_barra)
    out = []
    for r, ancla, izq in obstaculos:
        toca = [h.right() for h in huella if h.intersects(r)] + [ln.right() for ln in lineas if ln.intersects(r)]
        if toca:
            out.append((r, ancla, izq, max(toca)))
    return out


def huella_acciones(cajas, trazos, previas):
    m = MARGEN_SOLAPE
    huella = [Rect(ax, cy - H - extra(a)[0], w, 2 * H + extra(a)[0] + extra(a)[1]).adjusted(-m, -m, m, m)
              for a, ax, cy, w in cajas
              if (a.get("id", ""), *(round(v, 1) for v in (ax, cy - H, w, 2 * H)), *extra(a)) not in previas]
    lineas = [Rect(min(x1, x2) - 1, min(y1, y2) - 1, abs(x2 - x1) + 2, abs(y2 - y1) + 2).adjusted(0, 0, m, 0)
              for tramo in trazos for (x1, y1), (x2, y2) in zip(tramo, tramo[1:])]
    return huella, lineas


def caja_obstaculo_barra(bx, by, bw, bh, alto_minimo):
    if bh < alto_minimo:
        return Rect(bx, by - (alto_minimo - bh) / 2, bw, alto_minimo)
    return Rect(bx, by, bw, bh)


def obstaculos_acciones(M, clave, medir, medir_comentario, alto_barra):
    trans = orientaciones(M)
    pos = posiciones(M)
    obstaculos: list[tuple[Rect, float, float]] = []
    for i, (px, py) in pos.items():
        if i != clave:
            r = caja_barra(trans[i], px, py) if i in trans else caja_etapa(px, py)
            obstaculos.append((r, px, r.left()))
    for b in M.get("bars", []):
        bx, by, bw, bh = barra(b)
        r = caja_obstaculo_barra(bx, by, bw, bh, alto_barra)
        obstaculos.append((r, bx, bx))  # (Rect.intersects es falso con alto 0: una barra «O» nunca estorbaría)
    otras = [c for c in colocadas(M, medir) if clave not in (c["etapa"], c["grupo"])]
    izq_grupo: dict[str, float] = {}
    for c in otras:
        if not c["etapa"]:
            izq_grupo[c["grupo"]] = min(izq_grupo.get(c["grupo"], c["rect"][0]), c["rect"][0])
    for c in otras:
        if c["etapa"]:
            obstaculos.append((Rect(*c["rect"]), pos[c["etapa"]][0], pos[c["etapa"]][0] - H))
        else:
            obstaculos.append((Rect(*c["rect"]), izq_grupo[c["grupo"]], izq_grupo[c["grupo"]]))
    obstaculos += [(r, pos[tid][0], pos[tid][0] - TB) for r, tid in textos_transiciones(M, medir)]
    # El comentario propio ya se coloca a la derecha de sus acciones.
    for i, r in rects_comentarios(M, medir, medir_comentario):
        if i != clave:
            obstaculos.append((r, pos[i][0], pos[i][0] - (TB if i in trans else H)))
    return obstaculos


def pares_solape(M, propios: set[str], sin_horizontales: bool, medir, medir_comentario,
                 alto_barra=BARRA_ALTO_MIN) -> set[tuple[str, str]]:
    """Las parejas de elementos, con al menos uno de `propios`, cuyas cajas quedan a menos de MARGEN_SOLAPE (etapas,
    macroetapas, transiciones y sus textos, barras, y las acciones y órdenes, que cuentan como de su etapa), según el
    modelo y sin esperar a que se dibuje. Con `sin_horizontales`, no cuentan las transiciones en un tramo horizontal
    (de un
    retorno o un salto) ni sus textos: su sitio lo da el enlace, no el paso vertical (AB5)."""
    trans = orientaciones(M)
    cajas: list[tuple[str, Rect]] = [
        (i, caja_barra(trans[i], x, y) if i in trans else caja_etapa(x, y))
        for i, (x, y) in posiciones(M).items()]
    for b in M.get("bars", []):
        bx, by, bw, bh = barra(b)
        cajas.append((b["id"], caja_obstaculo_barra(bx, by, bw, bh, alto_barra)))
    cajas += [(c["etapa"] or c["grupo"], Rect(*c["rect"])) for c in colocadas(M, medir)]
    cajas += [(tid, r) for r, tid in textos_transiciones(M, medir)]
    cajas += rects_comentarios(M, medir, medir_comentario)  # con el ID de su elemento
    if sin_horizontales:
        fuera = {i for i, o in trans.items() if o in EVOLUCION_HORIZONTAL}
        cajas = [(i, r) for i, r in cajas if i not in fuera]
    out: set[tuple[str, str]] = set()
    m = MARGEN_SOLAPE
    limites = [(i, r.limites()) if r.w and r.h else (i, None) for i, r in cajas]
    for n, (i, r) in enumerate(cajas):
        margen = r.adjusted(-m, -m, m, m)
        if not margen.w or not margen.h:
            continue
        ampliada = margen.limites()
        for j, s in limites[n + 1:]:
            if s and i != j and (i in propios or j in propios) and cruza(ampliada, s):
                out.add((min(i, j), max(i, j)))
    return out


def toca(a: Rect, b: Rect) -> bool:
    """Si dos rectángulos se tocan o se cruzan (también con alto 0, como una barra de alternativa)."""
    return a.left() <= b.right() and b.left() <= a.right() and a.top() <= b.bottom() and b.top() <= a.bottom()


def marcos_grupo(a: dict[str, Any]) -> list[Rect]:
    """Dónde quedan, en el dibujo, los marcos vacíos que se mueven con el grupo (con su nombre debajo)."""
    dx, dy = a["x"] - a["x0"], a["y"] - a["y0"]
    return [Rect(x + dx + SX, y + dy, VACIO_W, VACIO_H + 20)
            for i, (x, y) in a["inicio"].items() if a["tipos"][i] == "marco"]


def huella_arrastre(a: dict[str, Any], elementos, cajas_acciones) -> list[Rect]:
    """Las cajas de lo que se está moviendo, en su posición actual: el elemento y, de una etapa, sus acciones; de un
    grupo de acciones sueltas, cada una."""
    if a.get("tipo") == "borrador":
        return [Rect(*c["rect"]) for c in cajas_acciones if c["id"] in a["ids"]]
    if a.get("tipo") == "marco":  # el marco vacío, con su nombre debajo
        return [Rect(a["x"] + SX, a["y"], VACIO_W, VACIO_H + 20)]
    if a.get("tipo") == "grupo":
        moviendo = set(a["ids"])
        return [r for i, r, etapa in elementos() if i in moviendo or etapa in moviendo] + marcos_grupo(a)
    ident = a["id"]
    cajas = elementos()
    mio = [r for i, r, _ in cajas if i == ident]
    acciones = [Rect(*c["rect"]) for c in cajas_acciones if c["etapa"] == ident]
    comentarios = [r for i, r, etapa in cajas if i.startswith("coment:") and etapa == ident]
    return mio + acciones + comentarios
