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

from PySide6.QtCore import QObject, Signal, QEvent, QElapsedTimer, QSettings, Qt, QTimer, QSize, QRectF, QPointF, QPoint, QUrl
from PySide6.QtGui import (QDesktopServices, QCursor, QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter,
                           QPainterPath, QPen, QPixmap, QFont, QFontMetrics)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
                               QScrollArea, QSplitter, QStackedWidget, QTabBar, QTableWidget, QTableWidgetItem,
                               QToolBar, QToolButton, QVBoxLayout, QWidget, QStyle, QMenu, QTextEdit, QPlainTextEdit, QAbstractSpinBox,
                               QSizePolicy, QStylePainter, QStyleOptionButton, QAbstractButton, QAbstractScrollArea, QStyledItemDelegate)

from . import recursos_ui  # Registra los iconos vectoriales incorporados.
from . import estilo
from . import estilo_botones
from .laminas import VistaLamina
from .estilo import _trazos_reinicio  # noqa: F401  (las pruebas lo leen desde aquí)
from . import propiedades_archivo
from . import actualizaciones
from .aviso_version import DialogoVersionNueva
from grafcet.diagnostics import DiagnosticError
from grafcet.engine import Session
from grafcet.examples import EJEMPLOS
from grafcet.persistence import open_model
from grafcet.profile import APP_VERSION, SEMANTIC_OPTIONS, normalize_options
from grafcet.timeutil import parse_duration
from grafcet.view import Vista, auto_layout, layout_from_presentation, t_trunc

from .diagrama import COL, VistaDiagrama, imagen
from .edicion import HERRAMIENTAS, Edicion, aviso_valores_iniciales, quitar_valores_iniciales, sin_codigos
from .propiedades import FichaJerarquia, PanelPropiedades, Paleta
from .flotantes import GestorFlotantes
from .navegacion import Navegacion
from .leyenda import Leyenda
from .mensajes import amable, motivo_parada, partir
from .alto_opciones import agrandar_para_transicion
from .paneles import (PanelPlegable, DivisorPlegable, PilaActual, EtiquetaAyuda, EtiquetaElidida, ChipModo, BandaModo,
                      CajaSeccion, TituloSeccion, CabeceraCompacta, ContextoNombres, DelegadoNombres, EtiquetaGrupos, ReparteColumnas,
                      partir_nombre, LINEAS_NOMBRE)
from .variables import PanelVariables
from .entradas_salidas import CONEXION_INICIAL, PanelES
from conexion.configuracion import ARCHIVO, CANALES_INICIALES, Configuracion, aviso_host, normalizar_host
from conexion.coordinador import Coordinador

TITULO = "GRAFCET Connect"
URL_CODIGO = "https://github.com/SrLaguarto/GRAFCET-Connect"  # dónde está el código (diálogo «Acerca de»)
URL_FALLOS = "https://github.com/SrLaguarto/GRAFCET-Connect/issues"  # dónde se comunica un fallo o una sugerencia
ICONO_PROGRAMA = Path(__file__).resolve().parent / "recursos" / "grafcet_connect.ico"
HUECO_FRANJA = 4  # px entre la franja de modo (4 px de alto, arriba del recuadro del dibujo) y la fila de cabecera
ANCHO_DERECHO = 270  # el panel derecho desde UMBRAL_DERECHO px de ancho de ventana (P10: «Papel» y «Tipo» enteros, tablas de estado con sus cuatro columnas)
UMBRAL_DERECHO = 1280
ANCHO_LATERAL = 212  # ancho mínimo de los paneles laterales al editar (la tabla de variables enseña los nombres)
NOMBRE_MIN_TABLA = 96  # la columna del nombre de las tablas (estado de la simulación) mide al menos esto a cualquier tamaño: las demás se compactan antes
ANCHO_TITULO_UTIL = 150  # cabecera del dibujo: lo que mide, como poco, el título del grafcet para que se reconozca (antes de ceder sitio al zoom con palabras)
ARRIBA_CAJA = 1  # margen superior del contenido de una sección: con el hueco del título deja E2 entre el título y lo primero (T3)
ARRIBA_VARIABLES = 4  # (el título de Variables es más grande)
ANCHO_AYUDA_UTIL = 200  # y lo que pide la ayuda de debajo del título para leerse en dos líneas (con menos, se queda en el botón «Ayuda ▾»)
ALTO_INFERIOR = {"simular": 220, "editar": 240}  # altura inicial del panel inferior: la traza, o las opciones de lo seleccionado
ESPERA_ESCALA = 120  # ms sin cambios de tamaño de la ventana antes de aplicar la escala nueva (una sola vez por ráfaga de `resizeEvent`)
ESPERA_ARRANQUE = 600  # ms desde el primer `show` en los que la escala se aplica sin esperar (la ventana se maximiza al arrancar)
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

    ACENTO = estilo.ACENTO

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from . import VERSION
        self.setWindowTitle(f"Acerca de {TITULO}")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QDialog {{ background: {estilo.FONDO} }} QLabel {{ color: {estilo.TINTA} }}")
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        cab = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon(str(ICONO_PROGRAMA)).pixmap(64, 64))
        cab.addWidget(icono)
        titulo = QLabel(f"<span style='font-size:{estilo.T_TITULO + 4}px; font-weight:600; color:{self.ACENTO}'>{TITULO}</span><br>"
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
                                   f"border: 1px solid transparent; border-radius: {estilo.R_S}px; padding: 0 14px }}")  # (el borde transparente deja el alto de control de la hoja global)
        self.b_fallo.clicked.connect(lambda: self.abrir(URL_FALLOS))
        fila = QHBoxLayout()
        fila.addWidget(self.b_fallo)
        fila.addStretch(1)
        lay.addLayout(fila)
        garantia = QLabel("Este programa se ofrece sin ninguna garantía. Las licencias, la propia y las de las "
                          "bibliotecas incluidas, están en la carpeta «licencias». Interfaz con Qt for Python "
                          "(PySide6), bajo licencia LGPL v3.")
        garantia.setWordWrap(True)
        garantia.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: 12px")
        lay.addWidget(garantia)
        cerrar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cerrar.rejected.connect(self.reject)
        cerrar.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        lay.addWidget(cerrar)

    def abrir(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))


def _icono_grafcet() -> QIcon:
    """Esquema de etapa, transición y etapa (el dibujo GRAFCET), para el botón que vuelve desde la vista de E/S."""
    return estilo.icono_grafcet()


def _icono_barra(tipo: str, color: str = estilo.TINTA) -> QIcon:
    """Iconos de línea propios para los controles de la aplicación (no son notación GRAFCET); de un solo trazo (estilo.py)."""
    return estilo.icono(tipo, color)


class _BotonAyuda(QToolButton):
    """El enlace «Ayuda ▾» de la cabecera del dibujo: pide su ancho natural pero no fija el mínimo de la ventana (si no hay sitio, `_ajustar_cabecera`
    lo esconde antes que cortarlo; así la ventana sigue cabiendo en media pantalla)."""

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)  # (con «Minimum», el mínimo del diseño sería su `sizeHint`)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, super().minimumSizeHint().height())


