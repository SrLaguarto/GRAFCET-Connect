"""Sistema de estilo de la interfaz de GRAFCET Connect: tokens (color, ritmo de espaciado, radios, tipografía, alturas de
control), iconos de un mismo trazo y la hoja de estilo global que se genera a partir de ellos.

Identidad: tinta azul marino sobre papel gris frío, con un único acento petróleo para lo accionable y un verde de
«máquina en marcha» reservado a la simulación. El dibujo del grafcet (`diagrama.COL`) no se toca: sigue en negro sobre
blanco, con la etapa activa en `#40d641` y la selección en azul (P-IMP-77); el rojo queda solo para errores y el ámbar para
avisos (P-IMP-89). Contrastes comprobados con `propuesta/herramientas/contrastes.py`: texto 4,5:1 o más y bordes de control
3:1 o más sobre sus fondos.

Todo lo que dibuja la interfaz (no el lienzo) toma de aquí sus colores. Los módulos no deben escribir colores en hexadecimal:
usan estos nombres, o las propiedades dinámicas que la hoja global conoce (`modo`, `estadoLuz`, `activa`, `primario`…).
"""
from __future__ import annotations

from string import Template

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# -- color ----------------------------------------------------------------------------------------------------------
TINTA = "#16263a"          # texto principal (15,3:1 sobre blanco)
TINTA_2 = "#4a5b6e"        # texto secundario (7:1)
TINTA_3 = "#5b6b7d"        # ayudas y rótulos discretos (4,9:1 sobre el fondo de la ventana)
BLANCO = "white"
FONDO = "#eef2f6"          # fondo de la ventana
SUPERFICIE = "#ffffff"     # tarjetas y paneles
SUPERFICIE_2 = "#f6f8fb"   # cabeceras de tabla, zonas hundidas
BORDE = "#cdd6e0"          # separadores y marcos decorativos
BORDE_CONTROL = "#7b8a9c"  # borde de un control (3,5:1 sobre blanco)
DESHABILITADO = "#7c8896"  # texto de lo no disponible (la norma exime de contraste a lo deshabilitado)
HOVER = "#e4ecf3"          # pasar el puntero por un control sin relleno
PULSADO = "#d3dfea"

ACENTO = "#0b6e75"         # petróleo: lo accionable, un solo acento por zona (6:1 con texto blanco)
ACENTO_OSCURO = "#095259"
ACENTO_HOVER = "#0d8189"
ACENTO_SUAVE = "#cfeee6"   # relleno de lo seleccionado o activo (menta; una prueba fija este tono en el icono marcado)
ACENTO_BORDE = "#8fcdd1"

EDICION = "#27415f"        # azul tinta: el programa está en edición (blanco encima: 10,5:1)
SIMULACION = "#157a35"     # verde máquina: simulación en marcha (blanco encima: 5,4:1)
SIMULACION_SUAVE = "#e3f4e8"
SIMULACION_BORDE = "#8cc9a0"

OK = "#17803d"
AVISO = "#8a5a00"          # texto ámbar sobre fondo claro (5,4:1)
AVISO_FONDO = "#fff4d6"
AVISO_BORDE = "#e3b74a"
ERROR = "#c62828"          # solo errores (el mismo del dibujo)
ERROR_FONDO = "#fdecea"
FOCO = TINTA               # el foco de teclado: trazo discontinuo de 2 px
CONFIRMAR = "#27665c"      # botón de confirmar de la franja de selección de PLANOS (P-IMP planos)

MESA = "#dfe5eb"           # el tablero sobre el que se ve una hoja de PLANOS o una plantilla (no es parte del dibujo)

LUZ = {"conectada": "#17803d", "desconectada": "#6f7f92", "error": "#c62828"}  # punto de la conexión externa

