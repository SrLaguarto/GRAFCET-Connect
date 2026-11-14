"""Página Planos integrada, navegación, persistencia, zoom y comandos reales."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_editor_cadenas import BaseQt,QT
from grafcet.laminas import ajustes_lamina
if QT:
    from PySide6.QtCore import Qt,QEvent,QPointF,QPoint
    from PySide6.QtGui import QWheelEvent
    from escritorio.diagrama import posiciones
    from PySide6.QtWidgets import QApplication,QDialog
    from PySide6.QtTest import QTest
    from escritorio.laminas import DialogoLaminas,DocumentoLaminas
    from escritorio.carpetas import predeterminada


@unittest.skipUnless(QT,'requiere PySide6')
class PlanosIntegrados(BaseQt):
    def setUp(self):
        self.docs=tempfile.TemporaryDirectory();self.rutas=patch('escritorio.carpetas.QStandardPaths.writableLocation',return_value=self.docs.name);self.rutas.start();super().setUp()
    def tearDown(self):
        self.w.panel_planos.guardar_timer.stop();self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.rutas.stop();self.docs.cleanup()
    def preparar(self):
        w,e=self.vacio();s=e.ed.add_step('g','1',True);e.cambia();e.sel=[s];e.ed.dirty=False;w.show();QApplication.processEvents();return w,e,s
    def crear_hoja(self,e,refs=None):
        plan=e.ed.add_sheet_plan('Plano de pruebas');ident=e.ed.add_plan_page(plan,ajustes_lamina({'plantilla':predeterminada()}))
        if refs:e.ed.set_page_graphics(ident,[{'refs':refs,'porcentaje':100.,'offset_mm':[0.,0.]}])
        return ident
    def pulsar_planos(self):
        barra=self.w.pestanas_vistas;QTest.mouseClick(barra,Qt.MouseButton.LeftButton,pos=barra.tabRect(1).center());QApplication.processEvents()
        return self.w.panel_planos
    def test_SPAG01_planos_es_pagina_incrustada_sin_editor_modal(self):
        """REQ-EDT-11: el botón Planos abre una página de la ventana, con lista, lienzo y propiedades."""
        w,e,s=self.preparar();self.crear_hoja(e,[s]);e.ed.dirty=False
        with patch.object(DialogoLaminas,'exec') as modal:p=self.pulsar_planos();modal.assert_not_called()
        self.assertEqual(w.paginas_es.currentIndex(),2);self.assertIs(w.paginas_es.currentWidget(),p)
        self.assertFalse(p.editor.isWindow());self.assertFalse(p.editor.isModal());self.assertTrue(p.editor.isVisible());self.assertIsNone(QApplication.activeModalWidget())
        self.assertTrue(w.a_planos.isChecked());self.assertFalse(w.a_es.isChecked());self.assertEqual(p.lista.count(),1)
        self.assertGreater(p.editor.area.viewport().width(),250);self.assertFalse(e.ed.dirty)
        QTest.keyClick(p.editor.vista,Qt.Key.Key_Escape);self.assertTrue(p.editor.isVisible());self.assertEqual(w.paginas_es.currentIndex(),2)
    def test_SPAG02_navegar_grafcet_planos_es_y_controles_coherentes(self):
        """REQ-EDT-11, REQ-SIM-03: GRAFCET, Planos y E/S conservan sus botones y bloquean Play/Reiniciar en Planos."""
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);p=self.pulsar_planos();antes=copy.deepcopy(e.ed.model)
        for a in (w.a_ejecutar,w.a_reiniciar,w.a_borrar,w.a_debajo):self.assertFalse(a.isEnabled())
        QTest.mouseClick(w.tb_sim.widgetForAction(w.a_ejecutar),Qt.MouseButton.LeftButton);QTest.keyClick(p.editor.vista,Qt.Key.Key_Delete)
        self.assertEqual(e.ed.model,antes);self.assertEqual(w.modo,'editar')
        QTest.mouseClick(w.luz_es,Qt.MouseButton.LeftButton);self.assertEqual(w.paginas_es.currentIndex(),1);self.assertFalse(w.a_planos.isChecked());self.assertTrue(w.a_es.isChecked())
        p=self.pulsar_planos();self.assertEqual(w.paginas_es.currentIndex(),2);self.assertFalse(w.a_es.isChecked())
        QTest.mouseClick(w.pestanas_vistas,Qt.MouseButton.LeftButton,pos=w.pestanas_vistas.tabRect(0).center());self.assertEqual(w.paginas_es.currentIndex(),0);self.assertFalse(w.a_planos.isChecked());self.assertTrue(w.a_ejecutar.isEnabled())
    def test_SPAG03_guardar_aplica_cambios_sin_esperar_el_temporizador(self):
        """REQ-DAT-02, REQ-EDT-11: Ctrl+S incluye los campos recién editados en Planos sin necesitar Aplicar."""
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);p=self.pulsar_planos();modelo=copy.deepcopy(e.ed.model);p.a_texto.trigger();QTest.mouseClick(p.editor.vista,Qt.MouseButton.LeftButton,pos=self.punto_mm(p.editor.vista,40,60));campo=p.editor.editor_textos.contenido;campo.setFocus();campo.selectAll();QTest.keyClicks(campo,'Plano guardado')
        ruta=Path(self.tmp.name)/'plano.grafnet'
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=(str(ruta),'')):
            QTest.keyClick(campo,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(ruta.exists());self.assertEqual(e.ed.sheet_links()[0]['ajustes']['plantilla']['primitives'][-1]['text'],'Plano guardado');self.assertEqual(e.ed.model,modelo)
        self.assertTrue(w.abrir_ruta(ruta));self.assertIs(w.panel_planos.origen,w.edicion)
        self.assertEqual(w.edicion.ed.sheet_links()[0]['ajustes']['plantilla']['primitives'][-1]['text'],'Plano guardado')
    def test_SPAG04_cambio_vista_y_cancelacion_de_nuevo_no_pierden_campos(self):
        """REQ-EDT-05, REQ-EDT-11: salir de Planos aplica los campos y cancelar Nuevo conserva el proyecto."""
        from PySide6.QtWidgets import QMessageBox
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);p=self.pulsar_planos();p.editor.campos['autor'].setText('Autor editado')
        with patch('escritorio.ventana.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel):w.nuevo()
        self.assertIs(w.edicion,e);self.assertEqual(e.ed.sheet_links()[0]['ajustes']['campos']['autor'],'Autor editado');self.assertTrue(e.ed.dirty)
        w._mostrar_pagina(False);e.ed.rename(s,'Actualizada');e.cambia();p=self.pulsar_planos()
        self.assertEqual(p.editor.modelo['steps'][0]['label'],'Actualizada');self.assertEqual(p.editor.campos['autor'].text(),'Autor editado')
    def test_SPAG05_lista_de_hojas_aplica_campos_y_refleja_el_original(self):
        """REQ-EDT-11: las hojas de la izquierda muestran su selección vinculada y guardan sus ajustes por separado."""
        w,e,s=self.preparar();t=e.ed.add_step('g','2',at=(250,180));e.cambia();cfg=ajustes_lamina({'plantilla':predeterminada()})
        a=e.ed.add_sheet_link([s],cfg,'Hoja A');b=e.ed.add_sheet_link([t],cfg,'Hoja B');p=self.pulsar_planos();self.assertEqual(p.lista.count(),2)
        punto=p.lista.visualItemRect(p.lista.item(0)).center();QTest.mouseClick(p.lista.viewport(),Qt.MouseButton.LeftButton,pos=punto)
        self.assertEqual(p.hoja_id,a);self.assertEqual([x['id'] for x in p.editor.modelo['steps']],[s]);p.editor.campos['numero'].setText('GC-A')
        punto=p.lista.visualItemRect(p.lista.item(1)).center();QTest.mouseClick(p.lista.viewport(),Qt.MouseButton.LeftButton,pos=punto)
        self.assertEqual(p.hoja_id,b);self.assertEqual(e.ed.sheet_links()[0]['ajustes']['campos']['numero'],'GC-A');self.assertEqual(p.editor.campos['numero'].text(),'')
        w._mostrar_pagina(False);e.ed.rename(s,'Nuevo nombre');e.cambia();w.mostrar_hoja(a)
        self.assertEqual(p.editor.modelo['steps'][0]['label'],'Nuevo nombre');self.assertEqual(p.editor.campos['numero'].text(),'GC-A')
    def test_SPAG06_zoom_visual_no_cambia_escala_ni_cajetin_y_exporta_limpio(self):
        """REQ-EDT-11: zoom y selección de colocación afectan solo a la pantalla, sin cambiar el PDF/SVG."""
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);p=self.pulsar_planos();QApplication.processEvents();d=p.editor.documento;factor=d.factor;cajetin=copy.deepcopy(d.plantilla.p['title_box']);modelo=copy.deepcopy(e.ed.model)
        p.zoom_combo.setCurrentIndex(p.zoom_combo.findData(2.));QApplication.processEvents();self.assertGreater(p.editor.area.verticalScrollBar().maximum(),0)
        self.assertEqual(p.editor.documento.factor,factor);self.assertEqual(p.editor.documento.plantilla.p['title_box'],cajetin)
        p.zoom_combo.setCurrentIndex(0);QApplication.processEvents();v=p.editor.vista;r=d.capas[0].destino(0);esc=min((v.width()-24)/d.ancho,(v.height()-24)/d.alto)
        a=QPoint(round((v.width()-d.ancho*esc)/2+r.center().x()*esc),round((v.height()-d.alto*esc)/2+r.center().y()*esc));QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=a);self.assertTrue(v.seleccionado)
        ruta=Path(self.tmp.name)/'sin-seleccion.svg';d.exportar_svg(ruta);self.assertNotIn('#326dcb',ruta.read_text(encoding='utf-8').lower());self.assertEqual(e.ed.model,modelo)
    def test_SPAG07_imprimir_y_exportar_desde_el_plano_actual(self):
        """REQ-EDT-11: Ctrl+P y la barra imprimen/exportan la hoja seleccionada, sin abrir otro editor."""
        w,e,s=self.preparar();cfg=ajustes_lamina({'plantilla':predeterminada()});ident=e.ed.add_sheet_link([s],cfg,'Actual');w.mostrar_hoja(ident);QApplication.processEvents();p=w.panel_planos;campo=p.editor.vista;campo.setFocus()
        with patch.object(DocumentoLaminas,'imprimir',return_value=True) as imprimir,patch.object(DialogoLaminas,'exec') as modal:
            QTest.keyClick(campo,Qt.Key.Key_P,Qt.KeyboardModifier.ControlModifier);self.assertEqual(imprimir.call_count,1);modal.assert_not_called()
        self.assertEqual(p.hoja_id,ident);ruta=Path(self.tmp.name)/'actual.svg'
        with patch('escritorio.laminas.QFileDialog.getSaveFileName',return_value=(str(ruta),'Dibujo SVG (*.svg)')):p.a_exportar.trigger()
        self.assertTrue(ruta.is_file());self.assertIsNone(QApplication.activeModalWidget())
    def test_SPAG08_cambios_se_aplican_en_memoria_sin_autoguardado_a_archivo(self):
        """REQ-DAT-02, REQ-EDT-11: editar un campo deja el proyecto modificado, pero no guarda archivos automáticamente."""
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);p=self.pulsar_planos();p.editor.campos['revision'].setText('C')
        with patch('escritorio.archivos.guardar_grafnet') as escribir:QTest.qWait(450);escribir.assert_not_called()
        self.assertEqual(e.ed.sheet_links()[0]['ajustes']['campos']['revision'],'C');self.assertTrue(e.ed.dirty);self.assertIn('*',p.titulo.text())

    def test_SPAG09_planos_vacio_hasta_creacion_explicita(self):
        """REQ-EDT-11: abrir Planos no crea hojas ni añade el dibujo completo por defecto."""
        w,e,s=self.preparar();antes=copy.deepcopy(e.ed.presentation);p=self.pulsar_planos()
        self.assertIsNone(p.editor);self.assertEqual(p.lista.count(),0);self.assertFalse(hasattr(p,'planes'));self.assertIn('Todavía no hay hojas',p.vacio.text());self.assertEqual(e.ed.presentation,antes)
        from escritorio.hojas import CrearHoja
        with patch.object(CrearHoja,'exec',lambda d:(d.accept() or QDialog.DialogCode.Accepted)):p.a_hoja.trigger()
        self.assertEqual(p.lista.count(),1);self.assertEqual(p.graficos,[]);self.assertIsNotNone(p.editor.documento);self.assertFalse(p.editor.documento.capas)

    def test_SPAG10_traer_seleccion_explicita_confirmar_y_cancelar(self):
        """REQ-EDT-11: Traer vuelve al editor y solo incluye los elementos seleccionados al confirmar."""
        w,e,s=self.preparar();otro=e.ed.add_step('g','2',at=(0,120));e.cambia();ident=self.crear_hoja(e);p=self.pulsar_planos()
        p.a_nueva.trigger();self.assertEqual(w.paginas_es.currentIndex(),0);self.assertTrue(w.aviso_traer.isVisible());e.sel=[s]
        QTest.mouseClick(w.b_confirmar_traer,Qt.MouseButton.LeftButton);self.assertEqual(w.paginas_es.currentIndex(),2)
        self.assertEqual(p.graficos[0]['refs'],[s]);self.assertEqual([x['id'] for x in p.editor.modelo['steps']],[s]);self.assertNotIn(otro,p.graficos[0]['refs'])
        p.a_nueva.trigger();e.sel=[otro];w.cancelar_traer();self.assertEqual(len(p.graficos),1);self.assertIsNone(w.destino_traer)

    def test_SPAG11_varios_planos_hojas_y_dibujos_persisten(self):
        """REQ-DAT-02, REQ-EDT-11: cada plano conserva varias hojas y cada hoja varias selecciones vinculadas."""
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);plan=e.ed.sheet_plans()[0]['id'];h2=e.ed.add_plan_page(plan,ajustes_lamina());otro=e.ed.add_sheet_plan('Otro plano');h3=e.ed.add_plan_page(otro,ajustes_lamina());p=self.pulsar_planos();w.mostrar_hoja(ident);p.insertar([s])
        self.assertEqual(p.lista.count(),3);self.assertEqual(len(p.editor.documento.capas),2);self.assertFalse(p.editor.documento.capas[0].destino(0).intersects(p.editor.documento.capas[1].destino(0)))
        self.assertEqual(p.editor.documento.campos(0)['hoja'], '1 de 3')
        self.assertEqual(p.editor.pagina.text(), 'Hoja 1 de 3')
        QTest.mouseClick(p.lista.viewport(), Qt.MouseButton.LeftButton,
                         pos=p.lista.visualItemRect(p.lista.item(1)).center())
        self.assertEqual(p.hoja_id, h2)
        self.assertEqual(p.editor.pagina.text(), 'Hoja 2 de 3')
        w.mostrar_hoja(h2)
        self.assertEqual(p.editor.documento.campos(0)['hoja'], '2 de 3')
        w.mostrar_hoja(h3);self.assertEqual(p.lista.count(),3);ruta=Path(self.tmp.name)/'varios.grafnet';self.assertTrue(w._guardar_archivo(ruta));self.assertTrue(w.abrir_ruta(ruta))
        self.assertEqual(len(w.edicion.ed.sheet_plans()),2);self.assertEqual(len(w.edicion.ed.sheet_links()),3);self.assertEqual(len(w.edicion.ed.sheet_links()[0]['grafcets']),2)

    def test_SPAG12_tamano_impreso_50_200_no_modifica_original(self):
        """REQ-EDT-11: cada GRAFCET se escala del 50 al 200 %, conservando los 11,64 mm de referencia al 100 %."""
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);p=self.pulsar_planos();m=copy.deepcopy(e.ed.model);f=p.editor.documento.capas[0].factor
        self.assertAlmostEqual(f*44,11.6416666667)
        for porcentaje in (50,200,100):
            p.tamano.setValue(porcentaje);self.assertAlmostEqual(p.editor.documento.capas[0].factor,f*porcentaje/100);self.assertEqual(e.ed.sheet_links()[0]['grafcets'][0]['porcentaje'],porcentaje)
        self.assertEqual((p.tamano.minimum(),p.tamano.maximum()),(50,200));self.assertEqual(e.ed.model,m)
        e.ed.undo();self.assertEqual(e.ed.sheet_links()[0]['grafcets'][0]['porcentaje'],200);e.ed.redo();self.assertEqual(e.ed.sheet_links()[0]['grafcets'][0]['porcentaje'],100)

    def test_SPAG13_rueda_sin_ctrl_y_arrastre_central_desplazan_vista(self):
        """REQ-EDT-11: Ctrl + rueda (zoom) y botón central navegan como en el dibujo principal sin mover lo impreso."""
        from escritorio.diagrama import ZOOM_PASO
        w,e,s=self.preparar();self.crear_hoja(e,[s]);p=self.pulsar_planos();p.zoom_combo.setCurrentIndex(p.zoom_combo.findData(2.));QApplication.processEvents();v=p.editor.vista;antes=copy.deepcopy(p.graficos)
        pos=QPointF(200,200);anclado=v.punto_hoja(pos);pantalla=pos+v.pos();evento=QWheelEvent(pos,QPointF(v.mapToGlobal(pos.toPoint())),QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.ControlModifier,Qt.ScrollPhase.NoScrollPhase,False)
        QApplication.sendEvent(v,evento);self.assertAlmostEqual(p.factor_zoom,2*ZOOM_PASO);QApplication.processEvents();despues=v.punto_hoja(pantalla-v.pos());self.assertAlmostEqual(anclado.x(),despues.x(),delta=.3);self.assertAlmostEqual(anclado.y(),despues.y(),delta=.3);a=p.editor.area;a.verticalScrollBar().setValue(100);valor=a.verticalScrollBar().value()
        QTest.mousePress(v,Qt.MouseButton.MiddleButton,pos=QPoint(200,200));QTest.mouseMove(v,QPoint(200,150));QTest.mouseRelease(v,Qt.MouseButton.MiddleButton,pos=QPoint(200,150));self.assertGreater(a.verticalScrollBar().value(),valor);self.assertEqual(p.graficos,antes)

    def test_SPAG14_exportacion_incluye_todas_las_colocaciones(self):
        """REQ-EDT-11: PDF/SVG contienen todas las selecciones de la hoja sin selección azul ni fondo sepia."""
        w,e,s=self.preparar();otro=e.ed.add_step('g','Segundo',at=(0,150));e.cambia();self.crear_hoja(e,[s]);p=self.pulsar_planos();p.insertar([otro]);d=p.editor.documento
        ruta=Path(self.tmp.name)/'hoja.svg';d.exportar_svg(ruta);svg=ruta.read_text(encoding='utf-8').lower();self.assertIn('segundo',svg);self.assertNotIn('#e5e0d8',svg);self.assertNotIn('#326dcb',svg)
        d.exportar_pdf(Path(self.tmp.name)/'hoja.pdf');self.assertGreater((Path(self.tmp.name)/'hoja.pdf').stat().st_size,1000)

    def test_SPAG15_insertar_sin_sitio_no_cambia_hoja(self):
        """REQ-EDT-11: una selección que no cabe se rechaza sin insertar parcialmente ni reducirla a escondidas."""
        w,e,s=self.preparar();otro=e.ed.add_step('g','2',at=(0,3000));e.cambia();self.crear_hoja(e,[s]);p=self.pulsar_planos();antes=copy.deepcopy(e.ed.presentation)
        with self.assertRaisesRegex(ValueError,'no cabe'):p.insertar([s,otro])
        self.assertEqual(e.ed.presentation,antes);self.assertEqual(len(p.graficos),1)

    def test_SPAG16_enviar_a_hoja_existente_y_escalas_independientes(self):
        """REQ-EDT-11: Enviar a plano permite elegir una hoja existente y conserva el tamaño de sus otras selecciones."""
        from escritorio.hojas import CrearHoja
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);w._mostrar_pagina(False);e.sel=[s]
        def elegir(d):
            d.destino.setCurrentIndex(d.destino.findData(ident));d.accept();return QDialog.DialogCode.Accepted
        with patch.object(CrearHoja,'exec',elegir):w.a_enviar_lamina.trigger()
        p=w.panel_planos;self.assertEqual(len(e.ed.sheet_links()),1);self.assertEqual(len(p.graficos),2)
        p.elegir_grafico(1);p.tamano.setValue(150);self.assertEqual([g['porcentaje'] for g in p.graficos],[100,150]);self.assertEqual(p.editor.documento.escala_rotulo,'Varias')
        w._mostrar_pagina(False);e.ed.rename(s,'Actualizada');e.cambia();w.mostrar_hoja(ident)
        self.assertEqual([g['modelo']['steps'][0]['label'] for g in p.editor.modelo['_graficos']],['Actualizada','Actualizada'])

    def punto_mm(self,v,x,y):
        d=v.documento;k=min((v.width()-24)/d.ancho,(v.height()-24)/d.alto)
        return QPoint(round((v.width()-d.ancho*k)/2+x*k),round((v.height()-d.alto*k)/2+y*k))

    def test_SPAG17_orden_herramientas_y_tamanos(self):
        """REQ-EDT-01, REQ-EDT-11: pestañas antes de herramientas propias, sin botones generales duplicados."""
        w,e,s=self.preparar()
        for ancho,alto in ((1366,768),(1000,600)):
            w.resize(ancho,alto);QApplication.processEvents()
            self.assertFalse(w.tb_proyecto.isVisible());self.assertFalse(w.tb_conexion.isVisible())
            self.assertGreaterEqual(w.herramientas_grafcet.y(),w.pestanas_vistas.geometry().bottom())
            self.assertTrue(w.tb_sim.isVisible());self.assertEqual([a for a in w.tb_edit.actions() if not a.isSeparator() and a not in (w.a_dependencias, w.a_errores)],
                                                              [w.a_deshacer, w.a_rehacer, w.a_cortar, w.a_copiar,
                                                               w.a_pegar, w.a_borrar])
            for pagina in ('planos',True):
                w._mostrar_pagina(pagina);QApplication.processEvents();self.assertFalse(w.herramientas_grafcet.isVisible())
            w._mostrar_pagina(False)
        self.assertEqual(w.a_nuevo.text().replace('&',''),'Nuevo proyecto')

    def test_SPAG18_importar_real_pdf_dxf_svg_y_reabrir_sin_original(self):
        """REQ-EDT-11, REQ-DAT-02: la acción visible importa formatos externos y los incorpora al archivo."""
        from test_plantillas import dxf_ejemplo,pdf_ejemplo
        from escritorio.plantillas import EditorPlantilla
        w,e,s=self.preparar();self.crear_hoja(e);p=self.pulsar_planos();root=Path(self.tmp.name)
        for extension in ('dxf','pdf','svg'):
            with self.subTest(extension=extension):
                ruta=root/('externa.'+extension)
                if extension=='dxf':dxf_ejemplo(ruta)
                elif extension=='pdf':pdf_ejemplo(ruta,paginas=2)
                else:ruta.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm"><rect x="5" y="5" width="200" height="287" fill="none" stroke="black"/></svg>',encoding='utf-8')
                with patch('escritorio.laminas.QFileDialog.getOpenFileName',return_value=(str(ruta),'')),patch('escritorio.laminas.QInputDialog.getInt',return_value=(2,True)),patch('escritorio.laminas.QMessageBox.information'),patch.object(EditorPlantilla,'exec') as emergente:
                    p.editor.a_importar.trigger();emergente.assert_not_called()
                self.assertIn(p.editor.a_importar, p.editor.b_opciones_plantilla.menu().actions())
                self.assertIsNotNone(p.editor.documento)
                self.assertAlmostEqual(p.editor.documento.ancho,210,delta=.2);self.assertAlmostEqual(p.editor.documento.alto,297,delta=.2)
                if extension in ('pdf','svg'):self.assertTrue(p.editor.plantilla['background']['data'])
                if extension=='pdf':self.assertTrue(any('original 2' in t.get('text','') for t in p.editor.plantilla['primitives']))
                p.aplicar();archivo=root/(extension+'.grafnet');self.assertTrue(w._guardar_archivo(archivo));ruta.unlink();self.assertTrue(w.abrir_ruta(archivo));p=w.panel_planos
                self.assertEqual(p.lista.count(),1);self.assertIsNotNone(p.editor.documento)
                salida=root/(extension+'-export.svg');p.editor.documento.exportar_svg(salida);self.assertTrue(salida.exists())

    def test_SPAG19_cancelacion_error_y_pdf_cancelado_no_cambian_hoja(self):
        """REQ-DAT-02, REQ-EDT-11: cancelar importación o fallar no modifica presentación ni historial."""
        from test_plantillas import pdf_ejemplo
        w,e,s=self.preparar();self.crear_hoja(e);p=self.pulsar_planos();antes=copy.deepcopy(p.editor.valores());presentacion=copy.deepcopy(e.ed.presentation)
        malo=Path(self.tmp.name)/'malo.dxf';malo.write_text('inválido',encoding='utf-8')
        pdf=Path(self.tmp.name)/'cancelado.pdf';pdf_ejemplo(pdf,paginas=2)
        for ruta in ('',str(malo),str(pdf)):
            with patch('escritorio.laminas.QFileDialog.getOpenFileName',return_value=(ruta,'')),patch('escritorio.laminas.QInputDialog.getInt',return_value=(1,False)),patch('escritorio.laminas.QMessageBox.warning'):
                p.editor.a_importar.trigger()
            self.assertEqual(p.editor.valores(),antes);self.assertEqual(e.ed.presentation,presentacion)

    def test_SPAG20_texto_en_hoja_propiedades_mover_eliminar_historial(self):
        """REQ-EDT-05, REQ-EDT-11: un clic coloca texto libre; propiedades, arrastre y borrado se deshacen."""
        w,e,s=self.preparar();ident=self.crear_hoja(e);p=self.pulsar_planos();p.editor.a_quitar_plantilla.trigger();p.aplicar();QApplication.processEvents()
        p.a_texto.trigger();v=p.editor.vista;QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=self.punto_mm(v,40,60))
        t=p.editor.editor_textos;self.assertIsNotNone(t.actual);self.assertIs(p.editor.propiedades.currentWidget(),t.panel_propiedades)
        self.assertAlmostEqual(t.actual.t['x'],40,delta=1);self.assertAlmostEqual(t.actual.t['y'],60,delta=1)
        t.contenido.setPlainText('Texto libre');t.altura.setValue(4);t.giro.setCurrentIndex(1);t.alineacion.setCurrentIndex(t.alineacion.findData('center'))
        from PySide6.QtGui import QColor
        with patch('escritorio.plantillas.QColorDialog.getColor',return_value=QColor('#c02080')):t.color.click()
        self.assertEqual(t.actual.t['color'],'#c02080');self.assertEqual(t.actual.t['rotation'],90);self.assertFalse(t.actual.t.get('field'))
        a=self.punto_mm(v,t.actual.sceneBoundingRect().center().x(),t.actual.sceneBoundingRect().center().y());b=a+QPoint(20,15);x=t.actual.t['x']
        QTest.mousePress(v,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(v,b);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,pos=b)
        self.assertNotEqual(t.actual.t['x'],x);movido=copy.deepcopy(t.actual.t);v.setFocus();QTest.keyClick(v,Qt.Key.Key_Delete)
        self.assertFalse(p.editor.plantilla['primitives']);QTest.keyClick(v,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier);QApplication.processEvents()
        self.assertEqual(p.editor.plantilla['primitives'][0],movido)
        w.a_rehacer.trigger();self.assertFalse(p.editor.plantilla['primitives']);w.a_deshacer.trigger();self.assertEqual(p.editor.plantilla['primitives'][0],movido)
        ruta=Path(self.tmp.name)/'texto.grafnet';self.assertTrue(w._guardar_archivo(ruta));self.assertTrue(w.abrir_ruta(ruta));self.assertEqual(w.panel_planos.editor.plantilla['primitives'][0],movido)

    def test_SPAG21_edicion_interna_zona_y_textos_libres(self):
        """REQ-EDT-11: textos importados y zona se editan en la hoja como textos libres, sin enlaces a campos."""
        w,e,s=self.preparar();ident=self.crear_hoja(e);p=self.pulsar_planos();d=p.editor
        plantilla={'version':1,'size':[210,297],'source':'DXF','primitives':[{'kind':'text','text':'HOJA 1 DE 1','x':30,'y':60,'height':3,'rotation':0,'valign':'top','suggest':'hoja'}]}
        d.establecer_plantilla(plantilla);d.aplicar();QApplication.processEvents();t=d.editor_textos
        d.a_editar_plantilla.trigger();self.assertTrue(d.editando_plantilla);self.assertFalse(t.isWindow() and t.isVisible());self.assertEqual(d.a_editar_plantilla.text(),'Terminar edición')
        a=self.punto_mm(d.vista,31,61);QTest.mouseClick(d.vista,Qt.MouseButton.LeftButton,pos=a)
        self.assertIsNotNone(t.actual);self.assertFalse(t.actual.t.get('field'));self.assertFalse(t.sugerencia.isVisible());self.assertFalse(t.enlace.isVisible());t.contenido.setPlainText('Hoja escrita a mano');self.assertFalse(t.actual.t.get('field'))
        t.b_zona.click();a=self.punto_mm(d.vista,25,25);b=self.punto_mm(d.vista,150,180)
        QTest.mousePress(d.vista,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(d.vista,b);QTest.mouseRelease(d.vista,Qt.MouseButton.LeftButton,pos=b)
        self.assertIsNotNone(d.plantilla.get('zone'));self.assertAlmostEqual(d.documento.contenido.left(),25,delta=1)
        d.a_editar_plantilla.trigger();self.assertFalse(d.editando_plantilla);self.assertFalse(t.b_zona.isVisible());p.insertar([s]);self.assertTrue(p.editor.documento.contenido.contains(p.editor.documento.capas[0].destino(0)))

    def test_SPAG22_plantilla_libre_campos_contextuales_y_exportacion(self):
        """REQ-EDT-11: sin campos extensos; textos usan el mismo dibujo en PDF/SVG/impresión."""
        w,e,s=self.preparar();self.crear_hoja(e,[s]);p=self.pulsar_planos();d=p.editor
        self.assertFalse(d.campos['autor'].isVisible());d.a_quitar_plantilla.trigger();self.assertFalse(d.campos['autor'].isVisible());self.assertFalse(d.plantilla['primitives'])
        p.a_texto.trigger();QTest.mouseClick(d.vista,Qt.MouseButton.LeftButton,pos=self.punto_mm(d.vista,50,80));d.editor_textos.contenido.setPlainText('Libre exportado');d.editor_textos.altura.setValue(4)
        root=Path(self.tmp.name);d.documento.exportar_svg(root/'texto.svg');d.documento.exportar_pdf(root/'texto.pdf')
        svg=(root/'texto.svg').read_text(encoding='utf-8');self.assertIn('Libre exportado',svg);self.assertNotIn('#326dcb',svg.lower());self.assertGreater((root/'texto.pdf').stat().st_size,1000)
        with patch.object(type(d.documento),'imprimir',return_value=True) as imprimir:d.imprimir();imprimir.assert_called_once_with(d)
        d.a_estandar.trigger();self.assertFalse(d.campos['autor'].isVisible());self.assertEqual(d.plantilla['source'],'GrafConnect')

    def test_SPAG23_migracion_nombres_repetidos_sin_perdida(self):
        """REQ-DAT-02, REQ-EDT-11: la lista única reúne hojas con nombres iguales de planes distintos sin descartarlas."""
        w,e,s=self.preparar();a=e.ed.add_sheet_plan('Primero');b=e.ed.add_sheet_plan('Segundo');cfg=ajustes_lamina({'plantilla':predeterminada()})
        ids=[e.ed.add_plan_page(plan,cfg,'Igual') for plan in (a,b)]
        e.ed.set_page_graphics(ids[1],[{'refs':[s],'porcentaje':75,'offset_mm':[15,20]}]);antes=copy.deepcopy(e.ed.presentation);p=self.pulsar_planos()
        self.assertEqual(p.lista.count(),2);self.assertEqual([p.lista.item(i).text() for i in range(2)],['Igual','Igual']);self.assertEqual(e.ed.presentation,antes)
        w.mostrar_hoja(ids[1]);self.assertEqual(p.graficos[0]['porcentaje'],75);self.assertEqual(p.graficos[0]['offset_mm'],[15,20]);self.assertEqual(p.editor.documento.campos(0)['hoja'],'2 de 2')

    def test_SPAG24_colocacion_grafcet_deshacer_sin_reaplicar_valor_viejo(self):
        """REQ-EDT-05, REQ-EDT-11: Ctrl+Z/Y en Planos restaura tamaño y posición, sin reescribir el estado deshecho."""
        w,e,s=self.preparar();self.crear_hoja(e,[s]);p=self.pulsar_planos();p.tamano.setValue(150);self.assertEqual(p.graficos[0]['porcentaje'],150)
        w.a_deshacer.trigger();self.assertEqual(p.graficos[0]['porcentaje'],100);w.a_rehacer.trigger();self.assertEqual(p.graficos[0]['porcentaje'],150)
        antes=p.graficos[0]['offset_mm'][:];p.editor.vista.capa=0;p.colocar([10,15]);w.a_deshacer.trigger();self.assertEqual(p.graficos[0]['offset_mm'],antes)

    def test_SPAG25_propiedades_texto_sin_recortes_y_cajetin_sin_franja(self):
        """REQ-EDT-01, REQ-EDT-11: propiedades utilizables a 1000×600 y franja extra ausente solo de la plantilla propia."""
        from grafcet.plantillas_tecnicas import plantilla_tecnica
        w,e,s=self.preparar();self.crear_hoja(e);p=self.pulsar_planos()
        propia=plantilla_tecnica(210,297)
        self.assertFalse(any(t.get('prefix') in ('Proyecto: ','Hoja ') for t in propia['primitives']))
        self.assertFalse(any(t.get('field') in ('hoja','proyecto') for t in propia['primitives']))
        p.editor.establecer_plantilla({'version':1,'source':'DXF','size':[210,297],'primitives':[{'kind':'text','text':'Proyecto: original','x':30,'y':60,'height':3,'rotation':0}]})
        self.assertEqual(p.editor.plantilla['primitives'][0]['text'],'Proyecto: original')
        p.editor.editor_textos.elegir(0)
        for ancho,alto in ((1366,768),(1000,600)):
            w.resize(ancho,alto);QApplication.processEvents();scroll=p.editor.editor_textos.panel_propiedades
            self.assertEqual((w.width(),w.height()),(ancho,alto));self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
            self.assertGreaterEqual(p.editor.area.viewport().width(),260);self.assertGreaterEqual(p.editor.area.viewport().height(),220)

    def test_SPAG26_traer_solo_selecciona_y_restaura_paneles(self):
        """REQ-EDT-05, REQ-EDT-11: Traer oculta herramientas y paneles, solo selecciona y restaura al cancelar."""
        w,e,s=self.preparar();ident=self.crear_hoja(e);p=self.pulsar_planos();antes=copy.deepcopy((e.ed.model,e.ed.presentation));paneles={n:q.abierto for n,q in w._plegables.items()}
        p.a_nueva.trigger();QApplication.processEvents();self.assertTrue(w._seleccionando_hoja);self.assertFalse(w.herramientas_grafcet.isVisible())
        self.assertTrue(all(not q.isVisible() for q in w._plegables.values()));self.assertTrue(w.aviso_traer.isVisible());self.assertGreater(w.aviso_traer.y(),w.paginas_es.y())
        self.assertFalse(w.a_ejecutar.isEnabled());self.assertFalse(w.a_borrar.isEnabled());self.assertFalse(w.diagrama.acceptDrops())
        v=w.diagrama;v.ajustar();QApplication.processEvents();pos=posiciones(e.M)[s];a=v.mapFromScene(QPointF(*pos));b=a+QPoint(45,25)
        QTest.mousePress(v.viewport(),Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(v.viewport(),b);QTest.mouseRelease(v.viewport(),Qt.MouseButton.LeftButton,pos=b)
        self.assertEqual(e.sel,[s]);self.assertIn('Planos',w.estado.text());QTest.keyClick(v,Qt.Key.Key_Delete);QTest.keyClick(v,Qt.Key.Key_X,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual((e.ed.model,e.ed.presentation),antes);self.assertFalse(w.a_cortar.isEnabled())
        w.cancelar_traer();self.assertFalse(w._seleccionando_hoja);self.assertIs(v.controlador,e);self.assertEqual({n:q.abierto for n,q in w._plegables.items()},paneles)
        w._mostrar_pagina(False);self.assertTrue(w.herramientas_grafcet.isVisible());self.assertTrue(w.a_ejecutar.isEnabled())

    def test_SPAG27_texto_heredado_libre_y_edicion_marcada(self):
        """REQ-EDT-11: un texto antes automático se escribe libremente, sin selector de campos ni botones de diálogo."""
        w,e,s=self.preparar();self.crear_hoja(e);p=self.pulsar_planos();d=p.editor;d.campos['titulo'].setText('Título heredado')
        d.establecer_plantilla({'version':1,'size':[210,297],'source':'DXF','primitives':[{'kind':'text','text':'Título','field':'titulo','x':40,'y':60,'height':3,'rotation':0}]})
        t=d.editor_textos;t.elegir(0);self.assertEqual(t.contenido.toPlainText(),'Título heredado');self.assertTrue(t.contenido.isVisible());self.assertTrue(t.contenido.isEnabled());self.assertFalse(t.enlace.isVisible());self.assertFalse(t.botones_dialogo.isVisible());self.assertFalse(t.sugerencia.isVisible())
        t.contenido.setPlainText('Escrito a mano');self.assertEqual(t.actual.t['text'],'Escrito a mano');self.assertFalse(t.actual.t.get('field'))
        d.a_editar_plantilla.trigger();self.assertTrue(d.a_editar_plantilla.isChecked());self.assertEqual(d.a_editar_plantilla.text(),'Terminar edición')
        t.elegir(0);t.contenido.setPlainText('Cambio durante edición');self.assertTrue(d.a_editar_plantilla.isChecked())
        d.a_editar_plantilla.trigger();self.assertFalse(d.a_editar_plantilla.isChecked())

    def test_SPAG28_rotulos_antiguos_y_margen_fijo(self):
        """REQ-EDT-11, REQ-DAT-02: elimina rótulos auxiliares propios heredados y bloquea la edición de márgenes."""
        from grafcet.plantillas_tecnicas import plantilla_tecnica
        w,e,s=self.preparar();p0=plantilla_tecnica(420,297);x,y,_,_=p0['title_box']
        for field in ('proyecto','hoja'):p0['primitives'].append({'kind':'text','text':'','field':field,'prefix':'Proyecto: ' if field=='proyecto' else 'Hoja ','omit_empty':True,'x':x+25,'y':y+33,'height':1.2,'rotation':0})
        cfg=ajustes_lamina({'formato':'A3','orientacion':'horizontal','plantilla':p0});ident=e.ed.add_plan_page(None,cfg);p=self.pulsar_planos()
        self.assertFalse(any(t.get('field') in ('hoja','proyecto') for t in p.editor.plantilla['primitives']));self.assertFalse(p.editor.margen.isEnabled());self.assertEqual(p.editor.margen.value(),10)
        p.aplicar();p.mostrar(ident);self.assertFalse(any(t.get('field') in ('hoja','proyecto') for t in p.editor.plantilla['primitives']))
        p.editor.a_quitar_plantilla.trigger();self.assertEqual(p.editor.documento.ancho,420);self.assertEqual(p.editor.documento.alto,297);self.assertFalse(p.editor.plantilla['primitives'])

    def test_SPAG29_mtext_dxf_respetan_banda_y_altura_visible(self):
        """REQ-EDT-11: MTEXT superior/centrado usa las letras visibles, no el interlineado de Qt; no corta el marco."""
        import ezdxf
        from PySide6.QtGui import QPainterPath
        from escritorio.importar_plantillas import importar_dxf
        from escritorio.plantillas import layout_texto
        ruta=Path(self.tmp.name)/'banda.dxf';d=ezdxf.new('R2000');d.units=4;m=d.modelspace()
        for y in (287,297):m.add_line((0,y),(210,y))
        m.add_line((0,0),(210,0));m.add_line((0,0),(0,297));m.add_line((210,0),(210,297))
        for x,texto in ((50,'8'),(100,'7')):m.add_mtext(texto,dxfattribs={'insert':(x,294),'char_height':4,'attachment_point':2})
        d.saveas(ruta);p=importar_dxf(ruta,campos=False)
        for t in (t for t in p['primitives'] if t['kind']=='text'):
            layout,font,k,rect,x,y,lineas,stretch=layout_texto(t,t['text']);trazo=QPainterPath();trazo.addText(QPointF(0,lineas[0].ascent()),font,t['text']);r=trazo.boundingRect()
            arriba=t['y']+y+r.top()*k;abajo=t['y']+y+r.bottom()*k
            self.assertAlmostEqual(arriba,3,delta=.12);self.assertLess(abajo,10);self.assertGreater(arriba,0);self.assertAlmostEqual(t['height'],4)

    def test_SPAG30_enviar_al_final_del_menu_con_separador(self):
        """REQ-EDT-01, REQ-EDT-11: Enviar a plano es la última sección del menú contextual real."""
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QTimer
        w,e,s=self.preparar();v=w.diagrama;v.ajustar();QApplication.processEvents();pos=posiciones(e.M)[s];p=v.mapFromScene(QPointF(*pos));capturado=[]
        original=v.menu_contextual
        def construir(opciones):
            menu=original(opciones);capturado.extend(menu.actions());QTimer.singleShot(0,menu.close);return menu
        with patch.object(v,'menu_contextual',side_effect=construir):
            self.app.sendEvent(v.viewport(),QContextMenuEvent(QContextMenuEvent.Reason.Mouse,p,v.viewport().mapToGlobal(p)))
        self.assertEqual(capturado[-1].text(),'Enviar a plano…');self.assertTrue(capturado[-2].isSeparator());self.assertEqual(sum(a.text()=='Enviar a plano…' for a in capturado),1)

    def test_SPAG31_marco_completo_sin_invadir_cajetin_con_raton(self):
        """REQ-EDT-05, REQ-EDT-11: se puede colocar a la izquierda del cajetín, pero no encima, y deshacer el arrastre."""
        from grafcet.plantillas_tecnicas import plantilla_tecnica
        from PySide6.QtCore import QRectF
        w,e,s=self.preparar();self.crear_hoja(e,[s]);p=self.pulsar_planos();p.editor.establecer_plantilla(plantilla_tecnica(420,297));p.aplicar();p.editor.vista.capa=0;p.colocar([20,250]);QApplication.processEvents()
        d=p.editor.documento;rect=d.capas[0].destino(0);caja=QRectF(*d.plantilla.p['title_box']);self.assertGreater(rect.bottom(),caja.top());self.assertLess(rect.right(),caja.left());self.assertFalse(rect.intersects(caja));antes=p.graficos[0]['offset_mm'][:]
        v=p.editor.vista;a=self.punto_mm(v,rect.center().x(),rect.center().y());b=self.punto_mm(v,caja.center().x(),caja.center().y())
        QTest.mousePress(v,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(v,b);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,pos=b)
        self.assertFalse(p.editor.documento.capas[0].destino(0).intersects(caja));w.a_deshacer.trigger();self.assertEqual(p.graficos[0]['offset_mm'],antes)
        p.colocar([20,20]);p.editor.editor_textos.poner_zona([30,30,90,100]);self.assertEqual(p.editor.documento.contenido.getRect(),(30,30,90,100))

    def test_SPAG32_miniaturas_todas_zoom_y_anadir_al_final(self):
        """REQ-EDT-01, REQ-EDT-11: todas las hojas tienen miniatura, independiente del zoom; botón y nuevas hojas al final."""
        from PySide6.QtCore import QSize
        from escritorio.hojas import CrearHoja
        w,e,s=self.preparar();ids=[self.crear_hoja(e,[s]) for _ in range(3)];p=self.pulsar_planos();QApplication.processEvents()
        def miniaturas():return [p.lista.item(i).icon().pixmap(QSize(116,82)).toImage() for i in range(p.lista.count())]
        antes=miniaturas();self.assertTrue(all(img.width()==116 and img.height()==82 for img in antes));p.zoom(.33);QApplication.processEvents();self.assertEqual(miniaturas(),antes)
        self.assertGreaterEqual(p.b_hoja.y(),p.lista.geometry().bottom())
        with patch.object(CrearHoja,'exec',lambda d:(d.accept() or QDialog.DialogCode.Accepted)):p.a_hoja.trigger()
        QApplication.processEvents()
        self.assertEqual([p.lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(3)],ids);self.assertEqual(p.hoja_id,e.ed.sheet_links()[-1]['id']);self.assertEqual(p.lista.currentRow(),3)
        self.assertTrue(all(img.width()==116 and img.height()==82 for img in miniaturas()));self.assertGreaterEqual(p.b_hoja.y(),p.lista.geometry().bottom())

    def test_SPAG33_dxf_antiguo_recupera_interior_completo_sin_tocar_zona_manual(self):
        """REQ-DAT-02, REQ-EDT-11: DXF ya incorporado recupera marco/cajetín desde sus líneas; una zona manual se conserva."""
        from test_plantillas import dxf_ejemplo
        from escritorio.importar_plantillas import importar_dxf
        w,e,s=self.preparar();ruta=Path(self.tmp.name)/'antiguo.dxf';dxf_ejemplo(ruta);plantilla=importar_dxf(ruta,campos=False)
        plantilla.pop('inner_frame',None);plantilla.pop('title_box',None);plantilla['detected_zone']=[12,12,186,233];ruta.unlink()
        ident=e.ed.add_plan_page(None,ajustes_lamina({'plantilla':plantilla}));p=self.pulsar_planos()
        self.assertEqual(p.editor.documento.marco.getRect(),(10,10,190,277));self.assertGreater(p.editor.documento.contenido.bottom(),247);self.assertEqual(p.editor.documento.exclusiones[0].getRect(),(10,247,190,40))
        p.aplicar();p.mostrar(ident);self.assertEqual(p.editor.plantilla['title_box'],[10,247,190,40])
        p.editor.editor_textos.poner_zona([20,20,100,120]);p.aplicar();p.mostrar(ident);self.assertEqual(p.editor.documento.contenido.getRect(),(20,20,100,120))

    def test_SPAG34_suprimir_colocacion_deshacer_y_texto_no_borran_original(self):
        """REQ-EDT-05, REQ-EDT-11: Supr elimina solo el GRAFCET seleccionado de la hoja en una transacción reversible."""
        w,e,s=self.preparar();self.crear_hoja(e,[s]);p=self.pulsar_planos();p.insertar([s]);QApplication.processEvents();original=copy.deepcopy(e.ed.model);antes=copy.deepcopy(p.graficos);n=len(e.ed.undo_stack)
        d=p.editor.documento;v=p.editor.vista;r=d.capas[1].destino(0);QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=self.punto_mm(v,r.center().x(),r.center().y()))
        QApplication.processEvents();self.assertEqual(v.capa,1);self.assertIs(p.editor.propiedades.currentWidget(),p.propiedades_grafico);self.assertTrue(p.tamano.isVisible());self.assertFalse(hasattr(p,'grafico_combo'))
        QTest.keyClick(v,Qt.Key.Key_Delete);self.assertEqual(len(p.graficos),1);self.assertEqual(e.ed.model,original);self.assertEqual(len(e.ed.undo_stack),n+1)
        w.a_deshacer.trigger();self.assertEqual(p.graficos,antes);w.a_rehacer.trigger();self.assertEqual(len(p.graficos),1);self.assertEqual(e.ed.model,original)
        p.a_texto.trigger();QTest.mouseClick(p.editor.vista,Qt.MouseButton.LeftButton,pos=self.punto_mm(p.editor.vista,80,100));t=p.editor.editor_textos;t.contenido.setPlainText('AB');t.contenido.setFocus();t.contenido.moveCursor(t.contenido.textCursor().MoveOperation.Start)
        QTest.keyClick(t.contenido,Qt.Key.Key_Delete);self.assertEqual(t.contenido.toPlainText(),'B');self.assertEqual(len(p.graficos),1);self.assertEqual(e.ed.model,original)

    def test_SPAG35_rotulos_completos_boton_separado_y_flecha_incorporada(self):
        """REQ-EDT-01, REQ-EDT-11: títulos de hojas completos, botones con contraste y flecha sin borde nativo superpuesto."""
        from PySide6.QtCore import QFile,QSize
        from PySide6.QtSvg import QSvgRenderer
        w,e,s=self.preparar();self.crear_hoja(e);self.crear_hoja(e);p=self.pulsar_planos()
        for size in ((1366,768),(1000,600)):
            w.resize(*size);QApplication.processEvents();r=p.lista.visualItemRect(p.lista.item(1));self.assertLess(r.bottom()+p.lista.spacing(),p.lista.viewport().height());self.assertGreaterEqual(p.b_hoja.y(),p.lista.geometry().bottom())
        self.assertTrue(QFile.exists(':/grafconnect/desplegar.svg'));self.assertTrue(QSvgRenderer(':/grafconnect/desplegar.svg').isValid());self.assertIn('QComboBox::drop-down',w.styleSheet());self.assertIn('width:24px',w.styleSheet());self.assertIn(':/grafconnect/desplegar.svg',w.styleSheet())
        p.a_nueva.trigger();self.assertEqual(w.b_confirmar_traer.objectName(),'confirmarSeleccionHoja');self.assertIn('background:#27665c',w.aviso_traer.styleSheet());self.assertIn('background:white',w.aviso_traer.styleSheet())

    def test_SPAG36_exportar_propone_plano_y_conserva_hoja_actual(self):
        """REQ-EDT-11: PDF/SVG se proponen como plano, sin cambiar formatos ni la hoja que se exporta."""
        w,e,s=self.preparar();ident=self.crear_hoja(e,[s]);p=self.pulsar_planos()
        with patch('escritorio.laminas.QFileDialog.getSaveFileName',return_value=('','')) as dialogo:p.a_exportar.trigger()
        args=dialogo.call_args.args;self.assertEqual(args[1],'Exportar plano');self.assertEqual(Path(args[2]).name,'plano.pdf');self.assertIn('*.svg',args[3]);self.assertEqual(p.hoja_id,ident)
        ruta=Path(self.tmp.name)/'plano.pdf'
        with patch('escritorio.laminas.QFileDialog.getSaveFileName',return_value=(str(ruta),'Dibujo SVG (*.svg)')):p.a_exportar.trigger()
        self.assertTrue(ruta.with_suffix('.svg').exists());self.assertFalse(Path(str(ruta)+'.svg').exists())

    def test_SPAG37_cambiar_ejemplos_y_reabrir_mismos_ids_no_bloquea_planos(self):
        """REQ-DAT-02, REQ-EDT-11: el editor de hojas de la fuente anterior no escribe ni dibuja sobre el nuevo proyecto."""
        from PySide6.QtWidgets import QMessageBox
        w,e,s=self.preparar();self.crear_hoja(e,[s]);p=self.pulsar_planos();errores=[]
        with patch('sys.excepthook',side_effect=lambda *args:errores.append(args)),patch('escritorio.ventana.QMessageBox.question',return_value=QMessageBox.StandardButton.Discard):
            for clave in ('encapsulacion','macroetapa','alternativas'):
                from grafcet.examples import EJEMPLOS
                from escritorio.edicion import Edicion
                titulo,_,crear=EJEMPLOS[clave];m,layout=crear()
                w._mostrar_pagina(False);w._establecer_edicion(Edicion.desde(m.doc,layout,titulo));w.fuente={'tipo':'editor'};w._cargar();QApplication.processEvents();e=w.edicion;antes=copy.deepcopy(e.ed.presentation)
                p=self.pulsar_planos();self.assertEqual(w.paginas_es.currentIndex(),2);self.assertIs(p.origen,e);self.assertIsNone(p.editor);self.assertEqual(p.lista.count(),0);self.assertEqual(e.ed.presentation,antes)
                self.crear_hoja(e);p.mostrar();self.assertIsNotNone(p.editor)
            ruta=Path(self.tmp.name)/'mismos-ids.grafnet';self.assertTrue(w._guardar_archivo(ruta));guardadas=copy.deepcopy(e.ed.sheet_links());p.editor.campos['titulo'].setText('Cambio que se descarta')
            self.assertTrue(w.abrir_ruta(ruta));QApplication.processEvents();p=self.pulsar_planos();self.assertEqual(w.edicion.ed.sheet_links(),guardadas);self.assertIs(p.origen,w.edicion);self.assertIsNotNone(p.editor)
        self.assertEqual(errores,[])

    def test_SPAG38_jerarquias_solo_se_llevan_si_se_seleccionan(self):
        """REQ-EDT-11, REQ-JER-05: Planos usa la selección exacta; Copiar conserva su ampliación jerárquica habitual."""
        from escritorio.hojas import dibujo_vinculado
        w,e,s=self.preparar();m=e.ed.add_macro('g','M1',at=(500,0));n=e.ed.add_step(m.partial,'3',at=(700,200));e.cambia()
        sola=dibujo_vinculado(e,[m.macro]);self.assertEqual([x['id'] for x in sola['macros']],[m.macro]);self.assertFalse(sola['steps']);self.assertFalse(sola['partials'])
        todos=dibujo_vinculado(e,[m.macro,m.partial,m.entry,m.exit,n]);self.assertEqual({x['id'] for x in todos['steps']},{m.entry,m.exit,n});self.assertEqual([x['id'] for x in todos['partials']],[m.partial]);self.assertIn(n,{x['id'] for x in e.ed.copy([m.macro]).entities['steps']})
        self.crear_hoja(e);p=self.pulsar_planos();w.diagrama.dependencias=True;p.insertar([m.macro]);self.assertIsNotNone(p.editor.documento);self.assertFalse(p.editor.modelo['steps']);self.assertFalse(p.editor.modelo['partials'])
        w,e,j=self.con_recinto();sola=dibujo_vinculado(e,[j['e0']]);self.assertEqual([x['id'] for x in sola['steps']],[j['e0']]);self.assertFalse(sola['partials'])
        marco=dibujo_vinculado(e,[j['r']]);self.assertEqual([x['id'] for x in marco['partials']],[j['r']]);self.assertFalse(marco['steps'])
        todos=dibujo_vinculado(e,[j['e0'],j['r'],j['a'],j['b']]);self.assertEqual({x['id'] for x in todos['steps']},{j['e0'],j['a'],j['b']});self.assertEqual([x['id'] for x in todos['partials']],[j['r']])

    def test_SPAG39_menu_hojas_reordena_deshace_y_guarda_orden(self):
        """REQ-EDT-05, REQ-EDT-11, REQ-DAT-02: menú contextual real para subir/bajar hojas; orden y datos reversibles."""
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QContextMenuEvent
        w,e,s=self.preparar();ids=[self.crear_hoja(e,[s]) for _ in range(3)];p=self.pulsar_planos();antes=copy.deepcopy(e.ed.sheet_links());modelo=copy.deepcopy(e.ed.model);capturadas=[];original=p.crear_menu_hoja
        def abrir():
            menu=original();capturadas.extend(menu.actions());QTimer.singleShot(0,menu.close);return menu
        punto=p.lista.visualItemRect(p.lista.item(0)).center()
        with patch.object(p,'crear_menu_hoja',side_effect=abrir):self.app.sendEvent(p.lista.viewport(),QContextMenuEvent(QContextMenuEvent.Reason.Mouse,punto,p.lista.viewport().mapToGlobal(punto)))
        self.assertEqual([a.text() for a in capturadas if not a.isSeparator()],['Eliminar hoja','Subir una hoja','Bajar una hoja']);self.assertFalse(capturadas[2].isEnabled());self.assertTrue(capturadas[3].isEnabled());n=len(e.ed.undo_stack);capturadas[3].trigger()
        self.assertEqual([h['id'] for h in e.ed.sheet_links()],[ids[1],ids[0],ids[2]]);self.assertEqual(len(e.ed.undo_stack),n+1);self.assertEqual(p.hoja_id,ids[0]);self.assertEqual(p.editor.documento.campos(0)['hoja'],'2 de 3')
        w.a_deshacer.trigger();self.assertEqual(e.ed.sheet_links(),antes);w.a_rehacer.trigger();self.assertEqual(e.ed.model,modelo)
        ruta=Path(self.tmp.name)/'orden.grafnet';self.assertTrue(w._guardar_archivo(ruta));self.assertTrue(w.abrir_ruta(ruta));self.assertEqual([h['id'] for h in w.edicion.ed.sheet_links()],[ids[1],ids[0],ids[2]])
        p=w.panel_planos;p.lista.setCurrentRow(2);menu=p.crear_menu_hoja();self.assertFalse(menu.actions()[3].isEnabled());historial=len(w.edicion.ed.undo_stack);p.mover_hoja(1);self.assertEqual(len(w.edicion.ed.undo_stack),historial)

    def test_SPAG40_suprimir_hojas_menu_teclado_y_ultima_con_deshacer(self):
        """REQ-EDT-05, REQ-EDT-11: Supr y menú eliminan la hoja completa, sin tocar el modelo, y se deshacen."""
        w,e,s=self.preparar();ids=[self.crear_hoja(e,[s]) for _ in range(3)];p=self.pulsar_planos();antes=copy.deepcopy(e.ed.sheet_links());modelo=copy.deepcopy(e.ed.model);p.lista.setCurrentRow(1);QApplication.processEvents();n=len(e.ed.undo_stack);p.lista.setFocus();QTest.keyClick(p.lista,Qt.Key.Key_Delete)
        self.assertEqual([h['id'] for h in e.ed.sheet_links()],[ids[0],ids[2]]);self.assertEqual(len(e.ed.undo_stack),n+1);self.assertEqual(e.ed.model,modelo);self.assertEqual(p.hoja_id,ids[2])
        w.a_deshacer.trigger();self.assertEqual(e.ed.sheet_links(),antes);w.a_rehacer.trigger();self.assertEqual([h['id'] for h in e.ed.sheet_links()],[ids[0],ids[2]])
        p.crear_menu_hoja().actions()[0].trigger();self.assertEqual([h['id'] for h in e.ed.sheet_links()],[ids[0]]);p.lista.setFocus();QTest.keyClick(p.lista,Qt.Key.Key_Delete)
        self.assertEqual(e.ed.sheet_links(),[]);self.assertIsNone(p.editor);self.assertTrue(p.a_hoja.isEnabled());w.a_deshacer.trigger();self.assertEqual(e.ed.sheet_links(),[antes[0]])
        p.a_nueva.trigger();w._mostrar_pagina('planos');p.lista.setFocus();QTest.keyClick(p.lista,Qt.Key.Key_Delete);self.assertIsNone(w.destino_traer);self.assertEqual(e.ed.model,modelo)

    def test_SPAG41_tarjetas_no_recortan_rotulos_con_varias_hojas_y_fuente_grande(self):
        """REQ-EDT-01, REQ-EDT-11: tarjeta completa a distintos tamaños/fuentes; lateral desplazable y Añadir al final."""
        w,e,s=self.preparar();ids=[self.crear_hoja(e) for _ in range(5)];p=self.pulsar_planos()
        for fuente in (12,20):
            p.lista.setStyleSheet(f'QListWidget {{font-size:{fuente}px;}}')
            for ancho,alto in ((1366,768),(1000,600)):
                w.resize(ancho,alto);QApplication.processEvents();QApplication.processEvents();p.ajustar_lista();QApplication.processEvents()
                ultimo=p.lista.visualItemRect(p.lista.item(4));self.assertLess(ultimo.bottom(),p.lista.viewport().height());self.assertGreaterEqual(ultimo.height(),82+p.lista.fontMetrics().height()+20);self.assertGreaterEqual(p.b_hoja.y(),p.lista.geometry().bottom())
                p.scroll_hojas.ensureWidgetVisible(p.b_hoja);QApplication.processEvents();punto=p.b_hoja.mapTo(p.scroll_hojas.viewport(),QPoint(0,0));self.assertGreaterEqual(punto.y(),0);self.assertLessEqual(punto.y()+p.b_hoja.height(),p.scroll_hojas.viewport().height())
        self.assertEqual([h['id'] for h in e.ed.sheet_links()],ids)


    def test_SPAG42_traer_cadena_ctrl_quita_y_shift_suma_sin_hijas(self):
        """REQ-EDT-11, REQ-JER-05: clic elige cadena propia, Ctrl ajusta elementos y Mayús suma la hija solo expresamente."""
        from grafcet.builder import M
        from escritorio.edicion import Edicion
        m=M().var('a').step('1',True).step('2').trans('t',['1'],['2'],'a')
        e=Edicion.desde(m.doc,{'1':(100,80),'t':(100,180),'2':(100,280)},'Cadenas')
        hija=e.ed.add_partial('Hija',owner='g'); sid=e.ed.add_step(hija,'3',True,at=(700,80)); fin=e.ed.add_step(hija,'4',at=(700,280))
        tid,_=e.ed.add_transition(hija,'a',[sid],[fin],at=(700,180)); e.cambia()
        w=self.w;w._establecer_edicion(e);w._poner_modo();w.refrescar_edicion();w.show()
        ident=self.crear_hoja(e);self.pulsar_planos().a_nueva.trigger();QApplication.processEvents()
        v=w.diagrama;v.ajustar();QApplication.processEvents();antes=copy.deepcopy((e.ed.model,e.ed.presentation))
        def clic(i,mod=Qt.KeyboardModifier.NoModifier):
            p=v.mapFromScene(QPointF(*posiciones(e.M)[i]));QTest.mouseClick(v.viewport(),Qt.MouseButton.LeftButton,mod,pos=p);QApplication.processEvents()
        clic('1');self.assertEqual(set(e.sel),{'1','t','2'});self.assertNotIn(sid,e.sel)
        clic('2',Qt.KeyboardModifier.ControlModifier);self.assertEqual(set(e.sel),{'1','t'})
        clic(sid,Qt.KeyboardModifier.ShiftModifier);self.assertEqual(set(e.sel),{'1','t',sid,tid,fin})
        QTest.keyClick(v,Qt.Key.Key_Right);self.assertEqual((e.ed.model,e.ed.presentation),antes)
        w.cancelar_traer()

if __name__=='__main__':unittest.main()
