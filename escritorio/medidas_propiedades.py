"""Ancho de Propiedades referido a media pantalla, con los tokens de maquetación."""
from . import estilo


def margen_horizontal(ancho):
    return max(2 * estilo.E6, ancho // (16 * estilo.E2) * estilo.E2)


def ancho_maximo():
    # 60 unidades E4 son la ventana de referencia de 960 px lógicos.
    # El responsable mantiene el mismo ancho al pasar a letra grande; el DPI lo escala Qt.
    referencia = 60 * estilo.E4
    return referencia - 2 * margen_horizontal(referencia)
