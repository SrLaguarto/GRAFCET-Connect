"""Regresiones del borrado de enlaces no ejecutables y reparación acotada al abrir."""
import copy
import tempfile
import unittest
from pathlib import Path

from grafcet.editor import Editor, new_grafcet_document
from grafcet.ids import IdGenerator
from grafcet.model import compute_revision
from grafcet.persistence import add_document, new_project, open_model, save_project


FIXTURE = Path(__file__).parent / "fixtures" / "salto_de_etapas"


def nuevo():
    return Editor(new_grafcet_document("m"), ids=IdGenerator("x"))


def barra_entre_transiciones():
    ed = nuevo()
    a, _ = ed.add_transition("g", "true", label="t1")
    b, _ = ed.add_transition("g", "true", label="t2")
    bar = ed.add_bar("Y", (100, 100))
    ed.bar_link(bar, "arriba", a)
    aviso = ed.bar_link(bar, "abajo", b)
    assert aviso.code == "D-ALTERNANCIA"
    return ed, a, b, bar


class BorradoDeBorradores(unittest.TestCase):
    def test_SDBR01_borrar_las_dos_transiciones_de_la_barra_incluye_el_borrador(self):
        """REQ-EDT-02, REQ-EDT-05: plan y borrado retiran la conexión dependiente completa."""
        ed, a, b, bar = barra_entre_transiciones()
        link = ed.model["draftLinks"][0]["id"]
        before = copy.deepcopy((ed.model, ed.presentation))
        n = len(ed.undo_stack)
        plan = ed.plan_delete([a, b])
        self.assertEqual(plan["elements"], sorted([a, b, link]))
        self.assertEqual(ed.delete([a, b]), plan)
        self.assertEqual(len(ed.undo_stack), n + 1)
        self.assertEqual(ed.model["draftLinks"], [])
        self.assertEqual(ed.bars()[0]["arriba"], [])
        self.assertEqual(ed.bars()[0]["abajo"], [])
        self.assertNotIn("D-ALTERNANCIA", {d.code for d in ed.validate().diagnostics})
        after = copy.deepcopy((ed.model, ed.presentation))
        ed.undo()
        self.assertEqual((ed.model, ed.presentation), before)
        ed.redo()
        self.assertEqual((ed.model, ed.presentation), after)
        self.assertEqual(ed.bars()[0]["id"], bar)

    def test_SDBR02_borrar_un_extremo_preserva_borradores_ajenos(self):
        """REQ-EDT-02, REQ-EDT-05: cualquiera de los extremos arrastra solo sus enlaces."""
        for lado in ("fromRef", "toRef"):
            with self.subTest(lado=lado):
                ed, a, b, _ = barra_entre_transiciones()
                c, _ = ed.add_transition("g", "true", label="t3")
                d, _ = ed.add_transition("g", "true", label="t4")
                ed.connect(c, d)
                dependent, valid = copy.deepcopy(ed.model["draftLinks"])
                ident = dependent[lado]
                self.assertIn(dependent["id"], ed.plan_delete([ident])["elements"])
                ed.delete([ident])
                self.assertEqual(ed.model["draftLinks"], [valid])
                self.assertIn(b if ident == a else a, {t["id"] for t in ed.model["transitions"]})
                ed.undo()
                self.assertEqual(ed.model["draftLinks"], [dependent, valid])
                ed.redo()
                self.assertEqual(ed.model["draftLinks"], [valid])

    def test_SDBR03_keep_dangling_conserva_referencias_ordinarias(self):
        """REQ-EDT-02, REQ-EDT-05: conservar referencias ordinarias no conserva conexiones fantasma."""
        ed = nuevo()
        a = ed.add_step("g", "A", True)
        b = ed.add_step("g", "B")
        t, _ = ed.add_transition("g", "true", pre=[a], post=[b])
        ed.connect(a, b)
        ed.delete([a], keep_dangling=True)
        self.assertEqual(ed.get(t)["preRefs"], [a])
        self.assertEqual(ed.model["draftLinks"], [])
        self.assertIn("D-REF", {d.code for d in ed.validate().diagnostics})
        ed.undo()
        self.assertEqual(len(ed.model["draftLinks"]), 1)

    def test_SDBR04_borrar_el_borrador_conserva_sus_extremos(self):
        """REQ-EDT-02, REQ-EDT-05: se puede borrar solo la conexión no ejecutable."""
        ed, a, b, _ = barra_entre_transiciones()
        link = ed.model["draftLinks"][0]["id"]
        self.assertEqual(ed.plan_delete([link])["elements"], [link])
        ed.delete([link])
        self.assertEqual({t["id"] for t in ed.model["transitions"]}, {a, b})
        self.assertEqual(ed.model["draftLinks"], [])

    def test_SDBR05_desunir_o_borrar_barra_elimina_solo_sus_parejas(self):
        """REQ-EDT-02, REQ-EDT-05: barra y enlaces cambian juntos y el historial los recupera."""
        for operation in ("desunir_arriba", "desunir_abajo", "borrar"):
            with self.subTest(operation=operation):
                ed, a, b, bar = barra_entre_transiciones()
                c, _ = ed.add_transition("g", "true", label="t3")
                ed.connect(a, c)
                valid = copy.deepcopy(ed.model["draftLinks"][1])
                before = copy.deepcopy((ed.model, ed.presentation))
                n = len(ed.undo_stack)
                if operation == "borrar":
                    ed.delete_bar(bar)
                else:
                    ed.bar_unlink(bar, a if operation.endswith("arriba") else b)
                self.assertEqual(ed.model["draftLinks"], [valid])
                self.assertEqual(len(ed.undo_stack), n + 1)
                after = copy.deepcopy((ed.model, ed.presentation))
                ed.undo()
                self.assertEqual((ed.model, ed.presentation), before)
                ed.redo()
                self.assertEqual((ed.model, ed.presentation), after)

    def test_SDBR06_borrar_extremo_y_despues_la_barra_no_deja_huerfanos(self):
        """REQ-EDT-02, REQ-EDT-05: borrar etapas o transiciones limpia también los extremos de la barra."""
        ed, a, b, bar = barra_entre_transiciones()
        ed.delete([a])
        ed.delete_bar(bar)
        self.assertEqual(ed.model["draftLinks"], [])
        self.assertEqual([t["id"] for t in ed.model["transitions"]], [b])
        ed.undo()
        self.assertEqual(ed.model["draftLinks"], [])
        ed.undo()
        self.assertEqual(len(ed.model["draftLinks"]), 1)

    def test_SDBR07_borrar_jerarquia_arrastra_borradores_interiores_y_exteriores(self):
        """REQ-EDT-05, REQ-JER-07: los borradores siguen el alcance transitivo del borrado."""
        for kind in ("macro", "recinto", "parcial"):
            with self.subTest(kind=kind):
                ed = nuevo()
                exterior = ed.add_step("g", "Exterior", True)
                if kind == "macro":
                    macro = ed.add_macro("g", "M1")
                    partial, target, inner = macro.partial, macro.macro, macro.entry
                    ed.connect(exterior, macro.macro)
                elif kind == "recinto":
                    owner = ed.add_step("g", "Encapsulante")
                    ed.set_step_kind(owner, "enclosing")
                    partial = ed.new_enclosure(owner, "G1").partial
                    target = owner
                    inner = ed.add_step(partial, "Interior")
                else:
                    partial = ed.add_partial("G1")
                    target = partial
                    inner = ed.add_step(partial, "Interior")
                other = ed.add_step(partial, "Otra")
                ed.connect(inner, other)
                ed.connect(exterior, inner)
                ids = {d["id"] for d in ed.model["draftLinks"]}
                self.assertTrue(ids <= set(ed.plan_delete([target])["elements"]))
                before = copy.deepcopy((ed.model, ed.presentation))
                ed.delete([target])
                self.assertEqual(ed.model["draftLinks"], [])
                ed.undo()
                self.assertEqual((ed.model, ed.presentation), before)
                ed.redo()
                self.assertEqual(ed.model["draftLinks"], [])


