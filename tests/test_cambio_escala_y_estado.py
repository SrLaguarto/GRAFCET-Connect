"""Encargo 9 del rediseño: el cambio de escala (maximizada <-> media pantalla) deja el dibujo en su sitio final en el mismo pintado, y el
texto de estado de una acción suelta sigue al estado de la selección."""
import unittest
from time import perf_counter

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QElapsedTimer, QPointF
    from PySide6.QtWidgets import QApplication


@unittest.skipUnless(QT, "requiere PySide6")
class CambioEscalaYEstado(BaseQt):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.w.hide)

    def _firma(self, w):
        d = w.diagrama
        return (d.viewport().mapTo(w, d.mapFromScene(0, 0)).toTuple(), d.viewport().mapTo(w, d.viewport().rect().topLeft()).toTuple(),
                d.size().toTuple(), round(d.escala(), 4), w.dock.width(), w.derecho.width())

    def test_SRED31_el_cambio_de_escala_no_deja_nada_pendiente_que_mueva_el_dibujo(self):
        """REQ-EDT-09: al pasar de 2000×1250 a 1000×1250 y vuelta (cruza el umbral de escala) el dibujo queda en su sitio final al volver
        `resize`; durante 500 ms de eventos ni se mueve ni cambia de tamaño, y el cambio tarda poco (tope amplio, medido en offscreen)."""
        w, e = self.vacio()
        w.resize(2000, 1250)
        w.show()
        self.cadena(e)
        for _ in range(10):
            QApplication.processEvents()
        for ancho, escala in ((1000, "normal"), (2000, "grande"), (1000, "normal"), (2000, "grande")):
            t = perf_counter()
            w.resize(ancho, 1250)
            dur = perf_counter() - t
            self.assertEqual(w._escala, escala)
            self.assertLess(dur, 3.0, "el cambio de escala tarda demasiado")
            final = self._firma(w)
            reloj = QElapsedTimer()
            reloj.start()
            while reloj.elapsed() < 500:
                QApplication.processEvents()
                self.assertEqual(self._firma(w), final, f"el dibujo se movió después del cambio a {ancho} px")

    def test_SRED32_la_accion_suelta_deja_de_avisar_al_unirla_y_vuelve_al_deshacer(self):
        """REQ-EDT-09: el texto «Acción suelta…» de la barra de estado y de la cabecera se va al unir la acción a una etapa (sigue
        seleccionada) y vuelve con Ctrl+Z; se calcula del estado de ahora, no al cambiar la selección."""
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        ids = self.cadena(e)
        did = e.poner_accion_suelta(QPointF(400, 200))
        QApplication.processEvents()
        self.assertTrue(w.ayuda.text().startswith("Acción suelta"))
        self.assertTrue(w.statusBar().currentMessage().startswith("Acción suelta"))
        e.unir_accion(did, ids[0])
        QApplication.processEvents()
        self.assertFalse(w.ayuda.text().startswith("Acción suelta"), w.ayuda.text())
        self.assertEqual(w.statusBar().currentMessage(), "")
        w.historial_plano(False)  # Ctrl+Z
        QApplication.processEvents()
        self.assertEqual(e.sel, [did])
        self.assertTrue(w.ayuda.text().startswith("Acción suelta"), w.ayuda.text())
        self.assertTrue(w.statusBar().currentMessage().startswith("Acción suelta"))
        w.historial_plano(True)  # Ctrl+Y: otra vez unida
        QApplication.processEvents()
        self.assertEqual(w.statusBar().currentMessage(), "")


if __name__ == "__main__":
    unittest.main()
