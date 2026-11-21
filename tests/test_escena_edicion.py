"""SESC50..SESC58: validar una vez por cambio, arrastre sin rehacer la `Vista` y parpadeo que solo toca sus realces (V2-E3, paso 7)."""
from importlib.util import find_spec
from unittest import TestCase, mock, skipUnless

QT = bool(find_spec("PySide6"))


@skipUnless(QT, "requiere PySide6")
class EdicionIncremental(TestCase):
    def setUp(self):
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        self.contexto = ventana()
        self.w = self.contexto.__enter__()
        self.addCleanup(self.contexto.__exit__, None, None, None)
        reiniciar(self.w, GEMMA)
        self.e, self.d = self.w.edicion, self.w.diagrama
        self.sc = self.d.scene()

    def punto(self, ident, dx=0):
        from PySide6.QtCore import QPointF
        from escritorio.diagrama import posiciones
        x, y = posiciones(self.e.M)[ident]
        return QPointF(x + dx, y)

    def etapa(self, etiqueta="100"):
        return next(s["id"] for s in self.e.ed.model["steps"] if s["label"] == etiqueta)

    # --- E-1: validar una vez por cambio
    def test_SESC50_los_diagnosticos_no_vuelven_a_validar_el_mismo_modelo(self):
        """REQ-EDT-09: pedir los diagnósticos varias veces sobre los mismos documentos valida una sola vez; tras un cambio, otra."""
        from grafcet.editor import Editor
        e = self.e
        with mock.patch.object(Editor, "validate", autospec=True, side_effect=Editor.validate) as validar:
            a = e.diagnosticos()
            b = e.diagnosticos()
            self.assertEqual(a, b)
            self.assertLessEqual(validar.call_count, 1)
            antes = validar.call_count
            e.ed.add_step("g", "99", at=(1500, 3000))  # un cambio de verdad en el modelo
            e.cambia()
            e.diagnosticos()
            self.assertEqual(validar.call_count, antes + 1)

    def test_SESC51_deshacer_y_rehacer_usan_la_validacion_recordada_y_dan_lo_mismo(self):
        """REQ-EDT-09: deshacer y rehacer vuelven a documentos ya validados: no se valida otra vez y los diagnósticos son idénticos a
        los de una validación nueva."""
        from grafcet.editor import Editor
        e = self.e
        inicial = e.diagnosticos()
        e.ed.add_step("g", "99", at=(1500, 3000))
        e.cambia()
        cambiado = e.diagnosticos()
        with mock.patch.object(Editor, "validate", autospec=True, side_effect=Editor.validate) as validar:
            e.deshacer()
            self.assertEqual(e.diagnosticos(), inicial)
            e.rehacer()
            self.assertEqual(e.diagnosticos(), cambiado)
            self.assertEqual(validar.call_count, 0)
        e._memo_validacion = []
        self.assertEqual(e.diagnosticos(), cambiado)

    # --- E-2: el arrastre no rehace la Vista
    def test_SESC52_un_fotograma_del_arrastre_no_rehace_la_vista_y_da_el_mismo_modelo(self):
        """REQ-EDT-01: pulsar y mover una etapa no construye ninguna `Vista`; soltar construye una; y el `M` de cada fotograma es el
        que daría una reconstrucción completa."""
        from PySide6.QtCore import QPointF
        import grafcet.view as V
        from tools import choque_escena as c
        e = self.e
        sid = self.etapa()
        o = self.punto(sid)
        e.seleccionar([])
        e.prensar(o)
        for dx in (-40, -80, -120, -60):
            e.mover(o + QPointF(dx, 0))
            c.comprobar_modelo(self.w, f"fotograma {dx}")  # (reconstruye aparte a propósito: es el oráculo)
        original = V.Vista.__init__
        llamadas = []

        def contar(self, *a, **k):
            llamadas.append(1)
            return original(self, *a, **k)
        with mock.patch.object(V.Vista, "__init__", contar):
            for dx in (-30, -90):
                e.mover(o + QPointF(dx, 0))
            self.assertEqual(len(llamadas), 0, "los fotogramas no rehacen la Vista")
            e.soltar(o + QPointF(-90, 0))
            self.assertEqual(len(llamadas), 1, "soltar rehace la Vista una sola vez")
        c.comprobar(self.w, momento="tras soltar")

    def test_SESC53_los_arrastres_de_otro_tipo_rehacen_la_vista(self):
        """REQ-EDT-01: un arrastre que no es de posiciones (aquí, el tramo de un enlace) sigue rehaciendo la `Vista` en cada fotograma
        y el modelo del fotograma es el completo."""
        from PySide6.QtCore import QPointF
        import grafcet.view as V
        from tools import choque_escena as c
        e = self.e
        enlace = next(r for r in e.M["enlaces"] if r["handles"])
        h = enlace["handles"][0]
        o = QPointF(*h["pos"])
        original = V.Vista.__init__
        llamadas = []

        def contar(self, *a, **k):
            llamadas.append(1)
            return original(self, *a, **k)
        e.seleccionar([])
        e.prensar(o)
        if not e.arrastre or e.arrastre.get("tipo") not in ("tramo", "flecha"):
            self.skipTest("no se pudo agarrar el tramo de un enlace")
        with mock.patch.object(V.Vista, "__init__", contar):
            e.mover(o + QPointF(0, 25))
            e.mover(o + QPointF(0, 50))
        self.assertGreaterEqual(len(llamadas), 1)
        e.soltar(o + QPointF(0, 50))
        c.comprobar(self.w, momento="tras el tramo")

    def test_SESC54_soltar_una_etapa_reconstruye_y_refresca_una_sola_vez(self):
        """REQ-EDT-01: un arrastre entero hace una `Vista` y un refresco de la ventana al soltar (y uno al pulsar, por la
        selección), no dos."""
        from PySide6.QtCore import QPointF
        from escritorio.ventana import Ventana
        e = self.e
        sid = self.etapa()
        o = self.punto(sid)
        e.seleccionar([])
        e.prensar(o)
        e.mover(o + QPointF(-80, 0))
        with mock.patch.object(Ventana, "refrescar_edicion", autospec=True, side_effect=Ventana.refrescar_edicion) as refrescar, \
                mock.patch.object(type(e), "reconstruir", autospec=True, side_effect=type(e).reconstruir) as reconstruir:
            e.soltar(o + QPointF(-80, 0))
            self.assertEqual((reconstruir.call_count, refrescar.call_count), (1, 1))

    # --- H2: el parpadeo solo toca sus realces
    def test_SESC55_un_paso_del_parpadeo_solo_cambia_realces_y_marcas(self):
        """REQ-EDT-09: cada paso del parpadeo aplica a la escena solo objetos de realce o marcas de una acción, nunca etapas,
        transiciones ni enlaces."""
        from escritorio.escena import escena as E
        e = self.e
        sid, tid = self.etapa(), e.ed.model["transitions"][0]["id"]
        aplicados = []
        original = E.diferencia

        def espiar(a, b):
            c = original(a, b)
            aplicados.append(c)
            return c
        with mock.patch.object(E, "diferencia", espiar):
            e.parpadeo.iniciar([sid, tid])
            for _ in range(5):
                e.parpadeo.paso()
            e.parpadeo.parar()
        no_vacios = [c for c in aplicados if not c.vacio]
        self.assertTrue(no_vacios, "el parpadeo debe cambiar algo")
        for c in no_vacios:
            tocados = c.afectados
            self.assertTrue(all(k[0] in ("realce", "accion") for k in tocados), sorted(tocados)[:4])

    def test_SESC56_el_parpadeo_no_retira_las_marcas_provisionales_de_un_gesto(self):
        """REQ-EDT-09: el lazo, o las cajas rojas, siguen en la escena tras un paso del parpadeo, y un redibujado normal sí las retira."""
        from PySide6.QtCore import QPointF
        from tools import choque_escena as c
        d, e = self.d, self.e
        d.lazo(QPointF(0, 0), QPointF(50, 50))
        d.marcar_prohibido([d.scene().sceneRect().adjusted(0, 0, -10, -10)])
        provisionales = [d.cuadro, *d.prohibidos]
        e.parpadeo.iniciar([self.etapa()])
        e.parpadeo.paso()
        e.parpadeo.paso()
        self.assertTrue(all(p.scene() is self.sc for p in provisionales))
        self.assertIsNotNone(d.cuadro)
        e.parpadeo.parar()
        self.assertTrue(all(p.scene() is self.sc for p in provisionales))
        self.w._redibujar_edicion()
        self.assertTrue(all(p.scene() is None for p in provisionales))
        c.comprobar(self.w, momento="tras el redibujado normal")

    def test_SESC57_el_parpadeo_deja_la_escena_como_el_dibujo_directo(self):
        """REQ-EDT-09: tras cada paso del parpadeo (con y sin filtro de parcial) la escena coincide con el dibujo directo."""
        from tools import choque_escena as c
        e = self.e
        e.parpadeo.iniciar([self.etapa(), e.ed.model["actions"][0]["id"]])
        for _ in range(4):
            e.parpadeo.paso()
            c.comprobar(self.w, momento="parpadeo")
        nav = self.w.navegacion
        nav.parcial.setCurrentIndex(2)
        e.parpadeo.iniciar([self.etapa()])
        for _ in range(3):
            e.parpadeo.paso()
            c.comprobar(self.w, momento="parpadeo con filtro")
        nav.parcial.setCurrentIndex(0)
        e.parpadeo.parar()
        c.comprobar(self.w, momento="al terminar")
