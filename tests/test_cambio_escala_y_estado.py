"""Encargo 9 del rediseño: el cambio de escala (maximizada <-> media pantalla) deja el dibujo en su sitio final en el mismo pintado, y el
texto de estado de una acción suelta sigue al estado de la selección."""
import unittest
from time import perf_counter

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QPointF, QSettings
    from PySide6.QtCore import Qt
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
            self.asentar_escala(w)  # (la escala se aplica al acabar la ráfaga: P-IMP-145)
            self.assertEqual(w._escala, escala)
            self.assertLess(dur, 3.0, "el cambio de escala tarda demasiado")
            final = self._firma(w)
            reloj = QElapsedTimer()
            reloj.start()
            while reloj.elapsed() < 500:
                QApplication.processEvents()
                self.assertEqual(self._firma(w), final, f"el dibujo se movió después del cambio a {ancho} px")

    def test_SRED33_una_rafaga_de_cambios_de_tamano_reaplica_la_escala_una_sola_vez(self):
        """REQ-EDT-09: varios `resize` seguidos que cruzan el umbral de escala (Aero Snap) cambian la escala una sola vez, al final de la
        ráfaga; mientras tanto se conserva la anterior y el dibujo no se mueve (anclado en cada `resizeEvent`), ni durante ni después."""
        from unittest import mock
        w, e = self.vacio()
        w.resize(2000, 1250)
        w.show()
        self.cadena(e)
        for _ in range(10):
            QApplication.processEvents()
        self.assertEqual(w._escala, "grande")
        self.pasar_arranque(w)  # (el primer instante tras mostrarse se aplica sin esperas)
        self.assertFalse(w._arrancando)
        original = type(w)._cambiar_escala
        with mock.patch.object(type(w), "_cambiar_escala", autospec=True, side_effect=original) as cambio:
            d = w.diagrama
            antes = d.viewport().mapTo(w, d.mapFromScene(0, 0)).toTuple()
            for ancho in (1300, 1900, 1200, 1800, 1100, 1000):
                w.resize(ancho, 1250)
                QApplication.processEvents()
                self.assertEqual(w._escala, "grande", "durante la ráfaga se conserva la escala anterior")
                self.assertEqual(cambio.call_count, 0)
            self.assertTrue(w._espera_escala.isActive())
            self.asentar_escala(w)
            self.assertEqual(w._escala, "normal")
            self.assertEqual(cambio.call_count, 1, "la escala se reaplica una sola vez por ráfaga")
            fin = w.diagrama.viewport().mapTo(w, w.diagrama.mapFromScene(0, 0)).toTuple()
            reloj = QElapsedTimer()
            reloj.start()
            while reloj.elapsed() < 500:
                QApplication.processEvents()
                self.assertEqual(w.diagrama.viewport().mapTo(w, w.diagrama.mapFromScene(0, 0)).toTuple(), fin)
            self.assertEqual(
                d.viewport().mapTo(w, d.mapFromScene(0, 0)).toTuple(), antes,
                "el dibujo sigue anclado en la ventana tras la ráfaga",
            )
        w.resize(1000, 1250)
        w.resize(1000, 1260)
        self.assertFalse(w._espera_escala.isActive(), "sin cruzar el umbral no queda nada pendiente")

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


    def test_SRED34_al_arrancar_la_unica_ventana_que_se_muestra_es_la_principal_maximizada(self):
        """REQ-EDT-09: durante el arranque (`ventana.main`) solo recibe `Show` la ventana principal, que se pide maximizada y transparente hasta
        entonces (en Windows se veía un instante con su tamaño normal), y al final queda opaca; ningún auxiliar sin padre se muestra."""
        import tempfile
        from pathlib import Path
        from unittest import mock
        from escritorio import carpetas, errores, ventana

        mostradas = []

        class Filtro(QObject):
            def eventFilter(self, o, ev):  # noqa: N802
                if ev.type() == QEvent.Type.Show and o.isWidgetType() and o.isWindow():
                    mostradas.append((type(o).__name__, o.windowOpacity(), bool(o.windowState() & Qt.WindowState.WindowMaximized)))
                return False

        def bucle(app):
            reloj = QElapsedTimer()
            reloj.start()
            while reloj.elapsed() < 700:
                QApplication.processEvents()
            return 0

        class Ajustes(QSettings):  # (sin tocar los ajustes del usuario)
            def __init__(self, *a):
                super().__init__(ini, QSettings.Format.IniFormat)

        with tempfile.TemporaryDirectory() as tmp:
            ini = str(Path(tmp) / "a.ini")
            filtro = Filtro()
            self.app.installEventFilter(filtro)
            try:
                with mock.patch.object(ventana, "QSettings", Ajustes),                         mock.patch.object(carpetas, "asegurar_carpetas", lambda: None),                         mock.patch.object(errores, "instalar", lambda: None),                         mock.patch.object(ventana.QApplication, "exec", bucle),                         mock.patch.dict("os.environ", {"GRAFCONNECT_SIN_ACTUALIZAR": "1"}):
                    self.assertEqual(ventana.main([]), 0)
            finally:
                self.app.removeEventFilter(filtro)
                for w in self.app.topLevelWidgets():
                    if type(w).__name__ == "Ventana" and w is not self.w:
                        w.edicion = None
                        w.hide()
                        w.deleteLater()
        self.assertEqual([m[0] for m in mostradas], ["Ventana"], mostradas)
        self.assertEqual(mostradas[0][1:], (0.0, True), "se muestra maximizada y todavía transparente")


if __name__ == "__main__":
    unittest.main()
