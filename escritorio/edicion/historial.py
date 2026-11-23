"""Operaciones atómicas, deshacer, rehacer y restauración de la selección."""
from __future__ import annotations

from typing import Any, Callable
from grafcet.diagnostics import DiagnosticError
from .constantes import MSG_ENCIMA


class _Historial:
    def _atomico(
        self, etiqueta: str, fn: Callable[[], Any], hueco: bool = True, vista_actual: bool = False,
        antes_de_notificar: Callable[[], None] | None = None, vista_al_final: bool = False, emitir: bool = True,
    ) -> str | None:
        """Varias operaciones como una sola de deshacer; si una falla, no queda ninguna y se devuelve el motivo. Con `hueco`
        (lo normal), lo que ensanchó o añadió acciones aparta lo que estorba; sin él, la operación ya cuida de dónde pone
        las cosas."""
        n, rehacer = len(self.ed.undo_stack), list(self.ed.redo_stack)
        self._encima = []
        try:
            with self.ed.group(etiqueta):
                if not vista_actual:
                    self.reconstruir()
                antes = self._firmas() if hueco else {}
                fn()
                self._encima = self._asegurar_hueco(antes) if hueco else []  # lo que ensanchó o añadió acciones aparta lo que estorba
        except DiagnosticError as exc:
            self._encima = []
            while len(self.ed.undo_stack) > n:
                self.ed.undo()
            self.ed.redo_stack[:] = rehacer  # (como estaba, aunque fn haya hecho varias operaciones)
            self.reconstruir()  # (una operación pudo haber rehecho la vista a medias)
            return "; ".join(self.sust(d.message) for d in exc.diagnostics)
        if antes_de_notificar is not None:
            antes_de_notificar()
        # `vista_al_final`: `fn` ya dejó la vista como queda (acabó con `reconstruir`); `emitir` falso: quien llama emite él, tras su mensaje
        # Con `hueco`, `_asegurar_hueco` acaba con la vista rehecha (y `_despejar` la rehace tras cada desplazamiento): rehacerla otra vez
        # daría la misma, salvo que `antes_de_notificar` toque el modelo o las posiciones. Cada `reconstruir` cuesta ~0,75 s en un proyecto de 108 etapas.
        self.cambia(reconstruir=not ((hueco and (vista_actual or antes_de_notificar is None)) or vista_al_final), emitir=emitir)
        if self._encima:  # no se pudo abrir hueco: se deja como está, con un aviso que no es un error
            self.informar(MSG_ENCIMA)
            self.parpadear(self._encima)
        return None

    def deshacer(self) -> str | None:
        if not self.ed.undo_stack:
            return None
        label = self.ed.undo()
        self._seleccion_suelta()
        self.cambia()
        return label

    def _seleccion_suelta(self) -> None:
        """Tras deshacer o rehacer, si la acción señalada ha quedado suelta (se deshizo su unión a la etapa), lo seleccionado es ella, como
        al soltarla: así vuelve a decir cómo unirla (`texto_estado`)."""
        if self.accion is not None and any(b["id"] == self.accion and not b.get("etapa") and b.get("tipo") != "forzado"
                                           for b in self.ed.draft_actions()):
            self.sel, self.accion = [self.accion], None

    def rehacer(self) -> str | None:
        if not self.ed.redo_stack:
            return None
        label = self.ed.redo()
        self._seleccion_suelta()
        self.cambia()
        return label
