"""Ajustes de la rama de rediseño: columnas de las tablas de estado sin esconder, panel derecho de 270 px, tope del panel inferior y
paleta de operadores en una fila en ventanas bajas."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtWidgets import QApplication
    from escritorio import estilo
    from escritorio.alto_opciones import alto_minimo_transicion, tope_alto
    from escritorio.ventana import ANCHO_DERECHO, UMBRAL_DERECHO


@unittest.skipUnless(QT, "requiere PySide6")
class Rediseno(BaseQt):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.w.hide)

    def _transicion(self, ancho, alto):
        w, e = self.vacio()
        w.resize(ancho, alto)
        w.show()
        ids = self.cadena(e)
        e.seleccionar([ids[1]])
        w._abrir_opciones()
        for _ in range(3):
            QApplication.processEvents()
        return w, e, ids

    def test_SRED01_ninguna_columna_de_las_tablas_de_estado_se_esconde(self):
        """REQ-SIM-03, REQ-EDT-09: «Salidas y variables» lleva siempre sus cuatro columnas (también «Modo») y «Temporizadores» las suyas
        (dónde, estado, lleva, preset), con el panel de 270 px y con el de 218; el nombre mide ≥ 96 px y las columnas se abrevian."""
        w, e = self.vacio()
        for ancho, alto in ((1366, 768), (960, 1040), (1100, 700)):
            w.resize(ancho, alto)
            w.show()
            w._poner_modo()
            QApplication.processEvents()
            for t in (w.t_vars, w.t_temp):
                self.assertEqual([t.isColumnHidden(c) for c in range(4)], [False] * 4, (ancho, alto, t.objectName()))
            for plan in w._planes_vars() + w._planes_temp():
                self.assertTrue(all(px > 0 for px in plan["anchos"].values()), "ningún plan esconde una columna")
        # Estado entero o abreviado, siempre con su texto entero en la celda
        w._elegir_plan_temp(w._planes_temp()[1])
        self.assertEqual(w.t_temp.itemDelegateForColumn(1).displayText("contando", None), "cont.")
        w._elegir_plan_temp(w._planes_temp()[0])
        self.assertEqual(w.t_temp.itemDelegateForColumn(1).displayText("contando", None), "contando")
        w._elegir_plan_vars(w._planes_vars()[1])
        self.assertEqual(w.t_vars.itemDelegateForColumn(1).displayText("salida continua", None), "cont.")

    def test_SRED02_panel_derecho_de_270_px_desde_1280_y_el_izquierdo_en_218(self):
        """REQ-EDT-09, REQ-EDT-07: el panel derecho mide 270 px desde 1280 px de ancho de ventana (Variables, y la simulación lo conserva
        al pulsar Play) y 218 por debajo; el izquierdo no cambia; a pantalla completa, lo que ya hacía la rama (300 a 1920)."""
        w, e = self.vacio()
        for ancho, alto, derecho in ((1366, 768, 270), (1280, 720, 270), (1279, 720, 218), (1000, 600, 218)):
            w.resize(ancho, alto)
            w.show()
            QApplication.processEvents()
            QApplication.processEvents()
            self.assertEqual(w.ancho_derecho, derecho, (ancho, alto))
            self.assertEqual(w.ancho_lateral, 218, "el izquierdo no cambia (SPAL05, SPAL06)")
            self.assertEqual((w.dock.width(), w.derecho.width()), (218, derecho), (ancho, alto))
        self.assertEqual((ANCHO_DERECHO, UMBRAL_DERECHO), (270, 1280))
        w.resize(1366, 768)
        QApplication.processEvents()
        self.assertTrue(w.variables.completo, "con 270 px «Papel» y «Tipo» salen enteros a 1366")
        w.resize(1000, 600)
        QApplication.processEvents()
        self.assertFalse(w.variables.completo, "con 218 se abrevian")
        w.resize(1920, 1080)
        QApplication.processEvents()
        QApplication.processEvents()
        self.assertEqual((w.ancho_derecho, w.ancho_lateral), (300, 300))

    def test_SRED03_cuatro_columnas_a_1366_con_el_panel_de_270(self):
        """REQ-SIM-03: a 1366×768 las tablas de estado de la simulación llevan sus cuatro columnas con «Modo» y «Estado» a la vista,
        el nombre ≥ 96 px, y el panel conserva su ancho al pulsar Play."""
        w, e = self.vacio()
        self.cadena(e)
        w.resize(1366, 768)
        w.show()
        QApplication.processEvents()
        ancho = w.derecho.width()
        self.assertEqual(ancho, 270)
        self.assertTrue(w.cambiar_modo("simular"))
        QApplication.processEvents()
        self.assertEqual(w.derecho.width(), ancho, "la simulación conserva el ancho (P-IMP-75)")
        for t in (w.t_vars, w.t_temp):
            self.assertEqual([t.isColumnHidden(c) for c in range(4)], [False] * 4)
            self.assertGreaterEqual(t.columnWidth(0), 96)
            self.assertEqual(t.horizontalScrollBar().maximum(), 0, "las cuatro caben sin desplazarse")

    def test_SRED04_el_panel_inferior_no_pasa_del_55_por_ciento_del_alto(self):
        """REQ-EDT-09: con una transición seleccionada el panel inferior no pasa del 55 % del alto de la ventana (con un mínimo que deja
        ver una fila de campos); a 768 px no cambia nada: sigue viendo entera la paleta de operadores."""
        w, e, ids = self._transicion(1366, 768)
        self.assertGreaterEqual(w.vsplit.sizes()[1], alto_minimo_transicion(w.props), "a 768 px lo de siempre")
        self.assertLessEqual(w.vsplit.sizes()[1], tope_alto(w))
        self.assertGreater(tope_alto(w), alto_minimo_transicion(w.props))
        w2, e2, ids2 = self._transicion(1366, 520)  # con la paleta en una fila (< 560 px) pide menos que el tope
        self.assertLessEqual(w2.vsplit.sizes()[1], tope_alto(w2))
        self.assertGreaterEqual(w2.vsplit.sizes()[1], w2.props.minimumSizeHint().height())
        # a 600 px la paleta de operadores (columna) no cabe entera en el tope: se desplaza dentro del panel, sin cortar controles
        w3, e3, ids3 = self._transicion(1366, 600)
        self.assertFalse(w3.props.prog.en_fila)
        self.assertLessEqual(w3.vsplit.sizes()[1], int(600 * 0.55) + 1)
        self.assertEqual(tope_alto(w3), max(int(600 * 0.55), w3.props.minimumSizeHint().height()))

    def test_SRED05_paleta_de_operadores_en_una_fila_por_debajo_de_560_px_de_alto(self):
        """REQ-EDT-09: por debajo de 560 px de alto la paleta de operadores va en una sola fila con desplazamiento horizontal y el
        panel pide mucho menos alto; por encima, en columna como siempre."""
        w, e, ids = self._transicion(1100, 520)
        prog = w.props.prog
        self.assertTrue(prog.en_fila)
        prog.elegir_categoria("operador")
        QApplication.processEvents()
        ys = {y for _, _, y in prog.paleta._cajas}
        self.assertEqual(len(ys), 1, "una sola fila de bloques")
        self.assertEqual(len(prog.paleta._cajas), 6)
        self.assertLess(prog._sc_paleta.height(), 70)
        self.assertLessEqual(alto_minimo_transicion(w.props), 260)
        self.assertLess(alto_minimo_transicion(w.props), 334)
        # estrechando el panel hay desplazamiento horizontal y ningún bloque se corta (se alcanzan con la barra)
        w.resize(640, 520)
        QApplication.processEvents()
        QApplication.processEvents()
        barra = prog._sc_paleta.horizontalScrollBar()
        self.assertGreater(barra.maximum(), 0, "la fila se desplaza a los lados")
        self.assertEqual(prog._sc_paleta.verticalScrollBar().maximum(), 0)
        self.assertLessEqual(prog.minimumSizeHint().width(), 200, "la fila no ensancha el panel")
        # el área de trabajo queda bajo la paleta y la fórmula sigue visible
        self.assertGreater(prog.lienzo.mapTo(prog, prog.lienzo.rect().topLeft()).y(), prog._sc_paleta.y())
        self.assertTrue(w.props.caja_formula.isVisible())
        # al subir de 560 px vuelve la columna
        w.resize(1100, 700)
        QApplication.processEvents()
        QApplication.processEvents()
        self.assertFalse(prog.en_fila)
        prog.elegir_categoria("operador")
        self.assertEqual(len({x for _, x, _ in prog.paleta._cajas}), 1, "la columna: todos en la misma x")
        self.assertGreater(len({y for _, _, y in prog.paleta._cajas}), 1)

    def test_SRED06_pestanas_plegadas_de_32_px(self):
        """REQ-EDT-09: las pestañas de los paneles plegados miden 32 px (objetivo táctil)."""
        from escritorio.paneles import PanelPlegable
        self.assertEqual(PanelPlegable.GROSOR_PESTANA, 32)


if __name__ == "__main__":
    unittest.main()
