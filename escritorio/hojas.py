"""Hojas vinculadas a IDs del proyecto: la selección se vuelve a dibujar al abrirlas."""
import copy
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QDialogButtonBox,QMessageBox
from grafcet.editor import Editor
from grafcet.laminas import ajustes_lamina,FORMATOS
from .carpetas import predeterminada,asegurar_carpetas,cargar_plantilla


def dibujo_vinculado(edicion,refs):
    from .edicion import Edicion
    frag=edicion.copiar_fragmento(refs)
    elegidos=set(refs)
    # Se conserva el modelo original para resolver nombres y expresiones externas;
    # solo se filtra la representación. Las acciones seleccionadas solas utilizan
    # la conversión y las posiciones visibles que ya ofrece Copiar.
    pres=copy.deepcopy(edicion.ed.presentation)
    pres.update(copy.deepcopy(frag.presentation))
    temporal=Edicion(Editor(copy.deepcopy(edicion.ed.model),pres),edicion.titulo)
    try:salida=copy.deepcopy(temporal.M)
    finally:temporal.deleteLater()
    for k in ('steps','macros','partials','transitions','drafts','draftActions','annotations','bars'):
        salida[k]=[x for x in salida.get(k,[]) if x['id'] in elegidos]
    for t in salida['transitions']:
        for k in ('pre','post','preDib','postDib'):t[k]=[i for i in t.get(k,[]) if i in elegidos]
    salida['links']=[l for l in salida.get('links',[]) if l['tid'] in elegidos and l['sid'] in elegidos]
    for bar in salida.get('bars',[]):
        for k in ('arriba','abajo'):bar[k]=[i for i in bar[k] if i in elegidos]
    return salida


class CrearHoja(QDialog):
    def __init__(self,edicion,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Enviar selección a plano')
        self.edicion = edicion
        raiz=QVBoxLayout(self);form=QFormLayout();raiz.addLayout(form)
        self.destino=QComboBox();self.destino.addItem('Crear hoja nueva',None)
        for h in edicion.ed.sheet_links():self.destino.addItem(h['nombre'],h['id'])
        form.addRow('Destino',self.destino)
        self.nombre=QLineEdit(f'Hoja {len(edicion.ed.sheet_links())+1}');form.addRow('Nombre',self.nombre)
        self.formato=QComboBox();self.formato.addItems(['A4','A3','A2','A1','A0']);form.addRow('Tamaño',self.formato)
        self.orientacion=QComboBox();self.orientacion.addItem('Vertical','vertical');self.orientacion.addItem('Horizontal','horizontal');form.addRow('Orientación',self.orientacion)
        self.plantilla=QComboBox();self.plantilla.addItem('Técnica predeterminada',None)
        self.actual=edicion.ed.sheet_settings().get('plantilla')
        if self.actual and self.actual.get('source')!='GrafConnect':self.plantilla.addItem('Plantilla actual del proyecto','actual')
        for archivo in asegurar_carpetas()['plantillas'].rglob('*.json'):
            if archivo.parent.name not in ('A4_vertical','A3_horizontal','A3_vertical') or archivo.name!='plantilla.json':self.plantilla.addItem(archivo.stem,str(archivo))
        form.addRow('Plantilla',self.plantilla)
        botones=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Ok).setText('Crear hoja');botones.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        raiz.addWidget(botones);botones.accepted.connect(self.accept);botones.rejected.connect(self.reject)
        self.formato.currentIndexChanged.connect(self.actualizar);self.plantilla.currentIndexChanged.connect(self.actualizar);self.actualizar()
        self.configuracion=None
        self.destino.currentIndexChanged.connect(self.actualizar_destino);self.actualizar_destino()
    def actualizar_destino(self):
        nueva=self.destino.currentData() is None
        for w in (self.nombre,self.plantilla):w.setEnabled(nueva)
        self.actualizar()
        if not nueva:self.formato.setEnabled(False);self.orientacion.setEnabled(False)
    def actualizar(self):
        tecnica=self.plantilla.currentData() is None
        self.formato.setEnabled(tecnica);self.orientacion.setEnabled(tecnica)
        self.orientacion.model().item(1).setEnabled(not(tecnica and self.formato.currentText()=='A4'))
        if tecnica and self.formato.currentText()=='A4':self.orientacion.setCurrentIndex(0)
    def valores(self):
        datos=self.plantilla.currentData();f=self.formato.currentText();o=self.orientacion.currentData()
        if datos is None:p=predeterminada(f,o)
        elif datos=='actual':p=copy.deepcopy(self.actual)
        else:p=cargar_plantilla(datos);p['source']='Personalizada'
        if datos is not None:
            from .importar_plantillas import formato_iso
            f,o=formato_iso(*p['size'])
        campos=self.edicion.ed.sheet_settings()['campos']
        for k,v in (('titulo',self.edicion.titulo),('proyecto',self.edicion.titulo),('fecha',QDate.currentDate().toString('yyyy-MM-dd'))):
            if not campos[k]:campos[k]=v
        cfg=ajustes_lamina({'formato':f,'orientacion':o,'modo':'escala','plantilla':p,
             'campos':campos})
        return cfg
    def accept(self):
        try:self.configuracion=self.valores()
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Crear hoja',str(exc));return
        super().accept()


