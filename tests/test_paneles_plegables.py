"""Paneles plegables por arrastre y editor de condiciones compacto."""
import copy
import unittest
from pathlib import Path
from test_editor_cadenas import BaseQt,QT
from grafcet.builder import M
if QT:
    from PySide6.QtCore import QEvent, QPoint, QRect, Qt
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
        w = self.w
        w._establecer_edicion(e)
        w.resize(ancho, alto)
        w.show()
        w.editar_condicion("t")
        QApplication.processEvents()
        w.flot.cerrar()
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
        for n,texto in (("derecho", "Variables"),):
            self.assertTrue(w.flechas[n].isVisible())
            QTest.mouseClick(w.flechas[n],Qt.MouseButton.LeftButton);QApplication.processEvents()
            self.assertTrue(w._panel(n).isHidden());self.assertTrue(w.pestanas[n].isVisible())
            self.assertEqual(w.pestanas[n].text(), texto)
            self.assertFalse(w._accion_panel(n).isChecked())
            self.assertFalse(w.ajustes.value("paneles/"+n,True,type=bool))
            self.assertFalse(w.diagrama.isAncestorOf(w.pestanas[n]))
            QTest.mouseClick(w.pestanas[n],Qt.MouseButton.LeftButton);QApplication.processEvents()
            self.assertTrue(w._panel(n).isVisible());self.assertTrue(w._accion_panel(n).isChecked())


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



    def test_SPAN06_editor_compacto_util_a_1000_y_categorias_accesibles(self):
        """REQ-EDT-09: los controles de la flotante y la banda de sus categorías caben a 1000×600 (E8: cuatro categorías, sin pestañas)."""
        w, e = self.preparar(1000, 600)
        w._abrir_opciones()
        QApplication.processEvents()
        p = w.props
        self.assertTrue(w.flot.hay_ventanas())
        self.assertGreater(p.prog.lienzo.parentWidget().height(), 40)
        self.assertEqual(len(p.prog.categorias), 4)
        zona = p.prog.banda
        for boton in list(p.prog.categorias.values()) + [b for bs in p.prog.banda.botones.values() for b in bs]:
            self.assertTrue(boton.isVisible())
            caja = QRect(boton.mapTo(zona, QPoint()), boton.size())
            self.assertTrue(zona.rect().contains(caja), boton.text())

    def test_SPAN07_preferencias_de_plegado_se_recuperan_en_otra_ventana(self):
        """REQ-EDT-09: se recuerda el plegado de Variables."""
        w,e=self.preparar()
        for n in w.flechas:w.flechas[n].click()
        w2=Ventana(w.ajustes)
        try:
            w2.nuevo();w2.resize(1366,768);w2.show();QApplication.processEvents()
            for n in ("derecho",):
                plegado = True
                self.assertEqual(w2._panel(n).isHidden(),plegado,n);self.assertEqual(w2.pestanas[n].isVisible(),plegado,n)
        finally:
            w2.hide();w2.edicion=None;w2.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SPAN08_simulacion_y_edicion_conservan_paneles_y_nombres_de_pestanas(self):
        """REQ-SIM-03, REQ-EDT-09: Play y Pausa conservan Variables, Simulación y Traza."""
        w,e=self.preparar()
        w.flechas["derecho"].click();QApplication.processEvents()
        antes=w.vsplit.sizes()
        w.a_ejecutar.setChecked(True);w.rt.stop();QApplication.processEvents()
        self.assertFalse(w.favoritos.isVisible())
        self.assertEqual(w.pestanas["derecho"].text(),"Simulación")
        self.assertEqual(w.pestanas["inferior"].text(),"Traza")
        w.a_ejecutar.setChecked(False);QApplication.processEvents()
        self.assertTrue(w.favoritos.isVisible())
        self.assertTrue(w.derecho.isHidden())
        self.assertTrue(w.inferior.isHidden())
        self.assertEqual(w.pestanas["derecho"].text(),"Variables")
        self.assertEqual(w.vsplit.sizes(),antes)


    def test_SPAN10_pestanas_plegadas_sin_hueco_al_volver_de_es(self):
        """REQ-EDT-09: cambiar de pantalla en E/S no reserva el ancho del contenido plegado."""
        w,e=self.preparar(2500,1400)
        w._mostrar_panel("derecho", False)
        QApplication.processEvents()
        for ancho in (1000,1900,1100):
            QTest.mouseClick(w.luz_es,Qt.MouseButton.LeftButton)
            w.resize(ancho,1000);QApplication.processEvents();w._poner_modo();QApplication.processEvents()
            QTest.mouseClick(w.pestanas_vistas,Qt.MouseButton.LeftButton,pos=w.pestanas_vistas.tabRect(0).center())
            QApplication.processEvents()
            self.assertEqual(w.paginas_es.currentIndex(),0)
            self.assertFalse(w._plegables['derecho'].abierto)
            self.assertEqual(w.split.sizes()[1],w._plegables['derecho'].GROSOR_PESTANA)
            self.assertEqual(w.split.sizes()[0]+w.split.sizes()[1]+w.split.handleWidth(),w.split.contentsRect().width())
            self.assertGreater(w.split.sizes()[0],w.width()-100)

    def test_SPAN11_ancho_elegido_se_conserva_tras_es_y_redimensionar(self):
        """REQ-EDT-09: el lateral abierto conserva el ancho elegido sin absorber el dibujo al volver de E/S."""
        w,e=self.preparar(2500,1400)
        self.arrastrar(w.split,QPoint(-100,0));ancho=w._plegables['derecho'].width()
        QTest.mouseClick(w.luz_es,Qt.MouseButton.LeftButton)
        w.resize(1100,1000);QApplication.processEvents();w._poner_modo();QApplication.processEvents()
        QTest.mouseClick(w.pestanas_vistas,Qt.MouseButton.LeftButton,pos=w.pestanas_vistas.tabRect(0).center())
        QApplication.processEvents()
        self.assertTrue(w._plegables['derecho'].abierto)
        self.assertAlmostEqual(w._plegables['derecho'].width(),ancho,delta=2)
        self.assertGreater(w.split.sizes()[0],300)
