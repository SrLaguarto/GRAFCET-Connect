"""Posición de las etiquetas, las receptividades y los comentarios."""
from typing import Any

from grafcet.routing import orientacion

from .acciones import acciones_etapa, geometria_acciones
from .base import EVOLUCION_HORIZONTAL, H, SX, TB, MedirComentario, MedirTexto, Rect


def rects_textos_t(t: dict[str, Any], x: float, y: float, medir: MedirTexto) -> tuple[Rect | None, Rect | None]:
    """Lo que ocupan la designación y la receptividad de una transición centrada en (x, y): a izquierda y derecha
    del trazo
    (evolución vertical) o, si el trazo es vertical, la designación debajo y la receptividad encima, centradas en
    él, para que
    no pisen los enlaces horizontales."""
    horizontal = orientacion(t) in EVOLUCION_HORIZONTAL
    etq = cond = None
    if t.get("showLabel", True):
        w = medir([{"t": f"({t.get('label', t['id'])})"}], 13)
        etq = Rect(x - w / 2, y + TB + 2, w, 21) if horizontal else Rect(x - TB - 6 - w, y - 12, w, 21)
    if t.get("cond"):
        w = medir(t["cond"], 14)
        cond = Rect(x - w / 2, y - TB - 26, w, 21) if horizontal else Rect(x + TB + 8, y - 12, w, 21)
    return etq, cond


def pos_comentario_t(t: dict[str, Any], tx: float, ty: float, w: float, derecha: float = 0.0) -> tuple[float, float]:
    """Dónde empieza (x) y dónde está su centro vertical (yc) el comentario de la transición centrada en (tx, ty),
    con la
    receptividad de ancho `w` (0 si no tiene) y `derecha`, hasta dónde llega el estado de un temporizador (0 si no
    hay): a
    la derecha de todo ello, con 14 de margen, para que nunca se monte sobre su receptividad. Con evolución
    horizontal, la
    receptividad va centrada sobre el trazo y el comentario junto a ella."""
    tope = derecha + 8 if derecha else float("-inf")  # (sin temporizador `derecha` es 0, no una x: no cuenta, AB1)
    if orientacion(t) in EVOLUCION_HORIZONTAL:
        return max(tx - w / 2 + w + (14 if w else 0), tope), ty - TB - 9 - 5
    return max(tx + TB + 8 + w + (14 if w else 0), tope), ty


def pos_comentario_e(x: float, y: float, derecho: float) -> tuple[float, float]:
    """Lo mismo para una etapa en (x, y): a la derecha de su última acción (`derecho`, o el borde de la etapa)."""
    return max(derecho, x + H) + 10, y


def rects_comentarios(M: dict[str, Any], medir: MedirTexto,
                     medir_comentario: MedirComentario) -> list[tuple[str, Rect]]:
    """El rectángulo de cada comentario de etapa y de transición según el modelo y sin dibujar, con el ID de su elemento
    (un comentario se mueve con él): lo que cuenta como obstáculo al colocar otras cosas (AB2)."""
    out: list[tuple[str, Rect]] = []
    for t in M["transitions"]:
        if t.get("comment"):
            w = medir(t["cond"], 14) if t.get("cond") else 0.0
            x, yc = pos_comentario_t(t, t["x"] + SX, t["y"], w)
            cw, ch = medir_comentario(t["comment"])
            out.append((t["id"], Rect(x, yc - ch / 2, cw, ch)))
    for s in M["steps"]:
        if s.get("comment"):
            x, y = s["x"] + SX, s["y"]
            cajas_ = geometria_acciones(x, y, acciones_etapa(M, s), s.get("actionLayout", "fila"), medir=medir)[0]
            xc, yc = pos_comentario_e(x, y, max([ax + w for _, ax, _, w in cajas_] + [x + H]))
            cw, ch = medir_comentario(s["comment"])
            out.append((s["id"], Rect(xc, yc - ch / 2, cw, ch)))
    return out


def textos_transiciones(M, medir) -> list[tuple[Rect, str]]:
    """Lo que ocupan los textos de las transiciones (su etiqueta a la izquierda y su receptividad a la derecha), con la
    transición a la que pertenecen."""
    out = []
    for t in M["transitions"]:
        tx, ty = t["x"] + SX, t["y"]
        out += [(r, t["id"]) for r in rects_textos_t(t, tx, ty, medir) if r is not None]
    return out
