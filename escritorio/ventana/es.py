"""Entradas y salidas: Modbus, conexión directa, el panel de E/S, sus preferencias recordadas y el refresco de la conexión."""
from __future__ import annotations

import copy
import json
from .. import estilo
from ..entradas_salidas import CONEXION_INICIAL
from pathlib import Path
from typing import Any
from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileDialog
from conexion.configuracion import ARCHIVO, CANALES_INICIALES, Configuracion, aviso_host, normalizar_host
from .constantes import ERRORES, TICK_MS


class ConexionES:
    """Entradas y salidas: Modbus, conexión directa, el panel de E/S, sus preferencias recordadas y el refresco de la conexión. Sin estado propio: usa los atributos de `Ventana` (la fachada) y llama a los demás métodos a través de `self`."""

    def _escala_es(self) -> None:
        """La vista de E/S lleva la escala de ahora (hoja, letra y alto de fila). Se hace al mostrarla: son más de mil widgets."""
        if self._es_pendiente:
            self._es_pendiente = False
            self.panel_es.escalar(self._hoja_escala, self._escala)

    def _refrescar_modbus(self):
        self.refresco_conexion.actualizar()

    def _despertar_ciclo(self) -> None:
        """Lo llama el trabajador de red (otro hilo) al terminar una petición: despierta al hilo de control, que atiende la respuesta ya."""
        self.ciclo.despertar()

    def _error_ciclo(self, exc: BaseException) -> None:
        """Lo llama el hilo de control (sin Qt) si un ciclo lanza una excepción: la conexión pasa a error, como un fallo de red, y se avisa a la pantalla."""
        with self.candado:
            m = self.modbus
            m.estado, m.mensaje = "error", m._mensaje_de_error(exc, "")
            m.en_marcha = m.reiniciando = False
            m._cero_al_cerrar = None
            if m.cliente is not None:
                m.cliente.cerrar()
        self._respuesta_modbus.notificar()

    def _raiz_modbus(self):
        if (self.modo == "editar" or self.fuente.get("tipo") == "editor") and self.edicion:
            return self.edicion.ruta
        return self.fuente.get("raiz")

    def _persistir_mapa_modbus(self, config):
        if self.modbus.activo:
            with self.candado:
                self.modbus.reasignar(config,self.panel_es.doc)
        raiz = self._raiz_modbus()
        if raiz and self.panel_es.doc:
            try:
                config.guardar(raiz / ARCHIVO, self.panel_es.doc)
                if self.edicion and getattr(self.edicion,"contenedor",None):
                    self.edicion.ed.dirty=True;self._titulo_ventana()
            except (OSError, ValueError) as exc:
                self.panel_es.estado.setText(f"No se pudo guardar el mapa: {exc}")

    def _cargar_config_modbus(self, doc: dict[str, Any] | None = None) -> None:
        self.panel_es.directa.establecer_edicion(self.edicion)
        doc = doc or self.v.doc
        raiz = self._raiz_modbus()
        config, avisos = None, []
        origen = "Última configuración utilizada" if self.ajustes.contains("modbus/configuracion") or self.ajustes.contains("modbus/host") else "Configuración inicial del servidor"
        fallo = None
        # Recargar el mismo proyecto conserva el mapa en memoria; cambiar de proyecto exige un mapa propio.
        anterior = self.panel_es.config
        cambio = self._proyecto != self._proyecto_modbus
        self._proyecto_modbus = self._proyecto
        if not cambio and anterior.modelo == doc["id"]:
            config = anterior
            origen = "Configuración de este proyecto en memoria"
        elif raiz and (raiz / ARCHIVO).exists():
            try:
                origen = "Configuración guardada en el proyecto"
                config = Configuracion.cargar(raiz / ARCHIVO, doc, avisos)  # lo que ya no casa se descarta; el resto se conserva
            except (ValueError, OSError) as exc:
                fallo = f"No se pudo cargar el mapa: {exc}"
        from ..conexion_directa import configuracion_inicial
        if config is None and self._proyecto[0] == "nuevo":
            config = configuracion_inicial(self._proyecto, doc, self._parametros_recordados["canales"])
        from ..conexion_ventana import preparar_carga
        preparar_carga(self, config)
        with self.candado:
            vivo = self.modbus.activo and self.modbus.estado != "cerrando" and self.modbus.cliente is not None
            datos_cliente = (self.modbus.cliente.host, self.modbus.cliente.puerto, self.modbus.cliente.unidad) if vivo else None
        if datos_cliente is not None:
            config = copy.deepcopy(config or configuracion_inicial(
                self._proyecto, doc, self._parametros_recordados["canales"]))
            config.host, config.puerto, config.unidad = datos_cliente
        self.panel_es.cargar(doc, config, avisos)
        self.panel_es.host.setToolTip(f"{origen}. Copia la dirección que muestra el software del servidor Modbus.")
        if fallo:
            self.panel_es.mostrar_estado("error", fallo)
        if self.modbus.activo and self.modbus.estado != "cerrando" and cambio:
            self._cambiar_modelo_modbus(doc)

    def _cambiar_modelo_modbus(self, doc: dict[str, Any]) -> None:
        """Otro modelo con la conexión viva: TCP se conserva, pero lo que el modelo anterior hubiera escrito ya no lo controla
        nadie (cero) y la lectura sigue con el mapa del modelo nuevo, cuyas salidas asignadas también se ponen a cero (el
        coordinador junta los dos ceros en uno)."""
        with self.candado:
            anterior = self.modbus.adaptador  # no depende de lo ya confirmado: una escritura en vuelo puede haber llegado a la planta
            if anterior is not None and (anterior.salidas or getattr(anterior, "salidas_control", [])):
                self.modbus.pausar(diagnostico=True)
            try:
                self.modbus.observar(self.panel_es.config, doc)
            except ERRORES as exc:
                self.modbus.mensaje = f"Conectado · el mapa de este modelo no es válido: {exc}"

    def _guardar_config_modbus(self):
        try:
            config = self.panel_es.obtener()
            raiz = self._raiz_modbus()
            if raiz:
                ruta = raiz / ARCHIVO
            else:
                nombre, _ = QFileDialog.getSaveFileName(self, "Guardar configuración Modbus", ARCHIVO, "JSON (*.json)")
                if not nombre:
                    return
                ruta = Path(nombre)
            config.guardar(ruta, self.panel_es.doc)
            self.panel_es.config = config
            self.panel_es.estado.setText(f"Configuración guardada: {ruta}")
        except (ValueError, OSError) as exc:
            self.panel_es.estado.setText(f"No se pudo guardar: {exc}")

    def _abrir_config_modbus(self):
        nombre, _ = QFileDialog.getOpenFileName(self, "Cargar configuración Modbus", "", "JSON (*.json)")
        if nombre:
            try:
                avisos = []
                config = Configuracion.cargar(Path(nombre), self.panel_es.doc, avisos)
                self.panel_es.cargar(self.panel_es.doc, config, avisos)
                self.panel_es.estado.setText("Mapa cargado · desconectado")
            except (ValueError, OSError) as exc:
                self.panel_es.estado.setText(f"No se pudo cargar: {exc}")

    def _leer_conexion_recordada(self) -> tuple[str, int, int]:
        """El último (host, puerto, esclavo) con el que se conectó o se probó con éxito; la primera vez, la configuración inicial."""
        a = self.ajustes
        crudo = a.value("modbus/host", CONEXION_INICIAL[0])
        self._aviso_host_recordado = aviso_host(crudo)  # lo que no es IP no se cambia en silencio: el panel avisa
        host = normalizar_host(crudo)  # «localhost» pasa a 127.0.0.1; lo que no es IPv4, a la inicial (sin guardarlo todavía)
        puerto, unidad = a.value("modbus/puerto", CONEXION_INICIAL[1], type=int), a.value("modbus/unidad", CONEXION_INICIAL[2], type=int)
        if not host or not 1 <= puerto <= 65535 or not 0 <= unidad <= 255:  # un valor roto no debe dejar sin conexión propuesta
            return CONEXION_INICIAL
        return host, puerto, unidad

    def _leer_parametros_recordados(self) -> dict[str, Any]:
        host, puerto, unidad = self._leer_conexion_recordada()
        base = {"host": host, "puerto": puerto, "unidad": unidad, "periodo_ms": 20, "timeout_ms": 500,
                "canales": copy.deepcopy(CANALES_INICIALES), "escalas": {}}
        try:
            texto = self.ajustes.value("modbus/configuracion", "")
            if texto:
                datos = json.loads(str(texto))
                if not isinstance(datos, dict):
                    raise ValueError("preferencias inválidas")
                # las cantidades de canales no se heredan: una versión anterior guardó aquí 16/8 y las imponía
                propuesta = {**base, **{k: datos[k] for k in base if k in datos and k != "canales"}}
                c = Configuracion(**{k: v for k, v in propuesta.items() if k != "escalas"})
                c.validar({"id": "", "variables": []})
                if not isinstance(propuesta["escalas"], dict):
                    raise ValueError("escalas inválidas")
                from fractions import Fraction
                for clave, escala in propuesta["escalas"].items():
                    area, numero = clave.split(":")
                    if area not in CANALES_INICIALES or not 0 <= int(numero) <= 65535 or Fraction(str(escala)) <= 0:
                        raise ValueError("escala inválida")
                return propuesta
        except (ValueError, TypeError, ZeroDivisionError, AttributeError):
            pass
        return base

    def _recordar_parametros(self, config: Configuracion) -> None:
        if config.modo == "directo":
            return
        datos = {k: getattr(config, k) for k in ("host", "puerto", "unidad", "periodo_ms", "timeout_ms")}
        datos["canales"] = copy.deepcopy(CANALES_INICIALES)  # (siempre las iniciales: las del proyecto van en su mapa)
        datos["escalas"] = dict(self.panel_es.escalas_base)
        datos["escalas"].update({f"{s.area}:{s.direccion}": s.escala for s in config.senales})
        texto = json.dumps(datos, ensure_ascii=False, sort_keys=True)
        if self.ajustes.value("modbus/configuracion", "") != texto:
            self.ajustes.setValue("modbus/configuracion", texto)
            for clave in ("host", "puerto", "unidad"):
                self.ajustes.setValue(f"modbus/{clave}", datos[clave])
            self.ajustes.sync()
        self._parametros_recordados = datos
        self._conexion_recordada = tuple(datos[k] for k in ("host", "puerto", "unidad"))
        self.panel_es.conexion_defecto = self._conexion_recordada
        self.panel_es.aviso_host_defecto = ""  # (ya se guardó una IP, con éxito)
        self.panel_es.parametros_defecto = copy.deepcopy(datos)

    def _recordar_conexion(self) -> None:
        """Recuerda parámetros completos tras una conexión o prueba con éxito, nunca las asignaciones de otro proyecto."""
        m = self.modbus
        if m.cliente is None or not (m.estado == "conectado" or (m.estado == "desconectado" and m.mensaje.startswith("Conexión probada"))):
            return
        config = copy.deepcopy(self.panel_es.config)
        config.host, config.puerto, config.unidad = m.cliente.host, m.cliente.puerto, m.cliente.unidad
        self._recordar_parametros(config)

    def _doc_es(self) -> dict[str, Any] | None:
        """El modelo cuyas variables enseña el panel de E/S: el que se edita; al simular, el que se está ejecutando."""
        if self.modo == "editar" and self.edicion:
            return self.edicion.ed.model
        return self.v.doc if self.v else None

    def _autoasignar_nuevas_es(self):
        e=self.edicion
        if e is None or getattr(self,'solo_lectura',False):return
        doc=e.ed.model; actuales={v['id'] for v in doc['variables']}
        previos=getattr(self,'_variables_es_vistas',actuales)
        self._auto_es_pendientes.update(actuales-previos);self._variables_es_vistas=actuales
        self._auto_es_pendientes.intersection_update(actuales)
        if not self._auto_es_pendientes:return
        if self._proyecto_modbus!=self._proyecto:self._cargar_config_modbus(doc)
        else:self.panel_es.actualizar(doc)
        faltan=self.panel_es.autoasignar(self._auto_es_pendientes)
        self._auto_es_pendientes.clear()
        if faltan:self.statusBar().showMessage('Sin canal Modbus libre: '+', '.join(faltan),12000)

    def _sincronizar_es(self, mostrando: bool = False) -> None:
        """Deja las listas y los canales del panel de E/S con las variables actuales del modelo, conservando el mapa y la
        configuración (la IP incluida); lo que ya no casa se quita con aviso. Con la conexión viva no se toca: el mapa en
        uso no cambia a mitad de sesión y solo se marca que hay variables nuevas pendientes de ver al desconectar. Al
        mostrar el panel (`mostrando`) también se cambia de mapa si el proyecto es otro; en cualquier otro momento, solo
        si el panel se ve y sigue siendo el mismo proyecto (cambiar de proyecto lo hace `_cargar_config_modbus`)."""
        doc, p = self._doc_es(), self.panel_es
        if doc is None:
            return
        mismo = self._proyecto == self._proyecto_modbus and p.config.modelo == doc["id"]
        if not mostrando and not mismo:
            return
        if mismo:
            cambio=p.firma(doc)!=p.firma_modelo
            p.actualizar(doc)
            if cambio and self.modbus.activo:
                with self.candado:
                    self.modbus.reasignar(p.config,doc)
        else:
            self._cargar_config_modbus(doc)
        self._autoasignar_nuevas_es()

    def mostrar_es(self):
        self._escala_es()
        self._sincronizar_es(mostrando=True)
        self._mostrar_pagina(True)

    def _alternar_es(self, on: bool) -> None:
        """El botón conmutador: marcado abre la vista de E/S; desmarcado vuelve al dibujo GRAFCET."""
        if on:
            self.mostrar_es()
        else:
            self._mostrar_pagina(False)

    def _sincronizar_boton_es(self, _indice: int = 0) -> None:
        """Deja el botón con el aspecto de la página que se ve (también si la página la cambió otra vía: la flecha ← del
        panel, la prueba guiada…): «E/S externas» en el dibujo GRAFCET; «Vista GRAFCET», pulsado, en la vista de E/S."""
        es = self.paginas_es.currentIndex() == 1
        self.a_es.blockSignals(True)
        self.a_es.setChecked(es)
        self.a_es.blockSignals(False)
        self._aspecto_boton_es(es)
        indice=self.paginas_es.currentIndex()
        pendiente = False
        if hasattr(self,'pestanas_vistas'):
            self.pestanas_vistas.blockSignals(True);self.pestanas_vistas.setCurrentIndex({0:0,1:2,2:1}[indice]);self.pestanas_vistas.blockSignals(False)
            self.luz_es.setProperty("abierta",indice==1);self.luz_es.style().unpolish(self.luz_es);self.luz_es.style().polish(self.luz_es)  # activa mientras se ve E/S
            pendiente=self.destino_traer is not None and self.destino_traer[0] is self.edicion
            self.aviso_traer.setVisible(indice==0 and pendiente)
        if hasattr(self,"herramientas_grafcet"):self.herramientas_grafcet.setVisible(indice==0 and not pendiente)
        planos=self.paginas_es.currentIndex()==2
        self.a_planos.blockSignals(True);self.a_planos.setChecked(planos);self.a_planos.blockSignals(False)
        self.a_planos.setToolTip("Volver al GRAFCET" if planos else "Editar planos, plantillas y cajetín")
        self.a_ejecutar.setEnabled(not(es or planos or pendiente));self.a_reiniciar.setEnabled(not(es or planos or pendiente))
        editar=self.modo=="editar" and not planos and not pendiente and not getattr(self,"solo_lectura",False)
        for a in (*self.a_herr.values(),self.a_debajo,*getattr(self,"_a_errores",()),self.a_girar_izq,self.a_girar_der):a.setEnabled(editar)
        e=self.edicion
        self.a_deshacer.setEnabled(not pendiente and (editar or planos) and e is not None and bool(e.ed.undo_stack));self.a_rehacer.setEnabled(not pendiente and (editar or planos) and e is not None and bool(e.ed.redo_stack));self.a_borrar.setEnabled(editar and e is not None and bool(e.sel))
        self.a_dependencias.setEnabled(not planos) if hasattr(self,"a_dependencias") else None
        self._actualizar_portapapeles()
        self._seleccion_para_hoja(indice==0 and pendiente)

    def _aspecto_boton_es(self, es: bool) -> None:
        """Texto, tooltip e icono del botón conmutador en cada una de sus dos vistas."""
        self.a_es.setText("Vista GRAFCET" if es else "E/S externas")
        self.a_es.setToolTip("Volver al dibujo GRAFCET" if es else
                             "Conectar sensores y actuadores · se vuelve con este mismo botón o desde las pestañas superiores")
        self.a_es.setIcon(self._iconos_es[1 if es else 0])

    def _fijar_ancho_boton_es(self) -> None:
        """El botón mide siempre lo del más ancho de sus dos estados (texto e icono): al alternar entre «E/S externas» y «Vista
        GRAFCET» no se mueve nada más de la barra."""
        boton = self.tb_conexion.widgetForAction(self.a_es)
        anchos = []
        for es in (False, True):
            self._aspecto_boton_es(es)
            anchos.append(boton.sizeHint().width())
        self._aspecto_boton_es(self.paginas_es.currentIndex() == 1)
        boton.setFixedWidth(max(anchos))

    def _conectar_modbus(self, prueba=False):
        try:
            config = self.panel_es.obtener()
        except (ValueError, RuntimeError) as exc:
            self.panel_es.estado.setText(f"No se pudo conectar: {exc}")
            return
        self._iniciar_conexion_modbus(config, None, prueba)

    def _iniciar_conexion_modbus(self, config, sesion, prueba):
        en_play = self.a_ejecutar.isChecked() and not prueba  # P-IMP-172: al conectar en Play, se vuelve a Play
        try:
            self._parar_sin_cambiar_vista()
            with self.candado:
                self.modbus.iniciar(config, sesion, prueba, documento=self.panel_es.doc)
            self.ciclo.arrancar()  # el hilo de control lleva el ciclo mientras haya conexión
            self.panel_es.config = config
            self.panel_es._dibujar()
            self.panel_es.ocupado(True)
            self.panel_es.estado.setText(self.modbus.mensaje)
            self.rt.setInterval(TICK_MS)  # el reloj de la pantalla ya no marca el periodo de la conexión: solo atiende las novedades y refresca
            self._iniciar_reloj()
            self.rt.start()
        except (ValueError, RuntimeError) as exc:
            self.panel_es.estado.setText(f"No se pudo conectar: {exc}")
            return
        if en_play:  # conecta en Pausa (P-IMP-60, con su cero) y, ya conectado, Play de nuevo desde las etapas iniciales
            self._replay_intentos = 100
            QTimer.singleShot(50, self, self._replay_tras_conectar)

    def _replay_tras_conectar(self):
        estado = getattr(self.modbus, "estado", "")
        if estado == "conectado":
            if not self.a_ejecutar.isChecked():
                anterior = getattr(self, "_conservar_vista_al_parar", False)
                self._conservar_vista_al_parar = True
                try:self.a_ejecutar.setChecked(True)
                finally:self._conservar_vista_al_parar = anterior
            return
        self._replay_intentos -= 1
        if self._replay_intentos > 0 and self.modbus.activo and estado != "error":
            QTimer.singleShot(50, self, self._replay_tras_conectar)

    def _parar_sin_cambiar_vista(self):
        anterior=getattr(self,"_conservar_vista_al_parar",False)
        self._conservar_vista_al_parar=True
        try:self.a_ejecutar.setChecked(False)
        finally:self._conservar_vista_al_parar=anterior

    def _desconectar_modbus(self):
        # Con el candado todo el rato (única orden que lo retiene durante un refresco): Stop y Desconectar son una sola orden del usuario y el hilo de
        # control no puede meter entre las dos un fallo de red que la deje en «error» en vez de «desconectado».
        with self.candado:
            anterior = getattr(self, "_conservar_vista_al_parar", False)
            self._conservar_vista_al_parar = True
            try:
                self.a_ejecutar.setChecked(False)
            finally:
                self._conservar_vista_al_parar = anterior
                self._sincronizar_boton_es()
            self.modbus.desconectar()
        self.ciclo.despertar()
        self.panel_es.estado.setText(self.modbus.mensaje)
        self.rt.start()

    # -- indicador de la conexión externa -------------------------------------------------------
    def _luz_es(self, estado: str, mensaje: str = "") -> None:
        """Punto de color y texto breve en la barra de simulación: verde conectada, gris desconectada, rojo error."""
        self._ultima_luz = (estado, mensaje)
        texto = {"conectado": "conectada", "error": "error", "diagnostico": "error"}.get(estado, "desconectada")
        # la luz no depende solo del color: círculo con marca (conectada), círculo vacío (desconectada) o rombo con «!» (error)
        self.luz_es.setIcon(QIcon(estilo.forma_luz(texto)))
        self.luz_es.setIconSize(QSize(12, 12))
        etiqueta = "E/S" if getattr(self, "_muy_estrecho", False) else "E/S externas"
        self.luz_es.setText(f"{etiqueta}: error" if texto == "error" else etiqueta)
        self.luz_es.setToolTip((mensaje + "\n" if mensaje else "") + f"E/S externas: {texto} · clic para abrir")
        self.luz_es.setAccessibleName(f"E/S externas: {texto}")
        estilo.poner(self.luz_es, estadoLuz=texto)
        if hasattr(self, "_ubica_modo"):
            self._ubica_modo.ajustar()
