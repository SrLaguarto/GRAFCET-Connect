"""Editor de escritorio (P-IMP-32, paso 3): crear un grafcet secuencial con el ratón, enlazarlo, moverlo, borrarlo,
deshacer, guardarlo, abrirlo y simularlo.

Las pruebas del núcleo (S-EDI01..02) no necesitan Qt. Las de la interfaz (S-EDI03..20) se omiten si PySide6 no está
instalado y usan la plataforma «offscreen»: no abren ventanas ni diálogos (los ganchos y los mensajes se sustituyen).
Ninguna es oráculo del documento 11: comprueban que el editor usa las operaciones de grafcet/editor.py y que lo
que se dibuja y se simula es lo que decide el núcleo.
"""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from grafcet.diagnostics import DiagnosticError  # noqa: E402
from grafcet.editor import Editor, new_grafcet_document  # noqa: E402
from grafcet.persistence import open_model  # noqa: E402
from grafcet.notation import a_nucleo, a_usuario, normalizar_espacios  # noqa: E402
from grafcet.profile import normalize_options  # noqa: E402
from grafcet.view import Vista, layout_from_presentation  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path("C:/Windows/Fonts").is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    from PySide6.QtCore import QPointF, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
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


def centro(M, ident):
    from escritorio.diagrama import posiciones
    return QPointF(*posiciones(M)[ident])


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
        self.assertIn("No compila", w.l_resumen.text())
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
        self.assertEqual([w.paleta.item(i).text() for i in range(w.paleta.count())], ["Etapa", "Transición", "Simultaneidad"],
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
                cb = pv.tabla.cellWidget(fila, col)
                cb.setCurrentIndex(cb.findData(valor))
                cb.activated.emit(cb.currentIndex())
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
            w.props.prog.poner_bloque(nombre, "entrada")
        self.assertEqual((e.texto_condicion(t1), e.texto_condicion(t2)), ("I00", "I01"))
        for datos in ({"tipo": "evento", "variable": "CT", "valor": "CT + 1"}, {"tipo": "continua", "variable": "Q00"},
                      {"tipo": "continua", "variable": "Q01"}):
            d = DialogoAccion(w, e, s1)
            d.tipo.setCurrentIndex(d.tipo.findData(datos["tipo"]))
            d.variable.setCurrentText(datos["variable"])
            d.valor.setText(datos.get("valor", ""))
            if datos["tipo"] == "evento":
                d.evento.poner_bloque("I02", "entrada")
                d.evento.lienzo.e.sel = (0, 1)
                d.evento.botones["sube"].click()
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
        """REQ-EDT-02, REQ-TMP-01: con la etapa X1 en bloques y «Temporizar…», la receptividad es 3s/X1, se guarda como
        delay(3 s, active(1), 0 s) y la transición franquea a los 3 s de activarse la etapa 1."""
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
        w.props.prog.poner_bloque("I00", "entrada")
        e.seleccionar([t2])
        prog = w.props.prog
        prog.poner_bloque("X1", "etapa")
        prog.lienzo.e.sel = (0, 1)
        with mock.patch.object(bloques._Dialogo, "exec", return_value=bloques.QDialog.DialogCode.Accepted):
            prog.botones["temporizar"].click()  # el asistente, con sus valores: 3 s, la etapa elegida, 0 s
        self.assertEqual(w.props.t_texto.text(), "3s/X1")
        self.assertEqual(e.texto_condicion(t2), "delay(3 s, active(`1`), 0 s)")
        self.assertEqual(prog.lienzo.e.b[0]["cat"], "tiempo")
        hecho = self._recorrido(e.ed.model, [(1, {"I00": True}), (2, {"I00": False})], 8)
        self.assertEqual([(x[0], x[1]) for x in hecho], [("0", ["0"]), ("1000000", ["1"]), ("2000000", ["1"]),
                                                         ("4000000", ["0"])])

    def test_SEDI42_programador_por_bloques(self):
        """REQ-EDT-02: los bloques trocean y vuelven a juntar el mismo texto; entre dos operandos ponen ·; NOT y los
        flancos van sobre un bloque o un grupo; los paréntesis se quitan con su pareja; un clic en · lo cambia a +."""
        from escritorio.bloques import Expresion, categoria, juntar, trocear
        roles = {"marcha": "input", "paro": "input", "Q00": "output", "CT": "internal"}
        clase = lambda t: categoria(t, roles, {"X1"})
        for t in ("↑marcha AND NOT paro", "NOT (marcha OR X1) AND CT >= 3", "3s/X1 OR NOT marcha/2s", "↓(marcha AND paro)",
                  "X1 AND (marcha OR (paro AND NOT Q00))", "1", "NOT ↑marcha"):
            self.assertEqual(juntar(trocear(t, clase)), t)
        self.assertEqual([b["cat"] for b in trocear("marcha AND Q00 AND CT >= 3 AND X1 AND 3s/X1 AND nada AND 1", clase)
                          if b["k"] == "atomo"], ["entrada", "salida", "comparacion", "etapa", "tiempo", "otro", "constante"])
        e = Expresion()
        bloque = lambda t: [{"k": "atomo", "t": t, "cat": clase(t), "neg": False, "flanco": ""}]
        e.insertar(bloque("marcha"))
        e.insertar(bloque("X1"))
        self.assertEqual(e.texto(), "marcha AND X1", "entre dos operandos, Y")
        e.sel = (0, 1)
        e.negar()
        e.sel = (0, 3)
        e.negar()
        self.assertEqual(e.texto(), "NOT (NOT marcha AND X1)", "NOT sobre varios bloques: entre paréntesis")
        e.sel, e.cursor = None, len(e.b)
        e.flanco("↑")  # sobre el grupo que acaba de cerrar
        e.insertar([{"k": "op", "t": "OR"}])
        e.insertar(bloque("paro"))
        self.assertEqual(e.texto(), "NOT ↑(NOT marcha AND X1) OR paro")
        e.sel = (0, 1)
        e.quitar()  # el paréntesis se va con su pareja
        self.assertEqual(e.texto(), "NOT marcha AND X1 OR paro")
        e.sel = (2, 5)
        self.assertTrue(e.envolver())
        self.assertEqual(e.texto(), "NOT marcha AND (X1 OR paro)")
        # En el panel: cada cambio en los bloques es la receptividad; un clic en · la cambia a +
        w = self.w
        e2, ids, ts = self.secuencial()
        e2.seleccionar([ts["t1"]])
        prog = w.props.prog
        prog.poner_bloque("paro", "entrada")
        self.assertEqual(e2.texto_condicion(ts["t1"]), "marcha AND paro")
        lienzo = prog.lienzo
        lienzo.resize(400, 60)
        lienzo._cajas, lienzo._huecos, _ = lienzo._maqueta(400)
        QTest.mouseClick(lienzo, Qt.MouseButton.LeftButton, pos=lienzo._cajas[1].center().toPoint())
        self.assertEqual(e2.texto_condicion(ts["t1"]), "marcha OR paro")
        n = len(e2.ed.undo_stack)
        QTest.mouseClick(lienzo, Qt.MouseButton.LeftButton, pos=lienzo._cajas[2].center().toPoint())
        prog.botones["not"].click()
        self.assertEqual((e2.texto_condicion(ts["t1"]), len(e2.ed.undo_stack)), ("marcha OR NOT paro", n + 1))
        QTest.keyClick(lienzo, Qt.Key.Key_Delete)
        self.assertEqual(e2.texto_condicion(ts["t1"]), "marcha")
        # Escribir el texto a mano vuelve a trocearlo en bloques
        w.props.t_texto.setText("↑marcha AND NOT X1")
        w.props.t_texto.textEdited.emit(w.props.t_texto.text())
        self.assertEqual([(b["t"], b["neg"], b["flanco"]) for b in prog.lienzo.e.b if b["k"] == "atomo"],
                         [("marcha", False, "↑"), ("X1", True, "")])

    def test_SEDI43_panel_de_variables(self):
        """REQ-EDT-07, REQ-EDT-06: el diccionario muestra papel, tipo, valor inicial y usos; renombrar actualiza los
        usos; papel y tipo se cambian; una variable usada no se quita y una sin usos sí; todo se deshace."""
        w = self.w
        e, ids, ts = self.secuencial()
        pv = w.variables
        nombres = [pv.tabla.item(r, 0).text() for r in range(pv.tabla.rowCount())]
        self.assertEqual(nombres, ["marcha", "paro"])
        self.assertEqual(pv.tabla.item(0, 5).text(), "1", "marcha se usa en t1")
        pv.tabla.item(0, 0).setText("Marcha")
        self.assertEqual(e.texto_condicion(ts["t1"]), "Marcha", "el renombrado llega a la receptividad")
        cb = pv.tabla.cellWidget(1, 1)
        cb.setCurrentIndex(cb.findData("output"))
        cb.activated.emit(cb.currentIndex())
        self.assertEqual(e.ed.model["variables"][1]["role"], "output")
        pv.tabla.selectRow(0)
        pv.quitar()
        self.assertIn("se usa", pv.msg.text())
        pv.nueva()
        self.assertEqual(e.ed.model["variables"][-1]["name"], "I00")
        pv.tabla.item(2, 3).setText("1")  # valor inicial de una entrada
        self.assertIs(e.ed.model["variables"][-1]["initialValue"], True)
        self.assertFalse(pv.tabla.item(1, 3).flags() & Qt.ItemFlag.ItemIsEditable, "una salida empieza en 0")
        pv.tabla.selectRow(2)
        pv.quitar()
        self.assertEqual(len(e.ed.model["variables"]), 2)
        e.deshacer()
        e.deshacer()
        self.assertEqual(len(e.ed.model["variables"]), 3)

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
        self.assertEqual(list(opciones), ["Añadir acción…"])
        pedidas = []
        e.pedir_accion = lambda sid, aid: pedidas.append((sid, aid))
        opciones["Añadir acción…"]()
        self.assertEqual(pedidas, [(ids["1"], None)])
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
        self.assertIn("Quitar acción", dict(e.menu(dentro)))
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

if __name__ == "__main__":
    unittest.main()
