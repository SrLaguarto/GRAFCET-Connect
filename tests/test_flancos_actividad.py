"""Flancos sobre actividad (U-03, decisión del responsable, chat 20-11-2026): ↑X y ↓X solo valen en la evolución
inmediatamente siguiente a la que cambió el operando. Pruebas SFA…; la primera línea de cada docstring lista los
requisitos que cubre."""
import unittest

from helpers import M, S, last_diag, records, session


def codes(res):
    return {(d.code, d.question) for d in res.diagnostics}


class FlancosActividad(unittest.TestCase):
    def test_SFA01_recinto_activacion_encapsulada(self):
        """REQ-EVT-03, REQ-JER-03: al activarse la encapsulante 72, su etapa de activación 60 pasa a 61 con ↑X72."""
        m = M().partial("R").var("p")
        m.step("A", True).step("H72", kind="enclosing")
        m.step("E60", partial="R").step("E61", partial="R")
        m.trans("t", ["A"], ["H72"], "p").trans("u", ["E60"], ["E61"], "rise(active(H72))", partial="R")
        m.enclosure("H72", "R", ["E60"])
        cm = m.compile()
        s = session(cm, batches=[(S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.z.situation, {"H72", "E61"})
        ev = records(s, "evolucion")
        self.assertEqual([e["cleared"] for e in ev], [["t"], ["u"]], "u franquea en la evolución siguiente")

    def _fin_ciclo(self, init_c, c_tarde=False):
        m = M().partial("h").var("p").var("c")
        m.step("S4", True).step("S0")
        m.step("S101b", True, partial="h").step("S100", partial="h")
        m.trans("t40", ["S4"], ["S0"], "p").trans("t04", ["S0"], ["S4"], "NOT p AND false")
        m.trans("t101", ["S101b"], ["S100"], "c AND fall(active(S4))", partial="h")
        batches = [(S, 0, {"p": True})]
        if c_tarde:
            batches.append((2 * S, 0, {"c": True}))
        return session(m.compile(), init={"c": init_c}, batches=batches)

    def test_SFA02_fin_de_ciclo_c_y_flanco_descendente(self):
        """REQ-EVT-03: con c, 101b→100 se franquea justo tras 4→0; si c llega más tarde, ya no."""
        s = self._fin_ciclo(True)
        s.run()
        self.assertEqual(s.z.situation, {"S0", "S100"})
        s = self._fin_ciclo(False, c_tarde=True)
        s.run()
        self.assertEqual(s.z.situation, {"S0", "S101b"}, "el flanco no se guarda para contextos posteriores")

    def test_SFA03_sin_flanco_al_arrancar(self):
        """REQ-EVT-03, REQ-SEM-01: las etapas iniciales no producen ↑X al arrancar."""
        m = M().step("A", True).step("B").trans("t", ["A"], ["B"], "rise(active(A))")
        s = session(m.compile())
        self.assertEqual(s.z.situation, {"A"})
        m = M().step("A", True).step("B").trans("t", ["A"], ["B"], "fall(active(B))")
        self.assertEqual(session(m.compile()).z.situation, {"A"})

    def test_SFA04_solo_la_evolucion_inmediata(self):
        """REQ-EVT-03: el flanco no vale en evoluciones posteriores ni en contextos posteriores."""
        m = M().partial("h").var("p").var("q")
        m.step("A", True).step("B").step("C")
        m.step("D", True, partial="h").step("E", partial="h").step("F", partial="h")
        m.trans("t1", ["A"], ["B"], "p").trans("t2", ["B"], ["C"], "true")
        m.trans("u1", ["D"], ["E"], "rise(active(B))", partial="h").trans("u2", ["E"], ["F"], "rise(active(B))", partial="h")
        s = session(m.compile(), batches=[(S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.z.situation, {"C", "E"}, "u1 en la evolución 2; u2 no vale en la 3")
        m = M().partial("h").var("p").var("q")
        m.step("A", True).step("B")
        m.step("D", True, partial="h").step("E", partial="h")
        m.trans("t1", ["A"], ["B"], "p").trans("u1", ["D"], ["E"], "rise(active(B)) AND q", partial="h")
        s = session(m.compile(), batches=[(S, 0, {"p": True}), (2 * S, 0, {"q": True})])
        s.run()
        self.assertEqual(s.z.situation, {"B", "D"})

    def test_SFA05_bucle_de_flancos_llega_al_limite(self):
        """REQ-EVT-03, REQ-SEM-07: A→B con ↑XA y B→A con ↑XB acaba en D-LIM-EVOL."""
        m = M().var("p").step("S0", True).step("A").step("B")
        m.trans("t0", ["S0"], ["A"], "p")
        m.trans("t1", ["A"], ["B"], "rise(active(A))").trans("t2", ["B"], ["A"], "rise(active(B))")
        s = session(m.compile(), budget=20, batches=[(S, 0, {"p": True})])
        s.run()
        self.assertEqual(last_diag(s).code, "D-LIM-EVOL")

    def test_SFA06_validador(self):
        """REQ-EVT-03: se admiten ↑X, ↓X y ↑(X1·X2); siguen bloqueados internas, temporales y mezclas."""
        def val(cond, **vars_):
            m = M().var("p").var("n", "internal").step("A", True).step("B").step("C")
            m.trans("t", ["A"], ["B"], cond)
            return m.validate()
        for ok in ("rise(active(C))", "fall(active(C))", "rise(active(B) AND active(C))"):
            r = val(ok)
            self.assertFalse(r.diagnostics, ok)
            self.assertIn("eventos.actividad", r.capabilities)
            self.assertNotIn("eventos.entradas", r.capabilities)
        for bad in ("rise(n)", "rise(delay(1 s, p, 0 s))", "rise(p AND active(C))", "rise(n AND active(C))"):
            self.assertIn(("D-SEM-PENDIENTE", "U-03"), codes(val(bad)), bad)

    def test_SFA07_activacion_por_forzado(self):
        """REQ-EVT-03, REQ-JER-06: la activación que provoca un forzado produce el flanco en la evolución siguiente."""
        m = M().partial("G").partial("h").var("p")
        m.step("F0", True).step("F1")
        m.step("A", True, partial="G").step("J", partial="G")
        m.step("D", True, partial="h").step("E", partial="h")
        m.trans("t", ["F0"], ["F1"], "p").trans("u", ["D"], ["E"], "rise(active(J))", partial="h")
        m.force("F", "F1", "G", "explicit", ["J"])
        s = session(m.compile(), batches=[(S, 0, {"p": True})])
        s.run()
        self.assertEqual(s.z.situation, {"F1", "J", "E"}, str(last_diag(s) if s.diagnostics else ""))

    def test_SFA08_accion_por_evento_con_flanco_de_actividad_bloqueada(self):
        """REQ-EVT-03, REQ-ACT-02: una acción por evento con ↑X queda bloqueada (U-03), no se ignora en silencio."""
        m = M().var("n", "internal", "int").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "true").stored("A", "n", "event", "n + 1", event="rise(active(B))")
        r = m.validate()
        self.assertIn(("D-SEM-PENDIENTE", "U-03"), codes(r))
        self.assertIn("flanco sobre actividad en una acción por evento", " ".join(d.message for d in r.diagnostics))

    def test_SFA09_transicion_fuente_con_flanco_de_actividad_bloqueada(self):
        """REQ-EVT-03, REQ-MOD-04: una transición fuente con ↑X queda bloqueada (U-03)."""
        m = M().step("A", True).step("B").step("C").trans("t", [], ["C"], "rise(active(B))")
        r = m.validate()
        self.assertIn(("D-SEM-PENDIENTE", "U-03"), codes(r))
        self.assertIn("transición fuente", " ".join(d.message for d in r.diagnostics))


if __name__ == "__main__":
    unittest.main()
