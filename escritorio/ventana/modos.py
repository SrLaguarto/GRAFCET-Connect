"""Modos y edición: editar y simular, el puente con la edición y Propiedades, las páginas (E/S y Planos) y las hojas."""
from __future__ import annotations

import html
from .. import estilo
from ..diagrama import COL
from ..edicion import Edicion
from ..mensajes import partir
from ..propiedades import PanelPropiedades
from typing import Any
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QInputDialog, QListWidgetItem, QMessageBox
from .constantes import AYUDA_EDICION, NOMBRE_HERRAMIENTA, TITULO
from .dialogos import DialogoForzado


class Modos:
    """Modos y edición: editar y simular, el puente con la edición y Propiedades, las páginas (E/S y Planos) y las hojas. Sin estado propio: usa los atributos de `Ventana` (la fachada) y llama a los demás métodos a través de `self`."""

    def _abrir_opciones(self, explicito: bool = True) -> None:
        self.flot.abrir(explicito)

    def _props_abiertas(self) -> bool:
        return self.flot.abierto

    @property
    def props(self) -> PanelPropiedades:
        return self.flot.panel_actual()

    def props_activo(self) -> PanelPropiedades:
        return self.props

    def _tras_gesto(self, antes: tuple, despues: tuple) -> None:
        self.flot.tras_gesto(antes, despues)

    def _empezar_edicion(self, e: Edicion) -> None:
        self._ayuda = ""
        self._n_nuevos += 1
        self._proyecto = ("nuevo", self._n_nuevos)
        self._establecer_edicion(e)
        self.cambiar_modo("editar")

    def _establecer_edicion(self, e: Edicion) -> None:
        self.diagrama.scene().reiniciar()
        self.solo_lectura = False
        if self._errores_auto:
            self._marcar_errores(False, False)
        self._variables_es_vistas = {v["id"] for v in e.ed.model["variables"]}
        self._auto_es_pendientes = set()
        self.destino_traer=None;self.aviso_traer.hide()
        self.navegacion.buscar.clear(); self.navegacion.parcial.setCurrentIndex(0); self.navegacion.actual = None
        self.diagrama.seleccion_navegacion.clear()
        self.edicion = e
        e.diagrama = self.diagrama
        e.cambiado.connect(self.refrescar_edicion)
        e.redibujar.connect(self._redibujar_edicion)
        e.realces.connect(self._redibujar_realces)
        # (lo que pide el usuario, con doble clic, Intro o «Editar…», despliega el panel; lo que piden otras operaciones, no: P-IMP-118)
        e.pedir_condicion = lambda tid: self.editar_condicion(tid, e.pedido_explicito)
        e.pedir_etiqueta = lambda ident: self.editar_etiqueta(ident, e.pedido_explicito)
        e.pedir_accion = lambda sid, aid: self.editar_accion(sid, aid, e.pedido_explicito)
        e.tras_gesto = self._tras_gesto
        e.confirmar_borrado = self._confirmar_borrado
        e.pedir_texto = lambda titulo, etiqueta, actual: self._pedir_texto(titulo, etiqueta, actual)
        e.pedir_forzado = lambda datos: self._pedir_forzado(datos)
        if e.enlaces_quitados:
            cantidad, e.enlaces_quitados = e.enlaces_quitados, 0
            aviso = ("Se quitó un enlace en borrador que apuntaba a elementos que ya no existen" if cantidad == 1 else
                     f"Se quitaron {cantidad} enlaces en borrador que apuntaban a elementos que ya no existen")
            e.informar(aviso)
            QMessageBox.information(self, TITULO, aviso)
        if e.barras_limpiadas:
            cantidad, e.barras_limpiadas = e.barras_limpiadas, 0
            aviso = ("Se quitó de una barra la unión con un elemento que ya no existe" if cantidad == 1 else
                     f"Se quitaron de las barras {cantidad} uniones con elementos que ya no existen")
            e.informar(aviso)
            QMessageBox.information(self, TITULO, aviso)

    def cambiar_modo(self, modo: str) -> bool:
        if self.destino_traer:return False
        """Los modos solo se alternan con Play (simular) y Pausa (editar); esto es el mismo control por dentro. Devuelve si
        el programa ha quedado en el modo pedido (Play puede negarse: no compila, inestable…)."""
        on = modo == "simular"
        if self.a_ejecutar.isChecked() != on:
            self.a_ejecutar.setChecked(on)
        else:
            self._ejecutar(on)
        return self.modo == modo

    def _poner_chip(self, modo: str, texto: str, ayuda: str = "") -> None:
        """Actualiza la etiqueta de estado de la fila de pestañas."""
        self.estado.poner(modo, texto, ayuda)
        self._ubica_modo.ajustar()
        self._ajustar_cabecera()

    def _modo_visual(self) -> None:
        """Franja del borde del dibujo y fila de herramientas: verdes al simular, azul tinta al editar (propiedad `modo`)."""
        modo = "simular" if self.modo == "simular" else "editar"
        for w in (getattr(self, "banda_modo", None), getattr(self, "herramientas_grafcet", None),
                  getattr(self, "fila_pestanas", None)):
            if w is not None:
                estilo.poner(w, modo=modo)

    def _fusionar_filas(self, fusionar: bool) -> None:
        """Un cuarto de pantalla: las herramientas (Play, Reiniciar…) suben a la fila de las pestañas para ganar alto."""
        fila = self.herramientas_grafcet
        lay = self.fila_pestanas.layout()
        if fusionar:
            lay.insertWidget(2, fila)
        else:
            self.centralWidget().layout().insertWidget(2, fila)
        fila.layout().setContentsMargins(0 if fusionar else 10, 2 if fusionar else 5, 0 if fusionar else 10, 2 if fusionar else 5)
        fila.layout().setSpacing(estilo.E1 if fusionar else 6)
        for w in (fila, self.fila_pestanas):
            estilo.poner(w, fusion=fusionar)

    def _poner_modo(self) -> None:
        """Alterna las herramientas sin perder tamaños de edición ni el encuadre manual."""
        self.diagrama.dibujado = None  # (otro modo, otro dibujo: lo primero que se pida se dibuja)
        self._ancho_reloj = 0  # el reloj de la barra de estado vuelve a medir lo que su texto (otro modo, otro texto)
        self.l_reloj.setMinimumWidth(0)
        self._modo_visual()
        self._plegar_laterales_compactos()
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        lateral = self._plegables["derecho"]
        ancho = (lateral.width() if lateral.abierto else self._tamanos_paneles["derecho"]) if getattr(self, "_anchos_puestos", False) else self.ancho_derecho
        guardado = getattr(self, "_paneles_edicion", None)
        if not editar and guardado is None:
            self._paneles_edicion = {"inferior": False,
                                    "tamanos": self.vsplit.sizes() if self.isVisible() else None}
        self.variables.setEnabled(editar)
        self._props.setEnabled(editar)
        for accion in (self.a_guardar,self.a_guardar_como,self.a_enviar_lamina,self.a_exportar): accion.setEnabled(not getattr(self,"solo_lectura",False))
        # (con la pestaña de E/S oculta y marcada, Qt elegiría otra al habilitar PLANOS: se vuelve a marcar la de la página que se ve)
        self.pestanas_vistas.blockSignals(True);self.pestanas_vistas.setTabEnabled(1,not getattr(self,"solo_lectura",False))
        self.pestanas_vistas.setCurrentIndex({0:0,1:2,2:1}[self.paginas_es.currentIndex()]);self.pestanas_vistas.blockSignals(False)
        self._acciones_edicion(editar)
        self.a_inferior.setEnabled(self.modo == "simular")
        self.derecho.setCurrentIndex(1 if editar else 0)
        self.inferior.setCurrentIndex(0)
        self._anchos_laterales(ancho)
        if not editar:
            self.diagrama.actualizar_diagnosticos(False)
            self._mostrar_panel("inferior", False, guardar=False)
        elif guardado is not None:
            self._restauracion_paneles = guardado
            self._mostrar_panel("inferior", guardado["inferior"], guardar=False)
            self._paneles_edicion = None
            def restaurar():
                if getattr(self, "_restauracion_paneles", None) is guardado:
                    if self.modo == "editar" and guardado["tamanos"] is not None:
                        self.vsplit.setSizes(guardado["tamanos"])
                    def terminar():
                        if getattr(self, "_restauracion_paneles", None) is guardado:
                            self._restauracion_paneles = None
                    QTimer.singleShot(0, self, terminar)
            if guardado["tamanos"] is not None:
                self.vsplit.setSizes(guardado["tamanos"])
            QTimer.singleShot(0, self, restaurar)
        for n in ("derecho", "inferior"):
            self.visibilidad_paneles.reponer_modo(n, editar, guardado)
        self.diagrama.modo_edicion(editar, self.edicion if editar else None,
                                   conservar=getattr(self, "_encuadre_modo", None) is not None)
        if not editar:
            self.flot.ocultar()
        if editar:
            self.refrescar_edicion()
        elif self.v is not None:
            self._titulo_ventana()
            if getattr(self,"solo_lectura",False): self.refrescar_edicion()

    def _alternar_errores(self, on: bool) -> None:
        """El usuario marca o desmarca «Mostrar errores»: el aviso de la cabecera del dibujo se ve y se actualiza en vivo, o no se ve al editar."""
        self._errores_auto = False
        self.diagrama.diagnosticos_abiertos = on  # (al marcar, la lista sale desplegada; «N errores ▾» la pliega; al desmarcar y volver a marcar, otra vez desplegada)
        self.refrescar_edicion()

    def _marcar_errores(self, on: bool, auto: bool) -> None:
        """Marca o desmarca «Mostrar errores» sin pasar por el gesto del usuario (`auto`: lo hace un Play fallido, y se desmarca solo)."""
        self.b_errores.blockSignals(True)
        self.b_errores.setChecked(on)
        self.b_errores.blockSignals(False)
        self._errores_auto = on and auto

    def _armar_avisos(self, abrir: bool) -> None:
        """Un Play que no simula (errores que lo impiden) o que para por un diagnóstico marca «Mostrar errores» y despliega el aviso con su lista
        (`abrir`); con solo avisos que no bloquean, lo marca y el aviso queda plegado. Si el botón ya lo había marcado el usuario, sigue siendo suyo."""
        if not self.b_errores.isChecked():
            self._marcar_errores(True, True)
        if abrir:
            self.diagrama.diagnosticos_abiertos = True
        if self.modo == "editar":
            self.refrescar_edicion()

    def herramienta(self, h: str) -> None:
        e = self.edicion
        if e is not None and e.herramienta != h:
            e.herramienta, e.enlace, e.mensaje = h, None, ""
            self.refrescar_edicion()
        elif e is not None:
            self.refrescar_edicion()

    def _ayuda_ficha(self, texto: str) -> None:
        """Un clic en una ficha de la paleta: su ayuda, como aviso informativo (no coloca nada)."""
        if self.edicion is not None:
            self.edicion.informar(texto)
            self.edicion.cambiado.emit()

    refrescando = False  # dentro de `refrescar_edicion` (lo mira `GestorFlotantes.colocar`)

    def refrescar_edicion(self) -> None:
        self.refrescando = True
        try:
            self._refrescar_edicion()
        finally:
            self.refrescando = False

    def _refrescar_edicion(self) -> None:
        e = self.edicion
        if e is None or self.modo != "editar":
            return
        diags = e.diagnosticos()
        self._marcas_diagnostico = e.marcados_de(diags) if self.b_errores.isChecked() else set()
        self.diagrama.mostrar(e.M, {}, e.seleccion_dibujo(), self._marcas_diagnostico, e.parpadeo.activos())
        if getattr(self, "solo_lectura", False):
            self._poner_chip("lectura", "EJEMPLO · SOLO LECTURA", "Ejemplo de solo lectura: se puede simular; para editar, abra un proyecto o cree uno nuevo")
        else:
            self._poner_chip("editar", "EDICIÓN", "Modo edición: Simular inicia la simulación")
        self.ayuda.setToolTip(self._ayuda if getattr(self,"solo_lectura",False) else AYUDA_EDICION[e.herramienta])
        mensaje, info = e.texto_estado()
        from ..vigencia_avisos import presentar_estado
        presentar_estado(self, mensaje, info)
        self.l_herr.setText(f"<b>{NOMBRE_HERRAMIENTA[e.herramienta]}</b>: {html.escape(AYUDA_EDICION[e.herramienta])}")
        sel = [e.nombre(i) for i in e.sel]
        self.l_sel.setText(("Selección: " + ", ".join(sel)) if sel else "Nada seleccionado.")
        self._poner_reloj(f"{len(e.M['steps'])} etapas · {len(e.M['transitions'])} transiciones")
        self.a_herr[e.herramienta].setChecked(True)
        self.flot.actualizar()
        self.variables.mostrar(e)
        planos=hasattr(self,"paginas_es") and self.paginas_es.currentIndex()==2
        self.a_deshacer.setEnabled(bool(e.ed.undo_stack))
        self.a_rehacer.setEnabled(bool(e.ed.redo_stack))
        self.a_borrar.setEnabled(bool(e.sel) and not planos and not getattr(self,"solo_lectura",False))
        self._actualizar_portapapeles()
        self.a_debajo.setEnabled(len(e.sel) == 1 and not getattr(self,"solo_lectura",False))
        bloq = [d for d in diags if d["blocks"]]
        self.l_resumen.setText("El grafcet se puede simular." if not bloq else
                               f"No se puede simular: {len(bloq)} error{'es' if len(bloq) != 1 else ''}")
        self.l_resumen.setStyleSheet(f"color: {COL['ok'] if not bloq else COL['err']}")
        self.lista_diag.clear()
        for d in diags:
            nombre = f"{e.nombre(d['target'])}: " if d["target"] else ""
            if d["code"] == "D-TIPO-EVENTO" and d["message"].startswith("Acción por evento"):
                nombre = ""
            if d.get("completo"):
                nombre = ""  # el aviso ya nombra el enlace o la barra: no se repite delante
            mensaje = d["message"] if nombre else d["message"][:1].upper() + d["message"][1:]
            principal, completo = partir(f"{nombre}{mensaje}")
            item = QListWidgetItem(principal)
            item.setData(Qt.ItemDataRole.UserRole, d["target"])
            # El código no va en el texto (P-IMP-89), pero sigue a la vista en la ayuda emergente (REQ-EDT-09).
            referencia = f"Referencia: {d['code']}"
            ayuda = [x for x in (completo, d["correction"], referencia) if x]
            item.setToolTip("\n".join(ayuda))
            item.setForeground(QColor(COL["text"]))  # el rojo queda para lo que impide simular (el resumen)
            self.lista_diag.addItem(item)
        for texto, detalle in self._avisos_ejecucion:  # por qué paró el motor la última vez que se simuló
            item = QListWidgetItem(texto)
            item.setToolTip(detalle)
            item.setForeground(QColor(COL["text"]))
            self.lista_diag.addItem(item)
        hay_detalle = self.lista_diag.count() > 0
        errores, avisos = len(bloq) + (1 if self._avisos_ejecucion else 0), len(diags) - len(bloq)
        partes = [f"{n} {'error' if n == 1 else 'errores'}" for n in (errores,) if n] + [f"{n} {'aviso' if n == 1 else 'avisos'}" for n in (avisos,) if n]
        resumen = " · ".join(([ "Simulación detenida"] if self._avisos_ejecucion else []) + partes)
        if not hay_detalle and self._errores_auto and self.b_errores.isChecked():
            self._marcar_errores(False, False)  # lo marcó un Play fallido y ya no queda nada: se desmarca solo
        if self.b_errores.isChecked():
            self.diagrama.actualizar_diagnosticos(True, resumen if hay_detalle else "", vacio=not hay_detalle)
        else:
            self.diagrama.actualizar_diagnosticos(False)
        self._titulo_ventana()
        if self.destino_traer:self._sincronizar_boton_es()
        if hasattr(self, "panel_es"):  # las variables pueden haber cambiado: el panel de E/S las sigue (o avisa, si hay conexión)
            self._sincronizar_es()
            self._autoasignar_nuevas_es()

    def _redibujar_realces(self) -> None:
        """Un paso del parpadeo: solo cambian los realces naranjas. La escena aplica esa diferencia y no se tocan ni las marcas
        provisionales de un gesto en curso (lazo, imán, anclas…) ni el encuadre."""
        e = self.edicion
        if e is not None and self.modo == "editar":
            self.diagrama.mostrar(e.M, {}, e.seleccion_dibujo(), self._marcas_diagnostico, e.parpadeo.activos(), solo_realces=True)

    def _redibujar_edicion(self) -> None:
        e = self.edicion
        if e is not None and self.modo == "editar":
            # un arrastre no valida de nuevo; el parpadeo sí repinta lo marcado por los diagnósticos
            self.diagrama.mostrar(e.M, {}, e.seleccion_dibujo(), self._marcas_diagnostico, e.parpadeo.activos())

    def _ir_a_diagnostico(self, item: QListWidgetItem) -> None:
        """Un clic en un diagnóstico selecciona el elemento y lo centra (REQ-EDT-09)."""
        e, target = self.edicion, item.data(Qt.ItemDataRole.UserRole)
        if e is not None and target:
            e.seleccionar([target])
            c = e.centro(target)
            if c is not None:
                self.diagrama.centrar_en(c)
            e.parpadear([target], centrar=False)  # ya está centrado

    def editar_condicion(self, tid: str, explicito: bool = True) -> None:
        """Doble clic en una transición: la selecciona y despliega el panel inferior con su receptividad (solo si lo pide el
        usuario: con `explicito` falso, un panel plegado se queda plegado)."""
        self.edicion.seleccionar([tid])
        self._abrir_opciones(explicito)

    def editar_accion(self, sid: str | None, aid: str | None = None, explicito: bool = True) -> None:
        """Doble clic en una acción, «Editar…» o una acción recién unida a una etapa: la selecciona y despliega el panel inferior
        con sus opciones (tipo, variable, valor, condición o evento: todo se aplica al momento). Sin `aid`, añade una acción
        nueva a la etapa."""
        e = self.edicion
        if aid is None:
            if sid:
                e.anadir_accion(sid)
            return
        seleccion = [sid] if sid else (e.sel if aid in e.sel else [aid])
        if (e.accion, e.ver_accion, e.sel) != (aid, True, seleccion):
            e.accion, e.ver_accion, e.sel = aid, True, seleccion
            e.cambiado.emit()
        self._abrir_opciones(explicito)

    def editar_etiqueta(self, ident: str, explicito: bool = True) -> None:
        """Doble clic en una etapa: despliega las opciones y lleva el cursor a su etiqueta."""
        self.edicion.seleccionar([ident])
        self._abrir_opciones(explicito)
        if self._props_abiertas():
            self.props_activo().s_etiqueta.setFocus()
            self.props_activo().s_etiqueta.selectAll()

    def _pedir_texto(self, titulo: str, etiqueta: str, actual: str) -> str | None:
        """Un nombre que pide la edición («Añadir recinto…», «Renombrar…» de una macroetapa): el texto escrito, o None si se
        cancela. Es un método propio para poder sustituirlo en las pruebas, sin bloquear con el diálogo."""
        texto, ok = QInputDialog.getText(self, titulo, etiqueta, text=actual)
        return texto if ok else None

    def _pedir_forzado(self, datos: dict[str, Any]) -> dict[str, Any] | None:
        """La orden de forzado que pide la edición («Forzar un parcial…», «Editar orden de forzado…»): lo elegido en
        `DialogoForzado`, o None si se cancela. Método propio para poder sustituirlo en las pruebas, sin bloquear."""
        d = DialogoForzado(self, datos)
        return d.resultado() if d.exec() == QDialog.DialogCode.Accepted else None

    def _confirmar_borrado(self, plan: dict[str, list[str]]) -> bool:
        e = self.edicion
        n = e.nombres
        elegidos = list(dict.fromkeys(e.nombre(i) for i in e.sel))  # con nombres, sin repetir (una macroetapa y su expansión)
        extra = [t for t in dict.fromkeys(e.nombre(i) for i in plan["elements"] if i not in e.sel) if t not in elegidos]
        texto = f"Se borrará: {', '.join(elegidos)}."
        if extra:
            texto += f"\n\nTambién se lleva consigo: {', '.join(extra)}."
        if plan["affectedTransitions"]:
            texto += f"\n\nQuedan sin enlace en este extremo: {', '.join(n.get(i, i) for i in plan['affectedTransitions'])}."
        avisos = e.avisos_borrado(plan)  # recintos y órdenes que pierden etapas de su enlace de activación o de su conjunto
        if avisos:
            texto += "\n\nTambién cambia la jerarquía:\n" + "\n".join(f"• {a[0].upper()}{a[1:]}." for a in avisos)
        return QMessageBox.question(self, TITULO, texto + "\n\nSe puede deshacer con Ctrl+Z. ¿Continuar?") \
            == QMessageBox.StandardButton.Yes

    def _mostrar_pagina(self, es: bool | str, refrescar_planos=True) -> None:
        """Cambio centralizado entre GRAFCET (0), E/S (1) y Planos (2)."""
        destino=2 if es=="planos" else (1 if es else 0)
        if destino==2 and getattr(self,"solo_lectura",False): return
        anterior = self.paginas_es.currentIndex()
        if anterior == 0 and destino != 0 and self._plegables["derecho"].abierto:
            self._tamanos_paneles["derecho"] = self._plegables["derecho"].width()
        if self.paginas_es.currentIndex()==2 and destino!=2:self.panel_planos.aplicar()
        if destino == 1:
            self._escala_es()
        if destino==2:
            self._escala_planos()
        if destino==2 and refrescar_planos:
            self.panel_planos.mostrar()
            self.panel_planos.parpadear_boton_hoja()
        self.paginas_es.setCurrentIndex(destino)
        if destino == 0 and anterior != 0:
            # El contenido oculto conserva geometrías viejas al cambiar de pantalla.
            # Restaurar el ancho del panel, o solo su pestaña si está plegado.
            self._anchos_laterales(self._tamanos_paneles["derecho"])
        self._sincronizar_boton_es()
        if destino == 0 and anterior != 0 and self.modo == "simular" and self.v is not None:
            self.refrescar()  # El dibujo se actualiza al volver, antes del siguiente sondeo.

    def _alternar_planos(self,on):
        self._mostrar_pagina("planos" if on else False)

    def _seleccion_para_hoja(self,activo):
        if activo:
            self._poner_chip("aviso", "SELECCIONANDO · para Planos", "Seleccionando elementos para añadirlos a una hoja de PLANOS")
            self.ayuda.setText('Clic: cadena completa · Mayús+clic: añadir otra cadena · Ctrl+clic: añadir o quitar un elemento. Sin jerarquías inferiores automáticas.')
        if activo==getattr(self,'_seleccionando_hoja',False):return
        self._seleccionando_hoja=activo
        if activo:
            from ..hojas import SeleccionParaHoja
            self._paneles_traer={n:p.abierto for n,p in self._plegables.items()}
            self._tamanos_traer = (self.split.sizes(), self.vsplit.sizes())
            for n in self._paneles_traer:
                self._plegables[n].hide();self.flechas[n].hide();self.pestanas[n].hide()
            self.diagrama.controlador=SeleccionParaHoja(self.edicion);self.diagrama.setAcceptDrops(False)
            self._estilo_traer=self.diagrama.styleSheet();self.diagrama.setStyleSheet(self._estilo_traer+' QGraphicsView {border:2px solid '+estilo.AVISO_BORDE+'; background:'+estilo.AVISO_FONDO+';}')
            self._poner_chip("aviso", "SELECCIONANDO · para Planos", "Seleccionando elementos para añadirlos a una hoja de PLANOS")
            self.ayuda.setText('Clic: cadena completa · Mayús+clic: añadir otra cadena · Ctrl+clic: añadir o quitar un elemento. Sin jerarquías inferiores automáticas.')
        else:
            self.diagrama.controlador=self.edicion if self.modo=='editar' else None;self.diagrama.setAcceptDrops(self.modo=='editar' and not getattr(self,'solo_lectura',False));self.diagrama.setStyleSheet(getattr(self,'_estilo_traer',''))
            for n,visible in getattr(self,'_paneles_traer',{}).items():
                self._mostrar_panel(n,visible,guardar=False);self.flechas[n].setVisible(visible)
            for divisor, tamanos in zip((self.split, self.vsplit), self._tamanos_traer):
                divisor.setSizes(tamanos)
            if self.modo=='editar':self.refrescar_edicion()

    def preparar_traer(self,ident):
        if not ident or not self.edicion:return
        self.panel_planos.aplicar();self.destino_traer=(self.edicion,ident);self._mostrar_pagina(False)
        self.diagrama.setFocus()

    def cancelar_traer(self):
        self.destino_traer=None;self.aviso_traer.hide();self._mostrar_pagina('planos')

    def confirmar_traer(self):
        if not self.destino_traer or self.destino_traer[0] is not self.edicion:
            self.destino_traer=None;self.aviso_traer.hide();return
        e,ident=self.destino_traer
        if not e.sel:
            QMessageBox.information(self,'Traer GRAFCET','Selecciona los elementos que quieres añadir.');return
        try:
            self.panel_planos.mostrar(ident);self.panel_planos.insertar(e.copiar_fragmento().selected)
        except (ValueError,RuntimeError) as exc:QMessageBox.warning(self,'Traer GRAFCET',str(exc));return
        self.destino_traer=None;self.aviso_traer.hide();self.mostrar_hoja(ident)

    def historial_plano(self,rehacer=False):
        e=self.edicion
        if e is None:return
        plano=self.paginas_es.currentIndex()==2
        if plano:
            p=self.panel_planos;p.aplicar()
            p.liberar_editor()
        (e.rehacer if rehacer else e.deshacer)()
        if plano:self.panel_planos.mostrar()

    def enviar_seleccion_lamina(self):
        e=self.edicion
        if e is None or self.modo!='editar' or not e.sel:return
        self.panel_planos.aplicar()
        from ..hojas import CrearHoja
        d=CrearHoja(e,self)
        try:
            if not d.exec():return
            ident=d.destino.currentData()
            if ident is None:
                from ..hojas import dibujo_vinculado
                from ..planos_controles import comprobar_cabe
                cfg = d.configuracion or d.valores()
                comprobar_cabe(dibujo_vinculado(e, e.copiar_fragmento().selected), cfg)
                ident=e.ed.add_plan_page(None,d.configuracion or d.valores(),d.nombre.text().strip() or None)
            e.cambia();self.panel_planos.mostrar(ident);self.panel_planos.insertar(e.copiar_fragmento().selected);self.mostrar_hoja(ident)
        except (OSError,ValueError,RuntimeError) as exc:QMessageBox.warning(self,'Enviar a plano',str(exc))
        finally:d.deleteLater()

    def mostrar_hoja(self,ident):
        self.panel_planos.mostrar(ident)
        self._mostrar_pagina("planos",False)

    def abrir_laminas(self, accion="previa") -> None:
        if getattr(self,"solo_lectura",False):
            if accion=="imprimir":
                from ..laminas import DocumentoLaminas
                doc=DocumentoLaminas(self.edicion.M,self.v.state() if self.modo=="simular" else {},self.edicion.ed.sheet_settings(),self.diagrama.dependencias)
                doc.imprimir(self)
            return
        if accion in ("exportar","imprimir") and self.paginas_es.currentIndex()==2 and self.panel_planos.editor:
            self.panel_planos.aplicar()
        else:
            self.panel_planos.mostrar();self._mostrar_pagina("planos",False)
        editor=self.panel_planos.editor
        if editor and accion in ("exportar","imprimir"):getattr(editor,accion)()
