"""Casos T-09 a T-16 del documento 11: expresiones, eventos, tiempo y acciones."""
import tempfile
import unittest
from pathlib import Path

from helpers import M, S, declared, last_diag, records, scenario, session, us

from grafcet import expressions as ex
from grafcet.canonical import digest
from grafcet.diagnostics import DiagnosticError
from grafcet.engine import State, _Env
from grafcet.persistence import add_document, new_project, open_project, save_project
from grafcet.scenario import load_scenario
from grafcet.timeutil import parse_duration, parse_time_field


def codes(res):
    return {d.code for d in res.diagnostics}


class Expresiones(unittest.TestCase):
    def test_T09a_precedencia(self):
        m = M().var("a").var("b").var("c").step("A", True).step("B").step("C", True).step("D")
        m.trans("t1", ["A"], ["B"], "a OR b AND c").trans("t2", ["C"], ["D"], "(a OR b) AND c")
        cm = m.compile()
        # Evaluación pura sobre un estado fijo (a=true haría franquear t1 si evolucionara)
        z = State(frozenset({"A", "C"}), {"a": True, "b": False, "c": False}, {}, {}, {}, {}, 0, 0, 0)
        env = _Env(cm, z, None)
        self.assertTrue(ex.evaluate(cm.exprs[m.doc["transitions"][0]["conditionRef"]].node, env))
        self.assertFalse(ex.evaluate(cm.exprs[m.doc["transitions"][1]["conditionRef"]].node, env))
        self.assertNotEqual(m.doc["expressions"][0]["meaning"], m.doc["expressions"][1]["meaning"])

    def test_T09b_unidades_y_tipos(self):
        m = M().var("L", "input", "int", unit="m").var("T", "input", "int", unit="°C").var("n", "internal", "int")
        m.step("A", True).step("B").trans("t", ["A"], ["B"], "L > T").stored("B", "n", "activation", "true")
        res = m.validate()
        self.assertIn("D-UNIDAD", codes(res))
        self.assertIn("D-TIPO", codes(res))
        self.assertFalse(res.can_simulate)

    def test_T09c_texto_pendiente_y_divergencia_se_guardan(self):
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "depósito preparado", descriptive=True)
        res = m.validate()
        self.assertIn("D-EXP-PENDIENTE", codes(res))
        self.assertFalse(res.can_simulate)
        e = m.doc["expressions"][0]
        e.update(mode="executable", text="p", bindings={"p": "p"},
                 meaning={"operator": "not", "operands": [{"operator": "ref", "reference": "p"}]})
        res = m.validate()
        self.assertIn("D-EXP-DIVERGENTE", codes(res))
        self.assertFalse(res.can_simulate)
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "T-09c")
            add_document(pj, m.doc)
            save_project(Path(tmp), pj)
            back = open_project(Path(tmp)).models()[0]
        self.assertEqual(back["expressions"][0], e, "se conservan texto y significado divergentes")

    def test_T09d_observar_no_modifica_estado(self):
        m = M().var("n", "internal", "int").var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "n > 3 AND p")
        s = declared(m.compile(), ["A"], values={"n": 4})
        before = digest(s.z.to_dict(s.cm, s.pending()))
        nrec = len(s.trace.records)
        for _ in range(100):
            obs = s.observe()
        self.assertEqual(digest(s.z.to_dict(s.cm, s.pending())), before)
        self.assertEqual(len(s.trace.records), nrec)
        self.assertEqual(s.z.values["n"], 4)
        self.assertEqual(obs["timeUs"], "0")


