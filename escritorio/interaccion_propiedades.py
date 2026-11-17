"""Indicadores contenidos y arrastre acotado de la cabecera de Propiedades."""
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton, QStylePainter

from . import estilo


class CasillaPropiedades(QCheckBox):
    """Deja un píxel para el borde nativo de Windows, que pinta fuera del indicador."""

    def initStyleOption(self, opcion):  # noqa: N802
        super().initStyleOption(opcion)
        opcion.rect.adjust(1, 0, -1, 0)

    def sizeHint(self):  # noqa: N802
        return super().sizeHint() + QSize(2, 0)

    def minimumSizeHint(self):  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, evento):  # noqa: N802
        opcion = QStyleOptionButton()
        self.initStyleOption(opcion)
        pintor = QStylePainter(self)
        pintor.drawControl(QStyle.ControlElement.CE_CheckBox, opcion)


class ArrastrePropiedades(QObject):
    """Solo la cabecera arrastra; cada apertura vuelve a usar el centro calculado."""

    def __init__(self, flotante, principal):
        super().__init__(flotante)
        self.flotante = flotante
        self.principal = principal
        self.inicio = None
        self.posicion = QPoint()
        self.movida = False
        for zona in (flotante.cabecera, flotante.titulo):
            zona.setCursor(Qt.CursorShape.SizeAllCursor)
            zona.installEventFilter(self)

    def limitar(self, posicion=None):
        area = QRect(self.principal.mapToGlobal(QPoint()), self.principal.size())
        area.adjust(estilo.E1, estilo.E1, -estilo.E1, -estilo.E1)
        v = self.flotante
        posicion = v.pos() if posicion is None else posicion
        barra = v.cabecera.geometry()
        visible = min(120, barra.width() // 3)
        minimo = area.left() - barra.right() + visible - 1
        maximo = area.right() - barra.left() - visible + 1
        x = max(minimo, min(posicion.x(), maximo))
        y = max(area.top() - barra.top(), min(posicion.y(), area.bottom() - barra.bottom()))
        v.move(x, y)
        # La geometría completa se conserva; lo que sale del cliente queda oculto por la máscara.
        cliente = QRect(self.principal.mapToGlobal(QPoint()), self.principal.size())
        visible = cliente.intersected(v.geometry()).translated(-v.pos())
        mascara = QRegion(visible)
        if mascara == QRegion(v.rect()):
            v.clearMask()
        elif mascara != v.mask():
            v.setMask(mascara)

    def eventFilter(self, objeto, evento):  # noqa: N802
        tipo = evento.type()
        if tipo == QEvent.Type.MouseButtonPress and evento.button() == Qt.MouseButton.LeftButton:
            self.inicio = evento.globalPosition().toPoint()
            self.posicion = self.flotante.pos()
            return True
        if tipo == QEvent.Type.MouseMove and self.inicio is not None:
            self.movida = True
            self.limitar(self.posicion + evento.globalPosition().toPoint() - self.inicio)
            return True
        if tipo == QEvent.Type.MouseButtonRelease and self.inicio is not None:
            self.inicio = None
            return True
        return False