# -- espaciado (ritmo de 4 y 8), radios, tipografía, alturas -------------------------------------------------------
E1, E2, E3, E4, E6 = 4, 8, 12, 16, 24
R_S, R_M, R_L = 4, 8, 12
FUENTE = "Segoe UI"
T_BASE, T_PEQUENA, T_TITULO, T_SECCION, T_CHIP = 13, 12, 16, 14, 13
ALTO_CONTROL = 36          # objetivo táctil principal (ideal 36-40)
ALTO_CONTROL_COMPACTO = 32  # mínimo táctil, cuando falta alto
ALTO_BARRA = 34            # botones de las barras de herramientas (el presupuesto de alto sobre el dibujo no admite 36)
ALTO_BARRA_COMPACTA = 32
ALTO_FILA = 30             # filas de tablas y listas
ALTO_FILA_COMPACTA = 28
ANCHO_BARRA = 12           # barras de desplazamiento


# -- modo compacto --------------------------------------------------------------------------------------------------
UMBRAL_ANCHO = 1000  # por debajo: pantalla partida (los paneles laterales se compactan)
UMBRAL_ALTO = 560    # por debajo: un cuarto de pantalla (se estrechan cabeceras y márgenes)


def tamano_compacto(ancho: int, alto: int) -> tuple[bool, bool]:
    """(compacto en ancho, compacto en alto) para el tamaño de la ventana."""
    return ancho < UMBRAL_ANCHO, alto < UMBRAL_ALTO


# -- hoja de estilo global ------------------------------------------------------------------------------------------
def _familia(selectores: str, alto: int, pad_h: int, extra: str = "", pad_extra: tuple[int, int] = (0, 0)) -> str:
    """Un control de `alto` px con borde de 1 px y, con el foco, borde discontinuo de 2 px que no mueve nada: el relleno y el
    alto de contenido compensan el borde que crece (y `pad_extra`, el hueco de una flecha, p. ej. de un desplegable)."""
    selectores_foco = ", ".join(f"{s}:focus" for s in (x.strip() for x in selectores.split(",")))
    return (f"{selectores} {{ min-height:{alto - 2}px; padding:0 {pad_h + pad_extra[0]}px 0 {pad_h}px; {extra} }}\n"
            f"{selectores_foco} {{ border:2px dashed {FOCO}; min-height:{alto - 4}px; "
            f"padding:0 {pad_h - 1 + pad_extra[0]}px 0 {pad_h - 1}px; }}\n")


