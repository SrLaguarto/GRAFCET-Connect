"""Correcciones tras probar el editor en clase: etapas sin subíndice, arrastrar un enlace lo mueve, arrastrar desde una etapa crea
transición y etapa, acciones sueltas, valores de las variables en las transiciones y rueda."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from grafcet.builder import M
from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Editor, new_grafcet_document
from grafcet.routing import SX, enlaces
from grafcet.view import norm
from helpers_grafnet import fixture_grafnet
from test_dibujo_vista import vista, dibujo, texto, textos
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsPathItem, QGraphicsScene
    from escritorio import diagrama as dg
    from escritorio.diagrama import SX, anclas
    from grafcet.routing import enlaces


class VariableDeEtapaSinSubindice(unittest.TestCase):
    def test_SAUL01_la_variable_de_etapa_se_escribe_x3_sin_subindice(self):
        """REQ-EDT-02: X3 se dibuja y se previsualiza como texto plano, sin subíndice."""
        m = M().var("p").step("E3", True).step("B")
        m.trans("t", ["E3"], ["B"], "p AND active(E3)")
        v = vista(m, {"E3": (100, 60), "t": (100, 140), "B": (100, 220)})
        cond = v.model["transitions"][0]["cond"]
        self.assertIn("X3", [s["t"] for s in cond])
        self.assertFalse(any(s.get("s") for s in cond), "ningún segmento lleva subíndice")
        self.assertNotIn("<sub>", dg._html(cond))
        sig = norm({"operator": "active", "reference": "E3"}, True, {"E3": "E3"})
        self.assertEqual(sig, [{"t": "X3"}])
        if QT:
            sc, _ = dibujo(v)
            self.assertNotIn("vertical-align:sub", texto(sc, "p·X3").toHtml())


@unittest.skipUnless(QT, "PySide6 no está instalado")
class Gestos(BaseQt):
    def dos_etapas(self):
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        b = e.ed.add_step("g", "2", at=(160, 300))
        t, _ = e.ed.add_transition("g", "", [a], [b], at=(100, 180), label="t1")
        e.cambia()
        return w, e, a, b, t

    def test_SAUL02_arrastrar_un_enlace_mueve_su_tramo_y_no_crea_nada(self):
        """REQ-EDT-02: agarrar el cuerpo de un enlace y arrastrar mueve el tramo (sin seleccionarlo antes); no abre ramas."""
        w, e, a, b, t = self.dos_etapas()
        antes = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]))
        ruta = next(r for r in enlaces(e.M) if r["handles"])
        h = ruta["handles"][0]
        i = h["segment"]
        p0 = QPointF((ruta["pts"][i][0] + ruta["pts"][i + 1][0]) / 2, (ruta["pts"][i][1] + ruta["pts"][i + 1][1]) / 2)
        e.sel = []
        e.prensar(p0)
        self.assertEqual(e.arrastre["tipo"], "tramo")
        self.assertIsNone(e.enlace)
        n = len(e.ed.undo_stack)
        e.mover(p0 + QPointF(0, 20))
        e.mover(p0 + QPointF(0, 40))
        e.soltar(p0 + QPointF(0, 40))
        self.assertEqual((len(e.ed.model["steps"]), len(e.ed.model["transitions"])), antes)
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación de deshacer")
        self.assertIn(ruta["id"], e.ed.link_styles())
        e.deshacer()
        self.assertNotIn(ruta["id"], e.ed.link_styles())

    def test_SAUL03_arrastrar_un_enlace_recto_solo_lo_selecciona(self):
        """REQ-EDT-02: un enlace sin tramos que mover (recto) se selecciona, pero arrastrarlo no crea ni mueve nada."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        b = e.ed.add_step("g", "2", at=(100, 300))
        e.ed.add_transition("g", "", [a], [b], at=(100, 180), label="t1")
        e.cambia()
        ruta = enlaces(e.M)[1]
        self.assertFalse(ruta["handles"])
        p = QPointF(ruta["pts"][0][0], (ruta["pts"][0][1] + ruta["pts"][-1][1]) / 2)
        antes = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.undo_stack))
        e.prensar(p)
        e.mover(p + QPointF(200, 60))
        e.soltar(p + QPointF(200, 60))
        self.assertEqual((len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.undo_stack)), antes)
        self.assertEqual(e.sel, [ruta["id"]])

    def test_SAUL04_arrastrar_de_una_etapa_a_un_hueco_crea_solo_una_transicion(self):
        """REQ-EDT-02: de una etapa a un hueco se crea solo una transición enlazada, y una sola operación de deshacer."""
        w, e, a, b, t = self.dos_etapas()
        n_s, n_t, n_u = len(e.M["steps"]), len(e.M["transitions"]), len(e.ed.undo_stack)
        pa = next(x for x in anclas(e.M, a) if x["lado"] == "abajo")["pos"]
        q = QPointF(560, 400)
        e.prensar(pa)
        e.mover(q)
        e.soltar(q)
        self.assertEqual((len(e.M["steps"]) - n_s, len(e.M["transitions"]) - n_t), (0, 1))
        tr = next(x for x in e.M["transitions"] if x["id"] == e.sel[0])
        self.assertEqual(tr["pre"], [a], "la transición sale de la etapa de origen")
        self.assertEqual(len(e.ed.undo_stack), n_u + 1)
        e.deshacer()
        self.assertEqual((len(e.M["steps"]), len(e.M["transitions"])), (n_s, n_t))

    def test_SAUL05_arrastrar_de_una_etapa_a_otra_etapa_las_une_con_una_transicion(self):
        """REQ-EDT-02: soltar sobre otra etapa crea una transición entre las dos (nunca un enlace etapa-etapa en borrador)."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        b = e.ed.add_step("g", "2", at=(100, 360))
        e.cambia()
        n_t, n_u = len(e.M["transitions"]), len(e.ed.undo_stack)
        pa = next(x for x in anclas(e.M, a) if x["lado"] == "abajo")["pos"]
        pb = next(x for x in anclas(e.M, b) if x["lado"] == "arriba")["pos"]
        e.prensar(pa)
        e.mover(pb)
        e.soltar(pb)
        self.assertEqual(len(e.M["transitions"]), n_t + 1)
        tr = e.M["transitions"][-1]
        self.assertEqual((tr["pre"], tr["post"]), ([a], [b]))
        self.assertFalse(e.M["drafts"], "no queda un enlace en borrador entre etapas")
        self.assertEqual(len(e.ed.undo_stack), n_u + 1)
        e.deshacer()
        self.assertEqual(len(e.M["transitions"]), n_t)

    def test_SAUL06_soltar_sobre_una_etapa_anterior_es_un_retorno_con_transicion(self):
        """REQ-EDT-02: si la otra etapa queda encima, la transición nueva hace el retorno (salto o repetición de secuencia)."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        b = e.ed.add_step("g", "2", at=(100, 360))
        e.cambia()
        pb = next(x for x in anclas(e.M, b) if x["lado"] == "abajo")["pos"]
        pa = next(x for x in anclas(e.M, a) if x["lado"] == "arriba")["pos"]
        e.prensar(pb)
        e.mover(pa)
        e.soltar(pa)
        tr = e.M["transitions"][-1]
        self.assertEqual((tr["pre"], tr["post"]), ([b], [a]))
        self.assertTrue(any(r["arriba"] for r in enlaces(e.M) if r["tid"] == tr["id"]), "el enlace de retorno sube")

    def test_SAUL07_arrastrar_de_una_transicion_a_un_hueco_sigue_creando_una_etapa(self):
        """REQ-EDT-02: de una transición a un hueco se crea solo la etapa que sigue."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        t, _ = e.ed.add_transition("g", "", [a], [], at=(100, 180), label="t1")
        e.cambia()
        n_s, n_t = len(e.M["steps"]), len(e.M["transitions"])
        pt = next(x for x in anclas(e.M, t) if x["lado"] == "abajo")["pos"]
        q = QPointF(pt.x(), pt.y() + 120)
        e.prensar(pt)
        e.mover(q)
        e.soltar(q)
        self.assertEqual((len(e.M["steps"]) - n_s, len(e.M["transitions"]) - n_t), (1, 0))
        self.assertEqual(next(x for x in e.M["transitions"] if x["id"] == t)["post"], [e.sel[0]])


@unittest.skipUnless(QT, "PySide6 no está instalado")
class AccionesSueltas(BaseQt):
    def test_SAUL08_play_no_une_una_accion_suelta_bajo_el_extremo_de_una_transicion(self):
        """REQ-EDT-02, REQ-EDT-09: una acción suelta con su punto de unión bajo el extremo de una transición sumidero sigue
        suelta: ni Play ni pulsar ahí la unen a nada (las acciones solo se unen a etapas, con un enlace explícito)."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        t, _ = e.ed.add_transition("g", "", [a], [], at=(100, 180), label="t1")
        e.cambia()
        punta = QPointF(100 + SX, 180 + dg.TALLO_T)
        did = e.poner_accion_suelta(punta)
        self.assertFalse(next(d for d in e.ed.draft_actions() if d["id"] == did).get("etapa"))
        # pulsar y soltar justo en el punto compartido: no se une nada
        e.prensar(punta)
        e.soltar(punta)
        self.assertEqual(e.ed.model["actions"], [])
        self.assertFalse(next(d for d in e.ed.draft_actions() if d["id"] == did).get("etapa"))
        # y la transición no es el destino de la acción: unir es rechazado
        origen = next(x for x in anclas(e.M, did) if x["lado"] == "izq")
        destino = next(x for x in anclas(e.M, t) if x["lado"] == "abajo")
        e.unir(origen, destino)
        self.assertFalse(next(d for d in e.ed.draft_actions() if d["id"] == did).get("etapa"))
        self.assertEqual(e.ed.model["actions"], [])
        with mock.patch("escritorio.ventana.QMessageBox.warning"):
            w.a_ejecutar.setChecked(True)
        self.assertEqual(w.modo, "editar", "una acción suelta bloquea Play")
        self.assertFalse(next(d for d in e.ed.draft_actions() if d["id"] == did).get("etapa"))
        self.assertEqual(e.ed.model["actions"], [])

    def test_SAUL09_una_acciones_suelta_de_contador_con_variable_nueva_no_da_error(self):
        """REQ-EDT-09: «C := C + 1» en una acción suelta cuya variable se declara en la misma operación no da «no interpretado»,
        como una vez unida a su etapa; un texto mal escrito o con otra variable inexistente se sigue rechazando."""
        w, e = self.vacio()
        did = e.poner_accion_suelta(QPointF(400, 200), "activacion")
        d = {"tipo": "activacion", "variable": "C", "valor": "C + 1", "evento": ""}
        self.assertIsNone(e.cambiar_accion(did, d, ("internal", {"kind": "int"})))
        self.assertTrue(any(v["name"] == "C" for v in e.ed.model["variables"]))
        # con la variable ya declarada también
        otra = e.poner_accion_suelta(QPointF(400, 400), "activacion")
        self.assertIsNone(e.cambiar_accion(otra, {**d, "variable": "C"}))
        # lo genuinamente inválido sigue dando error
        mala = e.poner_accion_suelta(QPointF(400, 600), "activacion")
        self.assertIn("El valor no es válido", e.cambiar_accion(mala, {**d, "valor": "C +"}) or "")
        self.assertIn("El valor no es válido",
                      e.cambiar_accion(mala, {**d, "valor": "C + Z"}, ("internal", {"kind": "int"})) or "",
                      "otra variable que no existe no vale")
        # unida a una etapa, lo mismo
        s = e.poner_etapa(QPointF(100, 100), inicial=True)
        nueva = e.poner_accion_suelta(QPointF(300, 800), "activacion")
        e.unir_accion(nueva, s)
        self.assertIsNone(e.cambiar_accion(nueva, {**d, "variable": "K", "valor": "K + 1"}, ("internal", {"kind": "int"}))
                          if e._es_borrador(nueva) else None)


