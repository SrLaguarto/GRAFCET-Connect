"""Pruebas de la tanda T0b: fichas de estilo (#10) y componentes visuales comunes reutilizables."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

try:
    from PySide6.QtCore import QRect, QSize
    from PySide6.QtGui import QColor, QFontMetrics, QImage, QPainter
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QListWidget,
        QVBoxLayout,
        QWidget,
    )
    QT = True
except ImportError:
    QT = False

if QT:
    from escritorio import estilo, estilo_dialogos
    from escritorio.componentes_comunes import (
        BarraPapel,
        CabeceraDialogo,
        DesplegableAcotado,
        PastillaBooleana,
        PieDialogo,
        acotar_desplegable,
        colores_pastilla_booleana,
        icono_barra_papel,
        normalizar_botones_dialogo,
        pintar_barra_papel,
        pintar_pastilla_booleana,
        pixmap_barra_papel,
    )


@unittest.skipUnless(QT, "Falta PySide6")
class TestT0bEstiloYComponentes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        estilo.activar_escala("normal")

    def setUp(self) -> None:
        estilo.activar_escala("normal")
        self.addCleanup(estilo.activar_escala, "normal")

    def test_T0B01_fichas_color_alturas_radio_y_papeles_propuesta_10(self) -> None:
        """Verifica que todas las fichas de la propuesta #10 están expuestas en `escritorio.estilo`."""
        self.assertEqual(estilo.PRIMARIO, "#0b6e75")
        self.assertEqual(estilo.ACENTO, "#0b6e75")
        self.assertEqual(estilo.PRIMARIO_HOVER, "#095a60")
        self.assertEqual(estilo.ACENTO_HOVER, "#095a60")

        self.assertEqual(estilo.SELECCION_FONDO, "#cfeee6")
        self.assertEqual(estilo.ACENTO_SUAVE, "#cfeee6")
        self.assertEqual(estilo.SELECCION_BORDE, "#8fd3c3")
        self.assertEqual(estilo.ACENTO_BORDE, "#8fd3c3")
        self.assertEqual(estilo.SELECCION_TEXTO, "#0b4f54")

        self.assertEqual(estilo.SUPERFICIE, "#ffffff")
        self.assertEqual(estilo.SUPERFICIE_2, "#f7f9fc")
        self.assertEqual(estilo.SUPERFICIE_3, "#f1f5f9")
        self.assertEqual(estilo.CABECERA_PANEL, "#e2e8f0")

        self.assertEqual(estilo.BORDE_SUAVE, "#cbd5e1")
        self.assertEqual(estilo.BORDE_MEDIO, "#94a3b8")
        # `BORDE_CONTROL` conserva `#7b8a9c` para garantizar contraste >= 3:1 sobre SUPERFICIE_2 (`test_SL102`).
        self.assertEqual(estilo.BORDE_CONTROL, "#7b8a9c")

        self.assertEqual(estilo.PAPEL_ENTRADA, "#15747b")
        self.assertEqual(estilo.PAPEL_SALIDA, "#157a35")
        self.assertEqual(estilo.PAPEL_MEMORIA, "#6d28d9")
        for alias, esperado in (
            ("input", "#15747b"),
            ("entrada", "#15747b"),
            ("E", "#15747b"),
            ("output", "#157a35"),
            ("salida", "#157a35"),
            ("S", "#157a35"),
            ("internal", "#6d28d9"),
            ("memoria", "#6d28d9"),
            ("M", "#6d28d9"),
        ):
            self.assertEqual(estilo.color_papel_variable(alias), esperado, alias)

        self.assertEqual((estilo.ALTO_ESTANDAR, estilo.ALTO_COMPACTO), (32, 30))
        self.assertEqual(estilo.R_CONTROL, 6)
        self.assertEqual(estilo.ALTO_MAX_DESPLEGABLE, 300)
        self.assertEqual((estilo.BARRA_PAPEL_ANCHO, estilo.BARRA_PAPEL_ALTO), (3.5, 16.0))
        # `ORIGEN_MEMORIA` unificado con `PAPEL_MEMORIA` (#6d28d9) en C3.
        self.assertEqual(estilo.ORIGEN_MEMORIA, "#6d28d9")

    def test_T0B02_cifras_tabulares_avance_identico_sin_propiedades_qss_invalidas(self) -> None:
        """`fuente_tabular` garantiza el mismo ancho para las cifras 0–9 y `qss_tabular` es válido en Qt."""
        for modo_mono in (True, False):
            f = estilo.fuente_tabular(px=13, negrita=True, mono=modo_mono)
            fm = QFontMetrics(f)
            avances = {fm.horizontalAdvance(str(d)) for d in range(10)}
            self.assertEqual(len(avances), 1, (modo_mono, avances))
            self.assertEqual(fm.horizontalAdvance("111"), fm.horizontalAdvance("808"))
        self.assertNotIn("font-variant-numeric", estilo.qss_tabular())
        self.assertIn("Consolas", estilo.qss_tabular())

    def test_T0B03_pastilla_booleana_widget_y_pintor(self) -> None:
        """La pastilla booleana distingue visualmente `0` y `1` tanto en widget como en pintor delegado."""
        self.assertEqual(colores_pastilla_booleana(0), ("#f1f5f9", "#cbd5e1", "#64748b"))
        self.assertEqual(colores_pastilla_booleana(1), ("#dcfce7", "#86efac", "#15803d"))

        pastilla = PastillaBooleana(False)
        pastilla.resize(pastilla.sizeHint())
        self.assertEqual((pastilla.valor, pastilla.texto()), (False, "0"))
        img_0 = pastilla.grab().toImage()

        pastilla.poner_valor(True)
        self.assertEqual((pastilla.valor, pastilla.texto()), (True, "1"))
        img_1 = pastilla.grab().toImage()
        self.assertNotEqual(img_0, img_1)

        # Uso directo en `QPainter` (p. ej. delegados de tabla en C1)
        lienzo = QImage(60, 28, QImage.Format.Format_ARGB32_Premultiplied)
        lienzo.fill(QColor(estilo.SUPERFICIE))
        p = QPainter(lienzo)
        caja = pintar_pastilla_booleana(p, QRect(0, 0, 60, 28), 1)
        p.end()
        self.assertAlmostEqual(caja.height(), 19.0, delta=1.5)
        # En la esquina interior de la cápsula debe aparecer el relleno verde `#dcfce7`
        muestra = lienzo.pixelColor(int(caja.left() + 5), int(caja.top() + 4)).name()
        self.assertEqual(muestra, estilo.BOOL_1_FONDO)

    def test_T0B04_barra_papel_3_5x16_en_widget_pintor_e_icono(self) -> None:
        """La barra de papel pinta un trazo de `3,5 × 16 px` con los tres colores semánticos."""
        for papel, hex_esperado in (("input", "#15747b"), ("output", "#157a35"), ("internal", "#6d28d9")):
            w = BarraPapel(papel)
            self.assertEqual(w.color(), hex_esperado)
            img = w.grab().toImage()
            cx = round(img.width() / 2)
            cy = round(img.height() / 2)
            self.assertEqual(img.pixelColor(cx, cy).name(), hex_esperado)

            pm = pixmap_barra_papel(papel)
            self.assertEqual(pm.devicePixelRatio(), 2.0)
            ic = icono_barra_papel(papel)
            self.assertFalse(ic.isNull())

        lienzo = QImage(20, 24, QImage.Format.Format_ARGB32_Premultiplied)
        lienzo.fill(QColor(estilo.SUPERFICIE))
        p = QPainter(lienzo)
        caja = pintar_barra_papel(p, 4.0, 12.0, "memoria")
        p.end()
        self.assertEqual((caja.width(), caja.height()), (3.5, 16.0))
        self.assertEqual(lienzo.pixelColor(5, 12).name(), "#6d28d9")

    def test_T0B05_cabecera_y_pie_dialogo_orden_cancelar_aceptar(self) -> None:
        """Cabecera con barra de acento y pie estándar con `Cancelar` a la izquierda y `Aceptar` primario a la derecha."""
        dlg = QDialog()
        estilo_dialogos.aplicar_escala_dialogo(dlg)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)

        cab = CabeceraDialogo("Configuración de conexión", dlg, subtitulo="Ajusta los parámetros.", mostrar_cerrar=True)
        pie = PieDialogo(dlg, texto_ayuda="Pulsa Intro para confirmar").conectar(dlg)
        lay.addWidget(cab)
        lay.addStretch(1)
        lay.addWidget(pie)
        dlg.resize(460, 220)
        dlg.show()
        self.addCleanup(dlg.close)
        QApplication.processEvents()

        self.assertIsNotNone(cab.barra)
        self.assertIsNotNone(cab.boton_cerrar)
        self.assertEqual(cab.etiqueta_titulo.text(), "Configuración de conexión")
        self.assertTrue(cab.etiqueta_subtitulo.isVisible())

        self.assertEqual(pie.boton_cancelar.text(), "Cancelar")
        self.assertEqual(pie.boton_aceptar.text(), "Aceptar")
        self.assertTrue(bool(pie.boton_aceptar.property("primario")))
        self.assertFalse(bool(pie.boton_cancelar.property("primario")))
        self.assertEqual(pie.boton_aceptar.height(), estilo.ALTO_ESTANDAR)
        self.assertEqual(pie.boton_cancelar.height(), estilo.ALTO_ESTANDAR)
        self.assertLess(pie.boton_cancelar.geometry().right(), pie.boton_aceptar.geometry().left(),
                        "Orden obligatorio: Cancelar a la izquierda y Aceptar a la derecha")

    def test_T0B06_normalizar_botones_dialogo_reordena_qdialogbuttonbox(self) -> None:
        """`normalizar_botones_dialogo` deja `Cancelar | Aceptar` también en un `QDialogButtonBox` nativo."""
        cont = QWidget()
        cont.setStyleSheet(estilo.hoja_global())
        lay = QVBoxLayout(cont)
        caja = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, cont)
        lay.addWidget(caja)
        cancelar, aceptar = normalizar_botones_dialogo(caja, texto_aceptar="Guardar", texto_cancelar="Cancelar")
        cont.resize(400, 80)
        cont.show()
        self.addCleanup(cont.close)
        QApplication.processEvents()

        self.assertIsNotNone(cancelar)
        self.assertIsNotNone(aceptar)
        assert cancelar is not None and aceptar is not None
        self.assertEqual((cancelar.text(), aceptar.text()), ("Cancelar", "Guardar"))
        self.assertTrue(bool(aceptar.property("primario")))
        self.assertEqual(aceptar.height(), estilo.ALTO_ESTANDAR)
        self.assertLess(cancelar.geometry().right(), aceptar.geometry().left())

    def test_T0B07_desplegable_acotado_a_300px_con_scroll(self) -> None:
        """`DesplegableAcotado` y `acotar_desplegable` limitan listas largas a `300 px` sin alterar el alto cerrado."""
        cont = QWidget()
        cont.setStyleSheet(estilo.hoja_global())
        lay = QVBoxLayout(cont)

        combo = DesplegableAcotado(cont)
        for i in range(30):
            combo.addItem(f"Variable {i:02d}")
        lay.addWidget(combo)

        combo2 = QComboBox(cont)
        for i in range(25):
            combo2.addItem(f"Opción {i:02d}")
        acotar_desplegable(combo2, 300)
        lay.addWidget(combo2)

        lista = QListWidget(cont)
        for i in range(25):
            lista.addItem(f"Elemento {i:02d}")
        acotar_desplegable(lista, 300)
        lay.addWidget(lista)

        cont.resize(340, 460)
        cont.show()
        self.addCleanup(cont.close)
        QApplication.processEvents()

        # El control cerrado mantiene el alto de la escala activa (`30 px` en normal).
        self.assertAlmostEqual(combo.height(), estilo.ALTO_CONTROL, delta=1)
        self.assertEqual(lista.maximumHeight(), 300)

        combo.showPopup()
        QApplication.processEvents()
        try:
            self.assertTrue(combo.view().isVisible())
            self.assertLessEqual(combo.view().height(), 300)
            self.assertLessEqual(combo.view().window().height(), 302)
            self.assertGreater(combo.view().verticalScrollBar().maximum(), 0,
                               "Con 30 elementos debe activarse el desplazamiento vertical")
        finally:
            combo.hidePopup()


if __name__ == "__main__":
    unittest.main()
