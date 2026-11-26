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
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

# -- color ----------------------------------------------------------------------------------------------------------
TINTA = "#16263a"          # texto principal (15,3:1 sobre blanco)
TINTA_2 = "#4a5b6e"        # texto secundario (7:1)
TINTA_3 = "#5b6b7d"        # ayudas y rótulos discretos (4,9:1 sobre el fondo de la ventana)
BLANCO = "white"
FONDO = "#eef2f6"          # fondo de la ventana
SUPERFICIE = "#ffffff"     # tarjetas y paneles
SUPERFICIE_2 = "#f7f9fc"   # cabeceras de tabla, barras secundarias
SUPERFICIE_3 = "#f1f5f9"   # estuches segmentados y barra de estado
BORDE = "#d4dde8"          # separadores y marcos decorativos
BORDE_FUERTE = "#b6c4d4"   # borde suave de botones secundarios y cápsulas
BORDE_CONTROL = "#7b8a9c"  # borde de un control (3,5:1 sobre blanco)
DESHABILITADO = "#7c8896"  # texto de lo no disponible (la norma exime de contraste a lo deshabilitado)
HOVER = "#e4ecf3"          # pasar el puntero por un control sin relleno
PULSADO = "#d3dfea"

ACENTO = "#0b6e75"         # petróleo: lo accionable, un solo acento por zona (6:1 con texto blanco)
ACENTO_OSCURO = "#095259"
ACENTO_HOVER = "#0d8189"
ACENTO_SUAVE = "#cfeee6"   # relleno de lo seleccionado o activo (menta; una prueba fija este tono en el icono marcado)
ACENTO_BORDE = "#8fcdd1"

EDICION = "#2f3b4a"        # tinta pizarra, neutra: el programa está en edición; no compite con el acento petróleo (blanco encima: 11,3:1)
SIMULACION = "#157a35"     # verde máquina de la simulación en marcha (blanco encima: 5,4:1)
SIMULACION_SUAVE = "#e3f4e8"
SIMULACION_HOVER = "#0f6a2c"  # (blanco encima: 6,7:1)
SIMULACION_BORDE = "#8cc9a0"

PILOTO_ENCENDIDO = "#39ff14"  # verde eléctrico de las señales booleanas activas
PILOTO_APAGADO = "#3f8f57"  # verde apagado: distinto del gris de «Cualquiera» (#6d837b), contraste 3,5:1 con el fondo del módulo
PILOTO_HALO = "#4539ff14"  # mismo verde, con alfa 27 %

OK = SIMULACION           # lo correcto y lo activo comparten el mismo verde
AVISO = "#8a5a00"          # texto ámbar sobre fondo claro (5,4:1)
AVISO_FONDO = "#fff4d6"
AVISO_BORDE = "#e3b74a"
ERROR = "#c62828"          # solo errores (el mismo del dibujo)
NOMBRE_PENDIENTE_FONDO = "#ffe0b2"  # naranja claro: nombre que impide traer una señal
ERROR_FONDO = "#fdecea"
FOCO = TINTA               # el foco de teclado: trazo discontinuo de 2 px
FOCO_FUERTE = "#000000"    # el foco de un botón relleno (Play/Stop): 3 px, 3:1 o más contra el relleno y contra el fondo
CONFIRMAR = "#27665c"      # botón de confirmar de la franja de selección de PLANOS (P-IMP planos)
CONFIRMAR_BORDE = "#1d5048"
CONFIRMAR_HOVER = "#1b5149"
PARPADEO = "#2f8a91"       # el tono claro del parpadeo de «+ Añadir hoja»: blanco encima, 4,1:1

TIPO_BOOL, TIPO_DECIMAL, TIPO_ENTERA, TIPO_CUALQUIERA = "#22a342", "#008add", "#d96a0c", "#6d837b"  # la barrita de tipo de variable (E/S)
ORIGEN_MEMORIA = "#7a3e8e"  # ciruela: la barra de origen de las fichas de memoria (7,2:1 sobre blanco); ni aviso ni tipo entero
SENAL_CONDICION, SENAL_ACCION = ACENTO, TINTA_2  # el color de cada parte de Propiedades: receptividad, condición y evento / acción
SENAL_TENUE, SENAL_ASIGNADA = "#cbd2d5", "#7c8a90"  # la barrita sin señal y asignada (3,5:1 sobre blanco con su contorno)
RESALTADO = "#e8f5ef"      # fila de variable resaltada en E/S (una prueba fija este tono)
ASIGNACION = "#c1e8dc"     # la zona de un canal donde caería la variable que se arrastra
LED_CONSOLA = "#22c55e"    # piloto LED encendido en la consola de simulación

