"""Página de Planos integrada en la ventana: hojas, lienzo y propiedades."""
from PySide6.QtCore import Qt,QSize,QTimer,QEvent,QPointF,QRect,QRectF
from PySide6.QtGui import QAction,QIcon,QPixmap,QPainter,QPen,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QToolBar,QToolButton,
    QSplitter,QListView,QListWidget,QListWidgetItem,QComboBox,QMenu,QMessageBox,QInputDialog,QDoubleSpinBox,QScrollArea,QFormLayout,QPushButton,QStyledItemDelegate,QStyle,QSizePolicy)
from . import estilo
from .paneles import TituloSeccion
from .bloques import FlowLayout
from .laminas import DialogoLaminas

_ACTUAL=object()


def icono_planos():
    pix=QPixmap(32,32);pix.fill(Qt.GlobalColor.transparent);p=QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QColor(estilo.ACENTO),1.7))
    p.drawRect(6,3,21,26);p.drawRect(9,6,15,20);p.drawRect(14,21,10,5);p.drawLine(19,21,19,26);p.end()
    return QIcon(pix)


class MiniaturaHoja(QStyledItemDelegate):
    """Tarjeta medida y pintada con la misma fuente, independiente del estilo nativo."""
    def sizeHint(self,opcion,indice):
        ancho=max(128,self.parent().viewport().width())
        texto=opcion.fontMetrics.boundingRect(QRect(0,0,ancho-16,10000),Qt.TextFlag.TextWordWrap,indice.data() or '')
        return QSize(ancho,8+82+6+texto.height()+8)

    def paint(self,p,opcion,indice):
        p.save();r=opcion.rect
        if opcion.state & QStyle.StateFlag.State_Selected:p.fillRect(r.adjusted(2,2,-2,-2),QColor(estilo.ACENTO_SUAVE))
        icono=indice.data(Qt.ItemDataRole.DecorationRole)
        if icono:icono.paint(p,QRect(r.center().x()-58,r.top()+8,116,82),Qt.AlignmentFlag.AlignCenter)
        p.setFont(opcion.font);p.setPen(opcion.palette.text().color())
        texto=QRect(r.left()+8,r.top()+96,r.width()-16,r.height()-104)
        p.drawText(texto,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop|Qt.TextFlag.TextWordWrap,indice.data() or '')
        p.restore()


