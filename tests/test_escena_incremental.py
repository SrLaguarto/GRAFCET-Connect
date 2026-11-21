"""SESC20..SESC28: la escena incremental del editor (V2-E3, paso 4) y la unicidad de las claves del modelo visual."""
import sys
from importlib.util import find_spec
from pathlib import Path
from unittest import TestCase, mock, skipUnless

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from escritorio.escena.descriptores import Grabadora  # noqa: E402
from test_escena_descriptores import servicios_falsos  # noqa: E402

QT = bool(find_spec("PySide6"))


class ClavesUnicas(TestCase):
    def test_SESC20_una_clave_que_reaparece_pasa_a_ser_otra_y_cada_grupo_es_contiguo(self):
        """REQ-EDT-01: al volver a entrar en un grupo del que se salió, el grupo nuevo tiene clave propia (`#2`, `#3`…)."""
        g = Grabadora(servicios_falsos())
        a, b = ("acciones", "s1"), ("etapa", "s1")
        g.entrar(a)
        g.line(0, 0, 1, 1, g.pen("text"), 1)
        g.entrar(b)
        g.line(0, 0, 2, 2, g.pen("text"), 1)
        g.entrar(a)          # reaparece, separada de la primera
        g.line(0, 0, 3, 3, g.pen("text"), 1)
        g.entrar(a)          # seguir en el grupo actual no lo parte
        g.line(0, 0, 4, 4, g.pen("text"), 1)
        g.entrar(b)
        g.line(0, 0, 5, 5, g.pen("text"), 1)
        self.assertEqual(g.orden, (a, b, (*a, "#2"), (*b, "#2")))
        self.assertEqual([len(g.objetos[c]) for c in g.orden], [1, 1, 2, 1])
        claves = [c for c, _ in g.secuencia]
        vistos = [c for i, c in enumerate(claves) if i == 0 or claves[i - 1] != c]
        self.assertEqual(len(vistos), len(set(vistos)))

    def test_SESC21_un_grupo_sin_descriptores_no_cuenta_como_salida(self):
        """REQ-EDT-01: entrar y salir sin dibujar nada no obliga a renombrar la clave."""
        g = Grabadora(servicios_falsos())
        previo = g.entrar(("nota", "n1"))
        g.entrar(previo)
        g.entrar(("nota", "n1"))
        g.line(0, 0, 1, 1, g.pen("text"), 1)
        self.assertEqual(g.orden, (("nota", "n1"),))


