"""Hilo de control del ciclo de E/S (V2-E7, paso 1). Sin Qt.

Hace, con su propio reloj y sin pasar por el hilo de la pantalla, lo que antes hacía la rama «con conexión» de `Ventana._tick`:

    con el candado:  avanzar el reloj lógico del motor (si toca, antes de aplicar muestras: P-IMP-50)
                     `coordinador.tick(ejecutar)`        (leer → aplicar → calcular → escribir: la máquina de estados no cambia)
                     apuntar si el motor se ha parado o si la conexión se ha caído (la pantalla lo atiende)
    sin el candado:  esperar hasta el plazo de la próxima lectura o hasta que acabe una petición de red (`despertar`)

Reglas:
  - El motor (`Session`) y el `Coordinador` los toca quien tenga el candado (`conexion.hilos.Candado`, reentrante). El hilo de control lo coge para
    un ciclo (~1 ms); nunca lo retiene durante una espera, ni la pantalla durante un dibujo.
  - No toca Qt. «Ejecutar» lo fija la pantalla (`pedir_ejecucion`) y se decide en un único sitio (`_ejecutar_ahora`), donde cabrá una pausa futura.
  - El reloj lógico usa `perf_counter_ns` y conserva las fracciones de microsegundo (SRED05).

Espera. `Event.wait(0,005)` en Windows tarda ~16 ms (la resolución del temporizador del sistema, 15,625 ms, no la sube nadie) y `timeBeginPeriod(1)` no
es fiable aquí. `time.sleep` sí es preciso (Python ≥ 3.11 usa un temporizador de alta resolución) pero no se puede despertar antes. `Espera` combina las dos
cosas con un temporizador de alta resolución de Windows y un evento en una sola espera del sistema (`WaitForMultipleObjects`): vuelve a la hora exacta o en
cuanto alguien llama a `despertar`, lo que ocurra antes. Fuera de Windows, `Event.wait` largo más un sueño corto con comprobaciones.
"""
from collections.abc import Callable
from time import perf_counter, perf_counter_ns, sleep
import gc
import sys
import threading

from .hilos import Candado

PERIODO_DEFECTO_MS = 100  # sin conexión con periodo conocido
ESPERA_ACTIVA_MAX = 0.25  # s: lo máximo que duerme el hilo sin nada que hacer (se despierta antes con `despertar`)
ESPERA_MINIMA = 0.0002    # s: nunca gira sin dormir
INTERVALO_NOVEDADES = 0.1  # s: como mucho 10 avisos por segundo a la pantalla
INTERVALO_GIL = 0.0005     # s: el intervalo de cambio de hilo de Python mientras haya hilo de control (por defecto 5 ms): ver `_ajustar_gil`
REFREEZE_S = 10.0          # s: cada cuánto vuelve a congelar el gc el hilo de control (lo acumulado, sobre todo la traza, sale de las recolecciones); 0 = nunca

_gil = {"vivos": 0, "previo": None}  # cuántos hilos de control hay y el intervalo de cambio que había antes del primero
_gil_candado = threading.Lock()


def _ajustar_gil(arrancar: bool) -> None:
    """Mientras haya algún hilo de control, el intervalo de cambio del GIL baja a 0,5 ms: el hilo de control no espera hasta 5 ms a que la pantalla suelte
    Python (en un dibujo, que es Python casi todo) cada vez que vuelve de la red. Al parar el último se deja como estaba.
    Con el primero también se congela lo vivo del gc (`gc.freeze`): una recolección completa de 36-40 ms, cada ~2,5 s, paraba
    todos los hilos y fijaba el máximo del intervalo (E7); al parar el último se descongela. Mientras tanto, cada hilo vuelve a
    congelar cada `REFREEZE_S` (en `_bucle`): la traza, que crece sin parar, haría crecer también esas recolecciones (de 3 a 65 ms en 5 min)."""
    with _gil_candado:
        if arrancar:
            if _gil["vivos"] == 0:
                _gil["previo"] = sys.getswitchinterval()
                sys.setswitchinterval(INTERVALO_GIL)
                gc.freeze()  # lo vivo hasta ahora sale de las recolecciones: una gen2 de 36-40 ms paraba todos los hilos
            _gil["vivos"] += 1
        else:
            _gil["vivos"] = max(0, _gil["vivos"] - 1)
            if _gil["vivos"] == 0 and _gil["previo"] is not None:
                sys.setswitchinterval(_gil["previo"])
                _gil["previo"] = None
                gc.unfreeze()


