"""Paleta de elementos y panel de opciones del editor (P-IMP-32, P-IMP-43, P-IMP-44, P-IMP-47).

La paleta agrupa fichas arrastrables en Etapas, Transiciones, Acciones y Jerarquías.
Los encabezados solo organizan la lista; un clic en una ficha muestra su ayuda.

El panel de opciones (abajo, a todo el ancho, al editar) muestra y cambia la configuración de lo seleccionado, con dos
zonas: a la izquierda una columna estrecha con los campos y a la derecha lo ancho.
- Transición: etiqueta, si se muestra y comentario; a la derecha, el programador por bloques de la receptividad (con el
  texto de la fórmula, cómo se escribe y cómo se dibuja, y «Crear las que faltan» para las variables que no existen).
- Etapa: etiqueta, tipo, comentario y colocación de las acciones; a la derecha, la lista de sus acciones y sus botones.
- Acción: frase, variable (y límite de una acción antigua) a la izquierda (`PanelAccion`; el tipo se cambia con botón
  derecho sobre la acción); a la derecha el
  programador del valor de una memorizada y, si es condicionada o por evento, el de su condición o su evento.
- Macroetapa, recinto (su marco), expansión, grafcet parcial suelto y orden de forzado (también la que aún no está completa): una
  ficha compacta (`FichaJerarquia`) con su descripción y los mismos botones que el botón derecho (Encuadrar la expansión,
  Renombrar…, Encuadrar la encapsulante, Configurar, Editar o Quitar la orden…; el doble clic en una orden la edita); una
  etapa lleva la suya sobre su lista de acciones (encapsulante, de un recinto, entrada o salida de una expansión, Forzar un
  parcial…).
- Enlace, barra de simultaneidad, varios elementos o nada: lo suyo, o la invitación a elegir un elemento.
Cada cambio se aplica al momento con las operaciones de Edicion / grafcet/editor.py (una operación de deshacer).
"""
from __future__ import annotations

import html
import re
from typing import Any, Callable

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
                               QStackedWidget, QStyledItemDelegate, QStyle, QVBoxLayout, QWidget)

from grafcet.routing import TALLO_E, TALLO_T
from grafcet.view import norm

from .acciones import PanelAccion
from .bloques import FlowLayout, Programador
from .diagrama import ACT_MIN, COL, H, MARK, TB, VACIO_H, VACIO_W, _html, ficha_accion
from .edicion import COLOCACIONES, CONTINUAS, Parpadeo

NARANJA = COL["glow"]
ANCHO_COLUMNA = 230  # la columna estrecha de campos del panel de opciones
NOMBRES = {"etapa": "Etapa", "transicion": "Transición", "simultaneidad": "Simultaneidad", "accion:continua": "Acción",
           "macroetapa": "Macroetapa", "encapsulante": "Encapsulante", "parcial": "Grafcet parcial", "forzado": "Forzado"}
AYUDAS = {"etapa": "Etapa: arrástrela al dibujo", "transicion": "Transición: arrástrela al dibujo",
          "simultaneidad": "Barra de simultaneidad (doble trazo, Y): une varias etapas a una transición, o una transición "
                           "a varias etapas. Se ensancha estirando de sus extremos. Las alternativas (O) no son un elemento: "
                           "se construyen con el ratón enlazando una etapa con una segunda transición, o arrastrando a un enlace.",
          "accion:continua": "Acción continua: se cumple mientras la etapa está activa. Arrástrela al dibujo (queda suelta, con «?»); "
                             "se une a una etapa arrastrando desde su punto de unión de la izquierda hasta la etapa, o pegándola al "
                             "lado de otra acción. Para otro tipo (condicionada, al activar, al desactivar, por evento), botón "
                             "derecho sobre la acción, «Tipo de acción»",
          "macroetapa": "Macroetapa (divisiones arriba y abajo): arrástrela al dibujo y crea la macroetapa con su expansión, "
                        "con la etapa de entrada y la de salida a su derecha. Suelte etapas y transiciones dentro de la "
                        "expansión para rellenarla; botón derecho en la macroetapa, «Encuadrar la expansión», para verla "
                        "(«Mostrar dependencias», en la barra de herramientas, dibuja los trazos que la unen a la macroetapa)",
          "encapsulante": "Etapa encapsulante (esquinas cortadas): arrástrela al dibujo, o convierta una etapa con el botón "
                          "derecho. Botón derecho en la encapsulante, «Añadir recinto…», crea un recinto; se rellena soltando "
                          "etapas dentro de su marco, y «Enlace de activación» en una de ellas la marca (*); «Encuadrar el "
                          "recinto» lo muestra",
          "parcial": "Grafcet parcial (marco redondeado con «G»): arrástrelo a un hueco del dibujo y crea un grafcet parcial "
                     "vacío, con nombre propio (G1, G2…) y un marco vacío. Suelte etapas y transiciones dentro de su marco "
                     "para rellenarlo; «Renombrar…» (botón derecho o doble clic en su marco) le cambia el nombre, y una orden "
                     "de forzado («Forzado») de una etapa de otro parcial puede forzarlo. No se pone encima de otro "
                     "elemento ni de otro marco",
          "forzado": "Orden de forzado (rectángulo doble «G{ }»): arrástrela al dibujo como una acción; queda suelta («G?{?}») y "
                     "no se simula. Doble clic en ella (o su panel de opciones) abre el diálogo para elegir el parcial al que "
                     "fuerza, la forma (explícita, la situación actual, vacía o inicial) y, si es explícita, sus etapas. Se une "
                     "a una etapa arrastrando desde su punto de unión de la izquierda hasta la etapa (o desde el lado derecho de "
                     "la etapa hasta ella), soltándola sobre la etapa o pegándola a su fila de acciones; unida y completa, "
                     "mientras esa etapa está activa impone esa situación al parcial. Supr la quita. Hace falta otro parcial "
                     "(un grafcet parcial, un recinto o una macroetapa) al que forzar"}
SECCIONES = (
    ("Etapas", ("etapa", "etapa_inicial")),
    ("Transiciones", ("transicion", "simultaneidad:apertura", "simultaneidad:cierre")),
    ("Acciones", tuple("accion:" + t for t in ("continua", "condicionada", "activacion", "desactivacion", "evento"))),
    ("Jerarquías", ("encapsulante", "macroetapa", "forzado", "parcial")),
)
NOMBRES.update({"etapa_inicial": "Etapa inicial", "simultaneidad:apertura": "Apertura de simultaneidad",
                "simultaneidad:cierre": "Cierre de simultaneidad", "accion:continua": "Continua",
                "accion:condicionada": "Condicionada", "accion:activacion": "Al activar",
                "accion:desactivacion": "Al desactivar", "accion:evento": "Por evento"})
AYUDAS["etapa_inicial"] = "Etapa inicial: arrástrela al dibujo. Se crea con el doble cuadrado de etapa inicial."
for t in ("apertura", "cierre"):
    AYUDAS["simultaneidad:" + t] = ("Apertura: una transición hacia varias etapas. " if t == "apertura" else
                                    "Cierre: varias etapas hacia una transición. ") + AYUDAS["simultaneidad"]