@skipUnless(QT, "requiere PySide6")
class EscenaIncrementalReal(TestCase):
    def setUp(self):
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        self.contexto = ventana()
        self.w = self.contexto.__enter__()
        self.addCleanup(self.contexto.__exit__, None, None, None)
        reiniciar(self.w, GEMMA)
        self.e = self.w.edicion
        self.sc = self.w.diagrama.scene()

    def igual_que_el_dibujo_directo(self):
        from tools import choque_escena as c
        c.comprobar(self.w, momento="test")

    def mover(self, sid, dx):
        from PySide6.QtCore import QPointF
        from escritorio.diagrama import posiciones
        o = QPointF(*posiciones(self.e.M)[sid])
        self.e.prensar(o)
        self.e.mover(o + QPointF(dx, 0))
        self.e.soltar(o + QPointF(dx, 0))

    def test_SESC22_mover_una_etapa_solo_crea_lo_que_cambia_y_deja_el_resto_como_estaba(self):
        """REQ-EDT-01: tras mover una etapa se crean muy pocos ítems, los de lo lejano conservan su identidad y la escena es la
        del dibujo directo."""
        from PySide6.QtWidgets import QGraphicsTextItem
        from escritorio.escena import realizador
        e = self.e
        lejos = e.ed.model["steps"][-1]["id"]
        sid = next(s["id"] for s in e.ed.model["steps"] if s["label"] == "100")
        textos = {id(i): i for i in self.sc.items() if isinstance(i, QGraphicsTextItem) and lejos in (i.data(43) or ())}
        total = len(self.sc.items())
        with mock.patch.object(realizador, "crear", wraps=realizador.crear) as crear, \
                mock.patch.object(self.sc, "_rehacer", wraps=self.sc._rehacer) as rehacer:
            self.mover(sid, -80)
            self.assertFalse(rehacer.called, "mover una etapa no debe rehacer la escena")
        self.assertLess(crear.call_count, total // 3)
        self.assertTrue(textos.keys() <= {id(i) for i in self.sc.items()}, "los textos de una etapa lejana siguen siendo los mismos")
        self.igual_que_el_dibujo_directo()

    def test_SESC23_si_construir_falla_la_escena_queda_como_estaba(self):
        """REQ-EDT-09: una excepción al construir el modelo visual no deja la escena a medias (H1)."""
        from escritorio.escena import modelo_visual
        antes = [id(i) for i in self.sc.items()]
        with mock.patch.object(modelo_visual, "construir", side_effect=KeyError("fallo simulado")):
            with self.assertRaises(KeyError):
                self.w._redibujar_edicion()
        self.assertEqual([id(i) for i in self.sc.items()], antes)
        self.igual_que_el_dibujo_directo()
        self.w._redibujar_edicion()
        self.igual_que_el_dibujo_directo()

    def test_SESC24_si_aplicar_falla_se_rehace_la_escena_entera(self):
        """REQ-EDT-09: un fallo al aplicar la diferencia rehace la escena por completo y la deja como el dibujo directo."""
        from escritorio.escena import realizador
        sid = self.e.ed.model["steps"][3]["id"]
        def falla(*args):  # (no un Mock: guardaría los ítems de sus llamadas y los dejaría vivos tras destruirse la escena)
            raise RuntimeError("fallo simulado")

        with mock.patch.object(realizador, "actualizar", falla):
            self.mover(sid, 120)
        self.assertIsInstance(self.sc.error, RuntimeError)
        self.igual_que_el_dibujo_directo()
        self.sc.error = None
        self.mover(sid, -120)
        self.assertIsNone(self.sc.error)
        self.igual_que_el_dibujo_directo()

    def test_SESC25_las_marcas_provisionales_se_retiran_al_redibujar(self):
        """REQ-EDT-01: el lazo, el imán y las anclas no sobreviven a un redibujado ni se duplican."""
        from PySide6.QtCore import QPointF
        d = self.w.diagrama
        d.lazo(QPointF(0, 0), QPointF(50, 50))
        d.marcar_prohibido([d.scene().sceneRect().adjusted(0, 0, -10, -10)])
        provisionales = [d.cuadro, *d.prohibidos]
        self.assertTrue(all(p.scene() is self.sc for p in provisionales))
        self.w._redibujar_edicion()
        self.assertTrue(all(p.scene() is None for p in provisionales))
        self.assertEqual((d.cuadro, d.prohibidos), (None, []))
        self.igual_que_el_dibujo_directo()

    def test_SESC26_play_y_stop_dejan_la_escena_como_el_dibujo_directo(self):
        """REQ-SIM-01: Play y Stop pasan por la escena incremental (E4: también al simular hay registro) y la dejan como el dibujo
        directo."""
        from tools.entorno_v2_e0 import bombear, play
        play(self.w)
        bombear()
        self.assertIsNotNone(self.sc.modelo)
        self.igual_que_el_dibujo_directo()
        self.w.a_ejecutar.trigger()
        bombear()
        self.assertEqual(self.w.modo, "editar")
        self.assertIsNotNone(self.sc.modelo)
        self.igual_que_el_dibujo_directo()

    def test_SESC27_equidistanciar_rehace_por_lotes_y_queda_igual(self):
        """REQ-EDT-01: cuando cambia casi todo, se rehace la escena y el resultado coincide con el dibujo directo."""
        e = self.e
        sid = next(s["id"] for s in e.ed.model["steps"] if s["label"] == "100")
        e.seleccionar([sid])
        self.assertTrue(e.equidistanciar([sid]))
        self.igual_que_el_dibujo_directo()
        e.deshacer()
        self.igual_que_el_dibujo_directo()

    def test_SESC28_los_proyectos_reales_no_necesitan_claves_repetidas(self):
        """REQ-EDT-01: en GEMMA, el proyecto generado y Linea larga ninguna clave del modelo visual lleva sufijo `#n`."""
        from tempfile import TemporaryDirectory
        from escritorio.escena.modelo_visual import construir
        from tools import choque_escena as c
        with TemporaryDirectory(prefix="mv-test-") as tmp:
            for nombre, ruta in c.proyectos(tmp).items():
                c.reiniciar(self.w, ruta)
                e = self.w.edicion
                ids = [s["id"] for s in e.ed.model["steps"][:3]] + [a["id"] for a in e.ed.model["actions"][:3]]
                for sel in (set(), set(ids), set(ids) | {f"accion:{i}" for i in ids}):
                    mv = construir(e.M, {}, sel, {ids[0]}, {ids[1]}, True)
                    repetidas = [k for k in mv.objetos if k and str(k[-1]).startswith("#")]
                    self.assertEqual(repetidas, [], f"{nombre}: {repetidas[:3]}")
                    self.assertNotIn(("sin_grupo",), mv.objetos)

    def test_SESC29_sin_el_apilado_la_prueba_de_choque_lo_detecta(self):
        """REQ-EDT-01: si `_apilar` no coloca los ítems nuevos, el orden entre ítems de igual `z` difiere del dibujo directo y la
        comparación de la prueba de choque lo señala."""
        from escritorio.escena.escena import EscenaIncremental
        from tools import choque_escena as c
        secuencia = [r for r in c.generar(11, 80) if r["op"] in ("anadir_accion", "anadir_etapa", "anadir_transicion", "mover",
                                                                   "texto_accion", "condicion", "comentario")][:30]
        with mock.patch.object(EscenaIncremental, "_apilar", lambda *a, **k: None):
            f = c.ejecutar(self.w, c.GEMMA, secuencia)
        self.assertIsNotNone(f, "sin apilar, alguna operación debería dejar el orden distinto")
        self.assertEqual(f.tipo, "ESC-3")
        self.assertIsNone(c.ejecutar(self.w, c.GEMMA, secuencia), "con el apilado, la misma secuencia pasa")

    def test_SESC30_ningun_item_de_la_escena_pasa_a_ser_propiedad_de_python(self):
        """REQ-EDT-09: tras mover, alternar dependencias y volver de la simulación, ningún ítem de la escena es propiedad de
        Python (PySide lo borraría, aún dentro de la escena, al morir su envoltorio: así se rompió `parentItem()`)."""
        import shiboken6
        from tools.entorno_v2_e0 import bombear, play
        d = self.w.diagrama
        self.mover(self.e.ed.model["steps"][3]["id"], 100)
        d.mostrar_dependencias(False)
        d.mostrar_dependencias(True)
        play(self.w)
        bombear()
        self.w.a_ejecutar.trigger()
        bombear()
        self.mover(self.e.ed.model["steps"][5]["id"], -100)
        self.assertEqual([i for i in self.sc.items() if shiboken6.ownedByPython(i)], [])
        self.assertEqual([i for n in self.sc.nodos.values() for _, items in n for i in items if shiboken6.ownedByPython(i)], [])

    def test_SESC31_la_ayuda_emergente_no_borra_items_de_la_escena(self):
        """REQ-EDT-09: pasar el ratón por un ítem sin ayuda (una línea de enlace) no lo deja como propiedad de Python ni lo borra de
        la escena, en edición y en simulación (`parentItem()` lo hacía)."""
        import gc
        import shiboken6
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QGraphicsPathItem
        from escritorio.ayudas_emergentes import texto_del_control
        from tools.entorno_v2_e0 import bombear, play

        class Evento:
            def __init__(self, p):
                self.p = p

            def pos(self):
                return self.p

        d = self.w.diagrama

        def pasar_el_raton():
            sc = d.scene()
            antes = len(sc.items())
            candidatos = [i for i in sc.items() if isinstance(i, QGraphicsPathItem) and not i.toolTip()]
            visitados = 0
            for i in candidatos:
                p = i.mapToScene(i.path().pointAtPercent(0.5))
                pos = d.mapFromScene(p)
                alcanzado = d.itemAt(pos)
                if alcanzado is None or alcanzado.toolTip():
                    continue
                texto_del_control(d.viewport(), Evento(QPoint(pos)))
                visitados += 1
                del alcanzado
                if visitados == 15:
                    break
            self.assertGreaterEqual(visitados, 5, "debe haber pasado el ratón por varios ítems sin ayuda")
            del candidatos, i
            gc.collect()
            self.assertEqual(len(sc.items()), antes)
            self.assertEqual([x for x in sc.items() if shiboken6.ownedByPython(x)], [])

        pasar_el_raton()
        play(self.w)
        bombear()
        pasar_el_raton()
        self.w.a_ejecutar.trigger()
        bombear()
        self.igual_que_el_dibujo_directo()

    def test_SESC32_el_apilado_de_igual_z_es_el_del_dibujo_completo_con_cualquier_secuencia(self):
        """REQ-EDT-01: con muchos objetos de igual `z`, altas, bajas, cambios y reordenamientos al azar dejan el apilado
        exactamente como lo da una escena nueva (`stackBefore` solo actúa entre ítems de la misma `z`)."""
        from random import Random
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio.escena import escena as E, realizador
        from escritorio.escena.diferencia import diferencia
        from escritorio.escena.modelo_visual import ModeloVisual
        from tools.choque_escena import huella_item

        def modelo(estado):
            objetos = {("obj", str(n)): (("rect", x, 0.0, 10.0, 10.0, None, "panel", 0, z, None, None, ()),) for n, z, x in estado}
            secuencia = tuple((c, d) for c, ds in objetos.items() for d in ds)
            return ModeloVisual(objetos, tuple(objetos), secuencia)

        def apilado(escena):
            return [huella_item(i, False) for i in escena.items()]

        azar = Random(32)
        siguiente = [0]

        def nuevo():
            siguiente[0] += 1
            return (siguiente[0], azar.choice((1.0, 10.0, 10.0)), float(siguiente[0]))

        estado = [nuevo() for _ in range(40)]
        sc = E.EscenaIncremental(None)
        sc.aplicar(modelo(estado))
        for paso in range(300):
            previo = list(estado)
            for _ in range(azar.randint(1, 4)):
                accion = azar.choice(("alta", "baja", "mover", "cambiar"))
                if accion == "alta":
                    estado.insert(azar.randrange(len(estado) + 1), nuevo())
                elif accion == "baja" and len(estado) > 30:
                    estado.pop(azar.randrange(len(estado)))
                elif accion == "mover":
                    estado.insert(azar.randrange(len(estado) + 1), estado.pop(azar.randrange(len(estado))))
                else:
                    k = azar.randrange(len(estado))
                    n, z, x = estado[k]
                    estado[k] = (n, azar.choice((1.0, 10.0)), x + 0.5)
            mv = modelo(estado)
            cambios = diferencia(sc.modelo, mv)
            if cambios.vacio:
                continue
            sc._aplicar(cambios, mv)  # sin el atajo de «rehacer todo»
            esperado = QGraphicsScene()
            realizador.todo(esperado, mv)
            self.assertEqual(apilado(sc), apilado(esperado), f"paso {paso}: {[e[0] for e in previo]} -> {[e[0] for e in estado]}")
