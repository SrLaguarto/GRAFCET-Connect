"""SCD: una prueba por regla de relectura de I3 y ambigüedad de identidades."""
import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from conexion.configuracion import Configuracion
from conexion.reconciliar import reconciliar
from conexion.uniones import Union
from escritorio.edicion import Edicion
from escritorio.traer_modelo import Propuestas
from grafcet.builder import M
from grafcet.editor import Editor
from servidor_directo_falso import senal


class Relectura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.doc = M().var("led", "output").step("0", True).doc
        self.anterior = copy.deepcopy(self.doc)
        self.config = Configuracion(host="localhost", puerto=7410, modo="directo")
        self.config.uniones = [Union(self.doc["variables"][0]["id"], "original", "led", "Bit", "output")]
        self.senal = senal("original", "led", papel="Output")

    def propuestas(self, catalogo):
        return Propuestas(Edicion(Editor(self.doc), "Prueba"), self.config, catalogo)

    def releer(self, catalogo):
        avisos = reconciliar(self.config, self.doc, catalogo)
        self.assertEqual(self.doc, self.anterior, "Releer no modifica el modelo")
        return avisos

    def test_SCD20_sin_cambios_ya_traida(self):
        self.assertEqual(self.releer([self.senal]), [])
        self.assertEqual(self.propuestas([self.senal]).elegidas(), [])

    def test_SCD21_senales_nuevas_solo_nuevas_marcadas(self):
        catalogo = [self.senal, senal("nueva", "Marcha")]
        self.releer(catalogo)
        self.assertEqual([f.nombre for f in self.propuestas(catalogo).elegidas()], ["Marcha"])

    def test_SCD22_nombre_nuevo_misma_identidad(self):
        self.senal["name"] = "Motor"
        self.releer([self.senal])
        self.assertEqual(self.config.uniones[0].nombre, "Motor")
        self.assertEqual(self.doc["variables"][0]["name"], "led")

    def test_SCD23_borrada_union_ambar(self):
        self.assertIn("no encontrada", self.releer([])[0])
        self.assertEqual(len(self.config.uniones), 1)

    def test_SCD24_id_cambia_solo_coincidencia_exacta(self):
        self.senal["id"] = "nuevo"
        self.assertIn("vuelto a unir", self.releer([self.senal])[0])
        self.assertEqual(self.config.uniones[0].id, "nuevo")

    def test_SCD25_tipo_cambia_variable_intacta(self):
        self.senal["type"] = "Int"
        self.assertIn("tipo", self.releer([self.senal])[0])
        self.assertEqual(self.doc["variables"][0]["type"]["kind"], "bool")

    def test_SCD26_nombre_de_variable_de_otro_papel_en_rojo(self):
        catalogo = [self.senal, senal("sensor", "led")]
        self.releer(catalogo)
        self.assertIn("Ya hay", self.propuestas(catalogo).filas[1].motivo)

    def test_SCD27_salida_borrada_no_se_une_a_sensor(self):
        catalogo = [senal("sensor", "led")]
        self.releer(catalogo)
        self.assertTrue(self.config.uniones[0].motivo)
        self.assertEqual(self.config.uniones[0].id, "original")
        self.assertIn("Ya hay", self.propuestas(catalogo).filas[0].motivo)

    def test_SCD28_papel_o_tipo_de_variable_cambiado(self):
        for campo, valor in (("role", "input"), ("type", {"kind": "int"})):
            with self.subTest(campo=campo):
                self.doc = copy.deepcopy(self.anterior)
                self.doc["variables"][0][campo] = valor
                antes = copy.deepcopy(self.doc)
                reconciliar(self.config, self.doc, [self.senal])
                self.assertTrue(self.config.uniones[0].motivo)
                self.assertEqual(self.doc, antes)

    def test_SCD29_varias_coincidencias_no_se_elige(self):
        catalogo = [senal("uno", "led", papel="Output"), senal("dos", "led", papel="Output")]
        self.releer(catalogo)
        self.assertEqual(self.config.uniones[0].id, "original")
        self.assertIn("varias", self.config.uniones[0].motivo)


if __name__ == "__main__":
    unittest.main()
