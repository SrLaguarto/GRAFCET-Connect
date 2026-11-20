"""Fallos graves 1.1.9: señal borrada con la conexión directa en marcha; desplegable de acción con el ratón aún pulsado."""
import os
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conexion.configuracion import Configuracion
from conexion.coordinador import Coordinador
from conexion.uniones import Union
from helpers import M, session
from servidor_directo_falso import ServidorDirecto, senal
from test_conexion_directa_intercambio import esperar
from test_editor_cadenas import BaseQt, QT
from test_selector_accion import SelectorAccion as _Sel

if QT:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QApplication
    from escritorio import diagrama


class SenalBorradaDirecta(unittest.TestCase):
    def preparar(self):
        m = M().var("sensor").var("otro").var("motor", "output").step("E0", True)
        m.cont("E0", "motor", "sensor")
        servidor = ServidorDirecto([senal("entrada", "Sensor", valor=True), senal("otra", "Otro", valor=True),
                                    senal("salida", "Motor", papel="Output")])
        self.addCleanup(servidor.cerrar)
        config = Configuracion(host="127.0.0.1", puerto=servidor.puerto, periodo_ms=5, modo="directo")
        config.uniones = [Union("sensor", "entrada", "Sensor", "Bit", "input"),
                          Union("otro", "otra", "Otro", "Bit", "input"),
                          Union("motor", "salida", "Motor", "Bit", "output")]
        c = Coordinador()
        self.addCleanup(c.cerrar)
        return m, servidor, config, c

    def test_SF119_01_entrada_borrada_marca_la_union_y_sigue_conectado(self):
        """REQ-CON-01: borrar en el simulador una entrada unida no tira la conexión: la unión queda «señal no encontrada»."""
        m, servidor, config, c = self.preparar()
        c.iniciar(config, session(m.compile()))
        esperar(c, lambda: c.estado == "conectado")
        servidor.senales = [s for s in servidor.senales if s["id"] != "otra"]
        esperar(c, lambda: config.uniones[1].motivo == "señal no encontrada")
        for _ in range(20):
            c.tick(True)
            time.sleep(0.002)
        self.assertEqual(c.estado, "conectado", c.mensaje)
        self.assertEqual(c.cliente.avisos.count("«Otro»: señal no encontrada"), 1)
        self.assertFalse(config.uniones[0].motivo)
        self.assertIn("señal no encontrada", c.mensaje)
        esperar(c, lambda: c.escritos.get("motor") is True, True)

    def test_SF119_02_salida_borrada_marca_la_union_y_sigue_conectado(self):
        """REQ-CON-01: lo mismo al escribir una salida cuyo id ya no existe (404)."""
        m, servidor, config, c = self.preparar()
        c.iniciar(config, session(m.compile()))
        esperar(c, lambda: c.estado == "conectado")
        servidor.senales = [s for s in servidor.senales if s["id"] != "salida"]
        esperar(c, lambda: config.uniones[2].motivo == "señal no encontrada", True)
        self.assertEqual(c.estado, "conectado")
        self.assertEqual(c.cliente.avisos.count("«Motor»: señal no encontrada"), 1)
        self.assertEqual(c.muestra.get("sensor"), True)

    def test_SF119_03_id_ausente_de_la_respuesta_de_lectura(self):
        """REQ-CON-01: un id unido que falta en la respuesta (sin error) se trata igual."""
        from conexion.adaptador_directo import AdaptadorDirecto
        from conexion.intercambio_directo import TransporteDirecto
        m, servidor, config, c = self.preparar()
        t = TransporteDirecto(config)
        self.addCleanup(t.cerrar)
        a = AdaptadorDirecto(config, session(m.compile()))
        t.preparar(a, m.doc)
        with mock.patch.object(t, "pedir", return_value=[{"id": "entrada", "value": True}]):
            self.assertEqual(t.leer(a.entradas), {"sensor": True})
        self.assertEqual(config.uniones[1].motivo, "señal no encontrada")
        self.assertEqual(t.avisos, ["«Otro»: señal no encontrada"])
        with mock.patch.object(t, "pedir", return_value=[{"id": "entrada", "value": 1}, {"id": "entrada", "value": 1}]):
            from conexion.http_directo import ErrorDirecto
            with self.assertRaises(ErrorDirecto):
                t.leer(a.entradas)


@unittest.skipUnless(QT, "Falta PySide6")
class DesplegableConRatonPulsado(BaseQt):
    preparar = _Sel.preparar
    doble = _Sel.doble

    def test_SF119_10_no_abre_la_lista_con_el_boton_pulsado_y_la_abre_al_soltar(self):
        """REQ-EDT-09: con el botón del ratón aún pulsado (el del doble clic) la lista no se abre; al soltarlo, sí."""
        pulsado = [True]
        izq = Qt.MouseButton.LeftButton
        nada = Qt.MouseButton.NoButton
        with mock.patch.object(QApplication, "mouseButtons", staticmethod(lambda: izq if pulsado[0] else nada)):
            w, e, did = self.preparar()
            caja, cb = self.doble(w, e, did)
            self.assertIsNotNone(cb)
            for _ in range(5):
                QApplication.processEvents()
                time.sleep(0.02)
            self.assertFalse(cb.view().isVisible(), "pulsado: la lista no se abre")
            pulsado[0] = False
            limite = time.monotonic() + 2
            while not cb.view().isVisible() and time.monotonic() < limite:
                QApplication.processEvents()
                time.sleep(0.005)
            self.assertTrue(cb.view().isVisible(), "soltado: se abre")


del _Sel  # (para que no se descubra como prueba)


if __name__ == "__main__":
    unittest.main()
