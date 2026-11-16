"""SIDI: los botones estándar de Qt salen en español y nunca en blanco (P-IMP-158; un «OK» o un «Sí» vacíos dejaban
diálogos sin respuesta afirmativa)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QInputDialog, QMessageBox, QPushButton
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class Idioma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from escritorio import idioma
        idioma.instalar()

    def textos(self, w):
        w.show()
        QApplication.processEvents()
        out = [b.text() for b in w.findChildren(QPushButton)]
        w.close()
        return out

    def test_SIDI01_dialogo_de_texto_con_aceptar_y_cancelar(self):
        d = QInputDialog()
        d.setLabelText("Nombre del recinto")
        self.assertEqual(sorted(self.textos(d)), ["Aceptar", "Cancelar"])

    def test_SIDI02_confirmacion_si_no_y_guardado(self):
        m = QMessageBox()
        b = QMessageBox.StandardButton
        m.setStandardButtons(b.Yes | b.No | b.Save | b.Discard | b.Cancel | b.Close)
        self.assertEqual(sorted(self.textos(m)), sorted(["Sí", "No", "Guardar", "Descartar", "Cancelar", "Cerrar"]))

    def test_SIDI03_ningun_boton_estandar_queda_en_blanco(self):
        b = QDialogButtonBox.StandardButton
        todos = [x for x in b if x not in (b.NoButton,)]
        caja = QDialogButtonBox()
        for x in todos:
            try:
                caja.addButton(x)
            except (TypeError, ValueError):
                pass
        vacios = [caja.standardButton(btn) for btn in caja.buttons() if not btn.text().strip()]
        self.assertEqual(vacios, [], "ningún botón estándar sin texto")


if __name__ == "__main__":
    unittest.main()
