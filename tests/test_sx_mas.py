"""SX+: fórmulas a media pantalla, nombres de macroetapas y simultaneidad sola."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QPoint, QPointF, QRect, Qt
    from PySide6.QtWidgets import QGraphicsTextItem, QStyle, QStyleOptionButton
    from PySide6.QtTest import QTest
    from tools import hoja_contactos as HC
    from escritorio import estilo
    from escritorio.diagrama import barra, posiciones
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class PropiedadesMas(unittest.TestCase):
    def contexto(self, tipo="transicion", ancho=853, alto=1019):
        HC.aplicacion()
        c = HC.Contexto(ancho, alto)
        self.addCleanup(c.cerrar)
        HC._flotante(tipo)(c)
        return c, c.w.flot.panel, c.w.flot.principal

    def test_SXM1_banda_de_categorias_entera(self):
        """REQ-EDT-02: en las tres ventanas, la cinta de inserción (`.op-ribbon`: «Insertar:» + botones de inserción y herramientas)
        cabe entera, también a media pantalla real: nada queda cortado ni superpuesto."""
        for ancho, alto in ((853, 1019), (960, 1032), (1366, 768), (1920, 1080)):
            for tipo in ("transicion", "condicionada", "evento"):
                with self.subTest(ancho=ancho, tipo=tipo):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    banda = p.prog.banda
                    rotulos = list(p.prog.categorias.values())
                    self.assertEqual(banda.l_prefijo.text(), "Insertar:")
                    self.assertTrue(all(r is banda.l_prefijo for r in rotulos))
                    botones = [b for bs in banda.botones.values() for b in bs]
                    self.assertEqual([b.text() for b in botones], ["( … )", "Temporizador", "= ≠ < ≥", "1", "0"])
                    for w in [banda.l_prefijo, *botones, *banda._herramientas]:
                        self.assertTrue(w.isVisible(), w.text())
                        self.assertTrue(banda.rect().contains(QRect(w.mapTo(banda, QPoint()), w.size())), w.text())
                        self.assertGreaterEqual(w.width(), w.fontMetrics().horizontalAdvance(w.text()), w.text())
                    rects = [QRect(w.mapTo(banda, QPoint()), w.size()) for w in [*botones, *banda._herramientas]]
                    for i, a in enumerate(rects):
                        for b in rects[i + 1:]:
                            self.assertFalse(a.intersects(b), "los botones no se pisan")
                    c.w._mostrar_panel("inferior", False)

    def test_SXM2_campos_sin_corte_y_comentario_largo(self):
        """REQ-EDT-02: etiqueta inline en cabecera y comentario a todo el ancho en la franja inferior `.comment-row`."""
        for ancho in (853, 960, 1366):
            c, p, v = self.contexto(ancho=ancho)
            self.assertIs(p.t_etiqueta.parentWidget(), v.caja_etiqueta)
            self.assertIs(p.t_comentario.parentWidget(), v.pie)
            self.assertEqual(p.t_etiqueta.width(), 56)
            self.assertGreater(p.t_comentario.width(), p.t_etiqueta.width() * 2)
            self.assertGreater(p.t_comentario.x(), v.pie.l_comentario.geometry().right())
            self.assertEqual(v.pie.width() - (p.t_comentario.geometry().right() + 1), 14)  # margen derecho de 14 px en `.comment-row`
            c.w._mostrar_panel("inferior", False)

    def test_SXM3_altura_moderada_y_aire_alrededor(self):
        """REQ-EDT-02: altura estable (`_marco_ventana() + 332`) con aire alrededor y área cómoda para bloques."""
        for ancho, alto in ((1366, 768), (1920, 1080)):
            c, p, v = self.contexto(ancho=ancho, alto=alto)
            self.assertEqual(v.height(), c.w.flot._marco_ventana() + 332)
            self.assertGreater(v.height(), 465)
            self.assertLess(v.height(), c.w.flot._area().height() - 2 * estilo.E6)
            self.assertGreater(p.prog.lienzo.height(), 200)
            c.w._mostrar_panel("inferior", False)

    def test_SXM4_aviso_vacio_y_lupa_se_conservan(self):
        """REQ-EDT-02: la transición vacía sigue mostrando el aviso rojo bajo los bloques."""
        c, p, v = self.contexto()
        p._desde_bloques("")
        HC._bombear(5)
        self.assertTrue(v.lupa.isVisible())
        self.assertTrue(p.t_estado.isVisible())
        self.assertIn("Vacía: la transición no compila", p.t_estado.text())
        self.assertIn("#c62828", p.t_estado.styleSheet().lower())

    def test_SXM5_esquinas_redondas_y_fondo_opaco(self):
        """REQ-UX-01: curvas transparentes por fuera, fondo blanco `#ffffff` completamente opaco en 2.0.1."""
        c, p, v = self.contexto()
        self.assertTrue(v.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(v.windowFlags() & Qt.WindowType.NoDropShadowWindowHint)
        imagen = v.grab().toImage()
        dpr = imagen.devicePixelRatio()
        for x, y in ((5, 5), (400, 25), (5, 100)):
            color = imagen.pixelColor(round(x * dpr), round(y * dpr))
            self.assertEqual(color.alpha(), 255)
            self.assertEqual(color.name(), estilo.SUPERFICIE)
        for x, y in ((0, 0), (imagen.width() - 1, 0),
                     (0, imagen.height() - 1), (imagen.width() - 1, imagen.height() - 1)):
            self.assertEqual(imagen.pixelColor(x, y).alpha(), 0)


@unittest.skipUnless(QT, "requiere PySide6")
class EdicionMas(unittest.TestCase):
    def contexto(self):
        HC.aplicacion()
        c = HC.Contexto(1366, 768)
        c.mostrar()
        self.addCleanup(c.cerrar)
        return c

    def test_SXM6_nombre_macro_renombra_expansion_y_deshace(self):
        """REQ-JER-07: el texto M1 edita M33, E33 y S33 en una sola operación, conservando las referencias."""
        c = self.contexto()
        e = c.e
        mid = e.poner_macro(QPointF(600, 250))
        info = e.ed.macro_info(mid)
        e.pedir_texto = Mock(return_value="M33")
        nombre = next(i for i in c.w.diagrama.scene().items()
                      if isinstance(i, QGraphicsTextItem) and i.toPlainText() == "M1")
        n = len(e.ed.undo_stack)
        e.doble(nombre.sceneBoundingRect().center())
        self.assertEqual(e.nombre(mid), "M33")
        self.assertEqual((e.nombre(info.entry), e.nombre(info.exit)), ("E33", "S33"))
        self.assertEqual(e.ed.macro_info(mid), info)
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        c.w.activateWindow()
        c.w.diagrama.setFocus()
        HC._bombear(3)
        QTest.keyClick(c.w.diagrama.viewport(), Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        HC._bombear(3)
        self.assertEqual((e.nombre(mid), e.nombre(info.entry), e.nombre(info.exit)), ("M1", "E1", "S1"))
        e.pedir_texto.assert_called_once()

    def test_SXM7_cuerpo_macro_navega_y_nombre_repetido_se_rechaza(self):
        """REQ-JER-07: cuerpo y nombre mantienen operaciones distintas; el rechazo no cambia el modelo."""
        c = self.contexto()
        e = c.e
        mid = e.poner_macro(QPointF(600, 250))
        otro = e.poner_macro(QPointF(600, 500))
        centro = QPointF(*posiciones(e.M)[mid])
        e.encuadrar_expansion = Mock()
        e.doble(centro + QPointF(0, -17))
        e.encuadrar_expansion.assert_called_once_with(mid)
        antes = len(e.ed.undo_stack)
        e.pedir_texto = Mock(return_value=e.nombre(otro))
        nombre = next(i for i in c.w.diagrama.scene().items()
                      if isinstance(i, QGraphicsTextItem) and i.toPlainText() == "M1")
        e.doble(nombre.sceneBoundingRect().center())
        self.assertEqual(e.nombre(mid), "M1")
        self.assertEqual(len(e.ed.undo_stack), antes)
        self.assertTrue(e.mensaje)

    def test_SXM8_simultaneidad_sola_visible_y_persistente(self):
        """REQ-EDT-02: la doble línea sola se dibuja y conserva su caja al añadir y quitar otro elemento."""
        c = self.contexto()
        e = c.e
        e.colocar("simultaneidad", QPointF(600, 250))
        bid = e.sel[0]
        caja = barra(next(b for b in e.M["bars"] if b["id"] == bid))
        self.assertGreater(caja[2], 0)
        self.assertGreater(caja[3], 0)
        escena = c.w.diagrama.scene()
        lineas = [i for i in escena.items() if i.toolTip() == "Simultaneidad"]
        self.assertEqual(len(lineas), 2)
        self.assertTrue(all(i.isVisible() for i in lineas))
        self.assertTrue(all(escena.sceneRect().intersects(i.sceneBoundingRect()) for i in lineas))
        tid = e.poner_transicion(QPointF(700, 400))
        e.seleccionar([tid])
        self.assertTrue(e.borrar())
        self.assertEqual(len([i for i in escena.items() if i.toolTip() == "Simultaneidad"]), 2)
        self.assertEqual(caja, barra(next(b for b in e.M["bars"] if b["id"] == bid)))


if __name__ == "__main__":
    unittest.main()
