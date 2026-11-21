"""Realización en Qt de un modelo visual: un ítem estándar por descriptor, en el orden de dibujo (V2-E3)."""
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsScene

from .descriptores import Descriptor
from .modelo_visual import ModeloVisual

DATO_PARCIAL = 42
DATO_ELEMENTOS = 43


def _pluma(p: Any) -> QPen:
    from ..diagrama import _Pintor
    return QPen(Qt.PenStyle.NoPen) if p is None else _Pintor.pen(p[1], p[2], p[3])


def _relleno(nombre: str | None) -> QBrush:
    from ..diagrama import COL
    return QBrush(QColor(COL[nombre])) if nombre else QBrush(Qt.BrushStyle.NoBrush)


def _poner(item: Any, z: float, tip: str | None, parcial: Any, elementos: Any) -> Any:
    item.setData(DATO_PARCIAL, parcial)
    item.setData(DATO_ELEMENTOS, elementos)
    item.setZValue(z)
    if tip:
        item.setToolTip(tip)
    return item


def crear(escena: QGraphicsScene, d: Descriptor) -> list[Any]:
    """Crea y añade a la escena los ítems de un descriptor (los mismos, con los mismos datos, que `diagrama._Pintor`)."""
    from .. import diagrama as dg
    from ..textos_diagrama import EscenaDiagrama, texto_nuevo
    tipo = d[0]
    if tipo == "linea":
        _, x1, y1, x2, y2, pluma, z, tip, parcial, elementos = d
        return [_poner(escena.addLine(x1, y1, x2, y2, _pluma(pluma)), z, tip, parcial, elementos)]
    if tipo == "camino":
        _, pts, pluma, relleno, z, tip, parcial, elementos = d
        ruta = QPainterPath(QPointF(*pts[0]))
        for p in pts[1:]:
            ruta.lineTo(*p)
        if relleno:
            ruta.closeSubpath()
        return [_poner(escena.addPath(ruta, _pluma(pluma), _relleno(relleno)), z, tip, parcial, elementos)]
    if tipo == "rect":
        _, x, y, w, h, pluma, relleno, radio, z, tip, parcial, elementos = d
        if radio:
            ruta = QPainterPath()
            ruta.addRoundedRect(QRectF(x, y, w, h), radio, radio)
            item = escena.addPath(ruta, _pluma(pluma), _relleno(relleno))
        else:
            item = escena.addRect(QRectF(x, y, w, h), _pluma(pluma), _relleno(relleno))
        return [_poner(item, z, tip, parcial, elementos)]
    if tipo == "elipse":
        _, cx, cy, r, relleno, z, tip, parcial, elementos = d
        item = escena.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r), QPen(Qt.PenStyle.NoPen), _relleno(relleno))
        return [_poner(item, z, tip, parcial, elementos)]
    if tipo == "texto":
        _, contenido, color, (tamano, negrita, mono), x, arriba, z, tip, parcial, elementos = d
        fuente, tinta = dg._fuente(tamano, negrita, mono), QColor(dg.COL[color])
        item = (escena.texto(contenido, tinta, fuente) if isinstance(escena, EscenaDiagrama)
                else texto_nuevo(contenido, tinta, fuente))
        item.setPos(x, arriba)
        item.setToolTip(tip or "")
        escena.addItem(item)
        return [_poner(item, z, tip, parcial, elementos)]
    if tipo == "comentario":
        _, texto, ancho, x, y, z, parcial, elementos = d
        item = dg._item_comentario(texto, ancho)
        item.setPos(x, y)
        escena.addItem(item)
        return [_poner(item, z, None, parcial, elementos)]
    if tipo == "nota":
        from ..anotaciones import dibujar_nota
        return dibujar_nota(escena, dict(d[1]), d[2])
    raise ValueError(f"descriptor desconocido: {tipo!r}")


def todo(escena: QGraphicsScene, mv: ModeloVisual) -> None:
    """Dibuja el modelo visual entero sobre una escena (vacía): ítem a ítem, en el orden de dibujo."""
    for _, d in mv.secuencia:
        crear(escena, d)
