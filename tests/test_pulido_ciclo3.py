"""Pruebas de regresión del Ciclo 3 (pulido de editor, propiedades, conexión directa y láminas)."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from grafcet.builder import M
from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Editor, new_grafcet_document
from grafcet.ids import transition_effective_label
from grafcet.model import validate_model
from grafcet.view import display_names
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QGraphicsRectItem
    from conexion.configuracion import Configuracion
    from conexion.intercambio_directo import TransporteDirecto
    from conexion.uniones import Union
    from escritorio import orden_acciones
    from escritorio.acciones import SIN_VARIABLES, opciones_variable
    from escritorio.bloques import normalizar_duracion
    from escritorio.diagrama import COL
    from escritorio.entradas_salidas import NIVEL_ACTIVO, PanelES, ROL_ASIGNADA
    from escritorio.edicion import Edicion
    from escritorio.laminas import DialogoLaminas
    from escritorio.menu_variable import ComboMenu, ROL_PAPEL, UMBRAL_FILTRO
    from escritorio.partes_propiedades import CampoEtiquetaTransicion, ConmutadorPartes
    from grafcet.laminas import ajustes_lamina


def _bombear(n: int = 4) -> None:
    for _ in range(n):
        QApplication.processEvents()


class Ciclo3Nucleo(unittest.TestCase):
    def test_PC3_08_colision_transicion_sin_label_no_interna_y_renombrado(self):
        doc = (
            M()
            .var("a")
            .var("b")
            .step("0", True)
            .step("1")
            .step("2")
            .trans("tr1", ["0"], ["1"], "a")
            .trans("tr2", ["1"], ["2"], "b")
            .doc
        )
        doc["transitions"][1].pop("label", None)
        self.assertEqual(transition_effective_label(doc["transitions"][1]), "tr2")
        # Poner label="tr2" en tr1 choca con tr2 aunque tr2 omita "label" y use su ID no interno.
        doc["transitions"][0]["label"] = "tr2"
        res = validate_model(doc)
        self.assertFalse(res.can_simulate)
        self.assertTrue(any(d.code == "D-NOMBRE-COLISION" for d in res.diagnostics))
        self.assertEqual(Editor.transiciones_repetidas(doc), {"tr1", "tr2"})
        ed = Editor(copy.deepcopy(doc))
        with self.assertRaises(DiagnosticError) as ctx:
            ed.rename("tr1", "tr2", repetida=False)
        self.assertEqual(ctx.exception.diagnostics[0].code, "D-NOMBRE-COLISION")
        # En vista, una automática no pisa el ID efectivo "t2" si otra transición no interna lo ocupa.
        doc2 = new_grafcet_document("v")
        e2 = Editor(doc2)
        s0 = e2.add_step("g", "0", True, at=(100, 80))
        s1 = e2.add_step("g", "1", False, at=(100, 220))
        t_auto, _ = e2.add_transition("g", "a", [s0], [s1], at=(100, 150))
        d_raw = copy.deepcopy(e2.model)
        d_raw["transitions"].append(
            {
                "id": "t1",
                "partialRef": "g",
                "preRefs": [s1],
                "postRefs": [s0],
                "conditionRef": d_raw["transitions"][0]["conditionRef"],
            }
        )
        nombres = display_names(d_raw)
        self.assertEqual(nombres["t1"], "t1")
        self.assertEqual(nombres[t_auto], "t2")


@unittest.skipUnless(QT, "requiere PySide6")
class Ciclo3Qt(BaseQt):
    def test_PC3_01_menus_variables_sin_elija_ni_filtrar(self):
        v = {"q1": ("output", "bool"), "m1": ("internal", "bool")}
        ops_con = opciones_variable(v, ["q1", "m1"], "")
        self.assertFalse(any("Elija" in txt for txt, _, _ in ops_con))
        self.assertEqual(ops_con[0], ("Salidas", None, False))
        ops_vacio = opciones_variable({}, [], "")
        self.assertEqual(ops_vacio, [(SIN_VARIABLES, "", False)])

        combo = ComboMenu()
        self.addCleanup(combo.deleteLater)
        for i in range(UMBRAL_FILTRO + 4):
            combo.addItem(f"q{i:02d}", f"q{i:02d}")
            combo.setItemData(combo.count() - 1, "output", ROL_PAPEL)
        self.assertFalse(combo.con_filtro())
        combo.resize(220, 30)
        combo.show()
        _bombear()
        combo.showPopup()
        _bombear()
        self.assertIsNone(combo.filtro_menu.etiqueta)
        combo.hidePopup()

        w, e = self.vacio()
        e.ed.add_variable("q1", "output", {"kind": "bool"})
        s0 = e.ed.add_step("g", "0", True, at=(100, 80))
        did = e.ed.add_draft_action((140, 80), {"tipo": "activacion", "etapa": s0})
        e.cambia()
        e.pedir_accion(s0, did)
        w._abrir_opciones()
        _bombear()
        p = w.props
        self.assertEqual(p.pagina, "accion")
        items = [p.accion.variable.itemText(i) for i in range(p.accion.variable.count())]
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0], "Salidas")
        self.assertFalse(any("Elija" in t for t in items))
        self.assertEqual(p.accion.variable.currentIndex(), -1)
        self.assertEqual(p.accion.variable.currentText(), "")

    def test_PC3_02_conmutador_marca_blanca_solo_en_activo(self):
        c = ConmutadorPartes([("evento", "Evento", "#7c3aed"), ("accion", "Acción", "#0d9488")])
        self.addCleanup(c.deleteLater)
        c.show()
        _bombear()

        def tiene_marca_blanca(boton) -> bool:
            img = boton.grab().toImage()
            w, h = img.width(), img.height()
            cy = h // 2
            blancos = 0
            for x in range(8, min(22, w)):
                for y in range(max(0, cy - 4), min(h, cy + 5)):
                    if img.pixelColor(x, y) == QColor("#ffffff"):
                        blancos += 1
            return blancos >= 16

        self.assertTrue(tiene_marca_blanca(c.botones["evento"]))
        self.assertFalse(tiene_marca_blanca(c.botones["accion"]))
        c.poner("accion")
        _bombear()
        self.assertFalse(tiene_marca_blanca(c.botones["evento"]))
        self.assertTrue(tiene_marca_blanca(c.botones["accion"]))

    def test_PC3_03_duracion_asume_segundos_y_aplica_al_perder_foco(self):
        self.assertEqual(normalizar_duracion("3"), "3s")
        self.assertEqual(normalizar_duracion(" 2,5 "), "2,5s")
        self.assertEqual(normalizar_duracion("500 ms"), "500ms")
        self.assertEqual(normalizar_duracion("0"), "")
        self.assertEqual(normalizar_duracion("0s"), "")
        self.assertIsNone(normalizar_duracion("abc"))

        w, e = self.vacio()
        e.ed.add_variable("a", "input", {"kind": "bool"})
        s0 = e.ed.add_step("g", "0", True, at=(100, 80))
        s1 = e.ed.add_step("g", "1", False, at=(100, 220))
        tid, _ = e.ed.add_transition("g", "a", [s0], [s1], at=(100, 150))
        e.cambia()
        e.seleccionar([tid])
        w._abrir_opciones()
        _bombear()
        p = w.props
        p._desde_bloques("1s/a")
        _bombear()
        lienzo = p.prog.lienzo
        lienzo._abrir_editor(QRectF(10, 10, 46, 22), (0,), "t1")
        _bombear()
        ed = lienzo._editor
        self.assertIsNotNone(ed)
        ed.setText("4")
        ed.editingFinished.emit()
        _bombear()
        self.assertIn("4 s", e.texto_condicion(tid))

    def test_PC3_04_conexion_directa_sin_parpadeo_y_protege_pendiente(self):
        p = PanelES()
        self.addCleanup(p.deleteLater)
        doc = M().var("s1").var("s2").var("q1", "output").step("0", True).doc
        u1 = Union("s1", "sig1", "Sensor 1", "Bit", "input")
        cfg = Configuracion(modo="directo", modelo=doc["id"], uniones=[u1])
        p.cargar(doc, cfg)
        cliente = TransporteDirecto(Configuracion(modo="directo", modelo=doc["id"], uniones=[u1]))
        cliente.senales = {
            "sig1": {"id": "sig1", "name": "Sensor 1", "type": "Bit", "kind": "Input"},
            "sig2": {"id": "sig2", "name": "Actuador 1", "type": "Bit", "kind": "Output"},
        }
        p.directa.refrescar_catalogo(cliente)
        _bombear()
        t1_antes = p.directa.dibujo.terminales["sig1"]
        t2_antes = p.directa.dibujo.terminales["sig2"]
        item_s1_antes = p.lista_entradas.item(0)

        p.directa.unir("q1", "sig2")
        _bombear()
        self.assertIs(p.directa.dibujo.terminales["sig1"], t1_antes)
        self.assertIs(p.directa.dibujo.terminales["sig2"], t2_antes)
        self.assertIs(p.lista_entradas.item(0), item_s1_antes)
        self.assertTrue(p.lista_salidas.item(0).data(ROL_ASIGNADA))
        self.assertEqual(t2_antes.nombre.text(), "q1")
        self.assertIsNotNone(p.directa._uniones_pendientes)

        # Un catálogo retrasado con el estado anterior [u1] no revierte q1 <-> sig2.
        cliente_viejo = TransporteDirecto(Configuracion(modo="directo", modelo=doc["id"], uniones=[u1]))
        cliente_viejo.senales = cliente.senales
        p.directa.refrescar_catalogo(cliente_viejo)
        _bombear()
        self.assertEqual(len(p.config.uniones), 2)
        self.assertEqual(p.directa.dibujo.terminales["sig2"].nombre.text(), "q1")

        # Cuando el cliente confirma la misma firma pendiente, _uniones_pendientes se limpia.
        cliente_ok = TransporteDirecto(
            Configuracion(
                modo="directo",
                modelo=doc["id"],
                uniones=[u1, Union("q1", "sig2", "Actuador 1", "Bit", "output")],
            )
        )
        cliente_ok.senales = cliente.senales
        p.directa.refrescar_catalogo(cliente_ok)
        self.assertIsNone(p.directa._uniones_pendientes)

        # Actualización de nivel en tiempo real en TerminalDirecto mantiene el mismo widget.
        p.mostrar_valores({"s1": True})
        self.assertEqual(t1_antes.led.nivel, NIVEL_ACTIVO)
        self.assertIs(p.directa.dibujo.terminales["sig1"], t1_antes)

    def test_PC3_05_planos_oculta_error_vacio_y_lo_muestra_al_fallar(self):
        with tempfile.TemporaryDirectory() as docs, mock.patch(
            "escritorio.carpetas.QStandardPaths.writableLocation", return_value=docs
        ):
            w, e = self.vacio()
            s0 = e.ed.add_step("g", "0", True, at=(100, 80))
            e.cambia()
            w.show()
            _bombear()
            dlg = DialogoLaminas(e.M, {}, ajustes_lamina({}), lambda _: None, parent=w, integrado=True)
            self.addCleanup(dlg.deleteLater)
            dlg.show()
            _bombear()
            self.assertTrue(dlg.error.isHidden())
            dlg._fijar_error("Aviso de prueba")
            _bombear()
            self.assertFalse(dlg.error.isHidden())
            self.assertEqual(dlg.error.text(), "Aviso de prueba")
            dlg._fijar_error("")
            _bombear()
            self.assertTrue(dlg.error.isHidden())
            self.assertEqual(s0, e.M["steps"][0]["id"])

    def test_PC3_06_etiquetas_automaticas_transicion_y_renumerado(self):
        w, e = self.vacio()
        s0 = e.ed.add_step("g", "0", True, at=(100, 80))
        s1 = e.ed.add_step("g", "1", False, at=(100, 220))
        s2 = e.ed.add_step("g", "2", False, at=(100, 360))
        t1_id = e.poner_transicion(QPointF(100, 150))
        t2_id = e.poner_transicion(QPointF(100, 290))
        t3_id = e.poner_transicion(QPointF(100, 430))
        self.assertNotIn("label", e.ed.get(t1_id))
        self.assertNotIn("label", e.ed.get(t2_id))
        self.assertNotIn("label", e.ed.get(t3_id))
        self.assertEqual((e.nombres[t1_id], e.nombres[t2_id], e.nombres[t3_id]), ("t1", "t2", "t3"))
        # Borrar t1 renumera automáticamente t2 -> t1 y t3 -> t2.
        e.sel = [t1_id]
        e.borrar()
        self.assertEqual((e.nombres[t2_id], e.nombres[t3_id]), ("t1", "t2"))
        # Fijar etiqueta manual la conserva y vaciarla devuelve automática (con deshacer).
        self.assertIsNone(e.renombrar(t3_id, "PasoFinal"))
        self.assertEqual(e.ed.get(t3_id)["label"], "PasoFinal")
        self.assertEqual(e.nombres[t3_id], "PasoFinal")
        self.assertIsNone(e.renombrar(t3_id, ""))
        self.assertNotIn("label", e.ed.get(t3_id))
        self.assertEqual(e.nombres[t3_id], "t2")
        e.deshacer()
        self.assertEqual(e.ed.get(t3_id)["label"], "PasoFinal")
        self.assertIsNone(e.renombrar(t2_id, t2_id))
        self.assertEqual((s0, s1, s2)[0], e.ed.model["steps"][0]["id"])

    def test_PC3_07_campo_etiqueta_bloqueado_doble_clic_y_esc(self):
        w, e = self.vacio()
        t1 = e.poner_transicion(QPointF(100, 150))
        t2 = e.poner_transicion(QPointF(100, 290))
        e.seleccionar([t1])
        w._abrir_opciones()
        _bombear()
        p = w.props
        v = w.flot.principal
        self.assertIsInstance(p.t_etiqueta, CampoEtiquetaTransicion)
        self.assertTrue(p.t_etiqueta.isReadOnly())
        self.assertEqual(p.t_etiqueta.text(), "t1")

        # Estando bloqueado, Escape cierra la flotante sin deseleccionar.
        QTest.keyClick(p.t_etiqueta, Qt.Key.Key_Escape)
        _bombear()
        self.assertFalse(v.isVisible())
        self.assertEqual(e.sel, [t1])

        w._abrir_opciones()
        _bombear()
        # Doble clic desbloquea; Escape cancela la edición, rebloquea y mantiene abierta la ventana.
        p.t_etiqueta.desbloquear()
        self.assertFalse(p.t_etiqueta.isReadOnly())
        p.t_etiqueta.setText("Borrador")
        QTest.keyClick(p.t_etiqueta, Qt.Key.Key_Escape)
        _bombear()
        self.assertTrue(p.t_etiqueta.isReadOnly())
        self.assertTrue(v.isVisible())
        self.assertEqual(p.t_etiqueta.text(), "t1")
        self.assertNotIn("label", e.ed.get(t1))

        # Desbloquear + confirmar etiqueta manual fija y rebloquea.
        p.t_etiqueta.desbloquear()
        p.t_etiqueta.setText("tr_A")
        p.t_etiqueta.editingFinished.emit()
        _bombear()
        self.assertTrue(p.t_etiqueta.isReadOnly())
        self.assertEqual(e.ed.get(t1).get("label"), "tr_A")
        self.assertEqual(e.nombres[t1], "tr_A")

        # Desbloquear + vaciar vuelve a automática (t1) y rebloquea.
        p.t_etiqueta.desbloquear()
        p.t_etiqueta.setText("")
        p.t_etiqueta.editingFinished.emit()
        _bombear()
        self.assertTrue(p.t_etiqueta.isReadOnly())
        self.assertNotIn("label", e.ed.get(t1))
        self.assertEqual(e.nombres[t1], "t1")

        # Duplicado manual marca colisión naranja en el dibujo y diagnóstico no bloqueante de edición.
        p.t_etiqueta.desbloquear()
        p.t_etiqueta.setText("dup")
        p.t_etiqueta.editingFinished.emit()
        e.renombrar(t2, "dup")
        w.refrescar_edicion()
        _bombear()
        diags = [d for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"]
        self.assertEqual(len(diags), 1)
        self.assertEqual(set(diags[0]["targets"]), {t1, t2})
        glow = QColor(COL["glow"])
        marcos = [
            it for it in w.diagrama.scene().items()
            if isinstance(it, QGraphicsRectItem) and it.pen().color() == glow
        ]
        self.assertEqual(len(marcos), 2)

    def test_PC3_08b_forzados_sustituye_id_en_action_order(self):
        doc = (
            M()
            .var("q1", "output")
            .var("q2", "output")
            .step("0", True)
            .stored("0", "q1", "activation", "1")
            .stored("0", "q2", "activation", "1")
            .doc
        )
        ed = Editor(doc)
        g1 = ed.add_partial("G1")
        s0 = ed.model["steps"][0]["id"]
        aid1, aid2 = ed.model["steps"][0]["actionRefs"]
        orden_acciones.mover(ed, s0, aid2, -1)
        self.assertEqual(orden_acciones.ids_etapa(ed, s0), [aid2, aid1])
        e = Edicion(ed, "Prueba")
        fid = e._poner_orden(s0, None, {"destino": g1, "forma": "empty"}, quitar=aid1)
        self.assertIsNotNone(fid)
        self.assertEqual(orden_acciones.ids_etapa(ed, s0), [aid2, fid])

    def test_PC3_09_desborde_favoritos_alineado_izquierda(self):
        w, _ = self.vacio()
        w.resize(640, 768)
        w.show()
        self.pasar_arranque(w)
        w._mostrar_panel("derecho", True)
        _bombear(6)
        menu = w.favoritos.crear_menu_desborde()
        self.addCleanup(menu.deleteLater)
        menu.show()
        _bombear(4)
        botones = [a.defaultWidget() for a in menu.actions()]
        self.assertGreaterEqual(len(botones), 6)

        def col_icono(boton) -> int:
            img = boton.grab().toImage()
            w_b, h_b = img.width(), img.height()
            for x in range(w_b):
                for y in range(4, max(5, h_b - 4)):
                    c = img.pixelColor(x, y)
                    if c.alpha() > 0 and c.red() < 100 and c.green() < 100 and c.blue() < 100:
                        return x
            return -1

        xs = [col_icono(b) for b in botones]
        self.assertTrue(all(8 <= x <= 14 for x in xs), xs)
        self.assertLessEqual(max(xs) - min(xs), 1, xs)

    def test_PC3_10_alternar_directo_modbus_directo_repuebla_terminales(self):
        from escritorio.directa_marco import TerminalDirecto

        p = PanelES()
        self.addCleanup(p.deleteLater)
        doc = M().var("s1").var("q1", "output").step("0", True).doc
        u1 = Union("s1", "sig1", "Sensor 1", "Bit", "input")
        cfg_dir = Configuracion(modo="directo", modelo=doc["id"], uniones=[u1])
        cliente = TransporteDirecto(Configuracion(modo="directo", modelo=doc["id"], uniones=[u1]))
        cliente.senales = {
            "sig1": {"id": "sig1", "name": "Sensor 1", "type": "Bit", "kind": "Input"},
            "sig2": {"id": "sig2", "name": "Actuador 1", "type": "Bit", "kind": "Output"},
        }
        p.cargar(doc, cfg_dir)
        p.directa.refrescar_catalogo(cliente)
        _bombear()
        self.assertIn("s1", p.indicadores_listas)

        # Cambiar a Modbus y redibujar (destruye widgets Modbus al reconstruir o cambiar) y volver a Directo.
        p.directa.selector.setCurrentIndex(0)
        _bombear()
        self.assertIsNone(p.directa.dibujo._clave_layout)
        p.directa.selector.setCurrentIndex(1)
        _bombear()
        p.cargar(doc, cfg_dir)
        _bombear()
        self.assertTrue(p.terminales)
        self.assertTrue(all(isinstance(t, TerminalDirecto) for t in p.terminales.values()))
        self.assertIn("s1", p.indicadores_listas)
        # Simular cambio de estado ocupado y selección de clic sin RuntimeError en objetos C++.
        p.ocupado(True)
        p.ocupado(False)
        p._eleccion = ("variable", "s1")
        p._pintar_eleccion()
        self.assertTrue(p.indicadores_listas["s1"].isSelected())
