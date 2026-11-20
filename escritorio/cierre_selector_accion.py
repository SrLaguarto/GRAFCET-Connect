"""Esc cierra también el selector sobre el dibujo cuando el foco está en su lista nativa; y la suelta que quedó del doble clic que abrió la
lista no la cierra ni elige."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication


class CierreSelectorAccion(QObject):
    def __init__(self, selector):
        super().__init__(selector)
        self.selector = selector
        self.pendiente = False
        self.origen = None
        vista = selector.view()
        vista.installEventFilter(self)
        vista.viewport().installEventFilter(self)  # (los filtros instalados después van primero: antes que los de Qt)
        vista.window().installEventFilter(self)

    def suelta_pendiente(self) -> None:
        """Se llama al abrir la lista: el botón del doble clic puede seguir pulsado y su suelta llegaría a la lista."""
        self.pendiente = True
        self.origen = QCursor.pos()

    def eventFilter(self, objeto, evento):
        tipo = evento.type()
        if tipo == QEvent.Type.KeyPress and evento.key() == Qt.Key.Key_Escape:
            self.selector.hidePopup()
            evento.accept()
            return True
        if self.pendiente:
            if tipo == QEvent.Type.MouseMove:
                # (al abrir la lista bajo el puntero puede llegar un movimiento sin mover el ratón: solo cuenta pasar la distancia de arrastre)
                pos = evento.globalPosition().toPoint()
                if self.origen is None:
                    self.origen = pos
                elif (pos - self.origen).manhattanLength() >= QApplication.startDragDistance():
                    self.pendiente = False  # arrastrar desde el doble clic hasta una opción: la suelta elige como siempre
            elif tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
                self.pendiente = False  # un clic normal: la suelta elige como siempre
            elif tipo == QEvent.Type.MouseButtonRelease:
                self.pendiente = False
                evento.accept()
                return True  # primera suelta sin pulsar ni mover el ratón dentro de la lista: es la del doble clic; se ignora
        return False
