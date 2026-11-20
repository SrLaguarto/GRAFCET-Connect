"""Regresiones del manejo de entradas y de proyectos sin cambios de situación."""
from argparse import ArgumentTypeError
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless


@skipUnless(find_spec("PySide6"), "requiere PySide6")
class BancoRendimiento(TestCase):
    def test_entradas_booleanas_por_nombre(self):
        from tools.banco_rendimiento import _entradas, _identificar_entradas

        entradas = _entradas("Paro=1, Seta emergencia=0")
        modelo = {"variables": [
            {"id": "p", "name": "Paro", "role": "input", "type": {"kind": "bool"}},
            {"id": "s", "name": "Seta emergencia", "role": "input", "type": {"kind": "bool"}},
            {"id": "q", "name": "Motor", "role": "output", "type": {"kind": "bool"}},
        ]}
        self.assertEqual(_identificar_entradas(modelo, entradas), {"p": True, "s": False})
        for texto in ("Paro=2", "Paro=1,Paro=0", "Paro", "=1", "Paro=0,"):
            with self.subTest(texto=texto), self.assertRaises(ArgumentTypeError):
                _entradas(texto)
        with self.assertRaisesRegex(ValueError, "única entrada booleana"):
            _identificar_entradas(modelo, {"Motor": True})

    def test_edicion_se_mide_aunque_no_haya_cambios_de_situacion(self):
        from escritorio.proyecto_archivo import guardar_grafnet
        from escritorio.sello import CLAVE
        from grafcet.editor import Editor, new_grafcet_document
        from grafcet.persistence import add_document, new_project
        from tools.banco_rendimiento import medir_proyecto, tabla

        ed = Editor(new_grafcet_document("situacion_fija"))
        a = ed.add_step("g", "0", True, at=(240, 100))
        b = ed.add_step("g", "1", at=(240, 440))
        ed.add_transition("g", "false", [a], [b], at=(240, 270))
        var = ed.add_variable("Piloto", "output", {"kind": "bool"})
        ed.add_continuous_action(a, var)
        proyecto = new_project("situacion_fija", "Situación fija")
        add_document(proyecto, ed.model)
        add_document(proyecto, ed.presentation)
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "fijo.grafnet"
            guardar_grafnet(ruta, proyecto, CLAVE).cerrar()
            datos = medir_proyecto(ruta, calentamientos=0, repeticiones=1, pasos=2)
        self.assertEqual(set(datos["operaciones"]), {
            "abrir", "anadir_accion", "mover_etapa", "deshacer", "rehacer", "equidistanciar",
            "receptividad", "play", "stop",
        })
        self.assertEqual(datos["cambios_situacion"], [])
        self.assertEqual(datos["simulacion"]["estado"], "no medida")
        self.assertEqual(datos["simulacion"]["medidos"], 0)
        self.assertIn("0 de 2 cambios de situación", datos["simulacion"]["motivo"])
        self.assertIn("paso (no medido)", tabla({"fijo": datos}))
