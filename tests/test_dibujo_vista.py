"""Dibujo del grafcet y zoom (S-EDI200..219): la barra de la negación, el tiempo transcurrido de un temporizador encima de
su duración y el zoom anclado al puntero con «Centrar todo».

Las pruebas del estado (`Vista`) no necesitan Qt. Las del dibujo y la vista se omiten si PySide6 no está instalado y usan la
plataforma «offscreen» de Qt: no abren ventanas. Ninguna es oráculo del documento 11: comprueban que el dibujo muestra lo
que decide el motor, igual en escritorio/diagrama.py y en tools/dibujo.js.
"""
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers import M  # noqa: E402

from grafcet.profile import normalize_options  # noqa: E402
from grafcet.view import Vista  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path("C:/Windows/Fonts").is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsScene, QGraphicsTextItem
    from escritorio import diagrama as dg
    QT = True
except ImportError:  # el núcleo no depende de Qt
    QT = False


def vista(m, layout=None, **kw):
    return Vista("m", "", "", lambda: (m, layout), normalize_options(None), **kw)


def modelo_negado():
    """A -t(marcha · NOT paro)→ B -u(NOT (p AND q) AND NOT X(A))→ C, con una acción de B con NOT q y un evento de C con NOT q."""
    m = (M().var("marcha").var("paro").var("p").var("q").var("n", "internal", "int").var("y", "output")
         .step("A", True).step("B").step("C"))
    m.trans("t", ["A"], ["B"], "marcha AND NOT paro")
    m.trans("u", ["B"], ["C"], "NOT (p AND q) AND NOT active(A)")
    m.cont("B", "y", "NOT q")
    m.stored("C", "n", "event", "n + 1", event="rise(NOT q)")
    return m, {"A": (220, 60), "t": (220, 140), "B": (220, 220), "u": (220, 300), "C": (220, 380)}


def modelo_temporizado():
    """A -t1(go)→ B -t2(ok · 3s/X(B))→ C; B lleva y (siempre) y z (condicionada por 2s/q)."""
    m = M().var("go").var("ok").var("q").var("y", "output").var("z", "output").step("A", True).step("B").step("C")
    m.trans("t1", ["A"], ["B"], "go")
    m.trans("t2", ["B"], ["C"], "ok AND delay(3 s, active(B), 0 s)")
    m.cont("B", "y")
    m.cont("B", "z", "delay(2 s, q, 0 s)")
    return m, {"A": (220, 60), "t1": (220, 140), "B": (220, 220), "t2": (220, 300), "C": (220, 380)}


def corriendo(m, layout, **kw):
    """B activa desde el instante 0 (t2 cuenta, con ok a 0 para que no franquee) y q desde 0,5 s: a 1 s, t2 lleva «1 s» y
    la condición de z lleva «0,5 s»."""
    v = vista(m, layout, **kw)
    v.act("fijar", {"cambios": {"go": True}})
    v.act("avanzar", {"us": 500_000})
    v.act("fijar", {"cambios": {"q": True}})
    v.act("avanzar", {"us": 500_000})
    return v


def dibujo(v, S=None):
    sc = QGraphicsScene()
    cajas = dg.dibujar(sc, v.model, S if S is not None else v.state())
    return sc, cajas


def textos(sc):
    return [it for it in sc.items() if isinstance(it, QGraphicsTextItem)]


def texto(sc, plano):
    return next(it for it in textos(sc) if it.toPlainText() == plano)


def barras_negado(sc):
    return [it for it in sc.items() if isinstance(it, QGraphicsLineItem) and abs(it.pen().widthF() - dg.GROSOR_NEGADO) < 1e-6]


@unittest.skipUnless(QT, "requiere PySide6")
class Negado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SEDI200_la_barra_del_negado_es_una_linea_de_2_px_sobre_la_palabra(self):
        """REQ-EDT-02: la barra de una variable negada es una línea propia de 2 px (el sobrerrayado del texto es de 1 px y
        Qt no deja regularlo) que cubre exactamente la palabra, pegada a su borde de arriba; el texto ya no lleva
        sobrerrayado."""
        m, lay = modelo_negado()
        sc, _ = dibujo(vista(m, lay))
        t = texto(sc, "marcha·paro")
        # La barra de «paro»: de donde empieza «paro» hasta donde acaba el texto, a la altura del borde de arriba del texto
        ancho_paro = dg._Pintor.ancho([{"t": "paro"}], 14)
        barra = next(b for b in barras_negado(sc) if abs(b.line().y1() - t.pos().y()) < 0.01
                     and b.line().x2() > t.pos().x() + t.boundingRect().width() - 1.5)
        self.assertAlmostEqual(barra.line().x2() - barra.line().x1(), ancho_paro, delta=1.0)
        self.assertAlmostEqual(barra.line().x2(), t.pos().x() + t.boundingRect().width(), delta=1.5)
        self.assertEqual(barra.pen().widthF(), 2.0)
        self.assertEqual(barra.pen().color().rgb(), t.defaultTextColor().rgb(), "del color del texto")
        self.assertNotIn("overline", t.toHtml(), "la negación ya no es el sobrerrayado del texto")
        # La etiqueta de la interfaz (panel de propiedades) sigue con el sobrerrayado, que es lo único que puede dibujar
        self.assertIn("overline", dg._html([{"t": "paro", "o": True}]))
        self.assertNotIn("overline", dg._html([{"t": "paro", "o": True}], False))

    def test_SEDI201_la_barra_cubre_cada_tramo_negado_en_receptividades_condiciones_y_eventos(self):
        """REQ-EDT-02: un tramo de segmentos negados seguidos (NOT (p AND q), NOT X(A) con su subíndice) lleva una sola
        barra, y la hay en la receptividad, en la condición de una acción y en su evento."""
        m, lay = modelo_negado()
        sc, _ = dibujo(vista(m, lay))
        u = texto(sc, "p·q·XA")  # NOT (p AND q) AND NOT X(A): dos tramos, p·q y XA
        cerca = [b for b in barras_negado(sc) if abs(b.line().y1() - u.pos().y()) < 0.01 and
                 u.pos().x() - 0.1 <= b.line().x1() <= u.pos().x() + u.boundingRect().width()]
        self.assertEqual(len(cerca), 2, "una barra por tramo, no una por segmento")
        cerca.sort(key=lambda b: b.line().x1())
        self.assertAlmostEqual(cerca[0].line().x1(), u.pos().x(), delta=0.01)
        self.assertAlmostEqual(cerca[0].line().x2() - cerca[0].line().x1(), dg._Pintor.ancho(
            [{"t": "p"}, {"t": "·"}, {"t": "q"}], 14), delta=1.0)
        self.assertAlmostEqual(cerca[1].line().x2(), u.pos().x() + u.boundingRect().width(), delta=1.5)
        cond = texto(sc, "q")  # la condición de la acción de B, escrita con 13 px
        self.assertTrue(any(abs(b.line().y1() - cond.pos().y()) < 0.01 for b in barras_negado(sc)))
        evento = texto(sc, "↑(q)")
        self.assertTrue(any(abs(b.line().y1() - evento.pos().y()) < 0.01 and b.line().x1() > evento.pos().x()
                            for b in barras_negado(sc)))

    def test_SEDI202_la_barra_no_cambia_anchos_ni_disposicion(self):
        """REQ-EDT-02: la barra no cambia lo que mide un texto ni dónde caen las cajas de las acciones (la disposición no
        depende de si una variable está negada)."""
        for tam in (13, 14, 15):
            self.assertEqual(dg._Pintor.ancho([{"t": "paro", "o": True}], tam), dg._Pintor.ancho([{"t": "paro"}], tam))
        negada = {"kind": "continuous", "id": "a", "target": "y", "text": [{"t": "y"}], "cond": [{"t": "q", "o": True}]}
        normal = {**negada, "cond": [{"t": "q"}]}
        self.assertEqual(dg._ancho_accion(negada), dg._ancho_accion(normal))
        for disp in ("fila", "columna", "matriz-2", "fila-separada"):
            self.assertEqual([c[1:] for c in dg._geometria_acciones(0, 0, [negada, negada], disp)[0]],
                             [c[1:] for c in dg._geometria_acciones(0, 0, [normal, normal], disp)[0]])

    def test_SEDI203_dibujo_js_y_css_pintan_la_misma_barra(self):
        """REQ-EDT-02: el banco web (tools/dibujo.js y dibujo.css) pinta la barra del negado como una línea propia de 2 px,
        igual que Qt, y no usa el sobrerrayado del texto."""
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        css = (ROOT / "tools" / "dibujo.css").read_text(encoding="utf-8")
        self.assertEqual(int(re.search(r"const GROSOR_NEGADO = (\d+)", js).group(1)), int(dg.GROSOR_NEGADO))
        self.assertNotIn("text-decoration", js)
        self.assertIn('class:"neg"', js)
        self.assertRegex(css, r"\.neg\{[^}]*stroke-width:2[;}]")
        self.assertEqual(int(re.search(r"const TMR_EXTRA = (\d+)", js).group(1)), dg.TMR_EXTRA)


