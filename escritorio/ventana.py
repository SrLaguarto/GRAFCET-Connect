"""Ventana del simulador GRAFCET de escritorio (P-IMP-29, P-IMP-30): primera versión portable para Windows.

Simula un ejemplo o un modelo guardado (proyecto o documento de modelo, documento 09) con el dibujo de la
norma. Entradas, tiempo real (como un autómata: los retardos son temporizadores que cuentan solos), evolución a
evolución, traza, salidas, variables, temporizadores y, en «Ajustes», las lecturas de interpretación. Toda la
semántica la decide grafcet/engine.py con el perfil provisional: la ventana no aproxima nada y los bloqueos por
cuestiones U se muestran tal cual. No es el editor. Basado en IEC 60848.
"""
from __future__ import annotations

import copy
import html
import json
import os
import re
from time import perf_counter
from math import ceil
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, QEvent, QElapsedTimer, QSettings, Qt, QTimer, QSize, QRectF, QPointF, QUrl
from PySide6.QtGui import (QDesktopServices, QCursor, QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
                               QScrollArea, QSplitter, QStackedWidget, QTabBar, QTableWidget, QTableWidgetItem,
                               QToolBar, QToolButton, QVBoxLayout, QWidget, QStyle, QMenu, QTextEdit, QPlainTextEdit, QAbstractSpinBox)

from . import recursos_ui  # Registra los iconos vectoriales incorporados.
from . import propiedades_archivo
from . import actualizaciones
from grafcet.diagnostics import DiagnosticError
from grafcet.engine import Session
from grafcet.examples import EJEMPLOS
from grafcet.persistence import open_model
from grafcet.profile import APP_VERSION, SEMANTIC_OPTIONS, normalize_options
from grafcet.timeutil import parse_duration
from grafcet.view import Vista, auto_layout, layout_from_presentation, t_trunc

from .diagrama import COL, VistaDiagrama, imagen
from .edicion import HERRAMIENTAS, Edicion, aviso_valores_iniciales, quitar_valores_iniciales, sin_codigos
from .propiedades import PanelPropiedades, Paleta
from .navegacion import Navegacion
from .leyenda import Leyenda
from .recentrado import Recentrado
from .mensajes import amable, motivo_parada, partir
from .alto_opciones import agrandar_para_transicion
from .paneles import PanelPlegable, DivisorPlegable, PilaActual
from .variables import PanelVariables
from .entradas_salidas import CONEXION_INICIAL, PanelES
from conexion.configuracion import ARCHIVO, CANALES_INICIALES, Configuracion, aviso_host, normalizar_host
from conexion.coordinador import Coordinador

TITULO = "GRAFCET Connect"
URL_CODIGO = "https://github.com/SrLaguarto/GRAFCET-Connect"  # dónde está el código (diálogo «Acerca de»)
URL_FALLOS = "https://github.com/SrLaguarto/GRAFCET-Connect/issues"  # dónde se comunica un fallo o una sugerencia
ICONO_PROGRAMA = Path(__file__).resolve().parent / "recursos" / "grafcet_connect.ico"
ANCHO_LATERAL = 212  # ancho mínimo de los paneles laterales al editar (la tabla de variables enseña los nombres)
ALTO_INFERIOR = {"simular": 220, "editar": 240}  # altura inicial del panel inferior: la traza, o las opciones de lo seleccionado
TICK_MS = 100  # tiempo real: cada cuánto se avanza el tiempo lógico
AYUDA_EDICION = {
    "seleccionar": "Clic selecciona un elemento (doble clic o Intro abre sus opciones abajo); arrastrarlo lo mueve (a la "
                   "rejilla, y no encima de otro elemento); de un punto de unión (arriba o abajo de una etapa o transición, "
                   "a la derecha de una etapa) sale un enlace. Supr borra; Ctrl+Z y Ctrl+Y deshacen y rehacen. Los "
                   "elementos y las acciones nuevos se arrastran desde la paleta de la izquierda; otro tipo de acción, con botón derecho "
                   "sobre ella.",
}
NOMBRE_HERRAMIENTA = {"seleccionar": "Seleccionar"}
AVISO = "Basado en IEC 60848"
TEXTOS_FIRMA = {
    "sin_firma": ("Archivo sin firma",
                  "Este archivo no se guardó con esta versión de GRAFCET Connect o se modificó fuera del programa. "
                  "Se puede usar con normalidad; al guardarlo seguirá sin firma."),
    "desarrollo": ("Archivo de la versión de desarrollo (sin firma de esta versión)",
                   "Este archivo está firmado con la clave de la versión de desarrollo, no con la de esta versión. "
                   "Se puede usar con normalidad; al guardarlo seguirá sin firma de esta versión."),
}
ESTADOS = {"pausada-estable": ("estable", "ok"), "pausada-recorrido": ("en recorrido (situación inestable)", "virt"),
           "error": ("detenido por diagnóstico", "err"), "no-compilable": ("no compilable", "err"),
           "finalizada": ("finalizada", "ok"), "preparada": ("preparada", "muted"), "ejecutando": ("ejecutando", "muted")}
TRAZA = {"fallo": "err", "evolucion": "accent", "contexto": "muted"}
ERRORES = (DiagnosticError, RuntimeError, ValueError, KeyError)


def _q_key(q: str) -> list[Any]:
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"[.-]", q)]  # números antes que letras


class DialogoForzado(QDialog):
    """«Forzar un parcial…» y «Editar orden de forzado…»: el parcial destino (por su nombre), la forma de la orden (explícita, la
    situación actual, vacía o inicial) y, solo si es explícita, las etapas del destino que se imponen (selección múltiple por
    nombre). `datos` es lo que prepara `Edicion._datos_forzado`; el resultado (`resultado`) lleva los ID de lo elegido. No
    valida: si la orden no vale (una explícita sin etapas, un ciclo de forzado), lo dice la edición con el aviso en rojo."""

    def __init__(self, parent: QWidget, datos: dict[str, Any]) -> None:
        super().__init__(parent)
        self.datos = datos
        actual = datos.get("actual")
        self.setWindowTitle("Editar orden de forzado" if actual else "Forzar un parcial")
        self.resize(420, 460)
        lay = QVBoxLayout(self)
        nota = QLabel(f"Orden de forzado de la etapa {html.escape(datos['origen'])}: mientras esa etapa esté activa, impone una "
                      "situación al parcial que elija.")
        nota.setWordWrap(True)
        lay.addWidget(nota)
        form = QFormLayout()
        self.destino = QComboBox()
        for pid, nombre in datos["destinos"]:
            self.destino.addItem(nombre, pid)
        form.addRow("Parcial que se fuerza", self.destino)
        lay.addLayout(form)
        caja = QGroupBox("Situación que se impone")
        cl = QVBoxLayout(caja)
        self.grupo = QButtonGroup(self)
        self.formas: dict[str, QRadioButton] = {}
        for clave, texto in datos["formas"]:
            b = QRadioButton(texto)
            self.grupo.addButton(b)
            self.formas[clave] = b
            cl.addWidget(b)
        lay.addWidget(caja)
        self.l_etapas = QLabel("Etapas del parcial que quedan activas (solo en la forma Explícita):")
        self.l_etapas.setWordWrap(True)
        lay.addWidget(self.l_etapas)
        self.etapas = QListWidget()
        lay.addWidget(self.etapas, 1)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)
        if actual:
            self.destino.setCurrentIndex(max(0, self.destino.findData(actual["destino"])))
        self.formas[actual["forma"] if actual and actual["forma"] in self.formas else "explicit"].setChecked(True)
        self._llenar(actual["etapas"] if actual else [])
        self.destino.currentIndexChanged.connect(lambda _: self._llenar([]))
        self.grupo.buttonToggled.connect(lambda *_: self._habilitar())

    def _llenar(self, marcadas: list[str]) -> None:
        """Las etapas del parcial elegido, con casilla, con las `marcadas` ya puestas."""
        self.etapas.clear()
        for sid, nombre in self.datos["etapas"].get(self.destino.currentData(), []):
            it = QListWidgetItem(nombre)
            it.setData(Qt.ItemDataRole.UserRole, sid)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if sid in marcadas else Qt.CheckState.Unchecked)
            self.etapas.addItem(it)
        self._habilitar()

    def _habilitar(self) -> None:
        explicita = self.formas["explicit"].isChecked()
        self.etapas.setEnabled(explicita)
        self.l_etapas.setEnabled(explicita)

    def resultado(self) -> dict[str, Any]:
        """Lo elegido: {destino: ID del parcial, forma: explicit|current|empty|initial, etapas: [ID] (solo las marcadas, y
        solo si la forma es explícita)}."""
        forma = next(k for k, b in self.formas.items() if b.isChecked())
        marcadas = [self.etapas.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.etapas.count())
                    if self.etapas.item(i).checkState() == Qt.CheckState.Checked] if forma == "explicit" else []
        return {"destino": self.destino.currentData(), "forma": forma, "etapas": marcadas}


TEXTOS_FLANCOS = {
    "situacion-anterior": "De uno en uno. Cuando cambia una entrada, solo avanzan las transiciones que ya estaban "
                          "listas antes del cambio: la simulación recorre el grafcet paso a paso. Es lo habitual.",
    "recorrido": "Todo de una vez. Cuando cambia una entrada, el cambio vale durante todo el recorrido de ese "
                 "instante: el grafcet puede avanzar varias etapas seguidas con el mismo cambio."}
# (los valores son los de SEMANTIC_OPTIONS["U-03"])


class Lecturas(QDialog):
    """«Ajustes de simulación»: una sola opción con palabras normales, cuándo vale el cambio de una entrada (la
    lectura U-03 de SEMANTIC_OPTIONS). Las demás lecturas no se muestran: conservan los valores con que se abre."""

    CUESTION = "U-03"

    def __init__(self, parent: QWidget, options: dict[str, str]) -> None:
        super().__init__(parent)
        self.base = dict(options)
        self.setWindowTitle("Ajustes de simulación")
        self.resize(560, 300)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>¿Cuándo vale el cambio de una entrada?</b>"))
        nota = QLabel("Elija cómo reacciona la simulación cuando una entrada cambia de valor. Si cambia el ajuste, la "
                      "simulación se reinicia y la barra de estado avisa de que no es el habitual.")
        nota.setWordWrap(True)
        lay.addWidget(nota)
        spec = SEMANTIC_OPTIONS[self.CUESTION]
        self.grupo = QButtonGroup(self)
        self.botones: dict[str, QRadioButton] = {}
        actual = options.get(self.CUESTION, spec["default"])
        for valor in (v for v in spec["values"] if v in TEXTOS_FLANCOS):
            r = QRadioButton(TEXTOS_FLANCOS[valor])
            r.setStyleSheet("QRadioButton { padding: 4px }")
            r.setChecked(valor == actual)
            self.grupo.addButton(r)
            lay.addWidget(r)
            self.botones[valor] = r
        lay.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText("Volver al ajuste habitual")
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._defaults)
        lay.addWidget(buttons)

    def _defaults(self) -> None:
        self.botones[SEMANTIC_OPTIONS[self.CUESTION]["default"]].setChecked(True)

    def options(self) -> dict[str, str]:
        elegido = next((v for v, r in self.botones.items() if r.isChecked()), self.base.get(self.CUESTION))
        return {**self.base, self.CUESTION: elegido}


class AcercaDe(QDialog):
    """«Acerca de GRAFCET Connect»: icono, versión, licencia, enlace al código, botón para comunicar un fallo y Cerrar. Los
    enlaces se abren con `QDesktopServices` (`abrir`)."""

    ACENTO = "#147f80"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from . import VERSION
        self.setWindowTitle(f"Acerca de {TITULO}")
        self.setMinimumWidth(460)
        self.setStyleSheet("QDialog { background: #f4faf8 } QLabel { color: #1d2330 }")
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        cab = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon(str(ICONO_PROGRAMA)).pixmap(64, 64))
        cab.addWidget(icono)
        titulo = QLabel(f"<span style='font-size:20px; font-weight:600; color:{self.ACENTO}'>{TITULO}</span><br>"
                        f"Versión {VERSION}{' · versión de desarrollo' if sello.DESARROLLO else ''}<br>"
                        "Editor y simulador GRAFCET · Basado en IEC 60848")
        cab.addWidget(titulo, 1)
        lay.addLayout(cab)
        self.l_licencia = QLabel(f"{TITULO} es software libre y de código abierto, publicado con la licencia GPL-3.0. "
                                 f"Su código está en <a href=\"{URL_CODIGO}\">GitHub</a>.<br><br>"
                                 "Para usarlo en un producto o servicio que no pueda cumplir la GPL-3.0, el "
                                 "autor ofrece licencias comerciales: pídalas a través de GitHub.")
        self.l_licencia.setWordWrap(True)
        self.l_licencia.linkActivated.connect(self.abrir)
        lay.addWidget(self.l_licencia)
        self.l_fallos = QLabel("Si encuentras un fallo o tienes una sugerencia, puedes comunicarlo en GitHub:")
        self.l_fallos.setWordWrap(True)
        lay.addWidget(self.l_fallos)
        self.b_fallo = QPushButton("Comunicar un fallo")
        self.b_fallo.setStyleSheet(f"QPushButton {{ background: {self.ACENTO}; color: white; font-weight: 600; "
                                   "border: 0; border-radius: 5px; padding: 6px 14px }")
        self.b_fallo.clicked.connect(lambda: self.abrir(URL_FALLOS))
        fila = QHBoxLayout()
        fila.addWidget(self.b_fallo)
        fila.addStretch(1)
        lay.addLayout(fila)
        garantia = QLabel("Este programa se ofrece sin ninguna garantía. Las licencias, la propia y las de las "
                          "bibliotecas incluidas, están en la carpeta «licencias». Interfaz con Qt for Python "
                          "(PySide6), bajo licencia LGPL v3.")
        garantia.setWordWrap(True)
        garantia.setStyleSheet("color: #6b7385; font-size: 11px")
        lay.addWidget(garantia)
        cerrar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cerrar.rejected.connect(self.reject)
        cerrar.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        lay.addWidget(cerrar)

    def abrir(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))


def _icono_grafcet() -> QIcon:
    """Esquema de etapa, transición y etapa (el dibujo GRAFCET), para el botón que vuelve desde la vista de E/S."""
    pm = QPixmap(40, 40)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#2f5b88"), 3))
    p.drawRect(10, 3, 20, 12)  # etapa
    p.drawLine(20, 15, 20, 20)
    p.drawLine(12, 20, 28, 20)  # transición: la barra que corta el enlace
    p.drawLine(20, 20, 20, 25)
    p.drawRect(10, 25, 20, 12)  # etapa
    p.end()
    return QIcon(pm)


def _trazos_reinicio() -> tuple[QPainterPath, QPainterPath]:
    """Arco abierto arriba y punta angular, según la referencia del responsable."""
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


def _icono_barra(tipo: str, color: str = "#43545e") -> QIcon:
    """Iconos de línea propios para los controles de la aplicación (no son notación GRAFCET)."""
    pm = QPixmap(48, 48)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    trazos = {
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
    }
    if tipo == "play":
        path = QPainterPath()
        path.moveTo(8, 6)
        path.lineTo(18, 12)
        path.lineTo(8, 18)
        path.closeSubpath()
        p.fillPath(path, QColor(color))
    elif tipo == "stop":
        p.fillRect(QRectF(6, 6, 12, 12), QColor(color))
    elif tipo == "dependencias":
        p.drawRect(QRectF(2, 9, 6, 6))
        p.drawRoundedRect(QRectF(15, 3, 8, 18), 1, 1)
        pen = p.pen();pen.setStyle(Qt.PenStyle.DotLine);pen.setWidthF(1.2);p.setPen(pen)
        p.drawLine(QPointF(8, 9), QPointF(15, 3))
        p.drawLine(QPointF(8, 15), QPointF(15, 21))
    elif tipo == "reiniciar":
        arco, punta = _trazos_reinicio()
        p.drawPath(arco)
        p.drawPath(punta)
    for trazo in trazos.get(tipo, []):
        path = QPainterPath()
        path.moveTo(*trazo[0])
        for punto in trazo[1:]:
            path.lineTo(*punto)
        p.drawPath(path)
    p.end()
    return QIcon(pm)


class _BotonEntrada(QPushButton):
    """El estado marcado sigue el valor de la entrada, no el automatismo checkable de Qt."""
    def __init__(self) -> None:
        super().__init__()
        self.setCheckable(True)
        self.control = self.enclavado = self.liberar = self.interruptor = self.nc = False

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self.control = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        super().mousePressEvent(event)

    def indicar(self, on: bool) -> None:
        estado = (self.interruptor, self.enclavado, on)
        if estado == getattr(self, "_indicador", None):
            return
        self._indicador = estado
        pm = QPixmap(20, 16)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#147f80" if on else "#718a85")
        p.setPen(QPen(color, 1.4))
        if self.interruptor:
            p.drawRoundedRect(QRectF(1, 4, 17, 8), 4, 4)
            p.setBrush(color)
            p.drawEllipse(QPointF(14 if on else 5, 8), 2.2, 2.2)
        elif self.enclavado:
            p.drawArc(QRectF(6, 1, 6, 10), 0, 180 * 16)
            p.setBrush(QColor("#d5eee5"))
            p.drawRoundedRect(QRectF(4, 7, 10, 7), 1.5, 1.5)
            p.drawLine(9, 10, 9, 12)
        else:
            p.setBrush(color if on else Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(9, 8), 4, 4)
        p.end()
        self.setIconSize(QSize(20, 16))
        self.setIcon(QIcon(pm))

    def nextCheckState(self) -> None:  # noqa: N802
        pass  # refrescar() pone el valor confirmado por la simulación


class _ControlPulsadores(QObject):
    """Un filtro por aplicación; la liberación se dirige a la ventana que recibe la tecla."""
    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if (evento.type() == QEvent.Type.KeyRelease and evento.key() == Qt.Key.Key_Control
                and not evento.isAutoRepeat()):
            while objeto is not None:
                if isinstance(objeto, Ventana):
                    objeto._soltar_enclavados()
                    break
                objeto = objeto.parent()
        return False


from .archivos import ArchivosProyecto
from . import sello

class _RespuestaModbus(QObject):
    lista = Signal()

    def notificar(self):
        # El trabajador solo despierta al propietario; nunca toca Qt ni la sesión.
        try:
            self.lista.emit()
        except RuntimeError:
            pass  # La ventana puede haberse destruido mientras terminaba la red.


