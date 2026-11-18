"""Historial de una apertura de Propiedades."""


class SesionPropiedades:
    def __init__(self, edicion):
        self.edicion = edicion
        editor = edicion.ed
        self.anteriores = len(editor.undo_stack)
        self.rehacer = list(editor.redo_stack)
        self.sucio = editor.dirty

    def terminar(self, confirmar):
        if confirmar:
            return
        editor = self.edicion.ed
        cambios = editor.undo_stack[self.anteriores:]
        if not cambios:
            return
        agrupado = ("Propiedades", cambios[0][1], cambios[-1][2])
        editor.undo_stack[self.anteriores:] = [agrupado]
        editor.undo()
        editor.redo_stack[:] = self.rehacer
        editor.dirty = self.sucio
        self.edicion.cambia()
