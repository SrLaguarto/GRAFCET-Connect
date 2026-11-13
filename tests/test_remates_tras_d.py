"""SREM2: barra neutra y Propiedades compactas en ambos modos de presentación."""
import unittest
from collections import Counter
from unittest import mock

try:
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

if QT:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QMenu, QStyle, QStyleOptionComboBox, QVBoxLayout, QWidget
    from test_editor_cadenas import BaseQt
    from escritorio import estilo
    from escritorio.acciones import PanelAccion
    from escritorio.diagrama import SelectorAccion
else:
    BaseQt = unittest.TestCase


@unittest.skipUnless(QT, "requiere PySide6")
class RematesTrasD(BaseQt):
    def preparar(self, tipo="transicion", flotante=False, ancho=1366, alto=768):
        w, e = self.vacio()
        w._cambiar_modo_propiedades("flotante" if flotante else "abajo")
        ids = self.cadena(e)
        e.nueva_variable("aux", "internal")
        w.resize(ancho, alto)
        w.show()
        self.pasar_arranque(w)
        self.asentar_escala(w)
        aid = None
        if tipo == "transicion":
            w.editar_condicion(ids[1])
        else:
            datos = {"tipo": tipo, "variable": "aux"}
            if tipo == "condicionada":
                datos["condicion"] = "marcha"
            else:
                datos["valor"] = "1"
                if tipo == "evento":
                    datos["evento"] = "↑marcha"
            self.assertIsNone(e.poner_accion(ids[2], datos))
            aid = e.acciones(ids[2])[-1]["id"]
            w.editar_accion(ids[2], aid)
        w._abrir_opciones()
        for _ in range(8):
            QApplication.processEvents()
        return w, e, w.flot.panel if flotante else w.props, aid

    def test_SREM201_quitar_boton_conserva_menu_atajo_y_separadores(self):
        w, e, p, aid = self.preparar()
        self.assertNotIn(w.a_debajo, w.tb_edit.actions())
        self.assertIsNone(w.tb_edit.widgetForAction(w.a_debajo))
        self.assertTrue(any(w.a_debajo in m.actions() for m in w.menuBar().findChildren(QMenu)))
        self.assertEqual(w.a_debajo.shortcut().toString(), "Ctrl+Return")
        acciones = w.tb_edit.actions()
        self.assertFalse(acciones[-1].isSeparator())
        self.assertFalse(any(a.isSeparator() and b.isSeparator() for a, b in zip(acciones, acciones[1:])))
        sid = e.poner_etapa(QPointF(700, 100))
        e.seleccionar([sid])
        antes = len(e.M["steps"]), len(e.M["transitions"])
        w.diagrama.setFocus()
        QTest.keyClick(w.diagrama, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        self.assertEqual((len(e.M["steps"]), len(e.M["transitions"])), (antes[0] + 1, antes[1] + 1))

    def test_SREM202_fondo_identico_en_edicion_y_simulacion(self):
        w, e, p, aid = self.preparar()
        for ancho, alto in ((1366, 768), (960, 520)):
            w.resize(ancho, alto)
            self.asentar_escala(w)
            QApplication.processEvents()
            barra = w.herramientas_grafcet
            antes = barra.grab().toImage().pixelColor(barra.width() - estilo.E2, 2)
            self.assertTrue(w.cambiar_modo("simular"))
            for _ in range(4):
                QApplication.processEvents()
            despues = barra.grab().toImage().pixelColor(barra.width() - estilo.E2, 2)
            self.assertEqual(antes, despues)
            self.assertTrue(w.banda_modo.isVisible())
            self.assertIn("SIMULACIÓN", w.estado.text())
            w.cambiar_modo("editar")

    def test_SREM203_aviso_en_linea_bajo_formula_y_papelera_centrada(self):
        for flotante in (False,):  # (la ventana flotante ya no tiene fila «Fórmula» ni aviso fijo, y la papelera va junto a las categorías: SPFL29 y SPFL30)
            w, e, p, aid = self.preparar(flotante=flotante)
            estado, campo, papelera = p.t_estado, p.t_texto, p.prog.papelera
            self.assertFalse(estado.wordWrap())
            self.assertEqual(estado.height(), estado.fontMetrics().height())
            self.assertGreater(estado.y(), campo.geometry().bottom())
            self.assertEqual(estado.x(), campo.x())
            self.assertLessEqual(abs(papelera.geometry().center().y() - campo.geometry().center().y()), 1)
            texto = "Error de validación\n" + "con una explicación extensa. " * 30
            estado.setText(texto)
            self.assertEqual(estado.toolTip(), texto)
            elidido = estado.texto_visible()
            self.assertNotIn("\n", elidido)
            self.assertTrue(elidido.endswith("…"))

    def test_SREM204_frase_usa_el_ancho_completo(self):
        for flotante in (False,):  # (la ventana flotante ya no lleva la frase de la acción: SPFL29)
            w, e, p, aid = self.preparar("evento", flotante)
            frase = p.accion.frase
            self.assertGreater(frase.width(), 300)
            self.assertGreater(frase.width(), p.izq.width())
            self.assertAlmostEqual(frase.width(), p.width() - p.layout().contentsMargins().left()
                                   - p.layout().contentsMargins().right(), delta=2)
            self.assertTrue(frase.wordWrap())

    def test_SREM205_fila_valor_centrada_y_salto_al_estrechar(self):
        for flotante in (False, True):
            w, e, p, aid = self.preparar("evento", flotante)
            pa = p.accion
            controles = [pa.variable, pa.l_fichas, *pa.fichas.values()]
            centros = [x.mapToGlobal(x.rect().center()).y() for x in controles]
            self.assertLessEqual(max(centros) - min(centros), 1)
            caja = QWidget()
            self.addCleanup(caja.close)
            lay = QVBoxLayout(caja)
            prueba = PanelAccion()
            lay.addWidget(prueba)
            lay.addWidget(prueba.caja_valor)
            prueba.mostrar(e, aid)
            caja.resize(220, 400)
            caja.show()
            for _ in range(4):
                QApplication.processEvents()
            fichas, variable = prueba.caja_fichas, prueba.variable
            self.assertGreaterEqual(fichas.y() - variable.geometry().bottom() - 1, estilo.E2)
            self.assertEqual(fichas.x(), variable.x())

    def test_SREM206_relleno_interior_de_los_dos_selectores(self):
        w, e, p, aid = self.preparar("evento")
        opcion, campo = p.accion.variable.rectangulo_texto()
        self.assertGreaterEqual(campo.left() - opcion.rect.left(), estilo.E2, "el texto, a E2 del borde del desplegable, no del de la caja")
        with mock.patch.object(SelectorAccion, "showPopup"):
            w.diagrama.abrir_selector((100, 100, 100, 44), [("aux", "aux", True)], "aux", lambda _: None)
            QApplication.processEvents()
            cb = w.diagrama._selector
            opcion = QStyleOptionComboBox()
            cb.initStyleOption(opcion)
            campo = cb.style().subControlRect(
                QStyle.ComplexControl.CC_ComboBox, opcion, QStyle.SubControl.SC_ComboBoxEditField, cb)
            self.assertGreaterEqual(campo.left(), estilo.E2)
            self.assertLessEqual(cb.width(), 100)
            w.diagrama.cerrar_selector()

    def test_SREM207_filas_de_categorias_en_tamanos_y_modos(self):
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            for flotante in (False, True):
                for tipo in ("transicion", "condicionada", "evento"):
                    with self.subTest(ancho=ancho, flotante=flotante, tipo=tipo):
                        w, e, p, aid = self.preparar(tipo, flotante, ancho, alto)
                        botones = p.prog.categorias.values()
                        filas = Counter(b.mapToGlobal(QPoint()).y() for b in botones)
                        self.assertTrue(all(b.isVisible() for b in botones))
                        if ancho >= 1366:
                            self.assertEqual(len(filas), 1)
                        else:
                            self.assertLessEqual(len(filas), 2)
                            if len(filas) == 2:
                                self.assertGreaterEqual(min(filas.values()), 2)
