"""Avisos y errores de la conexión con el simulador de procesos: Decimal como numérica, Entera con escala y mensajes legibles."""
import os
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from helpers import M, session
from conexion.adaptador import Adaptador, ErrorConversion, texto_numero
from conexion.configuracion import Configuracion, Senal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    from escritorio.entradas_salidas import PanelES, aviso_escala
    QT = True
except ImportError:
    QT = False

DECIMAL = {"kind": "decimal", "scale": 2}


class MensajesConversion(unittest.TestCase):
    def test_SFIO70_texto_numero_con_coma_espanola(self):
        """REQ-ROB-01: los números de los mensajes llevan coma decimal y sin ceros de más."""
        self.assertEqual(texto_numero(Fraction(13, 10)), "1,3")
        self.assertEqual(texto_numero(Fraction(2345, 1000)), "2,345")
        self.assertEqual(texto_numero(Fraction(40)), "40")
        self.assertEqual(texto_numero(-Fraction(1, 100)), "-0,01")

    def test_SFIO71_entrada_entera_con_decimales_se_redondea_y_se_anota(self):
        """REQ-ROB-01, REQ-EXP-01: una Entera que recibe 1,3 (130 con escala 100) usa 1, sin error, y el redondeo queda
        anotado con lo recibido y lo usado; mitades lejos de cero, también con INT16 negativo."""
        m = M().var("nivel", kind="int").step("E0", True)
        a = Adaptador(Configuracion(senales=[Senal("nivel", "input-register", 0, "INT16", "100")]), session(m.compile()))
        for raw, esperado in ((130, 1), (150, 2), (249, 2), (65536 - 150, -2), (65536 - 130, -1), (200, 2)):
            a.aplicar({"nivel": raw})
            self.assertEqual(a.sesion.z.values["nivel"], esperado, raw)
        a.aplicar({"nivel": 65536 - 150})
        self.assertEqual(a.redondeos["nivel"], (Fraction(-3, 2), -2))
        a.aplicar({"nivel": 130})
        self.assertEqual(a.redondeos["nivel"], (Fraction(13, 10), 1))

    def test_SFIO71b_entera_sin_decimales_no_anota_y_la_conexion_sigue_en_estado_conectado(self):
        """REQ-ROB-01: una Entera con escala 1 no anota redondeos; con escala 100 y decimales no hay error."""
        m = M().var("nivel", kind="int").step("E0", True)
        a = Adaptador(Configuracion(senales=[Senal("nivel", "input-register", 0, "INT16", "1")]), session(m.compile()))
        a.aplicar({"nivel": 7})
        self.assertEqual(a.sesion.z.values["nivel"], 7)
        self.assertEqual(a.redondeos, {})
        cfg = Configuracion(senales=[Senal("nivel", "input-register", 0, "INT16", "100")])
        a2 = Adaptador(cfg, session(m.compile()))
        a2.aplicar({"nivel": 130})  # no lanza ErrorConversion: el coordinador no pasa a error
        self.assertEqual(a2.sesion.status, "pausada-estable")

    def test_SFIO72_entrada_decimal_con_mas_decimales_de_los_declarados(self):
        """REQ-EXP-01: un Decimal de 2 decimales que recibe 1,234 lo dice con el nombre de la variable."""
        m = M().var("temp", kind="decimal", scale=2).step("E0", True)
        a = Adaptador(Configuracion(senales=[Senal("temp", "input-register", 0, "INT16", "1000")]), session(m.compile()))
        with self.assertRaises(ErrorConversion) as ctx:
            a.aplicar({"temp": 1234})
        self.assertIn("La entrada «temp» es Decimal (2 decimales), pero el simulador de procesos ha enviado 1,234.", str(ctx.exception))

    def test_SFIO73_salida_no_representable_nombra_la_variable(self):
        """REQ-EXP-01: una salida con más decimales que el registro, o fuera de su rango, lo dice con el nombre."""
        m = M().var("pos", "output", kind="decimal", scale=3).step("E0", True)
        cfg = Configuracion(senales=[Senal("pos", "holding", 0, "INT16", "100")])
        a = Adaptador(cfg, session(m.compile()))
        a.sesion.z.values["pos"] = Fraction(2345, 1000)
        with self.assertRaises(ErrorConversion) as ctx:
            a.valores_salida()
        self.assertTrue(str(ctx.exception).startswith("La salida «pos» vale 2,345 y el registro del simulador de procesos solo admite "
                                                      "2 decimales"), str(ctx.exception))
        a.sesion.z.values["pos"] = Fraction(400)
        with self.assertRaises(ErrorConversion) as ctx:
            a.valores_salida()
        self.assertIn("La salida «pos» vale 400 y se sale del rango del registro (de -327,68 a 327,67).", str(ctx.exception))

    def test_SFIO74_muestra_incompleta_y_mensajes_de_red_sin_codigos(self):
        """REQ-ROB-01: la muestra incompleta y los fallos de red se explican sin códigos ni jerga."""
        from conexion.coordinador import explicar_fallo
        from conexion.modbus import ErrorModbus
        m = M().var("a").step("E0", True)
        a = Adaptador(Configuracion(senales=[Senal("a", "discrete", 0)]), session(m.compile()))
        with self.assertRaises(ErrorConversion):
            a.aplicar({})
        for causa in (ConnectionRefusedError(10061, "x", None, 10061), ConnectionResetError(10054, "x", None, 10054),
                      TimeoutError("t")):
            error = ErrorModbus(str(causa))
            error.__cause__ = causa
            self.assertNotIn("WinError", explicar_fallo(error))
            self.assertIn("El simulador de procesos", explicar_fallo(error))

    def test_SFIO75_el_error_de_conversion_llega_al_estado_del_coordinador(self):
        """REQ-ROB-01: lo que sube hasta el estado es el texto del alumno, no uno genérico ni con «Detalle»."""
        from conexion.coordinador import Coordinador
        texto = ("La entrada «temp» es Decimal (2 decimales), pero el simulador de procesos ha enviado 1,234. "
                 "Aumente los decimales de la variable en Variables.")
        mensaje = Coordinador._mensaje_de_error(ErrorConversion(texto), texto.rstrip("."))
        self.assertTrue(mensaje.startswith(texto[:-1]), mensaje)
        self.assertNotIn("Detalle", mensaje)


