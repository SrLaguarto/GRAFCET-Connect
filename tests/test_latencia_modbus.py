"""Latencia de comunicación con servidor local y eventos Qt reales."""
import os
import threading
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from conexion.configuracion import Configuracion, Senal
from conexion.coordinador import Coordinador
from helpers import M, session
from test_modbus import servidor
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings
    from escritorio.ventana import Ventana
    QT = True
except ImportError:
    QT = False


class ComunicacionTests(unittest.TestCase):
    def test_SRED01_aviso_no_ejecuta_motor_en_trabajador(self):
        """REQ-SIM-03: la red notifica; solo el propietario aplica la muestra."""
        aviso = threading.Event()
        c = Coordinador(aviso.set)
        try:
            c._enviar("prueba", lambda: 42)
            self.assertTrue(aviso.wait(1))
            self.assertEqual(c.futuro.result(), 42)
            self.assertEqual(c.estado, "desconectado")
            self.assertEqual(c.muestra, {})
        finally:
            c.cerrar()

    def test_SRED02_periodo_nuevo_y_explicito(self):
        """REQ-SIM-03: periodo inicial de 20 ms sin alterar valores explícitos."""
        self.assertEqual(Configuracion().periodo_ms, 20)
        self.assertEqual(Configuracion(periodo_ms=50).periodo_ms, 50)
        self.assertEqual(Configuracion(periodo_ms=80).periodo_ms, 80)

    def test_SRED06_periodos_cortos_guardar_y_abrir(self):
        """REQ-SIM-03, REQ-DAT-02: 5 y 10 ms se validan y guardan sin cambiar el valor inicial."""
        doc=M().var("sensor").step("0",True).doc
        with tempfile.TemporaryDirectory() as tmp:
            ruta=Path(tmp)/"conexion.json"
            for periodo in (5,10,20,50,10000):
                with self.subTest(periodo=periodo):
                    c=Configuracion(periodo_ms=periodo)
                    c.guardar(ruta,doc)
                    self.assertEqual(Configuracion.cargar(ruta,doc).periodo_ms,periodo)
        for periodo in (0,1,4,10001,5.0,True):
            with self.subTest(periodo=periodo),self.assertRaises(ValueError):
                Configuracion(periodo_ms=periodo).validar(doc)
        self.assertEqual(Configuracion().periodo_ms,20)

    def test_SRED07_planificacion_con_fracciones_de_milisegundo(self):
        """REQ-SIM-03: un sondeo de 5 ms usa plazos del reloj de alta resolución."""
        from types import SimpleNamespace
        c=Coordinador()
        try:
            c.estado="conectado"
            c.adaptador=SimpleNamespace(sesion=None,config=Configuracion(periodo_ms=5),entradas=[])
            with patch.object(c,"_enviar") as enviar,patch("conexion.coordinador.perf_counter",return_value=1000.0) as reloj:
                c.tick(False)
                self.assertAlmostEqual(c.proxima,1000.005)
                self.assertEqual(enviar.call_count,1)
                reloj.return_value=1000.0049
                c.tick(False);self.assertEqual(enviar.call_count,1)
                reloj.return_value=1000.005
                c.tick(False);self.assertEqual(enviar.call_count,2)
        finally:
            c.adaptador=None
            c.cerrar()

    def test_SRED16_parada_por_ambos_haces_con_marcha_por_pulso(self):
        """REQ-SIM-03: el ensayo de dos etapas se para al recibirse ambos haces, con Marcha ya liberada."""
        from conexion.adaptador import Adaptador
        from grafcet.profile import normalize_options
        m=M().var("marcha").var("automatico").var("bajo").var("pale").var("cinta","output")
        m.step("0",True).step("1")
        m.trans("arranque",["0"],["1"],"automatico OR NOT automatico AND marcha")
        m.trans("parada",["1"],["0"],"bajo AND pale").cont("1","cinta")
        cfg=Configuracion(periodo_ms=5,senales=[Senal(n,"discrete",i) for i,n in enumerate(("marcha","automatico","bajo","pale"))]+[Senal("cinta","coil",0)])
        a=Adaptador(cfg,session(m.compile(),options=normalize_options(None)))
        muestra=dict.fromkeys(("marcha","automatico","bajo","pale"),False)
        muestra["marcha"]=True;a.aplicar(muestra);self.assertTrue(a.valores_salida()["cinta"])
        muestra["marcha"]=False;a.aplicar(muestra)
        muestra["bajo"]=True;a.aplicar(muestra);self.assertTrue(a.valores_salida()["cinta"])
        muestra["pale"]=True;a.aplicar(muestra)
        self.assertFalse(a.valores_salida()["cinta"])
        self.assertEqual(a.sesion.status,"pausada-estable")
        self.assertEqual(a.sesion.z.situation,frozenset(["0"]))


