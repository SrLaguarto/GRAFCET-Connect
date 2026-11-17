"""Los callbacks diferidos se cancelan al destruir su control, sin excepciones ocultas por Qt."""
from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtWidgets import QAbstractItemView, QApplication, QStyleOptionViewItem, QTableWidgetItem
    from shiboken6 import delete, isValid
    from escritorio.diagrama import SelectorAccion
    from escritorio.variables import PanelVariables
    from tools import hoja_contactos as HC
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class CallbacksQt(unittest.TestCase):
    def setUp(self):
        self.app = HC.aplicacion()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        HC._bombear(2)
        self.errores = []
        self.objetos = []
        self.salida = io.StringIO()
        self.redireccion = redirect_stderr(self.salida)
        self.redireccion.__enter__()
        self.hook = sys.excepthook
        sys.excepthook = lambda tipo, valor, pila: self.errores.append((tipo.__name__, str(valor)))

    def tearDown(self):
        try:
            for objeto in self.objetos:
                if isValid(objeto):
                    delete(objeto)
            HC._bombear(4)
        finally:
            sys.excepthook = self.hook
            self.redireccion.__exit__(None, None, None)
        self.assertEqual(self.errores, [])
        self.assertNotIn("RuntimeError", self.salida.getvalue())

    def panel(self):
        panel = PanelVariables()
        self.objetos.append(panel)
        return panel

    def test_SCB1_tabla_destruida_cancela_la_reconstruccion(self):
        panel = self.panel()
        panel.e = object()
        with patch.object(panel.tabla, "state", return_value=QAbstractItemView.State.EditingState):
            panel._diferir(panel._reconstruir)
        delete(panel.tabla)
        HC._bombear(3)

    def test_SCB2_panel_destruido_cancela_la_fila_rechazada(self):
        panel = self.panel()
        fila = {"blanca": True}
        panel._filas = [fila]
        panel.tabla.setRowCount(1)
        panel.tabla.setItem(0, 0, QTableWidgetItem("rechazado"))
        with patch.object(panel.tabla, "state", return_value=QAbstractItemView.State.EditingState):
            panel._diferir(lambda: panel._en_blanco(fila))
        delete(panel)
        HC._bombear(3)

    def test_SCB3_control_vivo_sigue_ejecutando_el_cambio(self):
        panel = self.panel()
        cambios = []
        with patch.object(panel.tabla, "state", return_value=QAbstractItemView.State.EditingState):
            panel._diferir(lambda: cambios.append("diferido"))
        self.assertEqual(cambios, [])
        HC._bombear(3)
        self.assertEqual(cambios, ["diferido"])

    def test_SCB4_selector_eliminado_cancela_sus_senales_pendientes(self):
        for razon in (None, Qt.FocusReason.TabFocusReason, Qt.FocusReason.OtherFocusReason):
            with self.subTest(razon=razon):
                selector = SelectorAccion()
                if razon is None:
                    selector.hidePopup()
                else:
                    evento = QFocusEvent(QEvent.Type.FocusOut, razon)
                    QApplication.sendEvent(selector, evento)
                delete(selector)
                HC._bombear(3)

    def test_SCB5_selector_vivo_sigue_avisando_del_cierre(self):
        selector = SelectorAccion()
        self.objetos.append(selector)
        cierres = []
        selector.cerrado.connect(lambda: cierres.append(True))
        selector.hidePopup()
        self.assertEqual(cierres, [])
        HC._bombear(3)
        self.assertEqual(cierres, [True])

    def combo(self, panel):
        panel._filas = [panel._fila_nueva(blanca=True)]
        panel.tabla.setRowCount(1)
        indice = panel.tabla.model().index(0, 1)
        delegado = panel.tabla.itemDelegate()
        combo = delegado.createEditor(panel.tabla.viewport(), QStyleOptionViewItem(), indice)
        return delegado, combo

    def test_SCB6_editor_eliminado_no_abre_lista_ni_emite_cierre_tardio(self):
        panel = self.panel()
        cierres = []
        with patch.object(panel, "elegir"):
            delegado, combo = self.combo(panel)
            delegado.closeEditor.connect(lambda *args: cierres.append(True))
            combo.activated.emit(0)
        delete(combo)
        HC._bombear(3)
        self.assertEqual(cierres, [])

    def test_SCB7_editor_vivo_confirma_y_cierra_como_antes(self):
        panel = self.panel()
        cierres = []
        with patch.object(panel, "elegir") as elegir:
            delegado, combo = self.combo(panel)
            delegado.closeEditor.connect(lambda *args: cierres.append(True))
            combo.activated.emit(0)
            elegir.assert_called_once()
        HC._bombear(3)
        self.assertEqual(cierres, [True])


if __name__ == "__main__":
    unittest.main()