_PLANTILLA = Template("""
QWidget { font-family:"$fuente"; font-size:${t_base}px; color:$tinta; }
QMainWindow, QDialog { background:$fondo; }
QToolTip { background:$tinta; color:$blanco; border:0; padding:6px 8px; }
QWidget#panelDibujo, QWidget#panelElementos, QWidget#panelVariables,
QWidget#panelPropiedades { background:$superficie; border:1px solid $borde; border-radius:${r_m}px; }
QLabel#tituloPanel { font-size:${t_titulo}px; font-weight:600; color:$tinta; border:0; }
QWidget#cabeceraPropiedades { background:$superficie_2; border-radius:${r_s}px; }
QLabel#tituloPropiedades { color:$acento; font-size:${t_seccion}px; font-weight:600; background:transparent; padding:3px 0; }
QLabel#ayudaPropiedades { color:$tinta_3; padding:4px 8px; }

QMenuBar { background:$superficie; padding:0 8px; border-bottom:1px solid $borde; }
QMenuBar::item { padding:${pad_menu}px 12px; border-radius:${r_s}px; }
QMenuBar::item:selected, QMenu::item:selected { background:$acento_suave; color:$tinta; }
QMenu { background:$superficie; border:1px solid $borde_control; padding:4px; }
QMenu::item { padding:${pad_item}px 28px ${pad_item}px 24px; border-radius:${r_s}px; }
QMenu::item:disabled { color:$deshabilitado; }
QMenu::separator { height:1px; background:$borde; margin:4px 8px; }

QWidget#filaPestanas { background:$fondo_pestanas; }
QWidget#filaPestanas[fusion="true"] { border-bottom:1px solid $borde; }
QWidget#filaPestanas[fusion="true"][modo="simular"] { background:$simulacion_suave; border-bottom:3px solid $simulacion; }
QWidget#herramientasGrafcet[fusion="true"], QWidget#herramientasGrafcet[fusion="true"][modo="simular"] { background:transparent; border:0; }
QTabBar#pestanasVistas { background:transparent; border:0; }
QTabBar#pestanasVistas::tab { padding:${pad_tab}px 20px; margin:4px 4px 0 0; background:transparent;
    color:$tinta_2; border:2px solid transparent; border-bottom:3px solid transparent; font-weight:600; border-top-left-radius:${r_m}px; border-top-right-radius:${r_m}px; }
QTabBar#pestanasVistas::tab:selected { background:$superficie; color:$tinta; border-bottom:3px solid $acento; }
QTabBar#pestanasVistas::tab:hover:!selected { background:$hover; color:$tinta; }
QTabBar#pestanasVistas::tab:disabled { color:$deshabilitado; }
QTabBar#pestanasVistas::tab:selected:focus { border:2px dashed $foco; border-bottom:3px solid $acento; }

QWidget#bandaModo { background:$edicion; border-top-left-radius:${r_m}px; border-top-right-radius:${r_m}px; }
QWidget#bandaModo[modo="simular"] { background:$simulacion; }
QToolButton#luzES { border:1px solid $borde_control; border-radius:${radio_pastilla}px; background:$superficie; color:$tinta;
    padding:0 14px 0 10px; min-height:${alto_pastilla}px; font-weight:600; }
QToolButton#luzES:hover { background:$hover; border-color:$tinta_2; }
QToolButton#luzES:pressed { background:$pulsado; }
QToolButton#luzES:focus { border:2px dashed $foco; padding:0 13px 0 9px; min-height:${alto_pastilla_foco}px; }
QToolButton#luzES[estadoLuz="conectada"] { border:1px solid $ok; }
QToolButton#luzES[estadoLuz="error"] { background:$error_fondo; border:2px solid $error; padding:0 13px 0 9px; min-height:${alto_pastilla_foco}px; }
QToolButton#luzES[abierta="true"] { background:$acento_suave; border:2px solid $acento; padding:0 13px 0 9px; min-height:${alto_pastilla_foco}px; }
QWidget#herramientasGrafcet { background:$superficie; border-bottom:1px solid $borde; }
QWidget#herramientasGrafcet[modo="simular"] { background:$simulacion_suave; border-bottom:3px solid $simulacion; }
QToolBar { background:transparent; border:0; spacing:8px; padding:0; margin:0; }
QToolBar QToolButton { min-height:${alto_tb_c}px; padding:0 12px; border:1px solid transparent; border-radius:${r_s}px; color:$tinta; background:transparent; }
QToolBar QToolButton:hover { background:$hover; border-color:$borde; }
QToolBar QToolButton:pressed { background:$pulsado; }
QToolBar QToolButton:checked { background:$acento_suave; border-color:$acento; color:$tinta; }
QToolBar QToolButton:disabled { color:$deshabilitado; background:transparent; border-color:transparent; }
QToolBar QToolButton:focus { border:2px dashed $foco; min-height:${alto_tb_f}px; padding:0 11px; }
QToolBar::separator { width:1px; background:$borde; margin:6px 4px; }
QToolBar#barraSimulacion QToolButton#botonReiniciar { background:$superficie; border:1px solid $borde_control; }
QToolBar#barraSimulacion QToolButton#botonReiniciar:hover { background:$hover; }
QToolBar#barraSimulacion QToolButton#botonReiniciar:pressed { background:$pulsado; }
QToolBar#barraSimulacion QToolButton#botonReiniciar:disabled { border-color:$borde; }
QToolBar#barraSimulacion QToolButton#botonReiniciar:focus { border:2px dashed $foco; }
QToolBar#barraSimulacion QToolButton#botonPlay { background:$acento; color:$blanco; border:1px solid $acento_oscuro; font-weight:700;
    padding:0 18px 0 14px; min-width:92px; }
QToolBar#barraSimulacion QToolButton#botonPlay:hover { background:$acento_hover; }
QToolBar#barraSimulacion QToolButton#botonPlay:pressed { background:$acento_oscuro; }
QToolBar#barraSimulacion QToolButton#botonPlay:checked { background:$tinta; border-color:$tinta; color:$blanco; }
QToolBar#barraSimulacion QToolButton#botonPlay:disabled { background:$pulsado; color:$deshabilitado; border-color:$borde; }
QToolBar#barraSimulacion QToolButton#botonPlay:focus { border:2px dashed $blanco; padding:0 17px 0 13px; }
QToolBar#barraEdicion QToolButton, QToolBar#barraVista QToolButton { background:$superficie; border:1px solid $borde_control; min-width:${alto_tb}px; padding:0 8px; }
QToolBar#barraEdicion QToolButton:hover, QToolBar#barraVista QToolButton:hover { background:$hover; border-color:$tinta_2; }
QToolBar#barraEdicion QToolButton:pressed, QToolBar#barraVista QToolButton:pressed { background:$pulsado; }
QToolBar#barraEdicion QToolButton:checked, QToolBar#barraVista QToolButton:checked { background:$acento_suave; border:2px solid $acento; padding:0 7px; }
QToolBar#barraEdicion QToolButton:disabled, QToolBar#barraVista QToolButton:disabled { background:$superficie_2; border-color:$borde; }
QToolBar#barraEdicion QToolButton:focus, QToolBar#barraVista QToolButton:focus { border:2px dashed $foco; padding:0 7px; }
QToolBar#barraPlanos { padding:2px 0; spacing:4px; }
QToolBar#barraPlanos QToolButton { background:$superficie; border:1px solid $borde_control; padding:0 10px; }
QToolBar#barraPlanos QToolButton#bibliotecaPlanos { padding:0 32px 0 10px; }
QToolBar#barraPlanos QToolButton:hover { background:$hover; border-color:$tinta_2; }
QToolBar#barraPlanos QToolButton:pressed { background:$pulsado; }
QToolBar#barraPlanos QToolButton:checked { background:$acento_suave; border:2px solid $acento; padding:0 9px; }
QToolBar#barraPlanos QToolButton:disabled { background:$superficie_2; border-color:$borde; }
QToolBar#barraPlanos QToolButton:focus { border:2px dashed $foco; padding:0 9px; }
QToolBar#barraConexion QToolButton { border:1px solid $acento_borde; background:$superficie; color:$acento; }
QToolButton#bibliotecaPlanos { padding-right:28px; }
QToolButton#bibliotecaPlanos::menu-indicator { image:url(:/grafconnect/desplegar.svg); subcontrol-origin:padding; subcontrol-position:center right; right:8px; width:12px; height:8px; }

QLineEdit, QComboBox { background:$superficie; border:1px solid $borde_control; border-radius:${r_s}px;
    selection-background-color:$acento; selection-color:$blanco; }
QLineEdit:disabled, QComboBox:disabled { background:$superficie_2; border-color:$borde; color:$deshabilitado; }
QLineEdit[readOnly="true"] { background:$superficie_2; }
$familia_entradas
QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; width:24px; border:0; background:transparent; }
QComboBox::down-arrow { image:url(:/grafconnect/desplegar.svg); width:12px; height:8px; }
QComboBox QAbstractItemView { background:$superficie; border:1px solid $borde_control; selection-background-color:$acento_suave; selection-color:$tinta; outline:0; }
QComboBox QAbstractItemView::item { min-height:${alto_fila}px; padding:0 8px; }

QPushButton { background:$superficie; border:1px solid $borde_control; border-radius:${r_s}px; color:$tinta; }
$familia_botones
QPushButton:hover { background:$hover; border-color:$tinta_2; }
QPushButton:pressed { background:$pulsado; }
QPushButton:checked { background:$acento_suave; border-color:$acento; }
QPushButton:disabled, QToolButton:disabled { color:$deshabilitado; }
QPushButton:disabled { border-color:$borde; background:$superficie_2; }
QPushButton[primario="true"] { background:$acento; color:$blanco; border-color:$acento_oscuro; font-weight:600; }
QPushButton[primario="true"]:hover { background:$acento_hover; border-color:$acento_oscuro; }
QPushButton[primario="true"]:pressed { background:$acento_oscuro; }
QPushButton[primario="true"]:focus { border:2px dashed $blanco; }
QPushButton[primario="true"]:disabled { background:$pulsado; color:$deshabilitado; border-color:$borde; }
QPushButton[entrada="true"] { text-align:left; padding-left:12px; font-weight:600; }
QPushButton[entrada="true"][activa="true"] { background:$acento_suave; border:2px solid $acento; color:$tinta; }
QPushButton[entrada="true"]:disabled { background:$superficie_2; color:$deshabilitado; }
QPushButton[entrada="true"][activa="true"]:disabled { background:$acento_suave; border:2px solid $acento_borde; color:$tinta_2; }
QToolButton { border:1px solid transparent; border-radius:${r_s}px; background:transparent; }
QToolButton:hover { background:$hover; }
QToolButton:pressed { background:$pulsado; }
QToolButton:checked { background:$acento_suave; border-color:$acento; }
QToolButton:focus { border:2px dashed $foco; }
QCheckBox, QRadioButton { spacing:8px; min-height:${alto_menos}px; }
QCheckBox:focus, QRadioButton:focus { border:2px dashed $foco; border-radius:${r_s}px; }
QListWidget:focus, QTableWidget:focus, QTreeWidget:focus, QTextEdit:focus, QPlainTextEdit:focus { border:2px dashed $foco; }
QGraphicsView:focus { border:2px dashed $foco; }
QGraphicsView { border:2px solid transparent; }

QGroupBox { background:$superficie; border:0; margin-top:26px; font-size:${t_seccion}px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; padding:3px 6px; color:$acento; }
QGroupBox#grupoVariables { font-size:${t_titulo}px; }
QGroupBox#grupoVariables::title { color:$tinta; }
QGroupBox QLabel, QGroupBox QPushButton, QGroupBox QTableWidget, QGroupBox QLineEdit, QGroupBox QComboBox, QGroupBox QCheckBox { font-weight:400; font-size:${t_base}px; }
QTableWidget, QListWidget, QTreeWidget { background:$superficie; border:2px solid transparent; gridline-color:$borde; alternate-background-color:$superficie_2;
    selection-background-color:$acento_suave; selection-color:$tinta; outline:0; }
QListWidget#paletaElementos::item { padding-left:7px; border:0; }
QListWidget#paletaElementos::item:hover { background:$hover; }
QListWidget#paletaElementos QScrollBar:vertical { width: 9px; }  /* la paleta mide justo dos columnas de fichas */
QHeaderView::section { background:$superficie_2; border:0; border-bottom:1px solid $borde; padding:6px 6px; color:$tinta_2; font-weight:600; }
QScrollArea { border:0; background:transparent; }
QScrollBar:horizontal { height: ${ancho_barra}px; background:$borde; margin:0; border-radius:6px; }
QScrollBar::handle:horizontal { background:$borde_control; min-width:36px; border-radius:5px; margin:1px; }
QScrollBar::handle:horizontal:hover { background:$tinta_2; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:transparent; }
QScrollBar:vertical { width: ${ancho_barra}px; background:$borde; margin:0; border-radius:6px; }
QScrollBar::handle:vertical { background:$borde_control; min-height:36px; border-radius:5px; margin:1px; }
QScrollBar::handle:vertical:hover { background:$tinta_2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QSplitter::handle { background:$fondo; }
QStatusBar { background:$fondo; color:$tinta_2; font-size:${t_pequena}px; }
QStatusBar::item { border:0; }
QProgressBar { border:1px solid $borde_control; border-radius:${r_s}px; background:$superficie; text-align:center; }
QProgressBar::chunk { background:$acento; }
""")


