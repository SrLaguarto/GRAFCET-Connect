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
from grafcet.editor import Editor, new_model_document
from grafcet.engine import Session
from grafcet.profile import normalize_options
from grafcet.ids import IdGenerator, document_filename, document_id_fits
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
        self.assertEqual([r for r in records(s, "estable") if r["timeUs"] == str(S)], [],
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

    def test_SH05_activar_etapa_ya_activa_no_ejecuta_sus_acciones(self):
        """REQ-SEM-05, REQ-EVT-03: hallazgo H-05, cerrado por el comparador (3.3 A). Con «detener», U-04."""
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "p").stored("B", "n", "activation", "n + 1")
        s = declared(m.compile(), ["A", "B"], batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual((s.z.situation, s.z.values["n"]), ({"B"}, 0))
        s = declared(m.compile(), ["A", "B"], batches=[(1 * S, 0, {"p": True})], options={"3.3": "detener"})
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-04"))
        self.assertEqual(s.z.values["n"], 0)

    def test_SH07_memoria_inicial_no_nula_no_compila(self):
        """REQ-ACT-02, REQ-SEM-01: hoja 08, 1.5 A (cierra H-07); otro valor inicial se pone al activar la etapa inicial."""
        res = M().var("n", "internal", "int", init="5").step("A", True).validate()
        d = next(x for x in res.diagnostics if x.element == "n")
        self.assertEqual((d.code, d.field), ("D-FORMATO", "initialValue"))
        self.assertFalse(res.can_simulate)
        m = M().var("n", "internal", "int").step("A", True).stored("A", "n", "activation", "5")
        self.assertEqual(session(m.compile()).z.values["n"], 5, "n := 5 al activar la etapa inicial")
        # Comentario del responsable a 1.5: en la aplicación no se declara un valor inicial fuera del grafcet
        ed = Editor(new_model_document("m"), ids=IdGenerator("x"))
        with self.assertRaises(DiagnosticError) as ctx:
            ed.add_variable("n", "internal", {"kind": "int"}, initial="5")
        self.assertEqual((ctx.exception.diagnostics[0].code, ctx.exception.diagnostics[0].field), ("D-FORMATO", "initialValue"))
        v = ed.add_variable("e", "input", {"kind": "bool"}, initial=True)  # las entradas las da el escenario
        ed.change_variable(v, role="internal")
        self.assertIs(next(x for x in ed.model["variables"] if x["id"] == v)["initialValue"], False, "deja de ser entrada: 0")
        with self.assertRaises(DiagnosticError):
            ed.change_variable(v, initialValue=True)

    def test_SH08_parcial_dentro_de_otro(self):
        """REQ-JER-01, REQ-MOD-07: hallazgo H-08, cerrado por el responsable (8.1 C): sin encapsulante no compila; como recinto, sí."""
        m = M().partial("G2", owner="g").var("y", "output").step("A", True).step("B", partial="G2")
        m.cont("A", "y", "activePartial(g)")
        res = m.validate()
        d = next(x for x in res.diagnostics if x.element == "G2")
        self.assertEqual((d.code, d.field), ("D-FORMATO", "ownerRef"))
        self.assertFalse(res.can_simulate)
        self.assertIn("D-CAPACIDAD-NO-SOPORTADA", {x.code for x in m.validate({"8.1": "detener"}).diagnostics})
        # G2 como recinto de H, que está en g: se admite; con G2 activo, H está activa y g también (A y B coinciden)
        m = M().partial("G2", owner="g").var("y", "output").step("H", True, kind="enclosing").step("B", True, partial="G2")
        m.cont("H", "y", "activePartial(g)").enclosure("H", "G2", ["B"])
        s = session(m.compile())
        self.assertEqual((s.z.situation, s.z.outputs["y"]), ({"H", "B"}, True))
        for reading in ("A", "B"):
            self.assertTrue(session(m.compile({"8.1": reading}), options={"8.1": reading}).z.outputs["y"], reading)

    def test_SH09_reentrada_en_el_mismo_instante_conserva_la_duracion(self):
        """REQ-TMP-02, REQ-SEM-06: P-IMP-18 (cierra H-09); la salida y reentrada sin tiempo no reinicia el retardo."""
        m = M().var("q").var("y", "output").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "rise(q)").trans("u", ["B"], ["A"], "true").cont("A", "y", "delay(5 s, active(A), 0 s)")
        cm = m.compile()
        s = Session(cm, scenario(cm, None, [(2 * S, 0, {"q": True})]), options={"U-03": "situacion-anterior"})
        s.start()
        s.step_external()
        self.assertEqual(s.z.situation, {"A"})
        self.assertEqual(records(s, "evolucion")[1]["durationKept"], ["A"])
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["B"])
        s.advance_to(4_999_999)
        self.assertFalse(s.z.outputs["y"], "sigue contando desde 0, no desde 2 s")
        s.advance_to(5 * S)
        self.assertTrue(s.z.outputs["y"], "vence a 5 s: la duración no se interrumpió")
        m2 = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(1 s, active(A) AND p, 0 s)")
        self.assertIn("D-CAPACIDAD-NO-SOPORTADA", {d.code for d in m2.validate().diagnostics}, "base compuesta: H-09 sigue")

    def test_SH09b_etapa_que_sale_por_su_temporizador_y_reentra_no_se_estabiliza(self):
        """REQ-SEM-07, REQ-TMP-02: consecuencia de P-IMP-18; ciclo instantáneo sin fin, cortado con D-LIM-EVOL (doc. 04)."""
        m = M().var("marcha").var("fin").step("E0", True).step("E1").step("E2")
        m.trans("t1", ["E0"], ["E1"], "marcha").trans("t2", ["E1"], ["E2"], "delay(3 s, active(E1), 0 s)")
        m.trans("t3", ["E2"], ["E0"], "fin")
        cm = m.compile()
        s = Session(cm, scenario(cm, None, [(0, 0, {"marcha": True}), (1, 0, {"fin": True})]), budget=30)
        s.start()
        s.run()
        self.assertEqual((s.status, last_diag(s).code), ("pausada-recorrido", "D-LIM-EVOL"))
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")][1:7], [["t2"], ["t3"], ["t1"], ["t2"], ["t3"], ["t1"]])

    def test_SH10_leer_salida_continua(self):
        """REQ-ACT-01: hallazgo H-10, cerrado por el comparador (8.2 C): se lee según la situación del momento, también la inestable."""
        m = M().var("p").var("y", "output").var("luz", "output").step("A", True).step("B").step("C")
        m.trans("t1", ["A"], ["B"], "p").cont("B", "y").trans("t2", ["B"], ["C"], "y").cont("C", "luz")
        s = session(m.compile(), batches=[(S, 0, {"p": True})])
        s.run()
        self.assertEqual((s.z.situation, s.z.outputs["y"], s.z.outputs["luz"]), ({"C"}, False, True))
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["B"], "B es inestable: y no llega a salir")
        self.assertIn("D-CAPACIDAD-NO-SOPORTADA", {d.code for d in m.validate({"8.2": "detener"}).diagnostics})
        # Con acción limitada, la lectura respeta el límite
        m = M().var("p").var("y", "output").step("A", True).step("B").step("C")
        m.cont("A", "y", limit_us=2 * S).trans("t", ["A"], ["B"], "NOT y").trans("u", ["B"], ["C"], "p")
        s = session(m.compile(), batches=[(5 * S, 0, {"p": True})])
        s.advance_to(S)
        self.assertEqual(s.z.situation, {"A"})
        s.advance_to(3 * S)
        self.assertEqual(s.z.situation, {"B"}, "a los 2 s y deja de valer y NOT y franquea")

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
        """REQ-EVT-03, REQ-ACT-02: acción por evento en una etapa que sale con ese evento: no se ejecuta (comparador, 5.2 B)."""
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "rise(p)").stored("A", "n", "event", "n + 1", event="rise(p)")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual((s.z.situation, s.z.values["n"]), ({"B"}, 0))
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})], options={"5.2": "detener"})
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-03"))
        self.assertEqual((s.z.situation, s.z.values["n"]), ({"A"}, 0))

    def test_SU05_receptividad_lee_valor_asignado(self):
        """REQ-ACT-05, REQ-SEM-09: hoja 08, 2.3 A; la receptividad ve el valor recién asignado y sigue en el mismo instante."""
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "n = 1").stored("B", "n", "activation", "1")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual((s.z.situation, s.z.values["n"]), ({"C"}, 1))
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["t"], ["u"]])
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["B"], "B es inestable, pero su acción se ejecutó")

    def test_SU05b_asignaciones_sucesivas_vale_la_ultima(self):
        """REQ-ACT-05, REQ-ACT-02: hoja 08, 2.4 A; dos asignaciones distintas sucesivas en un instante, vale la última."""
        m = M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "true")
        m.stored("B", "z", "activation", "1").stored("C", "z", "activation", "2")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.z.values["z"], 2)
        last = records(s, "evolucion")[-1]["assignments"][0]
        self.assertEqual((last["value"], last["previous"]), ("2", "1"))

    def test_SU06_lote_y_vencimiento_coincidentes(self):
        """REQ-TMP-03: lote y vencimiento independientes en el mismo τ se procesan juntos (comparador 4.3 A; cierra H-17)."""
        m = M().var("q").var("y", "output").step("A", True).cont("A", "y", "delay(2 s, active(A), 0 s)")
        s = session(m.compile(), batches=[(2 * S, 0, {"q": True})])
        s.run()
        ctx = [r for r in records(s, "contexto") if r["timeUs"] == str(2 * S)]
        self.assertEqual([(r["stimulus"], r["batch"], r["expiring"]) for r in ctx], [("lote", "b0", ["e1"])], "un solo contexto")
        self.assertTrue(s.z.outputs["y"])
        s = session(m.compile(), batches=[(2 * S, 0, {"q": True})], options={"4.3": "detener"})
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-06"))
        self.assertFalse(s.z.outputs["y"])

    def test_SU06_delay_cero(self):
        """REQ-TMP-03: 0s/p no compila (comparador, 4.4 B); 0s/p/2s no se preguntó y sigue en U-06."""
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "delay(0 s, p, 0 s)")
        self.assertEqual([d.code for d in m.validate().diagnostics if d.blocks_start], ["D-FORMATO"])
        self.assertTrue(any(d.question == "U-06" for d in m.validate({"4.4": "detener"}).diagnostics))
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "delay(0 s, p, 2 s)")
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
        """REQ-MOD-04: fuente de nivel y transición sin lados no compilan (comparador 6.2 A y 6.4 A); con «detener», U-07."""
        m = M().var("p").step("A", True).trans("f", [], ["A"], "p").trans("n", [], [], "p")
        res = m.validate()
        self.assertEqual([(d.code, d.element) for d in res.diagnostics], [("D-FORMATO", "f"), ("D-FORMATO", "n")])
        self.assertFalse(res.can_simulate)
        res = m.validate({"6.2": "detener", "6.4": "detener"})
        self.assertEqual(sum(1 for d in res.diagnostics if d.question == "U-07"), 2)
        self.assertIsNotNone(res.model)
        self.assertFalse(res.can_simulate)

    def test_SU09_inicializacion_decidida(self):
        """REQ-SEM-01, REQ-ACT-02, REQ-TMP-02: hoja 08, 1.1 A, 1.2 A y 1.3 A (U-09 cerrada por el responsable)."""
        # 1.2 A: situación inicial inestable → evoluciona en τ=0; A queda inestable
        m = M().var("p").var("y", "output").step("A", True).step("B").trans("t", ["A"], ["B"], "p").cont("A", "y")
        s = session(m.compile(), init={"p": True})
        self.assertEqual((s.z.situation, s.z.time, s.z.outputs["y"]), ({"B"}, 0, False))
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["A"])
        # 1.1 A: acción al activar una etapa inicial, ejecutada al arrancar (evolución 0)
        m = M().var("z", "internal").step("A", True).stored("A", "z", "activation", "true")
        s = session(m.compile())
        self.assertTrue(s.z.values["z"])
        self.assertEqual(records(s, "evolucion")[0]["evolutionIndex"], 0)
        # 1.1 A + 1.2 A: la receptividad inicial ve el valor asignado al arrancar (2.3 A)
        m = M().var("n", "internal", "int").step("A", True).step("B").stored("A", "n", "activation", "1")
        m.trans("t", ["A"], ["B"], "n = 1")
        self.assertEqual(session(m.compile()).z.situation, {"B"})
        # 1.3 A: temporizador sobre una entrada ya verdadera al arrancar cuenta desde τ=0
        m = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(1 s, p, 0 s)")
        s = session(m.compile(), init={"p": True})
        s.advance_to(999_999)
        self.assertFalse(s.z.outputs["y"])
        s.advance_to(1 * S)
        self.assertTrue(s.z.outputs["y"])
        # Sin flancos inventados: una entrada que vale 1 al arrancar no produce ↑p (doc. 05)
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "rise(p)")
        self.assertEqual(session(m.compile(), init={"p": True}).z.situation, {"A"})


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

    def test_SOPT03a_por_defecto_situacion_anterior(self):
        """REQ-EVT-03, REQ-SEM-09, REQ-NOR-02: por defecto, la respuesta 5.1 («situación anterior»); «detener» sigue disponible."""
        s = self._u03()
        self.assertEqual((s.status, s.z.situation), ("finalizada", {"B"}))
        self.assertEqual(s.trace.header["semanticProfile"]["options"]["U-03"], "situacion-anterior")
        s = self._u03("detener")
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-03"))
        self.assertEqual(s.trace.header["semanticProfile"]["options"]["U-03"], "detener")

    def test_SOPT03b_lectura_situacion_anterior(self):
        """REQ-EVT-03, REQ-SEM-09, REQ-SIM-05: el evento solo franquea lo validado antes de él → B, con hipótesis en la traza."""
        s = self._u03("situacion-anterior")
        self.assertEqual((s.status, s.z.situation), ("finalizada", {"B"}))
        hyp = records(s, "estable")[-1]["hypotheses"]
        self.assertEqual(hyp, [{"question": "U-03", "reading": "situacion-anterior", "transition": "u",
                                "evolutionIndex": 2, "receptivity": False}])
        self.assertEqual(s.trace.header["semanticProfile"]["options"]["U-03"], "situacion-anterior")
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
        self.assertEqual([x for x in records(r, "estable") if x["timeUs"] == str(S)], [], "sin estabilidad publicada")

    def test_SOPT03d_instantanea_exige_la_misma_lectura(self):
        """REQ-SIM-04, REQ-DAT-04: no se mezclan instantáneas de lecturas distintas."""
        s = self._u03("recorrido")
        snap = s.snapshot("con-hipotesis")
        with self.assertRaises(DiagnosticError) as ctx:
            Session.restore(s.cm, s.scenario, snap)
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-INSTANTANEA-INCOMPATIBLE")
        r = Session.restore(s.cm, s.scenario, snap, options={"U-03": "recorrido"})
        self.assertEqual(r.z.situation, {"C"})

    def test_SOPT03e_limites_de_la_opcion(self):
        """REQ-MOD-04, REQ-EVT-03: valores no admitidos se rechazan; la repetición de fuentes la decide 6.3, no U-03."""
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
        self.assertEqual(s.z.situation, {"X", "A", "B"}, "6.3 A: una vez por flanco, también con «recorrido»")
        s = Session(cm, scenario(cm, None, [(1 * S, 0, {"p": True})]), options={"U-03": "recorrido", "6.3": "detener"})
        s.start()
        s.run()
        self.assertEqual(q(s), ("D-SEM-PENDIENTE", "U-07"))


