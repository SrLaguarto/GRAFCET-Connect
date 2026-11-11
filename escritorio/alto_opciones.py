"""Alto mínimo del panel de opciones al seleccionar una transición.

Con una transición seleccionada, el panel inferior debe enseñar entera la paleta de operadores de la receptividad
(y, o, no, ( ), flanco ↑, flanco ↓), sin barra de desplazamiento, y debajo la fila «Fórmula». Aquí se calcula ese alto y
se agranda el panel si es menor; si el usuario lo ha hecho mayor, no se toca. Dos límites (P1 y P11): con la ventana baja
(< 560 px) la paleta va en una fila y el panel pide mucho menos; y el panel nunca pasa del 55 % del alto de la ventana
(con un mínimo que deja ver una fila de campos): lo que no cabe se desplaza dentro del panel.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .bloques import PaletaBloques, Programador

if TYPE_CHECKING:
    from .propiedades import PanelPropiedades
    from .ventana import Ventana

TOPE_PROPORCIONAL = 0.55  # el panel inferior, como mucho, el 55 % del alto de la ventana
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
    y la fila «Fórmula» debajo. Con la ventana baja (`Programador.modo_fila`) la paleta va en una fila: ≈ 190 px."""
    programador = props.prog
    franja = 0 if programador.cat_en_cabecera else programador._sc_carpetas.height() + programador.layout().spacing()  # (en la cabecera no gastan alto)
    if programador.en_fila:  # la fila de la paleta y, debajo, al menos una línea del área (que se desplaza si hace falta)
        paleta = programador._sc_paleta.height() + programador._lay_cuerpo.spacing() + programador.lienzo.minimumHeight()
    else:
        paleta = alto_operadores()
    extra = max(0, franja + paleta - ALTO_BASE_PROGRAMADOR)
    return props.minimumSizeHint().height() + extra


def tope_alto(ventana: Ventana) -> int:
    """El panel inferior no pasa de `TOPE_PROPORCIONAL` del alto de la ventana, y nunca baja de lo que deja ver una fila de campos (P11):
    lo que no cabe se desplaza dentro del panel. A 768 px son ≈ 422 px: no cambia nada visible."""
    return max(int(ventana.height() * TOPE_PROPORCIONAL), ventana.props.minimumSizeHint().height())


def agrandar_para_transicion(ventana: Ventana) -> None:
    """Si hay una transición seleccionada y el panel inferior es más bajo que su mínimo (con el tope de `tope_alto`), lo agranda (cede el dibujo).
    Si no hay nada con opciones (nada, o varios elementos), el panel mide solo lo que pide su contenido y, mientras el usuario no haya movido el
    divisor, se encoge a eso: sin bandas vacías."""
    if ventana.modo != "editar" or ventana.inferior.isHidden():
        return
    if ventana.props.pagina == "vacio":
        if getattr(ventana, "_opciones_automaticas", True):
            minimo = max(ventana._minimo_panel("inferior"), ventana.props.minimumSizeHint().height())
            arriba, abajo = ventana.vsplit.sizes()
            if abajo > minimo:
                ventana.vsplit.setSizes([arriba + abajo - minimo, minimo])
        return
    if ventana.props.pagina != "transicion":
        return
    minimo = min(alto_minimo_transicion(ventana.props), tope_alto(ventana))
    arriba, abajo = ventana.vsplit.sizes()
    if abajo < minimo:
        ventana.vsplit.setSizes([max(arriba - (minimo - abajo), 120), minimo])
