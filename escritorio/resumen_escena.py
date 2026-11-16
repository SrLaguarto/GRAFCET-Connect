"""Un resumen de una fila y detalle desplazable, sin crecer por cada unión."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from . import estilo
from .paneles import EtiquetaElidida


class EtiquetaResumen(EtiquetaElidida):
    pulsada = Signal()

    def __init__(self):
        super().__init__(ancho_maximo=2000)
        self.setWordWrap(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            self.pulsada.emit()
        super().mouseReleaseEvent(evento)

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.pulsada.emit()
            evento.accept()
        else:
            super().keyPressEvent(evento)


class ResumenEscena(QWidget):
    def __init__(self, padre=None):
        super().__init__(padre)
        self.texto = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(estilo.E1)
        self.etiqueta = EtiquetaResumen()
        self.detalle = QPlainTextEdit()
        self.detalle.setReadOnly(True)
        self.detalle.setFixedHeight(84)
        self.detalle.setStyleSheet(f"color:{estilo.TINTA_2}")
        layout.addWidget(self.etiqueta)
        layout.addWidget(self.detalle)
        self.detalle.hide()
        self.etiqueta.pulsada.connect(self.alternar)

    def fijar(self, resumen, detalles):
        self.texto = resumen
        self.detalle.setPlainText("\n".join(detalles))
        self.detalle.hide()
        self._actualizar()

    def alternar(self):
        if self.detalle.toPlainText():
            self.detalle.setVisible(self.detalle.isHidden())
            self._actualizar()

    def _actualizar(self):
        tiene_detalle = bool(self.detalle.toPlainText())
        flecha = (" ›" if self.detalle.isHidden() else " ⌄") if tiene_detalle else ""
        self.etiqueta.setText(self.texto + flecha)
        self.etiqueta.setToolTip(self.texto + "\n" + self.detalle.toPlainText())
        self.etiqueta.setAccessibleName(self.texto + (". Mostrar detalle" if tiene_detalle else ""))
