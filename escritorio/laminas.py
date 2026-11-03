"""Láminas: una misma composición vectorial para vista previa, PDF, SVG e impresión."""
from __future__ import annotations
import copy
import math
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
from PySide6.QtCore import Qt,QRectF,QRect,QSize,QSizeF,QMarginsF,QPointF,QByteArray,QBuffer,QIODevice,Signal
from PySide6.QtGui import (QPainter,QPen,QColor,QFont,QPdfWriter,QPageSize,QPageLayout,QTextLayout,QTextOption)
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter,QPrintDialog
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QScrollArea,
    QComboBox,QDoubleSpinBox,QLineEdit,QCheckBox,QPushButton,QLabel,QFileDialog,QMessageBox,
    QMenuBar,QInputDialog,QStackedWidget,QDialogButtonBox,QSizePolicy,QGraphicsScene,QGraphicsTextItem,QGraphicsRectItem,QGraphicsPathItem,QGraphicsPixmapItem)
from grafcet.laminas import FORMATOS,CAMPOS,ajustes_lamina
from .diagrama import dibujar,Z_EDIT,Z_STEP

ROTULOS={'titulo':'Título','proyecto':'Proyecto','autor':'Autor','centro':'Centro o empresa','fecha':'Fecha',
         'revision':'Revisión','escala':'Escala','hoja':'Hoja','libre':'Campo libre','comprobado':'Comprobado por','fecha_comprobado':'Fecha de comprobación','firma_autor':'Firma dibujado','firma_comprobado':'Firma comprobado','numero':'Número','sustituye':'Sustituye a','sustituido_por':'Sustituido por'}


def _texto(p,r,texto,tamano=2.5,negrita=False,centrado=False):
    p.save();p.translate(r.topLeft());p.scale(.1,.1)
    f=QFont('Arial');f.setPixelSize(round(tamano*10));f.setBold(negrita);p.setFont(f)
    p.setPen(QColor('#172e4d'))
    # Dibujar solo las líneas que caben: el generador SVG ignora el clip de QPainter.
    layout=QTextLayout(str(texto),f);opciones=QTextOption()
    opciones.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    opciones.setAlignment(Qt.AlignmentFlag.AlignHCenter if centrado else Qt.AlignmentFlag.AlignLeft)
    layout.setTextOption(opciones);layout.beginLayout();lineas=[];y=0
    while True:
        linea=layout.createLine()
        if not linea.isValid():break
        linea.setLineWidth(r.width()*10)
        if y+linea.height()>r.height()*10:break
        linea.setPosition(QPointF(0,y));lineas.append(linea);y+=linea.height()
    layout.endLayout()
    origen=QPointF(0,(r.height()*10-y)/2)
    for linea in lineas:linea.draw(p,origen)
    p.restore()



def _letra(n):
    out=''
    while n>=0:out=chr(65+n%26)+out;n=n//26-1
    return out


def _tramos(inicio,fin,capacidad,protegidos):
    out=[];x=inicio
    while x<fin-1e-6:
        z=min(x+capacidad,fin)
        if z<fin-1e-6:
            while True:
                cortados=[a-2 for a,b in protegidos if a-1e-6<z<b+1e-6]
                if not cortados:break
                z=min(cortados)
            if z<=x+1e-6:
                raise ValueError('Un símbolo o texto no cabe a esta escala sin cortarlo. Reduce la escala o elige una hoja mayor.')
        out.append((x,z));x=z
        if len(out)>400:raise ValueError('Demasiadas hojas: reduce la escala.')
    return out


