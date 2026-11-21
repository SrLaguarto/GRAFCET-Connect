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
        self.assertIn(f.tipo, ("ESC-9", "ESC-3"))

    def test_SESC85_un_tramo_largo_de_simulacion_al_azar_pasa_todos_los_oraculos(self):
        """REQ-SIM-01: 120 operaciones al azar sobre GEMMA, con tramos largos en simulación, no dan ningún fallo."""
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA
        self.assertIsNone(c.ejecutar_nuevo(GEMMA, c.generar(13, 120)))