@unittest.skipUnless(QT, "Falta PySide6")
class PanelAvisos(unittest.TestCase):
    def test_SFIO76_decimal_se_coloca_solo_igual_que_entera(self):
        """REQ-EDT-07, REQ-SIM-03: Entera y Decimal, entrada o salida, van al primer registro libre; una booleana que pasa a
        Decimal se recoloca sola en un registro, sin aviso de quitada."""
        from escritorio.ventana import Ventana
        from PySide6.QtCore import QSettings
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w = Ventana(QSettings(str(Path(tmp) / "a.ini"), QSettings.Format.IniFormat))
            try:
                w.nuevo()
                e = w.edicion
                for nombre, papel, tipo in (("ent", "input", {"kind": "int"}), ("dec", "input", DECIMAL),
                                            ("sal_e", "output", {"kind": "int"}), ("sal_d", "output", DECIMAL),
                                            ("b", "input", None)):
                    self.assertIsNone(e.nueva_variable(nombre, papel, tipo))
                nombres = {v["id"]: v["name"] for v in e.ed.model["variables"]}
                mapa = {nombres[s.variable]: (s.area, s.direccion, s.escala) for s in w.panel_es.config.senales}
                self.assertEqual(mapa, {"ent": ("input-register", 0, "100"), "dec": ("input-register", 1, "100"),
                                        "sal_e": ("holding", 0, "100"), "sal_d": ("holding", 1, "100"),
                                        "b": ("discrete", 0, "1")})
                vid = next(i for i, n in nombres.items() if n == "b")
                self.assertIsNone(e.cambiar_variable(vid, type=DECIMAL))
                w._sincronizar_es()
                mapa = {nombres[s.variable]: (s.area, s.direccion) for s in w.panel_es.config.senales}
                self.assertEqual(mapa["b"], ("input-register", 2))
                self.assertNotIn("«b»", w.panel_es.estado.text())
            finally:
                w.edicion.ed.dirty = False
                w.close()
                w.deleteLater()
                app.processEvents()

    def test_SFIO77_aviso_ambar_de_entera_con_escala_distinta_de_uno(self):
        """REQ-SIM-03, REQ-ROB-01: una Entera en un registro con escala 100 lleva un aviso junto a su fila y en la nota; una
        Decimal, una Entera con escala 1 y las booleanas, no."""
        app = QApplication.instance() or QApplication([])
        doc = (M().var("nivel", kind="int").var("temp", kind="decimal", scale=2).var("v", "output", kind="int")
               .var("a").step("E0", True).doc)
        canales = {"discrete": {"offset": 0, "cantidad": 8}, "coil": {"offset": 0, "cantidad": 8},
                   "input-register": {"offset": 0, "cantidad": 4}, "holding": {"offset": 0, "cantidad": 4}}
        panel = PanelES()
        panel.cargar(doc, Configuracion(modelo=doc["id"], canales=canales, senales=[
            Senal("nivel", "input-register", 0, "INT16", "100"), Senal("temp", "input-register", 1, "INT16", "100"),
            Senal("v", "holding", 0, "INT16", "1"), Senal("a", "discrete", 0)]))
        t = panel.terminales
        self.assertIn("se redondeará al entero más cercano", t[("input-register", 0)].aviso)
        self.assertIn("Decimal (2 decimales)", t[("input-register", 0)].aviso)
        self.assertIsNotNone(t[("input-register", 0)].marca)
        for clave in (("input-register", 1), ("holding", 0), ("discrete", 0)):
            self.assertEqual(t[clave].aviso, "", clave)
            self.assertIsNone(t[clave].marca, clave)
        self.assertIn("«nivel»", panel.avisos_escala)
        self.assertNotIn("«temp»", panel.avisos_escala)
        self.assertEqual(aviso_escala(doc["variables"][0], Senal("nivel", "input-register", 0, "INT16", "1")), "")
        app.processEvents()

    def test_SFIO78b_el_aviso_de_escala_solo_es_para_lo_que_el_programa_recibe(self):
        """REQ-SIM-03: una Entera de salida enviada con escala 100 (5 → 500) no pierde nada y no avisa; una Entera de entrada con
        escala 100 sí."""
        doc = M().var("nivel", kind="int").var("v", "output", kind="int").step("E0", True).doc
        entrada, salida = doc["variables"]
        self.assertEqual(aviso_escala(salida, Senal("v", "holding", 0, "INT16", "100")), "")
        self.assertIn("se redondeará", aviso_escala(entrada, Senal("nivel", "input-register", 0, "INT16", "100")))

    def test_SFIO79_el_redondeo_recibido_marca_la_variable_en_ambar_con_lo_recibido_y_lo_usado(self):
        """REQ-SIM-03, REQ-ROB-01: tras un redondeo la fila de la Entera lleva el aviso con lo recibido y lo usado; sin
        redondeos (otra conexión) vuelve al aviso preventivo o a ninguno."""
        app = QApplication.instance() or QApplication([])
        doc = M().var("nivel", kind="int").var("n2", kind="int").step("E0", True).doc
        canales = {"discrete": {"offset": 0, "cantidad": 2}, "coil": {"offset": 0, "cantidad": 2},
                   "input-register": {"offset": 0, "cantidad": 2}, "holding": {"offset": 0, "cantidad": 2}}
        panel = PanelES()
        panel.cargar(doc, Configuracion(modelo=doc["id"], canales=canales, senales=[
            Senal("nivel", "input-register", 0, "INT16", "1"), Senal("n2", "input-register", 1, "INT16", "100")]))
        t = panel.terminales
        self.assertIsNone(t[("input-register", 0)].marca)
        panel.mostrar_redondeos({"nivel": (Fraction(13, 10), 1)})
        marca = t[("input-register", 0)].marca
        self.assertIsNotNone(marca)
        self.assertTrue(marca.isVisibleTo(panel) or not marca.isHidden())
        self.assertEqual(marca.toolTip(), "El simulador de procesos ha enviado 1,3 y la variable es Entera: se usa 1. "
                                          "Para el valor exacto, póngala como Decimal (2 decimales).")
        panel.mostrar_redondeos({})
        self.assertTrue(t[("input-register", 0)].marca.isHidden())
        self.assertIn("se redondeará", t[("input-register", 1)].marca.toolTip())
        app.processEvents()

    def test_SFIO78_la_linea_de_sondeo_y_ciclo_no_se_ve(self):
        """REQ-SIM-03: la medida de sondeo y ciclo se conserva (texto y tooltip) pero la línea queda oculta."""
        app = QApplication.instance() or QApplication([])
        panel = PanelES()
        panel.mostrar_tiempos({"sondeo_ms": 5.7, "ciclo_ms": 2.0, "ciclo_max_ms": 20.3})
        self.assertTrue(panel.tiempos.isHidden())
        self.assertEqual(panel.tiempos.text(), "Sondeo 5,7 ms · Ciclo 2,0 ms · máx. 20,3 ms")
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
