"""SESC10..SESC18: diferencia entre modelos visuales (V2-E3, paso 3)."""
from importlib.util import find_spec
from unittest import TestCase, skipUnless

from escritorio.escena.diferencia import aplicar, diferencia, reordenadas
from escritorio.escena.modelo_visual import ModeloVisual

QT = bool(find_spec("PySide6"))


def sintetico(**objetos):
    """Un modelo visual hecho a mano: cada argumento es un objeto ('tipo_id' -> lista de tipos de descriptor)."""
    obj = {tuple(k.split("_", 1)): tuple((t, k, i) for i, t in enumerate(ts)) for k, ts in objetos.items()}
    secuencia = tuple((c, d) for c, ds in obj.items() for d in ds)
    return ModeloVisual(obj, tuple(obj), secuencia)


class DiferenciaPura(TestCase):
    def test_SESC10_sin_anterior_todo_son_altas(self):
        """REQ-EDT-01: el primer modelo visual es todo altas, sin bajas ni cambios."""
        b = sintetico(etapa_1=["rect", "texto"], etapa_2=["rect"])
        c = diferencia(None, b)
        self.assertEqual(set(c.altas), set(b.objetos))
        self.assertEqual((c.bajas, c.cambiadas, c.reordenadas), ((), {}, ()))
        self.assertEqual(aplicar(None, c), (b.objetos, b.orden))

    def test_SESC11_altas_bajas_y_cambios_con_su_forma(self):
        """REQ-EDT-01: altas, bajas y cambiadas, y si lo cambiado conserva el número y el tipo de sus descriptores."""
        a = sintetico(etapa_1=["rect", "texto"], etapa_2=["rect"], accion_1=["rect", "texto"])
        b = sintetico(etapa_1=["rect", "texto"], etapa_2=["rect", "linea"], accion_3=["rect"])
        b.objetos[("etapa", "1")] = tuple((*d[:2], d[2] + 1) for d in b.objetos[("etapa", "1")])  # mismo tipo, otros datos
        c = diferencia(a, b)
        self.assertEqual(set(c.altas), {("accion", "3")})
        self.assertEqual(c.bajas, (("accion", "1"),))
        self.assertEqual(set(c.cambiadas), {("etapa", "1"), ("etapa", "2")})
        self.assertEqual(c.misma_forma, {("etapa", "1"): True, ("etapa", "2"): False})
        self.assertFalse(c.vacio)

    def test_SESC12_sin_cambios_la_diferencia_esta_vacia(self):
        """REQ-EDT-01: dos modelos visuales iguales no dan ninguna tarea."""
        a = sintetico(etapa_1=["rect"], etapa_2=["rect"])
        self.assertTrue(diferencia(a, sintetico(etapa_1=["rect"], etapa_2=["rect"])).vacio)

    def test_SESC13_orden_cambiado(self):
        """REQ-EDT-01: solo se reordenan los objetos que se mueven, no todos los que quedan detrás."""
        self.assertEqual(reordenadas(tuple("ABCD"), tuple("ACDB")), ("B",))
        self.assertEqual(reordenadas(tuple("ABCD"), tuple("ABCD")), ())
        self.assertEqual(len(reordenadas(tuple("ABC"), tuple("CBA"))), 2)
        self.assertEqual(reordenadas(tuple("ABCD"), tuple("XACYD")), ())  # altas y bajas no cuentan como reorden
        a = sintetico(etapa_1=["rect"], etapa_2=["rect"], etapa_3=["rect"])
        b = sintetico(etapa_3=["rect"], etapa_1=["rect"], etapa_2=["rect"])
        c = diferencia(a, b)
        self.assertEqual(c.reordenadas, (("etapa", "3"),))
        self.assertEqual(c.orden, b.orden)
        self.assertEqual(aplicar(a, c), (b.objetos, b.orden))


