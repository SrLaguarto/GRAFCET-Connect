"""Un trabajador de red; tick() y el motor pertenecen al hilo llamador.

No crea relojes ni ejecuta el motor desde el trabajador. La reconexión es manual.
"""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from .adaptador import Adaptador, MonitorEntradas, escribir_salidas, leer_entradas
from .modbus import ClienteModbus


class Coordinador:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="modbus")
        self.futuro = None
        self.estado = "desconectado"
        self.mensaje = "Desconectado"
        self.fase = ""
        self.adaptador = None
        self.cliente = None
        self.muestra = {}
        self.escritos = {}
        self.fallo_motor = False
        self.cero_pendiente = False
        self.proxima = 0
        self.en_marcha = False
        self._ejecutar = False
        self._descartar_lectura = False
        self._generacion = 0
        self.reiniciando = False
        self._cerrado = False
        self._observar_despues = False
        self._salidas_seguras = None

    def solicitar_ejecucion(self, ejecutar):
        if ejecutar:
            self._observar_despues = False  # la intención más reciente (Play) manda sobre un Reiniciar en Pausa
        if ejecutar != self._ejecutar:
            self.en_marcha = False
            if self.estado == "conectado":
                self.mensaje = ("Conectado · leyendo sensores antes de ejecutar…" if ejecutar else
                                "Conectado · Pausa · estado y salidas conservados")
            # Una lectura enviada antes de Ejecutar no sirve para reanudar.
            self._descartar_lectura = ejecutar and self.futuro is not None and self.fase == "leer"
            self._ejecutar = ejecutar

    @property
    def activo(self):
        return self.estado in ("conectando", "conectado", "diagnostico", "cerrando", "probando")

    def _enviar(self, fase, funcion, *args):
        if self.futuro is not None:
            raise RuntimeError("Ya hay una petición Modbus pendiente")
        self.fase = fase
        self._generacion_peticion = self._generacion
        self.futuro = self.executor.submit(funcion, *args)

    def reiniciar(self, sesion):
        """Cambia sesión sin cerrar TCP; descarta respuestas de la ejecución anterior."""
        if self.estado not in ("conectado", "diagnostico") or self.adaptador.sesion is None or sesion.cm.revision != self.adaptador.sesion.cm.revision:
            raise RuntimeError("El reinicio requiere conexión estable y el mismo modelo")
        self.vincular(sesion)

    def vincular(self, sesion, config=None, documento=None, observar_despues=False):
        """Vincula una ejecución a TCP existente; no vuelve a conectar."""
        if self.estado not in ("conectado", "diagnostico"):
            raise RuntimeError("Espera a que termine la conexión")
        config = config or self.adaptador.config
        if documento is not None:
            config.validar(documento)
        adaptador = Adaptador(config, sesion)
        valores = adaptador.valores_salida()
        self._generacion += 1
        self.adaptador = adaptador
        self._valores_reinicio = valores
        self.reiniciando = True
        self._observar_despues = observar_despues
        self.en_marcha = self._ejecutar = self.fallo_motor = self.cero_pendiente = False
        self._descartar_lectura = False
        self.muestra = {}
        self.estado = "conectado"
        self.mensaje = "Conectado · reiniciando GRAFCET y salidas iniciales…"

    def pausar(self, diagnostico=False):
        """Conserva transporte y salidas; un diagnóstico solicita cero."""
        if not self.activo or self.adaptador is None or (self.adaptador.sesion is None and not diagnostico):
            return
        anterior = self.adaptador
        if diagnostico:
            salidas = list(anterior.salidas or getattr(anterior, "salidas_control", []))
            self._salidas_seguras = (salidas, {s.variable: False if s.formato == "BOOL" else 0 for s in salidas})
        self._generacion += 1
        self.adaptador = MonitorEntradas.desde_adaptador(anterior)
        self.en_marcha = self._ejecutar = self.reiniciando = self.fallo_motor = self.cero_pendiente = False
        if self.estado == "diagnostico":
            self.estado = "conectado"
        if self.estado == "conectado":
            self.mensaje = "Conectado · GRAFCET parado · edición habilitada"

    def observar(self, config, documento):
        """Cambia el mapa de lectura (otro modelo) con el GRAFCET parado, sin tocar TCP; descarta lo que estuviera en vuelo."""
        if not self.activo:
            return
        monitor = MonitorEntradas(config, documento)
        self._generacion += 1
        self.adaptador = monitor
        self.muestra = {}
        self.en_marcha = self._ejecutar = self.reiniciando = self.fallo_motor = self.cero_pendiente = False

    def iniciar(self, config, sesion, prueba=False, documento=None):
        if self.activo or self.futuro is not None:
            raise RuntimeError("Desconecte antes de cambiar la conexión")
        self.adaptador = Adaptador(config, sesion) if sesion is not None else MonitorEntradas(config, documento)
        self.cliente = ClienteModbus(config.host, config.puerto, config.unidad, config.timeout_ms / 1000)
        self.estado = "probando" if prueba else "conectando"
        self.mensaje = "Probando conexión…" if prueba else "Conectando; actuadores a cero…"
        self.muestra, self.escritos = {}, {}
        self.fallo_motor = self.cero_pendiente = False
        self.reiniciando = False
        self._observar_despues = False
        self._salidas_seguras = None
        self.en_marcha = self._ejecutar = self._descartar_lectura = False
        # Calcular valores del motor en el hilo propietario, antes de encolar red.
        cero = self.adaptador.valores_salida(cero=True)
        def conectar():
            self.cliente.conectar()
            try:
                if not prueba:
                    escribir_salidas(self.cliente, self.adaptador.salidas, cero)
                return leer_entradas(self.cliente, self.adaptador.entradas)
            finally:
                if prueba:
                    self.cliente.cerrar()
        self._enviar("prueba" if prueba else "inicio", conectar)

    def desconectar(self):
        if not self.activo:
            return
        self.estado = "cerrando"
        self.mensaje = "Desconectando; la planta puede conservar sus salidas"
        # La respuesta pendiente se descarta; el mismo trabajador cerrará el socket.

    def tick(self, ejecutar=False):
        """Recoger red y aplicar muestras; llamar exclusivamente desde el hilo de sesión."""
        if self._cerrado:
            return
        self.solicitar_ejecucion(ejecutar and not self.reiniciando)
        if self.futuro is not None and self.futuro.done():
            futuro, fase = self.futuro, self.fase
            generacion = self._generacion_peticion
            self.futuro = None
            try:
                resultado = futuro.result()
                if self.estado != "cerrando" and generacion == self._generacion:
                    if fase == "prueba":
                        self.estado, self.mensaje = "desconectado", "Conexión probada; no se han escrito actuadores"
                    elif fase == "inicio":
                        self.muestra = resultado
                        self.estado, self.mensaje = "conectado", "Conectado · actuadores a cero · pulse Ejecutar"
                        self.escritos = self.adaptador.valores_salida(cero=True)
                        if self.adaptador.sesion is None:
                            self.mensaje = "Conectado · observación de entradas · sin escritura de salidas"
                    elif fase == "leer":
                        self.muestra = resultado
                        descartar = self._descartar_lectura
                        self._descartar_lectura = False
                        if self.adaptador.sesion is not None and ejecutar and not descartar and not self.fallo_motor and self.adaptador.sesion.status == "pausada-estable":
                            self.adaptador.aplicar(resultado)
                            if self.adaptador.sesion.status == "pausada-estable":
                                self.en_marcha = True
                                self.mensaje = "Conectado · Ejecutando · intercambio de sensores y actuadores activo"
                                valores = self.adaptador.valores_salida()
                                self._enviar("escribir", self._escribir, valores, list(self.adaptador.salidas))
                    elif fase in ("escribir", "cero"):
                        self.escritos = resultado
                        if fase == "cero":
                            self.mensaje = "Motor detenido · cero confirmado · desconecte y corrija el diagnóstico"
                    elif fase == "cerrar":
                        self.estado, self.mensaje = "desconectado", "Desconectado · salidas no garantizadas"
                    elif fase == "reiniciar":
                        self.escritos, self.muestra = resultado
                        self.reiniciando = False
                        self.mensaje = "Conectado · GRAFCET reiniciado · pulse Ejecutar"
                        if self._observar_despues:
                            self.adaptador = MonitorEntradas.desde_adaptador(self.adaptador)
                    elif fase == "seguras":
                        self.escritos = resultado
                        self._salidas_seguras = None
            except Exception as exc:
                # También incluye conversión inválida: no seguir controlando con muestras malas.
                self.estado, self.mensaje = "error", f"Conexión detenida: {exc}. Salidas no garantizadas."
                self.en_marcha = False
                self.reiniciando = False
                self.cliente.cerrar()  # la petición ya ha terminado
        if self.estado == "cerrando":
            if self.futuro is None:
                if self.fase == "cerrar":
                    self.estado, self.mensaje = "desconectado", "Desconectado · salidas no garantizadas"
                else:
                    self._enviar("cerrar", self.cliente.cerrar)
            return
        if self.estado not in ("conectado", "diagnostico"):
            return
        if self._salidas_seguras is not None:
            if self.futuro is None:
                senales, valores = self._salidas_seguras
                self._enviar("seguras", self._escribir, valores, senales)
            return
        if self.reiniciando:
            if self.futuro is None:
                valores = self._valores_reinicio
                salidas, entradas = list(self.adaptador.salidas), list(self.adaptador.entradas)
                def reinicio_red():
                    self._escribir(valores, salidas)
                    return valores, leer_entradas(self.cliente, entradas)
                self._enviar("reiniciar", reinicio_red)
            return
        if self.adaptador.sesion is not None and self.adaptador.sesion.status != "pausada-estable" and not self.fallo_motor:
            self.fallo_motor = self.cero_pendiente = True
            self.en_marcha = False
            self.estado, self.mensaje = "diagnostico", "Motor detenido · solicitando cero · reconecte para continuar"
        if self.futuro is not None:
            return
        if self.cero_pendiente:
            self.cero_pendiente = False
            self._enviar("cero", self._escribir, self.adaptador.valores_salida(cero=True), list(self.adaptador.salidas))
        elif not self.fallo_motor and monotonic() >= self.proxima:
            self.proxima = monotonic() + self.adaptador.config.periodo_ms / 1000
            self._enviar("leer", leer_entradas, self.cliente, self.adaptador.entradas)

    def _escribir(self, valores, senales=None):
        escribir_salidas(self.cliente, self.adaptador.salidas if senales is None else senales, valores)
        return valores

    def cerrar(self):
        # No destruir un trabajador activo: el cierre se serializa después de la petición.
        if self._cerrado:
            return
        self._cerrado = True
        self.estado = "desconectado"
        if self.cliente is not None:
            self.executor.submit(self.cliente.cerrar)
        self.executor.shutdown(wait=False, cancel_futures=False)
