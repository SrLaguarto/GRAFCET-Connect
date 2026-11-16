"""Porcentaje prescindible del zoom y ayuda de sus botones siempre actualizada."""
from PySide6.QtCore import QObject


class PorcentajeZoom(QObject):
    def __init__(self, diagrama):
        super().__init__(diagrama)
        self.diagrama = diagrama
        self.visible = True
        self.ayudas = None
        diagrama.zoomCambiado.connect(self.actualizar_ayudas)

    def mostrar(self, visible):
        d = self.diagrama
        if self.ayudas is None:
            self.ayudas = (d.b_menos.toolTip(), d.b_mas.toolTip())
        if self.visible != visible:
            self.visible = visible
            d.l_zoom.setVisible(visible)
            d.barra.layout().invalidate()
            d.barra.adjustSize()
        self.actualizar_ayudas()

    def actualizar_ayudas(self, *_):
        if self.ayudas is None:
            return
        d = self.diagrama
        for boton, ayuda in zip((d.b_menos, d.b_mas), self.ayudas):
            sufijo = "" if self.visible else f" · zoom {d.l_zoom.text()}"
            boton.setToolTip(ayuda + sufijo)