MESA = "#dfe5eb"           # el tablero sobre el que se ve una hoja de PLANOS o una plantilla (no es parte del dibujo)

LUZ = {"conectada": SIMULACION, "desconectada": "#6f7f92", "error": "#c62828"}  # punto de la conexión externa

# -- espaciado (ritmo de 4 y 8), radios, tipografía, alturas -------------------------------------------------------
E1, E2, E3, E4, E6 = 4, 8, 12, 16, 24
R_S, R_M, R_L = 4, 8, 12
FUENTE = "Segoe UI"
FUENTE_TITULO = "Bahnschrift"  # tipografía técnica de Windows para títulos, rótulos de sección y chip (reserva: Segoe UI)
FUENTE_MONO = "Consolas"      # cifras: tiempos, valores y porcentaje
FAMILIA_TITULO = f'"{FUENTE_TITULO}", "{FUENTE}"'
FAMILIA_MONO = f'"{FUENTE_MONO}", "Courier New"'
ANCHO_BARRA = 10           # barras de desplazamiento

# Dos escalas de letra y controles que cambian con el tamaño de la ventana (`activar_escala`).
# Normal: hasta 1366×768, controles de 30 px. Grande: letra base de 14 px y controles de 32 px,
# para leer con el proyector desde 1600×900. Los menús no cambian.
ESCALAS = {
    "normal": dict(T_BASE=13, T_PEQUENA=12, T_TITULO=16, T_SECCION=14, T_CHIP=13, T_CIFRA=12,
                   ALTO_CONTROL=30, ALTO_CONTROL_COMPACTO=30, ALTO_BARRA=30, ALTO_BARRA_COMPACTA=28,
                   ALTO_FILA=30, ALTO_ENTRADA=32, ALTO_FILA_COMPACTA=28,
                   T_ES=12, ALTO_FILA_ES=24, ANCHO_INTERIOR_ES=200),  # (vista de E/S 2.0.1: filas legibles y limpias)
    "grande": dict(T_BASE=14, T_PEQUENA=13, T_TITULO=19, T_SECCION=16, T_CHIP=15, T_CIFRA=14,
                   ALTO_CONTROL=32, ALTO_CONTROL_COMPACTO=32, ALTO_BARRA=34, ALTO_BARRA_COMPACTA=32,
                   ALTO_FILA=34, ALTO_ENTRADA=36, ALTO_FILA_COMPACTA=32,
                   T_ES=14, ALTO_FILA_ES=26, ANCHO_INTERIOR_ES=236)}
UMBRAL_GRANDE = (1600, 900)  # ancho y alto de la ventana a partir de los cuales rige la escala grande
ESCALA = "normal"
T_BASE = T_PEQUENA = T_TITULO = T_SECCION = T_CHIP = T_CIFRA = 0
ALTO_CONTROL = ALTO_CONTROL_COMPACTO = ALTO_BARRA = ALTO_BARRA_COMPACTA = ALTO_FILA = ALTO_ENTRADA = ALTO_FILA_COMPACTA = 0
T_ES = ALTO_FILA_ES = ANCHO_INTERIOR_ES = 0


HISTERESIS_ESCALA = 40  # px: ya en la escala grande, no se vuelve a la normal hasta bajar tanto del umbral (arrastrar el borde justo por él no la reaplica una y otra vez)


def escala_para(ancho: int, alto: int, actual: str | None = None) -> str:
    """La escala que corresponde a una ventana de ese tamaño: «grande» desde `UMBRAL_GRANDE`, «normal» por debajo. Con `actual` («grande»),
    la escala grande se conserva hasta `HISTERESIS_ESCALA` px por debajo del umbral."""
    margen = HISTERESIS_ESCALA if actual == "grande" else 0
    return "grande" if ancho >= UMBRAL_GRANDE[0] - margen and alto >= UMBRAL_GRANDE[1] - margen else "normal"


def activar_escala(nombre: str) -> None:
    """Pone los tokens de letra y de alto de la escala `nombre` (los lee quien construye una hoja de estilo después de esto; las
    hojas ya aplicadas las vuelve a generar la ventana, que es quien llama aquí al cruzar el umbral)."""
    global ESCALA
    ESCALA = nombre
    globals().update(ESCALAS[nombre])
    from .campos_medidos import notificar_fuentes
    notificar_fuentes()


activar_escala("normal")


# -- modo compacto --------------------------------------------------------------------------------------------------
UMBRAL_ANCHO = 1000  # por debajo: pantalla partida (los paneles laterales se compactan)
UMBRAL_MUY_ESTRECHO = 760  # por debajo (media pantalla): Reiniciar solo icono y pestañas más justas
UMBRAL_ALTO = 560    # por debajo: un cuarto de pantalla (se estrechan cabeceras y márgenes)


