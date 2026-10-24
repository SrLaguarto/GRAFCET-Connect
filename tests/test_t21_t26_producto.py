"""Casos T-21 a T-26 del documento 11: editor, datos, simulación, plataforma y robustez.

Los casos que exigen interfaz gráfica (T-21g, T-21h, T-26a, T-26b), instalación (T-24e)
o el equipo de referencia de U-10 (T-25d) no se ejecutan aquí; constan como pendientes
en la matriz de trazabilidad.
"""
import copy
import socket
import tempfile
import unittest
from pathlib import Path

from helpers import M, S, records, scenario, session
from test_t17_t20_jerarquias import macro_model

from grafcet.canonical import canonical_bytes, digest
from grafcet.declaration import coverage_declaration
from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Editor, duplicate_model, new_model_document
from grafcet.engine import Session
from grafcet.ids import IdGenerator
from grafcet.model import compute_revision, semantic_projection, validate_model
from grafcet.persistence import (FileSystem, Recovery, _element_ids, add_document, migrate_project, new_project,
                                 open_project, parse_document, save_project)
from grafcet.profile import APP_VERSION, FORMAT_VERSION, PROFILE_ID
from grafcet.scenario import load_scenario
from grafcet.timeutil import format_duration, parse_duration
from grafcet.trace import semantic_view, verify_trace


def codes(diags):
    return {d.code for d in diags}


def basic_editor(prefix="x"):
    ed = Editor(new_model_document("mod"), ids=IdGenerator(prefix))
    g = ed.add_partial("Principal")
    p = ed.add_variable("p", "input", {"kind": "bool"})
    a = ed.add_step(g, "A", True, at=(10, 20))
    b = ed.add_step(g, "B", at=(10, 120))
    t, _ = ed.add_transition(g, "p", pre=[a], post=[b], at=(10, 70))
    return ed, g, p, a, b, t


