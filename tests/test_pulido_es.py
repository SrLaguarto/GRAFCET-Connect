"""Panel compacto de E/S y configuración portable con prioridades explícitas."""
from helpers_grafnet import fixture_grafnet
import copy
import json
from pathlib import Path
import shutil
import unittest
from test_editor_cadenas import BaseQt, QT
from grafcet.builder import M
from conexion.configuracion import ARCHIVO, CONEXION_INICIAL, CANALES_INICIALES, Configuracion, Senal

if QT:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QSignalSpy
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QMessageBox
    from PySide6.QtGui import QAction
    from escritorio.entradas_salidas import PanelES, ALTO_FILA, ALTO_VARIABLE, NIVEL_ACTIVO, NIVEL_ASIGNADO


def documento():
    return (M().var("sensor").var("nivel", kind="decimal", scale=2).var("motor", "output")
            .var("consigna", "output", "int").step("0", True).doc)


@unittest.skipUnless(QT, "PySide6 no está instalado")
class PulidoES(BaseQt):
    def modelo(self, nombre="modelo"):
        w = self.w
        if w.edicion:
            w.edicion.ed.dirty = False
        w.fuente = {"tipo": "fichero", "ruta": Path(self.tmp.name) / f"{nombre}.json", "doc": documento(),
                    "layout": {}, "titulo": "Prueba", "ayuda": "", "raiz": None}
        w._cargar()
        return w, w.panel_es

    def test_SESP01_sin_proyecto_ni_preferencias_usa_factory_io(self):
        """REQ-SIM-03: sin configuración propia ni recordada se proponen servidor y cantidades iniciales de conexión."""
        w, p = self.modelo()
        c = p.obtener()
        self.assertEqual((c.host, c.puerto, c.unidad), CONEXION_INICIAL)
        self.assertEqual(c.canales, CANALES_INICIALES)
        self.assertEqual(Configuracion().host, CONEXION_INICIAL[0])
        self.assertEqual(p.tabla.cellWidget(1, 7).text(), "100")
        self.assertIn("servidor Modbus", p.host.toolTip())
        self.assertNotIn("Factory", p.host.toolTip())
        self.assertFalse(w.ajustes.contains("modbus/configuracion"))

    def test_SESP02_recordado_incluye_canales_y_escalas_sin_asignaciones(self):
        """REQ-SIM-03, REQ-DAT-02: un proyecto sin mapa usa los parámetros completos recordados, sin copiar variables asignadas."""
        w, p = self.modelo()
        canales = copy.deepcopy(CANALES_INICIALES)
        canales["input-register"] = {"offset": 2, "cantidad": 5}
        c = Configuracion(host="10.1.2.3", puerto=1502, unidad=7, periodo_ms=80, timeout_ms=900, modelo=p.doc["id"],
                          canales=canales, senales=[Senal("nivel", "input-register", 2, "INT16", "25")])
        p.cargar(p.doc, c); w._recordar_parametros(p.obtener())
        w, p = self.modelo("otro")
        c = p.obtener()
        self.assertEqual((c.host, c.puerto, c.unidad, c.periodo_ms, c.timeout_ms), ("10.1.2.3", 1502, 7, 80, 900))
        self.assertEqual(c.canales, canales); self.assertEqual(c.senales, [])
        self.assertTrue(p.asignar("nivel", "input-register", 2))
        self.assertEqual(p.config.senales[0].escala, "25")
        prefs = json.loads(w.ajustes.value("modbus/configuracion"))
        self.assertNotIn("senales", prefs); self.assertNotIn("modelo", prefs)

    def test_SESP03_json_del_proyecto_manda_sobre_preferencias(self):
        """REQ-DAT-02, REQ-SIM-03: servidor, cantidades y escala del proyecto tienen prioridad sobre la última configuración."""
        w, p = self.modelo()
        w._recordar_parametros(Configuracion(host="10.0.0.7", canales=copy.deepcopy(CANALES_INICIALES)))
        raiz = Path(self.tmp.name) / "guardado"
        w.edicion.guardar(raiz)
        canales = copy.deepcopy(CANALES_INICIALES); canales["coil"]["cantidad"] = 21
        Configuracion(host="10.0.0.9", puerto=2502, unidad=4, modelo=p.doc["id"], canales=canales,
                      senales=[Senal("nivel", "input-register", 0, "INT16", "50")]).guardar(raiz / ARCHIVO, p.doc)
        self.assertTrue(w.abrir_ruta(fixture_grafnet(raiz)))
        c = p.obtener()
        self.assertEqual((c.host, c.puerto, c.unidad), ("10.0.0.9", 2502, 4))
        self.assertEqual(c.canales["coil"]["cantidad"], 21)
        self.assertEqual(c.senales[0].escala, "50")
        self.assertIn("guardada en el proyecto", p.host.toolTip())

    def test_SESP04_primera_guarda_adjunta_mapa_y_viaja_con_el_proyecto(self):
        """REQ-DAT-02, REQ-EDT-01: la primera guarda de proyecto incluye la conexión y la copia transportada conserva sus ajustes."""
        w, p = self.modelo()
        p.host.setText("10.10.10.10"); p.host.editingFinished.emit()
        p.asignar("nivel", "input-register", 0)
        p.tabla.cellWidget(1, 7).setText("40"); p.tabla.cellWidget(1, 7).editingFinished.emit()
        raiz = Path(self.tmp.name) / "nuevo"
        self.assertFalse((raiz / ARCHIVO).exists())
        w.edicion.ruta = raiz
        from unittest.mock import patch
        with patch("escritorio.archivos.QFileDialog.getSaveFileName",return_value=(str(raiz)+".grafnet","")):
            self.assertTrue(w.guardar())
        raiz=w.edicion.ruta
        guardada = Configuracion.cargar(raiz / ARCHIVO, p.doc)
        self.assertEqual((guardada.host, guardada.senales[0].escala), ("10.10.10.10", "40"))
        copia = Path(self.tmp.name) / "transportado"; shutil.copytree(raiz, copia)
        self.assertTrue(w.abrir_ruta(fixture_grafnet(copia)))
        self.assertEqual((p.obtener().host, p.obtener().senales[0].escala), ("10.10.10.10", "40"))

    def test_SESP05_preferencias_anteriores_validas_no_se_sustituyen_silenciosamente(self):
        """REQ-SIM-03: una dirección previamente recordada manda sobre el valor inicial y se identifica su procedencia."""
        w, p = self.modelo()
        w.ajustes.setValue("modbus/host", "127.0.0.1")
        w.ajustes.remove("modbus/configuracion")
        d = w._leer_parametros_recordados()
        self.assertEqual(d["host"], "127.0.0.1")
        w.ajustes.setValue("modbus/host", "")
        self.assertEqual(w._leer_parametros_recordados()["host"], CONEXION_INICIAL[0])

    def test_SESP06_filas_iguales_y_registros_alineados_con_cantidades_distintas(self):
        """REQ-SIM-03: sensores, canales y actuadores usan la misma altura; los registros comienzan en la misma horizontal."""
        w, p = self.modelo()
        c = Configuracion(canales={a: {"offset": 0, "cantidad": n} for a, n in
                                    (("discrete", 3), ("coil", 7), ("input-register", 2), ("holding", 4))})
        p.cargar(p.doc, c); w._mostrar_pagina(True); w.resize(1366, 768); w.show(); QApplication.processEvents()
        self.assertEqual(ALTO_VARIABLE, ALTO_FILA)
        self.assertTrue(all(t.height() == ALTO_FILA for t in p.terminales.values()))
        self.assertEqual(p.lista_entradas.visualItemRect(p.lista_entradas.item(0)).height(), ALTO_FILA)
        a = p.terminales["input-register", 0]; b = p.terminales["holding", 0]
        self.assertEqual(a.mapTo(p, QPoint()).y(), b.mapTo(p, QPoint()).y())
        self.assertEqual(a.canal.text(), "Entrada numérica 0")
        self.assertEqual(b.canal.text(), "Salida numérica 0")

    def test_SESP07_led_activo_saturado_e_inactivo_neutro(self):
        """REQ-SIM-03: la señal activa tiene color saturado y la inactiva es neutra en lista y canal."""
        w, p = self.modelo()
        p.asignar("sensor", "discrete", 0)
        led = p.indicadores["sensor"][0]
        p.mostrar_valores({"sensor": False}); apagado = led.color()
        p.mostrar_valores({"sensor": True}); activo = led.color()
        self.assertLess(apagado.hsvSaturation(), 45)
        self.assertGreater(activo.hsvSaturation(), 160)
        self.assertNotEqual(apagado, activo)
        self.assertEqual(led.nivel, NIVEL_ACTIVO)
        p.mostrar_valores({"sensor": None}); self.assertEqual(led.nivel, NIVEL_ASIGNADO)

    def test_SESP08_cabecera_colorea_todos_los_estados_sin_perder_texto(self):
        """REQ-SIM-03: estado inicial neutro, estable verde, fallo y desconexión con el fondo original, con mensaje conservado."""
        w, p = self.modelo()
        for estado, mensaje, visual in (("desconectado", "Desconectado", "neutro"),
                                         ("conectado", "Conectado", "conectado"),
                                         ("error", "Conexión perdida", "neutro"),
                                         ("desconectado", "Desconectado", "neutro")):
            p.mostrar_estado(estado, mensaje)
            self.assertEqual(p.cabecera.property("estadoVisual"), visual)
            self.assertEqual(p.estado.text(), mensaje)

    def test_SESP09_no_hay_controles_del_bloque_inferior_ni_prueba_guiada(self):
        """REQ-SIM-03: la configuración no ofrece Aplicar, cargar/guardar archivos, probar, guía ni Cerrar inferior."""
        w, p = self.modelo()
        prohibidos = {"Aplicar mapa", "Cargar configuración…", "Guardar configuración…", "Probar conexión", "Abrir prueba guiada", "Cerrar"}
        self.assertFalse(prohibidos & {b.text() for b in p.findChildren(QPushButton)})
        self.assertFalse(any(a.text() == "Abrir prueba guiada" for a in w.findChildren(QAction)))
        self.assertTrue(p.b_conectar.isVisibleTo(p)); self.assertTrue(p.b_configuracion.isVisibleTo(p))

    def test_SESP10_asignar_y_editar_configuracion_aplican_sin_boton(self):
        """REQ-SIM-03, REQ-DAT-02: arrastrar/asignar y terminar la edición de un campo aplican el mapa sin botón adicional."""
        w, p = self.modelo(); spy = QSignalSpy(p.aplicar)
        self.assertTrue(p.asignar("sensor", "discrete", 0))
        self.assertEqual(spy.count(), 1)
        p.host.setText("10.2.3.4"); p.host.editingFinished.emit()
        self.assertEqual(p.config.host, "10.2.3.4")
        self.assertEqual(spy.count(), 2)
        self.assertTrue(p.tabla.cellWidget(0, 7).isReadOnly())
        self.assertFalse(p.tabla.cellWidget(1, 7).isReadOnly())
        p.quitar("sensor"); self.assertEqual(spy.count(), 3)
        self.assertEqual(p.config.senales, [])

    def test_SESP11_mapa_invalido_avisa_sin_sobrescribir_el_archivo(self):
        """REQ-DAT-02, REQ-ROB-01: una configuración guardada inválida se señala y el original no se sobrescribe al abrir."""
        w, p = self.modelo(); raiz = Path(self.tmp.name) / "invalido"; w.edicion.guardar(raiz)
        ruta = raiz / ARCHIVO; ruta.write_text('{"version": 999}', encoding="utf-8")
        before = ruta.read_bytes()
        self.assertTrue(w.abrir_ruta(fixture_grafnet(raiz)))
        self.assertIn("No se pudo cargar", p.estado.text())
        self.assertEqual(p.cabecera.property("estadoVisual"), "neutro")
        self.assertEqual(ruta.read_bytes(), before)

    def test_SESP12_preferencias_invalidas_vuelven_a_valores_validos(self):
        """REQ-SIM-03, REQ-ROB-01: preferencias corruptas no dejan una propuesta inválida ni alteran las guardadas."""
        w, p = self.modelo()
        w.ajustes.setValue("modbus/configuracion", '{"host": "", "puerto": -1}')
        self.assertEqual(w._leer_parametros_recordados()["host"], CONEXION_INICIAL[0])
        w.ajustes.setValue("modbus/configuracion", '{"escalas": {"holding:0": "0"}}')
        self.assertEqual(w._leer_parametros_recordados()["canales"], CANALES_INICIALES)

    def test_SESP13_guardar_no_altera_el_mapa_de_una_conexion_viva(self):
        """REQ-DAT-02, REQ-SIM-04: guardar depura una copia para el proyecto sin cambiar los controles ni el mapa en uso."""
        w, p = self.modelo(); p.asignar("sensor", "discrete", 0); p.ocupado(True)
        before = copy.deepcopy((p.doc, p.config))
        doc = copy.deepcopy(p.doc); doc["variables"] = [v for v in doc["variables"] if v["id"] != "sensor"]
        config = w._configuracion_para_guardar(doc)
        self.assertEqual(config.senales, [])
        self.assertEqual((p.doc, p.config), before)

    def test_SESP14_capacidad_a_1366_y_panel_usable_a_1000(self):
        """REQ-SIM-03, REQ-EDT-09: los 20+10 canales por lado caben sin scroll a 1366×768 y la vista pequeña conserva acceso."""
        w, p = self.modelo()
        for area,campo in p.cantidades.items():campo.setValue(20 if area in ('discrete','coil') else 10)
        w._mostrar_pagina(True); w.show()
        for ancho, alto in ((1366, 768), (1000, 600)):
            w.resize(ancho, alto)
            for _ in range(6): QApplication.processEvents()
            self.assertEqual((w.width(), w.height()), (ancho, alto))
            self.assertLessEqual(p.minimumSizeHint().width(), w.width())
            self.assertTrue(p.b_conectar.isVisibleTo(w)); self.assertTrue(p.b_configuracion.isVisibleTo(w))
            scroll = p.lienzo.parentWidget().parentWidget()
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            if ancho == 1366:
                self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
