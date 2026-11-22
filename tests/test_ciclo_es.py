"""SCIC01..SCIC09: el hilo de control del ciclo de E/S, sin Qt (V2-E7, paso 1)."""
import statistics
import sys
import threading
import time
import unittest
from unittest import mock
from types import SimpleNamespace

from conexion.ciclo import CicloES, Espera
from conexion.hilos import Candado


class Sesion:
    def __init__(self, registro):
        self.status = "pausada-estable"
        self.z = SimpleNamespace(time=0)
        self.registro = registro

    def advance_to(self, t):
        self.registro.append(("avanzar", t))
        self.z.time = t


class Coordinador:
    """Lo mínimo que usa el ciclo de un `Coordinador`: estado, sesión, plazo de la próxima lectura y `tick`."""

    def __init__(self, periodo_ms=5, registro=None):
        self.registro = [] if registro is None else registro
        self.estado, self.reiniciando, self.en_marcha, self.fallo_motor = "conectado", False, True, False
        self.mensaje = "Conectado"
        self.futuro = None
        self.proxima = 0.0
        self.sesion = Sesion(self.registro)
        self.adaptador = SimpleNamespace(sesion=self.sesion, config=SimpleNamespace(periodo_ms=periodo_ms))
        self.horas = []
        self.fallo = None
        self.llamadas = threading.Semaphore(0)

    @property
    def activo(self):
        return self.estado in ("conectando", "conectado", "diagnostico", "cerrando", "probando")

    def tick(self, ejecutar=False):
        self.registro.append(("tick", ejecutar))
        self.horas.append(time.perf_counter())
        self.llamadas.release()
        if self.fallo is not None:
            raise self.fallo
        # como el coordinador: lanza la lectura siguiente cuando llega su plazo
        if time.perf_counter() >= self.proxima:
            self.proxima = time.perf_counter() + self.adaptador.config.periodo_ms / 1000