class PaginaPlanos(QWidget):
    def __init__(self,ventana):
        super().__init__();self.ventana=ventana;self.editor=None;self.origen=None;self.hoja_id=None
        self.aplicando=False;self.cargando=False;self.automatico=True;self.factor_zoom=1.;self.graficos=[];self.pan=None;self.grafico_actual=0
        self.parpadeos_hoja=0
        self.t_hoja=QTimer(self)
        self.t_hoja.setInterval(350)
        self.t_hoja.timeout.connect(self._paso_parpadeo_hoja)
        self.lista_timer=QTimer(self);self.lista_timer.setSingleShot(True);self.lista_timer.setInterval(0);self.lista_timer.timeout.connect(self.ajustar_lista)
        self.dimension_timer=QTimer(self);self.dimension_timer.setSingleShot(True);self.dimension_timer.setInterval(0);self.dimension_timer.timeout.connect(self.dimensionar)
        self.guardar_timer=QTimer(self);self.guardar_timer.setSingleShot(True);self.guardar_timer.setInterval(400);self.guardar_timer.timeout.connect(self.aplicar)
        raiz=QVBoxLayout(self);raiz.setContentsMargins(2*estilo.E2,2*estilo.E2,2*estilo.E2,2*estilo.E2);raiz.setSpacing(estilo.E1)  # (el contenido, dentro de la tarjeta de `paintEvent`)
        barras=QWidget();flujo=FlowLayout(barras,estilo.E2);self.barra=QToolBar('Planos');self.barra.setObjectName('barraPlanos');self.barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon);flujo.addWidget(self.barra)
        self.a_hoja=self.barra.addAction('+ Añadir hoja',self.nueva_hoja)
        self.a_nueva=self.barra.addAction('Traer GRAFCET',self.traer)
        self.barra.addSeparator();self.a_centrar=self.barra.addAction('Centrar GRAFCET',lambda:self.editor and self.editor.centrar())
        self.barra_hoja=self.barra;self.barra=QToolBar('Vista de la hoja');self.barra.setObjectName('barraPlanos');flujo.addWidget(self.barra)
        self.l_zoom_pantalla=QLabel('Zoom de pantalla ');self.acc_zoom_etiqueta=self.barra.addWidget(self.l_zoom_pantalla)
        self.barra.addAction('−',lambda:self.zoom(1/1.15));self.zoom_combo=QComboBox();self.zoom_combo.setMinimumWidth(130)
        self.zoom_combo.addItem('Ajustar hoja',None)
        for n in (50,75,100,125,150,200):self.zoom_combo.addItem(str(n)+' %',n/100)
        self.barra.addWidget(self.zoom_combo);self.barra.addAction('+',lambda:self.zoom(1.15));self.zoom_combo.currentIndexChanged.connect(self.elegir_zoom)
        self.propiedades_grafico=QWidget(self);self.propiedades_grafico.hide();form=QFormLayout(self.propiedades_grafico)
        form.addRow(QLabel('GRAFCET seleccionado'))
        self.tamano=QDoubleSpinBox();self.tamano.setRange(50,200);self.tamano.setSingleStep(10);self.tamano.setDecimals(0);self.tamano.setSuffix(' %');self.tamano.setValue(100);self.tamano.setToolTip('Tamaño impreso (50–200 %), independiente del zoom');self.tamano.valueChanged.connect(self.cambiar_tamano);form.addRow('Tamaño',self.tamano)
        self.b_eliminar_grafico=QPushButton('Eliminar del plano');self.b_eliminar_grafico.clicked.connect(self.eliminar_grafico);form.addRow(self.b_eliminar_grafico)
        self.b_plantilla=QToolButton();self.b_plantilla.setText('Biblioteca y opciones');self.b_plantilla.setObjectName('bibliotecaPlanos');self.b_plantilla.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);self.acc_biblioteca=self.barra.addWidget(self.b_plantilla)
        self.compacto=False;self.b_mas=QToolButton();self.b_mas.setText('Más');self.b_mas.setObjectName('bibliotecaPlanos');self.b_mas.setToolTip('Centrar, exportar, imprimir, biblioteca y plantilla');self.b_mas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);self.menu_mas=QMenu(self.b_mas);self.b_mas.setMenu(self.menu_mas);self.menu_mas.aboutToShow.connect(self._rellenar_mas);self.acc_mas=self.barra.addWidget(self.b_mas);self.acc_mas.setVisible(False)
        self.a_exportar=self.barra_hoja.addAction('Exportar…',lambda:self.editor and self.editor.exportar())
        self.a_imprimir=self.barra_hoja.addAction('Imprimir…',lambda:self.editor and self.editor.imprimir())
        self.barra_plantilla=QToolBar('Plantilla y textos');self.barra_plantilla.setObjectName('barraPlanos');flujo.addWidget(self.barra_plantilla);raiz.addWidget(barras)
        cab=QHBoxLayout();self.estado=QLabel('EDICIÓN DE PLANO');self.estado.setStyleSheet(estilo.estilo_chip('editar'));self.estado.setFixedHeight(estilo.ALTO_CONTROL-6);self.estado.setObjectName('chipModo')
        self.titulo=QLabel('Planos');self.titulo.setStyleSheet(f'color:{estilo.TINTA};font-weight:700;font-size:{estilo.T_TITULO}px');self.titulo.setMinimumHeight(estilo.ALTO_CONTROL);cab.setSpacing(estilo.E3);cab.addWidget(self.estado);cab.addWidget(self.titulo,1);raiz.addLayout(cab)
        self.divisor=QSplitter(Qt.Orientation.Horizontal);raiz.addWidget(self.divisor,1)
        lateral=QWidget();l=QVBoxLayout(lateral);l.setContentsMargins(8,4,8,0);l.setSpacing(estilo.E2);titulo_hojas=TituloSeccion('Hojas');titulo_hojas.setContentsMargins(5,0,0,0);  # (8 px al borde de la columna, como la tabla y los botones de Variables; el cuadrado a 13, como el de Elementos y Variables)
        titulo_hojas.setMinimumHeight(estilo.ALTO_CONTROL-6);titulo_hojas.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed);l.addWidget(titulo_hojas)
        b_hoja=QToolButton();b_hoja.setDefaultAction(self.a_hoja);self.b_hoja=b_hoja;b_hoja.setMinimumHeight(estilo.ALTO_CONTROL);b_hoja.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
        self.barra_hoja.removeAction(self.a_hoja)
        self.lista=QListWidget();self.lista.setViewMode(QListView.ViewMode.ListMode);self.lista.setItemDelegate(MiniaturaHoja(self.lista));self.lista.installEventFilter(self);self.lista.setFlow(QListView.Flow.TopToBottom);self.lista.setWrapping(False);self.lista.setMovement(QListView.Movement.Static);self.lista.setResizeMode(QListView.ResizeMode.Adjust);self.lista.setSpacing(0);self.lista.setIconSize(QSize(116,82));self.lista.setWordWrap(True);self.lista.setMinimumWidth(140);self.lista.setMaximumWidth(205);self.lista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);l.addWidget(self.lista);l.addWidget(b_hoja);l.addStretch(1)
        self.scroll_hojas=QScrollArea();self.scroll_hojas.setFocusPolicy(Qt.FocusPolicy.NoFocus);self.scroll_hojas.setWidgetResizable(True);self.scroll_hojas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.scroll_hojas.setMinimumWidth(160);self.scroll_hojas.setMaximumWidth(215);self.scroll_hojas.setWidget(lateral);self.divisor.addWidget(self.scroll_hojas);self.cuerpo=QWidget();self.layout_editor=QVBoxLayout(self.cuerpo);self.layout_editor.setContentsMargins(0,0,0,0)
        self.vacio=QLabel('Todavía no hay hojas. Pulsa «+ Añadir hoja».');self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter);self.layout_editor.addWidget(self.vacio)
        self.divisor.addWidget(self.cuerpo);self.divisor.setStretchFactor(0,0);self.divisor.setStretchFactor(1,1);self.divisor.setSizes([160,1100])
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.lista.customContextMenuRequested.connect(self.menu_hoja)
        self.lista.currentRowChanged.connect(self.elegir);self.actualizar_acciones()

    def paintEvent(self,evento):
        """PLANOS dentro de una tarjeta blanca de borde fino y esquinas redondeadas, como el dibujo, la paleta o el panel de E/S (con el
        mismo margen de 8 px a los lados y abajo)."""
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(estilo.BORDE),1));p.setBrush(QColor(estilo.SUPERFICIE))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(estilo.E2+.5,.5,-estilo.E2-.5,-estilo.E2-.5),estilo.R_M,estilo.R_M);p.end()

    def escalar(self):
        """Cambió la escala de letra y de controles (pantalla completa o no): el chip y el título se miden otra vez."""
        self.estado.setStyleSheet(estilo.estilo_chip('editar'));self.estado.setFixedHeight(estilo.ALTO_CONTROL-6)
        self.titulo.setStyleSheet(f'color:{estilo.TINTA};font-weight:700;font-size:{estilo.T_TITULO}px');self.titulo.setMinimumHeight(estilo.ALTO_CONTROL)

    def compactar(self,on):
        """Ventana estrecha o baja: la hoja manda. Quedan «Traer GRAFCET» y el zoom en una sola fila, y lo secundario (centrar, exportar,
        imprimir, biblioteca y las órdenes de la plantilla) pasa a un botón «Más ▾» con un menú."""
        on=bool(on)
        if on!=self.compacto:
            self.compacto=on;self._aplicar_compacto()

    def _aplicar_compacto(self):
        on=self.compacto
        for a in (self.a_centrar,self.a_exportar,self.a_imprimir):a.setVisible(not on)
        self.acc_zoom_etiqueta.setVisible(not on);self.acc_biblioteca.setVisible(not on);self.acc_mas.setVisible(on)
        self.barra_plantilla.setVisible(self.editor is not None and not on)
        self.scroll_hojas.setMinimumWidth(112 if on else 150);self.scroll_hojas.setMaximumWidth(150 if on else 215)
        if self.editor is not None:
            pila=self.editor.propiedades;pila.setFixedWidth(232 if on else 290)
            for i in range(pila.count()):pila.widget(i).setFixedWidth(228 if on else 286)  # (cada página llena la pila: si no, se corta por la derecha)

    def _rellenar_mas(self):
        m=self.menu_mas;m.clear()
        for a in (self.a_centrar,self.a_exportar,self.a_imprimir):  # (sus botones de la barra están ocultos: el menú lleva copias)
            copia=m.addAction(a.text(),a.trigger);copia.setEnabled(a.isEnabled())
        if self.editor is not None:
            m.addSeparator()
            for a in self.barra_plantilla.actions():m.addAction(a)
        biblioteca=self.b_plantilla.menu()
        if biblioteca is not None and biblioteca.actions():
            biblioteca.setTitle('Biblioteca de plantillas');m.addSeparator();m.addMenu(biblioteca)

    def liberar_editor(self):
        if self.editor:
            self.editor.propiedades.removeWidget(self.propiedades_grafico);self.propiedades_grafico.setParent(self);self.propiedades_grafico.hide()
            self.editor.modificado.disconnect(self.cambiado);self.layout_editor.removeWidget(self.editor);self.editor.deleteLater();self.editor=None

    def ajustar_lista(self):
        lista=self.lista;lista.doItemsLayout();n=lista.count();lista.setVisible(bool(n))
        alto=sum(lista.sizeHintForRow(i) for i in range(n))+2*lista.frameWidth()+4 if n else 0
        if lista.height()!=alto:lista.setFixedHeight(alto)

    def menu_hoja(self,punto):
        item=self.lista.itemAt(punto)
        if item is None:return
        self.lista.setCurrentItem(item);menu=self.crear_menu_hoja()
        menu.exec(self.lista.viewport().mapToGlobal(punto))

    def crear_menu_hoja(self):
        menu=QMenu(self.lista);fila=self.lista.currentRow()
        a=menu.addAction('Eliminar hoja',self.eliminar_hoja);a.setEnabled(fila>=0)
        menu.addSeparator()
        a=menu.addAction('Subir una hoja',lambda:self.mover_hoja(-1));a.setEnabled(fila>0)
        a=menu.addAction('Bajar una hoja',lambda:self.mover_hoja(1));a.setEnabled(0<=fila<self.lista.count()-1)
        return menu

    def eliminar_hoja(self):
        item=self.lista.currentItem()
        if item is None or self.origen is not self.ventana.edicion:return
        ident=item.data(Qt.ItemDataRole.UserRole);fila=self.lista.currentRow();e=self.origen
        self.aplicar();self.liberar_editor()
        if self.ventana.destino_traer==(e,ident):self.ventana.destino_traer=None;self.ventana.aviso_traer.hide()
        e.ed.delete_sheet(ident);e.cambia()
        hojas=e.ed.sheet_links();destino=hojas[min(fila,len(hojas)-1)]['id'] if hojas else None
        self.mostrar(destino);self.lista.setFocus()

    def mover_hoja(self,delta):
        item=self.lista.currentItem()
        if item is None or self.origen is not self.ventana.edicion:return
        ident=item.data(Qt.ItemDataRole.UserRole);e=self.origen;self.aplicar()
        if e.ed.move_sheet(ident,delta):e.cambia();self.mostrar(ident);self.lista.setFocus()

    def eliminar_grafico(self):
        if not self.editor or not self.editor.vista.seleccionado or not self.graficos:return
        i=self.editor.vista.capa
        if not 0<=i<len(self.graficos):return
        self.aplicar();del self.graficos[i]
        e=self.ventana.edicion;e.ed.set_page_graphics(self.hoja_id,self.graficos);e.cambia();self.mostrar(self.hoja_id)

    def mostrar(self,ident=_ACTUAL):
        if self.cargando:return
        e=self.ventana.edicion
        if ident is _ACTUAL:ident=self.hoja_id if self.origen is e else None
        if self.origen is not e:
            self.guardar_timer.stop();self.liberar_editor();self.hoja_id=None;self.graficos=[];self.pan=None
        self.aplicar();self.cargando=True
        try:
            self.origen=e;self.lista.blockSignals(True);self.lista.clear()
            hojas=e.ed.sheet_links() if e else []
            for h in hojas:
                item=QListWidgetItem(icono_planos(),h['nombre']);item.setData(Qt.ItemDataRole.UserRole,h['id']);self.lista.addItem(item)
            if not any(h['id']==ident for h in hojas):ident=hojas[0]['id'] if hojas else None
            fila=next((i for i in range(self.lista.count()) if self.lista.item(i).data(Qt.ItemDataRole.UserRole)==ident),-1)
            self.ajustar_lista();self.lista.setCurrentRow(fila);self.lista.blockSignals(False);self.cargar(ident)
        finally:self.cargando=False
        self.estilo_boton_hoja()

    ACENTO_HOJA = estilo.ACENTO  # el acento de la interfaz (el de los títulos de esta página)
    ACENTO_HOJA_CLARO = estilo.PARPADEO

    def estilo_boton_hoja(self, fase=True):
        """«+ Añadir hoja» es el botón principal (fondo de acento, texto blanco) mientras no hay ninguna hoja; con
        hojas, el estilo normal. `fase` False es el tono claro del parpadeo."""
        sin_hojas = self.lista.count() == 0 and self.ventana.edicion is not None
        if not sin_hojas:
            self.t_hoja.stop()
            self.b_hoja.setStyleSheet('')
            return
        fondo = self.ACENTO_HOJA if fase else self.ACENTO_HOJA_CLARO
        self.b_hoja.setStyleSheet(
            f'QToolButton {{ background:{fondo}; color:white; font-weight:600; border:1px solid {self.ACENTO_HOJA}; '
            f'border-radius:{estilo.R_S}px; padding:0 14px; min-height:{estilo.ALTO_CONTROL - 2}px }}')

    def parpadear_boton_hoja(self):
        """Al entrar en la pestaña sin hojas, el botón parpadea suavemente tres veces (alterna dos tonos del acento)."""
        if self.lista.count() or self.ventana.edicion is None:
            return
        self.parpadeos_hoja = 6
        self.estilo_boton_hoja(False)
        self.t_hoja.start()

    def _paso_parpadeo_hoja(self):
        self.parpadeos_hoja -= 1
        if self.parpadeos_hoja <= 0:
            self.t_hoja.stop()
            self.estilo_boton_hoja(True)
            return
        self.estilo_boton_hoja(self.parpadeos_hoja % 2 == 0)

    def elegir(self,fila):
        if fila>=0 and not self.cargando:self.cargar(self.lista.item(fila).data(Qt.ItemDataRole.UserRole))

    def cargar(self,ident):
        self.aplicar();self.cargando=True
        try:
            self.liberar_editor()
            e=self.ventana.edicion;self.origen=e;self.hoja_id=ident
            v=self.ventana.v
            if e is None and v is None:self.vacio.show();return
            if ident is None:
                self.graficos=[];self.titulo.setText('Planos');self.vacio.setText('Todavía no hay hojas. Pulsa «+ Añadir hoja».');self.vacio.show();self.actualizar_acciones();return
            from .hojas import dibujo_vinculado
            hoja=next(h for h in e.ed.sheet_links() if h['id']==ident);cfg=hoja['ajustes'];nombre=hoja['nombre']
            self.graficos=self.graficos_hoja(hoja)
            modelo=self.modelo_hoja()
            estado={} if self.ventana.modo=='editar' else v.state()
            def guardar(valores):
                if e is not None and self.ventana.edicion is e:
                    e.ed.set_sheet_link(ident,valores)
                    e.ed.set_page_graphics(ident,self.graficos)
                    e.cambia();self.ventana._titulo_ventana()
            self.editor=DialogoLaminas(modelo,estado,cfg,guardar,self.cuerpo,self.ventana.diagrama.dependencias,integrado=True)
            self.editor.centrar=self.centrar_grafico;self.editor.vista.colocar=self.colocar;self.editor.vista.elegir_capa=self.elegir_grafico;self.editor.vista.eliminar_grafico=self.eliminar_grafico
            self.editor.propiedades.addWidget(self.propiedades_grafico)
            self.editor.nombre_plano=nombre;self.layout_editor.addWidget(self.editor);self.vacio.hide()
            self.editor.anterior.clicked.disconnect();self.editor.siguiente.clicked.disconnect();self.editor.anterior.clicked.connect(lambda:self.pasar_hoja(-1));self.editor.siguiente.clicked.connect(lambda:self.pasar_hoja(1))
            self.editor.modificado.connect(self.cambiado);self.editor.area.viewport().installEventFilter(self);self.editor.vista.installEventFilter(self)
            for w in (self.editor.modo,self.editor.escala,self.editor.unidad):
                w.hide();w.parentWidget().layout().labelForField(w).hide()
            self.elegir_grafico(0)
            self.barra_plantilla.clear()
            for accion in (self.editor.a_importar,self.editor.a_estandar,self.editor.a_editar_plantilla,self.editor.a_quitar_plantilla):self.barra_plantilla.addAction(accion)
            self.a_texto=self.barra_plantilla.addAction('Añadir texto',self.editor.anadir_texto)
            biblioteca=QMenu(self.b_plantilla)
            for a in self.editor.menu_plantilla.actions()[4:]:biblioteca.addAction(a)
            self.b_plantilla.setMenu(biblioteca);self.navegacion();self.actualizar_titulo();self.actualizar_acciones();self.miniatura(True);self._aplicar_compacto()
            self.dimension_timer.start()
        except (ValueError,OSError,RuntimeError,StopIteration) as exc:
            self.vacio.setText(str(exc));self.vacio.show();self.actualizar_acciones()
        finally:self.cargando=False

    def cambiado(self):
        if self.cargando:return
        self.navegacion();self.actualizar_acciones();self.actualizar_titulo();self.dimensionar();self.guardar_timer.start()

    def aplicar(self):
        self.guardar_timer.stop()
        if self.editor is None or self.aplicando or self.origen is not self.ventana.edicion:return
        self.aplicando=True
        try:
            self.editor.aplicar()
            e=self.ventana.edicion
            if e is self.origen and self.hoja_id and any(h['id']==self.hoja_id for h in e.ed.sheet_links()):
                antes=e.ed.dirty;e.ed.set_page_graphics(self.hoja_id,self.graficos)
                if e.ed.dirty or antes:e.cambia();self.ventana._titulo_ventana()
        finally:self.aplicando=False
        self.actualizar_titulo();self.miniatura()

    def actualizar_titulo(self):
        if self.editor:
            e=self.ventana.edicion;pendiente=e and e.ed.dirty
            self.titulo.setText(self.editor.nombre_plano+(' *' if pendiente else ''))

    def actualizar_acciones(self):
        e=self.ventana.edicion;ed=self.editor
        self.a_hoja.setEnabled(e is not None);self.barra_plantilla.setVisible(ed is not None and not self.compacto)
        self.a_nueva.setEnabled(ed is not None and self.ventana.modo=='editar');self.tamano.setEnabled(ed is not None and bool(self.graficos))
        for a,b in ((self.a_exportar,'b_exportar'),(self.a_imprimir,'b_imprimir'),(self.a_centrar,'b_centrar')):a.setEnabled(ed is not None and getattr(ed,b).isEnabled())
        self.b_plantilla.setEnabled(ed is not None)

    def miniatura(self,todas=False):
        if not self.editor or not self.editor.documento or self.origen is not self.ventana.edicion:return
        from .laminas import DocumentoHoja
        hojas={h['id']:h for h in self.ventana.edicion.ed.sheet_links()}
        for i in range(self.lista.count()):
            item=self.lista.item(i);ident=item.data(Qt.ItemDataRole.UserRole)
            if not todas and ident!=self.hoja_id:continue
            try:
                h=hojas.get(ident)
                if h is None:continue
                d=self.editor.documento if ident==self.hoja_id else DocumentoHoja(self.modelo_hoja(h),self.editor.estado,h['ajustes'],self.ventana.diagrama.dependencias)
                pix=QPixmap(116,82);pix.fill(QColor(estilo.MESA));p=QPainter(pix)
                try:
                    escala=min(112/d.ancho,78/d.alto);p.translate((116-d.ancho*escala)/2,(82-d.alto*escala)/2);p.scale(escala,escala);d.pintar(p,0)
                finally:p.end()
                item.setIcon(QIcon(pix))
            except (ValueError,RuntimeError):item.setIcon(icono_planos())

    def elegir_zoom(self,indice):
        valor=self.zoom_combo.itemData(indice);self.automatico=valor is None
        if valor is not None:self.factor_zoom=valor
        self.dimensionar()

    def zoom(self,factor):
        if self.editor and self.editor.documento:
            if self.automatico:
                d=self.editor.documento;v=self.editor.area.viewport();self.factor_zoom=min((v.width()-24)/d.ancho,(v.height()-24)/d.alto)/(96/25.4)
            self.automatico=False;self.factor_zoom=max(.1,min(8,self.factor_zoom*factor));self.zoom_combo.blockSignals(True);self.zoom_combo.setCurrentIndex(-1);self.zoom_combo.setPlaceholderText(f'{self.factor_zoom*100:.0f} %');self.zoom_combo.blockSignals(False);self.dimensionar()

    def dimensionar(self):
        if not self.editor or not self.editor.documento:return
        d=self.editor.documento;v=self.editor.vista
        pol=Qt.ScrollBarPolicy.ScrollBarAlwaysOff if self.automatico else Qt.ScrollBarPolicy.ScrollBarAsNeeded  # «Ajustar hoja»: la hoja cabe, sin barras
        self.editor.area.setHorizontalScrollBarPolicy(pol);self.editor.area.setVerticalScrollBarPolicy(pol)
        if self.automatico:v.resize(self.editor.area.viewport().size())
        else:v.resize(round(d.ancho*96/25.4*self.factor_zoom)+24,round(d.alto*96/25.4*self.factor_zoom)+24)
        v.update()

    def eventFilter(self,obj,event):
        if obj is self.lista:
            if event.type() in (QEvent.Type.Resize,QEvent.Type.FontChange,QEvent.Type.StyleChange,QEvent.Type.Show):self.lista_timer.start()
            if event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Delete:self.eliminar_hoja();return True
            return super().eventFilter(obj,event)
        if not self.editor:return super().eventFilter(obj,event)
        if obj is self.editor.area.viewport() and event.type()==QEvent.Type.Resize:self.dimension_timer.start()
        if event.type()==QEvent.Type.Wheel:
            from .diagrama import factor_zoom_rueda,desplazamiento_rueda,modo_rueda
            if modo_rueda(event)=="desplaza":  # Mayús + rueda: en horizontal; dos dedos de un panel táctil: en los dos ejes
                dx,dy=desplazamiento_rueda(event);a=self.editor.area;h,v=a.horizontalScrollBar(),a.verticalScrollBar();h.setValue(h.value()-dx);v.setValue(v.value()-dy);return True
            factor=factor_zoom_rueda(event)
            if factor==1.0:return True
            if self.editor.documento is None:return True  # (sin hoja cargada no hay punto que conservar)
            area=self.editor.area;vista=self.editor.vista;local=event.position()
            if obj is area.viewport():local=local-vista.pos()
            punto=vista.punto_hoja(local);pantalla=local+vista.pos()
            self.zoom(factor)
            d=self.editor.documento;k=min((vista.width()-24)/d.ancho,(vista.height()-24)/d.alto)
            nuevo=QPointF((vista.width()-d.ancho*k)/2+punto.x()*k,(vista.height()-d.alto*k)/2+punto.y()*k)
            h,v=area.horizontalScrollBar(),area.verticalScrollBar();delta=nuevo+vista.pos()-pantalla
            h.setValue(round(h.value()+delta.x()));v.setValue(round(v.value()+delta.y()));return True
        if event.type()==QEvent.Type.NativeGesture and event.gestureType()==Qt.NativeGestureType.ZoomNativeGesture:
            self.zoom(max(.2,1+event.value()));return True  # el pellizco de un panel táctil (macOS, Linux)
        if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton and obj is self.editor.vista:
            vista=self.editor.vista;t=vista.textos
            if t and vista.documento is not None and (vista.nuevo_texto or (vista.zona and t.b_zona.isChecked()) or any(i.contains(i.mapFromScene(vista.punto_hoja(event.position()))) for i in t.items)):return False
        if event.type()==QEvent.Type.MouseButtonPress and (event.button()==Qt.MouseButton.MiddleButton or (event.button()==Qt.MouseButton.LeftButton and (not self.editor.documento or not any(c.destino(0).contains(self.editor.vista.punto_hoja(event.position())) for c in self.editor.documento.capas)))):
            if event.button()==Qt.MouseButton.LeftButton and self.editor.vista.textos:self.editor.vista.textos.elegir(-1);self.editor.vista.seleccionado=False;self.editor.vista.update()
            a=self.editor.area;self.pan=(event.globalPosition(),a.horizontalScrollBar().value(),a.verticalScrollBar().value());self.editor.vista.setCursor(Qt.CursorShape.ClosedHandCursor);return True
        if self.pan and event.type()==QEvent.Type.MouseMove:
            p,h,v=self.pan;delta=event.globalPosition()-p;a=self.editor.area;a.horizontalScrollBar().setValue(round(h-delta.x()));a.verticalScrollBar().setValue(round(v-delta.y()));return True
        if self.pan and event.type()==QEvent.Type.MouseButtonRelease:
            self.pan=None;self.editor.vista.unsetCursor();return True
        return super().eventFilter(obj,event)

    @staticmethod
    def graficos_hoja(hoja):
        import copy
        if 'grafcets' in hoja:return copy.deepcopy(hoja['grafcets'])
        return [{'refs':hoja['refs'],'porcentaje':max(50,min(200,100/float(hoja['ajustes']['escala']))),'offset_mm':[float(x) for x in hoja['ajustes']['offset_mm']]}] if hoja['refs'] else []

    def modelo_hoja(self,hoja=None):
        from .hojas import dibujo_vinculado
        graficos=self.graficos if hoja is None else self.graficos_hoja(hoja)
        refs=list(dict.fromkeys(r for g in graficos for r in g['refs']))
        modelo=dibujo_vinculado(self.ventana.edicion,refs)
        hojas=self.ventana.edicion.ed.sheet_links()
        modelo['_numero_hoja']=next((i+1 for i,h in enumerate(hojas) if h['id']==(self.hoja_id if hoja is None else hoja['id'])),1);modelo['_total_hojas']=len(hojas)
        modelo['_graficos']=[dict(g,modelo=dibujo_vinculado(self.ventana.edicion,g['refs'])) for g in graficos]
        return modelo

    def navegacion(self):
        if not self.editor:return
        n=self.lista.count();i=self.lista.currentRow()
        self.editor.pagina.setText(f'Hoja {i+1} de {n}');self.editor.anterior.setEnabled(i>0);self.editor.siguiente.setEnabled(i<n-1)

    def pasar_hoja(self,delta):
        i=self.lista.currentRow()+delta
        if 0<=i<self.lista.count():self.lista.setCurrentRow(i)

    def nueva_hoja(self):
        from .hojas import CrearHoja
        e=self.ventana.edicion;d=CrearHoja(e,self);d.setWindowTitle('Añadir hoja al plano')
        try:
            if not d.exec():return
            self.aplicar();cfg=d.configuracion or d.valores();cfg.update(modo='escala',escala=1.,offset_mm=[0.,0.])
            ident=e.ed.add_plan_page(None,cfg,d.nombre.text().strip() or None);e.cambia();self.mostrar(ident);QTimer.singleShot(0,self,lambda:self.scroll_hojas.ensureWidgetVisible(self.b_hoja))
        finally:d.deleteLater()

    def traer(self):
        self.ventana.preparar_traer(self.hoja_id)

    def elegir_grafico(self,indice):
        if not self.editor or not self.graficos:return
        indice=max(0,min(indice,len(self.graficos)-1));self.editor.vista.capa=indice
        self.grafico_actual=indice
        if self.editor.vista.seleccionado:self.editor.propiedades.setCurrentWidget(self.propiedades_grafico)
        self.tamano.blockSignals(True);self.tamano.setValue(self.graficos[indice]['porcentaje']);self.tamano.blockSignals(False);self.editor.vista.update()

    def actualizar_grafico(self):
        self.editor.modelo=self.modelo_hoja();self.editor.actualizar()

    def cambiar_tamano(self,valor):
        if not self.editor or not self.graficos:return
        i=max(0,self.grafico_actual);anterior=self.graficos[i]['porcentaje'];self.graficos[i]['porcentaje']=valor
        self.actualizar_grafico()
        if self.editor.documento is None:
            self.graficos[i]['porcentaje']=anterior;self.actualizar_grafico();self.elegir_grafico(i)
            QMessageBox.warning(self,'Tamaño del GRAFCET','Ese tamaño no cabe en la zona de dibujo. Mueve el GRAFCET o elige una hoja mayor.');return
        self.aplicar()

    def centrar_grafico(self):
        if not self.editor or not self.editor.documento or not self.graficos:return
        i=max(0,self.grafico_actual);d=self.editor.documento.capas[i]
        actual=d.destino(0);centrado=d.ajustar_posicion(actual.translated(d.contenido.center()-actual.center()),actual);delta=centrado.topLeft()-actual.topLeft();offset=self.graficos[i]['offset_mm']
        self.colocar([float(offset[0])+delta.x(),float(offset[1])+delta.y()])

    def colocar(self,offset):
        if not self.graficos:return
        self.graficos[max(0,self.editor.vista.capa)]['offset_mm']=offset;self.actualizar_grafico();self.aplicar()

    def insertar(self,refs):
        import copy
        from .laminas import DocumentoHoja
        if not refs:raise ValueError('Selecciona elementos del GRAFCET')
        anterior=copy.deepcopy(self.graficos);e=self.ventana.edicion
        nuevo={'refs':list(dict.fromkeys(refs)),'porcentaje':100.,'offset_mm':[0.,0.]}
        self.graficos.append(nuevo)
        try:
            # Buscar un hueco sin cambiar el tamaño físico ni las selecciones existentes.
            cfg=self.editor.valores();d=DocumentoHoja(self.modelo_hoja(),{},cfg);r=d.capas[-1].destino(0);existentes=[c.destino(0).adjusted(-2,-2,2,2) for c in d.capas[:-1]]
            sitio=None
            for y in range(0,max(1,int(d.contenido.height()-r.height())+1),5):
                for x in range(0,max(1,int(d.contenido.width()-r.width())+1),5):
                    candidato=r.translated(x,y)
                    if d.posicion_valida(candidato) and not any(c.intersects(candidato) for c in existentes):sitio=[float(x),float(y)];break
                if sitio is not None:break
            if sitio is None:raise ValueError('No hay sitio libre para esta selección al 100 %. Añade otra hoja o mueve los GRAFCET existentes.')
            nuevo['offset_mm']=sitio;e.ed.set_page_graphics(self.hoja_id,self.graficos);e.cambia();self.mostrar(self.hoja_id);self.elegir_grafico(len(self.graficos)-1)
        except (ValueError,RuntimeError):self.graficos=anterior;raise
