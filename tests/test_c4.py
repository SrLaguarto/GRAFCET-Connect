"""Comprobaciones de presentación y reintento de E/S externas (tanda C4)."""
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_modbus_panel as pruebas_modbus
from test_modbus import servidor

from conexion.configuracion import Configuracion, Senal
from grafcet.builder import M


@unittest.skipUnless(pruebas_modbus.QT, "Falta PySide6")
class InterfazC4(unittest.TestCase):
    def test_SC401_reintenta_tras_un_fallo_real_con_el_destino_actual(self):
        from PySide6.QtWidgets import QApplication
        from escritorio.ventana import Ventana

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as rechazado:
            rechazado.bind(("127.0.0.1", 0))  # puerto reservado, sin escuchar
            w = Ventana(pruebas_modbus.ajustes_de_prueba(tmp))
            doc = M().var("sensor").step("E0", True).doc
            w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": doc,
                        "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
            try:
                w._cargar()
                panel = w.panel_es
                panel.cargar(doc, Configuracion(host="127.0.0.1", puerto=rechazado.getsockname()[1],
                                                modelo=doc["id"], senales=[Senal("sensor", "discrete", 0)],
                                                timeout_ms=500))
                w.show()
                w.mostrar_es()
                self.assertTrue(panel.b_conectar.isVisible())
                panel.b_conectar.click()
                pruebas_modbus.PanelTests._esperar(
                    app, w, lambda: panel.b_reintentar.isVisible() and panel.b_reintentar.isEnabled()
                )
                with w.candado:
                    mensaje = w.modbus.mensaje
                self.assertEqual(panel.estado.text(), mensaje)
                self.assertIn("Salidas no garantizadas", panel.estado.text())
                self.assertIn("Detalle:", panel.estado.text())
                self.assertTrue(panel.pastilla_conexion.isHidden())

                with servidor(pruebas_modbus.PanelTests._servidor_planta([])) as planta:
                    panel.puerto.setValue(planta.puerto)
                    panel.b_reintentar.click()
                    pruebas_modbus.PanelTests._esperar(app, w, panel.pastilla_conexion.isVisible)
                    self.assertEqual(panel.pastilla_conexion.text(), f"● Conectado · 127.0.0.1:{planta.puerto}")
                    self.assertTrue(panel.b_conectar.isHidden())
                    self.assertTrue(panel.b_reintentar.isHidden())
                    self.assertEqual(panel.b_desconectar.text(), "Desconectar")
                    panel.b_desconectar.click()
                    pruebas_modbus.PanelTests._esperar(app, w, panel.b_conectar.isVisible)
                    self.assertTrue(panel.pastilla_conexion.isHidden())
                    self.assertEqual(w.paginas_es.currentIndex(), 1)
            finally:
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SC402_configuraciones_usan_la_cabecera_y_el_pie_comunes(self):
        from PySide6.QtWidgets import QApplication
        from escritorio.componentes_comunes import CabeceraDialogo, PieDialogo
        from escritorio.entradas_salidas import PanelES
        from escritorio.filtro_senales import ConfiguracionDirecta

        app = QApplication.instance() or QApplication([])
        panel = PanelES()
        doc = M().step("E0", True).doc
        panel.cargar(doc, Configuracion())
        try:
            panel.abrir_configuracion()
            modbus = panel.dialogo_config
            pie = modbus.findChild(PieDialogo)
            self.assertEqual(modbus.findChild(CabeceraDialogo).etiqueta_titulo.text(), modbus.windowTitle())
            self.assertEqual(pie.boton_aceptar.text(), "Cerrar")
            self.assertTrue(pie.boton_cancelar.isHidden())
            pie.boton_aceptar.click()
            self.assertFalse(modbus.isVisible())

            panel.cargar(doc, Configuracion(host="localhost", puerto=7410, modo="directo"))
            directa = ConfiguracionDirecta(panel.directa)
            self.assertEqual(directa.findChild(CabeceraDialogo).etiqueta_titulo.text(), directa.windowTitle())
            pie = directa.findChild(PieDialogo)
            self.assertEqual((pie.boton_cancelar.text(), pie.boton_aceptar.text()), ("Cancelar", "Aceptar"))
            pie.boton_aceptar.click()
            self.assertEqual(directa.result(), directa.DialogCode.Accepted)
        finally:
            panel.dialogo_config.close()
            panel.close()
            panel.deleteLater()
            app.processEvents()

    def test_SC403_la_ayuda_del_servidor_conserva_el_aviso_de_salidas(self):
        from PySide6.QtWidgets import QApplication
        from conexion.http_directo import sin_servidor
        from escritorio.entradas_salidas import PanelES

        app = QApplication.instance() or QApplication([])
        panel = PanelES()
        doc = M().step("E0", True).doc
        panel.cargar(doc, Configuracion(host="localhost", puerto=7410, modo="directo"))
        try:
            with patch("conexion.servidor_web_simulador.estado", return_value="activo"):
                panel.mostrar_estado("error", f"{sin_servidor('localhost', 7410)} Salidas no garantizadas.")
            self.assertIn("El simulador de fábricas no responde (localhost:7410)", panel.estado.text())
            self.assertIn("Salidas no garantizadas.", panel.estado.text())
            self.assertFalse(panel.b_reintentar.isHidden())
        finally:
            panel.close()
            panel.deleteLater()
            app.processEvents()