def tamano_compacto(ancho: int, alto: int) -> tuple[bool, bool]:
    """(compacto en ancho, compacto en alto) para el tamaño de la ventana."""
    return ancho < UMBRAL_ANCHO, alto < UMBRAL_ALTO


# -- hoja de estilo global ------------------------------------------------------------------------------------------
def _familia(selectores: str, alto: int, pad_h: int, extra: str = "", pad_extra: tuple[int, int] = (0, 0),
             teclado: bool = False) -> str:
    """Un control de `alto` px con borde de 1 px y, con el foco, borde de 2 px que no mueve nada: sólido de acento con
    el ratón (salvo botones, que solo marcan foco por teclado) y discontinuo con el teclado (`tecl="true"`)."""
    sel = [x.strip() for x in selectores.split(",")]
    pad = f"0 {pad_h - 1 + pad_extra[0]}px 0 {pad_h - 1}px"
    norm = f"{selectores} {{ min-height:{alto - 2}px; padding:0 {pad_h + pad_extra[0]}px 0 {pad_h}px; {extra} }}\n"
    if teclado:
        foco = ", ".join(f'{s}[tecl="true"]:focus' for s in sel)
        return norm + f"{foco} {{ border:2px dashed {FOCO}; min-height:{alto - 4}px; padding:{pad}; }}\n"
    foco_r = ", ".join(f"{s}:focus" for s in sel)
    foco_t = ", ".join(f'{s}[tecl="true"]:focus' for s in sel)
    return (norm + f"{foco_r} {{ border:2px solid {ACENTO}; min-height:{alto - 4}px; padding:{pad}; }}\n"
            + f"{foco_t} {{ border:2px dashed {FOCO}; min-height:{alto - 4}px; padding:{pad}; }}\n")


