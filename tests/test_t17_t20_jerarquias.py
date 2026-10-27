"""Casos T-17 a T-20 del documento 11: jerarquías (P-IMP-23).

La ejecución sigue el documento 06: macroetapas (LOC tabla 11), encapsulación (LOC §7.4) y forzado (LOC
tabla 9). Lo que el documento 06 deja en U-08 (cuestiones 7.2–7.8 de la hoja 08) se detiene por defecto con
D-SEM-PENDIENTE; cada caso B comprueba esa detención y, como referencia, lo que hace cada lectura posible.
"""
import copy
import unittest

from helpers import M, S, last_diag, records, session


def with_force(m, fid, src, dst, kind, steps=None):
    f = {"id": fid, "sourceStepRef": src, "targetPartialRef": dst, "targetKind": kind}
    if steps is not None:
        f["targetSteps"] = steps
    m.doc["forces"].append(f)
    return m


def add_macro(m, mid="M", exp="XM", partial="X", entry="E", exit_="Sx", owner="g"):
    h = m.doc["hierarchy"]
    h["macros"].append({"id": mid, "label": mid, "partialRef": owner, "expansionRef": exp})
    h["expansions"].append({"id": exp, "ownerMacroRef": mid, "partialRef": partial, "entryRef": entry, "exitRef": exit_})
    return m


def add_enclosure(m, eid, owner, partial, activation):
    m.doc["hierarchy"]["enclosures"].append({"id": eid, "ownerStepRef": owner, "partialRef": partial,
                                             "activationRefs": activation})
    return m


def macro_model(shared=False, nested=False, recursive=False):
    m = M().partial("X").partial("Y").var("p").var("q").var("r").var("s")
    m.step("A", True).step("B").step("E", kind="entry", partial="X").step("K", partial="X").step("Sx", kind="exit", partial="X")
    m.trans("tq", ["E"], ["K"], "q", partial="X").trans("tr", ["K"], ["Sx"], "r", partial="X")
    add_macro(m)
    m.trans("tp", ["A"], ["M"], "p").trans("ts", ["M"], ["B"], "s")
    h = m.doc["hierarchy"]
    if shared:
        h["macros"].append({"id": "M2", "label": "M2", "partialRef": "g", "expansionRef": "XM"})
    if nested or recursive:
        m.step("E2", kind="entry", partial="Y").step("S2", kind="exit", partial="Y")
        add_macro(m, "N", "XN", "Y", "E2", "S2", owner="X")
        if recursive:
            m.partial("Z").step("E3", kind="entry", partial="Z").step("S3", kind="exit", partial="Z")
            h["macros"].append({"id": "M3", "label": "M3", "partialRef": "Y", "expansionRef": "XM3"})
            h["expansions"].append({"id": "XM3", "ownerMacroRef": "M3", "partialRef": "X", "entryRef": "E3", "exitRef": "S3"})
    return m


def enclosure_model(owner_initial=True, inner_initial=True, second_owner=False):
    m = M().partial("R").var("p").var("q")
    m.step("H", owner_initial, kind="enclosing").step("I", inner_initial, partial="R").step("J", partial="R").step("K", partial="R")
    m.trans("t", ["H"], [], "p").trans("u", ["I"], ["J"], "q", partial="R")
    add_enclosure(m, "encR", "H", "R", ["K"])
    if second_owner:
        m.step("H2", kind="enclosing")
        add_enclosure(m, "encR2", "H2", "R", ["K"])
    return m


def codes(res):
    return {d.code for d in res.diagnostics}


def at(s, t):
    s.advance_to(t)
    return s.z.situation