class ValoresEnTransiciones(unittest.TestCase):
    def modelo(self):
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B")
        m.stored("A", "n", "activation", "n + 1")
        m.trans("t", ["A"], ["B"], "n >= 3")
        m.trans("u", ["B"], ["A"], "p")
        return m, {"A": (220, 60), "t": (220, 140), "B": (220, 220), "u": (220, 300)}

    @unittest.skipUnless(QT, "requiere PySide6")
    def test_SAUL16_al_simular_se_ve_el_valor_de_la_variable_numerica_de_la_receptividad(self):
        """REQ-SIM-03: junto a «n ≥ 3» se dibuja el valor actual de n, en el estilo de las acciones, solo en simulación y sin
        pisar el texto de la condición."""
        m, lay = self.modelo()
        v = vista(m, lay)
        t = next(x for x in v.model["transitions"] if x["label"] == "t")
        self.assertEqual(len(t["numericVars"]), 1)
        self.assertNotIn("numericVars", next(x for x in v.model["transitions"] if x["label"] == "u"))
        S = v.state()
        self.assertIn(t["numericVars"][0], S["variableReadouts"])
        sc = QGraphicsScene()
        dg.dibujar(sc, v.model, S)
        cond = next(i for i in textos(sc) if i.toPlainText().startswith("[n"))
        lecturas = [i for i in textos(sc) if i.toPlainText() == S["variableReadouts"][t["numericVars"][0]]
                    and i.font().pixelSize() == 10 and i.defaultTextColor().name() == dg.COL["readout"]]
        cerca = [i for i in lecturas if abs(i.pos().x() - cond.pos().x()) < cond.boundingRect().width()
                 and i.pos().y() < cond.pos().y()]
        self.assertTrue(cerca, "el valor se dibuja sobre el texto de la receptividad")
        self.assertLessEqual(cerca[0].pos().y() + cerca[0].boundingRect().height(), cond.pos().y() + 1, "sin pisar la condición")
        # en edición (sin lecturas) no se dibuja
        sc2 = QGraphicsScene()
        dg.dibujar(sc2, v.model, {})
        self.assertFalse([i for i in textos(sc2) if i.font().pixelSize() == 10 and i.defaultTextColor().name() == dg.COL["readout"]])


