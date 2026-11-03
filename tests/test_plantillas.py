"""Plantillas autónomas DXF/PDF/SVG y edición real de textos y zona útil."""
import base64
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from grafcet.editor import Editor,new_grafcet_document
from grafcet.laminas import ajustes_lamina
from grafcet.plantillas import validar_plantilla
from test_editor_cadenas import QT,cadena_lineal
DXF=importlib.util.find_spec('ezdxf') is not None
PDF=importlib.util.find_spec('pypdfium2') is not None
if QT:
    from PySide6.QtCore import Qt,QPointF,QRectF,QEvent,QMarginsF
    from PySide6.QtGui import QPdfWriter,QPainter,QFont,QPen,QColor,QImage,QPageSize,QPageLayout
    from PySide6.QtWidgets import QApplication,QDialog,QGraphicsTextItem,QMessageBox
    from PySide6.QtTest import QTest
    from escritorio.edicion import Edicion
    from escritorio.laminas import DocumentoLaminas,DialogoLaminas
    from escritorio.plantillas import EditorPlantilla,valor_texto
    from escritorio.importar_plantillas import importar,importar_dxf,importar_pdf,importar_svg,paginas_pdf,formato_iso


def dxf_ejemplo(ruta,pulgadas=False):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    u=1/25.4 if pulgadas else 1
    d=ezdxf.new('R2000');d.units=1 if pulgadas else 4;m=d.modelspace()
    d.header['$EXTMIN']=(0,0,0);d.header['$EXTMAX']=(210*u,297*u,0)
    def rect(esp,x,y,w,h):
        puntos=[(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]
        for a,b in zip(puntos,puntos[1:]):esp.add_line((a[0]*u,a[1]*u),(b[0]*u,b[1]*u))
    rect(m,0,0,210,297);rect(m,10,10,190,277);rect(m,10,10,190,40)
    d.styles.new('SHX',dxfattribs={'font':'simplex.shx'})
    m.add_text('Revisión N.º 2',dxfattribs={'height':3*u,'insert':(30*u,80*u),'style':'SHX'})
    m.add_text('Giro',dxfattribs={'height':3*u,'rotation':90}).set_placement((40*u,100*u),align=TextEntityAlignment.TOP_CENTER)
    m.add_mtext(r'{\fArial|b0;Título\Pcon tildes: áéíóú}',dxfattribs={'char_height':3*u,'insert':(20*u,250*u),'width':60*u})
    m.add_text('HOJA 1 DE 1',dxfattribs={'height':3*u,'insert':(20*u,20*u)})
    m.add_text('$PRPSHEET:"Revisión"',dxfattribs={'height':3*u,'insert':(70*u,20*u)})
    b=d.blocks.new('Cajetin');rect(b,0,0,80,30)
    b.add_attdef('TITULO',(2*u,20*u),text='Por defecto',height=3*u)
    b.add_attdef('AUTOR',(2*u,10*u),text='Autor por defecto',height=3*u)
    m.add_blockref('Cajetin',(110*u,10*u)).add_auto_attribs({'TITULO':'Título importado'})
    b=d.blocks.new('Hijo');b.add_line((0,0),(10*u,0));b.add_text('Bloque',dxfattribs={'height':2*u,'insert':(0,2*u)})
    b=d.blocks.new('Padre');b.add_blockref('Hijo',(0,0),dxfattribs={'xscale':2,'yscale':2,'rotation':90})
    m.add_blockref('Padre',(100*u,200*u))
    m.add_circle((60*u,160*u),5*u);m.add_arc((80*u,160*u),5*u,20,110)
    m.add_ellipse((120*u,160*u),major_axis=(10*u,0),ratio=.5)
    m.add_lwpolyline([(140*u,150*u,0,0,.4),(150*u,160*u,0,0,0)],format='xyseb')
    m.add_polyline2d([(20*u,150*u),(30*u,160*u),(40*u,150*u)])
    m.add_spline([(160*u,160*u),(170*u,180*u),(180*u,150*u)])
    d.saveas(ruta)


def pdf_ejemplo(ruta,formato='A4',paginas=1,trazos=False):
    w,h={'A4':(210,297),'A3':(297,420)}[formato]
    writer=QPdfWriter(str(ruta));writer.setResolution(72)
    writer.setPageLayout(QPageLayout(QPageSize(getattr(QPageSize.PageSizeId,formato)),QPageLayout.Orientation.Portrait,QMarginsF(0,0,0,0)))
    p=QPainter(writer)
    try:
        for i in range(paginas):
            if i:writer.newPage()
            p.save();p.scale(72/25.4,72/25.4);p.setPen(QPen(QColor('black'),.25));p.drawRect(QRectF(10,10,w-20,h-20));p.drawRect(QRectF(10,h-50,w-20,40))
            f=QFont('Arial');f.setPixelSize(4);p.setFont(f);p.setPen(QColor('#0044cc'))
            if trazos:
                from PySide6.QtGui import QPainterPath
                trazo=QPainterPath();trazo.addText(QPointF(20,h-30),f,'Texto en trazos');p.drawPath(trazo)
            else:
                p.drawText(QPointF(20,h-30),'Título original '+str(i+1));p.drawText(QPointF(100,h-30),'HOJA 1 DE 1')
                p.save();p.translate(80,h-30);p.rotate(-90);p.drawText(QPointF(0,0),'Vertical');p.restore()
            p.restore()
    finally:p.end()
    del writer


@unittest.skipUnless(QT,'requiere PySide6')
class Plantillas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.ed,*_=cadena_lineal();self.e=Edicion(self.ed,'Ejemplo')
    def tearDown(self):self.e.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.tmp.cleanup()
    def dxf(self,pulgadas=False):
        ruta=self.root/'generado.dxf';dxf_ejemplo(ruta,pulgadas);return importar_dxf(ruta)
    def cfg(self,p):
        f,o=formato_iso(*p['size']);return ajustes_lamina({'plantilla':p,'formato':f,'orientacion':o,'campos':{'titulo':'Mi proyecto','autor':'Responsable','revision':'C'}})
    @unittest.skipUnless(DXF,'requiere ezdxf')
    def test_SPLT01_dxf_entidades_bloques_unidades_textos_y_campos(self):
        """REQ-EDT-11, REQ-DAT-02: DXF en mm/pulgadas conserva geometría, atributos, tildes, alineación y transformaciones."""
        for pulgadas in (False,True):
            with self.subTest(pulgadas=pulgadas):
                p=self.dxf(pulgadas);self.assertEqual(p['size'],[210,297]);self.assertFalse(p['warnings'])
                textos=[t for t in p['primitives'] if t['kind']=='text'];self.assertIn('Revisión N.º 2',[t['text'] for t in textos]);self.assertIn('Título\ncon tildes: áéíóú',[t['text'] for t in textos])
                self.assertEqual(next(t for t in textos if t['text']=='Revisión N.º 2')['font'],'Consolas')
                campos={t['field']:t for t in textos if t.get('field')};self.assertEqual(set(campos),{'titulo','autor','revision'})
                self.assertEqual(sum(t.get('field')=='titulo' for t in textos),1);self.assertEqual(valor_texto(campos['titulo'],{'titulo':'Rellenado'}),'Rellenado')
                giro=next(t for t in textos if t['text']=='Giro');self.assertEqual(giro['align'],'center');self.assertEqual(giro['valign'],'top');self.assertAlmostEqual(giro['rotation'],-90)
                bloque=next(t for t in textos if t['text']=='Bloque');self.assertAlmostEqual(bloque['rotation'],-90);self.assertAlmostEqual(bloque['height'],4)
                self.assertTrue(any(t['kind']=='arc' and t['span']==360 for t in p['primitives']));self.assertGreaterEqual(sum(t['kind']=='path' for t in p['primitives']),4)
                self.assertIsNotNone(p.get('detected_zone'));self.assertGreater(p['detected_zone'][1]+p['detected_zone'][3],247);self.assertIsNotNone(p.get('title_box'))
    @unittest.skipUnless(DXF,'requiere ezdxf')
    def test_SPLT02_sugerencias_no_enlazan_sin_aceptacion(self):
        """REQ-EDT-11: HOJA se propone y permanece fija hasta aceptar expresamente el enlace."""
        p=self.dxf();t=next(t for t in p['primitives'] if t.get('suggest')=='hoja');self.assertFalse(t.get('field'))
        d=EditorPlantilla(p,{'hoja':'2 de 8'})
        try:
            d.show();QApplication.processEvents();n=next(i for i,x in enumerate(d.items) if x.t.get('suggest')=='hoja');d.lista.setCurrentRow(n)
            self.assertEqual(valor_texto(d.actual.t,d.campos),'HOJA 1 DE 1');QTest.mouseClick(d.sugerencia,Qt.MouseButton.LeftButton)
            self.assertEqual(d.actual.t['field'],'hoja');self.assertEqual(valor_texto(d.actual.t,d.campos),'HOJA 2 de 8');self.assertFalse(t.get('field'))
        finally:d.close();d.deleteLater()
    @unittest.skipUnless(PDF,'requiere pypdfium2')
    def test_SPLT03_pdf_a4_a3_fondo_300ppp_sin_textos_y_giro(self):
        """REQ-EDT-11: PDF conserva mm, extrae textos editables y deja un fondo PNG sin duplicarlos."""
        for formato,ancho,alto in (('A4',210,297),('A3',297,420)):
            with self.subTest(formato=formato):
                ruta=self.root/'original.pdf';pdf_ejemplo(ruta,formato);p=importar_pdf(ruta)
                self.assertAlmostEqual(p['size'][0],ancho,delta=.2);self.assertAlmostEqual(p['size'][1],alto,delta=.2)
                textos=p['primitives'];self.assertIn('Título original 1',[t['text'] for t in textos]);self.assertIn('HOJA 1 DE 1',[t['text'] for t in textos])
                self.assertEqual(next(t for t in textos if t['text']=='HOJA 1 DE 1')['suggest'],'hoja')
                self.assertAlmostEqual(abs(next(t for t in textos if t['text']=='Vertical')['rotation']),90,delta=.1)
                img=QImage.fromData(base64.b64decode(p['background']['data']),'PNG');self.assertFalse(img.isNull());self.assertAlmostEqual(img.width(),p['size'][0]/25.4*300,delta=1)
                self.assertNotIn(b'\x00\x44\xcc',img.convertToFormat(QImage.Format.Format_RGB888).bits().tobytes())
                self.assertGreater(p['detected_zone'][1]+p['detected_zone'][3],alto-49);self.assertIsNotNone(p.get('title_box'))
    @unittest.skipUnless(PDF,'requiere pypdfium2')
    def test_SPLT04_pdf_pagina_elegida_y_textos_en_trazos_avisados(self):
        """REQ-EDT-11: elegir otra página respeta su contenido; los textos en trazos se conservan y se avisan."""
        ruta=self.root/'dos.pdf';pdf_ejemplo(ruta,paginas=2);self.assertEqual(paginas_pdf(ruta),2)
        p=importar_pdf(ruta,1);self.assertIn('Título original 2',[t['text'] for t in p['primitives']])
        pdf_ejemplo(ruta,trazos=True);p=importar_pdf(ruta);self.assertFalse(p['primitives']);self.assertTrue(any('trazos' in s for s in p['warnings']))
        with self.assertRaisesRegex(ValueError,'inexistente'):importar_pdf(ruta,5)
        pdf_ejemplo(ruta)
        with patch('pypdfium2.PdfTextObj.extract',return_value='\ufffd'):
            p=importar_pdf(ruta);self.assertFalse(p['primitives']);self.assertTrue(any('decodificar' in s for s in p['warnings']))
    @unittest.skipUnless(DXF and PDF,'requiere ezdxf y pypdfium2')
    def test_SPLT05_guardar_abrir_sin_original_ni_importadores_y_deshacer(self):
        """REQ-DAT-02, REQ-EDT-05, REQ-EDT-11: plantilla autónoma en .grafnet y una operación reversible sin tocar modelo."""
        from grafcet.persistence import new_project,add_document
        from escritorio.proyecto_archivo import guardar_grafnet,abrir_grafnet
        for tipo in ('dxf','pdf'):
            with self.subTest(tipo=tipo):
                ruta=self.root/('origen.'+tipo)
                if tipo=='dxf':dxf_ejemplo(ruta);p=importar_dxf(ruta)
                else:pdf_ejemplo(ruta);p=importar_pdf(ruta)
                modelo=copy.deepcopy(self.ed.model);pres=copy.deepcopy(self.ed.presentation);self.ed.set_sheet_settings(self.cfg(p));self.ed.undo();self.assertEqual(self.ed.presentation,pres);self.ed.redo();self.assertEqual(self.ed.model,modelo)
                proyecto=new_project('p','Prueba');add_document(proyecto,self.ed.model);add_document(proyecto,self.ed.presentation)
                key=b'plantillas prueba'.ljust(32,b'x');destino=self.root/'prueba.grafnet';g=guardar_grafnet(destino,proyecto,key);g.cerrar();ruta.unlink()
                with patch.dict('sys.modules',{'ezdxf':None,'pypdfium2':None}):
                    a=abrir_grafnet(destino,key,'rechazar')
                    try:
                        doc=next(d for d in a.proyecto.documents.values() if d.get('family')=='presentation');cfg=ajustes_lamina(doc['laminas']);self.assertEqual(cfg,self.ed.sheet_settings())
                        salida=DocumentoLaminas(self.e.M,{},cfg);salida.exportar_svg(self.root/'abierto.svg');salida.exportar_pdf(self.root/'abierto.pdf')
                    finally:a.cerrar()
    @unittest.skipUnless(PDF,'requiere pypdfium2')
    def test_SPLT06_exportaciones_contienen_fondo_y_texto_editado_con_zona(self):
        """REQ-EDT-11: PDF/SVG y mosaico reutilizan fondo, campos editados y zona útil sin invadir el cajetín."""
        ruta=self.root/'origen.pdf';pdf_ejemplo(ruta);p=importar_pdf(ruta);p['zone']=[20.,20.,160.,180.]
        next(t for t in p['primitives'] if t['text']=='Título original 1')['text']='Texto editado'
        cfg=self.cfg(p);d=DocumentoLaminas(self.e.M,{},cfg);self.assertEqual(d.contenido.getRect(),(20,20,160,180))
        self.assertTrue(d.contenido.contains(d.destino(0)));d.exportar_svg(self.root/'salida.svg');d.exportar_pdf(self.root/'salida.pdf')
        xml=ET.parse(self.root/'salida.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
        self.assertTrue(xml.findall('.//s:image',ns));self.assertIn('Texto editado',''.join(xml.itertext()));self.assertIn(b'/Subtype /Image',(self.root/'salida.pdf').read_bytes())
        fijo=DocumentoLaminas(self.e.M,{},dict(cfg,modo='escala',unidad_mm=1.));self.assertGreater(fijo.total,1)
        for i in range(fijo.total):self.assertTrue(fijo.contenido.adjusted(-.001,-.001,.001,.001).contains(fijo.destino(i)))
    def test_SPLT07_svg_autonomo_tamano_real_y_personalizado(self):
        """REQ-EDT-11: SVG autónomo se usa de fondo sin campos y conserva sus medidas físicas."""
        ruta=self.root/'fondo.svg';ruta.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="123mm" height="87mm"><rect x="1" y="1" width="99" height="70"/></svg>',encoding='utf-8')
        p=importar_svg(ruta);self.assertEqual(p['size'],[123,87]);self.assertFalse(p['primitives']);d=DocumentoLaminas(self.e.M,{},self.cfg(p));self.assertEqual((d.ancho,d.alto),(123,87))
        self.assertAlmostEqual(d.layout().fullRect(QPageLayout.Unit.Millimeter).width(),123,delta=.2)
        ruta.unlink();d.exportar_pdf(self.root/'svg.pdf')
    @unittest.skipUnless(DXF,'requiere ezdxf')
    def test_SPLT08_editor_textos_mover_borrar_anadir_y_marcar_zona(self):
        """REQ-EDT-11: edición real de contenido, posición, tamaño, giro y zona; cancelar conserva el original."""
        original=self.dxf();antes=copy.deepcopy(original);d=EditorPlantilla(original,{'titulo':'Proyecto'})
        try:
            d.show();QApplication.processEvents();d.vista.fitInView(d.escena.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
            QTest.mouseClick(d.nuevo,Qt.MouseButton.LeftButton);item=d.actual;d.contenido.setFocus();d.contenido.selectAll();QTest.keyClicks(d.contenido,'Texto nuevo')
            d.altura.setValue(4.);d.giro.setCurrentIndex(d.giro.findData(90.));d.alineacion.setCurrentIndex(d.alineacion.findData('center'))
            a=d.vista.mapFromScene(item.pos()+QPointF(0,1));b=a+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(25,15)
            pos=item.pos();QTest.mousePress(d.vista.viewport(),Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(d.vista.viewport(),b);QTest.mouseRelease(d.vista.viewport(),Qt.MouseButton.LeftButton,pos=b)
            self.assertNotEqual(item.pos(),pos);self.assertEqual(item.t['text'],'Texto nuevo');self.assertEqual(item.t['rotation'],90.)
            QTest.mouseClick(d.b_zona,Qt.MouseButton.LeftButton);a=d.vista.mapFromScene(QPointF(25,25));b=d.vista.mapFromScene(QPointF(180,210))
            QTest.mousePress(d.vista.viewport(),Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(d.vista.viewport(),b);QTest.mouseRelease(d.vista.viewport(),Qt.MouseButton.LeftButton,pos=b)
            self.assertIsNotNone(d.plantilla['zone']);self.assertAlmostEqual(d.plantilla['zone'][2],155,delta=2)
            n=len(d.items);QTest.mouseClick(d.borrar,Qt.MouseButton.LeftButton);self.assertEqual(len(d.items),n-1);d.reject();self.assertEqual(original,antes)
        finally:d.close();d.deleteLater()
    @unittest.skipUnless(DXF,'requiere ezdxf')
    def test_SPLT09_importar_invalido_y_cancelar_no_cambian_lamina(self):
        """REQ-EDT-11: errores, DWG y cancelación dejan formato, plantilla y campos intactos."""
        d=DialogoLaminas(self.e.M,{},self.ed.sheet_settings(),self.ed.set_sheet_settings)
        try:
            antes=copy.deepcopy(d.valores());ruta=self.root/'roto.dxf';ruta.write_text('no es un dxf')
            for archivo in (ruta,self.root/'archivo.dwg'):
                with patch('escritorio.laminas.QFileDialog.getOpenFileName',return_value=(str(archivo),'')),patch('escritorio.laminas.QMessageBox.warning') as aviso:
                    d.importar_plantilla();self.assertEqual(d.valores(),antes);aviso.assert_called_once()
            ruta=self.root/'bien.dxf';dxf_ejemplo(ruta)
            with patch('escritorio.laminas.QFileDialog.getOpenFileName',return_value=(str(ruta),'')),patch.object(EditorPlantilla,'exec',return_value=QDialog.DialogCode.Rejected):
                d.importar_plantilla();self.assertEqual(d.valores(),antes)
        finally:d.close();d.deleteLater()
    @unittest.skipUnless(PDF,'requiere pypdfium2')
    def test_SPLT10_pdf_cifrado_invalido_y_vacio_rechazados(self):
        """REQ-EDT-11: cifrado, archivo no válido y página vacía dan avisos claros antes de importar."""
        ruta=self.root/'mal.pdf';ruta.write_bytes(b'no es PDF')
        with self.assertRaisesRegex(ValueError,'PDF no válido'):importar_pdf(ruta)
        pdf_ejemplo(ruta)
        with patch('pypdfium2.raw.FPDF_GetSecurityHandlerRevision',return_value=2),self.assertRaisesRegex(ValueError,'cifrado'):importar_pdf(ruta)
        w=QPdfWriter(str(ruta));p=QPainter(w);p.end();del w
        with self.assertRaisesRegex(ValueError,'vacía'):importar_pdf(ruta)
    def test_SPLT11_validacion_de_primitivas_y_limites_de_zona(self):
        """REQ-DAT-02, REQ-EDT-11: no se aceptan coordenadas, primitivas o zonas corruptas."""
        for p in ({'version':1,'size':[210,297],'primitives':[{'kind':'secreto'}]}, {'version':1,'size':[210,297],'primitives':[],'zone':[10,10,300,40]}, {'version':1,'size':[float('nan'),297],'primitives':[]}):
            with self.subTest(p=p),self.assertRaises(ValueError):validar_plantilla(p)

    @unittest.skipUnless(DXF,'requiere ezdxf')
    def test_SPLT12_importacion_aceptada_se_guarda_con_campos_y_mismo_modelo(self):
        """REQ-EDT-11, REQ-DAT-02: aceptar la importación permite aplicar y guardar la plantilla desde Lámina."""
        ruta=self.root/'nuevo.dxf';dxf_ejemplo(ruta);modelo=copy.deepcopy(self.ed.model)
        d=DialogoLaminas(self.e.M,{},self.ed.sheet_settings(),self.ed.set_sheet_settings)
        try:
            with patch('escritorio.laminas.QFileDialog.getOpenFileName',return_value=(str(ruta),'')),patch.object(EditorPlantilla,'exec',return_value=QDialog.DialogCode.Accepted):d.importar_plantilla()
            self.assertEqual(d.formato.currentText(),'A4');self.assertFalse(d.formato.isEnabled());self.assertTrue(d.a_editar_plantilla.isEnabled())
            self.assertEqual(d.documento.contenido.left(),d.plantilla['detected_zone'][0]);self.assertEqual(d.documento.contenido.bottom(),d.plantilla['title_box'][1]-2)
            d.campos['titulo'].setText('Campo rellenado desde lamina');d.campos['autor'].setText('Autor de prueba')
            salida=self.root/'campos.svg';d.documento.exportar_svg(salida)
            textos=''.join((e.text or '') for e in ET.parse(salida).getroot().findall('.//{http://www.w3.org/2000/svg}text'))
            self.assertIn('Campo rellenado desde lamina',textos);self.assertIn('Autor de prueba',textos)
            d.aplicar();self.assertEqual(self.ed.model,modelo);self.assertEqual(self.ed.sheet_settings()['plantilla']['source'],'DXF')
            self.assertIsInstance(self.ed.presentation['laminas']['plantilla']['size'][0],str)
        finally:d.close();d.deleteLater()
    @unittest.skipUnless(DXF,'requiere ezdxf')
    def test_SPLT13_dxf_sin_unidades_y_caja_no_iso(self):
        """REQ-EDT-11: sin INSUNITS se usan mm y un marco no ISO conserva su caja propia."""
        import ezdxf
        ruta=self.root/'sin-unidades.dxf';doc=ezdxf.new();doc.units=0;doc.modelspace().add_lwpolyline([(30,20),(153,20),(153,107),(30,107)],close=True);doc.saveas(ruta)
        p=importar_dxf(ruta);self.assertEqual(p['size'],[123,87]);self.assertEqual(formato_iso(*p['size'])[0],'Personalizado')
        d=DocumentoLaminas(self.e.M,{},self.cfg(p));self.assertEqual((d.ancho,d.alto),(123,87))
        doc=ezdxf.new();doc.saveas(ruta)
        with self.assertRaisesRegex(ValueError,'vacío'):importar_dxf(ruta)
    @unittest.skipUnless(PDF,'requiere pypdfium2')
    def test_SPLT14_pdf_texto_en_formulario_anidado_se_extrae_y_quita(self):
        """REQ-EDT-11: los textos dentro de Form XObjects también son editables y desaparecen del fondo."""
        import pypdfium2 as pdf
        origen=self.root/'original.pdf';destino=self.root/'formulario.pdf';pdf_ejemplo(origen)
        src=pdf.PdfDocument(origen);dst=pdf.PdfDocument.new();pagina=dst.new_page(595,842)
        xo=src.page_as_xobject(0,dst);obj=xo.as_pageobject();pagina.insert_obj(obj);pagina.gen_content();dst.save(destino)
        pagina.close();xo.close();dst.close();src.close()
        p=importar_pdf(destino);self.assertIn('Título original 1',[t['text'].strip() for t in p['primitives']])
        img=QImage.fromData(base64.b64decode(p['background']['data']),'PNG').convertToFormat(QImage.Format.Format_RGB888)
        self.assertNotIn(b'\x00\x44\xcc',img.bits().tobytes())

    def test_SPLT15_zona_automatica_usa_marco_interior_y_no_cuadricula(self):
        """REQ-EDT-11: con doble marco, la zona útil empieza dentro del marco interior, fuera de la cuadrícula."""
        from escritorio.importar_plantillas import zona_detectada
        lineas=[]
        for x,y,w,h in ((15,5,400,287),(20,10,390,277),(220,230,190,57)):
            pts=[(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]
            lineas.extend({'kind':'line','points':list(a)+list(b)} for a,b in zip(pts,pts[1:]))
        p={'version':1,'size':[420,297],'primitives':lineas};zona_detectada(p)
        self.assertEqual(p['detected_zone'],[22,12,386,273]);self.assertEqual(p['title_box'],[220,230,190,57])
        d=DocumentoLaminas(self.e.M,{},self.cfg(p));self.assertTrue(QRectF(20,10,390,220).contains(d.contenido));self.assertTrue(d.contenido.contains(d.destino(0)))

    def test_SPLT16_escala_fija_por_defecto_etapas_de_1164_mm(self):
        """REQ-EDT-11: decisión del responsable, etapa de 44 unidades a unos 11,64 mm por defecto, sin ajuste automático."""
        cfg=ajustes_lamina();self.assertEqual(cfg['modo'],'escala');self.assertEqual(cfg['escala'],1.)
        d=DocumentoLaminas(self.e.M,{},cfg);self.assertAlmostEqual(44*d.factor,11.64,delta=.01)
        d=DialogoLaminas(self.e.M,{},cfg,self.ed.set_sheet_settings)
        try:
            self.assertAlmostEqual(d.valores()['unidad_mm'],25.4/96);self.assertIsNotNone(d.documento);self.assertEqual(d.escala.singleStep(),.1)
        finally:d.close();d.deleteLater()

    @unittest.skipUnless(DXF,'requiere ezdxf')
    def test_SPLT17_textos_fit_aligned_respetan_anclas_y_altura(self):
        """REQ-EDT-11: TEXT FIT y ALIGNED conservan el ancho entre anclas; ALIGNED escala también la altura."""
        import ezdxf,math
        from ezdxf.enums import TextEntityAlignment
        from escritorio.plantillas import layout_texto
        ruta=self.root/'alineados.dxf';doc=ezdxf.new();doc.units=4;m=doc.modelspace()
        m.add_lwpolyline([(0,0),(210,0),(210,297),(0,297)],close=True)
        m.add_text('Ajustado',dxfattribs={'height':3}).set_placement((20,20),(80,20),align=TextEntityAlignment.FIT)
        m.add_text('Ajustado',dxfattribs={'height':3}).set_placement((20,40),(80,40),align=TextEntityAlignment.ALIGNED)
        m.add_text('Diagonal',dxfattribs={'height':3}).set_placement((20,60),(40,80),align=TextEntityAlignment.FIT)
        doc.saveas(ruta);p=importar_dxf(ruta);textos=[t for t in p['primitives'] if t['kind']=='text']
        fit=next(t for t in textos if t['text']=='Ajustado' and t['fit']=='fit');alineado=next(t for t in textos if t.get('fit')=='aligned')
        self.assertAlmostEqual(layout_texto(fit,fit['text'])[3].width(),60,delta=.01)
        self.assertAlmostEqual(layout_texto(alineado,alineado['text'])[3].width(),60,delta=.01)
        self.assertGreater(layout_texto(alineado,alineado['text'])[3].height(),layout_texto(fit,fit['text'])[3].height())
        diagonal=next(t for t in textos if t['text']=='Diagonal');self.assertAlmostEqual(diagonal['rotation'],-45,delta=.01)
        self.assertAlmostEqual(layout_texto(diagonal,diagonal['text'])[3].width(),math.sqrt(800),delta=.01)


if __name__=='__main__':unittest.main()
