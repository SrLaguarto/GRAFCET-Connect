"""Dibujo en milímetros y edición de textos y zona útil de una plantilla incorporada."""
import base64
import copy
from PySide6.QtCore import Qt,QRectF,QPointF,Signal
from PySide6.QtGui import QPainter,QPen,QColor,QFont,QFontMetricsF,QTextLayout,QTextOption,QPainterPath,QImage,QTransform
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QPushButton,QLabel,
    QPlainTextEdit,QLineEdit,QComboBox,QDoubleSpinBox,QListWidget,QGraphicsView,QGraphicsScene,QGraphicsItem,
    QDialogButtonBox,QWidget,QScrollArea,QFontComboBox,QMessageBox,QColorDialog)
from grafcet.laminas import CAMPOS
from grafcet.plantillas import validar_plantilla

ROTULOS={'titulo':'Título','proyecto':'Proyecto','autor':'Autor','centro':'Centro o empresa',
         'fecha':'Fecha','revision':'Revisión','escala':'Escala','hoja':'Hoja','libre':'Campo libre','comprobado':'Comprobado por','fecha_comprobado':'Fecha de comprobación','firma_autor':'Firma dibujado','firma_comprobado':'Firma comprobado','numero':'Número','sustituye':'Sustituye a','sustituido_por':'Sustituido por'}


def valor_texto(t,campos):
    valor=campos.get(t.get('field'),t['text']) if t.get('field') else t['text']
    if not valor and t.get('omit_empty'):return ''
    return t.get('prefix','')+valor+t.get('suffix','')


def layout_texto(t,valor):
    font=QFont(t.get('font','Arial'));font.setPixelSize(1000)
    metricas=QFontMetricsF(font);s=t['height']/max(1,metricas.capHeight())
    layout=QTextLayout(valor,font);op=QTextOption();op.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(op);layout.beginLayout();lineas=[];y=0;ancho=0
    # QTextLayout entiende saltos Unicode, no los \n de MTEXT.
    if '\n' in valor:
        layout.endLayout();layout=QTextLayout(valor.replace('\n','\u2028'),font);layout.setTextOption(op);layout.beginLayout()
    while True:
        li=layout.createLine()
        if not li.isValid():break
        li.setLineWidth(t['width']/s if t.get('width') and not t.get('fit') else 1e7)
        if t.get('max_height') and y+li.height()>t['max_height']/s:break
        li.setPosition(QPointF(0,y));lineas.append(li);ancho=max(ancho,li.naturalTextWidth());y+=li.height()
    layout.endLayout()
    stretch=t.get('stretch',1.)
    if t.get('fit') and ancho>0:
        ratio=t['width']/(ancho*s*stretch)
        if t['fit']=='aligned':s*=ratio
        else:stretch*=ratio
        ancho=ancho*s
    else:ancho=t.get('width',ancho*s)
    # Anclar la caja visible de las letras, no el espacio de interlínea de Qt.
    superior=(lineas[0].ascent()-metricas.capHeight())*s if lineas else 0
    alto=((lineas[-1].y()+lineas[-1].ascent())*s-superior) if lineas else 0
    x={'left':0,'center':-ancho/2,'right':-ancho}[t.get('align','left')]
    tipo=t.get('valign','baseline');v={'top':-superior,'middle':-alto/2-superior,'bottom':-alto-superior,'baseline':-metricas.ascent()*s}[tipo]
    return layout,font,s,QRectF(x*stretch,v,ancho*stretch,alto),x,v,lineas,stretch


def pintar_texto(p,t,valor):
    layout,font,s,rect,x,y,lineas,stretch=layout_texto(t,valor)
    p.save();p.translate(t['x'],t['y']);p.rotate(t['rotation']);p.scale(-1 if t.get('mirror_x') else 1,-1 if t.get('mirror_y') else 1);p.scale(stretch,1)
    p.translate(x,y);p.scale(s,s);p.setFont(font);p.setPen(QColor(t.get('color','#000000')))
    for li in lineas:
        desplazamiento=(rect.width()/stretch/s-li.naturalTextWidth())*{'left':0,'center':.5,'right':1}[t.get('align','left')]
        li.draw(p,QPointF(desplazamiento,0))
    p.restore()


