"""Pruebas de regresión del Ciclo 2 (11 ajustes tras pruebas en vivo)."""
from __future__ import annotations

import unittest

from grafcet.builder import M
from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Editor
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QEvent, QItemSelectionModel, QPoint, QPointF, Qt
    from PySide6.QtGui import QColor, QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
                                   QGraphicsPathItem, QGraphicsRectItem, QLineEdit, QToolTip)
    from conexion.configuracion import Configuracion, Senal
    from conexion.uniones import Union
    from escritorio import estilo, orden_acciones
    from escritorio.ayudas_emergentes import ANCHO_MAXIMO, ayuda_html, texto_plano
    from escritorio.diagrama import COL, SX, H, dibujar
    from escritorio.entradas_salidas import DelegadoVariable, PanelES, ROL_ASIGNADA
    from escritorio.estilo_config_es import hoja_dialogo_es
    from escritorio.geometria.acciones import acciones_etapa
    from escritorio.menu_variable import pintar_caja


def _editor_transiciones_iguales(etiqueta: str = "t2") -> tuple[Editor, str, str]:
    doc = (M().var("a").var("b").step("0", True).step("1").step("2")
           .trans("tr1", ["0"], ["1"], "a")
           .trans("tr2", ["1"], ["2"], "b")
           .doc)
    doc["transitions"][0]["label"] = etiqueta
    doc["transitions"][1]["label"] = etiqueta
    ed = Editor(doc)
    for k, (px, py) in (
        ("0", (100, 80)),
        ("1", (100, 240)),
        ("2", (100, 400)),
        ("tr1", (100, 160)),
        ("tr2", (100, 320)),
    ):
        ed.move(k, px, py)
    return ed, "tr1", "tr2"


class TransicionesRepetidasNucleo(unittest.TestCase):
    def test_PC2_10_nucleo_detecta_etiqueta_transicion_repetida_y_permite_editar(self):
        ed, tr1, tr2 = _editor_transiciones_iguales("t2")
        res = ed.validate()
        self.assertFalse(res.can_simulate)
        self.assertTrue(any(d.code == "D-NOMBRE-COLISION" for d in res.diagnostics))
        self.assertEqual(ed.transiciones_repetidas(ed.model), {tr1, tr2})
        ed.rename(tr1, "t1", repetida=True)
        res2 = ed.validate()
        self.assertTrue(res2.can_simulate)
        self.assertEqual(ed.transiciones_repetidas(ed.model), set())
        ed.rename(tr1, "t2", repetida=True)
        self.assertFalse(ed.validate().can_simulate)

    def test_PC2_12_renombrar_transicion_con_otra_sin_etiqueta(self):
        doc = (M().var("a").var("b").step("0", True).step("1").step("2")
               .trans("tr1", ["0"], ["1"], "a")
               .trans("tr2", ["1"], ["2"], "b")
               .doc)
        doc["transitions"][1].pop("label", None)
        ed = Editor(doc)
        ed.rename("tr1", "t1", repetida=False)
        self.assertEqual(ed.get("tr1")["label"], "t1")
        ed.rename("tr1", "t9", repetida=True)
        self.assertEqual(ed.get("tr1")["label"], "t9")
        ed.rename("tr2", "t9", repetida=True)
        with self.assertRaises(DiagnosticError) as ctx:
            ed.rename("tr1", "t9", repetida=False)
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-NOMBRE-COLISION")


