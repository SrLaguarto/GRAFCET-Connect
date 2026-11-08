"""Conexión de E/S: vista «autómata» con las variables a los lados y los canales del servidor Modbus en el centro.

A la izquierda, los sensores; a la derecha, los actuadores (listas de variables que se arrastran). En el centro, un marco
de borde fino con la cabecera «(IP:puerto) Esclavo ID:n» y dos columnas de canales: Input e Input Reg a la izquierda, Coil y
Holding Reg a la derecha. El nombre de la variable asignada se escribe fuera del marco, pegado a él. Estilo plano y compacto.
Una barrita de color indica el tipo de la variable (Bool, Decimal, Entera, Cualquiera) y su viveza, si la señal está activa."""
from dataclasses import replace
import json
import copy
from PySide6.QtCore import Signal, Qt, QMimeData, QSize, QRect, QEvent, QRegularExpression, QTimer
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetrics, QPainter, QPixmap, QRegularExpressionValidator
from fractions import Fraction
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QSizePolicy,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
                               QAbstractItemView, QMenu, QApplication, QGridLayout, QStyle,
                               QStyledItemDelegate)

from . import estilo
from .paneles import ContextoNombres, EtiquetaGrupos, TituloSeccion
from conexion.adaptador import texto_numero
from conexion.configuracion import ETIQUETA_CANAL, CONEXION_INICIAL, CANALES_INICIALES, Configuracion, Senal, normalizar_host

AREAS = {"discrete": "Entradas digitales (Discrete Inputs)",
         "coil": "Salidas digitales (Coils)",
         "input-register": "Entradas numéricas (Input Registers)",
         "holding": "Salidas numéricas (Holding Registers)"}
FORMATOS = {"BOOL": "BOOL (apagado/encendido)", "INT16": "INT16 (entero con signo)",
            "UINT16": "UINT16 (entero sin signo)"}
TIPOS = {"bool": "Booleana (0/1)", "int": "Entera", "decimal": "Decimal", "duration": "Duración"}
MIME_VARIABLE = "application/x-grafconnect-variable"
# Host, puerto y esclavo que propone el panel la primera vez, sin nada recordado ni mapa guardado: la configuración inicial del servidor Modbus.
# Después la ventana propone la última conexión que funcionó (`PanelES.conexion_defecto`).

# Aspecto. El color de la barrita es el del tipo; su viveza, el estado: tenue (canal sin asignar), tipo (asignado) y vivo
# (la señal está activa). La leyenda de abajo explica los colores.
FONDO = estilo.SUPERFICIE_2
COLOR_TIPO = {"bool": estilo.TIPO_BOOL, "decimal": estilo.TIPO_DECIMAL, "int": estilo.TIPO_ENTERA}
COLOR_CUALQUIERA = estilo.TIPO_CUALQUIERA
LEYENDA = (("Bool", "bool"), ("Decimal", "decimal"), ("Entera", "int"), ("Cualquiera", None))
NIVEL_TENUE, NIVEL_ASIGNADO, NIVEL_ACTIVO = .28, .62, 1.0
ALTO_FILA = 16  # (a la escala normal; a pantalla completa la vista sube de tamaño: `PanelES.alto_fila`, ver `PanelES.escalar`)
ALTO_VARIABLE = ALTO_FILA
ANCHO_INTERIOR = 200  # la mitad del marco que cae dentro de él: indicador, nombre del canal y, en los registros, su valor
ROL_COLOR, ROL_ASIGNADA, ROL_ACTIVO = (Qt.ItemDataRole.UserRole + n for n in (1, 2, 3))
def estilo_panel(escala: str = "normal") -> str:
    """La hoja de la vista de E/S con la letra de la escala `escala` (`estilo.ESCALAS`): las filas y los nombres de canal suben de 12 a 14 px
    a pantalla completa, como el resto de la interfaz."""
    e = estilo.ESCALAS[escala]
    return f"""
    QWidget#conexionES {{ background:{estilo.FONDO}; }}
    QWidget#conexionES, QWidget#conexionES QLabel, QWidget#conexionES QListWidget {{ font-size:{e["T_ES"]}px; }}
    QWidget#tarjetaES {{ background:white; border:1px solid {estilo.BORDE}; border-radius:{estilo.R_M}px; }}
    QWidget#tarjetaES QLabel {{ border:0; }}
    QWidget#conexionES QLabel#canalES {{ color:{estilo.TINTA_2}; }}
    QWidget#conexionES QLabel#asignacionES {{ color:{estilo.TINTA}; }}
    QWidget#conexionES QLabel#asignacionES[aviso="true"] {{ color:{estilo.AVISO}; }}
    QWidget#conexionES QLabel#valorES {{ color:{estilo.TINTA_2}; font-size:{e["T_ES"]}px; font-family:{estilo.FAMILIA_MONO}; }}
    QWidget#conexionES QLabel#tituloPLC {{ color:{estilo.ACENTO}; font-family:{estilo.FAMILIA_TITULO}; font-size:{e["T_SECCION"]}px; font-weight:600; padding:6px; }}
    QFrame#cabeceraES {{ background:{estilo.SUPERFICIE}; border:0; border-bottom:1px solid {estilo.BORDE}; }}
    QFrame#cabeceraES[estadoVisual="conectado"] {{ background:{estilo.SIMULACION_SUAVE}; border-bottom:2px solid {estilo.SIMULACION}; }}
    QFrame#cabeceraES QWidget {{ background:transparent; }}
    QFrame#cabeceraES QPushButton {{ background:{estilo.SUPERFICIE}; color:{estilo.TINTA}; border:1px solid {estilo.BORDE_CONTROL}; padding:0 14px;
        border-radius:{estilo.R_S}px; min-height:{e["ALTO_CONTROL_COMPACTO"] - 2}px; font-size:{e["T_BASE"]}px; }}
    QFrame#cabeceraES QPushButton:hover {{ background:{estilo.HOVER}; border-color:{estilo.TINTA_2}; }}
    QFrame#cabeceraES QPushButton:pressed {{ background:{estilo.PULSADO}; }}
    QFrame#cabeceraES QPushButton[tecl="true"]:focus {{ border:2px dashed {estilo.FOCO}; padding:0 13px; min-height:{e["ALTO_CONTROL_COMPACTO"] - 4}px; }}
    QFrame#cabeceraES QPushButton:disabled {{ color:{estilo.DESHABILITADO}; background:{estilo.SUPERFICIE_2}; border-color:{estilo.BORDE}; }}
    QFrame#cabeceraES QPushButton[primario="true"] {{ background:{estilo.ACENTO}; color:white; border-color:{estilo.ACENTO_OSCURO}; font-weight:600; }}
    QFrame#cabeceraES QPushButton[primario="true"]:hover {{ background:{estilo.ACENTO_HOVER}; }}
    QFrame#cabeceraES QPushButton[primario="true"][tecl="true"]:focus {{ border:2px dashed white; }}
    QWidget#conexionES QLabel#tituloES {{ color:{estilo.TINTA}; font-size:{e["T_TITULO"]}px; font-weight:700; padding-left:4px; }}
    QWidget#cuerpoES, QFrame#pieES {{ background:transparent; }}
    QWidget#cuerpoES QLabel, QFrame#pieES QLabel {{ color:{estilo.TINTA_2}; background:transparent; }}
    QWidget#conexionES QLabel#seccionES {{ color:{estilo.ACENTO}; font-family:{estilo.FAMILIA_TITULO}; font-size:{e["T_SECCION"]}px; font-weight:600; padding:6px; }}  /* como los títulos de sección del resto: tipo de título, acento, sin mayúsculas */
    QWidget#conexionES QLabel#ayudaES, QWidget#conexionES QLabel#resumenES {{ color:{estilo.TINTA_2}; }}
    QFrame#moduloPLC {{ background:transparent; border:1px solid {estilo.BORDE_CONTROL}; }}
    QListWidget#listaES {{ background:transparent; border:0; outline:0; }}
    QListWidget#listaES[tecl="true"]:focus {{ border:2px dashed {estilo.FOCO}; }}
    QScrollArea#scrollES {{ background:white; border:1px solid {estilo.BORDE}; border-radius:{estilo.R_M}px; }}
    QScrollArea#scrollES > QWidget > QWidget {{ background:white; }}
    QScrollArea#scrollCuerpoES, QScrollArea#scrollCuerpoES > QWidget > QWidget#cuerpoES {{ background:transparent; }}
    QWidget#conexionES QScrollBar:vertical {{ background:{estilo.BORDE}; width:{estilo.ANCHO_BARRA}px; margin:0; border-radius:{estilo.ANCHO_BARRA // 2}px; }}
    QWidget#conexionES QScrollBar::handle:vertical {{ background:{estilo.BORDE_CONTROL}; border-radius:{estilo.ANCHO_BARRA // 2 - 1}px; margin:1px; min-height:36px; }}
    QWidget#conexionES QScrollBar:horizontal {{ background:{estilo.BORDE}; height:{estilo.ANCHO_BARRA}px; margin:0; border-radius:{estilo.ANCHO_BARRA // 2}px; }}
    QWidget#conexionES QScrollBar::handle:horizontal {{ background:{estilo.BORDE_CONTROL}; border-radius:{estilo.ANCHO_BARRA // 2 - 1}px; margin:1px; min-width:36px; }}
    QWidget#conexionES QScrollBar::add-line, QWidget#conexionES QScrollBar::sub-line {{ height:0; width:0; }}
    QWidget#conexionES QScrollBar::add-page, QWidget#conexionES QScrollBar::sub-page {{ background:transparent; }}
    QPushButton#quitarES {{ background:transparent; color:{estilo.TINTA_2}; border:0; padding:0; font-size:14px; min-height:0; }}
    QPushButton#quitarES:hover {{ color:{estilo.ERROR}; }}
    QPushButton#quitarES[tecl="true"]:focus {{ border:1px dashed {estilo.FOCO}; padding:0; }}
    QPushButton#quitarES:disabled {{ color:{estilo.DESHABILITADO}; background:transparent; }}
"""


ESTILO_PANEL = estilo_panel()


def mezclar(color, nivel):
    """El color sobre el fondo: nivel 1 es el color entero; menos, más apagado."""
    if nivel < NIVEL_ACTIVO:
        return QColor(estilo.SENAL_TENUE if nivel < NIVEL_ASIGNADO else estilo.SENAL_ASIGNADA)  # (3,5:1 sobre blanco; la barrita lleva además un borde de 3,5:1)
    c, f = QColor(color).getRgb(), QColor(FONDO).getRgb()
    return QColor(*(round(f[i] + (c[i] - f[i]) * nivel) for i in range(3)))