class DocumentoLaminas:
    def __init__(self,modelo,estado,ajustes,dependencias=False):
        self.ajustes=ajustes_lamina(ajustes);self.modelo=copy.deepcopy(modelo)
        self.estado=copy.deepcopy(estado) if self.ajustes['con_estado'] else {}
        self.escena=QGraphicsScene();dibujar(self.escena,self.modelo,self.estado,dependencias=dependencias)
        for item in list(self.escena.items()):
            if item.zValue()>=Z_EDIT:self.escena.removeItem(item)
        limites=self.escena.itemsBoundingRect()
        self.limites=limites.adjusted(-4,-4,4,4) if not limites.isEmpty() else QRectF(0,0,1,1)
        plantilla=self.ajustes['plantilla']
        if plantilla:w,h=plantilla['size']
        else:
            from grafcet.plantillas_tecnicas import plantilla_tecnica
            w,h=FORMATOS[self.ajustes['formato']]
            if self.ajustes['orientacion']=='horizontal':w,h=h,w
            plantilla=plantilla_tecnica(w,h,self.ajustes['margen_mm'])
        from .plantillas import FondoPlantilla
        self.plantilla=FondoPlantilla(plantilla)
        self.ancho,self.alto=w,h;m=self.ajustes['margen_mm']
        self.marco=QRectF(*plantilla.get('inner_frame',[m,m,w-2*m,h-2*m]))
        zona=plantilla.get('zone') or plantilla.get('detected_zone')
        self.exclusiones=[QRectF(*plantilla['title_box'])] if plantilla.get('title_box') and ajustes.get('_interior_completo') else []
        self.contenido=QRectF(*zona) if zona else self.marco.adjusted(2,2,-2,-2)
        if not ajustes.get('_interior_completo') and not plantilla.get('zone') and plantilla.get('title_box'):self.contenido.setBottom(float(plantilla['title_box'][1])-2)
        if self.contenido.width()<=0 or self.contenido.height()<=0:raise ValueError('Los márgenes no dejan espacio para el dibujo')
        if self.ajustes['modo']=='ajustar':
            self.factor=min(self.contenido.width()/self.limites.width(),self.contenido.height()/self.limites.height())
            self.xs=[(self.limites.left(),self.limites.right())];self.ys=[(self.limites.top(),self.limites.bottom())]
        else:
            unidad=self.ajustes['unidad_mm']
            if unidad is None:raise ValueError('Elige la referencia física para la escala fija')
            self.factor=unidad/self.ajustes['escala']
            protegidos=[]
            for item in self.escena.items():
                if isinstance(item,(QGraphicsTextItem,QGraphicsPixmapItem)) or (isinstance(item,(QGraphicsRectItem,QGraphicsPathItem)) and (item.zValue()>=Z_STEP-.1 or item.zValue()==.2)):
                    r=item.sceneBoundingRect()
                    if not r.isEmpty():protegidos.append(r)
            self.xs=_tramos(self.limites.left(),self.limites.right(),self.contenido.width()/self.factor,[(r.left(),r.right()) for r in protegidos])
            self.ys=_tramos(self.limites.top(),self.limites.bottom(),self.contenido.height()/self.factor,[(r.top(),r.bottom()) for r in protegidos])
        self.total=len(self.xs)*len(self.ys)
        if self.total>400:raise ValueError('El dibujo requiere más de 400 hojas; reduce la escala')
        for i in range(self.total):self.destino(i)

    @property
    def escala_rotulo(self):
        if self.ajustes['campos']['escala']:return self.ajustes['campos']['escala']
        if self.ajustes['modo']=='ajustar':return 'Ajuste a hoja'
        return ('1:'+format(self.ajustes['escala'],'.6g')).replace('.',',')

    def fuente(self,indice):
        y,x=divmod(indice,len(self.xs));a,b=self.xs[x];c,d=self.ys[y]
        return QRectF(a,c,b-a,d-c)

    def destino(self,indice):
        fuente=self.fuente(indice)
        r=QRectF(self.contenido.topLeft(),fuente.size()*self.factor)
        if self.ajustes['modo']=='ajustar':r.moveCenter(self.contenido.center())
        r.translate(*self.ajustes['offset_mm'])
        if not self.posicion_valida(r):raise ValueError('El GRAFCET no cabe en esa posición: debe quedar dentro del marco o zona de dibujo, sin ocupar el cajetín')
        return r

    def posicion_valida(self,rect):
        return self.contenido.adjusted(-.001,-.001,.001,.001).contains(rect) and not any(r.intersects(rect) for r in self.exclusiones)

    def ajustar_posicion(self,rect,anterior):
        if self.posicion_valida(rect):return rect
        candidatos=[]
        for caja in self.exclusiones:
            for borde,valor in (('moveRight',caja.left()),('moveLeft',caja.right()),('moveBottom',caja.top()),('moveTop',caja.bottom())):
                r=QRectF(rect);getattr(r,borde)(valor)
                if self.posicion_valida(r):candidatos.append(r)
        return min(candidatos,key=lambda r:(r.center()-rect.center()).manhattanLength()) if candidatos else anterior

    def _dibujo(self,p,indice):
        destino=self.destino(indice)
        p.save();p.setClipRect(destino)
        self.escena.render(p,destino,self.fuente(indice),Qt.AspectRatioMode.IgnoreAspectRatio)
        p.restore()

    def campos(self,indice):
        campos=dict(self.ajustes['campos']);campos['escala']=self.escala_rotulo
        campos['hoja']=campos['hoja'].replace('{n}',str(indice+1)).replace('{m}',str(self.total))
        return campos

    def _fondo_plantilla(self,p,indice):
        if self.plantilla:self.plantilla.pintar(p,self.campos(indice))

    def _decoracion(self,p,indice):
        if self.estado and self.plantilla.p.get('source')=='GrafConnect':
            _texto(p,QRectF(self.contenido.left(),self.contenido.bottom(),self.contenido.width(),2),f"Estado de simulación · t = {self.estado.get('time','')}",1.5)
        if self.total>1:self._continuaciones(p,indice)

    def pintar(self,p,indice):
        if not 0<=indice<self.total:raise IndexError('Hoja inexistente')
        p.save();p.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing|QPainter.RenderHint.SmoothPixmapTransform)
        p.setClipRect(QRectF(0,0,self.ancho,self.alto),Qt.ClipOperation.IntersectClip)
        p.fillRect(QRectF(0,0,self.ancho,self.alto),QColor('white'))
        self._fondo_plantilla(p,indice);self._dibujo(p,indice);self._decoracion(p,indice)
        p.restore()

    def _continuaciones(self,p,indice):
        fila,col=divmod(indice,len(self.xs));r=self.contenido
        vecinos=[]
        if col:vecinos.append((QRectF(r.left()-8,r.center().y()-5,8,10),'← '+str(indice)))
        if col+1<len(self.xs):vecinos.append((QRectF(r.right(),r.center().y()-5,8,10),str(indice+2)+' →'))
        if fila:vecinos.append((QRectF(r.center().x()-8,r.top()-4,16,4),'↑ '+str(indice-len(self.xs)+1)))
        if fila+1<len(self.ys):vecinos.append((QRectF(r.center().x()-8,r.bottom(),16,4),'↓ '+str(indice+len(self.xs)+1)))
        for caja,texto in vecinos:
            p.fillRect(caja,QColor('white'));_texto(p,caja,texto,2.5,True,True)

    def layout(self):
        tamanio=QPageSize(QSizeF(min(self.ancho,self.alto),max(self.ancho,self.alto)),QPageSize.Unit.Millimeter,
                         self.ajustes['formato'],QPageSize.SizeMatchPolicy.ExactMatch)
        orientacion=QPageLayout.Orientation.Landscape if self.ancho>=self.alto else QPageLayout.Orientation.Portrait
        return QPageLayout(tamanio,orientacion,QMarginsF(0,0,0,0),QPageLayout.Unit.Millimeter)

    def pintar_dispositivo(self,dispositivo,indices=None):
        p=QPainter()
        if not p.begin(dispositivo):raise OSError('No se pudo iniciar la salida de la lámina')
        try:
            for n,i in enumerate(range(self.total) if indices is None else indices):
                if n and not dispositivo.newPage():raise OSError('No se pudo crear una nueva hoja')
                p.save();p.scale(dispositivo.logicalDpiX()/25.4,dispositivo.logicalDpiY()/25.4);self.pintar(p,i);p.restore()
        finally:p.end()

    def _atomico(self,ruta,escribir):
        ruta=Path(ruta);ruta.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.lamina-',suffix=ruta.suffix,dir=ruta.parent);os.close(fd)
        try:escribir(tmp);os.replace(tmp,ruta)
        finally:Path(tmp).unlink(missing_ok=True)

    def exportar_pdf(self,ruta):
        def escribir(tmp):
            writer=QPdfWriter(tmp);writer.setResolution(300);writer.setPageLayout(self.layout())
            writer.setTitle(self.ajustes['campos']['titulo']);writer.setCreator('GrafConnect')
            self.pintar_dispositivo(writer)
            del writer
        self._atomico(ruta,escribir)
        return [Path(ruta)]

    def rutas_svg(self,ruta):
        ruta=Path(ruta)
        return [ruta] if self.total==1 else [ruta.with_name(f'{ruta.stem}_hoja_{i+1:03d}.svg') for i in range(self.total)]

    def _svg(self,indice,dibujar):
        datos=QByteArray();buffer=QBuffer(datos);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        g=QSvgGenerator();g.setOutputDevice(buffer);g.setResolution(254)
        g.setSize(QSize(round(self.ancho*10),round(self.alto*10)))
        g.setViewBox(QRect(0,0,round(self.ancho*10),round(self.alto*10)))
        g.setTitle(self.ajustes['campos']['titulo']);g.setDescription(f'Lámina {indice+1} de {self.total}')
        p=QPainter(g)
        try:
            p.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing|QPainter.RenderHint.SmoothPixmapTransform)
            p.scale(10,10);dibujar(p,indice)
        finally:p.end()
        buffer.close()
        return ET.fromstring(bytes(datos))

    def exportar_svg(self,ruta):
        # QSvgGenerator no conserva el clip de QPainter. Se añade el recorte SVG
        # al dibujo vectorial para que los enlaces del mosaico no invadan el marco.
        ns='http://www.w3.org/2000/svg';ET.register_namespace('',ns)
        ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
        rutas=self.rutas_svg(ruta)
        for i,destino in enumerate(rutas):
            raiz=self._svg(i,self._decoracion);raiz.set('version','1.1');raiz.attrib.pop('baseProfile',None)
            decoracion=[e for e in raiz if e.tag not in {f'{{{ns}}}defs',f'{{{ns}}}title',f'{{{ns}}}desc'}]
            for e in decoracion:raiz.remove(e)
            defs=raiz.find(f'{{{ns}}}defs')
            clip=ET.SubElement(defs,f'{{{ns}}}clipPath',id='zona-dibujo',clipPathUnits='userSpaceOnUse')
            r=self.destino(i)
            ET.SubElement(clip,f'{{{ns}}}rect',x=str(r.x()*10),y=str(r.y()*10),width=str(r.width()*10),height=str(r.height()*10))
            ET.SubElement(raiz,f'{{{ns}}}rect',width='100%',height='100%',fill='white')
            if self.plantilla:
                fondo=self._svg(i,self._fondo_plantilla)
                for e in fondo:
                    if e.tag not in {f'{{{ns}}}title',f'{{{ns}}}desc'}:raiz.append(e)
            grupo=ET.SubElement(raiz,f'{{{ns}}}g',{'clip-path':'url(#zona-dibujo)'})
            grafico=self._svg(i,self._dibujo)
            for e in grafico:
                if e.tag not in {f'{{{ns}}}title',f'{{{ns}}}desc'}:grupo.append(e)
            for e in decoracion:raiz.append(e)
            contenido=ET.tostring(raiz,encoding='utf-8',xml_declaration=True)
            self._atomico(destino,lambda tmp,datos=contenido:Path(tmp).write_bytes(datos))
        return rutas

    def imprimir(self,parent=None):
        printer=QPrinter(QPrinter.PrinterMode.HighResolution);printer.setFullPage(True);printer.setPageLayout(self.layout())
        printer.setDocName(self.ajustes['campos']['titulo'])
        dialogo=QPrintDialog(printer,parent);dialogo.setWindowTitle('Imprimir plano');dialogo.setMinMax(1,self.total)
        if dialogo.exec()!=QDialog.DialogCode.Accepted:return False
        if not printer.setPageLayout(self.layout()):raise ValueError('La impresora no admite el formato de la lámina')
        printer.setFullPage(True)
        desde,hasta=0,self.total
        if printer.printRange()==QPrinter.PrintRange.PageRange:desde=max(0,printer.fromPage()-1);hasta=min(self.total,printer.toPage())
        self.pintar_dispositivo(printer,range(desde,hasta));return True