@skipUnless(QT, "requiere PySide6")
class DiferenciaReal(TestCase):
    """Sobre la guía GEMMA, con las operaciones reales de `Edicion`."""

    def setUp(self):
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        self.contexto = ventana()
        self.w = self.contexto.__enter__()
        self.addCleanup(self.contexto.__exit__, None, None, None)
        reiniciar(self.w, GEMMA)
        self.e = self.w.edicion

    def mv(self, sel=()):
        from escritorio.escena.modelo_visual import construir
        return construir(self.e.M, {}, set(sel), set(), set(), False)

    def cierra(self, a, b):
        c = diferencia(a, b)
        self.assertEqual(aplicar(a, c), (b.objetos, b.orden))  # la propiedad: aplicar(diferencia(a, b), a) == b
        return c

    def test_SESC14_mover_una_etapa_cambia_su_objeto_y_lo_que_la_rodea(self):
        """REQ-EDT-01: mover una etapa cambia su objeto, el de sus acciones y los enlaces que la tocan, sin altas ni bajas."""
        from PySide6.QtCore import QPointF
        from escritorio.diagrama import posiciones
        e = self.e
        sid = next(s["id"] for s in e.ed.model["steps"] if s["label"] == "100")
        antes = self.mv()
        o = QPointF(*posiciones(e.M)[sid])
        e.prensar(o)
        e.mover(o + QPointF(-80, 0))
        e.soltar(o + QPointF(-80, 0))
        despues = self.mv()
        c = self.cierra(antes, despues)
        self.assertIn(("etapa", sid), c.cambiadas)
        self.assertTrue(any(k[0] == "enlace" for k in c.cambiadas))
        self.assertEqual((c.altas, c.bajas), ({}, ()))
        self.assertLess(len(c.cambiadas), len(antes.objetos) // 2, "mover una etapa no debe cambiar medio dibujo")

    def test_SESC15_anadir_y_borrar_una_accion(self):
        """REQ-EDT-01: añadir una acción da de alta su objeto (sin bajas) y borrarla lo da de baja."""
        e = self.e
        sid = e.ed.model["steps"][0]["id"]
        antes = self.mv()
        ids = {a["id"] for a in e.ed.model["actions"]} | {b["id"] for b in e.ed.draft_actions()}
        e.anadir_accion(sid)
        despues = self.mv()
        c = self.cierra(antes, despues)
        nuevas = {b["id"] for b in e.ed.draft_actions()} | {a["id"] for a in e.ed.model["actions"]}
        (nueva,) = nuevas - ids
        self.assertIn(("accion", nueva), c.altas)
        self.assertEqual(c.bajas, ())
        e.seleccionar([nueva])
        e.borrar()
        c2 = self.cierra(despues, self.mv())
        self.assertIn(("accion", nueva), c2.bajas)

    def test_SESC16_deshacer_y_rehacer_devuelven_exactamente_el_modelo_visual_anterior(self):
        """REQ-EDT-01: deshacer deja un modelo visual idéntico al de antes de la operación, y rehacer al de después."""
        from PySide6.QtCore import QPointF
        from escritorio.diagrama import posiciones
        e = self.e
        sid = e.ed.model["steps"][3]["id"]
        antes = self.mv()
        o = QPointF(*posiciones(e.M)[sid])
        e.prensar(o)
        e.mover(o + QPointF(120, 0))
        e.soltar(o + QPointF(120, 0))
        despues = self.mv()
        self.assertFalse(diferencia(antes, despues).vacio)
        e.deshacer()
        self.assertTrue(diferencia(antes, self.mv()).vacio)
        e.rehacer()
        self.assertTrue(diferencia(despues, self.mv()).vacio)

    def test_SESC17_cambiar_un_texto_y_la_seleccion(self):
        """REQ-EDT-01: cambiar una receptividad toca su transición y poco más; seleccionar solo cambia realces y marcas."""
        e = self.e
        tid = e.ed.model["transitions"][2]["id"]
        antes = self.mv()
        e.poner_condicion(tid, "no Paro", crear=True)
        c = self.cierra(antes, self.mv())
        self.assertIn(("transicion", tid), c.cambiadas)
        self.assertLessEqual(len(c.cambiadas) + len(c.altas) + len(c.bajas), 8)
        sid = e.ed.model["steps"][0]["id"]
        plano = self.mv()
        e.seleccionar([sid])
        c = self.cierra(plano, self.mv(e.seleccion_dibujo()))
        self.assertTrue(c.altas and all(k[0] == "realce" for k in c.altas), c.altas.keys())
        self.assertEqual((c.bajas, c.reordenadas), ((), ()))

    def test_SESC18_equidistanciar_y_una_secuencia_al_azar_cumplen_la_propiedad(self):
        """REQ-EDT-01: tras Equidistanciar y tras 40 operaciones al azar, `aplicar(diferencia(a, b), a)` es siempre `b`."""
        from tools import choque_escena as c
        e = self.e
        antes = self.mv()
        e.seleccionar([next(s["id"] for s in e.ed.model["steps"] if s["label"] == "100")])
        e.equidistanciar([e.sel[0]])
        self.cierra(antes, self.mv())
        previo = self.mv()
        for reg in c.generar(7, 40):
            try:
                c.aplicar(self.w, reg)
            except Exception as exc:  # noqa: BLE001
                if not c._aviso_de_interfaz(exc):
                    raise
            if self.w.modo != "editar":
                continue
            nuevo = self.mv(self.w.edicion.seleccion_dibujo())
            self.cierra(previo, nuevo)
            previo = nuevo