def color_tipo(variable):
    return COLOR_TIPO.get(variable["type"]["kind"], COLOR_CUALQUIERA)


def encaja(variable, area):
    """Si la variable puede asignarse (arrastrándola) a un canal de esa área: papel y tipo casan con ella."""
    tipo = variable["type"]["kind"]
    return variable["role"] == ("input" if area in ("discrete", "input-register") else "output") and (
        tipo == "bool" if area in ("discrete", "coil") else tipo in ("int", "decimal"))


def aviso_escala(variable, senal):
    """Aviso (ámbar) si una variable Entera va a un registro con escala distinta de 1, como la del simulador de procesos (100):
    la planta manda valores con decimales y una Entera los redondea. Solo para lo que el programa RECIBE (entradas): una salida
    Entera con escala 100 (5 → 500) no pierde nada. Cadena vacía si no hay nada que avisar."""
    if variable is None or senal is None or variable["role"] != "input" or variable["type"]["kind"] != "int"             or senal.formato == "BOOL":
        return ""
    try:
        escala = Fraction(senal.escala)
    except (ValueError, ZeroDivisionError, TypeError):
        return ""
    if escala == 1:
        return ""
    return ("El simulador de procesos manda este valor con decimales: se redondeará al entero más cercano. "
            "Para el valor exacto, ponga la variable como Decimal (2 decimales).")


def aviso_redondeo(recibido, usado):
    """El aviso (ámbar) de una Entera que ya ha recibido un valor con decimales y lo ha redondeado."""
    return (f"El simulador de procesos ha enviado {texto_numero(recibido)} y la variable es Entera: se usa "
            f"{texto_numero(usado)}. Para el valor exacto, póngala como Decimal (2 decimales).")


def areas_variable(variable):
    """Las áreas que ofrece la tabla para la variable (la primera es la propuesta)."""
    digital = variable["type"]["kind"] == "bool"
    if variable["role"] == "input":
        return ["discrete", "coil"] if digital else ["input-register", "holding"]
    return ["coil"] if digital else ["holding"]


class IndicadorES(QWidget):
    """Barrita (o cuadrito) de color: uno o dos colores y un nivel de viveza. No recibe el ratón."""

    def __init__(self, ancho=4, alto=12):
        super().__init__()
        self.setFixedSize(ancho, alto)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.colores, self.nivel = (COLOR_CUALQUIERA,), NIVEL_TENUE

    def fijar(self, colores, nivel):
        colores = tuple(colores)
        if (colores, nivel) != (self.colores, self.nivel):
            self.colores, self.nivel = colores, nivel
            self.update()

    def fijar_nivel(self, nivel):
        self.fijar(self.colores, nivel)

    def color(self):
        """El primer color tal como se ve (con su viveza)."""
        return mezclar(self.colores[0], self.nivel)

    def paintEvent(self, _evento):
        p = QPainter(self)
        n = len(self.colores)
        for i, c in enumerate(self.colores):
            y0, y1 = i * self.height() // n, (i + 1) * self.height() // n
            p.fillRect(0, y0, self.width(), y1 - y0, mezclar(c, self.nivel))
        p.setPen(QColor(estilo.BORDE_CONTROL))  # el contorno cumple los 3:1 que no cumplen los tonos tenues sobre blanco
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)


class EtiquetaElidida(QLabel):
    """Etiqueta de una línea que, si no cabe, acaba en «…» (el texto completo sigue en text() y en el tooltip)."""

    def __init__(self, texto="", alineacion=Qt.AlignmentFlag.AlignLeft):
        super().__init__(texto)
        self.setAlignment(alineacion | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.contexto = None  # los nombres de su lista: el recorte no confunde dos (`ContextoNombres`); sin él, se corta por el final

    def texto_visible(self):
        fm = QFontMetrics(self.font())
        if self.contexto is None:
            return fm.elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        return self.contexto.elidir(self.text(), fm, self.width())

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setPen(self.palette().windowText().color())
        p.setFont(self.font())
        p.drawText(self.rect(), int(self.alignment()), self.texto_visible())


def _pintar_variable(p, rect, texto, color, activa, derecha, resaltado=False, letra=None, contexto=None):
    fuente = QFont(p.font()); fuente.setPixelSize(letra or ESCALAS_ES["normal"]); p.setFont(fuente)
    fm = QFontMetrics(fuente)
    if resaltado:
        p.fillRect(rect, QColor(estilo.RESALTADO))
    p.setPen(QColor(estilo.TINTA))
    tr = rect.adjusted(6, 0, -6, 0)
    # un nombre largo conserva lo que lo distingue de los demás de su lista (sensor_…_10_avance frente a sensor_…_20_avance)
    visible = contexto.elidir(texto, fm, tr.width()) if contexto is not None else fm.elidedText(texto, Qt.TextElideMode.ElideMiddle, tr.width())
    p.drawText(tr, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, visible)


ESCALAS_ES = {"normal": estilo.ESCALAS["normal"]["T_ES"], "grande": estilo.ESCALAS["grande"]["T_ES"]}  # letra de las filas, por escala


def figura_variable(texto, color, derecha, activa=False, letra=None, alto=None):
    fuente = QFont(estilo.FUENTE); fuente.setPixelSize(letra or ESCALAS_ES["normal"])
    pm = QPixmap(QFontMetrics(fuente).horizontalAdvance(texto) + 18, alto or ALTO_VARIABLE)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setFont(fuente)
    _pintar_variable(p, pm.rect(), texto, color, activa, derecha, False, letra); p.end()
    return pm


class DelegadoVariable(QStyledItemDelegate):
    """Nombre alineado a la izquierda; la fila completa sirve para seleccionar y arrastrar."""
    def __init__(self, padre, barra_a_la_derecha):
        super().__init__(padre)
        self.derecha = barra_a_la_derecha

    def sizeHint(self, _opcion, _indice):
        return QSize(0, getattr(self.parent(), "alto", ALTO_VARIABLE))

    def paint(self, p, opcion, indice):
        p.save()
        lista = self.parent()
        _pintar_variable(p, opcion.rect.adjusted(4,1,-4,-1), indice.data() or "", indice.data(ROL_COLOR),
                         indice.data(ROL_ACTIVO), self.derecha,
                         bool(opcion.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)),
                         getattr(lista, "letra", None), getattr(lista, "contexto", None))
        p.restore()

    def texto_visible(self, indice, ancho):
        """Lo que se ve de esa fila de la lista con `ancho` px de fila (para comprobarlo sin mirar píxeles)."""
        lista = self.parent()
        fuente = QFont(estilo.FUENTE)
        fuente.setPixelSize(getattr(lista, "letra", None) or ESCALAS_ES["normal"])
        return lista.contexto.elidir(indice.data() or "", QFontMetrics(fuente), ancho - 8 - 12)


class ListaVariables(QListWidget):
    def __init__(self, lado="entrada"):
        super().__init__()
        self.setObjectName("listaES")
        self.letra, self.alto = ESCALAS_ES["normal"], ALTO_VARIABLE  # la letra y el alto de fila de la escala de ahora (`PanelES.escalar`)
        self.contexto = ContextoNombres()  # los nombres de la lista, para que el recorte no confunda dos
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.setItemDelegate(DelegadoVariable(self, lado == "entrada"))

    def startDrag(self, actions):
        it = self.currentItem()
        if it is None:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData([it]))
        figura = figura_variable(it.text(), it.data(ROL_COLOR), self.itemDelegate().derecha, it.data(ROL_ACTIVO), self.letra, self.alto)
        drag.setPixmap(figura)
        drag.setHotSpot(figura.rect().center())
        drag.exec(Qt.DropAction.CopyAction)

    def mimeData(self, items):
        datos = QMimeData()
        if items:
            datos.setData(MIME_VARIABLE, items[0].data(Qt.ItemDataRole.UserRole).encode("utf-8"))
        return datos


