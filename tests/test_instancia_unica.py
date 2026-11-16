"""SIU: instancia única entre procesos y guardado/cancelación al recibir otra apertura."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QElapsedTimer, QEventLoop, QPointF, QProcess, Qt, QTimer
    from PySide6.QtNetwork import QLocalSocket
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
    from escritorio.instancia_unica import InstanciaUnica, mensaje_apertura
    from test_editor_cadenas import BaseQt
    QT = True
except ImportError:
    QT = False
    BaseQt = unittest.TestCase


def esperar(condicion, limite=10000):
    reloj = QElapsedTimer()
    reloj.start()
    while not condicion():
        if reloj.elapsed() > limite:
            raise AssertionError("La apertura entre procesos no terminó")
        QTest.qWait(10)


def proceso(carpeta, modelo=None, modo="--cliente", trabajo=None):
    p = QProcess()
    if trabajo:
        p.setWorkingDirectory(str(trabajo))
    p.start(sys.executable, [str(Path(__file__).resolve()), modo, str(carpeta), json.dumps(modelo)])
    if not p.waitForStarted(3000):
        raise AssertionError(p.errorString())
    return p


def terminar(p):
    if p.state() != QProcess.ProcessState.NotRunning:
        p.kill()
        p.waitForFinished(3000)


def resultado(p):
    esperar(lambda: p.state() == QProcess.ProcessState.NotRunning)
    error = bytes(p.readAllStandardError()).decode("utf-8", errors="replace")
    texto = bytes(p.readAllStandardOutput()).decode("utf-8", errors="replace")
    if p.exitCode() != 0:
        raise AssertionError((p.exitCode(), texto, error))
    return json.loads(texto.strip().splitlines()[-1])


@unittest.skipUnless(QT, "requiere PySide6")
class Protocolo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name) / "ipc"
        self.duena = InstanciaUnica(self.app, self.carpeta)
        self.addCleanup(self.duena.cerrar)
        self.assertTrue(self.duena.iniciar())
        self.w = QWidget()
        self.addCleanup(self.w.deleteLater)
        self.pedidos = []
        self.w.nuevo = lambda: self.pedidos.append(None)
        self.w.abrir_ruta = lambda p: self.pedidos.append(p)
        self.w.cargar_ejemplo = lambda key: self.pedidos.append(key)
        self.duena.vincular(self.w)

    def cliente(self, modelo=None, modo="--cliente", trabajo=None):
        p = proceso(self.carpeta, modelo, modo, trabajo)
        self.addCleanup(terminar, p)
        return p

    def test_SIU01_segundo_arranque_reutiliza_la_ventana_sin_crear_otra(self):
        p = self.cliente()
        self.assertEqual(resultado(p), {"codigo": 0, "ventanas_creadas": 0})
        self.assertEqual(self.pedidos, [None])
        self.assertTrue(self.duena.servidor.isListening())

    def test_SIU02_ruta_relativa_con_espacios_y_unicode_se_resuelve_en_el_cliente(self):
        trabajo = Path(self.tmp.name) / "segundo"
        trabajo.mkdir()
        nombre = "proyecto con eñe.grafnet"
        p = self.cliente(nombre, trabajo=trabajo)
        resultado(p)
        self.assertEqual(self.pedidos, [(trabajo / nombre).resolve()])

    def test_SIU03_dos_peticiones_no_entran_a_la_vez_durante_un_dialogo(self):
        profundidad = []
        activos = 0
        segundo = []

        def abrir():
            nonlocal activos
            activos += 1
            profundidad.append(activos)
            self.pedidos.append(None)
            if len(self.pedidos) == 1:
                segundo.append(self.cliente())
                bucle = QEventLoop()
                QTimer.singleShot(500, bucle.quit)
                bucle.exec()
            activos -= 1

        self.w.nuevo = abrir
        primero = self.cliente()
        resultado(primero)
        resultado(segundo[0])
        self.assertEqual(self.pedidos, [None, None])
        self.assertEqual(profundidad, [1, 1])

    def test_SIU04_cierre_normal_libera_la_reserva(self):
        self.duena.cerrar()
        otra = InstanciaUnica(self.app, self.carpeta)
        self.addCleanup(otra.cerrar)
        self.assertTrue(otra.iniciar())

    def test_SIU05_reserva_abandonada_se_recupera_si_el_proceso_muere(self):
        self.duena.cerrar()
        p = self.cliente(modo="--propietaria")
        esperar(lambda: p.canReadLine())
        self.assertTrue(json.loads(bytes(p.readLine()).decode("utf-8"))["lista"])
        terminar(p)
        otra = InstanciaUnica(self.app, self.carpeta)
        self.addCleanup(otra.cerrar)
        self.assertTrue(otra.iniciar())

    def test_SIU06_mensaje_invalido_no_cambia_el_proyecto(self):
        s = QLocalSocket()
        self.addCleanup(s.abort)
        s.connectToServer(self.duena.nombre)
        esperar(lambda: s.state() == QLocalSocket.LocalSocketState.ConnectedState)
        s.write(b"{mal formado}\n")
        s.flush()
        esperar(s.canReadLine)
        self.assertEqual(json.loads(bytes(s.readLine())), {"estado": "rechazado"})
        self.assertEqual(self.pedidos, [])

    def test_SIU13_propietaria_cierra_con_apertura_pendiente_y_la_siguiente_la_recupera(self):
        self.duena.ventana = None
        p = self.cliente(modo="--relevo")
        esperar(lambda: len(self.duena.cola) == 1)
        self.duena.cerrar()
        self.assertEqual(resultado(p), {"primaria": True, "codigo": 0})

    def test_SIU14_argumento_ejemplo_se_conserva_en_la_ventana_abierta(self):
        from grafcet.examples import EJEMPLOS
        key = next(iter(EJEMPLOS))
        p = self.cliente(key, modo="--ejemplo")
        self.assertEqual(resultado(p), {"codigo": 0, "ventanas_creadas": 0})
        self.assertEqual(self.pedidos, [key])

    def test_SIU15_dos_arranques_simultaneos_eligen_una_sola_propietaria(self):
        self.duena.cerrar()
        a = self.cliente(modo="--competir")
        b = self.cliente(modo="--competir")
        esperar(lambda: a.canReadLine() and b.canReadLine())
        valores = [json.loads(bytes(p.readLine()).decode("utf-8"))["primaria"] for p in (a, b)]
        self.assertEqual(sorted(valores), [False, True])
        terminar(a)
        terminar(b)

    def test_SIU07_modal_existente_se_resuelve_antes_de_abrir(self):
        modal = QWidget(self.w)
        modal.setWindowModality(Qt.WindowModality.ApplicationModal)
        modal.setWindowFlags(Qt.WindowType.Dialog)
        self.addCleanup(modal.close)
        modal.show()
        p = self.cliente()
        QTest.qWait(250)
        self.assertEqual(self.pedidos, [])
        modal.close()
        resultado(p)
        self.assertEqual(self.pedidos, [None])


@unittest.skipUnless(QT, "requiere PySide6")
class Guardado(BaseQt):
    def setUp(self):
        super().setUp()
        self.carpeta = Path(self.tmp.name) / "ipc"
        self.duena = InstanciaUnica(self.app, self.carpeta)
        self.addCleanup(self.duena.cerrar)
        self.assertTrue(self.duena.iniciar())
        w, e = self.vacio()
        e.poner_etapa(QPointF(100, 100))
        self.e = e
        self.duena.vincular(w)
        w.show()
        self.addCleanup(w.hide)
        self.pasar_arranque(w)
        self.asentar_escala(w)

    def tearDown(self):
        self.duena.cerrar()
        super().tearDown()

    def nueva_apertura(self, decision, guardar=None, modelo=None):
        contexto = mock.patch.object(self.w, "guardar", side_effect=guardar) if guardar else mock.patch.object(
            self.w, "guardar", return_value=False)
        with mock.patch("escritorio.ventana.QMessageBox.question", return_value=decision) as pregunta, contexto as g:
            p = proceso(self.carpeta, modelo)
            self.addCleanup(terminar, p)
            r = resultado(p)
        self.assertEqual(r, {"codigo": 0, "ventanas_creadas": 0})
        pregunta.assert_called_once()
        return g

    def test_SIU16_dialogo_real_en_espanol_y_cancelar_conserva_el_proyecto(self):
        from escritorio.idioma import BotonesEspanol, NOMBRE, instalar
        instalar()
        instalar()
        self.assertEqual(len(self.app.findChildren(BotonesEspanol, NOMBRE)), 1)
        textos = []

        def pulsar():
            d = QApplication.activeModalWidget()
            if not isinstance(d, QMessageBox):
                QTimer.singleShot(20, pulsar)
                return
            botones = (QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Discard,
                       QMessageBox.StandardButton.Cancel)
            textos.extend(d.button(b).text() for b in botones)
            d.button(QMessageBox.StandardButton.Cancel).click()

        QTimer.singleShot(50, pulsar)
        p = proceso(self.carpeta)
        self.addCleanup(terminar, p)
        self.assertEqual(resultado(p), {"codigo": 0, "ventanas_creadas": 0})
        self.assertEqual(textos, ["Guardar", "Descartar", "Cancelar"])
        self.assertIs(self.w.edicion, self.e)
        self.assertTrue(self.e.ed.dirty)

    def test_SIU08_cancelar_conserva_proyecto_y_cambios(self):
        antes = copy.deepcopy(self.e.ed.model)
        g = self.nueva_apertura(QMessageBox.StandardButton.Cancel)
        self.assertIs(self.w.edicion, self.e)
        self.assertEqual(self.e.ed.model, antes)
        self.assertTrue(self.e.ed.dirty)
        g.assert_not_called()

    def test_SIU09_descartar_abre_un_proyecto_nuevo_en_la_misma_ventana(self):
        g = self.nueva_apertura(QMessageBox.StandardButton.Discard)
        self.assertIsNot(self.w.edicion, self.e)
        self.assertEqual(self.w.edicion.ed.model["steps"], [])
        g.assert_not_called()

    def test_SIU10_guardar_conserva_archivo_y_abre_nuevo(self):
        ruta = Path(self.tmp.name) / "anterior.grafnet"
        g = self.nueva_apertura(QMessageBox.StandardButton.Save, lambda: self.w._guardar_archivo(ruta))
        g.assert_called_once()
        self.assertTrue(ruta.is_file())
        self.assertIsNot(self.w.edicion, self.e)
        self.assertTrue(self.w.abrir_ruta(ruta))
        self.assertEqual(len(self.w.edicion.ed.model["steps"]), 1)

    def test_SIU11_si_guardar_falla_no_se_sustituye_el_proyecto(self):
        g = self.nueva_apertura(QMessageBox.StandardButton.Save)
        g.assert_called_once()
        self.assertIs(self.w.edicion, self.e)
        self.assertTrue(self.e.ed.dirty)

    def test_SIU12_archivo_solicitado_se_abre_tras_descartar(self):
        ruta = Path(self.tmp.name) / "solicitado.grafnet"
        self.assertTrue(self.w._guardar_archivo(ruta))
        self.e.poner_etapa(QPointF(100, 200))
        self.assertEqual(len(self.e.ed.model["steps"]), 2)
        self.nueva_apertura(QMessageBox.StandardButton.Discard, modelo=str(ruta))
        self.assertIsNot(self.w.edicion, self.e)
        self.assertEqual(len(self.w.edicion.ed.model["steps"]), 1)
        self.assertEqual(Path(self.w.edicion.archivo), ruta)


def cliente_prueba():
    app = QApplication.instance() or QApplication([])
    carpeta = Path(sys.argv[2])
    modelo = json.loads(sys.argv[3])
    if sys.argv[1] == "--relevo":
        with InstanciaUnica(app, carpeta) as duena:
            primaria = duena.iniciar(modelo)
            print(json.dumps({"primaria": primaria, "codigo": duena.codigo}), flush=True)
        return duena.codigo
    if sys.argv[1] == "--competir":
        with InstanciaUnica(app, carpeta) as duena:
            primaria = duena.iniciar()
            if primaria:
                w = QWidget()
                w.nuevo = lambda: None
                duena.vincular(w)
            print(json.dumps({"primaria": primaria}), flush=True)
            return app.exec() if primaria else duena.codigo
    if sys.argv[1] == "--propietaria":
        duena = InstanciaUnica(app, carpeta)
        print(json.dumps({"lista": duena.iniciar()}), flush=True)
        return app.exec()
    from escritorio import ventana
    with mock.patch("escritorio.instancia_unica.directorio_instancia", return_value=carpeta), \
            mock.patch.object(ventana, "Ventana", side_effect=AssertionError("No debe crear otra ventana")) as crear:
        argumentos = ["--ejemplo", modelo] if sys.argv[1] == "--ejemplo" else ([modelo] if modelo else [])
        codigo = ventana.main(argumentos)
    print(json.dumps({"codigo": codigo, "ventanas_creadas": crear.call_count}), flush=True)
    return codigo


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--cliente", "--propietaria", "--relevo", "--ejemplo", "--competir"):
        sys.exit(cliente_prueba())
    unittest.main()
