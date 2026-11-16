"""Los diálogos nuevos toman la escala actual, en vez de la hoja inicial de la ventana."""
from . import estilo


def aplicar_escala_dialogo(dialogo):
    dialogo.setStyleSheet(estilo.hoja_global() + dialogo.styleSheet())
