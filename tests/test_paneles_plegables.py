"""Paneles plegables por arrastre y editor de condiciones compacto."""
import copy
import unittest
from pathlib import Path
from test_editor_cadenas import BaseQt,QT
from grafcet.builder import M
if QT:
    from PySide6.QtCore import Qt,QPoint,QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.edicion import Edicion
    from escritorio.ventana import Ventana


@unittest.skipUnless(QT,"requiere PySide6")
class Paneles(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def preparar(self,ancho=1366,alto=768):
        m=M().var("a").var("b").step("1",True).step("2").trans("t",["1"],["2"],"a")
        e=Edicion.desde(m.doc,{"1":(100,80),"t":(100,180),"2":(100,280)},"Paneles")
        w=self.w;w._establecer_edicion(e);w.resize(ancho,alto);w.show();w.editar_condicion("t");QApplication.processEvents()
        return w,e

    def arrastrar(self,divisor,delta):
        h=divisor.handle(1);p=h.rect().center()
        QTest.mousePress(h,Qt.MouseButton.LeftButton,pos=p)
        QTest.mouseMove(h,p+delta)
        QTest.mouseRelease(h,Qt.MouseButton.LeftButton,pos=p+delta)
        QApplication.processEvents()

    def test_SPAN01_cabeceras_y_pestanas_fuera_del_dibujo(self):
        """REQ-EDT-09: cada cabecera pliega y la pestaña nombrada recupera su panel, con menú y ajustes coherentes."""
        w,e=self.preparar()
        self.assertFalse(w.diagrama._bordes)
        for n,texto in (("izquierdo","Elementos"),("derecho","Variables"),("inferior","Propiedades")):
            self.assertTrue(w.flechas[n].isVisible())
            QTest.mouseClick(w.flechas[n],Qt.MouseButton.LeftButton);QApplication.processEvents()
            self.assertTrue(w._panel(n).isHidden());self.assertTrue(w.pestanas[n].isVisible())
            self.assertEqual(w.pestanas[n].text(),texto);self.assertFalse(w._accion_panel(n).isChecked())
            self.assertFalse(w.ajustes.value("paneles/"+n,True,type=bool))
            self.assertFalse(w.diagrama.isAncestorOf(w.pestanas[n]))
            QTest.mouseClick(w.pestanas[n],Qt.MouseButton.LeftButton);QApplication.processEvents()
            self.assertTrue(w._panel(n).isVisible());self.assertTrue(w._accion_panel(n).isChecked())

    def test_SPAN02_izquierdo_ancho_fijo_y_arrastre_para_plegar(self):
        """REQ-EDT-09: el izquierdo no se amplía; arrastrar hacia dentro lo pliega y su pestaña recupera el ancho fijo."""
        w,e=self.preparar();ancho=w.dock.width()
        self.arrastrar(w.split_izquierdo,QPoint(80,0))
        self.assertEqual(w.dock.width(),ancho);self.assertTrue(w.dock.isVisible())
        self.arrastrar(w.split_izquierdo,QPoint(-50,0))
        self.assertTrue(w.dock.isHidden());self.assertEqual(w._plegables["izquierdo"].width(),26)
        self.assertGreater(w.pestanas["izquierdo"].height(),100)
        QTest.mouseClick(w.pestanas["izquierdo"],Qt.MouseButton.LeftButton);QApplication.processEvents()
        self.assertEqual(w.dock.width(),ancho)

    def test_SPAN03_derecho_amplia_nombre_y_pliega_antes_de_comprimir_tabla(self):
        """REQ-EDT-07, REQ-EDT-09: solo Nombre absorbe el ancho extra; bajar del mínimo pliega y restaura el tamaño útil anterior."""
        w,e=self.preparar();t=w.variables.tabla
        antes=[t.columnWidth(i) for i in range(3)];ancho=w.derecho.width()
        self.arrastrar(w.split,QPoint(-80,0));amplio=w.derecho.width()
        self.assertGreater(amplio,ancho);self.assertGreater(t.columnWidth(0),antes[0])
        self.assertEqual([t.columnWidth(i) for i in (1,2)],antes[1:])
        self.arrastrar(w.split,QPoint(amplio-w._minimo_panel("derecho")+30,0))
        self.assertTrue(w.derecho.isHidden());self.assertTrue(w.pestanas["derecho"].isVisible())
        QTest.mouseClick(w.pestanas["derecho"],Qt.MouseButton.LeftButton);QApplication.processEvents()
        self.assertAlmostEqual(w.derecho.width(),amplio,delta=2)
        self.assertEqual([t.columnWidth(i) for i in (1,2)],antes[1:])

    def test_SPAN04_inferior_pliega_bajo_minimo_y_recupera_altura_por_atajo(self):
        """REQ-EDT-09: el editor no se comprime por debajo de su mínimo útil; la pestaña y Ctrl+J conservan la altura anterior."""
        w,e=self.preparar();self.arrastrar(w.vsplit,QPoint(0,-35));alto=w.inferior.height()
        formula=w.props.t_texto.text()
        self.arrastrar(w.vsplit,QPoint(0,alto-w._minimo_panel("inferior")+30))
        self.assertTrue(w.inferior.isHidden());self.assertEqual(w.vsplit.sizes()[1],26)
        self.assertEqual(w.pestanas["inferior"].text(),"Propiedades")
        w.activateWindow();w.setFocus();QApplication.processEvents()
        QTest.keyClick(w,Qt.Key.Key_J,Qt.KeyboardModifier.ControlModifier);QApplication.processEvents()
        self.assertTrue(w.inferior.isVisible());self.assertAlmostEqual(w.inferior.height(),alto,delta=2)
        self.assertEqual(w.props.t_texto.text(),formula)

    def test_SPAN05_formula_estado_y_controles_en_una_fila_con_vista_previa(self):
        """REQ-EDT-02, REQ-EDT-09: fórmula, estado, ampliar y papelera comparten fila; vista previa y edición manual siguen disponibles."""
        w,e=self.preparar();p=w.props
        centros=[c.mapTo(p,c.rect().center()).y() for c in (p.t_texto,p.t_estado,p.prog.ampliar,p.prog.papelera)]
        self.assertLessEqual(max(centros)-min(centros),3)
        self.assertFalse(p.detalles_bloques.isVisible());self.assertTrue(p.t_texto.isReadOnly())
        QTest.mouseClick(p.t_previa,Qt.MouseButton.LeftButton);QApplication.processEvents()
        self.assertTrue(p.t_vista.isVisible());self.assertTrue(p.t_dibujo.isVisible())
        self.assertIn("a",p.t_vista.text());QTest.mouseClick(p.t_previa,Qt.MouseButton.LeftButton)
        QTest.mouseClick(p.t_manual,Qt.MouseButton.LeftButton,pos=QPoint(8,p.t_manual.height()//2))
        self.assertFalse(p.t_texto.isReadOnly())
        p.t_texto.setFocus();p.t_texto.selectAll();QTest.keyClicks(p.t_texto,"a AND NOT b");p.t_texto.editingFinished.emit()
        self.assertEqual(e.texto_usuario("t"),"a AND NOT b")
        QTest.mouseClick(p.prog.ampliar,Qt.MouseButton.LeftButton);QApplication.processEvents()
        ventana=p.prog._ventana
        try:
            self.assertTrue(ventana.isVisible());self.assertEqual(p.prog._espejo.texto(),p.prog.texto())
        finally:ventana.close()

    def test_SPAN06_editor_compacto_util_a_1000_y_categorias_accesibles(self):
        """REQ-EDT-09: a 1000×600 los controles no se cortan, y las categorías largas conservan su desplazamiento."""
        w,e=self.preparar(1000,600);p=w.props
        self.assertLessEqual(w.minimumSizeHint().height(),600)
        for c in (p.t_texto,p.t_estado,p.prog.ampliar,p.prog.papelera):
            r=c.rect();esquina=c.mapTo(p,r.bottomRight())
            self.assertLessEqual(esquina.x(),p.width());self.assertLessEqual(esquina.y(),p.height())
        self.assertGreater(p.prog.lienzo.parentWidget().height(),40)
        self.assertEqual(len(p.prog.categorias),8)
        self.assertEqual(p.prog._sc_carpetas.horizontalScrollBarPolicy(),Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def test_SPAN07_preferencias_de_plegado_se_recuperan_en_otra_ventana(self):
        """REQ-EDT-09: las preferencias de visibilidad se recuerdan y siempre existe una pestaña para recuperar cada panel."""
        w,e=self.preparar()
        for n in w.flechas:w.flechas[n].click()
        w2=Ventana(w.ajustes,Path(self.tmp.name)/"otra-recuperacion")
        try:
            w2.nuevo();w2.resize(1366,768);w2.show();QApplication.processEvents()
            for n in w2.pestanas:
                self.assertTrue(w2._panel(n).isHidden(),n);self.assertTrue(w2.pestanas[n].isVisible(),n)
        finally:
            w2.hide();w2.edicion=None;w2.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SPAN08_simulacion_y_edicion_conservan_paneles_y_nombres_de_pestanas(self):
        """REQ-SIM-03, REQ-EDT-09: Play oculta Elementos, y los paneles de edición se recuperan sin perder sus preferencias."""
        w,e=self.preparar();w.flechas["derecho"].click();QApplication.processEvents()
        antes=w.vsplit.sizes()
        w.a_ejecutar.setChecked(True);w.rt.stop();QApplication.processEvents()
        self.assertFalse(w._plegables["izquierdo"].isVisible())
        self.assertEqual(w.pestanas["derecho"].text(),"Simulación")
        self.assertEqual(w.pestanas["inferior"].text(),"Traza")
        w.a_ejecutar.setChecked(False);QApplication.processEvents()
        self.assertTrue(w.dock.isVisible());self.assertTrue(w.derecho.isHidden());self.assertTrue(w.inferior.isVisible())
        self.assertEqual(w.pestanas["derecho"].text(),"Variables")
        self.assertEqual(w.vsplit.sizes(),antes)
