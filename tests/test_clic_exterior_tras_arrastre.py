"""REQ-EDT-02: el arrastre nativo no inutiliza el clic exterior de Propiedades."""
import ctypes
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from tools import hoja_contactos as HC
    from escritorio import arrastre_popup
    QT = True
except ImportError:
    QT = False


def punto_nativo(widget, punto):
    global_ = widget.mapToGlobal(punto)
    escala = widget.devicePixelRatioF()
    return round(global_.x() * escala), round(global_.y() * escala)


def mover_raton(origen, destino):
    """Solo Win32 en el trabajador; los QWidget se consultan antes, en el hilo de UI."""
    usuario = ctypes.windll.user32
    usuario.SetCursorPos(*origen)
    time.sleep(.1)
    usuario.mouse_event(2, 0, 0, 0, 0)
    try:
        time.sleep(.2)
        for i in range(1, 41):
            x = origen[0] + (destino[0] - origen[0]) * i / 40
            y = origen[1] + (destino[1] - origen[1]) * i / 40
            usuario.SetCursorPos(round(x), round(y))
            time.sleep(.03)
    finally:
        usuario.mouse_event(4, 0, 0, 0, 0)


@unittest.skipUnless(QT, "requiere Qt")
class CapturaPopup(unittest.TestCase):
    def test_SXC2_no_roba_la_captura_de_un_desplegable_abierto(self):
        """Un popup distinto abierto durante el arrastre conserva la prioridad del ratón."""
        ventana = Mock()
        ventana.windowType.return_value = Qt.WindowType.Popup
        with patch.object(arrastre_popup.QApplication, "platformName", return_value="windows"), \
                patch.object(arrastre_popup.QApplication, "activePopupWidget", return_value=object()), \
                patch.object(arrastre_popup, "isValid", return_value=True):
            arrastre_popup.recuperar_captura(ventana)
        ventana.windowHandle.assert_not_called()


@unittest.skipUnless(QT and sys.platform == "win32", "requiere Qt y ratón nativo de Windows")
class ClicExteriorNativo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        HC.aplicacion()
        if QApplication.platformName() != "windows":
            raise unittest.SkipTest("requiere QT_QPA_PLATFORM=windows; offscreen no reproduce la captura OLE")

    def arrastrar(self, paleta, destino):
        QTest.qWait(300)
        paleta._calcular(paleta.width())
        caja = next(r for r, ruta, nodo in paleta._bloques if nodo is not None)
        origen = punto_nativo(paleta, caja.center().toPoint())
        llegada = punto_nativo(destino, QPoint(40, 20))
        hilo = threading.Thread(target=mover_raton, args=(origen, llegada))
        hilo.start()
        QTest.qWait(2200)
        hilo.join(timeout=2)
        self.assertFalse(hilo.is_alive())
        HC._bombear(5)

    def clic(self, widget, punto):
        usuario = ctypes.windll.user32
        usuario.SetCursorPos(*punto_nativo(widget, punto))
        usuario.mouse_event(2, 0, 0, 0, 0)
        QTest.qWait(30)
        usuario.mouse_event(4, 0, 0, 0, 0)
        HC._bombear(5)

    def test_SXC1_clic_nativo_cierra_tras_soltar_variable_sin_atravesar(self):
        """Arrastre OLE real y clic Win32 real, sin sustituirlos por eventos de QTest."""
        for ancho, alto in ((853, 1019), (1366, 768)):
            for tipo in ("transicion", "condicionada", "evento"):
                with self.subTest(ancho=ancho, tipo=tipo):
                    c = HC.Contexto(ancho, alto)
                    try:
                        HC._flotante(tipo)(c)
                        p, v = c.w.flot.panel, c.w.flot.principal
                        p.prog.poner("")
                        HC._bombear(5)
                        self.arrastrar(p.prog.paleta, p.prog.lienzo)
                        self.assertEqual(p.prog.texto(), "marcha")
                        self.assertTrue(v.isVisible())
                        seleccion = list(c.e.sel)
                        boton = c.w.tb_sim.widgetForAction(c.w.a_ejecutar)
                        self.clic(boton, boton.rect().center())
                        self.assertFalse(v.isVisible())
                        self.assertEqual(c.e.sel, seleccion)
                        self.assertEqual(c.w.modo, "editar")
                    finally:
                        c.cerrar()

    def test_SXC3_clic_nativo_cierra_tambien_tras_arrastre_rechazado(self):
        """Soltar fuera del formulador cancela el bloque y también recupera el clic exterior."""
        c = HC.Contexto(853, 1019)
        try:
            HC._flotante("transicion")(c)
            p, v = c.w.flot.panel, c.w.flot.principal
            p.prog.poner("")
            HC._bombear(5)
            boton = c.w.tb_sim.widgetForAction(c.w.a_ejecutar)
            self.arrastrar(p.prog.paleta, boton)
            self.assertEqual(p.prog.texto(), "")
            self.assertTrue(v.isVisible())
            self.clic(boton, boton.rect().center())
            self.assertFalse(v.isVisible())
            self.assertEqual(c.w.modo, "editar")
        finally:
            c.cerrar()


if __name__ == "__main__":
    unittest.main()
