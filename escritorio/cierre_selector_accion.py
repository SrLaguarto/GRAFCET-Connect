"""Esc cierra también el selector sobre el dibujo cuando el foco está en su lista nativa."""
from PySide6.QtCore import QEvent, QObject, Qt


class CierreSelectorAccion(QObject):
    def __init__(self, selector):
        super().__init__(selector)
        self.selector = selector
        vista = selector.view()
        vista.installEventFilter(self)
        vista.window().installEventFilter(self)

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Type.KeyPress and evento.key() == Qt.Key.Key_Escape:
            self.selector.hidePopup()
            evento.accept()
            return True
        return False
