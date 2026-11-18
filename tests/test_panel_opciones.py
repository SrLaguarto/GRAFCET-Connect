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

    def test_SPOP01_sin_ajuste_solo_propiedades_flotantes(self):
        """REQ-EDT-02: solo hay un panel de propiedades, alojado por el gestor flotante."""
        w = self.ventana()
        self.assertIs(w.props, w.flot.panel)
        self.assertEqual(w.inferior.count(), 1)

    def test_SPOP02_ajuste_antiguo_no_reintroduce_abajo(self):
        """REQ-EDT-02: los ajustes antiguos se ignoran sin migraciones ni avisos."""
        for valor in ("abajo", "flotante", "desconocido"):
            w = self.ventana(valor)
            self.assertIs(w.props, w.flot.panel)
            self.assertFalse(w.flot.abierto)
            self.assertEqual(w.ajustes.value("paneles/propiedades"), valor)

    def test_SPOP03_sin_submenu_de_modo_en_ver(self):
        """REQ-EDT-02: Ver no ofrece el selector de modos retirado."""
        w = self.ventana()
        ver = next(a.menu() for a in w.menuBar().actions() if a.text().replace("&", "") == "Ver")
        self.assertFalse(any("Panel de opciones" in a.text().replace("&", "") for a in ver.actions()))

    def test_SPOP04_sin_fijar_y_con_traza(self):
        """REQ-EDT-02, REQ-SIM-03: se retira Fijar y se conserva el contenido de traza."""
        from PySide6.QtWidgets import QToolButton
        w = self.ventana()
        self.assertFalse(any(b.text() == "Fijar" for b in w.findChildren(QToolButton)))
        self.assertTrue(w.inferior.isAncestorOf(w.traza))


if __name__ == "__main__":
    unittest.main()