class TerminalES(QFrame):
    """Un canal: el lateral exterior al PLC es la zona donde soltar una variable. Dentro del marco, el indicador y el nombre del canal
    (y el valor, en los registros); fuera, a su lado, el nombre de la variable asignada y, al pasar el ratón, «×»."""

    def __init__(self, panel, area, direccion, variable=None, aviso=""):
        super().__init__(panel)
        self.panel, self.area, self.direccion, self.variable = panel, area, direccion, variable
        self.aviso = aviso
        self._inicio_arrastre = None
        self._resaltado = False
        self.setAcceptDrops(not panel.bloqueado)
        self.setObjectName("senalPLC")
        alto = getattr(panel, "alto_fila", ALTO_FILA)  # (el de la escala de ahora: 16 px, y 20 a pantalla completa)
        self.setFixedHeight(alto)
        entrada = area in ("discrete", "input-register")
        analogica = area in ("input-register", "holding")
        self.led = IndicadorES()
        if variable:
            self.led.fijar((color_tipo(variable),), NIVEL_ASIGNADO)
        else:  # sin asignar: tenue, con el color propio del área (los registros admiten Decimal y Entera)
            self.led.fijar((COLOR_TIPO["decimal"], COLOR_TIPO["int"]) if analogica else (COLOR_TIPO["bool"],), NIVEL_TENUE)
        self.canal = QLabel(f"{ETIQUETA_CANAL[area]} {direccion}")
        self.canal.setObjectName("canalES")  # (su color, en la hoja del panel: una hoja por etiqueta costaba 3 de cada 88 filas)
        self.nombre = EtiquetaElidida(variable["name"] if variable else "",
                                      Qt.AlignmentFlag.AlignRight if entrada else Qt.AlignmentFlag.AlignLeft)
        self.nombre.setObjectName("asignacionES")  # lo que se agarra para mover la asignación a otro canal
        self.nombre.contexto = panel.contexto_de(area)  # (los nombres de ese lado: dos canales no se leen igual aunque el recorte coma)
        self.nombre.setProperty("aviso", bool(aviso))  # ámbar si lleva aviso (hoja del panel: `QLabel#asignacionES[aviso="true"]`)
        self.marca = None
        if aviso:  # señal ámbar junto a la fila: no impide nada, solo avisa
            self.marca = self._crear_marca(aviso)
        self.nombre.setToolTip(self._ayuda_nombre(aviso))  # el nombre entero, aunque la etiqueta lo recorte con «…»
        self.valor = QLabel("—" if variable else "", self)
        self.valor.setObjectName("valorES")  # cifra en la letra técnica, color y tamaño en la hoja del panel
        self.valor.setVisible(analogica)
        self.barrita_nombre = IndicadorES(6, 13)
        self.barrita_nombre.hide()  # el estado se muestra solo en el indicador del canal del PLC
        interior = QWidget()
        self.interior = interior
        interior.setFixedWidth(getattr(panel, "ancho_interior", ANCHO_INTERIOR))
        il = QHBoxLayout(interior)
        il.setContentsMargins(3, 0, 3, 0)
        il.setSpacing(6)
        if entrada:
            for w in (self.led, self.canal):
                il.addWidget(w)
            il.addStretch()
            il.addWidget(self.valor)
        else:
            il.addWidget(self.valor)
            il.addStretch()
            for w in (self.canal, self.led):
                il.addWidget(w)
        for w in (interior, self.canal, self.nombre, self.valor):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.b_quitar = None
        if variable:
            self.b_quitar = QPushButton("×")
            self.b_quitar.setObjectName("quitarES")
            self.b_quitar.setFixedSize(18, alto - 2)
            self.b_quitar.setToolTip("Desconecta para desasignar" if panel.bloqueado else "Desasignar esta señal")
            self.b_quitar.setEnabled(not panel.bloqueado)
            self.b_quitar.clicked.connect(lambda: panel.quitar(variable["id"]))
            self.b_quitar.hide()  # solo al pasar el ratón por la fila
        l = QHBoxLayout(self)
        self._diseno = l
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        if entrada:
            if self.b_quitar:
                l.addWidget(self.b_quitar)
            if self.marca:  # por el lado exterior: el nombre sigue pegado al marco del PLC
                l.addWidget(self.marca)
            l.addWidget(self.nombre, 1)
            l.addWidget(self.barrita_nombre)
            l.addSpacing(8)
            l.addWidget(interior)
        else:
            l.addWidget(interior)
            l.addSpacing(8)
            l.addWidget(self.barrita_nombre)
            l.addWidget(self.nombre, 1)
            if self.marca:
                l.addWidget(self.marca)
            if self.b_quitar:
                l.addWidget(self.b_quitar)
        self.setToolTip(f"{AREAS[area]} · dirección {direccion}\nArrastra una variable. Botón derecho para quitar o configurar.")

    def _ayuda_nombre(self, aviso=""):
        """Ayuda de la etiqueta del nombre: el nombre entero (la etiqueta lo recorta) y, si lo hay, el aviso."""
        nombre = self.variable["name"] if self.variable else ""
        return "\n".join(x for x in (nombre, aviso) if x)

    @staticmethod
    def _crear_marca(texto):
        marca = QLabel("⚠")
        marca.setStyleSheet(f"color:{estilo.AVISO}; font-size:12px")
        marca.setToolTip(texto)
        return marca

    def fijar_redondeo(self, texto):
        """Marca la fila en ámbar con el aviso de un redondeo recibido (sustituye al preventivo mientras dure)."""
        texto = texto or self.aviso
        if texto and self.marca is None:
            self.marca = self._crear_marca(texto)
            entrada = self.area in ("discrete", "input-register")
            self._diseno.insertWidget(self._diseno.indexOf(self.nombre) + (0 if entrada else 1), self.marca)
        if self.marca is not None:
            self.marca.setToolTip(texto)
            self.marca.setVisible(bool(texto))
        self.nombre.setToolTip(self._ayuda_nombre(texto))
        estilo.poner(self.nombre, aviso=bool(texto))

    def mimeData(self):
        datos = QMimeData()
        if self.variable:
            datos.setData(MIME_VARIABLE, self.variable["id"].encode("utf-8"))
        return datos

    def resaltado(self):
        return self._resaltado

    def _resaltar(self, on):
        self._resaltado = on
        self.update()

    def zona_asignacion(self):
        """Solo el lateral fuera del PLC: izquierda para sensores, derecha para actuadores."""
        r = self.interior.geometry()
        if self.area in ("discrete", "input-register"):
            return QRect(0, 0, r.left(), self.height())
        return QRect(r.right()+1, 0, max(0, self.width()-r.right()-1), self.height())

    def paintEvent(self, evento):
        super().paintEvent(evento)
        if self._resaltado:
            QPainter(self).fillRect(self.zona_asignacion(), QColor(estilo.ASIGNACION))

    def detalle(self):
        """Lo que cuenta la línea de detalle de la ventana al pasar por la fila: el nombre entero, el canal y el tipo."""
        if not self.variable:
            return ""
        return f"{self.variable['name']} · {self.canal.text()} · {TIPOS[self.variable['type']['kind']]}"

    def enterEvent(self, evento):
        if self.b_quitar is not None and self.b_quitar.isEnabled():
            self.b_quitar.show()
        self.update()
        self.panel.detalle.emit(self.detalle())
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        if self.b_quitar is not None:
            self.b_quitar.hide()
        self.update()
        self.panel.detalle.emit("")
        super().leaveEvent(evento)

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            self._inicio_arrastre = evento.position().toPoint()
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento):
        if self.panel.bloqueado or self.variable is None or self._inicio_arrastre is None:
            return
        if evento.buttons() & Qt.MouseButton.LeftButton and (evento.position().toPoint() - self._inicio_arrastre).manhattanLength() >= QApplication.startDragDistance():
            self._inicio_arrastre = None
            arrastre = QDrag(self.panel)
            arrastre.setMimeData(self.mimeData())
            arrastre.setPixmap(figura_variable(self.variable["name"], color_tipo(self.variable), self.area in ("discrete", "input-register")))
            arrastre.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.MoveAction)

    def _variable_evento(self, evento):
        if self.panel.bloqueado or not evento.mimeData().hasFormat(MIME_VARIABLE):
            return None
        try:
            vid = bytes(evento.mimeData().data(MIME_VARIABLE)).decode("utf-8")
        except UnicodeError:
            return None
        return vid if self.panel.admite(vid, self.area) else None

    def dragEnterEvent(self, evento):
        if self._variable_evento(evento):
            self._resaltar(self.zona_asignacion().contains(evento.position().toPoint()))
            evento.acceptProposedAction()  # permite continuar hacia el lateral sin salir de la fila

    def dragMoveEvent(self, evento):
        valido = bool(self._variable_evento(evento)) and self.zona_asignacion().contains(evento.position().toPoint())
        self._resaltar(valido)
        if valido:
            evento.acceptProposedAction()
        else:
            evento.ignore()

    def dragLeaveEvent(self, evento):
        self._resaltar(False)
        evento.accept()

    def dropEvent(self, evento):
        self._resaltar(False)
        vid = self._variable_evento(evento)
        if vid and self.zona_asignacion().contains(evento.position().toPoint()) and self.panel.asignar(vid, self.area, self.direccion):
            evento.acceptProposedAction()

    def contextMenuEvent(self, evento):
        if self.panel.bloqueado or not self.variable:
            return
        menu = QMenu(self)
        quitar = menu.addAction("Quitar asignación")
        ajustar = menu.addAction("Configurar señal…")
        elegido = menu.exec(evento.globalPos())
        if elegido == quitar:
            self.panel.quitar(self.variable["id"])
        elif elegido == ajustar:
            self.panel.abrir_configuracion()


class LienzoPLC(QWidget):
    """El centro: la cabecera del servidor y las dos columnas de canales (las filas llevan fuera del marco el nombre de la
    variable). El marco de borde fino es una capa transparente encima que no recibe el ratón: abarca la mitad interior de
    cada fila, de modo que los nombres quedan fuera y se pegan a él."""

    def __init__(self):
        super().__init__()
        self.setObjectName("lienzoES")
        self.ancho_interior = ANCHO_INTERIOR
        rejilla = QGridLayout(self)
        rejilla.setContentsMargins(0, 2, 0, 2)
        rejilla.setSpacing(0)
        titulo = QLabel("PLC · Modbus TCP")
        titulo.setObjectName("tituloPLC")
        rejilla.addWidget(titulo, 0, 0, 1, 2)
        self.destino = QLabel()
        self.destino.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.destino.setFixedSize(2 * self.ancho_interior, 36)
        self.izq, self.der = QWidget(), QWidget()
        self.fila_izq, self.fila_der = QVBoxLayout(self.izq), QVBoxLayout(self.der)
        for f in (self.fila_izq, self.fila_der):
            f.setContentsMargins(0, 0, 0, 0)
            f.setSpacing(0)
        self.ayuda = QLabel("Arrastra las variables a las entradas y salidas.", self)
        self.ayuda.setObjectName("ayudaES")
        self.ayuda.setWordWrap(True)
        self.ayuda.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ayuda.setContentsMargins(0, 0, 0, 0)
        self.ayuda.setMinimumHeight(20)
        rejilla.addWidget(self.destino, 1, 0, 1, 2, Qt.AlignmentFlag.AlignHCenter)
        rejilla.addWidget(self.izq, 2, 0, Qt.AlignmentFlag.AlignTop)
        rejilla.addWidget(self.der, 2, 1, Qt.AlignmentFlag.AlignTop)
        self.ayuda.hide()  # las instrucciones siguen en los tooltips de los canales
        rejilla.setColumnStretch(0, 1)
        rejilla.setColumnStretch(1, 1)
        rejilla.setRowStretch(4, 1)
        self.marco = QFrame(self)
        self.marco.setObjectName("moduloPLC")
        self.marco.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMinimumWidth(2 * self.ancho_interior + 120)

    def fijar_interior(self, ancho):
        """El ancho de la mitad del marco que cae dentro de él (más ancho con la letra grande)."""
        self.ancho_interior = ancho
        self.destino.setFixedSize(2 * ancho, 36)
        self.setMinimumWidth(2 * ancho + 120)
        self._colocar_marco()

    def event(self, evento):  # noqa: N802
        resultado = super().event(evento)
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest, QEvent.Type.Show, QEvent.Type.Polish):
            self._colocar_marco()
        return resultado

    def _colocar_marco(self):
        g, d, c = self.izq.geometry(), self.der.geometry(), self.destino.geometry()
        x0, x1 = g.right() + 1 - self.ancho_interior, d.left() + self.ancho_interior
        y1 = max(g.bottom() if self.fila_izq.count() else 0, d.bottom() if self.fila_der.count() else 0, c.bottom()) + 5
        self.marco.setGeometry(x0, c.top(), x1 - x0, y1 - c.top())
        self.marco.raise_()


