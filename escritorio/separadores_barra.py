"""Separación visible entre barras, donde Qt oculta los separadores iniciales."""
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import estilo


class SeparadorBarra(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("separadorBarras")
        self.setFixedWidth(2 * estilo.E1 + 1)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def sizeHint(self):  # noqa: N802
        return QSize(self.width(), estilo.ALTO_CONTROL_COMPACTO)

    def paintEvent(self, evento):  # noqa: N802
        pintor = QPainter(self)
        pintor.setPen(QPen(QColor(estilo.BORDE), 1))
        x = self.width() // 2
        pintor.drawLine(x, estilo.E1, x, max(estilo.E1, self.height() - estilo.E1 - 1))
