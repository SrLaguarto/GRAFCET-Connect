"""Encargo 4: títulos de Propiedades sin nombre, categorías en la cabecera de la acción, etiquetas de etapa de 4 caracteres, ficha de etapa con
nombre no numérico, avisos de diagnóstico plegados y hueco bajo la franja de modo."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QApplication


@unittest.skipUnless(QT, "requiere PySide6")
class CabecerasYAvisos(BaseQt):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.w.hide)

    def test_SRED26_el_titulo_de_propiedades_dice_solo_el_tipo_y_la_etapa_admite_4_caracteres(self):
        """REQ-EDT-09, REQ-EDT-02: «Propiedades · Transición», «· Etapa»… sin el nombre del elemento (se edita en «Etiqueta»); la etiqueta de una
        etapa admite 4 caracteres como máximo al escribirla, y lo ya guardado con más se conserva."""
        w, e = self.vacio()
        ids = self.cadena(e)
        w.resize(1366, 768)
        w.show()
        for sel, titulo in (([ids[0]], "Propiedades · Etapa"), ([ids[1]], "Propiedades · Transición"), ([ids[0], ids[1]], "elementos seleccionados")):
            e.seleccionar(sel)
            w._abrir_opciones()
            for _ in range(4):
                QApplication.processEvents()
            self.assertIn(titulo, w.props.titulo.text())
        self.assertEqual(w.props.s_etiqueta.maxLength(), 4)
        sid = ids[0]
        self.assertIsNotNone(e.renombrar(sid, "12345"), "más de 4 se rechaza")
        self.assertIsNone(e.renombrar(sid, "1234"))
        e.ed.rename(sid, "etapa_larga", repetida=True)  # (un archivo con nombres largos se abre igual: el núcleo no limita)
        e.cambia()
        self.assertEqual(e.nombres[sid], "etapa_larga")

    def test_SRED27_las_categorias_de_una_accion_suben_a_la_cabecera(self):
        """REQ-EDT-09: el programador visible de una acción usa la fila de la cabecera, entre el título y «Fijar», alineado con su paleta; el
        título dice «Propiedades · Acción» y lo que se edita va sobre el área de bloques; en estrecho vuelven a su fila propia."""
        w, e = self.vacio()
        ids = self.cadena(e)
        e.nueva_variable("CT", "internal", {"kind": "int"})
        e.nueva_variable("I02", "input")
        self.assertIsNone(e.poner_accion(ids[0], {"tipo": "evento", "variable": "CT", "valor": "CT + 1", "evento": "↑I02"}))
        aid = e.acciones(ids[0])[0]["id"]
        w.resize(2000, 1250)
        w.show()
        w.editar_accion(ids[0], aid)
        for _ in range(8):
            QApplication.processEvents()
        p = w.props
        self.assertEqual(p.titulo.text(), "Propiedades · Acción")
        prog = p.prog
        self.assertTrue(prog.cat_en_cabecera)
        self.assertTrue(p.cabecera.isAncestorOf(prog._sc_carpetas))
        self.assertEqual(prog._sc_carpetas.mapTo(p, QPoint(0, 0)).x(), prog._sc_paleta.mapTo(p, QPoint(0, 0)).x())
        self.assertLess(prog._sc_carpetas.mapTo(p, QPoint(0, 0)).x() + prog._sc_carpetas.width(), p.t_fijar.mapTo(p, QPoint(0, 0)).x())
        self.assertIn("Evento de la acción", p.l_bloques.text())
        self.assertGreater(p.l_bloques.mapTo(p, QPoint(0, 0)).y(), p.cabecera.height() - 2)
        w.resize(960, 1040)
        for _ in range(6):
            QApplication.processEvents()
        self.assertFalse(prog.cat_en_cabecera)

    def test_SRED28_la_ficha_de_una_etapa_con_nombre_no_numerico_se_ve_como_en_la_formula(self):
        """REQ-EDT-02: una etapa llamada «0fsd» (o con espacios) se ve «X0fsd» en la paleta, en el área y en el desplegable, no «active(`0fsd`)»;
        lo que se guarda y se escribe en la fórmula no cambia. (En main ya salía como active(`0fsd`).)"""
        from escritorio.bloques import Programador, arbol_a_texto, etapa_visible, nuevo
        from grafcet.notation import x_etapa
        etapas = [x_etapa("0fsd"), x_etapa("a b"), "X1", x_etapa("Inicio")]
        prog = Programador(lambda: ({}, etapas))
        prog.elegir_categoria("etapa")
        visibles = [prog.paleta.motor.elementos(n)[0][2] for n in prog.paleta.bloques()]
        self.assertEqual(sorted(visibles), sorted(["X0fsd", "Xa b", "X1", "XInicio"]))
        self.assertEqual([t for t, _ in prog.opciones("etapa")], ["X0fsd", "Xa b", "X1", "XInicio"])
        self.assertEqual(etapa_visible("active(`0fsd`)"), "X0fsd")
        nodo = nuevo("temp", t1="3s", a=nuevo("etapa", n=x_etapa("0fsd")))
        self.assertEqual(prog.lienzo.motor.elementos(nodo["a"])[0][2], "X0fsd")
        self.assertEqual(arbol_a_texto(nodo), "3s/active(`0fsd`)", "lo que se guarda no cambia")

    def test_SRED29_los_avisos_de_diagnostico_van_plegados_con_un_resumen(self):
        """REQ-EDT-09: arriba a la derecha, el triángulo y, a su lado, un resumen plegado («2 errores»); un clic despliega la lista y otro la
        pliega; sigue desplegada si cambian los avisos y se oculta todo cuando no queda ninguno; se maneja con Espacio."""
        from PySide6.QtTest import QTest
        w, e = self.vacio()
        self.cadena(e)
        w.resize(1366, 768)
        w.show()
        e.ed.add_transition("g", "", label="t9", at=(100, 500))
        e.cambia()
        for _ in range(4):
            QApplication.processEvents()
        d = w.diagrama
        b = d.resumen_diagnosticos
        self.assertTrue(d.indicador_diagnosticos.isVisible() and b.isVisible())
        self.assertRegex(b.text(), r"[0-9]+ errores?")
        self.assertFalse(d.lista_diagnosticos.isVisible(), "por defecto, plegado")
        self.assertLess(d.indicador_diagnosticos.geometry().right(), b.x())
        b.click()
        self.assertTrue(d.lista_diagnosticos.isVisible() and d.lista_diagnosticos.count() >= 1)
        e.ed.add_transition("g", "", label="t10", at=(100, 600))
        e.cambia()
        for _ in range(4):
            QApplication.processEvents()
        self.assertTrue(d.lista_diagnosticos.isVisible(), "desplegada, sigue desplegada con un aviso nuevo")
        b.click()
        self.assertFalse(d.lista_diagnosticos.isVisible())
        QTest.keyClick(b, Qt.Key.Key_Space)
        self.assertTrue(d.lista_diagnosticos.isVisible(), "Espacio la despliega")
        self.assertEqual(b.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        d.actualizar_diagnosticos(False)
        self.assertFalse(any(x.isVisible() for x in (b, d.indicador_diagnosticos, d.lista_diagnosticos)))
        self.assertFalse(d.diagnosticos_abiertos, "sin avisos, vuelve a plegada")

    def test_SRED30_hueco_entre_la_franja_de_modo_y_la_cabecera(self):
        """REQ-EDT-09: entre la franja de modo y el borde superior del recuadro del zoom (y del chip y el título) quedan al menos 4 px."""
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        for _ in range(4):
            QApplication.processEvents()
        tarjeta = w.diagrama.parentWidget()
        franja = w.banda_modo.geometry().bottom()
        for objeto in (w.diagrama.barra, w.estado, w.titulo):
            self.assertGreaterEqual(objeto.mapTo(tarjeta, QPoint(0, 0)).y() - franja - 1, 4, type(objeto).__name__)


if __name__ == "__main__":
    unittest.main()
