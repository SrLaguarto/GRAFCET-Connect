"""Pruebas unitarias y de interfaz de la tanda F1 (Planos: fallos y mejoras rápidas)."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from grafcet.laminas import ajustes_lamina
from test_editor_cadenas import BaseQt, QT
from test_laminas import paginas_pdf

if QT:
    from PySide6.QtCore import QEvent, QPoint, Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.carpetas import predeterminada
    from escritorio.laminas import DocumentoHoja, DocumentoLaminas
    from escritorio.plantillas import pintar_texto


@unittest.skipUnless(QT, "requiere PySide6")
class PruebasF1Planos(BaseQt):
    def setUp(self):
        self.docs = tempfile.TemporaryDirectory()
        self.rutas = patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=self.docs.name)
        self.rutas.start()
        super().setUp()

    def tearDown(self):
        self.w.panel_planos.guardar_timer.stop()
        self.w.panel_planos.deshacer_hoja_timer.stop()
        self.w.hide()
        super().tearDown()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.rutas.stop()
        self.docs.cleanup()

    def _preparar(self, tam=(1366, 768)):
        w, e = self.vacio()
        s = e.ed.add_step("g", "1", True)
        e.cambia()
        e.sel = [s]
        e.ed.dirty = False
        w.resize(*tam)
        w.show()
        QApplication.processEvents()
        return w, e, s

    def _crear_hoja(self, e, refs=None, formato="A4", orientacion="vertical", nombre=None):
        cfg = ajustes_lamina({
            "formato": formato,
            "orientacion": orientacion,
            "plantilla": predeterminada(formato, orientacion),
        })
        ident = e.ed.add_plan_page(None, cfg, nombre)
        if refs:
            e.ed.set_page_graphics(ident, [{"refs": refs, "porcentaje": 100., "offset_mm": [0., 0.]}])
        return ident

    def _ir_planos(self):
        self.w._mostrar_pagina("planos")
        QApplication.processEvents()
        return self.w.panel_planos

    def _punto_mm(self, vista, x, y):
        d = vista.documento
        k = min((vista.width() - 24) / d.ancho, (vista.height() - 24) / d.alto)
        return QPoint(
            round((vista.width() - d.ancho * k) / 2 + x * k),
            round((vista.height() - d.alto * k) / 2 + y * k),
        )

    def test_SF1_01_menu_mas_activo_y_centrar_en_media_pantalla(self):
        """REQ-EDT-11, REQ-UX-01: a media pantalla «Más» está habilitado y «Centrar» sin prefijo."""
        w, e, s = self._preparar(tam=(960, 1040))
        self._crear_hoja(e, [s])
        p = self._ir_planos()
        self.assertTrue(p.compacto)
        self.assertEqual(p.a_centrar.text(), "Centrar")
        self.assertEqual(p.editor.b_centrar.text(), "Centrar")
        p.controles._rellenar_mas()
        copias = p.controles.menu_mas.actions()
        self.assertEqual([a.text() for a in copias], ["Centrar", "Añadir texto", "Exportar…", "Imprimir…"])
        self.assertTrue(all(a.isEnabled() for a in copias))
        p.colocar([10.0, 15.0])
        copias[0].trigger()
        d = p.editor.documento
        centro_graf = d.capas[0].destino(0).center()
        self.assertLess((centro_graf - d.capas[0].contenido.center()).manhattanLength(), 0.01)

    def test_SF1_02_escala_se_en_cajetin_y_personalizada_respetada(self):
        """REQ-EDT-11: un esquema GRAFCET muestra «S/E» por defecto, salvo texto explícito en el campo Escala."""
        w, e, s = self._preparar()
        doc_limpio = DocumentoLaminas(self.w.edicion.M, {}, {"modo": "escala", "unidad_mm": 1., "escala": 4 / 3})
        self.assertEqual(doc_limpio.escala_rotulo, "S/E")
        hoja = DocumentoHoja(
            {
                "_graficos": [
                    {"refs": [s], "porcentaje": 75., "offset_mm": [0., 0.], "modelo": self.w.edicion.M},
                    {"refs": [s], "porcentaje": 150., "offset_mm": [40., 0.], "modelo": self.w.edicion.M},
                ],
                "_numero_hoja": 1,
                "_total_hojas": 1,
            },
            {},
            ajustes_lamina(),
        )
        self.assertEqual(hoja.escala_rotulo, "S/E")
        self.assertEqual(hoja.campos(0)["escala"], "S/E")
        hoja_manual = DocumentoHoja(
            {"_graficos": [], "_numero_hoja": 1, "_total_hojas": 1},
            {},
            ajustes_lamina({"campos": {"escala": "1:2"}}),
        )
        self.assertEqual(hoja_manual.escala_rotulo, "1:2")

    def test_SF1_03_recuadro_seleccion_texto_centrado_en_tinta(self):
        """REQ-EDT-11: la caja de selección del texto rodea las letras centrada verticalmente sin subirse."""
        w, e, s = self._preparar()
        self._crear_hoja(e)
        p = self._ir_planos()
        t = p.editor.editor_textos
        for anclaje in ("top", "middle", "bottom", "baseline"):
            with self.subTest(anclaje=anclaje):
                dato = {
                    "kind": "text",
                    "text": "Nombre",
                    "x": 20.,
                    "y": 20.,
                    "height": 4.,
                    "rotation": 0.,
                    "align": "left",
                    "valign": anclaje,
                    "font": "Arial",
                    "color": "#000000",
                }
                t.insertar_texto(dato)
                item = t.actual
                caja = item.boundingRect()
                img = QImage(300, 300, QImage.Format.Format_RGB32)
                img.fill(QColor("white"))
                pintor = QPainter(img)
                pintor.translate(100, 100)
                pintor.scale(10, 10)
                pintar_texto(pintor, {**dato, "x": 0., "y": 0.}, "Nombre")
                pintor.end()
                ys = [yy / 10 - 10 for yy in range(300) for xx in range(300) if img.pixelColor(xx, yy).red() < 200]
                self.assertTrue(ys)
                centro_tinta = (min(ys) + max(ys)) / 2
                self.assertAlmostEqual(caja.center().y(), centro_tinta, delta=0.25)

    def test_SF1_04_borrar_grafcet_sin_reconstruir_editor_ni_parpadeo(self):
        """REQ-EDT-11: eliminar un GRAFCET con Supr mantiene editor, vista y zoom sin reconstruir la página."""
        w, e, s = self._preparar()
        self._crear_hoja(e, [s])
        p = self._ir_planos()
        p.zoom_combo.setCurrentIndex(p.zoom_combo.findData(1.25))
        QApplication.processEvents()
        editor_antes = p.editor
        vista_antes = p.editor.vista
        d = p.editor.documento
        r = d.capas[0].destino(0)
        punto = self._punto_mm(vista_antes, r.center().x(), r.center().y())
        QTest.mouseClick(vista_antes, Qt.MouseButton.LeftButton, pos=punto)
        self.assertTrue(vista_antes.seleccionado)
        vista_antes.setFocus()
        QTest.keyClick(vista_antes, Qt.Key.Key_Delete)
        self.assertIs(p.editor, editor_antes)
        self.assertIs(p.editor.vista, vista_antes)
        self.assertFalse(p.graficos)
        self.assertFalse(vista_antes.seleccionado)
        self.assertAlmostEqual(p.factor_zoom, 1.25)
        w.a_deshacer.trigger()
        self.assertEqual(len(p.graficos), 1)

    def test_SF1_05_consolas_giros_cuatro_y_posicion_explicita(self):
        """REQ-EDT-11, REQ-UX-01: texto en Consolas, giros 0/90/180/270° y origen (0, 0) visible."""
        from test_auditoria_maquetacion import REGLAS
        w, e, s = self._preparar()
        self._crear_hoja(e)
        p = self._ir_planos()
        p.a_texto.trigger()
        v = p.editor.vista
        QTest.mouseClick(v, Qt.MouseButton.LeftButton, pos=self._punto_mm(v, 40, 60))
        t = p.editor.editor_textos
        self.assertEqual(t.actual.t["font"], "Consolas")
        self.assertEqual([t.giro.itemData(i) for i in range(4)], [0., 90., 180., 270.])
        t.giro.setCurrentIndex(t.giro.findData(180.))
        self.assertEqual(t.actual.t["rotation"], 180.)
        t.giro.setCurrentIndex(t.giro.findData(270.))
        self.assertEqual(t.actual.t["rotation"], 270.)
        self.assertEqual(t.posicion_titulo.text(), "Posición del texto (mm)")
        self.assertIn("esquina superior izquierda", t.posicion_origen.text())
        self.assertIn("(0, 0)", t.posicion_origen.text())
        QApplication.processEvents()
        self.assertEqual(t.panel_propiedades.horizontalScrollBar().maximum(), 0)
        for regla in ("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C4"):
            self.assertEqual(REGLAS[regla](t.panel_propiedades), [], regla)

    def test_SF1_06_hoja_nueva_hereda_formato_sin_dialogo(self):
        """REQ-EDT-11: crear hoja no abre diálogo y hereda formato, orientación y plantilla de la activa."""
        w, e, s = self._preparar()
        p = self._ir_planos()
        p.vacio.b_crear_primera.click()
        QApplication.processEvents()
        self.assertIsNone(QApplication.activeModalWidget())
        self.assertEqual(p.lista.count(), 1)
        self.assertEqual((p.editor.formato.currentText(), p.editor.orientacion.currentData()), ("A4", "vertical"))
        p.editor.formato.setCurrentText("A3")
        p.editor.orientacion.setCurrentIndex(p.editor.orientacion.findData("horizontal"))
        QApplication.processEvents()
        p.b_hoja.click()
        QApplication.processEvents()
        self.assertIsNone(QApplication.activeModalWidget())
        self.assertEqual(p.lista.count(), 2)
        self.assertEqual((p.editor.formato.currentText(), p.editor.orientacion.currentData()), ("A3", "horizontal"))
        p.editor.a_quitar_plantilla.trigger()
        p.b_hoja.click()
        QApplication.processEvents()
        self.assertEqual(p.lista.count(), 3)
        self.assertEqual(p.editor.plantilla["source"], "Hoja sin plantilla")
        self.assertEqual(p.editor.plantilla["size"], [420., 297.])

    def test_SF1_07_borrar_hoja_muestra_barra_deshacer_y_recupera(self):
        """REQ-EDT-05, REQ-EDT-11: borrar una hoja muestra «Deshacer» no modal y recupera la hoja al pulsarlo."""
        w, e, s = self._preparar()
        h1 = self._crear_hoja(e, [s], nombre="Principal")
        self._crear_hoja(e, nombre="Auxiliar")
        p = self._ir_planos()
        p.lista.setCurrentRow(0)
        p.eliminar_hoja()
        QApplication.processEvents()
        self.assertTrue(p.aviso_deshacer_hoja.isVisible())
        self.assertIn("Principal", p.l_deshacer_hoja.text())
        self.assertEqual(p.lista.count(), 1)
        p.b_deshacer_hoja.click()
        QApplication.processEvents()
        self.assertFalse(p.aviso_deshacer_hoja.isVisible())
        self.assertEqual(p.lista.count(), 2)
        self.assertEqual(e.ed.sheet_links()[0]["id"], h1)
        p.lista.setCurrentRow(1)
        p.eliminar_hoja()
        p.lista.setCurrentRow(0)
        p.eliminar_hoja()
        self.assertEqual(p.lista.count(), 0)
        self.assertTrue(p.aviso_deshacer_hoja.isVisible())
        p.b_deshacer_hoja.click()
        self.assertEqual(p.lista.count(), 1)

    def test_SF1_08_exportar_pdf_todas_hojas_hoja_suelta_y_plural(self):
        """REQ-EDT-11: PDF multipágina con todas las hojas (tamaños propios), hoja suelta y singular correcto."""
        w, e, s = self._preparar()
        self._crear_hoja(e, [s], "A4", "vertical", "Primera")
        self._crear_hoja(e, [s], "A3", "horizontal", "Segunda")
        self._crear_hoja(e, None, "A4", "vertical", "Tercera")
        p = self._ir_planos()
        p.lista.setCurrentRow(1)
        QApplication.processEvents()
        ruta_todas = Path(self.docs.name) / "todas.pdf"
        with patch(
            "escritorio.laminas.QFileDialog.getSaveFileName",
            return_value=(str(ruta_todas), "Documento PDF — todas las hojas (*.pdf)"),
        ):
            p.a_exportar.trigger()
        total, cajas = paginas_pdf(ruta_todas)
        self.assertEqual(total, 3)
        self.assertAlmostEqual(cajas[0][0], 210 * 72 / 25.4, delta=0.6)
        self.assertAlmostEqual(cajas[1][0], 420 * 72 / 25.4, delta=0.6)
        self.assertAlmostEqual(cajas[2][0], 210 * 72 / 25.4, delta=0.6)
        self.assertIn("Exportadas 3 hojas en", p.editor.error.text())
        ruta_una = Path(self.docs.name) / "una.pdf"
        with patch(
            "escritorio.laminas.QFileDialog.getSaveFileName",
            return_value=(str(ruta_una), "Documento PDF — hoja actual (*.pdf)"),
        ):
            p.a_exportar.trigger()
        total_una, cajas_una = paginas_pdf(ruta_una)
        self.assertEqual(total_una, 1)
        self.assertAlmostEqual(cajas_una[0][0], 420 * 72 / 25.4, delta=0.6)
        self.assertIn("Exportada 1 hoja en", p.editor.error.text())
        self.assertNotIn("1 hojas", p.editor.error.text())

    def _plantilla_pdf_importada(self):
        return {
            "version": 1,
            "size": [210., 297.],
            "source": "PDF",
            "primitives": [
                {
                    "kind": "text",
                    "text": "Rótulo importado",
                    "x": 30.,
                    "y": 50.,
                    "height": 4.,
                    "rotation": 0.,
                    "align": "left",
                    "valign": "top",
                    "font": "Arial",
                    "color": "#000000",
                }
            ],
        }

    def test_SF1_09_portapapeles_ctrl_menu_derecho_importados_y_deshacer(self):
        """REQ-EDT-05, REQ-EDT-11: copiar, cortar, pegar y eliminar textos (también importados) y deshacer."""
        w, e, s = self._preparar()
        self._crear_hoja(e, nombre="Hoja 1")
        h2 = self._crear_hoja(e, nombre="Hoja 2")
        p = self._ir_planos()
        p.editor.establecer_plantilla(self._plantilla_pdf_importada())
        p.aplicar()
        QApplication.processEvents()
        v = p.editor.vista
        t = p.editor.editor_textos
        menu = p.crear_menu_lienzo(self._punto_mm(v, 34, 52))
        self.assertIsNotNone(menu)
        acciones = {a.text(): a for a in menu.actions() if not a.isSeparator()}
        self.assertEqual(list(acciones), ["Cortar", "Copiar", "Pegar", "Eliminar"])
        self.assertTrue(acciones["Copiar"].isEnabled())
        self.assertFalse(acciones["Pegar"].isEnabled())
        acciones["Copiar"].trigger()
        self.assertTrue(w.a_pegar.isEnabled())
        v.setFocus()
        QTest.keyClick(v, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        self.assertEqual(len(t.items), 2)
        self.assertEqual(t.actual.t["text"], "Rótulo importado")
        t.contenido.setFocus()
        QApplication.processEvents()
        self.assertFalse(w.a_copiar.isEnabled())
        v.setFocus()
        QApplication.processEvents()
        QTest.keyClick(v, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        self.assertEqual(len(t.items), 1)
        p.mostrar(h2)
        QApplication.processEvents()
        p.editor.vista.setFocus()
        QTest.keyClick(p.editor.vista, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        self.assertTrue(any(i.t["text"] == "Rótulo importado" for i in p.editor.editor_textos.items))
        w.a_deshacer.trigger()
        QApplication.processEvents()
        self.assertFalse(any(i.t["text"] == "Rótulo importado" for i in p.editor.editor_textos.items))
        w.a_rehacer.trigger()
        QApplication.processEvents()
        self.assertTrue(any(i.t["text"] == "Rótulo importado" for i in p.editor.editor_textos.items))

    def test_SF1_10_doble_clic_enfoca_contenido_seleccionado(self):
        """REQ-EDT-11: doble clic sobre un texto lleva el foco a Contenido con todo su texto seleccionado."""
        w, e, s = self._preparar()
        self._crear_hoja(e)
        p = self._ir_planos()
        p.editor.a_quitar_plantilla.trigger()
        p.a_texto.trigger()
        v = p.editor.vista
        QTest.mouseClick(v, Qt.MouseButton.LeftButton, pos=self._punto_mm(v, 50, 70))
        t = p.editor.editor_textos
        t.contenido.setPlainText("Motor principal")
        v.setFocus()
        QApplication.processEvents()
        centro = t.actual.sceneBoundingRect().center()
        QTest.mouseDClick(v, Qt.MouseButton.LeftButton, pos=self._punto_mm(v, centro.x(), centro.y()))
        QApplication.processEvents()
        self.assertTrue(t.contenido.hasFocus())
        self.assertEqual(t.contenido.textCursor().selectedText(), "Motor principal")

    def test_SF1_11_flechas_1mm_10mm_y_escape_deselecciona(self):
        """REQ-EDT-11: flechas mueven 1 mm (10 mm con Mayús) y Esc deselecciona textos, GRAFCET y modo texto."""
        w, e, s = self._preparar()
        self._crear_hoja(e, [s])
        p = self._ir_planos()
        p.a_texto.trigger()
        v = p.editor.vista
        QTest.mouseClick(v, Qt.MouseButton.LeftButton, pos=self._punto_mm(v, 50, 70))
        t = p.editor.editor_textos
        x0, y0 = t.actual.t["x"], t.actual.t["y"]
        v.setFocus()
        QTest.keyClick(v, Qt.Key.Key_Right)
        QTest.keyClick(v, Qt.Key.Key_Down)
        self.assertAlmostEqual(t.actual.t["x"], x0 + 1.0, delta=0.01)
        self.assertAlmostEqual(t.actual.t["y"], y0 + 1.0, delta=0.01)
        QTest.keyClick(v, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
        QTest.keyClick(v, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
        self.assertAlmostEqual(t.actual.t["x"], x0 - 9.0, delta=0.01)
        self.assertAlmostEqual(t.actual.t["y"], y0 - 9.0, delta=0.01)
        QTest.keyClick(v, Qt.Key.Key_Escape)
        self.assertIsNone(t.actual)
        self.assertEqual(p.editor.propiedades.currentIndex(), 0)
        p.a_texto.trigger()
        self.assertTrue(v.nuevo_texto)
        QTest.keyClick(v, Qt.Key.Key_Escape)
        self.assertFalse(v.nuevo_texto)

    def test_SF1_12_enlazado_cajetin_conserva_enlace_al_mover_xy(self):
        """REQ-EDT-11: mover X/Y de un texto enlazado al cajetín mantiene la actualización del campo."""
        w, e, s = self._preparar()
        self._crear_hoja(e)
        p = self._ir_planos()
        d = p.editor
        d.campos["titulo"].setText("Título inicial")
        t = d.editor_textos
        indice_titulo = next(i for i, item in enumerate(t.items) if item.t.get("field") == "titulo")
        t.elegir(indice_titulo)
        t.x.setValue(t.x.value() + 2.0)
        t.y.setValue(t.y.value() + 1.0)
        self.assertEqual(t.actual.t.get("field"), "titulo")
        d.vista.setFocus()
        QTest.keyClick(d.vista, Qt.Key.Key_Right)
        self.assertEqual(t.actual.t.get("field"), "titulo")
        d.campos["titulo"].setText("Título actualizado")
        self.assertEqual(t.contenido.toPlainText(), "Título actualizado")
        self.assertEqual(d.documento.campos(0)["titulo"], "Título actualizado")
        t.contenido.setPlainText("Título manual")
        self.assertFalse(t.actual.t.get("field"))


if __name__ == "__main__":
    unittest.main()
