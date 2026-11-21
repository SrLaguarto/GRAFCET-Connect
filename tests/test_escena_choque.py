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
        from escritorio.escena.escena import EscenaIncremental
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA
        original = EscenaIncremental.aplicar

        def pierde_una_etapa(escena, mv):
            original(escena, mv)
            etapas = [k for k in mv.objetos if k[0] == "etapa"]
            if len(etapas) > 28:  # GEMMA tiene 28 etapas: con una más, la escena pierde el cuadrado de la última
                escena.removeItem(escena.nodos[etapas[-1]][0][1][0])

        with TemporaryDirectory(prefix="choque-test-") as tmp, mock.patch.object(EscenaIncremental, "aplicar", pierde_una_etapa):
            secuencia = [r for r in c.generar(SEMILLA, 120) if r["op"] in ("anadir_etapa", "mover", "deshacer", "zoom")][:40]
            f = c.ejecutar_nuevo(GEMMA, secuencia)
            self.assertIsNotNone(f, "no se detectó la figura perdida")
            self.assertIn(f.tipo, ("ESC-1", "ESC-3"))
            minima = c.ddmin(GEMMA, secuencia[:f.indice + 1], f.tipo, 240, cada=1, modelo_cada=1)
            self.assertLessEqual(len(minima), 3)
            datos = c.informe("gemma", SEMILLA, f, minima, Path(tmp) / "fallo.json")
            guardado = json.loads((Path(tmp) / "fallo.json").read_text(encoding="utf-8"))
            self.assertEqual(guardado["secuencia_minima"], minima)
            self.assertIn("--reproducir", datos["repetir"])
            repetido = c.ejecutar_nuevo(GEMMA, guardado["secuencia_minima"])  # desde cero, con otra ventana
            self.assertIsNotNone(repetido)
            self.assertEqual(repetido.tipo, f.tipo)

    def test_SESC95_la_minimizacion_solo_acepta_lo_que_se_reproduce_desde_cero(self):
        """REQ-EDT-09: un fallo que depende del estado de la vista (aquí, «dependencias» apagadas) se minimiza sin perder la
        operación que lo prepara, porque cada candidato se prueba en una ventana nueva."""
        from escritorio.escena.escena import EscenaIncremental
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA
        original = EscenaIncremental.aplicar

        def pierde_con_dependencias_apagadas(escena, mv):
            original(escena, mv)
            if not escena.parent().dependencias:
                escena.removeItem(escena.nodos[next(k for k in mv.orden if k[0] == "etapa")][0][1][0])

        with TemporaryDirectory(prefix="choque-test-") as tmp, \
                mock.patch.object(EscenaIncremental, "aplicar", pierde_con_dependencias_apagadas):
            base = c.generar(SEMILLA, 200)
            secuencia = [r for r in base if r["op"] in ("zoom", "mover")][:6] + [r for r in base if r["op"] == "dependencias"][:1] \
                + [r for r in base if r["op"] in ("zoom", "mover")][6:9]
            fallo = c.ejecutar_nuevo(GEMMA, secuencia)
            self.assertIsNotNone(fallo)
            minima = c.ddmin(GEMMA, secuencia[:fallo.indice + 1], fallo.tipo, 240, cada=1, modelo_cada=1)
            self.assertIn("dependencias", [r["op"] for r in minima], "la operación que prepara el fallo no puede desaparecer")
            self.assertLessEqual(len(minima), 2)
            repetido = c.ejecutar_nuevo(GEMMA, minima)
            self.assertIsNotNone(repetido, "la secuencia mínima debe fallar desde cero")
            self.assertEqual(repetido.tipo, fallo.tipo)
