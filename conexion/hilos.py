"""Guarda de hilos del ciclo de E/S (V2-E7, paso 0). Sin Qt.

El motor (`Session`) y el `Coordinador` los tocará un solo hilo a la vez: el candado de control (`Candado`, reentrante). Esta guarda
comprueba que se cumple. Solo con la variable `GRAFCONNECT_COMPROBAR_HILOS=1`; sin ella, `proteger` no toca el objeto y no cuesta nada.

Con la guarda activa y el hilo de control vivo (`candado.control_vivo`), cualquier lectura o escritura de un atributo o método protegido desde
un hilo que no tiene el candado lanza `AccesoSinCandado`, con el nombre del objeto, el del atributo y el del hilo. Mientras no haya hilo de
control (hoy, o después de pararlo) no se exige nada.

Uso (lo hará el hilo de control cuando exista):

    candado = Candado()
    proteger(coordinador, ("tick", "estado", "medidas", ...), candado, "Coordinador")
    with candado.hilo_de_control():      # mientras viva el hilo de control
        ...
"""
from contextlib import contextmanager
import os
import threading

VARIABLE = "GRAFCONNECT_COMPROBAR_HILOS"

# Lo que se protege en la ventana (V2-E7): lo que cambia el estado del coordinador o del motor, y la foto del motor (`observe`). No se protegen las
# lecturas de un escalar suelto (`estado`, `mensaje`, `activo`, `en_marcha`…): son atómicas y la pantalla las usa como banderas; lo que se lee en
# bloque (la muestra, las medidas, el estado del motor para dibujar) la pantalla lo copia con el candado cogido.
COORDINADOR = ("tick", "_tick_red", "_enviar", "iniciar", "vincular", "pausar", "reasignar", "observar", "desconectar", "solicitar_ejecucion",
               "reiniciar")
SESION = ("advance_to", "manual_input", "step_external", "step_evolution", "run_to_stable", "observe", "restart")


class AccesoSinCandado(RuntimeError):
    """Un hilo ha tocado el motor o el coordinador sin tener el candado de control mientras el hilo de control está vivo."""


class Candado:
    """Candado reentrante que sabe qué hilo lo tiene y si el hilo de control está vivo."""

    def __init__(self) -> None:
        self._candado = threading.RLock()
        self._dueno: int | None = None
        self._profundidad = 0
        self.control_vivo = False

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        ok = self._candado.acquire(blocking, timeout)
        if ok:
            self._dueno = threading.get_ident()
            self._profundidad += 1
        return ok

    def release(self) -> None:
        self._profundidad -= 1
        if self._profundidad == 0:
            self._dueno = None
        self._candado.release()

    __enter__ = acquire

    def __exit__(self, *_) -> None:
        self.release()

    def cogido_por_este_hilo(self) -> bool:
        return self._dueno == threading.get_ident()

    @contextmanager
    def hilo_de_control(self):
        """Marca que el hilo de control está vivo (a partir de aquí la guarda exige el candado)."""
        self.control_vivo = True
        try:
            yield self
        finally:
            self.control_vivo = False


def guarda_activa() -> bool:
    return os.environ.get(VARIABLE) == "1"


def proteger(objeto, nombres, candado: Candado, nombre: str | None = None) -> bool:
    """Con `GRAFCONNECT_COMPROBAR_HILOS=1`, hace que leer o escribir cualquiera de `nombres` (atributos o métodos) de `objeto` exija el candado
    cuando el hilo de control está vivo. Devuelve si lo ha protegido; sin la variable no hace nada. Cambia la clase del objeto por una subclase
    suya (sigue siendo `isinstance` de la original); `desproteger` lo deja como estaba."""
    if not guarda_activa():
        return False
    original = type(objeto)
    if getattr(original, "_guarda_de_hilos", False):
        return True
    protegidos = frozenset(nombres)
    etiqueta = nombre or original.__name__

    def exigir(clave: str) -> None:
        if candado.control_vivo and not candado.cogido_por_este_hilo():
            raise AccesoSinCandado(f"{etiqueta}.{clave} se ha tocado desde el hilo «{threading.current_thread().name}» sin el candado de control, "
                                   "con el hilo de control vivo: el motor y el coordinador solo se tocan con el candado cogido")

    class Protegido(original):
        _guarda_de_hilos = True
        _clase_original = original

        def __getattribute__(self, clave):
            if clave in protegidos:
                exigir(clave)
            return super().__getattribute__(clave)

        def __setattr__(self, clave, valor):
            if clave in protegidos:
                exigir(clave)
            super().__setattr__(clave, valor)

    Protegido.__name__ = original.__name__
    Protegido.__qualname__ = original.__qualname__
    objeto.__class__ = Protegido
    return True


def desproteger(objeto) -> None:
    clase = type(objeto)
    if getattr(clase, "_guarda_de_hilos", False):
        objeto.__class__ = clase._clase_original
