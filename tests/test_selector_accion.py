"""Doble clic en una acción continua: un desplegable de variables sobre la propia acción, en lugar de abrir Propiedades."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox
    from escritorio import estilo
    from escritorio.diagrama import MAS_PROPIEDADES


@unittest.skipUnless(QT, "Falta PySide6")
class SelectorAccion(BaseQt):
    def preparar(self):
        w, e = self.vacio()
        for n, r in (("marcha", "input"), ("motor", "output"), ("luz", "output")):
            e.nueva_variable(n, r)
        e.nueva_variable("cuenta", "internal", {"kind": "int"})
        e.nueva_variable("q_int", "output", {"kind": "int"})
        e.nueva_variable("aux", "internal")
        self.cadena(e)
        w.resize(1360, 860)
        w.show()
        self.addCleanup(w.hide)
        did = e.poner_accion_suelta(QPointF(500, 200))
        for _ in range(6):
            QApplication.processEvents()
        self.pedidas = []
        e.pedir_accion = lambda sid, aid: self.pedidas.append((sid, aid))
        return w, e, did

    def doble(self, w, e, did):
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == did)
        x, y, ancho, alto = caja["rect"]
        e.doble(QPointF(x + ancho / 2, y + alto / 2))
        for _ in range(4):
            QApplication.processEvents()
        return caja, w.diagrama._selector

    def test_SSEL01_doble_clic_en_una_continua_abre_el_desplegable_sobre_la_accion(self):
        """REQ-ACT-01, REQ-EDT-09: doble clic en una acción continua abre, sin Propiedades, un desplegable sobre su rectángulo (ancho mínimo el suyo,
        alto del token, ya abierto) que solo ofrece salidas booleanas y luego memorias booleanas, sin cabeceras ni tipo, con el papel «(S)» o
        «(M)»; un separador y «Más propiedades…». Sin variable, el cuadro cerrado muestra «Elija la variable…» sin que sea una opción."""
        w, e, did = self.preparar()
        caja, cb = self.doble(w, e, did)
        self.assertIsNotNone(cb, e.datos_accion(did))
        self.assertEqual(self.pedidas, [], "no se abre Propiedades")
        self.assertEqual(cb.accessibleName(), "Variable de la acción")
        self.assertGreaterEqual(cb.width(), round(caja["rect"][2] * w.diagrama.escala()) - 1)
        self.assertEqual(cb.height(), estilo.ALTO_CONTROL)
        self.assertTrue(cb.view().isVisible(), "ya desplegado")
        textos = [cb.itemText(i) for i in range(cb.count()) if cb.itemData(i) != MAS_PROPIEDADES and cb.itemText(i)]
        self.assertEqual(textos, ["motor  (S)", "luz  (S)", "aux  (M)"], "salidas booleanas y luego memorias booleanas; sin la entera ni la entrada")
        self.assertEqual([cb.itemData(i) for i in range(3)], ["motor", "luz", "aux"])
        self.assertEqual((cb.currentIndex(), cb.placeholderText()), (-1, "Elija la variable…"))
        self.assertNotIn("Elija la variable…", [cb.itemText(i) for i in range(cb.count())])
        self.assertEqual(cb.itemText(cb.count() - 1), "Más propiedades…")
        self.assertEqual(cb.itemText(cb.count() - 2), "")  # (el separador)
        sep = cb.count() - 2
        self.assertFalse(cb.model().item(sep).isSelectable() or cb.model().item(sep).isEnabled(), "el separador no se elige")
        self.assertLessEqual(cb.view().sizeHintForRow(sep), 8, "una línea fina, no una fila entera")
        self.assertLessEqual(cb.view().window().width(), cb.width() + 4, "la lista mide lo que el cuadro (los nombres caben)")
        self.assertGreaterEqual(cb.view().window().width(), cb.width() - 4)

    def test_SSEL01b_con_variable_el_cuadro_la_muestra_y_sin_ninguna_valida_hay_una_linea_desactivada(self):
        """REQ-ACT-01: con variable en la acción, el cuadro cerrado muestra la actual; sin salidas ni memorias booleanas, una línea desactivada."""
        w, e, did = self.preparar()
        e.elegir_variable_accion(did, "luz")
        for _ in range(4):
            QApplication.processEvents()
        nuevo = w.diagrama.cajas_acciones[0]["id"]  # (al completarse, la acción cambia de ID)
        caja, cb = self.doble(w, e, nuevo)
        self.assertEqual((cb.currentIndex(), cb.currentData()), (1, "luz"))
        w.diagrama.cerrar_selector()
        e.elegir_variable_accion(nuevo, "")
        for v in [v for v in e.ed.model["variables"] if v["role"] != "input"]:
            self.assertIsNone(e.quitar_variable(v["id"]))
        for _ in range(4):
            QApplication.processEvents()
        caja, cb = self.doble(w, e, w.diagrama.cajas_acciones[0]["id"])
        self.assertIsNotNone(cb)
        self.assertEqual(cb.itemText(0), "Ninguna")
        self.assertFalse(cb.model().item(0).isEnabled())

    def test_SSEL02_elegir_cambia_la_variable_con_un_paso_de_deshacer_y_cierra(self):
        """REQ-ACT-01, REQ-EDT-02: elegir una variable la aplica por la vía de Propiedades (un paso de deshacer) y cierra el desplegable."""
        w, e, did = self.preparar()
        caja, cb = self.doble(w, e, did)
        n = len(e.ed.undo_stack)
        i = cb.findData("motor")
        self.assertGreaterEqual(i, 0)
        cb.activated.emit(i)
        for _ in range(4):
            QApplication.processEvents()
        self.assertIsNone(w.diagrama._selector)
        self.assertEqual(e.datos_accion(did)["variable"], "motor")
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(e.datos_accion(did)["variable"], "")

    def test_SSEL03_esc_zoom_y_desplazar_cierran_sin_cambiar_nada(self):
        """REQ-EDT-09: Esc, un zoom y un desplazamiento cierran el desplegable sin cambiar nada."""
        w, e, did = self.preparar()
        n = len(e.ed.undo_stack)
        caja, cb = self.doble(w, e, did)
        QTest.keyClick(cb, Qt.Key.Key_Escape)
        for _ in range(4):
            QApplication.processEvents()
        self.assertIsNone(w.diagrama._selector)
        caja, cb = self.doble(w, e, did)
        self.assertIsNotNone(w.diagrama._selector)
        w.diagrama.zoom(1.2)
        for _ in range(3):
            QApplication.processEvents()
        self.assertIsNone(w.diagrama._selector)
        caja, cb = self.doble(w, e, did)
        w.diagrama.horizontalScrollBar().setValue(w.diagrama.horizontalScrollBar().value() + 30)
        self.assertIsNone(w.diagrama._selector)
        self.assertEqual((len(e.ed.undo_stack), e.datos_accion(did)["variable"]), (n, ""))

    def test_SSEL04_mas_propiedades_abre_propiedades_y_una_condicionada_sigue_abriendolas(self):
        """REQ-ACT-01: «Más propiedades…» cierra el desplegable y abre el panel de Propiedades (inferior) con esa acción, aunque estuviera plegado;
        el doble clic en una acción condicionada abre Propiedades sin desplegable."""
        w, e, did = self.preparar()
        e.pedir_accion = lambda sid, aid: w.editar_accion(sid, aid, e.pedido_explicito)  # lo real, no el espía
        if w._plegables["inferior"].abierto:
            w._plegables["inferior"].mostrar(False)
        for _ in range(3):
            QApplication.processEvents()
        self.assertFalse(w._plegables["inferior"].abierto)
        caja, cb = self.doble(w, e, did)
        cb.activated.emit(cb.count() - 1)
        for _ in range(4):
            QApplication.processEvents()
        self.assertIsNone(w.diagrama._selector)
        self.assertTrue(w._plegables["inferior"].abierto, "el panel inferior se despliega")
        self.assertTrue(w.props.isVisible())
        self.assertEqual((e.accion, e.ver_accion), (did, True))
        self.assertTrue(w.props.accion.isVisible(), "muestra las opciones de la acción")
        d = dict(e.datos_accion(did), variable="motor", tipo="condicionada", condicion="marcha")
        self.assertIsNone(e.cambiar_accion(did, d))
        self.pedidas.clear()
        self.pedidas.clear()
        e.pedir_accion = lambda sid, aid: self.pedidas.append((sid, aid))
        caja, cb = self.doble(w, e, did)
        self.assertIsNone(cb)
        self.assertEqual(len(self.pedidas), 1)
