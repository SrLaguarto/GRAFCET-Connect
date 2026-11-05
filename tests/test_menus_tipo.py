"""Los submenús «Tipo de acción» (con «Orden de forzado») y «Tipo de etapa» (Etapa, Encapsulante, Macroetapa y la
casilla «Etapa inicial») del botón derecho, y `Editor.set_step_kind` con la macroetapa.

Las pruebas del núcleo (SMTP01..) no necesitan Qt. Las de la interfaz (SMTP10..) se omiten si PySide6 no está
instalado y ejercen `Edicion.menu` y las funciones que el menú llama. Ninguna es oráculo del documento 11:
comprueban que cada cambio es una sola operación de deshacer, que lo que el modelo no admite se rechaza sin cambiar
nada y que la macroetapa que sale de convertir una etapa es la misma que da `add_macro`."""
import re
import tempfile
import unittest
from pathlib import Path

from test_editor_cadenas import BaseQt, QT, centro, centro_caja, centro_orden

from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Editor, new_grafcet_document
from grafcet.ids import IdGenerator
from grafcet.persistence import add_document, new_project, open_model, save_project

if QT:
    from PySide6.QtCore import QPointF


TIPOS_Y_ORDEN = ["Continua", "Condicionada", "Al activar", "Al desactivar", "Por evento", "Orden de forzado"]


def nuevo():
    return Editor(new_grafcet_document("m"), ids=IdGenerator("x"))


def forma(ed):
    """El modelo con nombres en vez de ID: etapas, macroetapas con su expansión, transiciones y posición de cada
    elemento."""
    m = ed.model
    nombre = {x["id"]: x["label"] for c in ("steps", "partials") for x in m[c]}
    nombre.update({x["id"]: x["label"] for x in m["hierarchy"]["macros"]})
    sitio = {q["elementRef"]: (q["x"], q["y"]) for q in ed.presentation["elementLayouts"]}
    return {"etapas": sorted((s["label"], s["kind"], nombre[s["partialRef"]], s["initial"]) for s in m["steps"]),
            "macros": sorted((x["label"], nombre[x["partialRef"]],
                              nombre[next(e for e in m["hierarchy"]["expansions"]
                                          if e["id"] == x["expansionRef"])["partialRef"]])
                             for x in m["hierarchy"]["macros"]),
            "parciales": sorted((q["label"], nombre.get(q.get("ownerRef"))) for q in m["partials"]),
            "transiciones": sorted((tuple(sorted(nombre[i] for i in t["preRefs"])),
                                    tuple(sorted(nombre[i] for i in t["postRefs"]))) for t in m["transitions"]),
            "sitios": sorted((nombre.get(i, i), p) for i, p in sitio.items() if i in nombre)}


