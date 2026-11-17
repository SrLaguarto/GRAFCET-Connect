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

    @staticmethod
    def _estado_neutro(panel):
        """Tras activar el servidor web, el aviso deja de verse como error (queda en tinta, con el punto neutro)."""
        panel.check.setText("●")
        panel.check.setStyleSheet(f"background:transparent; color:{estilo.TINTA_3}; border-radius:{estilo.R_M}px; "
                                  f"font-size:{panel.letra}px; font-weight:600")

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        from .ayuda_servidor_web import AyudaServidorWeb
        self.ayuda_servidor = AyudaServidorWeb(panel.estado, panel.fila_estado.layout(), panel.fila_estado,
                                               al_activar=lambda: self._estado_neutro(panel))
        self.catalogo = []
        self.revision_dibujo = 0
        self._firma_dibujo = None
        self._valores_presentados = {}
        self.edicion = None
        self.dialogo_traer = None
        self.dialogo_resumen = None
        self.firma_catalogo = None
        self.catalogo_leido = False
        self.cliente_catalogo = None
        self.reunidas_lectura = 0
        self.avisos_lectura = []
        self.dialogo_otra_escena = None
        from .traer_modelo import HistorialUniones
        self.historial = HistorialUniones()
        self.traer.connect(self.abrir_traer)
        self.config_modbus = None
        self.config_directa = Configuracion(host="localhost", puerto=7410, modo="directo")
        self.cargando = False
        from .campos_medidos import ComboMedido
        self.selector = ComboMedido()
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
        layout.addWidget(self.selector, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.paginas, 1)
        scroll.setWidget(contenedor)
        panel.lienzo.layout().itemAtPosition(0, 0).widget().hide()
        panel.lienzo.layout().setContentsMargins(0, estilo.E2, 0, 2)
        self._crear_panel()
        panel.cabecera.layout().addWidget(panel.fila_estado)
        self._crear_escena()

    def _crear_escena(self):
        panel = self.panel
        from .resumen_escena import ResumenEscena
        self.resumen_escena = ResumenEscena(panel)
        panel.cabecera.layout().addWidget(self.resumen_escena)
        self.resumen_escena.hide()
        self.b_quitar_sin_senal = QPushButton("Quitar uniones sin señal")
        self.b_quitar_sin_senal.clicked.connect(self.abrir_otra_escena)
        self.b_quitar_sin_senal.hide()
        from .pie_escena import PieEscena
        self.pie_escena = PieEscena(panel, self.b_quitar_sin_senal)
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
            self.resumen_escena.hide()
            self.b_quitar_sin_senal.hide()
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

    def _firma(self, doc):
        uniones = self.panel.config.uniones
        return (doc["id"], self.panel.firma(doc),
                tuple((u.variable, u.id, u.nombre, u.tipo, u.papel, u.motivo) for u in uniones))

    def actualizar(self, doc):
        if self.edicion is not None:
            self.historial.sincronizar(self.edicion.ed, self.panel.config)
        if self._firma(doc) == self._firma_dibujo:
            self.panel.doc = doc
            return []
        return self.cargar(doc, self.panel.config)

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
        self.revision_dibujo += 1
        self._valores_presentados.clear()
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
            "Ponga el driver del simulador en «Ninguno» para la conexión directa.")
        self.panel.ayuda_vacio.show()
        self.aplicar_estilo()
        self._firma_dibujo = self._firma(self.panel.doc)

    def aplicar_estilo(self):
        alto = estilo.ESCALAS[self.panel.escala]["ALTO_CONTROL"]
        for control in (self.selector, self.host, self.puerto, self.b_traer, self.b_quitar_sin_senal):
            control.setFixedHeight(alto)
        self.selector.medir()

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
        from .filtro_senales import ConfiguracionDirecta
        dialogo = ConfiguracionDirecta(self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.panel.config = dialogo.config
            self.aplicar()
            self.dibujar()

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
        from fractions import Fraction
        from .entradas_salidas import NIVEL_ACTIVO, NIVEL_ASIGNADO
        for identidad, terminal in self.dibujo.terminales.items():
            variable = terminal.variable
            valor = valores.get(variable["id"]) if variable else None
            firma = (terminal, valor)
            if self._valores_presentados.get(identidad) == firma:
                continue
            self._valores_presentados[identidad] = firma
            numerica = terminal.senal["type"].lower() != "bit"
            texto = (str(valor) if valor is not None else "—" if variable else "") if numerica else ""
            if terminal.valor.text() != texto:
                terminal.valor.setText(texto)
            if variable is not None:
                try:
                    activo = bool(Fraction(valor)) if isinstance(valor, str) else bool(valor)
                except (ValueError, TypeError, ZeroDivisionError):
                    activo = False
                terminal.led.fijar_nivel(NIVEL_ACTIVO if activo else NIVEL_ASIGNADO)

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
        anteriores = {u.variable: u.id for u in self.panel.config.uniones}
        mismo_modelo = cliente.config.modelo == self.panel.doc["id"]
        uniones = cliente.config.uniones if mismo_modelo else self.panel.config.uniones
        firma = (tuple((s["id"], s["name"], s["type"], s["kind"]) for s in cliente.senales.values()),
                 tuple((u.variable, u.id, u.nombre, u.motivo) for u in uniones))
        lectura = cliente is not self.cliente_catalogo or self.firma_catalogo is None
        lectura = lectura or firma[0] != self.firma_catalogo[0]
        if lectura or firma != self.firma_catalogo:
            if mismo_modelo:
                self.panel.config.uniones = deepcopy(uniones)
            self.firma_catalogo = firma
            self.catalogo = list(cliente.senales.values())
            from .escena_modelo import contar_reunidas
            self.catalogo_leido = True
            if lectura:
                self.cliente_catalogo = cliente
                self.reunidas_lectura = contar_reunidas(anteriores, self.panel.config)
                self.avisos_lectura = list(cliente.avisos)
                from conexion.filtro_directo import actualizar
                actualizar(self.panel.config, self.catalogo)
            self.dibujar()

    def avisar_escena(self, motivos):
        from .escena_modelo import de_otra_escena, resumen_lectura
        config = self.panel.config
        ausentes = de_otra_escena(config, self.catalogo) if self.catalogo_leido else []
        self.b_quitar_sin_senal.setVisible(bool(ausentes) and self.edicion is not None)
        mostrar = self.catalogo_leido and bool(motivos or self.reunidas_lectura)
        self.resumen_escena.setVisible(mostrar)
        if mostrar:
            reunidas = [a for a in self.avisos_lectura if "se ha vuelto a unir" in a]
            texto = resumen_lectura(config, self.catalogo, self.reunidas_lectura)
            self.resumen_escena.fijar(texto, reunidas + motivos)

    def abrir_otra_escena(self):
        if self.edicion is None:
            return
        from .otra_escena import DialogoOtraEscena
        self.dialogo_otra_escena = DialogoOtraEscena(self)
        self.dialogo_otra_escena.open()


def configuracion_inicial(proyecto, documento, canales):
    """Solo un proyecto nuevo nace directo; un archivo anterior sigue usando Modbus."""
    if proyecto[0] == "nuevo":
        return Configuracion(host="localhost", puerto=7410, modo="directo", modelo=documento["id"])
    return Configuracion(modelo=documento["id"], canales=deepcopy(canales))
