"""SR: dos escenas HTTP falsas, limpieza reversible y maquetación de la ventana."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")
try:
    from PySide6.QtWidgets import QApplication
    from conexion.configuracion import Configuracion
    from conexion.http_directo import ClienteDirecto
    from conexion.uniones import Union
    from escritorio import estilo
    from escritorio.edicion import Edicion
    from escritorio.entradas_salidas import PanelES
    from escritorio.otra_escena import DialogoOtraEscena
    from escritorio.traer_dialogo import DialogoTraer
    from grafcet.builder import M
    from grafcet.editor import Editor
    from servidor_directo_falso import ServidorDirecto, senal
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class CambiarEscena(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        escala_anterior = estilo.ESCALA
        estilo.activar_escala("normal")
        self.addCleanup(estilo.activar_escala, escala_anterior)
        self.escena_a = [senal("a", "Libre"), senal("b", "Motor", papel="Output"), senal("c", "Coincide")]
        self.escena_b = [senal("c-nueva", "Coincide"), senal("nueva", "Sensor de la escena nueva")]
        self.servidor = ServidorDirecto(self.escena_a)
        self.addCleanup(self.servidor.cerrar)
        doc = M().var("libre").var("motor", "output").var("coincide").step("0", True)
        doc.cont("0", "motor")
        self.edicion = Edicion(Editor(doc.doc), "Escena A")
        self.panel = PanelES()
        self.panel.setStyleSheet(estilo.hoja_global())
        self.addCleanup(self.panel.close)
        self.addCleanup(self.panel.deleteLater)
        self.controlador = self.panel.directa
        self.controlador.establecer_edicion(self.edicion)
        config = Configuracion(modo="directo", host="127.0.0.1", puerto=self.servidor.puerto, modelo=doc.doc["id"])
        config.uniones = [Union("libre", "a", "Libre", "Bit", "input"),
                          Union("motor", "b", "Motor", "Bit", "output"),
                          Union("coincide", "c", "Coincide", "Bit", "input")]
        self.panel.cargar(doc.doc, config)
        self.edicion.cambiado.connect(lambda: self.panel.actualizar(self.edicion.ed.model))
        cliente = ClienteDirecto("127.0.0.1", self.servidor.puerto)
        try:
            self.controlador.catalogo = cliente.catalogo()
            self.controlador.catalogo_leido = True
        finally:
            cliente.cerrar()
        self.panel.resize(1366, 700)
        self.panel.show()
        self.app.processEvents()

    def leer_b(self):
        self.servidor.senales = deepcopy(self.escena_b)
        dialogo = DialogoTraer(self.controlador)
        self.addCleanup(dialogo.reject)
        limite = time.monotonic() + 3
        while dialogo.propuestas is None and time.monotonic() < limite:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertIsNotNone(dialogo.propuestas)
        return dialogo

    def test_SR1_resumen_corto_y_detalle_plegado(self):
        d = self.leer_b()
        d.show()
        self.app.processEvents()
        self.assertIn("2 señales leídas", d.estado.text())
        self.assertIn("1 unión se ha vuelto a unir", d.estado.text())
        self.assertIn("2 uniones no están en esta escena", d.estado.text())
        self.assertNotIn("señal no encontrada", d.estado.text())
        self.assertFalse(d.estado.wordWrap())
        self.assertTrue(d.resumen_escena.detalle.isHidden())
        self.assertIn("señal no encontrada", d.estado.toolTip())
        d.resumen_escena.alternar()
        self.assertEqual(d.resumen_escena.detalle.height(), 84)

    def test_SR2_grupo_solo_ausentes_y_casillas_marcadas_por_defecto(self):
        d = self.leer_b()
        grupo = d.otra_escena
        self.assertEqual(grupo.titulo.text(), "De otra escena · 2")
        self.assertEqual({u.id for u in grupo.filas}, {"a", "b"})
        self.assertTrue(all(c.isChecked() for c in grupo.casillas))
        self.assertTrue(grupo.borrar_variables.isChecked())
        self.assertEqual(self.panel.config.uniones[2].id, "c-nueva")

    def test_SR3_quitar_solo_uniones_conserva_variables(self):
        d = self.leer_b()
        grupo = d.otra_escena
        grupo.borrar_variables.setChecked(False)
        grupo.quitar()
        self.assertEqual([u.id for u in self.panel.config.uniones], ["c-nueva"])
        self.assertEqual(len(self.edicion.ed.model["variables"]), 3)
        self.assertNotIn("a", self.controlador.dibujo.terminales)
        self.assertNotIn("b", self.controlador.dibujo.terminales)

    def test_SR4_defecto_borra_libres_y_conserva_usada_con_aviso_de_donde(self):
        d = self.leer_b()
        grupo = d.otra_escena
        grupo.quitar()
        self.assertEqual({v["id"] for v in self.edicion.ed.model["variables"]}, {"motor", "coincide"})
        self.assertIn("motor", grupo.aviso.toPlainText())
        self.assertIn("acción", grupo.aviso.toPlainText())
        self.assertIn(estilo.AVISO, grupo.aviso.styleSheet())
        self.assertFalse(grupo.aviso.isHidden())

    def test_SR5_una_operacion_deshacer_y_rehacer_devuelve_todo(self):
        d = self.leer_b()
        antes = deepcopy(self.panel.config.uniones)
        numero = len(self.edicion.ed.undo_stack)
        d.otra_escena.quitar()
        self.assertEqual(len(self.edicion.ed.undo_stack), numero + 1)
        self.edicion.deshacer()
        self.assertEqual(self.panel.config.uniones, antes)
        self.assertEqual(len(self.edicion.ed.model["variables"]), 3)
        self.assertEqual(len(d.otra_escena.filas), 2)
        self.edicion.rehacer()
        self.assertEqual([u.id for u in self.panel.config.uniones], ["c-nueva"])
        self.assertEqual(len(self.edicion.ed.model["variables"]), 2)

    def test_SR6_boton_del_panel_solo_si_hay_ausentes_y_misma_ventana(self):
        self.controlador.dibujar()
        self.assertTrue(self.controlador.b_quitar_sin_senal.isHidden())
        d = self.leer_b()
        self.assertFalse(self.controlador.b_quitar_sin_senal.isHidden())
        self.controlador.abrir_otra_escena()
        pequeno = self.controlador.dialogo_otra_escena
        self.addCleanup(pequeno.reject)
        self.assertIsInstance(pequeno, DialogoOtraEscena)
        self.assertEqual(len(pequeno.grupo.filas), 2)
        self.assertTrue(pequeno.grupo.borrar_variables.isChecked())
        d.otra_escena.quitar()
        self.assertTrue(self.controlador.b_quitar_sin_senal.isHidden())

    def test_SR7_solo_quita_las_marcadas_y_reunidas_fuera_del_grupo(self):
        d = self.leer_b()
        grupo = d.otra_escena
        grupo.casillas[1].setChecked(False)
        grupo.quitar()
        self.assertEqual({u.id for u in self.panel.config.uniones}, {"b", "c-nueva"})
        self.assertEqual([u.id for u in grupo.filas], ["b"])
        self.assertNotIn("c-nueva", [u.id for u in grupo.filas])

    def test_SR8_auditoria_ventana_a_1366_y_media_pantalla(self):
        from test_auditoria_maquetacion import REGLAS
        d = self.leer_b()
        d.otra_escena.alternar()
        for ancho in (1366, 683):
            with self.subTest(ancho=ancho):
                d.resize(ancho - 32, 610)
                d.show()
                self.app.processEvents()
                for regla in ("M1", "M2", "C1", "C2", "C5", "TB1", "TB2"):
                    self.assertEqual(REGLAS[regla](d), [], regla)
                d.resumen_escena.alternar()
                self.app.processEvents()
                self.assertGreater(d.zona.parentWidget().height(), 100)
                d.resumen_escena.alternar()

    def test_SR9_muchas_ausentes_no_hacen_crecer_el_resumen(self):
        for n in range(25):
            vid = self.edicion.ed.add_variable(f"libre{n}", "input", {"kind": "bool"})
            self.panel.config.uniones.append(Union(vid, f"ausente{n}", f"Antigua {n}", "Bit", "input"))
        self.edicion.cambia()
        d = self.leer_b()
        d.resize(651, 610)
        d.show()
        self.app.processEvents()
        self.assertIn("27 uniones no están en esta escena", d.estado.text())
        self.assertLessEqual(d.estado.height(), d.estado.fontMetrics().height() + 4)
        self.assertTrue(d.resumen_escena.detalle.isHidden())
        self.assertGreater(d.zona.parentWidget().height(), 200)
        d.resumen_escena.alternar()
        self.app.processEvents()
        self.assertEqual(d.resumen_escena.detalle.height(), 84)
        self.assertGreater(d.zona.parentWidget().height(), 150)

    def test_SR10_auditoria_panel_y_ventana_pequena_a_media_pantalla(self):
        from test_auditoria_maquetacion import REGLAS
        self.leer_b()
        pequeno = DialogoOtraEscena(self.controlador)
        self.addCleanup(pequeno.reject)
        for ancho in (1366, 683):
            with self.subTest(ancho=ancho):
                self.panel.resize(ancho, 700)
                pequeno.resize(min(720, ancho - 32), 420)
                pequeno.show()
                self.app.processEvents()
                for raiz in (pequeno, self.panel):
                    for regla in ("M1", "M2", "C1", "C2", "C5", "TB1", "TB2"):
                        self.assertEqual(REGLAS[regla](raiz), [], regla)

    def test_SR11_ctrl_z_en_el_grupo_recupera_las_variables(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        d = self.leer_b()
        grupo = d.otra_escena
        grupo.alternar()
        d.show()
        self.app.processEvents()
        grupo.quitar()
        grupo.borrar_variables.setFocus()
        QTest.keyClick(grupo.borrar_variables, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.app.processEvents()
        self.assertEqual(len(self.edicion.ed.model["variables"]), 3)
        self.assertEqual(len(self.panel.config.uniones), 3)


if __name__ == "__main__":
    unittest.main()
