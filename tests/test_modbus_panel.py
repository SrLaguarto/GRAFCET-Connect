import os
import unittest
import time
from pathlib import Path
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    from escritorio.entradas_salidas import PanelES
    QT = True
except ImportError:
    QT = False

from conexion.configuracion import Configuracion, Senal
from grafcet.builder import M


@unittest.skipUnless(QT, "Falta PySide6")
class PanelTests(unittest.TestCase):
    def test_SFIO19_arrastrar_mover_y_reemplazar(self):
        """REQ-SIM-03: eventos de arrastre, movimiento, sustitución, tipos y bloqueo."""
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        app = QApplication.instance() or QApplication([])
        p = PanelES()
        try:
            p.cargar(M().var("a").var("b").var("q", "output").step("0", True).doc)
            p.show()
            app.processEvents()
            def soltar(lista, indice, area, direccion):
                mime = lista.mimeData([lista.item(indice)])
                terminal = p.terminales[(area, direccion)]
                entrar = QDragEnterEvent(QPoint(5, 5), Qt.DropAction.CopyAction, mime,
                                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                app.sendEvent(terminal, entrar)
                drop = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime,
                                  Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                app.sendEvent(terminal, drop)
                return drop.isAccepted()
            self.assertTrue(soltar(p.lista_entradas, 0, "discrete", 0))
            self.assertTrue(soltar(p.lista_entradas, 0, "discrete", 1))
            self.assertEqual([(s.variable, s.direccion) for s in p.obtener().senales], [("a", 1)])
            self.assertTrue(soltar(p.lista_entradas, 1, "discrete", 1))
            self.assertEqual([(s.variable, s.direccion) for s in p.obtener().senales], [("b", 1)])
            self.assertFalse(soltar(p.lista_salidas, 0, "discrete", 0))
            self.assertTrue(soltar(p.lista_salidas, 0, "coil", 0))
            p.ocupado(True)
            self.assertFalse(p.admite("a", "discrete"))
            self.assertFalse(p.terminales[("coil", 0)].acceptDrops())
            p.quitar("q")
            self.assertEqual(len(p.obtener().senales), 2)
            p.ocupado(False)
            p.quitar("q")
            self.assertEqual([s.variable for s in p.obtener().senales], ["b"])
        finally:
            p.close()
            p.deleteLater()
            app.processEvents()

    def test_SFIO20_pantalla_simple_y_check_confirmado(self):
        """REQ-SIM-03: ajustes fuera de pantalla principal y check de conexión real."""
        app = QApplication.instance() or QApplication([])
        p = PanelES()
        try:
            p.cargar(M().var("sensor").step("0", True).doc)
            p.show()
            app.processEvents()
            self.assertFalse(p.tabla.isVisible())
            self.assertFalse(p.host.isVisible())
            from PySide6.QtCore import QPoint
            izquierda = p.lista_entradas.mapTo(p, QPoint()).x()
            centro = p.modulo.mapTo(p, QPoint()).x()
            derecha = p.lista_salidas.mapTo(p, QPoint()).x()
            self.assertLess(izquierda, centro)
            self.assertLess(centro, derecha)
            self.assertLess(p.modulo.width(), p.width() * .7)
            p.mostrar_estado("conectando", "Conectando…")
            self.assertNotEqual(p.check.text(), "✓")
            p.mostrar_estado("conectado", "Conectado · Ejecutando")
            self.assertEqual(p.check.text(), "✓")
            self.assertEqual(p.estado.text(), "Conectado")
            p.mostrar_estado("error", "Conexión perdida")
            self.assertEqual(p.check.text(), "✕")
            p.b_configuracion.click()
            self.assertFalse(p.tabla.isVisible())
            self.assertTrue(p.host.isVisible())
            p.b_avanzado.click()
            self.assertTrue(p.tabla.isVisible())
        finally:
            p.dialogo_config.close()
            p.close()
            p.deleteLater()
            app.processEvents()

    def test_SFIO17_etiquetas_y_direcciones_independientes(self):
        """REQ-SIM-03: etiquetas explicadas conservan claves de conexión y separan áreas."""
        app = QApplication.instance() or QApplication([])
        p = PanelES()
        try:
            doc = M().var("PM").var("PP").var("Q", "output").step("0", True).doc
            p.cargar(doc)
            self.assertTrue(p.ayuda_vacio.isVisibleTo(p))
            for fila in range(3):
                p.tabla.cellWidget(fila, 0).setChecked(True)
                self.assertIn("(", p.tabla.cellWidget(fila, 4).currentText())
                self.assertIn("(", p.tabla.cellWidget(fila, 6).currentText())
            config = p.obtener()
            self.assertEqual([(s.area, s.direccion, s.formato) for s in config.senales],
                             [("discrete", 0, "BOOL"), ("discrete", 1, "BOOL"), ("coil", 0, "BOOL")])
            p._aplicar()
            self.assertFalse(p.ayuda_vacio.isVisibleTo(p))
            self.assertEqual(set(p.indicadores), {"PM", "PP", "Q"})
        finally:
            p.close()
            p.deleteLater()
            app.processEvents()

    def test_SFIO18_proyecto_listo_y_avisos(self):
        """REQ-SIM-02/03: proyecto manual preparado y mensajes accionables sin red."""
        from escritorio.ventana import Ventana
        from conexion.adaptador import Adaptador
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w = Ventana(recuperacion=Path(tmp))
            try:
                w.panel_es.b_prueba_guiada.click()
                self.assertIn("PM y dos cintas", w.windowTitle())
                self.assertEqual(w.paginas_es.currentIndex(), 1)
                w.panel_es.b_volver.click()
                self.assertEqual(w.paginas_es.currentIndex(), 0)
                w.a_es.trigger()
                self.assertEqual(w.paginas_es.currentIndex(), 1)
                self.assertFalse(w.a_ejecutar.isChecked())
                config = w.panel_es.obtener()
                self.assertEqual(config.host, "192.168.1.133")
                self.assertEqual([(s.variable, s.area, s.direccion) for s in config.senales],
                                 [("PM", "discrete", 0), ("Q00", "coil", 0), ("Q01", "coil", 1)])
                a = Adaptador(config, w.v.s)
                self.assertEqual(w.v.s.z.situation, frozenset(["0"]))
                self.assertEqual(a.valores_salida(), {"Q00": False, "Q01": False})
                a.aplicar({"PM": False})
                self.assertEqual(w.v.s.z.situation, frozenset(["0"]))
                a.aplicar({"PM": True})
                self.assertEqual(w.v.s.z.situation, frozenset(["1"]))
                self.assertEqual(a.valores_salida(), {"Q00": True, "Q01": True})
                a.aplicar({"PM": False})
                self.assertEqual(w.v.s.z.situation, frozenset(["1"]))
                self.assertEqual(a.valores_salida(), {"Q00": True, "Q01": True})
                for fila in range(3):
                    w.panel_es.tabla.cellWidget(fila, 0).setChecked(False)
                w._conectar_modbus()
                self.assertIn("Usar", w.panel_es.estado.text())
                self.assertFalse(w.modbus.activo)
                w.v.s = None
                w._conectar_modbus()
                self.assertEqual(w.panel_es.estado.text(), "Revisar GRAFCET")
                self.assertIn("diagnósticos", w.panel_es.estado.toolTip())
                self.assertIn("manifest.json", w.panel_es.estado.toolTip())
            finally:
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO16_ventana_ciclo_y_reinicio(self):
        """REQ-SIM-02, REQ-SIM-03: controles Qt y descarte al reiniciar sesión."""
        from escritorio.ventana import Ventana
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        def esperar_ui(condicion):
            limite = time.monotonic() + 3
            while not condicion():
                app.processEvents()
                if time.monotonic() >= limite:
                    self.fail(w.modbus.mensaje)
                time.sleep(.002)
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p: b"\x02\x01\x01" if p[0] == 2 else p[:5]) as sc:
            w = Ventana(recuperacion=Path(tmp))
            try:
                m = M().var("sensor").var("motor", "output").step("E0", True)
                m.cont("E0", "motor", "sensor")
                w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": m.doc,
                            "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
                w._cargar()
                w.panel_es.cargar(m.doc, Configuracion(puerto=sc.puerto, periodo_ms=20,
                    senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)]))
                w._conectar_modbus()
                esperar_ui(lambda: w.modbus.estado == "conectado")
                self.assertFalse(w.a_ejecutar.isChecked())
                w.a_ejecutar.setChecked(True)
                esperar_ui(lambda: w.modbus.escritos.get("motor") is True)
                w.a_ejecutar.setChecked(False)
                instante = w.v.s.z.time
                fin = time.monotonic() + .08
                esperar_ui(lambda: time.monotonic() >= fin)
                self.assertEqual(w.v.s.z.time, instante)
                self.assertFalse(w.botones["sensor"].isEnabled())
                anterior = w.v.s
                w.reiniciar()
                esperar_ui(lambda: w.v.s is not anterior)
                self.assertFalse(w.modbus.activo)
                self.assertFalse(w.a_ejecutar.isChecked())
                self.assertFalse(w.v.s.z.values["sensor"])
            finally:
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO08_panel_y_mapa(self):
        """REQ-SIM-03: E/S externas configurables con tipo y valor visibles."""
        app = QApplication.instance() or QApplication([])
        doc = M().var("sensor").var("motor", "output").var("velocidad", "input", "int").step("E0", True).doc
        c = Configuracion(senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0),
                                   Senal("velocidad", "input-register", 0, "INT16")])
        p = PanelES()
        p.cargar(doc, c)
        self.assertEqual(p.obtener().senales, c.senales)
        p.mostrar_valores({"sensor": True, "motor": False, "velocidad": -12})
        self.assertEqual(p.indicadores["velocidad"][1].text(), "-12")
        p.ocupado(True)
        self.assertFalse(p.config_widget.isEnabled())
        p.close()
        p.deleteLater()
        app.processEvents()
