"""Edición explícita de una plantilla incorporada en la hoja del proyecto."""
import copy

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from . import estilo


class SesionPlantilla(QObject):
    def __init__(self, editor):
        super().__init__(editor)
        self.e = editor
        self.original = None
        self.seleccion = False
        self.barra = QWidget(editor)
        self.barra.setObjectName("edicionPlantilla")
        fila = QHBoxLayout(self.barra)
        fila.setContentsMargins(estilo.E2, estilo.E2, estilo.E2, estilo.E2)
        fila.setSpacing(estilo.E2)
        self.titulo = QLabel()
        self.titulo.setWordWrap(True)
        fila.addWidget(self.titulo, 1)
        self.guardar = QPushButton("Guardar plantilla")
        estilo.poner(self.guardar, primario=True)
        self.cancelar_boton = QPushButton("Cancelar")
        fila.addWidget(self.guardar)
        fila.addWidget(self.cancelar_boton)
        self.guardar.clicked.connect(self.aceptar)
        self.cancelar_boton.clicked.connect(self.cancelar)
        editor.layout().insertWidget(0, self.barra)
        self.barra.hide()

    def eventFilter(self, objeto, evento):
        tipos = (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
        if self.e.editando_plantilla and evento.type() in tipos and isinstance(objeto, QWidget):
            if evento.key() == Qt.Key.Key_Escape and (objeto is self.e or self.e.isAncestorOf(objeto)):
                evento.accept()
                if evento.type() == QEvent.Type.KeyPress:
                    self.cancelar()
                return True
        return False

    def comenzar(self):
        e = self.e
        if e.editando_plantilla:
            e.a_editar_plantilla.setChecked(True)
            return
        if e.plantilla is None:
            return
        self.original = copy.deepcopy(e.plantilla)
        self.seleccion = e.vista.seleccionado
        e.editando_plantilla = True
        e.a_editar_plantilla.setChecked(True)
        nombre = e.predeterminadas.currentText().partition(" — ")[0]
        self.titulo.setText(f"Editando la plantilla «{nombre}»")
        e.vista.zona = True
        e.editor_textos.controles.mostrar_zona(True)
        e.propiedades.setCurrentWidget(e.editor_textos.panel_propiedades)
        self.barra.show()
        QApplication.instance().installEventFilter(self)

    def aceptar(self):
        if not self.e.editando_plantilla:
            return
        self.terminar()
        self.e.aplicar()

    def cancelar(self):
        e = self.e
        if not e.editando_plantilla:
            return True
        if e.plantilla != self.original:
            respuesta = QMessageBox.question(e, "Cancelar edición", "¿Descartar los cambios de la plantilla?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.No)
            if respuesta != QMessageBox.StandardButton.Yes:
                return False
        e.plantilla = copy.deepcopy(self.original)
        self.terminar()
        e.preparar_textos()
        e.actualizar()
        return True

    def terminar(self):
        e = self.e
        e.editando_plantilla = False
        e.a_editar_plantilla.setChecked(False)
        e.vista.zona = False
        e.vista.nuevo_texto = False
        e.vista.inicio_zona = None
        e.editor_textos.controles.mostrar_zona(False)
        e.editor_textos.elegir(-1)
        e.propiedades.setCurrentIndex(0)
        e.vista.seleccionado = self.seleccion
        self.barra.hide()
        QApplication.instance().removeEventFilter(self)
        e.vista.update()
