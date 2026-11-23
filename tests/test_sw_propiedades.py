"""SW: ventana de Propiedades (REQ-EDT-02, REQ-EDT-09)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QStyle, QStyleOptionButton
    from tools import hoja_contactos as HC
    from escritorio import estilo
    from test_auditoria_maquetacion import regla_C6
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class PropiedadesW(unittest.TestCase):
    def contexto(self, tipo="transicion", ancho=1366, alto=768):
        HC.aplicacion()
        c = HC.Contexto(ancho, alto)
        self.addCleanup(c.cerrar)
        HC._flotante(tipo)(c)
        return c, c.w.flot.panel, c.w.flot.principal

    def arrastrar(self, v, desplazamiento):
        origen = QPoint(v.cabecera.width() // 2, v.cabecera.height() // 2)
        QTest.mousePress(v.cabecera, Qt.MouseButton.LeftButton, pos=origen)
        QTest.mouseMove(v.cabecera, origen + desplazamiento)
        QTest.mouseRelease(v.cabecera, Qt.MouseButton.LeftButton, pos=origen)
        HC._bombear(3)

    def comprobar_limites(self, c, v):
        area = c.w.rect().adjusted(estilo.E1, estilo.E1, -estilo.E1, -estilo.E1)
        barra = v.cabecera.geometry().translated(v.pos() - c.w.mapToGlobal(QPoint()))
        self.assertGreaterEqual(barra.top(), area.top())
        self.assertLessEqual(barra.bottom(), area.bottom())
        self.assertGreaterEqual(barra.intersected(area).width(), min(120, barra.width() // 3))

    def test_SW1_indicador_entero_y_alineado(self):
        """REQ-EDT-02: casilla y borde completos, también con foco, en los tres tamaños."""
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            with self.subTest(ancho=ancho):
                c, p, v = self.contexto(ancho=ancho, alto=alto)
                # (E8: sin la casilla «Mostrar etiqueta» no queda casilla en la ventana de la transición: el foco se prueba en la etiqueta)
                for foco in (False, True):
                    p.t_etiqueta.setFocus() if foco else p.t_etiqueta.clearFocus()
                    HC._bombear(3)
                    self.assertEqual(regla_C6(v), [])
                    etiquetas = [x for x in p.t_etiqueta.parentWidget().findChildren(QLabel)
                                 if x.text() in ("Etiqueta", "Comentario")]
                    self.assertEqual(len(etiquetas), 2)  # E8: el pie rotula la etiqueta y el comentario, uno junto a su campo (ya no en una columna común)
                    self.assertGreater(p.t_comentario.x(), p.t_etiqueta.geometry().right())
                c.w._mostrar_panel("inferior", False)

    def test_SW2_clic_fuera_se_consume(self):
        """REQ-EDT-02: el clic cierra sin seleccionar ni pulsar la barra de detrás."""
        c, p, v = self.contexto()
        seleccion = list(c.e.sel)
        QTest.mouseClick(c.w.diagrama.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        HC._bombear(3)
        self.assertFalse(v.isVisible())
        self.assertEqual(c.e.sel, seleccion)
        c.w._abrir_opciones()
        HC._bombear(3)
        QTest.mouseClick(c.w.tb_sim.widgetForAction(c.w.a_ejecutar), Qt.MouseButton.LeftButton)
        self.assertFalse(v.isVisible())
        self.assertEqual(c.w.modo, "editar")

    def test_SW3_popup_tiene_prioridad(self):
        """REQ-EDT-02: un clic exterior cierra primero el desplegable, después Propiedades."""
        c, p, v = self.contexto("evento")
        combo = p.accion.variable
        combo.showPopup()
        QTest.qWait(250)
        HC._bombear(3)
        self.assertIsNotNone(QApplication.activePopupWidget())
        QTest.mouseClick(c.w.diagrama.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        HC._bombear(3)
        self.assertFalse(combo.view().isVisible())
        self.assertTrue(v.isVisible())
        QTest.mouseClick(c.w.diagrama.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        self.assertFalse(v.isVisible())

    def test_SW4_clic_dentro_no_cierra(self):
        """REQ-EDT-02: ni la lupa ni la cabecera cierran la ventana."""
        c, p, v = self.contexto()
        for zona in (v.lupa, v.cabecera, v.titulo):
            QTest.mouseClick(zona, Qt.MouseButton.LeftButton)
            self.assertTrue(v.isVisible())

    def test_SW5_arrastrar_mueve_y_no_recoloca_con_zoom(self):
        """REQ-EDT-09: mover la cabecera desplaza solo Propiedades; el zoom conserva su lugar."""
        c, p, v = self.contexto()
        antes = v.pos()
        self.arrastrar(v, QPoint(15, 15))
        self.assertNotEqual(v.pos(), antes)
        self.assertTrue(v.isVisible())
        despues = v.pos()

        class Registro(QObject):
            def __init__(self):
                super().__init__()
                self.movimientos = []

            def eventFilter(self, objeto, evento):
                if evento.type() == QEvent.Type.Move:
                    self.movimientos.append(evento.pos())
                return False

        registro = Registro()
        v.installEventFilter(registro)
        c.w.diagrama.zoom(1.1)
        HC._bombear(3)
        self.assertEqual(v.pos(), despues)
        self.assertEqual(registro.movimientos, [])
        self.comprobar_limites(c, v)

    def test_SW6_arrastre_acotado(self):
        """REQ-EDT-02: X1 conserva la barra alcanzable aunque el resto salga del cliente."""
        c, p, v = self.contexto()
        for delta in (QPoint(-5000, -5000), QPoint(5000, 5000)):
            self.arrastrar(v, delta)
            self.comprobar_limites(c, v)

    def test_SW7_reabrir_centra(self):
        """REQ-EDT-02: la posición manual no persiste al cerrar."""
        c, p, v = self.contexto()
        self.arrastrar(v, QPoint(-100, -100))
        v.b_cerrar.click()
        c.w._abrir_opciones()
        HC._bombear(6)
        centro = c.w.flot._area().center()
        self.assertLessEqual((v.geometry().center() - centro).manhattanLength(), 2)

    def test_SW8_redimensionar_acota(self):
        """REQ-EDT-02: X1 conserva la barra alcanzable al estrechar la principal."""
        c, p, v = self.contexto(ancho=2000, alto=1250)
        self.arrastrar(v, QPoint(5000, 5000))
        c.w.resize(960, 1032)
        HC._bombear(10)
        c.w._escala_tras_la_rafaga()
        HC._bombear(10)
        self.comprobar_limites(c, v)

    def test_SW9_esc_y_cruz(self):
        """REQ-EDT-02: Esc y cruz siguen cerrando sin deseleccionar."""
        c, p, v = self.contexto()
        seleccion = list(c.e.sel)
        QTest.keyClick(p.t_etiqueta, Qt.Key.Key_Escape)
        self.assertFalse(v.isVisible())
        self.assertEqual(c.e.sel, seleccion)
        c.w._abrir_opciones()
        HC._bombear(4)
        QTest.mouseClick(v.b_cerrar, Qt.MouseButton.LeftButton)
        self.assertFalse(v.isVisible())

    def test_SW10_otras_casillas(self):
        """REQ-EDT-02: se revisan también etapa, acciones y las fichas de jerarquía."""
        for tipo in ("etapa", "evento", "condicionada", "transicion"):
            c, p, v = self.contexto(tipo)
            self.assertEqual(regla_C6(v), [])
            c.w._mostrar_panel("inferior", False)

    def test_SW11_jerarquia_y_auditoria_detecta_recortes(self):
        """REQ-EDT-02: macroetapa y encapsulante; la regla detecta un indicador desplazado fuera."""
        c, p, v = self.contexto("etapa")
        for tipo in ("macro", "enclosing"):
            c.w._mostrar_panel("inferior", False)
            sid = c.e.poner_etapa(QPointF(650, 250), tipo=tipo)
            c.e.seleccionar([sid])
            c.w._abrir_opciones()
            HC._bombear(6)
            self.assertEqual(regla_C6(v), [])
        c.w._mostrar_panel("inferior", False)
        # (E8: «Mostrar etiqueta» ya no existe y la ventana no deja otra casilla a la vista: se prueba que la regla detecta un indicador desplazado
        # fuera con una casilla de la propia ventana)
        from escritorio.interaccion_propiedades import CasillaPropiedades
        casilla = CasillaPropiedades("Casilla de prueba", v.cuerpo)
        casilla.move(estilo.E4, estilo.E4)
        casilla.show()
        HC._bombear(3)
        self.assertTrue(casilla.isVisible())
        antes = casilla.pos()
        casilla.move(-10, casilla.y())
        self.assertTrue(regla_C6(v))
        casilla.move(antes)
        self.assertEqual(regla_C6(v), [])

    def test_SW12_clic_por_ventana_nativa(self):
        """REQ-EDT-02: la modalidad no oculta el clic exterior al filtro de la aplicación."""
        c, p, v = self.contexto()
        seleccion = list(c.e.sel)
        QTest.mouseClick(c.w.windowHandle(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        HC._bombear(5)
        self.assertFalse(v.isVisible())
        self.assertEqual(c.e.sel, seleccion)

    def test_SW13_popup_y_clic_por_ventana_nativa(self):
        """REQ-EDT-02: el clic nativo tampoco atraviesa los dos niveles de ventanas."""
        c, p, v = self.contexto("evento")
        seleccion = list(c.e.sel)
        combo = p.accion.variable
        combo.showPopup()
        QTest.qWait(250)
        self.assertTrue(combo.view().isVisible())
        QTest.mouseClick(c.w.windowHandle(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        HC._bombear(5)
        self.assertFalse(combo.view().isVisible())
        self.assertTrue(v.isVisible())
        self.assertEqual(c.e.sel, seleccion)
        QTest.mouseClick(c.w.windowHandle(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        HC._bombear(5)
        self.assertFalse(v.isVisible())
        self.assertEqual(c.e.sel, seleccion)


if __name__ == "__main__":
    unittest.main()
