"""Un trabajador de red; tick() y el motor pertenecen al hilo llamador.

No crea relojes ni ejecuta el motor desde el trabajador. La reconexión es manual.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import re
from time import perf_counter

from .adaptador import Adaptador, MonitorEntradas, escribir_salidas, leer_entradas, salidas_asignadas, valores_cero
from .modbus import ClienteModbus

WINERROR_CORTADA, WINERROR_RECHAZADA, WINERROR_TIEMPO = (10053, 10054), 10061, 10060
CLAVE_ANTERIOR = "anterior"  # variable de una salida del mapa anterior en un cero unido: (CLAVE_ANTERIOR, n), nunca un ID


def explicar_fallo(exc) -> str:
    """Una primera frase corta y legible para los fallos de red habituales (conexión anulada o reiniciada por el servidor Modbus,
    rechazada, tiempo agotado), con su código si lo hay; cadena vacía si no se reconoce (el mensaje sigue siendo el técnico).
    Solo explica: no decide nada del estado ni del comportamiento."""
    causa = exc.__cause__ if isinstance(exc.__cause__, OSError) else exc
    texto = str(exc)
    codigo = getattr(causa, "winerror", None)
    if codigo is None and (m := re.search(r"WinError (\d+)", texto)):
        codigo = int(m.group(1))
    sufijo = f" (WinError {codigo})" if codigo else ""
    if codigo in WINERROR_CORTADA or isinstance(causa, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return f"El servidor Modbus cerró o anuló la conexión{sufijo}"
    if codigo == WINERROR_RECHAZADA or isinstance(causa, ConnectionRefusedError):
        return f"El servidor Modbus rechazó la conexión{sufijo}: comprueba que está activo y la IP"
    if codigo == WINERROR_TIEMPO or isinstance(causa, TimeoutError) or "Tiempo de espera Modbus agotado" in texto:
        return f"El servidor Modbus no ha respondido a tiempo{sufijo}"
    if "El servidor cerró la conexión" in texto:
        return "El servidor Modbus cerró la conexión"
    return ""


class Coordinador:
    def __init__(self, notificar=None):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="modbus")
        self.notificar = notificar
        self.medidas = {}
        self._ultima_lectura = None
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
        self._salidas_seguras = None
        self._seguras_en_vuelo = None  # el cero de `_salidas_seguras` ya enviado y sin confirmar (si llega Play, no se repite)
        self._cero_al_cerrar = None  # (señales, valores) del cero que falta por escribir antes de cerrar el TCP
        self._tcp_abierto = False  # lo pone el trabajador al conectar: si falla antes, nunca hubo conexión ni se escribió nada
        self._texto_cierre = "Desconectado"

    def solicitar_ejecucion(self, ejecutar):
        if ejecutar != self._ejecutar:
            self.en_marcha = False
            if self.estado == "conectado":
                self.mensaje = ("Conectado · leyendo sensores antes de ejecutar…" if ejecutar else
                                "Conectado · Stop · salidas a cero")
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
        marcas = {}
        self._marcas_peticion = marcas
        def trabajo():
            marcas["inicio"] = perf_counter()
            try:
                return funcion(*args)
            finally:
                marcas["fin"] = perf_counter()
        self.futuro = self.executor.submit(trabajo)
        if self.notificar is not None:
            self.futuro.add_done_callback(lambda _: self.notificar())

    def reiniciar(self, sesion):
        """Cambia sesión sin cerrar TCP; descarta respuestas de la ejecución anterior."""
        if self.estado not in ("conectado", "diagnostico") or self.adaptador.sesion is None or sesion.cm.revision != self.adaptador.sesion.cm.revision:
            raise RuntimeError("El reinicio requiere conexión estable y el mismo modelo")
        self.vincular(sesion)

    def vincular(self, sesion, config=None, documento=None):
        """Vincula una ejecución a TCP existente; no vuelve a conectar. No escribe nada: primero se leen las entradas de la
        planta (`reiniciando` dura hasta que no queda nada en vuelo de la ejecución anterior), se aplican a la sesión nueva,
        el motor calcula y solo entonces se escriben las salidas (leer, aplicar, calcular, escribir)."""
        if self.estado not in ("conectado", "diagnostico"):
            raise RuntimeError("Espera a que termine la conexión")
        config = config or self.adaptador.config
        if documento is not None:
            config.validar(documento)
        adaptador = Adaptador(config, sesion)
        adaptador.valores_salida()  # solo comprueba que las salidas iniciales caben en su formato; no se escribe nada todavía
        self._generacion += 1
        self.adaptador = adaptador
        self.reiniciando = True
        self.proxima = 0  # Tras descartar lo antiguo, leer inmediatamente antes de ejecutar.
        self.en_marcha = self._ejecutar = self.fallo_motor = self.cero_pendiente = False
        self._descartar_lectura = False
        self.muestra = {}
        self.estado = "conectado"
        self.mensaje = "Conectado · reiniciando GRAFCET · leyendo sensores antes de ejecutar…"

    def pausar(self, diagnostico=False):
        """Pausa: conserva el transporte, deja de ejecutar y pide cero para todas las salidas asignadas (coils y holding):
        Pausa es «todo a 0 hasta un nuevo Play». Ya en observación (sin sesión) solo vuelve a pedir el cero si se pide
        expresamente (`diagnostico`: un diagnóstico del motor o el cambio de modelo). Con la red caída el cero no se
        garantiza: es el estado «error» del tick."""
        if not self.activo or self.adaptador is None or (self.adaptador.sesion is None and not diagnostico):
            return
        anterior = self.adaptador
        salidas = salidas_asignadas(anterior)
        # Si el motor ya se había detenido, `tick` pidió el cero por su cuenta: se aprovecha en vez de repetirlo (en vuelo se
        # adopta como el de Pausa; ya confirmado no hay nada más que escribir; sin enviar, `_salidas_seguras` lo sustituye)
        cero_del_diagnostico = self.fallo_motor and not self.cero_pendiente
        self._salidas_seguras = None if cero_del_diagnostico else (salidas, valores_cero(salidas))
        self._generacion += 1
        if cero_del_diagnostico and self.futuro is not None and self.fase == "cero":
            self.fase, self._generacion_peticion = "seguras", self._generacion
        self.adaptador = MonitorEntradas.desde_adaptador(anterior)
        self.en_marcha = self._ejecutar = self.reiniciando = self.fallo_motor = self.cero_pendiente = False
        if self.estado == "diagnostico":
            self.estado = "conectado"
        if self.estado == "conectado":
            self.mensaje = "Conectado · Stop · salidas a cero · edición habilitada"

    def observar(self, config, documento):
        """Cambia el mapa de lectura (otro modelo) con el GRAFCET parado, sin tocar TCP; descarta lo que estuviera en vuelo.
        Con la conexión establecida (o en curso; la prueba no escribe nada) pide también el cero de las salidas asignadas del
        mapa nuevo: se une al cero pendiente del mapa anterior, si lo hay, con un solo cero por canal."""
        if not self.activo:
            return
        monitor = MonitorEntradas(config, documento)
        self._generacion += 1
        self.adaptador = monitor
        self.muestra = {}
        self.en_marcha = self._ejecutar = self.reiniciando = self.fallo_motor = self.cero_pendiente = False
        nuevas = salidas_asignadas(monitor)
        if nuevas and self.estado in ("conectando", "conectado", "diagnostico"):
            self._salidas_seguras = self._unir_ceros(self._salidas_seguras, nuevas)

    @staticmethod
    def _unir_ceros(previo, nuevas):
        """El cero pendiente `previo` ((señales, valores) o None) junto con el de las salidas `nuevas`: un solo cero por canal.
        Las señales nuevas conservan su variable (es la que se muestra); las de antes, que ya no son de este modelo y cuyos ID
        podrían coincidir con los nuevos, van con una clave propia (`CLAVE_ANTERIOR`)."""
        senales, valores = list(nuevas), valores_cero(nuevas)
        canales = {(s.area, s.direccion) for s in nuevas}
        for i, s in enumerate(previo[0] if previo else ()):
            if (s.area, s.direccion) not in canales:
                clave = (CLAVE_ANTERIOR, i)
                senales.append(replace(s, variable=clave))
                valores[clave] = False if s.formato == "BOOL" else 0
        return senales, valores

    def iniciar(self, config, sesion, prueba=False, documento=None):
        """Conecta y, salvo en la prueba, deja a 0 todas las salidas asignadas (coils y holding) antes de leer las entradas:
        también sin sesión (Pausa), porque en Pausa todo está a 0. La prueba no escribe nada."""
        if self.activo or self.futuro is not None:
            raise RuntimeError("Desconecte antes de cambiar la conexión")
        self.adaptador = Adaptador(config, sesion) if sesion is not None else MonitorEntradas(config, documento)
        self.cliente = ClienteModbus(config.host, config.puerto, config.unidad, config.timeout_ms / 1000)
        self.estado = "probando" if prueba else "conectando"
        self.mensaje = "Probando conexión…" if prueba else "Conectando; actuadores a cero…"
        self.muestra, self.escritos = {}, {}
        self.medidas = {}
        self._ultima_lectura = None
        self.fallo_motor = self.cero_pendiente = False
        self.reiniciando = False
        self._salidas_seguras = self._cero_al_cerrar = self._seguras_en_vuelo = None
        self._tcp_abierto = False
        self.en_marcha = self._ejecutar = self._descartar_lectura = False
        # Calcular valores del motor en el hilo propietario, antes de encolar red.
        cero = self.adaptador.valores_salida(cero=True)
        salidas = salidas_asignadas(self.adaptador)
        def conectar():
            self.cliente.conectar()
            self._tcp_abierto = True
            try:
                if not prueba:
                    escribir_salidas(self.cliente, salidas, cero)
                return leer_entradas(self.cliente, self.adaptador.entradas)
            finally:
                if prueba:
                    self.cliente.cerrar()
        self._enviar("prueba" if prueba else "inicio", conectar)

    def _cero_de_cierre(self):
        """El cero que se intenta escribir antes de cerrar el TCP: (señales, valores) de todas las salidas asignadas, o None si
        la conexión aún no está establecida (conectando, probando) o no hay salidas asignadas."""
        if self.estado not in ("conectado", "diagnostico") or self.adaptador is None:
            return None
        salidas = salidas_asignadas(self.adaptador)
        return (salidas, valores_cero(salidas)) if salidas else None

    def desconectar(self):
        """Con la conexión establecida, escribe el cero de todas las salidas asignadas ANTES de cerrar el TCP (mejor esfuerzo:
        si la red falla, se cierra igual y el estado pasa a «error» con el aviso de salidas no garantizadas)."""
        if not self.activo or self.estado == "cerrando":
            return
        self._cero_al_cerrar = self._cero_de_cierre()
        self._salidas_seguras = None  # el cero del cierre lo sustituye
        self._texto_cierre = ("Desconectado · salidas no garantizadas" if self.adaptador is not None
                              and salidas_asignadas(self.adaptador) else "Desconectado")
        self.estado = "cerrando"
        self.mensaje = "Desconectando · salidas a cero…" if self._cero_al_cerrar else "Desconectando…"
        # La respuesta pendiente se descarta; el mismo trabajador escribirá el cero y cerrará el socket.

    def tick(self, ejecutar=False):
        """Recoger red y aplicar muestras; llamar exclusivamente desde el hilo de sesión."""
        if self._cerrado:
            return
        self.solicitar_ejecucion(ejecutar and not self.reiniciando)
        if self.futuro is not None and self.futuro.done():
            futuro, fase = self.futuro, self.fase
            generacion = self._generacion_peticion
            marcas = self._marcas_peticion
            ahora = perf_counter()
            if generacion == self._generacion:
                self.medidas[f"{fase}_red_ms"] = (marcas["fin"] - marcas["inicio"]) * 1000
                self.medidas[f"{fase}_espera_ms"] = (ahora - marcas["fin"]) * 1000
            self.futuro = None
            try:
                resultado = futuro.result()
                if fase == "cero-cierre":
                    self.escritos = resultado
                    self._texto_cierre = "Desconectado · salidas a cero"
                elif (fase == "seguras" and self.estado != "cerrando" and generacion != self._generacion
                      and self._salidas_seguras is not None and self._salidas_seguras is self._seguras_en_vuelo):
                    # Play (`vincular`) llegó con el cero de Pausa ya enviado: la respuesta es de la ejecución anterior pero
                    # confirma ese mismo cero, que no se repite (si no llega, es el fallo de red de abajo: el cero no se da por hecho)
                    self._salidas_seguras = self._seguras_en_vuelo = None
                elif self.estado != "cerrando" and generacion == self._generacion:
                    if fase == "prueba":
                        self.estado, self.mensaje = "desconectado", "Conexión probada; no se han escrito actuadores"
                    elif fase == "inicio":
                        self.muestra = resultado
                        self.estado, self.mensaje = "conectado", "Conectado · actuadores a cero · pulse Play"
                        self.escritos = self.adaptador.valores_salida(cero=True)
                        if self.adaptador.sesion is None:  # Pausa: lo asignado ya está a 0 y solo se observan las entradas
                            self.mensaje = ("Conectado · Stop · salidas a cero · observando las entradas" if self.escritos else
                                            "Conectado · observación de entradas · sin salidas asignadas")
                    elif fase == "leer":
                        anterior = self._ultima_lectura
                        if anterior is not None and anterior[0] == generacion:
                            self.medidas["sondeo_ms"] = (marcas["inicio"] - anterior[1]) * 1000
                            self.medidas["sondeo_max_ms"] = max(self.medidas.get("sondeo_max_ms", 0), self.medidas["sondeo_ms"])
                        self._ultima_lectura = (generacion, marcas["inicio"])
                        self.muestra = resultado
                        descartar = self._descartar_lectura
                        self._descartar_lectura = False
                        if self.adaptador.sesion is not None and ejecutar and not descartar and not self.fallo_motor and self.adaptador.sesion.status == "pausada-estable":
                            self._inicio_ciclo = marcas["inicio"]
                            inicio_evolucion = perf_counter()
                            self.adaptador.aplicar(resultado)
                            self.medidas["evolucion_ms"] = (perf_counter() - inicio_evolucion) * 1000
                            if self.adaptador.sesion.status == "pausada-estable":
                                self.en_marcha = True
                                self.mensaje = "Conectado · Ejecutando · intercambio de sensores y actuadores activo"
                                valores = self.adaptador.valores_salida()
                                self._enviar("escribir", self._escribir, valores, list(self.adaptador.salidas))
                    elif fase in ("escribir", "cero"):
                        self.escritos = resultado
                        if fase == "escribir":
                            self.medidas["ciclo_ms"] = (marcas["fin"] - self._inicio_ciclo) * 1000
                            self.medidas["ciclo_max_ms"] = max(self.medidas.get("ciclo_max_ms", 0), self.medidas["ciclo_ms"])
                        if fase == "cero":
                            self.mensaje = "Motor detenido · cero confirmado · desconecte y corrija el diagnóstico"
                    elif fase == "cerrar":
                        self.estado, self.mensaje = "desconectado", "Desconectado · salidas no garantizadas"
                    elif fase == "seguras":
                        # un cero unido (`observar`) también pone a cero lo del mapa anterior: eso ya no se muestra
                        self.escritos = {k: v for k, v in resultado.items() if not isinstance(k, tuple)}
                        self._salidas_seguras = self._seguras_en_vuelo = None
            except Exception as exc:
                # También incluye conversión inválida: no seguir controlando con muestras malas.
                frase = explicar_fallo(exc)  # solo cambia el texto: una frase legible y, detrás, el detalle técnico
                if self.estado == "cerrando":  # el usuario acaba de desconectar: se le dice eso, no que reconecte
                    motivo = f"{frase or exc}." + (f" Detalle: {exc}" if frase else "")
                    if fase in ("inicio", "prueba") and not self._tcp_abierto:  # nunca hubo conexión: no se intentó ningún cero
                        texto = f"Desconectado · no se llegó a conectar: {motivo}"
                    elif fase == "prueba":  # la prueba no escribe nada: no hay salidas que garantizar
                        texto = f"Desconectado · la prueba de conexión se interrumpió: {motivo}"
                    else:
                        texto = f"Desconectado · salidas no garantizadas · no se pudo poner a cero la planta: {motivo}"
                    self.estado, self.mensaje = "error", texto
                else:
                    self.estado, self.mensaje = "error", (
                        f"{frase}. Salidas no garantizadas. Pulsa Conectar para reanudar. Detalle: {exc}" if frase else
                        f"Conexión detenida: {exc}. Salidas no garantizadas.")
                self.en_marcha = False
                self.reiniciando = False
                self._cero_al_cerrar = None
                self.cliente.cerrar()  # la petición ya ha terminado
        if self.estado == "cerrando":
            if self.futuro is None:
                if self.fase == "cerrar":
                    self.estado, self.mensaje = "desconectado", self._texto_cierre
                elif self._cero_al_cerrar is not None:
                    senales, valores = self._cero_al_cerrar
                    self._cero_al_cerrar = None
                    self._enviar("cero-cierre", self._escribir, valores, senales)
                else:
                    self._enviar("cerrar", self.cliente.cerrar)
            return
        if self.estado not in ("conectado", "diagnostico"):
            return
        if self._salidas_seguras is not None:
            if self.futuro is None:
                senales, valores = self._salidas_seguras
                self._seguras_en_vuelo = self._salidas_seguras
                self._enviar("seguras", self._escribir, valores, senales)
            return
        if self.reiniciando:
            # Sesión nueva: no se escribe nada hasta leer y aplicar las entradas. Mientras queda algo en vuelo de la ejecución
            # anterior (su respuesta se descarta por la generación) se espera; después se sale de aquí SIN leer en este mismo
            # tic: la lectura se pide con la ejecución ya solicitada (si no, `_descartar_lectura` la tiraría) y es la que se
            # aplica, de modo que la primera escritura ya lleva las entradas de la planta.
            if self.futuro is None:
                self.reiniciando = False
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
        elif not self.fallo_motor and perf_counter() >= self.proxima:
            self.proxima = perf_counter() + self.adaptador.config.periodo_ms / 1000
            self._enviar("leer", leer_entradas, self.cliente, self.adaptador.entradas)

    def _escribir(self, valores, senales=None):
        escribir_salidas(self.cliente, self.adaptador.salidas if senales is None else senales, valores)
        return valores

    def cerrar(self):
        # No destruir un trabajador activo: el cierre se serializa después de la petición.
        if self._cerrado:
            return
        self._cerrado = True
        cero = self._cero_al_cerrar or self._cero_de_cierre()  # el cero va antes de cerrar el TCP (mejor esfuerzo)
        self._cero_al_cerrar = None
        self.estado = "desconectado"
        if self.cliente is not None:
            self.executor.submit(self._cerrar_tras_cero, cero)
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _cerrar_tras_cero(self, cero):
        """En el trabajador, tras lo pendiente: el cero, si lo hay, y el cierre del TCP pase lo que pase (si la red falla, se
        cierra igual)."""
        try:
            if cero is not None:
                escribir_salidas(self.cliente, *cero)
        except Exception:  # noqa: BLE001 - mejor esfuerzo: ya no hay a quién avisar
            pass
        finally:
            self.cliente.cerrar()
