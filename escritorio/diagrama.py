"""Dibujo del grafcet con Qt: la misma notación y proporciones que tools/dibujo.js (tablas 1–11 de la norma).

Etapa cuadrada (doble si es inicial), transición como trazo corto con su designación entre paréntesis y su
receptividad (↑ ↓ · + y sobrerrayado), sincronización y divergencia simultánea con doble trazo, enlace
ascendente con flecha, y acciones del alto de la etapa: trazo con condición, flecha al activar o al desactivar,
banderita de evento. Jerarquía: macroetapa con divisiones horizontales unida a su expansión por trazos
discontinuos, encapsulante con las esquinas cortadas, «*» de enlace de activación, recinto con la encapsulante
arriba y su nombre abajo, parcial en marco redondeado y orden de forzado «G{…}» en rectángulo doble.

Las proporciones y convenciones se tomaron por inspección visual de las imágenes de la norma aportadas por el
usuario (fuente IMG del documento 02); no se copia ningún activo y el contraste con una copia íntegra sigue
pendiente (U-01). El estado (etapas activas, inestables, transiciones validadas o franqueables, bloqueos) lo da
el motor a través de grafcet.view.Vista; aquí solo se pinta.
"""
from __future__ import annotations

import html
from typing import Any

from grafcet.routing import TALLO_T, enlaces

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFrame, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QHBoxLayout, QLabel,
                               QMenu, QToolButton, QWidget)

SX = 100       # margen izquierdo del dibujo
H = 22         # semilado de la etapa cuadrada (unidad: lado = 2·H)
TB = 14        # semilongitud del trazo de transición (≈0,65 del lado)
ACT_LINK = 26  # enlace etapa–acción (≈0,6 del lado)
ACT_MIN = 80   # anchura mínima de una acción
MARK = 7       # divisiones de la macroetapa

# Colores del tema claro de tools/dibujo.css: el dibujo es negro sobre blanco, como en la norma
COL = {"panel": "#ffffff", "text": "#1d2330", "muted": "#6b7385", "accent": "#1f6feb", "accent_soft": "#dbe8ff",
       "ok": "#1a7f37", "err": "#c62828", "virt": "#8250df", "glow": "#e36209"}
FONT = "Arial"
Z_FRAME, Z_LINK, Z_BAR, Z_STEP = 0, 1, 2, 3


def _html(segs: list[dict[str, Any]] | None) -> str:
    """Segmentos {t, o: sobrerrayado (negación), s: subíndice} como texto enriquecido de Qt."""
    out = []
    for s in segs or []:
        t = html.escape(s["t"]).replace(" ", "&nbsp;")
        if s.get("s"):
            t = f"<sub>{t}</sub>"
        if s.get("o"):
            t = f'<span style="text-decoration: overline">{t}</span>'
        out.append(t)
    return "".join(out)


class _Pintor:
    def __init__(self, scene: QGraphicsScene) -> None:
        self.sc = scene

    @staticmethod
    def pen(color: str, width: float = 1.6, dash: tuple[float, float] | None = None) -> QPen:
        p = QPen(QColor(COL[color]), width)
        p.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        if dash:
            p.setDashPattern([d / width for d in dash])  # Qt mide el discontinuo en anchos de trazo
        return p

    @staticmethod
    def _put(item: Any, z: float, tip: str | None) -> Any:
        item.setZValue(z)
        if tip:
            item.setToolTip(tip)
        return item

    def line(self, x1: float, y1: float, x2: float, y2: float, pen: QPen, z: float, tip: str | None = None) -> None:
        self._put(self.sc.addLine(x1, y1, x2, y2, pen), z, tip)

    def poly(self, pts: list[tuple[float, float]], pen: QPen | None, z: float, fill: str | None = None,
             tip: str | None = None) -> None:
        path = QPainterPath(QPointF(*pts[0]))
        for p in pts[1:]:
            path.lineTo(*p)
        if fill:
            path.closeSubpath()
        self._put(self.sc.addPath(path, pen or QPen(Qt.PenStyle.NoPen),
                                  QBrush(QColor(COL[fill])) if fill else QBrush(Qt.BrushStyle.NoBrush)), z, tip)

    def rect(self, x: float, y: float, w: float, h: float, pen: QPen | None, z: float, fill: str | None = None,
             tip: str | None = None, radius: float = 0) -> None:
        brush = QBrush(QColor(COL[fill])) if fill else QBrush(Qt.BrushStyle.NoBrush)
        pen = pen or QPen(Qt.PenStyle.NoPen)
        if radius:
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, w, h), radius, radius)
            item = self.sc.addPath(path, pen, brush)
        else:
            item = self.sc.addRect(QRectF(x, y, w, h), pen, brush)
        self._put(item, z, tip)

    def circle(self, cx: float, cy: float, r: float, fill: str, z: float, tip: str | None = None) -> None:
        self._put(self.sc.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r), QPen(Qt.PenStyle.NoPen),
                                     QBrush(QColor(COL[fill]))), z, tip)

    def text(self, x: float, y: float, segs: list[dict[str, Any]] | None, size: int, color: str, z: float,
             anchor: str = "start", tip: str | None = None, bold: bool = False, halo: bool = False) -> float:
        """Texto con la línea base en y (como en SVG); devuelve su anchura."""
        if not segs:
            return 0.0
        font = QFont(FONT)
        font.setPixelSize(size)
        font.setBold(bold)
        item = QGraphicsTextItem()
        item.document().setDocumentMargin(0)
        item.setFont(font)
        item.setDefaultTextColor(QColor(COL[color]))
        item.setHtml(_html(segs))
        w = item.boundingRect().width()
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        top = y - QFontMetricsF(font).ascent()
        item.setPos(x0, top)
        self.sc.addItem(item)
        self._put(item, z + 0.02, tip)
        if halo:  # rótulo de marco: fondo blanco que corta el trazo, como paint-order en el SVG
            self.rect(x0 - 3, top - 1, w + 6, item.boundingRect().height() + 2, None, z + 0.01, "panel")
        return w

    def seg(self, t: str) -> list[dict[str, Any]]:
        return [{"t": t}]


