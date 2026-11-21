"""Realización en Qt de un modelo visual: un ítem estándar por descriptor, en el orden de dibujo (V2-E3)."""
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsScene

from ..elementos_lupa import DATO_ELEMENTOS, DATO_PARCIAL
from .descriptores import Descriptor
from .modelo_visual import ModeloVisual



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


def crear(escena: QGraphicsScene, d: Descriptor, reservar: bool = True) -> list[Any]:
    """Crea y añade a la escena los ítems de un descriptor (los mismos, con los mismos datos, que `diagrama._Pintor`). Con `reservar`,
    un texto de una `EscenaDiagrama` sale de su reserva de textos idénticos; la escena incremental no la usa."""
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
        item = (escena.texto(contenido, tinta, fuente) if reservar and isinstance(escena, EscenaDiagrama)
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


def crear_todo(escena: QGraphicsScene, mv: ModeloVisual, reservar: bool = True) -> dict[Any, list[tuple[Descriptor, list[Any]]]]:
    """Como `todo`, y devuelve los ítems de cada objeto: clave -> [(descriptor, [ítems])]."""
    nodos: dict[Any, list[tuple[Descriptor, list[Any]]]] = {}
    for clave, d in mv.secuencia:
        nodos.setdefault(clave, []).append((d, crear(escena, d, reservar)))
    return nodos


def _cabecera(item: Any, z: float, tip: str | None, parcial: Any, elementos: Any) -> None:
    item.setData(DATO_PARCIAL, parcial)
    item.setData(DATO_ELEMENTOS, elementos)
    item.setZValue(z)
    item.setToolTip(tip or "")


def actualizar(items: list[Any], antes: Descriptor, ahora: Descriptor) -> bool:
    """Pone un ítem ya creado como lo dejaría `crear` con el descriptor nuevo. Devuelve False si no se puede en el sitio (otro
    tipo de ítem, otro texto, otra nota): quien llama lo sustituye."""
    tipo = ahora[0]
    if tipo != antes[0] or len(items) != 1 or tipo == "nota":
        return False
    item = items[0]
    if tipo == "linea":
        _, x1, y1, x2, y2, pluma, z, tip, parcial, elementos = ahora
        item.setLine(x1, y1, x2, y2)
        item.setPen(_pluma(pluma))
        _cabecera(item, z, tip, parcial, elementos)
    elif tipo == "camino":
        _, pts, pluma, relleno, z, tip, parcial, elementos = ahora
        ruta = QPainterPath(QPointF(*pts[0]))
        for p in pts[1:]:
            ruta.lineTo(*p)
        if relleno:
            ruta.closeSubpath()
        item.setPath(ruta)
        item.setPen(_pluma(pluma))
        item.setBrush(_relleno(relleno))
        _cabecera(item, z, tip, parcial, elementos)
    elif tipo == "rect":
        _, x, y, w, h, pluma, relleno, radio, z, tip, parcial, elementos = ahora
        if bool(radio) != bool(antes[7]):
            return False
        if radio:
            ruta = QPainterPath()
            ruta.addRoundedRect(QRectF(x, y, w, h), radio, radio)
            item.setPath(ruta)
        else:
            item.setRect(QRectF(x, y, w, h))
        item.setPen(_pluma(pluma))
        item.setBrush(_relleno(relleno))
        _cabecera(item, z, tip, parcial, elementos)
    elif tipo == "elipse":
        _, cx, cy, r, relleno, z, tip, parcial, elementos = ahora
        item.setRect(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        item.setBrush(_relleno(relleno))
        _cabecera(item, z, tip, parcial, elementos)
    elif tipo == "texto":
        if ahora[1:4] != antes[1:4]:
            return False
        _, _, _, _, x, arriba, z, tip, parcial, elementos = ahora
        item.setPos(x, arriba)
        _cabecera(item, z, tip, parcial, elementos)
    elif tipo == "comentario":
        if ahora[1:3] != antes[1:3]:
            return False
        _, _, _, x, y, z, parcial, elementos = ahora
        item.setPos(x, y)
        _cabecera(item, z, None, parcial, elementos)
    else:
        return False
    return True
