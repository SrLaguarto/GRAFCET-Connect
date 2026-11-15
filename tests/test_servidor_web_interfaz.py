"""SM1: ayuda en conexión y Traer E/S, sin usar Documentos reales ni un simulador externo."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

if QT:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication
    from conexion import servidor_web_simulador as servidor
    from conexion.configuracion import Configuracion
    from conexion.http_directo import ClienteDirecto, ErrorDirecto, sin_servidor
    from escritorio import estilo
    from escritorio.ayuda_servidor_web import HECHO, YA_ACTIVO
    from escritorio.edicion import Edicion
    from escritorio.entradas_salidas import PanelES
    from escritorio.traer_dialogo import DialogoTraer
    from grafcet.builder import M
    from grafcet.editor import Editor

@unittest.skipUnless(QT, "requiere PySide6")
class AyudaWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        estilo.activar_escala("normal")
        self.addCleanup(estilo.activar_escala, "normal")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.docs = Path(self.tmp.name)
        parche = patch.object(servidor, "documentos_usuario", return_value=self.docs)
        parche.start()
        self.addCleanup(parche.stop)
        self.paneles = []
        self.dialogos = []

    def tearDown(self):
        for dialogo in self.dialogos:
            dialogo.reject()
        for panel in self.paneles:
            panel.hide()
            panel.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def firma(self, activo=False):
        p = self.docs / "planta"
        (p / "My Scenes").mkdir(parents=True)
        (p / "CertificatesStore").mkdir()
        if activo:
            (p / "auto.cfg").write_bytes(b"app.web_server=True\r\n")
        return p

    def panel(self, modo="directo"):
        doc = M().var("sensor").step("0", True).doc
        panel = PanelES()
        self.paneles.append(panel)
        panel.cargar(doc, Configuracion(modelo=doc["id"], modo=modo))
        panel.directa.establecer_edicion(Edicion(Editor(doc), "Servidor web"))
        panel.resize(1366, 650)
        panel.show()
        self.app.processEvents()
        return panel

    def esperar(self, condicion):
        fin = time.monotonic() + 4
        while not condicion():
            self.app.processEvents()
            if time.monotonic() > fin:
                self.fail("No terminó la operación de la interfaz")
            time.sleep(0.002)

    def test_SM114_falta_boton_activa_y_mantiene_resultado(self):
        carpeta = self.firma()
        p = self.panel()
        mensaje = sin_servidor("localhost", 7410)
        p.mostrar_estado("error", mensaje)
        ayuda = p.directa.ayuda_servidor
        self.assertTrue(ayuda.boton.isVisible())
        self.assertEqual(ayuda.boton.height(), estilo.ALTO_CONTROL)
        ayuda.boton.click()
        self.assertIn(HECHO, p.estado.text())
        self.assertFalse(ayuda.boton.isVisible())
        self.assertEqual((carpeta / "auto.cfg").read_bytes(), b"app.web_server = True\r\n")
        p.mostrar_estado("error", mensaje)
        self.assertIn(HECHO, p.estado.text())

    def test_SM115_activo_avisa_reinicio_sin_boton(self):
        self.firma(True)
        p = self.panel()
        p.mostrar_estado("error", sin_servidor("localhost", 7410))
        self.assertFalse(p.directa.ayuda_servidor.boton.isVisible())
        self.assertIn(YA_ACTIVO, p.estado.text())
        self.assertIn("None", p.estado.text())
        self.assertIn("7410", p.estado.text())

    def test_SM116_sin_carpeta_y_varias_sin_boton(self):
        p = self.panel()
        mensaje = sin_servidor("localhost", 7410)
        p.mostrar_estado("error", mensaje)
        self.assertFalse(p.directa.ayuda_servidor.boton.isVisible())
        self.assertIn("auto.cfg", p.estado.text())
        self.firma()
        (self.docs / "otra/My Scenes").mkdir(parents=True)
        (self.docs / "otra/CertificatesStore").mkdir()
        p.mostrar_estado("conectando", "Conectando")
        p.mostrar_estado("error", mensaje)
        self.assertFalse(p.directa.ayuda_servidor.boton.isVisible())
        self.assertIn("auto.cfg", p.estado.text())

    def test_SM117_modbus_y_exito_no_consultan_configuracion(self):
        for modo, estado in (("modbus", "error"), ("directo", "conectado")):
            p = self.panel(modo)
            with patch.object(servidor, "estado") as comprobar:
                p.mostrar_estado(estado, sin_servidor("localhost", 7410))
                comprobar.assert_not_called()
            self.assertFalse(p.directa.ayuda_servidor.boton.isVisible())

    def test_SM118_error_permiso_se_muestra_sin_danar(self):
        carpeta = self.firma()
        p = self.panel()
        p.mostrar_estado("error", sin_servidor("localhost", 7410))
        with patch.object(servidor.tempfile, "NamedTemporaryFile", side_effect=PermissionError("Sin permiso")):
            p.directa.ayuda_servidor.boton.click()
        self.assertIn("Sin permiso", p.estado.text())
        self.assertFalse((carpeta / "auto.cfg").exists())

    def test_SM119_traer_caido_ofrece_activar_y_luego_ya_activo(self):
        carpeta = self.firma()
        p = self.panel()
        with patch.object(ClienteDirecto, "catalogo", side_effect=ErrorDirecto(sin_servidor("localhost", 7410))):
            dialogo = DialogoTraer(p.directa)
            self.dialogos.append(dialogo)
            dialogo.show()
            self.esperar(lambda: dialogo.futuro is None)
            self.assertTrue(dialogo.ayuda_servidor.boton.isVisible())
            dialogo.ayuda_servidor.boton.click()
            self.assertEqual(dialogo.estado.text(), HECHO)
            self.assertTrue((carpeta / "auto.cfg").exists())
            dialogo.leer()
            self.esperar(lambda: dialogo.futuro is None)
            self.assertFalse(dialogo.ayuda_servidor.boton.isVisible())
            self.assertIn(YA_ACTIVO, dialogo.estado.text())

    def test_SM120_respuesta_http_erronea_no_es_servidor_ausente(self):
        self.firma()
        p = self.panel()
        with patch.object(servidor, "estado") as comprobar:
            p.mostrar_estado("error", "HTTP 404: Not Found")
            comprobar.assert_not_called()
        self.assertFalse(p.directa.ayuda_servidor.boton.isVisible())


    def test_SM121_conectar_real_propaga_la_ayuda_del_fallo(self):
        from test_editor_cadenas import BaseQt
        self.firma()
        caso = BaseQt()
        caso.setUp()
        self.addCleanup(caso.tearDown)
        w, _ = caso.vacio()
        try:
            w.mostrar_es()
            w.show()
            w.panel_es.directa.selector.setCurrentIndex(1)
            with patch.object(ClienteDirecto, "catalogo", side_effect=ErrorDirecto(sin_servidor("localhost", 7410))):
                w._conectar_modbus()
                self.esperar(lambda: w.modbus.estado == "error")
                self.app.processEvents()
                self.assertTrue(w.panel_es.directa.ayuda_servidor.boton.isVisible())
        finally:
            w.modbus.cerrar()
            w.hide()


    def test_SM124_avisos_y_boton_pasan_auditoria_en_ambas_escalas(self):
        import test_auditoria_maquetacion as auditoria
        self.firma()
        p = self.panel()
        for ancho, alto, escala in ((1366, 768, "normal"), (2000, 1250, "grande")):
            estilo.activar_escala(escala)
            p.escalar(estilo.hoja_global(), escala)
            p.resize(ancho, alto)
            p.mostrar_estado("error", sin_servidor("localhost", 7410))
            for _ in range(8):
                self.app.processEvents()
            for regla, comprobar in auditoria.REGLAS.items():
                if regla in ("B1", "B2"):
                    continue
                malos = [x for x in comprobar(p) if not auditoria.permitida(regla, x)]
                self.assertEqual(malos, [], (ancho, regla, malos))
            self.assertEqual(p.directa.ayuda_servidor.boton.height(), estilo.ALTO_CONTROL)
        estilo.activar_escala("normal")


    def test_SM125_aviso_de_traer_pasa_auditoria_en_ambas_escalas(self):
        import test_auditoria_maquetacion as auditoria
        self.firma()
        p = self.panel()
        with patch.object(ClienteDirecto, "catalogo", side_effect=ErrorDirecto(sin_servidor("localhost", 7410))):
            for ancho, alto, escala in ((1366, 768, "normal"), (2000, 1250, "grande")):
                estilo.activar_escala(escala)
                dialogo = DialogoTraer(p.directa)
                self.dialogos.append(dialogo)
                dialogo.resize(ancho, alto)
                dialogo.show()
                self.esperar(lambda: dialogo.futuro is None)
                for _ in range(8):
                    self.app.processEvents()
                for regla, comprobar in auditoria.REGLAS.items():
                    if regla in ("B1", "B2"):
                        continue
                    malos = [x for x in comprobar(dialogo) if not auditoria.permitida(regla, x)]
                    self.assertEqual(malos, [], (ancho, regla, malos))
                self.assertTrue(dialogo.ayuda_servidor.boton.isVisible())
                self.assertEqual(dialogo.ayuda_servidor.boton.height(), estilo.ALTO_CONTROL)
                dialogo.reject()


if __name__ == "__main__":
    unittest.main()
