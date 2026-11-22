"""SHIL01..SHIL05: guarda de hilos del ciclo de E/S (V2-E7, paso 0, `GRAFCONNECT_COMPROBAR_HILOS=1`). Sin Qt."""
import os
import threading
import unittest
from unittest import mock

from conexion.hilos import VARIABLE, AccesoSinCandado, Candado, desproteger, proteger


class Cosa:
    def __init__(self):
        self.valor = 1
        self.otro = 2

    def tick(self):
        return self.valor


def desde_otro_hilo(f):
    """Ejecuta `f()` en otro hilo y devuelve (resultado, excepción)."""
    salida = []
    h = threading.Thread(target=lambda: salida.append(_intentar(f)), name="otro-hilo")
    h.start()
    h.join()
    return salida[0]


def _intentar(f):
    try:
        return f(), None
    except Exception as exc:  # noqa: BLE001
        return None, exc


class GuardaDeHilos(unittest.TestCase):
    def con(self, valor):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        if valor is None:
            os.environ.pop(VARIABLE, None)
        else:
            os.environ[VARIABLE] = valor

    def test_SHIL01_sin_la_variable_no_toca_el_objeto(self):
        """REQ-SIM-03: sin `GRAFCONNECT_COMPROBAR_HILOS=1`, `proteger` no cambia el objeto ni cuesta nada, aunque haya hilo de control."""
        self.con(None)
        c, candado = Cosa(), Candado()
        self.assertFalse(proteger(c, ("valor", "tick"), candado))
        self.assertIs(type(c), Cosa)
        with candado.hilo_de_control():
            self.assertEqual(desde_otro_hilo(lambda: c.valor), (1, None))

    def test_SHIL02_con_la_variable_pero_sin_hilo_de_control_no_se_exige_nada(self):
        """REQ-SIM-03: con la variable y sin hilo de control vivo (hoy, o tras pararlo) cualquier hilo puede tocar el objeto."""
        self.con("1")
        c, candado = Cosa(), Candado()
        self.assertTrue(proteger(c, ("valor", "tick"), candado, "Cosa"))
        self.assertIsInstance(c, Cosa)
        self.assertEqual(desde_otro_hilo(lambda: c.tick()), (1, None))

    def test_SHIL03_con_hilo_de_control_vivo_tocarlo_sin_el_candado_falla_con_un_error_claro(self):
        """REQ-SIM-03: con el hilo de control vivo, leer, escribir o llamar sin el candado lanza `AccesoSinCandado` (con el objeto, el atributo y el
        hilo); con el candado cogido, también reentrante, pasa; lo no protegido no se vigila."""
        self.con("1")
        c, candado = Cosa(), Candado()
        proteger(c, ("valor", "tick"), candado, "Cosa")
        with candado.hilo_de_control():
            _, error = desde_otro_hilo(lambda: c.valor)
            self.assertIsInstance(error, AccesoSinCandado)
            for texto in ("Cosa.valor", "otro-hilo", "candado de control"):
                self.assertIn(texto, str(error))
            self.assertIsInstance(desde_otro_hilo(lambda: setattr(c, "valor", 5))[1], AccesoSinCandado)
            self.assertIsInstance(desde_otro_hilo(lambda: c.tick())[1], AccesoSinCandado)
            self.assertEqual(c.otro, 2)  # no protegido
            self.assertIsInstance(_intentar(lambda: c.valor)[1], AccesoSinCandado)  # tampoco el hilo principal, sin candado

            def con_candado():
                with candado:
                    with candado:  # reentrante
                        c.valor = 7
                        return c.tick()
            self.assertEqual(desde_otro_hilo(con_candado), (7, None))
        self.assertEqual(c.valor, 7)  # pasado el hilo de control, vuelve a no exigirse

    def test_SHIL04_el_candado_solo_vale_para_el_hilo_que_lo_tiene(self):
        """REQ-SIM-03: que un hilo tenga el candado no autoriza a otro."""
        self.con("1")
        c, candado = Cosa(), Candado()
        proteger(c, ("valor",), candado)
        listo, sigue = threading.Event(), threading.Event()
        dueno = threading.Thread(target=lambda: (candado.acquire(), listo.set(), sigue.wait(2), candado.release()))
        with candado.hilo_de_control():
            dueno.start()
            self.assertTrue(listo.wait(2))
            self.assertIsInstance(_intentar(lambda: c.valor)[1], AccesoSinCandado)
            sigue.set()
            dueno.join()

    def test_SHIL05_funciona_con_un_coordinador_real_y_se_puede_quitar(self):
        """REQ-SIM-03: sobre un `Coordinador` real, su estado y sus medidas exigen el candado con el hilo de control vivo; `desproteger` lo deja igual."""
        from conexion.coordinador import Coordinador
        self.con("1")
        coord, candado = Coordinador(), Candado()
        try:
            original = type(coord)
            self.assertTrue(proteger(coord, ("estado", "medidas", "tick"), candado, "Coordinador"))
            with candado.hilo_de_control():
                self.assertIsInstance(desde_otro_hilo(lambda: coord.estado)[1], AccesoSinCandado)
                self.assertIsInstance(desde_otro_hilo(lambda: coord.medidas)[1], AccesoSinCandado)
                with candado:
                    self.assertEqual(coord.estado, "desconectado")
                self.assertEqual(desde_otro_hilo(lambda: coord.futuro), (None, None))  # `futuro` no está protegido
            desproteger(coord)
            self.assertIs(type(coord), original)
            self.assertEqual(desde_otro_hilo(lambda: coord.estado), ("desconectado", None))
        finally:
            coord.cerrar()


if __name__ == "__main__":
    unittest.main()
