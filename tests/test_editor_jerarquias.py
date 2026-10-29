"""Editor de jerarquías en el núcleo (paso 6 del plan, sin Qt): macroetapas con su expansión, recintos con su
encapsulante y órdenes de forzado, con transacción y deshacer (documento 06; P-IMP-23..27).

Los ejemplos «macroetapa», «encapsulacion» y «forzado» se reconstruyen con las operaciones del editor y deben simular
igual que los hechos con el constructor (grafcet.builder.M). Ninguna prueba es oráculo del documento 11: comprueban que
el editor deja el modelo como lo declara el documento 09, que lo inválido se rechaza con los diagnósticos que ya da
`validate()` y que U-08 (vaciar por forzado un recinto con su encapsulante activa) sigue deteniéndose.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from helpers import M, S, records, session

from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Editor, EnclosureIds, MacroIds, new_grafcet_document
from grafcet.examples import EJEMPLOS
from grafcet.ids import IdGenerator
from grafcet.model import validate_model
from grafcet.persistence import add_document, new_project, open_model, save_project
from grafcet.profile import normalize_options
from grafcet.view import Vista, display_names, layout_from_presentation

VACIA = {"macros": [], "expansions": [], "enclosures": []}


def nuevo():
    return Editor(new_grafcet_document("m"), ids=IdGenerator("x"))


def entradas(ed, *nombres):
    return {n: ed.add_variable(n, "input", {"kind": "bool"}) for n in nombres}


def codigos(diags):
    return {d.code for d in diags}


def etiquetas(doc):
    """Nombre de cada elemento (variable, etapa, parcial, macroetapa, transición): los ID del editor no se comparan."""
    out = {v["id"]: v["name"] for v in doc["variables"]}
    for coll in ("steps", "partials"):
        out.update({x["id"]: x["label"] for x in doc[coll]})
    out.update({x["id"]: x["label"] for x in doc["hierarchy"]["macros"]})
    out.update({t["id"]: t.get("label", t["id"]) for t in doc["transitions"]})
    return out


def foto(s, nombre):
    obs = s.observe()
    return {"situacion": sorted(nombre[i] for i in s.z.situation),
            "salidas": sorted(nombre[k] for k, v in s.z.outputs.items() if v),
            "macros": {nombre[k]: v for k, v in obs.get("macros", {}).items()},
            "ordenes": sorted((nombre[f["target"]], f["kind"], tuple(sorted(nombre[i] for i in f["steps"])))
                              for f in obs.get("forces", []))}


def corrida(doc, guion, init=None):
    """Simula `doc` con el guion [(segundos, {entrada: valor})] y devuelve lo observable con nombres en vez de ID:
    la situación, las salidas, la actividad de las macroetapas y las órdenes vigentes tras cada instante, y las
    transiciones que franquea cada evolución."""
    res = validate_model(doc)
    assert res.can_simulate, [str(d) for d in res.diagnostics]
    nombre = etiquetas(doc)
    por_nombre = {v["name"]: v["id"] for v in doc["variables"]}
    s = session(res.model, init={por_nombre[k]: v for k, v in (init or {}).items()},
                batches=[(t * S, 0, {por_nombre[k]: v for k, v in ch.items()}) for t, ch in guion])
    fotos = [foto(s, nombre)]
    for t, _ in guion:
        s.advance_to(t * S)
        fotos.append(foto(s, nombre))
    return fotos, [sorted(nombre[t] for t in r["cleared"]) for r in records(s, "evolucion")]


def situaciones(fotos):
    return [f["situacion"] for f in fotos]


# --- Los tres ejemplos, hechos con el editor ------------------------------------------------------

def ed_macroetapa():
    ed = nuevo()
    entradas(ed, "p", "q", "r", "s")
    motor = ed.add_variable("motor", "output", {"kind": "bool"})
    a, b = ed.add_step("g", "A", True), ed.add_step("g", "B")
    mac = ed.add_macro("g", "M", entry_label="E1", exit_label="S1", expansion_label="X")
    k = ed.add_step(mac.partial, "K")
    ed.add_transition(mac.partial, "q", pre=[mac.entry], post=[k], label="tq")
    ed.add_transition(mac.partial, "r", pre=[k], post=[mac.exit], label="tr")
    ed.add_continuous_action(k, motor)
    tp, _ = ed.add_transition("g", "p", pre=[a], label="tp")
    ts, _ = ed.add_transition("g", "s", post=[b], label="ts")
    ed.connect(tp, mac.macro)  # una macroetapa se enlaza como una etapa
    ed.connect(mac.macro, ts)
    ed.add_transition("g", "NOT s", pre=[b], post=[a], label="tb")
    return ed


def ed_encapsulacion(via_parcial_existente=False):
    ed = nuevo()
    entradas(ed, "p", "q", "r")
    luz = ed.add_variable("luz", "output", {"kind": "bool"})
    h = ed.add_step("g", "H", True)
    z = ed.add_step("g", "Z")
    ed.set_step_kind(h, "enclosing")
    if via_parcial_existente:
        rp = ed.add_partial("R", owner="g")
        ed.add_enclosure(h, rp)
    else:
        rp = ed.new_enclosure(h, "R").partial
    i = ed.add_step(rp, "I", True)
    j = ed.add_step(rp, "J")
    k = ed.add_step(rp, "K")
    ed.set_activation(k)
    ed.add_transition("g", "p", pre=[h], post=[z], label="t")
    ed.add_transition("g", "q", pre=[z], post=[h], label="u")
    ed.add_transition(rp, "r", pre=[i], post=[j], label="v")
    ed.add_transition(rp, "r", pre=[k], post=[j], label="w")
    ed.add_continuous_action(j, luz)
    return ed


def ed_forzado():
    ed = nuevo()
    entradas(ed, "f", "a", "b", "c")
    g = ed.add_partial("G")
    h2, h = ed.add_step("g", "H2", True), ed.add_step("g", "H")
    a, b, c = ed.add_step(g, "A", True), ed.add_step(g, "B"), ed.add_step(g, "C")
    ed.add_transition("g", "f", pre=[h2], post=[h], label="t1")
    ed.add_transition("g", "NOT f", pre=[h], post=[h2], label="t2")
    ed.add_transition(g, "a", pre=[a], post=[b], label="ta")
    ed.add_transition(g, "b", pre=[b], post=[c], label="tb")
    ed.add_transition(g, "c", pre=[c], post=[a], label="tc")
    ed.add_force(h, g, "explicit", [b])
    return ed


class EditorDeJerarquias(unittest.TestCase):
    def rechaza(self, ed, codigo, op, *args, **kw):
        """La operación se rechaza con ese diagnóstico, no cambia nada y no entra en el historial."""
        antes, pila = copy.deepcopy((ed.model, ed.presentation)), len(ed.undo_stack)
        with self.assertRaises(DiagnosticError) as ctx:
            op(*args, **kw)
        self.assertIn(codigo, codigos(ctx.exception.diagnostics), [str(d) for d in ctx.exception.diagnostics])
        self.assertEqual((ed.model, ed.presentation), antes)
        self.assertEqual(len(ed.undo_stack), pila)

    def test_SEDI139_macroetapa_con_su_expansion_entrada_y_salida(self):
        """REQ-JER-04, REQ-MOD-07, REQ-EDT-05: `add_macro` crea la macroetapa, su expansión (un parcial dentro del
        suyo, regla 8.1 C) y sus etapas de entrada y salida; una expansión por macroetapa; se deshace y se rehace."""
        ed = nuevo()
        a = ed.add_step("g", "A", True, at=(160, 60))
        b = ed.add_step("g", "B")
        mac = ed.add_macro("g", "M", at=(160, 220))
        self.assertIsInstance(mac, MacroIds)
        self.assertEqual(ed.model["hierarchy"]["macros"],
                         [{"id": mac.macro, "label": "M", "partialRef": "g", "expansionRef": mac.expansion}])
        self.assertEqual(ed.model["hierarchy"]["expansions"],
                         [{"id": mac.expansion, "ownerMacroRef": mac.macro, "partialRef": mac.partial, "entryRef": mac.entry,
                           "exitRef": mac.exit}])
        exp = ed.get(mac.partial)
        self.assertEqual((exp["ownerRef"], exp["label"], exp["stepRefs"]), ("g", "M", [mac.entry, mac.exit]))
        self.assertEqual([(ed.get(i)["kind"], ed.get(i)["label"], ed.get(i)["partialRef"]) for i in (mac.entry, mac.exit)],
                         [("entry", "E1", mac.partial), ("exit", "S1", mac.partial)])
        self.assertEqual(layout_from_presentation(ed.presentation), {a: (160.0, 60.0), mac.macro: (160.0, 220.0)})
        entradas(ed, "p")
        ed.add_transition("g", "p", pre=[a], post=[mac.macro])
        ed.add_transition("g", "true", pre=[mac.macro], post=[b])
        res = ed.validate()
        self.assertEqual([str(d) for d in res.diagnostics], [], "válido, sin diagnósticos nuevos")
        self.assertTrue(res.can_simulate)
        self.assertEqual(ed.macro_info(mac.macro), mac)
        # la entrada y la salida de la siguiente son E2 y S2; una macroetapa dentro de una expansión (anidada)
        mac2 = ed.add_macro("g", "N")
        inner = ed.add_macro(mac.partial, "Interna", expansion_label="XI")
        self.assertEqual((ed.get(mac2.entry)["label"], ed.get(mac2.exit)["label"]), ("E2", "S2"))
        self.assertEqual((ed.get(inner.entry)["label"], ed.get(inner.exit)["label"]), ("E3", "S3"))
        self.assertEqual(ed.get(inner.partial)["ownerRef"], mac.partial)
        res = ed.validate()
        self.assertFalse({"D-PROPIETARIO", "D-JERARQUIA-CICLO", "D-FORMATO", "D-REF"} & codigos(res.diagnostics))
        self.assertTrue(res.can_simulate)
        self.assertEqual(len({x["partialRef"] for x in ed.model["hierarchy"]["expansions"]}), 3, "una expansión por macroetapa")
        roles = ed.partial_roles()
        self.assertEqual(roles["g"]["kind"], "root")
        self.assertEqual((roles[mac.partial]["kind"], roles[mac.partial]["parent"], roles[mac.partial]["macro"]),
                         ("expansion", "g", mac.macro))
        self.assertEqual((roles[inner.partial]["kind"], roles[inner.partial]["parent"]), ("expansion", mac.partial))
        self.assertEqual(roles[mac.partial]["text"], "expansión de la macroetapa M")
        antes = copy.deepcopy((ed.model, ed.presentation))
        ed.undo()
        self.assertEqual(len(ed.model["hierarchy"]["macros"]), 2)
        ed.redo()
        self.assertEqual((ed.model, ed.presentation), antes)

    def test_SEDI140_ejemplo_macroetapa_reconstruido_con_el_editor(self):
        """REQ-JER-04, REQ-EDT-02: el ejemplo «macroetapa» hecho con el editor simula igual que el del constructor."""
        guion = [(1, {"p": True}), (2, {"q": True}), (3, {"s": True}), (4, {"r": True}), (5, {"s": False}), (6, {"p": False})]
        ed = ed_macroetapa()
        self.assertEqual([str(d) for d in ed.validate().diagnostics], [])
        mio = corrida(ed.model, guion)
        self.assertEqual(mio, corrida(EJEMPLOS["macroetapa"][2]()[0].doc, guion))
        self.assertEqual(situaciones(mio[0]), [["A"], ["E1"], ["K"], ["K"], ["B"], ["S1"], ["S1"]],
                         "p activa E1; s no basta sin S1; r llega a S1 y sale a B; sin s vuelve a A y, con p, entra en M y "
                         "recorre la expansión hasta S1, que espera a s")
        self.assertEqual(mio[0][2]["salidas"], ["motor"])
        self.assertEqual([f["macros"] for f in mio[0]][:3], [{"M": False}, {"M": True}, {"M": True}])

    def test_SEDI141_ejemplo_encapsulacion_reconstruido_con_el_editor(self):
        """REQ-JER-05, REQ-EDT-02: el ejemplo «encapsulacion», con un recinto nuevo o con un parcial ya creado, simula
        igual que el del constructor (inicio {H,I}; reentrada por el enlace de activación en K)."""
        guion = [(1, {"p": True}), (2, {"p": False, "q": True}), (3, {"q": False, "r": True}), (4, {"r": False}),
                 (5, {"p": True}), (6, {"p": False, "q": True})]
        esperado = corrida(EJEMPLOS["encapsulacion"][2]()[0].doc, guion)
        for via in (False, True):
            ed = ed_encapsulacion(via)
            self.assertEqual([str(d) for d in ed.validate().diagnostics], [], f"via_parcial_existente={via}")
            self.assertEqual(corrida(ed.model, guion), esperado, f"via_parcial_existente={via}")
        self.assertEqual(situaciones(esperado[0]), [["H", "I"], ["Z"], ["H", "K"], ["H", "J"], ["H", "J"], ["Z"], ["H", "K"]])
        self.assertEqual(esperado[0][3]["salidas"], ["luz"])
        # el marcado se ve en el modelo y se quita
        k = next(s["id"] for s in ed.model["steps"] if s["label"] == "K")
        self.assertEqual(ed.model["hierarchy"]["enclosures"][0]["activationRefs"], [k])
        ed.set_activation(k, False)
        self.assertEqual(ed.model["hierarchy"]["enclosures"][0]["activationRefs"], [])

    def test_SEDI142_ejemplo_forzado_reconstruido_con_el_editor(self):
        """REQ-JER-02, REQ-EDT-02: el ejemplo «forzado» hecho con el editor simula igual que el del constructor: G no
        evoluciona mientras H está activa y, al retirarse la orden, sigue desde B."""
        guion = [(1, {"f": True}), (2, {"a": True}), (3, {"a": False, "b": True}), (4, {"f": False}), (5, {"b": False, "c": True})]
        ed = ed_forzado()
        self.assertEqual([str(d) for d in ed.validate().diagnostics], [])
        mio = corrida(ed.model, guion)
        self.assertEqual(mio, corrida(EJEMPLOS["forzado"][2]()[0].doc, guion))
        self.assertEqual(situaciones(mio[0]), [["A", "H2"], ["B", "H"], ["B", "H"], ["B", "H"], ["C", "H2"], ["A", "H2"]])
        self.assertEqual(mio[0][1]["ordenes"], [("G", "explicit", ("B",))])
        self.assertEqual(mio[0][4]["ordenes"], [], "al quitar f se retira la orden")

    def test_SEDI143_las_cuatro_formas_de_forzado(self):
        """REQ-JER-02: explícita, actual, vacía e inicial, hechas con `add_force`, imponen lo mismo que las del
        constructor (T-17a, T-17b); `set_force` cambia la forma y `delete_force` la quita."""
        esperado = {"explicit": ["B", "H"], "empty": ["H"], "initial": ["A", "H"]}
        for forma in esperado:
            m = M().partial("G").var("p").var("q").step("H", True).step("H2")
            m.step("A", True, partial="G").step("B", partial="G").step("C", partial="G")
            m.trans("t", ["B"], ["C"], "p", partial="G").trans("v", ["H"], ["H2"], "q")
            m.force("F", "H", "G", forma, ["B"] if forma == "explicit" else None)
            ed = nuevo()
            entradas(ed, "p", "q")
            g = ed.add_partial("G")
            h, h2 = ed.add_step("g", "H", True), ed.add_step("g", "H2")
            a, b, c = ed.add_step(g, "A", True), ed.add_step(g, "B"), ed.add_step(g, "C")
            ed.add_transition(g, "p", pre=[b], post=[c], label="t")
            ed.add_transition("g", "q", pre=[h], post=[h2], label="v")
            ed.add_force(h, g, forma, [b] if forma == "explicit" else None)
            guion = [(1, {"q": True})]
            mio = corrida(ed.model, guion, init={"p": True})
            self.assertEqual(mio, corrida(m.doc, guion, init={"p": True}), forma)
            self.assertEqual(mio[0][0]["situacion"], esperado[forma], forma)
        # actual: captura {A,B} al entrar en vigor y la mantiene (T-17b)
        m = M().partial("G").var("p").var("q").step("H", True).step("H2")
        m.step("A", True, partial="G").step("B", True, partial="G").step("C", partial="G")
        m.trans("t", ["A"], ["C"], "p", partial="G").trans("v", ["H"], ["H2"], "q").force("F", "H", "G", "current")
        ed = nuevo()
        entradas(ed, "p", "q")
        g = ed.add_partial("G")
        h, h2 = ed.add_step("g", "H", True), ed.add_step("g", "H2")
        a, b, c = ed.add_step(g, "A", True), ed.add_step(g, "B", True), ed.add_step(g, "C")
        ed.add_transition(g, "p", pre=[a], post=[c], label="t")
        ed.add_transition("g", "q", pre=[h], post=[h2], label="v")
        f = ed.add_force(h, g, "current")
        self.assertNotIn("targetSteps", ed.get(f))
        guion = [(1, {"p": True}), (2, {"q": True})]
        mio = corrida(ed.model, guion)
        self.assertEqual(mio, corrida(m.doc, guion))
        self.assertEqual(situaciones(mio[0]), [["A", "B", "H"], ["A", "B", "H"], ["B", "C", "H2"]])
        # set_force: de «actual» a «explícita» y a «vacía»; delete_force la quita y se deshace
        ed.set_force(f, kind="explicit", steps=[c])
        self.assertEqual((ed.get(f)["targetKind"], ed.get(f)["targetSteps"]), ("explicit", [c]))
        ed.set_force(f, kind="empty")
        self.assertEqual(ed.get(f), {"id": f, "sourceStepRef": h, "targetPartialRef": g, "targetKind": "empty"})
        self.assertEqual(corrida(ed.model, [])[0][0]["situacion"], ["H"])
        ed.delete_force(f)
        self.assertEqual(ed.model["forces"], [])
        ed.undo()
        self.assertEqual(ed.get(f)["targetKind"], "empty")

    def test_SEDI144_recintos_varios_encapsulantes_anidadas_y_marcas(self):
        """REQ-JER-05, REQ-MOD-07: una encapsulante con varios recintos (y una encapsulante dentro de un recinto) se
        construye con las operaciones y entra y sale como T-19b; cada recinto tiene una sola encapsulante."""
        ed = nuevo()
        entradas(ed, "p", "q")
        z = ed.add_step("g", "Z", True)
        h = ed.add_step("g", "H")
        ed.set_step_kind(h, "enclosing")
        r1, r2 = ed.new_enclosure(h, "R1"), ed.new_enclosure(h, "R2")
        self.assertIsInstance(r1, EnclosureIds)
        k = ed.add_step(r1.partial, "K")
        ed.set_step_kind(k, "enclosing")
        ed.add_step(r1.partial, "K2")
        lt = ed.add_step(r2.partial, "L")
        r3 = ed.new_enclosure(k, "R3")
        n = ed.add_step(r3.partial, "N")
        for s in (k, lt, n):
            ed.set_activation(s)
        ed.add_transition("g", "p", pre=[z], post=[h], label="t")
        ed.add_transition("g", "q", pre=[h], post=[z], label="u")
        self.assertEqual([str(d) for d in ed.validate().diagnostics], [])
        roles = ed.partial_roles()
        self.assertEqual([(roles[x.partial]["kind"], roles[x.partial]["parent"], roles[x.partial]["ownerStep"])
                          for x in (r1, r2, r3)], [("enclosure", "g", h), ("enclosure", "g", h), ("enclosure", r1.partial, k)])
        self.assertEqual(roles[r3.partial]["activation"], [n])
        self.assertEqual(roles[r1.partial]["text"], "recinto de la encapsulante H")
        self.assertEqual(roles[r3.partial]["text"], "recinto de la encapsulante K")
        # igual que T-19b hecho con el constructor
        m = M().partial("R1").partial("R2").partial("R3").var("p").var("q").step("Z", True).step("H", kind="enclosing")
        m.step("K", kind="enclosing", partial="R1").step("K2", partial="R1").step("L", partial="R2").step("N", partial="R3")
        m.trans("t", ["Z"], ["H"], "p").trans("u", ["H"], ["Z"], "q")
        m.enclosure("H", "R1", ["K"]).enclosure("H", "R2", ["L"]).enclosure("K", "R3", ["N"])
        guion = [(1, {"p": True}), (2, {"p": False, "q": True})]
        mio = corrida(ed.model, guion)
        self.assertEqual(mio, corrida(m.doc, guion))
        self.assertEqual(situaciones(mio[0]), [["Z"], ["H", "K", "L", "N"], ["Z"]])
        # una etapa que no está en un recinto no lleva enlace de activación; devolver a ordinaria exige borrar antes
        self.rechaza(ed, "D-REF", ed.set_activation, z)
        self.rechaza(ed, "D-FORMATO", ed.set_step_kind, h, "ordinary")
        # un recinto sin etapa inicial con la encapsulante inicial: lo informa validate(), no lo rechaza la operación
        ed2 = nuevo()
        i = ed2.add_step("g", "I", True)
        ed2.set_step_kind(i, "enclosing")
        rec = ed2.new_enclosure(i, "R")
        self.assertIn("D-JERARQUIA-INICIAL", codigos(ed2.validate().diagnostics))
        ed2.add_step(rec.partial, "J", True)
        self.assertEqual(ed2.validate().diagnostics, [])
        self.assertEqual(ed2.validate().model.hier.enclosures[i][0].partial, rec.partial)

    def test_SEDI145_rechazo_de_macroetapas_y_recintos_invalidos(self):
        """REQ-MOD-07, REQ-JER-04, REQ-JER-05, REQ-EDT-05: lo estructuralmente inválido se rechaza con los diagnósticos
        que da el modelo (D-REF, D-PROPIETARIO, D-JERARQUIA-CICLO, D-FORMATO, D-NOMBRE-COLISION); no cambia nada ni entra
        en el historial."""
        ed = nuevo()
        a = ed.add_step("g", "A", True)
        h = ed.add_step("g", "H", True)
        h2 = ed.add_step("g", "H2")
        for s in (h, h2):
            ed.set_step_kind(s, "enclosing")
        rec = ed.new_enclosure(h, "R")
        i = ed.add_step(rec.partial, "I", True)
        mac = ed.add_macro("g", "M")
        otro = ed.add_partial("Otro")
        x = ed.add_step(otro, "X", True)
        ed.set_step_kind(x, "enclosing")
        r = lambda codigo, op, *args, **kw: self.rechaza(ed, codigo, op, *args, **kw)  # noqa: E731
        r("D-REF", ed.add_macro, "no-existe", "N")
        r("D-NOMBRE-COLISION", ed.add_macro, "g", "M")
        r("D-NOMBRE-COLISION", ed.add_macro, "g", "N", entry_label="Q", exit_label="Q")
        r("D-NOMBRE-COLISION", ed.add_macro, "g", "N", expansion_label="R")
        r("D-FORMATO", ed.add_macro, "g", "")
        r("D-REF", ed.add_enclosure, "no-existe", otro)
        r("D-REF", ed.add_enclosure, h2, "no-existe")
        r("D-FORMATO", ed.add_enclosure, a, otro)  # la etapa A no es encapsulante
        r("D-FORMATO", ed.new_enclosure, a, "Q")
        r("D-PROPIETARIO", ed.add_enclosure, h2, rec.partial)  # un recinto, una sola encapsulante
        r("D-PROPIETARIO", ed.add_enclosure, h2, mac.partial)  # ni recinto de una expansión
        r("D-JERARQUIA-CICLO", ed.add_enclosure, h, "g")  # el recinto no puede contener a su propia encapsulante
        kr = ed.add_step(rec.partial, "KR")
        ed.set_step_kind(kr, "enclosing")
        r("D-JERARQUIA-CICLO", ed.add_enclosure, kr, "g")  # ni indirectamente: g contiene a R y R a g
        r("D-REF", ed.add_enclosure, h2, otro, [i])  # el enlace de activación es de etapas del recinto
        r("D-FORMATO", ed.add_enclosure, x, rec.partial)  # el parcial ya está dentro de g, y X está en Otro
        r("D-FORMATO", ed.set_step_kind, h, "ordinary")  # con recintos
        r("D-FORMATO", ed.set_step_kind, mac.entry, "enclosing")
        r("D-FORMATO", ed.set_step_kind, a, "entry")
        r("D-REF", ed.set_activation, a)
        r("D-REF", ed.set_activation, "no-existe")
        r("D-REF", ed.macro_info, "no-existe")
        r("D-REF", ed.delete, [mac.entry])  # la entrada o la salida no se borran solas
        r("D-REF", ed.delete, [mac.exit, a])
        # lo válido pasa: un recinto ya creado con su dueño, y un segundo recinto para H, cada uno con su etapa inicial
        q = ed.add_partial("Q", owner=otro)
        ed.add_enclosure(x, q)
        ed.add_step(q, "QI", True)
        ed.add_step(ed.new_enclosure(h, "R2").partial, "R2I", True)
        self.assertEqual(ed.validate().diagnostics, [])

    def test_SEDI146_rechazo_de_ordenes_de_forzado_invalidas_y_conflicto_posible(self):
        """REQ-JER-02, REQ-JER-03: ciclos, referencias y formas inválidas se rechazan; dos órdenes con igual destino y
        objetivo distinto se aceptan y `validate()` avisa (D-FORZADO-CONFLICTO), sin prioridad por ID (T-17c, T-17d)."""
        ed = nuevo()
        g1, g2 = ed.add_partial("G1"), ed.add_partial("G2")
        a, b = ed.add_step(g1, "A", True), ed.add_step(g1, "B")
        c, d = ed.add_step(g2, "C", True), ed.add_step(g2, "D")
        h1, h2 = ed.add_step("g", "H1", True), ed.add_step("g", "H2", True)
        r = lambda codigo, op, *args, **kw: self.rechaza(ed, codigo, op, *args, **kw)  # noqa: E731
        f = ed.add_force(a, g2, "empty")  # G1 fuerza a G2
        r("D-JERARQUIA-CICLO", ed.add_force, c, g1, "empty")  # G2 fuerza a G1: ciclo (T-17d)
        r("D-JERARQUIA-CICLO", ed.add_force, b, g1, "initial")  # un parcial no se fuerza a sí mismo
        r("D-REF", ed.add_force, "no-existe", g1, "empty")
        r("D-REF", ed.add_force, h1, "no-existe", "empty")
        r("D-FORMATO", ed.add_force, h1, g1, "otra")
        r("D-FORMATO", ed.add_force, h1, g1, "explicit")  # «explicit» exige su conjunto
        r("D-FORMATO", ed.add_force, h1, g1, "empty", [a])  # y solo «explicit» lo lleva
        r("D-REF", ed.add_force, h1, g1, "explicit", [c])  # etapas del destino
        # set_force: lo mismo al cambiar
        r("D-JERARQUIA-CICLO", ed.set_force, f, target_partial=g1)
        r("D-JERARQUIA-CICLO", ed.set_force, f, source_step=c)
        r("D-REF", ed.set_force, f, source_step="no-existe")
        r("D-REF", ed.set_force, "no-existe", kind="empty")
        r("D-FORMATO", ed.set_force, f, kind="explicit")  # sin conjunto
        r("D-FORMATO", ed.set_force, f, steps=[c])  # la forma «vacía» no lleva conjunto
        r("D-REF", ed.set_force, f, kind="explicit", steps=[a])  # etapa de otro parcial
        r("D-REF", ed.delete_force, a)  # no es una orden
        # explícita con el conjunto repetido: se queda con uno; cambiar el destino exige las etapas del nuevo
        ed.set_force(f, kind="explicit", steps=[c, c])
        self.assertEqual(ed.get(f)["targetSteps"], [c])
        r("D-REF", ed.set_force, f, target_partial=g1)  # el conjunto era de G2
        # conflicto posible: se acepta, validate() avisa y el arranque se detiene sin elegir (T-17c)
        ed.delete_force(f)
        f1 = ed.add_force(h1, g2, "explicit", [c])
        f2 = ed.add_force(h2, g2, "explicit", [d])
        res = ed.validate()
        conflicto = [x for x in res.diagnostics if x.code == "D-FORZADO-CONFLICTO"]
        self.assertEqual([(x.severity, x.element) for x in conflicto], [("advertencia", g2)])
        self.assertIn(f1, conflicto[0].evidence["ordenes"])
        self.assertIn(f2, conflicto[0].evidence["ordenes"])
        self.assertEqual(session(res.model, start=False).start()[0].code, "D-FORZADO-CONFLICTO")

    def test_SEDI147_editar_ordenes_de_forzado(self):
        """REQ-JER-02, REQ-EDT-05: `set_force` cambia destino, forma, etapas y origen conservando el ID de la orden;
        `delete_force` la quita; todo se deshace y se rehace."""
        ed = nuevo()
        g1, g2 = ed.add_partial("G1"), ed.add_partial("G2")
        b = ed.add_step(g1, "B", True)
        d = ed.add_step(g2, "D", True)
        e = ed.add_step(g2, "E")
        h = ed.add_step("g", "H", True)
        f = ed.add_force(h, g1, "explicit", [b])
        s0 = copy.deepcopy(ed.model["forces"])
        ed.set_force(f, target_partial=g2, kind="explicit", steps=[d, e])
        self.assertEqual(ed.get(f), {"id": f, "sourceStepRef": h, "targetPartialRef": g2, "targetKind": "explicit",
                                     "targetSteps": [d, e]})
        ed.set_force(f, kind="initial")
        self.assertNotIn("targetSteps", ed.get(f))
        ed.set_force(f, source_step=b, kind="current")
        self.assertEqual((ed.get(f)["sourceStepRef"], ed.get(f)["targetKind"]), (b, "current"))
        self.assertEqual(len(ed.model["forces"]), 1, "sigue siendo una orden, con el mismo ID")
        self.assertTrue(ed.validate().can_simulate)
        for _ in range(3):
            ed.undo()
        self.assertEqual(ed.model["forces"], s0)
        ed.redo()
        self.assertEqual(ed.get(f)["targetPartialRef"], g2)
        ed.delete_force(f)
        self.assertEqual(ed.model["forces"], [])
        ed.undo()
        self.assertEqual(len(ed.model["forces"]), 1)

    def test_SEDI148_vaciar_un_recinto_activo_sigue_deteniendose_u08(self):
        """REQ-JER-06, U-08: forzar vacío un recinto con su encapsulante activa se detiene con D-SEM-PENDIENTE (U-08); con
        la encapsulante inactiva, el forzado se ignora (7.4 C), como en T-20c."""
        ed = nuevo()
        h = ed.add_step("g", "H", True)
        ed.set_step_kind(h, "enclosing")
        rec = ed.new_enclosure(h, "R")
        ed.add_step(rec.partial, "I", True)
        f0 = ed.add_step("g", "F0", True)
        ed.add_force(f0, rec.partial, "empty")
        res = ed.validate()
        self.assertTrue(res.can_simulate, [str(d) for d in res.diagnostics])
        d = session(res.model, start=False).start()[0]
        self.assertEqual((d.code, d.question), ("D-SEM-PENDIENTE", "U-08"))
        ed2 = nuevo()
        h = ed2.add_step("g", "H")
        ed2.set_step_kind(h, "enclosing")
        rec = ed2.new_enclosure(h, "R")
        ed2.add_step(rec.partial, "I")
        j = ed2.add_step(rec.partial, "J")
        f0 = ed2.add_step("g", "F0", True)
        ed2.add_force(f0, rec.partial, "explicit", [j])
        res = ed2.validate()
        self.assertTrue(res.can_simulate, [str(d) for d in res.diagnostics])
        self.assertEqual(sorted(res.model.steps[i].label for i in session(res.model).z.situation), ["F0"],
                         "el recinto sigue vacío: no se activa nada dentro de H inactiva (7.4 C)")

    def test_SEDI149_borrar_una_macroetapa_con_todo_lo_suyo(self):
        """REQ-EDT-05, REQ-MOD-07: borrar una macroetapa se lleva su expansión, su entrada y su salida, lo de dentro (también
        macroetapas anidadas, recintos y órdenes) y los enlaces que apuntaban a ella; no deja referencias rotas; se
        deshace de una vez."""
        ed = nuevo()
        entradas(ed, "p", "q")
        a, b = ed.add_step("g", "A", True, at=(0, 0)), ed.add_step("g", "B")
        mac = ed.add_macro("g", "M", at=(100, 100))
        ed.move(mac.entry, 300, 20)
        k = ed.add_step(mac.partial, "K")
        inner = ed.add_macro(mac.partial, "N", expansion_label="XN")
        ed.add_transition(mac.partial, "q", pre=[mac.entry], post=[k])
        ed.add_transition(mac.partial, "q", pre=[k], post=[inner.macro])
        ed.add_transition(mac.partial, "q", pre=[inner.macro], post=[mac.exit])
        enc = ed.add_step(mac.partial, "EH")
        ed.set_step_kind(enc, "enclosing")
        rec = ed.new_enclosure(enc, "RR")
        ed.add_step(rec.partial, "RI")
        t1, _ = ed.add_transition("g", "p", pre=[a], post=[mac.macro])
        t2, _ = ed.add_transition("g", "p", pre=[mac.macro], post=[b])
        t3, _ = ed.add_transition("g", "p", pre=[b], post=[a])
        fuera = ed.add_partial("Fuera")
        ed.add_step(fuera, "XF", True)
        f_sale = ed.add_force(k, fuera, "empty")  # desde dentro de la macroetapa hacia fuera
        f_entra = ed.add_force(a, mac.partial, "empty")  # desde fuera hacia la expansión
        plan = ed.plan_delete([mac.macro])
        muertos = set(plan["elements"])
        self.assertTrue({mac.macro, mac.expansion, mac.partial, mac.entry, mac.exit, k, inner.macro, inner.expansion,
                         inner.partial, inner.entry, inner.exit, enc, rec.enclosure, rec.partial, f_sale, f_entra} <= muertos)
        self.assertEqual(plan["affectedTransitions"], sorted([t1, t2]))
        antes = copy.deepcopy((ed.model, ed.presentation))
        ed.delete([mac.macro])
        m = ed.model
        self.assertEqual([p["label"] for p in m["partials"]], ["g", "Fuera"])
        self.assertEqual(sorted(s["label"] for s in m["steps"]), ["A", "B", "XF"])
        self.assertEqual((m["forces"], m["hierarchy"]), ([], VACIA))
        self.assertEqual([(t["preRefs"], t["postRefs"]) for t in m["transitions"]],
                         [([a], []), ([], [b]), ([b], [a])], "los enlaces a la macroetapa desaparecen, no se inventan otros")
        self.assertFalse({x["elementRef"] for x in ed.presentation["elementLayouts"]} & muertos)
        # lo que queda no tiene referencias rotas ni nada jerárquico mal; solo las dos transiciones que perdieron un lado
        res = ed.validate()
        self.assertEqual({(x.code, x.element) for x in res.diagnostics}, {("D-FORMATO", t2)})
        ed.undo()
        self.assertEqual((ed.model, ed.presentation), antes, "restauración exacta en un paso")
        # borrar la expansión por su parcial se lleva la macroetapa: no hay macroetapa sin expansión
        ed.delete([mac.partial])
        self.assertEqual(ed.model["hierarchy"], VACIA)
        self.assertNotIn(mac.macro, ed.get(t1)["postRefs"])
        self.assertEqual({(x.code, x.element) for x in ed.validate().diagnostics}, {("D-FORMATO", t2)})

    def test_SEDI150_borrar_encapsulantes_recintos_y_etapas_con_marcas_u_ordenes(self):
        """REQ-EDT-05, REQ-JER-05: borrar una etapa marcada o una de un conjunto explícito las quita de su recinto y de su
        orden; borrar un recinto (su parcial, o él mismo) lo borra entero y deja la encapsulante sin recintos; borrar el
        origen o el destino de una orden la borra."""
        ed = nuevo()
        h = ed.add_step("g", "H", True)
        ed.set_step_kind(h, "enclosing")
        rec = ed.new_enclosure(h, "R")
        i, j, k = ed.add_step(rec.partial, "I", True), ed.add_step(rec.partial, "J"), ed.add_step(rec.partial, "K")
        ed.set_activation(j)
        ed.set_activation(k)
        g, g2 = ed.add_partial("G"), ed.add_partial("G2")
        a, b = ed.add_step(g, "A", True), ed.add_step(g, "B")
        ed.add_step(g2, "C", True)
        f_exp = ed.add_force(h, g, "explicit", [a, b])
        f_orig = ed.add_force(i, g2, "initial")
        # una etapa marcada se borra: desaparece del enlace de activación; una de la orden, de su conjunto
        plan = ed.plan_delete([j, b])
        self.assertEqual(plan["affectedHierarchy"], sorted([rec.enclosure, f_exp]))
        ed.delete([j, b])
        self.assertEqual(ed.get(rec.enclosure)["activationRefs"], [k])
        self.assertEqual(ed.get(f_exp)["targetSteps"], [a])
        self.assertEqual(ed.validate().diagnostics, [])
        ed.undo()
        self.assertEqual((ed.get(rec.enclosure)["activationRefs"], ed.get(f_exp)["targetSteps"]), ([j, k], [a, b]))
        # borrar el origen de una orden la borra; borrar su parcial destino, también
        ed.delete([i])
        self.assertEqual([f["id"] for f in ed.model["forces"]], [f_exp])
        ed.delete([g])
        self.assertEqual(ed.model["forces"], [])
        self.assertEqual({d.code for d in ed.validate().diagnostics}, {"D-JERARQUIA-INICIAL"},
                         "H inicial se queda con un recinto sin etapa inicial: lo avisa el modelo, no se completa solo")
        ed.undo()
        ed.undo()
        self.assertIn(f_orig, {f["id"] for f in ed.model["forces"]})
        # borrar el recinto por su parcial: se va el recinto con su contenido; la encapsulante se queda sin recintos
        antes = copy.deepcopy((ed.model, ed.presentation))
        ed.delete([rec.partial])
        self.assertEqual(ed.model["hierarchy"]["enclosures"], [])
        self.assertEqual([s["label"] for s in ed.model["steps"]], ["H", "A", "B", "C"])
        self.assertEqual(ed.get(h)["kind"], "enclosing", "sigue siendo una encapsulante, sin recintos")
        self.assertEqual([f["id"] for f in ed.model["forces"]], [f_exp], "la orden de origen H se queda; la de I se va")
        self.assertEqual(ed.validate().diagnostics, [])
        ed.undo()
        self.assertEqual((ed.model, ed.presentation), antes)
        # y por el propio recinto: lo mismo
        ed.delete([rec.enclosure])
        self.assertEqual((ed.model["hierarchy"]["enclosures"], [p["label"] for p in ed.model["partials"]]),
                         ([], ["g", "G", "G2"]))
        # una encapsulante vuelve a ordinaria cuando ya no tiene recintos
        ed.set_step_kind(h, "ordinary")
        self.assertEqual(ed.get(h)["kind"], "ordinary")
        self.assertEqual(ed.validate().diagnostics, [])

    def test_SEDI151_renombrar_parciales_y_macroetapas(self):
        """REQ-EDT-06, REQ-MOD-06: `rename` cambia la etiqueta de un parcial o de una macroetapa conservando su ID y la
        revisión semántica, actualiza el texto de las receptividades que la usan y diagnostica la colisión."""
        ed = nuevo()
        entradas(ed, "p")
        g = ed.add_partial("G")
        a, b = ed.add_step("g", "A", True), ed.add_step("g", "B")
        ed.add_step(g, "X", True)
        mac = ed.add_macro("g", "M")
        _, diag = ed.add_transition("g", "activePartial(G) AND activeMacro(M) AND p", pre=[a], post=[b])
        self.assertIsNone(diag)
        rev = ed.revision
        usos = ed.rename(g, "Cinta")
        ed.rename(mac.macro, "Prensa")
        self.assertEqual((ed.get(g)["label"], ed.get(mac.macro)["label"]), ("Cinta", "Prensa"))
        self.assertEqual([e["text"] for e in ed.model["expressions"]], ["activePartial(Cinta) AND activeMacro(Prensa) AND p"])
        self.assertEqual(len(usos), 1)
        self.assertEqual(ed.revision, rev, "renombrar no cambia el significado (H-13)")
        self.assertEqual(ed.validate().diagnostics, [])
        # colisión: otro parcial o macroetapa con ese nombre; el mismo nombre no es colisión; nombre inválido
        otro = ed.add_partial("Otro")
        seg = ed.add_macro("g", "Segunda")
        self.rechaza(ed, "D-NOMBRE-COLISION", ed.rename, otro, "Cinta")
        self.rechaza(ed, "D-NOMBRE-COLISION", ed.rename, mac.partial, "Cinta")
        self.rechaza(ed, "D-NOMBRE-COLISION", ed.rename, seg.macro, "Prensa")
        self.rechaza(ed, "D-FORMATO", ed.rename, otro, "")
        ed.rename(otro, "Otro")
        # una orden o una expansión no tienen nombre
        f = ed.add_force(a, g, "empty")
        self.rechaza(ed, "D-FORMATO", ed.rename, f, "x")
        self.rechaza(ed, "D-FORMATO", ed.rename, mac.expansion, "x")
        # renombrar la expansión por su parcial no toca a la macroetapa
        ed.rename(mac.partial, "Cuerpo")
        self.assertEqual((ed.get(mac.partial)["label"], ed.get(mac.macro)["label"]), ("Cuerpo", "Prensa"))
        self.assertEqual(ed.validate().diagnostics, [])

    def test_SEDI152_mover_la_macroetapa_y_consultar_la_jerarquia(self):
        """REQ-EDT-03, REQ-JER-07, REQ-EDT-08: `move` coloca una macroetapa como a una etapa (solo presentación: la
        revisión no cambia) y se deshace; `partial_roles` y `macro_info` bastan para mostrar y abrir la jerarquía."""
        ed = nuevo()
        ed.add_step("g", "A", True)
        mac = ed.add_macro("g", "M")
        self.assertNotIn(mac.macro, layout_from_presentation(ed.presentation))
        rev = ed.revision
        ed.move(mac.macro, 300, 120)
        self.assertEqual(layout_from_presentation(ed.presentation)[mac.macro], (300.0, 120.0))
        ed.move(mac.macro, 40, 50)
        self.assertEqual(layout_from_presentation(ed.presentation)[mac.macro], (40.0, 50.0))
        self.assertEqual(ed.revision, rev)
        ed.undo()
        self.assertEqual(layout_from_presentation(ed.presentation)[mac.macro], (300.0, 120.0))
        ed.undo()
        self.assertNotIn(mac.macro, layout_from_presentation(ed.presentation))
        # la consulta: raíz, expansión (con su macroetapa, entrada y salida) y recinto (con su encapsulante y marcas)
        h = ed.add_step("g", "H")
        ed.set_step_kind(h, "enclosing")
        rec = ed.new_enclosure(h, "R")
        k = ed.add_step(rec.partial, "K")
        ed.set_activation(k)
        roles = ed.partial_roles()
        self.assertEqual(list(roles), ["g", mac.partial, rec.partial], "en el orden de los parciales")
        self.assertEqual(roles["g"], {"kind": "root", "parent": None, "text": "raíz"})
        self.assertEqual(roles[mac.partial], {"kind": "expansion", "parent": "g", "macro": mac.macro, "expansion": mac.expansion,
                                              "entry": mac.entry, "exit": mac.exit, "text": "expansión de la macroetapa M"})
        self.assertEqual(roles[rec.partial], {"kind": "enclosure", "parent": "g", "enclosure": rec.enclosure, "ownerStep": h,
                                              "activation": [k], "text": "recinto de la encapsulante H"})
        self.assertEqual(ed.macro_info(mac.macro).partial, mac.partial)

    def test_SEDI153_deshacer_y_rehacer_cada_operacion_de_jerarquia(self):
        """REQ-EDT-05: cada operación de jerarquía es una transacción que se deshace y se rehace sin dejar restos, también
        agrupadas; una operación fallida no entra en el historial."""
        ed = nuevo()
        entradas(ed, "p")
        h = ed.add_step("g", "H", True)
        g = ed.add_partial("G")
        b = ed.add_step(g, "B", True)
        s = ed.add_partial("S", owner="g")
        snaps = [copy.deepcopy((ed.model, ed.presentation))]

        def paso(op, *args, **kw):
            res = op(*args, **kw)
            snaps.append(copy.deepcopy((ed.model, ed.presentation)))
            return res
        mac = paso(ed.add_macro, "g", "M", at=(10, 10))
        paso(ed.set_step_kind, h, "enclosing")
        rec = paso(ed.new_enclosure, h, "R")
        k = paso(ed.add_step, rec.partial, "K", True)
        paso(ed.set_activation, k)
        f = paso(ed.add_force, h, g, "explicit", [b])
        paso(ed.set_force, f, kind="current")
        paso(ed.rename, mac.macro, "N")
        paso(ed.move, mac.macro, 99, 99)
        paso(ed.delete_force, f)
        paso(ed.set_activation, k, False)
        paso(ed.add_enclosure, h, s, [])
        paso(ed.delete, [mac.macro])
        pila = len(ed.undo_stack)
        self.rechaza(ed, "D-REF", ed.add_force, h, "no-existe", "empty")
        self.assertEqual(len(ed.undo_stack), pila)
        for anterior in reversed(snaps[:-1]):
            ed.undo()
            self.assertEqual((ed.model, ed.presentation), anterior)
        for posterior in snaps[1:]:
            ed.redo()
            self.assertEqual((ed.model, ed.presentation), posterior)
        # agrupadas: «macroetapa con su primera etapa» se deshace de una vez
        n = len(ed.undo_stack)
        with ed.group("macroetapa y etapa interior"):
            m2 = ed.add_macro("g", "Otra")
            ed.add_step(m2.partial, "Q")
        self.assertEqual(len(ed.undo_stack), n + 1)
        ed.undo()
        self.assertFalse(any(x["label"] == "Otra" for x in ed.model["hierarchy"]["macros"]))
        ed.redo()
        self.assertTrue(any(x["label"] == "Otra" for x in ed.model["hierarchy"]["macros"]))

    def test_SEDI154_ida_y_vuelta_y_vista_con_macroetapas_recintos_y_ordenes(self):
        """REQ-DAT-02, REQ-MOD-07, REQ-JER-07: un modelo con macroetapa, recinto con enlace de activación y orden de forzado,
        hecho con el editor, se guarda y se abre sin pérdida, simula igual y la vista (`Vista`) lo representa con la
        macroetapa, la expansión, el recinto, el «*» y la orden G{…}."""
        ed = nuevo()
        entradas(ed, "p", "q", "r")
        a, b = ed.add_step("g", "A", True, at=(100, 60)), ed.add_step("g", "B", at=(100, 380))
        h = ed.add_step("g", "H", True, at=(400, 60))
        ed.set_step_kind(h, "enclosing")
        mac = ed.add_macro("g", "M", at=(100, 220))
        ed.move(mac.entry, 600, 60)
        ed.move(mac.exit, 600, 300)
        k = ed.add_step(mac.partial, "K", at=(600, 180))
        ed.add_transition(mac.partial, "q", pre=[mac.entry], post=[k], at=(600, 120), label="tq")
        ed.add_transition(mac.partial, "r", pre=[k], post=[mac.exit], at=(600, 240), label="tr")
        tp, _ = ed.add_transition("g", "p", pre=[a], post=[mac.macro], at=(100, 140), label="tp")
        ed.add_transition("g", "true", pre=[mac.macro], post=[b], at=(100, 300), label="ts")
        ed.add_transition("g", "NOT p", pre=[b], post=[a], at=(250, 220), label="tb")
        rec = ed.new_enclosure(h, "R")
        i = ed.add_step(rec.partial, "I", True, at=(400, 200))
        j = ed.add_step(rec.partial, "J", at=(400, 340))
        k2 = ed.add_step(rec.partial, "K2", at=(520, 200))
        ed.set_activation(k2)
        ed.add_transition(rec.partial, "q", pre=[i], post=[j], at=(400, 270), label="ti")
        g = ed.add_partial("G")
        x1, x2 = ed.add_step(g, "X1", True, at=(800, 60)), ed.add_step(g, "X2", at=(800, 220))
        ed.add_transition(g, "r", pre=[x1], post=[x2], at=(800, 140), label="tg")
        ed.add_force(h, g, "explicit", [x2])
        self.assertEqual(ed.validate().diagnostics, [])
        guion = [(1, {"p": True}), (2, {"q": True}), (3, {"r": True}), (4, {"p": False})]
        esperado = corrida(ed.model, guion)
        self.assertEqual(esperado[0][0]["ordenes"], [("G", "explicit", ("X2",))])
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "Jerarquías")
            add_document(pj, ed.model)
            add_document(pj, ed.presentation)
            save_project(Path(tmp), pj)
            op = open_model(Path(tmp))
        self.assertEqual(op.doc, ed.model, "sin pérdida")
        self.assertEqual(op.presentations[0], ed.presentation)
        self.assertEqual(corrida(op.doc, guion), esperado)
        self.assertEqual(validate_model(op.doc).diagnostics, [])
        v = Vista("m", "t", "", lambda: (op.doc, layout_from_presentation(op.presentations[0])), normalize_options(None),
                  presentation=op.presentations[0])
        mv = v.model
        self.assertEqual([(x["id"], x["x"], x["y"], x["expansion"], x["entry"], x["exit"]) for x in mv["macros"]],
                         [(mac.macro, 100.0, 220.0, mac.partial, mac.entry, mac.exit)])
        tipos = {p["id"]: (p["kind"], p["label"]) for p in mv["partials"]}
        self.assertEqual(tipos, {mac.partial: ("expansion", "M"), rec.partial: ("enclosure", "R"), g: ("partial", "G")})
        self.assertEqual(next(p for p in mv["partials"] if p["id"] == mac.partial)["macro"], mac.macro)
        self.assertEqual(next(p for p in mv["partials"] if p["id"] == rec.partial)["ownerStep"], h)
        pasos = {s["id"]: s for s in mv["steps"]}
        self.assertEqual((pasos[h]["kind"], pasos[k2]["activation"], pasos[j]["activation"]), ("enclosing", True, False))
        self.assertEqual((pasos[mac.entry]["kind"], pasos[mac.exit]["kind"]), ("entry", "exit"))
        self.assertEqual((pasos[mac.entry]["x"], pasos[mac.entry]["y"]), (600.0, 60.0))
        orden = [x for x in pasos[h]["actions"] if x["kind"] == "force"]
        self.assertEqual([("".join(seg["t"] for seg in x["text"]), x["target"]) for x in orden], [("G{X2}", g)])
        tr = {t["id"]: t for t in mv["transitions"]}
        self.assertEqual((tr[tp]["pre"], tr[tp]["post"]), ([a], [mac.macro]))
        estado = v.state()
        self.assertEqual([f["target"] for f in estado["forces"]], [g])
        self.assertEqual(estado["macros"], {mac.macro: False})

    def test_SEDI155_el_recinto_toma_el_dueno_y_el_contenido_cuenta_en_el_dueno(self):
        """REQ-JER-05, REQ-MOD-07, P-IMP-27: `add_enclosure` pone como dueño del parcial el de la encapsulante si no declara
        ninguno (como `new_enclosure` y `add_macro`) y rechaza otro; el contenido cuenta en X_dueño (hijos al compilar y
        `activePartial(dueño)` mientras la macroetapa está activa)."""
        ed = nuevo()
        h = ed.add_step("g", "H", True)
        ed.set_step_kind(h, "enclosing")
        rp = ed.add_partial("R")
        self.assertNotIn("ownerRef", ed.get(rp))
        ed.add_enclosure(h, rp)
        self.assertEqual(ed.get(rp)["ownerRef"], "g")
        ed.add_step(rp, "I", True)
        res = ed.validate()
        self.assertEqual(res.diagnostics, [])
        self.assertEqual(res.model.partials["g"]["children"], {rp})
        self.assertEqual(ed.partial_roles()[rp]["parent"], "g")
        # un dueño declarado que coincide se conserva; uno que no coincide se rechaza (D-FORMATO) y no cambia nada
        otro = ed.add_partial("Otro")
        x = ed.add_step(otro, "X", True)
        ed.set_step_kind(x, "enclosing")
        q = ed.add_partial("Q", owner="g")
        self.rechaza(ed, "D-FORMATO", ed.add_enclosure, x, q)
        h2 = ed.add_step("g", "H2")
        ed.set_step_kind(h2, "enclosing")
        ed.add_enclosure(h2, q)
        self.assertEqual(ed.get(q)["ownerRef"], "g")
        # en la expansión de una macroetapa sí se nota: con A inactiva, g no tiene etapas activas y X_g sigue siendo cierta
        ed2 = nuevo()
        entradas(ed2, "p")
        y = ed2.add_variable("y", "output", {"kind": "bool"})
        a = ed2.add_step("g", "A", True)
        mac = ed2.add_macro("g", "M")
        ed2.add_transition("g", "p", pre=[a], post=[mac.macro])
        qp = ed2.add_partial("Cuenta")
        ed2.add_continuous_action(ed2.add_step(qp, "S", True), y, "activePartial(g)")
        self.assertEqual(corrida(ed2.model, [(1, {"p": True})])[0][1], {"situacion": ["E1", "S"], "salidas": ["y"],
                                                                         "macros": {"M": True}, "ordenes": []})
        sin_dueno = copy.deepcopy(ed2.model)
        next(pt for pt in sin_dueno["partials"] if pt["id"] == mac.partial).pop("ownerRef")
        self.assertEqual(corrida(sin_dueno, [(1, {"p": True})])[0][1]["salidas"], [], "sin dueño, la expansión no cuenta")

    def test_SEDI156_add_partial_rechaza_un_nombre_repetido(self):
        """REQ-EDT-06: dos parciales no se llaman igual (D-NOMBRE-COLISION), como al renombrarlos o al crear la expansión
        de una macroetapa o un recinto; las mayúsculas distinguen; lo rechazado no entra en el historial."""
        ed = nuevo()
        self.rechaza(ed, "D-NOMBRE-COLISION", ed.add_partial, "g")  # el parcial raíz ya se llama g
        self.rechaza(ed, "D-FORMATO", ed.add_partial, "")
        ed.add_partial("G")
        self.rechaza(ed, "D-NOMBRE-COLISION", ed.add_partial, "G", owner="g")
        mac = ed.add_macro("g", "M")  # en un grafcet sin ninguna etapa inicial: el diseño a medias no impide crear lo primero
        self.rechaza(ed, "D-NOMBRE-COLISION", ed.add_partial, "M")  # el parcial de la expansión de M
        self.assertEqual(ed.get(mac.partial)["label"], "M")
        self.assertEqual([d.code for d in ed.validate().diagnostics], ["D-FORMATO"], "sin etapas iniciales (6.1 A): lo avisa validate()")

    def test_SEDI157_nombres_visibles_de_ordenes_recintos_y_expansiones_tambien_en_los_diagnosticos(self):
        """REQ-EDT-09, REQ-JER-07: `display_names` da nombre a las órdenes de forzado, a los recintos y a las expansiones sin
        cambiar los que ya daba, y `Vista` los usa en el mensaje y en la evidencia de los diagnósticos (D-FORZADO-CONFLICTO,
        D-PROPIETARIO…), que no muestran ID internos; el elemento sigue siendo su ID. Un ID legible (el de un ejemplo) no
        cambia."""
        ed = Editor(new_grafcet_document("m"))  # con los ID internos que crea el editor (UUID)
        h1, h2 = ed.add_step("g", "H1", True), ed.add_step("g", "H2", True)
        h = ed.add_step("g", "H3")
        ed.set_step_kind(h, "enclosing")
        rec = ed.new_enclosure(h, "R")
        ed.add_step(rec.partial, "I")
        mac = ed.add_macro("g", "M")
        g = ed.add_partial("G")
        c, d = ed.add_step(g, "C", True), ed.add_step(g, "D")
        f1, f2 = ed.add_force(h1, g, "explicit", [c]), ed.add_force(h2, g, "explicit", [d])
        f3, f4 = ed.add_force(h, g, "current"), ed.add_force(h, g, "empty")
        f5 = ed.add_force(h, g, "initial")
        nombres = display_names(ed.model)
        self.assertEqual([nombres[f] for f in (f1, f2, f3, f4, f5)],
                         ["orden G{C} de H1", "orden G{D} de H2", "orden G{*} de H3", "orden G{ } de H3", "orden G{INIT} de H3"])
        self.assertEqual((nombres[rec.enclosure], nombres[mac.expansion]), ("recinto R", "expansión de M"))
        self.assertEqual((nombres[h1], nombres[g], nombres[mac.macro], nombres[mac.entry]), ("H1", "G", "M", "E1"))
        # los que ya había no cambian: sin las nuevas, lo mismo que antes
        nuevos = {f1, f2, f3, f4, f5, rec.enclosure, mac.expansion}
        self.assertEqual({k: v for k, v in nombres.items() if k not in nuevos},
                         {**{s["id"]: s["label"] for s in ed.model["steps"]}, **{p["id"]: p["label"] for p in ed.model["partials"]},
                          mac.macro: "M"})
        for clave in ("forzado", "encapsulacion", "macroetapa"):  # los ID legibles de los ejemplos no cambian
            self.assertTrue(all(i == n for i, n in display_names(EJEMPLOS[clave][2]()[0].doc).items()), clave)
        # una forma de orden desconocida no impide nombrar lo demás
        roto = copy.deepcopy(ed.model)
        roto["forces"][0]["targetKind"] = "otra"
        self.assertEqual(display_names(roto)[f1], "orden G{?} de H1")
        self.assertEqual(display_names(roto)[f2], "orden G{D} de H2")
        # D-FORZADO-CONFLICTO al arrancar (dos órdenes vigentes con objetivo distinto): sin ID en mensaje ni evidencia
        for x in (f3, f4, f5):
            ed.delete_force(x)
        v = Vista("m", "t", "", lambda: (ed.model, {}), normalize_options(None))
        diag = v.state()["diagnostics"][-1]
        self.assertEqual(diag["code"], "D-FORZADO-CONFLICTO")
        self.assertIn("orden G{C} de H1", diag["evidence"]["ordenes"])
        self.assertIn("orden G{D} de H2", diag["evidence"]["ordenes"])
        textos = [diag["message"], diag["correction"], *diag["evidence"].values()]
        self.assertFalse([t for t in textos if any(i in t for i in (f1, f2, g, c, d, h1, h2))], textos)
        self.assertEqual(diag["element"], g, "el elemento sigue siendo su ID: el dibujo lo busca")
        # D-PROPIETARIO: el recinto de H3 también es recinto de otra encapsulante (a mano: el editor no lo permite)
        doc = copy.deepcopy(ed.model)
        doc["steps"].append({"id": "h4", "label": "H4", "partialRef": "g", "kind": "enclosing", "initial": False,
                             "actionRefs": []})
        doc["partials"][0]["stepRefs"].append("h4")
        doc["hierarchy"]["enclosures"].append({"id": "r-doble", "ownerStepRef": "h4", "partialRef": rec.partial,
                                               "activationRefs": []})
        v = Vista("m", "t", "", lambda: (doc, {}), normalize_options(None))
        diag = next(x for x in v.state()["diagnostics"] if x["code"] == "D-PROPIETARIO")
        self.assertIn("recinto R", diag["message"])
        self.assertFalse([i for i in (rec.enclosure, rec.partial, "r-doble") if i in diag["message"]], diag["message"])
        self.assertIn(diag["element"], ("r-doble", rec.enclosure))

    def test_SEDI158_pegar_ignora_la_jerarquia_y_pega_las_etapas_como_ordinarias(self):
        """REQ-EDT-04, REQ-MOD-07: `copy` ignora las macroetapas, los recintos y las órdenes (aunque estén en la selección) y
        trata el enlace con una macroetapa como referencia externa; `paste` pega una etapa encapsulante, de entrada o de
        salida como ordinaria, sin estructura asociada, y el resultado no da D-FORMATO ni otro diagnóstico."""
        ed = nuevo()
        var = entradas(ed, "p")
        a = ed.add_step("g", "A", True)
        h = ed.add_step("g", "H")
        ed.set_step_kind(h, "enclosing")
        rec = ed.new_enclosure(h, "R")
        ed.set_activation(ed.add_step(rec.partial, "K"))
        mac = ed.add_macro("g", "M")
        tp, _ = ed.add_transition("g", "p", pre=[a], post=[mac.macro])
        g = ed.add_partial("G")
        ed.add_step(g, "C", True)
        f = ed.add_force(h, g, "empty")
        self.assertEqual(ed.validate().diagnostics, [])
        hier = copy.deepcopy((ed.model["hierarchy"], ed.model["forces"]))
        frag = ed.copy([a, h, mac.entry, mac.exit, tp, mac.macro, mac.expansion, rec.enclosure, f])
        self.assertEqual(sorted(x["id"] for x in frag.entities["steps"]), sorted([a, h, mac.entry, mac.exit]))
        self.assertEqual([x["id"] for x in frag.entities["transitions"]], [tp])
        self.assertEqual(ed.plan_paste(frag), {mac.macro: "macros", var["p"]: "variables"},
                         "el enlace con la macroetapa es una referencia externa, como el de la variable")
        mapping = ed.paste(frag, "g", {mac.macro: "keep", var["p"]: "keep"})
        pegadas = [s for s in ed.model["steps"] if s["id"] in mapping.values()]
        self.assertEqual(sorted(s["label"] for s in pegadas), ["A (copia)", "E1", "H (copia)", "S1"])  # E1 y S1 no chocan en g
        self.assertEqual({s["kind"] for s in pegadas}, {"ordinary"})
        self.assertEqual((ed.model["hierarchy"], ed.model["forces"]), hier, "no se crea ninguna macroetapa, recinto ni orden")
        self.assertEqual(ed.get(h)["kind"], "enclosing", "el original no cambia")
        self.assertEqual(ed.get(mac.entry)["kind"], "entry")
        self.assertEqual(ed.validate().diagnostics, [])
        # solo jerarquía en la selección: no hay nada que copiar ni que pegar
        vacio = ed.copy([mac.macro, mac.expansion, rec.enclosure, f])
        self.assertEqual((vacio.entities["steps"], vacio.entities["transitions"], vacio.external_refs), ([], [], {}))

    def test_SEDI193_una_macroetapa_unida_a_una_barra_se_ve_unida_en_la_vista(self):
        """REQ-JER-04, REQ-MOD-03, REQ-MOD-07: una etapa y una macroetapa por encima de una barra de simultaneidad Y y la barra
        por encima de una transición (preRefs = [A, M]): `Vista` lleva la macroetapa en `arriba` de la barra (como una etapa) y
        la transición no la dibuja directa (`preDib` vacío), y los conectores de la barra incluyen el de la macroetapa. Los
        ejemplos del banco no cambian: no tienen barras."""
        from grafcet.routing import enlaces
        ed = nuevo()
        entradas(ed, "p")
        a, b = ed.add_step("g", "A", True, at=(100, 60)), ed.add_step("g", "B", at=(100, 380))
        mac = ed.add_macro("g", "M", at=(300, 60))
        t1, _ = ed.add_transition("g", "p", at=(200, 220), label="t1")
        ed.connect(t1, b)
        barra = ed.add_bar("Y", (100, 140))
        for ident in (a, mac.macro):
            ed.bar_link(barra, "arriba", ident)
        ed.bar_link(barra, "abajo", t1)
        self.assertEqual(ed.get(t1)["preRefs"], [a, mac.macro], "el modelo: las dos etapas anteriores de la transición")
        v = Vista("m", "t", "", lambda: (ed.model, layout_from_presentation(ed.presentation)), normalize_options(None),
                  presentation=ed.presentation)
        mv = v.model
        (bv,) = mv["bars"]
        self.assertEqual((bv["arriba"], bv["abajo"]), ([a, mac.macro], [t1]))
        tr = next(t for t in mv["transitions"] if t["id"] == t1)
        self.assertEqual((tr["pre"], tr["preDib"]), ([a, mac.macro], []), "se dibuja por la barra, no directa")
        ids = {e["id"] for e in enlaces(mv)}
        self.assertTrue({f"{barra}|{a}|barra", f"{barra}|{mac.macro}|barra", f"{barra}|{t1}|barra"} <= ids, ids)
        self.assertFalse({f"{t1}|{a}|pre", f"{t1}|{mac.macro}|pre"} & ids, "sin enlaces directos duplicados")
        # una macroetapa borrada deja de figurar en la barra (no se dibuja un extremo inexistente)
        ed.delete([mac.macro])
        v = Vista("m", "t", "", lambda: (ed.model, layout_from_presentation(ed.presentation)), normalize_options(None),
                  presentation=ed.presentation)
        self.assertEqual(v.model["bars"][0]["arriba"], [a])
        # ningún ejemplo lleva barras: su vista no cambia
        for clave, (titulo, _, construir) in EJEMPLOS.items():
            modelo, disposicion = construir()
            vista = Vista(clave, titulo, "", lambda: (modelo, disposicion), normalize_options(None))
            self.assertEqual(vista.model["bars"], [], clave)


if __name__ == "__main__":
    unittest.main()
