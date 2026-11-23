"""Anclas, distancias y detección geométrica bajo un punto."""
from typing import Any, Callable

from grafcet.routing import orientacion, punto_t

from .base import ALTO_T, ANCLA, ANCLA_S, EVOLUCION_HORIZONTAL, H, RADIO_ANCLA, SIMUL, SX, TB
from .base import MedirTexto, Punto, Rect, barra, distancia_segmento as _distancia, posiciones
from .enlaces import _otros_t, enlaces, simul_d
from .marcos import cajas_parciales
from .textos import rects_textos_t


def _segmento(M: dict[str, Any], pos: dict[str, Punto], d: dict[str, Any]) -> tuple[Punto, Punto] | None:
    a, b = pos.get(d["from"]), pos.get(d["to"])
    return (a, b) if a and b else None


def anclas(
    M: dict[str, Any], ident: str, pos: dict[str, tuple[float, float]] | None = None, *,
    pasos: set[str] | None = None, transiciones: dict[str, dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Puntos de unión de un elemento: etapa y transición, arriba (entra el enlace) y abajo (sale); la etapa, además, en
    el centro de su lado derecho (de ahí salen las acciones); una acción suelta (la primera de su grupo), a la
    izquierda. `pasos` (los ID de las etapas) y `transiciones` (por ID) son solo para no buscarlos en cada llamada cuando se piden las
    de todos los elementos (`ancla_en`): el resultado es el mismo."""
    for b in M.get("bars", []):
        if b["id"] == ident:
            bx, by, w, h = barra(b)
            return [{"id": ident, "lado": "arriba", "pos": (bx + w / 2, by - 9)},
                    {"id": ident, "lado": "abajo", "pos": (bx + w / 2, by + h + 9)}]
    for d in M.get("draftActions", []):  # una acción suelta: un solo punto de unión, en el medio de su lado izquierdo
        if d["id"] == ident and not d.get("etapa") and d.get("cabeza", True):
            return [{"id": ident, "lado": "izq", "pos": (d["x"] + SX, d["y"])}]
    if pos is None:
        pos = posiciones(M)
    if ident not in pos:
        return []
    x, y = pos[ident]
    t = next((t for t in M["transitions"] if t["id"] == ident), None) if transiciones is None else transiciones.get(ident)
    arriba, abajo = H, H
    if t is not None:
        arriba = ANCLA_S + simul_d(t, x, y, _otros_t(t, pos, -1), -1) - SIMUL if t.get("simulPre") else ANCLA
        abajo = ANCLA_S + simul_d(t, x, y, _otros_t(t, pos, 1), 1) - SIMUL if t.get("simulPost") else ANCLA
    if t is not None and orientacion(t) != "abajo":  # «arriba» es la entrada (el lado de donde viene la evolución)
        return [{"id": ident, "lado": "arriba", "pos": punto_t(t, x, y, -arriba)},
                {"id": ident, "lado": "abajo", "pos": punto_t(t, x, y, abajo)}]
    out = [{"id": ident, "lado": "arriba", "pos": (x, y - arriba)},
           {"id": ident, "lado": "abajo", "pos": (x, y + abajo)}]
    if (ident in pasos) if pasos is not None else any(st["id"] == ident for st in M["steps"]):
        out.append({"id": ident, "lado": "der", "pos": (x + H, y)})
    return out


def ancla_en(M: dict[str, Any], p: Punto, radio: float = RADIO_ANCLA, sin_der: bool = False) -> dict[str, Any] | None:
    """El punto de unión más cercano al puntero, si hay alguno a menos de `radio` (el de la derecha de una etapa, de
    donde salen las acciones, solo a menos de 8 si la etapa ya las tiene: ahí empieza su enlace, que se selecciona;
    `sin_der`
    lo ignora, para enlaces que no son de acciones)."""
    best = None
    ocupadas = {s["id"] for s in M["steps"] if s["actions"]}
    ocupadas.update(d["etapa"] for d in M.get("draftActions", []) if d.get("etapa"))
    cuadrados = {s["id"] for s in M["steps"]} | {s["id"] for s in M.get("macros", [])}
    pos = posiciones(M)  # una sola vez: `anclas` la rehace entera si no se la dan (y se llama por cada elemento)
    pasos = {s["id"] for s in M["steps"]}
    transiciones = {t["id"]: t for t in M["transitions"]}
    for ident, (cx, cy) in pos.items():
        if ident in cuadrados and Rect(cx - H + 2, cy - H + 2, 2 * H - 4, 2 * H - 4).contiene(p):
            continue  # dentro de la caja se selecciona o arrastra; los puntos de enlace quedan fuera
        for a in anclas(M, ident, pos, pasos=pasos, transiciones=transiciones):
            if a["lado"] == "der" and sin_der:
                continue
            d = ((a["pos"][0] - p[0]) ** 2 + (a["pos"][1] - p[1]) ** 2) ** 0.5
            limite = min(radio, 8) if a["lado"] == "der" and ident in ocupadas else radio
            if d <= limite and (best is None or d < best[0]):
                best = (d, a)
    for d in M.get("draftActions", []):
        for a in anclas(M, d["id"]):
            dist = ((a["pos"][0] - p[0]) ** 2 + (a["pos"][1] - p[1]) ** 2) ** 0.5
            if dist <= radio and (best is None or dist < best[0]):
                best = (dist, a)
    for b in M.get("bars", []):  # en una barra, el punto de unión sigue al puntero a lo largo de su ancho
        bx, by, w, h = barra(b)
        if bx - 4 <= p[0] <= bx + w + 4:
            x = min(max(p[0], bx), bx + w)
            for lado, y in (("arriba", by - 9), ("abajo", by + h + 9)):
                d = abs(p[1] - y)
                if d <= min(radio, 7) and (best is None or d < best[0]):
                    best = (d, {"id": b["id"], "lado": lado, "pos": (x, y)})
    return best[1] if best else None


def marco_en(M: dict[str, Any], p: Punto, borde: float = 6, *, medir: MedirTexto,
             cajas: dict[str, dict[str, float]] | None = None) -> str | None:
    """El parcial cuyo marco (recinto o parcial; la expansión no tiene) se toca en el punto: su borde, a `borde` o
    menos, o
    su nombre. Dentro del marco, lejos del borde, no hay nada que agarrar: ahí se suelta, se traza el lazo… Si hay
    varios,
    el más pequeño."""
    if not any(part["kind"] in ("enclosure", "partial") for part in M.get("partials") or []):
        return None  # sin recintos ni parciales con marco no hay nada que tocar: no se calculan las cajas
    if cajas is None:  # (quien lo pide muchas veces sobre el mismo dibujo, como un arrastre, las trae ya calculadas)
        cajas = cajas_parciales(M, medir=medir)
    mejor: tuple[float, str] | None = None
    for part in M.get("partials") or []:
        b = cajas.get(part["id"])
        if not b or part["kind"] not in ("enclosure", "partial"):
            continue
        x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
        cerca = x0 - borde <= p[0] <= x1 + borde and y0 - borde <= p[1] <= y1 + borde
        interior = x0 + borde < p[0] < x1 - borde and y0 + borde < p[1] < y1 - borde
        w = 8 * len(part["label"]) + 8  # ancho de alcance del nombre bajo el parcial
        xn = x0 + 26
        en_nombre = xn <= p[0] <= xn + w + 8 and y1 - 8 <= p[1] <= y1 + 12
        if part["kind"] == "enclosure":
            dueno = M.get("names", {}).get(part.get("ownerStep"), part.get("ownerStep", ""))
            en_nombre |= xn <= p[0] <= xn + 8 * len(dueno) + 16 and y0 - 12 <= p[1] <= y0 + 8
        if (cerca and not interior) or en_nombre:
            area = (x1 - x0) * (y1 - y0)
            if mejor is None or area < mejor[0]:
                mejor = (area, part["id"])
    return mejor[1] if mejor else None


def elemento_en(M: dict[str, Any], p: Punto, medir: MedirTexto,
                anotacion_en: Callable[[], str | None], cajas: dict[str, dict[str, float]] | None = None) -> str | None:
    """El elemento bajo un punto del dibujo: etapa, transición (su trazo), enlace en borrador, enlace o, al final y solo
    en su borde o su nombre, el marco de un parcial."""
    pos = posiciones(M)
    for t in M["transitions"]:  # el trazo, su designación a la izquierda y su receptividad a la derecha
        x, y = pos[t["id"]]
        if orientacion(t) in EVOLUCION_HORIZONTAL:  # designación debajo y receptividad encima
            if abs(p[0] - x) <= ALTO_T and abs(p[1] - y) <= TB + 6 or any(
                    r is not None and r.adjusted(-2, -2, 2, 2).contiene(p) for r in rects_textos_t(t, x, y, medir)):
                return t["id"]
            continue
        ancho = 8 * sum(len(sg["t"]) for sg in (t.get("cond") or []))
        if -(TB + 44) <= p[0] - x <= TB + 12 + ancho and abs(p[1] - y) <= ALTO_T:
            return t["id"]
    for s in list(M["steps"]) + list(M.get("macros", [])):
        x, y = pos[s["id"]]
        if abs(p[0] - x) <= H + 4 and abs(p[1] - y) <= H + 4:
            return s["id"]
    for b in M.get("bars", []):
        bx, by, w, h = barra(b)
        if bx - 6 <= p[0] <= bx + w + 6 and by - 6 <= p[1] <= by + h + 6:
            return b["id"]
    for d in M.get("drafts", []):
        seg = _segmento(M, pos, d)
        if seg and _distancia(p, *seg) <= 6:
            return d["id"]
    for e in enlaces(M):  # los enlaces, al final: lo que hay encima manda
        if any(_distancia(p, a, b) <= 7 for a, b in zip(e["pts"], e["pts"][1:])):
            return e["id"]
    return anotacion_en() or marco_en(M, p, medir=medir, cajas=cajas)