def hoja_global(compacto_alto: bool = False) -> str:
    """La hoja de estilo de la ventana. La ventana usa siempre la de alturas normales (cambiarla al vuelo cuesta cerca de un
    segundo); `compacto_alto` baja las alturas de control a 32 px y queda para herramientas y maquetas."""
    alto = ALTO_CONTROL_COMPACTO if compacto_alto else ALTO_CONTROL
    alto_tb = ALTO_BARRA_COMPACTA if compacto_alto else ALTO_BARRA  # botones de las barras: 34 px, o 32 en un cuarto de pantalla
    t = dict(
        fuente=FUENTE, t_base=T_BASE, t_pequena=T_PEQUENA, t_titulo=T_TITULO, t_seccion=T_SECCION,
        tinta=TINTA, tinta_2=TINTA_2, tinta_3=TINTA_3, blanco=BLANCO, fondo=FONDO, superficie=SUPERFICIE,
        superficie_2=SUPERFICIE_2, borde=BORDE, borde_control=BORDE_CONTROL, deshabilitado=DESHABILITADO, hover=HOVER,
        pulsado=PULSADO, acento=ACENTO, acento_oscuro=ACENTO_OSCURO, acento_hover=ACENTO_HOVER, acento_suave=ACENTO_SUAVE,
        acento_borde=ACENTO_BORDE, simulacion=SIMULACION, simulacion_suave=SIMULACION_SUAVE, foco=FOCO,
        r_s=R_S, r_m=R_M, fondo_pestanas=FONDO, edicion=EDICION, ok=OK, error=ERROR, error_fondo=ERROR_FONDO,
        radio_pastilla=alto_tb // 2, alto_pastilla=alto_tb - 5, alto_pastilla_foco=alto_tb - 7, alto_tb=alto_tb, alto_tb_c=alto_tb - 5, alto_tb_f=alto_tb - 7,
        pad_menu=3 if compacto_alto else 4, pad_item=6 if compacto_alto else 8,
        pad_tab=3 if not compacto_alto else 2, pad_barra=2 if compacto_alto else 4, alto_menos=alto - 2, alto_menos4=alto - 4,
        alto_fila=ALTO_FILA_COMPACTA if compacto_alto else ALTO_FILA, ancho_barra=ANCHO_BARRA,
        familia_entradas=_familia("QLineEdit, QComboBox", alto, 8),
        familia_botones=_familia("QPushButton", alto, 12),
    )
    hoja = _PLANTILLA.substitute(**t)
    # el desplegable deja sitio a su flecha (la zona `drop-down`, de 24 px); se escribe aparte para que `padding` no se pierda
    hoja += f"QComboBox {{ padding-right:28px; }}\nQComboBox:focus {{ padding-right:27px; }}\n"
    return hoja