class Espera:
    """Espera hasta una hora o hasta que alguien llame a `despertar`, con la precisión del temporizador de alta resolución."""

    def __init__(self) -> None:
        self._windows = sys.platform == "win32"
        self.cerrado = False
        self._cerradura = threading.Lock()  # `despertar` (cualquier hilo) y `cerrar` (el hilo de control) no se pisan
        self._evento_py = threading.Event()
        self._k = self._timer = self._evento = None
        if self._windows:
            try:
                self._abrir_windows()
            except (OSError, AttributeError):
                self._windows = False

    def _abrir_windows(self) -> None:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateWaitableTimerExW.restype = wintypes.HANDLE
        k.CreateWaitableTimerExW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        k.CreateEventW.restype = wintypes.HANDLE
        k.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        k.SetWaitableTimer.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong), wintypes.LONG, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL]
        k.SetWaitableTimer.restype = wintypes.BOOL
        k.WaitForMultipleObjects.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD]
        k.WaitForMultipleObjects.restype = wintypes.DWORD
        k.SetEvent.argtypes = [wintypes.HANDLE]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        timer = k.CreateWaitableTimerExW(None, None, 0x00000002, 0x1F0003)  # CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS
        if not timer:
            timer = k.CreateWaitableTimerExW(None, None, 0, 0x1F0003)  # Windows anterior a 10 1803: sin alta resolución
        evento = k.CreateEventW(None, False, False, None)  # de reinicio automático: un `despertar` sin nadie esperando no se pierde
        if not timer or not evento:
            for creado in (timer, evento):  # lo que sí se creó se cierra
                if creado:
                    k.CloseHandle(creado)
            raise OSError("no se pudo crear el temporizador o el evento")
        self._k, self._timer, self._evento, self._ctypes = k, timer, evento, ctypes
        self._manejadores = (wintypes.HANDLE * 2)(timer, evento)
        self._solo_evento = (wintypes.HANDLE * 1)(evento)

    def despertar(self) -> None:
        """Hace que la espera actual (o la próxima) vuelva ya. Se puede llamar desde cualquier hilo."""
        with self._cerradura:
            if self._windows and not self.cerrado:
                self._k.SetEvent(self._evento)
            else:
                self._evento_py.set()

    def esperar(self, hasta: float) -> None:
        """Duerme hasta `perf_counter() >= hasta` o hasta un `despertar`."""
        restante = hasta - perf_counter()
        if self._windows and not self.cerrado:
            if restante <= 0:
                self._k.WaitForMultipleObjects(1, self._solo_evento, False, 0)  # consume un aviso pendiente
                return
            vence = self._ctypes.c_longlong(-int(restante * 1e7))  # negativo: relativo, en unidades de 100 ns
            self._k.SetWaitableTimer(self._timer, self._ctypes.byref(vence), 0, None, None, False)
            self._k.WaitForMultipleObjects(2, self._manejadores, False, 0xFFFFFFFF)
            return
        if restante > 0.03:
            self._evento_py.wait(restante - 0.03)  # grueso: puede pasarse hasta ~16 ms, de ahí el margen
        while perf_counter() < hasta and not self._evento_py.is_set():
            sleep(0.0005)
        self._evento_py.clear()

    def cerrar(self) -> None:
        """Libera el temporizador y el evento. Después `despertar` no hace nada que importe y `esperar` cae al camino portable."""
        with self._cerradura:
            if self.cerrado:
                return
            self.cerrado = True
            if self._windows and self._timer is not None:
                self._k.CloseHandle(self._timer)
                self._k.CloseHandle(self._evento)
                self._timer = self._evento = None
            self._windows = False


