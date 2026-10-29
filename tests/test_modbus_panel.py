import os
import unittest
import time
from pathlib import Path
import tempfile

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
    def test_SFIO16_ventana_ciclo_y_reinicio(self):
        """REQ-SIM-02, REQ-SIM-03: controles Qt y descarte al reiniciar sesión."""
        from escritorio.ventana import Ventana
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        def esperar_ui(condicion):
            limite = time.monotonic() + 3
            while not condicion():
                app.processEvents()
                if time.monotonic() >= limite:
                    self.fail(w.modbus.mensaje)
                time.sleep(.002)
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p: b"\x02\x01\x01" if p[0] == 2 else p[:5]) as sc:
            w = Ventana(recuperacion=Path(tmp))
            try:
                m = M().var("sensor").var("motor", "output").step("E0", True)
                m.cont("E0", "motor", "sensor")
                w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": m.doc,
                            "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
                w._cargar()
                w.panel_es.cargar(m.doc, Configuracion(puerto=sc.puerto, periodo_ms=20,
                    senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)]))
                w._conectar_modbus()
                esperar_ui(lambda: w.modbus.estado == "conectado")
                self.assertFalse(w.a_ejecutar.isChecked())
                w.a_ejecutar.setChecked(True)
                esperar_ui(lambda: w.modbus.escritos.get("motor") is True)
                w.a_ejecutar.setChecked(False)
                instante = w.v.s.z.time
                fin = time.monotonic() + .08
                esperar_ui(lambda: time.monotonic() >= fin)
                self.assertEqual(w.v.s.z.time, instante)
                self.assertFalse(w.botones["sensor"].isEnabled())
                anterior = w.v.s
                w.reiniciar()
                esperar_ui(lambda: w.v.s is not anterior)
                self.assertFalse(w.modbus.activo)
                self.assertFalse(w.a_ejecutar.isChecked())
                self.assertFalse(w.v.s.z.values["sensor"])
            finally:
                w.close()
                w.deleteLater()
                app.processEvents()

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
