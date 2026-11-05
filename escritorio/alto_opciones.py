"""Alto mínimo del panel de opciones al seleccionar una transición.

Con una transición seleccionada, el panel inferior debe enseñar entera la paleta de operadores de la receptividad
(y, o, no, ( ), flanco ↑, flanco ↓), sin barra de desplazamiento, y debajo la fila «Fórmula». Aquí se calcula ese alto y
se agranda el panel si es menor; si el usuario lo ha hecho mayor, no se toca.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .bloques import PaletaBloques, Programador

if TYPE_CHECKING:
    from .propiedades import PanelPropiedades
    from .ventana import Ventana

MARGEN_PALETA = 4  # px de más sobre el alto de la paleta (su marco)
ALTO_BASE_PROGRAMADOR = 116  # el alto mínimo con el que el programador entra en el diseño del panel
_sondas: dict[str, PaletaBloques] = {}


def alto_operadores() -> int:
    """El alto de la columna de bloques de la categoría «Operadores» (la medida no depende del modelo)."""
    sonda = _sondas.get("operador")
    if sonda is None:
        sonda = PaletaBloques(lambda: ({}, []), columna=True)
        sonda.cargar("operador")
        _sondas["operador"] = sonda
    return sonda.heightForWidth(Programador.PALETA_MAX - 16) + MARGEN_PALETA


def alto_minimo_transicion(props: PanelPropiedades) -> int:
    """El alto del panel de opciones para que la paleta de operadores se vea entera, con la franja de categorías encima
    y la fila «Fórmula» debajo."""
    programador = props.prog
    franja = programador._sc_carpetas.height() + programador.layout().spacing()
    extra = max(0, franja + alto_operadores() - ALTO_BASE_PROGRAMADOR)
    return props.minimumSizeHint().height() + extra


def agrandar_para_transicion(ventana: Ventana) -> None:
    """Si hay una transición seleccionada y el panel inferior es más bajo que su mínimo, lo agranda (cede el dibujo)."""
    if ventana.modo != "editar" or ventana.inferior.isHidden() or ventana.props.pagina != "transicion":
        return
    minimo = alto_minimo_transicion(ventana.props)
    arriba, abajo = ventana.vsplit.sizes()
    if abajo < minimo:
        ventana.vsplit.setSizes([max(arriba - (minimo - abajo), 120), minimo])
