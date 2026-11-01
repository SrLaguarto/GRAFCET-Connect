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
    from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsScene, QGraphicsTextItem
    from escritorio import diagrama as dg
    QT = True
except ImportError:  # el núcleo no depende de Qt
    QT = False
try:
    from PySide6.QtQml import QJSEngine  # para ejecutar tools/dibujo.js con un DOM de mentira
    QJS = QT
except ImportError:
    QJS = False


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


def trazos_macro(pos, m):
    x, y = pos[m["id"]]
    lado = (pos[m["entry"]][0] + pos[m["exit"]][0]) / 2 - x
    out = []
    for k, vertical in (("entry", -dg.H), ("exit", dg.H)):
        u, v = pos[m[k]]
        if lado:
            horizontal = dg.H if lado > 0 else -dg.H
            out.append((x+horizontal, y+vertical, u-horizontal, v+vertical))
        else:
            t = dg.H / max(abs(u-x), abs(v-y))
            out.append((x+(u-x)*t, y+(v-y)*t, u-(u-x)*t, v-(v-y)*t))
    return sorted(out)


@unittest.skipUnless(QT, "requiere PySide6")
class Negado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SEDI200_la_barra_del_negado_es_una_linea_de_1_25_px_sobre_la_palabra(self):
        """REQ-EDT-02: la barra de una variable negada es una línea propia de 1,25 px (el sobrerrayado del texto es de 1 px y
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
        self.assertEqual(barra.pen().widthF(), 1.25)
        self.assertEqual(barra.pen().color().name(), dg.COL["true_text"], "NOT paro es verdadero: texto y barra resaltados")
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
        """REQ-EDT-02: el banco web (tools/dibujo.js y dibujo.css) pinta la barra del negado como una línea propia de 1,25 px,
        igual que Qt, y no usa el sobrerrayado del texto."""
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        css = (ROOT / "tools" / "dibujo.css").read_text(encoding="utf-8")
        self.assertEqual(int(re.search(r"const GROSOR_NEGADO = (\d+)", js).group(1)), int(dg.GROSOR_NEGADO))
        self.assertNotIn("text-decoration", js)
        self.assertIn('class:verde ? "neg verdadero" : "neg"', js)
        self.assertRegex(css, r"\.neg\{[^}]*stroke-width:1\.25[;}]")
        self.assertEqual(int(re.search(r"const TMR_EXTRA = (\d+)", js).group(1)), dg.TMR_EXTRA)


class Temporizador(unittest.TestCase):
    def test_SEDI204_el_estado_del_temporizador_es_solo_lo_transcurrido(self):
        """REQ-SIM-03, REQ-TMP-01: antes de empezar no hay nada que mostrar; mientras cuenta, solo el tiempo transcurrido
        («1 s», sin el preset); al vencer, «3,00 s ✓». Cada temporizador dice qué duración del texto es la suya (`token`,
        `nth`); la tabla de temporizadores conserva «lleva» y «preset»."""
        m, lay = modelo_temporizado()
        v = vista(m, lay)
        self.assertEqual({(t["estado"], t["shown"]) for t in v.state()["temporal"].values()}, {("parado", "")})
        v = corriendo(m, lay)
        por_token = {t["token"]: t for t in v.state()["temporal"].values()}
        t2, z = por_token["3s"], por_token["2s"]
        self.assertEqual((t2["estado"], t2["shown"], t2["lleva"], t2["preset"], t2["nth"]),
                         ("contando", "1,00 s", "1 s", "3 s", 0))
        self.assertEqual((z["estado"], z["shown"], z["lleva"], z["preset"]), ("contando", "0,50 s", "0,5 s", "2 s"))
        v.act("avanzar", {"us": 2_000_000})  # t2 vence a los 3 s (ok es 0: no franquea); z, a los 2,5 s de q
        por_token = {t["token"]: t for t in v.state()["temporal"].values()}
        self.assertEqual([(t["estado"], t["shown"]) for t in (por_token["3s"], por_token["2s"])],
                         [("vencido", "3,00 s ✓"), ("vencido", "2,00 s ✓")])

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

    def test_SEDI207_el_tiempo_transcurrido_va_alineado_encima_de_la_duracion(self):
        """REQ-SIM-03, REQ-TMP-01: en la receptividad «ok·3s/XB» el «1,00 s» se alinea con el inicio del «3s», justo
        sobre la línea de arriba del texto; al vencer, «3,00 s ✓» en el mismo sitio y en otro color; antes de empezar, nada."""
        m, lay = modelo_temporizado()
        v = corriendo(m, lay)
        sc, _ = dibujo(v)
        cond = texto(sc, "ok·3s/XB")
        etiqueta = texto(sc, "1,00 s")
        segs = v.model["transitions"][1]["cond"]
        lim = dg._Pintor.limites(segs, 14)
        i = [s["t"] for s in segs].index("3s")
        inicio = cond.pos().x() + lim[i]
        r = etiqueta.sceneBoundingRect()
        self.assertAlmostEqual(r.left(), inicio, delta=.01)
        base = r.top() + dg._Pintor.ascenso(dg.TMR_TAM)
        self.assertTrue(0 < cond.pos().y() - base <= 4)
        self.assertGreater(inicio, cond.pos().x() + 10, "se localiza midiendo el token")
        self.assertEqual(etiqueta.font().pixelSize(), 10)
        self.assertEqual(etiqueta.defaultTextColor().name(), dg.COL["readout"])
        # Antes de empezar no hay nada; al vencer, «3,00 s ✓» en el mismo sitio y de otro color
        sc0, _ = dibujo(vista(m, lay))
        colores = {dg.COL["accent"], dg.COL["true_text"]}
        self.assertEqual([it.toPlainText() for it in textos(sc0) if re.fullmatch(r"\d+,\d{2} s(?: ✓)?", it.toPlainText())], [])
        v.act("avanzar", {"us": 2_000_000})
        sc1, _ = dibujo(v)
        hecho = texto(sc1, "3,00 s ✓")
        self.assertEqual(hecho.defaultTextColor().name(), dg.COL["readout"])
        self.assertAlmostEqual(hecho.pos().x(), inicio, delta=1.0)

    def test_SEDI208_si_no_se_localiza_la_duracion_se_alinea_con_toda_la_receptividad(self):
        """REQ-SIM-03: un temporizador cuya duración no está en el texto (token desconocido) se alinea al inicio de toda la
        receptividad como alternativa de presentación."""
        m, lay = modelo_temporizado()
        v = corriendo(m, lay)
        S = v.state()
        for t in S["temporal"].values():
            t["token"] = "9s"
        sc, _ = dibujo(v, S)
        cond, etiqueta = texto(sc, "ok·3s/XB"), texto(sc, "1,00 s")
        self.assertAlmostEqual(etiqueta.pos().x(), cond.pos().x(), delta=.01)

    def test_SEDI209_el_tiempo_transcurrido_no_pisa_la_barra_de_la_transicion_ni_el_texto(self):
        """REQ-SIM-03: el tiempo transcurrido de una receptividad no toca el trazo de la transición, ni su designación, ni el
        texto de la receptividad; con comentario, éste empieza después."""
        m, lay = modelo_temporizado()
        v = corriendo(m, lay, comments={"t2": "se espera"})
        sc, _ = dibujo(v)
        r = texto(sc, "1,00 s").sceneBoundingRect()
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
        el tiempo transcurrido va alineado al inicio de la duración del texto, por encima de la marca."""
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
            inicio = cond.pos().x() + lim[i]
            etiqueta = next(it for it in textos(sc) if it.toPlainText() == "0,50 s"
                            and abs(it.pos().x() - inicio) < .01)
            base = etiqueta.pos().y() + dg._Pintor.ascenso(dg.TMR_TAM)
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
        r = texto(sc, "0,50 s").sceneBoundingRect()
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
        reserva = d.barra.height() / d.escala()  # arriba se deja, además, el alto del recuadro de los controles del zoom
        self.assertAlmostEqual(vis.center().x(), c.center().x(), delta=1.0 / d.escala())
        self.assertAlmostEqual(vis.center().y() + reserva / 2, c.center().y(), delta=1.0 / d.escala())
        izq = (c.left() - vis.left()) * d.escala()
        arriba = (c.top() - vis.top()) * d.escala()
        self.assertGreaterEqual(min(izq, arriba), dg.MARGEN_AJUSTE - 2, "con un margen libre alrededor")
        self.assertGreaterEqual(arriba, dg.MARGEN_AJUSTE + d.barra.height() - 2, "y, arriba, el recuadro del zoom de más")
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
        reserva = d.barra.height() / d.escala()
        self.assertAlmostEqual(vis.center().x(), c.center().x(), delta=1.0 / d.escala())
        self.assertAlmostEqual(vis.center().y() + reserva / 2, c.center().y(), delta=1.0 / d.escala())
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

    def espia(self):
        """Un controlador de edición que solo anota lo que le llega del ratón."""
        llamadas = []

        class Espia:
            sel: list = []

            def __getattr__(self, nombre):
                if nombre in ("prensar", "mover", "soltar", "doble"):
                    return lambda p, event=None: llamadas.append((nombre, p)) or False
                raise AttributeError(nombre)
        return Espia(), llamadas

    def pulsar_central(self, pos):
        QTest.mousePress(self.d.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(*pos))

    def test_SEDI321_con_el_boton_central_arrastrar_desplaza_el_dibujo_agarrando_el_punto_al_simular(self):
        """REQ-SIM-03, REQ-EDT-02: al simular, con el botón central (la rueda) pulsado, arrastrar desplaza el dibujo como si se
        agarrara ese punto (el punto pulsado sigue bajo el puntero, a menos de 1 px) y deja la vista en zoom manual."""
        d = self.d
        self.assertFalse(d._manual)
        agarrado = self.bajo((400, 300))
        self.pulsar_central((400, 300))
        self.assertTrue(d._manual, "empezar ya es mover la vista a mano")
        self.assertEqual(d.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        for destino in ((380, 280), (330, 250), (460, 340)):
            QTest.mouseMove(d.viewport(), QPoint(*destino))
            ahora = d.mapToScene(QPoint(*destino))
            self.assertLess(max(abs(ahora.x() - agarrado.x()), abs(ahora.y() - agarrado.y())) * d.escala(), 1.5, destino)
        QTest.mouseRelease(d.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(460, 340))
        k = d.escala()
        d.mostrar(self.v.model, self.v.state())  # un refresco no la reencaja
        self.assertEqual((d._manual, d.escala()), (True, k))
        despues = d.mapToScene(QPoint(460, 340))
        self.assertLess(max(abs(despues.x() - agarrado.x()), abs(despues.y() - agarrado.y())) * k, 1.5)
        # soltado el botón, mover el ratón ya no desplaza nada
        QTest.mouseMove(d.viewport(), QPoint(200, 200))
        self.assertLess(abs(d.mapToScene(QPoint(460, 340)).x() - agarrado.x()) * k, 1.5)
        # el botón izquierdo sigue arrastrando la vista con la mano, y la rueda sigue haciendo zoom
        self.rueda((450, 325), 120)
        self.assertGreater(d.escala(), k)

    def test_SEDI322_con_el_boton_central_al_editar_no_selecciona_ni_edita_nada_y_el_izquierdo_sigue_igual(self):
        """REQ-EDT-02, REQ-EDT-05: al editar, el botón central desplaza el dibujo (zoom manual) sin que el editor se entere: no
        llegan al controlador ni la pulsación, ni los movimientos, ni la suelta, ni el doble clic; el botón izquierdo sigue llegando."""
        d = self.d
        ctrl, llamadas = self.espia()
        d.modo_edicion(True, ctrl)
        d.mostrar(self.v.model, self.v.state())
        self.app.processEvents()
        agarrado = self.bajo((300, 250))
        self.pulsar_central((300, 250))
        QTest.mouseMove(d.viewport(), QPoint(260, 200))
        QTest.mouseMove(d.viewport(), QPoint(240, 150))
        QTest.mouseRelease(d.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(240, 150))
        QTest.mouseDClick(d.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(240, 150))
        self.assertEqual(llamadas, [], "el editor no se entera")
        self.assertTrue(d._manual)
        ahora = d.mapToScene(QPoint(240, 150))
        self.assertLess(max(abs(ahora.x() - agarrado.x()), abs(ahora.y() - agarrado.y())) * d.escala(), 1.5)
        self.assertEqual(d.viewport().cursor().shape(), Qt.CursorShape.CrossCursor, "el cursor de edición vuelve")
        QTest.mousePress(d.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(300, 250))
        QTest.mouseRelease(d.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(300, 250))
        self.assertEqual([n for n, _ in llamadas], ["prensar", "soltar"], "el botón izquierdo sigue llegando al editor")

    def test_SEDI323_centrar_seleccion_encuadra_lo_seleccionado_y_sin_seleccion_no_hace_nada(self):
        """REQ-EDT-02, REQ-SIM-03: junto a «Centrar todo» hay «Centrar selección» (con su ayuda): al editar, encuadra con `encuadrar`
        la caja de lo seleccionado (y sus acciones) con el margen y el tope de zoom de siempre, y deja el zoom manual; sin
        selección, o al simular, está desactivado y no hace nada."""
        from escritorio.edicion import Edicion
        from PySide6.QtWidgets import QToolButton
        d = self.d
        lay = d.barra.layout()
        self.assertEqual([lay.itemAt(i).widget() for i in range(lay.count())],
                         [d.b_menos, d.l_zoom, d.b_mas, d.b_ajustar, d.b_seleccion])
        self.assertIsInstance(d.b_seleccion, QToolButton)
        self.assertEqual(d.b_seleccion.text(), "Centrar selección")
        self.assertIn("seleccionado", d.b_seleccion.toolTip())
        self.assertFalse(d.b_seleccion.isEnabled(), "al simular no hay selección")
        k = d.escala()
        d.centrar_seleccion()
        d.b_seleccion.click()
        self.assertEqual((d.escala(), d._manual), (k, False), "sin efecto")
        # al editar, con una edición de verdad
        e = Edicion.nuevo()
        e.diagrama = d
        d.modo_edicion(True, e)
        e.cambiado.connect(lambda: d.mostrar(e.M, {}, e.seleccion_dibujo(), set(), set()))
        e.poner_etapa(QPointF(160, 60))
        lejos = e.poner_etapa(QPointF(1400, 900))
        e.nueva_variable("Q00", "output")
        e.pedir_accion = lambda sid, aid: None
        self.assertIsNone(e.poner_accion(lejos, {"tipo": "continua", "variable": "Q00"}))
        otra = e.poner_etapa(QPointF(300, 700))
        e.seleccionar([])
        self.app.processEvents()
        d.ajustar()
        self.assertFalse(d.b_seleccion.isEnabled(), "sin nada seleccionado")
        k = d.escala()
        esquina = d._a_escena(QPointF(0, 0))
        d.b_seleccion.click()
        self.assertEqual((d.escala(), d._a_escena(QPointF(0, 0))), (k, esquina), "sin efecto")
        # una etapa lejana, con su acción: se encuadra todo ello
        e.seleccionar([lejos])
        self.assertTrue(d.b_seleccion.isEnabled())
        caja = e.caja_seleccion()
        accion = next(c for c in d.cajas_acciones if c["etapa"] == lejos)["rect"]
        self.assertTrue(caja.contains(QRectF(*accion)), "con la caja de su acción")
        self.assertTrue(caja.contains(e.centro(lejos)))
        d.b_seleccion.click()
        self.app.processEvents()
        vis = self.visible()
        self.assertTrue(vis.contains(caja))
        self.assertAlmostEqual(vis.center().x(), caja.center().x(), delta=1.5 / d.escala())
        self.assertAlmostEqual(vis.center().y(), caja.center().y(), delta=1.5 / d.escala())
        self.assertLessEqual(d.escala(), dg.ZOOM_AJUSTE_MAX + 1e-9)
        self.assertTrue(d._manual)
        # varias a la vez: caben las dos, con el margen
        e.seleccionar([lejos, otra])
        d.b_seleccion.click()
        self.app.processEvents()
        vis, dos = self.visible(), e.caja_seleccion()
        self.assertTrue(vis.contains(dos))
        self.assertTrue(vis.contains(e.centro(lejos)) and vis.contains(e.centro(otra)))
        self.assertGreaterEqual(min(dos.left() - vis.left(), vis.right() - dos.right(), dos.top() - vis.top(),
                                    vis.bottom() - dos.bottom()) * d.escala(), dg.MARGEN_AJUSTE - 2)
        # lo que no tiene caja (nada dibujado) se ignora
        e.sel = ["no-existe"]
        self.assertIsNone(e.caja_seleccion())
        d.mostrar(e.M, {}, set(), set(), set())
        self.assertFalse(d.b_seleccion.isEnabled())
        # al volver a simular, se desactiva
        d.modo_edicion(False)
        self.assertFalse(d.b_seleccion.isEnabled())

    def test_SEDI324_centrar_todo_deja_arriba_el_alto_del_recuadro_del_zoom_de_mas_y_no_lo_tapa(self):
        """REQ-SIM-03, REQ-EDT-02: «Centrar todo» deja arriba, además del margen de siempre, el alto del recuadro de los controles del
        zoom (que está encima del dibujo): ninguna parte de lo dibujado queda bajo ese recuadro, al simular y al editar; el zoom se
        calcula con lo que queda de alto, así que el dibujo sigue entero a la vista."""
        d = self.d
        for modo in ("simular", "editar"):
            if modo == "editar":
                d.modo_edicion(True, SimpleNamespace())
                d.mostrar(self.v.model, self.v.state())
            d.b_ajustar.click()
            self.app.processEvents()
            c = self.contenido()
            en_vista = d.mapFromScene(c).boundingRect()
            recuadro = d.barra.geometry()
            self.assertGreaterEqual(en_vista.top(), d.barra.height() + dg.MARGEN_AJUSTE - 2, modo)
            self.assertFalse(QRect(en_vista).intersects(recuadro), f"{modo}: el recuadro del zoom no tapa el dibujo")
            self.assertTrue(self.visible().contains(c), modo)
            self.assertGreaterEqual(d.viewport().height() - en_vista.bottom(), dg.MARGEN_AJUSTE - 2, f"{modo}: y abajo, el margen de siempre")


def ejemplo(clave):
    """La vista de uno de los ejemplos de la aplicación («macroetapa», «encapsulacion»…)."""
    from grafcet.examples import EJEMPLOS
    m, layout = EJEMPLOS[clave][2]()
    return vista(m.doc, layout)


def rayas(sc):
    """Los trazos discontinuos grises (las dependencias) que hay en la escena."""
    return [it for it in sc.items() if isinstance(it, QGraphicsLineItem) and it.pen().style() == Qt.PenStyle.CustomDashLine
            and it.pen().color().name() in (dg.COL["muted"], dg.COL["active"])]


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
        con ella, la macroetapa se une a su entrada y a su salida (dos trazos) y la encapsulante a su recinto (otros dos, uno a
        cada esquina del lado del marco que mira hacia ella, saliendo del contorno de la etapa); un parcial con una orden de
        forzado no lleva ninguno."""
        v = ejemplo("macroetapa")
        sc, _ = dibujo(v)
        self.assertEqual(rayas(sc), [], "por defecto, sin dependencias")
        sc, _ = dibujo_con(v, False)
        self.assertEqual(rayas(sc), [])
        sc, _ = dibujo_con(v, True)
        pos = dg.posiciones(v.model)
        (m,) = v.model["macros"]
        esperado = trazos_macro(pos, m)
        self.assertEqual(sorted((r.line().x1(), r.line().y1(), r.line().x2(), r.line().y2()) for r in rayas(sc)), esperado,
                         "de la macroetapa a su entrada y a su salida")
        v = ejemplo("encapsulacion")
        self.assertEqual(rayas(dibujo(v)[0]), [])
        sc, _ = dibujo_con(v, True)
        trazos = rayas(sc)
        self.assertEqual(len(trazos), 2, "dos trazos hacia el recinto")
        pos, marco = dg.posiciones(v.model), dg.cajas_parciales(v.model)["R"]
        enc = next(p["ownerStep"] for p in v.model["partials"] if p["id"] == "R")
        esquinas = {(marco[a], marco[b]) for a in ("x0", "x1") for b in ("y0", "y1")}
        llegan = {(t.line().x2(), t.line().y2()) for t in trazos}
        self.assertTrue(len(llegan) == 2 and llegan <= esquinas, "cada uno llega a una esquina distinta del marco")
        self.assertEqual({x for x, _ in llegan}, {marco["x0"]}, "las dos del lado que mira a la encapsulante: el recinto está a su derecha")
        ex, ey = pos[enc]
        for t in trazos:  # salen del contorno de la etapa (la del ejemplo es inicial: su cuadrado exterior)
            self.assertEqual((abs(t.line().x1() - ex), abs(t.line().y1() - ey)), (dg.H, dg.H), "de una esquina de la encapsulante")
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
            self.assertEqual([lay.itemAt(i).widget() for i in range(lay.count())],
                             [d.b_menos, d.l_zoom, d.b_mas, d.b_ajustar, d.b_seleccion])
            self.assertFalse(d.ajustes.value(dg.CLAVE_DEPENDENCIAS, False, type=bool))
            b.click()
            self.assertEqual((b.isChecked(), d.dependencias, len(rayas(d.scene()))), (True, True, 2), "al simular")
            self.assertTrue(d.ajustes.value(dg.CLAVE_DEPENDENCIAS, False, type=bool))
            d.modo_edicion(True, SimpleNamespace())
            d.mostrar(v.model, v.state())
            self.assertEqual(len(rayas(d.scene())), 2, "y al editar, con el mismo estado")
            self.assertTrue(b.isChecked())
            # otra vista con los mismos ajustes arranca con él encendido y lo pinta
            d2 = dg.VistaDiagrama()
            d2.ajustes = QSettings(ini, QSettings.Format.IniFormat)
            d2.mostrar(v.model, v.state())
            self.assertEqual((d2.dependencias, d2.b_dependencias.isChecked(), len(rayas(d2.scene()))), (True, True, 2))
            b.click()
            self.assertEqual((b.isChecked(), d.dependencias, rayas(d.scene())), (False, False, []))
            self.assertFalse(d.ajustes.value(dg.CLAVE_DEPENDENCIAS, False, type=bool))
            d3 = dg.VistaDiagrama()  # sin ajustes ni ventana, no recuerda nada pero funciona
            d3.mostrar(v.model, v.state())
            d3.b_dependencias.click()
            self.assertEqual(len(rayas(d3.scene())), 2)
            for vista_ in (d, d2, d3):
                vista_.close()
                vista_.deleteLater()

    def test_SEDI296_dibujo_js_acepta_la_misma_opcion_apagada_por_defecto_y_calcula_igual_los_trazos_del_recinto(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05: tools/dibujo.js y escritorio/diagrama.py tienen la misma opción, `dependencias`,
        apagada por defecto, para los mismos trazos (macroetapa-expansión y los dos de encapsulante-recinto), y eligen igual el
        lado del marco y las esquinas de la encapsulante de las que salen; el banco no necesita botón."""
        import inspect
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        self.assertIn("function drawDiagram(svg, M, S, opciones = {})", js)
        self.assertIn("const dependencias = !!opciones.dependencias;", js)
        self.assertIn("drawFrames(frames, M, pos, dependencias, geo, roles);", js)
        self.assertIn("function drawFrames(g, M, pos, dependencias, geo, roles={})", js)
        self.assertIn("if (!dependencias || !m || !pos[m.entry] || !pos[m.exit]) return;", js, "los trazos de la expansión")
        self.assertIn("if (dependencias && pos[pt.ownerStep])", js, "los de la encapsulante")
        self.assertEqual(js.count('class:"expline "'), 2, "todos son trazos de dependencia, con color según actividad")
        for html_ in ("banco_de_pruebas.html", "comparador.html"):
            self.assertNotIn("dependencias", (ROOT / "tools" / html_).read_text(encoding="utf-8"), "sin botón: se ven apagadas")
        param = inspect.signature(dg.dibujar).parameters["dependencias"]
        self.assertEqual(param.default, False)
        self.assertEqual(inspect.signature(dg.imagen).parameters["dependencias"].default, False)
        # la misma cuenta: el eje de mayor diferencia entre centros (en empate, el vertical), la esquina más cercana de la etapa
        for cuenta in ("Math.abs(dy) >= Math.abs(dx)", "dy <= 0 ? b.y0 : b.y1", "dx < 0 ? b.x0 : b.x1",
                       "inicial ? H : H - Math.round(0.22 * 2 * H) / 2", "d2(e, d) < d2(m, d) ? e : m"):
            self.assertIn(cuenta, js)
        fuente = inspect.getsource(dg._dependencias_recinto)
        for cuenta in ("abs(dy) >= abs(dx)", 'b["y0"] if dy <= 0 else b["y1"]', 'b["x0"] if dx < 0 else b["x1"]',
                       "H if inicial else H - round(0.22 * 2 * H) / 2"):
            self.assertIn(cuenta, fuente)
        self.assertFalse(hasattr(dg, "_punto_del_marco"), "ya no hay un único trazo al punto más cercano del marco")


@unittest.skipUnless(QT, "requiere PySide6")
class NombreDeLaEncapsulante(unittest.TestCase):
    """Los nombres del marco de un recinto, como en la norma: el de la encapsulante arriba y el del recinto abajo, los dos a caballo
    del trazo, cortándolo, con un fondo del color del lienzo para que se lean; igual en Qt y en el banco web."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def nombre_y_marco(v, sc):
        """El texto con el nombre de la encapsulante del recinto «R» de «encapsulacion» (el centrado sobre su marco) y su marco."""
        marco = dg.cajas_parciales(v.model)["R"]
        enc = next(p["ownerStep"] for p in v.model["partials"] if p["id"] == "R")
        nombre, cx = v.model["names"][enc], marco["x0"] + 30
        return [it for it in sc.items() if isinstance(it, QGraphicsTextItem) and it.toPlainText() == nombre
                and abs(it.sceneBoundingRect().left() - cx) < 1], marco

    @staticmethod
    def fondos(sc, texto_):
        """Los rectángulos del color del lienzo (sin trazo) que hay bajo un texto y que lo cubren por los lados."""
        from PySide6.QtGui import QColor
        r = texto_.sceneBoundingRect()
        return [it for it in sc.items() if hasattr(it, "brush") and it.brush().style() == Qt.BrushStyle.SolidPattern
                and it.brush().color() == QColor(dg.COL["panel"]) and it.sceneBoundingRect().contains(r)]

    def test_SEDI274_el_nombre_de_la_encapsulante_va_a_caballo_del_trazo_superior_de_su_recinto_sobre_su_fondo(self):
        """REQ-JER-05, REQ-EDT-02: el nombre de la encapsulante se escribe a la izquierda sobre el marco de su recinto, con su línea
        base 5 por debajo del trazo de arriba (a caballo de él, como el nombre del recinto abajo) y un fondo del color del lienzo,
        por encima del trazo, que lo corta: se ve el trazo a los lados y no entre las letras."""
        from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter
        v = ejemplo("encapsulacion")
        sc, _ = dibujo(v)
        self.assertFalse(hasattr(dg, "ENCIMA_MARCO"), "ya no sube por encima del marco")
        (nombre,), marco = self.nombre_y_marco(v, sc)
        r, y0 = nombre.sceneBoundingRect(), marco["y0"]
        self.assertAlmostEqual(r.top() + QFontMetricsF(nombre.font()).ascent(), y0 + 5, places=1, msg="línea base, como el de abajo")
        self.assertTrue(r.top() < y0 < r.bottom(), "a caballo del trazo")
        self.assertAlmostEqual(r.left(), marco["x0"] + 30, delta=.01)
        (fondo,) = self.fondos(sc, nombre)
        marco_item = next(it for it in sc.items() if it.zValue() == dg.Z_FRAME and hasattr(it, "rect") and it.rect().width() > 100
                          and abs(it.rect().top() - y0) < 0.1)
        self.assertGreater(fondo.zValue(), marco_item.zValue(), "el fondo va por encima del trazo")
        self.assertGreater(nombre.zValue(), fondo.zValue(), "y el texto, por encima del fondo")
        rb = texto(sc, "R").sceneBoundingRect()
        self.assertAlmostEqual(rb.left(), r.left(), delta=.01)
        self.assertTrue(rb.top() < marco["y1"] < rb.bottom(), "el nombre del recinto sigue sobre el trazo de abajo")
        self.assertEqual(len(self.fondos(sc, texto(sc, "R"))), 1)
        # al pintarlo: el trazo se ve a unos pocos píxeles a cada lado del nombre y se corta junto a él
        escala, area = 4, QRectF(r.left() - 30, y0 - 12, r.width() + 60, 24)
        img = QImage(int(area.width() * escala), int(area.height() * escala), QImage.Format.Format_ARGB32)
        img.fill(QColor(dg.COL["panel"]))
        p = QPainter(img)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        sc.render(p, QRectF(0, 0, img.width(), img.height()), area)
        p.end()

        def oscuro(x, y):
            c = img.pixelColor(int((x - area.left()) * escala), int((y - area.top()) * escala))
            return c.red() < 140

        self.assertTrue(oscuro(r.left() - 12, y0) and oscuro(r.right() + 12, y0), "el trazo, a los lados del nombre")
        self.assertFalse(oscuro(r.left() - 1.5, y0) or oscuro(r.right() + 1.5, y0), "cortado junto al nombre, que se lee")

    def test_SEDI275_dibujo_js_coloca_el_nombre_de_la_encapsulante_igual_que_escritorio(self):
        """REQ-JER-05, REQ-EDT-02: tools/dibujo.js escribe el nombre de la encapsulante a caballo del trazo de arriba (línea base 5
        por debajo, a la izquierda) y el del recinto a caballo del de abajo, los dos con el fondo del color del lienzo de `framelabel`,
        como escritorio/diagrama.py; ya no sube por encima del marco."""
        import inspect
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        css = (ROOT / "tools" / "dibujo.css").read_text(encoding="utf-8")
        self.assertNotIn("ENCIMA_MARCO", js)
        self.assertIn("txt(g, b.x0 + 30, b.y0 + 5, nameOf(M, pt.ownerStep)", js)
        self.assertIn("txt(g, b.x0 + 30, b.y1 + 5, pt.label", js)
        self.assertRegex(css, r"\.framelabel\{[^}]*paint-order:stroke;stroke:var\(--panel\)", "el fondo del color del lienzo")
        marcos = inspect.getsource(dg._marcos)
        self.assertNotIn("ENCIMA_MARCO", marcos)
        self.assertIn('b["y0"] + 5', marcos)
        self.assertIn('b["y1"] + 5', marcos)
        self.assertEqual(marcos.count("halo=True"), 3, "los dos del recinto y el del parcial, sobre su fondo")

    def test_SEDI276_centrar_todo_deja_a_la_vista_el_nombre_y_el_marco_no_depende_de_el(self):
        """REQ-EDT-02: el nombre sobresale la mitad del marco, así que la caja del dibujo lo incluye y «Centrar todo» lo deja a la
        vista; la disposición del modelo no cambia: el marco sigue midiendo lo mismo en torno a sus etapas."""
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


# --- Los marcos de los parciales abarcan todo lo que se dibuja de ellos; las dependencias del recinto, a sus esquinas ----------

def modelo_parcial_con_retorno(con_temporizador=False):
    """El parcial G de una captura: A (inicial), B y C, sus transiciones ta, tb y tc (todo en G) y el retorno de tc a A, por la
    izquierda. Con `con_temporizador`, tb espera 3 s y B lleva una acción condicionada por un retardo."""
    m = M().partial("G").var("a").var("b").var("c").var("y", "output").step("A", True, partial="G").step("B", partial="G")
    m.step("C", partial="G")
    m.trans("ta", ["A"], ["B"], "a", partial="G").trans("tc", ["C"], ["A"], "c", partial="G")
    m.trans("tb", ["B"], ["C"], "b AND delay(3 s, active(B), 0 s)" if con_temporizador else "b", partial="G")
    if con_temporizador:
        m.cont("B", "y", "delay(2 s, a, 0 s)")
    return m, {"A": (220, 60), "ta": (220, 140), "B": (220, 220), "tb": (220, 300), "C": (220, 380), "tc": (220, 460)}


def modelo_recinto_con_retorno():
    """El recinto R de la otra captura: la encapsulante H (con Z) y, en R, I (inicial), J con una acción, K («*») con otra
    condicionada y t1, que vuelve de J a I por la izquierda; todo lo de R queda a la derecha de x = 400 del dibujo."""
    m = M().partial("R").var("p").var("q").var("r").var("luz", "output")
    m.step("H", True, kind="enclosing").step("Z")
    m.step("I", True, partial="R").step("J", partial="R").step("K", partial="R")
    m.trans("t", ["H"], ["Z"], "p").trans("u", ["Z"], ["H"], "q")
    m.trans("v", ["I"], ["J"], "r", partial="R").trans("w", ["K"], ["J"], "r", partial="R").trans("t1", ["J"], ["I"], "q", partial="R")
    m.cont("J", "luz").cont("K", "luz", "r")
    m.enclosure("H", "R", ["K"])
    return m, {"H": (160, 60), "t": (160, 140), "Z": (160, 220), "u": (160, 290), "I": (430, 70), "v": (430, 150), "J": (430, 230),
               "K": (580, 70), "w": (580, 150), "t1": (430, 310)}


def modelo_con_recinto_en(lado):
    """Una encapsulante H en (500, 400) y su recinto R, con una etapa y su transición, a su `lado` («arriba», «abajo», «izquierda» o
    «derecha»); el marco de R no cambia entre un caso y otro, solo la encapsulante."""
    m = M().partial("R").var("p").step("H", True, kind="enclosing").step("A", True, partial="R").step("B", partial="R")
    m.trans("t", ["A"], ["B"], "p", partial="R")
    m.enclosure("H", "R", ["A"])
    centro = {"arriba": (400, 700), "abajo": (400, 80), "izquierda": (900, 400), "derecha": (100, 400)}[lado]
    return m, {"H": centro, "A": (500, 300), "t": (500, 380), "B": (500, 460)}


@unittest.skipUnless(QT, "requiere PySide6")
class MarcosQueAbarcanTodo(unittest.TestCase):
    """Encargo D2, punto 3: el marco de un parcial y el de un recinto rodean todo lo que se dibuja de él (etapas, transiciones con
    sus textos, acciones, barras y los recorridos de sus enlaces, también los de retorno), con el margen de siempre, y no cambian
    al simular."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def marco(v, pid):
        b = dg.cajas_parciales(v.model)[pid]
        return QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"])

    def fuera(self, sc, marco, desde_x=-1e9, margen=18):
        """Lo dibujado de verdad (todo salvo los marcos y sus nombres) que está a la derecha de `desde_x` y no cabe en el marco con
        `margen` de sobra; vacío si cabe."""
        dentro = marco.adjusted(margen, margen, -margen, -margen)
        return [(type(it).__name__, it.sceneBoundingRect()) for it in sc.items()
                if it.zValue() >= 1 and it.sceneBoundingRect().left() >= desde_x and not dentro.contains(it.sceneBoundingRect())]

    def test_SEDI313_el_marco_del_parcial_rodea_el_retorno_los_enlaces_los_textos_y_las_acciones(self):
        """REQ-EDT-02, REQ-JER-04: el marco del parcial G de la captura (A, B y C con el retorno de tc a A por la izquierda) rodea
        el recorrido del retorno y de los enlaces, las transiciones con sus designaciones y receptividades, y no solo las etapas; con
        un margen de 26 a los lados y 22 arriba y abajo de lo más externo."""
        m, lay = modelo_parcial_con_retorno()
        v = vista(m, lay)
        sc, _ = dibujo(v)
        marco = self.marco(v, "G")
        self.assertEqual(self.fuera(sc, marco), [], "todo lo dibujado cabe en el marco, con margen")
        pts = [p for e in dg.enlaces(v.model) for p in e["pts"]]
        self.assertEqual(min(x for x, _ in pts) - marco.left(), dg.MARGEN_MARCO_X, "el carril del retorno, con el margen de siempre")
        self.assertGreaterEqual(min(y for _, y in pts) - marco.top(), dg.MARGEN_MARCO_Y - 0.01)
        self.assertGreaterEqual(marco.bottom() - max(y for _, y in pts), dg.MARGEN_MARCO_Y - 0.01)
        pos = dg.posiciones(v.model)
        antiguo_x0 = min(x for x, _ in (pos[i] for i in ("A", "B", "C"))) - dg.H - 26  # lo que rodeaba antes: solo las etapas
        self.assertLess(marco.left(), antiguo_x0 - 40, "el marco de antes dejaba fuera la flecha de retorno")
        for t in ("(ta)", "(tb)", "(tc)", "a", "b", "c"):  # los textos de las transiciones
            r = texto(sc, t).sceneBoundingRect()
            self.assertTrue(marco.contains(r), t)
        # una acción más ancha que lo de siempre a la derecha: el marco la sigue (y sus marcas de arriba)
        m.cont("B", "y", "a AND b")
        v2 = vista(m, lay)
        sc2, cajas = dibujo(v2)
        caja = next(c for c in cajas if c["etapa"] == "B")
        self.assertTrue(self.marco(v2, "G").contains(QRectF(*caja["rect"])))
        self.assertEqual(self.fuera(sc2, self.marco(v2, "G")), [])

    def test_SEDI314_el_marco_del_recinto_rodea_el_retorno_de_su_etapa_inicial_y_sus_acciones(self):
        """REQ-EDT-02, REQ-JER-05: el marco del recinto R de la captura (con el retorno de t1 a I por la izquierda y las acciones de J
        y de K) lo rodea todo; la encapsulante H, de fuera, queda fuera."""
        m, lay = modelo_recinto_con_retorno()
        v = vista(m, lay)
        sc, cajas = dibujo(v)
        marco = self.marco(v, "R")
        self.assertEqual(self.fuera(sc, marco, desde_x=400), [], "todo lo de R cabe en su marco, con margen")
        retorno = next(e for e in dg.enlaces(v.model) if e["id"] == "t1|I|post")
        self.assertTrue(all(marco.adjusted(25, 21, -25, -21).contains(QPointF(x, y)) for x, y in retorno["pts"]), "el retorno de t1")
        for c in cajas:
            self.assertTrue(marco.contains(QRectF(*c["rect"])), c)
        h = dg.posiciones(v.model)["H"]
        self.assertFalse(marco.contains(QPointF(*h)), "la encapsulante no es de su recinto")
        # y el parcial de al lado (el raíz, sin marco) no se lleva nada de R
        self.assertEqual(set(dg.cajas_parciales(v.model)), {"R"})

    def test_SEDI315_el_marco_no_cambia_al_simular_ni_por_el_tiempo_de_un_temporizador(self):
        """REQ-EDT-02, REQ-SIM-03: el marco solo depende de lo estructural: el tiempo transcurrido de un temporizador y el estado de
        las etapas no lo cambian (el dibujo cabe igual en él mientras cuenta), y dibujar con otro estado ni lo toca."""
        m, lay = modelo_parcial_con_retorno(con_temporizador=True)
        v = vista(m, lay)
        antes = dg.cajas_parciales(v.model)
        parado = dibujo(v)[0]
        self.assertEqual(self.fuera(parado, self.marco(v, "G")), [])
        v.act("fijar", {"cambios": {"a": True}})
        v.act("avanzar", {"us": 1_500_000})
        self.assertTrue(v.state()["temporal"], "hay un temporizador contando")
        contando = dibujo(v)[0]
        self.assertTrue(any(t.toPlainText().endswith(" s") for t in textos(contando) if t.toPlainText()[:1].isdigit()), "con su tiempo")
        self.assertEqual(dg.cajas_parciales(v.model), antes)
        self.assertEqual(self.fuera(contando, self.marco(v, "G")), [], "el tiempo transcurrido también cabe")
        self.assertEqual(dg.cajas_parciales(vista(m, lay).model), antes)

    def test_SEDI316_mover_y_encuadrar_usan_el_marco_nuevo(self):
        """REQ-EDT-02, REQ-EDT-08, REQ-JER-07: lo que se suelta en el carril del retorno, que ahora queda dentro del marco, es del
        parcial; «Encuadrar» encaja el marco nuevo; y al mover una etapa el marco la sigue con todo lo que se dibuja de ella."""
        from escritorio.edicion import Edicion
        m, lay = modelo_recinto_con_retorno()
        e = Edicion.desde(m.doc, lay, "t")
        marco = dg.cajas_parciales(e.M)["R"]
        antiguo_x0 = min(dg.posiciones(e.M)[i][0] for i in ("I", "J", "K")) - dg.H - 26
        self.assertLess(marco["x0"], antiguo_x0 - 10, "el marco nuevo llega más a la izquierda")
        en_el_carril = QPointF((marco["x0"] + antiguo_x0) / 2, 200)
        self.assertEqual(e.parcial_en(en_el_carril), "R", "soltar ahí es soltar en el recinto")
        caja = e._caja_encuadre("R")
        self.assertEqual((caja.left(), caja.right(), caja.top(), caja.bottom()),
                         (marco["x0"] - 10, marco["x1"] + 10, marco["y0"] - 10, marco["y1"] + 18))
        # mover la etapa J a la derecha: el marco crece con ella y sigue conteniendo el retorno de t1
        antes = marco["x1"]
        e.ed.move("J", 600, 230)
        e.cambia()
        nuevo = dg.cajas_parciales(e.M)["R"]
        self.assertGreater(nuevo["x1"], antes)
        for x, y in next(r for r in dg.enlaces(e.M) if r["id"] == "t1|I|post")["pts"]:
            self.assertTrue(nuevo["x0"] <= x <= nuevo["x1"] and nuevo["y0"] <= y <= nuevo["y1"])

    def test_SEDI317_un_parcial_con_acciones_en_todas_las_colocaciones_barras_y_simultaneidades_lo_lleva_dentro(self):
        """REQ-EDT-02, REQ-ACT-01: con acciones en cada colocación (matriz, columna, fila separada), una condición, un evento, una
        divergencia y una convergencia simultáneas y una barra, el marco del parcial sigue rodeando todo lo suyo."""
        m = (M().partial("G").var("p").var("q").var("r").var("s").var("y1", "output").var("y2", "output").var("y3", "output")
             .var("n", "internal", "int"))
        for sid in "ABCDEF":
            m.step(sid, sid == "A", partial="G")
        m.trans("t1", ["A"], ["B", "C"], "p", partial="G").trans("t2", ["B"], ["D"], "q", partial="G")
        m.trans("t3", ["C"], ["E"], "r", partial="G").trans("t4", ["D", "E"], ["F"], "s", partial="G")
        m.trans("t5", ["F"], ["A"], "NOT s AND delay(2 s, p, 0 s)", partial="G")
        m.cont("A", "y1").cont("A", "y2", "q").cont("A", "y3", "p AND q").cont("B", "y1", "q").cont("B", "y2")
        m.cont("C", "y1").cont("C", "y2", "r").stored("D", "n", "event", "n + 1", event="rise(p)")
        lay = {"A": (220, 50), "t1": (220, 115), "B": (150, 190), "C": (290, 190), "t2": (150, 260), "t3": (290, 260),
               "D": (150, 330), "E": (290, 330), "t4": (220, 405), "F": (220, 480), "t5": (220, 545)}
        v = vista(m, lay, action_layouts={"A": "matriz-2", "B": "columna", "C": "fila-separada"})
        sc, _ = dibujo(v)
        self.assertEqual(self.fuera(sc, self.marco(v, "G")), [])
        # con la barra de simultaneidad que une dos etapas con una transición, también
        barra = {"id": "b1", "kind": "Y", "x": 40, "y": 372, "ancho": 340, "arriba": ["D", "E"], "abajo": ["t4"]}
        v2 = vista(m, lay, bars=[barra], action_layouts={"A": "matriz-2"})
        sc2, _ = dibujo(v2)
        self.assertEqual(self.fuera(sc2, self.marco(v2, "G")), [])
        self.assertGreaterEqual(self.marco(v2, "G").left(), 0)
        self.assertTrue(self.marco(v2, "G").contains(QRectF(40 + dg.SX, 372, 340, 4)))


@unittest.skipUnless(QT, "requiere PySide6")
class DependenciasAlLadoDelRecinto(unittest.TestCase):
    """Encargo D2, punto 5: con «Mostrar dependencias», la encapsulante se une a su recinto con dos trazos discontinuos a las dos
    esquinas del lado del marco que mira hacia ella, como en la figura de la norma."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    MARCO = {"x0": 100.0, "x1": 300.0, "y0": 100.0, "y1": 200.0}  # centro (200, 150)

    def test_SEDI318_las_dos_esquinas_son_las_del_lado_que_mira_a_la_encapsulante_y_salen_de_las_suyas_mas_cercanas(self):
        """REQ-JER-05, REQ-EDT-02: con el recinto debajo, a la derecha, a la izquierda o encima de la encapsulante, los dos trazos
        llegan a las dos esquinas del lado del marco que la mira (el eje de mayor diferencia entre centros; en empate, el
        vertical) y salen de la esquina de la encapsulante más cercana a cada una (en una cortada, el punto medio de la
        diagonal; en una inicial, la esquina del cuadrado exterior)."""
        b = self.MARCO
        c = dg.H - round(0.22 * 2 * dg.H) / 2  # 17: las esquinas cortadas
        casos = {
            "el recinto debajo": ((200, 20), [((183, 37), (100, 100)), ((217, 37), (300, 100))]),
            "el recinto encima": ((200, 330), [((183, 313), (100, 200)), ((217, 313), (300, 200))]),
            "el recinto a la derecha": ((0, 150), [((17, 133), (100, 100)), ((17, 167), (100, 200))]),
            "el recinto a la izquierda": ((400, 150), [((383, 133), (300, 100)), ((383, 167), (300, 200))]),
        }
        self.assertEqual(c, 17)
        for nombre, ((ox, oy), esperado) in casos.items():
            self.assertEqual(dg._dependencias_recinto(b, ox, oy), [((float(a), float(b_)), (float(x), float(y)))
                                                                    for ((a, b_), (x, y)) in esperado], nombre)
        # empate entre los dos ejes: el vertical (en el sentido de la encapsulante); en el centro, el de arriba
        self.assertEqual([d for _, d in dg._dependencias_recinto(b, 300, 250)], [(100.0, 200.0), (300.0, 200.0)], "diagonal, debajo del marco")
        self.assertEqual([d for _, d in dg._dependencias_recinto(b, 100, 50)], [(100.0, 100.0), (300.0, 100.0)], "diagonal, encima del marco")
        self.assertEqual([d for _, d in dg._dependencias_recinto(b, 200, 150)], [(100.0, 100.0), (300.0, 100.0)])
        # una encapsulante inicial sale de las esquinas del cuadrado exterior
        self.assertEqual(dg._dependencias_recinto(b, 200, 20, inicial=True),
                         [((178.0, 42.0), (100.0, 100.0)), ((222.0, 42.0), (300.0, 100.0))])

    def test_SEDI319_el_dibujo_pone_los_dos_trazos_en_cada_lado_y_cambian_si_el_marco_cambia_de_lado(self):
        """REQ-JER-05, REQ-EDT-02: dibujado, cada recinto lleva dos trazos grises discontinuos, bajo todo lo demás, a las esquinas
        del lado que mira a su encapsulante; con el mismo recinto y la encapsulante en otro lado, cambian de esquinas. Sin la opción,
        ninguno."""
        lados = {"abajo": "y0", "arriba": "y1", "izquierda": "x1", "derecha": "x0"}  # el lado del marco al que llegan
        for lado, borde in lados.items():
            m, lay = modelo_con_recinto_en(lado)
            v = vista(m, lay)
            self.assertEqual(rayas(dibujo(v)[0]), [], lado)
            sc, _ = dibujo_con(v, True)
            trazos = rayas(sc)
            self.assertEqual(len(trazos), 2, lado)
            marco = dg.cajas_parciales(v.model)["R"]
            llegan = sorted((t.line().x2(), t.line().y2()) for t in trazos)
            esperado = (sorted([(marco["x0"], marco[borde]), (marco["x1"], marco[borde])]) if borde[0] == "y"
                        else sorted([(marco[borde], marco["y0"]), (marco[borde], marco["y1"])]))
            self.assertEqual(llegan, esperado, f"el recinto está {lado} de la encapsulante: el lado {borde}")
            h = dg.posiciones(v.model)["H"]
            for t in trazos:
                self.assertEqual((abs(t.line().x1() - h[0]), abs(t.line().y1() - h[1])), (dg.H, dg.H), "de la esquina de la etapa")
            self.assertTrue(all(t.zValue() == dg.Z_FRAME for t in trazos), "bajo todo lo demás")
        # el marco de R es el mismo en los cuatro casos
        marcos = {dg.cajas_parciales(vista(*modelo_con_recinto_en(lado)).model)["R"].__repr__() for lado in lados}
        self.assertEqual(len(marcos), 1)

    def test_SEDI320_las_dependencias_no_cambian_la_disposicion_y_el_trazo_de_la_macroetapa_sigue_igual(self):
        """REQ-JER-04, REQ-JER-05: mostrar las dependencias solo añade sus trazos (dos por recinto); la macroetapa sigue unida a su
        expansión por las rectas entre centros recortadas en las cajas."""
        v = ejemplo("macroetapa")
        pos = dg.posiciones(v.model)
        (mac,) = v.model["macros"]
        sc, _ = dibujo_con(v, True)
        lineas = sorted((r.line().x1(), r.line().y1(), r.line().x2(), r.line().y2()) for r in rayas(sc))
        self.assertEqual(lineas, trazos_macro(pos, mac))
        m, lay = modelo_con_recinto_en("abajo")
        v = vista(m, lay)
        sin, con = dibujo_con(v, False)[0], dibujo_con(v, True)[0]
        self.assertEqual(len(rayas(con)) - len(rayas(sin)), 2)


MOCK_DOM = """
function MockEl(tag) { this.tag = tag; this.attrs = {}; this.children = []; this._text = ""; }
MockEl.prototype.setAttribute = function(k, v) { this.attrs[k] = v; };
MockEl.prototype.appendChild = function(c) { var i=this.children.indexOf(c); if(i>=0) this.children.splice(i,1); this.children.push(c); return c; };
Object.defineProperty(MockEl.prototype, "textContent", {
  get: function() { return this.children.length ? this.children.map(function(c) { return c.textContent; }).join("") : this._text; },
  set: function(v) { this._text = String(v); this.children = []; }});
Object.defineProperty(MockEl.prototype, "innerHTML", {get: function() { return ""; }, set: function(v) { this.children = []; this._text = ""; }});
MockEl.prototype.getComputedTextLength = function() { return 8 * this.textContent.length; };
MockEl.prototype.getBBox = function() { return {x: 0, y: 0, width: 8 * this.textContent.length, height: 12}; };
MockEl.prototype.getNumberOfChars = function() { throw new Error("sin caracteres"); };
var document = {createElementNS: function(ns, tag) { return new MockEl(tag); }};
function getComputedStyle(e) { return {fontSize: "14px"}; }
function volcar(e) { return {tag: e.tag, attrs: e.attrs, hijos: e.children.map(volcar)}; }
"""


def dibujar_con_js(modelo, estado, dependencias=True):
    """Ejecuta tools/dibujo.js (`drawDiagram`) con un DOM de mentira que mide 8 px por carácter y devuelve lo que dibuja: el árbol de
    elementos (tag, attrs, hijos); el primer hijo es el grupo de los marcos. (QJSEngine no admite la propagación de objetos
    `{...attrs}` de `txt`: se sustituye por su equivalente.)"""
    import json
    eng = QJSEngine()
    fuente = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8").replace("{x, y, ...attrs}", "Object.assign({x, y}, attrs)")
    r = eng.evaluate(MOCK_DOM + "\n" + fuente)
    assert not r.isError(), f"{r.property('lineNumber').toInt()}: {r.toString()}"
    r = eng.evaluate("var M = %s; var S = %s; var svg = new MockEl('svg'); drawDiagram(svg, M, S, {dependencias: %s});"
                     "JSON.stringify(volcar(svg))" % (json.dumps(modelo), json.dumps(estado), "true" if dependencias else "false"))
    assert not r.isError(), f"{r.property('lineNumber').toInt()}: {r.toString()}"
    return json.loads(r.toString())


@unittest.skipUnless(QJS, "requiere PySide6 con QtQml")
class DibujoJsComoQt(unittest.TestCase):
    """tools/dibujo.js y escritorio/diagrama.py dibujan lo mismo: aquí se ejecuta el JS y se compara con Qt."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SEDI325_dibujo_js_dibuja_los_mismos_marcos_y_trazos_de_dependencia_que_qt(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05: con las mismas medidas de texto (8 px por carácter en los dos), `drawDiagram` de
        tools/dibujo.js dibuja los mismos marcos de parcial y de recinto que `cajas_parciales`, y los mismos trazos de dependencia
        (dos por recinto y los de la macroetapa), en los ejemplos de la aplicación y en las capturas: con retornos, acciones en
        todas las colocaciones, simultaneidades y los cuatro lados del recinto."""
        from unittest import mock
        casos = {}
        for clave in ("forzado", "encapsulacion", "macroetapa"):
            casos[clave] = ejemplo(clave)
        casos["parcial con retorno"] = vista(*modelo_parcial_con_retorno(con_temporizador=True))
        casos["recinto con retorno"] = vista(*modelo_recinto_con_retorno())
        for lado in ("abajo", "arriba", "izquierda", "derecha"):
            casos[f"recinto {lado}"] = vista(*modelo_con_recinto_en(lado))
        m = (M().partial("G").var("p").var("q").var("r").var("s").var("y1", "output").var("y2", "output").var("n", "internal", "int"))
        for sid in "ABCDEF":
            m.step(sid, sid == "A", partial="G")
        m.trans("t1", ["A"], ["B", "C"], "p", partial="G").trans("t2", ["B"], ["D"], "q", partial="G")
        m.trans("t3", ["C"], ["E"], "r", partial="G").trans("t4", ["D", "E"], ["F"], "s", partial="G")
        m.trans("t5", ["F"], ["A"], "NOT s AND delay(2 s, p, 0 s)", partial="G")
        m.cont("A", "y1").cont("A", "y2", "q").cont("B", "y1", "q").cont("B", "y2").cont("C", "y1").cont("C", "y2", "r")
        m.stored("D", "n", "event", "n + 1", event="rise(p)")
        lay = {"A": (220, 50), "t1": (220, 115), "B": (150, 190), "C": (290, 190), "t2": (150, 260), "t3": (290, 260),
               "D": (150, 330), "E": (290, 330), "t4": (220, 405), "F": (220, 480), "t5": (220, 545)}
        casos["acciones y simultaneidades"] = vista(m, lay, action_layouts={"A": "matriz-2", "B": "columna", "C": "fila-separada"})
        medir = staticmethod(lambda segs, size, bold=False: 8.0 * sum(len(s["t"]) for s in (segs or [])))
        with mock.patch.object(dg._Pintor, "ancho", medir):
            for nombre, v in casos.items():
                arbol = dibujar_con_js(v.model, v.state())
                marcos = arbol["hijos"][0]["hijos"]
                js_marcos = sorted((float(h["attrs"]["x"]), float(h["attrs"]["y"]), float(h["attrs"]["x"]) + float(h["attrs"]["width"]),
                                    float(h["attrs"]["y"]) + float(h["attrs"]["height"])) for h in marcos if h["tag"] == "rect")
                py_marcos = sorted((b["x0"], b["y0"], b["x1"], b["y1"]) for p, b in dg.cajas_parciales(v.model).items()
                                   if next(q for q in v.model["partials"] if q["id"] == p)["kind"] != "expansion")
                self.assertEqual(js_marcos, py_marcos, nombre)
                trazos_js = []
                for h in marcos:
                    if h["tag"] == "path":
                        n = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", h["attrs"]["d"])]
                        trazos_js += [tuple(n[i:i + 4]) for i in range(0, len(n), 4)]
                sc, _ = dibujo_con(v, True)
                trazos_py = [(r.line().x1(), r.line().y1(), r.line().x2(), r.line().y2()) for r in rayas(sc)]
                self.assertEqual(sorted(trazos_js), sorted(trazos_py), nombre)
                self.assertEqual(len(trazos_py), 2 * len([p for p in v.model["partials"] if p["kind"] == "enclosure"])
                                 + 2 * len(v.model["macros"]), nombre)


if __name__ == "__main__":
    unittest.main()