@unittest.skipUnless(QT, "requiere PySide6")
class PulidoCiclo2Qt(BaseQt):
    def test_PC2_01_subtitulos_es_variables_creadas(self):
        p = PanelES()
        self.addCleanup(p.deleteLater)
        p.cargar(M().var("s1").var("q1", "output").step("0", True).doc)
        self.assertEqual(p.subtitulos["input"].text(), "Variables creadas en GRAFCET Connect")
        self.assertEqual(p.subtitulos["output"].text(), "Variables creadas en GRAFCET Connect")

    def test_PC2_02_terminales_hueco_cable_y_quitar_junto_al_nombre(self):
        p = PanelES()
        self.addCleanup(p.deleteLater)
        self.addCleanup(p.hide)
        doc = M().var("a").var("b", "output").var("sensor_muy_largo_de_estacion_principal_01").step("0", True).doc
        cfg = Configuracion(senales=[
            Senal("a", "discrete", 0),
            Senal("sensor_muy_largo_de_estacion_principal_01", "discrete", 1),
            Senal("b", "coil", 0),
        ])
        p.cargar(doc, cfg)
        p.resize(1300, 720)
        p.show()
        QApplication.processEvents()
        tin = p.terminales[("discrete", 0)]
        tout = p.terminales[("coil", 0)]
        wire_in_left = tin.interior.geometry().left() - 10
        self.assertGreaterEqual(wire_in_left - tin.nombre.geometry().right(), 3)
        wire_out_right = tout.interior.geometry().right() + 11
        self.assertGreaterEqual(tout.nombre.geometry().left() - wire_out_right, 3)
        tin.b_quitar.show()
        tout.b_quitar.show()
        QApplication.processEvents()
        self.assertLessEqual(tin.nombre.geometry().left() - tin.b_quitar.geometry().right(), 12)
        self.assertLessEqual(tout.b_quitar.geometry().left() - tout.nombre.geometry().right(), 12)
        tlong = p.terminales[("discrete", 1)]
        tlong.b_quitar.show()
        QApplication.processEvents()
        self.assertGreaterEqual(tlong.b_quitar.x(), 0)
        self.assertGreater(tlong.nombre.width(), 0)

    def test_PC2_03_planos_conserva_estilo_v2_tras_cambio_escala(self):
        w, _ = self.vacio()
        w.resize(1366, 768)
        w.show()
        QTest.mouseClick(w.pestanas_vistas, Qt.MouseButton.LeftButton, pos=w.pestanas_vistas.tabRect(1).center())
        QApplication.processEvents()
        hoja = w.panel_planos.styleSheet()
        self.assertIn("scrollHojasPlanos", hoja)
        self.assertIn("areaHojaPlanos", hoja)
        self.assertIn("panelPropiedadesPlanos", hoja)
        w.resize(1680, 960)
        QApplication.processEvents()
        w._escala_de_la_ventana()
        QApplication.processEvents()
        hoja_g = w.panel_planos.styleSheet()
        self.assertIn("scrollHojasPlanos", hoja_g)
        self.assertIn("panelPropiedadesPlanos", hoja_g)
        w.hide()

    def test_PC2_04_variables_multiseleccion_y_eliminar(self):
        w, e = self.vacio()
        e.nueva_variable("v1", "input")
        e.nueva_variable("v2", "input")
        e.nueva_variable("v3", "output")
        pv = w.variables
        pv.mostrar(e)
        self.assertEqual(pv.tabla.selectionMode(), QAbstractItemView.SelectionMode.ExtendedSelection)
        idx0 = pv.tabla.model().index(0, 0)
        idx2 = pv.tabla.model().index(2, 0)
        sel = pv.tabla.selectionModel()
        sel.select(idx0, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        sel.select(idx2, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        pv.quitar()
        self.assertEqual([v["name"] for v in e.variables()], ["v2"])

    def test_PC2_05_tooltips_claros_y_compactos(self):
        hoja = estilo.hoja_global()
        self.assertIn("QToolTip { background:#ffffff; color:#16263a;", hoja)
        corto = ayuda_html("Deshacer")
        self.assertNotIn("<table width=", corto)
        self.assertEqual(texto_plano(corto).strip(), "Deshacer")
        largo_txt = "Texto muy largo para probar el ajuste automático de línea dentro de una ayuda emergente. " * 4
        largo = ayuda_html(largo_txt)
        self.assertIn(f'width="{ANCHO_MAXIMO - 2 * estilo.E4}"', largo)
        self.assertEqual(texto_plano(largo).strip(), largo_txt.strip())

    def test_PC2_06_foco_sin_doble_borde_y_teclado_vs_raton(self):
        w, _ = self.vacio()
        w.show()
        hoja = estilo.hoja_global()
        self.assertIn("QLineEdit:focus, QComboBox:focus { border:2px solid", hoja)
        self.assertIn('QLineEdit[tecl="true"]:focus, QComboBox[tecl="true"]:focus { border:2px dashed', hoja)
        campo = QLineEdit("abc", w)
        campo.show()
        QApplication.processEvents()
        QTest.mouseClick(campo, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        self.assertFalse(bool(campo.property("tecl")))
        QTest.keyClick(campo, Qt.Key.Key_Space)
        QTest.keyClick(campo, Qt.Key.Key_Left)
        self.assertFalse(bool(campo.property("tecl")))
        ev_tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(campo, ev_tab)
        self.assertTrue(QApplication.instance()._foco_teclado.teclado)
        combo = QComboBox(w)
        combo.addItem("motor", "motor")
        combo.setFixedSize(140, 30)
        combo.setFocus()
        combo.show()
        QApplication.processEvents()
        # No debe arrojar error al pintar con raton o teclado y conserva dimensiones
        pintar_caja(combo, "motor", "output")
        combo.setProperty("tecl", True)
        pintar_caja(combo, "motor", "output")
        w.hide()

    def test_PC2_07_checkboxes_visibles_y_sin_border_zero(self):
        hoja_es = hoja_dialogo_es()
        self.assertNotIn("QCheckBox { background:transparent; color:#16263a; border:0;", hoja_es)
        self.assertIn("QFrame#tarjetaConfigES QLabel {", hoja_es)
        estilo.hoja_global()
        caja = QCheckBox("Probar")
        caja.setStyleSheet(estilo.hoja_global())
        caja.setChecked(True)
        caja.show()
        QApplication.processEvents()
        img = caja.grab().toImage()
        encontrado = any(img.pixelColor(x, y).name() == estilo.ACENTO
                         for x in range(img.width()) for y in range(img.height()))
        self.assertTrue(encontrado, "la casilla marcada debe mostrar su fondo acento completo")
        caja.hide()
        caja.deleteLater()

    def test_PC2_08_acciones_separadas_re_unen_en_grupo(self):
        w, e = self.vacio()
        self.assertIsNone(e.nueva_variable("Q00", "output"))
        self.assertIsNone(e.nueva_variable("Q01", "output"))
        s1 = e.ed.add_step("g", "1", True, at=(100, 120))
        e.cambia()
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q00"}))
        self.assertIsNone(e.poner_accion(s1, {"tipo": "continua", "variable": "Q01"}))
        w.refrescar_edicion()
        e.eliminar_enlace_acciones(s1)
        sueltas = e.ed.draft_actions()
        self.assertEqual(len(sueltas), 2)
        grupo = sueltas[0].get("grupo")
        self.assertTrue(grupo)
        self.assertEqual(sueltas[1].get("grupo"), grupo)
        e.unir_accion(sueltas[0]["id"], s1)
        self.assertEqual(len(e.acciones(s1)), 2)
        self.assertEqual([e.datos_accion(a["id"])["variable"] for a in e.acciones(s1)], ["Q00", "Q01"])

    def test_PC2_09_indicador_c_en_modbus_y_directa(self):
        p = PanelES()
        self.addCleanup(p.deleteLater)
        doc = M().var("sensor_muy_largo_10").var("sensor_muy_largo_20").step("0", True).doc
        p.cargar(doc, Configuracion(senales=[Senal("sensor_muy_largo_10", "discrete", 0)]))
        self.assertTrue(p.lista_entradas.item(0).data(ROL_ASIGNADA))
        self.assertFalse(p.lista_entradas.item(1).data(ROL_ASIGNADA))
        delegado = p.lista_entradas.itemDelegate()
        self.assertIsInstance(delegado, DelegadoVariable)
        w1 = delegado.texto_visible(p.lista_entradas.model().index(0, 0), 140)
        w2 = delegado.texto_visible(p.lista_entradas.model().index(1, 0), 140)
        self.assertLess(len(w1), len(w2))
        cfg_d = Configuracion(modo="directo", uniones=[Union("sensor_muy_largo_10", "id1", "Sensor 1", "Bit", "input")])
        p.cargar(doc, cfg_d)
        self.assertTrue(p.lista_entradas.item(0).data(ROL_ASIGNADA))
        self.assertFalse(p.lista_entradas.item(1).data(ROL_ASIGNADA))

    def test_PC2_10_transiciones_repetidas_naranja_y_diagnostico(self):
        w, e = self.vacio()
        ed, tr1, tr2 = _editor_transiciones_iguales("t2")
        e.ed = ed
        e.cambia()
        diags = [d for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"]
        self.assertEqual(len(diags), 1)
        self.assertEqual(set(diags[0]["targets"]), {tr1, tr2})
        self.assertFalse(e.ed.validate().can_simulate)
        e.poner_etiquetas(False)
        w.refrescar_edicion()
        glow = QColor(COL["glow"])
        marcos_naranja = [
            it for it in w.diagrama.scene().items()
            if isinstance(it, QGraphicsRectItem) and it.pen().color() == glow
        ]
        self.assertEqual(len(marcos_naranja), 2)
        e.renombrar(tr1, "t1")
        w.refrescar_edicion()
        self.assertTrue(e.ed.validate().can_simulate)
        marcos_naranja2 = [
            it for it in w.diagrama.scene().items()
            if isinstance(it, QGraphicsRectItem) and it.pen().color() == glow
        ]
        self.assertEqual(len(marcos_naranja2), 0)

    def test_PC2_11_lienzo_vacio_sin_barras_al_arranque(self):
        w, _ = self.vacio()
        w.resize(1366, 768)
        w.show()
        QApplication.processEvents()
        self.assertIsNone(w.diagrama._contenido)
        self.assertEqual(w.diagrama.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertEqual(w.diagrama.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        w.hide()

    def test_PC2_13_separar_y_reunir_grupo_mixto_forzado_accion(self):
        # Subcaso 1: sin `actionOrder` previo, modelo [forzado f1] + borrador pendiente [d_incompleto]
        w, e, d = self.con_recinto()
        h, r, b = d["h"], d["r"], d["b"]
        e.pedir_forzado = lambda datos: {"destino": r, "forma": "explicit", "etapas": [b]}
        e.pedir_accion = lambda *a: None
        f1 = e.forzar(h)
        d_inc = e.anadir_accion(h)
        self.assertNotIn("actionOrder", e.ed.presentation)
        w.refrescar_edicion()
        rect_f1 = next(c for c in w.diagrama.cajas_ordenes if c["id"] == f1)["rect"]
        e.eliminar_enlace_acciones(h)
        sueltos1 = [x for x in e.ed.draft_actions() if not x.get("etapa")]
        sueltos1.sort(key=lambda x: x.get("orden", 10 ** 6))
        self.assertEqual([x["tipo"] for x in sueltos1], ["forzado", "continua"])
        self.assertEqual((sueltos1[0]["x"], sueltos1[0]["y"]),
                         (str(round(rect_f1[0] - SX)), str(round(rect_f1[1] + H))))
        e.unir_accion(sueltos1[0]["id"], h)
        w.refrescar_edicion()
        f2 = e.ed.model["forces"][-1]["id"]
        self.assertEqual(orden_acciones.ids_etapa(e.ed, h), [f2, d_inc])
        etapa_m = next(s for s in e.M["steps"] if s["id"] == h)
        self.assertEqual([a["id"] for a in acciones_etapa(e.M, etapa_m)], [f2, d_inc])

        # Subcaso 2: completar borrador `forzado` antes de una acción conserva su orden y al separar/reunir también
        w2, e2, d2 = self.con_recinto()
        h2, r2, b2 = d2["h"], d2["r"], d2["b"]
        self.assertIsNone(e2.nueva_variable("Q00", "output"))
        self.assertIsNone(e2.poner_accion(h2, {"tipo": "continua", "variable": "Q00"}))
        a1 = e2.ed.get(h2)["actionRefs"][0]
        did_f = e2.ed.add_draft_action((360, 60), {"etapa": h2, "tipo": "forzado"})
        orden_acciones.guardar(e2.ed, h2, [did_f, a1])
        e2.cambia()
        e2.pedir_forzado = lambda datos: {"destino": r2, "forma": "explicit", "etapas": [b2]}
        fid = e2.configurar_orden(did_f)
        self.assertEqual(orden_acciones.ids_etapa(e2.ed, h2), [fid, a1])
        w2.refrescar_edicion()
        e2.eliminar_enlace_acciones(h2)
        sueltos2 = [x for x in e2.ed.draft_actions() if not x.get("etapa")]
        sueltos2.sort(key=lambda x: x.get("orden", 10 ** 6))
        self.assertEqual([x["tipo"] for x in sueltos2], ["forzado", "continua"])
        e2.unir_accion(sueltos2[0]["id"], h2)
        w2.refrescar_edicion()
        fid2 = e2.ed.model["forces"][-1]["id"]
        a2 = e2.ed.get(h2)["actionRefs"][0]
        self.assertEqual(orden_acciones.ids_etapa(e2.ed, h2), [fid2, a2])
        etapa_m2 = next(s for s in e2.M["steps"] if s["id"] == h2)
        self.assertEqual([(a["kind"], a["id"]) for a in acciones_etapa(e2.M, etapa_m2)],
                         [("force", fid2), ("continuous", a2)])
        e2.deshacer()
        self.assertEqual(len(e2.ed.model["forces"]), 0)
        e2.rehacer()
        self.assertEqual([a["id"] for a in acciones_etapa(e2.M, next(s for s in e2.M["steps"] if s["id"] == h2))],
                         [fid2, a2])


if __name__ == "__main__":
    unittest.main()
