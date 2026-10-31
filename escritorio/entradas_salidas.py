"""Conexión de E/S: vista «autómata» con las variables a los lados y los canales del servidor Modbus en el centro.

A la izquierda, los sensores; a la derecha, los actuadores (listas de variables que se arrastran). En el centro, un marco
de borde fino con la cabecera «(IP:puerto) Esclavo ID:n» y dos columnas de canales: Input e Input Reg a la izquierda, Coil y
Holding Reg a la derecha. El nombre de la variable asignada se escribe fuera del marco, pegado a él. Estilo plano y compacto.
Una barrita de color indica el tipo de la variable (Bool, Decimal, Entera, Cualquiera) y su viveza, si la señal está activa."""
from dataclasses import replace
import json
from PySide6.QtCore import Signal, Qt, QMimeData, QSize, QRect, QEvent
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetrics, QPainter
from fractions import Fraction
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QSizePolicy,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
                               QAbstractItemView, QMenu, QApplication, QGridLayout, QStyle,
                               QStyledItemDelegate)

from conexion.configuracion import ETIQUETA_CANAL, Configuracion, Senal

AREAS = {"discrete": "Inputs (entradas digitales 0/1)",
         "coil": "Coils (señales digitales 0/1)",
         "input-register": "Input Registers (números de entrada)",
         "holding": "Holding Registers (números modificables)"}
FORMATOS = {"BOOL": "BOOL (apagado/encendido)", "INT16": "INT16 (entero con signo)",
            "UINT16": "UINT16 (entero sin signo)"}
TIPOS = {"bool": "Booleana (0/1)", "int": "Entera", "decimal": "Decimal", "duration": "Duración"}
MIME_VARIABLE = "application/x-grafconnect-variable"
# Host, puerto y esclavo que propone el panel la primera vez, sin nada recordado ni mapa guardado: el servidor de Factory I/O.
# Después la ventana propone la última conexión que funcionó (`PanelES.conexion_defecto`).
CONEXION_INICIAL = ("192.168.1.133", 502, 1)

# Aspecto. El color de la barrita es el del tipo; su viveza, el estado: tenue (canal sin asignar), tipo (asignado) y vivo
# (la señal está activa). La leyenda de abajo explica los colores.
FONDO = "#f4fbf9"
COLOR_TIPO = {"bool": "#8bc34a", "decimal": "#2fa8f0", "int": "#e8892b"}
COLOR_CUALQUIERA = "#6d837b"
LEYENDA = (("Bool", "bool"), ("Decimal", "decimal"), ("Entera", "int"), ("Cualquiera", None))
NIVEL_TENUE, NIVEL_ASIGNADO, NIVEL_ACTIVO = .28, .62, 1.0
ALTO_FILA = 18
ALTO_VARIABLE = 34
ANCHO_INTERIOR = 128  # la mitad del marco que cae dentro de él: indicador, nombre del canal y, en los registros, su valor
ROL_COLOR, ROL_ASIGNADA, ROL_ACTIVO = (Qt.ItemDataRole.UserRole + n for n in (1, 2, 3))
ESTILO_PANEL = """
    QWidget#conexionES { background:#eef7f7; }
    QWidget#tarjetaES { background:white; border:1px solid #d4e7e8; border-radius:7px; }
    QWidget#tarjetaES QLabel { border:0; }
    QLabel#tituloPLC { color:#147f80; font-size:15px; font-weight:600; padding:8px; }
    QFrame#cabeceraES { background:#f4fbf9; border:0; border-bottom:1px solid #d1e6df; }
    QFrame#cabeceraES QPushButton { background:transparent; color:#167d79; border:0; padding:4px 10px; border-radius:0; }
    QFrame#cabeceraES QPushButton:hover { color:#164f48; background:#e1f2eb; }
    QFrame#cabeceraES QPushButton:disabled { color:#81958f; background:transparent; }
    QLabel#tituloES { color:#203b45; font-size:13px; font-weight:600; padding-left:4px; }
    QWidget#cuerpoES, QFrame#pieES { background:transparent; }
    QWidget#cuerpoES QLabel, QFrame#pieES QLabel { color:#365b55; background:transparent; }
    QLabel#seccionES { color:#122849; font-size:14px; font-weight:600; padding:10px 6px; }
    QLabel#ayudaES, QLabel#resumenES { color:#657e77; }
    QFrame#moduloPLC { background:transparent; border:1px solid #b5d9cf; }
    QListWidget#listaES { background:transparent; border:0; outline:0; }
    QScrollArea#scrollES { background:white; border:1px solid #d4e7e8; border-radius:7px; }
    QScrollArea#scrollES > QWidget > QWidget { background:white; }
    QWidget#cuerpoES QScrollBar:vertical { background:transparent; width:8px; margin:0; }
    QWidget#cuerpoES QScrollBar::handle:vertical { background:#aacfc3; border-radius:3px; min-height:24px; }
    QWidget#cuerpoES QScrollBar::add-line:vertical, QWidget#cuerpoES QScrollBar::sub-line:vertical { height:0; }
    QWidget#cuerpoES QScrollBar::add-page:vertical, QWidget#cuerpoES QScrollBar::sub-page:vertical { background:transparent; }
    QPushButton#quitarES { background:transparent; color:#637d75; border:0; padding:0; font-size:14px; }
    QPushButton#quitarES:hover { color:#b13d3d; }
    QPushButton#quitarES:disabled { color:#8a9c95; }
"""


