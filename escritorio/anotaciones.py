"""Texto e imágenes de presentación: importación, edición y dibujo, sin semántica GRAFCET."""
import base64
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPixmap, QPen, QBrush
from PySide6.QtWidgets import (QColorDialog, QDialog, QDialogButtonBox, QFileDialog,
    QFontComboBox, QFormLayout, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsTextItem, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout)


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
    if mime is None:raise ValueError("Elija una imagen PNG o JPG")
    w=min(280,max(40,imagen.width()))
    return {"name":Path(nombre).name,"data":"data:"+mime+";base64,"+base64.b64encode(datos).decode("ascii"),
            "width":w,"height":w*imagen.height()/imagen.width()}


def editar_texto(n,padre=None):
    d=QDialog(padre);d.setWindowTitle("Editar texto");d.resize(540,360)
    l=QVBoxLayout(d);texto=QPlainTextEdit(n.get("text",""));l.addWidget(texto,1)
    f=QFormLayout();fuente=QFontComboBox();fuente.setCurrentFont(QFont(n.get("font","Arial")))
    tam=QSpinBox();tam.setRange(1,1024);tam.setValue(round(n.get("size",18)))
    tam.setToolTip("Tamaño del texto en píxeles")
    color=QPushButton();elegido=[n.get("color","#172e4d")]
    def actualizar():
        ff=fuente.currentFont();ff.setPixelSize(tam.value());texto.setFont(ff)
        texto.setStyleSheet("color:"+elegido[0]);color.setText(elegido[0]);color.setStyleSheet("color:"+elegido[0])
    def elegir():
        c=QColorDialog.getColor(QColor(elegido[0]),d,"Color del texto")
        if c.isValid():elegido[0]=c.name();actualizar()
    color.clicked.connect(elegir);fuente.currentFontChanged.connect(lambda _:actualizar());tam.valueChanged.connect(lambda _:actualizar())
    for etiqueta,w in (("Fuente",fuente),("Tamaño",tam),("Color",color)):f.addRow(etiqueta,w)
    l.addLayout(f);botones=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    botones.accepted.connect(d.accept);botones.rejected.connect(d.reject);l.addWidget(botones);actualizar()
    if d.exec()!=QDialog.DialogCode.Accepted:return None
    return {"text":texto.toPlainText(),"font":fuente.currentFont().family(),"size":tam.value(),"color":elegido[0]}


@lru_cache(maxsize=16)
def _pixmap(data):
    p=QPixmap()
    try:p.loadFromData(base64.b64decode(data.split(",",1)[1],validate=True))
    except (ValueError,IndexError):pass
    return p


def dibujar(scene,M,seleccion):
    for n in M.get("annotations",[]):
        r=rect(n);base=QGraphicsRectItem(r);base.setPen(QPen(Qt.PenStyle.NoPen));base.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        base.setZValue(.2);base.setToolTip("Texto" if n["kind"]=="text" else n.get("name","Imagen"));scene.addItem(base)
        if n["kind"]=="text":
            base.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
            t=QGraphicsTextItem();scene.addItem(t);t.setParentItem(base);t.setPlainText(n.get("text",""));f=QFont(n.get("font","Arial"));f.setPixelSize(round(n.get("size",18)))
            t.setFont(f);t.setDefaultTextColor(QColor(n.get("color","#172e4d")));t.document().setDocumentMargin(0)
            t.setTextWidth(max(1,r.width()-8));t.setPos(r.left()+4,r.top()+4)
        else:
            pm=_pixmap(n["data"])
            if not pm.isNull():
                p=QGraphicsPixmapItem(pm,base);k=min(r.width()/pm.width(),r.height()/pm.height());p.setScale(k)
                p.setPos(r.left()+(r.width()-pm.width()*k)/2,r.top()+(r.height()-pm.height()*k)/2)
                p.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        if n["id"] in seleccion:
            borde=scene.addRect(r,QPen(QColor("#1f6feb"),1.4,Qt.PenStyle.DashLine));borde.setZValue(10)
            h=scene.addRect(r.right()-4,r.bottom()-4,8,8,QPen(QColor("#1f6feb"),1.4),QBrush(QColor("white")))
            h.setZValue(11);h.setToolTip("Arrastre para cambiar el tamaño")