class DocumentoHoja(DocumentoLaminas):
    """Una hoja física con varias selecciones vinculadas, cada una a escala propia."""
    def __init__(self,modelo,estado,ajustes,dependencias=False):
        vacio=copy.deepcopy(modelo)
        for k in ('steps','macros','partials','transitions','drafts','draftActions','annotations','links','bars'):vacio[k]=[]
        vacio.pop('_graficos',None)
        cfg=copy.deepcopy(ajustes);cfg.update(modo='escala',escala=1.,unidad_mm=25.4/96,offset_mm=[0.,0.],_interior_completo=True)
        self.numero=modelo.get('_numero_hoja',1);self.hojas=modelo.get('_total_hojas',1)
        self.capas=[]
        super().__init__(vacio,estado,cfg,dependencias)
        for g in modelo['_graficos']:
            c=copy.deepcopy(cfg);c['escala']=100/g['porcentaje'];c['offset_mm']=g['offset_mm']
            d=DocumentoLaminas(g['modelo'],estado,c,dependencias)
            if d.total!=1:raise ValueError('El GRAFCET no cabe en esta hoja. Reduce su tamaño (mínimo 50 %) o elige una hoja mayor.')
            self.capas.append(d)
        self.total=1
    @property
    def escala_rotulo(self):
        if self.ajustes['campos']['escala']:return self.ajustes['campos']['escala']
        escalas={round(1/c.ajustes['escala'],6) for c in self.capas}
        if len(escalas)>1:return 'Varias'
        if not escalas:return ''
        valor=escalas.pop()
        return (f'{valor:g}:1' if valor>=1 else f'1:{1/valor:g}').replace('.',',')
    def campos(self,indice):
        campos=super().campos(indice);campos['hoja']=self.ajustes['campos']['hoja'].replace('{n}',str(self.numero)).replace('{m}',str(self.hojas));return campos
    def destino(self,indice):
        return QRectF(self.contenido)
    def _dibujo(self,p,indice):
        for d in self.capas:d._dibujo(p,0)