class Jerarquias(unittest.TestCase):
    def test_T17a_forzado_explicito_vacio_e_inicial(self):
        """G mantiene {B} y t no franquea mientras H está activa; vacío deja G sin etapas; inicial, sus iniciales."""
        base = M().partial("G").var("p").var("q").step("H", True).step("H2")
        base.step("A", True, partial="G").step("B", partial="G").step("C", partial="G")
        base.trans("t", ["B"], ["C"], "p", partial="G").trans("v", ["H"], ["H2"], "q")
        expected = {"explicit": {"H", "B"}, "empty": {"H"}, "initial": {"H", "A"}}
        for kind, steps in (("explicit", ["B"]), ("empty", None), ("initial", None)):
            mm = M()
            mm.doc = copy.deepcopy(base.doc)
            s = session(with_force(mm, "F", "H", "G", kind, steps).compile(), init={"p": True}, batches=[(S, 0, {"q": True})])
            self.assertEqual(s.z.situation, expected[kind], kind)
            self.assertEqual(s.observe()["forces"][0]["steps"], sorted(expected[kind] - {"H"}))
            if kind == "explicit":
                self.assertEqual(at(s, S), {"H2", "C"}, "retirada: G evoluciona desde {B}")
                retira = [h for e in records(s, "evolucion") for h in e.get("hierarchy", []) if h["event"] == "retira"]
                self.assertEqual(retira, [{"order": "F", "event": "retira", "source": "H", "target": "G"}])

    def test_T17b_forzado_actual_captura_y_retirada(self):
        """La orden «actual» mantiene la captura {A,B}; al retirarse, G evoluciona desde ahí."""
        m = M().partial("G").var("p").var("q").step("H", True).step("H2")
        m.step("A", True, partial="G").step("B", True, partial="G").step("C", partial="G")
        m.trans("t", ["A"], ["C"], "p", partial="G").trans("v", ["H"], ["H2"], "q")
        s = session(with_force(m, "F", "H", "G", "current").compile(), batches=[(S, 0, {"p": True}), (2 * S, 0, {"q": True})])
        self.assertEqual(at(s, S), {"H", "A", "B"}, "p no cambia la captura")
        self.assertEqual(at(s, 2 * S), {"H2", "B", "C"})
        snap = s.snapshot("tras-retirada")
        self.assertEqual(snap["state"]["activeForces"], [])

    def test_T17c_conflicto_de_forzado(self):
        """Dos órdenes vigentes con igual destino y objetivo distinto: D-FORZADO-CONFLICTO, sin prioridad."""
        m = M().partial("G").step("H1", True).step("H2", True).step("A", True, partial="G").step("B", partial="G")
        with_force(m, "F1", "H1", "G", "explicit", ["A"])
        with_force(m, "F2", "H2", "G", "explicit", ["B"])
        res = m.validate()
        conf = [d for d in res.diagnostics if d.code == "D-FORZADO-CONFLICTO"]
        self.assertEqual(len(conf), 1, "aviso estático del conflicto posible")
        self.assertIn("F1", conf[0].evidence["ordenes"])
        s = session(res.model, start=False)
        d = s.start()[0]
        self.assertEqual(d.code, "D-FORZADO-CONFLICTO")
        self.assertIn("F1", d.evidence["ordenes"])
        self.assertIn("F2", d.evidence["ordenes"])
        self.assertIsNone(s.z.forces.get("F1") if s.z else None, "no se elige ninguna orden")

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

    def test_T18a_macroetapa_entrada_y_salida(self):
        """p activa E; q activa K sin salida externa (XM no sustituye a S); r activa S y habilita la salida a B."""
        s = session(macro_model().compile(), batches=[(S, 0, {"p": True}), (2 * S, 0, {"q": True}),
                                                      (3 * S, 0, {"s": True}), (4 * S, 0, {"r": True})])
        self.assertEqual(at(s, S), {"E"})
        self.assertTrue(s.observe()["macros"]["M"], "XM con E activa")
        self.assertEqual(at(s, 2 * S), {"K"})
        self.assertEqual(at(s, 3 * S), {"K"}, "s verdadera, pero S no está activa")
        self.assertEqual(at(s, 4 * S), {"B"})
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["Sx"], "S activa solo durante el recorrido")
        self.assertFalse(s.observe()["macros"]["M"])

    def test_T18b_recorrido_de_expansion_y_reentrada(self):
        """Expansión E→S/1: recorrido virtual hasta B; un nuevo ciclo vuelve a activar E."""
        m = M().partial("X").var("p").step("A", True).step("B").step("E", kind="entry", partial="X")
        m.step("Sx", kind="exit", partial="X").trans("te", ["E"], ["Sx"], "true", partial="X")
        add_macro(m).trans("tp", ["A"], ["M"], "p").trans("ts", ["M"], ["B"], "true").trans("tb", ["B"], ["A"], "NOT p")
        s = session(m.compile(), batches=[(S, 0, {"p": True}), (2 * S, 0, {"p": False}), (3 * S, 0, {"p": True})])
        self.assertEqual(at(s, S), {"B"})
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["E", "Sx"])
        self.assertEqual(at(s, 3 * S), {"B"})
        self.assertEqual([e["activated"] for e in records(s, "evolucion") if "E" in e["activated"]], [["E"], ["E"]])

    def test_T18c_propiedad_unica_y_recursion(self):
        self.assertIn("D-PROPIETARIO", codes(macro_model(shared=True).validate()))
        nested = macro_model(nested=True).validate()
        self.assertFalse({"D-PROPIETARIO", "D-JERARQUIA-CICLO"} & codes(nested), [str(d) for d in nested.diagnostics])
        self.assertIsNotNone(nested.model, "identidad conservada en anidamiento")
        self.assertIn("D-JERARQUIA-CICLO", codes(macro_model(recursive=True).validate()))

    def test_T18d_rama_residual(self):
        """S habilita la salida con K aún activa: 7.5 A, se desactivan todas las etapas de la expansión. Con «detener»,
        U-08; las lecturas B y C se comprueban como referencia."""
        m = M().partial("X").var("p").var("q").var("s").step("A", True).step("B")
        m.step("E", kind="entry", partial="X").step("K", partial="X").step("Sx", kind="exit", partial="X")
        m.trans("tq", ["E"], ["K", "Sx"], "q", partial="X")
        add_macro(m).trans("tp", ["A"], ["M"], "p").trans("ts", ["M"], ["B"], "s")
        batches = [(S, 0, {"p": True}), (2 * S, 0, {"q": True}), (3 * S, 0, {"s": True})]
        s = session(m.compile(), batches=batches)
        s.run()
        self.assertEqual((s.status, s.z.situation), ("finalizada", {"B"}))
        s = session(m.compile(), batches=batches, options={"7.5": "detener"})
        s.run()
        self.assertEqual((last_diag(s).code, last_diag(s).question), ("D-SEM-PENDIENTE", "U-08"))
        self.assertEqual(s.z.situation, {"K", "Sx"}, "se conserva el último estado estable")
        outcome = {}
        for reading in ("A", "B", "C"):
            r = session(m.compile({"7.5": reading}), batches=batches, options={"7.5": reading})
            r.run()
            outcome[reading] = (r.status, sorted(r.z.situation), last_diag(r).code if r.diagnostics else None)
        self.assertEqual(outcome, {"A": ("finalizada", ["B"], None), "B": ("finalizada", ["B", "K"], None),
                                   "C": ("error", ["K", "Sx"], "D-JERARQUIA-RAMA")})

    def test_T18e_reentrada_de_macroetapa_y_memoria(self):
        """E se activa en ambas llegadas: n=1 tras la primera y n=2 tras la segunda; la memoria no se reinicia."""
        m = M().partial("X").var("p").var("q").var("r").var("n", "internal", "int").step("A", True)
        m.step("E", kind="entry", partial="X").step("Sx", kind="exit", partial="X").trans("tq", ["E"], ["Sx"], "q", partial="X")
        m.stored("E", "n", "activation", "n + 1")
        add_macro(m).trans("tp", ["A"], ["M"], "p").trans("tr", ["M"], ["A"], "r")
        h = S // 2
        s = session(m.compile(), batches=[(S, 0, {"p": True}), (S + h, 0, {"p": False}), (2 * S, 0, {"q": True}),
                                         (2 * S + h, 0, {"q": False}), (3 * S, 0, {"r": True}), (3 * S + h, 0, {"r": False}),
                                         (4 * S, 0, {"p": True})])
        at(s, S)
        self.assertEqual(s.z.values["n"], 1)
        self.assertEqual(at(s, 3 * S), {"A"})
        self.assertEqual(s.z.values["n"], 1)
        self.assertEqual(at(s, 4 * S), {"E"})
        self.assertEqual(s.z.values["n"], 2)

    def test_T19a_inicio_salida_y_reentrada_por_enlace_de_activacion(self):
        """Inicio {H,I}; la salida de H vacía R; la reentrada activa K, no I ni la última situación."""
        m = M().partial("R").var("p").var("q").step("H", True, kind="enclosing").step("Z")
        m.step("I", True, partial="R").step("J", partial="R").step("K", partial="R")
        m.trans("t", ["H"], ["Z"], "p").trans("u", ["Z"], ["H"], "q")
        add_enclosure(m, "encR", "H", "R", ["K"])
        s = session(m.compile(), batches=[(S, 0, {"p": True}), (2 * S, 0, {"p": False, "q": True})])
        self.assertEqual(s.z.situation, {"H", "I"})
        self.assertEqual(at(s, S), {"Z"})
        self.assertEqual(at(s, 2 * S), {"H", "K"})

    def test_T19b_encapsulacion_anidada(self):
        """Entrar en H activa K y L (sus recintos) y N (recinto de K); salir de H desactiva todos los descendientes."""
        m = M().partial("R1").partial("R2").partial("R3").var("p").var("q").step("Z", True).step("H", kind="enclosing")
        m.step("K", kind="enclosing", partial="R1").step("K2", partial="R1").step("L", partial="R2").step("N", partial="R3")
        m.trans("t", ["Z"], ["H"], "p").trans("u", ["H"], ["Z"], "q")
        add_enclosure(m, "enc1", "H", "R1", ["K"])
        add_enclosure(m, "enc2", "H", "R2", ["L"])
        add_enclosure(m, "enc3", "K", "R3", ["N"])
        s = session(m.compile(), batches=[(S, 0, {"p": True}), (2 * S, 0, {"p": False, "q": True})])
        self.assertEqual(at(s, S), {"H", "K", "L", "N"})
        self.assertEqual(at(s, 2 * S), {"Z"})

    def test_T19c_propietario_unico_y_coherencia_inicial(self):
        self.assertIn("D-PROPIETARIO", codes(enclosure_model(second_owner=True).validate()))
        res = enclosure_model(owner_initial=False, inner_initial=True).validate()
        self.assertIn("D-JERARQUIA-INICIAL", codes(res))
        h = next(s for s in enclosure_model(owner_initial=False).doc["steps"] if s["id"] == "H")
        self.assertFalse(h["initial"], "no se completa el padre sin aviso")
        self.assertIn("D-JERARQUIA-INICIAL", codes(enclosure_model(owner_initial=True, inner_initial=False).validate()))

    def test_T20a_desactivacion_y_vencimiento_interior(self):
        """H se desactiva a 2 s cuando vence 2s/X_A en su interior: 7.6 B, primero actúa lo interior (n := 1) y después se
        desactiva. Con «detener», U-08; la lectura A se comprueba como referencia."""
        m = M().partial("R").var("p").var("n", "internal", "int").step("H", True, kind="enclosing").step("Z")
        m.step("A", True, partial="R").step("B", partial="R").stored("B", "n", "activation", "1")
        m.trans("ti", ["A"], ["B"], "delay(2 s, active(A), 0 s)", partial="R").trans("to", ["H"], ["Z"], "p")
        add_enclosure(m, "encR", "H", "R", ["A"])
        s = session(m.compile(), batches=[(2 * S, 0, {"p": True})])
        s.run()
        self.assertEqual((s.z.situation, s.z.values["n"]), ({"Z"}, 1))
        self.assertEqual(records(s, "estable")[-1]["virtualSteps"], ["B"], "B actúa y queda inestable")
        s = session(m.compile(), batches=[(2 * S, 0, {"p": True})], options={"7.6": "detener"})
        s.run()
        self.assertEqual((last_diag(s).code, last_diag(s).question), ("D-SEM-PENDIENTE", "U-08"))
        self.assertEqual(s.z.situation, {"H", "A"})
        outcome = {}
        for reading in ("A", "B"):
            r = session(m.compile(), batches=[(2 * S, 0, {"p": True})], options={"7.6": reading})
            r.run()
            outcome[reading] = (sorted(r.z.situation), r.z.values["n"])
        self.assertEqual(outcome, {"A": (["Z"], 0), "B": (["Z"], 1)}, "B actúa y después se desactiva")

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

    def test_T20c_forzado_contra_recinto(self):
        """Forzar el recinto de una encapsulante inactiva: 7.4 C, se ignora mientras siga inactiva (con «detener», U-08).
        Vaciarlo con ella activa no se preguntó: U-08, sin resultado silencioso."""
        m = enclosure_model(owner_initial=False, inner_initial=False)
        m.step("F0", True)
        with_force(m, "F", "F0", "R", "explicit", ["J"])
        self.assertEqual(session(m.compile()).z.situation, {"F0"}, "R sigue vacío: no se activa nada dentro de H inactiva")
        s = session(m.compile(), start=False, options={"7.4": "detener"})
        d = s.start()[0]
        self.assertEqual((d.code, d.question), ("D-SEM-PENDIENTE", "U-08"))
        outcome = {}
        for reading in ("A", "B", "C"):
            r = session(m.compile(), start=False, options={"7.4": reading})
            diags = r.start()
            outcome[reading] = diags[0].code if diags else sorted(r.z.situation)
        self.assertEqual(outcome, {"A": "D-FORZADO-RECINTO", "B": ["F0", "J"], "C": ["F0"]})
        m = enclosure_model()
        m.step("F0", True)
        with_force(m, "F", "F0", "R", "empty")
        d = session(m.compile(), start=False).start()[0]
        self.assertEqual((d.code, d.question), ("D-SEM-PENDIENTE", "U-08"), "vaciar un recinto activo: no preguntado")


if __name__ == "__main__":
    unittest.main()