_PLANTILLA = Template("""
QWidget { font-family:"$fuente"; font-size:${t_base}px; color:$tinta; }
QMainWindow, QDialog { background:$fondo; }
QToolTip { background:$superficie; color:$tinta; border:1px solid $borde_fuerte; border-radius:6px; padding:6px 8px; }
QWidget#panelDibujo, QWidget#panelVariables, QWidget#consolaSimulacion { background:$superficie; border:0; border-radius:0; }
QLabel#tituloConsola { color:$tinta_3; font-size:11px; font-weight:700; letter-spacing:0.4px; background:transparent; }
QFrame#cabeceraPanel { background:$superficie_2; border:0; border-bottom:1px solid $borde; }
QLabel#badgePanel { font-family:$familia_mono; font-size:10.5px; font-weight:600; color:$tinta_2; background:#e2e8f0; border-radius:8px; padding:1px 6px; }
QWidget#panelPropiedades { background:$superficie; border:1px solid $borde; border-radius:${r_m}px; }
QLabel#tituloPanel { font-family:$familia_titulo; font-size:12.5px; font-weight:700; color:$tinta; border:0; background:transparent; }
QWidget#cabeceraPropiedades { background:$superficie_2; border-radius:${r_s}px; }
QLabel#tituloPropiedades { font-family:$familia_titulo; color:$acento; font-size:${t_seccion}px; font-weight:600; background:transparent; padding:3px 0; }
QLabel#ayudaPropiedades { color:$tinta_3; padding:4px 8px; }

QMenuBar { background:transparent; padding:0; border:0; font-size:12px; color:$tinta_2; }
QMenuBar::item { padding:4px 7px; border-radius:${r_s}px; color:$tinta_2; background:transparent; }
QMenuBar::item:selected { background:$hover; color:$tinta; }
QMenu::item:selected { background:$acento_suave; color:$tinta; }
QMenu { background:$superficie; border:1px solid $borde_control; padding:4px; }
QMenu::item { padding:${pad_item}px 28px ${pad_item}px 24px; border-radius:${r_s}px; }
QMenu::item:disabled { color:$deshabilitado; }
QMenu::separator { height:1px; background:$borde; margin:4px 8px; }

QWidget#filaPestanas { background:$superficie; border-bottom:1px solid $borde; }
QWidget#filaPestanas[fusion="true"] { border-bottom:1px solid $borde; }
QWidget#herramientasGrafcet[fusion="true"], QWidget#herramientasGrafcet[fusion="true"][modo="simular"] { background:transparent; border:0; }
QFrame#estucheVistas { background:$superficie_3; border:1px solid $borde; border-radius:7px; }
QTabBar#pestanasVistas { background:transparent; border:0; }
QTabBar#pestanasVistas::tab { font-family:$familia_titulo; font-size:12px; padding:4px 12px; margin:0 1px 0 0; background:transparent;
    color:$tinta_2; border:1px solid transparent; font-weight:600; border-radius:5px; }
QTabBar#pestanasVistas::tab:selected { background:$superficie; color:$tinta; border:1px solid $borde_fuerte; }
QTabBar#pestanasVistas[estrecha="true"]::tab { padding:4px 8px; margin-right:1px; }
QTabBar#pestanasVistas::tab:hover:!selected { background:rgba(255,255,255,170); color:$tinta; }
QTabBar#pestanasVistas::tab:disabled { color:$deshabilitado; }
QTabBar#pestanasVistas[tecl="true"]::tab:selected:focus { border:2px dashed $foco; }

QWidget#bandaModo { background:transparent; }
QToolButton#luzES { font-family:$familia_titulo; font-size:12px; font-weight:600; border:1px solid transparent; border-radius:5px;
    background:transparent; color:$tinta_2; padding:3px 12px; min-height:20px; }
QToolButton#luzES:hover { background:rgba(255,255,255,170); color:$tinta; }
QToolButton#luzES:pressed { background:$pulsado; }
QToolButton#luzES[tecl="true"]:focus { border:2px dashed $foco; padding:2px 11px; }
QToolButton#luzES[estadoLuz="conectada"] { color:$tinta; }
QToolButton#luzES[estadoLuz="error"] { background:$error_fondo; border:1px solid $error; color:$error; }
QToolButton#luzES[abierta="true"] { background:$superficie; border:1px solid $borde_fuerte; color:$tinta; font-weight:600; }
QWidget#herramientasGrafcet { background:$superficie_2; border-bottom:1px solid $borde; }
QToolBar { background:transparent; border:0; spacing:4px; padding:0; margin:0; }
QToolBar QToolButton { min-height:${alto_tb_c}px; padding:0 9px; border:1px solid transparent; border-radius:6px; color:$tinta_2; background:transparent; font-weight:600; }
QToolBar QToolButton:hover { background:$hover; color:$tinta; }
QToolBar QToolButton:pressed { background:$pulsado; }
QToolBar QToolButton:checked { background:$acento_suave; border-color:$acento_borde; color:$acento_oscuro; }
QToolBar QToolButton:disabled { color:$deshabilitado; background:transparent; border-color:transparent; }
QToolBar QToolButton[tecl="true"]:focus { border:2px dashed $foco; min-height:${alto_tb_f}px; padding:0 8px; }
QToolBar::separator { width:1px; background:$borde; margin:5px 3px; }
QToolBar#barraSimulacion QToolButton#botonReiniciar { background:$superficie; border:1px solid $borde_fuerte; color:$tinta; border-radius:6px; padding:0 10px; }
QToolBar#barraSimulacion QToolButton#botonReiniciar:hover { background:$hover; border-color:$borde_control; }
QToolBar#barraSimulacion QToolButton#botonReiniciar:pressed { background:$pulsado; }
QToolBar#barraSimulacion QToolButton#botonReiniciar:disabled { border-color:$borde; color:$deshabilitado; }
QToolBar#barraSimulacion QToolButton#botonReiniciar[tecl="true"]:focus { border:2px dashed $foco; }
QToolBar#barraSimulacion QToolButton#botonPlay { font-family:$familia_titulo; background:$acento; color:$blanco; border:1px solid $acento_oscuro; font-weight:600;
    border-radius:6px; padding:0 14px; }
QToolBar#barraSimulacion QToolButton#botonPlay:hover { background:$acento_oscuro; }
QToolBar#barraSimulacion QToolButton#botonPlay:pressed { background:$acento_oscuro; }
QToolBar#barraSimulacion QToolButton#botonPlay:checked { background:$simulacion; border-color:$simulacion_hover; color:$blanco; }
QToolBar#barraSimulacion QToolButton#botonPlay:checked:hover { background:$simulacion_hover; }
QToolBar#barraSimulacion QToolButton#botonPlay:disabled { background:$pulsado; color:$deshabilitado; border-color:$borde; }
QToolBar#barraSimulacion QToolButton#botonPlay[tecl="true"]:focus { border:3px dashed $foco_fuerte; padding:0 12px; min-height:${alto_tb_f2}px; }
QToolBar#barraEdicion QToolButton, QToolBar#barraVistaDer QToolButton, QToolBar#barraVista QToolButton { background:transparent; border:1px solid transparent; border-radius:6px; min-width:${alto_tb}px; padding:0 7px; color:$tinta_2; font-weight:600; }
QToolBar#barraEdicion QToolButton:hover, QToolBar#barraVistaDer QToolButton:hover, QToolBar#barraVista QToolButton:hover { background:$hover; border-color:transparent; color:$tinta; }
QToolBar#barraEdicion QToolButton:pressed, QToolBar#barraVistaDer QToolButton:pressed, QToolBar#barraVista QToolButton:pressed { background:$pulsado; }
QToolBar#barraEdicion QToolButton:checked, QToolBar#barraVistaDer QToolButton:checked, QToolBar#barraVista QToolButton:checked { background:$acento_suave; border:1px solid $acento_borde; color:$acento_oscuro; }
QToolBar#barraEdicion QToolButton:disabled, QToolBar#barraVistaDer QToolButton:disabled, QToolBar#barraVista QToolButton:disabled { background:transparent; border-color:transparent; color:$deshabilitado; }
QToolBar#barraEdicion QToolButton[tecl="true"]:focus, QToolBar#barraVistaDer QToolButton[tecl="true"]:focus, QToolBar#barraVista QToolButton[tecl="true"]:focus { border:2px dashed $foco; padding:0 6px; }
QToolBar#barraPlanos { background:$superficie; border:1px solid $borde; border-radius:${r_m}px; padding:4px 8px; spacing:6px; }
QToolBar#barraPlanos::separator { background:$borde; width:1px; margin:4px 6px; }
QToolBar#barraPlanos QToolButton { background:$superficie; border:1px solid $borde_fuerte; border-radius:6px; color:$tinta; padding:0 10px; }
QToolBar#barraPlanos QToolButton#bibliotecaPlanos { padding:0 32px 0 10px; }
QToolBar#barraPlanos QToolButton:hover { background:$hover; border-color:$borde_control; color:$tinta; }
QToolBar#barraPlanos QToolButton:pressed { background:$pulsado; }
QToolBar#barraPlanos QToolButton:checked { background:$acento_suave; border:2px solid $acento; color:$acento_oscuro; padding:0 9px; }
QToolBar#barraPlanos QToolButton:disabled { background:$superficie_2; border-color:$borde; color:$deshabilitado; }
QToolBar#barraPlanos QToolButton[tecl="true"]:focus { border:2px dashed $foco; padding:0 9px; }
QToolBar#barraConexion QToolButton { border:1px solid $acento_borde; background:$superficie; color:$acento; }
QToolButton#bibliotecaPlanos { padding-right:28px; }
QToolButton#bibliotecaPlanos::menu-indicator { image:url(:/grafconnect/desplegar.svg); subcontrol-origin:padding; subcontrol-position:center right; right:8px; width:12px; height:8px; }

QLineEdit, QComboBox { background:$superficie; border:1px solid $borde_control; border-radius:${r_s}px;
    selection-background-color:$acento; selection-color:$blanco; }
QLineEdit:disabled, QComboBox:disabled { background:$superficie_2; border-color:$borde; color:$deshabilitado; }
QLineEdit[readOnly="true"] { background:$superficie_2; }
$familia_entradas
QSpinBox, QDoubleSpinBox { background:$superficie; border:1px solid $borde_control; border-radius:${r_s}px;
    selection-background-color:$acento; selection-color:$blanco; }
QSpinBox:disabled, QDoubleSpinBox:disabled { background:$superficie_2; border-color:$borde; color:$deshabilitado; }
$familia_spin
QSpinBox, QDoubleSpinBox { max-height:${alto_menos}px; }  /* (la altura que pide el propio spinbox es mayor que su mínimo: sin esto mide 3 px más que los demás controles) */
QSpinBox:focus, QDoubleSpinBox:focus { max-height:${alto_menos4}px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:18px; border:0; background:transparent; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:18px; border:0; background:transparent; }
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background:$hover; }
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed, QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed { background:$pulsado; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image:url(:/grafconnect/subir.svg); width:8px; height:5px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image:url(:/grafconnect/desplegar.svg); width:8px; height:5px; }
QSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled, QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::down-arrow:disabled { image:none; }
QAbstractSpinBox QLineEdit, QAbstractSpinBox QLineEdit:focus { border:0; background:transparent; min-height:0; padding:0 0 0 4px; margin:0; }
QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; width:24px; border:0; background:transparent; }
QComboBox::down-arrow { image:url(:/grafconnect/desplegar.svg); width:12px; height:8px; }
QComboBox QAbstractItemView { background:$superficie; border:1px solid $borde_control; selection-background-color:$acento_suave; selection-color:$tinta; outline:0; }
QComboBox QAbstractItemView::item { min-height:${alto_fila}px; padding:0 8px; }

QPushButton { background:$superficie; border:1px solid $borde_fuerte; border-bottom-color:#9fb0c4; border-radius:6px; color:$tinta; font-weight:500; }
$familia_botones
QPushButton:hover { background:$hover; border-color:$borde_control; }
QPushButton:pressed { background:$pulsado; }
QPushButton:checked { background:$acento_suave; border-color:$acento; }
QPushButton:disabled, QToolButton:disabled { color:$deshabilitado; }
QPushButton:disabled { border-color:$borde; background:$superficie_2; }
QPushButton[primario="true"] { background:$acento; color:$blanco; border:1px solid $acento_oscuro; font-weight:600; }
QPushButton[primario="true"]:hover { background:$acento_hover; border-color:$acento_oscuro; }
QPushButton[primario="true"]:pressed { background:$acento_oscuro; }
QPushButton[primario="true"][tecl="true"]:focus { border:2px dashed $blanco; }
QPushButton[primario="true"]:disabled { background:$pulsado; color:$deshabilitado; border-color:$borde; }
QPushButton[entrada="true"] { text-align:left; padding:0 10px; border:2px solid $borde_fuerte; border-radius:6px; background:$superficie; color:$tinta; font-weight:600; min-height:${alto_entrada}px; }
QPushButton[entrada="true"]:hover { border-color:$acento; }
QPushButton[entrada="true"][tecl="true"]:focus { border:2px dashed $foco; padding:0 10px; min-height:${alto_entrada}px; }
QPushButton[entrada="true"][activa="true"] { background:$simulacion_suave; border:2px solid $simulacion; color:$simulacion_hover; }
QPushButton[entrada="true"]:disabled { background:$superficie_2; border-color:$borde; color:$deshabilitado; }
QPushButton[entrada="true"][activa="true"]:disabled { background:$simulacion_suave; border:2px solid $simulacion_borde; color:$tinta_2; }
QToolButton { border:1px solid transparent; border-radius:${r_s}px; background:transparent; }
QToolButton:hover { background:$hover; }
QToolButton:pressed { background:$pulsado; }
QToolButton:checked { background:$acento_suave; border-color:$acento; }
QToolButton[tecl="true"]:focus { border:2px dashed $foco; }
QCheckBox, QRadioButton { spacing:8px; min-height:${alto_menos}px; }
QCheckBox[tecl="true"]:focus, QRadioButton[tecl="true"]:focus { border:2px dashed $foco; border-radius:${r_s}px; }
/* el anillo discontinuo de listas, tablas y del dibujo solo con el teclado: la ventana pone tecl="true" al recibir el foco con Tab */
QListWidget[tecl="true"]:focus, QTableWidget[tecl="true"]:focus, QTreeWidget[tecl="true"]:focus, QTextEdit:focus, QPlainTextEdit:focus { border:2px dashed $foco; }
QGraphicsView[tecl="true"]:focus { border:2px dashed $foco; }
QGraphicsView { border:2px solid transparent; }

QGroupBox { font-family:$familia_titulo; background:$superficie; border:0; margin-top:24px; font-size:${t_seccion}px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; padding:3px 6px; color:$acento; }
QGroupBox[seccion="true"]::title { padding:3px 6px; }  /* subsecciones limpias sin marcador (paneles.CajaSeccion) */
QGroupBox#grupoVariables { font-size:${t_titulo}px; }
QGroupBox#grupoVariables::title { color:$tinta; }
QGroupBox QLabel, QGroupBox QPushButton, QGroupBox QTableWidget, QGroupBox QLineEdit, QGroupBox QComboBox, QGroupBox QCheckBox { font-family:"$fuente"; font-weight:400; font-size:${t_base}px; }
QTableWidget, QListWidget, QTreeWidget { background:$superficie; border:2px solid transparent; gridline-color:$borde; alternate-background-color:$superficie_2;
    selection-background-color:$acento_suave; selection-color:$tinta; outline:0; }
QHeaderView::section { background:$superficie_2; border:0; border-bottom:1px solid $borde; padding:6px 6px; color:$tinta_2; font-weight:600; }
QScrollArea { border:0; background:transparent; }
QScrollArea > QWidget > QWidget { background:$fondo; }  /* el contenido de un área desplazable, con el fondo de la ventana (no el gris de Qt) */
QScrollBar:horizontal { height: ${ancho_barra}px; background:transparent; margin:0; border-radius:5px; }
QScrollBar::handle:horizontal { background:$borde_fuerte; min-width:36px; border-radius:4px; margin:2px; }
QScrollBar::handle:horizontal:hover { background:$borde_control; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:transparent; }
QScrollBar:vertical { width: ${ancho_barra}px; background:transparent; margin:0; border-radius:5px; }
QScrollBar::handle:vertical { background:$borde_fuerte; min-height:36px; border-radius:4px; margin:2px; }
QScrollBar::handle:vertical:hover { background:$borde_control; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QSplitter::handle { background:transparent; }
QSplitter::handle:horizontal { border-right:1px solid $borde; }
QSplitter::handle:vertical { border-top:1px solid $borde; }
QSplitter::handle:hover { background:$acento_suave; }
QStatusBar { background:$superficie_3; border-top:1px solid $borde; color:$tinta_2; font-size:11px; min-height:26px; }
QStatusBar::item { border:0; }
QProgressBar { border:1px solid $borde_control; border-radius:${r_s}px; background:$superficie; text-align:center; }
QProgressBar::chunk { background:$acento; }
/* controles dentro de una tabla, lista o árbol (celdas con `setCellWidget` y editores de delegado): miden lo que la fila, sin alto mínimo propio */
QAbstractItemView QLineEdit, QAbstractItemView QComboBox, QAbstractItemView QAbstractSpinBox,
QAbstractItemView QLineEdit:focus, QAbstractItemView QComboBox:focus, QAbstractItemView QAbstractSpinBox:focus { min-height:0; padding-top:0; padding-bottom:0; border-radius:0; }
QAbstractItemView QAbstractSpinBox QLineEdit { border:0; min-height:0; padding:0; }
""")