class Temporizador(unittest.TestCase):
    def test_SEDI204_el_estado_del_temporizador_es_solo_lo_transcurrido(self):
        """REQ-SIM-03, REQ-TMP-01: antes de empezar no hay nada que mostrar; mientras cuenta, solo el tiempo transcurrido
        («1 s», sin el preset); al vencer, «3 s ✓». Cada temporizador dice qué duración del texto es la suya (`token`,
        `nth`); la tabla de temporizadores conserva «lleva» y «preset»."""
        m, lay = modelo_temporizado()
        v = vista(m, lay)
        self.assertEqual({(t["estado"], t["shown"]) for t in v.state()["temporal"].values()}, {("parado", "")})
        v = corriendo(m, lay)
        por_token = {t["token"]: t for t in v.state()["temporal"].values()}
        t2, z = por_token["3s"], por_token["2s"]
        self.assertEqual((t2["estado"], t2["shown"], t2["lleva"], t2["preset"], t2["nth"]),
                         ("contando", "1 s", "1 s", "3 s", 0))
        self.assertEqual((z["estado"], z["shown"], z["lleva"], z["preset"]), ("contando", "0,5 s", "0,5 s", "2 s"))
        v.act("avanzar", {"us": 2_000_000})  # t2 vence a los 3 s (ok es 0: no franquea); z, a los 2,5 s de q
        por_token = {t["token"]: t for t in v.state()["temporal"].values()}
        self.assertEqual([(t["estado"], t["shown"]) for t in (por_token["3s"], por_token["2s"])],
                         [("vencido", "3 s ✓"), ("vencido", "2 s ✓")])

    def test_SEDI205_dos_temporizadores_de_la_misma_duracion_se_distinguen_por_su_orden(self):
        """REQ-TMP-01: «3s/p OR 3s/q/2s»: cada temporizador apunta a su propia aparición de «3s» en el texto; el de
        desconexión apunta a la duración de desconexión."""
        m = M().var("p").var("q").var("y", "output").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "delay(3 s, p, 0 s) OR delay(3 s, q, 2 s)")
        v = vista(m, {"A": (220, 60), "t": (220, 140), "B": (220, 220)})
        v.act("fijar", {"cambios": {"p": True, "q": True}})
        v.act("avanzar", {"us": 500_000})
        ts = {k: (t["token"], t["nth"]) for k, t in v.state()["temporal"].items()}
        self.assertEqual(sorted(ts.values()), [("3s", 0), ("3s", 1)])
        textos_ = [s["t"] for s in v.model["transitions"][0]["cond"]]
        self.assertEqual(textos_.count("3s"), 2)
        v.act("avanzar", {"us": 3_000_000})
        v.act("fijar", {"cambios": {"q": False}})  # el segundo temporizador cuenta su desconexión: «2s», la única de su texto
        off = next(t for t in v.state()["temporal"].values() if t["off"])
        self.assertEqual((off["token"], off["nth"], off["preset"]), ("2s", 0, "2 s"))

    def test_SEDI206_las_acciones_con_retardo_se_marcan_en_el_modelo_sin_depender_del_estado(self):
        """REQ-TMP-01: la acción con un retardo en su condición o su evento lleva `tmr` (para reservarle sitio arriba); la
        marca no cambia al simular."""
        m, lay = modelo_temporizado()
        v = vista(m, lay)
        acc = {a["target"]: a for a in v.model["steps"][1]["actions"]}
        self.assertEqual((bool(acc["y"].get("tmr")), bool(acc["z"].get("tmr"))), (False, True))
        v.act("fijar", {"cambios": {"go": True, "q": True}})
        v.act("avanzar", {"us": 2_500_000})
        self.assertEqual({a["target"]: bool(a.get("tmr")) for a in v.model["steps"][1]["actions"]}, {"y": False, "z": True})


