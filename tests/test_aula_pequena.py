"""Comentarios de una clase real: barras de desplazamiento, IP de Modbus en cuatro cajas, luz de la conexión externa y aviso de
versión nueva. Las pruebas de red usan un acceso inyectado: ninguna toca Internet."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_editor_cadenas import BaseQt, QT
from grafcet.routing import enlaces
from conexion.configuracion import CONEXION_INICIAL, Configuracion, aviso_host, es_ipv4, normalizar_host

if QT:
    from PySide6.QtCore import QEvent, QPointF, QSettings, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from escritorio import actualizaciones
    from escritorio.actualizaciones import Comprobador, Resultado, consultar, es_mas_nueva, interpretar, numeros_version


def _json(tag, url="https://github.com/SrLaguarto/GRAFCET-Connect/releases/tag/x"):
    return json.dumps({"tag_name": tag, "html_url": url})


class HostIPv4(unittest.TestCase):
    def test_SIP01_validacion_de_host(self):
        """REQ-SIM-03: el host de la conexión Modbus es una IPv4; lo demás se rechaza con un mensaje claro."""
        self.assertTrue(es_ipv4("192.168.1.133"))
        for malo in ("localhost", "256.1.1.1", "1.2.3", "1.2.3.4.5", "a.b.c.d", "01.2.3.4", "1.2..4", ""):
            self.assertFalse(es_ipv4(malo), malo)
        doc = {"id": "m", "variables": []}
        Configuracion(host="10.0.0.7").validar(doc)
        with self.assertRaisesRegex(ValueError, "IP de cuatro números"):
            Configuracion(host="localhost").validar(doc)

    def test_SIP02_host_guardado_no_valido(self):
        """REQ-SIM-03: «localhost» se carga como 127.0.0.1; cualquier otro valor no válido, como la dirección inicial, pero con
        un aviso que lo dice (no se sustituye en silencio) y sin guardar la sustitución."""
        self.assertEqual(aviso_host("plc.aula"), "La dirección guardada (plc.aula) no es una IP. Escriba la IP del servidor.")
        self.assertIn("fe80::1", aviso_host(" fe80::1 "))
        for bueno in ("10.1.2.3", "localhost", " LocalHost ", "", None, 5):
            self.assertEqual(aviso_host(bueno), "", bueno)
        self.assertEqual(normalizar_host("localhost"), "127.0.0.1")
        self.assertEqual(normalizar_host(" LocalHost "), "127.0.0.1")
        self.assertEqual(normalizar_host("mi-servidor"), CONEXION_INICIAL[0])
        self.assertEqual(normalizar_host(None), CONEXION_INICIAL[0])
        self.assertEqual(normalizar_host("10.1.2.3"), "10.1.2.3")

    def test_SIP08_mapa_guardado_con_nombre_dns_carga_con_aviso_y_no_se_reescribe(self):
        """REQ-SIM-03: un mapa con un host que no es IP carga con la IP inicial en las cajas y un aviso; el fichero no cambia."""
        doc = {"id": "m", "variables": []}
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "c.json"
            Configuracion(host="10.0.0.7", modelo="m").guardar(ruta, doc)
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            datos["host"] = "plc.aula"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            c = Configuracion.cargar(ruta, doc)
            self.assertEqual((c.host, c.aviso_host), (CONEXION_INICIAL[0], "La dirección guardada (plc.aula) no es una IP. Escriba la IP del servidor."))
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["host"], "plc.aula")
            Configuracion.cargar(ruta, doc)  # (y cargarlo no lo toca)
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["host"], "plc.aula")
            datos["host"] = "localhost"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            self.assertEqual(Configuracion.cargar(ruta, doc).aviso_host, "")


@unittest.skipUnless(QT, "PySide6 no está instalado")
class CampoIP(BaseQt):
    def campo(self):
        c = self.w.panel_es.host
        c.setText("1.2.3.4")
        return c

    def mostrar(self):
        """La IP vive en el diálogo de configuración: hay que mostrarlo para que haya foco."""
        d = self.w.panel_es.dialogo_config
        d.show()
        d.activateWindow()
        QApplication.processEvents()
        return self.w.panel_es.host

    def teclear(self, caja, texto):
        caja.setFocus()
        for t in texto:
            QTest.keyClicks(caja, t)

    def test_SIP03_campo_de_cuatro_cajas(self):
        """REQ-SIM-03: la IP son cuatro cajas con nombre accesible; text()/setText() usan «a.b.c.d»."""
        c = self.w.panel_es.host
        self.assertEqual(len(c.cajas), 4)
        self.assertEqual([x.accessibleName() for x in c.cajas],
                         [f"IP, {n} número" for n in ("primer", "segundo", "tercer", "cuarto")])
        c.setText("192.168.1.133")
        self.assertEqual(c.text(), "192.168.1.133")
        c.setText("localhost")
        self.assertEqual(c.text(), "127.0.0.1")
        c.setText("raro")
        self.assertEqual(c.text(), CONEXION_INICIAL[0])

    def test_SIP04_teclado_salta_y_rechaza(self):
        """REQ-SIM-03: tres cifras o un punto pasan a la siguiente caja; solo cifras; no se admite más de 255."""
        c = self.mostrar()
        for caja in c.cajas:
            caja.setText("")
        self.teclear(c.cajas[0], "192")
        self.assertTrue(c.cajas[1].hasFocus())
        self.teclear(c.cajas[1], "1.")
        self.assertTrue(c.cajas[2].hasFocus())
        self.assertEqual(c.cajas[1].text(), "1")
        self.teclear(c.cajas[2], "a2")
        self.assertEqual(c.cajas[2].text(), "2")
        self.teclear(c.cajas[2], "60")  # 260 > 255: la última cifra no entra
        self.assertEqual(c.cajas[2].text(), "26")

    def test_SIP05_retroceso_y_pegado(self):
        """REQ-SIM-03: Retroceso en una caja vacía vuelve a la anterior; pegar «a.b.c.d» en cualquier caja reparte los números."""
        c = self.mostrar()
        c.setText("1.2.3.4")
        c.cajas[2].setText("")
        c.cajas[2].setFocus()
        QTest.keyClick(c.cajas[2], Qt.Key.Key_Backspace)
        self.assertTrue(c.cajas[1].hasFocus())
        c.cajas[2].setFocus()
        c.cajas[2].insert("10.20.30.40")  # lo que genera pegar
        c.cajas[2].textEdited.emit("10.20.30.40")
        self.assertEqual(c.text(), "10.20.30.40")
        c.cajas[0].textEdited.emit("256.1.1.1")  # no válido: no cambia nada
        self.assertEqual(c.text(), "10.20.30.40")

    def test_SIP06_editingfinished_al_salir(self):
        """REQ-SIM-03: la señal editingFinished se emite al salir de la dirección o con Intro, no al saltar entre cajas."""
        c = self.mostrar()
        c.setText("1.2.3.4")
        recibidas = []
        c.editingFinished.connect(lambda: recibidas.append(c.text()))
        c.cajas[0].setFocus()
        c.cajas[1].setFocus()
        QApplication.processEvents()
        self.assertEqual(recibidas, [])
        QTest.keyClick(c.cajas[1], Qt.Key.Key_Return)
        self.assertEqual(recibidas, ["1.2.3.4"])

    def test_SIP07_host_recordado_no_ipv4(self):
        """REQ-SIM-03: un host guardado que no es IPv4 se carga normalizado, con aviso, y sin reescribir lo guardado."""
        for guardado, esperado in (("localhost", "127.0.0.1"), ("otra-cosa", CONEXION_INICIAL[0]), ("10.9.8.7", "10.9.8.7")):
            self.w.ajustes.setValue("modbus/host", guardado)
            self.assertEqual(self.w._leer_conexion_recordada()[0], esperado)
            self.assertEqual(self.w._aviso_host_recordado, "" if guardado != "otra-cosa" else aviso_host(guardado))
            self.assertEqual(self.w.ajustes.value("modbus/host"), guardado, "no se guarda la sustitución")

    def test_SIP09_el_panel_enseña_el_aviso_hasta_que_se_aplica_una_ip(self):
        """REQ-SIM-03: con un host recordado que no es IP, el estado del panel de E/S lo dice y las cajas llevan la IP inicial;
        aplicar el mapa con una IP escrita quita el aviso."""
        self.w.ajustes.setValue("modbus/host", "plc.aula")
        self.w._leer_conexion_recordada()
        p = self.w.panel_es
        p.aviso_host_defecto = self.w._aviso_host_recordado
        p.cargar(p.doc)
        self.assertEqual(p.host.text(), CONEXION_INICIAL[0])
        self.assertIn("La dirección guardada (plc.aula) no es una IP. Escriba la IP del servidor.", p.estado.nota)
        p.host.setText("10.0.0.9")
        self.assertTrue(p._aplicar())
        self.assertEqual(p.aviso_host, "")

    def test_SIP10_ceros_a_la_izquierda_se_quitan_al_salir_de_la_caja(self):
        """REQ-SIM-03: «010» pasa a «10» y «000» a «0» al salir de la caja o pulsar Intro."""
        c = self.mostrar()
        c.setText("1.2.3.4")
        c.cajas[0].setText("010")
        c.cajas[1].setText("000")
        c.cajas[2].setText("007")
        c.cajas[3].setText("100")
        c.cajas[0].setFocus()
        c.cajas[1].setFocus()
        QApplication.processEvents()
        self.assertEqual(c.cajas[0].text(), "10")
        c.cajas[2].setFocus()
        c.cajas[3].setFocus()
        QApplication.processEvents()
        self.assertEqual((c.cajas[1].text(), c.cajas[2].text(), c.cajas[3].text()), ("0", "7", "100"))
        c.cajas[3].setText("050")
        QTest.keyClick(c.cajas[3], Qt.Key.Key_Return)
        self.assertEqual(c.text(), "10.0.7.50")


@unittest.skipUnless(QT, "PySide6 no está instalado")
class Barras(BaseQt):
    def test_SSCR01_ventana_pequena_con_barras_a_la_vista(self):
        """REQ-EDT-09: con la ventana pequeña los paneles laterales se desplazan en ambos sentidos y las barras se ven."""
        w = self.w
        w.resize(640, 400)
        w.show()
        QApplication.processEvents()
        for area in (w.scroll, w.derecho.widget(1)):
            self.assertEqual(area.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.assertEqual(area.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.assertEqual(w.panel_es.scroll_cuerpo.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.assertEqual(w.panel_es.scroll_cuerpo.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # el contenido que no cabe es alcanzable: si es más alto o ancho que la vista, la barra existe y se puede mover
        for area in (w.scroll, w.derecho.widget(1)):
            interior, vista = area.widget(), area.viewport()
            if interior.minimumSizeHint().height() > vista.height():
                self.assertGreater(area.verticalScrollBar().maximum(), 0)
            if interior.minimumSizeHint().width() > vista.width():
                self.assertGreater(area.horizontalScrollBar().maximum(), 0)
        self.assertIn("width: 12px", w.styleSheet())  # barras de 12 px y asa oscura, visibles


@unittest.skipUnless(QT, "PySide6 no está instalado")
class Luz(BaseQt):
    def test_SLUZ01_luz_de_la_conexion_externa(self):
        """REQ-SIM-03: la barra de simulación muestra si la conexión externa está conectada, desconectada o en error."""
        w = self.w
        self.assertEqual(w.luz_es.text(), "E/S externas: desconectada")
        w.panel_es.mostrar_estado("conectado", "Conectado")
        self.assertEqual(w.luz_es.text(), "E/S externas: conectada")
        w.panel_es.mostrar_estado("error", "Sin respuesta")
        self.assertEqual(w.luz_es.text(), "E/S externas: error")
        self.assertIn("Sin respuesta", w.luz_es.toolTip())
        w.panel_es.mostrar_estado("desconectado", "")
        self.assertEqual(w.luz_es.text(), "E/S externas: desconectada")
        w.luz_es.click()
        self.assertEqual(w.paginas_es.currentIndex(), 1)


@unittest.skipUnless(QT, "PySide6 no está instalado")
class MenuGirar(BaseQt):
    def test_SGIR01_menu_girar_transicion(self):
        """REQ-EDT-09: el menú Editar gira la transición seleccionada; sin atajo propio (lo trata el dibujo) y desactivado fuera de edición."""
        w, e = self.vacio()
        for a, texto in ((w.a_girar_izq, "antihorario"), (w.a_girar_der, "horario")):
            self.assertIn(texto, a.text())
            self.assertTrue(a.shortcut().isEmpty())
        llamadas = []
        e.girar_transiciones = lambda sentido, transiciones=None: llamadas.append(sentido)
        w.a_girar_izq.trigger()
        w.a_girar_der.trigger()
        self.assertEqual(llamadas, [-1, 1])
        w.a_ejecutar.setChecked(False)
        w._acciones_edicion(False)
        self.assertFalse(w.a_girar_izq.isEnabled() or w.a_girar_der.isEnabled())


class Versiones(unittest.TestCase):
    def test_SACT01_comparacion_numerica(self):
        """REQ-SIM-03: las versiones se comparan como tuplas numéricas, no como texto."""
        self.assertEqual(numeros_version("v1.0.2"), (1, 0, 2))
        self.assertIsNone(numeros_version("1.0.2-beta"))
        self.assertIsNone(numeros_version(None))
        self.assertTrue(es_mas_nueva("v1.0.10", "1.0.9"))
        self.assertTrue(es_mas_nueva("1.1", "1.0.9"))
        self.assertFalse(es_mas_nueva("1.0", "1.0.0"))
        self.assertFalse(es_mas_nueva("1.0.1", "1.0.1"))
        self.assertFalse(es_mas_nueva("0.9.9", "1.0.1"))
        self.assertFalse(es_mas_nueva("raro", "1.0.1"))

    def test_SACT02_interpreta_el_json(self):
        """REQ-SIM-03: la respuesta de GitHub da nueva, al día o fallo."""
        self.assertEqual(interpretar(_json("v1.0.2", "https://x/r"), "1.0.1"), Resultado("nueva", "1.0.2", "https://x/r"))
        self.assertEqual(interpretar(_json("v1.0.1"), "1.0.1").estado, "al_dia")
        for roto in ("", "no es json", "[]", "{}", json.dumps({"tag_name": 5}), json.dumps({"tag_name": "nightly"}),
                     json.dumps({"tag_name": "v1.0.2", "html_url": 3})):
            self.assertEqual(interpretar(roto, "1.0.1").estado, "fallo", roto)

    def test_SACT03_los_fallos_son_silenciosos(self):
        """REQ-SIM-03: sin red, con límite de peticiones o con basura, la consulta no lanza: devuelve fallo."""
        def sin_red(url, agente, espera):
            raise OSError("sin conexión")
        self.assertEqual(consultar(sin_red).estado, "fallo")
        self.assertEqual(consultar(lambda *a: "<html>").estado, "fallo")
        pedido = {}

        def espia(url, agente, espera):
            pedido.update(url=url, agente=agente, espera=espera)
            return _json("v99.0.0")
        r = consultar(espia, "1.0.1")
        self.assertEqual((r.estado, r.version), ("nueva", "99.0.0"))
        self.assertEqual(pedido["url"], actualizaciones.URL_ULTIMA)
        self.assertEqual(pedido["agente"], "GRAFCET-Connect/1.0.1")
        self.assertLessEqual(pedido["espera"], 5)


@unittest.skipUnless(QT, "PySide6 no está instalado")
class AvisoVersion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from escritorio.ventana import Ventana
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = str(Path(self.tmp.name) / "a.ini")
        self.respuesta = _json("v999.0.0", "https://github.com/SrLaguarto/GRAFCET-Connect/releases/tag/v999.0.0")
        self.llamadas = []
        self.w = self.nueva_ventana()
        self._ventana = Ventana

    def nueva_ventana(self):
        from escritorio.ventana import Ventana

        def obtener(url, agente, espera):
            self.llamadas.append(url)
            if isinstance(self.respuesta, Exception):
                raise self.respuesta
            return self.respuesta
        w = Ventana(QSettings(self.ruta, QSettings.Format.IniFormat), obtener)
        w.comprobador.sincrono = True
        return w

    def tearDown(self):
        self.w.edicion = None
        self.w.deleteLater()
        self.tmp.cleanup()

    def test_SACT04_aviso_no_modal_y_ahora_no_se_recuerda(self):
        """REQ-SIM-03: una versión nueva se avisa sin ventana modal; «Ahora no» la recuerda y no se repite en el arranque."""
        w = self.w
        w.show()
        self.assertTrue(w.aviso_version.isHidden())
        w.buscar_actualizaciones()
        self.assertFalse(w.aviso_version.isHidden())
        self.assertIn("999.0.0", w.l_version.text())
        w.b_ahora_no.click()
        self.assertTrue(w.aviso_version.isHidden())
        self.assertEqual(w.ajustes.value("actualizaciones/ignorada"), "999.0.0")
        w.buscar_actualizaciones()  # el mismo arranque: no se vuelve a mostrar
        self.assertTrue(w.aviso_version.isHidden())
        self.respuesta = _json("v999.0.1")  # una versión posterior sí
        w.buscar_actualizaciones()
        self.assertFalse(w.aviso_version.isHidden())

    def test_SACT05_fallo_en_el_arranque_no_dice_nada(self):
        """REQ-SIM-03: en el arranque, un fallo de red no muestra aviso ni mensaje."""
        self.respuesta = OSError("sin conexión")
        self.w.show()
        self.w.buscar_actualizaciones()
        self.assertTrue(self.w.aviso_version.isHidden())
        self.assertEqual(self.w.statusBar().currentMessage(), "")

    def test_SACT06_comprobacion_manual_informa_siempre(self):
        """REQ-SIM-03: «Buscar actualizaciones…» informa de nueva versión, última versión o imposibilidad de comprobar."""
        textos = []
        orig = QMessageBox.information
        QMessageBox.information = staticmethod(lambda padre, titulo, texto, *a: textos.append(texto))
        try:
            self.respuesta = _json("v0.0.1")
            self.w.buscar_actualizaciones(True)
            self.respuesta = OSError("sin conexión")
            self.w.buscar_actualizaciones(True)
        finally:
            QMessageBox.information = orig
        self.assertIn("última versión", textos[0])
        self.assertIn("No se ha podido comprobar", textos[1])

    def test_SACT07_ajuste_al_arrancar(self):
        """REQ-SIM-03: «Buscar actualizaciones al arrancar» está activo por defecto y se guarda."""
        self.assertTrue(actualizaciones.al_arrancar_activo(self.w.ajustes))
        self.assertTrue(self.w.a_actualizar_arranque.isChecked())
        self.w.a_actualizar_arranque.setChecked(False)
        self.assertFalse(self.w.ajustes.value("actualizaciones/al_arrancar", True, type=bool))
        w2 = self.nueva_ventana()
        self.assertFalse(w2.a_actualizar_arranque.isChecked())
        self.assertFalse(actualizaciones.al_arrancar_activo(w2.ajustes))
        w2.deleteLater()
        self.assertEqual(self.llamadas, [])  # construir la ventana nunca consulta la red

    def test_SACT08_el_hilo_entrega_el_resultado(self):
        """REQ-SIM-03: sin modo síncrono, la consulta va en un hilo y el resultado llega a la interfaz."""
        c = Comprobador(None, lambda *a: _json("v999.0.0"))
        recibido = []
        c.resultado.connect(lambda manual, r: recibido.append((manual, r)))
        c.comprobar(True)
        c.hilo.join(5)
        for _ in range(50):
            QApplication.processEvents()
            if recibido:
                break
            QTest.qWait(20)
        self.assertEqual(recibido[0][0], True)
        self.assertEqual(recibido[0][1].estado, "nueva")

    def test_SACT09_una_comprobacion_manual_con_otra_en_marcha_tambien_contesta(self):
        """REQ-SIM-03: si se pide una comprobación manual mientras corre la del arranque, su resultado se entrega como manual."""
        import threading
        espera = threading.Event()

        def obtener(*a):
            espera.wait(5)
            return _json("v999.0.0")
        c = Comprobador(None, obtener)
        recibido = []
        c.resultado.connect(lambda manual, r: recibido.append(manual))
        c.comprobar(False)  # la del arranque
        c.comprobar(True)  # la manual: no lanza otra consulta, pero queda anotada
        espera.set()
        c.hilo.join(5)
        for _ in range(50):
            QApplication.processEvents()
            if recibido:
                break
            QTest.qWait(20)
        self.assertEqual(recibido, [True])
        recibido.clear()
        c.comprobar(False)  # y ya no queda nada pendiente
        c.hilo.join(5)
        for _ in range(50):
            QApplication.processEvents()
            if recibido:
                break
            QTest.qWait(20)
        self.assertEqual(recibido, [False])

    def test_SACT10_solo_se_abren_las_urls_del_repositorio(self):
        """REQ-SIM-03: «Descargar» abre la URL de la publicación solo si es de github.com/SrLaguarto/GRAFCET-Connect/; si no, la última."""
        ok = "https://github.com/SrLaguarto/GRAFCET-Connect/releases/tag/v9"
        ultima = "https://github.com/SrLaguarto/GRAFCET-Connect/releases/latest"
        self.assertEqual(actualizaciones.url_segura(ok), ok)
        for mala in ("https://evil.example/https://github.com/SrLaguarto/GRAFCET-Connect/", "http://github.com/SrLaguarto/GRAFCET-Connect/x",
                     "https://github.com/SrLaguarto/GRAFCET-Connect", "https://github.com/otro/GRAFCET-Connect/x", "file:///c:/x", "", None):
            self.assertEqual(actualizaciones.url_segura(mala), ultima, mala)
        abiertas = []
        with mock.patch("escritorio.ventana.QDesktopServices.openUrl", side_effect=lambda u: abiertas.append(u.toString())):
            self.w._version_nueva = Resultado("nueva", "9", "https://evil.example/x")
            self.w._descargar_version()
            self.w._version_nueva = Resultado("nueva", "9", ok)
            self.w._descargar_version()
        self.assertEqual(abiertas, [ultima, ok])


@unittest.skipUnless(QT, "PySide6 no está instalado")
class TeclasDeGiro(BaseQt):
    def test_SGIR02_ctrl_mayus_flechas_no_giran_en_solo_lectura_ni_al_simular(self):
        """REQ-EDT-09: Ctrl+Mayús+←/→ gira al editar y no hace nada con el controlador de solo selección ni al simular."""
        w, e = self.vacio()
        llamadas = []
        e.girar_transiciones = lambda sentido, transiciones=None: llamadas.append(sentido)

        def pulsar():
            ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right,
                           Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            w.diagrama.keyPressEvent(ev)
        pulsar()
        self.assertEqual(llamadas, [1])
        e.solo_seleccion = True  # como el controlador de «Añadir a la hoja»
        pulsar()
        self.assertEqual(llamadas, [1])
        e.solo_seleccion = False
        with mock.patch("escritorio.ventana.QMessageBox.warning"):
            w.a_ejecutar.setChecked(True)
        if w.modo != "editar":
            pulsar()
            self.assertEqual(llamadas, [1])


@unittest.skipUnless(QT, "PySide6 no está instalado")
class PulidoTrasLaSegundaPrueba(BaseQt):
    """Cambios tras la segunda prueba del responsable: nombres largos con ayuda, flecha de los enlaces a mano, enlaces de
    transiciones giradas movibles, aviso de las acciones sueltas, fórmulas sin «Escribir a mano» y la luz de la conexión."""

    def con_enlace(self, orientacion=None, posiciones=((100, 60), (160, 140), (220, 220))):
        w, e = self.vacio()
        a = e.ed.add_step("g", "1", True, at=posiciones[0])
        b = e.ed.add_step("g", "2", at=posiciones[2])
        t, _ = e.ed.add_transition("g", "", [a], [b], at=posiciones[1], label="t1")
        e.cambia()
        self.assertIsNone(e.poner_condicion(t, "p", crear=True))
        if orientacion:
            e.ed.set_transition_orientation(t, orientacion)
            e.cambia()
        return w, e, a, b, t

    # -- 1. nombres largos
    def test_SPUL01_el_nombre_entero_sale_en_la_ayuda_de_cada_lugar_donde_se_recorta(self):
        """REQ-EDT-07, REQ-SIM-03: la tabla de variables, las listas del panel de E/S, las tablas de la simulación y las fichas
        de los bloques ofrecen el nombre completo en una ayuda emergente."""
        from escritorio.bloques import PaletaBloques
        largo = "LAENTRADA_CON_UN_NOMBRE_MUY_LARGO_DE_VERDAD"
        w, e = self.vacio()
        e.nueva_variable(largo, "input")
        w.show()
        QApplication.processEvents()
        tabla = w.variables.tabla
        fila = [tabla.item(r, 0).text() for r in range(tabla.rowCount())].index(largo)
        self.assertEqual(tabla.item(fila, 0).toolTip(), largo)
        w.mostrar_es()
        QApplication.processEvents()
        item = w.panel_es.lista_entradas.item(0)
        self.assertEqual(item.text(), largo)
        self.assertTrue(item.toolTip().startswith(largo), item.toolTip())
        w._filas(w.t_vars, [(largo, "salida continua", "ON", "", "ok")])
        self.assertEqual(w.t_vars.item(0, 0).toolTip(), largo)
        paleta = PaletaBloques(lambda: ({largo: ("input", "bool")}, []), columna=True)
        paleta.cargar("entrada")
        paleta.resize(90, 60)
        paleta._calcular(90)
        self.assertTrue(paleta.motor.recortadas, "con 90 px el nombre se recorta con «…»")
        rect, completo = paleta.motor.recortadas[0]
        self.assertEqual(completo, largo)
        self.assertEqual(paleta._completo_en(rect.center()), largo)
        self.assertEqual(paleta._completo_en(QPointF(1000, 1000)), "")

    # -- 2. flecha de un enlace
    def test_SPUL02_el_boton_derecho_en_un_enlace_muestra_o_quita_la_flecha(self):
        """REQ-EDT-02: «Mostrar flecha» si el enlace no la lleva y «Quitar flecha» si la lleva (solo la que cambia el estado);
        queda en linkStyles[enlace].arrows.flow.visible, con una operación de deshacer, y se dibuja en la ruta."""
        w, e, a, b, t = self.con_enlace()
        enlace = f"{t}|{a}|pre"
        pts = next(r for r in enlaces(e.M) if r["id"] == enlace)["pts"]
        punto = QPointF((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
        self.assertFalse(e.flecha_visible(enlace), "un enlace que baja no lleva flecha")
        opciones = [x for x, _ in e.menu(punto) if x != "-"]
        self.assertIn("Mostrar flecha", opciones)
        self.assertNotIn("Quitar flecha", opciones)
        n = len(e.ed.undo_stack)
        dict(e.menu(punto))["Mostrar flecha"]()
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        self.assertTrue(e.flecha_visible(enlace))
        self.assertIs(e.ed.presentation["linkStyles"][enlace]["arrows"]["flow"]["visible"], True)
        self.assertTrue(any(f["key"] == "flow" for f in next(r for r in enlaces(e.M) if r["id"] == enlace)["arrows"]))
        opciones = [x for x, _ in e.menu(punto) if x != "-"]
        self.assertIn("Quitar flecha", opciones)
        self.assertNotIn("Mostrar flecha", opciones)
        dict(e.menu(punto))["Quitar flecha"]()
        self.assertFalse(e.flecha_visible(enlace))
        self.assertIs(e.ed.presentation["linkStyles"][enlace]["arrows"]["flow"]["visible"], False)
        e.deshacer()
        self.assertTrue(e.flecha_visible(enlace))

    # -- 4. enlaces de transiciones giradas
    def test_SPUL03_los_tramos_de_un_enlace_de_transicion_girada_se_mueven_y_se_deshacen(self):
        """REQ-EDT-02: el enlace de una transición girada tiene tiradores; arrastrar uno corre ese tramo (route.tramos, relativo
        al recorrido automático), se respeta al dibujar, es una operación de deshacer y un recorrido de otra forma lo ignora."""
        from grafcet.routing import desplazar_tramos
        w, e, a, b, t = self.con_enlace("derecha", ((100, 60), (100, 140), (100, 220)))
        post = f"{t}|{b}|post"
        ruta = next(r for r in enlaces(e.M) if r["id"] == post)
        self.assertTrue(ruta["handles"], "tiene tiradores")
        h = ruta["handles"][0]
        self.assertTrue(h["orient"])
        i = h["segment"]
        antes = ruta["pts"]
        vertical = antes[i][0] == antes[i + 1][0]
        e.sel = [post]
        p = QPointF(*h["pos"])
        destino = p + (QPointF(40, 0) if vertical else QPointF(0, 40))
        n = len(e.ed.undo_stack)
        e.prensar(p)
        e.mover(destino)
        e.soltar(destino)
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        tramos = e.ed.presentation["linkStyles"][post]["route"]["tramos"]
        self.assertEqual(tramos["n"], str(len(antes)))
        despues = next(r for r in enlaces(e.M) if r["id"] == post)["pts"]
        eje = 0 if vertical else 1
        movido = despues[i][eje] - antes[i][eje]
        self.assertAlmostEqual(movido, 40, delta=6, msg="a la rejilla")
        self.assertEqual(despues[i + 1][eje] - antes[i + 1][eje], movido)
        self.assertEqual((despues[0], despues[-1]), (antes[0], antes[-1]), "los extremos no se mueven")
        e.deshacer()
        self.assertEqual(next(r for r in enlaces(e.M) if r["id"] == post)["pts"], antes)
        # un ajuste guardado para otra forma del recorrido (otro nº de puntos) no se aplica
        self.assertEqual(desplazar_tramos(antes, {"n": str(len(antes) + 1), str(i): "40"}), antes)
        self.assertEqual(desplazar_tramos(antes, None), antes)

    # -- 5. acción suelta
    def test_SPUL04_una_accion_suelta_con_un_valor_valido_no_deja_el_aviso_de_antes(self):
        """REQ-EDT-02: armar «Q + 1» con bloques en una acción suelta pasa por textos a medias (avisa) y, al quedar válido, el aviso
        desaparece; un texto de verdad inválido sigue avisando."""
        from escritorio.bloques import nuevo
        w, e = self.vacio()
        e.ed.add_variable("Q", "internal", {"kind": "int"})
        e.cambia()
        did = e.ed.add_draft_action((100, 100), {})
        e.sel, e.accion = [did], did
        e.reconstruir()
        e.cambiado.emit()
        e.tipo_accion(did, "activacion")
        e.cambiado.emit()
        pa = w.props.accion
        pa.poner_variable("Q")
        pa.prog.colocar(nuevo("ar", op="+"))
        self.assertIn("El valor no es válido", pa.msg.text(), "a medias, con huecos")
        pa.prog.colocar(nuevo("vnum", n="Q"))
        pa.prog.colocar(nuevo("num", v="1"))
        self.assertEqual((pa.valor.text(), pa.msg.text(), pa._rechazado), ("Q + 1", "", None))
        self.assertEqual(e.datos_accion(e.accion_activa())["valor"], "Q + 1")
        pa._desde_bloques("Q +")
        self.assertIn("El valor no es válido", pa.msg.text())

    # -- 6 y 7. fórmulas
    def test_SPUL05_la_formula_de_la_transicion_y_el_valor_de_la_accion_se_ven_con_la_notacion_del_dibujo(self):
        """REQ-EDT-02: sin «Escribir a mano» en ninguna; el cuadro de la fórmula no se edita y la muestra como el dibujo (↑, ↓,
        sobrerrayado, ·, +, X2); el valor de la acción lleva «Q :=» (o «? :=») en lugar de «Valor»."""
        from escritorio.acciones import CajaFormula
        w, e = self.vacio()
        for nombre in ("a", "b"):
            e.ed.add_variable(nombre, "input", {"kind": "bool"})
        e.ed.add_variable("Q", "internal", {"kind": "int"})
        s = e.ed.add_step("g", "1", True, at=(100, 60))
        s2 = e.ed.add_step("g", "2", at=(100, 220))
        t, _ = e.ed.add_transition("g", "", [s], [s2], at=(100, 140), label="t1")
        e.cambia()
        self.assertIsNone(e.poner_condicion(t, "↑a AND NOT b OR X2"))
        e.seleccionar([t])
        p = w.props
        self.assertFalse(hasattr(p, "t_manual"))
        self.assertIsInstance(p.t_texto, CajaFormula)
        self.assertTrue(p.t_texto.isReadOnly())
        self.assertEqual(p.t_texto.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(p.t_texto.text(), "↑a AND NOT b OR X2", "el texto del usuario no cambia")
        html = p.t_texto.html_mostrado()
        self.assertIn("↑", html)
        self.assertIn("overline", html)
        self.assertIn("·", html)
        self.assertNotIn(" AND ", html)
        self.assertIn("X2", html)
        p.t_texto.setText("a AND")  # a medias: se ve tal cual
        self.assertIsNone(p.t_texto.html_mostrado())
        # la acción: «Q :=» y el valor con el formato del dibujo
        did = e.ed.add_draft_action((100, 100), {})
        e.sel, e.accion = [did], did
        e.reconstruir()
        e.cambiado.emit()
        e.tipo_accion(did, "activacion")
        e.cambiado.emit()
        pa = p.accion
        self.assertFalse(hasattr(pa, "manual"))
        self.assertEqual(pa.l_valor.text(), "? :=")
        pa.poner_variable("Q")
        self.assertEqual((pa.l_valor.text(), pa.l_fichas.text()), ("Q :=", "Q :="))
        pa._desde_bloques("Q + 1")
        self.assertEqual(pa.valor.text(), "Q + 1")
        self.assertIn("Q", pa.valor.html_mostrado())
        self.assertTrue(pa.valor.isReadOnly())

    # -- 10. luz de la conexión
    def test_SPUL06_la_luz_de_la_conexion_va_al_final_de_la_fila_de_las_pestanas(self):
        """REQ-SIM-03: «E/S externas: …» queda a la derecha del todo de la fila de GRAFCET / PLANOS / E/S externas, no junto a
        Reiniciar; un clic abre la vista de E/S."""
        w = self.w
        w.resize(1200, 800)
        w.show()
        QApplication.processEvents()
        self.assertIs(w.luz_es.parentWidget(), w.fila_pestanas)
        self.assertIs(w.pestanas_vistas.parentWidget(), w.fila_pestanas)
        fila = w.fila_pestanas.rect()
        self.assertGreater(w.luz_es.geometry().left(), w.pestanas_vistas.geometry().right())
        self.assertGreater(w.luz_es.geometry().right(), fila.right() - 20)
        self.assertLessEqual(w.luz_es.geometry().right(), fila.right())
        self.assertFalse(w.tb_sim.isAncestorOf(w.luz_es))
        w.luz_es.click()
        self.assertEqual(w.paginas_es.currentIndex(), 1)


if __name__ == "__main__":
    unittest.main()
