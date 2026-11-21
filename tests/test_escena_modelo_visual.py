"""SESC05..SESC09: modelo visual y su realización en Qt frente al dibujo directo (V2-E3, paso 2)."""
from importlib.util import find_spec
from unittest import TestCase, skipUnless

QT = bool(find_spec("PySide6"))


def huella(escena):
    from tools.choque_escena import huella_item
    return [huella_item(i, False) for i in escena.items()]  # en el orden de apilado que da Qt


def entradas(e, variante):
    sel = e.seleccion_dibujo() | {e.ed.model["steps"][0]["id"], e.ed.model["transitions"][0]["id"]}
    return {
        "plano": (set(), set(), set()),
        "seleccion": (sel, {e.ed.model["transitions"][1]["id"]}, set()),
        "parpadeo": (sel, set(), {e.ed.model["steps"][1]["id"], e.ed.model["actions"][0]["id"]}),
    }[variante]


@skipUnless(QT, "requiere PySide6")
class ModeloVisual(TestCase):
    def proyectos(self):
        from tools import choque_escena as c
        from tempfile import TemporaryDirectory
        tmp = TemporaryDirectory(prefix="mv-test-")
        self.addCleanup(tmp.cleanup)
        return c.proyectos(tmp.name)

    def comparar(self, e, S, variante, dependencias):
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio import diagrama as dg
        from escritorio.escena import realizador
        from escritorio.escena.modelo_visual import construir
        sel, marcados, naranja = entradas(e, variante) if e.ed.model["actions"] else (set(), set(), set())
        directa, uniones, ordenes = QGraphicsScene(), [], []
        cajas = dg._recorrer(dg._Pintor(directa), e.M, S, sel, marcados, naranja, uniones, ordenes, dependencias)
        mv = construir(e.M, S, sel, marcados, naranja, dependencias)
        realizada = QGraphicsScene()
        realizador.todo(realizada, mv)
        self.assertEqual(huella(realizada), huella(directa), (variante, dependencias))
        self.assertEqual((mv.cajas, mv.uniones, mv.ordenes), (cajas, uniones, ordenes))
        return mv

    def test_SESC05_realizar_el_modelo_visual_da_la_misma_escena_que_el_dibujo_directo(self):
        """REQ-EDT-01: en GEMMA, el proyecto generado y Linea larga, con selección, marcas, parpadeo y dependencias, la escena
        creada desde los descriptores coincide en cada ítem, su apilado y las cajas con la del dibujo directo."""
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import ventana
        with ventana() as w:
            for nombre, ruta in self.proyectos().items():
                reiniciar(w, ruta)
                for variante in ("plano", "seleccion", "parpadeo"):
                    for dependencias in (False, True):
                        with self.subTest(proyecto=nombre, variante=variante, dependencias=dependencias):
                            self.comparar(w.edicion, {}, variante, dependencias)

    def test_SESC06_dibujar_y_el_dibujo_directo_dan_lo_mismo_en_edicion_y_en_simulacion(self):
        """REQ-SIM-01: `dibujar` (por descriptores) coincide con `dibujar_directo` sobre la escena del diagrama, también con el
        estado de una simulación en marcha."""
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio import diagrama as dg
        from tools.choque_escena import huella_item, reiniciar
        from tools.entorno_v2_e0 import GEMMA, bombear, paso, play, ventana
        with ventana() as w:
            reiniciar(w, GEMMA)
            for fase in ("edicion", "simulacion"):
                if fase == "simulacion":
                    play(w)
                    paso(w, "avanzar", us=1_000_000)
                    bombear()
                    M, S = w.v.model, w.v.state()
                else:
                    M, S = w.edicion.M, {}
                a, b = w.diagrama.scene(), QGraphicsScene()
                ua, oa, ub, ob = [], [], [], []
                ca = dg.dibujar(a, M, S, None, None, None, ua, oa, False)
                cb = dg.dibujar_directo(b, M, S, None, None, None, ub, ob, False)
                self.assertEqual([huella_item(i, False) for i in a.items()], [huella_item(i, False) for i in b.items()], fase)
                self.assertEqual((ca, ua, oa), (cb, ub, ob), fase)

    def test_SESC07_cada_grupo_es_contiguo_y_cada_elemento_tiene_su_objeto(self):
        """REQ-EDT-01: los descriptores de un objeto son contiguos en el orden de dibujo, ninguno queda sin grupo y todo
        elemento del modelo tiene el suyo."""
        from escritorio.escena.modelo_visual import construir
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import ventana
        with ventana() as w:
            for nombre, ruta in self.proyectos().items():
                reiniciar(w, ruta)
                e = w.edicion
                mv = construir(e.M, {}, e.seleccion_dibujo(), set(), set(), True)
                claves = [c for c, _ in mv.secuencia]
                vistos = [c for i, c in enumerate(claves) if i == 0 or claves[i - 1] != c]
                self.assertEqual(len(vistos), len(set(vistos)), f"{nombre}: algún grupo no es contiguo")
                self.assertNotIn(("sin_grupo",), mv.objetos)
                self.assertEqual(tuple(dict.fromkeys(claves)), mv.orden)
                self.assertTrue(all(mv.objetos[c] for c in mv.orden))
                for s in e.ed.model["steps"]:
                    self.assertIn(("etapa", s["id"]), mv.objetos)
                for t in e.ed.model["transitions"]:
                    self.assertIn(("transicion", t["id"]), mv.objetos)
                for a in e.ed.model["actions"]:
                    self.assertIn(("accion", a["id"]), mv.objetos)
                for r in e.M["links"]:
                    self.assertIn(("enlace", r["id"]), mv.objetos)

    def test_SESC08_construir_es_determinista_y_no_cambia_el_modelo(self):
        """REQ-EDT-01: dos construcciones seguidas son iguales y `M` no se modifica."""
        from copy import deepcopy
        from escritorio.escena.modelo_visual import construir
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        with ventana() as w:
            reiniciar(w, GEMMA)
            e = w.edicion
            antes = deepcopy(e.M)
            a = construir(e.M, {}, set(), set(), set(), False)
            self.assertEqual(a, construir(e.M, {}, set(), set(), set(), False))
            self.assertEqual(antes, e.M)

    def test_SESC09_el_modelo_visual_se_puede_construir_sin_figuras_en_la_escena(self):
        """REQ-EDT-01: construir no crea ítems en ninguna escena (solo mide textos)."""
        from escritorio.escena.modelo_visual import construir
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        with ventana() as w:
            reiniciar(w, GEMMA)
            antes = len(w.diagrama.scene().items())
            construir(w.edicion.M, {}, set(), set(), set(), False)
            self.assertEqual(len(w.diagrama.scene().items()), antes)
