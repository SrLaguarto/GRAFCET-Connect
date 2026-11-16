"""El desplegable de una acción usa lista, no un menú que se recoloca tras Show."""
from PySide6.QtWidgets import QProxyStyle, QStyle


class EstiloLista(QProxyStyle):
    def styleHint(self, hint, opcion=None, widget=None, resultado=None):
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, opcion, widget, resultado)
