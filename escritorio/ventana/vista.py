"""Vista: la construcción de la interfaz, los paneles plegables, los divisores, la escala, la pantalla completa y la cabecera."""
from __future__ import annotations

from .. import estilo
from ..diagrama import VistaDiagrama
from ..flotantes import GestorFlotantes
from ..navegacion import Navegacion
from ..paneles import (BandaModo, CajaSeccion, DelegadoNombres, DivisorPlegable, EtiquetaAyuda, EtiquetaElidida,
                       EtiquetaGrupos, PanelPlegable, PilaActual, ReparteColumnas, TituloSeccion)
from ..propiedades import Paleta, PanelPropiedades
from ..variables import PanelVariables
from typing import Any
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QScrollArea, QSizePolicy, QTableWidget, QVBoxLayout, QWidget)
from .constantes import (ALTO_TRAZA, ANCHO_DERECHO, ANCHO_DERECHO_BASE, ARRIBA_CAJA, ARRIBA_VARIABLES, AVISO, ESPERA_ARRANQUE,
                         ESPERA_ESCALA, HUECO_FRANJA, NOMBRE_MIN_TABLA, UMBRAL_DERECHO)
from .simulacion import _DelegadoEtapasConsola, _DelegadoNombrePapel, _DelegadoPastillaConsola
from .widgets import (_AjustaBanda, _AjustaCabecera, _BotonEntrada, _DelegadoAbreviado, _DelegadoValorConsola,
                      _FirmaEstado, _SalidaRaton, _VigilaAlto)


