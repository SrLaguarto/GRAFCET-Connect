"""Dibujo del grafcet con Qt: la misma notación y proporciones que tools/dibujo.js (tablas 1–11 de la norma).

Etapa cuadrada (doble si es inicial), transición como trazo corto con su designación entre paréntesis y su
receptividad (↑ ↓ · + y sobrerrayado), sincronización y divergencia simultánea con doble trazo, enlace
ascendente con flecha, y acciones del alto de la etapa: trazo con condición, flecha al activar o al desactivar,
banderita de evento. Jerarquía: macroetapa con divisiones horizontales, encapsulante con las esquinas cortadas,
«*» de enlace de activación, recinto con la encapsulante arriba y su nombre abajo, parcial en marco redondeado y orden
de forzado «G{…}» en rectángulo doble. Las dependencias (la macroetapa unida a su expansión y la encapsulante unida a sus
recintos, por trazos discontinuos) solo se dibujan con la opción `dependencias` («Mostrar dependencias»).

Las proporciones y convenciones se tomaron por inspección visual de las imágenes de la norma aportadas por el
usuario (fuente IMG del documento 02); no se copia ningún activo y el contraste con una copia íntegra sigue
pendiente (U-01). El estado (etapas activas, inestables, transiciones validadas o franqueables, bloqueos) lo da
el motor a través de grafcet.view.Vista; aquí solo se pinta.
"""
from __future__ import annotations

import html
from typing import Any

from grafcet.routing import NORMAL, SENTIDO, TALLO_T, enlaces, orientacion, punto_t

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QIcon, QImage, QPainter, QPainterPath, QPen,
                           QPalette, QPixmap, QRegion)
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QListWidget, QHBoxLayout, QLabel,
                               QMenu, QProxyStyle, QPushButton, QStyle, QStyledItemDelegate, QStyleOptionComboBox, QStyleOptionViewItem, QStylePainter,
                               QToolButton, QWidget)

from . import estilo

SX = 100       # margen izquierdo del dibujo
H = 22         # semilado de la etapa cuadrada (unidad: lado = 2·H)
TB = 8         # trazo de transición de 16 px frente al lado de etapa de 44 px
ACT_LINK = 26  # enlace etapa–acción (≈0,6 del lado)
ACT_MIN = 80   # anchura mínima de una acción
MARK = 7       # divisiones de la macroetapa
ACT_GAP = 36   # entre cajas de acción de una fila separada
ACT_BUS = 28   # de la línea común de una fila separada, por debajo de las cajas
ACT_COL = 12   # separación mínima entre cajas de una columna (crece lo que piden sus marcas)
ACT_CANAL = 7  # de la derivación a la segunda columna de una matriz, por debajo de su fila

# Colores del tema claro de tools/dibujo.css: el dibujo es negro sobre blanco, como en la norma
COL = {"readout": "#326dcb","panel": "#ffffff", "text": "#1d2330", "muted": "#6b7385", "accent": "#1f6feb", "accent_soft": "#dbe8ff",
       "ok": "#1a7f37", "active": "#40d641", "active_soft": "#e4f9e4", "true_text": "#40d641", "history": "#1a7f1b", "err": "#c62828", "aviso": "#eeb445", "virt": "#8250df", "glow": "#e36209"}
FONT = "Arial"
Z_FRAME, Z_LINK, Z_BAR, Z_STEP = 0, 1, 2, 3
ANCHO_COMENTARIO = 190  # ancho máximo de un comentario antes de pasar a otra línea
GROSOR_NEGADO = 1.25     # grosor de la barra de una variable negada (Qt no deja regular el del sobrerrayado del texto)
TMR_TAM = 10            # tamaño del tiempo transcurrido de un temporizador, que se dibuja encima de su duración
TMR_EXTRA = 12          # lo que sube por encima de la condición o el evento de una acción con temporizador
MARGEN_MARCO_X = 26     # lo que se separa el marco de un parcial de todo lo que dibuja de él, a izquierda y derecha...
MARGEN_MARCO_Y = 22     # ... y por arriba y por abajo (el mismo de siempre alrededor de sus etapas)
_ANCHOS: dict[tuple[Any, ...], float] = {}  # lo que mide cada texto (`_Pintor.ancho`): los marcos lo piden a cada movimiento del ratón


def _html(segs: list[dict[str, Any]] | None, sobrerrayado: bool = True, verdaderos: set[str] | None = None) -> str:
    """Segmentos {t, o: sobrerrayado (negación), s: subíndice} como texto enriquecido de Qt. Con `sobrerrayado` (una
    etiqueta de la interfaz, que no puede dibujar nada más) la negación es el sobrerrayado del texto, de 1 px; el dibujo
    lo pide sin él y pinta la barra aparte (`_Pintor.text`), de `GROSOR_NEGADO`."""
    out = []
    for s in segs or []:
        t = html.escape(s["t"]).replace(" ", "&nbsp;")
        if s.get("s"):
            t = f"<sub>{t}</sub>"
        if s.get("o") and sobrerrayado:
            t = f'<span style="text-decoration: overline">{t}</span>'
        if verdaderos and any(k in verdaderos for k in s.get("eval", [])):
            t = f'<span style="color:{COL["true_text"]}">{t}</span>'
        out.append(t)
    return "".join(out)


def _negados(segs: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Tramos [i, j) de segmentos negados seguidos: la barra de la negación cubre cada tramo de una vez, aunque lleve
    subíndices o signos dentro."""
    out: list[tuple[int, int]] = []
    for i, s in enumerate(segs):
        if s.get("o"):
            if out and out[-1][1] == i:
                out[-1] = (out[-1][0], i + 1)
            else:
                out.append((i, i + 1))
    return out


class _Pintor:
    def __init__(self, scene: QGraphicsScene) -> None:
        self.sc = scene
        self.verdaderos: set[str] = set()
        self.parcial = None

    @staticmethod
    def pen(color: str, width: float = 1.6, dash: tuple[float, float] | None = None) -> QPen:
        p = QPen(QColor(COL[color]), width)
        p.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        if dash:
            p.setDashPattern([d / width for d in dash])  # Qt mide el discontinuo en anchos de trazo
        return p

    def _put(self, item: Any, z: float, tip: str | None) -> Any:
        item.setData(42, self.parcial)
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
             anchor: str = "start", tip: str | None = None, bold: bool = False, halo: bool = False, mono: bool = False) -> float:
        """Texto con la línea base en y (como en SVG); devuelve su anchura."""
        if not segs:
            return 0.0
        font = QFont("Consolas" if mono else FONT)
        if mono:
            font.setStyleHint(QFont.StyleHint.Monospace)
            font.setFixedPitch(True)
        font.setPixelSize(size)
        font.setBold(bold)
        item = QGraphicsTextItem()
        item.document().setDocumentMargin(0)
        item.setFont(font)
        item.setDefaultTextColor(QColor(COL[color]))
        item.setHtml(_html(segs, False, self.verdaderos))
        w = item.boundingRect().width()
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        top = y - QFontMetricsF(font).ascent()
        item.setPos(x0, top)
        self.sc.addItem(item)
        self._put(item, z + 0.02, tip)
        tramos = _negados(segs)
        if tramos:  # la barra de la negación: una línea propia sobre cada tramo negado, a la altura de arriba del texto
            lim = self._limites(item, segs)
            for i, j in tramos:
                while i < j:
                    verde = any(k in self.verdaderos for k in segs[i].get("eval", []))
                    fin = i + 1
                    while fin < j and any(k in self.verdaderos for k in segs[fin].get("eval", [])) == verde:
                        fin += 1
                    self.line(x0 + lim[i], top, x0 + lim[fin], top,
                              self.pen("true_text" if verde else color, GROSOR_NEGADO), z + 0.03, tip)
                    i = fin
        if halo:  # rótulo de marco: fondo blanco que corta el trazo, como paint-order en el SVG
            self.rect(x0 - 3, top - 1, w + 6, item.boundingRect().height() + 2, None, z + 0.01, "panel")
        return w

    @staticmethod
    def ancho(segs: list[dict[str, Any]] | None, size: int, bold: bool = False) -> float:
        """Lo que ocupa un texto, sin dibujarlo."""
        if not segs:
            return 0.0
        clave = (tuple((s["t"], bool(s.get("s"))) for s in segs), size, bold)
        if clave not in _ANCHOS:
            font = QFont(FONT)
            font.setPixelSize(size)
            font.setBold(bold)
            item = QGraphicsTextItem()
            item.document().setDocumentMargin(0)
            item.setFont(font)
            item.setHtml(_html(segs, False))
            _ANCHOS[clave] = item.boundingRect().width()
        return _ANCHOS[clave]

    @staticmethod
    def _limites(item: QGraphicsTextItem, segs: list[dict[str, Any]]) -> list[float]:
        """Dónde empieza cada segmento dentro del texto de `item` y dónde acaba el último (len(segs) + 1 posiciones)."""
        linea = item.document().firstBlock().layout().lineAt(0)
        n, out = 0, []
        for s in segs:
            out.append(float(linea.cursorToX(n)[0]))
            n += len(s["t"])
        out.append(float(linea.cursorToX(n)[0]))
        return out

    @staticmethod
    def limites(segs: list[dict[str, Any]] | None, size: int, bold: bool = False) -> list[float]:
        """Lo mismo para un texto sin dibujar (las posiciones se miden desde su origen)."""
        if not segs:
            return [0.0]
        font = QFont(FONT)
        font.setPixelSize(size)
        font.setBold(bold)
        item = QGraphicsTextItem()
        item.document().setDocumentMargin(0)
        item.setFont(font)
        item.setHtml(_html(segs, False))
        item.boundingRect()  # compone el texto
        return _Pintor._limites(item, segs)

    @staticmethod
    def ascenso(size: int, bold: bool = False) -> float:
        """Lo que sube el texto de ese tamaño por encima de su línea base."""
        font = QFont(FONT)
        font.setPixelSize(size)
        font.setBold(bold)
        return QFontMetricsF(font).ascent()

    def seg(self, t: str) -> list[dict[str, Any]]:
        return [{"t": t}]

    def comentario(self, x: float, yc: float, texto: str, z: float, ancho: float = ANCHO_COMENTARIO) -> None:
        """Comentario de una etapa o transición: el texto entre comillas tipográficas, en cursiva y discreto, a la derecha
        de `x`, centrado en vertical en `yc` y ajustado a varias líneas si pasa de `ancho`."""
        font = QFont(FONT)
        font.setPixelSize(12)
        font.setItalic(True)
        item = QGraphicsTextItem()
        item.document().setDocumentMargin(0)
        item.setFont(font)
        item.setDefaultTextColor(QColor(COL["muted"]))
        item.setPlainText(f"“{texto}”")
        item.setTextWidth(ancho)
        w = item.document().idealWidth()
        item.setTextWidth(min(ancho, w + 2))  # sin hueco a la derecha si cabe en menos
        item.setPos(x, yc - item.boundingRect().height() / 2)
        self.sc.addItem(item)
        self._put(item, z + 0.02, None)


def _temporizadores(S: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Temporizadores con algo que mostrar (contando o vencidos), por expresión que los contiene."""
    out: dict[str, list[dict[str, Any]]] = {}
    for t in (S.get("temporal") or {}).values():
        if t.get("shown"):
            out.setdefault(t["expr"], []).append(t)
    return out


def _duracion(segs: list[dict[str, Any]], t: dict[str, Any]) -> int | None:
    """El segmento que escribe la duración de un temporizador (su `token`, la `nth`-ésima vez que aparece), si está."""
    sitios = [i for i, sg in enumerate(segs) if sg["t"] == t.get("token")]
    return sitios[t.get("nth", 0)] if t.get("nth", 0) < len(sitios) else None


def _estado_temporal(pt: _Pintor, x: float, y: float, segs: list[dict[str, Any]] | None, size: int, ref: str | None,
                     tmp: dict[str, list[dict[str, Any]]], z: float, tip: str | None = None) -> float:
    """Estado de los temporizadores de una receptividad, condición o evento, que se escribe con `size` desde `x` con su
    línea base en `y`: el tiempo transcurrido («0,50 s») mientras cuenta, o «3,00 s ✓» al vencer, alineado al extremo de la
    duración del temporizador (o de todo el texto, si no se encuentra) y por encima de su barra si está negada. Devuelve
    hasta dónde llega por la derecha (0 si no se dibuja nada)."""
    lista = tmp.get(ref or "", []) if segs else []
    if not lista:
        return 0.0
    lim = pt.limites(segs, size)
    derecha = 0.0
    for t in lista:
        i = _duracion(segs, t)
        a, b = (lim[0], lim[-1]) if i is None else (lim[i], lim[i + 1])
        negado = any(s.get("o") for s in segs) if i is None else bool(segs[i].get("o"))
        base = y - pt.ascenso(size) - (3 if negado else 1)  # la barra de la negación está arriba del texto, algo más gruesa
        off = bool(t.get("off"))
        ancla = x + (b if off else a)
        color = "readout"
        w = pt.text(ancla, base - 1, pt.seg(t["shown"]), TMR_TAM, color, z, "end" if off else "start", tip,
                    mono=True)
        derecha = max(derecha, ancla if off else ancla + w)
    return derecha


def _valores_variables(pt: _Pintor, x: float, y: float, t: dict[str, Any], S: dict[str, Any], nombres: dict[str, str],
                       z: float, tip: str | None = None) -> None:
    """Al simular, el valor actual de cada variable numérica (`numericVars`: contadores, magnitudes) que usa la receptividad de
    la transición, como el de una acción (`_caja_accion`): en pequeño y en azul, centrado sobre el nombre de la variable en el
    texto de la receptividad y por encima de él (y de la duración de un temporizador, si la hay). La condición se escribe con su
    línea base en `y`. Fuera de la simulación (sin lecturas) no se dibuja nada."""
    lecturas, segs = S.get("variableReadouts") or {}, t.get("cond")
    if not lecturas or not segs or not t.get("numericVars"):
        return
    lim = pt.limites(segs, 14)
    base = y - pt.ascenso(14) - 3 - (TMR_EXTRA if t.get("tmr") else 0)
    for vid in t["numericVars"]:
        valor, nombre = lecturas.get(vid), nombres.get(vid, vid)
        i = next((n for n, sg in enumerate(segs) if sg["t"] == nombre), None)
        if valor is None or i is None:
            continue
        pt.text(x + (lim[i] + lim[i + 1]) / 2, base, pt.seg(valor), 10, "readout", z, anchor="middle", tip=tip, mono=True)


REJILLA = 20   # paso de la rejilla del editor (coordenadas del modelo)
ALTO_T = 14    # semialtura del área de una transición al editar (el trazo es fino: se acierta mejor así)
ANCLA = TALLO_T  # distancia de los puntos de unión de una transición a su centro: al final de su tramo recto, lejos del
                 # trazo, para que agarrar la transición la mueva y no saque una rama
ANCLA_S = 28   # ... y si ese lado es una simultaneidad (el punto queda fuera del doble trazo)
SIMUL = 14     # distancia del doble trazo de una simultaneidad al centro de la transición
RADIO_ANCLA = 14  # a qué distancia del puntero se marca un punto de unión (generoso: se agarra sin puntería)
Z_EDIT = 10    # selección, tiradores y marcas por encima de todo el dibujo
EVOLUCION_HORIZONTAL = ("derecha", "izquierda")  # orientaciones de una transición cuyo trazo es vertical


def caja_barra(o: str, x: float, y: float) -> QRectF:
    """La caja del trazo de una transición centrada en (x, y) con la orientación `o` (vertical si la evolución es horizontal)."""
    return QRectF(x - 2, y - TB, 4, 2 * TB) if o in EVOLUCION_HORIZONTAL else QRectF(x - TB, y - 2, 2 * TB, 4)


def orientaciones(M: dict[str, Any]) -> dict[str, str]:
    """La orientación de cada transición de la vista (`abajo` la de siempre)."""
    return {t["id"]: orientacion(t) for t in M["transitions"]}


def rects_textos_t(t: dict[str, Any], x: float, y: float) -> tuple[QRectF | None, QRectF | None]:
    """Lo que ocupan la designación y la receptividad de una transición centrada en (x, y): a izquierda y derecha del trazo
    (evolución vertical) o, si el trazo es vertical, la designación debajo y la receptividad encima, centradas en él, para que
    no pisen los enlaces horizontales."""
    horizontal = orientacion(t) in EVOLUCION_HORIZONTAL
    etq = cond = None
    if t.get("showLabel", True):
        w = _Pintor.ancho([{"t": f"({t.get('label', t['id'])})"}], 13)
        etq = QRectF(x - w / 2, y + TB + 2, w, 21) if horizontal else QRectF(x - TB - 6 - w, y - 12, w, 21)
    if t.get("cond"):
        w = _Pintor.ancho(t["cond"], 14)
        cond = QRectF(x - w / 2, y - TB - 26, w, 21) if horizontal else QRectF(x + TB + 8, y - 12, w, 21)
    return etq, cond


def _trazos_girada(pt: _Pintor, t: dict[str, Any], tx: float, ty: float, pre: list[tuple[float, float]],
                   post: list[tuple[float, float]], trazo: QPen) -> None:
    """Los tramos rectos de una transición cuya evolución no va hacia abajo (sin etapa anterior o siguiente) y los dobles
    trazos de sus simultaneidades, en el eje de su evolución: lo que hace el dibujo normal, girado."""
    n = NORMAL[orientacion(t)]

    def P(u: float, v: float = 0.0) -> tuple[float, float]:
        return punto_t(t, tx, ty, u, v)

    def doble(signo: int, otros: list[tuple[float, float]]) -> None:
        vs = [(p[0] - tx) * n[0] + (p[1] - ty) * n[1] for p in otros] + [0.0]
        lo, hi = min(vs) - 8, max(vs) + 8
        u1, u2 = signo * SIMUL, signo * (SIMUL + BARRA_GROSOR)
        for u in (u1, u2):
            pt.line(*P(u, lo), *P(u, hi), trazo, Z_LINK)
        (x0, y0), (x1, y1) = P(u1 + signo, lo), P(u2 - signo, hi)
        pt.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), None, Z_LINK + 0.1, "panel")
        pt.line(*P(u1), tx, ty, trazo, Z_LINK)
    if len(pre) > 1 or t.get("simulPre"):
        doble(-1, pre)
    if t.get("simulPost"):
        doble(1, post)
    if not pre:
        pt.line(*P(-TALLO_T), tx, ty, trazo, Z_LINK)
    if not post:
        pt.line(tx, ty, *P(TALLO_T), trazo, Z_LINK)


