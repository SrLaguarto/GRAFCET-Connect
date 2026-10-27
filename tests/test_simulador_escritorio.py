"""Simulador de escritorio (P-IMP-29): abrir y guardar modelos, colocación automática, entradas numéricas y la
ventana Qt sin pantalla.

Las pruebas del núcleo (S-APP01..04) no necesitan Qt. Las de la ventana (S-APP05..07) se omiten si PySide6 no
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


@unittest.skipUnless(QT, "PySide6 no está instalado")
class Ventana(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from escritorio.ventana import Ventana as V
        cls.w = V()

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
        self.assertIn("distintas de las decididas", self.w.l_lect.text())
        self.w.botones["p"].click()
        self.assertEqual(self.w.v.state()["situation"], ["C"], "con «recorrido» la subida llega a C")
        self.w._opciones(normalize_options(None))
        self.assertIn("decididas por el responsable", self.w.l_lect.text())


if __name__ == "__main__":
    unittest.main()
