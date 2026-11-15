"""SCD: modo directo, uniones y conservación de Modbus (I1)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from conexion.configuracion import Configuracion
from conexion.uniones import Union
from grafcet.builder import M
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from escritorio.entradas_salidas import PanelES


class ModoDirecto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.doc = M().var("marcha").var("motor", "output").step("0", True).doc
        self.panel = PanelES()
        self.panel.cargar(self.doc)
        self.addCleanup(self.panel.close)
        self.addCleanup(self.panel.dialogo_config.close)

    def test_SCD01_selector_y_vista_sin_canales(self):
        directa = self.panel.directa
        self.assertEqual(directa.selector.currentData(), "modbus")
        previa = self.panel.obtener()
        directa.selector.setCurrentIndex(1)
        self.assertEqual(self.panel.obtener().modo, "directo")
        self.assertIs(directa.paginas.currentWidget(), directa.widget)
        self.assertEqual(self.panel.obtener().host, "localhost")
        self.assertEqual(self.panel.obtener().puerto, 7410)
        self.panel.mostrar_valores({self.doc["variables"][0]["id"]: True})
        directa.selector.setCurrentIndex(0)
        self.assertEqual(self.panel.obtener(), previa)

    def test_SCD02_modo_se_guarda_y_antiguo_es_modbus(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "conexion.json"
            for modo, host, puerto in (("directo", "localhost", 7410), ("modbus", "127.0.0.1", 502)):
                config = Configuracion(host=host, puerto=puerto, modo=modo)
                config.guardar(ruta, self.doc)
                self.assertEqual(Configuracion.cargar(ruta, self.doc).modo, modo)
            import json
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            datos.pop("modo")
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            self.assertEqual(Configuracion.cargar(ruta, self.doc).modo, "modbus")

    def test_SCD03_unir_quitar_y_rechazar_papel_incorrecto(self):
        self.panel.directa.selector.setCurrentIndex(1)
        directa = self.panel.directa
        directa.catalogo = [{"id": "sensor", "name": "Pulsador", "type": "Bit", "kind": "Input"}]
        entrada, salida = self.doc["variables"]
        directa.unir(salida["id"], "sensor")
        self.assertEqual(self.panel.config.uniones, [])
        directa.unir(entrada["id"], "sensor")
        self.assertEqual(self.panel.config.uniones[0].id, "sensor")
        self.assertEqual(directa.dibujo.terminales["sensor"].nombre.text(), "marcha")
        self.assertEqual(directa.dibujo.terminales["sensor"].canal.text(), "Pulsador")
        directa.quitar("sensor")
        self.assertEqual(self.panel.config.uniones, [])

    def test_SCD04_union_rota_se_conserva_y_modo_bloqueado_conectado(self):
        entrada = self.doc["variables"][0]
        config = Configuracion(host="localhost", puerto=7410, modo="directo")
        config.uniones = [Union(entrada["id"], "ausente", "Pulsador", "Bit", "input", "señal no encontrada")]
        self.panel.cargar(self.doc, config)
        self.panel.actualizar(self.doc)
        self.assertEqual(len(self.panel.config.uniones), 1)
        self.assertIn("no encontrada", self.panel.directa.dibujo.terminales["ausente"].toolTip())
        self.panel.ocupado(True)
        self.assertFalse(self.panel.directa.selector.isEnabled())
        self.panel.ocupado(False)
        self.assertTrue(self.panel.directa.selector.isEnabled())

    def test_SCD05_modo_directo_no_hereda_altura_de_canales_modbus(self):
        self.panel.resize(1366, 650)
        self.panel.show()
        for _ in range(5):
            self.app.processEvents()
        self.panel.directa.selector.setCurrentIndex(1)
        for _ in range(5):
            self.app.processEvents()
        self.assertEqual(self.panel._partes[1].verticalScrollBar().maximum(), 0)


if __name__ == "__main__":
    unittest.main()