class TipoDeEtapaEnElNucleo(unittest.TestCase):
    def cadena(self):
        """A -t1-> X -t2-> B, con X una etapa ordinaria en (160, 180)."""
        ed = nuevo()
        ed.add_variable("p", "input", {"kind": "bool"})
        a = ed.add_step("g", "A", True, at=(160, 60))
        x = ed.add_step("g", "M", at=(160, 180))
        b = ed.add_step("g", "B", at=(160, 300))
        ed.add_transition("g", "p", pre=[a], post=[x], label="t1", at=(160, 120))
        ed.add_transition("g", "p", pre=[x], post=[b], label="t2", at=(160, 240))
        return ed, a, x, b

    def rechaza(self, ed, codigo, op, *args):
        antes, pila = (ed.model, ed.presentation), len(ed.undo_stack)
        with self.assertRaises(DiagnosticError) as ctx:
            op(*args)
        self.assertIn(codigo, {d.code for d in ctx.exception.diagnostics}, [str(d) for d in ctx.exception.diagnostics])
        self.assertEqual((ed.model, ed.presentation), antes)
        self.assertEqual(len(ed.undo_stack), pila)
        return " ".join(d.message for d in ctx.exception.diagnostics)

    def test_SMTP01_etapa_a_macroetapa_conserva_id_nombre_posicion_y_enlaces_y_equivale_a_add_macro(self):
        """REQ-JER-04, REQ-EDT-08, REQ-MOD-07: `set_step_kind(etapa, "macro")` deja una macroetapa con el ID, el
        nombre, la posición y los enlaces de la etapa, y su expansión con la entrada y la salida igual que
        `add_macro`; es una sola operación de deshacer y el resultado se guarda y se abre sin pérdida."""
        ed, a, x, b = self.cadena()
        antes, n = (ed.model, ed.presentation), len(ed.undo_stack)
        ed.set_step_kind(x, "macro")
        self.assertEqual(len(ed.undo_stack), n + 1)
        (mac,) = ed.model["hierarchy"]["macros"]
        self.assertEqual((mac["id"], mac["label"], mac["partialRef"]), (x, "M", "g"))
        self.assertNotIn(x, [s["id"] for s in ed.model["steps"]])
        self.assertTrue(all(x not in q["stepRefs"] for q in ed.model["partials"]))
        info = ed.macro_info(x)
        self.assertEqual([(s["kind"], s["label"]) for s in ed.model["steps"] if s["partialRef"] == info.partial],
                         [("entry", "E1"), ("exit", "S1")])
        self.assertEqual([(t["preRefs"], t["postRefs"]) for t in ed.model["transitions"]], [([a], [x]), ([x], [b])])
        # la misma macroetapa que daría add_macro en ese sitio
        ed2 = nuevo()
        ed2.add_variable("p", "input", {"kind": "bool"})
        a2 = ed2.add_step("g", "A", True, at=(160, 60))
        b2 = ed2.add_step("g", "B", at=(160, 300))
        mac2 = ed2.add_macro("g", "M", at=(160, 180))
        ed2.add_transition("g", "p", pre=[a2], post=[mac2.macro], label="t1", at=(160, 120))
        ed2.add_transition("g", "p", pre=[mac2.macro], post=[b2], label="t2", at=(160, 240))
        self.assertEqual(forma(ed), forma(ed2))
        self.assertEqual({d.code for d in ed.validate().diagnostics}, {d.code for d in ed2.validate().diagnostics})
        # se guarda y se abre tal cual
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "Macroetapa por conversión")
            add_document(pj, ed.model)
            add_document(pj, ed.presentation)
            save_project(Path(tmp), pj)
            op = open_model(Path(tmp))
        self.assertEqual(op.doc, ed.model)
        self.assertEqual(op.presentations[0], ed.presentation)
        ed.undo()
        self.assertEqual((ed.model, ed.presentation), antes)
        ed.redo()
        self.assertEqual(ed.model["hierarchy"]["macros"][0]["id"], x)

    def test_SMTP02_macroetapa_a_etapa_ordinaria_o_encapsulante_solo_con_la_expansion_vacia(self):
        """REQ-JER-04, REQ-JER-05, REQ-MOD-07: una macroetapa pasa a etapa ordinaria o encapsulante con su ID y sus
        enlaces si su expansión solo tiene la entrada, la salida y lo que las une (se borra); con algo más se
        rechaza («vacíe la expansión antes») y no cambia nada; cada cambio es una operación de deshacer."""
        ed, a, x, b = self.cadena()
        ed.set_step_kind(x, "macro")
        info = ed.macro_info(x)
        despues_de_macro, n = (ed.model, ed.presentation), len(ed.undo_stack)
        # lo que une la entrada con la salida no cuenta como contenido
        ed.add_transition(info.partial, "p", pre=[info.entry], post=[info.exit], label="u")
        with_u = (ed.model, ed.presentation)
        ed.set_step_kind(x, "enclosing")
        self.assertEqual(len(ed.undo_stack), n + 2)
        self.assertEqual([(s["id"], s["kind"], s["label"]) for s in ed.model["steps"] if s["id"] == x],
                         [(x, "enclosing", "M")])
        self.assertEqual((ed.model["hierarchy"]["macros"], ed.model["hierarchy"]["expansions"]), ([], []))
        self.assertEqual([p["id"] for p in ed.model["partials"]], ["g"])
        self.assertEqual(sorted(s["label"] for s in ed.model["steps"]), ["A", "B", "M"])
        self.assertEqual([t["label"] for t in ed.model["transitions"]], ["t1", "t2"])
        self.assertIn(x, ed.model["partials"][0]["stepRefs"])
        self.assertEqual({q["elementRef"] for q in ed.presentation["elementLayouts"]}, {a, x, b, *(
            t["id"] for t in ed.model["transitions"])})
        self.assertEqual([t["preRefs"] + t["postRefs"] for t in ed.model["transitions"]], [[a, x], [x, b]])
        ed.undo()
        self.assertEqual((ed.model, ed.presentation), with_u)
        ed.set_step_kind(x, "ordinary")
        self.assertEqual(next(s for s in ed.model["steps"] if s["id"] == x)["kind"], "ordinary")
        ed.undo()
        # con una etapa más dentro de la expansión: rechazado
        ed.add_step(info.partial, "Dentro")
        mensaje = self.rechaza(ed, "D-FORMATO", ed.set_step_kind, x, "ordinary")
        self.assertIn("vacíe la expansión antes", mensaje)
        self.rechaza(ed, "D-FORMATO", ed.set_step_kind, x, "enclosing")
        self.assertIsNotNone(despues_de_macro)

    def test_SMTP03_rechazos_al_convertir_en_macroetapa(self):
        """REQ-JER-04, REQ-JER-05, REQ-MOD-07: una encapsulante con recintos, una etapa inicial, una con acciones
        sin completar unidas o la entrada y la salida de una expansión no pasan a macroetapa; una con acciones se
        rechaza con un texto claro. Nada cambia ni entra en el historial."""
        ed = nuevo()
        ed.add_variable("Q", "output", {"kind": "bool"})
        ini = ed.add_step("g", "I", True, at=(160, 60))
        h = ed.add_step("g", "H", at=(160, 180))
        ed.set_step_kind(h, "enclosing")
        ed.new_enclosure(h, "R")
        c = ed.add_step("g", "C", at=(160, 300))
        v = ed.add_step("g", "V", at=(160, 420))
        otro = ed.add_macro("g", "Z", at=(400, 60))
        self.assertIn("recinto", self.rechaza(ed, "D-FORMATO", ed.set_step_kind, h, "macro"))
        self.assertIn("inicial", self.rechaza(ed, "D-FORMATO", ed.set_step_kind, ini, "macro"))
        self.rechaza(ed, "D-FORMATO", ed.set_step_kind, otro.entry, "macro")
        self.rechaza(ed, "D-FORMATO", ed.set_step_kind, otro.exit, "ordinary")
        ed.add_draft_action((300, 300), {"etapa": c})
        self.assertIn("sin completar", self.rechaza(ed, "D-FORMATO", ed.set_step_kind, c, "macro"))
        self.rechaza(ed, "D-REF", ed.set_step_kind, "no-existe", "macro")
        # una acción del modelo: se detecta antes y se rechaza con un texto claro
        ed.add_continuous_action(v, ed.model["variables"][0]["id"], "true")
        mensaje = self.rechaza(ed, "D-FORMATO", ed.set_step_kind, v, "macro")
        self.assertIn("tiene acciones u órdenes de forzado: quítelas antes de convertirla en macroetapa", mensaje)
        self.assertNotRegex(mensaje, r"D-[A-Z]|[a-z]-[0-9a-f]{32}")


    def test_SMTP04_etapa_con_ordenes_o_enlace_de_activacion_no_pasa_a_macroetapa_con_texto_claro(self):
        """REQ-JER-04, REQ-JER-05, REQ-EDT-09: una etapa que es origen de una orden de forzado, la que lleva el
        enlace de activación de un recinto o la que figura en el conjunto de una orden se rechazan antes de la
        validación, con un texto sin códigos ni ID que dice qué quitar."""
        ed = nuevo()
        ed.add_step("g", "I", True, at=(160, 60))
        h = ed.add_step("g", "H", at=(160, 180))
        ed.set_step_kind(h, "enclosing")
        rec = ed.new_enclosure(h, "R")
        a = ed.add_step(rec.partial, "A")
        ed.set_activation(a)
        otro = ed.add_partial("Otro")
        b = ed.add_step(otro, "B")
        origen = ed.add_step("g", "O", at=(160, 300))
        ed.add_force(origen, otro, "explicit", [b])
        for etapa, texto in ((a, "enlace de activación"), (origen, "órdenes de forzado"), (b, "conjunto de etapas")):
            mensaje = self.rechaza(ed, "D-FORMATO", ed.set_step_kind, etapa, "macro")
            self.assertIn(texto, mensaje)
            self.assertIn("antes de convertirla en macroetapa", mensaje)
            self.assertNotRegex(mensaje, r"D-[A-Z]|[a-z]-[0-9a-f]{32}")