class FondoPlantilla:
    def __init__(self,plantilla):
        self.p=plantilla;self.imagen=None;self.svg=None
        fondo=plantilla.get('background')
        if fondo:
            try:datos=base64.b64decode(fondo['data'],validate=True)
            except ValueError as exc:raise ValueError('Fondo de plantilla dañado') from exc
            if fondo['kind']=='png':
                self.imagen=QImage.fromData(datos,'PNG')
                if self.imagen.isNull():raise ValueError('Imagen de plantilla no válida')
            else:
                self.svg=QSvgRenderer(datos)
                if not self.svg.isValid():raise ValueError('SVG de plantilla no válido')
    def pintar(self,p,campos,textos=True):
        w,h=self.p['size'];r=QRectF(0,0,w,h)
        if self.imagen is not None:p.drawImage(r,self.imagen)
        if self.svg is not None:self.svg.render(p,r)
        for t in self.p['primitives']:
            if t['kind']=='text':
                if textos:pintar_texto(p,t,valor_texto(t,campos))
                continue
            p.setPen(QPen(QColor(t.get('color','#000000')),t.get('weight',.25)));p.setBrush(Qt.BrushStyle.NoBrush)
            if t['kind']=='line':a,b,c,d=t['points'];p.drawLine(QPointF(a,b),QPointF(c,d))
            elif t['kind']=='arc':
                x,y=t['center'];r=t['radius'];p.drawArc(QRectF(x-r,y-r,2*r,2*r),round(t['start']*16),round(t['span']*16))
            else:
                pts=t['points'];trazo=QPainterPath(QPointF(*pts[0]))
                for v in pts[1:]:trazo.lineTo(QPointF(*v))
                p.drawPath(trazo)


class _FondoItem(QGraphicsItem):
    def __init__(self,fondo,campos):super().__init__();self.fondo=fondo;self.campos=campos;self.setZValue(-10)
    def boundingRect(self):return QRectF(0,0,*self.fondo.p['size'])
    def paint(self,p,*args):p.fillRect(self.boundingRect(),QColor('white'));self.fondo.pintar(p,self.campos,False)


class TextoPlantilla(QGraphicsItem):
    def __init__(self,t,campos,soltar):
        super().__init__();self.t=t;self.campos=campos;self.soltar=soltar;self.setZValue(1)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.sincronizar()
    def sincronizar(self):
        self.prepareGeometryChange();self.setPos(self.t['x'],self.t['y']);self.setRotation(self.t['rotation']);self.update()
    def boundingRect(self):
        r=layout_texto(self.t,valor_texto(self.t,self.campos))[3]
        if self.t.get('mirror_x'):r=QRectF(-r.right(),r.top(),r.width(),r.height())
        if self.t.get('mirror_y'):r=QRectF(r.left(),-r.bottom(),r.width(),r.height())
        return r.adjusted(-.3,-.3,.3,.3)
    def paint(self,p,*args):
        t={**self.t,'x':0,'y':0,'rotation':0};pintar_texto(p,t,valor_texto(t,self.campos))
        if self.isSelected():p.setPen(QPen(QColor('#326dcb'),.25,Qt.PenStyle.DashLine));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRect(self.boundingRect())
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event);self.t.update(x=self.pos().x(),y=self.pos().y());self.soltar()


