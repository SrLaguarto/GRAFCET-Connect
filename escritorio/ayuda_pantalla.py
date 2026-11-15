"""Ayuda contextual accesible desde el menú, sin ocupar la cabecera."""
from PySide6.QtCore import QEvent, QObject, Qt

from . import estilo


class AyudaPantalla(QObject):
    def __init__(self, ventana):
        super().__init__(ventana)
        self.v = ventana
        ventana.ayuda_larga.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        ventana.ayuda_larga.installEventFilter(self)

    def eventFilter(self, objeto, evento):
        if evento.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            if evento.key() == Qt.Key.Key_Escape:
                evento.accept()
                if evento.type() == QEvent.Type.KeyPress:
                    self.cerrar()
                return True
        return False

    def alternar(self):
        self.v._ayuda_abierta = not self.v._ayuda_abierta
        self.v._ajustar_cabecera()
        if self.v._ayuda_abierta:
            self.v.ayuda_larga.setFocus()

    def cerrar(self):
        self.v._ayuda_abierta = False
        self.v._ajustar_cabecera()
        self.v.diagrama.setFocus()

    def actualizar(self, texto, libre):
        v = self.v
        abierta = v._ayuda_abierta and bool(texto)
        error = bool(texto) and estilo.ERROR in v.ayuda.styleSheet()
        v.ayuda.mostrar_texto = error and not abierta and libre >= estilo.E6 * 4
        v.ayuda.update()
        v.a_ayuda_pantalla.blockSignals(True)
        v.a_ayuda_pantalla.setChecked(abierta)
        v.a_ayuda_pantalla.blockSignals(False)
        v.ayuda_larga.setText(texto if abierta else "")
        v.ayuda_larga.setVisible(abierta)
