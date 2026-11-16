"""SCD: integración con la ventana y límites del encargo."""
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from PySide6.QtWidgets import QApplication
from conexion.configuracion import ARCHIVO
from conexion.uniones import Union
from servidor_directo_falso import ServidorDirecto, senal
from test_editor_cadenas import BaseQt


class VentanaDirecta(BaseQt):
    def test_SCD50_conectar_desde_la_ventana_y_cambiar_papel(self):
        w, e = self.vacio()
        e.nueva_variable("Marcha")
        e.nueva_variable("Motor", "output")
        servidor = ServidorDirecto([senal("s", "Pulsador", valor=True), senal("q", "Motor", papel="Output")])
        self.addCleanup(servidor.cerrar)
        self.addCleanup(w.modbus.cerrar)
        self.addCleanup(w.hide)
        w.mostrar_es()
        w.show()
        panel = w.panel_es
        panel.directa.selector.setCurrentIndex(1)
        panel.directa.host.setText("127.0.0.1")
        panel.directa.puerto.setValue(servidor.puerto)
        entrada, salida = e.ed.model["variables"]
        panel.config.uniones = [Union(entrada["id"], "s", "Pulsador", "Bit", "input"),
                                Union(salida["id"], "q", "Motor", "Bit", "output")]
        panel.directa.aplicar()
        w._conectar_modbus()
        self.esperar(lambda: w.modbus.estado == "conectado", w)
        self.assertEqual(w.modbus.muestra, {entrada["id"]: True})
        self.assertEqual(panel.directa.dibujo.fila_izq.count(), 1)
        e.cambiar_variable(entrada["id"], role="output")
        self.esperar(lambda: w.modbus.adaptador.entradas == [], w)
        self.assertEqual(w.modbus.estado, "conectado")
        self.assertIn("papel", panel.directa.dibujo.terminales["s"].toolTip())
        w._desconectar_modbus()
        self.esperar(lambda: w.modbus.estado == "desconectado", w)

    def esperar(self, condicion, ventana):
        limite = time.monotonic() + 4
        while not condicion():
            QApplication.processEvents()
            if time.monotonic() > limite:
                self.fail((ventana.modbus.estado, ventana.modbus.mensaje))
            time.sleep(0.002)


class Limites(unittest.TestCase):
    def test_SCD51_ficheros_del_encargo_sin_nombre_comercial(self):
        import json
        inventario = json.loads((ROOT / "artifacts/conexion_directa/revision_i.json").read_text(encoding="utf-8"))
        marca = ARCHIVO.removeprefix("conexion-").removesuffix(".json")
        normalizar = lambda texto: "".join(c for c in texto.casefold() if c.isalnum())
        for nombre in inventario["archivos_codigo"]:
            with self.subTest(fichero=nombre):
                texto = (ROOT / nombre).read_text(encoding="utf-8")
                if nombre == "conexion/configuracion.py":
                    texto = texto.replace(f'ARCHIVO = "{ARCHIVO}"', "", 1)
                self.assertNotIn(normalizar(marca), normalizar(texto))


if __name__ == "__main__":
    unittest.main()