class VistaLamina(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.documento=None;self.indice=0;self.setMinimumSize(260,220);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.colocar=lambda offset:None;self.arrastre=None;self.seleccionado=False;self.capa=0;self.elegir_capa=lambda i:None;self.eliminar_grafico=lambda:None;self.textos=None;self.nuevo_texto=False;self.zona=False;self.inicio_texto=None;self.inicio_zona=None
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#e5e0d8'))
        d=self.documento
        if d is None:return
        escala=min((self.width()-24)/d.ancho,(self.height()-24)/d.alto)
        p.translate((self.width()-d.ancho*escala)/2,(self.height()-d.alto*escala)/2);p.scale(escala,escala);d.pintar(p,self.indice)
        if self.textos and self.textos.actual:
            p.save();item=self.textos.actual;p.translate(item.pos());p.rotate(item.rotation());p.setPen(QPen(QColor('#326dcb'),1/escala,Qt.PenStyle.DashLine));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRect(item.boundingRect());p.restore()
        if self.zona and self.textos:
            r=self.textos.plantilla.get('zone') or self.textos.plantilla.get('detected_zone')
            if r:p.setPen(QPen(QColor('#326dcb'),1/escala,Qt.PenStyle.DashLine));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRect(QRectF(*r))
        if self.inicio_zona:
            p.setPen(QPen(QColor('#326dcb'),1/escala,Qt.PenStyle.DashLine));p.drawRect(QRectF(*self.inicio_zona).normalized())
        if self.seleccionado:
            p.setPen(QPen(QColor('#326dcb'),1/escala,Qt.PenStyle.DashLine));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRect(d.capas[self.capa].destino(0) if hasattr(d,'capas') and d.capas else d.destino(self.indice))
    def punto_hoja(self,punto):
        d=self.documento;escala=min((self.width()-24)/d.ancho,(self.height()-24)/d.alto)
        return QPointF((punto.x()-(self.width()-d.ancho*escala)/2)/escala,(punto.y()-(self.height()-d.alto*escala)/2)/escala)
    def mousePressEvent(self,event):
        d=self.documento
        if d and d.total==1 and event.button()==Qt.MouseButton.LeftButton:
            p=self.punto_hoja(event.position())
            if self.textos:
                t=self.textos
                if self.nuevo_texto:
                    t.blockSignals(True);t.anadir();t.actual.t.update(x=p.x(),y=p.y());t.actual.sincronizar();t.blockSignals(False);t.movido();self.nuevo_texto=False;self.unsetCursor();return
                if self.zona and t.b_zona.isChecked():self.inicio_zona=(p,p);return
                item=next((i for i in reversed(t.items) if i.contains(i.mapFromScene(p))),None)
                t.elegir(t.items.index(item) if item else -1)
                if item:self.inicio_texto=(p,item.t['x'],item.t['y']);self.seleccionado=False;self.update();return
            if hasattr(d,'capas'):
                self.capa=next((i for i in reversed(range(len(d.capas))) if d.capas[i].destino(0).contains(p)),-1)
                self.seleccionado=self.capa>=0
                if self.seleccionado:self.elegir_capa(self.capa)
            else:self.seleccionado=d.destino(0).contains(p)
            self.update()
            if self.seleccionado:
                capa=d.capas[self.capa] if hasattr(d,'capas') else d
                self.arrastre=(p,capa.destino(0),list(capa.ajustes['offset_mm']));self.setCursor(Qt.CursorShape.ClosedHandCursor);return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.inicio_zona:self.inicio_zona=(self.inicio_zona[0],self.punto_hoja(event.position()));self.update();return
        if self.inicio_texto:
            p,x,y=self.inicio_texto;delta=self.punto_hoja(event.position())-p;t=self.textos.actual
            t.t.update(x=x+delta.x(),y=y+delta.y());t.sincronizar();self.documento.plantilla.p=self.textos.plantilla;self.update();return
        if self.arrastre:
            p,r,offset=self.arrastre;d=self.documento
            if hasattr(d,'capas'):d=d.capas[self.capa]
            delta=self.punto_hoja(event.position())-p
            dx=max(d.contenido.left()-r.left(),min(delta.x(),d.contenido.right()-r.right()))
            dy=max(d.contenido.top()-r.top(),min(delta.y(),d.contenido.bottom()-r.bottom()))
            nuevo=d.ajustar_posicion(r.translated(dx,dy),r);delta=nuevo.topLeft()-r.topLeft()
            d.ajustes['offset_mm']=[offset[0]+delta.x(),offset[1]+delta.y()];self.update();return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self.inicio_zona:
            self.mouseMoveEvent(event);r=QRectF(*self.inicio_zona).normalized().intersected(QRectF(0,0,self.documento.ancho,self.documento.alto));self.inicio_zona=None
            if r.width()>=5 and r.height()>=5:self.textos.poner_zona(list(r.getRect()))
            self.update();return
        if self.inicio_texto:self.mouseMoveEvent(event);self.inicio_texto=None;self.textos.movido();return
        if self.arrastre:
            self.mouseMoveEvent(event);self.arrastre=None;self.unsetCursor();d=self.documento.capas[self.capa] if hasattr(self.documento,'capas') else self.documento
            self.colocar(list(d.ajustes['offset_mm']));return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if self.textos and self.textos.actual and event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace):self.textos.eliminar();return
        if self.seleccionado and event.key()==Qt.Key.Key_Delete:self.eliminar_grafico();return
        super().keyPressEvent(event)
    def sizeHint(self):return QSize(800,600)