def mezclar(color, nivel):
    """El color sobre el fondo: nivel 1 es el color entero; menos, más apagado."""
    c, f = QColor(color).getRgb(), QColor(FONDO).getRgb()
    return QColor(*(round(f[i] + (c[i] - f[i]) * nivel) for i in range(3)))


def color_tipo(variable):
    return COLOR_TIPO.get(variable["type"]["kind"], COLOR_CUALQUIERA)


def encaja(variable, area):
    """Si la variable puede asignarse (arrastrándola) a un canal de esa área: papel y tipo casan con ella."""
    tipo = variable["type"]["kind"]
    return variable["role"] == ("input" if area in ("discrete", "input-register") else "output") and (
        tipo == "bool" if area in ("discrete", "coil") else tipo in ("int", "decimal"))


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


class EtiquetaElidida(QLabel):
    """Etiqueta de una línea que, si no cabe, acaba en «…» (el texto completo sigue en text() y en el tooltip)."""

    def __init__(self, texto="", alineacion=Qt.AlignmentFlag.AlignLeft):
        super().__init__(texto)
        self.setAlignment(alineacion | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setPen(self.palette().windowText().color())
        elidido = QFontMetrics(self.font()).elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        p.drawText(self.rect(), int(self.alignment()), elidido)


class DelegadoVariable(QStyledItemDelegate):
    """Una fila de las listas laterales: el nombre y, en el borde, la barrita con el color del tipo. Los sensores llevan el
    texto a la derecha con la barrita a su derecha; los actuadores, al revés."""

    def __init__(self, padre, barra_a_la_derecha):
        super().__init__(padre)
        self.derecha = barra_a_la_derecha

    def sizeHint(self, _opcion, _indice):  # noqa: N802
        return QSize(0, ALTO_VARIABLE)

    def paint(self, p, opcion, indice):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = opcion.rect.adjusted(7, 2, -7, -2)
        elegido = bool(opcion.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver))
        p.setPen(QColor("#b7dcd8" if elegido else "#e0ecee"))
        p.setBrush(QColor("#eaf6f3" if elegido else "#ffffff"))
        p.drawRoundedRect(r, 4, 4)
        color = mezclar(indice.data(ROL_COLOR) or COLOR_CUALQUIERA,
                        NIVEL_ACTIVO if indice.data(ROL_ACTIVO) else NIVEL_ASIGNADO)
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(r.left() + 9, r.center().y() - 4, 8, 8)
        fuente = opcion.font
        fuente.setPixelSize(13)
        p.setFont(fuente)
        p.setPen(QColor("#132b46"))
        texto = r.adjusted(26, 0, -6, 0)
        elidido = QFontMetrics(fuente).elidedText(indice.data() or "", Qt.TextElideMode.ElideRight, texto.width())
        p.drawText(texto, Qt.AlignmentFlag.AlignVCenter, elidido)
        p.restore()


class ListaVariables(QListWidget):
    def __init__(self, lado="entrada"):
        super().__init__()
        self.setObjectName("listaES")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.setItemDelegate(DelegadoVariable(self, lado == "entrada"))

    def mimeData(self, items):
        datos = QMimeData()
        if items:
            datos.setData(MIME_VARIABLE, items[0].data(Qt.ItemDataRole.UserRole).encode("utf-8"))
        return datos