def all_strings(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from all_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from all_strings(v)
    elif isinstance(x, str):
        yield x


class Editor_(unittest.TestCase):
    def test_T21a_crear_guardar_reabrir_duplicar(self):
        ed, g, p, a, b, t = basic_editor()
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "Demo")
            add_document(pj, ed.model)
            add_document(pj, ed.presentation)
            save_project(Path(tmp), pj)
            back = open_project(Path(tmp))
            self.assertEqual(back.doc("model", "mod"), ed.model)
        dup = duplicate_model(ed.model, "mod2", IdGenerator("y"))
        orig_ids = set(_element_ids(ed.model))
        self.assertFalse(orig_ids & set(_element_ids(dup)))
        self.assertFalse(orig_ids & set(all_strings(dup)), "el duplicado no referencia identidades del original")
        self.assertTrue(validate_model(dup).can_simulate)

    def test_T21b_diagnosticos_separados_borrador_guardable(self):
        ed, g, p, a, b, t = basic_editor()
        diag = ed.connect(a, b)
        self.assertEqual(diag.code, "D-ALTERNANCIA")
        doc = copy.deepcopy(ed.model)
        doc["transitions"][0]["postRefs"].append("no-existe")
        doc["steps"].append(dict(doc["steps"][0]))  # identidad duplicada
        res = validate_model(doc)
        found = {d.code: d.element for d in res.diagnostics}
        self.assertTrue({"D-ALTERNANCIA", "D-REF", "D-ID"} <= set(found))
        self.assertTrue(all(found[c] for c in ("D-ALTERNANCIA", "D-REF", "D-ID")), "cada diagnóstico localiza su elemento")
        self.assertFalse(res.can_simulate)
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "borrador")
            add_document(pj, doc)
            save_project(Path(tmp), pj)
            self.assertEqual(open_project(Path(tmp)).models()[0], doc)

    def test_T21c_cruzar_mover_alinear_no_conecta(self):
        ed, g, p, a, b, t = basic_editor()
        t2, _ = ed.add_transition(g, "NOT p", pre=[b], post=[a], at=(60, 70))
        rel = copy.deepcopy(ed.model["transitions"])
        rev = ed.revision
        coords = copy.deepcopy(ed.presentation["elementLayouts"])
        ed.move(a, 200, 300)  # las rutas pasan a cruzarse: no cambia ninguna relación
        ed.move(b, 0, 0)
        ed.align([a, b, t], "x")
        ed.distribute([a, b, t], "y")
        self.assertEqual(ed.model["transitions"], rel)
        self.assertEqual(ed.revision, rev, "solo cambia la presentación")
        for _ in range(4):
            ed.undo()
        self.assertEqual(ed.presentation["elementLayouts"], coords)

    def test_T21d_renombrar_conserva_ids_y_traza(self):
        ed, g, p, a, b, t = basic_editor()
        t2, _ = ed.add_transition(g, "active(A) AND NOT p", pre=[b], post=[a])
        def run(model):
            res = validate_model(model)
            s = session(res.model, batches=[(1 * S, 0, {p: True}), (2 * S, 0, {p: False})])
            s.run()
            return semantic_view(s.trace.records), res.model.revision
        before, rev = run(copy.deepcopy(ed.model))
        touched = ed.rename(p, "marcha")
        ed.rename(a, "Inicio")
        self.assertEqual(len(touched), 2)
        texts = {e["text"] for e in ed.model["expressions"]}
        self.assertIn("marcha", texts)
        self.assertIn("active(Inicio) AND NOT marcha", texts)
        self.assertEqual(ed.get(p)["id"], p)
        after, rev2 = run(copy.deepcopy(ed.model))
        self.assertEqual(before, after, "traza equivalente")
        self.assertEqual(rev, rev2, "renombrar no cambia la revisión semántica (H-13)")
        snapshot = copy.deepcopy(ed.model)
        with self.assertRaises(DiagnosticError) as ctx:
            ed.rename(b, "Inicio")
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-NOMBRE-COLISION")
        self.assertEqual(ed.model, snapshot)

    def test_T21e_copiar_pegar_con_referencia_externa(self):
        ed, g, p, a, b, t = basic_editor()
        frag = ed.copy([a, t, b])
        self.assertEqual(ed.plan_paste(frag), {p: "variables"}, "se muestra la decisión antes de confirmar")
        mapping = ed.paste(frag, g, {p: "keep"})
        new_ids = set(mapping.values())
        self.assertFalse(new_ids & {a, b, t})
        new_t = next(x for x in ed.model["transitions"] if x["id"] == mapping[t])
        self.assertEqual((new_t["preRefs"], new_t["postRefs"]), ([mapping[a]], [mapping[b]]))
        self.assertIn(p, ed.get(new_t["conditionRef"])["bindings"].values(), "p se mantiene como vínculo explícito")
        ed2, g2, p2, a2, b2, t2 = basic_editor("z")
        ed2.paste(ed2.copy([a2, t2, b2]), g2, {p2: "pending"})
        res = ed2.validate()
        self.assertIn("D-REF", codes(res.diagnostics))
        self.assertFalse(res.can_simulate, "la alternativa pendiente bloquea el inicio")

    def test_T21f_borrar_encapsulante_y_deshacer_atomico(self):
        ed, g, p, a, b, t = basic_editor()
        r = ed.add_partial("Recinto")
        h = ed.add_step(g, "H", kind="enclosing")
        i = ed.add_step(r, "I")
        k = ed.add_step(r, "K")
        ed.add_transition(r, "p", pre=[i], post=[k])
        ed.connect(t, h)
        def fn(m, pr):
            m["hierarchy"]["enclosures"].append({"id": "encR", "ownerStepRef": h, "partialRef": r, "activationRefs": [k]})
        ed._txn("crear recinto", fn)
        full = copy.deepcopy((ed.model, ed.presentation))
        plan = ed.delete([h])
        self.assertTrue({h, "encR", r, i, k} <= set(plan["elements"]))
        self.assertNotIn(h, ed.model["transitions"][0]["postRefs"])
        deleted = copy.deepcopy((ed.model, ed.presentation))
        ed.undo()
        self.assertEqual((ed.model, ed.presentation), full, "restauración exacta en un paso")
        ed.redo()
        self.assertEqual((ed.model, ed.presentation), deleted)
        n_undo = len(ed.undo_stack)
        with self.assertRaises(DiagnosticError):
            ed.delete([a, "no-existe"])
        self.assertEqual((ed.model, ed.presentation), deleted, "una operación fallida no borra nada")
        self.assertEqual(len(ed.undo_stack), n_undo, "ni entra en el historial")


