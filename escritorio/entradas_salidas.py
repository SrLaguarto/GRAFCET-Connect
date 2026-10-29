"""Conexión de E/S: variables laterales y asignación sobre un módulo central."""
from PySide6.QtCore import Signal, Qt, QMimeData, QSize
from PySide6.QtGui import QDrag
from fractions import Fraction
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
                               QAbstractItemView, QMenu, QApplication, QGridLayout)

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
        self._inicio_arrastre = None
        self.setAcceptDrops(not panel.bloqueado)
        self.setObjectName("senalPLC")
        self.setMinimumWidth(205)
        self.setFixedHeight(60)
        l = QHBoxLayout(self)
        l.setContentsMargins(7, 2, 7, 2)
        l.setSpacing(7)
        prefijo = {"discrete": "I", "coil": "Q", "input-register": "AI", "holding": "AQ"}[area]
        canal = QLabel(f"{prefijo}{direccion:02}")
        canal.setFixedWidth(44)
        canal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canal.setStyleSheet("background:#293f50; color:#d5eaff; border:1px solid #4b687c; border-radius:5px; font-weight:600; font-size:13px")
        señal = QFrame()
        señal.setObjectName("asignacionES")
        señal.setStyleSheet("QFrame#asignacionES { background:#304c60; border:1px solid #587b94; border-radius:5px; }" if variable else
                            "QFrame#asignacionES { background:transparent; border:1px dashed #49687e; border-radius:5px; }")
        sl = QHBoxLayout(señal)
        sl.setContentsMargins(8, 4, 8, 4)
        sl.setSpacing(5)
        self.led = QLabel("●")
        self.led.setStyleSheet("color:#718393; font-size:17px")
        self.nombre = QLabel(variable["name"] if variable else "Sin asignar")
        self.nombre.setWordWrap(True)
        self.valor = QLabel("—" if variable else "")
        for etiqueta in (canal, self.led, self.nombre, self.valor):
            etiqueta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.nombre.setStyleSheet(f"color:{'#e0ecf7' if variable else '#80a1b8'}; font-size:14px; font-weight:{'600' if variable else '400'}")
        self.valor.setStyleSheet("color:#a7c3d7; font-size:11px")
        if variable:
            sl.addWidget(self.led)
        sl.addWidget(self.nombre, 1)
        if area in ("input-register", "holding"):
            sl.addWidget(self.valor)
        else:
            self.valor.hide()
        if area in ("coil", "holding"):
            l.addWidget(señal, 1)
            l.addWidget(canal)
        else:
            l.addWidget(canal)
            l.addWidget(señal, 1)
        self.b_quitar = None
        if variable:
            self.b_quitar = QPushButton("×")
            self.b_quitar.setFixedSize(22, 28)
            self.b_quitar.setStyleSheet("padding:0; color:#9cb5c8; font-size:18px; background:transparent")
            self.b_quitar.setToolTip("Desconecta para desasignar" if panel.bloqueado else "Desasignar esta señal")
            self.b_quitar.setEnabled(not panel.bloqueado)
            self.b_quitar.clicked.connect(lambda: panel.quitar(variable["id"]))
            l.addWidget(self.b_quitar)
        self.setToolTip(f"{AREAS[area]} · dirección {direccion}\nArrastra una variable. Botón derecho para quitar o configurar.")

    def mimeData(self):
        datos = QMimeData()
        if self.variable:
            datos.setData(MIME_VARIABLE, self.variable["id"].encode("utf-8"))
        return datos

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            self._inicio_arrastre = evento.position().toPoint()
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento):
        if self.panel.bloqueado or self.variable is None or self._inicio_arrastre is None:
            return
        if evento.buttons() & Qt.MouseButton.LeftButton and (evento.position().toPoint() - self._inicio_arrastre).manhattanLength() >= QApplication.startDragDistance():
            self._inicio_arrastre = None
            arrastre = QDrag(self.panel)
            arrastre.setMimeData(self.mimeData())
            arrastre.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.MoveAction)

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
            self.setStyleSheet("background:#3c5145; border-radius:4px")
            evento.acceptProposedAction()

    def dragLeaveEvent(self, evento):
        self.setStyleSheet("")
        evento.accept()

    def dropEvent(self, evento):
        self.setStyleSheet("")
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
    volver = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("conexionES")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#conexionES { background:#111c24; color:#dfedf8; }
            QWidget#conexionES QLabel { color:#cfdfed; background:transparent; }
            QFrame#cabeceraES { background:#111c24; border:0; border-bottom:1px solid #304655; }
            QFrame#moduloPLC { background:#1e303e; border:1px solid #4b667b; border-radius:10px; }
            QFrame#lateralES { background:#1a2a36; border:1px solid #344d60; border-radius:10px; }
            QFrame#senalPLC { border:0; background:transparent; border-radius:4px; }
            QFrame#senalPLC:hover { background:#294354; }
            QListWidget { background:transparent; border:0; outline:0; color:#dadbe3; font-size:13px; }
            QListWidget::item { padding:0; border-radius:6px; }
            QListWidget::item:hover { background:#304c61; }
            QListWidget::item:selected { background:#33566e; color:#e4f4ff; }
            QPushButton { background:transparent; color:#c8cad4; border:0; padding:7px 12px; border-radius:4px; }
            QPushButton:hover { background:#304c61; color:white; }
            QPushButton:disabled { color:#747680; }
            QScrollArea { background:transparent; border:0; }
            QDialog { background:#303034; color:#e9e9ee; }
        """)
        self.doc = None
        self.config = Configuracion()
        self.indicadores = {}
        self.indicadores_listas = {}
        self.terminales = {}
        self.bloqueado = False
        self.extras = {a: set() for a in AREAS}
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        self.estado = EstadoConexion()
        self.estado.setText("Desconectado")
        self.estado.setWordWrap(True)
        banda = QFrame()
        banda.setObjectName("cabeceraES")
        banda.setMinimumHeight(94)
        cabecera = QHBoxLayout(banda)
        cabecera.setContentsMargins(28, 12, 24, 12)
        cabecera.setSpacing(16)
        self.b_volver = QPushButton("←")
        self.b_volver.setFixedWidth(34)
        self.b_volver.setToolTip("Volver al GRAFCET")
        self.b_volver.setStyleSheet("font-size:23px; padding:0")
        self.b_volver.clicked.connect(self.volver)
        cabecera.addWidget(self.b_volver)
        textos = QVBoxLayout()
        titulo = QLabel("Asignación de E/S")
        titulo.setStyleSheet("font-size:20px; color:#eff7ff; font-weight:600")
        textos.addWidget(titulo)
        subtitulo = QLabel("Arrastra las señales a los canales del PLC virtual")
        subtitulo.setStyleSheet("color:#8fb9d9; font-size:12px")
        textos.addWidget(subtitulo)
        cabecera.addLayout(textos)
        cabecera.addStretch()
        self.check = QLabel("●")
        self.check.setStyleSheet("color:#87939c; font-size:22px")
        self.badge = QFrame()
        self.badge.setFixedHeight(40)
        bl = QHBoxLayout(self.badge)
        bl.setContentsMargins(12, 7, 12, 7)
        bl.setSpacing(7)
        bl.addWidget(self.check)
        bl.addWidget(self.estado)
        self.badge.setStyleSheet("background:#20313d; border-radius:7px")
        cabecera.addWidget(self.badge)
        self.b_prueba_guiada = QPushButton("Abrir prueba guiada")
        self.b_prueba_guiada.clicked.connect(self.abrir_prueba)
        self.b_configuracion = QPushButton("Configuración")
        self.b_configuracion.clicked.connect(self.abrir_configuracion)
        raiz.addWidget(banda)
        self.modulo = QFrame()
        self.modulo.setObjectName("moduloPLC")
        cuerpo = QVBoxLayout(self.modulo)
        cuerpo.setContentsMargins(14, 16, 14, 12)
        cuerpo.setSpacing(12)
        encabezado_plc = QHBoxLayout()
        nombre_plc = QLabel("PLC VIRTUAL")
        nombre_plc.setStyleSheet("color:#e9f4ff; font-weight:600; font-size:17px")
        encabezado_plc.addWidget(nombre_plc)
        self.b_canales = QPushButton("+ Canales")
        self.b_canales.setToolTip("Configurar offset y cantidad de entradas y salidas")
        self.b_canales.setStyleSheet("color:#91c9f0; background:#29485e; padding:5px 10px; border-radius:4px")
        self.b_canales.clicked.connect(self.abrir_configuracion)
        encabezado_plc.addWidget(self.b_canales)
        self.online = QLabel("● OFFLINE")
        self.online.setStyleSheet("color:#7991a4; font-weight:600; font-size:11px")
        encabezado_plc.addWidget(self.online, 1, Qt.AlignmentFlag.AlignRight)
        cuerpo.addLayout(encabezado_plc)
        self.destino = QLabel()
        self.destino.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.destino.setStyleSheet("color:#90bad7; font-size:11px; padding-bottom:8px")
        cuerpo.addWidget(self.destino)
        self.ayuda_vacio = QLabel("Arrastra las variables a las entradas y salidas.")
        self.ayuda_vacio.setWordWrap(True)
        self.ayuda_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ayuda_vacio.setStyleSheet("color:#8f949f; font-size:11px")
        puertos = QHBoxLayout()
        puertos.setSpacing(22)
        self.fila_entradas = QVBoxLayout()
        self.fila_salidas = QVBoxLayout()
        self.fila_entradas.setSpacing(2)
        self.fila_salidas.setSpacing(2)
        etiquetas = QHBoxLayout()
        etiquetas.addWidget(QLabel("ENTRADAS"))
        etiquetas.addWidget(QLabel("SALIDAS"), 1, Qt.AlignmentFlag.AlignRight)
        cuerpo.addLayout(etiquetas)
        puertos.addLayout(self.fila_entradas)
        puertos.addLayout(self.fila_salidas)
        cuerpo.addLayout(puertos)
        cuerpo.addWidget(self.ayuda_vacio)
        self.resumen = QLabel()
        self.resumen.setStyleSheet("border-top:1px solid #3b5264; padding-top:12px; color:#8ab4d1; font-size:11px")
        cuerpo.addWidget(self.resumen)
        scroll = QScrollArea()
        centro = QWidget()
        centro.setObjectName("zonaPLC")
        centro.setStyleSheet("QWidget#zonaPLC { background:transparent; }")
        central = QVBoxLayout(centro)
        central.setContentsMargins(0, 0, 0, 0)
        central.addWidget(self.modulo, 1)
        scroll.setWidgetResizable(True)
        scroll.setWidget(centro)
        zona = QHBoxLayout()
        zona.setContentsMargins(24, 20, 24, 16)
        zona.setSpacing(14)
        self.cuentas = {}
        self.lista_entradas, self.lista_salidas = ListaVariables(), ListaVariables()
        for titulo, lista in (("Entradas", self.lista_entradas), ("Salidas", self.lista_salidas)):
            lado = QFrame()
            lado.setObjectName("lateralES")
            listas = QVBoxLayout(lado)
            listas.setSpacing(18)
            listas.setContentsMargins(12, 18, 12, 14)
            etiqueta = QLabel("SENSORES" if lista is self.lista_entradas else "ACTUADORES")
            etiqueta.setStyleSheet("font-size:13px; font-weight:600; color:#d5e9fb")
            listas.addWidget(etiqueta)
            self.cuentas["input" if lista is self.lista_entradas else "output"] = etiqueta
            lista.setMinimumWidth(165)
            listas.addWidget(lista, 1)
            if lista is self.lista_salidas:
                zona.addWidget(scroll, 2)
            zona.addWidget(lado, 1)
        raiz.addLayout(zona, 1)
        leyenda = QLabel('<span style="color:#4fe3a2">●</span> Señal activa　 <span style="color:#718393">●</span> Inactiva　 <span style="color:#52bdff">✓</span> Asignada　 ·　 I / Q = posición fija')
        leyenda.setStyleSheet("color:#8fb9d9; padding:4px 26px 20px; font-size:12px")
        raiz.addWidget(leyenda)
        self.dialogo_config = DialogoConfiguracion(self)
        self.dialogo_config.setWindowTitle("Configuración Modbus TCP")
        self.dialogo_config.resize(640, 380)
        self.dialogo_config.setStyleSheet("""
            QDialog { background:#303034; color:#e6e6ed; }
            QLabel, QCheckBox { color:#d5d5df; }
            QLineEdit, QSpinBox, QComboBox { background:#3a3b43; color:#eeeeF4; border:1px solid #666873; border-radius:3px; padding:5px; }
            QTableWidget { background:#33343a; color:#e6e6ed; gridline-color:#4c4d56; }
            QHeaderView::section { background:#28292f; color:#c9cbd5; padding:6px; border:0; }
            QPushButton { background:#454750; color:#e6e6ed; padding:7px 12px; border:0; border-radius:4px; }
            QPushButton:hover { background:#565965; }
        """)
        self.b_prueba_guiada.clicked.connect(self.dialogo_config.hide)
        ajustes = QVBoxLayout(self.dialogo_config)
        self.config_widget = QWidget()
        configuracion = QVBoxLayout(self.config_widget)
        endpoint = QFormLayout()
        endpoint.setVerticalSpacing(14)
        endpoint.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        servidor = QLabel("Servidor")
        servidor.setStyleSheet("font-size:18px; color:#c4dfae; padding:8px 0")
        configuracion.addWidget(servidor)
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
        self.host.setFixedWidth(260)
        self.puerto.setFixedWidth(110)
        self.unidad.setFixedWidth(110)
        self.host.setToolTip("Copia el Host que muestra Factory I/O en CONFIGURACIÓN. Debe coincidir con el servidor activo.")
        self.unidad.setToolTip("El mismo número que «Esclavo ID» en Factory I/O; normalmente 1.")
        for texto, widget in (("IP (Host)", self.host), ("Puerto", self.puerto), ("Esclavo ID", self.unidad)):
            endpoint.addRow(texto, widget)
        configuracion.addLayout(endpoint)
        titulo_canales = QLabel("Canales del servidor")
        titulo_canales.setStyleSheet("font-size:17px; color:#c4dfae; padding-top:10px")
        configuracion.addWidget(titulo_canales)
        rejilla_canales = QGridLayout()
        rejilla_canales.addWidget(QLabel("Offset (desde)"), 0, 1)
        rejilla_canales.addWidget(QLabel("Cantidad"), 0, 2)
        self.offsets, self.cantidades = {}, {}
        self.canales_editados = False
        for fila, (area, texto) in enumerate((("discrete", "I · Entradas digitales"), ("coil", "Q · Salidas digitales"),
                                             ("input-register", "AI · Entradas numéricas"), ("holding", "AQ · Salidas numéricas")), 1):
            offset, cantidad = QSpinBox(), QSpinBox()
            offset.setRange(0, 65535)
            cantidad.setRange(0, 256 if area in ("discrete", "coil") else 64)
            offset.setFixedWidth(110)
            cantidad.setFixedWidth(110)
            offset.valueChanged.connect(self._marcar_canales)
            cantidad.valueChanged.connect(self._marcar_canales)
            self.offsets[area], self.cantidades[area] = offset, cantidad
            rejilla_canales.addWidget(QLabel(texto), fila, 0)
            rejilla_canales.addWidget(offset, fila, 1)
            rejilla_canales.addWidget(cantidad, fila, 2)
        configuracion.addLayout(rejilla_canales)
        ayuda_canales = QLabel("Copia offset y cantidad de Factory I/O. Estos ajustes no modifican el servidor.")
        ayuda_canales.setWordWrap(True)
        ayuda_canales.setStyleSheet("color:#98adbd; font-size:11px")
        configuracion.addWidget(ayuda_canales)
        self.b_avanzado = QPushButton("Asignaciones y ajustes avanzados  ›")
        self.b_avanzado.setStyleSheet("text-align:left; margin-top:12px; background:transparent; color:#b9beca")
        self.b_avanzado.clicked.connect(self._alternar_avanzado)
        configuracion.addWidget(self.b_avanzado)
        self.avanzado = QWidget()
        avanzado = QVBoxLayout(self.avanzado)
        avanzado.setContentsMargins(0, 10, 0, 0)
        tiempos = QFormLayout()
        tiempos.addRow("Periodo", self.periodo)
        tiempos.addRow("Tiempo de espera", self.timeout)
        avanzado.addLayout(tiempos)
        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels(["Usar", "Variable", "Papel", "Tipo", "Área", "Dirección (base 0)", "Formato", "Escala"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setMinimumHeight(150)
        avanzado.addWidget(self.tabla)
        configuracion.addWidget(self.avanzado)
        self.avanzado.hide()
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
        self.b_desconectar = QPushButton("Desconectar / editar")
        self.b_desconectar.clicked.connect(self.desconectar)
        self.b_desconectar.setEnabled(False)
        for b in (self.b_aplicar, self.b_cargar, self.b_guardar):
            botones.addWidget(b)
        avanzado.addLayout(botones)
        principales = QHBoxLayout()
        principales.addWidget(self.b_probar)
        principales.addStretch()
        principales.addWidget(self.b_prueba_guiada)
        ajustes.addLayout(principales)
        for b in (self.b_conectar, self.b_desconectar, self.b_configuracion):
            cabecera.addWidget(b)
        self.b_desconectar.hide()
        nota = QLabel("Factory I/O: driver Modbus TCP/IP Server. Escala: valor GRAFCET = registro / escala. "
                      "Los pulsos más cortos que el intervalo efectivo pueden perderse.")
        nota.setWordWrap(True)
        avanzado.addWidget(nota)
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

    def _marcar_canales(self):
        self.canales_editados = True

    def _alternar_avanzado(self):
        mostrar = self.avanzado.isHidden()
        self.avanzado.setVisible(mostrar)
        self.b_avanzado.setText("Asignaciones y ajustes avanzados  ⌄" if mostrar else "Asignaciones y ajustes avanzados  ›")
        self.dialogo_config.resize(1050 if mostrar else 640, 680 if mostrar else 380)

    def _cerrar_configuracion(self):
        self.dialogo_config.close()

    def mostrar_estado(self, estado, mensaje):
        self.estado.setText(mensaje)
        conectado = estado == "conectado"
        self.check.setText("✓" if conectado else "✕" if estado in ("error", "diagnostico") else "●")
        self.check.setStyleSheet(f"background:{'#8ac849' if conectado else 'transparent'}; color:{'#22301a' if conectado else '#ea7878' if estado in ('error','diagnostico') else '#979aa5'}; border-radius:11px; min-width:22px; min-height:22px; font-size:16px; font-weight:600")
        self.check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.estado.setVisible(not conectado)
        self.check.setToolTip(mensaje)
        self.estado.setVisible(True)
        self.estado.setStyleSheet(f"color:{'#59e5ae' if conectado else '#aec1d2'}; font-size:12px")
        self.badge.setStyleSheet(f"background:{'#193e33' if conectado else '#20313d'}; border:1px solid {'#32634e' if conectado else '#385061'}; border-radius:7px")
        self.online.setText("● ONLINE" if conectado else "● OFFLINE")
        self.online.setStyleSheet(f"color:{'#59e5ae' if conectado else '#7991a4'}; font-weight:600; font-size:11px")

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
        self.abrir_configuracion()
        self.cantidades[area].setFocus()
        self.cantidades[area].selectAll()

    def cargar(self, doc, config=None):
        self.doc = doc
        self.config = config or Configuracion(modelo=doc["id"])
        c = self.config
        for area in AREAS:
            posiciones = [s.direccion for s in c.senales if s.area == area]
            rol = "input" if area == "input-register" else "output"
            base = (4 if area == "discrete" else 2 if area == "coil" else
                    2 if any(v["role"] == rol and v["type"]["kind"] in ("int", "decimal") for v in doc["variables"]) else 0)
            limite = 256 if area in ("discrete", "coil") else 64
            offset = min(posiciones) if posiciones and max(posiciones) >= limite else 0
            cantidad = max(base, max(posiciones) - offset + 1 if posiciones else 0)
            rango = c.canales.get(area, {"offset": offset, "cantidad": cantidad})
            self.offsets[area].setValue(rango["offset"])
            self.cantidades[area].setValue(rango["cantidad"])
        self.canales_editados = False
        self.destino.setText(f"{c.host}:{c.puerto}\nEsclavo ID: {c.unidad}")
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
        c.canales = ({area: {"offset": self.offsets[area].value(), "cantidad": self.cantidades[area].value()}
                      for area in AREAS} if self.canales_editados or self.config.canales else {})
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
        self.indicadores_listas.clear()
        asignadas = {s.variable for s in self.config.senales}
        for rol, titulo in (("input", "SENSORES"), ("output", "ACTUADORES")):
            self.cuentas[rol].setText(f"{titulo}     {sum(v['role'] == rol for v in self.variables)}")
        for v in self.variables:
            item = QListWidgetItem(v["name"])
            item.setSizeHint(QSize(180, 54))
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            item.setToolTip(TIPOS[v["type"]["kind"]])
            if v["type"]["kind"] == "duration":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            lista = self.lista_entradas if v["role"] == "input" else self.lista_salidas
            lista.setSpacing(3)
            lista.addItem(item)
            tarjeta = QFrame()
            tarjeta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            tarjeta.setStyleSheet("QFrame { background:#243b4b; border:1px solid #3c5c72; border-radius:6px; }")
            fila_tarjeta = QHBoxLayout(tarjeta)
            fila_tarjeta.setContentsMargins(9, 4, 9, 4)
            asa = QLabel("⠿")
            asa.setStyleSheet("color:#6488a1; font-size:16px; border:0; background:transparent")
            nombre = QLabel(v["name"])
            nombre.setStyleSheet("color:#dbeeff; font-weight:600; font-size:14px; border:0; background:transparent")
            nombre.setWordWrap(True)
            led = QLabel("●")
            led.setStyleSheet("color:#718393; font-size:17px; border:0; background:transparent")
            marca = QLabel("✓" if v["id"] in asignadas else "○")
            marca.setStyleSheet("color:#52bdff; font-size:18px; border:0; background:transparent")
            for w in (asa, nombre, led, marca):
                fila_tarjeta.addWidget(w, 1 if w is nombre else 0)
            lista.setItemWidget(item, tarjeta)
            self.indicadores_listas[v["id"]] = led
        mapa = {(s.area, s.direccion): s for s in self.config.senales}
        for area in AREAS:
            numerica = area in ("input-register", "holding")
            entrada = area in ("discrete", "input-register")
            if numerica and area not in self.config.canales and not any(v["type"]["kind"] in ("int", "decimal") and v["role"] == ("input" if entrada else "output") for v in self.variables):
                continue
            if area in self.config.canales:
                rango = self.config.canales[area]
                direcciones = range(rango["offset"], rango["offset"] + rango["cantidad"])
            else:
                direcciones = set(range(2 if numerica or not entrada else 4)) | {d for a, d in mapa if a == area}
            fila = self.fila_entradas if entrada else self.fila_salidas
            for direccion in sorted(direcciones):
                s = mapa.get((area, direccion))
                v = variables.get(s.variable) if s else None
                terminal = TerminalES(self, area, direccion, v)
                fila.addWidget(terminal)
                self.terminales[(area, direccion)] = terminal
                if v:
                    self.indicadores[v["id"]] = (terminal.led, terminal.valor)
        self.fila_entradas.addStretch()
        self.fila_salidas.addStretch()
        ni = sum(variables[s.variable]["role"] == "input" for s in self.config.senales if s.variable in variables)
        nq = len(self.config.senales) - ni
        ti = sum(a in ("discrete", "input-register") for a, _ in self.terminales)
        tq = len(self.terminales) - ti
        self.resumen.setText(f"{ni}/{ti} entradas asignadas                 {nq}/{tq} salidas asignadas")

    def mostrar_valores(self, valores):
        def activo(valor):
            try:
                return bool(Fraction(valor)) if isinstance(valor, str) else bool(valor)
            except (ValueError, TypeError, ZeroDivisionError):
                return False
        for vid, led in self.indicadores_listas.items():
            led.setStyleSheet(f"color:{'#4fe3a2' if activo(valores.get(vid)) else '#718393'}; font-size:17px; border:0; background:transparent")
        for vid, (led, etiqueta) in self.indicadores.items():
            valor = valores.get(vid)
            if valor is None:
                etiqueta.setText("—")
                color = "#87939c"
            else:
                etiqueta.setText(str(int(valor)) if type(valor) is bool else str(valor))
                color = "#4fe3a2" if activo(valor) else "#718393"
            led.setStyleSheet(f"color:{color}; font-size:17px")

    def mostrar_muestra(self, muestra, senales):
        valores = {}
        for s in senales:
            if s.variable not in muestra:
                continue
            raw = muestra[s.variable]
            if s.formato != "BOOL":
                raw = raw - 65536 if s.formato == "INT16" and raw >= 32768 else raw
                raw = Fraction(raw) / Fraction(s.escala)
            valores[s.variable] = raw
        self.mostrar_valores(valores)

    def ocupado(self, on):
        self.bloqueado = on
        self.lista_entradas.setDragEnabled(not on)
        self.lista_salidas.setDragEnabled(not on)
        for terminal in self.terminales.values():
            terminal.setAcceptDrops(not on)
            if terminal.b_quitar:
                terminal.b_quitar.setEnabled(not on)
                terminal.b_quitar.setToolTip("Pulsa «Desconectar / editar» para desasignar" if on else "Desasignar esta señal")
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
