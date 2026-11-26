"""SU: equipos del centro, detección por contenido y ayuda completa con Documentos temporales."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from conexion import servidor_web_simulador as servidor
from escritorio.arranque_servidor_web import ARGUMENTO, despachar
from test_servidor_web_interfaz import AyudaWebBase, QT

if QT:
    from PySide6.QtGui import QFontMetrics
    from conexion.http_directo import ClienteDirecto, ErrorDirecto, sin_servidor
    from escritorio.ayuda_servidor_web import MANUAL
    from escritorio.traer_dialogo import DialogoTraer
    from servidor_directo_falso import ServidorDirecto, senal


class DeteccionCentro(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.docs = Path(temporal.name)
        parche = patch.object(servidor, "documentos_usuario", return_value=self.docs)
        parche.start()
        self.addCleanup(parche.stop)

    def carpeta(self, nombre, indicio=None):
        carpeta = self.docs / nombre
        (carpeta / "My Scenes").mkdir(parents=True)
        if indicio == "auto.cfg":
            (carpeta / indicio).write_bytes(b"otra = 3\n")
        elif indicio:
            (carpeta / indicio).mkdir()
        return carpeta

    def test_SU1_centro_detectado_y_activado_por_arranque_del_instalador(self):
        carpeta = self.carpeta("planta del aula", "Screenshots")
        self.assertEqual(servidor.buscar_carpeta(), carpeta)
        self.assertEqual(despachar([ARGUMENTO], self.docs), 0)
        self.assertEqual((carpeta / "auto.cfg").read_bytes(), b"app.web_server = True\r\n")

    def test_SU2_cada_indicio_desempata_frente_a_my_scenes_solo(self):
        simple = self.carpeta("sin indicios")
        for indicio in ("CertificatesStore", "Screenshots", "auto.cfg"):
            with self.subTest(indicio=indicio):
                preferida = self.carpeta(indicio, indicio)
                self.assertEqual(servidor.buscar_carpeta(), preferida)
                self.assertTrue(servidor.activar().correcto)
                self.assertFalse((simple / "auto.cfg").exists())
                for item in preferida.iterdir():
                    if item.is_dir():
                        item.rmdir()
                    else:
                        item.unlink()
                preferida.rmdir()

    def test_SU3_empates_no_escriben_ni_ponderan_numero_de_indicios(self):
        primera = self.carpeta("primera", "Screenshots")
        segunda = self.carpeta("segunda", "CertificatesStore")
        (segunda / "auto.cfg").write_bytes(b"app.web_server = False\n")
        self.assertEqual(servidor.estado(), "varias")
        self.assertFalse(servidor.activar().correcto)
        self.assertFalse((primera / "auto.cfg").exists())
        self.assertEqual((segunda / "auto.cfg").read_bytes(), b"app.web_server = False\n")
        (primera / "Screenshots").rmdir()
        (segunda / "CertificatesStore").rmdir()
        (segunda / "auto.cfg").unlink()
        self.assertEqual(servidor.estado(), "varias")
        self.assertFalse(servidor.activar().correcto)
        self.assertFalse(list(self.docs.rglob("auto.cfg")))


@unittest.skipUnless(QT, "requiere PySide6")
class InterfazCentro(AyudaWebBase):
    def solo_escenas(self):
        carpeta = self.docs / "planta del centro"
        (carpeta / "My Scenes").mkdir(parents=True)
        return carpeta

    def caida(self, panel):
        fallo = ErrorDirecto(sin_servidor("localhost", 7410))
        with patch.object(ClienteDirecto, "catalogo", side_effect=fallo):
            dialogo = DialogoTraer(panel.directa)
            self.dialogos.append(dialogo)
            dialogo.show()
            self.esperar(lambda: dialogo.futuro is None)
        return dialogo

    def test_SU4_extremo_a_extremo_conectar_solo_my_scenes_y_activar(self):
        from test_editor_cadenas import BaseQt
        carpeta = self.solo_escenas()
        (carpeta / "auto.cfg").write_bytes(b"otra = 42\n")
        caso = BaseQt()
        caso.setUp()
        self.addCleanup(caso.tearDown)
        ventana, _ = caso.vacio()
        ventana.show()
        ventana.mostrar_es()
        ventana.panel_es.directa.selector.setCurrentIndex(1)
        self.addCleanup(ventana.modbus.cerrar)
        fallo = ErrorDirecto(sin_servidor("localhost", 7410))
        with patch.object(ClienteDirecto, "catalogo", side_effect=fallo):
            ventana._conectar_modbus()
            self.esperar(lambda: ventana.modbus.estado == "error")
        self.app.processEvents()
        boton = ventana.panel_es.directa.ayuda_servidor.boton
        self.assertTrue(boton.isVisible())
        boton.click()
        self.assertEqual((carpeta / "auto.cfg").read_bytes(), b"otra = 42\napp.web_server = True\n")
        self.assertFalse(boton.isVisible())

    def test_SU5_sin_carpeta_o_empate_pista_manual_sin_escritura(self):
        panel = self.panel()
        for empate in (False, True):
            with self.subTest(empate=empate):
                if empate:
                    self.solo_escenas()
                    (self.docs / "otra/My Scenes").mkdir(parents=True)
                panel.mostrar_estado("conectando", "Conectando")
                panel.mostrar_estado("error", sin_servidor("localhost", 7410))
                self.assertIn(MANUAL, panel.estado.text())
                self.assertFalse(panel.directa.ayuda_servidor.boton.isVisible())
                dialogo = self.caida(panel)
                self.assertIn(MANUAL, dialogo.ayuda_lectura.etiqueta.text())
                self.assertFalse(dialogo.ayuda_servidor.boton.isVisible())
                dialogo.reject()
                self.assertFalse(list(self.docs.rglob("auto.cfg")))

    def test_SU6_traer_ayuda_completa_medidas_captura_y_activacion(self):
        import test_auditoria_maquetacion as auditoria
        carpeta = self.solo_escenas()
        panel = self.panel()
        dialogo = self.caida(panel)
        etiqueta = dialogo.ayuda_lectura.etiqueta
        for ancho in (1366, 960):
            with self.subTest(ancho=ancho):
                dialogo.resize(ancho, 768)
                for _ in range(8):
                    self.app.processEvents()
                self.assertTrue(dialogo.ayuda_servidor.boton.isVisible())
                self.assertTrue(dialogo.ayuda_lectura.isVisible())
                self.assertTrue(etiqueta.wordWrap())
                for texto in ("Activar el servidor web", "Reinicie", "«Ninguno»", "Volver a leer"):
                    self.assertIn(texto, etiqueta.text())
                self.assertNotIn("…", etiqueta.text())
                necesario = etiqueta.heightForWidth(etiqueta.width())
                self.assertGreaterEqual(etiqueta.height(), necesario)
                self.assertTrue(dialogo.ayuda_lectura.rect().contains(etiqueta.geometry()))
                boton = dialogo.ayuda_servidor.boton
                self.assertGreaterEqual(boton.width(), QFontMetrics(boton.font()).horizontalAdvance(boton.text()))
                for regla, comprobar in auditoria.REGLAS.items():
                    if regla in ("B1", "B2"):
                        continue
                    malos = [x for x in comprobar(dialogo) if not auditoria.permitida(regla, x)]
                    self.assertEqual(malos, [], (ancho, regla))
                captura = os.environ.get("U_CAPTURAS")
                if captura:
                    salida = Path(captura)
                    salida.mkdir(parents=True, exist_ok=True)
                    dialogo.grab().save(str(salida / f"traer_centro_{ancho}.png"))
        dialogo.ayuda_servidor.boton.click()
        self.assertEqual((carpeta / "auto.cfg").read_bytes(), b"app.web_server = True\r\n")
        self.assertIn("Hecho", etiqueta.text())
        self.assertIn("Volver a leer", dialogo.estado.text())
        self.assertNotIn("Pulse «Activar", etiqueta.text())

    def test_SU7_volver_a_leer_catalogo_http_oculta_ayuda_y_muestra_tablas(self):
        self.solo_escenas()
        panel = self.panel()
        dialogo = self.caida(panel)
        falso = ServidorDirecto([senal("a", "Marcha")])
        self.addCleanup(falso.cerrar)
        panel.directa.host.setText("127.0.0.1")
        panel.directa.puerto.setValue(falso.puerto)
        dialogo.b_leer.click()
        self.esperar(lambda: dialogo.futuro is None)
        self.assertIsNotNone(dialogo.propuestas)
        self.assertFalse(dialogo.ayuda_lectura.isVisible())
        self.assertFalse(dialogo.ayuda_servidor.boton.isVisible())
        self.assertEqual(len(dialogo.tablas), 2)
        self.assertTrue(dialogo.b_traer.isEnabled())


if __name__ == "__main__":
    unittest.main()
