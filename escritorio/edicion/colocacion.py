"""Adaptadores a la geometría E1 para obstáculos, huecos y equidistancia."""
from __future__ import annotations

from typing import Any
from PySide6.QtCore import QPointF, QRectF
from grafcet.diagnostics import Diagnostic, DiagnosticError
from ..geometria import acciones as geo_acciones, choques as geo_choques
from ..geometria import equidistancia as geo_equidistancia, textos as geo_textos
from ..geometria.base import Rect, esquina_parcial
from ..geometria.choques import DESPLAZA_PASADAS, MARGEN_SOLAPE
from ..diagrama import ACT_MIN, H, REJILLA, _Pintor, cajas_parciales, medida_comentario
from .constantes import DY, MSG_EQUIDISTANCIA


class _Colocacion:
    def _elementos(self) -> list[tuple[str, QRectF, str]]:
        return [(i, QRectF(*r), etapa) for i, r, etapa in self._elementos_geometricos()]

    def _elementos_geometricos(self):
        acciones = getattr(self.diagrama, "cajas_acciones", None) or []
        ordenes = getattr(self.diagrama, "cajas_ordenes", None) or []
        return geo_choques.elementos(self.M, acciones, ordenes, _Pintor.ancho, medida_comentario)

    def _solapa(self, huella: list[QRectF], propios: set[str]) -> list[QRectF]:
        cajas = [Rect(*r.getRect()) for r in huella]
        return [QRectF(*r) for r in geo_choques.solapa(self._elementos_geometricos(), cajas, propios)]

    def _colocadas(self) -> list[dict[str, Any]]:
        return geo_acciones.colocadas(self.M, _Pintor.ancho)

    def _textos_transiciones(self) -> list[tuple[QRectF, str]]:
        return [(QRectF(*r), tid) for r, tid in geo_textos.textos_transiciones(self.M, _Pintor.ancho)]

    def _situacion(self, clave: str) -> tuple[float, float, list[dict[str, Any]], bool] | None:
        return geo_acciones.situacion(self.M, clave)

    def _choques(self, clave: str, disposicion: str) -> list[tuple[QRectF, float, float, float]]:
        choques = geo_choques.choques(
            self.M, clave, disposicion, self._previas, _Pintor.ancho, medida_comentario, self._alto_minimo_barra,
        )
        return [(QRectF(*r), ancla, izq, derecha) for r, ancla, izq, derecha in choques]

    def _desplazar(self, corte: float, d: int, propio: str) -> None:
        ed = self.ed
        plan = geo_choques.plan_desplazamiento(
            self.M, ed.bars(), ed.draft_actions(), ed.link_styles(), corte, d, propio,
        )
        for ident, x, y in plan.nodos:
            ed.move(ident, x, y)
        for ident, x, medida, ensanchar in plan.barras:
            if ensanchar:
                ed.resize_bar(ident, x, medida)
            else:
                ed.move_bar(ident, x, medida)
        if plan.sueltas:
            ed.update_draft_actions(plan.sueltas)
        for ident, estilo in plan.estilos.items():
            ed.set_link_style(ident, estilo)

    def _despejar(self, clave: str, reconstruir: bool = True) -> bool:
        """Que las acciones de la etapa (o del grupo suelto) `clave`, con la colocación elegida, no queden encima de otro
        elemento. Si ya caben, no hace nada. Si no, abre hueco: desplaza a la derecha, con sus enlaces, todo lo que empieza
        donde empieza el primer obstáculo o más allá (`_desplazar`), lo justo para dejar el margen y en pasos de rejilla, hasta
        DESPLAZA_MAX. Si no se consigue (el obstáculo está a la izquierda de la etapa o debajo de ella, o pide más de
        DESPLAZA_MAX), deshace lo desplazado y lo deja como está. Devuelve si cabe. Va dentro de una operación atómica."""
        if reconstruir:
            self.reconstruir()
        disposicion = self.colocacion(clave)
        choques = self._choques(clave, disposicion)
        if not choques:
            return True
        x, _, _, suelto = self._situacion(clave)
        n, rehacer, total = len(self.ed.undo_stack), list(self.ed.redo_stack), 0
        for _ in range(DESPLAZA_PASADAS):
            limites = [(r.left(), ancla, izq, derecha) for r, ancla, izq, derecha in choques]
            siguiente = geo_choques.proximo_desplazamiento(
                limites, x if suelto else x + H, total, self._desplazamiento_maximo,
            )
            if siguiente is None:
                break
            corte, d = siguiente
            total += d
            self._desplazar(corte, d, clave)
            self.reconstruir()
            choques = self._choques(clave, disposicion)
            if not choques:
                return True
        while len(self.ed.undo_stack) > n:  # no se pudo: ningún desplazamiento a medias
            self.ed.undo()
        self.ed.redo_stack[:] = rehacer  # (lo deshecho no se puede rehacer: la pila de rehacer, como estaba)
        self.reconstruir()
        return False

    def _firmas(self) -> dict[str, tuple[Any, ...]]:
        return geo_acciones.firmas(self._colocadas())

    def _asegurar_hueco(self, antes: dict[str, tuple[Any, ...]]) -> list[str]:
        """Tras una edición (dentro de su operación atómica): las etapas y grupos sueltos cuyas acciones cambiaron respecto a
        `antes` (`_firmas`) se despejan (`_despejar`), y también las etapas que pasan a tener acciones. Un grupo suelto que
        no estaba en `antes` (las acciones que se acaban de separar de su etapa) no se despeja: se queda donde estaba.
        Devuelve los que no se pudieron: sus acciones quedan encima de algo. No cuenta lo que ya chocaba antes de la operación
        (una acción que estaba y no se ha movido): la banderita de una acción condicionada que ya rozaba un texto de transición
        hacía parpadear la etapa con cada acción nueva (AA1)."""
        self.reconstruir()
        despues = self._firmas()
        etapas = {s["id"] for s in self.M["steps"]}
        pendientes = []
        for k in geo_choques.candidatos_hueco(antes, despues, etapas):
            if not self._despejar(k, reconstruir=False):
                self._previas = antes.get(k, ())
                try:
                    if self._choques(k, self.colocacion(k)):
                        pendientes.append(k)
                finally:
                    self._previas = ()
        return pendientes

    def _huella_arrastre(self, a: dict[str, Any]) -> list[QRectF]:
        cajas = getattr(self.diagrama, "cajas_acciones", None) or []
        return [QRectF(*r) for r in geo_choques.huella_arrastre(a, self._elementos_geometricos, cajas)]

    def _malas_arrastre(self, a: dict[str, Any]) -> list[QRectF]:
        tipo = a.get("tipo")
        propios = set(a["ids"]) if tipo in ("borrador", "grupo") else {a["id"]}
        huella = self._huella_arrastre(a)
        malas = self._solapa(huella, propios)
        if malas or tipo not in ("marco", "grupo"):
            return malas
        if tipo == "grupo":
            huella = self._marcos_grupo(a)
            propios.update(a.get("marcos", []))
        cajas = geo_choques.solapa_marcos([Rect(*r.getRect()) for r in huella], cajas_parciales(self.M), propios)
        return [QRectF(*r) for r in cajas]

    def _hay_solape(self, a: dict[str, Any]) -> bool:
        return bool(self._malas_arrastre(a))

    def _huella_ficha(self, tipo: str, p: QPointF) -> list[QRectF]:
        x, y = self._esquina_parcial(p) if tipo == "parcial" else self._modelo(p)
        caja = geo_choques.huella_ficha(tipo, x, y)
        if caja is None:
            return []
        if (
            (tipo == "accion" or tipo.startswith("accion:") or tipo == "forzado")
            and self._buscar_iman([], x, y, ACT_MIN)
        ):
            return []
        qt = QRectF(*caja)
        malas = self._solapa([qt], set())
        if not malas and tipo == "parcial":
            if geo_choques.solapa_marcos([caja], cajas_parciales(self.M), margen=MARGEN_SOLAPE):
                return [qt]
        return malas

    @staticmethod
    def _toca(a: QRectF, b: QRectF) -> bool:
        return geo_choques.toca(Rect(*a.getRect()), Rect(*b.getRect()))

    def _libre(self, zona: QRectF) -> bool:
        """Si la zona del dibujo no toca ningún elemento (etapas, macroetapas, transiciones, barras, acciones) ni marco."""
        rect = Rect(*zona.getRect())
        if any(geo_choques.toca(rect, r) for _, r, _ in self._elementos_geometricos()):
            return False
        return not geo_choques.solapa_marcos([rect], cajas_parciales(self.M))

    def _columna_expansion(self, x: int, y: int) -> int | None:
        return geo_choques.columna_expansion(x, y, lambda zona: self._libre(QRectF(*zona)))

    def _esquina_parcial(self, p: QPointF) -> tuple[int, int]:
        """La esquina superior izquierda (x, y del modelo, en la rejilla) del marco de un grafcet parcial nuevo soltado en p: el
        marco queda centrado en el punto, como una etapa."""
        return esquina_parcial(p.toTuple())

    def _posiciones_modelo(self) -> dict[str, tuple[float, float]]:
        return geo_equidistancia.posiciones_modelo(self.M)

    def _extensiones(self) -> dict[str, tuple[float, float]]:
        return geo_equidistancia.extensiones(self.M, _Pintor.ancho)

    def _pares_solape(self, propios: set[str], sin_horizontales: bool = False) -> set[tuple[str, str]]:
        return geo_choques.pares_solape(
            self.M, propios, sin_horizontales, _Pintor.ancho, medida_comentario, self._alto_minimo_barra,
        )

    def equidistanciar(self, ids: list[str] | None = None) -> list[str] | None:
        """«Equidistanciar alturas de la cadena», «…de la selección» o «…de todo el lienzo» (con `ids` None):
        `Editor.equidistribute` con la distancia estándar DY entre etapas y transiciones, que aumenta donde las acciones de
        una etapa lo piden (`_extensiones`). Una sola operación de deshacer, solo presentación: el modelo no cambia. Si con
        ello algo quedara encima de otro elemento que antes no tocaba, no cambia nada y se avisa. Devuelve los ID de lo que
        se movió (vacío si ya estaba así, o no hay cadenas), o None si se rechazó."""
        self.reconstruir()
        pos = self._posiciones_modelo()
        cadenas = self.ed.chains(ids, pos)
        if not cadenas:
            self.informar("No hay una cadena de elementos enlazados que equidistanciar")
            self.cambiado.emit()
            return []
        propios = {i for c in cadenas for i in c}
        antes, sucio = self._pares_solape(propios, True), self.ed.dirty
        movidos: list[str] = []

        def hacer() -> None:
            extensiones = self._extensiones()
            movidos.extend(geo_equidistancia.equidistribuir(
                self.ed, self.M, ids, pos, extensiones, DY, MARGEN_SOLAPE, REJILLA,
            ))
            self.reconstruir()
            if self._pares_solape(propios, True) - antes:
                raise DiagnosticError(Diagnostic("D-FORMATO", MSG_EQUIDISTANCIA))
        # La vista ya es la de ahora al empezar (arriba) y al acabar `hacer`; el refresco de la ventana, uno solo, tras el mensaje.
        motivo = self._atomico("equidistanciar alturas", hacer, hueco=False, vista_actual=True, vista_al_final=True, emitir=False)
        if motivo:
            self.ed.dirty = sucio  # lo que se deshizo no cuenta como un cambio sin guardar
            self.mensaje = motivo
            self.cambiado.emit()
            return None
        self.informar("Alturas equidistanciadas" if movidos else "Las alturas ya estaban equidistanciadas")
        self.cambiado.emit()
        return movidos
