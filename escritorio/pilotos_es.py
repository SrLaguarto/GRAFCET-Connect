"""Dibujo del piloto de E/S, con halo contenido y contorno de contraste."""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from . import estilo


def tamano_piloto(alto_fila=None):
    alto = alto_fila if alto_fila is not None else (20 if estilo.ESCALA == "grande" else 16)
    lado = round(alto * 0.6) + 4
    return QSize(lado, lado)


def pintar_piloto(widget, colores, encendido):
    pintor = QPainter(widget)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    caja = QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
    circulo = caja.adjusted(2, 2, -2, -2)
    pintor.setPen(Qt.PenStyle.NoPen)
    if encendido:
        pintor.setBrush(QColor(estilo.PILOTO_HALO))
        pintor.drawEllipse(caja)
    if len(colores) == 1:
        pintor.setBrush(colores[0])
        pintor.drawEllipse(circulo)
    else:
        paso = 360 * 16 // len(colores)
        for indice, color in enumerate(colores):
            pintor.setBrush(color)
            pintor.drawPie(circulo, indice * paso, paso)
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.setPen(QPen(QColor(estilo.BORDE_CONTROL), 1))
    pintor.drawEllipse(circulo)
    pintor.end()