class VistaPlantilla(QGraphicsView):
    def __init__(self,escena,cambiar):
        super().__init__(escena);self.zona=False;self.inicio=None;self.rectangulo=None;self.cambiar=cambiar
        self.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing)
        self.setBackgroundBrush(QColor('#dcebe7'));self.setMinimumSize(430,300)
    def resizeEvent(self,event):super().resizeEvent(event);self.fitInView(self.sceneRect().adjusted(-4,-4,4,4),Qt.AspectRatioMode.KeepAspectRatio)
    def mousePressEvent(self,event):
        if self.zona and event.button()==Qt.MouseButton.LeftButton:
            self.inicio=self.mapToScene(event.position().toPoint());self.rectangulo=self.scene().addRect(QRectF(self.inicio,self.inicio),QPen(QColor('#326dcb'),.4));self.rectangulo.setZValue(20);return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.inicio is not None:self.rectangulo.setRect(QRectF(self.inicio,self.mapToScene(event.position().toPoint())).normalized());return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self.inicio is not None:
            r=self.rectangulo.rect().intersected(self.sceneRect());self.scene().removeItem(self.rectangulo);self.rectangulo=None;self.inicio=None
            if r.width()>=5 and r.height()>=5:self.cambiar(list(r.getRect()))
            return
        super().mouseReleaseEvent(event)


