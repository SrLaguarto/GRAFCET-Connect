"""Gestos reales de pulsadores y controles de ejecución del simulador."""
import copy
import unittest
from unittest import mock
from test_editor_cadenas import BaseQt, QT
from helpers import records

if QT:
    from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication


@unittest.skipUnless(QT, "PySide6 no está instalado")
class PulsadoresYControl(BaseQt):
    def preparar(self):
        w, e = self.vacio()
        p = e.ed.add_variable("p", "input", {"kind": "bool"})
        q = e.ed.add_variable("q", "input", {"kind": "bool"})
        a = e.ed.add_step("g", "1", True, at=(100, 80))
        b = e.ed.add_step("g", "2", at=(100, 240))
        arriba, _ = e.ed.add_transition("g", "p", pre=[a], post=[b], label="t1", at=(100, 160))
        abajo, _ = e.ed.add_transition("g", "NOT p", pre=[b], post=[a], label="t2", at=(100, 320))
        e.cambia(); w.resize(1366, 768); w.show(); QApplication.processEvents()
        w.a_ejecutar.setChecked(True); w.rt.stop(); QApplication.processEvents()
        return w, p, q, a, b, arriba, abajo

    def valores(self, w):
        return w.v.state()["values"]

    def contexto(self, boton, texto):
        visto = []
        def elegir():
            menu = QApplication.activePopupWidget()
            visto.extend(a.text() for a in menu.actions())
            next(a for a in menu.actions() if a.text() == texto).trigger()
            menu.close()
        QTimer.singleShot(0, elegir)
        centro = boton.rect().center()
        QApplication.sendEvent(boton, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, centro, boton.mapToGlobal(centro)))
        self.assertEqual(visto, ["Convertir en interruptor", "Convertir en pulsador", "", "Normalmente abierto (NA)", "Normalmente cerrado (NC)"])

    def test_SPUL01_presionar_y_soltar_producen_dos_cambios_y_evoluciones(self):
        """REQ-SIM-02, REQ-SIM-03: el pulsador da 1 al presionar y 0 al soltar, procesando ambas evoluciones."""
        w, p, q, a, b, subida, bajada = self.preparar()
        boton = w.botones[p]
        self.assertFalse(boton.interruptor)
        QTest.mousePress(boton, Qt.MouseButton.LeftButton)
        self.assertIs(self.valores(w)[p], True); self.assertTrue(boton.isChecked())
        self.assertEqual(w.v.state()["situation"], [b])
        QTest.mouseRelease(boton, Qt.MouseButton.LeftButton)
        self.assertIs(self.valores(w)[p], False); self.assertFalse(boton.isChecked())
        self.assertEqual(w.v.state()["situation"], [a])
        cleared = [r["cleared"] for r in records(w.v.s, "evolucion") if r["cleared"]]
        self.assertEqual(cleared, [[subida], [bajada]])

    def test_SPUL02_ctrl_enclava_y_otro_clic_libera_sin_perder_otras_entradas(self):
        """REQ-SIM-02: Ctrl+clic mantiene varias entradas y permite pulsar otras; el siguiente clic libera."""
        w, p, q, *_ = self.preparar()
        QTest.mouseClick(w.botones[p], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
        self.assertIs(self.valores(w)[p], True); self.assertTrue(w.botones[p].isChecked())
        QTest.mousePress(w.botones[q], Qt.MouseButton.LeftButton)
        self.assertTrue(self.valores(w)[p] and self.valores(w)[q])
        QTest.mouseRelease(w.botones[q], Qt.MouseButton.LeftButton)
        self.assertTrue(self.valores(w)[p]); self.assertFalse(self.valores(w)[q])
        QTest.mouseClick(w.botones[q], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self.valores(w)[p] and self.valores(w)[q])
        QTest.mouseClick(w.botones[p], Qt.MouseButton.LeftButton)
        self.assertFalse(self.valores(w)[p]); self.assertTrue(self.valores(w)[q])
        QTest.mouseClick(w.botones[q], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(self.valores(w)[q])

    def test_SPUL03_menu_cambia_tipo_y_lo_recuerda_sin_guardarlo(self):
        """REQ-SIM-02, REQ-DAT-01: el tipo de entrada se cambia en menú y dura la sesión sin entrar en los documentos."""
        w, p, q, *_ = self.preparar()
        e = w.edicion
        antes = copy.deepcopy((e.ed.model, e.ed.presentation))
        self.contexto(w.botones[p], "Convertir en interruptor")
        self.assertEqual((e.ed.model, e.ed.presentation), antes)
        QTest.mousePress(w.botones[p], Qt.MouseButton.LeftButton)
        self.assertFalse(self.valores(w)[p], "el interruptor espera a completar el clic")
        QTest.mouseRelease(w.botones[p], Qt.MouseButton.LeftButton)
        self.assertTrue(self.valores(w)[p])
        QTest.mouseClick(w.botones[p], Qt.MouseButton.LeftButton)
        self.assertFalse(self.valores(w)[p])
        w.reiniciar(); w.rt.stop()
        self.assertTrue(w.botones[p].interruptor)
        w.a_ejecutar.setChecked(False); w.a_ejecutar.setChecked(True); w.rt.stop()
        self.assertTrue(w.botones[p].interruptor)
        self.contexto(w.botones[p], "Convertir en pulsador")
        QTest.mouseClick(w.botones[p], Qt.MouseButton.LeftButton)
        self.assertFalse(self.valores(w)[p]); self.assertFalse(w.botones[p].interruptor)
        self.assertFalse(w.botones[q].interruptor)

    def test_SPUL04_conexion_externa_no_admite_cambios_manuales(self):
        """REQ-SIM-02, REQ-SIM-03: las entradas conectadas siguen perteneciendo exclusivamente a la conexión."""
        w, p, q, *_ = self.preparar()
        before = copy.deepcopy(w.v.state())
        with mock.patch.object(type(w.modbus), "activo", new_callable=mock.PropertyMock, return_value=True), \
                mock.patch.object(w, "refrescar"), mock.patch.object(w.v.s, "manual_input") as manual:
            QTest.mouseClick(w.botones[p], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
            manual.assert_not_called()
        self.assertEqual(w.v.state(), before)
        self.assertIn("Play/Stop", w.aviso.text())

    def test_SPUL05_soltar_fuera_del_boton_no_deja_entrada_activa(self):
        """REQ-SIM-02: soltar el pulsador fuera de su rectángulo también devuelve la entrada a 0."""
        w, p, q, *_ = self.preparar()
        boton = w.botones[p]
        QTest.mousePress(boton, Qt.MouseButton.LeftButton)
        QTest.mouseMove(boton, QPoint(-10, -10))
        QTest.mouseRelease(boton, Qt.MouseButton.LeftButton, pos=QPoint(-10, -10))
        self.assertFalse(self.valores(w)[p])

    def test_SPUL06_soltar_ctrl_libera_todos_los_enclavados_y_conserva_interruptor(self):
        """REQ-SIM-02, REQ-SIM-03: teclado y ratón reales liberan al soltar Ctrl cada pulsador y procesan sus evoluciones."""
        w,p,q,a,b,subida,bajada=self.preparar();w.a_ejecutar.setChecked(False)
        r=w.edicion.ed.add_variable("r","input",{"kind":"bool"});w.edicion.cambia()
        w.a_ejecutar.setChecked(True);w.rt.stop();w._cambiar_tipo_entrada(r,True)
        QTest.mouseClick(w.botones[r],Qt.MouseButton.LeftButton)
        QTest.keyPress(w,Qt.Key.Key_Control)
        for var in (p,q):
            QTest.mouseClick(w.botones[var],Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(all(self.valores(w)[var] for var in (p,q,r)))
        QTest.keyRelease(w.botones[q],Qt.Key.Key_Control)
        self.assertFalse(self.valores(w)[p]);self.assertFalse(self.valores(w)[q]);self.assertTrue(self.valores(w)[r])
        self.assertTrue(w.botones[r].isChecked())
        self.assertTrue(all(not w.botones[var].enclavado and not w.botones[var].isChecked() for var in (p,q)))
        self.assertEqual(w.v.state()["situation"],[a])
        self.assertIn([bajada],[rec["cleared"] for rec in records(w.v.s,"evolucion")])

    def test_SCTL01_play_stop_muestran_texto_icono_y_conservan_su_comportamiento(self):
        """REQ-SIM-03, REQ-SIM-04: Play inicia y Stop deja todo sin estado; solo cambian los rótulos e iconos."""
        w, p, q, *_ = self.preparar()
        self.assertEqual(w.a_ejecutar.text(), "Stop")
        stop = w.a_ejecutar.icon().pixmap(24, 24).toImage()
        self.assertIn("Stop", w.a_ejecutar.toolTip()); self.assertNotIn("Pausa", w.a_ejecutar.toolTip())
        w.a_ejecutar.setChecked(False)
        self.assertEqual((w.a_ejecutar.text(), w.modo), ("Play", "editar"))
        self.assertEqual(w.v.state().get("situation", []), [])
        self.assertFalse(stop == w.a_ejecutar.icon().pixmap(24, 24).toImage())
        self.assertFalse(w.a_reiniciar.icon().isNull())
        from grafcet.examples import EJEMPLOS
        self.assertTrue(all("Pausa" not in ayuda for titulo, ayuda, construir in EJEMPLOS.values()))

    def test_SCTL02_operaciones_internas_stop_y_reiniciar_vuelven_al_grafcet(self):
        """REQ-SIM-03, REQ-SIM-04: operaciones internas de Stop/Reiniciar usan el cambio central; la interfaz E/S las deshabilita."""
        w, p, q, *_ = self.preparar()
        for marcha, operacion in ((True, "stop"), (True, "reiniciar"), (False, "reiniciar")):
            with self.subTest(marcha=marcha, operacion=operacion):
                w.a_ejecutar.setChecked(marcha); w.rt.stop()
                w._mostrar_pagina(True)
                if operacion == "stop":
                    w.a_ejecutar.setChecked(False)
                else:
                    w.reiniciar()
                self.assertEqual(w.paginas_es.currentIndex(), 0)
                self.assertFalse(w.a_es.isChecked())
                self.assertEqual(w.a_es.text(), "E/S externas")
                self.assertEqual(w.a_ejecutar.isChecked(), marcha and operacion == "reiniciar")
