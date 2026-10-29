import os
import unittest
import time
from pathlib import Path
import tempfile
from unittest import mock

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
    def test_SFIO25_arrastre_desde_tarjeta_asignada(self):
        """REQ-SIM-03: el gesto comienza sobre la tarjeta, no solo sobre la lista."""
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QFrame
        from unittest.mock import patch
        app = QApplication.instance() or QApplication([])
        p = PanelES()
        try:
            p.cargar(M().var("a").step("0", True).doc,
                     Configuracion(senales=[Senal("a", "discrete", 0)]))
            p.show()
            app.processEvents()
            tarjeta = p.terminales[("discrete",0)].findChild(QFrame,"asignacionES")
            inicio = QPoint(10,10)
            app.sendEvent(tarjeta, QMouseEvent(QEvent.Type.MouseButtonPress,QPointF(inicio),
                          QPointF(tarjeta.mapToGlobal(inicio)),Qt.MouseButton.LeftButton,
                          Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier))
            fin = QPoint(60,10)
            with patch("escritorio.entradas_salidas.QDrag") as arrastre:
                app.sendEvent(tarjeta,QMouseEvent(QEvent.Type.MouseMove,QPointF(fin),
                              QPointF(tarjeta.mapToGlobal(fin)),Qt.MouseButton.NoButton,
                              Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier))
                self.assertTrue(arrastre.return_value.exec.called)
        finally:
            p.close()
            p.deleteLater()
            app.processEvents()

    def test_SFIO24_canales_offset_mover_desasignar_y_persistir(self):
        """REQ-DAT-02, REQ-SIM-03: canales explícitos y movimiento desde el slot."""
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        app = QApplication.instance() or QApplication([])
        p = PanelES()
        try:
            doc = M().var("a").var("b").var("q", "output").step("0", True).doc
            p.cargar(doc)
            p.offsets["discrete"].setValue(5)
            p.cantidades["discrete"].setValue(2)
            p.cantidades["coil"].setValue(1)
            self.assertTrue(p._aplicar())
            self.assertEqual({d for a, d in p.terminales if a == "discrete"}, {5,6})
            p.show()
            app.processEvents()
            self.assertTrue(p.asignar("a", "discrete", 5))
            mime = p.terminales[("discrete",5)].mimeData()
            destino = p.terminales[("discrete",6)]
            app.sendEvent(destino, QDragEnterEvent(QPoint(5,5), Qt.DropAction.MoveAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
            drop = QDropEvent(QPointF(5,5), Qt.DropAction.MoveAction, mime,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            app.sendEvent(destino, drop)
            self.assertTrue(drop.isAccepted())
            self.assertEqual([(s.variable,s.direccion) for s in p.obtener().senales], [("a",6)])
            p.terminales[("discrete",6)].b_quitar.click()
            self.assertEqual(p.obtener().senales, [])
            p.asignar("b", "discrete",6)
            p.cantidades["discrete"].setValue(1)
            self.assertFalse(p._aplicar())
            self.assertIn("fuera", p.error_config.text())
            p.quitar("b")
            self.assertEqual({d for a,d in p.terminales if a=="discrete"}, {5})
            with tempfile.TemporaryDirectory() as tmp:
                ruta=Path(tmp)/"conexion.json"
                p.obtener().guardar(ruta,doc)
                c=Configuracion.cargar(ruta,doc)
                self.assertEqual(c.canales["discrete"], {"offset":5,"cantidad":1})
        finally:
            p.close()
            p.deleteLater()
            app.processEvents()

    def test_SFIO22_observar_solo_entradas_desde_editor(self):
        """REQ-SIM-03: conexión de observación sin programa compilado ni salidas."""
        from escritorio.ventana import Ventana
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        peticiones = []
        def responder(p):
            peticiones.append(p)
            return b"\x02\x01\x01"
        def esperar_ui(condicion):
            limite = time.monotonic() + 3
            while not condicion():
                app.processEvents()
                if time.monotonic() >= limite:
                    self.fail(w.modbus.mensaje)
                time.sleep(.002)
        with tempfile.TemporaryDirectory() as tmp, servidor(responder) as sc:
            w = Ventana(recuperacion=Path(tmp))
            try:
                w.nuevo()
                self.assertIsNone(w.edicion.nueva_variable("sensor"))
                vid = w.edicion.ed.model["variables"][0]["id"]
                w.a_es.trigger()
                self.assertEqual(w.panel_es.doc, w.edicion.ed.model)
                w.panel_es.cargar(w.panel_es.doc, Configuracion(puerto=sc.puerto, periodo_ms=20,
                                        senales=[Senal(vid, "discrete", 0)]))
                ruta = Path(tmp) / "proyecto"
                w.edicion.guardar(ruta)
                w.panel_es._aplicar()
                guardado = Configuracion.cargar(ruta / "conexion-factoryio.json", w.edicion.ed.model)
                self.assertEqual([s.variable for s in guardado.senales], [vid])
                w._conectar_modbus()
                esperar_ui(lambda: w.modbus.estado == "conectado")
                esperar_ui(lambda: w.panel_es.indicadores[vid][1].text() == "1")
                self.assertIsNone(w.modbus.adaptador.sesion)
                self.assertEqual(w.modbus.adaptador.salidas, [])
                self.assertTrue(w.a_ejecutar.isEnabled())
                self.assertTrue(peticiones)
                self.assertTrue(all(p[0] == 2 for p in peticiones), "No se escribe ninguna salida")
                w._desconectar_modbus()
                esperar_ui(lambda: not w.modbus.activo)
            finally:
                w.edicion = None  # descarta solo el documento de esta prueba
                w.close()
                w.deleteLater()
                app.processEvents()

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
                w.panel_es.tabla.cellWidget(1, 0).setChecked(True)
                self.assertTrue(w.a_ejecutar.isEnabled())
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
                socket_anterior = w.modbus.cliente._socket
                w.reiniciar()
                esperar_ui(lambda: w.v.s is not anterior and not w.modbus.reiniciando)
                self.assertTrue(w.modbus.activo)
                self.assertEqual(w.modbus.estado, "conectado")
                self.assertIs(w.modbus.cliente._socket, socket_anterior)
                self.assertFalse(w.a_ejecutar.isChecked())
                self.assertFalse(w.v.s.z.values["sensor"])
                self.assertEqual(w.modbus.escritos, {"motor": False})
            finally:
                w.close()
                w.deleteLater()
                app.processEvents()

    def _ventana_conectada(self, tmp, sc, doc, senales):
        """Una ventana con el modelo dado, mapa asignado y conexión establecida (en Pausa, solo observando)."""
        from escritorio.ventana import Ventana
        w = Ventana(recuperacion=Path(tmp))
        w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": doc,
                    "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
        w._cargar()
        w.panel_es.cargar(doc, Configuracion(puerto=sc.puerto, periodo_ms=20, senales=senales))
        w._conectar_modbus()
        return w

    @staticmethod
    def _esperar(app, w, condicion):
        limite = time.monotonic() + 3
        while not condicion():
            app.processEvents()
            if time.monotonic() >= limite:
                raise AssertionError(w.modbus.mensaje)
            time.sleep(.002)

    @staticmethod
    def _servidor_planta(escrituras):
        """Sensor discreto siempre a 1; las escrituras de coils se anotan como (dirección, valor)."""
        def responder(p):
            if p[0] == 15:
                escrituras.append((int.from_bytes(p[1:3], "big"), p[6] & 1))
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        return responder

    def test_SFIO27_la_conexion_sobrevive_a_play_pausa_edicion_reinicio_y_abrir(self):
        """REQ-SIM-02, REQ-SIM-03: una vez conectado, ni Play, Pausa, editar, Reiniciar ni abrir otro ejemplo cierran
        Modbus; Pausa conserva TCP y salidas, Play vincula una sesión nueva al mismo TCP y solo Desconectar cierra."""
        from PySide6.QtWidgets import QMessageBox
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras = []
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta(escrituras)) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            w = self._ventana_conectada(tmp, sc, m.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado")
                socket = w.modbus.cliente._socket
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (False, "editar"), "conectar no ejecuta")
                # Play: la sesión se vincula al TCP existente y la planta recibe la salida
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos.get("motor") is True)
                self.assertEqual((w.modo, w.modbus.estado), ("simular", "conectado"))
                self.assertIs(w.modbus.cliente._socket, socket)
                # Pausa: edición, TCP y salidas conservados (no se escribe cero), la lectura continúa
                w.a_ejecutar.setChecked(False)
                n = len(escrituras)
                self.assertEqual((w.modo, w.modbus.estado, w.modbus.escritos), ("editar", "conectado", {"motor": True}))
                self.assertIsNone(w.modbus.adaptador.sesion)
                fin = time.monotonic() + .1
                esperar(lambda: time.monotonic() >= fin)
                self.assertEqual(len(escrituras), n, "Pausa no escribe en la planta")
                self.assertIs(w.modbus.cliente._socket, socket)
                self.assertTrue(w.modbus.activo and w.rt.isActive(), "sigue observando las entradas")
                # Editar (cambia el modelo) y Play otra vez: sesión nueva, mismo TCP
                anterior = w.v.s
                self.assertIsNone(w.edicion.nueva_variable("otra"))
                w.a_ejecutar.setChecked(True)
                self.assertIsNot(w.v.s, anterior)
                esperar(lambda: not w.modbus.reiniciando and w.modbus.escritos.get("motor") is True)
                self.assertEqual((w.modo, w.modbus.estado), ("simular", "conectado"))
                self.assertIs(w.modbus.cliente._socket, socket)
                # Reiniciar en Play: sigue en Play y en la misma conexión
                anterior = w.v.s
                w.reiniciar()
                self.assertIsNot(w.v.s, anterior)
                self.assertTrue(w.a_ejecutar.isChecked())
                esperar(lambda: not w.modbus.reiniciando and w.modbus.escritos.get("motor") is True)
                self.assertIs(w.modbus.cliente._socket, socket)
                # Reiniciar en Pausa: estado inicial, parado, conexión viva
                w.a_ejecutar.setChecked(False)
                w.reiniciar()
                esperar(lambda: not w.modbus.reiniciando and w.modbus.escritos == {"motor": False})
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo, w.modbus.estado), (False, "editar", "conectado"))
                self.assertIsNone(w.modbus.adaptador.sesion)
                self.assertIs(w.modbus.cliente._socket, socket)
                # Abrir otro ejemplo: la conexión sigue; lo que escribía el modelo anterior pasa a cero y el mapa es el nuevo
                w.a_ejecutar.setChecked(True)
                esperar(lambda: not w.modbus.reiniciando and w.modbus.escritos.get("motor") is True)
                with mock.patch("escritorio.ventana.QMessageBox.question") as pregunta:
                    pregunta.return_value = QMessageBox.StandardButton.Discard  # «otra» quedó sin guardar
                    w.cargar_ejemplo("temporizada")
                self.assertEqual(pregunta.call_count, 1)
                esperar(lambda: w.modbus.escritos == {"motor": False} and escrituras[-1] == (0, 0))
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo, w.modbus.estado), (False, "editar", "conectado"))
                self.assertIs(w.modbus.cliente._socket, socket)
                self.assertEqual(w.panel_es.doc["id"], w.v.doc["id"])
                self.assertEqual(w.modbus.adaptador.entradas, [], "mapa vacío del ejemplo nuevo")
                # Solo Desconectar cierra
                w._desconectar_modbus()
                esperar(lambda: not w.modbus.activo)
                self.assertEqual(w.modbus.estado, "desconectado")
            finally:
                w.edicion.ed.dirty = False  # el cierre no pregunta
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO28_mapa_invalido_tras_editar_avisa_y_no_arranca(self):
        """REQ-SIM-03: si lo editado deja el mapa sin su variable, Play no arranca el control externo, avisa en el panel
        de E/S y la conexión se conserva; al revisar la asignación (aquí, deshacer) se puede ejecutar."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras = []
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta(escrituras)) as sc:
            m = M().var("sensor").var("motor", "output").var("luz", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            w = self._ventana_conectada(tmp, sc, m.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0),
                                                         Senal("luz", "coil", 1)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado")
                socket = w.modbus.cliente._socket
                luz = next(v["id"] for v in w.edicion.ed.model["variables"] if v["name"] == "luz")
                self.assertIsNone(w.edicion.quitar_variable(luz))
                with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
                    w.a_ejecutar.setChecked(True)
                self.assertEqual(aviso.call_count, 1)
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (False, "editar"))
                self.assertIn("asignaci", w.panel_es.estado.text())
                self.assertIn("conexión se conserva", w.panel_es.estado.text())
                for _ in range(10):  # los tics siguientes no borran el aviso
                    app.processEvents()
                    time.sleep(.01)
                self.assertIn("asignaci", w.panel_es.estado.text())
                self.assertTrue(w.modbus.activo and w.modbus.estado == "conectado")
                self.assertIs(w.modbus.cliente._socket, socket)
                self.assertFalse([e for e in escrituras if e[0] == 0 and e[1]], "no se controla la planta")
                w.edicion.deshacer()  # la asignación vuelve a ser válida
                w.a_ejecutar.setChecked(True)
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (True, "simular"))
                esperar(lambda: w.modbus.escritos.get("motor") is True)
                self.assertIs(w.modbus.cliente._socket, socket)
            finally:
                w.edicion.ed.dirty = False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO29_inestable_con_modbus_avisa_pausa_y_pone_salidas_a_cero(self):
        """REQ-SEM-07, REQ-SIM-02: un GRAFCET inestable con la planta conectada se detiene (Pausa/edición), avisa una sola
        vez, lleva las salidas a cero y conserva la conexión."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras = []
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta(escrituras)) as sc:
            # con «sensor» a 1, E0 y E1 se alternan sin fin en tiempo cero
            m = M().var("sensor").var("motor", "output").step("E0", True).step("E1")
            m.trans("t1", ["E0"], ["E1"], "sensor").trans("t2", ["E1"], ["E0"], "sensor").cont("E1", "motor")
            w = self._ventana_conectada(tmp, sc, m.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado")
                socket = w.modbus.cliente._socket
                with mock.patch.object(type(w), "_avisar_inestable", autospec=True) as aviso:
                    w.a_ejecutar.setChecked(True)
                    esperar(lambda: aviso.call_count == 1)
                    esperar(lambda: w.modbus.escritos == {"motor": False} and escrituras and escrituras[-1] == (0, 0))
                    fin = time.monotonic() + .15
                    esperar(lambda: time.monotonic() >= fin)  # varios tics más: sigue siendo un solo aviso
                    self.assertEqual(aviso.call_count, 1)
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (False, "editar"))
                self.assertTrue(w.modbus.activo)
                self.assertEqual(w.modbus.estado, "conectado")
                self.assertIs(w.modbus.cliente._socket, socket)
                self.assertIsNone(w.modbus.adaptador.sesion)
                self.assertTrue(any("D-LIM-EVOL" in w.lista_diag.item(i).text() for i in range(w.lista_diag.count())))
                w._desconectar_modbus()
                esperar(lambda: not w.modbus.activo)
            finally:
                w.edicion.ed.dirty = False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO30_play_inmediato_tras_reiniciar_en_pausa_no_vuelve_a_pausa(self):
        """REQ-SIM-02, REQ-SIM-03: Reiniciar en Pausa y Play inmediato (antes de que termine el reinicio) deja la ejecución
        en Play: la intención más reciente cancela el paso a observación; el reinicio no se pierde y el TCP es el mismo."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras = []
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta(escrituras)) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            w = self._ventana_conectada(tmp, sc, m.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado")
                socket = w.modbus.cliente._socket
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos.get("motor") is True)
                w.a_ejecutar.setChecked(False)
                anterior = w.v.s
                w.reiniciar()
                self.assertTrue(w.modbus.reiniciando, "el reinicio aún no ha terminado")
                w.a_ejecutar.setChecked(True)  # inmediato: sin dar tiempo a que termine el reinicio
                self.assertTrue(w.a_ejecutar.isChecked())
                esperar(lambda: not w.modbus.reiniciando and w.modbus.en_marcha)
                for _ in range(15):  # varios tics más: Play no se desmarca solo
                    app.processEvents()
                    time.sleep(.01)
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (True, "simular"))
                self.assertIsNotNone(w.modbus.adaptador.sesion)
                self.assertIs(w.modbus.adaptador.sesion, w.v.s)
                self.assertIsNot(w.v.s, anterior, "el reinicio no se pierde")
                self.assertIs(w.modbus.cliente._socket, socket)
                self.assertIs(w.modbus.escritos.get("motor"), True)
            finally:
                w.edicion.ed.dirty = False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO31_abrir_otro_proyecto_pone_a_cero_aunque_la_escritura_siguiera_en_vuelo(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): Play y Pausa con una escritura de salidas en vuelo descartan su respuesta
        (modbus.escritos sigue vacío) pero la planta ya ha recibido el valor; al abrir otro proyecto se ponen a cero las
        salidas del mapa anterior igualmente."""
        import threading
        from PySide6.QtWidgets import QMessageBox
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras = []
        armada, llegada, puerta = threading.Event(), threading.Event(), threading.Event()
        planta = self._servidor_planta(escrituras)
        def responder(p):
            if p[0] == 15 and p[6] & 1 and armada.is_set() and not puerta.is_set():  # la escritura de motor = 1 del reinicio espera: en vuelo
                escrituras.append((int.from_bytes(p[1:3], "big"), p[6] & 1))
                llegada.set()
                puerta.wait(5)
                return p[:5]
            return planta(p)
        with tempfile.TemporaryDirectory() as tmp, servidor(responder) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor")  # motor = 1 desde la situación inicial: el reinicio de Play ya lo escribe
            w = self._ventana_conectada(tmp, sc, m.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado")
                armada.set()
                w.a_ejecutar.setChecked(True)
                esperar(llegada.is_set)  # la escritura del modelo ya está en la planta, sin respuesta todavía
                self.assertEqual(escrituras[-1], (0, 1))
                w.a_ejecutar.setChecked(False)  # Pausa: la respuesta se descarta
                self.assertEqual(w.modbus.escritos, {})
                with mock.patch("escritorio.ventana.QMessageBox.question") as pregunta:
                    pregunta.return_value = QMessageBox.StandardButton.Discard
                    w.cargar_ejemplo("temporizada")
                puerta.set()  # la planta responde; la petición de cero va detrás
                esperar(lambda: w.modbus.escritos == {"motor": False} and escrituras[-1] == (0, 0))
                self.assertTrue(w.modbus.activo)
            finally:
                puerta.set()
                w.edicion.ed.dirty = False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO32_cerrar_la_ventana_cierra_el_tcp(self):
        """REQ-SIM-03: cerrar la ventana con la conexión viva cierra el TCP (no queda el socket abierto contra la planta)."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras = []
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta(escrituras)) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            w = self._ventana_conectada(tmp, sc, m.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado")
                cliente = w.modbus.cliente
                self.assertIsNotNone(cliente._socket)
                w.edicion.ed.dirty = False  # el cierre no pregunta
                self.assertTrue(w.close())
                esperar(lambda: cliente._socket is None)
                self.assertEqual(w.modbus.estado, "desconectado")
            finally:
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