class SeleccionParaHoja:
    """Controlador temporal que solo selecciona; nunca mueve ni modifica el GRAFCET."""
    solo_seleccion=True
    def __init__(self,edicion):self.edicion=edicion;self.inicio=None;self.previos=[]
    @property
    def M(self):return self.edicion.M
    @property
    def sel(self):return self.edicion.sel
    @sel.setter
    def sel(self,valor):self.edicion.sel=valor
    @property
    def accion(self):return self.edicion.accion
    @accion.setter
    def accion(self,valor):self.edicion.accion=valor
    @property
    def caja_seleccion(self):return self.edicion.caja_seleccion
    def seleccionar(self,ids):self.edicion.seleccionar(ids)
    def mover_teclado(self,*args):return False
    def _cadena(self,ident):
        e=self.edicion
        posiciones={x['id']:(x['x'],x['y']) for k in ('steps','transitions','macros') for x in e.M.get(k,[])}
        cadenas=e.ed.chains([ident],posiciones)
        ids=list(dict.fromkeys(i for cadena in cadenas for i in cadena)) or [ident]
        ids += [a['id'] for etapa in e.M['steps'] if etapa['id'] in ids for a in etapa.get('actions',[])]
        ids += [a['id'] for a in e.M.get('draftActions',[]) if a.get('etapa') in ids]
        return list(dict.fromkeys(ids))
    def prensar(self,p,event=None):
        from .diagrama import elemento_en
        from PySide6.QtCore import Qt
        e=self.edicion;caja=e.accion_en(p) or e.orden_en(p);ident=caja['id'] if caja else elemento_en(e.M,p)
        amplia=bool(event and event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        individual=bool(event and event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ident:
            grupo=self._cadena(ident) if caja is None else [ident]
            if individual: ids=[i for i in e.sel if i!=ident] if ident in e.sel else e.sel+[ident]
            else: ids=list(dict.fromkeys(e.sel+grupo)) if amplia else grupo
            e.seleccionar(ids)
        else:
            self.inicio=p;self.previos=list(e.sel) if amplia else [];e.seleccionar(self.previos)
        return True
    def mover(self,p,event=None):
        if self.inicio is not None:self.edicion.diagrama.lazo(self.inicio,p)
        return True
    def soltar(self,p,event=None):
        if self.inicio is not None:
            self.edicion.seleccionar(list(dict.fromkeys(self.previos+self.edicion.dentro(self.inicio,p))))
            self.inicio=None;self.edicion.diagrama.lazo(None)
        return True
    def doble(self,*args):return True
    def menu(self,*args):return []
    def colocar(self,*args):return None
