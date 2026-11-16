"""El mismo grupo de limpieza en Traer E/S y en su ventana independiente."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHeaderView, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import estilo
from .escena_modelo import de_otra_escena, quitar_uniones
from .paleta_variables import TituloGrupo


class OtraEscena(QWidget):
    limpiada = Signal()

    def __init__(self, controlador):
        super().__init__()
        self.controlador = controlador
        self.filas = []
        self.casillas = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, estilo.E2, 0, 0)
        layout.setSpacing(estilo.E2)
        self.titulo = TituloGrupo("interna", self)
        self.titulo.plegado = True
        self.titulo.clicked.connect(self.alternar)
        layout.addWidget(self.titulo)
        self.contenido = QWidget()
        cuerpo = QVBoxLayout(self.contenido)
        cuerpo.setContentsMargins(0, 0, 0, 0)
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Quitar", "Señal antigua", "Variable", "Tipo"])
        self.tabla.verticalHeader().hide()
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 70)
        self.tabla.setColumnWidth(3, 82)
        self.tabla.setMinimumHeight(105)
        self.tabla.setMaximumHeight(230)
        cuerpo.addWidget(self.tabla)
        self.borrar_variables = QCheckBox("Borrar también las variables que no se usen en el GRAFCET")
        self.borrar_variables.setChecked(True)
        cuerpo.addWidget(self.borrar_variables)
        self.b_quitar = QPushButton("Quitar las marcadas")
        self.b_quitar.clicked.connect(self.quitar)
        cuerpo.addWidget(self.b_quitar, 0, Qt.AlignmentFlag.AlignRight)
        self.aviso = QPlainTextEdit()
        self.aviso.setReadOnly(True)
        self.aviso.setStyleSheet(f"color:{estilo.AVISO}; background:{estilo.AVISO_FONDO}")
        self.aviso.setMaximumHeight(84)
        self.aviso.hide()
        cuerpo.addWidget(self.aviso)
        layout.addWidget(self.contenido)
        self.contenido.hide()
        self.rellenar()
        controlador.edicion.cambiado.connect(self.rellenar)
        self._crear_atajos()

    def _crear_atajos(self):
        controlador = self.controlador
        self.atajos = []
        for tecla, accion in ((QKeySequence.StandardKey.Undo, controlador.edicion.deshacer),
                              (QKeySequence.StandardKey.Redo, controlador.edicion.rehacer)):
            atajo = QShortcut(QKeySequence(tecla), self)
            atajo.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            atajo.activated.connect(accion)
            self.atajos.append(atajo)

    def rellenar(self):
        from .entradas_salidas import _CasillaCentrada
        panel = self.controlador.panel
        self.filas = de_otra_escena(panel.config, self.controlador.catalogo)
        self.casillas = []
        variables = {v["id"]: v for v in panel.doc["variables"]}
        self.tabla.setRowCount(len(self.filas))
        tipos = {"bit": "Booleana", "int": "Entera", "float": "Decimal"}
        for row, union in enumerate(self.filas):
            casilla = _CasillaCentrada()
            casilla.setChecked(True)
            self.casillas.append(casilla)
            self.tabla.setCellWidget(row, 0, casilla)
            nombre = variables.get(union.variable, {}).get("name", union.variable)
            textos = ("", union.nombre, nombre, tipos.get(union.tipo.lower(), union.tipo))
            for col, texto in enumerate(textos):
                item = QTableWidgetItem(texto)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setToolTip(texto)
                self.tabla.setItem(row, col, item)
        self.titulo.setText(f"De otra escena · {len(self.filas)}")
        self.b_quitar.setEnabled(bool(self.filas))
        self.aplicar_estilo()

    def _fuente_titulo(self):
        fuente = QFont(self.font())
        fuente.setPixelSize(estilo.T_PEQUENA)
        return fuente

    def aplicar_estilo(self):
        panel = self.controlador.panel
        alto = estilo.ESCALAS[panel.escala]["ALTO_CONTROL"]
        for boton in (self.titulo, self.b_quitar):
            boton.setFixedHeight(alto)
        self.tabla.verticalHeader().setDefaultSectionSize(alto)

    def alternar(self):
        self.titulo.plegado = not self.titulo.plegado
        self.contenido.setVisible(not self.titulo.plegado)
        self.titulo.setAccessibleName(
            f"{self.titulo.text()}: {'plegado' if self.titulo.plegado else 'desplegado'}")
        self.titulo.update()

    def quitar(self):
        controlador = self.controlador
        seleccionadas = [u for u, casilla in zip(self.filas, self.casillas) if casilla.isChecked()]
        if not seleccionadas:
            return
        avisos = quitar_uniones(controlador.edicion, controlador.panel.config, controlador.historial,
                               seleccionadas, self.borrar_variables.isChecked())
        controlador.edicion.cambia()
        controlador.panel.actualizar(controlador.edicion.ed.model)
        controlador.aplicar()
        controlador.dibujar()
        self.rellenar()
        self.aviso.setPlainText("\n".join(avisos))
        self.aviso.setVisible(bool(avisos))
        self.limpiada.emit()


class DialogoOtraEscena(QDialog):
    def __init__(self, controlador):
        super().__init__(controlador.panel)
        self.setWindowTitle("Quitar uniones sin señal")
        self.setStyleSheet(estilo.hoja_global())
        self.resize(min(720, max(520, controlador.panel.window().width() - 32)), 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(estilo.E2, estilo.E2, estilo.E2, estilo.E2)
        self.grupo = OtraEscena(controlador)
        self.grupo.alternar()
        layout.addWidget(self.grupo)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botones.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
