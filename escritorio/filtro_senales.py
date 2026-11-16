"""Configuración directa: tiempos y exclusiones por ID, separada del controlador."""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from conexion import filtro_directo as filtro
from . import estilo

AYUDA_UNIDAS = "Las señales ya unidas siguen mostrándose y funcionando, aunque estén marcadas en esta lista."


class ConfiguracionDirecta(QDialog):
    def __init__(self, controlador):
        super().__init__(controlador.panel)
        from .entradas_salidas import _SpinConfiguracion
        self.setWindowTitle("Configuración de conexión directa")
        self.setStyleSheet(estilo.hoja_global())
        self.config = deepcopy(controlador.panel.config)
        self.catalogo = controlador.catalogo
        if not self.config.filtro_senales:
            filtro.actualizar(self.config, self.catalogo)
        self.cambiando = False
        self.controles = {}
        self.resize(min(840, max(500, controlador.panel.window().width() - 32)), 440)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(estilo.E2, estilo.E2, estilo.E2, estilo.E2)
        form = QFormLayout()
        for nombre, texto, minimo in (("periodo_ms", "Periodo (ms)", 5), ("timeout_ms", "Tiempo de espera (ms)", 10)):
            spin = _SpinConfiguracion()
            spin.setRange(minimo, 10000)
            spin.setValue(getattr(self.config, nombre))
            self.controles[nombre] = spin
            form.addRow(texto, spin)
        raiz.addLayout(form)
        self.b_avanzado = QPushButton("Opciones avanzadas ›")
        self.b_avanzado.setCheckable(True)
        raiz.addWidget(self.b_avanzado, 0, Qt.AlignmentFlag.AlignLeft)
        self.avanzado = QWidget()
        self._crear_avanzado()
        raiz.addWidget(self.avanzado)
        self.avanzado.hide()
        self.b_avanzado.toggled.connect(self.avanzado.setVisible)
        self.botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.botones.button(QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
        self.botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.botones.accepted.connect(self.accept)
        self.botones.rejected.connect(self.reject)
        raiz.addWidget(self.botones)
        self.rellenar()

    def _crear_avanzado(self):
        layout = QVBoxLayout(self.avanzado)
        layout.setContentsMargins(0, estilo.E2, 0, 0)
        from .paneles import TituloSeccion
        titulo = TituloSeccion("Señales que no se traen")
        titulo.setToolTip(AYUDA_UNIDAS)
        layout.addWidget(titulo)
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Excluir", "ID", "Señal", "Tipo"])
        self.tabla.verticalHeader().hide()
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setMinimumHeight(155)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 64)
        self.tabla.setColumnWidth(1, 270)
        self.tabla.setColumnWidth(3, 75)
        self.tabla.itemChanged.connect(self.cambiar)
        layout.addWidget(self.tabla)
        fila = QHBoxLayout()
        self.identidad = QComboBox()
        self.identidad.setEditable(True)
        self.identidad.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.identidad.setMinimumWidth(100)
        self.identidad.addItem("", "")
        self.identidad.lineEdit().setPlaceholderText("ID o elija una señal de la última lectura")
        for senal in self.catalogo:
            self.identidad.addItem(f'{senal["name"]} · {senal["type"]}', senal["id"])
        self.b_anadir = QPushButton("Añadir")
        self.b_anadir.clicked.connect(self.anadir)
        fila.addWidget(self.identidad, 1)
        fila.addWidget(self.b_anadir)
        layout.addLayout(fila)
        acciones = QHBoxLayout()
        self.b_quitar = QPushButton("Quitar")
        self.b_quitar.clicked.connect(self.quitar)
        self.b_ausentes = QPushButton("Quitar las que no están")
        self.b_ausentes.clicked.connect(self.quitar_ausentes)
        self.recordar = QCheckBox("Recordar mi selección")
        self.recordar.setChecked(self.config.recordar_filtro)
        self.recordar.setToolTip(
            "Sin marcar, la siguiente lectura vuelve a la lista inicial. Marcado, se guarda con el proyecto.")
        self.recordar.toggled.connect(self.cambiar_recuerdo)
        acciones.addWidget(self.recordar)
        acciones.addStretch()
        acciones.addWidget(self.b_quitar)
        acciones.addWidget(self.b_ausentes)
        layout.addLayout(acciones)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"color:{estilo.ERROR}")
        layout.addWidget(self.aviso)

    def rellenar(self):
        self.cambiando = True
        filas = [f for f in self.config.filtro_senales if not f.get("quitada", False)]
        presentes = {s["id"] for s in self.catalogo}
        self.tabla.setRowCount(len(filas))
        tipos = {"bit": "Booleana", "int": "Entera", "float": "Decimal"}
        for row, fila in enumerate(filas):
            nombre = fila.get("nombre", "")
            if fila["id"] not in presentes:
                nombre += " · no está en la escena abierta"
            textos = ("", fila["id"], nombre, tipos.get(fila.get("tipo", "").lower(), ""))
            for col, texto in enumerate(textos):
                item = QTableWidgetItem(texto)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setToolTip((texto + "\n" + AYUDA_UNIDAS).strip())
                if col == 0:
                    from .entradas_salidas import _CasillaCentrada
                    casilla = _CasillaCentrada()
                    casilla.setChecked(fila["excluir"])
                    casilla.setToolTip(AYUDA_UNIDAS)
                    casilla.toggled.connect(lambda on, fila=fila: fila.update(excluir=on))
                    self.tabla.setCellWidget(row, col, casilla)
                    item.setData(Qt.ItemDataRole.UserRole, fila["id"])
                if fila["id"] not in presentes:
                    item.setForeground(QColor(estilo.TINTA_3))
                self.tabla.setItem(row, col, item)
        self.cambiando = False

    def cambiar(self, item):
        if not self.cambiando and item.column() == 0:
            identidad = item.data(Qt.ItemDataRole.UserRole)
            for fila in self.config.filtro_senales:
                if fila["id"] == identidad:
                    fila["excluir"] = item.checkState() == Qt.CheckState.Checked

    def cambiar_recuerdo(self, recordar):
        self.config.recordar_filtro = recordar

    def anadir(self):
        texto = self.identidad.currentText().strip()
        identidad = self.identidad.currentData() if self.identidad.findText(texto) >= 0 else texto
        try:
            filtro.anadir(self.config, identidad or "", self.catalogo)
        except ValueError as exc:
            self.aviso.setText(str(exc))
            return
        self.aviso.clear()
        self.rellenar()

    def quitar(self):
        row = self.tabla.currentRow()
        if row >= 0:
            filtro.quitar(self.config, self.tabla.item(row, 0).data(Qt.ItemDataRole.UserRole))
            self.rellenar()

    def quitar_ausentes(self):
        presentes = {s["id"] for s in self.catalogo}
        self.config.filtro_senales = [f for f in self.config.filtro_senales if f["id"] in presentes]
        self.rellenar()

    def accept(self):
        for nombre, control in self.controles.items():
            setattr(self.config, nombre, control.value())
        super().accept()
