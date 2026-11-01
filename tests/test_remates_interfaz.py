"""Remates visuales y gestos de la interfaz, sin alterar la semántica del GRAFCET."""
import json
import math
import re
import unittest
from unittest import mock
from test_editor_cadenas import BaseQt, QT
from test_pulido_es import documento
from test_dibujo_vista import MOCK_DOM, ROOT, QJS
if QT:
    from PySide6.QtCore import Qt,QPoint,QPointF,QRect,QObject,QEvent
    from PySide6.QtGui import QImage,QPainter,QColor,QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QStyleOptionViewItem,QStyle,QGraphicsScene,QGraphicsRectItem,QGroupBox
    from escritorio.entradas_salidas import PanelES,figura_variable,ROL_COLOR,ROL_ACTIVO,ALTO_VARIABLE
    from escritorio import diagrama as dg
    from escritorio.ventana import _trazos_reinicio
if QJS:
    from PySide6.QtQml import QJSEngine


@unittest.skipUnless(QT,"requiere PySide6")
class Remates(BaseQt):
    def editor(self):
        w,e=self.vacio(); e.ed.add_step("g","1",True,at=(100,100));e.cambia()
        w.resize(1366,768);w.show();QApplication.processEvents()
        return w,e

    def test_SREM01_divisor_no_realimenta_relayout_de_paleta(self):
        """REQ-EDT-09: el arrastre real del divisor mantiene mínimos, barra y celdas estables al cambiar solo el alto."""
        w,e=self.editor();p=w.paleta;h=w.vsplit.handle(1);centro=h.rect().center()
        class Cuenta(QObject):
            def __init__(self):
                super().__init__();self.tamanos=0;self.pintados=0
            def eventFilter(self,obj,event):
                self.tamanos+=event.type()==QEvent.Type.Resize
                self.pintados+=event.type()==QEvent.Type.Paint
                return False
        cuenta=Cuenta();p.viewport().installEventFilter(cuenta)
        minimos=[];politicas=[];anchos=[];altos=[]
        with mock.patch.object(p,"doItemsLayout",wraps=p.doItemsLayout) as layout:
            QTest.mousePress(h,Qt.MouseButton.LeftButton,pos=centro)
            for dy in (-12,-24,-36,12,24,0):
                QTest.mouseMove(h,centro+QPoint(0,dy));QApplication.processEvents()
                minimos.append(p.minimumSizeHint().height());politicas.append(p.verticalScrollBarPolicy());anchos.append(p._ancho_celdas);altos.append(p.height())
            QTest.mouseRelease(h,Qt.MouseButton.LeftButton,pos=centro)
            self.assertLessEqual(layout.call_count,1)
        self.assertLessEqual(cuenta.pintados,cuenta.tamanos+1)
        self.assertGreater(len(set(altos)),1);self.assertEqual(len(set(minimos)),1);self.assertEqual(len(set(politicas)),1);self.assertEqual(len(set(anchos)),1)
        w._mostrar_panel("inferior",False);w._mostrar_panel("inferior",True);QApplication.processEvents()
        self.assertEqual(p.minimumSizeHint().height(),minimos[0])

    def test_SREM02_variables_ajustan_filas_y_botones_debajo_con_limite(self):
        """REQ-EDT-07, REQ-EDT-09: tabla sin espacio sobrante, botones debajo y desplazamiento interno con muchas filas."""
        w,e=self.editor();p=w.variables
        for i in range(2):e.ed.add_variable("p"+str(i),"input",{"kind":"bool"})
        e.cambia();QTest.qWait(20)
        natural=p.tabla.horizontalHeader().height()+sum(p.tabla.rowHeight(i) for i in range(2))+2*p.tabla.frameWidth()
        self.assertEqual(p.tabla.height(),natural)
        botones=list(p.b_nuevas.values())+[p.b_quitar]
        self.assertLessEqual(botones[0].parentWidget().y()-p.tabla.geometry().bottom(),10)
        for b in botones:self.assertGreaterEqual(b.width(),b.fontMetrics().horizontalAdvance(b.text())+16)
        for i in range(45):e.ed.add_variable("q"+str(i),"input",{"kind":"bool"})
        e.cambia();QTest.qWait(20)
        self.assertLessEqual(p.tabla.height(),320);self.assertGreater(p.tabla.verticalScrollBar().maximum(),0)
        self.assertLessEqual(botones[0].parentWidget().y()-p.tabla.geometry().bottom(),10)

    def test_SREM03_diagnostico_en_lienzo_selecciona_sin_tapar_zoom(self):
        """REQ-EDT-09: sin errores no hay indicador; el error con nombre se pulsa sobre el dibujo y conserva selección y parpadeo."""
        w,e=self.editor();d=w.diagrama
        self.assertFalse(d.indicador_diagnosticos.isVisible());self.assertFalse(w.lista_diag.isVisible())
        self.assertNotIn("Diagnósticos",[b.title() for b in w.derecho.findChildren(QGroupBox)])
        tid,_=e.ed.add_transition("g","",label="t2",at=(100,200));e.cambia();QApplication.processEvents()
        self.assertTrue(d.indicador_diagnosticos.isVisible());self.assertIs(w.lista_diag.parent(),d)
        self.assertGreater(w.lista_diag.y(),d.barra.geometry().bottom())
        i=next(i for i in range(w.lista_diag.count()) if w.lista_diag.item(i).data(Qt.ItemDataRole.UserRole)==tid)
        self.assertIn("t2",w.lista_diag.item(i).text());self.assertNotIn(tid,w.lista_diag.item(i).text())
        QTest.mouseClick(w.lista_diag.viewport(),Qt.MouseButton.LeftButton,pos=w.lista_diag.visualItemRect(w.lista_diag.item(i)).center())
        self.assertIn(tid,e.sel);self.assertIn(tid,e.parpadeo.ids)
        self.assertFalse(w.lista_diag.mask().contains(QPoint(w.lista_diag.width()-1,w.lista_diag.height()-1)))

    def test_SREM04_bool_sin_escala_numerica_editable_y_configuracion_portable(self):
        """REQ-SIM-03, REQ-DAT-02: BOOL muestra guion y guarda 1; INT16/UINT16 admiten escala, dirección, formato y uso."""
        from conexion.configuracion import Configuracion
        p=PanelES();p.cargar(documento());self.addCleanup(p.deleteLater)
        self.assertEqual(p.tabla.cellWidget(0,7).text(),"—");self.assertFalse(p.tabla.cellWidget(0,7).isEnabled())
        escala=p.tabla.cellWidget(1,7);self.assertEqual(escala.text(),"100");self.assertFalse(escala.isReadOnly());self.assertTrue(escala.isEnabled())
        p.asignar("sensor","discrete",0);p.asignar("nivel","input-register",0)
        escala.selectAll();QTest.keyClicks(escala,"25");escala.editingFinished.emit()
        p.tabla.cellWidget(1,5).setValue(3);p.tabla.cellWidget(1,6).setCurrentIndex(1)
        c=p.obtener();s=next(s for s in c.senales if s.variable=="nivel")
        self.assertEqual((s.escala,s.direccion,s.formato),("25",3,"UINT16"))
        self.assertEqual(next(s.escala for s in c.senales if s.variable=="sensor"),"1")
        p.cargar(p.doc,c);self.assertEqual(p.tabla.cellWidget(1,7).text(),"25")

    def test_SREM05_listas_simetria_arrastre_compacto_y_plc_sin_relleno(self):
        """REQ-SIM-03: nombres a la izquierda, fila arrastrable y figura compacta sin barrita; PLC sin relleno."""
        p=PanelES();p.cargar(documento());p.resize(1000,600);p.show();QApplication.processEvents();self.addCleanup(p.deleteLater)
        for lista in (p.lista_entradas,p.lista_salidas):
            it=lista.item(0);pm=figura_variable(it.text(),it.data(ROL_COLOR),lista.itemDelegate().derecha)
            self.assertLess(pm.width(),lista.viewport().width())
            imagen=QImage(300,ALTO_VARIABLE,QImage.Format.Format_ARGB32);imagen.fill(Qt.GlobalColor.white)
            op=QStyleOptionViewItem();op.rect=QRect(0,0,300,ALTO_VARIABLE);op.state=QStyle.StateFlag.State_MouseOver
            painter=QPainter(imagen);lista.itemDelegate().paint(painter,op,lista.model().index(0,0));painter.end()
            bx=292
            self.assertEqual(imagen.pixelColor(bx,ALTO_VARIABLE//2),QColor("#e8f5ef"))
            self.assertEqual(imagen.pixelColor(7,ALTO_VARIABLE//2),QColor("#e8f5ef"))
            it.setData(ROL_ACTIVO,True)
            painter=QPainter(imagen);lista.itemDelegate().paint(painter,op,lista.model().index(0,0));painter.end()
            self.assertEqual(imagen.pixelColor(bx,ALTO_VARIABLE//2),QColor("#e8f5ef"))
            libre=0 if lista.itemDelegate().derecha else 299
            self.assertEqual(imagen.pixelColor(libre,ALTO_VARIABLE//2),QColor("white"))
            with mock.patch("escritorio.entradas_salidas.QDrag") as drag:
                lista.setCurrentRow(0);lista.startDrag(Qt.DropAction.CopyAction)
                self.assertLess(drag.return_value.setPixmap.call_args.args[0].width(),lista.width())
        p.asignar("sensor","discrete",0)
        terminal=p.terminales[("discrete",0)]
        self.assertFalse(terminal.resaltado());self.assertFalse(terminal.barrita_nombre.isVisibleTo(terminal))

    def test_SREM06_play_stop_y_reiniciar_desde_es_por_boton_y_teclado(self):
        """REQ-SIM-03, REQ-SIM-04: E/S bloquea botones y atajos; los controles vuelven a funcionar en GRAFCET."""
        w,e=self.editor()
        for tecla in (False,True):
            for operacion in ("play","stop","reiniciar"):
                w.a_ejecutar.setChecked(operacion=="stop");w.rt.stop();w._mostrar_pagina(True);QApplication.processEvents()
                if tecla:QTest.keyClick(w,Qt.Key.Key_R,Qt.KeyboardModifier.ControlModifier) if operacion=="reiniciar" else QTest.keyClick(w,Qt.Key.Key_F5)
                else:
                    accion=w.a_reiniciar if operacion=="reiniciar" else w.a_ejecutar
                    QTest.mouseClick(w.tb_sim.widgetForAction(accion),Qt.MouseButton.LeftButton)
                w.rt.stop();QApplication.processEvents()
                self.assertEqual(w.paginas_es.currentIndex(),1,(tecla,operacion));self.assertTrue(w.a_es.isChecked())
                self.assertEqual(w.a_ejecutar.isChecked(),operacion=="stop")
                self.assertFalse(w.a_ejecutar.isEnabled());self.assertFalse(w.a_reiniciar.isEnabled())
                w._mostrar_pagina(False)
                self.assertTrue(w.a_ejecutar.isEnabled());self.assertTrue(w.a_reiniciar.isEnabled())

    def test_SREM07_reiniciar_sigue_referencia_angular_y_tangente(self):
        """REQ-EDT-09: brazos horizontal y vertical iguales y simétricos respecto a la tangente de la referencia gráfica."""
        arco,punta=_trazos_reinicio();p=arco.currentPosition();a,b,c=[punta.elementAt(i) for i in range(3)]
        self.assertAlmostEqual(a.y,b.y);self.assertAlmostEqual(b.x,c.x)
        self.assertAlmostEqual(b.x-a.x,c.y-b.y)
        t=QPointF(2**-.5,-2**-.5);n=QPointF(t.y(),-t.x())
        dx,dy=b.x-p.x(),b.y-p.y();self.assertAlmostEqual(dx*n.x()+dy*n.y(),0);self.assertAlmostEqual(dx*t.x()+dy*t.y(),3)
        self.assertAlmostEqual(math.hypot(a.x-b.x,a.y-b.y),math.hypot(c.x-b.x,c.y-b.y))

    def test_SREM08_borde_activo_por_encima_en_qt_y_svg_ambos_ordenes_y_forzado(self):
        """REQ-SIM-03, REQ-EDT-02: borde compartido activo prioritario, también con forzado, sin cambiar anchos ni posiciones."""
        for izquierda in (False,True):
            for forzado in (False,True):
                sc=QGraphicsScene();pt=dg._Pintor(sc);acciones=[]
                for i in range(2):acciones.append({"id":str(i),"kind":"force" if forzado and (i==0)==izquierda else "continuous","target":str(i),"text":[{"t":"y"}]})
                activo="0" if izquierda else "1";st={"outputs":{activo:{"value":True}},"forces":[{"order":activo}]}
                x=0
                for a in acciones:x+=dg._caja_accion(pt,x,100,a,st,{},None,"A",set())
                rects=[i for i in sc.items() if isinstance(i,QGraphicsRectItem) and i.rect().height()==2*dg.H]
                on=next(i for i in rects if i.pen().color().name()==dg.COL["active"]);off=next(i for i in rects if i is not on)
                self.assertGreater(on.zValue(),off.zValue());self.assertEqual(on.rect().width(),off.rect().width())
                if QJS:
                    eng=QJSEngine();js=(ROOT/"tools/dibujo.js").read_text(encoding="utf-8").replace("{x, y, ...attrs}","Object.assign({x, y}, attrs)")
                    self.assertFalse(eng.evaluate(MOCK_DOM+js).isError())
                    r=eng.evaluate("var g=new MockEl('g'); var x=0; %s.forEach(a=>{x+=drawAction(g,x,100,a,%s).w;}); JSON.stringify(volcar(g));"%(json.dumps(acciones),json.dumps(st)))
                    self.assertFalse(r.isError(),r.toString());arbol=json.loads(r.toString())
                    self.assertEqual(arbol["hijos"][-1]["attrs"]["class"],"active-outlines")
                    borde=arbol["hijos"][-1]["hijos"][0]["attrs"]
                    self.assertEqual(borde["x"],0 if izquierda else off.rect().width());self.assertEqual(borde["width"],on.rect().width())

    def test_SREM09_lima_actividad_texto_con_contraste_y_seleccion_azul(self):
        """REQ-SIM-03, REQ-EDT-02: lima en actividad y texto verdadero; la marca histórica conserva el verde oscuro legible."""
        def lum(c):
            componentes=[int(c[i:i+2],16)/255 for i in (1,3,5)]
            return sum(w*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for w,v in zip((.2126,.7152,.0722),componentes))
        self.assertEqual(dg.COL["active"],"#40d641");self.assertNotEqual(dg.COL["accent"],dg.COL["active"])
        self.assertGreaterEqual((lum(dg.COL["panel"])+.05)/(lum(dg.COL["history"])+.05),4.5)
        css=(ROOT/"tools/dibujo.css").read_text(encoding="utf-8")
        self.assertIn("--sim:"+dg.COL["active"],css);self.assertIn("--truth:"+dg.COL["true_text"],css)
        self.assertIn(".active-outlines rect{fill:none;stroke:var(--sim)",css)
        oscuro=css.split("prefers-color-scheme:dark",1)[1].split("}",1)[0]
        panel=re.search(r"--panel:(#[0-9a-f]{6})",oscuro)[1]
        texto=re.search(r"--truth:(#[0-9a-f]{6})",oscuro)[1]
        self.assertGreaterEqual((lum(texto)+.05)/(lum(panel)+.05),4.5)
