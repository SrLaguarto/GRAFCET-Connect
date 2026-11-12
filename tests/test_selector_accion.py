"""Doble clic en una acción continua: un desplegable de variables sobre la propia acción, en lugar de abrir Propiedades."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox
    from escritorio import estilo
    from escritorio.diagrama import MARCADORES_SELECTOR


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

    def test_SSEL01_doble_clic_en_una_continua_abre_el_desplegable_dentro_de_la_accion(self):
        """REQ-ACT-01, REQ-EDT-09: doble clic en una acción continua abre, sin Propiedades, un desplegable dentro de su rectángulo (ancho a lo sumo
        el interior de la caja, alto del token, ya abierto) que solo ofrece salidas booleanas y luego memorias booleanas, sin cabeceras ni tipo,
        con el papel «(S)» o «(M)»; sin separador ni «Más propiedades…». Sin variable, el cuadro cerrado muestra un marcador que no es opción."""
        w, e, did = self.preparar()
        caja, cb = self.doble(w, e, did)
        self.assertIsNotNone(cb, e.datos_accion(did))
        self.assertEqual(self.pedidas, [], "no se abre Propiedades")
        self.assertEqual(cb.accessibleName(), "Variable de la acción")
        esc = w.diagrama.escala()
        self.assertLessEqual(cb.width(), round(caja["rect"][2] * esc) - 2, "dentro de la caja: nunca más ancho que su interior")
        self.assertEqual(cb.height(), estilo.ALTO_CONTROL)
        self.assertTrue(cb.view().isVisible(), "ya desplegado")
        textos = [cb.itemText(i) for i in range(cb.count()) if cb.itemText(i)]
        self.assertEqual(textos, ["motor  (S)", "luz  (S)", "aux  (M)"], "salidas booleanas y luego memorias booleanas; sin la entera ni la entrada")
        self.assertEqual([cb.itemData(i) for i in range(cb.count())], ["motor", "luz", "aux"], "ni separador ni «Más propiedades…»")
        self.assertEqual((cb.currentIndex(), cb.placeholderText()), (-1, cb.placeholderText()))
        self.assertIn(cb.placeholderText(), MARCADORES_SELECTOR)
        self.assertNotIn(cb.placeholderText(), [cb.itemText(i) for i in range(cb.count())])
        self.assertGreaterEqual(cb.view().window().width(), cb.width() - 4)

    def test_SSEL05_el_marcador_cabe_entero_con_el_ancho_por_defecto_de_una_accion_a_las_dos_escalas(self):
        """REQ-EDT-09: con el ancho por defecto de una acción (80 px a 100 %) y a las dos escalas de la interfaz (normal y grande), el marcador del
        cuadro cerrado se lee entero (su texto cabe entre la sangría y la flecha) y el cuadro no sobresale de la caja; con zoom grande sale el texto
        completo «Elija la variable…»."""
        from PySide6.QtGui import QFontMetrics
        for ancho, alto in ((1360, 860), (2000, 1250)):
            w, e, did = self.preparar()
            w.resize(ancho, alto)
            for _ in range(6):
                QApplication.processEvents()
            for zoom in (None, 1.5, 2.5):
                w.diagrama.cerrar_selector()
                if zoom:
                    w.diagrama.zoom(zoom)
                    for _ in range(3):
                        QApplication.processEvents()
                caja, cb = self.doble(w, e, did)
                r = w.diagrama.mapFromScene(QRectF(*caja["rect"])).boundingRect()
                self.assertGreaterEqual(cb.geometry().left(), r.left(), (ancho, zoom))
                self.assertLessEqual(cb.geometry().right(), r.right(), (ancho, zoom))
                marcador = cb.placeholderText()
                self.assertLessEqual(QFontMetrics(cb.font()).horizontalAdvance(marcador), cb.width() - 6 - 18 - 2, (ancho, zoom, marcador))
                if zoom == 2.5:
                    self.assertEqual(marcador, "Elija la variable…")
            w.diagrama.cerrar_selector()

    def test_SSEL06_un_nombre_que_no_cabe_se_acorta_y_la_ayuda_emergente_lo_da_entero(self):
        """REQ-EDT-09: con una variable de nombre largo, el cuadro cerrado (más estrecho que la caja) lo muestra acortado con «…» sin cortarlo a
        medias y su ayuda emergente da el nombre entero; la lista desplegada se ensancha lo justo para leerlo."""
        w, e, did = self.preparar()
        e.nueva_variable("valvula_de_llenado_del_deposito_principal", "output")
        e.elegir_variable_accion(did, "valvula_de_llenado_del_deposito_principal")
        w.diagrama.zoom(0.5)  # (la caja crece con el nombre; alejando, queda más estrecha que él)
        for _ in range(4):
            QApplication.processEvents()
        caja, cb = self.doble(w, e, w.diagrama.cajas_acciones[0]["id"])
        # (alejando, el cuadro mide lo que la acción a 100 % —que crece con el nombre—, no menos: el nombre se lee entero y no hace falta ayuda)
        self.assertGreaterEqual(cb.width(), cb.fontMetrics().horizontalAdvance("valvula_de_llenado_del_deposito_principal"))
        img = cb.grab().toImage()
        self.assertGreater(img.width(), 0)
        self.assertLessEqual(abs(cb.view().window().width() - cb.width()), 2, "la lista mide lo que el cuadro")

    def test_SSEL07_la_lista_mide_el_cuadro_o_lo_justo_para_el_nombre_mas_largo_y_el_marcador_se_ve(self):
        """REQ-EDT-09: con un nombre corto («fe») y uno largo, a zoom 50 %, 100 % y 160 %, el cuadro nunca mide más que el interior de la acción
        (ni menos que a 100 %); la lista mide lo que el cuadro o, si un nombre no cabe en él, lo justo para el más largo con su papel (decisión del
        responsable del 12-nov-2026): todos los nombres se leen enteros, sin «…» ni ayuda emergente; con la acción sin variable se pinta el marcador."""
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QHelpEvent
        from unittest import mock
        from PySide6.QtWidgets import QStyleOptionViewItem
        w, e, did = self.preparar()
        w.resize(2000, 1250)
        largo = "fehgdgjfgjxyzxyz"
        e.nueva_variable("fe", "output")
        e.nueva_variable(largo, "output")
        for _ in range(6):
            QApplication.processEvents()
        base = None
        for zoom in (0.5, 1.0, 1.6):
            w.diagrama.cerrar_selector()
            w.diagrama.zoom(zoom / w.diagrama.escala())
            for _ in range(3):
                QApplication.processEvents()
            caja, cb = self.doble(w, e, did)
            self.assertAlmostEqual(w.diagrama.escala(), zoom, places=2)
            marco = cb.view().parentWidget()
            fm = cb.view().fontMetrics()
            pide = fm.horizontalAdvance(largo) + fm.horizontalAdvance("(S)") + 2 * 8 + 12
            self.assertGreaterEqual(marco.width(), cb.width(), zoom)
            self.assertLessEqual(marco.width(), max(cb.width(), pide) + 8, (zoom, "sin huecos: lo justo"))
            interior = round(caja["rect"][2] * max(zoom, 1.0)) - 2 * max(2, round(2 * max(zoom, 1.0)))
            self.assertLessEqual(cb.width(), interior, zoom)
            if zoom == 1.0:
                base = cb.width()
            elif zoom == 0.5:
                self.assertGreaterEqual(cb.width(), min(interior, cb.width()) - 2, "alejando, nunca menos que a 100 %")
            # el marcador se pinta (la acción no tiene variable)
            con = cb.grab().toImage()
            cb.setPlaceholderText("")
            sin = cb.grab().toImage()
            self.assertNotEqual(con, sin, "marcador visible")
            cb.setPlaceholderText(" ")
            vista, d = cb.view(), cb.view().itemDelegate()
            for i in range(cb.count()):
                nombre = cb.itemData(i)
                rect = vista.visualRect(vista.model().index(i, 0))
                self.assertLessEqual(abs(rect.width() - marco.width()), 6, (zoom, nombre))
                opt = QStyleOptionViewItem()
                opt.rect, opt.font = rect, vista.font()
                opt.fontMetrics = vista.fontMetrics()
                with mock.patch("escritorio.diagrama.QToolTip.showText") as ayuda:
                    d.helpEvent(QHelpEvent(QEvent.Type.ToolTip, QPoint(5, 5), QPoint(5, 5)), vista, opt, vista.model().index(i, 0))
                if nombre in (largo, "fe"):
                    ayuda.assert_not_called()
                    self.assertLessEqual(opt.fontMetrics.horizontalAdvance(nombre), d._hueco_nombre(opt.fontMetrics, rect, "S"), (zoom, nombre))
            w.diagrama.cerrar_selector()
        self.assertIsNotNone(base)

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

    def test_SSEL04_una_condicionada_sigue_abriendo_propiedades_y_la_continua_no_ofrece_mas_propiedades(self):
        """REQ-ACT-01: el doble clic en una acción condicionada abre Propiedades sin desplegable; en la continua solo se elige la variable (el
        desplegable no lleva «Más propiedades…»; el resto se edita en Propiedades con el panel inferior)."""
        w, e, did = self.preparar()
        caja, cb = self.doble(w, e, did)
        self.assertNotIn("Más propiedades…", [cb.itemText(i) for i in range(cb.count())])
        w.diagrama.cerrar_selector()
        d = dict(e.datos_accion(did), variable="motor", tipo="condicionada", condicion="marcha")
        self.assertIsNone(e.cambiar_accion(did, d))
        self.pedidas.clear()
        caja, cb = self.doble(w, e, did)
        self.assertIsNone(cb)
        self.assertEqual(len(self.pedidas), 1)
