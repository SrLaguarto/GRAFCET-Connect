"""Ventana del simulador GRAFCET de escritorio (P-IMP-29, P-IMP-30): primera versión portable para Windows.

Simula un ejemplo o un modelo guardado (proyecto o documento de modelo, documento 09) con el dibujo de la
norma. Entradas, tiempo real (como un autómata: los retardos son temporizadores que cuentan solos), evolución a
evolución, traza, salidas, variables, temporizadores y, en «Ajustes», las lecturas de interpretación. Toda la
semántica la decide grafcet/engine.py con el perfil provisional: la ventana no aproxima nada y los bloqueos por
cuestiones U se muestran tal cual. No es el editor ni declara conformidad con IEC 60848 / UNE-EN 60848.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QElapsedTimer, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QToolBar, QToolButton,
                               QVBoxLayout, QWidget)

from grafcet.diagnostics import DiagnosticError
from grafcet.examples import EJEMPLOS
from grafcet.persistence import add_document, new_project, open_model, save_project
from grafcet.profile import APP_VERSION, SEMANTIC_OPTIONS, normalize_options
from grafcet.timeutil import parse_duration
from grafcet.view import Vista, auto_layout, layout_from_presentation, presentation_for, t_trunc

from .diagrama import COL, VistaDiagrama

TITULO = "Simulador GRAFCET"
TICK_MS = 100  # tiempo real: cada cuánto se avanza el tiempo lógico
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
    def __init__(self, ajustes: QSettings | None = None) -> None:
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
        a = archivo.addAction("&Abrir modelo…", self.abrir)
        a.setShortcut(QKeySequence.StandardKey.Open)
        self.a_guardar = archivo.addAction("&Guardar como proyecto…", self.guardar)
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
        self.a_derecho = self._accion("Panel &derecho", lambda on: self._mostrar_panel("derecho", on), "Ctrl+B", True)
        self.a_inferior = self._accion("Panel &inferior", lambda on: self._mostrar_panel("inferior", on), "Ctrl+J", True)
        ver.addAction(self.a_derecho)
        ver.addAction(self.a_inferior)
        ver.addSeparator()
        ver.addAction(self._accion("&Acercar", lambda: self.diagrama.acercar(), ["Ctrl+=", "Ctrl++"]))
        ver.addAction(self._accion("A&lejar", lambda: self.diagrama.alejar(), "Ctrl+-"))
        ver.addAction(self._accion("A&justar el dibujo", lambda: self.diagrama.ajustar(), "Ctrl+0"))
        sim = bar.addMenu("&Simulación")
        for a in (self.a_ejecutar, self.a_paso, self.a_completar, self.a_reiniciar):
            sim.addAction(a)
        sim.addSeparator()
        sim.addAction("&Avanzar el tiempo…", self.avanzar_tiempo).setToolTip("Herramienta de depuración")
        m_ajustes = bar.addMenu("A&justes")
        m_ajustes.addAction("&Lecturas de interpretación…", self.lecturas)
        ayuda = bar.addMenu("A&yuda")
        ayuda.addAction("&Leyenda del dibujo", lambda: self.pestanas.setCurrentIndex(1))
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
        vsplit = QSplitter(Qt.Orientation.Vertical)
        vsplit.addWidget(self.diagrama)
        self.pestanas = QTabWidget()
        self.traza = QListWidget()
        self.traza.setWordWrap(True)
        self.pestanas.addTab(self.traza, "Traza")
        leyenda = QLabel(LEYENDA)
        leyenda.setWordWrap(True)
        leyenda.setAlignment(Qt.AlignmentFlag.AlignTop)
        leyenda.setMargin(8)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(leyenda)
        self.pestanas.addTab(sc, "Leyenda")
        vsplit.addWidget(self.pestanas)
        vsplit.setSizes([620, 200])
        il.addWidget(vsplit, 1)

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
        self.scroll.setMinimumWidth(400)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vsplit = vsplit
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(izq)
        self.split.addWidget(self.scroll)
        self.split.setSizes([880, 460])
        self.setCentralWidget(self.split)
        # Barra de estado: aviso de conformidad, lecturas distintas de las decididas, instante lógico
        sb = self.statusBar()
        self.l_aviso = QLabel(AVISO)
        self.l_lect = QLabel()
        self.l_lect.setStyleSheet(f"color: {COL['err']}")
        self.l_reloj = QLabel()
        self.l_reloj.setStyleSheet("font-weight: 600")
        sb.addWidget(self.l_aviso, 1)
        sb.addPermanentWidget(self.l_lect)
        sb.addPermanentWidget(self.l_reloj)

    def _barra_herramientas(self) -> None:
        tb = QToolBar("Simulación")
        tb.setMovable(False)
        tb.setObjectName("barra-simulacion")
        for a in (self.a_ejecutar, self.a_paso, self.a_completar):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.a_reiniciar)
        self.addToolBar(tb)

    def _paneles(self) -> None:
        """Flechas en el borde del dibujo para plegar del todo el panel derecho y el inferior, y el estado guardado."""
        self.flechas = {}
        for nombre, lugar in (("derecho", "derecha"), ("inferior", "abajo")):
            b = QToolButton()
            b.clicked.connect(lambda _=False, n=nombre: self._mostrar_panel(n, self._panel(n).isHidden()))
            self.diagrama.borde(b, lugar)
            self.flechas[nombre] = b
        for nombre, accion in (("derecho", self.a_derecho), ("inferior", self.a_inferior)):
            visible = self.ajustes.value(f"paneles/{nombre}", True, type=bool)
            accion.blockSignals(True)
            accion.setChecked(visible)
            accion.blockSignals(False)
            self._mostrar_panel(nombre, visible, guardar=False)

    def _panel(self, nombre: str) -> QWidget:
        return self.scroll if nombre == "derecho" else self.pestanas

    def _mostrar_panel(self, nombre: str, visible: bool, guardar: bool = True) -> None:
        self._panel(nombre).setVisible(visible)
        accion = self.a_derecho if nombre == "derecho" else self.a_inferior
        if accion.isChecked() != visible:
            accion.blockSignals(True)
            accion.setChecked(visible)
            accion.blockSignals(False)
        # La flecha apunta hacia donde se pliega el panel y, plegado, hacia donde se despliega
        self.flechas[nombre].setText(("▸" if visible else "◂") if nombre == "derecho" else ("▾" if visible else "▴"))
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
        self.fuente = {"tipo": "ejemplo", "clave": key}
        self.acciones_ej[key].setChecked(True)
        self._cargar()

    def abrir_ruta(self, ruta: Path) -> bool:
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
        self.fuente = {"tipo": "fichero", "ruta": ruta, "doc": op.doc, "layout": layout, "titulo": op.title,
                       "ayuda": ayuda}
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
            else:
                self.v = Vista(f["ruta"].stem, f["titulo"], f["ayuda"], lambda: (f["doc"], f["layout"]), self.options)
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
    def guardar(self) -> None:
        """Guarda el modelo en curso, con sus posiciones, como proyecto (documento 09) que luego puede abrirse."""
        f = self.fuente
        base = QFileDialog.getExistingDirectory(self, "Carpeta donde crear el proyecto")
        if not base:
            return
        name = f["clave"] if f["tipo"] == "ejemplo" else f["ruta"].stem
        destino = Path(base) / re.sub(r"[^A-Za-z0-9._-]", "-", name)
        if destino.exists() and any(destino.iterdir()):
            r = QMessageBox.question(self, TITULO, f"{destino} ya existe y no está vacía. ¿Sobrescribir el proyecto?")
            if r != QMessageBox.StandardButton.Yes:
                return
        try:
            self.guardar_en(destino)
        except (DiagnosticError, OSError) as exc:
            QMessageBox.warning(self, TITULO, f"No se pudo guardar:\n\n{exc}")
            return
        self.statusBar().showMessage(f"Proyecto guardado en {destino}", 8000)

    def guardar_en(self, destino: Path) -> None:
        f, doc = self.fuente, self.v.doc
        if f["tipo"] == "ejemplo":
            layout = EJEMPLOS[f["clave"]][2]()[1]
        else:
            layout = {**auto_layout(doc), **f["layout"]}
        ident = re.sub(r"[^A-Za-z0-9._-]", "-", destino.name)[:120] or "proyecto"
        project = new_project(ident, self.v.model["title"])
        add_document(project, doc)
        add_document(project, presentation_for(doc, layout))
        save_project(destino, project)

    def guardar_imagen(self) -> None:
        from .diagrama import imagen
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar el dibujo", f"{self.v.key}.png", "Imagen PNG (*.png)")
        if ruta and not imagen(self.v.model, self.v.state()).save(ruta):
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
    if args.ejemplo:
        w.cargar_ejemplo(args.ejemplo)
    if args.modelo and not w.abrir_ruta(Path(args.modelo)):
        return 1 if args.captura else 0
    w.show()
    if args.captura:
        QTimer.singleShot(300, lambda: (w.grab().save(args.captura), app.quit()))
    return app.exec()
