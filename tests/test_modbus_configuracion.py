import copy
from pathlib import Path
import tempfile
import unittest

from conexion.configuracion import ARCHIVO, Configuracion, Senal
from grafcet.examples import EJEMPLOS
from grafcet.persistence import add_document, new_project, save_project


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.doc = EJEMPLOS[next(iter(EJEMPLOS))][2]()[0].doc
        self.var = next(v for v in self.doc["variables"] if v["role"] == "input" and v["type"]["kind"] == "bool")
        self.config = Configuracion(senales=[Senal(self.var["id"], "discrete", 0)])

    def test_SFIO04_persistencia_separada(self):
        """REQ-DAT-02: configuración externa no cambia el documento ni se borra al guardar."""
        original = copy.deepcopy(self.doc)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / ARCHIVO
            self.config.guardar(ruta, self.doc)
            p = new_project("p", "Prueba")
            add_document(p, self.doc)
            save_project(Path(tmp), p)
            c = Configuracion.cargar(ruta, self.doc)
            self.assertEqual(c.senales, self.config.senales)
            self.assertEqual(c.modelo, self.doc["id"])
        self.assertEqual(self.doc, original)

    def test_SFIO05_mapa_invalido(self):
        """REQ-ROB-01: no admite asociaciones incompatibles o repetidas."""
        for s in (Senal("inexistente", "discrete", 0), Senal(self.var["id"], "discrete", -1),
                  Senal(self.var["id"], "holding", 0), Senal(self.var["id"], "coil", 0, escala="0")):
            with self.subTest(s=s), self.assertRaises(ValueError):
                Configuracion(senales=[s]).validar(self.doc)
        self.config.senales *= 2
        with self.assertRaises(ValueError):
            self.config.validar(self.doc)