class CicloSinQt(unittest.TestCase):
    def preparar(self, **k):
        self.coord = Coordinador(**k)
        self.candado = Candado()
        self.errores, self.novedades = [], []
        self.ciclo = CicloES(self.coord, self.candado, al_novedad=lambda: self.novedades.append(time.perf_counter()),
                             al_error=self.errores.append)
        self.addCleanup(self.ciclo.parar)
        return self.ciclo

    def test_SCIC01_avanza_el_reloj_antes_de_aplicar_y_solo_si_toca(self):
        """REQ-SIM-03, REQ-TMP-02 (P-IMP-50): el ciclo avanza el reloj lógico antes de `tick` y solo si el motor está en marcha y estable."""
        c = self.preparar()
        c.pedir_ejecucion(True)
        c.ciclo()
        c.ciclo()
        orden = [x[0] for x in self.coord.registro]
        self.assertEqual(orden, ["avanzar", "tick", "avanzar", "tick"])
        self.assertTrue(all(x[1] is True for x in self.coord.registro if x[0] == "tick"))
        self.coord.registro.clear()
        self.coord.en_marcha = False  # todavía no ha aplicado nada: el reloj no avanza
        c.ciclo()
        self.assertEqual([x[0] for x in self.coord.registro], ["tick"])
        self.coord.registro.clear()
        self.coord.en_marcha, self.coord.sesion.status = True, "error"
        c.ciclo()
        self.assertEqual([x[0] for x in self.coord.registro], ["tick"])  # motor no estable: no se avanza

    def test_SCIC02_el_reloj_conserva_las_fracciones_de_microsegundo(self):
        """REQ-TMP-02: muchos ciclos cortos suman el tiempo real transcurrido, sin perder el resto de cada uno."""
        c = self.preparar()
        c.pedir_ejecucion(True)
        inicio = time.perf_counter_ns()
        c._marca_ns = inicio
        for _ in range(200):
            c.ciclo()
        fin = time.perf_counter_ns()
        total_us = self.coord.sesion.z.time
        self.assertLessEqual(abs(total_us - (fin - inicio) / 1000), 5)  # a lo sumo las fracciones del último ciclo

    def test_SCIC03_despierta_en_cuanto_termina_una_peticion(self):
        """REQ-SIM-03: con un plazo lejano, `despertar` (lo que hace el trabajador de red al acabar) pone el ciclo en marcha enseguida."""
        c = self.preparar(periodo_ms=2000)
        self.coord.proxima = time.perf_counter() + 5
        c.arrancar()
        self.assertTrue(self.coord.llamadas.acquire(timeout=1))  # el primer ciclo, al arrancar
        antes = time.perf_counter()
        c.despertar()
        self.assertTrue(self.coord.llamadas.acquire(timeout=1))
        self.assertLess(time.perf_counter() - antes, 0.05)

    def test_SCIC04_planifica_con_el_periodo(self):
        """REQ-SIM-03: con periodo de 10 ms el ciclo se repite cada ~10 ms, no cada 15,6 ms (la resolución de un `Event.wait`)."""
        c = self.preparar(periodo_ms=10)
        c.arrancar()
        time.sleep(0.6)
        c.parar()
        horas = self.coord.horas[3:]
        intervalos = [(b - a) * 1000 for a, b in zip(horas, horas[1:])]
        self.assertGreater(len(intervalos), 30)
        self.assertLess(statistics.median(intervalos), 12.5)
        self.assertGreater(statistics.median(intervalos), 8)

    def test_SCIC05_para_limpio(self):
        """REQ-SIM-03: `parar` espera al hilo, `vivo` cambia y el candado deja de marcar hilo de control; se puede arrancar otra vez."""
        c = self.preparar()
        ajenos = {h for h in threading.enumerate() if h.name == "control-es"}  # (de otras pruebas de la misma ejecución)
        self.assertFalse(c.vivo)
        c.arrancar()
        self.assertTrue(c.vivo)
        self.assertTrue(self.candado.control_vivo)
        c.parar()
        self.assertFalse(c.vivo)
        self.assertFalse(self.candado.control_vivo)
        self.assertEqual({h for h in threading.enumerate() if h.name == "control-es"} - ajenos, set())
        c.arrancar()
        self.assertTrue(c.vivo)
        c.parar()

    def test_SCIC06_una_excepcion_llega_a_la_pantalla_y_no_mata_el_hilo(self):
        """REQ-SIM-03: lo que lance un ciclo se pasa a `al_error`; el hilo sigue vivo y sigue ciclando."""
        c = self.preparar(periodo_ms=5)
        self.coord.fallo = RuntimeError("fallo de prueba")
        c.arrancar()
        for _ in range(3):
            self.assertTrue(self.coord.llamadas.acquire(timeout=1))
        self.assertTrue(c.vivo)
        self.assertGreaterEqual(len(self.errores), 2)
        self.assertEqual(str(self.errores[0]), "fallo de prueba")
        self.coord.fallo = None
        n = len(self.coord.horas)
        time.sleep(0.1)
        self.assertGreater(len(self.coord.horas), n)

    def test_SCIC07_ejecutar_se_decide_en_un_solo_sitio_y_lo_fija_la_pantalla(self):
        """REQ-SIM-03: `pedir_ejecucion(False)` hace que el ciclo llame a `tick(False)` y no avance el reloj."""
        c = self.preparar()
        c.pedir_ejecucion(True)
        c.ciclo()
        self.coord.registro.clear()
        c.pedir_ejecucion(False)
        c.ciclo()
        self.assertEqual(self.coord.registro, [("tick", False)])

    def test_SCIC08_avisa_de_motor_parado_y_de_conexion_caida(self):
        """REQ-SIM-03: con Play pedido, el ciclo apunta `motor_parado` y `conexion_caida` para que la pantalla los atienda; sin Play no avisa."""
        c = self.preparar()
        c.ciclo()
        self.assertEqual(c.tomar_avisos(), set())
        c.pedir_ejecucion(True)
        self.coord.sesion.status = "error"
        c.ciclo()
        self.assertEqual(c.tomar_avisos(), {"motor_parado"})
        self.assertEqual(c.tomar_avisos(), set())
        self.coord.sesion.status, self.coord.estado = "pausada-estable", "error"
        c.ciclo()
        c.ciclo()
        self.assertEqual(c.tomar_avisos(), set())  # activo es False: no hay nada que atender
        self.coord.estado = "diagnostico"
        c.ciclo()
        self.assertEqual(c.tomar_avisos(), {"conexion_caida"})

    def test_SCIC09_avisa_a_la_pantalla_como_mucho_10_veces_por_segundo(self):
        """REQ-SIM-03: con un ciclo de 5 ms, las novedades para la pantalla no pasan de ~10 por segundo, salvo un cambio de estado."""
        c = self.preparar(periodo_ms=5)
        c.arrancar()
        time.sleep(0.55)
        self.coord.estado, self.coord.mensaje = "error", "se cayó"
        time.sleep(0.05)
        c.parar()
        sin_cambio = [b - a for a, b in zip(self.novedades, self.novedades[1:])]
        self.assertLessEqual(len(self.novedades), 9)
        self.assertGreaterEqual(min(sin_cambio[:-1] or [1]), 0.09)


    def test_SCIC11_un_hilo_que_acaba_solo_libera_la_espera_el_gil_y_la_marca(self):
        """REQ-SIM-03: si el hilo acaba porque `sigue_vivo` ya no se cumple (sin pasar por `parar`), cierra su espera, quita la marca de hilo de control y
        devuelve el intervalo de cambio del GIL; se puede volver a arrancar."""
        from conexion import ciclo as modulo
        vivo = [True]
        c = self.preparar()
        c.sigue_vivo = lambda: vivo[0]
        antes = modulo._gil["vivos"]
        c.arrancar()
        self.assertEqual(modulo._gil["vivos"], antes + 1)
        espera = c._espera
        vivo[0] = False
        c.despertar()
        c._hilo.join(2)
        self.assertFalse(c.vivo)
        self.assertEqual(modulo._gil["vivos"], antes)
        self.assertFalse(self.candado.control_vivo)
        self.assertTrue(espera.cerrado)
        espera.despertar()  # cerrada: no falla
        espera.cerrar()
        vivo[0] = True
        c.arrancar()  # otra espera nueva
        self.assertTrue(c.vivo)
        self.assertFalse(c._espera.cerrado)
        c.parar()
        self.assertEqual(modulo._gil["vivos"], antes)
        c.parar()  # ya parado: no falla

    def test_SCIC12_parar_cierra_la_espera(self):
        """REQ-SIM-03: `parar` deja cerrada la espera del hilo (sus manejadores del sistema) y el intervalo del GIL como estaba."""
        from conexion import ciclo as modulo
        c = self.preparar()
        antes = modulo._gil["vivos"]
        previo = sys.getswitchinterval()
        c.arrancar()
        if antes == 0:
            self.assertLess(sys.getswitchinterval(), previo)
        espera = c._espera
        c.parar()
        self.assertTrue(espera.cerrado)
        self.assertEqual(modulo._gil["vivos"], antes)
        if antes == 0:
            self.assertEqual(sys.getswitchinterval(), previo)

    def test_SCIC13_el_gc_se_congela_con_el_primer_hilo_y_se_descongela_con_el_ultimo(self):
        """REQ-SIM-03: mientras haya algún hilo de control el gc tiene congelado lo vivo (sus recolecciones completas paraban todos los hilos);
        con dos hilos se descongela solo al parar el último."""
        import gc
        from conexion import ciclo as modulo
        if modulo._gil["vivos"] != 0:
            self.skipTest("hay otros hilos de control vivos")
        a, b = self.preparar(), self.preparar()
        base = gc.get_freeze_count()
        a.arrancar()
        self.addCleanup(a.parar)
        congelados = gc.get_freeze_count()
        self.assertGreater(congelados, base)
        b.arrancar()
        self.addCleanup(b.parar)
        a.parar()
        self.assertGreater(gc.get_freeze_count(), 0, "queda un hilo: sigue congelado")
        b.parar()
        self.assertEqual(gc.get_freeze_count(), 0)

    def test_SCIC14_el_hilo_vuelve_a_congelar_el_gc_cada_REFREEZE_S_y_no_si_es_cero(self):
        """REQ-SIM-03: mientras haya conexión el hilo de control vuelve a congelar el gc cada `REFREEZE_S` (la traza acumulada sale de las
        recolecciones completas); con 0 solo congela al arrancar."""
        import time
        from conexion import ciclo as modulo
        if modulo._gil["vivos"] != 0:
            self.skipTest("hay otros hilos de control vivos")
        for intervalo, minimo, maximo in ((0.05, 3, 1000), (0.0, 1, 1)):
            c = self.preparar()
            with mock.patch.object(modulo, "REFREEZE_S", intervalo), mock.patch.object(modulo.gc, "freeze") as congelar:
                c.arrancar()
                time.sleep(0.5)
                c.parar()
            self.assertGreaterEqual(congelar.call_count, minimo, intervalo)
            self.assertLessEqual(congelar.call_count, maximo, intervalo)


