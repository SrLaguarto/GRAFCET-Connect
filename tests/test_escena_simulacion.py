"""SESC80..SESC85: oráculos de simulación de la prueba de choque (V2-E4, paso 0)."""
from importlib.util import find_spec
from unittest import TestCase, mock, skipUnless

QT = bool(find_spec("PySide6"))

BASE = {"k2": 0, "dx": 0, "dy": 0, "v": 0, "auto": []}


def secuencia():
    """Play, cambios de entradas y de situación, y Reiniciar: lo justo para que todos los paneles tengan algo que enseñar."""
    return [{**BASE, "op": "play", "k": 0}, {**BASE, "op": "sim_fijar", "k": 1}, {**BASE, "op": "sim_cambio", "k": 2},
            {**BASE, "op": "sim_fijar", "k": 3, "k2": 1}, {**BASE, "op": "sim_cambio", "k": 4},
            {**BASE, "op": "sim_reiniciar", "k": 0}, {**BASE, "op": "sim_cambio", "k": 5}]


@skipUnless(QT, "requiere PySide6")
class OraculosDeSimulacion(TestCase):
    def ejecutar(self, parche=None):
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA
        if parche is None:
            return c.ejecutar_nuevo(GEMMA, secuencia())
        with parche:
            return c.ejecutar_nuevo(GEMMA, secuencia())

    def test_SESC80_las_operaciones_de_simulacion_existen_cambian_la_situacion_y_pasan(self):
        """REQ-SIM-01: `sim_fijar`, `sim_cambio`, `sim_reiniciar`, `sim_filtro` y `navegar` están en el generador; sobre GEMMA la
        secuencia de simulación cambia la situación varias veces y pasa los oráculos nuevos sin fallo."""
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA, ventana
        generadas = {r["op"] for r in c.generar(13, 400)}
        self.assertGreaterEqual(generadas, {"sim_fijar", "sim_cambio", "sim_reiniciar", "sim_filtro", "navegar", "play", "stop"})
        situaciones = set()
        with ventana() as w:
            c.reiniciar(w, GEMMA)
            for r in secuencia():
                c.aplicar(w, r)
                c.comprobar(w, momento=r["op"])
                if w.modo == "simular":
                    situaciones.add(frozenset(w.v.s.z.situation))
        self.assertGreaterEqual(len(situaciones), 3, "la simulación debe pasar por varias situaciones")

    def inyecta(self, retoca):
        """Un parche de `Ventana.refrescar` que, tras refrescar en simulación, estropea algo con `retoca(w)`."""
        from escritorio.ventana import Ventana
        original = Ventana.refrescar

        def estropeado(w):
            original(w)
            if w.modo == "simular" and w.v is not None:
                retoca(w)
        return mock.patch.object(Ventana, "refrescar", estropeado)

    def test_SESC81_el_oraculo_de_las_tablas_detecta_una_celda_con_otro_color(self):
        """REQ-SIM-01: ESC-6 detecta una tabla que no coincide con la de la rutina completa (aquí, una celda con otro color)."""
        from PySide6.QtGui import QColor
        f = self.ejecutar(self.inyecta(lambda w: w.t_vars.item(0, 2).setForeground(QColor("#ff00ff")) if w.t_vars.rowCount() else None))
        self.assertIsNotNone(f)
        self.assertEqual(f.tipo, "ESC-6")
        self.assertIsNone(self.ejecutar())

    def test_SESC82_el_oraculo_de_la_traza_detecta_una_fila_de_mas(self):
        """REQ-SIM-01: ESC-7 detecta una traza que no es la de construirla de cero."""
        f = self.ejecutar(self.inyecta(lambda w: w.traza.addItem("fila ajena")))
        self.assertIsNotNone(f)
        self.assertEqual(f.tipo, "ESC-7")

    def test_SESC83_el_oraculo_de_las_entradas_detecta_un_boton_con_otro_texto(self):
        """REQ-SIM-01: ESC-8 detecta un botón de entrada que no refleja el estado."""
        f = self.ejecutar(self.inyecta(lambda w: next(iter(w.botones.values())).setText("otro")))
        self.assertIsNotNone(f)
        self.assertEqual(f.tipo, "ESC-8")

    def test_SESC84_el_oraculo_del_atajo_detecta_un_dibujo_que_no_se_actualiza(self):
        """REQ-SIM-01: ESC-9 (H5) detecta una escena que se queda con un estado viejo porque no se dibuja."""
        from escritorio.diagrama import VistaDiagrama
        original = VistaDiagrama.mostrar

        def sin_dibujar_al_simular(self, *a, **k):
            if self.controlador is None:
                return
            return original(self, *a, **k)
        f = self.ejecutar(mock.patch.object(VistaDiagrama, "mostrar", sin_dibujar_al_simular))
        self.assertIsNotNone(f)
        self.assertIn(f.tipo, ("ESC-9", "ESC-3", "ESC-10"))  # (sin dibujar, la navegación tampoco se pone al día: ESC-10 salta antes)

    def test_SESC85_un_tramo_largo_de_simulacion_al_azar_pasa_todos_los_oraculos(self):
        """REQ-SIM-01: 120 operaciones al azar sobre GEMMA, con tramos largos en simulación, no dan ningún fallo."""
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA
        self.assertIsNone(c.ejecutar_nuevo(GEMMA, c.generar(13, 120)))


