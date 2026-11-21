"""Modelo visual: todo lo que se dibuja, como descriptores agrupados por elemento (V2-E3)."""
from dataclasses import dataclass, field
from typing import Any

from .descriptores import Clave, Descriptor, Grabadora


@dataclass
class ModeloVisual:
    objetos: dict[Clave, tuple[Descriptor, ...]]          # un objeto por elemento: clave -> sus descriptores, en orden
    orden: tuple[Clave, ...]                              # las claves en el orden de dibujo (el de su primer descriptor)
    secuencia: tuple[tuple[Clave, Descriptor], ...]       # todo, en el orden exacto de dibujo (fija el apilado)
    cajas: list[dict[str, Any]] = field(default_factory=list)      # dónde ha quedado cada acción
    uniones: list[dict[str, Any]] = field(default_factory=list)    # los trazos de cada etapa a sus acciones
    ordenes: list[dict[str, Any]] = field(default_factory=list)    # el rectángulo de cada orden de forzado

    def __eq__(self, otro: object) -> bool:
        return (isinstance(otro, ModeloVisual) and self.secuencia == otro.secuencia and self.cajas == otro.cajas
                and self.uniones == otro.uniones and self.ordenes == otro.ordenes)


def desde(g: Grabadora, cajas: list[dict[str, Any]], uniones: list[dict[str, Any]],
          ordenes: list[dict[str, Any]]) -> ModeloVisual:
    orden = g.orden
    return ModeloVisual({c: tuple(g.objetos[c]) for c in orden}, orden, tuple(g.secuencia), cajas, uniones, ordenes)


def construir(M: dict[str, Any], S: dict[str, Any], sel: set[str] | None = None, marcados: set[str] | None = None,
              naranja: set[str] | None = None, dependencias: bool = False) -> ModeloVisual:
    """El modelo visual de `M` con el estado `S`: el mismo recorrido que `diagrama.dibujar`, anotado en vez de pintado."""
    from .. import diagrama as dg
    g, uniones, ordenes = Grabadora(dg.servicios()), [], []
    cajas = dg._recorrer(g, M, S, sel, marcados, naranja, uniones, ordenes, dependencias)
    return desde(g, cajas, uniones, ordenes)
