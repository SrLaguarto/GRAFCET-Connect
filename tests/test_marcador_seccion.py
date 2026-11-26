"""El cuadrado de etapa de los títulos de sección se pinta entero (no se recorta su borde izquierdo)."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPoint, QRect, QSize, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio import estilo
    from escritorio.paneles import ALTO_MARCADOR, ANCHO_MARCADOR, TituloSeccion


@unittest.skipUnless(QT, "Falta PySide6")
class MarcadorSeccion(BaseQt):
    def comprobar(self, img, x0, cy, donde):
        dpr = img.devicePixelRatio()
        trazo = QColor(estilo.ACENTO)
        fondo = img.pixelColor(round((x0 + ANCHO_MARCADOR + 20) * dpr), round(cy * dpr))
        puntos = (
            ("centro", x0 + ANCHO_MARCADOR // 2, cy),
            ("arriba", x0 + ANCHO_MARCADOR // 2, cy - ALTO_MARCADOR // 2 + 1),
            ("abajo", x0 + ANCHO_MARCADOR // 2, cy + ALTO_MARCADOR // 2 - 2),
        )
        for lado, x, y in puntos:
            c = img.pixelColor(round(x * dpr), round(y * dpr))
            d_trazo = sum(abs(a - b) for a, b in zip(c.getRgb()[:3], trazo.getRgb()[:3]))
            d_fondo = sum(abs(a - b) for a, b in zip(c.getRgb()[:3], fondo.getRgb()[:3]))
            self.assertLess(d_trazo, d_fondo, f"{donde}: la zona {lado} del filete no es del color del trazo ({c.name()})")

    def test_SMAR01_la_cabecera_y_lista_de_hojas_caben_a_dos_tamanos(self):
        """REQ-UX-01: en Planos v2 la cabecera «Hojas» y su contador quedan contenidos dentro de su columna lateral y la lista no sobresale por la derecha a 1366×768 ni a 2000×1250."""
        w, e = self.vacio()
        w.show()
        for ancho, alto in ((1366, 768), (2000, 1250)):
            w.resize(ancho, alto)
            b = w.pestanas_vistas
            QTest.mouseClick(b, Qt.MouseButton.LeftButton, pos=b.tabRect(1).center())
            for _ in range(12):
                QApplication.processEvents()
                QTest.qWait(10)
            p = w.panel_planos
            vista = p.scroll_hojas.viewport()
            cab = p.titulo_hojas.parentWidget()
            self.assertEqual(p.titulo_hojas.text(), "Hojas")
            self.assertEqual(p.l_cont_hojas.text(), "0")
            self.assertLessEqual(cab.width(), vista.width())
            self.assertTrue(p.scroll_hojas.isAncestorOf(p.b_hoja))
            self.assertTrue(p.b_hoja.isHidden())
            lista = p.lista
            self.assertGreaterEqual(vista.width() - 8, lista.mapTo(vista, QPoint(0, 0)).x() + lista.width() - 1, "la lista no se sale por la derecha")
        w.hide()

    def test_SMAR02_un_titulo_suelto_sin_margen_tampoco_se_recorta(self):
        """REQ-UX-01: un TituloSeccion pegado al borde de su contenedor pinta el filete entero; con `con_marcador=False` queda limpio."""
        QApplication.instance()
        t = TituloSeccion("Prueba")
        t.resize(120, 22)
        t.setStyleSheet(f"background: {estilo.SUPERFICIE}")
        t.show()
        QApplication.processEvents()
        self.comprobar(t.grab().toImage(), 0, 11, "suelto")
        t.hide()

        sub = TituloSeccion("Condición", con_marcador=False)
        sub.resize(120, 22)
        sub.setStyleSheet(f"background: {estilo.SUPERFICIE}; color: {estilo.TINTA}")
        sub.show()
        QApplication.processEvents()
        img = sub.grab().toImage()
        self.assertFalse(
            any(img.pixelColor(x, y).name() == estilo.ACENTO for x in range(img.width()) for y in range(img.height()))
        )
        sub.hide()
