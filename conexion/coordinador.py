"""Un trabajador de red; tick() y el motor pertenecen al hilo llamador.

No crea relojes ni ejecuta el motor desde el trabajador. La reconexión es manual.
"""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from .adaptador import Adaptador, escribir_salidas, leer_entradas
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

    @property
    def activo(self):
        return self.estado in ("conectando", "conectado", "diagnostico", "cerrando", "probando")

    def _enviar(self, fase, funcion, *args):
        if self.futuro is not None:
            raise RuntimeError("Ya hay una petición Modbus pendiente")
        self.fase = fase
        self.futuro = self.executor.submit(funcion, *args)

    def iniciar(self, config, sesion, prueba=False):
        if self.activo or self.futuro is not None:
            raise RuntimeError("Desconecte antes de cambiar la conexión")
        self.adaptador = Adaptador(config, sesion)
        self.cliente = ClienteModbus(config.host, config.puerto, config.unidad, config.timeout_ms / 1000)
        self.estado = "probando" if prueba else "conectando"
        self.mensaje = "Probando conexión…" if prueba else "Conectando; actuadores a cero…"
        self.muestra, self.escritos = {}, {}
        self.fallo_motor = self.cero_pendiente = False
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
        if self.futuro is not None and self.futuro.done():
            futuro, fase = self.futuro, self.fase
            self.futuro = None
            try:
                resultado = futuro.result()
                if self.estado != "cerrando":
                    if fase == "prueba":
                        self.estado, self.mensaje = "desconectado", "Conexión probada; no se han escrito actuadores"
                    elif fase == "inicio":
                        self.muestra = resultado
                        self.estado, self.mensaje = "conectado", "Conectado · actuadores a cero · pulse Ejecutar"
                        self.escritos = self.adaptador.valores_salida(cero=True)
                    elif fase == "leer":
                        self.muestra = resultado
                        if ejecutar and not self.fallo_motor and self.adaptador.sesion.status == "pausada-estable":
                            self.adaptador.aplicar(resultado)
                            if self.adaptador.sesion.status == "pausada-estable":
                                valores = self.adaptador.valores_salida()
                                self._enviar("escribir", self._escribir, valores)
                    elif fase in ("escribir", "cero"):
                        self.escritos = resultado
                        if fase == "cero":
                            self.mensaje = "Motor detenido · cero confirmado · desconecte y corrija el diagnóstico"
                    elif fase == "cerrar":
                        self.estado, self.mensaje = "desconectado", "Desconectado · salidas no garantizadas"
            except Exception as exc:
                # También incluye conversión inválida: no seguir controlando con muestras malas.
                self.estado, self.mensaje = "error", f"Conexión detenida: {exc}. Salidas no garantizadas."
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
        if self.adaptador.sesion.status != "pausada-estable" and not self.fallo_motor:
            self.fallo_motor = self.cero_pendiente = True
            self.estado, self.mensaje = "diagnostico", "Motor detenido · solicitando cero · reconecte para continuar"
        if self.futuro is not None:
            return
        if self.cero_pendiente:
            self.cero_pendiente = False
            self._enviar("cero", self._escribir, self.adaptador.valores_salida(cero=True))
        elif not self.fallo_motor and monotonic() >= self.proxima:
            self.proxima = monotonic() + self.adaptador.config.periodo_ms / 1000
            self._enviar("leer", leer_entradas, self.cliente, self.adaptador.entradas)

    def _escribir(self, valores):
        escribir_salidas(self.cliente, self.adaptador.salidas, valores)
        return valores

    def cerrar(self):
        # No destruir un trabajador activo: el cierre se serializa después de la petición.
        if self.cliente is not None:
            self.executor.submit(self.cliente.cerrar)
        self.executor.shutdown(wait=False, cancel_futures=False)
