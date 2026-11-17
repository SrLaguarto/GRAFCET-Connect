"""El nombre de una macroetapa se edita; el resto de su caja navega a la expansión."""
from PySide6.QtWidgets import QGraphicsTextItem


def doble_macro(editor, identidad, punto):
    nombre = editor.nombre(identidad)
    textos = editor.diagrama.scene().items(punto) if editor.diagrama is not None else []
    en_nombre = any(isinstance(item, QGraphicsTextItem) and item.toPlainText() == nombre for item in textos)
    if en_nombre:
        editor.renombrar_macro(identidad)
    else:
        editor.encuadrar_expansion(identidad)
