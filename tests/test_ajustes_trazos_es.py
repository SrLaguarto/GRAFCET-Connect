"""Acabados de trazos, lecturas numéricas, arrastre E/S y controles por página."""
import copy
import json
import unittest
from unittest import mock
from grafcet.builder import M
from grafcet.examples import ej_repeticion
from grafcet.routing import enlaces
from test_dibujo_vista import QT,QJS,ROOT,MOCK_DOM,vista,dibujo,texto,corriendo,modelo_temporizado,dibujar_con_js
from test_editor_cadenas import BaseQt
if QT:
    from PySide6.QtCore import Qt,QPoint,QPointF,QRectF,QEvent
    from PySide6.QtGui import QImage,QPainter,QPixmap,QMouseEvent,QDragEnterEvent,QDragMoveEvent,QDragLeaveEvent,QDropEvent
    from PySide6.QtWidgets import QApplication,QWidget,QGraphicsLineItem
    from PySide6.QtTest import QTest
    from escritorio import diagrama as dg
    from escritorio.entradas_salidas import PanelES,figura_variable
if QJS:
    from PySide6.QtQml import QJSEngine


def recorrer(n):
    yield n
    for c in n.get("hijos",[]):yield from recorrer(c)


@unittest.skipUnless(QT,"requiere PySide6")
class Trazos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_SAFI01_transicion_corta_con_proporcion_igual_en_qt_y_js(self):
        """REQ-EDT-02: trazo de transición de 16 px frente a caja de etapa de 44 px, igual en los dos renderizadores."""
        v=vista(M().step("A",True).step("B").trans("t",["A"],["B"],"false"),{"A":(100,80),"t":(100,180),"B":(100,280)})
        sc,_=dibujo(v,{})
        trazo=next(i for i in sc.items() if isinstance(i,QGraphicsLineItem) and i.line().y1()==180 and i.line().y2()==180)
        self.assertEqual(trazo.line().length(),16);self.assertLess(trazo.line().length()/(2*dg.H),.4)
        if QJS:
            arbol=dibujar_con_js(v.model,{})
            lineas=[n["attrs"] for n in recorrer(arbol) if n["tag"]=="line" and n["attrs"].get("class")=="bar"]
            self.assertEqual(len(lineas),1);self.assertEqual(lineas[0]["x2"]-lineas[0]["x1"],16)

    def test_SAFI02_doble_barra_separa_lados_y_tapa_trazos_en_su_hueco(self):
        """REQ-EDT-02, REQ-EDT-14: doble barra con 8 px de hueco y conectores detenidos arriba/abajo; nada la atraviesa visualmente."""
        v=vista(M().step("A",True).step("B").trans("t",["A"],["B"],"false"),{"A":(100,50),"t":(100,100),"B":(100,250)})
        v.model["bars"]=[{"id":"Y","kind":"Y","x":60,"y":150,"ancho":100,"arriba":["A"],"abajo":["B"]}]
        v.model["links"]=enlaces(v.model)
        r=[e for e in v.model["links"] if e["rol"]=="barra"]
        self.assertEqual(r[0]["pts"][-1][1],150);self.assertEqual(r[1]["pts"][0][1],158)
        sc,_=dibujo(v,{})
        imagen=QImage(100,40,QImage.Format.Format_ARGB32);imagen.fill(Qt.GlobalColor.white)
        p=QPainter(imagen);sc.render(p,QRectF(0,0,100,40),QRectF(150,140,100,40),Qt.AspectRatioMode.IgnoreAspectRatio);p.end()
        self.assertEqual(imagen.pixelColor(50,14).name(),"#ffffff")
        self.assertNotEqual(imagen.pixelColor(50,10).name(),"#ffffff")
        self.assertNotEqual(imagen.pixelColor(50,18).name(),"#ffffff")
        if QJS:
            arbol=dibujar_con_js(v.model,{})
            huecos=[n["attrs"] for n in recorrer(arbol) if n["attrs"].get("class")=="sync-gap"]
            self.assertEqual(len(huecos),1);self.assertEqual(huecos[0]["height"],6)
            self.assertIn('.sync-gap{fill:var(--panel);stroke:none}',(ROOT/'tools/dibujo.css').read_text())

    def test_SAFI03_lecturas_de_variables_y_tiempos_en_azul_sin_cambiar_verdaderos(self):
        """REQ-SIM-03, REQ-TMP-01: valor y tiempo en #326DCB, incluso al vencer; expresiones verdaderas conservan su verde."""
        m,lay=modelo_temporizado();v=corriendo(m,lay)
        for avance,shown in ((0,"1,00 s"),(2_000_000,"3,00 s ✓")):
            if avance:v.act("avanzar",{"us":avance})
            sc,_=dibujo(v);self.assertEqual(texto(sc,shown).defaultTextColor().name(),"#326dcb")
        m=M().var("p").var("n","internal","int").step("A",True).stored("A","n","event","n+1",event="rise(p)")
        v=vista(m,{"A":(100,100)});v.act("fijar",{"cambios":{"p":True}})
        sc,_=dibujo(v);self.assertEqual(texto(sc,"1").defaultTextColor().name(),"#326dcb")
        self.assertNotEqual(dg.COL["readout"],dg.COL["true_text"])
        css=(ROOT/'tools/dibujo.css').read_text()
        self.assertIn('.timer-state.run text,.timer-state.done text{fill:#326dcb}',css)
        self.assertRegex(css,r'text.variable-value\{[^}]*fill:#326dcb')
        self.assertNotIn('.act.on text.variable-value',css)

    def test_SAFI04_lazos_anidados_sin_cruces_y_rutas_manuales_respetadas(self):
        """REQ-MOD-03, REQ-EDT-02, REQ-EDT-14: un retorno exterior rodea al interior; no se altera una ruta manual ni el modelo."""
        m,lay=ej_repeticion();m.trans("t4",["4"],["1"],"false");lay["t4"]=(300,620)
        antes=copy.deepcopy(m.doc)
        for inverso in (False,True):
            doc=copy.deepcopy(m.doc)
            if inverso:doc["transitions"].reverse()
            v=vista(doc,lay);r={e["id"]:e for e in enlaces(v.model)}
            interior=r["retorno|2|post"]["pts"];exterior=r["t4|1|post"]["pts"]
            self.assertLess(exterior[2][0],interior[2][0])
            # No hay intersecciones propias entre las dos polilíneas (extremos compartidos se permiten).
            for a,b in zip(interior,interior[1:]):
                for c,d in zip(exterior,exterior[1:]):
                    if (a[0]==b[0])==(c[0]==d[0]):continue
                    x,y,z,w=(a,b,c,d) if a[0]==b[0] else (c,d,a,b)
                    self.assertFalse(min(x[1],y[1])<z[1]<max(x[1],y[1]) and min(z[0],w[0])<x[0]<max(z[0],w[0]))
            v.model["linkStyles"]={"t4|1|post":{"route":{"laneX":200}}}
            manual=next(e for e in enlaces(v.model) if e["id"]=="t4|1|post")
            self.assertEqual(manual["pts"][2][0],300)
        self.assertEqual(m.doc,antes)


