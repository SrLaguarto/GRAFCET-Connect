import copy
from pathlib import Path
import tempfile
import unittest

from conexion.configuracion import ARCHIVO, Configuracion, Senal
from grafcet.examples import EJEMPLOS
from grafcet.persistence import add_document, new_project, save_project


class ConfigTests(unittest.TestCase):
    def test_SFIO26_escala_factoryio_100_y_migracion(self):
        """REQ-DAT-02: entradas/salidas numéricas usan 100 incluso en mapas anteriores."""
        import json
        from grafcet.builder import M
        doc=M().var("sensor",kind="decimal",scale=2).var("consigna","output","int").step("0",True).doc
        c=Configuracion(senales=[Senal("sensor","input-register",0,"INT16"),
                                 Senal("consigna","holding",0,"UINT16")])
        self.assertEqual([s.escala for s in c.senales],["100","100"])
        with tempfile.TemporaryDirectory() as tmp:
            ruta=Path(tmp)/"conexion.json"
            c.guardar(ruta,doc)
            datos=json.loads(ruta.read_text(encoding="utf-8"))
            for s in datos["senales"]:
                s["escala"]="1"
            ruta.write_text(json.dumps(datos),encoding="utf-8")
            cargada=Configuracion.cargar(ruta,doc)
            self.assertEqual([s.escala for s in cargada.senales],["100","100"])

    def test_SFIO23_limites_de_canales_configurados(self):
        """REQ-DAT-02: rangos explícitos, asignaciones fuera y compatibilidad sin rangos."""
        for rango in ({"offset":0,"cantidad":257}, {"offset":65535,"cantidad":2},
                      {"offset":-1,"cantidad":2}, {"offset":0,"cantidad":True}):
            with self.subTest(rango=rango), self.assertRaises(ValueError):
                Configuracion(canales={"discrete":rango}).validar(self.doc)
        c=Configuracion(senales=[Senal(self.var["id"],"discrete",5)])
        c.validar(self.doc)
        c.canales={"discrete":{"offset":6,"cantidad":2}}
        with self.assertRaises(ValueError):
            c.validar(self.doc)
        c.canales={"discrete":{"offset":5,"cantidad":1}}
        c.validar(self.doc)

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
