"""Disposición y zona del GRAFCET en el editor de plantillas."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QLabel, QSizePolicy

from . import estilo


class ControlesPlantilla:
    def __init__(self, editor, formulario):
        self.e = editor
        formulario.setContentsMargins(estilo.E2, estilo.E2, estilo.E2, estilo.E2)
        formulario.setSpacing(estilo.E2)
        formulario.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.aviso = QLabel("Elija un texto de la plantilla para cambiarlo")
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"color:{estilo.TINTA_2};")
        formulario.insertRow(0, self.aviso)
        editor.zona = QComboBox()
        editor.zona.addItem("Automática", False)
        editor.zona.addItem("Personalizada", True)
        editor.zona.setToolTip("Automática: usa la zona prevista por la plantilla, dentro del margen y sin el cajetín. "
                               "Personalizada: dibuje un rectángulo en la hoja.")
        formulario.addRow("Zona del GRAFCET", editor.zona)
        editor.zona_label = QLabel()
        editor.zona_label.setWordWrap(True)
        formulario.addRow(editor.zona_label)
        self.ayuda = QLabel("Define dónde se coloca el GRAFCET al traerlo. "
                            "Para personalizarla, arrastre un rectángulo sobre la hoja.")
        self.ayuda.setWordWrap(True)
        self.ayuda.setStyleSheet(f"color:{estilo.TINTA_2};")
        formulario.addRow(self.ayuda)
        linea = QFrame()
        linea.setFrameShape(QFrame.Shape.HLine)
        formulario.addRow(linea)
        formulario.addRow(editor.borrar)
        editor.zona.currentIndexChanged.connect(self.cambiar_zona)
        editor.seleccionado.connect(self.seleccionar)
        for control in (editor.x, editor.y, editor.altura):
            control.setFixedWidth(92)
        for control in (editor.fuente, editor.alineacion, editor.vertical, editor.giro, editor.zona):
            control.setMinimumContentsLength(1)
            control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def seleccionar(self):
        self.aviso.setVisible(self.e.actual is None)

    def cambiar_zona(self):
        e = self.e
        personalizada = e.zona.currentData()
        e.vista.zona = personalizada
        if not personalizada:
            e.poner_zona(None)

    def sincronizar_zona(self):
        e = self.e
        e.zona.blockSignals(True)
        e.zona.setCurrentIndex(1 if e.plantilla.get("zone") else 0)
        e.zona.blockSignals(False)
        e.vista.zona = False

    def mostrar_zona(self, visible):
        e = self.e
        for control in (e.zona, e.zona_label, self.ayuda):
            control.setVisible(visible)
        e.zona.parentWidget().layout().labelForField(e.zona).setVisible(visible)
