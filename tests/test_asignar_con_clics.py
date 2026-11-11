"""Vista de E/S: asignar con dos clics (variable y canal, o canal y variable), además de arrastrar."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.entradas_salidas import PanelES
    QT = True
except ImportError:
    QT = False

from grafcet.builder import M


@unittest.skipUnless(QT, "Falta PySide6")
class AsignarConClics(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.p = PanelES()
        self.p.cargar(M().var("a").var("b").var("q", "output").step("0", True).doc)
        self.p.resize(1200, 700)
        self.p.show()
        self.p.activateWindow()
        self.app.processEvents()
        self.cambios = []
        self.p.aplicar.connect(self.cambios.append)

    def tearDown(self):
        self.p.cancelar_eleccion()
        self.p.close()
        self.p.deleteLater()
        self.app.processEvents()

    def asignadas(self):
        return [(s.variable, s.area, s.direccion) for s in self.p.obtener().senales]

    def clic_variable(self, lista, indice):
        QTest.mouseClick(lista.viewport(), Qt.MouseButton.LeftButton, pos=lista.visualItemRect(lista.item(indice)).center())
        self.app.processEvents()

    def clic_canal(self, area, direccion):
        t = self.p.terminales[(area, direccion)]
        QTest.mouseClick(t, Qt.MouseButton.LeftButton, pos=t.zona_asignacion().center())
        self.app.processEvents()

    def esc(self):
        for tipo in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            self.app.sendEvent(self.p, QKeyEvent(tipo, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        self.app.processEvents()

    def test_SFIO80_clic_en_la_variable_y_en_el_canal_la_asigna_como_al_soltarla(self):
        """REQ-SIM-03: un clic en una variable la deja elegida (resaltada) y un clic en un canal compatible la asigna; en el orden
        inverso (canal y luego variable) también; con una asignada, el canal se sustituye como al soltar encima."""
        p = self.p
        self.clic_variable(p.lista_entradas, 0)
        self.assertEqual(p.eleccion(), ("variable", "a"))
        self.assertTrue(p.lista_entradas.item(0).isSelected(), "la variable elegida queda resaltada")
        self.clic_canal("discrete", 3)
        self.assertEqual(self.asignadas(), [("a", "discrete", 3)])
        self.assertIsNone(p.eleccion())
        self.assertEqual(len(self.cambios), 1, "una sola aplicación (un solo paso de deshacer), como al soltar")
        # canal y luego variable
        self.clic_canal("discrete", 5)
        self.assertEqual(p.eleccion(), ("canal", "discrete", 5))
        self.assertTrue(p.terminales[("discrete", 5)]._elegido)
        self.clic_variable(p.lista_entradas, 1)
        self.assertEqual(sorted(self.asignadas()), [("a", "discrete", 3), ("b", "discrete", 5)])
        self.assertIsNone(p.eleccion())
        self.assertFalse(any(t._elegido for t in p.terminales.values()))
        self.assertEqual(len(self.cambios), 2)
        # sobre un canal ocupado: sustituye (como el arrastre)
        self.clic_variable(p.lista_entradas, 0)
        self.clic_canal("discrete", 5)
        self.assertEqual(self.asignadas(), [("a", "discrete", 5)])

    def test_SFIO81_las_mismas_reglas_de_compatibilidad_que_el_arrastre(self):
        """REQ-SIM-03: una entrada no se asigna a una bobina ni una salida a un canal discreto de entrada; con un canal
        incompatible no pasa nada y la variable sigue elegida; en el orden inverso, la variable incompatible pasa a ser la elegida."""
        p = self.p
        self.clic_variable(p.lista_entradas, 0)
        self.clic_canal("coil", 0)
        self.assertEqual(self.asignadas(), [])
        self.assertEqual(p.eleccion(), ("variable", "a"), "sigue elegida")
        self.clic_canal("discrete", 0)
        self.assertEqual(self.asignadas(), [("a", "discrete", 0)])
        self.clic_canal("coil", 1)
        self.assertEqual(p.eleccion(), ("canal", "coil", 1))
        self.clic_variable(p.lista_entradas, 1)  # una entrada no encaja en una bobina
        self.assertEqual(self.asignadas(), [("a", "discrete", 0)])
        self.assertEqual(p.eleccion(), ("variable", "b"))
        self.assertFalse(any(t._elegido for t in p.terminales.values()))
        self.clic_canal("coil", 1)
        self.assertEqual(p.eleccion(), ("variable", "b"))
        self.assertEqual(self.asignadas(), [("a", "discrete", 0)])
        p.cancelar_eleccion()
        self.clic_variable(p.lista_salidas, 0)
        self.clic_canal("coil", 1)
        self.assertEqual(self.asignadas(), [("a", "discrete", 0), ("q", "coil", 1)])

    def test_SFIO82_esc_o_un_clic_en_vacio_cancelan_y_un_segundo_clic_en_el_canal_lo_suelta(self):
        """REQ-SIM-03: Esc o un clic fuera de las variables y los canales cancelan la elección sin asignar nada; con el
        canal elegido, otro clic en él lo deja sin elegir; con la conexión viva (bloqueado) los clics no eligen nada."""
        p = self.p
        self.clic_variable(p.lista_entradas, 0)
        self.esc()
        self.assertIsNone(p.eleccion())
        self.assertFalse(p.lista_entradas.item(0).isSelected())
        self.assertEqual(self.asignadas(), [])
        self.clic_canal("discrete", 2)
        QTest.mouseClick(p.resumen, Qt.MouseButton.LeftButton)  # un clic en vacío
        self.app.processEvents()
        self.assertIsNone(p.eleccion())
        self.assertFalse(any(t._elegido for t in p.terminales.values()))
        self.clic_canal("discrete", 2)
        self.clic_canal("discrete", 2)
        self.assertIsNone(p.eleccion())
        self.clic_variable(p.lista_entradas, 0)
        self.clic_canal("discrete", 4)  # y la elección sigue funcionando tras cancelar
        self.assertEqual(self.asignadas(), [("a", "discrete", 4)])
        p.bloqueado = True
        self.clic_variable(p.lista_entradas, 1)
        self.assertIsNone(p.eleccion())
        self.clic_canal("discrete", 6)
        self.assertEqual(self.asignadas(), [("a", "discrete", 4)])
        p.bloqueado = False

    def test_SFIO84_esc_solo_cancela_si_la_ventana_es_la_activa_y_no_hay_menu_ni_dialogo(self):
        """REQ-SIM-03: con un menú o un diálogo modal encima, o con otra ventana activa, Esc no cancela la elección (es de ellos)."""
        from unittest import mock
        p = self.p
        self.clic_variable(p.lista_entradas, 0)
        for objeto, valor in (("activePopupWidget", object()), ("activeModalWidget", object()), ("activeWindow", None)):
            with mock.patch.object(QApplication, objeto, return_value=valor):
                self.esc()
            self.assertEqual(p.eleccion(), ("variable", "a"), objeto)
        self.esc()
        self.assertIsNone(p.eleccion(), "y sin nada encima, Esc cancela")

    def test_SFIO83_la_eleccion_sobrevive_a_rehacer_las_listas(self):
        """REQ-SIM-03: al rehacerse las listas y los canales (cargar, actualizar) la variable elegida sigue marcada, y el canal
        elegido, también; si la variable desaparece, la elección se cancela."""
        p = self.p
        self.clic_variable(p.lista_entradas, 1)
        p._dibujar()
        self.app.processEvents()
        self.assertEqual(p.eleccion(), ("variable", "b"))
        self.assertTrue(p.lista_entradas.item(1).isSelected())
        p.cancelar_eleccion()
        self.clic_canal("coil", 2)
        p._dibujar()
        self.app.processEvents()
        self.assertTrue(p.terminales[("coil", 2)]._elegido)


if __name__ == "__main__":
    unittest.main()
