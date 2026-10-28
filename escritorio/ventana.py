"""Ventana del simulador GRAFCET de escritorio (P-IMP-29, P-IMP-30): primera versión portable para Windows.

Simula un ejemplo o un modelo guardado (proyecto o documento de modelo, documento 09) con el dibujo de la
norma. Entradas, tiempo real (como un autómata: los retardos son temporizadores que cuentan solos), evolución a
evolución, traza, salidas, variables, temporizadores y, en «Ajustes», las lecturas de interpretación. Toda la
semántica la decide grafcet/engine.py con el perfil provisional: la ventana no aproxima nada y los bloqueos por
cuestiones U se muestran tal cual. No es el editor ni declara conformidad con IEC 60848 / UNE-EN 60848.
"""
from __future__ import annotations

import copy
import html
import re
import shutil
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QElapsedTimer, QSettings, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDockWidget, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QScrollArea, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget)

from grafcet.diagnostics import DiagnosticError
from grafcet.examples import EJEMPLOS
from grafcet.persistence import Recovery, add_document, new_project, open_model, save_project
from grafcet.profile import APP_VERSION, SEMANTIC_OPTIONS, normalize_options
from grafcet.timeutil import parse_duration
from grafcet.view import Vista, auto_layout, layout_from_presentation, presentation_for, t_trunc

from .diagrama import COL, VistaDiagrama, imagen
from .edicion import HERRAMIENTAS, Edicion
from .propiedades import PanelPropiedades, Paleta, PaletaAcciones
from .variables import PanelVariables

TITULO = "Simulador GRAFCET"
ANCHO_LATERAL = 212  # ancho mínimo de los paneles laterales al editar (la tabla de variables enseña los nombres)
ALTO_INFERIOR = {"simular": 300, "editar": 380}  # altura inicial del panel inferior: la traza, o las opciones de lo seleccionado
TICK_MS = 100  # tiempo real: cada cuánto se avanza el tiempo lógico
AYUDA_EDICION = {
    "seleccionar": "Clic selecciona un elemento y muestra sus opciones abajo; arrastrarlo lo mueve (a la "
                   "rejilla, y no encima de otro elemento); de un punto de unión (arriba o abajo de una etapa o transición, "
                   "a la derecha de una etapa) sale un enlace. Supr borra; Ctrl+Z y Ctrl+Y deshacen y rehacen. Los "
                   "elementos y las acciones nuevos se arrastran desde las carpetas de la izquierda.",
}
NOMBRE_HERRAMIENTA = {"seleccionar": "Seleccionar"}
AVISO = "Núcleo con perfil provisional · no declara conformidad con IEC 60848 / UNE-EN 60848"
ESTADOS = {"pausada-estable": ("estable", "ok"), "pausada-recorrido": ("en recorrido (situación inestable)", "virt"),
           "error": ("detenido por diagnóstico", "err"), "no-compilable": ("no compilable", "err"),
           "finalizada": ("finalizada", "ok"), "preparada": ("preparada", "muted"), "ejecutando": ("ejecutando", "muted")}
TRAZA = {"fallo": "err", "evolucion": "accent", "contexto": "muted"}
ERRORES = (DiagnosticError, RuntimeError, ValueError, KeyError)
LEYENDA = (
    "<b>Etapa activa</b>: marca ● y fondo azul. <b>Etapa inestable</b> (activa durante un tiempo nulo: sus acciones "
    "memorizadas se ejecutan, las continuas no producen salida): borde morado discontinuo; «fue inestable» marca las "
    "del último instante.<br><b>Transición</b>: gris = no validada, negra = validada, azul = franqueable, naranja = "
    "recién franqueada.<br><b>Tras un bloqueo</b>: gris punteado = último estado estable conservado (no es el "
    "resultado); naranja discontinuo = alcanzada antes del punto en cuestión, sin confirmar; trazo rojo = transición "
    "en cuestión.<br><b>Acciones</b>: ↑ al activar, ↓ al desactivar, banderita = por evento, trazo con texto = "
    "condición; marco verde = salida a 1.<br><b>Jerarquía</b>: macroetapa = divisiones horizontales arriba y abajo, "
    "unida a su expansión (de E a S) por trazos discontinuos; encapsulante = esquinas cortadas; recinto = marco con "
    "la encapsulante arriba y su nombre abajo; * = enlace de activación; G{…} en rectángulo doble = orden de forzado "
    "(morada si está vigente; {*} situación actual, {INIT} inicial, { } vacía); marco redondeado = parcial.<br>"
    "<br><b>Temporizadores</b>: junto a la receptividad o la acción con retardo, «1,2 s / 3 s» mientras cuenta (lo "
    "que lleva / su preset) y «3 s ✓» cuando ha vencido.<br>"
    "Pase el ratón por una etapa o transición para ver su estado. La rueda acerca o aleja; doble clic ajusta.")


def _q_key(q: str) -> list[Any]:
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"[.-]", q)]  # números antes que letras


class Lecturas(QDialog):
    """Todas las lecturas de interpretación (SEMANTIC_OPTIONS): la decidida por el responsable va primero."""

    def __init__(self, parent: QWidget, options: dict[str, str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lecturas de interpretación")
        self.resize(760, 560)
        lay = QVBoxLayout(self)
        note = QLabel("Cada cuestión tiene la lectura decidida por el responsable. Elegir otra no implica conformidad; "
                      "se avisa en la barra de estado, se registra en la traza y cambiarla reinicia la simulación.")
        note.setWordWrap(True)
        lay.addWidget(note)
        form_host = QWidget()
        form = QFormLayout(form_host)
        self.combos: dict[str, QComboBox] = {}
        self.fijas: dict[str, str] = {}  # cuestiones sin decidir: no se eligen, el motor se detiene con su diagnóstico
        for q in sorted(SEMANTIC_OPTIONS, key=_q_key):
            spec = SEMANTIC_OPTIONS[q]
            label = QLabel(f"<b>{html.escape(q)}</b> · {html.escape(spec['scope'])}")
            label.setWordWrap(True)
            if spec["default"] == "detener":
                fija = QLabel("Sin decidir: se detiene")
                fija.setStyleSheet(f"color: {COL['muted']}")
                form.addRow(label, fija)
                self.fijas[q] = "detener"
                continue
            cb = QComboBox()
            for value, text in spec["values"].items():
                if value != "detener":  # «detener» es lo que hace el motor con lo abierto: no se ofrece como lectura
                    cb.addItem(("Por defecto · " if value == spec["default"] else "") + text, value)
            cb.setCurrentIndex(max(0, cb.findData(options.get(q, spec["default"]))))
            cb.setToolTip(spec["scope"])
            form.addRow(label, cb)
            self.combos[q] = cb
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_host)
        lay.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText("Volver a las decididas")
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._defaults)
        lay.addWidget(buttons)

    def _defaults(self) -> None:
        for q, cb in self.combos.items():
            cb.setCurrentIndex(cb.findData(SEMANTIC_OPTIONS[q]["default"]))

    def options(self) -> dict[str, str]:
        return {**self.fijas, **{q: cb.currentData() for q, cb in self.combos.items()}}


