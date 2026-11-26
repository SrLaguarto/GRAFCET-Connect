"""Coordenadas, medidas compartidas y rectángulos del lienzo."""
from typing import Any, Callable, NamedTuple

from grafcet.routing import TALLO_T, orientacion

SX = 100
H = 22
TB = 8
ACT_LINK = 26
ACT_MIN = 80
ACT_GAP = 36
ACT_BUS = 28
ACT_COL = 12
ACT_CANAL = 7
ANCHO_COMENTARIO = 190
TMR_EXTRA = 14
MARGEN_MARCO_X = 26
MARGEN_MARCO_Y = 22
REJILLA = 20
ALTO_T = 14
ANCLA = TALLO_T
ANCLA_S = 28
SIMUL = 14
PASO = 60
DISTANCIA_TRANSICION_BARRA = PASO - REJILLA
RADIO_ANCLA = 14
EVOLUCION_HORIZONTAL = ("derecha", "izquierda")
BARRA_GROSOR = 8
VACIO_W, VACIO_H = 180, 120

Punto = tuple[float, float]
MedirTexto = Callable[[list[dict[str, Any]], int], float]
MedirComentario = Callable[[str], tuple[float, float]]


class Rect(NamedTuple):
    x: float
    y: float
    w: float
    h: float

    def left(self) -> float:
        return self.x

    def top(self) -> float:
        return self.y

    def right(self) -> float:
        return self.x + self.w

    def bottom(self) -> float:
        return self.y + self.h

    def adjusted(self, izq: float, arriba: float, der: float, abajo: float) -> "Rect":
        return Rect(self.x + izq, self.y + arriba, self.w + der - izq, self.h + abajo - arriba)

    def contiene(self, punto: Punto) -> bool:
        x, y = punto
        x1, y1 = self.right(), self.bottom()
        return (self.w != 0 and self.h != 0 and min(self.x, x1) <= x <= max(self.x, x1)
                and min(self.y, y1) <= y <= max(self.y, y1))

    def limites(self) -> tuple[float, float, float, float]:
        x1, y1 = self.right(), self.bottom()
        return min(self.x, x1), min(self.y, y1), max(self.x, x1), max(self.y, y1)

    def intersects(self, otro: "Rect") -> bool:
        if not self.w or not self.h or not otro.w or not otro.h:
            return False
        return cruza(self.limites(), otro.limites())


def cruza(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """Intersección de dos cajas de área positiva. El contacto por un borde se excluye."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def rect_marco(b: dict[str, float]) -> Rect:
    return Rect(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"])


def caja_etapa(x: float, y: float) -> Rect:
    return Rect(x - H, y - H, 2 * H, 2 * H)


def distancia_segmento(p: Punto, a: Punto, b: Punto) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ((dx * dx + dy * dy) or 1)))
    return ((p[0] - a[0] - k * dx) ** 2 + (p[1] - a[1] - k * dy) ** 2) ** 0.5


def punto_modelo(p: Punto) -> tuple[int, int]:
    return ajustar(p[0] - SX), ajustar(p[1])


def esquina_parcial(p: Punto) -> tuple[int, int]:
    return ajustar(p[0] - SX - VACIO_W / 2), ajustar(p[1] - VACIO_H / 2)


def ajustar(v: float) -> int:
    """Al punto de la rejilla más cercano."""
    return round(v / REJILLA) * REJILLA


def posiciones(M: dict[str, Any]) -> dict[str, Punto]:
    """Centro, en el dibujo, de cada etapa, macroetapa y transición."""
    pos = {s["id"]: (s["x"] + SX, s["y"]) for s in M["steps"]}
    pos.update({m["id"]: (m["x"] + SX, m["y"]) for m in M.get("macros", [])})
    pos.update({t["id"]: (t["x"] + SX, t["y"]) for t in M["transitions"]})
    return pos


def orientaciones(M: dict[str, Any]) -> dict[str, str]:
    return {t["id"]: orientacion(t) for t in M["transitions"]}


def caja_barra(o: str, x: float, y: float) -> Rect:
    """Trazo de una transición centrada en (x, y)."""
    if o in EVOLUCION_HORIZONTAL:
        return Rect(x - 2, y - TB, 4, 2 * TB)
    return Rect(x - TB, y - 2, 2 * TB, 4)


def barra(b: dict[str, Any]) -> tuple[float, float, float, float]:
    """Una barra en el dibujo: x, y de arriba, ancho y alto."""
    return b["x"] + SX, b["y"], b["ancho"], BARRA_GROSOR if b["kind"] == "Y" else 0