class VistaVentana:
    """Vista: la construcción de la interfaz, los paneles plegables, los divisores, la escala, la pantalla completa y la cabecera. Sin estado propio: usa los atributos de `Ventana` (la fachada) y llama a los demás métodos a través de `self`."""

    def _caja(self, titulo: str) -> tuple[QWidget, QVBoxLayout]:
        box = QWidget()
        box.setObjectName("seccionConsola")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, estilo.E1)
        lay.setSpacing(estilo.E1)
        etiq = QLabel(titulo.upper())
        etiq.setObjectName("tituloConsola")
        lay.addWidget(etiq)
        self.lado.addWidget(box)
        self._cajas_lado = getattr(self, "_cajas_lado", []) + [box]
        return box, lay

    def _interfaz(self) -> None:
        izq = QWidget()
        izq.setObjectName("panelDibujo")
        il = QVBoxLayout(izq)
        il.setContentsMargins(10, 8, 10, 4)
        il.setSpacing(4)
        self._margenes_dibujo = (10, 8, 10, 4)
        izq.installEventFilter(_AjustaCabecera(izq, self))
        cab = QHBoxLayout()
        cab.setSpacing(estilo.E2)
        self._cab = cab
        from ..cabecera_favoritos import EstadoModo
        self.estado = EstadoModo()
        il.addLayout(cab)
        self.ayuda = EtiquetaAyuda(2)
        self.ayuda.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: {estilo.T_PEQUENA}px")
        cab.addWidget(self.ayuda,1)
        self.ayuda_larga = QLabel()  # la ayuda entera, a todo el ancho de la tarjeta (solo desplegada)
        self.ayuda_larga.setObjectName("ayudaLarga")
        self.ayuda_larga.setWordWrap(True)
        self.ayuda_larga.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ayuda_larga.hide()
        self._ayuda_abierta = False
        from ..ayuda_pantalla import AyudaPantalla
        self.ayuda_pantalla = AyudaPantalla(self)
        self._estilo_ayuda()
        self.diagrama = VistaDiagrama()
        self.navegacion = Navegacion(self.diagrama)
        cab.addWidget(self.navegacion)
        ver_navegacion = self._accion("Navegación y filtros…", self.navegacion.abrir_opciones)
        next(a.menu() for a in self.menuBar().actions() if a.text()=="&Ver").addAction(ver_navegacion)
        il.addWidget(self.ayuda_larga)
        il.addWidget(self.diagrama, 1)
        # Panel inferior: al simular, la traza; al editar, las opciones de lo seleccionado
        self.traza = QListWidget()
        self.traza.setWordWrap(True)
        self.traza.setFrameShape(QFrame.Shape.NoFrame)
        self.traza.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        from ..traza_panel import CajaTraza, DelegadoTraza
        self.traza.setItemDelegate(DelegadoTraza(self.traza))
        caja_traza = CajaTraza()
        lay_traza = QVBoxLayout(caja_traza)
        lay_traza.setContentsMargins(0, 4, 0, 6)
        lay_traza.addWidget(self.traza)
        self._props = PanelPropiedades()
        self._props.setObjectName("panelPropiedadesFlotante")
        self._props.setParent(self)
        self._props.hide()
        self.inferior = PilaActual()
        self.inferior.addWidget(caja_traza)
        self.flot = GestorFlotantes(self)  # las propiedades flotantes (se crean al usarlas)
        self._leyenda: QDialog | None = None

        der = QWidget()
        der.setObjectName("consolaSimulacion")
        self.lado = QVBoxLayout(der)
        self.lado.setContentsMargins(10, estilo.E2, 10, estilo.E2)
        self.lado.setSpacing(estilo.E1)
        self.diag = QLabel()
        self.diag.setWordWrap(True)
        self.diag.setTextFormat(Qt.TextFormat.RichText)
        self.diag.setStyleSheet(f"border: 1px solid {estilo.ERROR}; background: {estilo.ERROR_FONDO}; color: {estilo.TINTA}; "
                                f"border-radius: {estilo.R_M}px; padding: {estilo.E2}px")
        self.lado.addWidget(self.diag)

        _, lay = self._caja("Entradas")
        self.l_ayuda_entradas = EtiquetaGrupos("Clic: pulsar · Ctrl: enclavar · Der.: tipo")
        self.l_ayuda_entradas.setToolTip("Clic: pulsar · Ctrl+clic: enclavar · Clic derecho: cambiar tipo")
        self.l_ayuda_entradas.setStyleSheet(
            f"color: {estilo.TINTA_3}; font-size: {max(11, estilo.T_PEQUENA - 1)}px; font-weight: 400"
        )
        lay.addWidget(self.l_ayuda_entradas)
        # Las entradas se desplazan por dentro de su caja, con un alto máximo (`_alto_entradas`) que deja ver al menos cuatro filas de
        # «Salidas y variables»: con muchas entradas, las salidas no quedan fuera de la vista
        self.cont_rejilla = QWidget()
        self.rejilla = QGridLayout(self.cont_rejilla)
        self.rejilla.setContentsMargins(0, 0, 0, 0)
        self.sc_entradas = QScrollArea()
        self.sc_entradas.setObjectName("scrollEntradas")
        self.sc_entradas.setWidgetResizable(True)
        self.sc_entradas.setFrameShape(QFrame.Shape.NoFrame)
        self.sc_entradas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sc_entradas.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sc_entradas.setWidget(self.cont_rejilla)
        self.sc_entradas.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # (se desplaza con la rueda y la barra; sus botones ya reciben el foco)
        self.sc_entradas.setStyleSheet("QScrollArea#scrollEntradas, QScrollArea#scrollEntradas > QWidget > QWidget { background: transparent; }")
        lay.addWidget(self.sc_entradas)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"color: {estilo.ERROR}")
        self.aviso.setVisible(False)  # sin texto no ocupa alto (se enseña solo cuando hay algo que avisar)
        lay.addWidget(self.aviso)

        _, lay = self._caja("Salidas y variables")
        # Las columnas a la vista: el ancho del panel es fijo, así que **manda la del nombre** (≥ 96 px, `ReparteColumnas`): las demás se
        # abrevian antes de que baje de ahí («Modo» pasa a «cont.»/«mem.»; «Estado», a «par.»/«cont.»/«venc.»), **ninguna desaparece**,
        # los nombres se parten por los «_» en las líneas que hagan falta y la tabla mide lo que sus filas: sin barras anidadas
        self.t_vars = self._tabla(["Variable", "Modo", "Valor", "Etapas"], (None, 46, 34, 58))
        self.t_vars.horizontalHeaderItem(1).setToolTip("Salida continua o memorizada")
        self.t_vars.setItemDelegateForColumn(1, _DelegadoAbreviado({"salida continua": "continua"}, self.t_vars,
                                                                   {"salida continua": "cont.", "memorizada": "mem."}))
        self.t_vars.horizontalHeaderItem(3).setToolTip(
            "Etapas cuyas acciones contribuyen a la salida")
        self.t_vars.horizontalHeader().abreviaturas = {"Etapas": "Etap."}
        self._del_vars = (_DelegadoNombrePapel(self.t_vars, (0,)), _DelegadoEtapasConsola(self.t_vars, (3,), lineas=2))
        self.t_vars.setItemDelegateForColumn(0, self._del_vars[0])
        self.t_vars.setItemDelegateForColumn(2, _DelegadoPastillaConsola(self.t_vars))
        self.t_vars.setItemDelegateForColumn(3, self._del_vars[1])
        lay.addWidget(self.t_vars)
        self.t_vars.currentCellChanged.connect(self._detalle_del_foco)
        self.c_temp, lay = self._caja("Temporizadores")
        self.t_temp = self._tabla(["Dónde", "Estado", "Lleva", "Consigna"], (None, 54, 36, 42))
        self.t_temp.horizontalHeaderItem(2).setToolTip("Tiempo transcurrido")
        self.t_temp.horizontalHeaderItem(3).setToolTip("Duración programada")
        self.t_temp.setItemDelegateForColumn(1, _DelegadoAbreviado({}, self.t_temp, {"parado": "par.", "contando": "cont.", "vencido": "venc."}))
        self.t_temp.horizontalHeader().abreviaturas = {"Estado": "Est.", "Consigna": "Cons."}
        self._del_temp = DelegadoNombres(self.t_temp, (0,))
        self.t_temp.setItemDelegateForColumn(0, self._del_temp)
        lay.addWidget(self.t_temp)
        self.t_temp.currentCellChanged.connect(self._detalle_del_foco)
        self._reparto = (ReparteColumnas(self.t_vars, 0, NOMBRE_MIN_TABLA, self._planes_vars, self._elegir_plan_vars,
                                         lambda: self.ajustar_tabla(self.t_vars), ideal=lambda: self._del_vars[0].ancho_para(2, self.t_vars.fontMetrics())),
                         ReparteColumnas(self.t_temp, 0, NOMBRE_MIN_TABLA, self._planes_temp, self._elegir_plan_temp,
                                         lambda: self.ajustar_tabla(self.t_temp), ideal=lambda: self._del_temp.ancho_para(2, self.t_temp.fontMetrics())))
        self._salida_raton = _SalidaRaton(self, lambda: self._sobre_fila(None, -1))
        for tabla in (self.t_vars, self.t_temp):  # el nombre entero también al pasar el ratón por la fila
            tabla.setMouseTracking(True)
            tabla.entered.connect(lambda indice, tabla=tabla: self._sobre_fila(tabla, indice.row()))
            tabla.viewport().installEventFilter(self._salida_raton)
        self.lado.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(der)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # con la ventana pequeña, también se desplaza a los lados
        self._vigila_alto = _VigilaAlto(self.scroll.viewport(), self._alto_entradas)  # (el alto máximo de las entradas sigue al del panel)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Página de edición: cabecera fija .panel-hd + tabla edge-to-edge + pie fijo (estilo v2)
        pag = QWidget()
        pag.setObjectName("panelVariables")
        pl = QVBoxLayout(pag)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        self.l_herr = QLabel()
        self.l_herr.setWordWrap(True)
        self.l_herr.setTextFormat(Qt.TextFormat.RichText)
        self.l_herr.hide()  # la misma ayuda ya va sobre el dibujo; aquí no cabe en un panel estrecho (sigue en el objeto)
        pl.addWidget(self.l_herr)
        self.l_sel = QLabel()
        self.l_sel.setWordWrap(True)
        pl.addWidget(self.l_sel)
        self.l_sel.hide()  # la selección se identifica en el encabezado de Propiedades
        cab_vars = QFrame()
        cab_vars.setObjectName("cabeceraPanel")
        cab_vars.setFixedHeight(36)
        cvl = QHBoxLayout(cab_vars)
        cvl.setContentsMargins(10, 0, 38, 0)  # reserva a la derecha para el botón de plegar (32 px)
        cvl.setSpacing(6)
        l_tit_vars = QLabel("Variables")
        l_tit_vars.setObjectName("tituloPanel")
        self.l_cont_vars = QLabel("0")
        self.l_cont_vars.setObjectName("badgePanel")
        cvl.addWidget(l_tit_vars)
        cvl.addWidget(self.l_cont_vars)
        cvl.addStretch(1)
        pl.addWidget(cab_vars)
        self.variables = PanelVariables()
        self.variables.detalle.connect(self._detallar)
        self.l_resumen = QLabel()  # resumen accesible para la validación, sin bloque lateral
        self.l_resumen.hide()
        self.lista_diag = self.diagrama.lista_diagnosticos
        self.lista_diag.itemClicked.connect(self._ir_a_diagnostico)
        pl.addWidget(self.variables, 1)
        self.derecho = PilaActual()
        # F4: el botón de plegar (32 px) va en una fila de título propia sobre las tablas: al desplazar el panel ya no tapa la primera entrada
        pagina_sim = QWidget()
        pagina_sim.setObjectName("panelVariables")
        psl = QVBoxLayout(pagina_sim)
        psl.setContentsMargins(0, 0, 0, 0)
        psl.setSpacing(0)
        cab_sim = QFrame()
        cab_sim.setObjectName("cabeceraPanel")
        cab_sim.setFixedHeight(36)
        csl = QHBoxLayout(cab_sim)
        csl.setContentsMargins(10, 0, 38, 0)
        csl.setSpacing(6)
        self.titulo_sim = QLabel("Consola de simulación")
        self.titulo_sim.setObjectName("tituloPanel")
        self.l_cont_sim = QLabel("0")
        self.l_cont_sim.setObjectName("badgePanel")
        csl.addWidget(self.titulo_sim)
        csl.addWidget(self.l_cont_sim)
        csl.addStretch(1)
        psl.addWidget(cab_sim)
        psl.addWidget(self.scroll, 1)
        self.derecho.addWidget(pagina_sim)
        pag_scroll = QScrollArea()  # mantiene compatibilidad con referencias internas; la tabla hace su propio scroll
        pag_scroll.setWidgetResizable(True)
        pag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pag_scroll.setWidget(pag)
        self.derecho.addWidget(pag_scroll)
        self._pag_scroll, self._caja_vars = pag_scroll, pag
        self._vigila_pagina = _VigilaAlto(pag_scroll.viewport(), self._alto_tabla_variables)
        self.derecho.setMinimumWidth(300)
        self.paleta = Paleta(self.diagrama.escala, self)
        from ..favoritos import BarraFavoritos
        from ..cabecera_favoritos import CabeceraFavoritos
        self.favoritos = BarraFavoritos(self.ajustes, self.paleta)
        self._cab.insertWidget(0, self.favoritos)
        self._cabecera_favoritos = CabeceraFavoritos(self)
        self.favoritos.distribucion_cambiada.connect(self._orden_tab)
        self.paleta.ayuda.connect(self._ayuda_ficha)
        self.ancho_derecho = ANCHO_DERECHO_BASE
        self.variables.fijar_ancho_nominal(self.ancho_derecho)
        self._plegables = {
            n: PanelPlegable(c, titulo, n, lambda n=n: self._minimo_panel(n))
            for n, c, titulo in (("derecho", self.derecho, "Variables"), ("inferior", self.inferior, "Traza"))
        }
        self._tamanos_paneles = {"derecho": self.ancho_derecho, "inferior": ALTO_TRAZA}
        self.vsplit = DivisorPlegable(Qt.Orientation.Vertical)
        self.vsplit.addWidget(izq)
        self.vsplit.addWidget(self._plegables["inferior"])
        self.vsplit.configurar(1, "inferior", 1, self._plegables["inferior"])
        self.vsplit.setCollapsible(0, False)
        self.vsplit.setCollapsible(1, False)  # el panel inferior se pliega con su flecha, no arrastrando: nunca por debajo de lo que pide
        self.vsplit.setHandleWidth(4)
        self.vsplit.setStretchFactor(0, 1)  # al agrandar la ventana crece el dibujo; el panel inferior conserva su altura
        self.vsplit.setStretchFactor(1, 0)
        self.vsplit.setSizes([520, ALTO_TRAZA])
        self.split = DivisorPlegable(Qt.Orientation.Horizontal)
        self.split.addWidget(self.vsplit)
        self.split.addWidget(self._plegables["derecho"])
        self.split.configurar(1, "derecho", 1, self._plegables["derecho"])
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 0)
        self.split.setHandleWidth(5)
        self._derecho_a_mano = False  # el usuario movió el divisor: su ancho no se vuelve a tocar al cambiar de tamaño la ventana
        self.split.splitterMoved.connect(lambda *_: setattr(self, "_derecho_a_mano", True))
        self.split.setSizes([880, 460])
        self.split.setContentsMargins(0, 0, 0, 0)
        for divisor in (self.split, self.vsplit):
            divisor.plegar.connect(self._plegar_desde_divisor)
            divisor.abrir.connect(self._abrir_desde_tiron)
        self.setCentralWidget(self.split)
        self._preparar_barra_estado()

    def _preparar_barra_estado(self) -> None:
        sb = self.statusBar()
        # Los mensajes temporales se muestran en el centro. QStatusBar conserva su temporizador y su señal.
        sb.setStyleSheet("QStatusBar { color: transparent; }")
        self.zona_estado = QWidget()
        self.zona_estado.setObjectName("zonaEstado")
        zona = QHBoxLayout(self.zona_estado)
        zona.setContentsMargins(estilo.E3, 0, estilo.E3, 0)
        zona.setSpacing(estilo.E3)
        fija = QHBoxLayout()
        fija.setSpacing(estilo.E2)
        self.l_aviso = QLabel(AVISO)
        self.l_aviso.setStyleSheet(f"color: {estilo.TINTA_2}")
        fija.addWidget(self.l_aviso)
        separador = QLabel("·")
        separador.setStyleSheet(f"color: {estilo.TINTA_2}")
        separador.hide()
        fija.addWidget(separador)
        self.l_firma = _FirmaEstado(separador)
        self.l_firma.setStyleSheet(f"color: {estilo.TINTA_2}")
        self.l_firma.hide()
        fija.addWidget(self.l_firma)
        zona.addLayout(fija)

        centro = QHBoxLayout()
        centro.setSpacing(estilo.E2)
        self.l_lect = EtiquetaElidida()
        self.l_lect.minimo = 0
        self.l_lect.setStyleSheet(f"color: {estilo.AVISO}; font-weight: 600")
        centro.addWidget(self.l_lect)
        self._detalle_estado = QWidget()
        detalle = QHBoxLayout(self._detalle_estado)
        detalle.setContentsMargins(0, 0, 0, 0)
        self.l_detalle = EtiquetaElidida(modo=Qt.TextElideMode.ElideMiddle)
        self.l_detalle.setStyleSheet(f"color: {estilo.TINTA}; font-weight: 600")
        self.l_detalle.setAccessibleName("Detalle")
        self.l_detalle.destroyed.connect(self._desconectar_detalle_de_foco)
        self.l_detalle.hide()
        detalle.addWidget(self.l_detalle)
        centro.addWidget(self._detalle_estado, 1)
        self.l_mensaje_estado = EtiquetaElidida()
        self.l_mensaje_estado.setStyleSheet(f"color: {estilo.TINTA}; font-weight: 600")
        self.l_mensaje_estado.setAccessibleName("Mensaje de estado")
        self.l_mensaje_estado.hide()
        centro.addWidget(self.l_mensaje_estado, 1)
        zona.addLayout(centro, 1)

        self.l_reloj = QLabel()
        self.l_reloj.setStyleSheet(f"color: {estilo.TINTA}")
        self.l_reloj.setFont(estilo.fuente_tabular(px=estilo.T_CIFRA, negrita=True, mono=False))
        self.l_reloj.setMinimumWidth(0)
        self.l_reloj.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._ancho_reloj = 0  # ancho máximo que ha pedido el texto durante la simulación
        zona.addWidget(self.l_reloj)
        sb.addPermanentWidget(self.zona_estado, 1)
        sb.messageChanged.connect(self._mensaje_de_estado)

    def _desconectar_detalle_de_foco(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.disconnect(self._detalle_del_foco)

    def _mensaje_de_estado(self, texto: str) -> None:
        self.l_mensaje_estado.setText(texto)
        self.l_mensaje_estado.setVisible(bool(texto))
        self._detalle_estado.setVisible(not texto)

    def _paneles(self) -> None:
        """Recupera la visibilidad de Variables y Traza y conecta sus tiradores."""
        from ..visibilidad_paneles import VisibilidadPaneles
        self.visibilidad_paneles = VisibilidadPaneles(self)
        self.flechas = {n: p.cerrar for n, p in self._plegables.items()}
        self.pestanas = {n: p.pestana for n, p in self._plegables.items()}
        self.variables.conteo.connect(self._contar_variables)
        for nombre, panel in self._plegables.items():
            panel.alternar.connect(lambda n=nombre: self.visibilidad_paneles.alternar(n))
            panel.desplegar.connect(lambda tamano,n=nombre:self._abrir_desde_tiron(n,tamano))
        for nombre in ("derecho", "inferior"):
            accion = self._accion_panel(nombre)
            visible = self.ajustes.value(f"paneles/{nombre}", True, type=bool)
            if nombre == "inferior":  # La traza arranca plegada aunque un ajuste antiguo la dejara abierta.
                visible = False
            accion.blockSignals(True)
            accion.setChecked(visible)
            accion.blockSignals(False)
            self._mostrar_panel(nombre, visible, guardar=False)

        self.visibilidad_paneles.restaurar()

    def _panel(self, nombre: str) -> QWidget:
        return {"derecho": self.derecho, "inferior": self.inferior}[nombre]

    def _accion_panel(self, nombre: str) -> QAction:
        return {"derecho": self.a_derecho, "inferior": self.a_inferior}[nombre]

    def _mostrar_panel(self, nombre: str, visible: bool, guardar: bool = True) -> None:
        self.visibilidad_paneles.mostrar(nombre, visible, guardar)

    def _desplegar_panel(self, nombre: str, visible: bool, guardar: bool = True) -> None:
        if guardar:  # lo pide el usuario (cabecera, pestaña, atajo, divisor): el modo compacto ya no lo mueve
            self._manual_paneles[nombre] = True
            self._auto_plegados.discard(nombre)
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        panel = self._plegables[nombre]
        anterior = panel.abierto
        if nombre == "inferior" and not visible and self.edicion is not None and self.edicion.parte_editada is not None:
            self.edicion.parte_editada = None
        if anterior and not visible:
            actual = panel.height() if nombre == "inferior" else panel.width()
            self._tamanos_paneles[nombre] = getattr(panel, "tamano_recordado", None) or actual
            panel.tamano_recordado = None
        panel.mostrar(visible)
        if nombre == "derecho":
            self._texto_pestana_derecha(editar)
        if visible != anterior:
            tamano = max(self._minimo_panel(nombre), self._tamanos_paneles[nombre]) if visible else panel.GROSOR_PESTANA
            divisor = self.split if nombre == "derecho" else self.vsplit
            total = sum(divisor.sizes())
            divisor.setSizes([max(100, total - tamano), tamano])
        accion = self._accion_panel(nombre)
        if accion.isChecked() != visible:
            accion.blockSignals(True)
            accion.setChecked(visible)
            accion.blockSignals(False)
        # La flecha apunta hacia donde se pliega el panel y, plegado, hacia donde se despliega
        self.flechas[nombre].setText({"derecho": "▸" if visible else "◂",
                                      "inferior": "▾" if visible else "▴"}[nombre])
        self.flechas[nombre].setToolTip(f"{'Plegar' if visible else 'Desplegar'} el panel {nombre}")
        if guardar:
            self.ajustes.setValue(f"paneles/{nombre}", visible)
        if nombre == "inferior":
            self._zoom_diferido()  # (con Propiedades abierto, el zoom va en la cabecera)

    def _contar_variables(self, cuenta: int) -> None:
        self.l_cont_vars.setText(str(cuenta))
        self._texto_pestana_derecha(self.modo == "editar" and self.edicion is not None and not self.solo_lectura)

    def _texto_pestana_derecha(self, editar: bool) -> None:
        texto = f"Variables · {self.l_cont_vars.text()}" if editar else "Simulación"
        self.pestanas["derecho"].setText(texto)

    def _minimo_panel(self, nombre):
        if nombre != "inferior":
            return self._ancho_minimo_derecho()
        return max(120, self.traza.minimumSizeHint().height()+30)

    def _abrir_desde_tiron(self, nombre, tamano):
        tamano = max(self._minimo_panel(nombre), tamano)
        self._tamanos_paneles[nombre] = tamano
        self._mostrar_panel(nombre, True)
        if nombre == "derecho":
            total=sum(self.split.sizes());self.split.setSizes([max(100,total-tamano),tamano])
        elif nombre == "inferior":
            total=sum(self.vsplit.sizes());self.vsplit.setSizes([max(100,total-tamano),tamano])

    def _plegar_desde_divisor(self, nombre):
        self._mostrar_panel(nombre, False)

    def _anchos_laterales(self, ancho: int | None = None) -> None:
        panel = self._plegables["derecho"]
        ancho = max(self.ancho_derecho, panel.width() if ancho is None else ancho) if panel.abierto else panel.GROSOR_PESTANA
        self.derecho.setMinimumWidth(self._ancho_minimo_derecho())
        self.derecho.setMaximumWidth(16777215)
        self.split.handle(1).setEnabled(True)
        total = self.split.contentsRect().width() - self.split.handleWidth()
        self.split.setSizes([max(total - ancho, 100), ancho])

    def _estilo_aviso_traer(self) -> None:
        """La hoja de la franja «seleccionando para Planos» (con los alto de control de la escala de ahora)."""
        self.aviso_traer.setStyleSheet(
            f'QWidget#avisoSeleccionPlanos {{background:{estilo.AVISO_FONDO}; color:{estilo.TINTA}; border-top:2px solid {estilo.AVISO_BORDE}; border-radius:{estilo.R_S}px;}} '
            'QWidget#avisoSeleccionPlanos QLabel {background:transparent; font-weight:600;} '
            f'QWidget#avisoSeleccionPlanos QPushButton {{background:white; color:{estilo.TINTA}; border:1px solid {estilo.BORDE_CONTROL}; padding:0 14px; border-radius:{estilo.R_S}px; min-height:{estilo.ALTO_CONTROL - 2}px;}} '
            f'QWidget#avisoSeleccionPlanos QPushButton:hover {{background:{estilo.HOVER}; border-color:{estilo.TINTA};}} '
            f'QWidget#avisoSeleccionPlanos QPushButton[tecl=\"true\"]:focus {{border:2px dashed {estilo.FOCO}; padding:0 13px; min-height:{estilo.ALTO_CONTROL - 4}px;}} '
            f'QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja {{background:{estilo.CONFIRMAR}; color:white; border-color:{estilo.CONFIRMAR_BORDE}; font-weight:600;}} '
            f'QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja:hover {{background:{estilo.CONFIRMAR_HOVER};}} '
            'QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja[tecl="true"]:focus {border:2px dashed white;}')

    def _estilos_locales(self) -> None:
        """Lo que la ventana escribe a mano con las letras y los alto de control de la escala de ahora (títulos, ayudas, reloj,
        tablas, entradas…): se genera en la construcción y otra vez al cruzar el umbral de pantalla completa."""
        self.ayuda.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: {estilo.T_PEQUENA}px")
        self.l_ayuda_entradas.setStyleSheet(
            f"color: {estilo.TINTA_3}; font-size: {max(11, estilo.T_PEQUENA - 1)}px; font-weight: 400"
        )
        self._estilo_ayuda()
        self.navegacion.escalar()
        self.l_reloj.setFont(estilo.fuente_tabular(px=estilo.T_CIFRA, negrita=True, mono=False))
        self.estado.escalar()
        for b in self.botones.values():
            if isinstance(b, _BotonEntrada):
                b.ajustar_alto()  # (el alto de una línea de la escala de ahora, o el de sus líneas si el nombre va partido)
        hoja = self._hoja_consola()
        for t in (self.t_vars, self.t_temp):
            t.setStyleSheet(hoja)
            t.verticalHeader().setDefaultSectionSize(estilo.ALTO_FILA + 2)
            t.verticalHeader().setMinimumSectionSize(estilo.ALTO_FILA_COMPACTA)
        for reparto in self._reparto:  # (con la letra de ahora, las columnas se miden otra vez)
            reparto.aplicar()

    def _escala_de_la_ventana(self) -> None:
        """La escala que pide el tamaño de ahora. Con la ventana a la vista, el cambio no se hace en cada `resizeEvent`: una animación
        de Windows (Aero Snap) o arrastrar el borde mandan varios seguidos, y reaplicar la hoja de estilo en cada uno hacía «bailar» el
        dibujo. Se espera a que se calmen (`ESPERA_ESCALA` ms sin nuevos cambios de tamaño) y se aplica **una sola vez**, con el tamaño
        final; mientras tanto se conserva la escala anterior. Antes de mostrarse la ventana, en el primer instante tras mostrarse (hasta que se maximiza, sin que se vea el salto) y al terminar la
        espera, se aplica al momento."""
        deseada = estilo.escala_para(self.width(), self.height(), self._escala)
        if not self.isVisible() or self._escala_lista or self._arrancando:
            self._espera_escala.stop()
            self._aplicar_escala(deseada)
        elif deseada == self._escala:
            self._espera_escala.stop()  # (la ráfaga ha vuelto a la escala de ahora: no hay nada que cambiar)
        else:
            self._espera_escala.start(ESPERA_ESCALA)  # (se reinicia con cada evento de la ráfaga)

    def _escala_tras_la_rafaga(self) -> None:
        self._escala_lista = True
        try:
            self._adaptar_tamano()
        finally:
            self._escala_lista = False

    def _aplicar_escala(self, nombre: str) -> None:
        """Al cruzar el umbral de pantalla completa (`estilo.UMBRAL_GRANDE`) o volver por debajo: la letra base pasa de 13 a 14 px,
        los títulos, el chip y las cifras crecen y los controles miden 40 px; por debajo de ese tamaño, lo de siempre. Solo se
        repite al cruzar el umbral (la hoja entera tarda cerca de un segundo en aplicarse). Los menús conservan su aspecto."""
        if nombre == self._escala:
            return
        # (sin `setUpdatesEnabled(False)` aquí: no ahorraba nada y dejaba sin repintar, para siempre, a los hijos que se ponen en
        # `updatesEnabled` = falso por dentro, como la paleta de Elementos, que se quedaba vacía al cruzar el umbral)
        self._cambiar_escala(nombre)

    def _cambiar_escala(self, nombre: str) -> None:
        self._escala = nombre
        self._alto_cabecera = 0
        self._ancho_forzado = 0  # (la letra cambia: `_vigilar_barra` vuelve a medir si «Reiniciar» cabe con texto)
        estilo.activar_escala(nombre)
        self._hoja_escala = estilo.hoja_global() if nombre == "grande" else ""
        for destino in self._destinos_hoja:  # (solo lo que cambia: la hoja de la ventana no se toca)
            destino.setStyleSheet(self._hoja_escala)
        self._planos_pendiente = True  # PLANOS (oculta casi siempre, ≈ 10 ms) se pone al día cuando se muestra
        if self.paginas_es.currentIndex() == 2:
            self._escala_planos()
        self._es_pendiente = True  # E/S y Propiedades se ponen al día cuando se muestran
        if self.paginas_es.currentIndex() == 1:
            self._escala_es()
        self._poner_ancho_derecho(self._ancho_derecho_para(self.width()))  # (por si el ancho no cambió pero la letra sí)
        self._estilos_locales()
        self._ancho_reloj = 0  # el reloj vuelve a medir lo que su texto (otra letra, otro ancho)
        self.l_reloj.setMinimumWidth(0)
        if self.l_reloj.text():
            self._poner_reloj(self.l_reloj.text())
        self.diagrama.escalar()
        self.variables.escalar()
        self.diagrama.parentWidget().layout().invalidate()
        self._estilo_aviso_traer()
        if self.modo == "simular" and self.v is not None:
            self.refrescar()
        else:
            self.refrescar_edicion()
        self._fijar_ancho_boton_play()
        self.tb_sim.layout().invalidate()
        QTimer.singleShot(0, self, self._remedir_barra_simulacion)
        # La hoja nueva cambia lo que miden los controles, y Qt reparte las cajas en la vuelta siguiente del bucle de eventos: hasta
        # entonces el dibujo se veía en un sitio y, al repartirse, saltaba unos píxeles («flotando»). Se reparten aquí, en este pintado.
        QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)

    def _ancho_minimo_derecho(self) -> int:
        return min(self.ancho_derecho, ANCHO_DERECHO_BASE) if self._escala == "grande" else self.ancho_derecho

    def _ancho_derecho_para(self, ancho_ventana: int) -> int:
        """Ancho nominal para Variables y Simulación, con espacio para la letra grande."""
        umbral = estilo.UMBRAL_GRANDE[0]
        tramo = min(1.0, max(0.0, (ancho_ventana - 1366) / (umbral - 1366)))
        grande = min(1.0, max(0.0, (ancho_ventana - umbral) / 320))
        base = ANCHO_DERECHO_BASE + round(46 * tramo) + round(36 * grande)
        return max(base, ANCHO_DERECHO) if ancho_ventana >= UMBRAL_DERECHO else base

    def _poner_ancho_derecho(self, ancho: int) -> None:
        if ancho == self.ancho_derecho:
            return
        anterior, self.ancho_derecho = self.ancho_derecho, ancho
        self.variables.fijar_ancho_nominal(ancho)
        if self._tamanos_paneles["derecho"] == anterior:
            self._tamanos_paneles["derecho"] = ancho
        panel = self._plegables["derecho"]
        panel.mostrar(panel.abierto)
        self.derecho.setMinimumWidth(self._ancho_minimo_derecho())
        ajustar = panel.abierto and (panel.width() == anterior or not self._derecho_a_mano)
        self._anchos_laterales(ancho if ajustar else None)

    def _escala_planos(self) -> None:
        """PLANOS lleva la hoja de la escala de ahora; se hace al mostrarla (cruzar el umbral no repasa una página que no se ve)."""
        if self._planos_pendiente:
            self._planos_pendiente = False
            self.panel_planos.escalar(self._hoja_escala)

    def _zoom_diferido(self) -> None:
        if not self._zoom_pendiente:
            self._zoom_pendiente = True
            QTimer.singleShot(0, self, self._ajustar_zoom)

    def _ajustar_zoom(self) -> None:
        self._cabecera_favoritos.integrar_zoom()

    def _adaptar_tamano(self) -> None:
        """Modo compacto automático, sin que el usuario toque nada: por debajo de `estilo.UMBRAL_ANCHO` (pantalla partida) el
        panel de Variables se pliega solo al editar, y por debajo de `estilo.UMBRAL_ALTO` (un cuarto de pantalla) los márgenes se
        estrechan y las herramientas suben a la fila de las pestañas. Lo que el usuario plegó o desplegó a mano se respeta, y al
        agrandar la ventana vuelve lo que se plegó solo. No se cambia la hoja de estilo (aplicarla a toda la ventana tarda cerca
        de un segundo): los controles miden lo mismo a todos los tamaños."""
        self._escala_de_la_ventana()
        self._poner_ancho_derecho(self._ancho_derecho_para(self.width()))
        nuevo = estilo.tamano_compacto(self.width(), self.height())
        if nuevo != self._compacto:
            bajo_antes = self._compacto[1]
            self._compacto = nuevo
            ancho, alto = nuevo
            if alto != bajo_antes:
                self._fusionar_filas(alto)
            il = self.diagrama.parentWidget().layout()
            il.setContentsMargins(*((estilo.E2, estilo.E1 + HUECO_FRANJA, estilo.E2, estilo.E1) if alto else self._margenes_dibujo))
            self._reflujo_entradas()
            self._densidad_lateral()
            self.diagrama.compactar(ancho, alto)
            self._ajustar_zoom()  # los controles del zoom, en la cabecera (en estrecho o bajo, y con poco dibujo)
            self.panel_planos.compactar(ancho or alto)
        self._repartir_textos_barra()
        self._ajustar_cabecera()  # (el chip de modo pide hasta el 55 % del ancho, y deja al título unos 10 caracteres: el título cede antes que el estado)
        muy = self.width() < max(estilo.UMBRAL_MUY_ESTRECHO, self._ancho_forzado)
        if muy != self._muy_estrecho:  # media pantalla: la fila de arriba tiene que caber en 640 px
            self._muy_estrecho = muy
            self.tb_sim.widgetForAction(self.a_reiniciar).setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonIconOnly if muy else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.tb_sim.layout().invalidate()  # (la barra guarda lo que medían sus botones: sin esto «Reiniciar» se queda en el desbordamiento)
            self.tb_sim.updateGeometry()
            self.tb_sim.setMinimumWidth(0)
            QTimer.singleShot(0, self, self._remedir_barra_simulacion)
            estilo.poner(self.pestanas_vistas, estrecha=muy)
            for i in (0, 1):  # QTabBar guarda el tamaño de sus pestañas: cambiar el texto lo obliga a medirlas otra vez
                texto = self.pestanas_vistas.tabText(i)
                self.pestanas_vistas.setTabText(i, texto + " ")
                self.pestanas_vistas.setTabText(i, texto)
            self._luz_es(*self._ultima_luz)
        self._plegar_laterales_compactos()

    def _ajustar_cabecera(self) -> None:
        self._cabecera_favoritos.ajustar()

    def _alternar_ayuda(self) -> None:
        self.ayuda_pantalla.alternar()

    def _estilo_ayuda(self) -> None:
        """Estilo de la franja de ayuda contextual."""
        self.ayuda_larga.setStyleSheet(
            f"QLabel#ayudaLarga {{ color: {estilo.TINTA}; background: {estilo.SUPERFICIE_2}; border: 1px solid {estilo.BORDE}; "
            f"border-radius: {estilo.R_S}px; padding: 6px 10px; font-size: {estilo.T_PEQUENA}px; }}")

    def _vigilar_barra(self) -> None:
        """Red de seguridad, a cualquier ancho: si la barra de Play no cabe con «Reiniciar» y su texto (o este queda fuera de ella),
        «Reiniciar» pasa a solo icono con su ayuda, y sigue así mientras la ventana no sea más ancha que cuando no cabía."""
        if self._muy_estrecho or not self.isVisible():
            return
        barra, boton = self.tb_sim, self.tb_sim.widgetForAction(self.a_reiniciar)
        fuera = boton is not None and boton.isVisibleTo(barra) and boton.geometry().right() > barra.width()
        if fuera or barra.width() < barra.sizeHint().width() - 1:
            self._ancho_forzado = self.width() + 1
            self._adaptar_tamano()

    def _remedir_barra_simulacion(self) -> None:
        """Tras cambiar «Reiniciar» a solo icono, la barra de Play pide lo que mide ahora y su fila se vuelve a repartir."""
        for objeto in (self.tb_sim, self.herramientas_grafcet, self.fila_pestanas):
            lay = objeto.layout()
            if lay is not None:
                lay.invalidate()
                lay.activate()
        self.tb_sim.resize(self.tb_sim.sizeHint().width(), self.tb_sim.height())

    def _ancho_barra_edicion(self, con_texto: bool) -> int:
        """Lo que pide la barra de edición con las palabras de sus botones o solo con iconos (se mide una vez por escala)."""
        cache = self.__dict__.setdefault("_anchos_edicion", {})
        clave = (con_texto, estilo.ESCALA, self._compacto[0])
        if clave not in cache:
            self._textos_en_barras(con_texto)
            for barra in (self.tb_edit, self.tb_vista_der):
                barra.layout().invalidate()
                barra.layout().activate()
            cache[clave] = self.tb_edit.sizeHint().width() + self.tb_vista_der.sizeHint().width() + 16
        return cache[clave]

    def _repartir_textos_barra(self) -> None:
        """Mantiene Dependencias y Errores con texto mientras quepan junto a Play."""
        libre = self.herramientas_grafcet.width() if self.herramientas_grafcet.isVisible() else self.width()
        con = self._ancho_barra_edicion(True) + self.tb_sim.sizeHint().width() <= libre - 4 * estilo.E2
        antes = getattr(self, "_texto_en_barra", None)
        self._texto_en_barra = con
        self._textos_en_barras(con)
        if antes is not None and antes != con:
            for barra in (self.tb_edit, self.tb_vista_der):
                barra.layout().invalidate()
                barra.updateGeometry()

    def _textos_en_barras(self, con_texto: bool) -> None:
        """Dependencias y Errores muestran sus rótulos cortos cuando hay espacio."""
        forma = Qt.ToolButtonStyle.ToolButtonTextBesideIcon if con_texto else Qt.ToolButtonStyle.ToolButtonIconOnly
        rotulos = ("Dependencias", "Errores") if self._compacto[0] else ("Mostrar dependencias", "Mostrar errores")
        for a, rotulo in zip((self.a_dependencias, self.a_errores), rotulos):
            w = self.tb_vista_der.widgetForAction(a)
            if w is not None:
                w.setText(rotulo)
                w.setToolButtonStyle(forma)
        self.diagrama.b_dependencias.setToolButtonStyle(forma)

    def _configurar_foco(self) -> None:
        """Los botones se alcanzan con Tab y no toman el foco con el ratón (así el anillo solo sale al navegar con teclado); el
        orden va de arriba abajo y de izquierda a derecha, y al arrancar el foco está en el dibujo."""
        for b in self.findChildren(QAbstractButton):
            if not b.isCheckable() and b.focusPolicy() in (Qt.FocusPolicy.StrongFocus, Qt.FocusPolicy.NoFocus):
                b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        for tabla in self.findChildren(QTableWidget):
            tabla.setTabKeyNavigation(False)
        play = self.tb_sim.widgetForAction(self.a_ejecutar)
        if play is not None:
            play.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # (es un botón de dos estados: el bucle de arriba lo salta)
        for zona in self.findChildren(QScrollArea):  # una zona de desplazamiento no es una parada de Tab: sus controles sí
            if zona.focusPolicy() == Qt.FocusPolicy.StrongFocus:
                zona.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._orden_tab()

    def _orden_tab(self) -> None:
        d = self.diagrama
        entradas = list(getattr(self, "botones", {}).values())
        cadena = [self.pestanas_vistas, self.luz_es, self.tb_sim.widgetForAction(self.a_ejecutar),
                  self.tb_sim.widgetForAction(self.a_reiniciar),
                  *(self.tb_edit.widgetForAction(a) for a in self._acciones_solo_icono),
                  d.b_dependencias, self.b_errores,
                  *self.favoritos.foco(), d,
                  d.b_menos, d.b_mas, d.b_ajustar, d.b_seleccion,
                  self.flechas["derecho"], *entradas, self.variables.tabla, *self.variables.b_nuevas.values(),
                  self.variables.b_quitar, self.pestanas["derecho"], self.flechas["inferior"],
                  self.pestanas["inferior"]]
        cadena = [w for w in cadena if w is not None]
        for a, b in zip(cadena, cadena[1:]):
            QWidget.setTabOrder(a, b)

    def _plegar_laterales_compactos(self) -> None:
        estrecho = self._compacto[0]
        panel = self._plegables["derecho"]
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self, "solo_lectura", False)
        if estrecho and editar and panel.abierto and not self._manual_paneles.get("derecho"):
            self._mostrar_panel("derecho", False, guardar=False)
            self._auto_plegados.add("derecho")
        elif "derecho" in self._auto_plegados and not (estrecho and editar):
            self._auto_plegados.discard("derecho")
            self._mostrar_panel("derecho", True, guardar=False)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.isVisible():
            self._adaptar_tamano()
            QTimer.singleShot(0, self, self._vigilar_barra)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if not getattr(self, "_play_medido", False):
            self._play_medido = True
            self._fijar_ancho_boton_play()  # (ya con la hoja de estilo aplicada: la letra del botón es la que se ve)
        if not self._arranque_hecho:
            self._arranque_hecho = self._arrancando = True
            QTimer.singleShot(ESPERA_ARRANQUE, self, lambda: setattr(self, "_arrancando", False))
        self._escala_tras_la_rafaga()  # (al mostrarse, la escala del tamaño de ahora y sin esperas)
        if not self._foco_inicial:  # al arrancar, el foco va al dibujo (sin anillo: no llegó con Tab)
            self._foco_inicial = True
            self.diagrama.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False) and not getattr(self, "_anchos_puestos", False):
            self._anchos_puestos = True  # con la ventana ya dimensionada, los dos paneles laterales con el mismo ancho
            self._anchos_laterales(self.ancho_derecho)
