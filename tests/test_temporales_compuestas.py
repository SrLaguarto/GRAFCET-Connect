"""Bases temporales compuestas (P-IMP-176), P-IMP-18 extendida, rechazo de flancos y doble negación (IM10)."""
import json
import unittest

from helpers import M, S, scenario
from test_dibujo_vista import MOCK_DOM, QJS, QT, ROOT

from grafcet.engine import Session, declared_state
from grafcet.view import norm

if QT:
    from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsScene
    from escritorio import diagrama as dg
    from escritorio.escena.descriptores import Grabadora
if QJS:
    from PySide6.QtQml import QJSEngine

AVISO_FLANCO = (
    "Un flanco (↑a) no puede usarse en una temporización, "
    "ni a la conexión ni a la desconexión, porque dura un instante."
)


class BasesTemporalesCompuestas(unittest.TestCase):
    def test_etapas_conjuncion_disyuncion_y_negacion(self):
        """5s/(X1·X2), 3s/(a + b) y 2s/NOT a compilan y temporizan según su valor al cierre."""
        m = M().var("a").var("b").var("p").var("y1", "output").var("y2", "output").var("y3", "output")
        m.step("X1", True).step("P1", True).step("X2").trans("t1", ["P1"], ["X2"], "p")
        m.cont("X1", "y1", "delay(5 s, active(X1) AND active(X2), 0 s)")
        m.cont("X1", "y2", "delay(3 s, a OR b, 0 s)")
        m.cont("X1", "y3", "delay(2 s, NOT a, 0 s)")
        cm = m.compile()
        s = Session(cm, scenario(cm, None, [(1 * S, 0, {"b": True, "p": True})]))
        s.start()
        s.advance_to(1_999_999)
        self.assertFalse(s.z.outputs["y3"])
        s.advance_to(2 * S)
        self.assertTrue(s.z.outputs["y3"])
        s.advance_to(3_999_999)
        self.assertFalse(s.z.outputs["y2"])
        s.advance_to(4 * S)
        self.assertTrue(s.z.outputs["y2"])
        s.advance_to(5_999_999)
        self.assertFalse(s.z.outputs["y1"])
        s.advance_to(6 * S)
        self.assertTrue(s.z.outputs["y1"])

    def test_mezcla_etapas_internas_y_salida_continua(self):
        """Base con etapas, entradas, internas y lectura de salida continua (8.2 C), más desconexión 0s/base/3s."""
        m = M().var("p").var("c", "internal").var("yc", "output").var("yt", "output").var("yoff", "output")
        m.step("A", True).step("B").step("C", True)
        m.trans("t", ["A"], ["B"], "p").stored("B", "c", "activation", "true")
        m.cont("B", "yc", "true")
        m.cont("C", "yt", "delay(4 s, active(B) AND c AND yc, 0 s)")
        m.cont("C", "yoff", "delay(0 s, active(B) AND p, 3 s)")
        cm = m.compile()
        s = Session(cm, scenario(cm, None, [(1 * S, 0, {"p": True}), (2 * S, 0, {"p": False})]))
        s.start()
        self.assertFalse(s.z.outputs["yt"])
        self.assertFalse(s.z.outputs["yoff"])
        s.advance_to(1 * S)
        self.assertTrue(s.z.outputs["yoff"], "d1=0 se vuelve verdadera en el mismo instante que B AND p")
        self.assertFalse(s.z.outputs["yt"])
        s.advance_to(2 * S)
        self.assertTrue(s.z.outputs["yoff"], "d2=3s mantiene yoff hasta 5 s tras caer p a 2 s")
        s.advance_to(4_999_999)
        self.assertFalse(s.z.outputs["yt"], "yt aún no ha vencido antes de los 5 s")
        s.advance_to(5 * S)
        self.assertTrue(s.z.outputs["yt"])
        self.assertFalse(s.z.outputs["yoff"], "desconexión termina a los 2 + 3 = 5 s")

    def test_mezcla_dos_etapas_y_p_imp_18_transitorio_no_reinicia(self):
        """P-IMP-18 extendida: salida y reentrada en el mismo instante de una base compuesta conserva la cuenta."""
        m = M().var("q").var("y", "output").step("A", True).step("B").step("C", True)
        m.trans("t1", ["A"], ["B"], "rise(q)").trans("t2", ["B"], ["A"], "true")
        m.cont("C", "y", "delay(5 s, active(A) AND active(C), 0 s)")
        cm = m.compile()
        s = Session(cm, scenario(cm, None, [(2 * S, 0, {"q": True})]), options={"U-03": "situacion-anterior"})
        s.start()
        s.step_external()
        self.assertEqual(s.z.situation, {"A", "C"})
        s.advance_to(4_999_999)
        self.assertFalse(s.z.outputs["y"], "la salida y reentrada transitoria en t=2s no reinició desde 2s")
        s.advance_to(5 * S)
        self.assertTrue(s.z.outputs["y"], "vence a t=5s desde t=0s")

    def test_flanco_solo_o_en_base_compuesta_rechazado_con_texto_exacto(self):
        """Un flanco solo o dentro de una base compuesta falla con D-TIPO-EVENTO y el aviso exacto."""
        casos = [
            "delay(5 s, rise(a), 0 s)",
            "delay(0 s, fall(a), 3 s)",
            "delay(5 s, active(A) AND rise(a), 0 s)",
            "delay(3 s, a OR fall(b), 0 s)",
        ]
        for expr in casos:
            with self.subTest(expr=expr):
                m = M().var("a").var("b").var("y", "output").step("A", True).cont("A", "y", expr)
                res = m.validate()
                diags = [d for d in res.diagnostics if d.code == "D-TIPO-EVENTO"]
                self.assertTrue(diags, f"falta D-TIPO-EVENTO en {expr}: {res.diagnostics}")
                self.assertEqual(diags[0].message, AVISO_FLANCO)

    def test_declared_state_rechaza_base_compuesta_verdadera(self):
        """declared_state sigue rechazando bases temporales ya verdaderas sin estado temporal."""
        m = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(2 s, active(A) AND p, 0 s)")
        cm = m.compile()
        with self.assertRaisesRegex(ValueError, "base temporal compuesta"):
            declared_state(cm, ["A"], {"p": True})
        st = declared_state(cm, ["A"], {"p": False})
        self.assertEqual(st.situation, frozenset({"A"}))

    def test_coincidencia_lote_y_vencimiento_en_base_compuesta(self):
        """Un lote en el mismo instante que vence una base compuesta activa la detección 4.1."""
        m = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(3 s, active(A) AND p, 0 s)")
        cm = m.compile()
        sc = scenario(cm, None, [(0, 0, {"p": True}), (3 * S, 0, {"p": False})])
        s_det = Session(cm, sc, options={"4.1": "detener"})
        s_det.start()
        s_det.run()
        self.assertEqual(s_det.status, "error")
        self.assertEqual(s_det.diagnostics[-1].code, "D-SEM-PENDIENTE")
        s_a = Session(cm, sc, options={"4.1": "A"})
        s_a.start()
        s_a.run()
        self.assertEqual(s_a.status, "finalizada")


