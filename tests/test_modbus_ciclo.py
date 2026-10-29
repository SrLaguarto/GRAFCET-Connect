import time
import unittest

from conexion.coordinador import Coordinador
from conexion.configuracion import Configuracion, Senal
from helpers import M, session
from test_modbus import servidor


def esperar(c, condicion, ejecutar=False):
    limite = time.monotonic() + 3
    while not condicion():
        c.tick(ejecutar)
        if time.monotonic() > limite:
            raise AssertionError((c.estado, c.mensaje, c.fase))
        time.sleep(.001)


class CicloTests(unittest.TestCase):
    def test_SFIO15_temporizacion_sin_cambios_sensor(self):
        """REQ-TMP-02: el reloj existente dispara salidas aunque la muestra no cambie."""
        with servidor(lambda p: b"\x02\x01\x01" if p[0] == 2 else p[:5]) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "delay(1s, sensor, 0s)")
            s = session(m.compile())
            cfg = Configuracion(puerto=sc.puerto, periodo_ms=20,
                                senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                esperar(c, lambda: s.z.values["sensor"], True)
                self.assertFalse(s.z.outputs["motor"])
                s.advance_to(1000000)  # representa el avance del único QTimer de la ventana
                esperar(c, lambda: c.escritos.get("motor") is True, True)
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO09_ciclo_pausa_diagnostico(self):
        """REQ-SIM-02: ciclo completo, pausa conserva y diagnóstico solicita cero."""
        peticiones = []
        def responder(p):
            peticiones.append(p)
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        with servidor(responder) as servidor_cliente:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            s = session(m.compile())
            cfg = Configuracion(puerto=servidor_cliente.puerto, periodo_ms=20,
                                senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                self.assertFalse(s.z.values["sensor"], "Conectar no ejecuta el motor")
                esperar(c, lambda: c.escritos.get("motor") is True, True)
                self.assertTrue(s.z.outputs["motor"])
                # Completar el intercambio pendiente sin ejecutar: no se publica cero al pausar.
                n = sum(p[0] == 15 for p in peticiones)
                for _ in range(60):
                    c.tick(False)
                    time.sleep(.001)
                self.assertEqual(n, sum(p[0] == 15 for p in peticiones))
                self.assertTrue(s.z.outputs["motor"])
                s.status = "error"  # simula el resultado de un diagnóstico, sin alterar oráculos
                esperar(c, lambda: c.estado == "diagnostico" and c.escritos.get("motor") is False)
                self.assertTrue(s.z.outputs["motor"], "Poner planta a cero no modifica motor")
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO10_perdida_y_reconexion_manual(self):
        """REQ-ROB-01: pérdida de red detiene; reconectar no reanuda el motor."""
        responde = [True]
        def responder(p):
            return (b"\x02\x01\x01" if p[0] == 2 else p[:5]) if responde[0] else None
        with servidor(responder) as sc:
            m = M().var("sensor").step("E0", True)
            s = session(m.compile())
            cfg = Configuracion(puerto=sc.puerto, senales=[Senal("sensor", "discrete", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                responde[0] = False
                esperar(c, lambda: c.estado == "error")
                responde[0] = True
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                self.assertFalse(s.z.values["sensor"])
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()