@unittest.skipUnless(QT, "PySide6 no está instalado")
class RuedaYTactil(BaseQt):
    def vista_manual(self):
        w, e = self.vacio()
        for i in range(8):
            e.ed.add_step("g", str(i + 1), i == 0, at=(100 + 200 * i, 80 + 80 * i))
        e.cambia()
        w.resize(900, 650)
        w.show()
        QApplication.processEvents()
        d = w.diagrama
        d.zoom(1.0)  # zoom manual: aparecen las barras
        QApplication.processEvents()
        return w, d

    def rueda(self, d, angulo=(0, 0), pixeles=(0, 0), mod=Qt.KeyboardModifier.NoModifier, pos=(300, 300),
              fase=Qt.ScrollPhase.NoScrollPhase):
        p = QPointF(*pos)
        ev = QWheelEvent(p, d.viewport().mapToGlobal(p), QPoint(*pixeles), QPoint(*angulo), Qt.MouseButton.NoButton, mod,
                         fase, False)
        QApplication.sendEvent(d.viewport(), ev)
        QApplication.processEvents()

    def test_SAUL17b_las_tres_combinaciones_de_rueda(self):
        """REQ-EDT-02, REQ-SIM-03: rueda sola = desplaza en vertical; Ctrl+rueda = zoom; Mayús+rueda = horizontal."""
        w, d = self.vista_manual()
        h, v = d.horizontalScrollBar(), d.verticalScrollBar()
        v.setValue(v.maximum() // 2)
        h.setValue(h.maximum() // 2)
        v0, h0, k0 = v.value(), h.value(), d.escala()
        self.rueda(d, (0, -120))
        self.assertEqual((h.value(), d.escala()), (h0, k0))
        self.assertEqual(v.value(), v0 + 60)
        self.rueda(d, (0, 120), mod=Qt.KeyboardModifier.ControlModifier)
        self.assertGreater(d.escala(), k0)
        v.setValue(v.maximum() // 2)
        h.setValue(h.maximum() // 2)
        v1, h1, k1 = v.value(), h.value(), d.escala()
        self.rueda(d, (0, -120), mod=Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual((v.value(), d.escala()), (v1, k1))
        self.assertEqual(h.value(), h1 + 60)

    def test_SAUL17_rueda_y_ctrl_rueda_hacen_zoom_mayus_y_dos_dedos_desplazan(self):
        """REQ-EDT-02, REQ-SIM-03: solo Ctrl+rueda hace zoom anclado al puntero; la rueda sola desplaza en vertical y Mayús+rueda
        en horizontal; dos dedos de un panel táctil (pixelDelta o fase de desplazamiento) desplazan en los dos ejes; el pellizco
        nativo también hace zoom."""
        w, d = self.vista_manual()
        k = d.escala()
        self.rueda(d, (0, 120), mod=Qt.KeyboardModifier.ControlModifier)
        self.assertGreater(d.escala(), k)
        self.rueda(d, (0, -120), mod=Qt.KeyboardModifier.ControlModifier)
        self.assertAlmostEqual(d.escala(), k, places=6)
        h, v = d.horizontalScrollBar(), d.verticalScrollBar()
        v.setValue(v.maximum() // 2)
        h.setValue(h.maximum() // 2)
        v0, h0, k0 = v.value(), h.value(), d.escala()
        self.rueda(d, (0, 120), mod=Qt.KeyboardModifier.ControlModifier)
        self.assertAlmostEqual(d.escala(), k0 * 1.15, places=6)
        self.rueda(d, (0, -120), mod=Qt.KeyboardModifier.ControlModifier)
        self.assertAlmostEqual(d.escala(), k0, places=6)
        self.assertEqual((v.value(), h.value()), (v0, h0), "el zoom anclado no mueve las barras con el puntero en el centro")
        self.rueda(d, (0, 120))  # la rueda sola desplaza en vertical: hacia arriba, el contenido baja (la barra sube)
        self.assertEqual((d.escala(), h.value()), (k0, h0))
        self.assertLess(v.value(), v0)
        v.setValue(v0)
        self.rueda(d, (0, -120), mod=Qt.KeyboardModifier.ShiftModifier)  # Mayús: horizontal
        self.assertGreater(h.value(), h0)
        self.assertEqual((v.value(), d.escala()), (v0, k0))
        v2, h2 = v.value(), h.value()
        self.rueda(d, (0, 0), pixeles=(-30, -40))  # dos dedos: contenido a la izquierda y arriba
        self.assertEqual((h.value(), v.value(), d.escala()), (h2 + 30, v2 + 40, k0))
        self.rueda(d, (0, 120), fase=Qt.ScrollPhase.ScrollUpdate)  # con fase de desplazamiento y sin pixelDelta: también desplaza
        self.assertLess(v.value(), v2 + 40)
        self.assertEqual(d.escala(), k0)
        # pellizco nativo
        try:
            from PySide6.QtGui import QNativeGestureEvent, QPointingDevice
            ev = QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture, QPointingDevice.primaryPointingDevice(), 2,
                                     QPointF(300, 300), QPointF(300, 300), QPointF(300, 300), 0.25, QPointF(0, 0))
        except TypeError:
            self.skipTest("este PySide6 no construye QNativeGestureEvent")
        k = d.escala()
        QApplication.sendEvent(d.viewport(), ev)
        self.assertAlmostEqual(d.escala(), k * 1.25, places=6)


def _vista_giro(o):
    """A -t→ B con la transición girada hacia `o`, con las etapas colocadas a un lado como hace falta."""
    disp = {"abajo": {"A": (100, 60), "t": (100, 140), "B": (100, 220)},
            "derecha": {"A": (100, 60), "t": (160, 140), "B": (220, 220)},
            "izquierda": {"A": (300, 60), "t": (240, 140), "B": (180, 220)},
            "arriba": {"A": (100, 300), "t": (100, 200), "B": (100, 80)}}[o]
    m = M().var("p").step("A", True).step("B")
    m.trans("t", ["A"], ["B"], "p")
    return vista(m, disp, orientations={"t": o} if o != "abajo" else None)


def _signo(a, b):
    return ((b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1]))


class GiroDeTransicionesNucleo(unittest.TestCase):
    """El giro de la evolución a través de una transición (P-IMP-107): sin Qt."""

    def editor(self):
        from grafcet.editor import Editor, new_grafcet_document
        ed = Editor(new_grafcet_document("m"))
        a = ed.add_step("g", "1", True, at=(100, 60))
        b = ed.add_step("g", "2", at=(100, 220))
        t, _ = ed.add_transition("g", "", [a], [b], at=(100, 140), label="t1")
        return ed, a, b, t

    def test_SAUL10_el_giro_de_las_acciones_ya_no_existe(self):
        """REQ-EDT-02: se retiró el giro del bloque de acciones de una etapa (P-IMP-107 pasa a ser el de la transición)."""
        from grafcet.editor import Editor
        from grafcet.view import Vista
        self.assertFalse(hasattr(Editor, "ACTION_SIDES") or hasattr(Editor, "set_action_side") or hasattr(Editor, "action_sides"))
        self.assertNotIn("action_sides", Vista.__init__.__code__.co_varnames)
        ed, a, b, t = self.editor()
        ed.presentation["actionSides"] = {a: "abajo"}  # un archivo de la versión intermedia: se ignora
        v = vista(ed.model, None, presentation=ed.presentation)
        self.assertTrue(all("actionSide" not in s for s in v.model["steps"]))
        if QT:
            from escritorio.edicion import Edicion
            self.assertFalse(any(hasattr(dg, n) for n in ("LADOS_ACCIONES", "lado_acciones", "punto_acciones", "_geometria_der")))
            self.assertFalse(any(hasattr(Edicion, n) for n in ("girar_acciones", "lado_acciones", "_menu_giro_acciones")))
            self.assertNotIn("lado", dg._geometria_acciones.__code__.co_varnames)

    def test_SAUL11_cada_orientacion_gira_el_trazo_y_los_enlaces_y_pone_flecha(self):
        """REQ-EDT-02, REQ-MOD-06: el enlace llega a la transición y sale de ella en el sentido de su evolución, en tramos
        ortogonales; una evolución que no va hacia abajo lleva flecha en el enlace que sale; «abajo» no cambia."""
        sentido = {"abajo": (0, 1), "derecha": (1, 0), "arriba": (0, -1), "izquierda": (-1, 0)}
        for o, d in sentido.items():
            v = _vista_giro(o)
            t = v.model["transitions"][0]
            self.assertEqual(t.get("orient"), None if o == "abajo" else o, o)
            rutas = {r["rol"]: r for r in enlaces(v.model)}
            T = (t["x"] + SX, t["y"])
            for r in rutas.values():
                self.assertTrue(all(a[0] == b[0] or a[1] == b[1] for a, b in zip(r["pts"], r["pts"][1:])), (o, r["pts"]))
            self.assertEqual((rutas["pre"]["pts"][-1], rutas["post"]["pts"][0]), (T, T))
            self.assertEqual(_signo(*rutas["pre"]["pts"][-2:]), d, f"{o}: llega en el sentido de la evolución")
            self.assertEqual(_signo(*rutas["post"]["pts"][:2]), d, f"{o}: sale en el sentido de la evolución")
            self.assertEqual(rutas["pre"]["pts"][0][0], v.model["steps"][0]["x"] + SX, "sale de la etapa por abajo")
            self.assertEqual(rutas["post"]["pts"][-1][0], v.model["steps"][1]["x"] + SX)
            if o == "abajo":
                self.assertEqual([r["arrows"] for r in rutas.values()], [[], []])
                continue
            (f,) = rutas["post"]["arrows"]
            punta, (px, py) = f["pts"][0], f["pos"]
            self.assertEqual(f["segment"], 0, "junto a la transición")
            self.assertEqual(((punta[0] - px) / 6, (punta[1] - py) / 6), d, f"{o}: la flecha apunta a la evolución")
            if o != "arriba":  # con «arriba» el enlace de entrada sube y lleva su flecha de siempre
                self.assertEqual(rutas["pre"]["arrows"], [])
            for r in rutas.values():  # los tramos interiores se pueden mover a mano (P-IMP-116)
                self.assertTrue(all(h["orient"] for h in r["handles"]))
        # el enlace que da la vuelta (etapas en la misma vertical que la transición) también es ortogonal y llega bien
        m = M().var("p").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "p")
        for o, d in sentido.items():
            if o == "abajo":
                continue
            w = vista(m, {"A": (100, 60), "t": (100, 140), "B": (100, 220)}, orientations={"t": o})
            rutas = {r["rol"]: r for r in enlaces(w.model)}
            for r in rutas.values():
                self.assertTrue(all(a[0] == b[0] or a[1] == b[1] for a, b in zip(r["pts"], r["pts"][1:])), (o, r["pts"]))
            self.assertEqual(_signo(*rutas["pre"]["pts"][-2:]), d)
            self.assertEqual(_signo(*rutas["post"]["pts"][:2]), d)

    def test_SAUL12_formato_valor_desconocido_borrar_deshacer_y_pegar(self):
        """REQ-DAT-02, REQ-EDT-04: `presentation.transitionOrientations` solo guarda lo que no es «abajo»; un valor desconocido se
        lee como «abajo»; una sola operación de deshacer sin tocar el modelo; se poda al borrar y viaja al copiar y pegar."""
        ed, a, b, t = self.editor()
        self.assertNotIn("transitionOrientations", ed.presentation)
        rev = ed.revision
        n = len(ed.undo_stack)
        ed.set_transition_orientation(t, "derecha")
        self.assertEqual(ed.presentation["transitionOrientations"], {t: "derecha"})
        self.assertEqual((ed.revision, len(ed.undo_stack)), (rev, n + 1), "presentación: no cambia el modelo")
        ed.set_transition_orientation(t, "abajo")
        self.assertNotIn("transitionOrientations", ed.presentation, "«abajo» no se guarda")
        ed.undo()
        self.assertEqual(ed.presentation["transitionOrientations"], {t: "derecha"})
        with self.assertRaises(DiagnosticError):
            ed.set_transition_orientation(t, "diagonal")
        with self.assertRaises(DiagnosticError):
            ed.set_transition_orientation("no-existe", "arriba")
        v = vista(ed.model, None, presentation={"transitionOrientations": {t: "diagonal"}})
        self.assertNotIn("orient", v.model["transitions"][0], "desconocido: abajo")
        v = vista(ed.model, None, presentation={"transitionOrientations": {t: "izquierda"}})
        self.assertEqual(v.model["transitions"][0]["orient"], "izquierda")
        # copiar y pegar
        mp = ed.paste(ed.copy([a, t, b]), "g", at=(400, 60))
        self.assertEqual(ed.presentation["transitionOrientations"], {t: "derecha", mp[t]: "derecha"})
        ed.undo()
        self.assertEqual(ed.presentation["transitionOrientations"], {t: "derecha"})
        # borrar la transición poda su entrada (y deshacer la devuelve)
        ed.delete([t])
        self.assertNotIn("transitionOrientations", ed.presentation)
        ed.undo()
        self.assertEqual(ed.presentation["transitionOrientations"], {t: "derecha"})


@unittest.skipUnless(QT, "PySide6 no está instalado")
class GiroDeTransiciones(BaseQt):
    def con_transicion(self):
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 60))
        b = e.ed.add_step("g", "2", at=(100, 220))
        t, _ = e.ed.add_transition("g", "", [a], [b], at=(100, 140), label="t1")
        e.cambia()
        self.assertIsNone(e.poner_condicion(t, "p", crear=True))  # con receptividad: se puede simular
        return w, e, t

    def test_SAUL13_girar_a_derechas_y_a_izquierdas_recorre_las_cuatro_orientaciones_con_deshacer(self):
        """REQ-EDT-02: a derechas (como las agujas del reloj en pantalla) abajo → izquierda → arriba → derecha → abajo; a
        izquierdas, al revés; una operación de deshacer por giro; de vuelta a «abajo» no queda ninguna entrada."""
        w, e, t = self.con_transicion()
        self.assertEqual(e.orientacion_transicion(t), "abajo")
        for o in ("izquierda", "arriba", "derecha", "abajo"):
            n = len(e.ed.undo_stack)
            e.sel = [t]
            self.assertTrue(e.girar_transiciones(1))
            self.assertEqual(e.orientacion_transicion(t), o)
            self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertNotIn("transitionOrientations", e.ed.presentation)
        for o in ("derecha", "arriba", "izquierda", "abajo"):
            self.assertTrue(e.girar_transiciones(-1))
            self.assertEqual(e.orientacion_transicion(t), o)
        e.girar_transiciones(1)
        self.assertEqual(e.M["transitions"][0]["orient"], "izquierda")
        e.deshacer()
        self.assertEqual(e.orientacion_transicion(t), "abajo")
        self.assertNotIn("orient", e.M["transitions"][0])
        e.rehacer()
        self.assertEqual(e.M["transitions"][0]["orient"], "izquierda")
        e.sel = []
        self.assertFalse(e.girar_transiciones(1), "sin una transición seleccionada no hay nada que girar")

    def test_SAUL14_el_menu_del_boton_derecho_la_barra_de_menus_y_el_atajo_giran(self):
        """REQ-EDT-02: «Girar en sentido antihorario» y «Girar en sentido horario» en el menú de la transición, «Girar transición en
        sentido antihorario/horario» en Editar (desactivados al simular) y Ctrl+Mayús+←/→."""
        w, e, t = self.con_transicion()
        x, y = dg.posiciones(e.M)[t]
        opciones = dict(e.menu(QPointF(x, y)))
        self.assertIn("Girar en sentido antihorario", opciones)
        self.assertIn("Girar en sentido horario", opciones)
        self.assertEqual(e.sel, [t])
        opciones["Girar en sentido horario"]()
        self.assertEqual(e.orientacion_transicion(t), "izquierda")
        dict(e.menu(QPointF(*dg.posiciones(e.M)[t])))["Girar en sentido antihorario"]()
        self.assertEqual(e.orientacion_transicion(t), "abajo")
        self.assertEqual(w.a_girar_izq.text().replace("&", "").split("\t")[0], "Girar transición en sentido antihorario")
        self.assertEqual(w.a_girar_der.text().replace("&", "").split("\t")[0], "Girar transición en sentido horario")
        self.assertIn("Ctrl+Mayús+Izquierda", w.a_girar_izq.text())
        self.assertTrue(w.a_girar_izq.isEnabled() and w.a_girar_der.isEnabled())
        w.a_girar_der.trigger()
        self.assertEqual(e.orientacion_transicion(t), "izquierda")
        mod = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        from PySide6.QtGui import QKeyEvent
        for tecla, esperado in ((Qt.Key.Key_Right, "arriba"), (Qt.Key.Key_Left, "izquierda")):
            w.diagrama.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, tecla, mod))
            self.assertEqual(e.orientacion_transicion(t), esperado)
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertFalse(w.a_girar_izq.isEnabled() or w.a_girar_der.isEnabled())

    @staticmethod
    def flechas(sc):
        """Las puntas de flecha del dibujo: triángulos rellenos y sin trazo."""
        return [it for it in sc.items() if isinstance(it, QGraphicsPathItem) and it.pen().style() == Qt.PenStyle.NoPen
                and it.brush().style() == Qt.BrushStyle.SolidPattern and it.path().elementCount() <= 4]

    def test_SAUL15_el_trazo_es_vertical_con_el_texto_horizontal_sin_pisar_los_enlaces(self):
        """REQ-EDT-02: con evolución horizontal el trazo es vertical y la receptividad (encima) y la designación (debajo)
        quedan horizontales y centradas, fuera de los enlaces; con «arriba» el trazo sigue horizontal, con el texto a la
        derecha; la flecha se dibuja en el enlace que sale."""
        for o in ("derecha", "izquierda", "arriba"):
            v = _vista_giro(o)
            sc, _ = dibujo(v)
            t = v.model["transitions"][0]
            tx, ty = t["x"] + SX, t["y"]
            lineas = [(it.line(), it.pen().widthF()) for it in sc.items() if isinstance(it, QGraphicsLineItem)]
            barra = [ln for ln, g in lineas if g > 2 and abs(ln.length() - 2 * dg.TB) < 1e-6]
            self.assertEqual(len(barra), 1, o)
            ln = barra[0]
            if o == "arriba":
                self.assertEqual((ln.y1(), ln.y2()), (ty, ty))
            else:
                self.assertEqual((ln.x1(), ln.x2()), (tx, tx))
                self.assertEqual(sorted((ln.y1(), ln.y2())), [ty - dg.TB, ty + dg.TB])
            cond = texto(sc, "p")
            etq = next(it for it in textos(sc) if it.toPlainText().startswith("(") and it.toPlainText().endswith(")"))
            rc, re_ = cond.sceneBoundingRect(), etq.sceneBoundingRect()
            if o == "arriba":
                self.assertGreater(rc.left(), tx)
                self.assertLess(re_.right(), tx)
            else:
                self.assertLessEqual(rc.bottom(), ty - dg.TB + 4, "la receptividad, encima del trazo")
                self.assertGreaterEqual(re_.top(), ty + dg.TB - 4, "la designación, debajo")
                self.assertLess(abs(rc.center().x() - tx), 3)
                self.assertLess(abs(re_.center().x() - tx), 3)
                for r in enlaces(v.model):  # ningún tramo de enlace cruza los textos
                    for a, b in zip(r["pts"], r["pts"][1:]):
                        caja = QRectF(QPointF(*a), QPointF(*b)).normalized().adjusted(-1, -1, 1, 1)
                        self.assertFalse(caja.intersects(rc) or caja.intersects(re_), (o, r["pts"]))
            self.assertTrue(self.flechas(sc), f"{o}: lleva flecha")
        sc, _ = dibujo(_vista_giro("abajo"))
        self.assertFalse(self.flechas(sc), "abajo: sin flecha")

    def test_SAUL16_anclas_caja_y_clic_siguen_a_la_orientacion(self):
        """REQ-EDT-02: los puntos de unión, la caja del trazo y el clic en la transición siguen su orientación."""
        esperado = {"derecha": ((-dg.ANCLA, 0), (dg.ANCLA, 0)), "izquierda": ((dg.ANCLA, 0), (-dg.ANCLA, 0)),
                    "arriba": ((0, dg.ANCLA), (0, -dg.ANCLA)), "abajo": ((0, -dg.ANCLA), (0, dg.ANCLA))}
        for o, (entrada, salida) in esperado.items():
            v = _vista_giro(o)
            t = v.model["transitions"][0]
            tx, ty = t["x"] + SX, t["y"]
            por_lado = {a["lado"]: a["pos"] for a in anclas(v.model, t["id"])}
            self.assertEqual((por_lado["arriba"].x(), por_lado["arriba"].y()), (tx + entrada[0], ty + entrada[1]), o)
            self.assertEqual((por_lado["abajo"].x(), por_lado["abajo"].y()), (tx + salida[0], ty + salida[1]), o)
            horizontal = o in ("derecha", "izquierda")
            caja = dg.caja_barra(o, tx, ty)
            self.assertEqual((caja.width(), caja.height()), (4, 2 * dg.TB) if horizontal else (2 * dg.TB, 4))
            self.assertEqual(dg.elemento_en(v.model, QPointF(tx, ty - 6 if horizontal else ty)), t["id"], o)
            if horizontal:  # donde estaría el trazo horizontal de siempre ya no es de la transición
                self.assertNotEqual(dg.elemento_en(v.model, QPointF(tx + dg.TB + 20, ty - 8)), t["id"])

    def test_SAUL17_la_orientacion_se_guarda_y_se_abre(self):
        """REQ-DAT-02: viaja en `presentation.transitionOrientations` del archivo y al reabrirlo el dibujo es el mismo."""
        from escritorio.edicion import Edicion
        from grafcet.persistence import open_model
        from grafcet.view import layout_from_presentation
        w, e, t = self.con_transicion()
        e.sel = [t]
        e.girar_transiciones(1)
        e.girar_transiciones(1)
        with tempfile.TemporaryDirectory() as tmp:
            e.guardar(Path(tmp) / "proyecto")
            op = open_model(Path(tmp) / "proyecto")
            self.assertEqual(op.presentations[0]["transitionOrientations"], {t: "arriba"})
            otro = Edicion.desde(op.doc, layout_from_presentation(op.presentations[0]), op.title, presentacion=op.presentations[0])
            self.assertEqual(otro.orientacion_transicion(t), "arriba")
            self.assertEqual(enlaces(e.M), enlaces(otro.M))

    def test_SAUL18_el_modelo_no_cambia_con_el_giro(self):
        """REQ-EDT-02, REQ-MOD-06: el giro es solo presentación: el modelo queda igual y el grafcet sigue pudiendo simularse."""
        w, e, t = self.con_transicion()
        antes = copy.deepcopy(e.ed.model)
        e.sel = [t]
        e.girar_transiciones(1)
        self.assertEqual(e.ed.model, antes)
        self.assertTrue(w.cambiar_modo("simular"))


