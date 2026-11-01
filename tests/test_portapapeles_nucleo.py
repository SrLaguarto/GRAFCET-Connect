"""Regresiones del fragmento y del pegado jerárquico sin interfaz."""
import copy
import unittest
from grafcet.editor import Editor, new_grafcet_document
from grafcet.ids import IdGenerator
from grafcet.diagnostics import DiagnosticError


def nuevo(prefix="a"):
    return Editor(new_grafcet_document("m"), ids=IdGenerator(prefix))


def variable(ed, name="p"):
    return ed.add_variable(name, "output", {"kind": "bool"})


class PortapapelesNucleo(unittest.TestCase):
    def test_SCLI01_jerarquia_completa_y_forzados_remapeados(self):
        """REQ-EDT-04, REQ-JER-02, REQ-JER-04, REQ-JER-05: copia contenido propio y conserva o remapea destinos."""
        ed = nuevo()
        h = ed.add_step("g", "1", True, kind="enclosing", at=(20, 40))
        r = ed.new_enclosure(h, "G1")
        a = ed.add_step(r.partial, "2", True, at=(400, 40))
        ed.set_activation(a)
        macro = ed.add_macro(r.partial, "M1", at=(400, 200))
        f = ed.add_force(h, r.partial, "explicit", [a])
        external = ed.add_partial("G2")
        b = ed.add_step(external, "3", True)
        f2 = ed.add_force(a, external, "explicit", [b])
        frag = ed.copy([h])
        mapping = ed.paste(frag, "g")
        self.assertEqual(ed.get(mapping[f])["targetPartialRef"], mapping[r.partial])
        self.assertEqual(ed.get(mapping[f])["targetSteps"], [mapping[a]])
        self.assertEqual(ed.get(mapping[f2])["targetPartialRef"], external)
        self.assertEqual(ed.get(mapping[f2])["targetSteps"], [b])
        self.assertEqual(ed.get(mapping[macro.macro])["expansionRef"], mapping[macro.expansion])
        self.assertEqual(ed.get(mapping[r.partial])["ownerRef"], "g")
        self.assertEqual(ed.get(mapping[macro.partial])["ownerRef"], mapping[r.partial])
        self.assertEqual(ed.validate().diagnostics, [])

    def test_SCLI02_frontera_de_enlaces_se_corta(self):
        """REQ-EDT-04, REQ-MOD-03: solo se conservan los enlaces entre elementos copiados."""
        ed = nuevo()
        a = ed.add_step("g", "1", True)
        b = ed.add_step("g", "2")
        t, _ = ed.add_transition("g", "true", pre=[a], post=[b], label="t1")
        ed.connect(a, b)
        mp = ed.paste(ed.copy([a, t]), "g")
        self.assertEqual(ed.get(mp[t])["preRefs"], [mp[a]])
        self.assertEqual(ed.get(mp[t])["postRefs"], [])
        self.assertEqual(ed.model["draftLinks"], ed.model["draftLinks"][:1])
        self.assertEqual(len(ed.model["draftLinks"]), 1)

    def test_SCLI03_nombres_unicos_sin_duplicar_variables(self):
        """REQ-EDT-04, REQ-MOD-01: 2 con 1–5 ocupados pasa a 6; G1 y t1 usan el siguiente libre."""
        ed = nuevo()
        steps = [ed.add_step("g", str(n), n == 1) for n in range(1, 6)]
        v = variable(ed)
        t, _ = ed.add_transition("g", "p", pre=[steps[1]], post=[steps[2]], label="t1")
        g = ed.add_partial("G1")
        frag = ed.copy([steps[1], t, g])
        mp = ed.paste(frag, "g")
        self.assertEqual(ed.get(mp[steps[1]])["label"], "6")
        self.assertEqual(ed.get(mp[t])["label"], "t2")
        self.assertEqual(ed.get(mp[g])["label"], "G2")
        self.assertEqual([x["id"] for x in ed.model["variables"]], [v])
        mp2 = ed.paste(frag, "g")
        self.assertEqual(ed.get(mp2[steps[1]])["label"], "7")
        self.assertEqual(len(set(mp.values()) | set(mp2.values())), len(mp) + len(mp2))

    def test_SCLI04_pegar_se_deshace_y_rehace_en_una_operacion(self):
        """REQ-EDT-04, REQ-EDT-05: la copia no cambia el historial y pegar restaura ambos documentos."""
        ed = nuevo()
        macro = ed.add_macro("g", "M1", at=(100, 100))
        before = copy.deepcopy((ed.model, ed.presentation))
        n = len(ed.undo_stack)
        frag = ed.copy([macro.macro])
        self.assertEqual(len(ed.undo_stack), n)
        ed.paste(frag, "g", at=(600, 400))
        after = copy.deepcopy((ed.model, ed.presentation))
        self.assertEqual(len(ed.undo_stack), n + 1)
        ed.undo()
        self.assertEqual((ed.model, ed.presentation), before)
        ed.redo()
        self.assertEqual((ed.model, ed.presentation), after)

    def test_SCLI05_otro_proyecto_enlaza_variables_por_nombre_y_rechaza_faltantes(self):
        """REQ-EDT-04, REQ-DAT-01: no usa IDs del proyecto origen ni pega parcialmente si faltan variables."""
        src, dst = nuevo("a"), nuevo("b")
        p, q = variable(src, "p"), variable(src, "q")
        a = src.add_step("g", "1", True)
        t, _ = src.add_transition("g", "p AND q", pre=[a])
        frag = src.copy([a, t])
        before = copy.deepcopy((dst.model, dst.presentation, dst.undo_stack))
        with self.assertRaises(DiagnosticError) as ctx:
            dst.paste(frag, "g")
        self.assertIn("p", str(ctx.exception)); self.assertIn("q", str(ctx.exception))
        self.assertEqual((dst.model, dst.presentation, dst.undo_stack), before)
        p2, q2 = variable(dst, "p"), variable(dst, "q")
        mp = dst.paste(frag, "g")
        expr = dst.get(dst.get(mp[t])["conditionRef"])
        self.assertEqual(set(expr["bindings"].values()), {p2, q2})
        self.assertNotEqual({p, q}, {p2, q2})
        self.assertEqual(dst.validate().diagnostics, [])

    def test_SCLI06_accion_y_orden_copiadas_solas_quedan_sueltas(self):
        """REQ-EDT-04, REQ-ACT-01, REQ-JER-02: copiar solo una caja conserva configuración y rompe su enlace de etapa."""
        ed = nuevo(); v = variable(ed)
        s = ed.add_step("g", "1", True)
        aid = ed.add_continuous_action(s, v)
        g = ed.add_partial("G1"); ed.add_step(g, "2", True)
        fid = ed.add_force(s, g, "empty")
        mp = ed.paste(ed.copy([aid, fid]), "g", at=(600, 400))
        drafts = {d["id"]: d for d in ed.draft_actions()}
        self.assertEqual(drafts[mp[aid]]["variable"], v)
        self.assertEqual(drafts[mp[aid]]["tipo"], "continua")
        self.assertEqual(drafts[mp[fid]]["destino"], g)
        self.assertTrue(all(not d.get("etapa") for d in drafts.values()))
        self.assertEqual(ed.get(s)["actionRefs"], [aid])

    def test_SCLI07_barras_rutas_y_notas_conservan_geometria_relativa(self):
        """REQ-EDT-03, REQ-EDT-04: barras, notas y rutas internas viajan con sus referencias y coordenadas."""
        ed = nuevo(); a = ed.add_step("g", "1", True, at=(100, 100))
        t, _ = ed.add_transition("g", "false", label="t1", at=(100, 200))
        bar = ed.add_bar("Y", (100, 150))
        ed.bar_link(bar, "arriba", a); ed.bar_link(bar, "abajo", t)
        ed.set_comment(a, "comentario")
        lid = f"{t}|{a}|pre"
        ed.set_link_style(lid, {"route": {"laneX": "200", "middleY": "160"}})
        mp = ed.paste(ed.copy([a, t, bar]), "g", at=(500, 500))
        newbar = next(b for b in ed.bars() if b["id"] == mp[bar])
        self.assertEqual(newbar["arriba"], [mp[a]])
        self.assertEqual(newbar["abajo"], [mp[t]])
        self.assertEqual((newbar["x"], newbar["y"]), ("500", "550"))
        self.assertEqual(ed.comments()[mp[a]], "comentario")
        self.assertEqual(len({n["id"] for n in ed.presentation["notes"]}), 2)
        self.assertEqual(ed.link_styles()[f"{mp[t]}|{mp[a]}|pre"]["route"]["laneX"], "600")

    def test_SCLI08_texto_y_significado_apuntan_a_la_etapa_copiada_renombrada(self):
        """REQ-EDT-04, REQ-DAT-08: renombrar la copia actualiza texto, bindings y significado de sus receptividades."""
        ed = nuevo(); a = ed.add_step("g", "1", True)
        t, _ = ed.add_transition("g", "active(`1`)", pre=[a])
        mp = ed.paste(ed.copy([a, t]), "g")
        expr = ed.get(ed.get(mp[t])["conditionRef"])
        self.assertIn(mp[a], expr["bindings"].values())
        self.assertIn(ed.get(mp[a])["label"], expr["text"])
        self.assertNotIn("D-EXP-DIVERGENTE", {d.code for d in ed.validate().diagnostics})

    def test_SCLI09_marco_copiado_sin_su_dueno_es_parcial_independiente(self):
        """REQ-EDT-04, REQ-JER-05: copiar el marco de un recinto no duplica ni referencia la encapsulante exterior."""
        ed = nuevo(); h = ed.add_step("g", "1", True, kind="enclosing")
        r = ed.new_enclosure(h, "G1"); a = ed.add_step(r.partial, "2", True)
        mp = ed.paste(ed.copy([r.partial]), "g")
        self.assertNotIn("ownerRef", ed.get(mp[r.partial]))
        self.assertEqual(ed.get(mp[a])["partialRef"], mp[r.partial])
        self.assertEqual(len(ed.model["hierarchy"]["enclosures"]), 1)
        self.assertEqual(ed.validate().diagnostics, [])

    def test_SCLI10_borradores_agrupados_remapean_grupo_y_variables(self):
        """REQ-EDT-04, REQ-ACT-01: copiar un grupo suelto mantiene orden y expresión sin enlazarlo al original."""
        ed = nuevo(); v = variable(ed)
        d1 = ed.add_draft_action((100, 200), {"tipo": "continua", "variable": v})
        d2 = ed.add_draft_action((100, 200), {"tipo": "activacion", "variable": v, "valor": "p"})
        ed.update_draft_actions({d1: {"grupo": d1, "orden": 0}, d2: {"grupo": d1, "orden": 1}})
        mp = ed.paste(ed.copy([d1, d2]), "g", at=(500, 400))
        copies = [d for d in ed.draft_actions() if d["id"] in mp.values()]
        self.assertEqual({d["grupo"] for d in copies}, {mp[d1]})
        self.assertEqual([d["orden"] for d in copies], [0, 1])
        self.assertEqual({(d["x"], d["y"]) for d in copies}, {("500", "400")})
        self.assertEqual(len(ed.model["variables"]), 1)

    def test_SCLI11_pegar_forzado_no_crea_ciclo_silencioso(self):
        """REQ-EDT-04, REQ-JER-03: un pegado que haría que una orden fuerce su propio parcial se rechaza atómicamente."""
        ed = nuevo(); a = ed.add_step("g", "1", True)
        g = ed.add_partial("G1"); ed.add_step(g, "2", True)
        ed.add_force(a, g, "empty")
        before = copy.deepcopy((ed.model, ed.presentation, ed.undo_stack))
        with self.assertRaises(DiagnosticError):
            ed.paste(ed.copy([a]), g)
        self.assertEqual((ed.model, ed.presentation, ed.undo_stack), before)

    def test_SCLI12_decisiones_explicitas_conservan_referencia_pendiente(self):
        """REQ-EDT-04, REQ-EDT-09: se mantiene la API de decisión externa pendiente que diagnostica D-REF."""
        ed = nuevo(); v = variable(ed); a = ed.add_step("g", "1", True)
        t, _ = ed.add_transition("g", "p", pre=[a])
        ed.paste(ed.copy([a, t]), "g", {v: "pending"})
        self.assertIn("D-REF", {d.code for d in ed.validate().diagnostics})

    def test_SCLI13_marco_copia_barras_de_su_contenido(self):
        """REQ-EDT-04, REQ-MOD-03: copiar un parcial incluye la barra interior aunque no estuviera seleccionada aparte."""
        ed = nuevo(); g = ed.add_partial("G1")
        a = ed.add_step(g, "1", True); t, _ = ed.add_transition(g, "false", pre=[a])
        bar = ed.add_bar("Y", (100, 200))
        ed.bar_link(bar, "arriba", a); ed.bar_link(bar, "abajo", t)
        mp = ed.paste(ed.copy([g]), "g")
        self.assertIn(bar, mp)
        new = next(x for x in ed.bars() if x["id"] == mp[bar])
        self.assertEqual((new["arriba"], new["abajo"]), ([mp[a]], [mp[t]]))

    def test_SCLI14_encapsulante_aun_sin_recintos_conserva_su_tipo(self):
        """REQ-EDT-04, REQ-JER-05: una encapsulante todavía sin recintos no se transforma en ordinaria al copiar."""
        ed = nuevo(); h = ed.add_step("g", "1", True, kind="enclosing")
        mp = ed.paste(ed.copy([h]), "g")
        self.assertEqual(ed.get(mp[h])["kind"], "enclosing")
