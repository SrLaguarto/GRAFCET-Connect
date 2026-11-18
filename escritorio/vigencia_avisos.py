"""Un aviso de operación caduca al cambiar el documento, nunca al mover el ratón."""


class VigenciaAviso:
    def __init__(self, editor):
        self.editor = editor
        self.asiento = None
        self.rehacer = 0
        self.registrar()

    def registrar(self):
        self.asiento = self.editor.undo_stack[-1] if self.editor.undo_stack else None
        self.rehacer = len(self.editor.redo_stack)

    def cambio(self):
        asiento = self.editor.undo_stack[-1] if self.editor.undo_stack else None
        distinto = asiento is not self.asiento or len(self.editor.redo_stack) != self.rehacer
        self.registrar()
        return distinto


def seleccion_actual(edicion):
    return tuple(edicion.sel), edicion.accion


def texto_seleccion(edicion):
    ids = [edicion.accion] if edicion.accion else edicion.sel
    if not ids:
        return ""
    if len(ids) != 1:
        return "Selección: " + ", ".join(edicion.nombre(i) for i in ids)
    ident = ids[0]
    descripcion = edicion.descripcion_jerarquia(ident)
    if descripcion:
        if edicion._es_parcial_suelto(ident):
            descripcion += (": suelte etapas y transiciones dentro de su marco para rellenarlo; una orden de "
                            "forzado de otra etapa puede forzarlo («Forzado» en la paleta).")
        return descripcion
    borrador = next((b for b in edicion.ed.draft_actions() if b["id"] == ident), None)
    if borrador and not borrador.get("etapa"):
        from .edicion import MSG_ACCION_SUELTA
        return MSG_ACCION_SUELTA
    return edicion.nombre(ident)


def texto_estado(edicion):
    if edicion.seleccion_aviso != seleccion_actual(edicion):
        edicion._mensaje, edicion.mensaje_info = "", False
    if edicion._mensaje:
        return edicion._mensaje, edicion.mensaje_info
    return texto_seleccion(edicion), True


def presentar_estado(ventana, mensaje, info):
    from . import estilo
    ventana.ayuda.setText(mensaje)
    ventana.ayuda.setToolTip(mensaje)
    ventana.ayuda.setVisible(bool(mensaje))
    error = bool(mensaje) and not info
    ventana.ayuda.setStyleSheet(
        f"color: {estilo.ERROR if error else estilo.TINTA_2}; font-weight: {600 if error else 400}; "
        f"font-size: {estilo.T_PEQUENA}px")
    ventana.ayuda_pantalla.actualizar(mensaje, ventana.ayuda.width())
    barra = ventana.statusBar()
    if mensaje:
        barra.showMessage(mensaje)
    else:
        barra.clearMessage()
