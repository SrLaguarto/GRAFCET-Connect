"""Variables: la fila en blanco del final y pegar variables desde una hoja de cálculo."""
import unittest

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtWidgets import QApplication
    from escritorio.variables import MARCADOR, ROJO_SUAVE, parsear_pegado


EJEMPLO = "Marcha\tEntrada\tBooleana\nBarrera\tSalida\tBooleana\nError\tSalIdo\tBuleano\n"


@unittest.skipUnless(QT, "Falta PySide6")
class VariablesPegar(BaseQt):
    def setUp(self):
        super().setUp()
        self.w.resize(1360, 860)
        self.w.show()
        self.w, self.e = self.vacio()
        QApplication.processEvents()
        self.pv = self.w.variables
        self.addCleanup(self.w.hide)

    def nombres(self):
        return [(v["name"], v["role"], v["type"]["kind"]) for v in self.e.ed.model["variables"]]

    def fila(self, nombre):
        return next(r for r, f in enumerate(self.pv._filas) if self.pv.tabla.item(r, 0).text() == nombre)

    def test_SVAR01_la_tabla_termina_con_una_fila_en_blanco_que_crea_la_variable(self):
        """REQ-EDT-07: la fila en blanco del final (con «nueva variable…» en gris) crea la variable al escribir un nombre, y deja otra debajo."""
        pv = self.pv
        self.assertEqual((pv.tabla.rowCount(), pv.tabla.item(0, 0).text(), pv._filas[0]["blanca"]), (1, "", True))
        self.assertEqual(MARCADOR, "nueva variable…")
        n = len(self.e.ed.undo_stack)
        pv.tabla.item(0, 0).setText("Marcha")
        QApplication.processEvents()
        self.assertEqual(self.nombres(), [("Marcha", "input", "bool")])
        self.assertEqual(len(self.e.ed.undo_stack), n + 1)
        self.assertEqual((pv.tabla.rowCount(), pv.tabla.item(1, 0).text(), pv._filas[1]["blanca"]), (2, "", True))
        pv.tabla.item(1, 0).setText("Paro")
        QApplication.processEvents()
        self.assertEqual([x[0] for x in self.nombres()], ["Marcha", "Paro"])
        self.assertEqual(pv.tabla.rowCount(), 3)

    def test_SVAR02_la_fila_en_blanco_no_cuenta_ni_se_guarda_ni_sale_al_simular(self):
        """REQ-EDT-07: la fila en blanco no es una variable ni una fila pendiente (no impide guardar ni simular) y desaparece con el panel desactivado."""
        pv = self.pv
        self.assertEqual((self.e.ed.model["variables"], pv.sin_nombre(), self.w._variables_sin_nombre()), ([], 0, False))
        pv.nueva("output")  # los botones «+ Entrada / + Salida / + Memoria» siguen añadiendo una fila (que sí cuenta)
        self.assertEqual((pv.sin_nombre(), pv.tabla.rowCount(), pv._filas[0]["papel"], pv._filas[1]["blanca"]), (1, 2, "output", True))
        pv._confirmar_edicion()  # (con el cursor en el nombre, la tabla no se rehace)
        pv.tabla.selectRow(0)
        pv.quitar_seleccion()
        self.assertEqual((pv.sin_nombre(), pv.tabla.rowCount()), (0, 1))
        pv.tabla.selectRow(0)
        pv.quitar_seleccion()  # (la fila en blanco no se quita)
        self.assertEqual(pv.tabla.rowCount(), 1)
        pv.setEnabled(False)
        QApplication.processEvents()
        self.assertEqual(pv.tabla.rowCount(), 0)
        pv.setEnabled(True)
        QApplication.processEvents()
        self.assertEqual(pv.tabla.rowCount(), 1)

    def test_SVAR03_pegar_el_ejemplo_crea_dos_y_deja_la_tercera_en_rojo_con_sus_motivos(self):
        """REQ-EDT-07: dos filas válidas se crean; la tercera («SalIdo», «Buleano») queda pendiente con Papel y Tipo en rojo, ayuda con el motivo y resumen."""
        pv = self.pv
        n = len(self.e.ed.undo_stack)
        resumen = pv.pegar_texto(EJEMPLO)
        QApplication.processEvents()
        self.assertEqual(resumen, "3 filas pegadas: 2 creadas, 1 con errores (en rojo)")
        self.assertEqual(pv.msg.text(), resumen)
        self.assertEqual(self.nombres(), [("Marcha", "input", "bool"), ("Barrera", "output", "bool")])
        self.assertEqual(len(self.e.ed.undo_stack), n + 1, "todo el pegado es un solo paso de deshacer")
        r = self.fila("Error")
        t = pv.tabla
        self.assertEqual((t.item(r, 1).text(), t.item(r, 2).text()), ("SalIdo", "Buleano"))
        self.assertEqual(t.item(r, 1).background().color().name(), ROJO_SUAVE)
        self.assertEqual(t.item(r, 2).background().color().name(), ROJO_SUAVE)
        self.assertNotEqual(t.item(r, 0).background().color().name(), ROJO_SUAVE)
        self.assertEqual(t.item(r, 1).foreground().color().name(), "#c62828")
        self.assertIn("Papel no reconocido: «SalIdo». Use Entrada, Salida o Memoria.", t.item(r, 1).toolTip())
        self.assertIn("Tipo no reconocido: «Buleano»", t.item(r, 2).toolTip())
        self.assertEqual((pv.sin_nombre(), pv._filas[-1]["blanca"]), (1, True))
        self.e.deshacer() if hasattr(self.e, "deshacer") else self.w.historial_plano(False)
        QApplication.processEvents()
        self.assertEqual(self.nombres(), [])

    def test_SVAR04_cabecera_saltada_punto_y_coma_y_normalizacion(self):
        """REQ-EDT-07: una cabecera «Nombre / Papel / Tipo» se salta; «;» también separa; papel y tipo se reconocen sin mayúsculas ni tildes y con
        abreviaturas; si faltan, Entrada y Booleana."""
        self.assertEqual(parsear_pegado("Nombre;Papel;Tipo\nA;S;Bool\n\n"), [["A", "S", "Bool"]])
        self.pv.pegar_texto("Nombre\tPapel\tTipo\n  Sensor1 \t ENTRADA \t entéra\nMotor;sálida\nM1\tm\tDecimal\nSolo\n")
        QApplication.processEvents()
        self.assertEqual(self.nombres(), [("Sensor1", "input", "int"), ("Motor", "output", "bool"), ("M1", "internal", "decimal"), ("Solo", "input", "bool")])
        self.assertEqual(self.pv.sin_nombre(), 0)
        self.assertEqual(self.pv.msg.text(), "4 filas pegadas: 4 creadas")

    def test_SVAR05_corregir_la_celda_roja_crea_la_variable(self):
        """REQ-EDT-07: al corregir con el desplegable las celdas erróneas, la fila se crea sola y deja de estar pendiente."""
        pv = self.pv
        pv.pegar_texto(EJEMPLO)
        QApplication.processEvents()
        r = self.fila("Error")
        pv.elegir(r, 1, "output")
        QApplication.processEvents()
        self.assertNotIn("Error", [x[0] for x in self.nombres()], "aún falta el tipo")
        r = self.fila("Error")
        pv.elegir(r, 2, {"kind": "int"})
        QApplication.processEvents()
        self.assertEqual(self.nombres()[-1], ("Error", "output", "int"))
        self.assertEqual((pv.sin_nombre(), pv.tabla.rowCount()), (0, 4))

    def test_SVAR06_nombre_repetido_o_no_valido_queda_en_rojo_y_se_corrige_escribiendo(self):
        """REQ-EDT-07: un nombre repetido o no válido deja la celda del nombre en rojo con el motivo del núcleo; al escribir otro, se crea."""
        pv = self.pv
        pv.pegar_texto("A\tEntrada\tBooleana\nA\tSalida\nmal nombre\nB\n")
        QApplication.processEvents()
        self.assertEqual([x[0] for x in self.nombres()], ["A", "B"])
        self.assertEqual(pv.msg.text(), "4 filas pegadas: 2 creadas, 2 con errores (en rojo)")
        repetido = [(r, f) for r, f in enumerate(pv._filas) if f.get("pegada")]
        self.assertEqual(len(repetido), 2)
        (r1, f1), (r2, f2) = repetido
        self.assertIn("ya existe", pv.tabla.item(r1, 0).toolTip())
        self.assertIn("no puede ser nombre de variable", pv.tabla.item(r2, 0).toolTip())
        self.assertEqual(pv.tabla.item(r1, 0).background().color().name(), ROJO_SUAVE)
        pv.tabla.item(r1, 0).setText("A2")
        QApplication.processEvents()
        self.assertEqual([x[0] for x in self.nombres()], ["A", "B", "A2"])
        self.assertEqual(self.nombres()[-1][1], "output")
        self.assertEqual(pv.sin_nombre(), 1)

    def test_SVAR07_ctrl_v_con_la_tabla_enfocada_pega_variables_y_con_un_editor_abierto_es_un_pegado_normal(self):
        """REQ-EDT-07: Ctrl+V con la tabla enfocada pega las filas del portapapeles; con el editor de una celda abierto pega el texto en ella."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        pv = self.pv
        QApplication.clipboard().setText("Marcha\tEntrada\tBooleana\nBarrera\tSalida\tBooleana")
        pv.tabla.setFocus()
        QApplication.processEvents()
        QTest.keyClick(pv.tabla, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        self.assertEqual([x[0] for x in self.nombres()], ["Marcha", "Barrera"])
        QApplication.clipboard().setText("Texto")
        pv.tabla.editItem(pv.tabla.item(pv.tabla.rowCount() - 1, 0))
        from PySide6.QtWidgets import QLineEdit
        editor = pv.tabla.viewport().findChild(QLineEdit)
        self.assertIsNotNone(editor)
        QTest.keyClick(editor, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(editor.text(), "Texto")
        self.assertEqual(len(self.nombres()), 2)
