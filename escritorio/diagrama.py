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

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFrame, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QHBoxLayout, QLabel,
                               QToolButton, QWidget)

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


def _parcial(pid: str | None) -> str:
    """Parcial de un elemento; "" para el grafcet raíz (las etapas lo indican con None y las transiciones con "g")."""
    return "" if pid in (None, "g") else pid


def dibujar(scene: QGraphicsScene, M: dict[str, Any], S: dict[str, Any]) -> None:
    """M: estructura de la vista (Vista.model); S: estado observado (Vista.state())."""
    scene.clear()
    pt = _Pintor(scene)
    pos = {s["id"]: (s["x"] + SX, s["y"]) for s in M["steps"]}
    pos.update({m["id"]: (m["x"] + SX, m["y"]) for m in M.get("macros", [])})
    if not pos and not M["transitions"]:
        return
    min_x = min((p[0] for p in pos.values()), default=SX)
    # Enlace ascendente: por la izquierda del parcial de la transición, no de todo el dibujo
    left: dict[str, float] = {}
    for s in M["steps"]:
        k = _parcial(s.get("partial"))
        left[k] = min(left.get(k, pos[s["id"]][0]), pos[s["id"]][0])
    for m in M.get("macros", []):
        left[""] = min(left.get("", pos[m["id"]][0]), pos[m["id"]][0])
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
        pre = [pos[p] for p in t["pre"] if p in pos]
        post = [pos[p] for p in t["post"] if p in pos]
        if len(pre) > 1:  # sincronización: doble trazo sobre la transición
            xs, yy = [p[0] for p in pre], ty - 14
            pt.line(min(xs) - 8, yy, max(xs) + 8, yy, link, Z_LINK)
            pt.line(min(xs) - 8, yy - 4, max(xs) + 8, yy - 4, link, Z_LINK)
            for p in pre:
                pt.line(p[0], p[1] + H, p[0], yy - 4, link, Z_LINK)
            pt.line(tx, yy, tx, ty, link, Z_LINK)
        else:
            for p in pre:
                mid = (p[1] + H + ty) / 2
                pt.poly([(p[0], p[1] + H), (p[0], mid), (tx, mid), (tx, ty)], link, Z_LINK)
        down, up = [p for p in post if p[1] > ty], [p for p in post if p[1] <= ty]
        if len(down) > 1:  # divergencia simultánea: doble trazo bajo la transición
            xs, yy = [p[0] for p in down], ty + 14
            pt.line(tx, ty, tx, yy, link, Z_LINK)
            pt.line(min(xs) - 8, yy, max(xs) + 8, yy, link, Z_LINK)
            pt.line(min(xs) - 8, yy + 4, max(xs) + 8, yy + 4, link, Z_LINK)
            for p in down:
                pt.line(p[0], yy + 4, p[0], p[1] - H, link, Z_LINK)
        else:
            for p in down:
                mid = (ty + p[1] - H) / 2
                pt.poly([(tx, ty), (tx, mid), (p[0], mid), (p[0], p[1] - H)], link, Z_LINK)
        for p in up:  # enlace ascendente con flecha
            lx, top = min(left.get(_parcial(t.get("partial")), min_x), tx) - 70, p[1] - H - 16
            pt.poly([(tx, ty), (tx, ty + 14), (lx, ty + 14), (lx, top), (p[0], top), (p[0], p[1] - H)], link, Z_LINK)
            my = (ty + 14 + top) / 2
            pt.poly([(lx - 5, my + 6), (lx, my - 4), (lx + 5, my + 6)], None, Z_LINK, fill="text")
        if not pre:
            pt.line(tx, ty - 16, tx, ty, link, Z_LINK)  # transición fuente
        if not post:
            pt.line(tx, ty, tx, ty + 16, link, Z_LINK)  # transición sumidero
        color, width = "muted", 2.4
        if ob.get("validated"):
            color = "text"
        if ob.get("fireable"):
            color = "accent"
        if t["id"] in cleared:
            color, width = "glow", 3
        if blk and blk.get("element") == t["id"]:
            color, width = "err", 3
        tip = (f"Transición {t['id']}: validada {'sí' if ob.get('validated') else 'no'}, receptividad "
               f"{'verdadera' if ob.get('receptivity') else 'falsa'}"
               + ("; su parcial está forzado y no evoluciona" if ob.get("forced") else ""))
        pt.line(tx - TB, ty, tx + TB, ty, pt.pen(color, width), Z_BAR, tip)
        pt.text(tx - TB - 6, ty + 5, pt.seg(f"({t.get('label', t['id'])})"), 13, "muted", Z_BAR, "end", tip)
        w = pt.text(tx + TB + 8, ty + 5, t.get("cond"), 14, "text", Z_BAR, tip=tip)
        _estado_temporal(pt, tx + TB + 8 + w + (10 if w else 0), ty + 5, t.get("conditionRef"), tmp, Z_BAR, tip)
    for s in M["steps"]:
        x, y = pos[s["id"]]
        sid = s["id"]
        stale, act = bool(blk) and sid in situation, not blk and sid in situation
        cand = bool(blk) and sid in reached and not stale
        vir = sid in virtual and not act
        uns = not vir and not act and not stale and not cand and sid in unstable
        kind = {"enclosing": " (encapsulante)", "entry": " (entrada de la expansión)",
                "exit": " (salida de la expansión)"}.get(s["kind"], "")
        partial = f" · parcial {s['partial']}" if s.get("partial") else ""
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
        _acciones(pt, x, y, s["actions"], S, tmp)
    for m in M.get("macros", []):  # macroetapa: divisiones horizontales superior e inferior
        x, y = pos[m["id"]]
        act = bool((S.get("macros") or {}).get(m["id"]))
        tip = (f"Macroetapa {m['id']} (expansión {m['expansion']}): "
               + ("activa (alguna etapa de su expansión)" if act else "inactiva"))
        pt.rect(x - H, y - H, 2 * H, 2 * H, pt.pen("accent", 2.4) if act else pt.pen("text"), Z_STEP,
                "accent_soft" if act else "panel", tip)
        pt.line(x - H, y - H + MARK, x + H, y - H + MARK, pt.pen("text"), Z_STEP + 0.01, tip)
        pt.line(x - H, y + H - MARK, x + H, y + H - MARK, pt.pen("text"), Z_STEP + 0.01, tip)
        pt.text(x, y + 5, pt.seg(m["id"]), 16, "text", Z_STEP, "middle", tip)


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
            pt.text((b["x0"] + b["x1"]) / 2, b["y0"] + 5, pt.seg(p["ownerStep"]), 14, "text", Z_FRAME, "middle", halo=True)
            pt.text(b["x0"] + 30, b["y1"] + 5, pt.seg(p["label"]), 14, "text", Z_FRAME, halo=True)
        else:
            pt.rect(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"], pt.pen("muted", 1.2), Z_FRAME, radius=16)
            pt.text(b["x1"] - 30, b["y1"] + 5, pt.seg(p["label"]), 14, "text", Z_FRAME, "end", halo=True)


def _acciones(pt: _Pintor, x: float, y: float, actions: list[dict[str, Any]], S: dict[str, Any],
              tmp: dict[str, list[dict[str, Any]]]) -> None:
    """Acciones a la derecha de la etapa, del alto de la etapa y contiguas (representación (2) de la norma)."""
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
        if force:  # orden de forzado: rectángulo doble
            pt.rect(ax + 3, top + 3, w - 6, 2 * H - 6, pt.pen("virt" if on else "text", 1.2), Z_STEP - 0.01)
        mx = ax + 12
        mark = pt.pen("text")
        if a["kind"] == "continuous" and a.get("cond"):  # acción condicionada: trazo y condición
            pt.line(mx, top, mx, top - 14, mark, Z_STEP)
            w = pt.text(mx + 5, top - 4, a["cond"], 13, "text", Z_STEP)
            _estado_temporal(pt, mx + 5 + w + 8, top - 4, a.get("condRef"), tmp, Z_STEP)
        elif a.get("trigger") == "activation":  # memorizada al activar: flecha hacia arriba
            pt.line(mx, top, mx, top - 11, mark, Z_STEP)
            pt.poly([(mx - 5, top - 10), (mx, top - 19), (mx + 5, top - 10)], None, Z_STEP, fill="text")
        elif a.get("trigger") == "deactivation":  # memorizada al desactivar: flecha hacia abajo
            pt.line(mx, bottom, mx, bottom + 11, mark, Z_STEP)
            pt.poly([(mx - 5, bottom + 10), (mx, bottom + 19), (mx + 5, bottom + 10)], None, Z_STEP, fill="text")
        elif a.get("trigger") == "event":  # memorizada por evento: banderita y evento
            pt.line(mx, top, mx, top - 20, mark, Z_STEP)
            pt.poly([(mx, top - 20), (mx - 9, top - 15), (mx, top - 10)], None, Z_STEP, fill="text")
            w = pt.text(mx + 5, top - 11, a.get("event"), 13, "text", Z_STEP)
            _estado_temporal(pt, mx + 5 + w + 8, top - 11, a.get("condRef"), tmp, Z_STEP)
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
        """Flecha pegada a un borde del dibujo («derecha» o «abajo»): pliega el panel que hay al otro lado."""
        boton.setParent(self)
        boton.setStyleSheet(ESTILO_FLECHA)
        boton.setFixedSize(*((18, 54) if lugar == "derecha" else (54, 18)))
        boton.show()
        self._bordes.append((boton, lugar))
        self._colocar()

    def _colocar(self) -> None:
        w, h = self.width(), self.height()
        sb = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        self.barra.move(w - self.barra.width() - sb - 8, 8)
        for b, lugar in self._bordes:
            if lugar == "derecha":
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

    def mostrar(self, M: dict[str, Any], S: dict[str, Any]) -> None:
        centro = self.mapToScene(self.viewport().rect().center())  # al refrescar, la vista no se desplaza ni se reescala
        dibujar(self.scene(), M, S)
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-14, -14, 14, 14))
        if not self._manual:
            self.ajustar()
        else:
            self.centerOn(centro)

    def ajustar(self) -> None:
        self._manual = False
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
        if not self._manual:
            self.ajustar()
        self._colocar()

    def wheelEvent(self, event: Any) -> None:  # noqa: N802
        """La rueda (con o sin Ctrl) acerca o aleja alrededor del puntero; el dibujo se mueve arrastrándolo."""
        if not event.angleDelta().y():
            return
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.zoom(ZOOM_PASO if event.angleDelta().y() > 0 else 1 / ZOOM_PASO)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        event.accept()

    def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802
        self.ajustar()


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
