"""«Mostrar errores» (decisión del responsable, 12-nov-2026): el aviso de diagnósticos de la cabecera del dibujo no sale por sí solo al editar;
lo gobierna un botón conmutable de la barra de edición, junto a «Mostrar dependencias»."""
import unittest
from unittest import mock

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication


@unittest.skipUnless(QT, "requiere PySide6")
class MostrarErrores(BaseQt):
    def preparar(self, ancho=1366, alto=768):
        w, e = self.vacio()
        e.ed.add_step("g", "1", True, at=(100, 100))
        e.cambia()
        w.resize(ancho, alto)
        w.show()
        self.addCleanup(w.hide)
        self.bombear()
        return w, e

    @staticmethod
    def bombear(n=6):
        for _ in range(n):
            QApplication.processEvents()

    def _error(self, e):
        tid, _ = e.ed.add_transition("g", "", label="t2", at=(100, 200))
        e.cambia()
        self.bombear()
        return tid

    def _corregir(self, e, tid):
        e.seleccionar([tid])
        self.assertTrue(e.borrar())
        self.bombear()

    def _aviso_visible(self, w):
        d = w.diagrama
        return d.resumen_diagnosticos.isVisible() or d.indicador_diagnosticos.isVisible()

    def test_SERR01_marcar_y_desmarcar_muestra_y_oculta_el_aviso_en_vivo(self):
        """REQ-EDT-09: al editar, el aviso no se ve aunque haya errores; con «Mostrar errores» marcado se ve y se actualiza en vivo; con nada que
        avisar dice «Sin errores» (neutro, sin triángulo); desmarcado, se oculta."""
        w, e = self.preparar()
        b = w.b_errores
        self.assertTrue(b.isCheckable() and not b.isChecked())
        self.assertEqual(b.toolTip(), "Mostrar los errores y avisos del grafcet")
        self.assertFalse(b.icon().isNull())
        tid = self._error(e)
        self.assertFalse(self._aviso_visible(w), "sin pedirlo, no sale mientras se edita")
        b.click()
        self.bombear()
        d = w.diagrama
        self.assertTrue(d.indicador_diagnosticos.isVisible() and d.resumen_diagnosticos.isVisible())
        self.assertRegex(d.resumen_diagnosticos.text(), r"[0-9]+ errores?")
        self._corregir(e, tid)  # (se corrige: el aviso se actualiza en vivo)
        self.bombear()
        self.assertTrue(b.isChecked(), "lo marcó el usuario: sigue marcado")
        self.assertEqual(d.resumen_diagnosticos.text(), "Sin errores")
        self.assertFalse(d.indicador_diagnosticos.isVisible(), "sin triángulo")
        e.ed.add_transition("g", "", label="t3", at=(100, 300))
        e.cambia()
        self.bombear()
        self.assertRegex(d.resumen_diagnosticos.text(), r"[0-9]+ errores?")
        b.click()
        self.bombear()
        self.assertFalse(self._aviso_visible(w))

    def test_SERR09_al_marcar_el_boton_la_lista_sale_desplegada_y_el_enlace_la_pliega(self):
        """REQ-EDT-09: al marcar «Mostrar errores» la lista de mensajes aparece desplegada («N errores ▾»); el enlace la pliega; al desmarcar y volver
        a marcar, otra vez desplegada."""
        w, e = self.preparar()
        self._error(e)
        d = w.diagrama
        for _ in range(2):
            w.b_errores.click()
            self.bombear()
            self.assertTrue(d.lista_diagnosticos.isVisible() and d.resumen_diagnosticos.text().endswith("▾"), d.resumen_diagnosticos.text())
            d.resumen_diagnosticos.click()
            self.bombear()
            self.assertFalse(d.lista_diagnosticos.isVisible())
            self.assertTrue(d.resumen_diagnosticos.text().endswith("▸"))
            w.b_errores.click()  # desmarca
            self.bombear()
            self.assertFalse(self._aviso_visible(w))

    def test_SERR02_play_con_errores_no_simula_marca_el_boton_y_despliega_la_lista(self):
        """REQ-EDT-09, REQ-SIM-03: Play con errores que impiden simular no simula, marca el botón y el aviso aparece desplegado con la lista."""
        w, e = self.preparar()
        self._error(e)
        self.assertFalse(w.b_errores.isChecked())
        with mock.patch("escritorio.ventana.QMessageBox.warning"):
            self.assertFalse(w.cambiar_modo("simular"))
        self.bombear()
        self.assertEqual(w.modo, "editar")
        self.assertTrue(w.b_errores.isChecked())
        d = w.diagrama
        self.assertTrue(d.resumen_diagnosticos.isVisible() and d.lista_diagnosticos.isVisible(), "desplegado con la lista")
        self.assertGreaterEqual(d.lista_diagnosticos.count(), 1)

    def test_SERR03_marcado_por_un_play_fallido_se_desmarca_solo_al_corregir_y_el_del_usuario_no(self):
        """REQ-EDT-09: si el botón lo marcó un Play fallido y los errores desaparecen, se desmarca solo y el aviso desaparece; si lo marcó el
        usuario, sigue marcado con «Sin errores»."""
        w, e = self.preparar()
        tid = self._error(e)
        with mock.patch("escritorio.ventana.QMessageBox.warning"):
            w.cambiar_modo("simular")
        self.bombear()
        self.assertTrue(w.b_errores.isChecked())
        self._corregir(e, tid)
        self.bombear()
        self.assertFalse(w.b_errores.isChecked(), "se desmarca solo")
        self.assertFalse(self._aviso_visible(w))
        # marcado por el usuario antes del Play fallido: sigue suyo
        w.b_errores.click()
        tid2, _ = e.ed.add_transition("g", "", label="t4", at=(100, 300))
        e.cambia()
        self.bombear()
        with mock.patch("escritorio.ventana.QMessageBox.warning"):
            w.cambiar_modo("simular")
        self.bombear()
        self._corregir(e, tid2)
        self.bombear()
        self.assertTrue(w.b_errores.isChecked())
        self.assertEqual(w.diagrama.resumen_diagnosticos.text(), "Sin errores")

    def test_SERR04_al_simular_el_boton_esta_desactivado_y_el_aviso_se_oculta(self):
        """REQ-EDT-09: al simular, el botón queda desactivado como los demás de edición, el aviso de edición no se ve, y al volver a editar el botón
        recupera su estado."""
        w, e = self.preparar()
        w.b_errores.click()
        self.bombear()
        self.assertTrue(w.b_errores.isEnabled())
        self.assertTrue(w.cambiar_modo("simular"))
        self.bombear()
        self.assertFalse(w.b_errores.isEnabled())
        self.assertTrue(w.b_errores.isChecked())
        self.assertFalse(self._aviso_visible(w))
        w.cambiar_modo("editar")
        self.bombear()
        self.assertTrue(w.b_errores.isEnabled() and w.b_errores.isChecked())
        self.assertEqual(w.diagrama.resumen_diagnosticos.text(), "Sin errores")

    def test_SERR05_el_boton_cabe_a_1366_y_oculta_el_texto_antes_que_el_boton(self):
        """REQ-EDT-11: a 1366×768 la barra de edición cabe en su fila con el botón (con su texto, o solo con icono si no hay sitio) y a 1000×600
        y 800×600 el botón sigue entero y visible (se oculta antes el texto)."""
        for ancho, alto in ((1366, 768), (1000, 600), (800, 600)):
            w, e = self.preparar(ancho, alto)
            wd = w.tb_edit.widgetForAction(w.a_errores)
            self.assertTrue(wd.isVisible(), (ancho, alto))
            self.assertTrue(w.tb_edit.rect().contains(wd.geometry()), (ancho, alto, wd.geometry(), w.tb_edit.rect()))
            self.assertLessEqual(w.tb_sim.width() + w.tb_edit.sizeHint().width(), w.herramientas_grafcet.width(), (ancho, alto))
            w.hide()

    def test_SERR06_el_zoom_y_el_aviso_no_se_solapan_a_ningun_tamaño(self):
        """REQ-EDT-09: con el aviso visible, el recuadro del zoom (en la cabecera o flotando sobre el dibujo) y el aviso (triángulo, resumen y lista)
        no se pisan a 960×1032, 1000×1250, 1366×768 y 2000×1250, con la lista plegada y desplegada."""
        from PySide6.QtCore import QRect
        for ancho, alto in ((960, 1032), (1000, 1250), (1366, 768), (2000, 1250)):
            w, e = self.preparar(ancho, alto)
            self._error(e)
            w.b_errores.setChecked(True)
            d = w.diagrama
            for abierta in (False, True):
                d.desplegar_diagnosticos(abierta)
                self.bombear()
                zoom = QRect(d.barra.mapTo(w, d.barra.rect().topLeft()), d.barra.size())
                for x in (d.indicador_diagnosticos, d.resumen_diagnosticos, *([d.lista_diagnosticos] if abierta else [])):
                    caja = QRect(x.mapTo(w, x.rect().topLeft()), x.size())
                    self.assertFalse(zoom.intersects(caja), (ancho, alto, abierta, x.objectName(), zoom, caja))
            w.hide()

    def test_SERR07_la_ayuda_del_dibujo_es_siempre_el_boton_ayuda_salvo_un_mensaje_de_error(self):
        """REQ-EDT-09: a todos los tamaños la ayuda habitual de la cabecera es el botón «Ayuda ▾» (no el texto largo); pulsarlo la despliega
        entera («Ayuda ▴») y otra vez la recoge; un mensaje de error (en rojo) sí se lee en la fila."""
        from escritorio import estilo
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            w, e = self.preparar(ancho, alto)
            self.assertTrue(w.b_ayuda.isVisible() and w.b_ayuda.text() == "Ayuda ▾", (ancho, w.b_ayuda.text()))
            self.assertFalse(w.ayuda.mostrar_texto)
            w.b_ayuda.click()
            self.bombear()
            self.assertEqual(w.b_ayuda.text(), "Ayuda ▴")
            self.assertTrue(w.ayuda_larga.isVisible())
            w.b_ayuda.click()
            self.bombear()
            self.assertFalse(w.ayuda_larga.isVisible())
            e.rechazar("Mensaje de error de prueba")
            e.cambiado.emit()
            self.bombear()
            self.assertIn(estilo.ERROR, w.ayuda.styleSheet())
            self.assertTrue(w.ayuda.mostrar_texto or w.b_ayuda.text() == "Ayuda ▾", (ancho, "el error se lee o queda tras el botón con sitio justo"))
            w.hide()

    def test_SERR08_el_resumen_de_incidencias_es_un_enlace_sin_recuadro_ni_fondo(self):
        """REQ-EDT-09: «N errores ▸» no lleva recuadro ni fondo (ni con el puntero encima ni pulsado), su texto es rojo con errores y ámbar con solo
        avisos, el cursor es una mano y con Tab conserva el anillo de foco."""
        from PySide6.QtCore import Qt
        from escritorio import estilo
        w, e = self.preparar()
        self._error(e)
        w.b_errores.setChecked(True)
        self.bombear()
        b = w.diagrama.resumen_diagnosticos
        hoja = b.styleSheet()
        self.assertIn("border:0", hoja)
        self.assertIn(estilo.ERROR, hoja)
        self.assertEqual(hoja.count("background:transparent"), 2, "ni en reposo ni con el puntero encima ni pulsado")
        self.assertIn('[tecl="true"]:focus', hoja)
        self.assertEqual(b.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        w.diagrama.actualizar_diagnosticos(True, "1 aviso")
        self.assertIn(estilo.AVISO, b.styleSheet())


if __name__ == "__main__":
    unittest.main()