@unittest.skipUnless(QT, "Falta PySide6")
class LatenciaQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def esperar(self, condicion, segundos=2):
        fin = time.monotonic() + segundos
        while not condicion():
            self.app.processEvents()
            if time.monotonic() >= fin:
                self.fail("No llegó la respuesta Modbus: " + self.w.modbus.mensaje)
            time.sleep(.001)

    def abrir(self, tmp, sc, periodo):
        self.w = w = Ventana(QSettings(str(Path(tmp) / "ajustes.ini"), QSettings.Format.IniFormat))
        m = M().var("sensor").var("motor", "output").step("E0", True)
        m.cont("E0", "motor", "sensor")
        w.fuente = {"tipo": "fichero", "ruta": Path(tmp) / "modelo.json", "doc": m.doc,
                    "layout": {}, "titulo": "Latencia", "ayuda": "", "raiz": None}
        w._cargar()
        w.panel_es.cargar(m.doc, Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=periodo,
            senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)]))
        w._conectar_modbus()
        self.esperar(lambda: w.modbus.estado == "conectado" and w.modbus.futuro is None)
        return w

    def cerrar(self):
        w = self.w
        if w.edicion is not None:
            w.edicion.ed.dirty = False
        w.close()
        w.deleteLater()
        self.app.processEvents()

    def test_SRED03_respuesta_inmediata_sin_tick_periodico(self):
        """REQ-SIM-02, REQ-SIM-03: leer, evolucionar y escribir por respuesta, sin esperar al periodo."""
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p: b"\x02\x01\x01" if p[0] == 2 else p[:5]) as sc:
            w = self.abrir(tmp, sc, 2000)
            try:
                w.a_ejecutar.setChecked(True)
                w.rt.stop()
                w._tick()  # termina el descarte de la sesión anterior
                w.modbus.proxima = 0
                hilos = []
                aplicar = w.modbus.adaptador.aplicar
                def registrar(muestra):
                    hilos.append(threading.get_ident())
                    return aplicar(muestra)
                with patch.object(w.modbus.adaptador, "aplicar", registrar), patch.object(w, "refrescar") as dibujar:
                    w._ultimo_refresco_modbus = time.perf_counter()
                    w._tick()  # envía lectura; el resto lo hacen las respuestas
                    w._proxima_lectura.stop()
                    self.esperar(lambda: w.modbus.escritos.get("motor") is True, 1)
                    self.assertEqual(hilos, [threading.get_ident()])
                    self.assertLessEqual(dibujar.call_count, 1)
                self.assertTrue(w.v.s.z.values["sensor"])
                for clave in ("leer_red_ms", "leer_espera_ms", "evolucion_ms", "escribir_red_ms", "ciclo_ms"):
                    self.assertGreaterEqual(w.modbus.medidas[clave], 0)
                self.assertGreaterEqual(w.modbus.medidas["ciclo_ms"], w.modbus.medidas["leer_red_ms"])
                w.a_ejecutar.setChecked(False)
                w.rt.stop()
                self.esperar(lambda: w.modbus.escritos.get("motor") is False, 1)
                print("\nMedidas locales (ms):", {k: round(v, 3) for k, v in w.modbus.medidas.items()})
            finally:
                self.cerrar()

    def test_SRED04_siguiente_lectura_y_stop_sin_refresco_periodico(self):
        """REQ-SIM-02, REQ-SIM-03: sondeo autónomo y Stop a cero con el reloj periódico parado."""
        sensor = [True]
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p: bytes([2, 1, int(sensor[0])]) if p[0] == 2 else p[:5]) as sc:
            w = self.abrir(tmp, sc, 20)
            try:
                w.a_ejecutar.setChecked(True)
                w.rt.stop()
                w._tick()
                self.esperar(lambda: w.modbus.escritos.get("motor") is True)
                sensor[0] = False
                self.esperar(lambda: w.modbus.escritos.get("motor") is False)
                self.assertFalse(w.v.s.z.values["sensor"])
                sensor[0] = True
                self.esperar(lambda: w.modbus.escritos.get("motor") is True)
                w.a_ejecutar.setChecked(False)
                w.rt.stop()
                self.esperar(lambda: w.modbus.escritos.get("motor") is False)
                self.assertIsNone(w.v.s.z)
                self.assertTrue(w.modbus.activo)
            finally:
                self.cerrar()

    def test_SRED05_reloj_conserva_fracciones(self):
        """REQ-TMP-02: callbacks frecuentes conservan el tiempo inferior al milisegundo."""
        with tempfile.TemporaryDirectory() as tmp:
            self.w = w = Ventana(QSettings(str(Path(tmp) / "ajustes.ini"), QSettings.Format.IniFormat))
            try:
                w.edicion.ed.add_step("g","0",True);w.edicion.cambia();w._preparar_sesion()
                w._iniciar_reloj()
                class Reloj:
                    marca = 0
                    def isValid(self): return True
                    def nsecsElapsed(self): return self.marca
                reloj = Reloj()
                w.reloj = reloj
                w._marca_reloj_ns = w._resto_reloj_ns = 0
                with patch.object(w.a_ejecutar, "isChecked", return_value=True), patch.object(w, "_vigilar_motor", return_value=False), patch.object(w, "_act") as avanzar:
                    for _ in range(10):
                        reloj.marca += 150500
                        w._tick()
                    self.assertEqual(sum(c.kwargs["us"] for c in avanzar.call_args_list), 1505)
                    self.assertEqual(w._resto_reloj_ns, 0)
            finally:
                self.cerrar()

    def test_SRED08_selector_admite_5_y_10_ms(self):
        """REQ-SIM-03: el panel admite 5 y 10 ms y conserva esos valores al recargar."""
        with tempfile.TemporaryDirectory() as tmp:
            self.w=w=Ventana(QSettings(str(Path(tmp)/"ajustes.ini"),QSettings.Format.IniFormat))
            try:
                doc=M().var("sensor").step("0",True).doc
                self.assertEqual(w.panel_es.periodo.minimum(),5)
                for periodo in (5,10,50):
                    w.panel_es.cargar(doc,Configuracion(periodo_ms=periodo))
                    self.assertEqual(w.panel_es.periodo.value(),periodo)
                    self.assertEqual(w.panel_es.obtener().periodo_ms,periodo)
                w.panel_es.periodo.setValue(4)
                self.assertEqual(w.panel_es.periodo.value(),5)
            finally:self.cerrar()

    def test_SRED09_intercambio_real_a_5_y_10_ms(self):
        """REQ-SIM-02, REQ-SIM-03: intercambio TCP y cero de Stop con periodos cortos, sin prometer cadencia exacta."""
        import statistics
        for periodo in (5,10):
            marcas=[]
            def responder(p):
                if p[0]==2:
                    marcas.append(time.perf_counter())
                    return b"\x02\x01\x01"
                return p[:5]
            with self.subTest(periodo=periodo), tempfile.TemporaryDirectory() as tmp, servidor(responder) as sc:
                w=self.abrir(tmp,sc,periodo)
                try:
                    w.a_ejecutar.setChecked(True)
                    self.esperar(lambda:w.modbus.escritos.get("motor") is True)
                    marcas.clear()
                    self.esperar(lambda:len(marcas)>=40,5)
                    intervalos=[(b-a)*1000 for a,b in zip(marcas[3:],marcas[4:])]
                    self.assertTrue(all(t>0 for t in intervalos))
                    self.assertEqual(w.rt.interval(),periodo)
                    self.assertTrue(w.modbus.en_marcha)
                    self.assertFalse(w.modbus.fallo_motor)
                    ordenados=sorted(intervalos)
                    print(f"\nPeriodo {periodo} ms: intervalo local mediano {statistics.median(intervalos):.2f} ms; "
                          f"p95 {ordenados[int(.95*(len(ordenados)-1))]:.2f} ms; máximo {max(intervalos):.2f} ms")
                    w.a_ejecutar.setChecked(False)
                    self.esperar(lambda:w.modbus.escritos.get("motor") is False)
                finally:self.cerrar()

    def test_SRED10_desconectar_conserva_vista_es_en_play_y_stop(self):
        """REQ-SIM-03: desconectar por el botón detiene y pone a cero sin sacar al usuario de E/S."""
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        for ejecutar in (False,True):
            with self.subTest(ejecutar=ejecutar), tempfile.TemporaryDirectory() as tmp, servidor(lambda p:b"\x02\x01\x01" if p[0]==2 else p[:5]) as sc:
                w=self.abrir(tmp,sc,5)
                try:
                    if ejecutar:
                        w.a_ejecutar.setChecked(True)
                        self.esperar(lambda:w.modbus.escritos.get("motor") is True)
                    w.show();w._mostrar_pagina(True);self.app.processEvents()
                    QTest.mouseClick(w.panel_es.b_desconectar,Qt.MouseButton.LeftButton)
                    self.esperar(lambda:w.modbus.estado=="desconectado")
                    self.assertEqual(w.paginas_es.currentIndex(),1)
                    self.assertEqual(w.pestanas_vistas.currentIndex(),2)
                    self.assertTrue(w.a_es.isChecked())
                    self.assertFalse(w.a_ejecutar.isChecked())
                    self.assertFalse(w.a_ejecutar.isEnabled())
                    self.assertEqual(w.modbus.escritos,{"motor":False})
                finally:self.cerrar()

    def test_SRED11_tiempos_visibles_y_detalle(self):
        """REQ-SIM-03: se distinguen el sondeo real, el ciclo y la espera al aplicar la entrada."""
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p:b"\x02\x01\x01" if p[0]==2 else p[:5]) as sc:
            w=self.abrir(tmp,sc,5)
            try:
                w.a_ejecutar.setChecked(True)
                self.esperar(lambda:"sondeo_ms" in w.modbus.medidas and "ciclo_max_ms" in w.modbus.medidas)
                self.assertGreater(w.modbus.medidas["sondeo_ms"],0)
                self.assertGreaterEqual(w.modbus.medidas["sondeo_max_ms"],w.modbus.medidas["sondeo_ms"])
                self.assertGreaterEqual(w.modbus.medidas["ciclo_max_ms"],w.modbus.medidas["ciclo_ms"])
                w._ultimo_refresco_modbus=0;w._refrescar_modbus()
                self.assertTrue(w.panel_es.tiempos.isHidden())  # medida conservada, línea oculta
                self.assertIn("Ciclo",w.panel_es.tiempos.text())
                self.assertIn("máx.",w.panel_es.tiempos.text())
                self.assertIn("Intervalo real entre lecturas",w.panel_es.tiempos.toolTip())
                self.assertIn("Espera antes de aplicar la lectura",w.panel_es.tiempos.toolTip())
                w.panel_es.mostrar_tiempos({})
                self.assertTrue(w.panel_es.tiempos.isHidden())
            finally:self.cerrar()

    def test_SRED12_es_no_reconstruye_el_dibujo_oculto(self):
        """REQ-SIM-03: la vista E/S actualiza valores sin reconstruir el GRAFCET oculto."""
        sensor=[True]
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p:bytes([2,1,int(sensor[0])]) if p[0]==2 else p[:5]) as sc:
            w=self.abrir(tmp,sc,5)
            try:
                w.a_ejecutar.setChecked(True);self.esperar(lambda:w.modbus.escritos.get("motor") is True)
                w.refrescar();w._mostrar_pagina(True)
                with patch.object(w.diagrama,"mostrar",wraps=w.diagrama.mostrar) as dibujar,patch.object(w,"_variables",wraps=w._variables) as tablas,patch.object(w.panel_es,"mostrar_muestra",wraps=w.panel_es.mostrar_muestra) as muestra:
                    w._ultimo_refresco_modbus=0;w._refrescar_modbus()
                    dibujar.assert_not_called();tablas.assert_not_called();self.assertTrue(muestra.called)
                    sensor[0]=False;self.esperar(lambda:w.modbus.escritos.get("motor") is False)
                    w._ultimo_refresco_modbus=0;w._refrescar_modbus()
                    dibujar.assert_not_called();self.assertFalse(muestra.call_args.args[0]["sensor"])
                    w._mostrar_pagina(False)
                    self.assertTrue(dibujar.called);self.assertTrue(tablas.called)
                    self.assertFalse(w.diagrama._ultimo[1]["values"]["sensor"])
            finally:self.cerrar()

    def test_SRED13_reloj_solo_no_reconstruye_pero_un_cambio_si(self):
        """REQ-SIM-03: el reloj avanza sin recrear el dibujo idéntico; una entrada sí lo actualiza."""
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p:b"\x02\x01\x01" if p[0]==2 else p[:5]) as sc:
            w=self.abrir(tmp,sc,5)
            try:
                w.a_ejecutar.setChecked(True);self.esperar(lambda:w.modbus.escritos.get("motor") is True)
                w.rt.stop();w._proxima_lectura.stop()
                w.v.s.advance_to(w.v.s.z.time+1000);w.refrescar()
                with patch.object(w.diagrama,"mostrar",wraps=w.diagrama.mostrar) as dibujar:
                    w.v.s.advance_to(w.v.s.z.time+1000);w.refrescar()
                    dibujar.assert_not_called()
                    w.modbus.adaptador.aplicar({"sensor":False});w.refrescar()
                    self.assertEqual(dibujar.call_count,1)
                    self.assertFalse(w.diagrama._ultimo[1]["values"]["sensor"])
            finally:self.cerrar()

    def test_SRED14_temporizador_sigue_redibujando(self):
        """REQ-TMP-02, REQ-SIM-03: los cambios del tiempo mostrado invalidan la reutilización del dibujo."""
        with tempfile.TemporaryDirectory() as tmp:
            self.w=w=Ventana(QSettings(str(Path(tmp)/"a.ini"),QSettings.Format.IniFormat))
            try:
                m=M().var("sensor").var("motor","output").step("0",True)
                m.cont("0","motor","delay(1s, sensor, 0s)")
                w.fuente={"tipo":"fichero","ruta":Path(tmp)/"m.json","doc":m.doc,"layout":{},"titulo":"Temporizador","ayuda":"","raiz":None}
                w._cargar();w.a_ejecutar.setChecked(True);w.rt.stop()
                w.v.act("fijar",{"cambios":{"sensor":True}});w.refrescar()
                with patch.object(w.diagrama,"mostrar",wraps=w.diagrama.mostrar) as dibujar:
                    w.v.s.advance_to(w.v.s.z.time+100000);w.refrescar()
                    self.assertEqual(dibujar.call_count,1)
                    self.assertTrue(w.diagrama._ultimo[1]["temporal"])
            finally:self.cerrar()

    def test_SRED15_tablas_reutilizan_celdas_y_actualizan_valor_y_color(self):
        """REQ-SIM-03: actualizar valores conserva las celdas y cambia texto y color cuando corresponde."""
        from PySide6.QtWidgets import QTableWidget
        from escritorio.diagrama import COL
        tabla=QTableWidget(0,4)
        try:
            Ventana._filas(tabla,[("motor","salida continua","ON","etapa 1","ok")])
            celdas=[tabla.item(0,i) for i in range(4)]
            Ventana._filas(tabla,[("motor","salida continua","ON","etapa 1","ok")])
            for i,item in enumerate(celdas):self.assertIs(tabla.item(0,i),item)
            Ventana._filas(tabla,[("motor","salida continua","OFF","","muted")])
            self.assertIs(tabla.item(0,2),celdas[2]);self.assertEqual(celdas[2].text(),"OFF")
            self.assertEqual(celdas[2].foreground().color().name(),COL["muted"])
        finally:tabla.deleteLater();self.app.processEvents()

    def test_SRED17_ultima_parada_conserva_entradas_y_tiempos_de_ese_instante(self):
        """REQ-SIM-03: el diagnóstico conserva la entrada previa a la salida a cero, no una muestra posterior."""
        sensor=[True]
        with tempfile.TemporaryDirectory() as tmp, servidor(lambda p:bytes([2,1,int(sensor[0])]) if p[0]==2 else p[:5]) as sc:
            w=self.abrir(tmp,sc,5)
            try:
                self.assertIsNone(w.modbus.ultima_parada)
                w.a_ejecutar.setChecked(True);self.esperar(lambda:w.modbus.escritos.get("motor") is True)
                sensor[0]=False;self.esperar(lambda:w.modbus.ultima_parada is not None)
                parada=w.modbus.ultima_parada
                self.assertEqual(parada["salidas"],["motor"])
                self.assertEqual(parada["entradas"][-1]["valores"],{"sensor":False})
                self.assertGreaterEqual(parada["entradas"][-1]["antes_ms"],0)
                sensor[0]=True;self.esperar(lambda:w.modbus.escritos.get("motor") is True)
                self.assertIs(w.modbus.ultima_parada,parada)
                self.assertEqual(parada["entradas"][-1]["valores"],{"sensor":False})
                w._ultimo_refresco_modbus=0;w._refrescar_modbus()
                self.assertIn("Última salida desactivada por el GRAFCET: motor",w.panel_es.tiempos.toolTip())
                self.assertIn("sensor = 0",w.panel_es.tiempos.toolTip())
            finally:self.cerrar()
