"""SCD: configuración antigua, recurso directo y archivo de proyecto (I5)."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conexion.configuracion import ARCHIVO, Configuracion
from conexion.persistencia_directa import recurso
from conexion.uniones import Union
from grafcet.builder import M


class Persistencia(unittest.TestCase):
    def setUp(self):
        self.doc = M().var("marcha").step("0", True).doc
        self.config = Configuracion(host="localhost", puerto=7410, modo="directo", modelo=self.doc["id"])
        self.config.uniones = [Union(self.doc["variables"][0]["id"], "guid", "Pulsador marcha", "Bit", "input")]

    def test_SCD40_guardar_y_abrir_identidades_sin_cambiar_modelo(self):
        antes = copy.deepcopy(self.doc)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / ARCHIVO
            self.config.guardar(ruta, self.doc)
            cargada = Configuracion.cargar(ruta, self.doc)
            self.assertEqual(cargada, self.config)
            self.assertEqual(self.doc, antes)
            self.assertTrue(recurso(ruta).exists())

    def test_SCD41_cargador_anterior_real_abre_modo_directo(self):
        codigo = subprocess.check_output(["git", "show", "b856ff0:conexion/configuracion.py"], cwd=ROOT)
        namespace = {"__name__": "configuracion_anterior"}
        import types
        modulo = types.ModuleType("configuracion_anterior")
        sys.modules[modulo.__name__] = modulo
        self.addCleanup(sys.modules.pop, modulo.__name__, None)
        exec(compile(codigo, "configuracion_anterior.py", "exec"), modulo.__dict__)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / ARCHIVO
            self.config.guardar(ruta, self.doc)
            cargada = modulo.Configuracion.cargar(ruta, self.doc)
            self.assertEqual(cargada.senales, [])
            self.assertEqual(cargada.puerto, 7410)

    def test_SCD42_antigua_sin_recurso_abre_en_modbus(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mapa.json"
            Configuracion().guardar(ruta, self.doc)
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            datos.pop("modo")
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            cargada = Configuracion.cargar(ruta, self.doc)
            self.assertEqual(cargada.modo, "modbus")
            self.assertEqual(cargada.uniones, [])

    def test_SCD43_recurso_corrupto_rechazado_y_union_rota_conservada(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mapa.json"
            self.config.guardar(ruta, self.doc)
            otro = copy.deepcopy(self.doc)
            otro["variables"] = []
            cargada = Configuracion.cargar(ruta, otro)
            self.assertEqual(len(cargada.uniones), 1)
            recurso(ruta).write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                Configuracion.cargar(ruta, self.doc)

    def test_SCD44_archivo_grafnet_incluye_recurso_y_se_vuelve_a_abrir(self):
        from escritorio.proyecto_archivo import abrir_grafnet, guardar_grafnet
        from grafcet.editor import Editor
        from grafcet.persistence import add_document, new_project
        editor = Editor(self.doc)
        proyecto = new_project("proyecto", "Prueba")
        add_document(proyecto, editor.model)
        add_document(proyecto, editor.presentation)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "prueba.grafnet"
            clave = b"prueba-de-recurso-directo-local-32"
            guardado = guardar_grafnet(ruta, proyecto, clave,
                                      preparar=lambda raiz: self.config.guardar(raiz / ARCHIVO, self.doc))
            guardado.cerrar()
            abierto = abrir_grafnet(ruta, clave)
            try:
                self.assertEqual(Configuracion.cargar(abierto.raiz / ARCHIVO, self.doc), self.config)
            finally:
                abierto.cerrar()


if __name__ == "__main__":
    unittest.main()
