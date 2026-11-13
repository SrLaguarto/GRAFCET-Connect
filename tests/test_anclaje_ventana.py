"""El zoom manual queda anclado al área cliente, también entre pintados."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QEvent, QObject, QPoint, QPointF
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication


@unittest.skipUnless(QT, "requiere PySide6")
class AnclajeVentana(BaseQt):
    def preparar(self, modo):
        w, e = self.vacio()
        self.addCleanup(w.hide)
        self.cadena(e)
        w.resize(1366, 768)
        w.show()
        QTest.qWait(650)
        w.cambiar_modo(modo)
        w.rt.stop()
        d = w.diagrama
        d.zoom(1.37)
        for _ in range(5):
            QApplication.processEvents()
        return w, d

    def puntos(self, w, d):
        return tuple(d.viewport().mapTo(w, d.mapFromScene(p)).toTuple()
                     for p in (QPointF(), QPointF(80, 60), QPointF(400, 500)))

    def comprobar_tamanos(self, modo):
        w, d = self.preparar(modo)
        antes = self.puntos(w, d)
        zoom = d.escala()
        pintados = []
        prueba = self

        class Pintados(QObject):
            def eventFilter(self, objeto, evento):  # noqa: N802
                if evento.type() == QEvent.Type.Paint:
                    pintados.append(prueba.puntos(w, d))
                return False

        filtro = Pintados(d)
        d.viewport().installEventFilter(filtro)
        try:
            for ancho, alto in ((1400, 768), (1560, 950), (1700, 1000), (2000, 1250),
                                (960, 1032), (900, 540), (1400, 520), (1366, 768)):
                with self.subTest(modo=modo, tamano=(ancho, alto)):
                    w.resize(ancho, alto)
                    for _ in range(5):
                        QApplication.processEvents()
                        self.assertEqual(self.puntos(w, d), antes)
                    QTest.qWait(180)  # Incluye el cambio diferido de escala, sin forzarlo.
                    d.viewport().repaint()
                    self.assertEqual(self.puntos(w, d), antes)
                    self.assertEqual(d.escala(), zoom)
        finally:
            d.viewport().removeEventFilter(filtro)
        self.assertTrue(pintados)
        self.assertTrue(all(p == antes for p in pintados), (antes, set(pintados)))

    def test_SANC01_edicion_paneles_escala_compacto_y_pintados(self):
        """REQ-EDT-09: cero píxeles de desplazamiento respecto a la ventana, antes de cada pintado."""
        self.comprobar_tamanos("editar")

    def test_SANC02_simulacion_manual_paneles_escala_compacto_y_pintados(self):
        """REQ-SIM-03: con zoom manual se conserva el ancla respecto a la ventana y el zoom exacto."""
        self.comprobar_tamanos("simular")

    def test_SANC03_mover_vista_o_ancestro_sin_redimensionar(self):
        """REQ-EDT-09: Move sin Resize, incluso de un ancestro, compensa el origen inmediatamente."""
        w, d = self.preparar("editar")
        antes = self.puntos(w, d)
        tamano = d.size()
        d.move(d.pos() + QPoint(8, 12))
        self.assertEqual(d.size(), tamano)
        self.assertEqual(self.puntos(w, d), antes)
        padre = d.parentWidget()
        padre.move(padre.pos() + QPoint(4, 8))
        self.assertEqual(self.puntos(w, d), antes)

    def test_SANC04_desplazar_a_mano_actualiza_el_ancla(self):
        """REQ-EDT-09: el ancla respeta un desplazamiento deliberado por las barras."""
        w, d = self.preparar("editar")
        antes = self.puntos(w, d)
        barra = d.horizontalScrollBar()
        barra.setValue(barra.value() + 40)
        despues = self.puntos(w, d)
        self.assertNotEqual(antes, despues)
        w.resize(1800, 1000)
        QTest.qWait(180)
        self.assertEqual(self.puntos(w, d), despues)
