"""Editor de escritorio (P-IMP-32, paso 3): crear un grafcet secuencial con el ratón, enlazarlo, moverlo, borrarlo,
deshacer, guardarlo, abrirlo y simularlo.

Las pruebas del núcleo (S-EDI01..02) no necesitan Qt. Las de la interfaz (S-EDI03..20) se omiten si PySide6 no está
instalado y usan la plataforma «offscreen»: no abren ventanas ni diálogos (los ganchos y los mensajes se sustituyen).
Ninguna es oráculo del documento 11: comprueban que el editor usa las operaciones de grafcet/editor.py y que lo
que se dibuja y se simula es lo que decide el núcleo.
"""
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
    from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QSettings, Qt
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
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from escritorio.ventana import Ventana
        self.w = Ventana(QSettings(str(Path(self.tmp.name) / "a.ini"), QSettings.Format.IniFormat),
                         Path(self.tmp.name) / "recup")

    def tearDown(self):
        self.w.a_ejecutar.setChecked(False)
        self.w.edicion = None  # sin preguntar al cerrar
        self.w.deleteLater()
        self.tmp.cleanup()

    # -- el grafcet de la validación: E0 -marcha-> E1 -paro-> E0 ---------------------------------------
    def secuencial(self, w=None):
        """Lo construye con los gestos del ratón sobre el controlador: etapa inicial, transición, etapa..."""
        w = w or self.w
        w.nuevo()
        e = w.edicion

        def clic(h, x, y):
            e.herramienta = h
            e.prensar(QPointF(100 + x, y))
            e.soltar(QPointF(100 + x, y))

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
        self.assertEqual({t["label"]: t["cond"] for t in e.M["transitions"]}["t1"], [{"t": "marcha"}])
        self.assertEqual(e.ed.get(ids["0"])["initial"], True)
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.modo, "simular")
        self.assertEqual(w.v.state()["situation"], [ids["0"]])
        self.assertEqual(sorted(w.botones.values(), key=lambda b: b.text())[0].text(), "marcha = 0")
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w.botones[nombre["marcha"]].click()
        self.assertEqual(w.v.state()["situation"], [ids["1"]])
        w.botones[nombre["marcha"]].click()  # se suelta: con marcha y paro a 1, E0 y E1 se alternarían sin fin
        w.botones[nombre["paro"]].click()
        self.assertEqual(w.v.state()["situation"], [ids["0"]])
        # Editar y simular otra vez: ejecución nueva, desde la situación inicial
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
        with mock.patch("escritorio.ventana.QFileDialog.getExistingDirectory", return_value=str(dest.parent)):
            self.assertTrue(w.guardar())
        self.assertFalse(e.ed.dirty)
        dest = e.ruta
        self.assertTrue((dest / "manifest.json").exists())
        op = open_model(dest)
        self.assertTrue(op.executable)
        self.assertEqual(layout_from_presentation(op.presentations[0])[ids["1"]], (240.0, 220.0))
        self.assertTrue(w.abrir_ruta(dest))
        self.assertEqual(w.v.state()["situation"], [ids["0"]])
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w.botones[nombre["marcha"]].click()
        self.assertEqual(w.v.state()["situation"], [ids["1"]])
        # Editar el modelo abierto: copia con sus posiciones y, al guardar, en su misma carpeta
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual(w.edicion.ruta, dest)
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
        e.prensar(punto(ids["0"], "abajo"))
        e.soltar(punto(ids["1"], "arriba"))
        self.assertEqual(len(e.M["drafts"]), 1)
        self.assertIn("D-ALTERNANCIA", e.mensaje)
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
        self.assertIn("ya existe", e.renombrar(ids["1"], "0"))
        self.assertIsNone(e.renombrar(ids["1"], "Marcha"))
        self.assertEqual({s["id"]: s["label"] for s in e.M["steps"]}[ids["1"]], "Marcha")
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
        self.assertIsNone(w.edicion)
        self.assertEqual((w.modo, w.v.key), ("simular", "temporizada"))
        del pregunta

    def test_SEDI09_recuperacion_automatica(self):
        """REQ-EDT-10: con cambios sin guardar se copia la edición cada 30 s y se ofrece recuperarla; guardar la borra."""
        from PySide6.QtWidgets import QMessageBox
        w = self.w
        self.assertFalse(w.autoguardar(100), "sin edición no hay nada que copiar")
        e, ids, ts = self.secuencial()
        self.assertTrue(w.autoguardar(100.0))
        self.assertFalse(w.autoguardar(110.0), "antes de 30 s no repite")
        self.assertTrue(w.autoguardar(131.0))
        self.assertEqual(w.recup.available()["revision"], e.ed.revision)
        e.edicion = None
        with mock.patch("escritorio.ventana.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            w.edicion = None
            self.assertTrue(w.ofrecer_recuperacion())
        r = w.edicion
        self.assertEqual(sorted(s["label"] for s in r.M["steps"]), ["0", "1"])
        self.assertTrue(r.ed.dirty)
        self.assertTrue(r.ed.validate().can_simulate)
        with mock.patch("escritorio.ventana.QFileDialog.getExistingDirectory", return_value=self.tmp.name):
            self.assertTrue(w.guardar())
        self.assertIsNone(w.recup.available())

    def test_SEDI10_el_ratón_real_y_el_dibujo(self):
        """REQ-EDT-02, REQ-EDT-03: los clics del ratón sobre el dibujo llegan al editor; la selección y las marcas se
        dibujan; el dibujo del editor es el de la simulación (mismos textos)."""
        w = self.w
        w.nuevo()
        e, d = w.edicion, w.diagrama
        self.assertIs(d.controlador, e)
        self.assertEqual((d.dragMode(), d.rejilla), (d.DragMode.NoDrag, True))
        w.herramienta("etapa")
        QTest.mouseClick(d.viewport(), Qt.MouseButton.LeftButton, pos=d.mapFromScene(QPointF(213, 97)))
        self.assertEqual([(s["label"], s["x"], s["y"]) for s in e.M["steps"]], [("0", 120.0, 100.0)])
        w.herramienta("seleccionar")
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
        self.assertEqual(len(w.diagrama._marcas), 2)
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
        self.assertEqual([w.paleta.item(i).text() for i in range(w.paleta.count())], ["Etapa", "Transición", "Simultaneidad", "Acción"],
                         "Seleccionar no es un elemento y la etapa inicial es una etapa con otro tipo")
        pedidas = []
        e.pedir_condicion = pedidas.append
        self.assertEqual(w.paleta.mimeData([w.paleta.item(1)]).text(), "transicion")
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
        w.paleta.setCurrentRow(0)
        self.assertEqual(e.herramienta, "etapa")
        e.prensar(QPointF(500, 60))  # una vez colocada, vuelve a no haber herramienta
        self.assertEqual((e.herramienta, len(e.M["steps"]), w.paleta.currentRow()), ("seleccionar", 3, -1))

    def test_SEDI13_propiedades_de_la_etapa(self):
        """REQ-EDT-02: al seleccionar una etapa, el panel de la izquierda muestra su etiqueta y su tipo, editables."""
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ids["1"]])
        p = w.props
        self.assertEqual((p.pila.currentIndex(), p.s_etiqueta.text(), p.s_tipo.currentText()), (1, "1", "Normal"))
        p.s_etiqueta.setText("Marcha")
        p.s_etiqueta.editingFinished.emit()
        self.assertEqual(e.nombres[ids["1"]], "Marcha")
        p.s_etiqueta.setText("0")  # ya existe
        p.s_etiqueta.editingFinished.emit()
        self.assertIn("ya existe", p.msg.text())
        self.assertEqual(p.s_etiqueta.text(), "Marcha")
        p.s_tipo.setCurrentIndex(1)
        p.s_tipo.activated.emit(1)
        self.assertTrue(e.ed.get(ids["1"])["initial"])
        e.seleccionar([])
        self.assertEqual(p.pila.currentIndex(), 0)

    def test_SEDI14_propiedades_de_la_transicion(self):
        """REQ-EDT-02, REQ-EDT-09: la receptividad se arma con botones, variables, comparaciones y temporizadores; lo que
        no existe se ve en naranja y se crea con un boton; la etiqueta puede ocultarse (y se guarda)."""
        from escritorio.propiedades import NARANJA
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ts["t2"]])
        p = w.props
        self.assertEqual((p.pila.currentIndex(), p.t_texto.text(), p.t_etiqueta.text()), (2, "paro", "t2"))
        p.t_texto.clear()
        p._prefijar("NOT ")
        p._prefijar("↑")
        p._insertar("marcha")
        self.assertEqual(normalizar_espacios(p.t_texto.text()), "NOT ↑marcha")
        self.assertTrue(p.t_texto.text().startswith(" ") and p.t_texto.text().endswith(" "), "cada inserción, entre espacios")
        p.t_texto.editingFinished.emit()
        self.assertEqual(e.texto_condicion(ts["t2"]), "NOT rise(marcha)", "el núcleo guarda su sintaxis")
        self.assertEqual(p.t_texto.text(), "NOT ↑marcha", "y el panel la muestra con flechas")
        # NOT sobre un texto seleccionado: NOT y, entre paréntesis, la selección
        p.t_texto.setText("marcha AND paro")
        p.t_texto.selectAll()
        p._prefijar("NOT ")
        self.assertEqual(normalizar_espacios(p.t_texto.text()), "NOT (marcha AND paro)")
        p.t_texto.setText("marcha AND  paro")
        p.t_texto.setSelection(12, 4)
        p._prefijar("↓")
        self.assertEqual(normalizar_espacios(p.t_texto.text()), "marcha AND ↓paro")
        p.t_texto.setText("NOT ↑marcha")
        p.t_texto.editingFinished.emit()
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
        p.t_texto.setText("X1 AND  ↑marcha")
        p.t_texto.editingFinished.emit()
        self.assertEqual(e.texto_condicion(ts["t2"]), "active(`1`) AND rise(marcha)", "espacios normalizados")
        self.assertEqual(p.t_texto.text(), "X1 AND ↑marcha")
        p.t_texto.setText("paro")
        p.t_texto.editingFinished.emit()
        # Receptividad vacia o mal escrita: no compila y lo dice
        p.t_texto.setText("marcha AND")
        p.t_texto.editingFinished.emit()
        self.assertIn("t2", "; ".join(e.resumen(e.diagnosticos())))
        # Etiqueta oculta: no se dibuja y se conserva al guardar y abrir
        e.poner_condicion(ts["t2"], "paro")

        def textos():
            return [it.toPlainText() for it in w.diagrama.scene().items() if hasattr(it, "toPlainText")]
        self.assertIn("(t2)", textos())
        p.t_mostrar.click()  # desmarca
        self.assertNotIn("(t2)", textos())
        self.assertIn("(t1)", textos())
        with mock.patch("escritorio.ventana.QFileDialog.getExistingDirectory", return_value=self.tmp.name):
            self.assertTrue(w.guardar())
        self.assertTrue(w.abrir_ruta(e.ruta))
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual(w.edicion.ed.hidden_labels(), {ts["t2"]})

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
        self.assertEqual(alto, 4, "doble trazo")
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
        with mock.patch("escritorio.ventana.QFileDialog.getExistingDirectory", return_value=self.tmp.name):
            self.assertTrue(w.guardar())
        self.assertTrue(w.abrir_ruta(e.ruta))
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual(len(w.edicion.M["bars"]), 1)
        self.assertTrue(w.cambiar_modo("simular"))
        nombre = {bt.text().split(" ")[0]: v for v, bt in w.botones.items()}
        w.botones[nombre["marcha"]].click()
        self.assertEqual(sorted(w.v.state()["situation"]), sorted([ids["1"], e2]))
        # Quitar un elemento de la barra deshace su enlace; borrar la barra, los demas
        self.assertTrue(w.cambiar_modo("editar"))
        e = w.edicion
        bid = e.M["bars"][0]["id"]
        e.seleccionar([f"{bid}|{e2}|barra"])
        self.assertEqual(w.props.pila.currentIndex(), 3)
        self.assertTrue(e.borrar())
        self.assertEqual(e.ed.get(ts["t1"])["postRefs"], [ids["1"]])
        e.seleccionar([bid])
        self.assertEqual(w.props.pila.currentIndex(), 4)
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
        w.botones[nombre["alterna"]].click()  # el otro camino: E0 -t3-> E2
        self.assertEqual(w.v.state()["situation"], [e2])
        w.botones[nombre["alterna"]].click()
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
        # Una rama solo se une a un enlace que llega a una etapa
        antes = len(e.ed.undo_stack)
        e.prensar(pt(ids["1"], "abajo"))
        lista = {x["id"]: x for x in enlaces(e.M)}
        pre = lista[f"{ts['t1']}|{ids['0']}|pre"]["pts"]
        e.soltar(sobre(pre[:2], 0.5))  # el primer tramo, lejos de la transicion
        self.assertIn("llega a una etapa", e.mensaje)
        self.assertEqual(len(e.ed.undo_stack), antes)

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
        self.assertEqual(w.props.pila.currentIndex(), 3)
        self.assertIn("0 → t1", w.props.titulo.text())
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
        w.herramienta("etapa")
        QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos(QPointF(420, 60)))
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
        w.botones[nombre["rapida"]].click()
        self.assertEqual(w.v.state()["situation"], [e2], "el salto lleva de E0 a E2")

    def test_SEDI22_ejemplo_alternativas(self):
        """REQ-SIM-03: el ejemplo «alternativas» se simula, se dibuja con la flecha de union y se puede editar."""
        w = self.w
        w.cargar_ejemplo("alternativas")
        w.a_ejecutar.setChecked(False)
        nombre = {b.text().split(" ")[0]: v for v, b in w.botones.items()}
        w.botones[nombre["rapida"]].click()
        self.assertEqual(w.v.state()["situation"], ["E2"])
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
            e.herramienta = tipo
            e.prensar(QPointF(100 + 100, y))
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
        """REQ-EDT-02: clic selecciona un enlace; arrastre desde él abre otra rama en una transacción."""
        from escritorio.diagrama import enlaces
        self.w.cargar_ejemplo('seleccion')
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
        nueva = next(t for t in e.ed.model['transitions'] if t['id'] not in ('t1', 't2'))
        self.assertEqual(nueva['preRefs'], ['5'])
        self.assertEqual(len(e.ed.undo_stack), n+1)
        e.deshacer()
        self.assertEqual(len(e.M['transitions']), 2)

    def test_SEDI26_geometria_comun_retorno_y_movimiento(self):
        """REQ-MOD-03: uniones comunes, retorno fuera de la etapa, flecha automática y recorridos iguales en Qt/web."""
        from escritorio.diagrama import enlaces, H, SX
        self.w.cargar_ejemplo('repeticion')
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
        self.w.cargar_ejemplo('salto')
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
            w.a_ejecutar.setChecked(False)
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
        self.w.cargar_ejemplo('repeticion')
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
        dest = Path(self.tmp.name) / 'manual'
        self.w.guardar_en(dest)
        e.ed.dirty = False  # la copia ya está guardada; evitar el diálogo al abrirla en esta prueba
        self.assertTrue(self.w.abrir_ruta(dest))
        self.assertEqual(enlaces(self.w.v.model), expected)
        otra = Path(self.tmp.name) / 'copia-manual'
        self.w.guardar_en(otra)
        self.assertEqual(open_model(otra).presentations[0]['linkStyles']['retorno|2|post'], style)
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
        self.w.cargar_ejemplo('alternativas')
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
        self.assertTrue(w.flechas['izquierdo'].isHidden(), 'al simular no hay panel izquierdo')
        w.nuevo()
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
        self.assertEqual((pm.width(), pm.height()), (2 * (2 * H) + 8, 2 * (2 * H + 2 * TALLO_E) + 8))
        self.assertEqual((punto.x(), punto.y()), (2 * H + 4, 2 * (TALLO_E + H) + 4))
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
        (variables en su panel, receptividades con bloques, acciones con su diálogo), simula igual que el ejemplo: I00
        lleva a 1 e I01 vuelve a 0; en 1, cada subida de I02 suma 1 a CT y mantenerla no vuelve a contar; Q00 y Q01
        encendidas en 1."""
        from escritorio import bloques
        from escritorio.acciones import DialogoAccion
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
            d = DialogoAccion(w, e, s1)
            d.tipo.setCurrentIndex(d.tipo.findData(datos["tipo"]))
            d.variable.setCurrentText(datos["variable"])
            d.valor.setText(datos.get("valor", ""))
            if datos["tipo"] == "evento":
                d.evento.colocar(bloques.var("I02", "input"))
                d.evento.lienzo.soltar((), bloques.nuevo("sube"))  # un flanco sobre un bloque ocupado lo envuelve
                self.assertEqual(d.evento.texto(), "↑I02")
            d.aceptar()
            self.assertEqual(d.result(), d.DialogCode.Accepted, d.msg.text())
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
        clic en su caja selecciona la etapa y la señala; doble clic la edita; el diálogo explica lo que falta, crea la
        variable si no existe y se deshace de una vez."""
        from escritorio.acciones import DialogoAccion
        w = self.w
        e, ids, ts = self.secuencial()
        c = centro(e.M, ids["1"])
        self.assertEqual(e.menu(QPointF(c.x() + 400, c.y())), [], "en un hueco, nada")
        opciones = dict(e.menu(c))
        self.assertEqual(list(opciones), ["Añadir acción…", "Colocación de las acciones"])
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        opciones["Añadir acción…"]()  # crea la acción continua unida a la etapa (borrador, sin variable) y abre Editar
        (borrador,) = e.ed.draft_actions()
        self.assertEqual((pedidas, borrador["etapa"], borrador["tipo"]), ([(ids["1"], borrador["id"])], ids["1"], "continua"))
        e.deshacer()
        self.assertEqual(e.ed.draft_actions(), [])
        d = DialogoAccion(w, e, ids["1"])
        d.tipo.setCurrentIndex(d.tipo.findData("activacion"))
        d.variable.setCurrentText("CT")
        self.assertFalse(d.crear.isHidden(), "no existe: se ofrece crearla")
        d.crear.setCurrentIndex(d.crear.findData("internal:int"))
        n = len(e.ed.undo_stack)
        d.aceptar()
        self.assertIn("valor", d.msg.text())
        d.valor.setText("CT + 1")
        d.aceptar()
        self.assertEqual(len(e.ed.undo_stack), n + 1, "variable y acción, una sola operación")
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
        self.assertEqual(w.props.s_acciones.currentItem().data(Qt.ItemDataRole.UserRole), aid)
        self.assertIn("Quitar", dict(e.menu(dentro)))
        e.doble(dentro)
        self.assertEqual(pedidas[-1], (ids["1"], aid))
        d = DialogoAccion(w, e, ids["1"], aid)  # cambiarla: memorizada al desactivar, CT := 0
        self.assertEqual((d.tipo.currentData(), d.variable.currentText(), d.valor.text()), ("activacion", "CT", "CT + 1"))
        d.tipo.setCurrentIndex(d.tipo.findData("desactivacion"))
        d.valor.setText("0")
        d.aceptar()
        self.assertEqual(e.datos_accion(aid)["tipo"], "desactivacion")
        self.assertEqual(e.acciones(ids["1"])[0]["id"], aid, "conserva su ID")
        e.quitar_accion(aid)
        self.assertEqual(e.acciones(ids["1"]), [])
        e.deshacer()
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

    def test_SEDI48_dialogo_de_acciones_vista_previa_y_avisos(self):
        """REQ-ACT-01, REQ-EDT-02: el diálogo de acciones muestra la condición y el evento en la notación de la norma;
        una variable no válida para el tipo se avisa y se guarda al aceptar por segunda vez; un X1 ambiguo se avisa."""
        from escritorio.acciones import DialogoAccion
        e, ids, ts = self.secuencial()
        d = DialogoAccion(self.w, e, ids["1"])
        d.variable.setCurrentText("paro")  # una entrada: no se puede escribir (ni se ofrece en la lista)
        d.cond.poner("marcha AND NOT paro")
        d.cond.cambiado.emit(d.cond.texto())  # lo que hace un clic en un bloque
        self.assertIn("overline", d.v_cond.text())
        d.tipo.setCurrentIndex(d.tipo.findData("evento"))
        d.evento.poner("↑marcha")
        d.evento.cambiado.emit(d.evento.texto())
        self.assertIn("↑", d.v_evento.text())
        d.valor.setText("1")
        n = len(e.ed.undo_stack)
        d.aceptar()
        self.assertIn("entrada", d.msg.text())
        self.assertIn("Aceptar otra vez", d.msg.text())
        self.assertEqual(len(e.ed.undo_stack), n, "el primer Aceptar no guarda")
        d.valor.setText("0")  # cambiar algo reinicia el aviso
        self.assertNotIn("Aceptar otra vez", d.msg.text())
        d.aceptar()
        self.assertIn("Aceptar otra vez", d.msg.text())
        d.aceptar()
        self.assertEqual(len(e.ed.undo_stack), n + 1, "el segundo Aceptar guarda el borrador")
        self.assertEqual(e.acciones(ids["1"])[0]["variable"], "paro")
        # continua con una variable no booleana
        e.nueva_variable("CT", "internal", {"kind": "int"})
        d = DialogoAccion(self.w, e, ids["1"])
        d.variable.setCurrentText("CT")
        d.tipo.setCurrentIndex(d.tipo.findData("continua"))
        d.variable.setCurrentText("CT")
        d.aceptar()
        self.assertIn("booleana", d.msg.text())
        # X1 ambiguo
        e.ed.add_step(e.raiz, "E1")
        d.valor.setText("X1")  # oculto en una continua: no cuenta para el aviso
        d.cond.poner("")
        d.cond.cambiado.emit(d.cond.texto())
        self.assertNotIn("puede ser la etapa", d.msg.text())
        d.valor.setText("")
        d.cond.poner("X1")
        d.cond.cambiado.emit(d.cond.texto())
        self.assertIn("puede ser la etapa E1 o la etapa 1", d.msg.text())
        self.assertIn("active(`1`)", d.msg.text())
        e.seleccionar([ts["t1"]])  # y el panel de la transición avisa igual
        self.w.props.t_texto.setText("X1")
        self.w.props._previsualizar()
        self.assertIn("puede ser la etapa E1 o la etapa 1", self.w.props.t_estado.text())

    def test_SEDI49_memorias_en_la_interfaz(self):
        """REQ-EDT-07: las variables internas se llaman «memorias» en la interfaz; el papel guardado sigue siendo
        «internal»."""
        from escritorio.acciones import CREAR, DialogoAccion
        from escritorio.variables import PAPELES
        e, ids, ts = self.secuencial()
        self.assertIn(("internal", "Memoria"), PAPELES)
        self.assertEqual([t for p, k, t in CREAR if p == "internal"], ["Memoria booleana", "Memoria entera (contador)"])
        d = DialogoAccion(self.w, e, ids["1"])
        d.tipo.setCurrentIndex(d.tipo.findData("activacion"))
        d.variable.setCurrentText("CT")
        d.crear.setCurrentIndex(d.crear.findData("internal:int"))
        d.valor.setText("CT + 1")
        d.aceptar()
        self.assertEqual(next(v for v in e.ed.model["variables"] if v["name"] == "CT")["role"], "internal")
        pv = self.w.variables
        fila = [pv.tabla.item(r, 0).text() for r in range(pv.tabla.rowCount())].index("CT")
        self.assertEqual(pv.tabla.item(fila, 1).text(), "Memoria")

    def test_SEDI52_texto_y_bloques_sincronizados(self):
        """REQ-EDT-02: lo escrito en el campo de texto aparece en bloques; un texto que no se puede analizar no cambia los
        bloques y avisa; un cambio de bloques escribe el texto y se aplica al modelo."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ts["t1"]])
        prog, p = w.props.prog, w.props
        self.assertEqual((prog.lienzo.arbol["k"], prog.texto()), ("var", "marcha"))
        p.t_texto.setText("↑marcha AND NOT X1")
        p.t_texto.textEdited.emit(p.t_texto.text())
        a = prog.lienzo.arbol
        self.assertEqual((a["k"], a["a"]["k"], a["b"]["k"], a["b"]["a"]["n"]), ("y", "sube", "no", "X1"))
        self.assertTrue(prog.aviso.isHidden())
        p.t_texto.setText("marcha AND")  # a medias: los bloques se quedan como estaban
        p.t_texto.textEdited.emit(p.t_texto.text())
        self.assertEqual(prog.texto(), "↑marcha AND NOT X1")
        self.assertFalse(prog.aviso.isHidden())
        self.assertTrue(prog.aviso.text().startswith("No se puede pasar a bloques: "), prog.aviso.text())
        self.assertLess(len(prog.aviso.text()), 120, "una línea breve")
        p.t_texto.setText("marcha AND ?")  # un hueco es un hueco
        p.t_texto.textEdited.emit(p.t_texto.text())
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
        deshacer; en el diálogo de acciones, que aplica al aceptar, el programador tiene su historial local."""
        from escritorio import bloques
        from escritorio.acciones import DialogoAccion
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
        # el diálogo de acciones
        d = DialogoAccion(self.w, e, ids["1"])
        self.assertTrue(d.cond.historial and len(d.cond.findChildren(QShortcut)) == 3, "Ctrl+Z, Ctrl+Mayús+Z, Ctrl+Y")
        emitidos = []
        d.cond.cambiado.connect(emitidos.append)
        d.cond.colocar(bloques.var("marcha", "input"))
        d.cond.lienzo.soltar((), bloques.nuevo("no"))
        self.assertEqual(d.cond.texto(), "NOT marcha")
        self.assertIn("overline", d.v_cond.text())
        d.cond.deshacer()
        self.assertEqual(d.cond.texto(), "marcha")
        d.cond.deshacer()
        self.assertEqual((d.cond.texto(), d.v_cond.text()), ("", "<i>—</i>"))
        d.cond.deshacer()  # nada más que deshacer
        self.assertEqual(d.cond.texto(), "")
        d.cond.rehacer()
        d.cond.rehacer()
        self.assertEqual(d.cond.texto(), "NOT marcha")
        self.assertEqual(emitidos, ["marcha", "NOT marcha", "marcha", "", "marcha", "NOT marcha"])
        d.cond.poner("paro")  # lo que viene de fuera borra el historial
        d.cond.deshacer()
        self.assertEqual(d.cond.texto(), "paro")

    def test_SEDI55_ventana_ampliada_sincronizada(self):
        """REQ-EDT-02: «⤢ Ampliar» abre el programador en una ventana propia, no modal, con el mismo texto; los cambios de
        una se ven en la otra y se aplican igual al modelo."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        e.seleccionar([ts["t1"]])
        prog = w.props.prog
        prog.poner("marcha AND NOT paro")
        v = prog.ampliar_ventana()
        self.assertFalse(v.isModal())
        self.assertIs(prog.ampliar_ventana(), v, "una sola ventana")
        g = v.programador
        self.assertEqual((g.texto(), g.ampliar.isHidden()), ("marcha AND NOT paro", True))
        g.lienzo.soltar(("b", "a"), bloques.var("marcha", "input"))  # en la ventana: se aplica al modelo
        self.assertEqual((prog.texto(), e.texto_condicion(ts["t1"])), ("marcha AND NOT marcha",) * 2)
        n = len(e.ed.undo_stack)
        prog.lienzo.quitar(("b",))  # en el panel: se ve en la ventana
        self.assertEqual((g.texto(), e.texto_condicion(ts["t1"]), len(e.ed.undo_stack)), ("marcha AND ?",) * 2 + (n + 1,))
        g.lienzo.soltar(("b",), g.lienzo.arbol["a"], origen=("a",))  # mover dentro de la ventana
        self.assertEqual((prog.texto(), g.texto()), ("? AND marcha",) * 2)
        e.deshacer()  # el deshacer del editor, y el texto vuelve a las dos
        self.assertEqual((prog.texto(), g.texto()), ("marcha AND ?",) * 2)
        g.al_deshacer()  # Ctrl+Z en la ventana: el deshacer del editor
        self.assertEqual((prog.texto(), g.texto()), ("marcha AND NOT marcha",) * 2)
        prog.poner("↑paro")  # un texto nuevo, en las dos
        self.assertEqual(g.texto(), "↑paro")
        g.poner("marcha AND")  # y el aviso, también
        self.assertFalse(prog.aviso.isHidden())
        v.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        QApplication.processEvents()
        self.assertIsNone(prog._ventana)
        self.assertIsNot(prog.ampliar_ventana(), v)
        prog._ventana.close()

    def test_SEDI59_pestana_bloques_en_el_panel_inferior(self):
        """REQ-EDT-02: el programador de la receptividad es la pestaña «Bloques» del panel inferior, solo al editar;
        seleccionar una transición la activa con su receptividad; sin transición, el mensaje; hay un solo programador."""
        from escritorio.bloques import Programador
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        QApplication.processEvents()
        i = w.i_bloques
        self.assertEqual(w.pestanas.tabText(i), "Bloques")
        self.assertTrue(w.pestanas.isTabVisible(i), "en Editar aparece")
        self.assertEqual([w.pestanas.tabText(k) for k in range(2)], ["Traza", "Leyenda"])
        self.assertEqual(len(w.findChildren(Programador)), 1, "un solo programador en la ventana")
        self.assertTrue(w.pestanas.widget(i).isAncestorOf(w.props.prog), "vive en la pestaña")
        e.seleccionar([])
        w.pestanas.setCurrentIndex(0)
        QApplication.processEvents()
        self.assertTrue(w.props.prog.isHidden())
        self.assertEqual(w.props.l_bloques.text(), "Elija una transición para programar su receptividad")
        e.seleccionar([ts["t2"]])
        self.assertEqual(w.pestanas.currentIndex(), i, "al seleccionar una transición se activa Bloques")
        self.assertEqual((w.props.prog.texto(), w.props.prog.isHidden()), ("paro", False))
        self.assertIn("t2", w.props.l_bloques.text())
        w.pestanas.setCurrentIndex(1)  # otro cambio sobre la misma transición no arrebata la pestaña
        e.poner_condicion(ts["t2"], "paro AND marcha", crear=True)
        self.assertEqual(w.pestanas.currentIndex(), 1)
        e.seleccionar([ts["t1"]])
        self.assertEqual((w.pestanas.currentIndex(), w.props.prog.texto()), (i, "marcha"))
        e.seleccionar([ids["0"]])  # una etapa: el panel sigue en Bloques, con el mensaje
        self.assertEqual((w.pestanas.currentIndex(), w.props.prog.isHidden()), (i, True))
        e.seleccionar([ts["t1"]])
        w.pestanas.setCurrentIndex(i)
        w.cambiar_modo("simular")
        self.assertFalse(w.pestanas.isTabVisible(i), "en Simular no aparece")
        self.assertNotEqual(w.pestanas.currentIndex(), i)
        w.cambiar_modo("editar")
        self.assertTrue(w.pestanas.isTabVisible(i))

    def test_SEDI60_bloques_y_texto_sincronizados_en_la_pestana(self):
        """REQ-EDT-02: un cambio de bloques escribe el texto del panel izquierdo y es una operación del editor (Ctrl+Z);
        lo escrito en el texto aparece en los bloques; el panel izquierdo ya no lleva el programador."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        p, prog = w.props, w.props.prog
        e.seleccionar([ts["t1"]])
        self.assertIsNone(p.findChild(bloques.Programador), "el panel izquierdo no tiene el programador")
        n = len(e.ed.undo_stack)
        prog.lienzo.soltar((), bloques.nuevo("no"))
        self.assertEqual((p.t_texto.text(), e.texto_condicion(ts["t1"]), len(e.ed.undo_stack)),
                         ("NOT marcha", "NOT marcha", n + 1))
        e.deshacer()
        self.assertEqual((p.t_texto.text(), prog.texto()), ("marcha", "marcha"))
        p.t_texto.setText("paro AND marcha")
        p.t_texto.textEdited.emit(p.t_texto.text())
        self.assertEqual((prog.lienzo.arbol["k"], prog.texto()), ("y", "paro AND marcha"))
        self.assertEqual(len(e.ed.undo_stack), n, "escribir el texto no aplica hasta terminar")

    def test_SEDI61_boton_bloques_abajo_si_el_panel_esta_plegado(self):
        """REQ-EDT-02: con el panel inferior plegado no se despliega solo; el panel de la transición ofrece «Bloques
        abajo ▾», que lo despliega y elige la pestaña Bloques; con él a la vista, el botón no aparece."""
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        w._mostrar_panel("inferior", False)
        w.pestanas.setCurrentIndex(0)
        e.seleccionar([ts["t1"]])
        QApplication.processEvents()
        self.assertTrue(w.pestanas.isHidden(), "no se despliega por su cuenta")
        self.assertEqual(w.props.t_abajo.text(), "Bloques abajo ▾")
        self.assertFalse(w.props.t_abajo.isHidden())
        self.assertTrue(w.props.prog.parent().isHidden() or not w.props.prog.isVisible())
        w.props.t_abajo.click()
        self.assertFalse(w.pestanas.isHidden())
        self.assertEqual(w.pestanas.currentIndex(), w.i_bloques)
        self.assertTrue(w.props.t_abajo.isHidden(), "con el panel a la vista, el botón sobra")
        self.assertTrue(w.a_inferior.isChecked())
        w._mostrar_panel("inferior", False)
        self.assertFalse(w.props.t_abajo.isHidden())

    def test_SEDI62_ficha_accion_en_la_paleta(self):
        """REQ-ACT-01, REQ-EDT-02: la paleta ofrece la ficha «Acción» con su figura (el lado izquierdo, bajo el puntero);
        soltada en cualquier sitio crea una acción suelta sin abrir ningún diálogo; como herramienta, un clic hace lo
        mismo y la herramienta vale para una."""
        from escritorio.propiedades import figura
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        textos = [w.paleta.item(k).text() for k in range(w.paleta.count())]
        self.assertIn("Acción", textos)
        pm, punto = figura("accion", 1.0, 1.0)
        self.assertGreater(pm.width(), pm.height(), "un rectángulo de acción, más ancho que alto")
        self.assertTrue(pm.rect().contains(punto))
        self.assertLess(punto.x(), 8, "bajo el puntero, su lado izquierdo (el punto de unión)")
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        n, acciones = len(e.ed.undo_stack), len(e.ed.model["actions"])
        e.colocar("accion", QPointF(900, 400))  # en cualquier sitio, también fuera de toda etapa
        self.assertEqual((pedidas, len(e.ed.undo_stack), len(e.ed.model["actions"])), ([], n + 1, acciones))
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], "variable" in b, "etapa" in b), ("continua", False, False))
        self.assertEqual(e.sel, [b["id"]])
        e.colocar("accion", centro(e.M, ids["1"]))  # sobre una etapa tampoco pide nada: queda suelta
        self.assertEqual((pedidas, len(e.ed.draft_actions())), ([], 2))
        # como herramienta: clic en el dibujo
        w.paleta.setCurrentRow(textos.index("Acción"))
        self.assertEqual(e.herramienta, "accion")
        e.prensar(QPointF(900, 600))
        self.assertEqual((pedidas, e.herramienta, len(e.ed.draft_actions())), ([], "seleccionar", 3))

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
        v = prog.ampliar_ventana()
        for p in (prog, v.programador):  # área y ventana ampliada: el motor da la categoría de cada bloque
            self.assertEqual((p.lienzo.motor.categoria(p.lienzo.arbol), p.lienzo.motor.categoria(p.lienzo.arbol["a"])),
                             ("o", "y"))
        v.close()


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
            r = pal.visualItemRect(pal.item(0))
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
        """REQ-EDT-02, REQ-EDT-07: al crear, renombrar, quitar o cambiar de papel una variable (panel Variables, diálogo de
        acciones, «Crear las que faltan») la paleta de bloques, los desplegables y los colores del área, y la ventana
        ampliada se ponen al día en el acto, sin tener que volver a elegir la transición."""
        from escritorio.acciones import DialogoAccion
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        e.seleccionar([ts["t1"]])
        prog = w.props.prog
        prog.elegir_categoria("salida")
        self.assertIsNone(prog.paleta.bloques()[0]["n"], "sin salidas, el bloque se ofrece vacío")
        e.nueva_variable("Q05", "output", {"kind": "bool"})  # lo que hace «Nueva variable» del panel Variables
        self.assertEqual(prog.paleta.bloques()[0]["n"], "Q05", "la paleta se llena en el acto")
        self.assertEqual(prog.opciones("salida"), [("Q05", "Q05")])
        v = prog.ampliar_ventana()
        g = v.programador
        e.nueva_variable("Q06", "output", {"kind": "bool"})
        self.assertEqual(g.opciones("salida"), [("Q05", "Q05"), ("Q06", "Q06")])
        self.assertEqual(g.paleta.opciones_desplegable(g.paleta.bloques()[0], "n"), [("Q05", "Q05"), ("Q06", "Q06")])
        # renombrar y cambiar de papel (panel Variables)
        vid = next(x["id"] for x in e.ed.model["variables"] if x["name"] == "Q05")
        self.assertIsNone(e.cambiar_variable(vid, nombre="Motor"))
        self.assertEqual(prog.opciones("salida"), [("Motor", "Motor"), ("Q06", "Q06")])
        self.assertEqual(g.opciones("salida"), [("Motor", "Motor"), ("Q06", "Q06")])
        self.assertIsNone(e.cambiar_variable(vid, role="internal"))
        self.assertEqual(prog.opciones("salida"), [("Q06", "Q06")])
        self.assertEqual(prog.opciones("interna"), [("Motor", "Motor")])
        # el color del bloque del área sigue al papel: una variable que cambia de papel cambia de categoría
        e.poner_condicion(ts["t1"], "Motor")
        self.assertEqual(prog.texto(), "Motor")
        self.assertEqual(prog.lienzo.motor.categoria(prog.lienzo.arbol), "interna")
        self.assertIsNone(e.cambiar_variable(vid, role="output"))
        self.assertEqual(prog.lienzo.motor.categoria(prog.lienzo.arbol), "salida", "el área, al día sin tocar la fórmula")
        self.assertEqual(g.lienzo.motor.categoria(g.lienzo.arbol), "salida")
        e.poner_condicion(ts["t1"], "marcha")
        # quitar
        self.assertIsNone(e.quitar_variable(next(x["id"] for x in e.ed.model["variables"] if x["name"] == "Q06")))
        self.assertEqual(prog.opciones("salida"), [("Motor", "Motor")])
        self.assertEqual(g.opciones("salida"), [("Motor", "Motor")])
        v.close()
        # «Crear las que faltan»
        prog.elegir_categoria("entrada")
        w.props.t_manual.setChecked(True)
        w.props.t_texto.setText("nueva_in AND marcha")
        w.props.t_texto.textEdited.emit(w.props.t_texto.text())
        w.props._previsualizar()
        self.assertFalse(w.props.t_crear.isHidden())
        w.props.t_crear.click()
        self.assertIn(("nueva_in", "nueva_in"), prog.opciones("entrada"))
        # el diálogo de acciones: sus programadores escuchan al editor
        d = DialogoAccion(w, e, ids["1"])
        d.cond.elegir_categoria("interna")
        antes = d.cond.opciones("interna")
        e.nueva_variable("M7", "internal", {"kind": "bool"})
        self.assertEqual(d.cond.opciones("interna"), antes + [("M7", "M7")])
        self.assertEqual(d.cond.paleta.bloques()[0]["n"], antes[0][0] if antes else "M7")

    def test_SEDI67_carpetas_en_su_orden_y_temporizadores(self):
        """REQ-EDT-02: las carpetas del programador van en este orden: Operadores, Entradas, Salidas, Etapas (X),
        Memorias, Comparaciones, Temporizadores; la categoría «Tiempo» se llama «Temporizadores»."""
        from escritorio.bloques import CATEGORIAS, Programador
        e, ids, ts = self.secuencial()
        textos = ["Operadores", "Entradas", "Salidas", "Etapas (X)", "Memorias", "Comparaciones", "Temporizadores"]
        self.assertEqual([t for _, t in CATEGORIAS], textos)
        prog = self.w.props.prog
        self.assertEqual([b.text() for b in prog.categorias.values()], textos)
        self.assertNotIn("Tiempo", [b.text() for b in prog.categorias.values()])
        self.assertEqual(prog.categorias["tiempo"].text(), "Temporizadores")
        self.assertEqual(prog.paleta.clave, "entrada")

    def test_SEDI68_receptividad_en_la_pestana_con_texto_de_solo_lectura(self):
        """REQ-EDT-02: toda la receptividad está en la pestaña Bloques (texto de la fórmula, «Escrito», «Se dibuja» y
        «Crear las que faltan»); el panel izquierdo de la transición solo lleva etiqueta, «Mostrar etiqueta» y «Bloques
        abajo ▾». El texto se ve pero no se edita hasta marcar «Escribir a mano»; desmarcada, vuelve a solo lectura."""
        from escritorio import bloques
        w = self.w
        e, ids, ts = self.secuencial()
        w.resize(1360, 860)
        w.show()
        p, prog = w.props, w.props.prog
        e.seleccionar([ts["t1"]])
        QApplication.processEvents()
        izq = p.pila.widget(2)  # la página de la transición en el panel izquierdo
        pestana = w.pestanas.widget(w.i_bloques)
        for campo in (p.t_texto, p.t_vista, p.t_dibujo, p.t_crear, p.t_manual, p.t_estado):
            self.assertFalse(izq.isAncestorOf(campo), "ya no están en el panel izquierdo")
            self.assertTrue(pestana.isAncestorOf(campo), "están en la pestaña Bloques")
        self.assertTrue(izq.isAncestorOf(p.t_etiqueta) and izq.isAncestorOf(p.t_mostrar) and izq.isAncestorOf(p.t_abajo))
        self.assertEqual(sorted(x.text() for x in izq.findChildren(QLabel) if x.text() in ("Etiqueta", "Texto", "Escrito", "Se dibuja")),
                         ["Etiqueta"])
        self.assertEqual(p.t_texto.text(), "marcha")
        self.assertTrue(p.t_texto.isReadOnly(), "se ve pero no se edita")
        self.assertFalse(p.t_manual.isChecked())
        self.assertEqual(p.t_manual.text(), "Escribir a mano")
        # con bloques el texto sigue las piezas, sin dejar editar
        n = len(e.ed.undo_stack)
        prog.lienzo.soltar((), bloques.nuevo("no"))
        self.assertEqual((p.t_texto.text(), p.t_texto.isReadOnly(), len(e.ed.undo_stack)), ("NOT marcha", True, n + 1))
        # «Escribir a mano»: editable; lo escrito pasa a bloques y se aplica al terminar
        p.t_manual.setChecked(True)
        self.assertFalse(p.t_texto.isReadOnly())
        p.t_texto.setText("paro AND marcha")
        p.t_texto.textEdited.emit(p.t_texto.text())
        self.assertEqual((prog.lienzo.arbol["k"], prog.texto()), ("y", "paro AND marcha"))
        p.t_texto.editingFinished.emit()
        self.assertEqual(e.texto_usuario(ts["t1"]), "paro AND marcha")
        self.assertEqual(len(e.ed.undo_stack), n + 2)
        p.t_manual.setChecked(False)
        self.assertTrue(p.t_texto.isReadOnly(), "desmarcada, vuelve a solo lectura")
        # otra transición: solo lectura aunque se hubiera dejado marcada
        p.t_manual.setChecked(True)
        e.seleccionar([ts["t2"]])
        self.assertTrue(p.t_texto.isReadOnly() and not p.t_manual.isChecked())
        self.assertEqual(p.t_texto.text(), "paro")
        # lo que faltaba por crear, y el texto escrito de cómo se dibuja, están ahí
        p.t_manual.setChecked(True)
        p.t_texto.setText("↑nueva")
        p.t_texto.textEdited.emit(p.t_texto.text())
        self.assertFalse(p.t_crear.isHidden())
        self.assertIn("nueva", p.t_vista.text())
        p.t_texto.setText("↑marcha")
        p.t_texto.textEdited.emit(p.t_texto.text())
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
        """REQ-ACT-01, REQ-EDT-02: la ficha «Acción», soltada en cualquier sitio, crea una acción continua suelta sin
        variable (se dibuja con «?» y borde de borrador) y con un punto de unión a la izquierda; no abre ningún
        diálogo; se mueve arrastrándola; es una operación de deshacer."""
        from escritorio.diagrama import anclas
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
        # se dibuja con borde discontinuo (el pincel de borrador)
        rects = [it for it in w.diagrama.scene().items() if hasattr(it, "pen") and it.pen().style() == Qt.PenStyle.CustomDashLine
                 and abs(it.boundingRect().width() - ancho) < 4]
        self.assertTrue(rects, "borde discontinuo")
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
        """REQ-ACT-01, REQ-EDT-02: el botón derecho en una acción (suelta o unida) ofrece sus cinco tipos con el actual
        marcado, «Editar…», «Separar de la etapa» (si está unida) y «Quitar»; no ofrece el forzado. Cambiar a un tipo que
        pide datos que faltan deja la acción con «?» y abre Editar con el tipo ya puesto; si no falta nada, se cambia en
        su sitio."""
        w = self.w
        e, ids, ts = self.secuencial()
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        aid = self._accion_q(e, ids)

        def caja(i):
            c = next(c for c in w.diagrama.cajas_acciones if c["id"] == i)
            x, y, ancho, alto = c["rect"]
            return QPointF(x + ancho / 2, y + alto / 2)
        opciones = e.menu(caja(aid))
        textos = [t for t, _ in opciones]
        self.assertEqual(textos[:5], ["Continua", "Continua limitada en el tiempo", "Memorizada al activar",
                                      "Memorizada al desactivar", "Memorizada por evento"])
        self.assertEqual(e.menu_marcadas, {"Continua"})
        self.assertIn("Editar…", textos)
        self.assertIn("Separar de la etapa", textos)
        self.assertEqual(textos[-1], "Quitar")
        self.assertFalse([t for t in textos if "orzado" in t], "el forzado no se ofrece")
        # la barra de menú de Qt: separadores y marca del tipo actual
        menu = w.diagrama.menu_contextual(opciones)
        marcadas = [a.text() for a in menu.actions() if a.isCheckable() and a.isChecked()]
        self.assertEqual(marcadas, ["Continua"])
        # a memorizada al activar: falta el valor -> borrador unido con «?», Editar abierto, tipo puesto
        n = len(e.ed.undo_stack)
        dict(opciones)["Memorizada al activar"]()
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
        # a por evento: falta el evento
        e.tipo_accion(a2, "evento")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], pedidas), ("evento", [(ids["1"], b["id"])]))
        (m,) = e.M["draftActions"]
        self.assertEqual(m["event"], [{"t": "?"}])
        self.assertEqual(w.props.s_acciones.count(), 1)
        self.assertIn("?", w.props.s_acciones.item(0).text())
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
        # a continua limitada: falta el límite; con él, la acción del modelo lleva limitUs y se dibuja
        e.quitar_accion(a2)
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "continua", "variable": "Q00", "condicion": ""}))
        a3 = e.acciones(ids["1"])[0]["id"]
        pedidas.clear()
        e.tipo_accion(a3, "limitada")
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], pedidas), ("limitada", [(ids["1"], b["id"])]))
        self.assertEqual("".join(s["t"] for s in e.M["draftActions"][0]["cond"]), "NOT ?/X1", "el límite, como condición")
        self.assertEqual(e.poner_accion(ids["1"], {"tipo": "limitada", "variable": "Q00", "limite": "abc"}, b["id"]).split()[0],
                         "Límite")
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "limitada", "variable": "Q00", "limite": "3s"}, b["id"]))
        (a4,) = e.acciones(ids["1"])
        self.assertEqual((e.datos_accion(a4["id"])["tipo"], e.datos_accion(a4["id"])["limite"]), ("limitada", "3s"))
        self.assertEqual(e.ed.get(a4["id"])["limitUs"], "3000000")
        self.assertEqual([s["t"] for s in e.M["steps"][1]["actions"][0]["text"]], ["Q00"])
        self.assertTrue(e.ed.validate().can_simulate)
        # de limitada a continua: en su sitio
        e.tipo_accion(a4["id"], "continua")
        self.assertNotIn("limitUs", e.ed.get(a4["id"]))
        # una acción suelta: su menú no ofrece separar; cambia de tipo y pide lo que le falta
        d = e.poner_accion_suelta(QPointF(600, 500))
        opciones = e.menu(caja(d))
        self.assertNotIn("Separar de la etapa", [t for t, _ in opciones])
        self.assertEqual(e.menu_marcadas, {"Continua"})
        pedidas.clear()
        dict(opciones)["Memorizada por evento"]()
        self.assertEqual((e.ed.draft_actions()[0]["tipo"], pedidas), ("evento", [(None, d)]))
        self.assertEqual(e.menu_marcadas, {"Continua"}, "el menú se recalcula al abrirlo")
        e.menu(caja(d))
        self.assertEqual(e.menu_marcadas, {"Memorizada por evento"})
        dict(opciones)["Continua"]()  # no pide nada nuevo
        self.assertEqual(pedidas, [(None, d)])
        # Editar…, Quitar y doble clic
        self.assertEqual(dict(e.menu(caja(d)))["Editar…"](), None)
        self.assertEqual(pedidas[-1], (None, d))
        e.doble(caja(d))
        self.assertEqual(pedidas[-1], (None, d))
        dict(e.menu(caja(d)))["Quitar"]()
        self.assertEqual(e.ed.draft_actions(), [])
        # el menú de la etapa conserva «Añadir acción…»
        self.assertEqual(list(dict(e.menu(centro(e.M, ids["1"])))), ["Añadir acción…", "Colocación de las acciones"])

    def test_SEDI73_guardar_abrir_con_borradores_avisos_y_deshacer(self):
        """REQ-DAT-01, REQ-EDT-09, REQ-EDT-14: los borradores de acción se guardan en la presentación
        (`draftActions`) y se abren con el proyecto; no cambian la revisión semántica ni se simulan; cada uno da el
        aviso «Acción sin etapa: no se simula» (sin impedir simular el resto); deshacer y rehacer los siguen."""
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
        avisos = [d for d in e.diagnosticos() if d["code"] == "AVISO"]
        self.assertEqual(len(avisos), 3)
        self.assertEqual([d["message"] for d in avisos].count("Acción sin etapa: no se simula"), 2)
        self.assertTrue(any("sin completar" in d["message"] and "variable" in d["message"] for d in avisos))
        self.assertTrue(all(not d["blocks"] and d["severity"] == "advertencia" for d in avisos))
        self.assertTrue(e.ed.validate().can_simulate, "no impiden simular el resto")
        textos = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        self.assertEqual(sum("Acción sin etapa: no se simula" in t for t in textos), 2)
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
        self.assertEqual([c for c in e2.M["draftActions"]][0]["trigger"], "event")
        self.assertEqual(len([d for d in e2.diagnosticos() if d["code"] == "AVISO"]), 3)
        # la simulación no los ve
        v = Vista("m", "t", "", lambda: (copy.deepcopy(op.doc), {}), normalize_options(None), presentation=op.presentations[0])
        self.assertEqual((v.model["draftActions"], v.s is not None), ([], True))
        w.cambiar_modo("simular")
        self.assertEqual(w.modo, "simular")
        w.cambiar_modo("editar")
        self.assertEqual(len(e.ed.draft_actions()), 3)
        # deshacer y rehacer (una operación por borrador)
        antes = copy.deepcopy(e.ed.draft_actions())
        e.deshacer()
        self.assertNotEqual(e.ed.draft_actions(), antes)
        e.rehacer()
        self.assertEqual(e.ed.draft_actions(), antes)
        # una variable que usa un borrador no se quita; una etapa borrada deja suelto el borrador unido
        self.assertIn("usa", e.quitar_variable(q) or "")
        e.confirmar_borrado = lambda plan: True
        e.seleccionar([ids["0"]])
        e.borrar()
        self.assertNotIn("etapa", next(d for d in e.ed.draft_actions() if d["id"] == d3))
        e.deshacer()
        self.assertEqual(next(d for d in e.ed.draft_actions() if d["id"] == d3)["etapa"], ids["0"])


    def test_SEDI74_dialogo_editar_de_una_accion_suelta_o_sin_completar(self):
        """REQ-ACT-01, REQ-EDT-02: «Editar…» de una acción suelta abre el diálogo de acciones (con el límite de tiempo de
        las limitadas): guarda sus datos aunque falte algo; unida a una etapa y completa, pasa al modelo en una sola
        operación; «Añadir acción…» de una etapa crea la continua unida y abre Editar."""
        from escritorio.acciones import DialogoAccion
        w = self.w
        e, ids, ts = self.secuencial()
        e.nueva_variable("Q00", "output", {"kind": "bool"})
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        did = e.poner_accion_suelta(QPointF(500, 220))
        d = DialogoAccion(w, e, None, did)
        self.assertEqual(d.windowTitle(), "Acción suelta")
        self.assertTrue(d.limite.isHidden())
        d.tipo.setCurrentIndex(d.tipo.findData("limitada"))
        self.assertFalse(d.limite.isHidden(), "el límite de tiempo solo en la limitada")
        self.assertFalse(d.cond.isHidden(), "y la limitada lleva también su condición")
        d.limite.setText("2s")
        n = len(e.ed.undo_stack)
        d.aceptar()  # sin variable: se guarda igual, con «?»
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["tipo"], b["limite"], "variable" in b), ("limitada", "2s", False))
        self.assertEqual(("".join(s["t"] for s in e.M["draftActions"][0]["cond"]), e.M["draftActions"][0]["text"]),
                         ("NOT 2s/X?", [{"t": "?"}]))
        d = DialogoAccion(w, e, None, did)  # se reabre con lo guardado
        self.assertEqual((d.tipo.currentData(), d.limite.text()), ("limitada", "2s"))
        d.variable.setCurrentText("Q00")
        d.aceptar()
        self.assertEqual(e.ed.draft_actions()[0]["variable"], next(v["id"] for v in e.ed.model["variables"] if v["name"] == "Q00"))
        self.assertEqual(e.ed.model["actions"], [], "suelta: no es del modelo aunque esté completa")
        # una variable que no existe se crea al aceptar, con la acción suelta
        d = DialogoAccion(w, e, None, did)
        d.variable.setCurrentText("Q11")
        d.crear.setCurrentIndex(d.crear.findData("output:bool"))
        n = len(e.ed.undo_stack)
        d.aceptar()
        self.assertEqual((len(e.ed.undo_stack), [v["name"] for v in e.ed.model["variables"]]), (n + 1, ["marcha", "paro", "Q00", "Q11"]))
        # unida a una etapa y completa: pasa al modelo con su límite, en una operación
        e.unir_accion(did, ids["1"])
        (a,) = e.acciones(ids["1"])
        self.assertEqual((e.ed.draft_actions(), a["tipo"], a["limite"], a["variable"]), ([], "limitada", "2s", "Q11"))
        # «Añadir acción…» de la etapa: continua unida, sin variable, y Editar (aquí, el diálogo real)
        pedidas.clear()
        e.anadir_accion(ids["0"])
        (b,) = e.ed.draft_actions()
        self.assertEqual((b["etapa"], b["tipo"], pedidas), (ids["0"], "continua", [(ids["0"], b["id"])]))
        d = DialogoAccion(w, e, ids["0"], b["id"])
        self.assertIn("etapa 0", d.windowTitle())
        d.variable.setCurrentText("Q00")
        n = len(e.ed.undo_stack)
        d.aceptar()
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
        self.assertEqual("".join(s["t"] for s in a["cond"]), "(marcha + paro)·3s/X1")
        self.assertIsNone(e.poner_accion(ids["1"], {"tipo": "limitada", "variable": "Q00", "limite": "3s",
                                                    "condicion": "marcha"}, aid))
        self.assertEqual("".join(s["t"] for s in e.M["steps"][1]["actions"][0]["cond"]), "marcha·3s/X1")
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
        """REQ-EDT-09, REQ-SIM-03: al editar, el panel izquierdo mide de lo que piden las dos columnas de la paleta (su
        rejilla, el marco y la holgura) a un 15 % más, y el derecho tiene el mismo margen; las fichas siguen en dos
        columnas al mínimo; nada de lo que muestran se corta; se pliegan y despliegan; al simular, el derecho es el de
        siempre."""
        from escritorio.diagrama import anclas
        w = self.w
        e, ids, ts = self.secuencial()
        w.show()
        self.app.processEvents()
        minimo, maximo = w.ancho_lateral
        pal = w.paleta
        self.assertEqual(minimo, 2 * pal.gridSize().width() + 2 * pal.frameWidth() + 2)
        self.assertEqual(maximo, round(minimo * 1.15))
        for panel in (w.dock, w.derecho):
            self.assertEqual((panel.minimumWidth(), panel.maximumWidth()), (minimo, maximo), "el mismo margen")
            self.assertTrue(minimo <= panel.width() <= maximo, panel.width())
        self.assertLessEqual(abs(w.dock.width() - w.derecho.width()), 2, "los dos paneles, del mismo tamaño")
        # al ancho mínimo, las fichas siguen en dos columnas y dos filas, sin barras
        w.resizeDocks([w.dock], [minimo], Qt.Orientation.Horizontal)
        self.app.processEvents()
        self.assertEqual(w.dock.width(), minimo)
        r = [pal.visualItemRect(pal.item(i)) for i in range(4)]
        self.assertEqual((r[0].y(), r[1].y(), r[2].y()), (r[1].y(), r[0].y(), r[0].y() + pal.gridSize().height()))
        self.assertTrue(r[1].x() > r[0].x() and r[3].x() > r[2].x(), "dos columnas")
        self.assertEqual((pal.verticalScrollBarPolicy(), pal.horizontalScrollBarPolicy()), (Qt.ScrollBarPolicy.ScrollBarAlwaysOff,) * 2)
        # con cada tipo de selección, las propiedades caben en el ancho (no se cortan) y el panel derecho también
        b = e.poner_barra(QPointF(500, 400), "Y")
        for sel in ([ids["1"]], [ts["t1"]], [f"{ts['t1']}|{ids['0']}|pre"], [b]):
            e.seleccionar(sel)
            self.app.processEvents()
            visor = w.dock.widget().widget(1)
            self.assertLessEqual(w.props.minimumSizeHint().width(), visor.viewport().width(), sel)
        self.assertLessEqual(w.derecho.widget(1).widget().minimumSizeHint().width(), minimo)
        # plegar y desplegar siguen funcionando
        w.flechas["izquierdo"].click()
        self.assertTrue(w.dock.isHidden())
        w.flechas["izquierdo"].click()
        self.assertFalse(w.dock.isHidden())
        self.assertTrue(minimo <= w.dock.width() <= maximo)
        # al simular, el panel derecho vuelve a ser el de siempre
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual((w.derecho.minimumWidth(), w.derecho.maximumWidth()), (300, 16777215))
        self.assertTrue(w.cambiar_modo("editar"))
        self.assertEqual((w.derecho.minimumWidth(), w.derecho.maximumWidth()), (minimo, maximo))

    def test_SEDI79_tabla_de_variables_nombre_papel_tipo(self):
        """REQ-EDT-07: la tabla tiene solo Nombre, Papel y Tipo; se ofrecen Booleana, Entera y Decimal con 2 decimales;
        una variable de un fichero antiguo (decimal de 1 o 3 decimales, duración) se ve con su tipo y funciona, y si se
        le cambia el tipo solo se elige entre los tres; el valor inicial y la unidad que ya tuviera se conservan."""
        from escritorio.variables import TIPOS
        w = self.w
        w.nuevo()
        e, pv = w.edicion, w.variables
        e.nueva_variable("a", "input")
        e.ed.add_variable("T3", "input", {"kind": "decimal", "scale": 3}, unit="s", initial="1.500")
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
        # renombrar y cambiar el papel conservan la unidad y el valor inicial del modelo
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
        self.assertIn("ya existe", pv.msg.text())
        # con una fila sin nombre no se simula ni se guarda
        with mock.patch("escritorio.ventana.QFileDialog.getExistingDirectory") as carpeta, \
                mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertFalse(w.cambiar_modo("simular"))
            self.assertEqual(w.modo, "editar")
            self.assertFalse(w.guardar())
            carpeta.assert_not_called()
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
        self.assertEqual((w.variables.sin_nombre(), w.variables.tabla.rowCount()), (0, 0))

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

    def _tres_acciones(self, e, ids):
        """Una etapa con tres acciones: continua con condición, por evento (banderita) y al desactivar."""
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
                         ["En fila, pegadas", "En fila, separadas", "En columna"])
        self.assertEqual(e.menu_marcadas, {"En fila, pegadas"})
        menu = w.diagrama.menu_contextual(e.menu(c))
        sub = next(a.menu() for a in menu.actions() if a.menu() is not None)
        self.assertEqual([(a.text(), a.isChecked()) for a in sub.actions()],
                         [("En fila, pegadas", True), ("En fila, separadas", False), ("En columna", False)])
        modelo, revision, n = copy.deepcopy(e.ed.model), e.ed.model["revisionId"], len(e.ed.undo_stack)
        # en fila, separadas
        dict(opciones["Colocación de las acciones"])["En fila, separadas"]()
        self.assertEqual((e.ed.presentation["actionLayouts"], len(e.ed.undo_stack)), ({sid: "fila-separada"}, n + 1))
        self.assertEqual((e.ed.model, e.ed.model["revisionId"]), (modelo, revision), "solo presentación")
        r = cajas()
        self.assertTrue(all(abs(r[i + 1][0] - (r[i][0] + r[i][2]) - ACT_GAP) < 0.01 and r[i][1] == r[i + 1][1] for i in range(2)))
        e.menu(c)
        self.assertEqual(e.menu_marcadas, {"En fila, separadas"}, "el menú marca la colocación actual")
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
        self.assertEqual(pv.tabla.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        """REQ-ACT-01: tools/dibujo.js (banco y comparador) lee `actionLayout` de la vista y dibuja las tres colocaciones
        con las mismas medidas que escritorio/diagrama.py."""
        from escritorio import diagrama
        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        import re
        for nombre in ("ACT_MIN", "ACT_GAP", "ACT_BUS", "ACT_COL", "ACT_LINK"):
            valor = re.search(rf"const {nombre}\s*=\s*(\d+);", js)
            self.assertEqual(int(valor.group(1)), getattr(diagrama, nombre), nombre)
        for texto in ("s.actionLayout", '"fila-separada"', '"columna"', "actionExtra", "drawAction("):
            self.assertIn(texto, js)
        ver = Vista("k", "t", "", lambda: (new_grafcet_document("k"), {}), normalize_options(None))
        self.assertEqual(ver.model["steps"], [])


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
        # redundancias: los paréntesis que sobran y los espacios no se conservan
        self.assertEqual(arbol_a_texto(a("(marcha) AND   (paro OR (Q00 AND M1))")), "marcha AND (paro OR Q00 AND M1)")
        self.assertEqual(arbol_a_texto(a("a AND ?")), "a AND ?")
        # la estructura
        y = a("(↑marcha AND NOT X0) OR (3s/X1 AND CT >= 3)")
        self.assertEqual((y["k"], y["a"]["k"], y["a"]["a"]["k"], y["a"]["b"]["a"]["k"]), ("o", "y", "sube", "etapa"))
        t = y["b"]["a"]
        self.assertEqual((t["k"], t["t1"], t["t2"], t["a"]["n"]), ("temp", "3s", "", "X1"))
        c = y["b"]["b"]
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
        """REQ-EDT-02, REQ-EDT-07: la paleta tiene siete categorías con su color; las memorias son las variables de papel
        «internal»; sus desplegables se llenan con las variables y etapas del modelo."""
        from escritorio.bloques import CATEGORIAS, COLORES, PAPEL
        p = self.prog()
        self.assertEqual([t for _, t in CATEGORIAS], ["Operadores", "Entradas", "Salidas", "Etapas (X)", "Memorias",
                                                      "Comparaciones", "Temporizadores"])
        self.assertEqual(len({COLORES[c] for c, _ in CATEGORIAS}), 7, "colores distintos")
        self.assertEqual(PAPEL["interna"], "internal")
        self.assertEqual([b.toolTip() for b in p.categorias.values()], [t for _, t in CATEGORIAS])
        esperado = {"entrada": ("var", "marcha", "input"), "salida": ("var", "Q00", "output"),
                    "interna": ("var", "M1", "internal"), "etapa": ("etapa", "X0", None), "comparacion": ("cmp", "CT", None)}
        for clave, (k, n, papel) in esperado.items():
            p.elegir_categoria(clave)
            (b,) = p.paleta.bloques()
            self.assertEqual((b["k"], b["n"], b.get("papel")), (k, n, papel), clave)
            self.assertTrue(p.categorias[clave].isChecked())
        p.elegir_categoria("operador")
        self.assertEqual([b["k"] if b["k"] != "const" else b["v"] for b in p.paleta.bloques()],
                         ["y", "o", "no", "sube", "baja", 1, 0])
        p.elegir_categoria("tiempo")
        self.assertEqual([(b["k"], b["t1"], b["t2"]) for b in p.paleta.bloques()], [("temp", "3s", "")])
        self.assertEqual(p.opciones("interna"), [("M1", "M1")], "las memorias booleanas")
        self.assertEqual(p.opciones("etapa"), [("X0", "X0"), ("X1", "X1"), ("active(Inicio)", "active(Inicio)")])
        # lo elegido en un desplegable de la paleta se conserva, y se arrastra
        p.elegir_categoria("entrada")
        p.paleta.elegir((0,), "n", "paro")
        p.elegir_categoria("entrada")
        self.assertEqual(p.paleta.bloques()[0]["n"], "paro")
        p.elegir_categoria("tiempo")
        p.paleta.editar_campo((0,), "t1", "1s")
        p.elegir_categoria("tiempo")
        self.assertEqual(p.paleta.bloques()[0]["t1"], "1s")
        # sin variables de un tipo, el bloque se ofrece vacío
        from escritorio.bloques import Programador
        vacio = Programador(lambda: ({}, []))
        vacio.elegir_categoria("interna")
        self.assertIsNone(vacio.paleta.bloques()[0]["n"])
        vacio.lienzo.soltar(None, vacio.paleta.bloques()[0])
        self.assertEqual(vacio.texto(), "?")
        # el modelo cambia (se crea una memoria): la paleta se llena otra vez
        self.VARS = {**self.VARS, "M2": ("internal", "bool")}
        p.elegir_categoria("interna")
        self.assertEqual(p.opciones("interna"), [("M1", "M1"), ("M2", "M2")])
        self.assertEqual(p.paleta.opciones_desplegable(p.paleta.bloques()[0], "n"), [("M1", "M1"), ("M2", "M2")])

    def test_SEDI64_disposicion_en_columnas(self):
        """REQ-EDT-02: categorías como carpetas en una columna (las siete, con su color), a su derecha la columna de
        bloques de la categoría elegida (uno debajo de otro) y, ocupando el resto, el área de trabajo con la papelera."""
        from PySide6.QtWidgets import QPushButton
        p = self.prog()
        p.resize(900, 300)
        p.show()
        QApplication.processEvents()
        bs = list(p.categorias.values())
        self.assertEqual(len(bs), 7)
        self.assertTrue(all(isinstance(b, QPushButton) and not b.icon().isNull() for b in bs))
        pos = [b.mapTo(p, b.rect().topLeft()) for b in bs]
        self.assertEqual(len({q.x() for q in pos}), 1, "todas en una columna")
        self.assertEqual(sorted(q.y() for q in pos), [q.y() for q in pos], "una debajo de otra")
        self.assertGreater(p.paleta.mapTo(p, p.paleta.rect().topLeft()).x(), pos[0].x() + bs[0].width() - 4,
                           "la paleta, a la derecha de las categorías")
        self.assertGreater(p.lienzo.mapTo(p, p.lienzo.rect().topLeft()).x(),
                           p.paleta.mapTo(p, p.paleta.rect().topLeft()).x(), "y el área, a la derecha de la paleta")
        self.assertGreater(p.lienzo.width(), 300, "el área ocupa el resto")
        p.elegir_categoria("operador")
        QApplication.processEvents()
        cajas = sorted(p.paleta._cajas, key=lambda c: c[2])
        self.assertEqual(len(cajas), 7)
        self.assertEqual(len({x for _, x, _ in cajas}), 1, "los bloques, en una columna")
        self.assertEqual([c[2] for c in cajas], sorted({y for _, _, y in cajas}), "uno debajo de otro")
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


if __name__ == "__main__":
    unittest.main()