def hoja_global(compacto_alto: bool = False) -> str:
    """La hoja de estilo de la ventana. La ventana usa siempre la de alturas normales (cambiarla al vuelo cuesta cerca de un
    segundo); `compacto_alto` baja las alturas de control a 32 px y queda para herramientas y maquetas."""
    from .campos_medidos import instalar
    from .estilo_botones import instalar as instalar_botones
    instalar()
    instalar_botones()
    alto = ALTO_CONTROL_COMPACTO if compacto_alto else ALTO_CONTROL
    alto_tb = ALTO_BARRA_COMPACTA if compacto_alto else ALTO_BARRA  # botones de las barras: 34 px, o 32 en un cuarto de pantalla
    t = dict(
        fuente=FUENTE, t_base=T_BASE, t_pequena=T_PEQUENA, t_titulo=T_TITULO, t_seccion=T_SECCION,
        tinta=TINTA, tinta_2=TINTA_2, tinta_3=TINTA_3, blanco=BLANCO, fondo=FONDO, superficie=SUPERFICIE,
        superficie_2=SUPERFICIE_2, superficie_3=SUPERFICIE_3, borde=BORDE, borde_fuerte=BORDE_FUERTE,
        borde_control=BORDE_CONTROL, deshabilitado=DESHABILITADO, hover=HOVER,
        pulsado=PULSADO, acento=ACENTO, acento_oscuro=ACENTO_OSCURO, acento_hover=ACENTO_HOVER, acento_suave=ACENTO_SUAVE,
        acento_borde=ACENTO_BORDE, simulacion=SIMULACION, simulacion_suave=SIMULACION_SUAVE, foco=FOCO,
        r_s=R_S, r_m=R_M, fondo_pestanas=FONDO, edicion=EDICION, ok=OK, error=ERROR, error_fondo=ERROR_FONDO,
        familia_titulo=FAMILIA_TITULO, familia_mono=FAMILIA_MONO, foco_fuerte=FOCO_FUERTE, simulacion_hover=SIMULACION_HOVER, simulacion_borde=SIMULACION_BORDE, alto_entrada=ALTO_ENTRADA - 4, alto_tb_f2=alto_tb - 9,
        radio_pastilla=alto_tb // 2, alto_pastilla=alto_tb - 5, alto_pastilla_foco=alto_tb - 7, alto_tb=alto_tb, alto_tb_c=alto_tb - 5, alto_tb_f=alto_tb - 7,
        pad_menu=3 if compacto_alto else 4, pad_item=6 if compacto_alto else 8,
        pad_tab=3 if not compacto_alto else 2, pad_barra=2 if compacto_alto else 4, alto_menos=alto - 2, alto_menos4=alto - 4,
        alto_fila=ALTO_FILA_COMPACTA if compacto_alto else ALTO_FILA, ancho_barra=ANCHO_BARRA,
        familia_entradas=_familia("QLineEdit, QComboBox", alto, 8),
        familia_botones=_familia("QPushButton", alto, 12, teclado=True),
        familia_spin=_familia("QSpinBox, QDoubleSpinBox", alto, 8, pad_extra=(18, 0)),
    )
    hoja = _PLANTILLA.substitute(**t)
    # el desplegable deja sitio a su flecha (la zona `drop-down`, de 24 px); se escribe aparte para que `padding` no se pierda
    hoja += (
        "QComboBox { padding-right:28px; }\n"
        "QComboBox:focus, QComboBox[tecl=\"true\"]:focus { padding-right:27px; }\n"
    )
    return hoja


