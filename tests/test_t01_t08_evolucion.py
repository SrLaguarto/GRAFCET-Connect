"""Casos T-01 a T-08 del documento 11 (evolución).

Oráculos I = provisionales (U-01): que pasen no demuestra conformidad. Casos B = se
comprueba que la implementación se detiene con D-SEM-PENDIENTE y nombra la U; el
oráculo semántico sigue abierto.
"""
import unittest

from helpers import M, S, declared, last_diag, records, session

from grafcet.engine import Session
from grafcet.trace import semantic_view


class Evolucion(unittest.TestCase):
    def test_T01a_situacion_inicial_explicita(self):
        cm = M().step("A", True).step("B").step("C", True).compile()
        s = session(cm)
        self.assertEqual(s.z.situation, {"A", "C"})
        self.assertNotIn("B", s.z.situation)
        self.assertEqual(records(s, "evolucion"), [])

    def test_T01b_orden_de_archivo_irrelevante(self):
        cm = M().step("B").step("C", True).step("A", True).compile()
        self.assertEqual(session(cm).z.situation, {"A", "C"})

    def test_T01c_restaurar_conserva_memoria_reiniciar_la_pone_a_cero(self):
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B").trans("t", ["A"], ["B"], "p")
        m.stored("B", "n", "activation", "7")
        cm = m.compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.z.values["n"], 7)
        snap = s.snapshot("snap1")
        r = Session.restore(cm, s.scenario, snap)
        self.assertEqual(r.z.values["n"], 7)
        n2 = s.restart("run-2")
        self.assertEqual(n2.z.values["n"], 0)
        self.assertNotEqual(n2.trace.header["runId"], s.trace.header["runId"])
        self.assertTrue(records(s, "evolucion"), "la traza anterior se conserva")

    def test_T01d_sin_iniciales_bloqueo_U07(self):
        for m in (M().step("A").step("B").var("p").trans("t", ["A"], ["B"], "p"),
                  M().step("A").var("p").trans("f", [], ["A"], "rise(p)")):
            cm = m.compile()
            s = session(cm, start=False)
            diags = s.start()
            self.assertEqual(s.status, "error")
            self.assertIsNone(s.z, "no se inventa una etapa inicial")
            self.assertTrue(any(d.code == "D-SEM-PENDIENTE" and d.question == "U-07" for d in diags))

    def test_T02a_receptividad_sin_validacion(self):
        cm = M().var("p").step("A").step("B").trans("t", ["A"], ["B"], "p").compile()
        s = declared(cm, [], batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.z.situation, frozenset())
        self.assertEqual(records(s, "evolucion"), [])
        o = s.observe()["transitions"]["t"]
        self.assertEqual((o["receptivity"], o["validated"], o["fireable"]), (True, False, False))

    def test_T02b_validacion_sin_receptividad(self):
        cm = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p").compile()
        s = session(cm)
        o = s.observe()["transitions"]["t"]
        self.assertEqual((o["validated"], o["receptivity"], o["fireable"]), (True, False, False))
        self.assertEqual(s.z.situation, {"A"})

    def test_T02c_franqueamiento_inmediato(self):
        cm = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.step_external()
        evo = records(s, "evolucion")
        self.assertEqual([e["cleared"] for e in evo], [["t"]])
        self.assertEqual(evo[0]["timeUs"], str(1 * S))
        self.assertEqual(s.z.situation, {"B"})

    def test_T03a_divergencia_en_y_activa_el_conjunto(self):
        cm = M().var("p").step("A", True).step("B").step("C").trans("t", ["A"], ["B", "C"], "p").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.run()
        evo = records(s, "evolucion")
        self.assertEqual(len(evo), 1)
        self.assertEqual(evo[0]["situation"], ["B", "C"])

    def test_T03b_sincronizacion_desactiva_conjuntamente(self):
        cm = M().var("p").step("A", True).step("B", True).step("C").step("D") \
            .trans("t", ["A", "B"], ["C", "D"], "p").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.run()
        evo = records(s, "evolucion")[0]
        self.assertEqual((evo["deactivated"], evo["activated"]), (["A", "B"], ["C", "D"]))
        self.assertEqual(s.z.situation, {"C", "D"})

    def test_T03c_transicion_sumidero(self):
        cm = M().var("p").step("A", True).trans("t", ["A"], [], "p").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.z.situation, frozenset())
        cm2 = M().var("p").step("A", True).step("B", True).trans("t", ["A"], [], "p").compile()
        s2 = session(cm2, batches=[(1 * S, 0, {"p": True})])
        s2.run()
        self.assertEqual(s2.z.situation, {"B"}, "la etapa sumidero B permanece si ya estaba activa")

    def test_T03d_rama_no_recorrida_no_contribuye(self):
        m = M().var("p").var("q").var("r").var("y", "output").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["C"], "p").trans("u", ["A"], ["B"], "q").trans("v", ["B"], ["C"], "r").cont("B", "y")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["t"]])
        self.assertEqual(s.z.situation, {"C"})
        self.assertFalse(s.z.outputs["y"])

    def test_T04a_transiciones_independientes_simultaneas(self):
        cm = M().var("p").step("A", True).step("B").step("C", True).step("D") \
            .trans("t", ["A"], ["B"], "p").trans("u", ["C"], ["D"], "p").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.run()
        evo = records(s, "evolucion")
        self.assertEqual([e["cleared"] for e in evo], [["t", "u"]])
        self.assertEqual(s.z.situation, {"B", "D"})

    def test_T04b_sin_exclusion_automatica(self):
        cm = M().var("p").var("q").step("A", True).step("B").step("C") \
            .trans("t", ["A"], ["B"], "p").trans("u", ["A"], ["C"], "q").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True, "q": True})])
        s.run()
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["t", "u"]])
        self.assertEqual(s.z.situation, {"B", "C"})

    def test_T04c_presentacion_orden_y_parciales_no_cambian_observables(self):
        def build(reverse: bool, split: bool):
            m = M()
            if split:
                m.partial("g2")
            items = [("A", True, "g"), ("B", False, "g2" if split else "g"), ("C", False, "g")]
            for sid, ini, part in (reversed(items) if reverse else items):
                m.step(sid, ini, partial=part)
            m.var("q").var("p")
            if reverse:
                m.doc["variables"].reverse()
            trs = [("t", ["A"], ["B"], "p"), ("u", ["A"], ["C"], "q")]
            for tid, pre, post, c in (reversed(trs) if reverse else trs):
                m.trans(tid, pre, post, c)
            for s in m.doc["steps"]:
                s["label"] = ("Etapa " if reverse else "E") + s["id"]
            return m.compile()
        views = []
        for rev, split in ((False, False), (True, False), (True, True)):
            s = session(build(rev, split), batches=[(1 * S, 0, {"p": True, "q": True})])
            s.run()
            views.append(semantic_view(s.trace.records))
        self.assertEqual(views[0], views[1])
        self.assertEqual(views[0], views[2])

    def test_T05a_permanencia_activa(self):
        cm = M().var("p").step("A", True).step("B", True).step("C") \
            .trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "p").compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.run()
        first = records(s, "evolucion")[0]
        self.assertEqual(first["cleared"], ["t", "u"])
        self.assertEqual(first["permanent"], ["B"])
        self.assertEqual(first["situation"], ["B", "C"])
        # El «cierre posterior» se evalúa aparte (oráculo de T-05a); se registra como observación.

    def test_T05b_efectos_de_permanencia_bloqueo_U04(self):
        m = M().var("p").var("n", "internal", "int").var("mm", "internal", "int").step("A").step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "p")
        m.stored("B", "n", "activation", "n + 1").stored("B", "mm", "deactivation", "mm + 1")
        s = declared(m.compile(), ["A", "B"], batches=[(1 * S, 0, {"p": True})])
        s.run()
        d = last_diag(s)
        self.assertEqual((d.code, d.question, d.element), ("D-SEM-PENDIENTE", "U-04", "B"))
        self.assertEqual(s.z.situation, {"A", "B"}, "se conserva el último estado estable")
        self.assertEqual((s.z.values["n"], s.z.values["mm"]), (0, 0))

    def test_T06a_sincronizacion_incompleta(self):
        cm = M().var("p").step("B", True).step("C").step("D").trans("t", ["B", "C"], ["D"], "p").compile()
        s = session(cm, init={"p": True})
        o = s.observe()["transitions"]["t"]
        self.assertEqual((o["validated"], o["receptivity"]), (False, True))
        self.assertNotIn("D", s.z.situation)

    def test_T06b_recorrido_hasta_sincronizar(self):
        m = M().var("r").var("q").step("B", True).step("C").step("D").step("E", True)
        m.trans("t", ["B", "C"], ["D"], "r").trans("u", ["E"], ["C"], "q")
        s = session(m.compile(), init={"r": True}, batches=[(1 * S, 0, {"q": True})])
        s.run()
        evo = records(s, "evolucion")
        self.assertEqual([e["cleared"] for e in evo], [["u"], ["t"]])
        self.assertEqual({e["timeUs"] for e in evo}, {str(1 * S)}, "τ no cambia en el recorrido")
        self.assertEqual(s.z.situation, {"D"})

    def test_T06c_paralelismo_y_sincronizacion(self):
        m = M().var("p").var("q").var("r").var("s")
        for sid in "ABCDEF":
            m.step(sid, sid == "A")
        m.trans("t1", ["A"], ["B", "C"], "p").trans("t2", ["B"], ["D"], "q").trans("t3", ["C"], ["E"], "r")
        m.trans("t4", ["D", "E"], ["F"], "s")
        s = session(m.compile(), batches=[(i * S, 0, {v: True}) for i, v in enumerate("pqrs", 1)])
        seen = []
        while s.status == "pausada-estable" and s.next_stimulus() is not None:
            s.step_external()
            seen.append(set(s.z.situation))
        self.assertEqual(seen, [{"B", "C"}, {"D", "C"}, {"D", "E"}, {"F"}])

    def test_T07a_etapa_virtual_sin_pulso(self):
        m = M().var("p").var("y", "output").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "true").cont("B", "y")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        self.assertFalse(s.z.outputs["y"])
        s.run()
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["t"], ["u"]])
        self.assertEqual(s.z.situation, {"C"})
        self.assertFalse(s.z.outputs["y"])
        self.assertFalse(any(r.get("outputs", {}).get("y") for r in s.trace.records), "ningún pulso efectivo")
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["B"])

    def test_T07b_memorizada_al_activar_etapa_virtual(self):
        m = M().var("p").var("z", "internal").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "true").stored("B", "z", "activation", "true")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertTrue(s.z.values["z"])
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["B"])

    def test_T07c_memorizada_al_desactivar_etapa_virtual(self):
        m = M().var("p").var("z", "internal").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "true").stored("B", "z", "deactivation", "true")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.run()
        self.assertTrue(s.z.values["z"])

    def test_T08a_ciclo_instantaneo_al_arrancar(self):
        """Oráculo original de T-08a, ejecutable desde la respuesta 1.2 A de la hoja 08 (cierra H-03)."""
        cm = M().step("A", True).step("B").trans("t", ["A"], ["B"], "true").trans("u", ["B"], ["A"], "true").compile()
        s = session(cm, budget=20, start=False)
        diags = s.start()
        self.assertEqual([d.code for d in diags], ["D-LIM-EVOL"])
        self.assertEqual(s.status, "pausada-recorrido")
        self.assertEqual(s.z.time, 0, "τ = 0")
        self.assertEqual(records(s, "estable"), [], "no hay resultado estable")
        self.assertEqual(len(records(s, "evolucion")), 20, "evidencia del recorrido")
        self.assertEqual(len(records(s, "limite")), 1, "evidencia del límite")

    def test_T08b_espera_estable_no_es_divergencia(self):
        cm = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p").compile()
        s = session(cm, horizon=10 * S)
        s.run()
        self.assertEqual(s.status, "finalizada")
        self.assertFalse(any(d.code == "D-LIM-EVOL" for d in s.diagnostics))
        self.assertEqual(s.z.situation, {"A"})


if __name__ == "__main__":
    unittest.main()
