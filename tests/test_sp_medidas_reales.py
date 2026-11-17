"""Medidas reales de P1/P2 con el estilo de la ventana, sin conexiones externas."""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QStyle, QStyleOptionComboBox, QStyleOptionFrame
    from tools import hoja_contactos as hc
    QT = True
except ImportError:
    QT = False

CAPTURAS = os.environ.get("P_CAPTURAS_MEDIDAS")


def guardar(widget, nombre, alto=None):
    if not CAPTURAS:
        return
    carpeta = Path(CAPTURAS)
    carpeta.mkdir(parents=True, exist_ok=True)
    imagen = widget.grab().toImage()
    if alto:
        imagen = imagen.copy(0, 0, imagen.width(), min(alto, imagen.height()))
    imagen.save(str(carpeta / (nombre + ".png")))
    imagen.scaled(imagen.width() * 3, imagen.height() * 3).save(str(carpeta / (nombre + "_x3.png")))


@unittest.skipUnless(QT, "requiere PySide6")
class MedidasRealesP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = hc.aplicacion()

    def comprobar_campos(self, ip, puerto, unidad):
        medidas = []
        for octeto in ip.cajas:
            texto = octeto.fontMetrics().horizontalAdvance("888")
            self.assertEqual(octeto.width(), texto + 10)
            self.assertEqual(octeto.alignment(), Qt.AlignmentFlag.AlignCenter)
            opcion = QStyleOptionFrame()
            octeto.initStyleOption(opcion)
            interior = octeto.style().subElementRect(QStyle.SubElement.SE_LineEditContents, opcion, octeto)
            self.assertGreaterEqual(interior.width() - 4, texto)
            octeto.setText("888")
            medidas.append({"campo": "octeto", "texto": texto, "ancho": octeto.width()})
        for nombre, spin in (("puerto", puerto), ("esclavo", unidad)):
            texto = spin.fontMetrics().horizontalAdvance("888")
            self.assertGreaterEqual(spin.width(), texto + 28)
            self.assertLessEqual(spin.width(), texto + 28 + 4)
            self.assertGreaterEqual(spin.lineEdit().width() - 4, texto)
            spin.lineEdit().setText("888")
            medidas.append({"campo": nombre, "texto": texto, "ancho": spin.width()})
        return medidas

    def comprobar_selector(self, selector):
        opcion = QStyleOptionComboBox()
        selector.initStyleOption(opcion)
        interior = selector.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, opcion, QStyle.SubControl.SC_ComboBoxEditField, selector)
        textos = [selector.itemText(i) for i in range(selector.count())]
        for texto in textos:
            self.assertNotIn("…", texto)
            self.assertGreaterEqual(interior.width(), selector.fontMetrics().horizontalAdvance(texto))
        selector.showPopup()
        hc._bombear(2)
        self.assertEqual(selector.view().textElideMode(), Qt.TextElideMode.ElideNone)
        for texto in textos:
            self.assertGreaterEqual(selector.view().viewport().width() - 8,
                                    selector.view().fontMetrics().horizontalAdvance(texto))
        return {"selector": selector.width(), "interior": interior.width(), "opciones": textos}

    def test_SP120_medidas_y_capturas_a_1366_y_media_pantalla(self):
        resultados = []
        for ancho in (1366, 683):
            with self.subTest(ancho=ancho):
                c = hc.Contexto(ancho, 768)
                try:
                    hc._edicion(c)
                    c.w.mostrar_es()
                    hc._bombear(2)
                    p = c.w.panel_es
                    self.assertEqual(p.config.modo, "directo")
                    p.directa.selector.setCurrentIndex(0)
                    hc._bombear(2)
                    guardar(p.lienzo, f"cabecera_{ancho}", 155)
                    cabecera = self.comprobar_campos(p.lienzo.ip, p.lienzo.puerto, p.lienzo.unidad)
                    guardar(p.lienzo, f"cabecera_888_{ancho}", 155)
                    p.dialogo_config.show()
                    hc._bombear(2)
                    guardar(p.dialogo_config, f"modbus_{ancho}")
                    dialogo = self.comprobar_campos(p.host, p.puerto, p.unidad)
                    guardar(p.dialogo_config, f"modbus_888_{ancho}")
                    p.dialogo_config.hide()
                    selector = self.comprobar_selector(p.directa.selector)
                    guardar(p.directa.selector.view().window(), f"lista_modos_{ancho}")
                    p.directa.selector.hidePopup()
                    guardar(p.directa.selector, f"modo_cerrado_{ancho}")
                    resultados.append(dict(ancho=ancho, cabecera=cabecera, dialogo=dialogo, **selector))
                finally:
                    c.cerrar()
        if CAPTURAS:
            (Path(CAPTURAS) / "medidas.json").write_text(
                json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_SP121_puerto_largo_conserva_rango_y_crece_sin_recorte(self):
        c = hc.Contexto(683, 768)
        try:
            c.mostrar()
            c.w.mostrar_es()
            p = c.w.panel_es
            p.directa.selector.setCurrentIndex(0)
            p.dialogo_config.show()
            hc._bombear(2)
            for spin in (p.puerto, p.lienzo.puerto):
                self.assertEqual(spin.maximum(), 65535)
                spin.setValue(65535)
                hc._bombear(2)
                self.assertGreaterEqual(spin.lineEdit().width() - 4,
                                        spin.fontMetrics().horizontalAdvance("65535"))
                spin.setValue(502)
                hc._bombear(2)
                self.assertEqual(spin.width(), spin.fontMetrics().horizontalAdvance("888") + 28)
        finally:
            c.cerrar()

    def test_SP122_guardado_sin_modo_sigue_en_modbus(self):
        from conexion.configuracion import Configuracion
        from grafcet.builder import M
        import tempfile
        doc = M().step("0", True).doc
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "conexion.json"
            Configuracion(modelo=doc["id"]).guardar(ruta, doc)
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            datos.pop("modo", None)
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            self.assertEqual(Configuracion.cargar(ruta, doc).modo, "modbus")

    def test_SP125_proyecto_vacio_nuevo_desde_modbus_usa_directo(self):
        c = hc.Contexto(1366, 768)
        try:
            c.mostrar()
            c.w.mostrar_es()
            self.assertEqual(c.w.panel_es.config.modo, "directo")
            c.w.panel_es.directa.selector.setCurrentIndex(0)
            c.w.edicion.ed.dirty = False
            c.w.nuevo()
            hc._bombear(2)
            self.assertEqual(c.w.panel_es.config.modo, "directo")
            c.w._mostrar_pagina(False)
            c.w.edicion.ed.dirty = False
            c.w.nuevo()
            c.w.mostrar_es()
            hc._bombear(2)
            self.assertEqual(c.w.panel_es.config.modo, "directo")
        finally:
            c.cerrar()

    def test_SP130_direcciones_ocupan_su_columna_sin_hueco_ni_excepcion(self):
        from test_auditoria_maquetacion import REGLAS
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            with self.subTest(ancho=ancho):
                c = hc.Contexto(ancho, alto)
                try:
                    hc._configuracion(c)
                    dialogo = c.w.panel_es.dialogo_config
                    for regla, comprobar in REGLAS.items():
                        if regla not in ("B1", "B2"):
                            self.assertEqual(comprobar(dialogo), [], regla)
                finally:
                    c.cerrar()

    def test_SP132_columna_sigue_al_numero_al_reducir_la_fuente(self):
        from test_auditoria_maquetacion import regla_C5, regla_TB1
        from escritorio.campos_medidos import notificar_fuentes
        from escritorio import estilo
        escala_anterior = estilo.ESCALA
        c = hc.Contexto(2000, 1250)
        try:
            hc._configuracion(c)
            p = c.w.panel_es
            campos = [p.tabla.cellWidget(row, 5) for row in range(p.tabla.rowCount())]
            for campo in campos:
                campo.setStyleSheet("font-size:32px")
            notificar_fuentes()
            p._anchos_controles()
            hc._bombear(4)
            grande = p.tabla.columnWidth(5)
            for campo in campos:
                campo.setStyleSheet("")
            notificar_fuentes()
            hc._bombear(4)
            self.assertLess(p.tabla.columnWidth(5), grande)
            self.assertEqual(regla_C5(p.dialogo_config), [])
            self.assertEqual(regla_TB1(p.dialogo_config), [])
        finally:
            c.cerrar()
            estilo.activar_escala(escala_anterior)


if __name__ == "__main__":
    unittest.main()
