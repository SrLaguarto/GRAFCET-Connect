"""Texto e imagen de presentación, apertura de paneles y propiedades compactas."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from grafcet.editor import Editor,new_grafcet_document
from test_editor_cadenas import BaseQt,QT


class NotasNucleo(unittest.TestCase):
    def test_SOTR01_presentacion_y_deshacer_sin_modificar_modelo(self):
        """REQ-EDT-02, REQ-EDT-05: crear, editar, mover y borrar notas solo cambia presentación y se deshace."""
        e=Editor(new_grafcet_document('m'));modelo=copy.deepcopy(e.model)
        n=e.add_annotation('text',(20,40),text='Ensayo',font='Arial',size=18,color='#326dcb')
        estados=[copy.deepcopy(e.presentation)]
        e.update_annotation(n,text='Otro texto',width=280);estados.append(copy.deepcopy(e.presentation))
        e.move_many({n:(60,80)});estados.append(copy.deepcopy(e.presentation))
        e.delete([n]);self.assertEqual(e.annotations(),[])
        for estado in reversed(estados):e.undo();self.assertEqual(e.presentation,estado)
        self.assertEqual(e.model,modelo)

    def test_SOTR02_copiar_parcial_y_nota_suelta_con_identidades_nuevas(self):
        """REQ-EDT-04, REQ-JER-05: las notas propias viajan con el parcial y una nota suelta se pega en el destino."""
        e=Editor(new_grafcet_document('m'));g=e.add_partial('G1')
        n=e.add_annotation('text',(20,40),text='Hola',partialRef=g)
        mp=e.paste(e.copy([g]),'g',at=(300,200))
        nueva=next(x for x in e.annotations() if x['id']==mp[n])
        self.assertEqual(nueva['partialRef'],mp[g]);self.assertEqual((nueva['x'],nueva['y']),(300,200))
        e2=Editor(new_grafcet_document('otro'));mp2=e2.paste(e.copy([n]),'g',at=(60,80))
        self.assertEqual(e2.annotations()[0]['partialRef'],'g');self.assertEqual(e2.annotations()[0]['text'],'Hola')
        self.assertNotEqual(mp2[n],n)
        e2.undo();self.assertEqual(e2.annotations(),[])
        e.delete([g]);self.assertNotIn(n,{x['id'] for x in e.annotations()});e.undo();self.assertIn(n,{x['id'] for x in e.annotations()})

if QT:
    from PySide6.QtCore import QPoint,QPointF,QEvent,Qt,QTimer
    from PySide6.QtGui import QImage,QFont
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QDialog,QPlainTextEdit,QFontComboBox,QSpinBox,QGraphicsPixmapItem,QGraphicsTextItem
    from escritorio.anotaciones import importar_imagen,editar_texto,rect
    from escritorio.diagrama import ancla_en,H,SX
    from escritorio import propiedades as pr


@unittest.skipUnless(QT,'requiere PySide6')
class OtrosInterfaz(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def preparar(self):
        w,e=self.vacio();w.resize(1366,768);w.show();QApplication.processEvents();return w,e

    def arrastrar(self,widget,delta):
        p=widget.rect().center();QTest.mousePress(widget,Qt.MouseButton.LeftButton,pos=p)
        destino=widget.mapToGlobal(p)+delta
        from PySide6.QtWidgets import QWidget
        receptor=QWidget.mouseGrabber() or widget
        QTest.mouseMove(receptor,receptor.mapFromGlobal(destino));QTest.mouseRelease(receptor,Qt.MouseButton.LeftButton,pos=receptor.mapFromGlobal(destino))
        QApplication.processEvents()

    def gesto(self,p,q):
        d=self.w.diagrama;vp=d.viewport();a=d.mapFromScene(p);b=d.mapFromScene(q)
        QTest.mousePress(vp,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(vp,b)
        QTest.mouseRelease(vp,Qt.MouseButton.LeftButton,pos=b);QApplication.processEvents()

    def test_SOTR03_pestanas_abren_minimo_o_distancia_y_la_izquierda_es_fija(self):
        """REQ-EDT-09: arrastrar una pestaña cerrada hacia el centro abre al mínimo o a la distancia elegida."""
        w,e=self.preparar()
        for nombre,delta in (('izquierdo',QPoint(24,0)),('derecho',QPoint(-24,0)),('inferior',QPoint(0,-24))):
            w._mostrar_panel(nombre,False);QApplication.processEvents();self.arrastrar(w.pestanas[nombre],delta)
            self.assertFalse(w._panel(nombre).isHidden(),nombre)
            dimension=w._panel(nombre).height() if nombre=='inferior' else w._panel(nombre).width()
            self.assertAlmostEqual(dimension,w._minimo_panel(nombre),delta=2)
        for nombre,delta,esperado in (('derecho',QPoint(-310,0),336),('inferior',QPoint(0,-250),276)):
            w._mostrar_panel(nombre,False);QApplication.processEvents();self.arrastrar(w.pestanas[nombre],delta)
            dimension=w._panel(nombre).height() if nombre=='inferior' else w._panel(nombre).width()
            self.assertAlmostEqual(dimension,esperado,delta=2)

    def test_SOTR04_divisores_cerrados_abren_hacia_el_centro(self):
        """REQ-EDT-09: el divisor de un panel cerrado admite el gesto de apertura, incluido Elementos."""
        w,e=self.preparar()
        for nombre,sp,delta in (('izquierdo',w.split_izquierdo,QPoint(24,0)),('derecho',w.split,QPoint(-300,0)),('inferior',w.vsplit,QPoint(0,-250))):
            w._mostrar_panel(nombre,False);QApplication.processEvents();self.arrastrar(sp.handle(1),delta)
            self.assertFalse(w._panel(nombre).isHidden(),nombre)
            self.assertGreaterEqual(w._panel(nombre).height() if nombre=='inferior' else w._panel(nombre).width(),w._minimo_panel(nombre))

    def test_SOTR05_texto_desde_paleta_se_mueve_redimensiona_y_deshace(self):
        """REQ-EDT-02, REQ-EDT-05: un Texto de Otros se selecciona, mueve y redimensiona mediante eventos reales."""
        w,e=self.preparar();self.assertEqual(pr.SECCIONES[-1],('Otros',('texto','imagen')))
        self.soltar_ficha('texto',QPointF(300,140));QApplication.processEvents();n=e.M['annotations'][0];ident=n['id']
        self.assertEqual(e.sel,[ident]);self.assertIn('Texto',w.props.titulo.text())
        self.gesto(rect(n).center(),rect(n).center()+QPointF(40,40))
        n=e.anotacion(ident);self.assertEqual((n['x'],n['y']),(240,180))
        antes=copy.deepcopy(e.ed.presentation);r=rect(n)
        self.gesto(r.bottomRight(),r.bottomRight()+QPointF(60,30))
        n=e.anotacion(ident);self.assertAlmostEqual(n['width'],260,delta=2);self.assertAlmostEqual(n['height'],130,delta=2)
        e.ed.undo();self.assertEqual(e.ed.presentation,antes)
        e.cambia();QTest.keyClick(w.diagrama,Qt.Key.Key_Delete);self.assertEqual(e.ed.annotations(),[])
        e.ed.undo();self.assertEqual(len(e.ed.annotations()),1)

    def test_SOTR06_png_y_jpg_incorporados_y_tamano_con_raton(self):
        """REQ-EDT-02, REQ-DAT-02: PNG/JPG se incorporan al proyecto, conservan proporciones y no dependen del archivo original."""
        w,e=self.preparar()
        for ext in ('png','jpg'):
            archivo=Path(self.tmp.name)/('foto.'+ext);im=QImage(120,60,QImage.Format.Format_RGB32);im.fill('#326dcb');self.assertTrue(im.save(str(archivo)))
            with patch('escritorio.anotaciones.QFileDialog.getOpenFileName',return_value=(str(archivo),'')):
                self.soltar_ficha('imagen',QPointF(300,140))
            archivo.unlink();QApplication.processEvents();n=e.M['annotations'][-1];r=rect(n)
            self.assertTrue(any(isinstance(i,QGraphicsPixmapItem) and not i.pixmap().isNull() for i in w.diagrama.scene().items()))
            self.gesto(r.bottomRight(),r.bottomRight()+QPointF(60,30));n=e.anotacion(n['id'])
            self.assertAlmostEqual(n['width']/n['height'],2);self.assertAlmostEqual(n['width'],180,delta=2)
            antes=copy.deepcopy(e.ed.presentation);e.ed.undo();self.assertEqual(e.ed.annotations()[-1]['width'],120);e.ed.redo();self.assertEqual(e.ed.presentation,antes)
            e.ed.delete([n['id']]);e.cambia()

    def test_SOTR07_dialogo_texto_edita_fuente_tamano_y_color(self):
        """REQ-EDT-02: el diálogo confirma texto, familia, tamaño y color; cancelar no modifica nada."""
        w,e=self.preparar()
        def aceptar():
            d=QApplication.activeModalWidget();d.findChild(QPlainTextEdit).setPlainText('Nota de prueba')
            d.findChild(QFontComboBox).setCurrentFont(QFont('Courier New'))
            d.findChild(QSpinBox).setValue(24);d.accept()
        QTimer.singleShot(0,aceptar);datos=editar_texto({'text':'Texto','color':'#326dcb'},w)
        self.assertEqual(datos,{'text':'Nota de prueba','font':'Courier New','size':24,'color':'#326dcb'})
        QTimer.singleShot(0,lambda:QApplication.activeModalWidget().reject());self.assertIsNone(editar_texto(datos,w))

    def test_SOTR08_etapa_interior_arrastra_y_borde_enlaza(self):
        """REQ-EDT-03: el interior cerca de los conectores mueve la etapa; el borde conserva el enlace."""
        w,e=self.preparar();w._abrir_opciones();s=e.ed.add_step('g','1',True,at=(200,140));e.cambia()
        p=QPointF(300,140+H-5);self.assertIsNone(ancla_en(e.M,p))
        self.assertEqual(ancla_en(e.M,QPointF(300,140+H))['id'],s)
        self.gesto(p,p+QPointF(60,40));self.assertEqual(self.pos(e)[s],(260,180));self.assertIsNone(e.enlace)
        self.assertFalse(w.props.der.isVisible());self.assertTrue(w.props.s_etiqueta.isVisible())
        textos=[x[0] for x in e.menu(QPointF(360,180))]
        self.assertIn('Convertir en encapsulante',textos)

    def test_SOTR09_accion_por_evento_reserva_mas_espacio_al_evento(self):
        """REQ-EDT-09: en una acción por evento el editor del evento es claramente mayor que el del valor."""
        w,e=self.preparar();w._abrir_opciones();n=e.ed.add_draft_action((200,140),{'tipo':'evento'});e.sel=[n];e.cambia();QApplication.processEvents()
        p=w.props;self.assertTrue(p.accion.caja_valor.isVisible());self.assertTrue(p.pagina_bloques.isVisible())
        self.assertGreater(p.pagina_bloques.width(),2*p.accion.caja_valor.width())

    def test_SOTR10_qt_y_js_dibujan_notas_y_proyecto_se_reabre(self):
        """REQ-DAT-02, REQ-EDT-09: texto e imagen se conservan al guardar y ambos renderizadores usan la misma geometría y estilo."""
        from test_dibujo_vista import dibujar_con_js
        from grafcet.persistence import open_project
        w,e=self.preparar();n=e.ed.add_annotation('text',(200,120),text='Hola',font='Arial',size=20,color='#326dcb')
        archivo=Path(self.tmp.name)/'guardada.png';im=QImage(60,30,QImage.Format.Format_RGB32);im.fill('#326dcb');im.save(str(archivo))
        with patch('escritorio.anotaciones.QFileDialog.getOpenFileName',return_value=(str(archivo),'')):datos=importar_imagen(w)
        e.ed.add_annotation('image',(440,120),**datos);archivo.unlink()
        e.cambia();QApplication.processEvents();texto=next(i for i in w.diagrama.scene().items() if isinstance(i,QGraphicsTextItem) and i.toPlainText()=='Hola')
        self.assertEqual(texto.font().pixelSize(),20);self.assertEqual(texto.defaultTextColor().name(),'#326dcb')
        dom=dibujar_con_js(e.M,{})
        def todos(n):
            yield n
            for hijo in n['hijos']:yield from todos(hijo)
        caja=next(x for x in todos(dom) if x['tag']=='foreignObject')
        self.assertEqual((caja['attrs']['x'],caja['attrs']['y'],caja['attrs']['width'],caja['attrs']['height']),(300,120,200,100))
        self.assertIn('font-size:20px',caja['hijos'][0]['attrs']['style']);self.assertIn('color:#326dcb',caja['hijos'][0]['attrs']['style'])
        imagen=next(x for x in todos(dom) if x['tag']=='image')
        self.assertEqual((imagen['attrs']['x'],imagen['attrs']['y'],imagen['attrs']['width'],imagen['attrs']['height']),(540,120,60,30))
        self.assertEqual(imagen['attrs']['href'],datos['data'])
        raiz=Path(self.tmp.name)/'proyecto';e.guardar(raiz);abierto=open_project(raiz)
        self.assertEqual(Editor(abierto.models()[0],abierto.doc('presentation',e.ed.presentation['id'])).annotations(),e.ed.annotations())
        from grafcet.view import Vista
        from grafcet.profile import normalize_options
        v=Vista('m','','',lambda:(e.ed.model,e.layout()),normalize_options(None),presentation=e.ed.presentation)
        self.assertEqual(v.model['annotations'],e.M['annotations'])

    def test_SOTR11_atajos_copian_cortan_y_pegan_texto_entre_proyectos(self):
        """REQ-EDT-04, REQ-EDT-05: el portapapeles de texto sobrevive al proyecto y cortar/pegar se deshace de una vez."""
        w,e=self.preparar();n=e.poner_anotacion('texto',QPointF(300,140));w.diagrama.setFocus()
        QTest.keyClick(w.diagrama,Qt.Key.Key_X,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(e.ed.annotations(),[]);self.assertIsNotNone(w._portapapeles)
        e.ed.undo();self.assertEqual(e.ed.annotations()[0]['id'],n)
        e.ed.dirty=False;w.nuevo();e=w.edicion;w.diagrama.setFocus();QApplication.processEvents()
        QTest.keyClick(w.diagrama,Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier);QApplication.processEvents()
        self.assertEqual(len(e.ed.annotations()),1);self.assertEqual(e.ed.annotations()[0]['text'],'Texto')
        e.ed.undo();self.assertEqual(e.ed.annotations(),[])

    def test_SOTR12_arrastrar_marco_mueve_texto_con_el_contenido_una_vez(self):
        """REQ-EDT-03, REQ-JER-05: la anotación de un parcial se mueve con su marco en una operación."""
        from escritorio.diagrama import cajas_parciales
        w,e=self.preparar();g=e.poner_parcial(QPointF(300,120));n=e.ed.add_annotation('text',(220,160),text='Nota',partialRef=g)
        e.cambia();QApplication.processEvents();c=cajas_parciales(e.M)[g];p=QPointF(c['x0'],c['y0']+40)
        antes=copy.deepcopy(e.ed.presentation);self.gesto(p,p+QPointF(40,40))
        self.assertEqual((e.anotacion(n)['x'],e.anotacion(n)['y']),(260,200));e.ed.undo();self.assertEqual(e.ed.presentation,antes)

    def test_SOTR13_cancelar_o_archivo_no_valido_no_crea_imagen(self):
        """REQ-DAT-02: cancelar o elegir datos que no son PNG/JPG conserva el proyecto y da un aviso breve."""
        w,e=self.preparar();antes=self.estado(e);avisos=[];e.informar=avisos.append
        with patch('escritorio.anotaciones.QFileDialog.getOpenFileName',return_value=('','')):
            self.soltar_ficha('imagen',QPointF(300,120))
        self.assertEqual(self.estado(e),antes)
        archivo=Path(self.tmp.name)/'rota.png';archivo.write_bytes(b'no es una imagen')
        with patch('escritorio.anotaciones.QFileDialog.getOpenFileName',return_value=(str(archivo),'')):
            self.soltar_ficha('imagen',QPointF(300,120))
        self.assertEqual(self.estado(e),antes);self.assertIn('No se puede leer',avisos[-1])