class DialogoLaminas(QDialog):
    modificado=Signal()
    def __init__(self,modelo,estado,ajustes,aplicar,parent=None,dependencias=False,integrado=False):
        super().__init__(parent,Qt.WindowType.Widget if integrado else Qt.WindowType.Dialog);self.integrado=integrado;
        if integrado:self.setParent(parent,Qt.WindowType.Widget);self.setWindowFlags(Qt.WindowType.Widget)
        self.setWindowTitle('Láminas · vista previa');self.resize(1240,700)
        self.modelo=copy.deepcopy(modelo);self.estado=copy.deepcopy(estado);self.aplicar_callback=aplicar;self.dependencias=dependencias
        self.ajustes=ajustes_lamina(ajustes)
        if not self.ajustes['plantilla'] or self.ajustes['plantilla'].get('source')=='GrafConnect':self.ajustes['margen_mm']=10.
        from grafcet.plantillas_tecnicas import sin_rotulos_auxiliares
        self.ajustes['plantilla']=sin_rotulos_auxiliares(self.ajustes['plantilla'])
        p=self.ajustes['plantilla']
        if p and p.get('source')!='GrafConnect' and not p.get('zone') and not p.get('inner_frame'):
            from .importar_plantillas import zona_detectada
            zona_detectada(p)
        self.documento=None;self.indice=0
        self.plantilla=copy.deepcopy(self.ajustes['plantilla']);self.offset=list(self.ajustes['offset_mm']);self.aviso_biblioteca='';self.editor_textos=None;self.editando_plantilla=False
        if self.plantilla is None:self.cargar_tecnica(self.ajustes['formato'],self.ajustes['orientacion'],self.ajustes['margen_mm'])
        raiz=QVBoxLayout(self);barra=QMenuBar(self);raiz.setMenuBar(barra)
        if integrado:barra.hide();self.setSizeGripEnabled(False)
        menu=barra.addMenu('Lámina');self.menu_plantilla=menu;self.a_importar=menu.addAction('Importar plantilla…',self.importar_plantilla)
        self.a_editar_plantilla=menu.addAction('Editar plantilla',self.editar_plantilla);self.a_editar_plantilla.setCheckable(True)
        self.a_estandar=menu.addAction('Usar plantilla estándar',lambda:self.establecer_plantilla(None))
        self.a_quitar_plantilla=menu.addAction('Quitar plantilla',self.quitar_plantilla)
        menu.addAction('Guardar plantilla en biblioteca…',self.guardar_en_biblioteca)
        menu.addAction('Restaurar plantilla predeterminada…',self.restaurar_predeterminada)
        centro=QHBoxLayout();raiz.addLayout(centro,1)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFixedWidth(286 if integrado else 300);panel=QWidget();form=QFormLayout(panel);self.form_hoja=form;scroll.setWidget(panel)
        if integrado:
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:centro.addWidget(scroll)
        self.predeterminadas=QComboBox();self.predeterminadas.addItem('Elegir plantilla…',None)
        self.predeterminadas.addItem('A4 vertical — predeterminada',('A4','vertical'));self.predeterminadas.addItem('A3 horizontal',('A3','horizontal'));self.predeterminadas.addItem('A3 vertical',('A3','vertical'))
        for f in ('A2','A1','A0'):
            for o in ('vertical','horizontal'):self.predeterminadas.addItem(f+' '+o,(f,o))
        from .carpetas import asegurar_carpetas
        try:
            for archivo in asegurar_carpetas()['plantillas'].rglob('*.json'):
                if archivo.parent.name not in ('A4_vertical','A3_horizontal','A3_vertical') or archivo.name!='plantilla.json':self.predeterminadas.addItem(archivo.stem,str(archivo))
        except OSError:pass
        form.addRow('Biblioteca de plantillas',self.predeterminadas)
        self.formato=QComboBox();self.formato.addItems([*FORMATOS,'Personalizado']);self.formato.setCurrentText(self.ajustes['formato'])
        self.orientacion=QComboBox();self.orientacion.addItem('Horizontal','horizontal');self.orientacion.addItem('Vertical','vertical');self.orientacion.setCurrentIndex(self.orientacion.findData(self.ajustes['orientacion']))
        self.margen=QDoubleSpinBox();self.margen.setRange(5,40);self.margen.setSuffix(' mm');self.margen.setValue(self.ajustes['margen_mm']);self.margen.setEnabled(False);self.margen.setToolTip('Margen definido por la plantilla; no se modifica desde la hoja')
        self.modo=QComboBox();self.modo.addItem('Ajustar a una hoja','ajustar');self.modo.addItem('Escala fija / mosaico','escala');self.modo.setCurrentIndex(self.modo.findData(self.ajustes['modo']))
        self.escala=QDoubleSpinBox();self.escala.setRange(.01,10000);self.escala.setDecimals(2);self.escala.setSingleStep(.1);self.escala.setToolTip('A 1:1 una etapa mide 11,64 mm. Bajar el denominador aumenta el dibujo; subirlo lo reduce.');self.escala.setPrefix('1 : ');self.escala.setValue(self.ajustes['escala'])
        self.unidad=QComboBox();self.unidad.addItem('Elegir referencia…',None);self.unidad.addItem('96 ppp (44 u = 11,64 mm)',25.4/96);self.unidad.addItem('1 unidad = 1 mm',1.0)
        for i in range(self.unidad.count()):
            if self.unidad.itemData(i)==self.ajustes['unidad_mm']:self.unidad.setCurrentIndex(i)
        self.con_estado=QCheckBox('Incluir estado de simulación');self.con_estado.setEnabled(bool(estado));self.con_estado.setChecked(bool(estado) and self.ajustes['con_estado'])
        for nombre,w in (('Formato',self.formato),('Orientación',self.orientacion),('Margen',self.margen),('Colocación',self.modo),('Escala fija',self.escala),('Referencia',self.unidad)):form.addRow(nombre,w)
        form.addRow(self.con_estado);self.campos={}
        for k in CAMPOS:
            campo=QLineEdit(self.ajustes['campos'][k]);campo.setMaxLength(1000);self.campos[k]=campo;form.addRow(ROTULOS[k],campo)
        self.campos['hoja'].setToolTip('{n}: número de hoja; {m}: total de hojas')
        self.campos['escala'].setPlaceholderText('Automática si se deja vacío')
        self.guardar_ajustes=QPushButton('Aplicar al proyecto');form.addRow(self.guardar_ajustes)
        self.vista=VistaLamina();self.vista.colocar=self.colocar
        if integrado:
            self.area=QScrollArea();self.area.setWidgetResizable(False);self.area.setAlignment(Qt.AlignmentFlag.AlignCenter);self.area.setWidget(self.vista);centro.addWidget(self.area,1);self.propiedades=QStackedWidget();self.propiedades.setFixedWidth(290);self.propiedades.addWidget(scroll);centro.addWidget(self.propiedades)
        else:centro.addWidget(self.vista,1)
        nav=QHBoxLayout();raiz.addLayout(nav);self.anterior=QPushButton('← Anterior');self.siguiente=QPushButton('Siguiente →');self.pagina=QLabel()
        self.b_centrar=QPushButton('Centrar GRAFCET');nav.addWidget(self.b_centrar);self.b_centrar.clicked.connect(self.centrar)
        nav.addWidget(self.anterior);nav.addWidget(self.pagina);nav.addWidget(self.siguiente);nav.addStretch(1)
        self.b_exportar=QPushButton('Exportar…');self.b_imprimir=QPushButton('Imprimir…');cerrar=QPushButton('Cerrar')
        for w in (self.b_exportar,self.b_imprimir,cerrar):nav.addWidget(w)
        if integrado:
            for w in (self.b_exportar,self.b_imprimir,self.b_centrar,cerrar,self.guardar_ajustes):w.hide()
        self.error=QLabel();self.error.setWordWrap(True);raiz.addWidget(self.error)
        self.anterior.clicked.connect(lambda:self.ir(self.indice-1));self.siguiente.clicked.connect(lambda:self.ir(self.indice+1))
        self.b_exportar.clicked.connect(self.exportar);self.b_imprimir.clicked.connect(self.imprimir);cerrar.clicked.connect(self.close)
        self.guardar_ajustes.clicked.connect(lambda:self.aplicar(True))
        for w in (self.formato,self.orientacion,self.modo,self.unidad):w.currentIndexChanged.connect(self.actualizar)
        for w in (self.margen,self.escala):w.valueChanged.connect(self.actualizar)
        self.con_estado.toggled.connect(self.actualizar)
        for w in self.campos.values():w.textChanged.connect(self.actualizar)
        if self.plantilla and self.plantilla.get('source')=='GrafConnect':
            i=self.indice_predeterminada(self.ajustes['formato'],self.ajustes['orientacion'])
            if i>=0:self.predeterminadas.setCurrentIndex(i)
        self.predeterminadas.currentIndexChanged.connect(self.elegir_predeterminada)
        self.inicial=copy.deepcopy(self.valores());self.actualizar()
        if integrado:self.preparar_textos()

    def valores(self):
        return ajustes_lamina({'formato':self.formato.currentText(),'orientacion':self.orientacion.currentData(),'margen_mm':self.margen.value(),
          'modo':self.modo.currentData(),'escala':self.escala.value(),'unidad_mm':self.unidad.currentData(),'con_estado':self.con_estado.isChecked(),
          'plantilla':self.plantilla,'offset_mm':self.offset,'campos':{k:w.text() for k,w in self.campos.items()}})

    def actualizar(self,*args):
        tecnica=self.plantilla is None or self.plantilla.get('source')=='GrafConnect'
        if tecnica:
            f,o,m=self.formato.currentText(),self.orientacion.currentData(),self.margen.value()
            w,h=FORMATOS.get(f,(0,0));w,h=(h,w) if o=='horizontal' else (w,h)
            if self.plantilla is None or self.plantilla['size']!=[w,h] or abs(float(self.plantilla.get('margin_mm',10))-m)>.001:self.cargar_tecnica(f,o,m)
        for w in (self.formato,self.orientacion):w.setEnabled(tecnica)
        if tecnica:
            self.predeterminadas.blockSignals(True);self.predeterminadas.setCurrentIndex(max(0,self.indice_predeterminada(self.formato.currentText(),self.orientacion.currentData())));self.predeterminadas.blockSignals(False)
        if not tecnica:
            self.predeterminadas.blockSignals(True);self.predeterminadas.setItemText(0,self.plantilla.get('source','Personalizada')+' — proyecto');self.predeterminadas.setCurrentIndex(0);self.predeterminadas.blockSignals(False)
        self.a_editar_plantilla.setEnabled(self.plantilla is not None);self.a_quitar_plantilla.setEnabled(self.plantilla is not None)
        fijo=self.modo.currentData()=='escala';self.escala.setEnabled(fijo);self.unidad.setEnabled(fijo)
        try:
            self.documento=(DocumentoHoja if '_graficos' in self.modelo else DocumentoLaminas)(self.modelo,self.estado,self.valores(),self.dependencias);self.error.setText(self.aviso_biblioteca)
        except (ValueError,OverflowError) as exc:self.documento=None;self.error.setText(str(exc))
        self.b_exportar.setEnabled(self.documento is not None);self.b_imprimir.setEnabled(self.documento is not None)
        if self.editor_textos and self.documento:self.editor_textos.campos.update(self.documento.campos(0))
        self.guardar_ajustes.setEnabled(self.documento is not None);self.b_centrar.setEnabled(self.documento is None or self.documento.total==1);self.ir(self.indice);self.modificado.emit()

    def ir(self,indice):
        d=self.documento;self.indice=max(0,min(indice,d.total-1)) if d else 0
        self.vista.documento=d;self.vista.indice=self.indice;self.vista.update()
        self.pagina.setText(f'Hoja {self.indice+1} de {d.total}' if d else 'Sin vista previa')
        self.anterior.setEnabled(bool(d and self.indice));self.siguiente.setEnabled(bool(d and self.indice+1<d.total))

    def aplicar(self,forzar=False):
        if self.documento is None:return
        cfg=self.valores()
        if forzar or cfg!=self.inicial:self.aplicar_callback(cfg);self.inicial=copy.deepcopy(cfg)

    def exportar(self):
        d=self.documento
        if d is None:return
        from .carpetas import asegurar_carpetas
        try:inicial=str(asegurar_carpetas()['laminas']/'plano.pdf')
        except OSError as exc:QMessageBox.warning(self,'Exportar plano',str(exc));return
        nombre,filtro=QFileDialog.getSaveFileName(self,'Exportar plano',inicial,'Documento PDF (*.pdf);;Dibujo SVG (*.svg)')
        if not nombre:return
        ruta=Path(nombre);svg='SVG' in filtro
        extension='.svg' if svg else '.pdf'
        if ruta.suffix.lower() in ('.pdf','.svg'):ruta=ruta.with_suffix(extension)
        elif ruta.suffix.lower()!=extension:ruta=ruta.with_name(ruta.name+extension)
        rutas=d.rutas_svg(ruta) if svg else [ruta]
        if any(p.exists() for p in rutas) and QMessageBox.question(self,'Exportar plano','Se sobrescribirán archivos existentes. ¿Continuar?')!=QMessageBox.StandardButton.Yes:return
        try:
            if svg:d.exportar_svg(ruta)
            else:d.exportar_pdf(ruta)
            self.aplicar();self.error.setText(f'Exportadas {d.total} hojas en {ruta.parent}'+(' (un SVG por hoja)' if svg and d.total>1 else ''))
        except (OSError,ValueError,RuntimeError) as exc:QMessageBox.warning(self,'Exportar plano',str(exc))

    def imprimir(self):
        if self.documento is None:return
        try:
            if self.documento.imprimir(self):self.aplicar()
        except (OSError,ValueError,RuntimeError) as exc:QMessageBox.warning(self,'Imprimir plano',str(exc))

    def establecer_plantilla(self,plantilla):
        from .importar_plantillas import formato_iso
        from grafcet.plantillas_tecnicas import sin_rotulos_auxiliares
        self.plantilla=sin_rotulos_auxiliares(plantilla);self.offset=[0.,0.]
        nombre,orientacion=formato_iso(*plantilla['size']) if plantilla else (self.formato.currentText() if self.formato.currentText() in FORMATOS else 'A4',self.orientacion.currentData())
        self.formato.blockSignals(True);self.orientacion.blockSignals(True)
        self.formato.setCurrentText(nombre);self.orientacion.setCurrentIndex(self.orientacion.findData(orientacion))
        self.formato.blockSignals(False);self.orientacion.blockSignals(False)
        self.actualizar()
        if self.integrado:self.preparar_textos();self.actualizar_campos()

    def importar_plantilla(self):
        from .importar_plantillas import importar,paginas_pdf
        from .plantillas import EditorPlantilla
        from .carpetas import asegurar_carpetas,cargar_plantilla
        try:inicial=str(asegurar_carpetas()['plantillas'])
        except OSError as exc:QMessageBox.warning(self,'Importar plantilla',str(exc));return
        nombre,_=QFileDialog.getOpenFileName(self,'Importar plantilla de lámina',inicial,
            'Plantillas (*.dxf *.DXF *.pdf *.svg *.json);;Plantilla GrafConnect (*.json);;DXF (*.dxf *.DXF);;PDF (*.pdf);;SVG (*.svg);;Todos los archivos (*)')
        if not nombre:return
        try:
            pagina=0
            if Path(nombre).suffix.lower()=='.pdf':
                total=paginas_pdf(nombre)
                if total>1:
                    pagina,ok=QInputDialog.getInt(self,'Página de la plantilla','Página que se importa',1,1,total)
                    if not ok:return
                    pagina-=1
            plantilla=cargar_plantilla(nombre) if Path(nombre).suffix.lower()=='.json' else importar(nombre,pagina,campos=not self.integrado)
            if Path(nombre).suffix.lower()=='.json':plantilla['source']='Personalizada'
            if plantilla.get('warnings'):QMessageBox.information(self,'Importar plantilla','\n'.join(plantilla['warnings']))
            if self.integrado:self.establecer_plantilla(plantilla)
            else:
                editor=EditorPlantilla(plantilla,self.documento.campos(self.indice) if self.documento else {},self)
                try:
                    if editor.exec()==QDialog.DialogCode.Accepted:self.establecer_plantilla(editor.plantilla)
                finally:editor.deleteLater()
        except (ValueError,OSError,RuntimeError,ImportError) as exc:QMessageBox.warning(self,'Importar plantilla',str(exc))

    def preparar_textos(self):
        from .plantillas import EditorPlantilla
        if self.editor_textos:
            viejo=self.editor_textos;self.propiedades.removeWidget(viejo.panel_propiedades);viejo.panel_propiedades.deleteLater();viejo.deleteLater()
        t=EditorPlantilla(self.plantilla,self.documento.campos(0) if self.documento else {k:w.text() for k,w in self.campos.items()},self,solo_texto=True)
        t.hide();t.vista.hide();scroll=t.layout().itemAt(0).widget();t.layout().removeWidget(scroll);t.panel_propiedades=scroll;scroll.setFixedWidth(286)
        self.propiedades.addWidget(scroll);self.editor_textos=t;self.vista.textos=t
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);scroll.widget().layout().setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows);t.nuevo.hide()
        t.fuente.setMinimumContentsLength(8);t.fuente.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);t.fuente.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        t.botones_dialogo.hide()
        t.lista.hide();label=scroll.widget().layout().labelForField(t.lista)
        if label:label.hide()
        t.nuevo.clicked.disconnect();t.nuevo.clicked.connect(self.anadir_texto)
        t.modificado.connect(self.textos_cambiados)
        t.seleccionado.connect(lambda:self.propiedades.setCurrentWidget(t.panel_propiedades if t.actual else self.propiedades.widget(0)))
        t.elegir(-1);self.propiedades.setCurrentIndex(0)
        t.b_zona.toggled.connect(lambda on:setattr(self.vista,'zona',self.editando_plantilla));self.vista.zona=self.editando_plantilla
        for w in (t.b_zona,t.restar_zona,t.zona_label):w.setVisible(self.editando_plantilla)
        self.actualizar_campos()

    def actualizar_campos(self):
        if not self.integrado:return
        estandar=False  # En Planos se escribe directamente en los textos del cajetín.
        for w in self.campos.values():
            w.setVisible(bool(estandar));label=self.form_hoja.labelForField(w)
            if label:label.setVisible(bool(estandar))

    def textos_cambiados(self):
        self.plantilla=copy.deepcopy(self.editor_textos.plantilla);self.actualizar();self.aplicar()
        self.propiedades.setCurrentWidget(self.editor_textos.panel_propiedades if self.editor_textos.actual else self.propiedades.widget(0))

    def anadir_texto(self):
        self.vista.nuevo_texto=True;self.vista.setCursor(Qt.CursorShape.CrossCursor);self.error.setText('Pulsa en la hoja para colocar el texto.');self.vista.setFocus()

    def editar_plantilla(self):
        if self.integrado:
            if self.editor_textos is None:self.preparar_textos()
            self.editando_plantilla=not self.editando_plantilla;self.vista.zona=self.editando_plantilla
            self.a_editar_plantilla.setText('Terminar edición' if self.editando_plantilla else 'Editar plantilla');self.a_editar_plantilla.setChecked(self.editando_plantilla)
            self.error.setText('Editando plantilla · el fondo está bloqueado. Selecciona textos o marca la zona de dibujo.' if self.editando_plantilla else '')
            for w in (self.editor_textos.b_zona,self.editor_textos.restar_zona,self.editor_textos.zona_label):w.setVisible(self.editando_plantilla)
            self.propiedades.setCurrentWidget(self.editor_textos.panel_propiedades if self.editando_plantilla else self.propiedades.widget(0));self.vista.update();return
        if self.plantilla is None:return
        from .plantillas import EditorPlantilla
        editor=EditorPlantilla(self.plantilla,self.documento.campos(self.indice) if self.documento else {},self)
        try:
            if editor.exec()==QDialog.DialogCode.Accepted:self.establecer_plantilla(editor.plantilla)
        finally:editor.deleteLater()

    def quitar_plantilla(self):
        w,h=self.plantilla['size'];self.establecer_plantilla({'version':1,'size':[w,h],'source':'Hoja sin plantilla','primitives':[]})

    def cargar_tecnica(self,f,o,m):
        from .carpetas import predeterminada
        try:
            from grafcet.plantillas_tecnicas import sin_rotulos_auxiliares
            self.plantilla=sin_rotulos_auxiliares(predeterminada(f,o,m));self.aviso_biblioteca=''
            self.plantilla['primitives']=[t for t in self.plantilla['primitives'] if not(t.get('omit_empty') and t.get('field') in ('proyecto','revision','hoja','libre'))]
        except (OSError,ValueError) as exc:
            from grafcet.plantillas_tecnicas import plantilla_tecnica
            w,h=FORMATOS.get(f,FORMATOS['A4']);w,h=(h,w) if o=='horizontal' else (w,h)
            try:self.plantilla=plantilla_tecnica(w,h,m)
            except ValueError:self.plantilla=None
            self.aviso_biblioteca=str(exc)+' · No se ha sobrescrito ningún archivo.'

    def indice_predeterminada(self,formato,orientacion):
        for i in range(self.predeterminadas.count()):
            v=self.predeterminadas.itemData(i)
            if isinstance(v,(list,tuple)) and list(v)==[formato,orientacion]:return i
        return -1

    def elegir_predeterminada(self,indice):
        datos=self.predeterminadas.itemData(indice)
        if datos is None:return
        try:
            if isinstance(datos,(list,tuple)):
                f,o=datos;self.cargar_tecnica(f,o,10.)
                if self.plantilla is None:raise ValueError(self.aviso_biblioteca)
                p=self.plantilla;self.margen.blockSignals(True);self.margen.setValue(10.);self.margen.blockSignals(False);self.establecer_plantilla(p)
            else:
                from .carpetas import cargar_plantilla
                p=cargar_plantilla(datos);p['source']='Personalizada';self.establecer_plantilla(p)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Plantillas',str(exc))

    def colocar(self,offset):self.offset=offset;self.actualizar()

    def centrar(self):
        d=self.documento
        if d is None:
            self.colocar([0.,0.]);d=self.documento
        if d is None or d.total!=1:return
        if hasattr(d,'capas'):
            if not d.capas:return
            d=d.capas[max(0,self.vista.capa)]
        r=d.destino(0);delta=d.contenido.center()-r.center()
        self.colocar([self.offset[0]+delta.x(),self.offset[1]+delta.y()])

    def guardar_en_biblioteca(self):
        from .carpetas import asegurar_carpetas,guardar_plantilla
        try:
            inicial=asegurar_carpetas()['plantillas']/'plantilla_personalizada.json'
            nombre,_=QFileDialog.getSaveFileName(self,'Guardar plantilla en biblioteca',str(inicial),'Plantilla GrafConnect (*.json)',options=QFileDialog.Option.DontConfirmOverwrite)
            if not nombre:return
            destino=Path(nombre)
            if destino.suffix.lower()!='.json':destino=destino.with_name(destino.name+'.json')
            if destino.exists() and QMessageBox.question(self,'Plantilla','El archivo ya existe. ¿Sobrescribirlo?')!=QMessageBox.StandardButton.Yes:return
            guardar_plantilla(destino,self.plantilla or self.documento.plantilla.p)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Guardar plantilla',str(exc))

    def restaurar_predeterminada(self):
        from .carpetas import asegurar_carpetas,guardar_plantilla
        from grafcet.plantillas_tecnicas import PREDETERMINADAS,plantilla_tecnica
        nombre=self.formato.currentText()+'_'+self.orientacion.currentData()
        if nombre not in PREDETERMINADAS:
            QMessageBox.information(self,'Plantillas','Elige A4 vertical, A3 horizontal o A3 vertical para restaurar su archivo predeterminado');return
        try:
            rutas=asegurar_carpetas();destino=rutas['plantillas']/nombre/'plantilla.json'
            if QMessageBox.question(self,'Restaurar plantilla',f'Se sustituirá {destino}. ¿Restaurar la plantilla original?')!=QMessageBox.StandardButton.Yes:return
            p=plantilla_tecnica(*PREDETERMINADAS[nombre]);guardar_plantilla(destino,p);self.establecer_plantilla(p)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Restaurar plantilla',str(exc))

    def keyPressEvent(self,event):
        if self.integrado:
            if event.key()==Qt.Key.Key_Escape:self.vista.seleccionado=False;self.vista.update();event.accept();return
            QWidget.keyPressEvent(self,event);return
        super().keyPressEvent(event)

    def closeEvent(self,event):
        self.aplicar();super().closeEvent(event)