class Datos(unittest.TestCase):
    def test_T22a_ida_y_vuelta_conserva_significado_notas_y_vista(self):
        m = macro_model()
        m.expr("depósito preparado", "descriptive")
        pres = {"family": "presentation", "formatVersion": "0.1", "id": "m.vista", "modelId": "m",
                "views": [{"id": "v1", "label": "principal"}],
                "elementLayouts": [{"elementRef": "A", "viewRef": "v1", "x": "10.5", "y": "20"}],
                "notes": [{"id": "n1", "elementRef": "A", "text": "«Comentario» con ñ y 漢字"}]}
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "T-22a")
            add_document(pj, m.doc)
            add_document(pj, pres)
            save_project(Path(tmp), pj)
            back = open_project(Path(tmp))
        self.assertEqual(digest(semantic_projection(back.models()[0])), digest(semantic_projection(m.doc)))
        self.assertEqual(back.doc("presentation", "m.vista"), pres)

    def test_T22b_referencia_rota_propietario_contradictorio_clave_duplicada(self):
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p")
        doc = copy.deepcopy(m.doc)
        doc["steps"][1]["label"] = "Etiqueta"
        doc["transitions"][0]["postRefs"] = ["Etiqueta"]  # coincide con una etiqueta, no con un ID
        self.assertIn("D-REF", codes(validate_model(doc).diagnostics))
        doc2 = copy.deepcopy(m.doc)
        doc2["partials"].append({"id": "g2", "label": "g2", "stepRefs": ["A"], "transitionRefs": []})
        self.assertIn("D-FORMATO", codes(validate_model(doc2).diagnostics))
        raw = b'{"family":"model","formatVersion":"0.1","id":"m","id":"m2"}'
        self.assertEqual(parse_document(raw).diagnostics[0].code, "D-FORMATO")

    def test_T22c_versiones_y_desconocidos(self):
        major = parse_document(b'{"family":"model","formatVersion":"1.0","id":"m"}')
        self.assertEqual((major.executable, major.writable), (False, False))
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p")
        m.doc["script"] = "import os"
        m.doc["extensions"] = {"org.ejemplo.color": {"affectsSemantics": False, "data": {"A": "#ff0000"}}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pj = new_project("proy", "T-22c")
            add_document(pj, m.doc)
            save_project(root, pj)
            original = (root / "model-6d.json").read_bytes()
            back = open_project(root)
            self.assertFalse(back.executable)
            self.assertFalse(back.writable)
            with self.assertRaises(DiagnosticError):
                save_project(root, back)
            self.assertEqual((root / "model-6d.json").read_bytes(), original, "no se sobrescribe")
        del m.doc["script"]
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "T-22c")
            add_document(pj, m.doc)
            save_project(Path(tmp), pj)
            back = open_project(Path(tmp))
            self.assertTrue(back.executable and back.writable)
            self.assertEqual(back.models()[0]["extensions"], m.doc["extensions"], "extensión descriptiva preservada opaca")

    def test_T22d_guardado_interrumpido(self):
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p")
        v1 = copy.deepcopy(m.doc)
        v2 = copy.deepcopy(m.doc)
        v2["steps"][1]["label"] = "B2"
        pres = {"family": "presentation", "formatVersion": "0.1", "id": "m.vista", "modelId": "m", "views": [],
                "elementLayouts": [], "notes": []}
        outcomes = set()
        for fail_at in range(0, 12):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                pj = new_project("proy", "T-22d")
                add_document(pj, copy.deepcopy(v1))
                add_document(pj, copy.deepcopy(pres))
                save_project(root, pj)
                pj2 = new_project("proy", "T-22d")
                add_document(pj2, copy.deepcopy(v2))
                pres2 = dict(pres, notes=[{"id": "n", "text": "nueva"}])
                add_document(pj2, pres2)
                try:
                    save_project(root, pj2, FileSystem(fail_after_writes=fail_at))
                except OSError:
                    pass
                back = open_project(root)
                got = (back.models()[0], back.doc("presentation", "m.vista"))
                self.assertIn(got, [(v1, pres), (v2, pres2)], f"mezcla de revisiones con fallo en escritura {fail_at}")
                outcomes.add("v1" if got[0] == v1 else "v2")
        self.assertEqual(outcomes, {"v1", "v2"}, "se ejercitan fallos antes y después de confirmar")

    def test_T22d_recuperacion_separada(self):
        m = M().var("p").step("A", True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pj = new_project("proy", "rec")
            add_document(pj, m.doc)
            save_project(root, pj)
            main = (root / "model-6d.json").read_bytes()
            rec = Recovery(root)
            draft = new_project("proy", "rec")
            changed = copy.deepcopy(m.doc)
            changed["steps"][0]["label"] = "cambiada"
            add_document(draft, changed)
            self.assertTrue(rec.maybe_autosave(100.0, True, draft, compute_revision(changed)))
            self.assertFalse(rec.maybe_autosave(110.0, True, draft, "r"), "periodo de 30 s")
            self.assertTrue(rec.maybe_autosave(131.0, True, draft, "r"))
            self.assertFalse(rec.maybe_autosave(200.0, False, draft, "r"), "sin cambios no guarda")
            self.assertEqual(rec.available()["savedAtS"], "131")
            self.assertEqual((root / "model-6d.json").read_bytes(), main, "sin sobrescritura silenciosa")
            self.assertEqual(rec.load().models()[0]["steps"][0]["label"], "cambiada")

    def test_T22e_migracion_y_ejes_de_version(self):
        m = M().var("p").step("A", True)
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "src", Path(tmp) / "dst"
            pj = new_project("proy", "mig")
            add_document(pj, m.doc)
            save_project(src, pj)
            before = {f.name: f.read_bytes() for f in src.iterdir()}

            def rename_title(doc):
                if doc["family"] == "model":
                    doc = dict(doc, extensions={"org.ejemplo.nota": {"affectsSemantics": False, "data": "migrado"}})
                    return doc, ["añadida extensión descriptiva"]
                return doc, []
            report = migrate_project(src, dst, [rename_title])
            self.assertTrue(report["changes"])
            self.assertTrue((dst / "informe-migracion.json").exists())
            self.assertEqual({f.name: f.read_bytes() for f in src.iterdir()}, before, "el original se conserva")
            self.assertEqual(open_project(dst).manifest["normativeBase"], pj.manifest["normativeBase"])
        man = new_project("p", "t").manifest
        self.assertEqual((man["formatVersion"], man["appVersion"], man["capabilityProfile"]["id"], man["normativeBase"]["edition"]),
                         (FORMAT_VERSION, APP_VERSION, PROFILE_ID, "3.0"), "cuatro ejes de versión separados")


class Simulacion(unittest.TestCase):
    def _delay_model(self):
        return M().var("q").step("A", True).step("B").trans("t", ["A"], ["B"], "delay(5 s, active(A), 0 s)").compile()

    def test_T22f_restaurar_exige_compatibilidad_exacta(self):
        cm = self._delay_model()
        s = session(cm, batches=[(2 * S, 0, {"q": True})])
        s.step_external()
        snap = s.snapshot("snap")
        other = M().var("q").step("A", True).step("B").step("C").trans("t", ["A"], ["B"], "delay(5 s, active(A), 0 s)").compile()
        with self.assertRaises(DiagnosticError) as ctx:
            Session.restore(other, scenario(other), snap)
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-INSTANTANEA-INCOMPATIBLE")
        bad = copy.deepcopy(snap)
        bad["semanticProfile"]["version"] = "9.9"
        with self.assertRaises(DiagnosticError):
            Session.restore(cm, s.scenario, bad)
        self.assertEqual(s.status, "pausada-estable", "la sesión existente no se modifica")
        r = Session.restore(cm, s.scenario, snap)
        self.assertEqual({k: v.to_dict() for k, v in r.z.temporal.items()}, {k: v.to_dict() for k, v in s.z.temporal.items()})
        self.assertEqual(r.z.values, s.z.values)

    def test_T22g_traza_truncada_o_alterada(self):
        cm = self._delay_model()
        s = session(cm)
        s.run()
        s.close_trace()
        data = s.trace.to_jsonl()
        self.assertTrue(verify_trace(data).complete)
        truncated = b"\n".join(data.split(b"\n")[:-2]) + b"\n"
        chk = verify_trace(truncated)
        self.assertFalse(chk.complete)
        self.assertEqual(chk.diagnostics[0].code, "D-INTEGRIDAD")
        self.assertEqual(len(chk.records), len(s.trace.records), "prefijo verificado disponible")
        altered = data.replace(b'"situation":["B"]', b'"situation":["A"]', 1)
        self.assertFalse(verify_trace(altered).complete)
        partial_line = data[: len(data) - 40]
        self.assertFalse(verify_trace(partial_line).complete)

    def _t04a(self):
        return M().var("p").step("A", True).step("B").step("C", True).step("D") \
            .trans("t", ["A"], ["B"], "p").trans("u", ["C"], ["D"], "p").compile()

    def test_T23a_pausa_antes_del_conjunto(self):
        s = session(self._t04a(), batches=[(1 * S, 0, {"p": True})])
        s.breakpoints["t"] = "antes"
        s.run()
        self.assertEqual(s.status, "pausada-recorrido")
        obs = s.observe()
        self.assertEqual(obs["situation"], ["A", "C"], "antes del conjunto ninguna integrante está franqueada")
        s.step_evolution()
        self.assertEqual(records(s, "evolucion")[0]["cleared"] if records(s, "evolucion") else s._work["last"]["cleared"],
                         ["t", "u"])
        s.run_to_stable()
        self.assertEqual(s.z.situation, {"B", "D"})
        self.assertEqual([e["cleared"] for e in records(s, "evolucion")], [["t", "u"]])

    def test_T23b_continuo_microavances_y_puntos_de_parada(self):
        m = M().var("p").var("z", "internal").var("y", "output").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "true").stored("B", "z", "activation", "true").cont("C", "y")
        cm = m.compile()
        batches = [(1 * S, 0, {"p": True})]
        a = session(cm, batches=batches)
        a.run()
        b = session(cm, batches=batches)
        while b.status in ("pausada-estable", "pausada-recorrido"):
            if b.status == "pausada-estable" and b.next_stimulus() is None:
                break
            b.step_evolution()
        c = session(cm, batches=batches)
        c.breakpoints.update(t="antes", u="despues")
        while c.status != "finalizada":
            c.run()
        for other in (b, c):
            self.assertEqual(semantic_view(a.trace.records), semantic_view(other.trace.records))
            self.assertTrue(a.z.equivalent(other.z))

    def test_T23c_instantanea_continuar_y_restaurar(self):
        cm = self._delay_model()
        s = session(cm, batches=[(2 * S, 0, {"q": True})])
        s.step_external()
        snap = s.snapshot("s2")
        r = Session.restore(cm, s.scenario, snap)
        for sess in (s, r):
            sess.manual_input({"q": False})
            sess.run()
        tail = lambda x: [e for e in semantic_view(x.trace.records) if e["kind"] in ("evolucion", "contexto")][-2:]
        self.assertEqual(tail(s), tail(r))
        self.assertEqual(records(s, "evolucion")[-1]["timeUs"], str(5 * S))
        self.assertEqual(records(r, "evolucion")[-1]["timeUs"], str(5 * S))
        self.assertTrue(records(s, "entrada-manual"), "entrada manual registrada")

    def test_T23d_edicion_durante_ejecucion_crea_revision(self):
        ed, g, p, a, b, t = basic_editor()
        cm = validate_model(copy.deepcopy(ed.model)).model
        s = session(cm, batches=[(1 * S, 0, {p: True})])
        r1 = ed.revision
        ed.set_condition(t, "NOT p")
        r2 = ed.revision
        self.assertNotEqual(r1, r2)
        s.run()
        self.assertEqual(s.z.situation, {b}, "la ejecución anterior conserva su revisión inmutable")
        self.assertEqual(s.trace.header["modelRevision"], r1)
        ed.move(a, 99, 99)
        self.assertEqual(ed.revision, r2, "mover mantiene la revisión")

    def test_T23e_intervencion_de_depuracion(self):
        m = M().var("p").var("n", "internal", "int").step("A", True).step("B").trans("t", ["A"], ["B"], "p")
        m.stored("B", "n", "activation", "2")
        cm = m.compile()
        s = session(cm, batches=[(1 * S, 0, {"p": True})])
        s.step_external()
        self.assertEqual((s.status, s.z.values["n"]), ("pausada-estable", 2))
        br = s.debug_set("n", 9, "prueba de depuración")
        rec = records(br, "intervencion")[0]
        self.assertEqual((rec["before"], rec["after"]), ("2", "9"))
        self.assertNotEqual(br.run_id, s.run_id)
        self.assertTrue(br.trace.header["parentRun"].startswith(s.run_id))
        self.assertEqual(br.z.origin, "intervenido")
        self.assertEqual(records(br, "evolucion"), [], "sin transición ficticia")
        self.assertEqual(s.z.values["n"], 2)

    def test_T23f_instantanea_dentro_de_un_recorrido(self):
        m = M().var("p").var("z", "internal").step("A", True).step("B").step("C")
        m.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "true").stored("B", "z", "activation", "true")
        s = session(m.compile(), batches=[(1 * S, 0, {"p": True})])
        s.step_evolution()
        self.assertEqual(s.status, "pausada-recorrido")
        with self.assertRaises(DiagnosticError) as ctx:
            s.snapshot("mitad")
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-INSTANTANEA-FASE")
        s.run_to_stable()
        self.assertTrue(s.z.values["z"])
        assigns = [a for e in records(s, "evolucion") for a in e["assignments"]]
        self.assertEqual(len(assigns), 1, "la acción no se repite")