class EstadoConexion(QLabel):
    """El estado de la conexión: una frase corta si es de las conocidas y, si no, el mensaje entero. Hace salto de línea y
    crece en alto (nunca se corta); el texto completo también va en el tooltip y se puede seleccionar para copiarlo. La nota
    (asignaciones quitadas, variables nuevas pendientes…) va detrás de cualquier estado y sobrevive a que se reescriba."""

    def __init__(self):
        super().__init__()
        self.nota, self._texto = "", ""
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def fijar_nota(self, nota):
        if nota != self.nota:
            self.nota = nota
            self.setText(self._texto)

    def setText(self, texto):
        self._texto = texto
        self.setToolTip(texto + (f" · {self.nota}" if self.nota else ""))
        if texto.startswith("Conectado"):
            corto = "Conectado"
        elif texto.startswith(("Prueba preparada", "Mapa aplicado", "Configuración guardada", "Mapa cargado")):
            corto = "Desconectado"
        elif texto.startswith("Desconectado"):
            corto = "Revisar GRAFCET" if "GRAFCET" in texto else "Desconectado"
        elif texto.startswith("Conexión probada"):
            corto = "Conexión probada"
        else:
            corto = texto
        super().setText(corto + (f" · {self.nota}" if self.nota else ""))


class _SinRueda:
    def wheelEvent(self, evento):  # noqa: N802
        # Qt propaga la rueda ignorada al padre (tabla/área desplazable), sin editar el campo.
        evento.ignore()


class _SpinConfiguracion(_SinRueda, QSpinBox):
    pass


class _ComboConfiguracion(_SinRueda, QComboBox):
    pass


class _Octeto(QLineEdit):
    """Una de las cuatro cajas de la IP: solo cifras, hasta 255. Tres cifras o un punto pasan a la siguiente; Retroceso en
    una caja vacía vuelve a la anterior; pegar «a.b.c.d» reparte los números."""

    def __init__(self, campo, indice):
        super().__init__()
        self.campo, self.indice, self._previo = campo, indice, ""
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(46)
        self.setMaxLength(15)  # lo que cabe al pegar una IP entera; al teclear nunca pasa de 3
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9.]*"), self))
        self.setStyleSheet("padding: 4px 2px")
        self.textEdited.connect(self._editado)

    def _editado(self, texto):
        texto = texto.strip()
        if "." in texto or len(texto) > 3:
            if self.campo._repartir(texto, self.indice):
                return
            texto = self._previo
        elif texto and int(texto) > 255:
            texto = self._previo
        if texto != self.text():
            self.setText(texto)
        self._previo = texto
        if len(texto) == 3 and self.cursorPosition() == 3:
            self.campo._ir_a(self.indice + 1)

    def keyPressEvent(self, e):
        clave = e.key()
        if clave in (Qt.Key.Key_Period, Qt.Key.Key_Comma, Qt.Key.Key_Space) or e.text() == ".":
            if self.text():
                self.campo._ir_a(self.indice + 1)
            e.accept()
            return
        if clave == Qt.Key.Key_Backspace and not self.text() and not self.hasSelectedText():
            self.campo._ir_a(self.indice - 1, al_final=True)
            e.accept()
            return
        if clave == Qt.Key.Key_Left and self.cursorPosition() == 0 and not self.hasSelectedText():
            self.campo._ir_a(self.indice - 1, al_final=True)
            e.accept()
            return
        if clave == Qt.Key.Key_Right and self.cursorPosition() == len(self.text()) and not self.hasSelectedText():
            self.campo._ir_a(self.indice + 1)
            e.accept()
            return
        super().keyPressEvent(e)

    def sin_ceros(self):
        """Al salir de la caja: «010» pasa a «10» y «000» a «0»."""
        if self.text().isdigit() and self.text() != str(int(self.text())):
            self.setText(str(int(self.text())))
            self._previo = self.text()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.sin_ceros()
        QTimer.singleShot(0, self.campo._comprobar_salida)


class CampoIPv4(QWidget):
    """Dirección IPv4 en cuatro cajas con los puntos fijos entre ellas. Mismo uso que un QLineEdit en lo que necesita el panel:
    `text()`, `setText()` y la señal `editingFinished` (al salir de la dirección o pulsar Intro)."""
    editingFinished = Signal()
    NOMBRES = ("primer", "segundo", "tercer", "cuarto")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self.cajas = []
        for i in range(4):
            if i:
                punto = QLabel(".")
                punto.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lay.addWidget(punto)
            caja = _Octeto(self, i)
            caja.setAccessibleName(f"IP, {self.NOMBRES[i]} número")
            caja.returnPressed.connect(self._intro)
            lay.addWidget(caja)
            self.cajas.append(caja)
        lay.addStretch(1)
        for anterior, caja in zip(self.cajas, self.cajas[1:]):
            self.setTabOrder(anterior, caja)
        self.setFocusProxy(self.cajas[0])
        self.setAccessibleName("IP (Host)")

    def text(self):
        return ".".join(c.text() for c in self.cajas)

    def _intro(self):
        for caja in self.cajas:
            caja.sin_ceros()
        self.editingFinished.emit()

    def setText(self, texto):
        partes = normalizar_host(texto).split(".")
        for caja, parte in zip(self.cajas, partes):
            caja.setText(parte)
            caja._previo = parte

    def _ir_a(self, indice, al_final=False):
        if 0 <= indice < 4:
            caja = self.cajas[indice]
            caja.setFocus(Qt.FocusReason.TabFocusReason)
            if al_final:
                caja.setCursorPosition(len(caja.text()))
            else:
                caja.selectAll()

    def _repartir(self, texto, desde):
        """Reparte un texto pegado «a.b.c.d» (entero, desde la primera caja; o parte de él, desde la caja `desde`). False si no son números de 0 a 255."""
        partes = texto.replace(",", ".").split(".")
        if partes and partes[-1] == "" and len(partes) > 1:
            partes.pop()  # un punto final: «192.168.» se trata como «192.168»
        if len(partes) == 4:
            desde = 0  # una dirección entera se reparte desde la primera caja, sea cual sea la que se pegó
        if not partes or len(partes) > 4 - desde or not all(p.isdigit() and len(p) <= 3 and int(p) <= 255 for p in partes):
            return False
        for caja, parte in zip(self.cajas[desde:], partes):
            caja.setText(parte)
            caja._previo = parte
        self._ir_a(min(desde + len(partes), 3))
        return True

    def _comprobar_salida(self):
        if not any(c.hasFocus() for c in self.cajas):
            self.editingFinished.emit()


class DialogoConfiguracion(QDialog):
    def closeEvent(self, evento):
        panel = self.parent()
        if panel.bloqueado or panel.doc is None or panel._aplicar():
            evento.accept()
        else:
            evento.ignore()


