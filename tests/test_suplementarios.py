"""Pruebas suplementarias S-xx diseñadas por la implementación.

No sustituyen ni alteran oráculos del documento 11: cubren variantes de hallazgos (H-xx),
bloqueos U que ningún caso T ejercita directamente y reglas P internas (formato canónico,
decimales, declaración, paquete). La primera línea de cada docstring enumera los
requisitos que cubre; la herramienta de trazabilidad la lee.
"""
import json
import unittest
from fractions import Fraction
from pathlib import Path

from helpers import M, S, declared, last_diag, records, scenario, session

from grafcet.canonical import CanonicalError, canonical_text, strict_loads
from grafcet.declaration import coverage_declaration
from grafcet.diagnostics import DiagnosticError
from grafcet.engine import Session
from grafcet.profile import normalize_options
from grafcet.ids import document_filename, document_id_fits
from grafcet.persistence import add_document, new_project
from grafcet.values import TypeSpec, check_fits, format_value, parse_value

ROOT = Path(__file__).resolve().parents[1]


def q(s):
    return (last_diag(s).code, last_diag(s).question)


class Hallazgos(unittest.TestCase):
    def test_S08a_limite_de_evolucion_recuperable(self):
        """REQ-SEM-07, REQ-ROB-01, REQ-SIM-08: variante de T-08a disparada por un lote (H-03)."""
        cm = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["A"], "p").compile()
        s = session(cm, budget=20, batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.status, "pausada-recorrido")
        self.assertEqual(last_diag(s).code, "D-LIM-EVOL")
        self.assertEqual(len(records(s, "evolucion")), 20, "últimos registros completos")
        self.assertEqual(records(s, "estable")[-1]["timeUs"] if records(s, "estable") else None, None,
                         "no se publica falsa estabilidad")
        self.assertEqual(s.z.time, 0, "el último estado estable no avanza")
        self.assertEqual(records(s, "limite")[-1]["timeUs"], str(1 * S), "τ del contexto sin avanzar")
        s.extend_budget(40)
        s.run_to_stable()
        self.assertEqual(len(records(s, "evolucion")), 40, "contexto pendiente recuperable")
        self.assertEqual(s.status, "pausada-recorrido")

    def test_S12a_retardo_tras_activacion_no_inicial(self):
        """REQ-TMP-02: variante de T-12a independiente de H-02 (activación por transición a 1 s)."""
        m = M().var("p").step("X", True).step("A").step("B")
        m.trans("t0", ["X"], ["A"], "p").trans("t", ["A"], ["B"], "delay(2 s, active(A), 0 s)")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.advance_to(2_999_999)
        self.assertEqual(s.z.situation, {"A"})
        s.advance_to(3 * S)
        self.assertEqual(s.z.situation, {"B"})

    def test_SH05_activar_etapa_ya_activa_bloqueo_U04(self):
        """REQ-SEM-05, REQ-EVT-03: hallazgo H-05 (activación de etapa ya activa fuera de D)."""
        m = M().var("p").var("n", "internal", "int").step("A").step("B")
        m.trans("t", ["A"], ["B"], "p").stored("B", "n", "activation", "n + 1")
        s = declared(m.compile(), ["A", "B"], batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-04"))
        self.assertEqual(s.z.values["n"], 0)

    def test_SH07_memoria_inicial_no_nula_bloqueo_U09(self):
        """REQ-ACT-02, REQ-SEM-01: hallazgo H-07."""
        cm = M().var("n", "internal", "int", init="5").step("A", True).compile()
        s = session(cm, start=False)
        diags = s.start()
        self.assertEqual({(d.code, d.question) for d in diags}, {("D-SEM-PENDIENTE", "U-09")})

    def test_SH08_actividad_de_parcial_con_hijos(self):
        """REQ-JER-01: hallazgo H-08."""
        m = M().partial("G2", owner="g").var("y", "output").step("A", True).step("B", partial="G2")
        m.cont("A", "y", "activePartial(g)")
        res = m.validate()
        self.assertIn("D-CAPACIDAD-NO-SOPORTADA", {d.code for d in res.diagnostics})
        self.assertFalse(res.can_simulate)

    def test_SH09_reentrada_virtual_con_dependencia_temporal(self):
        """REQ-TMP-02: hallazgo H-09."""
        m = M().var("p").var("y", "output").step("A", True).step("B").step("X", True)
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["A"], "true").cont("A", "y", "delay(3 s, active(A), 0 s)")
        s = session(m.compile(), batches=[(2 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(last_diag(s).code, "D-CAPACIDAD-NO-SOPORTADA")
        self.assertIn("H-09", last_diag(s).question)
        m2 = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(1 s, active(A) AND p, 0 s)")
        self.assertIn("D-CAPACIDAD-NO-SOPORTADA", {d.code for d in m2.validate().diagnostics})

    def test_SH10_leer_salida_continua(self):
        """REQ-ACT-01: hallazgo H-10."""
        m = M().var("y", "output").step("A", True).step("B").cont("A", "y").trans("t", ["A"], ["B"], "y")
        self.assertIn("D-CAPACIDAD-NO-SOPORTADA", {d.code for d in m.validate().diagnostics})

    def test_SH12_id_de_documento_y_nombre_de_fichero(self):
        """REQ-DAT-01, REQ-PLT-02: hallazgo H-12."""
        long_id = "x" * 128
        self.assertFalse(document_id_fits("model", long_id))
        self.assertTrue(document_id_fits("model", "x" * 120))
        with self.assertRaises(DiagnosticError) as ctx:
            add_document(new_project("p", "t"), M(long_id).doc)
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-ID")
        self.assertEqual(document_filename("model", "A"), "model-41.json")


class BloqueosU(unittest.TestCase):
    def test_SU03_flanco_sobre_variable_interna(self):
        """REQ-EVT-03: eventos internos estáticamente bloqueados (U-03)."""
        m = M().var("n", "internal").step("A", True).step("B").trans("t", ["A"], ["B"], "rise(n)")
        self.assertTrue(any(d.question == "U-03" for d in m.validate().diagnostics))
        m2 = M().step("A", True).step("B").step("C").trans("t", ["A"], ["B"], "rise(active(C))")
        self.assertTrue(any(d.question == "U-03" for d in m2.validate().diagnostics))

    def test_SU03_accion_por_evento_en_etapa_que_sale(self):
        """REQ-EVT-03, REQ-ACT-02: acción sobre evento y etapa desactivada por ese evento (U-03/U-05)."""
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "rise(p)").stored("A", "n", "event", "n + 1", event="rise(p)")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-03"))
        self.assertEqual((s.z.situation, s.z.values["n"]), ({"A"}, 0))

    def test_SU05_receptividad_lee_valor_asignado(self):
        """REQ-ACT-05, REQ-SEM-09: asignación n:=1 seguida de receptividad n=1 en etapa virtual (U-05)."""
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "n = 1").stored("B", "n", "activation", "1")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-05"))
        self.assertEqual(s.z.situation, {"A"})

    def test_SU06_lote_y_vencimiento_coincidentes(self):
        """REQ-TMP-03: coincidencia de lote y vencimiento en el mismo τ (H-17, U-06)."""
        m = M().var("q").var("y", "output").step("A", True).cont("A", "y", "delay(2 s, active(A), 0 s)")
        s = session(m.compile(), batches=[(2 * S, 0, {"q": True})])
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-06"))
        self.assertFalse(s.z.outputs["y"])

    def test_SU06_delay_cero(self):
        """REQ-TMP-03: delay con d1=0 bloqueado (U-06)."""
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "delay(0 s, p, 0 s)")
        self.assertTrue(any(d.question == "U-06" for d in m.validate().diagnostics))

    def test_SU06_vencimientos_que_dependen_del_orden(self):
        """REQ-TMP-03, REQ-SEM-08: vencimientos simultáneos con efecto mutuo (U-06)."""
        m = M().step("A", True).step("B").step("C", True).step("D")
        m.trans("t", ["A"], ["B"], "delay(2 s, active(A), 0 s)")
        m.trans("u", ["C"], ["D"], "delay(2 s, active(C), 0 s) AND active(A)")
        s = session(m.compile())
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-06"))
        self.assertEqual(s.z.situation, {"A", "C"})

    def test_SU07_fuente_de_nivel_y_transicion_sin_lados(self):
        """REQ-MOD-04: U-07 en validación; el borrador se conserva."""
        m = M().var("p").step("A", True).trans("f", [], ["A"], "p").trans("n", [], [], "p")
        res = m.validate()
        self.assertEqual(sum(1 for d in res.diagnostics if d.question == "U-07"), 2)
        self.assertIsNotNone(res.model)
        self.assertFalse(res.can_simulate)

    def test_SU09_inicio_inestable_acciones_iniciales_y_temporal_verdadero(self):
        """REQ-SEM-01, REQ-ACT-02, REQ-TMP-02: bloqueos de inicialización (U-09)."""
        cases = [M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p"),
                 M().var("z", "internal").step("A", True).stored("A", "z", "activation", "true"),
                 M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(1 s, p, 0 s)")]
        for m in cases:
            s = session(m.compile(), init={"p": True} if m.doc["variables"][0]["name"] == "p" else None, start=False)
            self.assertTrue(any(d.question == "U-09" for d in s.start()), m.doc["variables"])


class LecturasSeleccionables(unittest.TestCase):
    """P-IMP-15: lectura de U-03 elegible por el usuario; por defecto, detener."""

    def _u03(self, reading=None, reinicio=False, budget=10_000):
        m = M().var("p").var("reinicio").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "rise(p)").trans("u", ["B"], ["C"], "rise(p)").trans("v", ["C"], ["A"], "reinicio")
        cm = m.compile()
        s = Session(cm, scenario(cm, {"reinicio": reinicio}, [(1 * S, 0, {"p": True})]), budget=budget,
                    options=None if reading is None else {"U-03": reading})
        self.assertEqual(s.start(), [])
        s.run()
        return s

    def test_SOPT03a_por_defecto_se_detiene(self):
        """REQ-EVT-03, REQ-SEM-09, REQ-NOR-02: sin elección explícita, U-03 sigue deteniendo."""
        s = self._u03()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-03"))
        self.assertEqual(s.trace.header["semanticProfile"]["options"], {"U-03": "detener"})

    def test_SOPT03b_lectura_situacion_anterior(self):
        """REQ-EVT-03, REQ-SEM-09, REQ-SIM-05: el evento solo franquea lo validado antes de él → B, con hipótesis en la traza."""
        s = self._u03("situacion-anterior")
        self.assertEqual((s.status, s.z.situation), ("finalizada", {"B"}))
        hyp = records(s, "estable")[-1]["hypotheses"]
        self.assertEqual(hyp, [{"question": "U-03", "reading": "situacion-anterior", "transition": "u",
                                "evolutionIndex": 2, "receptivity": False}])
        self.assertEqual(s.trace.header["semanticProfile"]["options"], {"U-03": "situacion-anterior"})
        self.assertEqual(self._u03("situacion-anterior", reinicio=True).z.situation, {"B"})

    def test_SOPT03c_lectura_recorrido(self):
        """REQ-EVT-03, REQ-SEM-07, REQ-SEM-09: el evento sigue disponible en el recorrido → C; con reinicio, ciclo sin fin."""
        s = self._u03("recorrido")
        self.assertEqual(s.z.situation, {"C"})
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["t"], ["u"]])
        # Con reinicio=1 el recorrido vuelve a A y el mismo flanco vuelve a franquear t: A→B→C→A→… en el mismo
        # instante. Es consecuencia de esta lectura; el motor lo corta con D-LIM-EVOL y no publica estado estable.
        r = self._u03("recorrido", reinicio=True, budget=30)
        self.assertEqual((r.status, last_diag(r).code), ("pausada-recorrido", "D-LIM-EVOL"))
        self.assertEqual([e["cleared"] for e in records(r, "evolucion")][:6], [["t"], ["u"], ["v"], ["t"], ["u"], ["v"]])
        self.assertEqual(records(r, "estable"), [])

    def test_SOPT03d_instantanea_exige_la_misma_lectura(self):
        """REQ-SIM-04, REQ-DAT-04: no se mezclan instantáneas de lecturas distintas."""
        s = self._u03("situacion-anterior")
        snap = s.snapshot("con-hipotesis")
        with self.assertRaises(DiagnosticError) as ctx:
            Session.restore(s.cm, s.scenario, snap)
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-INSTANTANEA-INCOMPATIBLE")
        r = Session.restore(s.cm, s.scenario, snap, options={"U-03": "situacion-anterior"})
        self.assertEqual(r.z.situation, {"B"})

    def test_SOPT03e_limites_de_la_opcion(self):
        """REQ-MOD-04, REQ-EVT-03: valores no admitidos se rechazan; la repetición de fuentes sigue en U-07."""
        with self.assertRaises(ValueError):
            normalize_options({"U-03": "lo-que-diga-el-plc"})
        with self.assertRaises(ValueError):
            normalize_options({"U-05": "recorrido"})
        m = M().var("p").step("X", True).step("A").step("B")
        m.trans("t", [], ["A"], "rise(p)").trans("u", [], ["B"], "rise(p)")
        cm = m.compile()
        s = Session(cm, scenario(cm, None, [(1 * S, 0, {"p": True})]), options={"U-03": "recorrido"})
        s.start()
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-07"))