class Ventana(ArchivosProyecto, QMainWindow):
    def __init__(self, ajustes: QSettings | None = None, obtener=None) -> None:
        super().__init__()
        self.setWindowTitle(TITULO)
        self.resize(1360, 860)
        # Preferencias de la interfaz (paneles plegados) en un .ini del usuario, sin tocar el registro
        self.ajustes = ajustes or QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "GRAFCET", "Simulador")
        self.options = normalize_options(None)  # por defecto: decisiones del responsable y, lo abierto, detener
        self.fuente: dict[str, Any] = {}
        self.v: Vista | None = None
        self.claves_entradas: tuple[str, ...] = ()
        self.botones: dict[str, QPushButton] = {}
        self.campos: dict[str, QLineEdit] = {}
        self.rt = QTimer(self)
        self.rt.setTimerType(Qt.TimerType.PreciseTimer)
        self.rt.setInterval(TICK_MS)
        self.rt.timeout.connect(self._tick)
        self.reloj = QElapsedTimer()
        self.edicion: Edicion | None = None
        self._alturas = dict(ALTO_INFERIOR)
        self.modo = "editar"  # solo cambia con Play (simular) y Pausa (editar)
        self._respuesta_modbus = _RespuestaModbus(self)
        self._respuesta_modbus.lista.connect(self._tick, Qt.ConnectionType.QueuedConnection)
        self.modbus = Coordinador(self._respuesta_modbus.notificar)
        self._proxima_lectura = QTimer(self)
        self._proxima_lectura.setSingleShot(True)
        self._proxima_lectura.setTimerType(Qt.TimerType.PreciseTimer)
        self._proxima_lectura.timeout.connect(self._tick)
        self._ultimo_refresco_modbus = 0.0
        self._marca_reloj_ns = 0
        self._resto_reloj_ns = 0
        self._transicion_ui = False  # Play/Pausa en curso: los cambios que él mismo provoca no lo repiten
        self._aviso_inestable_sesion = None  # sesión de la que ya se avisó (un solo aviso por episodio)
        self._popup_inestable = None
        self._avisos_ejecucion: list[tuple[str, str]] = []  # por qué se paró el motor (texto, ayuda): entre los avisos al editar
        self._ayuda = ""  # ayuda del ejemplo o modelo abierto, para mostrarla al simular lo que aún no se ha editado
        self._proyecto: Any = None  # qué proyecto hay abierto (los ID de modelo no lo distinguen: todos los ejemplos son «m»)
        self._proyecto_modbus: Any = None  # de qué proyecto es el mapa que tiene cargado el panel de E/S
        self._n_nuevos = 0
        self._tipos_entrada: dict[tuple[Any, str], bool] = {}
        self._entradas_nc = {}
        self._portapapeles = None
        self._menus()
        self._interfaz()
        self.diagrama.menu_portapapeles = self._menu_portapapeles
        QApplication.instance().focusChanged.connect(self._actualizar_portapapeles)
        app = QApplication.instance()
        if not hasattr(app, "_control_pulsadores"):
            app._control_pulsadores = _ControlPulsadores(app)
            app.installEventFilter(app._control_pulsadores)
        self.panel_es = PanelES()
        self._parametros_recordados = self._leer_parametros_recordados()
        self._conexion_recordada = tuple(self._parametros_recordados[k] for k in ("host", "puerto", "unidad"))
        self.panel_es.conexion_defecto = self._conexion_recordada
        self.panel_es.aviso_host_defecto = getattr(self, "_aviso_host_recordado", "")
        self.panel_es.parametros_defecto = copy.deepcopy(self._parametros_recordados)
        central = self.takeCentralWidget()
        self.paginas_es = QStackedWidget()
        self.paginas_es.addWidget(central)
        self.paginas_es.addWidget(self.panel_es)
        from .planos import PaginaPlanos
        self.panel_planos=PaginaPlanos(self)
        self.paginas_es.addWidget(self.panel_planos)
        contenedor=QWidget();disposicion=QVBoxLayout(contenedor);disposicion.setContentsMargins(0,0,0,0);disposicion.setSpacing(0)
        self.pestanas_vistas=QTabBar();self.pestanas_vistas.setExpanding(False);self.pestanas_vistas.setDrawBase(True)
        for texto in ('GRAFCET','PLANOS','E/S externas'):self.pestanas_vistas.addTab(texto)
        self.pestanas_vistas.setTabVisible(2,False)  # a E/S se entra por la luz de conexión (`luz_es`); el índice 2 solo marca la página
        self.pestanas_vistas.setStyleSheet("QTabBar {background:#e4eae9; border:0;} QTabBar::tab {min-width:100px; padding:5px 20px; margin:3px 3px 0 0; background:transparent; color:#536169; border:0; border-top-left-radius:9px; border-top-right-radius:9px;} QTabBar::tab:selected {background:white; color:#20343b;} QTabBar::tab:hover:!selected {background:#d7e1df;}")
        # La fila de arriba: las pestañas a la izquierda y, a la derecha del todo, la luz de la conexión externa (`luz_es`)
        self.fila_pestanas=QWidget();self.fila_pestanas.setObjectName('filaPestanas');self.fila_pestanas.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.fila_pestanas.setStyleSheet('QWidget#filaPestanas {background:#e4eae9;}')
        fila_p=QHBoxLayout(self.fila_pestanas);fila_p.setContentsMargins(0,0,6,0);fila_p.setSpacing(0)
        fila_p.addWidget(self.pestanas_vistas);fila_p.addStretch(1)
        disposicion.addWidget(self.fila_pestanas)
        self.aviso_traer=QWidget();self.aviso_traer.setObjectName('avisoSeleccionPlanos');self.aviso_traer.setStyleSheet('QWidget#avisoSeleccionPlanos {background:#f3e9cd; color:#574922; border-radius:3px;} QWidget#avisoSeleccionPlanos QLabel {background:transparent;} QWidget#avisoSeleccionPlanos QPushButton {background:white; color:#3b403b; border:1px solid #9b8959; padding:6px 12px; border-radius:3px;} QWidget#avisoSeleccionPlanos QPushButton:hover {background:#fffaf0; border-color:#665526;} QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja {background:#27665c; color:white; border-color:#1d5048;} QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja:hover {background:#1b5149;}');fila=QHBoxLayout(self.aviso_traer);fila.setContentsMargins(12,7,12,7);fila.addWidget(QLabel('PLANOS · Selecciona el GRAFCET para la hoja'))
        self.b_confirmar_traer=QPushButton('Añadir selección a la hoja');self.b_confirmar_traer.setObjectName('confirmarSeleccionHoja');fila.addWidget(self.b_confirmar_traer);cancelar=QPushButton('Cancelar');fila.addWidget(cancelar);fila.addStretch(1)
        self.b_confirmar_traer.clicked.connect(self.confirmar_traer);cancelar.clicked.connect(self.cancelar_traer)
        self.destino_traer=None;self.aviso_traer.hide();disposicion.addWidget(self.paginas_es,1);disposicion.addWidget(self.aviso_traer)
        self.setCentralWidget(contenedor)
        self.pestanas_vistas.currentChanged.connect(lambda i:self.mostrar_es() if i==2 else self._mostrar_pagina('planos' if i==1 else False))
        self.panel_es.volver.connect(lambda: self._mostrar_pagina(False))
        self.panel_es.conectar.connect(self._conectar_modbus)
        self.panel_es.probar.connect(lambda: self._conectar_modbus(prueba=True))
        self.panel_es.desconectar.connect(self._desconectar_modbus)
        self.panel_es.guardar.connect(self._guardar_config_modbus)
        self.panel_es.cargar_archivo.connect(self._abrir_config_modbus)
        self.panel_es.aplicar.connect(self._persistir_mapa_modbus)
        self._barra_herramientas()
        self._paneles()
        self.panel_es.estado_cambiado.connect(self._luz_es)
        self._version_nueva: actualizaciones.Resultado | None = None
        self.comprobador = actualizaciones.Comprobador(self, obtener)
        self.comprobador.resultado.connect(self._resultado_actualizacion)
        self.nuevo()
        self._cargar_config_modbus(self.edicion.ed.model)
        for nombre in ("izquierdo","derecho","inferior"):
            self._mostrar_panel(nombre, nombre != "inferior" or self._inferior_al_arrancar, guardar=False)
        self._accesibilidad()

    # -- construcción ---------------------------------------------------------------------------
    def _accion(self, texto: str, slot: Any, atajo: str | list[str] | None = None, marcable: bool = False) -> QAction:
        a = QAction(texto, self)
        a.setCheckable(marcable)
        if atajo:
            a.setShortcuts([QKeySequence(x) for x in ([atajo] if isinstance(atajo, str) else atajo)])
        (a.toggled if marcable else a.triggered).connect(slot)
        return a

    def _seleccionar_teclado(self, h):
        self.herramienta(h)
        if self.edicion and self.diagrama.hasFocus(): self.edicion.seleccionar([])

    def buscar_elemento(self):
        self._mostrar_pagina(False); self.navegacion.abrir()

    def insertar_teclado(self, tipo):
        if self.modo != 'editar' or self.edicion is None or getattr(self,"solo_lectura",False): return
        p = self.diagrama.mapToScene(self.diagrama.viewport().rect().center())
        if tipo == 'transicion': self.edicion.poner_transicion(p)
        else: self.edicion.poner_etapa(p, tipo == 'inicial')
        self.diagrama.setFocus()

    def conectar_teclado(self):
        e = self.edicion
        if self.modo != 'editar' or not e or len(e.sel) != 1 or getattr(self,'solo_lectura',False): return
        origen = e.sel[0]
        destinos = [d for d in self.navegacion.datos if d['id'] != origen and d['tipo'] in ('Etapa', 'Transición', 'Macroetapa', 'Barra')]
        nombres = [d['texto'] for d in destinos]
        elegido, ok = QInputDialog.getItem(self, 'Conectar elementos', 'Destino del enlace', nombres, 0, False)
        if ok and elegido in nombres: e.conectar(origen, destinos[nombres.index(elegido)]['id'])
        self.activateWindow(); self.diagrama.setFocus()

    def _accesibilidad(self):
        from PySide6.QtWidgets import QAbstractButton
        for boton in self.findChildren(QAbstractButton):
            if not boton.accessibleName(): boton.setAccessibleName((boton.text() or boton.toolTip()).replace('&',''))
            if not boton.accessibleDescription(): boton.setAccessibleDescription(boton.toolTip() or boton.accessibleName())
        for nombre in ('izquierdo', 'derecho', 'inferior'):
            self._plegables[nombre].setAccessibleName({'izquierdo':'Elementos','derecho':'Variables y simulación','inferior':'Propiedades y traza'}[nombre])
            self._plegables[nombre].setAccessibleDescription('Panel plegable. Use su cabecera para ocultarlo o su pestaña para recuperarlo.')

    def _menus(self) -> None:
        bar = self.menuBar()
        archivo = bar.addMenu("&Proyecto")
        self.a_nuevo = self._accion("&Nuevo proyecto", self.nuevo, "Ctrl+N")
        archivo.addAction(self.a_nuevo)
        a = self.a_abrir = archivo.addAction("&Abrir…", self.abrir)
        a.setShortcut(QKeySequence.StandardKey.Open)
        self.a_guardar = archivo.addAction("&Guardar", self.guardar)
        self.a_guardar.setShortcut(QKeySequence.StandardKey.Save)
        self.a_guardar_como = self._accion("Guardar &como…", self.guardar_como, "Ctrl+Shift+S")
        archivo.addAction(self.a_guardar_como)
        self.a_exportar = archivo.addAction("&Exportar…", lambda:self.abrir_laminas("exportar"))
        self.a_imprimir = self._accion("&Imprimir…", lambda:self.abrir_laminas("imprimir"), "Ctrl+P")
        archivo.addAction(self.a_imprimir)
        archivo.addAction("Guardar el &dibujo como imagen…", self.guardar_imagen)
        archivo.addAction("Propiedades del archi&vo…", lambda *_: propiedades_archivo.abrir(self))
        archivo.addSeparator()
        archivo.addAction("&Salir", self.close).setShortcut(QKeySequence.StandardKey.Quit)
        ejemplos = bar.addMenu("&Ejemplos")
        self.grupo = QActionGroup(self)
        from grafcet.ejemplos_aula import DIDACTICOS
        avanzados=ejemplos.addMenu("Más ejemplos y casos de estudio")
        self.acciones_ej: dict[str, QAction] = {}
        for key in (*DIDACTICOS,*(k for k in EJEMPLOS if k not in DIDACTICOS)):
            title,_,_=EJEMPLOS[key]
            act = (ejemplos if key in DIDACTICOS else avanzados).addAction(title)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, k=key: self.cargar_ejemplo(k))
            self.grupo.addAction(act)
            self.acciones_ej[key] = act
        ejemplos.removeAction(avanzados.menuAction());ejemplos.addSeparator();ejemplos.addAction(avanzados.menuAction())
        # Un solo control de ejecución: Play simula (traza abajo, sin paleta) y Pausa detiene y vuelve a editar
        self.a_ejecutar = self._accion("Play", self._ejecutar, "F5", marcable=True)
        self.a_ejecutar.setToolTip("Play: iniciar una simulación nueva · Stop: detener y dejar todo a 0 (F5)")
        self.a_reiniciar = self._accion("Reiniciar", self.reiniciar, "Ctrl+R")
        self.a_reiniciar.setToolTip("Volver a la situación inicial; en Play sigue en Play (Ctrl+R)")
        ver = bar.addMenu("&Ver")
        self.a_izquierdo = self._accion("Panel i&zquierdo (al editar)", lambda on: self._mostrar_panel("izquierdo", on),
                                        "Ctrl+L", True)
        self.a_derecho = self._accion("Panel &derecho", lambda on: self._mostrar_panel("derecho", on), "Ctrl+B", True)
        self.a_inferior = self._accion("Panel &inferior", lambda on: self._mostrar_panel("inferior", on), "Ctrl+J", True)
        ver.addAction(self.a_izquierdo)
        ver.addAction(self.a_derecho)
        ver.addAction(self.a_inferior)
        ver.addSeparator()
        ver.addAction(self._accion("&Acercar", lambda: self.diagrama.acercar(), ["Ctrl+=", "Ctrl++"]))
        ver.addAction(self._accion("A&lejar", lambda: self.diagrama.alejar(), "Ctrl+-"))
        ver.addAction(self._accion("&Centrar todo el dibujo", lambda: self.diagrama.ajustar(), "Ctrl+0"))
        # Edición
        self.a_herr: dict[str, QAction] = {}
        self.g_herr = QActionGroup(self)
        for h in HERRAMIENTAS:  # solo las que no colocan elementos: los elementos y las acciones se arrastran desde la paleta
            atajo = "Esc"
            a = self._accion("Seleccionar", lambda on, h=h: on and self.herramienta(h), atajo, True)
            a.triggered.connect(lambda on=False, h=h: self._seleccionar_teclado(h))
            a.setToolTip(f"{NOMBRE_HERRAMIENTA[h]} ({atajo}): {AYUDA_EDICION[h]}")
            self.g_herr.addAction(a)
            self.a_herr[h] = a
        self.a_herr["seleccionar"].blockSignals(True)
        self.a_herr["seleccionar"].setChecked(True)
        self.a_herr["seleccionar"].blockSignals(False)
        self.a_deshacer = self._accion("&Deshacer", lambda: self.historial_plano(False), "Ctrl+Z")
        self.a_rehacer = self._accion("&Rehacer", lambda: self.historial_plano(True), ["Ctrl+Y", "Ctrl+Shift+Z"])
        self.a_borrar = self._accion("&Borrar la selección\tSupr", lambda: self.edicion and self.edicion.borrar(), "Del")
        self.a_debajo = self._accion("&Añadir debajo\tCtrl+Enter", lambda: self.edicion and self.edicion.anadir_debajo(), "Ctrl+Return")
        self.a_debajo.setToolTip("Con una etapa seleccionada: transición y etapa enlazadas debajo (Ctrl+Intro)")
        # El atajo (Ctrl+Mayús+Izquierda/Derecha) lo trata VistaDiagrama.keyPressEvent: aquí solo va en el texto, sin QShortcut,
        # para no crear un atajo ambiguo.
        self.a_girar_izq = self._accion("Girar transición en sentido &antihorario	Ctrl+Mayús+Izquierda",
                                        lambda: self.edicion and self.edicion.girar_transiciones(-1))
        self.a_girar_der = self._accion("Girar transición en sentido &horario	Ctrl+Mayús+Derecha",
                                        lambda: self.edicion and self.edicion.girar_transiciones(1))
        self.a_cortar = self._accion("Cortar", lambda: self._portapapeles_accion("cortar"), "Ctrl+X")
        self.a_copiar = self._accion("Copiar", lambda: self._portapapeles_accion("copiar"), "Ctrl+C")
        self.a_pegar = self._accion("Pegar", lambda: self._portapapeles_accion("pegar"), "Ctrl+V")
        edicion = bar.addMenu("&Edición")
        for a in (self.a_cortar, self.a_copiar, self.a_pegar):
            edicion.addAction(a)
        edicion.addSeparator()
        self.a_buscar = self._accion("Buscar elemento…", self.buscar_elemento, "Ctrl+F")
        edicion.addAction(self.a_buscar)
        insertar = edicion.addMenu("Añadir &elemento")
        for texto, tipo in (("&Etapa", "etapa"), ("Etapa &inicial", "inicial"), ("&Transición", "transicion")):
            insertar.addAction(texto, lambda _=False, tipo=tipo: self.insertar_teclado(tipo))
        self.a_enviar_lamina=self._accion("Enviar a plano…",self.enviar_seleccion_lamina)
        edicion.addAction(self.a_enviar_lamina)
        edicion.addSeparator()
        for a in (self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo, self.a_girar_izq, self.a_girar_der):
            edicion.addAction(a)
        edicion.addSeparator()
        for a in self.a_herr.values():
            self.addAction(a)  # Esc deselecciona sin presentar «Seleccionar» como un atajo de clic
        # Enlazar sin ratón (REQ-EDT-13): sin entrada en el menú (P-IMP-104), solo con el atajo Ctrl+K.
        self.a_conectar = self._accion("Conectar con…", self.conectar_teclado, "Ctrl+K")
        self.addAction(self.a_conectar)
        sim = bar.addMenu("&Simulación")
        for a in (self.a_ejecutar, self.a_reiniciar):
            sim.addAction(a)
        m_ajustes = bar.addMenu("A&justes")
        m_ajustes.addAction("&Ajustes de simulación…", self.lecturas)
        self.a_actualizar_arranque = self._accion("&Buscar actualizaciones al arrancar", self._buscar_al_arrancar, marcable=True)
        self.a_actualizar_arranque.blockSignals(True)
        self.a_actualizar_arranque.setChecked(actualizaciones.al_arrancar_activo(self.ajustes))
        self.a_actualizar_arranque.blockSignals(False)
        m_ajustes.addAction(self.a_actualizar_arranque)
        ayuda = bar.addMenu("A&yuda")
        ayuda.addAction("&Leyenda del dibujo", self.leyenda)
        ayuda.addAction("&Buscar actualizaciones…", lambda: self.buscar_actualizaciones(True))
        ayuda.addAction("&Acerca de GRAFCET Connect…", self.acerca)
        for menu in (archivo, edicion, ver, ejemplos, sim, m_ajustes, ayuda):
            bar.removeAction(menu.menuAction())
            bar.addAction(menu.menuAction())

    def _caja(self, titulo: str) -> tuple[QGroupBox, QVBoxLayout]:
        box = QGroupBox(titulo)
        lay = QVBoxLayout(box)
        self.lado.addWidget(box)
        return box, lay

    def _interfaz(self) -> None:
        izq = QWidget()
        izq.setObjectName("panelDibujo")
        il = QVBoxLayout(izq)
        il.setContentsMargins(10, 5, 10, 6)
        il.setSpacing(4)
        cab = QHBoxLayout()
        self.estado = QLabel()
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-size: 15px; font-weight: 600; color: #147f80")
        cab.addWidget(self.estado)
        cab.addWidget(self.titulo)
        il.addLayout(cab)
        self.ayuda = QLabel()
        self.ayuda.setWordWrap(False)
        self.ayuda.setMinimumWidth(0)
        from PySide6.QtWidgets import QSizePolicy
        self.ayuda.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.ayuda.setStyleSheet(f"color: {COL['muted']}")
        cab.addWidget(self.ayuda,1)
        self.diagrama = VistaDiagrama()
        self.recentrado = Recentrado(lambda: self.diagrama.ajustar(), self)
        self.navegacion = Navegacion(self.diagrama)
        cab.addWidget(self.navegacion)
        self.estado.setMinimumHeight(self.navegacion.buscador.sizeHint().height()+4)
        ver_navegacion = self._accion("Navegación y filtros…", self.navegacion.abrir_opciones)
        next(a.menu() for a in self.menuBar().actions() if a.text()=="&Ver").addAction(ver_navegacion)
        il.addWidget(self.diagrama, 1)
        # Panel inferior: al simular, la traza; al editar, las opciones de lo seleccionado
        self.traza = QListWidget()
        self.traza.setWordWrap(True)
        caja_traza = QGroupBox("Traza")
        QVBoxLayout(caja_traza).addWidget(self.traza)
        self.props = PanelPropiedades()
        self.props.setObjectName("panelPropiedades")
        self.inferior = PilaActual()
        self.inferior.addWidget(caja_traza)
        self.inferior.addWidget(self.props)
        self._leyenda: QDialog | None = None

        der = QWidget()
        self.lado = QVBoxLayout(der)
        self.diag = QLabel()
        self.diag.setWordWrap(True)
        self.diag.setTextFormat(Qt.TextFormat.RichText)
        self.diag.setStyleSheet(f"border: 1px solid {COL['err']}; background: #fdecea; color: #1d2330; "
                                "border-radius: 6px; padding: 8px")
        self.lado.addWidget(self.diag)

        _, lay = self._caja("Entradas")
        self.rejilla = QGridLayout()
        lay.addLayout(self.rejilla)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"color: {COL['err']}")
        lay.addWidget(self.aviso)

        _, lay = self._caja("Salidas y variables")
        self.t_vars = self._tabla(["Variable", "Modo", "Valor", "Contribuyen"])
        lay.addWidget(self.t_vars)
        self.c_temp, lay = self._caja("Temporizadores")
        self.t_temp = self._tabla(["Dónde", "Estado", "Lleva", "Preset"])
        lay.addWidget(self.t_temp)
        self.lado.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(der)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # con la ventana pequeña, también se desplaza a los lados
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Página de edición: la herramienta, la selección y los diagnósticos (REQ-EDT-09)
        pag = QWidget()
        pag.setObjectName("panelVariables")
        pl = QVBoxLayout(pag)
        pl.setContentsMargins(8, 8, 8, 8)  # el panel es estrecho: poco marco, para que quepa la tabla de variables
        self.l_herr = QLabel()
        self.l_herr.setWordWrap(True)
        self.l_herr.setTextFormat(Qt.TextFormat.RichText)
        self.l_herr.hide()  # la misma ayuda ya va sobre el dibujo; aquí no cabe en un panel estrecho (sigue en el objeto)
        pl.addWidget(self.l_herr)
        self.l_sel = QLabel()
        self.l_sel.setWordWrap(True)
        pl.addWidget(self.l_sel)
        self.l_sel.hide()  # la selección se identifica en el encabezado de Propiedades
        self.variables = PanelVariables()
        caja_vars = QGroupBox("Variables")
        caja_vars.setObjectName("grupoVariables")
        caja_vars.setStyleSheet("QGroupBox { font-size: 16px; font-weight: 600; color: #122849; }")
        cv = QVBoxLayout(caja_vars)
        cv.setContentsMargins(1, 1, 1, 1)
        cv.addWidget(self.variables)
        self.variables.setMinimumHeight(140)
        self.l_resumen = QLabel()  # resumen accesible para la validación, sin bloque lateral
        self.l_resumen.hide()
        self.lista_diag = self.diagrama.lista_diagnosticos
        self.lista_diag.itemClicked.connect(self._ir_a_diagnostico)
        pl.addWidget(caja_vars)
        pl.addStretch(1)
        self.derecho = PilaActual()
        self.derecho.addWidget(self.scroll)
        pag_scroll = QScrollArea()  # si no cabe, se desplaza en alto y en ancho
        pag_scroll.setWidgetResizable(True)
        pag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pag_scroll.setWidget(pag)
        self.derecho.addWidget(pag_scroll)
        self.derecho.setMinimumWidth(300)  # al simular; al editar, el mismo margen de ancho que el panel izquierdo
        # Izquierda: la paleta (una sola lista de fichas); solo al editar. Las opciones de lo seleccionado van abajo.
        self.paleta = Paleta()
        self.paleta.setMinimumWidth(self.paleta.ancho_minimo())  # las dos columnas de fichas, sin cortarse
        self.paleta.ayuda.connect(self._ayuda_ficha)  # un clic en una ficha solo muestra su ayuda
        self.paleta.escala = self.diagrama.escala
        self.dock = QWidget()  # panel izquierdo: solo a la altura del dibujo, no del panel inferior
        self.dock.setObjectName("panelElementos")
        vl = QVBoxLayout(self.dock)
        vl.setContentsMargins(0, 0, 0, 0)
        titulo_elementos = QLabel("Elementos")
        titulo_elementos.setObjectName("tituloPanel")
        titulo_elementos.setContentsMargins(12, 10, 8, 6)
        vl.addWidget(titulo_elementos)
        vl.addWidget(self.paleta, 1)
        # Ancho de los paneles laterales al editar: único y fijo (lo que piden las dos columnas de la paleta y, como mínimo,
        # lo que hace falta para que la tabla de variables deje ver los nombres), el mismo en el panel izquierdo y en el
        # izquierdo fijo; el derecho puede ampliarse y ambos se pueden plegar
        self.ancho_lateral = max(self.dock.minimumSizeHint().width(), ANCHO_LATERAL)
        self.dock.setFixedWidth(self.ancho_lateral)
        self.dock.hide()
        # Arriba, el panel izquierdo (solo al editar), el dibujo y el panel derecho; abajo, a todo el ancho de la ventana, el
        # panel inferior (traza, opciones): así una fórmula larga o dos programadores por bloques caben sin apretarse.
        self._plegables = {n: PanelPlegable(c, titulo, n, lambda n=n: self._minimo_panel(n))
                          for n, c, titulo in (("izquierdo", self.dock, "Elementos"),
                                               ("derecho", self.derecho, "Variables"),
                                               ("inferior", self.inferior, "Propiedades"))}
        self._tamanos_paneles = {"izquierdo": self.ancho_lateral, "derecho": self.ancho_lateral, "inferior": ALTO_INFERIOR["editar"]}
        self.split = DivisorPlegable(Qt.Orientation.Horizontal)
        self.split.addWidget(izq)
        self.split.addWidget(self._plegables["derecho"])
        self.split.configurar(1, "derecho", 1, self._plegables["derecho"])
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 0)
        self.split.setHandleWidth(8)
        self.split.setSizes([880, 460])
        self.split_izquierdo = DivisorPlegable(Qt.Orientation.Horizontal)
        self.split_izquierdo.addWidget(self._plegables["izquierdo"])
        self.split_izquierdo.addWidget(self.split)
        self.split_izquierdo.setStretchFactor(0, 0)
        self.split_izquierdo.setStretchFactor(1, 1)
        self.split_izquierdo.configurar(1, "izquierdo", 0, self._plegables["izquierdo"])
        self.vsplit = DivisorPlegable(Qt.Orientation.Vertical)
        self.vsplit.addWidget(self.split_izquierdo)
        self.vsplit.addWidget(self._plegables["inferior"])
        self.vsplit.configurar(1, "inferior", 1, self._plegables["inferior"])
        for divisor in (self.split_izquierdo, self.split, self.vsplit):
            divisor.plegar.connect(self._plegar_desde_divisor)
            divisor.abrir.connect(self._abrir_desde_tiron)
        self.vsplit.setCollapsible(0, False)
        self.vsplit.setCollapsible(1, False)  # el panel inferior se pliega con su flecha, no arrastrando: nunca por debajo de lo que pide
        self.vsplit.setHandleWidth(8)
        self._opciones_automaticas = True
        self._seleccion_alto: tuple[str, tuple[str, ...]] | None = None  # qué selección comprobó ya el alto del panel
        self.vsplit.splitterMoved.connect(lambda *_: setattr(self, "_opciones_automaticas", False))
        self.vsplit.setStretchFactor(0, 1)  # al agrandar la ventana crece el dibujo; el panel inferior conserva su altura
        self.vsplit.setStretchFactor(1, 0)
        self.vsplit.setSizes([520, ALTO_INFERIOR["simular"]])
        self.setCentralWidget(self.vsplit)
        self.props.t_fijar.toggled.connect(self._fijar_cambiado)
        # Barra de estado: aviso de conformidad, lecturas distintas de las decididas, instante lógico
        sb = self.statusBar()
        self.l_aviso = QLabel(AVISO)
        self.l_lect = QLabel()
        self.l_lect.setStyleSheet(f"color: {COL['err']}")
        self.l_reloj = QLabel()
        self.l_reloj.setStyleSheet("font-weight: 600")
        sb.addWidget(self.l_aviso, 1)
        self.l_firma = QLabel()  # «Archivo sin firma»: discreto y permanente mientras el archivo abierto no tenga firma válida
        self.l_firma.setStyleSheet(f"color: {COL['muted']}")
        self.l_firma.hide()
        sb.addWidget(self.l_firma)
        self.aviso_version = QFrame()  # aviso discreto y descartable de versión nueva (no modal)
        self.aviso_version.setObjectName("avisoVersion")
        self.aviso_version.setStyleSheet("QFrame#avisoVersion { background: #e8f5f3; border: 1px solid #a2d2cd; border-radius: 4px; } "
                                         "QFrame#avisoVersion QPushButton { padding: 1px 8px; }")
        av = QHBoxLayout(self.aviso_version)
        av.setContentsMargins(8, 1, 4, 1)
        self.l_version = QLabel()
        av.addWidget(self.l_version)
        self.b_descargar = QPushButton("Descargar")
        self.b_descargar.clicked.connect(self._descargar_version)
        self.b_ahora_no = QPushButton("Ahora no")
        self.b_ahora_no.clicked.connect(self._descartar_version)
        av.addWidget(self.b_descargar)
        av.addWidget(self.b_ahora_no)
        self.aviso_version.setFixedHeight(20)  # no más alto que la barra de estado: al mostrarse no debe cambiar su altura
        self.b_descargar.setFixedHeight(18)
        self.b_ahora_no.setFixedHeight(18)
        av.setContentsMargins(8, 0, 4, 0)
        self.aviso_version.hide()
        sb.addWidget(self.aviso_version)
        # el mensaje temporal sustituye al texto fijo mientras dura (si no, se dibujan uno encima del otro)
        sb.messageChanged.connect(lambda texto: self.l_aviso.setVisible(not texto))
        sb.addPermanentWidget(self.l_lect)
        sb.addPermanentWidget(self.l_reloj)

    def _barra_herramientas(self) -> None:
        for accion, tipo in ((self.a_nuevo, "nuevo"), (self.a_abrir, "abrir"), (self.a_guardar, "guardar"),
                             (self.a_deshacer, "deshacer"), (self.a_rehacer, "rehacer"), (self.a_borrar, "borrar"),
                             (self.a_debajo, "debajo"), (self.a_ejecutar, "play"), (self.a_reiniciar, "reiniciar")):
            accion.setIcon(_icono_barra(tipo))
        self.tb_proyecto = QToolBar("Proyecto")
        self.tb_proyecto.setMovable(False)
        self.tb_proyecto.setIconSize(QSize(20, 20))
        self.tb_proyecto.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for accion in (self.a_nuevo, self.a_abrir, self.a_guardar):
            self.tb_proyecto.addAction(accion)
        self.tb_proyecto.widgetForAction(self.a_guardar).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for accion, texto in ((self.a_nuevo, "Nuevo"), (self.a_abrir, "Abrir"), (self.a_guardar, "Guardar")):
            boton = self.tb_proyecto.widgetForAction(accion)
            boton.setText(texto)
            accion.changed.connect(lambda b=boton, t=texto: b.setText(t))
        self.addToolBar(self.tb_proyecto)
        self.setStyleSheet("""
            QWidget { font-family: "Segoe UI"; font-size: 12px; color: #132b46; }
            QMainWindow, QDialog { background: #eef7f7; }
            QWidget#panelDibujo, QWidget#panelElementos, QWidget#panelVariables,
            QWidget#panelPropiedades { background: white; border: 1px solid #d4e7e8; border-radius: 7px; }
            QLabel#tituloPanel { font-size: 16px; font-weight: 600; color: #122849; border: 0; }
            QWidget#cabeceraPropiedades { background: #eaf6f5; border-radius: 4px; }
            QLabel#tituloPropiedades { color: #127c80; font-size: 13px; font-weight: 600; background: transparent;
                padding: 3px 0; }
            QLabel#ayudaPropiedades { color: #657b8b; padding: 4px 8px; }
            QMenuBar { background: white; padding: 2px 8px; border-bottom: 1px solid #e2eeee; }
            QMenuBar::item { padding: 5px 10px; }
            QMenuBar::item:selected, QMenu::item:selected { background: #e8f5f3; }
            QMenu { background: white; border: 1px solid #cde2e3; padding: 4px; }
            QMenu::item { padding: 6px 22px; }
            QToolBar { background: white; border: 0; border-bottom: 1px solid #dcebec; spacing: 5px; padding: 3px 3px; }
            QToolBar QToolButton { padding: 3px 7px; border: 1px solid transparent; border-radius: 2px; }
            QToolButton#bibliotecaPlanos { padding-right:28px; }
            QToolButton#bibliotecaPlanos::menu-indicator { image:url(:/grafconnect/desplegar.svg); subcontrol-origin:padding; subcontrol-position:center right; right:8px; width:12px; height:8px; }
            QToolBar QToolButton:hover { background: #edf8f6; border-color: #c7e5e1; }
            QToolBar QToolButton:checked { background: #d5e6e2; border-color: #82aaa2; color:#23483f; }
            QToolBar#barraSimulacion QToolButton { color: #334b50; background: transparent; padding: 3px 10px; }
            QToolBar#barraSimulacion QToolButton:hover { background: #d9efeb; }
            QToolBar#barraConexion QToolButton { border: 1px solid #a2d2cd; background: white; color: #167d80; }
            QLineEdit, QComboBox, QSpinBox { background: white; border: 1px solid #ccdfe5; border-radius: 4px;
                padding: 4px 6px; selection-background-color: #258d88; }
            QComboBox { padding-right:28px; min-height:18px; }
            QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; width:24px; border:0; background:transparent; }
            QComboBox::down-arrow { image:url(:/grafconnect/desplegar.svg); width:12px; height:8px; }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPushButton:focus,
            QToolButton:focus, QToolBar QToolButton:focus, QListWidget:focus, QGraphicsView:focus {
                border: 1px dashed #132b46; }
            QPushButton { background: white; border: 1px solid #cbdfe4; border-radius: 4px; padding: 4px 8px; }
            QPushButton:hover { background: #edf8f6; border-color: #8fbfb8; }
            QPushButton:disabled, QToolButton:disabled { color: #97a8b5; }
            QGroupBox { background: white; border: 0; margin-top: 23px; }
            QGroupBox::title { subcontrol-origin: margin; padding: 3px 5px; font-size: 14px; font-weight: 600; color: #147f80; }
            QGroupBox#grupoVariables::title { color: #122849; font-size: 16px; }
            QTableWidget, QListWidget { background: white; border: 0; gridline-color: #e4eff1;
                selection-background-color: #e3f3f0; selection-color: #126a68; }
            QListWidget#paletaElementos::item { padding-left: 7px; border: 0; }
            QListWidget#paletaElementos QScrollBar:vertical { width: 7px; }  /* la paleta mide justo dos columnas de fichas */
            QListWidget#paletaElementos::item:hover { background: #f0f8f7; }
            QHeaderView::section { background: #eaf6f5; border: 0; padding: 6px 4px; color: #197d81; }
            QScrollArea { border: 0; background: transparent; }
            QScrollBar:horizontal { height: 12px; background: #dcebeb; margin: 0; border-radius: 6px; }
            QScrollBar::handle:horizontal { background: #7fa7a8; min-width: 30px; border-radius: 5px; margin: 1px; }
            QScrollBar::handle:horizontal:hover { background: #5e8e90; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
            QScrollBar:vertical { width: 12px; background: #dcebeb; margin: 0; border-radius: 6px; }
            QScrollBar::handle:vertical { background: #7fa7a8; min-height: 30px; border-radius: 5px; margin: 1px; }
            QScrollBar::handle:vertical:hover { background: #5e8e90; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QSplitter::handle { background: #eef7f7; }
            QStatusBar { background: #eef7f7; color: #637b8c; font-size: 11px; }
        """)
        self.tb_sim = QToolBar("Simulación")
        self.tb_sim.setObjectName("barraSimulacion")
        self.tb_sim.setMovable(False)
        self.tb_sim.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tb_sim.addAction(self.a_ejecutar)
        self.tb_sim.addSeparator()
        self.tb_sim.addAction(self.a_reiniciar)
        self.luz_es = QToolButton()  # estado de la conexión externa (Modbus), a la vista mientras se simula
        self.luz_es.setObjectName("luzES")
        self.luz_es.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.luz_es.setCursor(Qt.CursorShape.PointingHandCursor)
        self.luz_es.setStyleSheet(
            "QToolButton#luzES { border: 1px solid #b8c6c4; border-radius: 11px; background: #f4f7f7; color: #20343b; padding: 3px 10px; }"
            "QToolButton#luzES:hover { background: #d7e1df; border-color: #8fa5a3; }"
            "QToolButton#luzES[abierta=\"true\"] { background: white; border: 1px solid #20343b; font-weight: 600; }")
        self.luz_es.setProperty("abierta", False)
        self.luz_es.clicked.connect(lambda: self.mostrar_es())
        self.fila_pestanas.layout().addWidget(self.luz_es)  # al final de la fila de pestañas, no junto a Reiniciar
        self._luz_es("desconectado", "")
        self.addToolBar(self.tb_sim)
        self.tb_conexion = QToolBar("Conexión")
        self.tb_conexion.setObjectName("barraConexion")
        self.tb_conexion.setMovable(False)
        self.tb_conexion.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        # Un solo botón conmuta entre el dibujo GRAFCET y la vista de E/S externas: pulsado (marcado) mientras se ve ésta,
        # con otro texto, tooltip e icono; _sincronizar_boton_es lo deja coherente con la página visible, sea cual sea la vía
        self.a_es = self._accion("E/S externas", self._alternar_es, marcable=True)
        self._iconos_es = (_icono_barra("conexion"), _icono_grafcet())
        from .planos import icono_planos
        self.a_planos=self._accion("Planos",self._alternar_planos,marcable=True)
        self.a_planos.setIcon(icono_planos());self.tb_conexion.addAction(self.a_planos)
        self.tb_conexion.addAction(self.a_es)
        self._sincronizar_boton_es()
        self.paginas_es.currentChanged.connect(self._sincronizar_boton_es)
        self.addToolBar(self.tb_conexion)
        self.tb_conexion.hide()
        self._fijar_ancho_boton_es()  # con la barra ya en la ventana: el botón lleva su hoja de estilo
        self._fijar_ancho_boton_play()
        self.tb_edit = QToolBar("Edición")
        self.tb_edit.setMovable(False)
        for a in (self.a_debajo,):
            self.tb_edit.addAction(a)
        boton = self.diagrama.b_dependencias
        boton.setIcon(_icono_barra("dependencias"))
        boton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        boton.setAccessibleName("Mostrar dependencias")
        boton.setStyleSheet("")  # hereda el estilo común de la barra
        self.addToolBar(self.tb_edit)
        self.tb_vista = QToolBar("Vista")
        self.tb_vista.setMovable(False)
        self.a_dependencias = self.tb_vista.addWidget(boton)
        self.a_dependencias.setVisible(True)
        self.a_dependencias.setEnabled(True)
        boton.show()
        self.addToolBar(self.tb_vista)
        self.tb_proyecto.hide()
        self.herramientas_grafcet=QWidget()
        fila=QHBoxLayout(self.herramientas_grafcet);fila.setContentsMargins(0,0,0,0)
        for barra in (self.tb_sim,self.tb_edit,self.tb_vista):
            self.removeToolBar(barra);fila.addWidget(barra);barra.show()
        fila.addStretch(1)
        self.centralWidget().layout().insertWidget(1,self.herramientas_grafcet)
        self.tb_edit.hide()
        self._acciones_edicion(False)

    def _paneles(self) -> None:
        """Controles de cabecera y pestañas en los bordes para plegar y recuperar los paneles (el izquierdo, el de la paleta y las
        propiedades, solo existe al editar), y el estado guardado."""
        self.flechas = {n: p.cerrar for n, p in self._plegables.items()}
        self.pestanas = {n: p.pestana for n, p in self._plegables.items()}
        for nombre, panel in self._plegables.items():
            panel.alternar.connect(lambda n=nombre: self._mostrar_panel(n, not self._accion_panel(n).isChecked()))
            panel.desplegar.connect(lambda tamano,n=nombre:self._abrir_desde_tiron(n,tamano))
        self.flechas["izquierdo"].hide()
        fijo = self.ajustes.value("paneles/inferior_fijo", False, type=bool)
        self.props.t_fijar.blockSignals(True)
        self.props.t_fijar.setChecked(fijo)
        self.props.t_fijar.blockSignals(False)
        for nombre in ("izquierdo", "derecho", "inferior"):
            accion = self._accion_panel(nombre)
            visible = self.ajustes.value(f"paneles/{nombre}", True, type=bool)
            if nombre == "inferior":  # sin fijar, arranca plegado aunque un ajuste antiguo lo dejara abierto
                visible = self._inferior_al_arrancar = visible and fijo
            accion.blockSignals(True)
            accion.setChecked(visible)
            accion.blockSignals(False)
            self._mostrar_panel(nombre, visible, guardar=False)

    def _panel(self, nombre: str) -> QWidget:
        return {"izquierdo": self.dock, "derecho": self.derecho, "inferior": self.inferior}[nombre]

    def _abrir_opciones(self, explicito: bool = True) -> None:
        """Despliega el panel inferior (las opciones de lo seleccionado) si estaba plegado, pero solo cuando el usuario lo
        pide (doble clic, Intro, «Editar…»). En otro caso (P-IMP-118) un panel plegado se queda plegado."""
        panel = self._plegables["inferior"]
        if not explicito and not panel.abierto:
            return
        self._mostrar_panel("inferior", True)
        agrandar_para_transicion(self)

    def _fijado(self) -> bool:
        return self.props.t_fijar.isChecked()

    def _fijar_cambiado(self, fijo: bool) -> None:
        """«Fijar»: se guarda (arranca abierto solo si está fijado) y fijado ya no se esconde nada."""
        self.ajustes.setValue("paneles/inferior_fijo", fijo)

    def _tras_gesto(self, antes: tuple, despues: tuple) -> None:
        """Pulsar o soltar el ratón en el dibujo (`antes` y `despues`: lo seleccionado y la acción señalada, `Edicion.clave_panel`).
        Con el panel de opciones abierto y sin fijar, un gesto que lo deja vacío o en otro elemento lo esconde al momento, sin
        estados intermedios; sobre el mismo elemento, no. Un panel que no mostraba nada se limita a actualizarse."""
        if (self.modo != "editar" or getattr(self, "solo_lectura", False) or not self._plegables["inferior"].abierto
                or self._fijado()):
            return
        mismo = despues == antes and bool(despues[0])
        sin_nada = not antes[0] and antes[1] is None and bool(despues[0])
        if not mismo and not sin_nada:
            self._ocultar_sin_fijar()

    def _ocultar_sin_fijar(self) -> None:
        """Esconde el panel de opciones sin que el dibujo salte: el punto de la escena de su esquina superior izquierda
        sigue en el mismo sitio de la pantalla."""
        d = self.diagrama
        punto = d.mapToScene(0, 0)
        self._mostrar_panel("inferior", False)

        def corregir() -> None:
            dx, dy = d.mapFromScene(punto).x(), d.mapFromScene(punto).y()
            if dx or dy:
                d.horizontalScrollBar().setValue(d.horizontalScrollBar().value() + dx)
                d.verticalScrollBar().setValue(d.verticalScrollBar().value() + dy)
        corregir()
        QTimer.singleShot(0, d, corregir)

    def _accion_panel(self, nombre: str) -> QAction:
        return {"izquierdo": self.a_izquierdo, "derecho": self.a_derecho, "inferior": self.a_inferior}[nombre]

    def _mostrar_panel(self, nombre: str, visible: bool, guardar: bool = True) -> None:
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        panel = self._plegables[nombre]
        anterior = panel.abierto
        if anterior and not visible:
            actual = panel.height() if nombre == "inferior" else panel.width()
            self._tamanos_paneles[nombre] = getattr(panel, "tamano_recordado", None) or actual
            panel.tamano_recordado = None
        panel.mostrar(visible)
        panel.setVisible(editar or nombre != "izquierdo")
        self.pestanas[nombre].setText({"izquierdo": "Elementos", "derecho": "Variables" if editar else "Simulación",
                                      "inferior": "Propiedades" if editar else "Traza"}[nombre])
        if visible != anterior:
            tamano = max(self._minimo_panel(nombre), self._tamanos_paneles[nombre]) if visible else panel.GROSOR_PESTANA
            if nombre == "derecho":
                total = sum(self.split.sizes());self.split.setSizes([max(100,total-tamano),tamano])
            elif nombre == "inferior":
                total = sum(self.vsplit.sizes());self.vsplit.setSizes([max(100,total-tamano),tamano])
            elif editar:
                total = sum(self.split_izquierdo.sizes());self.split_izquierdo.setSizes([tamano,max(100,total-tamano)])
        accion = self._accion_panel(nombre)
        if accion.isChecked() != visible:
            accion.blockSignals(True)
            accion.setChecked(visible)
            accion.blockSignals(False)
        # La flecha apunta hacia donde se pliega el panel y, plegado, hacia donde se despliega
        self.flechas[nombre].setText({"izquierdo": "◂" if visible else "▸", "derecho": "▸" if visible else "◂",
                                      "inferior": "▾" if visible else "▴"}[nombre])
        self.flechas[nombre].setToolTip(f"{'Plegar' if visible else 'Desplegar'} el panel {nombre}")
        if guardar:
            self.ajustes.setValue(f"paneles/{nombre}", visible)

    def _minimo_panel(self, nombre):
        if nombre != "inferior":
            return self.ancho_lateral
        if self.modo == "editar":
            minimo = max(76 if self.props.pagina == "vacio" else 160, self.props.minimumSizeHint().height())
            if self.props.pagina == "accion":
                # La frase se parte según el ancho de su columna: minimumSizeHint no cuenta esas líneas.
                minimo = max(minimo, self.props.layout().totalHeightForWidth(self.props.width()))
            return minimo
        return max(120, self.traza.minimumSizeHint().height()+30)

    def _abrir_desde_tiron(self, nombre, tamano):
        tamano = self.ancho_lateral if nombre == "izquierdo" else max(self._minimo_panel(nombre),tamano)
        self._tamanos_paneles[nombre] = tamano
        if nombre == "inferior":self._opciones_automaticas = False
        self._mostrar_panel(nombre, True)
        if nombre == "derecho":
            total=sum(self.split.sizes());self.split.setSizes([max(100,total-tamano),tamano])
        elif nombre == "inferior":
            total=sum(self.vsplit.sizes());self.vsplit.setSizes([max(100,total-tamano),tamano])

    def _plegar_desde_divisor(self, nombre):
        if nombre == "inferior":
            self._opciones_automaticas = False
        self._mostrar_panel(nombre, False)

    @staticmethod
    def _tabla(cols: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        t.setMinimumHeight(120)
        return t

    # -- fuentes: ejemplo o modelo guardado ------------------------------------------------------------
    def cargar_ejemplo(self, key: str) -> None:
        if not self._salir_de_edicion():
            self.acciones_ej[key].setChecked(False)
            return
        self.fuente = {"tipo": "ejemplo", "clave": key}
        self.acciones_ej[key].setChecked(True)
        self._cargar()

    def abrir_ruta(self, ruta: Path) -> bool:
        contenedor = None
        try:
            ruta=Path(ruta)
            if ruta.suffix.lower()!='.grafnet':
                raise ValueError('Abre un proyecto .grafnet con sello válido. No se admiten carpetas ni archivos JSON sueltos.')
            contenedor=self._leer_grafnet_gui(ruta)
            op=open_model(contenedor.raiz)
        except (DiagnosticError, OSError, ValueError) as exc:
            if contenedor is not None:contenedor.cerrar()
            QMessageBox.warning(self, TITULO, f"No se pudo abrir {ruta}:\n\n{exc}")
            return False
        if not op.executable:
            if contenedor is not None:contenedor.cerrar()
            QMessageBox.warning(self, TITULO, "El modelo no se puede simular:\n\n"
                                + "\n".join(amable(d.message, d.code) for d in op.diagnostics))
            return False
        if not self._salir_de_edicion():
            if contenedor is not None:contenedor.cerrar()
            return False
        quitadas = quitar_valores_iniciales(op.doc)  # P-IMP-117: ninguna variable declara un valor inicial fuera del grafcet
        layout = layout_from_presentation(op.presentations[0]) if op.presentations else {}
        avisos = [str(d) for d in op.diagnostics]
        ayuda = (f"Modelo abierto de {ruta}. "
                 + ("Posiciones de su presentación." if layout else "Sin presentación: colocado automáticamente.")
                 + (" Avisos: " + "; ".join(avisos) if avisos else ""))
        proyecto = contenedor.raiz
        self.fuente = {"tipo": "fichero", "ruta": ruta, "doc": op.doc, "layout": layout, "titulo": op.title,
                       "ayuda": ayuda, "raiz": proyecto, "presentacion": op.presentations[0] if op.presentations else None}
        self.fuente["contenedor"] = contenedor
        checked = self.grupo.checkedAction()
        if checked:
            self.grupo.setExclusive(False)
            checked.setChecked(False)
            self.grupo.setExclusive(True)
        self._cargar()
        if quitadas:
            if self.edicion is not None:
                self.edicion.ed.dirty = True  # guardar escribe el arreglo; abrir solo no firma ni guarda nada
            QMessageBox.information(self, TITULO, aviso_valores_iniciales(quitadas))
        return True

    def abrir(self) -> None:
        from .carpetas import asegurar_carpetas
        try:inicial=str(asegurar_carpetas()['grafcet'])
        except OSError as exc:QMessageBox.warning(self,"Abrir proyecto",str(exc));return
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", inicial, "Proyecto GRAFCET Connect (*.grafnet)")
        if ruta:
            self.abrir_ruta(Path(ruta))

    def _cargar(self) -> None:
        """Carga la fuente (ejemplo, modelo o lo que se edita) y deja el programa en Pausa: parado y editable, y sin estado
        (como tras Play y Pausa: ni etapas activas ni valores en las tablas; Play arranca la sesión). La conexión Modbus, si
        la hay, no se cierra: se conserva el TCP y las salidas pasan a 0 (Pausa)."""
        self._generacion_encuadre = getattr(self, "_generacion_encuadre", 0) + 1
        self.modbus.pausar()
        self._marcar_play(False)
        self._aviso_inestable_sesion = None
        self._avisos_ejecucion = []
        f = self.fuente
        try:
            if f["tipo"] == "ejemplo":
                title, help_text, build = EJEMPLOS[f["clave"]]
                self.v = Vista(f["clave"], title, help_text, build, self.options)
            elif f["tipo"] == "editor":  # lo que se está editando, tal como está: cada simulación es una ejecución nueva
                e = self.edicion
                self.v = Vista(e.ed.model["id"], e.titulo, "Simulación del grafcet que se está editando.",
                               lambda: (copy.deepcopy(e.ed.model), e.layout()), self.options, presentation=e.ed.presentation)
            else:
                self.v = Vista(f["ruta"].stem, f["titulo"], f["ayuda"], lambda: (f["doc"], f["layout"]), self.options,
                               presentation=f.get("presentacion"))
        except ERRORES as exc:
            QMessageBox.warning(self, TITULO, f"No se pudo preparar la simulación:\n\n{exc}")
            return
        if f["tipo"] != "editor":
            self._ayuda = self.v.model["help"]
            self._proyecto = ("ejemplo", f["clave"]) if f["tipo"] == "ejemplo" else ("fichero", str(f["ruta"]))
        self.setWindowTitle(f"{self.v.model['title']} — {TITULO}")
        self.diagrama.ajustar()
        self._entradas()
        if self.edicion is None or f["tipo"] != "editor":  # siempre se abre editable: Play simula una copia compilada
            self._establecer_edicion(self._edicion_desde_fuente())
        self.solo_lectura = f["tipo"]=="ejemplo" or (f["tipo"]=="editor" and getattr(self,"solo_lectura",False))
        self.modo = "editar"
        self._cargar_config_modbus()
        self._poner_modo()
        self._sin_estado()  # la Vista nace con la sesión en la situación inicial: en Pausa no se enseña nada de ella
        self.refrescar()
        if not self.modbus.activo:
            self.rt.stop()

    def reiniciar(self) -> None:
        """En Play vuelve a la situación inicial y sigue en Play; con E/S externas la conexión se conserva: solo se vincula
        una sesión nueva, que escribe sus salidas solo tras leer y aplicar las entradas de la planta. En Pausa ya está todo a
        0 y sin estado (Pausa es «todo a 0 hasta un nuevo Play»): no hay nada que reiniciar, solo se vuelve a pedir el cero
        a la planta si hay conexión."""
        self._mostrar_pagina(False)
        if not self.a_ejecutar.isChecked():
            self.modbus.pausar(diagnostico=True)
            self._sin_estado()
            self.refrescar()
            self.refrescar_edicion()
            return
        if not self._preparar_sesion():
            self.a_ejecutar.setChecked(False)  # no se ha podido: Pausa
            return
        self._iniciar_reloj()
        self.refrescar()

    def _sin_estado(self) -> None:
        """Pausa = todo a 0 hasta un nuevo Play: el GRAFCET no tiene ninguna etapa activa ni temporizador en curso, y las
        tablas de estado no enseñan lo de la sesión anterior. La sesión que había se sustituye por otra sin iniciar (estado
        «preparada» del motor: ni situación ni valores); Play siempre crea una nueva desde la situación inicial. No se
        toca el motor: solo se deja de apuntar a la sesión en marcha."""
        s = self.v.s if self.v else None
        if s is not None:
            self.v.s = Session(s.cm, s.scenario, s.ctl.budget, options=s.options)
            self.v.start_diags = []

    def _preparar_sesion(self) -> bool:
        """Compila lo que se edita y deja en self.v una sesión nueva, estable y en la situación inicial (Play siempre
        arranca de cero, y Reiniciar en Play también). Con Modbus vivo la vincula al TCP existente, sin reconectar: no se
        escribe nada hasta leer las entradas de la planta, aplicarlas a la sesión nueva y calcular (leer, aplicar, calcular,
        escribir). Si no puede, avisa y devuelve False sin tocar la conexión."""
        if self.edicion is None:
            self._establecer_edicion(self._edicion_desde_fuente() if self.v else Edicion.nuevo())
        if self._variables_sin_nombre():
            return False
        e = self.edicion
        if any(d["blocks"] for d in e.diagnosticos()):
            self._no_simulable()
            return False
        ayuda = self._ayuda if self._ayuda and not e.ed.undo_stack else "Simulación del grafcet."
        nueva = Vista(e.ed.model["id"], e.titulo, ayuda, lambda: (copy.deepcopy(e.ed.model), e.layout()), self.options,
                      presentation=e.ed.presentation)
        if nueva.s is None:  # compila con las lecturas por defecto, pero no con las activas (diálogo «Lecturas»)
            lineas = [f"• {e.sust(d.message)}" for d in nueva.compile_diags]  # (el texto del núcleo, con nombres y sin ID)
            QMessageBox.warning(self, TITULO, "El grafcet no compila con las lecturas de interpretación activas, no se puede "
                                "simular todavía:\n\n" + "\n".join(lineas[:8]) + ("\n…" if len(lineas) > 8 else ""))
            return False
        if not self.modbus.activo:
            contactos={vid:True for (proyecto,vid),nc in self._entradas_nc.items() if proyecto==self._proyecto and nc and vid in nueva.s.cm.variables}
            if contactos:nueva.act("fijar",{"cambios":contactos})
        if nueva.s.status != "pausada-estable":
            self._avisar_motor(nueva, al_arrancar=True)
            return False
        if self.modbus.activo:
            try:
                config = self.panel_es.obtener()
                config.validar(e.ed.model)  # lo editado puede haber dejado el mapa sin variable o de otro tipo
                self.modbus.vincular(nueva.s, config, e.ed.model)
            except ERRORES as exc:
                texto = f"No se puede ejecutar con la conexión y las asignaciones actuales: {exc}. Revise la asignación; la conexión se conserva."
                self.modbus.mensaje = texto
                self.panel_es.mostrar_estado(self.modbus.estado, texto)
                QMessageBox.warning(self, TITULO, texto)
                return False
        self.v = nueva
        self.fuente = {"tipo": "editor"}
        self._avisos_ejecucion = []
        self._entradas()
        return True

    # -- edición: modos, herramientas y diálogos ---------------------------------------------------
    def _foco_portapapeles(self) -> bool:
        foco = QApplication.focusWidget()
        while foco is not None and foco is not self:
            if isinstance(foco, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)) or foco is getattr(self, "variables", None):
                return True
            foco = foco.parentWidget()
        return False

    def _actualizar_portapapeles(self, *args: Any) -> None:
        e = self.edicion
        disponible = e is not None and not getattr(self,"solo_lectura",False) and self.modo == "editar" and not self.destino_traer and not self._foco_portapapeles() and (not hasattr(self,"paginas_es") or self.paginas_es.currentIndex()!=2)
        self.a_copiar.setEnabled(disponible and bool(e.sel))
        self.a_cortar.setEnabled(disponible and bool(e.sel))
        self.a_pegar.setEnabled(disponible and self._portapapeles is not None)
        if hasattr(self,"a_enviar_lamina"):self.a_enviar_lamina.setEnabled(disponible and bool(e.sel))

    def _portapapeles_accion(self, operacion: str, punto: Any = None) -> bool:
        e = self.edicion
        if e is None or self.modo != "editar" or self._foco_portapapeles() or self.destino_traer:
            return False
        if operacion == "pegar":
            if self._portapapeles is None:
                return False
            if punto is None:
                viewport = self.diagrama.viewport()
                local = viewport.mapFromGlobal(QCursor.pos())
                local = local if viewport.rect().contains(local) else viewport.rect().center()
                punto = self.diagrama.mapToScene(local)
            return e.pegar_fragmento(self._portapapeles, punto)
        if not e.sel:
            return False
        fragmento = e.copiar_fragmento()
        if not any(fragmento.entities.values()) and not any(fragmento.presentation.get(k) for k in ("barras", "draftActions", "notes")):
            return False
        if operacion == "cortar" and not e.borrar():
            return False
        self._portapapeles = fragmento
        e.informar("Selección cortada" if operacion == "cortar" else "Selección copiada")
        e.cambiado.emit()
        self._actualizar_portapapeles()
        return True

    def _menu_portapapeles(self, punto: Any, sobre_elemento: bool) -> list[tuple[str, Any]]:
        if sobre_elemento:
            return [("Cortar", lambda: self._portapapeles_accion("cortar")),
                    ("Copiar", lambda: self._portapapeles_accion("copiar")),
                    ("Enviar a plano…",self.enviar_seleccion_lamina)]
        return [("Pegar", (lambda: self._portapapeles_accion("pegar", punto)) if self._portapapeles is not None else None)]

    def _acciones_edicion(self, on: bool) -> None:
        for a in (*self.a_herr.values(), self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo, self.a_girar_izq, self.a_girar_der):
            a.setEnabled(on)
        self._actualizar_portapapeles()

    def _indicar_firma(self, e) -> None:
        """Indicación permanente en la barra de estado si el archivo abierto no tiene la firma de esta versión."""
        firma = getattr(getattr(e, "contenedor", None), "firma", "valida")
        texto, ayuda = TEXTOS_FIRMA.get(firma, ("", ""))
        self.l_firma.setText(texto)
        self.l_firma.setToolTip(ayuda)
        self.l_firma.setVisible(bool(texto))

    def _titulo_ventana(self) -> None:
        e = self.edicion
        self._indicar_firma(e)
        if hasattr(self,"panel_planos"):
            if self.paginas_es.currentIndex()==2 and self.panel_planos.origen is not e and not self.panel_planos.cargando:self.panel_planos.mostrar()
            else:self.panel_planos.actualizar_titulo()
        if e is not None:
            nombre = getattr(e,"archivo",None)
            nombre = nombre.name if nombre else e.titulo
            self.setWindowTitle(f"{nombre}{' *' if e.ed.dirty else ''}{' (ejemplo · solo lectura)' if getattr(self,'solo_lectura',False) else ' (editando)' if self.modo == 'editar' else ''} — {TITULO}")

    def _salir_de_edicion(self) -> bool:
        """Antes de cargar otro modelo: si hay cambios sin guardar, pregunta. Quien carga sustituye la edición en curso."""
        if hasattr(self,"panel_planos"):self.panel_planos.aplicar()
        e = self.edicion
        if e is not None and e.ed.dirty:
            r = QMessageBox.question(self, TITULO, f"«{e.titulo}» tiene cambios sin guardar. ¿Guardarlos?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                     | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel or (r == QMessageBox.StandardButton.Save and not self.guardar()):
                return False
        return True

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        if self._salir_de_edicion():
            self._transicion_ui = True
            self.a_ejecutar.setChecked(False)
            self.rt.stop()
            self.modbus.cerrar()
            event.accept()
        else:
            event.ignore()

    def nuevo(self) -> None:
        if not self._salir_de_edicion():
            return
        self._empezar_edicion(Edicion.nuevo())
        if self.modbus.activo:  # la conexión sigue; el modelo nuevo trae su propio mapa (vacío)
            self._cargar_config_modbus(self.edicion.ed.model)
        elif self.paginas_es.currentIndex() == 1:  # el panel de E/S está a la vista: que muestre el proyecto nuevo, no el anterior
            self._sincronizar_es(mostrando=True)

    def _edicion_desde_fuente(self) -> Edicion:
        """Copia editable de lo que se está simulando (un ejemplo o un modelo abierto)."""
        f = self.fuente
        if f["tipo"] == "editor":
            return Edicion.desde(self.v.doc, auto_layout(self.v.doc), self.v.model["title"])
        if f["tipo"] == "ejemplo":
            title, _, build = EJEMPLOS[f["clave"]]
            m, layout = build()
            return Edicion.desde(m.doc, layout, title)
        e=Edicion.desde(f["doc"], f["layout"], f["titulo"], f.get("raiz"), f.get("presentacion"))
        if f.get("contenedor") is not None:self._adoptar_archivo(e,f["contenedor"])
        return e

    def _empezar_edicion(self, e: Edicion) -> None:
        self._ayuda = ""
        self._n_nuevos += 1
        self._proyecto = ("nuevo", self._n_nuevos)
        self._establecer_edicion(e)
        self.cambiar_modo("editar")

    def _establecer_edicion(self, e: Edicion) -> None:
        self.solo_lectura = False
        self._variables_es_vistas = {v["id"] for v in e.ed.model["variables"]}
        self._auto_es_pendientes = set()
        self.destino_traer=None;self.aviso_traer.hide()
        self.navegacion.buscar.clear(); self.navegacion.parcial.setCurrentIndex(0); self.navegacion.actual = None
        self.diagrama.seleccion_navegacion.clear()
        self.edicion = e
        e.diagrama = self.diagrama
        e.cambiado.connect(self.refrescar_edicion)
        e.redibujar.connect(self._redibujar_edicion)
        # (lo que pide el usuario, con doble clic, Intro o «Editar…», despliega el panel; lo que piden otras operaciones, no: P-IMP-118)
        e.pedir_condicion = lambda tid: self.editar_condicion(tid, e.pedido_explicito)
        e.pedir_etiqueta = lambda ident: self.editar_etiqueta(ident, e.pedido_explicito)
        e.pedir_accion = lambda sid, aid: self.editar_accion(sid, aid, e.pedido_explicito)
        e.tras_gesto = self._tras_gesto
        e.confirmar_borrado = self._confirmar_borrado
        e.pedir_texto = lambda titulo, etiqueta, actual: self._pedir_texto(titulo, etiqueta, actual)
        e.pedir_forzado = lambda datos: self._pedir_forzado(datos)
        if e.enlaces_quitados:
            cantidad, e.enlaces_quitados = e.enlaces_quitados, 0
            aviso = ("Se quitó un enlace en borrador que apuntaba a elementos que ya no existen" if cantidad == 1 else
                     f"Se quitaron {cantidad} enlaces en borrador que apuntaban a elementos que ya no existen")
            e.informar(aviso)
            QMessageBox.information(self, TITULO, aviso)
        if e.barras_limpiadas:
            cantidad, e.barras_limpiadas = e.barras_limpiadas, 0
            aviso = ("Se quitó de una barra la unión con un elemento que ya no existe" if cantidad == 1 else
                     f"Se quitaron de las barras {cantidad} uniones con elementos que ya no existen")
            e.informar(aviso)
            QMessageBox.information(self, TITULO, aviso)

    def cambiar_modo(self, modo: str) -> bool:
        if self.destino_traer:return False
        """Los modos solo se alternan con Play (simular) y Pausa (editar); esto es el mismo control por dentro. Devuelve si
        el programa ha quedado en el modo pedido (Play puede negarse: no compila, inestable…)."""
        on = modo == "simular"
        if self.a_ejecutar.isChecked() != on:
            self.a_ejecutar.setChecked(on)
        else:
            self._ejecutar(on)
        return self.modo == modo

    def _poner_modo(self) -> None:
        """Alterna las herramientas sin perder tamaños de edición ni el encuadre manual."""
        self._dibujo_simulado = None
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        lateral = self._plegables["derecho"]
        ancho = (lateral.width() if lateral.abierto else self._tamanos_paneles["derecho"]) if getattr(self, "_anchos_puestos", False) else self.ancho_lateral
        guardado = getattr(self, "_paneles_edicion", None)
        if not editar and guardado is None:
            self._paneles_edicion = {"izquierdo": self.a_izquierdo.isChecked(),
                                    "inferior": self.a_inferior.isChecked() and self._fijado(),  # sin fijar, vuelve plegado
                                    "tamanos": self.vsplit.sizes() if self.isVisible() else None}
        self.tb_edit.setVisible(editar)
        self.variables.setEnabled(editar)
        self.props.setEnabled(editar); self.paleta.setEnabled(editar)
        for accion in (self.a_guardar,self.a_guardar_como,self.a_enviar_lamina,self.a_exportar): accion.setEnabled(not getattr(self,"solo_lectura",False))
        # (con la pestaña de E/S oculta y marcada, Qt elegiría otra al habilitar PLANOS: se vuelve a marcar la de la página que se ve)
        self.pestanas_vistas.blockSignals(True);self.pestanas_vistas.setTabEnabled(1,not getattr(self,"solo_lectura",False))
        self.pestanas_vistas.setCurrentIndex({0:0,1:2,2:1}[self.paginas_es.currentIndex()]);self.pestanas_vistas.blockSignals(False)
        self._acciones_edicion(editar)
        self.derecho.setCurrentIndex(1 if editar else 0)
        self.inferior.setCurrentIndex(1 if editar else 0)
        self._anchos_laterales(ancho)
        if not editar:
            self.diagrama.actualizar_diagnosticos(False)
            self._mostrar_panel("izquierdo", False, guardar=False)
            self._mostrar_panel("inferior", False, guardar=False)
        elif guardado is not None:
            self._restauracion_paneles = guardado
            self._mostrar_panel("izquierdo", guardado["izquierdo"], guardar=False)
            self._mostrar_panel("inferior", guardado["inferior"], guardar=False)
            self._paneles_edicion = None
            def restaurar():
                if getattr(self, "_restauracion_paneles", None) is guardado:
                    if self.modo == "editar" and guardado["tamanos"] is not None:
                        self.vsplit.setSizes(guardado["tamanos"])
                    def terminar():
                        if getattr(self, "_restauracion_paneles", None) is guardado:
                            self._restauracion_paneles = None
                    QTimer.singleShot(0, self, terminar)
            if guardado["tamanos"] is not None:
                self.vsplit.setSizes(guardado["tamanos"])
            QTimer.singleShot(0, self, restaurar)
        else:
            self._mostrar_panel("izquierdo", self.a_izquierdo.isChecked(), guardar=False)
            self._alto_inferior(True)
        self.flechas["izquierdo"].setVisible(editar)
        for n in ("derecho", "inferior"):
            self._mostrar_panel(n, self._accion_panel(n).isChecked(), guardar=False)
        self.diagrama.modo_edicion(editar, self.edicion if editar else None,
                                   conservar=getattr(self, "_encuadre_modo", None) is not None)
        if editar:
            self.refrescar_edicion()
        elif self.v is not None:
            self._titulo_ventana()
            if getattr(self,"solo_lectura",False): self.refrescar_edicion()

    def _anchos_laterales(self, ancho: int | None = None) -> None:
        panel = self._plegables["derecho"]
        ancho = max(self.ancho_lateral, panel.width() if ancho is None else ancho) if panel.abierto else panel.GROSOR_PESTANA
        self.derecho.setMinimumWidth(self.ancho_lateral)
        self.derecho.setMaximumWidth(16777215)
        self.split.handle(1).setEnabled(True)
        total = self.split.width() - self.split.handleWidth()
        self.split.setSizes([max(total - ancho, 100), ancho])

    def _dimensionar_opciones(self) -> None:
        """Reparto visual inicial: propiedades compactas, sin sobreescribir el divisor movido a mano."""
        if getattr(self,"_seleccionando_hoja",False):return
        self.props.layout().activate();self.props.updateGeometry()
        self._plegables["inferior"].mostrar(self._plegables["inferior"].abierto)
        if (not self._opciones_automaticas or self.modo != "editar" or self.inferior.isHidden()
                or getattr(self, "_restauracion_paneles", None) is not None):
            return
        self.props.layout().activate()
        alto = self._minimo_panel("inferior")
        total = sum(self.vsplit.sizes())
        self.vsplit.setSizes([max(total - alto, 120), alto])
        agrandar_para_transicion(self)

    def _alto_inferior(self, editar: bool) -> None:
        """Al cambiar de modo, el panel inferior recupera la altura que tenía en ese modo (la inicial, o la que dejó el
        divisor): el dibujo y el panel se reparten el alto. Al editar, mientras el divisor no se haya movido, el panel cede lo
        que haga falta (sin bajar de su mínimo) para que la paleta se vea entera; en una ventana más baja, la paleta se
        encoge y se desplaza."""
        if self.isVisible() and self.inferior.isVisible():
            self._alturas["simular" if editar else "editar"] = self.vsplit.sizes()[1]
        if self.inferior.isHidden():  # plegado, solo su pestaña y el resto para el dibujo: al desplegarlo vuelve a su altura
            grosor = self._plegables["inferior"].GROSOR_PESTANA
            self.vsplit.setSizes([max(sum(self.vsplit.sizes()) - grosor, 100), grosor])
            return
        alto = self._alturas["editar" if editar else "simular"]
        total = max(sum(self.vsplit.sizes()), alto + 200)
        if editar and alto == ALTO_INFERIOR["editar"] and not self.dock.isHidden():  # (a 1366×768: el inferior pasa de 380 a 328)
            alto = max(min(alto, total - self.paleta.sizeHint().height()), self.inferior.minimumSizeHint().height())
        self.vsplit.setSizes([total - alto, alto])
        if editar and self._opciones_automaticas:
            QTimer.singleShot(0, self, self._dimensionar_opciones)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.isVisible():
            self.recentrado.solicitar()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False) and not getattr(self, "_anchos_puestos", False):
            self._anchos_puestos = True  # con la ventana ya dimensionada, los dos paneles laterales con el mismo ancho
            self._anchos_laterales(self.ancho_lateral)
            self._alto_inferior(True)

    def _no_simulable(self) -> None:
        lineas = self.edicion.resumen(self.edicion.diagnosticos())
        QMessageBox.warning(self, TITULO, "El grafcet no compila, no se puede simular todavía:\n\n"
                            + "\n".join(f"• {x}" for x in lineas[:8]) + ("\n…" if len(lineas) > 8 else ""))
        # cada elemento con un error parpadea en naranja (después del aviso, que lo tapa) y se lleva a la vista
        self.edicion.parpadear(sorted(self.edicion.marcados_de(self.edicion.diagnosticos())))

    def _variables_sin_nombre(self) -> bool:
        """Si hay filas de variable sin nombre (solo de la interfaz): el aviso, el parpadeo de la fila y True; no se
        puede simular ni guardar con ellas."""
        if self.edicion is None or not self.variables.sin_nombre():
            return False
        self.edicion.mensaje = self.variables.avisar_sin_nombre()
        self.edicion.cambiado.emit()
        return True

    def herramienta(self, h: str) -> None:
        e = self.edicion
        if e is not None and e.herramienta != h:
            e.herramienta, e.enlace, e.mensaje = h, None, ""
            self.refrescar_edicion()
        elif e is not None:
            self.refrescar_edicion()

    def _ayuda_ficha(self, texto: str) -> None:
        """Un clic en una ficha de la paleta: su ayuda, como aviso informativo (no coloca nada)."""
        if self.edicion is not None:
            self.edicion.informar(texto)
            self.edicion.cambiado.emit()

    def refrescar_edicion(self) -> None:
        e = self.edicion
        if e is None or self.modo != "editar":
            return
        diags = e.diagnosticos()
        marcados = e.marcados_de(diags)
        self.diagrama.mostrar(e.M, {}, e.seleccion_dibujo(), marcados, e.parpadeo.activos())
        self.estado.setText("ejemplo · solo lectura" if getattr(self,"solo_lectura",False) else "editando")
        self.estado.setStyleSheet(f"color: {COL['accent']}; border: 1px solid {COL['accent']}; border-radius: 9px; "
                                  "padding: 1px 9px")
        self.titulo.setText(f"{e.titulo}{' *' if e.ed.dirty else ''}")
        self.ayuda.setToolTip(self._ayuda if getattr(self,"solo_lectura",False) else AYUDA_EDICION[e.herramienta])
        self.ayuda.setText(self._ayuda if getattr(self,"solo_lectura",False) else e.mensaje or "Arrastre fichas desde la paleta; doble clic en un elemento para ver sus propiedades.")
        error = bool(e.mensaje) and not e.mensaje_info  # un aviso informativo no va en rojo
        self.ayuda.setStyleSheet(f"color: {COL['err'] if error else COL['muted']}; font-weight: {600 if error else 400}")
        if e.mensaje:
            self.statusBar().showMessage(e.mensaje, 9000)
        self.l_herr.setText(f"<b>{NOMBRE_HERRAMIENTA[e.herramienta]}</b>: {html.escape(AYUDA_EDICION[e.herramienta])}")
        sel = [e.nombre(i) for i in e.sel]
        self.l_sel.setText(("Selección: " + ", ".join(sel)) if sel else "Nada seleccionado.")
        self.l_reloj.setText(f"{len(e.M['steps'])} etapas · {len(e.M['transitions'])} transiciones")
        self.a_herr[e.herramienta].setChecked(True)
        self.props.mostrar(e)
        pagina = (self.props.pagina, self.props.minimumSizeHint().height())
        if pagina != getattr(self, "_pagina_opciones", None):
            self._pagina_opciones = pagina
            QTimer.singleShot(0, self, self._dimensionar_opciones)
        seleccion = (self.props.pagina, tuple(e.sel))
        if seleccion != self._seleccion_alto:
            self._seleccion_alto = seleccion
            QTimer.singleShot(0, self, lambda: agrandar_para_transicion(self))
        self.variables.mostrar(e)
        planos=hasattr(self,"paginas_es") and self.paginas_es.currentIndex()==2
        self.a_deshacer.setEnabled(bool(e.ed.undo_stack))
        self.a_rehacer.setEnabled(bool(e.ed.redo_stack))
        self.a_borrar.setEnabled(bool(e.sel) and not planos and not getattr(self,"solo_lectura",False))
        self._actualizar_portapapeles()
        self.a_debajo.setEnabled(len(e.sel) == 1 and not getattr(self,"solo_lectura",False))
        bloq = [d for d in diags if d["blocks"]]
        self.l_resumen.setText("El grafcet se puede simular." if not bloq else
                               f"No se puede simular: {len(bloq)} error{'es' if len(bloq) != 1 else ''}")
        self.l_resumen.setStyleSheet(f"color: {COL['ok'] if not bloq else COL['err']}")
        self.lista_diag.clear()
        for d in diags:
            nombre = f"{e.nombre(d['target'])}: " if d["target"] else ""
            if d["code"] == "D-TIPO-EVENTO" and d["message"].startswith("Acción por evento"):
                nombre = ""
            if d.get("completo"):
                nombre = ""  # el aviso ya nombra el enlace o la barra: no se repite delante
            mensaje = d["message"] if nombre else d["message"][:1].upper() + d["message"][1:]
            principal, completo = partir(f"{nombre}{mensaje}")
            item = QListWidgetItem(principal)
            item.setData(Qt.ItemDataRole.UserRole, d["target"])
            # El código no va en el texto (P-IMP-89), pero sigue a la vista en la ayuda emergente (REQ-EDT-09).
            referencia = f"Referencia: {d['code']}"
            ayuda = [x for x in (completo, d["correction"], referencia) if x]
            item.setToolTip("\n".join(ayuda))
            item.setForeground(QColor(COL["text"]))  # el rojo queda para lo que impide simular (el resumen)
            self.lista_diag.addItem(item)
        for texto, detalle in self._avisos_ejecucion:  # por qué paró el motor la última vez que se simuló
            item = QListWidgetItem(texto)
            item.setToolTip(detalle)
            item.setForeground(QColor(COL["text"]))
            self.lista_diag.addItem(item)
        hay_detalle = self.lista_diag.count() > 0
        self.diagrama.actualizar_diagnosticos(hay_detalle)
        self._titulo_ventana()
        if self.destino_traer:self._sincronizar_boton_es()
        if hasattr(self, "panel_es"):  # las variables pueden haber cambiado: el panel de E/S las sigue (o avisa, si hay conexión)
            self._sincronizar_es()
            self._autoasignar_nuevas_es()

    def _redibujar_edicion(self) -> None:
        e = self.edicion
        if e is not None and self.modo == "editar":
            # un arrastre no valida de nuevo; el parpadeo sí repinta lo marcado por los diagnósticos
            self.diagrama.mostrar(e.M, {}, e.seleccion_dibujo(), e.marcados() if e.parpadeo.ids else set(),
                                  e.parpadeo.activos())

    def _ir_a_diagnostico(self, item: QListWidgetItem) -> None:
        """Un clic en un diagnóstico selecciona el elemento y lo centra (REQ-EDT-09)."""
        e, target = self.edicion, item.data(Qt.ItemDataRole.UserRole)
        if e is not None and target:
            e.seleccionar([target])
            c = e.centro(target)
            if c is not None:
                self.diagrama.centrar_en(c)
            e.parpadear([target], centrar=False)  # ya está centrado

    def editar_condicion(self, tid: str, explicito: bool = True) -> None:
        """Doble clic en una transición: la selecciona y despliega el panel inferior con su receptividad (solo si lo pide el
        usuario: con `explicito` falso, un panel plegado se queda plegado)."""
        self.edicion.seleccionar([tid])
        self._abrir_opciones(explicito)

    def editar_accion(self, sid: str | None, aid: str | None = None, explicito: bool = True) -> None:
        """Doble clic en una acción, «Editar…» o una acción recién unida a una etapa: la selecciona y despliega el panel inferior
        con sus opciones (tipo, variable, valor, condición o evento: todo se aplica al momento). Sin `aid`, añade una acción
        nueva a la etapa."""
        e = self.edicion
        if aid is None:
            if sid:
                e.anadir_accion(sid)
            return
        e.accion, e.ver_accion = aid, True
        e.sel = [sid] if sid else (e.sel if aid in e.sel else [aid])
        e.cambiado.emit()
        self._abrir_opciones(explicito)

    def editar_etiqueta(self, ident: str, explicito: bool = True) -> None:
        """Doble clic en una etapa: despliega las opciones y lleva el cursor a su etiqueta."""
        self.edicion.seleccionar([ident])
        self._abrir_opciones(explicito)
        if self._plegables["inferior"].abierto:
            self.props.s_etiqueta.setFocus()
            self.props.s_etiqueta.selectAll()

    def leyenda(self) -> None:
        """«Ayuda > Leyenda del dibujo»: una ventana propia (no modal) con lo que significa cada trazo y color."""
        if self._leyenda is None:
            self._leyenda = Leyenda(self)
        self._leyenda.show()
        self._leyenda.raise_()
        self._leyenda.activateWindow()

    def _pedir_texto(self, titulo: str, etiqueta: str, actual: str) -> str | None:
        """Un nombre que pide la edición («Añadir recinto…», «Renombrar…» de una macroetapa): el texto escrito, o None si se
        cancela. Es un método propio para poder sustituirlo en las pruebas, sin bloquear con el diálogo."""
        texto, ok = QInputDialog.getText(self, titulo, etiqueta, text=actual)
        return texto if ok else None

    def _pedir_forzado(self, datos: dict[str, Any]) -> dict[str, Any] | None:
        """La orden de forzado que pide la edición («Forzar un parcial…», «Editar orden de forzado…»): lo elegido en
        `DialogoForzado`, o None si se cancela. Método propio para poder sustituirlo en las pruebas, sin bloquear."""
        d = DialogoForzado(self, datos)
        return d.resultado() if d.exec() == QDialog.DialogCode.Accepted else None

    def _confirmar_borrado(self, plan: dict[str, list[str]]) -> bool:
        e = self.edicion
        n = e.nombres
        elegidos = list(dict.fromkeys(e.nombre(i) for i in e.sel))  # con nombres, sin repetir (una macroetapa y su expansión)
        extra = [t for t in dict.fromkeys(e.nombre(i) for i in plan["elements"] if i not in e.sel) if t not in elegidos]
        texto = f"Se borrará: {', '.join(elegidos)}."
        if extra:
            texto += f"\n\nTambién se lleva consigo: {', '.join(extra)}."
        if plan["affectedTransitions"]:
            texto += f"\n\nQuedan sin enlace en este extremo: {', '.join(n.get(i, i) for i in plan['affectedTransitions'])}."
        avisos = e.avisos_borrado(plan)  # recintos y órdenes que pierden etapas de su enlace de activación o de su conjunto
        if avisos:
            texto += "\n\nTambién cambia la jerarquía:\n" + "\n".join(f"• {a[0].upper()}{a[1:]}." for a in avisos)
        return QMessageBox.question(self, TITULO, texto + "\n\nSe puede deshacer con Ctrl+Z. ¿Continuar?") \
            == QMessageBox.StandardButton.Yes

    # -- acciones de simulación -------------------------------------------------------------------
    def _act(self, op: str, **body: Any) -> None:
        if self.modbus.activo:
            self.aviso.setText("Con E/S externas use Play/Stop; desconecte para depurar manualmente")
            return
        if self.v is None:
            return
        try:
            self.v.act(op, body)
            self.aviso.setText("")
        except ERRORES as exc:
            self.aviso.setText(f"No disponible: {exc}")
        self.refrescar()

    def _entradas(self) -> None:
        while self.rejilla.count():
            w = self.rejilla.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.botones, self.campos = {}, {}
        numeric = self.v.model.get("numericInputs", {})
        fila = 0
        for var in self.v.model["inputs"]:
            if var in numeric:
                etiqueta = QLabel(f"<b>{html.escape(self.nombre(var))}</b> =")
                etiqueta.setWordWrap(True)
                self.rejilla.addWidget(etiqueta, fila, 0, 1, 4)
                fila += 1
                campo = QLineEdit()
                campo.setPlaceholderText("valor" + (" entero" if numeric[var] == "int" else ""))
                campo.returnPressed.connect(lambda v=var: self._valor(v))
                self.rejilla.addWidget(campo, fila, 0, 1, 3)
                b = QPushButton("Aplicar")
                b.clicked.connect(lambda _=False, v=var: self._valor(v))
                self.rejilla.addWidget(b, fila, 3)
                self.campos[var] = campo
                self.botones[var] = b
                fila += 1
                continue
            b = _BotonEntrada()
            b.interruptor = self._tipos_entrada.get((self._proyecto, var), False)
            b.nc = self._entradas_nc.get((self._proyecto,var),False)
            self._ayuda_entrada(b)
            b.pressed.connect(lambda v=var, b=b: self._entrada_presionada(v, b))
            b.released.connect(lambda v=var, b=b: self._entrada_soltada(v, b))
            b.clicked.connect(lambda _=False, v=var, b=b: b.interruptor and self._act("entrada", var=v))
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda p, v=var, b=b: self._menu_entrada(v, b, p))
            self.rejilla.addWidget(b, fila, 0, 1, 4)
            self.botones[var] = b
            fila += 1
        if not self.v.model["inputs"]:
            self.rejilla.addWidget(QLabel("Sin entradas"), 0, 0)

    @staticmethod
    def _ayuda_entrada(b: _BotonEntrada) -> None:
        b.setToolTip(("NC: reposo 1, accionado 0 · " if b.nc else "NA: reposo 0, accionado 1 · ") + ("Interruptor: clic para conmutar · Botón derecho: cambiar tipo" if b.interruptor else
                     "Pulsador momentáneo: presionar invierte el reposo, soltar lo restaura · Ctrl+clic: enclavar mientras se mantiene Ctrl (otro clic libera) · Botón derecho: cambiar tipo"))

    def _cambiar_tipo_entrada(self, var: str, interruptor: bool) -> None:
        self._tipos_entrada[self._proyecto, var] = interruptor
        b = self.botones[var]
        b.interruptor, b.enclavado, b.liberar = interruptor, False, False
        self._ayuda_entrada(b)
        b.indicar(b.isChecked())

    def _menu_entrada(self, var: str, b: _BotonEntrada, punto: Any) -> None:
        if self.modbus.activo:
            return
        menu = QMenu(b)
        for tipo, texto in ((True, "Convertir en interruptor"), (False, "Convertir en pulsador")):
            a = menu.addAction(texto, lambda _=False, tipo=tipo: self._cambiar_tipo_entrada(var, tipo))
            a.setEnabled(tipo != b.interruptor)
        menu.addSeparator()
        for nc,texto in ((False,"Normalmente abierto (NA)"),(True,"Normalmente cerrado (NC)")):
            a=menu.addAction(texto,lambda _=False,nc=nc:self._cambiar_contacto(var,nc))
            a.setCheckable(True);a.setChecked(b.nc==nc)
        menu.exec(b.mapToGlobal(punto))

    def _cambiar_contacto(self,var,nc):
        self._entradas_nc[self._proyecto,var]=nc
        b=self.botones[var];b.nc=nc;b.enclavado=b.liberar=False
        self._ayuda_entrada(b);self._fijar_entrada(var,nc)

    def _fijar_entrada(self, var: str, valor: bool) -> None:
        if self.modo == "simular" and not self.modbus.activo and self.v is not None:
            if self.v.state().get("values", {}).get(var) is not valor:
                self._act("entrada", var=var)

    def _entrada_presionada(self, var: str, b: _BotonEntrada) -> None:
        if self.modbus.activo:
            self._act("entrada", var=var)
            return
        if b.interruptor:
            return  # como antes, el interruptor conmuta con clicked, al completar el clic
        elif b.enclavado:
            b.enclavado, b.liberar = False, False
            self._fijar_entrada(var, b.nc)
        else:
            b.enclavado, b.liberar = b.control, not b.control
            self._fijar_entrada(var, not b.nc)

    def _soltar_enclavados(self) -> None:
        for var, b in list(self.botones.items()):
            if isinstance(b, _BotonEntrada) and b.enclavado and not b.interruptor:
                b.enclavado, b.liberar = False, False
                self._fijar_entrada(var, b.nc)

    def _entrada_soltada(self, var: str, b: _BotonEntrada) -> None:
        if b.liberar:
            b.liberar = False
            self._fijar_entrada(var, b.nc)
        b.control = False
        self.refrescar()

    def nombre(self, ident: str) -> str:
        """Nombre visible de una variable, etapa, parcial o transición (los ID internos no se muestran)."""
        return self.v.model.get("names", {}).get(ident, ident) if self.v else ident

    def _valor(self, var: str) -> None:
        self._act("valor", var=var, texto=self.campos[var].text())

    def _opciones(self, options: dict[str, str]) -> None:
        self.options = normalize_options(options)  # cambia el perfil efectivo: ejecución nueva
        play = self.a_ejecutar.isChecked()
        if self.edicion is not None:
            self.fuente = {"tipo": "editor"}
        self._cargar()
        if play:
            self.a_ejecutar.setChecked(True)

    def lecturas(self) -> None:
        d = Lecturas(self, self.options)
        if d.exec() == QDialog.DialogCode.Accepted and d.options() != self.options:
            self._opciones(d.options())

    def _marcar_play(self, on: bool) -> None:
        """Pone el aspecto del control de ejecución (marca, texto e icono) sin provocar la transición."""
        self.a_ejecutar.blockSignals(True)
        self.a_ejecutar.setChecked(on)
        self.a_ejecutar.blockSignals(False)
        self.a_ejecutar.setText("Stop" if on else "Play")
        self.a_ejecutar.setIcon(_icono_barra("stop" if on else "play"))

    def _ejecutar(self, on: bool) -> None:
        """Play (on) o Pausa: el único control de ejecución. Play compila lo editado y arranca siempre una sesión nueva desde
        la situación inicial; Pausa detiene la evolución, vuelve a editar y deja todo a 0 hasta el siguiente Play: sin etapas
        activas ni temporizadores y, con E/S externas, todas las salidas asignadas a 0. La conexión Modbus no se cierra:
        Pausa conserva TCP y sigue observando las entradas, y Play vincula la sesión nueva al TCP existente."""
        if self._transicion_ui:
            return
        self._encuadre_modo = self.diagrama.guardar_encuadre()
        self._generacion_encuadre = getattr(self, "_generacion_encuadre", 0) + 1
        generacion = self._generacion_encuadre
        self._transicion_ui = True
        try:
            venia_de_play = self.modo == "simular"
            if on and not self._preparar_sesion():
                on = False  # no arranca (no compila, inestable, mapa de E/S inválido…): sigue en Pausa
            self.modo = "simular" if on else "editar"
            self._marcar_play(on)
            if not getattr(self, "_conservar_vista_al_parar", False):
                self._mostrar_pagina(False)
            if not on:
                self.modbus.pausar()
                if self.edicion is None:
                    self._establecer_edicion(self._edicion_desde_fuente() if self.v else Edicion.nuevo())
            self._poner_modo()
            if not on and venia_de_play:
                self._sin_estado()
                self.refrescar()  # las tablas dejan de enseñar la sesión anterior y las entradas se deshabilitan
            if on:
                self.refrescar()
            if self.modbus.activo:
                self.modbus.solicitar_ejecucion(on)
                self._proxima_lectura.start(1)  # Play/Stop no esperan al sondeo configurado.
            if on or self.modbus.activo:  # con la conexión viva el temporizador sigue en Pausa: observa las entradas
                self._iniciar_reloj()
                self.rt.start()
            else:
                self.rt.stop()
        finally:
            estado = self._encuadre_modo
            self._encuadre_modo = None
            self.diagrama.restaurar_encuadre(estado)
            def restaurar():
                if self._generacion_encuadre == generacion:
                    self.diagrama.restaurar_encuadre(estado)
            QTimer.singleShot(0, self.diagrama, restaurar)
            self._transicion_ui = False

    def _vigilar_motor(self) -> bool:
        """En Play, si el motor deja de estar en situación estable (inestable o detenido por un diagnóstico): se para, pasa a
        Pausa/edición y se cuenta por qué. Devuelve si ha parado."""
        s = self.v.s if self.v else None
        if s is None or s.status == "pausada-estable":
            return False
        self._avisar_motor(self.v)
        self.a_ejecutar.setChecked(False)
        return True

    def _avisar_motor(self, vista: Vista, al_arrancar: bool = False) -> None:
        """El motor no ha quedado en situación estable. Inestable (D-LIM-EVOL: no la alcanza dentro de su límite de
        evoluciones): aviso modal, una sola vez por episodio. Otro diagnóstico: mensaje en la barra de estado (o aviso, si
        era al arrancar). Con Modbus vivo, lo que ya se estuviera controlando pasa a estado seguro (cero) sin cerrar la
        conexión. Los detalles se quedan entre los diagnósticos del panel de edición."""
        d = vista._diag(vista.s.diagnostics[-1]) if vista.s.diagnostics else None  # con nombres, no ID internos
        inestable = d is not None and d["code"] == "D-LIM-EVOL"
        m = self.modbus
        if m.activo and (inestable or not al_arrancar) and (m.adaptador.sesion is not None or m.escritos):
            m.pausar(diagnostico=True)
        evoluciones = [r for r in vista.s.trace.records if r["kind"] == "evolucion"]
        motivos = motivo_parada(d["code"], d["message"], evoluciones, vista.names) if d else []
        self._avisos_ejecucion = motivos
        if inestable:
            if self._aviso_inestable_sesion is not vista.s:
                self._aviso_inestable_sesion = vista.s
                self._avisar_inestable(motivos[-1][0] if motivos else "")
        elif al_arrancar:
            QMessageBox.warning(self, TITULO, "No se puede ejecutar: revise los diagnósticos del grafcet."
                                + (f"\n\n{amable(d['message'], d['code'])}" if d else ""))
        else:
            texto = motivos[0][0] if motivos else "Simulación detenida."
            self.statusBar().showMessage(f"{texto} Vea el motivo en la lista de diagnósticos.", 12000)

    def _avisar_inestable(self, causa: str = "") -> None:
        """Ventana modal con un solo botón; no abre un bucle de eventos propio (se llama desde el temporizador). `causa` es
        la frase que nombra las transiciones que se repiten."""
        texto = "Simulación detenida: el grafcet no alcanza una situación estable." + (f"\n\n{causa}" if causa else "")
        cuadro = QMessageBox(QMessageBox.Icon.Warning, TITULO, texto, QMessageBox.StandardButton.Ok, self)
        cuadro.button(QMessageBox.StandardButton.Ok).setText("Aceptar")
        cuadro.finished.connect(lambda _=0: setattr(self, "_popup_inestable", None))
        self._popup_inestable = cuadro
        cuadro.open()

    def _iniciar_reloj(self):
        self.reloj.start()
        self._marca_reloj_ns = self._resto_reloj_ns = 0

    def _refrescar_modbus(self):
        ahora = perf_counter()
        if self.modbus.activo and ahora - self._ultimo_refresco_modbus < TICK_MS / 1000:
            return
        self._ultimo_refresco_modbus = ahora
        self._recordar_conexion()
        if not self.modbus.activo:
            self._sincronizar_es()
        self.panel_es.mostrar_estado(self.modbus.estado, self.modbus.mensaje)
        self.panel_es.mostrar_tiempos(self.modbus.medidas, self.modbus.ultima_parada)
        self.panel_es.ocupado(self.modbus.activo)
        self.panel_es.mostrar_redondeos(self.modbus.adaptador.redondeos if self.modbus.adaptador else {})
        if self.modo == "simular" and self.paginas_es.currentIndex() == 0:
            self.refrescar()
        else:
            self.panel_es.mostrar_muestra(self.modbus.muestra, self.modbus.adaptador.entradas,
                self.modbus.escritos, getattr(self.modbus.adaptador, "salidas_control", []))

    def _tick(self) -> None:
        marca = self.reloj.nsecsElapsed() if self.reloj.isValid() else 0
        us, self._resto_reloj_ns = divmod(max(0, marca - self._marca_reloj_ns) + self._resto_reloj_ns, 1000)
        self._marca_reloj_ns = marca
        if self.modbus.activo:
            ejecutar = (self.a_ejecutar.isChecked() and self.modbus.estado == "conectado"
                        and not self.modbus.reiniciando and self.modbus.adaptador.sesion is not None)
            if ejecutar and self.modbus.en_marcha and self.v and self.v.s and self.v.s.status == "pausada-estable":
                self.v.s.advance_to(self.v.s.z.time + us)
            self.modbus.tick(ejecutar)
            if self.a_ejecutar.isChecked():
                self._vigilar_motor()
                if self.modbus.estado in ("error", "desconectado", "diagnostico") or self.modbus.adaptador.sesion is None:
                    self._parar_sin_cambiar_vista()
            self._proxima_lectura.stop()
            if (self.modbus.estado == "conectado" and not self.modbus.fallo_motor
                    and self.modbus.futuro is None):
                espera = max(1, ceil((self.modbus.proxima - perf_counter()) * 1000))
                self._proxima_lectura.start(espera)
            self._refrescar_modbus()
            if not self.modbus.activo:
                self.rt.setInterval(TICK_MS)
                self.rt.stop()
            return
        if not self.a_ejecutar.isChecked():  # Pausa sin conexión: el reloj no tiene nada que avanzar
            self.rt.stop()
            self.rt.setInterval(TICK_MS)
            return
        if self.v is None or self.v.s is None:
            self.a_ejecutar.setChecked(False)
            return
        if not self._vigilar_motor():
            self._act("avanzar", us=us)

    def _raiz_modbus(self):
        if (self.modo == "editar" or self.fuente.get("tipo") == "editor") and self.edicion:
            return self.edicion.ruta
        return self.fuente.get("raiz")

    def _persistir_mapa_modbus(self, config):
        if self.modbus.activo:
            self.modbus.reasignar(config,self.panel_es.doc)
        raiz = self._raiz_modbus()
        if raiz and self.panel_es.doc:
            try:
                config.guardar(raiz / ARCHIVO, self.panel_es.doc)
                if self.edicion and getattr(self.edicion,"contenedor",None):
                    self.edicion.ed.dirty=True;self._titulo_ventana()
            except (OSError, ValueError) as exc:
                self.panel_es.estado.setText(f"No se pudo guardar el mapa: {exc}")

    def _cargar_config_modbus(self, doc: dict[str, Any] | None = None) -> None:
        doc = doc or self.v.doc
        raiz = self._raiz_modbus()
        config, avisos = None, []
        origen = "Última configuración utilizada" if self.ajustes.contains("modbus/configuracion") or self.ajustes.contains("modbus/host") else "Configuración inicial del servidor"
        fallo = None
        # Recargar el mismo proyecto conserva el mapa en memoria; cambiar de proyecto exige un mapa propio.
        anterior = self.panel_es.config
        cambio = self._proyecto != self._proyecto_modbus
        self._proyecto_modbus = self._proyecto
        if not cambio and anterior.modelo == doc["id"]:
            config = anterior
            origen = "Configuración de este proyecto en memoria"
        elif raiz and (raiz / ARCHIVO).exists():
            try:
                origen = "Configuración guardada en el proyecto"
                config = Configuracion.cargar(raiz / ARCHIVO, doc, avisos)  # lo que ya no casa se descarta; el resto se conserva
            except (ValueError, OSError) as exc:
                fallo = f"No se pudo cargar el mapa: {exc}"
        if self.modbus.activo:
            config = copy.deepcopy(config or Configuracion(modelo=doc["id"], canales=copy.deepcopy(self._parametros_recordados["canales"])))
            config.host, config.puerto, config.unidad = self.modbus.cliente.host, self.modbus.cliente.puerto, self.modbus.cliente.unidad
        self.panel_es.cargar(doc, config, avisos)
        self.panel_es.host.setToolTip(f"{origen}. Copia la dirección que muestra el software del servidor Modbus.")
        if fallo:
            self.panel_es.mostrar_estado("error", fallo)
        if self.modbus.activo and cambio:
            self._cambiar_modelo_modbus(doc)

    def _cambiar_modelo_modbus(self, doc: dict[str, Any]) -> None:
        """Otro modelo con la conexión viva: TCP se conserva, pero lo que el modelo anterior hubiera escrito ya no lo controla
        nadie (cero) y la lectura sigue con el mapa del modelo nuevo, cuyas salidas asignadas también se ponen a cero (el
        coordinador junta los dos ceros en uno)."""
        anterior = self.modbus.adaptador  # no depende de lo ya confirmado: una escritura en vuelo puede haber llegado a la planta
        if anterior is not None and (anterior.salidas or getattr(anterior, "salidas_control", [])):
            self.modbus.pausar(diagnostico=True)
        try:
            self.modbus.observar(self.panel_es.config, doc)
        except ERRORES as exc:
            self.modbus.mensaje = f"Conectado · el mapa de este modelo no es válido: {exc}"

    def _guardar_config_modbus(self):
        try:
            config = self.panel_es.obtener()
            raiz = self._raiz_modbus()
            if raiz:
                ruta = raiz / ARCHIVO
            else:
                nombre, _ = QFileDialog.getSaveFileName(self, "Guardar configuración Modbus", ARCHIVO, "JSON (*.json)")
                if not nombre:
                    return
                ruta = Path(nombre)
            config.guardar(ruta, self.panel_es.doc)
            self.panel_es.config = config
            self.panel_es.estado.setText(f"Configuración guardada: {ruta}")
        except (ValueError, OSError) as exc:
            self.panel_es.estado.setText(f"No se pudo guardar: {exc}")

    def _abrir_config_modbus(self):
        nombre, _ = QFileDialog.getOpenFileName(self, "Cargar configuración Modbus", "", "JSON (*.json)")
        if nombre:
            try:
                avisos = []
                config = Configuracion.cargar(Path(nombre), self.panel_es.doc, avisos)
                self.panel_es.cargar(self.panel_es.doc, config, avisos)
                self.panel_es.estado.setText("Mapa cargado · desconectado")
            except (ValueError, OSError) as exc:
                self.panel_es.estado.setText(f"No se pudo cargar: {exc}")

    def _leer_conexion_recordada(self) -> tuple[str, int, int]:
        """El último (host, puerto, esclavo) con el que se conectó o se probó con éxito; la primera vez, la configuración inicial."""
        a = self.ajustes
        crudo = a.value("modbus/host", CONEXION_INICIAL[0])
        self._aviso_host_recordado = aviso_host(crudo)  # lo que no es IP no se cambia en silencio: el panel avisa
        host = normalizar_host(crudo)  # «localhost» pasa a 127.0.0.1; lo que no es IPv4, a la inicial (sin guardarlo todavía)
        puerto, unidad = a.value("modbus/puerto", CONEXION_INICIAL[1], type=int), a.value("modbus/unidad", CONEXION_INICIAL[2], type=int)
        if not host or not 1 <= puerto <= 65535 or not 0 <= unidad <= 255:  # un valor roto no debe dejar sin conexión propuesta
            return CONEXION_INICIAL
        return host, puerto, unidad

    def _leer_parametros_recordados(self) -> dict[str, Any]:
        host, puerto, unidad = self._leer_conexion_recordada()
        base = {"host": host, "puerto": puerto, "unidad": unidad, "periodo_ms": 20, "timeout_ms": 500,
                "canales": copy.deepcopy(CANALES_INICIALES), "escalas": {}}
        try:
            texto = self.ajustes.value("modbus/configuracion", "")
            if texto:
                datos = json.loads(str(texto))
                if not isinstance(datos, dict):
                    raise ValueError("preferencias inválidas")
                # las cantidades de canales no se heredan: una versión anterior guardó aquí 16/8 y las imponía
                propuesta = {**base, **{k: datos[k] for k in base if k in datos and k != "canales"}}
                c = Configuracion(**{k: v for k, v in propuesta.items() if k != "escalas"})
                c.validar({"id": "", "variables": []})
                if not isinstance(propuesta["escalas"], dict):
                    raise ValueError("escalas inválidas")
                from fractions import Fraction
                for clave, escala in propuesta["escalas"].items():
                    area, numero = clave.split(":")
                    if area not in CANALES_INICIALES or not 0 <= int(numero) <= 65535 or Fraction(str(escala)) <= 0:
                        raise ValueError("escala inválida")
                return propuesta
        except (ValueError, TypeError, ZeroDivisionError, AttributeError):
            pass
        return base

    def _recordar_parametros(self, config: Configuracion) -> None:
        datos = {k: getattr(config, k) for k in ("host", "puerto", "unidad", "periodo_ms", "timeout_ms")}
        datos["canales"] = copy.deepcopy(CANALES_INICIALES)  # (siempre las iniciales: las del proyecto van en su mapa)
        datos["escalas"] = dict(self.panel_es.escalas_base)
        datos["escalas"].update({f"{s.area}:{s.direccion}": s.escala for s in config.senales})
        texto = json.dumps(datos, ensure_ascii=False, sort_keys=True)
        if self.ajustes.value("modbus/configuracion", "") != texto:
            self.ajustes.setValue("modbus/configuracion", texto)
            for clave in ("host", "puerto", "unidad"):
                self.ajustes.setValue(f"modbus/{clave}", datos[clave])
            self.ajustes.sync()
        self._parametros_recordados = datos
        self._conexion_recordada = tuple(datos[k] for k in ("host", "puerto", "unidad"))
        self.panel_es.conexion_defecto = self._conexion_recordada
        self.panel_es.aviso_host_defecto = ""  # (ya se guardó una IP, con éxito)
        self.panel_es.parametros_defecto = copy.deepcopy(datos)

    def _recordar_conexion(self) -> None:
        """Recuerda parámetros completos tras una conexión o prueba con éxito, nunca las asignaciones de otro proyecto."""
        m = self.modbus
        if m.cliente is None or not (m.estado == "conectado" or (m.estado == "desconectado" and m.mensaje.startswith("Conexión probada"))):
            return
        config = copy.deepcopy(self.panel_es.config)
        config.host, config.puerto, config.unidad = m.cliente.host, m.cliente.puerto, m.cliente.unidad
        self._recordar_parametros(config)

    def _configuracion_para_guardar(self, doc: dict[str, Any]) -> Configuracion:
        if not getattr(self.panel_es,"conectado",False):
            self.panel_es.actualizar(doc)
            config = self.panel_es.obtener()
        else:
            # Guardar no cambia el mapa ni la lectura que están en uso por una conexión viva.
            config = copy.deepcopy(self.panel_es.config)
            config.quitar_obsoletas(doc)
            config.modelo = doc["id"]
            config.validar(doc)
        return config

    def _doc_es(self) -> dict[str, Any] | None:
        """El modelo cuyas variables enseña el panel de E/S: el que se edita; al simular, el que se está ejecutando."""
        if self.modo == "editar" and self.edicion:
            return self.edicion.ed.model
        return self.v.doc if self.v else None

    def _autoasignar_nuevas_es(self):
        e=self.edicion
        if e is None or getattr(self,'solo_lectura',False):return
        doc=e.ed.model; actuales={v['id'] for v in doc['variables']}
        previos=getattr(self,'_variables_es_vistas',actuales)
        self._auto_es_pendientes.update(actuales-previos);self._variables_es_vistas=actuales
        self._auto_es_pendientes.intersection_update(actuales)
        if not self._auto_es_pendientes:return
        if self._proyecto_modbus!=self._proyecto:self._cargar_config_modbus(doc)
        else:self.panel_es.actualizar(doc)
        faltan=self.panel_es.autoasignar(self._auto_es_pendientes)
        self._auto_es_pendientes.clear()
        if faltan:self.statusBar().showMessage('Sin canal Modbus libre: '+', '.join(faltan),12000)

    def _sincronizar_es(self, mostrando: bool = False) -> None:
        """Deja las listas y los canales del panel de E/S con las variables actuales del modelo, conservando el mapa y la
        configuración (la IP incluida); lo que ya no casa se quita con aviso. Con la conexión viva no se toca: el mapa en
        uso no cambia a mitad de sesión y solo se marca que hay variables nuevas pendientes de ver al desconectar. Al
        mostrar el panel (`mostrando`) también se cambia de mapa si el proyecto es otro; en cualquier otro momento, solo
        si el panel se ve y sigue siendo el mismo proyecto (cambiar de proyecto lo hace `_cargar_config_modbus`)."""
        doc, p = self._doc_es(), self.panel_es
        if doc is None:
            return
        mismo = self._proyecto == self._proyecto_modbus and p.config.modelo == doc["id"]
        if not mostrando and not mismo:
            return
        if mismo:
            cambio=p.firma(doc)!=p.firma_modelo
            p.actualizar(doc)
            if cambio and self.modbus.activo:self.modbus.reasignar(p.config,doc)
        else:
            self._proyecto_modbus = self._proyecto
            p.cargar(doc)
        self._autoasignar_nuevas_es()

    def mostrar_es(self):
        self._sincronizar_es(mostrando=True)
        self._mostrar_pagina(True)

    def _mostrar_pagina(self, es: bool | str, refrescar_planos=True) -> None:
        """Cambio centralizado entre GRAFCET (0), E/S (1) y Planos (2)."""
        destino=2 if es=="planos" else (1 if es else 0)
        if destino==2 and getattr(self,"solo_lectura",False): return
        anterior = self.paginas_es.currentIndex()
        if anterior == 0 and destino != 0 and self._plegables["derecho"].abierto:
            self._tamanos_paneles["derecho"] = self._plegables["derecho"].width()
        if self.paginas_es.currentIndex()==2 and destino!=2:self.panel_planos.aplicar()
        if destino==2 and refrescar_planos:
            self.panel_planos.mostrar()
            self.panel_planos.parpadear_boton_hoja()
        self.paginas_es.setCurrentIndex(destino)
        if destino == 0 and anterior != 0:
            # El contenido oculto conserva geometrías viejas al cambiar de pantalla.
            # Restaurar el ancho del panel, o solo su pestaña si está plegado.
            self._anchos_laterales(self._tamanos_paneles["derecho"])
        self._sincronizar_boton_es()
        if destino == 0 and anterior != 0 and self.modo == "simular" and self.v is not None:
            self.refrescar()  # El dibujo se actualiza al volver, antes del siguiente sondeo.

    def _alternar_planos(self,on):
        self._mostrar_pagina("planos" if on else False)

    def _alternar_es(self, on: bool) -> None:
        """El botón conmutador: marcado abre la vista de E/S; desmarcado vuelve al dibujo GRAFCET."""
        if on:
            self.mostrar_es()
        else:
            self._mostrar_pagina(False)

    def _sincronizar_boton_es(self, _indice: int = 0) -> None:
        """Deja el botón con el aspecto de la página que se ve (también si la página la cambió otra vía: la flecha ← del
        panel, la prueba guiada…): «E/S externas» en el dibujo GRAFCET; «Vista GRAFCET», pulsado, en la vista de E/S."""
        es = self.paginas_es.currentIndex() == 1
        self.a_es.blockSignals(True)
        self.a_es.setChecked(es)
        self.a_es.blockSignals(False)
        self._aspecto_boton_es(es)
        indice=self.paginas_es.currentIndex()
        if hasattr(self,'pestanas_vistas'):
            self.pestanas_vistas.blockSignals(True);self.pestanas_vistas.setCurrentIndex({0:0,1:2,2:1}[indice]);self.pestanas_vistas.blockSignals(False)
            self.luz_es.setProperty("abierta",indice==1);self.luz_es.style().unpolish(self.luz_es);self.luz_es.style().polish(self.luz_es)  # activa mientras se ve E/S
            pendiente=self.destino_traer is not None and self.destino_traer[0] is self.edicion
            self.aviso_traer.setVisible(indice==0 and pendiente)
        if hasattr(self,'tb_edit'):self.tb_edit.setVisible(indice==0 and self.modo=='editar' and not getattr(self,'solo_lectura',False))
        if hasattr(self,"herramientas_grafcet"):self.herramientas_grafcet.setVisible(indice==0 and not pendiente)
        planos=self.paginas_es.currentIndex()==2
        self.a_planos.blockSignals(True);self.a_planos.setChecked(planos);self.a_planos.blockSignals(False)
        self.a_planos.setToolTip("Volver al GRAFCET" if planos else "Editar planos, plantillas y cajetín")
        self.a_ejecutar.setEnabled(not(es or planos or pendiente));self.a_reiniciar.setEnabled(not(es or planos or pendiente))
        editar=self.modo=="editar" and not planos and not pendiente and not getattr(self,"solo_lectura",False)
        for a in (*self.a_herr.values(),self.a_debajo,self.a_girar_izq,self.a_girar_der):a.setEnabled(editar)
        e=self.edicion
        self.a_deshacer.setEnabled(not pendiente and (editar or planos) and e is not None and bool(e.ed.undo_stack));self.a_rehacer.setEnabled(not pendiente and (editar or planos) and e is not None and bool(e.ed.redo_stack));self.a_borrar.setEnabled(editar and e is not None and bool(e.sel))
        self.a_dependencias.setEnabled(not planos) if hasattr(self,"a_dependencias") else None
        self._actualizar_portapapeles()
        self._seleccion_para_hoja(indice==0 and pendiente)

    def _aspecto_boton_es(self, es: bool) -> None:
        """Texto, tooltip e icono del botón conmutador en cada una de sus dos vistas."""
        self.a_es.setText("Vista GRAFCET" if es else "E/S externas")
        self.a_es.setToolTip("Volver al dibujo GRAFCET" if es else
                             "Conectar sensores y actuadores · se vuelve con este mismo botón o con la flecha ← del panel")
        self.a_es.setIcon(self._iconos_es[1 if es else 0])

    def _fijar_ancho_boton_play(self) -> None:
        boton = self.tb_sim.widgetForAction(self.a_ejecutar)
        inicial = self.a_ejecutar.isChecked()
        anchos = []
        for on in (False, True):
            self._marcar_play(on)
            anchos.append(boton.sizeHint().width())
        self._marcar_play(inicial)
        boton.setFixedWidth(max(anchos))

    def _fijar_ancho_boton_es(self) -> None:
        """El botón mide siempre lo del más ancho de sus dos estados (texto e icono): al alternar entre «E/S externas» y «Vista
        GRAFCET» no se mueve nada más de la barra."""
        boton = self.tb_conexion.widgetForAction(self.a_es)
        anchos = []
        for es in (False, True):
            self._aspecto_boton_es(es)
            anchos.append(boton.sizeHint().width())
        self._aspecto_boton_es(self.paginas_es.currentIndex() == 1)
        boton.setFixedWidth(max(anchos))

    def _conectar_modbus(self, prueba=False):
        try:
            config = self.panel_es.obtener()
        except (ValueError, RuntimeError) as exc:
            self.panel_es.estado.setText(f"No se pudo conectar: {exc}")
            return
        self._iniciar_conexion_modbus(config, None, prueba)

    def _iniciar_conexion_modbus(self, config, sesion, prueba):
        try:
            self._parar_sin_cambiar_vista()
            self.modbus.iniciar(config, sesion, prueba, documento=self.panel_es.doc)
            self.panel_es.config = config
            self.panel_es._dibujar()
            self.panel_es.ocupado(True)
            self.panel_es.estado.setText(self.modbus.mensaje)
            self.rt.setInterval(config.periodo_ms)
            self._iniciar_reloj()
            self.rt.start()
        except (ValueError, RuntimeError) as exc:
            self.panel_es.estado.setText(f"No se pudo conectar: {exc}")

    def _parar_sin_cambiar_vista(self):
        anterior=getattr(self,"_conservar_vista_al_parar",False)
        self._conservar_vista_al_parar=True
        try:self.a_ejecutar.setChecked(False)
        finally:self._conservar_vista_al_parar=anterior

    def _desconectar_modbus(self):
        anterior = getattr(self, "_conservar_vista_al_parar", False)
        self._conservar_vista_al_parar = True
        try:
            self.a_ejecutar.setChecked(False)
        finally:
            self._conservar_vista_al_parar = anterior
            self._sincronizar_boton_es()
        self.modbus.desconectar()
        self.panel_es.estado.setText(self.modbus.mensaje)
        self.rt.start()

    # -- presentación del estado ----------------------------------------------------------------
    def refrescar(self) -> None:
        if self.a_ejecutar.isChecked() and self._vigilar_motor():
            return
        M, S = self.v.model, self.v.state()
        simulando = self.modo == "simular"  # al editar, el dibujo, el estado y el título son los de la edición
        if simulando:
            label, color = ESTADOS.get(S["status"], (S["status"], "muted"))
            self.estado.setText(label)
            self.estado.setStyleSheet(f"color: {COL[color]}; border: 1px solid {COL[color]}; border-radius: 9px; "
                                      "padding: 1px 9px")
            self.titulo.setText(M["title"])
            self.ayuda.setText(M["help"]);self.ayuda.setToolTip(M["help"])
        stable, rec = S["status"] == "pausada-estable", S["status"] == "pausada-recorrido"
        self._diagnostico(S, rec)
        if simulando:
            estado_dibujo = S if "time" in S else {}
            # El reloj y la traza se muestran fuera del dibujo. Los temporizadores,
            # valores, colores e historial gráfico siguen formando parte de la huella.
            huella = {k: v for k, v in estado_dibujo.items()
                      if k not in ("time", "timeUs", "trace", "nextEvent", "nextEventUs")}
            previo = getattr(self, "_dibujo_simulado", None)
            if previo is None or previo[0] is not M or previo[1] != huella:
                self.diagrama.mostrar(M, estado_dibujo)
                self._dibujo_simulado = (M, copy.deepcopy(huella))
        values = S.get("values", {})
        for var, b in self.botones.items():
            b.setEnabled(stable)
            if var in self.campos:
                if not self.campos[var].hasFocus():
                    self.campos[var].setText(str(values.get(var, "")))
                self.campos[var].setEnabled(stable)
                continue
            on = values.get(var) is True
            b.setChecked(on)
            if on == b.nc:
                b.enclavado = False
            b.indicar(on)
            b.setText(f"{self.nombre(var)} = {1 if on else 0}")
            b.setStyleSheet(f"background: {COL['accent_soft']}; border: 1px solid {COL['accent']}; color: #1d2330; "
                            "padding: 5px 10px" if on else "padding: 5px 10px")
        if simulando:
            self.l_reloj.setText(f"τ = {t_trunc(S['timeUs']) if 'timeUs' in S else '—'}"
                                 + (f" · próximo vencimiento: {S['nextEvent']}" if S.get("nextEvent") else ""))
        self._lecturas()
        self._variables(M, S)
        self._traza(S)
        if hasattr(self, "panel_es"):
            valores = dict(S.get("values", {}))
            valores.update({k: x["value"] for k, x in S.get("outputs", {}).items()})
            if self.modbus.activo:
                a = self.modbus.adaptador
                for senal in a.entradas:
                    if senal.variable in self.modbus.muestra:
                        raw = self.modbus.muestra[senal.variable]
                        if senal.formato != "BOOL":
                            from fractions import Fraction
                            raw = raw - 65536 if senal.formato == "INT16" and raw >= 32768 else raw
                            raw = Fraction(raw) / Fraction(senal.escala)
                        valores[senal.variable] = raw
                for senal in (*a.salidas, *getattr(a, "salidas_control", [])):  # en Pausa, las asignadas siguen mostrando su último valor escrito
                    if senal.variable in self.modbus.escritos:
                        raw = self.modbus.escritos[senal.variable]
                        if senal.formato != "BOOL":
                            from fractions import Fraction
                            raw = raw - 65536 if senal.formato == "INT16" and raw >= 32768 else raw
                            raw = Fraction(raw) / Fraction(senal.escala)
                        valores[senal.variable] = raw
                for vid in self.botones:
                    if vid in self.panel_es.indicadores:
                        self.botones[vid].setEnabled(False)
                        if vid in self.campos:
                            self.campos[vid].setEnabled(False)
            self.panel_es.mostrar_valores(valores)

    def _diagnostico(self, S: dict[str, Any], rec: bool) -> None:
        e = html.escape
        if S["status"] == "no-compilable":
            items = "".join(f"<li>{e(amable(sin_codigos(d['message']), d['code']))}<br><i>{e(d.get('correction', ''))}</i></li>"
                            for d in S.get("diagnostics", []))
            self.diag.setText(f"<b>El programa no puede compilarse</b><ul>{items}</ul>Corrija el modelo; no se ejecuta "
                              "nada hasta entonces.")
            self.diag.show()
            return
        ds = [d for d in S.get("diagnostics", []) if S["status"] == "error" or rec][-1:]
        if not ds:
            self.diag.hide()
            return
        d, blk = ds[0], S.get("blocked")
        text = (f"<p>{e(amable(sin_codigos(d['message']), d['code']))}</p>"
                f"<p><i>{e(d.get('correction', ''))}</i></p>")
        if blk:
            text += (f"<p>El recorrido está determinado hasta las etapas {{{e(', '.join(self.nombre(i) for i in blk['reached']))}}}"
                     + (f"; el elemento en cuestión es <b>{e(self.nombre(blk['element']))}</b>" if blk.get("element") else "")
                     + ". Lo que ocurra después depende de una cuestión abierta, así que el lote se rechaza entero.</p>")
        if S["status"] == "error":
            text += ("<p>El motor no aproxima: conserva la última situación estable"
                     + (f" {{{e(', '.join(self.nombre(i) for i in blk['lastStable']))}}}, que <b>no</b> es el resultado del lote" if blk else "")
                     + ". Pulse «Reiniciar» (Ctrl+R) para seguir.</p>")
        else:
            text += "<p>Queda un contexto pendiente: puede completarse evolución a evolución.</p>"
        self.diag.setText(text)
        self.diag.show()

    def _lecturas(self) -> None:
        """Aviso discreto, en la barra de estado, cuando alguna lectura difiere de la decidida por el responsable."""
        changed = [q for q, v in self.options.items() if q in SEMANTIC_OPTIONS and v != SEMANTIC_OPTIONS[q]["default"]]
        self.l_lect.setText("Ajustes de simulación no habituales · " if changed else "")
        self.l_lect.setToolTip("Cambian cómo reacciona la simulación (Ajustes > Ajustes de simulación)"
                               if changed else "")

    def _variables(self, M: dict[str, Any], S: dict[str, Any]) -> None:
        outs = S.get("outputs") or {}
        rows = [(self.nombre(k), "salida continua", "ON" if o["value"] else "OFF", ", ".join(self.nombre(c) for c in o["contributors"]),
                 "ok" if o["value"] else "muted") for k, o in outs.items()]
        rows += [(self.nombre(k), "memorizada", str(v), "", "text") for k, v in (S.get("values") or {}).items()
                 if k not in M["inputs"] and k not in outs]
        self._filas(self.t_vars, rows)
        temp = S.get("temporal") or {}
        self.c_temp.setVisible(bool(temp))
        self._filas(self.t_temp, [(t["where"], t["estado"], t["lleva"], t["preset"],
                                   "accent" if t["estado"] == "contando" else "ok" if t["estado"] == "vencido" else "muted")
                                  for t in temp.values()], 1)

    @staticmethod
    def _filas(t: QTableWidget, rows: list[tuple[str, ...]], col_color: int = 2) -> None:
        t.setRowCount(len(rows))
        for i, (*cells, color) in enumerate(rows):
            for j, c in enumerate(cells):
                item = t.item(i, j)
                if item is None:
                    item = QTableWidgetItem(c)
                    item.setToolTip(c)  # el texto entero, aunque la celda lo recorte
                    t.setItem(i, j, item)
                elif item.text() != c:
                    item.setText(c)
                    item.setToolTip(c)
                if j == col_color and item.foreground().color() != QColor(COL[color]):
                    item.setForeground(QColor(COL[color]))

    def _traza(self, S: dict[str, Any]) -> None:
        self.traza.clear()
        for r in S.get("trace", []):
            item = QListWidgetItem(f"{r['time']:>9}   {r['text']}")
            if r["kind"] in TRAZA:
                item.setForeground(QColor(COL[TRAZA[r["kind"]]]))
            self.traza.addItem(item)
        self.traza.scrollToBottom()

    # -- guardar ------------------------------------------------------------------------------
    def guardar(self) -> bool:
        return self.guardar_proyecto()

    def guardar_en(self, destino: Path) -> None:
        if Path(destino).suffix.lower()!='.grafnet':
            raise ValueError('El proyecto debe guardarse como archivo .grafnet')
        if not self._guardar_archivo(destino):raise ValueError('No se guardó el proyecto')

    def _seleccion_para_hoja(self,activo):
        if activo:
            self.estado.setText('seleccionando para Planos');self.ayuda.setText('Clic: cadena completa · Mayús+clic: añadir otra cadena · Ctrl+clic: añadir o quitar un elemento. Sin jerarquías inferiores automáticas.')
        if activo==getattr(self,'_seleccionando_hoja',False):return
        self._seleccionando_hoja=activo
        if activo:
            from .hojas import SeleccionParaHoja
            self._paneles_traer={n:p.abierto for n,p in self._plegables.items()}
            self._tamanos_traer=(self.split_izquierdo.sizes(),self.split.sizes(),self.vsplit.sizes())
            for n in self._paneles_traer:
                self._plegables[n].hide();self.flechas[n].hide();self.pestanas[n].hide()
            self.diagrama.controlador=SeleccionParaHoja(self.edicion);self.diagrama.setAcceptDrops(False)
            self._estilo_traer=self.diagrama.styleSheet();self.diagrama.setStyleSheet(self._estilo_traer+' QGraphicsView {border:2px solid #aa914c; background:#fffaf0;}')
            self.estado.setText('seleccionando para Planos');self.ayuda.setText('Clic: cadena completa · Mayús+clic: añadir otra cadena · Ctrl+clic: añadir o quitar un elemento. Sin jerarquías inferiores automáticas.')
        else:
            self.diagrama.controlador=self.edicion if self.modo=='editar' else None;self.diagrama.setAcceptDrops(self.modo=='editar' and not getattr(self,'solo_lectura',False));self.diagrama.setStyleSheet(getattr(self,'_estilo_traer',''))
            for n,visible in getattr(self,'_paneles_traer',{}).items():
                self._mostrar_panel(n,visible,guardar=False);self.flechas[n].setVisible(visible)
            sizes=getattr(self,'_tamanos_traer',(None,None,None))
            if sizes[0] is not None:self.split_izquierdo.setSizes(sizes[0])
            if sizes[1] is not None:self.split.setSizes(sizes[1])
            if sizes[2] is not None:self.vsplit.setSizes(sizes[2])
            if self.modo=='editar':self.refrescar_edicion()

    def preparar_traer(self,ident):
        if not ident or not self.edicion:return
        self.panel_planos.aplicar();self.destino_traer=(self.edicion,ident);self._mostrar_pagina(False)
        self.diagrama.setFocus()

    def cancelar_traer(self):
        self.destino_traer=None;self.aviso_traer.hide();self._mostrar_pagina('planos')

    def confirmar_traer(self):
        if not self.destino_traer or self.destino_traer[0] is not self.edicion:
            self.destino_traer=None;self.aviso_traer.hide();return
        e,ident=self.destino_traer
        if not e.sel:
            QMessageBox.information(self,'Traer GRAFCET','Selecciona los elementos que quieres añadir.');return
        try:
            self.panel_planos.mostrar(ident);self.panel_planos.insertar(e.copiar_fragmento().selected)
        except (ValueError,RuntimeError) as exc:QMessageBox.warning(self,'Traer GRAFCET',str(exc));return
        self.destino_traer=None;self.aviso_traer.hide();self.mostrar_hoja(ident)

    def historial_plano(self,rehacer=False):
        e=self.edicion
        if e is None:return
        plano=self.paginas_es.currentIndex()==2
        if plano:
            p=self.panel_planos;p.aplicar()
            p.liberar_editor()
        (e.rehacer if rehacer else e.deshacer)()
        if plano:self.panel_planos.mostrar()

    def enviar_seleccion_lamina(self):
        e=self.edicion
        if e is None or self.modo!='editar' or not e.sel:return
        self.panel_planos.aplicar()
        from .hojas import CrearHoja
        d=CrearHoja(e,self)
        try:
            if not d.exec():return
            ident=d.destino.currentData()
            if ident is None:
                from .hojas import dibujo_vinculado
                from .laminas import DocumentoLaminas
                cfg=d.configuracion or d.valores();prueba=DocumentoLaminas(dibujo_vinculado(e,e.copiar_fragmento().selected),{},cfg)
                if prueba.total!=1:raise ValueError('La selección no cabe al 100 %. Elige una hoja mayor o selecciona menos elementos.')
                ident=e.ed.add_plan_page(None,d.configuracion or d.valores(),d.nombre.text().strip() or None)
            e.cambia();self.panel_planos.mostrar(ident);self.panel_planos.insertar(e.copiar_fragmento().selected);self.mostrar_hoja(ident)
        except (OSError,ValueError,RuntimeError) as exc:QMessageBox.warning(self,'Enviar a plano',str(exc))
        finally:d.deleteLater()

    def abrir_hojas(self):
        self._mostrar_pagina("planos")
        self.panel_planos.lista.setFocus()

    def mostrar_hoja(self,ident):
        self.panel_planos.mostrar(ident)
        self._mostrar_pagina("planos",False)

    def abrir_laminas(self, accion="previa") -> None:
        if getattr(self,"solo_lectura",False):
            if accion=="imprimir":
                from .laminas import DocumentoLaminas
                doc=DocumentoLaminas(self.edicion.M,self.v.state() if self.modo=="simular" else {},self.edicion.ed.sheet_settings(),self.diagrama.dependencias)
                doc.imprimir(self)
            return
        if accion in ("exportar","imprimir") and self.paginas_es.currentIndex()==2 and self.panel_planos.editor:
            self.panel_planos.aplicar()
        else:
            self.panel_planos.mostrar();self._mostrar_pagina("planos",False)
        editor=self.panel_planos.editor
        if editor and accion in ("exportar","imprimir"):getattr(editor,accion)()

    def guardar_imagen(self) -> None:
        editando = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar el dibujo", f"{self.edicion.titulo if editando else self.v.key}.png",
                                              "Imagen PNG (*.png)")
        dependencias = self.diagrama.dependencias  # lo que la vista dibuja ahora (el botón «Mostrar dependencias»)
        img = (imagen(self.edicion.M, {}, dependencias=dependencias) if editando else
               imagen(self.v.model, self.v.state(), dependencias=dependencias) if ruta else None)
        if ruta and not img.save(ruta):
            QMessageBox.warning(self, TITULO, f"No se pudo guardar {ruta}")

    def acerca(self) -> None:
        AcercaDe(self).exec()

    # -- indicador de la conexión externa -------------------------------------------------------
    def _luz_es(self, estado: str, mensaje: str = "") -> None:
        """Punto de color y texto breve en la barra de simulación: verde conectada, gris desconectada, rojo error."""
        color, texto = {"conectado": ("#3f9d4a", "conectada"), "error": ("#d64545", "error"),
                        "diagnostico": ("#d64545", "error")}.get(estado, ("#8a949c", "desconectada"))
        punto = QPixmap(12, 12)
        punto.fill(Qt.GlobalColor.transparent)
        p = QPainter(punto)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 10, 10)
        p.end()
        self.luz_es.setIcon(QIcon(punto))
        self.luz_es.setIconSize(QSize(12, 12))
        self.luz_es.setText(f"E/S externas: {texto}")
        self.luz_es.setToolTip((mensaje + "\n" if mensaje else "") + "Abrir E/S externas")
        self.luz_es.setAccessibleName(f"E/S externas: {texto}")
        self.luz_es.setProperty("estadoLuz", texto)

    # -- actualizaciones -----------------------------------------------------------------------
    def _buscar_al_arrancar(self, on: bool) -> None:
        self.ajustes.setValue(actualizaciones.CLAVE_AL_ARRANCAR, bool(on))
        self.ajustes.sync()

    def buscar_actualizaciones(self, manual: bool = False) -> None:
        """Consulta la última versión publicada en segundo plano. En el arranque (manual=False) no dice nada si falla."""
        if manual:
            self.statusBar().showMessage("Buscando actualizaciones…", 3000)
        self.comprobador.comprobar(manual)

    def _resultado_actualizacion(self, manual: bool, r: actualizaciones.Resultado) -> None:
        if r.estado == "nueva":
            if manual:
                self.aviso_version.hide()
                caja = QMessageBox(QMessageBox.Icon.Information, TITULO,
                                   f"Hay una versión nueva de GRAFCET Connect ({r.version}). Esta es la {APP_VERSION}.", parent=self)
                descargar = caja.addButton("Descargar", QMessageBox.ButtonRole.AcceptRole)
                caja.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
                caja.exec()
                if caja.clickedButton() is descargar:
                    QDesktopServices.openUrl(QUrl(actualizaciones.url_segura(r.url)))
            elif actualizaciones.ignorada(self.ajustes) != r.version:
                self._version_nueva = r
                self.l_version.setText(f"Hay una versión nueva de GRAFCET Connect ({r.version}).")
                self.aviso_version.show()
        elif manual:
            texto = ("Ya tiene la última versión de GRAFCET Connect." if r.estado == "al_dia" else
                     "No se ha podido comprobar: sin conexión o sin respuesta del servidor.")
            QMessageBox.information(self, TITULO, texto)

    def _descargar_version(self) -> None:
        if self._version_nueva:
            QDesktopServices.openUrl(QUrl(actualizaciones.url_segura(self._version_nueva.url)))
        self.aviso_version.hide()

    def _descartar_version(self) -> None:
        if self._version_nueva:
            actualizaciones.ignorar(self.ajustes, self._version_nueva.version)
        self.aviso_version.hide()


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="GRAFCET", description=TITULO)
    ap.add_argument("modelo", nargs="?", help="archivo .grafnet")
    ap.add_argument("--ejemplo", choices=list(EJEMPLOS), help="ejemplo con el que empezar")
    ap.add_argument("--captura", metavar="PNG", help="guardar una captura de la ventana y salir (comprobación)")
    ap.add_argument("--prueba-contenedor",action="store_true",help=argparse.SUPPRESS)
    ap.add_argument("--prueba-distribucion", metavar="GRAFNET", help=argparse.SUPPRESS)
    ap.add_argument("--prueba-propiedades", metavar="TXT", help=argparse.SUPPRESS)
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    if args.prueba_contenedor:
        from .proyecto_archivo import comprobar_contenedor
        comprobar_contenedor()
        return 0
    if args.prueba_distribucion:
        # Comprobación de construcción: clave de distribución (no la de desarrollo) y que abre su propio ejemplo.
        from grafcet.contenedor import sello_valido
        datos = Path(args.prueba_distribucion).read_bytes()
        return 0 if not sello.DESARROLLO and sello_valido(datos, sello.CLAVE) else 3
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(TITULO)
    app.setWindowIcon(QIcon(str(ICONO_PROGRAMA)))
    from .errores import instalar as instalar_avisos_de_error
    instalar_avisos_de_error()
    from .carpetas import asegurar_carpetas
    try:asegurar_carpetas()
    except OSError as exc:QMessageBox.warning(None,"Carpetas de GRAFCET Connect",str(exc))
    w = Ventana()
    if args.prueba_propiedades:
        # Comprobación de construcción: el diálogo Propiedades del archivo se monta en el ejecutable.
        import traceback
        try:
            propiedades_archivo.PropiedadesArchivo(propiedades_archivo.recopilar(w.edicion, True), w)
            Path(args.prueba_propiedades).write_text("ok", encoding="utf-8")
            return 0
        except Exception:
            Path(args.prueba_propiedades).write_text(traceback.format_exc(), encoding="utf-8")
            return 4
    if args.ejemplo:
        w.cargar_ejemplo(args.ejemplo)
    if args.modelo and not w.abrir_ruta(Path(args.modelo)):
        return 1 if args.captura else 0
    w.show()
    if (not args.captura and not os.environ.get(actualizaciones.VARIABLE_SIN_ACTUALIZAR)
            and actualizaciones.al_arrancar_activo(w.ajustes)):
        QTimer.singleShot(1500, w.buscar_actualizaciones)  # con la ventana ya a la vista; en un hilo, sin bloquear
    if args.captura:
        QTimer.singleShot(300, lambda: (w.grab().save(args.captura), app.quit()))
    return app.exec()
