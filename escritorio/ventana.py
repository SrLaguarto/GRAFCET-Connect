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

from PySide6.QtCore import QElapsedTimer, QSettings, QStandardPaths, Qt, QTimer, QSize
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
                               QScrollArea, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QToolBar, QToolButton, QVBoxLayout, QWidget, QStyle)

from grafcet.diagnostics import DiagnosticError
from grafcet.engine import Session
from grafcet.examples import EJEMPLOS
from grafcet.persistence import Recovery, add_document, new_project, open_model, save_project
from grafcet.profile import APP_VERSION, SEMANTIC_OPTIONS, normalize_options
from grafcet.timeutil import parse_duration
from grafcet.view import Vista, auto_layout, layout_from_presentation, presentation_for, t_trunc

from .diagrama import COL, VistaDiagrama, imagen
from .edicion import HERRAMIENTAS, Edicion
from .propiedades import PanelPropiedades, Paleta
from .variables import PanelVariables
from .entradas_salidas import CONEXION_INICIAL, PanelES
from conexion.configuracion import ARCHIVO, Configuracion
from conexion.coordinador import Coordinador

TITULO = "Simulador GRAFCET"
ANCHO_LATERAL = 212  # ancho mínimo de los paneles laterales al editar (la tabla de variables enseña los nombres)
ALTO_INFERIOR = {"simular": 300, "editar": 380}  # altura inicial del panel inferior: la traza, o las opciones de lo seleccionado
TICK_MS = 100  # tiempo real: cada cuánto se avanza el tiempo lógico
AYUDA_EDICION = {
    "seleccionar": "Clic selecciona un elemento y muestra sus opciones abajo; arrastrarlo lo mueve (a la "
                   "rejilla, y no encima de otro elemento); de un punto de unión (arriba o abajo de una etapa o transición, "
                   "a la derecha de una etapa) sale un enlace. Supr borra; Ctrl+Z y Ctrl+Y deshacen y rehacen. Los "
                   "elementos y las acciones nuevos se arrastran desde la paleta de la izquierda; otro tipo de acción, con botón derecho "
                   "sobre ella.",
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
    "condición; marco verde = salida a 1.<br><b>Jerarquía</b>: macroetapa = divisiones horizontales arriba y abajo; "
    "encapsulante = esquinas cortadas; recinto = marco con la encapsulante arriba y su nombre abajo; los trazos discontinuos "
    "que unen la macroetapa con su expansión (de E a S) y la encapsulante con su recinto solo se ven con «Mostrar "
    "dependencias» (junto al zoom); * = enlace de activación; G{…} en rectángulo doble = orden de forzado "
    "(morada si está vigente; {*} situación actual, {INIT} inicial, { } vacía); marco redondeado = parcial.<br>"
    "<br><b>Temporizadores</b>: encima de la duración de la receptividad o de la acción con retardo, el tiempo que "
    "lleva («0,5 s») mientras cuenta y «3 s ✓» cuando ha vencido.<br>"
    "Pase el ratón por una etapa o transición para ver su estado. La rueda acerca o aleja alrededor del puntero; "
    "«Centrar todo» (Ctrl+0) encaja el dibujo.")


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
        self.modo = "editar"  # solo cambia con Play (simular) y Pausa (editar)
        self.modbus = Coordinador()
        self._transicion_ui = False  # Play/Pausa en curso: los cambios que él mismo provoca no lo repiten
        self._aviso_inestable_sesion = None  # sesión de la que ya se avisó (un solo aviso por episodio)
        self._popup_inestable = None
        self._avisos_ejecucion: list[str] = []  # por qué se paró el motor: se muestra entre los diagnósticos al editar
        self._ayuda = ""  # ayuda del ejemplo o modelo abierto, para mostrarla al simular lo que aún no se ha editado
        self._proyecto: Any = None  # qué proyecto hay abierto (los ID de modelo no lo distinguen: todos los ejemplos son «m»)
        self._proyecto_modbus: Any = None  # de qué proyecto es el mapa que tiene cargado el panel de E/S
        self._n_nuevos = 0
        # Recuperación automática cada 30 s mientras hay cambios sin guardar (REQ-EDT-10)
        self.recup = Recovery(recuperacion or Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation)))
        self.t_auto = QTimer(self)
        self.t_auto.setInterval(30_000)
        self.t_auto.timeout.connect(self.autoguardar)
        self.t_auto.start()
        self._menus()
        self._interfaz()
        self.panel_es = PanelES()
        self._conexion_recordada = self._leer_conexion_recordada()
        self.panel_es.conexion_defecto = self._conexion_recordada
        central = self.takeCentralWidget()
        self.paginas_es = QStackedWidget()
        self.paginas_es.addWidget(central)
        self.paginas_es.addWidget(self.panel_es)
        self.setCentralWidget(self.paginas_es)
        self.panel_es.volver.connect(lambda: self._mostrar_pagina(False))
        self.panel_es.conectar.connect(self._conectar_modbus)
        self.panel_es.probar.connect(lambda: self._conectar_modbus(prueba=True))
        self.panel_es.desconectar.connect(self._desconectar_modbus)
        self.panel_es.guardar.connect(self._guardar_config_modbus)
        self.panel_es.cargar_archivo.connect(self._abrir_config_modbus)
        self.panel_es.abrir_prueba.connect(self._abrir_prueba_modbus)
        self.panel_es.aplicar.connect(self._persistir_mapa_modbus)
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
        archivo = bar.addMenu("&Proyecto")
        self.a_nuevo = self._accion("&Nuevo grafcet", self.nuevo, "Ctrl+N")
        archivo.addAction(self.a_nuevo)
        a = self.a_abrir = archivo.addAction("&Abrir modelo…", self.abrir)
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
        # Un solo control de ejecución: Play simula (traza abajo, sin paleta) y Pausa detiene y vuelve a editar
        self.a_ejecutar = self._accion("Ejecutar", self._ejecutar, "F5", marcable=True)
        self.a_ejecutar.setToolTip("Play: simular · Pausa: detener y editar (F5)")
        self.a_reiniciar = self._accion("Reiniciar", self.reiniciar, "Ctrl+R")
        self.a_reiniciar.setToolTip("Volver a la situación inicial; en Play sigue en Play (Ctrl+R)")
        self.a_avanzar = self._accion("&Avanzar el tiempo…", self.avanzar_tiempo)
        self.a_avanzar.setToolTip("Herramienta de depuración: solo en Play y sin E/S externas")
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
        for a in (self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo):
            edicion.addAction(a)
        edicion.addSeparator()
        for a in self.a_herr.values():
            edicion.addAction(a)
        sim = bar.addMenu("&Simulación")
        for a in (self.a_ejecutar, self.a_reiniciar):
            sim.addAction(a)
        sim.addSeparator()
        sim.addAction(self.a_avanzar)
        m_ajustes = bar.addMenu("A&justes")
        m_ajustes.addAction("&Lecturas de interpretación…", self.lecturas)
        ayuda = bar.addMenu("A&yuda")
        ayuda.addAction("&Leyenda del dibujo", self.leyenda)
        ayuda.addAction("&Acerca de", self.acerca)
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
        # Izquierda: la paleta (una sola lista de fichas); solo al editar. Las opciones de lo seleccionado van abajo.
        self.paleta = Paleta()
        self.paleta.setMinimumWidth(self.paleta.ancho_minimo())  # las dos columnas de fichas, sin cortarse
        self.paleta.ayuda.connect(self._ayuda_ficha)  # un clic en una ficha solo muestra su ayuda
        self.paleta.escala = self.diagrama.escala
        self.dock = QWidget()  # panel izquierdo: solo a la altura del dibujo, no del panel inferior
        vl = QVBoxLayout(self.dock)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(self.paleta)
        vl.addStretch(1)
        # Ancho de los paneles laterales al editar: único y fijo (lo que piden las dos columnas de la paleta y, como mínimo,
        # lo que hace falta para que la tabla de variables deje ver los nombres), el mismo en el panel izquierdo y en el
        # derecho; no se pueden estirar, solo plegar
        self.ancho_lateral = max(self.dock.minimumSizeHint().width(), ANCHO_LATERAL)
        self.dock.setFixedWidth(self.ancho_lateral)
        self.dock.hide()
        # Arriba, el panel izquierdo (solo al editar), el dibujo y el panel derecho; abajo, a todo el ancho de la ventana, el
        # panel inferior (traza, opciones): así una fórmula larga o dos programadores por bloques caben sin apretarse.
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(izq)
        self.split.addWidget(self.derecho)
        self.split.setSizes([880, 460])
        arriba = QWidget()
        al = QHBoxLayout(arriba)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        al.addWidget(self.dock)
        al.addWidget(self.split, 1)
        self.vsplit = QSplitter(Qt.Orientation.Vertical)
        self.vsplit.addWidget(arriba)
        self.vsplit.addWidget(self.inferior)
        self.vsplit.setCollapsible(0, False)
        self.vsplit.setCollapsible(1, False)  # el panel inferior se pliega con su flecha, no arrastrando: nunca por debajo de lo que pide
        self.vsplit.setStretchFactor(0, 1)  # al agrandar la ventana crece el dibujo; el panel inferior conserva su altura
        self.vsplit.setStretchFactor(1, 0)
        self.vsplit.setSizes([520, ALTO_INFERIOR["simular"]])
        self.setCentralWidget(self.vsplit)
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
        iconos = {self.a_nuevo: QStyle.StandardPixmap.SP_FileIcon,
                  self.a_abrir: QStyle.StandardPixmap.SP_DirOpenIcon,
                  self.a_guardar: QStyle.StandardPixmap.SP_DialogSaveButton,
                  self.a_deshacer: QStyle.StandardPixmap.SP_ArrowBack,
                  self.a_rehacer: QStyle.StandardPixmap.SP_ArrowForward,
                  self.a_borrar: QStyle.StandardPixmap.SP_TrashIcon,
                  self.a_debajo: QStyle.StandardPixmap.SP_ArrowDown,
                  self.a_ejecutar: QStyle.StandardPixmap.SP_MediaPlay,
                  self.a_reiniciar: QStyle.StandardPixmap.SP_BrowserReload}
        for accion, icono in iconos.items():
            accion.setIcon(self.style().standardIcon(icono))
        self.tb_proyecto = QToolBar("Proyecto")
        self.tb_proyecto.setMovable(False)
        self.tb_proyecto.setIconSize(QSize(20, 20))
        for accion in (self.a_nuevo, self.a_abrir, self.a_guardar):
            self.tb_proyecto.addAction(accion)
        self.tb_proyecto.widgetForAction(self.a_guardar).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(self.tb_proyecto)
        self.setStyleSheet(self.styleSheet() + """
            QMenuBar { background: #f6f7f9; padding: 2px 6px; }
            QMenuBar::item { padding: 5px 9px; border-radius: 4px; }
            QMenuBar::item:selected { background: #e0eaf5; }
            QToolBar { background: #f6f7f9; border: 0; spacing: 4px; padding: 4px; }
            QToolBar QToolButton { padding: 5px 7px; border-radius: 5px; }
            QToolBar QToolButton:hover { background: #e0eaf5; }
            QToolBar QToolButton:checked { background: #d5e6f7; color: #163e65; }
            QTabBar::tab { padding: 7px 18px; border: 0; background: #edf0f4; }
            QTabBar::tab:selected { background: white; border-bottom: 2px solid #377ab8; }
        """)
        self.tb_sim = QToolBar("Simulación")
        self.tb_sim.setMovable(False)
        self.tb_sim.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tb_sim.addAction(self.a_ejecutar)
        self.tb_sim.addSeparator()
        self.tb_sim.addAction(self.a_reiniciar)
        self.addToolBar(self.tb_sim)
        self.tb_conexion = QToolBar("Conexión")
        self.tb_conexion.setMovable(False)
        self.tb_conexion.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        # Un solo botón conmuta entre el dibujo GRAFCET y la vista de E/S externas: pulsado (marcado) mientras se ve ésta,
        # con otro texto, tooltip e icono; _sincronizar_boton_es lo deja coherente con la página visible, sea cual sea la vía
        self.a_es = self._accion("E/S externas", self._alternar_es, marcable=True)
        self._iconos_es = (self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon), _icono_grafcet())
        self.tb_conexion.addAction(self.a_es)
        self._sincronizar_boton_es()
        self.paginas_es.currentChanged.connect(self._sincronizar_boton_es)
        self.addToolBar(self.tb_conexion)
        self._fijar_ancho_boton_es()  # con la barra ya en la ventana: el botón lleva su hoja de estilo
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
        """Carga la fuente (ejemplo, modelo o lo que se edita) y deja el programa en Pausa: parado y editable. La
        conexión Modbus, si la hay, no se cierra: se conserva el TCP y las salidas pasan a 0 (Pausa)."""
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
        self.modo = "editar"
        self._cargar_config_modbus()
        self._poner_modo()
        self.refrescar()
        if not self.modbus.activo:
            self.rt.stop()

    def reiniciar(self) -> None:
        """En Play vuelve a la situación inicial y sigue en Play; con E/S externas la conexión se conserva: solo se vincula
        una sesión nueva y se reescriben las salidas iniciales. En Pausa ya está todo a 0 y sin estado (Pausa es «todo a 0
        hasta un nuevo Play»): no hay nada que reiniciar, solo se vuelve a pedir el cero a la planta si hay conexión."""
        if not self.a_ejecutar.isChecked():
            self.modbus.pausar(diagnostico=True)
            self._sin_estado()
            self.refrescar()
            self.refrescar_edicion()
            return
        if not self._preparar_sesion():
            self.a_ejecutar.setChecked(False)  # no se ha podido: Pausa
            return
        self.reloj.restart()
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
        arranca de cero, y Reiniciar en Play también). Con Modbus vivo la vincula al TCP existente, sin reconectar: antes de
        ejecutar se escriben las salidas iniciales y se leen las entradas de la conexión. Si no puede, avisa y devuelve
        False sin tocar la conexión."""
        if self.edicion is None:
            self._establecer_edicion(self._edicion_desde_fuente() if self.v else Edicion.nuevo())
        if self._variables_sin_nombre():
            return False
        e = self.edicion
        if not e.ed.validate().can_simulate:
            self._no_simulable()
            return False
        ayuda = self._ayuda if self._ayuda and not e.ed.undo_stack else "Simulación del grafcet."
        nueva = Vista(e.ed.model["id"], e.titulo, ayuda, lambda: (copy.deepcopy(e.ed.model), e.layout()), self.options,
                      presentation=e.ed.presentation)
        if nueva.s is None:  # compila con las lecturas por defecto, pero no con las activas (diálogo «Lecturas»)
            lineas = [f"• {d['code']}: {d['message']}" for d in map(nueva._diag, nueva.compile_diags)]
            QMessageBox.warning(self, TITULO, "El grafcet no compila con las lecturas de interpretación activas, no se puede "
                                "simular todavía:\n\n" + "\n".join(lineas[:8]) + ("\n…" if len(lineas) > 8 else ""))
            return False
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
    def _acciones_edicion(self, on: bool) -> None:
        for a in (*self.a_herr.values(), self.a_deshacer, self.a_rehacer, self.a_borrar, self.a_debajo):
            a.setEnabled(on)

    def _titulo_ventana(self) -> None:
        e = self.edicion
        if self.modo == "editar" and e is not None:
            self.setWindowTitle(f"{e.titulo}{' *' if e.ed.dirty else ''} (editando) — {TITULO}")

    def _salir_de_edicion(self) -> bool:
        """Antes de cargar otro modelo: si hay cambios sin guardar, pregunta. Quien carga sustituye la edición en curso."""
        e = self.edicion
        if e is not None and e.ed.dirty:
            r = QMessageBox.question(self, TITULO, f"«{e.titulo}» tiene cambios sin guardar. ¿Guardarlos?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                     | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel or (r == QMessageBox.StandardButton.Save and not self.guardar()):
                return False
        if e is not None:
            shutil.rmtree(self.recup.dir, ignore_errors=True)
        return True

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        if self._salir_de_edicion():
            self._transicion_ui = True
            self.a_ejecutar.setChecked(False)
            self.t_auto.stop()
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
        return Edicion.desde(f["doc"], f["layout"], f["titulo"], f.get("raiz"), f.get("presentacion"))

    def _empezar_edicion(self, e: Edicion) -> None:
        self._ayuda = ""
        self._n_nuevos += 1
        self._proyecto = ("nuevo", self._n_nuevos)
        self._establecer_edicion(e)
        self.cambiar_modo("editar")

    def _establecer_edicion(self, e: Edicion) -> None:
        self.edicion = e
        e.diagrama = self.diagrama
        e.cambiado.connect(self.refrescar_edicion)
        e.redibujar.connect(self._redibujar_edicion)
        e.pedir_condicion = self.editar_condicion
        e.pedir_etiqueta = self.editar_etiqueta
        e.pedir_accion = self.editar_accion
        e.confirmar_borrado = self._confirmar_borrado
        e.pedir_texto = lambda titulo, etiqueta, actual: self._pedir_texto(titulo, etiqueta, actual)
        e.pedir_forzado = lambda datos: self._pedir_forzado(datos)

    def cambiar_modo(self, modo: str) -> bool:
        """Los modos solo se alternan con Play (simular) y Pausa (editar); esto es el mismo control por dentro. Devuelve si
        el programa ha quedado en el modo pedido (Play puede negarse: no compila, inestable…)."""
        on = modo == "simular"
        if self.a_ejecutar.isChecked() != on:
            self.a_ejecutar.setChecked(on)
        else:
            self._ejecutar(on)
        return self.modo == modo

    def _poner_modo(self) -> None:
        """Ajusta la interfaz al modo: herramientas, panel derecho, dibujo y acciones."""
        editar = self.modo == "editar" and self.edicion is not None
        self.tb_edit.setVisible(editar)
        self.variables.setEnabled(editar)  # fuera de edición la tabla no responde a Supr (ni a nada)
        self.dock.setVisible(editar and self.a_izquierdo.isChecked())
        self.flechas["izquierdo"].setVisible(editar)
        self._acciones_edicion(editar)
        self.a_avanzar.setEnabled(not editar)  # la depuración del tiempo solo tiene sentido en Play
        self.derecho.setCurrentIndex(1 if editar else 0)
        self.inferior.setCurrentIndex(1 if editar else 0)  # la traza al simular; las opciones al editar
        self._anchos_laterales()
        self._alto_inferior(editar)
        self.diagrama.modo_edicion(editar, self.edicion if editar else None)
        if editar:
            self.refrescar_edicion()
        else:
            if self.v is not None:
                self.setWindowTitle(f"{self.v.model['title']} — {TITULO}")
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

    def _alto_inferior(self, editar: bool) -> None:
        """Al cambiar de modo, el panel inferior recupera la altura que tenía en ese modo (la inicial, o la que dejó el
        divisor): el dibujo y el panel se reparten el alto. Al editar, mientras el divisor no se haya movido, el panel cede lo
        que haga falta (sin bajar de su mínimo) para que la paleta se vea entera; en una ventana más baja, la paleta se
        encoge y se desplaza."""
        if self.isVisible() and self.inferior.isVisible():
            self._alturas["simular" if editar else "editar"] = self.vsplit.sizes()[1]
        if self.inferior.isHidden() and self.isVisible():
            return  # plegado: al desplegarlo vuelve a su altura
        alto = self._alturas["editar" if editar else "simular"]
        total = max(sum(self.vsplit.sizes()), alto + 200)
        if editar and alto == ALTO_INFERIOR["editar"] and not self.dock.isHidden():  # (a 1366×768: el inferior pasa de 380 a 328)
            alto = max(min(alto, total - self.paleta.sizeHint().height()), self.inferior.minimumSizeHint().height())
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
        for texto in self._avisos_ejecucion:  # por qué paró el motor la última vez que se simuló
            item = QListWidgetItem(f"Simulación detenida · {texto}")
            item.setForeground(QColor(COL["err"]))
            self.lista_diag.addItem(item)
        self._titulo_ventana()
        if hasattr(self, "panel_es"):  # las variables pueden haber cambiado: el panel de E/S las sigue (o avisa, si hay conexión)
            self._sincronizar_es()

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

    def avanzar_tiempo(self) -> None:
        """Depuración (solo en Play): avanza el tiempo lógico una duración dada (por ejemplo «0,5», «2 s» o «350 ms»)."""
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
        self._act("avanzar", us=us)

    # -- acciones de simulación -------------------------------------------------------------------
    def _act(self, op: str, **body: Any) -> None:
        if self.modbus.activo:
            self.aviso.setText("Con E/S externas use Ejecutar/Pausa; desconecte para depurar manualmente")
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
            b.clicked.connect(lambda _=False, v=var: self._act("entrada", var=v))
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
        self.a_ejecutar.setText("Pausa" if on else "Ejecutar")
        self.a_ejecutar.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPause if on else QStyle.StandardPixmap.SP_MediaPlay))

    def _ejecutar(self, on: bool) -> None:
        """Play (on) o Pausa: el único control de ejecución. Play compila lo editado y arranca siempre una sesión nueva desde
        la situación inicial; Pausa detiene la evolución, vuelve a editar y deja todo a 0 hasta el siguiente Play: sin etapas
        activas ni temporizadores y, con E/S externas, todas las salidas asignadas a 0. La conexión Modbus no se cierra:
        Pausa conserva TCP y sigue observando las entradas, y Play vincula la sesión nueva al TCP existente."""
        if self._transicion_ui:
            return
        self._transicion_ui = True
        try:
            venia_de_play = self.modo == "simular"
            if on and not self._preparar_sesion():
                on = False  # no arranca (no compila, inestable, mapa de E/S inválido…): sigue en Pausa
            self.modo = "simular" if on else "editar"
            self._marcar_play(on)
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
            if on or self.modbus.activo:  # con la conexión viva el temporizador sigue en Pausa: observa las entradas
                self.reloj.start()
                self.rt.start()
            else:
                self.rt.stop()
        finally:
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
        evoluciones = [r["text"] for r in vista.state().get("trace", []) if r["kind"] == "evolucion"][-4:]
        self._avisos_ejecucion = ([f"{d['code']}: {d['message']}"] if d else []) \
            + ([f"Últimas evoluciones: {' · '.join(evoluciones)}"] if inestable and evoluciones else [])
        if inestable:
            if self._aviso_inestable_sesion is not vista.s:
                self._aviso_inestable_sesion = vista.s
                self._avisar_inestable()
        elif al_arrancar:
            QMessageBox.warning(self, TITULO, "No se puede ejecutar: revise los diagnósticos del GRAFCET."
                                + (f"\n\n{d['code']}: {d['message']}" if d else ""))
        else:
            self.statusBar().showMessage("El motor se ha detenido por un diagnóstico"
                                         + (f" ({d['code']})" if d else "") + ": véalo en el panel de diagnósticos.", 12000)

    def _avisar_inestable(self) -> None:
        """Ventana modal con un solo botón; no abre un bucle de eventos propio (se llama desde el temporizador)."""
        cuadro = QMessageBox(QMessageBox.Icon.Warning, TITULO,
                             "El GRAFCET es inestable: no alcanza una situación estable. Revise las transiciones.",
                             QMessageBox.StandardButton.Ok, self)
        cuadro.button(QMessageBox.StandardButton.Ok).setText("Aceptar")
        cuadro.finished.connect(lambda _=0: setattr(self, "_popup_inestable", None))
        self._popup_inestable = cuadro
        cuadro.open()

    def _tick(self) -> None:
        us = self.reloj.restart() * 1000
        if self.modbus.activo:
            if self.modbus.adaptador.sesion is None:  # Pausa con la conexión viva: solo se observan las entradas
                self.modbus.tick(False)
                self._recordar_conexion()
                if not self.modbus.activo:  # acaba de cerrarse (desconexión, fallo o prueba): ya pueden verse las variables nuevas
                    self._sincronizar_es()
                self.panel_es.mostrar_estado(self.modbus.estado, self.modbus.mensaje)
                self.panel_es.ocupado(self.modbus.activo)
                self.panel_es.mostrar_muestra(self.modbus.muestra, self.modbus.adaptador.entradas, self.modbus.escritos,
                                              getattr(self.modbus.adaptador, "salidas_control", []))
                if self.a_ejecutar.isChecked():
                    self.a_ejecutar.setChecked(False)
                if not self.modbus.activo:
                    self.rt.stop()
                    self.rt.setInterval(TICK_MS)
                return
            ejecutar = self.a_ejecutar.isChecked() and self.modbus.estado == "conectado" and not self.modbus.reiniciando
            if ejecutar and self.modbus.en_marcha and self.v and self.v.s and self.v.s.status == "pausada-estable":
                self.v.s.advance_to(self.v.s.z.time + us)
            self.modbus.tick(ejecutar)
            self._recordar_conexion()
            if self.a_ejecutar.isChecked() and self._vigilar_motor():
                self.panel_es.mostrar_estado(self.modbus.estado, self.modbus.mensaje)
                return
            if self.modbus.estado in ("error", "desconectado", "diagnostico"):
                self.a_ejecutar.setChecked(False)
            if not self.modbus.activo:
                self._sincronizar_es()
            self.panel_es.mostrar_estado(self.modbus.estado, self.modbus.mensaje)
            self.panel_es.ocupado(self.modbus.activo)
            if self.modo == "simular":
                self.refrescar()
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
        raiz = self._raiz_modbus()
        if raiz and self.panel_es.doc:
            try:
                config.guardar(raiz / ARCHIVO, self.panel_es.doc)
            except (OSError, ValueError) as exc:
                self.panel_es.estado.setText(f"No se pudo guardar el mapa: {exc}")

    def _cargar_config_modbus(self, doc: dict[str, Any] | None = None) -> None:
        doc = doc or self.v.doc
        raiz = self._raiz_modbus()
        config, avisos = None, []
        # Recargar el mismo proyecto conserva el mapa en memoria; cambiar de proyecto exige un mapa propio.
        anterior = self.panel_es.config
        cambio = self._proyecto != self._proyecto_modbus
        self._proyecto_modbus = self._proyecto
        if not cambio and anterior.modelo == doc["id"]:
            config = anterior
        elif raiz and (raiz / ARCHIVO).exists():
            try:
                config = Configuracion.cargar(raiz / ARCHIVO, doc, avisos)  # lo que ya no casa se descarta; el resto se conserva
            except (ValueError, OSError) as exc:
                self.panel_es.estado.setText(f"No se pudo cargar el mapa: {exc}")
        if self.modbus.activo:
            config = copy.deepcopy(config or Configuracion(modelo=doc["id"]))
            config.host, config.puerto, config.unidad = self.modbus.cliente.host, self.modbus.cliente.puerto, self.modbus.cliente.unidad
        self.panel_es.cargar(doc, config, avisos)
        if self.modbus.activo and cambio:
            self._cambiar_modelo_modbus(doc)

    def _cambiar_modelo_modbus(self, doc: dict[str, Any]) -> None:
        """Otro modelo con la conexión viva: TCP se conserva, pero lo que el modelo anterior hubiera escrito ya no lo controla
        nadie (cero) y la lectura sigue con el mapa del modelo nuevo."""
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
        """El último (host, puerto, esclavo) con el que se conectó o se probó con éxito; la primera vez, el de Factory I/O."""
        a = self.ajustes
        host = str(a.value("modbus/host", CONEXION_INICIAL[0]) or "").strip()
        puerto, unidad = a.value("modbus/puerto", CONEXION_INICIAL[1], type=int), a.value("modbus/unidad", CONEXION_INICIAL[2], type=int)
        if not host or not 1 <= puerto <= 65535 or not 0 <= unidad <= 255:  # un valor roto no debe dejar sin conexión propuesta
            return CONEXION_INICIAL
        return host, puerto, unidad

    def _recordar_conexion(self) -> None:
        """Tras conectar o probar la conexión con éxito, recuerda el servidor para proponerlo en los proyectos que no traigan
        mapa propio (el mapa guardado de un proyecto manda sobre esto). No cambia nada de la conexión."""
        m = self.modbus
        if m.cliente is None or not (m.estado == "conectado" or (m.estado == "desconectado" and m.mensaje.startswith("Conexión probada"))):
            return
        datos = (m.cliente.host, m.cliente.puerto, m.cliente.unidad)
        if datos != self._conexion_recordada:
            self._conexion_recordada = datos
            self.panel_es.conexion_defecto = datos
            for clave, valor in zip(("host", "puerto", "unidad"), datos):
                self.ajustes.setValue(f"modbus/{clave}", valor)
            self.ajustes.sync()

    def _doc_es(self) -> dict[str, Any] | None:
        """El modelo cuyas variables enseña el panel de E/S: el que se edita; al simular, el que se está ejecutando."""
        if self.modo == "editar" and self.edicion:
            return self.edicion.ed.model
        return self.v.doc if self.v else None

    def _sincronizar_es(self, mostrando: bool = False) -> None:
        """Deja las listas y los canales del panel de E/S con las variables actuales del modelo, conservando el mapa y la
        configuración (la IP incluida); lo que ya no casa se quita con aviso. Con la conexión viva no se toca: el mapa en
        uso no cambia a mitad de sesión y solo se marca que hay variables nuevas pendientes de ver al desconectar. Al
        mostrar el panel (`mostrando`) también se cambia de mapa si el proyecto es otro; en cualquier otro momento, solo
        si el panel se ve y sigue siendo el mismo proyecto (cambiar de proyecto lo hace `_cargar_config_modbus`)."""
        doc, p = self._doc_es(), self.panel_es
        if doc is None:
            return
        if self.modbus.activo:
            p.marcar_pendiente(p.doc is not None and p.firma(doc) != p.firma_modelo)
            return
        mismo = self._proyecto == self._proyecto_modbus and p.config.modelo == doc["id"]
        if not mostrando and not (mismo and self.paginas_es.currentIndex() == 1):
            return
        if mismo:
            p.actualizar(doc)
        else:
            self._proyecto_modbus = self._proyecto
            p.cargar(doc)

    def mostrar_es(self):
        self._sincronizar_es(mostrando=True)
        self._mostrar_pagina(True)

    def _mostrar_pagina(self, es: bool) -> None:
        """Único sitio que cambia de página: el dibujo GRAFCET (es=False) o la vista de E/S externas (es=True)."""
        self.paginas_es.setCurrentIndex(1 if es else 0)
        self._sincronizar_boton_es()

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

    def _aspecto_boton_es(self, es: bool) -> None:
        """Texto, tooltip e icono del botón conmutador en cada una de sus dos vistas."""
        self.a_es.setText("Vista GRAFCET" if es else "E/S externas")
        self.a_es.setToolTip("Volver al dibujo GRAFCET" if es else
                             "Conectar sensores y actuadores · se vuelve con este mismo botón o con la flecha ← del panel")
        self.a_es.setIcon(self._iconos_es[1 if es else 0])

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
            if not config.senales:
                raise ValueError("Marca al menos una casilla «Usar» en la tabla de variables")
        except (ValueError, RuntimeError) as exc:
            self.panel_es.estado.setText(f"No se pudo conectar: {exc}")
            return
        self._iniciar_conexion_modbus(config, None, prueba)

    def _iniciar_conexion_modbus(self, config, sesion, prueba):
        try:
            self.a_ejecutar.setChecked(False)
            self.modbus.iniciar(config, sesion, prueba, documento=self.panel_es.doc)
            self.panel_es.config = config
            self.panel_es._dibujar()
            self.panel_es.ocupado(True)
            self.panel_es.estado.setText(self.modbus.mensaje)
            self.rt.setInterval(config.periodo_ms)
            self.reloj.start()
            self.rt.start()
        except (ValueError, RuntimeError) as exc:
            self.panel_es.estado.setText(f"No se pudo conectar: {exc}")

    def _abrir_prueba_modbus(self):
        import sys
        raiz = (Path(sys.executable).parent / "prueba_factoryio_digital" if getattr(sys, "frozen", False) else
                Path(__file__).resolve().parents[1] / "pruebas_manuales" / "factoryio_digital")
        if self.abrir_ruta(raiz / "manifest.json"):
            self.a_ejecutar.setChecked(False)
            self._mostrar_pagina(True)
            self.panel_es.estado.setText("Prueba preparada · desconectado. Comprueba la IP de Factory I/O y pulsa «Probar conexión».")

    def _desconectar_modbus(self):
        self.a_ejecutar.setChecked(False)
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
            self.ayuda.setText(M["help"])
        stable, rec = S["status"] == "pausada-estable", S["status"] == "pausada-recorrido"
        self._diagnostico(S, rec)
        if simulando:
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
