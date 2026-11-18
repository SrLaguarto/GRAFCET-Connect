"""Catálogo de fichas, arrastre al dibujo y desborde de Favoritos."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QMenu, QSizePolicy, QToolButton, QWidget, QWidgetAction

from . import estilo
from .propiedades import COLOCABLES, Paleta
from .ayudas_emergentes import ayuda_html

PREDETERMINADOS = (
    "etapa_inicial", "etapa", "transicion", "simultaneidad", "accion:continua", "accion:condicionada",
    "accion:activacion", "accion:desactivacion", "accion:evento", "forzado", "macroetapa", "encapsulante",
    "parcial", "texto", "imagen",
)
LADO_MINI = 24
FACTOR_MINI = LADO_MINI / 20


def _punto(x, y):
    return QPointF(x * FACTOR_MINI, y * FACTOR_MINI)


def _rect(x, y, ancho, alto):
    return QRectF(x * FACTOR_MINI, y * FACTOR_MINI, ancho * FACTOR_MINI, alto * FACTOR_MINI)


def _pintar_accion_mini(pintor, clave):
    cuerpo = _rect(2.5, 6.5, 15, 7)
    pintor.drawRect(cuerpo)
    if clave == "forzado":
        pintor.drawRect(cuerpo.adjusted(2.7, 2.7, -2.7, -2.7))
        return
    tipo = clave.partition(":")[2]
    if tipo == "condicionada":
        pintor.drawLine(_punto(5, 3), _punto(5, 6.5))
    elif tipo in ("activacion", "desactivacion"):
        activar = tipo == "activacion"
        base, punta, hombro = (6.5, 1.5, 3.25) if activar else (13.5, 18.5, 16.75)
        pintor.drawLine(_punto(5, base), _punto(5, punta))
        camino = QPainterPath(_punto(3.25, hombro))
        camino.lineTo(_punto(5, punta))
        camino.lineTo(_punto(6.75, hombro))
        pintor.drawPath(camino)
    elif tipo == "evento":
        pintor.drawLine(_punto(5, 1.5), _punto(5, 6.5))
        pintor.setBrush(QColor(estilo.TINTA))
        pintor.drawPolygon(QPolygonF([_punto(5, 1.5), QPointF(3, 3.6), _punto(5, 4.5)]))
        pintor.setBrush(Qt.BrushStyle.NoBrush)


def _pintar_etapa_mini(pintor, clave):
    cuerpo = QRectF(3, 3, 18, 18)
    pintor.drawRect(cuerpo)
    if clave == "etapa_inicial":
        pintor.drawRect(cuerpo.adjusted(4.5, 4.5, -4.5, -4.5))
    elif clave == "macroetapa":
        for proporcion in (3 / 11, 8 / 11):
            y = cuerpo.top() + cuerpo.height() * proporcion
            pintor.drawLine(QPointF(cuerpo.left(), y), QPointF(cuerpo.right(), y))
    elif clave == "encapsulante":
        lapiz = QPen(QColor(estilo.TINTA), 1.5)
        lapiz.setCapStyle(Qt.PenCapStyle.FlatCap)
        pintor.setPen(lapiz)
        corte = cuerpo.width() * 2.5 / 11
        for x, y, sx, sy in ((3, 3, 1, 1), (21, 3, -1, 1), (3, 21, 1, -1), (21, 21, -1, -1)):
            pintor.drawLine(QPointF(x + sx * corte, y), QPointF(x, y + sy * corte))

def _pintar_g_mini(pintor):
    """G vectorial pequeña, con el mismo trazo y sin depender de una fuente diminuta."""
    camino = QPainterPath(_punto(15.5, 8))
    for x, y in ((14.5, 7), (11.5, 7), (10.5, 8), (10.5, 12),
                 (11.5, 13), (15.5, 13), (15.5, 10), (13, 10)):
        camino.lineTo(_punto(x, y))
    pintor.drawPath(camino)


def _pintar_otros_mini(pintor, clave):
    if clave == "transicion":
        pintor.drawLine(_punto(10, 3), _punto(10, 17))
        pintor.drawLine(QPointF(3, 12), QPointF(21, 12))
    elif clave == "simultaneidad":
        for y in (8.5, 11.5):
            pintor.drawLine(QPointF(3, y * FACTOR_MINI), QPointF(21, y * FACTOR_MINI))
    elif clave == "parcial":
        pintor.drawRoundedRect(QRectF(3, 6.375, 18, 11.25), 2, 2)
        _pintar_g_mini(pintor)
    else:
        pintor.drawRect(QRectF(3, 3, 18, 18))
        if clave == "texto":
            for y in (7, 10, 13):
                pintor.drawLine(_punto(5, y), _punto(15 if y != 13 else 12, y))
        elif clave == "imagen":
            pintor.drawEllipse(_rect(5, 5, 2.5, 2.5))
            camino = QPainterPath(_punto(4, 14))
            for x, y in ((8, 9), (11, 12), (14, 8), (16, 11)):
                camino.lineTo(_punto(x, y))
            pintor.drawPath(camino)


def pintar_mini(pintor, clave):
    """Geometría propia en una caja lógica de 24×24, sin reducir la ficha de la paleta."""
    pintor.save()
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(QPen(QColor(estilo.TINTA), 1.5))
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    if clave.startswith("accion:") or clave == "forzado":
        _pintar_accion_mini(pintor, clave)
    elif clave in ("etapa", "etapa_inicial", "macroetapa", "encapsulante"):
        _pintar_etapa_mini(pintor, clave)
    else:
        _pintar_otros_mini(pintor, clave)
    pintor.restore()


class _MotorMini(QIconEngine):
    def __init__(self, clave):
        super().__init__()
        self.clave = clave

    def clone(self):
        return _MotorMini(self.clave)

    def paint(self, pintor, rect, modo, estado):
        pintor.save()
        pintor.translate(rect.x(), rect.y())
        pintor.scale(rect.width() / LADO_MINI, rect.height() / LADO_MINI)
        pintar_mini(pintor, self.clave)
        pintor.restore()

    def pixmap(self, tamano, modo, estado):
        return self.scaledPixmap(tamano, modo, estado, 1.0)

    def scaledPixmap(self, tamano, modo, estado, escala):
        """Qt entrega el tamaño lógico: se pinta directamente en los píxeles físicos de cada DPR."""
        fisico = QSize(round(tamano.width() * escala), round(tamano.height() * escala))
        imagen = QPixmap(fisico)
        imagen.setDevicePixelRatio(escala)
        imagen.fill(Qt.GlobalColor.transparent)
        pintor = QPainter(imagen)
        self.paint(pintor, QRectF(0, 0, tamano.width(), tamano.height()), modo, estado)
        pintor.end()
        return imagen


def icono_mini(clave):
    return QIcon(_MotorMini(clave))


class BotonFavorito(QToolButton):
    def __init__(self, barra, clave, menu=None):
        super().__init__(menu or barra)
        self.barra = barra
        self.clave = clave
        self.menu = menu
        self._pulsado = None
        self.setIcon(icono_mini(clave))
        self.setIconSize(QSize(barra.lado_icono, barra.lado_icono))
        self.setToolTip(ayuda_html(Paleta.texto_ayuda(clave), Paleta.nombre(clave)))
        self.setAccessibleName(Paleta.nombre(clave))
        self.clicked.connect(lambda: barra.paleta.ayuda.emit(Paleta.texto_ayuda(clave)))
        self.setAutoRaise(True)
        self.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0; min-height: 0; }"
            f"QToolButton:hover {{ background: {estilo.HOVER}; }}")
        if menu is not None:
            self.setText(Paleta.nombre(clave))
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.setMinimumHeight(estilo.ALTO_CONTROL)

    def mousePressEvent(self, evento):
        self._pulsado = evento.position().toPoint() if evento.button() == Qt.MouseButton.LeftButton else None
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento):
        if self._pulsado is None or not evento.buttons() & Qt.MouseButton.LeftButton:
            return
        distancia = (evento.position().toPoint() - self._pulsado).manhattanLength()
        if distancia < QApplication.startDragDistance():
            return
        self._pulsado = None
        if self.menu is not None:
            self.menu.hide()
        self.barra.paleta.arrastrar_elemento(self.clave, self)
        self.setDown(False)

    def mouseReleaseEvent(self, evento):
        self._pulsado = None
        super().mouseReleaseEvent(evento)


class BarraFavoritos(QWidget):
    distribucion_cambiada = Signal()
    CLAVE_AJUSTES = "favoritos/elementos"

    def __init__(self, ajustes, paleta):
        super().__init__()
        self.paleta = paleta
        self.lado_icono = round((estilo.ALTO_BARRA + LADO_MINI) / 2)
        self.compacta = False
        self._menu = None
        self._visibles = []
        self.ocultos = []
        ajustes.remove(self.CLAVE_AJUSTES)
        ajustes.remove("favoritos/visible")
        ajustes.remove("paletas/favoritos_principal_v1")
        ajustes.remove("favoritos/texto_imagen_v1")
        self.orden = list(PREDETERMINADOS)
        self.botones = {h: BotonFavorito(self, h) for h in COLOCABLES}
        self.desborde = QToolButton(self)
        self.desborde.setText("»")
        self.desborde.setToolTip("Más favoritos")
        self.desborde.setAutoRaise(True)
        self.desborde.clicked.connect(self._abrir_desborde)
        self.setObjectName("barraFavoritos")
        self.setAccessibleName("Favoritos de Elementos")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setAcceptDrops(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._disponer()

    def ancho_boton(self):
        if self.compacta:
            return max(estilo.ALTO_CONTROL, self.lado_icono)
        return max(estilo.ALTO_BARRA, self.lado_icono + estilo.E1)

    def sizeHint(self):
        return QSize(len(self.orden) * self.ancho_boton() + 2 * estilo.E2, estilo.ALTO_BARRA)

    def minimumSizeHint(self):
        return QSize(self.ancho_boton() + 2 * estilo.E2, estilo.ALTO_BARRA)

    def _disponer(self):
        ancho = self.ancho_boton()
        capacidad = max(0, (self.width() - 2 * estilo.E2) // ancho)
        hay_desborde = capacidad < len(self.orden)
        cantidad = max(0, capacidad - int(hay_desborde))
        self._visibles = self.orden[:cantidad]
        self.ocultos = self.orden[cantidad:]
        for clave, boton in self.botones.items():
            boton.setVisible(clave in self._visibles)
        alto = self.height()
        for i, clave in enumerate(self._visibles):
            self.botones[clave].setGeometry(estilo.E2 + i * ancho, 0, ancho, alto)
        self.desborde.setVisible(hay_desborde)
        self.desborde.setGeometry(estilo.E2 + cantidad * ancho, 0, ancho, alto)
        self.update()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.lado_icono = round((self.height() + LADO_MINI) / 2)
        if self.window().width() <= 960:
            self.lado_icono = 30
        for boton in self.botones.values():
            boton.setIconSize(QSize(self.lado_icono, self.lado_icono))
        self._disponer()
        self.distribucion_cambiada.emit()

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setPen(QPen(QColor(estilo.BORDE), 1))
        for x in (0, self.width() - 1):
            pintor.drawLine(x, estilo.E1, x, self.height() - estilo.E1)
        pintor.end()

    def foco(self):
        if not self.isVisibleTo(self.window()):
            return []
        botones = [self.botones[clave] for clave in self._visibles]
        if self.desborde.isVisible():
            botones.append(self.desborde)
        return botones

    def crear_menu_desborde(self):
        menu = QMenu(self)
        for clave in self.ocultos:
            accion = QWidgetAction(menu)
            accion.setText(Paleta.nombre(clave))
            accion.setIcon(icono_mini(clave))
            accion.setData(clave)
            accion.setDefaultWidget(BotonFavorito(self, clave, menu))
            menu.addAction(accion)
        return menu

    def _abrir_desborde(self):
        self._menu = self.crear_menu_desborde()
        self._menu.popup(self.desborde.mapToGlobal(QPoint(0, self.desborde.height())))