def campos_compactos(alto: int = ALTO_CONTROL_COMPACTO) -> str:
    """Hoja local para paneles con poco alto: campos de texto y desplegables de `alto` px (32, el mínimo táctil) en lugar de los
    36 de la hoja global, con el mismo foco discontinuo de 2 px sin que nada se mueva."""
    return (f"QLineEdit, QComboBox {{ min-height:{alto - 2}px; padding:0 8px; }} "
            f"QLineEdit:focus, QComboBox:focus {{ border:2px dashed {FOCO}; min-height:{alto - 4}px; padding:0 7px; }} "
            f"QComboBox {{ padding-right:28px; }} QComboBox:focus {{ padding-right:27px; }}")


# -- propiedades dinámicas ------------------------------------------------------------------------------------------
def poner(widget, **propiedades) -> None:
    """Pone propiedades dinámicas y vuelve a aplicar la hoja al widget (los selectores `[prop="valor"]` lo piden)."""
    cambiado = False
    for nombre, valor in propiedades.items():
        if widget.property(nombre) != valor:
            widget.setProperty(nombre, valor)
            cambiado = True
    if cambiado:
        repulir(widget)


def repulir(widget) -> None:
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
    widget.update()


# -- iconos (un solo trazo: 1,75 px sobre una rejilla de 24, extremos y uniones redondeados) --------------------------
_TRAZOS = {
    "nuevo": [[(7, 3), (14, 3), (19, 8), (19, 21), (5, 21), (5, 3), (7, 3)], [(14, 3), (14, 9), (19, 9)]],
    "abrir": [[(3, 8), (3, 5), (9, 5), (12, 8), (21, 8), (19, 20), (3, 20), (3, 8), (21, 8)]],
    "guardar": [[(4, 3), (18, 3), (21, 6), (21, 21), (3, 21), (3, 3), (4, 3)], [(7, 3), (7, 10), (17, 10), (17, 3)],
                [(7, 21), (7, 14), (17, 14), (17, 21)]],
    "borrar": [[(4, 6), (20, 6)], [(8, 6), (8, 3), (16, 3), (16, 6)], [(6, 6), (7, 21), (17, 21), (18, 6)],
               [(10, 10), (10, 17)], [(14, 10), (14, 17)]],
    "deshacer": [[(8, 4), (3, 9), (8, 14)], [(3, 9), (13, 9), (18, 11), (20, 15), (18, 20)]],
    "rehacer": [[(16, 4), (21, 9), (16, 14)], [(21, 9), (11, 9), (6, 11), (4, 15), (6, 20)]],
    "debajo": [[(6, 4), (18, 4)], [(12, 8), (12, 21)], [(7, 16), (12, 21), (17, 16)]],
    "pausa": [[(8, 5), (8, 19)], [(16, 5), (16, 19)]],
    "conexion": [[(3, 5), (10, 5), (10, 11), (3, 11), (3, 5)], [(14, 13), (21, 13), (21, 20), (14, 20), (14, 13)],
                 [(6, 11), (6, 17), (14, 17)], [(17, 13), (17, 8), (10, 8)]],
    # esquinas hacia fuera: «encajar todo el dibujo»
    "ajustar": [[(3, 9), (3, 3), (9, 3)], [(15, 3), (21, 3), (21, 9)], [(21, 15), (21, 21), (15, 21)], [(9, 21), (3, 21), (3, 15)],
                [(9, 9), (15, 9), (15, 15), (9, 15), (9, 9)]],
    # mira: «centrar la selección»
    "centrar": [[(12, 2), (12, 7)], [(12, 17), (12, 22)], [(2, 12), (7, 12)], [(17, 12), (22, 12)]],
    "editar": [[(4, 20), (5, 15), (16, 4), (20, 8), (9, 19), (4, 20)], [(13, 7), (17, 11)]],
    "mas": [[(12, 5), (12, 19)], [(5, 12), (19, 12)]],
    "menos": [[(5, 12), (19, 12)]],
    "cerrar": [[(6, 6), (18, 18)], [(18, 6), (6, 18)]],
    "plegar_izq": [[(15, 5), (8, 12), (15, 19)]],
    "plegar_der": [[(9, 5), (16, 12), (9, 19)]],
    "plegar_abajo": [[(5, 9), (12, 16), (19, 9)]],
    "plegar_arriba": [[(5, 15), (12, 8), (19, 15)]],
}


