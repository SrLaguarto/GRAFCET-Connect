"""Página de Planos integrada en la ventana: hojas, lienzo y propiedades."""
import copy
from PySide6.QtCore import Qt, QSize, QTimer, QEvent, QPointF, QRect, QRectF, QDate
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolBar, QToolButton, QFrame, QSplitter, QListView,
    QListWidget, QListWidgetItem, QComboBox, QMenu, QMessageBox, QInputDialog, QDoubleSpinBox, QScrollArea,
    QFormLayout, QPushButton, QStyledItemDelegate, QStyle, QSizePolicy,
)
from grafcet.laminas import FORMATOS, ajustes_lamina
from . import estilo
from .bloques import FlowLayout
from .laminas import DialogoLaminas, DocumentoHoja, exportar_pdf_documentos
from .planos_controles import ControlesPlanos, AVISO_NO_CABE

_ACTUAL=object()


def icono_planos():
    pix=QPixmap(32,32);pix.fill(Qt.GlobalColor.transparent);p=QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QColor(estilo.ACENTO),1.7))
    p.drawRect(6,3,21,26);p.drawRect(9,6,15,20);p.drawRect(14,21,10,5);p.drawLine(19,21,19,26);p.end()
    return QIcon(pix)


def estilo_planos() -> str:
    """Hoja v2 en tarjetas blancas sobre fondo gris frío para la pestaña Planos."""
    return (
        f"QWidget#paginaPlanos {{ background:{estilo.FONDO}; }}"
        f"QLabel#tituloPlanos {{ color:{estilo.TINTA}; font-family:{estilo.FAMILIA_TITULO};"
        f" font-size:{estilo.T_TITULO}px; font-weight:700; padding:0 2px; background:transparent; }}"
        f"QScrollArea#scrollHojasPlanos {{ background:{estilo.SUPERFICIE};"
        f" border:1px solid {estilo.BORDE}; border-radius:{estilo.R_M}px; }}"
        f"QScrollArea#scrollHojasPlanos > QWidget,"
        f" QScrollArea#scrollHojasPlanos > QWidget > QWidget {{ background:{estilo.SUPERFICIE}; }}"
        f"QWidget#lateralHojasPlanos {{ background:{estilo.SUPERFICIE}; }}"
        f"QLabel#sinHojasPlanos {{ color:{estilo.TINTA_3}; font-size:{estilo.T_PEQUENA}px; padding:18px 10px; background:transparent; }}"
        f"QListWidget#listaHojasPlanos {{ background:transparent; border:0; outline:0; }}"
        f"QToolBar#barraPlanos QFrame#barraZoomPlanos {{ background:{estilo.SUPERFICIE};"
        f" border:1px solid {estilo.BORDE}; border-radius:{estilo.R_M}px; }}"
        f"QToolBar#barraPlanos QFrame#barraZoomPlanos QToolButton {{ background:transparent; border:1px solid transparent;"
        f" border-radius:5px; color:{estilo.TINTA_2}; padding:0 6px; min-height:24px; min-width:24px; font-weight:600; }}"
        f"QToolBar#barraPlanos QFrame#barraZoomPlanos QToolButton:hover {{ background:{estilo.HOVER}; color:{estilo.TINTA}; }}"
        f"QToolBar#barraPlanos QFrame#barraZoomPlanos QToolButton:pressed {{ background:{estilo.PULSADO}; }}"
        f"QToolBar#barraPlanos QFrame#barraZoomPlanos QComboBox {{ background:transparent; border:1px solid transparent;"
        f" border-radius:5px; color:{estilo.ACENTO_OSCURO}; font-weight:600;"
        f" min-height:{max(28, estilo.ALTO_CONTROL) - 2}px; padding:0 22px 0 8px; }}"
        f"QToolBar#barraPlanos QFrame#barraZoomPlanos QComboBox:hover {{ background:{estilo.ACENTO_SUAVE}; }}"
        f"QToolBar#barraPlanos QFrame#barraZoomPlanos QComboBox:focus {{ border:1px solid {estilo.ACENTO_BORDE};"
        f" min-height:{max(28, estilo.ALTO_CONTROL) - 2}px; }}"
        f'QToolBar#barraPlanos QFrame#barraZoomPlanos QComboBox[tecl="true"]:focus {{ border:2px dashed {estilo.FOCO};'
        f" min-height:{max(28, estilo.ALTO_CONTROL) - 4}px; }}"
        f"QPushButton#botonAnadirHoja {{ background:{estilo.SUPERFICIE}; color:{estilo.ACENTO_OSCURO};"
        f" border:1px solid {estilo.ACENTO_BORDE}; border-radius:6px; font-weight:600; padding:0 10px; }}"
        f"QPushButton#botonAnadirHoja:hover {{ background:{estilo.ACENTO_SUAVE}; border-color:{estilo.ACENTO}; }}"
        f"QPushButton#botonAnadirHoja:pressed {{ background:{estilo.PULSADO}; }}"
        f"QPushButton#botonAnadirHoja:disabled {{ background:{estilo.SUPERFICIE_2}; color:{estilo.DESHABILITADO}; border-color:{estilo.BORDE}; }}"
        f"QWidget#cuerpoPlanos {{ background:transparent; }}"
        f"QFrame#tarjetaVaciaPlanos {{ background:{estilo.SUPERFICIE}; border:1px solid {estilo.BORDE_FUERTE};"
        f" border-radius:10px; }}"
        f"QLabel#iconoTarjetaPlanos {{ background:{estilo.ACENTO_SUAVE}; border:1px solid {estilo.ACENTO_BORDE};"
        f" border-radius:8px; }}"
        f"QLabel#tituloTarjetaPlanos {{ color:{estilo.TINTA}; font-family:{estilo.FAMILIA_TITULO}; font-size:15px; font-weight:700; padding:2px 0; background:transparent; }}"
        f"QLabel#descTarjetaPlanos {{ color:{estilo.TINTA_2}; font-size:{estilo.T_PEQUENA}px; padding:2px 0 6px 0; background:transparent; }}"
        f"QScrollArea#areaHojaPlanos {{ background:{estilo.MESA};"
        f" border:1px solid {estilo.BORDE}; border-radius:{estilo.R_M}px; }}"
        f"QScrollArea#areaHojaPlanos > QWidget,"
        f" QScrollArea#areaHojaPlanos > QWidget > QWidget {{ background:{estilo.MESA}; }}"
        f"QStackedWidget#panelPropiedadesPlanos {{ background:{estilo.SUPERFICIE};"
        f" border:1px solid {estilo.BORDE}; border-radius:{estilo.R_M}px; }}"
        f"QScrollArea#scrollPropiedadesPlanos, QScrollArea#scrollPropiedadesPlanos > QWidget,"
        f" QScrollArea#scrollPropiedadesPlanos > QWidget > QWidget, QWidget#panelHojaPlanos,"
        f" QWidget#propiedadesGraficoPlanos {{ background:{estilo.SUPERFICIE}; border:0; }}"
        f"QWidget#panelHojaPlanos QLabel, QWidget#propiedadesGraficoPlanos QLabel {{ background:transparent; }}"
        f"QLabel#seccionPropiedadesPlanos, QLabel#tituloPropiedadesGrafico {{ color:{estilo.ACENTO};"
        f" font-family:{estilo.FAMILIA_TITULO}; font-size:{estilo.T_SECCION}px;"
        f" font-weight:700; background:transparent; }}"
        f"QFrame#avisoDeshacerHoja {{ background:{estilo.SUPERFICIE};"
        f" border:1px solid {estilo.BORDE_FUERTE}; border-radius:{estilo.R_M}px; }}"
        f"QFrame#avisoDeshacerHoja QLabel {{ color:{estilo.TINTA}; background:transparent; }}"
        f"QWidget#paginaPlanos QSplitter::handle {{ background:transparent; width:8px; }}"
    )