class Eventos(unittest.TestCase):
    def test_T10a_sin_flanco_al_arrancar(self):
        cm = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "rise(p)").compile()
        s = session(cm, init={"p": True}, batches=[(1 * S, 0, {"p": False}), (2 * S, 0, {"p": True})])
        self.assertEqual(s.z.situation, {"A"})
        s.step_external()
        self.assertEqual(s.z.situation, {"A"})
        s.step_external()
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["t"]])
        self.assertEqual(records(s, "evolucion")[0]["timeUs"], str(2 * S))
        self.assertEqual(s.z.situation, {"B"})

    def _t10b(self, batches):
        m = M().var("p").var("q").step("A", True).step("B").step("C", True).step("D")
        m.trans("t", ["A"], ["B"], "rise(p OR q)").trans("u", ["C"], ["D"], "fall(p OR q)")
        s = session(m.compile(), init={"p": True}, batches=batches)
        s.run()
        return s

    def test_T10b_lote_simultaneo_frente_a_lotes_ordenados(self):
        s = self._t10b([(1 * S, 0, {"p": False, "q": True})])
        self.assertEqual([r["events"] for r in records(s, "contexto")], [[]])
        self.assertEqual(s.z.situation, {"A", "C"})
        s = self._t10b([(1 * S, 0, {"p": False}), (1 * S, 1, {"q": True})])
        ctx = records(s, "contexto")
        self.assertEqual([(r["batchOrdinal"], r["events"]) for r in ctx], [(0, ["e2"]), (1, ["e1"])])
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["u"], ["t"]])

    def test_T10c_flanco_no_se_retiene(self):
        m = M().var("p").var("q").step("A").step("B").step("C", True)
        m.trans("t", ["A"], ["B"], "rise(p)").trans("u", ["C"], ["A"], "q")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True}), (2 * S, 0, {"q": True})])
        s.run()
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["u"]])
        self.assertEqual(s.z.situation, {"A"})

    def test_T10d_alcance_causal_del_evento_bloqueo_U03(self):
        m = M().var("p").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "rise(p)").trans("u", ["B"], ["C"], "rise(p)")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        d = last_diag(s)
        self.assertEqual((d.code, d.question), ("D-SEM-PENDIENTE", "U-03"))
        self.assertEqual(s.z.situation, {"A"}, "ni B ni C: no se elige alternativa")

    def test_T10e_fuentes_por_evento_primera_evolucion_y_repeticion_U07(self):
        m = M().var("p").step("X", True).step("A").step("B")
        m.trans("t", [], ["A"], "rise(p)").trans("u", [], ["B"], "rise(p)")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(records(s, "evolucion")[0]["cleared"], ["t", "u"], "ambas reciben el mismo evento")
        self.assertEqual(last_diag(s).question, "U-07", "la repetición en el contexto queda pendiente")

    def test_T11a_permanencia_y_franqueamiento_separados_bloqueo_U04(self):
        m = M().var("p").var("n", "internal", "int").var("mm", "internal", "int").step("A").step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "p")
        m.stored("B", "n", "activation", "n + 1").stored("B", "mm", "deactivation", "mm + 1")
        s = declared(m.compile(), ["A", "B"], batches=[(1 * S, 0, {"p": True})])
        s.run()
        fallo = records(s, "fallo")[-1]
        self.assertEqual(fallo["proposedSet"], ["t", "u"], "E contiene t y u en la primera evolución")
        self.assertEqual(last_diag(s).question, "U-04")

    def test_T11b_evento_de_franqueamiento_bloqueo_U03(self):
        m = M().var("p").var("z", "internal").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "true")
        m.stored("C", "z", "event", "true", event="rise(p)", sources=["t"])
        res = m.validate()
        self.assertTrue(any(d.code == "D-SEM-PENDIENTE" and d.question == "U-03" for d in res.diagnostics))
        self.assertFalse(res.can_simulate)


