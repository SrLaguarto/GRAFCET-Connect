"""SCD: intercambio real contra HTTP falso, sin simulador externo (I4)."""
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conexion.adaptador_directo import AdaptadorDirecto
from conexion.configuracion import Configuracion
from conexion.coordinador import Coordinador
from conexion.intercambio_directo import TransporteDirecto
from conexion.uniones import Union
from helpers import M, session
from servidor_directo_falso import ServidorDirecto, senal


def esperar(coordinador, condicion, ejecutar=False):
    limite = time.monotonic() + 3
    while not condicion():
        coordinador.tick(ejecutar)
        if time.monotonic() >= limite:
            raise AssertionError((coordinador.estado, coordinador.mensaje, coordinador.fase))
        time.sleep(0.001)


class Intercambio(unittest.TestCase):
    def preparar(self):
        m = M().var("sensor").var("motor", "output").step("E0", True)
        m.cont("E0", "motor", "sensor")
        servidor = ServidorDirecto([senal("entrada", "Sensor", valor=True),
                                   senal("salida", "Motor", papel="Output")])
        self.addCleanup(servidor.cerrar)
        config = Configuracion(host="127.0.0.1", puerto=servidor.puerto, periodo_ms=5, modo="directo")
        config.uniones = [Union("sensor", "entrada", "Sensor", "Bit", "input"),
                          Union("motor", "salida", "Motor", "Bit", "output")]
        coordinador = Coordinador()
        self.addCleanup(coordinador.cerrar)
        return m, servidor, config, coordinador

    def test_SCD30_ciclo_lotes_ceros_pausa_y_desconexion(self):
        m, servidor, config, c = self.preparar()
        sesion = session(m.compile())
        c.iniciar(config, sesion)
        esperar(c, lambda: c.estado == "conectado")
        self.assertFalse(servidor.senales[1]["value"])
        self.assertFalse(sesion.z.values["sensor"], "Conectar no ejecuta")
        esperar(c, lambda: c.escritos.get("motor") is True, True)
        self.assertTrue(servidor.senales[1]["value"])
        lecturas = [p for p in servidor.peticiones if p[:2] == ("GET", "/api/tag/values")]
        self.assertTrue(lecturas)
        self.assertTrue(all(p[2] == ["entrada"] for p in lecturas))
        numero = sum(p[0] == "PUT" for p in servidor.peticiones)
        hasta = time.monotonic() + 0.06
        while time.monotonic() < hasta:
            c.tick(True)
            time.sleep(0.001)
        self.assertEqual(sum(p[0] == "PUT" for p in servidor.peticiones), numero)
        c.pausar()
        esperar(c, lambda: c.escritos.get("motor") is False)
        self.assertFalse(servidor.senales[1]["value"])
        c.desconectar()
        esperar(c, lambda: c.estado == "desconectado")
        self.assertFalse(servidor.senales[1]["value"])

    def test_SCD61_una_salida_puesta_a_cero_por_el_simulador_se_reenvia(self):
        """Sin cambios en el GRAFCET, las salidas se reenvían cada REFRESCO_S: si el simulador las pone a 0 por su cuenta
        (al reiniciar la escena), vuelven a su valor."""
        from unittest import mock
        from conexion import intercambio_directo
        m, servidor, config, c = self.preparar()
        sesion = session(m.compile())
        c.iniciar(config, sesion)
        esperar(c, lambda: c.estado == "conectado")
        esperar(c, lambda: servidor.senales[1]["value"] is True, True)
        servidor.senales[1]["value"] = False  # (la escena se reinicia en el simulador)
        with mock.patch.object(intercambio_directo, "REFRESCO_S", 0.05):
            esperar(c, lambda: servidor.senales[1]["value"] is True, True)

    def test_SCD31_tipos_reales_y_redondeo(self):
        m = M().var("entero", kind="int").var("decimal", kind="decimal", scale=2)
        m.step("E0", True)
        config = Configuracion(modo="directo", host="localhost", puerto=7410)
        config.uniones = [Union("entero", "i", "Cuenta", "Int", "input"),
                          Union("decimal", "f", "Distancia", "Float", "input")]
        adaptador = AdaptadorDirecto(config, session(m.compile()))
        adaptador.aplicar({"entero": -1.5, "decimal": 12.25})
        self.assertEqual(adaptador.sesion.z.values["entero"], -2)
        self.assertEqual(float(adaptador.sesion.z.values["decimal"]), 12.25)
        self.assertIn("entero", adaptador.redondeos)

    def test_SCD32_406_no_desconecta_y_no_repite_union_mala(self):
        m, servidor, config, c = self.preparar()
        servidor.rechazar.add("salida")
        c.iniciar(config, session(m.compile()))
        esperar(c, lambda: c.estado == "conectado")
        c.tick()
        self.assertIn("406", c.mensaje)
        self.assertEqual(c.estado, "conectado")
        self.assertTrue(config.uniones[1].motivo)

    def test_SCD33_ambar_no_se_lee_ni_escribe(self):
        m, servidor, config, c = self.preparar()
        servidor.senales = []
        c.iniciar(config, session(m.compile()))
        esperar(c, lambda: c.estado == "conectado")
        c.tick()
        self.assertIn("no encontrada", c.mensaje)
        self.assertEqual(servidor.peticiones, [("GET", "/api/tags", None)])
        self.assertEqual(c.adaptador.entradas, [])
        self.assertEqual(c.adaptador.salidas, [])

    def test_SCD34_cambio_id_al_conectar(self):
        m, servidor, config, c = self.preparar()
        servidor.senales[0]["id"] = "renovada"
        c.iniciar(config, session(m.compile()))
        esperar(c, lambda: c.estado == "conectado")
        self.assertEqual(config.uniones[0].id, "renovada")
        self.assertEqual(c.muestra, {"sensor": True})

    def test_SCD35_monitor_sin_motor_cero_y_valores(self):
        m, servidor, config, c = self.preparar()
        c.iniciar(config, None, documento=m.doc)
        esperar(c, lambda: c.estado == "conectado")
        self.assertEqual(c.muestra, {"sensor": True})
        self.assertFalse(servidor.senales[1]["value"])

    def test_SCD36_406_http_no_desconecta(self):
        m, servidor, config, c = self.preparar()
        cliente = TransporteDirecto(config)
        self.addCleanup(cliente.cerrar)
        adaptador = AdaptadorDirecto(config, session(m.compile()))
        cliente.preparar(adaptador, m.doc)
        servidor.error = 406
        self.assertEqual(cliente.escribir(adaptador.salidas, {"motor": True}), {})
        self.assertIn("406", cliente.avisos[-1])

    def test_SCD37_union_nueva_con_conexion_viva_relee_catalogo(self):
        from copy import deepcopy
        m, servidor, config, c = self.preparar()
        c.iniciar(config, None, documento=m.doc)
        esperar(c, lambda: c.estado == "conectado")
        nueva = deepcopy(config)
        nueva.uniones[0].id = "nueva"
        servidor.senales[0]["id"] = "nueva"
        c.reasignar(nueva, m.doc)
        esperar(c, lambda: c.adaptador.config.uniones[0].id == "nueva" and c.fase != "mapa")
        esperar(c, lambda: c.muestra.get("sensor") is True)
        self.assertEqual(c.estado, "conectado")
        self.assertGreaterEqual(sum(p[1] == "/api/tags" for p in servidor.peticiones), 2)

    def test_SCD38_cambio_de_modo_exige_desconectar(self):
        m, servidor, config, c = self.preparar()
        c.iniciar(config, None, documento=m.doc)
        esperar(c, lambda: c.estado == "conectado")
        otro = Configuracion(host=config.host, puerto=config.puerto)
        with self.assertRaisesRegex(ValueError, "Desconecta"):
            c.reasignar(otro, m.doc)


if __name__ == "__main__":
    unittest.main()
