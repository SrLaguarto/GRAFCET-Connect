"""Simulador de escritorio (P-IMP-29): abrir y guardar modelos, colocación automática, entradas numéricas y la
ventana Qt sin pantalla.

Las pruebas del núcleo (S-APP01..04) no necesitan Qt. Las de la ventana (S-APP05..16) se omiten si PySide6 no
está instalado; usan la plataforma «offscreen» de Qt, sin abrir ventanas. Ninguna es oráculo del documento 11:
comprueban que el simulador muestra lo que decide el motor, sin cambiar la semántica.
"""
import os
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers import M, S  # noqa: E402

from grafcet.canonical import canonical_bytes  # noqa: E402
from grafcet.diagnostics import DiagnosticError  # noqa: E402
from grafcet.editor import Editor, new_model_document  # noqa: E402
from grafcet.examples import EJEMPLOS  # noqa: E402
from grafcet.persistence import add_document, new_project, open_model, save_project  # noqa: E402
from grafcet.profile import normalize_options  # noqa: E402
from grafcet.values import TypeSpec  # noqa: E402
from grafcet.view import Vista, auto_layout, input_value, layout_from_presentation, presentation_for  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path("C:/Windows/Fonts").is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:  # el núcleo no depende de Qt
    QT = False


def guardar_ejemplo(key: str, root: Path) -> Path:
    m, layout = EJEMPLOS[key][2]()
    project = new_project(f"proyecto-{key}", EJEMPLOS[key][0])
    add_document(project, m.doc)
    add_document(project, presentation_for(m.doc, layout))
    save_project(root, project)
    return root


def run(v: Vista, *ops: tuple[str, dict]) -> dict:
    for op, body in ops:
        v.act(op, body)
    return v.state()


