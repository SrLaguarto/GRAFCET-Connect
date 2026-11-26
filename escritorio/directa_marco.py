"""Mismo módulo y terminales de E/S; el destino es una señal identificada por id."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QWidget

from conexion.catalogo_directo import interna
from conexion.uniones import Union
from . import estilo
from .entradas_salidas import LienzoPLC, TerminalES
from .paneles import EtiquetaElidida
from .campos_medidos import SpinMedido


class TerminalDirecto(TerminalES):
    def __init__(self, marco, senal, variable, motivo):
        tipo = senal["type"].lower()
        entrada = senal["kind"].lower() == "input"
        area = ("discrete" if entrada else "coil") if tipo == "bit" else (
            "input-register" if entrada else "holding")
        super().__init__(marco, area, senal["id"], variable, motivo)
        self.senal = senal
        etiqueta = EtiquetaElidida(senal["name"])
        etiqueta.setObjectName("canalES")
        etiqueta.setToolTip(f"señal: {senal['name']}" + (f"\n{motivo}" if motivo else ""))
        etiqueta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.interior.layout().replaceWidget(self.canal, etiqueta)
        self.canal.hide()
        self.canal.deleteLater()
        self.canal = etiqueta
        self.valor.setVisible(tipo != "bit")  # como en Modbus: la cifra solo en las numéricas; las booleanas, con el piloto
        self.setToolTip(etiqueta.toolTip())
        self.nombre.setToolTip("\n".join(x for x in (variable["name"] if variable else "", etiqueta.toolTip()) if x))

    def actualizar_asignacion(self, variable, motivo):
        """Actualiza estado, cable y botón quitar sin destruir ni recrear el terminal."""
        from .entradas_salidas import COLOR_TIPO, NIVEL_ACTIVO, NIVEL_ASIGNADO, NIVEL_TENUE, color_tipo
        cambio_var = (self.variable["id"] if self.variable else None) != (variable["id"] if variable else None)
        self.variable = variable
        self.aviso = motivo
        nombre = variable["name"] if variable else ""
        if self.nombre.text() != nombre:
            self.nombre.setText(nombre)
        if variable:
            if cambio_var or self.led.nivel < NIVEL_ASIGNADO:
                nivel = (min(NIVEL_ACTIVO, max(NIVEL_ASIGNADO, self.led.nivel))
                         if not cambio_var else NIVEL_ASIGNADO)
                self.led.fijar((color_tipo(variable),), nivel)
        else:
            analogica = self.area in ("input-register", "holding")
            colores = (COLOR_TIPO["decimal"], COLOR_TIPO["int"]) if analogica else (COLOR_TIPO["bool"],)
            self.led.fijar(colores, NIVEL_TENUE)
        if not variable:
            self.valor.setText("")
        elif cambio_var:
            self.valor.setText("—")
        if self.marca is None and motivo:
            self.marca = self._crear_marca(motivo)
            entrada = self.area in ("discrete", "input-register")
            self._diseno.insertWidget(self._diseno.indexOf(self.nombre) + (0 if entrada else 1), self.marca)
        if self.marca is not None:
            self.marca.setToolTip(motivo)
            self.marca.setVisible(bool(motivo))
        estilo.poner(self.nombre, aviso=bool(motivo))
        self.fijar_elegido(getattr(self.panel, "_eleccion", None) == ("canal", self.area, self.direccion))
        base_tip = f"señal: {self.senal['name']}" + (f"\n{motivo}" if motivo else "")
        self.canal.setToolTip(base_tip)
        self.nombre.setToolTip("\n".join(x for x in (nombre, base_tip) if x))
        nota = "\nUna señal ya unida sigue funcionando aunque figure en el filtro de señales."
        self.setToolTip(base_tip + (nota if variable else ""))
        if variable:
            self._asegurar_boton_quitar()
            self.b_quitar.setVisible(self.underMouse() and self.b_quitar.isEnabled())
        elif self.b_quitar is not None:
            self.b_quitar.hide()
        self.update()
        return cambio_var

    def _variable_evento(self, evento):
        variable = super()._variable_evento(evento)
        return variable if variable and self.panel.encaja(variable, self.direccion) else None

    def contextMenuEvent(self, evento):
        if not any(u.id == self.direccion for u in self.panel.controlador.panel.config.uniones):
            return
        menu = QMenu(self)
        quitar = menu.addAction("Quitar unión")
        if menu.exec(evento.globalPos()) == quitar:
            self.panel.controlador.quitar(self.direccion)


class MarcoDirecto(LienzoPLC):
    detalle = Signal(str)

    def __init__(self, controlador):
        self.controlador = controlador
        self.alto_fila = controlador.panel.alto_fila
        self.bloqueado = False
        self._eleccion = None
        self.terminales = {}
        self._clave_layout = None
        super().__init__()
        self.setAutoFillBackground(False)
        self.layout().setContentsMargins(0, 4, 0, 4)
        self.detalle.connect(controlador.panel.detalle)
        self.layout().itemAtPosition(0, 0).widget().hide()
        cabecera = QWidget()
        fila = QHBoxLayout(cabecera)
        fila.setContentsMargins(8, 6, 8, 6)
        fila.setSpacing(5)
        controlador.host = QLineEdit("localhost")
        controlador.host.setMinimumWidth(82)
        controlador.puerto = SpinMedido()
        controlador.puerto.setRange(1, 65535)
        controlador.puerto.setValue(7410)
        controlador.b_traer = QPushButton("Traer E/S")
        for widget in (QLabel("Servidor"), controlador.host, QLabel(":"), controlador.puerto, controlador.b_traer):
            fila.addWidget(widget, 1 if widget is controlador.host else 0)
        self.cabecera_marco.addWidget(cabecera)
        self.cabecera_marco.setCurrentWidget(cabecera)

    def fijar_alto_cabecera(self, alto_control):
        self._alto_cabecera = alto_control + 14
        self.cabecera_marco.setFixedSize(2 * self.ancho_interior, self._alto_cabecera)
        if hasattr(self, "subhdr"):
            self.subhdr.setFixedWidth(2 * self.ancho_interior)

    def contexto_de(self, area):
        return self.controlador.panel.contexto_de(area)

    def admite(self, variable, area):
        return any(self.encaja(variable, senal["id"]) for senal in self.controlador.catalogo)

    def encaja(self, variable, identidad):
        v = next((v for v in self.controlador.panel.variables if v["id"] == variable), None)
        s = next((s for s in self.controlador.catalogo if s["id"] == identidad), None)
        return s is not None and Union(variable, identidad, s["name"], s["type"], s["kind"].lower()).compatible(v)

    def asignar(self, variable, area, identidad):
        if not self.encaja(variable, identidad):
            return False
        self.controlador.unir(variable, identidad)
        return True

    def quitar(self, variable):
        union = next((u for u in self.controlador.panel.config.uniones if u.variable == variable), None)
        if union:
            self.controlador.quitar(union.id)

    def clic_canal(self, area, identidad):
        panel = self.controlador.panel
        if panel._eleccion and panel._eleccion[0] == "variable":
            self.asignar(panel._eleccion[1], area, identidad)
            panel.cancelar_eleccion()

    def _senales_visibles(self):
        panel = self.controlador.panel
        from conexion.filtro_directo import excluida
        senales = {s["id"]: s for s in self.controlador.catalogo if not excluida(panel.config, s)}
        for union in panel.config.uniones:
            senales.setdefault(union.id, {"id": union.id, "name": union.nombre,
                                         "type": union.tipo, "kind": union.papel})
        return senales

    def dibujar(self):
        panel = self.controlador.panel
        variables = {v["id"]: v for v in panel.variables}
        uniones = {u.id: u for u in panel.config.uniones}
        senales = self._senales_visibles()
        clave = (panel.escala, panel.alto_fila, panel.ancho_interior, self.bloqueado,
                 tuple((s["id"], s["name"], s["type"], s["kind"]) for s in senales.values()))
        motivos = []
        if clave == self._clave_layout and set(self.terminales) == set(senales):
            self.alto_fila = panel.alto_fila
            panel.terminales.clear()
            for identidad, terminal in self.terminales.items():
                union = uniones.get(identidad)
                variable = variables.get(union.variable) if union else None
                motivo = self._motivo_union(union, variable, motivos)
                if terminal.actualizar_asignacion(variable, motivo):
                    self.controlador._valores_presentados.pop(identidad, None)
                panel.terminales[(terminal.area, identidad)] = terminal
                if variable:
                    panel.indicadores[variable["id"]] = (terminal.led, terminal.valor)
            self.controlador.avisar_escena(motivos)
            panel.aviso = ""
            panel._pintar_nota()
            return True
        contenedor = self.controlador.scroll.widget()
        objetivo_freeze = contenedor if contenedor is not None else self
        objetivo_freeze.setUpdatesEnabled(False)
        try:
            self.alto_fila = panel.alto_fila
            self.fijar_interior(panel.ancho_interior, estilo.ESCALAS[panel.escala]["ALTO_CONTROL"])
            self._limpiar_terminales()
            self.terminales.clear()
            panel.terminales.clear()
            digitales = max((sum(s["kind"].lower() == papel and s["type"].lower() == "bit"
                                 for s in senales.values()) for papel in ("input", "output")), default=0)
            for papel, fila in (("input", self.fila_izq), ("output", self.fila_der)):
                grupo = [s for s in senales.values() if s["kind"].lower() == papel]
                booleanas = [s for s in grupo if s["type"].lower() == "bit"]
                numericas = [s for s in grupo if s["type"].lower() != "bit"]
                for senal in booleanas:
                    self._poner_terminal(senal, fila, uniones, variables, motivos)
                hueco = digitales - len(booleanas)
                if hueco and numericas:
                    fila.addSpacing(hueco * self.alto_fila)
                for senal in numericas:
                    self._poner_terminal(senal, fila, uniones, variables, motivos)
            self._clave_layout = clave
        finally:
            objetivo_freeze.setUpdatesEnabled(True)
        self.controlador.avisar_escena(motivos)
        panel.aviso = ""
        panel._pintar_nota()
        return False

    @staticmethod
    def _motivo_union(union, variable, motivos):
        motivo = union.motivo if union else ""
        if union and not union.compatible(variable):
            motivo = "El papel o el tipo de la variable ha cambiado"
        if motivo:
            motivos.append(f"{variable['name'] if variable else union.nombre}: {motivo}")
        return motivo

    def _limpiar_terminales(self):
        for fila in (self.fila_izq, self.fila_der):
            while fila.count():
                item = fila.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    widget.deleteLater()

    def _poner_terminal(self, senal, fila, uniones, variables, motivos):
        panel = self.controlador.panel
        identidad = senal["id"]
        union = uniones.get(identidad)
        variable = variables.get(union.variable) if union else None
        motivo = self._motivo_union(union, variable, motivos)
        terminal = TerminalDirecto(self, senal, variable, motivo)
        if union:
            ayuda = "Una señal ya unida sigue funcionando aunque figure en el filtro de señales."
            terminal.setToolTip(terminal.toolTip() + "\n" + ayuda)
        fila.addWidget(terminal)
        self.terminales[identidad] = terminal
        panel.terminales[(terminal.area, identidad)] = terminal
        if variable:
            panel.indicadores[variable["id"]] = (terminal.led, terminal.valor)
