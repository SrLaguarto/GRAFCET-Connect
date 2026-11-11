"""Cambios pedidos tras la tercera prueba en clase (P-IMP-118 a 124): el panel plegado no se abre solo, números de etapa
repetidos como borrador, paneles más compactos, enlaces de borrador entre etapa y transición, y arrastres más fieles."""
import copy
import tempfile
import unittest
from pathlib import Path

from grafcet.builder import M
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QEvent, QPointF, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.edicion import Edicion


@unittest.skipUnless(QT, "requiere PySide6")
class PanelPlegadoNoSeAbre(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def preparar(self):
        m = M().var("a").step("1", True).step("2").trans("t", ["1"], ["2"], "a")
        e = Edicion.desde(m.doc, {"1": (100, 80), "t": (100, 180), "2": (100, 280)}, "Panel")
        w = self.w
        w._establecer_edicion(e);w.resize(1366, 768);w.show();QApplication.processEvents()
        w._mostrar_panel("inferior", False);QApplication.processEvents()
        return w, e

    def ids(self, e):
        return {s["label"]: s["id"] for s in e.M["steps"]}, e.M["transitions"][0]["id"]

    def test_SAUC01_seleccionar_no_abre_el_panel_plegado_ni_hace_parpadear_su_pestana(self):
        """REQ-EDT-09: con el panel inferior plegado, seleccionar una etapa o una transición no lo despliega y la pestaña no parpadea."""
        w, e = self.preparar()
        etapas, t = self.ids(e)
        pest = w.pestanas["inferior"]
        for ident in (etapas["1"], t):
            e.seleccionar([ident]);QApplication.processEvents()
            self.assertFalse(w._plegables["inferior"].abierto)
            self.assertTrue(w.inferior.isHidden())
            self.assertFalse(hasattr(pest, "destellos"), "ya no hay parpadeo de la pestaña")
            self.assertFalse(hasattr(pest, "parpadear"))
        e.seleccionar([]);QApplication.processEvents()
        self.assertTrue(w.inferior.isHidden())

    def test_SAUC02_el_doble_clic_y_intro_abren_el_panel_plegado(self):
        """REQ-EDT-09: el doble clic en una etapa, una transición o una acción, y Intro con algo seleccionado, despliegan el panel."""
        w, e = self.preparar()
        etapas, t = self.ids(e)
        for ident in (etapas["1"], t):
            w._mostrar_panel("inferior", False);QApplication.processEvents()
            c = e.centro(ident)
            e.seleccionar([ident])
            self.assertTrue(w.inferior.isHidden())
            e.doble(QPointF(c))
            QApplication.processEvents()
            self.assertTrue(w._plegables["inferior"].abierto, ident)
            self.assertTrue(w.inferior.isVisible())
        w._mostrar_panel("inferior", False);QApplication.processEvents()
        e.seleccionar([t])
        w.diagrama.controlador = e
        QTest.keyClick(w.diagrama, Qt.Key.Key_Return);QApplication.processEvents()
        self.assertTrue(w._plegables["inferior"].abierto)

    def test_SAUC03_una_accion_nueva_no_abre_el_panel_plegado(self):
        """REQ-EDT-09: añadir una acción (que pide su editor) o soltar una transición nueva no despliega un panel plegado."""
        w, e = self.preparar()
        etapas, _ = self.ids(e)
        e.anadir_accion(etapas["1"]);QApplication.processEvents()
        self.assertTrue(w.inferior.isHidden())
        w._mostrar_panel("inferior", False);QApplication.processEvents()
        e.poner_transicion(QPointF(300, 300), pedir=True);QApplication.processEvents()  # soltar una transición de la paleta
        self.assertTrue(w.inferior.isHidden())
        # con el panel abierto, la petición lo deja abierto
        w._mostrar_panel("inferior", True);QApplication.processEvents()
        e.anadir_accion(etapas["2"]);QApplication.processEvents()
        self.assertTrue(w.inferior.isVisible())

    def test_SAUC04_con_el_panel_abierto_la_seleccion_lo_actualiza(self):
        """REQ-EDT-09: con el panel abierto, seleccionar cambia su página como siempre."""
        w, e = self.preparar()
        etapas, t = self.ids(e)
        w._mostrar_panel("inferior", True);QApplication.processEvents()
        e.seleccionar([t]);QApplication.processEvents()
        self.assertEqual(w.props.pagina, "transicion")
        e.seleccionar([etapas["1"]]);QApplication.processEvents()
        self.assertEqual(w.props.pagina, "etapa")


@unittest.skipUnless(QT, "requiere PySide6")
class PanelInferiorFijarYEsconder(BaseQt):
    """«Fijar» en el panel inferior de propiedades: sin fijar arranca plegado y se esconde solo al hacer clic en el dibujo
    fuera del elemento que muestra; fijado, no. Todo con clics reales sobre el controlador del dibujo."""

    def setUp(self):
        super().setUp()
        self.otras = []

    def tearDown(self):
        for v in self.otras:
            v.edicion = None;v.deleteLater()
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def ventana_con(self, **ajustes):
        """Una ventana nueva cuyo fichero de ajustes ya tiene estos valores (el del usuario no se toca)."""
        ini = Path(self.tmp.name) / f"arranque{len(self.otras)}.ini"
        a = QSettings(str(ini), QSettings.Format.IniFormat)
        for clave, valor in ajustes.items():
            a.setValue(clave.replace("__", "/"), valor)
        a.sync()
        from escritorio.ventana import Ventana
        v = Ventana(QSettings(str(ini), QSettings.Format.IniFormat))
        self.otras.append(v)
        return v

    def preparar(self):
        m = M().var("a").step("1", True).step("2").trans("t", ["1"], ["2"], "a")
        e = Edicion.desde(m.doc, {"1": (100, 80), "t": (100, 180), "2": (100, 280)}, "Panel")
        w = self.w
        w._establecer_edicion(e);w.resize(1366, 768);w.show();QApplication.processEvents()
        w._mostrar_panel("inferior", False);QApplication.processEvents()
        etapas = {s["label"]: s["id"] for s in e.M["steps"]}
        return w, e, etapas["1"], etapas["2"], e.M["transitions"][0]["id"]

    @staticmethod
    def clic(e, p):
        e.prensar(p);e.soltar(p)

    @staticmethod
    def doble_clic(e, p):
        """Lo que genera Qt: pulsar, soltar, doble clic, soltar."""
        e.prensar(p);e.soltar(p);e.doble(p);e.soltar(p)

    @staticmethod
    def esperar():
        QTest.qWait(QApplication.doubleClickInterval() + 150)
        QApplication.processEvents()

    FONDO = QPointF(600, 420)

    def abierto(self, w):
        return w._plegables["inferior"].abierto

    def test_SAUC31_arranca_plegado_y_sin_fijar_con_ajustes_vacios_o_antiguos(self):
        """REQ-EDT-09: con ajustes vacíos, o con un `paneles/inferior=True` antiguo sin `inferior_fijo`, el panel inferior de
        edición arranca plegado y «Fijar» desmarcado."""
        for ajustes in ({}, {"paneles__inferior": True}, {"paneles__inferior": True, "paneles__inferior_fijo": False}):
            v = self.ventana_con(**ajustes)
            self.assertFalse(v._plegables["inferior"].abierto, ajustes)
            self.assertFalse(v.a_inferior.isChecked())
            self.assertFalse(v.props.t_fijar.isChecked())

    def test_SAUC32_arranca_abierto_y_fijado_si_se_guardo_fijado(self):
        """REQ-EDT-09: con `paneles/inferior_fijo` y `paneles/inferior` en True arranca abierto y fijado; fijado pero con el
        panel plegado, arranca plegado (y fijado)."""
        v = self.ventana_con(paneles__inferior=True, paneles__inferior_fijo=True)
        self.assertTrue(v._plegables["inferior"].abierto)
        self.assertTrue(v.props.t_fijar.isChecked())
        v2 = self.ventana_con(paneles__inferior=False, paneles__inferior_fijo=True)
        self.assertFalse(v2._plegables["inferior"].abierto)
        self.assertTrue(v2.props.t_fijar.isChecked())

    def test_SAUC33_fijar_se_guarda_en_los_ajustes_y_tiene_su_tooltip(self):
        """REQ-EDT-09: «Fijar» es un botón marcable con su tooltip, visible sin nada seleccionado, y guarda `paneles/inferior_fijo`."""
        w, e, s1, s2, t = self.preparar()
        w._mostrar_panel("inferior", True);QApplication.processEvents()
        self.assertEqual(w.props.pagina, "vacio")
        b = w.props.t_fijar
        self.assertTrue(b.isVisible())
        self.assertEqual(b.text(), "Fijar")
        self.assertTrue(b.isCheckable())
        self.assertEqual(b.toolTip(), "Mantiene abierto este panel. Sin fijar, se esconde al hacer clic fuera del elemento.")
        self.assertFalse(w.ajustes.value("paneles/inferior_fijo", False, type=bool))
        b.click()
        self.assertTrue(w.ajustes.value("paneles/inferior_fijo", False, type=bool))
        b.click()
        self.assertFalse(w.ajustes.value("paneles/inferior_fijo", True, type=bool))
        self.assertFalse(hasattr(w.props, "t_previa"), "«Vista previa» ya no existe")

    def test_SAUC43_plegado_al_arrancar_no_deja_hueco_debajo_de_la_pestana(self):
        """REQ-EDT-09: con la ventana ya mostrada, y al agrandarla, el panel plegado es solo su pestaña pegada al borde inferior y el
        dibujo se queda con todo lo demás (antes quedaba un hueco vacío del alto del panel); seleccionar no lo cambia."""
        v = self.ventana_con()
        v.show();QTest.qWait(50)
        for ancho, alto in ((None, None), (1800, 1100)):
            if ancho:
                v.resize(ancho, alto);QTest.qWait(50)
            panel = v._plegables["inferior"]
            self.assertEqual(v.vsplit.sizes()[1], panel.GROSOR_PESTANA)
            self.assertEqual(panel.y() + panel.height(), v.vsplit.height())
        e = v.edicion
        s = e.poner_etapa(v.diagrama.mapToScene(300, 200));e.cambia()
        e.prensar(e.centro(s));e.soltar(e.centro(s));QTest.qWait(50)
        self.assertEqual(v.vsplit.sizes()[1], v._plegables["inferior"].GROSOR_PESTANA)
        e.ed.dirty = False;v.hide()

    def test_SAUC44_se_esconde_al_pulsar_sin_ensenar_la_pagina_nueva(self):
        """REQ-EDT-09: el clic fuera lo esconde al pulsar, sin esperas: no se ve antes el panel vacío ni el del otro elemento,
        y al abrirlo después recupera su altura."""
        w, e, s1, s2, t = self.preparar()
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        alto = w.vsplit.sizes()[1]
        self.assertGreater(alto, 32)
        e.prensar(self.FONDO)
        self.assertFalse(self.abierto(w), "ya al pulsar en el fondo")
        self.assertEqual(w.vsplit.sizes()[1], 32)
        e.soltar(self.FONDO)
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        self.assertTrue(self.abierto(w))
        e.prensar(e.centro(t))
        self.assertFalse(self.abierto(w), "ya al pulsar en otro elemento")
        e.soltar(e.centro(t))

    def test_SAUC45_el_aviso_de_no_poner_encima_no_se_queda_cuando_ya_no_es_cierto(self):
        """REQ-EDT-09: arrastrar una ficha por encima de un elemento avisa; al llegar a un hueco el aviso se va, y el de una
        ficha rechazada se va con el siguiente clic en el dibujo."""
        w, e, s1, s2, t = self.preparar()
        encima, hueco = e.centro(s1), self.FONDO
        self.assertFalse(e.sobrevolar("etapa", encima))
        self.assertEqual(e.mensaje, "No se puede poner encima de otro elemento")
        self.assertTrue(e.sobrevolar("etapa", hueco))
        self.assertEqual(e.mensaje, "")
        e.colocar("etapa", encima)
        self.assertEqual(e.mensaje, "No se puede poner encima de otro elemento")
        self.clic(e, hueco)
        self.assertEqual(e.mensaje, "")

    def test_SAUC34_el_doble_clic_abre_y_el_clic_en_el_fondo_lo_esconde(self):
        """REQ-EDT-09: doble clic en una etapa abre el panel; un clic en el fondo lo esconde."""
        w, e, s1, s2, t = self.preparar()
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        self.assertTrue(self.abierto(w))
        self.assertEqual(w.props.pagina, "etapa")
        self.esperar()
        self.assertTrue(self.abierto(w), "el doble clic lo deja abierto")
        self.clic(e, self.FONDO)
        QApplication.processEvents()
        self.assertEqual(e.sel, [])
        self.assertFalse(self.abierto(w))
        self.assertTrue(w.inferior.isHidden())

    def test_SAUC35_el_clic_en_el_mismo_elemento_no_lo_esconde_y_en_otro_si(self):
        """REQ-EDT-09: un clic en el mismo elemento (o arrastrarlo) no esconde el panel; un clic en otro elemento, sí."""
        w, e, s1, s2, t = self.preparar()
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        self.clic(e, e.centro(s1));self.esperar()
        self.assertTrue(self.abierto(w), "mismo elemento")
        p = e.centro(s1)
        e.prensar(p);e.mover(p + QPointF(0, 40));e.soltar(p + QPointF(0, 40));self.esperar()
        self.assertTrue(self.abierto(w), "arrastrar el mismo elemento")
        self.clic(e, e.centro(t));self.esperar()
        self.assertFalse(self.abierto(w), "otro elemento")
        self.assertEqual(e.sel, [t])

    def test_SAUC36_el_lazo_que_cambia_la_seleccion_esconde_el_panel(self):
        """REQ-EDT-09: seleccionar con lazo otros elementos esconde el panel sin fijar."""
        w, e, s1, s2, t = self.preparar()
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        a, b = QPointF(20, 230), QPointF(300, 340)  # alrededor de la etapa 2
        e.prensar(a);e.mover(b);e.soltar(b);self.esperar()
        self.assertIn(s2, e.sel)
        self.assertFalse(self.abierto(w))

    def test_SAUC37_el_doble_clic_en_otro_elemento_cambia_el_contenido_sin_cerrar(self):
        """REQ-EDT-09: con el panel abierto, un doble clic en otro elemento no lo hace parpadear: cambia de contenido y sigue abierto."""
        w, e, s1, s2, t = self.preparar()
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        self.assertEqual(w.props.pagina, "etapa")
        self.doble_clic(e, e.centro(t))
        self.esperar()
        self.assertTrue(self.abierto(w))
        self.assertEqual(w.props.pagina, "transicion")

    def test_SAUC38_fijado_ningun_clic_lo_esconde_pero_la_flecha_y_ctrl_j_si_lo_pliegan(self):
        """REQ-EDT-09: fijado, ni el fondo ni otro elemento lo esconden y la selección lo actualiza; la flecha y Ctrl+J lo
        pliegan y sigue fijado."""
        w, e, s1, s2, t = self.preparar()
        w.props.t_fijar.setChecked(True)
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        self.clic(e, self.FONDO);self.esperar()
        self.assertTrue(self.abierto(w), "fondo")
        self.clic(e, e.centro(t));self.esperar()
        self.assertTrue(self.abierto(w), "otro elemento")
        self.assertEqual(w.props.pagina, "transicion", "la selección lo actualiza")
        w.flechas["inferior"].click();QApplication.processEvents()
        self.assertFalse(self.abierto(w), "la flecha lo pliega")
        self.assertTrue(w.props.t_fijar.isChecked(), "y sigue fijado")
        w.a_inferior.setChecked(True);QApplication.processEvents()  # lo mismo que Ctrl+J
        self.assertTrue(self.abierto(w))
        w.a_inferior.setChecked(False);QApplication.processEvents()
        self.assertFalse(self.abierto(w))
        self.assertTrue(w.props.t_fijar.isChecked())

    def test_SAUC39_un_clic_dentro_del_panel_o_en_variables_no_lo_esconde(self):
        """REQ-EDT-09: un clic en la lista de variables, en el propio panel o en la paleta no esconde el panel sin fijar."""
        w, e, s1, s2, t = self.preparar()
        self.doble_clic(e, e.centro(s1));QApplication.processEvents()
        for widget in (w.variables, w.props.cabecera, w.props.s_etiqueta, w.paleta.viewport()):
            QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
            self.esperar()
            self.assertTrue(self.abierto(w), widget)

    def test_SAUC40_seleccionar_con_el_panel_plegado_no_lo_abre_ni_parpadea(self):
        """REQ-EDT-09: un clic que selecciona, con el panel plegado, no lo abre ni deja rastro de parpadeo en la pestaña."""
        w, e, s1, s2, t = self.preparar()
        self.clic(e, e.centro(s1));self.esperar()
        self.clic(e, e.centro(t));self.esperar()
        self.assertEqual(e.sel, [t])
        self.assertFalse(self.abierto(w))
        self.assertFalse(hasattr(w.pestanas["inferior"], "destellos"))
        self.assertFalse(hasattr(w.pestanas["inferior"], "_reloj"))

    def test_SAUC41_al_esconderlo_el_dibujo_no_salta(self):
        """REQ-EDT-09: al esconderse el panel, los puntos de la escena siguen en el mismo sitio de la pantalla."""
        w, e, s1, s2, t = self.preparar()
        self.doble_clic(e, e.centro(s1))
        for _ in range(8):
            QApplication.processEvents()
        d = w.diagrama
        puntos = [QPointF(100, 80), QPointF(100, 280), QPointF(0, 0), QPointF(300, 150)]
        antes = [d.viewport().mapToGlobal(d.mapFromScene(p)) for p in puntos]
        alto = d.viewport().height()
        self.clic(e, self.FONDO);self.esperar()
        self.assertFalse(self.abierto(w))
        self.assertGreater(d.viewport().height(), alto, "el dibujo gana el alto del panel")
        self.assertEqual([d.viewport().mapToGlobal(d.mapFromScene(p)) for p in puntos], antes)

    def test_SAUC42_al_volver_de_simular_el_panel_solo_sigue_abierto_si_estaba_fijado(self):
        """REQ-EDT-09: al volver de simular, un panel abierto sin fijar vuelve plegado y uno fijado vuelve abierto."""
        w, e, s1, s2, t = self.preparar()
        for fijo in (False, True):
            w.props.t_fijar.setChecked(fijo)
            self.doble_clic(e, e.centro(s1));QApplication.processEvents()
            self.assertTrue(self.abierto(w))
            self.assertTrue(w.cambiar_modo("simular"))
            QApplication.processEvents()
            self.assertTrue(w.cambiar_modo("editar"))
            for _ in range(4):
                QApplication.processEvents()
            self.assertEqual(self.abierto(w), fijo, fijo)
            w._mostrar_panel("inferior", False)


@unittest.skipUnless(QT, "requiere PySide6")
class EtapasConElMismoNumero(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def tres_etapas(self):
        """1 -t1-> 2 -t2-> 3, con t1 = a AND X2 y t2 = 3s/X3 (escrita en el editor, ligada por ID)."""
        w, e = self.vacio()
        s1 = e.ed.add_step("g", "1", True, at=(100, 80))
        s2 = e.ed.add_step("g", "2", at=(100, 280))
        s3 = e.ed.add_step("g", "3", at=(100, 480))
        t1, _ = e.ed.add_transition("g", "", [s1], [s2], at=(100, 180), label="t1")
        t2, _ = e.ed.add_transition("g", "", [s2], [s3], at=(100, 380), label="t2")
        e.ed.add_variable("a", "input", {"kind": "bool"})
        e.cambia()
        e.poner_condicion(t1, "a AND X2")
        e.poner_condicion(t2, "3s/X3")
        return w, e, (s1, s2, s3), (t1, t2)

    def expresiones(self, e):
        return {x["id"]: (x["text"], dict(x["bindings"])) for x in e.ed.model["expressions"]}

    def test_SAUC05_un_numero_repetido_se_admite_y_se_marca_como_error(self):
        """REQ-EDT-09, REQ-MOD-06: el número de una etapa puede coincidir con otro; se avisa en palabras y Play no arranca."""
        w, e, (s1, s2, s3), (t1, t2) = self.tres_etapas()
        self.assertIsNone(e.renombrar(s2, "3"))
        self.assertEqual({e.ed.get(s2)["label"], e.ed.get(s3)["label"]}, {"3"})
        self.assertEqual({x["label"] for x in e.M["steps"] if x["id"] in (s2, s3)}, {"3"}, "el dibujo enseña «3» en las dos")
        diags = [d for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["message"], "Hay dos etapas con el número 3: cambie una.")
        self.assertEqual(set(diags[0]["targets"]), {s2, s3})
        self.assertTrue(diags[0]["blocks"])
        self.assertLessEqual({s2, s3}, e.marcados())
        # el núcleo sigue rechazando el modelo: no compila ni se puede simular
        self.assertTrue(any(d.code == "D-NOMBRE-COLISION" for d in e.ed.validate().diagnostics))
        avisos = []
        from unittest import mock
        with mock.patch("escritorio.ventana.QMessageBox.warning", lambda *a: avisos.append(a[2])):
            self.assertFalse(w._preparar_sesion())
        self.assertIn("Hay dos etapas con el número 3: cambie una.", avisos[0])

    def test_SAUC06_las_expresiones_siguen_ligadas_por_id_y_al_renombrar_de_vuelta_todo_cuadra(self):
        """REQ-MOD-06: mientras el número está repetido, X2 y X3 siguen ligadas a sus etapas; al corregirlo, el texto se reescribe."""
        w, e, (s1, s2, s3), (t1, t2) = self.tres_etapas()
        antes = self.expresiones(e)
        e.renombrar(s2, "3")
        despues = self.expresiones(e)
        self.assertEqual(despues, antes, "nada se reescribe ni se vuelve a ligar mientras hay dos «3»")
        ligadas = {i for _, b in despues.values() for i in b.values()}
        self.assertIn(s2, ligadas)
        self.assertIn(s3, ligadas)
        # otra edición ajena (renombrar la transición) no toca nada
        e.renombrar(t1, "T9")
        self.assertEqual(self.expresiones(e), antes)
        # corregir el repetido: se reescribe con los nombres de ahora y todo vuelve a compilar
        self.assertIsNone(e.renombrar(s2, "7"))
        self.assertEqual([d for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"], [])
        textos = [t for t, _ in self.expresiones(e).values()]
        self.assertTrue(any("7" in t for t in textos), textos)
        self.assertFalse(any("active(`2`)" in t for t in textos), textos)
        self.assertEqual(e.ed.get(t1)["preRefs"], [s1])
        self.assertFalse(any(d["blocks"] for d in e.diagnosticos()), e.diagnosticos())
        # y de vuelta al 2 queda como al principio
        e.renombrar(s2, "2")
        self.assertEqual(self.expresiones(e), antes)

    def test_SAUC07_una_referencia_nueva_a_un_numero_repetido_no_se_liga_a_ninguna_etapa(self):
        """REQ-MOD-06: escribir X3 con dos etapas «3» no se liga a la equivocada: queda como texto pendiente y se avisa."""
        w, e, (s1, s2, s3), (t1, t2) = self.tres_etapas()
        e.renombrar(s2, "3")
        e.poner_condicion(t1, "a AND X3")
        exp = e.ed.get(e.ed.get(t1)["conditionRef"])
        self.assertEqual(exp["mode"], "descriptive")
        self.assertTrue(any(d["code"] == "D-EXP-PENDIENTE" for d in e.diagnosticos()))

    def test_SAUC08_se_guarda_y_se_abre_con_el_numero_repetido(self):
        """REQ-DAT-02: un proyecto con dos etapas con el mismo número se guarda, se abre igual y sigue sin poder simularse."""
        from escritorio.edicion import Edicion
        from grafcet.persistence import open_model
        from grafcet.view import layout_from_presentation
        w, e, (s1, s2, s3), (t1, t2) = self.tres_etapas()
        e.renombrar(s2, "3")
        with tempfile.TemporaryDirectory() as tmp:
            e.guardar(Path(tmp) / "proyecto")
            op = open_model(Path(tmp) / "proyecto")
            otro = Edicion.desde(op.doc, layout_from_presentation(op.presentations[0]), op.title,
                                 presentacion=op.presentations[0])
        self.assertEqual({otro.ed.get(s2)["label"], otro.ed.get(s3)["label"]}, {"3"})
        self.assertEqual(self.expresiones(otro), self.expresiones(e))
        self.assertEqual(len([d for d in otro.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"]), 1)
        self.assertEqual(otro.renombrar(s2, "2"), None)
        self.assertFalse(any(d["blocks"] for d in otro.diagnosticos()))

    def test_SAUC09_el_dibujo_marca_las_dos_etapas_y_el_resto_de_nombres_sigue_siendo_unico(self):
        """REQ-EDT-09: las dos etapas salen marcadas en rojo; una variable o un parcial repetidos siguen rechazándose."""
        w, e, (s1, s2, s3), (t1, t2) = self.tres_etapas()
        e.renombrar(s2, "3")
        w.refrescar_edicion()
        self.assertEqual(set(e.marcados()) & {s2, s3}, {s2, s3})
        e.ed.add_variable("b", "input", {"kind": "bool"})
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "b")
        from grafcet.diagnostics import DiagnosticError
        with self.assertRaises(DiagnosticError):
            e.ed.rename(vid, "a")
        with self.assertRaises(DiagnosticError):
            e.ed.rename(s2, "1")  # sin permiso explícito, el núcleo sigue rechazándolo


@unittest.skipUnless(QT, "requiere PySide6")
class UnirEnlacesConLibertad(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def cadena(self, n=5):
        """E0 -t1-> E1 -t2-> E2 ... (n etapas), con las transiciones en el punto medio, a 60 de cada etapa."""
        w, e = self.vacio()
        S = [e.ed.add_step("g", str(i), i == 0, at=(100, 60 + 120 * i)) for i in range(n)]
        T = [e.ed.add_transition("g", "", [S[i]], [S[i + 1]], at=(100, 120 + 120 * i), label=f"t{i + 1}")[0]
             for i in range(n - 1)]
        e.cambia()
        return w, e, S, T

    @staticmethod
    def punto(e, ident, lado):
        from escritorio.diagrama import anclas
        return next(a for a in anclas(e.M, ident) if a["lado"] == lado)["pos"]

    @staticmethod
    def arrastrar(e, p0, p1):
        """El gesto real: prensar, varios mover y soltar."""
        e.prensar(p0)
        for k in range(1, 7):
            e.mover(p0 + (p1 - p0) * k / 6)
        e.soltar(p1)

    @staticmethod
    def modelo(e):
        return [(t["id"], list(t["preRefs"]), list(t["postRefs"])) for t in e.ed.model["transitions"]]

    def test_SAUC10_salida_de_una_transicion_junto_a_otra_se_une_a_su_etapa_siguiente(self):
        """REQ-EDT-02, REQ-MOD-03: la salida de una transición soltada justo debajo de t1 (junto a su tallo, encima de su
        enlace con la etapa 1) es una convergencia: la transición pasa a tener la etapa 1 como siguiente."""
        w, e, S, T = self.cadena()
        t1 = e.layout()[T[0]]
        for dy in range(21, 42, 2):  # todo el tramo entre el tallo de t1 y la etapa 1
            nueva, _ = e.ed.add_transition("g", "", [S[4]], [], at=(100, 600), label="T")
            e.cambia()
            n = len(e.ed.undo_stack)
            self.arrastrar(e, self.punto(e, nueva, "abajo"), QPointF(t1[0] + 100, t1[1] + dy))
            self.assertEqual(e.ed.get(nueva)["postRefs"], [S[1]], f"dy={dy}: {e.mensaje}")
            self.assertEqual(e.ed.model["draftLinks"], [])
            self.assertEqual(sorted(t["id"] for t in e.ed.model["transitions"] if S[1] in t["postRefs"]),
                             sorted([T[0], nueva]))
            self.assertEqual(e.mensaje, "")
            self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación de deshacer")
            e.deshacer()
            e.deshacer()  # y la transición nueva

    def test_SAUC11_una_etapa_a_una_transicion_con_etapa_anterior_es_un_borrador(self):
        """REQ-EDT-09, REQ-MOD-03: soltar la salida de la etapa 3 sobre el enlace de la etapa 1 a su transición (o junto a
        sus puntos de unión) no crea un enlace de modelo: deja un borrador en rojo discontinuo, avisado, que impide simular."""
        from grafcet.routing import enlaces
        w, e, S, T = self.cadena()
        antes = self.modelo(e)
        pre = next(x for x in enlaces(e.M) if x["id"] == f"{T[1]}|{S[1]}|pre")
        ax = pre["pts"][0][0]
        arriba = self.punto(e, T[1], "arriba").y()  # entre la etapa 1 (su salida, a 202) y la entrada de t2 (a 216)
        for y in (arriba - 7, arriba - 3, arriba + 1):  # sobre el enlace, y en la zona del punto de unión de t2
            n = len(e.ed.undo_stack)
            self.arrastrar(e, self.punto(e, S[3], "abajo"), QPointF(ax, y))
            self.assertEqual(self.modelo(e), antes, f"y={y}: el modelo no cambia")
            self.assertEqual([(d["fromRef"], d["toRef"]) for d in e.ed.model["draftLinks"]], [(S[3], T[1])],
                             f"y={y}: {e.mensaje}")
            self.assertEqual(len(e.ed.undo_stack), n + 1)
            self.assertEqual(len(e.M["drafts"]), 1, "se dibuja como borrador (rojo discontinuo)")
            diag = [d for d in e.diagnosticos() if d["code"] == "D-SIMULTANEIDAD"]
            self.assertEqual(len(diag), 1)
            self.assertTrue(diag[0]["blocks"])
            self.assertIn("llega a la transición", diag[0]["message"])
            self.assertIn("ya tiene otra etapa anterior: use una barra de simultaneidad.", diag[0]["message"])
            self.assertIn("simultaneidad", e.mensaje)
            self.assertNotIn("Una rama se une", e.mensaje)
            e.deshacer()
            self.assertEqual(e.ed.model["draftLinks"], [])
            e.rehacer()
            self.assertEqual(len(e.ed.model["draftLinks"]), 1)
            e.seleccionar([e.ed.model["draftLinks"][0]["id"]])
            self.assertTrue(e.borrar())
            self.assertEqual(e.ed.model["draftLinks"], [], "se puede quitar")
            self.assertEqual(self.modelo(e), antes)

    def test_SAUC12_el_borrador_de_simultaneidad_impide_play_se_guarda_y_se_abre(self):
        """REQ-DAT-02, REQ-SIM-08: Play lo rechaza con el aviso; el archivo guardado y reabierto conserva el borrador."""
        from escritorio.edicion import Edicion
        from grafcet.persistence import open_model
        from grafcet.view import layout_from_presentation
        from unittest import mock
        w, e, S, T = self.cadena(4)
        for t in T:
            e.poner_condicion(t, "true")
        e.cambia()
        self.assertFalse(any(d["blocks"] for d in e.diagnosticos()), "antes del borrador, el grafcet se puede simular")
        e.borrador_simultaneidad(S[2], T[0])
        avisos = []
        with mock.patch("escritorio.ventana.QMessageBox.warning", lambda *a: avisos.append(a[2])):
            self.assertFalse(w._preparar_sesion())
        self.assertIn("ya tiene otra etapa anterior", avisos[0])
        with tempfile.TemporaryDirectory() as tmp:
            e.guardar(Path(tmp) / "proyecto")
            op = open_model(Path(tmp) / "proyecto")
            otro = Edicion.desde(op.doc, layout_from_presentation(op.presentations[0]), op.title,
                                 presentacion=op.presentations[0])
        self.assertEqual([(d["fromRef"], d["toRef"]) for d in otro.ed.model["draftLinks"]], [(S[2], T[0])])
        self.assertTrue(any(d["code"] == "D-SIMULTANEIDAD" and d["blocks"] for d in otro.diagnosticos()))
        self.assertEqual(len(otro.M["drafts"]), 1)

    def test_SAUC13_dos_transiciones_ya_con_etapas_se_unen_como_borrador(self):
        """REQ-EDT-02, REQ-EDT-09: unir dos transiciones existentes (con etapas) no se rechaza: queda un borrador por la
        alternancia, igual que dos etapas seguidas o dos transiciones nuevas seguidas; Play lo rechaza."""
        from unittest import mock
        w, e, S, T = self.cadena()
        antes = self.modelo(e)
        for a, lado_a, b, lado_b in ((T[0], "abajo", T[2], "arriba"), (T[2], "arriba", T[0], "abajo"),
                                     (T[1], "abajo", T[0], "arriba")):
            n = len(e.ed.undo_stack)
            self.arrastrar(e, self.punto(e, a, lado_a), self.punto(e, b, lado_b))
            self.assertEqual(self.modelo(e), antes)
            self.assertEqual(len(e.ed.model["draftLinks"]), 1, f"{a[:6]}→{b[:6]}: {e.mensaje}")
            self.assertEqual(len(e.ed.undo_stack), n + 1)
            self.assertIn("dos elementos del mismo tipo", e.mensaje)
            self.assertIn("D-ALTERNANCIA", [d["code"] for d in e.diagnosticos()])
            e.deshacer()
            self.assertEqual(e.ed.model["draftLinks"], [])
        e.conectar(T[0], T[2])  # la misma pareja por la API
        self.assertEqual(len(e.ed.model["draftLinks"]), 1)
        avisos = []
        with mock.patch("escritorio.ventana.QMessageBox.warning", lambda *a: avisos.append(a[2])):
            self.assertFalse(w._preparar_sesion())
        self.assertTrue(avisos)

    def test_SAUC14_una_etapa_a_una_transicion_sin_etapa_anterior_se_une_de_verdad(self):
        """REQ-EDT-02: lo que sí es válido sigue uniéndose: una etapa a una transición sin etapa anterior."""
        w, e, S, T = self.cadena()
        libre = e.poner_transicion(QPointF(100 + 300, 300))
        self.arrastrar(e, self.punto(e, S[3], "abajo"), self.punto(e, libre, "arriba"))
        self.assertEqual(e.ed.get(libre)["preRefs"], [S[3]])
        self.assertEqual(e.ed.model["draftLinks"], [])


@unittest.skipUnless(QT, "requiere PySide6")
class ConectoresSolapados(BaseQt):
    """El tramo que se arrastra a mano se queda donde se suelta y ningún otro enlace se mueve por ello (P-IMP-118)."""

    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def escenario(self):
        """E0..E5 en cadena, dos retornos automáticos (E5→E0 y E4→E1) y un salto de E1 a E3."""
        from escritorio.diagrama import anclas
        w, e = self.vacio()
        S = [e.ed.add_step("g", str(i), i == 0, at=(100, 60 + 120 * i)) for i in range(6)]
        for i in range(5):
            e.ed.add_transition("g", "", [S[i]], [S[i + 1]], at=(100, 120 + 120 * i), label=f"t{i + 1}")
        e.cambia()
        punto = lambda i, lado: next(a for a in anclas(e.M, i) if a["lado"] == lado)["pos"]
        for a, b in ((5, 0), (4, 1), (1, 3)):
            e.prensar(punto(S[a], "abajo"))
            e.soltar(punto(S[b], "abajo"))
        return w, e, S

    @staticmethod
    def recorridos(e, menos=None):
        from grafcet.routing import enlaces
        return {r["id"]: [tuple(p) for p in r["pts"]] for r in enlaces(e.M) if r["id"] != menos}

    def arrastrar(self, e, ruta, i, objetivo, k=0.2):
        """Agarra el tramo `i` del enlace (en un punto que no es su flecha) y lo lleva a `objetivo`; comprueba que durante el
        arrastre ningún otro enlace se mueve."""
        a, b = ruta["pts"][i], ruta["pts"][i + 1]
        vertical = a[0] == b[0]
        p0 = QPointF(a[0] + k * (b[0] - a[0]), a[1] + k * (b[1] - a[1]))
        p1 = QPointF(objetivo, p0.y()) if vertical else QPointF(p0.x(), objetivo)
        e.sel = []
        e.prensar(p0)
        if (e.arrastre or {}).get("tipo") != "tramo":  # ahí hay otra cosa encima (otro enlace, una caja): no se agarra el tramo
            e.arrastre = None
            return None
        antes = self.recorridos(e, ruta["id"])
        for j in range(1, 7):
            e.mover(p0 + (p1 - p0) * j / 6)
            self.assertEqual(self.recorridos(e, ruta["id"]), antes, "ningún otro enlace se mueve durante el arrastre")
        e.soltar(p1)
        return antes

    def test_SAUC15_un_carril_arrastrado_sobre_otro_enlace_se_queda_y_el_otro_no_huye(self):
        """REQ-EDT-02: el carril de un retorno llevado sobre el de otro (automático o ya colocado a mano) queda donde se suelta
        (en la rejilla); el otro no se mueve ni durante el arrastre, ni al soltar, ni tras otra edición."""
        from escritorio.diagrama import SX
        from grafcet.routing import enlaces
        w, e, S = self.escenario()
        retornos = [r for r in enlaces(e.M) if r["rol"] == "post" and len(r["pts"]) == 6]
        self.assertEqual(len(retornos), 2)
        exterior, interior = sorted(retornos, key=lambda r: r["pts"][2][0])
        for movido, fijo in ((interior, exterior), (exterior, interior)):
            x_fijo = fijo["pts"][2][0]
            otros = self.arrastrar(e, movido, 2, x_fijo)
            self.assertIsNotNone(otros, "el carril se agarra")
            self.assertEqual(self.recorridos(e, movido["id"]), otros, "al soltar, el otro sigue donde estaba")
            nuevo = next(r for r in enlaces(e.M) if r["id"] == movido["id"])
            self.assertNotEqual(x_fijo % 20, 0, "el carril automático no está en la rejilla")
            self.assertEqual(nuevo["pts"][2][0], x_fijo, "queda exactamente sobre el otro carril (a menos de media rejilla)")
            self.assertEqual(nuevo["pts"][2][0], SX + float(e.ed.link_styles()[movido["id"]]["route"]["laneX"]))
            e.ed.move(S[2], 100, 300)  # una edición posterior vuelve a calcular los recorridos
            e.cambia()
            self.assertEqual(self.recorridos(e, movido["id"]), otros)
            self.assertEqual(next(r for r in enlaces(e.M) if r["id"] == movido["id"])["pts"][2][0], nuevo["pts"][2][0])
            e.deshacer()  # el movimiento de la etapa
            e.deshacer()  # y el del tramo

    def test_SAUC16_un_tramo_horizontal_de_un_salto_sobre_otro_enlace_tampoco_mueve_a_los_demas(self):
        """REQ-EDT-02: igual con los tramos horizontales (salida y entrada de un retorno, tramo medio de un salto): se quedan
        donde se sueltan y no mueven a otro enlace."""
        from grafcet.routing import enlaces
        w, e, S = self.escenario()
        n = 0
        for ruta in list(enlaces(e.M)):
            for h in ruta["handles"]:
                i = h["segment"]
                a, b = ruta["pts"][i], ruta["pts"][i + 1]
                if a[0] == b[0]:
                    continue
                ajenos = [(c, d) for r in enlaces(e.M) if r["id"] != ruta["id"]
                          for c, d in zip(r["pts"], r["pts"][1:]) if c[1] == d[1] and c != d]
                if not ajenos:
                    continue
                bajo, alto = ruta["pts"][0][1] + ruta["tallos"][0], ruta["pts"][-1][1] - ruta["tallos"][1]
                if len(ruta["pts"]) == 6 and i in (1, 3):
                    continue  # (salida y entrada de un retorno: su tope es el tallo mínimo, geometría y no vecinos)
                # sobre cada tramo horizontal ajeno que cae en su recorrido permitido, y en medio si no hay ninguno
                destinos = {c[1] for c, _ in ajenos if bajo <= c[1] <= alto} or {round((bajo + alto) / 40) * 20}
                for objetivo in sorted(destinos):
                    otros = self.arrastrar(e, ruta, i, objetivo)
                    if otros is None:
                        continue
                    self.assertEqual(self.recorridos(e, ruta["id"]), otros)
                    nuevo = next(r for r in enlaces(e.M) if r["id"] == ruta["id"])
                    self.assertLessEqual(abs(nuevo["pts"][i][1] - objetivo), 10, f"{i} {objetivo}")
                    e.deshacer()
                    n += 1
        self.assertGreaterEqual(n, 2, "se probaron tramos horizontales")


    def test_SAUC21_el_tramo_pegado_a_otro_se_guarda_se_abre_y_se_deshace_y_lejos_sigue_la_rejilla(self):
        """REQ-EDT-02, REQ-DAT-02: a menos de media rejilla de un tramo paralelo ajeno se pega exacto; más lejos, a la rejilla;
        la coordenada exacta viaja en el archivo y Deshacer la quita."""
        from escritorio.diagrama import SX
        from escritorio.edicion import Edicion
        from grafcet.persistence import open_model
        from grafcet.routing import enlaces
        from grafcet.view import layout_from_presentation
        w, e, S = self.escenario()
        retornos = sorted((r for r in enlaces(e.M) if r["rol"] == "post" and len(r["pts"]) == 6), key=lambda r: r["pts"][2][0])
        exterior, interior = retornos
        x = exterior["pts"][2][0]
        self.arrastrar(e, interior, 2, x + 9)  # a 9 del carril ajeno: se pega
        r = next(q for q in enlaces(e.M) if q["id"] == interior["id"])
        self.assertEqual(r["pts"][2][0], x)
        guardado = e.ed.link_styles()[interior["id"]]["route"]["laneX"]
        with tempfile.TemporaryDirectory() as tmp:
            e.guardar(Path(tmp) / "proyecto")
            op = open_model(Path(tmp) / "proyecto")
            otro = Edicion.desde(op.doc, layout_from_presentation(op.presentations[0]), op.title, presentacion=op.presentations[0])
        self.assertEqual(otro.ed.link_styles()[interior["id"]]["route"]["laneX"], guardado)
        self.assertEqual(next(q for q in enlaces(otro.M) if q["id"] == interior["id"])["pts"][2][0], x)
        e.deshacer()
        self.assertNotIn(interior["id"], e.ed.link_styles())
        r = next(q for q in enlaces(e.M) if q["id"] == interior["id"])
        self.arrastrar(e, r, 2, x + 18)  # a más de media rejilla de todo carril ajeno: a la rejilla
        r = next(q for q in enlaces(e.M) if q["id"] == interior["id"])
        self.assertEqual(r["pts"][2][0] % 20, 0)


@unittest.skipUnless(QT, "requiere PySide6")
class SensibilidadDeTirarDeUnaAccion(BaseQt):
    """Tirar del borde de una acción se agarra a la misma distancia (en píxeles de pantalla, a cualquier zoom y a los dos
    lados del borde) que tirar de una transición desde una etapa o de una etapa desde una transición (P-IMP-118)."""

    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def montar(self):
        from escritorio.diagrama import anclas
        w, e = self.vacio()
        w.resize(1200, 800);w.show();QApplication.processEvents()
        s1 = e.ed.add_step("g", "1", True, at=(100, 80))
        s2 = e.ed.add_step("g", "2", at=(400, 80))
        t = e.ed.add_transition("g", "", [], [], at=(250, 300), label="t1")[0]
        e.cambia()
        e.pedir_accion = lambda sid, aid: None
        did = e.anadir_accion(s1)
        QApplication.processEvents()
        self.anclas = anclas
        return w, e, s1, s2, t, did

    def agarra(self, e, p, nueva):
        """Si pulsar en p agarra el punto de unión (o el borde de la acción, con `nueva`)."""
        e.enlace = e.arrastre = e.lazo = None
        e.prensar(p)
        r = bool(e.enlace) and bool(e.enlace.get("nueva")) == nueva
        e.enlace = e.arrastre = e.lazo = None
        e.sel, e.accion = [], None
        return r

    def alcance(self, e, p0, direccion, nueva, zoom):
        """La mayor distancia, en píxeles de pantalla, a lo largo de `direccion` a la que aún se agarra."""
        mejor, d = -1.0, 0.0
        while d <= 60:
            if self.agarra(e, p0 + direccion * (d / zoom), nueva):
                mejor = d
            d += 0.5
        return mejor

    def test_SAUC17_el_borde_de_una_accion_se_agarra_a_la_misma_distancia_que_un_punto_de_union(self):
        """REQ-EDT-02: a 50 %, 100 % y 150 %, el alcance del borde derecho de una acción (por fuera y por dentro) es el de la
        salida de una transición, y crece con el zoom igual que él."""
        w, e, s1, s2, t, did = self.montar()
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == did)["rect"]
        for zoom in (0.5, 1.0, 1.5):
            w.diagrama.resetTransform();w.diagrama.scale(zoom, zoom);QApplication.processEvents()
            ancla = self.alcance(e, self.anclas(e.M, t)[1]["pos"], QPointF(1, 0), False, zoom)
            self.assertAlmostEqual(ancla, 14 * zoom, delta=1, msg=f"zoom {zoom}")
            x, y, ancho, alto = caja
            borde = QPointF(x + ancho, y + alto / 2)
            fuera = self.alcance(e, borde, QPointF(1, 0), True, zoom)
            dentro = self.alcance(e, borde, QPointF(-1, 0), True, zoom)
            self.assertAlmostEqual(fuera, ancla, delta=1, msg=f"fuera, zoom {zoom}")
            self.assertAlmostEqual(dentro, ancla, delta=1, msg=f"dentro, zoom {zoom}")

    def test_SAUC18_el_cuerpo_de_la_accion_sigue_seleccionando_y_el_borde_ensanchado_no_crea_sin_arrastrar(self):
        """REQ-EDT-02: el centro de la acción no es un borde (selecciona), un clic en el borde ensanchado solo selecciona y
        solo arrastrar crea otra acción; fuera del alcance no se agarra nada."""
        w, e, s1, s2, t, did = self.montar()
        x, y, ancho, alto = next(c for c in w.diagrama.cajas_acciones if c["id"] == did)["rect"]
        self.assertFalse(self.agarra(e, QPointF(x + ancho / 2, y + alto / 2), True), "el cuerpo no es un borde")
        self.assertFalse(self.agarra(e, QPointF(x + ancho + 20, y + alto / 2), True), "lejos del borde no se agarra")
        n = len(e.ed.draft_actions())
        for dx in (-12, 10):  # por dentro y por fuera, más allá de lo que antes se agarraba (6 px por dentro)
            p = QPointF(x + ancho + dx, y + alto / 2)
            e.prensar(p)
            e.soltar(p)
            self.assertEqual(len(e.ed.draft_actions()), n, "un clic no crea nada")
            e.prensar(p)
            e.mover(p + QPointF(30, 0))
            e.soltar(p + QPointF(60, 0))
            self.assertEqual(len(e.ed.draft_actions()), n + 1, f"arrastrar desde dx={dx} crea otra acción")
            e.deshacer()
        # el cuerpo se sigue arrastrando para mover o seleccionar, no crea
        c = QPointF(x + ancho / 2, y + alto / 2)
        e.prensar(c)
        e.mover(c + QPointF(60, 0))
        e.soltar(c + QPointF(60, 0))
        self.assertEqual(len(e.ed.draft_actions()), n)


@unittest.skipUnless(QT, "requiere PySide6")
class PanelesMasCompactos(BaseQt):
    """Menos capas de cabecera antes del contenido (P-IMP-118): antes, 157 px sobre el dibujo y 40 px (65 en una transición)
    del borde del panel inferior a su primer control, a 1366×768."""

    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def preparar(self):
        from PySide6.QtCore import QPoint
        m = M().var("a").step("1", True).step("2").trans("t", ["1"], ["2"], "a")
        e = Edicion.desde(m.doc, {"1": (100, 80), "t": (100, 180), "2": (100, 280)}, "Medida")
        w = self.w
        w._establecer_edicion(e);w.resize(1366, 768);w.show();w._mostrar_panel("inferior", True)
        for _ in range(6):
            QApplication.processEvents()
        y = lambda wd: wd.mapTo(w, QPoint(0, 0)).y()
        return w, e, y

    def test_SAUC19_la_cabecera_del_panel_inferior_es_una_sola_fila_y_hay_menos_capas_sobre_el_dibujo(self):
        """REQ-EDT-09: el título, «Fijar» y lo demás de la cabecera comparten fila; el primer control queda a menos de
        32 px del borde del panel, la paleta de bloques de una transición también, y el dibujo empieza antes de los 140 px."""
        w, e, y = self.preparar()
        self.assertLessEqual(y(w.diagrama), 150, "antes, 157 (con el zoom siempre en la cabecera)")
        etapa = [s["id"] for s in e.M["steps"] if s["label"] == "1"][0]
        e.seleccionar([etapa])
        for _ in range(6):
            QApplication.processEvents()
        arriba = y(w.inferior)
        self.assertLessEqual(y(w.props.s_etiqueta) - arriba, 32, "antes, 40")
        e.seleccionar([e.M["transitions"][0]["id"]])
        for _ in range(8):
            QApplication.processEvents()
        self.assertEqual(w.props.pagina, "transicion")
        arriba = y(w.inferior)
        self.assertLessEqual(y(w.props.prog) - arriba, 32, "antes, 65: dos filas de cabecera")
        self.assertTrue(w.props.t_fijar.isVisible())
        self.assertAlmostEqual(y(w.props.t_fijar) + w.props.t_fijar.height() / 2, y(w.props.titulo) + w.props.titulo.height() / 2,
                               delta=4, msg="«Fijar» va en la fila del título")
        self.assertFalse(w.props.l_bloques.isVisible(), "no repite el título")
        self.assertIn("t", w.props.l_bloques.text())  # (el texto sigue, para quien lo lea)

    def test_SAUC20_la_cabecera_de_una_accion_enseña_su_condicion_en_la_misma_fila(self):
        """REQ-EDT-09: en una acción con condición, lo que programan los bloques se dice en la fila del título."""
        w, e, y = self.preparar()
        sid = [s["id"] for s in e.M["steps"] if s["label"] == "1"][0]
        e.pedir_accion = lambda *a: None
        did = e.anadir_accion(sid)
        e.tipo_accion(did, "condicionada")
        for _ in range(8):
            QApplication.processEvents()
        self.assertEqual(w.props.pagina, "accion")
        self.assertIn("Condición de la acción", w.props.l_bloques.text())
        self.assertTrue(w.props.l_bloques.isVisible())
        self.assertAlmostEqual(y(w.props.l_bloques), y(w.props.titulo), delta=6)



@unittest.skipUnless(QT, "requiere PySide6")
class RevisionIndependiente(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_SAUC22_intro_con_el_selector_de_hojas_no_hace_nada_ni_falla(self):
        """REQ-EDT-09: en el modo de seleccionar para una hoja, Intro con una etapa seleccionada se queda en silencio."""
        from escritorio.hojas import SeleccionParaHoja
        w, e = self.vacio()
        s = e.ed.add_step("g", "1", True, at=(100, 80))
        e.cambia()
        e.seleccionar([s])
        w.diagrama.controlador = SeleccionParaHoja(e)
        QTest.keyClick(w.diagrama, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(e.sel, [s])

    def tres(self):
        """etapas 1, 3, 4 y t2 = X3, ligada por ID a «3»."""
        w, e = self.vacio()
        s1 = e.ed.add_step("g", "1", True, at=(100, 80))
        s3 = e.ed.add_step("g", "3", at=(100, 280))
        s4 = e.ed.add_step("g", "4", at=(100, 480))
        t1, _ = e.ed.add_transition("g", "", [s1], [s3], at=(100, 180), label="t1")
        t2, _ = e.ed.add_transition("g", "", [s3], [s4], at=(100, 380), label="t2")
        e.cambia()
        e.poner_condicion(t1, "true")
        e.poner_condicion(t2, "X3")
        return w, e, (s1, s3, s4), (t1, t2)

    def texto(self, e, t):
        return e.texto_usuario(t)

    def test_SAUC23_al_resolver_el_repetido_borrando_la_otra_etapa_el_texto_se_reescribe(self):
        """REQ-MOD-06: etapa «3» renombrada a «4» (repetida) y la otra «4» borrada: la receptividad deja de decir X3 y dice X4."""
        w, e, (s1, s3, s4), (t1, t2) = self.tres()
        self.assertEqual(self.texto(e, t2), "X3")
        self.assertIsNone(e.renombrar(s3, "4"))
        self.assertEqual(self.texto(e, t2), "X3", "mientras sigue repetida, el texto no se reescribe")
        antes = copy.deepcopy(e.ed.model)
        e.ed.delete([s4], keep_dangling=True)
        e.cambia()
        self.assertEqual([d for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"], [])
        self.assertEqual(self.texto(e, t2), "X4", "el texto vuelve a cuadrar con el número de su etapa")
        despues = copy.deepcopy(e.ed.model)
        e.deshacer()
        self.assertEqual(e.ed.model, antes, "Deshacer restaura el estado exacto")
        e.rehacer()
        self.assertEqual(e.ed.model, despues)

    def test_SAUC24_intercambiar_dos_numeros_sigue_funcionando(self):
        """REQ-MOD-06: 3→4 (repetido) y luego 4→3 en la otra: se cruzan los números y cada texto sigue ligado a su etapa."""
        w, e, (s1, s3, s4), (t1, t2) = self.tres()
        e.poner_condicion(t1, "X4")
        self.assertIsNone(e.renombrar(s3, "4"))
        self.assertIsNone(e.renombrar(s4, "3"))
        self.assertEqual([d for d in e.diagnosticos() if d["code"] == "D-NOMBRE-COLISION"], [])
        self.assertEqual((self.texto(e, t1), self.texto(e, t2)), ("X3", "X4"), "t1 usaba la etapa que se llamaba 4; t2, la que se llamaba 3")
        self.assertFalse(any(d["blocks"] for d in e.diagnosticos()), e.diagnosticos())


@unittest.skipUnless(QT, "requiere PySide6")
class PegadoSoloSiSolapan(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def giradas(self, y2):
        """Dos transiciones giradas a la derecha, una a y=180 y otra a y2, con segmentos verticales fuera de la rejilla."""
        w, e = self.vacio()
        out = []
        for x, y in ((500, 180), (560, y2)):
            a = e.ed.add_step("g", f"a{x}", False, at=(x, y - 120))
            b = e.ed.add_step("g", f"b{x}", False, at=(x + 200, y + 120))
            t = e.ed.add_transition("g", "", [a], [b], at=(x, y), label=f"t{x}")[0]
            out.append(t)
        e.cambia()
        e.sel = list(out)
        e.girar_transiciones(1)
        e.cambia()
        return w, e, out

    def vertical_pre(self, e, t):
        from grafcet.routing import enlaces
        r = next(r for r in enlaces(e.M) if r["tid"] == t and r["rol"] == "pre")
        i = next(h["segment"] for h in r["handles"] if h["axis"] == "x")
        return r, i

    def arrastrar_x(self, e, t, x):
        r, i = self.vertical_pre(e, t)
        a, b = r["pts"][i], r["pts"][i + 1]
        p0 = QPointF(a[0], a[1] + 0.3 * (b[1] - a[1]))
        e.sel = []
        e.prensar(p0)
        self.assertEqual((e.arrastre or {}).get("tipo"), "tramo")
        e.mover(QPointF(x, p0.y()) + QPointF(1, 0))
        e.mover(QPointF(x, p0.y()))
        e.soltar(QPointF(x, p0.y()))
        from grafcet.routing import enlaces
        return next(q for q in enlaces(e.M) if q["id"] == r["id"])["pts"][i][0]

    def test_SAUC25_en_una_transicion_girada_se_pega_exacto_solo_si_los_tramos_se_solapan(self):
        """REQ-EDT-02: tramo vertical de una transición girada: con un paralelo ajeno fuera de la rejilla a menos de 10 y que
        se solapa a lo largo del otro eje, queda exacto; sin solape, en la rejilla."""
        from grafcet.routing import enlaces
        w, e, (t, t2) = self.giradas(180)
        otros = {round(p[0], 3) for r in enlaces(e.M) if r["tid"] == t2 for p, q in zip(r["pts"], r["pts"][1:]) if p[0] == q[0] and p != q}
        fuera = [x for x in otros if x % 20]
        self.assertTrue(fuera, otros)
        objetivo = min(fuera, key=lambda x: abs(x - 640))  # el vertical ajeno fuera de rejilla más cercano a la rejilla 640
        pegado = self.arrastrar_x(e, t, round(objetivo / 20) * 20)
        self.assertEqual(pegado, objetivo)
        e.deshacer()
        w2, e2, (u, u2) = self.giradas(560)  # el otro, mucho más abajo: no se solapan
        pegado = self.arrastrar_x(e2, u, round(objetivo / 20) * 20)
        self.assertEqual(pegado % 20, 0, "sin solape, a la rejilla")


@unittest.skipUnless(QT, "requiere PySide6")
class EntradaAES(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_SAUC30_a_es_externas_se_entra_por_la_luz_y_no_por_una_pestana(self):
        """REQ-SIM-03: la pestaña E/S externas no se ve; un clic en la luz de conexión abre E/S y la deja activa; GRAFCET vuelve."""
        w, e = self.vacio()
        w.resize(1200, 800);w.show();QApplication.processEvents()
        tabs = w.pestanas_vistas
        self.assertFalse(tabs.isTabVisible(2))
        self.assertTrue(tabs.isTabVisible(0) and tabs.isTabVisible(1))
        self.assertEqual(w.luz_es.toolTip().splitlines()[-1], "Abrir E/S externas")
        self.assertEqual(w.luz_es.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertFalse(w.luz_es.property("abierta"))
        QTest.mouseClick(w.luz_es, Qt.MouseButton.LeftButton);QApplication.processEvents()
        self.assertEqual(w.paginas_es.currentIndex(), 1)
        self.assertTrue(w.luz_es.property("abierta"))
        self.assertFalse(any(tabs.isTabVisible(i) and tabs.currentIndex() == i for i in range(3)), "ninguna pestaña activa a la vista")
        QTest.mouseClick(tabs, Qt.MouseButton.LeftButton, pos=tabs.tabRect(1).center());QApplication.processEvents()
        self.assertEqual(w.paginas_es.currentIndex(), 2);self.assertFalse(w.luz_es.property("abierta"))
        QTest.mouseClick(w.luz_es, Qt.MouseButton.LeftButton);QApplication.processEvents()
        QTest.mouseClick(tabs, Qt.MouseButton.LeftButton, pos=tabs.tabRect(0).center());QApplication.processEvents()
        self.assertEqual(w.paginas_es.currentIndex(), 0)
        self.assertFalse(w.luz_es.property("abierta"))
        w.luz_es.click();w.panel_es.b_volver.click()
        self.assertEqual((w.paginas_es.currentIndex(), w.luz_es.property("abierta")), (0, False))