def _trazos_reinicio() -> tuple[QPainterPath, QPainterPath]:
    """Arco abierto arriba y punta angular (la referencia del responsable para «Reiniciar»)."""
    arco = QPainterPath()
    arco.arcMoveTo(QRectF(4, 4, 16, 16), 90)
    arco.arcTo(QRectF(4, 4, 16, 16), 90, -315)
    extremo = arco.currentPosition()
    t = QPointF(2 ** -.5, -2 ** -.5)
    vertice = extremo + t * 3
    punta = QPainterPath(vertice - QPointF(5, 0))
    punta.lineTo(vertice)
    punta.lineTo(vertice + QPointF(0, 5))
    return arco, punta


def icono(tipo: str, color: str = TINTA, grosor: float = 1.75, tam: int = 24) -> QIcon:
    """Iconos de línea propios (no son notación GRAFCET). Se dibujan a 2× para que no se pixelen."""
    pm = QPixmap(tam * 2, tam * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if tam != 24:
        p.scale(tam / 24, tam / 24)
    p.setPen(QPen(QColor(color), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if tipo == "play":
        path = QPainterPath()
        path.moveTo(8, 5)
        path.lineTo(19, 12)
        path.lineTo(8, 19)
        path.closeSubpath()
        p.fillPath(path, QColor(color))
        p.drawPath(path)
    elif tipo == "stop":
        p.fillRect(QRectF(6, 6, 12, 12), QColor(color))
    elif tipo == "dependencias":
        p.drawRect(QRectF(2, 9, 6, 6))
        p.drawRoundedRect(QRectF(15, 3, 8, 18), 1, 1)
        pen = p.pen()
        pen.setStyle(Qt.PenStyle.DotLine)
        pen.setWidthF(1.4)
        p.setPen(pen)
        p.drawLine(QPointF(8, 9), QPointF(15, 3))
        p.drawLine(QPointF(8, 15), QPointF(15, 21))
    elif tipo == "reiniciar":
        arco, punta = _trazos_reinicio()
        p.drawPath(arco)
        p.drawPath(punta)
    elif tipo == "centrar":
        p.drawEllipse(QPointF(12, 12), 5, 5)
        p.drawEllipse(QPointF(12, 12), .6, .6)
    elif tipo == "planos":
        p.drawRect(QRectF(5, 2.5, 14, 19))
        p.drawRect(QRectF(7.5, 5, 9, 14))
        p.drawLine(QPointF(10, 15), QPointF(14.5, 15))
    for trazo in _TRAZOS.get(tipo, []):
        path = QPainterPath()
        path.moveTo(*trazo[0])
        for punto in trazo[1:]:
            path.lineTo(*punto)
        p.drawPath(path)
    p.end()
    return QIcon(pm)


def icono_grafcet(color: str = ACENTO) -> QIcon:
    """Esquema de etapa, transición y etapa: el botón que vuelve al dibujo desde la vista de E/S."""
    pm = QPixmap(48, 48)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 1.75, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawRect(QRectF(6, 2.5, 12, 7))
    p.drawLine(12, 9.5, 12, 11.5)
    p.drawLine(7.5, 12, 16.5, 12)
    p.drawLine(12, 12.5, 12, 14.5)
    p.drawRect(QRectF(6, 14.5, 12, 7))
    p.end()
    return QIcon(pm)


def punto(color: str, diametro: int = 12) -> QPixmap:
    """Punto de color para la luz de conexión (con un aro blanco: se ve también sobre fondos grises)."""
    pm = QPixmap(diametro * 2, diametro * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(1, 1, diametro - 2, diametro - 2))
    p.end()
    return pm


def forma_luz(estado: str, diametro: int = 14) -> QPixmap:
    """El estado de la conexión externa no va solo en color: conectada es un círculo lleno con una marca, desconectada un
    círculo vacío y error un rombo con exclamación."""
    clave = {"conectada": "conectada", "error": "error"}.get(estado, "desconectada")
    color = QColor(LUZ[clave])
    pm = QPixmap(diametro * 2, diametro * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    d = diametro
    if clave == "conectada":
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(1, 1, d - 2, d - 2))
        p.setPen(QPen(QColor("white"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline([QPointF(d * .29, d * .52), QPointF(d * .44, d * .67), QPointF(d * .72, d * .35)])
    elif clave == "desconectada":
        p.setBrush(QColor("white"))
        p.setPen(QPen(color, 1.8))
        p.drawEllipse(QRectF(1.9, 1.9, d - 3.8, d - 3.8))
    else:
        rombo = QPainterPath()
        rombo.moveTo(d / 2, .6)
        rombo.lineTo(d - .6, d / 2)
        rombo.lineTo(d / 2, d - .6)
        rombo.lineTo(.6, d / 2)
        rombo.closeSubpath()
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(rombo)
        p.setPen(QPen(QColor("white"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(d / 2, d * .28), QPointF(d / 2, d * .57))
        p.drawPoint(QPointF(d / 2, d * .75))
    p.end()
    return pm


def estilo_chip(modo: str) -> str:
    """El chip de modo de la cabecera del dibujo: relleno y texto en mayúsculas, para que el estado no dependa del color."""
    relleno, texto = {"simular": (SIMULACION, BLANCO), "editar": (EDICION, BLANCO),
                      "lectura": (TINTA_2, BLANCO), "aviso": (AVISO_FONDO, AVISO), "error": (ERROR, BLANCO)}.get(modo, (TINTA_2, BLANCO))
    borde = AVISO_BORDE if modo == "aviso" else relleno
    return (f"background:{relleno}; color:{texto}; border:1px solid {borde}; border-radius:{R_L}px; padding:2px 12px; "
            f"font-size:{T_CHIP}px; font-weight:700; letter-spacing:.5px")