class ReparacionAlAbrir(unittest.TestCase):
    def test_SDBR08_sanea_solo_enlaces_con_un_extremo_ausente_y_marca_dirty(self):
        """REQ-EDT-01, REQ-DAT-01: la reparación conserva entidades, vista y borradores editables."""
        ed, a, b, _ = barra_entre_transiciones()
        macro = ed.add_macro("g", "M1")
        step = ed.add_step("g", "A", True)
        ed.connect(macro.macro, step)
        doc = copy.deepcopy(ed.model)
        valid = copy.deepcopy(doc["draftLinks"])
        orphans = [
            {"id": "l-sin-origen", "fromRef": "ausente", "toRef": a},
            {"id": "l-sin-destino", "fromRef": b, "toRef": "ausente"},
            {"id": "l-sin-ambos", "fromRef": "ausente1", "toRef": "ausente2"},
        ]
        doc["draftLinks"].extend(orphans)
        doc["revisionId"] = compute_revision(doc)
        original = copy.deepcopy(doc)
        pres = copy.deepcopy(ed.presentation)
        repaired = Editor(doc, pres)
        self.assertEqual(repaired.cleaned_draft_link_ids, tuple(d["id"] for d in orphans))
        self.assertTrue(repaired.dirty)
        expected = copy.deepcopy(doc)
        expected["draftLinks"] = valid
        expected["revisionId"] = compute_revision(expected)
        self.assertEqual(repaired.model, expected)
        self.assertEqual(repaired.presentation, ed.presentation)
        self.assertEqual(doc, original, "la apertura no modifica el documento recibido al repararlo")
        self.assertEqual(repaired.undo_stack, [])
        self.assertEqual(repaired.redo_stack, [])
        self.assertNotEqual(repaired.revision, original["revisionId"])
        self.assertIn("D-ALTERNANCIA", {d.code for d in repaired.validate().diagnostics})

    def test_SDBR09_modelo_sin_huerfanos_no_necesita_reparacion(self):
        """REQ-EDT-01, REQ-EDT-02: abrir un borrador editable no lo elimina ni pide guardarlo."""
        ed, _, _, _ = barra_entre_transiciones()
        doc = copy.deepcopy(ed.model)
        loaded = Editor(doc, copy.deepcopy(ed.presentation))
        self.assertEqual(loaded.model, ed.model)
        self.assertEqual(loaded.cleaned_draft_link_ids, ())
        self.assertFalse(loaded.dirty)

    def test_SDBR10_reparacion_no_se_repite_al_validar_ni_deshacer(self):
        """REQ-EDT-05, REQ-EDT-09: validar no cambia el documento ni el historial de reparación."""
        ed = nuevo()
        doc = copy.deepcopy(ed.model)
        doc["draftLinks"] = [{"id": "l-huerfano", "fromRef": "antes", "toRef": "despues"}]
        loaded = Editor(doc)
        before = copy.deepcopy(loaded.model)
        sid = loaded.add_step("g", "A", True)
        loaded.validate()
        loaded.undo()
        loaded.validate()
        self.assertEqual(loaded.model, before)
        loaded.redo()
        self.assertEqual(loaded.get(sid)["label"], "A")
        self.assertEqual(loaded.cleaned_draft_link_ids, ("l-huerfano",))
        self.assertEqual(loaded.model["draftLinks"], [])

    def test_SDBR11_fixture_real_elimina_fantasma_sin_perder_el_modelo(self):
        """REQ-EDT-01, REQ-EDT-09, REQ-DAT-02: Salto-de-etapas se abre reparado desde la fixture."""
        originals = {p.name: p.read_bytes() for p in FIXTURE.iterdir()}
        self.assertEqual(len(originals), 3)
        opened = open_model(FIXTURE / "manifest.json")
        original = copy.deepcopy(opened.doc)
        self.assertEqual(len(original["draftLinks"]), 1)
        ed = Editor(opened.doc, opened.presentations[0])
        self.assertEqual(ed.cleaned_draft_link_ids, (original["draftLinks"][0]["id"],))
        self.assertEqual(ed.model["draftLinks"], [])
        expected = copy.deepcopy(original)
        expected["draftLinks"] = []
        expected["revisionId"] = compute_revision(expected)
        self.assertEqual(ed.model, expected)
        self.assertEqual(ed.presentation, opened.presentations[0])
        self.assertTrue(ed.dirty)
        self.assertTrue(ed.validate().can_simulate, ed.validate().diagnostics)
        self.assertEqual({p.name: p.read_bytes() for p in FIXTURE.iterdir()}, originals)

    def test_SDBR12_guardar_y_reabrir_conserva_reparacion_sin_nuevo_aviso(self):
        """REQ-EDT-01, REQ-DAT-02: guardar la reparación permite reabrir sin enlaces fantasma."""
        opened = open_model(FIXTURE / "manifest.json")
        ed = Editor(opened.doc, opened.presentations[0])
        project = new_project("reparado", "Salto de etapas reparado")
        add_document(project, ed.model)
        add_document(project, ed.presentation)
        with tempfile.TemporaryDirectory() as tmp:
            save_project(Path(tmp), project)
            reopened = open_model(Path(tmp))
            clean = Editor(reopened.doc, reopened.presentations[0])
        self.assertEqual(clean.model, ed.model)
        self.assertEqual(clean.presentation, ed.presentation)
        self.assertEqual(clean.cleaned_draft_link_ids, ())
        self.assertFalse(clean.dirty)
        self.assertTrue(clean.validate().can_simulate, clean.validate().diagnostics)

    def test_SDBR13_apertura_conserva_otras_referencias_incompletas(self):
        """REQ-EDT-02, REQ-EDT-09: la limpieza de borradores no oculta otros errores de referencia."""
        ed = nuevo()
        t, _ = ed.add_transition("g", "true", pre=["etapa-ausente"])
        doc = copy.deepcopy(ed.model)
        doc["draftLinks"] = [{"id": "l-huerfano", "fromRef": t, "toRef": "otra-transicion"}]
        repaired = Editor(doc)
        self.assertEqual(repaired.get(t)["preRefs"], ["etapa-ausente"])
        self.assertEqual(repaired.model["draftLinks"], [])
        self.assertIn("D-REF", {d.code for d in repaired.validate().diagnostics})


if __name__ == "__main__":
    unittest.main()
