"""SESC90..SESC94: prueba de choque del dibujo del editor (V2-E3, paso 0); versión corta de `tools/choque_escena.py`."""
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock, skipUnless
import json

QT = bool(find_spec("PySide6"))
SEMILLA = 20261120


@skipUnless(QT, "requiere PySide6")
class ChoqueEscena(TestCase):
    """Ediciones al azar con semilla fija y redibujados automáticos entre ellas; tras cada paso, un objeto por elemento,
    nada oculto ni vacío y coincidencia con una reconstrucción completa (ver el módulo de la herramienta)."""

    def correr(self, nombre, operaciones, **kw):
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import ventana
        with TemporaryDirectory(prefix="choque-test-") as tmp, ventana() as w:
            ruta = c.proyectos(tmp)[nombre]
            f, datos = c.correr(nombre, ruta, SEMILLA, operaciones, w=w, minimizar_s=120, **kw)
        self.assertIsNone(f, None if f is None else f"{f.tipo} ({f.momento}): {f.detalle[:600]}\n"
                                                     f"secuencia mínima: {json.dumps(datos['secuencia_minima'])[:1500]}\n"
                                                     f"{datos['repetir']}")

    def test_SESC90_choque_guia_gemma(self):
        """REQ-EDT-09: 50 ediciones al azar sobre la guía GEMMA, con comprobación completa tras cada paso."""
        self.correr("gemma", 50)

    def test_SESC91_choque_proyecto_generado_de_100_etapas(self):
        """REQ-EDT-09: 16 ediciones al azar sobre el proyecto de referencia de 100 etapas."""
        self.correr("ref100", 16)

    def test_SESC92_choque_linea_larga(self):
        """REQ-EDT-09: 16 ediciones al azar sobre Linea larga (111 etapas)."""
        from tools import choque_escena as c
        if not c.LINEA.is_file():
            self.skipTest("falta tests/fixtures/referencia/linea_larga.grafnet")
        self.correr("linea", 16)

    def test_SESC93_la_secuencia_es_determinista_y_serializable(self):
        """REQ-EDT-09: la misma semilla da la misma secuencia, hecha solo de datos."""
        from tools import choque_escena as c
        a, b = c.generar(SEMILLA, 50), c.generar(SEMILLA, 50)
        self.assertEqual(a, b)
        self.assertEqual(json.loads(json.dumps(a)), a)
        self.assertNotEqual(a, c.generar(SEMILLA + 1, 50))
        self.assertGreaterEqual({r["op"] for r in c.generar(SEMILLA, 400)}, {"mover", "deshacer", "pegar", "equidistanciar",
                                                                          "play", "texto_accion", "anadir_accion"})

    def test_SESC94_un_fallo_provocado_se_detecta_y_se_minimiza(self):
        """REQ-EDT-09: si el dibujo pierde una figura, la prueba lo detecta, deja un JSON reproducible con una secuencia mínima
        y esa secuencia vuelve a fallar al repetirla."""
        from escritorio import diagrama
        from escritorio.textos_diagrama import EscenaDiagrama
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA, ventana
        original = diagrama.dibujar

        def pierde_una_etapa(scene, M, *args, **kw):
            res = original(scene, M, *args, **kw)
            if isinstance(scene, EscenaDiagrama) and len(M["steps"]) > 28:  # GEMMA tiene 28 etapas
                rect = next(i for i in scene.items() if type(i).__name__ == "QGraphicsRectItem"
                            and M["steps"][-1]["id"] in (i.data(43) or ()))
                scene.removeItem(rect)
            return res

        with TemporaryDirectory(prefix="choque-test-") as tmp, ventana() as w, \
                mock.patch.object(diagrama, "dibujar", pierde_una_etapa):
            secuencia = [r for r in c.generar(SEMILLA, 120) if r["op"] in ("anadir_etapa", "mover", "deshacer", "zoom")][:40]
            f = c.ejecutar(w, GEMMA, secuencia)
            self.assertIsNotNone(f, "no se detectó la figura perdida")
            self.assertIn(f.tipo, ("ESC-1", "ESC-3"))
            minima = c.ddmin(w, GEMMA, secuencia[:f.indice + 1], f.tipo, 120, cada=1, modelo_cada=1)
            self.assertLessEqual(len(minima), 3)
            datos = c.informe("gemma", SEMILLA, f, minima, Path(tmp) / "fallo.json")
            guardado = json.loads((Path(tmp) / "fallo.json").read_text(encoding="utf-8"))
            self.assertEqual(guardado["secuencia_minima"], minima)
            self.assertIn("--reproducir", datos["repetir"])
            repetido = c.ejecutar(w, GEMMA, guardado["secuencia_minima"])
            self.assertIsNotNone(repetido)
            self.assertEqual(repetido.tipo, f.tipo)