class Tiempo(unittest.TestCase):
    def test_T12a_retardo_exacto_sin_cuantizacion(self):
        cm = M().step("A", True).step("B").trans("t", ["A"], ["B"], "delay(2 s, active(A), 0 s)").compile()
        s = session(cm)
        s.advance_to(1_999_999)
        self.assertEqual(s.z.situation, {"A"})
        s.advance_to(2_000_000)
        evo = records(s, "evolucion")
        self.assertEqual((evo[0]["cleared"], evo[0]["timeUs"]), (["t"], "2000000"))
        self.assertEqual(s.z.situation, {"B"})
        s.advance_to(2_000_001)
        self.assertEqual(s.z.situation, {"B"})

    def test_T12b_pulso_breve_no_activa(self):
        cm = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "delay(2 s, p, 0 s)").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True}), (2 * S, 0, {"p": False}), (3 * S, 0, {"p": True})])
        s.advance_to(4_999_999)
        self.assertEqual(s.z.situation, {"A"})
        self.assertFalse(list(s.z.temporal.values())[0].value)
        s.advance_to(5 * S)
        self.assertEqual(records(s, "evolucion")[0]["timeUs"], str(5 * S))
        self.assertEqual(s.z.situation, {"B"})

    def test_T12c_accion_limitada(self):
        cm = M().var("y", "output").step("A", True).cont("A", "y", limit_us=2 * S).compile()
        s = session(cm)
        self.assertTrue(s.z.outputs["y"])
        s.advance_to(1_999_999)
        self.assertTrue(s.z.outputs["y"])
        s.advance_to(2_000_000)
        self.assertFalse(s.z.outputs["y"])
        cm0 = M().var("y", "output").step("A", True).cont("A", "y", limit_us=0).compile()
        self.assertFalse(session(cm0).z.outputs["y"], "duración cero: sin pulso")

    def test_T12d_tiempo_exacto_rechazos(self):
        for text in ("0.1 us", "-1 s"):
            with self.assertRaises(DiagnosticError) as ctx:
                parse_duration(text)
            self.assertEqual(ctx.exception.diagnostics[0].code, "D-NUM")
        with self.assertRaises(DiagnosticError):
            parse_time_field(str(2**63))
        self.assertEqual(parse_duration("1 us"), 1)
        self.assertEqual(parse_time_field(str(2**63 - 1)), 2**63 - 1)

    def test_T12e_retardo_de_conexion_y_desconexion(self):
        cm = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(1.5 s, p, 2 s)").compile()
        s = session(cm, batches=[(2 * S, 0, {"p": True}), (8 * S, 0, {"p": False})])
        for t, expected in ((3_499_999, False), (3_500_000, True), (9_999_999, True), (10 * S, False)):
            s.advance_to(t)
            self.assertEqual(s.z.outputs["y"], expected, f"y en {t} µs")

    def test_T12f_reentrada_inicia_intervalo_nuevo(self):
        m = M().var("p").var("q").var("y", "output").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["A"], "q").cont("A", "y", "delay(3 s, active(A), 0 s)")
        s = session(m.compile(), batches=[(2 * S, 0, {"p": True}), (2_500_000, 0, {"p": False}),
                                           (4 * S, 0, {"q": True}), (4_500_000, 0, {"q": False})])
        s.advance_to(6_999_999)
        self.assertFalse(s.z.outputs["y"])
        s.advance_to(7 * S)
        self.assertTrue(s.z.outputs["y"])
        self.assertEqual(s.z.situation, {"A"})

    def test_T13a_lote_con_dos_escrituras(self):
        cm = M().var("p").step("A", True).compile()
        base = scenario(cm).doc
        bad = dict(base, batches=[{"id": "b1", "timeUs": str(S), "ordinalAtTime": 0, "origin": "escenario",
                                    "changes": [{"variableRef": "p", "value": False}, {"variableRef": "p", "value": True}]}])
        sc, diags = load_scenario(bad, cm)
        self.assertIsNone(sc)
        self.assertIn("D-LOTE", {d.code for d in diags})
        ok = dict(base, batches=[{"id": "b1", "timeUs": str(S), "ordinalAtTime": 0, "origin": "escenario",
                                   "changes": [{"variableRef": "p", "value": False}]},
                                  {"id": "b2", "timeUs": str(S), "ordinalAtTime": 1, "origin": "escenario",
                                   "changes": [{"variableRef": "p", "value": True}]}])
        sc, diags = load_scenario(ok, cm)
        self.assertEqual([(b.time, b.ordinal) for b in sc.batches], [(S, 0), (S, 1)])

    def test_T13b_caida_exacta_en_el_vencimiento_bloqueo(self):
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "delay(2 s, p, 0 s)")
        cm = m.compile()
        s = session(cm, init={"p": True}, start=False)
        self.assertEqual({d.question for d in s.start()}, {"U-09"}, "p verdadera desde el inicio: U-09")
        s = session(cm, batches=[(0, 0, {"p": True}), (2 * S, 0, {"p": False})])
        s.run()
        self.assertEqual((last_diag(s).code, last_diag(s).question), ("D-SEM-PENDIENTE", "U-06"))
        self.assertEqual(s.z.situation, {"A"})

    def test_T13c_rebote_durante_desconexion_bloqueo_U06(self):
        cm = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(1 s, p, 2 s)").compile()
        s = session(cm, batches=[(0, 0, {"p": True}), (3 * S, 0, {"p": False}), (4 * S, 0, {"p": True})])
        s.run()
        self.assertEqual((last_diag(s).code, last_diag(s).question), ("D-SEM-PENDIENTE", "U-06"))
        self.assertEqual(s.z.time, 3 * S, "se conserva el último estado estable")

    def test_T13d_vencimientos_simultaneos_misma_frontera(self):
        m = M().step("A", True).step("B").step("C", True).step("D")
        m.trans("t", ["A"], ["B"], "delay(2 s, active(A), 0 s)").trans("u", ["C"], ["D"], "delay(2 s, active(C), 0 s)")
        s = session(m.compile())
        s.run()
        evo = records(s, "evolucion")
        self.assertEqual([(e["cleared"], e["timeUs"]) for e in evo], [(["t", "u"], "2000000")])
        self.assertEqual(s.z.situation, {"B", "D"})


