"""Texto e imágenes de presentación: importación, edición y dibujo, sin semántica GRAFCET."""
import base64
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPixmap, QPen, QBrush
from PySide6.QtWidgets import (QColorDialog, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QFontComboBox, QFormLayout, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsTextItem, QPlainTextEdit, QPushButton, QVBoxLayout)
from .campos_medidos import SpinMedido as QSpinBox
from . import estilo
from .estilo_dialogos import PieDialogo, aplicar_escala_dialogo


def rect(n):
    return QRectF(n["x"]+100,n["y"],n["width"],n["height"])


def en(M,p):
    return next((n for n in reversed(M.get("annotations",[])) if rect(n).adjusted(-3,-3,3,3).contains(p)),None)


def importar_imagen(padre=None):
    nombre,_=QFileDialog.getOpenFileName(padre,"Añadir imagen","","Imágenes (*.png *.jpg *.jpeg)")
    if not nombre:return None
    datos=Path(nombre).read_bytes();imagen=QImage.fromData(datos)
    if imagen.isNull():raise ValueError("No se puede leer esta imagen PNG o JPG")
    mime="image/png" if datos.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if datos.startswith(b"\xff\xd8") else None
    if mime is None:raise ValueError("Elige una imagen PNG o JPG")
    w=min(280,max(40,imagen.width()))
    return {"name":Path(nombre).name,"data":"data:"+mime+";base64,"+base64.b64encode(datos).decode("ascii"),
            "width":w,"height":w*imagen.height()/imagen.width()}


def editar_texto(n, padre=None):
    d = QDialog(padre)
    aplicar_escala_dialogo(d)
    d.setWindowTitle("Editar texto")
    d.resize(540, 360)
    layout = QVBoxLayout(d)
    texto = QPlainTextEdit(n.get("text", ""))
    layout.addWidget(texto, 1)
    form = QFormLayout()
    fuente = QFontComboBox()
    fuente.setCurrentFont(QFont(n.get("font", "Arial")))
    tam = QSpinBox()
    tam.setRange(1, 1024)
    tam.setValue(round(n.get("size", 18)))
    tam.setToolTip("Tamaño del texto en píxeles")
    color = QPushButton()
    color.setAutoDefault(False)
    color.setAccessibleName("Elegir color del texto")
    muestra = QFrame()
    muestra.setObjectName("muestraColorTexto")
    muestra.setFixedSize(estilo.E6, estilo.E6)
    fila_color = QHBoxLayout()
    fila_color.setSpacing(estilo.E2)
    fila_color.addWidget(muestra)
    fila_color.addWidget(color)
    fila_color.addStretch()
    elegido = [n.get("color", "#172e4d")]

    def actualizar():
        letra = fuente.currentFont()
        letra.setPixelSize(tam.value())
        texto.setFont(letra)
        texto.setStyleSheet("color:" + elegido[0])
        color.setText(elegido[0])
        muestra.setStyleSheet(
            f"background:{elegido[0]}; border:1px solid {estilo.BORDE_CONTROL}; border-radius:{estilo.R_S}px"
        )

    def elegir():
        nuevo_color = QColorDialog.getColor(QColor(elegido[0]), d, "Color del texto")
        if nuevo_color.isValid():
            elegido[0] = nuevo_color.name()
            actualizar()

    color.clicked.connect(elegir)
    fuente.currentFontChanged.connect(lambda _: actualizar())
    tam.valueChanged.connect(lambda _: actualizar())
    for etiqueta, widget in (("Fuente", fuente), ("Tamaño", tam), ("Color", fila_color)):
        form.addRow(etiqueta, widget)
    layout.addLayout(form)
    layout.addWidget(PieDialogo().conectar(d))
    actualizar()
    if n.get("text") == "Texto":
        texto.selectAll()
    texto.setFocus()
    if d.exec() != QDialog.DialogCode.Accepted:
        return None
    return {"text": texto.toPlainText(), "font": fuente.currentFont().family(),
            "size": tam.value(), "color": elegido[0]}


@lru_cache(maxsize=16)
def _pixmap(data):
    p=QPixmap()
    try:p.loadFromData(base64.b64decode(data.split(",",1)[1],validate=True))
    except (ValueError,IndexError):pass
    return p


def dibujar_nota(scene,n,seleccionada):
    """Una nota de texto o imagen y, si está seleccionada, su borde y su tirador; devuelve los ítems que ha creado."""
    items=[]
    r=rect(n);base=QGraphicsRectItem(r);base.setPen(QPen(Qt.PenStyle.NoPen));base.setBrush(QBrush(Qt.BrushStyle.NoBrush))
    base.setZValue(.2);base.setToolTip("Texto" if n["kind"]=="text" else n.get("name","Imagen"));scene.addItem(base);items.append(base)
    if n["kind"]=="text":
        base.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
        t=QGraphicsTextItem();scene.addItem(t);t.setParentItem(base);t.setPlainText(n.get("text",""));f=QFont(n.get("font","Arial"));f.setPixelSize(round(n.get("size",18)))
        t.setFont(f);t.setDefaultTextColor(QColor(n.get("color","#172e4d")));t.document().setDocumentMargin(0)
        t.setTextWidth(max(1,r.width()-8));t.setPos(r.left()+4,r.top()+4);items.append(t)
    else:
        pm=_pixmap(n["data"])
        if not pm.isNull():
            p=QGraphicsPixmapItem(pm,base);k=min(r.width()/pm.width(),r.height()/pm.height());p.setScale(k)
            p.setPos(r.left()+(r.width()-pm.width()*k)/2,r.top()+(r.height()-pm.height()*k)/2)
            p.setTransformationMode(Qt.TransformationMode.SmoothTransformation);items.append(p)
    if seleccionada:
        borde=scene.addRect(r,QPen(QColor("#1f6feb"),1.4,Qt.PenStyle.DashLine));borde.setZValue(10)
        h=scene.addRect(r.right()-4,r.bottom()-4,8,8,QPen(QColor("#1f6feb"),1.4),QBrush(QColor("white")))
        h.setZValue(11);h.setToolTip("Arrastra para cambiar el tamaño");items.extend((borde,h))
    return items


def dibujar(scene,M,seleccion):
    for n in M.get("annotations",[]):
        dibujar_nota(scene,n,n["id"] in seleccion)
