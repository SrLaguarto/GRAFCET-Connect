"""SLVA: la lista de variables de la acción en Propiedades, con el tipo en corto y sin recortes (decisión del responsable, 13-nov-2026)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

if QT:
    from escritorio.acciones import _ComboVariable, opciones_variable


@unittest.skipUnless(QT, "requiere PySide6")
class ListaVariableAccion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SLVA01_tipo_en_corto(self):
        v = {"luz": ("output", "bool"), "nivel": ("output", "int"), "aux": ("internal", "bool"), "cuenta": ("internal", "decimal")}
        textos = {dato: t.strip() for t, dato, _ in opciones_variable(v, list(v), "") if dato}
        self.assertEqual(textos, {"luz": "luz  (Bool)", "nivel": "nivel  (Ent)", "aux": "aux  (Bool)", "cuenta": "cuenta  (Dec)"})

    def test_SLVA02_la_lista_crece_hasta_la_opcion_mas_larga(self):
        c = _ComboVariable()
        for texto in ("Elija la variable…", "Salidas", "   una salida de nombre bastante largo", "   y"):
            c.addItem(texto, texto.strip())
        c.resize(90, 62)
        fm = c.view().fontMetrics()
        largo = max(fm.horizontalAdvance(c.itemText(i)) for i in range(c.count()))
        self.assertGreater(c.ancho_lista(), largo, "cabe la opción más larga, con su margen")
        c.resize(900, 62)
        self.assertEqual(c.ancho_lista(), 900, "si caben, la lista mide lo que el desplegable")


if __name__ == "__main__":
    unittest.main()