class PrecisionDeLaEspera(unittest.TestCase):
    def test_SCIC10_espera_con_precision_y_despierta_al_momento(self):
        """REQ-SIM-03: `Espera.esperar(5 ms)` tarda ~5 ms (no 16) y `despertar` la corta enseguida, aunque falten segundos."""
        e = Espera()
        self.addCleanup(e.cerrar)
        reales = []

        def medir():
            for _ in range(60):
                t0 = time.perf_counter()
                e.esperar(t0 + 0.005)
                reales.append((time.perf_counter() - t0) * 1000)
        h = threading.Thread(target=medir)
        h.start()
        h.join()
        reales = reales[5:]
        self.assertLess(statistics.median(reales), 7.5, reales)
        self.assertLess(sorted(reales)[int(.95 * (len(reales) - 1))], 10)
        latencias = []

        def dormir():
            t0 = time.perf_counter()
            e.esperar(t0 + 3)
            latencias.append(time.perf_counter() - t0)
        h = threading.Thread(target=dormir)
        h.start()
        time.sleep(0.05)
        t1 = time.perf_counter()
        e.despertar()
        h.join()
        self.assertLess(time.perf_counter() - t1, 0.02)
        self.assertLess(latencias[0], 0.5)
        e.despertar()  # un aviso sin nadie esperando no se pierde
        t2 = time.perf_counter()
        e.esperar(t2 + 3)
        self.assertLess(time.perf_counter() - t2, 0.02)


if __name__ == "__main__":
    unittest.main()
