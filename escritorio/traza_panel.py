"""La cabecera de la traza reserva el alto completo de su flecha de cierre."""
from . import estilo
from .paneles import CajaSeccion


class CajaTraza(CajaSeccion):
    def __init__(self):
        super().__init__("Traza")
        self.setObjectName("cajaTraza")
        margen = 32 + 2 * estilo.E1
        self._regla_cabecera = (
            f"QGroupBox#cajaTraza {{margin-top:{margen}px;}}"
            f"QGroupBox#cajaTraza::title {{padding-top:{estilo.E2}px; padding-bottom:{estilo.E2}px;}}")
        self.setStyleSheet("")

    def setStyleSheet(self, hoja):  # noqa: N802
        """La actualización de escala conserva la reserva para el botón de cierre."""
        super().setStyleSheet(hoja.replace(self._regla_cabecera, "") + self._regla_cabecera)
