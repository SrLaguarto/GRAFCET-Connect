from helpers_grafnet import fixture_grafnet
import copy
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


def ajustes_de_prueba(tmp):
    """Los ajustes de la ventana en un .ini temporal: las pruebas que conectan no tocan los del usuario (la última IP)."""
    from PySide6.QtCore import QSettings
    return QSettings(str(Path(tmp) / "ajustes.ini"), QSettings.Format.IniFormat)


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
            app.processEvents()
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
        """REQ-SIM-03 (P-IMP-60): conexión de observación sin programa compilado: las entradas solo se leen; Conectar (en Pausa)
        pide exactamente un cero a cada salida asignada (coil y holding), antes de la primera lectura, y no se escribe nada más."""
        from escritorio.ventana import Ventana
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        peticiones, escrituras = [], []
        planta = self._planta_mixta(escrituras, [1])
        def responder(p):
            peticiones.append(p)
            return planta(p)
        def esperar_ui(condicion):
            limite = time.monotonic() + 3
            while not condicion():
                app.processEvents()
                if time.monotonic() >= limite:
                    self.fail(w.modbus.mensaje)
                time.sleep(.002)
        with tempfile.TemporaryDirectory() as tmp, servidor(responder) as sc:
            w = Ventana(ajustes_de_prueba(tmp))
            try:
                w.nuevo()
                self.assertIsNone(w.edicion.nueva_variable("sensor"))
                self.assertIsNone(w.edicion.nueva_variable("luz", "output"))
                self.assertIsNone(w.edicion.nueva_variable("consigna", "output", {"kind": "decimal", "scale": 2}))
                vid, luz, consigna = (v["id"] for v in w.edicion.ed.model["variables"])
                w.a_es.trigger()
                self.assertEqual(w.panel_es.doc, w.edicion.ed.model)
                w.panel_es.cargar(w.panel_es.doc, Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20,
                                        senales=[Senal(vid, "discrete", 0), Senal(luz, "coil", 3),
                                                 Senal(consigna, "holding", 5, "INT16")]))
                ruta = Path(tmp) / "proyecto"
                w.edicion.guardar(ruta)
                w.panel_es._aplicar()
                guardado = Configuracion.cargar(ruta / "conexion-factoryio.json", w.edicion.ed.model)
                self.assertEqual([s.variable for s in guardado.senales], [vid, luz, consigna])
                w._conectar_modbus()
                esperar_ui(lambda: w.modbus.estado == "conectado")
                esperar_ui(lambda: w.panel_es.indicadores[vid][1].text() == "1")
                self.assertIsNone(w.modbus.adaptador.sesion)
                self.assertEqual(w.modbus.adaptador.salidas, [], "sin programa compilado, el monitor no controla nada")
                self.assertEqual([s.variable for s in w.modbus.adaptador.salidas_control], [luz, consigna])
                self.assertFalse(w.a_ejecutar.isEnabled(), "Play no se usa desde E/S")
                w._mostrar_pagina(False)
                self.assertTrue(w.a_ejecutar.isEnabled())
                w._mostrar_pagina(True)
                esperar_ui(lambda: sum(p[0] == 2 for p in peticiones) >= 3)  # varias lecturas después de conectar
                self.assertEqual(escrituras, [("coil", 3, 0), ("holding", 5, 0)], "exactamente un cero a cada salida asignada")
                self.assertEqual([p[0] for p in peticiones[:2]], [15, 16], "el cero va antes de la primera lectura")
                self.assertEqual({p[0] for p in peticiones[2:]}, {2}, "después solo se leen las entradas")
                self.assertEqual(w.modbus.escritos, {luz: False, consigna: 0})
                w._desconectar_modbus()
                esperar_ui(lambda: not w.modbus.activo)
            finally:
                w.edicion = None  # descarta solo el documento de esta prueba
                if w.edicion is not None:w.edicion.ed.dirty=False
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
                app.processEvents()
                mime = lista.mimeData([lista.item(indice)])
                terminal = p.terminales[(area, direccion)]
                entrar = QDragEnterEvent(terminal.zona_asignacion().center(), Qt.DropAction.CopyAction, mime,
                                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                app.sendEvent(terminal, entrar)
                drop = QDropEvent(QPointF(terminal.zona_asignacion().center()), Qt.DropAction.CopyAction, mime,
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
            self.assertTrue(p.admite("a", "discrete"))
            self.assertTrue(p.terminales[("coil", 0)].acceptDrops())
            p.quitar("q")
            self.assertEqual(len(p.obtener().senales), 1)
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
            p.resize(1000, 600)
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
            self.assertTrue(p.ayuda_vacio.isVisibleTo(p))
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
            w = Ventana(ajustes_de_prueba(tmp))
            try:
                # El ensayo edita el mapa: usar una copia aislada, nunca el ejemplo del repositorio.
                import json
                import shutil
                origen = Path(__file__).resolve().parents[1] / "pruebas_manuales" / "factoryio_digital"
                copia = Path(tmp) / "prueba"
                shutil.copytree(origen, copia)
                ruta_mapa = copia / "conexion-factoryio.json"
                datos = json.loads(ruta_mapa.read_text(encoding="utf-8"))
                datos["senales"] = [{"variable": v, "area": a, "direccion": d, "formato": "BOOL", "escala": "1"}
                                     for v, a, d in [("PM", "discrete", 0), ("Q00", "coil", 0), ("Q01", "coil", 1)]]
                ruta_mapa.write_text(json.dumps(datos), encoding="utf-8")
                self.assertTrue(w.abrir_ruta(fixture_grafnet(copia)))
                w._mostrar_pagina(True)
                self.assertIn("PM y dos cintas", w.edicion.titulo)
                self.assertIn(w.edicion.archivo.name,w.windowTitle())
                self.assertEqual(w.paginas_es.currentIndex(), 1)
                w.panel_es.b_volver.click()
                self.assertEqual(w.paginas_es.currentIndex(), 0)
                w.a_es.trigger()
                self.assertEqual(w.paginas_es.currentIndex(), 1)
                self.assertFalse(w.a_ejecutar.isChecked())
                self.assertIsNone(w.v.s.z, "abrir la prueba deja Pausa sin estado: la sesión la arranca Play")
                config = w.panel_es.obtener()
                self.assertEqual(config.host, "192.168.1.133")
                self.assertEqual([(s.variable, s.area, s.direccion) for s in config.senales],
                                 [("PM", "discrete", 0), ("Q00", "coil", 0), ("Q01", "coil", 1)])
                w.a_ejecutar.setChecked(True)  # Play arranca la sesión desde la situación inicial
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
                w.a_ejecutar.setChecked(False)
                for fila in range(3):
                    w.panel_es.tabla.cellWidget(fila, 0).setChecked(False)
                with mock.patch.object(w.modbus,"iniciar") as iniciar:
                    w._conectar_modbus()
                self.assertFalse(iniciar.call_args.args[0].senales)
                self.assertFalse(w.modbus.activo)
                w.v.s = None
                w.panel_es.tabla.cellWidget(1, 0).setChecked(True)
                self.assertTrue(w.a_ejecutar.isEnabled())
            finally:
                if w.edicion is not None:w.edicion.ed.dirty=False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO16_ventana_ciclo_y_reinicio(self):
        """REQ-SIM-02, REQ-SIM-03: controles Qt; Pausa deja todo a 0 (sin sesión en marcha y con la salida a cero en la
        planta) y Reiniciar en Pausa solo vuelve a pedir el cero, sin cerrar el TCP."""
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
            w = Ventana(ajustes_de_prueba(tmp))
            try:
                m = M().var("sensor").var("motor", "output").step("E0", True)
                m.cont("E0", "motor", "sensor")
                w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": m.doc,
                            "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
                w._cargar()
                w.panel_es.cargar(m.doc, Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20,
                    senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)]))
                w._conectar_modbus()
                esperar_ui(lambda: w.modbus.estado == "conectado")
                self.assertFalse(w.a_ejecutar.isChecked())
                w.a_ejecutar.setChecked(True)
                esperar_ui(lambda: w.modbus.escritos.get("motor") is True)
                w.a_ejecutar.setChecked(False)
                esperar_ui(lambda: w.modbus.escritos == {"motor": False})  # Pausa: la salida pasa a cero
                self.assertIsNone(w.v.s.z, "sin sesión en marcha: ni etapas activas ni valores")
                fin = time.monotonic() + .08
                esperar_ui(lambda: time.monotonic() >= fin)
                self.assertIsNone(w.v.s.z, "el reloj no hace avanzar nada en Pausa")
                self.assertFalse(w.botones["sensor"].isEnabled())
                socket_anterior = w.modbus.cliente._socket
                w.reiniciar()  # en Pausa ya está todo a 0: solo vuelve a pedir el cero
                esperar_ui(lambda: w.modbus.escritos == {"motor": False} and not w.modbus.reiniciando)
                self.assertTrue(w.modbus.activo)
                self.assertEqual(w.modbus.estado, "conectado")
                self.assertIs(w.modbus.cliente._socket, socket_anterior)
                self.assertFalse(w.a_ejecutar.isChecked())
                self.assertIsNone(w.v.s.z)
                self.assertEqual(w.modbus.escritos, {"motor": False})
            finally:
                if w.edicion is not None:w.edicion.ed.dirty=False
                w.close()
                w.deleteLater()
                app.processEvents()

    def _ventana_conectada(self, tmp, sc, doc, senales):
        """Una ventana con el modelo dado, mapa asignado y conexión establecida (en Pausa: salidas a 0 y observando las entradas)."""
        from escritorio.ventana import Ventana
        w = Ventana(ajustes_de_prueba(tmp))
        w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": doc,
                    "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
        w._cargar()
        w.panel_es.cargar(doc, Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, senales=senales))
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
        Modbus; Pausa conserva el TCP pero deja las salidas a cero, Play vincula una sesión nueva al mismo TCP y solo
        Desconectar cierra."""
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
                # Pausa: edición y TCP conservados, la lectura continúa y todo a 0 (se escribe el cero de la salida asignada)
                w.a_ejecutar.setChecked(False)
                self.assertEqual((w.modo, w.modbus.estado), ("editar", "conectado"))
                self.assertIsNone(w.modbus.adaptador.sesion)
                esperar(lambda: w.modbus.escritos == {"motor": False} and escrituras[-1] == (0, 0))
                n = len(escrituras)
                fin = time.monotonic() + .1
                esperar(lambda: time.monotonic() >= fin)
                self.assertEqual(len(escrituras), n, "tras el cero, Pausa no escribe más en la planta")
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
                # Reiniciar en Pausa: ya está todo a 0 (solo vuelve a pedir el cero), parado, conexión viva
                w.a_ejecutar.setChecked(False)
                w.reiniciar()
                esperar(lambda: not w.modbus.reiniciando and w.modbus.escritos == {"motor": False})
                self.assertIsNone(w.v.s.z, "sin sesión en marcha")
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
                if w.edicion is not None:w.edicion.ed.dirty=False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO28_borrar_variable_asignada_depura_mapa_sin_impedir_play(self):
        """REQ-SIM-03: borrar una salida asignada solicita su cero, conserva TCP y permite Play con el mapa depurado."""
        from test_modbus import servidor
        app=QApplication.instance() or QApplication([]);escrituras=[]
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta(escrituras)) as sc:
            m=M().var("sensor").var("motor","output").var("luz","output").step("E0",True)
            m.cont("E0","motor","sensor")
            w=self._ventana_conectada(tmp,sc,m.doc,[Senal("sensor","discrete",0),Senal("motor","coil",0),Senal("luz","coil",1)])
            try:
                self._esperar(app,w,lambda:w.modbus.estado=="conectado")
                socket=w.modbus.cliente._socket
                self.assertIsNone(w.edicion.quitar_variable("luz"))
                self._esperar(app,w,lambda:w.modbus._mapa_pendiente is None and w.modbus.fase!="mapa")
                self.assertNotIn("luz",{s.variable for s in w.modbus.adaptador.config.senales})
                self.assertIn((1,False),escrituras)
                with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:w.a_ejecutar.setChecked(True)
                aviso.assert_not_called();self.assertEqual(w.modo,"simular")
                self._esperar(app,w,lambda:w.modbus.escritos.get("motor") is True)
                self.assertIs(w.modbus.cliente._socket,socket)
            finally:self._cerrar(app,w)

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
                self.assertTrue(any("no alcanza una situación estable" in w.lista_diag.item(i).text() for i in range(w.lista_diag.count())))
                w._desconectar_modbus()
                esperar(lambda: not w.modbus.activo)
            finally:
                w.edicion.ed.dirty = False
                if w.edicion is not None:w.edicion.ed.dirty=False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO30_play_inmediato_tras_reiniciar_en_pausa_no_vuelve_a_pausa(self):
        """REQ-SIM-02, REQ-SIM-03: Pausa, Reiniciar en Pausa (que solo vuelve a pedir el cero) y Play inmediato, antes de que
        termine el cero, deja la ejecución en Play: la intención más reciente manda; arranca una sesión nueva desde la
        situación inicial y el TCP es el mismo."""
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
                w.reiniciar()  # en Pausa: solo vuelve a pedir el cero
                self.assertFalse(w.modbus.reiniciando)
                w.a_ejecutar.setChecked(True)  # inmediato: sin dar tiempo a que termine el cero
                self.assertTrue(w.modbus.reiniciando, "Play vincula una sesión nueva: primero espera, y lee sus entradas")
                self.assertTrue(w.a_ejecutar.isChecked())
                esperar(lambda: not w.modbus.reiniciando and w.modbus.en_marcha)
                for _ in range(15):  # varios tics más: Play no se desmarca solo
                    app.processEvents()
                    time.sleep(.01)
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (True, "simular"))
                self.assertIsNotNone(w.modbus.adaptador.sesion)
                self.assertIs(w.modbus.adaptador.sesion, w.v.s)
                self.assertIsNot(w.v.s, anterior, "Play no se pierde: sesión nueva")
                self.assertIs(w.modbus.cliente._socket, socket)
                self.assertIs(w.modbus.escritos.get("motor"), True)
            finally:
                w.edicion.ed.dirty = False
                if w.edicion is not None:w.edicion.ed.dirty=False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO31_abrir_otro_proyecto_pone_a_cero_aunque_la_escritura_siguiera_en_vuelo(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): Play y Pausa con una escritura de salidas en vuelo descartan su respuesta
        (modbus.escritos sigue como lo dejó Conectar: el cero) pero la planta ya ha recibido el valor; al abrir otro proyecto se
        ponen a cero las salidas del mapa anterior igualmente."""
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
                self.assertEqual(w.modbus.escritos, {"motor": False}, "lo que dejó Conectar: la respuesta en vuelo no lo cambia")
                with mock.patch("escritorio.ventana.QMessageBox.question") as pregunta:
                    pregunta.return_value = QMessageBox.StandardButton.Discard
                    w.cargar_ejemplo("temporizada")
                puerta.set()  # la planta responde; la petición de cero va detrás
                esperar(lambda: w.modbus.escritos == {"motor": False} and escrituras[-1] == (0, 0))
                self.assertTrue(w.modbus.activo)
            finally:
                puerta.set()
                w.edicion.ed.dirty = False
                if w.edicion is not None:w.edicion.ed.dirty=False
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

    @staticmethod
    def _doc_vista():
        return (M().var("a").var("b").var("v", "input", "int").var("d", "input", "decimal", 2)
                .var("t", "input", "duration").var("q", "output").var("w", "output", "int").step("0", True).doc)

    def _panel_vista(self, app, ancho=1280, alto=720):
        """Un panel mostrado con a, v, q y w asignados y los canales del simulador de procesos (8 + 8 + 2 + 2)."""
        doc = self._doc_vista()
        c = Configuracion(host="192.168.1.133", puerto=502, unidad=1, modelo=doc["id"],
                          senales=[Senal("a", "discrete", 0), Senal("v", "input-register", 1, "INT16"),
                                   Senal("q", "coil", 0), Senal("w", "holding", 1, "INT16")],
                          canales={"discrete": {"offset": 0, "cantidad": 8}, "coil": {"offset": 0, "cantidad": 8},
                                   "input-register": {"offset": 0, "cantidad": 2}, "holding": {"offset": 0, "cantidad": 2}})
        p = PanelES()
        p.cargar(doc, c)
        p.resize(ancho, alto)
        p.show()
        app.processEvents()
        return p

    def test_SFIO33_marco_con_canales_y_nombres_fuera(self):
        """REQ-SIM-03: la vista autómata tiene la cabecera «(IP:puerto) Esclavo ID:n», Entrada e Entrada numérica a la izquierda,
        Salida y Salida numérica a la derecha, el nombre de la variable fuera del marco y pegado a él; 8 + 8 + 2 + 2 canales caben
        sin desplazarse en 1280×720 y en 1000×600, y con más canales aparece el desplazamiento vertical."""
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QScrollArea
        from escritorio.entradas_salidas import ALTO_FILA
        app = QApplication.instance() or QApplication([])
        for ancho, alto in ((1280, 720), (1000, 600)):
            p = self._panel_vista(app, ancho, alto)
            try:
                self.assertEqual(p.destino.text(), "(192.168.1.133:502)\nEsclavo ID:1")
                izq = [p.terminales[k].canal.text() for k in sorted(p.terminales, key=lambda k: (k[0] != "discrete", k[1]))
                       if k[0] in ("discrete", "input-register")]
                der = [p.terminales[k].canal.text() for k in sorted(p.terminales, key=lambda k: (k[0] != "coil", k[1]))
                       if k[0] in ("coil", "holding")]
                self.assertEqual(izq, [f"Entrada {n}" for n in range(8)] + ["Entrada numérica 0", "Entrada numérica 1"])
                self.assertEqual(der, [f"Salida {n}" for n in range(8)] + ["Salida numérica 0", "Salida numérica 1"])
                self.assertEqual(len(p.terminales), 20)
                self.assertTrue(all(t.height() == ALTO_FILA for t in p.terminales.values()), "filas compactas")
                x0 = p.modulo.mapTo(p, QPoint()).x()
                marco_izq, marco_der = x0, x0 + p.modulo.width()
                for k, lado in ((("discrete", 0), "izq"), (("input-register", 1), "izq"), (("coil", 0), "der"), (("holding", 1), "der")):
                    t = p.terminales[k]
                    caja_izq = t.nombre.mapTo(p, QPoint()).x()
                    caja_der = caja_izq + t.nombre.width()
                    self.assertTrue(t.nombre.text(), k)
                    self.assertFalse(t.barrita_nombre.isVisibleTo(t), "sin barrita junto al nombre")
                    if lado == "izq":
                        self.assertLessEqual(caja_der, marco_izq, "el nombre queda fuera del PLC")
                        self.assertGreater(caja_der, marco_izq - 12, "pegado al marco")
                    else:
                        self.assertGreaterEqual(caja_izq, marco_der, "el nombre queda fuera del PLC")
                        self.assertLess(caja_izq, marco_der + 12, "pegado al marco")
                self.assertEqual(p.terminales[("discrete", 1)].nombre.text(), "", "sin asignar no hay texto fuera")
                scroll = p.findChild(QScrollArea, "scrollES")
                self.assertFalse(scroll.verticalScrollBar().isVisible(), f"{ancho}x{alto}: sin desplazamiento")
                self.assertLessEqual(p.lienzo.height(), scroll.viewport().height())
                fondo = max(t.mapTo(p, QPoint(0, t.height())).y() for t in p.terminales.values())
                self.assertGreaterEqual(p.modulo.mapTo(p, QPoint(0, p.modulo.height())).y(), fondo, "el marco abarca todos los canales")
                # más canales: el centro se desplaza en vertical
                p.cantidades["discrete"].setValue(60)
                self.assertTrue(p._aplicar())
                for _ in range(3):  # el diseño se rehace en rondas: primero las filas, luego el área desplazable
                    app.processEvents()
                self.assertEqual(len(p.terminales), 72)
                self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
            finally:
                p.close()
                p.deleteLater()
                app.processEvents()

    def test_SFIO34_color_de_tipo_y_viveza_del_indicador(self):
        """REQ-SIM-03: la barrita de cada canal es tenue si no está asignado, del color del tipo (Bool verde, Decimal azul,
        Entera naranja, Cualquiera blanco) si lo está y más viva si la señal está activa; las analógicas muestran su valor."""
        from PySide6.QtCore import Qt
        from escritorio.entradas_salidas import (COLOR_CUALQUIERA, COLOR_TIPO, NIVEL_ACTIVO, NIVEL_ASIGNADO, NIVEL_TENUE,
                                                 ROL_ACTIVO, ROL_ASIGNADA, ROL_COLOR, mezclar)
        app = QApplication.instance() or QApplication([])
        doc = self._doc_vista()
        c = Configuracion(modelo=doc["id"], senales=[Senal("a", "discrete", 0), Senal("v", "input-register", 0, "INT16"),
                                                    Senal("d", "input-register", 1, "INT16"), Senal("q", "coil", 0)],
                          canales={"discrete": {"offset": 0, "cantidad": 3}, "coil": {"offset": 0, "cantidad": 2},
                                   "input-register": {"offset": 0, "cantidad": 2}, "holding": {"offset": 0, "cantidad": 0}})
        p = PanelES()
        try:
            p.cargar(doc, c)
            p.show()
            app.processEvents()
            led = lambda vid: p.indicadores[vid][0]  # noqa: E731
            self.assertEqual((led("a").colores, led("a").nivel), ((COLOR_TIPO["bool"],), NIVEL_ASIGNADO))
            self.assertEqual(led("v").colores, (COLOR_TIPO["int"],))
            self.assertEqual(led("d").colores, (COLOR_TIPO["decimal"],))
            tenue = p.terminales[("discrete", 2)].led
            self.assertEqual((tenue.colores, tenue.nivel), ((COLOR_TIPO["bool"],), NIVEL_TENUE), "sin asignar: tenue")
            self.assertLess(NIVEL_TENUE, NIVEL_ASIGNADO)
            self.assertLess(NIVEL_ASIGNADO, NIVEL_ACTIVO)
            p.mostrar_valores({"a": True, "v": 0, "d": "1.5", "q": False})
            self.assertEqual([led(v).nivel for v in ("a", "v", "d", "q")], [NIVEL_ACTIVO, NIVEL_ASIGNADO, NIVEL_ACTIVO, NIVEL_ASIGNADO])
            self.assertEqual([p.indicadores[v][1].text() for v in ("a", "v", "d")], ["1", "0", "1.5"])
            self.assertTrue(p.indicadores["v"][1].isVisibleTo(p), "las analógicas enseñan su valor")
            self.assertFalse(p.indicadores["a"][1].isVisibleTo(p), "las digitales, solo la barrita")
            pixel = led("a").grab().toImage().pixelColor(1, 1)
            self.assertEqual(pixel.getRgb()[:3], mezclar(COLOR_TIPO["bool"], NIVEL_ACTIVO).getRgb()[:3])
            # las listas laterales: sensores a la izquierda, actuadores a la derecha, con su color de tipo
            def fila(lista, nombre):
                return next(lista.item(i) for i in range(lista.count()) if lista.item(i).text() == nombre)
            self.assertEqual([p.lista_entradas.item(i).text() for i in range(p.lista_entradas.count())], ["a", "b", "v", "d", "t"])
            self.assertEqual([p.lista_salidas.item(i).text() for i in range(p.lista_salidas.count())], ["q", "w"])
            self.assertEqual([fila(p.lista_entradas, n).data(ROL_COLOR) for n in ("a", "v", "d", "t")],
                             [COLOR_TIPO["bool"], COLOR_TIPO["int"], COLOR_TIPO["decimal"], COLOR_CUALQUIERA])
            self.assertEqual([fila(p.lista_entradas, n).data(ROL_ASIGNADA) for n in ("a", "b")], [True, False])
            self.assertTrue(fila(p.lista_entradas, "a").data(ROL_ACTIVO))
            self.assertFalse(fila(p.lista_entradas, "v").data(ROL_ACTIVO))
            self.assertIn("asignada a Entrada 0", fila(p.lista_entradas, "a").toolTip())
            self.assertIn("sin asignar", fila(p.lista_entradas, "b").toolTip())
            self.assertFalse(fila(p.lista_entradas, "t").flags() & Qt.ItemFlag.ItemIsDragEnabled, "una duración no se arrastra")
            self.assertTrue(fila(p.lista_entradas, "b").flags() & Qt.ItemFlag.ItemIsDragEnabled)
        finally:
            p.close()
            p.deleteLater()
            app.processEvents()

    def test_SFIO35_arrastre_resalta_solo_lateral_y_la_x_aparece_al_pasar_el_raton(self):
        """REQ-SIM-03: al arrastrar una variable sobre un canal se resalta el lateral exterior al PLC (nombre incluido); soltar asigna;
        no se resalta si no cabe; conectado se conserva el arrastre y «×» solo aparece al pasar el ratón."""
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
        from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QEnterEvent
        app = QApplication.instance() or QApplication([])
        p = self._panel_vista(app)
        try:
            def entrar(terminal, lista, indice, punto=QPoint(5,5)):
                mime = lista.mimeData([lista.item(indice)])
                app.sendEvent(terminal, QDragEnterEvent(punto, Qt.DropAction.CopyAction, mime,
                                                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
                return mime
            vacio = p.terminales[("discrete", 3)]
            mime = entrar(vacio, p.lista_entradas, 1)  # b
            self.assertTrue(vacio.resaltado())
            marco_x = p.modulo.mapTo(p, QPoint()).x()
            self.assertLess(vacio.mapTo(p, QPoint()).x(), marco_x, "la fila entera abarca también el lado de fuera del marco")
            self.assertGreater(vacio.mapTo(p, QPoint(vacio.width(), 0)).x(), marco_x)
            app.sendEvent(vacio, QDragLeaveEvent())
            self.assertFalse(vacio.resaltado())
            entrar(vacio, p.lista_entradas, 1)
            drop = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            app.sendEvent(vacio, drop)
            self.assertTrue(drop.isAccepted())
            self.assertEqual({(s.variable, s.direccion) for s in p.obtener().senales if s.area == "discrete"}, {("a", 0), ("b", 3)})
            app.processEvents()
            self.assertFalse(any(t.resaltado() for t in p.terminales.values()))
            # una salida no cabe en un canal de entrada: no se resalta
            entrar(p.terminales[("discrete", 5)], p.lista_salidas, 0)
            self.assertFalse(p.terminales[("discrete", 5)].resaltado())
            # «×»: oculta hasta pasar el ratón; con conexión no aparece
            t = p.terminales[("discrete", 0)]
            self.assertFalse(t.b_quitar.isVisibleTo(t))
            app.sendEvent(t, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
            self.assertTrue(t.b_quitar.isVisibleTo(t))
            app.sendEvent(t, QEvent(QEvent.Type.Leave))
            self.assertFalse(t.b_quitar.isVisibleTo(t))
            p.ocupado(True)
            self.assertTrue(t.b_quitar.isEnabled())
            app.sendEvent(t, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
            self.assertTrue(t.b_quitar.isVisibleTo(t))
            entrar(p.terminales[("coil", 4)], p.lista_salidas, 0, p.terminales[("coil",4)].zona_asignacion().center())
            self.assertTrue(p.terminales[("coil", 4)].resaltado(), "con conexión también se asigna")
            app.sendEvent(t, QEvent(QEvent.Type.Leave))
            p.ocupado(False)
            self.assertTrue(t.b_quitar.isEnabled())
        finally:
            p.close()
            p.deleteLater()
            app.processEvents()

    # -- E/S externas al día con el modelo y última IP recordada (C1) ----------------------------------------------
    @staticmethod
    def _ventana_nueva(tmp, ajustes=None):
        from escritorio.ventana import Ventana
        return Ventana(ajustes or ajustes_de_prueba(tmp))

    def _ventana_modelo(self, tmp, doc, ajustes=None):
        """Una ventana con el modelo dado abierto como si viniera de un fichero, sin conexión."""
        w = self._ventana_nueva(tmp, ajustes)
        w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": doc,
                    "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
        w._cargar()
        return w

    @staticmethod
    def _cerrar(app, w):
        w.edicion.ed.dirty = False  # el cierre no pregunta
        if w.edicion is not None:w.edicion.ed.dirty=False
        w.close()
        w.deleteLater()
        app.processEvents()

    @staticmethod
    def _nombres(lista):
        return [lista.item(i).text() for i in range(lista.count())]

    @staticmethod
    def _es(w, ver):
        """Muestra (o deja de mostrar) la vista de E/S con el botón de la barra, como el usuario."""
        if (w.paginas_es.currentIndex() == 1) != ver:
            w.a_es.trigger()

    @staticmethod
    def _vid(w, nombre):
        return next(v["id"] for v in w.edicion.ed.model["variables"] if v["name"] == nombre)

    @staticmethod
    def _mapa(w):
        """El mapa del panel como {nombre: (área, dirección)}."""
        nombres = {v["id"]: v["name"] for v in w.panel_es.doc["variables"]}
        return {nombres[s.variable]: (s.area, s.direccion) for s in w.panel_es.obtener().senales}

    def test_SFIO37_variables_nuevas_del_editor_aparecen_en_es_y_se_pueden_asignar(self):
        """REQ-SIM-03, REQ-EDT-07: cada vez que se muestra E/S externas, sus listas y canales reflejan las variables actuales
        del editor (una entrada booleana, una entrada decimal y una salida decimal añadidas después de abrir el panel) y se
        asignan a discrete, input-register y holding; renombrar una variable asignada se refleja y lo asignado se conserva."""
        app = QApplication.instance() or QApplication([])
        decimal = {"kind": "decimal", "scale": 2}
        with tempfile.TemporaryDirectory() as tmp:
            w = self._ventana_nueva(tmp)
            p = w.panel_es
            try:
                w.nuevo()
                self.assertIsNone(w.edicion.nueva_variable("sensor1"))
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_entradas), ["sensor1"])
                self.assertTrue(p.asignar(self._vid(w, "sensor1"), "discrete", 1))
                self._es(w, False)
                # lo que se añade después de la primera visita
                self.assertIsNone(w.edicion.nueva_variable("sensor2"))
                self.assertIsNone(w.edicion.nueva_variable("nivel", "input", decimal))
                self.assertIsNone(w.edicion.nueva_variable("valvula", "output", decimal))
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_entradas), ["sensor1", "sensor2", "nivel"])
                self.assertEqual(self._nombres(p.lista_salidas), ["valvula"])
                self.assertIn(("input-register", 0), p.terminales)
                self.assertIn(("holding", 0), p.terminales)
                self.assertEqual(self._mapa(w), {"sensor1": ("discrete", 1), "sensor2": ("discrete", 0), "nivel": ("input-register", 0), "valvula": ("holding", 0)}, "se conserva la asignación previa y se asignan automáticamente las nuevas")
                self.assertTrue(p.asignar(self._vid(w, "sensor2"), "discrete", 0))
                self.assertTrue(p.asignar(self._vid(w, "nivel"), "input-register", 0))
                self.assertTrue(p.asignar(self._vid(w, "valvula"), "holding", 0))
                self.assertEqual(self._mapa(w), {"sensor1": ("discrete", 1), "sensor2": ("discrete", 0),
                                                 "nivel": ("input-register", 0), "valvula": ("holding", 0)})
                # renombrar una asignada: el nuevo nombre sale en la lista y en el canal, y la asignación sigue
                self._es(w, False)
                self.assertIsNone(w.edicion.cambiar_variable(self._vid(w, "sensor1"), nombre="marcha"))
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_entradas), ["marcha", "sensor2", "nivel"])
                self.assertEqual(p.terminales[("discrete", 1)].nombre.text(), "marcha")
                self.assertEqual(self._mapa(w)["marcha"], ("discrete", 1))
                self.assertNotIn("Asignaciones quitadas", p.estado.text())
                # borrar una asignada: sale del mapa, con aviso visible, y las demás siguen
                self._es(w, False)
                self.assertIsNone(w.edicion.quitar_variable(self._vid(w, "valvula")))
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_salidas), [])
                self.assertEqual(self._mapa(w), {"marcha": ("discrete", 1), "sensor2": ("discrete", 0),
                                                 "nivel": ("input-register", 0)})
                self.assertIn("Asignaciones quitadas", p.estado.text())
                self.assertIn("valvula", p.estado.text())
                self.assertEqual(p.host.text(), "192.168.1.133", "la configuración no se pierde al poner el panel al día")
                self.assertTrue(p._aplicar(), "el mapa que queda es válido")
                self.assertNotIn("Asignaciones quitadas", p.estado.text(), "el aviso dura hasta la siguiente acción sobre el mapa")
            finally:
                self._cerrar(app, w)

    def test_SFIO38_cambiar_tipo_o_papel_de_una_asignada_la_quita_con_aviso_sin_romper_el_panel(self):
        """REQ-SIM-03, REQ-EDT-07: si una variable asignada cambia de tipo o de papel y ya no casa con su área, se quita del
        mapa con un aviso y el panel queda consistente (antes: error al cargar y listas obsoletas para siempre); con otro
        tipo compatible, la asignación se conserva. Una booleana que pasa a numérica (Entera o Decimal) no se avisa: se
        recoloca sola en el primer registro libre."""
        app = QApplication.instance() or QApplication([])
        decimal = {"kind": "decimal", "scale": 2}
        with tempfile.TemporaryDirectory() as tmp:
            w = self._ventana_nueva(tmp)
            p = w.panel_es
            try:
                w.nuevo()
                for nombre, papel, tipo in (("a", "input", None), ("b", "input", decimal), ("c", "input", decimal)):
                    self.assertIsNone(w.edicion.nueva_variable(nombre, papel, tipo))
                self._es(w, True)
                self.assertTrue(p.asignar(self._vid(w, "a"), "discrete", 0))
                self.assertTrue(p.asignar(self._vid(w, "b"), "input-register", 0))
                self.assertTrue(p.asignar(self._vid(w, "c"), "input-register", 1))
                self._es(w, False)
                self.assertIsNone(w.edicion.cambiar_variable(self._vid(w, "a"), type=decimal))  # bool → decimal
                self.assertIsNone(w.edicion.cambiar_variable(self._vid(w, "b"), role="output"))  # entrada → salida
                self.assertIsNone(w.edicion.cambiar_variable(self._vid(w, "c"), type={"kind": "int"}))  # decimal → entera: casa
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_entradas), ["a", "c"])
                self.assertEqual(self._nombres(p.lista_salidas), ["b"])
                self.assertEqual(self._mapa(w), {"a": ("input-register", 2), "c": ("input-register", 1)})
                self.assertIn("«b»", p.estado.text())
                self.assertNotIn("«a»", p.estado.text(), "recolocada sola, sin aviso de quitada")
                self.assertIn("Asignaciones quitadas", p.estado.toolTip())
                self.assertEqual(p.config.senales, p.obtener().senales, "config y tabla coinciden")
                # las dos pueden asignarse ahora a lo que les corresponde
                self.assertTrue(p.asignar(self._vid(w, "a"), "input-register", 0))
                self.assertTrue(p.asignar(self._vid(w, "b"), "holding", 0))
                self.assertEqual(self._mapa(w), {"a": ("input-register", 0), "b": ("holding", 0), "c": ("input-register", 1)})
            finally:
                self._cerrar(app, w)

    def test_SFIO39_con_el_panel_a_la_vista_las_variables_nuevas_llegan_sin_salir_y_se_conserva_lo_escrito(self):
        """REQ-SIM-03: con la vista de E/S abierta (la tabla de variables sigue accesible) una variable nueva aparece al
        momento; el servidor y los canales escritos en Configuración, aunque no se hayan aplicado, no se pierden."""
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w = self._ventana_nueva(tmp)
            p = w.panel_es
            try:
                w.nuevo()
                self.assertIsNone(w.edicion.nueva_variable("uno"))
                self._es(w, True)
                p.host.setText("10.1.2.3")
                p.unidad.setValue(5)
                p.cantidades["discrete"].setValue(6)  # sin «Aplicar mapa» ni cerrar el diálogo
                self.assertIsNone(w.edicion.nueva_variable("dos"))
                self.assertEqual(self._nombres(p.lista_entradas), ["uno", "dos"])
                self.assertEqual((p.host.text(), p.unidad.value(), p.cantidades["discrete"].value()), ("10.1.2.3", 5, 6))
                self.assertEqual(len([1 for a, _ in p.terminales if a == "discrete"]), 6)
                self.assertTrue(p.asignar(self._vid(w, "dos"), "discrete", 5))
                self.assertIsNone(w.edicion.nueva_variable("tres"))
                self.assertEqual(self._mapa(w), {"uno": ("discrete", 0), "dos": ("discrete", 5), "tres": ("discrete", 1)})
                self.assertEqual(p.obtener().host, "10.1.2.3")
                # deshacer también lo sigue: la variable desaparece de las listas
                w.edicion.deshacer()
                self.assertEqual(self._nombres(p.lista_entradas), ["uno", "dos"])
            finally:
                self._cerrar(app, w)

    def test_SFIO40_conexion_activa_actualiza_variables_y_mapa_sin_reconectar(self):
        """REQ-SIM-02, REQ-SIM-03: altas y asignaciones se publican entre ciclos conservando TCP y canales existentes."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta([])) as sc:
            m=M().var("sensor").var("motor","output").step("E0",True);m.cont("E0","motor","sensor")
            w=self._ventana_conectada(tmp,sc,m.doc,[Senal("sensor","discrete",0),Senal("motor","coil",0)])
            p=w.panel_es
            try:
                self._esperar(app,w,lambda:w.modbus.estado=="conectado")
                cliente=w.modbus.cliente
                self._es(w,True)
                self.assertIsNone(w.edicion.nueva_variable("extra"))
                self.assertIsNone(w.edicion.nueva_variable("nivel","input",{"kind":"decimal","scale":2}))
                self.assertEqual(self._nombres(p.lista_entradas),["sensor","extra","nivel"])
                self._esperar(app,w,lambda:w.modbus._mapa_pendiente is None and w.modbus.fase!="mapa")
                self.assertEqual(self._mapa(w),{"sensor":("discrete",0),"motor":("coil",0),"extra":("discrete",1),"nivel":("input-register",0)})
                self.assertIs(w.modbus.cliente,cliente);self.assertTrue(w.modbus.activo)
                self.assertFalse(p.pendiente);self.assertFalse(p.bloqueado)
                self.assertEqual(p.puerto.value(),sc.puerto)
                self.assertTrue(p.asignar(self._vid(w,"nivel"),"input-register",2))
            finally:self._cerrar(app,w)

    def test_SFIO41_canales_fijados_a_mano_se_conservan_y_se_avisa_si_un_area_se_queda_sin_canales(self):
        """REQ-SIM-03, REQ-DAT-02: con las cantidades de canal escritas a mano no se inventan canales; si una variable
        nueva no tiene dónde asignarse porque su área está en 0, el estado lo dice y subir la cantidad lo arregla."""
        app = QApplication.instance() or QApplication([])
        decimal = {"kind": "decimal", "scale": 2}
        with tempfile.TemporaryDirectory() as tmp:
            w = self._ventana_nueva(tmp)
            p = w.panel_es
            try:
                w.nuevo()
                self.assertIsNone(w.edicion.nueva_variable("s1"))
                self._es(w, True)
                p.cantidades["input-register"].setValue(0)
                p.cantidades["holding"].setValue(0)
                p.cantidades["discrete"].setValue(6)
                self.assertTrue(p._aplicar())
                self.assertEqual(p.config.canales["input-register"]["cantidad"], 0)
                self._es(w, False)
                self.assertIsNone(w.edicion.nueva_variable("nivel", "input", decimal))
                self.assertIsNone(w.edicion.nueva_variable("valvula", "output", decimal))
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_entradas), ["s1", "nivel"])
                self.assertEqual(len([1 for a, _ in p.terminales if a == "discrete"]), 6, "los canales fijados se respetan")
                self.assertFalse([1 for a, _ in p.terminales if a in ("input-register", "holding")])
                self.assertIn("Sin canales en Entrada numérica, Salida numérica", p.estado.text())
                p.cantidades["input-register"].setValue(2)
                p.cantidades["holding"].setValue(1)
                self.assertTrue(p._aplicar())
                self.assertNotIn("Sin canales", p.estado.text())
                self.assertTrue(p.asignar(self._vid(w, "nivel"), "input-register", 1))
                self.assertTrue(p.asignar(self._vid(w, "valvula"), "holding", 0))
            finally:
                self._cerrar(app, w)

    def test_SFIO42_camino_de_simulacion_el_panel_sigue_a_las_variables_del_modelo_en_ejecucion(self):
        """REQ-SIM-03, REQ-EDT-07: en Play, E/S externas enseña las variables del modelo que se ejecuta; al volver a Pausa y
        editar, las variables nuevas aparecen al volver a mostrarlo, y las asignaciones se conservan."""
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            w = self._ventana_modelo(tmp, m.doc)
            p = w.panel_es
            try:
                self._es(w, True)
                self.assertTrue(p.asignar("sensor", "discrete", 0))
                self._es(w, False)
                w.a_ejecutar.setChecked(True)
                self.assertEqual(w.modo, "simular")
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_entradas), ["sensor"])
                self.assertEqual(self._nombres(p.lista_salidas), ["motor"])
                self.assertEqual(self._mapa(w), {"sensor": ("discrete", 0)})
                self._es(w, False)
                w.a_ejecutar.setChecked(False)
                self.assertEqual(w.modo, "editar")
                self.assertIsNone(w.edicion.nueva_variable("nivel", "input", {"kind": "decimal", "scale": 2}))
                self.assertIsNone(w.edicion.nueva_variable("valvula", "output", {"kind": "decimal", "scale": 2}))
                self._es(w, True)
                self.assertEqual(self._nombres(p.lista_entradas), ["sensor", "nivel"])
                self.assertEqual(self._nombres(p.lista_salidas), ["motor", "valvula"])
                self.assertTrue(p.asignar(self._vid(w, "nivel"), "input-register", 0))
                self.assertTrue(p.asignar(self._vid(w, "valvula"), "holding", 0))
                self.assertEqual(self._mapa(w), {"sensor": ("discrete", 0), "nivel": ("input-register", 0),
                                                 "valvula": ("holding", 0)})
                # un Play nuevo con el panel a la vista: el panel ya tiene lo del modelo que se ejecuta
                w.a_ejecutar.setChecked(True)
                self.assertEqual(self._nombres(p.lista_entradas), ["sensor", "nivel"])
                self.assertEqual(len(self._mapa(w)), 3)
            finally:
                w.a_ejecutar.setChecked(False)
                self._cerrar(app, w)

    def test_SFIO43_la_primera_vez_el_servidor_propuesto_es_el_del_simulador(self):
        """REQ-SIM-03: sin nada recordado ni mapa guardado, el panel propone 192.168.1.133, puerto 502 y esclavo 1; no se
        comparte el mismo valor inicial con la configuración de conexión."""
        app = QApplication.instance() or QApplication([])
        self.assertEqual(Configuracion().host, "192.168.1.133", "valor inicial unificado con el simulador de procesos")
        p = PanelES()
        try:
            p.cargar(M().var("a").step("0", True).doc)
            self.assertEqual((p.host.text(), p.puerto.value(), p.unidad.value()), ("192.168.1.133", 502, 1))
        finally:
            p.close()
            p.deleteLater()
            app.processEvents()
        with tempfile.TemporaryDirectory() as tmp:
            w = self._ventana_nueva(tmp)
            try:
                self.assertEqual(w.ajustes.value("modbus/host", "nada"), "nada", "no se guarda nada sin una conexión que funcione")
                self.assertEqual(w.panel_es.obtener().host, "192.168.1.133")  # el ejemplo con el que arranca
                w.nuevo()
                self._es(w, True)
                self.assertEqual((w.panel_es.host.text(), w.panel_es.puerto.value(), w.panel_es.unidad.value()),
                                 ("192.168.1.133", 502, 1))
            finally:
                self._cerrar(app, w)

    def test_SFIO44_recuerda_el_ultimo_servidor_que_conecto_y_lo_propone_en_proyectos_nuevos_y_al_reiniciar(self):
        """REQ-SIM-03: tras conectar con éxito, host, puerto y esclavo se recuerdan en los ajustes de la aplicación y se
        proponen en el proyecto nuevo (y, tras cerrar y abrir la aplicación, en la ventana nueva)."""
        from PySide6.QtCore import QSettings
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta([])) as sc:
            m = M().var("sensor").step("E0", True)
            w = self._ventana_modelo(tmp, m.doc)
            otra = None
            try:
                w.panel_es.cargar(m.doc, Configuracion(host="127.0.0.1", puerto=sc.puerto, unidad=7, periodo_ms=20,
                                                       senales=[Senal("sensor", "discrete", 0)]))
                self.assertEqual(w.ajustes.value("modbus/host", "nada"), "nada", "escribir en el panel no recuerda nada")
                w._conectar_modbus()
                self._esperar(app, w, lambda: w.modbus.estado == "conectado")
                self.assertEqual((w.ajustes.value("modbus/host"), w.ajustes.value("modbus/puerto", type=int),
                                  w.ajustes.value("modbus/unidad", type=int)), ("127.0.0.1", sc.puerto, 7))
                self.assertEqual(Path(w.ajustes.fileName()).parent, Path(tmp), "los ajustes de la prueba, no los del usuario")
                w._desconectar_modbus()
                self._esperar(app, w, lambda: not w.modbus.activo)
                w.nuevo()  # otro proyecto, sin mapa propio
                self._es(w, True)
                self.assertEqual((w.panel_es.host.text(), w.panel_es.puerto.value(), w.panel_es.unidad.value()),
                                 ("127.0.0.1", sc.puerto, 7))
                self.assertEqual(w.panel_es.config.senales, [])
                # la aplicación vuelve a abrirse: arranca con la última
                otra = self._ventana_nueva(tmp, QSettings(str(Path(tmp) / "ajustes.ini"), QSettings.Format.IniFormat))
                self.assertEqual((otra.panel_es.host.text(), otra.panel_es.puerto.value(), otra.panel_es.unidad.value()),
                                 ("127.0.0.1", sc.puerto, 7))
            finally:
                if otra is not None:
                    self._cerrar(app, otra)
                self._cerrar(app, w)

    def test_SFIO45_la_prueba_de_conexion_con_exito_tambien_recuerda_y_un_fallo_no(self):
        """REQ-SIM-03: «Probar conexión» con éxito recuerda el servidor; una conexión que falla no lo cambia."""
        import socket
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        cerrado = socket.socket()
        cerrado.bind(("127.0.0.1", 0))
        puerto_cerrado = cerrado.getsockname()[1]
        cerrado.close()  # nadie escucha en ese puerto
        with tempfile.TemporaryDirectory() as tmp, servidor(self._servidor_planta([])) as sc:
            m = M().var("sensor").step("E0", True)
            w = self._ventana_modelo(tmp, m.doc)
            try:
                w.panel_es.cargar(m.doc, Configuracion(host="127.0.0.1", puerto=puerto_cerrado, periodo_ms=20, timeout_ms=200,
                                                       senales=[Senal("sensor", "discrete", 0)]))
                w._conectar_modbus()
                self._esperar(app, w, lambda: w.modbus.estado == "error")
                self.assertEqual(w.ajustes.value("modbus/host", "nada"), "nada", "un fallo no se recuerda")
                w.panel_es.cargar(m.doc, Configuracion(host="127.0.0.1", puerto=sc.puerto, unidad=3, periodo_ms=20,
                                                       senales=[Senal("sensor", "discrete", 0)]))
                w._conectar_modbus(prueba=True)
                self._esperar(app, w, lambda: w.modbus.mensaje.startswith("Conexión probada"))
                self.assertFalse(w.modbus.activo)
                self.assertEqual((w.ajustes.value("modbus/host"), w.ajustes.value("modbus/puerto", type=int),
                                  w.ajustes.value("modbus/unidad", type=int)), ("127.0.0.1", sc.puerto, 3))
                self.assertEqual(w.panel_es.conexion_defecto, ("127.0.0.1", sc.puerto, 3))
            finally:
                self._cerrar(app, w)

    def test_SFIO46_el_mapa_guardado_del_proyecto_manda_sobre_el_servidor_recordado(self):
        """REQ-SIM-03, REQ-DAT-02: un proyecto con su configuración Modbus guardada abre con la suya, aunque haya un servidor
        recordado; uno sin configuración guardada abre con el recordado."""
        from conexion.configuracion import ARCHIVO
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            ajustes = ajustes_de_prueba(tmp)
            ajustes.setValue("modbus/host", "172.16.0.9")
            ajustes.setValue("modbus/puerto", 1234)
            ajustes.setValue("modbus/unidad", 7)
            ajustes.sync()
            m = M().var("sensor").step("E0", True)
            w = self._ventana_modelo(tmp, m.doc, ajustes)
            try:
                self.assertEqual((w.panel_es.host.text(), w.panel_es.puerto.value(), w.panel_es.unidad.value()),
                                 ("172.16.0.9", 1234, 7), "un modelo sin mapa propio propone lo recordado")
                ruta = Path(tmp) / "con_mapa"
                w.edicion.guardar(ruta)
                Configuracion(host="10.20.30.40", puerto=1502, unidad=3, modelo=m.doc["id"],
                              senales=[Senal("sensor", "discrete", 2)]).guardar(ruta / ARCHIVO, m.doc)
                sin_mapa = Path(tmp) / "sin_mapa"
                w.edicion.guardar(sin_mapa)
                self.assertTrue(w.abrir_ruta(fixture_grafnet(ruta / "manifest.json")))
                self.assertEqual((w.panel_es.host.text(), w.panel_es.puerto.value(), w.panel_es.unidad.value()),
                                 ("10.20.30.40", 1502, 3))
                self._es(w, True)
                self.assertEqual((w.panel_es.host.text(), w.panel_es.puerto.value(), w.panel_es.unidad.value()),
                                 ("10.20.30.40", 1502, 3), "mostrar el panel no lo cambia")
                self.assertEqual(self._mapa(w), {"sensor": ("discrete", 2)})
                self._es(w, False)
                self.assertTrue(w.abrir_ruta(fixture_grafnet(sin_mapa / "manifest.json")))
                self.assertEqual((w.panel_es.host.text(), w.panel_es.puerto.value(), w.panel_es.unidad.value()),
                                 ("172.16.0.9", 1234, 7))
                self.assertEqual(w.panel_es.config.senales, [])
            finally:
                self._cerrar(app, w)

    # -- Pausa = todo a 0 hasta un nuevo Play (C1) -------------------------------------------------------------------
    @staticmethod
    def _planta_mixta(escrituras, sensor, vivo=None):
        """Servidor de planta: el sensor (entrada discreta 0) vale lo que diga `sensor[0]`; las escrituras de coils y de
        holding se anotan como ("coil" | "holding", dirección, valor). Con `vivo[0]` falso deja de responder (red caída)."""
        def responder(p):
            if vivo is not None and not vivo[0]:
                return None
            if p[0] == 15:
                escrituras.extend(("coil", int.from_bytes(p[1:3], "big") + i, (p[6 + i // 8] >> (i % 8)) & 1)
                                  for i in range(int.from_bytes(p[3:5], "big")))
            elif p[0] == 16:
                escrituras.append(("holding", int.from_bytes(p[1:3], "big"), int.from_bytes(p[6:8], "big")))
            return bytes([2, 1, sensor[0]]) if p[0] == 2 else p[:5]
        return responder

    @staticmethod
    def _modelo_pausa():
        """E0 (inicial) -sensor-> E1: motor mientras E0, luz mientras E1 y una consigna decimal memorizada (1,5) al activar E0."""
        m = M().var("sensor").var("motor", "output").var("luz", "output").var("vel", "output", "decimal", scale=2)
        m.step("E0", True).step("E1").trans("t1", ["E0"], ["E1"], "sensor")
        m.cont("E0", "motor").cont("E1", "luz").stored("E0", "vel", "activation", "1.5")
        return m

    @staticmethod
    def _modelo_inestable():
        """Con «sensor» a 1, E0 y E1 se alternan sin fin en tiempo cero (D-LIM-EVOL)."""
        m = M().var("sensor").var("motor", "output").step("E0", True).step("E1")
        m.trans("t1", ["E0"], ["E1"], "sensor").trans("t2", ["E1"], ["E0"], "sensor").cont("E1", "motor")
        return m

    _MAPA_PAUSA = (("sensor", "discrete", 0, "BOOL"), ("motor", "coil", 0, "BOOL"), ("luz", "coil", 1, "BOOL"),
                   ("vel", "holding", 0, "INT16"))

    def _mapa_pausa(self, doc, puerto):
        return Configuracion(host="127.0.0.1", puerto=puerto, periodo_ms=20, modelo=doc["id"],
                             senales=[Senal(v, a, d, f) for v, a, d, f in self._MAPA_PAUSA])

    def test_SFIO47_pausa_pone_a_cero_coils_y_holding_y_play_arranca_de_la_situacion_inicial(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): Pausa deja todo a 0 hasta un nuevo Play: todas las coils y holding asignadas se
        escriben a 0, el GRAFCET no tiene etapas activas ni temporizadores y las tablas no enseñan la sesión anterior; la
        conexión sigue y se siguen leyendo las entradas. Play arranca siempre una sesión nueva desde la situación inicial,
        lee las entradas de la planta y las aplica antes de escribir sus salidas (aunque la sesión anterior hubiera
        evolucionado); el orden de las peticiones en el cable lo fija SFIO60."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras, sensor = [], [0]
        with tempfile.TemporaryDirectory() as tmp, servidor(self._planta_mixta(escrituras, sensor)) as sc:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            cero = {"motor": False, "luz": False, "vel": 0}
            try:
                w.panel_es.cargar(m.doc, self._mapa_pausa(m.doc, sc.puerto))
                w._conectar_modbus()  # en Pausa: pide el cero de las salidas asignadas y observa las entradas
                esperar(lambda: w.modbus.estado == "conectado")
                self.assertEqual((w.modbus.escritos, escrituras), (cero, [("coil", 0, 0), ("coil", 1, 0), ("holding", 0, 0)]),
                                 "Conectar en Pausa pide el cero de todas las salidas asignadas, una vez")
                socket = w.modbus.cliente._socket
                # Play: situación inicial en la planta
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos == {"motor": True, "luz": False, "vel": 150})
                self.assertEqual(w.v.state()["situation"], ["E0"])
                # el sensor se activa: evoluciona a E1
                sensor[0] = 1
                esperar(lambda: w.modbus.escritos == {"motor": False, "luz": True, "vel": 150})
                self.assertEqual(w.v.state()["situation"], ["E1"])
                self.assertGreater(w.t_vars.rowCount(), 0)
                # Pausa: todo a 0
                w.a_ejecutar.setChecked(False)
                self.assertEqual((w.modo, w.modbus.estado), ("editar", "conectado"))
                esperar(lambda: w.modbus.escritos == cero)
                ultimas = {(t, d): v for t, d, v in escrituras}
                self.assertEqual((ultimas[("coil", 0)], ultimas[("coil", 1)], ultimas[("holding", 0)]), (0, 0, 0),
                                 "lo último que recibió la planta en cada coil y holding asignada es 0")
                self.assertEqual(w.v.state().get("situation", []), [], "sin etapas activas")
                self.assertEqual(w.v.state().get("temporal", {}), {}, "sin temporizadores")
                self.assertEqual((w.t_vars.rowCount(), w.t_temp.rowCount(), w.traza.count()), (0, 0, 0),
                                 "las tablas no enseñan la sesión anterior")
                n = len(escrituras)
                fin = time.monotonic() + .15
                esperar(lambda: time.monotonic() >= fin)
                self.assertEqual(len(escrituras), n, "tras el cero, Pausa no escribe más")
                self.assertIs(w.modbus.cliente._socket, socket, "la conexión no se cierra")
                self.assertTrue(w.modbus.activo and w.rt.isActive(), "la observación de entradas sigue")
                esperar(lambda: w.panel_es.indicadores["sensor"][1].text() == "1" and w.panel_es.indicadores["vel"][1].text() == "0")
                self.assertEqual([w.panel_es.indicadores[v][1].text() for v in ("motor", "luz")], ["0", "0"])
                # Play otra vez, con el sensor ya a 0: sesión nueva desde la situación inicial (no sigue en E1)
                sensor[0] = 0
                anterior = w.v.s
                w.a_ejecutar.setChecked(True)
                self.assertIsNot(w.v.s, anterior)
                esperar(lambda: w.modbus.escritos == {"motor": True, "luz": False, "vel": 150})
                self.assertEqual(w.v.state()["situation"], ["E0"])
                self.assertIs(w.modbus.cliente._socket, socket)
                # Pausa y Play con el sensor a 1: arranca en E0 y lee antes las entradas de la conexión: evoluciona a E1
                w.a_ejecutar.setChecked(False)
                esperar(lambda: w.modbus.escritos == cero)
                sensor[0] = 1
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos == {"motor": False, "luz": True, "vel": 150})
                self.assertEqual(w.v.state()["situation"], ["E1"])
                self.assertIs(w.v.s.z.values["sensor"], True)
                w.a_ejecutar.setChecked(False)
                esperar(lambda: w.modbus.escritos == cero)
            finally:
                self._cerrar(app, w)

    def test_SFIO48_pausa_sin_conexion_deja_el_grafcet_sin_estado_y_cada_play_empieza_de_cero(self):
        """REQ-SIM-03 (P-IMP-60): sin E/S externas, Pausa también deja el GRAFCET sin etapas activas, sin temporizadores y con
        las tablas vacías; Play arranca de la situación inicial aunque no se haya editado nada; Reiniciar en Pausa no
        crea estado."""
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            try:
                w.a_ejecutar.setChecked(True)
                w.botones["sensor"].click()
                self.assertEqual(w.v.state()["situation"], ["E1"])
                self.assertEqual({k: x["value"] for k, x in w.v.state()["outputs"].items()}, {"motor": False, "luz": True})
                w.a_ejecutar.setChecked(False)
                self.assertEqual((w.v.state().get("situation", []), w.v.state().get("outputs", {}), w.v.state().get("values", {})),
                                 ([], {}, {}), "sin etapas, sin salidas y sin valores")
                self.assertEqual((w.t_vars.rowCount(), w.t_temp.rowCount(), w.traza.count()), (0, 0, 0))
                w.reiniciar()
                self.assertEqual(w.v.state().get("situation", []), [])
                self.assertFalse(w.a_ejecutar.isChecked())
                w.a_ejecutar.setChecked(True)
                self.assertEqual(w.v.state()["situation"], ["E0"], "Play: sesión nueva desde la situación inicial")
                self.assertEqual(w.botones["sensor"].text(), "sensor = 0")
                w.a_ejecutar.setChecked(False)
                w.a_ejecutar.setChecked(True)
                self.assertEqual(w.v.state()["situation"], ["E0"])
                w.a_ejecutar.setChecked(False)
            finally:
                w.a_ejecutar.setChecked(False)
                self._cerrar(app, w)

    def test_SFIO49_conectar_o_probar_con_play_activo_pasa_a_pausa_y_un_diagnostico_acaba_con_todo_a_cero(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): «Probar conexión» y «Conectar» con Play activo pasan a Pausa (sin etapas activas);
        probar no escribe nada y conectar (en Pausa) solo el cero de las asignadas; el cuadro de inestabilidad sigue
        avisando una sola vez y acaba en Pausa con todo a 0, con la conexión viva."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras, sensor = [], [0]
        with tempfile.TemporaryDirectory() as tmp, servidor(self._planta_mixta(escrituras, sensor)) as sc:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                w.panel_es.cargar(m.doc, self._mapa_pausa(m.doc, sc.puerto))
                w.a_ejecutar.setChecked(True)
                self.assertEqual(w.modo, "simular")
                w._conectar_modbus(prueba=True)
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (False, "editar"))
                self.assertEqual(w.v.state().get("situation", []), [])
                esperar(lambda: w.modbus.mensaje.startswith("Conexión probada"))
                self.assertEqual(escrituras, [], "probar no escribe actuadores")
                w.a_ejecutar.setChecked(True)
                self.assertEqual(w.modo, "simular")
                w._conectar_modbus()
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo), (False, "editar"))
                self.assertEqual(w.v.state().get("situation", []), [])
                esperar(lambda: w.modbus.estado == "conectado")
                self.assertEqual(escrituras, [("coil", 0, 0), ("coil", 1, 0), ("holding", 0, 0)], "conectar en Pausa: solo el cero")
                # inestable: avisa una vez, acaba en Pausa con todo a 0 y la conexión se conserva
                w._desconectar_modbus()
                esperar(lambda: not w.modbus.activo)
                inestable = self._modelo_inestable()
                w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "inestable.json", "doc": inestable.doc,
                            "layout": {}, "titulo": "Inestable", "ayuda": "", "raiz": None}
                w._cargar()
                w.panel_es.cargar(inestable.doc, Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, modelo=inestable.doc["id"],
                                                               senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)]))
                w._conectar_modbus()
                esperar(lambda: w.modbus.estado == "conectado")
                sensor[0] = 1
                n = len(escrituras)
                with mock.patch.object(type(w), "_avisar_inestable", autospec=True) as aviso:
                    w.a_ejecutar.setChecked(True)
                    esperar(lambda: aviso.call_count == 1)
                    esperar(lambda: w.modbus.escritos == {"motor": False} and len(escrituras) > n and escrituras[-1] == ("coil", 0, 0))
                self.assertEqual((w.a_ejecutar.isChecked(), w.modo, aviso.call_count), (False, "editar", 1))
                self.assertEqual(w.v.state().get("situation", []), [], "sin etapas activas tras el diagnóstico")
                self.assertTrue(w.modbus.activo)
            finally:
                self._cerrar(app, w)

    def test_SFIO50_con_la_red_caida_en_play_acaba_en_pausa_sin_estado_y_no_se_garantiza_el_cero(self):
        """REQ-ROB-01, REQ-SIM-02: si la red cae en Play, el programa acaba en Pausa sin etapas activas y el estado de la conexión
        dice que las salidas no están garantizadas (no puede escribirse el cero); no se reconecta solo."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras, sensor, vivo = [], [0], [True]
        with tempfile.TemporaryDirectory() as tmp, servidor(self._planta_mixta(escrituras, sensor, vivo)) as sc:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                w.panel_es.cargar(m.doc, self._mapa_pausa(m.doc, sc.puerto))
                w._conectar_modbus()
                esperar(lambda: w.modbus.estado == "conectado")
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos == {"motor": True, "luz": False, "vel": 150})
                vivo[0] = False  # la planta deja de responder
                esperar(lambda: w.modbus.estado == "error")
                esperar(lambda: not w.a_ejecutar.isChecked())
                self.assertEqual(w.modo, "editar")
                self.assertEqual(w.v.state().get("situation", []), [])
                self.assertIn("Salidas no garantizadas", w.modbus.mensaje)
                self.assertFalse(w.modbus.activo)
                self.assertEqual((w.t_vars.rowCount(), w.t_temp.rowCount()), (0, 0))
            finally:
                self._cerrar(app, w)

    # -- Conectar y Desconectar con el cero de las salidas asignadas (C3) --------------------------------------------
    _CEROS = [("coil", 0, 0), ("coil", 1, 0), ("holding", 0, 0)]

    def test_SFIO53_desconectar_en_play_pone_a_cero_coils_y_holding_antes_de_cerrar_el_tcp(self):
        """REQ-SIM-02, REQ-SIM-03, REQ-ROB-01: «Desconectar» en Play escribe el cero de todas las coils y holding asignadas ANTES
        de cerrar el TCP (lo último que recibe la planta en cada una es 0), la conexión queda cerrada y el mensaje ya no dice
        que la planta puede conservar sus salidas."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras, sensor = [], [0]
        with tempfile.TemporaryDirectory() as tmp, servidor(self._planta_mixta(escrituras, sensor)) as sc:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            ultimas = lambda: {(t, d): v for t, d, v in escrituras}  # noqa: E731
            try:
                w.panel_es.cargar(m.doc, self._mapa_pausa(m.doc, sc.puerto))
                w._conectar_modbus()
                esperar(lambda: w.modbus.estado == "conectado")
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos == {"motor": True, "luz": False, "vel": 150})
                self.assertEqual((ultimas()[("coil", 0)], ultimas()[("holding", 0)]), (1, 150), "la planta tiene lo de Play")
                cliente = w.modbus.cliente
                w._desconectar_modbus()
                self.assertIn("salidas a cero", w.modbus.mensaje)
                self.assertNotIn("conservar", w.modbus.mensaje)
                esperar(lambda: not w.modbus.activo)
                self.assertIsNone(cliente._socket, "el TCP está cerrado")
                self.assertEqual(w.modbus.estado, "desconectado")
                self.assertEqual(ultimas(), {("coil", 0): 0, ("coil", 1): 0, ("holding", 0): 0})
                self.assertEqual(escrituras[-3:], self._CEROS, "lo último que llegó a la planta, antes del cierre, es el cero")
                self.assertEqual(w.modbus.mensaje, "Desconectado · salidas a cero")
                self.assertFalse(w.a_ejecutar.isChecked())
            finally:
                self._cerrar(app, w)

    def test_SFIO54_desconectar_con_la_red_caida_cierra_igual_y_avisa_de_salidas_no_garantizadas(self):
        """REQ-ROB-01, REQ-SIM-03: si la planta ha dejado de responder, «Desconectar» no puede escribir el cero: la conexión se
        cierra igual (no se queda esperando) y el estado dice que las salidas no están garantizadas."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras, sensor, vivo = [], [0], [True]
        with tempfile.TemporaryDirectory() as tmp, servidor(self._planta_mixta(escrituras, sensor, vivo)) as sc:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                w.panel_es.cargar(m.doc, self._mapa_pausa(m.doc, sc.puerto))
                w._conectar_modbus()
                esperar(lambda: w.modbus.estado == "conectado")
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos == {"motor": True, "luz": False, "vel": 150})
                cliente = w.modbus.cliente
                vivo[0] = False
                w._desconectar_modbus()
                esperar(lambda: not w.modbus.activo)
                self.assertIsNone(cliente._socket, "se cierra igual")
                self.assertIn("salidas no garantizadas", w.modbus.mensaje.lower())
                self.assertIn("salidas no garantizadas", w.panel_es.estado.toolTip().lower(), "y el panel lo dice")
                self.assertTrue(w.modbus.mensaje.startswith("Desconectado"), "dice que se ha desconectado…")
                self.assertNotIn("Pulsa Conectar", w.modbus.mensaje, "…y no invita a reconectar justo después")
                self.assertNotIn("Pulsa Conectar", w.panel_es.estado.toolTip())
                self.assertFalse(w.a_ejecutar.isChecked())
            finally:
                self._cerrar(app, w)

    def test_SFIO55_cerrar_la_ventana_con_la_conexion_viva_escribe_el_cero_antes_de_cerrar_el_tcp(self):
        """REQ-SIM-03, REQ-ROB-01: cerrar la ventana en Play escribe el cero de las coils y holding asignadas antes de cerrar el
        TCP (mejor esfuerzo: el cero llega a la planta antes que el cierre); con la red caída cierra igual, sin quedarse esperando."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras, sensor, vivo = [], [0], [True]
        with tempfile.TemporaryDirectory() as tmp, servidor(self._planta_mixta(escrituras, sensor, vivo)) as sc:
            m = self._modelo_pausa()
            for red_caida in (False, True):
                w = self._ventana_modelo(tmp, m.doc)
                esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
                try:
                    w.panel_es.cargar(m.doc, self._mapa_pausa(m.doc, sc.puerto))
                    w._conectar_modbus()
                    esperar(lambda: w.modbus.estado == "conectado")
                    w.a_ejecutar.setChecked(True)
                    esperar(lambda: w.modbus.escritos == {"motor": True, "luz": False, "vel": 150})
                    cliente = w.modbus.cliente
                    vivo[0] = not red_caida
                    w.edicion.ed.dirty = False  # el cierre no pregunta
                    self.assertTrue(w.close())
                    w.modbus.executor.shutdown(wait=True)  # lo pendiente: el cero y el cierre del TCP
                    self.assertIsNone(cliente._socket, "el TCP queda cerrado")
                    if red_caida:
                        self.assertEqual({(t, d): v for t, d, v in escrituras}[("coil", 0)], 1,
                                         "con la red caída el cero no llega a la planta, pero se cierra igual")
                    else:
                        self.assertEqual(escrituras[-3:], self._CEROS, "lo último que llegó a la planta es el cero")
                finally:
                    vivo[0] = True
                    w.deleteLater()
                    app.processEvents()

    def test_SFIO57_un_mapa_guardado_con_variables_que_ya_no_existen_se_carga_sin_ellas_y_con_aviso(self):
        """REQ-SIM-03, REQ-DAT-02, REQ-ROB-01: al abrir un proyecto cuyo mapa guardado tiene asignaciones de una variable
        borrada o de un tipo que ya no casa, el panel carga el resto (servidor, puerto y demás asignaciones) y avisa de lo que
        ha quitado; un fichero corrupto se sigue rechazando entero, con su mensaje."""
        import json
        from conexion.configuracion import ARCHIVO
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            m = M().var("sensor").var("marcha").var("motor", "output").step("E0", True)
            w = self._ventana_modelo(tmp, m.doc)
            try:
                bueno, corrupto = Path(tmp) / "bueno", Path(tmp) / "corrupto"
                w.edicion.guardar(bueno)
                w.edicion.guardar(corrupto)
                Configuracion(host="10.20.30.40", puerto=1502, unidad=3, periodo_ms=40, modelo=m.doc["id"],
                              senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0),
                                       Senal("marcha", "discrete", 1)]).guardar(bueno / ARCHIVO, m.doc)
                datos = json.loads((bueno / ARCHIVO).read_text(encoding="utf-8"))
                for s in datos["senales"]:
                    if s["variable"] == "marcha":  # una booleana que el mapa guarda como registro: ya no casa
                        s.update(area="holding", direccion=2, formato="INT16", escala="100")
                datos["senales"].append({"variable": "borrada", "area": "discrete", "direccion": 5, "formato": "BOOL", "escala": "1"})
                (bueno / ARCHIVO).write_text(json.dumps(datos), encoding="utf-8")
                self.assertTrue(w.abrir_ruta(fixture_grafnet(bueno / "manifest.json")))
                p = w.panel_es
                self.assertEqual((p.host.text(), p.puerto.value(), p.unidad.value(), p.periodo.value()), ("10.20.30.40", 1502, 3, 40))
                self.assertEqual(self._mapa(w), {"sensor": ("discrete", 0), "motor": ("coil", 0)}, "se conserva el resto")
                self.assertIn("Asignaciones quitadas", p.estado.text())
                self.assertIn("la variable de Entrada 5 ya no existe", p.estado.text(), "sin enseñar el ID de la variable borrada")
                self.assertNotIn("borrada", p.estado.text())
                self.assertIn("«marcha» ya no encaja", p.estado.text())
                self._es(w, True)
                self.assertIn("Asignaciones quitadas", p.estado.text(), "el aviso se ve con el panel a la vista")
                self.assertTrue(p._aplicar(), "lo que queda es un mapa válido")
                self.assertNotIn("Asignaciones quitadas", p.estado.text(), "el aviso dura hasta la siguiente acción sobre el mapa")
                # un fichero corrupto se sigue rechazando entero
                self._es(w, False)
                (corrupto / ARCHIVO).write_text("{ esto no es json", encoding="utf-8")
                from PySide6.QtWidgets import QMessageBox
                with mock.patch("escritorio.ventana.QMessageBox.question",return_value=QMessageBox.StandardButton.Discard) as pregunta:
                    self.assertTrue(w.abrir_ruta(fixture_grafnet(corrupto / "manifest.json")))
                    pregunta.assert_called_once()  # el mapa editado está pendiente de guardar en el archivo
                self.assertIn("No se pudo cargar el mapa", w.panel_es.estado.text())
                self.assertEqual(w.panel_es.config.senales, [])
            finally:
                self._cerrar(app, w)

    # -- Play lee antes de escribir, un solo cero, abrir otro proyecto y avisos (D1) -----------------------------------
    def test_SFIO60_play_lee_las_entradas_antes_de_escribir_y_la_primera_escritura_ya_las_lleva(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): con la planta ya con el sensor a 1, Play no escribe antes de leer: la primera
        petición tras Play es una lectura, no se escribe hasta aplicar esa lectura a la sesión nueva, y lo primero que recibe
        la planta es lo que corresponde al sensor (luz, no el motor de la situación inicial). Reiniciar en Play, igual."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        eventos, escrituras, sensor = [], [], [0]
        planta = self._planta_mixta(escrituras, sensor)

        def responder(p):
            n = len(escrituras)
            respuesta = planta(p)
            if p[0] == 2:
                eventos.append(("leer", respuesta[2]))
            else:
                eventos.extend(("escribir", *e) for e in escrituras[n:])
            return respuesta
        with tempfile.TemporaryDirectory() as tmp, servidor(responder) as sc:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            cero = {"motor": False, "luz": False, "vel": 0}
            try:
                w.panel_es.cargar(m.doc, self._mapa_pausa(m.doc, sc.puerto))
                w._conectar_modbus()
                esperar(lambda: w.modbus.estado == "conectado" and w.modbus.escritos == cero)
                esperar(lambda: sum(e[0] == "leer" for e in eventos) >= 3)
                sensor[0] = 1  # la planta ya tiene el sensor activo cuando se pulsa Play
                esperar(lambda: w.panel_es.indicadores["sensor"][1].text() == "1")
                n = len(eventos)
                w.a_ejecutar.setChecked(True)
                esperar(lambda: w.modbus.escritos == {"motor": False, "luz": True, "vel": 150})
                nuevos = eventos[n:]
                self.assertEqual(nuevos[0][0], "leer", "la primera petición tras Play es una lectura")
                primera = next(i for i, e in enumerate(nuevos) if e[0] == "escribir")
                self.assertGreaterEqual(primera, 1)
                self.assertEqual({e[0] for e in nuevos[:primera]}, {"leer"}, "no se escribe nada antes de leer")
                self.assertIn(("leer", 1), nuevos[:primera], "y lo que se aplica es lo que la planta tiene")
                escribe = [e[1:] for e in nuevos if e[0] == "escribir"]
                self.assertEqual(escribe[:3], [("coil", 0, 0), ("coil", 1, 1), ("holding", 0, 150)],
                                 "la primera escritura ya lleva el sensor: motor a 0, luz a 1 y la consigna")
                self.assertNotIn(("coil", 0, 1), escribe, "el motor de la situación inicial nunca llega a la planta")
                self.assertEqual(w.v.state()["situation"], ["E1"])
                # Reiniciar en Play: sesión nueva (E0) que, con el sensor a 1, evoluciona a E1 antes de escribir nada
                n = len(eventos)
                w.reiniciar()
                esperar(lambda: not w.modbus.reiniciando and w.modbus.en_marcha)
                fin = time.monotonic() + .1
                esperar(lambda: time.monotonic() >= fin)
                self.assertNotIn(("escribir", "coil", 0, 1), eventos[n:], "Reiniciar tampoco escribe antes de leer")
                self.assertEqual(w.v.state()["situation"], ["E1"])
                w.a_ejecutar.setChecked(False)
                esperar(lambda: w.modbus.escritos == cero)
            finally:
                self._cerrar(app, w)

    def test_SFIO62_un_modelo_inestable_en_play_deja_un_solo_cero_en_la_planta(self):
        """REQ-SEM-07, REQ-ROB-01 (P-IMP-60): cuando el motor se detiene por inestabilidad (D-LIM-EVOL) con la planta
        conectada, lo único que llega a la planta tras la lectura que lo provoca es un cero por salida asignada (antes eran
        dos seguidos: el del coordinador y el de Pausa); la ventana acaba en Pausa/edición, conectada y a cero."""
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        eventos, sensor = [], [0]
        planta = self._planta_mixta([], sensor)

        def responder(p):
            respuesta = planta(p)
            eventos.append(("leer", respuesta[2]) if p[0] == 2 else ("escribir", int.from_bytes(p[1:3], "big"), p[6] & 1))
            return respuesta
        with tempfile.TemporaryDirectory() as tmp, servidor(responder) as sc:
            m = self._modelo_inestable()
            w = self._ventana_conectada(tmp, sc, m.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado")
                with mock.patch.object(type(w), "_avisar_inestable", autospec=True) as aviso:
                    w.a_ejecutar.setChecked(True)
                    esperar(lambda: w.modbus.en_marcha)  # con el sensor a 0 es estable
                    sensor[0] = 1  # ahora E0 y E1 se alternan sin fin
                    esperar(lambda: aviso.call_count == 1)
                    esperar(lambda: w.modbus.escritos == {"motor": False} and w.modbus.futuro is None and not w.a_ejecutar.isChecked())
                    fin = time.monotonic() + .2
                    esperar(lambda: time.monotonic() >= fin)  # varios tics más: no llega ningún cero repetido
                self.assertEqual(aviso.call_count, 1)
                tras = [e for e in eventos[eventos.index(("leer", 1)):] if e[0] == "escribir"]
                self.assertEqual(tras, [("escribir", 0, 0)], f"un solo cero tras la lectura que lo provoca: {tras}")
                self.assertEqual((w.modo, w.modbus.estado, w.modbus.adaptador.sesion), ("editar", "conectado", None))
            finally:
                self._cerrar(app, w)

    def test_SFIO63_abrir_otro_proyecto_con_la_conexion_viva_pone_a_cero_tambien_las_salidas_del_mapa_nuevo(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): al abrir otro proyecto con la conexión viva se pone a cero lo del mapa anterior y
        también las salidas asignadas del mapa del proyecto nuevo (la planta podía tenerlas a 1 por su cuenta). Cada canal
        recibe un solo cero aunque lo compartan los dos mapas, y dos variables del mismo ID (una booleana y otra de registro)
        no se estorban; el panel enseña lo del mapa nuevo y la conexión no se cierra."""
        from collections import Counter
        from conexion.configuracion import ARCHIVO
        from escritorio.edicion import Edicion
        from test_modbus import servidor
        app = QApplication.instance() or QApplication([])
        escrituras = []
        planta = self._planta_mixta(escrituras, [0])
        propio = {("coil", 5): 1, ("holding", 3): 150}  # lo que la planta tenía en las salidas del proyecto nuevo
        with tempfile.TemporaryDirectory() as tmp, servidor(planta) as sc:
            a = M("a").var("sensor").var("motor", "output").var("bomba", "output").step("E0", True)
            b = M("b").var("sensor").var("luz", "output").var("motor", "output", "decimal", scale=2).var("otra", "output").step("E0", True)
            ruta = Path(tmp) / "b"
            Edicion.desde(b.doc, {}, "B").guardar(ruta)
            Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, modelo="b", senales=[
                Senal("sensor", "discrete", 0), Senal("luz", "coil", 0), Senal("motor", "holding", 3, "INT16"),
                Senal("otra", "coil", 5)]).guardar(ruta / ARCHIVO, b.doc)
            w = self._ventana_conectada(tmp, sc, a.doc, [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0),
                                                         Senal("bomba", "coil", 2)])
            esperar = lambda c: self._esperar(app, w, c)  # noqa: E731
            try:
                esperar(lambda: w.modbus.estado == "conectado" and w.modbus.escritos == {"motor": False, "bomba": False})
                socket = w.modbus.cliente._socket
                planta_antes = {**propio, **{(t, d): v for t, d, v in escrituras}}
                self.assertEqual((planta_antes[("coil", 5)], planta_antes[("holding", 3)]), (1, 150), "aún sin tocar")
                n = len(escrituras)
                self.assertTrue(w.abrir_ruta(fixture_grafnet(ruta / "manifest.json")))
                esperar(lambda: w.modbus.escritos == {"luz": False, "motor": 0, "otra": False})
                fin = time.monotonic() + .15
                esperar(lambda: time.monotonic() >= fin)
                nuevas = escrituras[n:]
                self.assertEqual(Counter((t, d) for t, d, _ in nuevas),
                                 Counter({("coil", 0): 1, ("coil", 2): 1, ("coil", 5): 1, ("holding", 3): 1}),
                                 f"un cero por canal de los dos mapas: {nuevas}")
                self.assertEqual({v for _, _, v in nuevas}, {0})
                self.assertEqual((w.modbus.estado, w.modo, w.a_ejecutar.isChecked()), ("conectado", "editar", False))
                self.assertIs(w.modbus.cliente._socket, socket, "la conexión sigue")
                self.assertEqual(sorted(s.variable for s in w.panel_es.config.senales), ["luz", "motor", "otra", "sensor"])
                w._desconectar_modbus()
                esperar(lambda: not w.modbus.activo)
            finally:
                self._cerrar(app, w)

    def test_SFIO66_abrir_un_modelo_deja_pausa_sin_estado_tambien_en_el_panel_de_es_y_play_lo_arranca(self):
        """REQ-SIM-03 (P-IMP-60, P-IMP-67): abrir un ejemplo o un proyecto deja el programa en Pausa y sin estado, como tras
        Play y Pausa: las tablas y el panel de E/S no enseñan los valores de la situación inicial (motor, consigna…); Play, que
        arranca la sesión, sí."""
        from escritorio.entradas_salidas import NIVEL_ACTIVO, NIVEL_ASIGNADO
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            m = self._modelo_pausa()
            w = self._ventana_modelo(tmp, m.doc)
            p = w.panel_es
            try:
                p.cargar(m.doc, self._mapa_pausa(m.doc, 502))
                w.refrescar()
                self.assertEqual((w.modo, w.a_ejecutar.isChecked()), ("editar", False))
                self.assertEqual(w.v.state().get("situation", []), [])
                self.assertEqual((w.t_vars.rowCount(), w.t_temp.rowCount(), w.traza.count()), (0, 0, 0))
                self.assertFalse(any(b.isEnabled() for b in w.botones.values()), "sin sesión, las entradas no responden")
                self.assertEqual([p.indicadores[v][1].text() for v in ("sensor", "motor", "luz", "vel")], ["—"] * 4)
                self.assertEqual({p.indicadores[v][0].nivel for v in ("motor", "luz", "vel")}, {NIVEL_ASIGNADO})
                w.a_ejecutar.setChecked(True)  # Play: situación inicial (E0: motor y la consigna memorizada)
                self.assertEqual(w.v.state()["situation"], ["E0"])
                self.assertEqual(p.indicadores["motor"][0].nivel, NIVEL_ACTIVO)
                self.assertEqual(p.indicadores["vel"][1].text(), str(w.v.state()["values"]["vel"]))
                self.assertNotEqual(p.indicadores["vel"][1].text(), "—")
                w.a_ejecutar.setChecked(False)
                self.assertEqual(p.indicadores["vel"][1].text(), "—", "y Pausa vuelve a dejarlo sin estado")
            finally:
                self._cerrar(app, w)

    def test_SFIO67_una_asignada_que_pasa_a_interna_se_quita_con_el_aviso_de_quitar_obsoletas(self):
        """REQ-SIM-03, REQ-EDT-07 (P-IMP-67): si una variable asignada pasa a «interna», el panel avisa de que «ya no es de
        entrada ni de salida», lo mismo que dice `Configuracion.quitar_obsoletas` al abrir un proyecto; «ya no existe» queda
        para la variable que se ha borrado."""
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w = self._ventana_nueva(tmp)
            p = w.panel_es
            try:
                w.nuevo()
                self.assertIsNone(w.edicion.nueva_variable("sensor"))
                self.assertIsNone(w.edicion.nueva_variable("luz", "output"))
                self._es(w, True)
                self.assertTrue(p.asignar(self._vid(w, "sensor"), "discrete", 0))
                self.assertTrue(p.asignar(self._vid(w, "luz"), "coil", 0))
                config = copy.deepcopy(p.obtener())
                self._es(w, False)
                self.assertIsNone(w.edicion.cambiar_variable(self._vid(w, "sensor"), role="internal"))
                self.assertIsNone(w.edicion.quitar_variable(self._vid(w, "luz")))
                self._es(w, True)
                texto = p.estado.text()
                self.assertIn("«sensor» ya no es de entrada ni de salida", texto)
                self.assertNotIn("«sensor» ya no existe", texto)
                self.assertIn("«luz» ya no existe", texto)
                self.assertEqual(self._mapa(w), {})
                # el mismo texto que da el núcleo de conexión para la variable que pasó a interna
                self.assertEqual(config.quitar_obsoletas(w.edicion.ed.model),
                                 ["«sensor» ya no es de entrada ni de salida", "la variable de Salida 0 ya no existe"])
            finally:
                self._cerrar(app, w)