class ConflictosAlCompilar(unittest.TestCase):
    """P-IMP-16 (decisión del responsable de producto): un conflicto de escritura seguro impide compilar."""

    def _codes(self, m):
        res = m.validate()
        return [d for d in res.diagnostics if d.code == "D-ESCRITURA-CONFLICTO"], res

    def test_SESC01_conflictos_seguros_no_compilan(self):
        """REQ-ACT-03, REQ-EDT-09: activación/activación, desactivación/desactivación, activación/desactivación y misma etapa."""
        base = lambda: M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C")
        m = base().trans("t", ["A"], ["B", "C"], "p")
        m.stored("B", "z", "activation", "1").stored("C", "z", "activation", "2")
        m2 = base().trans("t", ["A", "B"], ["C"], "p")
        m2.stored("A", "z", "deactivation", "1").stored("B", "z", "deactivation", "2")
        m3 = base().trans("t", ["A"], ["B"], "p")
        m3.stored("A", "z", "deactivation", "1").stored("B", "z", "activation", "2")
        m4 = base().trans("t", ["A"], ["B"], "p")
        m4.stored("B", "z", "activation", "1").stored("B", "z", "activation", "-1")
        m5 = base().trans("t", ["A"], ["B"], "p")
        m5.stored("A", "z", "event", "1", event="rise(p)").stored("A", "z", "event", "2", event="rise(p)")
        m6 = base().trans("t", ["A"], ["B", "C"], "p")  # hoja 08, 2.1 C: dos incrementos simultáneos
        m6.stored("B", "z", "activation", "z + 1").stored("C", "z", "activation", "z + 1")
        for i, mm in enumerate((m, m2, m3, m4, m5, m6), 1):
            diags, res = self._codes(mm)
            self.assertEqual(len(diags), 1, f"caso {i}: {[str(d) for d in res.diagnostics]}")
            self.assertEqual(diags[0].severity, "error")
            self.assertFalse(res.can_simulate, f"caso {i} no debe compilar")
        m7 = M().var("p").var("x", "internal", "int").var("y", "internal", "int").step("A", True).step("B")
        m7.trans("t", ["A"], ["B"], "p").stored("B", "x", "activation", "y").stored("B", "y", "activation", "x")
        res = m7.validate()  # hoja 08, 2.2 B: dependencia cruzada
        self.assertIn("D-DEPENDENCIA-CRUZADA", {d.code for d in res.diagnostics})
        self.assertFalse(res.can_simulate)

    def test_SESC02_no_son_conflictos_seguros(self):
        """REQ-ACT-03, REQ-ACT-05: la misma constante, etapas en secuencia y eventos distintos no impiden compilar."""
        base = lambda: M().var("p").var("q").var("z", "internal", "int").step("A", True).step("B").step("C")
        iguales = base().trans("t", ["A"], ["B", "C"], "p")
        iguales.stored("B", "z", "activation", "2").stored("C", "z", "activation", "2")
        secuencia = base().trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "q")
        secuencia.stored("B", "z", "activation", "1").stored("C", "z", "activation", "2")
        eventos_distintos = base().trans("t", ["A"], ["B"], "p")
        eventos_distintos.stored("A", "z", "event", "1", event="rise(p)").stored("A", "z", "event", "2", event="rise(q)")
        for mm in (iguales, secuencia, eventos_distintos):
            diags, res = self._codes(mm)
            self.assertEqual(diags, [])
            self.assertTrue(res.can_simulate, [str(d) for d in res.diagnostics])


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
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B")  # 6.1 A: sin etapa inicial no compila; el estado declarado manda
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
        self.assertTrue({"eventos.internos", "eventos.franqueamiento", "temporal.delay-cero"} <= excluded,
                        "cuestiones aún abiertas")
        for cid in ("jerarquia.forzado-momento", "jerarquia.encapsulacion-coincidencia", "jerarquia.macro-inicial",
                    "jerarquia.forzado-tiempo", "jerarquia.forzado-recinto", "jerarquia.forzado-acciones",
                    "jerarquia.macro-ramas"):
            self.assertNotIn(cid, excluded, "decididas por el responsable (P-IMP-24 a P-IMP-26)")
        for cid in ("jerarquia.forzado", "jerarquia.macroetapas", "jerarquia.encapsulacion"):  # documento 06, I (P-IMP-23)
            self.assertNotIn(cid, excluded)
        caps = {c["id"]: c for c in decl["capabilities"]}
        decided = {"inicio.inestable": "hoja 08", "acciones.lecturas-contexto": "hoja 08", "eventos.recorrido": "comparador",
                   "permanencia.efectos": "comparador", "temporal.coincidencias": "comparador",
                   "transiciones.fuente-repeticion": "comparador"}
        for cid, where in decided.items():  # cerradas por el responsable
            self.assertNotIn(cid, excluded)
            self.assertEqual(caps[cid]["status"], "provisional", "decidida, pero sin contraste normativo (U-01)")
            self.assertIn(where, caps[cid]["reason"])
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
