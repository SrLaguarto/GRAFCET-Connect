import unittest
from conexion.adaptador import Adaptador
from conexion.configuracion import Configuracion, Senal
from helpers import M, session


class AdaptadorTests(unittest.TestCase):
    def construir(self):
        m = M().var("a").var("b").var("q", "output").var("r", "output")
        m.step("E0", initial=True).step("E1")
        m.trans("t", ["E0"], ["E1"], "a AND b")
        m.cont("E1", "q").stored("E1", "r", "activation", "true")
        c = Configuracion(senales=[Senal("a", "discrete", 0), Senal("b", "discrete", 1),
                                   Senal("q", "coil", 0), Senal("r", "coil", 1)])
        return Adaptador(c, session(m.compile()))

    def test_SFIO06_lote_y_salidas(self):
        """REQ-SIM-02: lote único y salidas efectivas continuas y memorizadas."""
        a = self.construir()
        a.aplicar({"a": True, "b": True})
        self.assertEqual(a.sesion.z.situation, frozenset(["E1"]))
        self.assertEqual(a.valores_salida(), {"q": True, "r": True})
        n = len(a.sesion.trace.records)
        a.aplicar({"a": True, "b": True})
        self.assertEqual(n, len(a.sesion.trace.records))
        self.assertEqual(a.valores_salida(cero=True), {"q": False, "r": False})
        self.assertEqual(a.valores_salida(), {"q": True, "r": True})

    def test_SFIO07_muestra_atomica(self):
        """REQ-ROB-01: una muestra incompleta o inválida no entra en el motor."""
        a = self.construir()
        for muestra in ({"a": True}, {"a": True, "b": 123}):
            with self.assertRaises(Exception):
                a.aplicar(muestra)
            self.assertFalse(a.sesion.z.values["a"])
