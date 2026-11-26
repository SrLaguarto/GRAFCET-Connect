"""Etiqueta de transición repetida escrita a mano: se avisa solo al pulsar Play y el aviso nombra cada transición por su etapa."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(1, str(ROOT / "tests"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from grafcet.builder import M
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtWidgets import QApplication
    from grafcet.editor import Editor


def _bombear(n: int = 5) -> None:
    for _ in range(n):
        QApplication.instance().processEvents()


def _editor(pasos: list[str], trans: list[tuple[str, list[str], list[str]]], etiqueta: str = "t25", *repetidas: str) -> Editor:
    """Un grafcet con las etapas y transiciones dadas; las transiciones de `repetidas` llevan la etiqueta escrita a mano."""
    m = M().var("a").step(pasos[0], True)
    for p in pasos[1:]:
        m = m.step(p)
    for tid, pre, post in trans:
        m = m.trans(tid, pre, post, "a")
    for t in m.doc["transitions"]:
        if t["id"] in repetidas:
            t["label"] = etiqueta
    return Editor(m.doc)


@unittest.skipUnless(QT, "requiere PySide6")
class EtiquetasRepetidasQt(BaseQt):
    def setUp(self):
        self._docs = tempfile.TemporaryDirectory()
        self.addCleanup(self._docs.cleanup)
        p = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=self._docs.name)
        p.start()
        self.addCleanup(p.stop)
        super().setUp()
        self.addCleanup(self.w.hide)

    def mensajes(self, ed: Editor) -> list[str]:
        w, e = self.vacio()
        e.ed = ed
        e.cambia()
        return [d["message"] for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"]

    def test_SETR01_dos_transiciones_tras_x11_y_x34(self):
        """Dos transiciones con la misma etiqueta: «Transición t25 repetida tras X11 y tras X34.»"""
        ed = _editor(["11", "12", "34", "35"], [("ta", ["11"], ["12"]), ("tb", ["34"], ["35"])], "t25", "ta", "tb")
        self.assertEqual(self.mensajes(ed), ["Transición t25 repetida tras X11 y tras X34."])

    def test_SETR02_tres_transiciones_coma_y_y(self):
        """Tres transiciones repetidas: «tras X11, tras X34 y tras X40»."""
        ed = _editor(["11", "12", "34", "35", "40", "41"],
                     [("ta", ["11"], ["12"]), ("tb", ["34"], ["35"]), ("tc", ["40"], ["41"])], "t25", "ta", "tb", "tc")
        self.assertEqual(self.mensajes(ed), ["Transición t25 repetida tras X11, tras X34 y tras X40."])

    def test_SETR03_convergencia_en_y(self):
        """Una transición con dos etapas anteriores va como un solo elemento y fuerza la coma antes de «y tras»."""
        ed = _editor(["11", "12", "13", "34", "35"],
                     [("ta", ["11", "12"], ["13"]), ("tb", ["34"], ["35"])], "t25", "ta", "tb")
        self.assertEqual(self.mensajes(ed), ["Transición t25 repetida tras X11 y X12, y tras X34."])

    def test_SETR04_transicion_fuente(self):
        """Una transición sin etapas anteriores se nombra «en una transición fuente»."""
        ed = _editor(["11", "12", "13"], [("ta", ["11"], ["12"]), ("tb", [], ["13"])], "t25", "ta", "tb")
        self.assertEqual(self.mensajes(ed), ["Transición t25 repetida tras X11 y en una transición fuente."])

    def test_SETR05_editar_sin_ruido(self):
        """Escribir una etiqueta repetida no da mensaje de error, ni parpadeo, ni marcas con «Mostrar errores» desmarcado."""
        w, e = self.vacio()
        e.ed = _editor(["11", "12", "34", "35"], [("ta", ["11"], ["12"]), ("tb", ["34"], ["35"])], "t25", "ta")
        e.cambia()
        w.b_errores.setChecked(False)
        self.assertIsNone(e.renombrar("tb", "t25"))
        w.refrescar_edicion()
        _bombear()
        self.assertEqual(e.parpadeo.activos(), set())
        self.assertFalse(e.parpadeo.t.isActive())
        texto, info = e.texto_estado()
        self.assertTrue(info or not texto)
        self.assertEqual(w._marcas_diagnostico, set())
        self.assertEqual(len(self.mensajes_de(e)), 1)  # el diagnóstico existe, solo que no se enseña

    def mensajes_de(self, e) -> list[str]:
        return [d["message"] for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"]

    def test_SETR06_play_no_arranca_y_el_aviso_trae_el_texto_nuevo(self):
        """Play con etiquetas repetidas no simula y el aviso dice «Transición t25 repetida tras X11 y tras X34.»"""
        w, e = self.vacio()
        e.ed = _editor(["11", "12", "34", "35"], [("ta", ["11"], ["12"]), ("tb", ["34"], ["35"])], "t25", "ta", "tb")
        e.cambia()
        w.refrescar_edicion()
        with mock.patch("escritorio.ventana.simulacion.QMessageBox.warning") as aviso:
            self.assertFalse(w._preparar_sesion())
        _bombear()
        self.assertTrue(aviso.called)
        self.assertIn("• Transición t25 repetida tras X11 y tras X34.", aviso.call_args.args[2])
        self.assertIsNone(w.v)

    def test_SETR07_vaciar_la_etiqueta_quita_el_aviso(self):
        """Vaciar la etiqueta de una transición la devuelve a automática y el aviso desaparece."""
        w, e = self.vacio()
        e.ed = _editor(["11", "12", "34", "35"], [("ta", ["11"], ["12"]), ("tb", ["34"], ["35"])], "t25", "ta", "tb")
        e.cambia()
        self.assertEqual(len(self.mensajes_de(e)), 1)
        self.assertIsNone(e.renombrar("tb", ""))
        self.assertEqual(self.mensajes_de(e), [])
        self.assertTrue(e.ed.validate().can_simulate)


if __name__ == "__main__":
    unittest.main()