@unittest.skipUnless(QT, "PySide6 no está instalado")
class EnlacesColocadosAMano(BaseQt):
    """Un tramo colocado a mano manda (P-IMP-113): se puede dejar encima de otro enlace y la recolocación automática no lo mueve."""

    def arrastrar_tramo(self, e, r, eje, punto_y=None, hasta=None):
        h = next(h for h in r["handles"] if h["axis"] == eje)
        pts = r["pts"]
        i = h["segment"]
        p0 = QPointF(pts[i][0], punto_y) if eje == "x" else QPointF((pts[i][0] + pts[i + 1][0]) / 2 - 20, pts[i][1])
        e.sel = []
        e.prensar(p0)
        d = QPointF(hasta, p0.y()) if eje == "x" else QPointF(p0.x(), hasta)
        e.mover(d + QPointF(1, 1))
        e.mover(d)
        e.soltar(d)

    def test_SAUL19_un_tramo_dejado_sobre_otro_enlace_se_queda_y_no_aparta_a_los_automaticos(self):
        """REQ-EDT-02: dos retornos; se deja el carril de uno sobre el del otro (también colocado a mano): se quedan solapados,
        el formato es el de siempre y una edición cualquiera no los recoloca. Un retorno automático no huye de uno manual."""
        w, e = self.vacio()
        A = e.ed.add_step("g", "1", True, at=(100, 80))
        B = e.ed.add_step("g", "2", at=(100, 260))
        C = e.ed.add_step("g", "3", at=(100, 440))
        e.ed.add_transition("g", "", [A], [B], at=(100, 170), label="t1")
        e.ed.add_transition("g", "", [B], [C], at=(100, 350), label="t2")
        t3, _ = e.ed.add_transition("g", "", [C], [A], at=(100, 520), label="t3")
        t4, _ = e.ed.add_transition("g", "", [C], [B], at=(100, 580), label="t4")
        e.cambia()

        def post(tid):
            return next(r for r in enlaces(e.M) if r["tid"] == tid and r["rol"] == "post")
        self.assertEqual((post(t3)["pts"][2][0], post(t4)["pts"][2][0]), (292.0, 104.0), "los dos retornos, automáticos")
        self.arrastrar_tramo(e, post(t4), "x", 300.0, 132.0)  # el carril de t4, hacia donde iría el de t3 (130) si estuviera solo (no hace huir al automático)
        r4 = post(t4)
        estilo = e.ed.link_styles()[r4["id"]]
        self.assertEqual(set(estilo), {"route"})
        self.assertEqual(set(estilo["route"]), {"laneX", "exitY", "entryY"}, "el mismo formato de siempre")
        x4 = r4["pts"][2][0]
        self.assertEqual(x4, SX + float(estilo["route"]["laneX"]))
        self.assertEqual(x4, 140.0, "queda donde se soltó (ajustado a la rejilla)")
        self.assertEqual(post(t3)["pts"][2][0], 292.0, "el automático no se mueve cuando se coloca a mano otro enlace (P-IMP-118)")
        # el otro, también a mano, justo en el mismo carril: solapados exactamente
        e.ed.set_link_style(post(t3)["id"], {"route": {"laneX": estilo["route"]["laneX"], "exitY": "544", "entryY": "42"}})
        self.assertEqual(post(t4)["pts"][2][0], x4, "el automático que se coloca a mano no mueve al otro")
        e.cambia()
        self.assertEqual(post(t3)["pts"][2][0], post(t4)["pts"][2][0])
        e.ed.move(A, 100, 60)  # una edición cualquiera vuelve a calcular los recorridos
        e.cambia()
        e.ed.move(C, 100, 460)
        e.cambia()
        self.assertEqual(post(t3)["pts"][2][0], x4)
        self.assertEqual(post(t4)["pts"][2][0], x4)

    def test_SAUL20_dos_tramos_horizontales_a_mano_en_la_misma_altura_se_quedan_solapados(self):
        """REQ-EDT-02: el tramo medio de un enlace llevado a la altura del de otro enlace se queda ahí, aunque se muevan otros
        elementos después."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        b = e.ed.add_step("g", "2", at=(200, 300))
        t1, _ = e.ed.add_transition("g", "", [a], [b], at=(100, 180), label="t1")
        a2 = e.ed.add_step("g", "3", True, at=(150, 80))
        b2 = e.ed.add_step("g", "4", at=(250, 300))
        t2, _ = e.ed.add_transition("g", "", [a2], [b2], at=(150, 180), label="t2")
        e.cambia()

        def post(tid):
            return next(r for r in enlaces(e.M) if r["tid"] == tid and r["rol"] == "post")
        e.ed.set_link_style(post(t1)["id"], {"route": {"middleY": "240"}})
        e.cambia()
        self.arrastrar_tramo(e, post(t2), "y", hasta=242)
        self.assertEqual(post(t2)["pts"][1][1], 240.0)
        self.assertEqual(post(t1)["pts"][1][1], 240.0)
        e.ed.move(a, 100, 60)
        e.cambia()
        e.ed.move(b2, 260, 320)
        e.cambia()
        self.assertEqual((post(t1)["pts"][1][1], post(t2)["pts"][1][1]), (240.0, 240.0))


@unittest.skipUnless(QT, "PySide6 no está instalado")
class UnionAutomatica(BaseQt):
    """Al soltar un elemento con un punto de unión libre muy cerca de otro libre y compatible, se unen solos (P-IMP-114)."""

    def arrastrar(self, e, ident, a):
        """Agarra el elemento por su centro y lo suelta en el punto del modelo `a` (x, y, sin el margen)."""
        x, y = dg.posiciones(e.M)[ident]
        ini, fin = QPointF(x, y), QPointF(a[0] + SX, a[1])
        e.prensar(ini)
        e.mover((ini + fin) / 2)
        e.mover(fin)
        e.soltar(fin)

    def base(self):
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        t, _ = e.ed.add_transition("g", "", [a], [], at=(100, 180), label="t1")
        b = e.ed.add_step("g", "2", at=(400, 400))
        e.cambia()
        return w, e, a, t, b

    @staticmethod
    def post(e, t):
        return next(x for x in e.M["transitions"] if x["id"] == t)["post"]

    def test_SAUL21_una_etapa_soltada_muy_cerca_de_la_salida_de_una_transicion_se_une(self):
        """REQ-EDT-02: la etapa que se suelta con su entrada a 8 px o menos de la salida libre de una transición se une a ella,
        en el mismo paso de deshacer que el movimiento."""
        w, e, a, t, b = self.base()
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.arrastrar(e, b, (100, 220))  # su entrada queda a 6 px de la salida de t1
        self.assertEqual(self.post(e, t), [b])
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SAUL22_lejos_o_con_el_punto_ocupado_no_se_une_nada(self):
        """REQ-EDT-02: a más de 8 px, o si el punto ya tiene un enlace, no se une; tampoco etapa con etapa."""
        w, e, a, t, b = self.base()
        self.arrastrar(e, b, (100, 260))  # entrada a unos 34 px de la salida
        self.assertEqual(self.post(e, t), [])
        c = e.ed.add_step("g", "3", at=(400, 600))
        e.cambia()
        self.arrastrar(e, b, (100, 220))  # se une b
        self.arrastrar(e, c, (100, 280))  # etapa con etapa no une; y la salida de t1 ya no está libre
        self.assertEqual(self.post(e, t), [b])
        self.assertEqual(len(e.M["transitions"]), 1)

    def test_SAUL23_una_transicion_soltada_cerca_de_la_salida_de_una_etapa_se_une(self):
        """REQ-EDT-02: la transición que se suelta con su entrada muy cerca de la salida libre de una etapa se une a ella."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        t, _ = e.ed.add_transition("g", "", [], [], at=(400, 300), label="t1")
        e.cambia()
        self.arrastrar(e, t, (100, 120))  # entrada a 6 px de la salida de la etapa
        self.assertEqual(next(x for x in e.M["transitions"] if x["id"] == t)["pre"], [a])

    def test_SAUL24_respeta_el_zoom(self):
        """REQ-EDT-02: el radio son 8 px de pantalla: con zoom 200 % son 4 unidades del dibujo; con 50 %, 16."""
        w, e, a, t, b = self.base()
        with mock.patch.object(e, "_zoom", return_value=2.0):
            self.arrastrar(e, b, (100, 220))
        self.assertEqual(self.post(e, t), [])
        self.arrastrar(e, b, (400, 400))
        with mock.patch.object(e, "_zoom", return_value=0.5):
            self.arrastrar(e, b, (100, 220))
        self.assertEqual(self.post(e, t), [b])

    def test_SAUL25_una_transicion_girada_usa_sus_puntos_girados(self):
        """REQ-EDT-02: con la transición girada a la derecha, su salida está a su derecha y es ahí donde une."""
        w, e, a, t, b = self.base()
        e.ed.set_transition_orientation(t, "derecha")
        e.cambia()
        salida = next(x for x in dg.anclas(e.M, t) if x["lado"] == "abajo")["pos"]
        self.assertGreater(salida.x(), dg.posiciones(e.M)[t][0])
        # (con los elementos solapados no se llega con el ratón: se prueba la unión sobre el modelo)
        e.ed.move(b, round(salida.x()) - SX, round(salida.y()) + 22 + 4)  # su entrada, a 4 px de la salida girada
        e.cambia()
        self.assertTrue(e._unir_cercanos({b}))
        self.assertEqual(self.post(e, t), [b])
        e.deshacer()
        e.ed.move(b, 100, 204 + 22 + 4)  # donde estaría la salida sin girar: ya no es un punto de la transición
        e.cambia()
        self.assertFalse(e._unir_cercanos({b}))

    def test_SAUL26_una_transicion_creada_arrastrando_une_tambien_su_otro_punto(self):
        """REQ-EDT-02: la transición que sale de arrastrar de una etapa a un hueco se une también a la etapa que queda debajo si su
        salida está a 8 px o menos de su entrada; un solo paso de deshacer."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        c = e.ed.add_step("g", "2", at=(100, 300))
        e.cambia()
        antes, n = self.estado(e), len(e.ed.undo_stack)
        pa = next(x for x in dg.anclas(e.M, a) if x["lado"] == "abajo")["pos"]
        q = QPointF(100 + SX, 260)  # la salida de la transición nueva queda a 6 px de la entrada de la etapa 2
        e.prensar(pa)
        e.mover(q)
        e.soltar(q)
        tr = next(x for x in e.M["transitions"] if x["id"] == e.sel[0])
        self.assertEqual((tr["pre"], tr["post"]), ([a], [c]))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SAUL27_la_paleta_tambien_une_en_un_solo_paso(self):
        """REQ-EDT-02: una transición soltada desde la paleta junto a la salida de una etapa se une; un solo paso de deshacer."""
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        e.cambia()
        n = len(e.ed.undo_stack)
        self.soltar_ficha("transicion", QPointF(100 + SX, 120))
        self.assertEqual(e.M["transitions"][0]["pre"], [a])
        self.assertEqual(len(e.ed.undo_stack), n + 1)

    def test_SAUL28_una_accion_suelta_se_une_al_punto_de_acciones_de_una_etapa(self):
        """REQ-EDT-02: el punto de una acción suelta a 8 px o menos del de las acciones de una etapa sin ellas las une; con el punto
        de la etapa ya ocupado, no."""
        w, e = self.vacio()
        s = e.ed.add_step("g", "1", True, at=(100, 80))
        e.cambia()
        e.pedir_accion = lambda sid, aid: None
        did = e.ed.add_draft_action((130, 80), {"tipo": "continua"})  # su lado izquierdo a 8 px del punto de la etapa
        e.cambia()
        self.assertTrue(e._unir_cercanos({did}))
        self.assertEqual(next(d for d in e.ed.draft_actions() if d["id"] == did)["etapa"], s)
        otra = e.ed.add_draft_action((130, 80), {"tipo": "continua"})
        e.cambia()
        self.assertFalse(e._unir_cercanos({otra}), "el punto de acciones de la etapa ya no está libre")

    def test_SAUL29_con_las_flechas_no_se_une_solo(self):
        """REQ-EDT-02: el ajuste fino con el teclado no une nada."""
        w, e, a, t, b = self.base()
        e.ed.move(b, 100, 200)
        e.cambia()
        e.sel = [b]
        e.mover_teclado(0, 20)
        self.assertEqual(self.post(e, t), [])


@unittest.skipUnless(QT, "PySide6 no está instalado")
class NuevaAccionDesdeUnaAccion(BaseQt):
    """Tirar del borde de una acción saca otra a continuación: el derecho en fila, el inferior en columna, ninguno en matriz de 2;
    la colocación nunca cambia (P-IMP-115)."""

    def montar(self):
        w, e = self.vacio()
        s = e.ed.add_step("g", "1", True, at=(100, 80))
        e.cambia()
        self.pedidas = []
        e.pedir_accion = lambda sid, aid: self.pedidas.append((sid, aid))
        did = e.anadir_accion(s)
        self.pedidas.clear()
        QApplication.processEvents()
        return w, e, s, did

    def caja(self, w, aid):
        return next(c for c in w.diagrama.cajas_acciones if c["id"] == aid)["rect"]

    def en_etapa(self, e, s):
        return [d for d in e.ed.draft_actions() if d.get("etapa") == s]

    def test_SAUL30_del_borde_derecho_sale_una_accion_a_continuacion(self):
        """REQ-EDT-02: arrastrar del borde derecho de una acción crea otra, vacía, de la misma etapa y detrás; un paso de deshacer."""
        w, e, s, did = self.montar()
        x, y, ancho, alto = self.caja(w, did)
        p = QPointF(x + ancho - 2, y + alto / 2)
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.pasar(p)
        self.assertEqual(w.diagrama.viewport().cursor().shape(), Qt.CursorShape.SizeHorCursor)
        e.prensar(p)
        e.mover(p + QPointF(30, 0))
        e.mover(p + QPointF(60, 0))
        e.soltar(p + QPointF(60, 0))
        acciones = self.en_etapa(e, s)
        self.assertEqual(len(acciones), 2)
        self.assertEqual(acciones[0]["id"], did)
        self.assertEqual(acciones[1]["tipo"], "continua")
        self.assertFalse(acciones[1].get("variable"))
        self.assertEqual(e.colocacion(s), "fila")
        self.assertEqual(self.pedidas, [(s, acciones[1]["id"])])
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SAUL31_en_fila_el_borde_inferior_no_saca_nada_ni_cambia_la_colocacion(self):
        """REQ-EDT-02: en fila el borde inferior no es un punto de tirar: no crea ninguna acción ni pasa la etapa a columna."""
        w, e, s, did = self.montar()
        x, y, ancho, alto = self.caja(w, did)
        p = QPointF(x + ancho / 2, y + alto - 2)
        antes = self.estado(e)
        e.pasar(p)
        self.assertNotEqual(w.diagrama.viewport().cursor().shape(), Qt.CursorShape.SizeVerCursor)
        e.prensar(p)
        e.mover(p + QPointF(0, 40))
        e.soltar(p + QPointF(0, 40))
        self.assertEqual(len(self.en_etapa(e, s)), 1)
        self.assertEqual(e.colocacion(s), "fila")
        self.assertEqual(self.pedidas, [])
        self.assertEqual(self.estado(e), antes)

    def test_SAUL34_en_columna_el_borde_inferior_saca_otra_debajo_sin_cambiar_la_colocacion(self):
        """REQ-EDT-02: en columna el borde inferior crea otra acción de la etapa (un paso de deshacer) y la colocación sigue en
        columna; en fila-separada solo vale el borde derecho; en matriz de 2 no vale ninguno."""
        w, e, s, did = self.montar()
        e.colocar_acciones(s, "columna")
        QApplication.processEvents()
        x, y, ancho, alto = self.caja(w, did)
        p = QPointF(x + ancho / 2, y + alto - 2)
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.pasar(p)
        self.assertEqual(w.diagrama.viewport().cursor().shape(), Qt.CursorShape.SizeVerCursor)
        e.prensar(p)
        e.mover(p + QPointF(0, 40))
        e.soltar(p + QPointF(0, 40))
        self.assertEqual(len(self.en_etapa(e, s)), 2)
        self.assertEqual(e.colocacion(s), "columna")
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SAUL32_un_clic_o_el_cuerpo_de_la_accion_no_crean_nada(self):
        """REQ-EDT-02: pulsar y soltar sin arrastrar (en el borde o en el cuerpo) solo selecciona la acción; arrastrar el cuerpo no crea."""
        w, e, s, did = self.montar()
        x, y, ancho, alto = self.caja(w, did)
        for p in (QPointF(x + ancho - 2, y + alto / 2), QPointF(x + ancho / 2, y + alto / 2)):
            e.prensar(p)
            e.soltar(p)
            self.assertEqual((e.sel, e.accion), ([s], did))
        centro = QPointF(x + ancho / 2, y + alto / 2)
        e.prensar(centro)
        e.mover(centro + QPointF(60, 0))
        e.soltar(centro + QPointF(60, 0))
        self.assertEqual(len(self.en_etapa(e, s)), 1)
        self.assertEqual(self.pedidas, [])

    def test_SAUL33_en_columna_el_borde_derecho_no_saca_nada(self):
        """REQ-EDT-02: en columna las acciones van debajo: el borde derecho no es un punto de tirar (el inferior sí)."""
        w, e, s, did = self.montar()
        e.colocar_acciones(s, "columna")
        QApplication.processEvents()
        x, y, ancho, alto = self.caja(w, did)
        p = QPointF(x + ancho - 2, y + alto / 2)
        e.prensar(p)
        e.mover(p + QPointF(60, 0))
        e.soltar(p + QPointF(60, 0))
        self.assertEqual(len(self.en_etapa(e, s)), 1)
        q = QPointF(x + ancho / 2, y + alto - 2)
        e.prensar(q)
        e.mover(q + QPointF(0, 40))
        e.soltar(q + QPointF(0, 40))
        self.assertEqual(len(self.en_etapa(e, s)), 2)
        self.assertEqual(e.colocacion(s), "columna")

    def test_SAUL35_fila_separada_solo_borde_derecho_y_matriz_ninguno(self):
        """REQ-EDT-02: en fila separada vale el borde derecho y no el inferior; en matriz de 2 no vale ninguno; la colocación no cambia."""
        w, e, s, did = self.montar()
        e.colocar_acciones(s, "matriz-2")
        QApplication.processEvents()
        x, y, ancho, alto = self.caja(w, did)
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == did)
        for punto in (QPointF(x + ancho - 2, y + alto / 2), QPointF(x + ancho / 2, y + alto - 2)):
            self.assertIsNone(e._borde_accion(caja, punto))
        e.colocar_acciones(s, "fila-separada")
        QApplication.processEvents()
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == did)
        x, y, ancho, alto = caja["rect"]
        self.assertEqual(e._borde_accion(caja, QPointF(x + ancho - 2, y + alto / 2)), "der")
        self.assertIsNone(e._borde_accion(caja, QPointF(x + ancho / 2, y + alto - 2)))
        self.assertEqual(e.colocacion(s), "fila-separada")


class ValoresInicialesFueraDelGrafcet(BaseQt):
    """P-IMP-117: todas las variables, entradas incluidas, empiezan en 0 (falso)."""

    def _grafnet(self, init):
        from escritorio.proyecto_archivo import guardar_grafnet
        from escritorio.sello import CLAVE
        from grafcet.persistence import add_document, new_project
        m = M().var("C", "input", "int", init=init).var("M1", "output").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "C = 3")
        doc = m.doc
        proyecto = new_project(doc["id"], "prueba")
        add_document(proyecto, doc)
        destino = Path(self.tmp.name) / "p.grafnet"
        guardar_grafnet(destino, proyecto, CLAVE, None).cerrar()
        return destino

    def test_SAUL36_variable_nueva_de_cualquier_rol_empieza_en_cero(self):
        """REQ-EDT-07: una entrada nueva empieza en 0 (falso) y otro valor inicial se rechaza."""
        ed = Editor(new_grafcet_document("g"))
        ent = ed.add_variable("p", "input", {"kind": "bool"})
        num = ed.add_variable("n", "input", {"kind": "int"})
        val = {v["id"]: v["initialValue"] for v in ed.model["variables"]}
        self.assertIs(val[ent], False)
        self.assertEqual(val[num], "0")
        with self.assertRaises(DiagnosticError) as cm:
            ed.change_variable(num, initialValue="3")
        self.assertEqual(cm.exception.diagnostics[0].field, "initialValue")
        self.assertIn("empiezan en 0", cm.exception.diagnostics[0].message)
        with self.assertRaises(DiagnosticError):
            ed.add_variable("q", "input", {"kind": "int"}, initial="3")

    def test_SAUL37_abrir_un_archivo_con_valor_inicial_lo_quita_y_avisa(self):
        """REQ-EDT-07: el archivo se abre, el valor inicial pasa a 0, hay un aviso y el proyecto queda modificado."""
        ruta = self._grafnet("3")
        with mock.patch("escritorio.ventana.QMessageBox.information") as aviso,                 mock.patch("escritorio.ventana.QMessageBox.warning") as fallo:
            self.assertTrue(self.w.abrir_ruta(ruta))
            fallo.assert_not_called()
            aviso.assert_called_once()
        texto = aviso.call_args.args[2]
        self.assertIn("Valores iniciales quitados: C empezaba en 3", texto)
        self.assertIn("C = 3", texto)
        e = self.w.edicion
        self.assertEqual(next(v for v in e.ed.model["variables"] if v["id"] == "C")["initialValue"], "0")
        self.assertTrue(e.ed.dirty)

    def test_SAUL38_archivo_sin_valores_iniciales_no_avisa_ni_queda_modificado(self):
        """REQ-EDT-07: un archivo con todo a 0 se abre sin aviso y sin cambios pendientes."""
        ruta = self._grafnet("0")
        with mock.patch("escritorio.ventana.QMessageBox.information") as aviso:
            self.assertTrue(self.w.abrir_ruta(ruta))
            aviso.assert_not_called()
        self.assertFalse(self.w.edicion.ed.dirty)


if __name__ == "__main__":
    unittest.main()
