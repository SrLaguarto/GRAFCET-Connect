from fractions import Fraction
import unittest

from conexion.adaptador import Adaptador
from conexion.configuracion import Configuracion, Senal
from helpers import M, session
from test_modbus import servidor


class AnalogicasTests(unittest.TestCase):
    def test_SFIO11_registros_red(self):
        """REQ-SIM-02: registros Modbus big endian y escrituras confirmadas."""
        peticiones = []
        def responder(p):
            peticiones.append(p)
            return bytes([p[0], 4, 0xff, 0xff, 0x80, 0]) if p[0] in (3, 4) else p[:5]
        with servidor(responder) as c:
            self.assertEqual(c.leer_registros(4, 2), [65535, 32768])
            self.assertEqual(c.leer_registros(4, 2, entradas=False), [65535, 32768])
            c.escribir_registros(8, [65535, 32768])
            with self.assertRaises(ValueError):
                c.escribir_registros(0, [-1])
        self.assertEqual(peticiones[-1], b"\x10\x00\x08\x00\x02\x04\xff\xff\x80\x00")

    def test_SFIO12_escalado_y_limites(self):
        """REQ-EXP-01: INT16/UINT16 y escala exacta, sin redondeos implícitos."""
        m = M().var("sensor", kind="decimal", scale=2).var("motor", "output", "decimal", scale=2)
        m.step("E0", True).stored("E0", "motor", "activation", "-1.25")
        s = session(m.compile())
        cfg = Configuracion(senales=[Senal("sensor", "input-register", 0, "INT16", "100"),
                                    Senal("motor", "holding", 0, "INT16", "100")])
        cfg.validar(m.doc)
        a = Adaptador(cfg, s)
        for raw, esperado in ((0x8000, Fraction(-32768, 100)), (0x7fff, Fraction(32767, 100)),
                              (0xffff, Fraction(-1, 100))):
            a.aplicar({"sensor": raw})
            self.assertEqual(s.z.values["sensor"], esperado)
        self.assertEqual(a.valores_salida(), {"motor": 65411})
        cfg.senales[0].formato = "UINT16"
        a.aplicar({"sensor": 65535})
        self.assertEqual(s.z.values["sensor"], Fraction(65535, 100))
        cfg.senales[1].formato = "UINT16"
        with self.assertRaises(ValueError):
            a.valores_salida()
        cfg.senales[1].formato, cfg.senales[1].escala = "INT16", "1"
        with self.assertRaises(ValueError):
            a.valores_salida()

    def test_SFIO13_rechaza_perdida_precision(self):
        """REQ-EXP-01: una entrada no representable no entra en el motor."""
        m = M().var("sensor", kind="decimal", scale=1).step("E0", True)
        a = Adaptador(Configuracion(senales=[Senal("sensor", "holding", 0, "INT16", "100")]), session(m.compile()))
        with self.assertRaises(Exception):
            a.aplicar({"sensor": 15})
        self.assertEqual(a.sesion.z.values["sensor"], 0)