@unittest.skipUnless(QT, "requiere PySide6")
class DibujoTemporizador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SEDI207_el_tiempo_transcurrido_va_centrado_encima_de_la_duracion(self):
        """REQ-SIM-03, REQ-TMP-01: en la receptividad «ok·3s/XB» el «1 s» se centra encima del «3s» (no a la derecha), justo
        sobre la línea de arriba del texto; al vencer, «3 s ✓» en el mismo sitio y en otro color; antes de empezar, nada."""
        m, lay = modelo_temporizado()
        v = corriendo(m, lay)
        sc, _ = dibujo(v)
        cond = texto(sc, "ok·3s/XB")
        etiqueta = texto(sc, "1 s")
        segs = v.model["transitions"][1]["cond"]
        lim = dg._Pintor.limites(segs, 14)
        i = [s["t"] for s in segs].index("3s")
        centro = cond.pos().x() + (lim[i] + lim[i + 1]) / 2
        r = etiqueta.sceneBoundingRect()
        self.assertAlmostEqual((r.left() + r.right()) / 2, centro, delta=1.0)
        base = etiqueta.pos().y() + dg._Pintor.ascenso(dg.TMR_TAM, True)  # línea base de la etiqueta
        self.assertTrue(0 < cond.pos().y() - base <= 4, f"encima y pegada al texto: {cond.pos().y() - base}")
        self.assertGreater(centro, cond.pos().x() + 10, "no está al principio del texto: se localiza midiendo")
        self.assertLess(r.right(), cond.pos().x() + cond.boundingRect().width() + 2, "no se va a la derecha del texto")
        self.assertEqual(etiqueta.defaultTextColor().name(), dg.COL["accent"])
        # Antes de empezar no hay nada; al vencer, «3 s ✓» en el mismo sitio y de otro color
        sc0, _ = dibujo(vista(m, lay))
        colores = {dg.COL["accent"], dg.COL["ok"]}
        self.assertEqual([it.toPlainText() for it in textos(sc0) if it.defaultTextColor().name() in colores], [])
        v.act("avanzar", {"us": 2_000_000})
        sc1, _ = dibujo(v)
        hecho = texto(sc1, "3 s ✓")
        self.assertEqual(hecho.defaultTextColor().name(), dg.COL["ok"])
        self.assertAlmostEqual(hecho.sceneBoundingRect().center().x(), centro, delta=1.0)

    def test_SEDI208_si_no_se_localiza_la_duracion_se_centra_sobre_toda_la_receptividad(self):
        """REQ-SIM-03: un temporizador cuya duración no está en el texto (token desconocido) se centra encima de toda la
        receptividad, no a la derecha."""
        m, lay = modelo_temporizado()
        v = corriendo(m, lay)
        S = v.state()
        for t in S["temporal"].values():
            t["token"] = "9s"
        sc, _ = dibujo(v, S)
        cond, etiqueta = texto(sc, "ok·3s/XB"), texto(sc, "1 s")
        r = etiqueta.sceneBoundingRect()
        self.assertAlmostEqual((r.left() + r.right()) / 2, cond.pos().x() + cond.boundingRect().width() / 2, delta=1.0)

    def test_SEDI209_el_tiempo_transcurrido_no_pisa_la_barra_de_la_transicion_ni_el_texto(self):
        """REQ-SIM-03: el tiempo transcurrido de una receptividad no toca el trazo de la transición, ni su designación, ni el
        texto de la receptividad; con comentario, éste empieza después."""
        m, lay = modelo_temporizado()
        v = corriendo(m, lay, comments={"t2": "se espera"})
        sc, _ = dibujo(v)
        r = texto(sc, "1 s").sceneBoundingRect()
        tx, ty = 220 + dg.SX, 300
        self.assertFalse(r.intersects(QRectF(tx - dg.TB, ty - 1.5, 2 * dg.TB, 3)), "no toca el trazo de la transición")
        self.assertFalse(r.intersects(QRectF(tx - 1, ty - 40, 2, 80)), "ni el enlace vertical que la cruza")
        self.assertFalse(r.intersects(texto(sc, "(t2)").sceneBoundingRect()))
        cond = texto(sc, "ok·3s/XB")
        self.assertLessEqual(r.bottom() - cond.pos().y(), 4, "el cuadro de la etiqueta apenas entra en el del texto")
        com = next(it for it in textos(sc) if it.toPlainText().startswith("“"))
        self.assertGreater(com.pos().x(), max(r.right(), cond.pos().x() + cond.boundingRect().width()))

    def test_SEDI210_condicion_y_evento_de_una_accion_llevan_su_tiempo_encima_de_su_duracion(self):
        """REQ-SIM-03, REQ-TMP-01: en una acción con condición temporizada, y en una memorizada con un evento con retardo,
        el tiempo transcurrido va centrado encima de la duración del texto, por encima de la marca."""
        m = (M().var("go").var("q").var("r").var("y", "output").var("n", "internal", "int").step("A", True).step("B"))
        m.trans("t", ["A"], ["B"], "go")
        m.cont("B", "y", "delay(2 s, q, 0 s)")
        m.stored("B", "n", "event", "n + 1", event="rise(r) AND delay(1 s, q, 0 s)")
        v = vista(m, {"A": (220, 60), "t": (220, 140), "B": (220, 220)})
        v.act("fijar", {"cambios": {"go": True, "q": True}})
        v.act("avanzar", {"us": 500_000})
        sc, cajas = dibujo(v)
        a_cond, a_evento = v.model["steps"][1]["actions"]
        for plano, segs, dur in (("2s/q", a_cond["cond"], "2s"), ("↑r·1s/q", a_evento["event"], "1s")):
            cond = texto(sc, plano)
            lim = dg._Pintor.limites(segs, 13)
            i = [s["t"] for s in segs].index(dur)
            centro = cond.pos().x() + (lim[i] + lim[i + 1]) / 2
            etiqueta = next(it for it in textos(sc) if it.toPlainText() == "0,5 s"
                            and abs(it.sceneBoundingRect().center().x() - centro) < 1.5)
            base = etiqueta.pos().y() + dg._Pintor.ascenso(dg.TMR_TAM, True)
            self.assertTrue(0 < cond.pos().y() - base <= 4, (plano, cond.pos().y() - base))

    def test_SEDI211_el_tiempo_de_una_accion_con_retardo_no_pisa_la_caja_de_arriba(self):
        """REQ-SIM-03: en una columna de acciones, el tiempo transcurrido de la segunda cabe en el hueco que la disposición le
        reserva (`tmr`): no toca la caja de la primera; sin la marca el hueco sería menor."""
        m, lay = modelo_temporizado()
        v = corriendo(m, lay, action_layouts={"B": "columna"})
        sc, cajas = dibujo(v)
        a1, a2 = sorted(cajas, key=lambda c: c["rect"][1])
        self.assertTrue(all(c["etapa"] == "B" for c in cajas))
        hueco = a2["rect"][1] - (a1["rect"][1] + a1["rect"][3])
        r = texto(sc, "0,5 s").sceneBoundingRect()
        self.assertGreaterEqual(r.top() - 1, a1["rect"][1] + a1["rect"][3],
                                "el cuadro de la etiqueta queda debajo de la caja de arriba")
        self.assertEqual(hueco, 20 + dg.TMR_EXTRA + 4)
        sin = [{**a, "tmr": False} for a in v.model["steps"][1]["actions"]]
        ys = [c[2] for c in dg._geometria_acciones(0, 0, sin, "columna")[0]]
        con = [c[2] for c in dg._geometria_acciones(0, 0, v.model["steps"][1]["actions"], "columna")[0]]
        self.assertEqual((con[1] - con[0]) - (ys[1] - ys[0]), dg.TMR_EXTRA)

    def test_SEDI212_dibujo_js_coloca_el_tiempo_encima_de_la_duracion_igual_que_qt(self):
        """REQ-SIM-03: el banco web escribe solo lo transcurrido encima de la duración (token y aparición, o todo el texto), con
        el mismo hueco `tmr` que Qt, y ya no usa el «lleva / preset» a la derecha."""
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        self.assertIn("t.token", js)
        self.assertIn("t.nth", js)
        self.assertIn("a.tmr", js)
        self.assertNotIn("getComputedTextLength() + 8, top-", js, "el estado ya no va a la derecha de la condición")
        self.assertIn("text.timer{", (ROOT / "tools" / "dibujo.css").read_text(encoding="utf-8"))
        # La misma altura que reserva Qt para una condición y un evento con temporizador
        self.assertEqual(dg._extra({"kind": "continuous", "cond": [{"t": "c"}], "tmr": True})[0], 20 + dg.TMR_EXTRA)
        self.assertEqual(dg._extra({"kind": "stored", "trigger": "event", "tmr": True})[0], 24 + dg.TMR_EXTRA)
        self.assertEqual(dg._extra({"kind": "stored", "trigger": "activation", "tmr": True})[0], 20)