class TerminalES(QFrame):
    """Un canal: la fila entera es la zona donde soltar una variable. Dentro del marco, el indicador y el nombre del canal
    (y el valor, en los registros); fuera, a su lado, el nombre de la variable asignada y, al pasar el ratón, «×»."""

    def __init__(self, panel, area, direccion, variable=None):
        super().__init__()
        self.panel, self.area, self.direccion, self.variable = panel, area, direccion, variable
        self._inicio_arrastre = None
        self._resaltado = False
        self.setAcceptDrops(not panel.bloqueado)
        self.setObjectName("senalPLC")
        self.setFixedHeight(ALTO_FILA)
        entrada = area in ("discrete", "input-register")
        analogica = area in ("input-register", "holding")
        self.led = IndicadorES()
        if variable:
            self.led.fijar((color_tipo(variable),), NIVEL_ASIGNADO)
        else:  # sin asignar: tenue, con el color propio del área (los registros admiten Decimal y Entera)
            self.led.fijar((COLOR_TIPO["decimal"], COLOR_TIPO["int"]) if analogica else (COLOR_TIPO["bool"],), NIVEL_TENUE)
        self.canal = QLabel(f"{ETIQUETA_CANAL[area]} {direccion}")
        self.canal.setStyleSheet("color:#365b55")
        self.nombre = EtiquetaElidida(variable["name"] if variable else "",
                                      Qt.AlignmentFlag.AlignRight if entrada else Qt.AlignmentFlag.AlignLeft)
        self.nombre.setObjectName("asignacionES")  # lo que se agarra para mover la asignación a otro canal
        self.nombre.setStyleSheet("color:#203b45")
        self.valor = QLabel("—" if variable else "")
        self.valor.setStyleSheet("color:#526e66; font-size:10px")
        self.valor.setVisible(analogica)
        interior = QWidget()
        interior.setFixedWidth(ANCHO_INTERIOR)
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
            self.b_quitar.setFixedSize(18, ALTO_FILA - 2)
            self.b_quitar.setToolTip("Desconecta para desasignar" if panel.bloqueado else "Desasignar esta señal")
            self.b_quitar.setEnabled(not panel.bloqueado)
            self.b_quitar.clicked.connect(lambda: panel.quitar(variable["id"]))
            self.b_quitar.hide()  # solo al pasar el ratón por la fila
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        if entrada:
            if self.b_quitar:
                l.addWidget(self.b_quitar)
            l.addWidget(self.nombre, 1)
            l.addSpacing(8)
            l.addWidget(interior)
        else:
            l.addWidget(interior)
            l.addSpacing(8)
            l.addWidget(self.nombre, 1)
            if self.b_quitar:
                l.addWidget(self.b_quitar)
        self.setToolTip(f"{AREAS[area]} · dirección {direccion}\nArrastra una variable. Botón derecho para quitar o configurar.")

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

    def paintEvent(self, evento):
        if self._resaltado or self.underMouse():
            QPainter(self).fillRect(self.rect(), QColor("#c1e8dc" if self._resaltado else "#e8f5ef"))
        super().paintEvent(evento)

    def enterEvent(self, evento):
        if self.b_quitar is not None and self.b_quitar.isEnabled():
            self.b_quitar.show()
        self.update()
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        if self.b_quitar is not None:
            self.b_quitar.hide()
        self.update()
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
            self._resaltar(True)
            evento.acceptProposedAction()

    def dragLeaveEvent(self, evento):
        self._resaltar(False)
        evento.accept()

    def dropEvent(self, evento):
        self._resaltar(False)
        vid = self._variable_evento(evento)
        if vid and self.panel.asignar(vid, self.area, self.direccion):
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
        rejilla = QGridLayout(self)
        rejilla.setContentsMargins(0, 6, 0, 8)
        rejilla.setSpacing(0)
        titulo = QLabel("PLC · Modbus TCP")
        titulo.setObjectName("tituloPLC")
        rejilla.addWidget(titulo, 0, 0, 1, 2)
        self.destino = QLabel()
        self.destino.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.destino.setFixedSize(2 * ANCHO_INTERIOR, 46)
        self.izq, self.der = QWidget(), QWidget()
        self.fila_izq, self.fila_der = QVBoxLayout(self.izq), QVBoxLayout(self.der)
        for f in (self.fila_izq, self.fila_der):
            f.setContentsMargins(0, 0, 0, 0)
            f.setSpacing(0)
        self.ayuda = QLabel("Arrastra las variables a las entradas y salidas.")
        self.ayuda.setObjectName("ayudaES")
        self.ayuda.setWordWrap(True)
        self.ayuda.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ayuda.setContentsMargins(0, 8, 0, 0)
        self.ayuda.setMinimumHeight(40)
        rejilla.addWidget(self.destino, 1, 0, 1, 2, Qt.AlignmentFlag.AlignHCenter)
        rejilla.addWidget(self.izq, 2, 0, Qt.AlignmentFlag.AlignTop)
        rejilla.addWidget(self.der, 2, 1, Qt.AlignmentFlag.AlignTop)
        rejilla.addWidget(self.ayuda, 3, 0, 1, 2, Qt.AlignmentFlag.AlignTop)
        rejilla.setColumnStretch(0, 1)
        rejilla.setColumnStretch(1, 1)
        rejilla.setRowStretch(4, 1)
        self.marco = QFrame(self)
        self.marco.setObjectName("moduloPLC")
        self.marco.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMinimumWidth(2 * ANCHO_INTERIOR + 120)

    def event(self, evento):  # noqa: N802
        resultado = super().event(evento)
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest, QEvent.Type.Show, QEvent.Type.Polish):
            self._colocar_marco()
        return resultado

    def _colocar_marco(self):
        g, d, c = self.izq.geometry(), self.der.geometry(), self.destino.geometry()
        x0, x1 = g.right() + 1 - ANCHO_INTERIOR, d.left() + ANCHO_INTERIOR
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("conexionES")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fuente = QFont(self.font())
        fuente.setPixelSize(11)  # letra pequeña: caben más canales
        self.setFont(fuente)
        self.setStyleSheet(ESTILO_PANEL)
        self.doc = None
        self.config = Configuracion()
        self.variables = []
        self.firma_modelo = ()
        self.conexion_defecto = CONEXION_INICIAL  # (host, puerto, esclavo) que propone `cargar` si no hay mapa guardado
        self.aviso = ""  # asignaciones quitadas al poner al día con el modelo; dura hasta la siguiente acción sobre el mapa
        self.pista_canales = ""  # variables sin dónde asignarse porque su área tiene cantidad 0
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
        banda = QFrame()
        banda.setObjectName("cabeceraES")
        cabeza = QVBoxLayout(banda)
        cabeza.setContentsMargins(0, 0, 0, 0)
        cabeza.setSpacing(0)
        fila_alta = QWidget()
        fila_alta.setFixedHeight(32)
        cabecera = QHBoxLayout(fila_alta)
        cabecera.setContentsMargins(10, 0, 12, 0)
        cabecera.setSpacing(4)
        self.b_volver = QPushButton("←")
        self.b_volver.setFixedSize(30, 28)
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
        self.check.setStyleSheet("color:#7d848c; font-size:10px")
        fe.addWidget(self.check, 0, Qt.AlignmentFlag.AlignTop)
        self.estado = EstadoConexion()
        self.estado.setText("Desconectado")
        self.estado.setStyleSheet("color:#657e77")
        fe.addWidget(self.estado, 1)
        cabeza.addWidget(fila_alta)
        cabeza.addWidget(fila_estado)
        self.b_prueba_guiada = QPushButton("Abrir prueba guiada")
        self.b_prueba_guiada.clicked.connect(self.abrir_prueba)
        self.b_configuracion = QPushButton("Configuración")
        self.b_configuracion.setToolTip("Servidor Modbus, cantidad de canales y asignaciones")
        self.b_configuracion.clicked.connect(self.abrir_configuracion)
        raiz.addWidget(banda)
        # Cuerpo: sensores | marco del servidor con sus canales | actuadores
        cuerpo = QWidget()
        cuerpo.setObjectName("cuerpoES")
        zona = QHBoxLayout(cuerpo)
        zona.setContentsMargins(12, 10, 12, 4)
        zona.setSpacing(10)
        self.lienzo = LienzoPLC()
        self.modulo = self.lienzo.marco
        self.destino = self.lienzo.destino
        self.fila_entradas, self.fila_salidas = self.lienzo.fila_izq, self.lienzo.fila_der
        self.ayuda_vacio = self.lienzo.ayuda
        scroll = QScrollArea()
        scroll.setObjectName("scrollES")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
            etiqueta = QLabel("SENSORES" if rol == "input" else "ACTUADORES")
            etiqueta.setObjectName("seccionES")
            etiqueta.setAlignment(Qt.AlignmentFlag.AlignLeft)
            etiqueta.setTextFormat(Qt.TextFormat.RichText)
            cl.addWidget(etiqueta)
            cl.addWidget(lista, 1)
            self.cuentas[rol] = etiqueta
            columnas.append(columna)
        zona.addWidget(columnas[0], 1)
        zona.addWidget(scroll, 3)
        zona.addWidget(columnas[1], 1)
        raiz.addWidget(cuerpo, 1)
        # Pie: leyenda de los colores de tipo y resumen de lo asignado
        pie = QFrame()
        pie.setObjectName("pieES")
        pl = QHBoxLayout(pie)
        pl.setContentsMargins(12, 2, 12, 6)
        pl.setSpacing(6)
        for texto, tipo in LEYENDA:
            cuadro = IndicadorES(8, 8)
            cuadro.fijar((COLOR_TIPO.get(tipo, COLOR_CUALQUIERA),), NIVEL_ACTIVO)
            pl.addWidget(cuadro)
            pl.addWidget(QLabel(texto))
            pl.addSpacing(12)
        pl.addStretch()
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.resumen.setObjectName("resumenES")
        pl.addWidget(self.resumen)
        raiz.addWidget(pie)
        self.dialogo_config = DialogoConfiguracion(self)
        self.dialogo_config.setWindowTitle("Configuración Modbus TCP")
        self.dialogo_config.resize(640, 380)
        self.dialogo_config.setStyleSheet("""
            QDialog { background:#f4fbf9; color:#203b45; }
            QLabel, QCheckBox { color:#365b55; }
            QLineEdit, QSpinBox, QComboBox { background:#ffffff; color:#203b45; border:1px solid #c7dfd9; border-radius:3px; padding:5px; }
            QTableWidget { background:#ffffff; color:#203b45; gridline-color:#d1e6df; }
            QHeaderView::section { background:#e8f5ef; color:#365b55; padding:6px; border:0; }
            QPushButton { background:#e8f5ef; color:#203b45; padding:4px 8px; border:0; border-radius:4px; }
            QPushButton:hover { background:#d5eee5; }
            QPushButton:disabled { color:#81958f; }
        """)
        self.b_prueba_guiada.clicked.connect(self.dialogo_config.hide)
        ajustes = QVBoxLayout(self.dialogo_config)
        self.config_widget = QWidget()
        configuracion = QVBoxLayout(self.config_widget)
        endpoint = QFormLayout()
        endpoint.setVerticalSpacing(8)
        endpoint.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        servidor = QLabel("Servidor")
        servidor.setStyleSheet("font-size:15px; color:#167d79; padding:8px 0")
        configuracion.addWidget(servidor)
        self.host = QLineEdit()
        self.puerto = QSpinBox()
        self.puerto.setRange(1, 65535)
        self.unidad = QSpinBox()
        self.unidad.setRange(0, 255)
        self.periodo = QSpinBox()
        self.periodo.setRange(20, 10000)
        self.periodo.setSuffix(" ms")
        self.timeout = QSpinBox()
        self.timeout.setRange(10, 10000)
        self.timeout.setSuffix(" ms")
        self.host.setFixedWidth(260)
        self.puerto.setFixedWidth(110)
        self.unidad.setFixedWidth(110)
        self.host.setToolTip("Copia el Host que muestra Factory I/O en CONFIGURACIÓN. Debe coincidir con el servidor activo.")
        self.unidad.setToolTip("El mismo número que «Esclavo ID» en Factory I/O; normalmente 1.")
        for texto, widget in (("IP (Host)", self.host), ("Puerto", self.puerto), ("Esclavo ID", self.unidad)):
            endpoint.addRow(texto, widget)
        configuracion.addLayout(endpoint)
        titulo_canales = QLabel("Canales del servidor")
        titulo_canales.setStyleSheet("font-size:14px; color:#167d79; padding-top:10px")
        configuracion.addWidget(titulo_canales)
        rejilla_canales = QGridLayout()
        rejilla_canales.addWidget(QLabel("Offset (desde)"), 0, 1)
        rejilla_canales.addWidget(QLabel("Cantidad"), 0, 2)
        self.offsets, self.cantidades = {}, {}
        self.canales_editados = False
        for fila, (area, texto) in enumerate((("discrete", "I · Entradas digitales"), ("coil", "Q · Salidas digitales"),
                                             ("input-register", "AI · Entradas numéricas"), ("holding", "AQ · Salidas numéricas")), 1):
            offset, cantidad = QSpinBox(), QSpinBox()
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
        ayuda_canales = QLabel("Copia offset y cantidad de Factory I/O. Estos ajustes no modifican el servidor.")
        ayuda_canales.setWordWrap(True)
        ayuda_canales.setStyleSheet("color:#526e66; font-size:11px")
        configuracion.addWidget(ayuda_canales)
        self.b_avanzado = QPushButton("Asignaciones y ajustes avanzados  ›")
        self.b_avanzado.setStyleSheet("text-align:left; margin-top:12px; background:transparent; color:#526e66")
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
        botones = QHBoxLayout()
        self.b_aplicar = QPushButton("Aplicar mapa")
        self.b_aplicar.clicked.connect(self._aplicar)
        self.b_guardar = QPushButton("Guardar configuración…")
        self.b_guardar.clicked.connect(self.guardar)
        self.b_cargar = QPushButton("Cargar configuración…")
        self.b_cargar.clicked.connect(self.cargar_archivo)
        self.b_probar = QPushButton("Probar conexión")
        self.b_probar.clicked.connect(self.probar)
        self.b_conectar = QPushButton("Conectar")
        self.b_conectar.clicked.connect(self.conectar)
        self.b_desconectar = QPushButton("Desconectar / editar")
        self.b_desconectar.clicked.connect(self.desconectar)
        self.b_desconectar.setEnabled(False)
        for b in (self.b_aplicar, self.b_cargar, self.b_guardar):
            botones.addWidget(b)
        avanzado.addLayout(botones)
        principales = QHBoxLayout()
        principales.addWidget(self.b_probar)
        principales.addStretch()
        principales.addWidget(self.b_prueba_guiada)
        ajustes.addLayout(principales)
        for b in (self.b_conectar, self.b_desconectar, self.b_configuracion):
            cabecera.addWidget(b)
        self.b_desconectar.hide()
        nota = QLabel("Factory I/O: driver Modbus TCP/IP Server. Escala: valor GRAFCET = registro / escala. "
                      "Los pulsos más cortos que el intervalo efectivo pueden perderse.")
        nota.setWordWrap(True)
        avanzado.addWidget(nota)
        self.error_config = QLabel()
        self.error_config.setWordWrap(True)
        self.error_config.setStyleSheet("color:#b13d3d")
        ajustes.addWidget(self.error_config)
        cerrar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cerrar.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        cerrar.rejected.connect(self._cerrar_configuracion)
        ajustes.addWidget(cerrar)

    def abrir_configuracion(self):
        self.dialogo_config.show()
        self.dialogo_config.raise_()

    def _marcar_canales(self):
        self.canales_editados = True

    def _alternar_avanzado(self):
        mostrar = self.avanzado.isHidden()
        self.avanzado.setVisible(mostrar)
        self.b_avanzado.setText("Asignaciones y ajustes avanzados  ⌄" if mostrar else "Asignaciones y ajustes avanzados  ›")
        self.dialogo_config.resize(1050 if mostrar else 640, 680 if mostrar else 380)

    def _cerrar_configuracion(self):
        self.dialogo_config.close()

    def mostrar_estado(self, estado, mensaje):
        self.estado.setText(mensaje)
        conectado = estado == "conectado"
        fallo = estado in ("error", "diagnostico")
        self.check.setText("✓" if conectado else "✕" if fallo else "●")
        self.check.setStyleSheet(f"background:{'#7cb342' if conectado else 'transparent'}; "
                                 f"color:{'#17240d' if conectado else '#ef6b6b' if fallo else '#7d848c'}; "
                                 f"border-radius:8px; font-size:{'11px' if conectado or fallo else '10px'}; font-weight:600")
        self.check.setToolTip(mensaje)
        self.estado.setStyleSheet(f"color:{'#9bd68f' if conectado else '#e89a9a' if fallo else '#657e77'}")
        self.estado.setVisible(True)

    def admite(self, vid, area):
        v = next((v for v in self.variables if v["id"] == vid), None)
        return bool(v and not self.bloqueado and encaja(v, area))

    def asignar(self, vid, area, direccion):
        if not self.admite(vid, area):
            return False
        for fila, v in enumerate(self.variables):
            if v["id"] != vid and self.tabla.cellWidget(fila, 0).isChecked() and self.tabla.cellWidget(fila, 4).currentData() == area and self.tabla.cellWidget(fila, 5).value() == direccion:
                self.tabla.cellWidget(fila, 0).setChecked(False)
            if v["id"] == vid:
                seleccionada = fila
        combo = self.tabla.cellWidget(seleccionada, 4)
        combo.setCurrentIndex(combo.findData(area))
        self.tabla.cellWidget(seleccionada, 5).setValue(direccion)
        self.tabla.cellWidget(seleccionada, 0).setChecked(True)
        self._aplicar()
        return True

    def quitar(self, vid):
        if self.bloqueado:
            return
        for fila, v in enumerate(self.variables):
            if v["id"] == vid:
                self.tabla.cellWidget(fila, 0).setChecked(False)
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
        nombres = {v["id"]: v["name"] for v in self.variables}
        host, puerto, unidad = self.conexion_defecto
        config, quitadas = self._depurar(doc, config or Configuracion(host, puerto, unidad, modelo=doc["id"]), nombres)
        quitadas = [*avisos, *quitadas]
        self.doc = doc
        self.config = config
        c = self.config
        c.fijar_escalas_factoryio()
        for area in AREAS:
            posiciones = [s.direccion for s in c.senales if s.area == area]
            rol = "input" if area == "input-register" else "output"
            base = (4 if area == "discrete" else 2 if area == "coil" else
                    2 if any(v["role"] == rol and v["type"]["kind"] in ("int", "decimal") for v in doc["variables"]) else 0)
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
                item.setToolTip(v["id"])
                self.tabla.setItem(fila, col, item)
            area = QComboBox()
            for clave in areas_variable(v):
                area.addItem(AREAS[clave], clave)
            area.setCurrentIndex(area.findData(s.area) if s else 0)
            area.setToolTip("Normalmente: Inputs para sensores y Coils para actuadores. Copia la asignación de Factory I/O.")
            self.tabla.setCellWidget(fila, 4, area)
            direccion = QSpinBox()
            direccion.setRange(0, 65535)
            propuestas = ocupadas[area.currentData()]
            propuesta = next((n for n in range(65536) if n not in propuestas), 0)
            direccion.setValue(s.direccion if s else propuesta)
            propuestas.add(direccion.value())
            direccion.setToolTip("El número exacto de Input o Coil en Factory I/O: Input 0 → 0, Coil 0 → 0. Son áreas independientes.")
            self.tabla.setCellWidget(fila, 5, direccion)
            formato = QComboBox()
            for clave in (["BOOL"] if digital else ["INT16", "UINT16"]):
                formato.addItem(FORMATOS[clave], clave)
            formato.setCurrentIndex(formato.findData(s.formato) if s else 0)
            self.tabla.setCellWidget(fila, 6, formato)
            escala = QLineEdit("1" if digital else "100")
            escala.setReadOnly(True)
            escala.setToolTip("Escala fija: 100 para señales numéricas de entrada y salida; 1 para digitales")
            self.tabla.setCellWidget(fila, 7, escala)
        self.tabla.resizeColumnsToContents()
        self.firma_modelo = self.firma(doc)
        self.pendiente = False
        self.aviso = f"Asignaciones quitadas: {'; '.join(quitadas)}" if quitadas else ""
        self._dibujar()
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
        return self.cargar(doc, base)

    def marcar_pendiente(self, pendiente):
        """Con la conexión viva el mapa en uso no cambia: se avisa de que hay variables nuevas o cambiadas por ver."""
        if pendiente != self.pendiente:
            self.pendiente = pendiente
            self._pintar_nota()

    def _pintar_nota(self):
        partes = (self.aviso, self.pista_canales, "Hay variables nuevas o cambiadas: se verán al desconectar" if self.pendiente else "")
        self.estado.fijar_nota(" · ".join(t for t in partes if t))

    def obtener(self):
        senales = []
        for fila, v in enumerate(self.variables):
            if self.tabla.cellWidget(fila, 0).isChecked():
                senales.append(Senal(v["id"], self.tabla.cellWidget(fila, 4).currentData(),
                                     self.tabla.cellWidget(fila, 5).value(), self.tabla.cellWidget(fila, 6).currentData(),
                                     self.tabla.cellWidget(fila, 7).text()))
        c = Configuracion(self.host.text().strip(), self.puerto.value(), self.unidad.value(),
                          self.periodo.value(), self.timeout.value(), self.doc["id"], senales)
        c.canales = ({area: {"offset": self.offsets[area].value(), "cantidad": self.cantidades[area].value()}
                      for area in AREAS} if self.canales_editados or self.config.canales else {})
        c.fijar_escalas_factoryio()
        c.validar(self.doc)
        return c

    def _aplicar(self):
        try:
            c = self.obtener()
        except ValueError as exc:
            self.estado.setText(f"Mapa inválido: {exc}")
            self.error_config.setText(f"Mapa inválido: {exc}")
            return False
        self.error_config.clear()
        self.config = c
        self.aviso = ""  # el usuario ya ha actuado sobre el mapa
        self._dibujar()
        self.estado.setText("Mapa aplicado · desconectado. Pulsa «Probar conexión» y después «Conectar».")
        self.aplicar.emit(c)
        return True

    def _dibujar(self):
        self.indicadores.clear()
        self.terminales.clear()
        self.indicadores_listas.clear()
        c = self.config
        self.destino.setText(f"({c.host}:{c.puerto})\nEsclavo ID:{c.unidad}")
        self.ayuda_vacio.setVisible(not c.senales)
        for fila in (self.fila_entradas, self.fila_salidas):
            while fila.count():
                item = fila.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
        variables = {v["id"]: v for v in self.variables}
        self.lista_entradas.clear()
        self.lista_salidas.clear()
        asignadas = {s.variable: f"{ETIQUETA_CANAL[s.area]} {s.direccion}" for s in c.senales}
        for rol, titulo in (("input", "SENSORES"), ("output", "ACTUADORES")):
            self.cuentas[rol].setText(f"{titulo} <span style='color:#657e77; font-size:10px'>{sum(v['role'] == rol for v in self.variables)}</span>")
        for v in self.variables:
            item = QListWidgetItem(v["name"])
            item.setSizeHint(QSize(0, ALTO_VARIABLE))
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            item.setData(ROL_COLOR, color_tipo(v))
            item.setData(ROL_ASIGNADA, v["id"] in asignadas)
            item.setData(ROL_ACTIVO, False)
            item.setToolTip(f"{TIPOS[v['type']['kind']]} · " + (f"asignada a {asignadas[v['id']]}" if v["id"] in asignadas else "sin asignar"))
            if v["type"]["kind"] == "duration":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            (self.lista_entradas if v["role"] == "input" else self.lista_salidas).addItem(item)
            self.indicadores_listas[v["id"]] = item
        mapa = {(s.area, s.direccion): s for s in c.senales}
        for area in AREAS:
            numerica = area in ("input-register", "holding")
            entrada = area in ("discrete", "input-register")
            if numerica and area not in c.canales and not any(v["type"]["kind"] in ("int", "decimal") and v["role"] == ("input" if entrada else "output") for v in self.variables):
                continue
            if area in c.canales:
                rango = c.canales[area]
                direcciones = range(rango["offset"], rango["offset"] + rango["cantidad"])
            else:
                direcciones = set(range(2 if numerica or not entrada else 4)) | {d for a, d in mapa if a == area}
            fila = self.fila_entradas if entrada else self.fila_salidas
            for direccion in sorted(direcciones):
                s = mapa.get((area, direccion))
                v = variables.get(s.variable) if s else None
                terminal = TerminalES(self, area, direccion, v)
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
        self.pista_canales = f"Sin canales en {', '.join(vacias)}: sube su cantidad en Configuración" if vacias else ""
        self._pintar_nota()

    def mostrar_valores(self, valores):
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
        self.bloqueado = on
        self.lista_entradas.setDragEnabled(not on)
        self.lista_salidas.setDragEnabled(not on)
        for terminal in self.terminales.values():
            terminal.setAcceptDrops(not on)
            if terminal.b_quitar:
                terminal.b_quitar.setEnabled(not on)
                terminal.b_quitar.setToolTip("Pulsa «Desconectar / editar» para desasignar" if on else "Desasignar esta señal")
                if on:
                    terminal.b_quitar.hide()
        self.b_conectar.setVisible(not on)
        self.b_desconectar.setVisible(on)
        self.b_prueba_guiada.setEnabled(not on)
        self.config_widget.setEnabled(not on)
        for b in (self.b_aplicar, self.b_cargar, self.b_guardar, self.b_probar, self.b_conectar):
            b.setEnabled(not on)
        self.b_desconectar.setEnabled(on)
