"""Selector de modo y lista de uniones de la vista de E/S."""
from copy import deepcopy

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLineEdit, QListWidgetItem,
                               QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from conexion.configuracion import Configuracion
from conexion.uniones import Union
from . import estilo


class PilaModos(QStackedWidget):
    def minimumSizeHint(self):
        return self.currentWidget().minimumSizeHint() if self.currentWidget() else super().minimumSizeHint()

    def sizeHint(self):
        return self.currentWidget().sizeHint() if self.currentWidget() else super().sizeHint()

    def heightForWidth(self, ancho):
        widget = self.currentWidget()
        if widget is None:
            return super().heightForWidth(ancho)
        alto = widget.heightForWidth(ancho)
        return alto if alto >= 0 else widget.minimumSizeHint().height()


class PanelDirecto(QObject):
    traer = Signal()

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.catalogo = []
        self.edicion = None
        self.dialogo_traer = None
        self.dialogo_resumen = None
        self.firma_catalogo = None
        from .traer_modelo import HistorialUniones
        self.historial = HistorialUniones()
        self.traer.connect(self.abrir_traer)
        self.config_modbus = None
        self.config_directa = Configuracion(host="localhost", puerto=7410, modo="directo")
        self.cargando = False
        self.selector = QComboBox()
        self.selector.addItem("Modbus TCP", "modbus")
        self.selector.addItem("Conexión directa (simulador de fábricas)", "directo")
        self.selector.setAccessibleName("Modo de conexión")
        self.selector.setStyleSheet(f"QComboBox {{font-weight:600; color:{estilo.ACENTO};}}")
        self.paginas = PilaModos()
        scroll = panel._partes[1]
        self.scroll = scroll
        self.viewport = scroll.viewport()
        self.viewport.installEventFilter(self)
        scroll.takeWidget()
        self.paginas.addWidget(panel.lienzo)
        self.widget = QWidget()
        self.paginas.addWidget(self.widget)
        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(estilo.E2, estilo.E1, estilo.E2, estilo.E1)
        layout.setSpacing(estilo.E2)
        layout.addWidget(self.selector)
        layout.addWidget(self.paginas, 1)
        scroll.setWidget(contenedor)
        panel.lienzo.layout().itemAtPosition(0, 0).widget().hide()
        panel.lienzo.layout().setContentsMargins(0, estilo.E2, 0, 2)
        self._crear_panel()
        panel.cabecera.layout().addWidget(panel.fila_estado)
        self.selector.currentIndexChanged.connect(self.cambiar_modo)

    def _crear_panel(self):
        from .directa_marco import MarcoDirecto
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.dibujo = MarcoDirecto(self)
        layout.addWidget(self.dibujo)
        self.b_traer.clicked.connect(self.traer)
        self.host.editingFinished.connect(self.aplicar)
        self.puerto.editingFinished.connect(self.aplicar)

    def cambiar_modo(self):
        if self.cargando or self.panel.doc is None:
            return
        actual = self.panel.obtener()
        if actual.modo == "directo":
            self.config_directa = actual
        else:
            self.config_modbus = actual
        if self.config_directa.modelo and self.config_directa.modelo != self.panel.doc["id"]:
            self.config_directa = Configuracion(host="localhost", puerto=7410, modo="directo")
        nuevo = self.config_directa if self.selector.currentData() == "directo" else self.config_modbus
        if nuevo is not None:
            nuevo.modelo = self.panel.doc["id"]
        self.panel.cargar(self.panel.doc, deepcopy(nuevo))
        self.panel.aplicar.emit(self.panel.config)

    def seleccionar(self, modo):
        self.cargando = True
        self.selector.setCurrentIndex(1 if modo == "directo" else 0)
        self.paginas.setCurrentIndex(1 if modo == "directo" else 0)
        self.paginas.updateGeometry()
        self.paginas.parentWidget().layout().invalidate()
        self.ajustar_alto()
        self.cargando = False
        self.aplicar_estilo()
        if modo == "modbus":
            self.panel.fila_estado.hide()
            self.panel.resumen.setMinimumWidth(0)
            self.panel.ayuda_vacio.setText("Arrastra las variables a las entradas y salidas.")
            self.panel.ayuda_vacio.show()

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Type.Resize and objeto is self.viewport:
            self.ajustar_alto()
        return super().eventFilter(objeto, evento)

    def ajustar_alto(self):
        contenedor = self.scroll.widget()
        if contenedor is None:
            return
        if self.selector.currentData() == "directo":
            alto = max(self.scroll.viewport().height(), contenedor.minimumSizeHint().height())
            contenedor.setMaximumHeight(alto)
        else:
            contenedor.setMaximumHeight(16777215)

    def cargar(self, doc, config):
        if self.edicion is not None:
            self.historial.sincronizar(self.edicion.ed, config)
        self.panel.doc = doc
        self.panel.config = deepcopy(config)
        self.panel.variables = [v for v in doc["variables"] if v["role"] in ("input", "output")]
        self.panel.firma_modelo = self.panel.firma(doc)
        self.seleccionar("directo")
        self.host.setText(config.host)
        self.puerto.setValue(config.puerto)
        self.dibujar()
        return []

    def obtener(self):
        config = deepcopy(self.panel.config)
        config.host = self.host.text().strip()
        config.puerto = self.puerto.value()
        config.validar(self.panel.doc)
        return config

    def aplicar(self):
        try:
            self.panel.config = self.obtener()
        except ValueError as exc:
            self.panel.estado.setText(str(exc))
            return
        self.panel.aplicar.emit(self.panel.config)

    def dibujar(self):
        self.panel.indicadores.clear()
        self.panel.indicadores_listas.clear()
        self.panel.terminales.clear()
        self._variables()
        self.dibujo.dibujar()
        self.panel.resumen.setText(f"{len(self.panel.config.uniones)} uniones")
        ancho = self.panel.resumen.fontMetrics().horizontalAdvance(self.panel.resumen.text())
        self.panel.resumen.setMinimumWidth(ancho + estilo.E2)
        self.panel.ayuda_vacio.setText(
            "Arrastre una variable a su señal. Botón derecho para quitar la unión. "
            "Ponga el driver del simulador en None para la conexión directa.")
        self.panel.ayuda_vacio.show()
        self.aplicar_estilo()

    def aplicar_estilo(self):
        alto = estilo.ESCALAS[self.panel.escala]["ALTO_CONTROL"]
        for control in (self.selector, self.host, self.puerto, self.b_traer):
            control.setFixedHeight(alto)
        fuente = self.puerto.fontMetrics()
        self.puerto.setFixedWidth(fuente.horizontalAdvance("65535") + 36)

    def _variables(self):
        from .entradas_salidas import ROL_COLOR, COLOR_TIPO
        for papel, lista in (("input", self.panel.lista_entradas), ("output", self.panel.lista_salidas)):
            lista.clear()
            nombres = [v["name"] for v in self.panel.variables if v["role"] == papel]
            lista.contexto.fijar(nombres)
            titulo = "Sensores" if papel == "input" else "Actuadores"
            self.panel.cuentas[papel].setText(
                f"{titulo} <span style='color:{estilo.TINTA_2}; font-weight:400'>{len(nombres)}</span>")
            for variable in self.panel.variables:
                if variable["role"] != papel:
                    continue
                item = QListWidgetItem(variable["name"])
                item.setData(Qt.ItemDataRole.UserRole, variable["id"])
                item.setData(ROL_COLOR, COLOR_TIPO.get(variable["type"]["kind"]))
                item.setToolTip(variable["name"])
                lista.addItem(item)

    def unir(self, variable_id, senal_id):
        variable = next((v for v in self.panel.variables if v["id"] == variable_id), None)
        senal = next((s for s in self.catalogo if s["id"] == senal_id), None)
        if variable is None or senal is None:
            return
        union = Union(variable_id, senal_id, senal["name"], senal["type"], senal["kind"].lower())
        if not union.compatible(variable):
            self.panel.estado.setText("La señal y la variable deben tener el mismo papel y tipo")
            return
        self.panel.config.uniones = [u for u in self.panel.config.uniones
                                     if u.variable != variable_id and u.id != senal_id] + [union]
        self.aplicar()
        self.dibujar()

    def quitar(self, identidad):
        self.panel.config.uniones = [u for u in self.panel.config.uniones if u.id != identidad]
        self.aplicar()
        self.dibujar()

    def configuracion(self):
        dialogo = QDialog(self.panel)
        dialogo.setWindowTitle("Configuración de conexión directa")
        layout = QFormLayout(dialogo)
        host = QLineEdit(self.host.text())
        controles = {}
        layout.addRow("Servidor", host)
        for nombre, etiqueta, minimo, maximo in (("puerto", "Puerto", 1, 65535),
                ("periodo_ms", "Periodo (ms)", 5, 10000), ("timeout_ms", "Tiempo de espera (ms)", 10, 10000)):
            control = QSpinBox()
            control.setRange(minimo, maximo)
            control.setValue(getattr(self.panel.config, nombre))
            controles[nombre] = control
            layout.addRow(etiqueta, control)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        layout.addRow(botones)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.host.setText(host.text())
            self.puerto.setValue(controles["puerto"].value())
            for nombre in ("periodo_ms", "timeout_ms"):
                setattr(self.panel.config, nombre, controles[nombre].value())
            self.aplicar()

    def ocupado(self, on):
        self.selector.setEnabled(not on)
        self.host.setEnabled(not on)
        self.puerto.setEnabled(not on)

    def abrir_traer(self):
        if self.edicion is None:
            self.panel.estado.setText("Abra un proyecto editable para traer E/S")
            return
        from .traer_dialogo import DialogoTraer
        self.dialogo_traer = DialogoTraer(self)
        self.dialogo_traer.open()

    def mostrar_valores(self, valores):
        for terminal in self.dibujo.terminales.values():
            variable = terminal.variable
            valor = valores.get(variable["id"]) if variable else None
            texto = "" if valor is None else str(int(valor)) if isinstance(valor, bool) else str(valor)
            terminal.valor.setText(texto)

    def establecer_edicion(self, edicion):
        if self.edicion is edicion:
            return
        if self.edicion is not None:
            self.edicion.cambiado.disconnect(self.editor_cambiado)
        self.edicion = edicion
        if edicion is not None:
            edicion.cambiado.connect(self.editor_cambiado)

    def editor_cambiado(self):
        if self.edicion is None or self.panel.config.modo != "directo":
            return
        if self.panel.config.modelo != self.edicion.ed.model["id"]:
            return
        self.historial.sincronizar(self.edicion.ed, self.panel.config)
        self.panel.actualizar(self.edicion.ed.model)

    def mostrar_resumen(self, texto):
        from PySide6.QtWidgets import QMessageBox
        cuadro = QMessageBox(QMessageBox.Icon.Information, "Traer E/S", texto,
                             QMessageBox.StandardButton.Ok, self.panel)
        cuadro.button(QMessageBox.StandardButton.Ok).setText("Aceptar")
        self.dialogo_resumen = cuadro
        cuadro.open()

    def refrescar_catalogo(self, cliente):
        from conexion.intercambio_directo import TransporteDirecto
        if self.panel.config.modo != "directo" or not isinstance(cliente, TransporteDirecto):
            return
        if cliente.config.modelo == self.panel.doc["id"]:
            self.panel.config.uniones = deepcopy(cliente.config.uniones)
        firma = (tuple((s["id"], s["name"], s["type"], s["kind"]) for s in cliente.senales.values()),
                 tuple((u.variable, u.id, u.nombre, u.motivo) for u in self.panel.config.uniones))
        if firma != self.firma_catalogo:
            self.firma_catalogo = firma
            self.catalogo = list(cliente.senales.values())
            self.dibujar()