@unittest.skipUnless(QT, "PySide6 no está instalado")
class SubmenusDeTipo(BaseQt):
    def preparado(self):
        """Una etapa inicial H, un grafcet parcial G con una etapa B y una variable de salida; la ventana a la vista."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        e.pedir_accion = lambda *a: None
        h = e.poner_etapa(QPointF(260, 80), inicial=True)
        e.renombrar(h, "2")
        g = e.poner_parcial(QPointF(700, 220))
        c = cajas_parciales(e.M)[g]
        b = e.poner_etapa(QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
        e.nueva_variable("Q00", "output")
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        return w, e, h, g, b

    @staticmethod
    def sin_ids(texto):
        """Ningún ID interno (`s-…`, `g-…`, `m-…`, `x-…`, `r-…`) en un texto que se le muestra al usuario."""
        return re.search(r"[a-z]-[0-9a-f]{32}", texto) is None

    @staticmethod
    def submenu(opciones, texto):
        """Las opciones del submenú `texto` como {texto: (función, icono)}."""
        lista = dict(opciones)[texto]
        return {t: (f, i[0] if i else None) for t, f, *i in lista}

    # -- acción <-> orden de forzado -------------------------------------------------------------------------------
    def test_SMTP10_accion_a_orden_de_forzado_aceptar_cancelar_y_deshacer(self):
        """REQ-EDT-09, REQ-JER-02: «Tipo de acción > Orden de forzado» en una acción de una etapa abre el diálogo de
        forzado; al aceptar quita la acción y crea la orden de la misma etapa en una sola operación de deshacer;
        cancelar no cambia nada; el submenú lleva icono en cada tipo."""
        w, e, h, g, b = self.preparado()
        self.assertIsNone(e.poner_accion(h, {"tipo": "continua", "variable": "Q00"}))
        (aid,) = [a["id"] for a in e.ed.model["actions"]]
        opciones = e.menu(centro_caja(w, aid))
        self.assertEqual(opciones[0][0], "Tipo de acción")
        sub = self.submenu(opciones, "Tipo de acción")
        self.assertEqual(list(sub), TIPOS_Y_ORDEN)
        self.assertTrue(all(i is not None and not i.isNull() for _, i in sub.values()))
        self.assertIn("Continua", e.menu_marcadas)
        self.assertNotIn("Orden de forzado", e.menu_marcadas)
        pedidas = []
        e.pedir_forzado = lambda datos: pedidas.append(datos) or None
        antes, n = self.estado(e), len(e.ed.undo_stack)
        sub["Orden de forzado"][0]()  # cancelar
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertEqual((pedidas[0]["origen"], [d for d, _ in pedidas[0]["destinos"]]), ("2", [g]))
        e.pedir_forzado = lambda datos: {"destino": g, "forma": "explicit", "etapas": [b]}
        sub["Orden de forzado"][0]()
        (f,) = e.ed.model["forces"]
        self.assertEqual((e.ed.model["actions"], f["sourceStepRef"], f["targetPartialRef"], f["targetKind"],
                          f["targetSteps"]), ([], h, g, "explicit", [b]))
        self.assertEqual((len(e.ed.undo_stack), e.sel), (n + 1, [f["id"]]))
        self.assertEqual([c["id"] for c in w.diagrama.cajas_ordenes], [f["id"]])
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        e.rehacer()
        self.assertEqual((len(e.ed.model["forces"]), e.ed.model["actions"]), (1, []))

    def test_SMTP11_accion_sin_completar_o_suelta_a_orden_y_rechazos(self):
        """REQ-EDT-09, REQ-JER-02: una acción sin completar unida a una etapa pasa a orden del modelo; una suelta, a
        orden suelta; sin otro parcial al que forzar se rechaza con el aviso en rojo; una explícita sin etapas,
        también; un rechazo del núcleo deja todo como estaba."""
        w, e, h, g, b = self.preparado()
        e.anadir_accion(h)
        (borrador,) = e.ed.draft_actions()
        did = borrador["id"]
        e.pedir_forzado = lambda datos: {"destino": g, "forma": "explicit", "etapas": []}
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.submenu(e.menu(centro_caja(w, did)), "Tipo de acción")["Orden de forzado"][0]()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue(e.mensaje and not e.mensaje_info and "etapa" in e.mensaje, e.mensaje)
        e.pedir_forzado = lambda datos: {"destino": g, "forma": "empty", "etapas": []}
        self.submenu(e.menu(centro_caja(w, did)), "Tipo de acción")["Orden de forzado"][0]()
        self.assertEqual((e.ed.draft_actions(), [(f["sourceStepRef"], f["targetKind"]) for f in e.ed.model["forces"]],
                          len(e.ed.undo_stack)), ([], [(h, "empty")], n + 1))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        # una acción suelta: orden suelta (sin etapa) con lo elegido, que sigue sin simularse
        suelta = e.poner_accion_suelta(QPointF(500, 600))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.submenu(e.menu(centro_caja(w, suelta)), "Tipo de acción")["Orden de forzado"][0]()
        (d,) = [x for x in e.ed.draft_actions() if x["id"] == suelta]
        self.assertEqual((d["tipo"], d["destino"], d["forma"], "etapa" in d, "variable" in d),
                         ("forzado", g, "empty", False, False))
        self.assertEqual((len(e.ed.undo_stack), e.ed.model["forces"], e.es_orden_suelta(suelta)), (n + 1, [], True))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        # sin otro parcial al que forzar
        w, e = self.vacio()
        e.pedir_accion = lambda *a: None
        solo = e.poner_etapa(QPointF(260, 80), inicial=True)
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(solo, {"tipo": "continua", "variable": "Q00"}))
        (aid,) = [a["id"] for a in e.ed.model["actions"]]
        e.pedir_forzado = lambda datos: self.fail("no hay nada que elegir")
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.parpadeo.parar()
        self.submenu(e.menu(centro_caja(w, aid)), "Tipo de acción")["Orden de forzado"][0]()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue("otro parcial" in e.mensaje and not e.mensaje_info, e.mensaje)
        self.assertEqual(e.parpadeo.ids, {aid})
        e.parpadeo.parar()

    def test_SMTP12_ciclo_de_forzado_al_convertir_una_accion_no_cambia_nada(self):
        """REQ-JER-02, REQ-EDT-09: si el núcleo rechaza la orden (ciclo, D-JERARQUIA-CICLO), la acción sigue donde
        estaba: la conversión es atómica."""
        w, e, d = self.con_recinto()
        e.pedir_accion = lambda *a: None
        h, r, a = d["h"], d["r"], d["a"]
        e.nueva_variable("Q00", "output")
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "empty", "etapas": []}
        self.assertIsNotNone(e.forzar(h))  # H (raíz) fuerza al recinto
        self.assertIsNone(e.poner_accion(a, {"tipo": "continua", "variable": "Q00"}))
        (aid,) = [x["id"] for x in e.ed.model["actions"]]
        # A (del recinto) fuerza al raíz
        e.pedir_forzado = lambda datos: {"destino": "g", "forma": "empty", "etapas": []}
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.parpadeo.parar()
        self.assertIsNone(e.accion_a_orden(aid))
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue("ciclo" in e.mensaje and not e.mensaje_info, e.mensaje)
        e.parpadeo.parar()

    def test_SMTP13_orden_de_forzado_a_accion_del_modelo_sin_completar_y_suelta(self):
        """REQ-EDT-09, REQ-JER-02: el menú de una orden de forzado (del modelo, sin completar unida o suelta) lleva
        «Tipo de acción» con «Orden de forzado» marcada; elegir un tipo la convierte en una acción de ese tipo de
        la misma etapa (borrador con «?») y abre su editor, en una sola operación de deshacer; elegir «Orden de
        forzado» no cambia nada."""
        w, e, h, g, b = self.preparado()
        e.pedir_forzado = lambda datos: {"destino": g, "forma": "explicit", "etapas": [b]}
        fid = e.forzar(h)
        abiertas = []
        e.pedir_accion = lambda sid, aid: abiertas.append((sid, aid))
        opciones = e.menu(centro_orden(w, fid))
        self.assertEqual([t for t, _ in opciones],
                         ["Tipo de acción", "-", "Editar orden de forzado…", "Quitar orden de forzado"])
        sub = self.submenu(opciones, "Tipo de acción")
        self.assertEqual(list(sub), TIPOS_Y_ORDEN)
        self.assertTrue(all(i is not None and not i.isNull() for _, i in sub.values()))
        self.assertEqual(e.menu_marcadas, {"Orden de forzado"})
        antes, n = self.estado(e), len(e.ed.undo_stack)
        sub["Orden de forzado"][0]()
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), abiertas), (antes, n, []))
        sub["Al activar"][0]()
        (borrador,) = e.ed.draft_actions()
        self.assertEqual((e.ed.model["forces"], borrador["tipo"], borrador["etapa"], e.ed.model["actions"]),
                         ([], "activacion", h, []))
        self.assertEqual((len(e.ed.undo_stack), abiertas, e.accion), (n + 1, [(h, borrador["id"])], borrador["id"]))
        self.assertEqual([c["id"] for c in w.diagrama.cajas_acciones if c["etapa"] == h], [borrador["id"]])
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        # una orden sin completar unida a la etapa: el mismo borrador cambia de tipo
        did = e.poner_orden_ficha(centro(e.M, h))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        abiertas.clear()
        sub = self.submenu(e.menu(centro_caja(w, did)), "Tipo de acción")
        self.assertEqual(e.menu_marcadas & {"Orden de forzado"}, {"Orden de forzado"})
        sub["Por evento"][0]()
        (d,) = e.ed.draft_actions()
        self.assertEqual((d["id"], d["tipo"], d["etapa"], "destino" in d, "forma" in d),
                         (did, "evento", h, False, False))
        self.assertEqual((len(e.ed.undo_stack), abiertas, e.es_orden_suelta(did)), (n + 1, [(h, did)], False))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        # suelta: pasa a ser una acción suelta
        e.quitar_orden(did)
        suelta = e.poner_orden_ficha(QPointF(500, 600))
        self.assertIsNone(e.ed.draft_actions()[-1].get("etapa"))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        abiertas.clear()
        self.submenu(e.menu(centro_caja(w, suelta)), "Tipo de acción")["Continua"][0]()
        d = next(x for x in e.ed.draft_actions() if x["id"] == suelta)
        self.assertEqual((d["tipo"], "etapa" in d, len(e.ed.undo_stack), abiertas),
                         ("continua", False, n + 1, [(None, suelta)]))

    # -- tipo de etapa -----------------------------------------------------------------------------------------
    def test_SMTP20_submenu_tipo_de_etapa_con_iconos_marcas_y_casilla_de_inicial(self):
        """REQ-JER-04, REQ-JER-05, REQ-EDT-09: el botón derecho en una etapa ofrece «Tipo de etapa» con icono por
        opción (Etapa, Encapsulante, Macroetapa: excluyentes, con la actual marcada, y «Etapa inicial», casilla
        independiente que usa `set_initial`); ya no hay entradas sueltas «Convertir en…»; la macroetapa lo ofrece
        sin la casilla de inicial; la entrada y la salida de una expansión no lo ofrecen."""
        w, e = self.vacio()
        e.pedir_accion = lambda *a: None
        s = e.poner_etapa(QPointF(260, 80))

        def inicial():
            return next(x for x in e.ed.model["steps"] if x["id"] == s)["initial"]
        opciones = e.menu(centro(e.M, s))
        self.assertEqual([t for t, _ in opciones][:3], ["Colocación de las acciones", "-", "Tipo de etapa"])
        self.assertFalse(any(t.startswith("Convertir en") for t, _ in opciones))
        sub = self.submenu(opciones, "Tipo de etapa")
        self.assertEqual(list(sub), ["Etapa", "Etapa inicial", "Encapsulante", "Macroetapa"])
        self.assertTrue(all(i is not None and not i.isNull() for _, i in sub.values()))
        self.assertEqual(e.menu_marcadas & {"Etapa", "Encapsulante", "Macroetapa", "Etapa inicial"}, {"Etapa"})
        n = len(e.ed.undo_stack)
        sub["Etapa inicial"][0]()
        self.assertEqual((inicial(), len(e.ed.undo_stack)), (True, n + 1))
        e.menu(centro(e.M, s))
        self.assertEqual(e.menu_marcadas & {"Etapa", "Encapsulante", "Macroetapa", "Etapa inicial"},
                         {"Etapa", "Etapa inicial"})
        self.submenu(e.menu(centro(e.M, s)), "Tipo de etapa")["Etapa inicial"][0]()
        self.assertFalse(inicial())
        e.deshacer()
        self.assertTrue(inicial())
        e.deshacer()
        # la macroetapa: Macroetapa marcada y sin «Etapa inicial»; la entrada y la salida no ofrecen el submenú
        mid = e.poner_macro(QPointF(260, 400))
        x = e.ed.macro_info(mid)
        sub = self.submenu(e.menu(centro(e.M, mid)), "Tipo de etapa")
        self.assertEqual(list(sub), ["Etapa", "Encapsulante", "Macroetapa"])
        self.assertEqual(e.menu_marcadas & {"Etapa", "Encapsulante", "Macroetapa"}, {"Macroetapa"})
        for ident in (x.entry, x.exit):
            self.assertNotIn("Tipo de etapa", [t for t, _ in e.menu(centro(e.M, ident))])
        # el panel de opciones ofrece los mismos tipos como casillas, con la actual marcada
        e.sel = [s]
        e.cambiado.emit()
        self.assertEqual([(t, b.isChecked()) for t, b in w.props.ficha_etapa.botones.items()
                          if t in ("Etapa", "Encapsulante", "Macroetapa") and not b.isHidden()],
                         [("Etapa", True), ("Encapsulante", False), ("Macroetapa", False)])

    def test_SMTP21_los_cuatro_cambios_de_tipo_de_etapa_con_el_menu(self):
        """REQ-JER-04, REQ-JER-05, REQ-EDT-09: Etapa <-> Encapsulante y Etapa/Encapsulante <-> Macroetapa desde el
        submenú; la etapa conserva su ID, su nombre y su lugar al pasar a macroetapa (que recibe su expansión a
        la derecha, con su entrada y su salida) y al volver; cada cambio es una operación de deshacer."""
        w, e = self.vacio()
        e.pedir_accion = lambda *a: None
        s = e.poner_etapa(QPointF(260, 80))
        e.renombrar(s, "7")
        lugar = e.ed.presentation["elementLayouts"][0]
        x0, y0 = lugar["x"], lugar["y"]

        def elige(ident, tipo):
            n = len(e.ed.undo_stack)
            self.submenu(e.menu(centro(e.M, ident)), "Tipo de etapa")[tipo][0]()
            self.assertEqual(len(e.ed.undo_stack), n + 1, tipo)

        def kind():
            return next((x["kind"] for x in e.ed.model["steps"] if x["id"] == s), "macro")
        elige(s, "Encapsulante")
        self.assertEqual(kind(), "enclosing")
        elige(s, "Etapa")
        self.assertEqual(kind(), "ordinary")
        elige(s, "Macroetapa")
        (mac,) = e.ed.model["hierarchy"]["macros"]
        self.assertEqual((kind(), mac["id"], mac["label"]), ("macro", s, "7"))
        info = e.ed.macro_info(s)
        lay = {q["elementRef"]: (q["x"], q["y"]) for q in e.ed.presentation["elementLayouts"]}
        self.assertEqual(lay[s], (x0, y0), "la macroetapa sigue donde estaba la etapa")
        entrada, salida = (tuple(int(c) for c in lay[i]) for i in (info.entry, info.exit))
        self.assertTrue(entrada[0] > int(lay[s][0]) and salida[1] > entrada[1], lay)
        self.assertEqual(e.sel, [s])
        self.assertTrue(e.mensaje_info and "macroetapa" in e.mensaje)
        self.assertEqual([x["id"] for x in e.M["macros"]], [s], "el dibujo la recibe")
        elige(s, "Encapsulante")  # macroetapa -> encapsulante: la expansión, vacía, se borra
        self.assertEqual((kind(), e.ed.model["hierarchy"]["macros"], len(e.ed.model["partials"])), ("enclosing", [], 1))
        elige(s, "Macroetapa")  # encapsulante -> macroetapa
        elige(s, "Etapa")  # macroetapa -> etapa ordinaria
        self.assertEqual((kind(), e.ed.model["hierarchy"], len(e.ed.model["partials"])),
                         ("ordinary", {"macros": [], "expansions": [], "enclosures": []}, 1))
        self.assertEqual([x["id"] for x in e.M["steps"]], [s])
        for _ in range(3):
            e.deshacer()
        self.assertEqual(kind(), "macro")
        # la misma etapa, ya macroetapa, no deja referencias rotas
        self.assertEqual([d for d in e.ed.validate().diagnostics if d.code in ("D-REF", "D-PROPIETARIO", "D-ID")], [])

    def test_SMTP22_rechazos_del_tipo_de_etapa_se_muestran_en_rojo_y_no_cambian_nada(self):
        """REQ-JER-04, REQ-JER-05, REQ-EDT-09: una encapsulante con recintos no vuelve a etapa ni pasa a macroetapa;
        una macroetapa con contenido en la expansión no vuelve a etapa («vacíe la expansión antes»); la entrada y
        la salida no cambian; una etapa inicial no pasa a macroetapa; con acciones, la validación del modelo
        decide. Cada rechazo es el aviso en rojo, el parpadeo del elemento y ningún cambio."""
        w, e, d = self.con_recinto()
        e.pedir_accion = lambda *a: None
        e0, h = d["e0"], d["h"]

        def rechazado(ident, tipo, texto):
            antes, n = self.estado(e), len(e.ed.undo_stack)
            e.parpadeo.parar()
            e.mensaje = ""
            e.cambiar_tipo_etapa(ident, tipo)
            self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n), (ident, tipo))
            self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje), e.mensaje)
            self.assertIn(texto, e.mensaje)
            self.assertEqual(e.parpadeo.ids, {ident})
            e.parpadeo.parar()
        rechazado(e0, "macro", "recinto")
        rechazado(e0, "ordinary", "recinto")
        e.tipo_etapa(h, True)
        rechazado(h, "macro", "inicial")
        e.tipo_etapa(h, False)
        # macroetapa con contenido: una etapa dentro de su expansión
        mid = e.poner_macro(QPointF(260, 520))
        x = e.ed.macro_info(mid)
        rechazado(x.entry, "macro", "expansión")
        rechazado(x.exit, "ordinary", "expansión")
        e.ed.add_step(x.partial, "Dentro")
        e.cambia()
        rechazado(mid, "ordinary", "vacíe la expansión antes")
        rechazado(mid, "enclosing", "vacíe la expansión antes")
        # una etapa con una acción: lo que decide es la validación del modelo (se deshace con su diagnóstico)
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(h, {"tipo": "continua", "variable": "Q00"}))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.mensaje = ""
        e.cambiar_tipo_etapa(h, "macro")
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue(e.mensaje and not e.mensaje_info, e.mensaje)

    def test_SMTP23_macroetapa_por_conversion_se_guarda_y_se_abre_y_simula_como_la_de_la_ficha(self):
        """REQ-JER-04, REQ-DAT-01, REQ-EDT-08: la macroetapa que sale de convertir una etapa desde el menú tiene la
        misma forma que la de la ficha «Macroetapa» (expansión con su entrada y su salida, a la derecha) y se
        guarda y se abre sin pérdida."""
        w, e = self.vacio()
        e.pedir_accion = lambda *a: None
        s = e.poner_etapa(QPointF(260, 80))
        e.renombrar(s, "M1")
        self.submenu(e.menu(centro(e.M, s)), "Tipo de etapa")["Macroetapa"][0]()
        w2, e2 = self.vacio()
        mid = e2.poner_macro(QPointF(260, 80))
        e2.renombrar(mid, "M1")
        a, b = forma(e.ed), forma(e2.ed)
        for clave in ("macros", "parciales"):
            self.assertEqual(a[clave], b[clave], clave)
        self.assertEqual(sorted(x[:3] for x in a["etapas"]), sorted(x[:3] for x in b["etapas"]))
        self.assertEqual(sorted(a["sitios"]), sorted(b["sitios"]))
        with tempfile.TemporaryDirectory() as tmp:
            pj = new_project("proy", "Macroetapa por conversión")
            add_document(pj, e.ed.model)
            add_document(pj, e.ed.presentation)
            save_project(Path(tmp), pj)
            op = open_model(Path(tmp))
        self.assertEqual((op.doc, op.presentations[0]), (e.ed.model, e.ed.presentation))


if __name__ == "__main__":
    unittest.main()