class ReglasP(unittest.TestCase):
    def test_SCAN_formato_canonico(self):
        """REQ-DAT-05, REQ-DAT-06: reglas de representación canónica y lectura estricta (09)."""
        self.assertEqual(canonical_text({"b": 1, "a": "x\"\\\n\u0001ñ/"}), '{"a":"x\\"\\\\\\u000a\\u0001ñ/","b":1}')
        self.assertEqual(canonical_text({"é": True, "z": None, "Z": False}), '{"Z":false,"z":null,"é":true}')
        for bad in ({"x": 1.5}, {"x": -1}, {"x": 2**31}, {"x": "\ud800"}):
            with self.assertRaises(CanonicalError):
                canonical_text(bad)
        for raw in (b'\xef\xbb\xbf{}', b'{"a":1,"a":2}', b'{"a":1e3}', b'{"a":Infinity}'):
            with self.assertRaises(CanonicalError):
                strict_loads(raw)

    def test_SDEC_decimales_y_enteros_exactos(self):
        """REQ-EXP-01, REQ-TMP-01: sin redondeo silencioso ni desbordamiento."""
        d2 = TypeSpec("decimal", 2)
        self.assertEqual(parse_value(d2, "1.5"), Fraction(3, 2))
        self.assertEqual(format_value(d2, Fraction(3, 2)), "1.5")
        for bad in ("1.50", "-0", "1.234", "01"):
            with self.assertRaises(DiagnosticError):
                parse_value(d2, bad)
        with self.assertRaises(DiagnosticError):
            check_fits(d2, Fraction(1, 3))
        with self.assertRaises(DiagnosticError):
            check_fits(TypeSpec("decimal", 0), Fraction(10**18))
        with self.assertRaises(DiagnosticError):
            check_fits(TypeSpec("int"), 2**63)
        m = M().var("p").var("n", "internal", "int").step("A").step("B")
        m.trans("t", ["A"], ["B"], "p").stored("B", "n", "activation", "n * 2")
        s = declared(m.compile(), ["A"], values={"n": 2**62}, batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(last_diag(s).code, "D-NUM")
        self.assertEqual(s.z.values["n"], 2**62, "se conserva el último estado completo")

    def test_SEXP_comparacion_encadenada_y_tipos(self):
        """REQ-EXP-01: comparaciones encadenadas rechazadas; sin conversión booleano↔número."""
        from grafcet import expressions as ex
        with self.assertRaises(ex.ParseError):
            ex.parse("a < b < c", lambda k, n: n)
        m = M().var("p").var("n", "input", "int").step("A", True).step("B").trans("t", ["A"], ["B"], "p AND n")
        self.assertIn("D-TIPO", {d.code for d in m.validate().diagnostics})

    def test_SDECL_declaracion_sin_conformidad(self):
        """REQ-NOR-01, REQ-NOR-02, REQ-ALC-03: la declaración excluye U críticas y no afirma conformidad."""
        decl = coverage_declaration()
        self.assertFalse(decl["conformityClaimed"])
        self.assertFalse([c for c in decl["capabilities"] if c["status"] == "aprobada"])
        self.assertTrue(all(c["status"] in ("provisional", "no-soportada") for c in decl["capabilities"]))
        excluded = {x["capability"] for x in decl["excludedMatters"]}
        self.assertTrue({"eventos.recorrido", "permanencia.efectos", "acciones.lecturas-contexto",
                         "temporal.coincidencias", "situacion.inicial.vacia", "inicio.inestable"} <= excluded)
        self.assertEqual(decl["normativeBase"]["edition"], "3.0")

    def test_SPKG_paquete_de_transferencia_intacto(self):
        """REQ-ALC-02, REQ-CR-02: parte automatizable de R-02 (doce Markdown, huellas de la versión implementada)."""
        pkg = ROOT.parent / "Definición del proyecto"
        files = sorted(p.name for p in pkg.iterdir())
        self.assertEqual(len(files), 12)
        self.assertTrue(all(f.endswith(".md") for f in files))
        base = ROOT / "spec" / "paquete_base.json"
        if base.exists():
            import hashlib
            expected = json.loads(base.read_text(encoding="utf-8"))["sha256"]
            got = {f: hashlib.sha256((pkg / f).read_bytes()).hexdigest() for f in files}
            self.assertEqual(got, expected, "el paquete cambió respecto a la versión implementada")


if __name__ == "__main__":
    unittest.main()