for t in ("continua", "condicionada", "activacion", "desactivacion", "evento"):
    AYUDAS["accion:" + t] = ("Acción " + NOMBRES["accion:" + t].lower() + ": arrástrela al dibujo; "
                            "únala a una etapa desde su punto de unión y configúrela con doble clic o en Propiedades.")
COLOCABLES = tuple(h for _, claves in SECCIONES for h in claves)


def icono(h: str) -> QIcon:
    """Dibujo del elemento, para reconocerlo en la paleta (con el trazo de la norma: etapa cuadrada, transición, barras,
    y la caja de una acción con su enlace a la izquierda, como la dibuja el diagrama)."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(COL["text"]), 2))
    if h == "parcial":  # un grafcet parcial: marco redondeado y «G» en la esquina inferior
        p.drawRoundedRect(QRectF(5, 10, 54, 44), 9, 9)
        fuente = QFont("Arial")
        fuente.setPixelSize(19)
        fuente.setBold(True)
        p.setFont(fuente)
        p.drawText(QRectF(36, 34, 22, 22), Qt.AlignmentFlag.AlignCenter, "G")
    elif h in ("etapa", "etapa_inicial", "macroetapa", "encapsulante"):
        p.drawLine(32, 2, 32, 14)
        p.drawRect(QRectF(16, 14, 32, 32))
        p.drawLine(32, 46, 32, 62)
        k = 32 / (2 * H)  # el lado de la etapa del dibujo (2·H) pasa a 32: las marcas de la macroetapa y de la encapsulante, a escala
        if h == "etapa_inicial":
            p.drawRect(QRectF(20, 18, 24, 24))
        elif h == "macroetapa":  # dos divisiones horizontales, arriba y abajo
            p.drawLine(QPointF(16, 14 + MARK * k), QPointF(48, 14 + MARK * k))
            p.drawLine(QPointF(16, 46 - MARK * k), QPointF(48, 46 - MARK * k))
        elif h == "encapsulante":  # las cuatro esquinas cortadas en diagonal
            c = round(0.22 * 2 * H) * k
            for (xa, ya), (xb, yb) in (((16 + c, 14), (16, 14 + c)), ((48 - c, 14), (48, 14 + c)),
                                       ((16, 46 - c), (16 + c, 46)), ((48, 46 - c), (48 - c, 46))):
                p.drawLine(QPointF(xa, ya), QPointF(xb, yb))
    elif h == "transicion":
        p.drawLine(32, 2, 32, 62)
        p.setPen(QPen(QColor(COL["text"]), 4))
        p.drawLine(20, 32, 44, 32)
    elif h.startswith("accion:"):
        p.end()
        from .diagrama import icono_accion
        return icono_accion(h.partition(":")[2])
    elif h == "forzado":  # la orden de forzado: rectángulo doble, con su enlace a la izquierda, y «G{ }»
        p.drawLine(2, 32, 14, 32)
        p.drawRect(QRectF(14, 14, 48, 36))
        p.setPen(QPen(QColor(COL["text"]), 1))
        p.drawRect(QRectF(17.5, 17.5, 41, 29))
        p.setPen(QPen(QColor(COL["text"]), 2))
        fuente = QFont("Arial")
        fuente.setPixelSize(13)
        fuente.setBold(True)
        p.setFont(fuente)
        p.drawText(QRectF(14, 14, 48, 36), Qt.AlignmentFlag.AlignCenter, "G{ }")
    else:
        if h == "simultaneidad:apertura":
            p.translate(0, 64)
            p.scale(1, -1)
        p.drawLine(16, 2, 16, 26)
        p.drawLine(48, 2, 48, 26)
        p.drawLine(4, 28, 60, 28)
        if h.startswith("simultaneidad"):
            p.drawLine(4, 34, 60, 34)
        p.drawLine(32, 36 if h.startswith("simultaneidad") else 30, 32, 62)
    p.end()
    return QIcon(pm)


def figura(h: str, escala: float = 1.0, dpr: float = 1.0) -> tuple[QPixmap, QPoint]:
    """El elemento tal como quedará en el dibujo, al zoom del dibujo, para llevarlo pegado al puntero al arrastrarlo
    desde la paleta, y el punto que va bajo el puntero: el que se coloca donde se suelta (el centro de la etapa o de la
    transición; el centro del trazo superior de la barra; el centro del lado izquierdo de una acción)."""
    if h.startswith("accion:"):
        return ficha_accion(h.partition(":")[2], escala, dpr, 0.85)
    m = 4  # margen, en píxeles
    if h == "parcial":  # el marco vacío que se creará (VACIO_W × VACIO_H), con una «G» abajo; bajo el puntero, su centro
        w, alto = VACIO_W, VACIO_H
        pm = QPixmap(round((w * escala + 2 * m) * dpr), round(((alto + 18) * escala + 2 * m) * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        p.setOpacity(0.85)
        p.translate(m, m)
        p.scale(escala, escala)
        p.setPen(QPen(QColor(COL["muted"]), 1.6))
        p.drawRoundedRect(QRectF(0, 0, w, alto), 16, 16)
        fuente = QFont("Arial")
        fuente.setPixelSize(14)
        p.setFont(fuente)
        p.setPen(QPen(QColor(COL["text"]), 1))
        p.drawText(QPointF(w - 40, alto + 15), "G")
        p.end()
        return pm, QPoint(round(w / 2 * escala + m), round(alto / 2 * escala + m))
    if h == "forzado":  # el rectángulo doble de la orden, con la medida de una acción, y bajo el puntero el centro de su lado izquierdo
        w, alto = ACT_MIN, 2 * H
        pm = QPixmap(round((w * escala + 2 * m) * dpr), round((alto * escala + 2 * m) * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        p.setOpacity(0.85)
        p.translate(m, m)
        p.scale(escala, escala)
        p.fillRect(QRectF(0, 0, w, alto), QColor(COL["panel"]))
        p.setPen(QPen(QColor(COL["text"]), 1.6))
        p.drawRect(QRectF(0, 0, w, alto))
        p.setPen(QPen(QColor(COL["text"]), 1.2))
        p.drawRect(QRectF(3, 3, w - 6, alto - 6))
        fuente = QFont("Arial")
        fuente.setPixelSize(15)
        p.setFont(fuente)
        p.drawText(QPointF(12, alto / 2 + 5), "G{ }")
        p.end()
        return pm, QPoint(round(m), round(alto / 2 * escala + m))
    if h in ("etapa", "etapa_inicial", "macroetapa", "encapsulante"):
        w, alto, cx, cy = 2 * H, 2 * H + 2 * TALLO_E, H, TALLO_E + H
    elif h == "transicion":
        w, alto, cx, cy = 2 * TB, 2 * TALLO_T, TB, TALLO_T
    else:
        w, alto, cx, cy = 120, 4 + 2 * TALLO_E, 60, TALLO_E
    pm = QPixmap(round((w * escala + 2 * m) * dpr), round((alto * escala + 2 * m) * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(0.85)
    p.translate(m, m)
    p.scale(escala, escala)
    p.setPen(QPen(QColor(COL["text"]), 1.6))
    if h in ("etapa", "etapa_inicial", "macroetapa", "encapsulante"):
        p.fillRect(QRectF(0, TALLO_E, 2 * H, 2 * H), QColor(COL["accent_soft"]))
        p.drawRect(QRectF(0, TALLO_E, 2 * H, 2 * H))
        p.drawLine(QPointF(H, 0), QPointF(H, TALLO_E))
        p.drawLine(QPointF(H, TALLO_E + 2 * H), QPointF(H, alto))
        if h == "etapa_inicial":
            p.drawRect(QRectF(4, TALLO_E + 4, 2 * H - 8, 2 * H - 8))
        elif h == "macroetapa":  # las divisiones de la macroetapa, como las dibuja el diagrama
            for y in (TALLO_E + MARK, TALLO_E + 2 * H - MARK):
                p.drawLine(QPointF(0, y), QPointF(2 * H, y))
        elif h == "encapsulante":  # y las esquinas cortadas de la encapsulante
            c = round(0.22 * 2 * H)
            for (xa, ya), (xb, yb) in (((c, 0), (0, c)), ((2 * H - c, 0), (2 * H, c)), ((0, 2 * H - c), (c, 2 * H)),
                                       ((2 * H, 2 * H - c), (2 * H - c, 2 * H))):
                p.drawLine(QPointF(xa, TALLO_E + ya), QPointF(xb, TALLO_E + yb))
    elif h == "transicion":
        p.drawLine(QPointF(TB, 0), QPointF(TB, alto))
        p.setPen(QPen(QColor(COL["muted"]), 2.4))
        p.drawLine(QPointF(0, TALLO_T), QPointF(2 * TB, TALLO_T))
    else:
        if h == "simultaneidad:apertura":
            p.translate(0, alto)
            p.scale(1, -1)
            cy = alto - cy
        for x in (30, 90):
            p.drawLine(QPointF(x, 0), QPointF(x, TALLO_E))
        p.drawLine(QPointF(0, TALLO_E), QPointF(120, TALLO_E))
        p.drawLine(QPointF(0, TALLO_E + 4), QPointF(120, TALLO_E + 4))
        p.drawLine(QPointF(60, TALLO_E + 4), QPointF(60, alto))
    p.end()
    return pm, QPoint(round(cx * escala + m), round(cy * escala + m))


class _DelegadoPaleta(QStyledItemDelegate):
    """Filas limpias y cabeceras de sección; el icono conserva el símbolo existente."""
    def paint(self, p: QPainter, opcion: Any, indice: Any) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = opcion.rect.adjusted(5, 1, -5, -1)
        clave = indice.data(Qt.ItemDataRole.UserRole)
        fuente = opcion.font
        if not clave:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#eaf6f5"))
            p.drawRoundedRect(QRectF(r), 4, 4)
            fuente.setBold(True)
            p.setFont(fuente)
            p.setPen(QColor("#167e80"))
            p.drawText(r.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, indice.data())
        else:
            if opcion.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#edf7f6"))
                p.drawRoundedRect(QRectF(r), 4, 4)
            icono = indice.data(Qt.ItemDataRole.DecorationRole)
            icono.paint(p, r.left() + 6, r.center().y() - 14, 28, 28)
            p.setFont(fuente)
            p.setPen(QColor("#172e4d"))
            p.drawText(r.adjusted(43, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, indice.data())
        p.restore()


class Paleta(QListWidget):
    """La lista de fichas del grafcet (etapa, transición, simultaneidad, acción, macroetapa, encapsulante, grafcet parcial y
    forzado). Las fichas solo se colocan arrastrándolas al dibujo; un clic en una ficha no hace nada salvo mostrar su ayuda
    (señal `ayuda`)."""

    ayuda = Signal(str)
    REJILLA = QSize(188, 34)  # fila compacta: icono a la izquierda y nombre a la derecha
    ICONO = QSize(28, 28)
    FILAS = 9  # filas visibles solicitadas; el resto queda accesible con desplazamiento
    FILAS_MIN = 3  # hasta dónde se encoge en una ventana baja (con desplazamiento vertical): fija el mínimo de alto de la ventana
    CLAVES: tuple[str, ...] = COLOCABLES

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListView.ViewMode.ListMode)  # iconos grandes con su nombre: se ven y se arrastran
        self.setIconSize(self.ICONO)
        self.setMovement(QListView.Movement.Static)  # Static desactiva el arrastre: se activa después
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.setObjectName("paletaElementos")
        self.setItemDelegate(_DelegadoPaleta(self))
        self.setMouseTracking(True)
        for titulo, claves in SECCIONES:
            cabecera = QListWidgetItem(titulo)
            cabecera.setFlags(Qt.ItemFlag.NoItemFlags)
            cabecera.setSizeHint(QSize(188, 28))
            cabecera.setBackground(QColor("#e8f6f5"))
            cabecera.setForeground(QColor("#137e80"))
            f = cabecera.font()
            f.setBold(True)
            cabecera.setFont(f)
            self.addItem(cabecera)
            for h in claves:
                it = QListWidgetItem(icono(h), self.nombre(h))
                it.setData(Qt.ItemDataRole.UserRole, h)
                it.setToolTip(self.texto_ayuda(h))
                it.setSizeHint(self.REJILLA)
                self.addItem(it)
        self.setCurrentRow(-1)
        self.itemClicked.connect(lambda it: self.ayuda.emit(self.texto_ayuda(it.data(Qt.ItemDataRole.UserRole)) if it.data(Qt.ItemDataRole.UserRole) else ""))
        # Altura flexible; el desplazamiento conserva todas las secciones accesibles.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @staticmethod
    def nombre(h: str) -> str:
        return NOMBRES[h]

    @staticmethod
    def texto_ayuda(h: str) -> str:
        return AYUDAS[h]

    def ancho_minimo(self) -> int:
        """Ancho para icono, nombre y barra vertical, sin desplazamiento horizontal."""
        return 218

    def alto_filas(self, filas: int) -> int:
        """El alto de `filas` filas de fichas, con el marco."""
        return filas * self.REJILLA.height() + 2 * self.frameWidth() + 2

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.ancho_minimo(), self.alto_filas(self.FILAS))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.ancho_minimo(), self.alto_filas(self.FILAS_MIN))

    escala = staticmethod(lambda: 1.0)  # zoom del dibujo; lo pone la ventana

    def startDrag(self, actions: Any) -> None:  # noqa: N802
        """Se arrastra el elemento mismo, al tamaño con que se verá en el dibujo, no el icono de la lista."""
        it = self.currentItem()
        if it is None or not it.data(Qt.ItemDataRole.UserRole):
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData([it]))
        pm, punto = figura(it.data(Qt.ItemDataRole.UserRole), self.escala(), self.devicePixelRatioF())
        drag.setPixmap(pm)
        drag.setHotSpot(punto)
        drag.exec(Qt.DropAction.CopyAction)

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:  # noqa: N802
        m = QMimeData()
        if items and items[0].data(Qt.ItemDataRole.UserRole):
            m.setText(items[0].data(Qt.ItemDataRole.UserRole))
        return m


def _formulario(w: QWidget) -> QFormLayout:
    """Formulario arriba de la columna y que se estrecha: si no cabe, el rótulo va encima del campo."""
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    f = QFormLayout()
    f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    lay.addLayout(f)
    lay.addStretch(1)
    return f


def _desplegable() -> QComboBox:
    """Desplegable que no impone su ancho al panel."""
    c = QComboBox()
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(6)
    return c


class FichaJerarquia(QWidget):
    """La descripción de un elemento de jerarquía (macroetapa, encapsulante, recinto, orden de forzado, entrada o salida de una
    expansión…) y sus botones: los mismos que el botón derecho (`Edicion.acciones_jerarquia`), con las casillas (el enlace de
    activación) marcadas o no. Los botones son siempre los mismos objetos, en un orden fijo: se enseñan o se esconden según el
    elemento, así que un clic puede cambiar la selección sin destruir el botón que lo emite. Sin nada que decir ni ofrecer,
    la ficha entera se esconde."""
    ORDEN = ("Encuadrar la expansión", "Renombrar…", "Convertir en encapsulante", "Añadir recinto…", "Encuadrar el recinto",
             "Encuadrar los recintos", "Convertir en etapa ordinaria", "Enlace de activación", "Encuadrar la encapsulante",
             "Encuadrar la macroetapa", "Forzar un parcial…", "Configurar orden de forzado…", "Editar orden de forzado…",
             "Quitar orden de forzado")  # el mismo orden que el botón derecho
    CASILLAS = ("Enlace de activación",)

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.texto = QLabel()
        self.texto.setWordWrap(True)
        self.texto.setStyleSheet("font-weight: 600")
        lay.addWidget(self.texto)
        self.caja = QWidget()
        self.flujo = FlowLayout(self.caja, 4)
        lay.addWidget(self.caja)
        self.botones: dict[str, QAbstractButton] = {}
        self._funciones: dict[str, Callable[[], Any]] = {}
        for t in self.ORDEN:
            self._crear(t)
        self.hide()

    def _crear(self, texto: str) -> QAbstractButton:
        b: QAbstractButton = QCheckBox(texto) if texto in self.CASILLAS else QPushButton(texto)
        b.clicked.connect(lambda _=False, t=texto: self._pulsar(t))
        self.flujo.addWidget(b)
        self.botones[texto] = b
        b.hide()
        return b

    def _pulsar(self, texto: str) -> None:
        funcion = self._funciones.get(texto)
        if funcion is not None:
            funcion()

    def mostrar(self, e: Any, ident: str | None) -> None:
        """La ficha de `ident` (en `e`, la edición); sin elemento o sin nada que enseñar, se esconde."""
        ficha = e.ficha_jerarquia(ident) if e is not None and ident else None
        self.texto.setText(ficha["texto"] if ficha else "")
        self.texto.setVisible(bool(ficha and ficha["texto"]))
        activos = set()
        self._funciones = {}
        for texto, funcion, estado in (ficha["botones"] if ficha else []):
            b = self.botones.get(texto) or self._crear(texto)
            self._funciones[texto] = funcion
            if estado is not None:
                b.blockSignals(True)
                b.setChecked(estado)
                b.blockSignals(False)
            activos.add(texto)
        for texto, b in self.botones.items():
            b.setVisible(texto in activos)
        self.caja.setVisible(bool(activos))
        self.setVisible(ficha is not None)
        self.caja.updateGeometry()

    def textos_visibles(self) -> list[str]:
        """Los botones que se ven ahora, en su orden."""
        return [t for t, b in self.botones.items() if not b.isHidden()]


class PanelPropiedades(QWidget):
    """Las opciones del elemento seleccionado, con campos editables (el panel «Opciones» de abajo)."""

    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.e: Any = None
        self.ident: str | None = None
        self._llenando = False
        self._anterior: tuple | None = None  # lo que programaron los bloques la última vez (para volver al texto de solo lectura)
        self._objetivo: tuple | None = None  # lo que programan los bloques: ("transicion", ID) o ("accion", ID, campo)
        self.pagina = "vacio"
        self.parpadeo_crear = Parpadeo(self)  # «Crear las que faltan» parpadea si un nombre no vale
        self.parpadeo_crear.cambia.connect(self._pintar_crear)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(3)
        self.titulo = QLabel()
        self.titulo.setObjectName("tituloPropiedades")
        lay.addWidget(self.titulo)
        self.vacio = QLabel(self.TEXTO_VACIO)
        self.vacio.setObjectName("ayudaPropiedades")
        lay.addWidget(self.vacio)
        self.cuerpo = QWidget()
        cuerpo = QHBoxLayout(self.cuerpo)
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(14)
        lay.addWidget(self.cuerpo, 1)
        # Izquierda, la columna estrecha de campos; derecha, lo ancho (lista de acciones, programadores, enlace, barra)
        self.izq = QStackedWidget()
        self.izq.setFixedWidth(ANCHO_COLUMNA)
        self.izq.addWidget(QWidget())  # 0: nada que mostrar en la columna
        self.izq.addWidget(self._etapa())  # 1
        self.izq.addWidget(self._transicion())  # 2
        self.accion = PanelAccion()  # 3
        self.izq.addWidget(self.accion)
        self.ficha_izq = FichaJerarquia()  # 4: macroetapa, recinto, expansión u orden de forzado
        pagina = QWidget()
        lh = QVBoxLayout(pagina)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.addWidget(self.ficha_izq)
        lh.addStretch(1)
        self.izq.addWidget(pagina)
        cuerpo.addWidget(self.izq)
        self.der = QStackedWidget()
        self.der.addWidget(self._vacio())  # 0
        self.der.addWidget(self._lista_acciones())  # 1
        self.der.addWidget(self._programacion())  # 2
        self.der.addWidget(self._enlace())  # 3
        self.der.addWidget(self._barra())  # 4
        cuerpo.addWidget(self.der, 1)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

    # -- páginas -----------------------------------------------------------------------------------
    def _programacion(self) -> QWidget:
        """Lo ancho de una transición o una acción: a la izquierda el programador del valor de una acción memorizada y,
        a su derecha, el programador por bloques de la receptividad de una transición o de la condición (o el evento) de una
        acción, con su texto, cómo se escribe, cómo se dibuja y «Crear las que faltan»."""
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)
        hl.addWidget(self.accion.caja_valor, 1)
        self.pagina_bloques = QWidget()
        hl.addWidget(self.pagina_bloques, 1)
        lay = QVBoxLayout(self.pagina_bloques)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.l_bloques = QLabel()
        self.l_bloques.setStyleSheet(f"color: {COL['muted']}")
        lay.addWidget(self.l_bloques)
        self.prog = Programador(lambda: self.e.fuente_bloques() if self.e is not None else ({}, []))
        self.prog.cambiado.connect(self._desde_bloques)
        self.prog.al_deshacer = lambda: self.e is not None and self.e.deshacer()  # Ctrl+Z en la ventana ampliada
        self.prog.al_rehacer = lambda: self.e is not None and self.e.rehacer()
        lay.addWidget(self.prog, 1)
        # Debajo del área, toda la receptividad: el texto de la fórmula (solo se ve; «Escribir a mano» lo deja editar), cómo
        # se escribe, cómo se dibuja, el estado y «Crear las que faltan»
        self.caja_formula = QWidget()
        g = QGridLayout(self.caja_formula)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(2)
        self.t_texto = QLineEdit()
        self.t_texto.setReadOnly(True)
        self.t_texto.setPlaceholderText("la fórmula se arma con bloques")
        self.t_texto.textEdited.connect(self._escrito)
        self.t_texto.editingFinished.connect(self._aplicar)
        self.t_manual = QCheckBox("Escribir a mano")
        self.t_manual.setToolTip("Dejar editar el texto de la fórmula (↑a AND NOT b, X1, 3s/X1…); lo escrito pasa a bloques")
        self.t_manual.toggled.connect(self._manual)
        self.t_vista = QLabel()
        self.t_vista.setWordWrap(True)
        self.t_vista.setTextFormat(Qt.TextFormat.RichText)
        self.t_dibujo = QLabel()
        self.t_dibujo.setTextFormat(Qt.TextFormat.RichText)
        self.t_dibujo.setWordWrap(True)
        self.t_estado = QLabel()
        self.t_estado.setWordWrap(True)
        self.t_crear = QPushButton("Crear las que faltan")
        self.t_crear.setToolTip("Declarar como entradas booleanas las variables que se usan y no existen")
        self.t_crear.clicked.connect(self._crear)
        g.addWidget(QLabel("Fórmula"), 0, 0)
        g.addWidget(self.t_texto, 0, 1)
        g.addWidget(self.t_manual, 0, 2)
        resumen = QHBoxLayout()
        resumen.setSpacing(8)
        resumen.addWidget(QLabel("Escrito"))
        resumen.addWidget(self.t_vista, 1)
        resumen.addWidget(QLabel("Se dibuja"))
        resumen.addWidget(self.t_dibujo, 1)
        g.addLayout(resumen, 1, 0, 1, 3)
        g.addWidget(self.t_estado, 2, 0, 1, 2)
        g.addWidget(self.t_crear, 2, 2)
        g.setColumnStretch(1, 1)
        lay.addWidget(self.caja_formula)
        self._ver_bloques(None)
        return w

    def _ver_bloques(self, titulo: str | None) -> None:
        """El programador de la transición o de la acción (condición o evento), o nada si no hay que programar."""
        self.pagina_bloques.setVisible(titulo is not None)
        self.l_bloques.setText(titulo or "")

    def objetivo_bloques(self) -> tuple | None:
        """Lo que programan los bloques ahora: ("transicion", ID) o ("accion", ID, «condicion» o «evento»)."""
        return self._objetivo

    def _guardado(self) -> str:
        """El texto guardado de lo que programan los bloques (receptividad, condición o evento), en la notación del usuario."""
        o = self._objetivo
        return self.e.texto_usuario(o[1]) if o[0] == "transicion" else self.e.texto_accion(o[1], o[2])

    TEXTO_VACIO = "Haga clic en un elemento del dibujo para ver y cambiar sus opciones."
    AYUDA_JERARQUIA = {
        "macro": "Macroetapa: doble clic en ella (o «Encuadrar la expansión») encaja su expansión en la vista y la resalta; suelte "
                 "etapas y transiciones dentro de su zona para rellenarla.",
        "expansion": "Expansión: sus etapas y transiciones son suyas; la entrada y la salida unen con la macroetapa. «Encuadrar "
                     "la macroetapa» la encaja en la vista.",
        "enclosure": "Recinto: suelte etapas dentro de su marco para rellenarlo; en una de ellas, «Enlace de activación» la marca. "
                     "Vacío, su borde se arrastra para moverlo.",
        "root": "Grafcet parcial: sus etapas y transiciones son suyas; lo que se suelta dentro de su marco, también. Vacío, su "
                "borde se arrastra para moverlo; «Renombrar…» (o doble clic) le cambia el nombre, y una orden de forzado "
                "puede forzarlo.",
        "marco": "Parcial: sus etapas y transiciones son suyas; lo que se suelta dentro de su marco, también.",
        "orden": "Orden de forzado: mientras su etapa está activa, impone su situación al parcial. Doble clic (o «Editar orden "
                 "de forzado…») la edita; Supr la quita (Ctrl+Z la devuelve).",
        "orden_suelta": "Orden de forzado sin completar: no se simula. Doble clic (o «Configurar orden de forzado…») abre el "
                        "diálogo para elegir el parcial al que fuerza, la forma y, si es explícita, sus etapas. Se une a una "
                        "etapa arrastrando desde su punto de unión de la izquierda hasta la etapa; unida y completa, impone su "
                        "situación al parcial mientras la etapa está activa. Supr la quita."}

    def _vacio(self) -> QWidget:
        self.l_vacio = QLabel(self.TEXTO_VACIO)
        self.l_vacio.setWordWrap(True)
        self.l_vacio.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.l_vacio.setStyleSheet(f"color: {COL['muted']}")
        return self.l_vacio

    def _etapa(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.s_etiqueta = QLineEdit()
        self.s_etiqueta.editingFinished.connect(lambda: self._renombrar(self.s_etiqueta))
        self.s_tipo = _desplegable()
        self.s_tipo.addItem("Normal", False)
        self.s_tipo.addItem("Inicial", True)
        self.s_tipo.activated.connect(lambda _: self.e.tipo_etapa(self.ident, self.s_tipo.currentData()))
        self.s_comentario = QLineEdit()
        self.s_comentario.setPlaceholderText("sin comentario")
        self.s_comentario.setToolTip("Comentario de la etapa: se dibuja entre comillas a su derecha (no entra en la simulación)")
        self.s_comentario.editingFinished.connect(lambda: self._comentar(self.s_comentario))
        self.s_colocacion = _desplegable()
        for valor, texto in COLOCACIONES:
            self.s_colocacion.addItem(texto, valor)
        self.s_colocacion.setToolTip("Cómo se colocan las acciones de la etapa en el dibujo")
        self.s_colocacion.activated.connect(lambda _: self.e.colocar_acciones(self.ident, self.s_colocacion.currentData()))
        f.addRow("Etiqueta", self.s_etiqueta)
        f.addRow("Tipo", self.s_tipo)
        f.addRow("Comentario", self.s_comentario)
        f.addRow("Colocación", self.s_colocacion)
        return w

    def _lista_acciones(self) -> QWidget:
        """Lo ancho de una etapa: su ficha de jerarquía (si tiene algo que decir) y, debajo, la lista de sus acciones y los
        botones para añadir, editar, quitar y mover."""
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)
        self.ficha_etapa = FichaJerarquia()
        vl.addWidget(self.ficha_etapa)
        cuerpo = QWidget()
        vl.addWidget(cuerpo, 1)
        hl = QHBoxLayout(cuerpo)
        hl.setContentsMargins(0, 0, 0, 0)
        izq = QVBoxLayout()
        izq.addWidget(QLabel("Acciones"))
        self.s_acciones = QListWidget()
        self.s_acciones.setWordWrap(True)
        self.s_acciones.itemDoubleClicked.connect(lambda it: self._editar(it.data(Qt.ItemDataRole.UserRole)))
        self.s_acciones.currentItemChanged.connect(self._accion_señalada)
        izq.addWidget(self.s_acciones, 1)
        hl.addLayout(izq, 1)
        col = QVBoxLayout()
        col.addSpacing(18)
        for texto, tip, accion in (("Añadir…", "Añadir una acción a la etapa (también con el botón derecho en la etapa)",
                                    self._anadir),
                                   ("Editar…", "Abrir las opciones de la acción elegida (o doble clic en ella)",
                                    lambda: self._editar(self._elegida())),
                                   ("Quitar", "Quitar la acción elegida", lambda: self._elegida() and self.e.quitar_accion(self._elegida())),
                                   ("◀", "Más a la izquierda en el dibujo", lambda: self._elegida() and self.e.mover_accion(self._elegida(), -1)),
                                   ("▶", "Más a la derecha", lambda: self._elegida() and self.e.mover_accion(self._elegida(), 1))):
            b = QPushButton(texto)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=accion: f())
            col.addWidget(b)
        col.addStretch(1)
        hl.addLayout(col)
        return w

    def _elegida(self) -> str | None:
        it = self.s_acciones.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _anadir(self) -> None:
        """«Añadir…»: una acción continua unida a la etapa, sin variable todavía; sus opciones se abren en el panel."""
        if self.e is not None and self.ident:
            self.e.anadir_accion(self.ident)

    def _editar(self, aid: str | None) -> None:
        if self.e is not None and self.ident and aid:
            self.e.pedir_accion(self.ident, aid)

    def _accion_señalada(self, it: Any, _: Any = None) -> None:
        """Elegir una acción en la lista la resalta en el dibujo."""
        aid = it.data(Qt.ItemDataRole.UserRole) if it else None
        if self.e is not None and aid != self.e.accion and not self._llenando:
            self.e.accion, self.e.ver_accion = aid, False
            self.e.cambiado.emit()

    def _transicion(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.t_etiqueta = QLineEdit()
        self.t_etiqueta.editingFinished.connect(lambda: self._renombrar(self.t_etiqueta))
        self.t_mostrar = QCheckBox("Mostrar etiqueta")
        self.t_mostrar.setToolTip("Dibujar la etiqueta (t1) junto a la transición")
        self.t_mostrar.clicked.connect(lambda on: self.e.mostrar_etiqueta(self.ident, on))
        self.t_comentario = QLineEdit()
        self.t_comentario.setPlaceholderText("sin comentario")
        self.t_comentario.setToolTip("Comentario de la transición: se dibuja entre comillas a la derecha de su receptividad "
                                     "(no entra en la simulación)")
        self.t_comentario.editingFinished.connect(lambda: self._comentar(self.t_comentario))
        f.addRow("Etiqueta", self.t_etiqueta)
        f.addRow(self.t_mostrar)
        f.addRow("Comentario", self.t_comentario)
        return w

    def _desde_bloques(self, texto: str) -> None:
        """Cada cambio en los bloques escribe el texto y se aplica (una operación de deshacer)."""
        self.t_texto.setText(texto)
        self._previsualizar()
        self._aplicar()

    def _escrito(self) -> None:
        self.prog.poner(self.t_texto.text())
        self._previsualizar()

    def _manual(self, on: bool) -> None:
        """«Escribir a mano»: marcada, el texto de la fórmula se puede editar; desmarcada, vuelve a ser de solo lectura."""
        self.t_texto.setReadOnly(not on)
        if on:
            self.t_texto.setFocus()
        elif self._objetivo is not None and self.e is not None:
            self._aplicar()

    def _enlace(self) -> QWidget:
        w = QWidget()
        f = QVBoxLayout(w)
        self.l_enlace = QLabel()
        self.l_enlace.setWordWrap(True)
        f.addWidget(self.l_enlace)
        self.f_tipo = QComboBox()
        self.f_tipo.setMaximumWidth(260)
        self.f_tipo.currentIndexChanged.connect(self._elegir_flecha)
        f.addWidget(self.f_tipo)
        self.f_visible = QCheckBox("Mostrar flecha")
        self.f_visible.clicked.connect(lambda on: self.e.ajustar_flecha(visible=on))
        f.addWidget(self.f_visible)
        fila = QHBoxLayout()
        self.f_auto = QPushButton("Flecha automática")
        self.f_auto.setToolTip("Restablecer la flecha: su sitio y si se ve, como los pone el programa")
        self.f_auto.clicked.connect(lambda: self.e.restablecer_flecha())
        fila.addWidget(self.f_auto)
        q = QPushButton("Quitar el enlace")
        q.clicked.connect(lambda: self.e.borrar())
        fila.addWidget(q)
        fila.addStretch(1)
        f.addLayout(fila)
        f.addStretch(1)
        return w

    def _elegir_flecha(self) -> None:
        if self.e is not None and self.f_tipo.currentData():
            self.e.flecha = self.f_tipo.currentData()
            self.mostrar(self.e)

    def _barra(self) -> QWidget:
        w = QWidget()
        f = QVBoxLayout(w)
        self.b_tipo = QLabel("Simultaneidad (doble trazo, Y)")
        self.b_tipo.setWordWrap(True)
        self.b_unidos = QLabel()
        self.b_unidos.setWordWrap(True)
        q = QPushButton("Quitar la barra")
        q.clicked.connect(lambda: self.e.borrar())
        ayuda = QLabel("Arrastre de un extremo para ensancharla; de un punto de unión sale un enlace.")
        ayuda.setWordWrap(True)
        f.addWidget(QLabel("<b>Tipo</b>"))
        f.addWidget(self.b_tipo)
        f.addWidget(QLabel("<b>Unidos</b>"))
        f.addWidget(self.b_unidos)
        f.addWidget(ayuda)
        fila = QHBoxLayout()
        fila.addWidget(q)
        fila.addStretch(1)
        f.addLayout(fila)
        f.addStretch(1)
        return w

    # -- estado ------------------------------------------------------------------------------------
    def mostrar(self, e: Any) -> None:
        """Rellena el panel con el elemento seleccionado (o lo vacía); respeta el campo que se está escribiendo."""
        self.e = e
        if e is not None:
            self.prog.refrescar()  # las variables pudieron cambiar (panel Variables, panel de la acción, «Crear las que faltan»)
        sel = e.sel if e is not None else []
        vivo = sel[0] if len(sel) == 1 else None
        aid = e.accion_activa() if e is not None else None
        kind = ("accion" if aid else
                "enlace" if "|" in vivo else
                "barra" if any(b["id"] == vivo for b in e.M.get("bars", [])) else
                "etapa" if any(s["id"] == vivo for s in e.M["steps"]) else
                "transicion" if any(t["id"] == vivo for t in e.M["transitions"]) else
                "macro" if any(x["id"] == vivo for x in e.M.get("macros", [])) else
                "orden" if any(f["id"] == vivo for f in e.ed.model["forces"]) or e.es_orden_suelta(vivo) else
                "marco" if any(q["id"] == vivo for q in e.M["partials"]) else None) if (vivo or aid) else None
        ident = aid if kind == "accion" else vivo if kind else None
        if (kind, ident) != (getattr(self, "_mostrado", None)):  # otro elemento: lo escrito sin confirmar se descarta
            for campo in (self.s_etiqueta, self.s_comentario, self.t_etiqueta, self.t_comentario):
                campo.blockSignals(True)
                campo.clearFocus()
                campo.blockSignals(False)
        self._mostrado = (kind, ident)
        self.ident = ident
        self.cuerpo.setVisible(kind is not None)
        self.vacio.setVisible(kind is None)
        self.pagina = kind or "vacio"  # qué opciones se muestran: etapa, transicion, accion, enlace, barra o vacio
        etapa_a = e.nombres.get(e.etapa_accion(aid), "") if kind == "accion" else ""
        titulo = {"etapa": f"Etapa {e.nombres.get(vivo)}", "transicion": f"Transición {e.nombres.get(vivo)}",
                  "enlace": f"Enlace {e.nombre(vivo)}" if vivo else "", "barra": e.nombre(vivo) if vivo else "",
                  "macro": f"Macroetapa {e.nombres.get(vivo)}",
                  "orden": "Orden de forzado" + (" sin completar" if e.es_orden_suelta(vivo) else ""),
                  "marco": e.nombre(vivo) if vivo else "",
                  "accion": f"Acción {(e.datos_accion(aid)['variable'] or '?') if aid else ''}" + (f" · etapa {etapa_a}" if etapa_a else " · suelta"),
                  None: "" if len(sel) < 2 else f"{len(sel)} elementos seleccionados"}[kind] if e is not None else ""
        self.titulo.setText(f"Propiedades · {titulo}" if titulo else "Propiedades")
        self.izq.setCurrentIndex({None: 0, "etapa": 1, "transicion": 2, "accion": 3, "enlace": 0, "barra": 0, "macro": 4,
                                  "orden": 4, "marco": 4}[kind])
        self.izq.setVisible(kind in ("etapa", "transicion", "accion", "macro", "orden", "marco"))
        self.ficha_izq.mostrar(e, vivo if kind in ("macro", "orden", "marco") else None)
        self.ficha_etapa.mostrar(e, vivo if kind == "etapa" else None)
        self.l_vacio.setText("Enlace de la etapa con sus acciones: Supr (o botón derecho, «Eliminar el enlace») las separa de la "
                             "etapa; quedan sueltas e independientes, cada una donde estaba."
                             if len(sel) == 1 and sel[0].startswith("enlaceacc:") else self.TEXTO_VACIO)
        self.vacio.setText(self.l_vacio.text())
        acc = e.accion_programable() if e is not None else None
        self._objetivo = (("transicion", vivo) if kind == "transicion" else ("accion", *acc) if acc and kind == "accion" else None)
        self._ver_bloques(None if self._objetivo is None else
                          f"Receptividad de la transición {e.nombres.get(vivo, vivo)}" if kind == "transicion" else
                          e.titulo_accion(acc[0], acc[1]))
        if kind == "accion":
            self.accion.mostrar(e, aid)
            memorizada = self.accion.clave_tipo not in CONTINUAS
            self.der.setCurrentIndex(2 if (memorizada or self._objetivo is not None) else 0)
            if not (memorizada or self._objetivo is not None):
                self.l_vacio.setText("Acción continua: vale 1 mientras la etapa está activa, y no lleva nada más. Cambie el tipo "
                                     "(botón derecho sobre la acción, «Tipo de acción») para añadirle una condición, o para que "
                                     "asigne un valor.")
        else:
            self.accion.caja_valor.setVisible(False)
        if self._objetivo is not None:
            if self._objetivo != self._anterior:  # otro objetivo: el texto vuelve a ser de solo lectura
                self.t_manual.blockSignals(True)
                self.t_manual.setChecked(False)
                self.t_manual.blockSignals(False)
                self.t_texto.setReadOnly(True)
                self.t_texto.blockSignals(True)  # sin «editingFinished»: aún tiene el texto del objetivo anterior
                self.t_texto.clearFocus()
                self.t_texto.blockSignals(False)
            guardado = self._guardado()
            self._poner(self.t_texto, guardado)
            self.prog.poner(guardado)
            self._previsualizar()
        self._anterior = self._objetivo
        if kind == "etapa":
            s = next(s for s in e.M["steps"] if s["id"] == vivo)
            self._poner(self.s_etiqueta, s["label"])
            self._poner(self.s_comentario, e.comentario(vivo))
            self.s_tipo.setCurrentIndex(1 if s["initial"] else 0)
            self.s_colocacion.setCurrentIndex(max(0, self.s_colocacion.findData(e.colocacion(vivo))))
            self.der.setCurrentIndex(1)
            self._llenando = True
            self.s_acciones.clear()
            for d in e.acciones(vivo):
                it = QListWidgetItem(e.resumen_accion(d))
                it.setData(Qt.ItemDataRole.UserRole, d["id"])
                self.s_acciones.addItem(it)
                if d["id"] == e.accion:
                    self.s_acciones.setCurrentItem(it)
            if not self.s_acciones.count():
                it = QListWidgetItem("Sin acciones: «Añadir…» o botón derecho en la etapa")
                it.setFlags(Qt.ItemFlag.NoItemFlags)
                self.s_acciones.addItem(it)
            self._llenando = False
        elif kind == "transicion":
            t = next(t for t in e.M["transitions"] if t["id"] == vivo)
            self._poner(self.t_etiqueta, t["label"])
            self._poner(self.t_comentario, e.comentario(vivo))
            self.t_mostrar.setChecked(t.get("showLabel", True))
            self.der.setCurrentIndex(2)
        elif kind == "barra":
            b = next(b for b in e.M["bars"] if b["id"] == vivo)
            self.b_unidos.setText(f"Por encima: {', '.join(e.nombre(i) for i in b['arriba']) or '—'}<br>"
                                  f"Por debajo: {', '.join(e.nombre(i) for i in b['abajo']) or '—'}")
            self.der.setCurrentIndex(4)
        elif kind == "enlace":
            tid, sid, rol = vivo.split("|")
            self.l_enlace.setText(f"{e.nombre(vivo)}<br>Arrastre la flecha a lo largo del enlace. "
                                  "Arrastre los cuadrados para recolocar los tramos. "
                                  "La flecha sigue el sentido del enlace; los ajustes de dibujo no cambian la "
                                  "simulación.")
            from .diagrama import enlaces
            ruta = next(r for r in enlaces(e.M) if r["id"] == vivo)
            kinds = ruta.get("arrowKinds", ["flow"])
            if e.flecha not in kinds:
                e.flecha = kinds[0]
            self.f_tipo.blockSignals(True)
            self.f_tipo.clear()
            for key in kinds:
                self.f_tipo.addItem("Flecha de recorrido" if key == "flow" else "Flecha de unión", key)
            self.f_tipo.setCurrentIndex(kinds.index(e.flecha))
            self.f_tipo.blockSignals(False)
            visible = any(a["key"] == e.flecha for a in ruta["arrows"])
            self.f_visible.setChecked(visible)
            self.der.setCurrentIndex(3)
        elif kind in ("macro", "orden", "marco"):
            clave = ("orden_suelta" if e.es_orden_suelta(vivo) else kind) if kind != "marco" \
                else e.ed.partial_roles().get(vivo, {}).get("kind")
            self.l_vacio.setText(self.AYUDA_JERARQUIA.get(clave, self.AYUDA_JERARQUIA["marco"]))
            self.der.setCurrentIndex(0)
        elif kind is None:
            self.der.setCurrentIndex(0)
        self.msg.setText("")
        self.msg.hide()

    @staticmethod
    def _poner(campo: QLineEdit, texto: str) -> None:
        if not campo.hasFocus() and campo.text() != texto:
            campo.setText(texto)

    def _insertar(self, texto: str) -> None:
        if self.ident is None:
            return
        self.t_texto.setFocus()
        self.t_texto.insert(f" {texto.strip()} ")  # siempre un espacio delante y otro detrás; los sobrantes se quitan al guardar
        self.prog.poner(self.t_texto.text())
        self._previsualizar()

    def _prefijar(self, prefijo: str) -> None:
        """NOT, ↑ o ↓ delante del texto seleccionado: si no es un solo nombre, entre paréntesis; sin selección, solo el
        prefijo."""
        sel = self.t_texto.selectedText().strip()
        if sel:
            self._insertar(prefijo + (sel if re.fullmatch(r"[\w.]+", sel) else f"({sel})"))
        else:
            self._insertar(prefijo)

    def _comentar(self, campo: QLineEdit) -> None:
        """El comentario de la etapa o transición mostrada: una operación de deshacer al confirmar."""
        if self.ident is None or self.e is None or self.e.sel != [self.ident] or self.ident not in self.e.nombres:
            return  # (el editingFinished puede llegar tarde: el elemento ya no es el mostrado, o ya no existe)
        self.e.poner_comentario(self.ident, campo.text())

    def _renombrar(self, campo: QLineEdit) -> None:
        if self.ident is None or self.e.sel != [self.ident] or self.ident not in self.e.nombres \
                or campo.text().strip() == self.e.nombres.get(self.ident):
            return  # (el editingFinished puede llegar tarde: el elemento ya no es el mostrado, o ya no existe)
        motivo = self.e.renombrar(self.ident, campo.text().strip())
        if motivo:
            self.msg.setText(motivo)
            self.msg.show()
            self.msg.setStyleSheet(f"color: {COL['err']}")
            campo.setText(self.e.nombres.get(self.ident, ""))

    # -- receptividad ------------------------------------------------------------------------------
    def _previsualizar(self) -> None:
        e, o, texto = self.e, self._objetivo, self.t_texto.text().strip()
        if e is None or o is None:
            return
        ident = o[1]
        tr = o[0] == "transicion"
        cosa = "Receptividad" if tr else "Condición" if o[2] == "condicion" else "Evento"
        faltan = e.sin_declarar(ident, texto) if texto else []
        pintado = html.escape(texto)
        for n in faltan:  # las variables que no existen, en naranja
            pintado = re.sub(rf"(?<![\w.]){re.escape(html.escape(n))}(?![\w.])",
                             f'<span style="color:{NARANJA};font-weight:600">{html.escape(n)}</span>', pintado)
        self.t_vista.setText(pintado or "<i>vacía</i>")
        self.t_crear.setVisible(bool(faltan))
        self.t_dibujo.setText("")
        if not texto:
            self.t_estado.setText("Vacía: la transición no compila." if tr else
                                  f"Vacía: sin {'condición' if o[2] == 'condicion' else 'evento'}, la acción no se simula.")
            self.t_estado.setStyleSheet(f"color: {COL['err'] if tr else COL['muted']}")
        elif faltan:
            self.t_estado.setText(f"No existen: {', '.join(faltan)}.")
            self.t_estado.setStyleSheet(f"color: {NARANJA}")
        else:
            d = e.comprobar(ident, texto)
            if d is None:
                aviso = e.aviso_ambiguas(texto)
                self.t_estado.setText(f"{cosa} {'correcta' if cosa != 'Evento' else 'correcto'}." + (f" {aviso}" if aviso else ""))
                self.t_estado.setStyleSheet(f"color: {NARANJA if aviso else COL['ok']}")
                self.t_dibujo.setText(_html(norm(e.significado(ident, texto), True, e.nombres)))
            else:
                self.t_estado.setText(f"Error de sintaxis: {e.sust(d.message)}. {e.sust(d.correction)}")
                self.t_estado.setStyleSheet(f"color: {COL['err']}")

    def _aplicar(self) -> None:
        o = self._objetivo
        if o is None or self.t_texto.text().strip() == self._guardado():
            return  # (al cambiar la selección, el campo oculto pierde el foco con el texto del objetivo anterior)
        if o[0] == "transicion":
            self.e.poner_condicion(o[1], self.t_texto.text().strip(), crear=False)
        else:
            self.e.poner_texto_accion(o[1], o[2], self.t_texto.text().strip())

    def _crear(self) -> None:
        o = self._objetivo
        if o is None:
            return
        texto = self.t_texto.text().strip()
        if o[0] == "transicion":
            resultado = self.e.poner_condicion(o[1], texto, crear=True)
            motivo = resultado.message if getattr(resultado, "code", "") == "D-FORMATO" else None
        else:
            motivo = self.e.poner_texto_accion(o[1], o[2], texto, crear=True)
        if motivo:  # un nombre que no se puede escribir en una fórmula: mensaje y parpadeo
            self.t_estado.setText(motivo)
            self.t_estado.setStyleSheet(f"color: {COL['err']}")
            self.parpadeo_crear.iniciar({"crear"})

    def _pintar_crear(self) -> None:
        self.t_crear.setStyleSheet(f"background: {NARANJA}" if self.parpadeo_crear.activos() else "")
