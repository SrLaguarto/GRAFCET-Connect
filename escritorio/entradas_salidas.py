"""Panel horizontal de E/S externas y configuración del mapa Modbus."""
from fractions import Fraction

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from conexion.configuracion import Configuracion, Senal


class PanelES(QWidget):
    aplicar = Signal(object)
    conectar = Signal()
    desconectar = Signal()
    probar = Signal()
    guardar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = None
        self.config = Configuracion()
        self.indicadores = {}
        raiz = QVBoxLayout(self)
        self.estado = QLabel("Desconectado · configuración local, sin red")
        raiz.addWidget(self.estado)
        self.modulo = QFrame()
        self.modulo.setObjectName("moduloPLC")
        self.modulo.setStyleSheet("QFrame#moduloPLC {background:#26333d; border:2px solid #75828a; border-radius:8px;}"
                                 "QLabel {color:#edf1f3;} QFrame#senalPLC {border:1px solid #75828a; border-radius:4px;}")
        cuerpo = QVBoxLayout(self.modulo)
        cuerpo.addWidget(QLabel("ENTRADAS · sensores → GRAFCET"))
        self.fila_entradas = QHBoxLayout()
        cuerpo.addLayout(self.fila_entradas)
        marca = QLabel("GrafConnect  |  E/S EXTERNAS  |  MODBUS TCP")
        marca.setAlignment(Qt.AlignmentFlag.AlignCenter)
        marca.setMinimumHeight(48)
        cuerpo.addWidget(marca)
        self.fila_salidas = QHBoxLayout()
        cuerpo.addLayout(self.fila_salidas)
        cuerpo.addWidget(QLabel("SALIDAS · GRAFCET → actuadores"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.modulo)
        scroll.setMinimumHeight(280)
        raiz.addWidget(scroll, 1)
        self.config_widget = QWidget()
        configuracion = QVBoxLayout(self.config_widget)
        endpoint = QHBoxLayout()
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
        for texto, widget in (("IP / host", self.host), ("Puerto", self.puerto), ("Unidad", self.unidad),
                              ("Periodo", self.periodo), ("Espera", self.timeout)):
            f = QFormLayout()
            f.addRow(texto, widget)
            endpoint.addLayout(f)
        configuracion.addLayout(endpoint)
        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels(["Usar", "Variable", "Papel", "Tipo", "Área", "Dirección (base 0)", "Formato", "Escala"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setMinimumHeight(150)
        configuracion.addWidget(self.tabla)
        raiz.addWidget(self.config_widget)
        botones = QHBoxLayout()
        self.b_aplicar = QPushButton("Aplicar mapa")
        self.b_aplicar.clicked.connect(self._aplicar)
        self.b_guardar = QPushButton("Guardar configuración…")
        self.b_guardar.clicked.connect(self.guardar)
        self.b_probar = QPushButton("Probar conexión")
        self.b_probar.clicked.connect(self.probar)
        self.b_conectar = QPushButton("Conectar")
        self.b_conectar.clicked.connect(self.conectar)
        self.b_desconectar = QPushButton("Desconectar")
        self.b_desconectar.clicked.connect(self.desconectar)
        self.b_desconectar.setEnabled(False)
        for b in (self.b_aplicar, self.b_guardar, self.b_probar, self.b_conectar, self.b_desconectar):
            botones.addWidget(b)
        raiz.addLayout(botones)
        nota = QLabel("Factory I/O: driver Modbus TCP/IP Server. Escala: valor GRAFCET = registro / escala. "
                      "Los pulsos más cortos que el intervalo efectivo pueden perderse.")
        nota.setWordWrap(True)
        raiz.addWidget(nota)

    def cargar(self, doc, config=None):
        self.doc = doc
        self.config = config or Configuracion(modelo=doc["id"])
        c = self.config
        self.host.setText(c.host)
        for w, valor in ((self.puerto, c.puerto), (self.unidad, c.unidad), (self.periodo, c.periodo_ms), (self.timeout, c.timeout_ms)):
            w.setValue(valor)
        self.variables = [v for v in doc["variables"] if v["role"] in ("input", "output")]
        mapa = {s.variable: s for s in c.senales}
        self.tabla.setRowCount(len(self.variables))
        for fila, v in enumerate(self.variables):
            s = mapa.get(v["id"])
            digital = v["type"]["kind"] == "bool"
            usar = QCheckBox()
            usar.setChecked(s is not None)
            usar.setEnabled(v["type"]["kind"] in ("bool", "int", "decimal"))
            self.tabla.setCellWidget(fila, 0, usar)
            for col, texto in ((1, v["name"]), (2, "Entrada" if v["role"] == "input" else "Salida"), (3, v["type"]["kind"])):
                item = QTableWidgetItem(texto)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setToolTip(v["id"])
                self.tabla.setItem(fila, col, item)
            area = QComboBox()
            area.addItems((["discrete", "coil"] if digital else ["input-register", "holding"])
                          if v["role"] == "input" else (["coil"] if digital else ["holding"]))
            area.setCurrentText(s.area if s else area.itemText(0))
            self.tabla.setCellWidget(fila, 4, area)
            direccion = QSpinBox()
            direccion.setRange(0, 65535)
            direccion.setValue(s.direccion if s else fila)
            self.tabla.setCellWidget(fila, 5, direccion)
            formato = QComboBox()
            formato.addItems(["BOOL"] if digital else ["INT16", "UINT16"])
            formato.setCurrentText(s.formato if s else formato.itemText(0))
            self.tabla.setCellWidget(fila, 6, formato)
            self.tabla.setCellWidget(fila, 7, QLineEdit(s.escala if s else "1"))
        self.tabla.resizeColumnsToContents()
        self._dibujar()

    def obtener(self):
        senales = []
        for fila, v in enumerate(self.variables):
            if self.tabla.cellWidget(fila, 0).isChecked():
                senales.append(Senal(v["id"], self.tabla.cellWidget(fila, 4).currentText(),
                                     self.tabla.cellWidget(fila, 5).value(), self.tabla.cellWidget(fila, 6).currentText(),
                                     self.tabla.cellWidget(fila, 7).text()))
        c = Configuracion(self.host.text().strip(), self.puerto.value(), self.unidad.value(),
                          self.periodo.value(), self.timeout.value(), self.doc["id"], senales)
        c.validar(self.doc)
        return c

    def _aplicar(self):
        try:
            c = self.obtener()
        except ValueError as exc:
            self.estado.setText(f"Mapa inválido: {exc}")
            return
        self.config = c
        self._dibujar()
        self.aplicar.emit(c)

    def _dibujar(self):
        self.indicadores.clear()
        for fila in (self.fila_entradas, self.fila_salidas):
            while fila.count():
                item = fila.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        variables = {v["id"]: v for v in self.variables}
        for s in self.config.senales:
            v = variables.get(s.variable)
            if not v:
                continue
            tarjeta = QFrame()
            tarjeta.setObjectName("senalPLC")
            tarjeta.setMinimumWidth(116)
            l = QVBoxLayout(tarjeta)
            punto = QLabel("●  ○  ○")
            punto.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nombre = QLabel(v["name"])
            nombre.setAlignment(Qt.AlignmentFlag.AlignCenter)
            valor = QLabel("—")
            valor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for w in (punto, nombre, QLabel(f"{s.formato} · {s.area}:{s.direccion}"), valor):
                l.addWidget(w)
            tarjeta.setToolTip(f"{v['name']} ({s.variable}) · escala {s.escala}")
            (self.fila_entradas if v["role"] == "input" else self.fila_salidas).addWidget(tarjeta)
            self.indicadores[s.variable] = (punto, valor)
        self.fila_entradas.addStretch()
        self.fila_salidas.addStretch()

    def mostrar_valores(self, valores):
        for vid, (led, etiqueta) in self.indicadores.items():
            valor = valores.get(vid)
            if valor is None:
                etiqueta.setText("—")
                color = "#87939c"
            else:
                etiqueta.setText(str(int(valor)) if type(valor) is bool else str(valor))
                color = "#58ed91" if valor else "#87939c"
            led.setStyleSheet(f"color:{color}; font-size:18px")

    def ocupado(self, on):
        self.config_widget.setEnabled(not on)
        for b in (self.b_aplicar, self.b_guardar, self.b_probar, self.b_conectar):
            b.setEnabled(not on)
        self.b_desconectar.setEnabled(on)
