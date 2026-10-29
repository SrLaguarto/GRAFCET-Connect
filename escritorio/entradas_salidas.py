"""Panel horizontal de E/S externas y configuración del mapa Modbus."""
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
                               QAbstractItemView, QMenu, QInputDialog)

from conexion.configuracion import Configuracion, Senal

AREAS = {"discrete": "Inputs (entradas digitales 0/1)",
         "coil": "Coils (señales digitales 0/1)",
         "input-register": "Input Registers (números de entrada)",
         "holding": "Holding Registers (números modificables)"}
FORMATOS = {"BOOL": "BOOL (apagado/encendido)", "INT16": "INT16 (entero con signo)",
            "UINT16": "UINT16 (entero sin signo)"}
TIPOS = {"bool": "Booleana (0/1)", "int": "Entera", "decimal": "Decimal", "duration": "Duración"}
MIME_VARIABLE = "application/x-grafconnect-variable"


class ListaVariables(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def mimeData(self, items):
        datos = QMimeData()
        if items:
            datos.setData(MIME_VARIABLE, items[0].data(Qt.ItemDataRole.UserRole).encode("utf-8"))
        return datos


class TerminalES(QFrame):
    def __init__(self, panel, area, direccion, variable=None):
        super().__init__()
        self.panel, self.area, self.direccion, self.variable = panel, area, direccion, variable
        self.setAcceptDrops(not panel.bloqueado)
        self.setObjectName("senalPLC")
        self.setMinimumWidth(116)
        l = QVBoxLayout(self)
        prefijo = {"discrete": "I", "coil": "Q", "input-register": "AI", "holding": "AQ"}[area]
        self.led = QLabel(f"●  {prefijo}{direccion:02}")
        self.led.setStyleSheet("color:#87939c; font-size:18px")
        self.nombre = QLabel(variable["name"] if variable else "Arrastra aquí")
        self.valor = QLabel("—" if variable else "")
        for w in (self.led, self.nombre, self.valor):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(w)
        self.setToolTip(f"{AREAS[area]} · dirección {direccion}\nArrastra una variable. Botón derecho para quitar o configurar.")

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
            evento.acceptProposedAction()

    def dropEvent(self, evento):
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


class EstadoConexion(QLabel):
    def setText(self, texto):
        self.setToolTip(texto)
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
        super().setText(corto)


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = None
        self.config = Configuracion()
        self.indicadores = {}
        self.terminales = {}
        self.bloqueado = False
        self.extras = {a: set() for a in AREAS}
        raiz = QVBoxLayout(self)
        self.estado = EstadoConexion()
        self.estado.setText("Desconectado")
        self.estado.setWordWrap(True)
        cabecera = QHBoxLayout()
        cabecera.addWidget(QLabel("Modbus TCP"))
        self.check = QLabel("●")
        self.check.setStyleSheet("color:#87939c; font-size:22px")
        cabecera.addWidget(self.check)
        cabecera.addWidget(self.estado, 1)
        self.b_prueba_guiada = QPushButton("Abrir prueba guiada")
        self.b_prueba_guiada.clicked.connect(self.abrir_prueba)
        self.b_configuracion = QPushButton("Configuración")
        self.b_configuracion.clicked.connect(self.abrir_configuracion)
        raiz.addLayout(cabecera)
        self.modulo = QFrame()
        self.modulo.setObjectName("moduloPLC")
        self.modulo.setStyleSheet("QFrame#moduloPLC {background:#26333d; border:2px solid #75828a; border-radius:8px;}"
                                 "QLabel {color:#edf1f3;} QFrame#senalPLC {border:1px solid #75828a; border-radius:4px;}")
        cuerpo = QVBoxLayout(self.modulo)
        self.ayuda_vacio = QLabel("Arrastra las variables a las entradas y salidas.")
        self.ayuda_vacio.setWordWrap(True)
        cuerpo.addWidget(self.ayuda_vacio)
        cuerpo.addWidget(QLabel("ENTRADAS · sensores → GRAFCET"))
        self.fila_entradas = QHBoxLayout()
        cuerpo.addLayout(self.fila_entradas)
        marca = QLabel("E/S")
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
        zona = QHBoxLayout()
        listas = QVBoxLayout()
        self.lista_entradas, self.lista_salidas = ListaVariables(), ListaVariables()
        for titulo, lista in (("Entradas", self.lista_entradas), ("Salidas", self.lista_salidas)):
            listas.addWidget(QLabel(titulo))
            lista.setFixedWidth(180)
            listas.addWidget(lista, 1)
        zona.addLayout(listas)
        zona.addWidget(scroll, 1)
        raiz.addLayout(zona, 1)
        self.dialogo_config = DialogoConfiguracion(self)
        self.dialogo_config.setWindowTitle("Configuración Modbus TCP")
        self.dialogo_config.resize(1050, 480)
        self.b_prueba_guiada.clicked.connect(self.dialogo_config.hide)
        ajustes = QVBoxLayout(self.dialogo_config)
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
        self.b_desconectar = QPushButton("Desconectar")
        self.b_desconectar.clicked.connect(self.desconectar)
        self.b_desconectar.setEnabled(False)
        for b in (self.b_aplicar, self.b_cargar, self.b_guardar, self.b_probar, self.b_prueba_guiada):
            botones.addWidget(b)
        ajustes.addLayout(botones)
        for b in (self.b_conectar, self.b_desconectar, self.b_configuracion):
            cabecera.addWidget(b)
        self.b_desconectar.hide()
        nota = QLabel("Factory I/O: driver Modbus TCP/IP Server. Escala: valor GRAFCET = registro / escala. "
                      "Los pulsos más cortos que el intervalo efectivo pueden perderse.")
        nota.setWordWrap(True)
        ajustes.addWidget(nota)
        self.error_config = QLabel()
        self.error_config.setWordWrap(True)
        self.error_config.setStyleSheet("color:#b13d3d")
        ajustes.addWidget(self.error_config)
        cerrar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cerrar.rejected.connect(self._cerrar_configuracion)
        ajustes.addWidget(cerrar)

    def abrir_configuracion(self):
        self.dialogo_config.show()
        self.dialogo_config.raise_()

    def _cerrar_configuracion(self):
        self.dialogo_config.close()

    def mostrar_estado(self, estado, mensaje):
        self.estado.setText(mensaje)
        conectado = estado == "conectado"
        self.check.setText("✓" if conectado else "✕" if estado in ("error", "diagnostico") else "●")
        self.check.setStyleSheet(f"color:{'#24a565' if conectado else '#c84b4b' if estado in ('error','diagnostico') else '#87939c'}; font-size:22px; font-weight:600")
        self.check.setToolTip(mensaje)

    def admite(self, vid, area):
        v = next((v for v in self.variables if v["id"] == vid), None)
        return bool(v and not self.bloqueado and v["role"] == ("input" if area in ("discrete", "input-register") else "output")
                    and (v["type"]["kind"] == "bool" if area in ("discrete", "coil") else v["type"]["kind"] in ("int", "decimal")))

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

    def agregar_terminal(self, area):
        direccion, ok = QInputDialog.getInt(self, "Añadir terminal", "Dirección (empieza en 0)", 4, 0, 65535)
        if ok:
            self.extras[area].add(direccion)
            self._dibujar()

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
            self.error_config.setText(f"Mapa inválido: {exc}")
            return False
        self.error_config.clear()
        self.config = c
        self._dibujar()
        self.estado.setText("Mapa aplicado · desconectado. Pulsa «Probar conexión» y después «Conectar».")
        self.aplicar.emit(c)
        return True

    def _dibujar(self):
        self.indicadores.clear()
        self.terminales.clear()
        self.ayuda_vacio.setVisible(not self.config.senales)
        for fila in (self.fila_entradas, self.fila_salidas):
            while fila.count():
                item = fila.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        variables = {v["id"]: v for v in self.variables}
        self.lista_entradas.clear()
        self.lista_salidas.clear()
        for v in self.variables:
            item = QListWidgetItem(v["name"])
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            item.setToolTip(TIPOS[v["type"]["kind"]])
            if v["type"]["kind"] == "duration":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            (self.lista_entradas if v["role"] == "input" else self.lista_salidas).addItem(item)
        mapa = {(s.area, s.direccion): s for s in self.config.senales}
        for area in AREAS:
            numerica = area in ("input-register", "holding")
            entrada = area in ("discrete", "input-register")
            if numerica and not any(v["type"]["kind"] in ("int", "decimal") and v["role"] == ("input" if entrada else "output") for v in self.variables):
                continue
            direcciones = set(range(2 if numerica else 4)) | self.extras[area] | {d for a, d in mapa if a == area}
            fila = self.fila_entradas if entrada else self.fila_salidas
            for direccion in sorted(direcciones):
                s = mapa.get((area, direccion))
                v = variables.get(s.variable) if s else None
                terminal = TerminalES(self, area, direccion, v)
                fila.addWidget(terminal)
                self.terminales[(area, direccion)] = terminal
                if v:
                    self.indicadores[v["id"]] = (terminal.led, terminal.valor)
            mas = QPushButton("+")
            mas.setFixedWidth(28)
            mas.setToolTip(f"Añadir terminal: {AREAS[area]}")
            mas.setEnabled(not self.bloqueado)
            mas.clicked.connect(lambda _=False, a=area: self.agregar_terminal(a))
            fila.addWidget(mas)
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
        self.bloqueado = on
        self.lista_entradas.setDragEnabled(not on)
        self.lista_salidas.setDragEnabled(not on)
        for terminal in self.terminales.values():
            terminal.setAcceptDrops(not on)
        for fila in (self.fila_entradas, self.fila_salidas):
            for i in range(fila.count()):
                widget = fila.itemAt(i).widget()
                if isinstance(widget, QPushButton):
                    widget.setEnabled(not on)
        self.b_conectar.setVisible(not on)
        self.b_desconectar.setVisible(on)
        self.b_prueba_guiada.setEnabled(not on)
        self.config_widget.setEnabled(not on)
        for b in (self.b_aplicar, self.b_cargar, self.b_guardar, self.b_probar, self.b_conectar):
            b.setEnabled(not on)
        self.b_desconectar.setEnabled(on)
