"""Simulación: Play, Stop y Reiniciar, `_act`, `refrescar`, las entradas, el reloj, el diagnóstico y las tablas de Variables y Temporizadores y la traza."""
from __future__ import annotations

import copy
import html
from .. import estilo
from ..diagrama import COL
from ..edicion import Edicion, sin_codigos
from ..mensajes import amable, motivo_parada
from ..paneles import CabeceraCompacta, ContextoNombres
from math import ceil
from time import perf_counter
from typing import Any
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import (QApplication, QGroupBox, QHeaderView, QLabel, QLineEdit, QListWidgetItem, QMenu, QMessageBox,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem)
from grafcet.engine import Session
from grafcet.profile import SEMANTIC_OPTIONS, normalize_options
from grafcet.view import Vista, t_trunc
from .constantes import ARRIBA_CAJA, ERRORES, ESTADOS, TICK_MS, TITULO, TRAZA
from .dialogos import _icono_barra
from .widgets import _BotonEntrada


class Simulacion:
    """Simulación: Play, Stop y Reiniciar, `_act`, `refrescar`, las entradas, el reloj, el diagnóstico y las tablas de Variables y Temporizadores y la traza. Sin estado propio: usa los atributos de `Ventana` (la fachada) y llama a los demás métodos a través de `self`."""

    @staticmethod
    def _tabla(cols: list[str], anchos: tuple[int | None, ...] | None = None) -> QTableWidget:
        """Tabla de estado del panel derecho. `anchos`: el de cada columna (None: la que se lleva lo que sobra). Texto de 12 px,
        sin barras de desplazamiento propias (`ajustar_tabla` le da el alto de sus filas), el texto largo se parte en dos líneas
        o se elide con «…» y va entero en la ayuda de la celda."""
        t = QTableWidget(0, len(cols))
        t.setHorizontalHeader(CabeceraCompacta(Qt.Orientation.Horizontal, t))  # (pinta el texto de la cabecera sin los márgenes de más de la de Qt)
        t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(estilo.ALTO_FILA)
        t.verticalHeader().setMinimumSectionSize(estilo.ALTO_FILA_COMPACTA)
        t.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)  # (el alto de cada fila lo pone `ajustar_tabla`: con ResizeToContents, cada celda que cambia hace que Qt mida todas las filas)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)  # elegir una fila pone su texto entero en la barra de estado
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # conserva el final del nombre, que es lo que lo distingue
        t.setWordWrap(True)
        t.setTabKeyNavigation(False)  # el Tab sale de la tabla, no salta de celda en celda
        t.setShowGrid(False)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(f"QTableWidget {{ font-size: {estilo.T_PEQUENA}px; border: 0; }} "
                        f"QTableWidget[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; }} "  # (la hoja propia manda sobre la global: lleva su anillo)
                        f"QHeaderView::section {{ font-size: {estilo.T_PEQUENA}px; font-weight: 400; padding: 4px 0; }} "  # (el texto lo pinta `CabeceraCompacta`, a 4 px: donde empieza el de las celdas)
                        f"QTableWidget::item {{ padding: 0; }}")
        cab = t.horizontalHeader()
        cab.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cab.setStretchLastSection(False)
        cab.setMinimumSectionSize(24)
        cab.setTextElideMode(Qt.TextElideMode.ElideRight)
        for i, ancho in enumerate(anchos or (None,) * len(cols)):
            if ancho is None:
                cab.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                cab.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                cab.resizeSection(i, ancho)
        t.setMinimumHeight(0)
        return t

    @staticmethod
    def ajustar_tabla(t: QTableWidget) -> None:
        """La tabla mide la cabecera más sus filas (con el alto que pide el texto partido): así no necesita barra propia y el
        panel, si hace falta, se desplaza una sola vez."""
        t.resizeRowsToContents()
        Simulacion._alto_tabla(t)

    @staticmethod
    def _alto_tabla(t: QTableWidget) -> None:
        """El alto de la tabla: su cabecera y sus filas tal como están (sin volver a medirlas)."""
        alto = t.horizontalHeader().height() + sum(t.rowHeight(r) for r in range(t.rowCount())) + 2 * t.frameWidth() + 4
        if t.height() != alto or t.minimumHeight() != alto:
            t.setFixedHeight(alto)

    def reiniciar(self) -> None:
        """En Play vuelve a la situación inicial y sigue en Play; con E/S externas la conexión se conserva: solo se vincula
        una sesión nueva, que escribe sus salidas solo tras leer y aplicar las entradas de la planta. En Pausa ya está todo a
        0 y sin estado (Pausa es «todo a 0 hasta un nuevo Play»): no hay nada que reiniciar, solo se vuelve a pedir el cero
        a la planta si hay conexión."""
        self._mostrar_pagina(False)
        if not self.a_ejecutar.isChecked():
            self.modbus.pausar(diagnostico=True)
            if self.v is None:
                return  # Todavía no hay una simulación cuyo estado refrescar.
            self._sin_estado()
            self.refrescar()
            self.refrescar_edicion()
            return
        if not self._preparar_sesion():
            self.a_ejecutar.setChecked(False)  # no se ha podido: Pausa
            return
        self._iniciar_reloj()
        self.refrescar()

    def _sin_estado(self) -> None:
        """Pausa = todo a 0 hasta un nuevo Play: el GRAFCET no tiene ninguna etapa activa ni temporizador en curso, y las
        tablas de estado no enseñan lo de la sesión anterior. La sesión que había se sustituye por otra sin iniciar (estado
        «preparada» del motor: ni situación ni valores); Play siempre crea una nueva desde la situación inicial. No se
        toca el motor: solo se deja de apuntar a la sesión en marcha."""
        s = self.v.s if self.v else None
        if s is not None:
            self.v.s = Session(s.cm, s.scenario, s.ctl.budget, options=s.options)
            self.v.start_diags = []

    def _preparar_sesion(self) -> bool:
        """Compila lo que se edita y deja en self.v una sesión nueva, estable y en la situación inicial (Play siempre
        arranca de cero, y Reiniciar en Play también). Con Modbus vivo la vincula al TCP existente, sin reconectar: no se
        escribe nada hasta leer las entradas de la planta, aplicarlas a la sesión nueva y calcular (leer, aplicar, calcular,
        escribir). Si no puede, avisa y devuelve False sin tocar la conexión."""
        if self.edicion is None:
            self._establecer_edicion(self._edicion_desde_fuente() if self.v else Edicion.nuevo())
        if self._variables_sin_nombre():
            return False
        e = self.edicion
        diags = e.diagnosticos()
        if any(d["blocks"] for d in diags):
            self._armar_avisos(True)  # Play fallido: el aviso aparece desplegado con la lista
            self._no_simulable()
            return False
        if diags:
            self._armar_avisos(False)  # solo avisos que no bloquean: se simula y el aviso queda plegado
        ayuda = self._ayuda if self._ayuda and not e.ed.undo_stack else "Simulación del grafcet."
        nueva = Vista(e.ed.model["id"], e.titulo, ayuda, lambda: (copy.deepcopy(e.ed.model), e.layout()), self.options,
                      presentation=e.ed.presentation)
        if nueva.s is None:  # compila con las lecturas por defecto, pero no con el perfil efectivo
            lineas = [f"• {e.sust(d.message)}" for d in nueva.compile_diags]  # (el texto del núcleo, con nombres y sin ID)
            QMessageBox.warning(self, TITULO, "El grafcet no compila con las lecturas de interpretación activas, no se puede "
                                "simular todavía:\n\n" + "\n".join(lineas[:8]) + ("\n…" if len(lineas) > 8 else ""))
            return False
        if not self.modbus.activo:
            contactos={vid:True for (proyecto,vid),nc in self._entradas_nc.items() if proyecto==self._proyecto and nc and vid in nueva.s.cm.variables}
            if contactos:nueva.act("fijar",{"cambios":contactos})
        if nueva.s.status != "pausada-estable":
            self._avisar_motor(nueva, al_arrancar=True)
            return False
        if self.modbus.activo:
            try:
                config = self.panel_es.obtener()
                config.validar(e.ed.model)  # lo editado puede haber dejado el mapa sin variable o de otro tipo
                self.modbus.vincular(nueva.s, config, e.ed.model)
            except ERRORES as exc:
                texto = f"No se puede ejecutar con la conexión y las asignaciones actuales: {exc}. Revise la asignación; la conexión se conserva."
                self.modbus.mensaje = texto
                self.panel_es.mostrar_estado(self.modbus.estado, texto)
                QMessageBox.warning(self, TITULO, texto)
                return False
        self.v = nueva
        self.fuente = {"tipo": "editor"}
        self._avisos_ejecucion = []
        self._entradas()
        return True

    @staticmethod
    def _medidas_tabla() -> tuple[QFontMetrics, QFontMetrics, Any]:
        """La letra de las celdas de estado, la de las cifras y lo que mide una cabecera (su texto, a 4 px del borde, más 2 px de holgura)."""
        fm = QFontMetrics(estilo.fuente(estilo.T_PEQUENA))
        return fm, QFontMetrics(estilo.fuente(estilo.T_CIFRA, mono=True)), lambda texto: fm.horizontalAdvance(texto) + 6

    def _planes_vars(self) -> list[dict[str, Any]]:
        """Los repartos de «Salidas y variables», de más a menos completo (el nombre manda: ver `ReparteColumnas`): todo entero; «Modo» abreviado
        («cont.», «mem.»); y, por último, la cabecera «Contrib.». **Ninguna columna se esconde** (P13 rechazada)."""
        fm, cifras, cab = self._medidas_tabla()
        valor = max(cab("Valor"), cifras.horizontalAdvance("False") + 8)  # (una memoria booleana sin salida enseña «False»: que no se corte)
        contribuyen, corta = cab("Contribuyen"), cab("Contrib.")
        modo_corto = max(cab("Modo"), fm.horizontalAdvance("cont.") + 7, fm.horizontalAdvance("mem.") + 7)
        modo = max(cab("Modo"), fm.horizontalAdvance("continua") + 7, fm.horizontalAdvance("memoria") + 7)
        return [{"anchos": {1: modo, 2: valor, 3: contribuyen}, "modo_corto": False},
                {"anchos": {1: modo_corto, 2: valor, 3: contribuyen}, "modo_corto": True},
                {"anchos": {1: modo_corto, 2: valor, 3: corta}, "modo_corto": True},
                # el más apretado (panel de 218 px con barra vertical): sin barra a los lados, con el nombre en unos 90 px
                {"anchos": {1: max(cab("Modo") - 2, fm.horizontalAdvance("mem.") + 5), 2: max(cifras.horizontalAdvance("False") + 4, cab("Valor") - 2),
                            3: fm.horizontalAdvance("Contr.") + 3}, "modo_corto": True, "apretado": True}]

    def _elegir_plan_vars(self, plan: dict[str, Any]) -> None:
        self.t_vars.itemDelegateForColumn(1).corto = plan["modo_corto"]

    def _planes_temp(self) -> list[dict[str, Any]]:
        """Los repartos de «Temporizadores» (P-IMP-30: dónde, estado, lleva, preset): «Estado» entero («parado», «contando», «vencido») o
        abreviado («par.», «cont.», «venc.», con su color) y, por último, la cabecera «Est.». **Ninguna columna se esconde.**"""
        fm, cifras, cab = self._medidas_tabla()
        tiempo = cifras.horizontalAdvance("12,5 s") + 8
        lleva, preset = max(cab("Lleva"), tiempo), max(cab("Preset"), tiempo)
        estado = max(cab("Estado"), fm.horizontalAdvance("contando") + 7)
        corto = max(cab("Est."), *(fm.horizontalAdvance(t) + 7 for t in ("par.", "cont.", "venc.")))
        return [{"anchos": {1: estado, 2: lleva, 3: preset}, "corto": False},
                {"anchos": {1: max(cab("Estado"), corto), 2: lleva, 3: preset}, "corto": True},
                {"anchos": {1: corto, 2: lleva, 3: preset}, "corto": True},
                {"anchos": {1: corto, 2: max(cab("Lleva") - 2, cifras.horizontalAdvance("0,0 s") + 4), 3: max(cab("Preset") - 2, cifras.horizontalAdvance("0,0 s") + 4)},
                 "corto": True, "apretado": True}]

    def _elegir_plan_temp(self, plan: dict[str, Any]) -> None:
        self.t_temp.itemDelegateForColumn(1).corto = plan["corto"]

    def _detallar(self, texto: str) -> None:
        """La línea de detalle de la barra de estado: el nombre entero de lo que tiene el foco o está elegido (vacía, se esconde)."""
        if self.l_detalle.text() != texto:
            self.l_detalle.setText(texto)
        self.l_detalle.setVisible(bool(texto))

    @staticmethod
    def _detalle_entrada(b: _BotonEntrada) -> str:
        return f"{b.nombre_completo()} = {b.text().rpartition(' = ')[2]} · entrada"

    @staticmethod
    def _detalle_fila(tabla: QTableWidget, fila: int) -> str:
        if not 0 <= fila < tabla.rowCount():
            return ""
        partes = (str(tabla.item(fila, c).data(Qt.ItemDataRole.UserRole) or tabla.item(fila, c).text())
                  for c in range(tabla.columnCount()) if tabla.item(fila, c) is not None)
        return " · ".join(p for p in partes if p)  # (un campo vacío no deja un « · » colgando al final)

    def _sobre_entrada(self, b: _BotonEntrada, dentro: bool) -> None:
        """El puntero entra en una entrada de la simulación o sale de ella: la línea de detalle dice su nombre entero."""
        self._bajo_raton = b if dentro else (None if self._bajo_raton is b else self._bajo_raton)
        self._detalle_del_foco()

    def _sobre_fila(self, tabla: QTableWidget | None, fila: int) -> None:
        """El puntero está sobre una fila de las tablas de estado (o fuera de ellas: `fila` < 0)."""
        self._bajo_raton = (tabla, fila) if tabla is not None and fila >= 0 else None
        self._detalle_del_foco()

    def _detalle_del_foco(self, *_args: Any) -> None:
        """La línea de detalle de la barra de estado dice el nombre entero de lo que se señala o se ha elegido, sin teclado y sin esperar a la
        ayuda emergente: lo que tiene el puntero encima (una entrada de la simulación, una fila de las tablas de estado) y, si no hay
        puntero encima, lo que tiene el foco (una entrada, la fila elegida de una tabla, la de variables). Sin nada de eso, se esconde."""
        f = QApplication.focusWidget()
        texto = ""
        try:
            r = self._bajo_raton
            if isinstance(r, _BotonEntrada):
                texto = self._detalle_entrada(r)
            elif isinstance(r, tuple):
                texto = self._detalle_fila(*r)
            elif isinstance(f, _BotonEntrada):
                texto = self._detalle_entrada(f)
            elif isinstance(f, QTableWidget) and f in (self.t_vars, self.t_temp):
                texto = self._detalle_fila(f, f.currentRow())
            elif f is self.variables.tabla and self.variables.tabla.currentRow() >= 0:
                self.variables._detallar(self.variables.tabla.currentRow())
                return
        except RuntimeError:  # la entrada o la tabla ya no existen (se rehicieron)
            self._bajo_raton = None
        self._detallar(texto)

    def _poner_reloj(self, texto: str) -> None:
        """El texto del reloj de la barra de estado («τ = 12,5 s · próximo vencimiento: 15 s»). Crece con el tiempo y la barra de
        estado reparte su ancho una vez por cambio: el reloj se queda con el ancho de lo más largo que ha escrito, para que
        no pierda ningún carácter (ni «1 s» en «próximo vencimiento: 3 s») ni la barra se mueva en cada tic."""
        if self.l_reloj.text() != texto:
            self.l_reloj.setText(texto)
        self.l_reloj.ensurePolished()  # (con la letra de su hoja de estilo, no la de la plataforma)
        ancho = self.l_reloj.fontMetrics().horizontalAdvance(texto) + 2 * self.l_reloj.margin() + 8
        if ancho > self._ancho_reloj:
            self._ancho_reloj = ancho
            self.l_reloj.setMinimumWidth(ancho)
            self.statusBar().updateGeometry()
            self.statusBar().layout().activate()

    def _no_simulable(self) -> None:
        lineas = self.edicion.resumen(self.edicion.diagnosticos())
        QMessageBox.warning(self, TITULO, "El grafcet no compila, no se puede simular todavía:\n\n"
                            + "\n".join(f"• {x}" for x in lineas[:8]) + ("\n…" if len(lineas) > 8 else ""))
        # cada elemento con un error parpadea en naranja (después del aviso, que lo tapa) y se lleva a la vista
        self.edicion.parpadear(sorted(self.edicion.marcados_de(self.edicion.diagnosticos())))

    # -- acciones de simulación -------------------------------------------------------------------
    def _act(self, op: str, **body: Any) -> None:
        if self.modbus.activo:
            self.aviso.setText("Con E/S externas use Play/Stop; desconecte para depurar manualmente")
            self.aviso.setVisible(True)
            return
        if self.v is None:
            return
        try:
            self.v.act(op, body)
            self.aviso.setText("")
            self.aviso.setVisible(False)
        except ERRORES as exc:
            self.aviso.setText(f"No disponible: {exc}")
            self.aviso.setVisible(True)
        self.refrescar()

    def _entradas(self) -> None:
        while self.rejilla.count():
            w = self.rejilla.takeAt(0).widget()
            if w is not None:
                w.hide()  # hasta que se borre, no se ve (si no, asoma tras los nuevos al cambiar la disposición)
                w.setParent(None)
                w.deleteLater()
        self.botones, self.campos = {}, {}
        numeric = self.v.model.get("numericInputs", {})
        fila = 0
        for var in self.v.model["inputs"]:
            if var in numeric:
                etiqueta = QLabel(f"<b>{html.escape(self.nombre(var))}</b> =")
                etiqueta.setWordWrap(True)
                self.rejilla.addWidget(etiqueta, fila, 0, 1, 4)
                fila += 1
                campo = QLineEdit()
                campo.setPlaceholderText("valor" + (" entero" if numeric[var] == "int" else ""))
                campo.returnPressed.connect(lambda v=var: self._valor(v))
                self.rejilla.addWidget(campo, fila, 0, 1, 3)
                b = QPushButton("Aplicar")
                b.clicked.connect(lambda _=False, v=var: self._valor(v))
                self.rejilla.addWidget(b, fila, 3)
                self.campos[var] = campo
                self.botones[var] = b
                fila += 1
                continue
            b = _BotonEntrada()
            b.interruptor = self._tipos_entrada.get((self._proyecto, var), False)
            b.nc = self._entradas_nc.get((self._proyecto,var),False)
            self._ayuda_entrada(b)
            b.pressed.connect(lambda v=var, b=b: self._entrada_presionada(v, b))
            b.released.connect(lambda v=var, b=b: self._entrada_soltada(v, b))
            b.clicked.connect(lambda _=False, v=var, b=b: b.interruptor and self._act("entrada", var=v))
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda p, v=var, b=b: self._menu_entrada(v, b, p))
            b.sobre.connect(lambda on, b=b: self._sobre_entrada(b, on))
            self.rejilla.addWidget(b, fila, 0, 1, 4)
            self.botones[var] = b
            fila += 1
        self._bajo_raton = None  # (los botones de antes se borran)
        contexto = ContextoNombres([self.nombre(v) for v, b in self.botones.items() if isinstance(b, _BotonEntrada)])
        for b in self.botones.values():
            if isinstance(b, _BotonEntrada):
                b.contexto = contexto
        if not self.v.model["inputs"]:
            self.rejilla.addWidget(QLabel("Sin entradas"), 0, 0)
        self._reflujo_entradas()
        self._densidad_lateral()
        QTimer.singleShot(0, self, self._reflujo_entradas)  # (otra vez con la hoja de estilo ya aplicada: la letra puede medir distinto)
        if hasattr(self, "pestanas") and hasattr(self, "props"):
            self._orden_tab()

    def _reflujo_entradas(self) -> None:
        """Con poca altura (un cuarto de pantalla) las entradas booleanas van de dos en dos: así caben también las tablas."""
        botones = [self.rejilla.itemAt(i).widget() for i in range(self.rejilla.count())]
        if not botones or not all(isinstance(b, _BotonEntrada) for b in botones):
            return
        por_fila = 2 if self._compacto[1] else 1
        if por_fila == 2:  # de dos en dos solo si los nombres caben enteros en media fila (si no, uno por fila y la tabla se desplaza)
            mitad = (self.ancho_derecho - 2 * estilo.E1 - estilo.ANCHO_BARRA - estilo.E1) // 2
            if any(b.ancho_natural(f"{self.nombre(v)} = 0") > mitad for v, b in self.botones.items() if isinstance(b, _BotonEntrada)):
                por_fila = 1
        for b in botones:
            self.rejilla.removeWidget(b)
        for i, b in enumerate(botones):
            self.rejilla.addWidget(b, i // por_fila, (i % por_fila) * (4 // por_fila), 1, 4 // por_fila)
        self._alto_entradas()

    def _densidad_lateral(self) -> None:
        """En un cuarto de pantalla el panel de simulación gana alto (títulos de caja 4 px más bajos y sin margen inferior) para que se
        vea también la fila de temporizadores sin desplazarse."""
        bajo = self._compacto[1]
        for caja in getattr(self, "_cajas_lado", []):
            caja.setStyleSheet(f"QGroupBox {{ margin-top: {estilo.E1 * 5}px; }}" if bajo else "")
            caja.layout().setContentsMargins(0, ARRIBA_CAJA, 0, 0 if bajo else estilo.E1)

    @staticmethod
    def _ayuda_entrada(b: _BotonEntrada) -> None:
        b.ayuda_base = (("NC: reposo 1, accionado 0 · " if b.nc else "NA: reposo 0, accionado 1 · ") + ("Interruptor: clic para conmutar · Botón derecho: cambiar tipo" if b.interruptor else
                     "Pulsador momentáneo: presionar invierte el reposo, soltar lo restaura · Ctrl+clic: enclavar mientras se mantiene Ctrl (otro clic libera) · Botón derecho: cambiar tipo"))
        b.setToolTip(b.ayuda_base)

    def _cambiar_tipo_entrada(self, var: str, interruptor: bool) -> None:
        self._tipos_entrada[self._proyecto, var] = interruptor
        b = self.botones[var]
        b.interruptor, b.enclavado, b.liberar = interruptor, False, False
        self._ayuda_entrada(b)
        b.indicar(b.isChecked())

    def _menu_entrada(self, var: str, b: _BotonEntrada, punto: Any) -> None:
        if self.modbus.activo:
            return
        menu = QMenu(b)
        for tipo, texto in ((True, "Convertir en interruptor"), (False, "Convertir en pulsador")):
            a = menu.addAction(texto, lambda _=False, tipo=tipo: self._cambiar_tipo_entrada(var, tipo))
            a.setEnabled(tipo != b.interruptor)
        menu.addSeparator()
        for nc,texto in ((False,"Normalmente abierto (NA)"),(True,"Normalmente cerrado (NC)")):
            a=menu.addAction(texto,lambda _=False,nc=nc:self._cambiar_contacto(var,nc))
            a.setCheckable(True);a.setChecked(b.nc==nc)
        menu.exec(b.mapToGlobal(punto))

    def _cambiar_contacto(self,var,nc):
        self._entradas_nc[self._proyecto,var]=nc
        b=self.botones[var];b.nc=nc;b.enclavado=b.liberar=False
        self._ayuda_entrada(b);self._fijar_entrada(var,nc)

    def _fijar_entrada(self, var: str, valor: bool) -> None:
        if self.modo == "simular" and not self.modbus.activo and self.v is not None:
            if self.v.state().get("values", {}).get(var) is not valor:
                self._act("entrada", var=var)

    def _entrada_presionada(self, var: str, b: _BotonEntrada) -> None:
        if self.modbus.activo:
            self._act("entrada", var=var)
            return
        if b.interruptor:
            return  # como antes, el interruptor conmuta con clicked, al completar el clic
        elif b.enclavado:
            b.enclavado, b.liberar = False, False
            self._fijar_entrada(var, b.nc)
        else:
            b.enclavado, b.liberar = b.control, not b.control
            self._fijar_entrada(var, not b.nc)

    def _soltar_enclavados(self) -> None:
        for var, b in list(self.botones.items()):
            if isinstance(b, _BotonEntrada) and b.enclavado and not b.interruptor:
                b.enclavado, b.liberar = False, False
                self._fijar_entrada(var, b.nc)

    def _entrada_soltada(self, var: str, b: _BotonEntrada) -> None:
        if b.liberar:
            b.liberar = False
            self._fijar_entrada(var, b.nc)
        b.control = False
        self.refrescar()

    def nombre(self, ident: str) -> str:
        """Nombre visible de una variable, etapa, parcial o transición (los ID internos no se muestran)."""
        return self.v.model.get("names", {}).get(ident, ident) if self.v else ident

    def _valor(self, var: str) -> None:
        self._act("valor", var=var, texto=self.campos[var].text())

    def _opciones(self, options: dict[str, str]) -> None:
        self.options = normalize_options(options)  # cambia el perfil efectivo: ejecución nueva
        play = self.a_ejecutar.isChecked()
        if self.edicion is not None:
            self.fuente = {"tipo": "editor"}
        self._cargar()
        if play:
            self.a_ejecutar.setChecked(True)

    def _marcar_play(self, on: bool) -> None:
        """Pone el aspecto del control de ejecución (marca, texto e icono) sin provocar la transición."""
        self.a_ejecutar.blockSignals(True)
        self.a_ejecutar.setChecked(on)
        self.a_ejecutar.blockSignals(False)
        self.a_ejecutar.setText("Stop" if on else "Play")
        self.a_ejecutar.setIcon(_icono_barra("stop" if on else "play", estilo.BLANCO))
        self._centrar_play(on)

    def _centrar_play(self, on: bool) -> None:
        """El botón mide siempre lo del más ancho de sus dos estados y su contenido (icono y texto) se pinta pegado a la izquierda: lo que sobra en el
        estado más corto se reparte como relleno a los dos lados, para que quede centrado (con foco también: allí el borde es dos puntos más grueso)."""
        boton = self.tb_sim.widgetForAction(self.a_ejecutar) if hasattr(self, "tb_sim") else None
        relleno = getattr(self, "_relleno_play", {}).get(on)
        if boton is None or relleno is None:
            return
        izq, der = relleno
        boton.setStyleSheet(f"QToolButton#botonPlay {{ padding: 0 {der}px 0 {izq}px; }}"
                            f"QToolButton#botonPlay[tecl=\"true\"]:focus {{ padding: 0 {max(0, der - 2)}px 0 {max(0, izq - 2)}px; }}")

    def _ejecutar(self, on: bool) -> None:
        """Play (on) o Pausa: el único control de ejecución. Play compila lo editado y arranca siempre una sesión nueva desde
        la situación inicial; Pausa detiene la evolución, vuelve a editar y deja todo a 0 hasta el siguiente Play: sin etapas
        activas ni temporizadores y, con E/S externas, todas las salidas asignadas a 0. La conexión Modbus no se cierra:
        Pausa conserva TCP y sigue observando las entradas, y Play vincula la sesión nueva al TCP existente."""
        if self._transicion_ui:
            return
        self._encuadre_modo = self.diagrama.guardar_encuadre()
        self._generacion_encuadre = getattr(self, "_generacion_encuadre", 0) + 1
        generacion = self._generacion_encuadre
        self._transicion_ui = True
        try:
            venia_de_play = self.modo == "simular"
            if on and not self._preparar_sesion():
                on = False  # no arranca (no compila, inestable, mapa de E/S inválido…): sigue en Pausa
            self.modo = "simular" if on else "editar"
            self._marcar_play(on)
            if not getattr(self, "_conservar_vista_al_parar", False):
                self._mostrar_pagina(False)
            if not on:
                self.modbus.pausar()
                if self.edicion is None:
                    self._establecer_edicion(self._edicion_desde_fuente() if self.v else Edicion.nuevo())
            self._poner_modo()
            if not on and venia_de_play:
                self._sin_estado()
                self.refrescar()  # las tablas dejan de enseñar la sesión anterior y las entradas se deshabilitan
            if on:
                self.refrescar()
            if self.modbus.activo:
                self.modbus.solicitar_ejecucion(on)
                self._proxima_lectura.start(1)  # Play/Stop no esperan al sondeo configurado.
            if on or self.modbus.activo:  # con la conexión viva el temporizador sigue en Pausa: observa las entradas
                self._iniciar_reloj()
                self.rt.start()
            else:
                self.rt.stop()
        finally:
            estado = self._encuadre_modo
            self._encuadre_modo = None
            self.diagrama.restaurar_encuadre(estado)
            def restaurar():
                if self._generacion_encuadre == generacion:
                    self.diagrama.restaurar_encuadre(estado)
            QTimer.singleShot(0, self.diagrama, restaurar)
            self._transicion_ui = False

    def _vigilar_motor(self) -> bool:
        """En Play, si el motor deja de estar en situación estable (inestable o detenido por un diagnóstico): se para, pasa a
        Pausa/edición y se cuenta por qué. Devuelve si ha parado."""
        s = self.v.s if self.v else None
        if s is None or s.status == "pausada-estable":
            return False
        self._avisar_motor(self.v)
        self.a_ejecutar.setChecked(False)
        return True

    def _avisar_motor(self, vista: Vista, al_arrancar: bool = False) -> None:
        """El motor no ha quedado en situación estable. Inestable (D-LIM-EVOL: no la alcanza dentro de su límite de
        evoluciones): aviso modal, una sola vez por episodio. Otro diagnóstico: mensaje en la barra de estado (o aviso, si
        era al arrancar). Con Modbus vivo, lo que ya se estuviera controlando pasa a estado seguro (cero) sin cerrar la
        conexión. Los detalles se quedan entre los diagnósticos del panel de edición."""
        d = vista._diag(vista.s.diagnostics[-1]) if vista.s.diagnostics else None  # con nombres, no ID internos
        inestable = d is not None and d["code"] == "D-LIM-EVOL"
        m = self.modbus
        if m.activo and (inestable or not al_arrancar) and (m.adaptador.sesion is not None or m.escritos):
            m.pausar(diagnostico=True)
        evoluciones = [r for r in vista.s.trace.records if r["kind"] == "evolucion"]
        motivos = motivo_parada(d["code"], d["message"], evoluciones, vista.names) if d else []
        self._avisos_ejecucion = motivos
        if motivos:
            self._armar_avisos(True)
        if inestable:
            if self._aviso_inestable_sesion is not vista.s:
                self._aviso_inestable_sesion = vista.s
                self._avisar_inestable(motivos[-1][0] if motivos else "")
        elif al_arrancar:
            QMessageBox.warning(self, TITULO, "No se puede ejecutar: revise los diagnósticos del grafcet."
                                + (f"\n\n{amable(d['message'], d['code'])}" if d else ""))
        else:
            texto = motivos[0][0] if motivos else "Simulación detenida."
            self.statusBar().showMessage(f"{texto} Vea el motivo en la lista de diagnósticos.", 12000)

    def _avisar_inestable(self, causa: str = "") -> None:
        """Ventana modal con un solo botón; no abre un bucle de eventos propio (se llama desde el temporizador). `causa` es
        la frase que nombra las transiciones que se repiten."""
        texto = "Simulación detenida: el grafcet no alcanza una situación estable." + (f"\n\n{causa}" if causa else "")
        cuadro = QMessageBox(QMessageBox.Icon.Warning, TITULO, texto, QMessageBox.StandardButton.Ok, self)
        cuadro.button(QMessageBox.StandardButton.Ok).setText("Aceptar")
        cuadro.finished.connect(lambda _=0: setattr(self, "_popup_inestable", None))
        self._popup_inestable = cuadro
        cuadro.open()

    def _iniciar_reloj(self):
        self.reloj.start()
        self._marca_reloj_ns = self._resto_reloj_ns = 0

    def _tick(self) -> None:
        marca = self.reloj.nsecsElapsed() if self.reloj.isValid() else 0
        us, self._resto_reloj_ns = divmod(max(0, marca - self._marca_reloj_ns) + self._resto_reloj_ns, 1000)
        self._marca_reloj_ns = marca
        if self.modbus.activo:
            ejecutar = (self.a_ejecutar.isChecked() and self.modbus.estado == "conectado"
                        and not self.modbus.reiniciando and self.modbus.adaptador.sesion is not None)
            if ejecutar and self.modbus.en_marcha and self.v and self.v.s and self.v.s.status == "pausada-estable":
                self.v.s.advance_to(self.v.s.z.time + us)
            self.modbus.tick(ejecutar)
            if self.a_ejecutar.isChecked():
                self._vigilar_motor()
                if self.modbus.estado in ("error", "desconectado", "diagnostico") or self.modbus.adaptador.sesion is None:
                    self._parar_sin_cambiar_vista()
            self._proxima_lectura.stop()
            if (self.modbus.estado == "conectado" and not self.modbus.fallo_motor
                    and self.modbus.futuro is None):
                espera = max(1, ceil((self.modbus.proxima - perf_counter()) * 1000))
                self._proxima_lectura.start(espera)
            self._refrescar_modbus()
            if not self.modbus.activo:
                self.rt.setInterval(TICK_MS)
                self.rt.stop()
            return
        if not self.a_ejecutar.isChecked():  # Pausa sin conexión: el reloj no tiene nada que avanzar
            self.rt.stop()
            self.rt.setInterval(TICK_MS)
            return
        if self.v is None or self.v.s is None:
            self.a_ejecutar.setChecked(False)
            return
        if not self._vigilar_motor():
            self._act("avanzar", us=us)

    def _fijar_ancho_boton_play(self) -> None:
        """El botón de Play mide lo del más ancho de sus dos estados (Play, Stop) y su contenido va centrado en los dos (`_centrar_play`). El ancho sale
        de medir cada estado sin relleno extra."""
        boton = self.tb_sim.widgetForAction(self.a_ejecutar)
        inicial = self.a_ejecutar.isChecked()
        self._relleno_play = {}
        boton.setStyleSheet("")
        contenido = {}
        for on in (False, True):
            self._marcar_play(on)
            contenido[on] = boton.sizeHint().width() - 2 - 2 * 16  # (el contenido: sin el borde ni el relleno de la hoja global)
        ancho = max(max(contenido.values()) + 2 * 16 + 2, 92)
        self._relleno_play = {on: ((ancho - 2 - c) // 2, ancho - 2 - c - (ancho - 2 - c) // 2) for on, c in contenido.items()}
        boton.setFixedWidth(ancho)
        boton.resize(ancho, boton.height())
        if boton.isVisible():  # lo que se ve (el icono y las letras tienen márgenes propios): se afina para que la tinta quede centrada
            habilitada = self.a_ejecutar.isEnabled()
            self.a_ejecutar.setEnabled(True)
            for on in (False, True):
                self._marcar_play(on)
                img = boton.grab().toImage()
                blancos = [x for x in range(img.width()) if any(min(c.red(), c.green(), c.blue()) > 200 for c in (img.pixelColor(x, y) for y in range(img.height())))]
                if blancos:
                    mover = ((img.width() - 1 - blancos[-1]) - blancos[0]) // 2  # (lo que sobra a la derecha menos lo de la izquierda: hacia la derecha si es positivo)
                    izq, der = self._relleno_play[on]
                    self._relleno_play[on] = (max(0, izq + mover), max(0, der - mover))
            self.a_ejecutar.setEnabled(habilitada)
        self._marcar_play(inicial)

    # -- presentación del estado ----------------------------------------------------------------
    def refrescar(self) -> None:
        if self.a_ejecutar.isChecked() and self._vigilar_motor():
            return
        M, S = self.v.model, self.v.state()
        simulando = self.modo == "simular"  # al editar, el dibujo, el estado y el título son los de la edición
        if simulando:
            label, color = ESTADOS.get(S["status"], (S["status"], "muted"))
            # el estado del motor se dice con las mismas palabras de siempre (estable, en recorrido…), en mayúsculas
            self._poner_chip({"err": "error", "virt": "aviso"}.get(color, "simular"), f"SIMULACIÓN · {label.upper()}",
                             f"Simulación en curso, {label}. Stop detiene y vuelve a editar")
            self.ayuda.setText(M["help"]);self.ayuda.setToolTip(M["help"])
        stable, rec = S["status"] == "pausada-estable", S["status"] == "pausada-recorrido"
        self._diagnostico(S, rec)
        if simulando:
            estado_dibujo = S if "time" in S else {}
            # El reloj y la traza se muestran fuera del dibujo. Los temporizadores,
            # valores, colores e historial gráfico siguen formando parte de la huella.
            huella = {k: v for k, v in estado_dibujo.items()
                      if k not in ("time", "timeUs", "trace", "nextEvent", "nextEventUs")}
            # H5: se compara con lo que la vista tiene dibujado (lo registra `mostrar`, la llame quien la llame), no con lo último que pidió
            # este método: Navegacion.ir o el botón de dependencias también dibujan.
            previo = self.diagrama.dibujado
            if previo is None or previo[0] is not M or previo[1] != huella:
                self.diagrama.mostrar(M, estado_dibujo)
        values = S.get("values", {})
        for var, b in self.botones.items():
            b.setEnabled(stable)
            if var in self.campos:
                if not self.campos[var].hasFocus():
                    self.campos[var].setText(str(values.get(var, "")))
                self.campos[var].setEnabled(stable)
                continue
            on = values.get(var) is True
            b.setChecked(on)
            if on == b.nc:
                b.enclavado = False
            b.indicar(on)
            b.setText(f"{self.nombre(var)} = {1 if on else 0}")
            estilo.poner(b, activa=on)  # relleno y borde de la hoja global; además, el icono (punto) y el «= 1» del texto
            if b.hasFocus() or self._bajo_raton is b:
                self._detalle_del_foco()  # (el «= 1» de la línea de detalle sigue al valor)
        if simulando:
            self._poner_reloj(f"τ = {t_trunc(S['timeUs']) if 'timeUs' in S else '—'}"
                              + (f" · próximo vencimiento: {S['nextEvent']}" if S.get("nextEvent") else ""))
        self._lecturas()
        self._variables(M, S)
        self._traza(S)
        if hasattr(self, "panel_es"):
            valores = dict(S.get("values", {}))
            valores.update({k: x["value"] for k, x in S.get("outputs", {}).items()})
            if self.modbus.activo:
                a = self.modbus.adaptador
                for senal in a.entradas:
                    if senal.variable in self.modbus.muestra:
                        raw = self.modbus.muestra[senal.variable]
                        if senal.formato != "BOOL":
                            from fractions import Fraction
                            raw = raw - 65536 if senal.formato == "INT16" and raw >= 32768 else raw
                            raw = Fraction(raw) / Fraction(senal.escala)
                        valores[senal.variable] = raw
                for senal in (*a.salidas, *getattr(a, "salidas_control", [])):  # en Pausa, las asignadas siguen mostrando su último valor escrito
                    if senal.variable in self.modbus.escritos:
                        raw = self.modbus.escritos[senal.variable]
                        if senal.formato != "BOOL":
                            from fractions import Fraction
                            raw = raw - 65536 if senal.formato == "INT16" and raw >= 32768 else raw
                            raw = Fraction(raw) / Fraction(senal.escala)
                        valores[senal.variable] = raw
                for vid in self.botones:
                    if vid in self.panel_es.indicadores:
                        self.botones[vid].setEnabled(False)
                        if vid in self.campos:
                            self.campos[vid].setEnabled(False)
            self.panel_es.mostrar_valores(valores)

    def _diagnostico(self, S: dict[str, Any], rec: bool) -> None:
        e = html.escape
        if S["status"] == "no-compilable":
            items = "".join(f"<li>{e(amable(sin_codigos(d['message']), d['code']))}<br><i>{e(d.get('correction', ''))}</i></li>"
                            for d in S.get("diagnostics", []))
            self.diag.setText(f"<b>El programa no puede compilarse</b><ul>{items}</ul>Corrija el modelo; no se ejecuta "
                              "nada hasta entonces.")
            self.diag.show()
            return
        ds = [d for d in S.get("diagnostics", []) if S["status"] == "error" or rec][-1:]
        if not ds:
            self.diag.hide()
            return
        d, blk = ds[0], S.get("blocked")
        text = (f"<p>{e(amable(sin_codigos(d['message']), d['code']))}</p>"
                f"<p><i>{e(d.get('correction', ''))}</i></p>")
        if blk:
            text += (f"<p>El recorrido está determinado hasta las etapas {{{e(', '.join(self.nombre(i) for i in blk['reached']))}}}"
                     + (f"; el elemento en cuestión es <b>{e(self.nombre(blk['element']))}</b>" if blk.get("element") else "")
                     + ". Lo que ocurra después depende de una cuestión abierta, así que el lote se rechaza entero.</p>")
        if S["status"] == "error":
            text += ("<p>El motor no aproxima: conserva la última situación estable"
                     + (f" {{{e(', '.join(self.nombre(i) for i in blk['lastStable']))}}}, que <b>no</b> es el resultado del lote" if blk else "")
                     + ". Pulse «Reiniciar» (Ctrl+R) para seguir.</p>")
        else:
            text += "<p>Queda un contexto pendiente: puede completarse evolución a evolución.</p>"
        self.diag.setText(text)
        self.diag.show()

    def _lecturas(self) -> None:
        """Aviso discreto, en la barra de estado, cuando alguna lectura difiere de la decidida por el responsable."""
        changed = [q for q, v in self.options.items() if q in SEMANTIC_OPTIONS and v != SEMANTIC_OPTIONS[q]["default"]]
        self.l_lect.setText("Ajustes de simulación no habituales · " if changed else "")
        self.l_lect.setToolTip("El documento usa ajustes de simulación distintos de los habituales"
                               if changed else "")

    @staticmethod
    def _filas_tablas(M: dict[str, Any], S: dict[str, Any], nombre: Callable[[str], str]) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
        """Las filas de «Salidas y variables» y de «Temporizadores» que da el estado (cada una acaba en el nombre del color de su celda)."""
        outs = S.get("outputs") or {}
        rows = [(nombre(k), "salida continua", "ON" if o["value"] else "OFF", ", ".join(nombre(c) for c in o["contributors"]),
                 "ok" if o["value"] else "muted") for k, o in outs.items()]
        rows += [(nombre(k), "memorizada", str(v), "", "text") for k, v in (S.get("values") or {}).items()
                 if k not in M["inputs"] and k not in outs]
        temp = S.get("temporal") or {}
        filas_t = [(t["where"], t["estado"], t["lleva"], t["preset"],
                    "readout" if t["estado"] == "contando" else "ok" if t["estado"] == "vencido" else "muted") for t in temp.values()]
        return rows, filas_t

    def _clave_tablas(self) -> tuple[Any, ...]:
        """De lo que, además de las filas, depende el aspecto de las tablas: su ancho y su letra (el reparto de columnas y el alto de las filas)."""
        return (self.t_vars.viewport().width(), self.t_temp.viewport().width(), self.t_vars.font().key(), self.t_temp.font().key(),
                self._escala)

    def _variables(self, M: dict[str, Any], S: dict[str, Any]) -> None:
        """Las tablas de Variables y Temporizadores. Si no cambia ninguna fila ni el ancho, no se toca nada; si cambia el texto o el color
        de algunas filas (lo habitual al simular), solo se rehacen esas filas y su alto (todas, si cambian los que contribuyen a una salida); si
        cambian los nombres de la primera columna o el número de filas, la rutina completa (`_variables_completo`, la que vigila ESC-6)."""
        if not self.refresco_conexion.tablas_cambiadas(M, S):
            return
        rows, filas_t = self._filas_tablas(M, S, self.nombre)
        clave, previo = self._clave_tablas(), self._previo_tablas
        mismos_nombres = (previo is not None and previo[2] == clave and len(previo[0]) == len(rows) and len(previo[1]) == len(filas_t)
                          and all(a[0] == b[0] for a, b in zip(previo[0], rows))
                          and all(a[0] == b[0] for a, b in zip(previo[1], filas_t)))
        if not mismos_nombres:
            self._variables_completo(M, S)
        else:
            cambio = False
            for t, ahora, antes, col_color, cifras in ((self.t_vars, rows, previo[0], 2, (2,)), (self.t_temp, filas_t, previo[1], 1, (2, 3))):
                if ahora == antes:
                    continue
                self._filas(t, ahora, col_color, cifras)
                if t is self.t_vars and any(a[3] != b[3] for a, b in zip(ahora, antes))                         and self._del_vars[1].fijar(self._textos_columna(t, 3)):
                    t.resizeRowsToContents()  # (otros nombres que distinguir entre sí: pueden cambiar las líneas de cualquier fila)
                else:
                    for r, (a, b) in enumerate(zip(ahora, antes)):
                        if a != b:
                            t.resizeRowToContents(r)
                self._alto_tabla(t)
                cambio = True
            if cambio:
                self._alto_entradas(tablas=False)
        self._previo_tablas = (rows, filas_t, clave)

    def _variables_completo(self, M: dict[str, Any], S: dict[str, Any]) -> None:
        """La rutina completa de las tablas: lo rehace todo (filas, contextos de nombres, reparto de columnas, alto de filas y de la caja de
        entradas). Es el camino de referencia de la incremental (`_variables`)."""
        rows, filas_t = self._filas_tablas(M, S, self.nombre)
        self._filas(self.t_vars, rows, cifras=(2,))
        self._del_vars[0].fijar(self._textos_columna(self.t_vars, 0))
        self._del_vars[1].fijar(self._textos_columna(self.t_vars, 3))
        self._reparto[0].aplicar()  # (con los nombres de ahora: el reparto busca que quepan en dos líneas)
        self.c_temp.setVisible(bool(S.get("temporal") or {}))
        self._filas(self.t_temp, filas_t, 1, cifras=(2, 3))
        self._del_temp.fijar(self._textos_columna(self.t_temp, 0))
        self._reparto[1].aplicar()
        self.ajustar_tabla(self.t_vars)
        self.ajustar_tabla(self.t_temp)
        self._alto_entradas()

    def _alto_tabla_variables(self) -> None:
        """F10: la tabla de Variables mide, como mucho, lo que deja el panel (menos lo demás de la página): así se desplaza ella y no la
        página (antes, en un cuarto de pantalla, había dos barras verticales una al lado de otra)."""
        pagina, caja, tabla = self._pag_scroll, self._caja_vars, self.variables.tabla
        alto = pagina.height() - 2 * pagina.frameWidth()
        if alto <= 0 or not caja.isVisibleTo(pagina):
            return
        resto = caja.y() + (caja.height() - tabla.height()) + estilo.E2  # (lo de arriba, lo del marco de la caja, el botón y el margen de abajo)
        self.variables.fijar_alto_maximo(alto - resto)

    def _alto_entradas(self, tablas: bool = True) -> None:
        """F2: la caja «Entradas» mide lo que sus botones, salvo que así no dejara ver, bajo ella, al menos cuatro filas (o todas, si hay
        menos) de «Salidas y variables»: entonces se desplaza por dentro, con ese alto máximo."""
        sc = self.sc_entradas
        vista = self.scroll.height() - 2 * self.scroll.frameWidth()  # (sin descontar la barra horizontal, que aparece y desaparece según el alto: oscilaría)
        if vista <= 0 or getattr(self, "_ajustando_entradas", False):
            return
        self._ajustando_entradas = True
        try:
            self._poner_alto_entradas(sc, vista, tablas)
        finally:
            self._ajustando_entradas = False

    def _poner_alto_entradas(self, sc: QScrollArea, vista: int, tablas: bool = True) -> None:
        if tablas:  # (con sus filas al día: el alto de la tabla y el de sus filas han de concordar; quien ya las ajustó lo dice)
            self.ajustar_tabla(self.t_vars)
            self.ajustar_tabla(self.t_temp)
        lay = self.cont_rejilla.layout()
        ancho_ref = self.scroll.width() - 2 * self.scroll.frameWidth()  # (el del panel sin su barra: con ella oscilaría; no se mide el visor)
        natural = max(lay.totalHeightForWidth(max(ancho_ref - 2 * estilo.E1, 60)), lay.sizeHint().height())
        t = self.t_vars
        visibles = min(t.rowCount(), 4)
        de_las_filas = (t.horizontalHeader().height() + sum(t.rowHeight(r) for r in range(visibles)) + 2 * t.frameWidth() + 4) if t.rowCount() else t.height()
        # «lo demás» del panel: el alto de las cajas «Entradas» (sin el desplazable) y «Salidas y variables» (con solo las filas que se han de ver),
        # el aviso de diagnóstico si se ve y los márgenes, calculado a un ancho de referencia (no de la geometría repartida, que llega tarde, ni
        # de lo que pide el diseño con una barra a un lado: las dos hacían oscilar el alto)
        ancho_caja = ancho_ref - 2 * estilo.E1
        entradas, salidas = self._cajas_lado[0], self._cajas_lado[1]

        def alto_caja(caja: QGroupBox) -> int:
            m, lay_caja = caja.contentsMargins(), caja.layout()
            dentro = lay_caja.totalHeightForWidth(ancho_caja - m.left() - m.right()) if lay_caja.hasHeightForWidth() else lay_caja.totalSizeHint().height()
            return m.top() + m.bottom() + dentro
        cajas = [alto_caja(entradas) - sc.height(), alto_caja(salidas) - (t.height() - de_las_filas)]
        if self.diag.isVisibleTo(self):
            cajas.insert(0, self.diag.heightForWidth(ancho_caja))
        resto = sum(cajas) + (len(cajas) - 1) * self.lado.spacing() + 2 * estilo.E1
        tope = max(vista - resto, 3 * estilo.ALTO_CONTROL_COMPACTO)  # (nunca menos de unos tres botones)
        alto = min(natural, tope)
        sc.setFixedHeight(alto)

    @staticmethod
    def _textos_columna(t: QTableWidget, c: int) -> list[str]:
        """Los textos enteros de una columna (los nombres que `DelegadoNombres` ha de poder distinguir)."""
        return [t.item(r, c).text() for r in range(t.rowCount()) if t.item(r, c) is not None]

    @staticmethod
    def _filas(t: QTableWidget, rows: list[tuple[str, ...]], col_color: int = 2, cifras: tuple[int, ...] = ()) -> None:
        """Rellena la tabla (el texto de cada celda es el entero; `cifras` son las columnas que van en la letra técnica)."""
        t.setRowCount(len(rows))
        for i, (*cells, color) in enumerate(rows):
            for j, c in enumerate(cells):
                item = t.item(i, j)
                if item is None:
                    item = QTableWidgetItem(c)
                    if j in cifras:
                        item.setFont(estilo.fuente(estilo.T_CIFRA, mono=True))  # las cifras (valor, tiempo, preset) en la letra técnica
                    item.setData(Qt.ItemDataRole.UserRole, c)
                    item.setToolTip(c)  # el texto entero, aunque la celda lo recorte
                    t.setItem(i, j, item)
                elif item.data(Qt.ItemDataRole.UserRole) != c:
                    item.setText(c)
                    item.setData(Qt.ItemDataRole.UserRole, c)
                    item.setToolTip(c)
                if j == col_color and item.foreground().color() != QColor(COL[color]):
                    item.setForeground(QColor(COL[color]))

    def _traza(self, S: dict[str, Any]) -> None:
        """La traza (los últimos registros, `Vista.state`): al avanzar la ventana de 60 se quitan por arriba los que salen y se añaden por abajo
        los nuevos; si no hay solape con lo que había, se rehace entera (`_traza_completa`)."""
        filas = [(f"{r['time']:>9}   {r['text']}", r["kind"]) for r in S.get("trace", [])]
        previa = self._previa_traza
        if previa is not None and self.traza.count() == len(previa):
            if filas == previa:
                self.traza.scrollToBottom()
                return
            for k in range(1, len(previa)):  # k: cuántos salen por arriba
                if previa[k:] == filas[:len(previa) - k]:
                    for _ in range(k):
                        self.traza.takeItem(0)
                    for fila in filas[len(previa) - k:]:
                        self._poner_fila_traza(*fila)
                    self.traza.scrollToBottom()
                    self._previa_traza = filas
                    return
            if previa and len(filas) >= len(previa) and filas[:len(previa)] == previa:  # solo se añade
                for fila in filas[len(previa):]:
                    self._poner_fila_traza(*fila)
                self.traza.scrollToBottom()
                self._previa_traza = filas
                return
        self._traza_completa(S)
        self._previa_traza = filas

    def _poner_fila_traza(self, texto: str, tipo: str) -> None:
        item = QListWidgetItem(texto)
        if tipo in TRAZA:
            item.setForeground(QColor(COL[TRAZA[tipo]]))
        self.traza.addItem(item)

    def _traza_completa(self, S: dict[str, Any]) -> None:
        """La traza hecha de cero: la referencia de `_traza`."""
        self.traza.clear()
        for r in S.get("trace", []):
            self._poner_fila_traza(f"{r['time']:>9}   {r['text']}", r["kind"])
        self.traza.scrollToBottom()
