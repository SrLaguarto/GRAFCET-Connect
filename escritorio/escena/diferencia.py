"""Diferencia entre dos modelos visuales, sin Qt (V2-E3).

`diferencia(anterior, nuevo)` dice qué objetos (un objeto por elemento, ver `modelo_visual`) hay que dar de alta, de baja,
cambiar o reordenar para pasar del anterior al nuevo. Es la única fuente de verdad de lo que la escena incremental debe aplicar:
`aplicar(anterior, cambios)` reconstruye el nuevo a partir del anterior (la prueba de la propiedad)."""
from bisect import bisect_left
from dataclasses import dataclass

from .descriptores import Clave, Descriptor
from .modelo_visual import ModeloVisual

Objetos = dict[Clave, tuple[Descriptor, ...]]


@dataclass(frozen=True)
class Cambios:
    altas: dict[Clave, tuple[Descriptor, ...]]        # objetos nuevos
    bajas: tuple[Clave, ...]                          # objetos que ya no están
    cambiadas: dict[Clave, tuple[Descriptor, ...]]    # misma clave, descriptores distintos (con los nuevos)
    misma_forma: dict[Clave, bool]                    # de las cambiadas: mismo número y tipo de descriptores (se pueden actualizar en el sitio)
    reordenadas: tuple[Clave, ...]                    # objetos que siguen y cuyo sitio en el orden de dibujo ha cambiado
    orden: tuple[Clave, ...]                          # el orden de dibujo nuevo

    @property
    def vacio(self) -> bool:
        return not (self.altas or self.bajas or self.cambiadas or self.reordenadas)

    @property
    def afectados(self) -> set[Clave]:
        return set(self.altas) | set(self.bajas) | set(self.cambiadas) | set(self.reordenadas)


def forma(descriptores: tuple[Descriptor, ...]) -> tuple[str, ...]:
    return tuple(d[0] for d in descriptores)


def _fuera_de_la_subsecuencia_creciente(posiciones: list[int]) -> set[int]:
    """Índices de `posiciones` que no pertenecen a una subsecuencia creciente más larga (la que se queda quieta)."""
    colas: list[int] = []        # menor valor final de una subsecuencia de cada longitud
    indice_cola: list[int] = []  # índice del elemento que cierra cada una
    previo = [-1] * len(posiciones)
    for i, p in enumerate(posiciones):
        k = bisect_left(colas, p)
        if k == len(colas):
            colas.append(p)
            indice_cola.append(i)
        else:
            colas[k], indice_cola[k] = p, i
        previo[i] = indice_cola[k - 1] if k else -1
    quietos: set[int] = set()
    i = indice_cola[-1] if indice_cola else -1
    while i != -1:
        quietos.add(i)
        i = previo[i]
    return set(range(len(posiciones))) - quietos


def reordenadas(anterior: tuple[Clave, ...], nuevo: tuple[Clave, ...]) -> tuple[Clave, ...]:
    antes = {c: i for i, c in enumerate(anterior)}
    comunes = [c for c in nuevo if c in antes]
    mueven = _fuera_de_la_subsecuencia_creciente([antes[c] for c in comunes])
    return tuple(c for i, c in enumerate(comunes) if i in mueven)


def diferencia(anterior: ModeloVisual | None, nuevo: ModeloVisual) -> Cambios:
    viejos: Objetos = anterior.objetos if anterior is not None else {}
    orden_viejo = anterior.orden if anterior is not None else ()
    altas = {c: d for c, d in nuevo.objetos.items() if c not in viejos}
    bajas = tuple(c for c in orden_viejo if c not in nuevo.objetos)
    cambiadas = {c: d for c, d in nuevo.objetos.items() if c in viejos and viejos[c] != d}
    return Cambios(altas, bajas, cambiadas, {c: forma(viejos[c]) == forma(d) for c, d in cambiadas.items()},
                   reordenadas(orden_viejo, nuevo.orden), nuevo.orden)


def aplicar(anterior: ModeloVisual | None, cambios: Cambios) -> tuple[Objetos, tuple[Clave, ...]]:
    """Los objetos y el orden que resultan de aplicar `cambios` al modelo visual `anterior`."""
    objetos: Objetos = dict(anterior.objetos) if anterior is not None else {}
    for c in cambios.bajas:
        del objetos[c]
    objetos.update(cambios.cambiadas)
    objetos.update(cambios.altas)
    return {c: objetos[c] for c in cambios.orden}, cambios.orden
