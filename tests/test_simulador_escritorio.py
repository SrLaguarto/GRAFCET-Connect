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
from unittest import mock

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
        con = {t["label"]: [{k: v for k, v in s.items() if k != "eval"} for s in t["cond"]] for t in M["transitions"]}
        for t in M["transitions"]:
            raiz = t["conditionRef"]
            esperadas = [[raiz]] if t["label"] == "t1" else [[raiz], [raiz], [raiz + ".1", raiz], [raiz + ".1", raiz]]
            self.assertEqual([s["eval"] for s in t["cond"]], esperadas)
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
        """REQ-SIM-03: cada ejemplo se carga y se dibuja; abrirlo deja Pausa sin estado y, con Play, un clic en una entrada hace
        evolucionar el grafcet como en el banco."""
        from escritorio.diagrama import imagen
        for key in EJEMPLOS:
            self.w.cargar_ejemplo(key)
            self.assertEqual(self.w.v.key, key)
            self.assertGreater(len(self.w.diagrama.scene().items()), 4, key)
            with mock.patch("escritorio.ventana.QMessageBox.warning"):  # los que no compilan (conflicto) avisan al hacer Play
                self.w.a_ejecutar.setChecked(True)  # el dibujo de la simulación, con la sesión en marcha
            img = imagen(self.w.v.model, self.w.v.state(), 1.0)
            self.assertGreater(img.width() * img.height(), 10_000, key)
            self.w.a_ejecutar.setChecked(False)
        self.w.cargar_ejemplo("contador-inestable")
        self.assertEqual(self.w.v.state().get("situation", []), [], "abrir deja Pausa sin estado: lo arranca Play")
        self.assertEqual((self.w.t_vars.rowCount(), self.w.t_temp.rowCount(), self.w.traza.count()), (0, 0, 0))
        self.assertFalse(any(b.isEnabled() for b in self.w.botones.values()), "sin sesión, las entradas no responden")
        self.w.a_ejecutar.setChecked(True)
        self.w._cambiar_tipo_entrada("I00", True)  # esta prueba mantiene la entrada
        self.w.botones["I00"].click()
        self.assertEqual(self.w.v.state()["situation"], ["1"])
        self.assertEqual(self.w.botones["I00"].text(), "I00 = 1")
        self.w._cambiar_tipo_entrada("I02", True)  # esta prueba mantiene la entrada
        self.w.botones["I02"].click()
        self.w._cambiar_tipo_entrada("I02", True)  # esta prueba mantiene la entrada
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
            self.assertEqual(self.w.v.state().get("situation", []), [], "abrir deja Pausa sin estado")
            self.w.a_ejecutar.setChecked(True)  # Play: la sesión arranca desde la situación inicial
            self.w._cambiar_tipo_entrada("p", True)  # esta prueba mantiene la entrada
            self.w.botones["p"].click()
            self.assertEqual(self.w.v.state()["situation"], ["E1"])
            self.w.a_ejecutar.setChecked(False)

    def test_SAPP07_lecturas_reinician(self):
        """Cambiar una lectura reinicia la simulación (queda en Pausa, sin estado, hasta Play) y se señala como distinta de la
        decidida."""
        self.w.cargar_ejemplo("bloqueo-u03")
        try:
            self.w._opciones({**self.w.options, "U-03": "recorrido"})
            self.assertEqual(self.w.v.options["U-03"], "recorrido")
            self.assertIn("distintas de las decididas: U-03", self.w.l_lect.text(), "el aviso va en la barra de estado")
            self.assertEqual(self.w.v.state().get("situation", []), [], "cambiar la lectura deja Pausa sin estado")
            self.w.a_ejecutar.setChecked(True)  # Play: ejecución nueva con la lectura elegida
            self.w._cambiar_tipo_entrada("p", True)  # esta prueba mantiene la entrada
            self.w.botones["p"].click()
            self.assertEqual(self.w.v.state()["situation"], ["C"], "con «recorrido» la subida llega a C")
            self.w._opciones(normalize_options(None))  # en Play: se reinicia y sigue en Play, con las lecturas decididas
            self.assertEqual(self.w.l_lect.text(), "", "con las lecturas decididas no hay aviso")
            self.assertEqual((self.w.a_ejecutar.isChecked(), self.w.v.state()["situation"]), (True, ["A"]), "sigue en Play, de cero")
        finally:
            self.w.a_ejecutar.setChecked(False)
            self.w._opciones(normalize_options(None))  # un fallo no deja las lecturas cambiadas a las pruebas siguientes

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

    def test_SAPP09_play_pausa_y_un_solo_control(self):
        """REQ-SIM-03: un solo control de ejecución. Play simula en tiempo real (traza abajo, sin paleta) y Pausa detiene y
        vuelve a editar; ya no hay botones, menús ni atajos Editar, Simular, Paso ni Completar. Excepción registrada a
        «al cargar, el tiempo real corre» (P-IMP-60): al abrir, el programa queda en Pausa."""
        from PySide6.QtGui import QAction
        w = self.w
        w.cargar_ejemplo("temporizada")
        self.assertEqual((w.modo, w.a_ejecutar.isChecked(), w.rt.isActive()), ("editar", False, False), "abrir deja Pausa")
        self.assertEqual(w.a_ejecutar.text(), "Play")
        self.assertIsNotNone(w.edicion)
        self.assertEqual((w.derecho.currentIndex(), w.inferior.currentIndex()), (1, 1), "paleta, propiedades y opciones")
        self.assertFalse(w.dock.isHidden())
        for nombre in ("a_editar", "a_simular", "a_paso", "a_completar", "tb_modo", "g_modo", "paso", "paso_evolucion"):
            self.assertFalse(hasattr(w, nombre), nombre)
        textos = {a.text().replace("&", "") for a in w.findChildren(QAction)}
        self.assertFalse(textos & {"Editar", "Simular", "Paso", "Completar recorrido"}, textos)
        atajos = {k.toString() for a in w.findChildren(QAction) for k in a.shortcuts()}
        self.assertFalse(atajos & {"Ctrl+1", "Ctrl+2", "F10", "F11"}, atajos)
        self.assertIn("F5", atajos)
        # Play: simula, el tiempo real corre
        w.a_ejecutar.setChecked(True)
        self.assertEqual((w.modo, w.a_ejecutar.text(), w.rt.isActive()), ("simular", "Stop", True))
        self.assertEqual((w.derecho.currentIndex(), w.inferior.currentIndex()), (0, 0), "entradas y traza")
        self.assertTrue(w.dock.isHidden() and w.flechas["izquierdo"].isHidden(), "sin paleta")
        self.assertFalse(hasattr(self.w, "b_tiempo"), "ya no hay botones de tiempo lógico")
        w._cambiar_tipo_entrada("marcha", True)  # esta prueba mantiene la entrada
        w.botones["marcha"].click()
        self.assertEqual((w.v.state()["situation"], w.v.state()["nextEvent"]), (["E1"], "3 s"))
        w._act("avanzar", us=3_000_000)  # lo que hace el tiempo real hasta el vencimiento exacto de 3 s
        self.assertEqual((w.v.state()["time"], w.v.state()["situation"]), ("3 s", ["E2"]))
        self.assertIn("τ = 3 s", w.l_reloj.text())
        # Pausa: detiene y vuelve a editar
        w.a_ejecutar.setChecked(False)
        self.assertEqual((w.modo, w.a_ejecutar.text(), w.rt.isActive()), ("editar", "Play", False))
        self.assertEqual((w.derecho.currentIndex(), w.inferior.currentIndex()), (1, 1))
        self.assertFalse(w.dock.isHidden())
        # Pausa = todo a 0 hasta un nuevo Play: sin etapas activas ni temporizadores, y las tablas no enseñan la sesión anterior
        self.assertEqual(w.v.state().get("situation", []), [])
        self.assertEqual(w.v.state().get("temporal", {}), {})
        self.assertEqual((w.t_vars.rowCount(), w.t_temp.rowCount(), w.traza.count()), (0, 0, 0))
        self.assertFalse(any(b.isEnabled() for b in w.botones.values()), "sin sesión, las entradas no responden")
        # Play otra vez, sin editar entre medias: sesión nueva desde la situación inicial (ya no sigue donde estaba)
        w.a_ejecutar.setChecked(True)
        self.assertEqual((w.v.state()["situation"], w.v.state()["time"]), (["E0"], "0 s"))
        self.assertEqual(w.botones["marcha"].text(), "marcha = 0", "las entradas también vuelven a su valor inicial")
        w.a_ejecutar.setChecked(False)
        w.cargar_ejemplo("conflicto")  # no compila: Play avisa y sigue en Pausa
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.a_ejecutar.setChecked(True)
        self.assertEqual((aviso.call_count, w.a_ejecutar.isChecked(), w.modo), (1, False, "editar"))

    def test_SAPP17_reiniciar_en_play_y_en_pausa(self):
        """REQ-SIM-03, REQ-SIM-04: Reiniciar vuelve a la situación inicial y en Play sigue en Play; en Pausa, que ya está todo
        a 0 y sin estado hasta un nuevo Play, no hay nada que reiniciar: sigue parado y editable, sin etapas activas."""
        w = self.w
        w.cargar_ejemplo("temporizada")
        w.a_ejecutar.setChecked(True)
        w._cambiar_tipo_entrada("marcha", True)  # esta prueba mantiene la entrada
        w.botones["marcha"].click()
        self.assertEqual(w.v.state()["situation"], ["E1"])
        anterior = w.v.s
        w.reiniciar()
        self.assertIsNot(w.v.s, anterior)
        self.assertEqual((w.v.state()["situation"], w.v.state()["time"]), (["E0"], "0 s"))
        self.assertEqual((w.a_ejecutar.isChecked(), w.modo, w.rt.isActive()), (True, "simular", True), "sigue en Play")
        self.assertEqual(w.botones["marcha"].text(), "marcha = 0", "las entradas vuelven a su valor inicial")
        w._cambiar_tipo_entrada("marcha", True)  # esta prueba mantiene la entrada
        w.botones["marcha"].click()
        self.assertEqual(w.v.state()["situation"], ["E1"])
        w.a_ejecutar.setChecked(False)
        self.assertEqual(w.v.state().get("situation", []), [], "Pausa: sin etapas activas")
        w.reiniciar()  # en Pausa: ya está todo a 0; no crea una sesión en marcha
        self.assertEqual(w.v.state().get("situation", []), [])
        self.assertEqual(w.v.s.status, "preparada", "sesión sin iniciar: ni situación ni valores")
        self.assertEqual((w.a_ejecutar.isChecked(), w.modo, w.rt.isActive()), (False, "editar", False), "sigue en Pausa")
        w.a_ejecutar.setChecked(True)
        self.assertEqual(w.v.state()["situation"], ["E0"], "Play arranca desde el estado inicial")
        w.a_ejecutar.setChecked(False)

    def test_SAPP18_abrir_ejemplo_o_modelo_deja_pausa_y_edicion(self):
        """REQ-SIM-03, REQ-EDT-01: al abrir un ejemplo o un modelo guardado, el programa queda parado y editable aunque
        estuviera en Play; Play arranca."""
        w = self.w
        w.cargar_ejemplo("temporizada")
        w.a_ejecutar.setChecked(True)
        self.assertTrue(w.rt.isActive())
        w.cargar_ejemplo("macroetapa")  # desde Play
        self.assertEqual((w.a_ejecutar.isChecked(), w.a_ejecutar.text(), w.modo, w.rt.isActive()),
                         (False, "Play", "editar", False))
        self.assertEqual(w.edicion.titulo, w.v.model["title"])
        with tempfile.TemporaryDirectory() as tmp:
            w.guardar_en(Path(tmp) / "macro")
            w.a_ejecutar.setChecked(True)
            self.assertTrue(w.abrir_ruta(Path(tmp) / "macro"))
            self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (False, "editar"))
            self.assertTrue(w.edicion.ed.validate().can_simulate)
            w.a_ejecutar.setChecked(True)
            self.assertEqual((w.a_ejecutar.isChecked(), w.modo, w.v.state()["status"]), (True, "simular", "pausada-estable"))
            w.a_ejecutar.setChecked(False)

    def test_SAPP19_inestable_avisa_una_vez_y_para(self):
        """REQ-SEM-07, REQ-SIM-03: si en Play el motor no alcanza una situación estable (D-LIM-EVOL), se detiene, pasa a
        Pausa/edición y aparece una sola ventana modal «El GRAFCET es inestable…» con un botón; los detalles quedan entre
        los diagnósticos. Una etapa inestable normal no avisa."""
        from PySide6.QtWidgets import QMessageBox
        w = self.w
        w.cargar_ejemplo("contador-inestable")  # la etapa 2 es inestable en cada bajada de I02 y no es un error
        w.a_ejecutar.setChecked(True)
        with mock.patch.object(type(w), "_avisar_inestable", autospec=True) as aviso:
            w._cambiar_tipo_entrada("I00", True)  # esta prueba mantiene la entrada
            w.botones["I00"].click()
            w._cambiar_tipo_entrada("I02", True)  # esta prueba mantiene la entrada
            w.botones["I02"].click()
            w._cambiar_tipo_entrada("I02", True)  # esta prueba mantiene la entrada
            w.botones["I02"].click()
            self.assertEqual((aviso.call_count, w.a_ejecutar.isChecked()), (0, True), "etapa inestable normal: sin aviso")
        w.a_ejecutar.setChecked(False)
        w.cargar_ejemplo("temporizada")
        w.a_ejecutar.setChecked(True)
        w._cambiar_tipo_entrada("marcha", True)  # esta prueba mantiene la entrada
        w.botones["marcha"].click()
        w._cambiar_tipo_entrada("fin", True)  # esta prueba mantiene la entrada
        w.botones["fin"].click()  # con marcha y fin, al vencer 3 s el ciclo no termina nunca
        w._act("avanzar", us=3_000_000)
        cuadro = w._popup_inestable
        self.assertIsNotNone(cuadro)
        self.assertEqual((w.a_ejecutar.isChecked(), w.modo, w.a_ejecutar.text()), (False, "editar", "Play"))
        self.assertEqual(cuadro.text(), "El GRAFCET es inestable: no alcanza una situación estable. Revise las transiciones.")
        self.assertEqual([b.text() for b in cuadro.buttons()], ["Aceptar"])
        self.assertTrue(cuadro.isModal())
        textos = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        self.assertTrue(any("D-LIM-EVOL" in t for t in textos), textos)
        self.assertTrue(any("franquea" in t and "t3" in t for t in textos), "qué transiciones")
        # No se repite por tic: más refrescos y tics del mismo episodio no abren otra ventana
        with mock.patch.object(type(w), "_avisar_inestable", autospec=True) as otro:
            w.refrescar_edicion()
            w.refrescar()
            w._tick()
            self.assertEqual((otro.call_count, w.a_ejecutar.isChecked()), (0, False))
        cuadro.button(QMessageBox.StandardButton.Ok).click()
        self.assertIsNone(w._popup_inestable)
        self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (False, "editar"), "al aceptar queda parado y editable")
        w.a_ejecutar.setChecked(True)  # se puede volver a ejecutar: nueva ejecución desde el principio
        self.assertEqual((w.modo, w.v.state()["status"]), ("simular", "pausada-estable"))
        w.a_ejecutar.setChecked(False)

    def test_SAPP10_temporizador_en_dibujo_y_tabla(self):
        """REQ-SIM-03: «temporizada», con E1 activa y 1 s transcurrido, muestra «1,00 s» (solo lo transcurrido) encima de la
        duración de la receptividad y «1 s / 3 s» en la tabla de temporizadores; al vencer, «3,00 s ✓»."""
        self.w.cargar_ejemplo("temporizada")
        self.w.a_ejecutar.setChecked(True)  # el dibujo del simulador es el de Play
        self.assertFalse(self.w.c_temp.isHidden())
        self.assertEqual(self.w.t_temp.rowCount(), 1)
        self.assertEqual(self.w.t_temp.item(0, 1).text(), "parado")
        self.w._cambiar_tipo_entrada("marcha", True)  # esta prueba mantiene la entrada
        self.w.botones["marcha"].click()
        self.w._act("avanzar", us=1_000_000)

        def textos():
            return [it.toPlainText() for it in self.w.diagrama.scene().items() if hasattr(it, "toPlainText")]
        self.assertIn("1,00 s", textos())
        self.assertNotIn("1 s / 3 s", textos(), "ya no se escribe lo que falta: solo el tiempo transcurrido")
        fila = [self.w.t_temp.item(0, j).text() for j in range(4)]
        self.assertEqual(fila, ["transición t2", "contando", "1 s", "3 s"])
        self.w._act("avanzar", us=2_000_000)  # vence y t2 franquea: E2, y el temporizador vuelve a parado
        self.assertEqual(self.w.v.state()["situation"], ["E2"])
        self.assertNotIn("1,00 s", textos())
        self.assertEqual(self.w.t_temp.item(0, 1).text(), "parado")
        self.w.a_ejecutar.setChecked(False)
        # Un retardo en la condición de una acción: «1,5 s» mientras cuenta y «2 s ✓» al vencer, encima de su duración
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio.diagrama import dibujar
        m = M().var("p").var("y", "output").step("A", True).step("B")
        m.trans("t", ["A"], ["B"], "p").cont("B", "y", "delay(2 s, p, 0 s)")
        v = Vista("m", "", "", lambda: (m, None), normalize_options(None))
        run(v, ("fijar", {"cambios": {"p": True}}), ("avanzar", {"us": 1_500_000}))
        sc = QGraphicsScene()
        dibujar(sc, v.model, v.state())
        self.assertIn("1,50 s", [it.toPlainText() for it in sc.items() if hasattr(it, "toPlainText")])
        self.assertEqual([t["estado"] for t in v.state()["temporal"].values()], ["contando"])
        run(v, ("avanzar", {"us": 500_000}))
        dibujar(sc, v.model, v.state())
        self.assertIn("2,00 s ✓", [it.toPlainText() for it in sc.items() if hasattr(it, "toPlainText")])
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
        w.a_ejecutar.setChecked(True)
        d.ajustar()
        base = d.escala()
        d.b_mas.click()
        d.b_mas.click()
        k = d.escala()
        self.assertGreater(k, base * 1.3)
        self.assertEqual(d.l_zoom.text(), f"{round(k * 100)} %")
        w._cambiar_tipo_entrada("I00", True)  # esta prueba mantiene la entrada
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
        w.a_ejecutar.setChecked(False)

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
        w.a_ejecutar.setChecked(True)
        self.assertEqual(list(w.botones), [marcha])
        self.assertEqual(w.botones[marcha].text(), "marcha = 0")
        w._cambiar_tipo_entrada(marcha, True)  # esta prueba mantiene la entrada
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
        w.a_ejecutar.setChecked(False)

    def test_SAPP20_play_con_lecturas_que_no_compilan_avisa_y_queda_en_pausa(self):
        """REQ-SIM-03, REQ-JER-04: si el modelo compila con las lecturas por defecto pero no con las activas (7.7 = B con una
        etapa inicial dentro de una expansión), Play avisa con los diagnósticos, no lanza excepción y queda en Pausa."""
        from grafcet.examples import ej_macroetapa
        w = self.w
        m, layout = ej_macroetapa()
        next(s for s in m.doc["steps"] if s["id"] == "K")["initial"] = True  # etapa inicial dentro de la expansión
        w.fuente = {"tipo": "fichero", "ruta": Path(self.tmp.name) / "macro.json", "doc": m.doc, "layout": layout,
                    "titulo": "Macro", "ayuda": "", "raiz": None}
        try:
            w._cargar()
            w._opciones({"7.7": "B"})
            self.assertIsNone(w.v.s, "con 7.7 = B no compila")
            with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
                w.a_ejecutar.setChecked(True)
            self.assertEqual(aviso.call_count, 1)
            self.assertIn("lecturas", aviso.call_args.args[2])
            self.assertIn("7.7", aviso.call_args.args[2])
            self.assertEqual((w.a_ejecutar.isChecked(), w.modo, w.a_ejecutar.text()), (False, "editar", "Play"))
            w._opciones({})  # lecturas por defecto: se puede ejecutar
            w.a_ejecutar.setChecked(True)
            self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (True, "simular"))
        finally:
            w.a_ejecutar.setChecked(False)
            w._opciones({})

    def test_SAPP13_tiempos_truncados_a_dos_decimales(self):
        """REQ-SIM-03: lo que lleva un temporizador y τ se muestran truncados a la baja a 2 decimales; el preset, tal cual."""
        w = self.w
        w.cargar_ejemplo("temporizada")
        w.a_ejecutar.setChecked(True)
        w._cambiar_tipo_entrada("marcha", True)  # esta prueba mantiene la entrada
        w.botones["marcha"].click()
        w._act("avanzar", us=1_239_999)
        self.assertEqual(w.v.state()["time"], "1,239999 s", "el estado exacto no se toca")
        self.assertEqual(w.t_temp.item(0, 2).text(), "1,23 s")
        self.assertEqual(w.l_reloj.text().split(" · ")[0], "τ = 1,23 s")
        w._act("avanzar", us=1)
        self.assertEqual((w.t_temp.item(0, 2).text(), w.l_reloj.text().split(" · ")[0]), ("1,24 s", "τ = 1,24 s"))
        self.assertEqual(w.t_temp.item(0, 3).text(), "3 s")
        self.assertEqual(w.a_ejecutar.text(), "Stop")
        self.assertFalse(w.a_ejecutar.icon().isNull(), "el símbolo se muestra ahora como icono de la barra")
        w.a_ejecutar.setChecked(False)
        self.assertEqual(w.a_ejecutar.text(), "Play")
        self.assertFalse(w.a_ejecutar.icon().isNull())


if __name__ == "__main__":
    unittest.main()
