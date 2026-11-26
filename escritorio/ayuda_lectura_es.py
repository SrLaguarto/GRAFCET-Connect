"""Explicación completa en el espacio sin señales cuando falla Traer E/S."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from conexion.http_directo import AVISO_SIN_SERVIDOR
from . import estilo


class AyudaLecturaES(QWidget):
    def __init__(self):
        super().__init__()
        self.servidor_ausente = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(estilo.E2, estilo.E2, estilo.E2, estilo.E2)
        self.etiqueta = QLabel()
        self.etiqueta.setTextFormat(Qt.TextFormat.PlainText)
        self.etiqueta.setWordWrap(True)
        self.etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.etiqueta.setStyleSheet(f"color:{estilo.TINTA_2}")
        layout.addStretch()
        layout.addWidget(self.etiqueta)
        layout.addStretch()
        self.hide()

    def mostrar(self, mensaje, activable):
        self.servidor_ausente = AVISO_SIN_SERVIDOR in mensaje
        self.actualizar(mensaje, activable)
        self.show()

    def actualizar(self, mensaje, activable):
        instrucciones = ""
        if self.servidor_ausente:
            if activable:
                instrucciones = "Pulsa «Activar el servidor web». "
            instrucciones += (
                "Reinicia el simulador de fábricas con el controlador en «Ninguno» "
                "y pulsa «Volver a leer»."
            )
        self.etiqueta.setText(mensaje + ("\n\n" + instrucciones if instrucciones else ""))
        self.etiqueta.setToolTip(self.etiqueta.text())

