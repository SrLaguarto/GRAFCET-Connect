"""SV: medición explícita sin filtro global y selector de acciones con ratón y teclado."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QFont
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio import campos_medidos as campos
    from escritorio.acciones import _ComboVariable
    from tools import hoja_contactos as hc
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class LagYDesplegable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = hc.aplicacion()

    def test_SV1_instalar_no_intercepta_eventos_de_la_aplicacion(self):
        anterior = self.app.property("camposMedidos")
        self.app.setProperty("camposMedidos", None)
        nueva = None
        try:
            with patch.object(self.app, "installEventFilter") as instalar_filtro:
                nueva = campos.instalar()
                self.assertIs(campos.instalar(), nueva)
                instalar_filtro.assert_not_called()
            self.assertNotIn("eventFilter", vars(campos.CamposMedidos))
        finally:
            self.app.setProperty("camposMedidos", anterior)
            if nueva is not None:
                nueva.deleteLater()

    def test_SV2_cambio_de_valor_mide_solo_si_cambian_las_cifras(self):
        spin = campos.SpinMedido()
        self.addCleanup(spin.deleteLater)
        self.addCleanup(spin.close)
        spin.setRange(0, 65535)
        spin.setProperty("digitosColumna", 3)
        spin.show()
        hc._bombear(8)
        with patch.object(campos, "ajustar", wraps=campos.ajustar) as medir:
            for valor in (10, 20, 100, 501, 999):
                spin.setValue(valor)
            self.assertEqual(medir.call_count, 0)
            ancho = spin.width()
            spin.setValue(1000)
            self.assertEqual(medir.call_count, 1)
            self.assertGreater(spin.width(), ancho)
            spin.setValue(1001)
            self.assertEqual(medir.call_count, 1)
            spin.setValue(99)
            self.assertEqual(medir.call_count, 2)
            self.assertEqual(spin.width(), ancho)

    def comprobar_escala(self, factor):
        entorno = dict(os.environ, QT_SCALE_FACTOR=str(factor), PYTHONIOENCODING="utf-8")
        resultado = subprocess.run([sys.executable, str(ROOT / "tests/ayuda_sv_desplegable.py")],
                                   cwd=ROOT, env=entorno, capture_output=True, text=True, encoding="utf-8", timeout=35)
        self.assertEqual(resultado.returncode, 0, (resultado.stdout or "") + (resultado.stderr or ""))
        datos = json.loads(resultado.stdout.strip().splitlines()[-1])
        self.assertEqual({d["tipo"] for d in datos}, {"condicionada", "evento", "continua_sobre_dibujo"})
        self.assertTrue(all(d["raton"] and d["teclado"] and d["esc"] for d in datos))

    def test_SV3_selector_abre_elige_y_cierra_al_100(self):
        self.comprobar_escala(1)

    def test_SV4_selector_abre_elige_y_cierra_al_125(self):
        self.comprobar_escala(1.25)

    def test_SV5_selector_abre_elige_y_cierra_al_150(self):
        self.comprobar_escala(1.5)

    def test_SV6_fuentes_se_notifican_una_vez_y_actualizan_la_medida(self):
        spin = campos.SpinMedido()
        self.addCleanup(spin.deleteLater)
        self.addCleanup(spin.close)
        spin.setRange(0, 10000)
        spin.show()
        hc._bombear(8)
        politica = campos.instalar()
        emisiones = []
        recibir = lambda: emisiones.append(True)
        politica.fuentes_cambiadas.connect(recibir)
        self.addCleanup(politica.fuentes_cambiadas.disconnect, recibir)
        with patch.object(campos, "ajustar", wraps=campos.ajustar) as medir:
            fuente = QFont(spin.font())
            fuente.setPixelSize(24)
            spin.setFont(fuente)
            campos.notificar_fuentes()
            campos.notificar_fuentes()
            hc._bombear(8)
            self.assertEqual(len(emisiones), 1)
            self.assertEqual(medir.call_count, 1)
            self.assertEqual(spin.width(), campos.ancho_numero(spin))

    def test_SV7_arrastre_y_layout_no_recalculan_campos_existentes(self):
        c = hc.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        hc._edicion(c)
        QTest.qWait(700)
        vista = c.w.diagrama.viewport()
        mime = QMimeData()
        mime.setText("etapa")
        boton = Qt.MouseButton.LeftButton
        nada = Qt.KeyboardModifier.NoModifier
        with patch.object(campos, "ajustar", wraps=campos.ajustar) as medir:
            QApplication.sendEvent(vista, QDragEnterEvent(QPoint(320, 180), Qt.CopyAction, mime, boton, nada))
            for i in range(200):
                evento = QDragMoveEvent(QPoint(320 + i % 140, 180 + i % 80), Qt.CopyAction, mime, boton, nada)
                QApplication.sendEvent(vista, evento)
                QApplication.sendEvent(c.w.panel_es, QEvent(QEvent.Type.LayoutRequest))
                self.app.processEvents()
            self.assertEqual(medir.call_count, 0)
            antes = len(c.e.ed.model["steps"])
            punto = QPoint(vista.width() - 70, vista.height() - 70)
            QApplication.sendEvent(vista, QDragMoveEvent(punto, Qt.CopyAction, mime, boton, nada))
            evento = QDropEvent(QPointF(punto), Qt.CopyAction, mime, boton, nada)
            QApplication.sendEvent(vista, evento)
            hc._bombear(8)
            self.assertEqual(len(c.e.ed.model["steps"]), antes + 1)
            self.assertLessEqual(medir.call_count, 64, "Solo los campos concretos creados al actualizar el modelo")

    def test_SV8_los_combos_heredan_el_estilo_de_la_aplicacion(self):
        for clase in (_ComboVariable, campos.ComboMedido):
            with self.subTest(clase=clase.__name__):
                combo = clase()
                self.addCleanup(combo.deleteLater)
                self.assertFalse(combo.testAttribute(Qt.WidgetAttribute.WA_SetStyle))
                self.assertIs(combo.style(), self.app.style())


    def test_SV9_cerrar_contexto_destruye_las_ventanas_qt(self):
        from shiboken6 import isValid
        c = hc.Contexto(1366, 768)
        ventana = c.w
        self.addCleanup(self.app.sendPostedEvents, None, QEvent.Type.DeferredDelete)
        c.cerrar()
        self.assertFalse(isValid(ventana), "El contexto no debe dejar una ventana pendiente entre pruebas")

    def test_SV10_base_qt_destruye_la_ventana_en_tear_down(self):
        from shiboken6 import isValid
        from test_editor_cadenas import BaseQt
        BaseQt.setUpClass()
        caso = BaseQt()
        caso.setUp()
        ventana = caso.w
        self.addCleanup(self.app.sendPostedEvents, None, QEvent.Type.DeferredDelete)
        caso.tearDown()
        caso.doCleanups()
        self.assertFalse(isValid(ventana), "La limpieza común debe terminar en el hilo de la interfaz")

    def test_SV11_salir_de_ip_no_invoca_un_campo_destruido(self):
        from PySide6.QtGui import QFocusEvent
        from escritorio.entradas_salidas import CampoIPv4
        campo = CampoIPv4()
        with patch("sys.excepthook") as excepcion:
            self.app.sendEvent(campo.cajas[0], QFocusEvent(QEvent.Type.FocusOut))
            campo.deleteLater()
            self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.app.processEvents()
            excepcion.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "regresión de fuentes offscreen con C:/Windows/Fonts")
    def test_SV12_pruebas_de_clave_conservan_el_entorno_de_qt(self):
        entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
        resultado = subprocess.run([sys.executable, str(ROOT / "tests/ayuda_sv_entorno.py")],
                                   cwd=ROOT, env=entorno, capture_output=True, text=True, encoding="utf-8", timeout=35)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        datos = json.loads(resultado.stdout.strip().splitlines()[-1])
        self.assertTrue(datos["entorno_conservado"])
        self.assertTrue(all(m["estrecha"] < m["ancha"] for m in datos["medidas"]))

    @unittest.skipUnless(os.name == "nt", "comprobación del entorno nativo de Windows")
    def test_SV13_aislar_python_no_cambia_el_entorno_nativo_ni_al_fallar(self):
        import ctypes
        from entorno_pruebas import entorno_aislado
        original = os.environ
        esperado = original["QT_QPA_FONTDIR"]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetEnvironmentVariableW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
        buffer = ctypes.create_unicode_buffer(32768)
        with self.assertRaisesRegex(RuntimeError, "salida de prueba"):
            with entorno_aislado({"QT_QPA_FONTDIR": "solo-en-la-copia-python"}):
                self.assertEqual(os.getenv("QT_QPA_FONTDIR"), "solo-en-la-copia-python")
                kernel.GetEnvironmentVariableW("QT_QPA_FONTDIR", buffer, len(buffer))
                self.assertEqual(buffer.value, esperado)
                raise RuntimeError("salida de prueba")
        self.assertIs(os.environ, original)
        self.assertEqual(os.environ["QT_QPA_FONTDIR"], esperado)

    @unittest.skipUnless(os.name == "nt", "presión de streams C en las fuentes Qt offscreen de Windows")
    def test_SV14_las_fuentes_se_leen_con_509_streams_ocupados(self):
        entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
        resultado = subprocess.run([sys.executable, str(ROOT / "tests/ayuda_sv_capacidad_fuentes.py")],
                                   cwd=ROOT, env=entorno, capture_output=True, text=True, encoding="utf-8", timeout=35)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        datos = json.loads(resultado.stdout.strip().splitlines()[-1])
        self.assertEqual(datos["aperturas_simuladas"], 509)
        self.assertGreaterEqual(datos["limite"], 8192)
        self.assertLess(datos["estrecha"], datos["ancha"])

if __name__ == "__main__":
    unittest.main()
