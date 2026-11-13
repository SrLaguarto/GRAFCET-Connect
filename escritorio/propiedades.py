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
  programador del valor de una memorizada y, si es condicionada o por evento, el de su condición o su evento. Una acción continua no
  lleva campos aquí: solo la frase que manda a hacer doble clic sobre ella (`FRASE_CONTINUA`; la variable se elige en el desplegable
  sobre la acción). El mismo panel (`flotante=True`, sin cabecera) sirve a las ventanas de Ver ▸ Panel de opciones ▸ Flotante
  (`flotantes.py`), donde el programador de la condición o del evento va en su propia ventana (`_llevar_bloques`).
- Macroetapa, recinto (su marco), expansión, grafcet parcial suelto y orden de forzado (también la que aún no está completa): una
  ficha compacta (`FichaJerarquia`) con su descripción y los mismos botones que el botón derecho (Encuadrar la expansión,
  Renombrar…, Encuadrar la encapsulante, Configurar, Editar o Quitar la orden…; el doble clic en una orden la edita); una
  etapa lleva la suya sobre su lista de acciones (su tipo: Etapa, Encapsulante o Macroetapa; de un recinto, entrada o
  salida de una expansión, Forzar un
  parcial…).
- Enlace, barra de simultaneidad, varios elementos o nada: lo suyo, o la invitación a elegir un elemento.
Cada cambio se aplica al momento con las operaciones de Edicion / grafcet/editor.py (una operación de deshacer).
"""
from __future__ import annotations

import html
import re
from typing import Any, Callable

from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
                               QStackedWidget, QStyledItemDelegate, QStyle, QToolButton, QVBoxLayout, QWidget)

from grafcet.routing import TALLO_T
from grafcet.expressions import is_event_positive
from grafcet.view import norm

from . import estilo
from .paneles import EtiquetaGrupos, TituloSeccion
from .acciones import CajaFormula, PanelAccion
from .bloques import FlowLayout, Programador
from .remates_propiedades import AvisoFormula, RematesAccion
from .paneles import PilaActual, PilaActualSolo
from .diagrama import ACT_MIN, COL, H, MARK, TB, VACIO_H, VACIO_W, _html
from .edicion import COLOCACIONES, CONTINUAS, Parpadeo

NARANJA = COL["glow"]
from .edicion import MAX_ETIQUETA_ETAPA  # noqa: E402
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
                          "derecho, «Tipo de etapa». Botón derecho en la encapsulante, «Añadir recinto…», crea un "
                          "recinto; se rellena soltando "
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
    ("Transiciones", ("transicion", "simultaneidad")),
    ("Acciones", tuple("accion:" + t for t in ("continua", "condicionada", "activacion", "desactivacion", "evento"))),
    ("Jerarquías", ("encapsulante", "macroetapa", "forzado", "parcial")),
    ("Otros", ("texto", "imagen")),
)
NOMBRES.update({"etapa_inicial": "Etapa inicial", "accion:continua": "Continua",
                "accion:condicionada": "Condicionada", "accion:activacion": "Al activar",
                "accion:desactivacion": "Al desactivar", "accion:evento": "Por evento"})
AYUDAS["etapa_inicial"] = "Etapa inicial: arrástrela al dibujo. Se crea con el doble cuadrado de etapa inicial."
for t in ("continua", "condicionada", "activacion", "desactivacion", "evento"):
    AYUDAS["accion:" + t] = ("Acción " + NOMBRES["accion:" + t].lower() + ": arrástrela al dibujo; "
                            "únala a una etapa desde su punto de unión y configúrela con doble clic o en Propiedades.")
NOMBRES.update({"texto":"Texto", "imagen":"Imagen"})
AYUDAS.update({"texto":"Cuadro de texto: arrástrelo al dibujo. Doble clic para elegir texto, fuente, tamaño y color. Estire su esquina para cambiar el cuadro.",
               "imagen":"Imagen PNG o JPG: arrástrela al dibujo y elija un archivo. Estire su esquina para cambiar el tamaño conservando sus proporciones."})
COLOCABLES = tuple(h for _, claves in SECCIONES for h in claves)


def _medidas_ficha(h: str) -> tuple[QRectF, QPointF]:
    """Lienzo lógico y punto de colocación; las cajas comparten altura y escala de referencia."""
    if h in ("texto","imagen"):
        return QRectF(-6,-6,108,72), QPointF(0,0)
    if h == "parcial":
        return QRectF(-4, -10, VACIO_W + 8, VACIO_H + 20), QPointF(VACIO_W / 2, VACIO_H / 2)
    if h.startswith("simultaneidad"):
        return QRectF(-64, -44, 128, 88), QPointF(0, 0)
    if h.startswith("accion") or h == "forzado":
        return QRectF(-8, -44, ACT_MIN + 16, 88), QPointF(0, 0)
    return QRectF(-48, -44, 96, 88), QPointF(0, 0)


def _pintar_ficha(p: QPainter, h: str) -> None:
    """Único dibujo de la ficha, compartido por la lista y la imagen de arrastre."""
    p.setPen(QPen(QColor(COL["text"]), 1.6))
    p.setBrush(QColor(COL["panel"]))
    if h in ("texto","imagen"):
        caja=QRectF(0,0,96,60);p.drawRoundedRect(caja,4,4)
        if h == "texto":
            fuente=QFont("Arial");fuente.setPixelSize(26);p.setFont(fuente)
            p.drawText(caja,Qt.AlignmentFlag.AlignCenter,"Texto")
        else:
            p.drawEllipse(QRectF(66,10,12,12))
            for a,b in ((QPointF(8,50),QPointF(33,22)),(QPointF(33,22),QPointF(53,44)),
                        (QPointF(53,44),QPointF(67,30)),(QPointF(67,30),QPointF(88,50))):p.drawLine(a,b)
    elif h == "parcial":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0, 0, VACIO_W, VACIO_H), 16, 16)
        fuente = QFont("Arial")
        fuente.setPixelSize(18)
        fuente.setBold(False)
        p.setFont(fuente)
        rotulo = QRectF(VACIO_W - 48, VACIO_H - 10, 24, 20)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(rotulo, Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawText(rotulo, Qt.AlignmentFlag.AlignCenter, "G")
    elif h.startswith("accion"):
        from .diagrama import _escena_ficha
        tipo = h.partition(":")[2] or "continua"
        limites, _ = _medidas_ficha(h)
        _escena_ficha(tipo).render(p, limites, limites)
    elif h == "forzado":
        caja = QRectF(0, -H, ACT_MIN, 2 * H)
        p.drawRect(caja)
        p.drawRect(caja.adjusted(4, 4, -4, -4))
        fuente = QFont("Arial")
        fuente.setPixelSize(15)
        p.setFont(fuente)
        p.drawText(caja, Qt.AlignmentFlag.AlignCenter, "G{ }")
    elif h.startswith("simultaneidad"):
        p.drawLine(QPointF(-60, 0), QPointF(60, 0))
        p.drawLine(QPointF(-60, 8), QPointF(60, 8))
    elif h == "transicion":
        p.drawLine(QPointF(0, -TALLO_T - 2), QPointF(0, TALLO_T + 2))
        p.setPen(QPen(QColor(COL["text"]), 2.4))
        p.drawLine(QPointF(-TB, 0), QPointF(TB, 0))
    else:
        p.drawRect(QRectF(-H, -H, 2 * H, 2 * H))
        if h == "etapa_inicial":
            p.drawRect(QRectF(-H + 4, -H + 4, 2 * H - 8, 2 * H - 8))
        elif h == "macroetapa":
            for y in (-H + MARK, H - MARK):
                p.drawLine(QPointF(-H, y), QPointF(H, y))
        elif h == "encapsulante":
            c = round(.22 * 2 * H)
            for (x0, y0), (x1, y1) in (((-H + c, -H), (-H, -H + c)), ((H - c, -H), (H, -H + c)),
                                       ((-H, H - c), (-H + c, H)), ((H, H - c), (H - c, H))):
                p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


def figura(h: str, escala: float = 1.0, dpr: float = 1.0) -> tuple[QPixmap, QPoint]:
    """La misma ficha de la paleta a la escala del dibujo, con su punto de colocación bajo el puntero."""
    limites, ancla = _medidas_ficha(h)
    pm = QPixmap(max(1, round(limites.width() * escala * dpr)), max(1, round(limites.height() * escala * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    p.scale(escala, escala)
    p.translate(-limites.left(), -limites.top())
    _pintar_ficha(p, h)
    p.end()
    return pm, QPoint(round((ancla.x() - limites.left()) * escala), round((ancla.y() - limites.top()) * escala))


def icono(h: str) -> QIcon:
    pm, _ = figura(h, 1.0, 2.0)
    pm = pm.scaled(192, 192, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    lienzo = QPixmap(192, 192)
    lienzo.setDevicePixelRatio(2)
    lienzo.fill(Qt.GlobalColor.transparent)
    p = QPainter(lienzo)
    p.drawPixmap(QPointF((96 - pm.width() / 2) / 2, (96 - pm.height() / 2) / 2), pm)
    p.end()
    return QIcon(lienzo)


class _DelegadoPaleta(QStyledItemDelegate):
    """Filas limpias y cabeceras de sección; el icono conserva el símbolo existente."""
    def paint(self, p: QPainter, opcion: Any, indice: Any) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = opcion.rect.adjusted(5, 1, -5, -1)
        clave = indice.data(Qt.ItemDataRole.UserRole)
        fuente = QFont(opcion.font)
        if not clave:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(estilo.SUPERFICIE_2))
            p.drawRoundedRect(QRectF(r), estilo.R_S, estilo.R_S)
            p.setBrush(QColor(estilo.ACENTO))  # el filete de acento a la izquierda de cada sección
            p.drawRoundedRect(QRectF(r.left(), r.top() + 4, 3, r.height() - 8), 1.5, 1.5)
            fuente.setBold(True)
            p.setFont(fuente)
            p.setPen(QColor(estilo.ACENTO))
            p.drawText(r.adjusted(12, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, indice.data())
        else:
            if opcion.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(estilo.ACENTO_SUAVE if opcion.state & QStyle.StateFlag.State_Selected else estilo.HOVER))
                p.drawRoundedRect(QRectF(r), estilo.R_S, estilo.R_S)
            icono = indice.data(Qt.ItemDataRole.DecorationRole)
            icono.paint(p, r.center().x() - 36, r.top() + 3, 72, 64)
            fuente.setPixelSize(estilo.T_PEQUENA)
            p.setFont(fuente)
            p.setPen(QColor(estilo.TINTA))
            p.drawText(QRectF(r.left() + 2, r.top() + 69, r.width() - 4, 27),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, indice.data())
        p.restore()


class Paleta(QListWidget):
    """La lista de fichas del grafcet (etapa, transición, simultaneidad, acción, macroetapa, encapsulante, grafcet parcial y
    forzado). Las fichas solo se colocan arrastrándolas al dibujo; un clic en una ficha no hace nada salvo mostrar su ayuda
    (señal `ayuda`)."""

    ayuda = Signal(str)
    REJILLA = QSize(100, 98)  # dos fichas por fila; icono y nombre debajo
    ICONO = QSize(72, 64)
    FILAS = 3  # filas visibles solicitadas; el resto queda accesible con desplazamiento
    FILAS_MIN = 1  # hasta dónde se encoge en una ventana baja (con desplazamiento vertical): fija el mínimo de alto de la ventana
    CLAVES: tuple[str, ...] = COLOCABLES

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setSpacing(0)
        self.setUniformItemSizes(False)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setIconSize(self.ICONO)
        self.setMovement(QListView.Movement.Static)  # Static desactiva el arrastre: se activa después
        self.setResizeMode(QListView.ResizeMode.Fixed)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.setObjectName("paletaElementos")
        self.setItemDelegate(_DelegadoPaleta(self))
        self.setMouseTracking(True)
        for titulo, claves in SECCIONES:
            cabecera = QListWidgetItem(titulo)
            cabecera.setFlags(Qt.ItemFlag.NoItemFlags)
            cabecera.setSizeHint(QSize(188, 28))
            cabecera.setBackground(QColor(estilo.SUPERFICIE_2))
            cabecera.setForeground(QColor(estilo.ACENTO))
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
        self._ancho_celdas = None
        self._actualizar_celdas()
        self.setCurrentRow(-1)
        self.itemClicked.connect(lambda it: self.ayuda.emit(self.texto_ayuda(it.data(Qt.ItemDataRole.UserRole)) if it.data(Qt.ItemDataRole.UserRole) else ""))
        # Altura flexible; el desplazamiento conserva todas las secciones accesibles.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _actualizar_celdas(self) -> None:
        ancho = max(2, self.width() - 2 * self.frameWidth() - self.verticalScrollBar().sizeHint().width())
        if ancho == getattr(self, "_ancho_celdas", None):
            return
        self._ancho_celdas = ancho
        self.setUpdatesEnabled(False)
        try:
            for i in range(self.count()):
                it = self.item(i)
                tam = QSize(ancho // 2, self.REJILLA.height()) if it.data(Qt.ItemDataRole.UserRole) else QSize(ancho, 26)
                if it.sizeHint() != tam:
                    it.setSizeHint(tam)
            self.doItemsLayout()
        finally:
            self.setUpdatesEnabled(True)  # (siempre a cierto: si se guardara lo de antes y la ventana lo tenía en falso, la paleta se quedaba sin pintar)

    def resizeEvent(self, evento: Any) -> None:  # noqa: N802
        super().resizeEvent(evento)
        self._actualizar_celdas()

    @staticmethod
    def nombre(h: str) -> str:
        return NOMBRES[h]

    @staticmethod
    def texto_ayuda(h: str) -> str:
        return AYUDAS[h]

    def ancho_minimo(self) -> int:
        """Ancho para icono, nombre y barra vertical, sin desplazamiento horizontal."""
        return 216  # (+ 1 px de borde de la tarjeta a cada lado = 218, el ancho del panel)

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
        self.arrastrar_elemento(it.data(Qt.ItemDataRole.UserRole))

    def arrastrar_elemento(self, clave: str, origen: QWidget | None = None) -> None:
        """La ficha y sus favoritos comparten MIME, escala, vista previa y punto de colocación."""
        items = [self.item(i) for i in range(self.count())
                 if self.item(i).data(Qt.ItemDataRole.UserRole) == clave]
        if not items:
            return
        drag = QDrag(origen if origen is not None else self)
        drag.setMimeData(self.mimeData(items))
        pm, punto = figura(clave, self.escala(), self.devicePixelRatioF())
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
    ORDEN = ("Etapa", "Encapsulante", "Macroetapa", "Encuadrar la expansión", "Renombrar…", "Añadir recinto…",
             "Encuadrar el recinto", "Encuadrar los recintos", "Enlace de activación", "Encuadrar la encapsulante",
             "Encuadrar la macroetapa", "Forzar un parcial…", "Configurar orden de forzado…", "Editar orden de forzado…",
             "Quitar orden de forzado")  # el mismo orden que el botón derecho
    CASILLAS = ("Etapa", "Encapsulante", "Macroetapa", "Enlace de activación")  # los tres primeros: «Tipo de etapa»
    alto_cambiado = Signal()  # la caja de botones pide otro alto (más o menos filas al ancho de ahora): el panel de Propiedades se redimensiona

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        # Botones de acciones avanzadas (los mismos del botón derecho): más bajos que los de panel, para que varias filas quepan
        # en una columna estrecha sin que el panel crezca (el menú contextual sigue ahí para quien necesite un objetivo mayor)
        self.setStyleSheet(self._hoja())
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

    def resizeEvent(self, evento: QEvent) -> None:  # noqa: N802
        """La caja de botones pide el alto de sus filas al ancho que tiene de verdad (el panel no propaga la altura según el ancho: con los botones
        en más filas de las que le tocaban, el último quedaba cortado)."""
        super().resizeEvent(evento)
        ancho = self.caja.width()
        if ancho > 0 and not self.caja.isHidden():
            alto = self.flujo.heightForWidth(ancho)
            if self.caja.minimumHeight() != alto:
                self.caja.setMinimumHeight(alto)
                self.setMinimumHeight((self.texto.heightForWidth(self.width()) + self.layout().spacing() if not self.texto.isHidden() else 0) + alto)  # (la ficha lo pide entero al panel)
                self.layout().invalidate()
                self.updateGeometry()
                self.alto_cambiado.emit()

    @staticmethod
    def _hoja() -> str:
        return (f"QPushButton {{ min-height: 20px; padding: 0 8px; font-size: {estilo.T_PEQUENA}px; }} "
                f"QCheckBox {{ min-height: 22px; font-size: {estilo.T_PEQUENA}px; }} "
                f"QPushButton[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; min-height: 18px; padding: 0 7px; }}")

    def escalar(self) -> None:
        self.setStyleSheet(self._hoja())

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


class _UbicaCategorias(QObject):
    """Cuando cambia el ancho de la cabecera del panel, vuelve a decidir si las categorías de bloques caben en ella."""

    def __init__(self, panel: "PanelPropiedades") -> None:
        super().__init__(panel)
        self.panel = panel

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:  # noqa: N802
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Move):
            self.panel._ubicar_categorias()
        return False


class PanelPropiedades(QWidget):
    """Las opciones del elemento seleccionado, con campos editables (el panel «Opciones» de abajo)."""
    ANCHO_MINIMO = 560  # lo más ancho que pide el panel a la ventana: con él abierto, la ventana baja a 640 px y vuelve
    alto_cambiado = Signal()  # el panel pide más o menos alto (el estado de la fórmula baja a su línea o vuelve a su lado)

    def escalar(self, hoja_ventana: str = "") -> None:
        """Cambió la escala de letra y de controles (pantalla completa o no): la hoja (la de la ventana para esa escala, si hay, y la de los
        campos compactos), «Fijar», categorías y fichas se miden otra vez. La ventana lo llama al abrir el panel."""
        self.setStyleSheet(hoja_ventana + estilo.campos_compactos())
        self.cabecera.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO + 4)
        self.t_fijar.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO)
        for prog in (self.prog, getattr(self.accion, "prog", None)):
            if prog is not None:
                prog.escalar()
        for ficha in (self.ficha_izq, self.ficha_etapa):
            ficha.escalar()
        self._ubicar_categorias()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """El ancho mínimo no pasa de `ANCHO_MINIMO`: al abrirse (y mientras sus páginas aún no se han repartido) el panel llegó a
        pedir 773 px y sacaba la ventana de su media pantalla sin que volviera. El alto sí es el de su contenido."""
        tam = super().minimumSizeHint()
        return QSize(min(tam.width(), self.ANCHO_MINIMO), tam.height())

    def sizeHint(self) -> QSize:  # noqa: N802
        tam = super().sizeHint()
        if self.pagina == "accion":
            # Aire preferido sobre la altura estricta de los campos, sin elevar el mínimo ni forzar desplazamiento.
            tam.setHeight(tam.height() + estilo.E2)
        return tam

    FRASE_CONTINUA = "Haz doble clic sobre la acción continua para desplegar las variables disponibles."

    def __init__(self, flotante: bool = False) -> None:
        super().__init__()
        self.flotante = flotante  # en una ventana flotante (`flotantes.py`): sin cabecera propia, y la condición o el evento de una acción pueden ir en otra ventana
        self.continua = False  # lo que se muestra es una acción continua: solo la frase (se elige la variable con doble clic sobre ella)
        self._bloques_fuera = False  # el programador de la condición o el evento está en la otra ventana (`destino_bloques`)
        self.destino_bloques: QVBoxLayout | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Campos de 32 px en el panel (el mínimo táctil): con 36 px la página de una etapa pediría más alto que la de una transición
        self.setStyleSheet(estilo.campos_compactos())
        self.e: Any = None
        self.ident: str | None = None
        self._llenando = False
        self._anterior: tuple | None = None  # lo que programaron los bloques la última vez (para volver al texto de solo lectura)
        self._objetivo: tuple | None = None  # lo que programan los bloques: ("transicion", ID) o ("accion", ID, campo)
        self.pagina = "vacio"
        self.parpadeo_crear = Parpadeo(self)  # «Crear las que faltan» parpadea si un nombre no vale
        self.parpadeo_crear.cambia.connect(self._pintar_crear)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 1, 10, 4)  # (1 px arriba: dentro del borde de la tarjeta, que la cabecera no tapa)  la cabecera (32 px) pega con el borde: el primer campo queda a 32 px del panel
        lay.setSpacing(0)
        # Una sola fila de cabecera (P-IMP-118): el título, lo que programan los bloques (si no repite el título) y «Fijar»;
        # a la derecha queda libre el sitio del botón de plegar
        self.cabecera = QWidget()
        self.cabecera.setObjectName("cabeceraPropiedades")
        self.fila_cabecera = QHBoxLayout(self.cabecera)
        self.fila_cabecera.setContentsMargins(estilo.E2, 2, 40, 2)  # a la derecha, el sitio del botón de plegar (32 px); 2 px arriba y abajo: ni las categorías ni «Fijar» tocan el borde de la franja
        self.cabecera.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO + 4)
        self.fila_cabecera.setSpacing(estilo.E3)
        self.titulo = TituloSeccion(x_marcador=4)
        self.titulo.setObjectName("tituloPropiedades")
        self.fila_cabecera.addWidget(self.titulo)
        lay.addWidget(self.cabecera)
        self.cabecera.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)  # (la cabecera, siempre arriba y del mismo alto)
        self.vacio = QLabel(self.TEXTO_VACIO)
        self.vacio.setObjectName("ayudaPropiedades")
        self.vacio.setWordWrap(True)
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)  # (el mensaje, justo bajo la cabecera)
        self.vacio.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.vacio)
        self.cuerpo = QWidget()
        cuerpo = QHBoxLayout(self.cuerpo)
        cuerpo.setContentsMargins(0, 2, 0, 0)  # el primer campo empieza por debajo de la franja del título
        cuerpo.setSpacing(14)
        lay.addWidget(self.cuerpo, 1)
        # Izquierda, la columna estrecha de campos; derecha, lo ancho (lista de acciones, programadores, enlace, barra)
        self.izq = PilaActualSolo() if flotante else PilaActual()  # (flotante: el alto de la página que se ve, no el de la mayor)
        self.izq.setFixedWidth(ANCHO_COLUMNA)
        self.izq.addWidget(QWidget())  # 0: nada que mostrar en la columna
        self.izq.addWidget(self._etapa())  # 1
        self.izq.addWidget(self._transicion())  # 2
        self.accion = PanelAccion()  # 3
        self.izq.addWidget(self.accion)
        self._remates_accion = RematesAccion(self, lay, ANCHO_COLUMNA)
        self.ficha_izq = FichaJerarquia()  # 4: macroetapa, recinto, expansión u orden de forzado
        pagina = QWidget()
        lh = QVBoxLayout(pagina)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.addWidget(self.ficha_izq)
        lh.addStretch(1)
        self.izq.addWidget(pagina)
        cuerpo.addWidget(self.izq)
        self.der = PilaActualSolo() if flotante else PilaActual()
        self.der.addWidget(self._vacio())  # 0
        self.der.addWidget(self._lista_acciones())  # 1
        self.der.addWidget(self._programacion())  # 2
        self.der.addWidget(self._enlace())  # 3
        self.der.addWidget(self._barra())  # 4
        nota=QWidget();nl=QVBoxLayout(nota);nl.setContentsMargins(0,0,0,0)
        self.nota_resumen=QLabel();self.nota_resumen.setTextFormat(Qt.TextFormat.PlainText);self.nota_resumen.setWordWrap(True);self.nota_resumen.setMaximumHeight(60)
        self.nota_editar=QPushButton("Editar texto…")
        self.nota_editar.clicked.connect(lambda: self.e.editar_anotacion(self.ident) if self.e is not None else None)
        nl.addWidget(self.nota_resumen);nl.addWidget(self.nota_editar,0,Qt.AlignmentFlag.AlignLeft);nl.addStretch(1)
        self.der.addWidget(nota)  # 5: texto o imagen
        cuerpo.addWidget(self.der, 1)
        cuerpo.addStretch(0)
        # «Fijar» (en el sitio de la antigua «Vista previa», en todas las páginas): sin fijar, el panel se esconde solo al
        # hacer clic en el dibujo fuera del elemento que muestra (lo decide la ventana)
        self.t_fijar = QToolButton()
        self.t_fijar.setText("Fijar")
        self.t_fijar.setCheckable(True)
        self.t_fijar.setAutoRaise(True)
        self.t_fijar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.t_fijar.setToolTip("Mantiene abierto este panel. Sin fijar, se esconde al hacer clic fuera del elemento.")
        self.t_fijar.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO)
        self.t_fijar.setStyleSheet(f"QToolButton{{padding:0 12px;border:1px solid {estilo.BORDE_CONTROL};"
                                   f"border-radius:{estilo.R_S}px;background:{estilo.SUPERFICIE};}}"
                                   f"QToolButton:hover{{background:{estilo.HOVER};border-color:{estilo.TINTA_2};}}"
                                   f"QToolButton[tecl=\"true\"]:focus{{border:2px dashed {estilo.FOCO};padding:0 11px;}}"
                                   f"QToolButton:checked{{background:{estilo.ACENTO};color:white;border-color:{estilo.ACENTO_OSCURO};font-weight:600;}}"
                                   f"QToolButton:checked[tecl=\"true\"]:focus{{border:2px dashed white;}}")
        self.fila_cabecera.addWidget(self.t_fijar)
        self._ubica_categorias = _UbicaCategorias(self)  # (las categorías de bloques, en la fila de la cabecera si caben)
        for objeto in (self.cabecera, self.cuerpo, self.pagina_bloques, self.accion.caja_valor, self.accion.caja_numerica):
            objeto.installEventFilter(self._ubica_categorias)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        if flotante:
            self.cabecera.hide()  # (el título, «Fijar» y cerrar los pone la ventana flotante)
            # La lupa ya enseña la fórmula dibujada: sin la fila «Fórmula», sin el aviso de «correcta» ni la frase de la acción. La papelera
            # sube a la fila de categorías (no roba alto); un error de la fórmula sí sale, en una línea roja bajo el área de bloques.
            self._l_formula.hide()
            self.t_texto.hide()
            self.t_estado.hide()
            self.accion.frase.hide()
            self.prog.papelera_arriba()

    def zona_de(self, w: QWidget | None) -> str | None:
        """En qué zona de la página de una acción está el widget `w` (el que tiene el foco): «bloques» (la condición o el evento) o «accion» (lo
        demás: variable, valor…); None si no está en ninguna."""
        if w is None:
            return None
        if self.pagina_bloques.isAncestorOf(w):
            return "bloques"
        if self.izq.isAncestorOf(w) or self.accion.caja_valor.isAncestorOf(w):
            return "accion"
        return None

    def _llevar_bloques(self, fuera: bool) -> None:
        """En una ventana flotante, el programador de la condición o del evento de una acción va en su propia ventana (`destino_bloques`); en los
        demás casos vuelve a su sitio, a la derecha de la página."""
        fuera = fuera and self.destino_bloques is not None
        if fuera == self._bloques_fuera:
            return
        self._bloques_fuera = fuera
        if fuera:
            self.destino_bloques.addWidget(self.pagina_bloques)
        else:
            self._hl_prog.insertWidget(1, self.pagina_bloques, 3)

    # -- categorías de bloques en la cabecera -------------------------------------------------------
    def _programador_en_cabecera(self) -> Programador | None:
        """El programador cuyas categorías suben a la fila de la cabecera: el de la receptividad (transición), el de la condición o el evento de
        una acción y, si una acción solo tiene el del valor, ese."""
        if self.pagina == "transicion":
            return self.prog
        if self.pagina == "accion":
            if self.pagina_bloques.isVisibleTo(self):
                return self.prog
            if self.accion.caja_valor.isVisibleTo(self) and self.accion.caja_numerica.isVisibleTo(self):
                return self.accion.prog
        return None

    def _ubicar_categorias(self) -> None:
        """Las categorías del programador por bloques (el de una transición, o el que se vea en una acción) van en la fila de la cabecera, entre el
        título (que ocupa la columna de campos, o hasta donde empieza la paleta) y «Fijar»: empiezan donde empiezan la paleta y el área, y el panel
        gana una fila de alto. Si no caben en esa fila, o en otra página, vuelven a su fila propia sobre la paleta (donde, en un panel estrecho,
        pasan a dos filas). Siempre en una sola línea, sin cortarse. En las páginas con columna de campos el título mide lo que esa columna."""
        if self.flotante:  # (sin cabecera: las categorías van en su fila, sobre la paleta)
            for prog in (self.prog, self.accion.prog):
                prog.categorias_en_cabecera(None)
            return
        e3, e2 = estilo.E3, estilo.E2
        elegido = self._programador_en_cabecera()
        columna = ANCHO_COLUMNA + 14 - e2 - e3  # la columna de campos más el hueco hasta la paleta, menos lo que ya pone la fila
        ancho_titulo = columna
        if elegido is self.accion.prog or (elegido is self.prog and self.pagina == "accion"):
            # el título llega hasta donde empieza el área de ese programador (en una acción, tras la columna de campos y, si lo hay, el valor)
            contenedor = self.accion.caja_valor if elegido is self.accion.prog else self.pagina_bloques
            x = contenedor.mapTo(self, QPoint(0, 0)).x() - self.cabecera.x()  # (a coordenadas de la cabecera, que no es antecesora del contenedor)
            if contenedor.isVisibleTo(self) and e2 + e3 + 60 < x < self.cabecera.width():
                ancho_titulo = x - e2 - e3
        disponible = self.cabecera.width() - e2 - ancho_titulo - e3 - (self.t_fijar.sizeHint().width() + e3) - 40 - e3
        natural = self.titulo.fontMetrics().horizontalAdvance(self.titulo.text()) + self.titulo.indent() + 8  # (no `sizeHint`: con ancho fijo da ese)
        titulo_cabe = natural <= ancho_titulo
        for prog in (self.prog, self.accion.prog):
            quiere = (prog is elegido and self.cabecera.width() > 0 and prog.ancho_categorias() <= disponible and titulo_cabe)
            if quiere:
                prog.categorias_en_cabecera(self.fila_cabecera, 1)
            else:
                prog.categorias_en_cabecera(None)
        if (elegido is not None and elegido.cat_en_cabecera) or (self.izq.isVisibleTo(self) and titulo_cabe):
            self.titulo.setFixedWidth(ancho_titulo)
        else:
            self.titulo.setMinimumWidth(0)
            self.titulo.setMaximumWidth(16777215)

    # -- páginas -----------------------------------------------------------------------------------
    def _programacion(self) -> QWidget:
        """Lo ancho de una transición o una acción: a la izquierda el programador del valor de una acción memorizada y,
        a su derecha, el programador por bloques de la receptividad de una transición o de la condición (o el evento) de una
        acción, con su texto, cómo se escribe, cómo se dibuja y «Crear las que faltan»."""
        w = QWidget()
        hl = QHBoxLayout(w)
        self._hl_prog = hl
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)
        hl.addWidget(self.accion.caja_valor, 1)
        self.pagina_bloques = QWidget()
        hl.addWidget(self.pagina_bloques, 3)
        lay = QVBoxLayout(self.pagina_bloques)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.l_bloques = QLabel()  # qué se edita («Condición de la acción Q (etapa 1)»): sobre el área de bloques, no en la cabecera
        self.l_bloques.setStyleSheet(f"color: {estilo.TINTA_2}; background: transparent")
        self.l_bloques.setWordWrap(True)
        self.l_bloques.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.l_bloques)
        self.fila_cabecera.addStretch(1)
        self.prog = Programador(lambda: self.e.fuente_bloques() if self.e is not None else ({}, []), compacto=True)
        self.prog.cambiado.connect(self._desde_bloques)
        self.prog.al_deshacer = lambda: self.e is not None and self.e.deshacer()
        self.prog.al_rehacer = lambda: self.e is not None and self.e.rehacer()
        lay.addWidget(self.prog, 1)
        # Debajo del área, toda la receptividad: el texto de la fórmula (solo se ve, con la notación del dibujo), cómo
        # se escribe, cómo se dibuja, el estado y «Crear las que faltan»
        self.caja_formula = QWidget()
        g = QGridLayout(self.caja_formula)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(estilo.E1)
        self.t_texto = CajaFormula()  # no se edita: se ve con la notación del dibujo y la arman los bloques
        self.t_texto.formato = self._formato_formula
        self.t_texto.setPlaceholderText("la fórmula se arma con bloques")
        # (el texto escrito y el dibujado de la receptividad ya no se enseñan; `_previsualizar` los sigue calculando, y las
        # pruebas los leen, en estas dos etiquetas ocultas)
        self.t_vista = QLabel(self.pagina_bloques)
        self.t_vista.setTextFormat(Qt.TextFormat.RichText)
        self.t_dibujo = QLabel(self.pagina_bloques)
        self.t_dibujo.setTextFormat(Qt.TextFormat.RichText)
        self.t_vista.hide()
        self.t_dibujo.hide()
        self.t_estado = AvisoFormula()
        self.t_crear = QPushButton("Crear las que faltan")
        self.t_crear.setToolTip("Declarar como entradas booleanas las variables que se usan y no existen")
        self.t_crear.clicked.connect(self._crear)
        self._l_formula = QLabel("Fórmula")
        g.addWidget(self._l_formula, 0, 0)
        g.addWidget(self.t_texto, 0, 1)
        self.t_texto.setMinimumWidth(48)
        g.addWidget(self.t_estado, 1, 1, 1, 3)
        g.addWidget(self.t_crear, 0, 2)
        self.prog.pie.removeWidget(self.prog.papelera)
        g.addWidget(self.prog.papelera, 0, 3, Qt.AlignmentFlag.AlignVCenter)
        g.setColumnStretch(1, 1)
        self._rejilla_formula, self._estado_abajo = g, True
        lay.addWidget(self.caja_formula)
        self._ver_bloques(None)
        return w

    def _ver_bloques(self, titulo: str | None) -> None:
        """El programador de la transición o de la acción (condición o evento), o nada si no hay que programar."""
        self.pagina_bloques.setVisible(titulo is not None)
        self.l_bloques.setText(titulo or "")
        self.l_bloques.setVisible(titulo is not None and self.pagina != "transicion")  # el título ya dice «Transición t»

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
        self.l_vacio.setStyleSheet(f"color: {estilo.TINTA_2}")
        return self.l_vacio

    def _etapa(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.s_etiqueta = QLineEdit()
        self.s_etiqueta.setMaxLength(MAX_ETIQUETA_ETAPA)  # más no cabe en el cuadro de la etapa
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
        self.s_enlace = QCheckBox("Enlace de activación")  # solo en una etapa de un recinto; como la opción del menú
        self.s_enlace.setToolTip("Al activarse la encapsulante, esta etapa se activa (el «*» del dibujo)")
        self.s_enlace.clicked.connect(lambda _: self.e.enlace_activacion(self.ident))
        f.addRow("Etiqueta", self.s_etiqueta)
        f.addRow("Tipo", self.s_tipo)
        f.addRow("", self.s_enlace)
        self.s_enlace.hide()
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

    def _formato_formula(self, texto: str) -> str | None:
        """La fórmula (receptividad, condición o evento) con la notación del dibujo; None si no se interpreta."""
        o = self._objetivo
        if o is None or self.e is None:
            return None
        segmentos = self.e.vista_formula(texto, o[1])
        return None if segmentos is None else _html(segmentos)

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
        accion = e.accion_activa() if e is not None else None
        self.prog.seleccionar_elemento((vivo, accion))
        if e is not None and (n := e.anotacion(vivo)):
            for campo in (self.s_etiqueta,self.s_comentario,self.t_etiqueta,self.t_comentario):
                campo.blockSignals(True);campo.clearFocus();campo.blockSignals(False)
            self._mostrado=("anotacion",vivo);self.ident=vivo;self.pagina="anotacion"
            self._objetivo=None;self._anterior=None;self._ver_bloques(None)
            self.accion.caja_valor.hide();self.cuerpo.show();self.vacio.hide();self.izq.hide()
            self.der.setCurrentIndex(5);self.der.show();self.msg.clear();self._ubicar_categorias()
            self.titulo.setText("Propiedades · "+("Texto" if n["kind"]=="text" else "Imagen"))
            self.nota_resumen.setText(n.get("text","") if n["kind"]=="text" else n.get("name","Imagen"))
            self.nota_editar.setText("Editar texto…" if n["kind"]=="text" else "Cambiar imagen…")
            self._remates_accion.mostrar(False)
            return
        self.continua = False
        aid = e.accion_activa() if e is not None else None
        if aid and e.datos_accion(aid)["tipo"] == "continua":  # una acción continua no se edita aquí: se despliega su variable con doble clic sobre ella
            for campo in (self.s_etiqueta, self.s_comentario, self.t_etiqueta, self.t_comentario):
                campo.blockSignals(True)
                campo.clearFocus()
                campo.blockSignals(False)
            self.continua, self._mostrado, self.ident, self.pagina = True, ("accion", aid), aid, "vacio"
            self.accion.mostrar(e, aid)  # (oculto, pero al día: sigue a la acción cuando cambia de borrador a acción del modelo)
            self._objetivo = self._anterior = None
            self._llevar_bloques(False)
            self._ver_bloques(None)
            self.accion.caja_valor.hide()
            self.cuerpo.hide()
            self.izq.hide()
            self.vacio.setText(self.FRASE_CONTINUA)
            self.l_vacio.setText(self.FRASE_CONTINUA)
            self.vacio.show()
            self.titulo.setText("Propiedades · Acción")
            self.msg.hide()
            self._remates_accion.mostrar(False)
            self._ubicar_categorias()
            return
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
        # el título dice solo el tipo («Propiedades · Transición»): el nombre ya se ve en el dibujo y se edita en el campo «Etiqueta»
        titulo = {"etapa": "Etapa", "transicion": "Transición", "enlace": "Enlace" if vivo else "", "barra": "Barra" if vivo else "",
                  "macro": "Macroetapa",
                  "orden": "Orden de forzado" + (" sin completar" if e.es_orden_suelta(vivo) else ""),
                  "marco": "Parcial" if vivo else "",
                  "accion": "Acción",
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
        self._llevar_bloques(kind == "accion" and self._objetivo is not None)
        self._ver_bloques(None if self._objetivo is None else
                          f"Receptividad de la transición {e.nombres.get(vivo, vivo)}" if kind == "transicion" else
                          e.titulo_accion(acc[0], acc[1]))
        if kind == "accion":
            self.accion.mostrar(e, aid)
            memorizada = self.accion.clave_tipo not in CONTINUAS
            self.der.setCurrentIndex(2 if (memorizada or self._objetivo is not None) else 0)
        else:
            self.accion.caja_valor.setVisible(False)
        if self._objetivo is not None:
            guardado = self._guardado()
            self._poner(self.t_texto, guardado)
            self.prog.poner(guardado)
            self._previsualizar()
        self._anterior = self._objetivo
        self.der.setVisible(kind != "etapa" and not (kind == "accion" and self._bloques_fuera and not memorizada))
        if kind == "etapa":
            s = next(s for s in e.M["steps"] if s["id"] == vivo)
            self._poner(self.s_etiqueta, s["label"])
            self._poner(self.s_comentario, e.comentario(vivo))
            self.s_tipo.setCurrentIndex(1 if s["initial"] else 0)
            rol = e.ed.partial_roles().get(e.parcial_de(vivo))
            en_recinto = bool(rol and rol["kind"] == "enclosure")
            self.s_enlace.setVisible(en_recinto)
            self.s_enlace.setChecked(en_recinto and vivo in rol["activation"])
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
        self._remates_accion.mostrar(kind == "accion")
        self._ubicar_categorias()

    @staticmethod
    def _poner(campo: QLineEdit, texto: str) -> None:
        if not campo.hasFocus() and campo.text() != texto:
            campo.setText(texto)

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
        self._previsualizar_texto()
        if self.flotante:  # solo se ve lo que no está bien (rojo o naranja); «correcta» y «vacía» (gris) no
            malo = self.t_estado.styleSheet() in (f"color: {COL['err']}", f"color: {NARANJA}") and bool(self.t_estado.text())
            if malo != self.t_estado.isVisibleTo(self.caja_formula):
                self.t_estado.setVisible(malo)
                self.alto_cambiado.emit()

    def _previsualizar_texto(self) -> None:
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
            if d is None and cosa == "Evento" and not is_event_positive(e.significado(ident, texto)):
                self.t_estado.setText("Esto es una condición, no un evento válido. Elija un flanco de subida (↑) o de bajada (↓).")
                self.t_estado.setStyleSheet(f"color: {COL['err']}")
                self.t_dibujo.setText(_html(norm(e.significado(ident, texto), True, e.nombres)))
                return
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
            if self.flotante:
                self.t_estado.show()
            self.parpadeo_crear.iniciar({"crear"})

    def _pintar_crear(self) -> None:
        self.t_crear.setStyleSheet(f"background: {NARANJA}" if self.parpadeo_crear.activos() else "")