@skipUnless(QT, "requiere PySide6")
class PanelesDeSimulacion(TestCase):
    """V2-E4, paso 4: las huellas sin copia profunda y los paneles de simulación que solo tocan lo que cambia."""

    def pasos(self, w, n=12):
        from copy import copy
        from tools.banco_rendimiento import _buscar_cambio
        from tools.entorno_v2_e0 import bombear, paso
        hechos = 0
        for _ in range(n):
            guion = _buscar_cambio(w.v)
            if guion is None:
                continue
            for op, args in guion:
                paso(w, op, **args)
                bombear()
            hechos += 1
        return hechos

    def test_SESC86_el_estado_no_cambia_despues_de_darse_ni_lo_cambia_quien_lo_recibe(self):
        """REQ-SIM-01: cada `Vista.state()` da objetos nuevos que nada cambia después (ni el motor al avanzar ni los paneles al leerlos):
        por eso las huellas del estado no necesitan copia profunda."""
        from copy import deepcopy
        from grafcet.view import Vista
        from tools.entorno_v2_e0 import GEMMA, bombear, play, ventana
        dadas = []
        original = Vista.state

        def registra(self):
            S = original(self)
            dadas.append((S, deepcopy(S)))
            return S
        with ventana() as w, mock.patch.object(Vista, "state", registra):
            self.assertTrue(w.abrir_ruta(GEMMA))
            play(w)
            self.assertGreater(self.pasos(w, 10), 4)
            w.refrescar()
            bombear()
        self.assertGreater(len(dadas), 8)
        for i, (S, copia) in enumerate(dadas):
            self.assertEqual(S, copia, f"el estado dado en la llamada {i} cambió después")

    def test_SESC87_las_tablas_la_traza_y_la_navegacion_solo_rehacen_lo_que_cambia(self):
        """REQ-SIM-01: al simular, la rutina completa de las tablas, la traza hecha de cero y la parte de los registros de la navegación que solo depende del documento no se
        rehacen en cada paso (y los oráculos ESC-6, ESC-7 y ESC-10 dan lo mismo que ellas)."""
        from escritorio import navegacion
        from escritorio.ventana import Ventana
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA, play, ventana
        cuentas = {"completo": 0, "traza": 0, "registros": 0, "refrescos": 0}

        def contar(clave, original):
            def f(*a, **k):
                cuentas[clave] += 1
                return original(*a, **k)
            return f
        with ventana() as w:
            self.assertTrue(w.abrir_ruta(GEMMA))
            play(w)
            with mock.patch.object(Ventana, "_variables_completo", contar("completo", Ventana._variables_completo)), \
                    mock.patch.object(Ventana, "_traza_completa", contar("traza", Ventana._traza_completa)), \
                    mock.patch.object(navegacion, "registros_base", contar("registros", navegacion.registros_base)), \
                    mock.patch.object(Ventana, "refrescar", contar("refrescos", Ventana.refrescar)):
                hechos = self.pasos(w, 12)
                c.comprobar_tablas(w, "t")
                c.comprobar_traza(w, "t")
                c.comprobar_navegacion(w, "t")
        self.assertGreater(hechos, 4)
        self.assertLess(cuentas["completo"], cuentas["refrescos"] // 2)
        self.assertLess(cuentas["traza"], cuentas["refrescos"] // 2)
        self.assertLess(cuentas["registros"], cuentas["refrescos"])
