"""Panel de opciones: flotante por defecto y submenú excluyente en Ver. REQ-EDT-02."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QActionGroup
    from tools import hoja_contactos as HC
    QT = True
except ImportError:  # sin PySide6
    QT = False


@unittest.skipUnless(QT, "Falta PySide6")
class PanelOpciones(unittest.TestCase):
    def setUp(self):
        HC.aplicacion()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = str(Path(self.tmp.name) / "a.ini")

    def ventana(self, guardado=None):
        from escritorio.ventana import Ventana
        ajustes = QSettings(self.ruta, QSettings.Format.IniFormat)
        if guardado is not None:
            ajustes.setValue("paneles/propiedades", guardado)
            ajustes.sync()
        w = Ventana(QSettings(self.ruta, QSettings.Format.IniFormat))
        self.addCleanup(self._cerrar, w)
        return w

    @staticmethod
    def _cerrar(w):
        w.edicion = None
        w.hide()
        w.deleteLater()

    def test_SPOP01_sin_ajuste_arranca_flotante(self):
        """REQ-EDT-02: una instalación nueva, sin valor guardado, arranca con el panel de opciones flotante."""
        w = self.ventana()
        self.assertEqual(w.modo_propiedades, "flotante")
        self.assertTrue(w.a_props["flotante"].isChecked() and not w.a_props["abajo"].isChecked())

    def test_SPOP02_valores_guardados_se_respetan(self):
        """REQ-EDT-02: «abajo» y «flotante» guardados se respetan; un valor desconocido se trata como «flotante»."""
        for guardado, esperado in (("abajo", "abajo"), ("flotante", "flotante"), ("otro", "flotante"), ("", "flotante")):
            with self.subTest(guardado=guardado):
                w = self.ventana(guardado)
                self.assertEqual(w.modo_propiedades, esperado)
                self.assertTrue(w.a_props[esperado].isChecked())

    def test_SPOP03_submenu_panel_de_opciones_en_ver(self):
        """REQ-EDT-02: Ver tiene «Panel de opciones» con «Flotante» y «Abajo», en ese orden, como grupo exclusivo con una sola marcada."""
        w = self.ventana()
        ver = next(a.menu() for a in w.menuBar().actions() if a.text().replace("&", "") == "Ver")
        sub = next(a.menu() for a in ver.actions() if a.menu() is not None and a.text().replace("&", "") == "Panel de opciones")
        self.assertEqual([a.text().replace("&", "") for a in sub.actions()], ["Flotante", "Abajo"])
        self.assertFalse([a for a in ver.actions() if "Propiedades:" in a.text()], "las entradas antiguas ya no están")
        grupo = sub.actions()[0].actionGroup()
        self.assertIsInstance(grupo, QActionGroup)
        self.assertTrue(grupo.isExclusive())
        self.assertTrue(all(a.isCheckable() and a.actionGroup() is grupo for a in sub.actions()))
        marcadas = [a for a in sub.actions() if a.isChecked()]
        self.assertEqual(len(marcadas), 1)
        self.assertEqual(marcadas[0], w.a_props[w.modo_propiedades])

    def test_SPOP04_marcar_abajo_cambia_desmarca_y_guarda(self):
        """REQ-EDT-02: marcar «Abajo» cambia el modo, desmarca «Flotante» y lo guarda; volver a pulsar la marcada no la desmarca."""
        w = self.ventana()
        w.a_props["abajo"].trigger()
        self.assertEqual(w.modo_propiedades, "abajo")
        self.assertTrue(w.a_props["abajo"].isChecked() and not w.a_props["flotante"].isChecked())
        self.assertEqual(w.ajustes.value("paneles/propiedades"), "abajo")
        w.a_props["abajo"].trigger()  # la marcada: sigue marcada
        self.assertTrue(w.a_props["abajo"].isChecked() and not w.a_props["flotante"].isChecked())
        self.assertEqual(w.modo_propiedades, "abajo")
        w.a_props["flotante"].trigger()
        self.assertEqual(w.modo_propiedades, "flotante")
        self.assertTrue(w.a_props["flotante"].isChecked() and not w.a_props["abajo"].isChecked())
        self.assertEqual(w.ajustes.value("paneles/propiedades"), "flotante")


if __name__ == "__main__":
    unittest.main()
