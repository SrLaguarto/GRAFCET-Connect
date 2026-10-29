import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    from escritorio.entradas_salidas import PanelES
    QT = True
except ImportError:
    QT = False

from conexion.configuracion import Configuracion, Senal
from grafcet.builder import M


@unittest.skipUnless(QT, "Falta PySide6")
class PanelTests(unittest.TestCase):
    def test_SFIO08_panel_y_mapa(self):
        """REQ-SIM-03: E/S externas configurables con tipo y valor visibles."""
        app = QApplication.instance() or QApplication([])
        doc = M().var("sensor").var("motor", "output").var("velocidad", "input", "int").step("E0", True).doc
        c = Configuracion(senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0),
                                   Senal("velocidad", "input-register", 0, "INT16")])
        p = PanelES()
        p.cargar(doc, c)
        self.assertEqual(p.obtener().senales, c.senales)
        p.mostrar_valores({"sensor": True, "motor": False, "velocidad": -12})
        self.assertEqual(p.indicadores["velocidad"][1].text(), "-12")
        p.ocupado(True)
        self.assertFalse(p.config_widget.isEnabled())
        p.close()
        p.deleteLater()
        app.processEvents()
