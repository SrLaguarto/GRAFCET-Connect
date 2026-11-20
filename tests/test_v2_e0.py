"""Pruebas breves de los bancos y del proyecto de carga de la versión 2.0."""
from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path
import tempfile
import unittest

from grafcet.view import Vista, layout_from_presentation
from tools.proyecto_referencia import construir


class ProyectoReferencia(unittest.TestCase):
    def test_construye_valida_y_simula_diez_pasos(self):
        e = construir()
        m = e.model
        self.assertEqual(len(m["steps"]), 100)
        self.assertEqual(len(m["actions"]), 300)
        self.assertEqual(len(m["partials"]), 8)
        self.assertEqual({f["targetKind"] for f in m["forces"]}, {"current", "explicit"})
        self.assertEqual(len(m["hierarchy"]["macros"]), 1)
        self.assertEqual(len(m["hierarchy"]["enclosures"]), 1)
        comentarios = e.comments()
        self.assertEqual(sum(s["id"] in comentarios for s in m["steps"]), 50)
        self.assertTrue(all(len(s["actionRefs"]) == 3 for s in m["steps"]))
        self.assertFalse(e.draft_actions())
        validacion = e.validate()
        self.assertTrue(validacion.can_simulate, validacion.diagnostics)
        layout = layout_from_presentation(e.presentation)
        v = Vista(m["id"], "Referencia", "", lambda: (m, layout), {}, presentation=e.presentation)
        anterior = v.state()["situation"]
        for _ in range(10):
            v.act("avanzar", {"us": 1_000_000})
            estado = v.state()
            self.assertEqual(estado["status"], "pausada-estable")
            self.assertNotEqual(estado["situation"], anterior)
            anterior = estado["situation"]
        variables = {x["name"]: x["id"] for x in m["variables"]}
        v.act("fijar", {"cambios": {variables["Pulso"]: True}})
        self.assertEqual(v.s.status, "pausada-estable")
        self.assertEqual(v.s.z.values[variables["C"]], 1)


@unittest.skipUnless(find_spec("PySide6"), "requiere PySide6")
class Bancos(unittest.TestCase):
    def test_muestra_de_cada_operacion(self):
        from tools.banco_rendimiento import medir_proyecto
        from tools.entorno_v2_e0 import GEMMA

        datos = medir_proyecto(GEMMA, calentamientos=0, repeticiones=1, pasos=1, perfil=True, periodico=True)
        operaciones = datos["operaciones"]
        self.assertEqual(set(operaciones), {
            "abrir", "anadir_accion", "mover_etapa", "deshacer", "rehacer", "equidistanciar",
            "receptividad", "play", "paso", "stop",
        })
        self.assertEqual(len(datos["cambios_situacion"]), 1)
        for nombre, fila in operaciones.items():
            with self.subTest(operacion=nombre):
                self.assertEqual(len(fila["muestras_ms"]), 1)
                self.assertGreater(fila["mediana_ms"], 0)
                self.assertEqual(fila["p90_ms"], fila["mediana_ms"])
                acumulados = [f["acumulado_ms"] for f in fila["perfil"]["top15"]]
                self.assertEqual(len(acumulados), 15)
                self.assertEqual(acumulados, sorted(acumulados, reverse=True))

    def test_genera_dos_imagenes_y_compara(self):
        from tools.banco_imagenes import Fuente, comparar, generar
        from PySide6.QtGui import QColor, QImage

        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            base = raiz / "base"
            fuentes = [Fuente("aula", clave="aula_marcha")]
            datos = generar(base, fuentes=fuentes, estados=("edicion", "etapa"))
            self.assertEqual(set(datos["imagenes"]), {"aula/edicion.png", "aula/etapa.png"})
            for nombre, huella in datos["imagenes"].items():
                self.assertEqual(sha256((base / nombre).read_bytes()).hexdigest(), huella)
                self.assertEqual(QImage(str(base / nombre)).size().toTuple(), (1366, 768))
            self.assertEqual(comparar(base, base), {})

            cambiada, diferencias = raiz / "cambiada", raiz / "diferencias"
            (cambiada / "aula").mkdir(parents=True)
            imagen = QImage(str(base / "aula/edicion.png"))
            imagen.setPixelColor(0, 0, QColor("red"))
            self.assertTrue(imagen.save(str(cambiada / "aula/edicion.png")))
            self.assertEqual(comparar(base, cambiada, diferencias), {
                "aula/edicion.png": "modificada", "aula/etapa.png": "ausente",
            })
            for nombre in datos["imagenes"]:
                self.assertTrue((diferencias / nombre).is_file())


if __name__ == "__main__":
    unittest.main()
