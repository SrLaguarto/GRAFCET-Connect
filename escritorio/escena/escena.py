"""Escena incremental del editor: aplica solo lo que cambia entre dos modelos visuales (V2-E3, paso 4)."""
from typing import Any

from PySide6.QtWidgets import QGraphicsScene

from . import realizador
from .diferencia import diferencia
from .modelo_visual import ModeloVisual

UMBRAL_REHACER = 0.6   # si cambia más de esta parte de los objetos, es más simple y barato rehacer la escena entera


class EscenaIncremental(QGraphicsScene):
    """La escena del diagrama, en edición y en simulación: guarda el modelo visual que tiene dibujado y los ítems de cada objeto
    (`nodos`: clave -> [(descriptor, [ítems])]) y, ante uno nuevo, da de alta, de baja, actualiza y reordena solo lo que difiere.

    El dibujo completo de siempre (`diagrama.dibujar`, que usa la simulación) vacía el registro: la primera aplicación después
    rehace la escena entera. Nunca se deja la escena a medias: el modelo visual nuevo se construye antes de llamar a `aplicar`,
    y si aplicarlo falla se rehace por completo."""

    def __init__(self, padre: Any) -> None:
        super().__init__(padre)
        self.error: Exception | None = None   # el último fallo al aplicar (la escena se rehízo entera)
        self.reiniciar()

    # --- registro
    def reiniciar(self) -> None:
        self.modelo: ModeloVisual | None = None
        self.nodos: dict[Any, list[tuple[Any, list[Any]]]] = {}

    def clear(self) -> None:
        self.reiniciar()  # (antes que `clear`: ningún envoltorio de un ítem que Qt va a destruir debe seguir en el registro)
        super().clear()

    # --- aplicar
    def aplicar(self, mv: ModeloVisual) -> None:
        if self.modelo is None:
            self._rehacer(mv)
            return
        fallo: Exception | None = None
        try:
            cambios = diferencia(self.modelo, mv)
            if cambios.vacio:
                self.modelo = mv
            elif len(cambios.afectados) > UMBRAL_REHACER * max(1, len(mv.orden)):
                self._rehacer(mv)
            else:
                self._aplicar(cambios, mv)
        except Exception as exc:  # noqa: BLE001
            fallo = exc.with_traceback(None)
        if fallo is not None:
            # Fuera del `except`: su traza retiene los marcos de `_aplicar` y, con ellos, envoltorios de ítems que `clear` va a
            # destruir; un envoltorio de PySide que sobrevive a su objeto C++ acaba confundido con el siguiente que ocupe su dirección.
            self._rehacer(mv)
            self.error = fallo

    def _rehacer(self, mv: ModeloVisual) -> None:
        self.clear()
        try:
            self.nodos = realizador.crear_todo(self, mv)
        except Exception:
            self.reiniciar()
            raise
        self.modelo = mv

    def _quitar(self, nodo: list[tuple[Any, list[Any]]]) -> None:
        for _, items in nodo:
            for item in items:
                if item.scene() is self:
                    self.removeItem(item)

    def _aplicar(self, cambios: Any, mv: ModeloVisual) -> None:
        nuevos: list[Any] = []   # ítems que hay que colocar en su sitio del apilado
        recien: set[int] = set()  # los que acaban de crearse (ya están al final de los hermanos)
        self.modelo, anterior = None, self.modelo   # si algo falla a medias, el registro queda invalidado
        for clave in cambios.bajas:
            self._quitar(self.nodos.pop(clave))
        for clave, descriptores in cambios.cambiadas.items():
            nodo = self.nodos[clave]
            if cambios.misma_forma[clave]:
                rehecho = []
                for (antes, items), ahora in zip(nodo, descriptores):
                    if antes == ahora:
                        rehecho.append((ahora, items))
                    elif (z := items[0].zValue()) is not None and realizador.actualizar(items, antes, ahora):
                        if items[0].zValue() != z:
                            nuevos.extend(items)   # cambia de z: debe ocupar su sitio entre los de su nueva z
                        rehecho.append((ahora, items))
                    else:
                        self._quitar([(antes, items)])
                        items = realizador.crear(self, ahora)
                        nuevos.extend(items)
                        recien.update(id(i) for i in items)
                        rehecho.append((ahora, items))
                self.nodos[clave] = rehecho
            else:
                self._quitar(nodo)
                self.nodos[clave] = [(d, realizador.crear(self, d)) for d in descriptores]
                creados = [i for _, items in self.nodos[clave] for i in items]
                nuevos.extend(creados)
                recien.update(id(i) for i in creados)
        for clave, descriptores in cambios.altas.items():
            self.nodos[clave] = [(d, realizador.crear(self, d)) for d in descriptores]
            creados = [i for _, items in self.nodos[clave] for i in items]
            nuevos.extend(creados)
            recien.update(id(i) for i in creados)
        for clave in cambios.reordenadas:
            nuevos.extend(i for _, items in self.nodos[clave] for i in items)
        self._apilar(mv, nuevos, recien)
        self.modelo = mv

    def _apilar(self, mv: ModeloVisual, mover: list[Any], recien: set[int]) -> None:
        """Deja el orden entre ítems de igual `z` como lo da el dibujo completo: el de `mv.secuencia`. Qt apila por `z` y, a igualdad,
        por el orden de los hermanos, y `stackBefore` tiene dos límites que se comprobaron con Qt: solo actúa entre ítems de la misma
        `z` («sibling must have the same Z value as this item», dice su documentación) y solo sabe llevar un ítem hacia atrás. Por
        eso cada ítem que hay que colocar se lleva primero al final de los hermanos (los recién creados ya están allí) y después se
        pone delante del siguiente ítem de su misma `z`."""
        if not mover:
            return
        # (no se usa `parentItem()`: en PySide6 deja al ítem como propiedad de Python y, al morir su envoltorio, lo borra de la escena)
        ids = {id(i) for i in mover}
        orden = [i for clave in mv.orden for _, items in self.nodos[clave] for i in items if i.topLevelItem() is i]
        siguiente: dict[float, Any] = {}   # el siguiente ítem del dibujo, de cada z
        for item in reversed(orden):
            z = item.zValue()
            if id(item) in ids:
                if id(item) not in recien:
                    self.removeItem(item)
                    self.addItem(item)
                if z in siguiente:
                    item.stackBefore(siguiente[z])
            siguiente[z] = item
