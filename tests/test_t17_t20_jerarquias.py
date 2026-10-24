"""Casos T-17 a T-20 del documento 11: jerarquías.

En esta iteración se implementan la estructura y su validación (propiedad única, ciclos,
coherencia inicial y conflicto posible de forzado). La EJECUCIÓN de forzado, macroetapas
y encapsulación no está implementada (hallazgo H-18, U-08). Para esos casos se
comprueba que el inicio se bloquea con D-CAPACIDAD-NO-SOPORTADA, sin ejecutar una
aproximación; el oráculo del caso queda sin ejecutar.
"""
import copy
import unittest

from helpers import M, S, records, session


def with_force(m, fid, src, dst, kind, steps=None):
    f = {"id": fid, "sourceStepRef": src, "targetPartialRef": dst, "targetKind": kind}
    if steps is not None:
        f["targetSteps"] = steps
    m.doc["forces"].append(f)
    return m


def macro_model(shared=False, nested=False, recursive=False):
    m = M().partial("X").partial("Y").var("p").var("q").var("r").var("s")
    m.step("A", True).step("B").step("E", kind="entry", partial="X").step("K", partial="X").step("Sx", kind="exit", partial="X")
    m.trans("tq", ["E"], ["K"], "q", partial="X").trans("tr", ["K"], ["Sx"], "r", partial="X")
    h = m.doc["hierarchy"]
    h["macros"].append({"id": "M", "label": "M", "partialRef": "g", "expansionRef": "XM"})
    h["expansions"].append({"id": "XM", "ownerMacroRef": "M", "partialRef": "X", "entryRef": "E", "exitRef": "Sx"})
    m.trans("tp", ["A"], ["M"], "p").trans("ts", ["M"], ["B"], "s")
    if shared:
        h["macros"].append({"id": "M2", "label": "M2", "partialRef": "g", "expansionRef": "XM"})
    if nested or recursive:
        m.step("E2", kind="entry", partial="Y").step("S2", kind="exit", partial="Y")
        h["macros"].append({"id": "N", "label": "N", "partialRef": "X", "expansionRef": "XN"})
        h["expansions"].append({"id": "XN", "ownerMacroRef": "N", "partialRef": "Y", "entryRef": "E2", "exitRef": "S2"})
        if recursive:
            h["macros"].append({"id": "M3", "label": "M3", "partialRef": "Y", "expansionRef": "XM3"})
            m.partial("Z").step("E3", kind="entry", partial="Z").step("S3", kind="exit", partial="Z")
            h["expansions"].append({"id": "XM3", "ownerMacroRef": "M3", "partialRef": "X", "entryRef": "E3", "exitRef": "S3"})
    return m


def enclosure_model(owner_initial=True, inner_initial=True, second_owner=False):
    m = M().partial("R").var("p").var("q")
    m.step("H", owner_initial, kind="enclosing").step("I", inner_initial, partial="R").step("J", partial="R").step("K", partial="R")
    m.trans("t", ["H"], [], "p").trans("u", ["I"], ["J"], "q", partial="R")
    h = m.doc["hierarchy"]
    h["enclosures"].append({"id": "encR", "ownerStepRef": "H", "partialRef": "R", "activationRefs": ["K"]})
    if second_owner:
        m.step("H2", kind="enclosing")
        h["enclosures"].append({"id": "encR2", "ownerStepRef": "H2", "partialRef": "R", "activationRefs": ["K"]})
    return m


def codes(res):
    return {d.code for d in res.diagnostics}


