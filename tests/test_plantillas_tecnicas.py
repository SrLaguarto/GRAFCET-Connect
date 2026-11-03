"""Plantillas técnicas propias, biblioteca en Documentos y hojas vinculadas."""
import copy
import ctypes
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from grafcet.editor import Editor,new_grafcet_document
from grafcet.laminas import ajustes_lamina
from grafcet.plantillas_tecnicas import plantilla_tecnica,PREDETERMINADAS
from test_editor_cadenas import QT,BaseQt,cadena_lineal
if QT:
    from PySide6.QtCore import Qt,QPoint,QPointF,QRectF,QEvent,QTimer,QStandardPaths
    from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
    from PySide6.QtTest import QTest
    from escritorio import carpetas
    from escritorio.edicion import Edicion
    from escritorio.hojas import CrearHoja,dibujo_vinculado
    from escritorio.laminas import DocumentoLaminas,DialogoLaminas
try:import pypdfium2 as pdf
except ImportError:pdf=None


def segmentos_pdf(ruta):
    d=pdf.PdfDocument(ruta);pagina=d[0];lineas=[];mm=25.4/72
    try:
        for obj in pagina.get_objects(filter=[pdf.raw.FPDF_PAGEOBJ_PATH]):
            anterior=inicio=None;mat=obj.get_matrix()
            for j in range(pdf.raw.FPDFPath_CountSegments(obj)):
                seg=pdf.raw.FPDFPath_GetPathSegment(obj,j);x,y=ctypes.c_float(),ctypes.c_float()
                if not pdf.raw.FPDFPathSegment_GetPoint(seg,ctypes.byref(x),ctypes.byref(y)):continue
                xx,yy=mat.on_point(x.value,y.value);p=(xx*mm,(pagina.get_height()-yy)*mm)
                tipo=pdf.raw.FPDFPathSegment_GetType(seg)
                if tipo==pdf.raw.FPDF_SEGMENT_MOVETO:inicio=p
                elif tipo==pdf.raw.FPDF_SEGMENT_LINETO and anterior:lineas.append(anterior+p)
                anterior=p
                if pdf.raw.FPDFPathSegment_GetClose(seg) and inicio:lineas.append(p+inicio)
        tp=pagina.get_textpage()
        try:texto=tp.get_text_range()
        finally:tp.close()
        return lineas,texto
    finally:d.close()


class TecnicasNucleo(unittest.TestCase):
    def test_STEC01_cajetin_180_por_36_y_divisiones_en_los_tres_formatos(self):
        """REQ-EDT-11: cajetín propio fijo de 180×36, divisiones 20/18/22/30 y bloque inferior de 60 mm."""
        from escritorio.importar_plantillas import campo
        for texto,esperado in (('Número','numero'),('Comprobado','comprobado'),('Sustituye a','sustituye'),('Sustituido por','sustituido_por')):self.assertEqual(campo(texto),esperado)
        for nombre,(w,h) in PREDETERMINADAS.items():
            with self.subTest(nombre=nombre):
                p=plantilla_tecnica(w,h);x,y,a,b=p['title_box'];self.assertEqual((a,b),(180,36));self.assertEqual((x,y),(w-190,h-46))
                lineas=[t['points'] for t in p['primitives'] if t['kind']=='line']
                for z in (20,38,60,90):self.assertIn([x+z,y,x+z,y+18],lineas)
                self.assertIn([x+120,y+18,x+120,y+36],lineas)
                for z in (24,30):self.assertIn([x+120,y+z,x+180,y+z],lineas)
                self.assertEqual(p['inner_frame'],[20,10,w-30,h-20]);self.assertIsNone(p['zone']);self.assertFalse(any(t.get('field') in ('hoja','proyecto') for t in p['primitives']))
                textos={t['text'] for t in p['primitives'] if t['kind']=='text'}
                self.assertTrue({'Dibujado','Comprobado','Fecha','Nombre','Firmas','Escala','Nombre plano','Razón social','Número','Sustituye a','Sustituido por'}<=textos)
                self.assertNotIn('background',p);self.assertEqual({t['color'] for t in p['primitives']},{'#000000'})
    def test_STEC02_hoja_vinculada_es_presentacion_y_deshacer_atomico(self):
        """REQ-DAT-02, REQ-EDT-05, REQ-EDT-11: crear y colocar una hoja no modifica el modelo y puede deshacerse."""
        e=Editor(new_grafcet_document('m'));s=e.add_step('g','1',True);modelo=copy.deepcopy(e.model);pres=copy.deepcopy(e.presentation)
        cfg=ajustes_lamina({'plantilla':plantilla_tecnica(210,297)})
        ident=e.add_sheet_link([s],cfg);self.assertEqual(e.sheet_links()[0]['refs'],[s]);self.assertEqual(e.model,modelo)
        e.undo();self.assertEqual(e.presentation,pres);e.redo();self.assertEqual(e.sheet_links()[0]['id'],ident)
        cfg['offset_mm']=[3.,4.];e.set_sheet_link(ident,cfg);self.assertEqual(e.sheet_links()[0]['ajustes']['offset_mm'],['3','4'])
        e.undo();self.assertEqual(e.sheet_links()[0]['ajustes']['offset_mm'],['0','0']);self.assertEqual(e.model,modelo)