class PanelES(QWidget):
    aplicar = Signal(object)
    conectar = Signal()
    desconectar = Signal()
    probar = Signal()
    guardar = Signal()
    cargar_archivo = Signal()
    abrir_prueba = Signal()
    volver = Signal()
    estado_cambiado = Signal(str, str)  # (estado, mensaje): lo que enseña el indicador de la barra de simulación
    detalle = Signal(str)  # el nombre entero (y canal, tipo) de la fila que señala el puntero: la ventana lo pone en su barra de estado

    def escalar(self, hoja_ventana: str = "", escala: str = "normal") -> None:
        """Pone la vista a la escala `escala` (pantalla completa o no): la hoja (la de la ventana para esa escala, si hay, y la propia), la
        letra, el alto de las filas y el ancho de lo que cae dentro del marco. Las filas se rehacen con su alto nuevo. La ventana lo llama
        al mostrar la vista (no al cruzar el umbral): son más de mil widgets. Sin argumentos, la escala normal."""
        e = estilo.ESCALAS[escala]
        letra_vieja = self.letra
        self.escala, self.alto_fila, self.ancho_interior, self.letra = escala, e["ALTO_FILA_ES"], e["ANCHO_INTERIOR_ES"], e["T_ES"]
        self.check.setStyleSheet(self.check.styleSheet().replace(f"font-size:{letra_vieja}px", f"font-size:{self.letra}px"))
        fuente = QFont(self.font())
        fuente.setPixelSize(self.letra)
        self.setFont(fuente)
        self.setStyleSheet(hoja_ventana + estilo_panel(escala))
        self.lienzo.fijar_interior(self.ancho_interior)
        for lista in (self.lista_entradas, self.lista_salidas):
            lista.letra, lista.alto = self.letra, self.alto_fila
        self.contexto_izq.fijar(()); self.contexto_der.fijar(())  # (se rehacen con las filas)
        if self.doc is not None:
            self._dibujar()
            self.mostrar_valores(self._ultimos_valores)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("conexionES")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.escala, self.alto_fila, self.ancho_interior, self.letra = "normal", ALTO_FILA, ANCHO_INTERIOR, ESCALAS_ES["normal"]
        self.contexto_izq, self.contexto_der = ContextoNombres(), ContextoNombres()  # los nombres asignados a cada lado del PLC
        self._ultimos_valores = {}
        fuente = QFont(self.font())
        fuente.setPixelSize(self.letra)  # letra algo menor: caben más canales
        self.setFont(fuente)
        self.setStyleSheet(estilo_panel())
        self.doc = None
        self._cargando = True
        self.parametros_defecto = {}
        self.escalas_base = {}
        self._hubo_conexion = False
        self.config = Configuracion()
        self.variables = []
        self.firma_modelo = ()
        self.conexion_defecto = CONEXION_INICIAL  # (host, puerto, esclavo) que propone `cargar` si no hay mapa guardado
        self.aviso = ""  # asignaciones quitadas al poner al día con el modelo; dura hasta la siguiente acción sobre el mapa
        self.aviso_host_defecto = ""  # la dirección recordada no era una IP (la ventana lo dice): se avisa en el mapa nuevo
        self.aviso_host = ""  # lo mismo, ya en el estado: hasta que el usuario aplique el mapa con una IP escrita
        self.pista_canales = ""  # variables sin dónde asignarse porque su área tiene cantidad 0
        self.redondeos = {}  # {variable: (recibido, usado)} de la conexión; ver mostrar_redondeos
        self.avisos_escala = ""  # variables Enteras con escala distinta de 1 (ámbar, junto a su fila y en la nota)
        self.pendiente = False  # con la conexión viva: hay variables nuevas que se verán al desconectar
        self.indicadores = {}
        self.indicadores_listas = {}
        self.terminales = {}
        self.bloqueado = False
        self.extras = {a: set() for a in AREAS}
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        # Cabecera: volver y título arriba; debajo, el estado de la conexión, que hace salto de línea y nunca se corta.
        # Los botones de Conectar y Configuración se añaden a la fila de arriba más abajo.
        banda = self.cabecera = QFrame()
        banda.setProperty("estadoVisual", "neutro")
        banda.setObjectName("cabeceraES")
        cabeza = QVBoxLayout(banda)
        cabeza.setContentsMargins(0, 0, 0, 0)
        cabeza.setSpacing(0)
        fila_alta = QWidget()
        fila_alta.setFixedHeight(estilo.ALTO_CONTROL + 8)
        cabecera = QHBoxLayout(fila_alta)
        cabecera.setContentsMargins(estilo.E3, 0, estilo.E3, 0)
        cabecera.setSpacing(estilo.E2)
        self.b_volver = QPushButton("←")
        self.b_volver.setFixedSize(estilo.ALTO_CONTROL, estilo.ALTO_CONTROL - 2)
        self.b_volver.setToolTip("Volver al GRAFCET")
        self.b_volver.setStyleSheet("font-size:18px; padding:0")
        self.b_volver.clicked.connect(self.volver)
        cabecera.addWidget(self.b_volver)
        titulo = QLabel("Asignación de E/S")
        titulo.setObjectName("tituloES")
        cabecera.addWidget(titulo)
        cabecera.addStretch()
        fila_estado = QWidget()
        fe = QHBoxLayout(fila_estado)
        fe.setContentsMargins(16, 0, 16, 7)
        fe.setSpacing(6)
        self.check = QLabel("●")
        self.check.setFixedSize(16, 16)
        self.check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.check.setStyleSheet(f"color:{estilo.TINTA_3}; font-size:{self.letra}px")
        fe.addWidget(self.check, 0, Qt.AlignmentFlag.AlignTop)
        self.estado = EstadoConexion()
        self.estado.setText("Desconectado")
        self.estado.setStyleSheet(f"color:{estilo.TINTA_2}")
        fe.addWidget(self.estado, 1)
        self.tiempos = QLabel()
        self.tiempos.setTextFormat(Qt.TextFormat.PlainText)
        self.tiempos.hide()
        fe.addWidget(self.tiempos)
        cabeza.addWidget(fila_alta)
        cabeza.addWidget(fila_estado)
        self.b_configuracion = QPushButton("Configuración")
        self.b_configuracion.setToolTip("Servidor Modbus, cantidad de canales y asignaciones")
        self.b_configuracion.clicked.connect(self.abrir_configuracion)
        raiz.addWidget(banda)
        # Cuerpo: sensores | marco del servidor con sus canales | actuadores
        cuerpo = QWidget()
        cuerpo.setObjectName("cuerpoES")
        zona = QGridLayout(cuerpo)
        zona.setContentsMargins(estilo.E2, 6, estilo.E2, estilo.E1)
        zona.setSpacing(6)
        self._zona = zona
        self.lienzo = LienzoPLC()
        self.modulo = self.lienzo.marco
        self.destino = self.lienzo.destino
        self.fila_entradas, self.fila_salidas = self.lienzo.fila_izq, self.lienzo.fila_der
        self.ayuda_vacio = self.lienzo.ayuda
        scroll = QScrollArea()
        scroll.setObjectName("scrollES")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.lienzo)
        self.cuentas = {}
        self.lista_entradas, self.lista_salidas = ListaVariables("entrada"), ListaVariables("salida")
        columnas = []
        for rol, lista in (("input", self.lista_entradas), ("output", self.lista_salidas)):
            columna = QWidget()
            columna.setObjectName("tarjetaES")
            columna.setMinimumWidth(144)
            cl = QVBoxLayout(columna)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)
            etiqueta = TituloSeccion("Sensores" if rol == "input" else "Actuadores", 6)
            etiqueta.setObjectName("seccionES")
            etiqueta.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)  # (con el centrado vertical, el cuadrado queda a la altura del texto)
            etiqueta.setTextFormat(Qt.TextFormat.RichText)
            cl.addWidget(etiqueta)
            cl.addWidget(lista, 1)
            self.cuentas[rol] = etiqueta
            columnas.append(columna)
        self._partes = (columnas[0], scroll, columnas[1])
        for lista in (self.lista_entradas, self.lista_salidas):  # el nombre entero de la variable, al pasar el ratón, en la barra de estado
            lista.entered.connect(lambda indice, lista=lista: self.detalle.emit((lista.item(indice.row()).toolTip() or "").replace("\n", " · ")))
            lista.viewport().installEventFilter(self)
        self._estrecho = None
        self._disponer(False)
        # con la ventana pequeña el cuerpo entero se desplaza (barras cuando hacen falta) en vez de cortarse
        self.scroll_cuerpo = QScrollArea()
        self.scroll_cuerpo.setObjectName("scrollCuerpoES")
        self.scroll_cuerpo.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_cuerpo.setWidgetResizable(True)
        self.scroll_cuerpo.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_cuerpo.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_cuerpo.setWidget(cuerpo)
        raiz.addWidget(self.scroll_cuerpo, 1)
        # Pie: leyenda de los colores de tipo y resumen de lo asignado
        pie = QFrame()
        pie.setObjectName("pieES")
        pl = QHBoxLayout(pie)
        pl.setContentsMargins(12, 0, 12, 2)
        pl.setSpacing(6)
        for texto, tipo in LEYENDA:
            cuadro = IndicadorES(8, 8)
            cuadro.fijar((COLOR_TIPO.get(tipo, COLOR_CUALQUIERA),), NIVEL_ACTIVO)
            pl.addWidget(cuadro)
            pl.addWidget(QLabel(texto))
            pl.addSpacing(12)
        self.ayuda_vacio.setParent(pie)
        self.ayuda_vacio.setWordWrap(True)  # a media pantalla se parte en dos líneas: no fija el ancho mínimo de la ventana
        self.ayuda_vacio.setMinimumWidth(0)
        self.ayuda_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(self.ayuda_vacio, 1)
        self.ayuda_vacio.show()
        self.resumen = EtiquetaGrupos()  # «0/44 entradas asignadas · 0/44 salidas asignadas»: se parte entre los dos grupos, no dentro de uno
        self.resumen.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.resumen.setObjectName("resumenES")
        pl.addWidget(self.resumen)
        raiz.addWidget(pie)
        self.dialogo_config = DialogoConfiguracion(self)
        self.dialogo_config.setWindowTitle("Configuración Modbus TCP")
        self.dialogo_config.resize(640, 380)
        self.dialogo_config.setStyleSheet(f"""
            QDialog {{ background:{estilo.FONDO}; color:{estilo.TINTA}; }}
            QLabel, QCheckBox {{ color:{estilo.TINTA}; }}
            QLineEdit, QSpinBox, QComboBox {{ background:{estilo.SUPERFICIE}; color:{estilo.TINTA}; border:1px solid {estilo.BORDE_CONTROL}; border-radius:{estilo.R_S}px; padding:5px; }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border:2px dashed {estilo.FOCO}; padding:4px; }}
            QTableWidget {{ background:{estilo.SUPERFICIE}; color:{estilo.TINTA}; gridline-color:{estilo.BORDE}; }}
            QHeaderView::section {{ background:{estilo.SUPERFICIE_2}; color:{estilo.TINTA_2}; padding:6px; border:0; font-weight:600; }}
            QPushButton {{ background:{estilo.SUPERFICIE}; color:{estilo.TINTA}; padding:6px 14px; border:1px solid {estilo.BORDE_CONTROL}; border-radius:{estilo.R_S}px; }}
            QPushButton:hover {{ background:{estilo.HOVER}; }}
            QPushButton[tecl="true"]:focus {{ border:2px dashed {estilo.FOCO}; padding:5px 13px; }}
            QPushButton:disabled {{ color:{estilo.DESHABILITADO}; }}
        """)
        ajustes = QVBoxLayout(self.dialogo_config)
        self.config_widget = QWidget()
        configuracion = QVBoxLayout(self.config_widget)
        endpoint = QFormLayout()
        endpoint.setVerticalSpacing(8)
        endpoint.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        servidor = QLabel("Conexión Modbus")
        servidor.setStyleSheet(f"font-size:{estilo.T_TITULO}px; font-weight:600; color:{estilo.ACENTO}; padding:8px 0")
        configuracion.addWidget(servidor)
        self.host = CampoIPv4()
        self.puerto = _SpinConfiguracion()
        self.puerto.setRange(1, 65535)
        self.unidad = _SpinConfiguracion()
        self.unidad.setRange(0, 255)
        self.periodo = _SpinConfiguracion()
        self.periodo.setRange(5, 10000)
        self.periodo.setSuffix(" ms")
        self.timeout = _SpinConfiguracion()
        self.timeout.setRange(10, 10000)
        self.timeout.setSuffix(" ms")
        self.puerto.setFixedWidth(110)
        self.unidad.setFixedWidth(110)
        self.host.setToolTip("Copia la dirección del software que actúa como servidor Modbus. Debe coincidir con el servidor activo.")
        self.unidad.setToolTip("El ID de unidad configurado en el servidor Modbus; normalmente 1.")
        for texto, widget in (("IP (Host)", self.host), ("Puerto", self.puerto), ("Esclavo ID", self.unidad)):
            endpoint.addRow(texto, widget)
        configuracion.addLayout(endpoint)
        titulo_canales = QLabel("Canales del servidor")
        titulo_canales.setStyleSheet(f"font-size:{estilo.T_SECCION}px; font-weight:600; color:{estilo.ACENTO}; padding-top:10px")
        configuracion.addWidget(titulo_canales)
        rejilla_canales = QGridLayout()
        rejilla_canales.addWidget(QLabel("Offset (desde)"), 0, 1)
        rejilla_canales.addWidget(QLabel("Cantidad"), 0, 2)
        self.offsets, self.cantidades = {}, {}
        self.canales_editados = False
        for fila, (area, texto) in enumerate((("discrete", "I · Entradas digitales"), ("coil", "Q · Salidas digitales"),
                                             ("input-register", "AI · Entradas numéricas"), ("holding", "AQ · Salidas numéricas")), 1):
            offset, cantidad = _SpinConfiguracion(), _SpinConfiguracion()
            offset.setRange(0, 65535)
            cantidad.setRange(0, 256 if area in ("discrete", "coil") else 64)
            offset.setFixedWidth(110)
            cantidad.setFixedWidth(110)
            offset.valueChanged.connect(self._marcar_canales)
            cantidad.valueChanged.connect(self._marcar_canales)
            self.offsets[area], self.cantidades[area] = offset, cantidad
            rejilla_canales.addWidget(QLabel(texto), fila, 0)
            rejilla_canales.addWidget(offset, fila, 1)
            rejilla_canales.addWidget(cantidad, fila, 2)
        configuracion.addLayout(rejilla_canales)
        self.b_restaurar_canales = QPushButton("Restablecer canales: 32 digitales y 12 numéricos")
        self.b_restaurar_canales.clicked.connect(self.restablecer_canales)
        configuracion.addWidget(self.b_restaurar_canales)
        self.ayuda_canales = QLabel("Copia el desplazamiento y la cantidad del software del servidor. Estos ajustes no modifican el servidor.")
        self.ayuda_canales.setWordWrap(True)
        self.ayuda_canales.setStyleSheet(f"color:{estilo.TINTA_2}; font-size:12px")
        configuracion.addWidget(self.ayuda_canales)
        self.b_avanzado = QPushButton("Asignaciones y ajustes avanzados  ›")
        self.b_avanzado.setStyleSheet(f"text-align:left; margin-top:12px; background:transparent; color:{estilo.TINTA_2}; border:0")
        self.b_avanzado.clicked.connect(self._alternar_avanzado)
        configuracion.addWidget(self.b_avanzado)
        self.avanzado = QWidget()
        avanzado = QVBoxLayout(self.avanzado)
        avanzado.setContentsMargins(0, 10, 0, 0)
        tiempos = QFormLayout()
        tiempos.addRow("Periodo", self.periodo)
        tiempos.addRow("Tiempo de espera", self.timeout)
        avanzado.addLayout(tiempos)
        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels(["Usar", "Variable", "Papel", "Tipo", "Área", "Dirección (base 0)", "Formato", "Escala"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setMinimumHeight(150)
        avanzado.addWidget(self.tabla)
        configuracion.addWidget(self.avanzado)
        self.avanzado.hide()
        ajustes.addWidget(self.config_widget)
        self.b_conectar = QPushButton("Conectar")
        self.b_conectar.clicked.connect(self.conectar)
        self.b_conectar.setProperty("primario", True)  # el botón principal de la cabecera
        self.b_desconectar = QPushButton("Desconectar / editar")
        self.b_desconectar.clicked.connect(self.desconectar)
        self.b_desconectar.setEnabled(False)
        for b in (self.b_conectar, self.b_desconectar, self.b_configuracion):
            cabecera.addWidget(b)
        self.b_desconectar.hide()
        self.error_config = QLabel()
        self.error_config.setWordWrap(True)
        self.error_config.setStyleSheet(f"color:{estilo.ERROR}")
        ajustes.addWidget(self.error_config)
        self.host.editingFinished.connect(self._config_editada)
        for widget in (self.puerto, self.unidad, self.periodo, self.timeout):
            widget.valueChanged.connect(self._config_editada)
        self._cargando = False

    def eventFilter(self, objeto, evento):  # noqa: N802
        if evento.type() == QEvent.Type.Leave and objeto in (self.lista_entradas.viewport(), self.lista_salidas.viewport()):
            self.detalle.emit("")
        return super().eventFilter(objeto, evento)

    def contexto_de(self, area):
        """Los nombres asignados al lado del PLC al que pertenece el canal de `area` (sensores a la izquierda, actuadores a la derecha)."""
        return self.contexto_izq if area in ("discrete", "input-register") else self.contexto_der

    UMBRAL_ESTRECHO = 900

    def _disponer(self, estrecho: bool) -> None:
        """Ancho: sensores | marco del PLC | actuadores. Estrecho (media pantalla): sensores y actuadores lado a lado arriba, con
        poca altura, y el marco del PLC debajo a todo el ancho, para que ningún nombre de canal («Salida numérica 11») se corte."""
        if estrecho == self._estrecho:
            return
        self._estrecho = estrecho
        sensores, scroll, actuadores = self._partes
        for w in self._partes:
            self._zona.removeWidget(w)
        for c in range(3):
            self._zona.setColumnStretch(c, 0)
        for f in range(2):
            self._zona.setRowStretch(f, 0)
        if estrecho:
            self._zona.addWidget(sensores, 0, 0)
            self._zona.addWidget(actuadores, 0, 1)
            self._zona.addWidget(scroll, 1, 0, 1, 2)
            self._zona.setColumnStretch(0, 1)
            self._zona.setColumnStretch(1, 1)
            self._zona.setRowStretch(1, 1)
            for w in (sensores, actuadores):
                w.setMinimumWidth(0)
                w.setMaximumHeight(150)
        else:
            self._zona.addWidget(sensores, 0, 0)
            self._zona.addWidget(scroll, 0, 1)
            self._zona.addWidget(actuadores, 0, 2)
            self._zona.setColumnStretch(0, 1)
            self._zona.setColumnStretch(1, 3)
            self._zona.setColumnStretch(2, 1)
            for w in (sensores, actuadores):
                w.setMinimumWidth(144)
                w.setMaximumHeight(16777215)

    def resizeEvent(self, evento):  # noqa: N802
        super().resizeEvent(evento)
        estrecho = self.width() < self.UMBRAL_ESTRECHO
        self._disponer(estrecho)
        self.resumen.setMaximumWidth(210 if estrecho else 16777215)  # media pantalla: «0/44 entradas asignadas» y «0/44 salidas asignadas» en dos líneas, no en una larga que deja la ayuda en cuatro

    def restablecer_canales(self):
        self._cargando=True
        for area,rango in CANALES_INICIALES.items():
            ocupadas=[s.direccion for s in self.config.senales if s.area==area]
            inicio=self.offsets[area].value()
            self.cantidades[area].setValue(max(rango["cantidad"],max(ocupadas,default=inicio-1)-inicio+1))
        self._cargando=False
        self._aplicar()

    def _config_editada(self, *args):
        if not self._cargando and not self.bloqueado and self.doc is not None:
            self._aplicar()

    def _escala(self, area, direccion):
        return "1" if area in ("discrete", "coil") else self.escalas_base.get(f"{area}:{direccion}", "100")

    def abrir_configuracion(self):
        self.dialogo_config.show()
        self.dialogo_config.raise_()

    def _marcar_canales(self):
        self.canales_editados = True
        self._config_editada()

    def _alternar_avanzado(self):
        mostrar = self.avanzado.isHidden()
        self.avanzado.setVisible(mostrar)
        self.b_avanzado.setText("Asignaciones y ajustes avanzados  ⌄" if mostrar else "Asignaciones y ajustes avanzados  ›")
        self.dialogo_config.resize(1050 if mostrar else 640, 680 if mostrar else 380)

    def _cerrar_configuracion(self):
        self.dialogo_config.close()

    def mostrar_tiempos(self, medidas, ultima_parada=None):
        """Cadencia observada y duración del intercambio, sin confundirlas con la parada física. Se guarda en `tiempos`
        (texto y tooltip), que permanece oculto."""
        def ms(clave):
            return f"{medidas[clave]:.1f}".replace(".", ",") + " ms"
        if "ciclo_ms" not in medidas:
            self.tiempos.clear()
            self.tiempos.hide()
            return
        prefijo = "Sondeo " + ms("sondeo_ms") + " · " if "sondeo_ms" in medidas else ""
        self.tiempos.setText(prefijo + "Ciclo " + ms("ciclo_ms") + " · máx. " + ms("ciclo_max_ms"))
        lineas = ["Medidas desde la última conexión."]
        for clave, nombre in (("sondeo_ms", "Intervalo real entre lecturas"),
                              ("sondeo_max_ms", "Máximo intervalo entre lecturas"),
                              ("leer_red_ms", "Lectura por red"),
                              ("leer_espera_ms", "Espera antes de aplicar la lectura"),
                              ("evolucion_ms", "Evolución del GRAFCET"),
                              ("escribir_red_ms", "Escritura por red"),
                              ("ciclo_ms", "Lectura hasta salida confirmada"),
                              ("ciclo_max_ms", "Máximo del ciclo")):
            if clave in medidas:
                lineas.append(nombre + ": " + ms(clave))
        if ultima_parada:
            lineas.append("")
            lineas.append("Última salida desactivada por el GRAFCET: " + ", ".join(ultima_parada["salidas"]))
            lineas.append("Entradas leídas antes de confirmar esa desactivación:")
            for entrada in ultima_parada["entradas"]:
                valores = ", ".join(k + " = " + (str(int(v)) if isinstance(v, bool) else str(v))
                                    for k, v in entrada["valores"].items())
                antes = f"{entrada['antes_ms']:.1f}".replace(".", ",")
                lineas.append(antes + " ms antes: " + valores)
        lineas.append("El ciclo no incluye la espera hasta el siguiente sondeo ni el movimiento después de desactivar la salida.")
        self.tiempos.setToolTip("\n".join(lineas))
        # La línea queda oculta: la medida se conserva (texto y detalle), pero no se enseña al alumno.

    def mostrar_estado(self, estado, mensaje):
        self.estado.setText(mensaje)
        conectado = estado == "conectado"
        self._hubo_conexion |= conectado
        visual = "conectado" if conectado else "neutro"
        self.cabecera.setProperty("estadoVisual", visual)
        self.cabecera.style().unpolish(self.cabecera)
        self.cabecera.style().polish(self.cabecera)
        self.cabecera.update()
        fallo = estado in ("error", "diagnostico")
        self.check.setText("✓" if conectado else "✕" if fallo else "●")
        self.check.setStyleSheet(f"background:{estilo.OK if conectado else estilo.ERROR if fallo else 'transparent'}; "
                                 f"color:{'white' if conectado or fallo else estilo.TINTA_3}; "
                                 f"border-radius:{estilo.R_M}px; font-size:{self.letra}px; font-weight:600")
        self.check.setToolTip(mensaje)
        self.estado.setStyleSheet(f"color:{estilo.OK if conectado else estilo.ERROR if fallo else estilo.AVISO if self._hubo_conexion else estilo.TINTA_2}; font-weight:600")
        self.estado.setVisible(True)
        self.estado_cambiado.emit(estado, mensaje)

    def admite(self, vid, area):
        v = next((v for v in self.variables if v["id"] == vid), None)
        return bool(v and not self.bloqueado and encaja(v, area))

    def autoasignar(self, nuevas):
        """Solo variables recién creadas; nunca desplaza una asignación existente."""
        if self.bloqueado:return []
        sin_canal=[]
        for v in self.variables:
            if v['id'] not in nuevas or any(s.variable==v['id'] for s in self.config.senales):continue
            digital=v['type']['kind']=='bool'
            if v['type']['kind'] not in ('bool','int','decimal'):continue
            area=('discrete' if digital else 'input-register') if v['role']=='input' else ('coil' if digital else 'holding')
            rango=self.config.canales.get(area,CANALES_INICIALES[area])
            ocupadas={s.direccion for s in self.config.senales if s.area==area}
            libre=next((i for i in range(rango['offset'],rango['offset']+rango['cantidad']) if i not in ocupadas),None)
            if libre is None:sin_canal.append(v['name'])
            else:self.asignar(v['id'],area,libre)
        return sin_canal

    def asignar(self, vid, area, direccion):
        if not self.admite(vid, area):
            return False
        self._cargando = True
        for fila, v in enumerate(self.variables):
            if v["id"] != vid and self.tabla.cellWidget(fila, 0).isChecked() and self.tabla.cellWidget(fila, 4).currentData() == area and self.tabla.cellWidget(fila, 5).value() == direccion:
                self.tabla.cellWidget(fila, 0).setChecked(False)
            if v["id"] == vid:
                seleccionada = fila
        self._cargando = True
        nueva = not self.tabla.cellWidget(seleccionada, 0).isChecked()
        combo = self.tabla.cellWidget(seleccionada, 4)
        combo.setCurrentIndex(combo.findData(area))
        self.tabla.cellWidget(seleccionada, 5).setValue(direccion)
        if nueva:
            self.tabla.cellWidget(seleccionada, 7).setText("—" if area in ("discrete", "coil") else self._escala(area, direccion))
        self.tabla.cellWidget(seleccionada, 0).setChecked(True)
        self._cargando = False
        self._aplicar()
        return True

    def quitar(self, vid):
        if self.bloqueado:
            return
        self._cargando = True
        for fila, v in enumerate(self.variables):
            if v["id"] == vid:
                self.tabla.cellWidget(fila, 0).setChecked(False)
        self._cargando = False
        self._aplicar()

    @staticmethod
    def firma(doc):
        """Lo del modelo que ve este panel: sus variables de entrada y salida (ID, nombre, papel y tipo)."""
        return tuple((v["id"], v["name"], v["role"], json.dumps(v["type"], sort_keys=True))
                     for v in doc["variables"] if v["role"] in ("input", "output"))

    @staticmethod
    def _depurar(doc, config, nombres):
        """Separa las asignaciones de `config` que siguen casando con las variables de `doc` de las que ya no: la variable
        no existe, ya no es de entrada ni de salida (pasó a interna), o su papel o tipo ya no casan con el área. Devuelve la
        configuración sin ellas (la misma, si no hay ninguna) y un texto por cada una quitada. `nombres` {ID: nombre} de las
        variables que había antes."""
        todas = {v["id"]: v for v in doc["variables"]}
        variables = {i: v for i, v in todas.items() if v["role"] in ("input", "output")}
        validas, quitadas = [], []
        for s in config.senales:
            v = variables.get(s.variable)
            canal = f"{ETIQUETA_CANAL.get(s.area, s.area)} {s.direccion}"
            if v is None and s.variable in todas:  # existe, pero ya es interna: el mismo aviso que `Configuracion.quitar_obsoletas`
                quitadas.append(f"«{todas[s.variable]['name']}» ya no es de entrada ni de salida")
            elif v is None:
                quitadas.append(f"«{nombres.get(s.variable, s.variable)}» ya no existe")
            elif v["type"]["kind"] not in ("bool", "int", "decimal") or s.area not in areas_variable(v):
                quitadas.append(f"«{v['name']}» ya no encaja en {canal}")
            else:
                validas.append(s)
        return (replace(config, senales=validas) if quitadas else config), quitadas

    def cargar(self, doc, config=None, avisos=()):
        """Pone en el panel las variables de `doc` y el mapa `config` (por defecto, uno nuevo con la última conexión
        propuesta). Las asignaciones que ya no casan con el modelo se quitan y se avisa en el estado. Devuelve esos avisos;
        `avisos` son los de lo ya quitado al leer el mapa (`Configuracion.cargar`), que van delante."""
        self._cargando = True
        aviso_previo=self.aviso if self.doc is not None and self.doc["id"]==doc["id"] else ""
        nombres = {v["id"]: v["name"] for v in self.variables}
        host, puerto, unidad = self.conexion_defecto
        prefs = self.parametros_defecto
        if config is None:
            config = Configuracion(host, puerto, unidad, prefs.get("periodo_ms", 20), prefs.get("timeout_ms", 500),
                                   modelo=doc["id"], canales=copy.deepcopy(CANALES_INICIALES),
                                   )
            self.escalas_base = dict(prefs.get("escalas", {}))
            self.aviso_host = self.aviso_host_defecto
        else:
            self.escalas_base = {f"{s.area}:{s.direccion}": s.escala for s in config.senales}
            self.aviso_host = getattr(config, "aviso_host", "") or (
                self.aviso_host if self.doc is not None and self.doc["id"] == doc["id"] and config.host == self.host.text() else "")
        config, quitadas = self._depurar(doc, config, nombres)
        quitadas = [*avisos, *quitadas]
        self.doc = doc
        self.config = config
        c = self.config
        for area in AREAS:
            posiciones = [s.direccion for s in c.senales if s.area == area]
            rol = "input" if area == "input-register" else "output"
            base = CANALES_INICIALES[area]["cantidad"]
            limite = 256 if area in ("discrete", "coil") else 64
            offset = min(posiciones) if posiciones and max(posiciones) >= limite else 0
            cantidad = max(base, max(posiciones) - offset + 1 if posiciones else 0)
            rango = c.canales.get(area, {"offset": offset, "cantidad": cantidad})
            self.offsets[area].setValue(rango["offset"])
            self.cantidades[area].setValue(rango["cantidad"])
        self.canales_editados = False
        self.host.setText(c.host)
        for w, valor in ((self.puerto, c.puerto), (self.unidad, c.unidad), (self.periodo, c.periodo_ms), (self.timeout, c.timeout_ms)):
            w.setValue(valor)
        self.variables = [v for v in doc["variables"] if v["role"] in ("input", "output")]
        mapa = {s.variable: s for s in c.senales}
        ocupadas = {area: {s.direccion for s in c.senales if s.area == area} for area in AREAS}
        self.tabla.setRowCount(len(self.variables))
        for fila, v in enumerate(self.variables):
            s = mapa.get(v["id"])
            digital = v["type"]["kind"] == "bool"
            usar = QCheckBox()
            usar.setChecked(s is not None)
            usar.setEnabled(v["type"]["kind"] in ("bool", "int", "decimal"))
            self.tabla.setCellWidget(fila, 0, usar)
            for col, texto in ((1, v["name"]), (2, "Entrada" if v["role"] == "input" else "Salida"), (3, TIPOS[v["type"]["kind"]])):
                item = QTableWidgetItem(texto)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setToolTip(texto if col == 1 else v["id"])
                self.tabla.setItem(fila, col, item)
            area = _ComboConfiguracion()
            for clave in areas_variable(v):
                area.addItem(AREAS[clave], clave)
            area.setCurrentIndex(area.findData(s.area) if s else 0)
            area.setToolTip("Entradas para sensores y salidas para actuadores. Copia la asignación del servidor Modbus.")
            self.tabla.setCellWidget(fila, 4, area)
            direccion = _SpinConfiguracion()
            direccion.setRange(0, 65535)
            propuestas = ocupadas[area.currentData()]
            propuesta = next((n for n in range(65536) if n not in propuestas), 0)
            direccion.setValue(s.direccion if s else propuesta)
            propuestas.add(direccion.value())
            direccion.setToolTip("Número de entrada o salida en el servidor Modbus: Entrada 0 → 0, Salida 0 → 0. Áreas independientes.")
            self.tabla.setCellWidget(fila, 5, direccion)
            formato = _ComboConfiguracion()
            for clave in (["BOOL"] if digital else ["INT16", "UINT16"]):
                formato.addItem(FORMATOS[clave], clave)
            formato.setCurrentIndex(formato.findData(s.formato) if s else 0)
            self.tabla.setCellWidget(fila, 6, formato)
            escala = QLineEdit("—" if digital else s.escala if s else self._escala(area.currentData(), direccion.value()))
            escala.setReadOnly(digital)
            escala.setEnabled(not digital)
            escala.setToolTip("No aplica a BOOL (escala fija 1)" if digital else "Valor GRAFCET = registro / escala. Predeterminada: 100")
            self.tabla.setCellWidget(fila, 7, escala)
            usar.toggled.connect(self._config_editada)
            area.currentIndexChanged.connect(self._config_editada)
            direccion.valueChanged.connect(self._config_editada)
            formato.currentIndexChanged.connect(self._config_editada)
            escala.editingFinished.connect(self._config_editada)
        self.tabla.resizeColumnsToContents()
        self.firma_modelo = self.firma(doc)
        self.pendiente = False
        aviso_nuevo=f"Asignaciones quitadas: {'; '.join(quitadas)}" if quitadas else ""
        self.aviso=" · ".join(x for x in (aviso_previo,aviso_nuevo) if x)
        self._dibujar()
        self._cargando = False
        return quitadas

    def actualizar(self, doc):
        """El modelo ha cambiado (variables nuevas, renombradas, de otro tipo o papel, o borradas): vuelve a poner listas,
        canales y tabla con las variables actuales. Conserva la configuración (servidor, canales, lo escrito en
        Configuración y aún sin aplicar) y las asignaciones que siguen casando; quita, con aviso, las que ya no. Si lo que
        ve el panel no ha cambiado, no reconstruye nada. Devuelve los avisos de lo quitado."""
        if self.doc is None:
            return self.cargar(doc)
        if self.firma(doc) == self.firma_modelo:
            self.doc = doc  # lo demás del modelo (etapas, valores iniciales…) no cambia lo que se ve, pero sí lo que se valida
            return []
        try:
            base = self.obtener()
        except ValueError:  # lo escrito a medias no es válido: se parte del último mapa aplicado
            base = self.config
        recolocar = set()
        if not self.bloqueado:  # con la conexión viva el mapa no se mueve
            base, recolocar = self._separar_por_cambio_de_tipo(doc, base)
        quitadas = self.cargar(doc, base)
        sin_canal = self.autoasignar(recolocar)
        if sin_canal:
            self.aviso = " · ".join(t for t in (self.aviso, "Sin canal Modbus libre: " + ", ".join(sin_canal)) if t)
            self._pintar_nota()
        return quitadas

    @staticmethod
    def _separar_por_cambio_de_tipo(doc, config):
        """Las asignaciones de variables que han pasado de booleana a numérica (Entera o Decimal, igual) no se pueden
        conservar en su canal digital, pero tampoco se avisa de que se quitan: se vuelven a colocar solas en un registro,
        como una variable nueva. Devuelve la configuración sin ellas y el conjunto de IDs que hay que recolocar."""
        variables = {v["id"]: v for v in doc["variables"] if v["role"] in ("input", "output")}
        recolocar, conservadas = set(), []
        for s in config.senales:
            v = variables.get(s.variable)
            ahora_numerica = v is not None and v["type"]["kind"] in ("int", "decimal")
            if ahora_numerica and s.area in ("discrete", "coil"):
                recolocar.add(s.variable)
            else:
                conservadas.append(s)
        return (replace(config, senales=conservadas) if recolocar else config), recolocar

    def marcar_pendiente(self, pendiente):
        """Con la conexión viva el mapa en uso no cambia: se avisa de que hay variables nuevas o cambiadas por ver."""
        if pendiente != self.pendiente:
            self.pendiente = pendiente
            self._pintar_nota()

    def _pintar_nota(self):
        partes = (self.aviso_host, self.aviso, self.avisos_escala, self.pista_canales, "Hay variables nuevas o cambiadas: se verán al desconectar" if self.pendiente else "")
        self.estado.fijar_nota(" · ".join(t for t in partes if t))

    def obtener(self):
        senales = []
        for fila, v in enumerate(self.variables):
            if self.tabla.cellWidget(fila, 0).isChecked():
                senales.append(Senal(v["id"], self.tabla.cellWidget(fila, 4).currentData(),
                                     self.tabla.cellWidget(fila, 5).value(), self.tabla.cellWidget(fila, 6).currentData(),
                                     "1" if v["type"]["kind"] == "bool" else self.tabla.cellWidget(fila, 7).text()))
        c = Configuracion(self.host.text(), self.puerto.value(), self.unidad.value(),
                          self.periodo.value(), self.timeout.value(), self.doc["id"], senales)
        c.canales = ({area: {"offset": self.offsets[area].value(), "cantidad": self.cantidades[area].value()}
                      for area in AREAS})
        c.validar(self.doc)
        return c

    def _aplicar(self):
        try:
            c = self.obtener()
        except ValueError as exc:
            self.mostrar_estado("error", f"Mapa inválido: {exc}")
            self.error_config.setText(f"Mapa inválido: {exc}")
            return False
        self.error_config.clear()
        self.config = c
        self.escalas_base.update({f"{s.area}:{s.direccion}": s.escala for s in c.senales})
        self.aviso = ""  # el usuario ya ha actuado sobre el mapa
        self.aviso_host = ""  # (y ha puesto la IP, que obtener() ya validó)
        self._dibujar()
        if not getattr(self,"conectado",False):
            self.estado.setText("Configuración actualizada · desconectado. Pulsa «Conectar».")
        self.aplicar.emit(c)
        return True

    def _dibujar(self):
        self.indicadores.clear()
        self.terminales.clear()
        self.indicadores_listas.clear()
        c = self.config
        self.destino.setText(f"({c.host}:{c.puerto})\nEsclavo ID:{c.unidad}")
        self.ayuda_vacio.show()
        for fila in (self.fila_entradas, self.fila_salidas):
            while fila.count():
                item = fila.takeAt(0)
                if item.widget():
                    viejo = item.widget()
                    viejo.hide()
                    viejo.setParent(None)  # (fuera del árbol de la ventana ya: hasta que se borre de verdad, no hay que repasarlo cada vez que cambia la hoja)
                    viejo.deleteLater()
        variables = {v["id"]: v for v in self.variables}
        self.lista_entradas.clear()
        self.lista_salidas.clear()
        asignadas = {s.variable: f"{ETIQUETA_CANAL[s.area]} {s.direccion}" for s in c.senales}
        for rol, titulo in (("input", "Sensores"), ("output", "Actuadores")):
            self.cuentas[rol].setText(f"{titulo} <span style='color:{estilo.TINTA_2}; font-size:{self.letra}px; font-weight:400'>{sum(v['role'] == rol for v in self.variables)}</span>")
        # los nombres de cada lista y de cada lado del PLC: el recorte de un nombre largo conserva lo que lo distingue de los demás
        self.lista_entradas.contexto.fijar([v["name"] for v in self.variables if v["role"] == "input"])
        self.lista_salidas.contexto.fijar([v["name"] for v in self.variables if v["role"] == "output"])
        self.contexto_izq.fijar([variables[s.variable]["name"] for s in c.senales if s.variable in variables and s.area in ("discrete", "input-register")])
        self.contexto_der.fijar([variables[s.variable]["name"] for s in c.senales if s.variable in variables and s.area in ("coil", "holding")])
        for v in self.variables:
            item = QListWidgetItem(v["name"])
            item.setSizeHint(QSize(0, self.alto_fila))
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            item.setData(ROL_COLOR, color_tipo(v))
            item.setData(ROL_ASIGNADA, v["id"] in asignadas)
            item.setData(ROL_ACTIVO, False)
            item.setToolTip(f"{v['name']}\n{TIPOS[v['type']['kind']]} · " + (f"asignada a {asignadas[v['id']]}" if v["id"] in asignadas else "sin asignar"))
            if v["type"]["kind"] == "duration":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            (self.lista_entradas if v["role"] == "input" else self.lista_salidas).addItem(item)
            self.indicadores_listas[v["id"]] = item
        mapa = {(s.area, s.direccion): s for s in c.senales}
        direcciones_area = {}
        for area in AREAS:
            rango = c.canales.get(area)
            direcciones_area[area] = (list(range(rango["offset"], rango["offset"] + rango["cantidad"])) if rango else
                                     sorted(set(range(CANALES_INICIALES[area]["cantidad"])) | {d for a, d in mapa if a == area}))
        digitales = max(len(direcciones_area[a]) for a in ("discrete", "coil"))
        for area in AREAS:
            numerica = area in ("input-register", "holding")
            entrada = area in ("discrete", "input-register")
            direcciones = direcciones_area[area]
            fila = self.fila_entradas if entrada else self.fila_salidas
            if numerica:
                hueco = digitales - len(direcciones_area["discrete" if entrada else "coil"])
                if hueco:
                    fila.addSpacing(hueco * self.alto_fila)
            for direccion in sorted(direcciones):
                s = mapa.get((area, direccion))
                v = variables.get(s.variable) if s else None
                terminal = TerminalES(self, area, direccion, v, aviso_escala(v, s))
                fila.addWidget(terminal)
                self.terminales[(area, direccion)] = terminal
                if v:
                    self.indicadores[v["id"]] = (terminal.led, terminal.valor)
        ni = sum(variables[s.variable]["role"] == "input" for s in c.senales if s.variable in variables)
        nq = len(c.senales) - ni
        ti = sum(a in ("discrete", "input-register") for a, _ in self.terminales)
        tq = len(self.terminales) - ti
        self.resumen.setText(f"{ni}/{ti} entradas asignadas  ·  {nq}/{tq} salidas asignadas")
        # Con canales fijados a mano, un área en 0 no ofrece dónde soltar sus variables: se dice cuál para subirla
        vacias = [ETIQUETA_CANAL[a] for a in AREAS if c.canales.get(a, {}).get("cantidad", 1) == 0
                  and any(encaja(v, a) and v["id"] not in asignadas for v in self.variables)]
        avisos = []
        for s in c.senales:
            texto = aviso_escala(variables.get(s.variable), s)
            if texto:
                avisos.append(f"«{variables[s.variable]['name']}»: {texto}")
        self.avisos_escala = "; ".join(avisos)
        self._pintar_redondeos()
        self.pista_canales = f"Sin canales en {', '.join(vacias)}: sube su cantidad en Configuración" if vacias else ""
        self._pintar_nota()

    def mostrar_redondeos(self, redondeos):
        """Marca en ámbar las Enteras que han recibido decimales en esta conexión (con el último valor y el usado)."""
        if redondeos == self.redondeos:
            return
        self.redondeos = dict(redondeos)
        self._pintar_redondeos()

    def _pintar_redondeos(self):
        for terminal in self.terminales.values():
            dato = terminal.variable and self.redondeos.get(terminal.variable["id"])
            terminal.fijar_redondeo(aviso_redondeo(*dato) if dato else "")

    def mostrar_valores(self, valores):
        self._ultimos_valores = valores
        def activo(valor):
            try:
                return bool(Fraction(valor)) if isinstance(valor, str) else bool(valor)
            except (ValueError, TypeError, ZeroDivisionError):
                return False
        for vid, item in self.indicadores_listas.items():
            item.setData(ROL_ACTIVO, activo(valores.get(vid)))
        for vid, (led, etiqueta) in self.indicadores.items():
            valor = valores.get(vid)
            if valor is None:
                etiqueta.setText("—")
                led.fijar_nivel(NIVEL_ASIGNADO)
            else:
                etiqueta.setText(str(int(valor)) if type(valor) is bool else str(valor))
                led.fijar_nivel(NIVEL_ACTIVO if activo(valor) else NIVEL_ASIGNADO)

    def mostrar_muestra(self, muestra, senales, escritos=None, salidas=()):
        """Los valores leídos de la planta (entradas) y, en Pausa con la conexión viva, lo último escrito en las salidas
        asignadas (cero tras pausar), con la escala de cada señal."""
        valores = {}
        for origen, lista in ((muestra, senales), (escritos or {}, salidas)):
            for s in lista:
                if s.variable not in origen:
                    continue
                raw = origen[s.variable]
                if s.formato != "BOOL":
                    raw = raw - 65536 if s.formato == "INT16" and raw >= 32768 else raw
                    raw = Fraction(raw) / Fraction(s.escala)
                valores[s.variable] = raw
        self.mostrar_valores(valores)

    def ocupado(self, on):
        self.conectado = on
        self.bloqueado = False
        self.lista_entradas.setDragEnabled(True)
        self.lista_salidas.setDragEnabled(True)
        for terminal in self.terminales.values():
            terminal.setAcceptDrops(True)
            if terminal.b_quitar:
                terminal.b_quitar.setEnabled(True)
                terminal.b_quitar.setToolTip("Desasignar esta señal")

        self.b_conectar.setVisible(not on)
        self.b_desconectar.setVisible(on)
        self.config_widget.setEnabled(not on)
        for b in (self.b_conectar,):
            b.setEnabled(not on)
        self.b_desconectar.setEnabled(on)
