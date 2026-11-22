"""SNUC01..SNUC10: los cambios de rendimiento del núcleo (V2-E3, paso 9) no cambian ningún resultado."""
import copy
import os
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
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ)); os.environ.pop("GRAFCONNECT_COMPROBAR_SELLOS", None)  # (cuenta lo que la memoria evita: la comprobación de sellos recalcula a propósito)

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
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ)); os.environ.pop("GRAFCONNECT_COMPROBAR_SELLOS", None)  # (cuenta lo que la memoria evita: la comprobación de sellos recalcula a propósito)

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


class _Registros(list):
    """Lista de la traza que no deja recorrerla de principio a fin (`state()` solo necesita su cola)."""
    recorridos = 0

    def __iter__(self):
        type(self).recorridos += 1
        return super().__iter__()


class EstadoConTrazaLarga(unittest.TestCase):
    def test_SNUC11_state_no_recorre_la_traza_entera_y_su_coste_no_crece_con_ella(self):
        """REQ-SIM-01: `Vista.state()` busca la última evolución desde el final de la traza (que llega a 10^6 registros, D-TRAZA-LIM):
        con unos 40.000 registros la salida es la misma y el coste no crece."""
        from time import perf_counter
        ed = Editor(new_grafcet_document("rend"), ids=IdGenerator("r-"))
        a = ed.add_step("g", "0", True, at=(240, 100))
        b = ed.add_step("g", "1", at=(240, 440))
        marcha = ed.add_variable("Marcha", "input", {"kind": "bool"})
        ed.add_transition("g", "Marcha", [a], [b], at=(240, 270))
        v = vista(ed)
        v.s.manual_input({marcha: True})  # franquea: la traza acaba con una evolución real
        while v.s.status != "pausada-estable" or v.s.next_stimulus() is not None:
            v.s.step_external()
        corta = v.state()
        self.assertTrue(any(r["kind"] == "evolucion" for r in v.s.trace.records))

        def coste():
            mejor = float("inf")
            for _ in range(15):
                t = perf_counter()
                v.state()
                mejor = min(mejor, perf_counter() - t)
            return mejor
        antes = coste()
        evolucion = next(r for r in v.s.trace.records if r["kind"] == "evolucion")
        relleno = [dict(evolucion, cleared=["relleno"]) for _ in range(40000)]  # (distinta de la última: si se leyera una del relleno, se vería)
        registros = _Registros(relleno + list(v.s.trace.records))
        v.s.trace.records = registros
        _Registros.recorridos = 0
        larga = v.state()
        self.assertEqual(_Registros.recorridos, 0, "state() no debe recorrer la traza entera")
        self.assertTrue(corta["lastCleared"])
        self.assertEqual(larga["lastCleared"], corta["lastCleared"])
        self.assertEqual({k: x for k, x in larga.items() if k != "trace"}, {k: x for k, x in corta.items() if k != "trace"})
        despues = coste()
        self.assertLess(despues, antes * 2 + 0.002, f"state() con 40.000 registros de más: {despues * 1000:.2f} ms frente a {antes * 1000:.2f} ms")


def _manual_input_lenta(self, changes):
    """`Session.manual_input` como era antes de E7 paso 4 (recorría todos los lotes): la referencia de la prueba."""
    from grafcet.diagnostics import Diagnostic, DiagnosticError
    from grafcet.scenario import Batch
    if self.status != "pausada-estable":
        raise RuntimeError("las entradas manuales se admiten en pausa estable")
    at = self.z.time
    used = [b.ordinal for b in self.batches if b.time == at]
    b = Batch(f"manual-{len(self.trace.records) + 1}", at, (max(used) + 1) if used else 0, tuple(sorted(changes.items())), "manual")
    for vid in changes:
        if self.cm.variables[vid].role != "input":
            raise DiagnosticError(Diagnostic("D-ESCRITURA-ROL", f"{vid} no es entrada", element=vid))
    idx = next((i for i, x in enumerate(self.batches) if i >= self.z.next_batch and (x.time, x.ordinal) > (b.time, b.ordinal)),
               len(self.batches))
    self.batches.insert(idx, b)
    self._log("entrada-manual", timeUs=str(at), batch=b.to_dict(self.cm))
    return b