def posiciones(M: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Centro, en el dibujo, de cada etapa, macroetapa y transición."""
    pos = {s["id"]: (s["x"] + SX, s["y"]) for s in M["steps"]}
    pos.update({m["id"]: (m["x"] + SX, m["y"]) for m in M.get("macros", [])})
    pos.update({t["id"]: (t["x"] + SX, t["y"]) for t in M["transitions"]})
    return pos


def _segmento(M: dict[str, Any], pos: dict[str, tuple[float, float]], d: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    a, b = pos.get(d["from"]), pos.get(d["to"])
    return (a, b) if a and b else None


BARRA_GROSOR = 8   # separación de las dos líneas de una barra de simultaneidad


def barra(b: dict[str, Any]) -> tuple[float, float, float, float]:
    """Una barra en el dibujo: x, y de arriba, ancho y alto."""
    return b["x"] + SX, b["y"], b["ancho"], BARRA_GROSOR if b["kind"] == "Y" else 0


def anclas(M: dict[str, Any], ident: str) -> list[dict[str, Any]]:
    """Puntos de unión de un elemento: etapa y transición, arriba (entra el enlace) y abajo (sale); la etapa, además, en
    el centro de su lado derecho (de ahí salen las acciones); una acción suelta (la primera de su grupo), a la
    izquierda."""
    for b in M.get("bars", []):
        if b["id"] == ident:
            bx, by, w, h = barra(b)
            return [{"id": ident, "lado": "arriba", "pos": QPointF(bx + w / 2, by - 9)},
                    {"id": ident, "lado": "abajo", "pos": QPointF(bx + w / 2, by + h + 9)}]
    for d in M.get("draftActions", []):  # una acción suelta: un solo punto de unión, en el medio de su lado izquierdo
        if d["id"] == ident and not d.get("etapa") and d.get("cabeza", True):
            return [{"id": ident, "lado": "izq", "pos": QPointF(d["x"] + SX, d["y"])}]
    pos = posiciones(M)
    if ident not in pos:
        return []
    x, y = pos[ident]
    t = next((t for t in M["transitions"] if t["id"] == ident), None)
    arriba = H if t is None else ANCLA_S if t.get("simulPre") else ANCLA
    abajo = H if t is None else ANCLA_S if t.get("simulPost") else ANCLA
    if t is not None and orientacion(t) != "abajo":  # «arriba» es la entrada (el lado de donde viene la evolución)
        return [{"id": ident, "lado": "arriba", "pos": QPointF(*punto_t(t, x, y, -arriba))},
                {"id": ident, "lado": "abajo", "pos": QPointF(*punto_t(t, x, y, abajo))}]
    out = [{"id": ident, "lado": "arriba", "pos": QPointF(x, y - arriba)},
           {"id": ident, "lado": "abajo", "pos": QPointF(x, y + abajo)}]
    if any(st["id"] == ident for st in M["steps"]):
        out.append({"id": ident, "lado": "der", "pos": QPointF(x + H, y)})
    return out


def _distancia(p: QPointF, a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = max(0.0, min(1.0, ((p.x() - a[0]) * dx + (p.y() - a[1]) * dy) / ((dx * dx + dy * dy) or 1)))
    return ((p.x() - a[0] - k * dx) ** 2 + (p.y() - a[1] - k * dy) ** 2) ** 0.5


def ancla_en(M: dict[str, Any], p: QPointF, radio: float = RADIO_ANCLA, sin_der: bool = False) -> dict[str, Any] | None:
    """El punto de unión más cercano al puntero, si hay alguno a menos de `radio` (el de la derecha de una etapa, de
    donde salen las acciones, solo a menos de 8 si la etapa ya las tiene: ahí empieza su enlace, que se selecciona; `sin_der`
    lo ignora, para enlaces que no son de acciones)."""
    best = None
    ocupadas = {s["id"] for s in M["steps"] if s["actions"]} | {d["etapa"] for d in M.get("draftActions", []) if d.get("etapa")}
    cuadrados = {s["id"] for s in M["steps"]} | {s["id"] for s in M.get("macros", [])}
    for ident, (cx, cy) in posiciones(M).items():
        if ident in cuadrados and QRectF(cx-H+2,cy-H+2,2*H-4,2*H-4).contains(p):
            continue  # dentro de la caja se selecciona o arrastra; los puntos de enlace quedan fuera
        for a in anclas(M, ident):
            if a["lado"] == "der" and sin_der:
                continue
            d = ((a["pos"].x() - p.x()) ** 2 + (a["pos"].y() - p.y()) ** 2) ** 0.5
            if d <= (min(radio, 8) if a["lado"] == "der" and ident in ocupadas else radio) and (best is None or d < best[0]):
                best = (d, a)
    for d in M.get("draftActions", []):
        for a in anclas(M, d["id"]):
            dist = ((a["pos"].x() - p.x()) ** 2 + (a["pos"].y() - p.y()) ** 2) ** 0.5
            if dist <= radio and (best is None or dist < best[0]):
                best = (dist, a)
    for b in M.get("bars", []):  # en una barra, el punto de unión sigue al puntero a lo largo de su ancho
        bx, by, w, h = barra(b)
        if bx - 4 <= p.x() <= bx + w + 4:
            x = min(max(p.x(), bx), bx + w)
            for lado, y in (("arriba", by - 9), ("abajo", by + h + 9)):
                d = abs(p.y() - y)
                if d <= min(radio, 7) and (best is None or d < best[0]):
                    best = (d, {"id": b["id"], "lado": lado, "pos": QPointF(x, y)})
    return best[1] if best else None


def marco_en(M: dict[str, Any], p: QPointF, borde: float = 6) -> str | None:
    """El parcial cuyo marco (recinto o parcial; la expansión no tiene) se toca en el punto: su borde, a `borde` o menos, o
    su nombre. Dentro del marco, lejos del borde, no hay nada que agarrar: ahí se suelta, se traza el lazo… Si hay varios,
    el más pequeño."""
    cajas = cajas_parciales(M)
    mejor: tuple[float, str] | None = None
    for part in M.get("partials") or []:
        b = cajas.get(part["id"])
        if not b or part["kind"] not in ("enclosure", "partial"):
            continue
        x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
        cerca = x0 - borde <= p.x() <= x1 + borde and y0 - borde <= p.y() <= y1 + borde
        interior = x0 + borde < p.x() < x1 - borde and y0 + borde < p.y() < y1 - borde
        w = 8 * len(part["label"]) + 8  # lo que ocupa el nombre del parcial, abajo (a la izquierda en un recinto, a la derecha si no)
        xn = x0 + 26
        en_nombre = xn <= p.x() <= xn + w + 8 and y1 - 8 <= p.y() <= y1 + 12
        if part["kind"] == "enclosure":
            dueno = M.get("names", {}).get(part.get("ownerStep"), part.get("ownerStep", ""))
            en_nombre |= xn <= p.x() <= xn + 8 * len(dueno) + 16 and y0 - 12 <= p.y() <= y0 + 8
        if (cerca and not interior) or en_nombre:
            area = (x1 - x0) * (y1 - y0)
            if mejor is None or area < mejor[0]:
                mejor = (area, part["id"])
    return mejor[1] if mejor else None


def elemento_en(M: dict[str, Any], p: QPointF) -> str | None:
    """El elemento bajo un punto del dibujo: etapa, transición (su trazo), enlace en borrador, enlace o, al final y solo
    en su borde o su nombre, el marco de un parcial."""
    pos = posiciones(M)
    for t in M["transitions"]:  # el trazo, su designación a la izquierda y su receptividad a la derecha
        x, y = pos[t["id"]]
        if orientacion(t) in EVOLUCION_HORIZONTAL:  # trazo vertical; designación (debajo) y receptividad (encima), centradas
            if abs(p.x() - x) <= ALTO_T and abs(p.y() - y) <= TB + 6 or any(
                    r is not None and r.adjusted(-2, -2, 2, 2).contains(p) for r in rects_textos_t(t, x, y)):
                return t["id"]
            continue
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
    from .anotaciones import en
    n = en(M,p)
    return n["id"] if n else marco_en(M, p)


def parciales_dibujo(M):
    """Pertenencia visual: las barras heredan el parcial de sus extremos, sin cambiar el modelo."""
    partes = {x["id"]: x.get("partial") or "g" for k in ("steps", "transitions", "macros") for x in M.get(k, [])}
    for b in M.get("bars", []):
        extremos = {partes[i] for i in b.get("arriba", []) + b.get("abajo", []) if i in partes}
        partes[b["id"]] = next(iter(extremos)) if len(extremos) == 1 else (None if extremos else "g")
    return partes


def _realces(pt: _Pintor, M: dict[str, Any], sel: set[str], marcados: set[str], naranja: set[str] = frozenset()) -> None:
    """Edición: enlaces en borrador, elementos en cuestión (rojo discontinuo), selección con sus tiradores y, mientras
    parpadean tras un error, los elementos afectados en naranja (las acciones, en su caja)."""
    pos = posiciones(M)
    pertenencia = parciales_dibujo(M)
    pertenencia.update({q["id"]: q["id"] for q in M.get("partials", [])})
    pertenencia.update({a["id"]: s.get("partial") or "g" for s in M.get("steps", []) for a in s.get("actions", [])})
    for e in enlaces(M): pertenencia[e["id"]] = pertenencia.get(e.get("tid") or e.get("sid"))
    etapas = {s["id"] for s in M["steps"]} | {m["id"] for m in M.get("macros", [])}
    for d in M.get("drafts", []):
        pt.parcial = pertenencia.get(d.get("from"))
        seg = _segmento(M, pos, d)
        if seg:
            (x1, y1), (x2, y2) = seg
            mixto = d.get("from") in etapas and d.get("to") in {t["id"] for t in M["transitions"]}
            pt.line(x1, y1, x2, y2, pt.pen("err", 3 if d["id"] in sel else 1.8, (6, 4)), Z_EDIT,
                    "Enlace en borrador: una etapa llega a una transición que ya tiene otra etapa anterior; falta la barra de "
                    "simultaneidad. No es ejecutable" if mixto else
                    "Enlace en borrador: une dos elementos del mismo tipo y no es ejecutable")
    trans = orientaciones(M)
    rutas = {e["id"]: e for e in enlaces(M)}
    barras = {b["id"]: b for b in M.get("bars", [])}
    marcos = cajas_parciales(M, pos)  # un parcial (recinto, expansión) seleccionado o en cuestión se remarca en su marco
    for ident, color, width in [(i, "err", 1.8) for i in marcados] + [(i, "accent", 1.6) for i in sel]:
        pt.parcial = pertenencia.get(ident)
        if ident in marcos:
            b = marcos[ident]
            pt.rect(b["x0"] - 6, b["y0"] - 6, b["x1"] - b["x0"] + 12, b["y1"] - b["y0"] + 12, pt.pen(color, width, (5, 3)), Z_EDIT)
            continue
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
        hx, hy = ((ALTO_T, TB + 6) if trans[ident] in EVOLUCION_HORIZONTAL else (TB + 6, ALTO_T)) if ident in trans else (H + 6, H + 6)
        pt.rect(x - hx, y - hy, 2 * hx, 2 * hy, pt.pen(color, width, (5, 3)), Z_EDIT)
        if color == "accent":  # tiradores en las esquinas
            for cx, cy in ((x - hx, y - hy), (x + hx, y - hy), (x - hx, y + hy), (x + hx, y + hy)):
                pt.rect(cx - 3, cy - 3, 6, 6, pt.pen("accent", 1), Z_EDIT + 0.1, "panel")
    for ident in sorted(naranja):  # parpadeo naranja de un error
        pt.parcial = pertenencia.get(ident)
        if ident in marcos:
            b = marcos[ident]
            pt.rect(b["x0"] - 8, b["y0"] - 8, b["x1"] - b["x0"] + 16, b["y1"] - b["y0"] + 16, pt.pen("glow", 3.5), Z_EDIT + 0.5)
        elif ident in rutas:
            pt.poly([(float(x), float(y)) for x, y in rutas[ident]["pts"]], pt.pen("glow", 5), Z_EDIT + 0.5)
        elif ident in barras:
            bx, by, w, h = barra(barras[ident])
            pt.rect(bx - 7, by - 9, w + 14, h + 18, pt.pen("glow", 3.5), Z_EDIT + 0.5)
        elif ident in pos:
            x, y = pos[ident]
            hx, hy = ((ALTO_T + 3, TB + 9) if trans[ident] in EVOLUCION_HORIZONTAL else (TB + 9, ALTO_T + 3)) if ident in trans else (H + 9, H + 9)
            pt.rect(x - hx, y - hy, 2 * hx, 2 * hy, pt.pen("glow", 3.5), Z_EDIT + 0.5)


def _colores_elementos(M, S):
    activos = set(S.get("situation") or []) if not S.get("blocked") else set()
    activos.update(i for i, v in (S.get("macros") or {}).items() if v)
    roles = {i: "active" for i in activos}
    for t in M["transitions"]:
        ob = (S.get("transitions") or {}).get(t["id"], {})
        if ob.get("fireable") or ob.get("validated") and (ob.get("receptivity") or
                (S.get("truth") or {}).get(t.get("conditionRef")) is True):
            roles[t["id"]] = "active"
    roles.update({i: "history" for i in S.get("lastCleared") or []})
    tids = {t["id"] for t in M["transitions"]}
    for b in M.get("bars", []):
        vecinos = set(b["arriba"]) | set(b["abajo"])
        candidatos = vecinos & tids or vecinos
        colores = {roles.get(i) for i in candidatos}
        if "active" in colores or "history" in colores:
            roles[b["id"]] = "active" if "active" in colores else "history"
    for p in M.get("partials", []):
        if p.get("ownerStep") in activos or any(e.get("partial") == p["id"] and e["id"] in activos
                                               for e in M["steps"] + M.get("macros", [])):
            roles[p["id"]] = "active"
    return roles


def _color_enlace(M, roles, e):
    # El destino activo nunca alimenta hacia atrás un enlace entrante.
    if e["rol"] == "pre":
        return roles.get(e["tid"]) or roles.get(e["sid"], "text")
    if e["rol"] == "barra":
        b = next(b for b in M.get("bars", []) if b["id"] == e["tid"])
        return (roles.get(e["sid"]) if e["sid"] in b["arriba"] else roles.get(e["tid"])) or "text"
    return roles.get(e["tid"], "text")


def dibujar(scene: QGraphicsScene, M: dict[str, Any], S: dict[str, Any], sel: set[str] | None = None,
            marcados: set[str] | None = None, naranja: set[str] | None = None,
            uniones: list[dict[str, Any]] | None = None, ordenes: list[dict[str, Any]] | None = None,
            dependencias: bool = False) -> list[dict[str, Any]]:
    """M: estructura de la vista (Vista.model); S: estado observado (Vista.state()); sel y marcados, solo al editar:
    los elementos seleccionados y los que tienen un diagnóstico; naranja, los que parpadean tras un error (en la fase
    encendida del parpadeo). Devuelve dónde ha quedado cada acción ({id, etapa, rect, …}), para que el editor las
    encuentre con el ratón; en `uniones`, si se da, los trazos que unen cada etapa con sus acciones, y en `ordenes` el
    rectángulo de cada orden de forzado ({id, etapa, rect}: no son acciones, pero también se señalan con el ratón).
    `dependencias` (como en tools/dibujo.js) dibuja los trazos discontinuos que unen una macroetapa con su expansión y una
    encapsulante con sus recintos; por defecto no se dibujan. Mostrarlos u ocultarlos no cambia ninguna otra cosa."""
    scene.clear()
    cajas: list[dict[str, Any]] = []
    from .anotaciones import dibujar as dibujar_anotaciones
    dibujar_anotaciones(scene,M,sel or set())
    pt = _Pintor(scene)
    pt.verdaderos = {k for k, v in S.get("truth", {}).items() if v is True}
    pertenencia = parciales_dibujo(M)
    nombre = M.get("names", {}).get  # los ID internos nunca se muestran: etapas, parciales y macroetapas, por su nombre
    pos = {s["id"]: (s["x"] + SX, s["y"]) for s in M["steps"]}
    pos.update({m["id"]: (m["x"] + SX, m["y"]) for m in M.get("macros", [])})
    if not pos and not M["transitions"] and not M.get("draftActions"):
        return cajas
    # Enlace ascendente: por la izquierda del parcial de la transición, no de todo el dibujo
    situation, virtual = set(S.get("situation") or []), set(S.get("virtual") or [])
    unstable, cleared = set(S.get("unstable") or []), set(S.get("lastCleared") or [])
    blk = S.get("blocked")
    reached = set(blk["reached"]) if blk else set()
    roles = _colores_elementos(M, S)
    _marcos(pt, M, pos, dependencias, roles)
    tmp = _temporizadores(S)
    marcadas = {i for i in (sel or set()) if i.startswith("accion:")} | {f"parpadeo:{i}" for i in (naranja or ())}
    link = pt.pen("text")
    for t in M["transitions"]:
        pt.parcial = t.get("partial") or "g"
        tx, ty = t["x"] + SX, t["y"]
        ob = (S.get("transitions") or {}).get(t["id"], {})
        trazo = pt.pen(roles.get(t["id"], "text"))
        pre = [pos[p] for p in t.get("preDib", t["pre"]) if p in pos]
        post = [pos[p] for p in t.get("postDib", t["post"]) if p in pos]
        giro = orientacion(t)
        if giro != "abajo":
            _trazos_girada(pt, t, tx, ty, pre, post, trazo)
        if giro == "abajo" and (len(pre) > 1 or t.get("simulPre")):
            xs, yy = [p[0] for p in pre] + [tx], ty - SIMUL
            pt.line(min(xs) - 8, yy, max(xs) + 8, yy, trazo, Z_LINK)
            pt.rect(min(xs)-8, yy-BARRA_GROSOR+1, max(xs)-min(xs)+16, BARRA_GROSOR-2, None, Z_LINK+0.1, "panel")
            pt.line(min(xs) - 8, yy - BARRA_GROSOR, max(xs) + 8, yy - BARRA_GROSOR, trazo, Z_LINK)
            pt.line(tx, yy, tx, ty, trazo, Z_LINK)
        if giro == "abajo" and t.get("simulPost"):
            xs, yy = [p[0] for p in post] + [tx], ty + SIMUL
            pt.line(tx, ty, tx, yy, trazo, Z_LINK)
            pt.line(min(xs) - 8, yy, max(xs) + 8, yy, trazo, Z_LINK)
            pt.rect(min(xs)-8, yy+1, max(xs)-min(xs)+16, BARRA_GROSOR-2, None, Z_LINK+0.1, "panel")
            pt.line(min(xs) - 8, yy + BARRA_GROSOR, max(xs) + 8, yy + BARRA_GROSOR, trazo, Z_LINK)
        if giro == "abajo" and not pre:
            pt.line(tx, ty - TALLO_T, tx, ty, trazo, Z_LINK)  # transición fuente: su tramo recto es parte de ella
        if giro == "abajo" and not post:
            pt.line(tx, ty, tx, ty + TALLO_T, trazo, Z_LINK)  # transición sumidero
        color, width = "text", 2.4
        if ob.get("validated"):
            color = "text"
        if ob.get("fireable"):
            color = "active"
        if roles.get(t["id"]) == "active":
            color = "active"
        if t["id"] in cleared:
            color, width = "history", 3
        if blk and blk.get("element") == t["id"]:
            color, width = "err", 3
        tip = (f"Transición {t.get('label', t['id'])}: validada {'sí' if ob.get('validated') else 'no'}, receptividad "
               f"{'verdadera' if ob.get('receptivity') else 'falsa'}"
               + ("; su parcial está forzado y no evoluciona" if ob.get("forced") else ""))
        if giro in EVOLUCION_HORIZONTAL:  # trazo vertical; designación debajo y receptividad encima, horizontales y centradas
            pt.line(tx, ty - TB, tx, ty + TB, pt.pen(color, width), Z_BAR, tip)
            if t.get("showLabel", True):
                pt.text(tx, ty + TB + 19, pt.seg(f"({t.get('label', t['id'])})"), 13, color, Z_BAR, "middle", tip)
            w = _Pintor.ancho(t["cond"], 14) if t.get("cond") else 0
            x0, yb = tx - w / 2, ty - TB - 9
            pt.text(x0, yb, t.get("cond"), 14, "text", Z_BAR, tip=tip)
            derecha = _estado_temporal(pt, x0, yb, t.get("cond"), 14, t.get("conditionRef"), tmp, Z_BAR, tip)
            _valores_variables(pt, x0, yb, t, S, M.get("names", {}), Z_BAR, tip)
            if t.get("comment"):
                pt.comentario(max(x0 + w + (14 if w else 0), derecha + 8), yb - 5, t["comment"], Z_BAR)
            continue
        pt.line(tx - TB, ty, tx + TB, ty, pt.pen(color, width), Z_BAR, tip)
        if t.get("showLabel", True):
            pt.text(tx - TB - 6, ty + 5, pt.seg(f"({t.get('label', t['id'])})"), 13, color, Z_BAR, "end", tip)
        w = pt.text(tx + TB + 8, ty + 5, t.get("cond"), 14, "text", Z_BAR, tip=tip)
        fin = tx + TB + 8 + w
        derecha = _estado_temporal(pt, tx + TB + 8, ty + 5, t.get("cond"), 14, t.get("conditionRef"), tmp, Z_BAR, tip)
        _valores_variables(pt, tx + TB + 8, ty + 5, t, S, M.get("names", {}), Z_BAR, tip)
        if t.get("comment"):  # a la derecha de la receptividad (o de la transición, si no tiene)
            pt.comentario(max(fin + (14 if w else 0), derecha + 8), ty, t["comment"], Z_BAR)
    for b in M.get("bars", []):  # barras de simultaneidad (doble trazo) y de alternativa (trazo simple), con sus conectores
        pt.parcial = pertenencia[b["id"]]
        bx, by, w, h = barra(b)
        trazo = pt.pen(roles.get(b["id"], "text"))
        tipo = "Simultaneidad" if b["kind"] == "Y" else "Alternativa"
        pt.line(bx, by, bx + w, by, trazo, Z_LINK + 0.5, tipo)
        if b["kind"] == "Y":
            pt.rect(bx, by+1, w, h-2, None, Z_LINK+0.25, "panel")
            pt.line(bx, by + h, bx + w, by + h, trazo, Z_LINK + 0.5, tipo)
    for e in enlaces(M):
        pt.parcial = pertenencia.get(e.get("tid") or e.get("sid"))
        color_enlace = _color_enlace(M, roles, e)
        pt.poly([(float(x), float(y)) for x, y in e["pts"]], pt.pen(color_enlace), Z_LINK)
        for flecha in e["arrows"]:
            pt.poly(flecha["pts"], None, Z_LINK + 0.1, fill=color_enlace)
    for s in M["steps"]:
        pt.parcial = s.get("partial") or "g"
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
            outer = pt.pen("active", 2.4)
        if vir or uns:
            outer = pt.pen("virt", 2, (5, 4))
        if stale:
            outer = pt.pen("muted", 2, (2, 3))
        if cand:
            outer = pt.pen("glow", 2.2, (6, 4))
        pt.rect(x - H, y - H, 2 * H, 2 * H, outer, Z_STEP, "active_soft" if act else "panel", tip)
        if s["initial"]:
            pt.rect(x - H + 4, y - H + 4, 2 * H - 8, 2 * H - 8, pt.pen("active" if act else "text"), Z_STEP + 0.01, None, tip)
        if s["kind"] == "enclosing":  # encapsulante: esquinas cortadas; si es inicial, las del cuadrado interior
            h = H - 4 if s["initial"] else H
            c = round(0.22 * 2 * h)
            x0, x1, y0, y1 = x - h, x + h, y - h, y + h
            for a, b in (((x0 + c, y0), (x0, y0 + c)), ((x1 - c, y0), (x1, y0 + c)),
                         ((x0, y1 - c), (x0 + c, y1)), ((x1, y1 - c), (x1 - c, y1))):
                pt.line(*a, *b, pt.pen("active" if act else "text"), Z_STEP + 0.01, tip)
        pt.text(x, y + 3, pt.seg(s.get("label", sid)), 16, "active" if act else "text", Z_STEP, "middle", tip)
        if s.get("activation"):
            pt.text(x - H - 5, y + 5, pt.seg("*"), 18, "active" if act else "text", Z_STEP, "end", tip, bold=True)
        if act:
            pt.circle(x, y + 12, 3.5, "active", Z_STEP + 0.05, tip)
        for flag, label, color in ((vir, "inestable", "virt"), (uns, "fue inestable", "virt"),
                                   (stale, "último estable", "muted"), (cand, "alcanzada, sin confirmar", "glow")):
            if flag:
                pt.text(x, y + H + 13, pt.seg(label), 10, color, Z_STEP, "middle", tip)
        unidas = [d for d in M.get("draftActions", []) if d.get("etapa") == s["id"]]  # sin completar, al final de la fila
        _acciones(pt, x, y, s["actions"] + unidas, S, tmp, cajas, s["id"], marcadas, s.get("actionLayout", "fila"),
                  uniones=uniones, resaltar=f"enlaceacc:{s['id']}" in (sel or ()), ordenes=ordenes)
        if s.get("comment"):  # a la derecha de la etapa, o de su última acción si las tiene
            cajas_ = _geometria_acciones(x, y, s["actions"] + unidas, s.get("actionLayout", "fila"))[0]
            pt.comentario(max([ax + w for _, ax, _, w in cajas_] + [x + H]) + 10, y, s["comment"], Z_STEP)
    for m in M.get("macros", []):  # macroetapa: divisiones horizontales superior e inferior
        pt.parcial = m.get("partial") or "g"
        x, y = pos[m["id"]]
        act = bool((S.get("macros") or {}).get(m["id"]))
        tip = (f"Macroetapa {nombre(m['id'], m['id'])} (expansión {nombre(m['expansion'], m['expansion'])}): "
               + ("activa (alguna etapa de su expansión)" if act else "inactiva"))
        pt.rect(x - H, y - H, 2 * H, 2 * H, pt.pen("active", 2.4) if act else pt.pen("text"), Z_STEP,
                "active_soft" if act else "panel", tip)
        pt.line(x - H, y - H + MARK, x + H, y - H + MARK, pt.pen("active" if act else "text"), Z_STEP + 0.01, tip)
        pt.line(x - H, y + H - MARK, x + H, y + H - MARK, pt.pen("active" if act else "text"), Z_STEP + 0.01, tip)
        pt.text(x, y + 5, pt.seg(nombre(m["id"], m["id"])), 16, "active" if act else "text", Z_STEP, "middle", tip)
    grupos: dict[str, list[dict[str, Any]]] = {}
    for d in M.get("draftActions", []):  # acciones sueltas: las de un grupo, juntas desde la posición de la primera
        if not d.get("etapa"):
            grupos.setdefault(d.get("grupo") or d["id"], []).append(d)
    for g, miembros in grupos.items():
        pt.parcial = miembros[0].get("partial") or "g"
        _acciones(pt, miembros[0]["x"] + SX, miembros[0]["y"], miembros, S, tmp, cajas, "", marcadas,
                  (M.get("actionLayouts") or {}).get(g, "fila"), suelto=True, grupo=g)
    pt.parcial = None
    if sel or marcados or naranja or M.get("drafts"):
        _realces(pt, M, set(sel or ()), set(marcados or ()), set(naranja or ()))
    return cajas


VACIO_W, VACIO_H = 180, 120  # tamaño del marco de un recinto sin etapas (el editor lo anota con `vacio`, ver `cajas_parciales`)


def _contenido_parciales(M: dict[str, Any], pos: dict[str, tuple[float, float]]) -> dict[str, list[float]]:
    """Por parcial, el rectángulo [x0, y0, x1, y1] (en el dibujo, sin márgenes) de todo lo que se dibuja de él: sus etapas y
    macroetapas, sus transiciones (el trazo, su designación a la izquierda y su receptividad a la derecha, y los trazos de
    una simultaneidad), las acciones y órdenes unidas a sus etapas (con las marcas que sobresalen y los trazos que las unen),
    los recorridos de sus enlaces (también los de retorno, por fuera) y las barras que unen elementos suyos. No cuenta lo que
    depende del estado de la simulación (el tiempo de un temporizador, las etiquetas «inestable»…) ni los comentarios: el marco
    no cambia al simular. Igual que `drawFrames` de tools/dibujo.js."""
    out: dict[str, list[float]] = {}
    de: dict[str, str | None] = {}

    def anotar(pid: str | None, x0: float, y0: float, x1: float, y1: float) -> None:
        if not pid:
            return
        b = out.setdefault(pid, [x0, y0, x1, y1])
        b[:] = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]
    unidas = M.get("draftActions", [])
    for s in M["steps"]:
        x, y = pos[s["id"]]
        de[s["id"]] = pid = s.get("partial")
        anotar(pid, x - H, y - H, x + H, y + H)
        acciones = s["actions"] + [d for d in unidas if d.get("etapa") == s["id"]]
        if acciones and pid:
            cajas, union = _geometria_acciones(x, y, acciones, s.get("actionLayout", "fila"))
            for a, ax, cy, w in cajas:
                arriba, abajo = _extra(a)
                anotar(pid, ax, cy - H - arriba, ax + w, cy + H + abajo)
            for tramo in union:
                for px, py in tramo:
                    anotar(pid, px, py, px, py)
    for m in M.get("macros", []):
        x, y = pos[m["id"]]
        de[m["id"]] = pid = m.get("partial")
        anotar(pid, x - H, y - H, x + H, y + H)
    for t in M["transitions"]:
        tx, ty = t["x"] + SX, t["y"]
        de[t["id"]] = pid = t.get("partial")
        pre = [pos[p] for p in t.get("preDib", t["pre"]) if p in pos]
        post = [pos[p] for p in t.get("postDib", t["post"]) if p in pos]
        if orientacion(t) != "abajo":  # transición girada: su trazo, sus tramos rectos y sus textos
            n = NORMAL[orientacion(t)]
            for u, v in ((0, -TB), (0, TB), (-TALLO_T if not pre else 0, 0), (TALLO_T if not post else 0, 0)):
                anotar(pid, *punto_t(t, tx, ty, u, v), *punto_t(t, tx, ty, u, v))
            for r in rects_textos_t(t, tx, ty):
                if r is not None:
                    anotar(pid, r.left(), r.top(), r.right(), r.bottom())
            for signo, otros, hay in ((-1, pre, len(pre) > 1 or t.get("simulPre")), (1, post, t.get("simulPost"))):
                if hay:
                    vs = [(p[0] - tx) * n[0] + (p[1] - ty) * n[1] for p in otros] + [0.0]
                    for u in (signo * SIMUL, signo * (SIMUL + BARRA_GROSOR)):
                        for v in (min(vs) - 8, max(vs) + 8):
                            anotar(pid, *punto_t(t, tx, ty, u, v), *punto_t(t, tx, ty, u, v))
            continue
        anotar(pid, tx - TB, ty - (TALLO_T if not pre else 0), tx + TB, ty + (TALLO_T if not post else 0))
        if t.get("showLabel", True):
            w = _Pintor.ancho([{"t": f"({t.get('label', t['id'])})"}], 13)
            anotar(pid, tx - TB - 6 - w, ty - 12, tx - TB - 6, ty + 9)
        if t.get("cond"):
            anotar(pid, tx + TB + 8, ty - 12, tx + TB + 8 + _Pintor.ancho(t["cond"], 14), ty + 9)
        if len(pre) > 1 or t.get("simulPre"):  # el doble trazo de una divergencia o convergencia simultánea
            xs = [p[0] for p in pre] + [tx]
            anotar(pid, min(xs) - 8, ty - SIMUL - BARRA_GROSOR, max(xs) + 8, ty - SIMUL)
        if t.get("simulPost"):
            xs = [p[0] for p in post] + [tx]
            anotar(pid, min(xs) - 8, ty + SIMUL, max(xs) + 8, ty + SIMUL + BARRA_GROSOR)
    for e in M["links"] if "links" in M else enlaces(M):  # el enlace es del parcial de su transición (el de una barra, del de su elemento)
        pid = de.get(e["sid"] if e["rol"] == "barra" else e["tid"])
        for px, py in e["pts"]:
            anotar(pid, px, py, px, py)
    for b in M.get("bars", []):
        bx, by, w, h = barra(b)
        for ident in list(b["arriba"]) + list(b["abajo"]):
            anotar(de.get(ident), bx, by, bx + w, by + h)
    return out


def cajas_parciales(M: dict[str, Any], pos: dict[str, tuple[float, float]] | None = None) -> dict[str, dict[str, float]]:
    """El rectángulo (x0, y0, x1, y1, en el dibujo) de cada parcial con contenido: el que rodea todo lo que se dibuja de él
    (`_contenido_parciales`: etapas, transiciones con sus textos, acciones y órdenes unidas, barras y los recorridos de sus
    enlaces, también los de retorno) con el margen de la norma (MARGEN_MARCO_X, MARGEN_MARCO_Y) y, como mínimo, el de siempre
    alrededor de sus etapas y transiciones (por la derecha, más ancho, para sus acciones), más el de sus parciales hijos. Es
    el marco que pinta `_marcos` (un recinto o un parcial) y, en una expansión, la zona que ocupa aunque no se dibuje (el
    editor la usa para saber en qué parcial cae lo que se suelta). Solo el editor anota un parcial con `vacio` (un recinto
    recién creado, sin etapas), con su esquina superior izquierda en `x`, `y` (coordenadas del modelo): se dibuja como marco
    vacío de VACIO_W × VACIO_H. Un parcial sin contenido ni `vacio` no tiene caja."""
    pos = pos if pos is not None else posiciones(M)
    parts = M.get("partials") or []
    box: dict[str, dict[str, float] | None] = {}
    dibujado = _contenido_parciales(M, pos)

    def own(pid: str) -> list[tuple[float, float]]:
        return ([pos[s["id"]] for s in M["steps"] if s.get("partial") == pid]
                + [pos[m["id"]] for m in M.get("macros", []) if m.get("partial") == pid]
                + [(t["x"] + SX, t["y"]) for t in M["transitions"] if t.get("partial") == pid])

    def frame(pid: str) -> dict[str, float] | None:
        if pid in box:
            return box[pid]
        pts = own(pid)
        b = ({"x0": min(p[0] for p in pts) - H - 26, "x1": max(p[0] for p in pts) + H + 70,
              "y0": min(p[1] for p in pts) - H - 22, "y1": max(p[1] for p in pts) + H + 22} if pts else None)
        if pid in dibujado:  # todo lo que se dibuja de él queda dentro, con margen
            x0, y0, x1, y1 = dibujado[pid]
            e = {"x0": x0 - MARGEN_MARCO_X, "x1": x1 + MARGEN_MARCO_X, "y0": y0 - MARGEN_MARCO_Y, "y1": y1 + MARGEN_MARCO_Y}
            b = e if b is None else {"x0": min(b["x0"], e["x0"]), "x1": max(b["x1"], e["x1"]),
                                     "y0": min(b["y0"], e["y0"]), "y1": max(b["y1"], e["y1"])}
        if b is None:
            vacio = next((c for c in parts if c["id"] == pid and c.get("vacio")), None)
            if vacio is not None:
                b = {"x0": vacio["x"] + SX, "x1": vacio["x"] + SX + VACIO_W, "y0": vacio["y"], "y1": vacio["y"] + VACIO_H}
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

    return {c["id"]: b for c in parts if (b := frame(c["id"]))}


def _dependencias_recinto(b: dict[str, float], ox: float, oy: float, inicial: bool = False
                          ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Los dos trazos de dependencia de una encapsulante centrada en (ox, oy) a su recinto de marco `b`, como en la figura de la
    norma: cada uno llega a una de las dos esquinas del lado del marco que mira hacia la encapsulante (el lado cuya normal
    apunta a su centro, según el eje de mayor diferencia entre los centros; en empate, el vertical): con el recinto debajo, a sus
    dos esquinas de arriba; a la derecha, a las dos de la izquierda; y así. Salen de la esquina de la encapsulante más cercana a
    cada esquina de destino: en las esquinas cortadas de la etapa, el punto medio de su diagonal (en una inicial, la esquina
    del cuadrado exterior). Se eligen al dibujar, según la posición de ahora: si el marco cambia de lado, cambian. Igual en
    tools/dibujo.js."""
    dx, dy = ox - (b["x0"] + b["x1"]) / 2, oy - (b["y0"] + b["y1"]) / 2
    if abs(dy) >= abs(dx):
        y = b["y0"] if dy <= 0 else b["y1"]
        destinos = [(b["x0"], y), (b["x1"], y)]
    else:
        x = b["x0"] if dx < 0 else b["x1"]
        destinos = [(x, b["y0"]), (x, b["y1"])]
    c = H if inicial else H - round(0.22 * 2 * H) / 2
    esquinas = [(ox + sx * c, oy + sy * c) for sy in (-1, 1) for sx in (-1, 1)]
    return [(min(esquinas, key=lambda e: (e[0] - d[0]) ** 2 + (e[1] - d[1]) ** 2), d) for d in destinos]


def _dependencia_cajas(a: tuple[float, float], b: tuple[float, float], superior: bool = True,
                        lado: float | None = None) -> tuple[tuple[float, float], tuple[float, float]]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    lado = dx if lado is None else lado
    if lado == 0:
        k = min(.5, H / max(abs(dx), abs(dy))) if dx or dy else 0
        return (a[0] + dx * k, a[1] + dy * k), (b[0] - dx * k, b[1] - dy * k)
    hx, hy = (H if lado > 0 else -H), (-H if superior else H)
    return (a[0] + hx, a[1] + hy), (b[0] - hx, b[1] + hy)


def _marcos(pt: _Pintor, M: dict[str, Any], pos: dict[str, tuple[float, float]], dependencias: bool = False, roles: dict[str, str] | None = None) -> None:
    """Parciales según las figuras de la norma: recinto (marco continuo, con el nombre de la encapsulante arriba y el del
    recinto abajo, a caballo del trazo, sobre un fondo del color del lienzo), parcial (marco redondeado con su nombre; un hijo
    dentro de su padre) y expansión (trazos discontinuos de la macroetapa a su entrada y a su salida, sin marco). Esos trazos
    discontinuos son las dependencias: solo se dibujan con `dependencias`, y con ellas también los dos que unen una
    encapsulante con las esquinas del lado del marco de cada uno de sus recintos que mira hacia ella (`_dependencias_recinto`)."""
    parts = M.get("partials") or []
    roles = roles or {}
    cajas = cajas_parciales(M, pos)

    for p in parts:
        pt.parcial = p["id"]
        if p["kind"] == "expansion":
            m = next((x for x in M.get("macros", []) if x["id"] == p.get("macro")), None)
            if not dependencias or not m or m["entry"] not in pos or m["exit"] not in pos:
                continue
            (mx, my), (ex, ey), (sx, sy) = pos[m["id"]], pos[m["entry"]], pos[m["exit"]]
            dash = pt.pen(roles.get(m["id"], "muted"), 1.2, (5, 4))
            for n, destino in enumerate(((ex, ey), (sx, sy))):
                desde, hasta = _dependencia_cajas((mx, my), destino, n == 0, (ex + sx) / 2 - mx)
                pt.line(*desde, *hasta, dash, Z_FRAME)
            continue
        b = cajas.get(p["id"])
        if not b:
            continue
        if p["kind"] == "enclosure":
            if dependencias and p.get("ownerStep") in pos:
                ox, oy = pos[p["ownerStep"]]
                dueno = next((s for s in M["steps"] if s["id"] == p["ownerStep"]), None)
                for (x1, y1), (x2, y2) in _dependencias_recinto(b, ox, oy, bool(dueno and dueno["initial"])):
                    pt.line(x1, y1, x2, y2, pt.pen(roles.get(p["id"], "muted"), 1.2, (5, 4)), Z_FRAME)
            pt.rect(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"], pt.pen(roles.get(p["id"], "text")), Z_FRAME)
            # el nombre de la encapsulante, a la izquierda a caballo del trazo de arriba, y el del recinto, a la izquierda del de abajo,
            # con un fondo del color del lienzo que corta el trazo y deja leerlos; igual en tools/dibujo.js
            pt.text(b["x0"] + 30, b["y0"] + 5, pt.seg(M.get("names", {}).get(p["ownerStep"], p["ownerStep"])), 14,
                    roles.get(p["id"], "text"), Z_FRAME, "start", halo=True)
            pt.text(b["x0"] + 30, b["y1"] + 5, pt.seg(p["label"]), 14, roles.get(p["id"], "text"), Z_FRAME, halo=True)
        else:
            pt.rect(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"], pt.pen(roles.get(p["id"], "muted"), 1.2), Z_FRAME, radius=16)
            pt.text(b["x0"] + 30, b["y1"] + 5, pt.seg(p["label"]), 14, roles.get(p["id"], "text"), Z_FRAME, halo=True)


def _extra(a: dict[str, Any]) -> tuple[int, int]:
    """Lo que sobresale la marca de una acción por encima y por debajo de su caja (condición, flecha, banderita), y el
    tiempo transcurrido de su temporizador, que va encima de la condición o del evento (`tmr`)."""
    if a["kind"] == "continuous" and a.get("cond"):
        return 20 + (TMR_EXTRA if a.get("tmr") else 0), 0
    arriba, abajo = {"event": (24, 0), "activation": (20, 0), "deactivation": (0, 20)}.get(a.get("trigger"), (0, 0))
    return arriba + (TMR_EXTRA if a.get("tmr") and a.get("trigger") == "event" else 0), abajo


def _ancho_accion(a: dict[str, Any]) -> float:
    """Ancho de la caja de una acción: el de su texto y, si lleva condición o evento encima, el que éstos necesitan para
    no invadir a la caja vecina (el estado de un temporizador, que cambia al simular, no cuenta)."""
    w = max(ACT_MIN, _Pintor.ancho(a["text"], 15) + 24)
    marca = a.get("cond") if a["kind"] == "continuous" else a.get("event") if a.get("trigger") == "event" else None
    return max(w, 12 + 5 + _Pintor.ancho(marca, 13) + 8) if marca else w


def _geometria_acciones(x: float, y: float, actions: list[dict[str, Any]], disposicion: str,
                        suelto: bool = False) -> tuple[list[tuple[dict[str, Any], float, float, float]], list[list[tuple[float, float]]]]:
    """Dónde va cada acción ({acción, x, y del centro, ancho}) y los trazos que las unen entre sí y con la etapa
    (polilíneas). Cuatro colocaciones (figuras (1)–(3) de la norma): «fila» (por defecto; cajas contiguas, la
    representación (2)), «fila-separada» (cajas separadas, unidas a una línea común que sale de la etapa), «matriz-2»
    (cuadrícula de dos columnas, de izquierda a derecha y de arriba abajo; una barra vertical común a su izquierda con
    una derivación a cada fila: la de la segunda columna pasa por debajo de la caja de la primera y sube a la suya) y
    «columna» (una debajo de otra, unidas por una línea vertical que sale de la etapa). Una etapa está en (x, y) y las acciones
    salen de su lado derecho; un grupo suelto empieza en (x, y), el punto medio de su lado izquierdo."""
    ax = x if suelto else x + H + ACT_LINK
    union: list[list[tuple[float, float]]] = [] if suelto else [[(x + H, y), (ax, y)]]
    if not actions:
        return [], union
    bx = ax - ACT_LINK / 2
    if disposicion == "columna":
        ancho, ys = max(_ancho_accion(a) for a in actions), [y]
        for previa, a in zip(actions, actions[1:]):  # el hueco deja sitio a las marcas de las dos cajas vecinas
            ys.append(ys[-1] + 2 * H + max(ACT_COL, _extra(previa)[1] + _extra(a)[0] + 4))
        if len(ys) > 1:
            union.append([(bx, y), (bx, ys[-1])])
            union += [[(bx, cy), (ax, cy)] for cy in (ys if suelto else ys[1:])]
        return [(a, ax, cy, max(ancho, _ancho_accion(a))) for a, cy in zip(actions, ys)], union
    if disposicion == "matriz-2":
        filas = [actions[i:i + 2] for i in range(0, len(actions), 2)]
        w1 = max(_ancho_accion(f[0]) for f in filas)
        w2 = max((_ancho_accion(f[1]) for f in filas if len(f) > 1), default=0)
        x2, ys, canales = ax + w1 + ACT_GAP, [y], []
        for n, f in enumerate(filas):
            if n:  # el hueco deja sitio a las marcas y al canal de la derivación de la fila de arriba
                ys.append(ys[-1] + 2 * H + max(ACT_COL, max(_extra(a)[1] for a in filas[n - 1])
                                               + max(_extra(a)[0] for a in f) + 2 * ACT_CANAL))
            canales.append(ys[-1] + H + max(_extra(a)[1] for a in f) + ACT_CANAL)  # por debajo de la fila, entre las dos cajas
        cajas = [(a, ax if i % 2 == 0 else x2, ys[i // 2], w1 if i % 2 == 0 else w2) for i, a in enumerate(actions)]
        if len(actions) > 1:
            fin = canales[-1] if len(filas[-1]) > 1 else ys[-1]
            union.append([(bx, y), (bx, fin)])
            union += [[(bx, cy), (ax, cy)] for cy in (ys if suelto else ys[1:])]
            union += [[(bx, canales[n]), (x2 - 14, canales[n]), (x2 - 14, ys[n]), (x2, ys[n])]
                      for n, f in enumerate(filas) if len(f) > 1]
        return cajas, union
    if disposicion == "fila-separada":
        cajas, entradas = [], []
        for i, a in enumerate(actions):
            if i:
                ax += ACT_GAP
                entradas.append(ax - 14)
            w = _ancho_accion(a)
            cajas.append((a, ax, y, w))
            ax += w
        if entradas:
            yb = y + H + ACT_BUS
            union.append([(bx, y), (bx, yb), (entradas[-1], yb)])
            if suelto:
                union.append([(bx, y), (cajas[0][1], y)])
            union += [[(ex, yb), (ex, y), (ex + 14, y)] for ex in entradas]
        return cajas, union
    cajas = []
    for a in actions:
        w = _ancho_accion(a)
        cajas.append((a, ax, y, w))
        ax += w
    return cajas, union


def _acciones(pt: _Pintor, x: float, y: float, actions: list[dict[str, Any]], S: dict[str, Any],
              tmp: dict[str, list[dict[str, Any]]], cajas: list[dict[str, Any]] | None = None, etapa: str = "",
              marcadas: set[str] = frozenset(), disposicion: str = "fila", suelto: bool = False,
              grupo: str = "", uniones: list[dict[str, Any]] | None = None, resaltar: bool = False,
              ordenes: list[dict[str, Any]] | None = None) -> None:
    """Las acciones de una etapa (a la derecha de ella, del alto de la etapa) o de un grupo suelto (desde (x, y)), con la
    colocación dada (ver `_geometria_acciones`). Anota en `cajas` el rectángulo de cada una y en `uniones` los trazos de
    la etapa a sus acciones (para seleccionarlos); las de `marcadas` («accion:ID», al editar) se resaltan y, con
    `resaltar`, el enlace de la etapa a sus acciones."""
    if not actions:
        return
    colocadas, union = _geometria_acciones(x, y, actions, disposicion, suelto)
    linea = pt.pen("active" if etapa in (S.get("situation") or []) and not S.get("blocked") else "text")
    for tramo in union:
        pt.poly([(float(a), float(b)) for a, b in tramo], linea, Z_STEP)
    if not suelto and uniones is not None:
        uniones.append({"id": f"enlaceacc:{etapa}", "trazos": union})
    if resaltar:
        for tramo in union:
            pt.poly([(float(a), float(b)) for a, b in tramo], pt.pen("accent", 4), Z_EDIT)
    cabeza = actions[0].get("id", "")
    for a, ax, cy, w in colocadas:
        _caja_accion(pt, ax, cy, a, S, tmp, cajas, etapa, marcadas, suelta=suelto, ancho=w, grupo=grupo, cabeza=cabeza,
                     ordenes=ordenes)


def _caja_accion(pt: _Pintor, ax: float, y: float, a: dict[str, Any], S: dict[str, Any],
                 tmp: dict[str, list[dict[str, Any]]], cajas: list[dict[str, Any]] | None, etapa: str,
                 marcadas: set[str], suelta: bool = False, ancho: float = 0, grupo: str = "", cabeza: str = "",
                 ordenes: list[dict[str, Any]] | None = None) -> float:
    """Una acción con su caja (a la derecha de `ax`, centrada en `y`) y sus marcas: condición, flecha al activar o al
    desactivar, banderita de evento. Una acción suelta o sin completar se dibuja como cualquier otra, con «?» en lo que
    falta. `ancho` es el mínimo (las cajas de una columna miden lo mismo). Devuelve su ancho."""
    top, bottom = y - H, y + H
    force = a["kind"] == "force"
    borrador = bool(a.get("borrador"))
    if a["kind"] == "continuous":
        on = bool(((S.get("outputs") or {}).get(a.get("target")) or {}).get("value")) and not borrador
    else:
        on = force and any(f["order"] == a["id"] for f in S.get("forces") or [])
    if "activeActions" in S:
        on = a["id"] in S["activeActions"] and not borrador
    pt.text(ax + 12, y + 5, a["text"], 15, "active" if on else "text", Z_STEP)
    valor = (S.get("variableReadouts") or {}).get(a.get("target"))
    if a["kind"] == "stored" and valor is not None:
        nombre = a["text"][0]["t"].split(":=", 1)[0].rstrip()
        centro = ax + 12 + pt.ancho(pt.seg(nombre), 15) / 2
        pt.text(centro, y - 10, pt.seg(valor), 10, "readout", Z_STEP, anchor="middle", mono=True)
    w = max(ancho, _ancho_accion(a))
    outer = pt.pen("active", 2.6) if on else pt.pen("text")
    pt.rect(ax, top, w, 2 * H, outer, Z_STEP + (0.005 if on else -0.02), "active_soft" if on else "panel",
            ("Orden de forzado sin completar: no se simula" if force else "Acción sin completar: no se simula") if borrador
            else None)
    if cajas is not None and (not force or borrador):  # (una orden sin completar se mueve y se une como una acción suelta)
        cajas.append({"id": a["id"], "etapa": etapa, "rect": (ax, top, w, 2 * H), "borrador": borrador, "suelta": suelta,
                      "grupo": grupo, "cabeza": cabeza or a["id"], "forzado": force})
    if ordenes is not None and force and not borrador:  # una orden de forzado no es una acción, pero se selecciona y tiene su menú
        ordenes.append({"id": a["id"], "etapa": etapa, "rect": (ax, top, w, 2 * H)})
    if f"accion:{a.get('id')}" in marcadas:
        pt.rect(ax - 3, top - 3, w + 6, 2 * H + 6, pt.pen("accent", 1.6, (5, 3)), Z_EDIT)
    if f"parpadeo:{a.get('id')}" in marcadas:  # parpadeo naranja de un error
        pt.rect(ax - 4, top - 4, w + 8, 2 * H + 8, pt.pen("glow", 3.5), Z_EDIT + 0.5)
    if force:  # orden de forzado: rectángulo doble
        pt.rect(ax + 3, top + 3, w - 6, 2 * H - 6, pt.pen("active" if on else "text", 1.2), Z_STEP + (0.006 if on else -0.01))
    mx = ax + 12
    mark = pt.pen("active" if on else "text")
    if a["kind"] == "continuous" and a.get("cond"):  # acción condicionada: trazo y condición
        pt.line(mx, top, mx, top - 14, mark, Z_STEP)
        pt.text(mx + 5, top - 4, a["cond"], 13, "text", Z_STEP)
        _estado_temporal(pt, mx + 5, top - 4, a["cond"], 13, a.get("condRef"), tmp, Z_STEP)
    elif a.get("trigger") == "activation":  # memorizada al activar: flecha hacia arriba
        pt.line(mx, top, mx, top - 11, mark, Z_STEP)
        pt.poly([(mx - 5, top - 10), (mx, top - 19), (mx + 5, top - 10)], None, Z_STEP, fill="active" if on else "text")
    elif a.get("trigger") == "deactivation":  # memorizada al desactivar: flecha hacia abajo
        pt.line(mx, bottom, mx, bottom + 11, mark, Z_STEP)
        pt.poly([(mx - 5, bottom + 10), (mx, bottom + 19), (mx + 5, bottom + 10)], None, Z_STEP, fill="active" if on else "text")
    elif a.get("trigger") == "event":  # memorizada por evento: banderita y evento
        pt.line(mx, top, mx, top - 20, mark, Z_STEP)
        pt.poly([(mx, top - 20), (mx - 9, top - 15), (mx, top - 10)], None, Z_STEP, fill="active" if on else "text")
        pt.text(mx + 5, top - 11, a.get("event"), 13, "text", Z_STEP)
        _estado_temporal(pt, mx + 5, top - 11, a.get("event"), 13, a.get("condRef"), tmp, Z_STEP)
    return w


# Los cinco tipos de acción del menú «Tipo de acción» (botón derecho) y de la ficha «Acción» de la paleta (la continua): nombre y la
# acción de ejemplo que se dibuja
FICHAS_ACCION = (("continua", "Continua"), ("condicionada", "Condicionada"), ("activacion", "Al activar"),
                 ("desactivacion", "Al desactivar"), ("evento", "Por evento"))


def _accion_ficha(tipo: str) -> dict[str, Any]:
    if tipo == "forzado":  # la orden de forzado (rectángulo doble) del menú «Tipo de acción»; no es ficha de la paleta
        return {"id": "ficha", "kind": "force", "text": [{"t": "G{ }"}]}
    q = [{"t": "Q"}]
    if tipo in ("continua", "condicionada"):
        return {"id": "ficha", "kind": "continuous", "text": q, "cond": [{"t": "c"}] if tipo == "condicionada" else None}
    asigna = [{"t": "Q := 1"}]
    return {"id": "ficha", "kind": "stored", "text": asigna,
            "trigger": {"activacion": "activation", "desactivacion": "deactivation", "evento": "event"}[tipo],
            "event": [{"t": "↑a"}] if tipo == "evento" else None}


def _escena_ficha(tipo: str) -> QGraphicsScene:
    sc = QGraphicsScene()
    _caja_accion(_Pintor(sc), 0, 0, _accion_ficha(tipo), {}, {}, None, "", frozenset())
    return sc


def ficha_accion(tipo: str, escala: float = 1.0, dpr: float = 1.0, opacidad: float = 1.0,
                 comun: bool = False) -> tuple[QPixmap, QPoint]:
    """Una acción de ese tipo dibujada con la misma función que el diagrama (`_caja_accion`), a la escala dada, y el punto
    de la imagen que va bajo el puntero al arrastrarla (el centro de su lado izquierdo, que es donde se coloca). Con
    `comun`, el lienzo es el mismo para los cinco tipos (la caja queda en el mismo sitio en todos: así se alinean los
    iconos de una lista)."""
    sc = _escena_ficha(tipo)
    r = sc.itemsBoundingRect()
    if comun:
        for t, _ in (*FICHAS_ACCION, ("forzado", "")):
            r = r.united(_escena_ficha(t).itemsBoundingRect())
    r = r.adjusted(-4, -4, 4, 4)
    pm = QPixmap(max(1, round(r.width() * escala * dpr)), max(1, round(r.height() * escala * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    p.setOpacity(opacidad)
    sc.render(p, QRectF(0, 0, r.width() * escala, r.height() * escala), r)
    p.end()
    return pm, QPoint(round(-r.left() * escala), round(-r.top() * escala))


def icono_accion(tipo: str, ancho: int = 84, alto: int = 64) -> QIcon:
    """El icono de una ficha de acción (el mismo lienzo para todas), ajustado a ese tamaño."""
    pm, _ = ficha_accion(tipo, 1.0, 2.0, comun=True)
    return QIcon(pm.scaled(ancho * 2, alto * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


def _icono_marcado(icono: QIcon, lado: int = 48) -> QIcon:
    """El icono de la opción marcada de un submenú: el mismo dibujo sobre un fondo menta con borde, para que se distinga."""
    pm = icono.pixmap(lado, lado)
    marcado = QPixmap(pm.size())
    marcado.setDevicePixelRatio(pm.devicePixelRatio())
    marcado.fill(Qt.GlobalColor.transparent)
    p = QPainter(marcado)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(estilo.ACENTO), 2))
    p.setBrush(QColor(estilo.ACENTO_SUAVE))
    ancho, alto = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
    p.drawRoundedRect(QRectF(1, 1, ancho - 2, alto - 2), 5, 5)
    p.drawPixmap(0, 0, pm)
    p.end()
    return QIcon(marcado)


class _EstiloIconos(QProxyStyle):
    """Iconos más grandes en un menú (los de los tipos de acción, que se ven dibujados: a 16 px no se reconocerían)."""

    def pixelMetric(self, metric: Any, option: Any = None, widget: Any = None) -> int:  # noqa: N802
        if metric == QStyle.PixelMetric.PM_SmallIconSize:
            return 48
        return super().pixelMetric(metric, option, widget)


ZOOM_MIN, ZOOM_MAX, ZOOM_PASO = 0.1, 8.0, 1.15
PASO_RUEDA = 60   # px que desplaza un giro de rueda (120 unidades de `angleDelta`) cuando no hace zoom


def modo_rueda(event: Any) -> str:
    """Qué hace un evento de rueda: «zoom» o «desplaza». Solo Ctrl + rueda hace zoom (también el pellizco de un panel táctil de
    Windows, que llega así); la rueda sola desplaza en vertical, Mayús + rueda en horizontal y el gesto de dos dedos de un panel
    táctil, en los dos ejes."""
    return "zoom" if event.modifiers() & Qt.KeyboardModifier.ControlModifier else "desplaza"


def factor_zoom_rueda(event: Any) -> float:
    """El factor de zoom de un giro de rueda. Con Ctrl (o el pellizco de un panel táctil de Windows): `ZOOM_PASO` por cada 120
    unidades de `angleDelta`, así que los giros finos acercan o alejan en proporción. 1 si no hay giro."""
    ang = event.angleDelta()
    d = ang.y() or ang.x()
    if not d:
        return 1.0
    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
        return ZOOM_PASO ** (max(-720, min(720, d)) / 120)
    return ZOOM_PASO if d > 0 else 1 / ZOOM_PASO


def desplazamiento_rueda(event: Any) -> tuple[int, int]:
    """Lo que hay que mover el contenido (px; positivo = a la derecha, abajo) con una rueda sin Ctrl o con el gesto de dos dedos
    de un panel táctil: `pixelDelta` si lo da el sistema; si no, `angleDelta` a `PASO_RUEDA` px por giro de rueda, con Mayús para
    desplazar en horizontal. Un panel táctil puede mover en los dos ejes a la vez. Las barras de desplazamiento restan esto."""
    pix = event.pixelDelta()
    if not pix.isNull():
        return pix.x(), pix.y()
    ang = event.angleDelta()
    dx, dy = ang.x() * PASO_RUEDA / 120, ang.y() * PASO_RUEDA / 120
    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and not dx:
        dx, dy = dy, 0
    return round(dx), round(dy)
ZOOM_AJUSTE_MAX = 1.6   # lo más que se amplía al encajar algo (centrar todo, encuadrar): un dibujo pequeño no se agranda sin límite
MARGEN_AJUSTE = 24   # px libres alrededor del dibujo al centrarlo todo
CLAVE_DEPENDENCIAS = "dibujo/mostrar_dependencias"  # dónde recuerda QSettings si se muestran las dependencias
VISIBLE_MIN = 80     # px del dibujo que, como mínimo, siguen a la vista al desplazarse o alejar (nunca se pierde del todo)
ESTILO_FLECHA = (f"QToolButton {{ background: rgba(255,255,255,235); border: 1px solid {estilo.BORDE_CONTROL}; border-radius: {estilo.R_S}px; "
                 f"color: {estilo.TINTA}; font-size: 13px }} QToolButton:hover {{ background: {estilo.ACENTO_SUAVE} }}")
def estilo_barra_zoom() -> str:
    """La hoja de los controles del zoom con la escala de letra y de controles de ahora (`estilo.activar_escala`)."""
    return (
    f"QFrame#barraZoom {{ background: rgba(255,255,255,242); border: 1px solid {estilo.BORDE_CONTROL}; border-radius: {estilo.R_M}px }} "
    f"QFrame#barraZoom QToolButton {{ border: 1px solid transparent; border-radius: {estilo.R_S}px; padding: 0 8px; min-height: {estilo.ALTO_CONTROL_COMPACTO - 2}px; "
    f"min-width: {estilo.ALTO_CONTROL_COMPACTO - 2}px; font-size: {estilo.T_BASE}px; font-weight: 600; color: {estilo.TINTA}; background: transparent }} "
    f"QFrame#barraZoom QToolButton#pasoZoom {{ font-size: {estilo.T_TITULO}px; padding: 0 4px; }} "  # (más grande, la «+» y la «−» hacían la barra más alta que sus botones)
    f"QFrame#barraZoom QToolButton:hover {{ background: {estilo.ACENTO_SUAVE}; border-color: {estilo.ACENTO_BORDE} }} "
    f"QFrame#barraZoom QToolButton:pressed {{ background: {estilo.PULSADO} }} "
    f"QFrame#barraZoom QToolButton:disabled {{ color: {estilo.DESHABILITADO}; background: transparent; border-color: transparent }} "
    f"QFrame#barraZoom QToolButton[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; padding: 0 7px }} "
    f"QFrame#barraZoom QToolButton#pasoZoom[tecl=\"true\"]:focus {{ padding: 0 3px }} "
    f"QFrame#barraZoom QLabel {{ border: none; min-width: 48px; color: {estilo.TINTA}; font-weight: 600; background: transparent; "
    f"font-family: {estilo.FAMILIA_MONO}; font-size: {estilo.T_CIFRA}px }} "
    f"QFrame#barraZoom[compacta=\"true\"] QToolButton {{ min-width: 28px; padding: 0 2px }} "
    f"QFrame#barraZoom[compacta=\"true\"] QToolButton[tecl=\"true\"]:focus {{ padding: 0 1px }} "
    f"QFrame#barraZoom[compacta=\"true\"] QLabel {{ min-width: 38px }}")
ESTILO_BARRA_ZOOM = estilo_barra_zoom()


class _BarraZoom(QFrame):
    """El recuadro de los controles del zoom: se vuelve a medir cuando cambian la hoja de estilo, la letra o el contenido
    (si no, quedaba tan estrecho como con la letra por defecto y los botones mostraban «Cent…todo»).
    Integrado en la cabecera de la ventana **no cuenta para su ancho mínimo** (`integrada`): la ventana decide si caben sus palabras, y si
    ni los iconos caben vuelve a flotar sobre el dibujo; nunca impide que la ventana baje a media pantalla."""
    integrada = False

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        tam = super().minimumSizeHint()
        return QSize(0, tam.height()) if self.integrada else tam

    def event(self, e: QEvent) -> bool:  # noqa: N802
        resultado = super().event(e)
        if e.type() in (QEvent.Type.LayoutRequest, QEvent.Type.StyleChange, QEvent.Type.FontChange, QEvent.Type.Polish):
            tam = self.layout().totalSizeHint() if self.layout() is not None else self.sizeHint()
            if tam.isValid() and tam != self.size():
                self.resize(tam)
                vista = self.parentWidget()
                if vista is not None and hasattr(vista, "_colocar"):
                    vista._colocar()
        return resultado


MARCADORES_SELECTOR = ("Elija la variable…", "Elija variable…", "Variable…", "…")  # el marcador del desplegable sin variable: el primero que cabe
SELECTOR_PAD_IZQ, SELECTOR_FLECHA = 6, 18  # sangría del texto y ancho de la zona de la flecha del desplegable sobre la acción (más justos que los de un campo)


class _OpcionConPapel(QStyledItemDelegate):
    """Las opciones del desplegable sobre una acción: el nombre a la izquierda y su papel («S», «M») entre paréntesis a la derecha."""

    @staticmethod
    def _separador(index: Any) -> bool:
        return index.data(Qt.ItemDataRole.AccessibleDescriptionRole) == "separator"

    def sizeHint(self, option: Any, index: Any) -> QSize:  # noqa: N802
        if self._separador(index):
            return QSize(option.rect.width(), 7)  # una línea fina con poco margen, no una fila entera
        return super().sizeHint(option, index)

    def paint(self, painter: Any, option: Any, index: Any) -> None:
        if self._separador(index):
            painter.save()
            painter.setPen(QColor(estilo.BORDE_CONTROL))
            y = option.rect.center().y()
            painter.drawLine(option.rect.left() + 6, y, option.rect.right() - 6, y)
            painter.restore()
            return
        papel = index.data(Qt.ItemDataRole.UserRole + 1)
        if not papel:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        estilo_ = opt.widget.style() if opt.widget else QApplication.style()
        estilo_.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        r = opt.rect.adjusted(8, 0, -8, 0)
        painter.save()
        painter.setPen(opt.palette.color(QPalette.ColorGroup.Normal if index.flags() & Qt.ItemFlag.ItemIsEnabled else QPalette.ColorGroup.Disabled,
                                         QPalette.ColorRole.HighlightedText if opt.state & QStyle.StateFlag.State_Selected else QPalette.ColorRole.Text))
        nombre = index.data(Qt.ItemDataRole.DisplayRole).rsplit("  (", 1)[0]
        painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, nombre)
        painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"({papel})")
        painter.restore()


class SelectorAccion(QComboBox):
    """El desplegable que sale sobre una acción del dibujo (doble clic en una continua). Se cierra solo al elegir, con Esc, con un clic fuera o al
    perder el foco; `cerrado` avisa de ello para quitarlo."""
    cerrado = Signal()
    _reclamado = False

    def paintEvent(self, ev: Any) -> None:  # noqa: N802
        """Como un desplegable normal, pero lo que no cabe se acorta con «…» (la ayuda emergente da el nombre entero) y no se corta a medias."""
        p = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        p.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        campo = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, opt, QStyle.SubControl.SC_ComboBoxEditField, self)
        opt.currentText = self.fontMetrics().elidedText(opt.currentText, Qt.TextElideMode.ElideRight, max(0, campo.width() - 4))
        p.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def hidePopup(self) -> None:  # noqa: N802
        super().hidePopup()
        QTimer.singleShot(0, self.cerrado.emit)

    def keyPressEvent(self, ev: Any) -> None:  # noqa: N802
        if ev.key() == Qt.Key.Key_Escape:
            ev.accept()
            self.cerrado.emit()
            return
        super().keyPressEvent(ev)

    def focusOutEvent(self, ev: Any) -> None:  # noqa: N802
        super().focusOutEvent(ev)
        r = ev.reason()
        if r in (Qt.FocusReason.MouseFocusReason, Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ActiveWindowFocusReason):
            QTimer.singleShot(0, self.cerrado.emit)  # (un clic en otro sitio, Tab o cambiar de ventana)
        elif r == Qt.FocusReason.OtherFocusReason and not self._reclamado:  # el dibujo repinta y se queda el foco: se recupera una vez
            self._reclamado = True
            QTimer.singleShot(0, lambda: self.setFocus(Qt.FocusReason.OtherFocusReason) if self.isVisible() else None)


class VistaDiagrama(QGraphicsView):
    """Vista del dibujo. Se ajusta a la ventana hasta que se hace zoom; desde entonces el zoom se mantiene al
    refrescar y solo «Centrar todo» (`ajustar`: Ctrl+0, o el doble clic al simular) vuelve a encajar y centrar todo lo
    dibujado. La rueda acerca o aleja anclada al puntero: el punto del dibujo que tiene debajo no se mueve.

    La escena es el dibujo con un margen de una vista menos `VISIBLE_MIN` a cada lado, a cualquier zoom: se puede anclar
    y desplazar en cualquier sentido sin que el dibujo llegue a salirse del todo de la vista. Las barras de desplazamiento
    solo se ven con zoom manual (al ajustar solo hay que ver el dibujo).

    Junto a los controles del zoom hay «Centrar selección» (al editar: encuadra con `encuadrar` la caja de lo seleccionado, que
    da el controlador con `caja_seleccion`; sin selección, o al simular, está desactivado). En la barra de herramientas está el botón conmutable «Mostrar
    dependencias» (`dependencias`, apagado por defecto): con él se dibujan los trazos discontinuos que unen una macroetapa con
    su expansión y una encapsulante con sus recintos. Se recuerda entre sesiones en los `QSettings` de la ventana que contiene
    la vista (o en `ajustes`, si se le da uno). Con el botón central del ratón (la rueda) pulsado, arrastrar desplaza el dibujo
    como si se agarrara ese punto, al editar y al simular, sin seleccionar ni editar nada: la vista queda en zoom manual."""

    zoomCambiado = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setBackgroundBrush(QColor(COL["panel"]))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)  # el zoom lo ancla `zoom`, no Qt
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self._manual = False
        self._contenido: QRectF | None = None  # lo dibujado, sin márgenes (None si no hay nada)
        self._bordes: list[tuple[QWidget, str]] = []
        self.barra_integrada = False  # los controles del zoom van en la cabecera de la ventana (integrar_barra), no encima del dibujo
        self._solo_iconos = False  # con los controles en la cabecera y poco sitio: solo iconos y el porcentaje (`solo_iconos`)
        self._estrecho = self._bajo = False  # lo último que pidió `compactar`
        self._anchos_barra: dict[tuple[bool, str], int] = {}  # lo que mide el recuadro del zoom con solo iconos o con texto, por escala
        self.dependencias = False  # se dibujan los trazos discontinuos de las dependencias (macroetapa-expansión, encapsulante-recinto)
        self.ajustes: QSettings | None = None  # dónde se recuerda; sin él, los `ajustes` de la ventana que contiene la vista
        self._dependencias_leidas = False
        self._ultimo: tuple[Any, ...] | None = None  # lo último que se dibujó: lo repinta el botón de dependencias
        self._ajuste_pendiente = False  # se encajó el dibujo antes de que la vista se mostrara (con su tamaño final): al mostrarse o al primer cambio de tamaño se encaja de nuevo
        self._encuadrando: QRectF | None = None  # lo que acaba de encuadrarse, hasta que la ventana termina de recolocarse
        self._barra_zoom()
        self.lista_diagnosticos = QListWidget(self)
        self.lista_diagnosticos.setObjectName("listaDiagnosticos")
        self.lista_diagnosticos.setWordWrap(True)
        self.lista_diagnosticos.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista_diagnosticos.setStyleSheet(
            "QListWidget { background:transparent; border:0; font-size:13px; } "
            f"QListWidget[tecl=\"true\"]:focus {{ border:2px dashed {estilo.FOCO}; }} "
            f"QListWidget::item {{ background:rgba(255,255,255,235); color:{estilo.TINTA}; padding:2px; }}")
        self.lista_diagnosticos.hide()
        self.indicador_diagnosticos = QLabel(self)
        self.indicador_diagnosticos.setObjectName("indicadorDiagnosticos")
        self.indicador_diagnosticos.setAccessibleName("Incidencias")
        pm = QPixmap(40,40);pm.fill(Qt.GlobalColor.transparent)
        pintor = QPainter(pm);pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        triangulo = QPainterPath(QPointF(18.6,5.6))
        triangulo.quadTo(20,3,21.4,5.6);triangulo.lineTo(36.6,33.4)
        triangulo.quadTo(38,36,35,36);triangulo.lineTo(5,36)
        triangulo.quadTo(2,36,3.4,33.4);triangulo.closeSubpath()
        pintor.setPen(QPen(QColor(COL["aviso"]),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,
                           Qt.PenJoinStyle.RoundJoin))
        pintor.setBrush(QColor(COL["aviso"]));pintor.drawPath(triangulo)
        pintor.setPen(QPen(QColor("white"),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        pintor.drawLine(20,13,20,24)
        pintor.setPen(Qt.PenStyle.NoPen);pintor.setBrush(QColor("white"))
        pintor.drawEllipse(QPointF(20,30),2.3,2.3);pintor.end()
        self.indicador_diagnosticos.setPixmap(pm)
        self.indicador_diagnosticos.setStyleSheet("background:transparent; padding:0; margin:0; border:0")
        self.indicador_diagnosticos.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.indicador_diagnosticos.hide()
        # El resumen plegado («2 errores», «1 aviso», «Simulación detenida · 1 error») junto al triángulo; un clic (o Espacio) despliega la lista debajo
        self.diagnosticos_abiertos = False
        self.resumen_diagnosticos = QPushButton(self)
        self.resumen_diagnosticos.setObjectName("resumenDiagnosticos")
        self.resumen_diagnosticos.setCheckable(True)
        self.resumen_diagnosticos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resumen_diagnosticos.setAccessibleName("Resumen de incidencias")
        self._estilo_resumen(estilo.AVISO)
        self.resumen_diagnosticos.clicked.connect(self.desplegar_diagnosticos)
        self.resumen_diagnosticos.hide()
        self.controlador: Any = None  # al editar: recibe prensar / mover / soltar / doble con puntos del dibujo
        self.rejilla = False
        self.area_minima: QRectF | None = None
        self.goma = None  # línea provisional de un enlace que se está trazando
        self.cuadro = None  # rectángulo del lazo de selección que se está trazando
        self._marcas: list[Any] = []
        self.iman: Any = None  # el resalte del lado donde se pegaría una acción
        self.destino: Any = None  # el recuadro del parcial (recinto, expansión) donde caería lo que se arrastra desde la paleta
        self.prohibidos: list[Any] = []  # cajas en rojo: lo que se arrastra y no se puede colocar donde está
        self.uniones_acciones: list[dict[str, Any]] = []  # los trazos de cada etapa a sus acciones (para seleccionarlos)
        self.cajas_acciones: list[dict[str, Any]] = []
        self.cajas_ordenes: list[dict[str, Any]] = []  # el rectángulo de cada orden de forzado dibujada
        self._origen = False  # en edición, hasta que se usa el ratón, el dibujo se queda arriba a la izquierda
        self._pulsado = QPoint()  # dónde se pulsó el botón izquierdo: un arrastre de la vista empieza pasada la distancia de arrastre
        self._pan: tuple[QPointF, int, int] | None = None  # el botón central pulsado: dónde, y las barras de desplazamiento entonces
        self._barras()
        self.navegacion = None; self.filtro_parcial = None; self.seleccion_navegacion = set()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Dibujo del GRAFCET")
        self.setAccessibleDescription("Tab y Mayús+Tab recorren elementos; flechas mueven; Intro edita; Esc deselecciona. Ctrl+Tab sale hacia los controles.")

    def focusNextPrevChild(self, siguiente):
        if self.hasFocus() and self.navegacion and not QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            if self.navegacion.recorrer(siguiente): return True
        return super().focusNextPrevChild(siguiente)

    def keyPressEvent(self, e):
        c = self.controlador
        if e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            super().focusNextPrevChild(e.key() == Qt.Key.Key_Tab); e.accept(); return
        delta = {Qt.Key.Key_Left:(-REJILLA,0), Qt.Key.Key_Right:(REJILLA,0), Qt.Key.Key_Up:(0,-REJILLA), Qt.Key.Key_Down:(0,REJILLA)}.get(e.key())
        if c and delta and not e.modifiers():
            c.mover_teclado(*delta); e.accept(); return
        if c and hasattr(c, "girar_transiciones") and not getattr(c, "solo_seleccion", False) and e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and e.modifiers() == (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            c.girar_transiciones(-1 if e.key() == Qt.Key.Key_Left else 1); e.accept(); return  # girar las transiciones seleccionadas
        if c and e.key() == Qt.Key.Key_Escape:
            c.seleccionar([]); e.accept(); return
        if c and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not e.modifiers():
            (c.explicito if hasattr(c, "explicito") else lambda f: f())(self.editar_propiedades_teclado); e.accept(); return
        super().keyPressEvent(e)

    def editar_propiedades_teclado(self):
        c = self.controlador
        if not c or not c.sel or getattr(c,"solo_seleccion",False): return
        ident = c.sel[-1]
        if any(t['id'] == ident for t in c.M['transitions']):
            c.pedir_condicion(ident)
            if hasattr(self.window(), 'props'): self.window().props.prog.setFocus()
        elif any(s['id'] == ident for s in c.M['steps']): c.pedir_etiqueta(ident)
        elif any(a['id'] == ident for a in c.ed.model['actions']) or c._es_borrador(ident):
            sid = next((s["id"] for s in c.M["steps"] if any(a["id"] == ident for a in s.get("actions", []))), None)
            c.pedir_accion(sid, ident)
            if hasattr(self.window(), "props"): self.window().props.accion.variable.setFocus()
        else:
            c.seleccionar([ident]); c.diagrama.window()._abrir_opciones()

    def modo_edicion(self, on: bool, controlador: Any = None, conservar: bool = False) -> None:
        """Al editar: sin arrastre de mano, rejilla, el zoom manual y un dibujo que no se recoloca al añadir elementos (la
        vista conserva lo que se ve aunque la escena cambie de tamaño); al simular, el comportamiento de siempre."""
        self.cerrar_selector()
        self.controlador = controlador if on else None
        self.rejilla = on
        self.area_minima = QRectF(0, 0, 1100, 760) if on else None  # solo da la zona de un dibujo vacío y el origen al abrir
        self.setDragMode(QGraphicsView.DragMode.NoDrag if on else QGraphicsView.DragMode.ScrollHandDrag)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop if on else Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(on)
        self.setAcceptDrops(on)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)
        if conservar:
            self._manual, self._origen, self._encuadrando = True, False, None
            self._barras()
        elif on:
            self.resetTransform()
            self._origen = True  # el primer dibujo en edición empieza arriba a la izquierda
            self._manual = True
            self._barras()
            self._actualizar_escena()
            self._notificar()
        else:
            self._manual = False
            self._origen = False
            self._barras()
        self.goma = None
        self.cuadro = None
        self._actualizar_seleccion()

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

    def marcar_iman(self, lado: tuple[QPointF, QPointF] | None) -> None:
        """Resalta el lado de una acción donde se pegaría la que se arrastra (None lo quita)."""
        if self.iman is not None and self.iman.scene() is self.scene():
            self.scene().removeItem(self.iman)
        self.iman = None
        if lado is not None:
            a, b = lado
            self.iman = self.scene().addLine(a.x(), a.y(), b.x(), b.y(), _Pintor.pen("accent", 5))
            self.iman.setZValue(Z_EDIT + 2)

    def marcar_destino(self, caja: dict[str, float] | None) -> None:
        """Recuadra el parcial (su marco, o la zona de una expansión, que no tiene) donde caería una etapa, una transición o
        una macroetapa soltada ahora desde la paleta; None lo quita. Fuera de todo marco cae en el parcial raíz: no se marca."""
        if self.destino is not None and self.destino.scene() is self.scene():
            self.scene().removeItem(self.destino)
        self.destino = None
        if caja is not None:
            self.destino = self.scene().addRect(QRectF(caja["x0"] - 4, caja["y0"] - 4, caja["x1"] - caja["x0"] + 8,
                                                       caja["y1"] - caja["y0"] + 8), _Pintor.pen("accent", 2, (6, 4)),
                                                QBrush(QColor(31, 111, 235, 18)))
            self.destino.setZValue(Z_EDIT + 2)

    def marcar_prohibido(self, cajas: list[QRectF] | None) -> None:
        """Pone en rojo las cajas de lo que se arrastra y no se puede colocar donde está (encima de otro elemento), con el
        cursor de prohibido; None lo quita."""
        for it in self.prohibidos:
            if it.scene() is self.scene():
                self.scene().removeItem(it)
        self.prohibidos = []
        for r in cajas or []:
            it = self.scene().addRect(r.adjusted(-3, -3, 3, 3), _Pintor.pen("err", 2.2), QBrush(QColor(192, 57, 43, 70)))
            it.setZValue(Z_EDIT + 3)
            self.prohibidos.append(it)
        if self.controlador is not None:
            self.viewport().setCursor(Qt.CursorShape.ForbiddenCursor if cajas else Qt.CursorShape.CrossCursor)

    def trazo_provisional(self, a: QPointF | None, b: QPointF | None = None) -> None:
        """Línea de ayuda mientras se traza un enlace (None la quita)."""
        if self.goma is not None and self.goma.scene() is self.scene():
            self.scene().removeItem(self.goma)
        self.goma = None
        if a is not None and b is not None:
            self.goma = self.scene().addLine(a.x(), a.y(), b.x(), b.y(), _Pintor.pen("accent", 2, (6, 4)))
            self.goma.setZValue(Z_EDIT + 1)

    def lazo(self, a: QPointF | None, b: QPointF | None = None) -> None:
        """Rectángulo de selección mientras se arrastra desde un hueco (None lo quita)."""
        if self.cuadro is not None and self.cuadro.scene() is self.scene():
            self.scene().removeItem(self.cuadro)
        self.cuadro = None
        if a is not None and b is not None:
            self.cuadro = self.scene().addRect(QRectF(a, b).normalized(), _Pintor.pen("accent", 1.2, (5, 3)),
                                               QBrush(QColor(31, 111, 235, 28)))
            self.cuadro.setZValue(Z_EDIT + 3)

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

    def _empezar_pan(self, event: Any) -> None:
        """El botón central (la rueda) pulsado: empieza a desplazar el dibujo, agarrado por el punto pulsado. No llega al
        controlador (no selecciona ni edita nada) y deja la vista en zoom manual, también al simular."""
        self._origen = False
        self._manual = True
        self._barras()
        self._pan = (event.position(), self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def _terminar_pan(self) -> None:
        self._pan = None
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if self.controlador is not None else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._empezar_pan(event)
            return
        if self.filtro_parcial and self.controlador and self.navegacion:
            ident = elemento_en(self.controlador.M, self.mapToScene(event.position().toPoint()))
            d = next((d for d in self.navegacion.datos if d['id'] == ident), None)
            if d and d['parcial'] != self.filtro_parcial: event.accept(); return
        self.setFocus()
        self._origen = False
        self._pulsado = event.position().toPoint()
        if not self._evento("prensar", event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if self._pan is not None:
            if event.buttons() & Qt.MouseButton.MiddleButton:  # el punto agarrado sigue bajo el puntero
                origen, h, v = self._pan
                self.horizontalScrollBar().setValue(h - round(event.position().x() - origen.x()))
                self.verticalScrollBar().setValue(v - round(event.position().y() - origen.y()))
                event.accept()
            else:  # se soltó fuera de la vista
                self._terminar_pan()
            return
        if not self._evento("mover", event):
            if self.controlador is None and not self._manual and event.buttons() & Qt.MouseButton.LeftButton:
                if (event.position().toPoint() - self._pulsado).manhattanLength() < QApplication.startDragDistance():
                    return  # un clic con algo de temblor no es arrastrar: la vista ni se mueve ni deja de reencajarse
                self._manual = True  # arrastrar el dibujo con la mano es mover la vista: ya no se reencaja sola
                self._barras()
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._pan is not None:
            self._terminar_pan()
            event.accept()
            return
        if not self._evento("soltar", event):
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: Any) -> None:  # noqa: N802
        """Al editar, el botón derecho ofrece lo que se puede hacer con lo que hay debajo (añadir acción, editarla…)."""
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        punto = self.mapToScene(event.pos())
        controlador = self.controlador
        if getattr(controlador,"solo_seleccion",False):return
        seleccion = list(controlador.sel) if controlador is not None else []
        caja = (controlador.accion_en(punto) or controlador.orden_en(punto)) if controlador is not None else None
        ident = (caja["id"] if caja else elemento_en(controlador.M, punto)) if controlador is not None else None
        if self.filtro_parcial and self.navegacion:
            d = next((d for d in self.navegacion.datos if d["id"] == ident), None)
            if d and d["parcial"] != self.filtro_parcial: event.accept(); return
        opciones = controlador.menu(punto) if controlador is not None else []
        if controlador is not None and ident in seleccion and len(seleccion) > 1:
            controlador.sel, controlador.accion = seleccion, None
            controlador.cambiado.emit()
        elif controlador is not None and ident is not None and caja is None and "|" not in ident and ident not in controlador.sel:
            controlador.seleccionar([ident])
        if controlador is not None and hasattr(self, "menu_portapapeles"):
            extras=self.menu_portapapeles(punto, ident is not None)
            finales=[x for x in extras if x[0]=='Enviar a plano…'];extras=[x for x in extras if x[0]!='Enviar a plano…']
            opciones=extras+([('-',None)]+opciones if opciones else [])
            if finales:opciones+=[('-',None)]+finales
        if not opciones:
            super().contextMenuEvent(event)
            return
        menu = self.menu_contextual(opciones)
        menu.exec(event.globalPos())

    def menu_contextual(self, opciones: list[tuple[str, Any]]) -> QMenu:
        """El menú del botón derecho: «-» es un separador, una lista en lugar de la función es un submenú (sus opciones
        pueden llevar un tercer elemento, el icono) y lo que el controlador marca en `menu_marcadas` (el tipo actual de
        una acción, como «Etapa inicial» en una etapa) lleva su marca. Lo que está en `menu_desmarcadas` también es una
        casilla (como «Enlace de activación» en una etapa de un recinto), pero sin marcar."""
        menu = QMenu(self)
        marcadas = getattr(self.controlador, "menu_marcadas", set())
        desmarcadas = getattr(self.controlador, "menu_desmarcadas", set())
        for texto, accion in opciones:
            if texto == "-":
                menu.addSeparator()
                continue
            if isinstance(accion, list):  # un submenú: sus opciones, con las marcadas del controlador
                sub = menu.addMenu(texto)
                if any(len(o) > 2 for o in accion):  # con iconos de verdad (dibujados): más grandes
                    estilo = _EstiloIconos(sub.style())
                    estilo.setParent(sub)
                    sub.setStyle(estilo)
                for t, f, *icono in accion:
                    a = sub.addAction(icono[0], t, f) if icono else sub.addAction(t, f)
                    if t in marcadas:
                        a.setCheckable(True)
                        a.setChecked(True)
                        if icono:  # con iconos grandes la marca de la casilla no se ve: fila en negrita y icono con fondo
                            fuente = a.font()
                            fuente.setBold(True)
                            a.setFont(fuente)
                            a.setIcon(_icono_marcado(icono[0]))
                continue
            a = menu.addAction(texto, accion) if accion is not None else menu.addAction(texto)
            a.setEnabled(accion is not None)
            if texto in marcadas or texto in desmarcadas:
                a.setCheckable(True)
                a.setChecked(texto in marcadas)
        return menu

    def _barra_zoom(self) -> None:
        """Controles del zoom sobre el dibujo, arriba a la derecha: «−», porcentaje, «+», «Centrar todo» y «Centrar selección».
        Los dos últimos llevan icono y texto; en una ventana estrecha (pantalla partida) solo el icono, con su ayuda. La
        ventana aloja «Mostrar dependencias» en su barra de herramientas."""
        self.barra = _BarraZoom(self)
        self.barra.setObjectName("barraZoom")
        self.barra.setStyleSheet(estilo_barra_zoom())
        lay = QHBoxLayout(self.barra)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(2)
        self.b_menos = QToolButton()
        self.b_menos.setObjectName("pasoZoom")
        self.b_menos.setText("−")
        self.b_menos.setToolTip("Alejar (Ctrl+−)")
        self.b_menos.clicked.connect(self.alejar)
        self.l_zoom = QLabel("100 %")
        self.l_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.b_mas = QToolButton()
        self.b_mas.setObjectName("pasoZoom")
        self.b_mas.setText("+")
        self.b_mas.setToolTip("Acercar (Ctrl+=)")
        self.b_mas.clicked.connect(self.acercar)
        self.b_ajustar = QToolButton()
        self.b_ajustar.setText("Centrar todo")
        self.b_ajustar.setIcon(estilo.icono("ajustar", estilo.TINTA, tam=20))
        self.b_ajustar.setIconSize(QSize(20, 20))
        self.b_ajustar.setToolTip("Centrar todo el dibujo en la ventana (Ctrl+0; en simulación, también doble clic)")
        self.b_ajustar.clicked.connect(self.ajustar)
        self.b_seleccion = QToolButton()
        self.b_seleccion.setText("Centrar selección")
        self.b_seleccion.setIcon(estilo.icono("centrar", estilo.TINTA, tam=20))
        self.b_seleccion.setIconSize(QSize(20, 20))
        self.b_seleccion.setToolTip("Centrar selección: encaja y centra en la ventana lo que hay seleccionado (solo al editar). "
                                    "Sin nada seleccionado, o al simular, no hace nada")
        self.b_seleccion.setEnabled(False)
        self.b_seleccion.clicked.connect(self.centrar_seleccion)
        for b in (self.b_menos, self.b_mas, self.b_ajustar, self.b_seleccion):
            b.setAccessibleName(b.toolTip().split(" (")[0].split(":")[0])
        self.b_dependencias = QToolButton()
        self.b_dependencias.setText("Mostrar dependencias")
        self.b_dependencias.setCheckable(True)
        self.b_dependencias.setToolTip("Mostrar dependencias: dibuja los trazos discontinuos que unen una macroetapa con su "
                                       "expansión y una encapsulante con sus recintos. Apagado por defecto; se recuerda")
        self.b_dependencias.clicked.connect(self.mostrar_dependencias)
        for w in (self.b_menos, self.l_zoom, self.b_mas, self.b_ajustar, self.b_seleccion):
            lay.addWidget(w)
        self.b_dependencias.setParent(self)
        self.b_dependencias.hide()  # la ventana la aloja en la barra de herramientas
        self.compactar(False, False)
        self.barra.adjustSize()

    def escalar(self) -> None:
        """Cambió la escala de letra y de controles (pantalla completa o no): la barra del zoom vuelve a medirse con la suya."""
        self.barra.setStyleSheet(estilo_barra_zoom())
        self.barra.layout().invalidate()
        self.barra.adjustSize()
        self._colocar()

    def compactar(self, estrecho: bool, bajo: bool) -> None:
        """Ventana estrecha: «Centrar todo» y «Centrar selección» pasan a solo icono; baja: los controles se quedan en 32 px. Con los
        controles en la cabecera y sin sitio para sus palabras (`solo_iconos`), también solo el icono, con su ayuda."""
        self._estrecho, self._bajo = bool(estrecho), bool(bajo)
        self._estilo_barra(self._estrecho or self._bajo or self._solo_iconos)
        self.barra.layout().invalidate()
        self.barra.adjustSize()
        self._colocar()

    def _estilo_barra(self, iconos: bool) -> None:
        """Los botones de «Centrar» con su texto o solo con su icono, y el recuadro con sus márgenes normales o los compactos."""
        estilo_boton = Qt.ToolButtonStyle.ToolButtonIconOnly if iconos else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        for b in (self.b_ajustar, self.b_seleccion):
            b.setToolButtonStyle(estilo_boton)
        self._compacta = iconos
        estilo.poner(self.barra, compacta=iconos)
        for hijo in self.barra.findChildren(QWidget):  # (la regla `[compacta="true"] QToolButton` mira a un ascendiente: cada hijo vuelve a aplicarla)
            estilo.repulir(hijo)
        self._margenes_barra()
        self.barra.layout().setSpacing(0 if iconos else 2)

    def solo_iconos(self, on: bool) -> None:
        """Con los controles del zoom en la cabecera y poco sitio: solo iconos y el porcentaje (cada botón con su ayuda). Así el recuadro mide
        lo justo (≈ 160 px) y **nunca impone ancho** a la ventana: con las palabras pedía 242 px más y la ventana no bajaba de 848 px."""
        if bool(on) != self._solo_iconos:
            self._solo_iconos = bool(on)
            self.compactar(self._estrecho, self._bajo)

    def ancho_barra(self, iconos: bool) -> int:
        """Lo que mide el recuadro del zoom con solo iconos o con las palabras de «Centrar todo» y «Centrar selección» (se mide una vez por
        escala: la ventana lo usa para decidir si caben en la cabecera)."""
        clave = (iconos, estilo.ESCALA)
        if clave not in self._anchos_barra:
            ahora = self._compacta
            self._estilo_barra(iconos)
            self.barra.layout().invalidate()
            self.barra.layout().activate()
            self._anchos_barra[clave] = self.barra.layout().totalSizeHint().width()
            self._estilo_barra(ahora)
            self.barra.layout().invalidate()
            self.barra.layout().activate()
        return self._anchos_barra[clave]

    def _margenes_barra(self) -> None:
        """Los márgenes del recuadro: apretados si es compacto y, integrado en la cabecera, también arriba y abajo (así sube lo mínimo la
        fila del título y el dibujo conserva su alto)."""
        self.barra.layout().setContentsMargins(*((2, 2, 2, 2) if getattr(self, "_compacta", False) else
                                                 (4, 1, 4, 1) if self.barra_integrada else (4, 3, 4, 3)))

    def integrar_barra(self, diseno: Any = None) -> None:
        """Con `diseno` (un QBoxLayout de la cabecera de la ventana), los controles del zoom se mueven allí y dejan de flotar
        sobre el dibujo (ni lo tapan ni reservan su franja al centrar todo); con None, vuelven a flotar arriba a la derecha.
        La ventana lo pide con la ventana estrecha o baja."""
        if diseno is not None and not self.barra_integrada:
            diseno.addWidget(self.barra)
            self.barra_integrada = self.barra.integrada = True
        elif diseno is None and self.barra_integrada:
            self.barra.setParent(self)
            self.barra_integrada = self.barra.integrada = False
            self.solo_iconos(False)  # (flotando sobre el dibujo vuelve a llevar sus palabras)
        else:
            return
        self._margenes_barra()
        self.barra.layout().invalidate()
        self.barra.show()
        self.barra.adjustSize()
        self._colocar()
        if not self._manual:
            self.ajustar()

    def _ajustes(self) -> QSettings | None:
        """Dónde se recuerda el estado de las dependencias: los `ajustes` propios o, si no hay, los de la ventana que contiene
        la vista (la ventana principal los llama así); sin ninguno, no se recuerda."""
        a = self.ajustes if self.ajustes is not None else getattr(self.window(), "ajustes", None)
        return a if isinstance(a, QSettings) else None

    def _leer_dependencias(self) -> None:
        """La primera vez que hay dónde leerlo, el estado guardado de «Mostrar dependencias» (apagado si no lo hay)."""
        a = self._ajustes()
        if a is None or self._dependencias_leidas:
            return
        self._dependencias_leidas = True
        self.dependencias = bool(a.value(CLAVE_DEPENDENCIAS, False, type=bool))
        self.b_dependencias.setChecked(self.dependencias)

    def mostrar_dependencias(self, on: bool) -> None:
        """Muestra u oculta los trazos discontinuos de las dependencias (macroetapa-expansión, encapsulante-recinto), recuerda
        el estado y repinta lo último dibujado. Solo cambia esos trazos: ni la disposición, ni los marcos, ni la selección."""
        self.dependencias, self._dependencias_leidas = bool(on), True
        self.b_dependencias.setChecked(self.dependencias)
        a = self._ajustes()
        if a is not None:
            a.setValue(CLAVE_DEPENDENCIAS, self.dependencias)
            a.sync()
        if self._ultimo is not None:
            self.mostrar(*self._ultimo)

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
        if not self.barra_integrada:
            self.barra.move(w - self.barra.width() - sb - 8, 8)
        bx, bw, bb = w - 252 - self.verticalScrollBar().sizeHint().width() - 8, 252, 2  # (reserva siempre el ancho de la barra, se vea o no)
        # el aviso va siempre en el mismo sitio y con el mismo ancho, esté donde esté el zoom
        for b, lugar in self._bordes:
            if lugar == "izquierda":
                b.move(0, (h - b.height()) // 2)
            elif lugar == "derecha":
                b.move(w - b.width() - sb, (h - b.height()) // 2)
            else:
                b.move((w - b.width()) // 2, h - b.height() - sh)
            b.raise_()
        if not self.barra_integrada:
            self.barra.raise_()
        if hasattr(self, "lista_diagnosticos"):
            lista = self.lista_diagnosticos
            ancho = max(80, bw - 48)
            lista.setFixedWidth(ancho)
            for i in range(lista.count()):
                item = lista.item(i)
                caja = lista.fontMetrics().boundingRect(QRect(0,0,max(1,ancho-28),10000), Qt.TextFlag.TextWordWrap, item.text())
                tam = QSize(ancho-20, caja.height()+8)
                if item.sizeHint() != tam:
                    item.setSizeHint(tam)
            lista.doItemsLayout()
            alto = min(max(30, h // 3), sum(max(20, lista.sizeHintForRow(i)) for i in range(lista.count())) + 4)
            lista.setFixedHeight(alto)
            y0 = bb + 6 if self.barra_integrada else self.barra.y() + self.barra.height() + 2  # (con el zoom flotando arriba a la derecha, el aviso va debajo: nunca se pisan)
            boton = self.resumen_diagnosticos
            alto_boton = estilo.ALTO_CONTROL_COMPACTO  # C1: el alto de un control, centrado con el triángulo (de 40 px)
            boton.setGeometry(bx + (8 if getattr(self, "vacio_diagnosticos", False) else 48), y0 + (40 - alto_boton) // 2, ancho, alto_boton)
            lista.move(bx + 48, y0 + 38)
            self.indicador_diagnosticos.setGeometry(bx, y0, 40, 40)
            region = QRegion()
            for i in range(lista.count()):
                r = lista.visualItemRect(lista.item(i))
                caja = lista.fontMetrics().boundingRect(QRect(0, 0, max(1,r.width()-8), 10000),
                                                        Qt.TextFlag.TextWordWrap, lista.item(i).text())
                region |= QRegion(r.x(), r.y(), min(r.width(), caja.width()+8), r.height())
            if lista.verticalScrollBar().isVisible():
                region |= QRegion(lista.verticalScrollBar().geometry())
            lista.setMask(region)
            lista.raise_()
            boton.raise_()
            self.indicador_diagnosticos.raise_()

    def _estilo_resumen(self, color: str) -> None:
        """El resumen de incidencias es un enlace: sin recuadro ni fondo (tampoco al pasar el puntero ni al pulsar), con el texto y la flecha del
        color del aviso (el ámbar oscuro, o el rojo de error si hay errores). Con Tab, el anillo de foco de siempre."""
        if getattr(self, "_color_resumen", None) == color:
            return
        self._color_resumen = color
        self.resumen_diagnosticos.setStyleSheet(
            f"QPushButton#resumenDiagnosticos {{ background:transparent; color:{color}; border:0; padding:0 8px; text-align:left; "
            f"font-size:13px; font-weight:600; min-height:0; }} "
            f"QPushButton#resumenDiagnosticos:hover, QPushButton#resumenDiagnosticos:pressed, QPushButton#resumenDiagnosticos:checked "
            f"{{ background:transparent; color:{color}; }} "
            f"QPushButton#resumenDiagnosticos[tecl=\"true\"]:focus {{ border:2px dashed {estilo.FOCO}; padding:0 6px; }}")

    def actualizar_diagnosticos(self, visible: bool, resumen: str = "", vacio: bool = False) -> None:
        """Muestra u oculta los avisos de arriba a la derecha: el triángulo y, a su lado, `resumen` plegado con su flecha; la lista de mensajes,
        debajo, solo si está desplegada (si lo estaba y llega otro aviso, sigue desplegada; si desaparecen todos, se oculta todo y vuelve a plegada)."""
        if not visible or vacio:
            self.diagnosticos_abiertos = False
        self.vacio_diagnosticos = bool(visible and vacio)
        self.resumen_diagnosticos.setChecked(self.diagnosticos_abiertos)
        if vacio:  # «Mostrar errores» marcado y nada que avisar: «Sin errores» en tono neutro, sin triángulo ni flecha
            self._estilo_resumen(estilo.TINTA_2)
            self.resumen_diagnosticos.setText("Sin errores")
            self.resumen_diagnosticos.setToolTip("No hay errores ni avisos")
        else:
            self._estilo_resumen(estilo.ERROR if "error" in resumen.lower() else estilo.AVISO)
            self.resumen_diagnosticos.setText(f"{resumen}  {'▾' if self.diagnosticos_abiertos else '▸'}")
            self.resumen_diagnosticos.setToolTip(resumen + (" · clic para plegar la lista" if self.diagnosticos_abiertos else " · clic para ver los mensajes"))
        self.lista_diagnosticos.setVisible(visible and not vacio and self.diagnosticos_abiertos)
        self.resumen_diagnosticos.setVisible(visible)
        self.resumen_diagnosticos.setEnabled(not vacio)
        self.indicador_diagnosticos.setVisible(visible and not vacio)
        self._colocar()

    def desplegar_diagnosticos(self, abierto: bool) -> None:
        """Despliega o pliega la lista de mensajes bajo el resumen."""
        self.diagnosticos_abiertos = bool(abierto)
        self.actualizar_diagnosticos(self.resumen_diagnosticos.isVisible(), self.resumen_diagnosticos.text().rsplit("  ", 1)[0], getattr(self, "vacio_diagnosticos", False))

    def escala(self) -> float:
        return self.transform().m11()

    def _notificar(self) -> None:
        self.l_zoom.setText(f"{round(self.escala() * 100)} %")
        self.zoomCambiado.emit(self.escala())

    def _a_escena(self, c: QPointF) -> QPointF:
        """El punto de la escena que está en el punto `c` de la vista (sin redondear a píxeles)."""
        inversa, _ = self.viewportTransform().inverted()
        return inversa.map(c)

    def _situar(self, p: QPointF, c: QPointF) -> None:
        """Desplaza la vista para que el punto `p` de la escena quede en el punto `c` de la vista (±0,5 px)."""
        q = self.viewportTransform().map(p)
        hb, vb = self.horizontalScrollBar(), self.verticalScrollBar()
        hb.setValue(hb.value() + round(q.x() - c.x()))
        vb.setValue(vb.value() + round(q.y() - c.y()))

    def _base(self) -> QRectF | None:
        """Lo que hay que mantener a la vista: lo dibujado o, si no hay nada, el área mínima de edición."""
        return self._contenido if self._contenido is not None else self.area_minima

    def _actualizar_escena(self, esquina: QPointF | None = None) -> None:
        """La escena es lo dibujado con, a cada lado, lo que cabe en la vista menos `VISIBLE_MIN` px (en unidades del
        dibujo, al zoom actual): así se puede anclar el zoom en cualquier punto y desplazarse hasta el borde sin perder
        del todo el dibujo. Lo que se ve no se mueve aunque la escena cambie de tamaño."""
        base = self._base()
        if base is None:
            return
        esquina = esquina if esquina is not None else self._a_escena(QPointF(0, 0))
        k = self.escala() or 1.0
        vw, vh = self.viewport().width(), self.viewport().height()
        mx, my = max(vw - VISIBLE_MIN, vw // 2) / k, max(vh - VISIBLE_MIN, vh // 2) / k
        visible = QRectF(esquina.x(), esquina.y(), vw / k, vh / k)
        self.scene().setSceneRect(base.adjusted(-mx, -my, mx, my).united(visible))
        self._situar(esquina, QPointF(0, 0))

    def _barras(self) -> None:
        """Las barras de desplazamiento solo con zoom manual: al ajustar el dibujo cabe entero y no hay nada que mover."""
        politica = Qt.ScrollBarPolicy.ScrollBarAlwaysOn if self._manual else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        horizontal = vertical = politica  # fijas: así la vista no cambia de tamaño al desplazarse o acercar
        if self._manual and self.controlador is not None and self._contenido is not None:
            # Al editar, el zoom es siempre «manual» (el dibujo no se reencaja solo), pero una barra solo sirve si lo dibujado no cabe
            # en esa dirección: se decide con el tamaño entero de la vista (no con el que deja la barra), así no oscila.
            k = self.escala() or 1.0
            marco = 2 * self.frameWidth()
            on, off = Qt.ScrollBarPolicy.ScrollBarAlwaysOn, Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            horizontal = on if self._contenido.width() * k + MARGEN_AJUSTE > self.width() - marco else off
            vertical = on if self._contenido.height() * k + MARGEN_AJUSTE > self.height() - marco else off
        self.setHorizontalScrollBarPolicy(horizontal)
        self.setVerticalScrollBarPolicy(vertical)
        self._colocar()

    def _al_origen(self) -> None:
        """En edición, hasta que se usa el ratón, el dibujo se queda arriba a la izquierda (donde empieza su área)."""
        base = self._base()
        if base is not None:
            r = base.adjusted(-14, -14, 14, 14)
            if self.area_minima is not None:
                r = r.united(self.area_minima)
            self._situar(r.topLeft(), QPointF(0, 0))

    def mostrar(self, M: dict[str, Any], S: dict[str, Any], sel: set[str] | None = None,
                marcados: set[str] | None = None, naranja: set[str] | None = None) -> None:
        self._leer_dependencias()
        if self.controlador is None and sel is None: sel = self.seleccion_navegacion
        self._ultimo = (M, S, sel, marcados, naranja)
        self.goma = None
        self.cuadro = None
        self._marcas = []
        self.uniones_acciones = []
        self.cajas_ordenes = []
        self.iman = None
        self.destino = None
        self.prohibidos = []
        self.cajas_acciones = dibujar(self.scene(), M, S, sel, marcados, naranja, self.uniones_acciones, self.cajas_ordenes,
                                      self.dependencias)
        if self.navegacion: self.navegacion.actualizar(M, S)
        r = self.scene().itemsBoundingRect()
        self._contenido = r if not r.isEmpty() else None
        self._actualizar_seleccion()
        self._actualizar_escena()
        if not self._manual:
            self.ajustar()
        elif self._origen:
            self._al_origen()
        if self._manual and self.controlador is not None:
            self._barras()  # lo dibujado cambió: puede haber dejado de caber, o de sobrar la barra

    def guardar_encuadre(self) -> tuple:
        """Fija el zoom y un punto en coordenadas de pantalla durante un cambio de paneles/modo."""
        estado = (self.transform(), self._a_escena(QPointF(0, 0)), self.viewport().mapToGlobal(QPoint(0, 0)))
        self._manual, self._origen, self._encuadrando = True, False, None
        return estado

    def restaurar_encuadre(self, estado: tuple) -> None:
        transformacion, punto, pantalla = estado
        self._manual, self._origen, self._encuadrando = True, False, None
        self.setTransform(transformacion)
        self._barras()
        self._actualizar_escena()
        local = QPointF(self.viewport().mapFromGlobal(pantalla))
        k = self.escala() or 1.0
        visible = QRectF(punto.x() - local.x() / k, punto.y() - local.y() / k,
                         self.viewport().width() / k, self.viewport().height() / k)
        self.scene().setSceneRect(self.sceneRect().united(visible.adjusted(-1, -1, 1, 1)))
        self._situar(punto, local)
        self._notificar()

    def ajustar(self) -> None:
        """«Centrar todo»: encaja y centra lo dibujado (no el área mínima vacía de edición), con un margen y, arriba, el alto
        de los controles del zoom de más (para que no tapen el dibujo). Al editar, el zoom queda manual; al simular, vuelve a
        ajustarse solo con cada cambio de tamaño del dibujo."""
        self._manual = self.controlador is not None  # al editar, el zoom no se recoloca solo
        self._origen = False
        self._ajuste_pendiente = not self.isVisible()
        self._barras()
        self._encajar(self._base(), reservar_barra=True)
        if self._manual and self.controlador is not None:
            # al editar, las barras se decidieron con el zoom de antes: con el nuevo puede sobrar una (al pasar de una ventana grande a una
            # pequeña quedaba una barra vertical inútil hasta el siguiente Play/Stop) o hacer falta otra; se revisan y, si cambian, se reencaja
            antes = (self.horizontalScrollBarPolicy(), self.verticalScrollBarPolicy())
            self._barras()
            if (self.horizontalScrollBarPolicy(), self.verticalScrollBarPolicy()) != antes:
                self._encajar(self._base(), reservar_barra=True)

    def _caja_seleccion(self) -> QRectF | None:
        """El rectángulo de la selección del controlador (`caja_seleccion`, con las cajas de lo seleccionado), o None si no hay
        controlador (al simular) ni selección."""
        caja = getattr(self.controlador, "caja_seleccion", None)
        r = caja() if callable(caja) else None
        return r if r is not None and not r.isEmpty() else None

    def _actualizar_seleccion(self) -> None:
        self.b_seleccion.setEnabled(self._caja_seleccion() is not None)

    def centrar_seleccion(self) -> None:
        """«Centrar selección»: encuadra (`encuadrar`) lo que hay seleccionado; sin selección, no hace nada."""
        r = self._caja_seleccion()
        if r is not None:
            self.encuadrar(r)

    def encuadrar(self, r: QRectF) -> None:
        """«Encuadrar» (la expansión de una macroetapa, un recinto…): encaja y centra en la vista el rectángulo `r` de la escena,
        con el mismo margen y el mismo tope de zoom (`ZOOM_AJUSTE_MAX`) que «Centrar todo». El zoom queda manual, también al
        simular: la vista se queda donde se ha puesto hasta «Centrar todo»."""
        self._manual = True
        self._origen = False
        self._barras()
        self._encajar(r)
        self._encuadrando = r  # (al avisar de lo encuadrado, la ventana puede recolocar sus paneles y cambiar el tamaño de la vista)
        QTimer.singleShot(0, self._terminar_encuadre)

    def _terminar_encuadre(self) -> None:
        self._encuadrando = None

    def _encajar(self, r: QRectF | None, reservar_barra: bool = False) -> None:
        """Pone el zoom que hace caber `r` con `MARGEN_AJUSTE` alrededor (sin pasar de `ZOOM_AJUSTE_MAX`) y lo centra. Con
        `reservar_barra`, arriba se deja además el alto de los controles del zoom, que están encima del dibujo."""
        if r is None or r.width() <= 0 or r.height() <= 0:
            return
        vw, vh = self.viewport().width(), self.viewport().height()
        arriba = MARGEN_AJUSTE + (self.barra.height() if reservar_barra and not self.barra_integrada else 0)
        k = min(max(vw - 2 * MARGEN_AJUSTE, 1) / r.width(), max(vh - arriba - MARGEN_AJUSTE, 1) / r.height(), ZOOM_AJUSTE_MAX)
        self.resetTransform()
        self.scale(k, k)
        self._actualizar_escena()
        self._situar(r.center(), QPointF(self.viewport().width() / 2,
                                          (arriba + self.viewport().height() - MARGEN_AJUSTE) / 2))
        self._notificar()

    def zoom(self, factor: float, ancla: QPointF | None = None) -> None:
        """Zoom manual: queda fijo hasta «Centrar todo» o doble clic. El punto de la vista `ancla` (por defecto el
        centro) no se mueve: el que tiene debajo del dibujo sigue debajo."""
        self.cerrar_selector()
        k = min(max(self.escala() * factor, ZOOM_MIN), ZOOM_MAX) / self.escala()
        self._manual = True
        self._origen = False
        self._barras()  # (con zoom manual aparecen las barras y la vista cambia de tamaño: el centro, el de ahora)
        c = ancla if ancla is not None else QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
        p = self._a_escena(c)
        self.scale(k, k)
        self._actualizar_escena()
        self._situar(p, c)
        self._notificar()

    def abrir_selector(self, rect: Any, opciones: list[tuple[Any, ...]], actual: str, al_elegir: Any) -> None:
        """Un desplegable abierto sobre el rectángulo `rect` (x, y, ancho, alto del dibujo) con las `opciones` (texto, dato, habilitada[, papel: se
        pinta a la derecha]). Va **dentro** de la caja de la acción: mide a lo sumo su ancho interior a la escala de la vista (lo que pide su opción
        más larga, si cabe); un nombre que no cabe se acorta con «…» y su ayuda emergente lo da entero. Cerrado muestra la variable actual o, si no
        hay, el marcador «Elija la variable…» (no es una opción; con poco sitio, uno más corto, ver `MARCADORES_SELECTOR`). Elegir una llama a
        `al_elegir(dato)` y cierra. Esc, un clic fuera, desplazar o hacer zoom lo cierran sin cambiar nada."""
        self.cerrar_selector()
        x, y, w, h = rect
        r = self.mapFromScene(QRectF(x, y, w, h)).boundingRect()
        cb = SelectorAccion(self.viewport())
        cb.setAccessibleName("Variable de la acción")
        cb.setItemDelegate(_OpcionConPapel(cb))
        for texto, dato, habilitada, *papel in opciones:
            cb.addItem(texto, dato)
            cb.setItemData(cb.count() - 1, texto, Qt.ItemDataRole.ToolTipRole)
            if papel and papel[0]:
                cb.setItemData(cb.count() - 1, papel[0], Qt.ItemDataRole.UserRole + 1)
            if not habilitada:
                cb.model().item(cb.count() - 1).setEnabled(False)
        cb.setStyleSheet(f"QComboBox {{ padding:0 2px 0 {SELECTOR_PAD_IZQ}px; }} QComboBox:focus {{ padding:0 1px 0 {SELECTOR_PAD_IZQ - 1}px; }} "
                         f"QComboBox::drop-down {{ width:{SELECTOR_FLECHA}px; }}")
        cb.setFixedHeight(estilo.ALTO_CONTROL)
        margen = max(2, round(2 * self.escala()))  # (el trazo de la caja)
        interior = max(SELECTOR_FLECHA, r.width() - 2 * margen)
        fm = cb.fontMetrics()
        util = interior - SELECTOR_PAD_IZQ - SELECTOR_FLECHA - 4  # (borde y foco)
        marcador = next((m for m in MARCADORES_SELECTOR if fm.horizontalAdvance(m) <= util), MARCADORES_SELECTOR[-1])
        cb.setPlaceholderText(actual or marcador)
        cb.setCurrentIndex(cb.findData(actual) if actual else -1)
        texto_actual = cb.currentText() if actual else ""
        pide = max([fm.horizontalAdvance(cb.itemText(i)) for i in range(cb.count())] + [0 if actual else fm.horizontalAdvance(marcador)]) + SELECTOR_PAD_IZQ + SELECTOR_FLECHA + 4
        cb.setMinimumWidth(0)
        ancho = max(SELECTOR_FLECHA, min(interior, pide))
        cb.setToolTip(texto_actual if texto_actual and fm.horizontalAdvance(texto_actual) > ancho - SELECTOR_PAD_IZQ - SELECTOR_FLECHA - 4
                      else "Variable de la acción")
        cb.setGeometry(r.left() + margen, r.center().y() - estilo.ALTO_CONTROL // 2, ancho, estilo.ALTO_CONTROL)
        necesario = cb.view().sizeHintForColumn(0) + 24  # (la lista mide lo que el cuadro, salvo que un nombre no quepa)
        if necesario > ancho:
            cb.view().setMinimumWidth(necesario)

        def elegido(i: int) -> None:
            dato = cb.itemData(i)
            self.cerrar_selector()
            if dato:
                al_elegir(dato)
        cb.activated.connect(elegido)
        cb.cerrado.connect(self.cerrar_selector)
        self._selector = cb
        cb.show()
        cb.raise_()
        cb.setFocus(Qt.FocusReason.OtherFocusReason)
        QTimer.singleShot(0, lambda: cb.showPopup() if self._selector is cb and cb.isVisible() else None)

    def cerrar_selector(self) -> None:
        """Quita el desplegable de la acción, si hay uno."""
        cb, self._selector = getattr(self, "_selector", None), None
        if cb is not None:
            cb.hide()
            cb.deleteLater()

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # noqa: N802
        if getattr(self, "_selector", None) is not None:
            self.cerrar_selector()  # (el desplegable va sobre la acción: si el dibujo se mueve, se cierra)
        super().scrollContentsBy(dx, dy)

    def acercar(self) -> None:
        self.zoom(ZOOM_PASO)

    def alejar(self) -> None:
        self.zoom(1 / ZOOM_PASO)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        """Al mostrarse (ya dentro de su ventana) lee el estado guardado de las dependencias, si no lo había leído, y repinta."""
        super().showEvent(event)
        if self._ajuste_pendiente:
            self.ajustar()
        antes = self.dependencias
        self._leer_dependencias()
        if self.dependencias != antes and self._ultimo is not None:
            self.mostrar(*self._ultimo)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        """Cambiar el tamaño de la vista no recentra ni reencaja: el dibujo queda anclado arriba a la izquierda (mismo zoom y mismo punto del
        dibujo en la esquina de la vista; al agrandar, más sitio a la derecha y abajo; al encoger, se recorta por ahí); es lo que pasa al editar
        y con zoom manual al simular. Solo «Centrar todo», abrir un ejemplo o un proyecto, y encuadrar encajan. (Lo que se encajó antes de mostrarse la vista, sí se encaja de nuevo con su tamaño final.)"""
        esquina = self._a_escena(QPointF(0, 0))  # (antes de que Qt recoloque las barras con el tamaño nuevo)
        super().resizeEvent(event)
        if (self._ajuste_pendiente and self.isVisible()) or not self._manual:
            self.ajustar()  # (sin zoom manual al simular, la vista se reencaja con la ventana, como siempre: REQ-SIM-03)
        else:
            self._barras()  # (las barras dependen de lo que cabe en la vista)
            self._actualizar_escena(esquina)  # la vista cambia de tamaño y con ella los márgenes de la escena
            if self._origen:
                self._al_origen()
            elif self._encuadrando is not None:  # recién encuadrado: se vuelve a encajar con el tamaño que ha quedado
                self._encajar(self._encuadrando)
        self._colocar()

    def wheelEvent(self, event: Any) -> None:  # noqa: N802
        """Ctrl + rueda acerca o aleja anclado al puntero, y el pellizco de un panel táctil también; la rueda sola desplaza en
        vertical, Mayús + rueda en horizontal y el gesto de dos dedos de un panel táctil, en los dos ejes (`modo_rueda`)."""
        self._origen = False
        if modo_rueda(event) == "zoom":
            if (f := factor_zoom_rueda(event)) != 1.0:
                self.zoom(f, event.position())
            event.accept()
            return
        dx, dy = desplazamiento_rueda(event)
        if dx or dy:
            self._manual = True  # mover la vista a mano: ya no se reencaja sola (como arrastrar con el botón central)
            self._barras()
            h, v = self.horizontalScrollBar(), self.verticalScrollBar()
            h.setValue(h.value() - dx)
            v.setValue(v.value() - dy)
        event.accept()

    def viewportEvent(self, event: Any) -> bool:  # noqa: N802
        """El pellizco de un panel táctil (gesto nativo de zoom, macOS y Linux) acerca o aleja anclado a los dedos."""
        if event.type() == QEvent.Type.NativeGesture and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self._origen = False
            self.zoom(max(0.2, 1.0 + event.value()), event.position())
            event.accept()
            return True
        return super().viewportEvent(event)

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
            libre = True
            if hasattr(self.controlador, "sobrevolar"):  # una acción que se acerca a otra: el lado donde se pegaría
                libre = self.controlador.sobrevolar(event.mimeData().text(), self.mapToScene(event.position().toPoint()))
            if libre is False:  # encima de otro elemento: el cursor de prohibido, y no se puede soltar
                event.ignore()
            else:
                event.acceptProposedAction()

    def dragLeaveEvent(self, event: Any) -> None:  # noqa: N802
        self.marcar_iman(None)
        self.marcar_destino(None)
        self.marcar_prohibido(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: Any) -> None:  # noqa: N802
        """Un elemento arrastrado desde la paleta se coloca donde se suelta."""
        self.marcar_iman(None)
        self.marcar_destino(None)
        self.marcar_prohibido(None)
        if self.controlador is not None and event.mimeData().hasText():
            self.controlador.colocar(event.mimeData().text(), self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()

    def centrar_en(self, p: QPointF) -> None:
        self.centerOn(p)

    def centrar_si_fuera(self, p: QPointF) -> bool:
        """Lleva a la vista el punto si queda fuera de lo que se ve; devuelve si se desplazó."""
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        if visible.contains(p):
            return False
        self.centerOn(p)
        return True


def imagen(M: dict[str, Any], S: dict[str, Any], escala: float = 2.0, dependencias: bool = False) -> QImage:
    """El dibujo como imagen (para pruebas y para guardar una figura)."""
    scene = QGraphicsScene()
    dibujar(scene, M, S, dependencias=dependencias)
    r = scene.itemsBoundingRect().adjusted(-14, -14, 14, 14)
    img = QImage(max(1, int(r.width() * escala)), max(1, int(r.height() * escala)), QImage.Format.Format_ARGB32)
    img.fill(QColor(COL["panel"]))
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    scene.render(p, QRectF(0, 0, img.width(), img.height()), r)
    p.end()
    return img
