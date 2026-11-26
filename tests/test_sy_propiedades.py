"""SY: ancho acotado, cursor normal y lupa que solo pinta su elemento."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
    from PySide6.QtGui import QColor, QPen
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QStyle, QStyleOptionButton
    from escritorio import estilo
    from escritorio.elementos_lupa import DATO_ELEMENTOS
    from tools import hoja_contactos as HC
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class PropiedadesY(unittest.TestCase):
    def contexto(self, tipo="transicion", ancho=960, alto=1032):
        HC.aplicacion()
        c = HC.Contexto(ancho, alto)
        self.addCleanup(c.cerrar)
        if tipo == "macroetapa":
            HC._edicion(c)
            mid = c.e.poner_macro(QPointF(500, 200))
            c.e.seleccionar([mid])
            c.w._abrir_opciones()
        else:
            HC._flotante("etapa" if tipo == "inicial" else tipo)(c)
            if tipo == "etapa":
                c.e.seleccionar([c.ids["etapas"][1]])
                c.w._abrir_opciones()
        HC._bombear(10)
        return c, c.w.flot.panel, c.w.flot.principal

    def test_SY1_ancho_maximo_igual_al_de_media_pantalla(self):
        """El cambio de letra normal a grande conserva el tope de 920 px lógicos en 2.0.1 (y 848 px a media pantalla 960)."""
        for tipo in ("transicion", "condicionada", "evento", "activacion_numerica"):
            for ancho, alto, esperado in ((960, 1032, 848), (1920, 1080, 920), (2560, 1440, 920)):
                with self.subTest(tipo=tipo, ancho=ancho):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    self.assertEqual(v.width(), esperado)
                    self.doCleanups()

    def test_SY2_medias_pantallas_y_altos_acotados_al_area_actual(self):
        """En media pantalla, los editores mantienen altura estable (`_marco_ventana() + 332`) acotada al área disponible."""
        for ancho, alto, esperado in ((683, 768, 587), (960, 1032, 848)):
            for tipo in ("transicion", "condicionada", "evento", "activacion_numerica"):
                with self.subTest(tipo=tipo, ancho=ancho):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    disponible = c.w.paginas_es.height() - 2 * estilo.E6
                    alto_esperado = min(disponible, max(c.w.flot._marco_ventana() + 332, 460))
                    self.assertEqual((v.width(), v.height()), (esperado, alto_esperado))
                    self.assertLessEqual(v.height(), disponible)
                    self.doCleanups()

    def test_SY3_centrada_y_categorias_enteras_a_pantalla_completa(self):
        """La ventana centrada y la banda de categorías entera dentro de su columna con el ancho nuevo (E8: la banda sustituye a las pestañas;
        cambia el soporte de la comprobación, no lo que se exige)."""
        for ancho, alto in ((1366, 768), (1920, 1080), (2560, 1440)):
            for tipo in ("transicion", "condicionada", "evento"):
                with self.subTest(tipo=tipo, ancho=ancho):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    self.assertLessEqual((v.geometry().center() - c.w.flot._area().center()).manhattanLength(), 2)
                    banda = p.prog.banda
                    elementos = list(p.prog.categorias.values()) + [b for bs in banda.botones.values() for b in bs]
                    for w in elementos:
                        self.assertTrue(w.isVisible(), w.text())
                        self.assertTrue(banda.rect().contains(QRect(w.mapTo(banda, QPoint()), w.size())), w.text())
                        self.assertGreaterEqual(w.width(), w.fontMetrics().horizontalAdvance(w.text()), w.text())
                    self.doCleanups()

    def test_SY4_etapas_y_macroetapas_conservan_su_ancho_menor(self):
        """El máximo de 920 px rige en acciones; etapas y macroetapas conservan su ancho compacto (640 px)."""
        for tipo in ("etapa", "inicial", "macroetapa", "activacion", "desactivacion"):
            c, p, v = self.contexto(tipo, 1920, 1080)
            if tipo in ("etapa", "inicial", "macroetapa"):
                self.assertLessEqual(v.width(), 40 * estilo.E4)
            else:
                self.assertEqual(v.width(), 920)
            self.assertTrue(v.isVisible())
            self.doCleanups()

    def test_SY5_cursor_de_flecha_sin_perder_el_arrastre(self):
        """La ventana, cabecera y título heredan flecha; ✕ muestra mano apuntadora, y el movimiento conserva el agarre."""
        c, p, v = self.contexto()
        for widget in (v, v.cabecera, v.titulo):
            self.assertEqual(widget.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(v.b_cerrar.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        antes = v.pos()
        inicio = QPoint(90, v.cabecera.height() // 2)
        QTest.mousePress(v.cabecera, Qt.MouseButton.LeftButton, pos=inicio)
        QTest.mouseMove(v.cabecera, inicio + QPoint(17, 13))
        QTest.mouseRelease(v.cabecera, Qt.MouseButton.LeftButton, pos=inicio + QPoint(17, 13))
        self.assertEqual(v.pos(), antes + QPoint(17, 13))

    def test_SY6_lupa_identica_con_y_sin_vecinos(self):
        """No basta estrechar un recorte: ni un ítem vecino superpuesto puede salir en la lupa."""
        for tipo in ("etapa", "inicial", "transicion", "activacion", "condicionada", "evento", "macroetapa"):
            with self.subTest(tipo=tipo):
                c, p, v = self.contexto(tipo)
                escena = c.w.diagrama.scene()
                propios = [i for i in escena.items() if p.ident in (i.data(DATO_ELEMENTOS) or ())]
                self.assertTrue(propios)
                centro = v.lupa.origen.center()
                intruso = escena.addRect(QRectF(centro.x() - 4, centro.y() - 4, 8, 8),
                                        QPen(Qt.PenStyle.NoPen), QColor(estilo.ERROR))
                intruso.setData(DATO_ELEMENTOS, ("vecino-ajeno",))
                intruso.setZValue(9)
                vecinos = [i for i in escena.items() if i.isVisible() and i not in propios]
                antes = v.lupa.grab().toImage()
                self.assertTrue(all(i.isVisible() for i in vecinos))
                for item in vecinos:
                    item.hide()
                despues = v.lupa.grab().toImage()
                self.assertEqual(antes, despues)
                for item in vecinos:
                    item.show()
                self.doCleanups()

    def test_SY7_altos_a_pantalla_completa_se_ajustan_al_area_actual(self):
        """A pantalla completa, todos los editores conservan su altura estable (`_marco_ventana() + 332`) sin estirarse al borde."""
        fijos = {"transicion": 533, "activacion_numerica": 577, "condicionada": 581}
        for ancho, alto in ((1920, 1080), (2560, 1440)):
            for tipo in fijos:
                c, p, v = self.contexto(tipo, ancho, alto)
                disponible = c.w.paginas_es.height() - 2 * estilo.E6
                self.assertEqual(v.height(), c.w.flot._marco_ventana() + 332, (ancho, tipo))
                self.assertEqual(v.height(), fijos[tipo], (ancho, tipo))
                self.assertLess(v.height(), disponible, (ancho, tipo))
                self.doCleanups()


if __name__ == "__main__":
    unittest.main()