class Ventana(QMainWindow):
    def __init__(self, ajustes: QSettings | None = None, recuperacion: Path | None = None) -> None:
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
        self.rt.setInterval(TICK_MS)
        self.rt.timeout.connect(self._tick)
        self.reloj = QElapsedTimer()
        self.edicion: Edicion | None = None
        self._alturas = dict(ALTO_INFERIOR)
        self.modo = "simular"
        # Recuperación automática cada 30 s mientras hay cambios sin guardar (REQ-EDT-10)
        self.recup = Recovery(recuperacion or Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation)))
        self.t_auto = QTimer(self)
        self.t_auto.setInterval(30_000)
        self.t_auto.timeout.connect(self.autoguardar)
        self.t_auto.start()
        self._menus()
        self._interfaz()
        self._barra_herramientas()
        self._paneles()
        self.cargar_ejemplo(next(iter(EJEMPLOS)))

    # -- construcción ---------------------------------------------------------------------------
    def _accion(self, texto: str, slot: Any, atajo: str | list[str] | None = None, marcable: bool = False) -> QAction:
        a = QAction(texto, self)
        a.setCheckable(marcable)
        if atajo:
            a.setShortcuts([QKeySequence(x) for x in ([atajo] if isinstance(atajo, str) else atajo)])
        (a.toggled if marcable else a.triggered).connect(slot)
        return a

    def _menus(self) -> None:
        bar = self.menuBar()
        archivo = bar.addMenu("&Archivo")
        archivo.addAction(self._accion("&Nuevo grafcet", self.nuevo, "Ctrl+N"))
        a = archivo.addAction("&Abrir modelo…", self.abrir)
        a.setShortcut(QKeySequence.StandardKey.Open)
        self.a_guardar = archivo.addAction("&Guardar proyecto…", self.guardar)
        self.a_guardar.setShortcut(QKeySequence.StandardKey.Save)
        archivo.addAction("Guardar el &dibujo como imagen…", self.guardar_imagen)
        archivo.addSeparator()
        archivo.addAction("&Salir", self.close).setShortcut(QKeySequence.StandardKey.Quit)
        ejemplos = bar.addMenu("&Ejemplos")
        self.grupo = QActionGroup(self)
        self.acciones_ej: dict[str, QAction] = {}
        for key, (title, _, _) in EJEMPLOS.items():
            act = ejemplos.addAction(title)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, k=key: self.cargar_ejemplo(k))
            self.grupo.addAction(act)
            self.acciones_ej[key] = act
        # Acciones de la simulación: también van en la barra de herramientas
        self.a_ejecutar = self._accion("▶ Ejecutar", self._ejecutar, "F5", marcable=True)
        self.a_ejecutar.setToolTip("Ejecutar / pausar el tiempo real (F5)")
        self.a_paso = self._accion("Paso", self.paso_evolucion, "F10")
        self.a_paso.setToolTip("Una evolución; con la situación estable, hasta el próximo vencimiento (F10)")
        self.a_completar = self._accion("Completar recorrido", lambda: self._act("estabilizar"), "F11")
        self.a_completar.setToolTip("Terminar las evoluciones pendientes hasta la situación estable (F11)")
        self.a_reiniciar = self._accion("Reiniciar", self.reiniciar, "Ctrl+R")
        self.a_reiniciar.setToolTip("Reiniciar la simulación (Ctrl+R)")
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
        ver.addAction(self._accion("A&justar el dibujo", lambda: self.diagrama.ajustar(), "Ctrl+0"))
        # Modo y edición
        self.a_editar = self._accion("Editar", lambda on: on and self.cambiar_modo("editar"), "Ctrl+1", True)
        self.a_simular = self._accion("Simular", lambda on: on and self.cambiar_modo("simular"), "Ctrl+2", True)
        self.a_editar.setToolTip("Editar el grafcet (Ctrl+1)")
        self.a_simular.setToolTip("Simular el grafcet; si no compila, se muestran los diagnósticos (Ctrl+2)")
        self.g_modo = QActionGroup(self)
        for a in (self.a_editar, self.a_simular):
            self.g_modo.addAction(a)
        self.a_simular.blockSignals(True)
        self.a_simular.setChecked(True)
        self.a_simular.blockSignals(False)
        self.a_herr: dict[str, QAction] = {}
        self.g_herr = QActionGroup(self)
        for h in HERRAMIENTAS:  # solo las que no colocan elementos: los elementos y las acciones se arrastran desde la paleta
            atajo = "Esc"
            a = self._accion("Seleccionar (Esc)", lambda on, h=h: on and self.herramienta(h), atajo, True)
            a.setToolTip(f"{NOMBRE_HERRAMIENTA[h]} ({atajo}): {AYUDA_EDICION[h]}")
            self.g_herr.addAction(a)
            self.a_herr[h] = a
        self.a_herr["seleccionar"].blockSignals(True)
        self.a_herr["seleccionar"].setChecked(True)
        self.a_herr["seleccionar"].blockSignals(False)
        self.a_deshacer = self._accion("&Deshacer", lambda: self.edicion and self.edicion.deshacer(), "Ctrl+Z")
        self.a_rehacer = self._accion("&Rehacer", lambda: self.edicion and self.edicion.rehacer(), ["Ctrl+Y", "Ctrl+Shift+Z"])
        self.a_borrar = self._accion("&Borrar la selección", lambda: self.edicion and self.edicion.borrar(), "Del")
        self.a_debajo = self._accion("&Añadir debajo", lambda: self.edicion and self.edicion.anadir_debajo(), "Ctrl+Return")
        self.a_debajo.setToolTip("Con una etapa seleccionada: transición y etapa enlazadas debajo (Ctrl+Intro)")
        edicion = bar.addMenu("&Edición")
        for a in (self.a_editar, self.a_simular):
            edicion.addAction(a)
        edicion.addSeparator()
        for a in (self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo):
            edicion.addAction(a)
        edicion.addSeparator()
        for a in self.a_herr.values():
            edicion.addAction(a)
        sim = bar.addMenu("&Simulación")
        for a in (self.a_ejecutar, self.a_paso, self.a_completar, self.a_reiniciar):
            sim.addAction(a)
        sim.addSeparator()
        sim.addAction("&Avanzar el tiempo…", self.avanzar_tiempo).setToolTip("Herramienta de depuración")
        m_ajustes = bar.addMenu("A&justes")
        m_ajustes.addAction("&Lecturas de interpretación…", self.lecturas)
        ayuda = bar.addMenu("A&yuda")
        ayuda.addAction("&Leyenda del dibujo", self.leyenda)
        ayuda.addAction("&Acerca de", self.acerca)

    def _caja(self, titulo: str) -> tuple[QGroupBox, QVBoxLayout]:
        box = QGroupBox(titulo)
        lay = QVBoxLayout(box)
        self.lado.addWidget(box)
        return box, lay

    def _interfaz(self) -> None:
        izq = QWidget()
        il = QVBoxLayout(izq)
        cab = QHBoxLayout()
        self.estado = QLabel()
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-size: 15px; font-weight: 600")
        cab.addWidget(self.estado)
        cab.addWidget(self.titulo, 1)
        il.addLayout(cab)
        self.ayuda = QLabel()
        self.ayuda.setWordWrap(True)
        self.ayuda.setStyleSheet(f"color: {COL['muted']}")
        il.addWidget(self.ayuda)
        self.diagrama = VistaDiagrama()
        il.addWidget(self.diagrama, 1)
        # Panel inferior: al simular, la traza; al editar, las opciones de lo seleccionado
        self.traza = QListWidget()
        self.traza.setWordWrap(True)
        caja_traza = QGroupBox("Traza")
        QVBoxLayout(caja_traza).addWidget(self.traza)
        self.props = PanelPropiedades()
        self.inferior = QStackedWidget()
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
        self.paso = QCheckBox("Paso a paso (detener tras cada evolución)")
        lay.addWidget(self.paso)

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
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Página de edición: la herramienta, la selección y los diagnósticos (REQ-EDT-09)
        pag = QWidget()
        pl = QVBoxLayout(pag)
        pl.setContentsMargins(2, 2, 2, 2)  # el panel es estrecho: poco marco, para que quepa la tabla de variables
        self.l_herr = QLabel()
        self.l_herr.setWordWrap(True)
        self.l_herr.setTextFormat(Qt.TextFormat.RichText)
        self.l_herr.hide()  # la misma ayuda ya va sobre el dibujo; aquí no cabe en un panel estrecho (sigue en el objeto)
        pl.addWidget(self.l_herr)
        self.l_sel = QLabel()
        self.l_sel.setWordWrap(True)
        pl.addWidget(self.l_sel)
        self.variables = PanelVariables()
        caja_vars = QGroupBox("Variables")
        cv = QVBoxLayout(caja_vars)
        cv.setContentsMargins(1, 1, 1, 1)
        cv.addWidget(self.variables)
        self.variables.setMinimumHeight(140)
        caja = QGroupBox("Diagnósticos")
        cl = QVBoxLayout(caja)
        cl.setContentsMargins(1, 1, 1, 1)
        self.l_resumen = QLabel()  # una línea; el detalle va solo en la lista
        self.l_resumen.setWordWrap(True)
        cl.addWidget(self.l_resumen)
        self.lista_diag = QListWidget()
        self.lista_diag.setWordWrap(True)
        self.lista_diag.itemClicked.connect(self._ir_a_diagnostico)
        self.lista_diag.setMinimumHeight(60)
        self.lista_diag.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # el texto se ajusta al ancho
        cl.addWidget(self.lista_diag)
        reparto = QSplitter(Qt.Orientation.Vertical)  # variables arriba, diagnósticos abajo
        reparto.addWidget(caja_vars)
        reparto.addWidget(caja)
        reparto.setSizes([360, 140])
        pl.addWidget(reparto, 1)
        self.derecho = QStackedWidget()
        self.derecho.addWidget(self.scroll)
        pag_scroll = QScrollArea()  # si no cabe en alto, se desplaza (el ancho es el del panel, sin barra horizontal)
        pag_scroll.setWidgetResizable(True)
        pag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pag_scroll.setWidget(pag)
        self.derecho.addWidget(pag_scroll)
        self.derecho.setMinimumWidth(300)  # al simular; al editar, el mismo margen de ancho que el panel izquierdo
        # Arriba, el dibujo y el panel derecho; abajo, a todo el ancho de los dos, el panel inferior (traza,
        # opciones): así una fórmula larga se ve en una línea. El panel izquierdo es un dock, a toda la altura.
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(izq)
        self.split.addWidget(self.derecho)
        self.split.setSizes([880, 460])
        self.vsplit = QSplitter(Qt.Orientation.Vertical)
        self.vsplit.addWidget(self.split)
        self.vsplit.addWidget(self.inferior)
        self.vsplit.setSizes([520, ALTO_INFERIOR["simular"]])
        self.setCentralWidget(self.vsplit)
        # Izquierda: la paleta (carpetas Elementos y Acciones); solo al editar. Las opciones de lo seleccionado van abajo.
        self.paleta = Paleta()
        self.paleta_acciones = PaletaAcciones()
        self.carpetas = QTabWidget()  # las dos carpetas de la paleta: «Elementos» y «Acciones»
        for lista, titulo in ((self.paleta, "Elementos"), (self.paleta_acciones, "Acciones")):
            lista.setMinimumWidth(lista.ancho_minimo())  # las dos columnas de fichas, sin cortarse
            lista.ayuda.connect(self._ayuda_ficha)  # un clic en una ficha solo muestra su ayuda
            lista.escala = self.diagrama.escala
            self.carpetas.addTab(lista, titulo)
        izq_edit = QWidget()
        vl = QVBoxLayout(izq_edit)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(self.carpetas)
        vl.addStretch(1)
        self.dock = QDockWidget("Elementos", self)
        self.dock.setObjectName("dock-elementos")
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.dock.setWidget(izq_edit)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)
        # Ancho de los paneles laterales al editar: único y fijo (lo que piden las dos columnas de la paleta y, como mínimo,
        # lo que hace falta para que la tabla de variables deje ver los nombres), el mismo en el dock y en el panel derecho;
        # no se pueden estirar, solo plegar
        self.ancho_lateral = max(self.dock.minimumSizeHint().width(), ANCHO_LATERAL)
        self.dock.setMinimumWidth(self.ancho_lateral)
        self.dock.setMaximumWidth(self.ancho_lateral)
        self.resizeDocks([self.dock], [self.ancho_lateral], Qt.Orientation.Horizontal)
        self.dock.hide()
        # Barra de estado: aviso de conformidad, lecturas distintas de las decididas, instante lógico
        sb = self.statusBar()
        self.l_aviso = QLabel(AVISO)
        self.l_lect = QLabel()
        self.l_lect.setStyleSheet(f"color: {COL['err']}")
        self.l_reloj = QLabel()
        self.l_reloj.setStyleSheet("font-weight: 600")
        sb.addWidget(self.l_aviso, 1)
        # el mensaje temporal sustituye al texto fijo mientras dura (si no, se dibujan uno encima del otro)
        sb.messageChanged.connect(lambda texto: self.l_aviso.setVisible(not texto))
        sb.addPermanentWidget(self.l_lect)
        sb.addPermanentWidget(self.l_reloj)

    def _barra_herramientas(self) -> None:
        self.tb_modo = QToolBar("Modo")
        self.tb_modo.setMovable(False)
        for a in (self.a_editar, self.a_simular):
            self.tb_modo.addAction(a)
        self.addToolBar(self.tb_modo)
        self.tb_sim = QToolBar("Simulación")
        self.tb_sim.setMovable(False)
        for a in (self.a_ejecutar, self.a_paso, self.a_completar):
            self.tb_sim.addAction(a)
        self.tb_sim.addSeparator()
        self.tb_sim.addAction(self.a_reiniciar)
        self.addToolBar(self.tb_sim)
        self.tb_edit = QToolBar("Edición")
        self.tb_edit.setMovable(False)
        for a in (self.a_debajo, self.a_deshacer, self.a_rehacer, self.a_borrar):
            self.tb_edit.addAction(a)
        self.addToolBar(self.tb_edit)
        self.tb_edit.hide()
        self._acciones_edicion(False)

    def _paneles(self) -> None:
        """Flechas en el borde del dibujo para plegar del todo los paneles (el izquierdo, el de la paleta y las
        propiedades, solo existe al editar), y el estado guardado."""
        self.flechas = {}
        for nombre, lugar in (("izquierdo", "izquierda"), ("derecho", "derecha"), ("inferior", "abajo")):
            b = QToolButton()
            b.clicked.connect(lambda _=False, n=nombre: self._mostrar_panel(n, not self._accion_panel(n).isChecked()))
            self.diagrama.borde(b, lugar)
            self.flechas[nombre] = b
        self.flechas["izquierdo"].hide()
        for nombre in ("izquierdo", "derecho", "inferior"):
            accion = self._accion_panel(nombre)
            visible = self.ajustes.value(f"paneles/{nombre}", True, type=bool)
            accion.blockSignals(True)
            accion.setChecked(visible)
            accion.blockSignals(False)
            self._mostrar_panel(nombre, visible, guardar=False)

    def _panel(self, nombre: str) -> QWidget:
        return {"izquierdo": self.dock, "derecho": self.derecho, "inferior": self.inferior}[nombre]

    def _abrir_opciones(self) -> None:
        """Despliega el panel inferior (las opciones de lo seleccionado), si estaba plegado."""
        self._mostrar_panel("inferior", True)

    def _accion_panel(self, nombre: str) -> QAction:
        return {"izquierdo": self.a_izquierdo, "derecho": self.a_derecho, "inferior": self.a_inferior}[nombre]

    def _mostrar_panel(self, nombre: str, visible: bool, guardar: bool = True) -> None:
        editar = self.modo == "editar" and self.edicion is not None
        self._panel(nombre).setVisible(visible and (editar or nombre != "izquierdo"))
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
        if not self._salir_de_edicion():
            return False
        try:
            op = open_model(ruta)
        except (DiagnosticError, OSError) as exc:
            QMessageBox.warning(self, TITULO, f"No se pudo abrir {ruta}:\n\n{exc}")
            return False
        if not op.executable:
            QMessageBox.warning(self, TITULO, "El modelo no se puede simular:\n\n"
                                + "\n".join(str(d) for d in op.diagnostics))
            return False
        layout = layout_from_presentation(op.presentations[0]) if op.presentations else {}
        avisos = [str(d) for d in op.diagnostics]
        ayuda = (f"Modelo abierto de {ruta}. "
                 + ("Posiciones de su presentación." if layout else "Sin presentación: colocado automáticamente.")
                 + (" Avisos: " + "; ".join(avisos) if avisos else ""))
        proyecto = ruta if ruta.is_dir() else ruta.parent if ruta.name == "manifest.json" else None
        self.fuente = {"tipo": "fichero", "ruta": ruta, "doc": op.doc, "layout": layout, "titulo": op.title,
                       "ayuda": ayuda, "raiz": proyecto, "presentacion": op.presentations[0] if op.presentations else None}
        checked = self.grupo.checkedAction()
        if checked:
            self.grupo.setExclusive(False)
            checked.setChecked(False)
            self.grupo.setExclusive(True)
        self._cargar()
        return True

    def abrir(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir modelo", "", "Modelo o proyecto GRAFCET (*.json)")
        if ruta:
            self.abrir_ruta(Path(ruta))

    def _cargar(self) -> None:
        self.a_ejecutar.setChecked(False)  # ejecución nueva; si se puede, el tiempo real arranca al final
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
        self.setWindowTitle(f"{self.v.model['title']} — {TITULO}")
        self.diagrama.ajustar()
        self._entradas()
        self.refrescar()
        # Como un autómata: el tiempo corre desde que se carga (si el modelo compila y la situación es estable)
        self.a_ejecutar.setChecked(self.v.s is not None and self.v.s.status == "pausada-estable")

    def reiniciar(self) -> None:
        self._cargar()

    # -- edición: modos, herramientas y diálogos ---------------------------------------------------
    def _acciones_edicion(self, on: bool) -> None:
        for a in (*self.a_herr.values(), self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo):
            a.setEnabled(on)

    def _titulo_ventana(self) -> None:
        e = self.edicion
        if self.modo == "editar" and e is not None:
            self.setWindowTitle(f"{e.titulo}{' *' if e.ed.dirty else ''} (editando) — {TITULO}")

    def _salir_de_edicion(self) -> bool:
        """Antes de cargar otro modelo: si hay cambios sin guardar, pregunta. Descarta la edición en curso."""
        e = self.edicion
        if e is not None and e.ed.dirty:
            r = QMessageBox.question(self, TITULO, f"«{e.titulo}» tiene cambios sin guardar. ¿Guardarlos?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                     | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel or (r == QMessageBox.StandardButton.Save and not self.guardar()):
                return False
        if e is not None:
            shutil.rmtree(self.recup.dir, ignore_errors=True)
            self.edicion = None
            self.modo = "simular"
            self._poner_modo()
        return True

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        if self._salir_de_edicion():
            self.a_ejecutar.setChecked(False)
            self.t_auto.stop()
            event.accept()
        else:
            event.ignore()

    def nuevo(self) -> None:
        if not self._salir_de_edicion():
            return
        self._empezar_edicion(Edicion.nuevo())

    def _edicion_desde_fuente(self) -> Edicion:
        """Copia editable de lo que se está simulando (un ejemplo o un modelo abierto)."""
        f = self.fuente
        if f["tipo"] == "ejemplo":
            title, _, build = EJEMPLOS[f["clave"]]
            m, layout = build()
            return Edicion.desde(m.doc, layout, title)
        return Edicion.desde(f["doc"], f["layout"], f["titulo"], f.get("raiz"), f.get("presentacion"))

    def _empezar_edicion(self, e: Edicion) -> None:
        self.edicion = e
        e.diagrama = self.diagrama
        e.cambiado.connect(self.refrescar_edicion)
        e.redibujar.connect(self._redibujar_edicion)
        e.pedir_condicion = self.editar_condicion
        e.pedir_etiqueta = self.editar_etiqueta
        e.pedir_accion = self.editar_accion
        e.confirmar_borrado = self._confirmar_borrado
        self.cambiar_modo("editar")

    def cambiar_modo(self, modo: str) -> bool:
        if modo == "editar":
            if self.edicion is None:
                if self.v is None:
                    self._empezar_edicion(Edicion.nuevo())
                else:
                    self._empezar_edicion(self._edicion_desde_fuente())
                return True
            self.a_ejecutar.setChecked(False)
            self.modo = "editar"
        else:
            if self.edicion is not None:
                if self._variables_sin_nombre():
                    self._poner_modo()
                    return False
                res = self.edicion.ed.validate()
                if not res.can_simulate:
                    self._no_simulable()
                    self._poner_modo()
                    return False
                self.fuente = {"tipo": "editor"}
                self.modo = "simular"
                self._poner_modo()
                self._cargar()
                return True
            self.modo = "simular"
        self._poner_modo()
        return True

    def _poner_modo(self) -> None:
        """Ajusta la interfaz al modo: herramientas, panel derecho, dibujo y acciones."""
        editar = self.modo == "editar" and self.edicion is not None
        for a, on in ((self.a_editar, editar), (self.a_simular, not editar)):
            a.blockSignals(True)
            a.setChecked(on)
            a.blockSignals(False)
        self.tb_edit.setVisible(editar)
        self.tb_sim.setVisible(not editar)
        self.dock.setVisible(editar and self.a_izquierdo.isChecked())
        self.flechas["izquierdo"].setVisible(editar)
        self._acciones_edicion(editar)
        for a in (self.a_ejecutar, self.a_paso, self.a_completar, self.a_reiniciar):
            a.setEnabled(not editar)  # sin simulación en curso al editar (F5 y compañía no hacen nada)
        self.derecho.setCurrentIndex(1 if editar else 0)
        self.inferior.setCurrentIndex(1 if editar else 0)  # la traza al simular; las opciones al editar
        self._anchos_laterales()
        self._alto_inferior(editar)
        self.diagrama.modo_edicion(editar, self.edicion if editar else None)
        if editar:
            self.refrescar_edicion()
        else:
            self.diagrama.ajustar()

    def _anchos_laterales(self) -> None:
        """Al editar, el panel derecho mide lo mismo que el izquierdo, fijo y sin divisor que lo mueva; al simular, el de
        siempre (se puede estirar)."""
        editar = self.modo == "editar" and self.edicion is not None
        ancho = self.ancho_lateral
        self.derecho.setMinimumWidth(ancho if editar else 300)
        self.derecho.setMaximumWidth(ancho if editar else 16777215)
        self.split.handle(1).setEnabled(not editar)
        total = max(self.split.width(), 1000)
        self.split.setSizes([total - ancho, ancho] if editar else [880, 460])
        if editar:
            self.resizeDocks([self.dock], [ancho], Qt.Orientation.Horizontal)

    def _alto_inferior(self, editar: bool) -> None:
        """Al cambiar de modo, el panel inferior recupera la altura que tenía en ese modo (la inicial, o la que dejó el
        divisor): el dibujo y el panel se reparten el alto."""
        if self.isVisible() and self.inferior.isVisible():
            self._alturas["simular" if editar else "editar"] = self.vsplit.sizes()[1]
        if self.inferior.isHidden() and self.isVisible():
            return  # plegado: al desplegarlo vuelve a su altura
        alto = self._alturas["editar" if editar else "simular"]
        total = max(sum(self.vsplit.sizes()), alto + 200)
        self.vsplit.setSizes([total - alto, alto])

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self.modo == "editar" and self.edicion is not None and not getattr(self, "_anchos_puestos", False):
            self._anchos_puestos = True  # con la ventana ya dimensionada, los dos paneles laterales con el mismo ancho
            self._anchos_laterales()
            self._alto_inferior(True)

    def _no_simulable(self) -> None:
        lineas = self.edicion.resumen(self.edicion.diagnosticos())
        QMessageBox.warning(self, TITULO, "El grafcet no compila, no se puede simular todavía:\n\n"
                            + "\n".join(f"• {x}" for x in lineas[:8]) + ("\n…" if len(lineas) > 8 else ""))
        # cada elemento con un error parpadea en naranja (después del aviso, que lo tapa) y se lleva a la vista
        self.edicion.parpadear([d["target"] for d in self.edicion.diagnosticos() if d["blocks"] and d["target"]])

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
        marcados = {d["target"] for d in diags if d["blocks"] and d["target"]}
        self.diagrama.mostrar(e.M, {}, e.seleccion_dibujo(), marcados, e.parpadeo.activos())
        self.estado.setText("editando")
        self.estado.setStyleSheet(f"color: {COL['accent']}; border: 1px solid {COL['accent']}; border-radius: 9px; "
                                  "padding: 1px 9px")
        self.titulo.setText(f"{e.titulo}{' *' if e.ed.dirty else ''}")
        self.ayuda.setText(e.mensaje or AYUDA_EDICION[e.herramienta])
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
        self.variables.mostrar(e)
        self.a_deshacer.setEnabled(bool(e.ed.undo_stack))
        self.a_rehacer.setEnabled(bool(e.ed.redo_stack))
        self.a_borrar.setEnabled(bool(e.sel))
        self.a_debajo.setEnabled(len(e.sel) == 1)
        bloq = [d for d in diags if d["blocks"]]
        self.l_resumen.setText("El grafcet se puede simular." if not bloq else
                               f"No se puede simular: {len(bloq)} error{'es' if len(bloq) != 1 else ''}")
        self.l_resumen.setStyleSheet(f"color: {COL['ok'] if not bloq else COL['err']}")
        self.lista_diag.clear()
        for d in diags:
            q = f" · {d['question']}" if d["question"] else ""
            item = QListWidgetItem(f"{d['code']}{q}: {d['message']}")
            item.setData(Qt.ItemDataRole.UserRole, d["target"])
            item.setToolTip(d["correction"])
            item.setForeground(QColor(COL["err"] if d["blocks"] else COL["muted"]))
            self.lista_diag.addItem(item)
        self._titulo_ventana()

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

    def editar_condicion(self, tid: str) -> None:
        """Doble clic en una transición: la selecciona y despliega el panel inferior con su receptividad."""
        self.edicion.seleccionar([tid])
        self._abrir_opciones()

    def editar_accion(self, sid: str | None, aid: str | None = None) -> None:
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
        self._abrir_opciones()

    def editar_etiqueta(self, ident: str) -> None:
        """Doble clic en una etapa: despliega las opciones y lleva el cursor a su etiqueta."""
        self.edicion.seleccionar([ident])
        self._abrir_opciones()
        self.props.s_etiqueta.setFocus()
        self.props.s_etiqueta.selectAll()

    def leyenda(self) -> None:
        """«Ayuda > Leyenda del dibujo»: una ventana propia (no modal) con lo que significa cada trazo y color."""
        if self._leyenda is None:
            d = QDialog(self)
            d.setWindowTitle("Leyenda del dibujo")
            d.resize(640, 420)
            lay = QVBoxLayout(d)
            texto = QLabel(LEYENDA)
            texto.setWordWrap(True)
            texto.setAlignment(Qt.AlignmentFlag.AlignTop)
            texto.setMargin(8)
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setWidget(texto)
            lay.addWidget(sc)
            self._leyenda = d
        self._leyenda.show()
        self._leyenda.raise_()
        self._leyenda.activateWindow()

    def _confirmar_borrado(self, plan: dict[str, list[str]]) -> bool:
        e = self.edicion
        n = e.nombres
        extra = [n.get(i, i) for i in plan["elements"] if i not in e.sel]
        texto = f"Se borrará: {', '.join(n.get(i, i) for i in e.sel)}."
        if extra:
            texto += f"\n\nTambién se lleva consigo: {', '.join(extra)}."
        if plan["affectedTransitions"]:
            texto += f"\n\nQuedan sin enlace en este extremo: {', '.join(n.get(i, i) for i in plan['affectedTransitions'])}."
        return QMessageBox.question(self, TITULO, texto + "\n\nSe puede deshacer con Ctrl+Z. ¿Continuar?") \
            == QMessageBox.StandardButton.Yes

    # -- recuperación automática (REQ-EDT-10) -----------------------------------------------------------
    def autoguardar(self, ahora: float | None = None) -> bool:
        e = self.edicion
        if e is None or not e.ed.dirty:
            return False
        try:
            return self.recup.maybe_autosave(time.time() if ahora is None else ahora, True, e.proyecto(), e.ed.revision)
        except (DiagnosticError, OSError):
            return False

    def ofrecer_recuperacion(self) -> bool:
        """Al arrancar: si quedó una copia de recuperación de una edición sin guardar, se ofrece abrirla."""
        try:
            info = self.recup.available()
            if not info:
                return False
            op = open_model(self.recup.dir)
        except (DiagnosticError, OSError):
            return False
        if QMessageBox.question(self, TITULO, "Quedó una edición sin guardar (copia de recuperación). ¿Abrirla?") \
                != QMessageBox.StandardButton.Yes:
            shutil.rmtree(self.recup.dir, ignore_errors=True)
            return False
        e = Edicion.desde(op.doc, {}, op.title, None, op.presentations[0] if op.presentations else None)
        e.ed.dirty = True
        self._empezar_edicion(e)
        return True

    def paso_evolucion(self) -> None:
        """Paso: una evolución del recorrido pendiente; con la situación estable, hasta el próximo vencimiento."""
        if self.v is None or self.v.s is None:
            return
        st = self.v.s.status
        if st == "pausada-recorrido":
            self._act("evolucion")
        elif st == "pausada-estable":
            sig = self.v.state().get("nextEventUs")
            if sig is None:
                self.aviso.setText("No hay ningún vencimiento pendiente: la situación solo cambia con las entradas.")
            else:
                self._act("hasta", us=sig)

    def avanzar_tiempo(self) -> None:
        """Depuración: avanza el tiempo lógico una duración dada (por ejemplo «0,5», «2 s» o «350 ms»)."""
        if self.v is None or self.v.s is None or self.v.s.status != "pausada-estable":
            QMessageBox.information(self, TITULO, "El tiempo solo puede avanzarse con la situación estable.")
            return
        texto, ok = QInputDialog.getText(self, "Avanzar el tiempo", "Duración (segundos, o con unidad: «350 ms»):",
                                         text="1 s")
        if not ok:
            return
        raw = texto.strip().replace(",", ".")
        try:
            us = parse_duration(raw if re.search(r"[a-zµ]", raw) else f"{raw} s")
        except DiagnosticError as exc:
            QMessageBox.warning(self, TITULO, f"No es una duración válida: {exc}")
            return
        self.a_ejecutar.setChecked(False)  # el tiempo avanzado a mano no se mezcla con el del reloj
        self._act("avanzar", us=us)

    # -- acciones de simulación -------------------------------------------------------------------
    def _act(self, op: str, **body: Any) -> None:
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
        fila = col = 0
        for var in self.v.model["inputs"]:
            if var in numeric:
                if col:
                    fila, col = fila + 1, 0
                self.rejilla.addWidget(QLabel(f"<b>{html.escape(self.nombre(var))}</b> ="), fila, 0)
                campo = QLineEdit()
                campo.setPlaceholderText("valor" + (" entero" if numeric[var] == "int" else ""))
                campo.returnPressed.connect(lambda v=var: self._valor(v))
                self.rejilla.addWidget(campo, fila, 1, 1, 2)
                b = QPushButton("Aplicar")
                b.clicked.connect(lambda _=False, v=var: self._valor(v))
                self.rejilla.addWidget(b, fila, 3)
                self.campos[var] = campo
                self.botones[var] = b
                fila += 1
                continue
            b = QPushButton()
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, v=var: self._act("entrada", var=v, paso=self.paso.isChecked()))
            self.rejilla.addWidget(b, fila, col)
            self.botones[var] = b
            col += 1
            if col == 4:
                fila, col = fila + 1, 0
        if not self.v.model["inputs"]:
            self.rejilla.addWidget(QLabel("Sin entradas"), 0, 0)

    def nombre(self, ident: str) -> str:
        """Nombre visible de una variable, etapa, parcial o transición (los ID internos no se muestran)."""
        return self.v.model.get("names", {}).get(ident, ident) if self.v else ident

    def _valor(self, var: str) -> None:
        self._act("valor", var=var, texto=self.campos[var].text(), paso=self.paso.isChecked())

    def _opciones(self, options: dict[str, str]) -> None:
        self.options = normalize_options(options)  # cambia el perfil efectivo: ejecución nueva
        self._cargar()

    def lecturas(self) -> None:
        d = Lecturas(self, self.options)
        if d.exec() == QDialog.DialogCode.Accepted and d.options() != self.options:
            self._opciones(d.options())

    def _ejecutar(self, on: bool) -> None:
        self.a_ejecutar.setText("‖ Pausa" if on else "▶ Ejecutar")
        if on:
            self.reloj.start()
            self.rt.start()
        else:
            self.rt.stop()

    def _tick(self) -> None:
        us = self.reloj.restart() * 1000
        if self.v is None or self.v.s is None or self.v.s.status != "pausada-estable":
            self.a_ejecutar.setChecked(False)
            return
        self._act("avanzar", us=us)

    # -- presentación del estado ----------------------------------------------------------------
    def refrescar(self) -> None:
        M, S = self.v.model, self.v.state()
        label, color = ESTADOS.get(S["status"], (S["status"], "muted"))
        self.estado.setText(label)
        self.estado.setStyleSheet(f"color: {COL[color]}; border: 1px solid {COL[color]}; border-radius: 9px; "
                                  "padding: 1px 9px")
        self.titulo.setText(M["title"])
        self.ayuda.setText(M["help"])
        stable, rec = S["status"] == "pausada-estable", S["status"] == "pausada-recorrido"
        self._diagnostico(S, rec)
        self.diagrama.mostrar(M, S if "time" in S else {})
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
            b.setText(f"{self.nombre(var)} = {1 if on else 0}")
            b.setStyleSheet(f"background: {COL['accent_soft']}; border: 1px solid {COL['accent']}; color: #1d2330; "
                            "padding: 5px 10px" if on else "padding: 5px 10px")
        self.a_completar.setEnabled(rec)
        self.a_paso.setEnabled(rec or (stable and S.get("nextEventUs") is not None))
        self.a_ejecutar.setEnabled(stable or self.a_ejecutar.isChecked())
        if self.a_ejecutar.isChecked() and not stable:
            self.a_ejecutar.setChecked(False)  # error o recorrido pendiente: el tiempo real se pausa solo
        self.l_reloj.setText(f"τ = {t_trunc(S['timeUs']) if 'timeUs' in S else '—'}"
                             + (f" · próximo vencimiento: {S['nextEvent']}" if S.get("nextEvent") else ""))
        self._lecturas()
        self._variables(M, S)
        self._traza(S)

    def _diagnostico(self, S: dict[str, Any], rec: bool) -> None:
        e = html.escape
        if S["status"] == "no-compilable":
            items = "".join(f"<li><b>{e(d['code'])}</b>: {e(d['message'])}<br><i>{e(d.get('correction', ''))}</i></li>"
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
        text = (f"<b>{e(d['code'])}{' · ' + e(d['question']) if d.get('question') else ''}</b><p>{e(d['message'])}</p>"
                f"<p><i>{e(d.get('correction', ''))}</i></p>")
        if blk:
            text += (f"<p>Recorrido determinado hasta S = {{{e(', '.join(self.nombre(i) for i in blk['reached']))}}}"
                     + (f"; en cuestión: <b>{e(self.nombre(blk['element']))}</b>" if blk.get("element") else "")
                     + ". Lo que pase después depende de la cuestión abierta, así que el lote se rechaza entero.</p>")
        if S["status"] == "error":
            text += ("<p>El motor no aproxima: conserva el último estado estable"
                     + (f" {{{e(', '.join(self.nombre(i) for i in blk['lastStable']))}}}, que <b>no</b> es el resultado del lote" if blk else "")
                     + ". Pulse «Reiniciar» (Ctrl+R) para seguir.</p>")
        else:
            text += "<p>Contexto pendiente: puede completarse evolución a evolución.</p>"
        self.diag.setText(text)
        self.diag.show()

    def _lecturas(self) -> None:
        """Aviso discreto, en la barra de estado, cuando alguna lectura difiere de la decidida por el responsable."""
        changed = [q for q, v in self.options.items() if q in SEMANTIC_OPTIONS and v != SEMANTIC_OPTIONS[q]["default"]]
        self.l_lect.setText(f"Lecturas distintas de las decididas: {', '.join(sorted(changed, key=_q_key))} · "
                            if changed else "")
        self.l_lect.setToolTip("Se registran en la traza y no implican conformidad (Ajustes > Lecturas de interpretación)"
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
                item = QTableWidgetItem(c)
                if j == col_color:
                    item.setForeground(QColor(COL[color]))
                t.setItem(i, j, item)

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
        """Guarda el modelo en curso, con sus posiciones, como proyecto (documento 09) que luego puede abrirse.
        Si se está editando, guarda lo editado en su carpeta (la primera vez pregunta cuál)."""
        if self.edicion is not None:
            return self._guardar_edicion()
        f = self.fuente
        base = QFileDialog.getExistingDirectory(self, "Carpeta donde crear el proyecto")
        if not base:
            return False
        name = f["clave"] if f["tipo"] == "ejemplo" else f["ruta"].stem
        destino = Path(base) / re.sub(r"[^A-Za-z0-9._-]", "-", name)
        if destino.exists() and any(destino.iterdir()):
            r = QMessageBox.question(self, TITULO, f"{destino} ya existe y no está vacía. ¿Sobrescribir el proyecto?")
            if r != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.guardar_en(destino)
        except (DiagnosticError, OSError) as exc:
            QMessageBox.warning(self, TITULO, f"No se pudo guardar:\n\n{exc}")
            return False
        self.statusBar().showMessage(f"Proyecto guardado en {destino}", 8000)
        return True

    def _guardar_edicion(self) -> bool:
        e = self.edicion
        if self._variables_sin_nombre():
            return False
        destino = e.ruta
        if destino is None:
            base = QFileDialog.getExistingDirectory(self, "Carpeta donde crear el proyecto")
            if not base:
                return False
            destino = Path(base) / (re.sub(r"[^A-Za-z0-9._-]", "-", e.titulo).strip("-") or "grafcet")
            if destino.exists() and any(destino.iterdir()):
                r = QMessageBox.question(self, TITULO, f"{destino} ya existe y no está vacía. ¿Sobrescribir el proyecto?")
                if r != QMessageBox.StandardButton.Yes:
                    return False
        try:
            e.guardar(destino)
        except (DiagnosticError, OSError) as exc:
            QMessageBox.warning(self, TITULO, f"No se pudo guardar:\n\n{exc}")
            return False
        shutil.rmtree(self.recup.dir, ignore_errors=True)  # lo guardado ya no necesita su copia de recuperación
        self.recup.last_save_s = None
        self.statusBar().showMessage(f"Proyecto guardado en {destino}", 8000)
        self._titulo_ventana()
        return True

    def guardar_en(self, destino: Path) -> None:
        f, doc = self.fuente, self.v.doc
        if f["tipo"] == "editor":
            layout = {**auto_layout(doc), **self.edicion.layout()}
        elif f["tipo"] == "ejemplo":
            layout = EJEMPLOS[f["clave"]][2]()[1]
        else:
            layout = {**auto_layout(doc), **f["layout"]}
        ident = re.sub(r"[^A-Za-z0-9._-]", "-", destino.name)[:120] or "proyecto"
        project = new_project(ident, self.v.model["title"])
        add_document(project, doc)
        pres = self.edicion.ed.presentation if f["tipo"] == "editor" else f.get("presentacion")
        add_document(project, copy.deepcopy(pres) if pres else presentation_for(doc, layout))
        save_project(destino, project)

    def guardar_imagen(self) -> None:
        editando = self.modo == "editar" and self.edicion is not None
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar el dibujo", f"{self.edicion.titulo if editando else self.v.key}.png",
                                              "Imagen PNG (*.png)")
        img = imagen(self.edicion.M, {}) if editando else imagen(self.v.model, self.v.state()) if ruta else None
        if ruta and not img.save(ruta):
            QMessageBox.warning(self, TITULO, f"No se pudo guardar {ruta}")

    def acerca(self) -> None:
        QMessageBox.about(self, f"Acerca de {TITULO}", (
            f"<b>{TITULO}</b> {APP_VERSION}<br><br>Simulador del núcleo GRAFCET con el <b>perfil provisional</b>: no "
            "declara conformidad con IEC 60848 / UNE-EN 60848. Las lecturas por defecto son las decisiones del "
            "responsable; lo que sigue abierto se detiene con su cuestión U.<br><br>Interfaz con Qt for Python "
            "(PySide6), bajo licencia LGPL v3: las bibliotecas de Qt van como ficheros separados en la carpeta del "
            "programa y pueden sustituirse por otras versiones compatibles."))


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="GRAFCET", description=TITULO)
    ap.add_argument("modelo", nargs="?", help="proyecto (carpeta o manifest.json) o documento de modelo que abrir")
    ap.add_argument("--ejemplo", choices=list(EJEMPLOS), help="ejemplo con el que empezar")
    ap.add_argument("--captura", metavar="PNG", help="guardar una captura de la ventana y salir (comprobación)")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(TITULO)
    w = Ventana()
    if not args.captura:
        w.ofrecer_recuperacion()
    if args.ejemplo:
        w.cargar_ejemplo(args.ejemplo)
    if args.modelo and not w.abrir_ruta(Path(args.modelo)):
        return 1 if args.captura else 0
    w.show()
    if args.captura:
        QTimer.singleShot(300, lambda: (w.grab().save(args.captura), app.quit()))
    return app.exec()