@unittest.skipUnless(QT,'requiere PySide6')
class TecnicasQt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.documentos=self.root/'OneDrive'/'Mis documentos';self.rutas=patch('escritorio.carpetas.QStandardPaths.writableLocation',return_value=str(self.documentos));self.rutas.start()
        self.ed,*_=cadena_lineal();self.e=Edicion(self.ed,'Prueba técnica')
    def tearDown(self):
        self.e.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.rutas.stop();self.tmp.cleanup()
    def test_STEC03_primera_ejecucion_recupera_faltantes_sin_sobrescribir(self):
        """REQ-DAT-02, REQ-EDT-11: QStandardPaths localiza Documentos, crea la estructura y respeta modificaciones."""
        r=carpetas.asegurar_carpetas();self.assertEqual(r['raiz'],self.documentos/'GrafConnect')
        for k in ('plantillas','grafcet','laminas'):self.assertTrue(r[k].is_dir())
        archivo=r['plantillas']/'A4_vertical'/'plantilla.json';p=carpetas.cargar_plantilla(archivo);p['primitives'][0]['weight']=.8;carpetas.guardar_plantilla(archivo,p);antes=archivo.read_bytes()
        falta=r['plantillas']/'A3_vertical'/'plantilla.json';falta.unlink();carpetas.asegurar_carpetas();self.assertTrue(falta.is_file());self.assertEqual(archivo.read_bytes(),antes)
        archivo.write_bytes(b'archivo modificado sin JSON');carpetas.asegurar_carpetas();self.assertEqual(archivo.read_bytes(),b'archivo modificado sin JSON')
        with self.assertRaises(ValueError):carpetas.predeterminada()
    def test_STEC04_default_a4_vertical_y_sin_a4_horizontal_en_preselecciones(self):
        """REQ-EDT-11: la creación ofrece A4 vertical por defecto y A3 en ambas orientaciones, sin preset A4 horizontal."""
        d=DialogoLaminas(self.e.M,{},self.ed.sheet_settings(),self.ed.set_sheet_settings);c=CrearHoja(self.e)
        try:
            self.assertEqual(d.valores()['formato'],'A4');self.assertEqual(d.valores()['orientacion'],'vertical');self.assertEqual(d.predeterminadas.currentText(),'A4 vertical — predeterminada')
            nombres=[d.predeterminadas.itemText(i) for i in range(d.predeterminadas.count())]
            self.assertIn('A3 horizontal',nombres);self.assertIn('A3 vertical',nombres);self.assertNotIn('A4 horizontal',nombres)
            self.assertEqual(c.valores()['orientacion'],'vertical');self.assertFalse(c.orientacion.model().item(1).isEnabled())
            c.formato.setCurrentText('A3');self.assertTrue(c.orientacion.model().item(1).isEnabled())
            c.orientacion.setCurrentIndex(1);self.assertEqual(c.valores()['plantilla']['size'],[420,297])
            d.predeterminadas.setCurrentIndex(d.indice_predeterminada('A3','horizontal'));self.assertEqual(d.documento.plantilla.p['title_box'][2:],[180,36])
        finally:d.close();c.reject();d.deleteLater();c.deleteLater()
    @unittest.skipUnless(pdf is not None,'requiere pypdfium2 para inspeccionar PDF')
    def test_STEC05_pdf_vectorial_cotas_cajetin_y_rotulos_correctos(self):
        """REQ-EDT-11: el PDF conserva el cajetín 180×36 mm y las referencias sin rasterizar la plantilla propia."""
        for f,o,w,h in (('A4','vertical',210,297),('A3','horizontal',420,297),('A3','vertical',297,420)):
            with self.subTest(f=f,o=o):
                d=DocumentoLaminas(self.e.M,{},dict(formato=f,orientacion=o));ruta=self.root/(f+o+'.pdf');d.exportar_pdf(ruta)
                lineas,texto=segmentos_pdf(ruta);x,y=w-190,h-46
                esperado=[(x,y,x+180,y),(x+180,y,x+180,y+36),(x+180,y+36,x,y+36),(x,y+36,x,y)]
                for linea in esperado:self.assertTrue(any(max(abs(a-b) for a,b in zip(linea,l))<.03 or max(abs(a-b) for a,b in zip(linea,l[2:]+l[:2]))<.03 for l in lineas),linea)
                compacto=' '.join(texto.split());self.assertIn('Dibujado',compacto);self.assertIn('Comprobado',compacto);self.assertIn('Razón social',compacto)
                self.assertNotIn(b'/Subtype /Image',ruta.read_bytes())
    def test_STEC06_arrastrar_centrar_y_escalar_no_mueven_el_cajetin(self):
        """REQ-EDT-11: arrastrar y centrar el GRAFCET cambia solo su colocación en la zona libre."""
        d=DialogoLaminas(self.e.M,{},self.ed.sheet_settings(),self.ed.set_sheet_settings)
        try:
            d.resize(1200,720);d.show();QApplication.processEvents();p=copy.deepcopy(d.documento.plantilla.p);modelo=copy.deepcopy(self.ed.model)
            vista=d.vista;doc=d.documento;factor=min((vista.width()-24)/doc.ancho,(vista.height()-24)/doc.alto)
            centro=doc.destino(0).center();a=QPoint(round((vista.width()-doc.ancho*factor)/2+centro.x()*factor),round((vista.height()-doc.alto*factor)/2+centro.y()*factor));b=a+QPoint(30,15)
            QTest.mousePress(vista,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(vista,b);QTest.mouseRelease(vista,Qt.MouseButton.LeftButton,pos=b)
            self.assertNotEqual(d.offset,[0.,0.]);QTest.mouseClick(d.b_centrar,Qt.MouseButton.LeftButton)
            self.assertLess((d.documento.destino(0).center()-d.documento.contenido.center()).manhattanLength(),.001)
            d.escala.setValue(2.);d.aplicar();self.assertEqual(d.documento.plantilla.p,p);self.assertEqual(self.ed.model,modelo)
            self.assertTrue(d.documento.contenido.contains(d.documento.destino(0)))
        finally:d.close();d.deleteLater()
    def test_STEC07_biblioteca_no_sobrescribe_ni_restaura_sin_permiso(self):
        """REQ-DAT-02, REQ-EDT-11: guardar y restaurar piden permiso y conservan el archivo si se cancela."""
        rutas=carpetas.asegurar_carpetas();archivo=rutas['plantillas']/'A4_vertical'/'plantilla.json';antes=archivo.read_bytes()
        d=DialogoLaminas(self.e.M,{},self.ed.sheet_settings(),self.ed.set_sheet_settings)
        try:
            with patch('escritorio.laminas.QFileDialog.getSaveFileName',return_value=(str(archivo),'')),patch('escritorio.laminas.QMessageBox.question',return_value=QMessageBox.StandardButton.No):d.guardar_en_biblioteca()
            self.assertEqual(archivo.read_bytes(),antes)
            p=carpetas.cargar_plantilla(archivo);p['primitives'][0]['weight']=.8;carpetas.guardar_plantilla(archivo,p);modificado=archivo.read_bytes()
            with patch('escritorio.laminas.QMessageBox.question',return_value=QMessageBox.StandardButton.No):d.restaurar_predeterminada()
            self.assertEqual(archivo.read_bytes(),modificado)
            with patch('escritorio.laminas.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes):d.restaurar_predeterminada()
            self.assertEqual(carpetas.cargar_plantilla(archivo),plantilla_tecnica(210,297))
        finally:d.close();d.deleteLater()
    def test_STEC08_vinculo_refleja_nombre_posicion_y_contenido_jerarquico(self):
        """REQ-EDT-11, REQ-JER-05: la hoja conserva IDs y vuelve a resolver geometría, rótulos y contenido de la selección."""
        s=self.ed.model['steps'][0]['id'];ref=[s,self.ed.model['transitions'][0]['id']]
        antes=dibujo_vinculado(self.e,ref);self.assertEqual(len(antes['steps']),1);self.assertEqual(len(antes['links']),1)
        self.ed.rename(s,'Etapa nueva');self.ed.move_many({s:(40,100)});self.e.cambia();despues=dibujo_vinculado(self.e,ref)
        self.assertEqual(despues['steps'][0]['label'],'Etapa nueva');self.assertEqual((despues['steps'][0]['x'],despues['steps'][0]['y']),(40,100))
        macro=self.ed.add_macro('g','M1',at=(500,0));self.e.cambia();ref=[macro.macro];nueva=self.ed.add_step(macro.partial,'Adicional',at=(800,200));self.e.cambia()
        salida=dibujo_vinculado(self.e,ref);self.assertNotIn(nueva,{x['id'] for x in salida['steps']});self.assertEqual(len(salida['macros']),1)
        salida=dibujo_vinculado(self.e,ref+[macro.partial,macro.entry,macro.exit,nueva]);self.assertIn(nueva,{x['id'] for x in salida['steps']});self.assertEqual(len(salida['macros']),1)
    def test_STEC09_accion_seleccionada_sola_usa_el_mismo_fragmento_que_copiar(self):
        """REQ-EDT-11: una acción unida enviada sola conserva su dibujo como acción suelta, sin incluir su etapa."""
        y=self.ed.add_variable('salida','output',{'kind':'bool'});s=self.ed.model['steps'][0]['id'];a=self.ed.add_continuous_action(s,y);self.e.cambia()
        m=dibujo_vinculado(self.e,[a]);self.assertFalse(m['steps']);self.assertEqual([x['id'] for x in m['draftActions']],[a]);self.assertFalse(m['draftActions'][0].get('etapa'))

    def test_STEC12_centrar_recupera_una_colocacion_fuera_de_zona(self):
        """REQ-EDT-11: si al cambiar escala la colocación deja de caber, Centrar la recupera sin alterar la plantilla."""
        d=DialogoLaminas(self.e.M,{},self.ed.sheet_settings(),self.ed.set_sheet_settings)
        try:
            antes=copy.deepcopy(d.plantilla);d.colocar([120.,80.]);self.assertIsNotNone(d.documento)
            d.escala.setValue(.5);self.assertIsNone(d.documento);self.assertTrue(d.b_centrar.isEnabled())
            d.centrar();self.assertIsNotNone(d.documento);self.assertEqual(d.plantilla,antes)
        finally:d.close();d.deleteLater()


@unittest.skipUnless(QT,'requiere PySide6')
class HojasFlujo(BaseQt):
    def setUp(self):
        self.docs=tempfile.TemporaryDirectory();self.rutas=patch('escritorio.carpetas.QStandardPaths.writableLocation',return_value=self.docs.name);self.rutas.start();super().setUp()
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.rutas.stop();self.docs.cleanup()
    def test_STEC10_enviar_seleccion_crear_guardar_abrir_y_vincular(self):
        """REQ-EDT-01, REQ-EDT-05, REQ-EDT-11: el menú crea la hoja vinculada y esta se conserva dentro de .grafnet."""
        w,e=self.vacio();s=e.ed.add_step('g','1',True);otro=e.ed.add_step('g','2',at=(300,200));e.cambia();e.sel=[s];w.show();QApplication.processEvents();modelo=copy.deepcopy(e.ed.model)
        def crear():
            d=next(x for x in QApplication.topLevelWidgets() if isinstance(x,CrearHoja) and x.isVisible())
            self.assertEqual((d.formato.currentText(),d.orientacion.currentData()),('A4','vertical'));d.accept()
        QTimer.singleShot(30,crear);w.a_enviar_lamina.trigger();self.assertEqual(len(e.ed.sheet_links()),1);self.assertEqual(e.ed.model,modelo)
        self.assertEqual(w.paginas_es.currentIndex(),2);self.assertFalse(w.panel_planos.editor.isWindow())
        self.assertEqual([x['id'] for x in w.panel_planos.editor.modelo['steps']],[s])
        e.ed.undo();self.assertEqual(e.ed.sheet_links()[0]['grafcets'],[]);e.ed.undo();self.assertFalse(e.ed.sheet_links());e.ed.redo();e.ed.redo();e.cambia()
        ruta=Path(self.tmp.name)/'hojas.grafnet';self.assertTrue(w._guardar_archivo(ruta));self.assertTrue(w.abrir_ruta(ruta));e=w.edicion;hoja=e.ed.sheet_links()[0]
        e.ed.rename(s,'Actualizada');e.cambia();m=dibujo_vinculado(e,hoja['refs']);self.assertEqual(m['steps'][0]['label'],'Actualizada');self.assertNotIn(otro,{x['id'] for x in m['steps']})
        with patch('escritorio.laminas.DialogoLaminas.exec') as emergente:
            w.mostrar_hoja(hoja['id']);emergente.assert_not_called()
    def test_STEC11_guardar_por_defecto_en_documentos_grafcet(self):
        """REQ-EDT-01, REQ-DAT-02: Guardar como propone Documentos/GrafConnect/GRAFCET, fuera de la instalación."""
        w,e=self.vacio();e.ed.add_step('g','1',True);e.cambia()
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=('','')) as pedir:w.guardar_como()
        inicial=Path(pedir.call_args.args[2]);self.assertEqual(inicial.parent,Path(self.docs.name)/'GrafConnect'/'GRAFCET')


if __name__=='__main__':unittest.main()