class CicloES:
    """El hilo de control. `coordinador` es el `Coordinador`; `candado`, el de `conexion.hilos`. `al_novedad()` avisa (como mucho 10 veces por segundo, y
    al momento si cambia el estado de la conexión o hay un aviso) a quien dibuja; `al_error(exc)` recibe lo que lance un ciclo: el hilo sigue vivo."""

    def __init__(self, coordinador, candado: Candado, al_novedad: Callable[[], None] | None = None,
                 al_error: Callable[[BaseException], None] | None = None, sigue_vivo: Callable[[], bool] | None = None) -> None:
        self._origen, self.candado = coordinador, candado
        self.sigue_vivo = sigue_vivo  # () -> bool: si dice que no (la ventana que lo usa ya no existe), el hilo acaba solo
        self.al_novedad, self.al_error = al_novedad, al_error
        self._espera = Espera()
        self._hilo: threading.Thread | None = None
        self._parar = False
        self._pedida = False
        self._avisos: set[str] = set()
        self._marca_ns = perf_counter_ns()
        self._resto_ns = 0
        self._ultima_novedad = 0.0
        self._ultimo_estado: tuple | None = None
        self.ciclos = 0

    @property
    def coordinador(self):
        """El coordinador de ahora (`coordinador` puede ser un objeto o una función que lo da: la ventana puede cambiar el suyo)."""
        return self._origen() if callable(self._origen) else self._origen

    # -- vida del hilo -----------------------------------------------------------------------------------------------------------
    @property
    def vivo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def arrancar(self) -> None:
        if self.vivo:
            return
        if self._espera.cerrado:  # (el hilo anterior cerró la suya al acabar)
            self._espera = Espera()
        self._parar = False
        self._marca_ns, self._resto_ns = perf_counter_ns(), 0
        _ajustar_gil(True)
        self.candado.control_vivo = True
        self._hilo = threading.Thread(target=self._bucle, name="control-es", daemon=True)
        self._hilo.start()

    def parar(self) -> None:
        """Para el hilo y espera a que acabe. No llamarlo con el candado cogido (el hilo puede estar esperándolo)."""
        hilo = self._hilo
        if hilo is None:
            return
        self._parar = True
        self._espera.despertar()
        if hilo is not threading.current_thread():
            hilo.join()
        self._hilo = None

    def despertar(self) -> None:
        """Lo llama el trabajador de red al terminar una petición (cualquier hilo): el ciclo la atiende ya, sin esperar al plazo."""
        self._espera.despertar()

    # -- órdenes de la pantalla --------------------------------------------------------------------------------------------------
    def pedir_ejecucion(self, ejecutar: bool) -> None:
        """Play (True) o Stop/Pausa (False). Con el candado cogido por quien llama, o sin hilo vivo."""
        self._pedida = bool(ejecutar)
        self._espera.despertar()

    def _ejecutar_ahora(self) -> bool:
        """El único sitio donde se decide si el ciclo ejecuta el motor: aquí cabrá, sin tocar nada más, el estado de pausa futuro."""
        return self._pedida

    def tomar_avisos(self) -> set[str]:
        """Los avisos del ciclo para la pantalla (`motor_parado`, `conexion_caida`) desde la última vez; con el candado."""
        with self.candado:
            avisos, self._avisos = self._avisos, set()
        return avisos

    # -- el ciclo ----------------------------------------------------------------------------------------------------------------
    def ciclo(self) -> None:
        """Un ciclo: lo de `_tick` con conexión, sin Qt. Se puede llamar desde cualquier hilo (coge el candado) y cuantas veces se quiera: `tick` ya se llama
        hoy desde tres disparadores."""
        with self.candado:
            m = self.coordinador
            if m is None:
                return
            ahora = perf_counter_ns()
            us, self._resto_ns = divmod(max(0, ahora - self._marca_ns) + self._resto_ns, 1000)  # conserva las fracciones de µs
            self._marca_ns = ahora
            self.ciclos += 1
            if not m.activo:
                return
            pedida = self._ejecutar_ahora()
            sesion = m.adaptador.sesion if m.adaptador is not None else None
            ejecutar = pedida and m.estado == "conectado" and not m.reiniciando and sesion is not None
            if ejecutar and m.en_marcha and sesion.status == "pausada-estable":
                sesion.advance_to(sesion.z.time + us)  # el reloj lógico, antes de aplicar muestras (P-IMP-50)
            m.tick(ejecutar)
            if pedida:
                sesion = m.adaptador.sesion if m.adaptador is not None else None
                if sesion is not None and sesion.status != "pausada-estable":
                    self._avisos.add("motor_parado")
                if m.estado in ("error", "desconectado", "diagnostico") or sesion is None:
                    self._avisos.add("conexion_caida")

    def _plazo(self) -> float:
        """La hora (de `perf_counter`) del próximo ciclo: la próxima lectura, o el periodo si hay una petición en vuelo (el reloj lógico sigue avanzando)."""
        with self.candado:
            m = self.coordinador
            ahora = perf_counter()
            if m is None or not m.activo:
                return ahora + ESPERA_ACTIVA_MAX
            periodo = (m.adaptador.config.periodo_ms / 1000) if m.adaptador is not None else PERIODO_DEFECTO_MS / 1000
            plazo = ahora + max(periodo, ESPERA_MINIMA)
            if m.estado == "conectado" and not m.fallo_motor and m.futuro is None:
                plazo = min(plazo, max(m.proxima, ahora + ESPERA_MINIMA))
            return min(plazo, ahora + ESPERA_ACTIVA_MAX)

    def _bucle(self) -> None:
        espera = self._espera  # la de este hilo: si luego se arranca otro, tendrá la suya
        proximo_congelado = perf_counter() + REFREEZE_S
        try:
            while not self._parar:
                if self.sigue_vivo is not None and not self.sigue_vivo():
                    break
                try:
                    self.ciclo()
                except Exception as exc:  # noqa: BLE001 - nada muere en silencio: se cuenta a la pantalla y el hilo sigue
                    if self.al_error is not None:
                        self.al_error(exc)
                self._avisar()
                if REFREEZE_S > 0 and perf_counter() >= proximo_congelado:
                    gc.freeze()  # lo acumulado desde la última vez (la traza) sale también de las recolecciones
                    proximo_congelado = perf_counter() + REFREEZE_S
                espera.esperar(self._plazo())
        finally:
            # Al acabar, por `parar` o porque `sigue_vivo` ya no se cumple: libera la espera, quita la marca de hilo de control y devuelve el
            # intervalo de cambio del GIL (el contador de `_ajustar_gil` lleva la cuenta de los hilos vivos).
            espera.cerrar()
            self.candado.control_vivo = False
            _ajustar_gil(False)

    def _avisar(self) -> None:
        if self.al_novedad is None:
            return
        m = self.coordinador
        if m is None:
            return
        estado = (m.estado, m.mensaje, bool(self._avisos))  # lecturas sueltas de escalares: atómicas
        ahora = perf_counter()
        if estado != self._ultimo_estado or ahora - self._ultima_novedad >= INTERVALO_NOVEDADES:
            self._ultimo_estado, self._ultima_novedad = estado, ahora
            self.al_novedad()
