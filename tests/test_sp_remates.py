"""Remates pedidos durante P: nombres pendientes y sustitución del texto inicial."""
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")
try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit
    from conexion.configuracion import Configuracion
    from escritorio import estilo
    from escritorio.anotaciones import editar_texto
    from escritorio.edicion import Edicion
    from escritorio.entradas_salidas import PanelES
    from escritorio.traer_dialogo import DialogoTraer
    from servidor_directo_falso import ServidorDirecto, senal
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class RematesP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_SP126_nombre_invalido_naranja_y_se_limpia_al_corregir(self):
        servidor = ServidorDirecto([senal("uno", "Xmotor inicio"), senal("dos", "Marcha")])
        self.addCleanup(servidor.cerrar)
        panel = PanelES()
        self.addCleanup(panel.close)
        edicion = Edicion.nuevo()
        panel.directa.establecer_edicion(edicion)
        panel.cargar(edicion.ed.model, Configuracion(modo="directo", host="127.0.0.1", puerto=servidor.puerto))
        dialogo = DialogoTraer(panel.directa)
        self.addCleanup(dialogo.reject)
        limite = time.monotonic() + 3
        while dialogo.propuestas is None and time.monotonic() < limite:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertIsNotNone(dialogo.propuestas)
        tabla, filas = dialogo.tablas[0]
        item = tabla.item(0, 2)
        self.assertTrue(filas[0].motivo)
        self.assertEqual(item.background().color().name(), estilo.NOMBRE_PENDIENTE_FONDO)
        self.assertEqual(tabla.item(1, 2).background().style(), Qt.BrushStyle.NoBrush)
        item.setText("Inicio")
        self.assertEqual(item.background().style(), Qt.BrushStyle.NoBrush)
        self.assertTrue(dialogo.b_traer.isEnabled())

    def test_SP127_escribir_sustituye_texto_inicial(self):
        original = {"text": "Texto", "font": "Arial", "size": 18, "color": "#172e4d"}

        def aceptar(dialogo):
            editor = dialogo.findChild(QPlainTextEdit)
            self.assertEqual(editor.textCursor().selectedText(), "Texto")
            QTest.keyClicks(editor, "Mi anotacion")
            return QDialog.DialogCode.Accepted

        with patch.object(QDialog, "exec", aceptar):
            resultado = editar_texto(original)
        self.assertEqual(resultado["text"], "Mi anotacion")
        self.assertEqual(original["text"], "Texto")

    def test_SP128_editar_y_cancelar_conservan_contenido_existente(self):
        original = {"text": "Contenido existente", "font": "Arial", "size": 18, "color": "#172e4d"}
        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            self.assertEqual(editar_texto(original)["text"], original["text"])
        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            self.assertIsNone(editar_texto(original))
        self.assertEqual(original["text"], "Contenido existente")


if __name__ == "__main__":
    unittest.main()