@unittest.skipUnless(QT, "requiere PySide6")
class Zoom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        m = M().var("go").step("E0", True)
        prev = "E0"
        for k in range(1, 13):  # un dibujo grande: trece etapas, más alto que la vista
            m.step(f"E{k}").trans(f"t{k}", [prev], [f"E{k}"], "go")
            prev = f"E{k}"
        self.v = vista(m)
        self.d = dg.VistaDiagrama()
        self.d.resize(900, 650)
        self.d.show()
        self.app.processEvents()
        self.d.mostrar(self.v.model, self.v.state())
        self.app.processEvents()

    def tearDown(self):
        self.d.close()
        self.d.deleteLater()

    def contenido(self):
        return self.d.scene().itemsBoundingRect()

    def visible(self):
        return self.d.mapToScene(self.d.viewport().rect()).boundingRect()

    def rueda(self, pos, delta, mod=Qt.KeyboardModifier.NoModifier):
        p = QPointF(*pos)
        ev = QWheelEvent(p, self.d.viewport().mapToGlobal(p), QPoint(0, 0), QPoint(0, delta), Qt.MouseButton.NoButton,
                         mod, Qt.ScrollPhase.NoScrollPhase, False)
        self.app.sendEvent(self.d.viewport(), ev)
        self.app.processEvents()

    def bajo(self, pos):
        return self.d._a_escena(QPointF(*pos))

    def test_SEDI213_la_rueda_hace_zoom_anclada_al_puntero(self):
        """REQ-SIM-03, REQ-EDT-02: con la rueda, el punto del dibujo que está bajo el cursor se queda bajo el cursor (a menos
        de 1 px), también cuando el dibujo cabe sin barras de desplazamiento, en cualquier esquina y acercando o alejando."""
        d = self.d
        self.assertEqual(d.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff, "al ajustar no hay barras")
        for pos in ((100, 100), (450, 325), (840, 600), (30, 600), (840, 40)):
            for delta in (120, -120, -120, 120, 120, -120):
                antes, k0 = self.bajo(pos), d.escala()
                self.rueda(pos, delta)
                self.assertNotEqual(d.escala(), k0)
                despues = self.bajo(pos)
                err = max(abs(despues.x() - antes.x()), abs(despues.y() - antes.y())) * d.escala()
                self.assertLess(err, 1.0, f"{pos} {delta}: el punto se movió {err:.2f} px")
        d.ajustar()
        k0 = d.escala()
        self.rueda((450, 325), 120, Qt.KeyboardModifier.ControlModifier)  # con Ctrl, lo mismo
        self.assertGreater(d.escala(), k0)

    def test_SEDI214_la_rueda_ancla_tambien_con_mucho_zoom_y_cerca_del_borde_de_la_escena(self):
        """REQ-SIM-03: tras acercar al máximo y desplazarse hasta el borde, la rueda sigue anclada (la escena tiene margen
        de una vista a cada lado a cualquier zoom)."""
        d = self.d
        for _ in range(30):
            self.rueda((450, 325), 120)
        self.assertAlmostEqual(d.escala(), dg.ZOOM_MAX, places=6)
        d.horizontalScrollBar().setValue(d.horizontalScrollBar().minimum())
        d.verticalScrollBar().setValue(d.verticalScrollBar().minimum())
        for pos in ((10, 10), (450, 325), (700, 500)):  # (no pegado al borde contrario: ahí el desplazamiento ya no da más)
            for delta in (-120, 120):
                antes = self.bajo(pos)
                self.rueda(pos, delta)
                despues = self.bajo(pos)
                err = max(abs(despues.x() - antes.x()), abs(despues.y() - antes.y())) * d.escala()
                self.assertLess(err, 1.5, f"{pos} {delta}: {err:.2f} px")

    def test_SEDI215_centrar_todo_deja_todo_lo_dibujado_dentro_y_centrado(self):
        """REQ-SIM-03, REQ-EDT-02: «Centrar todo» (el botón, `ajustar` y Ctrl+0 del menú) encaja y centra todo el dibujo con
        un margen, venga de donde venga la vista; el botón se llama así y su ayuda dice el atajo."""
        d = self.d
        self.assertEqual(d.b_ajustar.text(), "Centrar todo")
        self.assertIn("Ctrl+0", d.b_ajustar.toolTip())
        fit = d.escala()
        for _ in range(8):  # se aleja y se pierde por una esquina
            self.rueda((20, 20), -120)
        d.horizontalScrollBar().setValue(d.horizontalScrollBar().maximum())
        self.assertLess(d.escala(), fit)
        d.b_ajustar.click()
        self.app.processEvents()
        c, vis = self.contenido(), self.visible()
        self.assertTrue(vis.contains(c), f"todo el dibujo dentro de la vista: {c} en {vis}")
        self.assertAlmostEqual(vis.center().x(), c.center().x(), delta=1.0 / d.escala())
        self.assertAlmostEqual(vis.center().y(), c.center().y(), delta=1.0 / d.escala())
        izq = (c.left() - vis.left()) * d.escala()
        arriba = (c.top() - vis.top()) * d.escala()
        self.assertGreaterEqual(min(izq, arriba), dg.MARGEN_AJUSTE - 2, "con un margen libre alrededor")
        self.assertAlmostEqual(d.escala(), fit, delta=0.02, msg="encaja como al abrir (el viewport cambia por las barras)")

    def test_SEDI216_centrar_todo_al_editar_encaja_lo_dibujado_y_no_el_area_minima(self):
        """REQ-EDT-02: al editar, «Centrar todo» encaja y centra los elementos dibujados (un dibujo pequeño se amplía), no el
        área mínima vacía de 1100 × 760, y el zoom queda manual."""
        m = M().var("go").step("E0", True).step("E1").trans("t1", ["E0"], ["E1"], "go")
        v = vista(m)
        d = self.d
        d.modo_edicion(True, SimpleNamespace())
        d.mostrar(v.model, v.state())
        self.app.processEvents()
        self.assertAlmostEqual(d.escala(), 1.0, places=6)
        d.b_ajustar.click()
        self.app.processEvents()
        c, vis = self.contenido(), self.visible()
        self.assertGreater(d.escala(), 1.2, "el área mínima (1100 × 760) daría menos de 0,8")
        self.assertTrue(vis.contains(c))
        self.assertAlmostEqual(vis.center().x(), c.center().x(), delta=1.0 / d.escala())
        self.assertAlmostEqual(vis.center().y(), c.center().y(), delta=1.0 / d.escala())
        self.assertTrue(d._manual, "al editar el zoom no se recoloca solo")
        d.mostrar(v.model, v.state())  # un refresco no mueve lo que se ve
        self.assertAlmostEqual(self.visible().center().x(), vis.center().x(), delta=1.0 / d.escala())
        self.assertAlmostEqual(self.visible().center().y(), vis.center().y(), delta=1.0 / d.escala())
        d.modo_edicion(False)  # al simular, vuelve a ajustarse solo
        self.assertFalse(d._manual)

    def test_SEDI217_alejar_no_deja_el_dibujo_fuera_de_la_vista(self):
        """REQ-SIM-03: a cualquier zoom, hasta el mínimo y desplazándose hasta cualquier extremo, queda a la vista al menos
        una parte del dibujo, y «Centrar todo» lo devuelve."""
        d = self.d
        for _ in range(40):
            self.rueda((880, 630), -120)
        self.assertAlmostEqual(d.escala(), dg.ZOOM_MIN, places=6)
        c = self.contenido()
        for escala_ in (dg.ZOOM_MIN, 0.5, 1.0, 4.0, dg.ZOOM_MAX):  # a cualquier zoom, hasta cada extremo, queda un trozo
            d.zoom(escala_ / d.escala())
            for h in (d.horizontalScrollBar().minimum(), d.horizontalScrollBar().maximum()):
                for vv in (d.verticalScrollBar().minimum(), d.verticalScrollBar().maximum()):
                    d.horizontalScrollBar().setValue(h)
                    d.verticalScrollBar().setValue(vv)
                    tocado = self.visible().intersected(c)
                    lo_que_hay = min(60, c.width() * d.escala(), c.height() * d.escala())  # al menos 60 px del dibujo, o todo él si es menor
                    self.assertGreaterEqual(min(tocado.width(), tocado.height()) * d.escala(), lo_que_hay - 2,
                                            (escala_, h, vv, tocado))
        d.b_ajustar.click()
        self.assertTrue(self.visible().contains(c))

    def test_SEDI218_zoom_manual_fijo_hasta_centrar_y_doble_clic_al_simular(self):
        """REQ-SIM-03: tras hacer zoom con la rueda la vista no se reajusta sola (ni al refrescar ni al cambiar de tamaño)
        hasta «Centrar todo»; el doble clic al simular centra; las barras solo se ven con zoom manual."""
        d = self.d
        fit = d.escala()
        self.rueda((450, 325), 120)
        self.rueda((450, 325), 120)
        k = d.escala()
        self.assertGreater(k, fit)
        self.assertEqual(d.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        esquina = d._a_escena(QPointF(0, 0))
        d.mostrar(self.v.model, self.v.state())  # refresco: ni zoom ni posición cambian
        self.assertEqual(d.escala(), k)
        self.assertAlmostEqual(d._a_escena(QPointF(0, 0)).x(), esquina.x(), delta=1.0 / k)
        self.assertAlmostEqual(d._a_escena(QPointF(0, 0)).y(), esquina.y(), delta=1.0 / k)
        d.resize(800, 600)
        self.app.processEvents()
        self.assertEqual(d.escala(), k, "con zoom manual, cambiar de tamaño no reajusta")
        QTest.mouseDClick(d.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(300, 300))
        self.app.processEvents()
        self.assertFalse(d._manual)
        self.assertTrue(self.visible().contains(self.contenido()))
        self.assertEqual(d.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        k2 = d.escala()
        d.resize(900, 650)  # sin zoom manual, la vista se reencaja con la ventana
        self.app.processEvents()
        self.assertNotEqual(d.escala(), k2)
        self.assertTrue(self.visible().contains(self.contenido()))

    def test_SEDI219_arrastrar_el_dibujo_con_la_mano_deja_la_vista_manual_y_los_botones_zoomean_al_centro(self):
        """REQ-SIM-03: al simular, arrastrar el dibujo lo deja donde se suelta (no se reencaja con el siguiente refresco); «+» y
        «−» hacen zoom alrededor del centro de la vista."""
        d = self.d
        self.assertFalse(d._manual)
        QTest.mousePress(d.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(400, 300))
        QTest.mouseMove(d.viewport(), QPoint(380, 280))
        QTest.mouseRelease(d.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(380, 280))
        self.assertTrue(d._manual, "el arrastre es mover la vista a mano")
        d.b_ajustar.click()  # (sin zoom manual)
        self.assertFalse(d._manual)
        for boton in (d.b_mas, d.b_menos, d.b_menos):
            d.b_mas.click()  # con zoom manual (las barras ocupan sitio) el centro de la vista es otro
            centro = QPointF(d.viewport().width() / 2, d.viewport().height() / 2)
            antes = self.bajo((centro.x(), centro.y()))
            boton.click()
            despues = self.bajo((centro.x(), centro.y()))
            self.assertLess(max(abs(despues.x() - antes.x()), abs(despues.y() - antes.y())) * d.escala(), 1.0)

    def test_SEDI269_un_clic_con_temblor_no_deja_la_vista_manual_y_el_arrastre_empieza_pasada_la_distancia(self):
        """REQ-SIM-03: al simular, un clic en el que el ratón se mueve menos que la distancia de arrastre del sistema (el temblor
        de la mano) no mueve la vista ni la deja en manual: sigue reencajándose al refrescar y al cambiar de tamaño; pasada esa
        distancia es un arrastre de la vista, que ya no se reencaja sola."""
        d = self.d
        vp = d.viewport()
        umbral = QApplication.startDragDistance()
        self.assertGreater(umbral, 3)
        fit, esquina = d.escala(), d._a_escena(QPointF(0, 0))
        barras = (d.horizontalScrollBar().value(), d.verticalScrollBar().value())
        for dx, dy in ((1, 0), (0, 1), (1, 1), (umbral - 1, 0), (0, -(umbral - 1)), (-(umbral // 2), umbral // 2 - 1)):
            QTest.mousePress(vp, Qt.MouseButton.LeftButton, pos=QPoint(400, 300))
            QTest.mouseMove(vp, QPoint(400 + dx, 300 + dy))
            QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, pos=QPoint(400 + dx, 300 + dy))
            self.assertFalse(d._manual, f"temblor de ({dx}, {dy}) px: no es un arrastre")
            self.assertEqual((d.horizontalScrollBar().value(), d.verticalScrollBar().value()), barras, "la vista no se mueve")
            self.assertEqual(d.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertEqual((d.escala(), d._a_escena(QPointF(0, 0))), (fit, esquina))
        d.resize(800, 600)  # y se sigue reencajando con la ventana
        self.app.processEvents()
        self.assertNotEqual(d.escala(), fit)
        self.assertTrue(self.visible().contains(self.contenido()))
        d.resize(900, 650)
        self.app.processEvents()
        # un arrastre de verdad (pasada la distancia, en varios pasos del ratón) deja la vista manual
        QTest.mousePress(vp, Qt.MouseButton.LeftButton, pos=QPoint(400, 300))
        QTest.mouseMove(vp, QPoint(402, 300))
        self.assertFalse(d._manual, "dos píxeles aún no son un arrastre")
        QTest.mouseMove(vp, QPoint(400 + umbral, 300))
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, pos=QPoint(400 + umbral, 300))
        self.assertTrue(d._manual, "justo en la distancia de arrastre empieza")
        self.assertEqual(d.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # mover el ratón sin pulsar (para ver la información de una etapa) nunca cambia el modo
        d.b_ajustar.click()
        self.assertFalse(d._manual)
        QTest.mouseMove(vp, QPoint(200, 200))
        QTest.mouseMove(vp, QPoint(260, 240))
        self.assertFalse(d._manual)

    def test_SEDI271_centrar_todo_dice_su_atajo_y_el_doble_clic_de_la_simulacion(self):
        """REQ-SIM-03, REQ-EDT-02: la ayuda del botón «Centrar todo» cita Ctrl+0 y, al simular, el doble clic (que también
        centra); al editar, el doble clic es del editor."""
        d = self.d
        ayuda = d.b_ajustar.toolTip()
        self.assertIn("Ctrl+0", ayuda)
        self.assertIn("doble clic", ayuda)
        self.assertIn("simulación", ayuda)
        self.rueda((450, 325), 120)
        self.assertTrue(d._manual)
        QTest.mouseDClick(d.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(300, 300))
        self.assertFalse(d._manual, "lo que dice la ayuda: el doble clic al simular centra")

    def test_SEDI289_encuadrar_encaja_y_centra_un_rectangulo_con_margen_y_el_tope_de_centrar_todo(self):
        """REQ-EDT-08, REQ-JER-07, REQ-SIM-03: `encuadrar(r)` encaja y centra en la vista el rectángulo de escena `r` con el mismo
        margen que «Centrar todo» y sin ampliar más de su tope (1,6), y deja el zoom manual (la vista no se reencaja sola) aunque
        se simule; «Centrar todo» sigue encajando todo."""
        d = self.d
        self.assertFalse(d._manual)
        c = self.contenido()
        r = QRectF(c.left() + 20, c.top() + 100, 400, 600)
        d.encuadrar(r)
        self.app.processEvents()
        vis = self.visible()
        self.assertTrue(d._manual, "queda manual")
        self.assertTrue(vis.contains(r))
        self.assertAlmostEqual(vis.center().x(), r.center().x(), delta=1.0 / d.escala())
        self.assertAlmostEqual(vis.center().y(), r.center().y(), delta=1.0 / d.escala())
        margen = min(r.left() - vis.left(), vis.right() - r.right(), r.top() - vis.top(), vis.bottom() - r.bottom())
        self.assertGreaterEqual(margen * d.escala(), dg.MARGEN_AJUSTE - 2, "con un margen libre alrededor")
        self.assertLess(d.escala(), dg.ZOOM_AJUSTE_MAX)
        k = d.escala()
        d.mostrar(self.v.model, self.v.state())  # un refresco no mueve lo que se ve
        self.assertEqual(d.escala(), k)
        # una caja pequeña no se amplía más del tope de «Centrar todo»
        d.encuadrar(QRectF(c.left() + 10, c.top() + 10, 30, 30))
        self.assertAlmostEqual(d.escala(), dg.ZOOM_AJUSTE_MAX, places=6)
        # y «Centrar todo» sigue encajando todo lo dibujado
        d.b_ajustar.click()
        self.app.processEvents()
        self.assertFalse(d._manual)
        self.assertTrue(self.visible().contains(self.contenido()))


def ejemplo(clave):
    """La vista de uno de los ejemplos de la aplicación («macroetapa», «encapsulacion»…)."""
    from grafcet.examples import EJEMPLOS
    m, layout = EJEMPLOS[clave][2]()
    return vista(m.doc, layout)


def rayas(sc):
    """Los trazos discontinuos grises (las dependencias) que hay en la escena."""
    return [it for it in sc.items() if isinstance(it, QGraphicsLineItem) and it.pen().style() == Qt.PenStyle.CustomDashLine
            and it.pen().color().name() == dg.COL["muted"]]


def dibujo_con(v, dependencias, sel=None):
    sc = QGraphicsScene()
    cajas = dg.dibujar(sc, v.model, v.state(), sel, dependencias=dependencias)
    return sc, cajas


@unittest.skipUnless(QT, "requiere PySide6")
class Dependencias(unittest.TestCase):
    """Encargo C2, punto 2: los trazos discontinuos de la macroetapa a su expansión y de la encapsulante a sus recintos solo
    se dibujan con la opción `dependencias` («Mostrar dependencias»), en Qt y en el banco web."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SEDI286_por_defecto_no_hay_trazos_de_dependencia_y_con_la_opcion_aparecen_los_de_macroetapa_y_encapsulante(self):
        """REQ-JER-04, REQ-JER-05, REQ-EDT-02: sin la opción (por defecto) no se dibuja ningún trazo discontinuo de dependencia;
        con ella, la macroetapa se une a su entrada y a su salida (dos trazos) y la encapsulante al marco de su recinto (uno,
        desde su centro hasta el punto más cercano del borde del marco); un parcial con una orden de forzado no lleva ninguno."""
        v = ejemplo("macroetapa")
        sc, _ = dibujo(v)
        self.assertEqual(rayas(sc), [], "por defecto, sin dependencias")
        sc, _ = dibujo_con(v, False)
        self.assertEqual(rayas(sc), [])
        sc, _ = dibujo_con(v, True)
        pos = dg.posiciones(v.model)
        (m,) = v.model["macros"]
        esperado = sorted([(pos[m["id"]][0] + dg.H, pos[m["id"]][1] - dg.H, pos[m["entry"]][0] - dg.H, pos[m["entry"]][1] - dg.H),
                           (pos[m["id"]][0] + dg.H, pos[m["id"]][1] + dg.H, pos[m["exit"]][0] - dg.H, pos[m["exit"]][1] + dg.H)])
        self.assertEqual(sorted((r.line().x1(), r.line().y1(), r.line().x2(), r.line().y2()) for r in rayas(sc)), esperado,
                         "de la macroetapa a su entrada y a su salida")
        v = ejemplo("encapsulacion")
        self.assertEqual(rayas(dibujo(v)[0]), [])
        sc, _ = dibujo_con(v, True)
        (r,) = rayas(sc)
        pos, marco = dg.posiciones(v.model), dg.cajas_parciales(v.model)["R"]
        enc = next(p["ownerStep"] for p in v.model["partials"] if p["id"] == "R")
        self.assertEqual((r.line().x1(), r.line().y1()), pos[enc], "sale del centro de la encapsulante")
        x2, y2 = r.line().x2(), r.line().y2()
        self.assertTrue(marco["x0"] <= x2 <= marco["x1"] and marco["y0"] <= y2 <= marco["y1"]
                        and (x2 in (marco["x0"], marco["x1"]) or y2 in (marco["y0"], marco["y1"])), "y llega al borde del marco")
        self.assertEqual(rayas(dibujo_con(ejemplo("forzado"), True)[0]), [], "una orden de forzado no lleva trazo de dependencia")

    def test_SEDI287_mostrar_u_ocultar_las_dependencias_no_cambia_la_disposicion_los_marcos_ni_la_seleccion(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05: lo único que cambia al mostrar las dependencias son sus trazos: el resto de lo
        dibujado (posiciones, tamaños, orden en z), la caja que ocupa el dibujo, los marcos de los parciales, las cajas de las
        acciones y la selección resaltada son los mismos."""
        for clave in ("macroetapa", "encapsulacion"):
            v = ejemplo(clave)
            sel = {p["id"] for p in v.model["partials"]} | {m["id"] for m in v.model["macros"]}
            sin, cajas_sin = dibujo_con(v, False, sel)
            con, cajas_con = dibujo_con(v, True, sel)
            self.assertTrue(rayas(con) and not rayas(sin), clave)

            def firma(sc):
                quitar = {id(it) for it in rayas(sc)}
                return sorted((type(it).__name__, round(it.sceneBoundingRect().x(), 2), round(it.sceneBoundingRect().y(), 2),
                               round(it.sceneBoundingRect().width(), 2), round(it.sceneBoundingRect().height(), 2), it.zValue())
                              for it in sc.items() if id(it) not in quitar)
            self.assertEqual(firma(con), firma(sin), clave)
            self.assertEqual(con.itemsBoundingRect(), sin.itemsBoundingRect(), f"{clave}: la caja del dibujo")
            self.assertEqual(cajas_con, cajas_sin, clave)
            self.assertEqual(dg.cajas_parciales(v.model), dg.cajas_parciales(v.model))
            self.assertTrue(all(it.zValue() == dg.Z_FRAME for it in rayas(con)), "bajo todo lo demás")

    def test_SEDI288_el_boton_mostrar_dependencias_de_la_vista_conmuta_repinta_y_se_recuerda(self):
        """REQ-EDT-02, REQ-SIM-03: la vista tiene el botón conmutable «Mostrar dependencias» tras los controles del zoom, apagado
        por defecto; al pulsarlo repinta con los trazos (al simular y al editar), queda marcado y se recuerda en sus ajustes, que
        lee otra vista con los mismos ajustes."""
        import tempfile
        from PySide6.QtCore import QSettings
        v = ejemplo("encapsulacion")
        with tempfile.TemporaryDirectory() as tmp:
            ini = str(Path(tmp) / "a.ini")
            d = dg.VistaDiagrama()
            d.ajustes = QSettings(ini, QSettings.Format.IniFormat)
            d.resize(900, 650)
            d.show()
            self.app.processEvents()
            d.mostrar(v.model, v.state())
            b = d.b_dependencias
            self.assertEqual((b.text(), b.isCheckable(), b.isChecked(), d.dependencias, rayas(d.scene())),
                             ("Mostrar dependencias", True, False, False, []))
            lay = d.barra.layout()
            self.assertEqual([lay.itemAt(i).widget() for i in range(lay.count())], [d.b_menos, d.l_zoom, d.b_mas, d.b_ajustar, b])
            self.assertFalse(d.ajustes.value(dg.CLAVE_DEPENDENCIAS, False, type=bool))
            b.click()
            self.assertEqual((b.isChecked(), d.dependencias, len(rayas(d.scene()))), (True, True, 1), "al simular")
            self.assertTrue(d.ajustes.value(dg.CLAVE_DEPENDENCIAS, False, type=bool))
            d.modo_edicion(True, SimpleNamespace())
            d.mostrar(v.model, v.state())
            self.assertEqual(len(rayas(d.scene())), 1, "y al editar, con el mismo estado")
            self.assertTrue(b.isChecked())
            # otra vista con los mismos ajustes arranca con él encendido y lo pinta
            d2 = dg.VistaDiagrama()
            d2.ajustes = QSettings(ini, QSettings.Format.IniFormat)
            d2.mostrar(v.model, v.state())
            self.assertEqual((d2.dependencias, d2.b_dependencias.isChecked(), len(rayas(d2.scene()))), (True, True, 1))
            b.click()
            self.assertEqual((b.isChecked(), d.dependencias, rayas(d.scene())), (False, False, []))
            self.assertFalse(d.ajustes.value(dg.CLAVE_DEPENDENCIAS, False, type=bool))
            d3 = dg.VistaDiagrama()  # sin ajustes ni ventana, no recuerda nada pero funciona
            d3.mostrar(v.model, v.state())
            d3.b_dependencias.click()
            self.assertEqual(len(rayas(d3.scene())), 1)
            for vista_ in (d, d2, d3):
                vista_.close()
                vista_.deleteLater()

    def test_SEDI296_dibujo_js_acepta_la_misma_opcion_apagada_por_defecto_y_calcula_igual_el_punto_del_marco(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05: tools/dibujo.js y escritorio/diagrama.py tienen la misma opción, `dependencias`,
        apagada por defecto, para los mismos trazos (macroetapa-expansión y encapsulante-recinto), y calculan igual el punto del
        marco al que llega el de la encapsulante; el banco no necesita botón."""
        import inspect
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        self.assertIn("function drawDiagram(svg, M, S, opciones = {})", js)
        self.assertIn("const dependencias = !!opciones.dependencias;", js)
        self.assertIn("drawFrames(frames, M, pos, dependencias);", js)
        self.assertIn("function drawFrames(g, M, pos, dependencias)", js)
        self.assertIn("if (!dependencias || !m || !pos[m.entry] || !pos[m.exit]) return;", js, "los trazos de la expansión")
        self.assertIn("if (dependencias && pos[pt.ownerStep])", js, "el de la encapsulante")
        self.assertEqual(js.count("class:\"expline\""), 2, "los dos son el mismo trazo discontinuo gris")
        for html_ in ("banco_de_pruebas.html", "comparador.html"):
            self.assertNotIn("dependencias", (ROOT / "tools" / html_).read_text(encoding="utf-8"), "sin botón: se ven apagadas")
        param = inspect.signature(dg.dibujar).parameters["dependencias"]
        self.assertEqual(param.default, False)
        self.assertEqual(inspect.signature(dg.imagen).parameters["dependencias"].default, False)
        # el mismo cálculo del punto del marco: fuera (al rectángulo más próximo) y dentro (al borde más cercano)
        for cuenta in ("Math.min(Math.max(x, b.x0), b.x1)", "Math.min(Math.max(y, b.y0), b.y1)",
                       "[[b.x0, y], [b.x1, y], [x, b.y0], [x, b.y1]][d.indexOf(Math.min(...d))]"):
            self.assertIn(cuenta, js)
        b = {"x0": 100.0, "x1": 300.0, "y0": 50.0, "y1": 150.0}
        for (x, y), esperado in {(20, 80): (100, 80), (400, 80): (300, 80), (200, 0): (200, 50), (200, 400): (200, 150),
                                 (0, 0): (100, 50), (500, 500): (300, 150), (110, 100): (100, 100), (200, 60): (200, 50)}.items():
            self.assertEqual(dg._punto_del_marco(b, x, y), esperado, (x, y))


@unittest.skipUnless(QT, "requiere PySide6")
class NombreDeLaEncapsulante(unittest.TestCase):
    """Encargo C3, punto 6: el nombre de la encapsulante, centrado sobre el marco de su recinto, queda entero por encima del
    trazo (ni lo corta la línea ni hace falta un fondo que la interrumpa), igual en Qt y en el banco web."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def nombre_y_marco(v, sc):
        """El texto con el nombre de la encapsulante del recinto «R» de «encapsulacion» (el centrado sobre su marco) y su marco."""
        marco = dg.cajas_parciales(v.model)["R"]
        enc = next(p["ownerStep"] for p in v.model["partials"] if p["id"] == "R")
        nombre, cx = v.model["names"][enc], (marco["x0"] + marco["x1"]) / 2
        return [it for it in sc.items() if isinstance(it, QGraphicsTextItem) and it.toPlainText() == nombre
                and abs(it.sceneBoundingRect().center().x() - cx) < 1], marco

    def test_SEDI274_el_nombre_de_la_encapsulante_va_entero_por_encima_del_trazo_superior_de_su_recinto(self):
        """REQ-JER-05, REQ-EDT-02: el nombre de la encapsulante se escribe centrado sobre el marco de su recinto, con su línea
        base ENCIMA_MARCO por encima del trazo: entero por encima de él, sin que la línea lo corte ni un fondo del color del
        lienzo la interrumpa; el nombre del recinto, debajo, sigue a caballo del trazo de abajo con su fondo."""
        from PySide6.QtGui import QColor, QFontMetricsF
        v = ejemplo("encapsulacion")
        sc, _ = dibujo(v)
        (nombre,), marco = self.nombre_y_marco(v, sc)
        r, y0 = nombre.sceneBoundingRect(), marco["y0"]
        self.assertAlmostEqual(r.top() + QFontMetricsF(nombre.font()).ascent(), y0 - dg.ENCIMA_MARCO, places=1, msg="línea base")
        self.assertLess(r.bottom(), y0 - 0.8, "todo el texto, descendentes incluidos, queda por encima del trazo (de 1,6)")
        self.assertLess(r.top(), y0 - 10)
        trazo = QRectF(marco["x0"], y0 - 0.8, marco["x1"] - marco["x0"], 1.6)
        fondos = [it for it in sc.items() if hasattr(it, "brush") and it.brush().style() == Qt.BrushStyle.SolidPattern
                  and it.brush().color() == QColor(dg.COL["panel"]) and it.sceneBoundingRect().intersects(trazo)]
        self.assertEqual(fondos, [], "ningún fondo del color del lienzo corta el trazo de arriba")
        rb = texto(sc, "R").sceneBoundingRect()
        self.assertTrue(rb.top() < marco["y1"] < rb.bottom(), "el nombre del recinto sigue sobre el trazo de abajo")

    def test_SEDI275_dibujo_js_coloca_el_nombre_de_la_encapsulante_igual_que_escritorio(self):
        """REQ-JER-05, REQ-EDT-02: tools/dibujo.js sube la línea base del nombre de la encapsulante el mismo ENCIMA_MARCO que
        escritorio/diagrama.py y deja el nombre del recinto a caballo del trazo de abajo, como antes."""
        import inspect
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        self.assertEqual(int(re.search(r"const ENCIMA_MARCO = (\d+);", js).group(1)), dg.ENCIMA_MARCO)
        self.assertIn("txt(g, (b.x0 + b.x1) / 2, b.y0 - ENCIMA_MARCO, nameOf(M, pt.ownerStep)", js)
        self.assertNotIn("b.y0 + 5", js)
        self.assertIn("txt(g, b.x0 + 30, b.y1 + 5, pt.label", js)
        marcos = inspect.getsource(dg._marcos)
        self.assertIn('b["y0"] - ENCIMA_MARCO', marcos)
        self.assertNotIn('b["y0"] + 5', marcos)
        self.assertIn('b["y1"] + 5', marcos)

    def test_SEDI276_centrar_todo_deja_a_la_vista_el_nombre_y_el_marco_no_depende_de_el(self):
        """REQ-EDT-02: el nombre sobresale del marco, así que la caja del dibujo lo incluye y «Centrar todo» lo deja a la vista;
        la disposición del modelo no cambia: el marco sigue midiendo lo mismo en torno a sus etapas."""
        v = ejemplo("encapsulacion")
        d = dg.VistaDiagrama()
        try:
            d.resize(900, 650)
            d.show()
            self.app.processEvents()
            d.mostrar(v.model, v.state())
            d.ajustar()
            self.app.processEvents()
            (nombre,), marco = self.nombre_y_marco(v, d.scene())
            r = nombre.sceneBoundingRect()
            self.assertTrue(d.scene().itemsBoundingRect().contains(r), "la caja del dibujo incluye el nombre")
            self.assertTrue(d.mapToScene(d.viewport().rect()).boundingRect().contains(r), "y «Centrar todo» lo deja a la vista")
            pos = dg.posiciones(v.model)
            propias = [pos[s["id"]] for s in v.model["steps"] if s.get("partial") == "R"]
            self.assertEqual((marco["y0"], marco["y1"]), (min(y for _, y in propias) - dg.H - 22, max(y for _, y in propias) + dg.H + 22))
        finally:
            d.close()
            d.deleteLater()


if __name__ == "__main__":
    unittest.main()