class EditorPlantilla(QDialog):
    modificado=Signal()
    seleccionado=Signal()
    def __init__(self,plantilla,campos,parent=None,solo_texto=False):
        super().__init__(parent);self.setWindowTitle('Editar plantilla · textos y zona de dibujo');self.resize(1280,740)
        self.plantilla=validar_plantilla(plantilla);self.campos=dict(campos);self.ocupado=False;self.actual=None;self.color_actual='#000000';self.solo_texto=solo_texto
        raiz=QHBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFixedWidth(330)
        panel=QWidget();form=QFormLayout(panel);scroll.setWidget(panel);raiz.addWidget(scroll)
        self.lista=QListWidget();self.lista.setMaximumHeight(140);form.addRow('Textos de la plantilla',self.lista)
        botones=QHBoxLayout();self.nuevo=QPushButton('Añadir texto');self.borrar=QPushButton('Eliminar')
        botones.addWidget(self.nuevo);botones.addWidget(self.borrar);form.addRow(botones)
        self.contenido=QPlainTextEdit();self.contenido.setMaximumHeight(65);self.enlace=QComboBox();self.enlace.addItem('Texto fijo','')
        for k in CAMPOS:self.enlace.addItem(ROTULOS[k],k)
        for t in self.plantilla['primitives']:
            f=t.get('field','')
            if f and self.enlace.findData(f)<0:self.enlace.addItem('Campo '+f.removeprefix('@'),f)
        self.sugerencia=QPushButton();form.addRow('Contenido',self.contenido);form.addRow('Enlazado a',self.enlace);form.addRow(self.sugerencia)
        if solo_texto:self.enlace.hide();form.labelForField(self.enlace).hide()
        self.fuente=QFontComboBox();form.addRow('Fuente',self.fuente)
        self.color=QPushButton('Color del texto');form.addRow(self.color);self.color.clicked.connect(self.elegir_color)
        self.x=self.spin(-2000,4000);self.y=self.spin(-2000,4000);self.altura=self.spin(.05,500)
        self.alineacion=QComboBox()
        for texto,dato in (('Izquierda','left'),('Centro','center'),('Derecha','right')):self.alineacion.addItem(texto,dato)
        self.vertical=QComboBox()
        for texto,dato in (('Arriba','top'),('Centro','middle'),('Abajo','bottom'),('Línea base','baseline')):self.vertical.addItem(texto,dato)
        self.giro=QComboBox();self.giro.addItem('0°',0.);self.giro.addItem('90°',90.)
        for label,w in (('X (mm)',self.x),('Y (mm)',self.y),('Altura (mm)',self.altura),('Alineación',self.alineacion),('Anclaje vertical',self.vertical),('Giro',self.giro)):form.addRow(label,w)
        self.b_zona=QPushButton('Marcar zona de dibujo');self.b_zona.setCheckable(True);form.addRow(self.b_zona)
        self.zona_label=QLabel();self.zona_label.setWordWrap(True);form.addRow(self.zona_label)
        self.restar_zona=QPushButton('Usar zona automática');form.addRow(self.restar_zona)
        self.info=QLabel('Arrastra los textos para moverlos.' if solo_texto else 'Arrastra los textos para moverlos. Los enlaces propuestos solo se aplican al aceptarlos.');self.info.setWordWrap(True);form.addRow(self.info)
        self.botones_dialogo=aceptar=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);aceptar.button(QDialogButtonBox.StandardButton.Ok).setText('Aceptar');aceptar.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar');form.addRow(aceptar)
        self.escena=QGraphicsScene();self.escena.setSceneRect(QRectF(0,0,*self.plantilla['size']))
        self.fondo=FondoPlantilla(self.plantilla);self.base=_FondoItem(self.fondo,self.campos);self.escena.addItem(self.base)
        self.vista=VistaPlantilla(self.escena,self.poner_zona);raiz.addWidget(self.vista,1);self.items=[];self.zona_item=None
        self.lista.currentRowChanged.connect(self.elegir);self.escena.selectionChanged.connect(self.desde_escena)
        self.nuevo.clicked.connect(self.anadir);self.borrar.clicked.connect(self.eliminar);self.sugerencia.clicked.connect(self.aceptar_sugerencia)
        self.contenido.textChanged.connect(self.editar)
        for w in (self.x,self.y,self.altura):w.valueChanged.connect(self.editar)
        for w in (self.enlace,self.alineacion,self.vertical,self.giro):w.currentIndexChanged.connect(self.editar)
        self.fuente.currentFontChanged.connect(self.editar)
        self.b_zona.toggled.connect(lambda on:setattr(self.vista,'zona',on));self.restar_zona.clicked.connect(lambda:self.poner_zona(None))
        aceptar.accepted.connect(self.accept);aceptar.rejected.connect(self.reject);self.rellenar();self.mostrar_zona()
    def elegir_color(self):
        color=QColorDialog.getColor(QColor(self.color_actual),self,'Color del texto')
        if color.isValid():self.color_actual=color.name();self.color.setStyleSheet('color:'+self.color_actual);self.editar()

    def spin(self,a,b):
        w=QDoubleSpinBox();w.setDecimals(3);w.setRange(a,b);return w
    def rellenar(self):
        self.ocupado=True;self.lista.clear()
        for item in self.items:self.escena.removeItem(item)
        self.items=[]
        for t in self.plantilla['primitives']:
            if t['kind']!='text':continue
            item=TextoPlantilla(t,self.campos,self.movido);self.escena.addItem(item);self.items.append(item)
            self.lista.addItem(('↔ ' if t.get('field') else '')+valor_texto(t,self.campos).replace('\n',' ')[:70])
        self.ocupado=False;self.lista.setCurrentRow(0 if self.items else -1);self.elegir(self.lista.currentRow())
    def elegir(self,n):
        if self.ocupado:return
        self.ocupado=True;self.actual=self.items[n] if 0<=n<len(self.items) else None
        for item in self.items:item.setSelected(item is self.actual)
        habilitado=self.actual is not None
        for w in (self.contenido,self.enlace,self.x,self.y,self.altura,self.alineacion,self.vertical,self.giro,self.fuente,self.borrar,self.color):w.setEnabled(habilitado)
        if self.actual:
            t=self.actual.t;self.color_actual=t.get('color','#000000');self.color.setStyleSheet('color:'+self.color_actual);f=t.get('field','');self.contenido.setPlainText(self.campos.get(f,t['text']) if f.startswith('@') else t['text'])
            self.contenido.setEnabled(self.solo_texto or not f or f.startswith('@'));
            if self.solo_texto:self.contenido.setPlainText(valor_texto(t,self.campos))
            self.enlace.setCurrentIndex(max(0,self.enlace.findData(f)))
            self.x.setValue(t['x']);self.y.setValue(t['y']);self.altura.setValue(t['height'])
            self.alineacion.setCurrentIndex(self.alineacion.findData(t.get('align','left')));self.vertical.setCurrentIndex(self.vertical.findData(t.get('valign','baseline')))
            if self.giro.findData(t['rotation'])<0:self.giro.addItem(f"Importado ({t['rotation']:.2f}°)",t['rotation'])
            self.giro.setCurrentIndex(self.giro.findData(t['rotation']));self.fuente.setCurrentFont(QFont(t.get('font','Arial')))
            propuesta=t.get('suggest');self.sugerencia.setVisible(bool(propuesta and not f and not self.solo_texto));self.sugerencia.setText('Enlazar a '+ROTULOS.get(propuesta,str(propuesta)))
        else:self.sugerencia.hide()
        self.ocupado=False;self.seleccionado.emit()
    def desde_escena(self):
        if self.ocupado:return
        seleccionado=next((i for i in self.items if i.isSelected()),None)
        if seleccionado:self.lista.setCurrentRow(self.items.index(seleccionado))
    def movido(self):
        if self.actual:self.elegir(self.items.index(self.actual));self.modificado.emit()
    def editar(self,*args):
        if self.ocupado or not self.actual:return
        t=self.actual.t;f=self.enlace.currentData();cambio=f!=t.get('field','')
        if self.solo_texto:
            f='';cambio=bool(t.get('field'));t['text']=self.contenido.toPlainText();t.pop('prefix',None);t.pop('suffix',None);t.pop('suggest',None);t.pop('omit_empty',None)
        elif cambio and not f:t['text']=valor_texto(t,self.campos);t.pop('prefix',None);t.pop('suffix',None)
        elif not f or f.startswith('@'):t['text']=self.contenido.toPlainText()
        if cambio and f==t.get('suggest') and t.get('suggest_prefix'):t['prefix']=t['suggest_prefix']
        t.update(field=f,x=self.x.value(),y=self.y.value(),height=self.altura.value(),rotation=self.giro.currentData(),align=self.alineacion.currentData(),valign=self.vertical.currentData(),font=self.fuente.currentFont().family(),color=self.color_actual)
        self.actual.sincronizar();self.lista.item(self.items.index(self.actual)).setText(('↔ ' if f else '')+valor_texto(t,self.campos).replace('\n',' ')[:70])
        if cambio:self.elegir(self.items.index(self.actual))
        self.modificado.emit()
    def anadir(self):
        self.plantilla['primitives'].append({'kind':'text','text':'Texto','x':20.,'y':20.,'height':3.,'rotation':0.,'align':'left','valign':'top','font':'Arial','color':'#000000'})
        self.rellenar();self.lista.setCurrentRow(len(self.items)-1);self.modificado.emit()
    def eliminar(self):
        if self.actual:self.plantilla['primitives'].remove(self.actual.t);self.actual=None;self.rellenar();self.modificado.emit()
    def aceptar_sugerencia(self):
        if self.actual and self.actual.t.get('suggest'):self.enlace.setCurrentIndex(self.enlace.findData(self.actual.t['suggest']))
    def poner_zona(self,rect):self.plantilla['zone']=rect;self.b_zona.setChecked(False);self.mostrar_zona();self.modificado.emit()
    def mostrar_zona(self):
        if self.zona_item:self.escena.removeItem(self.zona_item);self.zona_item=None
        r=self.plantilla.get('zone') or self.plantilla.get('detected_zone')
        if r:
            self.zona_item=self.escena.addRect(QRectF(*r),QPen(QColor('#326dcb'),.3,Qt.PenStyle.DashLine));self.zona_item.setZValue(.5)
        self.zona_label.setText(('Zona marcada: ' if self.plantilla.get('zone') else 'Zona automática: ')+(', '.join(f'{v:.1f}' for v in r)+' mm' if r else 'hoja con márgenes'))
    def accept(self):
        try:self.plantilla=validar_plantilla(self.plantilla)
        except ValueError as exc:QMessageBox.warning(self,'Plantilla',str(exc));return
        super().accept()
