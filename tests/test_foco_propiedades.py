"""SFOC: resaltar la parte editada al mover el foco en Propiedades (barra inferior) no falla con una transición."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from tools import hoja_contactos as HC
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class FocoPropiedades(unittest.TestCase):
    def test_SFOC01_foco_en_los_bloques_de_una_transicion(self):
        """Con la barra abajo y una transición elegida, poner el foco en sus bloques no lanza IndexError (la transición no tiene
        «condición» ni «evento»: no hay parte que resaltar)."""
        HC.aplicacion()
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        HC._edicion(c)
        w = c.w
        w._cambiar_modo_propiedades("abajo")
        c.e.seleccionar([c.ids["transiciones"][0]])
        w._abrir_opciones()
        HC._bombear(6)
        self.assertEqual(w.props.objetivo_bloques()[0], "transicion")
        antes = c.e.parte_editada
        w._foco_propiedades(None, w.props.prog)  # (antes: IndexError en objetivo[2])
        self.assertEqual(c.e.parte_editada, antes)


if __name__ == "__main__":
    unittest.main()
