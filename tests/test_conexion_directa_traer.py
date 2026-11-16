"""SCD: catálogo HTTP, diálogo, creación y deshacer (I2)."""
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from conexion.configuracion import Configuracion
from conexion.http_directo import ClienteDirecto, ErrorDirecto
from conexion.uniones import Union
from escritorio.edicion import Edicion
from escritorio.entradas_salidas import NIVEL_ACTIVO, PanelES
from escritorio.traer_modelo import HistorialUniones, Propuestas, de_fabrica, interna, proponer, traer
from escritorio.traer_dialogo import DialogoTraer
from grafcet.editor import Editor, new_grafcet_document
from servidor_directo_falso import ServidorDirecto, senal


class TraerES(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.edicion = Edicion(Editor(new_grafcet_document("m")), "Prueba")
        self.config = Configuracion(host="localhost", puerto=7410, modo="directo")

    def test_SCD10_propuestas_neutras_y_validacion_compartida(self):
        for original, esperado in (("Pick & Place 0 (Grab)", "Pick y Place 0 Grab"),
                ("Chain Transfer 0 (+)", "Chain Transfer 0+"), (" Motor  (-) ", "Motor-")):
            self.assertEqual(proponer(original), esperado)
        for nombre in ("Emergency Stop 0", "Pick & Place 0 (Grab)", "Light Indicator (Green) 0"):
            self.assertTrue(de_fabrica(nombre))
        catalogo = [senal("a", "Marcha"), senal("b", "Emergency Stop 0"), senal("c", "Xmotor inicio"),
                    senal("d", ""), senal("e", "-"), senal("f", "Simulador I/O (Running)", direccion=496)]
        propuestas = Propuestas(self.edicion, self.config, catalogo)
        self.assertEqual(len(propuestas.filas), 3)
        self.assertEqual([f.marcada for f in propuestas.filas], [True, False, True])
        fila = propuestas.filas[2]
        self.assertEqual(fila.motivo, self.edicion.motivo_variable_nueva(fila.nombre))
        self.assertTrue(interna(catalogo[-1]))

    def test_SCD11_crear_tres_tipos_unir_y_deshacer_una_vez(self):
        historial = HistorialUniones()
        catalogo = [senal("a", "Marcha"), senal("b", "Cuenta", "Int"),
                    senal("c", "Velocidad", "Float", "Output")]
        propuestas = Propuestas(self.edicion, self.config, catalogo)
        resumen = traer(propuestas, historial)
        self.assertIn("3 creadas", resumen)
        self.assertEqual([v["type"]["kind"] for v in self.edicion.ed.model["variables"]], ["bool", "int", "decimal"])
        self.assertEqual(len(self.config.uniones), 3)
        self.assertEqual(len(self.edicion.ed.undo_stack), 1)
        self.edicion.deshacer()
        historial.sincronizar(self.edicion.ed, self.config)
        self.assertEqual(self.edicion.ed.model["variables"], [])
        self.assertEqual(self.config.uniones, [])
        self.edicion.rehacer()
        historial.sincronizar(self.edicion.ed, self.config)
        self.assertEqual(len(self.config.uniones), 3)

    def test_SCD12_existente_ya_traida_y_conflicto(self):
        self.edicion.nueva_variable("Marcha")
        propuestas = Propuestas(self.edicion, self.config, [senal("a", "Marcha")])
        self.assertTrue(propuestas.filas[0].existente)
        self.assertIn("1 unidas", traer(propuestas, HistorialUniones()))
        propuestas = Propuestas(self.edicion, self.config, [senal("a", "Marcha"), senal("b", "Marcha", papel="Output")])
        self.assertEqual(propuestas.filas[0].ya, "Marcha")
        self.assertFalse(propuestas.filas[0].marcada)
        self.assertIn("Ya hay", propuestas.filas[1].motivo)

    def test_SCD13_repetidos_impiden_crear_dos_variables(self):
        propuestas = Propuestas(self.edicion, self.config, [senal("a", "Marcha"), senal("b", "Marcha")])
        self.assertEqual(propuestas.pendientes(), 2)
        with self.assertRaises(ValueError):
            traer(propuestas, HistorialUniones())
        self.assertEqual(self.edicion.ed.model["variables"], [])

    def test_SCD14_http_errores_y_sin_servidor(self):
        servidor = ServidorDirecto([senal("a", "Marcha")])
        self.addCleanup(servidor.cerrar)
        cliente = ClienteDirecto("127.0.0.1", servidor.puerto)
        self.addCleanup(cliente.cerrar)
        self.assertEqual(cliente.catalogo()[0]["name"], "Marcha")
        for codigo in (404, 406, 500):
            servidor.error = codigo
            with self.assertRaisesRegex(ErrorDirecto, str(codigo)):
                cliente.catalogo()
        servidor.error = 0
        servidor.no_json = True
        with self.assertRaisesRegex(ErrorDirecto, "no parece"):
            cliente.catalogo()
        import socket
        with socket.socket() as cerrado:
            cerrado.bind(("127.0.0.1", 0))
            puerto = cerrado.getsockname()[1]
        cliente = ClienteDirecto("127.0.0.1", puerto, timeout=0.1)
        with self.assertRaisesRegex(ErrorDirecto, "app.web_server = True"):
            cliente.catalogo()
        cliente.cerrar()

    def test_SCD15_dialogo_grupos_rojo_verde_y_boton(self):
        servidor = ServidorDirecto([senal("a", "Marcha"), senal("b", "Xmotor inicio"),
                                   senal("c", "Simulador I/O (Running)", direccion=496)])
        self.addCleanup(servidor.cerrar)
        panel = PanelES()
        self.addCleanup(panel.close)
        panel.directa.edicion = self.edicion
        self.config.host = "127.0.0.1"
        self.config.puerto = servidor.puerto
        panel.cargar(self.edicion.ed.model, self.config)
        dialogo = DialogoTraer(panel.directa)
        self.addCleanup(dialogo.reject)
        limite = time.monotonic() + 3
        while dialogo.propuestas is None and time.monotonic() < limite:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertIsNotNone(dialogo.propuestas)
        self.assertEqual(len(dialogo.tablas), 3)
        self.assertFalse(dialogo.b_traer.isEnabled())
        self.assertIn("1 por corregir", dialogo.b_traer.text())
        tabla, filas = dialogo.tablas[0]
        tabla.item(1, 2).setText("Inicio")
        self.assertTrue(filas[1].cambiado)
        self.assertTrue(dialogo.b_traer.isEnabled())
        from escritorio import estilo
        self.assertEqual(tabla.item(1, 2).foreground().color().name(), estilo.OK)

    def test_SCD16_importacion_del_dialogo_y_deshacer_con_panel_conectado(self):
        servidor = ServidorDirecto([senal("a", "Marcha"), senal("b", "Motor", papel="Output")])
        self.addCleanup(servidor.cerrar)
        panel = PanelES()
        self.addCleanup(panel.close)
        panel.directa.establecer_edicion(self.edicion)
        self.config.host = "127.0.0.1"
        self.config.puerto = servidor.puerto
        self.config.modelo = self.edicion.ed.model["id"]
        panel.cargar(self.edicion.ed.model, self.config)
        dialogo = DialogoTraer(panel.directa)
        self.addCleanup(dialogo.reject)
        limite = time.monotonic() + 3
        while dialogo.propuestas is None and time.monotonic() < limite:
            self.app.processEvents()
            time.sleep(0.005)
        dialogo.importar()
        self.addCleanup(panel.directa.dialogo_resumen.close)
        self.assertEqual(len(panel.config.uniones), 2)
        self.edicion.deshacer()
        self.assertEqual(panel.config.uniones, [])
        self.assertEqual(self.edicion.ed.model["variables"], [])
        self.edicion.rehacer()
        self.assertEqual(len(panel.config.uniones), 2)
        panel.mostrar_muestra({panel.config.uniones[0].variable: True}, panel.config.uniones)
        self.assertEqual(panel.directa.dibujo.terminales["a"].valor.text(), "")
        self.assertEqual(panel.directa.dibujo.terminales["a"].led.nivel, NIVEL_ACTIVO)

    def test_SCD17_dos_importaciones_deshacer_y_rehacer_seguidas(self):
        historial = HistorialUniones()
        for catalogo in ([senal("a", "Marcha")], [senal("b", "Motor", papel="Output")]):
            traer(Propuestas(self.edicion, self.config, catalogo), historial)
        self.edicion.ed.undo()
        self.edicion.ed.undo()
        historial.sincronizar(self.edicion.ed, self.config)
        self.assertEqual(self.config.uniones, [])
        self.edicion.ed.redo()
        self.edicion.ed.redo()
        historial.sincronizar(self.edicion.ed, self.config)
        self.assertEqual(len(self.config.uniones), 2)


if __name__ == "__main__":
    unittest.main()
