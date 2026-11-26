"""Menús, atajos de teclado, ayuda y actualizaciones: lo que se compone con acciones (`QAction`) y se despacha a las demás piezas."""
from __future__ import annotations

from .. import actualizaciones, estilo, propiedades_archivo
from ..aviso_version import DialogoVersionNueva
from ..diagrama import imagen
from ..edicion import HERRAMIENTAS
from ..leyenda import Leyenda
from typing import Any
from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QCursor, QKeySequence
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QFileDialog, QHBoxLayout, QInputDialog,
                               QLineEdit, QMessageBox, QPlainTextEdit, QTextEdit, QToolBar, QToolButton, QWidget)
from grafcet.profile import APP_VERSION
from .constantes import AYUDA_EDICION, ICONO_PROGRAMA, NOMBRE_HERRAMIENTA, TITULO
from .dialogos import AcercaDe, _icono_barra, _icono_grafcet


class Menus:
    """Menús, atajos de teclado, ayuda y actualizaciones: lo que se compone con acciones (`QAction`) y se despacha a las demás piezas. Sin estado propio: usa los atributos de `Ventana` (la fachada) y llama a los demás métodos a través de `self`."""

    # -- construcción ---------------------------------------------------------------------------
    def _accion(self, texto: str, slot: Any, atajo: str | list[str] | None = None, marcable: bool = False) -> QAction:
        a = QAction(texto, self)
        a.setCheckable(marcable)
        if atajo:
            a.setShortcuts([QKeySequence(x) for x in ([atajo] if isinstance(atajo, str) else atajo)])
        (a.toggled if marcable else a.triggered).connect(slot)
        return a

    def _seleccionar_teclado(self, h):
        self.herramienta(h)
        if self.edicion and self.diagrama.hasFocus(): self.edicion.seleccionar([])

    def buscar_elemento(self):
        self._mostrar_pagina(False); self.navegacion.abrir()

    def insertar_teclado(self, tipo):
        if self.modo != 'editar' or self.edicion is None or getattr(self,"solo_lectura",False): return
        p = self.diagrama.mapToScene(self.diagrama.viewport().rect().center())
        if tipo == 'transicion': self.edicion.poner_transicion(p)
        else: self.edicion.poner_etapa(p, tipo == 'inicial')
        self.diagrama.setFocus()

    def conectar_teclado(self):
        e = self.edicion
        if self.modo != 'editar' or not e or len(e.sel) != 1 or getattr(self,'solo_lectura',False): return
        origen = e.sel[0]
        destinos = [d for d in self.navegacion.datos if d['id'] != origen and d['tipo'] in ('Etapa', 'Transición', 'Macroetapa', 'Barra')]
        nombres = [d['texto'] for d in destinos]
        elegido, ok = QInputDialog.getItem(self, 'Conectar elementos', 'Destino del enlace', nombres, 0, False)
        if ok and elegido in nombres: e.conectar(origen, destinos[nombres.index(elegido)]['id'])
        self.activateWindow(); self.diagrama.setFocus()

    def _accesibilidad(self):
        from PySide6.QtWidgets import QAbstractButton
        for boton in self.findChildren(QAbstractButton):
            if not boton.accessibleName(): boton.setAccessibleName((boton.text() or boton.toolTip()).replace('&',''))
            if not boton.accessibleDescription(): boton.setAccessibleDescription(boton.toolTip() or boton.accessibleName())
        for nombre in ('derecho', 'inferior'):
            self._plegables[nombre].setAccessibleName({'derecho': 'Variables y simulación', 'inferior': 'Traza'}[nombre])
            self._plegables[nombre].setAccessibleDescription('Panel plegable. Usa su cabecera para ocultarlo o su pestaña para recuperarlo.')

    def _menus(self) -> None:
        self.paginas_es = None
        self.panel_planos = None
        self.destino_traer = None
        bar = self.menuBar()
        archivo = bar.addMenu("&Proyecto")
        self.a_nuevo = self._accion("&Nuevo proyecto", self.nuevo, "Ctrl+N")
        archivo.addAction(self.a_nuevo)
        a = self.a_abrir = archivo.addAction("&Abrir…", self.abrir)
        a.setShortcut(QKeySequence.StandardKey.Open)
        self.a_guardar = archivo.addAction("&Guardar", self.guardar)
        self.a_guardar.setShortcut(QKeySequence.StandardKey.Save)
        self.a_guardar_como = self._accion("Guardar &como…", self.guardar_como, "Ctrl+Shift+S")
        archivo.addAction(self.a_guardar_como)
        self.a_exportar = archivo.addAction("&Exportar…", lambda:self.abrir_laminas("exportar"))
        self.a_imprimir = self._accion("&Imprimir…", lambda:self.abrir_laminas("imprimir"), "Ctrl+P")
        archivo.addAction(self.a_imprimir)
        archivo.addAction("Guardar el &dibujo como imagen…", self.guardar_imagen)
        archivo.addAction("Propiedades del archi&vo…", lambda *_: propiedades_archivo.abrir(self))
        archivo.addSeparator()
        archivo.addAction("&Salir", self.close).setShortcut(QKeySequence.StandardKey.Quit)
        # Un solo control de ejecución: Simular arranca tiempo real (traza abajo, sin paleta) y Stop detiene y vuelve a editar
        self.a_ejecutar = self._accion("Simular", self._ejecutar, "F5", marcable=True)
        self.a_ejecutar.setToolTip("Simular: iniciar una simulación nueva · Detener: detener y dejar todo a 0 (F5)")
        self.a_reiniciar = self._accion("Reiniciar", self.reiniciar, "Ctrl+R")
        self.a_reiniciar.setToolTip("Volver a la situación inicial; en Play sigue en Play (Ctrl+R)")
        ver = bar.addMenu("&Ver")
        self.a_derecho = self._accion(
            "Panel &derecho", lambda on: self._mostrar_panel("derecho", on), "Ctrl+B", True)
        self.a_inferior = self._accion(
            "Panel &inferior", lambda on: self.visibilidad_paneles.activar_traza(on), "Ctrl+J", True)
        self.addAction(self.a_derecho)  # Ctrl+B pliega Variables desde su pestaña.
        self.addAction(self.a_inferior)  # Ctrl+J conserva el acceso a la traza, sin entrada en Ver.
        self.a_ver_dependencias = self._accion(
            "Mostrar dependencias", lambda on: self.diagrama.mostrar_dependencias(on), marcable=True)
        self.a_ver_errores = self._accion("Mostrar errores", self._errores_desde_menu, marcable=True)
        self.a_ver_etiquetas = self._accion("Etiquetas de transiciones", self._etiquetas_desde_menu, marcable=True)
        self.a_ver_etiquetas.setToolTip("Dibujar u ocultar la etiqueta (t1, t2…) de todas las transiciones")
        ver.addSeparator()
        ver.addAction(self.a_ver_dependencias)
        ver.addAction(self.a_ver_errores)
        ver.addAction(self.a_ver_etiquetas)
        ver.aboutToShow.connect(self._sincronizar_menu_dibujo)
        ver.addSeparator()
        ver.addAction(self._accion("&Acercar", lambda: self.diagrama.acercar(), ["Ctrl+=", "Ctrl++"]))
        ver.addAction(self._accion("A&lejar", lambda: self.diagrama.alejar(), "Ctrl+-"))
        ver.addAction(self._accion("&Centrar todo el dibujo", lambda: self.diagrama.ajustar(), "Ctrl+0"))
        # Edición
        self.a_herr: dict[str, QAction] = {}
        self.g_herr = QActionGroup(self)
        for h in HERRAMIENTAS:  # solo las que no colocan elementos: los elementos y las acciones se arrastran desde la paleta
            atajo = "Esc"
            a = self._accion("Seleccionar", lambda on, h=h: on and self.herramienta(h), atajo, True)
            a.triggered.connect(lambda on=False, h=h: self._seleccionar_teclado(h))
            a.setToolTip(f"{NOMBRE_HERRAMIENTA[h]} ({atajo}): {AYUDA_EDICION[h]}")
            self.g_herr.addAction(a)
            self.a_herr[h] = a
        self.a_herr["seleccionar"].blockSignals(True)
        self.a_herr["seleccionar"].setChecked(True)
        self.a_herr["seleccionar"].blockSignals(False)
        self.a_deshacer = self._accion("&Deshacer", lambda: self.historial_plano(False), "Ctrl+Z")
        self.a_rehacer = self._accion("&Rehacer", lambda: self.historial_plano(True), ["Ctrl+Y", "Ctrl+Shift+Z"])
        self.a_borrar = self._accion("&Borrar la selección\tSupr", lambda: self.edicion and self.edicion.borrar(), "Del")
        self.a_debajo = self._accion("&Añadir debajo\tCtrl+Enter", lambda: self.edicion and self.edicion.anadir_debajo(), "Ctrl+Return")
        self.a_debajo.setToolTip("Con una etapa seleccionada: transición y etapa enlazadas debajo (Ctrl+Intro)")
        # El atajo (Ctrl+Mayús+Izquierda/Derecha) lo trata VistaDiagrama.keyPressEvent: aquí solo va en el texto, sin QShortcut,
        # para no crear un atajo ambiguo.
        self.a_girar_izq = self._accion("Girar transición en sentido &antihorario	Ctrl+Mayús+Izquierda",
                                        lambda: self.edicion and self.edicion.girar_transiciones(-1))
        self.a_girar_der = self._accion("Girar transición en sentido &horario	Ctrl+Mayús+Derecha",
                                        lambda: self.edicion and self.edicion.girar_transiciones(1))
        self.a_cortar = self._accion("Cortar", lambda: self._portapapeles_accion("cortar"), "Ctrl+X")
        self.a_copiar = self._accion("Copiar", lambda: self._portapapeles_accion("copiar"), "Ctrl+C")
        self.a_pegar = self._accion("Pegar", lambda: self._portapapeles_accion("pegar"), "Ctrl+V")
        edicion = bar.addMenu("&Edición")
        for a in (self.a_cortar, self.a_copiar, self.a_pegar):
            edicion.addAction(a)
        edicion.addSeparator()
        self.a_buscar = self._accion("Buscar elemento…", self.buscar_elemento, "Ctrl+F")
        edicion.addAction(self.a_buscar)
        insertar = edicion.addMenu("Añadir &elemento")
        for texto, tipo in (("&Etapa", "etapa"), ("Etapa &inicial", "inicial"), ("&Transición", "transicion")):
            insertar.addAction(texto, lambda _=False, tipo=tipo: self.insertar_teclado(tipo))
        self.a_enviar_lamina=self._accion("Enviar a plano…",self.enviar_seleccion_lamina)
        edicion.addAction(self.a_enviar_lamina)
        edicion.addSeparator()
        for a in (self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo, self.a_girar_izq, self.a_girar_der):
            edicion.addAction(a)
        edicion.addSeparator()
        for a in self.a_herr.values():
            self.addAction(a)  # Esc deselecciona sin presentar «Seleccionar» como un atajo de clic
        # Enlazar sin ratón (REQ-EDT-13): sin entrada en el menú (P-IMP-104), solo con el atajo Ctrl+K.
        self.a_conectar = self._accion("Conectar con…", self.conectar_teclado, "Ctrl+K")
        self.addAction(self.a_conectar)
        sim = bar.addMenu("&Simulación")
        for a in (self.a_ejecutar, self.a_reiniciar):
            sim.addAction(a)
        m_ajustes = bar.addMenu("A&justes")
        self.a_actualizar_arranque = self._accion("&Buscar actualizaciones al arrancar", self._buscar_al_arrancar, marcable=True)
        self.a_actualizar_arranque.blockSignals(True)
        self.a_actualizar_arranque.setChecked(actualizaciones.al_arrancar_activo(self.ajustes))
        self.a_actualizar_arranque.blockSignals(False)
        m_ajustes.addAction(self.a_actualizar_arranque)
        ayuda = bar.addMenu("A&yuda")
        self.a_ayuda_pantalla = self._accion("Ayuda de esta pantalla", self._alternar_ayuda, "F1", True)
        ayuda.addAction(self.a_ayuda_pantalla)
        ayuda.addAction("&Leyenda del dibujo", self.leyenda)
        ayuda.addAction("&Buscar actualizaciones…", lambda: self.buscar_actualizaciones(True))
        ayuda.addAction("&Acerca de GRAFCET Connect…", self.acerca)
        for menu in (archivo, edicion, ver, sim, m_ajustes, ayuda):
            bar.removeAction(menu.menuAction())
            bar.addAction(menu.menuAction())

    def _barra_herramientas(self) -> None:
        for accion, tipo in ((self.a_nuevo, "nuevo"), (self.a_abrir, "abrir"), (self.a_guardar, "guardar"),
                             (self.a_deshacer, "deshacer"), (self.a_rehacer, "rehacer"), (self.a_borrar, "borrar"),
                             (self.a_debajo, "debajo"), (self.a_cortar, "cortar"), (self.a_copiar, "copiar"),
                             (self.a_pegar, "pegar"), (self.a_ejecutar, "play"), (self.a_reiniciar, "reiniciar")):
            accion.setIcon(_icono_barra(tipo, estilo.BLANCO if tipo == "play" else estilo.TINTA))
        self.tb_proyecto = QToolBar("Proyecto")
        self.tb_proyecto.setMovable(False)
        self.tb_proyecto.setIconSize(QSize(20, 20))
        self.tb_proyecto.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for accion in (self.a_nuevo, self.a_abrir, self.a_guardar):
            self.tb_proyecto.addAction(accion)
        self.tb_proyecto.widgetForAction(self.a_guardar).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for accion, texto in ((self.a_nuevo, "Nuevo"), (self.a_abrir, "Abrir"), (self.a_guardar, "Guardar")):
            boton = self.tb_proyecto.widgetForAction(accion)
            boton.setText(texto)
            accion.changed.connect(lambda b=boton, t=texto: b.setText(t))
        self.addToolBar(self.tb_proyecto)
        self.setStyleSheet(estilo.hoja_global())
        self.tb_sim = QToolBar("Simulación")
        self.tb_sim.setObjectName("barraSimulacion")
        self.tb_sim.setMovable(False)
        self.tb_sim.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tb_sim.setIconSize(QSize(20, 20))
        self.tb_sim.addAction(self.a_ejecutar)
        self.tb_sim.addSeparator()
        self.tb_sim.addAction(self.a_reiniciar)
        self.tb_sim.widgetForAction(self.a_ejecutar).setObjectName("botonPlay")  # el único botón primario de la barra
        self.tb_sim.widgetForAction(self.a_reiniciar).setObjectName("botonReiniciar")
        self.luz_es = QToolButton()  # estado de la conexión externa (Modbus), a la vista mientras se simula
        self.luz_es.setObjectName("luzES")
        self.luz_es.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.luz_es.setCursor(Qt.CursorShape.PointingHandCursor)
        self.luz_es.setProperty("abierta", False)
        self.luz_es.clicked.connect(lambda: self.mostrar_es())
        self.estuche_vistas.layout().addWidget(self.luz_es)
        self._luz_es("desconectado", "")
        self.addToolBar(self.tb_sim)
        self.tb_conexion = QToolBar("Conexión")
        self.tb_conexion.setObjectName("barraConexion")
        self.tb_conexion.setMovable(False)
        self.tb_conexion.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        # Un solo botón conmuta entre el dibujo GRAFCET y la vista de E/S externas: pulsado (marcado) mientras se ve ésta,
        # con otro texto, tooltip e icono; _sincronizar_boton_es lo deja coherente con la página visible, sea cual sea la vía
        self.a_es = self._accion("E/S externas", self._alternar_es, marcable=True)
        self._iconos_es = (_icono_barra("conexion"), _icono_grafcet())
        from ..planos import icono_planos
        self.a_planos=self._accion("Planos",self._alternar_planos,marcable=True)
        self.a_planos.setIcon(icono_planos());self.tb_conexion.addAction(self.a_planos)
        self.tb_conexion.addAction(self.a_es)
        self._sincronizar_boton_es()
        self.paginas_es.currentChanged.connect(self._sincronizar_boton_es)
        self.addToolBar(self.tb_conexion)
        self.tb_conexion.hide()
        self._fijar_ancho_boton_es()  # con la barra ya en la ventana: el botón lleva su hoja de estilo
        self._fijar_ancho_boton_play()
        # Tras Play y Reiniciar: Deshacer · Rehacer | Cortar · Copiar · Pegar · Borrar | Dependencias · Errores.
        # De Deshacer a Borrar, solo icono y atajo; Dependencias y Errores llevan texto cuando hay sitio.
        self.tb_edit = QToolBar("Edición")
        self.tb_edit.setObjectName("barraEdicion")
        self.tb_edit.setMovable(False)
        self.tb_edit.setIconSize(QSize(20, 20))
        self.tb_edit.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._acciones_solo_icono = []
        for grupo in ((self.a_deshacer, "Deshacer", "Ctrl+Z"), (self.a_rehacer, "Rehacer", "Ctrl+Y")), ((self.a_cortar, "Cortar", "Ctrl+X"), (self.a_copiar, "Copiar", "Ctrl+C"), (self.a_pegar, "Pegar", "Ctrl+V"),
                      (self.a_borrar, "Borrar la selección", "Supr")):
            if self._acciones_solo_icono:
                self.tb_edit.addSeparator()
            for a, nombre, atajo in grupo:
                a.setToolTip(f"{nombre} ({atajo})")
                self.tb_edit.addAction(a)
                self.tb_edit.widgetForAction(a).setAccessibleName(nombre)
                self._acciones_solo_icono.append(a)
        self.tb_vista_der = QToolBar("Vista derecha")
        self.tb_vista_der.setObjectName("barraVistaDer")
        self.tb_vista_der.setMovable(False)
        self.tb_vista_der.setIconSize(QSize(18, 18))
        self.tb_vista_der.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        boton = self.diagrama.b_dependencias
        boton.setIcon(_icono_barra("dependencias"))
        boton.setAccessibleName("Mostrar dependencias")
        boton.setStyleSheet("")  # hereda el estilo común de la barra
        self.a_dependencias = self.tb_vista_der.addWidget(boton)
        self.a_dependencias.setVisible(True)
        self.a_dependencias.setEnabled(True)
        boton.show()
        # «Mostrar errores»: conmutador del aviso de diagnósticos de la cabecera del dibujo (se ve y se actualiza en vivo al editar)
        self.b_errores = QToolButton()
        self.b_errores.setText("Mostrar errores")
        self.b_errores.setCheckable(True)
        self.b_errores.setIcon(_icono_barra("aviso"))
        self.b_errores.setToolTip("Mostrar los errores y avisos del grafcet")
        self.b_errores.setAccessibleName("Mostrar errores")
        self.b_errores.toggled.connect(self._alternar_errores)
        self._errores_auto = False  # lo marcó un Play fallido (y se desmarca solo al desaparecer los errores), no el usuario
        self.a_errores = self.tb_vista_der.addWidget(self.b_errores)
        self._a_errores = (self.a_errores,)
        self.a_errores.setVisible(True)
        self._textos_en_barras(True)
        self.addToolBar(self.tb_edit)
        self.addToolBar(self.tb_vista_der)
        self.tb_proyecto.hide()
        self.herramientas_grafcet=QWidget()
        self.herramientas_grafcet.setObjectName("herramientasGrafcet")
        self.herramientas_grafcet.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.herramientas_grafcet.setProperty("modo", "editar")  # la hoja global la tiñe de verde al simular
        fila=QHBoxLayout(self.herramientas_grafcet);fila.setContentsMargins(10,5,10,5);fila.setSpacing(6)
        from ..separadores_barra import SeparadorBarra
        for numero, barra in enumerate((self.tb_sim, self.tb_edit)):
            if numero:
                fila.addWidget(SeparadorBarra())
            self.removeToolBar(barra)
            fila.addWidget(barra)
            barra.show()
        fila.addStretch(1)
        self.removeToolBar(self.tb_vista_der)
        fila.addWidget(self.tb_vista_der)
        self.tb_vista_der.show()
        self.centralWidget().layout().insertWidget(2, self.herramientas_grafcet)
        from ..cabecera_favoritos import UbicaModo
        self._ubica_modo = UbicaModo(
            self.estado, self.fila_pestanas, self.pestanas_vistas, self.luz_es,
            menu_cluster=self.menu_cluster, estuche=self.estuche_vistas,
        )
        self._acciones_edicion(False)

    # -- edición: modos, herramientas y diálogos ---------------------------------------------------
    def _foco_portapapeles(self) -> bool:
        foco = QApplication.focusWidget()
        while foco is not None and foco is not self:
            if isinstance(foco, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)) or foco is getattr(self, "variables", None):
                return True
            foco = foco.parentWidget()
        return False

    def _actualizar_portapapeles(self, *args: Any) -> None:
        e = self.edicion
        base = (
            e is not None
            and not self.solo_lectura
            and self.modo == "editar"
            and not self.destino_traer
            and not self._foco_portapapeles()
        )
        en_planos = self.paginas_es is not None and self.paginas_es.currentIndex() == 2
        if en_planos and self.panel_planos is not None:
            puede_copiar, puede_pegar = self.panel_planos.estado_portapapeles()
            self.a_copiar.setEnabled(base and puede_copiar)
            self.a_cortar.setEnabled(base and puede_copiar)
            self.a_pegar.setEnabled(base and puede_pegar)
            self.a_enviar_lamina.setEnabled(False)
            return
        disponible = base and not en_planos
        self.a_copiar.setEnabled(disponible and bool(e.sel))
        self.a_cortar.setEnabled(disponible and bool(e.sel))
        self.a_pegar.setEnabled(disponible and self._portapapeles is not None)
        self.a_enviar_lamina.setEnabled(disponible and bool(e.sel))

    def _portapapeles_accion(self, operacion: str, punto: Any = None) -> bool:
        e = self.edicion
        if e is None or self.modo != "editar" or self._foco_portapapeles() or self.destino_traer:
            return False
        if self.paginas_es is not None and self.paginas_es.currentIndex() == 2 and self.panel_planos is not None:
            return self.panel_planos.portapapeles_texto(operacion, punto)
        from ..bloques import MIME_FORMULA
        clipboard = QApplication.clipboard()
        datos = clipboard.mimeData()
        hay_formula = datos is not None and datos.hasFormat(MIME_FORMULA)
        if operacion == "pegar":
            if hay_formula or self._portapapeles is None:
                return False
            sobre_seleccion = punto is None
            if sobre_seleccion:
                viewport = self.diagrama.viewport()
                local = viewport.mapFromGlobal(QCursor.pos())
                local = local if viewport.rect().contains(local) else viewport.rect().center()
                punto = self.diagrama.mapToScene(local)
            return e.pegar_fragmento(self._portapapeles, punto, sobre_seleccion=sobre_seleccion)
        if not e.sel:
            return False
        fragmento = e.copiar_fragmento()
        if not any(fragmento.entities.values()) and not any(fragmento.presentation.get(k) for k in ("barras", "draftActions", "notes")):
            return False
        if operacion == "cortar" and not e.borrar():
            return False
        if hay_formula:
            clipboard.clear()
        self._portapapeles = fragmento
        e.informar("Selección cortada" if operacion == "cortar" else "Selección copiada")
        e.cambiado.emit()
        self._actualizar_portapapeles()
        return True

    def _menu_portapapeles(self, punto: Any, sobre_elemento: bool) -> list[tuple[str, Any]]:
        if sobre_elemento:
            opciones = [("Cortar", lambda: self._portapapeles_accion("cortar")),
                        ("Copiar", lambda: self._portapapeles_accion("copiar"))]
            if self._portapapeles and self.edicion.objetivo_pegar_acciones(self._portapapeles, punto):
                opciones.append(("Pegar", lambda: self._portapapeles_accion("pegar", punto)))
            opciones.append(("Enviar a plano…", self.enviar_seleccion_lamina))
            return opciones
        return [("Pegar", (lambda: self._portapapeles_accion("pegar", punto)) if self._portapapeles is not None else None)]

    def _acciones_edicion(self, on: bool) -> None:
        for a in (*self.a_herr.values(), self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo, *self._a_errores, self.a_girar_izq, self.a_girar_der):
            a.setEnabled(on)
        self._actualizar_portapapeles()

    def _errores_desde_menu(self, on: bool) -> None:
        self._marcar_errores(on, False)
        self._alternar_errores(on)

    def _etiquetas_desde_menu(self, on: bool) -> None:
        """«Ver > Etiquetas de transiciones»: una operación de deshacer que muestra u oculta la etiqueta de todas las transiciones."""
        if self.edicion is not None and self.modo == "editar" and not self.solo_lectura:
            self.edicion.poner_etiquetas(on)

    def _sincronizar_menu_dibujo(self) -> None:
        e = self.edicion
        editable = e is not None and self.modo == "editar" and not self.solo_lectura and bool(e.M["transitions"])
        self.a_ver_etiquetas.blockSignals(True)
        self.a_ver_etiquetas.setChecked(bool(editable and e.etiquetas_visibles()) if e is not None and self.modo == "editar" else False)
        self.a_ver_etiquetas.blockSignals(False)
        self.a_ver_etiquetas.setEnabled(editable)
        self.a_ver_dependencias.setChecked(self.diagrama.dependencias)
        self.a_ver_dependencias.setEnabled(self.a_dependencias.isEnabled())
        self.a_ver_errores.setChecked(self.b_errores.isChecked())
        self.a_ver_errores.setEnabled(self.a_errores.isEnabled())

    def leyenda(self) -> None:
        """«Ayuda > Leyenda del dibujo»: una ventana propia (no modal) con lo que significa cada trazo y color."""
        if self._leyenda is None:
            self._leyenda = Leyenda(self)
        self._leyenda.show()
        self._leyenda.raise_()
        self._leyenda.activateWindow()

    def guardar_imagen(self) -> None:
        editando = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar el dibujo", f"{self.edicion.titulo if editando else self.v.key}.png",
                                              "Imagen PNG (*.png)")
        dependencias = self.diagrama.dependencias  # lo que la vista dibuja ahora (el botón «Mostrar dependencias»)
        img = (imagen(self.edicion.M, {}, dependencias=dependencias) if editando else
               imagen(self.v.model, self.v.state(), dependencias=dependencias) if ruta else None)
        if ruta and not img.save(ruta):
            QMessageBox.warning(self, TITULO, f"No se pudo guardar {ruta}")

    def acerca(self) -> None:
        AcercaDe(self).exec()

    # -- actualizaciones -----------------------------------------------------------------------
    def _buscar_al_arrancar(self, on: bool) -> None:
        self.ajustes.setValue(actualizaciones.CLAVE_AL_ARRANCAR, bool(on))
        self.ajustes.sync()

    def buscar_actualizaciones(self, manual: bool = False) -> None:
        """Consulta la última versión publicada en segundo plano. En el arranque (manual=False) no dice nada si falla."""
        if manual:
            self.statusBar().showMessage("Buscando actualizaciones…", 3000)
        self.comprobador.comprobar(manual)

    def _resultado_actualizacion(self, manual: bool, r: actualizaciones.Resultado) -> None:
        if r.estado == "nueva":
            self._avisar_version_nueva(r)  # al arrancar y a mano, el mismo diálogo (no se guarda nada al descartarlo)
        elif manual:
            texto = ("Ya tienes la última versión de GRAFCET Connect." if r.estado == "al_dia" else
                     "No se ha podido comprobar: sin conexión o sin respuesta del servidor.")
            QMessageBox.information(self, TITULO, texto)

    def _avisar_version_nueva(self, r: actualizaciones.Resultado, intentos: int = 40) -> None:
        """Abre el diálogo de versión nueva sobre la ventana, ya visible; si aún no lo está (el arranque), espera un poco."""
        if self._dialogo_version is not None and self._dialogo_version.isVisible():
            return
        if not self.isVisible():
            if intentos > 0:
                QTimer.singleShot(250, self, lambda: self._avisar_version_nueva(r, intentos - 1))
            return
        self._version_nueva = r
        self._dialogo_version = DialogoVersionNueva(self, APP_VERSION, r.version, r.url, ICONO_PROGRAMA)
        self._dialogo_version.open()  # (no bloquea: es modal solo para esta ventana)