class ManualInputPorLaCola(unittest.TestCase):
    def sesiones(self):
        from grafcet.engine import Session
        ed = Editor(new_grafcet_document("rend"), ids=IdGenerator("r-"))
        a = ed.add_step("g", "0", True, at=(240, 100))
        b = ed.add_step("g", "1", at=(240, 440))
        c = ed.add_step("g", "2", at=(240, 780))
        x = ed.add_variable("A", "input", {"kind": "bool"})
        y = ed.add_variable("B", "input", {"kind": "bool"})
        ed.add_transition("g", "A", [a], [b], at=(240, 270))
        ed.add_transition("g", "B", [b], [c], at=(240, 610))
        pendientes = [(5_000_000, 0, {x: True}), (5_000_000, 1, {y: True}), (9_000_000, 0, {x: False}), (20_000_000, 0, {y: False})]
        v = Vista(ed.model["id"], "t", "", lambda: (ed.model, layout_from_presentation(ed.presentation)), {}, batches=pendientes)
        _ = v.s

        class Lenta(Session):
            manual_input = _manual_input_lenta
        lenta = Lenta(v.s.cm, v.s.scenario, v.s.ctl.budget, options=v.s.options)
        lenta.start()
        rapida = Session(v.s.cm, v.s.scenario, v.s.ctl.budget, options=v.s.options)
        rapida.start()
        return rapida, lenta, x, y

    def test_SNUC12_manual_input_da_lo_mismo_que_la_version_que_recorria_todos_los_lotes(self):
        """REQ-SIM-01: `manual_input` (por la cola de la lista de lotes) coincide con la referencia lenta: ordinal, posición en `batches` y traza,
        con muchas llamadas, varias en el mismo instante, con lotes de escenario pendientes y tras avanzar el tiempo."""
        from random import Random
        for semilla in range(6):
            azar = Random(semilla)
            rapida, lenta, x, y = self.sesiones()
            self.assertTrue(rapida._lotes_ordenados)
            for paso in range(120):
                if azar.random() < 0.35:
                    destino = rapida.z.time + azar.choice((0, 1_000_000, 3_000_000, 6_000_000))
                    for s in (rapida, lenta):
                        if s.status == "pausada-estable":
                            s.advance_to(destino)
                else:
                    cambios = {azar.choice((x, y)): azar.random() < 0.5}
                    resultados = []
                    for s in (rapida, lenta):
                        try:
                            resultados.append(s.manual_input(cambios))
                        except RuntimeError as exc:
                            resultados.append(str(exc))
                    self.assertEqual(resultados[0], resultados[1], (semilla, paso))
                self.assertEqual([(b.id, b.time, b.ordinal, b.changes, b.origin) for b in rapida.batches],
                                 [(b.id, b.time, b.ordinal, b.changes, b.origin) for b in lenta.batches], (semilla, paso))
                self.assertEqual(rapida.z.next_batch, lenta.z.next_batch)
                self.assertEqual(rapida.trace.records, lenta.trace.records, (semilla, paso))

    def test_SNUC13_si_los_lotes_no_estan_ordenados_manual_input_busca_por_toda_la_lista(self):
        """REQ-SIM-01: una lista de lotes sin ordenar (una instantánea restaurada no la comprueba) no usa el atajo y da lo que daba la versión lenta."""
        from grafcet.engine import Session
        from grafcet.scenario import Batch
        rapida, _, x, _y = self.sesiones()
        desordenados = [Batch("b0", 8_000_000, 0, ((x, True),)), Batch("b1", 2_000_000, 0, ((x, False),))]
        s = Session(rapida.cm, rapida.scenario, rapida.ctl.budget, batches=desordenados, options=rapida.options)
        self.assertFalse(s._lotes_ordenados)
        s.start()
        t = Session(rapida.cm, rapida.scenario, rapida.ctl.budget, batches=list(desordenados), options=rapida.options)
        t.manual_input = _manual_input_lenta.__get__(t)
        t.start()
        for k in range(4):
            self.assertEqual(s.manual_input({x: k % 2 == 0}), t.manual_input({x: k % 2 == 0}))
            self.assertEqual(s.batches, t.batches)

    def test_SNUC14_el_coste_de_manual_input_no_crece_con_los_lotes_ya_procesados(self):
        """REQ-SIM-01: con 40.000 lotes procesados de más, una llamada a `manual_input` cuesta como con 400."""
        from time import perf_counter
        from grafcet.scenario import Batch
        costes = {}
        for n in (400, 40_000):
            rapida, _, x, _y = self.sesiones()
            procesados = [Batch(f"p{i}", i, 0, (), "escenario") for i in range(n)]
            rapida.batches = procesados + rapida.batches
            rapida.z.next_batch += n
            rapida.z.time = n + 10
            mejor = float("inf")
            for k in range(30):
                t = perf_counter()
                rapida.manual_input({x: k % 2 == 0})
                mejor = min(mejor, perf_counter() - t)
            costes[n] = mejor
        self.assertLess(costes[40_000], costes[400] * 3 + 0.0005, costes)


if __name__ == "__main__":
    unittest.main()
