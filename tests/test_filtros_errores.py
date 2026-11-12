"""Filtros de eventos de la aplicación (solo QWidget), filtro de la elección de E/S solo mientras hace falta y aviso de errores sin reentrada."""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.entradas_salidas import PanelES
    from escritorio import errores
    from escritorio.laminas import VistaLamina
    QT = True
except ImportError:
    QT = False

from grafcet.builder import M


def raton(tipo=QEvent.Type.MouseButtonPress):
    p = QPointF(5, 5)
    return QMouseEvent(tipo, p, p, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


@unittest.skipUnless(QT, "Falta PySide6")
class FiltrosYErrores(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.fallos = []
        self.hook = sys.excepthook
        sys.excepthook = lambda t, v, r: self.fallos.append(v)

    def tearDown(self):
        sys.excepthook = self.hook

    def panel(self):
        p = PanelES()
        p.cargar(M().var("a").var("q", "output").step("0", True).doc)
        p.resize(1200, 700)
        p.show()
        self.app.processEvents()
        self.addCleanup(lambda: (p.cancelar_eleccion(), p.close(), p.deleteLater()))
        return p

    def test_SFLT01_un_evento_de_raton_en_un_qwindow_con_eleccion_pendiente_no_falla(self):
        """REQ-SIM-03: el filtro de la elección solo trata widgets; un clic recibido por un QWindow no lanza ninguna excepción."""
        p = self.panel()
        p._clic_variable("a")
        self.assertEqual(p.eleccion(), ("variable", "a"))
        self.assertIsNotNone(p.windowHandle())
        self.app.sendEvent(p.windowHandle(), raton())
        self.assertEqual(self.fallos, [])

    def test_SFLT02_arrastre_en_la_vista_con_eleccion_pendiente_no_falla(self):
        """REQ-SIM-03: arrastrar una variable con una elección pendiente no provoca errores en el filtro."""
        p = self.panel()
        p._clic_variable("a")
        lista = p.lista_entradas
        QTest.mousePress(lista.viewport(), Qt.MouseButton.LeftButton, pos=lista.visualItemRect(lista.item(0)).center())
        QTest.mouseMove(lista.viewport(), lista.visualItemRect(lista.item(0)).center() + __import__("PySide6.QtCore").QtCore.QPoint(60, 10))
        QTest.mouseRelease(lista.viewport(), Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.fallos, [])

    def test_SFLT03_el_filtro_solo_esta_con_eleccion_pendiente_y_la_vista_visible(self):
        """REQ-SIM-03: el filtro de la aplicación se quita al cancelar y al ocultarse la vista, y vuelve al mostrarse con la elección."""
        p = self.panel()
        self.assertFalse(p._filtro_puesto)
        p._clic_variable("a")
        self.assertTrue(p._filtro_puesto)
        p.hide()
        self.assertFalse(p._filtro_puesto)
        p.show()
        self.assertTrue(p._filtro_puesto)
        p.cancelar_eleccion()
        self.assertFalse(p._filtro_puesto)
        p.hide()
        p._eleccion = ("variable", "a")
        p._vigilar_eleccion()
        self.assertFalse(p._filtro_puesto)  # (oculta: no se instala)
        p._eleccion = None

    def test_SFLT04_el_aviso_de_error_no_reentra_y_resume_el_texto(self):
        """REQ-EDT-09: un error durante el aviso no abre otro diálogo; el texto es la última línea, acortada."""
        llamadas = []

        def aviso(*a):
            llamadas.append(a[2])
            try:
                raise ValueError("otro")
            except ValueError:
                errores._avisar(*sys.exc_info())  # un segundo error mientras se muestra el primero

        with mock.patch.object(errores.QMessageBox, "warning", side_effect=aviso), mock.patch.object(errores, "_guardar", return_value=None), \
                mock.patch.object(sys, "stderr", None):
            errores._avisar(ValueError, ValueError("primera\n" + "x" * 500), None)
            errores._avisar(ValueError, ValueError("a"), None)
        self.assertEqual(len(llamadas), 2)  # el segundo error mostrado durante el primero no abrió otro
        self.assertLess(len(llamadas[0]), 420)
        self.assertNotIn("primera", llamadas[0])

    def test_SFLT05_punto_hoja_sin_documento_no_falla(self):
        """REQ-EDT-11: la vista de la hoja sin documento (cambio de hoja, hoja no válida) responde a ratón y a punto_hoja sin error."""
        v = VistaLamina()
        v.resize(300, 200)
        self.assertIsNone(v.documento)
        v.punto_hoja(QPointF(3, 4))
        v.inicio_texto = (QPointF(), 0, 0)
        for tipo in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease):
            self.app.sendEvent(v, raton(tipo))
        self.assertEqual(self.fallos, [])
        self.assertIsNone(v.inicio_texto)
