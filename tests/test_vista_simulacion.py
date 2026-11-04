"""Tamaños, encuadre y controles visuales al alternar edición y simulación."""
from pathlib import Path
import unittest
from test_editor_cadenas import BaseQt, QT
from grafcet.builder import M
if QT:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QPalette
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.ventana import _trazos_reinicio


@unittest.skipUnless(QT, "requiere PySide6")
class VistaSimulacion(BaseQt):
    def preparar(self):
        w=self.w
        m=M().var("marcha").var("fin").var("sensor").step("A",True).step("B").trans("t",["A"],["B"],"marcha")
        w.fuente={"tipo":"fichero","ruta":Path(self.tmp.name)/"m.json","doc":m.doc,
                  "layout":{"A":(220,80),"t":(220,180),"B":(220,280)},"titulo":"Vista","ayuda":"","raiz":None}
        w._cargar();w._abrir_opciones();w.resize(1366,768);w.show();self.procesar();w.rt.stop()
        return w,w.diagrama

    def procesar(self):
        for _ in range(8):self.app.processEvents()

    def ejecutar(self,w,on):
        w.a_ejecutar.setChecked(on);w.rt.stop();self.procesar()

    def pantalla(self,d,p):
        return d.viewport().mapToGlobal(d.mapFromScene(p))

    def test_SMOD01_play_stop_ancho_fijo_y_reiniciar_no_se_desplaza(self):
        """REQ-SIM-03, REQ-EDT-09: el ancho mayor de Play/Stop evita mover los controles siguientes."""
        w,d=self.preparar();b=w.tb_sim.widgetForAction(w.a_ejecutar);r=w.tb_sim.widgetForAction(w.a_reiniciar)
        ancho=b.width();x=r.mapToGlobal(r.rect().topLeft()).x()
        for on in (True,False,True,False):
            self.ejecutar(w,on);self.assertEqual(b.width(),ancho)
            self.assertGreaterEqual(ancho,b.sizeHint().width());self.assertEqual(r.mapToGlobal(r.rect().topLeft()).x(),x)

    def test_SMOD02_play_oculta_y_stop_restaura_tamanos_y_divisor_manual(self):
        """REQ-EDT-09, REQ-SIM-03: Play oculta paleta e inferior; Stop restaura sus tamaños y el reparto manual."""
        w,d=self.preparar();w.vsplit.moveSplitter(420,1);self.procesar()
        anterior=(w.dock.width(),w.derecho.width(),w.inferior.height(),w.vsplit.sizes())
        self.assertFalse(w._opciones_automaticas)
        self.ejecutar(w,True)
        self.assertTrue(w.dock.isHidden() and w.inferior.isHidden())
        self.assertEqual(w.derecho.width(),anterior[1])
        self.ejecutar(w,False)
        self.assertFalse(w.dock.isHidden() or w.inferior.isHidden())
        self.assertEqual((w.dock.width(),w.derecho.width(),w.inferior.height(),w.vsplit.sizes()),anterior)

    def test_SMOD03_plegado_previo_y_ancho_derecho_manual_se_conservan(self):
        """REQ-EDT-09: se respetan los paneles plegados previamente y el ancho que el usuario haya dejado con el divisor."""
        w,d=self.preparar();w.flechas["inferior"].click();w.flechas["izquierdo"].click()
        self.ejecutar(w,True);w.split.moveSplitter(w.split.width()-350,1);self.procesar();ancho=w.derecho.width()
        self.ejecutar(w,False);self.assertTrue(w.dock.isHidden() and w.inferior.isHidden())
        self.assertEqual(w.derecho.width(),ancho)
        self.ejecutar(w,True);self.assertEqual(w.derecho.width(),ancho)

    def test_SMOD04_zoom_y_puntos_en_pantalla_iguales_al_entrar_y_salir(self):
        """REQ-EDT-09, REQ-SIM-03: la geometría en pantalla se conserva aunque se amplíe el área visible al ocultar paneles."""
        w,d=self.preparar();d.zoom(1.35);d.horizontalScrollBar().setValue(d.horizontalScrollBar().value()+75)
        d.verticalScrollBar().setValue(d.verticalScrollBar().value()+30);self.procesar()
        puntos=[QPointF(292,80),QPointF(480,310)];antes=[self.pantalla(d,p) for p in puntos];k=d.escala()
        for on in (True,False,True,False):
            self.ejecutar(w,on);self.assertAlmostEqual(d.escala(),k)
            for p,q in zip(puntos,antes):self.assertLessEqual((self.pantalla(d,p)-q).manhattanLength(),1)
            w.refrescar();self.procesar()
            for p,q in zip(puntos,antes):self.assertLessEqual((self.pantalla(d,p)-q).manhattanLength(),1)

    def test_SMOD05_encuadre_extremo_a_1000_y_centrar_sigue_disponible(self):
        """REQ-EDT-09: se conserva el encuadre cerca del límite de desplazamiento, y Centrar todo mantiene su función."""
        w,d=self.preparar();w.resize(1000,600);self.procesar();d.zoom(1.7)
        d.horizontalScrollBar().setValue(d.horizontalScrollBar().minimum());self.procesar()
        p=QPointF(292,80);q=self.pantalla(d,p);k=d.escala()
        for on in (True,False):
            self.ejecutar(w,on);self.assertAlmostEqual(d.escala(),k)
            self.assertLessEqual((self.pantalla(d,p)-q).manhattanLength(),1)
        d.b_ajustar.click();self.procesar();self.assertNotAlmostEqual(d.escala(),k)

    def test_SMOD06_stop_y_reiniciar_desde_es_por_boton_y_atajo(self):
        """REQ-SIM-03, REQ-SIM-04: botones y atajos inactivos en E/S; volver a GRAFCET los recupera con el conmutador coherente."""
        w,d=self.preparar()
        for accion in (w.a_ejecutar,w.a_reiniciar):
            for atajo in (False,True):
                self.ejecutar(w,True);w.a_es.trigger();self.procesar();self.assertEqual(w.paginas_es.currentIndex(),1)
                if atajo:
                    w.activateWindow();w.setFocus();QTest.keySequence(w,accion.shortcut())
                else:QTest.mouseClick(w.tb_sim.widgetForAction(accion),Qt.MouseButton.LeftButton)
                self.procesar();self.assertEqual(w.paginas_es.currentIndex(),1)
                self.assertTrue(w.a_es.isChecked());self.assertFalse(accion.isEnabled())
                self.assertTrue(w.a_ejecutar.isChecked())
                w.a_es.trigger();self.procesar()
                self.assertEqual(w.paginas_es.currentIndex(),0);self.assertTrue(accion.isEnabled())
                self.assertFalse(w.a_es.isChecked());self.assertEqual(w.a_es.text(),"E/S externas")

    def test_SMOD07_pulsador_interruptor_y_ctrl_se_distinguen_sin_cambiar_texto(self):
        """REQ-SIM-02, REQ-SIM-03: iconos distintos distinguen tipo y enclavamiento y se actualizan al liberar Ctrl."""
        w,d=self.preparar();self.ejecutar(w,True);w._cambiar_tipo_entrada("fin",True)
        QTest.mouseClick(w.botones["fin"],Qt.MouseButton.LeftButton)
        QTest.mouseClick(w.botones["sensor"],Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier)
        firma=lambda b:bytes(b.icon().pixmap(20,16).toImage().constBits())
        self.assertEqual(len({firma(w.botones[v]) for v in ("marcha","fin","sensor")}),3)
        antes=firma(w.botones["sensor"]);QTest.keyRelease(w,Qt.Key.Key_Control)
        self.assertNotEqual(firma(w.botones["sensor"]),antes)
        self.assertEqual(w.botones["sensor"].text(),"sensor = 0");self.assertTrue(w.botones["fin"].isChecked())

    def test_SMOD08_cabecera_es_solo_verde_o_color_original(self):
        """REQ-SIM-03: desconexión y fallo restauran el fondo neutro manteniendo sus mensajes."""
        w,d=self.preparar();p=w.panel_es;w._mostrar_pagina(True);self.procesar()
        inicial=p.cabecera.palette().color(QPalette.ColorRole.Window)
        p.mostrar_estado("conectado","Conectado");self.procesar()
        self.assertNotEqual(p.cabecera.palette().color(QPalette.ColorRole.Window),inicial)
        for estado in ("error","desconectado","diagnostico"):
            p.mostrar_estado(estado,"Aviso "+estado);self.procesar()
            self.assertEqual(p.cabecera.property("estadoVisual"),"neutro")
            self.assertEqual(p.cabecera.palette().color(QPalette.ColorRole.Window),inicial)
            self.assertEqual(p.estado.text(),"Aviso "+estado)

    def test_SMOD09_punta_reiniciar_en_extremo_y_simetrica_a_tangente(self):
        """REQ-EDT-09: la punta angular de la referencia continúa la tangente, con brazos simétricos."""
        arco,punta=_trazos_reinicio();e=arco.currentPosition();a,b,c=[punta.elementAt(i) for i in range(3)]
        self.assertAlmostEqual(b.x-e.x(),3*2**-.5);self.assertAlmostEqual(b.y-e.y(),-3*2**-.5)
        t=QPointF(2**-.5,-2**-.5);n=QPointF(t.y(),-t.x())
        proy=lambda p,v:(p.x-e.x())*v.x()+(p.y-e.y())*v.y()
        self.assertAlmostEqual(proy(a,t),proy(c,t));self.assertLess(proy(a,t),proy(b,t))
        self.assertAlmostEqual(proy(a,n),-proy(c,n));self.assertNotAlmostEqual(proy(a,n),0)

    def test_SMOD10_variables_texto_mas_margenes_cabe_sin_ensanchar_panel(self):
        """REQ-EDT-07, REQ-EDT-09: se conserva la corrección anterior, con dos columnas y espacio para texto y relleno."""
        w,d=self.preparar();p=w.variables
        self.assertEqual(w.derecho.width(),w.ancho_lateral)
        for b in (*p.b_nuevas.values(),p.b_quitar):
            self.assertGreaterEqual(b.width(),b.fontMetrics().horizontalAdvance(b.text())+16)

    def test_SMOD11_altura_automatica_previa_se_restaura_con_receptividad_seleccionada(self):
        """REQ-EDT-09, REQ-SIM-03: también la altura automática del editor se conserva al parar, sin un nuevo reparto."""
        w,d=self.preparar();w.edicion.seleccionar(["t"]);self.procesar();self.assertTrue(w._opciones_automaticas)
        altura=w.inferior.height();tamanos=w.vsplit.sizes()
        self.ejecutar(w,True);self.ejecutar(w,False)
        self.assertEqual(w.inferior.height(),altura);self.assertEqual(w.vsplit.sizes(),tamanos)

    def test_SMOD12_abrir_otro_ejemplo_cancela_restauraciones_pendientes(self):
        """REQ-EDT-01, REQ-EDT-09: abrir otra fuente permite el encuadre inicial, sin aplicar el del proyecto anterior."""
        from unittest import mock
        w,d=self.preparar();d.zoom(1.45)
        w.a_ejecutar.setChecked(True);w.rt.stop();w.a_ejecutar.setChecked(False)
        w.edicion.ed.dirty=False
        with mock.patch.object(d,"restaurar_encuadre",wraps=d.restaurar_encuadre) as restaurar:
            w.cargar_ejemplo("temporizada");self.procesar();escala=d.escala()
            # El ejemplo pliega los paneles: su encuadre inicial usa esa geometría ya asentada.
            self.procesar();restaurar.assert_not_called()
        self.assertAlmostEqual(d.escala(),escala)

    def test_SMOD13_entradas_booleanas_y_numericas_caben_en_el_ancho_conservado(self):
        """REQ-SIM-03, REQ-EDT-09: conservar el ancho derecho no recorta pulsadores, interruptores ni edición numérica."""
        w,d=self.preparar();w.edicion.nueva_variable("nivel","input",{"kind":"decimal","scale":2})
        self.ejecutar(w,True);self.assertEqual(w.derecho.width(),w.ancho_lateral)
        limite=w.scroll.viewport().mapToGlobal(w.scroll.viewport().rect().topRight()).x()
        for b in [*w.botones.values(),*w.campos.values()]:
            self.assertLessEqual(b.mapToGlobal(b.rect().topRight()).x(),limite)
        for var in ("marcha","fin","sensor"):
            b=w.botones[var]
            self.assertGreaterEqual(b.width(),b.fontMetrics().horizontalAdvance(b.text())+b.iconSize().width()+24)
