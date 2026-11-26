"""Configuración directa: tiempos y exclusiones por ID, separada del controlador."""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from conexion import filtro_directo as filtro
from . import estilo
from .componentes_comunes import CabeceraDialogo, PieDialogo
from .estilo_config_es import crear_tarjeta, hoja_dialogo_es

AYUDA_UNIDAS = "Las señales ya unidas siguen mostrándose y funcionando, aunque estén marcadas en esta lista."


class ConfiguracionDirecta(QDialog):
    def __init__(self, controlador):
        super().__init__(controlador.panel)
        from .entradas_salidas import _SpinConfiguracion
        self.setWindowTitle("Configuración de conexión directa")
        self.setStyleSheet(estilo.hoja_global() + hoja_dialogo_es())
        self.config = deepcopy(controlador.panel.config)
        self.catalogo = controlador.catalogo
        if not self.config.filtro_senales:
            filtro.actualizar(self.config, self.catalogo)
        self.cambiando = False
        self.controles = {}
        self.etiquetas_tiempos = {}
        self._ancho_objetivo = min(840, max(500, controlador.panel.window().width() - 32))
        self.setMinimumWidth(500)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(CabeceraDialogo(self.windowTitle()))
        contenido = QVBoxLayout()
        contenido.setContentsMargins(estilo.E4, estilo.E3, estilo.E4, estilo.E3)
        contenido.setSpacing(estilo.E2)
        raiz.addLayout(contenido, 1)
        tarjeta_tiempos, lay_tiempos = crear_tarjeta("Tiempos de lectura", self)
        fila_tiempos = QHBoxLayout()
        fila_tiempos.setContentsMargins(0, 0, 0, 0)
        fila_tiempos.setSpacing(24)
        for nombre, texto, minimo in (("periodo_ms", "Periodo (ms)", 5), ("timeout_ms", "Tiempo de espera (ms)", 10)):
            col = QVBoxLayout()
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(4)
            etiq = QLabel(texto)
            etiq.setStyleSheet(f"color:{estilo.TINTA_2}; font-weight:600; font-size:{estilo.T_PEQUENA}px;")
            spin = _SpinConfiguracion()
            spin.setRange(minimo, 10000)
            spin.setValue(getattr(self.config, nombre))
            self.controles[nombre] = spin
            self.etiquetas_tiempos[nombre] = etiq
            col.addWidget(etiq)
            col.addWidget(spin, 0, Qt.AlignmentFlag.AlignLeft)
            fila_tiempos.addLayout(col)
        fila_tiempos.addStretch(1)
        lay_tiempos.addLayout(fila_tiempos)
        contenido.addWidget(tarjeta_tiempos)
        self.avanzado = QWidget()
        self._crear_avanzado()
        contenido.addWidget(self.avanzado, 1)
        pie = PieDialogo().conectar(self)
        self.b_cancelar = pie.boton_cancelar
        self.b_aceptar = pie.boton_aceptar
        raiz.addWidget(pie)
        self.rellenar()
        self.layout().activate()
        self.adjustSize()
        alto_max = max(440, controlador.panel.window().height() - 48)
        self.resize(self._ancho_objetivo, min(self.sizeHint().height(), alto_max))

    def _crear_avanzado(self):
        exterior = QVBoxLayout(self.avanzado)
        exterior.setContentsMargins(0, 0, 0, 0)
        exterior.setSpacing(0)
        tarjeta, layout = crear_tarjeta("Señales que no se traen", self.avanzado, AYUDA_UNIDAS)
        exterior.addWidget(tarjeta)
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Excluir", "ID", "Señal", "Tipo"])
        self.tabla.verticalHeader().hide()
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setMinimumHeight(140)
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
        self.identidad.lineEdit().setPlaceholderText("ID o elige una señal de la última lectura")
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
