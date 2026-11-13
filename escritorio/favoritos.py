"""Favoritos de la paleta: selección persistente, arrastre, reordenación y desborde."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QMenu, QSizePolicy, QToolButton, QWidget, QWidgetAction

from . import estilo
from .propiedades import COLOCABLES, SECCIONES, Paleta

PREDETERMINADOS = (
    "etapa_inicial", "etapa", "transicion", "simultaneidad", "accion:continua", "accion:condicionada",
    "accion:activacion", "accion:desactivacion", "accion:evento", "forzado", "macroetapa", "encapsulante", "parcial",
)
LADO_MINI = 20


def _pintar_accion_mini(pintor, clave):
    cuerpo = QRectF(2.5, 6.5, 15, 7)
    pintor.drawRect(cuerpo)
    if clave == "forzado":
        pintor.drawRect(cuerpo.adjusted(2.25, 2.25, -2.25, -2.25))
        return
    tipo = clave.partition(":")[2]
    if tipo == "condicionada":
        pintor.drawLine(QPointF(5, 3), QPointF(5, 6.5))
    elif tipo in ("activacion", "desactivacion"):
        activar = tipo == "activacion"
        base, punta, hombro = (6.5, 1.5, 3.25) if activar else (13.5, 18.5, 16.75)
        pintor.drawLine(QPointF(5, base), QPointF(5, punta))
        camino = QPainterPath(QPointF(3.25, hombro))
        camino.lineTo(5, punta)
        camino.lineTo(6.75, hombro)
        pintor.drawPath(camino)
    elif tipo == "evento":
        pintor.drawLine(QPointF(5, 1.5), QPointF(5, 6.5))
        pintor.setBrush(QColor(estilo.TINTA))
        pintor.drawPolygon(QPolygonF([QPointF(5, 1.5), QPointF(2, 3), QPointF(5, 4.5)]))
        pintor.setBrush(Qt.BrushStyle.NoBrush)


def _pintar_etapa_mini(pintor, clave):
    cuerpo = QRectF(4.5, 4.5, 11, 11)
    pintor.drawRect(cuerpo)
    if clave == "etapa_inicial":
        pintor.drawRect(cuerpo.adjusted(2.75, 2.75, -2.75, -2.75))
    elif clave == "macroetapa":
        for y in (7.5, 12.5):
            pintor.drawLine(QPointF(cuerpo.left(), y), QPointF(cuerpo.right(), y))
    elif clave == "encapsulante":
        for a, b in (((7, 4.5), (4.5, 7)), ((13, 4.5), (15.5, 7)),
                     ((4.5, 13), (7, 15.5)), ((13, 15.5), (15.5, 13))):
            pintor.drawLine(QPointF(*a), QPointF(*b))


def _pintar_g_mini(pintor):
    """G vectorial pequeña, con el mismo trazo y sin depender de una fuente diminuta."""
    camino = QPainterPath(QPointF(15.5, 8))
    for x, y in ((14.5, 7), (11.5, 7), (10.5, 8), (10.5, 12),
                 (11.5, 13), (15.5, 13), (15.5, 10), (13, 10)):
        camino.lineTo(x, y)
    pintor.drawPath(camino)


def _pintar_otros_mini(pintor, clave):
    if clave == "transicion":
        pintor.drawLine(QPointF(10, 3), QPointF(10, 17))
        pintor.drawLine(QPointF(5, 10), QPointF(15, 10))
    elif clave == "simultaneidad":
        for y in (8.5, 11.5):
            pintor.drawLine(QPointF(3, y), QPointF(17, y))
    elif clave == "parcial":
        pintor.drawRoundedRect(QRectF(2, 5, 16, 10), 2, 2)
        _pintar_g_mini(pintor)
    else:
        pintor.drawRect(QRectF(2.5, 3, 15, 14))
        if clave == "texto":
            for y in (7, 10, 13):
                pintor.drawLine(QPointF(5, y), QPointF(15 if y != 13 else 12, y))
        elif clave == "imagen":
            pintor.drawEllipse(QRectF(5, 5, 2.5, 2.5))
            camino = QPainterPath(QPointF(4, 14))
            for x, y in ((8, 9), (11, 12), (14, 8), (16, 11)):
                camino.lineTo(x, y)
            pintor.drawPath(camino)


def pintar_mini(pintor, clave):
    """Geometría propia en una caja lógica de 20×20, sin reducir la ficha de la paleta."""
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


class MenuSeleccion(QMenu):
    """Las casillas cambian en el acto sin cerrar la selección de favoritos."""

    def mouseReleaseEvent(self, evento):
        accion = self.actionAt(evento.position().toPoint())
        if evento.button() == Qt.MouseButton.LeftButton and accion is not None and accion.isCheckable():
            accion.trigger()
            return
        super().mouseReleaseEvent(evento)

    def keyPressEvent(self, evento):
        accion = self.activeAction()
        if evento.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if accion is not None and accion.isCheckable():
                accion.trigger()
                return
        super().keyPressEvent(evento)


class BotonFavorito(QToolButton):
    def __init__(self, barra, clave, menu=None):
        super().__init__(menu or barra)
        self.barra = barra
        self.clave = clave
        self.menu = menu
        self._pulsado = None
        self.setIcon(icono_mini(clave))
        self.setIconSize(QSize(20, 20))
        self.setToolTip(f"Favoritos: {Paleta.nombre(clave)}")
        self.setAccessibleName(self.toolTip())
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
    contenido_cambiado = Signal()
    CLAVE_AJUSTES = "favoritos/elementos"

    def __init__(self, ajustes, paleta):
        super().__init__()
        self.ajustes = ajustes
        self.paleta = paleta
        self._insercion = None
        self._menu = None
        self._visibles = []
        self.ocultos = []
        guardados = ajustes.value(self.CLAVE_AJUSTES) if ajustes.contains(self.CLAVE_AJUSTES) else PREDETERMINADOS
        if isinstance(guardados, str):
            guardados = [guardados]
        self.orden = list(dict.fromkeys(h for h in (guardados or []) if h in COLOCABLES))
        self.botones = {h: BotonFavorito(self, h) for h in COLOCABLES}
        self.desborde = QToolButton(self)
        self.desborde.setText("»")
        self.desborde.setToolTip("Más favoritos")
        self.desborde.setAutoRaise(True)
        self.desborde.clicked.connect(self._abrir_desborde)
        self.setObjectName("barraFavoritos")
        self.setAccessibleName("Favoritos de Elementos")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setAcceptDrops(True)
        self._disponer()

    def ancho_boton(self):
        return estilo.ALTO_BARRA

    def sizeHint(self):
        return QSize(len(self.orden) * self.ancho_boton() + 2 * estilo.E2, estilo.ALTO_BARRA)

    def minimumSizeHint(self):
        return QSize(self.ancho_boton() + 2 * estilo.E2, estilo.ALTO_BARRA)

    def _guardar(self):
        self.ajustes.setValue(self.CLAVE_AJUSTES, self.orden)
        self._disponer()
        self.updateGeometry()
        self.contenido_cambiado.emit()

    def mostrar_elemento(self, clave, visible):
        if clave not in COLOCABLES:
            return
        if visible and clave not in self.orden:
            self.orden.append(clave)
        elif not visible and clave in self.orden:
            self.orden.remove(clave)
        self._guardar()

    def reordenar(self, clave, posicion):
        if clave not in self.orden:
            return
        anterior = self.orden.index(clave)
        self.orden.remove(clave)
        if anterior < posicion:
            posicion -= 1
        self.orden.insert(max(0, min(posicion, len(self.orden))), clave)
        self._guardar()

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
        self._disponer()

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setPen(QPen(QColor(estilo.BORDE), 1))
        for x in (0, self.width() - 1):
            pintor.drawLine(x, estilo.E1, x, self.height() - estilo.E1)
        if self._insercion is not None:
            x = estilo.E2 + self._insercion * self.ancho_boton()
            pintor.setPen(QPen(QColor(estilo.ACENTO), 2))
            pintor.drawLine(x, estilo.E1, x, self.height() - estilo.E1)
        pintor.end()

    def crear_menu_seleccion(self):
        menu = MenuSeleccion(self)
        for titulo, claves in SECCIONES:
            menu.addSection(titulo)
            for clave in claves:
                accion = menu.addAction(icono_mini(clave), Paleta.nombre(clave))
                accion.setData(clave)
                accion.setCheckable(True)
                accion.setChecked(clave in self.orden)
                accion.toggled.connect(lambda visible, h=clave: self.mostrar_elemento(h, visible))
        return menu

    def contextMenuEvent(self, evento):
        self._menu = self.crear_menu_seleccion()
        self._menu.popup(evento.globalPos())

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

    def _admite(self, evento):
        origen = evento.source()
        return (isinstance(origen, BotonFavorito) and origen.barra is self
                and evento.mimeData().text() in self.orden)

    def dragEnterEvent(self, evento):
        if self._admite(evento):
            evento.acceptProposedAction()
        else:
            evento.ignore()

    def dragMoveEvent(self, evento):
        if not self._admite(evento):
            evento.ignore()
            return
        x = evento.position().x()
        self._insercion = sum(x > self.botones[h].geometry().center().x() for h in self._visibles)
        self.update()
        evento.acceptProposedAction()

    def dragLeaveEvent(self, evento):
        self._insercion = None
        self.update()

    def dropEvent(self, evento):
        if self._admite(evento):
            self.dragMoveEvent(evento)
            self.reordenar(evento.mimeData().text(), self._insercion)
            evento.acceptProposedAction()
        else:
            evento.ignore()
        self._insercion = None
        self.update()