def campos_compactos(alto: int | None = None) -> str:
    """Hoja local para paneles con poco alto: campos y desplegables de `alto` px (por defecto, `ALTO_CONTROL_COMPACTO`)
    con borde sólido de acento en ratón y discontinuo de foco en teclado."""
    alto = ALTO_CONTROL_COMPACTO if alto is None else alto
    return (
        f"QLineEdit, QComboBox {{ min-height:{alto - 2}px; padding:0 8px; }} "
        f"QLineEdit:focus, QComboBox:focus {{ border:2px solid {ACENTO}; min-height:{alto - 4}px; padding:0 7px; }} "
        f'QLineEdit[tecl="true"]:focus, QComboBox[tecl="true"]:focus {{ border:2px dashed {FOCO}; '
        f"min-height:{alto - 4}px; padding:0 7px; }} "
        f"QComboBox {{ padding-right:28px; }} "
        f'QComboBox:focus, QComboBox[tecl="true"]:focus {{ padding-right:27px; }}'
    )


def fuente(px: int | None = None, negrita: bool = False, titulo: bool = False, mono: bool = False) -> QFont:
    """Una letra con la familia explícita de la interfaz y su tamaño en píxeles. Para medir texto antes de que el widget tenga la
    letra de su hoja de estilo: `QFont()` da la de la plataforma, que puede ser otra (y el texto medido no sería el que se pinta)."""
    f = QFont(FUENTE_MONO if mono else FUENTE_TITULO if titulo else FUENTE)
    f.setPixelSize(px or T_BASE)
    f.setBold(negrita)
    return f


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
    "volver": [[(20, 12), (4, 12)], [(10, 6), (4, 12), (10, 18)]],
    "deshacer": [[(8, 4), (3, 9), (8, 14)], [(3, 9), (13, 9), (18, 11), (20, 15), (18, 20)]],
    "rehacer": [[(16, 4), (21, 9), (16, 14)], [(21, 9), (11, 9), (6, 11), (4, 15), (6, 20)]],
    # tijeras: dos hojas que se cruzan (las anillas se dibujan en `icono`), dos hojas de papel solapadas y un portapapeles con su pinza
    "cortar": [[(8.6, 14.6), (19, 3)], [(15.4, 14.6), (5, 3)]],
    "copiar": [[(9, 8), (20, 8), (20, 21), (9, 21), (9, 8)], [(15, 8), (15, 3), (4, 3), (4, 16), (9, 16)]],
    "pegar": [[(9, 5), (6, 5), (5, 6), (5, 21), (19, 21), (19, 6), (18, 5), (15, 5)], [(9, 3), (15, 3), (15, 7), (9, 7), (9, 3)],
              [(8, 12), (16, 12)], [(8, 16), (14, 16)]],
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


