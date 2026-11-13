"""Editor de escritorio (P-IMP-32, paso 3): crear un grafcet secuencial con el ratón, enlazarlo, moverlo, borrarlo,
deshacer, guardarlo, abrirlo y simularlo.

Las pruebas del núcleo (S-EDI01..02) no necesitan Qt. Las de la interfaz (S-EDI03..20) se omiten si PySide6 no está
instalado y usan la plataforma «offscreen»: no abren ventanas ni diálogos (los ganchos y los mensajes se sustituyen).
Ninguna es oráculo del documento 11: comprueban que el editor usa las operaciones de grafcet/editor.py y que lo
que se dibuja y se simula es lo que decide el núcleo.
"""
from helpers_grafnet import fixture_grafnet
import copy
import json
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from grafcet.diagnostics import DiagnosticError  # noqa: E402
from grafcet.editor import Editor, new_grafcet_document  # noqa: E402
from grafcet.persistence import open_model  # noqa: E402
from grafcet.notation import a_nucleo, a_usuario, etapas_ambiguas, normalizar_espacios  # noqa: E402
from grafcet.profile import normalize_options  # noqa: E402
from grafcet.view import Vista, layout_from_presentation  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path("C:/Windows/Fonts").is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRectF, QSettings, Qt
    from PySide6.QtGui import QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    QT = True
except ImportError:
    QT = False


class Nucleo(unittest.TestCase):
    def test_SEDI01_parcial_raiz_etiquetas_y_agrupar(self):
        """REQ-EDT-02, REQ-EDT-03: el grafcet nuevo tiene el parcial raíz «g»; las etiquetas nuevas son 0, 1… (solo el
        número) y t1..; varias operaciones agrupadas se deshacen y se rehacen de una vez."""
        ed = Editor(new_grafcet_document("m"))
        self.assertEqual([p["id"] for p in ed.model["partials"]], ["g"])
        self.assertEqual((ed.next_label("step"), ed.next_label("transition")), ("0", "t1"))
        with ed.group("dos etapas"):
            ed.add_step("g", "0", True, at=(0, 60))
            ed.add_step("g", "1", at=(0, 220))
        self.assertEqual(len(ed.undo_stack), 1)
        self.assertEqual(ed.next_label("step"), "2")
        t, _ = ed.add_transition("g", "", label=ed.next_label("transition"))
        self.assertEqual(ed.get(t)["label"], "t1")
        self.assertEqual(ed.next_label("transition"), "t2")
        ed.undo()
        ed.undo()
        self.assertEqual(ed.model["steps"], [])
        ed.redo()
        self.assertEqual(len(ed.model["steps"]), 2)
        with self.assertRaises(DiagnosticError):
            ed.add_transition("g", "", label="")

    def test_SEDI02_comprobar_receptividad_sin_cambiar_el_modelo(self):
        """REQ-EDT-09: un texto mal escrito se diagnostica sin tocar el modelo; las variables que faltan se listan."""
        ed = Editor(new_grafcet_document("m"))
        ed.add_variable("marcha", "input", {"kind": "bool"})
        antes = ed.revision
        self.assertIsNone(ed.check_expression("marcha", "g"))
        self.assertEqual(ed.check_expression("marcha AND", "g").code, "D-EXP-PENDIENTE")
        self.assertEqual(ed.check_expression("marcha AND paro", "g").code, "D-EXP-PENDIENTE")
        self.assertEqual(ed.undeclared_variables("marcha AND paro AND otra", "g"), ["paro", "otra"])
        self.assertEqual(ed.undeclared_variables("marcha AND", "g"), [], "con error de sintaxis no se ofrece crear nada")
        self.assertEqual((ed.revision, ed.model["expressions"]), (antes, []))

    def test_SEDI98_acciones_sueltas_en_grupo_en_el_nucleo(self):
        """REQ-ACT-01, REQ-DAT-01: el editor guarda en `presentation.draftActions` los grupos de acciones sueltas (`grupo`,
        `orden`) y su colocación en `actionLayouts`; `update_draft_actions` cambia varias a la vez en una operación; un
        grupo con menos de dos miembros se disuelve; borrar una etapa deja sus acciones sin completar juntas; solo
        presentación: la revisión semántica no cambia."""
        ed = Editor(new_grafcet_document("m"))
        s0 = ed.add_step("g", "0", True)
        revision = ed.revision
        self.assertIn("condicionada", Editor.DRAFT_TIPOS)
        a = ed.add_draft_action((10, 20), {"tipo": "condicionada"})
        b = ed.add_draft_action((10, 20), {"grupo": "k1", "orden": 1})
        c = ed.add_draft_action((10, 20), {"grupo": "k1", "orden": 0, "tipo": "evento"})
        self.assertEqual([d.get("grupo") for d in ed.draft_actions()], [None, "k1", "k1"])
        with self.assertRaises(DiagnosticError):
            ed.add_draft_action((0, 0), {"grupo": 3})
        with self.assertRaises(DiagnosticError):
            ed.add_draft_action((0, 0), {"orden": "x"})
        with self.assertRaises(DiagnosticError):
            ed.add_draft_action((0, 0), {"orden": True})
        n = len(ed.undo_stack)
        ed.update_draft_actions({a: {"grupo": "k1", "orden": 2, "x": 40, "y": 60}, b: {"x": 40, "y": 60}})
        self.assertEqual(len(ed.undo_stack), n + 1, "una operación")
        self.assertEqual([(d["x"], d["y"]) for d in ed.draft_actions()], [("40", "60"), ("40", "60"), ("10", "20")])
        # una colocación para el grupo y para la etapa; un identificador que no es ni una cosa ni la otra no vale
        ed.set_action_layout("k1", "columna")
        ed.set_action_layout(s0, "fila-separada")
        self.assertEqual(ed.action_layouts(), {"k1": "columna", s0: "fila-separada"})
        with self.assertRaises(DiagnosticError):
            ed.set_action_layout("k9", "columna")
        # con un solo miembro, el grupo se disuelve y su colocación se olvida
        ed.delete_draft_actions([a, b])
        self.assertEqual(ed.draft_actions(), [{"id": c, "x": "10", "y": "20", "tipo": "evento"}])
        self.assertEqual(ed.action_layouts(), {s0: "fila-separada"})
        ed.undo()
        self.assertEqual((len(ed.draft_actions()), ed.action_layouts()), (3, {"k1": "columna", s0: "fila-separada"}))
        ed.redo()
        # unir a una etapa manda la etapa: el grupo desaparece
        d = ed.add_draft_action((0, 0), {"grupo": "k2", "orden": 0})
        e2 = ed.add_draft_action((0, 0), {"grupo": "k2", "orden": 1})
        ed.update_draft_actions({d: {"etapa": s0, "grupo": None}, e2: {"etapa": s0, "grupo": None}})
        self.assertEqual([x.get("grupo") for x in ed.draft_actions()], [None, None, None])
        # borrar la etapa: sus acciones sin completar quedan juntas (un grupo) y con la colocación que tenían
        ed.update_draft_actions({d: {"orden": 1}, e2: {"orden": 0}})
        ed.delete([s0])
        resto = ed.draft_actions()
        self.assertTrue(all("etapa" not in x for x in resto))
        sueltas = [x for x in resto if x["id"] in (d, e2)]
        gid = sueltas[0]["grupo"]
        self.assertTrue(gid and all(x["grupo"] == gid for x in sueltas))
        self.assertEqual(sorted(sueltas, key=lambda x: x["orden"])[0]["id"], e2, "conservan su orden")
        self.assertEqual(ed.action_layouts(), {gid: "fila-separada"}, "y su colocación, ahora la del grupo")
        self.assertEqual(ed.revision, ed.revision)
        self.assertTrue(ed.validate().can_simulate)
        # presentación: ninguna operación de grupos cambia el modelo
        ed2 = Editor(new_grafcet_document("m2"))
        ed2.add_step("g", "0", True)
        rev = ed2.revision
        x1 = ed2.add_draft_action((0, 0))
        x2 = ed2.add_draft_action((0, 0))
        ed2.update_draft_actions({x1: {"grupo": "k", "orden": 0}, x2: {"grupo": "k", "orden": 1}})
        ed2.set_action_layout("k", "columna")
        self.assertEqual(ed2.revision, rev)


class Notacion(unittest.TestCase):
    def test_SEDI39_acciones_y_variables_en_el_nucleo(self):
        """REQ-EDT-07, REQ-ACT-01: una acción se cambia de arriba abajo conservando su ID y su lugar, se ordena y se quita
        sola (sin dejar referencias); una variable usada no se quita y una sin usos sí; todo se deshace."""
        ed = Editor(new_grafcet_document("m"))
        s0 = ed.add_step("g", "0", True)
        q = ed.add_variable("Q00", "output", {"kind": "bool"})
        ct = ed.add_variable("CT", "internal", {"kind": "int"})
        i2 = ed.add_variable("I02", "input", {"kind": "bool"})
        a1 = ed.add_continuous_action(s0, q)
        a2 = ed.add_stored_action(s0, ct, "activation", "CT + 1")
        n = len(ed.undo_stack)
        ed.update_action(a2, ct, "stored", trigger="event", value="CT + 1", event="rise(I02)")
        a = ed.get(a2)
        self.assertEqual((a["trigger"]["kind"], ed.get(s0)["actionRefs"]), ("event", [a1, a2]))
        self.assertEqual(len(ed.model["expressions"]), 3, "las expresiones de antes se retiran")
        self.assertTrue(ed.validate().can_simulate)
        with self.assertRaises(DiagnosticError):
            ed.update_action(a2, ct, "stored", trigger="event", value="CT + 1")  # evento sin expresión
        ed.move_action(a2, -1)
        self.assertEqual(ed.get(s0)["actionRefs"], [a2, a1])
        with self.assertRaises(DiagnosticError):
            ed.delete_variable(ct)  # objetivo de una acción y usada en su valor
        ed.delete([a2])
        self.assertEqual(ed.get(s0)["actionRefs"], [a1])
        self.assertTrue(ed.validate().can_simulate)
        ed.delete_variable(i2)
        self.assertEqual([v["name"] for v in ed.model["variables"]], ["Q00", "CT"])
        while len(ed.undo_stack) > n:
            ed.undo()
        self.assertEqual(ed.get(a2)["trigger"]["kind"], "activation")
        self.assertEqual(len(ed.model["variables"]), 3)

    def test_SEDI16_notacion_del_usuario(self):
        """REQ-EDT-02: ↑a, ↓a y X1 se traducen a la sintaxis del núcleo y vuelven; los espacios se ignoran al escribir y
        se normalizan siempre; el analizador no cambia."""
        et, va = ["E0", "E1", "Marcha"], ["marcha", "X7"]
        self.assertEqual(a_nucleo("↑marcha", et, va), "rise(marcha)")
        self.assertEqual(a_nucleo("↓ (marcha AND  X1)", et, va), "fall(marcha AND active(E1))")
        self.assertEqual(a_nucleo("NOT ↑a OR X0", et, va), "NOT rise(a) OR active(E0)")
        self.assertEqual(a_nucleo("X7 AND X1", et, va), "X7 AND active(E1)", "X7 es una variable: no se toca")
        self.assertEqual(a_nucleo("X9", et, va), "X9", "sin etapa E9, se deja")
        self.assertEqual(a_nucleo("↑↓a", et, va), "rise(fall(a))")
        self.assertEqual(a_usuario("rise(marcha) AND NOT fall(active(E1))"), "↑marcha AND NOT ↓X1")
        self.assertEqual(a_usuario("fall(a AND b)"), "↓(a AND b)")
        # Los retardos se escriben como en la norma: 3s/X1, X1/2s, 3s/NOT marcha/2s (los 0 s no se escriben)
        self.assertEqual(a_usuario("delay(3 s, active(E1), 0 s)"), "3s/X1")
        self.assertEqual(a_usuario("delay(0 s, active(E1), 2 s)"), "X1/2s")
        self.assertEqual(a_nucleo("3s/X1", et, va), "delay(3 s, active(E1), 0 s)")
        self.assertEqual(a_nucleo("X1/2s", et, va), "delay(0 s, active(E1), 2 s)")
        self.assertEqual(a_nucleo("3 s / NOT marcha / 2 s", et, va), "delay(3 s, NOT marcha, 2 s)")
        self.assertEqual(a_nucleo("1,5s/↑marcha AND paro", et, va), "delay(1.5 s, rise(marcha), 0 s) AND paro")
        self.assertEqual(a_usuario("delay(2 s, a AND b, 0 s)"), "2s/(a AND b)")
        self.assertEqual(a_usuario("delay(0 s, a, 0 s)"), "delay(0 s, a, 0 s)", "sin tiempos, no hay nada que abreviar")
        for t in ("marcha AND NOT paro", "↑marcha", "↓(a OR b)", "X0 AND X1", "3s/X1", "3s/NOT marcha/2s", "X1/2s",
                  "3s/(a AND b)", "marcha AND 3s/↑paro"):
            self.assertEqual(a_usuario(a_nucleo(t, et, va)), t, t)
        self.assertEqual(normalizar_espacios("  a   AND ( b ,c )  "), "a AND (b,c)")
        ed = Editor(new_grafcet_document("m"))
        ed.add_variable("marcha", "input", {"kind": "bool"})
        ed.add_step("g", "E1")
        self.assertIsNone(ed.check_expression(a_nucleo("↑marcha AND X1", ["E1"], ["marcha"]), "g"))

    def test_SEDI45_constantes_1_y_0(self):
        """REQ-EDT-02: en la notación del usuario se ve 1 y 0 y se guarda true y false, solo como operando booleano
        completo; CT = 1 y las cuentas quedan numéricas."""
        self.assertEqual(a_nucleo("1"), "true")
        self.assertEqual(a_nucleo("NOT 0"), "NOT false")
        self.assertEqual(a_nucleo("a AND 1 OR (0)"), "a AND true OR (false)")
        self.assertEqual(a_nucleo("↑1"), "rise(true)")
        self.assertEqual(a_nucleo("3s/1"), "delay(3 s, true, 0 s)")
        for t in ("CT = 1", "CT + 1 > 3", "1 < CT", "CT <> 0", "1s/a", "1,5s/a", "1.5 s/a"):
            self.assertNotIn("true", a_nucleo(t), t)
            self.assertNotIn("false", a_nucleo(t), t)
        self.assertEqual(a_nucleo("n + 1", booleana=False), "n + 1")
        self.assertEqual(a_nucleo("1", booleana=False), "1", "un valor numérico no se vuelve true")
        self.assertEqual(a_usuario("true AND NOT false"), "1 AND NOT 0")
        for t in ("1", "0", "a AND 1", "NOT 0", "CT = 1", "CT + 1 > 3", "1 < CT", "3s/X1", "3s/1"):
            self.assertEqual(a_usuario(a_nucleo(t, ["E1"], [])), t, t)
        # los paréntesis que rodean al literal son transparentes; junto a una comparación o una cuenta, numérico
        for t in ("CT > (1)", "CT * (1) > 3", "CT + (1) > 3", "CT > 6/1", "(1) = m"):
            self.assertEqual(a_nucleo(t), t, t)
        self.assertEqual(a_nucleo("↑(1)"), "rise(true)")
        self.assertEqual(a_nucleo("a OR (0)"), "a OR (false)")
        self.assertEqual(a_nucleo("3s/1/2s"), "delay(3 s, true, 2 s)")
        self.assertEqual(a_nucleo("rise(1)"), "rise(1)", "la llamada no es un grupo")
        # en una comparación booleana, true y false quedan; ida y vuelta en los dos sentidos
        for t in ("m = true", "true = m", "m != false", "(m) = true", "↑1", "CT > (1)", "CT > 6/1", "a AND 1"):
            n = a_nucleo(t, [], ["m", "a", "CT"])
            self.assertEqual(a_usuario(n), t, t)
            self.assertEqual(a_nucleo(a_usuario(n), [], ["m", "a", "CT"]), n, t)
        self.assertEqual(a_usuario("(true) = m"), "(true) = m")

    def test_SEDI46_retardo_con_parentesis_anidados(self):
        """REQ-EDT-02, REQ-TMP-01: la condición de un retardo puede llevar paréntesis anidados (3s/(a AND (b OR c)),
        (…)/2s, 3s/(…)/2s) y vuelve igual al mostrarla."""
        self.assertEqual(a_nucleo("3s/(a AND (b OR c))"), "delay(3 s, (a AND (b OR c)), 0 s)")
        self.assertEqual(a_nucleo("(a AND (b OR c))/2s"), "delay(0 s, (a AND (b OR c)), 2 s)")
        self.assertEqual(a_nucleo("3s/(a AND (b OR (c AND d)))/2s"), "delay(3 s, (a AND (b OR (c AND d))), 2 s)")
        self.assertEqual(a_nucleo("x AND 3s/(a AND (b OR c))"), "x AND delay(3 s, (a AND (b OR c)), 0 s)")
        for t in ("3s/(a AND (b OR c))", "(a AND (b OR c))/2s", "3s/(a AND (b OR c))/2s", "3s/NOT ↑a/2s",
                  "3s/(3s/a/2s)", "(1s/a)/2s"):
            self.assertEqual(a_usuario(a_nucleo(t)), t, t)
        self.assertEqual(a_nucleo("3s/(3s/a/2s)"), "delay(3 s, (delay(3 s, a, 2 s)), 0 s)", "el interior también se traduce")
        ed = Editor(new_grafcet_document("m"))
        for n in "abc":
            ed.add_variable(n, "input", {"kind": "bool"})
        self.assertIsNone(ed.check_expression(a_nucleo("3s/(a AND (b OR c))"), None))

    def test_SEDI47_aviso_de_x1_ambiguo(self):
        """REQ-EDT-02: si existen la etapa E1 y la etapa 1, X1 se sigue resolviendo a E1, pero se señala que podría ser
        la otra."""
        et = ["E0", "E1", "1"]
        self.assertEqual(a_nucleo("X1", et), "active(E1)")
        self.assertEqual(etapas_ambiguas("X1 AND X0 AND ↑X1", et, []), ["X1"])
        self.assertEqual(etapas_ambiguas("X1", ["E1"], []), [])
        self.assertEqual(etapas_ambiguas("X1", et, ["X1"]), [], "una variable X1 manda")
        self.assertEqual(etapas_ambiguas("active(`1`)", et, []), [])


def centro(M, ident):
    from escritorio.diagrama import posiciones
    return QPointF(*posiciones(M)[ident])


def centro_caja(w, aid):
    """El centro de la caja de una acción en el dibujo."""
    x, y, ancho, alto = next(c for c in w.diagrama.cajas_acciones if c["id"] == aid)["rect"]
    return QPointF(x + ancho / 2, y + alto / 2)


def QRectF_de(r):  # noqa: N802
    from PySide6.QtCore import QRectF
    return QRectF(*r)


def QRectF_contiene(r, p):  # noqa: N802
    return QRectF_de(r).contains(p)


COL_ERR = "#c62828"  # el rojo de los errores en el dibujo (escritorio.diagrama.COL["err"])


def posiciones_modelo(e):
    """Las posiciones de la presentación de lo que se edita."""
    return layout_from_presentation(e.ed.presentation)


@unittest.skipUnless(QT, "PySide6 no está instalado")
class Interfaz(unittest.TestCase):
    def proyecto_fixture(self,clave):
        """Proyecto editable construido por la prueba; los ejemplos del menú no se editan."""
        from grafcet.examples import EJEMPLOS
        from escritorio.edicion import Edicion
        titulo,_,crear=EJEMPLOS[clave];m,layout=crear()
        self.w._establecer_edicion(Edicion.desde(m.doc,layout,titulo))
        self.w.fuente={'tipo':'editor'};self.w._cargar()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from escritorio.ventana import Ventana
        self.w = Ventana(QSettings(str(Path(self.tmp.name) / "a.ini"), QSettings.Format.IniFormat))

    def tearDown(self):
        self.w.a_ejecutar.setChecked(False)
        self.w.edicion = None  # sin preguntar al cerrar
        self.w.deleteLater()
        self.tmp.cleanup()

    def soltar_ficha(self, tipo, p, w=None):
        """Suelta una ficha de la paleta en el punto p del dibujo (el evento que genera Qt al terminar el arrastre)."""
        w = w or self.w
        mime = QMimeData()
        mime.setText(tipo)
        w.diagrama.dropEvent(QDropEvent(QPointF(w.diagrama.mapFromScene(p)), Qt.DropAction.CopyAction, mime,
                                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))

    def panel_accion(self, sid, aid=None):
        """Abre las opciones de una acción en el panel inferior y devuelve su panel (`w.props.accion`): sin `aid`, con
        «Añadir…» (una acción continua nueva unida a la etapa, sin variable); con él, como «Editar…»."""
        w, e = self.w, self.w.edicion
        if aid is None:
            e.anadir_accion(sid)
        else:
            w.editar_accion(sid, aid)
        return w.props.accion

    @staticmethod
    def poner_tipo(d, tipo):
        """Cambia el tipo de la acción como lo hace el usuario: botón derecho sobre ella, «Tipo de acción» (el panel de
        opciones ya no tiene lista de tipos, P-IMP-46)."""
        d.e.tipo_accion(d.aid, tipo)

    def anadir_accion(self, sid, tipo="continua", variable="", valor=""):
        """Lo que hacía el diálogo «Añadir acción»: «Añadir…» y luego, en el panel, tipo, variable y valor (cada campo se
        aplica al momento). Devuelve el panel."""
        a = self.panel_accion(sid)
        if tipo != "continua":
            self.poner_tipo(a, tipo)
        if variable:
            a.variable.setCurrentText(variable)
        if valor:
            a._desde_bloques(valor)
        return a

    # -- el grafcet de la validación: E0 -marcha-> E1 -paro-> E0 ---------------------------------------
    def secuencial(self, w=None):
        """Lo construye con los gestos del ratón sobre el controlador: etapa inicial, transición, etapa..."""
        w = w or self.w
        w.nuevo()
        e = w.edicion

        def clic(h, x, y):  # soltar la ficha de la paleta en el dibujo (los elementos solo se colocan arrastrando)
            e.colocar(h, QPointF(100 + x, y))

        def enlace(a, b):
            """Del punto de abajo de a al punto de arriba de b (los dos con el ratón)."""
            from escritorio.diagrama import anclas
            pa = next(x for x in anclas(e.M, a) if x["lado"] == "abajo")["pos"]
            pb = next(x for x in anclas(e.M, b) if x["lado"] == "arriba")["pos"]
            e.herramienta = "seleccionar"
            e.prensar(pa)
            e.mover(pb)
            e.soltar(pb)
        clic("etapa", 0, 60)
        e.tipo_etapa(e.M["steps"][0]["id"], True)  # una etapa es una etapa: inicial se elige en sus opciones
        clic("transicion", 0, 140)
        clic("etapa", 0, 220)
        clic("transicion", 0, 300)
        ids = {s["label"]: s["id"] for s in e.M["steps"]}
        ts = {t["label"]: t["id"] for t in e.M["transitions"]}
        self.assertEqual(len(e.ed.validate().diagnostics) > 0, True, "una transición nueva queda pendiente, sin pedir nada")
        e.poner_condicion(ts["t1"], "marcha", crear=True)
        e.poner_condicion(ts["t2"], "paro", crear=True)
        enlace(ids["0"], ts["t1"])
        enlace(ts["t1"], ids["1"])
        enlace(ids["1"], ts["t2"])
        enlace(ts["t2"], ids["0"])
        return e, ids, ts

    def test_SEDI03_crear_enlazar_y_simular(self):
        """REQ-EDT-01, REQ-EDT-02, REQ-EDT-14: E0 (inicial) → t1 «marcha» → E1 → t2 «paro» → E0 se crea con el ratón,
        se valida, se simula (cada vez, una ejecución nueva) y vuelve a Editar."""
        w = self.w
        e, ids, ts = self.secuencial()
        self.assertEqual(sorted(ids), ["0", "1"])
        self.assertEqual(sorted(ts), ["t1", "t2"])
        self.assertTrue(e.ed.validate().can_simulate, [str(d) for d in e.ed.validate().diagnostics])
        t1 = next(t for t in e.M["transitions"] if t["label"] == "t1")
        self.assertEqual(t1["cond"], [{"t": "marcha", "eval": [t1["conditionRef"]]}])
        self.assertEqual(e.ed.get(ids["0"])["initial"], True)
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.modo, "simular")
        self.assertEqual(w.v.state()["situation"], [ids["0"]])
        self.assertEqual(sorted(w.botones.values(), key=lambda b: b.text())[0].text(), "marcha = 0")
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w._cambiar_tipo_entrada(nombre["marcha"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["marcha"]].click()
        self.assertEqual(w.v.state()["situation"], [ids["1"]])
        w._cambiar_tipo_entrada(nombre["marcha"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["marcha"]].click()  # se suelta: con marcha y paro a 1, E0 y E1 se alternarían sin fin
        w._cambiar_tipo_entrada(nombre["paro"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["paro"]].click()
        self.assertEqual(w.v.state()["situation"], [ids["0"]])
        # Editar y simular otra vez: ejecución nueva, desde la situación inicial
        w._cambiar_tipo_entrada(nombre["marcha"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["marcha"]].click()
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual((w.modo, w.derecho.currentIndex()), ("editar", 1))
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.v.state()["situation"], [ids["0"]])

    def test_SEDI04_guardar_abrir_y_simular(self):
        """REQ-EDT-01, REQ-DAT-02: el grafcet creado se guarda como proyecto, se abre y simula igual; en Editar se
        recupera con sus posiciones."""
        w = self.w
        e, ids, ts = self.secuencial()
        e.ed.move(ids["1"], 240, 220)
        e.cambia()
        dest = Path(self.tmp.name) / "mi-grafcet"
        with mock.patch("escritorio.ventana.QFileDialog.getSaveFileName", return_value=(str(dest)+".grafnet","")):
            self.assertTrue(w.guardar())
        self.assertFalse(e.ed.dirty)
        dest = e.archivo
        self.assertTrue(dest.is_file())
        self.assertTrue((e.ruta / "manifest.json").exists())
        op = open_model(e.ruta)
        self.assertTrue(op.executable)
        self.assertEqual(layout_from_presentation(op.presentations[0])[ids["1"]], (240.0, 220.0))
        self.assertTrue(w.abrir_ruta(fixture_grafnet(dest)))
        self.assertEqual(w.v.state().get("situation", []), [], "abrir deja Pausa sin estado")
        self.assertTrue(w.cambiar_modo("simular"))  # Play arranca la sesión desde la situación inicial
        self.assertEqual(w.v.state()["situation"], [ids["0"]])
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w._cambiar_tipo_entrada(nombre["marcha"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["marcha"]].click()
        self.assertEqual(w.v.state()["situation"], [ids["1"]])
        # Editar el modelo abierto: copia con sus posiciones y, al guardar, en su misma carpeta
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual(w.edicion.archivo, dest)
        self.assertEqual(w.edicion.layout()[ids["1"]], (240.0, 220.0))

    def test_SEDI05_deshacer_rehacer_mover_y_borrar(self):
        """REQ-EDT-01, REQ-EDT-05: un arrastre es una sola operación de deshacer; borrar avisa de lo que arrastra y se
        deshace; el panel de diagnósticos lleva al elemento."""
        w = self.w
        e, ids, ts = self.secuencial()
        n = len(e.ed.undo_stack)
        e.herramienta = "seleccionar"
        p = centro(e.M, ids["1"])
        e.prensar(p)
        for k in (1, 2, 3, 4):  # varios movimientos, una sola operación
            e.mover(QPointF(p.x() + 13 * k, p.y() + 7 * k))
        e.soltar(QPointF(p.x() + 52, p.y() + 28))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertEqual(e.layout()[ids["1"]], (60.0, 240.0), "a la rejilla de 20")
        e.deshacer()
        self.assertEqual(e.layout()[ids["1"]], (0.0, 220.0))
        e.rehacer()
        self.assertEqual(e.layout()[ids["1"]], (60.0, 240.0))
        # Borrar E1 avisa de las transiciones que quedan sin enlace
        avisos = []
        e.confirmar_borrado = lambda plan: avisos.append(plan) or False
        e.seleccionar([ids["1"]])
        self.assertFalse(e.borrar())
        self.assertEqual(avisos[0]["affectedTransitions"], sorted(ts.values()))
        self.assertEqual(len(e.M["steps"]), 2)
        e.confirmar_borrado = lambda plan: True
        self.assertTrue(e.borrar())
        self.assertEqual([s["label"] for s in e.M["steps"]], ["0"])
        e.deshacer()
        self.assertEqual(sorted(s["label"] for s in e.M["steps"]), ["0", "1"])
        self.assertTrue(e.ed.validate().can_simulate, "deshacer devuelve también los enlaces")

    def test_SEDI06_receptividad_mal_escrita_y_diagnosticos(self):
        """REQ-EDT-09: una receptividad que no se interpreta se conserva como texto, se diagnostica con su corrección,
        marca la transición y no deja simular; el clic en el diagnóstico la selecciona."""
        w = self.w
        e, ids, ts = self.secuencial()
        diag = e.poner_condicion(ts["t1"], "marcha AND")
        self.assertEqual(diag.code, "D-EXP-PENDIENTE")
        ds = [d for d in e.diagnosticos() if d["blocks"]]
        self.assertEqual([d["target"] for d in ds], [ts["t1"]])
        self.assertIn("completar", ds[0]["correction"].lower())
        self.assertEqual(e.marcados(), {ts["t1"]})
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertFalse(w.cambiar_modo("simular"))
        self.assertIn("Receptividades vacías o con errores de sintaxis: t1", aviso.call_args.args[2])
        self.assertEqual(w.modo, "editar", "no simula: sigue en Editar")
        w.refrescar_edicion()
        self.assertEqual(w.lista_diag.count(), 1)
        e.seleccionar([])
        w._ir_a_diagnostico(w.lista_diag.item(0))
        self.assertEqual(e.sel, [ts["t1"]])
        self.assertEqual(w.l_resumen.text(), "No se puede simular: 1 error")
        e.poner_condicion(ts["t1"], "marcha")
        self.assertTrue(w.cambiar_modo("simular"))

    def test_SEDI07_enlaces_en_borrador_y_añadir_debajo(self):
        """REQ-MOD-03: dos elementos del mismo tipo quedan como borrador con su diagnóstico; «añadir debajo» crea
        transición y etapa enlazadas en una sola operación."""
        e, ids, ts = self.secuencial()
        from escritorio.diagrama import anclas

        def punto(i, lado):
            return next(x for x in anclas(e.M, i) if x["lado"] == lado)["pos"]
        e.herramienta = "seleccionar"
        e.conectar(ids["0"], ids["1"])  # (arrastrar de una etapa a otra ya crea una transición en medio: ver test_aula)
        self.assertEqual(len(e.M["drafts"]), 1)
        self.assertIn("dos elementos del mismo tipo", e.mensaje)
        self.assertNotIn("D-ALTERNANCIA", e.mensaje)
        self.assertIn("D-ALTERNANCIA", [d["code"] for d in e.diagnosticos()])
        e.seleccionar([e.M["drafts"][0]["id"]])
        self.assertTrue(e.borrar())
        self.assertEqual(e.M["drafts"], [])
        # Enlace duplicado: se rechaza con su motivo
        e.prensar(punto(ids["0"], "abajo"))
        e.soltar(punto(ts["t1"], "arriba"))
        self.assertIn("duplicado", e.mensaje)
        # Una segunda etapa en la misma transición sería una simultaneidad: no se hace por accidente
        e.prensar(punto(ids["1"], "abajo"))
        e.soltar(punto(ts["t1"], "arriba"))
        self.assertIn("simultaneidad", e.mensaje)
        self.assertEqual(next(t for t in e.M["transitions"] if t["id"] == ts["t1"])["pre"], [ids["0"]])
        # Añadir debajo
        pedidas = []
        e.pedir_condicion = pedidas.append  # pide la receptividad de la transición nueva, que es otra operación
        e.seleccionar([ids["1"]])
        n = len(e.ed.undo_stack)
        nuevo = e.anadir_debajo()
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertEqual(len(pedidas), 0, "añadir debajo no pide receptividad")
        self.assertEqual((len(e.M["steps"]), len(e.M["transitions"])), (3, 3))
        t3 = next(t for t in e.M["transitions"] if t["label"] == "t3")
        self.assertEqual((t3["pre"], t3["post"]), ([ids["1"]], [nuevo]))
        e.deshacer()
        self.assertEqual((len(e.M["steps"]), len(e.M["transitions"])), (2, 2))

    def test_SEDI08_etiquetas_y_cambios_sin_guardar(self):
        """REQ-EDT-01, REQ-EDT-06: renombrar una etapa conserva su identidad y actualiza el dibujo; con cambios sin
        guardar, abrir otro modelo o cerrar pregunta."""
        w = self.w
        e, ids, ts = self.secuencial()
        self.assertIsNone(e.renombrar(ids["1"], "0"))  # P-IMP-118: un número repetido se admite, y se marca como error
        self.assertTrue(any(d["code"] == "D-NOMBRE-COLISION" and d["blocks"] for d in e.diagnosticos()))
        self.assertIsNone(e.renombrar(ids["1"], "Marc"))  # (una etapa admite 4 caracteres como máximo: más no cabe en su cuadro)
        self.assertIsNotNone(e.renombrar(ids["1"], "Marcha"))
        self.assertEqual({s["id"]: s["label"] for s in e.M["steps"]}[ids["1"]], "Marc")
        self.assertTrue(e.ed.dirty)
        pregunta = mock.patch("escritorio.ventana.QMessageBox.question", return_value=mock.sentinel.cancelar)
        from PySide6.QtWidgets import QMessageBox
        with mock.patch("escritorio.ventana.QMessageBox.question", return_value=QMessageBox.StandardButton.Cancel) as q:
            w.cargar_ejemplo("temporizada")
            self.assertEqual(q.call_count, 1)
            self.assertIs(w.edicion, e, "cancelar conserva lo editado")
            self.assertFalse(w._salir_de_edicion())
        with mock.patch("escritorio.ventana.QMessageBox.question", return_value=QMessageBox.StandardButton.Discard):
            w.cargar_ejemplo("temporizada")
        self.assertIsNot(w.edicion, e, "descartar abre el ejemplo de consulta")
        self.assertFalse(w.edicion.ed.dirty)
        self.assertEqual((w.modo, w.v.key, w.a_ejecutar.isChecked()), ("editar", "temporizada", False), "al abrir: Pausa")
        del pregunta


    def test_SEDI10_el_ratón_real_y_el_dibujo(self):
        """REQ-EDT-02, REQ-EDT-03: los clics del ratón sobre el dibujo llegan al editor; la selección y las marcas se
        dibujan; el dibujo del editor es el de la simulación (mismos textos)."""
        w = self.w
        w.nuevo()
        e, d = w.edicion, w.diagrama
        self.assertIs(d.controlador, e)
        self.assertEqual((d.dragMode(), d.rejilla), (d.DragMode.NoDrag, True))
        self.soltar_ficha("etapa", QPointF(213, 97))
        self.assertEqual([(s["label"], s["x"], s["y"]) for s in e.M["steps"]], [("0", 120.0, 100.0)])
        QTest.mouseClick(d.viewport(), Qt.MouseButton.LeftButton, pos=d.mapFromScene(QPointF(220, 100)))
        self.assertEqual(e.sel, [e.M["steps"][0]["id"]])
        textos = [it.toPlainText() for it in d.scene().items() if hasattr(it, "toPlainText")]
        self.assertIn("0", textos)
        from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsPathItem
        self.assertTrue([it for it in d.scene().items() if it.zValue() >= 10], "la selección y sus tiradores se dibujan")
        # Doble clic sobre la etapa: pide su etiqueta
        pedidas = []
        e.pedir_etiqueta = pedidas.append
        QTest.mouseDClick(d.viewport(), Qt.MouseButton.LeftButton, pos=d.mapFromScene(QPointF(220, 100)))
        self.assertEqual(pedidas, [e.sel[0]])
        # Suprimir borra la selección
        self.assertTrue(w.a_borrar.isEnabled())
        w.a_borrar.trigger()
        self.assertEqual(e.M["steps"], [])
        # Al simular, el ratón vuelve a ser el de la simulación
        w.edicion.ed.add_step("g", "A", True, at=(0, 60))
        e.cambia()
        w.cambiar_modo("simular")
        self.assertIsNone(d.controlador)
        self.assertEqual(d.dragMode(), d.DragMode.ScrollHandDrag)

    def test_SEDI11_puntos_de_union(self):
        """REQ-EDT-02: etapas y transiciones tienen puntos de unión arriba y abajo; al acercarse se marcan y del punto
        sale el enlace (el de arriba recibe, el de abajo emite)."""
        from escritorio.diagrama import H, ancla_en, anclas
        w = self.w
        e, ids, ts = self.secuencial()
        for _ in range(4):
            e.deshacer()  # quita los cuatro enlaces
        self.assertTrue(all(not t["pre"] and not t["post"] for t in e.M["transitions"]))
        c = centro(e.M, ids["0"])
        puntos = {a["lado"]: a["pos"] for a in anclas(e.M, ids["0"])}
        self.assertEqual((puntos["arriba"], puntos["abajo"]), (QPointF(c.x(), c.y() - H), QPointF(c.x(), c.y() + H)))
        self.assertEqual(ancla_en(e.M, QPointF(c.x() + 3, c.y() + H + 4))["lado"], "abajo")
        self.assertIsNone(ancla_en(e.M, c), "el centro no es un punto de unión")
        # Pasar el puntero marca los puntos del elemento
        e.pasar(QPointF(c.x() + 2, c.y() + H + 2))
        self.assertEqual(len(w.diagrama._marcas), 3, "la etapa, además, tiene su punto del centro del lado derecho")
        self.assertEqual({a["lado"] for a in anclas(e.M, ids["0"])}, {"arriba", "abajo", "der"})
        # Del punto de abajo de E0 al punto de arriba de t1: E0 -> t1
        t1 = centro(e.M, ts["t1"])
        e.herramienta = "seleccionar"
        e.prensar(QPointF(c.x(), c.y() + H))
        self.assertIsNotNone(e.enlace)
        e.mover(QPointF(t1.x(), t1.y() - 12))
        e.soltar(QPointF(t1.x(), t1.y() - 12))
        t = next(t for t in e.M["transitions"] if t["id"] == ts["t1"])
        self.assertEqual(t["pre"], [ids["0"]])
        # Del punto de arriba de E1 (que recibe) al de abajo de t1: t1 -> E1
        c1 = centro(e.M, ids["1"])
        e.prensar(QPointF(c1.x(), c1.y() - H))
        e.soltar(QPointF(t1.x(), t1.y() + 12))
        self.assertEqual(next(t for t in e.M["transitions"] if t["id"] == ts["t1"])["post"], [ids["1"]])

    def test_SEDI12_paleta_arrastrar_y_sin_pedir_receptividad(self):
        """REQ-EDT-02: los elementos de la paleta, a la izquierda, se arrastran al dibujo; una transicion se coloca sin
        pedir su receptividad."""
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDropEvent
        w = self.w
        w.nuevo()
        e, d = w.edicion, w.diagrama
        self.assertFalse(w.dock.isHidden())
        from escritorio.propiedades import NOMBRES, SECCIONES
        self.assertEqual([w.paleta.item(i).text() for i in range(w.paleta.count())],
                         [texto for titulo, claves in SECCIONES for texto in (titulo, *(NOMBRES[h] for h in claves))])
        pedidas = []
        e.pedir_condicion = pedidas.append
        self.assertEqual(w.paleta.mimeData([w.paleta.item(4)]).text(), "transicion")
        for tipo, p in (("etapa", QPointF(300, 61)), ("transicion", QPointF(300, 137)), ("etapa", QPointF(300, 222))):
            m = QMimeData()
            m.setText(tipo)
            ev = QDropEvent(QPointF(d.mapFromScene(p)), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
            d.dropEvent(ev)
        self.assertEqual([(s["label"], s["initial"], s["x"], s["y"]) for s in e.M["steps"]],
                         [("0", False, 200.0, 60.0), ("1", False, 200.0, 220.0)])
        self.assertEqual([(t["label"], t["y"]) for t in e.M["transitions"]], [("t1", 140.0)])
        self.assertEqual(pedidas, [], "no pide la receptividad")
        w.paleta.setCurrentRow(0)  # un clic en una ficha no cambia la herramienta ni coloca nada
        self.assertEqual(e.herramienta, "seleccionar")
        e.prensar(QPointF(500, 60))
        self.assertEqual((e.herramienta, len(e.M["steps"])), ("seleccionar", 2))

    def test_SEDI13_propiedades_de_la_etapa(self):
        """REQ-EDT-02: al seleccionar una etapa, el panel de la izquierda muestra su etiqueta y su tipo, editables."""
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ids["1"]])
        p = w.props
        self.assertEqual((p.pagina, p.s_etiqueta.text(), p.s_tipo.currentText()), ("etapa", "1", "Normal"))
        p.s_etiqueta.setText("Marc")
        p.s_etiqueta.editingFinished.emit()
        self.assertEqual(e.nombres[ids["1"]], "Marc")
        p.s_etiqueta.setText("0")  # ya lo tiene otra etapa: se admite y se marca como error (P-IMP-118)
        p.s_etiqueta.editingFinished.emit()
        self.assertEqual((p.msg.text(), p.s_etiqueta.text(), e.ed.get(ids["1"])["label"]), ("", "0", "0"))
        self.assertTrue(any(d["code"] == "D-NOMBRE-COLISION" and d["blocks"] for d in e.diagnosticos()))
        p.s_etiqueta.setText("Marc")
        p.s_etiqueta.editingFinished.emit()
        self.assertEqual(p.s_etiqueta.text(), "Marc")
        p.s_tipo.setCurrentIndex(1)
        p.s_tipo.activated.emit(1)
        self.assertTrue(e.ed.get(ids["1"])["initial"])
        e.seleccionar([])
        self.assertEqual(p.pagina, "vacio")

    def test_SEDI14_propiedades_de_la_transicion(self):
        """REQ-EDT-02, REQ-EDT-09: la receptividad se arma con botones, variables, comparaciones y temporizadores; lo que
        no existe se ve en naranja y se crea con un boton; la etiqueta puede ocultarse (y se guarda)."""
        from escritorio.propiedades import NARANJA
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ts["t2"]])
        p = w.props
        self.assertEqual((p.pagina, p.t_texto.text(), p.t_etiqueta.text()), ("transicion", "paro", "t2"))
        p._desde_bloques(" NOT  ↑ marcha ")  # lo que arman los bloques
        self.assertEqual(e.texto_condicion(ts["t2"]), "NOT rise(marcha)", "el núcleo guarda su sintaxis")
        self.assertEqual(p.t_texto.text(), "NOT ↑marcha", "y el panel la muestra con flechas")
        p._desde_bloques("NOT ↑marcha")
        self.assertTrue(e.ed.validate().can_simulate)
        p._previsualizar()
        self.assertIn("↑", p.t_dibujo.text())
        # Una variable que no existe, en naranja, con su boton para crearla
        p.t_texto.setText("marcha AND fin")
        p._previsualizar()
        self.assertIn(NARANJA, p.t_vista.text())
        self.assertIn(">fin</span>", p.t_vista.text())
        self.assertNotIn(">marcha</span>", p.t_vista.text())
        self.assertFalse(p.t_crear.isHidden())
        p._crear()
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["marcha", "paro", "fin"])
        self.assertTrue(e.ed.validate().can_simulate)
        p.mostrar(e)
        self.assertTrue(p.t_crear.isHidden())
        self.assertIn(("fin", "fin"), p.prog.opciones("entrada"), "el cajón de entradas")
        self.assertIn(("X1", "X1"), p.prog.opciones("etapa"), "la etapa 1 se escribe X1")
        p._desde_bloques("X1 AND  ↑marcha")
        self.assertEqual(e.texto_condicion(ts["t2"]), "active(`1`) AND rise(marcha)", "espacios normalizados")
        self.assertEqual(p.t_texto.text(), "X1 AND ↑marcha")
        p._desde_bloques("paro")
        # Receptividad vacia o mal escrita: no compila y lo dice
        p._desde_bloques("marcha AND")
        self.assertIn("t2", "; ".join(e.resumen(e.diagnosticos())))
        # Etiqueta oculta: no se dibuja y se conserva al guardar y abrir
        e.poner_condicion(ts["t2"], "paro")

        def textos():
            return [it.toPlainText() for it in w.diagrama.scene().items() if hasattr(it, "toPlainText")]
        self.assertFalse(p.t_mostrar.isChecked())
        self.assertNotIn("(t2)", textos())
        self.assertNotIn("(t1)", textos())
        p.t_mostrar.click()  # marca explícitamente
        self.assertIn("(t2)", textos())
        p.t_mostrar.click()  # desmarca
        self.assertNotIn("(t2)", textos())
        self.assertNotIn("(t1)", textos())
        with mock.patch("escritorio.ventana.QFileDialog.getSaveFileName", return_value=(str(Path(self.tmp.name)/"guardado.grafnet"),"")):
            self.assertTrue(w.guardar())
        self.assertTrue(w.abrir_ruta(fixture_grafnet(getattr(e,"archivo",None) or e.ruta)))
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual(w.edicion.ed.hidden_labels(), set(ts.values()))

    def test_SEDI15_transiciones_mas_altas_de_acertar(self):
        """REQ-EDT-02: el area de una transicion es mas alta que su trazo: se acierta sin punteria."""
        from escritorio.diagrama import ALTO_T, elemento_en
        e, ids, ts = self.secuencial()
        c = centro(e.M, ts["t1"])
        for dy in (-ALTO_T + 1, 0, ALTO_T - 1):
            self.assertEqual(elemento_en(e.M, QPointF(c.x(), c.y() + dy)), ts["t1"], dy)
        self.assertIsNone(elemento_en(e.M, QPointF(c.x() + 150, c.y() + ALTO_T + 12)))

    def test_SEDI17_barra_de_simultaneidad(self):
        """REQ-MOD-03, REQ-EDT-02: la simultaneidad es una barra de doble trazo que se arrastra desde la paleta, se
        enlaza con etapas y transicion y se ensancha estirando de sus extremos; el modelo guarda los enlaces normales."""
        from escritorio.diagrama import anclas, barra
        w = self.w
        e, ids, ts = self.secuencial()
        e.poner_condicion(ts["t2"], "paro")
        e.poner_etapa(QPointF(100 + 200, 220))
        e2 = next(s["id"] for s in e.M["steps"] if s["label"] == "2")
        pt = lambda i, lado: next(a for a in anclas(e.M, i) if a["lado"] == lado)["pos"]
        # Directo, una segunda etapa en la transicion se rechaza
        e.prensar(pt(ts["t1"], "abajo"))
        e.soltar(pt(e2, "arriba"))
        self.assertIn("simultaneidad", e.mensaje)
        # La barra se coloca donde se suelta y se ve
        e.colocar("simultaneidad", QPointF(100 + 100, 180))
        b = e.M["bars"][0]
        self.assertEqual((b["kind"], b["x"], b["y"], b["ancho"]), ("Y", 40.0, 180.0, 120.0))
        self.assertEqual(e.sel, [b["id"]])
        bx, by, ancho, alto = barra(b)
        self.assertEqual(alto, 8, "doble trazo con separación visible")
        # t1 -> barra (por encima) y barra -> E1 y E2 (por debajo): se parte el enlace directo t1 -> E1
        e.ed.disconnect(ts["t1"], ids["1"])
        e.cambia()
        for origen, destino in ((pt(ts["t1"], "abajo"), None), ):
            pass
        e.prensar(pt(ts["t1"], "abajo"))
        e.soltar(QPointF(bx + 30, by - 8))
        self.assertEqual(e.M["bars"][0]["arriba"], [ts["t1"]])
        for etapa in (ids["1"], e2):
            e.prensar(pt(etapa, "arriba"))
            e.soltar(QPointF(bx + 80, by + alto + 8))
        self.assertEqual(sorted(e.M["bars"][0]["abajo"]), sorted([ids["1"], e2]))
        self.assertEqual(sorted(e.ed.get(ts["t1"])["postRefs"]), sorted([ids["1"], e2]), "el modelo, con enlaces normales")
        self.assertEqual(len(e.M["bars"][0]["abajo"]) + len(e.M["bars"][0]["arriba"]), 3)
        self.assertTrue(e.ed.validate().can_simulate)
        # Estirar del extremo derecho: una sola operacion; se guarda
        n = len(e.ed.undo_stack)
        e.seleccionar([b["id"]])
        e.prensar(QPointF(bx + ancho, by + alto / 2))
        e.mover(QPointF(bx + ancho + 47, by))
        e.mover(QPointF(bx + ancho + 85, by))
        e.soltar(QPointF(bx + ancho + 85, by))
        self.assertEqual((e.M["bars"][0]["x"], e.M["bars"][0]["ancho"]), (40.0, 200.0))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(e.M["bars"][0]["ancho"], 120.0)
        # Mover la barra entera
        e.prensar(QPointF(bx + 60, by + 2))
        e.mover(QPointF(bx + 60, by + 42))
        e.soltar(QPointF(bx + 60, by + 42))
        self.assertEqual(e.M["bars"][0]["y"], 220.0)
        e.deshacer()
        # Guardar, abrir y simular: marcha activa E1 y E2 a la vez
        with mock.patch("escritorio.ventana.QFileDialog.getSaveFileName", return_value=(str(Path(self.tmp.name)/"guardado.grafnet"),"")):
            self.assertTrue(w.guardar())
        self.assertTrue(w.abrir_ruta(fixture_grafnet(getattr(e,"archivo",None) or e.ruta)))
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual(len(w.edicion.M["bars"]), 1)
        self.assertTrue(w.cambiar_modo("simular"))
        nombre = {bt.text().split(" ")[0]: v for v, bt in w.botones.items()}
        w._cambiar_tipo_entrada(nombre["marcha"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["marcha"]].click()
        self.assertEqual(sorted(w.v.state()["situation"]), sorted([ids["1"], e2]))
        # Quitar un elemento de la barra deshace su enlace; borrar la barra, los demas
        self.assertTrue(w.cambiar_modo("editar"))
        e = w.edicion
        bid = e.M["bars"][0]["id"]
        e.seleccionar([f"{bid}|{e2}|barra"])
        self.assertEqual(w.props.pagina, "enlace")
        self.assertTrue(e.borrar())
        self.assertEqual(e.ed.get(ts["t1"])["postRefs"], [ids["1"]])
        e.seleccionar([bid])
        self.assertEqual(w.props.pagina, "barra")
        self.assertTrue(e.borrar())
        self.assertEqual((e.M["bars"], e.ed.get(ts["t1"])["postRefs"]), ([], []))

    def test_SEDI19_alternativas_con_el_raton(self):
        """REQ-MOD-03, REQ-EDT-02: la alternativa (O) no es un elemento: se construye con el raton. Una segunda transicion
        desde una etapa se aparta a un lado para que se vea la rama; arrastrar de una transicion a un enlace une su rama
        a la etapa de ese enlace (flecha abajo); de una etapa a un enlace, un salto de secuencia."""
        from escritorio.diagrama import anclas, enlaces
        w = self.w
        e, ids, ts = self.secuencial()  # E0 -t1(marcha)-> E1 -t2(paro)-> E0
        e.poner_condicion(ts["t2"], "paro")
        pt = lambda i, lado: next(a for a in anclas(e.M, i) if a["lado"] == lado)["pos"]

        def sobre(trazo, k=0.35):  # un punto del ultimo tramo del enlace, lejos de los puntos de union
            (x0, y0), (x1, y1) = trazo[-2], trazo[-1]
            return QPointF(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)
        # Alternativa en el origen: una segunda transicion desde E0, justo debajo de t1, se aparta a un lado
        e.poner_transicion(QPointF(100 + 20, 190))  # casi debajo de t1
        t3 = next(t["id"] for t in e.M["transitions"] if t["label"] == "t3")
        e.prensar(pt(ids["0"], "abajo"))
        e.soltar(pt(t3, "arriba"))
        x1, x3 = centro(e.M, ts["t1"]).x(), centro(e.M, t3).x()
        self.assertGreaterEqual(abs(x3 - x1), 160, "la rama se ve: t3 queda a un lado de t1")
        self.assertEqual(len(e.ed.undo_stack) - 0 > 0, True)
        e.poner_condicion(t3, "alterna", crear=True)
        # Una etapa nueva E2 debajo, y una transicion t4 de E2 a ... se une al enlace t1 -> E1 (rama que vuelve)
        e.poner_etapa(QPointF(100 + 200, 420))
        e2 = next(s["id"] for s in e.M["steps"] if s["label"] == "2")
        e.conectar(t3, e2)
        e.poner_transicion(QPointF(100 + 200, 520))
        t4 = next(t["id"] for t in e.M["transitions"] if t["label"] == "t4")
        e.conectar(e2, t4)
        e.poner_condicion(t4, "vuelve", crear=True)
        lista = {x["id"]: x for x in enlaces(e.M)}
        enlace = lista[f"{ts['t1']}|{ids['1']}|post"]["pts"]
        punto = sobre(enlace)
        e.prensar(pt(t4, "abajo"))
        e.mover(punto)
        e.soltar(punto)
        self.assertEqual(e.ed.get(t4)["postRefs"], [ids["1"]], "t4 vuelve a E1: dos ramas llegan a una etapa")
        self.assertTrue(w.cambiar_modo("simular"))
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w._cambiar_tipo_entrada(nombre["alterna"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["alterna"]].click()  # el otro camino: E0 -t3-> E2
        self.assertEqual(w.v.state()["situation"], [e2])
        w._cambiar_tipo_entrada(nombre["alterna"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["alterna"]].click()
        w._cambiar_tipo_entrada(nombre["vuelve"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["vuelve"]].click()
        self.assertEqual(w.v.state()["situation"], [ids["1"]])
        # Salto de secuencia: de E0 al enlace que llega a E2 (de t3): una transicion nueva E0 -> E2
        self.assertTrue(w.cambiar_modo("editar"))
        e = w.edicion
        lista = {x["id"]: x for x in enlaces(e.M)}
        enlace = lista[f"{t3}|{e2}|post"]["pts"]
        punto = sobre(enlace)
        n = len(e.ed.model["transitions"])
        e.prensar(pt(ids["0"], "abajo"))
        e.soltar(punto)
        self.assertEqual(len(e.ed.model["transitions"]), n + 1)
        salto = next(t for t in e.ed.model["transitions"] if t["id"] not in (ts["t1"], ts["t2"], t3, t4))
        self.assertEqual((salto["preRefs"], salto["postRefs"], salto["label"]), ([ids["0"]], [e2], "t5"))
        self.assertEqual(e.sel, [salto["id"]])
        # Una etapa soltada sobre el enlace de entrada de una transición no es una rama: queda como borrador (P-IMP-118)
        antes = len(e.ed.undo_stack)
        e.prensar(pt(ids["1"], "abajo"))
        lista = {x["id"]: x for x in enlaces(e.M)}
        pre = lista[f"{ts['t1']}|{ids['0']}|pre"]["pts"]
        e.soltar(sobre(pre[:2], 0.5))  # el primer tramo, lejos de la transicion
        self.assertIn("simultaneidad", e.mensaje)
        self.assertEqual(len(e.ed.model["draftLinks"]), 1)
        self.assertEqual(len(e.ed.undo_stack), antes + 1)

    def test_SEDI20_sentido_del_enlace_segun_el_trazo(self):
        """REQ-MOD-03: de arriba abajo, el enlace no lleva flecha; de abajo arriba, si (sale solo del trazo)."""
        from escritorio.diagrama import anclas, enlaces
        e, ids, ts = self.secuencial()
        for _ in range(4):
            e.deshacer()
        pt = lambda i, lado: next(a for a in anclas(e.M, i) if a["lado"] == lado)["pos"]
        e.prensar(pt(ids["0"], "abajo"))  # E0 (arriba) a t1 (debajo)
        e.soltar(pt(ts["t1"], "arriba"))
        self.assertFalse({x["id"]: x for x in enlaces(e.M)}[f"{ts['t1']}|{ids['0']}|pre"]["arriba"])
        e.prensar(pt(ids["1"], "abajo"))  # E1 (abajo) a t1 (arriba): el flujo sube, y E1 es anterior de t2... de t1 no
        e.soltar(pt(ts["t2"], "arriba"))
        self.assertFalse({x["id"]: x for x in enlaces(e.M)}[f"{ts['t2']}|{ids['1']}|pre"]["arriba"])
        # De t2 (abajo) a E0 (arriba): el enlace va hacia arriba, con flecha
        e.prensar(pt(ts["t2"], "abajo"))
        e.soltar(pt(ids["0"], "arriba"))
        self.assertTrue({x["id"]: x for x in enlaces(e.M)}[f"{ts['t2']}|{ids['0']}|post"]["arriba"])
        # Del punto de arriba de E1 al de abajo de t1: E1 recibe, y t1 -> E1 baja sin flecha
        e.prensar(pt(ids["1"], "arriba"))
        e.soltar(pt(ts["t1"], "abajo"))
        self.assertEqual(e.ed.get(ts["t1"])["postRefs"], [ids["1"]])
        self.assertFalse({x["id"]: x for x in enlaces(e.M)}[f"{ts['t1']}|{ids['1']}|post"]["arriba"])

    def test_SEDI18_enlaces_seleccionables_flecha_y_quitar(self):
        """REQ-EDT-02: un enlace se selecciona con un clic en su trazo; si va de abajo arriba se dibuja con flecha; se
        puede quitar sin borrar los elementos. No hay botón para invertirlo (P-IMP-36): se quita y se vuelve a enlazar."""
        from escritorio.diagrama import enlaces
        w = self.w
        e, ids, ts = self.secuencial()
        lista = {x["id"]: x for x in enlaces(e.M)}
        self.assertEqual(len(lista), 4)
        enlace = f"{ts['t1']}|{ids['0']}|pre"
        self.assertIn(enlace, lista)
        a, b = lista[enlace]["pts"][0], lista[enlace]["pts"][1]
        punto = QPointF((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        e.herramienta = "seleccionar"
        e.prensar(punto)
        e.soltar(punto)
        self.assertEqual(e.sel, [enlace])
        self.assertEqual(w.props.pagina, "enlace")
        self.assertIn("Enlace", w.props.titulo.text())
        self.assertIn("0 → t1", w.l_sel.text())
        self.assertFalse(hasattr(w.props, "f_invertir") or hasattr(e, "invertir"))
        lista = {x["id"]: x for x in enlaces(e.M)}
        self.assertTrue(lista[f"{ts['t2']}|{ids['0']}|post"]["arriba"], "el enlace de vuelta a E0 ya va hacia arriba")
        self.assertFalse(lista[f"{ts['t1']}|{ids['0']}|pre"]["arriba"])
        # Quitar el enlace: las dos etapas y las dos transiciones siguen
        e.seleccionar([enlace])
        self.assertTrue(e.borrar())
        self.assertEqual((len(e.M["steps"]), len(e.M["transitions"]), len(enlaces(e.M))), (2, 2, 3))
        e.deshacer()
        self.assertEqual(len(enlaces(e.M)), 4)

    def test_SEDI21_abrir_ramas_con_el_raton_de_verdad(self):
        """REQ-MOD-03, REQ-EDT-02: con eventos de raton reales sobre el dibujo (pulsar, mover, soltar): arrastrar de un punto
        de union a un hueco crea el elemento siguiente; una rama desde la misma etapa; una rama que se une a un enlace;
        y un salto de secuencia. Es el ejemplo «alternativas» construido desde cero."""
        from escritorio.diagrama import anclas, enlaces
        w = self.w
        w.nuevo()
        e, d = w.edicion, w.diagrama
        vp = d.viewport()

        def pos(p):
            return d.mapFromScene(QPointF(p))

        def arrastrar(a, b):
            QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos(a))
            for k in (0.3, 0.6, 1.0):
                QTest.mouseMove(vp, pos(QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k)))
            QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos(b))

        def punto(i, lado):
            return next(x for x in anclas(e.M, i) if x["lado"] == lado)["pos"]

        def sobre(enlace, k=0.35):
            (x0, y0), (x1, y1) = enlaces(e.M)[[x["id"] for x in enlaces(e.M)].index(enlace)]["pts"][-2:]
            return QPointF(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)

        def uno(coleccion, etiqueta):
            return next(x["id"] for x in e.M[coleccion] if x["label"] == etiqueta)
        self.soltar_ficha("etapa", QPointF(420, 60))
        e0 = uno("steps", "0")
        e.tipo_etapa(e0, True)
        # Hacia abajo, siempre arrastrando de un punto de union a un hueco: t1, E1, t2, E2
        arrastrar(punto(e0, "abajo"), QPointF(420, 140))
        t1 = uno("transitions", "t1")
        arrastrar(punto(t1, "abajo"), QPointF(420, 220))
        e1 = uno("steps", "1")
        arrastrar(punto(e1, "abajo"), QPointF(420, 300))
        t2 = uno("transitions", "t2")
        arrastrar(punto(t2, "abajo"), QPointF(420, 380))
        e2 = uno("steps", "2")
        self.assertEqual((len(e.M["steps"]), len(e.M["transitions"])), (3, 2))
        self.assertEqual((e.ed.get(t1)["preRefs"], e.ed.get(t1)["postRefs"]), ([e0], [e1]))
        # Una alternativa: de E0 a otro hueco a un lado: una segunda transicion desde la misma etapa (salto de secuencia)
        arrastrar(punto(e0, "abajo"), QPointF(640, 260))
        t3 = uno("transitions", "t3")
        self.assertEqual(e.ed.get(t3)["preRefs"], [e0])
        # ... que se une al enlace que llega a E2
        arrastrar(punto(t3, "abajo"), sobre(f"{t2}|{e2}|post"))
        self.assertEqual(e.ed.get(t3)["postRefs"], [e2], "dos ramas llegan a E2")
        # Una rama que vuelve: de E2 a un hueco, y de ahi al enlace que llega a E1
        arrastrar(punto(e2, "abajo"), QPointF(640, 440))
        t4 = uno("transitions", "t4")
        arrastrar(punto(t4, "abajo"), sobre(f"{t1}|{e1}|post"))
        self.assertEqual(e.ed.get(t4)["postRefs"], [e1])
        self.assertEqual(sorted(x["id"] for x in e.ed.model["transitions"] if e0 in x["preRefs"]), sorted([t1, t3]))
        self.assertEqual(sorted(x["id"] for x in e.ed.model["transitions"] if e2 in x["preRefs"]), [t4])
        # Un deshacer por rama, y el grafcet compila al poner sus receptividades
        n = len(e.ed.undo_stack)
        e.deshacer()
        self.assertEqual(e.ed.get(t4)["postRefs"], [])
        e.rehacer()
        self.assertEqual(len(e.ed.undo_stack), n)
        for t, c in ((t1, "marcha"), (t2, "fin1"), (t3, "rapida"), (t4, "repetir")):
            e.poner_condicion(t, c, crear=True)
        self.assertTrue(e.ed.validate().can_simulate, [str(x) for x in e.ed.validate().diagnostics])
        self.assertTrue(w.cambiar_modo("simular"))
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w._cambiar_tipo_entrada(nombre["rapida"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["rapida"]].click()
        self.assertEqual(w.v.state()["situation"], [e2], "el salto lleva de E0 a E2")

    def test_SEDI22_ejemplo_alternativas(self):
        """REQ-SIM-03: un proyecto de prueba de alternativas se simula y se edita conservando las flechas de unión."""
        w = self.w
        self.proyecto_fixture("alternativas")
        w.a_ejecutar.setChecked(True)  # abrir deja Pausa sin estado: Play arranca la sesión
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w._cambiar_tipo_entrada(nombre["rapida"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["rapida"]].click()
        self.assertEqual(w.v.state()["situation"], ["E2"])
        w._cambiar_tipo_entrada(nombre["repetir"], True)  # esta prueba mantiene la entrada
        w.botones[nombre["repetir"]].click()
        self.assertEqual(w.v.state()["situation"], ["E1"], "la rama que vuelve")
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual((len(w.edicion.M["steps"]), len(w.edicion.M["transitions"])), (4, 6))
        self.assertTrue(w.edicion.ed.validate().can_simulate)
        e = w.edicion
        self.assertEqual(e.ed.next_label("transition"), "t7", "en un ejemplo, los ID t1..t6 ya son nombres")
        # Dos ramas llegan a una etapa (E0 recibe t4 y la nueva), pero a una transicion no: seria una simultaneidad
        nueva = e.poner_transicion(QPointF(100 + 500, 700))
        e.conectar(nueva, "E0")
        self.assertEqual(sorted(t["id"] for t in e.ed.model["transitions"] if "E0" in t["postRefs"]), sorted(["t4", nueva]))
        e.conectar("E3", "t2")
        self.assertIn("simultaneidad", e.mensaje)
        self.assertEqual(e.ed.get("t2")["preRefs"], ["E1"])

    def test_SEDI23_el_punto_de_arriba_recibe_y_el_enlace_entra_por_arriba(self):
        """REQ-MOD-03: lo que se arrastra desde el punto de arriba de una transicion es lo que le llega (viene de la etapa
        a la que se suelta), aunque la etapa quede debajo: el enlace sube, lleva flecha y entra por arriba; el rechazo se ve."""
        from escritorio.diagrama import anclas, enlaces
        w = self.w
        w.nuevo()
        e = w.edicion
        pt = lambda i, lado: next(a for a in anclas(e.M, i) if a["lado"] == lado)["pos"]
        # E4 -t7-> E5 -t8-> E6 -t9-> E7, y t10 a la derecha de E5, con su salida a E5 (la rama que vuelve)
        for y, tipo in ((60, "etapa"), (140, "transicion"), (220, "etapa"), (300, "transicion"), (380, "etapa"),
                        (460, "transicion"), (540, "etapa")):
            e.colocar(tipo, QPointF(100 + 100, y))
        steps = [s["id"] for s in e.M["steps"]]
        ts = [t["id"] for t in e.M["transitions"]]
        for a, b in ((steps[0], ts[0]), (ts[0], steps[1]), (steps[1], ts[1]), (ts[1], steps[2]), (steps[2], ts[2]),
                     (ts[2], steps[3])):
            e.conectar(a, b)
        e.poner_transicion(QPointF(100 + 190, 300))
        t10 = next(t["id"] for t in e.M["transitions"] if t["label"] == "t4")
        e.prensar(pt(t10, "abajo"))
        e.soltar(pt(steps[1], "arriba"))  # t10 -> E5: la rama que vuelve, por la derecha
        self.assertEqual(e.ed.get(t10)["postRefs"], [steps[1]])
        # Ahora, el punto de ARRIBA de t10 hacia E6 (que queda debajo): E6 -> t10, que entra por arriba
        e.prensar(pt(t10, "arriba"))
        e.soltar(pt(steps[2], "arriba"))
        self.assertEqual(e.ed.get(t10)["preRefs"], [steps[2]], "el punto de arriba recibe: E6 es su etapa anterior")
        self.assertEqual(e.mensaje, "")
        enlace = {x["id"]: x for x in enlaces(e.M)}[f"{t10}|{steps[2]}|pre"]
        self.assertTrue(enlace["arriba"], "de abajo arriba: con flecha")
        self.assertEqual(enlace["pts"][-1], centro(e.M, t10).toTuple(), "entra en la transicion")
        self.assertLess(enlace["pts"][-2][1], centro(e.M, t10).y(), "por arriba, no por abajo")
        self.assertFalse(e.ed.validate().can_simulate, "las receptividades aún están pendientes")
        # Un rechazo se ve: queda en el mensaje, que sale en rojo
        e.prensar(pt(t10, "abajo"))
        e.soltar(pt(steps[3], "arriba"))
        self.assertIn("ya tiene una etapa siguiente", e.mensaje)
        self.assertEqual(w.statusBar().currentMessage(), e.mensaje)


    def test_SEDI24_entrada_de_transicion_a_enlace_de_salida(self):
        """REQ-EDT-02, REQ-MOD-03: arrastrar la entrada a un enlace de salida crea otra alternativa, no una simultaneidad."""
        from escritorio.diagrama import anclas, enlaces
        e, ids, ts = self.secuencial()
        nuevo = e.poner_transicion(QPointF(500, 140))
        pre = next(x for x in enlaces(e.M) if x['id'] == f"{ts['t1']}|{ids['0']}|pre")
        a, b = pre['pts'][:2]
        destino = QPointF((a[0]+b[0])/2, (a[1]+b[1])/2)
        origen = anclas(e.M, nuevo)[0]['pos']
        d = self.w.diagrama
        def arrastrar(a, b):
            QTest.mousePress(d.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, d.mapFromScene(a))
            QTest.mouseMove(d.viewport(), d.mapFromScene(b))
            QTest.mouseRelease(d.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, d.mapFromScene(b))
        n = len(e.ed.undo_stack)
        arrastrar(origen, destino)
        self.assertEqual(e.ed.get(nuevo)['preRefs'], [ids['0']])
        self.assertEqual(e.ed.get(nuevo)['postRefs'], [])
        self.assertEqual(e.ed.get(ts['t1'])['preRefs'], [ids['0']])
        self.assertEqual(len(e.ed.undo_stack), n+1)
        e.deshacer()
        self.assertEqual(e.ed.get(nuevo)['preRefs'], [])
        e.rehacer()
        self.assertEqual(e.ed.get(nuevo)['preRefs'], [ids['0']])

    def test_SEDI25_arrastrar_desde_linea_de_seleccion(self):
        """REQ-EDT-02: clic selecciona un enlace; arrastrarlo mueve su tramo (no abre ninguna rama), en una operación."""
        from escritorio.diagrama import enlaces
        self.proyecto_fixture('seleccion')
        self.w.cambiar_modo('editar')
        e, d = self.w.edicion, self.w.diagrama
        ruta = next(x for x in enlaces(e.M) if x['tid'] == 't2' and x['rol'] == 'pre')
        a, b = ruta['pts'][1:3]
        p = QPointF((a[0]+b[0])/2, a[1])
        n = len(e.ed.undo_stack)
        QTest.mouseClick(d.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, d.mapFromScene(p))
        self.assertEqual(e.sel, [ruta['id']])
        self.assertEqual(len(e.ed.undo_stack), n)
        destino = QPointF(650, 180)
        QTest.mousePress(d.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, d.mapFromScene(p))
        QTest.mouseMove(d.viewport(), d.mapFromScene(destino))
        QTest.mouseRelease(d.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, d.mapFromScene(destino))
        self.assertEqual(len(e.M['transitions']), 2, 'no se abre ninguna rama')
        self.assertIn(ruta['id'], e.ed.link_styles(), 'el tramo agarrado se movió')
        self.assertEqual(len(e.ed.undo_stack), n+1)
        e.deshacer()
        self.assertNotIn(ruta['id'], e.ed.link_styles())
        self.assertEqual(len(e.M['transitions']), 2)

    def test_SEDI26_geometria_comun_retorno_y_movimiento(self):
        """REQ-MOD-03: uniones comunes, retorno fuera de la etapa, flecha automática y recorridos iguales en Qt/web."""
        from escritorio.diagrama import enlaces, H, SX
        self.proyecto_fixture('repeticion')
        self.w.cambiar_modo('editar')
        e = self.w.edicion
        rutas = enlaces(e.M)
        self.assertEqual(rutas, e.M['links'])
        salida = [r for r in rutas if r['sid'] == '3' and r['rol'] == 'pre']
        llegada = [r for r in rutas if r['sid'] == '2' and r['rol'] == 'post']
        self.assertEqual(salida[0]['pts'][1][1], salida[1]['pts'][1][1])
        self.assertEqual(llegada[0]['pts'][-2][1], llegada[1]['pts'][-2][1])
        retorno = next(r for r in rutas if r['tid'] == 'retorno' and r['rol'] == 'post')
        self.assertTrue(retorno['arriba'])
        # La etapa queda debajo de la transición: sale por ABAJO y rodea su cuerpo.
        e.ed.move('retorno', 80, 260)
        e.cambia()
        r = next(r for r in enlaces(e.M) if r['tid'] == 'retorno' and r['rol'] == 'pre')
        self.assertEqual(r['pts'][0], (300+SX, 380+H))
        self.assertTrue(r['arriba'])
        self.assertLess(r['pts'][-2][1], 260)
        self.assertNotEqual(r['pts'][2][0], 300+SX)
        e.ed.move('retorno', 80, 100)
        e.cambia()
        self.assertFalse(next(r for r in enlaces(e.M) if r['tid'] == 'retorno' and r['rol'] == 'post')['arriba'])

    def test_SEDI28_salto_inverso_guardar_y_reabrir(self):
        """REQ-EDT-01, REQ-EDT-02: arrastrar la entrada de una etapa a una salida crea el salto; persiste y se deshace entero."""
        from escritorio.diagrama import anclas, enlaces
        from escritorio.edicion import Edicion
        self.proyecto_fixture('salto')
        self.w.cambiar_modo('editar')
        e = self.w.edicion
        n = len(e.ed.undo_stack)
        e.unir_a_enlace(anclas(e.M, '4')[0], 't1|1|pre')
        t = e.ed.get(e.sel[0])
        self.assertEqual((t['preRefs'], t['postRefs']), (['1'], ['4']))
        e.poner_condicion(t['id'], 'saltar')
        with tempfile.TemporaryDirectory() as tmp:
            e.guardar(Path(tmp) / 'proyecto')
            op = open_model(Path(tmp) / 'proyecto')
            otro = Edicion.desde(op.doc, layout_from_presentation(op.presentations[0]), op.title, presentacion=op.presentations[0])
            self.assertEqual(enlaces(e.M), enlaces(otro.M))
            self.assertTrue(otro.ed.validate().can_simulate)
        e.deshacer()  # receptividad
        e.deshacer()  # salto completo
        self.assertEqual(len(e.ed.undo_stack), n)
        self.assertNotIn(t['id'], {t['id'] for t in e.M['transitions']})

    def test_SEDI27_ejemplos_seleccion_salto_repeticion(self):
        """REQ-SIM-03: las ramas construidas ejecutan selección, salto y repetición sin cambiar el motor."""
        w = self.w
        def cargar(key):
            w.cargar_ejemplo(key)
            w.a_ejecutar.setChecked(True)  # abrir deja Pausa sin estado: Play arranca la sesión
        def pulsar(nombre):
            next(b for b in w.botones.values() if b.text().split(' ')[0] == nombre).click()
        cargar('seleccion')
        pulsar('a')
        self.assertEqual(w.v.state()['situation'], ['6'])
        cargar('seleccion')
        pulsar('b')
        self.assertEqual(w.v.state()['situation'], ['7'])
        cargar('salto')
        pulsar('saltar')
        self.assertEqual(w.v.state()['situation'], ['4'])
        cargar('repeticion')
        for nombre in ('inicio', 'inicio', 'avance', 'avance', 'repetir'):
            pulsar(nombre)
        self.assertEqual(w.v.state()['situation'], ['2'])
        for nombre in ('repetir', 'avance', 'avance', 'fin'):
            pulsar(nombre)
        self.assertEqual(w.v.state()['situation'], ['4'])


    def retorno_editable(self):
        self.proyecto_fixture('repeticion')
        self.w.cambiar_modo('editar')
        e = self.w.edicion
        e.seleccionar(['retorno|2|post'])
        return e

    def arrastrar_dibujo(self, a, b):
        d = self.w.diagrama
        QTest.mousePress(d.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, d.mapFromScene(QPointF(*a)))
        for k in (0.3, 0.6, 1):
            QTest.mouseMove(d.viewport(), d.mapFromScene(QPointF(a[0]+k*(b[0]-a[0]), a[1]+k*(b[1]-a[1]))))
        QTest.mouseRelease(d.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, d.mapFromScene(QPointF(*b)))

    def test_SEDI29_flecha_arrastrar_y_ocultar_sin_cambiar_modelo(self):
        """REQ-EDT-02, REQ-EDT-03: mover y ocultar la flecha son presentación; un arrastre, un deshacer. La flecha sigue
        el sentido del enlace: no hay botón para darle la vuelta (P-IMP-36)."""
        import copy
        from escritorio.diagrama import enlaces
        e = self.retorno_editable()
        original = copy.deepcopy(e.ed.model)
        ruta = lambda: next(r for r in enlaces(e.M) if r['id'] == 'retorno|2|post')
        f = ruta()['arrows'][0]
        pts = ruta()['pts']
        destino = (pts[2][0], pts[2][1]*0.2+pts[3][1]*0.8)
        n = len(e.ed.undo_stack)
        self.arrastrar_dibujo(f['pos'], destino)
        nuevo = ruta()['arrows'][0]
        self.assertAlmostEqual(nuevo['pos'][1], destino[1], delta=2)
        self.assertEqual(len(e.ed.undo_stack), n+1)
        self.assertEqual(e.ed.model, original)
        e.deshacer()
        self.assertEqual(ruta()['arrows'][0]['pos'], f['pos'])
        e.rehacer()
        nuevo = ruta()['arrows'][0]
        self.assertLess(nuevo['pts'][0][1], nuevo['pos'][1], 'la punta sigue hacia arriba: el retorno sube')
        self.w.props.f_visible.click()
        self.assertEqual(ruta()['arrows'], [])
        self.assertFalse(self.w.props.f_visible.isChecked())
        self.w.props.f_visible.click()
        self.assertEqual(ruta()['arrows'][0], nuevo)
        self.assertEqual(e.ed.model, original)
        self.w.props.f_auto.click()
        self.assertEqual(ruta()['arrows'][0], f)

    def test_SEDI30_recolocar_retorno_y_mover_etapa(self):
        """REQ-EDT-02, REQ-EDT-03: tiradores para carril y alturas; extremos conectados al mover etapas. El recorrido no
        tiene botón de restaurar: se recoloca a mano."""
        from escritorio.diagrama import enlaces
        e = self.retorno_editable()
        ruta = lambda: next(r for r in enlaces(e.M) if r['id'] == 'retorno|2|post')
        inicial = ruta()['pts']
        revision = e.ed.model['revisionId']
        # Llevar el carril desde la izquierda hasta la derecha del grafcet.
        h = next(h for h in ruta()['handles'] if h['segment'] == 2)
        n = len(e.ed.undo_stack)
        self.arrastrar_dibujo(h['pos'], (700, h['pos'][1]))
        self.assertEqual(ruta()['pts'][2][0], 700)
        self.assertEqual(len(e.ed.undo_stack), n+1)
        e.deshacer()
        self.assertEqual(ruta()['pts'], inicial)
        e.rehacer()
        # La altura del tramo superior también es manual.
        h = next(h for h in ruta()['handles'] if h['segment'] == 3)
        self.arrastrar_dibujo(h['pos'], (h['pos'][0], 120))
        self.assertEqual(ruta()['pts'][3][1], 120)
        self.assertEqual(e.ed.model['revisionId'], revision)
        e.ed.move('2', 340, 240)
        e.cambia()
        self.assertEqual(ruta()['pts'][2][0], 700)
        self.assertEqual(ruta()['pts'][3][1], 120)
        self.assertEqual(ruta()['pts'][-1], (440, 218))
        self.assertFalse(hasattr(self.w.props, 'r_auto'))

    def test_SEDI31_flecha_union_horizontal_independiente(self):
        """REQ-EDT-02: la flecha de unión no sale por defecto (el enlace baja); se muestra, se mueve y se oculta; la
        de recorrido se orienta con el tramo horizontal."""
        from escritorio.diagrama import enlaces
        e = self.retorno_editable()
        ruta = lambda: next(r for r in enlaces(e.M) if r['id'] == 't1|2|post')
        self.assertIn('join', ruta()['arrowKinds'])
        self.assertEqual(ruta()['arrows'], [])
        e.seleccionar(['t1|2|post'])
        e.flecha = 'join'
        self.w.props.mostrar(e)
        self.w.props.f_visible.click()
        f = next(f for f in ruta()['arrows'] if f['key'] == 'join')
        self.arrastrar_dibujo(f['pos'], (f['pos'][0], f['pos'][1]-20))
        self.assertEqual(e.flecha, 'join')
        self.w.props.f_visible.click()
        self.assertEqual(ruta()['arrows'], [])
        e.seleccionar(['retorno|2|post'])
        e.flecha = 'flow'
        r = next(r for r in enlaces(e.M) if r['id'] == e.sel[0])
        a, b = r['pts'][3:5]
        target = ((a[0]+b[0])/2, a[1])
        self.arrastrar_dibujo(r['arrows'][0]['pos'], target)
        r = next(r for r in enlaces(e.M) if r['id'] == e.sel[0])
        f = r['arrows'][0]
        self.assertAlmostEqual(f['pos'][1], target[1], delta=1)
        self.assertGreater(f['pts'][0][0], f['pos'][0], 'flecha a la derecha sobre el tramo horizontal')

    def test_SEDI32_dibujo_manual_persistencia_y_simulacion(self):
        """REQ-EDT-01, REQ-SIM-03: los ajustes sobreviven a guardar, abrir, simular y guardar otra copia."""
        from escritorio.diagrama import enlaces
        e = self.retorno_editable()
        style = {'route': {'laneX': '580', 'exitY': '500', 'entryY': '160'},
                 'arrows': {'flow': {'segment': 2, 'ratio': '0.7'}}}
        e.ed.set_link_style(e.sel[0], style)
        e.cambia()
        expected = enlaces(e.M)
        self.assertTrue(self.w.cambiar_modo('simular'))
        self.assertEqual(enlaces(self.w.v.model), expected)
        dest = Path(self.tmp.name) / 'manual.grafnet'
        self.w.guardar_en(dest)
        e.ed.dirty = False  # la copia ya está guardada; evitar el diálogo al abrirla en esta prueba
        self.assertTrue(self.w.abrir_ruta(fixture_grafnet(dest)))
        self.assertEqual(enlaces(self.w.v.model), expected)
        otra = Path(self.tmp.name) / 'copia-manual.grafnet'
        self.w.guardar_en(otra)
        self.assertEqual(open_model(self.w.edicion.ruta).presentations[0]['linkStyles']['retorno|2|post'], style)
        self.assertTrue(self.w.cambiar_modo('editar'))
        self.assertEqual(enlaces(self.w.edicion.M), expected)

    def nuevo_par(self, etapa, transicion):
        """Un grafcet nuevo con una etapa y una transición en las posiciones dadas (coordenadas del modelo)."""
        if self.w.edicion is not None:
            self.w.edicion.ed.dirty = False  # descartar el anterior sin el diálogo de cambios sin guardar
        self.w.nuevo()
        e = self.w.edicion
        sid = e.ed.add_step(e.raiz, "6", at=etapa)
        tid, _ = e.ed.add_transition(e.raiz, "", at=transicion, label="t3")
        e.cambia()
        return e, sid, tid

    def test_SEDI33_una_flecha_por_lazo_y_ninguna_al_bajar(self):
        """REQ-EDT-02: por defecto solo lleva flecha un enlace que sube, y una por lazo, en el enlace más largo (figura del
        responsable: 7 → t3 → 7); un enlace que baja no la lleva, tampoco donde se unen dos ramas."""
        from escritorio.diagrama import enlaces
        e, sid, tid = self.nuevo_par((0, 0), (200, 30))
        e.conectar(sid, tid)  # 7 → t3: t3 casi a la altura de 7, el enlace rodea y sube un poco
        e.conectar(tid, sid)  # t3 → 7: el retorno sube por el carril
        rutas = {r['id']: r for r in enlaces(e.M)}
        ida, vuelta = rutas[f'{tid}|{sid}|pre'], rutas[f'{tid}|{sid}|post']
        self.assertTrue(ida['arriba'] and vuelta['arriba'], 'los dos tienen algún tramo que sube')
        self.assertEqual([len(ida['arrows']), len(vuelta['arrows'])], [0, 1], 'una sola flecha, en el retorno largo')
        # Dos lazos que comparten etapas: cada retorno lleva la suya
        e.ed.dirty = False  # sin el diálogo de cambios sin guardar
        self.proyecto_fixture('alternativas')
        self.w.cambiar_modo('editar')
        e = self.w.edicion
        con = [r for r in enlaces(e.M) if r['arrows']]
        self.assertEqual(sorted(r['id'] for r in con), sorted(r['id'] for r in enlaces(e.M) if r['arriba']))
        self.assertFalse(any(f['key'] == 'join' for r in enlaces(e.M) for f in r['arrows']), 'sin flecha de unión')

    def test_SEDI36_sin_escalones_en_el_tramo_horizontal(self):
        """REQ-EDT-02: un carril guardado cuando el enlace daba un rodeo no deja un escalón cuando ya no hace falta; con
        poco sitio los tramos verticales se acortan antes que dar un rodeo de unos puntos."""
        from escritorio.diagrama import enlaces
        from grafcet.routing import TALLO_CORTO
        e, sid, tid = self.nuevo_par((0, 0), (420, 160))
        e.conectar(sid, tid)
        ident = f'{tid}|{sid}|pre'
        e.ed.set_link_style(ident, {'route': {'laneX': '230', 'exitY': '50', 'entryY': '56'}})
        e.cambia()
        pts = next(r for r in enlaces(e.M) if r['id'] == ident)['pts']
        self.assertEqual(len(pts), 4)
        self.assertEqual(pts[1][1], pts[2][1], 'tramo horizontal recto, a la altura de salida guardada')
        self.assertEqual(pts[1][1], 50)
        # 36 de hueco entre la etapa y la transición: no caben 16 + 24, pero no se da un rodeo
        e, sid, tid = self.nuevo_par((0, 0), (200, 58))
        e.conectar(sid, tid)
        r = next(r for r in enlaces(e.M) if r['id'] == f'{tid}|{sid}|pre')
        self.assertEqual(len(r['pts']), 4)
        self.assertEqual(r['arrows'], [])
        self.assertGreaterEqual(r['pts'][1][1] - r['pts'][0][1], TALLO_CORTO)
        self.assertGreaterEqual(r['pts'][3][1] - r['pts'][2][1], TALLO_CORTO)

    def test_SEDI37_iman_alinea_con_el_elemento_enlazado(self):
        """REQ-EDT-03: al mover una etapa o una transición a dos pasos de rejilla o menos de la vertical de un elemento
        enlazado, se alinea con él y el enlace queda recto (sin la S); más lejos, se queda donde se suelta."""
        from escritorio.diagrama import enlaces
        e, sid, tid = self.nuevo_par((0, 0), (80, 80))
        e.conectar(sid, tid)
        c = centro(e.M, tid)
        for dx, esperado in ((-20, 60), (-40, 0), (-60, 0)):  # a 60 se queda; a 40 o a 20, a la vertical de la etapa
            e.prensar(c)
            e.mover(QPointF(c.x() + dx, c.y() + 2))
            e.soltar(QPointF(c.x() + dx, c.y() + 2))
            self.assertEqual(centro(e.M, tid).x() - 100, esperado)
            e.deshacer()
            self.assertEqual(centro(e.M, tid), c)
        e.prensar(c)
        e.mover(QPointF(c.x() - 50, c.y()))
        e.soltar(QPointF(c.x() - 50, c.y()))
        pts = next(r for r in enlaces(e.M) if r['id'] == f'{tid}|{sid}|pre')['pts']
        self.assertTrue(all(x == pts[0][0] for x, _ in pts), 'enlace recto')

    def test_SEDI38_panel_izquierdo_plegable_y_figura_de_la_paleta(self):
        """REQ-EDT-02: el panel izquierdo (paleta y propiedades) se pliega como los otros, desde su flecha o desde Ver, y
        se recuerda; al arrastrar de la paleta se lleva la figura del elemento al zoom del dibujo, con su centro bajo el
        puntero."""
        from escritorio.diagrama import H
        from escritorio.propiedades import figura
        from grafcet.routing import TALLO_E
        w = self.w
        self.secuencial()  # la prueba construye su GRAFCET: el arranque del programa es vacío
        w.edicion.ed.dirty=False
        self.assertFalse(w.flechas['izquierdo'].isHidden(), 'al abrir está en Pausa/edición: hay panel izquierdo')
        self.assertTrue(w.cambiar_modo('simular'))
        self.assertTrue(w.flechas['izquierdo'].isHidden(), 'en Play no hay panel izquierdo')
        self.secuencial()  # un grafcet propio y simulable (un grafcet vacío no arranca)
        self.assertFalse(w.dock.isHidden() or w.flechas['izquierdo'].isHidden())
        w.flechas['izquierdo'].click()
        self.assertTrue(w.dock.isHidden() and not w.a_izquierdo.isChecked())
        self.assertEqual(w.flechas['izquierdo'].text(), '▸')
        self.assertFalse(w.ajustes.value('paneles/izquierdo', True, type=bool))
        w.cambiar_modo('simular')
        w.cambiar_modo('editar')
        self.assertTrue(w.dock.isHidden(), 'plegado sigue plegado al volver a editar')
        w.a_izquierdo.setChecked(True)
        self.assertFalse(w.dock.isHidden())
        self.assertEqual(w.flechas['izquierdo'].text(), '◂')
        pm, punto = figura('etapa', 2.0)
        self.assertEqual((pm.width(), pm.height()), (192, 176))
        self.assertEqual((punto.x(), punto.y()), (96, 88))
        self.assertGreater(figura('transicion', 2.0)[0].height(), figura('transicion', 1.0)[0].height())

    def test_SEDI34_agarrar_una_transicion_la_mueve(self):
        """REQ-EDT-02: el trazo de una transición se agarra para moverla; sus puntos de unión quedan al final de su
        tramo recto, arriba y abajo, y solo de ahí sale una rama."""
        from escritorio.diagrama import ALTO_T, anclas
        from grafcet.routing import TALLO_T
        e, sid, tid = self.nuevo_par((0, 0), (0, 160))
        c = centro(e.M, tid)
        puntos = {a['lado']: a['pos'] for a in anclas(e.M, tid)}
        self.assertEqual((puntos['arriba'].y(), puntos['abajo'].y()), (c.y() - TALLO_T, c.y() + TALLO_T))
        for dy in (-ALTO_T, -6, 0, 6, ALTO_T):
            e.prensar(QPointF(c.x() + 4, c.y() + dy))
            self.assertIsNone(e.enlace, f'a {dy} del trazo se agarra la transición')
            self.assertEqual(e.arrastre['id'], tid)
            e.soltar(QPointF(c.x() + 4, c.y() + dy))
        e.prensar(puntos['abajo'])
        self.assertEqual((e.enlace['id'], e.enlace['lado']), (tid, 'abajo'))
        e.soltar(puntos['abajo'])

    def test_SEDI35_tramo_vertical_minimo_en_etapas_y_transiciones(self):
        """REQ-EDT-02: un enlace siempre sale de la etapa y llega a la transición (y al revés) con un tramo vertical
        mínimo, aunque estén casi a la misma altura (figura del responsable: 6 y t3); si no cabe, sube con flecha."""
        from escritorio.diagrama import enlaces
        from grafcet.routing import TALLO_E, TALLO_T

        def ruta(e, ident):
            return next(r for r in enlaces(e.M) if r['id'] == ident)

        def tramos(pts, ini, fin):
            (a, b), (c, d) = pts[:2], pts[-2:]
            self.assertEqual((a[0], c[0]), (b[0], d[0]), 'primer y último tramo verticales')
            self.assertGreaterEqual(b[1] - a[1], ini)
            self.assertGreaterEqual(d[1] - c[1], fin)
        # Como en la figura: t3 a la izquierda de 6, casi a la altura de su borde inferior
        e, sid, tid = self.nuevo_par((200, 40), (0, 60))
        e.conectar(sid, tid)
        r = ruta(e, f'{tid}|{sid}|pre')
        tramos(r['pts'], TALLO_E, TALLO_T)
        self.assertTrue(r['arrows'], 'el tramo que sube lleva flecha')
        # Transición encima de una etapa muy próxima
        e, sid, tid = self.nuevo_par((200, 130), (0, 100))
        e.conectar(tid, sid)
        tramos(ruta(e, f'{tid}|{sid}|post')['pts'], TALLO_T, TALLO_E)
        # Con sitio, el recorrido de siempre: tramo horizontal a media altura y sin flecha
        e, sid, tid = self.nuevo_par((200, 0), (0, 80))
        e.conectar(sid, tid)
        r = ruta(e, f'{tid}|{sid}|pre')
        self.assertEqual(len(r['pts']), 4)
        self.assertEqual(r['arrows'], [])
        # Un tramo recolocado a mano tampoco se come los tramos mínimos
        e.ed.set_link_style(r['id'], {'route': {'middleY': '24'}})
        e.cambia()
        tramos(ruta(e, r['id'])['pts'], TALLO_E, TALLO_T)


    # -- paso 4: variables, acciones y programador por bloques (P-IMP-38) ------------------------------------
    def _recorrido(self, doc, pasos, horizonte):
        """Ejecuta un modelo con entradas por nombre y devuelve, en cada situación estable, el instante, las etapas,
        las salidas y los valores, todo por nombre (los ID del editor y los del ejemplo no coinciden)."""
        from helpers import S as SEG, records, session
        from grafcet.model import validate_model
        res = validate_model(doc)
        self.assertTrue(res.can_simulate, [d.message for d in res.diagnostics])
        nom = {s["id"]: s["label"] for s in doc["steps"]} | {v["id"]: v["name"] for v in doc["variables"]}
        var = {v["name"]: v["id"] for v in doc["variables"]}
        ses = session(res.model, None, [(t * SEG, 0, {var[k]: x for k, x in ch.items()}) for t, ch in pasos],
                      horizon=horizonte * SEG)
        ses.run()
        return [(r["timeUs"], sorted(nom[x] for x in r["situation"]), {nom[k]: x for k, x in r["outputs"].items()},
                 {nom[k]: x for k, x in r["values"].items()}) for r in records(ses, "estable")]

    def test_SEDI40_contador_por_flanco_con_el_editor(self):
        """REQ-EDT-07, REQ-ACT-01, REQ-SIM-03: el ejemplo «contador-flanco» del responsable, hecho con el editor
        (variables en su panel, receptividades con bloques, acciones con su panel de opciones), simula igual que el ejemplo: I00
        lleva a 1 e I01 vuelve a 0; en 1, cada subida de I02 suma 1 a CT y mantenerla no vuelve a contar; Q00 y Q01
        encendidas en 1."""
        from escritorio import bloques
        from grafcet.examples import EJEMPLOS
        w = self.w
        w.nuevo()
        e, pv = w.edicion, w.variables
        for nombre, papel, tipo in (("I00", "input", "bool"), ("I01", "input", "bool"), ("I02", "input", "bool"),
                                    ("Q00", "output", "bool"), ("Q01", "output", "bool"), ("CT", "internal", "int")):
            pv.nueva()
            fila = pv.tabla.rowCount() - 1
            pv.tabla.item(fila, 0).setText(nombre)  # como al escribir en la tabla
            for col, valor in ((1, papel), (2, {"kind": tipo})):
                pv.elegir(fila, col, valor)  # lo que hace el desplegable de la celda
        self.assertEqual([(v["name"], v["role"], v["type"]["kind"]) for v in e.ed.model["variables"]],
                         [("I00", "input", "bool"), ("I01", "input", "bool"), ("I02", "input", "bool"),
                          ("Q00", "output", "bool"), ("Q01", "output", "bool"), ("CT", "internal", "int")])
        s0 = e.poner_etapa(QPointF(260, 60))
        e.tipo_etapa(s0, True)
        e.seleccionar([s0])
        s1 = e.anadir_debajo()
        t1 = next(t["id"] for t in e.M["transitions"])
        e.seleccionar([s1])
        t2 = e.poner_transicion(QPointF(260, 300))
        e.conectar(s1, t2)
        e.conectar(t2, s0)
        for tid, nombre in ((t1, "I00"), (t2, "I01")):  # receptividades con el cajón de entradas
            e.seleccionar([tid])
            w.props.prog.colocar(bloques.var(nombre, "input"))
        self.assertEqual((e.texto_condicion(t1), e.texto_condicion(t2)), ("I00", "I01"))
        for datos in ({"tipo": "evento", "variable": "CT", "valor": "CT + 1"}, {"tipo": "continua", "variable": "Q00"},
                      {"tipo": "continua", "variable": "Q01"}):
            self.anadir_accion(s1, datos["tipo"], datos["variable"], datos.get("valor", ""))
            if datos["tipo"] == "evento":  # el evento se programa en el panel de opciones (la acción es un borrador hasta entonces)
                borrador = e.acciones(s1)[0]
                self.assertTrue(borrador["borrador"] and e.faltan(borrador) == ["evento"])
                w.editar_accion(s1, borrador["id"])  # sus opciones, en el panel inferior
                self.assertEqual(w.props.objetivo_bloques(), ("accion", borrador["id"], "evento"))
                w.props.prog.colocar(bloques.var("I02", "input"))
                w.props.prog.lienzo.soltar((), bloques.nuevo("sube"))  # un flanco sobre un bloque ocupado lo envuelve
                self.assertEqual(w.props.prog.texto(), "↑I02")
                self.assertFalse(e.acciones(s1)[0].get("borrador"), "con su evento, pasa al modelo")
        self.assertEqual([e.resumen_accion(x) for x in e.acciones(s1)],
                         ["CT := CT + 1   (con ↑I02)", "Q00   (continua)", "Q01   (continua)"])
        pasos = [(1, {"I00": True}), (2, {"I00": False}), (3, {"I02": True}), (4, {"I02": False}), (5, {"I02": True}),
                 (6, {}), (7, {"I02": False}), (8, {"I01": True}), (9, {"I02": True}), (10, {"I02": False})]
        ejemplo, _ = EJEMPLOS["contador-flanco"][2]()
        hecho = self._recorrido(e.ed.model, pasos, 12)
        self.assertEqual(hecho, self._recorrido(ejemplo.doc, pasos, 12))
        self.assertIn(("5000000", ["1"], {"Q00": True, "Q01": True}), [x[:3] for x in hecho])
        self.assertEqual([x[3]["CT"] for x in hecho if "CT" in x[3]][-1], "2",
                         "dos subidas en 1; mantener I02 o subir en 0 no cuenta")

    def test_SEDI41_retardo_3s_X1_con_el_asistente(self):
        """REQ-EDT-02, REQ-TMP-01: con la etapa X1 en bloques y el bloque «temporizar» encima, la receptividad es 3s/X1,
        se guarda como delay(3 s, active(1), 0 s) y la transición franquea a los 3 s de activarse la etapa 1."""
        from escritorio import bloques
        w = self.w
        w.nuevo()
        e = w.edicion
        s0 = e.poner_etapa(QPointF(260, 60))
        e.tipo_etapa(s0, True)
        e.seleccionar([s0])
        s1 = e.anadir_debajo()
        t1 = next(t["id"] for t in e.M["transitions"])
        e.nueva_variable("I00")
        e.seleccionar([s1])
        t2 = e.poner_transicion(QPointF(260, 300))
        e.conectar(s1, t2)
        e.conectar(t2, s0)
        e.seleccionar([t1])
        w.props.prog.colocar(bloques.var("I00", "input"))
        e.seleccionar([t2])
        prog = w.props.prog
        prog.colocar(bloques.nuevo("etapa", n="X1"))
        prog.lienzo.soltar((), bloques.nuevo("temp"))  # temporizar sobre X1: la envuelve, con t1 = 3s
        self.assertEqual(w.props.t_texto.text(), "3s/X1")
        self.assertEqual(e.texto_condicion(t2), "delay(3 s, active(`1`), 0 s)")
        self.assertEqual(prog.lienzo.arbol["k"], "temp")
        hecho = self._recorrido(e.ed.model, [(1, {"I00": True}), (2, {"I00": False})], 8)
        self.assertEqual([(x[0], x[1]) for x in hecho], [("0", ["0"]), ("1000000", ["1"]), ("2000000", ["1"]),
                                                         ("4000000", ["0"])])

    def test_SEDI43_panel_de_variables(self):
        """REQ-EDT-07, REQ-EDT-06: el diccionario muestra nombre, papel y tipo (sin inicial, unidad ni usos); renombrar
        actualiza los usos; papel y tipo se cambian; una variable usada no se quita y una sin usos sí; todo se deshace."""
        w = self.w
        e, ids, ts = self.secuencial()
        pv = w.variables
        nombres = [pv.tabla.item(r, 0).text() for r in range(pv.tabla.rowCount())]
        self.assertEqual(nombres, ["marcha", "paro"])
        self.assertEqual(pv.tabla.columnCount(), 3, "Nombre, Papel y Tipo")
        pv.tabla.item(0, 0).setText("Marcha")
        self.assertEqual(e.texto_condicion(ts["t1"]), "Marcha", "el renombrado llega a la receptividad")
        pv.elegir(1, 1, "output")
        self.assertEqual(e.ed.model["variables"][1]["role"], "output")
        pv.tabla.selectRow(0)
        pv.quitar()
        self.assertIn("se usa", pv.msg.text())
        pv.nueva()
        self.assertEqual(len(e.ed.model["variables"]), 2, "la fila nueva no está en el modelo hasta tener nombre")
        pv.tabla.item(2, 0).setText("Rearme")
        self.assertEqual(e.ed.model["variables"][-1]["name"], "Rearme")
        pv.tabla.selectRow(2)
        pv.quitar()
        self.assertEqual(len(e.ed.model["variables"]), 2)
        e.deshacer()
        self.assertEqual(len(e.ed.model["variables"]), 3)
        e.deshacer()
        self.assertEqual(len(e.ed.model["variables"]), 2, "crear la variable con su nombre fue una operación")

    def test_SEDI44_acciones_desde_el_dibujo(self):
        """REQ-ACT-01, REQ-EDT-02: botón derecho en una etapa: «Añadir acción…»; la acción se dibuja a su derecha; un
        clic en su caja selecciona la etapa y la señala; doble clic la edita en el panel de opciones, que crea la
        variable si no existe y aplica cada cambio como una operación de deshacer."""
        w = self.w
        e, ids, ts = self.secuencial()
        c = centro(e.M, ids["1"])
        self.assertEqual([t for t, _ in e.menu(QPointF(c.x() + 400, c.y()))],
                         ["Equidistanciar todo el lienzo"],
                         "en un hueco, un grafcet parcial nuevo y equidistanciar el lienzo (hay una cadena)")
        opciones = dict(e.menu(c))
        self.assertEqual(list(opciones), ["Colocación de las acciones", "-", "Tipo de etapa",
                                          "Equidistanciar alturas de la cadena"])
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        e.anadir_accion(ids["1"])  # crea la acción continua unida a la etapa (borrador, sin variable) y abre Editar
        (borrador,) = e.ed.draft_actions()
        self.assertEqual((pedidas, borrador["etapa"], borrador["tipo"]), ([(ids["1"], borrador["id"])], ids["1"], "continua"))
        e.deshacer()
        self.assertEqual(e.ed.draft_actions(), [])
        d = self.panel_accion(ids["1"])
        self.poner_tipo(d, "activacion")
        self.assertNotIn("CT", d.ofrecidas())
        e.nueva_variable("CT", "internal", {"kind": "int"})  # se crea en la tabla de variables, no desde el panel de la acción
        d = self.panel_accion(ids["1"], e.acciones(ids["1"])[0]["id"])
        self.assertIn("CT", d.ofrecidas())
        n = len(e.ed.undo_stack)
        d.variable.setCurrentText("CT")
        self.assertEqual(d.variable.currentText(), "CT")
        self.assertEqual(len(e.ed.undo_stack), n + 1, "la elección de la variable, una operación")
        self.assertEqual(e.faltan(e.acciones(ids["1"])[0]), ["valor"], "sin valor, la acción queda como borrador")
        d._desde_bloques("CT + 1")
        self.assertEqual(len(e.ed.undo_stack), n + 2, "completar la acción es otra operación")
        self.assertEqual(e.datos_accion(e.acciones(ids["1"])[0]["id"])["valor"], "CT + 1")
        self.assertTrue(e.ed.validate().can_simulate)
        aid = e.acciones(ids["1"])[0]["id"]
        caja = next(x for x in w.diagrama.cajas_acciones if x["id"] == aid)
        x, y, ancho, alto = caja["rect"]
        dentro = QPointF(x + ancho / 2, y + alto / 2)
        e.prensar(dentro)
        e.soltar(dentro)
        self.assertEqual((e.sel, e.accion), ([ids["1"]], aid))
        self.assertIn(f"accion:{aid}", e.seleccion_dibujo())
        self.assertEqual((w.props.pagina, w.props.accion.aid), ("accion", aid), "sus opciones, en el panel inferior")
        self.assertIn("Quitar", dict(e.menu(dentro)))
        e.doble(dentro)
        self.assertEqual(pedidas[-1], (ids["1"], aid))
        d = self.panel_accion(ids["1"], aid)  # cambiarla: memorizada al desactivar, CT := 0
        self.assertEqual((d.clave_tipo, d.variable.currentText(), d.valor.text()), ("activacion", "CT", "CT + 1"))
        self.poner_tipo(d, "desactivacion")
        d._desde_bloques("0")
        self.assertEqual(e.datos_accion(aid)["tipo"], "desactivacion")
        self.assertEqual((e.datos_accion(aid)["valor"], e.acciones(ids["1"])[0]["id"]), ("0", aid), "conserva su ID")
        e.quitar_accion(aid)
        self.assertEqual(e.acciones(ids["1"]), [])
        for _ in range(3):  # quitar, el valor y el tipo: una operación cada uno
            e.deshacer()
        self.assertEqual(e.datos_accion(aid)["tipo"], "activacion")

    def test_SEDI58_receptividad_1_y_accion_entera(self):
        """REQ-EDT-02, REQ-ACT-01: una receptividad «1» se guarda como true y se valida sin D-TIPO; el valor de una acción
        memorizada de una variable entera, n := 1, sigue siendo el entero 1."""
        e, ids, ts = self.secuencial()
        e.condicion(ts["t1"], "1")
        self.assertEqual(e.texto_condicion(ts["t1"]), "true")
        self.assertEqual(e.texto_usuario(ts["t1"]), "1")
        self.assertNotIn("D-TIPO", [d.code for d in e.ed.validate().diagnostics])
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "activacion", "variable": "n", "valor": "1", "evento": ""},
                                         None, ("internal", "int")))
        a = e.acciones(ids["1"])[0]
        valor = next(x["text"] for x in e.ed.model["expressions"] if x["id"] == e.ed.get(a["id"])["valueRef"])
        self.assertEqual(valor, "1")
        self.assertEqual(e.datos_accion(a["id"])["valor"], "1")
        self.assertNotIn("D-TIPO", [d.code for d in e.ed.validate().diagnostics])

    def test_SEDI48_panel_de_acciones_vista_previa_y_avisos(self):
        """REQ-ACT-01, REQ-EDT-02: el panel de la acción no lleva programador de condición dentro (la condición y el evento se
        programan con bloques a su lado); una variable no válida para el tipo se aplica y se avisa en naranja con
        parpadeo; un X1 ambiguo del valor se avisa."""
        from escritorio.diagrama import COL
        e, ids, ts = self.secuencial()
        d = self.panel_accion(ids["1"])
        self.assertFalse(hasattr(d, "cond") or hasattr(d, "evento"), "sin programador de condición dentro")
        self.poner_tipo(d, "evento")
        d._desde_bloques("1")
        n = len(e.ed.undo_stack)
        d.variable.setCurrentText("paro")  # una entrada: no se puede escribir (ni se ofrece en la lista)
        self.assertEqual(len(e.ed.undo_stack), n + 1, "se aplica al momento, como una operación")
        self.assertIn("entrada", d.msg.text())
        self.assertIn(COL["glow"], d.msg.styleSheet(), "el aviso, en naranja")
        self.assertEqual(d.parpadeo.ids, {"variable"})
        self.assertEqual(e.acciones(ids["1"])[0]["variable"], "paro")
        self.assertEqual(e.acciones(ids["1"])[0]["tipo"], "evento")
        # continua con una variable no booleana: el aviso, y la acción queda como borrador
        e.nueva_variable("CT", "internal", {"kind": "int"})
        d = self.panel_accion(ids["1"])
        d.variable.setCurrentText("CT")
        self.assertIn("booleana", d.msg.text())
        self.assertTrue(e.acciones(ids["1"])[-1]["borrador"])
        # X1 ambiguo
        e.nueva_variable("M1", "internal")
        e.ed.add_step(e.raiz, "E1")
        e.cambia()
        d.valor.setText("X1")  # oculto en una continua: no cuenta para el aviso
        self.assertNotIn("puede ser la etapa", d.msg.text())
        d = self.panel_accion(ids["1"])
        d.variable.setCurrentText("M1")
        self.poner_tipo(d, "activacion")
        d._desde_bloques("X1")
        self.assertIn("puede ser la etapa E1 o la etapa 1", d.msg.text())
        self.assertIn("active(`1`)", d.msg.text())
        e.seleccionar([ts["t1"]])  # y el panel de la transición avisa igual
        self.w.props.t_texto.setText("X1")
        self.w.props._previsualizar()
        self.assertIn("puede ser la etapa E1 o la etapa 1", self.w.props.t_estado.text())

    def test_SEDI49_memorias_en_la_interfaz(self):
        """REQ-EDT-07: las variables internas se llaman «memorias» en la interfaz; el papel guardado sigue siendo
        «internal»."""
        from escritorio.variables import PAPELES
        e, ids, ts = self.secuencial()
        self.assertIn(("internal", "Memoria"), PAPELES)
        e.nueva_variable("CT", "internal", {"kind": "int"})
        d = self.anadir_accion(ids["1"], "activacion", "CT")
        d._desde_bloques("CT + 1")
        self.assertEqual(next(v for v in e.ed.model["variables"] if v["name"] == "CT")["role"], "internal")
        pv = self.w.variables
        fila = [pv.tabla.item(r, 0).text() for r in range(pv.tabla.rowCount())].index("CT")
        self.assertEqual(pv.tabla.item(fila, 1).text(), "Memoria")

    def test_SEDI52_texto_y_bloques_sincronizados(self):
        """REQ-EDT-02: un texto (el guardado) se pasa a bloques con `poner`; uno que no se puede analizar no cambia los
        bloques y avisa; un cambio de bloques escribe el texto y se aplica al modelo."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ts["t1"]])
        prog, p = w.props.prog, w.props
        self.assertEqual((prog.lienzo.arbol["k"], prog.texto()), ("var", "marcha"))
        prog.poner("↑marcha AND NOT X1")
        a = prog.lienzo.arbol
        self.assertEqual((a["k"], a["a"]["k"], a["b"]["k"], a["b"]["a"]["n"]), ("y", "sube", "no", "X1"))
        self.assertTrue(prog.aviso.isHidden())
        prog.poner("marcha AND")  # a medias: los bloques se quedan como estaban
        self.assertEqual(prog.texto(), "↑marcha AND NOT X1")
        self.assertFalse(prog.aviso.isHidden())
        self.assertTrue(prog.aviso.text().startswith("No se puede pasar a bloques: "), prog.aviso.text())
        self.assertLess(len(prog.aviso.text()), 120, "una línea breve")
        prog.poner("marcha AND ?")  # un hueco es un hueco
        self.assertTrue(prog.aviso.isHidden())
        self.assertIsNone(prog.lienzo.arbol["b"])
        n = len(e.ed.undo_stack)  # un cambio de bloques escribe el texto y se aplica, con una operación del editor
        prog.lienzo.soltar(("b",), bloques.var("paro", "input"))
        self.assertEqual((p.t_texto.text(), e.texto_condicion(ts["t1"]), len(e.ed.undo_stack)),
                         ("marcha AND paro", "marcha AND paro", n + 1))
        # poner() no emite cambiado: no se aplica nada
        emitidos = []
        prog.cambiado.connect(emitidos.append)
        prog.poner("paro")
        self.assertEqual((emitidos, prog.texto()), ([], "paro"))

    def test_SEDI53_deshacer_cambios_de_bloques(self):
        """REQ-EDT-02: en el panel de la transición cada cambio de bloques es una operación del editor y se deshace con su
        deshacer; un programador sin editor detrás tiene su historial local."""
        from escritorio import bloques
        from escritorio.bloques import Programador
        from PySide6.QtGui import QShortcut
        e, ids, ts = self.secuencial()
        e.seleccionar([ts["t1"]])
        prog = self.w.props.prog
        prog.lienzo.soltar((), bloques.nuevo("no"))  # NOT marcha
        prog.lienzo.soltar((), bloques.nuevo("sube"))  # ↑ sobre NOT marcha: lo envuelve
        self.assertEqual(e.texto_usuario(ts["t1"]), "↑(NOT marcha)")
        e.deshacer()
        self.assertEqual((e.texto_usuario(ts["t1"]), prog.texto()), ("NOT marcha", "NOT marcha"))
        e.deshacer()
        self.assertEqual((e.texto_usuario(ts["t1"]), prog.texto()), ("marcha", "marcha"))
        e.rehacer()
        self.assertEqual(prog.texto(), "NOT marcha")
        prog.al_deshacer()  # lo que usa la ventana ampliada
        self.assertEqual(prog.texto(), "marcha")
        # un programador con historial local (el que no depende del deshacer del editor)
        cond = Programador(e.fuente_bloques, historial=True)
        self.assertTrue(cond.historial and len(cond.findChildren(QShortcut)) == 3, "Ctrl+Z, Ctrl+Mayús+Z, Ctrl+Y")
        emitidos = []
        cond.cambiado.connect(emitidos.append)
        cond.colocar(bloques.var("marcha", "input"))
        cond.lienzo.soltar((), bloques.nuevo("no"))
        self.assertEqual(cond.texto(), "NOT marcha")
        cond.deshacer()
        self.assertEqual(cond.texto(), "marcha")
        cond.deshacer()
        self.assertEqual(cond.texto(), "")
        cond.deshacer()  # nada más que deshacer
        self.assertEqual(cond.texto(), "")
        cond.rehacer()
        cond.rehacer()
        self.assertEqual(cond.texto(), "NOT marcha")
        self.assertEqual(emitidos, ["marcha", "NOT marcha", "marcha", "", "marcha", "NOT marcha"])
        cond.poner("paro")  # lo que viene de fuera borra el historial
        cond.deshacer()
        self.assertEqual(cond.texto(), "paro")

    def test_SEDI59_panel_de_opciones_abajo_sin_pestanas(self):
        """REQ-EDT-02: el panel inferior, al editar, es un único panel «Opciones» (sin pestañas) con la receptividad de la
        transición seleccionada; al simular muestra la traza; hay dos programadores (el de la receptividad o la condición y
        el del valor de una acción) y el panel izquierdo no tiene ninguno."""
        from PySide6.QtWidgets import QTabWidget
        from escritorio.bloques import Programador
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w._abrir_opciones()
        w.show()
        QApplication.processEvents()
        self.assertFalse(hasattr(w, "i_bloques"))
        self.assertEqual(set(w.pestanas), {"izquierdo", "derecho", "inferior"})
        self.assertTrue(all(not w.props.isAncestorOf(t) for t in w.pestanas.values()),
                        "las pestañas de recuperación están fuera del editor")
        self.assertEqual([t for t in w.findChildren(QTabWidget) if t.isAncestorOf(w.props) or w.inferior.isAncestorOf(t)], [],
                         "el panel inferior no tiene pestañas")
        self.assertIs(w.inferior.currentWidget(), w.props, "en Editar, las opciones")
        self.assertEqual(set(w.findChildren(Programador)), {w.props.prog, w.props.accion.prog})
        self.assertTrue(w.props.isAncestorOf(w.props.prog) and not w.dock.isAncestorOf(w.props.prog))
        e.seleccionar([])
        QApplication.processEvents()
        self.assertEqual(w.props.titulo.text(), "Propiedades")
        self.assertTrue(not w.props.prog.isVisible() and w.props.pagina == "vacio")
        self.assertEqual(w.props.l_vacio.text(), "Haga clic en un elemento del dibujo para ver y cambiar sus opciones.")
        e.seleccionar([ts["t2"]])
        self.assertEqual((w.props.prog.texto(), w.props.prog.isVisible(), w.props.pagina), ("paro", True, "transicion"))
        self.assertIn("t2", w.props.l_bloques.text())
        self.assertIn("Transición", w.props.titulo.text())
        e.poner_condicion(ts["t2"], "paro AND marcha", crear=True)
        self.assertEqual(w.props.prog.texto(), "paro AND marcha")
        e.seleccionar([ids["0"]])  # una etapa: sus opciones, sin programador
        self.assertEqual((w.props.prog.isVisible(), w.props.pagina), (False, "etapa"))
        e.seleccionar([ts["t1"]])
        w.cambiar_modo("simular")
        self.assertIs(w.inferior.currentWidget().findChild(type(w.traza)), w.traza, "en Simular, la traza")
        self.assertEqual(w.inferior.currentIndex(), 0)
        w.cambiar_modo("editar")
        self.assertIs(w.inferior.currentWidget(), w.props)

    def test_SEDI60_bloques_y_texto_sincronizados_en_el_panel(self):
        """REQ-EDT-02: un cambio de bloques escribe el texto de la fórmula del panel de opciones y es una operación del
        editor (Ctrl+Z); lo escrito en el texto aparece en los bloques; el panel izquierdo (la paleta) no lleva el
        programador."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        p, prog = w.props, w.props.prog
        e.seleccionar([ts["t1"]])
        self.assertIsNone(w.dock.findChild(bloques.Programador), "el panel izquierdo no tiene el programador")
        n = len(e.ed.undo_stack)
        prog.lienzo.soltar((), bloques.nuevo("no"))
        self.assertEqual((p.t_texto.text(), e.texto_condicion(ts["t1"]), len(e.ed.undo_stack)),
                         ("NOT marcha", "NOT marcha", n + 1))
        e.deshacer()
        self.assertEqual((p.t_texto.text(), prog.texto()), ("marcha", "marcha"))
        prog.poner("paro AND marcha")
        self.assertEqual((prog.lienzo.arbol["k"], prog.texto()), ("y", "paro AND marcha"))
        self.assertEqual(len(e.ed.undo_stack), n, "poner un texto en los bloques no aplica nada")

    def test_SEDI61_panel_plegado_se_despliega_con_el_doble_clic(self):
        """REQ-EDT-02: con el panel inferior plegado no se despliega solo al seleccionar; el doble clic en una transición,
        etapa o acción (y «Editar…») lo despliega con sus opciones; no hay botones «Bloques abajo»."""
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        w._mostrar_panel("inferior", False)
        e.seleccionar([ts["t1"]])
        QApplication.processEvents()
        self.assertTrue(w.inferior.isHidden(), "no se despliega por su cuenta")
        self.assertFalse(any(hasattr(w.props, n) for n in ("t_abajo", "s_abajo", "actualizar_boton")))
        e.doble(centro(e.M, ts["t1"]))  # doble clic en la transición
        self.assertFalse(w.inferior.isHidden())
        self.assertTrue(w.a_inferior.isChecked())
        self.assertEqual((w.props.pagina, w.props.prog.texto()), ("transicion", "marcha"))
        w._mostrar_panel("inferior", False)
        e.doble(centro(e.M, ids["1"]))  # en una etapa: su etiqueta
        self.assertFalse(w.inferior.isHidden())
        self.assertEqual((w.props.pagina, e.sel), ("etapa", [ids["1"]]))
        self.assertTrue(w.props.s_etiqueta.hasFocus() or w.props.s_etiqueta.isVisible())
        w._mostrar_panel("inferior", False)
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00", "condicion": ""}))
        aid = e.acciones(ids["1"])[0]["id"]
        w.editar_accion(ids["1"], aid)  # «Editar…»: la acción, en el panel
        self.assertFalse(w.inferior.isHidden())
        self.assertEqual((w.props.pagina, w.props.continua, w.props.accion.aid), ("vacio", True, aid), "una continua: solo la frase")

    def test_SEDI62_ficha_accion_en_la_paleta(self):
        """REQ-ACT-01, REQ-EDT-02: la paleta ofrece la ficha «Acción» (continua) con su figura (el lado izquierdo, bajo
        el puntero); soltada en cualquier sitio crea una acción suelta sin abrir ningún diálogo; «accion» a secas sigue
        siendo una continua."""
        from escritorio.propiedades import figura
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        textos = [w.paleta.item(k).text() for k in range(w.paleta.count())]
        self.assertEqual(textos[7], "Continua")
        pm, punto = figura("accion:continua", 1.0, 1.0)
        self.assertGreater(pm.width(), pm.height(), "un rectángulo de acción, más ancho que alto")
        self.assertTrue(pm.rect().contains(punto))
        self.assertEqual(punto.x(), 8, "bajo el puntero, el borde izquierdo de la caja")
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        n, acciones = len(e.ed.undo_stack), len(e.ed.model["actions"])
        e.colocar("accion", QPointF(900, 400))  # en cualquier sitio, también fuera de toda etapa
        self.assertEqual((pedidas, len(e.ed.undo_stack), len(e.ed.model["actions"])), ([], n + 1, acciones))
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], "variable" in b, "etapa" in b), ("continua", False, False))
        self.assertEqual(e.sel, [b["id"]])
        e.colocar("accion:continua", centro(e.M, ids["1"]))  # encima de una etapa no se coloca (S-EDI115)
        self.assertEqual((pedidas, len(e.ed.draft_actions())), ([], 1))
        e.colocar("accion:continua", QPointF(900, 600))  # en otro hueco, otra suelta sin pedir nada
        self.assertEqual((pedidas, len(e.ed.draft_actions())), ([], 2))

    def test_SEDI63_y_y_o_con_colores_distintos(self):
        """REQ-EDT-02: «y» y «o» siguen en Operadores pero se dibujan con colores distintos entre sí y del resto de
        categorías (paleta, área y ventana ampliada), con texto blanco."""
        from escritorio.bloques import COLORES, Motor, nuevo
        y, o = COLORES["y"], COLORES["o"]
        resto = {c for c in COLORES if c not in ("y", "o")}
        self.assertNotEqual(y, o)
        self.assertTrue(all(COLORES[c].lower() not in (y.lower(), o.lower()) for c in resto))
        m = Motor(lambda: ({}, []))
        self.assertEqual((m.categoria(nuevo("y")), m.categoria(nuevo("o")), m.categoria(nuevo("no"))), ("y", "o", "operador"))
        e, ids, ts = self.secuencial()
        e.seleccionar([ts["t1"]])
        prog = self.w.props.prog
        prog.poner("marcha AND paro OR marcha")
        for p in (prog,):  # el área: el motor da la categoría de cada bloque
            self.assertEqual((p.lienzo.motor.categoria(p.lienzo.arbol), p.lienzo.motor.categoria(p.lienzo.arbol["a"])),
                             ("o", "y"))


    # -- ronda P-IMP-41: arrastre de las paletas, variables al día, lazo y acciones sueltas ---------------------------
    def _accion_q(self, e, ids):
        """Variables Q00 (salida) y CT (memoria entera) y una acción continua Q00 en la etapa 1: devuelve su ID."""
        e.nueva_variable("Q00", "output", {"kind": "bool"})
        e.nueva_variable("CT", "internal", {"kind": "int"})
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00", "condicion": ""}))
        return e.acciones(ids["1"])[0]["id"]

    def _enlazar_accion(self, e, did, destino):
        """Arrastra con el ratón del punto de unión de la acción suelta (o de una etapa) hasta `destino` (un punto)."""
        from escritorio.diagrama import anclas
        pa = anclas(e.M, did)[0]["pos"]
        e.herramienta = "seleccionar"
        e.prensar(pa)
        e.mover(destino)
        e.soltar(destino)

    def test_SEDI65_arrastre_de_las_paletas(self):
        """REQ-EDT-02: la paleta «Elementos» se arrastra (el arrastre se activa después de fijar el modo de iconos y el
        movimiento estático, que lo desactiva): propiedades, gesto real del ratón y QDrag con la figura; la paleta de
        bloques y su área aceptan el arrastre."""
        from PySide6.QtWidgets import QAbstractItemView, QListView
        from escritorio import bloques, propiedades
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        QApplication.processEvents()
        pal = w.paleta
        self.assertTrue(pal.dragEnabled())
        self.assertEqual(pal.dragDropMode(), QAbstractItemView.DragDropMode.DragOnly)
        self.assertEqual(pal.movement(), QListView.Movement.Static)
        llamadas = []
        with mock.patch.object(propiedades.Paleta, "startDrag", lambda self, a: llamadas.append(a)):  # el gesto real
            r = pal.visualItemRect(pal.item(1))
            vp = pal.viewport()
            QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, r.center())
            QTest.mouseMove(vp, r.center() + QPoint(40, 40))
            QTest.mouseMove(vp, r.center() + QPoint(80, 80))
            QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, r.center() + QPoint(80, 80))
        self.assertEqual(len(llamadas), 1, "pulsar y arrastrar sobre una ficha empieza el arrastre")
        capturados = []

        class FalsoDrag:
            def __init__(self, origen):
                self.datos = {}
                capturados.append(self)

            def setMimeData(self, m):
                self.datos["texto"] = m.text()

            def setPixmap(self, pm):
                self.datos["pm"] = pm

            def setHotSpot(self, p):
                self.datos["punto"] = p

            def exec(self, *a):
                self.datos["exec"] = a
                return Qt.DropAction.IgnoreAction
        with mock.patch.object(propiedades, "QDrag", FalsoDrag):
            for fila in range(pal.count()):
                pal.setCurrentRow(fila)
                pal.startDrag(Qt.DropAction.CopyAction)
        self.assertEqual([c.datos["texto"] for c in capturados], list(propiedades.COLOCABLES))
        for c in capturados:
            self.assertFalse(c.datos["pm"].isNull())
            self.assertTrue(c.datos["pm"].rect().contains(c.datos["punto"]))
        # soltar en el dibujo (el evento que genera Qt al terminar el arrastre)
        mime = QMimeData()
        mime.setText("accion")
        n = len(e.ed.draft_actions())
        w.diagrama.dropEvent(QDropEvent(QPointF(300, 300), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                                        Qt.KeyboardModifier.NoModifier))
        self.assertEqual(len(e.ed.draft_actions()), n + 1, "soltar la ficha en el dibujo la coloca")
        # la paleta de bloques arrastra con su propio QDrag y el área (y la papelera) aceptan lo que se suelta
        prog = w.props.prog
        self.assertTrue(prog.lienzo.acceptDrops() and prog.papelera.acceptDrops())
        capturados.clear()
        with mock.patch.object(bloques, "QDrag", FalsoDrag), mock.patch.object(bloques.QDrag, "exec", create=True):
            prog.paleta._arrastrar((0,))
        self.assertEqual(len(capturados), 1)

    def test_SEDI66_variables_nuevas_al_dia_en_el_programador(self):
        """REQ-EDT-02, REQ-EDT-07: al crear, renombrar, quitar o cambiar de papel una variable (panel Variables, panel de
        la acción, «Crear las que faltan») la paleta de bloques (una ficha por variable), los desplegables y los colores del
        área, y la ventana ampliada se ponen al día en el acto, sin tener que volver a elegir la transición."""
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        e.seleccionar([ts["t1"]])
        prog = w.props.prog
        prog.elegir_categoria("variables")
        def salidas():
            return [b for b in prog.paleta.bloques() if b.get("papel") == "output"]
        self.assertEqual(salidas(), [], "sin salidas, el grupo no se ofrece")
        e.nueva_variable("Q05", "output", {"kind": "bool"})  # lo que hace «Nueva variable» del panel Variables
        self.assertEqual(salidas()[0]["n"], "Q05", "la paleta se llena en el acto")
        self.assertEqual(prog.opciones("salida"), [("Q05", "Q05")])
        e.nueva_variable("Q06", "output", {"kind": "bool"})
        self.assertEqual(prog.opciones("salida"), [("Q05", "Q05"), ("Q06", "Q06")])
        self.assertEqual([b["n"] for b in salidas()], ["Q05", "Q06"], "una ficha por salida")
        # renombrar y cambiar de papel (panel Variables)
        vid = next(x["id"] for x in e.ed.model["variables"] if x["name"] == "Q05")
        self.assertIsNone(e.cambiar_variable(vid, nombre="Motor"))
        self.assertEqual(prog.opciones("salida"), [("Motor", "Motor"), ("Q06", "Q06")])
        self.assertIsNone(e.cambiar_variable(vid, role="internal"))
        self.assertEqual(prog.opciones("salida"), [("Q06", "Q06")])
        self.assertEqual(prog.opciones("interna"), [("Motor", "Motor")])
        # el color del bloque del área sigue al papel: una variable que cambia de papel cambia de categoría
        e.poner_condicion(ts["t1"], "Motor")
        self.assertEqual(prog.texto(), "Motor")
        self.assertEqual(prog.lienzo.motor.categoria(prog.lienzo.arbol), "interna")
        self.assertIsNone(e.cambiar_variable(vid, role="output"))
        self.assertEqual(prog.lienzo.motor.categoria(prog.lienzo.arbol), "salida", "el área, al día sin tocar la fórmula")
        e.poner_condicion(ts["t1"], "marcha")
        # quitar
        self.assertIsNone(e.quitar_variable(next(x["id"] for x in e.ed.model["variables"] if x["name"] == "Q06")))
        self.assertEqual(prog.opciones("salida"), [("Motor", "Motor")])
        # «Crear las que faltan»
        prog.elegir_categoria("variables")
        w.props.t_texto.setText("nueva_in AND marcha")
        w.props._previsualizar()
        self.assertFalse(w.props.t_crear.isHidden())
        w.props.t_crear.click()
        self.assertIn(("nueva_in", "nueva_in"), prog.opciones("entrada"))

    def test_SEDI67_carpetas_en_su_orden_y_temporizadores(self):
        """REQ-EDT-02: Variables, Operadores, Temporizadores, Comparaciones y Constantes, en ese orden;
        la categoría «Tiempo» se llama «Temporizadores»."""
        from escritorio.bloques import CATEGORIAS, Programador
        e, ids, ts = self.secuencial()
        textos = ["Variables", "Operadores", "Temporizadores", "Comparaciones", "Constantes"]
        self.assertEqual([t for _, t in CATEGORIAS], textos)
        prog = self.w.props.prog
        self.assertEqual([b.text() for b in prog.categorias.values()], textos)
        self.assertNotIn("Tiempo", [b.text() for b in prog.categorias.values()])
        self.assertEqual(prog.categorias["tiempo"].text(), "Temporizadores")
        self.assertEqual(prog.paleta.clave, "variables")

    def test_SEDI68_receptividad_en_el_panel_con_texto_de_solo_lectura(self):
        """REQ-EDT-02: toda la receptividad está a la derecha del panel de opciones (texto de la fórmula, «Escrito», «Se
        dibuja» y «Crear las que faltan»); su columna estrecha de la izquierda solo lleva etiqueta, «Mostrar etiqueta» y
        comentario. El texto se ve (con la notación del dibujo) pero no se edita: no hay «Escribir a mano»."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        p, prog = w.props, w.props.prog
        e.seleccionar([ts["t1"]])
        QApplication.processEvents()
        izq = p.izq.widget(2)  # la columna de la transición, a la izquierda del panel de opciones
        derecha = p.pagina_bloques
        for campo in (p.t_texto, p.t_vista, p.t_dibujo, p.t_crear, p.t_estado):
            self.assertFalse(izq.isAncestorOf(campo), "no están en la columna estrecha")
            self.assertTrue(derecha.isAncestorOf(campo), "están a su derecha")
        self.assertTrue(izq.isAncestorOf(p.t_etiqueta) and izq.isAncestorOf(p.t_mostrar) and izq.isAncestorOf(p.t_comentario))
        self.assertTrue(w.inferior.isAncestorOf(izq) and not w.dock.isAncestorOf(izq), "y todo en el panel de abajo")
        self.assertEqual(sorted(x.text() for x in izq.findChildren(QLabel) if x.text() in ("Etiqueta", "Texto", "Escrito", "Se dibuja")),
                         ["Etiqueta"])
        self.assertEqual(p.t_texto.text(), "marcha")
        self.assertTrue(p.t_texto.isReadOnly(), "se ve pero no se edita")
        self.assertFalse(hasattr(p, "t_manual"), "sin «Escribir a mano»")
        self.assertEqual(p.t_texto.focusPolicy(), Qt.FocusPolicy.NoFocus)
        # con bloques el texto sigue las piezas, sin dejar editar
        n = len(e.ed.undo_stack)
        prog.lienzo.soltar((), bloques.nuevo("no"))
        self.assertEqual((p.t_texto.text(), p.t_texto.isReadOnly(), len(e.ed.undo_stack)), ("NOT marcha", True, n + 1))
        # otra transición: sigue el texto de esa, también sin editar
        e.seleccionar([ts["t2"]])
        self.assertTrue(p.t_texto.isReadOnly())
        self.assertEqual(p.t_texto.text(), "paro")
        # lo que faltaba por crear, y el texto escrito de cómo se dibuja, están ahí
        p.t_texto.setText("↑nueva")
        p._previsualizar()
        self.assertFalse(p.t_crear.isHidden())
        self.assertIn("nueva", p.t_vista.text())
        p.t_texto.setText("↑marcha")
        p._previsualizar()
        self.assertIn("↑", p.t_dibujo.text())
        self.assertIn("correcta", p.t_estado.text())

    def test_SEDI69_lazo_de_seleccion(self):
        """REQ-EDT-02: arrastrar desde un hueco dibuja un rectángulo y selecciona lo que queda dentro (etapas,
        transiciones, simultaneidades y acciones); Mayús amplía; Supr lo borra en una sola operación de deshacer; no
        interfiere con arrastrar elementos ni con sacar enlaces de un punto de unión."""
        from escritorio.diagrama import anclas
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        e.confirmar_borrado = lambda plan: True
        aid = self._accion_q(e, ids)
        barra = e.poner_barra(QPointF(600, 300), "Y")
        suelta = e.poner_accion_suelta(QPointF(500, 500))

        class Mayus:
            def modifiers(self):
                return Qt.KeyboardModifier.ShiftModifier

            def buttons(self):
                return Qt.MouseButton.LeftButton

        def lazo(a, b, evento=None):
            e.herramienta = "seleccionar"
            e.prensar(a, evento)
            self.assertIsNotNone(e.lazo, "un hueco empieza el lazo")
            e.mover(QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2), evento)
            e.mover(b, evento)
            self.assertIsNotNone(w.diagrama.cuadro, "se ve el rectángulo")
            e.soltar(b, evento)
            self.assertIsNone(w.diagrama.cuadro)
        lazo(QPointF(20, 20), QPointF(170, 170))  # la etapa 0 (100, 60) y t1 (100, 140)
        self.assertEqual(set(e.sel), {ids["0"], ts["t1"]})
        self.assertIsNone(e.lazo)
        lazo(QPointF(20, 190), QPointF(700, 330), Mayus())  # amplía: etapa 1, t2, su acción y la barra
        self.assertEqual(set(e.sel), {ids["0"], ts["t1"], ids["1"], ts["t2"], aid, barra})
        lazo(QPointF(460, 460), QPointF(700, 540), Mayus())  # y la acción suelta
        self.assertIn(suelta, e.sel)
        self.assertEqual(len(e.sel), 7)
        self.assertEqual(set(e.sel) - {suelta, barra}, {ids["0"], ts["t1"], ids["1"], ts["t2"], aid})
        # sin Mayús, el lazo sustituye; un rectángulo que no encierra nada, deja la selección vacía
        lazo(QPointF(20, 190), QPointF(170, 250))
        self.assertEqual(e.sel, [ids["1"]], "la etapa entera; su acción cae fuera del rectángulo")
        lazo(QPointF(700, 20), QPointF(760, 60))
        self.assertEqual(e.sel, [])
        e.prensar(QPointF(700, 20))  # un clic en un hueco, sin arrastrar: deselecciona
        e.soltar(QPointF(700, 20))
        self.assertEqual((e.sel, e.lazo), ([], None))
        # Supr: una sola operación de deshacer
        lazo(QPointF(20, 20), QPointF(700, 330))
        lazo(QPointF(460, 460), QPointF(700, 540), Mayus())
        self.assertEqual(len(e.sel), 7)
        n = len(e.ed.undo_stack)
        modelo = copy.deepcopy(e.ed.model)
        w.a_borrar.trigger()
        self.assertEqual((e.sel, len(e.ed.undo_stack)), ([], n + 1))
        self.assertEqual((e.ed.model["steps"], e.ed.model["transitions"], e.ed.model["actions"], e.ed.bars(),
                          e.ed.draft_actions()), ([], [], [], [], []))
        e.deshacer()
        self.assertEqual(e.ed.model, modelo)
        self.assertEqual(len(e.ed.bars()), 1)
        self.assertEqual(len(e.ed.draft_actions()), 1)
        # no interfiere: arrastrar un elemento lo mueve, y de un punto de unión sale un enlace
        antes = posiciones_modelo(e)[ids["0"]]
        e.prensar(centro(e.M, ids["0"]))
        self.assertIsNone(e.lazo)
        e.mover(centro(e.M, ids["0"]) + QPointF(0, 40))
        e.soltar(centro(e.M, ids["0"]) + QPointF(0, 40))
        self.assertNotEqual(posiciones_modelo(e)[ids["0"]], antes)
        pa = next(a for a in anclas(e.M, ids["1"]) if a["lado"] == "abajo")["pos"]
        e.prensar(pa)
        self.assertIsNone(e.lazo)
        self.assertIsNotNone(e.enlace, "de un punto de unión sale el enlace, no el lazo")
        e.soltar(pa)
        e.enlace = None

    def test_SEDI70_soltar_la_ficha_accion_crea_una_accion_suelta(self):
        """REQ-ACT-01, REQ-EDT-02: la ficha «Continua», soltada en cualquier sitio, crea una acción continua suelta sin
        variable (se dibuja con «?», como cualquier acción) y con un punto de unión a la izquierda; no abre ningún
        diálogo; se mueve arrastrándola; es una operación de deshacer."""
        from escritorio.diagrama import COL, anclas
        w = self.w
        e, ids, ts = self.secuencial()
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        revision = e.ed.revision
        n = len(e.ed.undo_stack)
        did = e.poner_accion_suelta(QPointF(500, 200))
        self.assertEqual((pedidas, len(e.ed.undo_stack), e.ed.revision), ([], n + 1, revision), "sin diálogo; presentación")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["id"], b["tipo"], b["x"], b["y"]), (did, "continua", "400", "200"))
        self.assertEqual(e.ed.model["actions"], [], "no es una acción del modelo: no tiene etapa ni variable")
        (m,) = e.M["draftActions"]
        self.assertEqual((m["text"], m["kind"], m["borrador"], m["etapa"]), ([{"t": "?"}], "continuous", True, None))
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == did)
        self.assertTrue(caja["suelta"] and caja["borrador"])
        x, y, ancho, alto = caja["rect"]
        self.assertEqual((x, y + alto / 2), (500, 200), "su lado izquierdo, en el punto donde se soltó")
        (a,) = anclas(e.M, did)
        self.assertEqual((a["lado"], a["pos"]), ("izq", QPointF(500, 200)), "el punto de unión, a la izquierda")
        # su punto de unión se ve al pasar el puntero (como los de etapas y transiciones)
        e.pasar(QPointF(x + ancho / 2, y + alto / 2))
        self.assertEqual(len(w.diagrama._marcas), 1)
        e.pasar(QPointF(900, 700))
        self.assertEqual(len(w.diagrama._marcas), 0)
        # se dibuja como cualquier acción: rectángulo normal, ni discontinuo ni naranja
        rects = [it for it in w.diagrama.scene().items() if hasattr(it, "pen") and abs(it.boundingRect().width() - ancho) < 4
                 and abs(it.boundingRect().height() - alto) < 4]
        self.assertTrue(rects)
        self.assertTrue(all(it.pen().style() == Qt.PenStyle.SolidLine and it.pen().color().name() != COL["glow"]
                            for it in rects), "sin borde discontinuo ni naranja")
        # arrastrarla la mueve (una operación de deshacer por arrastre)
        n = len(e.ed.undo_stack)
        e.prensar(QPointF(x + ancho / 2, y + alto / 2))
        self.assertEqual((e.sel, e.arrastre["tipo"]), ([did], "borrador"))
        e.mover(QPointF(x + ancho / 2 + 60, y + alto / 2 + 40))
        e.soltar(QPointF(x + ancho / 2 + 60, y + alto / 2 + 40))
        self.assertEqual((e.ed.draft_actions()[0]["x"], e.ed.draft_actions()[0]["y"], len(e.ed.undo_stack)),
                         ("460", "240", n + 1))
        self.assertEqual(pedidas, [])
        # deshacer y rehacer
        e.deshacer()
        e.deshacer()
        self.assertEqual(e.ed.draft_actions(), [])
        e.rehacer()
        e.rehacer()
        self.assertEqual(e.ed.draft_actions()[0]["x"], "460")

    def test_SEDI71_enlazar_una_accion_a_una_etapa_separarla_y_deshacer(self):
        """REQ-ACT-01, REQ-EDT-02: arrastrar del punto de unión de una acción suelta a una etapa la une: con variable pasa a
        ser una acción del modelo (la última de la etapa); sin variable queda unida como borrador y pide variable; soltar
        el enlace de la etapa sobre la acción suelta también vale; «Separar de la etapa» la deja suelta; todo se
        deshace de una vez."""
        w = self.w
        e, ids, ts = self.secuencial()
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        aid0 = self._accion_q(e, ids)
        # sin variable: queda unida como borrador y se abre Editar
        did = e.poner_accion_suelta(QPointF(600, 220))
        self._enlazar_accion(e, did, centro(e.M, ids["1"]))
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["etapa"], pedidas), (ids["1"], [(ids["1"], did)]))
        self.assertEqual(len(e.ed.model["actions"]), 1, "aún no es del modelo")
        self.assertEqual([a["id"] for a in e.acciones(ids["1"])], [aid0, did])
        self.assertEqual(e.acciones(ids["1"])[1]["borrador"], True)
        self.assertEqual(e.sel, [ids["1"]])
        (m,) = e.M["draftActions"]
        self.assertEqual(m["etapa"], ids["1"])
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == did)
        self.assertFalse(caja["suelta"])
        c0 = next(c for c in w.diagrama.cajas_acciones if c["id"] == aid0)
        self.assertGreater(caja["rect"][0], c0["rect"][0], "unida: a la derecha de las demás, en la fila de la etapa")
        # con la variable: pasa a ser una acción del modelo, en un solo paso de deshacer
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "activacion", "variable": "CT", "valor": "CT + 1", "evento": ""},
                                         did))
        self.assertEqual(e.ed.draft_actions(), [])
        self.assertEqual([a["variable"] for a in e.acciones(ids["1"])], ["Q00", "CT"])
        e.deshacer()  # una sola operación: vuelve el borrador unido y se va la acción
        self.assertEqual(([a["variable"] for a in e.acciones(ids["1"])], len(e.ed.draft_actions())), (["Q00", ""], 1))
        e.rehacer()
        self.assertEqual(e.ed.draft_actions(), [])
        # un borrador con variable y sin etapa pasa al modelo en cuanto se une, al final
        q = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Q00")
        n = len(e.ed.undo_stack)
        did2 = e.ed.add_draft_action((400, 400), {"variable": q, "tipo": "continua"})
        e.cambia()
        pedidas.clear()
        self._enlazar_accion(e, did2, centro(e.M, ids["1"]))
        self.assertEqual((e.ed.draft_actions(), pedidas), ([], []), "completa: no pide nada")
        self.assertEqual(len(e.acciones(ids["1"])), 3)
        self.assertEqual(len(e.ed.undo_stack), n + 2, "colocar y unir (conversión incluida): dos operaciones")
        nuevo = e.acciones(ids["1"])[-1]["id"]
        self.assertEqual(e.sel, [ids["1"]])
        self.assertEqual(e.accion, nuevo)
        # separar una acción del modelo: vuelve a ser suelta, con sus datos, junto a donde estaba
        n = len(e.ed.undo_stack)
        e.separar_accion(nuevo)
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        (s,) = e.ed.draft_actions()
        self.assertEqual((s.get("etapa"), s["tipo"], s["variable"]), (None, "continua", q))
        self.assertEqual(len(e.acciones(ids["1"])), 2)
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == s["id"])
        ultima = max(c["rect"][0] + c["rect"][2] for c in w.diagrama.cajas_acciones if c["etapa"] == ids["1"])
        self.assertTrue(caja["suelta"] and caja["rect"][0] >= ultima, "suelta, a la derecha de la fila")
        e.deshacer()
        self.assertEqual((len(e.ed.draft_actions()), [a["id"] for a in e.acciones(ids["1"])][-1]), (0, nuevo),
                         "deshacer: la misma acción, con su ID")
        # soltar el enlace de la etapa sobre una acción suelta también vale
        e.separar_accion(nuevo)
        (s,) = e.ed.draft_actions()
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == s["id"])
        from escritorio.diagrama import anclas
        pa = next(a for a in anclas(e.M, ids["1"]) if a["lado"] == "abajo")["pos"]
        x, y, ancho, alto = caja["rect"]
        e.herramienta = "seleccionar"
        e.prensar(pa)
        e.mover(QPointF(x + ancho / 2, y + alto / 2))
        e.soltar(QPointF(x + ancho / 2, y + alto / 2))
        self.assertEqual((e.ed.draft_actions(), len(e.acciones(ids["1"]))), ([], 3))
        # separar un borrador unido sin variable
        did3 = e.poner_accion_suelta(QPointF(700, 220))
        self._enlazar_accion(e, did3, centro(e.M, ids["1"]))
        self.assertEqual(e.ed.draft_actions()[0]["etapa"], ids["1"])
        e.separar_accion(did3)
        self.assertNotIn("etapa", e.ed.draft_actions()[0])
        # el enlace soltado en un hueco o sobre otra cosa no hace nada raro
        n = len(e.ed.undo_stack)
        self._enlazar_accion(e, did3, QPointF(900, 700))
        self.assertEqual((len(e.ed.undo_stack), len(e.M["transitions"])), (n, 2))
        self.assertIn("etapa", e.mensaje)
        self._enlazar_accion(e, did3, centro(e.M, ts["t1"]))
        self.assertEqual(len(e.ed.undo_stack), n)
        self.assertNotIn("etapa", e.ed.draft_actions()[0])

    def test_SEDI72_tipo_de_accion_por_el_boton_derecho(self):
        """REQ-ACT-01, REQ-EDT-02: el botón derecho en una acción (suelta o unida) ofrece un submenú «Tipo de acción» con
        los cinco tipos (icono y nombre; el actual, marcado), «Editar…», «Separar de la etapa» (si está unida) y
        «Quitar»; no ofrece el forzado. Cambiar a un tipo que pide datos que faltan deja la acción con «?»: si falta el
        valor se abre Editar; la condición y el evento se programan en el panel de opciones. Si no falta nada, se cambia en
        su sitio."""
        from escritorio.edicion import TEXTO_LIMITADA
        w = self.w
        e, ids, ts = self.secuencial()
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        aid = self._accion_q(e, ids)

        def caja(i):
            c = next(c for c in w.diagrama.cajas_acciones if c["id"] == i)
            x, y, ancho, alto = c["rect"]
            return QPointF(x + ancho / 2, y + alto / 2)

        def tipos(opciones):
            return {t: f for t, f, _ in dict(opciones)["Tipo de acción"]}
        opciones = e.menu(caja(aid))
        textos = [t for t, _ in opciones]
        self.assertEqual(list(tipos(opciones)),
                         ["Continua", "Condicionada", "Al activar", "Al desactivar", "Por evento", "Orden de forzado"])
        self.assertTrue(all(len(x) == 3 and not x[2].isNull() for x in dict(opciones)["Tipo de acción"]), "con su icono")
        self.assertEqual(e.menu_marcadas, {"Continua"})
        self.assertEqual(textos[0], "Tipo de acción")
        self.assertIn("Editar…", textos)
        self.assertIn("Separar de la etapa", textos)
        self.assertEqual(textos[-1], "Quitar")
        self.assertFalse([t for t in textos if "orzado" in t or "limitada" in t.lower()], "el forzado no se ofrece")
        # la barra de menú de Qt: el submenú, con el icono de cada tipo y la marca del actual
        menu = w.diagrama.menu_contextual(opciones)
        sub = next(a for a in menu.actions() if a.text() == "Tipo de acción").menu()
        self.assertEqual([a.text() for a in sub.actions() if a.isCheckable() and a.isChecked()], ["Continua"])
        self.assertTrue(all(not a.icon().isNull() for a in sub.actions()))
        # a memorizada al activar: falta el valor -> borrador unido con «?», Editar abierto, tipo puesto
        n = len(e.ed.undo_stack)
        tipos(opciones)["Al activar"]()
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], b["etapa"], e.ed.model["actions"]), ("activacion", ids["1"], []))
        self.assertEqual(pedidas, [(ids["1"], b["id"])])
        (m,) = e.M["draftActions"]
        self.assertEqual((m["kind"], m["trigger"], [s["t"] for s in m["text"]]), ("stored", "activation", ["Q00 := ", "?"]))
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "activacion", "variable": "Q00", "valor": "1"}, b["id"]))
        self.assertEqual((e.ed.draft_actions(), e.datos_accion(e.acciones(ids["1"])[0]["id"])["valor"]), ([], "1"))
        # de memorizada a memorizada (nada falta): en su sitio, con su ID
        a2 = e.acciones(ids["1"])[0]["id"]
        pedidas.clear()
        e.tipo_accion(a2, "desactivacion")
        self.assertEqual((e.acciones(ids["1"])[0]["id"], e.datos_accion(a2)["tipo"], pedidas, e.ed.draft_actions()),
                         (a2, "desactivacion", [], []))
        # a por evento: falta el evento, que no se pide en un diálogo: se programa en el panel de opciones
        e.tipo_accion(a2, "evento")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], pedidas), ("evento", []))
        (m,) = e.M["draftActions"]
        self.assertEqual(m["event"], [{"t": "?"}])
        self.assertEqual((e.accion, w.props.objetivo_bloques()), (b["id"], ("accion", b["id"], "evento")))
        self.assertEqual((w.props.pagina, w.props.accion.aid), ("accion", b["id"]), "sus opciones, abajo")
        self.assertIn("evento sin programar", w.props.accion.frase.text())
        e.deshacer()
        self.assertEqual((e.ed.draft_actions(), e.datos_accion(a2)["tipo"]), ([], "desactivacion"), "una operación")
        # una variable entera no sirve para una continua: queda «?» en la variable
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "activacion", "variable": "CT", "valor": "CT + 1"}))
        ct = e.acciones(ids["1"])[-1]["id"]
        e.tipo_accion(ct, "continua")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], "variable" in b, pedidas[-1]), ("continua", False, (ids["1"], b["id"])))
        e.deshacer()
        e.quitar_accion(ct)
        # a condicionada: falta la condición (borrador con «?» en el trazo); con ella, pasa al modelo
        e.quitar_accion(a2)
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00", "condicion": ""}))
        a3 = e.acciones(ids["1"])[0]["id"]
        pedidas.clear()
        e.tipo_accion(a3, "condicionada")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], pedidas, e.accion), ("condicionada", [], b["id"]))
        self.assertEqual("".join(s["t"] for s in e.M["draftActions"][0]["cond"]), "?")
        self.assertIsNone(e.poner_texto_accion(b["id"], "condicion", "marcha"))
        (a4,) = e.acciones(ids["1"])
        self.assertEqual((e.ed.draft_actions(), e.datos_accion(a4["id"])["tipo"], e.datos_accion(a4["id"])["condicion"]),
                         ([], "condicionada", "marcha"))
        self.assertTrue(e.ed.validate().can_simulate)
        # una condicionada con límite de tiempo (de un fichero antiguo): marcada como tal; «Condicionada» no la cambia
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "limitada", "variable": "Q00", "condicion": "marcha",
                                                    "limite": "3s"}, a4["id"]))
        self.assertEqual(e.ed.get(a4["id"])["limitUs"], "3000000")
        opciones = e.menu(caja(a4["id"]))
        self.assertEqual(e.menu_marcadas, {TEXTO_LIMITADA})
        self.assertEqual(list(tipos(opciones))[1], TEXTO_LIMITADA)
        n = len(e.ed.undo_stack)
        e.tipo_accion(a4["id"], "condicionada")
        self.assertEqual((len(e.ed.undo_stack), e.ed.get(a4["id"])["limitUs"]), (n, "3000000"), "no cambia nada")
        e.tipo_accion(a4["id"], "continua")  # una continua no lleva condición ni límite
        self.assertNotIn("limitUs", e.ed.get(a4["id"]))
        self.assertEqual(e.datos_accion(a4["id"])["condicion"], "")
        # una acción suelta: su menú no ofrece separar; cambia de tipo y pide lo que le falta
        d = e.poner_accion_suelta(QPointF(600, 500))
        opciones = e.menu(caja(d))
        self.assertNotIn("Separar de la etapa", [t for t, _ in opciones])
        self.assertEqual(e.menu_marcadas, {"Continua"})
        pedidas.clear()
        tipos(opciones)["Por evento"]()
        self.assertEqual((e.ed.draft_actions()[0]["tipo"], pedidas), ("evento", [(None, d)]))
        self.assertEqual(e.menu_marcadas, {"Continua"}, "el menú se recalcula al abrirlo")
        e.menu(caja(d))
        self.assertEqual(e.menu_marcadas, {"Por evento"})
        tipos(opciones)["Continua"]()  # no pide nada nuevo
        self.assertEqual(pedidas, [(None, d)])
        # Editar…, Quitar y doble clic
        self.assertEqual(dict(e.menu(caja(d)))["Editar…"](), None)
        self.assertEqual(pedidas[-1], (None, d))
        e.doble(caja(d))
        self.assertEqual(pedidas[-1], (None, d))
        dict(e.menu(caja(d)))["Quitar"]()
        self.assertEqual(e.ed.draft_actions(), [])
        # el menú de la etapa conserva «Añadir acción…»
        self.assertEqual(list(dict(e.menu(centro(e.M, ids["1"])))),
                         ["Colocación de las acciones", "-", "Tipo de etapa",
                          "Equidistanciar alturas de la cadena"])

    def test_SEDI73_guardar_abrir_con_borradores_avisos_y_deshacer(self):
        """REQ-DAT-01, REQ-EDT-09, REQ-EDT-14: los borradores de acción se guardan en la presentación
        (`draftActions`) y se abren con el proyecto; no cambian la revisión semántica ni se simulan; cada uno da el
        error «Acción sin configurar» para sueltas y unidas incompletas; deshacer y rehacer los siguen."""
        from escritorio.edicion import Edicion
        w = self.w
        e, ids, ts = self.secuencial()
        e.pedir_accion = lambda sid, aid: None
        self._accion_q(e, ids)
        q = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Q00")
        revision = e.ed.revision
        d1 = e.poner_accion_suelta(QPointF(500, 220))
        e.poner_accion(None, {"tipo": "evento", "variable": "Q00", "valor": "1", "evento": "↑marcha"}, d1)
        d2 = e.poner_accion_suelta(QPointF(500, 320))
        e.tipo_accion(d2, "limitada")
        e.poner_accion(None, {"tipo": "limitada", "variable": "", "limite": "2s"}, d2)
        d3 = e.poner_accion_suelta(QPointF(500, 420))
        self._enlazar_accion(e, d3, centro(e.M, ids["0"]))  # unida a la etapa 0 y sin variable
        self.assertEqual(e.ed.revision, revision, "los borradores son presentación: la revisión semántica no cambia")
        # avisos en Diagnósticos
        avisos = [d for d in e.diagnosticos() if d["code"] in ("AVISO", "D-ACCION-PENDIENTE")]
        self.assertEqual(len(avisos), 3)
        self.assertEqual([d["message"] for d in avisos].count("Acción sin configurar suelta"), 2)
        self.assertTrue(any("sin configurar en la etapa" in d["message"] and "variable" in d["message"] for d in avisos))
        self.assertEqual(sum(d["blocks"] and d["severity"] == "bloqueo" for d in avisos), 3)
        self.assertTrue(e.ed.validate().can_simulate, "la presentación la comprueba Edicion al pulsar Play")
        textos = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        self.assertEqual(sum("Acción sin configurar suelta" in t for t in textos), 2)
        e.seleccionar([d1])  # un clic en el aviso selecciona la acción
        w._ir_a_diagnostico(next(w.lista_diag.item(i) for i in range(w.lista_diag.count())
                                 if w.lista_diag.item(i).data(Qt.ItemDataRole.UserRole) == d1))
        self.assertEqual(e.sel, [d1])
        self.assertIsNotNone(e.centro(d1))
        # guardar y abrir
        destino = Path(self.tmp.name) / "con-borradores"
        e.guardar(destino)
        pres = next(destino.glob("presentation-*.json"))
        guardado = json.loads(pres.read_text(encoding="utf-8"))
        self.assertEqual([d["id"] for d in guardado["draftActions"]], [d1, d2, d3])
        self.assertEqual(guardado["draftActions"][0]["tipo"], "evento")
        self.assertEqual((guardado["draftActions"][0]["variable"], guardado["draftActions"][0]["evento"]), (q, "↑marcha"))
        self.assertEqual(guardado["draftActions"][2]["etapa"], ids["0"])
        op = open_model(destino)
        self.assertEqual(op.presentations[0]["draftActions"], e.ed.draft_actions())
        e2 = Edicion.desde(op.doc, {}, "abierto", destino, op.presentations[0])
        self.assertEqual(e2.ed.draft_actions(), e.ed.draft_actions())
        self.assertEqual(e2.ed.revision, revision)
        self.assertEqual(len([m for m in e2.M["draftActions"] if m["etapa"] is None]), 2)
        self.assertEqual(next(c for c in e2.M["draftActions"] if c["id"] == d1)["trigger"], "event")
        self.assertEqual(len([d for d in e2.diagnosticos() if d["code"] == "D-ACCION-PENDIENTE"]), 3)
        # la simulación no los ve
        v = Vista("m", "t", "", lambda: (copy.deepcopy(op.doc), {}), normalize_options(None), presentation=op.presentations[0])
        self.assertEqual((v.model["draftActions"], v.s is not None), ([], True))
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertFalse(w.cambiar_modo("simular"))
        self.assertEqual(w.modo, "editar")
        aviso.assert_called_once()
        self.assertEqual(len(e.ed.draft_actions()), 3)
        # deshacer y rehacer (una operación por borrador)
        antes = copy.deepcopy(e.ed.draft_actions())
        e.deshacer()
        self.assertNotEqual(e.ed.draft_actions(), antes)
        e.rehacer()
        self.assertEqual(e.ed.draft_actions(), antes)
        # una variable que usa un borrador no se quita; una etapa borrada se lleva el borrador unido
        self.assertIn("usa", e.quitar_variable(q) or "")
        e.confirmar_borrado = lambda plan: True
        e.seleccionar([ids["0"]])
        e.borrar()
        self.assertNotIn(d3, [d["id"] for d in e.ed.draft_actions()], "se va con su etapa")
        e.deshacer()
        self.assertEqual(next(d for d in e.ed.draft_actions() if d["id"] == d3)["etapa"], ids["0"])


    def test_SEDI74_opciones_de_una_accion_suelta_o_sin_completar(self):
        """REQ-ACT-01, REQ-EDT-02: «Editar…» de una acción suelta abre sus opciones en el panel inferior (con el límite de
        tiempo de las limitadas): guarda sus datos aunque falte algo; unida a una etapa y completa, pasa al modelo en una sola
        operación; «Añadir acción…» de una etapa crea la continua unida y abre sus opciones."""
        w = self.w
        e, ids, ts = self.secuencial()
        e.nueva_variable("Q00", "output", {"kind": "bool"})
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        did = e.poner_accion_suelta(QPointF(500, 220))
        d = self.panel_accion(None, did)
        self.assertEqual(w.props.titulo.text(), "Propiedades · Acción")
        self.assertTrue(d.limite.isHidden())
        self.assertFalse(hasattr(d, "tipo"), "el panel no lleva lista de tipos: se cambia con botón derecho (P-IMP-46)")
        self.assertFalse(hasattr(d, "cond"), "sin programador dentro")
        e.ed.update_draft_action(did, tipo="limitada")  # lo que trae un fichero antiguo
        e.cambia()
        d = self.panel_accion(None, did)
        self.assertEqual(d.clave_tipo, "limitada")
        self.assertFalse(d.limite.isHidden(), "el límite de tiempo solo en la limitada")
        d.limite.setText("2s")
        n = len(e.ed.undo_stack)
        d.limite.editingFinished.emit()  # sin variable: se guarda igual, con «?»
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], b["limite"], "variable" in b), ("limitada", "2s", False))
        self.assertEqual(("".join(s["t"] for s in e.M["draftActions"][0]["cond"]), e.M["draftActions"][0]["text"]),
                         ("NOT 2s/X?", [{"t": "?"}]))
        d = self.panel_accion(None, did)  # se reabre con lo guardado
        self.assertEqual((d.clave_tipo, d.limite.text()), ("limitada", "2s"))
        d.variable.setCurrentText("Q00")
        self.assertEqual(e.ed.draft_actions()[0]["variable"], next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Q00"))
        self.assertEqual(e.ed.model["actions"], [], "suelta: no es del modelo aunque esté completa")
        # una variable que no existe se crea con la elección, en la misma operación
        # una variable nueva se crea en la tabla de variables (aquí no) y se elige en la lista
        d = self.panel_accion(None, did)
        self.assertEqual(d.variable.findData("Q11"), -1)
        e.nueva_variable("Q11", "output", {"kind": "bool"})
        d = self.panel_accion(None, did)
        n = len(e.ed.undo_stack)
        d.variable.setCurrentText("Q11")
        self.assertEqual((len(e.ed.undo_stack), [v["name"] for v in e.ed.model["variables"]]), (n + 1, ["marcha", "paro", "Q00", "Q11"]))
        # unida a una etapa y completa: pasa al modelo con su límite, en una operación
        e.unir_accion(did, ids["1"])
        (a,) = e.acciones(ids["1"])
        self.assertEqual((e.ed.draft_actions(), a["tipo"], a["limite"], a["variable"]), ([], "limitada", "2s", "Q11"))
        # «Añadir acción…» de la etapa: continua unida, sin variable, y sus opciones (aquí, el panel real)
        pedidas.clear()
        e.anadir_accion(ids["0"])
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["etapa"], b["tipo"], pedidas), (ids["0"], "continua", [(ids["0"], b["id"])]))
        d = self.panel_accion(ids["0"], b["id"])
        self.assertEqual(w.props.titulo.text(), "Propiedades · Acción")  # (la etapa, sobre el área de bloques o en el panel de la acción)
        n = len(e.ed.undo_stack)
        d.variable.setCurrentText("Q00")
        self.assertEqual((e.ed.draft_actions(), len(e.ed.undo_stack), e.acciones(ids["0"])[0]["variable"]), ([], n + 1, "Q00"))
        self.assertTrue(e.ed.validate().can_simulate)


    def test_SEDI75_accion_limitada_se_dibuja_como_condicion_not_d_sobre_x(self):
        """REQ-ACT-01, REQ-TMP-02: una acción limitada en el tiempo se dibuja como en la norma, con su límite como una
        condición más (NOT 3s/X1; con condición c, c · NOT 3s/X1) y sin símbolo nuevo; el modelo sigue guardando limitUs; el
        banco dibuja lo mismo porque comparte el texto de la condición."""
        w = self.w
        e, ids, ts = self.secuencial()
        e.nueva_variable("Q00", "output", {"kind": "bool"})
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "limitada", "variable": "Q00", "limite": "3s"}))
        a = e.M["steps"][1]["actions"][0]
        self.assertEqual(("".join(s["t"] for s in a["cond"]), [s["t"] for s in a["text"]]), ("3s/X1", ["Q00"]))
        self.assertTrue(all(s.get("o") for s in a["cond"]), "con la barra encima (negada)")
        aid = e.acciones(ids["1"])[0]["id"]
        self.assertEqual(e.ed.get(aid)["limitUs"], "3000000")
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "limitada", "variable": "Q00", "limite": "3s",
                                                    "condicion": "marcha OR paro"}, aid))
        a = e.M["steps"][1]["actions"][0]
        self.assertEqual("".join(s["t"] for s in a["cond"]), "(marcha + paro) · 3s/X1")
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "limitada", "variable": "Q00", "limite": "3s",
                                                    "condicion": "marcha"}, aid))
        self.assertEqual("".join(s["t"] for s in e.M["steps"][1]["actions"][0]["cond"]), "marcha · 3s/X1")
        self.assertTrue(e.ed.validate().can_simulate)
        # el banco usa la misma condición de la vista para toda acción continua
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        self.assertIn('a.kind === "continuous" && a.cond', js)
        self.assertNotIn("limit", js.lower())

    def test_SEDI76_mensajes_informativos_y_barra_de_estado(self):
        """REQ-EDT-09: un aviso informativo de la edición no sale en rojo (el rojo es de los errores); el mensaje temporal
        de la barra de estado sustituye al texto fijo mientras dura y no se superpone."""
        w = self.w
        e, ids, ts = self.secuencial()
        w.show()
        e.poner_accion_suelta(QPointF(500, 200))
        self.assertTrue(e.mensaje and e.mensaje_info)
        self.assertNotIn(COL_ERR, w.ayuda.styleSheet())
        self.assertTrue(w.l_aviso.isHidden(), "el texto fijo cede su sitio al mensaje")
        self.assertIn("Acción suelta", w.statusBar().currentMessage())
        w.statusBar().clearMessage()
        self.assertFalse(w.l_aviso.isHidden())
        e.mensaje = "Un rechazo"
        e.cambiado.emit()
        self.assertFalse(e.mensaje_info)
        self.assertIn(COL_ERR, w.ayuda.styleSheet())

    def test_SEDI77_borradores_danados_al_abrir(self):
        """REQ-DAT-01, REQ-EDT-09: un `draftActions` corrupto no rompe la apertura: se descartan los dañados (no son
        diccionarios, sin tipo o de tipo desconocido, posición ausente o no numérica) con un aviso en Diagnósticos; una etapa
        inexistente deja el borrador suelto y una variable inexistente, con «?»."""
        from escritorio.edicion import Edicion
        e, ids, ts = self.secuencial()
        bien = {"id": "c-1", "x": "40", "y": "60", "tipo": "continua"}
        pres = copy.deepcopy(e.ed.presentation)
        pres["draftActions"] = [
            bien, 7, "x", {"id": "c-2", "x": "1", "y": "2"}, {"id": "c-3", "x": "1", "y": "2", "tipo": "raro"},
            {"id": "c-4", "y": "2", "tipo": "continua"}, {"id": "c-5", "x": "uno", "y": "2", "tipo": "continua"},
            {"id": "c-6", "x": "1", "y": "2", "tipo": "evento", "etapa": "s-no-existe", "variable": "v-no-existe",
             "valor": "1"}, {"x": "1", "y": "2", "tipo": "continua"}]
        e2 = Edicion.desde(e.ed.model, {}, "dañado", None, pres)
        self.assertEqual([b["id"] for b in e2.ed.draft_actions()], ["c-1", "c-6"])
        c6 = e2.ed.draft_actions()[1]
        self.assertEqual(("etapa" in c6, "variable" in c6), (False, False))
        self.assertEqual(e2.ignorados, 7)
        msgs = [d["message"] for d in e2.diagnosticos() if d["code"] == "AVISO"]
        self.assertIn("Se ignoraron 7 borradores de acción dañados", msgs)
        self.assertEqual(e2.M["draftActions"][1]["text"][0]["t"], "? := ")
        pres["draftActions"] = [3]
        e3 = Edicion.desde(e.ed.model, {}, "uno", None, pres)
        self.assertIn("Se ignoró un borrador de acción dañado", [d["message"] for d in e3.diagnosticos()])
        pres["draftActions"] = "roto"
        self.assertEqual(Edicion.desde(e.ed.model, {}, "x", None, pres).ed.draft_actions(), [])

    # -- P-IMP-42: paneles laterales, tabla de variables, parpadeo y colocación de las acciones --------------------
    def test_SEDI78_anchos_de_los_paneles_laterales(self):
        """REQ-EDT-09, REQ-SIM-03: al editar, los paneles laterales tienen un ancho único y fijo (el que piden las dos
        columnas de la paleta: su rejilla, el marco y la holgura), los dos iguales y sin divisor que los mueva; las
        fichas siguen en dos columnas; nada de lo que muestran se corta; se pliegan y despliegan; al simular, el derecho
        es el de siempre."""
        from escritorio.diagrama import anclas
        w = self.w
        e, ids, ts = self.secuencial()
        w.show()
        self.app.processEvents()
        minimo, maximo = w.ancho_lateral, 16777215
        derecho = w.ancho_derecho  # (el derecho mide más desde 1280 px de ancho de ventana: P10)
        pal = w.paleta
        self.assertGreaterEqual(minimo, 2 * pal.gridSize().width() + 2 * pal.frameWidth() + 2, "caben las dos columnas")
        self.assertGreaterEqual(minimo, pal.ancho_minimo())
        self.assertEqual((w.dock.minimumWidth(), w.dock.maximumWidth()), (minimo, minimo))
        self.assertEqual((w.derecho.minimumWidth(), w.derecho.maximumWidth()), (derecho, maximo))
        self.assertEqual((w.dock.width(),w.derecho.width()),(minimo,derecho))
        self.assertTrue(w.split.handle(1).isEnabled(), "divisor habilitado también al editar")
        w.split.moveSplitter(w.split.width() - 400, 1)  # el panel derecho se puede estirar
        self.app.processEvents()
        self.assertEqual(w.dock.width(), minimo)
        self.assertGreater(w.derecho.width(), derecho)
        r = [pal.visualItemRect(pal.item(i)) for i in range(pal.count())]
        self.assertEqual((pal.count(), len({x.y() for x in r})), (20, 13))
        self.assertEqual(len({x.x() for x in r}), 2, "dos columnas por sección")
        self.assertEqual(pal.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertGreaterEqual(pal.viewport().width(), pal.REJILLA.width())
        # con cada tipo de selección, las opciones caben en el ancho del panel de abajo (no se cortan) y el panel derecho también
        b = e.poner_barra(QPointF(500, 400), "Y")
        for sel in ([ids["1"]], [ts["t1"]], [f"{ts['t1']}|{ids['0']}|pre"], [b]):
            e.seleccionar(sel)
            self.app.processEvents()
            self.assertLessEqual(w.props.minimumSizeHint().width(), w.inferior.width(), sel)
        self.assertLessEqual(w.derecho.widget(1).widget().minimumSizeHint().width(), derecho)
        # plegar y desplegar siguen funcionando
        w.flechas["izquierdo"].click()
        self.assertTrue(w.dock.isHidden())
        w.flechas["izquierdo"].click()
        self.assertFalse(w.dock.isHidden())
        self.assertEqual(w.dock.width(), minimo)
        # al simular conserva el ancho de edición y permite mover su divisor
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual((w.derecho.minimumWidth(), w.derecho.maximumWidth()), (derecho, 16777215))
        self.assertTrue(w.split.handle(1).isEnabled())
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual((w.derecho.minimumWidth(), w.derecho.maximumWidth()), (derecho, maximo))

    def test_SEDI79_tabla_de_variables_nombre_papel_tipo(self):
        """REQ-EDT-07: la tabla tiene solo Nombre, Papel y Tipo; se ofrecen Booleana, Entera y Decimal con 2 decimales;
        una variable de un fichero antiguo (decimal de 1 o 3 decimales, duración) se ve con su tipo y funciona, y si se
        le cambia el tipo solo se elige entre los tres; la unidad que ya tuviera se conserva."""
        from escritorio.variables import TIPOS
        w = self.w
        w.nuevo()
        e, pv = w.edicion, w.variables
        e.nueva_variable("a", "input")
        e.ed.add_variable("T3", "input", {"kind": "decimal", "scale": 3}, unit="s")
        e.ed.add_variable("T1", "output", {"kind": "decimal", "scale": 1})
        e.ed.add_variable("D", "input", {"kind": "duration"}, unit="ms")
        e.cambia()
        self.assertEqual([pv.tabla.horizontalHeaderItem(c).text() for c in range(pv.tabla.columnCount())],
                         ["Nombre", "Papel", "Tipo"])
        self.assertEqual([t for _, t in TIPOS], ["Booleana", "Entera", "Decimal (2)"])
        self.assertEqual(TIPOS[2][0], {"kind": "decimal", "scale": 2})
        self.assertEqual([t for _, t in pv.opciones(0, 2)], ["Booleana", "Entera", "Decimal (2)"])
        self.assertEqual([pv.tabla.item(r, 2).text() for r in range(4)],
                         ["Booleana", "Decimal (3)", "Decimal (1)", "Duración"])
        self.assertEqual([pv.tabla.item(r, 1).text() for r in range(4)], ["Entrada", "Entrada", "Salida", "Entrada"])
        self.assertTrue(all(pv.tabla.cellWidget(r, c) is None for r in range(4) for c in (1, 2)), "texto, sin desplegable")
        # siguen funcionando: sin diagnósticos que las mencionen y usables en una receptividad
        t1, _ = e.ed.add_transition(e.raiz, "", at=(0, 100), label="t1")
        e.cambia()
        self.assertIsNone(e.comprobar(t1, "T3 > 1"), "una decimal de 3 decimales se usa en una receptividad")
        # cambiar el tipo de una antigua: solo entre los tres (la antigua figura como la actual y no cambia nada)
        self.assertEqual([t for _, t in pv.opciones(1, 2)], ["Decimal (3)", "Booleana", "Entera", "Decimal (2)"])
        n = len(e.ed.undo_stack)
        pv.elegir(1, 2, pv.opciones(1, 2)[0][0])
        self.assertEqual(len(e.ed.undo_stack), n, "elegir el que ya tiene no cambia nada")
        pv.elegir(1, 2, {"kind": "int"})
        v = next(x for x in e.ed.model["variables"] if x["name"] == "T3")
        self.assertEqual(v["type"], {"kind": "int"})
        self.assertEqual((v["unit"], len(e.ed.undo_stack)), ("s", n + 1), "la unidad se conserva; una operación")
        self.assertEqual(pv.tabla.item(1, 2).text(), "Entera")
        self.assertEqual(len(pv.opciones(1, 2)), 3, "ya no ofrece el tipo antiguo")
        # renombrar conserva la unidad
        d = next(x for x in e.ed.model["variables"] if x["name"] == "D")
        pv.tabla.item(3, 0).setText("Dur")
        self.assertEqual((d["unit"], next(x for x in e.ed.model["variables"] if x["id"] == d["id"])["unit"]), ("ms", "ms"))
        # los usos no se listan pero siguen impidiendo quitar la variable
        e.poner_condicion(t1, "a", crear=False)
        pv.tabla.selectRow(0)
        pv.quitar()
        self.assertIn("se usa", pv.msg.text())
        self.assertEqual(len(e.ed.model["variables"]), 4)

    def test_SEDI80_variable_nueva_sin_nombre(self):
        """REQ-EDT-07, REQ-EDT-09: «Nueva variable» añade una fila en blanco que solo existe en la interfaz; al escribir un
        nombre válido se crea en el modelo (una operación de deshacer); uno no válido o repetido se rechaza con su
        mensaje y la fila sigue en blanco; con filas sin nombre no se puede simular ni guardar."""
        w = self.w
        w.nuevo()
        e, pv = w.edicion, w.variables
        n = len(e.ed.undo_stack)
        pv.nueva()
        self.assertEqual((pv.tabla.rowCount(), pv.tabla.item(0, 0).text(), pv.sin_nombre()), (1, "", 1))
        self.assertEqual((e.ed.model["variables"], len(e.ed.undo_stack)), ([], n), "no está en el modelo")
        # no válido: demasiado largo
        pv.tabla.item(0, 0).setText("x" * 300)
        self.assertEqual((e.ed.model["variables"], pv.tabla.item(0, 0).text(), pv.sin_nombre()), ([], "", 1))
        self.assertIn("nombre inválido", pv.msg.text())
        self.assertEqual(len(pv.parpadeo.ids), 1)
        self.assertTrue(pv.parpadeo.t.isActive())
        # el papel y el tipo de la fila pendiente se recuerdan hasta crear la variable
        pv.elegir(0, 1, "output")
        pv.elegir(0, 2, {"kind": "int"})
        self.assertEqual((pv.tabla.item(0, 1).text(), pv.tabla.item(0, 2).text()), ("Salida", "Entera"))
        self.assertEqual(e.ed.model["variables"], [])
        pv.tabla.item(0, 0).setText("Cuenta")
        (v,) = e.ed.model["variables"]
        self.assertEqual((v["name"], v["role"], v["type"]), ("Cuenta", "output", {"kind": "int"}))
        self.assertEqual((len(e.ed.undo_stack), pv.sin_nombre(), pv.tabla.item(0, 0).text()), (n + 1, 0, "Cuenta"))
        e.deshacer()
        self.assertEqual(e.ed.model["variables"], [])
        e.rehacer()
        # repetido
        pv.nueva()
        self.assertEqual(pv.tabla.rowCount(), 2)
        pv.tabla.item(1, 0).setText("Cuenta")
        self.assertEqual((len(e.ed.model["variables"]), pv.tabla.item(1, 0).text(), pv.sin_nombre()), (1, "", 1))
        self.assertIn("ya existe", pv.msg.text().lower())
        # con una fila sin nombre no se simula ni se guarda
        with mock.patch("escritorio.ventana.QFileDialog.getSaveFileName") as archivo, \
                mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertFalse(w.cambiar_modo("simular"))
            self.assertEqual(w.modo, "editar")
            self.assertFalse(w.guardar())
            archivo.assert_not_called()
            aviso.assert_not_called()
        self.assertEqual(e.mensaje, "Hay una variable sin nombre: escríbale un nombre o quítela")
        self.assertEqual(pv.msg.text(), e.mensaje)
        self.assertEqual(pv.parpadeo.ids, {pv._clave_fila(pv._pend[0])})
        # quitarla: solo la fila de la interfaz, sin tocar el modelo ni deshacer
        n = len(e.ed.undo_stack)
        pv.tabla.selectRow(1)
        pv.quitar()
        self.assertEqual((pv.tabla.rowCount(), pv.sin_nombre(), len(e.ed.undo_stack)), (1, 0, n))
        # al empezar otra edición, las filas sin nombre de la anterior no pasan
        pv.nueva()
        w.edicion.ed.dirty = False
        w.nuevo()
        self.assertEqual((w.variables.sin_nombre(), w.variables.tabla.rowCount()), (0, 1), "solo la fila de muestra")

    def test_SEDI81_parpadeo_naranja_en_los_errores(self):
        """REQ-EDT-09: un rechazo, un intento de simular con errores, un clic en Diagnósticos (también en el aviso de un
        borrador) y el aviso de una fila sin nombre hacen parpadear en naranja los elementos afectados unas veces
        (tres parpadeos en 1,5 s) con un temporizador; se programan los elementos correctos."""
        from escritorio.edicion import PARPADEO_MS, PARPADEO_PASOS, Parpadeo
        w = self.w
        e, ids, ts = self.secuencial()
        # el mecanismo: encendido, apagado, encendido…, tres veces encendido y se para
        p = Parpadeo()
        fases = []
        p.cambia.connect(lambda: fases.append(p.fase))
        p.iniciar(["a", "b"])
        self.assertEqual((p.activos(), p.t.isActive(), p.t.interval()), ({"a", "b"}, True, PARPADEO_MS))
        for _ in range(PARPADEO_PASOS):
            p.paso()
        self.assertEqual((fases, p.t.isActive(), p.activos(), p.ids), ([True, False, True, False, True, False, False], False, set(), set()))
        self.assertEqual(fases.count(True), 3, "tres parpadeos")
        self.assertEqual(PARPADEO_MS * PARPADEO_PASOS, 1500)
        # un rechazo que se refiere a elementos: parpadean esos
        b1, b2 = e.poner_barra(QPointF(500, 100), "Y"), e.poner_barra(QPointF(500, 200), "Y")
        e.parpadeo.parar()
        e.unir({"id": b1, "lado": "abajo"}, {"id": b2, "lado": "arriba"})
        self.assertIn("otra barra", e.mensaje)
        self.assertEqual((e.parpadeo.ids, e.parpadeo.t.isActive()), ({b1, b2}, True))
        self.assertEqual(e.parpadeo.activos(), {b1, b2})
        e.parpadeo.parar()
        e.conectar(ids["0"], ts["t2"])  # t2 ya tiene una etapa anterior
        self.assertIn("ya tiene una etapa", e.mensaje)
        self.assertEqual(e.parpadeo.ids, {ts["t2"], ids["0"]})
        # el dibujo recibe lo que parpadea (fase encendida) y lo dibuja en la capa naranja
        nar = [it for it in w.diagrama.scene().items() if hasattr(it, "pen") and it.pen().color().name() == "#e36209"
               and it.pen().widthF() >= 3.5]
        self.assertTrue(nar, "los elementos se dibujan en naranja en la fase encendida")
        e.parpadeo.paso()  # fase apagada
        self.assertFalse([it for it in w.diagrama.scene().items() if hasattr(it, "pen") and it.pen().color().name() == "#e36209"
                          and it.pen().widthF() >= 3.5])
        e.parpadeo.parar()
        # una acción (del modelo o borrador)
        e.nueva_variable("Q00", "output")
        e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00", "condicion": ""})
        aid = e.ed.model["actions"][0]["id"]
        e.parpadear([aid])
        self.assertEqual(e.parpadeo.ids, {aid})
        nar = [it for it in w.diagrama.scene().items() if hasattr(it, "pen") and it.pen().color().name() == "#e36209"
               and it.pen().widthF() >= 3.5]
        self.assertTrue(nar, "la caja de la acción parpadea")
        e.parpadeo.parar()
        # simular con errores: cada elemento con un error de validación
        t3 = e.poner_transicion(QPointF(300, 400))
        with mock.patch("escritorio.ventana.QMessageBox.warning"):
            self.assertFalse(w.cambiar_modo("simular"))
        esperados = {d["target"] for d in e.diagnosticos() if d["blocks"] and d["target"]}
        self.assertIn(t3, esperados)
        self.assertEqual(e.parpadeo.ids, esperados)
        e.parpadeo.parar()
        # un clic en una línea de Diagnósticos
        fila = next(i for i in range(w.lista_diag.count()) if w.lista_diag.item(i).data(Qt.ItemDataRole.UserRole) == t3)
        w._ir_a_diagnostico(w.lista_diag.item(fila))
        self.assertEqual((e.sel, e.parpadeo.ids), ([t3], {t3}))
        e.parpadeo.parar()
        # el aviso de un borrador
        did = e.poner_accion_suelta(QPointF(520, 330))
        fila = next(i for i in range(w.lista_diag.count()) if w.lista_diag.item(i).data(Qt.ItemDataRole.UserRole) == did)
        w._ir_a_diagnostico(w.lista_diag.item(fila))
        self.assertEqual(e.parpadeo.ids, {did})
        # la fila de una variable
        pv = w.variables
        pv.nueva()
        pv.avisar_sin_nombre()
        (clave,) = pv.parpadeo.ids
        self.assertTrue(clave.startswith("sin-nombre:"))
        self.assertEqual(pv.tabla.item(pv.tabla.rowCount() - 1, 0).background().color().name(), "#ffd2ad")
        pv.parpadeo.paso()
        self.assertNotEqual(pv.tabla.item(pv.tabla.rowCount() - 1, 0).background().color().name(), "#ffd2ad")
        # un nombre repetido en una fila existente: parpadea esa fila
        e.nueva_variable("zz")
        pv.tabla.item(0, 0).setText("zz")
        self.assertEqual(pv.parpadeo.ids, {e.ed.model["variables"][0]["id"]})

    @staticmethod
    def _apartar_t2(e):
        """Baja la transición t2 para dejar sitio, bajo la etapa 1, a una columna de acciones (P-IMP-48: las acciones no se
        colocan encima del texto de una transición)."""
        e.ed.move(next(t["id"] for t in e.M["transitions"] if t["label"] == "t2"), 0, 800)
        e.cambia()

    def _tres_acciones(self, e, ids):
        """Una etapa con tres acciones: continua con condición, por evento (banderita) y al desactivar."""
        self._apartar_t2(e)
        e.nueva_variable("Q00", "output")
        e.nueva_variable("CT", "internal", {"kind": "int"})
        e.nueva_variable("M1", "internal")
        sid = ids["1"]
        e.poner_accion(sid, {"tipo": "continua", "variable": "Q00", "condicion": "marcha AND NOT paro"})
        e.poner_accion(sid, {"tipo": "evento", "variable": "CT", "valor": "CT + 1", "evento": "↑(marcha + paro)"})
        e.poner_accion(sid, {"tipo": "desactivacion", "variable": "M1", "valor": "0"})
        return sid

    def test_SEDI82_colocacion_de_las_acciones_de_una_etapa(self):
        """REQ-ACT-01, REQ-EDT-02, REQ-DAT-01: por defecto, cajas pegadas en fila; el botón derecho en la etapa ofrece
        «Colocación de las acciones» (en fila pegadas, en fila separadas, en columna) con la actual marcada; se guarda por
        etapa en `presentation.actionLayouts` (sin clave, «fila»), es una operación de vista que se deshace, no cambia el
        modelo, viaja con el proyecto y la Vista."""
        from escritorio.diagrama import ACT_GAP, H, _extra
        from escritorio.edicion import Edicion
        w = self.w
        e, ids, ts = self.secuencial()
        e.pedir_accion = lambda sid, aid: None  # sin diálogos
        e.confirmar_borrado = lambda plan: True
        sid = self._tres_acciones(e, ids)
        aids = e.ed.get(sid)["actionRefs"]

        def cajas():
            return [next(c for c in w.diagrama.cajas_acciones if c["id"] == a)["rect"] for a in aids]
        # por defecto: en fila, pegadas, y sin clave en la presentación
        self.assertEqual((e.colocacion(sid), "actionLayouts" in e.ed.presentation), ("fila", False))
        r = cajas()
        self.assertTrue(all(abs(r[i][0] + r[i][2] - r[i + 1][0]) < 0.01 and r[i][1] == r[i + 1][1] for i in range(2)))
        # el menú de la etapa: submenú con las tres opciones y la actual marcada
        c = centro(e.M, sid)
        opciones = dict(e.menu(c))
        self.assertEqual([t for t, _ in opciones["Colocación de las acciones"]],
                         ["En fila, pegadas", "En fila, separadas", "En matriz de 2", "En columna"])
        self.assertEqual(e.menu_marcadas, {"En fila, pegadas", "Etapa"})
        menu = w.diagrama.menu_contextual(e.menu(c))
        sub = next(a.menu() for a in menu.actions() if a.menu() is not None)
        self.assertEqual([(a.text(), a.isChecked()) for a in sub.actions()],
                         [("En fila, pegadas", True), ("En fila, separadas", False), ("En matriz de 2", False),
                          ("En columna", False)])
        modelo, revision, n = copy.deepcopy(e.ed.model), e.ed.model["revisionId"], len(e.ed.undo_stack)
        # en fila, separadas
        dict(opciones["Colocación de las acciones"])["En fila, separadas"]()
        self.assertEqual((e.ed.presentation["actionLayouts"], len(e.ed.undo_stack)), ({sid: "fila-separada"}, n + 1))
        self.assertEqual((e.ed.model, e.ed.model["revisionId"]), (modelo, revision), "solo presentación")
        r = cajas()
        self.assertTrue(all(abs(r[i + 1][0] - (r[i][0] + r[i][2]) - ACT_GAP) < 0.01 and r[i][1] == r[i + 1][1] for i in range(2)))
        e.menu(c)
        self.assertEqual(e.menu_marcadas, {"En fila, separadas", "Etapa"}, "el menú marca la colocación actual")
        # en columna: una debajo de otra, del mismo ancho, con el hueco que piden sus marcas
        e.colocar_acciones(sid, "columna")
        self.assertEqual(e.ed.presentation["actionLayouts"], {sid: "columna"})
        r = cajas()
        self.assertEqual({(x, w_) for x, _, w_, _ in r}, {(r[0][0], r[0][2])})
        acciones = [a for s in e.M["steps"] if s["id"] == sid for a in s["actions"]]
        for i in range(2):
            hueco = r[i + 1][1] - (r[i][1] + 2 * H)
            self.assertGreaterEqual(hueco, _extra(acciones[i])[1] + _extra(acciones[i + 1])[0], "sitio para las marcas")
        # una operación de vista, con deshacer y rehacer
        e.deshacer()
        self.assertEqual(e.colocacion(sid), "fila-separada")
        e.deshacer()
        self.assertEqual((e.colocacion(sid), "actionLayouts" in e.ed.presentation), ("fila", False))
        e.rehacer()
        e.rehacer()
        self.assertEqual(e.colocacion(sid), "columna")
        self.assertIn("Mover arriba", dict(e.menu(centro_caja(w, aids[0]))), "en columna se mueve arriba y abajo")
        e.colocar_acciones(sid, "columna")  # la misma: no es una operación
        self.assertEqual(len(e.ed.undo_stack), n + 2)
        # un borrador unido a la etapa va al final según la colocación
        did = e.poner_accion_suelta(QPointF(900, 600))
        e.unir_accion(did, sid)
        orden = [c["id"] for c in sorted((c for c in w.diagrama.cajas_acciones if c["etapa"] == sid), key=lambda c: c["rect"][1])]
        self.assertEqual(orden[-1], did)
        e.colocar_acciones(sid, "fila")
        orden = [c["id"] for c in sorted((c for c in w.diagrama.cajas_acciones if c["etapa"] == sid), key=lambda c: c["rect"][0])]
        self.assertEqual(orden[-1], did)
        self.assertIn("Mover a la izquierda", dict(e.menu(centro_caja(w, aids[0]))))
        e.colocar_acciones(sid, "fila-separada")
        # guardar, abrir y simular
        destino = Path(self.tmp.name) / "p"
        e.guardar(destino)
        op = open_model(destino)
        self.assertEqual(op.presentations[0]["actionLayouts"], {sid: "fila-separada"})
        e2 = Edicion.desde(op.doc, {}, "abierto", None, op.presentations[0])
        self.assertEqual(e2.colocacion(sid), "fila-separada")
        v = Vista("k", "t", "", lambda: (op.doc, layout_from_presentation(op.presentations[0])),
                  normalize_options(None), presentation=op.presentations[0])
        self.assertEqual({s["id"]: s["actionLayout"] for s in v.model["steps"]}[sid], "fila-separada")
        v2 = Vista("k", "t", "", lambda: (op.doc, {}), normalize_options(None))
        self.assertEqual({s["actionLayout"] for s in v2.model["steps"]}, {"fila"}, "sin clave, en fila")
        # un valor desconocido en el fichero vale «fila»; uno inválido no se puede poner
        pres = copy.deepcopy(op.presentations[0])
        pres["actionLayouts"] = {sid: "rara"}
        self.assertEqual(Edicion.desde(op.doc, {}, "x", None, pres).colocacion(sid), "fila")
        with self.assertRaises(DiagnosticError):
            e.ed.set_action_layout(sid, "rara")
        with self.assertRaises(DiagnosticError):
            e.ed.set_action_layout("s-no-existe", "columna")
        # borrar la etapa borra su colocación
        e.seleccionar([sid])
        e.borrar()
        self.assertNotIn("actionLayouts", e.ed.presentation)

    def test_SEDI83_condicion_y_banderita_encima_sin_solaparse(self):
        """REQ-ACT-01: en las tres colocaciones, la condición (trazo vertical a la izquierda de la caja y su texto), la
        banderita de evento y la flecha de al activar o al desactivar se dibujan encima de su caja (la de al desactivar,
        debajo) sin invadir a las cajas vecinas; cada caja se ensancha con su texto, con su condición y con su evento."""
        from PySide6.QtWidgets import QGraphicsTextItem
        from escritorio.diagrama import ACT_MIN, _Pintor, _ancho_accion
        w = self.w
        e, ids, ts = self.secuencial()
        sid = self._tres_acciones(e, ids)
        e.nueva_variable("CONTADOR12343", "internal", {"kind": "int"})
        e.poner_accion(sid, {"tipo": "activacion", "variable": "CONTADOR12343", "valor": "CONTADOR12343 + 1"})
        acciones = [a for s in e.M["steps"] if s["id"] == sid for a in s["actions"]]
        for lay in ("fila", "fila-separada", "columna"):
            e.colocar_acciones(sid, lay)
            cajas = {c["id"]: c["rect"] for c in w.diagrama.cajas_acciones if c["etapa"] == sid}
            for a in acciones:  # el ancho: el de su texto, y el que piden su condición o su evento
                x, y, ancho, alto = cajas[a["id"]]
                self.assertGreaterEqual(ancho, max(ACT_MIN, _Pintor.ancho(a["text"], 15) + 24) - 0.01, (lay, a["text"]))
                self.assertAlmostEqual(ancho, _ancho_accion(a), delta=0.01) if lay != "columna" else None
            if lay == "columna":
                self.assertEqual(len({round(r[2], 2) for r in cajas.values()}), 1, "misma anchura en columna")
            rects = list(cajas.values())
            textos = [it for it in w.diagrama.scene().items() if isinstance(it, QGraphicsTextItem)]
            marcas = [it for it in textos if not any(QRectF_contiene(r, it.sceneBoundingRect().center()) for r in rects)
                      and it.sceneBoundingRect().center().x() > min(r[0] for r in rects)]
            self.assertTrue(marcas, "la condición y el evento están dibujados")
            for it in marcas:
                rt = it.sceneBoundingRect()
                for r in rects:  # no invade ninguna caja
                    self.assertFalse(rt.adjusted(0.5, 0.5, -0.5, -0.5).intersects(QRectF_de(r)), (lay, it.toPlainText()))
                debajo = next((r for r in rects if r[0] <= rt.left() <= r[0] + r[2]), None)
                if debajo is not None:  # y cabe sobre su caja (no se mete en el espacio de la vecina)
                    self.assertLessEqual(rt.right(), debajo[0] + debajo[2] + 0.5, (lay, it.toPlainText()))

    def test_SEDI85_papel_y_tipo_como_texto_con_desplegable_al_editar(self):
        """REQ-EDT-07: Papel y Tipo se ven como texto; al editar la celda aparece un desplegable con las opciones y al elegir se
        aplica (una operación de deshacer); el nombre se estira, no hay barra horizontal y el nombre completo va en el
        tooltip."""
        from PySide6.QtWidgets import QComboBox
        w = self.w
        e, ids, ts = self.secuencial()
        w.show()
        self.app.processEvents()
        pv = w.variables
        e.nueva_variable("un_nombre_muy_largo_de_variable", "output")
        self.app.processEvents()
        self.assertEqual(pv.tabla.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # visible si no cabe
        r = [pv.tabla.item(i, 0).text() for i in range(pv.tabla.rowCount())].index("un_nombre_muy_largo_de_variable")
        self.assertEqual(pv.tabla.item(r, 0).toolTip(), "un_nombre_muy_largo_de_variable")
        tabla = pv.tabla
        self.assertLessEqual(sum(tabla.columnWidth(c) for c in range(3)), tabla.viewport().width() + 1, "sin barra horizontal")
        deleg = tabla.itemDelegate()
        editor = deleg.createEditor(tabla.viewport(), None, tabla.model().index(r, 1))
        self.assertIsInstance(editor, QComboBox)
        self.assertEqual([editor.itemText(i) for i in range(editor.count())], ["Entrada", "Salida", "Memoria"])
        self.assertEqual(editor.currentText(), "Salida")
        n = len(e.ed.undo_stack)
        editor.setCurrentIndex(2)
        editor.activated.emit(2)
        self.assertEqual((e.ed.model["variables"][r]["role"], len(e.ed.undo_stack)), ("internal", n + 1))
        self.assertEqual(tabla.item(r, 1).text(), "Memoria")
        # un clic en la celda abre su editor
        tabla.clicked.emit(tabla.model().index(r, 2))
        self.assertEqual(tabla.state(), tabla.State.EditingState)

    def test_SEDI86_limitada_dibuja_x_de_la_etiqueta_no_del_id(self):
        """REQ-ACT-01: la condición de una acción limitada (`NOT 3s/X…`) usa la etiqueta de la etapa (X0), no su ID interno,
        en las del modelo y en los borradores; el banco lee la misma vista."""
        from PySide6.QtCore import QPointF
        w = self.w
        w.nuevo()
        e = w.edicion
        e.pedir_accion = lambda sid, aid: None
        e.nueva_variable("Q01", "output")
        sid = e.poner_etapa(QPointF(40, 60))
        e.ed.rename(sid, "E7")
        e.cambia()
        self.assertNotEqual(sid, "E7")
        e.poner_accion(sid, {"tipo": "limitada", "variable": "Q01", "limite": "3s"})
        did = e.poner_accion_suelta(QPointF(300, 200))
        e.ed.update_draft_action(did, tipo="limitada", etapa=sid, limite="2s")
        e.cambia()
        txt = lambda segs: "".join(x["t"] for x in segs)  # noqa: E731
        (st,) = e.M["steps"]
        self.assertEqual(txt(st["actions"][0]["cond"]), "3s/X7")
        self.assertEqual(txt(e.M["draftActions"][0]["cond"]), "2s/X7")

    def test_SEDI84_banco_dibuja_las_colocaciones_como_el_editor(self):
        """REQ-ACT-01: tools/dibujo.js (banco y comparador) lee `actionLayout` de la vista y dibuja las cuatro colocaciones
        con las mismas medidas que escritorio/diagrama.py."""
        from escritorio import diagrama
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        import re
        for nombre in ("ACT_MIN", "ACT_GAP", "ACT_BUS", "ACT_COL", "ACT_LINK", "ACT_CANAL"):
            valor = re.search(rf"const {nombre}\s*=\s*(\d+);", js)
            self.assertEqual(int(valor.group(1)), getattr(diagrama, nombre), nombre)
        for texto in ("s.actionLayout", '"fila-separada"', '"matriz-2"', '"columna"', "actionExtra", "drawAction("):
            self.assertIn(texto, js)
        ver = Vista("k", "t", "", lambda: (new_grafcet_document("k"), {}), normalize_options(None))
        self.assertEqual(ver.model["steps"], [])

    # -- P-IMP-43: paleta solo arrastrando, carpeta de acciones, pegar y agrupar acciones, enlace de acciones, condición
    # y evento con bloques, nombres reservados --------------------------------------------------------------------
    def _caja(self, aid):
        return next(c for c in self.w.diagrama.cajas_acciones if c["id"] == aid)

    def _der(self, e, sid):
        from escritorio.diagrama import anclas
        return next(a for a in anclas(e.M, sid) if a["lado"] == "der")["pos"]

    def test_SEDI87_los_elementos_solo_se_colocan_arrastrando(self):
        """REQ-EDT-02: no hay modo herramienta para colocar: un clic en una ficha solo muestra su ayuda, un clic en el
        dibujo no coloca nada y no hay atajos Alt+n; soltar la ficha en el dibujo sí la coloca. Solo queda la herramienta
        que no coloca (seleccionar, Esc)."""
        from PySide6.QtGui import QAction
        from escritorio.edicion import HERRAMIENTAS
        from escritorio.propiedades import AYUDAS
        w = self.w
        w.nuevo()
        e = w.edicion
        self.assertEqual(HERRAMIENTAS, ("seleccionar",))
        self.assertEqual(list(w.a_herr), ["seleccionar"])
        atajos = [a.shortcut().toString() for a in w.findChildren(QAction)]
        self.assertFalse([x for x in atajos if x.startswith("Alt+")], "sin atajos de colocar")
        self.assertIn("Esc", atajos)
        self.assertFalse(hasattr(w.paleta, "elegida") or hasattr(w.paleta, "elegir"), "la paleta ya no elige herramienta")
        n = len(e.ed.undo_stack)
        w.paleta.setCurrentRow(0)
        w.paleta.itemClicked.emit(w.paleta.item(1))  # un clic en la ficha «Etapa»
        self.assertEqual((e.herramienta, e.mensaje, e.mensaje_info), ("seleccionar", AYUDAS["etapa"], True))
        e.prensar(QPointF(500, 60))  # y un clic en el dibujo no coloca nada
        e.soltar(QPointF(500, 60))
        self.assertEqual((e.M["steps"], len(e.ed.undo_stack)), ([], n))
        w.paleta.itemClicked.emit(w.paleta.item(7))  # la ficha «Acción»
        self.assertEqual(e.mensaje, AYUDAS["accion:continua"])
        self.assertEqual(w.ayuda.text(), AYUDAS["accion:continua"])
        self.soltar_ficha("etapa", QPointF(300, 60))  # arrastrada, sí
        self.assertEqual(len(e.M["steps"]), 1)
        self.assertEqual(w.l_herr.text().count("Seleccionar"), 1)

    def test_SEDI88_paleta_por_secciones_y_cinco_fichas_de_accion(self):
        """REQ-ACT-01, REQ-EDT-02: la paleta es una sola lista, sin carpetas, con etapa, transición, simultaneidad, una
        ficha «Acción» (la continua, dibujada con la misma función que el diagrama) y las de jerarquía (macroetapa y
        encapsulante, S-EDI170); arrastrar la de acción crea una acción continua
        suelta donde se suelta, sin diálogo, con «?» en lo que falta; los otros tipos se piden con botón derecho
        (conservan su ficha dibujada en el menú «Tipo de acción»)."""
        from PySide6.QtWidgets import QTabWidget
        from escritorio import diagrama, propiedades
        w = self.w
        w.nuevo()
        e = w.edicion
        self.assertFalse(hasattr(w, "carpetas") or hasattr(w, "paleta_acciones") or hasattr(propiedades, "PaletaAcciones"))
        self.assertEqual(w.dock.findChildren(QTabWidget), [], "sin pestañas: la lista, directamente")
        self.assertIs(w.paleta.parent(), w.dock)
        pa = w.paleta
        fichas = [pa.item(i) for i in range(pa.count()) if pa.item(i).data(Qt.ItemDataRole.UserRole)]
        self.assertEqual([pa.mimeData([it]).text() for it in fichas], list(propiedades.COLOCABLES))
        self.assertEqual([pa.item(i).text() for i in range(pa.count()) if not pa.item(i).data(Qt.ItemDataRole.UserRole)],
                         ["Etapas", "Transiciones", "Acciones", "Jerarquías", "Otros"])
        self.assertEqual(len(fichas), 15)
        self.assertTrue(all(not it.icon().isNull() and it.toolTip() for it in fichas))
        self.assertNotIn("carpeta", w.ayuda.text())
        self.assertIn("paleta", w.ayuda.text())
        # la figura es lo que `_caja_accion` dibuja, y el icono de cada tipo sigue existiendo para el menú de tipo
        tipos = [t for t, _ in diagrama.FICHAS_ACCION]
        self.assertEqual(tipos, ["continua", "condicionada", "activacion", "desactivacion", "evento"])
        imagenes = [diagrama.icono_accion(t).pixmap(84, 64).toImage() for t in tipos]
        self.assertEqual(len({bytes(im.constBits()) for im in imagenes}), 5, "cada tipo, su dibujo en el menú")
        pm, punto = propiedades.figura("accion:continua", 1.0, 1.0)
        self.assertTrue(pm.rect().contains(punto) and punto.x() == 8)
        # arrastrar de verdad: QDrag con la figura y el texto de la ficha
        capturados = []

        class FalsoDrag:
            def __init__(self, origen):
                self.datos = {}
                capturados.append(self)

            def setMimeData(self, m):
                self.datos["texto"] = m.text()

            def setPixmap(self, pm):
                self.datos["pm"] = pm

            def setHotSpot(self, p):
                self.datos["punto"] = p

            def exec(self, *a):
                return Qt.DropAction.IgnoreAction
        with mock.patch.object(propiedades, "QDrag", FalsoDrag):
            pa.setCurrentRow(7)
            pa.startDrag(Qt.DropAction.CopyAction)
        self.assertEqual([c.datos["texto"] for c in capturados], ["accion:continua"])
        self.assertTrue(all(c.datos["pm"].rect().contains(c.datos["punto"]) for c in capturados))
        # soltar la ficha en vacío: una acción continua suelta, sin diálogo, con «?» y dibujada como cualquier acción
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        self.soltar_ficha("accion:continua", QPointF(300, 100))
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], pedidas), ("continua", []))
        self.assertTrue("variable" not in b and "etapa" not in b)
        # sin discontinuo ni naranja, como cualquier acción
        from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem
        trazos = [it.pen() for it in w.diagrama.scene().items() if isinstance(it, (QGraphicsRectItem, QGraphicsPathItem))
                  and it.zValue() < 10 and it.pen().style() != Qt.PenStyle.NoPen]
        self.assertTrue(trazos)
        self.assertTrue(all(p.style() == Qt.PenStyle.SolidLine and p.color().name() != diagrama.COL["glow"] for p in trazos))
        # el tipo se cambia con botón derecho (la operación del menú «Tipo de acción»)
        e.tipo_accion(b["id"], "evento")
        self.assertEqual(e.ed.draft_actions()[0]["tipo"], "evento")

    def test_SEDI89_punto_derecho_de_la_etapa_y_union_con_acciones_sueltas(self):
        """REQ-ACT-01, REQ-EDT-02: la etapa tiene un punto de unión en el centro de su lado derecho (visible al pasar el
        puntero); arrastrar de él hasta una acción suelta la une, y arrastrar del punto izquierdo de la acción hasta
        cualquier parte de la etapa o hasta ese punto también; de él no sale nada hacia lo que no es una acción."""
        from escritorio.diagrama import H, ancla_en
        w = self.w
        e, ids, ts = self.secuencial()
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        c = centro(e.M, ids["1"])
        der = self._der(e, ids["1"])
        self.assertEqual(der, QPointF(c.x() + H, c.y()))
        self.assertEqual(ancla_en(e.M, der + QPointF(5, 3))["lado"], "der")
        e.pasar(c + QPointF(H - 2, 2))
        self.assertEqual(len(w.diagrama._marcas), 3)
        # de la etapa a la acción suelta (a su caja)
        d1 = e.poner_accion_suelta(QPointF(700, 400))
        e.prensar(der)
        self.assertIsNotNone(e.enlace)
        e.mover(centro_caja(w, d1))
        e.soltar(centro_caja(w, d1))
        self.assertEqual((e.ed.draft_actions()[0]["etapa"], pedidas), (ids["1"], [(ids["1"], d1)]))
        # con la etapa ya con acciones, su punto solo se agarra de cerca (ahí empieza el enlace, que se selecciona)
        self.assertIsNone(ancla_en(e.M, der + QPointF(12, 0)), "a más de 8: no es un punto de unión")
        self.assertIsNotNone(ancla_en(e.M, der + QPointF(4, 0)))
        # de la acción a cualquier parte de la etapa
        d2 = e.poner_accion_suelta(QPointF(700, 500))
        self._enlazar_accion(e, d2, c + QPointF(5, 5))
        self.assertEqual([b["etapa"] for b in e.ed.draft_actions()], [ids["1"], ids["1"]])
        # y al punto del lado derecho de otra etapa
        d3 = e.poner_accion_suelta(QPointF(700, 600))
        self._enlazar_accion(e, d3, self._der(e, ids["0"]))
        self.assertEqual(e.ed.draft_actions()[2]["etapa"], ids["0"])
        # de la etapa a un hueco nace una continua; a una transición se sigue rechazando
        n = len(e.ed.undo_stack)
        e.prensar(self._der(e, ids["0"]))
        e.soltar(QPointF(900, 700))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertEqual(e._datos_borrador(e._borrador(e.accion))["tipo"], "continua")
        e.deshacer()
        self.assertEqual(len(e.ed.undo_stack), n)
        e.prensar(self._der(e, ids["0"]))
        e.soltar(centro(e.M, ts["t1"]))
        self.assertIn("Una acción se une a una etapa", e.mensaje)
        self.assertEqual(len(e.ed.undo_stack), n)
        # el punto de la derecha solo vale para el enlace de una acción: los demás enlaces lo ignoran
        self.assertIsNone(ancla_en(e.M, self._der(e, ids["0"]), sin_der=True))

    def _etapa_con_dos_acciones(self):
        e, ids, ts = self.secuencial()
        self._apartar_t2(e)
        e.pedir_accion = lambda sid, aid: None
        e.nueva_variable("Q00", "output", {"kind": "bool"})
        e.nueva_variable("Q01", "output", {"kind": "bool"})
        e.nueva_variable("Q02", "output", {"kind": "bool"})
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00"}))
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q01"}))
        return e, ids, ts

    def test_SEDI90_pegar_una_accion_al_lado_de_otra_con_iman(self):
        """REQ-ACT-01, REQ-EDT-02: soltar (o mover) una acción suelta de modo que toque el lado derecho de otra acción de la
        etapa la añade a ella detrás de ella, con el lado resaltado antes de soltar; completa, pasa al modelo en su sitio;
        incompleta, queda unida con «?». En columna se pega también por el lado inferior; en fila separada, en el
        siguiente lugar. Es una sola operación de deshacer."""
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        s1 = ids["1"]
        a1, a2 = [a["id"] for a in e.acciones(s1)]
        x, y, ancho, alto = self._caja(a1)["rect"]
        # el resalte aparece al pasar la ficha cerca del lado derecho de la primera, y se va al alejarse
        e.sobrevolar("accion:continua", QPointF(x + ancho + 6, y + alto / 2))
        self.assertIsNotNone(w.diagrama.iman)
        recta = w.diagrama.iman.line()
        self.assertEqual((round(recta.x1()), round(recta.y1()), round(recta.y2())), (round(x + ancho), round(y), round(y + alto)))
        e.sobrevolar("accion:continua", QPointF(x + ancho + 90, y + alto / 2 + 300))
        self.assertIsNone(w.diagrama.iman)
        # lo mismo, con el evento de Qt cuando se arrastra una ficha sobre el dibujo
        from PySide6.QtGui import QDragMoveEvent
        m = QMimeData()
        m.setText("accion:continua")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            w.diagrama.dragMoveEvent(QDragMoveEvent(w.diagrama.mapFromScene(QPointF(x + ancho + 6, y + alto / 2)),
                                                    Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                                                    Qt.KeyboardModifier.NoModifier))
        self.assertIsNotNone(w.diagrama.iman)
        w.diagrama.marcar_iman(None)
        e.sobrevolar("etapa", QPointF(x + ancho + 6, y + alto / 2))
        self.assertIsNone(w.diagrama.iman)
        # soltar una ficha «Al activar» (incompleta) tocando la derecha de la primera: queda unida, con «?»
        n = len(e.ed.undo_stack)
        self.soltar_ficha("accion:activacion", QPointF(x + ancho + 6, y + alto / 2))
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una operación de deshacer")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["etapa"], b["tipo"], "grupo" in b), (s1, "activacion", False))
        self.assertEqual([a["id"] for a in e.acciones(s1)], [a1, a2, b["id"]], "los borradores, tras las del modelo")
        self.assertEqual((e.sel, e.accion), ([s1], b["id"]))
        e.deshacer()
        self.assertEqual((e.ed.draft_actions(), len(e.ed.undo_stack)), ([], n))
        # una acción suelta completa, movida con el ratón hasta tocar la derecha de la primera: pasa al modelo detrás de ella
        d = e.poner_accion_suelta(QPointF(800, 500))
        self.assertIsNone(e.poner_accion(None, {"tipo": "continua", "variable": "Q02"}, d))
        cd = self._caja(d)["rect"]
        e.prensar(QPointF(cd[0] + 20, cd[1] + 20))
        e.mover(QPointF(x + ancho + 20 + 4, y + 20 + 2))
        self.assertIsNotNone(w.diagrama.iman, "al mover, el lado donde se pegaría")
        n = len(e.ed.undo_stack)
        e.soltar(QPointF(x + ancho + 20 + 4, y + 20 + 2))
        self.assertEqual((e.ed.draft_actions(), len(e.ed.undo_stack)), ([], n + 1))
        nombres = [e.datos_accion(a["id"])["variable"] for a in e.acciones(s1)]
        self.assertEqual(nombres, ["Q00", "Q02", "Q01"], "detrás de la primera, no al final")
        self.assertIsNone(w.diagrama.iman, "ya no se resalta")
        self.assertTrue(e.ed.validate().can_simulate)
        e.deshacer()
        self.assertEqual([e.datos_accion(a["id"])["variable"] for a in e.acciones(s1)], ["Q00", "Q01"])
        self.assertEqual(len(e.ed.draft_actions()), 1, "vuelve a ser suelta, donde estaba")
        # en columna: también por el lado inferior, en el siguiente lugar
        e.deshacer()
        e.deshacer()
        e.colocar_acciones(s1, "columna")
        x1, y1, w1, h1 = self._caja(a1)["rect"]
        n = len(e.ed.undo_stack)
        self.soltar_ficha("accion:continua", QPointF(x1 + 10, y1 + h1 + 8 + 22))  # su lado izquierdo, justo bajo la primera
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["etapa"], len(e.ed.undo_stack)), (s1, n + 1))
        # la nueva ocupa el lugar de entre medias: las de modelo antes, el borrador después (orden de dibujo)
        orden = [c["id"] for c in w.diagrama.cajas_acciones if c["etapa"] == s1]
        self.assertEqual(orden, [a1, a2, b["id"]])
        e.deshacer()
        # en fila separada: al lado derecho de la primera (en el hueco) se pega en el siguiente lugar
        e.colocar_acciones(s1, "fila-separada")
        x1, y1, w1, h1 = self._caja(a1)["rect"]
        self.soltar_ficha("accion:evento", QPointF(x1 + w1 + 6, y1 + h1 / 2))
        self.assertEqual(len(e.ed.draft_actions()), 1)
        self.assertEqual(e.ed.draft_actions()[0]["etapa"], s1)

    def test_SEDI91_grupos_sueltos_se_mueven_y_se_unen_juntos(self):
        """REQ-ACT-01, REQ-DAT-01: varias acciones sueltas pegadas forman un grupo suelto (`grupo` y `orden` en la
        presentación) que se selecciona entero, se mueve junto, tiene su colocación y se une a una etapa de una vez
        (completas, al modelo; en una operación de deshacer); se guarda y se abre; la que se separa deja el grupo, que
        se disuelve con menos de dos."""
        from escritorio.diagrama import anclas
        from escritorio.edicion import Edicion
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        s0 = ids["0"]
        a = e.poner_accion_suelta(QPointF(600, 300))
        x, y, ancho, alto = self._caja(a)["rect"]
        b = e.poner_accion_suelta(QPointF(x + ancho + 4, y + alto / 2), "condicionada")  # pegada a la derecha
        c = e.poner_accion_suelta(QPointF(x + 2 * ancho + 4, y + alto / 2), "activacion")
        borradores = e.ed.draft_actions()
        self.assertEqual([d["id"] for d in borradores], [a, b, c])
        g = borradores[0]["grupo"]
        self.assertTrue(g and all(d["grupo"] == g for d in borradores))
        self.assertEqual([d["orden"] for d in borradores], [0, 1, 2])
        self.assertEqual(len({(d["x"], d["y"]) for d in borradores}), 1, "comparten posición")
        cajas = [self._caja(i)["rect"] for i in (a, b, c)]
        self.assertEqual([r[0] for r in cajas], [cajas[0][0], cajas[0][0] + cajas[0][2], cajas[0][0] + cajas[0][2] + cajas[1][2]])
        self.assertEqual([m["cabeza"] for m in e.M["draftActions"]], [True, False, False])
        self.assertEqual([x["lado"] for i in (a, b, c) for x in anclas(e.M, i)], ["izq"], "un solo punto de unión: el del grupo")
        self.assertEqual({self._caja(i)["grupo"] for i in (a, b, c)}, {g})
        # se selecciona entero y se mueve junto (una operación)
        cen = centro_caja(w, b)
        e.prensar(cen)
        e.soltar(cen)
        self.assertEqual((e.sel, e.accion), ([a, b, c], b))
        self.assertEqual(e.seleccion_dibujo() & {f"accion:{i}" for i in (a, b, c)}, {f"accion:{i}" for i in (a, b, c)})
        n = len(e.ed.undo_stack)
        e.prensar(cen)
        e.mover(cen + QPointF(60, 40))
        self.assertEqual(len({(m["x"], m["y"]) for m in e.M["draftActions"]}), 1, "el grupo entero, mientras se arrastra")
        e.soltar(cen + QPointF(60, 40))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertEqual({(d["x"], d["y"]) for d in e.ed.draft_actions()}, {("560", "340")})
        # colocación del grupo: en columna, la segunda debajo de la primera
        dict(e.menu(centro_caja(w, b)))["Colocación de las acciones"][3][1]()
        self.assertEqual(e.ed.action_layouts(), {g: "columna"})
        r = [self._caja(i)["rect"] for i in (a, b, c)]
        self.assertEqual((r[0][0], r[1][0], r[2][0]), (r[0][0],) * 3)
        self.assertLess(r[0][1], r[1][1])
        e.menu(centro_caja(w, b))
        self.assertEqual(e.menu_marcadas & {"En columna"}, {"En columna"})
        # se guarda y se abre tal cual
        destino = Path(self.tmp.name) / "con-grupo"
        e.guardar(destino)
        e2 = Edicion.desde(open_model(destino).doc, {}, "abierto", destino, open_model(destino).presentations[0])
        self.assertEqual(e2.ed.draft_actions(), e.ed.draft_actions())
        self.assertEqual(e2.ed.action_layouts(), {g: "columna"})
        # completar las dos primeras y unir el grupo a la etapa 0 de una vez: las completas pasan al modelo, en orden
        self.assertIsNone(e.poner_accion(None, {"tipo": "continua", "variable": "Q00"}, a))
        self.assertIsNone(e.poner_accion(None, {"tipo": "condicionada", "variable": "Q02", "condicion": "marcha"}, b))
        n = len(e.ed.undo_stack)
        self._enlazar_accion(e, a, centro(e.M, s0))
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación")
        self.assertEqual([x["variable"] for x in e.acciones(s0)], ["Q00", "Q02", ""])
        self.assertEqual([x.get("borrador") for x in e.acciones(s0)], [None, None, True])
        self.assertEqual((len(e.ed.model["actions"]), e.ed.action_layouts()), (4, {}), "el grupo ya no existe, ni su colocación")
        self.assertEqual({d.get("grupo") for d in e.ed.draft_actions()}, {None})
        e.deshacer()
        self.assertEqual(({d["grupo"] for d in e.ed.draft_actions()}, e.ed.action_layouts()), ({g}, {g: "columna"}))
        self.assertEqual(len(e.ed.model["actions"]), 2)
        # separar una del grupo: el grupo se disuelve con menos de dos
        e.separar_accion(c)
        self.assertEqual([d.get("grupo") for d in e.ed.draft_actions()], [g, g, None])
        e.separar_accion(b)
        self.assertEqual(({d.get("grupo") for d in e.ed.draft_actions()}, e.ed.action_layouts()), ({None}, {}))
        # quitar y borrar un grupo con Supr
        d1 = e.poner_accion_suelta(QPointF(900, 600))
        d2 = e.poner_accion_suelta(QPointF(900 + 80 + 100 - 96, 600))
        self.assertEqual(len(e._ids_grupo(d1)), 2)
        e.seleccionar(e._ids_grupo(d1))
        w.a_borrar.trigger()
        self.assertNotIn(d1, [d["id"] for d in e.ed.draft_actions()])
        self.assertNotIn(d2, [d["id"] for d in e.ed.draft_actions()])

    def test_SEDI92_el_enlace_de_las_acciones_se_selecciona_y_se_elimina(self):
        """REQ-ACT-01, REQ-EDT-02: el trazo que une la etapa con sus acciones se selecciona con un clic (se resalta); Supr
        o botón derecho → «Eliminar el enlace» las separa de la etapa: quedan sueltas e independientes (sin grupo), cada
        una donde estaba y sin solaparse, con todos sus datos; una operación de deshacer. Borrar una etapa con acciones
        las deja igual."""
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        s1 = ids["1"]
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "activacion", "variable": "Q02", "valor": "1"}))
        e.anadir_accion(s1)  # un borrador unido, sin variable
        e.colocar_acciones(s1, "columna")
        antes = [(a["id"], e.datos_accion(a["id"])) for a in e.acciones(s1)]
        self.assertEqual(len(antes), 4)
        x0, y0, _, alto = self._caja(antes[0][0])["rect"]
        u = next(u for u in w.diagrama.uniones_acciones if u["id"] == f"enlaceacc:{s1}")
        tramo = u["trazos"][0]
        p = QPointF((tramo[0][0] + tramo[1][0]) / 2, tramo[0][1] + 2)
        e.prensar(p)
        e.soltar(p)
        self.assertEqual((e.sel, e.accion), ([f"enlaceacc:{s1}"], None))
        self.assertIn("enlace de las acciones de la etapa 1", e.nombre(e.sel[0]))
        gruesos = [it for it in w.diagrama.scene().items() if hasattr(it, "pen") and it.pen().widthF() == 4.0
                   and it.pen().color().name() == "#1f6feb"]
        self.assertTrue(gruesos, "el enlace seleccionado se resalta")
        self.assertTrue(w.a_borrar.isEnabled())
        n = len(e.ed.undo_stack)
        w.a_borrar.trigger()  # Supr
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una operación")
        self.assertEqual((e.acciones(s1), e.ed.model["actions"]), ([], []))
        sueltas = sorted(e.ed.draft_actions(), key=lambda d: self._caja(d["id"])["rect"][1])  # de arriba abajo, como estaban
        self.assertEqual(len(sueltas), 4)
        self.assertTrue(all("etapa" not in d and "grupo" not in d and "orden" not in d for d in sueltas))
        self.assertEqual(e.ed.action_layouts(), {s1: "columna"}, "ya no hay grupo ni colocación de grupo")
        self.assertEqual(sorted(e.sel), sorted(d["id"] for d in sueltas))
        rects = [self._caja(d["id"])["rect"] for d in sueltas]
        for i, r in enumerate(rects):
            for q in rects[i + 1:]:
                self.assertTrue(r[0] + r[2] <= q[0] + 0.5 or q[0] + q[2] <= r[0] + 0.5 or r[1] + r[3] <= q[1] + 0.5
                                or q[1] + q[3] <= r[1] + 0.5, "no se solapan")
        # sus datos, intactos: el tipo, la variable, el valor
        datos = [e._datos_borrador(d) for d in sueltas]
        self.assertEqual([(d["tipo"], d["variable"]) for d in datos],
                         [("continua", "Q00"), ("continua", "Q01"), ("activacion", "Q02"), ("continua", "")])
        self.assertEqual(datos[2]["valor"], "1")
        # donde estaban: la primera, con su lado izquierdo en el mismo sitio
        x, y, _, _ = self._caja(sueltas[0]["id"])["rect"]
        self.assertEqual((round(x), round(y)), (round(x0), round(y0)))
        self.assertTrue(e.ed.validate().can_simulate)
        self.assertEqual(w.edicion.diagnosticos()[-1]["code"], "D-ACCION-PENDIENTE")
        e.deshacer()
        self.assertEqual([(a["id"], e.datos_accion(a["id"])) for a in e.acciones(s1)][:3], antes[:3], "vuelven con los mismos ID")
        self.assertEqual((e.ed.draft_actions()[0]["etapa"], e.ed.action_layouts()), (s1, {s1: "columna"}))
        # botón derecho sobre el enlace
        self.assertIsNone(e.union_en(QPointF(1000, 1000)))
        opciones = e.menu(p)
        self.assertEqual([t for t, _ in opciones], ["Eliminar el enlace"])
        self.assertEqual(e.sel, [f"enlaceacc:{s1}"])
        opciones[0][1]()
        self.assertEqual((e.acciones(s1), len(e.ed.draft_actions())), ([], 4))
        # una etapa con una sola acción: queda suelta, sin grupo
        e.deshacer()
        e.quitar_accion(antes[1][0])
        e.quitar_accion(antes[2][0])
        e.quitar_accion(e.acciones(s1)[-1]["id"])
        e.eliminar_enlace_acciones(s1)
        (suelta,) = e.ed.draft_actions()
        self.assertEqual(("grupo" in suelta, suelta["tipo"]), (False, "continua"))
        # el enlace de una etapa sin acciones no existe
        self.assertNotIn(f"enlaceacc:{s1}", [u["id"] for u in w.diagrama.uniones_acciones])
        # al pulsar muy cerca del punto de la derecha, empieza un enlace en lugar de seleccionarlo
        e.deshacer()
        e.deshacer()
        centro1 = centro(e.M, s1)
        e.prensar(QPointF(centro1.x() + 22 + 3, centro1.y()))
        self.assertIsNotNone(e.enlace)
        e.soltar(QPointF(centro1.x() + 22 + 3, centro1.y()))

    def test_SEDI93_condicion_y_evento_de_una_accion_en_el_panel_de_opciones(self):
        """REQ-ACT-01, REQ-EDT-02: al seleccionar una acción condicionada (o por evento, o una continua limitada de un
        fichero) el panel de opciones programa su condición (o su evento) igual que la receptividad de una transición;
        cada cambio es una operación de deshacer; con condición válida pasa al modelo y si se vacía vuelve a ser borrador;
        la limitada conserva su límite; las variables que faltan se crean con «Crear las que faltan»."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        s1 = ids["1"]
        p, prog = w.props, w.props.prog
        a1 = e.acciones(s1)[0]["id"]
        # una continua no se programa
        self.panel_accion(s1, a1)
        self.assertEqual((p.pagina, p.continua, p.objetivo_bloques(), prog.isVisible()), ("vacio", True, None, False))
        # a condicionada: borrador con «?»; sus bloques, vacíos
        e.tipo_accion(a1, "condicionada")
        (b,) = e.ed.draft_actions()
        self.assertEqual(p.objetivo_bloques(), ("accion", b["id"], "condicion"))
        self.assertEqual(p.l_bloques.text(), "Condición de la acción Q00 (etapa 1)")
        self.assertEqual((p.pagina, prog.texto(), p.t_texto.text()), ("accion", "", ""))
        self.assertTrue(p.t_texto.isReadOnly())
        self.assertIn("Vacía", p.t_estado.text())
        # el primer bloque la completa: pasa al modelo, con la condición
        n = len(e.ed.undo_stack)
        prog.colocar(bloques.var("marcha", "input"))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertEqual(e.ed.draft_actions(), [])
        nuevo = e.accion
        self.assertEqual((e.datos_accion(nuevo)["tipo"], e.datos_accion(nuevo)["condicion"]), ("condicionada", "marcha"))
        self.assertEqual(p.objetivo_bloques(), ("accion", nuevo, "condicion"))
        self.assertEqual((prog.texto(), p.t_texto.text()), ("marcha", "marcha"))
        self.assertIn("Condición correcta", p.t_estado.text())
        self.assertIn("marcha", p.t_dibujo.text())
        # cada cambio, una operación; se deshace
        prog.lienzo.soltar((), bloques.nuevo("y"))  # «marcha AND ?»: a medias, vuelve a ser borrador
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["condicion"], e.accion, p.objetivo_bloques()), ("marcha AND ?", b["id"], ("accion", b["id"], "condicion")))
        self.assertEqual(p.t_texto.text(), "marcha AND ?")
        prog.lienzo.soltar(("b",), bloques.var("paro", "input"))  # completa: al modelo otra vez
        nuevo = e.accion
        self.assertEqual((e.ed.draft_actions(), e.datos_accion(nuevo)["condicion"]), ([], "marcha AND paro"))
        self.assertEqual(len(e.ed.undo_stack), n + 3)
        prog.lienzo.soltar(("b",), bloques.nuevo("no"))  # completa → completa: en su sitio, con su ID
        self.assertEqual((e.accion, e.datos_accion(nuevo)["condicion"], len(e.ed.undo_stack)),
                         (nuevo, "marcha AND NOT paro", n + 4))
        e.deshacer()
        self.assertEqual((e.datos_accion(nuevo)["condicion"], prog.texto()), ("marcha AND paro", "marcha AND paro"))
        e.deshacer()
        self.assertEqual(e.ed.draft_actions()[0]["condicion"], "marcha AND ?")
        self.assertIsNone(e.accion, "la acción señalada ya no existe")
        e.deshacer()
        self.assertEqual(e.datos_accion(e.acciones(s1)[-1]["id"])["condicion"], "marcha")
        e.rehacer()
        e.rehacer()
        e.rehacer()
        nuevo = e.acciones(s1)[-1]["id"]
        # vaciarla: vuelve a ser borrador
        self.panel_accion(s1, nuevo)
        prog.lienzo.quitar((0,))
        (b,) = e.ed.draft_actions()
        self.assertEqual((e.acciones(s1)[-1]["id"], e.accion, b.get("condicion")), (b["id"], b["id"], None))
        # el enlace seleccionado explica lo que se puede hacer con él
        e.seleccionar([f"enlaceacc:{s1}"])
        self.assertIn("Eliminar el enlace", p.l_vacio.text())
        e.deshacer()
        self.assertEqual((e.ed.draft_actions(), e.datos_accion(e.acciones(s1)[-1]["id"])["condicion"]),
                         ([], "marcha AND NOT paro"))

    def test_SEDI94_evento_acciones_sueltas_limitada_y_crear_las_que_faltan(self):
        """REQ-ACT-01, REQ-EDT-02, REQ-EDT-07: el panel de opciones programa también el evento de una acción, la condición de
        una acción suelta (y de las de un grupo) y la de una limitada de un fichero antiguo, que conserva su límite;
        «Crear las que faltan» declara las entradas que se usan y no existen; con un nombre que no vale no crea nada,
        avisa y parpadea."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        s1 = ids["1"]
        p, prog = w.props, w.props.prog
        e.nueva_variable("CT", "internal", {"kind": "int"})
        # por evento: «Evento de la acción CT (etapa 1)»
        self.assertIsNone(e.poner_accion(s1, {"tipo": "evento", "variable": "CT", "valor": "CT + 1"}))
        (b,) = e.ed.draft_actions()
        self.panel_accion(s1, b["id"])
        self.assertEqual((p.objetivo_bloques(), p.l_bloques.text()), (("accion", b["id"], "evento"), "Evento de la acción CT (etapa 1)"))
        self.assertIn("Vacía", p.t_estado.text())
        prog.colocar(bloques.var("marcha", "input"))
        prog.lienzo.soltar((), bloques.nuevo("sube"))
        self.assertEqual(prog.texto(), "↑marcha")
        self.assertEqual(e.ed.draft_actions(), [], "con su evento, pasa al modelo")
        evento = e.accion
        self.assertEqual((e.datos_accion(evento)["tipo"], e.datos_accion(evento)["evento"]), ("evento", "↑marcha"))
        self.assertIn("Evento correcto", p.t_estado.text())
        self.assertTrue(e.ed.validate().can_simulate)
        # una variable que no existe: sigue siendo borrador y «Crear las que faltan» la declara y completa la acción
        prog.lienzo.quitar((0,))
        (b,) = e.ed.draft_actions()
        p.t_texto.setText("↑nueva_in")
        p._aplicar()
        self.assertEqual(e.ed.draft_actions()[0]["evento"], "↑nueva_in")
        self.assertIn("No existen: nueva_in", p.t_estado.text())
        self.assertFalse(p.t_crear.isHidden())
        n = len(e.ed.undo_stack)
        p.t_crear.click()
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una operación: la variable y la acción")
        self.assertEqual(next(v for v in e.ed.model["variables"] if v["name"] == "nueva_in")["role"], "input")
        self.assertEqual((e.ed.draft_actions(), e.datos_accion(e.accion)["evento"]), ([], "↑nueva_in"))
        # un nombre que no vale (entre comillas invertidas): no se crea, mensaje y parpadeo
        self.panel_accion(s1, e.acciones(s1)[-1]["id"])
        p.t_texto.setText("↑(`OR`)")
        p._aplicar()
        n = len(e.ed.undo_stack)
        self.assertFalse(p.t_crear.isHidden())
        p.t_crear.click()
        self.assertEqual(len(e.ed.undo_stack), n)
        self.assertNotIn("OR", [v["name"] for v in e.ed.model["variables"]])
        self.assertEqual(p.t_estado.text(), '"OR" no puede ser nombre de variable: es una palabra de las fórmulas')
        self.assertTrue(p.parpadeo_crear.t.isActive())
        self.assertEqual(e.mensaje, p.t_estado.text())
        p.parpadeo_crear.parar()
        # una acción suelta, y las de un grupo
        d = e.poner_accion_suelta(QPointF(800, 300), "condicionada")
        e.seleccionar([d])
        self.assertEqual((p.objetivo_bloques(), p.l_bloques.text()), (("accion", d, "condicion"), "Condición de la acción ? (suelta)"))
        prog.colocar(bloques.var("paro", "input"))
        self.assertEqual((e.ed.draft_actions()[-1]["condicion"], e.ed.draft_actions()[-1]["id"]), ("paro", d), "sigue suelta")
        x, y, ancho, alto = self._caja(d)["rect"]
        d2 = e.poner_accion_suelta(QPointF(x + ancho + 3, y + alto / 2), "evento")
        e.prensar(centro_caja(w, d2))  # el grupo entero seleccionado y la acción señalada, la pulsada
        e.soltar(centro_caja(w, d2))
        self.assertEqual((len(e.sel), e.accion, p.objetivo_bloques()), (2, d2, ("accion", d2, "evento")))
        e.prensar(centro_caja(w, d))
        e.soltar(centro_caja(w, d))
        self.assertEqual((e.accion, p.objetivo_bloques(), prog.texto()), (d, ("accion", d, "condicion"), "paro"))
        # una limitada de un fichero antiguo: su condición se programa y su límite se conserva
        self.assertIsNone(e.poner_accion(s1, {"tipo": "limitada", "variable": "Q02", "condicion": "marcha", "limite": "3s"}))
        lim = e.ed.get(s1)["actionRefs"][-1]
        self.panel_accion(s1, lim)
        self.assertEqual((p.objetivo_bloques(), prog.texto()), (("accion", lim, "condicion"), "marcha"))
        prog.lienzo.soltar((), bloques.nuevo("no"))
        self.assertEqual((e.accion, e.datos_accion(lim)["condicion"], e.ed.get(lim)["limitUs"]), (lim, "NOT marcha", "3000000"))
        self.assertEqual(e.datos_accion(lim)["tipo"], "limitada")
        # sin condición, una limitada solo lleva su límite: sigue completa
        prog.lienzo.quitar((0,))
        self.assertEqual((e.accion, e.datos_accion(lim)["condicion"], e.ed.get(lim)["limitUs"]), (lim, "", "3000000"))
        # transición y acción comparten el panel: al elegir una transición, sus bloques
        e.seleccionar([ts["t1"]])
        self.assertEqual((p.objetivo_bloques(), p.l_bloques.text()), (("transicion", ts["t1"]), "Receptividad de la transición t1"))

    def test_SEDI95_el_panel_conserva_condicion_evento_y_limite(self):
        """REQ-ACT-01, REQ-EDT-02: el panel de la acción no lleva programador de condición dentro y conserva la condición y el
        evento de la acción; una condicionada o por evento sin ellos queda como borrador unido a la etapa (se programan con
        los bloques de su lado); el límite de tiempo solo aparece en una limitada, y quitarlo la deja condicionada."""
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        s1 = ids["1"]
        # añadir una condicionada: sin condición, queda como borrador unido
        d = self.panel_accion(s1)
        self.assertFalse(hasattr(d, "tipo"), "sin lista de tipos: el tipo se cambia con botón derecho sobre la acción")
        self.assertTrue(d.limite.isHidden())
        self.poner_tipo(d, "condicionada")
        d.variable.setCurrentText("Q02")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["etapa"], b["tipo"], "condicion" in b), (s1, "condicionada", False))
        self.assertEqual(w.props.objetivo_bloques(), ("accion", b["id"], "condicion"), "sus bloques, a su lado")
        # por evento: sin evento, borrador; el valor se programa aparte
        d = self.anadir_accion(s1, "evento", "Q02")
        self.assertEqual(e.faltan(e._datos_borrador(e.ed.draft_actions()[1])), ["valor", "evento"])
        d._desde_bloques("1")
        self.assertEqual([x["tipo"] for x in e.ed.draft_actions()], ["condicionada", "evento"])
        self.assertEqual(e.faltan(e._datos_borrador(e.ed.draft_actions()[1])), ["evento"])
        # una condicionada completa: abrir y cambiar la variable conserva su condición
        e.quitar_accion(e.ed.draft_actions()[0]["id"])
        e.quitar_accion(e.ed.draft_actions()[0]["id"])
        self.assertIsNone(e.poner_accion(s1, {"tipo": "condicionada", "variable": "Q02", "condicion": "marcha AND NOT paro"}))
        a = e.acciones(s1)[-1]["id"]
        d = self.panel_accion(s1, a)
        self.assertEqual((d.clave_tipo, d.variable.currentText()), ("condicionada", "Q02"))
        d.variable.setCurrentText("Q01")
        self.assertEqual((e.datos_accion(a)["condicion"], e.datos_accion(a)["variable"]), ("marcha AND NOT paro", "Q01"))
        self.poner_tipo(d, "continua")  # a continua: sin condición
        self.assertEqual((e.datos_accion(a)["tipo"], e.datos_accion(a)["condicion"]), ("continua", ""))
        # una limitada: «Condicionada (con límite de tiempo)»; quitar el límite la deja condicionada, con su condición
        self.assertIsNone(e.poner_accion(s1, {"tipo": "limitada", "variable": "Q02", "condicion": "marcha", "limite": "2s"}))
        lim = e.acciones(s1)[-1]["id"]
        d = self.panel_accion(s1, lim)
        self.assertEqual(d.clave_tipo, "limitada")
        self.assertEqual((d.limite.text(), d.limite.isHidden()), ("2s", False))
        d.limite.setText("")
        d.limite.editingFinished.emit()
        self.assertEqual((e.datos_accion(lim)["tipo"], e.datos_accion(lim)["condicion"]), ("condicionada", "marcha"))
        self.assertNotIn("limitUs", e.ed.get(lim))
        # y con otro tipo, el límite desaparece
        self.assertIsNone(e.poner_accion(s1, {"tipo": "limitada", "variable": "Q02", "limite": "2s"}))
        lim = e.acciones(s1)[-1]["id"]
        d = self.panel_accion(s1, lim)
        self.poner_tipo(d, "continua")
        self.assertEqual((e.datos_accion(lim)["tipo"], "limitUs" in e.ed.get(lim)), ("continua", False))

    def test_SEDI96_nombres_de_variable_reservados(self):
        """REQ-EDT-07, REQ-EDT-09: en la interfaz se rechaza, con mensaje y parpadeo, un nombre de variable que no se puede
        escribir en una fórmula (palabra reservada sin distinguir mayúsculas, símbolos, no empieza por letra ni
        por cifra con alguna letra como 1M1, solo cifras, parecido a una duración como 2s, o confundible con una etapa
        como X1); vale en la tabla de variables y en «Crear las que faltan»; el núcleo no cambia."""
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        for n in ("AND", "and", "Or", "NOT", "true", "False", "rise", "FALL", "active", "activePartial", "activeMacro",
                  "elapsed", "delay", "DELAY"):
            self.assertEqual(e.motivo_nombre(n), f'"{n}" no puede ser nombre de variable: es una palabra de las fórmulas', n)
        for n in ("a*b", "a/b", "(x)", "1-2", "1_", "1_2", "1.5a", "a b/c", "mi var!"):  # («+» y «-» se admiten dentro: test_nombres_con_signos)
            self.assertIn("debe empezar por una letra o _", e.motivo_nombre(n), n)
        for n in ("2", "10", "1.5", "1,5"):  # solo un número: no es un nombre
            self.assertIn("es solo un número", e.motivo_nombre(n), n)
        for n in ("2s", "10ms", "3us", "0.5s", "1 s"):  # se leería como una duración
            self.assertIn("se leería como una duración", e.motivo_nombre(n), n)
        for n in ("X1", "X12"):
            self.assertIn("se confundiría con la actividad de la etapa", e.motivo_nombre(n), n)
        for n in ("marcha", "Q00", "x1", "Xmarcha", "Motor_1", "I0.1", "andar", "Sí", "XX1", "_",
                  "1M1", "2S3", "1M2", "10M", "1S", "2s3", "1X2", "9_b", "a-b", "1M-1"):  # con cifra delante, si lleva alguna letra (P-IMP-46)
            self.assertIsNone(e.motivo_nombre(n), n)
        # la tabla de variables: mensaje, parpadeo y la fila vuelve a quedar en blanco
        pv = w.variables
        n = len(e.ed.undo_stack)
        pv.nueva()
        fila = pv.tabla.rowCount() - 1
        pv.tabla.item(fila, 0).setText("AND")
        self.assertEqual(pv.msg.text(), '"AND" no puede ser nombre de variable: es una palabra de las fórmulas')
        self.assertTrue(pv.parpadeo.t.isActive())
        self.assertEqual((len(e.ed.undo_stack), [v["name"] for v in e.ed.model["variables"]].count("AND")), (n, 0))
        self.assertEqual(pv.sin_nombre(), 1, "la fila sigue en blanco")
        pv.parpadeo.parar()
        pv.tabla.item(fila, 0).setText("X7")
        self.assertIn("X7", pv.msg.text())
        pv.parpadeo.parar()
        pv.tabla.item(fila, 0).setText("Sensor")  # uno válido sí se crea
        self.assertEqual((pv.msg.text(), "Sensor" in [v["name"] for v in e.ed.model["variables"]]), ("", True))
        # renombrar
        v = next(x for x in e.ed.model["variables"] if x["name"] == "Sensor")
        self.assertEqual(e.cambiar_variable(v["id"], nombre="OR"), '"OR" no puede ser nombre de variable: es una palabra de las fórmulas')
        self.assertEqual(next(x for x in e.ed.model["variables"] if x["id"] == v["id"])["name"], "Sensor")
        self.assertIsNone(e.cambiar_variable(v["id"], nombre="Sensor"), "el mismo nombre no se vuelve a comprobar")
        self.assertIn("no puede ser nombre", e.nueva_variable("Mi variable!") or "")
        # «Crear las que faltan» en una receptividad
        e.seleccionar([ts["t1"]])
        res = e.poner_condicion(ts["t1"], "`AND` AND marcha", crear=True)
        self.assertEqual(res.code, "D-FORMATO")
        self.assertEqual(e.mensaje, res.message)
        self.assertNotIn("AND", [x["name"] for x in e.ed.model["variables"]])
        # el panel de la acción ya no crea variables (P-IMP-46); la tabla de variables es el único sitio
        # el núcleo admite lo que ya estaba (ficheros antiguos): el nombre reservado entre comillas invertidas
        vid = e.ed.add_variable("AND", "input", {"kind": "bool"})
        e.poner_condicion(ts["t2"], "`AND`")
        self.assertEqual(e.texto_condicion(ts["t2"]), "`AND`")
        self.assertIsNone(e.cambiar_variable(vid, role="internal"))

    def test_SEDI99_y_y_o_con_muchos_operandos(self):
        """REQ-EDT-02: un «y» o un «o» de 10, 11 o 26 operandos (las claves de los huecos no chocan con la clase del nodo):
        texto -> árbol -> texto estable y con el mismo significado, se dibuja sin excepción y el «+» llega al máximo."""
        from grafcet.expressions import parse
        from escritorio import bloques
        from escritorio.bloques import arbol_a_texto, hijos, texto_a_arbol
        nombres = [f"v{i}" for i in range(26)]
        vars_ = {n: ("input", "bool") for n in nombres}
        sig = lambda t: parse(a_nucleo(t, [], vars_.keys()), lambda clase, nombre: nombre)  # noqa: E731
        for n_ in (10, 11, 26):
            for op in (" OR ", " AND "):
                t = op.join(nombres[:n_])
                arbol = texto_a_arbol(t, vars_, [])
                self.assertEqual(len(hijos(arbol)), n_, t)
                self.assertNotIn("k", hijos(arbol), "la clase del nodo no es un hueco")
                self.assertEqual(arbol_a_texto(arbol), t)
                self.assertEqual(arbol_a_texto(texto_a_arbol(arbol_a_texto(arbol), vars_, [])), t)
                self.assertEqual(sig(arbol_a_texto(arbol)), sig(t), "mismo significado")
        # dibujo sin excepción, en el área, con «+» hasta el máximo
        from escritorio.bloques import Programador
        p = Programador(lambda: (vars_, []))
        p.resize(900, 500)
        p.show()
        p.poner(" OR ".join(nombres[:10]))
        QApplication.processEvents()
        area = p.lienzo
        for _ in range(40):
            area.anadir_hueco((0,))
            QApplication.processEvents()
        self.assertEqual(len(hijos(area.arbol)), bloques.MAX_ENTRADAS)
        self.assertEqual(area.arbol["k"], "o")
        self.assertEqual(arbol_a_texto(texto_a_arbol(p.texto(), vars_, [])), p.texto())
        self.assertTrue(area.grab().width() > 0)
        self.assertFalse([x for x in area._piezas if x[3] == "mas"], "sin «+» en el máximo")
        # soltar, quitar y mover con claves altas
        area.soltar(("K",), bloques.var("v1"))
        self.assertEqual(area.arbol["K"]["n"], "v1")
        area.quitar((0, "K"))  # al sacar el bloque, su hueco desaparece: los de detrás ocupan su sitio
        self.assertEqual(len(hijos(area.arbol)), bloques.MAX_ENTRADAS - 1)
        area.anadir_hueco((0,))
        self.assertTrue(area.quitar_hueco((0,), hijos(area.arbol)[-1]))
        self.assertEqual(len(hijos(area.arbol)), bloques.MAX_ENTRADAS - 1)
        p.close()

    def test_SEDI100_limitada_con_condicion_a_medias_pasa_a_borrador(self):
        """REQ-ACT-01, REQ-EDT-02: la condición a medias (con huecos) de una limitada de un fichero antiguo la deja como
        borrador que conserva su límite, como en una condicionada; con una condición completa vuelve al modelo."""
        e, ids, ts = self._etapa_con_dos_acciones()
        s1 = ids["1"]
        self.assertIsNone(e.poner_accion(s1, {"tipo": "limitada", "variable": "Q02", "limite": "3s"}))
        lim = e.ed.get(s1)["actionRefs"][-1]
        self.assertIsNone(e.poner_texto_accion(lim, "condicion", "marcha AND ?"))
        b = next(x for x in e.ed.draft_actions() if x["tipo"] == "limitada")
        self.assertEqual((b["limite"], b["condicion"], b["etapa"]), ("3s", "marcha AND ?", s1))
        self.assertIsNone(e.poner_texto_accion(b["id"], "condicion", "marcha AND paro"))
        self.assertEqual(e.ed.draft_actions(), [])
        nueva = e.ed.get(s1)["actionRefs"][-1]
        self.assertEqual((e.ed.get(nueva)["limitUs"], e.datos_accion(nueva)["condicion"]), ("3000000", "marcha AND paro"))

    def test_SEDI101_renombrar_con_la_seleccion_cambiada_no_hace_nada(self):
        """REQ-EDT-02: un editingFinished que llega tarde (la selección cambió, o el elemento ya no existe, por ejemplo tras
        deshacer) no renombra nada ni falla."""
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ids["1"]])
        p = w.props
        p.s_etiqueta.setText("Otra")
        e.sel = [ids["0"]]  # la selección cambió antes de que llegara el aviso (el panel aún no se ha refrescado)
        p._renombrar(p.s_etiqueta)
        self.assertEqual((e.nombres[ids["1"]], e.nombres[ids["0"]]), ("1", "0"))
        e.seleccionar([ids["1"]])
        e.confirmar_borrado = lambda plan: True
        e.borrar()
        p.ident = ids["1"]  # obsoleto: el elemento ya no existe
        p.s_etiqueta.setText("Z")
        p._renombrar(p.s_etiqueta)  # sin KeyError

    # -- P-IMP-44: paneles fijos, acciones sueltas independientes, «y»/«o» sin «×», diálogo de acciones, tabla de variables
    def test_SEDI102_borrar_una_etapa_borra_sus_acciones_y_se_restaura(self):
        """REQ-ACT-01, REQ-EDT-05: borrar una etapa borra también sus acciones (del modelo y los borradores unidos); la
        consulta de borrado las cuenta; una operación de deshacer lo restaura todo."""
        e, ids, ts = self._etapa_con_dos_acciones()
        s1 = ids["1"]
        e.anadir_accion(s1)  # una sin completar, unida
        antes = [(a["id"], e.datos_accion(a["id"])) for a in e.acciones(s1)]
        self.assertEqual(len(antes), 3)
        preguntas = []
        e.confirmar_borrado = lambda plan: preguntas.append(plan) or True
        e.seleccionar([s1])
        n = len(e.ed.undo_stack)
        self.assertTrue(e.borrar())
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una operación")
        self.assertEqual(len([x for x in preguntas[0]["elements"] if x != s1]), 2, "la consulta cuenta las del modelo")
        self.assertEqual((e.ed.model["actions"], e.ed.draft_actions()), ([], []))
        e.deshacer()
        self.assertEqual([(a["id"], e.datos_accion(a["id"])) for a in e.acciones(s1)], antes)

    def test_SEDI103_botones_nueva_entrada_salida_memoria(self):
        """REQ-EDT-07, REQ-EDT-09: la tabla de variables tiene «+ Entrada», «+ Salida» y «+ Memoria» (tooltips Nueva entrada,
        salida y memoria) que añaden la fila sin nombre con el papel puesto y tipo Booleana, y «Eliminar»; los cuatro caben
        en el ancho fijo del panel (en una fila si caben, si no en dos)."""
        from escritorio.variables import PAPELES as PAPELES_V
        w = self.w
        e, ids, ts = self.secuencial()
        pv = w.variables
        self.assertEqual({p: (b.text(), b.toolTip()) for p, b in pv.b_nuevas.items()},
                         {"input": ("+ Entrada", "Nueva entrada"), "output": ("+ Salida", "Nueva salida"),
                          "internal": ("+ Memoria", "Nueva memoria")})
        self.assertEqual(pv.b_quitar.text(), "Eliminar")
        for papel, nombre in (("input", "Ent"), ("output", "Sal"), ("internal", "Mem")):
            pv.b_nuevas[papel].click()
            fila = pv.tabla.rowCount() - 1
            self.assertEqual((pv.tabla.item(fila, 0).text(), pv.tabla.item(fila, 1).text(), pv.tabla.item(fila, 2).text()),
                             ("", dict(PAPELES_V)[papel], "Booleana"))
            pv.tabla.item(fila, 0).setText(nombre)
        self.assertEqual([(v["name"], v["role"], v["type"]["kind"]) for v in e.ed.model["variables"]][-3:],
                         [("Ent", "input", "bool"), ("Sal", "output", "bool"), ("Mem", "internal", "bool")])
        w.show()
        self.app.processEvents()
        botones = [*pv.b_nuevas.values(), pv.b_quitar]
        self.assertTrue(all(b.geometry().right() <= pv.width() and b.isVisible() for b in botones))
        self.assertLessEqual(len({b.geometry().top() for b in botones}), 2, "una fila, o dos")

    def _dialogo_con_memorias(self):
        e, ids, ts = self._etapa_con_dos_acciones()
        e.nueva_variable("CT", "internal", {"kind": "int"})
        e.nueva_variable("M1", "internal", {"kind": "bool"})
        e.nueva_variable("I02", "input", {"kind": "bool"})
        return e, ids, ts

    def _variables_en_la_tabla(self, *nombres, papel="input"):
        """Un grafcet nuevo con las variables dadas (creadas por el núcleo) y la tabla de variables al día."""
        w = self.w
        w.nuevo()
        for n in nombres:
            self.assertIsNone(w.edicion.nueva_variable(n, papel))
        w.show()
        self.app.processEvents()
        return w.edicion, w.variables

    def test_SEDI260_supr_quita_la_variable_seleccionada_como_el_boton(self):
        """REQ-EDT-07: Supr con una fila seleccionada en la tabla de variables la quita directamente, por el mismo camino que
        «Quitar» (una operación de deshacer); sin diálogos nuevos."""
        e, pv = self._variables_en_la_tabla("a", "b", "c")
        with mock.patch("escritorio.ventana.QMessageBox.question") as pregunta, mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            pv.tabla.selectRow(1)
            pv.tabla.setFocus()
            n = len(e.ed.undo_stack)
            QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
            self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["a", "c"])
            self.assertEqual((len(e.ed.undo_stack), pv.tabla.rowCount(), pv.msg.text()), (n + 1, 2, ""))
            pregunta.assert_not_called()
            aviso.assert_not_called()
            # sin ninguna fila seleccionada no quita nada
            pv.tabla.clearSelection()
            QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
            self.assertEqual(len(e.ed.model["variables"]), 2)
            # el botón «Quitar» y Supr dan lo mismo
            pv.tabla.selectRow(0)
            pv.quitar()
            self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["c"])
        e.deshacer()
        e.deshacer()
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["a", "b", "c"])

    def test_SEDI261_supr_de_una_variable_en_uso_se_rechaza_igual_que_quitar(self):
        """REQ-EDT-07, REQ-EDT-09: si el núcleo no deja quitar la variable (se usa), Supr enseña el mismo motivo que el
        botón «Quitar», la fila parpadea y no se borra nada."""
        w = self.w
        e, ids, ts = self.secuencial()
        pv = w.variables
        nombres = [v["name"] for v in e.ed.model["variables"]]
        self.assertEqual(nombres[:2], ["marcha", "paro"])
        pv.tabla.selectRow(0)
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
        con_supr = pv.msg.text()
        self.assertIn("se usa", con_supr)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], nombres)
        self.assertEqual(len(pv.parpadeo.ids), 1)
        pv.msg.setText("")
        pv.tabla.selectRow(0)
        pv.quitar()
        self.assertEqual(pv.msg.text(), con_supr, "el mismo aviso que con el botón")

    def test_SEDI262_supr_con_la_celda_en_edicion_es_del_editor_y_no_borra_el_dibujo(self):
        """REQ-EDT-07: con el editor de una celda abierto Supr borra texto, no la fila; con la tabla enfocada Supr es de la
        tabla y no el atajo «Borrar la selección» del dibujo (que conserva su selección)."""
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtWidgets import QAbstractItemView, QLineEdit
        w = self.w
        e, pv = self._variables_en_la_tabla("abc", "otra")
        pv.tabla.selectRow(0)
        pv.tabla.editItem(pv.tabla.item(0, 0))
        self.assertEqual(pv.tabla.state(), QAbstractItemView.State.EditingState)
        editor = pv.tabla.findChild(QLineEdit)
        QTest.keyClick(editor, Qt.Key.Key_Home)
        QTest.keyClick(editor, Qt.Key.Key_Delete)
        self.assertEqual(editor.text(), "bc", "Supr borra texto en el editor")
        self.assertEqual(len(e.ed.model["variables"]), 2)
        for destino in (editor, pv.tabla):  # ni siquiera dirigido a la tabla mientras se edita
            QTest.keyClick(destino, Qt.Key.Key_Delete)
            self.assertEqual(len(e.ed.model["variables"]), 2)
        sobre = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(pv.tabla, sobre)
        self.assertFalse(sobre.isAccepted(), "editando, el atajo no se reserva")
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertNotEqual(pv.tabla.state(), QAbstractItemView.State.EditingState)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["abc", "otra"])
        # sin edición: la tabla se reserva Supr frente al atajo de la ventana y el dibujo conserva su selección
        e.colocar("etapa", QPointF(100, 60))
        self.assertTrue(e.sel)
        w.activateWindow()
        pv.tabla.selectRow(1)
        pv.tabla.setFocus()
        sobre = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(pv.tabla, sobre)
        self.assertTrue(sobre.isAccepted(), "Supr con el foco en la tabla no es «Borrar la selección»")
        pasos = len(e.ed.model["steps"])
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["abc"])
        self.assertEqual(len(e.ed.model["steps"]), pasos, "la etapa seleccionada en el dibujo sigue ahí")

    def test_SEDI263_supr_con_varias_filas_y_filas_sin_nombre(self):
        """REQ-EDT-07: con varias filas seleccionadas Supr las quita todas (una operación de deshacer por variable); si el
        núcleo rechaza alguna, las demás se quitan y el aviso es el del rechazo; una fila sin nombre sale sin tocar el modelo."""
        from PySide6.QtCore import QItemSelectionModel
        from PySide6.QtWidgets import QAbstractItemView
        w = self.w
        e, ids, ts = self.secuencial()
        pv = w.variables
        for n in ("libre1", "libre2"):
            self.assertIsNone(e.nueva_variable(n, "input"))
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["marcha", "paro", "libre1", "libre2"])
        pv.tabla.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # la tabla es de una fila; el gesto admite varias
        pv.tabla.setFocus()
        pv.tabla.selectRow(2)
        pv.tabla.selectionModel().select(pv.tabla.model().index(3, 0),
                                         QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        n = len(e.ed.undo_stack)
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["marcha", "paro"])
        self.assertEqual(len(e.ed.undo_stack), n + 2)
        # una en uso entre las seleccionadas: las libres salen, la usada se queda con su aviso
        self.assertIsNone(e.nueva_variable("libre3", "input"))
        pv.tabla.selectAll()
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["marcha", "paro"])
        self.assertIn("se usa", pv.msg.text())
        self.assertEqual(len(pv.parpadeo.ids), 2)
        # una fila sin nombre: solo se quita de la interfaz
        n = len(e.ed.undo_stack)
        pv.nueva()
        self.assertEqual(pv.sin_nombre(), 1)
        pv.tabla.setFocus()
        pv.tabla.selectRow(pv.tabla.rowCount() - 1)
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
        self.assertEqual((pv.sin_nombre(), pv.tabla.rowCount(), len(e.ed.undo_stack)), (0, 2, n))
        self.assertEqual(pv.msg.text(), "")

    def test_SEDI264_supr_solo_actua_al_editar(self):
        """REQ-EDT-07: fuera del modo edición (en Play) la tabla de variables no responde a Supr; al volver a Pausa, sí."""
        w = self.w
        e, ids, ts = self.secuencial()
        pv = w.variables
        self.assertIsNone(e.nueva_variable("libre", "input"))
        self.assertTrue(pv.isEnabled())
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertFalse(pv.isEnabled(), "en Play la tabla de variables no es editable")
        nombres = [v["name"] for v in e.ed.model["variables"]]
        pv.tabla.selectRow(len(nombres) - 1)
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
        pv.quitar_seleccion()
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], nombres)
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertTrue(pv.isEnabled())
        pv.tabla.selectRow(len(nombres) - 1)
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], nombres[:-1])

    def test_SEDI268_supr_del_teclado_numerico_tambien_quita_la_variable(self):
        """REQ-EDT-07: el Supr del teclado numérico (con el modificador de teclado numérico) actúa igual que el Supr normal en la
        tabla de variables: quita la fila seleccionada, la tabla se reserva el atajo frente al «Borrar la selección» de la
        ventana y el dibujo conserva su selección; con Mayús o Ctrl no es de la tabla."""
        from PySide6.QtGui import QKeyEvent
        w = self.w
        e, pv = self._variables_en_la_tabla("a", "b", "c")
        e.colocar("etapa", QPointF(100, 60))
        self.assertTrue(e.sel)
        seleccion, pasos = list(e.sel), len(e.ed.model["steps"])
        w.activateWindow()
        pv.tabla.selectRow(1)
        pv.tabla.setFocus()
        for mod, reservado in ((Qt.KeyboardModifier.NoModifier, True), (Qt.KeyboardModifier.KeypadModifier, True),
                               (Qt.KeyboardModifier.ShiftModifier, False), (Qt.KeyboardModifier.ControlModifier, False)):
            sobre = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_Delete, mod)
            self.app.sendEvent(pv.tabla, sobre)
            self.assertEqual(sobre.isAccepted(), reservado, f"el atajo de la tabla con {mod}")
        n = len(e.ed.undo_stack)
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete, Qt.KeyboardModifier.KeypadModifier)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["a", "c"])
        self.assertEqual((len(e.ed.undo_stack), len(e.ed.model["steps"]), e.sel), (n + 1, pasos, seleccion),
                         "una sola operación y el dibujo sigue como estaba")
        # con el editor de una celda abierto sigue siendo del editor, también con el modificador del teclado numérico
        pv.tabla.selectRow(0)
        pv.tabla.editItem(pv.tabla.item(0, 0))
        QTest.keyClick(pv.tabla, Qt.Key.Key_Delete, Qt.KeyboardModifier.KeypadModifier)
        self.assertEqual([v["name"] for v in e.ed.model["variables"]], ["a", "c"])

    def test_SEDI265_pestanas_entre_grafcet_planos_y_es_externas(self):
        """REQ-SIM-03, REQ-EDT-11: las tres pestañas identifican la página y se sincronizan por cualquier vía."""
        w=self.w;w.edicion.ed.add_step("g","0",True);w.edicion.cambia();w.show();self.app.processEvents();tabs=w.pestanas_vistas
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],['GRAFCET','PLANOS','E/S externas'])
        for pesta,indice in ((2,1),(1,2),(0,0),(2,1)):
            if pesta==2:QTest.mouseClick(w.luz_es,Qt.MouseButton.LeftButton)  # a E/S se entra por la luz de conexión: su pestaña no se ve
            else:QTest.mouseClick(tabs,Qt.MouseButton.LeftButton,pos=tabs.tabRect(pesta).center())
            self.assertEqual(w.paginas_es.currentIndex(),indice);self.assertEqual(tabs.currentIndex(),pesta)
        w.panel_es.b_volver.click();self.assertEqual((w.paginas_es.currentIndex(),tabs.currentIndex()),(0,0))
        w.mostrar_es();self.assertEqual(tabs.currentIndex(),2)
        w.cambiar_modo('simular');self.assertEqual((w.paginas_es.currentIndex(),tabs.currentIndex()),(0,0))
        w.cambiar_modo('editar');self.assertEqual(tabs.currentIndex(),0)
        self.assertFalse(w.tb_conexion.isVisible(),'los antiguos conmutadores no se duplican en la barra')

    def test_SEDI270_las_pestanas_no_se_mueven_al_cambiar_de_vista(self):
        """REQ-SIM-03: las pestañas tienen textos y geometría estables al cambiar entre los tres espacios."""
        w=self.w;w.resize(1366,768);w.show();self.app.processEvents();tabs=w.pestanas_vistas
        medidas=[tabs.tabRect(i) for i in range(2)];pos=tabs.mapTo(w,QPoint(0,0))
        for i in (2,1,0,1,2,0):
            QTest.mouseClick(w.luz_es,Qt.MouseButton.LeftButton) if i==2 else QTest.mouseClick(tabs,Qt.MouseButton.LeftButton,pos=tabs.tabRect(i).center())
            self.app.processEvents()
            self.assertEqual([tabs.tabRect(j) for j in range(2)],medidas);self.assertEqual(tabs.mapTo(w,QPoint(0,0)),pos)
            self.assertEqual(tabs.currentIndex(),i)

    def test_SEDI266_el_estado_de_conexion_hace_salto_de_linea_y_no_se_corta(self):
        """REQ-SIM-03: el estado de la conexión del panel de E/S ocupa su propia fila bajo el título, hace salto de línea y
        crece en alto: un mensaje de error largo (WinError 10053) se ve entero, a cualquier ancho, y va en el tooltip."""
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QFontMetrics
        from PySide6.QtWidgets import QFrame
        from escritorio.entradas_salidas import PanelES
        largo = ("El simulador de procesos cerró o anuló la conexión (WinError 10053). Salidas no garantizadas. Pulsa Conectar para "
                 "reanudar. Detalle: [WinError 10053] Se ha anulado una conexión establecida por el software en su equipo host")
        p = PanelES()
        try:
            p.cargar(*self._doc_y_config_es())
            p.resize(1000, 600)
            p.show()
            self.app.processEvents()
            banda = p.findChild(QFrame, "cabeceraES")
            corto = banda.height()
            p.mostrar_estado("error", largo)
            self.assertEqual(p.check.text(), "✕")
            self.assertTrue(p.estado.wordWrap())
            self.assertEqual((p.estado.text(), p.estado.toolTip(), p.check.toolTip()), (largo, largo, largo))
            for ancho in (1280, 1000, 760, 560):
                p.resize(ancho, 600)
                for _ in range(3):
                    self.app.processEvents()
                est = p.estado
                necesaria = QFontMetrics(est.font()).boundingRect(QRect(0, 0, est.width(), 0), Qt.TextFlag.TextWordWrap, largo).height()
                self.assertGreaterEqual(est.height(), necesaria, f"ancho {ancho}: el texto cabe entero en la etiqueta")
                self.assertGreaterEqual(est.heightForWidth(est.width()), necesaria)
                self.assertLessEqual(est.mapTo(banda, est.rect().bottomLeft()).y(), banda.height(), "y la etiqueta cabe en la cabecera")
                self.assertLessEqual(banda.geometry().bottom(), p.lienzo.mapTo(p, p.lienzo.rect().topLeft()).y(), "sin pisar el cuerpo")
            p.resize(1000, 600)
            for _ in range(3):
                self.app.processEvents()
            self.assertGreater(p.estado.height(), QFontMetrics(p.estado.font()).height() * 1.5, "son varias líneas")
            self.assertGreater(banda.height(), corto, "la cabecera crece con el mensaje")
            p.mostrar_estado("conectado", "Conectado · Ejecutando")
            for _ in range(3):
                self.app.processEvents()
            self.assertEqual((p.estado.text(), p.check.text(), banda.height()), ("Conectado", "✓", corto))
        finally:
            p.close()
            p.deleteLater()
            self.app.processEvents()

    @staticmethod
    def _doc_y_config_es():
        from conexion.configuracion import Configuracion, Senal
        from grafcet.builder import M
        doc = M().var("sensor").var("motor", "output").step("0", True).doc
        return doc, Configuracion(modelo=doc["id"], senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])

    def test_SEDI104_panel_de_acciones_lista_de_variables_sin_crear_desde_aqui(self):
        """REQ-ACT-01, REQ-EDT-07: la variable se elige en una lista ordenada por papel (Salidas, Memorias) con su tipo; nunca
        ofrece entradas; una continua o condicionada solo booleanas; una memorizada, de cualquier tipo. La lista ya no ofrece
        «Nueva variable…» (las variables se crean en la tabla de variables, P-IMP-46); sin ninguna que valga, lo dice."""
        e, ids, ts = self._dialogo_con_memorias()
        s1 = ids["1"]
        d = self.panel_accion(s1)
        datos = lambda: [d.variable.itemData(i) for i in range(d.variable.count())]  # noqa: E731
        self.assertEqual(d.ofrecidas(), ["Q00", "Q01", "Q02", "M1"], "continua: salidas y memorias booleanas, sin entradas")
        self.assertEqual(datos(), ["", None, "Q00", "Q01", "Q02", None, "M1"])
        textos = [d.variable.itemText(i) for i in range(d.variable.count())]
        self.assertEqual((textos[1], textos[5]), ("Salidas", "Memorias"))
        self.assertNotIn("Nueva variable…", textos)
        self.assertFalse(hasattr(d, "nueva_variable"), "ni método ni diálogo para crear variables desde la acción")
        self.assertIn("Booleana", textos[2])
        self.assertFalse(d.variable.model().item(1).isEnabled(), "los rótulos no se eligen")
        self.poner_tipo(d, "condicionada")
        self.assertEqual(d.ofrecidas(), ["Q00", "Q01", "Q02", "M1"])
        for tipo in ("activacion", "desactivacion", "evento"):
            self.poner_tipo(d, tipo)
            self.assertEqual(d.ofrecidas(), ["Q00", "Q01", "Q02", "CT", "M1"], tipo)
            self.assertNotIn("I02", d.ofrecidas())
        self.assertTrue(any("Entera" in d.variable.itemText(i) and d.variable.itemData(i) == "CT"
                            for i in range(d.variable.count())), "con su tipo")
        # una variable creada en la tabla aparece enseguida en la lista y se elige como cualquier otra
        d.poner_variable("CT")
        n = len(e.ed.undo_stack)
        self.assertIsNone(e.nueva_variable("TOT", "internal", {"kind": "int"}))
        self.assertIn("TOT", d.ofrecidas())
        d.poner_variable("TOT")
        self.assertEqual(d.variable.currentText(), "TOT")
        self.assertEqual(len(e.ed.undo_stack), n + 2, "crear la variable y elegirla: dos operaciones")
        d._desde_bloques("TOT + 1")
        self.assertEqual(len(e.ed.undo_stack), n + 3)
        # una continua no escribe una variable entera: al cambiar de tipo se vuelve a elegir
        a = e.acciones(s1)[-1]["id"]
        d = self.panel_accion(s1, a)
        self.assertEqual(d.variable.currentText(), "TOT")
        self.poner_tipo(d, "continua")
        self.assertEqual(d.variable.currentText(), "")
        self.assertNotIn("TOT", d.ofrecidas())

    def test_SEDI117_lista_de_variables_vacia_o_sin_la_variable_actual(self):
        """REQ-ACT-01, REQ-EDT-07: si no hay ninguna variable que la acción pueda escribir (o la elegida ya no existe), la
        lista muestra «(sin variables: créelas en la tabla de variables)» y no se rompe; al crear una, se ofrece."""
        from escritorio.acciones import SIN_VARIABLES
        e, ids, ts = self.secuencial()  # solo hay entradas (marcha, paro)
        d = self.panel_accion(ids["1"])
        self.assertEqual((d.ofrecidas(), d.variable.count(), d.variable.itemText(0)), ([], 1, SIN_VARIABLES))
        self.assertEqual(d.variable.currentText(), "")
        self.assertFalse(d.variable.model().item(0).isEnabled())
        d.variable.activated.emit(0)  # no hay nada que elegir: no pasa nada
        self.assertEqual(e.acciones(ids["1"])[-1]["variable"], "")
        e.nueva_variable("Q00", "output", {"kind": "bool"})
        self.assertEqual(d.ofrecidas(), ["Q00"])
        self.assertEqual(d.variable.itemText(0), "Elija la variable…")
        self.poner_tipo(d, "activacion")  # y otro tipo conserva la lista sin romperse
        self.assertEqual(d.ofrecidas(), ["Q00"])

    def test_SEDI105_programador_de_valor_de_una_accion_memorizada(self):
        """REQ-ACT-01, REQ-EDT-02: el valor de una memorizada se programa en el panel de la acción: una booleana elige entre las fichas
        «1» y «0»; una numérica arma el valor con un número, variables numéricas (cualquier papel) y los operadores +, −, ×,
        ÷ anidados; el texto (de solo lectura, con «Escribir a mano») y los
        bloques van de la mano en los dos sentidos; un valor que no se analiza se rechaza con su motivo."""
        from escritorio import bloques
        from escritorio.bloques import arbol_a_texto, texto_a_arbol_valor
        w = self.w
        e, ids, ts = self._dialogo_con_memorias()
        s1 = ids["1"]
        d = self.panel_accion(s1)
        self.assertTrue(d.caja_valor.isHidden(), "una continua no lleva valor")
        self.poner_tipo(d, "activacion")
        # booleana: dos fichas
        d.poner_variable("M1")
        self.assertFalse(d.caja_valor.isHidden() or d.caja_fichas.isHidden())
        self.assertTrue(d.caja_numerica.isHidden())
        d.fichas["1"].click()
        self.assertEqual((d.valor.text(), d.fichas["1"].isChecked(), d.fichas["0"].isChecked()), ("1", True, False))
        d.fichas["0"].click()
        self.assertEqual((d.valor.text(), d.fichas["0"].isChecked()), ("0", True))
        # numérica: el valor se arma con bloques
        d.poner_variable("CT")
        self.assertTrue(d.caja_fichas.isHidden() and not d.caja_numerica.isHidden())
        d._poner_valor("CT + 1")
        self.assertEqual((d.valor.text(), d.prog.texto()), ("CT + 1", "CT + 1"))
        arbol = d.prog.lienzo.arbol
        self.assertEqual((arbol["k"], arbol["op"], arbol["a"], arbol["b"]), ("ar", "+", {"k": "vnum", "n": "CT"}, {"k": "num", "v": "1"}))
        self.assertTrue(d.valor.isReadOnly(), "el valor se arma con bloques: no se edita a mano")
        self.assertFalse(hasattr(d, "manual"))
        # la paleta corta: Número, Variables, Operadores
        self.assertEqual([c for c, _ in d.prog.lista_categorias], ["numero", "vnum", "aritm"])
        d.prog.elegir_categoria("vnum")
        self.assertEqual([n["n"] for n in d.prog.paleta._raices], ["CT"], "una ficha por variable numérica, de cualquier papel")
        d.prog.elegir_categoria("aritm")
        self.assertEqual([n["op"] if n["k"] == "ar" else n["k"] for n in d.prog.paleta._raices],
                         ["+", "-", "*", "/", "par"], "los cuatro operadores y el paréntesis")
        # con bloques: CT * 2 - 1, anidado (un operador sobre otro lo envuelve); lo a medias no se guarda
        d._desde_bloques("")
        lienzo = d.prog.lienzo
        d.prog.colocar(bloques.nuevo("ar", op="*"))
        lienzo.soltar(("a",), bloques.nuevo("vnum", n="CT"))
        lienzo.soltar(("b",), bloques.nuevo("num", v="2"))
        self.assertEqual(d.valor.text(), "CT * 2")
        lienzo.soltar((), bloques.nuevo("ar", op="-"))
        self.assertEqual(d.valor.text(), "CT * 2 - ?")
        lienzo.soltar(("b",), bloques.nuevo("num", v="1"))
        self.assertEqual(d.valor.text(), "CT * 2 - 1")
        self.assertTrue(lienzo.editar_campo(("b",), "v", "7"))
        self.assertEqual(d.valor.text(), "CT * 2 - 7")
        self.assertFalse(lienzo.editar_campo(("b",), "v", "abc"), "un número es un número")
        self.assertEqual(d.valor.text(), "CT * 2 - 7")
        # los cuatro operadores, anidados, y el texto de vuelta
        vars_ = {"CT": ("internal", "int"), "I02": ("input", "bool")}
        for t in ("CT + 1", "5", "CT * 2 - 1", "(CT + 1) * 2", "CT / 2 - 1", "CT - (1 - 2)", "1 + 2 * 3", "CT * (2 + 3) / 4",
                  "-1", "CT + ?", "2.5 * CT"):
            self.assertEqual(arbol_a_texto(texto_a_arbol_valor(t, vars_, [])), t, t)
        m = texto_a_arbol_valor("(CT + 1) * 2 - 6 / 3", vars_, [])
        self.assertEqual((m["k"], m["op"], m["a"]["op"], m["b"]["op"]), ("ar", "-", "*", "/"))
        self.assertEqual(arbol_a_texto({"k": "ar", "op": "-", "a": bloques.nuevo("num", v="1"),
                                        "b": bloques.nuevo("ar", op="+", a=bloques.nuevo("num", v="2"), b=bloques.nuevo("num", v="3"))}),
                         "1 - (2 + 3)")
        self.assertEqual(texto_a_arbol_valor("I02 + 1", vars_, [])["a"]["k"], "texto", "una booleana no es un operando numérico")
        # de texto a bloques (el texto guardado)
        d.prog.poner("(CT + 1) * 2")
        self.assertEqual((lienzo.arbol["op"], lienzo.arbol["a"]["k"], lienzo.arbol["a"]["a"]["op"]), ("*", "par", "+"),
                         "el paréntesis escrito es un bloque «( )»")
        # lo escrito se guarda al terminar: el texto de siempre, que el núcleo analiza como siempre
        d._desde_bloques("CT * 2 - 1")
        (a,) = e.acciones(s1)[-1:]
        self.assertEqual((a["variable"], a["valor"]), ("CT", "CT * 2 - 1"))
        self.assertTrue(e.ed.validate().can_simulate)
        # un valor que no se analiza se rechaza con su motivo, en naranja, y no se guarda
        d = self.panel_accion(s1)
        self.poner_tipo(d, "activacion")
        d.poner_variable("CT")
        n = len(e.ed.undo_stack)
        d._desde_bloques("CT +")
        self.assertTrue(d.msg.text())
        self.assertEqual(len(e.ed.undo_stack), n, "no se guardó nada")
        # un número editado desde el área de la paleta o con el campo, en el propio bloque
        d.valor.setText("")
        d.prog.elegir_categoria("numero")
        d.prog.colocar(d.prog.paleta.bloques()[0])
        self.assertEqual(d.valor.text(), "1")

    def test_SEDI106_frase_explicativa_y_condicion_con_bloques_al_lado(self):
        """REQ-ACT-01, REQ-EDT-02: arriba del panel de la acción, una frase la explica según su tipo; la condición (o el
        evento) se programa con bloques a su lado, con el dibujo de la norma debajo; una continua o una memorizada con
        valor no los llevan."""
        w = self.w
        e, ids, ts = self._dialogo_con_memorias()
        s1 = ids["1"]
        p = w.props
        d = self.panel_accion(s1)
        d.poner_variable("Q00")
        self.assertEqual(d.frase.text(), "Mientras la etapa 1 esté activa, Q00 vale 1.")
        self.assertTrue(p.pagina_bloques.isHidden(), "una continua no se programa")
        self.poner_tipo(d, "condicionada")
        self.assertEqual(d.frase.text(), "Mientras la etapa 1 esté activa (y se cumpla la condición), Q00 vale 1.")
        self.assertFalse(p.pagina_bloques.isHidden(), "ofrece programar la condición con bloques")
        self.assertEqual(p.objetivo_bloques()[2], "condicion")
        self.poner_tipo(d, "activacion")
        d.poner_variable("CT")
        d._desde_bloques("CT + 1")
        self.assertEqual(d.frase.text(), "Al activarse la etapa 1: CT := CT + 1.")
        self.assertTrue(p.pagina_bloques.isHidden() and not d.caja_valor.isHidden())
        self.poner_tipo(d, "desactivacion")
        self.assertEqual(d.frase.text(), "Al desactivarse la etapa 1: CT := CT + 1.")
        # con una acción por evento y otra condicionada que ya tienen su evento y su condición
        self.assertIsNone(e.poner_accion(s1, {"tipo": "evento", "variable": "CT", "valor": "CT + 1", "evento": "↑I02"}))
        self.assertIsNone(e.poner_accion(s1, {"tipo": "condicionada", "variable": "Q02", "condicion": "marcha AND paro"}))
        ev, co = e.acciones(s1)[-2]["id"], e.acciones(s1)[-1]["id"]
        d = self.panel_accion(s1, ev)
        self.assertEqual(d.frase.text(), "Con cada ↑I02 mientras la etapa 1 está activa: CT := CT + 1.")
        self.assertEqual((p.objetivo_bloques(), p.prog.texto()), (("accion", ev, "evento"), "↑I02"))
        self.assertFalse(d.caja_valor.isHidden() or p.pagina_bloques.isHidden(), "valor y evento, a la vez")
        d = self.panel_accion(s1, co)
        self.assertEqual((p.objetivo_bloques(), p.prog.texto()), (("accion", co, "condicion"), "marcha AND paro"))
        self.assertIn("marcha · paro", p.t_dibujo.text().replace("&nbsp;", " "), "con el dibujo de la norma")

    def test_SEDI107_comentarios_en_la_presentacion_guardar_deshacer_y_borrar(self):
        """REQ-DAT-01, REQ-EDT-14: el comentario de una etapa o transición se guarda en `presentation.notes`
        ({id, elementRef, text, kind: comment}); no cambia la revisión semántica, ni los diagnósticos, ni la simulación;
        se guarda, se abre y se deshace; vacío lo quita; se va con su elemento y vuelve con deshacer; una acción no lleva
        comentario."""
        from escritorio.edicion import Edicion
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        s1, t1 = ids["1"], ts["t1"]
        rev, diag = e.ed.revision, e.diagnosticos()
        modelo = copy.deepcopy(e.ed.model)
        n = len(e.ed.undo_stack)
        e.poner_comentario(s1, "  Dosificar producto A  ")
        e.poner_comentario(t1, "Producto A pesado")
        self.assertEqual(len(e.ed.undo_stack), n + 2, "una operación por cambio")
        self.assertEqual(e.comentario(s1), "Dosificar producto A")
        (nota,) = [x for x in e.ed.presentation["notes"] if x["elementRef"] == s1]
        self.assertEqual((nota["text"], nota["kind"], bool(nota["id"])), ("Dosificar producto A", "comment", True))
        self.assertEqual((e.ed.revision, e.ed.model, e.diagnosticos()), (rev, modelo, diag), "la semántica no cambia")
        e.poner_comentario(s1, "Dosificar producto A")  # sin cambio: nada que deshacer
        self.assertEqual(len(e.ed.undo_stack), n + 2)
        self.assertEqual((e.M["steps"][1]["comment"], [t for t in e.M["transitions"] if t["id"] == t1][0]["comment"]),
                         ("Dosificar producto A", "Producto A pesado"))
        self.assertNotIn("comment", e.M["steps"][0])
        # la simulación del grafcet que se edita lo ve igual y no cambia
        w.cambiar_modo("simular")
        self.assertEqual(w.v.model["steps"][1]["comment"], "Dosificar producto A")
        self.assertIsNotNone(w.v.s)
        w.cambiar_modo("editar")
        # una acción no lleva comentario
        with self.assertRaises(DiagnosticError):
            e.ed.set_comment(e.acciones(s1)[0]["id"], "no")
        # guardar y abrir
        destino = Path(self.tmp.name) / "con-comentarios"
        e.guardar(destino)
        ab = open_model(destino)
        self.assertEqual(ab.presentations[0]["notes"], e.ed.presentation["notes"])
        e2 = Edicion.desde(ab.doc, {}, "abierto", destino, ab.presentations[0])
        self.assertEqual((e2.comentario(s1), e2.comentario(t1)), ("Dosificar producto A", "Producto A pesado"))
        self.assertEqual(e2.ed.revision, rev)
        # deshacer y rehacer
        e.deshacer()
        self.assertEqual((e.comentario(t1), e.comentario(s1)), ("", "Dosificar producto A"))
        e.rehacer()
        self.assertEqual(e.comentario(t1), "Producto A pesado")
        # vacío lo quita
        e.poner_comentario(t1, "   ")
        self.assertEqual(e.comentario(t1), "")
        self.assertEqual([x["elementRef"] for x in e.ed.presentation["notes"]], [s1])
        e.deshacer()
        # borrar la etapa se lleva su comentario (y vuelve con deshacer)
        e.confirmar_borrado = lambda plan: True
        e.seleccionar([s1])
        e.borrar()
        self.assertEqual([x["elementRef"] for x in e.ed.presentation["notes"]], [t1], "solo se va el de la etapa")
        e.deshacer()
        self.assertEqual(e.comentario(s1), "Dosificar producto A")
        self.assertIn(s1, [x["elementRef"] for x in e.ed.presentation["notes"]])

    def test_SEDI108_campo_comentario_en_las_propiedades(self):
        """REQ-EDT-14: el panel de propiedades de la etapa y de la transición tiene el campo «Comentario»: confirmarlo es una
        operación de deshacer; vacío = sin comentario; un aviso tardío con la selección cambiada no hace nada."""
        w = self.w
        e, ids, ts = self.secuencial()
        p = w.props
        e.seleccionar([ids["1"]])
        self.assertEqual(p.s_comentario.text(), "")
        n = len(e.ed.undo_stack)
        p.s_comentario.setText("Esperar la mezcla")
        p.s_comentario.editingFinished.emit()
        self.assertEqual((e.comentario(ids["1"]), len(e.ed.undo_stack)), ("Esperar la mezcla", n + 1))
        p.s_comentario.editingFinished.emit()  # sin cambios: no hay otra operación
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.seleccionar([ts["t1"]])
        self.assertEqual(p.t_comentario.text(), "")
        p.t_comentario.setText("Producto pesado")
        p.t_comentario.editingFinished.emit()
        self.assertEqual(e.comentario(ts["t1"]), "Producto pesado")
        e.seleccionar([ids["1"]])
        self.assertEqual(p.s_comentario.text(), "Esperar la mezcla", "al volver, lo que tenía")
        p.s_comentario.setText("")
        p.s_comentario.editingFinished.emit()
        self.assertEqual(e.comentario(ids["1"]), "")
        e.sel = [ids["0"]]  # selección cambiada antes de que llegara el aviso
        p.s_comentario.setText("tarde")
        p._comentar(p.s_comentario)
        self.assertEqual(e.comentario(ids["0"]), "")
        e.deshacer()
        self.assertEqual(e.comentario(ids["1"]), "Esperar la mezcla")

    def test_SEDI109_dibujo_de_los_comentarios_sin_solapes(self):
        """REQ-EDT-14, REQ-SIM-03: el comentario se dibuja entre comillas tipográficas, en cursiva: el de una transición a la
        derecha de su receptividad; el de una etapa a la derecha de la etapa, o de su última acción si las tiene; ajustado
        a varias líneas si es largo; sin solapar con etapas, cajas de acciones, receptividades ni otros comentarios (como
        en la figura de ejemplo del responsable); se ve también al simular."""
        from PySide6.QtWidgets import QGraphicsTextItem
        w = self.w
        e, ids, ts = self._etapa_con_dos_acciones()
        e.nueva_variable("a")
        s1, s0 = ids["1"], ids["0"]
        e.condicion(ts["t1"], "a")
        largos = ("Esperar el final del transporte de dos briquetas, y además el vaciado de la báscula completa",
                  "Ciclo de Inicio · Báscula vacía · Mezcladora en la parte superior")
        e.poner_comentario(s1, largos[0])
        e.poner_comentario(s0, "Inicio")
        e.poner_comentario(ts["t1"], largos[1])
        e.poner_comentario(ts["t2"], "sin receptividad")

        def comentarios():
            sc = w.diagrama.scene()
            return {it.toPlainText(): it.sceneBoundingRect() for it in sc.items()
                    if isinstance(it, QGraphicsTextItem) and it.toPlainText().startswith("“")}
        c = comentarios()
        self.assertEqual(sorted(c), sorted(f"“{t}”" for t in (*largos, "Inicio", "sin receptividad")))
        for t, r in c.items():
            self.assertLessEqual(r.width(), 192, "ancho máximo")
        largo = c[f"“{largos[0]}”"]
        self.assertGreater(largo.height(), 2 * 12, "ajustado a varias líneas")
        # a la derecha de la última acción de la etapa 1
        ultima = max((x for x in w.diagrama.cajas_acciones if x["etapa"] == s1), key=lambda x: x["rect"][0])["rect"]
        self.assertGreaterEqual(largo.left(), ultima[0] + ultima[2])
        # a la derecha de la etapa sin acciones
        ini = c["“Inicio”"]
        self.assertGreater(ini.left(), e.M["steps"][0]["x"] + 40 + 22)
        # sin solapes con nada más
        from escritorio.diagrama import SX, H
        cajas = [QRectF(*x["rect"]) for x in w.diagrama.cajas_acciones]
        cajas += [QRectF(s["x"] + SX - H, s["y"] - H, 2 * H, 2 * H) for s in e.M["steps"]]
        otros = [it.sceneBoundingRect() for it in w.diagrama.scene().items()
                 if isinstance(it, QGraphicsTextItem) and not it.toPlainText().startswith("“")]
        todos = list(c.values())
        for i, r in enumerate(todos):
            for q in cajas + otros + todos[i + 1:]:
                self.assertFalse(r.intersects(q), (r, q))
        # un comentario de una acción no existe, y al simular se ven igual
        w.cambiar_modo("simular")
        self.assertEqual(sorted(comentarios()), sorted(c))
        w.cambiar_modo("editar")

    # -- ronda de opciones abajo: paleta de fichas, panel de opciones, variables al día y no solapar ----------------------
    def test_SEDI111_paleta_de_bloques_una_ficha_por_elemento(self):
        """REQ-EDT-02, REQ-EDT-07: en Entradas, Salidas, Etapas, Memorias (y Variables del valor) hay una ficha por cada
        elemento que existe, en orden (etapas por número, variables por nombre), sin desplegable y ya elegida, con
        desplazamiento si no caben; sin elementos, un único mensaje; se actualiza al crear, renombrar o quitar;
        los bloques ya puestos en el área conservan su ▾."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        for n in range(2, 11):
            e.poner_etapa(QPointF(600, 60 + 70 * n))
        for n, papel in (("zeta", "output"), ("alfa", "output"), ("I10", "input"), ("I2", "input")):
            e.nueva_variable(n, papel)
        w.resize(1360, 860)
        w.show()
        w._abrir_opciones()
        e.seleccionar([ts["t1"]])
        prog = w.props.prog
        prog.elegir_categoria("variables")
        def fichas(papel):
            return [b for b in prog.paleta.bloques() if b["k"] == "etapa" and papel == "etapa"
                    or b.get("papel") == papel]
        etiquetas = sorted((s["label"] for s in e.M["steps"]), key=int)
        self.assertEqual([b["n"] for b in fichas("etapa")], [f"X{n}" for n in etiquetas],
                         "por número: X2 antes que X10")
        self.assertFalse([x for x in prog.paleta._piezas if x[1] == "drop"], "sin desplegable")
        for n in range(11, 41):
            e.poner_etapa(QPointF(900, 20 * n))
        prog.elegir_categoria("variables")
        w.props.prog.paleta.invalidar()
        QApplication.processEvents()
        self.assertGreater(prog._sc_paleta.verticalScrollBar().maximum(), 0, "con muchas fichas, desplazamiento vertical")
        prog.elegir_categoria("variables")
        self.assertEqual([b["n"] for b in fichas("output")], ["alfa", "zeta"], "por nombre")
        prog.elegir_categoria("variables")
        self.assertEqual([b["n"] for b in fichas("input")], ["I2", "I10", "marcha", "paro"])
        # cada ficha se arrastra con su elemento ya elegido (el área conserva el desplegable)
        prog.lienzo.soltar((), fichas("input")[2])
        self.assertEqual(prog.texto(), "marcha")
        prog.lienzo.invalidar()
        prog.lienzo._calcular(300)
        self.assertTrue([x for x in prog.lienzo._piezas if x[1] == "drop"], "los bloques puestos conservan su ▾")
        # al día en el acto
        e.nueva_variable("Q9", "output")
        prog.elegir_categoria("variables")
        self.assertEqual([b["n"] for b in fichas("output")], ["alfa", "Q9", "zeta"])
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Q9")
        self.assertIsNone(e.cambiar_variable(vid, nombre="Bomba"))
        self.assertEqual([b["n"] for b in fichas("output")], ["alfa", "Bomba", "zeta"])
        self.assertIsNone(e.quitar_variable(vid))
        self.assertEqual([b["n"] for b in fichas("output")], ["alfa", "zeta"])
        # Sin elementos: un único aviso, sin fichas vacías.
        vacio = bloques.Programador(lambda: ({}, []))
        self.assertEqual(vacio.paleta.bloques(), [])
        self.assertFalse(vacio.paleta.mensaje.isHidden())
        # variables numéricas del valor: una ficha por variable
        e.nueva_variable("CT", "internal", {"kind": "int"})
        e.nueva_variable("AA", "output", {"kind": "int"})
        d = self.anadir_accion(ids["1"], "activacion")
        d.prog.elegir_categoria("vnum")
        self.assertEqual([b["n"] for b in d.prog.paleta.bloques()], ["AA", "CT"])

    def test_SEDI112_panel_de_opciones_etapa_transicion_y_encaje_a_1360x860(self):
        """REQ-EDT-02, REQ-EDT-09: el panel de opciones de abajo muestra, de una etapa, etiqueta, tipo, comentario y
        colocación a la izquierda, sin el bloque derecho de acciones; la paleta y la selección de acción siguen accesibles; de una transición, la columna
        estrecha de etiqueta, mostrar y comentario y su receptividad; cabe a 1360×860 con altura suficiente y el divisor con
        el dibujo se puede mover; el panel izquierdo solo lleva la paleta."""
        w = self.w
        e, ids, ts = self.secuencial()
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00"}))
        w.resize(1360, 860)
        w.show()
        w._abrir_opciones()
        QApplication.processEvents()
        p = w.props
        self.assertFalse(w.dock.isAncestorOf(p))
        e.seleccionar([ids["1"]])
        QApplication.processEvents()
        self.assertEqual((p.pagina, p.s_colocacion.currentData(), p.s_acciones.count()), ("etapa", "fila", 1))
        p.s_colocacion.setCurrentIndex(p.s_colocacion.findData("columna"))
        p.s_colocacion.activated.emit(p.s_colocacion.currentIndex())
        self.assertEqual(e.colocacion(ids["1"]), "columna")
        self.assertTrue(p.izq.isVisible() and p.izq.width() <= 240, "columna estrecha a la izquierda")
        self.assertFalse(p.s_acciones.isVisible());self.assertFalse(p.der.isVisible())
        self.assertLess(p.izq.x(),20,"los campos conservados quedan a la izquierda")
        w.editar_accion(ids["1"],e.acciones(ids["1"])[0]["id"])
        self.assertEqual((p.pagina, p.continua), ("vacio", True), "una continua no lleva campos: solo la frase (encargo 12)")
        self.assertEqual(p.accion.b_etapa.text(), "Etapa 1", "solo informa de la etapa: no es un botón")
        from PySide6.QtWidgets import QPushButton
        self.assertNotIsInstance(p.accion.b_etapa, QPushButton)
        self.assertEqual(p.pagina, "vacio")
        e.seleccionar([ids["1"]])  # otra vez la etapa (la etiqueta no lleva a ella)
        QApplication.processEvents()
        self.assertEqual(p.pagina, "etapa")
        n = len(e.ed.draft_actions())
        e.colocar("accion:continua",QPointF(850,600))  # la paleta conserva la creación y las propiedades de acción
        self.assertEqual((len(e.ed.draft_actions()), p.pagina, p.continua), (n + 1, "vacio", True))
        e.seleccionar([ts["t1"]])
        QApplication.processEvents()
        self.assertEqual(p.pagina, "transicion")
        self.assertTrue(p.prog.isVisible() and p.t_etiqueta.isVisible() and p.t_comentario.isVisible())
        # altura y ancho suficientes a 1360×860, y el divisor se mueve
        self.assertGreaterEqual(w.inferior.height(), w.props.minimumSizeHint().height())
        self.assertLessEqual(p.minimumSizeHint().width(), w.inferior.width())
        self.assertLessEqual(p.minimumSizeHint().height(), w.inferior.height())
        antes = w.vsplit.sizes()
        w.vsplit.moveSplitter(antes[0] - 60, 1)
        self.assertEqual(w.vsplit.sizes()[1], antes[1] + 60, "el divisor entre el dibujo y el panel se mueve")
        # una acción por evento con valor y evento: todo cabe
        e.nueva_variable("CT", "internal", {"kind": "int"})
        e.nueva_variable("I02", "input")
        self.assertIsNone(e.poner_accion(ids["0"], {"tipo": "evento", "variable": "CT", "valor": "CT + 1", "evento": "↑I02"}))
        w.editar_accion(ids["0"], e.acciones(ids["0"])[0]["id"])
        QApplication.processEvents()
        self.assertTrue(p.accion.caja_valor.isVisible() and p.pagina_bloques.isVisible())
        self.assertLessEqual(p.minimumSizeHint().width(), w.inferior.width())

    def _con_accion_por_evento(self):
        """Un grafcet con una acción memorizada por evento (valor y evento a la vez) y su transición; devuelve (e, ids, ts, aid)."""
        e, ids, ts = self.secuencial()
        e.nueva_variable("CT", "internal", {"kind": "int"})
        e.nueva_variable("I02", "input")
        self.assertIsNone(e.poner_accion(ids["0"], {"tipo": "evento", "variable": "CT", "valor": "CT + 1", "evento": "↑I02"}))
        return e, ids, ts, e.acciones(ids["0"])[0]["id"]

    def test_SEDI121_panel_inferior_a_todo_el_ancho_y_laterales_solo_arriba(self):
        """REQ-EDT-09, REQ-EDT-02: el panel inferior ocupa todo el ancho de la ventana, por debajo del dibujo y de los
        paneles laterales; el izquierdo (paleta) y el derecho quedan encima, a la altura del dibujo; plegarlos o
        desplegarlos no cambia el panel inferior; su altura se mueve con el divisor y no baja de lo que pide su contenido."""
        from PySide6.QtWidgets import QDockWidget
        w = self.w
        e, ids, ts, aid = self._con_accion_por_evento()
        self.assertEqual(w.findChildren(QDockWidget), [], "el panel izquierdo ya no es un dock de toda la altura")
        for tam in ((2000, 1000), (1366, 768)):
            w.resize(*tam)
            w.show()
            w.editar_accion(ids["0"], aid)
            QApplication.processEvents()
            ventana = w.centralWidget()
            inf = QRectF(w.inferior.mapTo(ventana, QPoint(0, 0)), w.inferior.size())
            self.assertEqual((inf.left(), inf.width()), (0, ventana.width()), f"{tam}: el inferior, de borde a borde")
            for panel in (w.dock, w.derecho, w.diagrama):
                self.assertTrue(panel.isVisible(), panel)
                alto = panel.mapTo(ventana, QPoint(0, panel.height())).y()
                self.assertLessEqual(alto, inf.top(), f"{tam}: {panel} no invade el panel inferior")
            self.assertGreater(w.dock.mapTo(ventana, QPoint(0, 0)).x() + w.dock.width(), 0)
            antes = (w.inferior.geometry(), w.vsplit.sizes())
            w.flechas["izquierdo"].click()
            w.flechas["derecho"].click()
            QApplication.processEvents()
            self.assertTrue(w.dock.isHidden() and w.derecho.isHidden())
            plegado = (w.inferior.geometry(), w.vsplit.sizes())
            self.assertEqual(plegado, antes, "plegar los laterales no toca el inferior")
            w.flechas["izquierdo"].click()
            w.flechas["derecho"].click()
            QApplication.processEvents()
            self.assertEqual((w.dock.width(), w.derecho.width()), (w.ancho_lateral, w.ancho_derecho))
            self.assertEqual((w.inferior.geometry(), w.vsplit.sizes()), antes)
        # altura: el divisor la mueve y hay un mínimo que deja ver los programadores
        minimo = w.props.minimumSizeHint().height()
        self.assertGreaterEqual(w.inferior.height(), minimo)
        w.vsplit.moveSplitter(w.vsplit.height() - 20, 1)  # intento de dejarlo casi sin altura
        QApplication.processEvents()
        self.assertGreaterEqual(w.inferior.height(), minimo, "no se aprieta por debajo de lo que pide el panel")
        w.vsplit.moveSplitter(0, 1)  # y de comerse el dibujo
        QApplication.processEvents()
        self.assertGreater(w.vsplit.widget(0).height(), 0)
        # plegado con ▾: desaparece y vuelve a su altura
        w.flechas["inferior"].click()
        self.assertTrue(w.inferior.isHidden())
        w.flechas["inferior"].click()
        self.assertFalse(w.inferior.isHidden())

    def test_SEDI122_opciones_sin_controles_cortados_ni_solapes(self):
        """REQ-EDT-09, REQ-EDT-02: con una acción por evento (programador del valor y del evento a la vez) y con una
        transición, a 2000×1000 y a 1366×768, todos los controles del panel de opciones (Escribir a mano, papelera,
        botones) quedan dentro del panel y de la ventana, y el programador del valor y el del evento no se solapan."""
        from PySide6.QtWidgets import QAbstractButton
        w = self.w
        e, ids, ts, aid = self._con_accion_por_evento()
        p = w.props

        def sin_cortes(sel, tam):
            QApplication.processEvents()
            raiz = QRectF(p.rect())
            botones = [b for b in p.findChildren(QAbstractButton) if b.isVisibleTo(p)]
            self.assertGreater(len(botones), 3, sel)
            for b in botones:
                ancestro = b.parentWidget()
                while ancestro is not None and ancestro is not p:
                    if ancestro.objectName() == "categoriasBloques":
                        ancestro.ensureWidgetVisible(b, 0, 0)
                        QApplication.processEvents()
                        self.assertTrue(QRectF(ancestro.viewport().rect()).contains(
                            QRectF(b.mapTo(ancestro.viewport(), QPoint(0, 0)), b.size())), b.text())
                        break
                    ancestro = ancestro.parentWidget()
                r = QRectF(b.mapTo(p, QPoint(0, 0)), b.size())
                self.assertTrue(raiz.contains(r), f"{tam} {sel}: «{b.text() or b.toolTip()}» fuera del panel {r} {raiz}")
                g = QRectF(b.mapTo(w, QPoint(0, 0)), b.size())
                self.assertTrue(QRectF(w.rect()).contains(g), f"{tam} {sel}: «{b.text() or b.toolTip()}» fuera de la ventana")
            for nombre in ("t_crear",):
                c = getattr(p, nombre)
                if c.isVisibleTo(p):
                    self.assertGreaterEqual(c.width(), c.sizeHint().width(), f"{tam} {sel}: {nombre} recortado")
        for tam in ((2000, 1000), (1366, 768)):
            w.resize(*tam)
            w.show()
            w.editar_accion(ids["0"], aid)
            QApplication.processEvents()
            self.assertTrue(p.accion.caja_valor.isVisibleTo(p) and p.pagina_bloques.isVisibleTo(p))
            a = QRectF(p.accion.caja_valor.mapTo(p, QPoint(0, 0)), p.accion.caja_valor.size())
            b = QRectF(p.pagina_bloques.mapTo(p, QPoint(0, 0)), p.pagina_bloques.size())
            self.assertFalse(a.intersects(b), f"{tam}: el valor y el evento no se solapan")
            self.assertLess(a.right(), b.left() + 1)
            sin_cortes("accion_evento", tam)
            e.seleccionar([ts["t1"]])
            QApplication.processEvents()
            self.assertEqual(p.pagina, "transicion")
            sin_cortes("transicion", tam)
            self.assertLessEqual(p.minimumSizeHint().width(), w.inferior.width())

    def test_SEDI113_traza_en_simular_y_leyenda_en_ayuda(self):
        """REQ-SIM-03: al simular la traza queda oculta y puede desplegarse y plegarse con su flecha; la leyenda es
        una ventana propia en «Ayuda > Leyenda del dibujo»; ni Traza ni Leyenda son pestañas al editar."""
        w = self.w
        e, ids, ts = self.secuencial()
        w.show()
        self.assertIs(w.inferior.currentWidget(), w.props)
        e.poner_condicion(ts["t1"], "marcha")
        e.poner_condicion(ts["t2"], "paro")
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.inferior.currentIndex(), 0)
        self.assertTrue(w.inferior.isHidden())
        self.assertTrue(w.inferior.currentWidget().isAncestorOf(w.traza))
        ayuda = next(a.menu() for a in w.menuBar().actions() if a.text() == "A&yuda")
        accion = next(a for a in ayuda.actions() if "Leyenda" in a.text())
        accion.trigger()
        self.assertTrue(w._leyenda.isVisible() and not w._leyenda.isModal())
        self.assertTrue(any("Etapa activa" in x.text() for x in w._leyenda.findChildren(QLabel)))
        w._leyenda.close()
        w.flechas["inferior"].click()
        self.assertFalse(w.inferior.isHidden())
        w.flechas["inferior"].click()
        self.assertTrue(w.inferior.isHidden())
        self.assertFalse(w.ajustes.value("paneles/inferior", True, type=bool))

    def test_SEDI114_variables_nuevas_visibles_al_instante_en_la_accion(self):
        """REQ-ACT-01, REQ-EDT-07: con las opciones de la acción a la vista, una variable que se crea, renombra, quita o cambia
        de papel o tipo en la tabla de variables aparece (o desaparece) al momento en la lista de la acción y en el
        programador de su valor."""
        w = self.w
        e, ids, ts = self.secuencial()
        d = self.anadir_accion(ids["1"], "activacion")
        pv = w.variables
        pv.nueva("output")
        fila = pv.tabla.rowCount() - 1
        pv.tabla.item(fila, 0).setText("Nueva")
        self.assertIn("Nueva", d.ofrecidas())
        self.assertTrue(any(d.variable.itemData(i) == "Nueva" for i in range(d.variable.count())), "en el desplegable, al momento")
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Nueva")
        pv.elegir(fila, 2, {"kind": "int"})
        d.poner_variable("Nueva")
        self.assertFalse(d.caja_numerica.isHidden())
        d.prog.elegir_categoria("vnum")
        self.assertEqual([b["n"] for b in d.prog.paleta.bloques()], ["Nueva"], "y en el programador del valor")
        self.assertIsNone(e.cambiar_variable(vid, nombre="Otra"))
        self.assertEqual([b["n"] for b in d.prog.paleta.bloques()], ["Otra"])
        self.assertTrue(any(d.variable.itemData(i) == "Otra" for i in range(d.variable.count())))
        self.assertIsNone(e.cambiar_variable(vid, role="internal"))
        self.assertIn("Otra", d.ofrecidas())
        pv.nueva("output")
        pv.tabla.item(pv.tabla.rowCount() - 1, 0).setText("Q7")
        self.assertIn("Q7", d.ofrecidas())
        self.poner_tipo(d, "continua")
        self.assertNotIn("Otra", d.ofrecidas(), "una continua solo escribe booleanas")
        self.assertIsNone(e.quitar_variable(next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Q7")))
        self.assertNotIn("Q7", d.ofrecidas())

    def test_SEDI115_no_colocar_un_elemento_encima_de_otro(self):
        """REQ-EDT-02: al soltar una ficha de la paleta o al terminar de mover (un elemento o un grupo de acciones), si su caja
        (con un margen de 8) se solapa con la de una etapa, transición, barra o acción, no se coloca (desde la paleta no se
        crea; al mover vuelve a su sitio) y se avisa con «No se puede poner encima de otro elemento»; durante el arrastre se
        ve en rojo con el cursor de prohibido; pegar una acción a otra (imán) sigue funcionando."""
        from escritorio.edicion import MSG_SOLAPE
        w = self.w
        e, ids, ts = self.secuencial()
        e.nueva_variable("Q00", "output")
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00"}))
        w.show()
        QApplication.processEvents()
        self.assertEqual(MSG_SOLAPE, "No se puede poner encima de otro elemento")
        # desde la paleta: encima de una etapa, de una transición y de una acción, no
        n = (len(e.M["steps"]), len(e.M["transitions"]), len(e.M["bars"]))
        for ficha, p in (("etapa", centro(e.M, ids["0"])), ("etapa", centro(e.M, ids["0"]) + QPointF(30, 10)),
                         ("transicion", centro(e.M, ids["1"])), ("transicion", centro(e.M, ts["t1"]) + QPointF(0, 6)),
                         ("simultaneidad", centro(e.M, ids["0"]))):
            e.colocar(ficha, p)
            self.assertEqual((len(e.M["steps"]), len(e.M["transitions"]), len(e.M["bars"])), n, (ficha, p))
            self.assertEqual((e.mensaje, e.mensaje_info), (MSG_SOLAPE, True))
        antes = len(e.ed.draft_actions())
        caja = next(c for c in w.diagrama.cajas_acciones if c["etapa"] == ids["1"])
        x, y, ancho, alto = caja["rect"]
        e.colocar("accion:evento", QPointF(x + 10, y + alto / 2 + 6))  # encima, pero no a su lado: no cabe
        self.assertEqual(len(e.ed.draft_actions()), antes)
        # en un hueco libre sí
        e.colocar("etapa", QPointF(100 + 400, 60))
        self.assertEqual(len(e.M["steps"]), n[0] + 1)
        # el imán sigue valiendo: pegada al lado derecho de una acción
        e.colocar("accion:continua", QPointF(x + ancho + 4, y + alto / 2))
        self.assertEqual(len(e.acciones(ids["1"])), 2, "se pega a la otra acción")
        # sobrevolar: devuelve False y pone la caja en rojo
        self.assertFalse(e.sobrevolar("etapa", centro(e.M, ids["0"])))
        self.assertEqual(len(w.diagrama.prohibidos), 1)
        self.assertEqual(w.diagrama.viewport().cursor().shape(), Qt.CursorShape.ForbiddenCursor)
        self.assertTrue(e.sobrevolar("etapa", QPointF(900, 400)))
        self.assertEqual((len(w.diagrama.prohibidos), w.diagrama.viewport().cursor().shape()), (0, Qt.CursorShape.CrossCursor))
        # al mover: una etapa soltada sobre otra vuelve a su sitio; en un hueco, se mueve
        origen = posiciones_modelo(e)[ids["1"]]
        c = centro(e.M, ids["1"])
        e.prensar(c)
        destino = centro(e.M, ids["0"]) + QPointF(4, 0)
        e.mover(destino)
        self.assertEqual(len(w.diagrama.prohibidos), 1, "en rojo mientras se arrastra")
        self.assertEqual(w.diagrama.viewport().cursor().shape(), Qt.CursorShape.ForbiddenCursor)
        e.soltar(destino)
        self.assertEqual(posiciones_modelo(e)[ids["1"]], origen)
        self.assertEqual((e.mensaje, e.mensaje_info), (MSG_SOLAPE, True))
        self.assertEqual(len(w.diagrama.prohibidos), 0)
        libre = QPointF(c.x() + 300, c.y())
        e.prensar(c)
        e.mover(libre)
        self.assertEqual(len(w.diagrama.prohibidos), 0)
        e.soltar(libre)
        self.assertNotEqual(posiciones_modelo(e)[ids["1"]], origen)
        # un grupo de acciones sueltas movido sobre una etapa vuelve; sobre otra acción, se pega
        d = e.poner_accion_suelta(QPointF(900, 500))
        c = centro_caja(w, d)
        e.prensar(c)
        e.mover(centro(e.M, ids["0"]) + QPointF(60, 0))
        self.assertEqual(len(w.diagrama.prohibidos), 1)
        e.soltar(centro(e.M, ids["0"]) + QPointF(60, 0))
        self.assertEqual(e._borrador(d).get("etapa"), None)
        self.assertEqual(centro_caja(w, d), c, "vuelve a su sitio")

    def test_SEDI116_lo_escrito_sin_confirmar_no_se_aplica_a_otro_elemento(self):
        """REQ-EDT-02: si el elemento mostrado en el panel de opciones cambia sin clic (deshacer, rehacer o selección por
        código) con un campo a medio escribir, al perder el foco ese texto no se aplica al elemento nuevo; y una barra
        soltada encima de una etapa avisa como los demás elementos."""
        from escritorio.edicion import MSG_SOLAPE
        w = self.w
        e, ids, ts = self.secuencial()
        e.nueva_variable("CT", "internal", {"kind": "int"})
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "activacion", "variable": "CT", "valor": "5"}))
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "activacion", "variable": "CT", "valor": "7"}))
        A, B = [a["id"] for a in e.acciones(ids["1"])]
        w.show()
        w.activateWindow()
        QApplication.processEvents()
        valores = lambda: [e.datos_accion(i)["valor"] for i in (A, B)]  # noqa: E731
        p = w.props.accion
        w.editar_accion(ids["1"], A)
        p.valor.setFocus()
        p.valor.setText("99")  # a medio escribir, sin confirmar
        w.editar_accion(ids["1"], B)  # cambia la acción mostrada sin clic
        w.props.s_etiqueta.setFocus()
        p.valor.clearFocus()
        QApplication.processEvents()
        self.assertEqual((valores(), p.valor.text()), (["5", "7"], "7"))
        # lo mismo con la etiqueta de una etapa y el comentario de una transición
        e.seleccionar([ids["0"]])
        w.props.s_etiqueta.setFocus()
        w.props.s_etiqueta.setText("Otra")
        e.seleccionar([ids["1"]])
        w.props.s_comentario.setFocus()
        QApplication.processEvents()
        self.assertEqual((e.nombres[ids["0"]], e.nombres[ids["1"]]), ("0", "1"))
        # una barra encima de una etapa: sin crearse y con el aviso
        n = len(e.M["bars"])
        e.mensaje = ""
        e.colocar("simultaneidad", centro(e.M, ids["0"]))
        self.assertEqual((len(e.M["bars"]), e.mensaje, e.mensaje_info), (n, MSG_SOLAPE, True))


    def test_SEDI118_nombres_de_variable_con_cifra_delante(self):
        """REQ-EDT-07, REQ-EDT-09, REQ-DAT-01: un nombre como 1M1 o 2S3 (nomenclatura industrial) vale como variable: se
        crea en la tabla de variables, en las fórmulas se escribe entre comillas invertidas (`1M1`), la ida y vuelta texto,
        bloques y texto lo conserva, los bloques, «Se dibuja», la tabla y el dibujo lo muestran sin ellas, se guarda, se
        abre y se simula; los números y lo que parece una duración (2s) siguen rechazados."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        pv = w.variables
        pv.nueva()
        fila = pv.tabla.rowCount() - 1
        for malo, parte in (("2s", "duración"), ("10ms", "duración"), ("3us", "duración"), ("12", "solo un número")):
            pv.tabla.item(fila, 0).setText(malo)
            self.assertIn(parte, pv.msg.text(), malo)
            self.assertEqual(pv.sin_nombre(), 1, "la fila sigue en blanco")
            pv.parpadeo.parar()
        pv.tabla.item(fila, 0).setText("1M2")
        self.assertEqual(pv.msg.text(), "")
        v = next(x for x in e.ed.model["variables"] if x["name"] == "1M2")
        self.assertEqual((v["role"], v["type"]["kind"]), ("input", "bool"))
        self.assertIsNone(e.nueva_variable("2S3", "output", {"kind": "bool"}))
        # la receptividad: el nombre va entre comillas invertidas en el texto
        e.seleccionar([ts["t1"]])
        p, prog = w.props, w.props.prog
        self.assertIsNone(e.comprobar(ts["t1"], "`1M2` AND NOT paro"))
        self.assertIsNotNone(e.comprobar(ts["t1"], "1M2 AND NOT paro"), "sin comillas invertidas no se puede leer")
        prog.lienzo.soltar((), bloques.var("1M2", "input"))
        self.assertEqual((p.t_texto.text(), e.texto_condicion(ts["t1"])), ("`1M2`", "`1M2`"))
        prog.lienzo.soltar((), bloques.nuevo("y"))
        prog.lienzo.soltar(("b",), bloques.nuevo("no", a=bloques.var("paro", "input")))
        self.assertEqual((p.t_texto.text(), e.texto_condicion(ts["t1"])), ("`1M2` AND NOT paro",) * 2)
        self.assertEqual(prog.texto(), "`1M2` AND NOT paro")
        self.assertEqual(prog.lienzo.arbol["a"], {"k": "var", "n": "1M2", "papel": "input"})
        # ida y vuelta: texto -> bloques -> texto
        for t in ("`1M2` AND NOT paro", "↑(`1M2`) OR `2S3`", "`1M2`", "3s/(`1M2`)", "NOT `2S3` AND (`1M2` OR paro)"):
            prog.poner(t)
            self.assertEqual(prog.texto(), t, t)
        prog.poner("`1M2` AND NOT paro")
        # el nombre se ve sin comillas en los bloques (desplegable), en «Se dibuja» y en el dibujo
        motor = bloques.Motor(prog.fuente)
        motor.reiniciar()
        self.assertEqual([x[2] for x in motor.elementos(prog.lienzo.arbol["a"])], ["1M2"])
        p._previsualizar()
        self.assertIn("1M2", p.t_dibujo.text())
        self.assertNotIn("`", p.t_dibujo.text())
        cond = "".join(x["t"] for x in next(t for t in e.M["transitions"] if t["id"] == ts["t1"])["cond"])
        self.assertIn("1M2", cond)
        self.assertNotIn("`", cond)
        self.assertIn("1M2", [pv.tabla.item(r, 0).text() for r in range(pv.tabla.rowCount())])
        # también como destino de una acción (la lista, sin comillas) y en un valor numérico
        e.nueva_variable("1CT", "internal", {"kind": "int"})
        d = self.anadir_accion(ids["1"], "activacion", "1CT", "`1CT` + 1")
        self.assertIn("1CT", [d.variable.itemData(i) for i in range(d.variable.count())])
        aid = e.acciones(ids["1"])[-1]["id"]
        self.assertEqual(e.datos_accion(aid)["valor"], "`1CT` + 1")
        self.assertEqual(d.prog.texto(), "`1CT` + 1")
        self.assertEqual(d.prog.lienzo.arbol["a"], {"k": "vnum", "n": "1CT"})
        self.assertTrue(e.ed.validate().can_simulate)
        # se guarda, se abre y se simula
        destino = Path(self.tmp.name) / "con-cifras"
        e.guardar(destino)
        ab = open_model(destino)
        self.assertIn("1M2", [x["name"] for x in ab.doc["variables"]])
        from escritorio.edicion import Edicion
        e2 = Edicion.desde(ab.doc, {}, "abierto", destino, ab.presentations[0])
        self.assertEqual(e2.texto_condicion(ts["t1"]), "`1M2` AND NOT paro")
        self.assertTrue(e2.ed.validate().can_simulate)
        # renombrar una variable a un nombre con cifra reescribe sus usos entre comillas invertidas
        vid = next(x["id"] for x in e.ed.model["variables"] if x["name"] == "paro")
        self.assertIsNone(e.cambiar_variable(vid, nombre="3P3"))
        self.assertEqual(e.texto_condicion(ts["t1"]), "`1M2` AND NOT `3P3`")
        self.assertTrue(e.ed.validate().can_simulate)

    def test_SEDI119_bloque_parentesis_en_todos_los_programadores(self):
        """REQ-EDT-02, REQ-EDT-09: el bloque «( )» está en la carpeta Operadores de todos los programadores (receptividad
        de una transición, condición y evento de una acción, y valor de una acción) y se suelta en cualquier hueco; con él se
        arma `((CT - 5 + N5) * 1 / 1) + 1` y `(a OR b) AND NOT c`; el texto conserva los paréntesis, y al pasar de texto a
        bloques vuelven como bloques «( )» sin añadir otros; el significado no cambia."""
        from escritorio import bloques
        from escritorio.bloques import arbol_a_texto, nuevo, texto_a_arbol, texto_a_arbol_valor
        from grafcet.expressions import parse
        w = self.w
        e, ids, ts = self.secuencial()
        for nombre, papel, tipo in (("CT", "internal", {"kind": "int"}), ("N5", "internal", {"kind": "int"}),
                                    ("a", "input", {"kind": "bool"}), ("b", "input", {"kind": "bool"}),
                                    ("c", "input", {"kind": "bool"}), ("DEC", "internal", {"kind": "decimal", "scale": 2})):
            e.nueva_variable(nombre, papel, tipo)
        # la receptividad de una transición: (a OR b) AND NOT c, con el bloque
        e.seleccionar([ts["t1"]])
        p, prog = w.props, w.props.prog
        prog.elegir_categoria("operador")
        par = next((n for n in prog.paleta.bloques() if n["k"] == "par"), None)
        self.assertEqual(par, {"k": "par", "a": None})
        prog.lienzo.soltar((), nuevo("y"))
        prog.lienzo.soltar(("a",), par)
        prog.lienzo.soltar(("a", "a"), nuevo("o"))
        prog.lienzo.soltar(("a", "a", "a"), bloques.var("a", "input"))
        prog.lienzo.soltar(("a", "a", "b"), bloques.var("b", "input"))
        prog.lienzo.soltar(("b",), nuevo("no", a=bloques.var("c", "input")))
        self.assertEqual((p.t_texto.text(), e.texto_condicion(ts["t1"])), ("(a OR b) AND NOT c",) * 2)
        # vuelve a bloques con el mismo paréntesis, sin añadir otros
        prog.poner("a OR b")
        prog.poner("(a OR b) AND NOT c")
        self.assertEqual((prog.lienzo.arbol["a"]["k"], prog.lienzo.arbol["a"]["a"]["k"], prog.lienzo.arbol["b"]["k"]),
                         ("par", "o", "no"))
        self.assertEqual(prog.texto(), "(a OR b) AND NOT c")
        # sin el bloque, la precedencia sigue siendo la del analizador: a OR b AND NOT c = a OR (b AND NOT c)
        prog.poner("a OR b AND NOT c")
        self.assertEqual((prog.lienzo.arbol["k"], prog.lienzo.arbol["b"]["k"], prog.texto()), ("o", "y", "a OR b AND NOT c"))
        # soltar el bloque sobre un bloque ocupado lo envuelve
        prog.poner("a OR b")
        prog.lienzo.soltar(("a",), nuevo("par"))
        self.assertEqual(prog.texto(), "(a) OR b")
        prog.poner("a OR b")
        # el valor de una acción: ((CT - 5 + N5) * 1 / 1) + 1
        d = self.anadir_accion(ids["1"], "activacion", "DEC")  # la división da un decimal
        d.prog.elegir_categoria("aritm")
        self.assertEqual([n["k"] for n in d.prog.paleta.bloques()], ["ar"] * 4 + ["par"])
        lienzo = d.prog.lienzo
        d._desde_bloques("")
        lienzo.soltar((), nuevo("ar", op="+"))
        lienzo.soltar(("b",), nuevo("num", v="1"))
        lienzo.soltar(("a",), nuevo("par"))
        lienzo.soltar(("a", "a"), nuevo("ar", op="/"))
        lienzo.soltar(("a", "a", "b"), nuevo("num", v="1"))
        lienzo.soltar(("a", "a", "a"), nuevo("ar", op="*"))
        lienzo.soltar(("a", "a", "a", "b"), nuevo("num", v="1"))
        lienzo.soltar(("a", "a", "a", "a"), nuevo("par"))
        lienzo.soltar(("a", "a", "a", "a", "a"), nuevo("ar", op="+"))
        lienzo.soltar(("a", "a", "a", "a", "a", "b"), nuevo("vnum", n="N5"))
        lienzo.soltar(("a", "a", "a", "a", "a", "a"), nuevo("ar", op="-"))
        lienzo.soltar(("a", "a", "a", "a", "a", "a", "a"), nuevo("vnum", n="CT"))
        lienzo.soltar(("a", "a", "a", "a", "a", "a", "b"), nuevo("num", v="5"))
        esperado = "((CT - 5 + N5) * 1 / 1) + 1"
        self.assertEqual((d.valor.text(), arbol_a_texto(lienzo.arbol)), (esperado, esperado))
        self.assertEqual(e.datos_accion(e.acciones(ids["1"])[-1]["id"])["valor"], esperado)
        self.assertTrue(e.ed.validate().can_simulate)
        # la ida y vuelta de texto a bloques y a texto, también con el hueco «?» del ejemplo del responsable
        vars_ = {"CT": ("internal", "int"), "N5": ("internal", "int")}
        for t in ("((CT - 5 + ?) * 1 / 1) + 1", esperado, "(CT)", "((CT))", "CT * (N5 + 1)", "(CT + 1) * 2", "-(CT + 1)",
                  "CT - (N5 - 1)", "(CT - N5) - 1", "(((1)))"):
            arbol = texto_a_arbol_valor(t, vars_, [])
            self.assertEqual(arbol_a_texto(arbol), t, t)
            self.assertEqual(arbol_a_texto(texto_a_arbol_valor(arbol_a_texto(arbol), vars_, [])), t, t)
        self.assertEqual(texto_a_arbol_valor("((CT - 5 + ?) * 1 / 1) + 1", vars_, [])["a"]["k"], "par")
        # en la condición y el evento de una acción (mismo programador): paréntesis conservados
        acc = {"a": ("input", "bool"), "b": ("input", "bool"), "c": ("input", "bool"), "CT": ("internal", "int")}
        for t in ("(a OR b) AND NOT c", "NOT (a AND b)", "↑((a AND b))", "↑(a OR b)", "3s/((a AND b))", "3s/(a AND b)",
                  "(CT > 3) AND a", "CT > (CT + 1) * 2", "((a))", "a AND (b AND c)", "(a AND b) AND c", "a AND (? OR b)"):
            self.assertEqual(arbol_a_texto(texto_a_arbol(t, acc, [])), t, t)
        e.seleccionar([ids["1"]])
        e.poner_accion(ids["1"], {"tipo": "condicionada", "variable": "Q00", "condicion": "(a OR b) AND NOT c"}, None,
                       ("output", "bool"))
        aid = e.acciones(ids["1"])[-1]["id"]
        w.editar_accion(ids["1"], aid)
        self.assertEqual(w.props.prog.texto(), "(a OR b) AND NOT c")
        self.assertEqual(w.props.prog.lienzo.arbol["a"]["k"], "par")
        self.assertEqual(w.props.prog.categorias["operador"].text(), "Operadores")
        # el significado no cambia: los paréntesis solo agrupan
        igual = lambda x, y: parse(a_nucleo(x, [], acc), lambda c, n: n) == parse(a_nucleo(y, [], acc), lambda c, n: n)  # noqa: E731
        self.assertTrue(igual("(a OR b) AND NOT c", "(a OR b) AND (NOT c)") and igual("((a))", "a"))
        self.assertFalse(igual("(a OR b) AND c", "a OR b AND c"))

    def test_SEDI120_dibujo_del_bloque_parentesis_y_de_las_operaciones_anidadas(self):
        """REQ-EDT-02: el bloque «( )» se dibuja con un paréntesis a cada lado, tan altos como lo que encierra (también si
        se apila); las operaciones aritméticas encadenadas se leen de izquierda a derecha con el operador entre sus
        operandos (sin bloques uno dentro de otro) y, si no caben, pasan de línea sin dejar un operador suelto al final;
        se dibuja a cualquier ancho."""
        from escritorio import bloques
        from escritorio.bloques import Programador, texto_a_arbol_valor
        from PySide6.QtCore import QRectF
        vars_ = {"CT": ("internal", "int"), "N5": ("internal", "int")}
        prog = Programador(lambda: (vars_, []), valor=True)
        t = "((CT - 5 + N5) * 1 / 1) + 1"
        arbol = texto_a_arbol_valor(t, vars_, [])
        prog.lienzo.poner_arbol(arbol)
        motor = prog.lienzo.motor
        motor.reiniciar()
        # en una fila: cada paréntesis mide lo que el bloque que encierra
        c = motor.caja(arbol, (0,), motor.natural(arbol, (0,)) + 10)
        pares = []

        def recorre(caja):
            for _, _, it in caja.items:
                if isinstance(it, bloques._Caja):
                    recorre(it)
                elif it.tipo == "paren":
                    pares.append((caja, it))
        recorre(c)
        self.assertEqual(len(pares), 4, "dos bloques «( )», dos paréntesis cada uno")
        for caja, it in pares:
            hijo = next(x for _, _, x in caja.items if isinstance(x, bloques._Caja))
            self.assertEqual(it.h, hijo.h)
        # apilado a poco ancho: sigue sin salirse
        for ancho in (240, 300, 400, 500):
            motor.reiniciar()
            c = motor.caja(arbol, (0,), ancho)
            self.assertLessEqual(c.w, ancho + 1, ancho)
        # una cadena a - b + c se pone en línea (sin un bloque dentro de otro): leída de izquierda a derecha, con el operador
        # entre sus operandos; el bloque de dentro (a - b) conserva su sitio, que es el de su operador
        motor.reiniciar()
        cadena = texto_a_arbol_valor("CT - 5 + N5", vars_, [])
        c = motor.caja(cadena, (0,), 400)
        self.assertEqual([x[2].tipo if not isinstance(x[2], bloques._Caja) else x[2].nodo["k"] for x in c.items],
                         ["vnum", "txt", "num", "txt", "vnum"])
        self.assertEqual(len({round(x[1] + x[2].h / 2) for x in c.items}), 1, "todo en una fila")
        self.assertEqual([(f[1], f[2]["op"]) for f in c.fantasmas], [((0, "a"), "-")])
        # uno que lleva paréntesis (a - (b - c)) queda como un bloque dentro
        c = motor.caja(texto_a_arbol_valor("CT - (5 - N5)", vars_, []), (0,), 400)
        self.assertEqual(c.fantasmas, [])
        # a un ancho en que no cabe, pasa de línea y nunca deja un operador al final de una
        c = motor.caja(cadena, (0,), 100)
        lineas = {}
        for x, y, it in c.items:
            lineas.setdefault(round(y + it.h / 2), []).append((x, it))
        self.assertGreater(len(lineas), 1)
        for fila in lineas.values():
            ultimo = max(fila, key=lambda q: q[0])[1]
            self.assertFalse(isinstance(ultimo, bloques._Pieza) and ultimo.tipo == "txt", "operador al final de línea")
        # el ratón: el operador de dentro pertenece al bloque de dentro, y el de fuera al de fuera
        prog.lienzo.poner_arbol(cadena)
        prog.resize(520, 200)
        prog.show()
        QApplication.processEvents()
        lienzo = prog.lienzo
        lienzo._calcular(lienzo.width())
        ops = [(r, it) for _, (c0, ox, oy) in enumerate(lienzo._cajas) for r, it in
               [(QRectF(ox + x, oy + y, it.w, it.h), it) for x, y, it in c0.items
                if not isinstance(it, bloques._Caja) and it.tipo == "txt"]]
        self.assertEqual([lienzo.ruta_en(r.center()) for r, _ in ops], [(0, "a"), (0,)])
        # el dibujo no falla (con y sin hueco)
        for t_ in (t, "((CT - 5 + ?) * 1 / 1) + 1", "(?)"):
            prog.lienzo.poner_arbol(texto_a_arbol_valor(t_, vars_, []))
            prog.resize(520, 300)
            prog.show()
            QApplication.processEvents()
            self.assertFalse(prog.lienzo.grab().isNull())
        prog.close()

    # -- P-IMP-48: las acciones de una etapa no se colocan encima de otros elementos; colocación «matriz de 2» -----------
    def _solapes_de_acciones(self, e):
        """Lo que se toca en el dibujo: cada caja de acción dibujada contra las etapas, las transiciones, los textos de las
        transiciones (los que dibuja la escena, con el aviso de la transición) y las demás acciones."""
        from PySide6.QtWidgets import QGraphicsTextItem
        from escritorio.diagrama import H, TB, posiciones
        w = self.w
        cajas = [(c["id"], QRectF(*c["rect"])) for c in w.diagrama.cajas_acciones]
        fijos = [(i, QRectF(x - TB, y - 2, 2 * TB, 4) if any(t["id"] == i for t in e.M["transitions"])
                  else QRectF(x - H, y - H, 2 * H, 2 * H)) for i, (x, y) in posiciones(e.M).items()]
        fijos += [("texto", it.sceneBoundingRect()) for it in w.diagrama.scene().items()
                  if isinstance(it, QGraphicsTextItem) and it.toolTip().startswith("Transición")]
        malos = [(a, i) for a, r in cajas for i, q in fijos if r.intersects(q)]
        malos += [(a, b) for k, (a, r) in enumerate(cajas) for b, q in cajas[k + 1:] if r.intersects(q)]
        return malos

    def test_SEDI124_colocacion_en_matriz_de_dos_columnas(self):
        """REQ-ACT-01, REQ-EDT-02, REQ-DAT-01: «En matriz de 2» (menú de la etapa y panel de opciones) coloca las acciones en
        una cuadrícula de dos columnas, de izquierda a derecha y de arriba abajo (1.ª y 2.ª en la primera fila, 3.ª y 4.ª en
        la segunda…), con el mismo ancho en cada columna; una barra vertical común las une a la etapa, con una derivación a
        cada fila (la de la 2.ª columna pasa por debajo de la 1.ª y sube a su caja); se guarda en `presentation.actionLayouts`,
        se deshace, vale también en un grupo suelto y el banco la dibuja igual."""
        import re
        from escritorio.diagrama import ACT_CANAL, ACT_GAP, ACT_LINK, H
        from escritorio.edicion import COLOCACIONES, Edicion
        w = self.w
        w.nuevo()
        e = w.edicion
        e.pedir_accion = lambda sid, aid: None
        e.colocar("etapa", QPointF(120, 100))
        sid = e.M["steps"][0]["id"]
        for n in ("Q00", "Q01", "Q02", "Q03", "Q04"):
            e.nueva_variable(n, "output")
        e.nueva_variable("CT", "internal", {"kind": "int"})
        self.assertEqual([v for v, _ in COLOCACIONES], ["fila", "fila-separada", "matriz-2", "columna"])
        self.assertEqual(dict(COLOCACIONES)["matriz-2"], "En matriz de 2")
        self.assertIn("matriz-2", e.ed.ACTION_LAYOUTS)
        # el menú de la etapa y el panel de opciones la ofrecen
        e.seleccionar([sid])
        self.assertIn("En matriz de 2", [t for t, _ in dict(e.menu(centro(e.M, sid)))["Colocación de las acciones"]])
        self.assertIn("matriz-2", [w.props.s_colocacion.itemData(i) for i in range(w.props.s_colocacion.count())])
        resultados = {}
        for n in (1, 2, 3, 5):
            for a in list(e.ed.get(sid)["actionRefs"]):
                e.quitar_accion(a)
            for k in range(n):
                d = ({"tipo": "activacion", "variable": "CT", "valor": "CT + 1"} if k == 1 else
                     {"tipo": "continua", "variable": f"Q0{k}", "condicion": "Q00 AND Q01"} if k == 2 else
                     {"tipo": "desactivacion", "variable": "Q03", "valor": "0"} if k == 3 else
                     {"tipo": "continua", "variable": f"Q0{k}"})
                self.assertIsNone(e.poner_accion(sid, d))
            aids = e.ed.get(sid)["actionRefs"]
            e.colocar_acciones(sid, "matriz-2")
            self.assertEqual((e.colocacion(sid), e.ed.presentation["actionLayouts"]), ("matriz-2", {sid: "matriz-2"}))
            r = [self._caja(a)["rect"] for a in aids]
            self.assertEqual(self._solapes_de_acciones(e), [])
            # la cuadrícula: la 1.ª y la 2.ª en la misma fila, la 3.ª y la 4.ª en la siguiente…
            for i, (x, y, ancho, alto) in enumerate(r):
                self.assertAlmostEqual(y, r[i - i % 2][1], delta=0.01, msg=f"{n}: la acción {i} va en la fila {i // 2}")
                self.assertAlmostEqual(x, r[i % 2][0], delta=0.01, msg=f"{n}: y en la columna {i % 2}")
                self.assertAlmostEqual(ancho, r[i % 2][2], delta=0.01, msg="mismo ancho en cada columna")
                if i >= 2:
                    self.assertGreater(y, r[i - 2][1] + alto, "cada fila, debajo de la anterior")
            if n > 1:
                self.assertAlmostEqual(r[1][0], r[0][0] + r[0][2] + ACT_GAP, delta=0.01)
            # los trazos: la barra común a la izquierda y una derivación a cada fila; la de la 2.ª columna, por debajo de
            # la fila y subiendo a su caja
            u = next(u for u in w.diagrama.uniones_acciones if u["id"] == f"enlaceacc:{sid}")["trazos"]
            px, py = centro(e.M, sid).x(), centro(e.M, sid).y()
            bx = px + H + ACT_LINK / 2
            self.assertEqual(u[0], [(px + H, py), (px + H + ACT_LINK, py)], "el enlace de la etapa")
            if n > 1:
                barra = u[1]
                self.assertEqual(barra[0], (bx, py))
                self.assertAlmostEqual(barra[1][0], bx, delta=0.01)
                filas = [r[i:i + 2] for i in range(0, n, 2)]
                derivaciones = [t for t in u[2:] if len(t) == 2]
                self.assertEqual(len(derivaciones), len(filas) - 1, "una por cada fila salvo la primera (la del enlace)")
                for f, t in zip(filas, [t for t in u[2:] if len(t) == 4]):
                    self.assertEqual(t[0][0], bx)
                    self.assertAlmostEqual(t[1][0], f[1][0] - 14, delta=0.01)  # sube justo antes de la 2.ª caja
                    self.assertAlmostEqual(t[3][0], f[1][0], delta=0.01)
                    self.assertAlmostEqual(t[3][1], f[1][1] + H, delta=0.01)  # y entra por su lado izquierdo
                    self.assertGreater(t[0][1], f[0][1] + 2 * H, "por debajo de la caja de la 1.ª columna")
                    self.assertGreaterEqual(t[0][1] - (f[0][1] + 2 * H), ACT_CANAL - 0.01)
            resultados[n] = r
        # una operación de vista: se deshace y se rehace, y no cambia el modelo
        modelo = copy.deepcopy(e.ed.model)
        e.colocar_acciones(sid, "columna")
        self.assertEqual(e.ed.model, modelo)
        e.deshacer()
        self.assertEqual(e.colocacion(sid), "matriz-2")
        e.rehacer()
        e.deshacer()
        # guardar y abrir
        destino = Path(self.tmp.name) / "matriz"
        e.guardar(destino)
        op = open_model(destino)
        self.assertEqual(op.presentations[0]["actionLayouts"], {sid: "matriz-2"})
        self.assertEqual(Edicion.desde(op.doc, {}, "abierto", None, op.presentations[0]).colocacion(sid), "matriz-2")
        v = Vista("k", "t", "", lambda: (op.doc, layout_from_presentation(op.presentations[0])), normalize_options(None),
                  presentation=op.presentations[0])
        self.assertEqual({s["id"]: s["actionLayout"] for s in v.model["steps"]}[sid], "matriz-2")
        # un grupo de acciones sueltas también la admite
        a = e.poner_accion_suelta(QPointF(700, 300))
        x, y, ancho, alto = self._caja(a)["rect"]
        b = e.poner_accion_suelta(QPointF(x + ancho + 4, y + alto / 2))
        c = e.poner_accion_suelta(QPointF(x + 2 * ancho + 4, y + alto / 2))
        g = e._borrador(a)["grupo"]
        e.colocar_acciones(g, "matriz-2")
        self.assertEqual(e.colocacion(g), "matriz-2")
        r = [self._caja(i)["rect"] for i in (a, b, c)]
        self.assertEqual(r[0][1], r[1][1])
        self.assertGreater(r[2][1], r[0][1])
        self.assertEqual(r[2][0], r[0][0])
        # el banco dibuja la misma colocación con las mismas medidas
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        self.assertEqual(int(re.search(r"const ACT_CANAL\s*=\s*(\d+);", js).group(1)), ACT_CANAL)
        for texto in ('"matriz-2"', "ACT_CANAL", "filas", "canales"):
            self.assertIn(texto, js)

    def _captura1(self):
        """El caso de la captura 1: una etapa (la «1», con t2 «paro» debajo) y otra a su derecha, a su altura. Devuelve el
        editor, los ID de las etapas y la de la derecha."""
        e, ids, ts = self.secuencial()
        e.pedir_accion = lambda sid, aid: None
        for n in ("Q00", "Q01", "Q02", "Q03", "Q04"):
            e.nueva_variable(n, "output")
        e.colocar("etapa", QPointF(100 + 200, 220))
        s2 = next(s["id"] for s in e.M["steps"] if s["id"] not in ids.values())
        return e, ids, ts, s2

    def test_SEDI123_las_acciones_de_una_etapa_apartan_lo_que_estorba(self):
        """REQ-EDT-02, REQ-ACT-01: al añadir acciones a una etapa (Añadir…, el panel o unir una suelta; pegar, en
        S-EDI133), si su colocación llega a menos de 8 de otra etapa, transición, texto o acción, la etapa se queda como está y se desplaza hacia la
        derecha lo que estorba y lo que queda a su derecha, en la misma operación de deshacer; la colocación elegida no
        cambia sola. El caso de la captura 1: la etapa 1 con tres acciones en fila y la 2 a su derecha y a su altura."""
        w = self.w
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        pos0 = posiciones_modelo(e)
        diag0 = [str(d) for d in e.ed.validate().diagnostics]
        self.assertEqual(pos0[s2], (200, 220))
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        self.assertEqual(posiciones_modelo(e), pos0, "con sitio, no se mueve nada")
        n = len(e.ed.undo_stack)
        # la segunda en fila llegaría a la etapa 2: se aparta, y no cambia la colocación (antes pasaba a «matriz de 2»)
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q01"}))
        x2 = posiciones_modelo(e)[s2][0]
        self.assertGreater(x2, 200)
        self.assertEqual(x2 % 20, 0, "en pasos de rejilla")
        self.assertEqual(len(e.ed.undo_stack), n + 1, "la acción y el desplazamiento, una sola operación")
        self.assertEqual((e.colocacion(s1), e.ed.action_layouts()), ("fila", {}), "la colocación elegida no cambia sola")
        self.assertEqual(self._solapes_de_acciones(e), [])
        self.assertEqual(e.mensaje, "")
        self.assertEqual({i: p for i, p in posiciones_modelo(e).items() if i != s2},
                         {i: p for i, p in pos0.items() if i != s2}, "lo demás (a su izquierda y debajo) no se mueve")
        self.assertEqual(posiciones_modelo(e)[s2][1], 220)
        e.deshacer()  # la acción y el desplazamiento vuelven juntos
        self.assertEqual((posiciones_modelo(e), len(e.acciones(s1))), (pos0, 1))
        e.rehacer()
        self.assertEqual((posiciones_modelo(e)[s2][0], len(e.acciones(s1))), (x2, 2))
        # la tercera: otro desplazamiento, y sigue en fila
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q02"}))
        x3 = posiciones_modelo(e)[s2][0]
        self.assertGreater(x3, x2)
        self.assertEqual((e.colocacion(s1), len(e.acciones(s1)), self._solapes_de_acciones(e)), ("fila", 3, []))
        # «Añadir acción…» y unir una suelta: lo mismo
        self.assertTrue(e.anadir_accion(s1))
        x4 = posiciones_modelo(e)[s2][0]
        self.assertGreater(x4, x3)
        self.assertEqual(self._solapes_de_acciones(e), [])
        d = e.poner_accion_suelta(QPointF(900, 500))
        e.unir_accion(d, s1)
        self.assertEqual(e._borrador(d).get("etapa"), s1)
        self.assertGreater(posiciones_modelo(e)[s2][0], x4)
        self.assertEqual(self._solapes_de_acciones(e), [])
        # los ID no cambian, y las acciones siguen unidas a la etapa 1; nada de lo que se simula cambió por moverse
        self.assertEqual({s["label"]: s["id"] for s in e.M["steps"] if s["id"] != s2}, ids)
        self.assertEqual([str(x) for x in e.ed.validate().diagnostics if "acci" not in str(x).lower()],
                         [x for x in diag0 if "acci" not in x.lower()])
        modelo = copy.deepcopy(e.ed.model)
        e.ed.move(s2, 100, 220)  # lo vuelve a poner encima: apartarlo es solo presentación
        e.cambia()
        self.assertTrue(e._despejar(s1))
        self.assertEqual(e.ed.model, modelo, "el modelo (y su revisión) no cambia al apartar")
        self.assertEqual(self._solapes_de_acciones(e), [])
        # guardar y abrir: las posiciones nuevas viajan
        destino = Path(self.tmp.name) / "apartado"
        e.guardar(destino)
        self.assertEqual(layout_from_presentation(open_model(destino).presentations[0]), posiciones_modelo(e))

    def test_SEDI126_ejemplos_paralelo_y_alternativas_con_una_accion_mas(self):
        """REQ-EDT-02, REQ-ACT-01: en el ejemplo «paralelo», una acción en la etapa B (con la C a 140 de ella) desplaza C, su
        transición y E a la derecha, sin solapes y en una sola operación de deshacer; la acción queda unida a B y el grafcet
        valida igual. Lo mismo en «alternativas»: una acción en la E1 aparta la transición t5 y lo que hay a su derecha."""
        from escritorio.diagrama import ACT_LINK, H
        w = self.w
        self.proyecto_fixture("paralelo")
        w.a_ejecutar.setChecked(False)
        self.assertTrue(w.cambiar_modo("editar"))
        e = w.edicion
        e.pedir_accion = lambda sid, aid: None
        e.nueva_variable("Q00", "output")
        antes, diag0 = posiciones_modelo(e), [str(d) for d in e.ed.validate().diagnostics]
        pila = len(e.ed.undo_stack)
        self.assertIsNone(e.poner_accion("B", {"tipo": "continua", "variable": "Q00"}))
        despues = posiciones_modelo(e)
        movidos = {i for i in antes if despues[i] != antes[i]}
        self.assertEqual(movidos, {"C", "t3", "E"}, "la rama de la derecha")
        saltos = {despues[i][0] - antes[i][0] for i in movidos}
        self.assertEqual(len(saltos), 1, "todos lo mismo: se conservan las posiciones relativas")
        self.assertTrue(0 < saltos.pop() < 100)
        self.assertTrue(all(despues[i][1] == antes[i][1] for i in antes), "solo a la derecha")
        self.assertEqual(len(e.ed.undo_stack), pila + 1, "una sola operación")
        self.assertEqual(e.ed.get("B")["actionRefs"], [e.ed.get("B")["actionRefs"][0]])
        caja = next(c for c in w.diagrama.cajas_acciones if c["etapa"] == "B")
        self.assertAlmostEqual(caja["rect"][0], despues["B"][0] + 100 + H + ACT_LINK, delta=0.01)
        self.assertEqual(self._solapes_de_acciones(e), [])
        self.assertEqual([str(d) for d in e.ed.validate().diagnostics], diag0)
        self.assertTrue(e.ed.validate().can_simulate)
        e.deshacer()
        self.assertEqual((posiciones_modelo(e), e.ed.get("B")["actionRefs"]), (antes, []))
        e.rehacer()
        self.assertEqual(posiciones_modelo(e), despues)
        # la otra rama, la D: su vecina E también se aparta
        self.assertIsNone(e.poner_accion("D", {"tipo": "continua", "variable": "Q00"}))
        self.assertEqual(self._solapes_de_acciones(e), [])
        self.assertTrue(e.ed.validate().can_simulate)
        e.ed.dirty = False  # (sin preguntar por lo no guardado)
        # «alternativas»: la E1 ya tiene una acción; con otra, t5 (a 180 de ella) se aparta con t6, que está debajo a su derecha
        self.proyecto_fixture("alternativas")
        w.a_ejecutar.setChecked(False)
        self.assertTrue(w.cambiar_modo("editar"))
        e = w.edicion
        e.pedir_accion = lambda sid, aid: None
        e.nueva_variable("Q00", "output")
        antes = posiciones_modelo(e)
        self.assertIsNone(e.poner_accion("E1", {"tipo": "continua", "variable": "Q00"}))
        despues = posiciones_modelo(e)
        self.assertEqual({i for i in antes if despues[i] != antes[i]}, {"t5", "t6"})
        self.assertEqual(self._solapes_de_acciones(e), [])
        self.assertEqual(e.mensaje, "")
        e.deshacer()
        self.assertEqual(posiciones_modelo(e), antes)

    def test_SEDI127_sin_poder_apartar_la_accion_se_queda_encima_con_un_aviso(self):
        """REQ-EDT-02, REQ-ACT-01: si no se puede abrir hueco a la derecha (el obstáculo está debajo de la etapa, o pide más
        del tope), la acción se añade igualmente, encima de lo que haya, sin error ni desplazamientos a medias, con un
        aviso suave (mensaje que no es un error y la etapa parpadea en naranja)."""
        from escritorio import edicion as modulo
        w = self.w
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        # Mantener un solape real con el trazo de transición más corto: paro OR paro conserva su valor.
        e.poner_condicion(ts["t2"], "paro OR paro")
        # 1. en columna, la segunda acción llega al texto de t2, debajo de la etapa: no hay a dónde apartarlo
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        e.colocar_acciones(s1, "columna")
        self.assertEqual((e.colocacion(s1), e.mensaje), ("columna", ""), "una sola cabe")
        e.ed.move(s2, 600, 220)  # la etapa 2 lejos
        e.cambia()
        pos0, pila, modelo_antes = posiciones_modelo(e), len(e.ed.undo_stack), copy.deepcopy(e.ed.model)
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q01"}))
        self.assertEqual(len(e.acciones(s1)), 2, "se añade igualmente")
        self.assertNotEqual(self._solapes_de_acciones(e), [], "y queda encima")
        self.assertEqual((posiciones_modelo(e), len(e.ed.undo_stack)), (pos0, pila + 1), "sin desplazamientos a medias")
        self.assertEqual(e.ed.redo_stack, [])
        self.assertEqual((e.mensaje, e.mensaje_info), (modulo.MSG_ENCIMA, True), "un aviso, no un error")
        self.assertEqual(e.parpadeo.ids, {s1}, "la etapa parpadea")
        self.assertTrue(e.ed.validate().can_simulate or len(e.ed.validate().diagnostics) > 0)
        e.deshacer()
        self.assertEqual((len(e.acciones(s1)), posiciones_modelo(e)), (1, pos0))
        self.assertEqual(e.ed.model, modelo_antes)
        # 2. más allá del tope: la etapa 2 estorba pero apartarla pide más de lo permitido
        e.colocar_acciones(s1, "fila")
        e.ed.move(s2, 220, 220)
        e.cambia()
        with mock.patch.object(modulo, "DESPLAZA_MAX", 10):
            pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
            self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q03"}))
            self.assertEqual(len(e.acciones(s1)), 2)
            self.assertEqual((posiciones_modelo(e), len(e.ed.undo_stack)), (pos0, pila + 1))
            self.assertEqual((e.mensaje, e.mensaje_info), (modulo.MSG_ENCIMA, True))
        # con el tope normal y editando la acción, se aparta (la edición recalcula)
        e.ed.move(s2, 220, 220)
        e.cambia()
        self.assertTrue(e._despejar(s1))
        self.assertEqual(self._solapes_de_acciones(e), [])

    def test_SEDI128_editar_una_accion_ya_colocada_aparta_lo_que_pisa(self):
        """REQ-EDT-02, REQ-ACT-01: cambiar la variable (de nombre largo), la condición o el tipo de una acción colocada, o la
        colocación elegida, la ensancha; lo que pisa se aparta hacia la derecha en la misma operación de deshacer, y la
        colocación elegida no cambia. Con el panel, solo al aplicar (no en cada pulsación)."""
        w = self.w
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        e.nueva_variable("VariableDeNombreMuyLargoParaEnsanchar", "output")
        e.nueva_variable("marcha2", "input")
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        aid = e.ed.get(s1)["actionRefs"][0]
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        # un cambio que no ensancha no mueve nada
        self.assertIsNone(e.cambiar_accion(aid, {**e.datos_accion(aid), "variable": "Q01"}))
        self.assertEqual(posiciones_modelo(e), pos0)
        # la variable de nombre largo la ensancha: se aparta la etapa 2, en la misma operación que el cambio
        pila = len(e.ed.undo_stack)
        self.assertIsNone(e.cambiar_accion(aid, {**e.datos_accion(aid), "variable": "VariableDeNombreMuyLargoParaEnsanchar"}))
        self.assertGreater(posiciones_modelo(e)[s2][0], 200)
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        self.assertEqual(self._solapes_de_acciones(e), [])
        self.assertEqual(e.mensaje, "")
        e.deshacer()
        self.assertEqual((posiciones_modelo(e), e.datos_accion(aid)["variable"]), (pos0, "Q01"))
        e.rehacer()
        self.assertGreater(posiciones_modelo(e)[s2][0], 200)
        # por el panel de opciones: el nombre se aplica al terminar (editingFinished), una sola vez
        e.deshacer()
        w.editar_accion(s1, aid)
        panel = w.props.accion
        pila = len(e.ed.undo_stack)
        panel.variable.setCurrentText("VariableDeNombreMuyLargoParaEnsanchar")
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        self.assertEqual((posiciones_modelo(e)[s2][0] > 200, self._solapes_de_acciones(e)), (True, []))
        e.deshacer()
        # el texto de una condición escrita a medias no mueve nada; la condición larga, sí
        self.assertIsNone(e.cambiar_accion(aid, {**e.datos_accion(aid), "variable": "Q00"}))
        e.tipo_accion(aid, "condicionada")
        aid = e.acciones(s1)[0]["id"]
        pos0 = posiciones_modelo(e)
        self.assertIsNone(e.poner_texto_accion(aid, "condicion", "marcha2"))
        e.deshacer()
        self.assertEqual(posiciones_modelo(e), pos0)
        self.assertIsNone(e.poner_texto_accion(aid, "condicion", "marcha2 AND VariableDeNombreMuyLargoParaEnsanchar"))
        aid = e.acciones(s1)[0]["id"]
        self.assertGreater(posiciones_modelo(e)[s2][0], 200)
        self.assertEqual(self._solapes_de_acciones(e), [])
        # la colocación elegida a mano: «en fila, separadas» ocupa más; se aparta lo que pisa y la colocación queda elegida
        e.ed.dirty = False  # (sin preguntar por lo no guardado)
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        e.ed.move(s2, 260, 220)
        e.cambia()
        for n in ("Q00", "Q01"):
            self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": n}))
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        self.assertEqual(pos0[s2], (260, 220), "dos en fila caben")
        e.colocar_acciones(s1, "fila-separada")
        self.assertEqual((e.colocacion(s1), len(e.ed.undo_stack)), ("fila-separada", pila + 1))
        self.assertGreater(posiciones_modelo(e)[s2][0], 260)
        self.assertEqual((self._solapes_de_acciones(e), e.mensaje), ([], ""))
        e.deshacer()  # la colocación y el desplazamiento vuelven juntos
        self.assertEqual((e.colocacion(s1), posiciones_modelo(e)), ("fila", pos0))
        e.rehacer()
        self.assertEqual(e.colocacion(s1), "fila-separada")

    def test_SEDI129_apartar_mueve_barras_acciones_sueltas_y_vias_de_enlaces(self):
        """REQ-EDT-02, REQ-ACT-01: al apartar lo que estorba, lo que queda a la derecha del primer obstáculo se mueve con sus
        posiciones relativas: las barras de simultaneidad que empiezan a su derecha, las acciones sueltas y la vía de un
        enlace con recorrido propio; una barra que cruza el corte se ensancha lo mismo. Lo de la izquierda no se mueve."""
        w = self.w
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        # una barra que cruza (empieza a la izquierda de la etapa 2 y acaba a su derecha), otra que empieza a su derecha, una
        # acción suelta a su derecha, una a su izquierda y la vía de un enlace
        cruza = e.ed.add_bar("Y", (100, 500), 400)
        derecha = e.ed.add_bar("O", (400, 540), 100)
        izquierda = e.ed.add_bar("Y", (-60, 580), 100)
        e.cambia()
        e.ed.set_link_style("via|a|post", {"route": {"laneX": "500", "exitY": "300", "entryY": "400"}})
        e.ed.set_link_style("via|b|post", {"route": {"laneX": "20", "exitY": "300", "entryY": "400"}})
        sd = e.poner_accion_suelta(QPointF(100 + 700, 500))
        si = e.poner_accion_suelta(QPointF(100 + 0, 700))
        antes = {b["id"]: (b["x"], b["ancho"]) for b in e.ed.bars()}
        xs = {i: e._borrador(i)["x"] for i in (sd, si)}
        pila = len(e.ed.undo_stack)
        for n in ("Q00", "Q01"):
            self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": n}))
        d = posiciones_modelo(e)[s2][0] - 200
        self.assertGreater(d, 0)
        despues = {b["id"]: (b["x"], b["ancho"]) for b in e.ed.bars()}
        from fractions import Fraction as F
        self.assertEqual(F(despues[cruza][0]), F(antes[cruza][0]), "la que cruza empieza donde estaba")
        self.assertEqual(F(despues[cruza][1]), F(antes[cruza][1]) + d, "y acaba lo mismo más a la derecha")
        self.assertEqual(F(despues[derecha][0]), F(antes[derecha][0]) + d)
        self.assertEqual(despues[derecha][1], antes[derecha][1])
        self.assertEqual(despues[izquierda], antes[izquierda])
        self.assertEqual(F(e._borrador(sd)["x"]), F(xs[sd]) + d, "la suelta de la derecha se mueve")
        self.assertEqual(e._borrador(si)["x"], xs[si], "la de la izquierda, no")
        estilos = e.ed.link_styles()
        self.assertEqual((float(estilos["via|a|post"]["route"]["laneX"]), float(estilos["via|b|post"]["route"]["laneX"])),
                         (500 + d, 20))
        self.assertEqual(estilos["via|a|post"]["route"]["exitY"], "300")
        e.deshacer()  # lo de la última acción, de una vez
        e.deshacer()
        self.assertEqual(len(e.ed.undo_stack), pila)
        self.assertEqual({b["id"]: (b["x"], b["ancho"]) for b in e.ed.bars()}, antes)
        self.assertEqual((e._borrador(sd)["x"], e.ed.link_styles()["via|a|post"]["route"]["laneX"]), (xs[sd], "500"))
        e.rehacer()
        e.rehacer()
        self.assertEqual(float(e.ed.link_styles()["via|a|post"]["route"]["laneX"]), 500 + d)
        self.assertEqual(self._solapes_de_acciones(e), [])
        # guardar y abrir
        destino = Path(self.tmp.name) / "apartado2"
        e.guardar(destino)
        pres = open_model(destino).presentations[0]
        self.assertEqual(layout_from_presentation(pres)[s2], (200 + d, 220))
        self.assertEqual({b["id"]: (b["x"], b["ancho"]) for b in pres["barras"]}, despues)


    # -- el despeje de las acciones de una etapa, caso por caso (P-IMP-48) -------------------------------------------
    def _rects(self, sid=None):
        """Las esquinas (x, y) de las cajas de acción dibujadas, ordenadas; las de una etapa, o las de todas."""
        return sorted((round(c["rect"][0], 1), round(c["rect"][1], 1)) for c in self.w.diagrama.cajas_acciones
                      if sid is None or c["etapa"] == sid)

    def _poner_etapa(self, e, sid, x, y=220):
        """Pone la etapa `sid` en (x, y) del modelo sin pasar por el despeje."""
        e.ed.move(sid, x, y)
        e.cambia()

    def test_SEDI130_el_corte_no_parte_una_columna(self):
        """REQ-EDT-02, REQ-ACT-01: si lo que estorba es una transición de una columna, se mueve la columna entera (etapas y
        transiciones con el mismo x) y no solo esa transición: el corte y la referencia de cada elemento son el mismo centro
        x. Cada acción, con su desplazamiento, es una sola operación de deshacer; lo que no está en la columna no se mueve."""
        e, ids, ts = self.secuencial()
        e.pedir_accion = lambda sid, aid: None
        for n in ("Q00", "Q01"):
            e.nueva_variable(n, "output")
        s1 = ids["1"]

        def enlace(a, b):
            from escritorio.diagrama import anclas
            pa = next(x for x in anclas(e.M, a) if x["lado"] == "abajo")["pos"]
            pb = next(x for x in anclas(e.M, b) if x["lado"] == "arriba")["pos"]
            e.herramienta = "seleccionar"
            e.prensar(pa)
            e.mover(pb)
            e.soltar(pb)
        antes = set(posiciones_modelo(e))
        e.colocar("etapa", QPointF(100 + 180, 140))
        e.colocar("transicion", QPointF(100 + 180, 220))
        e.colocar("etapa", QPointF(100 + 180, 300))
        columna = [i for i in posiciones_modelo(e) if i not in antes]
        a, t, b = sorted(columna, key=lambda i: posiciones_modelo(e)[i][1])
        enlace(a, t)
        enlace(t, b)
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        self.assertEqual({pos0[i][0] for i in columna}, {180})
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        self.assertEqual(posiciones_modelo(e), pos0, "una acción cabe: no se mueve nada")
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q01"}))  # la segunda llega a la transición
        pos1 = posiciones_modelo(e)
        self.assertEqual(len({pos1[i][0] - pos0[i][0] for i in columna}), 1, "las tres, lo mismo")
        self.assertGreater(pos1[t][0], 180)
        self.assertEqual({i: p for i, p in pos1.items() if i not in columna}, {i: p for i, p in pos0.items() if i not in columna})
        self.assertTrue(all(pos1[i][1] == pos0[i][1] for i in columna))
        self.assertEqual(len(e.ed.undo_stack), pila + 2)
        self.assertEqual((self._solapes_de_acciones(e), e.mensaje), ([], ""))
        e.deshacer()
        self.assertEqual(posiciones_modelo(e), pos0)

    def test_SEDI131_una_barra_de_alternativa_tambien_se_aparta(self):
        """REQ-EDT-02, REQ-ACT-01: una barra «O» (se dibuja sin grosor) cuenta como obstáculo, con un alto mínimo: si las
        acciones de una etapa llegan a ella, se aparta en la misma operación; nunca queda tapada en silencio. Sin ese alto
        mínimo la barra pasaría inadvertida (el defecto)."""
        from escritorio import edicion as modulo
        e, ids, ts = self.secuencial()
        e.pedir_accion = lambda sid, aid: None
        for n in ("Q00", "Q01"):
            e.nueva_variable(n, "output")
        s1 = ids["1"]
        o = e.ed.add_bar("O", (120, 220), 200)
        e.cambia()
        x0 = next(b["x"] for b in e.ed.bars() if b["id"] == o)
        pila = len(e.ed.undo_stack)
        with mock.patch.object(modulo, "BARRA_ALTO_MIN", 0):  # sin el alto mínimo: la barra no estorba
            for n in ("Q00", "Q01"):
                self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": n}))
            self.assertEqual(next(b["x"] for b in e.ed.bars() if b["id"] == o), x0)
            self.assertEqual(e.mensaje, "", "tapada y sin aviso")
        e.deshacer()
        e.deshacer()
        self.assertEqual((len(e.ed.undo_stack), len(e.acciones(s1))), (pila, 0))
        for n in ("Q00", "Q01"):
            self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": n}))
        derecha = max(c["rect"][0] + c["rect"][2] for c in self.w.diagrama.cajas_acciones)
        izquierda = float(next(b["x"] for b in e.ed.bars() if b["id"] == o)) + 100  # (x del dibujo)
        self.assertGreaterEqual(izquierda, derecha + modulo.MARGEN_SOLAPE)
        self.assertEqual((len(e.ed.undo_stack), e.mensaje), (pila + 2, ""))
        e.deshacer()
        e.deshacer()
        self.assertEqual(next(b["x"] for b in e.ed.bars() if b["id"] == o), x0, "la barra vuelve con las acciones")

    def test_SEDI132_separar_acciones_no_mueve_nada_y_la_primera_accion_si_despeja(self):
        """REQ-EDT-02, REQ-ACT-01: «Eliminar el enlace» y «Separar» dejan cada acción donde estaba y no mueven ninguna otra
        cosa del dibujo (las acciones sueltas nuevas, aunque queden sin hueco entre sí, no se apartan); añadir la primera
        acción a una etapa que no tenía ninguna sí aparta lo que estorba. Cada gesto, una operación de deshacer."""
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        # la primera acción de una etapa sin acciones, con la etapa 2 muy cerca
        self._poner_etapa(e, s2, 140)
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        self.assertGreater(posiciones_modelo(e)[s2][0], 140)
        self.assertEqual((len(e.ed.undo_stack), self._solapes_de_acciones(e)), (pila + 1, []))
        e.deshacer()
        self.assertEqual(posiciones_modelo(e), pos0)
        # tres acciones en fila y la etapa 2 muy a la derecha
        self._poner_etapa(e, s2, 700)
        for n in ("Q00", "Q01", "Q02"):
            self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": n}))
        pos0, pila, cajas0 = posiciones_modelo(e), len(e.ed.undo_stack), self._rects()
        self.assertEqual((pos0[s2], len(cajas0)), ((700, 220), 3))
        e.eliminar_enlace_acciones(s1)
        self.assertEqual(self._rects(), cajas0, "cada una, donde estaba")
        self.assertEqual(posiciones_modelo(e), pos0, "y la etapa de la derecha, sin moverse")
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        self.assertEqual((len(e.acciones(s1)), len([b for b in e.ed.draft_actions() if not b.get("etapa")])), (0, 3))
        e.deshacer()
        self.assertEqual((self._rects(), posiciones_modelo(e), len(e.acciones(s1))), (cajas0, pos0, 3))
        # separar una sola (la del medio): las otras dos no se mueven; la separada queda a la derecha de la fila
        aid = e.ed.get(s1)["actionRefs"][1]
        e.separar_accion(aid)
        self.assertEqual((posiciones_modelo(e), len(e.ed.undo_stack), len(e.acciones(s1))), (pos0, pila + 1, 2))
        sueltas = [c for c in self.w.diagrama.cajas_acciones if not c["etapa"]]
        self.assertEqual(len(sueltas), 1)
        self.assertGreater(sueltas[0]["rect"][0], max(x for x, _ in cajas0))
        self.assertEqual((self._solapes_de_acciones(e), e.mensaje), ([], ""))
        e.deshacer()
        self.assertEqual((posiciones_modelo(e), len(e.acciones(s1))), (pos0, 3))

    def test_SEDI133_pegar_una_accion_a_una_etapa_aparta_lo_que_estorba(self):
        """REQ-EDT-02, REQ-ACT-01: pegar una acción suelta a una etapa sigue la misma política que añadirla: si cabe, no se
        mueve nada; si no, se desplaza lo que estorba (en la misma operación de deshacer); si no se puede, queda con un
        aviso y sin desplazamientos a medias."""
        from escritorio import edicion as modulo
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        aid = e.ed.get(s1)["actionRefs"][0]
        d = e.poner_accion_suelta(QPointF(900, 500))
        # 1. cabe: la etapa 2 está lejos
        self._poner_etapa(e, s2, 700)
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        e.pegar([d], aid)
        self.assertEqual((e._borrador(d).get("etapa"), posiciones_modelo(e), len(e.ed.undo_stack)), (s1, pos0, pila + 1))
        e.deshacer()
        # 2. no cabe: se aparta
        self._poner_etapa(e, s2, 200)
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        e.pegar([d], aid)
        self.assertEqual(e._borrador(d).get("etapa"), s1)
        self.assertGreater(posiciones_modelo(e)[s2][0], 200)
        self.assertEqual(len(e.ed.undo_stack), pila + 1, "pegar y desplazar, una sola operación")
        self.assertEqual((self._solapes_de_acciones(e), e.mensaje), ([], ""))
        e.deshacer()
        self.assertEqual(posiciones_modelo(e), pos0)
        self.assertIsNone(e._borrador(d).get("etapa"))
        # 3. no se puede: queda encima con el aviso
        with mock.patch.object(modulo, "DESPLAZA_MAX", 10):
            e.pegar([d], aid)
            self.assertEqual((e._borrador(d).get("etapa"), posiciones_modelo(e)), (s1, pos0))
            self.assertEqual((e.mensaje, e.mensaje_info, len(e.ed.undo_stack)), (modulo.MSG_ENCIMA, True, pila + 1))
            self.assertEqual(e.parpadeo.ids, {s1})

    def test_SEDI134_cambiar_el_tipo_de_una_accion_aparta_lo_que_estorba(self):
        """REQ-ACT-01, REQ-EDT-02: cambiar el tipo de una acción colocada a otro que se dibuja más ancho («al activar», con
        su marca) aparta lo que pisa, en la misma operación; un cambio que no ensancha no mueve nada."""
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        self._poner_etapa(e, s2, 158)  # la caja de 80 llega a 228; la etapa 2 empieza a 236 (con el margen): cabe justo
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        e.tipo_accion(e.acciones(s1)[0]["id"], "condicionada")  # sin condición, mide lo mismo
        self.assertEqual(posiciones_modelo(e), pos0)
        pila = len(e.ed.undo_stack)
        e.tipo_accion(e.acciones(s1)[0]["id"], "activacion")  # unos píxeles más ancha
        self.assertGreater(posiciones_modelo(e)[s2][0], 158)
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        self.assertEqual((self._solapes_de_acciones(e), e.mensaje), ([], ""))
        e.deshacer()
        self.assertEqual((posiciones_modelo(e), e.datos_accion(e.acciones(s1)[0]["id"])["tipo"]), (pos0, "condicionada"))

    def test_SEDI135_mover_una_accion_de_orden_aparta_lo_que_estorba(self):
        """REQ-ACT-01, REQ-EDT-02: subir o bajar una acción en la etapa (en una matriz de 2, cuyas columnas toman el ancho de
        su acción más ancha) puede ensanchar el conjunto: lo que pisa se aparta en la misma operación. Si no ensancha, no se
        mueve nada."""
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        largo = "VariableDeNombreMuyLargoParaEnsanchar"
        e.nueva_variable(largo, "output")
        e.ed.move(ts["t2"], 0, 600)  # la matriz ocupa dos filas: la transición de debajo, lejos
        e.cambia()
        for n in (largo, "Q01", largo, "Q02"):
            self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": n}))
        e.colocar_acciones(s1, "matriz-2")
        refs = list(e.ed.get(s1)["actionRefs"])
        self.assertEqual(len(refs), 4)
        derecha = max(c["rect"][0] + c["rect"][2] for c in self.w.diagrama.cajas_acciones)
        self._poner_etapa(e, s2, derecha + 8 + 22 - 100)  # la etapa 2, justo al margen del conjunto
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        self.assertEqual(self._solapes_de_acciones(e), [])
        e.mover_accion(refs[2], -1)  # [L, Q01, L, Q02] -> [L, L, Q01, Q02]: la 2.ª columna pasa a ser tan ancha como L
        self.assertEqual(e.ed.get(s1)["actionRefs"], [refs[0], refs[2], refs[1], refs[3]])
        self.assertGreater(posiciones_modelo(e)[s2][0], pos0[s2][0])
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        self.assertEqual((self._solapes_de_acciones(e), e.mensaje), ([], ""))
        e.deshacer()
        self.assertEqual((posiciones_modelo(e), e.ed.get(s1)["actionRefs"]), (pos0, refs))
        e.rehacer()
        pos1 = posiciones_modelo(e)
        e.mover_accion(refs[1], +1)  # [L, L, Q01, Q02] -> [L, L, Q02, Q01]: las columnas miden lo mismo
        self.assertEqual((e.ed.get(s1)["actionRefs"][2], posiciones_modelo(e), e.mensaje), (refs[3], pos1, ""))

    def test_SEDI136_renombrar_una_variable_que_ensancha_una_accion_aparta_lo_que_estorba(self):
        """REQ-ACT-01, REQ-EDT-02, REQ-EDT-09: renombrar una variable con un nombre más largo ensancha las acciones que la
        usan: lo que pisa se aparta, junto con el cambio de nombre y en una sola operación de deshacer; un nombre igual de
        corto no mueve nada."""
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        self._poner_etapa(e, s2, 160)
        pos0 = posiciones_modelo(e)
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Q00")
        self.assertIsNone(e.cambiar_variable(vid, "Q10"))
        self.assertEqual(posiciones_modelo(e), pos0)
        pila = len(e.ed.undo_stack)
        self.assertIsNone(e.cambiar_variable(vid, "VariableDeNombreMuyLargoParaEnsanchar"))
        self.assertGreater(posiciones_modelo(e)[s2][0], 160)
        self.assertEqual(len(e.ed.undo_stack), pila + 1)
        self.assertEqual((self._solapes_de_acciones(e), e.mensaje), ([], ""))
        e.deshacer()
        self.assertEqual((posiciones_modelo(e), next(v["name"] for v in e.ed.model["variables"] if v["id"] == vid)),
                         (pos0, "Q10"))

    def test_SEDI137_sin_hueco_tras_desplazar_se_revierte_el_desplazamiento(self):
        """REQ-EDT-02, REQ-ACT-01: si tras desplazar sigue habiendo algo que estorba (aquí, forzado), lo desplazado se
        deshace: queda solo la edición (una operación en la pila), la pila de rehacer vacía, las posiciones como estaban,
        el aviso y la etapa que parpadea."""
        from escritorio import edicion as modulo
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)
        real, vistos = e._choques, []

        def terco(clave, disposicion):  # el primer resultado, siempre: como si lo desplazado no bastara
            if not vistos:
                vistos.extend(real(clave, disposicion))
            return list(vistos)
        e._choques = terco
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q01"}))
        self.assertTrue(vistos, "había con qué chocar")
        self.assertEqual(posiciones_modelo(e), pos0, "ningún desplazamiento a medias")
        self.assertEqual(len(e.ed.undo_stack), pila + 1, "solo la edición")
        self.assertEqual(e.ed.redo_stack, [])
        self.assertEqual(len(e.acciones(s1)), 2)
        self.assertEqual(e._encima, [s1])
        self.assertEqual((e.mensaje, e.mensaje_info), (modulo.MSG_ENCIMA, True))
        self.assertEqual(e.parpadeo.ids, {s1})
        e.deshacer()
        self.assertEqual((posiciones_modelo(e), len(e.acciones(s1))), (pos0, 1))

    def test_SEDI138_la_pila_de_rehacer_queda_como_estaba_si_algo_se_deshace(self):
        """REQ-EDT-02: una operación atómica que falla con un rehacer pendiente (aunque haga varias operaciones antes de
        fallar) y un despeje que no consigue hueco dejan la pila de rehacer exactamente como estaba: rehacer sigue
        rehaciendo lo mismo y no queda ningún «mover» ajeno."""
        from grafcet.diagnostics import Diagnostic
        e, ids, ts, s2 = self._captura1()
        s1 = ids["1"]
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        e.nueva_variable("Q09", "output")
        e.deshacer()  # queda un rehacer pendiente (la variable)
        rehacer = list(e.ed.redo_stack)
        self.assertEqual(len(rehacer), 1)
        pos0, pila = posiciones_modelo(e), len(e.ed.undo_stack)

        def dos_y_falla():
            e.ed.move(s2, 400, 220)
            e.ed.move(s2, 420, 220)
            raise DiagnosticError(Diagnostic("D-FORMATO", "falla a propósito"))
        motivo = e._atomico("falla", dos_y_falla)
        self.assertIn("falla a propósito", motivo)
        self.assertEqual(e.ed.redo_stack, rehacer, "idéntica, sin ningún «mover» ajeno")
        self.assertEqual((posiciones_modelo(e), len(e.ed.undo_stack)), (pos0, pila))
        e.rehacer()  # y rehace lo mismo de antes
        self.assertEqual(next(v["name"] for v in e.ed.model["variables"] if v["name"] == "Q09"), "Q09")
        e.deshacer()
        # el despeje que no consigue hueco, llamado directamente con un rehacer pendiente
        self._poner_etapa(e, s2, 150)  # pisa la caja de la acción
        e.nueva_variable("Q08", "output")
        e.deshacer()
        rehacer = list(e.ed.redo_stack)
        self.assertEqual(len(rehacer), 1)
        real, vistos = e._choques, []

        def terco(clave, disposicion):
            if not vistos:
                vistos.extend(real(clave, disposicion))
            return list(vistos)
        e._choques = terco
        pos0 = posiciones_modelo(e)
        self.assertFalse(e._despejar(s1))
        self.assertTrue(vistos)
        self.assertEqual((posiciones_modelo(e), e.ed.redo_stack), (pos0, rehacer))

    # -- jerarquías en la interfaz (paso 6, encargo B1): macroetapas, encapsulantes y recintos ------------------------
    def vacio(self, nombres=True):
        """Un grafcet nuevo, sin cambios pendientes y con los diálogos sin bloquear: el de borrado confirma y el de nombre
        (con `nombres`) acepta el que se propone."""
        w = self.w
        if w.edicion is not None:
            w.edicion.ed.dirty = False  # (una segunda edición en la misma prueba: sin preguntar si se guarda)
        w.nuevo()
        e = w.edicion
        e.ed.dirty = False
        e.confirmar_borrado = lambda plan: True
        if nombres:
            e.pedir_texto = lambda titulo, etiqueta, actual: actual
        return w, e

    @staticmethod
    def estado(e):
        """Lo que deshacer y rehacer deben devolver tal cual: el modelo y la presentación."""
        return copy.deepcopy((e.ed.model, e.ed.presentation))

    @staticmethod
    def estructura(e):
        """Los diagnósticos de estructura (referencias, propiedad, ciclos, formato) del modelo, salvo que todavía no tenga
        etapas iniciales (el grafcet de estas pruebas no las lleva)."""
        return [(d.code, d.message) for d in e.ed.validate().diagnostics
                if d.code in ("D-REF", "D-PROPIETARIO", "D-FORMATO", "D-JERARQUIA-CICLO") and "sin etapas iniciales" not in d.message]

    @staticmethod
    def tipo_etapa_menu(opciones):
        """Las funciones del submenú «Tipo de etapa» de un menú del botón derecho, por texto."""
        return {t: f for t, f, *_ in dict(opciones)["Tipo de etapa"]}

    @staticmethod
    def sin_ids(texto):
        """Ningún ID interno (`s-…`, `g-…`, `m-…`, `x-…`, `r-…`) en un texto que se le muestra al usuario."""
        import re
        return re.search(r"\b[a-z]-[0-9a-f]{32}\b", texto) is None

    @staticmethod
    def recuadros(w):
        """Los recuadros discontinuos azules del dibujo (la selección de un parcial, el parcial donde caería una ficha)."""
        return [it for it in w.diagrama.scene().items() if hasattr(it, "pen") and it.pen().color().name() == "#1f6feb"
                and it.pen().style() == Qt.PenStyle.CustomDashLine]

    def test_SEDI170_fichas_macroetapa_y_encapsulante_con_su_dibujo_y_su_ayuda(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05: la paleta ofrece «Macroetapa» y «Encapsulante» tras las demás fichas; su icono
        y la figura que se lleva al arrastrar reproducen el símbolo del diagrama (divisiones horizontales arriba y abajo;
        esquinas cortadas); un clic en la ficha muestra su ayuda y arrastrarla lleva su clave."""
        from escritorio import diagrama, propiedades
        w, e = self.vacio()
        pa = w.paleta
        fichas = {pa.item(i).data(Qt.ItemDataRole.UserRole): pa.item(i) for i in range(pa.count())}
        for clave in ("macroetapa", "encapsulante"):
            self.assertEqual(pa.mimeData([fichas[clave]]).text(), clave)
            self.assertEqual(fichas[clave].text(), propiedades.NOMBRES[clave])
        self.assertEqual(pa.sizeHint().height(), pa.alto_filas(pa.FILAS))

        def imagen(h):
            return propiedades.figura(h)[0].toImage()

        def tinta(img,x,y):
            c=img.pixelColor(x,y)
            return c.alpha()>0 and c.name()!=diagrama.COL["panel"]
        etapa,macro,enc=imagen("etapa"),imagen("macroetapa"),imagen("encapsulante")
        arriba,abajo=29,59
        self.assertFalse(tinta(etapa,48,arriba) or tinta(etapa,48,abajo))
        self.assertTrue(all(tinta(macro,x,arriba) and tinta(macro,x,abajo) for x in (32,48,64)),
                        "dos divisiones horizontales, de lado a lado")
        esquinas=((29,29),(66,28),(29,59),(66,60))
        self.assertFalse(any(tinta(etapa,x,y) for x,y in esquinas))
        self.assertTrue(all(tinta(enc,x,y) for x,y in esquinas),"las cuatro esquinas cortadas")
        self.assertFalse(tinta(enc,48,arriba),"la encapsulante no lleva divisiones")
        # la figura que va pegada al puntero es lo mismo, a la escala del dibujo, y se coloca por su centro
        figuras = {h: propiedades.figura(h, 1.0, 1.0) for h in ("etapa", "macroetapa", "encapsulante")}
        self.assertEqual(len({bytes(pm.toImage().constBits()) for pm, _ in figuras.values()}), 3)
        for pm, punto in figuras.values():
            self.assertTrue(pm.rect().contains(punto))
            self.assertEqual(punto, figuras["etapa"][1])
        # un clic en la ficha solo muestra su ayuda
        n = len(e.ed.undo_stack)
        for fila, clave in ((14, "macroetapa"), (13, "encapsulante")):
            pa.itemClicked.emit(pa.item(fila))
            self.assertEqual((e.mensaje, e.mensaje_info, w.ayuda.text()),
                             (propiedades.AYUDAS[clave], True, propiedades.AYUDAS[clave]))
        self.assertEqual(len(e.ed.undo_stack), n)
        self.assertIn("Encuadrar la expansión", propiedades.AYUDAS["macroetapa"])
        self.assertNotIn("Abrir expansión", propiedades.AYUDAS["macroetapa"])
        self.assertIn("Añadir recinto", propiedades.AYUDAS["encapsulante"])

    def test_SEDI171_soltar_la_ficha_macroetapa_crea_la_macroetapa_con_su_expansion(self):
        """REQ-EDT-02, REQ-JER-04, REQ-MOD-07, REQ-EDT-05: soltar «Macroetapa» crea la macroetapa en el punto, con su
        expansión (un parcial nuevo dentro del raíz con su entrada y su salida) a la derecha, en una sola operación de
        deshacer; si esa columna está ocupada la corre a la derecha; encima de otro elemento no se coloca."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        n = len(e.ed.undo_stack)
        self.soltar_ficha("macroetapa", QPointF(260, 220))
        m = e.ed.model
        (mac,) = m["hierarchy"]["macros"]
        (exp,) = m["hierarchy"]["expansions"]
        xp = next(p for p in m["partials"] if p["id"] == exp["partialRef"])
        self.assertEqual((mac["label"], mac["partialRef"], exp["ownerMacroRef"]), ("M1", "g", mac["id"]))
        self.assertEqual((xp["label"], xp["ownerRef"], sorted(xp["stepRefs"])),
                         ("M1", "g", sorted([exp["entryRef"], exp["exitRef"]])))
        self.assertEqual({s["id"]: (s["label"], s["kind"], s["partialRef"]) for s in m["steps"]},
                         {exp["entryRef"]: ("E1", "entry", xp["id"]), exp["exitRef"]: ("S1", "exit", xp["id"])})
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación de deshacer")
        lay = posiciones_modelo(e)
        self.assertEqual((lay[mac["id"]], lay[exp["entryRef"]], lay[exp["exitRef"]]),
                         ((160.0, 220.0), (440.0, 220.0), (440.0, 540.0)),
                         "la entrada a la altura de la macroetapa, la salida más abajo, las dos a su derecha")
        self.assertEqual(e.sel, [mac["id"]])
        self.assertTrue(e.mensaje_info and "M1" in e.mensaje and self.sin_ids(e.mensaje))
        self.assertEqual([(x["id"], x["entry"], x["exit"]) for x in e.M["macros"]],
                         [(mac["id"], exp["entryRef"], exp["exitRef"])])
        self.assertEqual([(p["kind"], p["label"]) for p in e.M["partials"]], [("expansion", "M1")])
        self.assertEqual(self.estructura(e), [])
        despues = self.estado(e)
        e.deshacer()
        self.assertEqual((e.ed.model["hierarchy"]["macros"], e.ed.model["steps"], [p["id"] for p in e.ed.model["partials"]]),
                         ([], [], ["g"]))
        e.rehacer()
        self.assertEqual(self.estado(e), despues)
        # su columna ocupada por la expansión anterior: la segunda se coloca más a la derecha, sin tocar la zona de la primera
        self.soltar_ficha("macroetapa", QPointF(260, 400))
        m2 = e.ed.model["hierarchy"]["macros"][1]
        x2 = e.ed.macro_info(m2["id"])
        self.assertEqual((m2["label"], posiciones_modelo(e)[x2.entry]), ("M2", (600.0, 400.0)))
        a, b = (cajas_parciales(e.M)[p] for p in (exp["partialRef"], x2.partial))
        self.assertTrue(a["x1"] < b["x0"] or b["x1"] < a["x0"], "las dos zonas no se tocan")
        # encima de otro elemento no se coloca
        n = len(e.ed.undo_stack)
        self.soltar_ficha("macroetapa", centro(e.M, mac["id"]))
        self.assertEqual((len(e.ed.undo_stack), e.mensaje, len(e.ed.model["hierarchy"]["macros"])),
                         (n, "No se puede poner encima de otro elemento", 2))

    def test_SEDI172_lo_soltado_en_el_marco_de_la_expansion_es_de_su_parcial(self):
        """REQ-JER-04, REQ-MOD-07, REQ-EDT-02: lo que se suelta dentro de la zona de una expansión (etapa, encapsulante,
        transición) es de su parcial; fuera de todo marco, del raíz. Lo que nace de una etapa o de una transición (arrastrar
        de su punto de unión, «Añadir debajo») es del parcial de ésta, y mover un elemento a otro marco es solo de
        presentación: no cambia su parcial (el marco se ajusta a las etapas que son suyas)."""
        from escritorio.diagrama import anclas, cajas_parciales
        w, e = self.vacio()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        b = cajas_parciales(e.M)[x.partial]
        self.assertEqual((b["x0"], b["x1"], b["y0"], b["y1"]), (492.0, 632.0, 176.0, 584.0))
        self.assertEqual((e.parcial_en(QPointF(540, 380)), e.parcial_en(QPointF(260, 380)), e.parcial_en(QPointF(700, 380))),
                         (x.partial, "g", "g"))
        # «Añadir debajo» de la entrada: la transición y la etapa son de la expansión
        e.sel = [x.entry]
        nueva = e.anadir_debajo()
        debajo = next(t for t in e.ed.model["transitions"] if x.entry in t["preRefs"])
        self.assertEqual((e.parcial_de(debajo["id"]), e.parcial_de(nueva)), (x.partial, x.partial))
        # soltar: una etapa, una transición y una encapsulante dentro; otra etapa fuera, en el raíz
        self.soltar_ficha("etapa", QPointF(610, 340))
        k = e.sel[0]
        self.soltar_ficha("transicion", QPointF(610, 420))
        t = e.sel[0]
        self.soltar_ficha("encapsulante", QPointF(610, 500))
        h = e.sel[0]
        self.soltar_ficha("etapa", QPointF(260, 60))
        fuera = e.sel[0]
        self.assertEqual([e.parcial_de(i) for i in (k, t, h, fuera)], [x.partial] * 3 + ["g"])
        self.assertEqual(next(s for s in e.ed.model["steps"] if s["id"] == h)["kind"], "enclosing")
        pr = next(p for p in e.ed.model["partials"] if p["id"] == x.partial)
        self.assertEqual((sorted(pr["stepRefs"]), sorted(pr["transitionRefs"])),
                         (sorted([x.entry, x.exit, nueva, k, h]), sorted([debajo["id"], t])))
        self.assertEqual(next(p for p in e.ed.model["partials"] if p["id"] == "g")["stepRefs"], [fuera])
        # del punto de unión a un hueco: lo que nace es del parcial de la etapa o transición, aunque el hueco caiga fuera
        origen = next(a for a in anclas(e.M, x.exit) if a["lado"] == "abajo")
        e.crear_desde(origen, QPointF(700, 640))
        self.assertEqual(e.parcial_de(e.sel[0]), x.partial)
        origen = next(a for a in anclas(e.M, e.sel[0]) if a["lado"] == "abajo")
        e.crear_desde(origen, QPointF(700, 800))  # de una transición, una etapa
        self.assertEqual(e.parcial_de(e.sel[0]), x.partial)
        # mover es solo presentación: la etapa del raíz arrastrada al marco sigue siendo del raíz...
        destino = QPointF(620, 740)
        e.prensar(centro(e.M, fuera))
        e.mover(destino)
        e.soltar(destino)
        self.assertEqual((e.parcial_de(fuera), e.parcial_en(centro(e.M, fuera))), ("g", x.partial))
        self.assertIn(fuera, [s["id"] for s in e.M["steps"] if s["partial"] is None], "el dibujo la sigue llevando en el raíz")
        # ... y la salida, arrastrada lejos, sigue siendo de la expansión (cuyo marco la sigue)
        e.prensar(centro(e.M, x.exit))
        e.mover(QPointF(1000, 900))
        e.soltar(QPointF(1000, 900))
        self.assertEqual((e.parcial_de(x.exit), e.parcial_en(centro(e.M, x.exit))), (x.partial, x.partial))
        self.assertEqual([m for _, m in self.estructura(e) if "transición sin etapas" not in m], [],
                         "(la transición suelta de la prueba no se enlaza: eso sí lo avisa)")

    def test_SEDI173_una_macroetapa_soltada_en_una_expansion_o_un_recinto_queda_anidada(self):
        """REQ-JER-04, REQ-MOD-07: una macroetapa soltada dentro de la zona de otra expansión, o en el marco de un recinto, es de
        ese parcial y su expansión cuelga de él (regla 8.1 C: un parcial dentro de otro solo como expansión de una macroetapa
        de éste, o como recinto de una encapsulante)."""
        w, e = self.vacio()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        self.soltar_ficha("macroetapa", QPointF(540, 380))
        interior = e.sel[0]
        xi = e.ed.macro_info(interior)
        m = e.ed.model
        self.assertEqual(next(p for p in m["hierarchy"]["macros"] if p["id"] == interior)["partialRef"], x.partial)
        self.assertEqual(next(p for p in m["partials"] if p["id"] == xi.partial)["ownerRef"], x.partial)
        self.assertEqual(next(p for p in m["partials"] if p["id"] == x.partial)["ownerRef"], "g")
        self.assertEqual(self.estructura(e), [])
        self.assertEqual(e.ed.partial_roles()[xi.partial]["parent"], x.partial)
        self.assertEqual([mm["label"] for mm in m["hierarchy"]["macros"]], ["M1", "M2"])
        # en el marco de un recinto: la macroetapa es del recinto y su expansión cuelga de él
        self.soltar_ficha("encapsulante", QPointF(260, 900))
        r = e.anadir_recinto(e.sel[0])
        b = next(p for p in e.M["partials"] if p["id"] == r)
        e.colocar("macroetapa", QPointF(b["x"] + 100 + 90, b["y"] + 60))
        anidada = e.sel[0]
        self.assertEqual(e.parcial_de(anidada), r)
        self.assertEqual(e.ed.partial_roles()[e.ed.macro_info(anidada).partial]["parent"], r)
        self.assertEqual(self.estructura(e), [])
        e.deshacer()
        self.assertNotIn(anidada, [mm["id"] for mm in e.ed.model["hierarchy"]["macros"]])
        self.assertIn(r, [p["id"] for p in e.ed.model["partials"]])

    def test_SEDI174_recinto_vacio_se_ve_se_selecciona_y_se_rellena_arrastrando(self):
        """REQ-JER-05, REQ-MOD-07, REQ-EDT-02, REQ-EDT-05, REQ-EDT-09: «Añadir recinto…» pide el nombre y crea el recinto de la
        encapsulante; vacío se ve como un marco mínimo (con su nombre y el de la encapsulante), se selecciona con un clic en su
        borde o su nombre y se rellena soltando etapas dentro (que pasan a su parcial); todo se deshace y se rehace; el
        diálogo del nombre es el de la ventana y se puede sustituir."""
        from escritorio.diagrama import cajas_parciales, elemento_en
        w, e = self.vacio(nombres=False)
        # el diálogo de nombre es el de la ventana (QInputDialog) y un nombre cancelado devuelve None
        with mock.patch("escritorio.ventana.QInputDialog.getText", return_value=("Z", True)) as g:
            self.assertEqual(e.pedir_texto("Título", "Rótulo", "propuesta"), "Z")
            self.assertEqual(g.call_args.args[1:3], ("Título", "Rótulo"))
            self.assertEqual(g.call_args.kwargs, {"text": "propuesta"})
        with mock.patch("escritorio.ventana.QInputDialog.getText", return_value=("", False)):
            self.assertIsNone(e.pedir_texto("Título", "Rótulo", "propuesta"))
        self.soltar_ficha("encapsulante", QPointF(260, 60))
        h = e.sel[0]
        preguntas = []

        def pedir(titulo, etiqueta, actual):
            preguntas.append((titulo, etiqueta, actual))
            return "Recinto A"
        e.pedir_texto = pedir
        n = len(e.ed.undo_stack)
        antes = self.estado(e)
        r = e.anadir_recinto(h)
        self.assertEqual(preguntas, [("Añadir recinto", "Nombre del recinto de la encapsulante 0:", "G1")])
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación de deshacer (recinto y posición del marco)")
        m = e.ed.model
        (rec,) = m["hierarchy"]["enclosures"]
        parte = next(p for p in m["partials"] if p["id"] == r)
        self.assertEqual((rec["ownerStepRef"], rec["partialRef"], rec["activationRefs"]), (h, r, []))
        self.assertEqual((parte["label"], parte["ownerRef"], parte["stepRefs"]), ("Recinto A", "g", []))
        self.assertEqual((e.sel, e.nombre(r), self.sin_ids(e.mensaje), e.mensaje_info), ([r], "recinto Recinto A", True, True))
        self.assertIn("Selección: recinto Recinto A", w.l_sel.text())
        # sin etapas, Vista no lo lleva: el editor lo anota para que se dibuje un marco vacío mínimo
        (p,) = e.M["partials"]
        self.assertEqual((p["kind"], p["vacio"], p["label"], p["ownerStep"]), ("enclosure", True, "Recinto A", h))
        caja = cajas_parciales(e.M)[r]
        self.assertEqual((caja["x1"] - caja["x0"], caja["y1"] - caja["y0"]), (180.0, 120.0))
        self.assertTrue(caja["x0"] > centro(e.M, h).x(), "a la derecha de su encapsulante")
        # se ve (con su nombre) y se selecciona con su borde o su nombre; dentro, no
        textos = [it.toPlainText() for it in w.diagrama.scene().items() if hasattr(it, "toPlainText")]
        self.assertIn("Recinto A", textos)
        self.assertEqual(elemento_en(e.M, QPointF(caja["x0"], caja["y0"] + 50)), r)
        self.assertEqual(elemento_en(e.M, QPointF(caja["x0"] + 40, caja["y1"] + 4)), r, "su nombre")
        centro_marco = QPointF((caja["x0"] + caja["x1"]) / 2, (caja["y0"] + caja["y1"]) / 2)
        self.assertIsNone(elemento_en(e.M, centro_marco))
        e.seleccionar([])
        e.prensar(QPointF(caja["x1"], caja["y0"] + 50))
        e.soltar(QPointF(caja["x1"], caja["y0"] + 50))
        self.assertEqual(e.sel, [r])
        self.assertTrue(self.recuadros(w), "el recinto seleccionado se remarca")
        e.seleccionar([])
        self.assertEqual(([t for t, _ in e.menu(QPointF(caja["x0"], caja["y0"] + 50))], e.sel), (["Encuadrar la encapsulante"], [r]),
                         "el botón derecho lo selecciona")
        # se rellena soltando etapas dentro de su marco: son del recinto, y el marco pasa a ser el de sus etapas
        self.assertEqual(e.parcial_en(centro_marco), r)
        self.soltar_ficha("etapa", centro_marco)
        i = e.sel[0]
        self.assertEqual(e.parcial_de(i), r)
        self.assertNotIn("vacio", [p for p in e.M["partials"] if p["id"] == r][0], "ya tiene etapas: lo dibuja Vista")
        # (con etapas, el marco es el de ellas: una segunda cabe a su derecha, dentro del margen; después se arrastra)
        self.soltar_ficha("etapa", QPointF(centro(e.M, i).x() + 70, centro(e.M, i).y()))
        j = e.sel[0]
        self.assertEqual((e.parcial_de(j), e.ed.partial_roles()[r]["kind"]), (r, "enclosure"))
        self.assertEqual(next(p for p in e.ed.model["partials"] if p["id"] == r)["stepRefs"], [i, j])
        # deshacer y rehacer: las dos etapas, el recinto y su marco vacío
        listo = self.estado(e)
        for _ in range(3):
            e.deshacer()
        self.assertEqual((self.estado(e), e.M["partials"]), (antes, []))
        for _ in range(3):
            e.rehacer()
        self.assertEqual(self.estado(e), listo)
        # cancelar el nombre no hace nada; uno repetido o vacío se rechaza con aviso y parpadeo, sin cambiar nada
        n, antes2 = len(e.ed.undo_stack), self.estado(e)
        e.pedir_texto = lambda *a: None
        self.assertIsNone(e.anadir_recinto(h))
        self.assertEqual((len(e.ed.undo_stack), self.estado(e)), (n, antes2))
        for malo in ("Recinto A", "  ", "g"):
            e.pedir_texto = lambda *a, malo=malo: malo
            e.parpadeo.parar()
            self.assertIsNone(e.anadir_recinto(h))
            self.assertEqual((len(e.ed.undo_stack), self.estado(e)), (n, antes2))
            self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje), e.mensaje)
            self.assertEqual(e.parpadeo.ids, {h})
        e.parpadeo.parar()
        # un segundo recinto de la misma encapsulante: otro marco, a su lado
        e.pedir_texto = lambda *a: "Recinto B"
        r2 = e.anadir_recinto(h)
        c1, c2 = (cajas_parciales(e.M)[p] for p in (r, r2))
        self.assertTrue(c1["x1"] < c2["x0"] or c2["x1"] < c1["x0"], "los marcos no se montan")
        self.assertEqual([x["ownerStepRef"] for x in e.ed.model["hierarchy"]["enclosures"]], [h, h])
        # una encapsulante inicial con un recinto sin etapa inicial: el diagnóstico señala la encapsulante, con nombres
        e.tipo_etapa(h, True)
        d = next(d for d in e.diagnosticos() if d["code"] == "D-JERARQUIA-INICIAL")
        self.assertEqual(d["target"], h)
        self.assertTrue(self.sin_ids(d["message"]), d["message"])

    def test_SEDI175_convertir_en_encapsulante_y_volver_a_etapa_ordinaria(self):
        """REQ-JER-05, REQ-EDT-09: el botón derecho en una etapa ofrece «Tipo de etapa» (Etapa, Encapsulante,
        Macroetapa); en una encapsulante, «Añadir recinto…»; la entrada y la salida de una expansión no ofrecen el
        submenú. Lo que el núcleo rechaza se muestra en rojo y con parpadeo, sin cambiar nada."""
        w, e = self.vacio()
        self.soltar_ficha("etapa", QPointF(260, 60))
        s = e.sel[0]

        def tipo():
            return next(x for x in e.ed.model["steps"] if x["id"] == s)["kind"]
        opciones = e.menu(centro(e.M, s))
        self.assertEqual([t for t, _ in opciones], ["Colocación de las acciones", "-", "Tipo de etapa"])
        n = len(e.ed.undo_stack)
        self.tipo_etapa_menu(opciones)["Encapsulante"]()
        self.assertEqual((tipo(), len(e.ed.undo_stack)), ("enclosing", n + 1))
        self.assertTrue(e.mensaje_info and self.sin_ids(e.mensaje))
        self.assertEqual([x["kind"] for x in e.M["steps"]], ["enclosing"], "el dibujo recibe el tipo")
        opciones = e.menu(centro(e.M, s))
        self.assertEqual([t for t, _ in opciones][1:], ["-", "Tipo de etapa", "Añadir recinto…"])
        # con un recinto ya no se ofrece volver a ordinaria; si se fuerza, el núcleo lo rechaza y no cambia nada
        e.anadir_recinto(s)
        self.assertEqual([t for t, _ in e.menu(centro(e.M, s))][1:],
                         ["-", "Tipo de etapa", "Añadir recinto…", "Encuadrar el recinto", "Forzar un parcial…"])
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.parpadeo.parar()
        e.tipo_encapsulante(s, False)
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje) and "recinto" in e.mensaje, e.mensaje)
        self.assertEqual(e.parpadeo.ids, {s})
        e.parpadeo.parar()
        # sin recintos, vuelve a ser una etapa ordinaria; deshacer y rehacer
        e.deshacer()
        self.assertEqual(e.ed.model["hierarchy"]["enclosures"], [])
        self.tipo_etapa_menu(e.menu(centro(e.M, s)))["Etapa"]()
        self.assertEqual(tipo(), "ordinary")
        e.deshacer()
        self.assertEqual(tipo(), "enclosing")
        e.rehacer()
        self.assertEqual(tipo(), "ordinary")
        # la entrada y la salida de una expansión no cambian de tipo, y el botón derecho no lo ofrece
        mid = e.poner_macro(QPointF(260, 400))
        x = e.ed.macro_info(mid)
        self.assertEqual([t for t, _ in e.menu(centro(e.M, x.entry))],
                         ["Colocación de las acciones", "-", "Encuadrar la macroetapa", "Forzar un parcial…"])
        antes = self.estado(e)
        e.tipo_encapsulante(x.exit, True)
        self.assertEqual(self.estado(e), antes)
        self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje))

    def test_SEDI176_enlace_de_activacion_como_casilla_marcada_o_desmarcada(self):
        """REQ-JER-05: el botón derecho en una etapa de un recinto ofrece «Enlace de activación» como casilla (marcada si lo
        tiene, sin marcar si no) que se alterna con una operación de deshacer y se dibuja con «*»; una etapa fuera de un
        recinto no lo ofrece y, si se fuerza, el núcleo lo rechaza."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        self.soltar_ficha("encapsulante", QPointF(260, 60))
        h = e.sel[0]
        r = e.anadir_recinto(h)
        caja = cajas_parciales(e.M)[r]
        self.soltar_ficha("etapa", QPointF((caja["x0"] + caja["x1"]) / 2, (caja["y0"] + caja["y1"]) / 2))
        i = e.sel[0]

        def marcas():
            return e.ed.model["hierarchy"]["enclosures"][0]["activationRefs"]

        def casilla():
            menu = w.diagrama.menu_contextual(e.menu(centro(e.M, i)))
            return next(a for a in menu.actions() if a.text() == "Enlace de activación")
        # sin marcar: una casilla sin marcar
        self.assertIn("Enlace de activación", dict(e.menu(centro(e.M, i))))
        self.assertEqual(("Enlace de activación" in e.menu_marcadas, "Enlace de activación" in e.menu_desmarcadas), (False, True))
        a = casilla()
        self.assertEqual((a.isCheckable(), a.isChecked()), (True, False))
        n = len(e.ed.undo_stack)
        a.trigger()  # como lo haría el usuario con el menú
        self.assertEqual((marcas(), len(e.ed.undo_stack)), ([i], n + 1))
        self.assertTrue(next(s for s in e.M["steps"] if s["id"] == i)["activation"])
        textos = [it.toPlainText() for it in w.diagrama.scene().items() if hasattr(it, "toPlainText")]
        self.assertIn("*", textos, "el «*» del enlace de activación")
        # marcada: una casilla marcada; al pulsarla otra vez, se quita
        a = casilla()
        self.assertEqual(("Enlace de activación" in e.menu_marcadas, "Enlace de activación" in e.menu_desmarcadas), (True, False))
        self.assertEqual((a.isCheckable(), a.isChecked()), (True, True))
        a.trigger()
        self.assertEqual(marcas(), [])
        self.assertFalse(next(s for s in e.M["steps"] if s["id"] == i)["activation"])
        e.deshacer()
        self.assertEqual(marcas(), [i])
        e.rehacer()
        self.assertEqual(marcas(), [])
        e.deshacer()
        e.deshacer()
        self.assertEqual(marcas(), [])
        # fuera de un recinto: no se ofrece; si se fuerza, el núcleo lo rechaza (aviso en rojo, parpadeo, nada cambia)
        self.assertNotIn("Enlace de activación", dict(e.menu(centro(e.M, h))))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.enlace_activacion(h)
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje) and e.parpadeo.ids == {h}, e.mensaje)
        e.parpadeo.parar()

    def test_SEDI177_encuadrar_la_expansion_lleva_la_vista_y_la_resalta_sin_tocar_el_modelo(self):
        """REQ-EDT-08, REQ-JER-07: «Encuadrar la expansión» en una macroetapa encaja en la vista la zona de su expansión y la
        resalta (selecciona su parcial: recuadro discontinuo) sin tocar el modelo, la presentación ni el historial; «Renombrar…»
        cambia el nombre de la macroetapa y el de su expansión en una sola operación de deshacer."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        opciones = e.menu(centro(e.M, mid))
        self.assertEqual([t for t, _ in opciones], ["Tipo de etapa", "Encuadrar la expansión", "Renombrar…"])
        self.assertEqual(e.sel, [mid])
        encuadrados = []
        w.diagrama.encuadrar = lambda r: encuadrados.append(r)
        antes, n, rev = self.estado(e), len(e.ed.undo_stack), e.ed.revision
        dict(opciones)["Encuadrar la expansión"]()
        b = cajas_parciales(e.M)[x.partial]
        (r,) = encuadrados
        self.assertTrue(r.contains(QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"])), "toda la zona de la expansión")
        self.assertEqual((e.sel, e.nombre(x.partial), len(e.ed.undo_stack), e.ed.revision, self.estado(e)),
                         ([x.partial], "expansión de M1", n, rev, antes))
        self.assertEqual(e.parpadeo.ids, {x.partial}, "parpadea para aparecer en primer plano")
        e.parpadeo.parar()
        self.assertTrue(e.mensaje_info and "M1" in e.mensaje and self.sin_ids(e.mensaje))
        self.assertIn("Selección: expansión de M1", w.l_sel.text())
        self.assertTrue([it for it in self.recuadros(w) if hasattr(it, "rect") and abs(it.rect().x() - (b["x0"] - 6)) < 1],
                        "su zona, recuadrada")
        # renombrar: pide el nombre con el actual de propuesta y cambia la macroetapa y su expansión
        preguntas = []
        e.pedir_texto = lambda *a: preguntas.append(a) or "Lavado"
        self.assertEqual(e.renombrar_macro(mid), "Lavado")
        self.assertEqual(preguntas, [("Renombrar la macroetapa", "Nuevo nombre de la macroetapa M1:", "M1")])
        m = e.ed.model
        self.assertEqual(([mm["label"] for mm in m["hierarchy"]["macros"]], next(p["label"] for p in m["partials"] if p["id"] == x.partial)),
                         (["Lavado"], "Lavado"))
        self.assertEqual(e.nombres[mid], "Lavado")
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        hecho = self.estado(e)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        e.rehacer()
        self.assertEqual(self.estado(e), hecho)
        # cancelar o dejar el mismo nombre no hace nada; un nombre repetido se rechaza sin dejar nada a medias
        self.soltar_ficha("macroetapa", QPointF(260, 700))
        otra = e.sel[0]
        self.assertEqual(e.nombres[otra], "M1")
        n = len(e.ed.undo_stack)
        for texto in (None, "M1"):
            e.pedir_texto = lambda *a, texto=texto: texto
            self.assertIsNone(e.renombrar_macro(otra))
            self.assertEqual(len(e.ed.undo_stack), n)
        e.pedir_texto = lambda *a: "Lavado"
        antes = self.estado(e)
        e.parpadeo.parar()
        self.assertIsNone(e.renombrar_macro(otra))
        self.assertEqual((self.estado(e), e.parpadeo.ids), (antes, {otra}))
        self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje), e.mensaje)
        e.parpadeo.parar()

    def test_SEDI178_borrar_solo_la_entrada_o_la_salida_avisa_y_no_cambia_nada(self):
        """REQ-EDT-05, REQ-EDT-09, REQ-JER-04: borrar solo la entrada o la salida de una expansión (el núcleo lo rechaza con
        D-REF) muestra el aviso en rojo con nombres y hace parpadear la etapa, sin dejar el estado a medias (ni siquiera lo
        que se borraba junto a ella); borrar la macroetapa entera pregunta con nombres y se deshace de una vez."""
        from PySide6.QtWidgets import QMessageBox
        w, e = self.vacio()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        barra = e.poner_barra(QPointF(700, 100), "Y")
        antes, n, rehacer = self.estado(e), len(e.ed.undo_stack), list(e.ed.redo_stack)
        for sel in ([x.entry], [x.exit], [barra, x.entry]):
            e.parpadeo.parar()
            e.sel = list(sel)
            self.assertFalse(e.borrar())
            self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.ed.redo_stack), (antes, n, rehacer), sel)
            self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje), e.mensaje)
            self.assertIn("macroetapa", e.mensaje)
            self.assertEqual(e.parpadeo.ids, set(sel) - {barra}, "la etapa que no se puede borrar parpadea")
        self.assertEqual(w.ayuda.text(), e.mensaje)
        self.assertEqual(w.ayuda.styleSheet().count("#c62828"), 1, "en rojo")
        e.parpadeo.parar()
        # la macroetapa entera: pregunta (con nombres) y se lleva su expansión; Ctrl+Z lo devuelve todo
        e.confirmar_borrado = lambda plan: False
        e.sel = [mid]
        self.assertFalse(e.borrar())
        self.assertEqual(self.estado(e), antes)
        textos = []
        e.confirmar_borrado = w._confirmar_borrado
        with mock.patch("escritorio.ventana.QMessageBox.question",
                        side_effect=lambda *a: textos.append(a[2]) or QMessageBox.StandardButton.Yes):
            self.assertTrue(e.borrar())
        e.confirmar_borrado = lambda plan: True
        self.assertTrue(self.sin_ids(textos[0]), textos[0])
        self.assertIn("Se borrará: M1.", textos[0])
        self.assertTrue("E1" in textos[0] and "S1" in textos[0], textos[0])
        self.assertEqual(textos[0].count("expansión de M1"), 1, "sin repetir lo que se llama igual")
        m = e.ed.model
        self.assertEqual((m["hierarchy"], [p["id"] for p in m["partials"]], m["steps"]),
                         ({"macros": [], "expansions": [], "enclosures": []}, ["g"], []))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        e.rehacer()
        self.assertEqual(e.ed.model["steps"], [])
        e.deshacer()
        # un recinto vacío seleccionado por su marco se borra como cualquier elemento (y se deshace)
        self.soltar_ficha("encapsulante", QPointF(260, 700))
        r = e.anadir_recinto(e.sel[0])
        listo = self.estado(e)
        e.sel = [r]
        self.assertTrue(e.borrar())
        self.assertEqual((e.ed.model["hierarchy"]["enclosures"], r in [p["id"] for p in e.ed.model["partials"]],
                          [p for p in e.M["partials"] if p.get("vacio")]), ([], False, []))
        self.assertNotIn(r, e.sel)
        e.deshacer()
        self.assertEqual(self.estado(e), listo)

    def test_SEDI179_deshacer_y_rehacer_de_toda_la_jerarquia_y_guardar_y_abrir(self):
        """REQ-EDT-05, REQ-DAT-01, REQ-MOD-07: macroetapa, contenido de su expansión, encapsulante, recinto, sus etapas, enlace de
        activación y renombrado se deshacen y rehacen paso a paso devolviendo el modelo y la presentación tal cual; guardado y
        abierto, la jerarquía se conserva y el recinto vacío sigue en su sitio."""
        from escritorio.diagrama import cajas_parciales
        from escritorio.edicion import Edicion
        w, e = self.vacio()
        pasos = []

        def paso(accion):
            accion()
            pasos.append(self.estado(e))
        paso(lambda: e.colocar("macroetapa", QPointF(260, 220)))
        mid = e.sel[0]
        paso(lambda: e.colocar("etapa", QPointF(540, 380)))
        paso(lambda: e.colocar("encapsulante", QPointF(260, 620)))
        h = e.sel[0]
        e.pedir_texto = lambda *a: "Recinto"
        paso(lambda: e.anadir_recinto(h))
        r = e.sel[0]
        c = cajas_parciales(e.M)[r]
        paso(lambda: e.colocar("etapa", QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2)))
        i = e.sel[0]
        paso(lambda: e.enlace_activacion(i))
        e.pedir_texto = lambda *a: "Lavado"
        paso(lambda: e.renombrar_macro(mid))
        self.assertEqual(len(pasos), 7)
        self.assertEqual(len({str(p) for p in pasos}), 7, "cada paso cambia algo")
        for k in range(len(pasos) - 1, 0, -1):  # hacia atrás, paso a paso
            e.deshacer()
            self.assertEqual(self.estado(e), pasos[k - 1], f"deshacer el paso {k}")
        e.deshacer()
        self.assertEqual((e.ed.model["steps"], e.ed.model["hierarchy"]["macros"], e.ed.undo_stack), ([], [], []))
        for k in range(len(pasos)):  # y hacia delante
            e.rehacer()
            self.assertEqual(self.estado(e), pasos[k], f"rehacer el paso {k}")
        self.assertFalse(e.ed.redo_stack)
        # guardar y abrir: la jerarquía y la posición del marco
        destino = Path(self.tmp.name) / "jerarquia"
        e.guardar(destino)
        op = open_model(destino)
        e2 = Edicion.desde(op.doc, {}, "abierto", destino, op.presentations[0])
        self.assertEqual(e2.ed.model["hierarchy"], e.ed.model["hierarchy"])
        self.assertEqual(cajas_parciales(e2.M)[r], cajas_parciales(e.M)[r])
        self.assertEqual({p["id"]: p["label"] for p in e2.M["partials"]}, {p["id"]: p["label"] for p in e.M["partials"]})
        self.assertEqual(e2.nombres[mid], "Lavado")
        self.assertEqual([p for p in e2.ed.model["hierarchy"]["enclosures"]][0]["activationRefs"], [i])
        # un recinto vacío: su marco sobrevive al guardado
        e.pedir_texto = lambda *a: "Vacío"
        r2 = e.anadir_recinto(h)
        e.guardar(destino)
        op = open_model(destino)
        e3 = Edicion.desde(op.doc, {}, "abierto", destino, op.presentations[0])
        self.assertEqual((cajas_parciales(e3.M)[r2], [p["vacio"] for p in e3.M["partials"] if p["id"] == r2]),
                         (cajas_parciales(e.M)[r2], [True]))

    def test_SEDI180_la_ficha_que_se_arrastra_recuadra_el_parcial_donde_caeria(self):
        """REQ-EDT-02, REQ-JER-04: al arrastrar una etapa, una encapsulante, una macroetapa o una transición sobre el marco de
        un parcial (también sobre la zona de una expansión, que no se dibuja) se recuadra el parcial donde caería; fuera de todo
        marco (el raíz), con la simultaneidad o con la acción, no; al soltar o salir se quita."""
        from PySide6.QtGui import QDragLeaveEvent
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        b = cajas_parciales(e.M)[x.partial]
        dentro, fuera = QPointF(540, 380), QPointF(260, 60)
        for ficha in ("etapa", "encapsulante", "macroetapa", "transicion"):
            self.assertTrue(e.sobrevolar(ficha, dentro))
            self.assertIsNotNone(w.diagrama.destino, ficha)
            r = w.diagrama.destino.rect()
            self.assertEqual((r.x(), r.y(), r.width(), r.height()),
                             (b["x0"] - 4, b["y0"] - 4, b["x1"] - b["x0"] + 8, b["y1"] - b["y0"] + 8))
            e.sobrevolar(ficha, fuera)
            self.assertIsNone(w.diagrama.destino, ficha)
        for ficha in ("simultaneidad", "accion:continua"):
            e.sobrevolar(ficha, dentro)
            self.assertIsNone(w.diagrama.destino, ficha)
        self.assertFalse(e.sobrevolar("etapa", QPointF(540, 220)), "encima de la entrada no se puede soltar")
        self.assertIsNone(w.diagrama.destino, "y no se recuadra")
        e.sobrevolar("etapa", dentro)
        self.assertIsNotNone(w.diagrama.destino)
        self.soltar_ficha("etapa", dentro)  # al soltar se quita
        self.assertIsNone(w.diagrama.destino)
        self.assertEqual(e.parcial_de(e.sel[0]), x.partial)
        e.sobrevolar("etapa", QPointF(540, 480))
        self.assertIsNotNone(w.diagrama.destino)
        w.diagrama.dragLeaveEvent(QDragLeaveEvent())  # al salir se quita
        self.assertIsNone(w.diagrama.destino)

    def test_SEDI181_marcos_de_los_parciales_como_los_dibuja_el_banco(self):
        """REQ-JER-04, REQ-JER-07: el rectángulo de cada parcial que entrega el dibujo (y con el que el editor decide dónde cae lo
        que se suelta) es el marco de las figuras de la norma, ampliado hasta rodear todo lo que se dibuja del parcial (retornos, textos
        y acciones): el recinto y el parcial de los ejemplos, y la zona de la expansión; tools/dibujo.js usa la misma cuenta. Un
        recinto vacío solo lo anota el editor: Vista (banco, comparador, simulador) no lo lleva, y dibujo.js no sabe de ellos."""
        from escritorio.diagrama import cajas_parciales, elemento_en
        from escritorio.edicion import Edicion
        from grafcet.examples import EJEMPLOS
        from grafcet.view import Vista
        esperado = {"encapsulacion": {"R": (475.0, 772.0, 26.0, 274.0)}, "macroetapa": {"X": (471.0, 684.0, 56.0, 464.0)},
                    "forzado": {"G": (484.0, 672.0, 0.0, 496.0)}}
        for clave, cajas in esperado.items():
            titulo, _, construir = EJEMPLOS[clave]
            m, layout = construir()
            e = Edicion.desde(m.doc, layout, titulo)
            self.assertEqual({p: (b["x0"], b["x1"], b["y0"], b["y1"]) for p, b in cajas_parciales(e.M).items()}, cajas, clave)
            self.assertFalse([p for p in e.M["partials"] if p.get("vacio")])
        # un parcial de los de siempre (marco redondeado) también se toca por su borde y recibe lo que se suelta dentro
        self.assertEqual((elemento_en(e.M, QPointF(484, 200)), e.parcial_en(QPointF(600, 300)), e.parcial_en(QPointF(300, 300))),
                         ("G", "G", e.raiz))
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        for cuenta in ("Math.min(...pts.map(p => p.x)) - H - 26", "Math.max(...pts.map(p => p.x)) + H + 70",
                       "Math.min(...pts.map(p => p.y)) - H - 22", "Math.max(...pts.map(p => p.y)) + H + 22"):
            self.assertIn(cuenta, js)
        self.assertNotIn("vacio", js, "el banco no sabe de marcos vacíos: solo los pone el editor")
        w, e = self.vacio()
        self.soltar_ficha("encapsulante", QPointF(260, 60))
        r = e.anadir_recinto(e.sel[0])
        self.assertEqual([p["id"] for p in e.M["partials"]], [r], "lo de Vista más lo que anota el editor")
        pura = Vista("x", "t", "", lambda: (e.ed.model, e.layout()), e.opciones)
        self.assertEqual(pura.model["partials"], [], "Vista no lleva el recinto vacío")

    def test_SEDI182_la_macroetapa_se_enlaza_como_una_etapa_y_lo_construido_simula(self):
        """REQ-JER-04, REQ-EDT-02, REQ-SIM-03: construida con los gestos del editor (ficha de macroetapa, «Añadir debajo»,
        etapas y transiciones soltadas en su expansión, enlaces), la macroetapa se comporta como la del ejemplo: la llegada
        activa su entrada y solo se sale de ella cuando su salida está activa."""
        from escritorio.diagrama import anclas
        w, e = self.vacio()
        e.colocar("etapa", QPointF(260, 60))
        a = e.sel[0]
        e.tipo_etapa(a, True)
        e.colocar("macroetapa", QPointF(260, 220))
        mid = e.sel[0]
        x = e.ed.macro_info(mid)

        def enlazar(origen, destino):
            pa = next(q for q in anclas(e.M, origen) if q["lado"] == "abajo")["pos"]
            pb = next(q for q in anclas(e.M, destino) if q["lado"] == "arriba")["pos"]
            e.prensar(pa)
            e.mover(pb)
            e.soltar(pb)
        e.colocar("transicion", QPointF(260, 140))
        t1 = e.sel[0]
        enlazar(a, t1)
        enlazar(t1, mid)
        e.sel = [mid]
        b = e.anadir_debajo()  # de una macroetapa: transición y etapa, en su parcial
        t2 = next(t for t in e.ed.model["transitions"] if mid in t["preRefs"])["id"]
        self.assertEqual((e.parcial_de(t2), e.parcial_de(b)), ("g", "g"))
        e.colocar("transicion", QPointF(540, 300))
        te = e.sel[0]
        e.colocar("etapa", QPointF(540, 380))
        k = e.sel[0]
        e.colocar("transicion", QPointF(540, 460))
        tk = e.sel[0]
        for origen, destino in ((x.entry, te), (te, k), (k, tk), (tk, x.exit)):
            enlazar(origen, destino)
        self.assertEqual([e.parcial_de(i) for i in (te, k, tk)], [x.partial] * 3)
        for tid, cond in ((t1, "p"), (t2, "s"), (te, "r"), (tk, "q")):
            e.poner_condicion(tid, cond, crear=True)
        self.assertEqual([d for d in e.diagnosticos() if d["blocks"]], [])
        self.assertTrue(e.ed.validate().can_simulate)
        ids = {v["name"]: v["id"] for v in e.ed.model["variables"]}
        v = e.vista

        def situacion():
            return sorted(e.nombres[i] for i in v.state()["situation"])

        def pulsar(nombre):
            v.act("fijar", {"cambios": {ids[nombre]: True}})
            v.act("fijar", {"cambios": {ids[nombre]: False}})
        self.assertEqual(situacion(), ["0"])
        pulsar("s")
        self.assertEqual(situacion(), ["0"], "sin la macroetapa activa, s no hace nada")
        pulsar("p")
        self.assertEqual(situacion(), ["E1"], "la llegada activa la entrada de la expansión")
        pulsar("s")
        self.assertEqual(situacion(), ["E1"], "aunque s valga 1, no se sale sin la salida activa")
        pulsar("r")
        self.assertEqual(situacion(), [e.nombres[k]])
        pulsar("q")
        self.assertEqual(situacion(), ["S1"])
        pulsar("s")
        self.assertEqual(situacion(), [e.nombres[b]])

    # -- jerarquías en la interfaz (paso 6, encargo B2): órdenes de forzado, panel de opciones y navegación ---------------
    @staticmethod
    def textos_dibujo(w):
        """Los textos que lleva el dibujo ahora."""
        return [it.toPlainText() for it in w.diagrama.scene().items() if hasattr(it, "toPlainText")]

    @staticmethod
    def centro_orden(w, fid):
        """El centro de la caja de una orden de forzado en el dibujo."""
        x, y, ancho, alto = next(c for c in w.diagrama.cajas_ordenes if c["id"] == fid)["rect"]
        return QPointF(x + ancho / 2, y + alto / 2)

    def con_recinto(self, nombre="R"):
        """Con gestos: una etapa H en el raíz y una encapsulante E0 con su recinto, que lleva las etapas A y B (con una
        transición entre las dos). Devuelve la ventana, la edición y los ID."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        e.colocar("etapa", QPointF(260, 60))
        h = e.sel[0]
        e.colocar("encapsulante", QPointF(260, 300))
        e0 = e.sel[0]
        e.pedir_texto = lambda *a: nombre
        r = e.anadir_recinto(e0)
        c = cajas_parciales(e.M)[r]
        e.colocar("etapa", QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
        a = e.sel[0]
        e.sel = [a]
        b = e.anadir_debajo()
        for sid, n in ((h, "H"), (e0, "E0"), (a, "A"), (b, "B")):
            self.assertIsNone(e.renombrar(sid, n))
        return w, e, {"h": h, "e0": e0, "r": r, "a": a, "b": b}

    def test_SEDI183_forzar_un_parcial_crea_la_orden_con_nombres_y_en_una_sola_operacion(self):
        """REQ-JER-02, REQ-JER-03, REQ-EDT-02, REQ-EDT-05, REQ-EDT-09: «Forzar un parcial…» en una etapa pide (gancho
        sustituible) el parcial destino, la forma y, si es explícita, las etapas, todo con nombres; crea la orden en una
        sola operación de deshacer y se dibuja «R{…}» en rectángulo doble; sin otro parcial no se ofrece; una orden que el
        núcleo rechaza (ciclo) o una explícita sin etapas dan el aviso en rojo con parpadeo y no cambian nada."""
        w, e = self.vacio()
        e.colocar("etapa", QPointF(260, 60))
        solo = e.sel[0]
        self.assertNotIn("Forzar un parcial…", dict(e.menu(centro(e.M, solo))), "sin otro parcial no hay a quién forzar")
        antes = self.estado(e)
        self.assertIsNone(e.forzar(solo))
        self.assertEqual(self.estado(e), antes)
        self.assertTrue(e.mensaje and not e.mensaje_info and "otro parcial" in e.mensaje)
        w, e, d = self.con_recinto()
        h, r, a, b = d["h"], d["r"], d["a"], d["b"]
        pedidas, respuesta = [], [None]
        e.pedir_forzado = lambda datos: pedidas.append(datos) or respuesta[0]
        opciones = e.menu(centro(e.M, h))
        self.assertEqual([t for t, _ in opciones][1:], ["-", "Tipo de etapa", "Forzar un parcial…"])
        # lo que se le enseña al diálogo: nombres (los ID solo para devolver la elección); cancelar no cambia nada
        antes, n = self.estado(e), len(e.ed.undo_stack)
        self.assertIsNone(dict(opciones)["Forzar un parcial…"]())
        datos = pedidas[-1]
        self.assertEqual((datos["origen"], datos["destinos"], datos["actual"]), ("H", [(r, "recinto R")], None))
        self.assertEqual(datos["etapas"], {r: [(a, "A"), (b, "B")]})
        self.assertEqual([t for _, t in datos["formas"]], ["Explícita", "La situación actual", "Vacía", "Inicial"])
        self.assertEqual([k for k, _ in datos["formas"]], ["explicit", "current", "empty", "initial"])
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        # explícita {B}: la orden, una sola operación, seleccionada, dibujada
        respuesta[0] = {"destino": r, "forma": "explicit", "etapas": [b]}
        fid = dict(e.menu(centro(e.M, h)))["Forzar un parcial…"]()
        (f,) = e.ed.model["forces"]
        self.assertEqual((f["id"], f["sourceStepRef"], f["targetPartialRef"], f["targetKind"], f["targetSteps"]),
                         (fid, h, r, "explicit", [b]))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertEqual((e.sel, e.mensaje_info, e.mensaje), ([fid], True, "Orden: H fuerza R a {B}."))
        self.assertEqual([(c["id"], c["etapa"]) for c in w.diagrama.cajas_ordenes], [(fid, h)])
        self.assertIn("R{B}", self.textos_dibujo(w))
        hecho = self.estado(e)
        e.deshacer()
        self.assertEqual((self.estado(e), w.diagrama.cajas_ordenes), (antes, []))
        e.rehacer()
        self.assertEqual(self.estado(e), hecho)
        # las otras tres formas (sin etapas, aunque el diálogo las devuelva); dos objetivos distintos para el mismo destino
        # no se rechazan: validate() avisa (D-FORZADO-CONFLICTO), y es un aviso, no un error
        for forma, texto, dibujo in (("current", "a la situación actual", "R{*}"), ("empty", "a la situación vacía", "R{ }"),
                                     ("initial", "a su situación inicial", "R{INIT}")):
            respuesta[0] = {"destino": r, "forma": forma, "etapas": ["no-se-usa"]}
            n = len(e.ed.undo_stack)
            nuevo = e.forzar(h)
            f = next(f for f in e.ed.model["forces"] if f["id"] == nuevo)
            self.assertEqual((f["targetKind"], "targetSteps" in f, len(e.ed.undo_stack)), (forma, False, n + 1))
            self.assertEqual(e.mensaje, f"Orden: H fuerza R {texto}.")
            self.assertIn(dibujo, self.textos_dibujo(w))
        conflicto = [x for x in e.diagnosticos() if x["code"] == "D-FORZADO-CONFLICTO"]
        self.assertTrue(conflicto and not conflicto[0]["blocks"] and self.sin_ids(conflicto[0]["message"]))
        # una explícita sin etapas, y un ciclo (A, del recinto, fuerza al raíz que H ya fuerza al recinto): rechazos
        antes, n = self.estado(e), len(e.ed.undo_stack)
        for caso, origen, motivo in (({"destino": r, "forma": "explicit", "etapas": []}, h, "al menos una etapa"),
                                     ({"destino": "g", "forma": "empty", "etapas": []}, a, "ciclo")):
            respuesta[0] = caso
            e.parpadeo.parar()
            self.assertIsNone(e.forzar(origen))
            self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
            self.assertTrue(e.mensaje and not e.mensaje_info and motivo in e.mensaje and self.sin_ids(e.mensaje), e.mensaje)
            self.assertEqual(e.parpadeo.ids, {origen})
        self.assertEqual([x for _, x in pedidas[-1]["destinos"]], ["g"], "el parcial de la propia etapa no se ofrece")
        e.parpadeo.parar()

    def test_SEDI184_la_caja_de_la_orden_se_selecciona_y_se_edita_o_se_quita_desde_su_menu(self):
        """REQ-JER-02, REQ-EDT-05: la caja «R{…}» de una orden se selecciona con un clic (no se arrastra: no es una acción) y
        su botón derecho ofrece «Editar orden de forzado…» (el mismo diálogo, con los valores actuales; `set_force`) y
        «Quitar orden de forzado» (`delete_force`), cada una en una sola operación de deshacer; Supr también la quita; no se
        coloca nada encima de ella."""
        w, e, d = self.con_recinto()
        h, r, a, b = d["h"], d["r"], d["a"], d["b"]
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "explicit", "etapas": [b]}
        fid = e.forzar(h)
        # un clic la selecciona y la resalta; arrastrarla no la mueve ni cambia nada
        antes = self.estado(e)
        e.seleccionar([])
        pc = self.centro_orden(w, fid)
        e.prensar(pc)
        self.assertEqual((e.sel, e.arrastre), ([fid], None))
        e.mover(QPointF(pc.x() + 300, pc.y() + 200))
        e.soltar(QPointF(pc.x() + 300, pc.y() + 200))
        self.assertEqual((e.sel, self.estado(e)), ([fid], antes))
        x0 = next(c for c in w.diagrama.cajas_ordenes if c["id"] == fid)["rect"][0]
        self.assertTrue([it for it in self.recuadros(w) if hasattr(it, "rect") and abs(it.rect().x() - (x0 - 3)) < 1],
                        "la caja seleccionada, recuadrada")
        self.assertEqual(w.props.pagina, "orden")
        # el menú de la caja (y no el de la etapa)
        opciones = e.menu(pc)
        self.assertEqual([t for t, _ in opciones],
                         ["Tipo de acción", "-", "Editar orden de forzado…", "Quitar orden de forzado"])
        self.assertNotIn("Editar orden de forzado…", dict(e.menu(centro(e.M, h))))
        # editar: el diálogo recibe los valores actuales; cambiar a «La situación actual»
        vistos = []
        respuesta = [{"destino": r, "forma": "current", "etapas": []}]
        e.pedir_forzado = lambda datos: vistos.append(datos) or respuesta[0]
        n = len(e.ed.undo_stack)
        self.assertEqual(dict(opciones)["Editar orden de forzado…"](), fid)
        self.assertEqual(vistos[0]["actual"], {"destino": r, "forma": "explicit", "etapas": [b]})
        self.assertEqual((vistos[0]["origen"], vistos[0]["destinos"]), ("H", [(r, "recinto R")]))
        (f,) = e.ed.model["forces"]
        self.assertEqual((f["id"], f["targetKind"], "targetSteps" in f, len(e.ed.undo_stack)), (fid, "current", False, n + 1))
        self.assertEqual(e.mensaje, "Orden: H fuerza R a la situación actual.")
        self.assertIn("R{*}", self.textos_dibujo(w))
        self.assertNotIn("R{B}", self.textos_dibujo(w))
        e.deshacer()
        self.assertEqual(e.ed.model["forces"][0]["targetSteps"], [b])
        e.rehacer()
        # editar a explícita con las dos etapas; cancelar no cambia nada; una explícita sin etapas se rechaza
        respuesta[0] = {"destino": r, "forma": "explicit", "etapas": [a, b]}
        e.editar_orden(fid)
        self.assertEqual((e.ed.model["forces"][0]["targetKind"], e.ed.model["forces"][0]["targetSteps"]), ("explicit", [a, b]))
        self.assertIn("R{A,B}", self.textos_dibujo(w))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        for caso in (None, {"destino": r, "forma": "explicit", "etapas": []}):
            respuesta[0] = caso
            e.parpadeo.parar()
            self.assertIsNone(e.editar_orden(fid))
            self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje))
        self.assertEqual(e.parpadeo.ids, {fid})
        e.parpadeo.parar()
        # quitar desde el menú de la caja, y se devuelve con Ctrl+Z
        pc = self.centro_orden(w, fid)
        n = len(e.ed.undo_stack)
        self.assertTrue(dict(e.menu(pc))["Quitar orden de forzado"]())
        self.assertEqual((e.ed.model["forces"], e.sel, len(e.ed.undo_stack), w.diagrama.cajas_ordenes), ([], [], n + 1, []))
        e.deshacer()
        self.assertEqual([f["id"] for f in e.ed.model["forces"]], [fid])
        # Supr, con la caja seleccionada, también la quita
        e.seleccionar([fid])
        self.assertTrue(e.borrar())
        self.assertEqual((e.ed.model["forces"], len(e.ed.undo_stack)), ([], n + 1))
        e.deshacer()
        # nada se coloca encima de su caja (se cuenta como un elemento más)
        n = len(e.ed.undo_stack)
        self.soltar_ficha("etapa", self.centro_orden(w, fid))
        self.assertEqual((len(e.ed.undo_stack), e.mensaje), (n, "No se puede poner encima de otro elemento"))

    def test_SEDI185_el_panel_de_opciones_muestra_la_ficha_de_jerarquia_con_los_botones_del_menu(self):
        """REQ-EDT-08, REQ-JER-07, REQ-EDT-09: al seleccionar una macroetapa, una encapsulante, una etapa de un recinto, la
        entrada de una expansión, un recinto (su marco), una expansión o una orden, el panel de opciones enseña su descripción
        con nombres y los mismos botones que el botón derecho (casillas incluidas), que hacen lo mismo; sin selección no hay
        ficha; los botones caben en el panel a 1366×768."""
        from PySide6.QtCore import QPoint
        w, e, d = self.con_recinto()
        h, e0, r, a, b = d["h"], d["e0"], d["r"], d["a"], d["b"]
        w._abrir_opciones()
        w.resize(1366, 768)
        w.show()
        QApplication.processEvents()
        mid = e.poner_macro(QPointF(260, 600))
        x = e.ed.macro_info(mid)
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "explicit", "etapas": [b]}
        fid = e.forzar(h)
        izq, der = w.props.ficha_izq, w.props.ficha_etapa

        def ver(ident, pagina, ficha, texto, botones):
            e.seleccionar([ident])
            QApplication.processEvents()
            self.assertEqual(w.props.pagina, pagina, ident)
            self.assertEqual((ficha.isHidden(), ficha.texto.text(), ficha.textos_visibles()), (False, texto, botones), ident)
            self.assertTrue(self.sin_ids(ficha.texto.text()))
            raiz = QRectF(w.props.rect())
            if pagina == "etapa":
                self.assertFalse(w.props.der.isVisible())
                opciones = {t:f for t,f,_ in e.acciones_jerarquia(ident)}
                for t in botones:self.assertIn(t,opciones)
                return
            for t in ficha.textos_visibles():  # los botones de jerarquías que siguen visibles caben en el panel
                bt = ficha.botones[t]
                self.assertTrue(raiz.contains(QRectF(bt.mapTo(w.props, QPoint(0, 0)), bt.size())), (ident, t))
        ver(mid, "macro", izq, "Macroetapa M1 · expansión M1 · entrada E1 · salida S1",
            ["Etapa", "Encapsulante", "Macroetapa", "Encuadrar la expansión", "Renombrar…"])
        self.assertIn("Macroetapa", w.props.titulo.text())  # (solo el tipo: el nombre ya se ve y se edita en su campo)
        ver(r, "marco", izq, "Recinto R de E0 · activación: ninguna", ["Encuadrar la encapsulante"])
        ver(fid, "orden", izq, "Orden: H fuerza R a {B}", ["Editar orden de forzado…", "Quitar orden de forzado"])
        ver(e0, "etapa", der, "Encapsulante E0 · recintos: R",
            ["Etapa", "Encapsulante", "Macroetapa", "Añadir recinto…", "Encuadrar el recinto", "Forzar un parcial…"])
        ver(x.entry, "etapa", der, "Entrada de la expansión de la macroetapa M1", ["Encuadrar la macroetapa", "Forzar un parcial…"])
        ver(a, "etapa", der, "Del recinto R de E0 · sin enlace de activación",
            ["Etapa", "Encapsulante", "Macroetapa", "Enlace de activación", "Encuadrar la encapsulante",
             "Forzar un parcial…"])
        ver(x.partial, "marco", izq, "Expansión de la macroetapa M1 · entrada E1 · salida S1", ["Encuadrar la macroetapa"])
        # los botones hacen lo que el menú: la casilla del enlace de activación, encuadrar, renombrar, editar y quitar
        e.seleccionar([a])
        casilla = der.botones["Enlace de activación"]
        self.assertEqual((casilla.isCheckable(), casilla.isChecked()), (True, False))
        n = len(e.ed.undo_stack)
        {t:f for t,f,_ in e.acciones_jerarquia(a)}["Enlace de activación"]()
        self.assertEqual((e.ed.model["hierarchy"]["enclosures"][0]["activationRefs"], len(e.ed.undo_stack)), ([a], n + 1))
        self.assertEqual((der.botones["Enlace de activación"].isChecked(), der.texto.text()),
                         (True, "Del recinto R de E0 · con enlace de activación"), "la casilla y el texto siguen al modelo")
        ver(r, "marco", izq, "Recinto R de E0 · activación: A", ["Encuadrar la encapsulante"])
        izq.botones["Encuadrar la encapsulante"].click()
        self.assertEqual(e.sel, [e0])
        encuadrados = []
        w.diagrama.encuadrar = lambda caja: encuadrados.append(caja)
        e.seleccionar([mid])
        izq.botones["Encuadrar la expansión"].click()
        self.assertEqual((e.sel, len(encuadrados)), ([x.partial], 1))
        e.parpadeo.parar()
        e.seleccionar([mid])
        e.pedir_texto = lambda *args: "Lavado"
        izq.botones["Renombrar…"].click()
        self.assertEqual(e.nombres[mid], "Lavado")
        self.assertEqual(izq.texto.text(), "Macroetapa Lavado · expansión Lavado · entrada E1 · salida S1")
        e.seleccionar([fid])
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "empty", "etapas": []}
        izq.botones["Editar orden de forzado…"].click()
        self.assertEqual(izq.texto.text(), "Orden: H fuerza R a la situación vacía")
        izq.botones["Quitar orden de forzado"].click()
        self.assertEqual((e.ed.model["forces"], e.sel, w.props.pagina), ([], [], "vacio"))
        # una etapa ordinaria del raíz sin otro parcial al que forzar solo ofrece su tipo, sin descripción
        w2, e2 = self.vacio()
        e2.colocar("etapa", QPointF(260, 60))
        e2.seleccionar([e2.sel[0]])
        self.assertEqual((w2.props.ficha_etapa.texto.isHidden(), w2.props.ficha_etapa.textos_visibles()),
                         (True, ["Etapa", "Encapsulante", "Macroetapa"]))
        e2.seleccionar([])
        self.assertEqual((w2.props.pagina, w2.props.ficha_etapa.isHidden(), w2.props.ficha_izq.isHidden()), ("vacio", True, True))

    def test_SEDI186_encuadrar_la_macroetapa_o_la_encapsulante_y_doble_clic_son_solo_navegacion(self):
        """REQ-EDT-08, REQ-JER-07: «Encuadrar la macroetapa» en la entrada y la salida de una expansión (y en su zona),
        «Encuadrar la encapsulante» en las etapas de un recinto y en su marco, y doble clic en una macroetapa («Encuadrar la
        expansión») seleccionan, encajan en la vista y resaltan el elemento sin tocar el modelo, el historial ni la marca de
        cambios."""
        from escritorio.diagrama import cajas_parciales
        w, e, d = self.con_recinto()
        e0, r, a = d["e0"], d["r"], d["a"]
        mid = e.poner_macro(QPointF(260, 600))
        x = e.ed.macro_info(mid)
        e.ed.dirty = False
        encuadrados = []
        w.diagrama.encuadrar = lambda caja: encuadrados.append(caja)
        antes, n = self.estado(e), len(e.ed.undo_stack)

        def esta_en_la_ultima(ident):
            """Lo último que se encuadró contiene el elemento (por su centro)."""
            return encuadrados[-1].contains(e.centro(ident))

        # la entrada y la salida: «Encuadrar la macroetapa»
        for sid in (x.entry, x.exit):
            e.seleccionar([])
            opciones = e.menu(centro(e.M, sid))
            self.assertIn("Encuadrar la macroetapa", dict(opciones))
            self.assertNotIn("Ir a la macroetapa", dict(opciones))
            self.assertEqual(dict(opciones)["Encuadrar la macroetapa"](), True)
            self.assertEqual(e.sel, [mid])
            self.assertTrue(esta_en_la_ultima(mid))
            self.assertEqual(e.parpadeo.ids, {mid})
            self.assertTrue(e.mensaje_info and self.sin_ids(e.mensaje) and "M1" in e.mensaje)
        # una etapa del recinto, y su marco: «Encuadrar la encapsulante»
        e.seleccionar([])
        dict(e.menu(centro(e.M, a)))["Encuadrar la encapsulante"]()
        self.assertEqual((e.sel, esta_en_la_ultima(e0), e.parpadeo.ids), ([e0], True, {e0}))
        c = cajas_parciales(e.M)[r]
        e.seleccionar([])
        opciones = e.menu(QPointF(c["x0"], c["y0"] + 10))
        self.assertEqual([t for t, _ in opciones], ["Encuadrar la encapsulante"])
        self.assertEqual(e.sel, [r])
        dict(opciones)["Encuadrar la encapsulante"]()
        self.assertEqual(e.sel, [e0])
        # la zona de la expansión (su parcial seleccionado) vuelve a la macroetapa
        e.seleccionar([x.partial])
        self.assertEqual([t for t, _, _ in e.ficha_jerarquia(x.partial)["botones"]], ["Encuadrar la macroetapa"])
        e.ficha_jerarquia(x.partial)["botones"][0][1]()
        self.assertEqual(e.sel, [mid])
        # doble clic en una macroetapa: encuadra su expansión; en una etapa, sigue pidiendo su etiqueta
        encuadrados.clear()
        e.seleccionar([])
        self.assertTrue(e.doble(centro(e.M, mid)))
        b = cajas_parciales(e.M)[x.partial]
        self.assertEqual((e.sel, len(encuadrados), e.parpadeo.ids), ([x.partial], 1, {x.partial}))
        self.assertTrue(encuadrados[0].contains(QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"])))
        e.parpadeo.parar()
        pedidas = []
        e.pedir_etiqueta = pedidas.append
        e.doble(centro(e.M, a))
        self.assertEqual(pedidas, [a])
        # nada de esto toca el modelo, el historial ni la marca de cambios
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.ed.dirty), (antes, n, False))

    def test_SEDI187_la_zona_de_suelta_de_un_parcial_incluye_un_margen_a_la_derecha_y_debajo(self):
        """REQ-JER-04, REQ-EDT-02: lo que se suelta a una etapa de ancho (a la derecha) o de alto (debajo) del marco de un
        parcial que no es el raíz es de ese parcial, para poder seguir rellenándolo; nunca a su izquierda ni arriba, el margen no
        quita lo que cae dentro del marco de otro parcial, y a más distancia es del raíz. El recuadro de destino lo anuncia."""
        from escritorio import edicion
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        m1 = e.poner_macro(QPointF(260, 220))
        x1 = e.ed.macro_info(m1)
        b = cajas_parciales(e.M)[x1.partial]
        self.assertEqual((b["x0"], b["x1"], b["y0"], b["y1"], edicion.MARGEN_SUELTA), (492.0, 632.0, 176.0, 584.0, 44))
        pe = e.parcial_en
        self.assertEqual((pe(QPointF(632 + 30, 380)), pe(QPointF(632 + 44, 380)), pe(QPointF(632 + 45, 380))),
                         (x1.partial, x1.partial, "g"), "a la derecha, una etapa de margen")
        self.assertEqual((pe(QPointF(540, 584 + 30)), pe(QPointF(540, 584 + 44)), pe(QPointF(540, 584 + 45))),
                         (x1.partial, x1.partial, "g"), "debajo, una etapa de margen")
        self.assertEqual((pe(QPointF(492 - 10, 380)), pe(QPointF(540, 176 - 10)), pe(QPointF(492 - 10, 176 - 10))),
                         ("g", "g", "g"), "ni a la izquierda ni arriba")
        self.assertEqual(pe(QPointF(632 + 30, 584 + 30)), x1.partial, "ni en la esquina")
        # el margen no quita lo que cae dentro del marco de otro parcial: una segunda expansión pegada a la primera
        m2 = e.poner_macro(QPointF(260, 400))
        x2 = e.ed.macro_info(m2)
        b2 = cajas_parciales(e.M)[x2.partial]
        self.assertTrue(b["x1"] < b2["x0"] < b["x1"] + 44, "los márgenes se solapan con el marco de la segunda")
        self.assertEqual((pe(QPointF(b["x1"] + 3, 380)), pe(QPointF(b2["x0"] + 3, 380))), (x1.partial, x2.partial))
        # el recuadro de destino y soltar: debajo de la salida cabe otra etapa, y es de la expansión
        w2, e2 = self.vacio()
        mid = e2.poner_macro(QPointF(260, 220))
        x = e2.ed.macro_info(mid)
        punto = QPointF(540, 584 + 30)
        self.assertTrue(e2.sobrevolar("etapa", punto))
        self.assertIsNotNone(w2.diagrama.destino, "se recuadra la expansión")
        self.soltar_ficha("etapa", punto, w2)
        self.assertEqual(e2.parcial_de(e2.sel[0]), x.partial)
        self.assertTrue(cajas_parciales(e2.M)[x.partial]["y1"] > 584 + 30, "el marco crece con lo que se le suelta")
        self.soltar_ficha("etapa", QPointF(540, 584 + 200), w2)
        self.assertEqual(e2.parcial_de(e2.sel[0]), "g")
        # lo mismo con el marco de un recinto con etapas
        w3, e3, d = self.con_recinto()
        c = cajas_parciales(e3.M)[d["r"]]
        e3.colocar("etapa", QPointF(c["x1"] + 30, c["y0"] + 40))
        self.assertEqual(e3.parcial_de(e3.sel[0]), d["r"])
        e3.colocar("encapsulante", QPointF(260, 700))
        self.assertEqual(e3.parcial_de(e3.sel[0]), "g")

    def test_SEDI188_el_marco_de_un_recinto_vacio_se_arrastra_con_una_sola_operacion_de_deshacer(self):
        """REQ-EDT-03, REQ-EDT-05, REQ-JER-05: el marco de un recinto sin etapas se mueve arrastrando su borde (a la rejilla; se
        ve moverse), y la posición se guarda con una sola operación de deshacer; no se pone encima de otro elemento ni del
        marco de otro parcial; un clic sin mover no cambia nada; el marco de un parcial con etapas solo se selecciona."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        self.soltar_ficha("encapsulante", QPointF(260, 60))
        h = e.sel[0]
        r = e.anadir_recinto(h)
        c0 = cajas_parciales(e.M)[r]
        # un clic sin mover: selecciona, y no cambia nada
        borde = QPointF(c0["x0"], c0["y0"] + 60)
        antes, n = self.estado(e), len(e.ed.undo_stack)
        e.seleccionar([])
        e.prensar(borde)
        e.soltar(borde)
        self.assertEqual((e.sel, self.estado(e), len(e.ed.undo_stack)), ([r], antes, n))
        # arrastrar: el marco sigue al puntero mientras se arrastra
        destino = QPointF(borde.x() + 200, borde.y() + 160)
        e.prensar(borde)
        self.assertEqual(e.arrastre["tipo"], "marco")
        e.mover(destino)
        c1 = cajas_parciales(e.M)[r]
        self.assertEqual((c1["x0"], c1["y0"]), (c0["x0"] + 200, c0["y0"] + 160), "se ve moverse, a la rejilla")
        self.assertEqual(self.estado(e), antes, "sin soltar, el modelo y la presentación no cambian")
        e.soltar(destino)
        c1 = cajas_parciales(e.M)[r]
        self.assertEqual((c1["x0"], c1["y0"], len(e.ed.undo_stack)), (c0["x0"] + 200, c0["y0"] + 160, n + 1))
        self.assertEqual(posiciones_modelo(e)[r], (c1["x0"] - 100, c1["y0"]))
        despues = self.estado(e)
        e.deshacer()
        self.assertEqual((self.estado(e), cajas_parciales(e.M)[r]), (antes, c0))
        e.rehacer()
        self.assertEqual(self.estado(e), despues)
        # no encima de otro elemento ni del marco de otro parcial: vuelve a su sitio con el aviso
        e.colocar("etapa", QPointF(c1["x0"] + 600, c1["y0"] + 40))
        otra = e.sel[0]
        n, antes = len(e.ed.undo_stack), self.estado(e)
        c1 = cajas_parciales(e.M)[r]
        origen = QPointF(c1["x0"], c1["y0"] + 60)
        e.prensar(origen)
        sobre = QPointF(centro(e.M, otra).x() - 90, origen.y())  # el marco taparía a la etapa
        e.mover(sobre)
        self.assertTrue(e.diagrama.prohibidos, "en rojo mientras tapa algo")
        e.soltar(sobre)
        self.assertEqual((self.estado(e), len(e.ed.undo_stack), e.mensaje), (antes, n, "No se puede poner encima de otro elemento"))
        # el marco de otro parcial (otro recinto vacío): tampoco, aunque no tape ninguna etapa
        r2 = e.anadir_recinto(h)
        otro = cajas_parciales(e.M)[r2]
        n, antes = len(e.ed.undo_stack), self.estado(e)
        c1 = cajas_parciales(e.M)[r]
        origen = QPointF(c1["x0"], c1["y0"] + 60)
        e.prensar(origen)
        sobre = QPointF(otro["x0"] - 90, otro["y0"] + 20 + 60)  # la mitad de un marco sobre la mitad del otro
        e.mover(sobre)
        self.assertTrue(e.diagrama.prohibidos)
        e.soltar(sobre)
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        # El marco con etapas también se arrastra por el borde, en una operación reversible.
        self.soltar_ficha("etapa", QPointF((c1["x0"] + c1["x1"]) / 2, (c1["y0"] + c1["y1"]) / 2))
        sid = e.sel[0]
        c2 = cajas_parciales(e.M)[r]
        antes, n = self.estado(e), len(e.ed.undo_stack)
        posicion = posiciones_modelo(e)[sid]
        e.seleccionar([])
        origen = QPointF(c2["x0"], (c2["y0"] + c2["y1"]) / 2)
        e.prensar(origen)
        self.assertEqual((e.sel, e.arrastre["tipo"]), ([r], "grupo"))
        e.mover(origen + QPointF(60, 40))
        e.soltar(origen + QPointF(60, 40))
        self.assertEqual(posiciones_modelo(e)[sid], (posicion[0] + 60, posicion[1] + 40))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SEDI189_las_condiciones_de_una_accion_se_leen_en_el_parcial_de_su_etapa(self):
        """REQ-ACT-01, REQ-MOD-07: la condición, el valor o el evento de una acción se comprueban con los nombres del parcial de
        su etapa y no con los del raíz: «XZ» es ambigua en el raíz si hay una etapa Z en dos recintos, pero vale en el recinto de
        cada una; la acción de esa etapa se completa y pasa al modelo."""
        from escritorio.diagrama import cajas_parciales
        w, e = self.vacio()
        zs = []
        for y in (60, 500):
            e.colocar("encapsulante", QPointF(260, y))
            r = e.anadir_recinto(e.sel[0])
            c = cajas_parciales(e.M)[r]
            e.colocar("etapa", QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
            self.assertIsNone(e.renombrar(e.sel[0], "Z"))
            zs.append((e.sel[0], r))
        (z1, r1), (z2, r2) = zs
        self.assertEqual((e.nombres[z1], e.nombres[z2]), ("G1.Z", "G2.Z"))
        self.assertEqual((e._texto_valido("XZ"), e._texto_valido("XZ", r1), e._texto_valido("XZ", r2)), (False, True, True))
        e.nueva_variable("Q", "output")
        datos = {"tipo": "condicionada", "variable": "Q", "condicion": "XZ"}
        self.assertEqual((e.faltan(datos), e.faltan(datos, r1)), (["condición"], []))
        self.assertIsNone(e._revisar_textos({**datos, "tipo": "evento", "evento": "↑XZ"}, r1))
        self.assertIn("no es válido", e._revisar_textos({**datos, "tipo": "evento", "evento": "↑XZ"}))
        # la acción de la etapa Z del primer recinto, con su condición, es una acción del modelo (no un borrador)
        self.assertIsNone(e.poner_accion(z1, datos))
        (acc,) = e.ed.model["actions"]
        self.assertEqual((acc["stepRef"], e.ed.draft_actions()), (z1, []))
        condicion = next(x for x in e.ed.model["expressions"] if x["id"] == acc["conditionRef"])
        self.assertEqual(list(condicion["bindings"].values()), [z1], "la Z del recinto de la etapa, y no la del otro")
        self.assertEqual(e._parcial(acc["id"]), r1, "y su ámbito es el de su parcial")
        # escribir su condición con el panel (poner_texto_accion) también usa ese ámbito: sigue siendo una acción del modelo
        self.assertIsNone(e.poner_texto_accion(acc["id"], "condicion", "XZ"))
        self.assertEqual((len(e.ed.model["actions"]), e.ed.draft_actions()), (1, []))
        # cambiarla a «por evento» la deja como borrador unido a la etapa; al completar valor y evento, vuelve al modelo
        e.tipo_accion(acc["id"], "evento")
        (b,) = e.ed.draft_actions()
        self.assertIsNone(e.poner_texto_accion(b["id"], "valor", "1"))
        self.assertEqual(len(e.ed.draft_actions()), 1)
        self.assertIsNone(e.poner_texto_accion(b["id"], "evento", "↑XZ"))
        self.assertEqual(e.ed.draft_actions(), [], "el evento se lee en el ámbito del recinto y la acción se completa")
        (nueva,) = e.ed.model["actions"]
        self.assertEqual((nueva["stepRef"], e.datos_accion(nueva["id"])["tipo"]), (z1, "evento"))

    def test_SEDI190_el_ejemplo_forzado_construido_solo_con_gestos_simula_como_el_del_constructor(self):
        """REQ-JER-02, REQ-EDT-02, REQ-SIM-03: el ejemplo «forzado» rehecho con gestos del editor (fichas, enlaces,
        «Añadir debajo», recinto con «Añadir recinto…», «Forzar un parcial…»; sin llamar a add_force) simula igual, paso a
        paso, que el del constructor: mientras H está activa, el parcial G no evoluciona aunque se pulsen a, b o c; al quitar f
        se retira la orden y G sigue desde B."""
        from escritorio.diagrama import anclas, cajas_parciales
        from grafcet.examples import EJEMPLOS
        from grafcet.view import Vista
        w, e = self.vacio()
        e.pedir_texto = lambda *args: "G"

        def enlazar(origen, destino):
            pa = next(q for q in anclas(e.M, origen) if q["lado"] == "abajo")["pos"]
            pb = next(q for q in anclas(e.M, destino) if q["lado"] == "arriba")["pos"]
            e.prensar(pa)
            e.mover(pb)
            e.soltar(pb)
        # el raíz: H2 -t1(f)-> H -t2(NOT f)-> H2
        e.colocar("etapa", QPointF(260, 60))
        h2 = e.sel[0]
        e.tipo_etapa(h2, True)
        e.colocar("transicion", QPointF(260, 140))
        t1 = e.sel[0]
        e.colocar("etapa", QPointF(260, 220))
        h = e.sel[0]
        e.colocar("transicion", QPointF(260, 300))
        t2 = e.sel[0]
        for origen, destino in ((h2, t1), (t1, h), (h, t2), (t2, h2)):
            enlazar(origen, destino)
        # una encapsulante inicial con su recinto G (que se rellena soltando A y con «Añadir debajo»): A -ta-> B -tb-> C -tc-> A
        e.colocar("encapsulante", QPointF(260, 460))
        e0 = e.sel[0]
        e.tipo_etapa(e0, True)
        g = e.anadir_recinto(e0)
        c = cajas_parciales(e.M)[g]
        e.colocar("etapa", QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
        a = e.sel[0]
        e.tipo_etapa(a, True)
        e.sel = [a]
        b = e.anadir_debajo()
        e.sel = [b]
        cc = e.anadir_debajo()
        origen = next(q for q in anclas(e.M, cc) if q["lado"] == "abajo")
        e.crear_desde(origen, QPointF(500, 900))
        tc = e.sel[0]
        enlazar(tc, a)
        ta = next(t["id"] for t in e.ed.model["transitions"] if a in t["preRefs"])
        tb = next(t["id"] for t in e.ed.model["transitions"] if b in t["preRefs"])
        self.assertEqual({e.parcial_de(i) for i in (a, b, cc, ta, tb, tc)}, {g}, "todo lo de dentro es del recinto")
        for sid, nombre in ((h2, "H2"), (h, "H"), (a, "A"), (b, "B"), (cc, "C"), (e0, "E0")):
            self.assertIsNone(e.renombrar(sid, nombre))
        for tid, cond in ((t1, "f"), (t2, "NOT f"), (ta, "a"), (tb, "b"), (tc, "c")):
            e.poner_condicion(tid, cond, crear=True)
        # la orden, con el botón derecho en H y el diálogo (sustituido): G{B}
        pedidas = []
        e.pedir_forzado = lambda datos: pedidas.append(datos) or {"destino": g, "forma": "explicit", "etapas": [b]}
        fid = dict(e.menu(centro(e.M, h)))["Forzar un parcial…"]()
        self.assertEqual((pedidas[0]["destinos"], pedidas[0]["etapas"][g]), ([(g, "recinto G")], [(a, "A"), (b, "B"), (cc, "C")]))
        self.assertEqual((e.mensaje, [f["id"] for f in e.ed.model["forces"]]), ("Orden: H fuerza G a {B}.", [fid]))
        self.assertIn("G{B}", self.textos_dibujo(w))
        self.assertEqual([d for d in e.diagnosticos() if d["blocks"]], [])
        self.assertTrue(e.ed.validate().can_simulate)
        # lo mismo que el ejemplo del constructor, con los mismos nombres: en la situación solo sobra la encapsulante E0
        construir = EJEMPLOS["forzado"][2]
        modelo, disposicion = construir()
        ref = Vista("ref", "t", "", lambda: (modelo, disposicion), e.opciones)
        mio = e.vista
        ids = {v["name"]: v["id"] for v in e.ed.model["variables"]}
        ids_ref = {v["name"]: v["id"] for v in ref.doc["variables"]}

        def situacion(v):
            return sorted(n for n in (v.names.get(i, i) for i in v.state()["situation"]) if n != "E0")

        def mover(v, var, valor):
            v.act("fijar", {"cambios": {(ids if v is mio else ids_ref)[var]: valor}})
        self.assertEqual((situacion(mio), situacion(ref)), (["A", "H2"], ["A", "H2"]))
        guion = [("f", True), ("a", None), ("b", None), ("c", None), ("f", False), ("b", None), ("c", None), ("a", None),
                 ("f", True), ("a", None), ("b", None), ("f", False), ("a", None), ("b", None), ("b", None), ("c", None)]
        vistas = []
        for var, valor in guion:
            for v in (mio, ref):
                if valor is None:  # un pulso
                    mover(v, var, True)
                    mover(v, var, False)
                else:
                    mover(v, var, valor)
            vistas.append(situacion(mio))
            self.assertEqual(situacion(mio), situacion(ref), (var, valor))
        self.assertIn(["B", "H"], vistas, "con f, H activa y G forzado a B")
        self.assertIn(["C", "H2"], vistas, "sin la orden, G sigue desde B")

    def test_SEDI191_el_ejemplo_forzado_abierto_se_edita_su_orden_con_el_menu_y_simula_igual(self):
        """REQ-JER-02, REQ-EDT-05, REQ-SIM-03: sobre el ejemplo «forzado» del constructor, el botón derecho en la caja «G{B}»
        edita la orden (otra forma, otras etapas) y la quita; volver a ponerla con «Forzar un parcial…» en H deja un modelo que
        simula igual que el original; todo se deshace de una vez por operación."""
        from grafcet.examples import EJEMPLOS
        from grafcet.view import Vista
        w = self.w
        self.proyecto_fixture("forzado")
        e = w.edicion
        e.ed.dirty = False
        original = Vista("o", "t", "", lambda: EJEMPLOS["forzado"][2](), e.opciones)
        (f0,) = e.ed.model["forces"]
        self.assertEqual(e.descripcion_jerarquia(f0["id"]), "Orden: H fuerza G a {B}")
        pc = self.centro_orden(w, f0["id"])
        self.assertEqual([t for t, _ in e.menu(pc)],
                         ["Tipo de acción", "-", "Editar orden de forzado…", "Quitar orden de forzado"])
        # editar: «Vacía» y luego «La situación actual»; el parcial G de los ejemplos aparece por su nombre
        vistos = []
        e.pedir_forzado = lambda datos: vistos.append(datos) or {"destino": "G", "forma": "empty", "etapas": []}
        n = len(e.ed.undo_stack)
        e.editar_orden(f0["id"])
        self.assertEqual(vistos[0]["actual"], {"destino": "G", "forma": "explicit", "etapas": ["B"]})
        self.assertEqual([x for _, x in vistos[0]["destinos"]], ["G"])
        self.assertEqual((e.ed.model["forces"][0]["targetKind"], len(e.ed.undo_stack)), ("empty", n + 1))
        self.assertIn("G{ }", self.textos_dibujo(w))
        e.deshacer()
        self.assertEqual(e.ed.model["forces"], [f0])
        # quitar con el menú, y volver a poner la misma orden desde la etapa H
        self.assertTrue(dict(e.menu(self.centro_orden(w, f0["id"])))["Quitar orden de forzado"]())
        self.assertEqual((e.ed.model["forces"], w.diagrama.cajas_ordenes), ([], []))
        e.pedir_forzado = lambda datos: {"destino": "G", "forma": "explicit", "etapas": ["B"]}
        nueva = dict(e.menu(centro(e.M, "H")))["Forzar un parcial…"]()
        (f1,) = e.ed.model["forces"]
        self.assertEqual({k: v for k, v in f1.items() if k != "id"}, {k: v for k, v in f0.items() if k != "id"})
        mio = e.vista
        ids = {v["name"]: v["id"] for v in e.ed.model["variables"]}
        ids_o = {v["name"]: v["id"] for v in original.doc["variables"]}
        self.assertEqual(f1["id"], nueva)
        for var, valor in (("f", True), ("a", None), ("b", None), ("f", False), ("b", None), ("c", None), ("f", True), ("c", None)):
            for v, tabla in ((mio, ids), (original, ids_o)):
                if valor is None:
                    v.act("fijar", {"cambios": {tabla[var]: True}})
                    v.act("fijar", {"cambios": {tabla[var]: False}})
                else:
                    v.act("fijar", {"cambios": {tabla[var]: valor}})
            self.assertEqual(sorted(mio.state()["situation"]), sorted(original.state()["situation"]), (var, valor))

    def test_SEDI192_dialogo_de_la_orden_de_forzado_con_nombres_formas_y_etapas(self):
        """REQ-JER-02, REQ-EDT-09: el diálogo de «Forzar un parcial…» (el de la ventana, sustituible) ofrece los parciales por su
        nombre, las cuatro formas con sus términos y, solo con la forma Explícita, las etapas del parcial elegido con casilla;
        devuelve los ID de lo elegido; al editar parte de los valores actuales; ningún texto lleva IDs; el gancho de la
        edición lo abre y cancelar devuelve None."""
        from PySide6.QtWidgets import QDialog
        from escritorio.ventana import DialogoForzado
        w, e, d = self.con_recinto()
        h, r, a, b = d["h"], d["r"], d["a"], d["b"]
        mid = e.poner_macro(QPointF(260, 600))
        x = e.ed.macro_info(mid)
        dlg = DialogoForzado(w, e._datos_forzado(h))
        self.assertEqual(dlg.windowTitle(), "Forzar un parcial")
        self.assertEqual([dlg.destino.itemText(i) for i in range(dlg.destino.count())], ["recinto R", "expansión de M1"])
        self.assertEqual([bt.text() for bt in dlg.formas.values()], ["Explícita", "La situación actual", "Vacía", "Inicial"])
        self.assertEqual(dlg.resultado(), {"destino": r, "forma": "explicit", "etapas": []}, "por defecto, explícita y sin etapas")
        items = [dlg.etapas.item(i) for i in range(dlg.etapas.count())]
        self.assertEqual([it.text() for it in items], ["A", "B"])
        self.assertTrue(dlg.etapas.isEnabled())
        items[1].setCheckState(Qt.CheckState.Checked)
        self.assertEqual(dlg.resultado(), {"destino": r, "forma": "explicit", "etapas": [b]})
        # otra forma: las etapas se deshabilitan y no se devuelven
        dlg.formas["current"].setChecked(True)
        self.assertEqual((dlg.etapas.isEnabled(), dlg.resultado()), (False, {"destino": r, "forma": "current", "etapas": []}))
        # otro parcial: su lista de etapas, sin marcar
        dlg.destino.setCurrentIndex(1)
        dlg.formas["explicit"].setChecked(True)
        self.assertEqual([dlg.etapas.item(i).text() for i in range(dlg.etapas.count())], ["E1", "S1"])
        dlg.etapas.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(dlg.resultado(), {"destino": x.partial, "forma": "explicit", "etapas": [x.entry]})
        textos = [dlg.destino.itemText(i) for i in range(dlg.destino.count())] + [bt.text() for bt in dlg.formas.values()]
        textos += [dlg.etapas.item(i).text() for i in range(dlg.etapas.count())]
        self.assertTrue(all(self.sin_ids(t) for t in textos))
        # al editar: parte de la orden actual
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "explicit", "etapas": [a, b]}
        fid = e.forzar(h)
        orden = e.ed.model["forces"][0]
        dlg = DialogoForzado(w, e._datos_forzado(h, orden))
        self.assertEqual(dlg.windowTitle(), "Editar orden de forzado")
        self.assertEqual((dlg.destino.currentData(), [dlg.etapas.item(i).checkState() for i in range(2)]),
                         (r, [Qt.CheckState.Checked] * 2))
        self.assertEqual(dlg.resultado(), {"destino": r, "forma": "explicit", "etapas": [a, b]})
        dlg = DialogoForzado(w, e._datos_forzado(h, {**orden, "targetKind": "initial"}))
        self.assertTrue(dlg.formas["initial"].isChecked() and not dlg.etapas.isEnabled())
        # el gancho de la edición es el de la ventana (`_pedir_forzado`): abre el diálogo y devuelve lo elegido, o None
        e.pedir_forzado = lambda datos: w._pedir_forzado(datos)
        with mock.patch.object(DialogoForzado, "exec", return_value=QDialog.DialogCode.Accepted):
            self.assertEqual(e.pedir_forzado(e._datos_forzado(h, orden)), {"destino": r, "forma": "explicit", "etapas": [a, b]})
        with mock.patch.object(DialogoForzado, "exec", return_value=QDialog.DialogCode.Rejected):
            n = len(e.ed.undo_stack)
            self.assertIsNone(e.editar_orden(fid))
            self.assertEqual(len(e.ed.undo_stack), n)

    # -- correcciones de la ronda B3 -----------------------------------------------------------------------------------
    def test_SEDI194_la_macroetapa_unida_a_una_barra_se_ve_unida_a_ella_en_el_editor(self):
        """REQ-JER-04, REQ-MOD-03, REQ-EDT-02: una etapa y una macroetapa unidas con el ratón por encima de una barra Y, y la
        barra por encima de una transición, dejan la transición con las dos como etapas anteriores; la vista y el dibujo la
        muestran unida a la barra (su conector se dibuja y el ratón lo encuentra) y sin enlace directo a la transición."""
        from escritorio.diagrama import barra as caja_barra, elemento_en, posiciones
        w, e = self.vacio()
        e.colocar("etapa", QPointF(360, 60))
        a = e.sel[0]
        mid = e.poner_macro(QPointF(460, 60))
        e.colocar("transicion", QPointF(410, 300))
        t1 = e.sel[0]
        b = e.poner_barra(QPointF(410, 160), "Y")
        e.unir({"id": b, "lado": "arriba"}, {"id": a, "lado": "abajo"})
        e.unir({"id": b, "lado": "arriba"}, {"id": mid, "lado": "abajo"})
        e.unir({"id": b, "lado": "abajo"}, {"id": t1, "lado": "arriba"})
        self.assertEqual(e.ed.get(t1)["preRefs"], [a, mid], "el modelo: las dos son anteriores a la transición")
        (bv,) = e.M["bars"]
        self.assertEqual((bv["arriba"], bv["abajo"]), ([a, mid], [t1]), "la vista lleva la macroetapa en la barra")
        tr = next(t for t in e.M["transitions"] if t["id"] == t1)
        self.assertEqual((tr["pre"], tr["preDib"]), ([a, mid], []), "y no la dibuja directa a la transición")
        enlaces_ = {x["id"]: x for x in e.M["links"]}
        self.assertTrue({f"{b}|{a}|barra", f"{b}|{mid}|barra", f"{b}|{t1}|barra"} <= set(enlaces_))
        self.assertFalse([i for i in enlaces_ if i in (f"{t1}|{a}|pre", f"{t1}|{mid}|pre")])
        # el dibujo pinta el conector de la macroetapa a la barra (de su centro a la barra), y el ratón lo encuentra
        ex, ey = posiciones(e.M)[mid]
        pts = enlaces_[f"{b}|{mid}|barra"]["pts"]
        self.assertEqual((tuple(pts[0]), pts[-1][1]), ((ex, ey), caja_barra(bv)[1]))
        trazo = [q for i, q in enumerate(pts) if i == 0 or tuple(q) != tuple(pts[i - 1])]  # (Qt junta los puntos repetidos)
        pintados = [it for it in w.diagrama.scene().items() if hasattr(it, "path") and it.path().elementCount() == len(trazo)
                    and all(abs(it.path().elementAt(i).x - trazo[i][0]) < 1e-6 and abs(it.path().elementAt(i).y - trazo[i][1]) < 1e-6
                            for i in range(len(trazo)))]
        self.assertTrue(pintados, "el conector de la macroetapa a la barra está en el dibujo")
        self.assertEqual(elemento_en(e.M, QPointF(ex, ey + 40)), f"{b}|{mid}|barra")
        # y se quita como cualquier unión a una barra: el conector seleccionado y Supr
        e.seleccionar([f"{b}|{mid}|barra"])
        self.assertTrue(e.borrar())
        self.assertEqual((e.ed.get(t1)["preRefs"], e.M["bars"][0]["arriba"]), ([a], [a]))
        e.deshacer()
        self.assertEqual(e.ed.get(t1)["preRefs"], [a, mid])

    def test_SEDI195_un_enlace_soltado_en_el_borde_o_el_nombre_de_un_marco_abre_la_rama_como_en_un_hueco(self):
        """REQ-EDT-02, REQ-EDT-03: soltar el enlace que sale de un punto de unión en el borde o en el nombre del marco de un
        parcial (que se selecciona con el ratón, pero no es un elemento al que unir nada) se trata como soltarlo en un hueco:
        abre una rama, con el elemento que sigue, en el parcial del que sale; antes no hacía nada ni avisaba."""
        from escritorio.diagrama import anclas, cajas_parciales, elemento_en
        w, e, d = self.con_recinto()
        h, r = d["h"], d["r"]
        c = cajas_parciales(e.M)[r]
        for gesto, punto in (("el borde", QPointF(c["x0"], c["y0"] + 10)), ("el nombre", QPointF(c["x0"] + 40, c["y1"] + 4))):
            self.assertEqual(elemento_en(e.M, punto), r, gesto)
            antes, n = len(e.ed.model["transitions"]), len(e.ed.undo_stack)
            origen = next(q for q in anclas(e.M, h) if q["lado"] == "abajo")
            e.prensar(origen["pos"])
            e.mover(punto)
            e.soltar(punto)
            self.assertEqual((len(e.ed.model["transitions"]), len(e.ed.undo_stack)), (antes + 1, n + 1), gesto)
            nueva = next(t for t in e.ed.model["transitions"] if t["id"] == e.sel[0])
            self.assertEqual((nueva["preRefs"], nueva["partialRef"]), ([h], "g"), f"{gesto}: una rama que sale de H, en su parcial")
            self.assertTrue(e.mensaje_info and "Rama abierta" in e.mensaje)
            e.deshacer()
        # lo mismo desde una transición: lo que sigue es una etapa, y es del parcial de la transición
        e.colocar("transicion", QPointF(700, 60))
        t = e.sel[0]
        origen = next(q for q in anclas(e.M, t) if q["lado"] == "abajo")
        n = len(e.ed.model["steps"])
        punto = QPointF(c["x0"], c["y0"] + 10)
        e.prensar(origen["pos"])
        e.mover(punto)
        e.soltar(punto)
        self.assertEqual(len(e.ed.model["steps"]), n + 1)
        self.assertEqual(e.ed.get(t)["postRefs"], [e.sel[0]])
        # desde el punto de una acción suelta, un marco tampoco es una etapa: el mismo aviso que en un hueco
        e.colocar("accion", QPointF(900, 200))
        ac = e.sel[0]
        origen = next(q for q in anclas(e.M, ac) if q["lado"] == "izq")
        antes = self.estado(e)
        nombre = QPointF(c["x0"] + 40, c["y1"] + 4)  # (en el borde se acaba de crear una etapa: aquí no hay nada)
        self.assertEqual(elemento_en(e.M, nombre), r)
        e.prensar(origen["pos"])
        e.mover(nombre)
        e.soltar(nombre)
        self.assertEqual(self.estado(e), antes)
        self.assertTrue(e.mensaje and not e.mensaje_info and "etapa" in e.mensaje, e.mensaje)

    def test_SEDI196_borrar_avisa_de_las_ordenes_y_los_recintos_que_pierden_etapas(self):
        """REQ-EDT-05, REQ-JER-02, REQ-JER-05: el aviso de borrado enseña, con nombres, el recinto que pierde su enlace de
        activación y la orden de forzado que pierde etapas («pierde la etapa B»; si no le queda ninguna, «pasa a ser una orden
        explícita sin etapas: fuerza el parcial a vacío»); pregunta aunque no haya nada más que avisar; el borrado sigue
        siendo el del núcleo (queda el conjunto reducido) y se deshace de una vez."""
        from PySide6.QtWidgets import QMessageBox
        w, e, d = self.con_recinto()
        h, r, a, b = d["h"], d["r"], d["a"], d["b"]
        e.enlace_activacion(a)
        e.enlace_activacion(b)
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "explicit", "etapas": [a, b]}
        fid = e.forzar(h)
        preguntas = []
        e.confirmar_borrado = lambda plan: preguntas.append(plan) or False
        # una etapa de las dos: la orden pierde una etapa y el recinto una marca; cancelar no cambia nada
        antes = self.estado(e)
        e.seleccionar([b])
        self.assertFalse(e.borrar())
        self.assertEqual((self.estado(e), len(preguntas)), (antes, 1))
        self.assertEqual(e.avisos_borrado(preguntas[0]), ["el recinto R pierde su enlace de activación en B",
                                                         "la orden R{A,B} de H pierde la etapa B"])
        textos = []
        e.confirmar_borrado = w._confirmar_borrado
        with mock.patch("escritorio.ventana.QMessageBox.question",
                        side_effect=lambda *args: textos.append(args[2]) or QMessageBox.StandardButton.Yes):
            self.assertTrue(e.borrar())
        self.assertTrue(self.sin_ids(textos[0]), textos[0])
        self.assertIn("También cambia la jerarquía:", textos[0])
        self.assertIn("• El recinto R pierde su enlace de activación en B.", textos[0])
        self.assertIn("• La orden R{A,B} de H pierde la etapa B.", textos[0])
        self.assertNotIn("sin etapas", textos[0])
        # el borrado en sí no cambia: queda el conjunto reducido
        m = e.ed.model
        self.assertEqual((m["forces"][0]["targetSteps"], m["hierarchy"]["enclosures"][0]["activationRefs"]), ([a], [a]))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        # las dos: la orden se queda sin etapas, y lo dice
        e.confirmar_borrado = w._confirmar_borrado
        e.seleccionar([a, b])
        textos.clear()
        with mock.patch("escritorio.ventana.QMessageBox.question",
                        side_effect=lambda *args: textos.append(args[2]) or QMessageBox.StandardButton.Yes):
            self.assertTrue(e.borrar())
        self.assertTrue(self.sin_ids(textos[0]), textos[0])
        self.assertIn("• La orden R{A,B} de H pierde las etapas A, B y pasa a ser una orden explícita sin etapas: "
                      "fuerza el parcial a vacío.", textos[0])
        self.assertIn("• El recinto R pierde su enlace de activación en A, B.", textos[0])
        self.assertEqual((e.ed.model["forces"][0]["targetKind"], e.ed.model["forces"][0]["targetSteps"],
                          e.ed.model["hierarchy"]["enclosures"][0]["activationRefs"]), ("explicit", [], []))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        # una etapa suelta del recinto con enlace de activación y nada más que avisar: también pregunta
        from escritorio.diagrama import cajas_parciales
        c = cajas_parciales(e.M)[r]
        e.colocar("etapa", QPointF(c["x1"] + 30, c["y0"] + 40))
        suelta = e.sel[0]
        e.enlace_activacion(suelta)
        preguntas.clear()
        e.confirmar_borrado = lambda plan: preguntas.append(plan) or False
        e.seleccionar([suelta])
        self.assertFalse(e.borrar())
        self.assertEqual(len(preguntas), 1)
        self.assertEqual((preguntas[0]["elements"], preguntas[0]["affectedTransitions"]), ([suelta], []))
        self.assertEqual(e.avisos_borrado(preguntas[0]), ["el recinto R pierde su enlace de activación en " + e.nombres[suelta]])
        # una etapa que ninguna orden ni recinto marca se borra sin preguntar, como siempre
        preguntas.clear()
        e.colocar("etapa", QPointF(260, 700))
        e.seleccionar([e.sel[0]])
        self.assertTrue(e.borrar())
        self.assertEqual(preguntas, [])

    def test_SEDI197_un_borrado_rechazado_deja_la_marca_de_cambios_como_estaba(self):
        """REQ-EDT-05, REQ-EDT-10: si `borrar` se rechaza (la entrada de una expansión sola, junto a una barra que ya se había
        quitado) se deshace todo y la marca de cambios sin guardar vuelve a lo que era: no queda como modificado un
        documento que no cambió."""
        w, e = self.vacio()
        mid = e.poner_macro(QPointF(260, 220))
        x = e.ed.macro_info(mid)
        barra = e.poner_barra(QPointF(700, 100), "Y")
        antes = self.estado(e)
        for sucio in (False, True):
            e.ed.dirty = sucio
            e.sel = [barra, x.entry]
            self.assertFalse(e.borrar())
            self.assertEqual((e.ed.dirty, self.estado(e)), (sucio, antes), f"antes dirty={sucio}")
            self.assertTrue(e.mensaje and not e.mensaje_info and self.sin_ids(e.mensaje))
        # y un borrado que sí se hace la marca
        e.ed.dirty = False
        e.sel = [barra]
        self.assertTrue(e.borrar())
        self.assertTrue(e.ed.dirty)

    # -- D1: guardar el dibujo con las dependencias y las fichas 1 y 0 del programador por bloques -----------------------
    def test_SEDI297_guardar_el_dibujo_como_imagen_respeta_mostrar_dependencias(self):
        """REQ-EDT-02, REQ-SIM-03 (P-IMP-66): «Guardar el dibujo como imagen» dibuja con el estado actual del botón «Mostrar
        dependencias»: apagado, sin los trazos discontinuos macroetapa-expansión; encendido, con ellos; al editar y en Play."""
        from PySide6.QtGui import QImage
        from escritorio import ventana as modulo
        from escritorio.diagrama import imagen
        w, d = self.w, self.w.diagrama
        w.cargar_ejemplo("macroetapa")
        self.assertFalse(d.b_dependencias.isChecked())

        def guardar(nombre):
            ruta = str(Path(self.tmp.name) / nombre)
            with mock.patch("escritorio.ventana.QFileDialog.getSaveFileName", return_value=(ruta, "")), \
                    mock.patch.object(modulo, "imagen", wraps=imagen) as dibujo:
                w.guardar_imagen()
            self.assertEqual(dibujo.call_count, 1)
            img = QImage(ruta)
            self.assertFalse(img.isNull(), nombre)
            return dibujo.call_args.kwargs["dependencias"], bytes(img.constBits())
        sin, bytes_sin = guardar("sin.png")
        d.b_dependencias.click()
        con, bytes_con = guardar("con.png")
        self.assertEqual((sin, con), (False, True), "el estado actual del botón")
        self.assertNotEqual(bytes_sin, bytes_con, "con las dependencias se dibujan los trazos discontinuos")
        d.b_dependencias.click()
        self.assertEqual(guardar("otra-vez-sin.png"), (False, bytes_sin), "apagado vuelve a ser la misma imagen")
        # en Play dibuja el estado de la simulación, con el mismo botón
        w.a_ejecutar.setChecked(True)
        self.assertEqual(guardar("play-sin.png")[0], False)
        d.b_dependencias.click()
        self.assertEqual(guardar("play-con.png")[0], True)
        d.b_dependencias.click()

    def esqueleto_sin_receptividad(self):
        """E0 (inicial) → t1 → E1 hecho con los gestos del ratón, con la transición todavía sin receptividad (una
        transición nueva queda pendiente). Devuelve la edición, los ID de las etapas por etiqueta y el de la transición."""
        from escritorio.diagrama import anclas
        w = self.w
        w.nuevo()
        e = w.edicion

        def enlace(a, b):
            pa = next(x for x in anclas(e.M, a) if x["lado"] == "abajo")["pos"]
            pb = next(x for x in anclas(e.M, b) if x["lado"] == "arriba")["pos"]
            e.herramienta = "seleccionar"
            e.prensar(pa)
            e.mover(pb)
            e.soltar(pb)
        e.colocar("etapa", QPointF(100, 60))
        e.tipo_etapa(e.M["steps"][0]["id"], True)
        e.colocar("transicion", QPointF(100, 140))
        e.colocar("etapa", QPointF(100, 220))
        ids = {s["label"]: s["id"] for s in e.M["steps"]}
        t = e.M["transitions"][0]["id"]
        enlace(ids["0"], t)
        enlace(t, ids["1"])
        return e, ids, t

    def test_SEDI298_las_fichas_1_y_0_se_arrastran_a_una_receptividad_vacia(self):
        """REQ-EDT-02, REQ-SIM-03: la carpeta «Constantes» del programador trae las fichas 1 (verdadero) y 0 (falso); soltada en
        la receptividad vacía de una transición, «1» da la receptividad válida «1» (se guarda como true) que siempre franquea y
        «0» la «0» (false) que nunca; la notación es la del usuario y la gramática no cambia."""
        from escritorio import bloques
        w = self.w
        e, ids, t = self.esqueleto_sin_receptividad()
        e.seleccionar([t])
        prog = w.props.prog
        a = prog.lienzo
        self.assertEqual(prog.texto(), "")
        self.assertFalse(e.ed.validate().can_simulate, "una transición nueva queda pendiente")
        prog.elegir_categoria("constante")
        self.assertEqual(prog.categorias["constante"].text(), "Constantes")
        uno, cero = prog.paleta.bloques()
        self.assertEqual([(b["k"], b["v"]) for b in (uno, cero)], [("const", 1), ("const", 0)])

        def arrastrar(nodo, sobre_la_raiz=False):
            """Lo que genera Qt al soltar una ficha de la paleta en el área de bloques: en el área vacía o sobre el bloque."""
            m = QMimeData()
            m.setData(bloques.MIME, json.dumps({"nodo": nodo, "grupo": prog.grupo, "origen": None}).encode())
            a._calcular(max(a.width(), 300))
            pos = next(x for x in a._bloques if x[1] == (0,))[0].center() if sobre_la_raiz else QPointF(20, 20)
            a.dropEvent(QDropEvent(pos, Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        arrastrar(uno)  # al área vacía: pasa a ser la receptividad
        self.assertEqual((prog.texto(), w.props.t_texto.text(), e.texto_condicion(t)), ("1", "1", "true"))
        self.assertTrue(e.ed.validate().can_simulate, [str(x) for x in e.ed.validate().diagnostics])
        self.assertEqual(e.texto_usuario(t), "1")
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.v.state()["situation"], [ids["1"]], "«1» franquea en cuanto la transición está validada")
        self.assertTrue(w.cambiar_modo("editar"))
        # «0» sobre el «1»: lo sustituye (una constante no envuelve)
        e.seleccionar([t])
        self.assertEqual(prog.texto(), "1", "al volver a editar, la receptividad vuelve como el bloque 1")
        arrastrar(cero, sobre_la_raiz=True)
        self.assertEqual((prog.texto(), e.texto_condicion(t)), ("0", "false"))
        self.assertTrue(e.ed.validate().can_simulate)
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.v.state()["situation"], [ids["0"]])
        w._act("avanzar", us=10_000_000)
        self.assertEqual(w.v.state()["situation"], [ids["0"]], "«0» no franquea nunca, por mucho tiempo que pase")
        self.assertTrue(w.cambiar_modo("editar"))

    def test_SEDI299_las_fichas_1_y_0_con_operadores_se_escriben_y_franquean_como_corresponde(self):
        """REQ-EDT-02, REQ-SIM-03: «1» y «0» combinadas con «y», «o» y «no» se escriben con 1 y 0 en la notación del usuario, se
        guardan como true y false, vuelven a bloques tal cual y franquean como corresponde con la entrada a 0 y a 1."""
        from escritorio.bloques import arbol_a_texto, nuevo, texto_a_arbol, var
        w = self.w
        e, ids, t = self.esqueleto_sin_receptividad()
        self.assertIsNone(e.nueva_variable("marcha"))
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "marcha")
        e.seleccionar([t])
        prog = w.props.prog
        prog.elegir_categoria("constante")
        uno, cero = prog.paleta.bloques()
        m = var("marcha")
        casos = [  # (gestos: dónde se suelta qué, texto, guardado, ¿franquea con marcha = 0?, ¿y con marcha = 1?)
            ([((), nuevo("y")), (("a",), uno), (("b",), m)], "1 AND marcha", "true AND marcha", False, True),
            ([((), nuevo("o")), (("a",), cero), (("b",), m)], "0 OR marcha", "false OR marcha", False, True),
            ([((), nuevo("o")), (("a",), m), (("b",), uno)], "marcha OR 1", "marcha OR true", True, True),
            ([((), nuevo("y")), (("a",), cero), (("b",), m)], "0 AND marcha", "false AND marcha", False, False),
            ([((), nuevo("no")), (("a",), cero)], "NOT 0", "NOT false", True, True),
            ([((), nuevo("no")), (("a",), uno)], "NOT 1", "NOT true", False, False),
            ([((), nuevo("o")), (("a",), nuevo("no", a=uno)), (("b",), m)], "NOT 1 OR marcha", "NOT true OR marcha", False, True),
            ([((), nuevo("y")), (("a",), nuevo("par", a=nuevo("o", a=cero, b=m))), (("b",), uno)], "(0 OR marcha) AND 1",
             "(false OR marcha) AND true", False, True),
        ]
        for gestos, texto, guardado, con0, con1 in casos:
            with self.subTest(texto):
                prog.lienzo.quitar(())  # la receptividad vacía
                for ruta, bloque in gestos:
                    prog.lienzo.soltar(ruta, bloque)
                self.assertEqual((prog.texto(), w.props.t_texto.text(), e.texto_condicion(t)), (texto, texto, guardado))
                self.assertEqual(arbol_a_texto(texto_a_arbol(texto, {"marcha": ("input", "bool")}, [])), texto, "ida y vuelta")
                self.assertTrue(e.ed.validate().can_simulate, [str(x) for x in e.ed.validate().diagnostics])
                for pulsar, franquea in ((False, con0), (True, con1)):
                    self.assertTrue(w.cambiar_modo("simular"))
                    if pulsar:
                        w._cambiar_tipo_entrada(vid, True)  # esta prueba mantiene la entrada
                        w.botones[vid].click()
                    self.assertEqual(w.v.state()["situation"], [ids["1" if franquea else "0"]],
                                     f"{texto} con marcha = {int(pulsar)}")
                    self.assertTrue(w.cambiar_modo("editar"))
                    e.seleccionar([t])


@unittest.skipUnless(QT, "PySide6 no está instalado")
class Bloques(unittest.TestCase):
    """El programador por bloques sin el panel: el modelo (texto <-> árbol, soltar, envolver, quitar), el área y la
    paleta."""
    VARS = {"marcha": ("input", "bool"), "paro": ("input", "bool"), "Q00": ("output", "bool"), "M1": ("internal", "bool"),
            "CT": ("internal", "int"), "Motor 1": ("output", "bool"), "T": ("input", "decimal")}
    ETAPAS = ["X0", "X1", "active(Inicio)"]

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def prog(self, **kw):
        from escritorio.bloques import Programador
        return Programador(lambda: (self.VARS, self.ETAPAS), **kw)

    def test_SEDI42_ida_y_vuelta_texto_arbol_texto(self):
        """REQ-EDT-02: el texto se vuelve árbol de bloques y el árbol vuelve al mismo texto, con paréntesis solo donde la
        precedencia lo exige; lo que no se representa con bloques es un bloque de texto y un «?» es un hueco."""
        from escritorio.bloques import arbol_a_texto, texto_a_arbol
        a = lambda t: texto_a_arbol(t, self.VARS, self.ETAPAS)  # noqa: E731
        for t in ("marcha", "↑marcha AND NOT paro", "NOT ↑marcha", "NOT NOT marcha", "NOT ↓(marcha AND paro)",
                  "marcha AND (paro AND Q00)", "marcha AND paro AND Q00", "marcha OR paro AND Q00",
                  "(marcha OR paro) AND Q00", "NOT (marcha OR X1) AND CT >= 3", "↑(marcha OR paro)", "↓(marcha AND paro)",
                  "X1", "X0 AND NOT X1", "active(Inicio)", "3s/X1", "X1/2s", "3s/X1/2s", "500ms/X1",
                  "3s/(marcha AND (paro OR Q00))", "3s/NOT marcha", "3s/↑marcha", "NOT (X1/2s)", "3s/X1 OR NOT marcha/2s",
                  "CT >= 3", "CT != 3", "CT < 3 OR CT = CT", "T <= 2.5", "NOT CT >= 3", "1", "0", "1 AND NOT 0",
                  "(↑marcha AND NOT X0) OR (3s/X1 AND CT >= 3)".replace("(", "").replace(")", ""),
                  "`Motor 1` AND marcha", "↑(`Motor 1`)", "nada", "nada AND marcha", "CT + 1 > 3", "CT = CT + 1",
                  "marcha AND ?", "NOT ?", "3s/?", "? AND ?", "↑?", "marcha AND (? OR paro)"):
            self.assertEqual(arbol_a_texto(a(t)), t, t)
        # la base de «temporizar» entre paréntesis salvo variable, etapa, constante o NOT/flanco directos sobre ellas
        for t in ("(↑↓marcha)/1s", "1s/(1s/marcha)", "(NOT (1s/marcha))/2s", "3s/↑marcha", "3s/NOT X1", "1s/1",
                  "T > 2s AND marcha", "CT > 1500ms", "T <= 2500us", "CT = true", "↑1"):
            self.assertEqual(arbol_a_texto(a(t)), t, t)
        from escritorio.bloques import nuevo
        sb = nuevo("sube", a=nuevo("baja", a=a("marcha")))
        for envuelto in (nuevo("temp", t1="", t2="1s", a=sb),
                         nuevo("temp", t1="1s", t2="", a=nuevo("temp", t1="", t2="2s", a=a("marcha"))),
                         nuevo("no", a=nuevo("temp", t1="3s", t2="", a=a("marcha"))),
                         nuevo("temp", t1="3s", t2="", a=nuevo("no", a=nuevo("sube", a=a("marcha"))))):
            txt = arbol_a_texto(envuelto)
            self.assertEqual(arbol_a_texto(a(txt)), txt, txt)
            self.assertEqual(a_nucleo(txt, [], ["marcha"]), a_nucleo(arbol_a_texto(a(txt)), [], ["marcha"]), txt)
        self.assertEqual(arbol_a_texto(nuevo("temp", t1="", t2="1s", a=sb)), "(↑↓marcha)/1s")
        # los paréntesis escritos se conservan como bloques «( )», también los que la precedencia no exige (P-IMP-46); los
        # espacios sobrantes, no
        self.assertEqual(arbol_a_texto(a("(marcha) AND   (paro OR (Q00 AND M1))")), "(marcha) AND (paro OR (Q00 AND M1))")
        self.assertEqual(arbol_a_texto(a("a AND ?")), "a AND ?")
        # la estructura
        y = a("(↑marcha AND NOT X0) OR (3s/X1 AND CT >= 3)")
        self.assertEqual((y["k"], y["a"]["k"], y["a"]["a"]["k"], y["a"]["a"]["a"]["k"], y["a"]["a"]["b"]["a"]["k"]),
                         ("o", "par", "y", "sube", "etapa"))
        t = y["b"]["a"]["a"]
        self.assertEqual((t["k"], t["t1"], t["t2"], t["a"]["n"]), ("temp", "3s", "", "X1"))
        c = y["b"]["a"]["b"]
        self.assertEqual((c["k"], c["n"], c["op"], c["v"]), ("cmp", "CT", ">=", "3"))
        self.assertEqual(a("X1/2s")["t2"], "2s")
        self.assertEqual(a("1.5s/X1")["t1"], "1500ms")
        self.assertEqual([a(x)["k"] for x in ("1", "0", "nada", "CT + 1 > 3", "marcha = 1", "X7", "CT")],
                         ["const", "const", "texto", "texto", "texto", "texto", "texto"])
        self.assertEqual(a("marcha AND paro")["a"], {"k": "var", "n": "marcha", "papel": "input"})
        self.assertEqual(a("Q00")["papel"], "output")
        self.assertEqual(a("M1")["papel"], "internal")
        self.assertIsNone(a("marcha AND ?")["b"])
        self.assertIsNone(a("?"))
        self.assertIsNone(a("  "))
        for malo in ("marcha AND", "(marcha", "marcha paro", "↑"):
            with self.assertRaises(ValueError):
                a(malo)
        # sin retardos, «temporizar» no cambia el texto; las etapas «E1» y «1» a la vez se distinguen
        from escritorio.bloques import nuevo
        self.assertEqual(arbol_a_texto(nuevo("temp", t1="", t2="", a=a("marcha OR paro"))), "marcha OR paro")
        doble = texto_a_arbol("active(`1`) AND X1", self.VARS, ["X1", "X1"])
        self.assertEqual((doble["a"]["k"], doble["b"]["k"]), ("texto", "etapa"))

    def test_SEDI50_soltar_envolver_sustituir_y_quitar(self):
        """REQ-EDT-02: un bloque suelto en un hueco lo encaja; uno que envuelve sobre un hueco ocupado deja el bloque que
        había en su primer hueco; uno simple lo sustituye; arrastrar fuera del área o a la papelera quita; el área vacía
        recibe la raíz."""
        from escritorio.bloques import nuevo, var
        p = self.prog()
        area, emitidos = p.lienzo, []
        p.cambiado.connect(emitidos.append)
        self.assertEqual(p.texto(), "")
        self.assertFalse(area.soltar(None, var("marcha")) is False, "sin raíz, el área vacía la recibe")
        self.assertEqual(p.texto(), "marcha")
        self.assertFalse(area.soltar(None, var("paro")), "con raíz, el área vacía no hace nada")
        self.assertEqual(emitidos, ["marcha"])
        area.soltar((), nuevo("y"))  # y sobre «marcha»: marcha entra en su primer hueco
        self.assertEqual(p.texto(), "marcha AND ?")
        area.soltar(("b",), var("paro"))  # un hueco vacío
        self.assertEqual(p.texto(), "marcha AND paro")
        area.soltar(("a",), nuevo("no"))  # envolver: marcha entra en «no»
        self.assertEqual(p.texto(), "NOT marcha AND paro")
        area.soltar(("a",), nuevo("baja"))
        self.assertEqual(p.texto(), "↓(NOT marcha) AND paro")
        area.soltar(("a", "a", "a"), nuevo("temp"))
        self.assertEqual(p.texto(), "↓(NOT 3s/marcha) AND paro".replace("NOT 3s/marcha", "NOT (3s/marcha)"))
        area.soltar(("b",), var("Q00", "output"))  # uno simple sobre uno ocupado: lo sustituye
        self.assertEqual(p.texto(), "↓(NOT (3s/marcha)) AND Q00")
        area.soltar((), nuevo("o"))  # envolver la raíz con «o»: todo entra en su primer hueco
        self.assertEqual(p.texto(), "↓(NOT (3s/marcha)) AND Q00 OR ?")
        area.soltar(("b",), nuevo("const", v=1))
        self.assertEqual(p.texto(), "↓(NOT (3s/marcha)) AND Q00 OR 1")
        area.soltar(("a",), nuevo("cmp", n="CT", op=">", v="2"))  # sustituye todo el «y»
        self.assertEqual(p.texto(), "CT > 2 OR 1")
        # un bloque que ya lleva algo y no tiene hueco no envuelve: sustituye
        lleno = nuevo("no", a=var("paro"))
        area.soltar(("a",), lleno)
        self.assertEqual(p.texto(), "NOT paro OR 1")
        # mover: sacarlo de su sitio (queda el hueco) y ponerlo en otro
        area.soltar(("b",), area.arbol["a"], origen=("a",))
        self.assertEqual(p.texto(), "? OR NOT paro")
        self.assertFalse(area.soltar(("b", "a"), area.arbol["b"], origen=("b",)), "sobre algo suyo: nada")
        self.assertEqual(p.texto(), "? OR NOT paro")
        # quitar: queda el hueco
        area.quitar(("b", "a"))
        self.assertEqual(p.texto(), "? OR NOT ?")
        area.quitar(("b",))
        self.assertEqual(p.texto(), "? OR ?")
        area.quitar(())
        self.assertEqual((p.texto(), area.arbol), ("", None))
        # la papelera: un bloque del área sale; de otro grupo o de la paleta, no
        area.soltar(None, nuevo("y", a=var("marcha"), b=var("paro")))
        p._a_la_papelera({"origen": ["b"], "grupo": "otro"})
        self.assertEqual(p.texto(), "marcha AND paro")
        p._a_la_papelera({"origen": None, "grupo": p.grupo})
        self.assertEqual(p.texto(), "marcha AND paro")
        p._a_la_papelera({"origen": ["b"], "grupo": p.grupo})
        self.assertEqual(p.texto(), "marcha AND ?")
        # y arrastrar fuera del área (sin papelera) quita lo mismo: `quitar` con la ruta de la superficie
        area.quitar((0, "a"))
        self.assertEqual(p.texto(), "? AND ?")
        self.assertEqual(emitidos[-1], "? AND ?")
        # el sitio bajo el puntero: el hueco o el bloque más interior
        from PySide6.QtCore import QPointF
        area.resize(300, 100)
        area._calcular(300)
        hueco_a = next(r for r, ruta, n in area._bloques if ruta == (0, "a"))
        self.assertEqual(area.ruta_en(hueco_a.center()), (0, "a"))
        self.assertEqual(area.ruta_en(QPointF(hueco_a.left() - 2, hueco_a.center().y())), (0,), "el borde del «y»")
        self.assertIsNone(area.ruta_en(QPointF(299, 99)))

    def test_SEDI51_desplegables_y_campos(self):
        """REQ-EDT-02: el desplegable de una variable ofrece las booleanas de su papel, el de una etapa todas las etapas y
        el de una comparación las variables no booleanas de cualquier papel; cambiarlos, y editar t1, t2 y el valor,
        cambia el texto."""
        from escritorio.bloques import nuevo, var
        p = self.prog()
        area = p.lienzo
        area.soltar(None, var("marcha"))
        n = area.arbol
        self.assertEqual([v for _, v in area.opciones_desplegable(n, "n")], ["marcha", "paro"], "entradas booleanas")
        area.elegir((), "n", "paro")
        self.assertEqual(p.texto(), "paro")
        area.soltar((), nuevo("etapa", n="X0"))
        self.assertEqual([v for _, v in area.opciones_desplegable(area.arbol, "n")], ["X0", "X1", "active(Inicio)"])
        area.elegir((), "n", "X1")
        self.assertEqual(p.texto(), "X1")
        area.soltar((), nuevo("temp"))
        self.assertEqual(p.texto(), "3s/X1")
        self.assertTrue(area.editar_campo((), "t1", "500 ms"))
        self.assertEqual(p.texto(), "500ms/X1")
        self.assertTrue(area.editar_campo((), "t2", "2s"))
        self.assertEqual(p.texto(), "500ms/X1/2s")
        self.assertTrue(area.editar_campo((), "t1", "0"))
        self.assertEqual(p.texto(), "X1/2s")
        self.assertTrue(area.editar_campo((), "t2", ""))
        self.assertEqual((p.texto(), area.arbol["k"]), ("X1", "temp"), "sin retardos el bloque sigue, y el texto no cambia")
        avisos = []
        area.avisa.connect(avisos.append)
        self.assertFalse(area.editar_campo((), "t1", "tres"))
        self.assertEqual((p.texto(), len(avisos)), ("X1", 1))
        area.quitar(())
        area.soltar(None, nuevo("cmp"))
        self.assertEqual(p.texto(), "? = 0")
        self.assertEqual([v for _, v in area.opciones_desplegable(area.arbol, "n")], ["CT", "T"], "no booleanas, de cualquier papel")
        self.assertEqual([t for t, _ in area.opciones_desplegable(area.arbol, "op")], ["=", "≠", "<", "≤", ">", "≥"])
        area.elegir((), "n", "CT")
        area.elegir((), "op", ">=")
        self.assertTrue(area.editar_campo((), "v", "3"))
        self.assertEqual(p.texto(), "CT >= 3")
        area.elegir((), "op", "!=")
        self.assertEqual(p.texto(), "CT != 3")
        self.assertTrue(area.editar_campo((), "v", ""))
        self.assertEqual(p.texto(), "CT != 0", "un valor vacío es 0")
        self.assertFalse(area.editar_campo((), "v", "3 AND"), "un valor que no se lee se rechaza")
        self.assertEqual(p.texto(), "CT != 0")
        n_avisos = len(avisos)
        for malo in ("a AND b", "marcha OR paro", "NOT marcha", "T > 2", "CT = CT"):
            self.assertFalse(area.editar_campo((), "v", malo), malo + ": no es un operando numérico")
        self.assertEqual((p.texto(), len(avisos)), ("CT != 0", n_avisos + 5))
        for bueno in ("CT + 1", "T", "2.5", "2s", "(CT + 1)"):
            self.assertTrue(area.editar_campo((), "v", bueno), bueno)
        self.assertEqual(p.texto(), "CT != (CT + 1)", "el valor se escribe tal cual")
        area.quitar(())
        area.soltar(None, nuevo("texto", s="nada"))
        self.assertTrue(area.editar_campo((), "s", "CT + 1 > 3"))
        self.assertEqual(p.texto(), "CT + 1 > 3")

    def test_SEDI54_paleta_por_categorias(self):
        """REQ-EDT-02, REQ-EDT-07: cinco categorías con su color (las constantes 1 y 0, en la suya); las memorias
        son las variables de papel «internal»; sus desplegables se llenan con las variables y etapas del modelo."""
        from escritorio.bloques import CATEGORIAS, COLORES, PAPEL
        p = self.prog()
        self.assertEqual([t for _, t in CATEGORIAS],
                         ["Variables", "Operadores", "Temporizadores", "Comparaciones", "Constantes"])
        self.assertEqual(len({COLORES[c] for c, _ in CATEGORIAS if c != "variables"}), 4)
        self.assertEqual(PAPEL["interna"], "internal")
        self.assertEqual([b.toolTip() for b in p.categorias.values()], [t for _, t in CATEGORIAS])
        # una ficha por elemento (etapas por número, variables por nombre), ya elegido; las comparaciones, un bloque
        esperado = {"entrada": [("var", "marcha", "input"), ("var", "paro", "input")],
                    "salida": [("var", "Motor 1", "output"), ("var", "Q00", "output")],
                    "interna": [("var", "M1", "internal")],
                    "etapa": [("etapa", "X0", None), ("etapa", "X1", None), ("etapa", "active(Inicio)", None)],
                    "comparacion": [("cmp", "CT", None)]}
        combinado = sum((esperado[c] for c in ("entrada", "etapa", "interna", "salida")), [])
        for clave, fichas in (("variables", combinado), ("comparacion", esperado["comparacion"])):
            p.elegir_categoria(clave)
            self.assertEqual([(b["k"], b["n"], b.get("papel")) for b in p.paleta.bloques()], fichas)
            self.assertTrue(p.categorias[clave].isChecked())
        p.elegir_categoria("operador")
        self.assertEqual([b["k"] for b in p.paleta.bloques()], ["y", "o", "no", "par", "sube", "baja"],
                         "con el bloque «( )» (P-IMP-46); las constantes ya no van entre los operadores")
        p.elegir_categoria("constante")
        self.assertEqual([(b["k"], b["v"]) for b in p.paleta.bloques()], [("const", 1), ("const", 0)])
        p.elegir_categoria("tiempo")
        self.assertEqual([(b["k"], b["t1"], b["t2"]) for b in p.paleta.bloques()], [("temp", "3s", "")])
        self.assertEqual(p.opciones("interna"), [("M1", "M1")], "las memorias booleanas")
        self.assertEqual(p.opciones("etapa"), [("X0", "X0"), ("X1", "X1"), ("XInicio", "active(Inicio)")], "se ve «XInicio»; lo que se guarda es active(Inicio)")
        # las fichas de elementos no llevan desplegable (▾); lo escrito en el temporizador se conserva
        p.elegir_categoria("variables")
        self.assertFalse([x for x in p.paleta._piezas if x[1] == "drop"])
        p.elegir_categoria("tiempo")
        p.paleta.editar_campo((0,), "t1", "1s")
        p.elegir_categoria("tiempo")
        self.assertEqual(p.paleta.bloques()[0]["t1"], "1s")
        # Sin variables ni etapas: sin fichas vacías.
        from escritorio.bloques import Programador
        vacio = Programador(lambda: ({}, []))
        self.assertEqual(vacio.paleta.bloques(), [])
        # el modelo cambia (se crea una memoria): la paleta se llena otra vez
        self.VARS = {**self.VARS, "M2": ("internal", "bool")}
        p.elegir_categoria("variables")
        self.assertEqual(p.opciones("interna"), [("M1", "M1"), ("M2", "M2")])
        memorias = [b["n"] for b in p.paleta.bloques() if b.get("papel") == "internal"]
        self.assertEqual(memorias, ["M1", "M2"], "la paleta se llena otra vez")

    def test_SEDI64_categorias_horizontales_y_bloques_en_columna(self):
        """REQ-EDT-02: categorías en una franja horizontal (las cinco, con su color), debajo la columna de
        bloques de la categoría elegida (uno debajo de otro) y, ocupando el resto, el área de trabajo con la papelera."""
        from PySide6.QtWidgets import QPushButton
        p = self.prog()
        p.resize(900, 300)
        p.show()
        QApplication.processEvents()
        bs = list(p.categorias.values())
        self.assertEqual(len(bs), 5)
        self.assertTrue(all(isinstance(b, QPushButton) and not b.icon().isNull() for b in bs))
        pos = [b.mapTo(p, b.rect().topLeft()) for b in bs]
        self.assertEqual(len({q.y() for q in pos}), 1, "categorías en una franja horizontal")
        self.assertEqual(sorted(q.x() for q in pos), [q.x() for q in pos], "orden de izquierda a derecha")
        self.assertGreater(p.paleta.mapTo(p, p.paleta.rect().topLeft()).y(), pos[0].y() + bs[0].height(),
                           "las fichas, debajo de las categorías")
        self.assertGreater(p.lienzo.mapTo(p, p.lienzo.rect().topLeft()).x(),
                           p.paleta.mapTo(p, p.paleta.rect().topLeft()).x(), "y el área, a la derecha de la paleta")
        self.assertGreater(p.lienzo.width(), 300, "el área ocupa el resto")
        p.elegir_categoria("operador")
        QApplication.processEvents()
        cajas = sorted(p.paleta._cajas, key=lambda c: c[2])
        self.assertEqual(len(cajas), 6, "y, o, no, ( ) y los flancos")
        self.assertEqual(len({x for _, x, _ in cajas}), 1, "los bloques, en una columna")
        self.assertEqual([c[2] for c in cajas], sorted({y for _, _, y in cajas}), "uno debajo de otro")
        p.elegir_categoria("constante")
        QApplication.processEvents()
        self.assertEqual(len(p.paleta._cajas), 2, "las constantes 1 y 0, en su carpeta y a la vista sin desplazarse")
        p.elegir_categoria("comparacion")
        self.assertEqual([b["k"] for b in p.paleta.bloques()], ["cmp"], "elegir una carpeta muestra sus bloques")
        self.assertTrue(p.categorias["comparacion"].isChecked())
        # con fórmula larga: en línea si cabe, apilada si no
        p.poner("(↑marcha AND NOT X0) OR (3s/X1 AND CT >= 3)")
        a = p.lienzo
        self.assertLess(a.heightForWidth(900), a.heightForWidth(250))
        self.assertTrue(p.papelera.isVisible())
        p.close()

    def test_SEDI56_cabe_a_200_px_y_crece_en_alto(self):
        """REQ-EDT-02: el área y la paleta caben a 200 px sin barra horizontal; el área crece en alto al estrecharse y
        los bloques se apilan; la paleta suelta (en línea, no la del programador) pasa de línea."""
        from escritorio.bloques import AreaBloques, PaletaBloques
        p = self.prog()
        p.poner("(↑marcha AND NOT X0) OR (3s/X1 AND CT >= 3)")
        self.assertLessEqual(p.paleta.minimumSizeHint().width(), 200)
        area = p.lienzo
        self.assertTrue(area.hasHeightForWidth())
        h = {w: area.heightForWidth(w) for w in (200, 260, 330, 700, 1000)}
        self.assertGreater(h[200], h[330], h)
        self.assertGreater(h[330], h[1000], h)
        for w in (200, 250, 330, 700):
            self.assertLessEqual(area.ancho_necesario(w), w, f"a {w} px los bloques no se salen")
        p.elegir_categoria("operador")
        suelta = PaletaBloques(lambda: (self.VARS, self.ETAPAS))
        suelta.cargar("operador")
        self.assertGreater(suelta.heightForWidth(200), suelta.heightForWidth(700), "la paleta en línea pasa de línea")
        self.assertLessEqual(p.paleta.ancho_necesario(200), 200)
        p.elegir_categoria("tiempo")
        self.assertLessEqual(p.paleta.ancho_necesario(200), 200, "el bloque temporizar también cabe")
        # una pila profunda de «y» a 200 px
        profundo = " AND ".join(f"(marcha OR NOT paro AND Q00 AND X{i % 2})" for i in range(4))
        p.poner(profundo)
        self.assertLessEqual(area.ancho_necesario(200), 200)
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        w = QWidget()
        w.resize(200, 400)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        sola = AreaBloques(lambda: (self.VARS, self.ETAPAS))  # un área suelta, a 200 px
        sola.poner_arbol(area.arbol)
        lay.addWidget(sola)
        w.show()
        QApplication.processEvents()
        self.assertEqual(sola.width(), 200)
        self.assertGreaterEqual(sola.height(), sola.heightForWidth(200))
        w.close()

    def test_SEDI57_raton_clic_en_piezas_y_arrastres_recibidos(self):
        """REQ-EDT-02: un clic en un desplegable abre su menú y en un campo, su editor (Intro aplica, Esc descarta);
        pulsar y mover sobre un bloque lo arrastra; el área recibe los arrastres (resaltando el hueco destino), la papelera
        quita lo que viene del área y un bloque de otro grupo se copia."""
        import json
        from PySide6.QtCore import QMimeData, QPointF
        from PySide6.QtGui import QDragMoveEvent, QDropEvent
        from escritorio import bloques
        p = self.prog()
        p.resize(300, 500)
        p.show()
        p.poner("3s/marcha AND CT >= 3")
        QApplication.processEvents()
        a = p.lienzo
        a._calcular(a.width())
        pieza = lambda clave, tipo: next(x for x in a._piezas if x[1] == tipo and x[3] == clave)  # noqa: E731
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=pieza("t1", "campo")[0].center().toPoint())
        self.assertEqual(a._editor.text(), "3s")
        a._editor.setText("2s")
        a._editor.editingFinished.emit()
        self.assertEqual((p.texto(), a._editor), ("2s/marcha AND CT >= 3", None))
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=pieza("v", "campo")[0].center().toPoint())
        a._editor.setText("9")
        a._editor.cancelado.emit()  # Esc: se descarta
        self.assertEqual(p.texto(), "2s/marcha AND CT >= 3")
        menus = []

        class Menu(bloques.QMenu):  # el menú real se queda esperando: se elige la tercera opción
            def exec(self, *args):
                menus.append([x.text() for x in self.actions()])
                self.actions()[2].trigger()
        with mock.patch.object(bloques, "QMenu", Menu):
            QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=pieza("op", "drop")[0].center().toPoint())
        self.assertEqual((menus, p.texto()), ([["=", "≠", "<", "≤", ">", "≥"]], "2s/marcha AND CT < 3"))
        # pulsar y mover sobre un bloque lo arrastra (el arrastre en sí no se puede simular)
        arrastres = []
        with mock.patch.object(a, "_arrastrar", lambda ruta: arrastres.append(ruta)):
            r = next(x for x in a._bloques if x[1] == (0, "b"))[0]
            QTest.mousePress(a, Qt.MouseButton.LeftButton, pos=(r.topLeft() + QPointF(3, 13)).toPoint())
            QTest.mouseMove(a, (r.topLeft() + QPointF(30, 40)).toPoint())
        self.assertEqual(arrastres, [(0, "b")])
        self.assertGreater(a.motor.pixmap(a.arbol).width(), 20, "la imagen que se lleva el puntero")

        def mime(nodo, grupo, origen):
            m = QMimeData()
            m.setData(bloques.MIME, json.dumps({"nodo": nodo, "grupo": grupo, "origen": origen}).encode())
            return m
        centro_ = lambda ruta: next(x for x in a._bloques if x[1] == ruta)[0].center()  # noqa: E731
        m = mime(bloques.var("paro"), "otro", None)
        with warnings.catch_warnings():  # el constructor con QPoint está marcado como obsoleto, pero es el que existe
            warnings.simplefilter("ignore", DeprecationWarning)
            a.dragMoveEvent(QDragMoveEvent(centro_((0, "a", "a")).toPoint(), Qt.DropAction.CopyAction, m,
                                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(a._objetivo, (0, "a", "a"), "el hueco destino se resalta")
        bloques._ARRASTRE["resuelto"] = False
        a.dropEvent(QDropEvent(centro_((0, "a", "a")), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier))
        self.assertEqual((p.texto(), a._objetivo, bloques._ARRASTRE["resuelto"]), ("2s/paro AND CT < 3", None, True))
        # del área al área, con su origen: se mueve
        a._calcular(a.width())
        m = mime(a.arbol["b"], p.grupo, ["b"])
        a.dropEvent(QDropEvent(centro_((0, "a", "a")), Qt.DropAction.MoveAction, m, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier))
        self.assertEqual(p.texto(), "2s/(CT < 3) AND ?")
        # de otro grupo, con origen: se copia y no se quita nada
        m = mime(bloques.var("marcha"), "otro", ["a"])
        a.dropEvent(QDropEvent(centro_((0, "b")), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier))
        self.assertEqual(p.texto(), "2s/(CT < 3) AND marcha")
        # la papelera
        m = mime(a.arbol["a"], p.grupo, ["a"])
        p.papelera.dropEvent(QDropEvent(QPointF(5, 5), Qt.DropAction.MoveAction, m, Qt.MouseButton.LeftButton,
                                        Qt.KeyboardModifier.NoModifier))
        self.assertEqual(p.texto(), "? AND marcha")
        # el área vacía recibe un bloque como raíz
        a.quitar(())
        a._calcular(a.width())
        m = mime(bloques.nuevo("no"), "x", None)  # el evento no es dueño del mime
        a.dropEvent(QDropEvent(QPointF(20, 20), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier))
        self.assertEqual(p.texto(), "NOT ?")
        p.close()

    def test_SEDI97_y_y_o_de_varias_entradas(self):
        """REQ-EDT-02: los bloques «y» y «o» llevan un «+» al final que añade otro hueco (sin «×»: un hueco vacío
        sobrante se quita con el botón derecho o con Supr, y al sacar un bloque su hueco desaparece); soltar un bloque sobre el «+» lo añade en un hueco nuevo; un «o» de n operandos se
        escribe `a OR b OR c OR d` y una cadena de OR (o de AND) del mismo nivel vuelve como un solo bloque de n huecos;
        el texto es estable y los paréntesis salen donde la precedencia los exige y donde hay un bloque «( )»."""
        import json
        from PySide6.QtCore import QMimeData, QPointF
        from PySide6.QtGui import QContextMenuEvent, QDropEvent
        from escritorio import bloques
        from escritorio.bloques import (anadir_hueco, arbol_a_texto, hijos, mover, nuevo, quitar_hueco, retirar,
                                        soltar_en_mas, texto_a_arbol, var)
        a = lambda t: texto_a_arbol(t, self.VARS, self.ETAPAS)  # noqa: E731
        # texto -> árbol: una cadena del mismo operador es un solo bloque
        o4 = a("marcha OR paro OR Q00 OR M1")
        self.assertEqual((o4["k"], hijos(o4), [o4[c]["n"] for c in hijos(o4)]), ("o", ("a", "b", "c", "d"), ["marcha", "paro", "Q00", "M1"]))
        y4 = a("marcha AND paro AND Q00 AND X1")
        self.assertEqual((y4["k"], hijos(y4), y4["d"]["k"]), ("y", ("a", "b", "c", "d"), "etapa"))
        self.assertEqual((hijos(a("marcha OR paro")), hijos(a("marcha"))), (("a", "b"), ()))
        # y un grupo explícito a la derecha sigue siendo un bloque dentro de otro, con sus paréntesis
        anidado = a("marcha OR (paro OR Q00 OR M1)")
        self.assertEqual((hijos(anidado), anidado["b"]["k"], anidado["b"]["a"]["k"], hijos(anidado["b"]["a"])),
                         (("a", "b"), "par", "o", ("a", "b", "c")))
        # árbol -> texto estable, con paréntesis solo donde la precedencia los exige
        for t in ("marcha OR paro OR Q00 OR M1", "marcha AND paro AND Q00 AND X1", "marcha OR (paro OR Q00 OR M1)",
                  "marcha AND (paro AND Q00 AND X1)", "(marcha OR paro) AND Q00 AND (M1 OR X1 OR CT >= 3)",
                  "marcha AND paro OR Q00 AND M1 OR X1", "NOT marcha OR NOT paro OR ↑Q00", "marcha OR ? OR paro",
                  "marcha AND ? AND ? AND paro"):
            self.assertEqual(arbol_a_texto(a(t)), t, t)
            self.assertEqual(arbol_a_texto(a(arbol_a_texto(a(t)))), arbol_a_texto(a(t)), "estable")
        self.assertEqual(arbol_a_texto(a("(marcha OR paro) OR Q00")), "(marcha OR paro) OR Q00",
                         "un grupo escrito es un bloque «( )» y se conserva (P-IMP-46)")
        self.assertEqual(arbol_a_texto(a("(marcha AND paro) OR (Q00 AND M1) OR X1 AND CT < 3")),
                         "(marcha AND paro) OR (Q00 AND M1) OR X1 AND CT < 3", "también los que la precedencia no exige")
        # añadir y quitar huecos
        base = a("marcha OR paro")
        tres = anadir_hueco(base, ())
        self.assertEqual((arbol_a_texto(tres), hijos(tres)), ("marcha OR paro OR ?", ("a", "b", "c")))
        self.assertEqual(arbol_a_texto(anadir_hueco(tres, ())), "marcha OR paro OR ? OR ?")
        simple = var("marcha")
        self.assertIs(anadir_hueco(simple, ()), simple, "solo en «y» y «o»")
        self.assertEqual(arbol_a_texto(quitar_hueco(tres, (), "c")), "marcha OR paro")
        self.assertEqual(arbol_a_texto(quitar_hueco(anadir_hueco(tres, ()), (), "c")), "marcha OR paro OR ?")
        self.assertEqual(arbol_a_texto(quitar_hueco(base, (), "b")), "marcha OR paro", "sin bajar de dos")
        lleno = a("marcha OR paro OR Q00")
        self.assertEqual(arbol_a_texto(quitar_hueco(lleno, (), "c")), "marcha OR paro OR Q00", "solo los vacíos")
        medio = {**lleno, "b": None}
        self.assertEqual(arbol_a_texto(quitar_hueco(medio, (), "b")), "marcha OR Q00", "los de detrás ocupan su sitio")
        self.assertEqual(arbol_a_texto(soltar_en_mas(base, (), var("Q00", "output"))), "marcha OR paro OR Q00")
        mov = soltar_en_mas(a("NOT marcha AND paro"), (), a("NOT marcha")["a"], origen=("a", "a"))
        self.assertEqual(arbol_a_texto(mov), "NOT ? AND paro AND marcha")
        # sacar un bloque de un «y»/«o» de más de dos huecos (arrastrándolo fuera o a otro sitio) quita su hueco
        self.assertEqual(arbol_a_texto(retirar(lleno, ("b",))), "marcha OR Q00")
        self.assertEqual(arbol_a_texto(retirar(base, ("b",))), "marcha OR ?", "con dos, el hueco se queda")
        self.assertEqual(arbol_a_texto(retirar(a("NOT marcha AND paro"), ("a", "a"))), "NOT ? AND paro")
        self.assertEqual(arbol_a_texto(mover(a("marcha OR paro OR Q00 OR M1"), ("b",), ("d",))), "marcha OR Q00 OR paro",
                         "el destino se resuelve antes de quitar el hueco de origen")
        self.assertEqual(arbol_a_texto(mover(a("(marcha OR paro OR Q00) AND M1"), ("a", "a", "b"), ("b",))),
                         "(marcha OR Q00) AND paro", "los de detrás ocupan el sitio")
        for n in range(30):
            base = anadir_hueco(base, ())
        self.assertEqual(len(hijos(base)), bloques.MAX_ENTRADAS)
        # el área: el «+» es una pieza de la superficie (sin «×» en los huecos)
        p = self.prog()
        p.resize(500, 300)
        p.show()
        p.poner("marcha OR paro")
        QApplication.processEvents()
        area = p.lienzo
        area._calcular(area.width())
        botones = lambda: [x for x in area._piezas if x[1] == "boton"]  # noqa: E731
        self.assertEqual([x[3] for x in botones()], ["mas"])
        emitidos = []
        p.cambiado.connect(emitidos.append)
        QTest.mouseClick(area, Qt.MouseButton.LeftButton, pos=botones()[0][0].center().toPoint())
        self.assertEqual((p.texto(), emitidos), ("marcha OR paro OR ?", ["marcha OR paro OR ?"]))
        self.assertEqual([x[3] for x in botones()], ["mas"], "solo el «+»: sin «×» en cada hueco")
        QTest.mouseClick(area, Qt.MouseButton.LeftButton, pos=botones()[-1][0].center().toPoint())
        self.assertEqual(p.texto(), "marcha OR paro OR ? OR ?")
        # un hueco vacío sobrante: se selecciona y Supr lo quita (el atajo de la ventana no se lo lleva)
        hueco = lambda c: next(r for r, ruta, n in area._bloques if ruta == (0, c))  # noqa: E731
        QTest.mouseClick(area, Qt.MouseButton.LeftButton, pos=hueco("d").center().toPoint())
        self.assertEqual(area._hueco_sel, (0, "d"))
        QTest.keyClick(area, Qt.Key.Key_Delete)
        self.assertEqual(p.texto(), "marcha OR paro OR ?")
        # y con el botón derecho → «Quitar hueco»
        self.assertTrue(area.hueco_quitable((0, "c")))
        self.assertFalse(area.hueco_quitable((0, "a")), "ocupado: no es un hueco")
        with mock.patch("escritorio.bloques.QMenu") as menu:
            area.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, hueco("c").center().toPoint(),
                                                    area.mapToGlobal(hueco("c").center().toPoint())))
            texto, accion = menu.return_value.addAction.call_args[0]
        self.assertEqual(texto, "Quitar hueco")
        accion()
        self.assertEqual(p.texto(), "marcha OR paro", "nunca baja de dos")
        self.assertFalse(area.hueco_quitable((0, "b")))
        QTest.mouseClick(area, Qt.MouseButton.LeftButton, pos=botones()[-1][0].center().toPoint())
        self.assertEqual(p.texto(), "marcha OR paro OR ?")
        self.assertEqual(len(p._pila), 0, "sin historial local: lo deshace quien lo usa")
        # pulsar un botón y mover no arrastra el bloque
        arrastres = []
        with mock.patch.object(area, "_arrastrar", lambda ruta: arrastres.append(ruta)):
            c = botones()[-1][0].center()
            QTest.mousePress(area, Qt.MouseButton.LeftButton, pos=c.toPoint())
            QTest.mouseMove(area, (c + QPointF(30, 30)).toPoint())
        self.assertEqual(arrastres, [])
        # soltar un bloque sobre el «+»: en un hueco nuevo, también uno del área
        def mime(nodo, grupo, origen):
            m = QMimeData()
            m.setData(bloques.MIME, json.dumps({"nodo": nodo, "grupo": grupo, "origen": origen}).encode())
            return m
        mas = botones()[-1][0].center()
        m = mime(var("M1", "internal"), "otro", None)
        from PySide6.QtGui import QDragMoveEvent
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            area.dragMoveEvent(QDragMoveEvent(mas.toPoint(), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                                              Qt.KeyboardModifier.NoModifier))
        self.assertEqual((area._objetivo, area._resalte_mas is not None), (None, True), "el «+» se resalta, no el bloque")
        area.dropEvent(QDropEvent(mas, Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(p.texto(), "marcha OR paro OR ? OR M1")
        area._calcular(area.width())
        mas = botones()[-1][0].center()
        m = mime(area.arbol["a"], p.grupo, ["a"])
        area.dropEvent(QDropEvent(mas, Qt.DropAction.MoveAction, m, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(p.texto(), "paro OR ? OR M1 OR marcha", "movido desde el área: su hueco desaparece")
        # el texto vuelve a bloques con n huecos, y «Escribir» y los bloques coinciden
        p.poner("marcha OR paro OR Q00 OR M1 OR X1")
        self.assertEqual((p.lienzo.arbol["k"], hijos(p.lienzo.arbol), p.texto()),
                         ("o", ("a", "b", "c", "d", "e"), "marcha OR paro OR Q00 OR M1 OR X1"))
        # en la paleta no hay botones
        self.assertFalse(p.paleta.motor.botones)
        p.elegir_categoria("operador")
        self.assertFalse([x for x in p.paleta._piezas if x[1] == "boton"])
        p.close()


if __name__ == "__main__":
    unittest.main()
