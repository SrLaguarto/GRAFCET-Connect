"""Panel horizontal de E/S externas y configuración del mapa Modbus."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from conexion.configuracion import Configuracion, Senal

AREAS = {"discrete": "Inputs (entradas digitales 0/1)",
         "coil": "Coils (señales digitales 0/1)",
         "input-register": "Input Registers (números de entrada)",
         "holding": "Holding Registers (números modificables)"}
FORMATOS = {"BOOL": "BOOL (apagado/encendido)", "INT16": "INT16 (entero con signo)",
            "UINT16": "UINT16 (entero sin signo)"}
TIPOS = {"bool": "Booleana (0/1)", "int": "Entera", "decimal": "Decimal", "duration": "Duración"}


class PanelES(QWidget):
    aplicar = Signal(object)
    conectar = Signal()
    desconectar = Signal()
    probar = Signal()
    guardar = Signal()
    cargar_archivo = Signal()
    abrir_prueba = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = None
        self.config = Configuracion()
        self.indicadores = {}
        raiz = QVBoxLayout(self)
        self.estado = QLabel("Desconectado · configuración local, sin red")
        self.estado.setWordWrap(True)
        cabecera = QHBoxLayout()
        cabecera.addWidget(self.estado, 1)
        self.b_prueba_guiada = QPushButton("Abrir prueba guiada")
        self.b_prueba_guiada.clicked.connect(self.abrir_prueba)
        cabecera.addWidget(self.b_prueba_guiada)
        raiz.addLayout(cabecera)
        self.modulo = QFrame()
        self.modulo.setObjectName("moduloPLC")
        self.modulo.setStyleSheet("QFrame#moduloPLC {background:#26333d; border:2px solid #75828a; border-radius:8px;}"
                                 "QLabel {color:#edf1f3;} QFrame#senalPLC {border:1px solid #75828a; border-radius:4px;}")
        cuerpo = QVBoxLayout(self.modulo)
        self.ayuda_vacio = QLabel("Sin señales asignadas. Marca las casillas «Usar» en la tabla inferior y pulsa «Aplicar mapa».")
        self.ayuda_vacio.setWordWrap(True)
        cuerpo.addWidget(self.ayuda_vacio)
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
        self.host.setToolTip("Copia el Host que muestra Factory I/O en CONFIGURACIÓN. Debe coincidir con el servidor activo.")
        self.unidad.setToolTip("El mismo número que «Esclavo ID» en Factory I/O; normalmente 1.")
        for texto, widget in (("IP (Host)", self.host), ("Puerto", self.puerto), ("Esclavo ID", self.unidad),
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
        self.b_cargar = QPushButton("Cargar configuración…")
        self.b_cargar.clicked.connect(self.cargar_archivo)
        self.b_probar = QPushButton("Probar conexión")
        self.b_probar.clicked.connect(self.probar)
        self.b_conectar = QPushButton("Conectar")
        self.b_conectar.clicked.connect(self.conectar)
        self.b_desconectar = QPushButton("Desconectar")
        self.b_desconectar.clicked.connect(self.desconectar)
        self.b_desconectar.setEnabled(False)
        for b in (self.b_aplicar, self.b_cargar, self.b_guardar, self.b_probar, self.b_conectar, self.b_desconectar):
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
            claves = ((["discrete", "coil"] if digital else ["input-register", "holding"])
                      if v["role"] == "input" else (["coil"] if digital else ["holding"]))
            for clave in claves:
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
            self.tabla.setCellWidget(fila, 7, QLineEdit(s.escala if s else "1"))
        self.tabla.resizeColumnsToContents()
        self._dibujar()

    def obtener(self):
        senales = []
        for fila, v in enumerate(self.variables):
            if self.tabla.cellWidget(fila, 0).isChecked():
                senales.append(Senal(v["id"], self.tabla.cellWidget(fila, 4).currentData(),
                                     self.tabla.cellWidget(fila, 5).value(), self.tabla.cellWidget(fila, 6).currentData(),
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
        self.estado.setText("Mapa aplicado · desconectado. Pulsa «Probar conexión» y después «Conectar».")
        self.aplicar.emit(c)

    def _dibujar(self):
        self.indicadores.clear()
        self.ayuda_vacio.setVisible(not self.config.senales)
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
            detalle = QLabel(f"{FORMATOS[s.formato]}\n{AREAS[s.area]} · {s.direccion}")
            detalle.setWordWrap(True)
            for w in (punto, nombre, detalle, valor):
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
        self.b_prueba_guiada.setEnabled(not on)
        self.config_widget.setEnabled(not on)
        for b in (self.b_aplicar, self.b_cargar, self.b_guardar, self.b_probar, self.b_conectar):
            b.setEnabled(not on)
        self.b_desconectar.setEnabled(on)
