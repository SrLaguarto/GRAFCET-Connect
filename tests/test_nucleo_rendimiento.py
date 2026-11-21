"""SNUC01..SNUC10: los cambios de rendimiento del núcleo (V2-E3, paso 9) no cambian ningún resultado."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

from grafcet import model as modelo  # noqa: E402
from grafcet.editor import Editor, new_grafcet_document  # noqa: E402
from grafcet.ids import IdGenerator  # noqa: E402
from grafcet.model import compute_revision, validate_model  # noqa: E402
from grafcet.view import Vista, layout_from_presentation  # noqa: E402

GOLDEN = RAIZ / "tests" / "fixtures" / "equivalencia_nucleo.json"


def editor():
    ed = Editor(new_grafcet_document("rend"), ids=IdGenerator("r-"))
    a = ed.add_step("g", "0", True, at=(240, 100))
    b = ed.add_step("g", "1", at=(240, 440))
    ed.add_variable("Marcha", "input", {"kind": "bool"})
    ed.add_transition("g", "false", [a], [b], at=(240, 270))
    return ed


def vista(ed):
    return Vista(ed.model["id"], "t", "", lambda: (ed.model, layout_from_presentation(ed.presentation)), {})


class EquivalenciaConElNucleoAnterior(unittest.TestCase):
    def test_SNUC01_los_resumenes_coinciden_con_los_del_nucleo_anterior(self):
        """REQ-CR-04: sobre los ejemplos de aula, los fixtures, GEMMA, el proyecto de 100 etapas y Linea larga, la revisión, los
        diagnósticos (en su orden), los enlaces, la estructura de la vista, la evolución de 12 pasos de simulación, las ediciones
        con deshacer y rehacer, y los enlaces de disposiciones al azar son los que daba el núcleo antes de los cambios de rendimiento
        (`tests/fixtures/equivalencia_nucleo.json`, generado por `tools/equivalencia_nucleo.py` con el árbol anterior)."""
        try:
            import equivalencia_nucleo as E
        except ImportError as exc:  # sin PySide6 no se pueden abrir los .grafnet
            self.skipTest(str(exc))
        esperado = json.loads(GOLDEN.read_text(encoding="utf-8"))
        obtenido = {}
        for nombre, doc, pres in E.proyectos(None):
            ed = E.editor_de(doc, pres)
            obtenido[nombre] = {"inicial": E.resumen_editor(ed, 12), "ediciones": [[n, x] for n, x in E.ediciones(ed)],
                                "disposiciones": E.disposiciones_al_azar(E.editor_de(doc, pres), 9,
                                                                         8 if len(doc["steps"]) > 90 else 25)}
        obtenido = json.loads(json.dumps(obtenido, sort_keys=True, default=repr))
        self.assertEqual(sorted(obtenido), sorted(esperado))
        for nombre in esperado:
            with self.subTest(proyecto=nombre):
                self.assertEqual(obtenido[nombre], esperado[nombre])


class HuellaUnaVezPorCambio(unittest.TestCase):
    def test_SNUC02_un_documento_del_editor_no_recalcula_su_huella_al_validarse(self):
        """REQ-DAT-02: la revisión del modelo compilado es la de siempre, pero sin volver a calcular la huella de un documento que el
        editor ya selló."""
        ed = editor()
        ed.add_step("g", "2", at=(240, 600))  # cambia el modelo: se calcula (y sella) su revisión
        with mock.patch.object(modelo, "compute_revision", wraps=compute_revision) as huella:
            r = validate_model(ed.model)
            self.assertEqual(huella.call_count, 0)
        self.assertEqual(r.model.revision, compute_revision(ed.model))
        self.assertEqual(r.model.revision, ed.model["revisionId"])

    def test_SNUC03_un_documento_sin_sellar_sigue_calculando_su_huella(self):
        """REQ-DAT-02: una copia del documento (nadie promete que no se toque) calcula su revisión como siempre."""
        ed = editor()
        ed.add_step("g", "2", at=(240, 600))
        copia = copy.deepcopy(ed.model)
        with mock.patch.object(modelo, "compute_revision", wraps=compute_revision) as huella:
            r = validate_model(copia)
        self.assertEqual(huella.call_count, 1)
        self.assertEqual(r.model.revision, compute_revision(copia))

    def test_SNUC04_la_huella_recordada_vale_tras_deshacer_y_rehacer(self):
        """REQ-DAT-02: tras deshacer y rehacer, la revisión validada es la del documento que toca."""
        ed = editor()
        ed.add_step("g", "2", at=(240, 600))
        cambiada = validate_model(ed.model).model.revision
        ed.add_step("g", "3", at=(240, 700))
        ultima = validate_model(ed.model).model.revision
        self.assertNotEqual(cambiada, ultima)
        ed.undo()
        self.assertEqual(validate_model(ed.model).model.revision, cambiada)
        ed.redo()
        self.assertEqual(validate_model(ed.model).model.revision, ultima)

    def test_SNUC09_el_documento_inicial_del_editor_tambien_esta_sellado(self):
        """REQ-DAT-02: un proyecto recién abierto (sin ninguna operación todavía) no recalcula la huella al validarse, y el editor sigue
        siendo dueño del mismo documento que recibió (`ed.model is doc`: no se copia)."""
        doc = new_grafcet_document("inicial")
        ed = Editor(doc, ids=IdGenerator("i-"))
        ed.add_variable("Marcha", "input", {"kind": "bool"})
        ed.undo()  # vuelve al documento inicial
        self.assertIs(ed.model, doc)
        with mock.patch.object(modelo, "compute_revision", wraps=compute_revision) as huella:
            r = validate_model(ed.model)
            validate_model(ed.model)
        self.assertEqual(huella.call_count, 0)
        self.assertEqual(r.model.revision if r.model else compute_revision(doc), compute_revision(doc))

    def test_SNUC10_un_borrador_reparado_al_abrir_tambien_se_sella_con_su_copia(self):
        """REQ-DAT-02: si el editor repara el documento al abrirlo (copia y quita un enlace huérfano), sella la copia que usa."""
        doc = new_grafcet_document("reparado")
        doc["draftLinks"] = [{"id": "d1", "fromRef": "nada", "toRef": "nunca"}]
        ed = Editor(doc, ids=IdGenerator("j-"))
        self.assertIsNot(ed.model, doc)
        self.assertEqual(ed.cleaned_draft_link_ids, ("d1",))
        with mock.patch.object(modelo, "compute_revision", wraps=compute_revision) as huella:
            validate_model(ed.model)
        self.assertEqual(huella.call_count, 0)


class ValidarUnaVez(unittest.TestCase):
    def test_SNUC05_validar_dos_veces_lo_mismo_valida_una_y_da_resultados_independientes(self):
        """REQ-CR-04: un documento del editor validado dos veces con las mismas lecturas se valida una vez; ambos resultados son
        iguales a los de una copia sin sellar y modificar uno no cambia el otro."""
        ed = editor()
        ed.add_step("g", "2", at=(240, 600))
        with mock.patch.object(modelo, "_validar", wraps=modelo._validar) as validar:
            a, b = validate_model(ed.model), validate_model(ed.model)
        self.assertEqual(validar.call_count, 1)
        sin_sellar = validate_model(copy.deepcopy(ed.model))
        for r in (a, b):
            self.assertEqual(r.diagnostics, sin_sellar.diagnostics)
            self.assertEqual(r.capabilities, sin_sellar.capabilities)
            self.assertEqual(r.can_simulate, sin_sellar.can_simulate)
        a.diagnostics.append("ajeno")
        a.capabilities.add("ajena")
        c = validate_model(ed.model)
        self.assertEqual(c.diagnostics, sin_sellar.diagnostics)
        self.assertNotIn("ajena", c.capabilities)

    def test_SNUC06_lecturas_distintas_se_validan_por_separado(self):
        """REQ-CR-04: la memoria distingue las lecturas con que se valida."""
        from grafcet.profile import SEMANTIC_OPTIONS
        ed = editor()
        ed.add_step("g", "2", at=(240, 600))
        q = next(iter(SEMANTIC_OPTIONS))
        otra = next(v for v in SEMANTIC_OPTIONS[q]["values"] if v != SEMANTIC_OPTIONS[q]["default"])
        with mock.patch.object(modelo, "_validar", wraps=modelo._validar) as validar:
            validate_model(ed.model)
            validate_model(ed.model, {q: otra})
            validate_model(ed.model, {q: otra})
            validate_model(ed.model)
        self.assertEqual(validar.call_count, 2)


class SesionAlUsarla(unittest.TestCase):
    def test_SNUC07_la_vista_no_arranca_la_sesion_hasta_que_se_usa(self):
        """REQ-SIM-01: construir una `Vista` crea la sesión pero no la arranca; pedir `s` o `start_diags` la arranca una sola vez."""
        from grafcet.engine import Session
        ed = editor()
        with mock.patch.object(Session, "start", autospec=True, side_effect=Session.start) as arrancar:
            v = vista(ed)
            self.assertEqual(arrancar.call_count, 0)
            _ = v.start_diags, v.s
            self.assertEqual(arrancar.call_count, 1)
            _ = v.s, v.start_diags
            self.assertEqual(arrancar.call_count, 1)
        self.assertIsNotNone(v.s.z)
        self.assertEqual(sorted(v.s.z.situation), [s["id"] for s in ed.model["steps"] if s["initial"]])

    def test_SNUC08_reemplazar_la_sesion_o_los_diagnosticos_conserva_su_significado(self):
        """REQ-SIM-01: asignar `s` o `start_diags` (lo hace la ventana al conectar) y un modelo que no compila siguen funcionando."""
        from grafcet.engine import Session
        v = vista(editor())
        nueva = Session(v.s.cm, v.s.scenario, v.s.ctl.budget, options=v.s.options)
        v.s = nueva
        v.start_diags = []
        self.assertIs(v.s, nueva)
        self.assertEqual(v.start_diags, [])
        roto = Editor(new_grafcet_document("roto"), ids=IdGenerator("q-"))
        roto.add_step("g", "0", True, at=(100, 100))
        roto.add_transition("g", "false", [], [], at=(100, 200))  # una transición sin etapas: no compila
        w = vista(roto)
        self.assertIsNone(w.s)
        self.assertEqual(w.start_diags, [])


if __name__ == "__main__":
    unittest.main()