def _temporizadores(S: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Temporizadores con algo que mostrar (contando o vencidos), por expresión que los contiene."""
    out: dict[str, list[dict[str, Any]]] = {}
    for t in (S.get("temporal") or {}).values():
        if t.get("shown"):
            out.setdefault(t["expr"], []).append(t)
    return out


def _estado_temporal(pt: _Pintor, x: float, y: float, ref: str | None, tmp: dict[str, list[dict[str, Any]]],
                     z: float, tip: str | None = None) -> None:
    """Estado de los temporizadores de una receptividad o condición: «1,2 s / 3 s» mientras cuenta y «3 s ✓» al vencer."""
    for t in tmp.get(ref or "", []):
        x += pt.text(x, y, pt.seg(t["shown"]), 12, "accent" if t["estado"] == "contando" else "ok", z, tip=tip,
                     bold=True) + 8


REJILLA = 20   # paso de la rejilla del editor (coordenadas del modelo)
ALTO_T = 14    # semialtura del área de una transición al editar (el trazo es fino: se acierta mejor así)
ANCLA = TALLO_T  # distancia de los puntos de unión de una transición a su centro: al final de su tramo recto, lejos del
                 # trazo, para que agarrar la transición la mueva y no saque una rama
ANCLA_S = 28   # ... y si ese lado es una simultaneidad (el punto queda fuera del doble trazo)
SIMUL = 14     # distancia del doble trazo de una simultaneidad al centro de la transición
RADIO_ANCLA = 14  # a qué distancia del puntero se marca un punto de unión (generoso: se agarra sin puntería)
Z_EDIT = 10    # selección, tiradores y marcas por encima de todo el dibujo


def posiciones(M: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Centro, en el dibujo, de cada etapa, macroetapa y transición."""
    pos = {s["id"]: (s["x"] + SX, s["y"]) for s in M["steps"]}
    pos.update({m["id"]: (m["x"] + SX, m["y"]) for m in M.get("macros", [])})
    pos.update({t["id"]: (t["x"] + SX, t["y"]) for t in M["transitions"]})
    return pos


def _segmento(M: dict[str, Any], pos: dict[str, tuple[float, float]], d: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    a, b = pos.get(d["from"]), pos.get(d["to"])
    return (a, b) if a and b else None


BARRA_GROSOR = 4   # separación de las dos líneas de una barra de simultaneidad


def barra(b: dict[str, Any]) -> tuple[float, float, float, float]:
    """Una barra en el dibujo: x, y de arriba, ancho y alto."""
    return b["x"] + SX, b["y"], b["ancho"], BARRA_GROSOR if b["kind"] == "Y" else 0


def anclas(M: dict[str, Any], ident: str) -> list[dict[str, Any]]:
    """Puntos de unión de un elemento: etapa y transición, arriba (entra el enlace) y abajo (sale)."""
    for b in M.get("bars", []):
        if b["id"] == ident:
            bx, by, w, h = barra(b)
            return [{"id": ident, "lado": "arriba", "pos": QPointF(bx + w / 2, by - 9)},
                    {"id": ident, "lado": "abajo", "pos": QPointF(bx + w / 2, by + h + 9)}]
    pos = posiciones(M)
    if ident not in pos:
        return []
    x, y = pos[ident]
    t = next((t for t in M["transitions"] if t["id"] == ident), None)
    arriba = H if t is None else ANCLA_S if t.get("simulPre") else ANCLA
    abajo = H if t is None else ANCLA_S if t.get("simulPost") else ANCLA
    return [{"id": ident, "lado": "arriba", "pos": QPointF(x, y - arriba)},
            {"id": ident, "lado": "abajo", "pos": QPointF(x, y + abajo)}]


def _distancia(p: QPointF, a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = max(0.0, min(1.0, ((p.x() - a[0]) * dx + (p.y() - a[1]) * dy) / ((dx * dx + dy * dy) or 1)))
    return ((p.x() - a[0] - k * dx) ** 2 + (p.y() - a[1] - k * dy) ** 2) ** 0.5


def ancla_en(M: dict[str, Any], p: QPointF, radio: float = RADIO_ANCLA) -> dict[str, Any] | None:
    """El punto de unión más cercano al puntero, si hay alguno a menos de `radio`."""
    best = None
    for ident in posiciones(M):
        for a in anclas(M, ident):
            d = ((a["pos"].x() - p.x()) ** 2 + (a["pos"].y() - p.y()) ** 2) ** 0.5
            if d <= radio and (best is None or d < best[0]):
                best = (d, a)
    for b in M.get("bars", []):  # en una barra, el punto de unión sigue al puntero a lo largo de su ancho
        bx, by, w, h = barra(b)
        if bx - 4 <= p.x() <= bx + w + 4:
            x = min(max(p.x(), bx), bx + w)
            for lado, y in (("arriba", by - 9), ("abajo", by + h + 9)):
                d = abs(p.y() - y)
                if d <= min(radio, 7) and (best is None or d < best[0]):
                    best = (d, {"id": b["id"], "lado": lado, "pos": QPointF(x, y)})
    return best[1] if best else None


def elemento_en(M: dict[str, Any], p: QPointF) -> str | None:
    """El elemento bajo un punto del dibujo: etapa, transición (su trazo) o enlace en borrador."""
    pos = posiciones(M)
    for t in M["transitions"]:  # el trazo, su designación a la izquierda y su receptividad a la derecha
        x, y = pos[t["id"]]
        ancho = 8 * sum(len(sg["t"]) for sg in (t.get("cond") or []))
        if -(TB + 44) <= p.x() - x <= TB + 12 + ancho and abs(p.y() - y) <= ALTO_T:
            return t["id"]
    for s in list(M["steps"]) + list(M.get("macros", [])):
        x, y = pos[s["id"]]
        if abs(p.x() - x) <= H + 4 and abs(p.y() - y) <= H + 4:
            return s["id"]
    for b in M.get("bars", []):
        bx, by, w, h = barra(b)
        if bx - 6 <= p.x() <= bx + w + 6 and by - 6 <= p.y() <= by + h + 6:
            return b["id"]
    for d in M.get("drafts", []):
        seg = _segmento(M, pos, d)
        if seg and _distancia(p, *seg) <= 6:
            return d["id"]
    for e in enlaces(M):  # los enlaces, al final: lo que hay encima manda
        if any(_distancia(p, a, b) <= 7 for a, b in zip(e["pts"], e["pts"][1:])):
            return e["id"]
    return None


def _realces(pt: _Pintor, M: dict[str, Any], sel: set[str], marcados: set[str]) -> None:
    """Edición: enlaces en borrador, elementos en cuestión (rojo discontinuo) y selección con sus tiradores."""
    pos = posiciones(M)
    for d in M.get("drafts", []):
        seg = _segmento(M, pos, d)
        if seg:
            (x1, y1), (x2, y2) = seg
            pt.line(x1, y1, x2, y2, pt.pen("err", 3 if d["id"] in sel else 1.8, (6, 4)), Z_EDIT,
                    "Enlace en borrador: une dos elementos del mismo tipo y no es ejecutable")
    trans = {t["id"] for t in M["transitions"]}
    rutas = {e["id"]: e for e in enlaces(M)}
    barras = {b["id"]: b for b in M.get("bars", [])}
    for ident, color, width in [(i, "err", 1.8) for i in marcados] + [(i, "accent", 1.6) for i in sel]:
        if ident in rutas:  # un enlace seleccionado se remarca a lo largo de su recorrido
            pt.poly([(float(x), float(y)) for x, y in rutas[ident]["pts"]], pt.pen("accent", 4), Z_EDIT)
            for h in rutas[ident]["handles"]:
                x, y = h["pos"]
                pt.rect(x-5, y-5, 10, 10, pt.pen("accent", 1.5), Z_EDIT+1, "panel",
                        "Arrastre este cuadrado para recolocar el tramo")
            for f in rutas[ident]["arrows"]:
                pt.poly(f["pts"], None, Z_EDIT+2, fill="accent", tip="Arrastre la flecha a lo largo del enlace")
            continue
        if ident in barras:
            bx, by, w, h = barra(barras[ident])
            pt.rect(bx - 5, by - 7, w + 10, h + 14, pt.pen(color, width, (5, 3)), Z_EDIT)
            if color == "accent":  # tiradores en los extremos: se estira de ellos
                for cx in (bx, bx + w):
                    pt.rect(cx - 4, by + h / 2 - 4, 8, 8, pt.pen("accent", 1.4), Z_EDIT + 0.1, "panel")
            continue
        if ident not in pos:
            continue
        x, y = pos[ident]
        hx, hy = (TB + 6, ALTO_T) if ident in trans else (H + 6, H + 6)
        pt.rect(x - hx, y - hy, 2 * hx, 2 * hy, pt.pen(color, width, (5, 3)), Z_EDIT)
        if color == "accent":  # tiradores en las esquinas
            for cx, cy in ((x - hx, y - hy), (x + hx, y - hy), (x - hx, y + hy), (x + hx, y + hy)):
                pt.rect(cx - 3, cy - 3, 6, 6, pt.pen("accent", 1), Z_EDIT + 0.1, "panel")


def dibujar(scene: QGraphicsScene, M: dict[str, Any], S: dict[str, Any], sel: set[str] | None = None,
            marcados: set[str] | None = None) -> list[dict[str, Any]]:
    """M: estructura de la vista (Vista.model); S: estado observado (Vista.state()); sel y marcados, solo al editar:
    los elementos seleccionados y los que tienen un diagnóstico. Devuelve dónde ha quedado cada acción
    ({id, etapa, rect}), para que el editor las encuentre con el ratón."""
    scene.clear()
    cajas: list[dict[str, Any]] = []
    pt = _Pintor(scene)
    nombre = M.get("names", {}).get  # los ID internos nunca se muestran: etapas, parciales y macroetapas, por su nombre
    pos = {s["id"]: (s["x"] + SX, s["y"]) for s in M["steps"]}
    pos.update({m["id"]: (m["x"] + SX, m["y"]) for m in M.get("macros", [])})
    if not pos and not M["transitions"]:
        return cajas
    # Enlace ascendente: por la izquierda del parcial de la transición, no de todo el dibujo
    situation, virtual = set(S.get("situation") or []), set(S.get("virtual") or [])
    unstable, cleared = set(S.get("unstable") or []), set(S.get("lastCleared") or [])
    blk = S.get("blocked")
    reached = set(blk["reached"]) if blk else set()
    _marcos(pt, M, pos)
    tmp = _temporizadores(S)
    link = pt.pen("text")
    for t in M["transitions"]:
        tx, ty = t["x"] + SX, t["y"]
        ob = (S.get("transitions") or {}).get(t["id"], {})
        pre = [pos[p] for p in t.get("preDib", t["pre"]) if p in pos]
        post = [pos[p] for p in t.get("postDib", t["post"]) if p in pos]
        if len(pre) > 1 or t.get("simulPre"):
            xs, yy = [p[0] for p in pre] + [tx], ty - SIMUL
            pt.line(min(xs) - 8, yy, max(xs) + 8, yy, link, Z_LINK)
            pt.line(min(xs) - 8, yy - 4, max(xs) + 8, yy - 4, link, Z_LINK)
            pt.line(tx, yy, tx, ty, link, Z_LINK)
        if t.get("simulPost"):
            xs, yy = [p[0] for p in post] + [tx], ty + SIMUL
            pt.line(tx, ty, tx, yy, link, Z_LINK)
            pt.line(min(xs) - 8, yy, max(xs) + 8, yy, link, Z_LINK)
            pt.line(min(xs) - 8, yy + 4, max(xs) + 8, yy + 4, link, Z_LINK)
        if not pre:
            pt.line(tx, ty - TALLO_T, tx, ty, link, Z_LINK)  # transición fuente: su tramo recto es parte de ella
        if not post:
            pt.line(tx, ty, tx, ty + TALLO_T, link, Z_LINK)  # transición sumidero
        color, width = "muted", 2.4
        if ob.get("validated"):
            color = "text"
        if ob.get("fireable"):
            color = "accent"
        if t["id"] in cleared:
            color, width = "glow", 3
        if blk and blk.get("element") == t["id"]:
            color, width = "err", 3
        tip = (f"Transición {t.get('label', t['id'])}: validada {'sí' if ob.get('validated') else 'no'}, receptividad "
               f"{'verdadera' if ob.get('receptivity') else 'falsa'}"
               + ("; su parcial está forzado y no evoluciona" if ob.get("forced") else ""))
        pt.line(tx - TB, ty, tx + TB, ty, pt.pen(color, width), Z_BAR, tip)
        if t.get("showLabel", True):
            pt.text(tx - TB - 6, ty + 5, pt.seg(f"({t.get('label', t['id'])})"), 13, "muted", Z_BAR, "end", tip)
        w = pt.text(tx + TB + 8, ty + 5, t.get("cond"), 14, "text", Z_BAR, tip=tip)
        _estado_temporal(pt, tx + TB + 8 + w + (10 if w else 0), ty + 5, t.get("conditionRef"), tmp, Z_BAR, tip)
    for b in M.get("bars", []):  # barras de simultaneidad (doble trazo) y de alternativa (trazo simple), con sus conectores
        bx, by, w, h = barra(b)
        tipo = "Simultaneidad" if b["kind"] == "Y" else "Alternativa"
        pt.line(bx, by, bx + w, by, link, Z_LINK + 0.5, tipo)
        if b["kind"] == "Y":
            pt.line(bx, by + h, bx + w, by + h, link, Z_LINK + 0.5, tipo)
    for e in enlaces(M):
        pt.poly([(float(x), float(y)) for x, y in e["pts"]], link, Z_LINK)
        for flecha in e["arrows"]:
            pt.poly(flecha["pts"], None, Z_LINK + 0.1, fill="text")
    for s in M["steps"]:
        x, y = pos[s["id"]]
        sid = s["id"]
        stale, act = bool(blk) and sid in situation, not blk and sid in situation
        cand = bool(blk) and sid in reached and not stale
        vir = sid in virtual and not act
        uns = not vir and not act and not stale and not cand and sid in unstable
        kind = {"enclosing": " (encapsulante)", "entry": " (entrada de la expansión)",
                "exit": " (salida de la expansión)"}.get(s["kind"], "")
        partial = f" · parcial {nombre(s['partial'], s['partial'])}" if s.get("partial") else ""
        tip = (f"Etapa {s.get('label', sid)}{' (inicial)' if s['initial'] else ''}{kind}{partial}"
               f"{' · enlace de activación' if s.get('activation') else ''}: "
               + ("último estado estable conservado" if stale else "alcanzada antes del punto en cuestión, sin confirmar"
                  if cand else "activa" if act else "inestable (en recorrido)" if vir
                  else "fue inestable en el último instante" if uns else "inactiva"))
        outer = pt.pen("text")
        if act:
            outer = pt.pen("accent", 2.4)
        if vir or uns:
            outer = pt.pen("virt", 2, (5, 4))
        if stale:
            outer = pt.pen("muted", 2, (2, 3))
        if cand:
            outer = pt.pen("glow", 2.2, (6, 4))
        pt.rect(x - H, y - H, 2 * H, 2 * H, outer, Z_STEP, "accent_soft" if act else "panel", tip)
        if s["initial"]:
            pt.rect(x - H + 4, y - H + 4, 2 * H - 8, 2 * H - 8, pt.pen("text"), Z_STEP + 0.01, None, tip)
        if s["kind"] == "enclosing":  # encapsulante: esquinas cortadas; si es inicial, las del cuadrado interior
            h = H - 4 if s["initial"] else H
            c = round(0.22 * 2 * h)
            x0, x1, y0, y1 = x - h, x + h, y - h, y + h
            for a, b in (((x0 + c, y0), (x0, y0 + c)), ((x1 - c, y0), (x1, y0 + c)),
                         ((x0, y1 - c), (x0 + c, y1)), ((x1, y1 - c), (x1 - c, y1))):
                pt.line(*a, *b, pt.pen("text"), Z_STEP + 0.01, tip)
        pt.text(x, y + 3, pt.seg(s.get("label", sid)), 16, "text", Z_STEP, "middle", tip)
        if s.get("activation"):
            pt.text(x - H - 5, y + 5, pt.seg("*"), 18, "text", Z_STEP, "end", tip, bold=True)
        if act:
            pt.circle(x, y + 12, 3.5, "accent", Z_STEP + 0.05, tip)
        for flag, label, color in ((vir, "inestable", "virt"), (uns, "fue inestable", "virt"),
                                   (stale, "último estable", "muted"), (cand, "alcanzada, sin confirmar", "glow")):
            if flag:
                pt.text(x, y + H + 13, pt.seg(label), 10, color, Z_STEP, "middle", tip)
        _acciones(pt, x, y, s["actions"], S, tmp, cajas, s["id"], {i for i in (sel or set()) if i.startswith("accion:")})
    for m in M.get("macros", []):  # macroetapa: divisiones horizontales superior e inferior
        x, y = pos[m["id"]]
        act = bool((S.get("macros") or {}).get(m["id"]))
        tip = (f"Macroetapa {nombre(m['id'], m['id'])} (expansión {nombre(m['expansion'], m['expansion'])}): "
               + ("activa (alguna etapa de su expansión)" if act else "inactiva"))
        pt.rect(x - H, y - H, 2 * H, 2 * H, pt.pen("accent", 2.4) if act else pt.pen("text"), Z_STEP,
                "accent_soft" if act else "panel", tip)
        pt.line(x - H, y - H + MARK, x + H, y - H + MARK, pt.pen("text"), Z_STEP + 0.01, tip)
        pt.line(x - H, y + H - MARK, x + H, y + H - MARK, pt.pen("text"), Z_STEP + 0.01, tip)
        pt.text(x, y + 5, pt.seg(nombre(m["id"], m["id"])), 16, "text", Z_STEP, "middle", tip)
    if sel or marcados or M.get("drafts"):
        _realces(pt, M, set(sel or ()), set(marcados or ()))
    return cajas


def _marcos(pt: _Pintor, M: dict[str, Any], pos: dict[str, tuple[float, float]]) -> None:
    """Parciales según las figuras de la norma: recinto (marco continuo, encapsulante arriba y nombre abajo),
    parcial (marco redondeado con su nombre; un hijo dentro de su padre) y expansión (trazos discontinuos de la
    macroetapa a su entrada y a su salida, sin marco)."""
    parts = M.get("partials") or []
    box: dict[str, dict[str, float] | None] = {}

    def own(pid: str) -> list[tuple[float, float]]:
        return ([pos[s["id"]] for s in M["steps"] if s.get("partial") == pid]
                + [(t["x"] + SX, t["y"]) for t in M["transitions"] if t.get("partial") == pid])

    def frame(pid: str) -> dict[str, float] | None:
        if pid in box:
            return box[pid]
        pts = own(pid)
        b = ({"x0": min(p[0] for p in pts) - H - 26, "x1": max(p[0] for p in pts) + H + 70,
              "y0": min(p[1] for p in pts) - H - 22, "y1": max(p[1] for p in pts) + H + 22} if pts else None)
        for c in parts:
            if c.get("owner") == pid and c["kind"] == "partial":
                cb = frame(c["id"])
                if not cb:
                    continue
                e = {"x0": cb["x0"] - 12, "x1": cb["x1"] + 12, "y0": cb["y0"] - 12, "y1": cb["y1"] + 16}
                b = e if b is None else {"x0": min(b["x0"], e["x0"]), "x1": max(b["x1"], e["x1"]),
                                         "y0": min(b["y0"], e["y0"]), "y1": max(b["y1"], e["y1"])}
        box[pid] = b
        return b

    for p in parts:
        if p["kind"] == "expansion":
            m = next((x for x in M.get("macros", []) if x["id"] == p.get("macro")), None)
            if not m or m["entry"] not in pos or m["exit"] not in pos:
                continue
            (mx, my), (ex, ey), (sx, sy) = pos[m["id"]], pos[m["entry"]], pos[m["exit"]]
            dash = pt.pen("muted", 1.2, (5, 4))
            pt.line(mx + H, my - H, ex - H, ey - H, dash, Z_FRAME)
            pt.line(mx + H, my + H, sx - H, sy + H, dash, Z_FRAME)
            continue
        b = frame(p["id"])
        if not b:
            continue
        if p["kind"] == "enclosure":
            pt.rect(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"], pt.pen("text"), Z_FRAME)
            pt.text((b["x0"] + b["x1"]) / 2, b["y0"] + 5, pt.seg(M.get("names", {}).get(p["ownerStep"], p["ownerStep"])), 14, "text", Z_FRAME,
                    "middle", halo=True)
            pt.text(b["x0"] + 30, b["y1"] + 5, pt.seg(p["label"]), 14, "text", Z_FRAME, halo=True)
        else:
            pt.rect(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"], pt.pen("muted", 1.2), Z_FRAME, radius=16)
            pt.text(b["x1"] - 30, b["y1"] + 5, pt.seg(p["label"]), 14, "text", Z_FRAME, "end", halo=True)


def _acciones(pt: _Pintor, x: float, y: float, actions: list[dict[str, Any]], S: dict[str, Any],
              tmp: dict[str, list[dict[str, Any]]], cajas: list[dict[str, Any]] | None = None, etapa: str = "",
              marcadas: set[str] = frozenset()) -> None:
    """Acciones a la derecha de la etapa, del alto de la etapa y contiguas (representación (2) de la norma). Anota
    en `cajas` el rectángulo de cada una; las de `marcadas` («accion:ID», al editar) se resaltan."""
    if not actions:
        return
    ax = x + H + ACT_LINK
    pt.line(x + H, y, ax, y, pt.pen("text"), Z_STEP)
    top, bottom = y - H, y + H
    for a in actions:
        force = a["kind"] == "force"
        if a["kind"] == "continuous":
            on = bool(((S.get("outputs") or {}).get(a["target"]) or {}).get("value"))
        else:
            on = force and any(f["order"] == a["id"] for f in S.get("forces") or [])
        w = max(ACT_MIN, pt.text(ax + 12, y + 5, a["text"], 15, "text", Z_STEP) + 24)
        outer = (pt.pen("virt", 2.2) if force else pt.pen("ok", 2.6)) if on else pt.pen("text")
        pt.rect(ax, top, w, 2 * H, outer, Z_STEP - 0.02, "panel")
        if cajas is not None and not force:
            cajas.append({"id": a["id"], "etapa": etapa, "rect": (ax, top, w, 2 * H)})
        if f"accion:{a.get('id')}" in marcadas:
            pt.rect(ax - 3, top - 3, w + 6, 2 * H + 6, pt.pen("accent", 1.6, (5, 3)), Z_EDIT)
        if force:  # orden de forzado: rectángulo doble
            pt.rect(ax + 3, top + 3, w - 6, 2 * H - 6, pt.pen("virt" if on else "text", 1.2), Z_STEP - 0.01)
        mx = ax + 12
        mark = pt.pen("text")
        if a["kind"] == "continuous" and a.get("cond"):  # acción condicionada: trazo y condición
            pt.line(mx, top, mx, top - 14, mark, Z_STEP)
            wc = pt.text(mx + 5, top - 4, a["cond"], 13, "text", Z_STEP)  # el ancho de la caja no cambia
            _estado_temporal(pt, mx + 5 + wc + 8, top - 4, a.get("condRef"), tmp, Z_STEP)
        elif a.get("trigger") == "activation":  # memorizada al activar: flecha hacia arriba
            pt.line(mx, top, mx, top - 11, mark, Z_STEP)
            pt.poly([(mx - 5, top - 10), (mx, top - 19), (mx + 5, top - 10)], None, Z_STEP, fill="text")
        elif a.get("trigger") == "deactivation":  # memorizada al desactivar: flecha hacia abajo
            pt.line(mx, bottom, mx, bottom + 11, mark, Z_STEP)
            pt.poly([(mx - 5, bottom + 10), (mx, bottom + 19), (mx + 5, bottom + 10)], None, Z_STEP, fill="text")
        elif a.get("trigger") == "event":  # memorizada por evento: banderita y evento
            pt.line(mx, top, mx, top - 20, mark, Z_STEP)
            pt.poly([(mx, top - 20), (mx - 9, top - 15), (mx, top - 10)], None, Z_STEP, fill="text")
            we = pt.text(mx + 5, top - 11, a.get("event"), 13, "text", Z_STEP)
            _estado_temporal(pt, mx + 5 + we + 8, top - 11, a.get("condRef"), tmp, Z_STEP)
        ax += w


ZOOM_MIN, ZOOM_MAX, ZOOM_PASO = 0.1, 8.0, 1.15
ESTILO_FLECHA = ("QToolButton { background: rgba(255,255,255,215); border: 1px solid #c3c9d6; border-radius: 4px; "
                 "color: #1d2330; font-size: 13px } QToolButton:hover { background: #dbe8ff }")


class VistaDiagrama(QGraphicsView):
    """Vista del dibujo. Se ajusta a la ventana hasta que se hace zoom; desde entonces el zoom se mantiene al
    refrescar y solo «Ajustar» (o el doble clic) vuelve a encajar el dibujo. La rueda acerca o aleja."""

    zoomCambiado = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setBackgroundBrush(QColor(COL["panel"]))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._manual = False
        self._bordes: list[tuple[QWidget, str]] = []
        self._barra_zoom()
        self.controlador: Any = None  # al editar: recibe prensar / mover / soltar / doble con puntos del dibujo
        self.rejilla = False
        self.area_minima: QRectF | None = None
        self.goma = None  # línea provisional de un enlace que se está trazando
        self._marcas: list[Any] = []
        self._origen = False  # en edición, hasta que se usa el ratón, el dibujo se queda arriba a la izquierda

    def modo_edicion(self, on: bool, controlador: Any = None) -> None:
        """Al editar: sin arrastre de mano, rejilla, un área fija (el dibujo no se recoloca al añadir elementos) y el
        zoom manual; al simular, el comportamiento de siempre."""
        self.controlador = controlador if on else None
        self.rejilla = on
        self.area_minima = QRectF(0, 0, 1100, 760) if on else None
        self.setDragMode(QGraphicsView.DragMode.NoDrag if on else QGraphicsView.DragMode.ScrollHandDrag)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop if on else Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(on)
        self.setAcceptDrops(on)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)
        if on:
            self.resetTransform()
            self._origen = True  # el primer dibujo en edición empieza arriba a la izquierda
            self._manual = True
            self._notificar()
        else:
            self._manual = False
            self._origen = False
        self.goma = None

    def marcar_anclas(self, anclas_: list[dict[str, Any]], destacada: dict[str, Any] | None = None) -> None:
        """Puntos de unión del elemento bajo el puntero; el más cercano, resaltado (como el ajuste a puntos del CAD)."""
        for it in getattr(self, "_marcas", []):
            if it.scene() is self.scene():
                self.scene().removeItem(it)
        self._marcas = []
        for a in anclas_:
            r = 6 if destacada and a["id"] == destacada["id"] and a["lado"] == destacada["lado"] else 4
            it = self.scene().addEllipse(a["pos"].x() - r, a["pos"].y() - r, 2 * r, 2 * r, _Pintor.pen("accent", 1.6),
                                         QBrush(QColor(COL["accent"] if r == 6 else COL["panel"])))
            it.setZValue(Z_EDIT + 2)
            self._marcas.append(it)

    def trazo_provisional(self, a: QPointF | None, b: QPointF | None = None) -> None:
        """Línea de ayuda mientras se traza un enlace (None la quita)."""
        if self.goma is not None and self.goma.scene() is self.scene():
            self.scene().removeItem(self.goma)
        self.goma = None
        if a is not None and b is not None:
            self.goma = self.scene().addLine(a.x(), a.y(), b.x(), b.y(), _Pintor.pen("accent", 2, (6, 4)))
            self.goma.setZValue(Z_EDIT + 1)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        if not self.rejilla or self.escala() < 0.45:
            return
        painter.setPen(QPen(QColor("#e3e6ec"), 0))
        x0 = int(rect.left() // REJILLA) * REJILLA + (SX % REJILLA)
        y0 = int(rect.top() // REJILLA) * REJILLA
        for gx in range(x0, int(rect.right()) + 1, REJILLA):
            for gy in range(y0, int(rect.bottom()) + 1, REJILLA):
                painter.drawPoint(gx, gy)

    def _evento(self, nombre: str, event: Any) -> bool:
        if self.controlador is None or event.button() != Qt.MouseButton.LeftButton and nombre != "mover":
            return False
        return bool(getattr(self.controlador, nombre)(self.mapToScene(event.position().toPoint()), event))

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self._origen = False
        if not self._evento("prensar", event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if not self._evento("mover", event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if not self._evento("soltar", event):
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: Any) -> None:  # noqa: N802
        """Al editar, el botón derecho ofrece lo que se puede hacer con lo que hay debajo (añadir acción, editarla…)."""
        opciones = self.controlador.menu(self.mapToScene(event.pos())) if self.controlador is not None else []
        if not opciones:
            super().contextMenuEvent(event)
            return
        menu = QMenu(self)
        for texto, accion in opciones:
            menu.addAction(texto, accion)
        menu.exec(event.globalPos())

    def _barra_zoom(self) -> None:
        """Controles del zoom sobre el dibujo, arriba a la derecha: «−», porcentaje, «+» y «Ajustar»."""
        self.barra = QFrame(self)
        self.barra.setStyleSheet("QFrame { background: rgba(255,255,255,215); border: 1px solid #c3c9d6; "
                                 "border-radius: 4px } QToolButton { border: none; padding: 2px 7px; font-size: 14px } "
                                 "QToolButton:hover { background: #dbe8ff } QLabel { border: none; min-width: 42px }")
        lay = QHBoxLayout(self.barra)
        lay.setContentsMargins(3, 2, 3, 2)
        lay.setSpacing(0)
        self.b_menos = QToolButton()
        self.b_menos.setText("−")
        self.b_menos.setToolTip("Alejar (Ctrl+−)")
        self.b_menos.clicked.connect(self.alejar)
        self.l_zoom = QLabel("100 %")
        self.l_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.b_mas = QToolButton()
        self.b_mas.setText("+")
        self.b_mas.setToolTip("Acercar (Ctrl+=)")
        self.b_mas.clicked.connect(self.acercar)
        self.b_ajustar = QToolButton()
        self.b_ajustar.setText("Ajustar")
        self.b_ajustar.setToolTip("Encajar el dibujo en la ventana (Ctrl+0 o doble clic)")
        self.b_ajustar.clicked.connect(self.ajustar)
        for w in (self.b_menos, self.l_zoom, self.b_mas, self.b_ajustar):
            lay.addWidget(w)
        self.barra.adjustSize()

    def borde(self, boton: QToolButton, lugar: str) -> None:
        """Flecha pegada a un borde del dibujo («izquierda», «derecha» o «abajo»): pliega el panel que hay al otro lado."""
        boton.setParent(self)
        boton.setStyleSheet(ESTILO_FLECHA)
        boton.setFixedSize(*((54, 18) if lugar == "abajo" else (18, 54)))
        boton.show()
        self._bordes.append((boton, lugar))
        self._colocar()

    def _colocar(self) -> None:
        w, h = self.width(), self.height()
        sb = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        self.barra.move(w - self.barra.width() - sb - 8, 8)
        for b, lugar in self._bordes:
            if lugar == "izquierda":
                b.move(0, (h - b.height()) // 2)
            elif lugar == "derecha":
                b.move(w - b.width() - sb, (h - b.height()) // 2)
            else:
                b.move((w - b.width()) // 2, h - b.height() - sh)
            b.raise_()
        self.barra.raise_()

    def escala(self) -> float:
        return self.transform().m11()

    def _notificar(self) -> None:
        self.l_zoom.setText(f"{round(self.escala() * 100)} %")
        self.zoomCambiado.emit(self.escala())

    def mostrar(self, M: dict[str, Any], S: dict[str, Any], sel: set[str] | None = None,
                marcados: set[str] | None = None) -> None:
        hb, vb = self.horizontalScrollBar().value(), self.verticalScrollBar().value()  # al refrescar, no se desplaza
        if self._origen:
            hb = vb = 0
        self.goma = None
        self._marcas = []
        self.cajas_acciones = dibujar(self.scene(), M, S, sel, marcados)
        r = self.scene().itemsBoundingRect().adjusted(-14, -14, 14, 14)
        self.scene().setSceneRect(r.united(self.area_minima) if self.area_minima else r)
        if not self._manual:
            self.ajustar()
        else:
            self.horizontalScrollBar().setValue(hb)
            self.verticalScrollBar().setValue(vb)

    def ajustar(self) -> None:
        self._manual = self.controlador is not None  # al editar, el zoom no se recoloca solo
        r = self.scene().sceneRect()
        if r.width() <= 0 or r.height() <= 0:
            return
        self.resetTransform()
        k = min(self.viewport().width() / r.width(), self.viewport().height() / r.height(), 1.6)
        self.scale(k, k)
        self._notificar()

    def zoom(self, factor: float) -> None:
        """Zoom manual: queda fijo hasta «Ajustar» o doble clic."""
        k = min(max(self.escala() * factor, ZOOM_MIN), ZOOM_MAX) / self.escala()
        self._manual = True
        self.scale(k, k)
        self._notificar()

    def acercar(self) -> None:
        self.zoom(ZOOM_PASO)

    def alejar(self) -> None:
        self.zoom(1 / ZOOM_PASO)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._origen:
            self.horizontalScrollBar().setValue(0)
            self.verticalScrollBar().setValue(0)
        if not self._manual:
            self.ajustar()
        self._colocar()

    def wheelEvent(self, event: Any) -> None:  # noqa: N802
        """La rueda (con o sin Ctrl) acerca o aleja alrededor del puntero; el dibujo se mueve arrastrándolo."""
        self._origen = False
        if not event.angleDelta().y():
            return
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.zoom(ZOOM_PASO if event.angleDelta().y() > 0 else 1 / ZOOM_PASO)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        event.accept()

    def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802
        if self.controlador is not None:
            if self._evento("doble", event):
                return
        else:
            self.ajustar()

    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802
        if self.controlador is not None and event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: Any) -> None:  # noqa: N802
        if self.controlador is not None and event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: Any) -> None:  # noqa: N802
        """Un elemento arrastrado desde la paleta se coloca donde se suelta."""
        if self.controlador is not None and event.mimeData().hasText():
            self.controlador.colocar(event.mimeData().text(), self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()

    def centrar_en(self, p: QPointF) -> None:
        self.centerOn(p)


def imagen(M: dict[str, Any], S: dict[str, Any], escala: float = 2.0) -> QImage:
    """El dibujo como imagen (para pruebas y para guardar una figura)."""
    scene = QGraphicsScene()
    dibujar(scene, M, S)
    r = scene.itemsBoundingRect().adjusted(-14, -14, 14, 14)
    img = QImage(max(1, int(r.width() * escala)), max(1, int(r.height() * escala)), QImage.Format.Format_ARGB32)
    img.fill(QColor(COL["panel"]))
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    scene.render(p, QRectF(0, 0, img.width(), img.height()), r)
    p.end()
    return img
