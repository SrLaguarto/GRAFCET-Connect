"""Acabados de actividad, incidencias, selección de variable y panel derecho."""
import copy
import json
import unittest
from unittest import mock
from test_editor_cadenas import BaseQt,QT
from test_dibujo_vista import vista,dibujo,texto,ejemplo,QJS,ROOT,MOCK_DOM,dibujar_con_js
from grafcet.builder import M
if QT:
    from PySide6.QtCore import Qt,QPoint,QEvent
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication,QWidget,QGraphicsLineItem,QGraphicsRectItem,QGraphicsPathItem
    from PySide6.QtTest import QTest
    from escritorio import diagrama as dg
    from escritorio.edicion import Edicion
    from escritorio.acciones import PanelAccion
if QJS:
    from PySide6.QtQml import QJSEngine


@unittest.skipUnless(QT,"requiere PySide6")
class Acabados(BaseQt):
    def tearDown(self):
        self.w.hide()
        super().tearDown()
        QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def editor(self):
        w,e=self.vacio();e.ed.add_step("g","1",True,at=(100,100));e.cambia()
        w.resize(1366,768);w.show();QTest.qWait(20)
        return w,e

    def test_SUIV01_acciones_reales_y_trazos_completos_con_inicial(self):
        """REQ-SIM-03, REQ-ACT-01: solo contribuciones reales; recuadros, texto, palito y banderita activos en lima."""
        m=(M().var("p").var("y","output").var("n","internal","int").step("A",True)
           .cont("A","y","p").cont("A","y","NOT p").stored("A","n","event","n + 1",event="rise(p)"))
        v=vista(m,{"A":(100,150)});v.act("fijar",{"cambios":{"p":True}})
        antes=copy.deepcopy(v.s.z);st=v.state();self.assertEqual(antes,v.s.z)
        aids=[a["id"] for a in m.doc["actions"]]
        evento=m.doc["actions"][-1]["trigger"]["expressionRef"]
        self.assertIs(st["truth"][evento],True)
        self.assertIn(aids[0],st["activeActions"]);self.assertNotIn(aids[1],st["activeActions"]);self.assertIn(aids[2],st["activeActions"])
        sc,_=dibujo(v);cx=100+dg.SX
        cajas=[it for it in sc.items() if isinstance(it,QGraphicsRectItem) and it.rect().center().x()==cx]
        self.assertEqual(len(cajas),2);self.assertTrue(all(it.pen().color().name()==dg.COL["active"] for it in cajas))
        self.assertEqual(texto(sc,"A").defaultTextColor().name(),dg.COL["active"])
        self.assertEqual(texto(sc,"n := n + 1").defaultTextColor().name(),dg.COL["active"])
        self.assertTrue(any(isinstance(i,QGraphicsPathItem) and i.brush().color().name()==dg.COL["active"] for i in sc.items()))
        v.act("avanzar",{"us":1});self.assertNotIn(aids[2],v.state()["activeActions"])
        self.assertIs(v.state()["truth"][evento],False)

    def test_SUIV02_transiciones_negras_simultaneidad_y_marca_historica_paridad(self):
        """REQ-SIM-03, REQ-EDT-02: negro inactivo, lima verdadero y verde oscuro última franqueada, también en barras Y."""
        m=M().var("p").step("A",True).step("B",True).step("C").trans("t",["A","B"],["C"],"p")
        v=vista(m,{"A":(100,80),"B":(260,80),"t":(180,180),"C":(180,280)})
        for verdadero,historia,esperado in ((False,False,"text"),(True,False,"active"),(True,True,"history")):
            st={"transitions":{"t":{"validated":True,"receptivity":verdadero}},"lastCleared":["t"] if historia else []}
            sc,_=dibujo(v,st);x,y=180+dg.SX,180
            barra=next(i for i in sc.items() if isinstance(i,QGraphicsLineItem) and i.line().x1()==x-dg.TB and i.line().y1()==y)
            self.assertEqual(barra.pen().color().name(),dg.COL[esperado])
            doble=[i for i in sc.items() if isinstance(i,QGraphicsLineItem) and i.line().y1() in (y-dg.SIMUL,y-dg.SIMUL-dg.BARRA_GROSOR) and i.line().x1()!=i.line().x2()]
            self.assertEqual(len(doble),2);self.assertTrue(all(i.pen().color().name()==dg.COL[esperado] for i in doble))
            if QJS:
                eng=QJSEngine();js=(ROOT/"tools/dibujo.js").read_text(encoding="utf-8").replace("{x, y, ...attrs}","Object.assign({x, y}, attrs)")
                self.assertFalse(eng.evaluate(MOCK_DOM+js).isError())
                modelo=copy.deepcopy(v.model);modelo["bars"]=[{"id":"Y","arriba":["t"],"abajo":["C"],"kind":"Y"}]
                result=eng.evaluate("JSON.stringify(coloresElementos(%s,%s))"%(json.dumps(modelo),json.dumps(st)))
                self.assertFalse(result.isError(),result.toString());self.assertEqual(json.loads(result.toString()),dg._colores_elementos(modelo,st))
        for clave in ("encapsulacion","macroetapa"):
            v=ejemplo(clave);st=v.state()
            if clave=="macroetapa":st["macros"]={v.model["macros"][0]["id"]:True}
            sc,_=dibujo(v,st)
            if clave=="encapsulacion":self.assertEqual(texto(sc,"R").defaultTextColor().name(),dg.COL["active"])
            else:
                mid=v.model["macros"][0]["id"];self.assertEqual(texto(sc,v.model["names"][mid]).defaultTextColor().name(),dg.COL["active"])
        css=(ROOT/"tools/dibujo.css").read_text(encoding="utf-8")
        for regla in (".step.active>rect",".step.active>.hmark",".act.on>.amark",".act.on>.atext,.act.on>.ahead"):
            self.assertIn(regla,css)
        self.assertEqual(dg.COL["true_text"],dg.COL["active"]);self.assertEqual(dg.COL["history"],"#1a7f1b")

    def test_SUIV03_banderita_identifica_accion_y_exige_evento_sin_elegir_flanco(self):
        """REQ-ACT-02, REQ-EDT-09: b no es un evento; error con variable y etapa, ayuda inmediata y modelo sin cambios implícitos."""
        m=M().var("b").var("j","internal").step("6",True).stored("6","j","event","true",event="b")
        e=Edicion.desde(m.doc,{"6":(100,100)},"Banderita");w=self.w;w._establecer_edicion(e);aid=m.doc["actions"][0]["id"]
        d=next(d for d in e.diagnosticos() if d["code"]=="D-TIPO-EVENTO")
        self.assertEqual(d["target"],aid);self.assertIn("j",d["message"]);self.assertIn("etapa 6",d["message"]);self.assertIn("flanco",d["message"])
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:w._no_simulable()
        self.assertIn("etapa 6",aviso.call_args.args[2]);self.assertNotIn("un elemento",aviso.call_args.args[2])
        p=w.props;p.e=e;p._objetivo=("accion",aid,"evento");p.t_texto.setText("b");p._previsualizar()
        self.assertIn("no un evento",p.t_estado.text());self.assertEqual(e.texto_accion(aid,"evento"),"b")
        e.poner_texto_accion(aid,"evento","↑b")
        self.assertNotIn("D-TIPO-EVENTO",[d["code"] for d in e.diagnosticos()])

    def test_SUIV04_selector_de_variable_en_caja_de_accion_con_popup_real(self):
        """REQ-EDT-07, REQ-EDT-10: selector con figura de acción conserva lista, teclado, variable elegida y deshacer."""
        m=M().var("y","output").var("z","output").step("1",True).cont("1","y")
        e=Edicion.desde(m.doc,{"1":(100,100)},"Selector");aid=m.doc["actions"][0]["id"]
        p=PanelAccion();self.addCleanup(p.deleteLater);self.addCleanup(p.hide);p.mostrar(e,aid);p.resize(330,250);p.show();QTest.qWait(20)
        c=p.variable;self.assertGreaterEqual(c.height(),62)
        pm=QPixmap(c.size());QWidget.render(c,pm)
        QTest.mouseClick(c,Qt.MouseButton.LeftButton);QTest.qWait(20)
        indice=c.model().index(c.findData("z"),0)
        QTest.mouseMove(c.view().viewport(),c.view().visualRect(indice).center());QTest.qWait(10)
        QTest.mouseClick(c.view().viewport(),Qt.MouseButton.LeftButton,pos=c.view().visualRect(indice).center())
        self.assertEqual(c.currentText(),"z");self.assertEqual(e.ed.get(aid)["targetRef"],"z")
        e.ed.undo();self.assertEqual(e.ed.get(aid)["targetRef"],"y")

    def test_SUIV05_panel_derecho_se_redimensiona_al_editar_y_simular(self):
        """REQ-EDT-09, REQ-SIM-03: divisor real habilitado en ambos modos; el panel izquierdo conserva su ancho."""
        w,e=self.editor()
        for simular in (False,True):
            w.a_ejecutar.setChecked(simular);w.rt.stop();QTest.qWait(20)
            h=w.split.handle(1);self.assertTrue(h.isEnabled());ancho=w.derecho.width();c=h.rect().center()
            QTest.mousePress(h,Qt.MouseButton.LeftButton,pos=c);QTest.mouseMove(h,c-QPoint(50,0));QTest.mouseRelease(h,Qt.MouseButton.LeftButton,pos=c)
            QTest.qWait(20);self.assertGreater(w.derecho.width(),ancho);self.assertEqual(w.dock.width(),w.ancho_lateral)

    def test_SUIV06_incidencias_triangular_bajo_zoom_a_izquierda_del_texto(self):
        """REQ-EDT-09: icono rojo junto al texto, debajo del zoom, manteniendo clic en diagnóstico y espacios transparentes."""
        w,e=self.editor();d=w.diagrama;self.assertFalse(d.indicador_diagnosticos.isVisible())
        e.ed.add_transition("g","",label="t2",at=(100,200));e.cambia();QTest.qWait(20)
        icono=d.indicador_diagnosticos;lista=d.lista_diagnosticos
        self.assertFalse(icono.pixmap().isNull());self.assertEqual(icono.width(),40)
        self.assertGreaterEqual(icono.y(),d.barra.geometry().bottom());self.assertLess(icono.geometry().right(),lista.x())
        self.assertFalse(icono.geometry().intersects(d.barra.geometry()))
        self.assertFalse(lista.mask().contains(QPoint(lista.width()-1,lista.height()-1)))