class _BotonEntrada(QPushButton):
    """El estado marcado sigue el valor de la entrada, no el automatismo checkable de Qt. Pulsada, enclavada o conmutada
    se distingue por la forma del icono (anillo, punto, candado, interruptor), por el texto («= 1») y por el relleno.
    Un nombre largo **se lee entero**: se parte por los «_» en dos o tres líneas (`ContextoNombres.lineas`) y el botón crece lo que
    haga falta, con « = 0 / = 1» pegado a la última línea; solo si ni en tres líneas cabe se elide por el medio. Nunca cambia el ancho de
    la ventana; el nombre entero va también en la ayuda y, con el foco, con el puntero encima o al pulsarla, en la línea de detalle. Mantener
    pulsado se comporta como siempre (P-IMP-75): la entrada sigue a 1 mientras dure. El foco es el de siempre: un clic lo da (y Espacio
    repite la pulsación); el anillo solo se ve con el teclado."""
    sobre = Signal(bool)  # el puntero entra (True) o sale (False): la línea de detalle dice el nombre entero

    def __init__(self) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setProperty("entrada", True)
        self.control = self.enclavado = self.liberar = self.interruptor = self.nc = False
        self.ayuda_base = ""
        self.contexto: ContextoNombres | None = None  # los nombres de las demás entradas: el elidido no confunde dos
        self.setMinimumHeight(estilo.ALTO_ENTRADA)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def enterEvent(self, event: Any) -> None:  # noqa: N802
        super().enterEvent(event)
        self.sobre.emit(True)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.sobre.emit(False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(160, estilo.ALTO_ENTRADA)

    def nombre_completo(self) -> str:
        texto = self.text()
        return texto.rpartition(" = ")[0] or texto

    def _ancho_texto(self) -> int:
        """Lo que queda para el texto: el botón menos el relleno (10 px a cada lado), el borde (2) y el icono con su hueco."""
        return max(24, self.width() - 2 * 10 - 2 * 2 - self.iconSize().width() - 8)

    def lineas_visibles(self) -> list[str]:
        """El texto del botón en sus líneas: el **nombre entero**, partido por los «_» en las líneas que haga falta (hasta tres; solo si ni así
        cabe se elide por el medio) y, pegado al final de la última, « = valor»."""
        nombre, separador, valor = self.text().rpartition(" = ")
        if not separador:
            return [self.text()]
        sufijo = " = " + valor
        if self.contexto is not None:
            return self.contexto.lineas(nombre, self.fontMetrics(), self._ancho_texto(), LINEAS_NOMBRE, sufijo)
        return partir_nombre(nombre, self.fontMetrics(), self._ancho_texto(), sufijo)[:LINEAS_NOMBRE]

    def texto_visible(self) -> str:
        """El texto que se ve ahora en el botón (el nombre partido en sus líneas, separadas por «\\n», y « = valor»)."""
        return "\n".join(self.lineas_visibles())

    def ajustar_alto(self) -> None:
        """El botón mide lo que sus líneas: con una, el alto de siempre; con el nombre partido en dos o tres, una línea más por cada una (la
        fila crece lo necesario y el nombre se lee entero)."""
        n = len(self.lineas_visibles()) if self.width() >= 40 else 1
        alto = estilo.ALTO_ENTRADA + 2 + (n - 1) * self.fontMetrics().lineSpacing()
        if n == 1:
            self.setMinimumHeight(estilo.ALTO_ENTRADA)
            self.setMaximumHeight(16777215)
        elif self.minimumHeight() != alto or self.maximumHeight() != alto:
            self.setFixedHeight(alto)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.ajustar_alto()

    def setText(self, texto: str) -> None:  # noqa: N802
        super().setText(texto)
        nombre = self.nombre_completo()
        self.setToolTip(f"{nombre}\n{self.ayuda_base}" if self.ayuda_base else nombre)
        self.ajustar_alto()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self.control = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        super().mousePressEvent(event)
    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QStylePainter(self)
        opcion = QStyleOptionButton()
        self.initStyleOption(opcion)
        # (con el foco, la hoja de estilo pinta el anillo `[tecl="true"]:focus`: aquí no se toca el estado del foco)
        if " = " in opcion.text:
            opcion.text = self.texto_visible()
        painter.drawControl(QStyle.ControlElement.CE_PushButton, opcion)

    def ancho_natural(self, texto: str | None = None) -> int:
        """Lo que mide el botón con el texto entero (en negrita, como lo pone la entrada activa)."""
        fuente = QFont(self.font())
        fuente.setBold(True)
        return 2 * 10 + 2 * 2 + self.iconSize().width() + 8 + QFontMetrics(fuente).horizontalAdvance(self.text() if texto is None else texto)

    def indicar(self, on: bool) -> None:
        estado = (self.interruptor, self.enclavado, on)
        if estado == getattr(self, "_indicador", None):
            return
        self._indicador = estado
        pm = QPixmap(48, 40)
        pm.setDevicePixelRatio(2)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(estilo.SIMULACION if on else estilo.TINTA_3)
        p.setPen(QPen(color, 1.6))
        if self.interruptor:
            p.drawRoundedRect(QRectF(1, 4, 20, 12), 6, 6)
            p.setBrush(color)
            p.drawEllipse(QPointF(15 if on else 7, 10), 3.4, 3.4)
        elif self.enclavado:
            p.drawArc(QRectF(7, 1, 8, 12), 0, 180 * 16)
            p.setBrush(QColor(estilo.SIMULACION_SUAVE))
            p.drawRoundedRect(QRectF(5, 8, 12, 9), 1.5, 1.5)
            p.drawLine(11, 11, 11, 14)
        else:
            p.setBrush(color if on else Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(11, 10), 5.5, 5.5)
        p.end()
        self.setIconSize(QSize(24, 20))
        self.setIcon(QIcon(pm))

    def nextCheckState(self) -> None:  # noqa: N802
        pass  # refrescar() pone el valor confirmado por la simulación


class _AjustaBanda(QObject):
    """Mantiene la franja de modo pegada al borde superior de la tarjeta del dibujo, a todo su ancho."""
    def __init__(self, tarjeta: QWidget, banda: QWidget) -> None:
        super().__init__(tarjeta)
        self.tarjeta, self.banda = tarjeta, banda

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            margen = estilo.R_M + 2  # dentro de las esquinas redondeadas de la tarjeta: el remate de la flecha no sobresale
            self.banda.setGeometry(margen, 0, max(0, self.tarjeta.width() - 2 * margen), 4)
            self.banda.raise_()
        return False


class _SalidaRaton(QObject):
    """Avisa de que el puntero sale del área visible de una tabla (para que la línea de detalle deje de hablar de la fila de debajo)."""

    def __init__(self, padre: QObject, al_salir: Any) -> None:
        super().__init__(padre)
        self.al_salir = al_salir

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() == QEvent.Type.Leave:
            self.al_salir()
        return False


class _VigilaAlto(QObject):
    """Llama a `fn` cada vez que cambia el tamaño de `objetivo`."""

    def __init__(self, objetivo: QWidget, fn: Callable[[], None]) -> None:
        super().__init__(objetivo)
        self.fn = fn
        objetivo.installEventFilter(self)

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() == QEvent.Type.Resize:
            self.fn()
        return False


class _DelegadoAbreviado(QStyledItemDelegate):
    """Enseña un texto corto en lugar del entero («continua» por «salida continua», «memoria» por «memorizada»): la celda sigue
    teniendo el texto entero (y lo lleva en su ayuda y en la línea de detalle), solo se pinta más corto para que la columna se lea.
    Con `corto` (la tabla no tiene sitio ni para la primera abreviatura) se pinta la más corta: «cont.», «mem.»."""

    def __init__(self, abreviaturas: dict[str, str], padre: QObject, cortas: dict[str, str] | None = None) -> None:
        super().__init__(padre)
        self.abreviaturas = abreviaturas
        self.cortas = cortas or abreviaturas
        self.corto = False

    def displayText(self, valor: Any, locale: Any) -> str:  # noqa: N802
        texto = str(valor)
        return (self.cortas if self.corto else self.abreviaturas).get(texto, texto)


class _AjustaCabecera(QObject):
    """Mantiene el título del grafcet dentro del sitio que dejan el chip de modo (que no cede: lleva el estado), los controles del
    zoom y el buscador: el título es lo que cede primero y se elide con «…»."""
    def __init__(self, tarjeta: QWidget, ventana: Any) -> None:
        super().__init__(tarjeta)
        self.tarjeta, self.ventana = tarjeta, ventana

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self.ventana._ajustar_cabecera()
            self.ventana._zoom_diferido()  # (el alto del dibujo cambió, o se abrió el buscador: puede que el zoom deba ir en la cabecera o flotar)
        return False


class _FocoTeclado(QObject):
    """Un filtro por aplicación para el teclado.

    (1) **El anillo de foco solo se ve si la última entrada fue del teclado.** Qt da el foco por sí solo (al ocultarse el control
    que lo tenía, al cambiar de página, al abrir un panel…) y lo hace con el motivo «Tab», así que el motivo no sirve para saber
    si hay un teclado de por medio. El filtro recuerda la última entrada: una tecla de navegación (Tab, flechas, Espacio,
    Intro, Esc…) la pasa a «teclado» y un clic, la rueda o un toque la pasan a «ratón». El control con el foco lleva la propiedad
    `tecl` (cierta solo con el teclado) y la hoja global y las locales pintan el anillo con `[tecl="true"]:focus`; con la entrada
    cambiada a ratón, el que lo tenía lo pierde al instante. Los campos de texto no dependen de esto: en ellos se escribe y su
    foco se ve siempre.
    (2) Un botón con el foco se activa también con Intro, como con Espacio.
    (3) Los botones de la ventana no toman el foco con el ratón.
    (4) Soltar Ctrl suelta las entradas enclavadas con Ctrl+clic (antes lo hacía otro filtro: con uno solo, la aplicación hace una
    llamada menos por cada evento, que son decenas de miles al reconstruir la vista de E/S)."""
    TECLAS = frozenset((Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                        Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Space,
                        Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape))
    PUNTERO = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.Wheel, QEvent.Type.TouchBegin,
               QEvent.Type.TabletPress)
    CON_ANILLO = (QAbstractButton, QTabBar, QAbstractScrollArea, VistaLamina)  # los controles cuyo anillo depende del teclado

    def __init__(self, padre: QObject | None = None) -> None:
        super().__init__(padre)
        self.teclado = False  # arrancar con el ratón: ningún anillo hasta la primera tecla de navegación

    def _marcar_foco(self, valor: bool) -> None:
        foco = QApplication.focusWidget()
        if foco is not None and isinstance(foco, self.CON_ANILLO):
            estilo.poner(foco, tecl=valor)

    INTERES = frozenset((*PUNTERO, QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.FocusIn, QEvent.Type.FocusOut, QEvent.Type.Show))

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        tipo = evento.type()
        if tipo not in self.INTERES:  # (el filtro ve todos los eventos de la aplicación: casi todos se descartan aquí, sin más)
            return False
        if tipo == QEvent.Type.KeyRelease:
            if evento.key() == Qt.Key.Key_Control and not evento.isAutoRepeat():  # soltar Ctrl suelta las entradas enclavadas con Ctrl+clic
                while objeto is not None:
                    if isinstance(objeto, Ventana):
                        objeto._soltar_enclavados()
                        break
                    objeto = objeto.parent()
            return False
        if tipo in self.PUNTERO:
            if self.teclado:
                self.teclado = False
                self._marcar_foco(False)
        elif tipo == QEvent.Type.KeyPress and evento.key() in self.TECLAS:
            if not self.teclado and (evento.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) or not evento.modifiers() & (
                    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)):
                self.teclado = True
                self._marcar_foco(True)
        elif tipo == QEvent.Type.FocusIn and isinstance(objeto, self.CON_ANILLO):
            estilo.poner(objeto, tecl=self.teclado)
        elif tipo == QEvent.Type.FocusOut and isinstance(objeto, self.CON_ANILLO):
            estilo.poner(objeto, tecl=False)
        if (tipo == QEvent.Type.KeyPress and evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not evento.modifiers() and isinstance(objeto, (QPushButton, QToolButton)) and objeto.hasFocus()
                and objeto.isEnabled() and isinstance(objeto.window(), Ventana)):
            objeto.animateClick()
            return True
        if (tipo == QEvent.Type.Show and isinstance(objeto, (QPushButton, QToolButton))
              and objeto.focusPolicy() in (Qt.FocusPolicy.StrongFocus, Qt.FocusPolicy.NoFocus) and not objeto.isCheckable()
              and isinstance(objeto.window(), Ventana)):
            objeto.setFocusPolicy(Qt.FocusPolicy.TabFocus)
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
        estilo_botones.instalar()  # (iconos y textos de los botones de herramientas, centrados; una sola vez)
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
        self._arrancando = False  # el primer instante tras mostrarse la ventana por primera vez: la escala se aplica sin esperas
        self._arranque_hecho = False
        self._escala_lista = False  # verdadero solo mientras se aplica la escala que esperaba el final de la ráfaga de cambios de tamaño
        self._espera_escala = QTimer(self)
        self._espera_escala.setSingleShot(True)
        self._espera_escala.timeout.connect(self._escala_tras_la_rafaga)
        self._escala = "normal"  # la escala de letra y de controles de ahora (estilo.escala_para): cambia sola con el tamaño
        estilo.activar_escala("normal")
        self._muy_estrecho = False
        self._ancho_forzado = 0  # por debajo de este ancho «Reiniciar» va como icono (lo fija `_vigilar_barra` si no cabe con texto)
        self._compacto = (False, False)  # (estrecho, bajo): lo fija el tamaño de la ventana (estilo.tamano_compacto)
        self._manual_paneles: dict[str, bool] = {}  # paneles que el usuario ha plegado o desplegado a mano: no se tocan solos
        self._auto_plegados: set[str] = set()  # paneles que el modo compacto ha plegado solo (y volverá a abrir)
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
        self._errores_auto = False  # «Mostrar errores» lo marcó un Play fallido (no el usuario)
        self._avisos_ejecucion: list[tuple[str, str]] = []  # por qué se paró el motor (texto, ayuda): entre los avisos al editar
        self._ayuda = ""  # ayuda del ejemplo o modelo abierto, para mostrarla al simular lo que aún no se ha editado
        self._proyecto: Any = None  # qué proyecto hay abierto (los ID de modelo no lo distinguen: todos los ejemplos son «m»)
        self._proyecto_modbus: Any = None  # de qué proyecto es el mapa que tiene cargado el panel de E/S
        self._n_nuevos = 0
        self._tipos_entrada: dict[tuple[Any, str], bool] = {}
        self._bajo_raton: Any = None  # lo que tiene el puntero encima y la línea de detalle cuenta: una entrada, o (tabla, fila)
        self._zoom_pendiente = False  # hay una revisión (diferida) de dónde van los controles del zoom
        self._hoja_escala = ""  # la hoja de la escala grande que llevan las partes de la ventana ("" en la normal)
        self._es_pendiente = self._props_pendiente = False  # E/S y Propiedades aún llevan la escala de antes (se ponen al mostrarlos)
        self._entradas_nc = {}
        self._portapapeles = None
        self._menus()
        self._interfaz()
        self.diagrama.menu_portapapeles = self._menu_portapapeles
        QApplication.instance().focusChanged.connect(self._actualizar_portapapeles)
        QApplication.instance().focusChanged.connect(self._detalle_del_foco)
        app = QApplication.instance()
        if not hasattr(app, "_foco_teclado"):
            app._foco_teclado = _FocoTeclado(app)
            app.installEventFilter(app._foco_teclado)
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
        self.paginas_es.addWidget(self.panel_planos)  # PLANOS se pinta su propia tarjeta (`PaginaPlanos.paintEvent`)
        contenedor=QWidget();disposicion=QVBoxLayout(contenedor);disposicion.setContentsMargins(0,0,0,0);disposicion.setSpacing(0)
        self.pestanas_vistas=QTabBar();self.pestanas_vistas.setExpanding(False);self.pestanas_vistas.setDrawBase(True)
        for texto in ('GRAFCET','PLANOS','E/S externas'):self.pestanas_vistas.addTab(texto)
        self.pestanas_vistas.setTabVisible(2,False)  # a E/S se entra por la luz de conexión (`luz_es`); el índice 2 solo marca la página
        self.pestanas_vistas.setObjectName("pestanasVistas")  # su aspecto lo da la hoja global (estilo.py)
        self.pestanas_vistas.setUsesScrollButtons(False)  # son dos pestañas: nunca flechas de desplazamiento
        self.pestanas_vistas.setAccessibleName("Vista: GRAFCET, PLANOS")
        # La fila de arriba: las pestañas a la izquierda y, a la derecha del todo, la luz de la conexión externa (`luz_es`)
        self.fila_pestanas=QWidget();self.fila_pestanas.setObjectName('filaPestanas');self.fila_pestanas.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.fila_pestanas.setMinimumWidth(1)  # su contenido (con textos) no fija el mínimo de la ventana: «Reiniciar» y la luz pasan a icono y texto corto al estrecharse
        fila_p=QHBoxLayout(self.fila_pestanas);fila_p.setContentsMargins(estilo.E2,0,estilo.E2,0);fila_p.setSpacing(0)
        fila_p.addWidget(self.pestanas_vistas);fila_p.addStretch(1)
        disposicion.addWidget(self.fila_pestanas)
        self.aviso_traer=QWidget();self.aviso_traer.setObjectName('avisoSeleccionPlanos')
        self._estilo_aviso_traer()
        fila=QHBoxLayout(self.aviso_traer);fila.setContentsMargins(12,estilo.E2,12,estilo.E2);fila.setSpacing(estilo.E2);fila.addWidget(QLabel('PLANOS · Selecciona el GRAFCET para la hoja'))
        self.b_confirmar_traer=QPushButton('Añadir selección a la hoja');self.b_confirmar_traer.setObjectName('confirmarSeleccionHoja');fila.addWidget(self.b_confirmar_traer);cancelar=QPushButton('Cancelar');fila.addWidget(cancelar);fila.addStretch(1)
        self.b_confirmar_traer.clicked.connect(self.confirmar_traer);cancelar.clicked.connect(self.cancelar_traer)
        self.destino_traer=None;self.aviso_traer.hide();disposicion.addWidget(self.paginas_es,1);disposicion.addWidget(self.aviso_traer)
        self.setCentralWidget(contenedor)
        self.pestanas_vistas.currentChanged.connect(lambda i:self.mostrar_es() if i==2 else self._mostrar_pagina('planos' if i==1 else False))
        self.panel_es.volver.connect(lambda: self._mostrar_pagina(False))
        self.panel_es.detalle.connect(self._detallar)  # el nombre entero de lo que señala el puntero en E/S, en la barra de estado
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
        self._dialogo_version: DialogoVersionNueva | None = None
        self.comprobador = actualizaciones.Comprobador(self, obtener)
        self.comprobador.resultado.connect(self._resultado_actualizacion)
        self.nuevo()
        self._cargar_config_modbus(self.edicion.ed.model)
        for nombre in ("izquierdo","derecho","inferior"):
            self._mostrar_panel(nombre, nombre != "inferior" or self._inferior_al_arrancar, guardar=False)
        self._accesibilidad()
        self._configurar_foco()
        self._estilos_locales()
        self._foco_inicial = False
        # La hoja de la ventana es siempre la de la escala normal; en la escala grande la hoja entera (con las letras y los alto de control
        # grandes) va en las partes de la ventana, y en la vista de E/S solo cuando se muestra: así cruzar 1600×900 no repasa los más de mil
        # widgets de las filas de E/S (era lo que congelaba la interfaz ≈ 700 ms). El que está más cerca manda sobre el de la ventana.
        self._destinos_hoja = [self.menuBar(), self.statusBar(), self.fila_pestanas, self.herramientas_grafcet, self.split_izquierdo,
                               self.inferior.widget(0)]  # (la vista de E/S, Propiedades y PLANOS, al mostrarlas; el aviso de PLANOS lleva su hoja propia)
        self._planos_pendiente = False

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
        # Dónde se editan las propiedades del elemento: en una ventana flotante (por defecto) o en la barra inferior (`flotantes.py`)
        self.modo_propiedades = "abajo" if self.ajustes.value("paneles/propiedades", "flotante") == "abajo" else "flotante"
        self.g_props = QActionGroup(self)  # (exclusivo: una sola marcada y marcar la marcada no la desmarca)
        self.a_props = {}
        self.m_props = ver.addMenu("Panel de &opciones")
        for modo, texto in (("flotante", "&Flotante"), ("abajo", "&Abajo")):
            a = self._accion(texto, lambda on, m=modo: on and self._cambiar_modo_propiedades(m), None, True)
            a.setChecked(modo == self.modo_propiedades)
            self.g_props.addAction(a)
            self.m_props.addAction(a)
            self.a_props[modo] = a
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
        box = CajaSeccion(titulo)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, ARRIBA_CAJA, 0, estilo.E1)  # T3: E2 entre el título y lo primero; las tablas de la simulación van de borde a borde (a 218 px no caben sus cuatro columnas con más margen: SRED13)
        lay.setSpacing(estilo.E1)
        self.lado.addWidget(box)
        self._cajas_lado = getattr(self, "_cajas_lado", []) + [box]
        return box, lay

    def _interfaz(self) -> None:
        izq = QWidget()
        izq.setObjectName("panelDibujo")
        il = QVBoxLayout(izq)
        il.setContentsMargins(estilo.E2, estilo.E1 + HUECO_FRANJA, estilo.E2, estilo.E2)  # (un hueco bajo la franja de modo: el zoom y el chip no la tocan)
        il.setSpacing(2)
        self._margenes_dibujo = (estilo.E2, estilo.E1 + HUECO_FRANJA, estilo.E2, estilo.E2)
        # Franja de color de lo alto de la tarjeta del dibujo: azul tinta al editar, verde al simular (no ocupa sitio)
        self.banda_modo = BandaModo(izq)
        self.banda_modo.setObjectName("bandaModo")
        self.banda_modo.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.banda_modo.setFixedHeight(4)
        self.banda_modo.setProperty("modo", "editar")
        self.banda_modo.setAccessibleName("Modo")
        izq.installEventFilter(_AjustaBanda(izq, self.banda_modo))
        izq.installEventFilter(_AjustaCabecera(izq, self))
        cab = QHBoxLayout()
        cab.setSpacing(estilo.E2)
        self._cab = cab
        self.estado = ChipModo()
        self.estado.setObjectName("chipModo")
        self.titulo = EtiquetaElidida(ancho_maximo=380)  # el nombre del grafcet se elide con «…»: nunca ensancha la ventana
        self.titulo.setStyleSheet(f"font-family: {estilo.FAMILIA_TITULO}; font-size: {estilo.T_TITULO}px; font-weight: 700; color: {estilo.TINTA}")
        self.titulo.minimo = 8  # (el botón «Ayuda ▾» va siempre en la cabecera: el título cede hasta casi nada para que la ventana quepa en media pantalla)
        cab.addWidget(self.estado)
        cab.addWidget(self.titulo)
        il.addLayout(cab)
        self.ayuda = EtiquetaAyuda(2)
        self.ayuda.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: {estilo.T_PEQUENA}px")
        cab.addWidget(self.ayuda,1)
        # Una ayuda que no cabe en sus dos líneas no se corta a media frase sin más: un botón visible («más ▾») la despliega entera en su
        # propia fila bajo la cabecera (y «Ayuda ▴» la recoge). La ayuda habitual va siempre tras el botón «Ayuda ▾».
        self.b_ayuda = _BotonAyuda()
        self.b_ayuda.setObjectName("masAyuda")
        self.b_ayuda.setText("más ▾")
        self.b_ayuda.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_ayuda.setToolTip("Leer la ayuda entera")
        self.b_ayuda.setAccessibleName("Ayuda del dibujo")
        self.b_ayuda.clicked.connect(self._alternar_ayuda)
        self.b_ayuda.hide()
        cab.addWidget(self.b_ayuda)
        cab.setAlignment(self.b_ayuda, Qt.AlignmentFlag.AlignVCenter)
        self.ayuda_larga = QLabel()  # la ayuda entera, a todo el ancho de la tarjeta (solo desplegada)
        self.ayuda_larga.setObjectName("ayudaLarga")
        self.ayuda_larga.setWordWrap(True)
        self.ayuda_larga.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ayuda_larga.hide()
        self._ayuda_abierta = False
        self._estilo_ayuda()
        self.diagrama = VistaDiagrama()
        self.navegacion = Navegacion(self.diagrama)
        cab.addWidget(self.navegacion)
        self.estado.setFixedHeight(estilo.ALTO_BARRA - 8)  # el chip de modo; la fila mide lo del buscador, para que no salte al abrirlo
        self.titulo.setMinimumHeight(estilo.ALTO_CONTROL_COMPACTO)  # la fila mide lo que el buscador (32 px): no salta al abrirlo
        cab.setAlignment(self.estado, Qt.AlignmentFlag.AlignVCenter)
        ver_navegacion = self._accion("Navegación y filtros…", self.navegacion.abrir_opciones)
        next(a.menu() for a in self.menuBar().actions() if a.text()=="&Ver").addAction(ver_navegacion)
        il.addWidget(self.ayuda_larga)
        il.addWidget(self.diagrama, 1)
        # Panel inferior: al simular, la traza; al editar, las opciones de lo seleccionado
        self.traza = QListWidget()
        self.traza.setWordWrap(True)
        caja_traza = CajaSeccion("Traza")
        QVBoxLayout(caja_traza).addWidget(self.traza)
        self.props = PanelPropiedades()
        self.props.setObjectName("panelPropiedades")
        self.props.prog.franja_cambiada.connect(lambda: agrandar_para_transicion(self))  # las categorías pasan a dos filas: el panel crece lo justo
        for ficha in self.props.findChildren(FichaJerarquia):  # (la ficha de jerarquía en más filas: el panel crece)
            ficha.alto_cambiado.connect(lambda: QTimer.singleShot(0, self, self._dimensionar_opciones))
        self.props.alto_cambiado.connect(lambda: QTimer.singleShot(0, self, lambda: agrandar_para_transicion(self)))  # (y si el estado de la fórmula baja a su línea)
        self.inferior = PilaActual()
        self.inferior.addWidget(caja_traza)
        self.inferior.addWidget(self.props)
        self.flot = GestorFlotantes(self)  # las propiedades flotantes (se crean al usarlas)
        QApplication.instance().focusChanged.connect(self._foco_propiedades)
        self._leyenda: QDialog | None = None

        der = QWidget()
        self.lado = QVBoxLayout(der)
        self.lado.setContentsMargins(estilo.E1, estilo.E1, estilo.E1, estilo.E1)
        self.lado.setSpacing(estilo.E1)
        self.diag = QLabel()
        self.diag.setWordWrap(True)
        self.diag.setTextFormat(Qt.TextFormat.RichText)
        self.diag.setStyleSheet(f"border: 1px solid {estilo.ERROR}; background: {estilo.ERROR_FONDO}; color: {estilo.TINTA}; "
                                f"border-radius: {estilo.R_M}px; padding: {estilo.E2}px")
        self.lado.addWidget(self.diag)

        _, lay = self._caja("Entradas")
        self.l_ayuda_entradas = EtiquetaGrupos("Clic: pulsar · Ctrl+clic: enclavar · Clic derecho: tipo")  # (se parte entre acciones, nunca por dentro de una; en el panel táctil del portátil, el toque con dos dedos es el clic derecho)
        self.l_ayuda_entradas.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: {estilo.T_PEQUENA}px; font-weight: 400")
        lay.addWidget(self.l_ayuda_entradas)
        # Las entradas se desplazan por dentro de su caja, con un alto máximo (`_alto_entradas`) que deja ver al menos cuatro filas de
        # «Salidas y variables»: con muchas entradas, las salidas no quedan fuera de la vista
        self.cont_rejilla = QWidget()
        self.rejilla = QGridLayout(self.cont_rejilla)
        self.rejilla.setContentsMargins(0, 0, 0, 0)
        self.sc_entradas = QScrollArea()
        self.sc_entradas.setObjectName("scrollEntradas")
        self.sc_entradas.setWidgetResizable(True)
        self.sc_entradas.setFrameShape(QFrame.Shape.NoFrame)
        self.sc_entradas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sc_entradas.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sc_entradas.setWidget(self.cont_rejilla)
        self.sc_entradas.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # (se desplaza con la rueda y la barra; sus botones ya reciben el foco)
        self.sc_entradas.setStyleSheet("QScrollArea#scrollEntradas, QScrollArea#scrollEntradas > QWidget > QWidget { background: transparent; }")
        lay.addWidget(self.sc_entradas)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"color: {estilo.ERROR}")
        self.aviso.setVisible(False)  # sin texto no ocupa alto (se enseña solo cuando hay algo que avisar)
        lay.addWidget(self.aviso)

        _, lay = self._caja("Salidas y variables")
        # Las columnas a la vista: el ancho del panel es fijo, así que **manda la del nombre** (≥ 96 px, `ReparteColumnas`): las demás se
        # abrevian antes de que baje de ahí («Modo» pasa a «cont.»/«mem.»; «Estado», a «par.»/«cont.»/«venc.»), **ninguna desaparece**,
        # los nombres se parten por los «_» en las líneas que hagan falta y la tabla mide lo que sus filas: sin barras anidadas
        self.t_vars = self._tabla(["Variable", "Modo", "Valor", "Contribuyen"], (None, 46, 32, 70))
        self.t_vars.horizontalHeaderItem(1).setToolTip("Salida continua o memorizada")
        self.t_vars.setItemDelegateForColumn(1, _DelegadoAbreviado({"salida continua": "continua", "memorizada": "memoria"}, self.t_vars,
                                                                   {"salida continua": "cont.", "memorizada": "mem."}))
        self.t_vars.horizontalHeaderItem(3).setToolTip(
            "Acciones que contribuyen a la salida, con el nombre que les da el modelo (la etapa o, si no lo tienen, su identificador a.etapa.salida.n)")
        self.t_vars.horizontalHeader().abreviaturas = {"Contribuyen": "Contrib.", "Contrib.": "Contr."}
        self._del_vars = (DelegadoNombres(self.t_vars, (0,)), DelegadoNombres(self.t_vars, (3,), lineas=2))  # nombres partidos sin que dos se lean igual
        self.t_vars.setItemDelegateForColumn(0, self._del_vars[0])
        self.t_vars.setItemDelegateForColumn(3, self._del_vars[1])
        lay.addWidget(self.t_vars)
        self.t_vars.currentCellChanged.connect(self._detalle_del_foco)
        self.c_temp, lay = self._caja("Temporizadores")
        self.t_temp = self._tabla(["Dónde", "Estado", "Lleva", "Preset"], (None, 54, 36, 42))
        self.t_temp.horizontalHeaderItem(2).setToolTip("Tiempo transcurrido")
        self.t_temp.horizontalHeaderItem(3).setToolTip("Duración programada")
        self.t_temp.setItemDelegateForColumn(1, _DelegadoAbreviado({}, self.t_temp, {"parado": "par.", "contando": "cont.", "vencido": "venc."}))
        self.t_temp.horizontalHeader().abreviaturas = {"Estado": "Est."}
        self._del_temp = DelegadoNombres(self.t_temp, (0,))
        self.t_temp.setItemDelegateForColumn(0, self._del_temp)
        lay.addWidget(self.t_temp)
        self.t_temp.currentCellChanged.connect(self._detalle_del_foco)
        self._reparto = (ReparteColumnas(self.t_vars, 0, NOMBRE_MIN_TABLA, self._planes_vars, self._elegir_plan_vars,
                                         lambda: self.ajustar_tabla(self.t_vars), ideal=lambda: self._del_vars[0].ancho_para(2, self.t_vars.fontMetrics())),
                         ReparteColumnas(self.t_temp, 0, NOMBRE_MIN_TABLA, self._planes_temp, self._elegir_plan_temp,
                                         lambda: self.ajustar_tabla(self.t_temp), ideal=lambda: self._del_temp.ancho_para(2, self.t_temp.fontMetrics())))
        self._salida_raton = _SalidaRaton(self, lambda: self._sobre_fila(None, -1))
        for tabla in (self.t_vars, self.t_temp):  # el nombre entero también al pasar el ratón por la fila
            tabla.setMouseTracking(True)
            tabla.entered.connect(lambda indice, tabla=tabla: self._sobre_fila(tabla, indice.row()))
            tabla.viewport().installEventFilter(self._salida_raton)
        self.lado.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(der)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # con la ventana pequeña, también se desplaza a los lados
        self._vigila_alto = _VigilaAlto(self.scroll.viewport(), self._alto_entradas)  # (el alto máximo de las entradas sigue al del panel)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Página de edición: la herramienta, la selección y los diagnósticos (REQ-EDT-09)
        pag = QWidget()
        pag.setObjectName("panelVariables")
        pl = QVBoxLayout(pag)
        pl.setContentsMargins(estilo.E2, estilo.E2, estilo.E2, estilo.E2)  # el panel es estrecho: poco marco, para que quepa la tabla de variables
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
        self.variables.detalle.connect(self._detallar)
        caja_vars = CajaSeccion("Variables")
        caja_vars.setObjectName("grupoVariables")
        cv = QVBoxLayout(caja_vars)
        cv.setContentsMargins(estilo.E2, ARRIBA_VARIABLES, estilo.E2, estilo.E1)  # M4 y T3
        cv.addWidget(self.variables)
        self.l_resumen = QLabel()  # resumen accesible para la validación, sin bloque lateral
        self.l_resumen.hide()
        self.lista_diag = self.diagrama.lista_diagnosticos
        self.lista_diag.itemClicked.connect(self._ir_a_diagnostico)
        pl.addWidget(caja_vars)
        pl.addStretch(1)
        self.derecho = PilaActual()
        # F4: el botón de plegar (32 px) va en una fila de título propia sobre las tablas: al desplazar el panel ya no tapa la primera entrada
        pagina_sim = QWidget()
        psl = QVBoxLayout(pagina_sim)
        psl.setContentsMargins(0, 0, 0, 0)
        psl.setSpacing(0)
        self.titulo_sim = TituloSeccion("Simulación")
        self.titulo_sim.setObjectName("tituloPanel")
        self.titulo_sim.setContentsMargins(estilo.E2, 0, 40, 0)  # (a la derecha, el sitio del botón de plegar)
        self.titulo_sim.setFixedHeight(36)
        psl.addWidget(self.titulo_sim)
        psl.addWidget(self.scroll, 1)
        self.derecho.addWidget(pagina_sim)
        pag_scroll = QScrollArea()  # si no cabe, se desplaza en alto y en ancho
        pag_scroll.setWidgetResizable(True)
        pag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pag_scroll.setWidget(pag)
        self.derecho.addWidget(pag_scroll)
        self._pag_scroll, self._caja_vars = pag_scroll, caja_vars
        self._vigila_pagina = _VigilaAlto(pag_scroll.viewport(), self._alto_tabla_variables)
        self.derecho.setMinimumWidth(300)  # al simular; al editar, el mismo margen de ancho que el panel izquierdo
        # Izquierda: la paleta (una sola lista de fichas); solo al editar. Las opciones de lo seleccionado van abajo.
        self.paleta = Paleta()
        self.paleta.setMinimumWidth(self.paleta.ancho_minimo())  # las dos columnas de fichas, sin cortarse
        self.paleta.ayuda.connect(self._ayuda_ficha)  # un clic en una ficha solo muestra su ayuda
        self.paleta.escala = self.diagrama.escala
        self.dock = QWidget()  # panel izquierdo: solo a la altura del dibujo, no del panel inferior
        self.dock.setObjectName("panelElementos")
        vl = QVBoxLayout(self.dock)
        vl.setContentsMargins(1, 1, 1, 3)  # (dentro del borde de la tarjeta: ni la paleta ni el título lo tapan; abajo 3 px por la esquina redonda)
        titulo_elementos = TituloSeccion("Elementos")
        titulo_elementos.setObjectName("tituloPanel")
        titulo_elementos.setContentsMargins(12, 10, 8, 6)
        vl.addWidget(titulo_elementos)
        vl.addWidget(self.paleta, 1)
        # Ancho de los paneles laterales al editar: único y fijo (lo que piden las dos columnas de la paleta y, como mínimo,
        # lo que hace falta para que la tabla de variables deje ver los nombres), el mismo en el panel izquierdo y en el
        # izquierdo fijo; el derecho puede ampliarse y ambos se pueden plegar
        self.ancho_lateral = self._ancho_lateral_base = max(self.dock.minimumSizeHint().width(), ANCHO_LATERAL)
        self.ancho_derecho = self.ancho_lateral  # el del panel derecho: desde `UMBRAL_DERECHO` de ancho de ventana mide `ANCHO_DERECHO` (P10)
        self.variables.fijar_ancho_nominal(self.ancho_derecho)
        self.dock.setFixedWidth(self.ancho_lateral)
        self.dock.hide()
        # Arriba, el panel izquierdo (solo al editar), el dibujo y el panel derecho; abajo, a todo el ancho de la ventana, el
        # panel inferior (traza, opciones): así una fórmula larga o dos programadores por bloques caben sin apretarse.
        self._plegables = {n: PanelPlegable(c, titulo, n, lambda n=n: self._minimo_panel(n))
                          for n, c, titulo in (("izquierdo", self.dock, "Elementos"),
                                               ("derecho", self.derecho, "Variables"),
                                               ("inferior", self.inferior, "Propiedades"))}
        self._plegables["izquierdo"].maximo = lambda: self.ancho_lateral
        self._tamanos_paneles = {"izquierdo": self.ancho_lateral, "derecho": self.ancho_derecho, "inferior": ALTO_INFERIOR["editar"]}
        self.split = DivisorPlegable(Qt.Orientation.Horizontal)
        self.split.addWidget(izq)
        self.split.addWidget(self._plegables["derecho"])
        self.split.configurar(1, "derecho", 1, self._plegables["derecho"])
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 0)
        self.split.setHandleWidth(8)
        self._derecho_a_mano = False  # el usuario movió el divisor: su ancho no se vuelve a tocar al cambiar de tamaño la ventana
        self.split.splitterMoved.connect(lambda *_: setattr(self, "_derecho_a_mano", True))
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
        self.split_izquierdo.setContentsMargins(estilo.E2, 0, estilo.E2, 0)  # los paneles de arriba, alineados con la barra de herramientas (el inferior va de borde a borde)
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
        self.l_lect.setStyleSheet(f"color: {estilo.AVISO}; font-weight: 600")
        self.l_reloj = QLabel()
        self.l_reloj.setStyleSheet(f"font-weight: 600; color: {estilo.TINTA}; font-family: {estilo.FAMILIA_MONO}")
        self.l_reloj.setMinimumWidth(0)
        self.l_reloj.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)  # mide lo que su texto: nunca pierde caracteres
        self._ancho_reloj = 0  # lo más ancho que ha llegado a ser el texto del reloj (el reloj solo crece, para que la barra no baile)
        sb.addWidget(self.l_aviso)
        # La línea de detalle: el nombre entero (y papel, tipo, valor…) de la entrada, la variable o la fila que tiene el foco o está
        # elegida; los nombres largos se elidén por el medio en las listas y aquí se leen enteros, sin pasar el ratón por encima.
        self.l_detalle = EtiquetaElidida(ancho_maximo=10 ** 6, modo=Qt.TextElideMode.ElideMiddle)
        self.l_detalle.setStyleSheet(f"color: {estilo.TINTA}; font-weight: 600")
        self.l_detalle.setAccessibleName("Detalle")
        self.l_detalle.hide()
        sb.addWidget(self.l_detalle, 1)
        self.l_firma = QLabel()  # «Archivo sin firma»: discreto y permanente mientras el archivo abierto no tenga firma válida
        self.l_firma.setStyleSheet(f"color: {estilo.TINTA_2}")
        self.l_firma.hide()
        sb.addWidget(self.l_firma)
        # el mensaje temporal sustituye al texto fijo mientras dura (si no, se dibujan uno encima del otro)
        sb.messageChanged.connect(lambda texto: self.l_aviso.setVisible(not texto))
        sb.addPermanentWidget(self.l_lect)
        sb.addPermanentWidget(self.l_reloj)

    def _barra_herramientas(self) -> None:
        for accion, tipo in ((self.a_nuevo, "nuevo"), (self.a_abrir, "abrir"), (self.a_guardar, "guardar"),
                             (self.a_deshacer, "deshacer"), (self.a_rehacer, "rehacer"), (self.a_borrar, "borrar"),
                             (self.a_debajo, "debajo"), (self.a_cortar, "cortar"), (self.a_copiar, "copiar"),
                             (self.a_pegar, "pegar"), (self.a_ejecutar, "play"), (self.a_reiniciar, "reiniciar")):
            accion.setIcon(_icono_barra(tipo, estilo.BLANCO if tipo == "play" else estilo.TINTA))
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
        self.setStyleSheet(estilo.hoja_global())
        self.tb_sim = QToolBar("Simulación")
        self.tb_sim.setObjectName("barraSimulacion")
        self.tb_sim.setMovable(False)
        self.tb_sim.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tb_sim.setIconSize(QSize(20, 20))
        self.tb_sim.addAction(self.a_ejecutar)
        self.tb_sim.addAction(self.a_reiniciar)
        self.tb_sim.widgetForAction(self.a_ejecutar).setObjectName("botonPlay")  # el único botón primario de la barra
        self.tb_sim.widgetForAction(self.a_reiniciar).setObjectName("botonReiniciar")
        self.luz_es = QToolButton()  # estado de la conexión externa (Modbus), a la vista mientras se simula
        self.luz_es.setObjectName("luzES")
        self.luz_es.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.luz_es.setCursor(Qt.CursorShape.PointingHandCursor)
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
        # Una sola barra de edición a continuación de Play y Reiniciar: Deshacer · Rehacer | Cortar · Copiar · Pegar · Borrar | Añadir debajo · Dependencias.
        # Deshacer a Borrar (desactivados fuera de la edición, con la habilitación de sus acciones), solo icono con su ayuda y atajo; «Añadir debajo» y «Dependencias» con texto cuando hay sitio (`_textos_en_barras`).
        self.tb_edit = QToolBar("Edición")
        self.tb_edit.setObjectName("barraEdicion")
        self.tb_edit.setMovable(False)
        self.tb_edit.setIconSize(QSize(20, 20))
        self.tb_edit.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._acciones_solo_icono = []
        self.tb_edit.addSeparator()  # entre Reiniciar y Deshacer
        for grupo in ((self.a_deshacer, "Deshacer", "Ctrl+Z"), (self.a_rehacer, "Rehacer", "Ctrl+Y")),                      ((self.a_cortar, "Cortar", "Ctrl+X"), (self.a_copiar, "Copiar", "Ctrl+C"), (self.a_pegar, "Pegar", "Ctrl+V"),
                      (self.a_borrar, "Borrar la selección", "Supr")):
            for a, nombre, atajo in grupo:
                a.setToolTip(f"{nombre} ({atajo})")
                self.tb_edit.addAction(a)
                self.tb_edit.widgetForAction(a).setAccessibleName(nombre)
                self._acciones_solo_icono.append(a)
            self.tb_edit.addSeparator()
        self.tb_edit.addAction(self.a_debajo)
        self.a_debajo.setIconText("Añadir debajo")  # el texto del botón, sin el atajo que acompaña al del menú
        boton = self.diagrama.b_dependencias
        boton.setIcon(_icono_barra("dependencias"))
        boton.setAccessibleName("Mostrar dependencias")
        boton.setStyleSheet("")  # hereda el estilo común de la barra
        self.a_dependencias = self.tb_edit.addWidget(boton)  # (al simular, los botones de edición siguen ahí, desactivados)
        self.a_dependencias.setVisible(True)
        self.a_dependencias.setEnabled(True)
        boton.show()
        # «Mostrar errores»: conmutador del aviso de diagnósticos de la cabecera del dibujo (se ve y se actualiza en vivo al editar)
        self.b_errores = QToolButton()
        self.b_errores.setText("Mostrar errores")
        self.b_errores.setCheckable(True)
        self.b_errores.setIcon(_icono_barra("aviso"))
        self.b_errores.setToolTip("Mostrar los errores y avisos del grafcet")
        self.b_errores.setAccessibleName("Mostrar errores")
        self.b_errores.toggled.connect(self._alternar_errores)
        self._errores_auto = False  # lo marcó un Play fallido (y se desmarca solo al desaparecer los errores), no el usuario
        self.a_errores = self.tb_edit.addWidget(self.b_errores)
        self._a_errores = (self.a_errores,)
        self.a_errores.setVisible(True)
        self._textos_en_barras(True)
        self.addToolBar(self.tb_edit)
        self.tb_proyecto.hide()
        self.herramientas_grafcet=QWidget()
        self.herramientas_grafcet.setObjectName("herramientasGrafcet")
        self.herramientas_grafcet.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.herramientas_grafcet.setProperty("modo", "editar")  # la hoja global la tiñe de verde al simular
        fila=QHBoxLayout(self.herramientas_grafcet);fila.setContentsMargins(estilo.E2,estilo.E1,estilo.E2,estilo.E1);fila.setSpacing(estilo.E2)
        for barra in (self.tb_sim,self.tb_edit):
            self.removeToolBar(barra);fila.addWidget(barra);barra.show()
        fila.addStretch(1)
        self.centralWidget().layout().insertWidget(1,self.herramientas_grafcet)
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
        if not explicito and not self._props_abiertas():
            return
        self._mostrar_panel("inferior", True)
        if self.flot.activo():
            return  # (las ventanas flotantes se colocan solas junto al elemento)
        agrandar_para_transicion(self)
        QTimer.singleShot(0, self, self._ver_seleccion)
        QTimer.singleShot(80, self, self._ver_seleccion)

    def _props_abiertas(self) -> bool:
        """¿Están abiertas las propiedades? La barra inferior, o las ventanas flotantes (Ver ▸ Panel de opciones ▸ Flotante)."""
        return self.a_inferior.isChecked() if self.flot.activo() else self._plegables["inferior"].abierto

    def props_activo(self) -> PanelPropiedades:
        """El panel de propiedades que se está usando: el de la barra inferior o el de las ventanas flotantes."""
        return self.flot.panel if self.flot.activo() and self.flot.panel is not None else self.props

    def _cambiar_modo_propiedades(self, modo: str) -> None:
        """Ver ▸ Panel de opciones ▸ Flotante o Abajo: se recuerda, y lo abierto pasa de un sitio al otro."""
        if modo == self.modo_propiedades:
            return
        abierto = self.a_inferior.isChecked()
        self.ajustes.setValue("paneles/propiedades", modo)
        self.flot.ocultar()
        panel = self._plegables["inferior"]
        if modo == "flotante":
            self.modo_propiedades = "abajo"
            self._mostrar_panel("inferior", False, guardar=False)  # (se pliega la barra: al volver, se abre desde cero)
            self.modo_propiedades = modo
            self._mostrar_panel("inferior", abierto, guardar=False)
        else:
            self.modo_propiedades = modo
            panel.show()
            self._mostrar_panel("inferior", abierto, guardar=False)
        for m, a in self.a_props.items():
            a.blockSignals(True)
            a.setChecked(m == modo)
            a.blockSignals(False)
        if self.edicion is not None and self.modo == "editar":
            self.refrescar_edicion()

    def _foco_propiedades(self, antes: Any, ahora: Any) -> None:
        """Con la barra inferior, al editar una acción condicionada o por evento se resalta en el dibujo lo que se está editando: su condición (o
        evento), si el foco está en los bloques, o su rectángulo, si está en el resto del panel."""
        e, p = self.edicion, self.props
        if e is None or self.modo_propiedades != "abajo" or ahora is None or p.objetivo_bloques() is None:
            return
        zona = p.zona_de(ahora)
        if zona is None:
            return
        objetivo = p.objetivo_bloques()
        parte = (objetivo[1], objetivo[2] if zona == "bloques" else "accion")
        if e.parte_editada != parte:
            e.parte_editada = parte
            self._redibujar_edicion()

    def _ver_seleccion(self) -> None:
        """Al abrir las Propiedades el dibujo pierde alto: si lo seleccionado queda tapado, se desplaza el dibujo hasta verlo
        (sin tocar el zoom ni la selección)."""
        if self.edicion is None or self.modo != "editar" or not self.diagrama.isVisible():
            return
        caja = self.diagrama._caja_seleccion()
        if caja is not None:
            self.diagrama.ensureVisible(caja, 24, 24)

    def _fijado(self) -> bool:
        return self.props.t_fijar.isChecked()

    def _fijar_cambiado(self, fijo: bool) -> None:
        """«Fijar»: se guarda (arranca abierto solo si está fijado) y fijado ya no se esconde nada."""
        self.ajustes.setValue("paneles/inferior_fijo", fijo)

    def _tras_gesto(self, antes: tuple, despues: tuple) -> None:
        """Pulsar o soltar el ratón en el dibujo (`antes` y `despues`: lo seleccionado y la acción señalada, `Edicion.clave_panel`).
        Con el panel de opciones abierto y sin fijar, un gesto que lo deja vacío o en otro elemento lo esconde al momento, sin
        estados intermedios; sobre el mismo elemento, no. Un panel que no mostraba nada se limita a actualizarse."""
        if (self.modo != "editar" or getattr(self, "solo_lectura", False) or not self._props_abiertas()
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
        if self.flot.activo():  # (las ventanas flotantes no cambian el tamaño del dibujo)
            self._mostrar_panel("inferior", False)
            return
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
        if guardar:  # lo pide el usuario (cabecera, pestaña, atajo, divisor): el modo compacto ya no lo mueve
            self._manual_paneles[nombre] = True
            self._auto_plegados.discard(nombre)
        if nombre == "inferior" and self.flot.activo():  # propiedades flotantes: la barra inferior no se usa; ventanas sobre el dibujo
            accion = self.a_inferior
            if accion.isChecked() != visible:
                accion.blockSignals(True)
                accion.setChecked(visible)
                accion.blockSignals(False)
            if guardar:
                self.ajustes.setValue("paneles/inferior", visible)
            self._plegables["inferior"].hide()
            if not visible and self.edicion is not None:
                self.edicion.parte_editada = None
            self.flot.actualizar()
            return
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        panel = self._plegables[nombre]
        anterior = panel.abierto
        if nombre == "inferior" and not visible and self.edicion is not None and self.edicion.parte_editada is not None:
            self.edicion.parte_editada = None
        if visible and nombre == "inferior":
            self._escala_props()
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
            if visible and nombre == "izquierdo":
                tamano = self.ancho_lateral  # (el izquierdo mide siempre su ancho, aunque con la escala grande pueda estrecharse hasta la base)
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
        if nombre == "inferior":
            self._zoom_diferido()  # (con Propiedades abierto, el zoom va en la cabecera)

    def _minimo_panel(self, nombre):
        if nombre != "inferior":
            return self._ancho_minimo_lateral(nombre)
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
    def _tabla(cols: list[str], anchos: tuple[int | None, ...] | None = None) -> QTableWidget:
        """Tabla de estado del panel derecho. `anchos`: el de cada columna (None: la que se lleva lo que sobra). Texto de 12 px,
        sin barras de desplazamiento propias (`ajustar_tabla` le da el alto de sus filas), el texto largo se parte en dos líneas
        o se elide con «…» y va entero en la ayuda de la celda."""
        t = QTableWidget(0, len(cols))
        t.setHorizontalHeader(CabeceraCompacta(Qt.Orientation.Horizontal, t))  # (pinta el texto de la cabecera sin los márgenes de más de la de Qt)
        t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(estilo.ALTO_FILA)
        t.verticalHeader().setMinimumSectionSize(estilo.ALTO_FILA_COMPACTA)
        t.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)  # elegir una fila pone su texto entero en la barra de estado
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # conserva el final del nombre, que es lo que lo distingue
        t.setWordWrap(True)
        t.setTabKeyNavigation(False)  # el Tab sale de la tabla, no salta de celda en celda
        t.setShowGrid(False)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(f"QTableWidget {{ font-size: {estilo.T_PEQUENA}px; border: 0; }} "
                        f"QTableWidget[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; }} "  # (la hoja propia manda sobre la global: lleva su anillo)
                        f"QHeaderView::section {{ font-size: {estilo.T_PEQUENA}px; font-weight: 400; padding: 4px 0; }} "  # (el texto lo pinta `CabeceraCompacta`, a 4 px: donde empieza el de las celdas)
                        f"QTableWidget::item {{ padding: 0; }}")
        cab = t.horizontalHeader()
        cab.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cab.setStretchLastSection(False)
        cab.setMinimumSectionSize(24)
        cab.setTextElideMode(Qt.TextElideMode.ElideRight)
        for i, ancho in enumerate(anchos or (None,) * len(cols)):
            if ancho is None:
                cab.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                cab.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                cab.resizeSection(i, ancho)
        t.setMinimumHeight(0)
        return t

    @staticmethod
    def ajustar_tabla(t: QTableWidget) -> None:
        """La tabla mide la cabecera más sus filas (con el alto que pide el texto partido): así no necesita barra propia y el
        panel, si hace falta, se desplaza una sola vez."""
        t.resizeRowsToContents()
        alto = t.horizontalHeader().height() + sum(t.rowHeight(r) for r in range(t.rowCount())) + 2 * t.frameWidth() + 4
        if t.height() != alto or t.minimumHeight() != alto:
            t.setFixedHeight(alto)

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
        if self._errores_auto:
            self._marcar_errores(False, False)  # (lo marcó un Play fallido: otra fuente, otro aviso; lo que marcó el usuario se queda)
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
        diags = e.diagnosticos()
        if any(d["blocks"] for d in diags):
            self._armar_avisos(True)  # Play fallido: el aviso aparece desplegado con la lista
            self._no_simulable()
            return False
        if diags:
            self._armar_avisos(False)  # solo avisos que no bloquean: se simula y el aviso queda plegado
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
        for a in (*self.a_herr.values(), self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo, *self._a_errores, self.a_girar_izq, self.a_girar_der):
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
        if self._errores_auto:
            self._marcar_errores(False, False)
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

    def _poner_chip(self, modo: str, texto: str, ayuda: str = "") -> None:
        """El chip de la cabecera del dibujo: el relleno y, sobre todo, el texto dicen en qué modo está el programa (no solo
        el color). Solo toca la hoja de estilo si cambia, porque `refrescar` pasa por aquí en cada tic."""
        if self.estado.text() != texto:
            self.estado.setText(texto)
        hoja = estilo.estilo_chip(modo)
        if self.estado.styleSheet() != hoja:
            self.estado.setStyleSheet(hoja)
        self.estado.setToolTip(ayuda)
        self.estado.setAccessibleName(texto.capitalize())
        self.estado.fijar_marcador("vacio" if modo in ("editar", "lectura") else "lleno")
        self._ajustar_cabecera()  # (el chip pide lo que mide su texto de ahora: el título cede lo que haga falta)

    def _modo_visual(self) -> None:
        """Franja del borde del dibujo y fila de herramientas: verdes al simular, azul tinta al editar (propiedad `modo`)."""
        modo = "simular" if self.modo == "simular" else "editar"
        for w in (getattr(self, "banda_modo", None), getattr(self, "herramientas_grafcet", None),
                  getattr(self, "fila_pestanas", None)):
            if w is not None:
                estilo.poner(w, modo=modo)

    def _fusionar_filas(self, fusionar: bool) -> None:
        """Un cuarto de pantalla: las herramientas (Play, Reiniciar…) suben a la fila de las pestañas, entre ellas y la luz de
        la conexión, y se gana una fila entera de alto para el dibujo."""
        fila = self.herramientas_grafcet
        if fusionar:
            self.fila_pestanas.layout().insertWidget(1, fila)
        else:
            self.centralWidget().layout().insertWidget(1, fila)
        fila.layout().setContentsMargins(0 if fusionar else estilo.E2, estilo.E1, 0 if fusionar else estilo.E2, estilo.E1)
        fila.layout().setSpacing(estilo.E1 if fusionar else estilo.E2)  # en la fila de las pestañas cada píxel cuenta: caben las cuatro barras
        for w in (fila, self.fila_pestanas):
            estilo.poner(w, fusion=fusionar)

    def _poner_modo(self) -> None:
        """Alterna las herramientas sin perder tamaños de edición ni el encuadre manual."""
        self._dibujo_simulado = None
        self._ancho_reloj = 0  # el reloj de la barra de estado vuelve a medir lo que su texto (otro modo, otro texto)
        self.l_reloj.setMinimumWidth(0)
        self._modo_visual()
        self._plegar_laterales_compactos()
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False)
        lateral = self._plegables["derecho"]
        ancho = (lateral.width() if lateral.abierto else self._tamanos_paneles["derecho"]) if getattr(self, "_anchos_puestos", False) else self.ancho_derecho
        guardado = getattr(self, "_paneles_edicion", None)
        if not editar and guardado is None:
            self._paneles_edicion = {"izquierdo": self.a_izquierdo.isChecked(),
                                    "inferior": self.a_inferior.isChecked() and self._fijado(),  # sin fijar, vuelve plegado
                                    "tamanos": self.vsplit.sizes() if self.isVisible() else None}
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
        if not editar:
            self.flot.ocultar()
        if editar:
            self.refrescar_edicion()
        elif self.v is not None:
            self._titulo_ventana()
            if getattr(self,"solo_lectura",False): self.refrescar_edicion()

    def _anchos_laterales(self, ancho: int | None = None) -> None:
        panel = self._plegables["derecho"]
        ancho = max(self.ancho_derecho, panel.width() if ancho is None else ancho) if panel.abierto else panel.GROSOR_PESTANA
        self.derecho.setMinimumWidth(self._ancho_minimo_lateral("derecho"))
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

    def _estilo_aviso_traer(self) -> None:
        """La hoja de la franja «seleccionando para Planos» (con los alto de control de la escala de ahora)."""
        self.aviso_traer.setStyleSheet(
            f'QWidget#avisoSeleccionPlanos {{background:{estilo.AVISO_FONDO}; color:{estilo.TINTA}; border-top:2px solid {estilo.AVISO_BORDE}; border-radius:{estilo.R_S}px;}} '
            'QWidget#avisoSeleccionPlanos QLabel {background:transparent; font-weight:600;} '
            f'QWidget#avisoSeleccionPlanos QPushButton {{background:white; color:{estilo.TINTA}; border:1px solid {estilo.BORDE_CONTROL}; padding:0 14px; border-radius:{estilo.R_S}px; min-height:{estilo.ALTO_CONTROL - 2}px;}} '
            f'QWidget#avisoSeleccionPlanos QPushButton:hover {{background:{estilo.HOVER}; border-color:{estilo.TINTA};}} '
            f'QWidget#avisoSeleccionPlanos QPushButton[tecl=\"true\"]:focus {{border:2px dashed {estilo.FOCO}; padding:0 13px; min-height:{estilo.ALTO_CONTROL - 4}px;}} '
            f'QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja {{background:{estilo.CONFIRMAR}; color:white; border-color:{estilo.CONFIRMAR_BORDE}; font-weight:600;}} '
            f'QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja:hover {{background:{estilo.CONFIRMAR_HOVER};}} '
            'QWidget#avisoSeleccionPlanos QPushButton#confirmarSeleccionHoja[tecl="true"]:focus {border:2px dashed white;}')

    def _estilos_locales(self) -> None:
        """Lo que la ventana escribe a mano con las letras y los alto de control de la escala de ahora (títulos, ayudas, reloj,
        tablas, entradas…): se genera en la construcción y otra vez al cruzar el umbral de pantalla completa."""
        self.titulo.setStyleSheet(f"font-family: {estilo.FAMILIA_TITULO}; font-size: {estilo.T_TITULO}px; font-weight: 700; color: {estilo.TINTA}")
        self.ayuda.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: {estilo.T_PEQUENA}px")
        self.l_ayuda_entradas.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: {estilo.T_PEQUENA}px; font-weight: 400")
        self._estilo_ayuda()
        self.navegacion.escalar()
        self.l_reloj.setStyleSheet(f"font-weight: 600; color: {estilo.TINTA}; font-family: {estilo.FAMILIA_MONO}; font-size: {estilo.T_CIFRA}px")
        self.estado.setFixedHeight(estilo.ALTO_BARRA - 8)
        self.titulo.setMinimumHeight(estilo.ALTO_CONTROL_COMPACTO)
        for b in self.botones.values():
            if isinstance(b, _BotonEntrada):
                b.ajustar_alto()  # (el alto de una línea de la escala de ahora, o el de sus líneas si el nombre va partido)
        hoja = (f"QTableWidget {{ font-size: {estilo.T_PEQUENA}px; border: 0; }} "
                f"QTableWidget[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; }} "
                f"QHeaderView::section {{ font-size: {estilo.T_PEQUENA}px; font-weight: 400; padding: 4px 0; }} "
                f"QTableWidget::item {{ padding: 0; }}")
        for t in (self.t_vars, self.t_temp):
            t.setStyleSheet(hoja)
            t.verticalHeader().setDefaultSectionSize(estilo.ALTO_FILA)
            t.verticalHeader().setMinimumSectionSize(estilo.ALTO_FILA_COMPACTA)
        for reparto in self._reparto:  # (con la letra de ahora, las columnas se miden otra vez)
            reparto.aplicar()

    @staticmethod
    def _medidas_tabla() -> tuple[QFontMetrics, QFontMetrics, Any]:
        """La letra de las celdas de estado, la de las cifras y lo que mide una cabecera (su texto, a 4 px del borde, más 2 px de holgura)."""
        fm = QFontMetrics(estilo.fuente(estilo.T_PEQUENA))
        return fm, QFontMetrics(estilo.fuente(estilo.T_CIFRA, mono=True)), lambda texto: fm.horizontalAdvance(texto) + 6

    def _planes_vars(self) -> list[dict[str, Any]]:
        """Los repartos de «Salidas y variables», de más a menos completo (el nombre manda: ver `ReparteColumnas`): todo entero; «Modo» abreviado
        («cont.», «mem.»); y, por último, la cabecera «Contrib.». **Ninguna columna se esconde** (P13 rechazada)."""
        fm, cifras, cab = self._medidas_tabla()
        valor = max(cab("Valor"), cifras.horizontalAdvance("False") + 8)  # (una memoria booleana sin salida enseña «False»: que no se corte)
        contribuyen, corta = cab("Contribuyen"), cab("Contrib.")
        modo_corto = max(cab("Modo"), fm.horizontalAdvance("cont.") + 7, fm.horizontalAdvance("mem.") + 7)
        modo = max(cab("Modo"), fm.horizontalAdvance("continua") + 7, fm.horizontalAdvance("memoria") + 7)
        return [{"anchos": {1: modo, 2: valor, 3: contribuyen}, "modo_corto": False},
                {"anchos": {1: modo_corto, 2: valor, 3: contribuyen}, "modo_corto": True},
                {"anchos": {1: modo_corto, 2: valor, 3: corta}, "modo_corto": True},
                # el más apretado (panel de 218 px con barra vertical): sin barra a los lados, con el nombre en unos 90 px
                {"anchos": {1: max(cab("Modo") - 2, fm.horizontalAdvance("mem.") + 5), 2: max(cifras.horizontalAdvance("False") + 4, cab("Valor") - 2),
                            3: fm.horizontalAdvance("Contr.") + 3}, "modo_corto": True, "apretado": True}]

    def _elegir_plan_vars(self, plan: dict[str, Any]) -> None:
        self.t_vars.itemDelegateForColumn(1).corto = plan["modo_corto"]

    def _planes_temp(self) -> list[dict[str, Any]]:
        """Los repartos de «Temporizadores» (P-IMP-30: dónde, estado, lleva, preset): «Estado» entero («parado», «contando», «vencido») o
        abreviado («par.», «cont.», «venc.», con su color) y, por último, la cabecera «Est.». **Ninguna columna se esconde.**"""
        fm, cifras, cab = self._medidas_tabla()
        tiempo = cifras.horizontalAdvance("12,5 s") + 8
        lleva, preset = max(cab("Lleva"), tiempo), max(cab("Preset"), tiempo)
        estado = max(cab("Estado"), fm.horizontalAdvance("contando") + 7)
        corto = max(cab("Est."), *(fm.horizontalAdvance(t) + 7 for t in ("par.", "cont.", "venc.")))
        return [{"anchos": {1: estado, 2: lleva, 3: preset}, "corto": False},
                {"anchos": {1: max(cab("Estado"), corto), 2: lleva, 3: preset}, "corto": True},
                {"anchos": {1: corto, 2: lleva, 3: preset}, "corto": True},
                {"anchos": {1: corto, 2: max(cab("Lleva") - 2, cifras.horizontalAdvance("0,0 s") + 4), 3: max(cab("Preset") - 2, cifras.horizontalAdvance("0,0 s") + 4)},
                 "corto": True, "apretado": True}]

    def _elegir_plan_temp(self, plan: dict[str, Any]) -> None:
        self.t_temp.itemDelegateForColumn(1).corto = plan["corto"]

    def _escala_de_la_ventana(self) -> None:
        """La escala que pide el tamaño de ahora. Con la ventana a la vista, el cambio no se hace en cada `resizeEvent`: una animación
        de Windows (Aero Snap) o arrastrar el borde mandan varios seguidos, y reaplicar la hoja de estilo en cada uno hacía «bailar» el
        dibujo. Se espera a que se calmen (`ESPERA_ESCALA` ms sin nuevos cambios de tamaño) y se aplica **una sola vez**, con el tamaño
        final; mientras tanto se conserva la escala anterior. Antes de mostrarse la ventana, en el primer instante tras mostrarse (hasta que se maximiza, sin que se vea el salto) y al terminar la
        espera, se aplica al momento."""
        deseada = estilo.escala_para(self.width(), self.height(), self._escala)
        if not self.isVisible() or self._escala_lista or self._arrancando:
            self._espera_escala.stop()
            self._aplicar_escala(deseada)
        elif deseada == self._escala:
            self._espera_escala.stop()  # (la ráfaga ha vuelto a la escala de ahora: no hay nada que cambiar)
        else:
            self._espera_escala.start(ESPERA_ESCALA)  # (se reinicia con cada evento de la ráfaga)

    def _escala_tras_la_rafaga(self) -> None:
        self._escala_lista = True
        try:
            self._adaptar_tamano()
        finally:
            self._escala_lista = False

    def _aplicar_escala(self, nombre: str) -> None:
        """Al cruzar el umbral de pantalla completa (`estilo.UMBRAL_GRANDE`) o volver por debajo: la letra base pasa de 13 a 14 px,
        los títulos, el chip y las cifras crecen y los controles miden 40 px; por debajo de ese tamaño, lo de siempre. Solo se
        repite al cruzar el umbral (la hoja entera tarda cerca de un segundo en aplicarse). Los menús conservan su aspecto."""
        if nombre == self._escala:
            return
        # (sin `setUpdatesEnabled(False)` aquí: no ahorraba nada y dejaba sin repintar, para siempre, a los hijos que se ponen en
        # `updatesEnabled` = falso por dentro, como la paleta de Elementos, que se quedaba vacía al cruzar el umbral)
        self._cambiar_escala(nombre)

    def _cambiar_escala(self, nombre: str) -> None:
        self._escala = nombre
        self._alto_cabecera = 0
        self._ancho_forzado = 0  # (la letra cambia: `_vigilar_barra` vuelve a medir si «Reiniciar» cabe con texto)
        estilo.activar_escala(nombre)
        self._hoja_escala = estilo.hoja_global() if nombre == "grande" else ""
        for destino in self._destinos_hoja:  # (solo lo que cambia: la hoja de la ventana no se toca)
            destino.setStyleSheet(self._hoja_escala)
        self._planos_pendiente = True  # PLANOS (oculta casi siempre, ≈ 10 ms) se pone al día cuando se muestra
        if self.paginas_es.currentIndex() == 2:
            self._escala_planos()
        self._es_pendiente = self._props_pendiente = True  # E/S y Propiedades se ponen al día cuando se muestran
        if self.paginas_es.currentIndex() == 1:
            self._escala_es()
        if self._plegables["inferior"].abierto:
            self._escala_props()
        self._poner_ancho_lateral(self._ancho_lateral_para(self.width()), self._ancho_derecho_para(self.width()))  # (por si el ancho no cambió pero la letra sí)
        self._estilos_locales()
        self._ancho_reloj = 0  # el reloj vuelve a medir lo que su texto (otra letra, otro ancho)
        self.l_reloj.setMinimumWidth(0)
        if self.l_reloj.text():
            self._poner_reloj(self.l_reloj.text())
        self.diagrama.escalar()
        self.variables.escalar()
        self.panel_planos.escalar()
        self.diagrama.parentWidget().layout().invalidate()
        self._estilo_aviso_traer()
        if self.modo == "simular" and self.v is not None:
            self.refrescar()
        else:
            self.refrescar_edicion()
        self._fijar_ancho_boton_play()
        self.tb_sim.layout().invalidate()
        QTimer.singleShot(0, self, self._remedir_barra_simulacion)
        # La hoja nueva cambia lo que miden los controles, y Qt reparte las cajas en la vuelta siguiente del bucle de eventos: hasta
        # entonces el dibujo se veía en un sitio y, al repartirse, saltaba unos píxeles («flotando»). Se reparten aquí, en este pintado.
        QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)

    def _ancho_lateral_para(self, ancho_ventana: int) -> int:
        """Los paneles laterales ganan ancho con la letra grande (así las tablas de la simulación llevan sus cuatro columnas con las
        cabeceras enteras), pero **poco a poco**: de los 218 px que fijan las pruebas de la paleta a 1366 de ancho, hasta los 264 px de la
        pantalla completa a 1600 (y 300 px a 1920×1080, donde sobra sitio). Así, al cruzar el umbral de 1600×900 el dibujo no da un salto
        de casi 100 px de ancho."""
        t = min(1.0, max(0.0, (ancho_ventana - 1366) / (estilo.UMBRAL_GRANDE[0] - 1366)))
        mas = min(1.0, max(0.0, (ancho_ventana - estilo.UMBRAL_GRANDE[0]) / 320))  # y de 264 a 300 px entre 1600 y 1920: con la letra grande las
        return self._ancho_lateral_base + round(46 * t) + round(36 * mas)           # tablas de estado llevan sus cuatro columnas enteras

    def _ancho_minimo_lateral(self, nombre: str) -> int:
        """Lo que mide, como poco, un panel lateral. Con la escala normal es su ancho; con la grande (donde los paneles son más anchos) solo la base:
        así el mínimo de la ventana es el de siempre y bajar de 1920 a 683 o 640 px de ancho cabe **en una sola petición** (F6: antes se quedaba en
        769 hasta que los paneles se estrechaban)."""
        nominal = self.ancho_derecho if nombre == "derecho" else self.ancho_lateral
        return min(nominal, self._ancho_lateral_base) if self._escala == "grande" else nominal

    def _fijar_dock(self, ancho: int) -> None:
        """El panel izquierdo mide `ancho` (fijo); con la escala grande puede estrecharse hasta la base (ver `_ancho_minimo_lateral`)."""
        self.dock.setMinimumWidth(self._ancho_minimo_lateral("izquierdo"))
        self.dock.setMaximumWidth(ancho)

    def _ancho_derecho_para(self, ancho_ventana: int) -> int:
        """El panel derecho (Variables, o las tablas de la simulación, que conserva el ancho al pulsar Play) mide `ANCHO_DERECHO` desde
        `UMBRAL_DERECHO` px de ancho de ventana: con él «Papel» y «Tipo» salen enteros y las tablas de estado llevan sus cuatro columnas
        (P10). Por debajo, el de siempre; a pantalla completa, lo que ya hacía la rama (`_ancho_lateral_para`) si es más."""
        base = self._ancho_lateral_para(ancho_ventana)
        return max(base, ANCHO_DERECHO) if ancho_ventana >= UMBRAL_DERECHO else base

    def _poner_ancho_lateral(self, nuevo: int, derecho: int | None = None) -> None:
        """Pone el ancho de los dos paneles laterales (`nuevo` el del izquierdo y, sin `derecho`, el del derecho también; el del divisor
        también: si no, queda un hueco muerto a su lado). Lo que el usuario ensanchó a mano no se toca."""
        derecho = nuevo if derecho is None else derecho
        if nuevo == self.ancho_lateral and derecho == self.ancho_derecho:
            return
        viejo, self.ancho_lateral = self.ancho_lateral, nuevo
        viejo_d, self.ancho_derecho = self.ancho_derecho, derecho
        self.variables.fijar_ancho_nominal(derecho)  # (con él se decide si «Papel» y «Tipo» van en palabras o abreviados)
        self._fijar_dock(nuevo)
        for n, antes, ahora in (("izquierdo", viejo, nuevo), ("derecho", viejo_d, derecho)):
            if self._tamanos_paneles[n] == antes:
                self._tamanos_paneles[n] = ahora
            self._plegables[n].mostrar(self._plegables[n].abierto)
        izq = self._plegables["izquierdo"]
        if izq.abierto and not izq.isHidden():
            total = sum(self.split_izquierdo.sizes())
            self.split_izquierdo.setSizes([nuevo, max(100, total - nuevo)])
        self.derecho.setMinimumWidth(self._ancho_minimo_lateral("derecho"))
        der = self._plegables["derecho"]
        self._anchos_laterales(derecho if der.abierto and (der.width() == viejo_d or not self._derecho_a_mano) else None)

    def _escala_planos(self) -> None:
        """PLANOS lleva la hoja de la escala de ahora; se hace al mostrarla (cruzar el umbral no repasa una página que no se ve)."""
        if self._planos_pendiente:
            self._planos_pendiente = False
            self.panel_planos.setStyleSheet(self._hoja_escala)

    def _escala_es(self) -> None:
        """La vista de E/S lleva la escala de ahora (hoja, letra y alto de fila). Se hace al mostrarla: son más de mil widgets."""
        if self._es_pendiente:
            self._es_pendiente = False
            self.panel_es.escalar(self._hoja_escala, self._escala)

    def _escala_props(self) -> None:
        """Propiedades lleva la escala de ahora (campos, «Fijar», categorías y fichas). Se hace al abrirlo."""
        if self._props_pendiente:
            self._props_pendiente = False
            self.props.escalar(self._hoja_escala)

    def _zoom_diferido(self) -> None:
        if not self._zoom_pendiente:
            self._zoom_pendiente = True
            QTimer.singleShot(0, self, self._ajustar_zoom)

    def _props_alto(self, mantener: bool) -> bool:
        """¿Está abierto el panel de Propiedades con su panel alto (al editar)? La receptividad de una transición pide ≈ 340 px y deja el dibujo
        en la mitad del alto de la ventana a cualquier tamaño; el panel de una etapa (≈ 180 px) deja el dibujo alto. Con histéresis: seguir
        integrado pide algo menos que integrarse."""
        return (self.modo == "editar" and not self.inferior.isHidden()
                and self.inferior.height() >= estilo.ALTO_PROPS_ZOOM - (40 if mantener else 0))

    def _ajustar_zoom(self) -> None:
        """Los controles del zoom flotan arriba a la derecha del dibujo, salvo en una ventana estrecha o baja (siempre van en la cabecera) y
        cuando el dibujo útil queda bajo: **con Propiedades abierto y su panel alto, a cualquier tamaño de ventana** (1366, 1440, 1920…: el
        dibujo se queda en la mitad del alto y el recuadro dejaría de flotar sobre la zona por la que el dibujo se desplaza para enseñar lo
        elegido), o con un dibujo de menos de `ALTO_DIBUJO_ZOOM`: entonces se integran en la fila del título y el chip. Con el panel bajo de
        una etapa el dibujo sigue alto y el recuadro flota como siempre (y, al esconder el panel, el dibujo no salta). En la cabecera se
        compacta a solo iconos y el porcentaje cuando faltan palabras de sitio (`_ajustar_cabecera`). Con histéresis, para que integrar
        la barra (que sube un poco la cabecera) no la haga volver."""
        self._zoom_pendiente = False
        d = self.diagrama
        sp = self._cab.spacing()
        # (el chip, un título mínimo y el zoom con solo iconos tienen que caber en la cabecera; si no —los paneles laterales aún abiertos en una
        # ventana de media pantalla, un instante antes de plegarse—, el recuadro flota sobre el dibujo y nunca pisa al chip)
        nav = self.navegacion.sizeHint().width() + sp if self.navegacion.isVisibleTo(self) else 0  # (el buscador abierto también pide su sitio en la fila)
        cabe = d.parentWidget().width() - 2 * estilo.E2 >= self.estado.minimumSizeHint().width() + self.titulo.fontMetrics().horizontalAdvance("0" * 10) + d.ancho_barra(True) + nav + 3 * sp  # (el título conserva ~10 caracteres: si no, el zoom se queda sobre el dibujo)
        # La zona de edición está fija: el zoom va **siempre** en la cabecera (con palabras si caben y solo iconos si no), a cualquier tamaño y con
        # Propiedades cerrado o abierto; solo flota si ni los iconos caben en la fila (a ese tamaño, siempre). La fila mide siempre lo mismo
        # (lo que el recuadro del zoom), así que el dibujo empieza siempre a la misma altura y el aviso de simulación detenida no se mueve.
        d.integrar_barra(self._cab if cabe else None)
        # (la fila mide lo del recuadro más alto que ha tenido —al editar y al simular lleva controles distintos—, flotando con 2 px menos de margen)
        self._alto_cabecera = max(getattr(self, "_alto_cabecera", 0), estilo.ALTO_CONTROL_COMPACTO, d.barra.sizeHint().height() - (0 if d.barra_integrada else 4))
        self.titulo.setMinimumHeight(self._alto_cabecera)
        self._ajustar_cabecera()

    def _adaptar_tamano(self) -> None:
        """Modo compacto automático, sin que el usuario toque nada: por debajo de `estilo.UMBRAL_ANCHO` (pantalla partida) el
        panel de Variables se pliega solo al editar, y por debajo de `estilo.UMBRAL_ALTO` (un cuarto de pantalla) los márgenes se
        estrechan y las herramientas suben a la fila de las pestañas. Lo que el usuario plegó o desplegó a mano se respeta, y al
        agrandar la ventana vuelve lo que se plegó solo. No se cambia la hoja de estilo (aplicarla a toda la ventana tarda cerca
        de un segundo): los controles miden lo mismo a todos los tamaños."""
        self._escala_de_la_ventana()
        self._poner_ancho_lateral(self._ancho_lateral_para(self.width()), self._ancho_derecho_para(self.width()))
        nuevo = estilo.tamano_compacto(self.width(), self.height())
        if nuevo != self._compacto:
            bajo_antes = self._compacto[1]
            self._compacto = nuevo
            ancho, alto = nuevo
            if alto != bajo_antes:
                self._fusionar_filas(alto)
                self.props.prog.modo_fila(alto)  # P1: la paleta de operadores en una fila (el panel pide ≈ 190 px y no 334)
            il = self.diagrama.parentWidget().layout()
            il.setContentsMargins(*((estilo.E2, estilo.E1 + HUECO_FRANJA, estilo.E2, estilo.E1) if alto else self._margenes_dibujo))
            self._reflujo_entradas()
            self._densidad_lateral()
            self.diagrama.compactar(ancho, alto)
            self._ajustar_zoom()  # los controles del zoom, en la cabecera (en estrecho o bajo, y con poco dibujo)
            self.panel_planos.compactar(ancho or alto)
        self._repartir_textos_barra()
        self._ajustar_cabecera()  # (el chip de modo pide hasta el 55 % del ancho, y deja al título unos 10 caracteres: el título cede antes que el estado)
        muy = self.width() < max(estilo.UMBRAL_MUY_ESTRECHO, self._ancho_forzado)
        if muy != self._muy_estrecho:  # media pantalla: la fila de arriba tiene que caber en 640 px
            self._muy_estrecho = muy
            self.tb_sim.widgetForAction(self.a_reiniciar).setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonIconOnly if muy else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.tb_sim.layout().invalidate()  # (la barra guarda lo que medían sus botones: sin esto «Reiniciar» se queda en el desbordamiento)
            self.tb_sim.updateGeometry()
            self.tb_sim.setMinimumWidth(0)
            QTimer.singleShot(0, self, self._remedir_barra_simulacion)
            estilo.poner(self.pestanas_vistas, estrecha=muy)
            for i in (0, 1):  # QTabBar guarda el tamaño de sus pestañas: cambiar el texto lo obliga a medirlas otra vez
                texto = self.pestanas_vistas.tabText(i)
                self.pestanas_vistas.setTabText(i, texto + " ")
                self.pestanas_vistas.setTabText(i, texto)
            self._luz_es(*self._ultima_luz)
        self._plegar_laterales_compactos()

    def _ajustar_cabecera(self) -> None:
        """Reparte la cabecera del dibujo. Manda el estado (el chip no cede) y, con él, el título del grafcet (cede hasta 24 px, pero antes que
        la ayuda); el zoom integrado lleva sus palabras solo si caben junto a un título y una ayuda útiles y, si no, solo iconos y el
        porcentaje. La ayuda de debajo del título se lee en dos líneas; si no caben, acaba en «…» con un botón visible («más ▾») que la
        despliega entera en su propia fila; con muy poco sitio se queda en el botón («Ayuda ▾») y, sin sitio ni para él, se esconde:
        es lo secundario y nunca se corta a media frase sin dar salida."""
        cab = self._cab
        d = self.diagrama
        sp = cab.spacing()
        ancho = d.parentWidget().width() - 2 * estilo.E2
        # F8: el título conserva al menos unos 10 caracteres antes de que el chip pase a su variante más corta (el estado nunca se pierde: la más
        # corta es solo el estado); lo que ocupan los demás controles (navegación y zoom, este con solo iconos) se descuenta del tope del chip
        otros = (self.navegacion.sizeHint().width() + sp if self.navegacion.isVisibleTo(self) else 0)             + (d.ancho_barra(True) + sp if d.barra_integrada else 0)
        minimo_titulo = self.titulo.fontMetrics().horizontalAdvance("0" * 10) + sp
        self.estado.fijar_tope(max(min(int(self.width() * 0.55), ancho - otros - minimo_titulo - 2 * sp), 60))
        usado = 0
        for w in (self.estado, self.navegacion):
            if w.isVisibleTo(self):
                usado += w.sizeHint().width() + sp
        if d.barra_integrada:  # el zoom, con sus palabras si caben junto al título y la ayuda y, si no, solo con iconos y el porcentaje
            para_zoom = ancho - usado - ANCHO_TITULO_UTIL - ANCHO_AYUDA_UTIL - 3 * sp
            d.solo_iconos(para_zoom < d.ancho_barra(False) + (40 if d._solo_iconos else 0))
            usado += d.barra.sizeHint().width() + sp
        texto = self.ayuda.text()
        if texto != getattr(self, "_texto_ayuda", None):  # otra ayuda: la desplegada se recoge (la misma de siempre, como al simular, no)
            self._texto_ayuda, self._ayuda_abierta = texto, False
        libre = max(24, ancho - usado - 2 * sp)  # para el título, la ayuda y su botón
        natural = self.titulo.sizeHint().width()
        boton = QFontMetrics(estilo.fuente(estilo.T_PEQUENA, negrita=True)).horizontalAdvance("Ayuda ▾") + 12 + 2 + sp
        abierta = self._ayuda_abierta and bool(texto)
        # El texto habitual de ayuda va siempre detrás del botón «Ayuda ▾» (a todos los tamaños); solo un mensaje de error (en rojo) se lee
        # en la fila mientras cabe, porque no se puede esconder lo que dice que algo ha fallado
        error = bool(texto) and estilo.ERROR in self.ayuda.styleSheet()
        letra = "Ayuda ▴" if abierta else "Ayuda ▾"
        if abierta or not error:
            titulo_max, hay_ayuda, letrero = min(natural, max(24, minimo_titulo, libre - boton)), False, letra
            if not texto:
                titulo_max, letrero = min(natural, libre), ""
        elif libre >= natural + ANCHO_AYUDA_UTIL and not self.ayuda.truncada(libre - natural):
            titulo_max, hay_ayuda, letrero = natural, True, ""  # el mensaje cabe en sus dos líneas
        elif libre - boton >= natural + ANCHO_AYUDA_UTIL:
            titulo_max, hay_ayuda, letrero = natural, True, "más ▾"  # no cabe entero: dos líneas que acaban en «…» y el botón
        elif libre - boton >= max(24, minimo_titulo):
            titulo_max, hay_ayuda, letrero = min(natural, libre - boton), False, "Ayuda ▾"
        else:
            titulo_max, hay_ayuda, letrero = min(natural, libre), False, ""  # ni el botón cabe: se esconde lo secundario
        if self.titulo.maximumWidth() != titulo_max:
            self.titulo.setMaximumWidth(titulo_max)
        self.ayuda.mostrar_texto = hay_ayuda
        self.ayuda.update()
        if letrero:
            if self.b_ayuda.text() != letrero:
                self.b_ayuda.setText(letrero)
                self.b_ayuda.setToolTip("Recoger la ayuda" if abierta else "Leer la ayuda entera")
        if self.b_ayuda.isVisibleTo(self) != bool(letrero):
            self.b_ayuda.setVisible(bool(letrero))
        if abierta and self.ayuda_larga.text() != texto:
            self.ayuda_larga.setText(texto)
        if self.ayuda_larga.isVisibleTo(self) != abierta:
            self.ayuda_larga.setVisible(abierta)

    def _alternar_ayuda(self) -> None:
        """«más ▾» / «Ayuda ▾» / «Ayuda ▴»: despliega la ayuda entera bajo la cabecera, o la recoge."""
        self._ayuda_abierta = not self._ayuda_abierta
        self._ajustar_cabecera()

    def _estilo_ayuda(self) -> None:
        """La hoja del botón «más ▾» de la ayuda y la de su fila desplegada (con la letra y el alto de control de la escala de ahora)."""
        alto = estilo.ALTO_CONTROL_COMPACTO
        self.b_ayuda.setFixedHeight(alto)
        self.b_ayuda.setStyleSheet(
            f"QToolButton#masAyuda {{ color: {estilo.ACENTO}; font-size: {estilo.T_PEQUENA}px; font-weight: 600; padding: 0 4px; min-height: {alto - 2}px; }} "
            f"QToolButton#masAyuda:hover {{ background: {estilo.ACENTO_SUAVE}; }} "
            f"QToolButton#masAyuda[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; padding: 0 3px; min-height: {alto - 4}px; }}")
        self.ayuda_larga.setStyleSheet(
            f"QLabel#ayudaLarga {{ color: {estilo.TINTA}; background: {estilo.SUPERFICIE_2}; border: 1px solid {estilo.BORDE}; "
            f"border-radius: {estilo.R_S}px; padding: 6px 10px; font-size: {estilo.T_PEQUENA}px; }}")

    def _detallar(self, texto: str) -> None:
        """La línea de detalle de la barra de estado: el nombre entero de lo que tiene el foco o está elegido (vacía, se esconde)."""
        if self.l_detalle.text() != texto:
            self.l_detalle.setText(texto)
        self.l_detalle.setVisible(bool(texto))

    @staticmethod
    def _detalle_entrada(b: _BotonEntrada) -> str:
        return f"{b.nombre_completo()} = {b.text().rpartition(' = ')[2]} · entrada"

    @staticmethod
    def _detalle_fila(tabla: QTableWidget, fila: int) -> str:
        if not 0 <= fila < tabla.rowCount():
            return ""
        partes = (str(tabla.item(fila, c).data(Qt.ItemDataRole.UserRole) or tabla.item(fila, c).text())
                  for c in range(tabla.columnCount()) if tabla.item(fila, c) is not None)
        return " · ".join(p for p in partes if p)  # (un campo vacío no deja un « · » colgando al final)

    def _sobre_entrada(self, b: _BotonEntrada, dentro: bool) -> None:
        """El puntero entra en una entrada de la simulación o sale de ella: la línea de detalle dice su nombre entero."""
        self._bajo_raton = b if dentro else (None if self._bajo_raton is b else self._bajo_raton)
        self._detalle_del_foco()

    def _sobre_fila(self, tabla: QTableWidget | None, fila: int) -> None:
        """El puntero está sobre una fila de las tablas de estado (o fuera de ellas: `fila` < 0)."""
        self._bajo_raton = (tabla, fila) if tabla is not None and fila >= 0 else None
        self._detalle_del_foco()

    def _detalle_del_foco(self, *_args: Any) -> None:
        """La línea de detalle de la barra de estado dice el nombre entero de lo que se señala o se ha elegido, sin teclado y sin esperar a la
        ayuda emergente: lo que tiene el puntero encima (una entrada de la simulación, una fila de las tablas de estado) y, si no hay
        puntero encima, lo que tiene el foco (una entrada, la fila elegida de una tabla, la de variables). Sin nada de eso, se esconde."""
        f = QApplication.focusWidget()
        texto = ""
        try:
            r = self._bajo_raton
            if isinstance(r, _BotonEntrada):
                texto = self._detalle_entrada(r)
            elif isinstance(r, tuple):
                texto = self._detalle_fila(*r)
            elif isinstance(f, _BotonEntrada):
                texto = self._detalle_entrada(f)
            elif isinstance(f, QTableWidget) and f in (self.t_vars, self.t_temp):
                texto = self._detalle_fila(f, f.currentRow())
            elif f is self.variables.tabla and self.variables.tabla.currentRow() >= 0:
                self.variables._detallar(self.variables.tabla.currentRow())
                return
        except RuntimeError:  # la entrada o la tabla ya no existen (se rehicieron)
            self._bajo_raton = None
        self._detallar(texto)

    def _poner_reloj(self, texto: str) -> None:
        """El texto del reloj de la barra de estado («τ = 12,5 s · próximo vencimiento: 15 s»). Crece con el tiempo y la barra de
        estado reparte su ancho una vez por cambio: el reloj se queda con el ancho de lo más largo que ha escrito, para que
        no pierda ningún carácter (ni «1 s» en «próximo vencimiento: 3 s») ni la barra se mueva en cada tic."""
        if self.l_reloj.text() != texto:
            self.l_reloj.setText(texto)
        self.l_reloj.ensurePolished()  # (con la letra de su hoja de estilo, no la de la plataforma)
        ancho = self.l_reloj.fontMetrics().horizontalAdvance(texto) + 2 * self.l_reloj.margin() + 8
        if ancho > self._ancho_reloj:
            self._ancho_reloj = ancho
            self.l_reloj.setMinimumWidth(ancho)
            self.statusBar().updateGeometry()

    def _vigilar_barra(self) -> None:
        """Red de seguridad, a cualquier ancho: si la barra de Play no cabe con «Reiniciar» y su texto (o este queda fuera de ella),
        «Reiniciar» pasa a solo icono con su ayuda, y sigue así mientras la ventana no sea más ancha que cuando no cabía."""
        if self._muy_estrecho or not self.isVisible():
            return
        barra, boton = self.tb_sim, self.tb_sim.widgetForAction(self.a_reiniciar)
        fuera = boton is not None and boton.isVisibleTo(barra) and boton.geometry().right() > barra.width()
        if fuera or barra.width() < barra.sizeHint().width() - 1:
            self._ancho_forzado = self.width() + 1
            self._adaptar_tamano()

    def _remedir_barra_simulacion(self) -> None:
        """Tras cambiar «Reiniciar» a solo icono, la barra de Play pide lo que mide ahora y su fila se vuelve a repartir."""
        for objeto in (self.tb_sim, self.herramientas_grafcet, self.fila_pestanas):
            lay = objeto.layout()
            if lay is not None:
                lay.invalidate()
                lay.activate()
        self.tb_sim.resize(self.tb_sim.sizeHint().width(), self.tb_sim.height())

    def _ancho_barra_edicion(self, con_texto: bool) -> int:
        """Lo que pide la barra de edición con las palabras de sus botones o solo con iconos (se mide una vez por escala)."""
        cache = self.__dict__.setdefault("_anchos_edicion", {})
        clave = (con_texto, estilo.ESCALA)
        if clave not in cache:
            self._textos_en_barras(con_texto)
            self.tb_edit.layout().invalidate()
            self.tb_edit.layout().activate()
            cache[clave] = self.tb_edit.sizeHint().width()
        return cache[clave]

    def _repartir_textos_barra(self) -> None:
        """B2: las palabras de «Añadir debajo», «Mostrar dependencias» y «Mostrar errores» solo van si la fila de herramientas las aguanta junto a la
        barra de Play (si no, solo icono con su ayuda: se oculta antes el texto que el botón). En pantalla partida, siempre solo icono."""
        ancho, alto = self._compacto
        con = False
        if not ancho:
            libre = (self.herramientas_grafcet.width() if self.herramientas_grafcet.isVisible() else self.width()) - 4 * estilo.E2
            con = alto or self._ancho_barra_edicion(True) + self.tb_sim.sizeHint().width() <= libre
        antes = getattr(self, "_texto_en_barra", None)
        self._texto_en_barra = con
        self._textos_en_barras(con)
        if antes is not None and antes != con:
            self.tb_edit.layout().invalidate()
            self.tb_edit.updateGeometry()

    def _textos_en_barras(self, con_texto: bool) -> None:
        """«Añadir debajo» y «Mostrar dependencias» llevan texto cuando hay sitio y solo icono (con su ayuda) en pantalla partida; el resto
        de botones de la barra de edición son siempre de solo icono."""
        forma = Qt.ToolButtonStyle.ToolButtonTextBesideIcon if con_texto else Qt.ToolButtonStyle.ToolButtonIconOnly
        for a in (self.a_debajo, self.a_dependencias, self.a_errores):
            w = self.tb_edit.widgetForAction(a)
            if w is not None:
                w.setToolButtonStyle(forma)
        self.diagrama.b_dependencias.setToolButtonStyle(forma)

    def _configurar_foco(self) -> None:
        """Los botones se alcanzan con Tab y no toman el foco con el ratón (así el anillo solo sale al navegar con teclado); el
        orden va de arriba abajo y de izquierda a derecha, y al arrancar el foco está en el dibujo."""
        for b in self.findChildren(QAbstractButton):
            if not b.isCheckable() and b.focusPolicy() in (Qt.FocusPolicy.StrongFocus, Qt.FocusPolicy.NoFocus):
                b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        for tabla in self.findChildren(QTableWidget):
            tabla.setTabKeyNavigation(False)
        play = self.tb_sim.widgetForAction(self.a_ejecutar)
        if play is not None:
            play.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # (es un botón de dos estados: el bucle de arriba lo salta)
        for zona in self.findChildren(QScrollArea):  # una zona de desplazamiento no es una parada de Tab: sus controles sí
            if zona.focusPolicy() == Qt.FocusPolicy.StrongFocus:
                zona.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._orden_tab()

    def _orden_tab(self) -> None:
        d = self.diagrama
        entradas = list(getattr(self, "botones", {}).values())
        cadena = [self.pestanas_vistas, self.luz_es, self.tb_sim.widgetForAction(self.a_ejecutar),
                  self.tb_sim.widgetForAction(self.a_reiniciar),
                  *(self.tb_edit.widgetForAction(a) for a in (*self._acciones_solo_icono, self.a_debajo)), d.b_dependencias, self.b_errores,
                  self.flechas["izquierdo"], self.paleta, d, self.b_ayuda, d.b_menos, d.b_mas, d.b_ajustar, d.b_seleccion,
                  self.flechas["derecho"], *entradas, self.variables.tabla, *self.variables.b_nuevas.values(),
                  self.variables.b_quitar, self.pestanas["izquierdo"], self.pestanas["derecho"], self.flechas["inferior"],
                  self.pestanas["inferior"], self.props.t_fijar]
        cadena = [w for w in cadena if w is not None]
        for a, b in zip(cadena, cadena[1:]):
            QWidget.setTabOrder(a, b)

    def _plegar_laterales_compactos(self) -> None:
        estrecho = self._compacto[0]
        panel = self._plegables["derecho"]
        editar = self.modo == "editar" and self.edicion is not None and not getattr(self, "solo_lectura", False)
        if estrecho and editar and panel.abierto and not self._manual_paneles.get("derecho"):
            self._mostrar_panel("derecho", False, guardar=False)
            self._auto_plegados.add("derecho")
        elif "derecho" in self._auto_plegados and not (estrecho and editar):
            self._auto_plegados.discard("derecho")
            self._mostrar_panel("derecho", True, guardar=False)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.isVisible():
            self._adaptar_tamano()
            QTimer.singleShot(0, self, self._vigilar_barra)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if not getattr(self, "_play_medido", False):
            self._play_medido = True
            self._fijar_ancho_boton_play()  # (ya con la hoja de estilo aplicada: la letra del botón es la que se ve)
        if not self._arranque_hecho:
            self._arranque_hecho = self._arrancando = True
            QTimer.singleShot(ESPERA_ARRANQUE, self, lambda: setattr(self, "_arrancando", False))
        self._escala_tras_la_rafaga()  # (al mostrarse, la escala del tamaño de ahora y sin esperas)
        if not self._foco_inicial:  # al arrancar, el foco va al dibujo (sin anillo: no llegó con Tab)
            self._foco_inicial = True
            self.diagrama.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.modo == "editar" and self.edicion is not None and not getattr(self,"solo_lectura",False) and not getattr(self, "_anchos_puestos", False):
            self._anchos_puestos = True  # con la ventana ya dimensionada, los dos paneles laterales con el mismo ancho
            self._anchos_laterales(self.ancho_derecho)
            self._alto_inferior(True)

    def _alternar_errores(self, on: bool) -> None:
        """El usuario marca o desmarca «Mostrar errores»: el aviso de la cabecera del dibujo se ve y se actualiza en vivo, o no se ve al editar."""
        self._errores_auto = False
        self.diagrama.diagnosticos_abiertos = on  # (al marcar, la lista sale desplegada; «N errores ▾» la pliega; al desmarcar y volver a marcar, otra vez desplegada)
        self.refrescar_edicion()

    def _marcar_errores(self, on: bool, auto: bool) -> None:
        """Marca o desmarca «Mostrar errores» sin pasar por el gesto del usuario (`auto`: lo hace un Play fallido, y se desmarca solo)."""
        self.b_errores.blockSignals(True)
        self.b_errores.setChecked(on)
        self.b_errores.blockSignals(False)
        self._errores_auto = on and auto

    def _armar_avisos(self, abrir: bool) -> None:
        """Un Play que no simula (errores que lo impiden) o que para por un diagnóstico marca «Mostrar errores» y despliega el aviso con su lista
        (`abrir`); con solo avisos que no bloquean, lo marca y el aviso queda plegado. Si el botón ya lo había marcado el usuario, sigue siendo suyo."""
        if not self.b_errores.isChecked():
            self._marcar_errores(True, True)
        if abrir:
            self.diagrama.diagnosticos_abiertos = True
        if self.modo == "editar":
            self.refrescar_edicion()

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
        if getattr(self, "solo_lectura", False):
            self._poner_chip("lectura", "EJEMPLO · SOLO LECTURA", "Ejemplo de solo lectura: se puede simular; para editar, abra un proyecto o cree uno nuevo")
        else:
            self._poner_chip("editar", "EDICIÓN", "Modo edición: Play inicia la simulación")
        self.titulo.setText(f"{e.titulo}{' *' if e.ed.dirty else ''}")
        self.ayuda.setToolTip(self._ayuda if getattr(self,"solo_lectura",False) else AYUDA_EDICION[e.herramienta])
        mensaje, info = e.texto_estado()
        self.ayuda.setText(self._ayuda if getattr(self,"solo_lectura",False) else mensaje or "Arrastre fichas desde la paleta; doble clic en un elemento para ver sus propiedades.")
        error = bool(mensaje) and not info  # un aviso informativo no va en rojo
        self.ayuda.setStyleSheet(f"color: {estilo.ERROR if error else estilo.TINTA_2}; font-weight: {600 if error else 400}; "
                                 f"font-size: {estilo.T_PEQUENA}px")
        # (la barra de estado sigue al texto de ahora: se retira cuando el mensaje que puso esta vista ya no es el vigente, no a los 9 s)
        barra, puesto = self.statusBar(), getattr(self, "_texto_estado_edicion", "")
        if mensaje:
            barra.showMessage(mensaje, 9000)
        elif puesto and barra.currentMessage() == puesto:
            barra.clearMessage()
        self._texto_estado_edicion = mensaje
        self.l_herr.setText(f"<b>{NOMBRE_HERRAMIENTA[e.herramienta]}</b>: {html.escape(AYUDA_EDICION[e.herramienta])}")
        sel = [e.nombre(i) for i in e.sel]
        self.l_sel.setText(("Selección: " + ", ".join(sel)) if sel else "Nada seleccionado.")
        self._poner_reloj(f"{len(e.M['steps'])} etapas · {len(e.M['transitions'])} transiciones")
        self.a_herr[e.herramienta].setChecked(True)
        if self.flot.activo():
            self.flot.actualizar()
        else:
            self.props.mostrar(e)
            objetivo = self.props.objetivo_bloques()
            if e.parte_editada is not None and (objetivo is None or objetivo[1] != e.parte_editada[0]):
                e.parte_editada = None  # (ya no se edita esa acción)
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
        errores, avisos = len(bloq) + (1 if self._avisos_ejecucion else 0), len(diags) - len(bloq)
        partes = [f"{n} {'error' if n == 1 else 'errores'}" for n in (errores,) if n] + [f"{n} {'aviso' if n == 1 else 'avisos'}" for n in (avisos,) if n]
        resumen = " · ".join(([ "Simulación detenida"] if self._avisos_ejecucion else []) + partes)
        if not hay_detalle and self._errores_auto and self.b_errores.isChecked():
            self._marcar_errores(False, False)  # lo marcó un Play fallido y ya no queda nada: se desmarca solo
        if self.b_errores.isChecked():
            self.diagrama.actualizar_diagnosticos(True, resumen if hay_detalle else "", vacio=not hay_detalle)
        else:
            self.diagrama.actualizar_diagnosticos(False)
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
        if self._props_abiertas():
            self.props_activo().s_etiqueta.setFocus()
            self.props_activo().s_etiqueta.selectAll()

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
            self.aviso.setVisible(True)
            return
        if self.v is None:
            return
        try:
            self.v.act(op, body)
            self.aviso.setText("")
            self.aviso.setVisible(False)
        except ERRORES as exc:
            self.aviso.setText(f"No disponible: {exc}")
            self.aviso.setVisible(True)
        self.refrescar()

    def _entradas(self) -> None:
        while self.rejilla.count():
            w = self.rejilla.takeAt(0).widget()
            if w is not None:
                w.hide()  # hasta que se borre, no se ve (si no, asoma tras los nuevos al cambiar la disposición)
                w.setParent(None)
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
            b.sobre.connect(lambda on, b=b: self._sobre_entrada(b, on))
            self.rejilla.addWidget(b, fila, 0, 1, 4)
            self.botones[var] = b
            fila += 1
        self._bajo_raton = None  # (los botones de antes se borran)
        contexto = ContextoNombres([self.nombre(v) for v, b in self.botones.items() if isinstance(b, _BotonEntrada)])
        for b in self.botones.values():
            if isinstance(b, _BotonEntrada):
                b.contexto = contexto
        if not self.v.model["inputs"]:
            self.rejilla.addWidget(QLabel("Sin entradas"), 0, 0)
        self._reflujo_entradas()
        self._densidad_lateral()
        QTimer.singleShot(0, self, self._reflujo_entradas)  # (otra vez con la hoja de estilo ya aplicada: la letra puede medir distinto)
        if hasattr(self, "pestanas") and hasattr(self, "props"):
            self._orden_tab()

    def _reflujo_entradas(self) -> None:
        """Con poca altura (un cuarto de pantalla) las entradas booleanas van de dos en dos: así caben también las tablas."""
        botones = [self.rejilla.itemAt(i).widget() for i in range(self.rejilla.count())]
        if not botones or not all(isinstance(b, _BotonEntrada) for b in botones):
            return
        por_fila = 2 if self._compacto[1] else 1
        if por_fila == 2:  # de dos en dos solo si los nombres caben enteros en media fila (si no, uno por fila y la tabla se desplaza)
            mitad = (self.ancho_derecho - 2 * estilo.E1 - estilo.ANCHO_BARRA - estilo.E1) // 2
            if any(b.ancho_natural(f"{self.nombre(v)} = 0") > mitad for v, b in self.botones.items() if isinstance(b, _BotonEntrada)):
                por_fila = 1
        for b in botones:
            self.rejilla.removeWidget(b)
        for i, b in enumerate(botones):
            self.rejilla.addWidget(b, i // por_fila, (i % por_fila) * (4 // por_fila), 1, 4 // por_fila)
        self._alto_entradas()

    def _densidad_lateral(self) -> None:
        """En un cuarto de pantalla el panel de simulación gana alto (títulos de caja 4 px más bajos y sin margen inferior) para que se
        vea también la fila de temporizadores sin desplazarse."""
        bajo = self._compacto[1]
        for caja in getattr(self, "_cajas_lado", []):
            caja.setStyleSheet(f"QGroupBox {{ margin-top: {estilo.E1 * 5}px; }}" if bajo else "")
            caja.layout().setContentsMargins(0, ARRIBA_CAJA, 0, 0 if bajo else estilo.E1)

    @staticmethod
    def _ayuda_entrada(b: _BotonEntrada) -> None:
        b.ayuda_base = (("NC: reposo 1, accionado 0 · " if b.nc else "NA: reposo 0, accionado 1 · ") + ("Interruptor: clic para conmutar · Botón derecho: cambiar tipo" if b.interruptor else
                     "Pulsador momentáneo: presionar invierte el reposo, soltar lo restaura · Ctrl+clic: enclavar mientras se mantiene Ctrl (otro clic libera) · Botón derecho: cambiar tipo"))
        b.setToolTip(b.ayuda_base)

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
        self.a_ejecutar.setIcon(_icono_barra("stop" if on else "play", estilo.BLANCO))
        self._centrar_play(on)

    def _centrar_play(self, on: bool) -> None:
        """El botón mide siempre lo del más ancho de sus dos estados y su contenido (icono y texto) se pinta pegado a la izquierda: lo que sobra en el
        estado más corto se reparte como relleno a los dos lados, para que quede centrado (con foco también: allí el borde es dos puntos más grueso)."""
        boton = self.tb_sim.widgetForAction(self.a_ejecutar) if hasattr(self, "tb_sim") else None
        relleno = getattr(self, "_relleno_play", {}).get(on)
        if boton is None or relleno is None:
            return
        izq, der = relleno
        boton.setStyleSheet(f"QToolButton#botonPlay {{ padding: 0 {der}px 0 {izq}px; }}"
                            f"QToolButton#botonPlay[tecl=\"true\"]:focus {{ padding: 0 {max(0, der - 2)}px 0 {max(0, izq - 2)}px; }}")

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
        if motivos:
            self._armar_avisos(True)
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
        self._escala_es()
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
        if destino == 1:
            self._escala_es()
        if destino==2:
            self._escala_planos()
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
        if hasattr(self,"herramientas_grafcet"):self.herramientas_grafcet.setVisible(indice==0 and not pendiente)
        planos=self.paginas_es.currentIndex()==2
        self.a_planos.blockSignals(True);self.a_planos.setChecked(planos);self.a_planos.blockSignals(False)
        self.a_planos.setToolTip("Volver al GRAFCET" if planos else "Editar planos, plantillas y cajetín")
        self.a_ejecutar.setEnabled(not(es or planos or pendiente));self.a_reiniciar.setEnabled(not(es or planos or pendiente))
        editar=self.modo=="editar" and not planos and not pendiente and not getattr(self,"solo_lectura",False)
        for a in (*self.a_herr.values(),self.a_debajo,*getattr(self,"_a_errores",()),self.a_girar_izq,self.a_girar_der):a.setEnabled(editar)
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
        """El botón de Play mide lo del más ancho de sus dos estados (Play, Stop) y su contenido va centrado en los dos (`_centrar_play`). El ancho sale
        de medir cada estado sin relleno extra."""
        boton = self.tb_sim.widgetForAction(self.a_ejecutar)
        inicial = self.a_ejecutar.isChecked()
        self._relleno_play = {}
        boton.setStyleSheet("")
        contenido = {}
        for on in (False, True):
            self._marcar_play(on)
            contenido[on] = boton.sizeHint().width() - 2 - 2 * 16  # (el contenido: sin el borde ni el relleno de la hoja global)
        ancho = max(max(contenido.values()) + 2 * 16 + 2, 92)
        self._relleno_play = {on: ((ancho - 2 - c) // 2, ancho - 2 - c - (ancho - 2 - c) // 2) for on, c in contenido.items()}
        boton.setFixedWidth(ancho)
        boton.resize(ancho, boton.height())
        if boton.isVisible():  # lo que se ve (el icono y las letras tienen márgenes propios): se afina para que la tinta quede centrada
            habilitada = self.a_ejecutar.isEnabled()
            self.a_ejecutar.setEnabled(True)
            for on in (False, True):
                self._marcar_play(on)
                img = boton.grab().toImage()
                blancos = [x for x in range(img.width()) if any(min(c.red(), c.green(), c.blue()) > 200 for c in (img.pixelColor(x, y) for y in range(img.height())))]
                if blancos:
                    mover = ((img.width() - 1 - blancos[-1]) - blancos[0]) // 2  # (lo que sobra a la derecha menos lo de la izquierda: hacia la derecha si es positivo)
                    izq, der = self._relleno_play[on]
                    self._relleno_play[on] = (max(0, izq + mover), max(0, der - mover))
            self.a_ejecutar.setEnabled(habilitada)
        self._marcar_play(inicial)

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
            # el estado del motor se dice con las mismas palabras de siempre (estable, en recorrido…), en mayúsculas
            self._poner_chip({"err": "error", "virt": "aviso"}.get(color, "simular"), f"SIMULACIÓN · {label.upper()}",
                             f"Simulación en curso, {label}. Stop detiene y vuelve a editar")
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
            estilo.poner(b, activa=on)  # relleno y borde de la hoja global; además, el icono (punto) y el «= 1» del texto
            if b.hasFocus() or self._bajo_raton is b:
                self._detalle_del_foco()  # (el «= 1» de la línea de detalle sigue al valor)
        if simulando:
            self._poner_reloj(f"τ = {t_trunc(S['timeUs']) if 'timeUs' in S else '—'}"
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
        self._filas(self.t_vars, rows, cifras=(2,))
        self._del_vars[0].fijar(self._textos_columna(self.t_vars, 0))
        self._del_vars[1].fijar(self._textos_columna(self.t_vars, 3))
        self._reparto[0].aplicar()  # (con los nombres de ahora: el reparto busca que quepan en dos líneas)
        temp = S.get("temporal") or {}
        self.c_temp.setVisible(bool(temp))
        self._filas(self.t_temp, [(t["where"], t["estado"], t["lleva"], t["preset"],
                                   "readout" if t["estado"] == "contando" else "ok" if t["estado"] == "vencido" else "muted")
                                  for t in temp.values()], 1, cifras=(2, 3))
        self._del_temp.fijar(self._textos_columna(self.t_temp, 0))
        self._reparto[1].aplicar()
        self.ajustar_tabla(self.t_vars)
        self.ajustar_tabla(self.t_temp)
        self._alto_entradas()

    def _alto_tabla_variables(self) -> None:
        """F10: la tabla de Variables mide, como mucho, lo que deja el panel (menos lo demás de la página): así se desplaza ella y no la
        página (antes, en un cuarto de pantalla, había dos barras verticales una al lado de otra)."""
        pagina, caja, tabla = self._pag_scroll, self._caja_vars, self.variables.tabla
        alto = pagina.height() - 2 * pagina.frameWidth()
        if alto <= 0 or not caja.isVisibleTo(pagina):
            return
        resto = caja.y() + (caja.height() - tabla.height()) + estilo.E2  # (lo de arriba, lo del marco de la caja, el botón y el margen de abajo)
        self.variables.fijar_alto_maximo(alto - resto)

    def _alto_entradas(self) -> None:
        """F2: la caja «Entradas» mide lo que sus botones, salvo que así no dejara ver, bajo ella, al menos cuatro filas (o todas, si hay
        menos) de «Salidas y variables»: entonces se desplaza por dentro, con ese alto máximo."""
        sc = self.sc_entradas
        vista = self.scroll.height() - 2 * self.scroll.frameWidth()  # (sin descontar la barra horizontal, que aparece y desaparece según el alto: oscilaría)
        if vista <= 0 or getattr(self, "_ajustando_entradas", False):
            return
        self._ajustando_entradas = True
        try:
            self._poner_alto_entradas(sc, vista)
        finally:
            self._ajustando_entradas = False

    def _poner_alto_entradas(self, sc: QScrollArea, vista: int) -> None:
        self.ajustar_tabla(self.t_vars)  # (con sus filas al día: el alto de la tabla y el de sus filas han de concordar)
        self.ajustar_tabla(self.t_temp)
        lay = self.cont_rejilla.layout()
        ancho_ref = self.scroll.width() - 2 * self.scroll.frameWidth()  # (el del panel sin su barra: con ella oscilaría; no se mide el visor)
        natural = max(lay.totalHeightForWidth(max(ancho_ref - 2 * estilo.E1, 60)), lay.sizeHint().height())
        t = self.t_vars
        visibles = min(t.rowCount(), 4)
        de_las_filas = (t.horizontalHeader().height() + sum(t.rowHeight(r) for r in range(visibles)) + 2 * t.frameWidth() + 4) if t.rowCount() else t.height()
        # «lo demás» del panel: el alto de las cajas «Entradas» (sin el desplazable) y «Salidas y variables» (con solo las filas que se han de ver),
        # el aviso de diagnóstico si se ve y los márgenes, calculado a un ancho de referencia (no de la geometría repartida, que llega tarde, ni
        # de lo que pide el diseño con una barra a un lado: las dos hacían oscilar el alto)
        ancho_caja = ancho_ref - 2 * estilo.E1
        entradas, salidas = self._cajas_lado[0], self._cajas_lado[1]

        def alto_caja(caja: QGroupBox) -> int:
            m, lay_caja = caja.contentsMargins(), caja.layout()
            dentro = lay_caja.totalHeightForWidth(ancho_caja - m.left() - m.right()) if lay_caja.hasHeightForWidth() else lay_caja.totalSizeHint().height()
            return m.top() + m.bottom() + dentro
        cajas = [alto_caja(entradas) - sc.height(), alto_caja(salidas) - (t.height() - de_las_filas)]
        if self.diag.isVisibleTo(self):
            cajas.insert(0, self.diag.heightForWidth(ancho_caja))
        resto = sum(cajas) + (len(cajas) - 1) * self.lado.spacing() + 2 * estilo.E1
        tope = max(vista - resto, 3 * estilo.ALTO_CONTROL_COMPACTO)  # (nunca menos de unos tres botones)
        alto = min(natural, tope)
        sc.setFixedHeight(alto)

    @staticmethod
    def _textos_columna(t: QTableWidget, c: int) -> list[str]:
        """Los textos enteros de una columna (los nombres que `DelegadoNombres` ha de poder distinguir)."""
        return [t.item(r, c).text() for r in range(t.rowCount()) if t.item(r, c) is not None]

    @staticmethod
    def _filas(t: QTableWidget, rows: list[tuple[str, ...]], col_color: int = 2, cifras: tuple[int, ...] = ()) -> None:
        """Rellena la tabla (el texto de cada celda es el entero; `cifras` son las columnas que van en la letra técnica)."""
        t.setRowCount(len(rows))
        for i, (*cells, color) in enumerate(rows):
            for j, c in enumerate(cells):
                item = t.item(i, j)
                if item is None:
                    item = QTableWidgetItem(c)
                    if j in cifras:
                        item.setFont(estilo.fuente(estilo.T_CIFRA, mono=True))  # las cifras (valor, tiempo, preset) en la letra técnica
                    item.setData(Qt.ItemDataRole.UserRole, c)
                    item.setToolTip(c)  # el texto entero, aunque la celda lo recorte
                    t.setItem(i, j, item)
                elif item.data(Qt.ItemDataRole.UserRole) != c:
                    item.setText(c)
                    item.setData(Qt.ItemDataRole.UserRole, c)
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
            self._poner_chip("aviso", "SELECCIONANDO · para Planos", "Seleccionando elementos para añadirlos a una hoja de PLANOS")
            self.ayuda.setText('Clic: cadena completa · Mayús+clic: añadir otra cadena · Ctrl+clic: añadir o quitar un elemento. Sin jerarquías inferiores automáticas.')
        if activo==getattr(self,'_seleccionando_hoja',False):return
        self._seleccionando_hoja=activo
        if activo:
            from .hojas import SeleccionParaHoja
            self._paneles_traer={n:p.abierto for n,p in self._plegables.items()}
            self._tamanos_traer=(self.split_izquierdo.sizes(),self.split.sizes(),self.vsplit.sizes())
            for n in self._paneles_traer:
                self._plegables[n].hide();self.flechas[n].hide();self.pestanas[n].hide()
            self.diagrama.controlador=SeleccionParaHoja(self.edicion);self.diagrama.setAcceptDrops(False)
            self._estilo_traer=self.diagrama.styleSheet();self.diagrama.setStyleSheet(self._estilo_traer+' QGraphicsView {border:2px solid '+estilo.AVISO_BORDE+'; background:'+estilo.AVISO_FONDO+';}')
            self._poner_chip("aviso", "SELECCIONANDO · para Planos", "Seleccionando elementos para añadirlos a una hoja de PLANOS")
            self.ayuda.setText('Clic: cadena completa · Mayús+clic: añadir otra cadena · Ctrl+clic: añadir o quitar un elemento. Sin jerarquías inferiores automáticas.')
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
        self._ultima_luz = (estado, mensaje)
        texto = {"conectado": "conectada", "error": "error", "diagnostico": "error"}.get(estado, "desconectada")
        # la luz no depende solo del color: círculo con marca (conectada), círculo vacío (desconectada) o rombo con «!» (error)
        self.luz_es.setIcon(QIcon(estilo.forma_luz(texto)))
        self.luz_es.setIconSize(QSize(14, 14))
        self.luz_es.setText(f"{'E/S' if getattr(self, '_muy_estrecho', False) else 'E/S externas'}: {texto}")  # media pantalla: una palabra menos
        self.luz_es.setToolTip((mensaje + "\n" if mensaje else "") + "Abrir E/S externas")
        self.luz_es.setAccessibleName(f"E/S externas: {texto}")
        estilo.poner(self.luz_es, estadoLuz=texto)

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
            self._avisar_version_nueva(r)  # al arrancar y a mano, el mismo diálogo (no se guarda nada al descartarlo)
        elif manual:
            texto = ("Ya tiene la última versión de GRAFCET Connect." if r.estado == "al_dia" else
                     "No se ha podido comprobar: sin conexión o sin respuesta del servidor.")
            QMessageBox.information(self, TITULO, texto)

    def _avisar_version_nueva(self, r: actualizaciones.Resultado, intentos: int = 40) -> None:
        """Abre el diálogo de versión nueva sobre la ventana, ya visible; si aún no lo está (el arranque), espera un poco."""
        if self._dialogo_version is not None and self._dialogo_version.isVisible():
            return
        if not self.isVisible():
            if intentos > 0:
                QTimer.singleShot(250, self, lambda: self._avisar_version_nueva(r, intentos - 1))
            return
        self._version_nueva = r
        self._dialogo_version = DialogoVersionNueva(self, APP_VERSION, r.version, r.url, ICONO_PROGRAMA)
        self._dialogo_version.open()  # (no bloquea: es modal solo para esta ventana)


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
    if args.captura:
        w.show()  # (la captura de comprobación conserva el tamaño de siempre)
    else:
        # La aplicación arranca siempre maximizada; al restaurar, la ventana se comporta como siempre. En Windows el
        # sistema muestra un instante la ventana con su tamaño normal antes de maximizarla (el «amago» de ventana
        # pequeña): se abre transparente y se hace opaca cuando ya está maximizada.
        w.setWindowOpacity(0.0)
        w.showMaximized()
        QTimer.singleShot(0, w, lambda: w.setWindowOpacity(1.0))
    if (not args.captura and not os.environ.get(actualizaciones.VARIABLE_SIN_ACTUALIZAR)
            and actualizaciones.al_arrancar_activo(w.ajustes)):
        QTimer.singleShot(1500, w.buscar_actualizaciones)  # con la ventana ya a la vista; en un hilo, sin bloquear
    if args.captura:
        QTimer.singleShot(300, lambda: (w.grab().save(args.captura), app.quit()))
    return app.exec()