def _triangulo_aviso() -> QPainterPath:
    t = QPainterPath(QPointF(12, 3.8))
    t.lineTo(21.2, 19.8)
    t.lineTo(2.8, 19.8)
    t.closeSubpath()
    return t


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
        p.drawRect(QRectF(2.5, 9, 6, 6))
        p.drawRoundedRect(QRectF(15.5, 4, 6, 16), 1, 1)
        trazo = QPen(p.pen())
        punto = QPen(trazo)  # las uniones de las esquinas: tres puntos redondos de verdad (un trazo discontinuo de 1 px se
        punto.setWidthF(1.4)  # difuminaba en gris al reducir el icono a 20 px y no se veía)
        punto.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(punto)
        for (x0, y0), (x1, y1) in (((8.5, 9), (15.5, 4)), ((8.5, 15), (15.5, 20))):
            for f in (0.2, 0.5, 0.8):
                p.drawPoint(QPointF(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
        p.setPen(trazo)
    elif tipo == "aviso":  # el triángulo de aviso, con el trazo de los demás
        p.drawPath(_triangulo_aviso())
        p.drawLine(QPointF(12, 9.5), QPointF(12, 14.2))
        p.drawPoint(QPointF(12, 17.4))
    elif tipo == "reiniciar":
        arco, punta = _trazos_reinicio()
        p.drawPath(arco)
        p.drawPath(punta)
    elif tipo == "centrar":
        p.drawEllipse(QPointF(12, 12), 5, 5)
        p.drawEllipse(QPointF(12, 12), .6, .6)
    elif tipo == "cortar":
        p.drawEllipse(QPointF(6.5, 18), 3, 3)
        p.drawEllipse(QPointF(17.5, 18), 3, 3)
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