class Plataforma(unittest.TestCase):
    def test_T24a_trazas_canonicas_deterministas(self):
        """Parcial: solo Windows en esta iteración; los digests se comparan en otros sistemas (U-10)."""
        def run():
            m = M().var("p").var("y", "output").step("A", True).cont("A", "y", "delay(1.5 s, p, 2 s)")
            s = session(m.compile(), batches=[(2 * S, 0, {"p": True}), (8 * S, 0, {"p": False})])
            s.run()
            return digest(semantic_view(s.trace.records))
        self.assertEqual(run(), run())

    def test_T24b_configuracion_regional(self):
        self.assertEqual(parse_duration("1,25 s", "es-ES"), 1_250_000)
        self.assertEqual(parse_duration("1.25 s", "en-US"), 1_250_000)
        with self.assertRaises(DiagnosticError):
            parse_duration("1,25 s", "en-US")
        self.assertEqual(format_duration(1_250_000, "s", "es-ES"), "1,25 s")
        cm = M().var("p").step("A", True).compile()
        sc = scenario(cm, batches=[(parse_duration("1,25 s", "es-ES"), 0, {"p": True})])
        self.assertIn(b'"timeUs":"1250000"', canonical_bytes(sc.doc))
        self.assertNotIn(b"1,25", canonical_bytes(sc.doc))

    def test_T24c_rutas_unicode_e_ids_que_difieren_en_mayusculas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Ensayo ñ"
            pj = new_project("proy", "Ensayo ñ")
            for mid, label in (("A", "válvula"), ("a", "VÁLVULA")):
                m = M(mid).step("S1", True)
                m.doc["steps"][0]["label"] = label
                add_document(pj, m.doc)
            save_project(root, pj)
            names = sorted(f.name for f in root.iterdir())
            self.assertIn("model-41.json", names)
            self.assertIn("model-61.json", names)
            back = open_project(root)
            self.assertEqual(back.doc("model", "A")["steps"][0]["label"], "válvula")
            self.assertEqual(back.doc("model", "a")["steps"][0]["label"], "VÁLVULA")

    def test_T24d_sin_conexion(self):
        def deny(*a, **k):
            raise AssertionError("acceso de red no permitido")
        saved = (socket.socket.connect, socket.create_connection, socket.getaddrinfo)
        socket.socket.connect, socket.create_connection, socket.getaddrinfo = deny, deny, deny
        try:
            ed, g, p, a, b, t = basic_editor()
            with tempfile.TemporaryDirectory() as tmp:
                pj = new_project("proy", "offline")
                add_document(pj, ed.model)
                save_project(Path(tmp), pj)
                cm = validate_model(open_project(Path(tmp)).models()[0]).model
            s = session(cm, batches=[(1 * S, 0, {p: True})])
            s.run()
            s.close_trace()
            verify_trace(s.trace.to_jsonl())
            coverage_declaration()
        finally:
            socket.socket.connect, socket.create_connection, socket.getaddrinfo = saved
        self.assertEqual(s.z.situation, {b})