@unittest.skipUnless(QT,"requiere PySide6")
class ArrastreES(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def preparar(self):
        p=PanelES();p.cargar(M().var("a").var("b").var("q","output").step("0",True).doc)
        p.resize(1366,768);p.show();self.app.processEvents()
        self.addCleanup(p.deleteLater);self.addCleanup(p.hide)
        return p

    def test_SAFI05_destino_resaltado_solo_fuera_del_plc_en_ambos_lados(self):
        """REQ-SIM-03: arrastrar resalta solo el lateral, dentro del PLC no se acepta el drop; válida la asignación exterior."""
        p=self.preparar()
        for area,lista in (("discrete",p.lista_entradas),("coil",p.lista_salidas)):
            t=p.terminales[(area,1)];mime=lista.mimeData([lista.item(0)])
            fuera=t.zona_asignacion().center();dentro=t.interior.geometry().center()
            imagen=QPixmap(t.size());QWidget.render(t,imagen);antes=imagen.toImage().pixelColor(dentro)
            entrar=QDragEnterEvent(fuera,Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(t,entrar);self.assertTrue(t.resaltado())
            imagen=QPixmap(t.size());QWidget.render(t,imagen)
            self.assertEqual(imagen.toImage().pixelColor(dentro),antes)
            self.assertEqual(imagen.toImage().pixelColor(fuera).name(),"#c1e8dc")
            mover=QDragMoveEvent(dentro,Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(t,mover);self.assertFalse(t.resaltado());self.assertFalse(mover.isAccepted())
            soltar=QDropEvent(QPointF(dentro),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(t,soltar);self.assertFalse(p.obtener().senales)
            self.app.sendEvent(t,QDragLeaveEvent())
            self.app.sendEvent(t,QDragEnterEvent(fuera,Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier))
            self.app.sendEvent(t,QDropEvent(QPointF(fuera),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier))
            self.app.processEvents();self.assertEqual(len(p.obtener().senales),1)
            asignado=p.terminales[(area,1)];self.assertFalse(asignado.barrita_nombre.isVisibleTo(asignado))
            p.quitar(asignado.variable["id"]);self.app.processEvents()

    def test_SAFI06_fila_completa_arrastrable_y_sin_barrita_en_figura(self):
        """REQ-SIM-03: gesto desde ambos extremos de la fila, con nombre alineado a la izquierda y figura sin cuadrado verde."""
        p=self.preparar();lista=p.lista_entradas;vp=lista.viewport();rect=lista.visualItemRect(lista.item(0))
        for x,dx in ((10,30),(rect.right()-8,-30)):
            punto=QPoint(x,rect.center().y())
            QTest.mousePress(vp,Qt.MouseButton.LeftButton,pos=punto)
            fin=punto+QPoint(dx,0)
            with mock.patch('escritorio.entradas_salidas.QDrag') as drag:
                evento=QMouseEvent(QEvent.Type.MouseMove,QPointF(fin),QPointF(vp.mapToGlobal(fin)),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
                self.app.sendEvent(vp,evento);self.assertTrue(drag.return_value.exec.called)
                figura=drag.return_value.setPixmap.call_args.args[0].toImage()
                self.assertFalse(any(figura.pixelColor(xx,yy).green()>100 and figura.pixelColor(xx,yy).red()<60 and figura.pixelColor(xx,yy).alpha()>0 for xx in range(figura.width()) for yy in range(figura.height())))
            QTest.mouseRelease(vp,Qt.MouseButton.LeftButton,pos=fin)


@unittest.skipUnless(QT,"requiere PySide6")
class ControlesES(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SAFI07_play_stop_reiniciar_inactivos_en_es_incluidos_atajos(self):
        """REQ-SIM-03, REQ-SIM-04: E/S deshabilita los controles y sus atajos; volver al dibujo los recupera sin parar la simulación."""
        w,e=self.vacio();e.ed.add_step("g","1",True,at=(100,100));e.cambia()
        w.resize(1366,768);w.show();QTest.qWait(20)
        for corriendo in (False,True):
            w.a_ejecutar.setChecked(corriendo);w.rt.stop();w._mostrar_pagina(True)
            antes=copy.deepcopy(w.v.state());self.assertFalse(w.a_ejecutar.isEnabled());self.assertFalse(w.a_reiniciar.isEnabled())
            for toolbar,accion in ((w.tb_sim,w.a_ejecutar),(w.tb_sim,w.a_reiniciar)):
                boton=toolbar.widgetForAction(accion);QTest.mouseClick(boton,Qt.MouseButton.LeftButton)
            QTest.keyClick(w,Qt.Key.Key_R,Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(w.v.state(),antes);self.assertEqual(w.paginas_es.currentIndex(),1)
            w._mostrar_pagina(False);self.assertTrue(w.a_ejecutar.isEnabled());self.assertTrue(w.a_reiniciar.isEnabled())
            self.assertEqual(w.a_ejecutar.isChecked(),corriendo)

    def test_SAFI08_icono_dependencia_con_marco_y_trazos_discontinuos_conserva_control(self):
        """REQ-EDT-02, REQ-SIM-03: icono de dependencia con caja y marco lateral; el conmutador sigue dibujando las dependencias."""
        from escritorio.ventana import _icono_barra
        pm=_icono_barra("dependencias").pixmap(24,24)
        self.assertFalse(pm.isNull());self.assertNotEqual(pm.toImage(),_icono_barra("conexion").pixmap(24,24).toImage())
        w,e=self.vacio();w.show();QTest.qWait(20);b=w.diagrama.b_dependencias
        self.assertEqual(b.accessibleName(),"Mostrar dependencias")
        QTest.mouseClick(b,Qt.MouseButton.LeftButton);self.assertTrue(w.diagrama.dependencias)
        QTest.mouseClick(b,Qt.MouseButton.LeftButton);self.assertFalse(w.diagrama.dependencias)