class Nucleo(unittest.TestCase):
    def test_SAPP01_abrir_lo_guardado(self):
        """REQ-DAT-02: un ejemplo guardado como proyecto se abre igual (modelo y posiciones) y simula
        igual, tanto desde la carpeta como desde el documento de modelo suelto."""
        with tempfile.TemporaryDirectory() as tmp:
            root = guardar_ejemplo("contador-inestable", Path(tmp) / "p")
            m, layout = EJEMPLOS["contador-inestable"][2]()
            model_file = next(root.glob("model-*.json"))
            for ruta in (root, root / "manifest.json", model_file):
                op = open_model(ruta)
                self.assertTrue(op.executable, ruta)
                self.assertEqual(canonical_bytes(op.doc), canonical_bytes(m.doc), "el modelo no cambia al guardarlo")
                self.assertEqual(len(op.presentations), 1, "se encuentra su presentación")
                self.assertEqual(layout_from_presentation(op.presentations[0]), {k: (float(x), float(y))
                                                                                 for k, (x, y) in layout.items()})
                v = Vista("p", op.title, "", lambda: (op.doc, layout_from_presentation(op.presentations[0])),
                          normalize_options(None))
                st = run(v, ("fijar", {"cambios": {"I00": True}}), ("fijar", {"cambios": {"I02": True}}),
                         ("fijar", {"cambios": {"I02": False}}))
                self.assertEqual((st["situation"], st["values"]["CT"]), (["1"], "1"), "2 suma aunque sea inestable")
            self.assertEqual(open_model(root).title, "Contador con etapa inestable")

    def test_SAPP02_abrir_rechaza_lo_que_no_es_modelo(self):
        """REQ-DAT-03, REQ-ROB-02: un documento de otra familia no se abre; uno con campos semánticos desconocidos
        se abre pero no se simula; un fichero ilegible da D-FORMATO."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pres = tmp / "vista.json"
            m, layout = EJEMPLOS["temporizada"][2]()
            pres.write_bytes(canonical_bytes(presentation_for(m.doc, layout)))
            with self.assertRaises(DiagnosticError) as cm:
                open_model(pres)
            self.assertEqual(cm.exception.diagnostics[0].code, "D-FORMATO")
            raro = dict(m.doc, campoNuevo=1)
            (tmp / "raro.json").write_bytes(canonical_bytes(raro))
            op = open_model(tmp / "raro.json")
            self.assertFalse(op.executable)
            self.assertEqual(op.presentations, [], "la presentación suelta es de otro nombre: no se toma")
            (tmp / "roto.json").write_text("{no es json", encoding="utf-8")
            with self.assertRaises(DiagnosticError) as cm:
                open_model(tmp / "roto.json")
            self.assertEqual(cm.exception.diagnostics[0].code, "D-FORMATO")

    def test_SAPP03_colocacion_automatica(self):
        """Un modelo sin presentación se dibuja: cada etapa, macroetapa y transición tiene posición, dos etapas no
        coinciden y las iniciales quedan arriba de su parcial."""
        for key, (_, _, build) in EJEMPLOS.items():
            m, _ = build()
            lay = auto_layout(m.doc)
            ids = ([s["id"] for s in m.doc["steps"]] + [t["id"] for t in m.doc["transitions"]]
                   + [x["id"] for x in m.doc["hierarchy"]["macros"]])
            self.assertEqual(sorted(lay), sorted(ids), key)
            nodes = [lay[s["id"]] for s in m.doc["steps"]] + [lay[x["id"]] for x in m.doc["hierarchy"]["macros"]]
            self.assertEqual(len(set(nodes)), len(nodes), f"{key}: dos etapas en el mismo sitio")
            for s in m.doc["steps"]:
                if s["initial"]:
                    same = [lay[x["id"]][1] for x in m.doc["steps"] if x["partialRef"] == s["partialRef"]]
                    self.assertEqual(lay[s["id"]][1], min(same), f"{key}: {s['id']} inicial arriba")
            v = Vista(key, "", "", lambda m=m: (m.doc, None), normalize_options(None))
            self.assertEqual(len(v.model["steps"]), len(m.doc["steps"]))

    def test_SAPP04_entradas_numericas(self):
        """REQ-SIM-02: una entrada numérica escrita a mano admite coma decimal y respeta tipo, escala y rango."""
        dec = TypeSpec("decimal", 1)
        self.assertEqual(input_value(dec, "2,5"), Fraction(5, 2))
        self.assertEqual(input_value(TypeSpec("int"), " -3 "), -3)
        for t, text in ((dec, "2,55"), (TypeSpec("int"), "3,5"), (TypeSpec("int"), "x"), (TypeSpec("bool"), "1")):
            with self.assertRaises(DiagnosticError, msg=text):
                input_value(t, text)
        m = M().var("n", "input", "int").var("y", "output").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "n >= 3").cont("B", "y")
        v = Vista("n", "", "", lambda: (m, None), normalize_options(None))
        self.assertEqual(v.model["numericInputs"], {"n": "int"})
        st = run(v, ("valor", {"var": "n", "texto": "2"}))
        self.assertEqual(st["situation"], ["A"])
        st = run(v, ("avanzar", {"us": S}), ("valor", {"var": "n", "texto": "3"}))
        self.assertEqual((st["situation"], st["outputs"]["y"]["value"]), (["B"], True))

    def test_SAPP14_nombres_en_vez_de_id(self):
        """REQ-EDT-07, REQ-SIM-03: un modelo hecho con el editor (ID internos) se dibuja y se traza con los nombres:
        «X E1», «marcha», «motor», «S = {E1}»; los ID solo se usan como claves."""
        m, e0, e1, marcha, motor = modelo_del_editor()
        v = Vista("ed", "Editor", "", lambda: (m, None), normalize_options(None))
        M = v.model
        nombres = {x["id"]: x["label"] for x in M["steps"]}
        self.assertEqual(sorted(nombres.values()), ["E0", "E1"])
        self.assertEqual(M["names"][marcha], "marcha")
        self.assertEqual(M["names"][motor], "motor")
        self.assertEqual(M["inputs"], [marcha])
        self.assertEqual(sorted(t["label"] for t in M["transitions"]), ["t1", "t2"], "sin etiqueta, t1, t2… y no el ID")
        con = {t["label"]: t["cond"] for t in M["transitions"]}
        self.assertEqual(sorted(con.values(), key=lambda c: c[0]["t"]),
                         [[{"t": "2s"}, {"t": "/"}, {"t": "X"}, {"t": "1", "s": True}], [{"t": "marcha"}]])  # la etapa E1 es X1
        acc = next(a for s in M["steps"] for a in s["actions"])
        self.assertEqual((acc["text"], acc["target"]), ([{"t": "motor"}], motor), "se muestra el nombre, la clave es el ID")
        st = run(v, ("entrada", {"var": marcha}), ("avanzar", {"us": 500_000}))
        self.assertEqual(st["situation"], [e1])
        textos = [r["text"] for r in st["trace"]]
        self.assertTrue(any("S = {E1}" in t for t in textos), textos)
        self.assertTrue(any("marcha=true" in t for t in textos), textos)
        self.assertFalse(any(i in t for t in textos for i in (e0, e1, marcha)), "la traza no muestra ID internos")
        self.assertEqual(st["temporal"][next(iter(st["temporal"]))]["where"], "transición t2")
        self.assertEqual(M["names"][st["outputs"][motor]["contributors"][0]], "E1", "la columna «Contribuyen» dice la etapa")
        # Los mensajes del motor también se escriben con nombres
        from grafcet.view import substitute
        self.assertEqual(substitute(f"la etapa {e1} y {marcha}", M["names"]), "la etapa E1 y marcha")

    def test_SAPP15_ejemplos_no_cambian(self):
        """REQ-SIM-03: en los ejemplos el ID es el nombre: mostrar nombres no cambia nada del dibujo ni de la traza."""
        for key, (title, help_text, build) in EJEMPLOS.items():
            v = Vista(key, title, help_text, build, normalize_options(None))
            for i, n in v.model["names"].items():
                self.assertEqual(i, n, f"{key}: {i}")


def modelo_del_editor():
    """Un grafcet hecho con el editor: sus ID son internos (s-…, v-…, t-…), sus nombres, los que se ven."""
    ed = Editor(new_model_document("m"))
    g = ed.add_partial("G")
    marcha = ed.add_variable("marcha", "input", {"kind": "bool"})
    motor = ed.add_variable("motor", "output", {"kind": "bool"})
    e0 = ed.add_step(g, "E0", True, at=(100, 60))
    e1 = ed.add_step(g, "E1", at=(100, 220))
    ed.add_transition(g, "marcha", [e0], [e1], at=(100, 140))
    ed.add_transition(g, "delay(2 s, active(E1), 0 s)", [e1], [e0], at=(100, 300))
    ed.add_continuous_action(e1, motor)
    return ed.model, e0, e1, marcha, motor


@unittest.skipUnless(QT, "PySide6 no está instalado")
class Ventana(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from PySide6.QtCore import QSettings
        from escritorio.ventana import Ventana as V
        cls.tmp = tempfile.TemporaryDirectory()  # las preferencias de las pruebas no tocan las del usuario
        cls.w = V(QSettings(str(Path(cls.tmp.name) / "ajustes.ini"), QSettings.Format.IniFormat))

    @classmethod
    def tearDownClass(cls):
        cls.w.a_ejecutar.setChecked(False)
        cls.w.ajustes.sync()
        cls.tmp.cleanup()

    def test_SAPP05_ejemplos_en_la_ventana(self):
        """REQ-SIM-03: cada ejemplo se carga y se dibuja; un clic en una entrada hace evolucionar el grafcet como en el banco."""
        from escritorio.diagrama import imagen
        for key in EJEMPLOS:
            self.w.cargar_ejemplo(key)
            self.assertEqual(self.w.v.key, key)
            self.assertGreater(len(self.w.diagrama.scene().items()), 4, key)
            img = imagen(self.w.v.model, self.w.v.state(), 1.0)
            self.assertGreater(img.width() * img.height(), 10_000, key)
        self.w.cargar_ejemplo("contador-inestable")
        self.w.botones["I00"].click()
        self.assertEqual(self.w.v.state()["situation"], ["1"])
        self.assertEqual(self.w.botones["I00"].text(), "I00 = 1")
        self.w.botones["I02"].click()
        self.w.botones["I02"].click()
        self.assertEqual(self.w.v.state()["values"]["CT"], "1")
        self.assertTrue(any("CT" in self.w.t_vars.item(i, 0).text() for i in range(self.w.t_vars.rowCount())))
        self.w.cargar_ejemplo("conflicto")
        self.assertFalse(self.w.diag.isHidden(), "el error de compilación se muestra")
        self.assertIn("no puede compilarse", self.w.diag.text())

    def test_SAPP06_guardar_y_abrir_en_la_ventana(self):
        """REQ-EDT-01, REQ-DAT-02: «Guardar como proyecto» y «Abrir modelo» conservan el modelo y su dibujo."""
        self.w.cargar_ejemplo("macroetapa")
        before = (self.w.v.model["steps"], self.w.v.model["transitions"])
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "macro"
            self.w.guardar_en(dest)
            self.assertTrue(self.w.abrir_ruta(dest))
            self.assertEqual(self.w.fuente["tipo"], "fichero")
            self.assertEqual((self.w.v.model["steps"], self.w.v.model["transitions"]), before)
            self.w.botones["p"].click()
            self.assertEqual(self.w.v.state()["situation"], ["E1"])

    def test_SAPP07_lecturas_reinician(self):
        """Cambiar una lectura reinicia la simulación y se señala como distinta de la decidida."""
        self.w.cargar_ejemplo("bloqueo-u03")
        self.w._opciones({**self.w.options, "U-03": "recorrido"})
        self.assertEqual(self.w.v.options["U-03"], "recorrido")
        self.assertIn("distintas de las decididas: U-03", self.w.l_lect.text(), "el aviso va en la barra de estado")
        self.w.botones["p"].click()
        self.assertEqual(self.w.v.state()["situation"], ["C"], "con «recorrido» la subida llega a C")
        self.w._opciones(normalize_options(None))
        self.assertEqual(self.w.l_lect.text(), "", "con las lecturas decididas no hay aviso")

    def test_SAPP08_ajustes_y_lecturas(self):
        """REQ-SEM-09: «Ajustes» (entre Simulación y Ayuda) tiene las lecturas; el diálogo no ofrece «detener» y el
        panel derecho ya no las lleva."""
        from PySide6.QtWidgets import QComboBox, QGroupBox
        from escritorio.ventana import Lecturas
        titulos = [a.text().replace("&", "") for a in self.w.menuBar().actions()]
        self.assertEqual(titulos[titulos.index("Simulación") + 1:], ["Ajustes", "Ayuda"])
        d = Lecturas(self.w, self.w.options)
        self.assertGreater(len(d.combos), 10)
        for q, cb in d.combos.items():
            self.assertNotIn("detener", [cb.itemData(i) for i in range(cb.count())], q)
        self.assertEqual(d.options(), self.w.options, "sin tocar nada, las lecturas no cambian")
        self.assertFalse(hasattr(self.w, "u03"))
        self.assertNotIn("Lecturas de interpretación", [g.title() for g in self.w.scroll.findChildren(QGroupBox)])
        self.assertEqual(self.w.scroll.findChildren(QComboBox), [], "el panel derecho no tiene combos de lecturas")

    def test_SAPP09_tiempo_real_pausa_y_paso(self):
        """REQ-SIM-03: al cargar, el tiempo real está activo; pausa, paso y reinicio funcionan."""
        self.w.cargar_ejemplo("temporizada")
        self.assertTrue(self.w.a_ejecutar.isChecked() and self.w.rt.isActive(), "corre desde que se carga")
        self.assertFalse(hasattr(self.w, "b_tiempo"), "ya no hay botones de tiempo lógico")
        self.w.a_ejecutar.setChecked(False)
        self.assertFalse(self.w.rt.isActive())
        self.assertFalse(self.w.a_paso.isEnabled(), "estable y sin vencimientos: Paso no tiene nada que hacer")
        self.w.botones["marcha"].click()
        self.assertEqual(self.w.v.state()["situation"], ["E1"])
        self.assertEqual(self.w.v.state()["nextEvent"], "3 s")
        self.assertTrue(self.w.a_paso.isEnabled())
        self.w.paso_evolucion()  # hasta el vencimiento exacto de 3 s
        self.assertEqual((self.w.v.state()["time"], self.w.v.state()["situation"]), ("3 s", ["E2"]))
        self.assertIn("τ = 3 s", self.w.l_reloj.text())
        self.w.reiniciar()
        self.assertEqual(self.w.v.state()["situation"], ["E0"])
        self.assertTrue(self.w.a_ejecutar.isChecked(), "tras reiniciar vuelve a correr")
        self.w.cargar_ejemplo("conflicto")  # el motor no arranca: no hay tiempo real
        self.assertFalse(self.w.a_ejecutar.isChecked())

    def test_SAPP10_temporizador_en_dibujo_y_tabla(self):
        """REQ-SIM-03: «temporizada», con E1 activa y 1 s transcurrido, muestra «1 s / 3 s» junto a la receptividad y en
        la tabla de temporizadores; al vencer, «3 s ✓»."""
        self.w.cargar_ejemplo("temporizada")
        self.w.a_ejecutar.setChecked(False)
        self.assertFalse(self.w.c_temp.isHidden())
        self.assertEqual(self.w.t_temp.rowCount(), 1)
        self.assertEqual(self.w.t_temp.item(0, 1).text(), "parado")
        self.w.botones["marcha"].click()
        self.w._act("avanzar", us=1_000_000)

        def textos():
            return [it.toPlainText() for it in self.w.diagrama.scene().items() if hasattr(it, "toPlainText")]
        self.assertIn("1 s / 3 s", textos())
        fila = [self.w.t_temp.item(0, j).text() for j in range(4)]
        self.assertEqual(fila, ["transición t2", "contando", "1 s", "3 s"])
        self.w._act("avanzar", us=2_000_000)  # vence y t2 franquea: E2, y el temporizador vuelve a parado
        self.assertEqual(self.w.v.state()["situation"], ["E2"])
        self.assertNotIn("1 s / 3 s", textos())
        self.assertEqual(self.w.t_temp.item(0, 1).text(), "parado")
        # Un retardo en la condición de una acción: «2 s ✓» al vencer, junto a la condición de la acción
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio.diagrama import dibujar
        m = M().var("p").var("y", "output").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "p").cont("B", "y", "delay(2 s, p, 0 s)")
        v = Vista("m", "", "", lambda: (m, None), normalize_options(None))
        run(v, ("fijar", {"cambios": {"p": True}}), ("avanzar", {"us": 1_500_000}))
        sc = QGraphicsScene()
        dibujar(sc, v.model, v.state())
        self.assertIn("1,5 s / 2 s", [it.toPlainText() for it in sc.items() if hasattr(it, "toPlainText")])
        self.assertEqual([t["estado"] for t in v.state()["temporal"].values()], ["contando"])
        run(v, ("avanzar", {"us": 500_000}))
        dibujar(sc, v.model, v.state())
        self.assertIn("2 s ✓", [it.toPlainText() for it in sc.items() if hasattr(it, "toPlainText")])
        self.assertEqual(([t["estado"] for t in v.state()["temporal"].values()], v.state()["outputs"]["y"]["value"]),
                         (["vencido"], True))

    def test_SAPP11_paneles_plegables(self):
        """REQ-SIM-03: el panel derecho y el inferior se pliegan del todo con su flecha y desde «Ver»; el estado se guarda."""
        from PySide6.QtCore import QSettings
        from escritorio.ventana import Ventana as V
        w = self.w
        self.assertFalse(w.derecho.isHidden() or w.inferior.isHidden())
        w.flechas["derecho"].click()
        self.assertTrue(w.derecho.isHidden() and not w.a_derecho.isChecked())
        self.assertEqual(w.flechas["derecho"].text(), "◂")
        w.flechas["inferior"].click()
        self.assertTrue(w.inferior.isHidden() and not w.a_inferior.isChecked())
        self.assertEqual(w.flechas["inferior"].text(), "▴")
        self.assertFalse(w.ajustes.value("paneles/derecho", True, type=bool))
        w.a_derecho.setChecked(True)  # desde el menú Ver
        w.a_inferior.setChecked(True)
        self.assertFalse(w.derecho.isHidden() or w.inferior.isHidden())
        self.assertTrue(w.ajustes.value("paneles/inferior", False, type=bool))
        self.assertEqual(w.flechas["derecho"].text(), "▸")
        w.a_derecho.setChecked(False)  # un arranque posterior lo recuerda
        w.ajustes.sync()
        otra = V(QSettings(w.ajustes.fileName(), QSettings.Format.IniFormat))
        try:
            self.assertTrue(otra.derecho.isHidden() and not otra.a_derecho.isChecked())
        finally:
            otra.a_ejecutar.setChecked(False)
            otra.deleteLater()
            w.a_derecho.setChecked(True)

    def test_SAPP12_zoom_se_conserva(self):
        """REQ-SIM-03: «+», «−» y la rueda con Ctrl cambian el zoom; un refresco lo conserva; «Ajustar» vuelve a encajar."""
        w, d = self.w, self.w.diagrama
        w.cargar_ejemplo("contador-flanco")
        w.a_ejecutar.setChecked(False)
        d.ajustar()
        base = d.escala()
        d.b_mas.click()
        d.b_mas.click()
        k = d.escala()
        self.assertGreater(k, base * 1.3)
        self.assertEqual(d.l_zoom.text(), f"{round(k * 100)} %")
        w.botones["I00"].click()  # refresca el dibujo
        w.refrescar()
        self.assertAlmostEqual(d.escala(), k, places=6, msg="el zoom elegido se mantiene al refrescar")
        d.b_menos.click()
        self.assertLess(d.escala(), k)
        d.b_ajustar.click()
        self.assertAlmostEqual(d.escala(), base, places=6)
        # La rueda del ratón, con o sin Ctrl, acerca y aleja
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent
        for mod in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier):
            antes = d.escala()
            for delta, sentido in ((120, 1), (-120, -1)):
                ev = QWheelEvent(QPointF(100, 100), d.mapToGlobal(QPointF(100, 100)), QPoint(0, 0), QPoint(0, delta),
                                 Qt.MouseButton.NoButton, mod, Qt.ScrollPhase.NoScrollPhase, False)
                k = d.escala()
                self.app.sendEvent(d.viewport(), ev)
                self.assertEqual(d.escala() > k, sentido > 0, f"rueda {delta} con {mod}")
            self.assertAlmostEqual(d.escala(), antes, places=6)
        d.ajustar()

    def test_SAPP16_ventana_con_nombres(self):
        """REQ-EDT-07, REQ-SIM-03: un modelo del editor, guardado y abierto en la ventana, muestra nombres en el dibujo,
        las entradas, las tablas y la traza."""
        m, e0, e1, marcha, motor = modelo_del_editor()
        with tempfile.TemporaryDirectory() as tmp:
            project = new_project("p-editor", "Editor")
            add_document(project, m)
            add_document(project, presentation_for(m, {e0: (100, 60), e1: (100, 220)}))
            save_project(Path(tmp) / "p", project)
            self.assertTrue(self.w.abrir_ruta(Path(tmp) / "p"))
        w = self.w
        w.a_ejecutar.setChecked(False)
        self.assertEqual(list(w.botones), [marcha])
        self.assertEqual(w.botones[marcha].text(), "marcha = 0")
        w.botones[marcha].click()
        self.assertEqual(w.botones[marcha].text(), "marcha = 1")
        filas = [[w.t_vars.item(i, j).text() for j in range(2)] for i in range(w.t_vars.rowCount())]
        self.assertEqual(filas, [["motor", "salida continua"]])
        self.assertEqual(w.t_temp.item(0, 0).text(), "transición t2")
        self.assertEqual(w.t_vars.item(0, 3).text(), "E1")
        textos = [it.toPlainText() for it in w.diagrama.scene().items() if hasattr(it, "toPlainText")]
        for esperado in ("E0", "E1", "motor", "marcha"):
            self.assertIn(esperado, textos)
        self.assertFalse(any(t.startswith(("s-", "v-", "g-")) for t in textos), textos)
        self.assertTrue(any("S = {E1}" in w.traza.item(i).text() for i in range(w.traza.count())))

    def test_SAPP13_tiempos_truncados_a_dos_decimales(self):
        """REQ-SIM-03: lo que lleva un temporizador y τ se muestran truncados a la baja a 2 decimales; el preset, tal cual."""
        w = self.w
        w.cargar_ejemplo("temporizada")
        w.a_ejecutar.setChecked(False)
        w.botones["marcha"].click()
        w._act("avanzar", us=1_239_999)
        self.assertEqual(w.v.state()["time"], "1,239999 s", "el estado exacto no se toca")
        self.assertEqual(w.t_temp.item(0, 2).text(), "1,23 s")
        self.assertEqual(w.l_reloj.text().split(" · ")[0], "τ = 1,23 s")
        w._act("avanzar", us=1)
        self.assertEqual((w.t_temp.item(0, 2).text(), w.l_reloj.text().split(" · ")[0]), ("1,24 s", "τ = 1,24 s"))
        self.assertEqual(w.t_temp.item(0, 3).text(), "3 s")
        self.assertEqual(w.a_ejecutar.text(), "▶ Ejecutar")
        w.a_ejecutar.setChecked(True)
        self.assertEqual(w.a_ejecutar.text(), "‖ Pausa")
        w.a_ejecutar.setChecked(False)


if __name__ == "__main__":
    unittest.main()