class Robustez(unittest.TestCase):
    def test_T25a_limites(self):
        def many(n):
            m = M()
            for i in range(n):
                m.step(f"s{i}", i == 0)
            return m.validate()
        self.assertNotIn("D-LIM-DATOS", codes(many(5000).diagnostics))
        self.assertIn("D-LIM-DATOS", codes(many(5001).diagnostics))
        def nested(depth):
            m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "NOT " * depth + "p")
            return m.doc, m.validate()
        doc, ok = nested(63)
        self.assertNotIn("D-LIM-DATOS", codes(ok.diagnostics))
        self.assertTrue(ok.can_simulate)
        self.assertEqual(parse_document(canonical_bytes(doc)).doc, doc, "el modelo límite se guarda y se relee")
        self.assertIn("D-LIM-DATOS", codes(nested(65)[1].diagnostics))
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "grande.json"
            f.write_bytes(b"{}" * 100)
            with self.assertRaises(DiagnosticError) as ctx:
                FileSystem().read(f, limit=50)
            self.assertEqual(ctx.exception.diagnostics[0].code, "D-LIM-DATOS")

    def test_T25b_script_operador_desconocido_y_ruta_externa(self):
        m = M().var("p").step("A", True).step("B").trans("t", ["A"], ["B"], "p")
        doc = copy.deepcopy(m.doc)
        doc["expressions"][0]["meaning"] = {"operator": "exec", "operands": [{"operator": "lit", "literal": {"type": "bool", "value": True}}]}
        doc["transitions"][0]["script"] = "__import__('os').remove('x')"
        res = validate_model(doc)
        self.assertIn("D-FORMATO", codes(res.diagnostics))
        self.assertFalse(res.can_simulate)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pj = new_project("proy", "ruta")
            add_document(pj, m.doc)
            save_project(root, pj)
            good = (root / "manifest.json").read_bytes()
            man = parse_document(good).doc
            man["modelRefs"][0]["path"] = "../fuera.json"
            (root / "manifest.json").write_bytes(canonical_bytes(man))
            with self.assertRaises(DiagnosticError) as ctx:
                open_project(root)
            self.assertEqual(ctx.exception.diagnostics[0].code, "D-RUTA")
            self.assertTrue((root / "model-6d.json").exists(), "el documento anterior queda intacto")

    def test_T25c_profundidad_y_documento_corrupto(self):
        deep = b'{"family":"model","formatVersion":"0.1","id":"m","x":' + b"[" * 200 + b"]" * 200 + b"}"
        self.assertEqual(parse_document(deep).diagnostics[0].code, "D-LIM-DATOS")
        self.assertEqual(parse_document(b'{"family":"model",').diagnostics[0].code, "D-FORMATO")
        self.assertEqual(parse_document(b'{"family":"model","formatVersion":"0.1","id":"m","v":1.5}').diagnostics[0].code,
                         "D-FORMATO")
        self.assertEqual(parse_document(b'{"family":"model","formatVersion":"0.1","id":"m","v":NaN}').diagnostics[0].code,
                         "D-FORMATO")


if __name__ == "__main__":
    unittest.main()
