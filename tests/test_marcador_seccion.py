"""El cuadrado de etapa de los títulos de sección se pinta entero (no se recorta su borde izquierdo)."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPoint, QRect, QSize, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio import estilo
    from escritorio.paneles import LADO_MARCADOR, TituloSeccion


def lados(img, x0, cy):
    """Los píxeles de los cuatro lados del cuadrado que empieza en x0 y está centrado en cy."""
    l = LADO_MARCADOR
    return {"izq": img.pixelColor(x0, cy), "der": img.pixelColor(x0 + l - 1, cy),
            "arr": img.pixelColor(x0 + l // 2, cy - l // 2), "abj": img.pixelColor(x0 + l // 2, cy + l // 2 - 1)}


@unittest.skipUnless(QT, "Falta PySide6")
class MarcadorSeccion(BaseQt):
    def comprobar(self, img, x0, cy, donde):
        fondo, trazo = QColor(estilo.SUPERFICIE), QColor(estilo.ACENTO)
        for lado, c in lados(img, x0, cy).items():
            d_trazo = sum(abs(a - b) for a, b in zip(c.getRgb()[:3], trazo.getRgb()[:3]))
            d_fondo = sum(abs(a - b) for a, b in zip(c.getRgb()[:3], img.pixelColor(x0 + LADO_MARCADOR + 20, cy).getRgb()[:3]))
            self.assertLess(d_trazo, d_fondo, f"{donde}: el lado {lado} del cuadrado no es del color del trazo ({c.name()})")

    def test_SMAR01_el_cuadrado_del_titulo_de_hojas_se_ve_entero_a_dos_tamanos(self):
        """REQ-UX-01: el cuadrado de etapa delante de «Hojas» tiene sus cuatro lados del color del trazo (no se recorta el izquierdo) y deja el mismo margen que los paneles (cuadrado a 13 px, botón «+ Añadir hoja» a 8 px y centrado), a 1366×768 y 2000×1250."""
        w, e = self.vacio()
        w.show()
        for ancho, alto in ((1366, 768), (2000, 1250)):
            w.resize(ancho, alto)
            b = w.pestanas_vistas
            QTest.mouseClick(b, Qt.MouseButton.LeftButton, pos=b.tabRect(1).center())
            for _ in range(12):
                QApplication.processEvents()
                QTest.qWait(10)
            t = next(x for x in w.panel_planos.findChildren(TituloSeccion) if x.text() == "Hojas")
            img = t.grab().toImage()
            self.comprobar(img, t.contentsMargins().left() + t.x_marcador, t.height() // 2, f"Hojas {ancho}×{alto}")
            # los márgenes de la columna, como los de los paneles (Variables: tabla y botones a 8 px del borde de su tarjeta; Elementos y
            # Variables: el cuadrado a 13 px): el cuadrado a 13, el botón «+ Añadir hoja» a 8 de cada lado
            vista = w.panel_planos.scroll_hojas.viewport()
            marcador = t.mapTo(vista, QPoint(0, 0)).x() + t.contentsMargins().left() + t.x_marcador
            b = w.panel_planos.b_hoja
            izq = b.mapTo(vista, QPoint(0, 0)).x()
            der = vista.width() - (izq + b.width())
            self.assertAlmostEqual(marcador, 13, delta=1, msg=f"cuadrado {ancho}×{alto}")
            self.assertAlmostEqual(izq, 8, delta=1, msg=f"botón a la izquierda {ancho}×{alto}")
            self.assertAlmostEqual(der, izq, delta=1, msg=f"botón centrado {ancho}×{alto}")
            lista = w.panel_planos.lista
            self.assertGreaterEqual(vista.width() - 8, lista.mapTo(vista, QPoint(0, 0)).x() + lista.width() - 1, "la lista no se sale por la derecha")
        w.hide()

    def test_SMAR02_un_titulo_suelto_sin_margen_tampoco_se_recorta(self):
        """REQ-UX-01: un TituloSeccion pegado al borde de su contenedor pinta el cuadrado entero."""
        QApplication.instance()
        t = TituloSeccion("Prueba")
        t.resize(120, 22)
        t.setStyleSheet(f"background: {estilo.SUPERFICIE}")
        t.show()
        QApplication.processEvents()
        self.comprobar(t.grab().toImage(), 0, 11, "suelto")
        t.hide()
