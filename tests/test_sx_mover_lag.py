"""SX: barra alcanzable e intercambio directo sin trabajo visual redundante (REQ-EDT-02)."""
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QEvent, QObject, QPoint, Qt
    from PySide6.QtGui import QRegion
    from PySide6.QtTest import QTest
    from conexion.http_directo import ClienteDirecto
    from conexion import intercambio_directo
    from escritorio import estilo
    from escritorio.entradas_salidas import IndicadorES, NIVEL_ACTIVO
    from tools import hoja_contactos as HC
    import test_sw_propiedades as SW
    from ayuda_sx_conexion import contexto, esperar
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class MoverX(unittest.TestCase):
    def preparar(self):
        return SW.PropiedadesW.contexto(self)

    def arrastrar(self, v, delta):
        SW.PropiedadesW.arrastrar(self, v, delta)

    def test_SX1_barra_dentro_y_contenido_fuera(self):
        """REQ-EDT-02: la barra permanece recuperable en los cuatro extremos."""
        c, p, v = self.preparar()
        tamano = v.size()
        for delta in (QPoint(-5000, -5000), QPoint(5000, 5000), QPoint(-5000, 5000)):
            self.arrastrar(v, delta)
            SW.PropiedadesW.comprobar_limites(self, c, v)
            self.assertEqual(v.size(), tamano)
            cliente = c.w.rect().translated(c.w.mapToGlobal(QPoint()))
            dentro = cliente.intersected(v.geometry())
            self.assertLess(dentro.width() * dentro.height(), v.width() * v.height() / 3)
            self.assertFalse(v.mask().isEmpty())
            self.assertTrue(v.mask().subtracted(QRegion(dentro.translated(-v.pos()))).isEmpty())
        cierre = v.b_cerrar.mapToGlobal(v.b_cerrar.rect().center())
        self.assertTrue(cliente.contains(cierre), "al salir por la izquierda, la cruz sigue alcanzable")

    def test_SX2_un_move_sin_resize_y_agarre_sigue_cursor(self):
        """REQ-EDT-02: se limita el destino antes de mover, sin un segundo salto correctivo."""
        c, p, v = self.preparar()
        origen = QPoint(100, v.cabecera.height() // 2)
        QTest.mousePress(v.cabecera, Qt.MouseButton.LeftButton, pos=origen)
        antes = v.pos()
        with patch.object(v, "move", wraps=v.move) as mover, patch.object(v, "resize", wraps=v.resize) as tamano:
            QTest.mouseMove(v.cabecera, origen + QPoint(20, 10))
            self.assertEqual(mover.call_count, 1)
            self.assertEqual(tamano.call_count, 0)
        self.assertEqual(v.pos(), antes + QPoint(20, 10))
        with patch.object(v, "move", wraps=v.move) as mover:
            QTest.mouseMove(v.cabecera, origen + QPoint(5000, 5000))
            self.assertEqual(mover.call_count, 1)
        QTest.mouseRelease(v.cabecera, Qt.MouseButton.LeftButton, pos=origen)

    def test_SX3_reabrir_centra_y_retira_recorte(self):
        """REQ-EDT-02: la posición de X no se conserva al reabrir."""
        c, p, v = self.preparar()
        self.arrastrar(v, QPoint(-5000, 5000))
        QTest.keyClick(v, Qt.Key.Key_Escape)
        self.assertFalse(v.isVisible())
        c.w._abrir_opciones()
        HC._bombear(5)
        self.assertLessEqual((v.geometry().center() - c.w.flot._area().center()).manhattanLength(), 2)
        self.assertTrue(v.mask().isEmpty())

    def test_SX4_redimensionar_conserva_barra(self):
        """REQ-EDT-02: el límite al cambiar el cliente es el mismo que al arrastrar."""
        c, p, v = self.preparar()
        self.arrastrar(v, QPoint(5000, 5000))
        c.w.resize(960, 700)
        HC._bombear(8)
        SW.PropiedadesW.comprobar_limites(self, c, v)

    def test_SX12_clic_en_zona_oculta_es_clic_fuera(self):
        """REQ-EDT-02: la zona que sale del cliente no cuenta como interior visible de Propiedades."""
        c, p, v = self.preparar()
        seleccion = list(c.e.sel)
        self.arrastrar(v, QPoint(-5000, 5000))
        punto = v.rect().center()
        self.assertFalse(v.mask().contains(punto))
        QTest.mouseClick(v, Qt.MouseButton.LeftButton, pos=punto)
        self.assertFalse(v.isVisible())
        self.assertEqual(c.e.sel, seleccion)


@unittest.skipUnless(QT, "requiere PySide6")
class IntercambioX(unittest.TestCase):
    def test_SX5_red_lenta_fuera_del_hilo_interfaz(self):
        """REQ-EDT-02: HTTP tarda 150 ms y la interfaz sigue atendiendo sus ciclos."""
        hilos = []
        principal = threading.get_ident()
        original = ClienteDirecto.pedir

        def pedir(cliente, *args, **kwargs):
            hilos.append(threading.get_ident())
            return original(cliente, *args, **kwargs)
        with patch.object(ClienteDirecto, "pedir", pedir):
            c, servidor = contexto(self, retardo=.15)
            limites = []
            for _ in range(30):
                inicio = time.perf_counter()
                with c.w.candado:  # (V2-E7: el coordinador se toca con el candado)
                    c.w.modbus.tick()
                limites.append((time.perf_counter() - inicio) * 1000)
                QTest.qWait(5)
        self.assertTrue(hilos)
        self.assertNotIn(principal, hilos)
        self.assertLess(max(limites), 15, "margen para máquinas de pruebas; la medida de entrega exige menos de 2 ms")

    def test_SX6_sin_cambios_no_redibuja_ni_reconstruye(self):
        """REQ-EDT-02: los resultados repetidos no rehacen el GRAFCET, tablas ni módulo."""
        c, servidor = contexto(self)
        p = c.w.panel_es

        class Pintados(QObject):
            def __init__(self):
                super().__init__()
                self.cuenta = 0

            def eventFilter(self, objeto, evento):
                if evento.type() == QEvent.Type.Paint:
                    self.cuenta += 1
                return False

        pintados = Pintados()
        c.w.diagrama.viewport().installEventFilter(pintados)
        with patch.object(c.w.diagrama, "mostrar", wraps=c.w.diagrama.mostrar) as dibujo:
            with patch.object(c.w.variables, "mostrar", wraps=c.w.variables.mostrar) as tabla:
                with patch.object(p.directa, "dibujar", wraps=p.directa.dibujar) as modulo:
                    with patch.object(p, "mostrar_estado", wraps=p.mostrar_estado) as estado:
                        QTest.qWait(350)
                        self.assertEqual([dibujo.call_count, tabla.call_count, modulo.call_count, estado.call_count],
                                         [0, 0, 0, 0])
        self.assertEqual(pintados.cuenta, 0)

    def test_SX7_un_valor_solo_toca_su_piloto(self):
        """REQ-EDT-02: una nueva muestra actualiza solo la señal que cambió."""
        c, servidor = contexto(self)
        tocados = []
        original = IndicadorES.fijar_nivel

        def fijar(led, nivel):
            tocados.append(led)
            return original(led, nivel)
        terminal = c.w.panel_es.directa.dibujo.terminales["0"]
        with patch.object(IndicadorES, "fijar_nivel", fijar):
            servidor.senales[0]["value"] = True
            esperar(lambda: terminal.led.nivel == NIVEL_ACTIVO)
            QTest.qWait(100)
        self.assertEqual(tocados, [terminal.led])
        self.assertEqual(terminal.valor.text(), "", "las booleanas solo se leen por el piloto")

    def test_SX8_traidas_sin_conectar_no_rehace_modulo_por_seleccion(self):
        """REQ-EDT-02: seleccionar y abrir Propiedades no cambia el catálogo ni sus filas."""
        c, servidor = contexto(self, conectar=False)
        p = c.w.panel_es
        objetos = dict(p.directa.dibujo.terminales)
        with patch.object(p.directa, "dibujar", wraps=p.directa.dibujar) as modulo:
            sid = c.e.ed.model["steps"][0]["id"]
            c.e.seleccionar([sid])
            c.w._abrir_opciones()
            HC._bombear(5)
            self.assertEqual(modulo.call_count, 0)
        self.assertEqual(objetos, p.directa.dibujo.terminales)

    def test_SX9_cero_variables_sin_refrescos_visuales(self):
        """REQ-EDT-02: conectar sin variables no repinta el indicador cada periodo."""
        c, servidor = contexto(self, numero=0)
        with patch.object(c.w, "_luz_es", wraps=c.w._luz_es) as luz:
            with patch.object(c.w.panel_es, "mostrar_estado", wraps=c.w.panel_es.mostrar_estado) as estado:
                QTest.qWait(350)
                self.assertEqual(luz.call_count, 0)
                self.assertEqual(estado.call_count, 0)
        self.assertFalse(any(p[1] == "/api/tag/values" for p in servidor.peticiones))

    def test_SX10_reenvio_forzado_no_reconstruye_tablas(self):
        """REQ-EDT-02: REFRESCO_S reenvía las salidas, sin redibujar un estado idéntico."""
        c, servidor = contexto(self)
        c.w.a_ejecutar.setChecked(True)
        esperar(lambda: c.w.modbus.en_marcha)
        QTest.qWait(250)
        puts = sum(p[0] == "PUT" for p in servidor.peticiones)
        with patch.object(intercambio_directo, "REFRESCO_S", .05):
            with patch.object(c.w.diagrama, "mostrar", wraps=c.w.diagrama.mostrar) as dibujo:
                with patch.object(c.w, "_filas", wraps=c.w._filas) as filas:
                    QTest.qWait(400)
                    # con el equipo cargado, el hilo de red puede tardar más: se espera al reenvío, con límite
                    esperar(lambda: sum(p[0] == "PUT" for p in servidor.peticiones) > puts)
                    self.assertEqual(dibujo.call_count, 0)
                    tablas = [x for x in filas.call_args_list if x.args[0] in (c.w.t_vars, c.w.t_temp)]
                    self.assertEqual(tablas, [])
        self.assertGreater(sum(p[0] == "PUT" for p in servidor.peticiones), puts)

    def test_SX11_ciclo_completo_de_interfaz_acotado(self):
        """REQ-EDT-02: el refresco completo de 60 señales no espera al HTTP ni rehace sus widgets."""
        c, servidor = contexto(self)
        medidas = []
        for _ in range(30):
            c.w._ultimo_refresco_modbus = 0
            inicio = time.perf_counter()
            c.w._tick()
            medidas.append((time.perf_counter() - inicio) * 1000)
            QTest.qWait(2)
        medidas.sort()
        self.assertLess(medidas[int(len(medidas) * .95)], 4, "objetivo 2 ms, con margen de ejecución")
        self.assertLess(max(medidas), 12)


if __name__ == "__main__":
    unittest.main()