class DobleNegacionVisual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QT:
            cls.app = QApplication.instance() or QApplication([])

    def _modelo_not_or_not(self):
        return {
            "operator": "not",
            "operands": [{
                "operator": "or",
                "operands": [
                    {"operator": "not", "operands": [{"operator": "ref", "reference": "va"}]},
                    {"operator": "not", "operands": [{"operator": "ref", "reference": "vb"}]},
                ],
            }],
        }

    def test_view_norm_genera_niveles_apilados_e_ids_distintos(self):
        """NOT(NOT a + NOT b) produce nivel 0 en a y b y nivel 1 sobre todo a + b."""
        segs = norm(self._modelo_not_or_not(), False, {"va": "a", "vb": "b"}, key="e")
        self.assertEqual([s["t"] for s in segs], ["a", " + ", "b"])
        self.assertEqual([len(s["neg"]) for s in segs], [2, 1, 2])
        self.assertEqual([g["n"] for g in segs[0]["neg"]], [0, 1])
        self.assertEqual(segs[1]["neg"][0]["n"], 1)
        self.assertEqual(segs[0]["neg"][1]["id"], segs[1]["neg"][0]["id"])
        self.assertEqual(segs[1]["neg"][0]["id"], segs[2]["neg"][1]["id"])
        self.assertNotEqual(segs[0]["neg"][0]["id"], segs[2]["neg"][0]["id"])
        self.assertEqual(segs[0]["neg"][0]["eval"], ["e.0.0"])
        self.assertEqual(segs[2]["neg"][0]["eval"], ["e.0.1"])
        self.assertEqual(segs[1]["neg"][0]["eval"], ["e"])

    @unittest.skipUnless(QT, "requiere PySide6")
    def test_qt_y_descriptores_dibujan_dos_alturas_y_colores_independientes(self):
        """Qt (_Pintor) y Grabadora dibujan barras apiladas a alturas distintas con colores propios."""
        segs = norm(self._modelo_not_or_not(), False, {"va": "a", "vb": "b"}, key="e")
        sc = QGraphicsScene()
        pt = dg._Pintor(sc)
        pt.verdaderos = {"e.0.0"}  # inner NOT a verdadera, inner NOT b y outer NOT falsas
        pt.text(10, 40, segs, 12, "text", 1)
        barras = [
            it for it in sc.items()
            if isinstance(it, QGraphicsLineItem) and abs(it.pen().widthF() - dg.GROSOR_NEGADO) < 1e-6
        ]
        self.assertEqual(len(barras), 3)
        ys = sorted({round(b.line().y1(), 2) for b in barras})
        self.assertEqual(len(ys), 2)
        self.assertAlmostEqual(ys[1] - ys[0], dg.PASO_NEGADO, places=2)
        verdes = [b for b in barras if b.pen().color().name() == dg.COL["true_text"]]
        self.assertEqual(len(verdes), 1)
        self.assertAlmostEqual(verdes[0].line().y1(), ys[1], places=2)

        g = Grabadora(dg.servicios())
        g.verdaderos = {"e"}  # outer NOT verdadera, inners falsas
        g.text(10, 40, segs, 12, "text", 1)
        lineas = [d for _, d in g.secuencia if d[0] == "linea"]
        self.assertEqual(len(lineas), 3)
        desc_verdes = [d for d in lineas if d[5][1] == "true_text"]
        self.assertEqual(len(desc_verdes), 1)
        self.assertLess(desc_verdes[0][2], max(d[2] for d in lineas))

    @unittest.skipUnless(QJS, "requiere PySide6.QtQml")
    def test_dibujo_js_dibuja_barras_apiladas_y_compatibilidad(self):
        """tools/dibujo.js dibuja las 3 barras apiladas en y distintos con clases independientes."""
        eng = QJSEngine()
        js = (ROOT / "tools/dibujo.js").read_text(encoding="utf-8").replace(
            "{x, y, ...attrs}", "Object.assign({x, y}, attrs)"
        )
        res = eng.evaluate(MOCK_DOM + js)
        self.assertFalse(res.isError(), res.toString())
        segs = norm(self._modelo_not_or_not(), False, {"va": "a", "vb": "b"}, key="e")
        truth = {"e": False, "e.0.0": True, "e.0.1": False}
        code = "var gn=new MockEl('g'); segText(gn,0,20,%s,'tcond','start',%s); JSON.stringify(volcar(gn));" % (
            json.dumps(segs), json.dumps(truth),
        )
        r = eng.evaluate(code)
        self.assertFalse(r.isError(), r.toString())
        arbol = json.loads(r.toString())
        lines = [h for h in arbol["hijos"] if h["tag"] == "line"]
        self.assertEqual(len(lines), 3)
        ys = sorted({float(h["attrs"]["y1"]) for h in lines})
        self.assertEqual(len(ys), 2)
        self.assertAlmostEqual(ys[1] - ys[0], 2.5, places=2)
        lineas_verdes = [h for h in lines if h["attrs"]["class"] == "neg verdadero"]
        self.assertEqual(len(lineas_verdes), 1)
        self.assertAlmostEqual(float(lineas_verdes[0]["attrs"]["y1"]), ys[1], places=2)


if __name__ == "__main__":
    unittest.main()
