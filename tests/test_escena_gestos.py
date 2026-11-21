"""SESC70..SESC75: una construcción y un dibujo por evento, huella sin recalcular tras abrir y nada sin actualizar (V2-E3, paso 10)."""
from contextlib import ExitStack
from importlib.util import find_spec
from unittest import TestCase, mock, skipUnless

QT = bool(find_spec("PySide6"))


@skipUnless(QT, "requiere PySide6")
class PorGesto(TestCase):
    def setUp(self):
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        self.contexto = ventana()
        self.w = self.contexto.__enter__()
        self.addCleanup(self.contexto.__exit__, None, None, None)
        reiniciar(self.w, GEMMA)
        self.e, self.d = self.w.edicion, self.w.diagrama

    def contar(self):
        """Parchea y devuelve los contadores: construcciones del modelo visual (lienzo y lupa), dibujos del lienzo, refrescos de la
        ventana, `Vista` rehechas y huellas calculadas."""
        import grafcet.model as modelo
        import grafcet.view as vista
        from escritorio import flotantes
        from escritorio.diagrama import VistaDiagrama
        from escritorio.escena import modelo_visual
        from escritorio.ventana import Ventana
        pila, c = ExitStack(), {}
        self.addCleanup(pila.close)
        c["construir"] = pila.enter_context(mock.patch.object(modelo_visual, "construir", wraps=modelo_visual.construir))
        c["construir_lupa"] = pila.enter_context(mock.patch.object(flotantes, "construir", c["construir"]))
        c["mostrar"] = pila.enter_context(mock.patch.object(VistaDiagrama, "mostrar", autospec=True, side_effect=VistaDiagrama.mostrar))
        c["refrescar"] = pila.enter_context(mock.patch.object(Ventana, "refrescar_edicion", autospec=True,
                                                              side_effect=Ventana.refrescar_edicion))
        original = vista.Vista.__init__
        c["vista"] = mock.MagicMock(side_effect=lambda self, *a, **k: original(self, *a, **k))
        pila.enter_context(mock.patch.object(vista.Vista, "__init__", autospec=True, side_effect=c["vista"]))
        c["huella"] = pila.enter_context(mock.patch.object(modelo, "compute_revision", wraps=modelo.compute_revision))
        return c

    def sid(self, etiqueta="100"):
        return next(s["id"] for s in self.e.ed.model["steps"] if s["label"] == etiqueta)

    def cuenta(self, c):
        return {k: v.call_count for k, v in c.items() if k != "construir_lupa"}

    def reinicia(self, c):
        for v in c.values():
            v.reset_mock()

    # --- la huella no se recalcula tras abrir
    def test_SESC70_tras_abrir_un_proyecto_ningun_gesto_recalcula_la_huella(self):
        """REQ-DAT-02: mover (que solo cambia la presentación), deshacer y rehacer, sobre un proyecto recién abierto, no calculan
        ninguna huella canónica: la del documento inicial ya está sellada."""
        from PySide6.QtCore import QPointF
        from escritorio.diagrama import posiciones
        c = self.contar()
        e, sid = self.e, self.sid()
        o = QPointF(*posiciones(e.M)[sid])
        e.seleccionar([])
        for _ in range(2):
            e.prensar(o)
            e.mover(o + QPointF(-80, 0))
            e.soltar(o + QPointF(-80, 0))
            e.deshacer()
            e.rehacer()
            e.deshacer()
        self.assertEqual(c["huella"].call_count, 0)

    # --- una construcción y un dibujo por evento
    def test_SESC71_cada_evento_de_un_arrastre_construye_y_dibuja_una_vez(self):
        """REQ-EDT-01: pulsar, cada fotograma y soltar hacen un `mostrar` y un `construir`; soltar rehace la `Vista` una vez y
        refresca la ventana una vez (pulsar, por la selección, otra)."""
        from PySide6.QtCore import QPointF
        from escritorio.diagrama import posiciones
        c = self.contar()
        e, sid = self.e, self.sid()
        o = QPointF(*posiciones(e.M)[sid])
        e.seleccionar([])
        self.reinicia(c)
        e.prensar(o)
        self.assertEqual((c["mostrar"].call_count, c["construir"].call_count, c["refrescar"].call_count), (1, 1, 1))
        for dx in (-80, -100, -120):
            self.reinicia(c)
            e.mover(o + QPointF(dx, 0))
            self.assertEqual((c["mostrar"].call_count, c["construir"].call_count, c["refrescar"].call_count, c["vista"].call_count),
                             (1, 1, 0, 0), dx)
        self.reinicia(c)
        e.soltar(o + QPointF(-120, 0))
        self.assertEqual((c["mostrar"].call_count, c["construir"].call_count, c["refrescar"].call_count, c["vista"].call_count),
                         (1, 1, 1, 1))

    def test_SESC72_deshacer_rehacer_receptividad_y_anadir_acciones_hacen_un_refresco_y_un_dibujo(self):
        """REQ-EDT-01: deshacer, rehacer, cambiar una receptividad y añadir una acción desde el borde de otra: un `mostrar`, un
        `construir`, un refresco de la ventana y una `Vista`."""
        from PySide6.QtCore import QPointF
        c = self.contar()
        e = self.e
        tid = e.ed.model["transitions"][0]["id"]
        accion = next(a for a in e.ed.model["actions"] if e.accion_en_id(a["id"]))
        cajas = [e.accion_en_id(a["id"]) for a in e.acciones(accion["stepRef"])]
        x, y, ancho, alto = max((k for k in cajas if k), key=lambda k: k["rect"][0] + k["rect"][2])["rect"]
        origen = QPointF(x + ancho, y + alto / 2)
        self.d.centrar_en(origen)
        e.seleccionar([])
        e.prensar(origen)
        e.mover(origen + QPointF(50, 0))
        pasos = (("receptividad", lambda: e.poner_condicion(tid, "no Paro", crear=True)),
                 ("deshacer", e.deshacer), ("rehacer", e.rehacer),
                 ("añadir acción", lambda: e.soltar(origen + QPointF(50, 0))))
        for nombre, f in pasos:
            self.reinicia(c)
            f()
            self.assertEqual((c["mostrar"].call_count, c["construir"].call_count, c["refrescar"].call_count,
                              c["vista"].call_count), (1, 1, 1, 1), nombre)

    def test_SESC73_equidistanciar_hace_un_refresco_y_dos_vistas_y_deja_todo_al_dia(self):
        """REQ-EDT-01: Equidistanciar refresca la ventana una vez (con su mensaje) y rehace la `Vista` dos veces (antes 4), y
        paneles, estado y marcas quedan como tras un refresco completo."""
        c = self.contar()
        e, w = self.e, self.w
        e.seleccionar([self.sid()])
        self.reinicia(c)
        movidos = e.equidistanciar([self.sid()])
        self.assertTrue(movidos)
        self.assertEqual((c["mostrar"].call_count, c["refrescar"].call_count, c["vista"].call_count), (1, 1, 2))
        self.assertIn("equidistanciadas", e.mensaje + " " + e.texto_estado()[0])

        def instantanea():
            return (w.l_sel.text(), w.l_resumen.text(), w.l_herr.text(), w.windowTitle(), w.lista_diag.count(),
                    w.a_deshacer.isEnabled(), w.a_rehacer.isEnabled(), w.a_borrar.isEnabled(), w._marcas_diagnostico)
        antes = instantanea()
        w.refrescar_edicion()
        self.assertEqual(antes, instantanea(), "tras un solo refresco todo estaba ya al día")
        self.assertTrue(w.a_deshacer.isEnabled())
        e.deshacer()
        self.assertFalse(e.mensaje, "deshacer limpia el aviso de la operación")

    def test_SESC74_con_propiedades_abiertas_la_lupa_y_los_paneles_siguen_al_cambio(self):
        """REQ-EDT-01: con Propiedades flotante abierta sobre una transición, cambiar su receptividad, deshacer y rehacer construyen
        el lienzo y la lupa una vez cada uno, recolocan dos veces como mucho (antes tres) y la lupa y el título siguen al cambio."""
        from escritorio.flotantes import GestorFlotantes
        from tools import choque_escena as ch
        from tools.entorno_v2_e0 import bombear
        e, w = self.e, self.w
        tid = e.ed.model["transitions"][2]["id"]
        w.editar_condicion(tid)
        bombear()
        self.assertTrue(w.flot.principal.isVisible())
        c = self.contar()
        for nombre, f in (("receptividad", lambda: e.poner_condicion(tid, "no Paro", crear=True)),
                          ("deshacer", e.deshacer), ("rehacer", e.rehacer)):
            self.reinicia(c)
            with mock.patch.object(GestorFlotantes, "_dimensionar", autospec=True,
                                   side_effect=GestorFlotantes._dimensionar) as dimensionar:
                f()
                bombear()
            self.assertEqual((c["mostrar"].call_count, c["refrescar"].call_count, c["vista"].call_count), (1, 1, 1), nombre)
            self.assertEqual(c["construir"].call_count, 2, f"{nombre}: el lienzo y la lupa, una vez cada uno")
            self.assertLessEqual(dimensionar.call_count, 2, nombre)
            ch.comprobar_lupa(w, nombre)
            ch.comprobar(w, momento=f"tras {nombre} con Propiedades abiertas")
            self.assertIs(w.flot.principal.lupa._modelo, e.M, f"{nombre}: la lupa dibuja el modelo de ahora")
            self.assertTrue(w.flot.principal.isVisible())

    def test_SESC75_varias_actualizaciones_en_la_misma_vuelta_recolocan_una_sola_vez_despues(self):
        """REQ-EDT-01: la recolocación diferida de Propiedades no se encadena: tres refrescos seguidos dejan una sola pendiente."""
        from escritorio.flotantes import GestorFlotantes
        from tools.entorno_v2_e0 import bombear
        w, e = self.w, self.e
        w.editar_condicion(e.ed.model["transitions"][2]["id"])
        bombear()
        with mock.patch.object(GestorFlotantes, "colocar", autospec=True, side_effect=GestorFlotantes.colocar) as colocar:
            for _ in range(3):
                w.flot.actualizar()
            directas = colocar.call_count
            self.assertEqual(directas, 3)
            bombear()
            self.assertEqual(colocar.call_count, directas + 1, "una sola recolocación diferida")
