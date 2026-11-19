"""Reutiliza los recorridos de los enlaces mientras su geometría no cambie."""
from copy import deepcopy
from typing import Any, Callable

from grafcet import routing


# También cuentan las acciones de cada etapa: los retornos evitan sus cajas y marcas.
ENTRADAS = ("steps", "macros", "transitions", "bars", "linkStyles")


class RutasDiagrama:
    def __init__(self) -> None:
        self.vaciar()

    def vaciar(self) -> None:
        self.clave: tuple[Any, ...] | None = None
        self.base: list[dict[str, Any]] = []
        self.ajustadas: list[dict[str, Any]] | None = None

    @staticmethod
    def entradas(modelo: dict[str, Any]) -> tuple[Any, ...]:
        # El orden de las listas determina el orden de los enlaces y el reparto de carriles.
        return tuple(modelo.get(nombre) for nombre in ENTRADAS)

    def _guardar(self, clave: tuple[Any, ...], base: list[dict[str, Any]]) -> None:
        self.clave = deepcopy(clave)
        self.base = base
        self.ajustadas = None

    def preparar(self, modelo: dict[str, Any]) -> None:
        """Recibe los recorridos recién calculados por Vista, antes de retocar su modelo."""
        if "links" in modelo:
            clave = self.entradas(modelo)
            if clave != self.clave:
                self._guardar(clave, modelo["links"])

    def obtener(self, modelo: dict[str, Any], ajustar: Callable) -> list[dict[str, Any]]:
        clave = self.entradas(modelo)
        if clave != self.clave:
            self._guardar(clave, routing.enlaces(modelo))
        if self.ajustadas is None:
            self.ajustadas = ajustar(modelo, self.base)
        return self.ajustadas


rutas = RutasDiagrama()