class MesaVaciaPlanos(QWidget):
    """Lienzo vacío de Planos con rejilla de puntos y tarjeta centrada «+ Crear primera hoja»."""

    _TITULO_DEFECTO = "Todavía no hay hojas de plano"
    _DESC_DEFECTO = "Crea una hoja A4 con cajetín técnico para encajar, rotular y exportar tu GRAFCET."

    def __init__(self, al_crear):
        super().__init__()
        self.setObjectName("vacioPlanos")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(20, 20, 20, 20)
        raiz.addStretch(1)
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaVaciaPlanos")
        tarjeta.setMinimumWidth(340)
        tarjeta.setMaximumWidth(380)
        tl = QVBoxLayout(tarjeta)
        tl.setContentsMargins(24, 24, 24, 24)
        tl.setSpacing(12)
        icono = QLabel()
        icono.setObjectName("iconoTarjetaPlanos")
        icono.setFixedSize(40, 40)
        icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icono.setPixmap(icono_planos().pixmap(22, 22))
        tl.addWidget(icono, 0, Qt.AlignmentFlag.AlignCenter)
        self.etiqueta_titulo = QLabel(self._TITULO_DEFECTO)
        self.etiqueta_titulo.setObjectName("tituloTarjetaPlanos")
        self.etiqueta_titulo.setWordWrap(True)
        self.etiqueta_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.addWidget(self.etiqueta_titulo)
        self.etiqueta_desc = QLabel(self._DESC_DEFECTO)
        self.etiqueta_desc.setObjectName("descTarjetaPlanos")
        self.etiqueta_desc.setWordWrap(True)
        self.etiqueta_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.addWidget(self.etiqueta_desc)
        self.b_crear_primera = QPushButton("+ Crear primera hoja")
        self.b_crear_primera.setProperty("primario", True)
        self.b_crear_primera.clicked.connect(al_crear)
        tl.addWidget(self.b_crear_primera, 0, Qt.AlignmentFlag.AlignCenter)
        self.escalar()
        raiz.addWidget(tarjeta, 0, Qt.AlignmentFlag.AlignCenter)
        raiz.addStretch(1)

    def escalar(self):
        self.b_crear_primera.setFixedHeight(estilo.ALTO_CONTROL)
        fm = self.etiqueta_desc.fontMetrics()
        ancho_txt = max(220, 340 - 48)
        caja = fm.boundingRect(QRect(0, 0, ancho_txt, 1000), int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap), self.etiqueta_desc.text())
        self.etiqueta_desc.setMinimumHeight(caja.height() + 14)

    def text(self):
        return self.etiqueta_titulo.text()

    def setText(self, texto):
        es_defecto = texto.startswith("Todavía no hay hojas")
        self.etiqueta_titulo.setText(self._TITULO_DEFECTO if es_defecto else texto)
        self.etiqueta_desc.setVisible(es_defecto)
        self.escalar()

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        p.setBrush(QColor(estilo.MESA))
        p.setPen(QPen(QColor(estilo.BORDE), 1))
        p.drawRoundedRect(r, estilo.R_M, estilo.R_M)
        p.setClipRect(r.adjusted(2, 2, -2, -2))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#c6d2df"))
        paso = 20
        for x in range(paso // 2, self.width(), paso):
            for y in range(paso // 2, self.height(), paso):
                p.drawEllipse(QPointF(x, y), 1.1, 1.1)
        p.end()


class MiniaturaHoja(QStyledItemDelegate):
    """Tarjeta medida y pintada con la misma fuente, independiente del estilo nativo."""
    def sizeHint(self,opcion,indice):
        ancho=max(128,self.parent().viewport().width())
        texto=opcion.fontMetrics.boundingRect(QRect(0,0,ancho-16,10000),Qt.TextFlag.TextWordWrap,indice.data() or '')
        return QSize(ancho,8+82+6+texto.height()+8)

    def paint(self,p,opcion,indice):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        r=opcion.rect
        caja=QRectF(r).adjusted(2.5,2.5,-2.5,-2.5)
        if opcion.state & QStyle.StateFlag.State_Selected:
            p.setBrush(QColor(estilo.ACENTO_SUAVE))
            p.setPen(QPen(QColor(estilo.ACENTO_BORDE),1))
            p.drawRoundedRect(caja,estilo.R_S,estilo.R_S)
        elif opcion.state & QStyle.StateFlag.State_MouseOver:
            p.setBrush(QColor(estilo.HOVER))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(caja,estilo.R_S,estilo.R_S)
        icono=indice.data(Qt.ItemDataRole.DecorationRole)
        if icono:icono.paint(p,QRect(r.center().x()-58,r.top()+8,116,82),Qt.AlignmentFlag.AlignCenter)
        p.setFont(opcion.font);p.setPen(opcion.palette.text().color())
        texto=QRect(r.left()+8,r.top()+96,r.width()-16,r.height()-104)
        p.drawText(texto,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop|Qt.TextFlag.TextWordWrap,indice.data() or '')
        p.restore()


class PaginaPlanos(QWidget):
    def __init__(self,ventana):
        super().__init__();self.ventana=ventana;self.editor=None;self.origen=None;self.hoja_id=None
        self.setObjectName("paginaPlanos")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self._hoja_base = ""
        self.setStyleSheet(estilo_planos())
        self.aplicando=False;self.cargando=False;self.automatico=True;self.factor_zoom=1.;self.graficos=[];self.pan=None;self.grafico_actual=0
        self._habilitadas = {}
        self._portapapeles_texto = None
        self._pegados_consecutivos = 0
        self.parpadeos_hoja=0
        self.t_hoja=QTimer(self)
        self.t_hoja.setInterval(350)
        self.t_hoja.timeout.connect(self._paso_parpadeo_hoja)
        self.lista_timer=QTimer(self);self.lista_timer.setSingleShot(True);self.lista_timer.setInterval(0);self.lista_timer.timeout.connect(self.ajustar_lista)
        self.dimension_timer=QTimer(self);self.dimension_timer.setSingleShot(True);self.dimension_timer.setInterval(0);self.dimension_timer.timeout.connect(self.dimensionar)
        self.guardar_timer=QTimer(self);self.guardar_timer.setSingleShot(True);self.guardar_timer.setInterval(400);self.guardar_timer.timeout.connect(self.aplicar)
        raiz=QVBoxLayout(self);raiz.setContentsMargins(estilo.E3,estilo.E2,estilo.E3,estilo.E3);raiz.setSpacing(estilo.E2)
        self.controles = ControlesPlanos(self, raiz)
        self.titulo = QLabel("Planos"); self.titulo.hide()
        self.divisor=QSplitter(Qt.Orientation.Horizontal);raiz.addWidget(self.divisor,1)
        lateral=QWidget();lateral.setObjectName("lateralHojasPlanos");lateral.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True);l=QVBoxLayout(lateral);l.setContentsMargins(0,0,0,8);l.setSpacing(6)
        cab_hojas=QFrame();cab_hojas.setObjectName("cabeceraPanel");cab_hojas.setFixedHeight(36);chl=QHBoxLayout(cab_hojas);chl.setContentsMargins(10,0,10,0);chl.setSpacing(6)
        t_hojas=QLabel("Hojas");t_hojas.setObjectName("tituloPanel");self.titulo_hojas=t_hojas;self.l_cont_hojas=QLabel("0");self.l_cont_hojas.setObjectName("badgePanel")
        chl.addWidget(t_hojas);chl.addWidget(self.l_cont_hojas);chl.addStretch(1);l.addWidget(cab_hojas)
        self.l_sin_hojas=QLabel("Sin hojas todavía");self.l_sin_hojas.setObjectName("sinHojasPlanos");self.l_sin_hojas.setWordWrap(True);self.l_sin_hojas.setAlignment(Qt.AlignmentFlag.AlignCenter);l.addWidget(self.l_sin_hojas)
        self.lista=QListWidget();self.lista.setObjectName("listaHojasPlanos");self.lista.setViewMode(QListView.ViewMode.ListMode);self.lista.setItemDelegate(MiniaturaHoja(self.lista));self.lista.installEventFilter(self);self.lista.setFlow(QListView.Flow.TopToBottom);self.lista.setWrapping(False);self.lista.setMovement(QListView.Movement.Static);self.lista.setResizeMode(QListView.ResizeMode.Adjust);self.lista.setSpacing(0);self.lista.setIconSize(QSize(116,82));self.lista.setWordWrap(True);self.lista.setMinimumWidth(140);self.lista.setMaximumWidth(205);self.lista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        caja_lista=QHBoxLayout();caja_lista.setContentsMargins(8,0,8,0);caja_lista.addWidget(self.lista);l.addLayout(caja_lista)
        self.b_hoja=QPushButton("+ Añadir otra hoja");self.b_hoja.setObjectName("botonAnadirHoja");self.b_hoja.setVisible(False);self.b_hoja.clicked.connect(self.nueva_hoja)
        caja_btn=QHBoxLayout();caja_btn.setContentsMargins(8,2,8,0);caja_btn.addWidget(self.b_hoja);l.addLayout(caja_btn)
        l.addStretch(1)
        self.scroll_hojas=QScrollArea();self.scroll_hojas.setObjectName("scrollHojasPlanos");self.scroll_hojas.setFocusPolicy(Qt.FocusPolicy.NoFocus);self.scroll_hojas.setWidgetResizable(True);self.scroll_hojas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.scroll_hojas.setMinimumWidth(160);self.scroll_hojas.setMaximumWidth(215);self.scroll_hojas.setWidget(lateral);self.divisor.addWidget(self.scroll_hojas);self.cuerpo=QWidget();self.cuerpo.setObjectName("cuerpoPlanos");self.cuerpo.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True);self.layout_editor=QVBoxLayout(self.cuerpo);self.layout_editor.setContentsMargins(0,0,0,0)
        self._crear_aviso_deshacer()
        self.vacio=MesaVaciaPlanos(self.nueva_hoja);self.layout_editor.addWidget(self.vacio)
        self.divisor.addWidget(self.cuerpo);self.divisor.setStretchFactor(0,0);self.divisor.setStretchFactor(1,1);self.divisor.setSizes([160,1100])
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.lista.customContextMenuRequested.connect(self.menu_hoja)
        self.lista.currentRowChanged.connect(self.elegir);self.actualizar_acciones()
        self.estilo_boton_hoja()

    def _crear_aviso_deshacer(self):
        self.aviso_deshacer_hoja = QFrame(self.cuerpo)
        self.aviso_deshacer_hoja.setObjectName("avisoDeshacerHoja")
        self.aviso_deshacer_hoja.hide()
        fila = QHBoxLayout(self.aviso_deshacer_hoja)
        fila.setContentsMargins(12, 6, 12, 6)
        fila.setSpacing(estilo.E2)
        self.l_deshacer_hoja = QLabel()
        self.l_deshacer_hoja.setWordWrap(True)
        fila.addWidget(self.l_deshacer_hoja, 1)
        self.b_deshacer_hoja = QPushButton("Deshacer")
        self.b_deshacer_hoja.setToolTip("Recupera la hoja eliminada (Ctrl+Z)")
        self.b_deshacer_hoja.setFixedHeight(estilo.ALTO_CONTROL)
        from .campos_medidos import ajustar_boton
        ajustar_boton(self.b_deshacer_hoja)
        self.b_deshacer_hoja.clicked.connect(self._deshacer_hoja_eliminada)
        fila.addWidget(self.b_deshacer_hoja)
        self.layout_editor.addWidget(self.aviso_deshacer_hoja)
        self.deshacer_hoja_timer = QTimer(self)
        self.deshacer_hoja_timer.setSingleShot(True)
        self.deshacer_hoja_timer.setInterval(8000)
        self.deshacer_hoja_timer.timeout.connect(self._ocultar_deshacer_hoja)

    def _mostrar_deshacer_hoja(self, nombre):
        self.l_deshacer_hoja.setText(f"Hoja «{nombre}» eliminada.")
        self.aviso_deshacer_hoja.show()
        self.deshacer_hoja_timer.start()

    def _ocultar_deshacer_hoja(self):
        self.deshacer_hoja_timer.stop()
        self.aviso_deshacer_hoja.hide()

    def _deshacer_hoja_eliminada(self):
        self._ocultar_deshacer_hoja()
        self.ventana.historial_plano(False)

    def escalar(self, hoja_base: str | None = None):
        """Actualiza la hoja de estilos y los mínimos con la escala de la ventana."""
        if hoja_base is not None:
            self._hoja_base = hoja_base
        self.setStyleSheet((self._hoja_base + "\n" if self._hoja_base else "") + estilo_planos())
        self.titulo.setMinimumHeight(estilo.ALTO_CONTROL)
        self.b_hoja.setFixedHeight(estilo.ALTO_CONTROL)
        self.b_deshacer_hoja.setFixedHeight(estilo.ALTO_CONTROL)
        from .campos_medidos import ajustar_boton
        ajustar_boton(self.b_deshacer_hoja)
        self.vacio.escalar()
        self.estilo_boton_hoja()

    def compactar(self,on):
        """Mantiene Traer y zoom en una fila; contenido y salida secundarios pasan al menú Más."""
        on=bool(on)
        if on!=self.compacto:
            self.compacto=on;self._aplicar_compacto()

    def _aplicar_compacto(self):
        self.controles.compactar()

    def liberar_editor(self):
        if self.editor:
            self.editor.propiedades.removeWidget(self.propiedades_grafico);self.propiedades_grafico.setParent(self);self.propiedades_grafico.hide()
            self.editor.modificado.disconnect(self.cambiado);self.layout_editor.removeWidget(self.editor);self.editor.deleteLater();self.editor=None

    def ajustar_lista(self):
        lista=self.lista;lista.doItemsLayout();n=lista.count();lista.setVisible(bool(n))
        self.l_sin_hojas.setVisible(not bool(n));self.l_cont_hojas.setText(str(n))
        self.b_hoja.setVisible(bool(n) and self.ventana.edicion is not None)
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
        item = self.lista.currentItem()
        if item is None or self.origen is not self.ventana.edicion:
            return
        ident = item.data(Qt.ItemDataRole.UserRole)
        nombre = item.text()
        fila = self.lista.currentRow()
        e = self.origen
        self.aplicar()
        self.liberar_editor()
        if self.ventana.destino_traer == (e, ident):
            self.ventana.destino_traer = None
            self.ventana.aviso_traer.hide()
        e.ed.delete_sheet(ident)
        e.cambia()
        hojas = e.ed.sheet_links()
        destino = hojas[min(fila, len(hojas) - 1)]["id"] if hojas else None
        self.mostrar(destino)
        if self.ventana.modo == "editar":
            self._mostrar_deshacer_hoja(nombre)
        if destino is not None:
            self.lista.setFocus()
        else:
            self.vacio.b_crear_primera.setFocus()

    def mover_hoja(self, delta):
        item = self.lista.currentItem()
        if item is None or self.origen is not self.ventana.edicion:
            return
        ident = item.data(Qt.ItemDataRole.UserRole)
        e = self.origen
        self.aplicar()
        if e.ed.move_sheet(ident, delta):
            e.cambia()
            self.mostrar(ident)
            self.lista.setFocus()

    def eliminar_grafico(self):
        if not self.editor or not self.editor.vista.seleccionado or not self.graficos:
            return
        if self.ventana.modo != "editar":
            return
        i = self.editor.vista.capa
        if not 0 <= i < len(self.graficos):
            return
        self.aplicar()
        del self.graficos[i]
        self.editor.vista.seleccionado = False
        self.grafico_actual = max(0, min(i, len(self.graficos) - 1))
        self.editor.vista.capa = self.grafico_actual if self.graficos else -1
        if self.graficos:
            self.tamano.blockSignals(True)
            self.tamano.setValue(self.graficos[self.grafico_actual]["porcentaje"])
            self.tamano.blockSignals(False)
        if not self.editor.editando_plantilla:
            self.editor.propiedades.setCurrentIndex(0)
        self.actualizar_grafico()
        self.guardar_timer.stop()
        e = self.ventana.edicion
        e.ed.set_page_graphics(self.hoja_id, self.graficos)
        e.cambia()
        self.ventana._titulo_ventana()
        self.actualizar_acciones()
        self.actualizar_titulo()
        self.miniatura()

    def mostrar(self, ident=_ACTUAL):
        if self.cargando:
            return
        self._ocultar_deshacer_hoja()
        e = self.ventana.edicion
        if ident is _ACTUAL:
            ident = self.hoja_id if self.origen is e else None
        if self.origen is not e:
            self.guardar_timer.stop()
            self.liberar_editor()
            self.hoja_id = None
            self.graficos = []
            self.pan = None
        self.aplicar()
        self.cargando = True
        try:
            self.origen = e
            self.lista.blockSignals(True)
            self.lista.clear()
            hojas = e.ed.sheet_links() if e else []
            for h in hojas:
                item = QListWidgetItem(icono_planos(), h["nombre"])
                item.setData(Qt.ItemDataRole.UserRole, h["id"])
                self.lista.addItem(item)
            if not any(h["id"] == ident for h in hojas):
                ident = hojas[0]["id"] if hojas else None
            fila = next(
                (i for i in range(self.lista.count()) if self.lista.item(i).data(Qt.ItemDataRole.UserRole) == ident),
                -1,
            )
            self.ajustar_lista()
            self.lista.setCurrentRow(fila)
            self.lista.blockSignals(False)
            self.cargar(ident)
        finally:
            self.cargando = False
        self.estilo_boton_hoja()

    ACENTO_HOJA = estilo.ACENTO  # el acento de la interfaz (el de los títulos de esta página)
    ACENTO_HOJA_CLARO = estilo.PARPADEO

    def estilo_boton_hoja(self, fase=True):
        """«+ Crear primera hoja» es el botón principal (fondo de acento, texto blanco) y parpadea mientras no hay
        hojas; con hojas, el botón lateral queda en estilo secundario limpio."""
        sin_hojas = self.lista.count() == 0 and self.ventana.edicion is not None
        self.b_hoja.setStyleSheet("")
        if not sin_hojas:
            self.t_hoja.stop()
            self.vacio.b_crear_primera.setStyleSheet("")
            return
        fondo = self.ACENTO_HOJA if fase else self.ACENTO_HOJA_CLARO
        self.vacio.b_crear_primera.setStyleSheet(
            f'QPushButton {{ background:{fondo}; color:white; font-weight:600; border:1px solid {self.ACENTO_HOJA}; '
            f'border-radius:6px; padding:0 14px; min-height:{estilo.ALTO_CONTROL - 2}px }}')

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
                self.graficos=[];self.titulo.setText('Planos');self.vacio.setText('Todavía no hay hojas de plano');self.vacio.show();self.actualizar_acciones();return
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
            self.editor = DialogoLaminas(
                modelo, estado, cfg, guardar, self.cuerpo, self.ventana.diagrama.dependencias, integrado=True
            )
            self.editor.documentos_proyecto = self.documentos_hojas
            self.editor.centrar = self.centrar_grafico
            self.editor.vista.colocar = self.colocar
            self.editor.vista.elegir_capa = self.elegir_grafico
            self.editor.vista.eliminar_grafico = self.eliminar_grafico
            self.editor.vista.editable = self.ventana.modo == "editar"
            self.editor.vista.menu_contextual = self._abrir_menu_lienzo
            self.editor.vista.accion_portapapeles = self.portapapeles_texto
            self.editor.seleccion_texto_cambiada.connect(self.ventana._actualizar_portapapeles)
            self.editor.propiedades.addWidget(self.propiedades_grafico)
            self.editor.nombre_plano=nombre;self.layout_editor.addWidget(self.editor);self.vacio.hide()
            self.editor.modificado.connect(self.cambiado);self.editor.area.viewport().installEventFilter(self);self.editor.vista.installEventFilter(self)
            for w in (self.editor.modo,self.editor.escala,self.editor.unidad):
                w.hide();w.parentWidget().layout().labelForField(w).hide()
            self.elegir_grafico(0)
            self.navegacion()
            self.actualizar_titulo()
            self.actualizar_acciones()
            self.miniatura(True)
            self._aplicar_compacto()
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
        e = self.ventana.edicion
        ed = self.editor
        editar = self.ventana.modo == "editar"
        estado = {
            self.a_hoja: e is not None,
            self.vacio.b_crear_primera: e is not None,
            self.a_nueva: ed is not None and editar,
            self.tamano: ed is not None and bool(self.graficos),
            self.a_exportar: ed is not None and ed.b_exportar.isEnabled(),
            self.a_imprimir: ed is not None and ed.b_imprimir.isEnabled(),
            self.a_centrar: ed is not None and ed.b_centrar.isEnabled(),
            self.a_texto: ed is not None and editar,
        }
        self._habilitadas = {accion: bool(activo) for accion, activo in estado.items()}
        for control, activo in estado.items():
            control.setEnabled(bool(activo))
        if ed is not None:
            ed.vista.editable = editar
        if self.ventana.panel_planos is self:
            self.ventana._actualizar_portapapeles()

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
            if t and vista.documento is not None:
                sobre_texto = any(i.contains(i.mapFromScene(vista.punto_hoja(event.position()))) for i in t.items)
                if vista.nuevo_texto or (vista.zona and t.vista.zona) or sobre_texto:
                    return False
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

    def _cargar_tecnica_limpia(self, formato, orientacion, margen):
        from grafcet.plantillas_tecnicas import plantilla_tecnica, sin_rotulos_auxiliares
        from .carpetas import predeterminada
        try:
            plantilla = sin_rotulos_auxiliares(predeterminada(formato, orientacion, margen))
            plantilla["primitives"] = [
                t for t in plantilla["primitives"]
                if not (t.get("omit_empty") and t.get("field") in ("proyecto", "revision", "hoja", "libre"))
            ]
            return plantilla
        except (OSError, ValueError):
            w, h = FORMATOS.get(formato, FORMATOS["A4"])
            w, h = (h, w) if orientacion == "horizontal" else (w, h)
            return plantilla_tecnica(w, h, margen)

    def _plantilla_heredada(self, base):
        if base is None:
            return self._cargar_tecnica_limpia("A4", "vertical", 10.)
        formato = base["formato"]
        orientacion = base["orientacion"]
        margen = float(base["margen_mm"])
        previa = base.get("plantilla")
        propia = previa is not None and (previa.get("source") != "GrafConnect" or previa.get("zone") is not None)
        if propia:
            return copy.deepcopy(previa)
        return self._cargar_tecnica_limpia(formato, orientacion, margen)

    def _ajustes_nueva_hoja(self, e):
        hojas = e.ed.sheet_links()
        if self.editor is not None:
            base = self.editor.valores()
        elif hojas:
            activa = next((h for h in hojas if h["id"] == self.hoja_id), hojas[-1])
            base = copy.deepcopy(activa["ajustes"])
        else:
            base = None
        formato = base["formato"] if base is not None else "A4"
        orientacion = base["orientacion"] if base is not None else "vertical"
        margen = float(base["margen_mm"]) if base is not None else 10.
        campos = copy.deepcopy(base["campos"] if base is not None else e.ed.sheet_settings()["campos"])
        por_defecto = (
            ("titulo", e.titulo),
            ("proyecto", e.titulo),
            ("fecha", QDate.currentDate().toString("yyyy-MM-dd")),
        )
        for clave, valor in por_defecto:
            if not campos.get(clave):
                campos[clave] = valor
        return ajustes_lamina({
            "formato": formato,
            "orientacion": orientacion,
            "margen_mm": margen,
            "modo": "escala",
            "escala": 1.,
            "offset_mm": [0., 0.],
            "plantilla": self._plantilla_heredada(base),
            "campos": campos,
        })

    def _nombre_nueva_hoja(self, hojas):
        usados = {h["nombre"] for h in hojas}
        n = len(hojas) + 1
        while f"Hoja {n}" in usados:
            n += 1
        return f"Hoja {n}"

    def nueva_hoja(self):
        e = self.ventana.edicion
        if e is None:
            return
        self._ocultar_deshacer_hoja()
        self.aplicar()
        cfg = self._ajustes_nueva_hoja(e)
        nombre = self._nombre_nueva_hoja(e.ed.sheet_links())
        ident = e.ed.add_plan_page(None, cfg, nombre)
        e.cambia()
        self.mostrar(ident)
        QTimer.singleShot(
            0,
            self,
            lambda: self.scroll_hojas.verticalScrollBar().setValue(self.scroll_hojas.verticalScrollBar().maximum()),
        )

    def documentos_hojas(self):
        """Construye los documentos de todas las hojas del proyecto en orden."""
        self.aplicar()
        e = self.ventana.edicion
        hojas = e.ed.sheet_links() if e else []
        if not hojas:
            return [self.editor.documento] if self.editor and self.editor.documento else []
        estado = {} if self.ventana.modo == "editar" or self.ventana.v is None else self.ventana.v.state()
        dependencias = self.ventana.diagrama.dependencias
        docs = []
        for h in hojas:
            if self.editor and self.editor.documento and h["id"] == self.hoja_id:
                docs.append(self.editor.documento)
                continue
            try:
                docs.append(DocumentoHoja(self.modelo_hoja(h), estado, h["ajustes"], dependencias))
            except ValueError as exc:
                raise ValueError(f"La hoja «{h['nombre']}» no se puede exportar: {exc}") from exc
        return docs

    def exportar_pdf_proyecto(self, ruta, solo_actual=False):
        """Exporta a PDF todas las hojas del proyecto o solo la activa."""
        if solo_actual and self.editor and self.editor.documento:
            docs = [self.editor.documento]
        else:
            docs = self.documentos_hojas()
        titulo = self.editor.ajustes["campos"]["titulo"] if self.editor else ""
        return exportar_pdf_documentos(docs, ruta, titulo)

    def estado_portapapeles(self):
        """Indica si hay un texto seleccionado para copiar/cortar y si hay uno en portapapeles para pegar."""
        if self.editor is None or self.editor.editor_textos is None or self.ventana.modo != "editar":
            return False, False
        return self.editor.editor_textos.actual is not None, self._portapapeles_texto is not None

    def portapapeles_texto(self, operacion, punto=None):
        """Copia, corta o pega un texto sobre la hoja activa de forma reversible."""
        if self.editor is None or self.editor.editor_textos is None or self.ventana.modo != "editar":
            return False
        t = self.editor.editor_textos
        if operacion in ("copiar", "cortar"):
            copia = t.copiar_actual()
            if copia is None:
                return False
            self._portapapeles_texto = copia
            self._pegados_consecutivos = 0 if operacion == "cortar" else 1
            if operacion == "cortar":
                t.eliminar()
            self.ventana._actualizar_portapapeles()
            return True
        if operacion != "pegar" or self._portapapeles_texto is None:
            return False
        nuevo = copy.deepcopy(self._portapapeles_texto)
        ancho, alto = self.editor.plantilla["size"]
        if punto is not None:
            x, y = float(punto.x()), float(punto.y())
        else:
            paso = 5.0 * self._pegados_consecutivos
            x = float(nuevo["x"]) + paso
            y = float(nuevo["y"]) + paso
            self._pegados_consecutivos += 1
        nuevo["x"] = max(1.0, min(max(1.0, float(ancho) - 1.0), x))
        nuevo["y"] = max(1.0, min(max(1.0, float(alto) - 1.0), y))
        self.editor.vista.seleccionado = False
        t.insertar_texto(nuevo)
        self.editor.vista.setFocus()
        self.editor.vista.update()
        self.ventana._actualizar_portapapeles()
        return True

    def crear_menu_lienzo(self, pos_vista):
        """Construye el menú contextual del lienzo de Planos según el elemento bajo el puntero."""
        if self.editor is None or self.editor.documento is None or self.editor.documento.total != 1:
            return None
        vista = self.editor.vista
        t = self.editor.editor_textos
        punto = vista.punto_hoja(QPointF(pos_vista))
        editable = self.ventana.modo == "editar"
        item = next((i for i in reversed(t.items) if i.contains(i.mapFromScene(punto))), None) if t else None
        if item is not None:
            return self._menu_texto_lienzo(vista, t, item, punto, editable)
        d = self.editor.documento
        capa = next((i for i in reversed(range(len(d.capas))) if d.capas[i].destino(0).contains(punto)), -1)
        if capa >= 0:
            return self._menu_grafcet_lienzo(vista, t, capa, punto, editable)
        return self._menu_vacio_lienzo(vista, t, punto, editable)

    def _menu_texto_lienzo(self, vista, t, item, punto, editable):
        vista.seleccionado = False
        t.elegir(t.items.index(item))
        vista.update()
        menu = QMenu(vista)
        a_cortar = menu.addAction("Cortar", lambda: self.portapapeles_texto("cortar"))
        a_copiar = menu.addAction("Copiar", lambda: self.portapapeles_texto("copiar"))
        destino = QPointF(punto.x() + 5.0, punto.y() + 5.0)
        a_pegar = menu.addAction("Pegar", lambda: self.portapapeles_texto("pegar", destino))
        menu.addSeparator()
        a_eliminar = menu.addAction("Eliminar", t.eliminar)
        for accion in (a_cortar, a_copiar, a_eliminar):
            accion.setEnabled(editable)
        a_pegar.setEnabled(editable and self._portapapeles_texto is not None)
        return menu

    def _menu_grafcet_lienzo(self, vista, t, capa, punto, editable):
        if t is not None:
            t.elegir(-1)
        vista.capa = capa
        vista.seleccionado = True
        self.elegir_grafico(capa)
        menu = QMenu(vista)
        a_centrar = menu.addAction("Centrar", self.centrar_grafico)
        a_centrar.setEnabled(self.editor.b_centrar.isEnabled())
        a_pegar = menu.addAction("Pegar", lambda: self.portapapeles_texto("pegar", punto))
        a_pegar.setEnabled(editable and self._portapapeles_texto is not None)
        menu.addSeparator()
        a_quitar = menu.addAction("Eliminar del plano", self.eliminar_grafico)
        a_quitar.setEnabled(editable)
        return menu

    def _menu_vacio_lienzo(self, vista, t, punto, editable):
        if t is not None:
            t.elegir(-1)
        vista.seleccionado = False
        if not self.editor.editando_plantilla:
            self.editor.propiedades.setCurrentIndex(0)
        vista.update()
        menu = QMenu(vista)
        a_pegar = menu.addAction("Pegar", lambda: self.portapapeles_texto("pegar", punto))
        a_pegar.setEnabled(editable and self._portapapeles_texto is not None)
        a_texto = menu.addAction("Añadir texto", self.editor.anadir_texto)
        a_texto.setEnabled(editable)
        return menu

    def _abrir_menu_lienzo(self, pos_vista, pos_global):
        menu = self.crear_menu_lienzo(pos_vista)
        if menu is not None:
            menu.exec(pos_global)

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
            cfg = self.editor.valores()
            try:
                d = DocumentoHoja(self.modelo_hoja(), {}, cfg)
            except ValueError as exc:
                from .planos_controles import AVISO_NO_CABE
                raise ValueError(AVISO_NO_CABE) from exc
            r = d.capas[-1].destino(0)
            existentes = [c.destino(0).adjusted(-2, -2, 2, 2) for c in d.capas[:-1]]
            sitio=None
            for y in range(0,max(1,int(d.contenido.height()-r.height())+1),5):
                for x in range(0,max(1,int(d.contenido.width()-r.width())+1),5):
                    candidato=r.translated(x,y)
                    if d.posicion_valida(candidato) and not any(c.intersects(candidato) for c in existentes):sitio=[float(x),float(y)];break
                if sitio is not None:break
            if sitio is None:raise ValueError('No hay sitio libre para esta selección al 100 %. Añade otra hoja o mueve los GRAFCET existentes.')
            nuevo['offset_mm']=sitio;e.ed.set_page_graphics(self.hoja_id,self.graficos);e.cambia();self.mostrar(self.hoja_id);self.elegir_grafico(len(self.graficos)-1)
        except (ValueError,RuntimeError):self.graficos=anterior;raise