class Acciones(unittest.TestCase):
    def test_T14a_disyuncion_de_contribuciones(self):
        m = M().var("p").var("q").var("r").var("y", "output").step("A", True).step("B", True).step("C")
        m.cont("A", "y", "p", aid="aA").cont("B", "y", "q", aid="aB").trans("t", ["B"], ["C"], "r")
        s = session(m.compile(), init={"q": True}, batches=[(1 * S, 0, {"r": True})])
        self.assertTrue(s.z.outputs["y"])
        self.assertEqual(s.z.contributors["y"], ["aB"])
        s.run()
        self.assertFalse(s.z.outputs["y"], "retirar B deja y=false; no «última acción gana»")

    def test_T14b_continua_sin_memoria(self):
        cm = M().var("p").var("y", "output").step("A", True).cont("A", "y", "p").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True}), (2 * S, 0, {"p": False})])
        seen = [s.z.outputs["y"]]
        while s.next_stimulus() is not None:
            s.step_external()
            seen.append(s.z.outputs["y"])
        self.assertEqual(seen, [False, True, False])

    def test_T14c_condicion_continua_con_evento(self):
        m = M().var("p").var("y", "output").step("A", True).cont("A", "y", "rise(p)")
        self.assertIn("D-TIPO-EVENTO", codes(m.validate()))
        # Segunda parte (etapa virtual sin pulso efectivo): ver T-07a.

    def test_T15a_memorizada_conserva_valor(self):
        m = M().var("p").var("q").var("z", "internal").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "q").stored("B", "z", "activation", "true")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True}), (2 * S, 0, {"q": True})])
        s.step_external()
        self.assertTrue(s.z.values["z"])
        s.step_external()
        self.assertEqual(s.z.situation, {"C"})
        self.assertTrue(s.z.values["z"])

    def test_T15b_accion_por_evento_cuenta_eventos_reales(self):
        m = M().var("p").var("n", "internal", "int").step("A", True)
        m.stored("A", "n", "event", "n + 1", event="rise(p)")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True}), (2 * S, 0, {"p": False}), (3 * S, 0, {"p": True})])
        got = []
        for _ in range(3):
            s.step_external()
            for _ in range(5):
                s.observe()  # observar o «repintar» no cuenta
            got.append(s.z.values["n"])
        self.assertEqual(got, [1, 1, 2])

    def test_T15c_lecturas_cruzadas_bloqueo_U05(self):
        m = M().var("p").var("x", "internal", "int").var("yv", "internal", "int").step("A").step("B")
        m.trans("t", ["A"], ["B"], "p").stored("B", "x", "activation", "yv").stored("B", "yv", "activation", "x")
        s = declared(m.compile(), ["A"], values={"x": 2, "yv": 5}, batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual((last_diag(s).code, last_diag(s).question), ("D-SEM-PENDIENTE", "U-05"))
        self.assertEqual((s.z.values["x"], s.z.values["yv"]), (2, 5))

    def _two_writers(self, v1, v2, expr=False):
        m = M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B", "C"], "p")
        m.stored("B", "z", "activation", v1, aid="aB").stored("C", "z", "activation", v2, aid="aC")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        return s

    def test_T16a_conflicto_de_escritura(self):
        s = self._two_writers("1", "2")
        d = last_diag(s)
        self.assertEqual(d.code, "D-ESCRITURA-CONFLICTO")
        self.assertIn("aB=1", d.evidence["propuestas"])
        self.assertIn("aC=2", d.evidence["propuestas"])
        self.assertEqual(s.z.values["z"], 0, "ningún valor final arbitrario")

    def test_T16b_escrituras_iguales(self):
        s = self._two_writers("2", "2")
        self.assertEqual(s.z.values["z"], 2)
        self.assertEqual(records(s, "evolucion")[0]["assignments"], [{"target": "z", "value": "2", "authors": ["aB", "aC"]}])

    def test_T16c_modos_mezclados(self):
        m = M().var("y", "output").step("A", True).step("B").cont("A", "y").stored("B", "y", "activation", "true")
        self.assertIn("D-MODO-SALIDA", codes(m.validate()))

    def test_T16d_dos_incrementos_bloqueo_U05(self):
        s = self._two_writers("z + 1", "z + 1")
        self.assertEqual((last_diag(s).code, last_diag(s).question), ("D-SEM-PENDIENTE", "U-05"))
        self.assertEqual(s.z.values["z"], 0)


if __name__ == "__main__":
    unittest.main()
