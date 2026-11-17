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
    from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
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
            c.w._cambiar_modo_propiedades("flotante")
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
        """El cambio de letra normal a grande conserva el tope confirmado de 848 px lógicos."""
        for tipo in ("transicion", "condicionada", "evento", "activacion_numerica"):
            referencia = None
            for ancho, alto in ((960, 1032), (1920, 1080), (2560, 1440)):
                with self.subTest(tipo=tipo, ancho=ancho):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    referencia = v.width() if referencia is None else referencia
                    self.assertLessEqual(abs(v.width() - referencia), 2)
                    self.assertEqual(v.width(), 848)
                    self.doCleanups()

    def test_SY2_medias_pantallas_y_altos_previos_no_cambian(self):
        """Medidas de referencia tomadas antes de Y, sin alterar la altura vigente de X+."""
        for ancho, alto, esperado in ((683, 768, 587), (960, 1032, 848)):
            for tipo in ("transicion", "condicionada", "evento", "activacion_numerica"):
                with self.subTest(tipo=tipo, ancho=ancho):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    alto_previo = {"transicion": 558, "activacion_numerica": 465}.get(
                        tipo, 603 if ancho == 683 else 867)
                    self.assertEqual((v.width(), v.height()), (esperado, alto_previo))
                    self.doCleanups()

    def test_SY3_centrada_y_categorias_enteras_a_pantalla_completa(self):
        """Una sola fila de categorías completas dentro de su columna con el ancho nuevo."""
        for ancho, alto in ((1366, 768), (1920, 1080), (2560, 1440)):
            for tipo in ("transicion", "condicionada", "evento"):
                with self.subTest(tipo=tipo, ancho=ancho):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    self.assertLessEqual((v.geometry().center() - c.w.flot._area().center()).manhattanLength(), 2)
                    botones = list(p.prog.categorias.values())
                    self.assertEqual(len({b.y() for b in botones}), 1)
                    self.assertFalse(p.categorias_una_fila.no_cabe)
                    for b in botones:
                        op = QStyleOptionButton()
                        b.initStyleOption(op)
                        r = b.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, op, b)
                        pide = b.fontMetrics().horizontalAdvance(b.text()) + b.iconSize().width() + 9
                        self.assertGreaterEqual(r.width(), pide)
                        self.assertTrue(b.parentWidget().rect().contains(b.geometry()))
                    self.doCleanups()

    def test_SY4_etapas_y_macroetapas_conservan_su_ancho_menor(self):
        """El máximo también rige para las fichas cortas sin estirarlas hasta el tope."""
        for tipo in ("etapa", "inicial", "macroetapa", "activacion", "desactivacion"):
            c, p, v = self.contexto(tipo, 1920, 1080)
            self.assertLessEqual(v.width(), 848)
            self.assertTrue(v.isVisible())
            self.doCleanups()

    def test_SY5_cursor_de_flecha_sin_perder_el_arrastre(self):
        """La cabecera, título y cerrar heredan flecha, y el movimiento conserva el agarre."""
        c, p, v = self.contexto()
        for widget in (v, v.cabecera, v.titulo, v.b_cerrar):
            self.assertEqual(widget.cursor().shape(), Qt.CursorShape.ArrowCursor)
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

    def test_SY7_altos_a_pantalla_completa_se_conservan(self):
        """El tope horizontal no cambia las alturas medidas antes de Y."""
        for ancho, alto in ((1920, 1080), (2560, 1440)):
            for tipo, esperado in (("transicion", 664), ("activacion_numerica", 553),
                                   ("condicionada", 905 if ancho == 1920 else 1265)):
                c, p, v = self.contexto(tipo, ancho, alto)
                self.assertEqual(v.height(), esperado, (ancho, tipo))
                self.doCleanups()


if __name__ == "__main__":
    unittest.main()