class Jerarquias(unittest.TestCase):
    def _blocked_not_executed(self, m, capability):
        res = m.validate()
        self.assertIsNotNone(res.model, "la estructura es válida y se puede guardar")
        self.assertFalse(res.can_simulate)
        hits = [d for d in res.diagnostics if d.code == "D-CAPACIDAD-NO-SOPORTADA" and d.evidence.get("capacidad") == capability]
        self.assertTrue(hits, f"debe bloquear {capability}: {[str(d) for d in res.diagnostics]}")

    def test_T17a_forzado_no_ejecutable_en_esta_iteracion(self):
        m = M().partial("G").var("p").step("H", True).step("A", True, partial="G").step("B", partial="G").step("C", partial="G")
        m.trans("t", ["B"], ["C"], "p", partial="G")
        for kind, steps in (("explicit", ["B"]), ("empty", None), ("initial", None)):
            mm = M()
            mm.doc = copy.deepcopy(m.doc)
            with_force(mm, "F", "H", "G", kind, steps)
            self._blocked_not_executed(mm, "jerarquia.forzado")

    def test_T17b_forzado_actual_no_ejecutable(self):
        m = M().partial("G").var("p").step("H", True).step("A", True, partial="G").step("B", True, partial="G")
        self._blocked_not_executed(with_force(m, "F", "H", "G", "current"), "jerarquia.forzado")

    def test_T17c_conflicto_posible_de_forzado(self):
        m = M().partial("G").step("H1", True).step("H2", True).step("A", True, partial="G").step("B", partial="G")
        with_force(m, "F1", "H1", "G", "explicit", ["A"])
        with_force(m, "F2", "H2", "G", "explicit", ["B"])
        res = m.validate()
        conf = [d for d in res.diagnostics if d.code == "D-FORZADO-CONFLICTO"]
        self.assertEqual(len(conf), 1)
        self.assertIn("F1", conf[0].evidence["ordenes"])
        self.assertIn("F2", conf[0].evidence["ordenes"])
        # La detección dinámica (ambos orígenes activos a la vez) requiere ejecución jerárquica.
        self._blocked_not_executed(m, "jerarquia.forzado")

    def test_T17d_ciclo_de_forzado(self):
        m = M().partial("G1").partial("G2").step("A", True, partial="G1").step("B", True, partial="G2")
        with_force(m, "F1", "A", "G2", "empty")
        with_force(m, "F2", "B", "G1", "empty")
        res = m.validate()
        cyc = [d for d in res.diagnostics if d.code == "D-JERARQUIA-CICLO"]
        self.assertTrue(cyc and "G1" in cyc[0].evidence["camino"] and "G2" in cyc[0].evidence["camino"])
        self.assertFalse(res.can_simulate)
        m2 = M().partial("G1").step("A", True, partial="G1")
        with_force(m2, "F", "A", "G1", "empty")
        self.assertIn("D-JERARQUIA-CICLO", codes(m2.validate()))

    def test_T18a_macroetapa_no_ejecutable_en_esta_iteracion(self):
        self._blocked_not_executed(macro_model(), "jerarquia.macroetapas")

    def test_T18b_recorrido_de_expansion_no_ejecutable(self):
        self._blocked_not_executed(macro_model(), "jerarquia.macroetapas")

    def test_T18c_propiedad_unica_y_recursion(self):
        self.assertIn("D-PROPIETARIO", codes(macro_model(shared=True).validate()))
        nested = macro_model(nested=True).validate()
        self.assertFalse({"D-PROPIETARIO", "D-JERARQUIA-CICLO"} & codes(nested), [str(d) for d in nested.diagnostics])
        self.assertIsNotNone(nested.model, "identidad conservada en anidamiento")
        self.assertIn("D-JERARQUIA-CICLO", codes(macro_model(recursive=True).validate()))

    def test_T18d_rama_residual_bloqueada(self):
        self._blocked_not_executed(macro_model(), "jerarquia.macroetapas")

    def test_T18e_reentrada_de_macroetapa_no_ejecutable(self):
        self._blocked_not_executed(macro_model(), "jerarquia.macroetapas")

    def test_T19a_encapsulacion_no_ejecutable_en_esta_iteracion(self):
        self._blocked_not_executed(enclosure_model(), "jerarquia.encapsulacion")

    def test_T19b_encapsulacion_anidada_no_ejecutable(self):
        self._blocked_not_executed(enclosure_model(), "jerarquia.encapsulacion")

    def test_T19c_propietario_unico_y_coherencia_inicial(self):
        self.assertIn("D-PROPIETARIO", codes(enclosure_model(second_owner=True).validate()))
        res = enclosure_model(owner_initial=False, inner_initial=True).validate()
        self.assertIn("D-JERARQUIA-INICIAL", codes(res))
        h = next(s for s in enclosure_model(owner_initial=False).doc["steps"] if s["id"] == "H")
        self.assertFalse(h["initial"], "no se completa el padre sin aviso")
        self.assertIn("D-JERARQUIA-INICIAL", codes(enclosure_model(owner_initial=True, inner_initial=False).validate()))

    def test_T20a_coincidencia_jerarquica_bloqueada(self):
        self._blocked_not_executed(enclosure_model(), "jerarquia.encapsulacion")

    def test_T20b_particion_sin_orden_y_actividad_derivada(self):
        def run(order):
            m = M().partial("G1").partial("G2").var("p").var("y", "output")
            parts = {"G1": [("A", True), ("B", False)], "G2": [("C", True), ("D", False)]}
            for g in order:
                for sid, ini in parts[g]:
                    m.step(sid, ini, partial=g)
            m.step("X", True)
            m.trans("t", ["A"], [], "p", partial="G1").trans("u", ["C"], ["D"], "p", partial="G2")
            m.cont("X", "y", "activePartial(G1) AND activePartial(G2)")
            s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
            before = s.z.outputs["y"]
            s.run()
            return before, records(s, "evolucion")[0]["cleared"], s.z.situation, s.z.outputs["y"]
        r1, r2 = run(["G1", "G2"]), run(["G2", "G1"])
        self.assertEqual(r1, r2)
        self.assertEqual(r1, (True, ["t", "u"], {"D", "X"}, False))

    def test_T20c_forzado_contra_recinto_bloqueado(self):
        m = enclosure_model()
        m.step("F0", True)
        with_force(m, "F", "F0", "R", "explicit", ["J"])
        self._blocked_not_executed(m, "jerarquia.forzado")
        self._blocked_not_executed(m, "jerarquia.encapsulacion")


if __name__ == "__main__":
    unittest.main()
