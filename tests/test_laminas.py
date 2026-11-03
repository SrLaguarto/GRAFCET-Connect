"""Láminas vectoriales, paginación, cajetín y flujo de la ventana (REQ-EDT-11)."""
import copy
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from grafcet.editor import Editor,new_grafcet_document
from grafcet.laminas import ajustes_lamina,CAMPOS
from grafcet.persistence import new_project,add_document
from escritorio.proyecto_archivo import guardar_grafnet,abrir_grafnet
from test_editor_cadenas import QT,BaseQt,cadena_lineal
if QT:
    from PySide6.QtCore import Qt,QEvent,QTimer
    from PySide6.QtWidgets import QApplication,QDialog,QGraphicsTextItem
    from PySide6.QtTest import QTest
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtPrintSupport import QPrinter
    from escritorio.edicion import Edicion
    from escritorio.laminas import DocumentoLaminas,DialogoLaminas
    from escritorio.diagrama import Z_EDIT,COL

NS={'s':'http://www.w3.org/2000/svg'}

def paginas_pdf(ruta):
    datos=Path(ruta).read_bytes()
    cajas=re.findall(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]',datos)
    return len(re.findall(rb'/Type\s*/Page\b',datos)),[(float(w),float(h)) for w,h in cajas]


class AjustesLaminas(unittest.TestCase):
    def test_SLAM01_presentacion_validada_y_deshacer_sin_cambiar_modelo(self):
        """REQ-DAT-02, REQ-EDT-05, REQ-EDT-11: los ajustes son presentación y una sola operación reversible."""
        e=Editor(new_grafcet_document('m'));modelo=copy.deepcopy(e.model);antes=copy.deepcopy(e.presentation)
        cfg=ajustes_lamina({'formato':'A3','campos':{'titulo':'Línea A','revision':'B'}})
        e.set_sheet_settings(cfg);self.assertEqual(e.model,modelo);self.assertTrue(e.dirty)
        self.assertEqual(e.sheet_settings(),cfg);e.undo();self.assertEqual(e.presentation,antes)
        e.redo();self.assertEqual(e.sheet_settings(),cfg);self.assertEqual(e.model,modelo)
        for invalido in ({'formato':'A6'},{'margen_mm':100},{'escala':float('nan')},{'campos':[]},{'con_estado':'sí'}):
            with self.subTest(invalido=invalido),self.assertRaises(ValueError):e.set_sheet_settings(invalido)
        self.assertEqual(e.sheet_settings(),cfg)
    def test_SLAM02_cajetin_completo_se_conserva_en_archivo_del_proyecto(self):
        """REQ-DAT-02, REQ-EDT-11: guardar y abrir conserva todos los campos y el formato sin ampliar el modelo."""
        e=Editor(new_grafcet_document('m'));cfg=ajustes_lamina({'formato':'A3','orientacion':'vertical','modo':'escala','unidad_mm':1.,'escala':2.,'campos':{k:'Campo '+k for k in CAMPOS}})
        e.set_sheet_settings(cfg);p=new_project('p','Prueba');add_document(p,e.model);add_document(p,e.presentation)
        with tempfile.TemporaryDirectory() as t:
            ruta=Path(t)/'laminas.grafnet';guardado=guardar_grafnet(ruta,p,b'clave de prueba'.ljust(32,b'x'));abierto=None
            try:
                abierto=abrir_grafnet(ruta,b'clave de prueba'.ljust(32,b'x'),'rechazar')
                self.assertEqual(abierto.proyecto.documents,guardado.proyecto.documents)
                pres=next(d for d in abierto.proyecto.documents.values() if d.get('family')=='presentation')
                self.assertEqual(ajustes_lamina(pres['laminas']),cfg)
                self.assertIsInstance(pres['laminas']['escala'],str)
            finally:
                if abierto:abierto.cerrar()
                guardado.cerrar()


@unittest.skipUnless(QT,'requiere PySide6')
class SalidasLaminas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.ed,*_=cadena_lineal();self.e=Edicion(self.ed,'Prueba de láminas')
    def tearDown(self):self.e.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.tmp.cleanup()
    def documento(self,**cfg):return DocumentoLaminas(self.e.M,{},dict({'modo':'ajustar'},**cfg))
    def test_SLAM03_pdf_y_svg_vectoriales_con_tamano_iso_y_orientacion(self):
        """REQ-EDT-11: A4/A3 en las dos orientaciones producen vector y el tamaño físico elegido."""
        for formato,orientacion,medidas in (('A4','horizontal',(297,210)),('A4','vertical',(210,297)),('A3','horizontal',(420,297)),('A3','vertical',(297,420))):
            with self.subTest(formato=formato,orientacion=orientacion):
                d=self.documento(formato=formato,orientacion=orientacion);pdf=self.root/'prueba.pdf';svg=self.root/'prueba.svg'
                d.exportar_pdf(pdf);d.exportar_svg(svg);n,cajas=paginas_pdf(pdf);self.assertEqual(n,1);self.assertTrue(cajas)
                for ancho,alto in cajas:
                    self.assertAlmostEqual(ancho,medidas[0]*72/25.4,delta=.51);self.assertAlmostEqual(alto,medidas[1]*72/25.4,delta=.51)
                xml=ET.parse(svg).getroot();self.assertEqual(xml.get('width'),str(medidas[0])+'mm');self.assertEqual(xml.get('height'),str(medidas[1])+'mm')
                self.assertFalse(xml.findall('.//s:image',NS));self.assertTrue(xml.findall('.//s:text',NS));self.assertTrue(QSvgRenderer(str(svg)).isValid())
                self.assertNotIn(b'/Subtype /Image',pdf.read_bytes())
    def test_SLAM04_sin_seleccion_tiradores_ni_marcas_y_sin_mutacion(self):
        """REQ-EDT-11: la escena limpia excluye marcas de edición y exportar no altera modelo ni presentación."""
        self.e.sel={self.ed.model['steps'][0]['id']};antes=copy.deepcopy((self.ed.model,self.ed.presentation,self.e.M,self.e.sel))
        d=self.documento();self.assertTrue(d.escena.items());self.assertFalse(any(i.zValue()>=Z_EDIT or i.isSelected() for i in d.escena.items()))
        ruta=self.root/'limpio.svg';d.exportar_svg(ruta)
        self.assertNotIn(COL['accent'].lower(),ruta.read_text(encoding='utf-8').lower())
        self.assertEqual((self.ed.model,self.ed.presentation,self.e.M,self.e.sel),antes)
    def test_SLAM05_estado_opcional_capturado_de_la_misma_revision(self):
        """REQ-EDT-11: solo la opción de estado incluye la actividad; la captura no sigue cambios posteriores."""
        estado=self.e.vista.state();antes=copy.deepcopy(estado)
        activo=DocumentoLaminas(self.e.M,estado,{'con_estado':True,'modo':'ajustar'});limpio=DocumentoLaminas(self.e.M,estado,{'modo':'ajustar'})
        estado['situation']=[];self.assertEqual(activo.estado,antes);self.assertEqual(limpio.estado,{})
        for d,nombre in ((activo,'activo.svg'),(limpio,'limpio.svg')):d.exportar_svg(self.root/nombre)
        self.assertIn('#40d641',(self.root/'activo.svg').read_text(encoding='utf-8').lower())
        self.assertNotIn('#40d641',(self.root/'limpio.svg').read_text(encoding='utf-8').lower())
    def test_SLAM06_mosaico_numerado_sin_cortar_simbolos_y_svg_recortado(self):
        """REQ-EDT-11: la escala fija pagina con referencias, conserva proporción y no corta símbolos o textos."""
        d=self.documento(modo='escala',unidad_mm=1.,escala=1.);self.assertGreater(d.total,1);self.assertEqual(d.factor,1.)
        textos=[i for i in d.escena.items() if isinstance(i,QGraphicsTextItem)]
        for i in textos:
            r=i.sceneBoundingRect()
            for a,b in d.ys[:-1]:self.assertFalse(r.top()<b<r.bottom())
        pdf=self.root/'mosaico.pdf';d.exportar_pdf(pdf);self.assertEqual(paginas_pdf(pdf)[0],d.total)
        rutas=d.exportar_svg(self.root/'mosaico.svg');self.assertEqual(len(rutas),d.total)
        for n,ruta in enumerate(rutas):
            xml=ET.parse(ruta).getroot();self.assertIn(f'{n+1:03d}',ruta.stem)
            self.assertIsNotNone(xml.find('.//s:clipPath',NS));self.assertIsNotNone(xml.find('.//s:g[@clip-path="url(#zona-dibujo)"]',NS))
            texto=''.join(xml.itertext());self.assertIn(f'{n+1} de {d.total}',texto)
            if n<d.total-1:self.assertIn(str(n+2),texto)
    def test_SLAM07_escala_sin_referencia_y_simbolo_mayor_se_avisan(self):
        """REQ-EDT-11: no se inventa una unidad física ni se parte un símbolo que no cabe."""
        with self.assertRaisesRegex(ValueError,'referencia física'):self.documento(modo='escala',unidad_mm=None)
        with self.assertRaisesRegex(ValueError,'sin cortarlo'):self.documento(modo='escala',unidad_mm=10.,escala=1.)
    def test_SLAM08_impresion_comparte_paginas_pdf_y_respeta_cancelacion(self):
        """REQ-EDT-11: imprimir usa las mismas láminas y el diálogo del sistema; cancelar no imprime."""
        d=self.documento(modo='escala',unidad_mm=1.);ruta=self.root/'impresora.pdf'
        printer=QPrinter(QPrinter.PrinterMode.HighResolution);printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat);printer.setOutputFileName(str(ruta))
        with patch('escritorio.laminas.QPrinter',return_value=printer) as constructor,patch('escritorio.laminas.QPrintDialog') as dialogo:
            constructor.PrinterMode=QPrinter.PrinterMode;constructor.PrintRange=QPrinter.PrintRange
            dialogo.return_value.exec.return_value=QDialog.DialogCode.Rejected
            self.assertFalse(d.imprimir());self.assertFalse(ruta.exists())
            dialogo.return_value.exec.return_value=QDialog.DialogCode.Accepted
            self.assertTrue(d.imprimir());self.assertEqual(paginas_pdf(ruta)[0],d.total)
        self.assertTrue(all(abs(w-210*72/25.4)<.51 and abs(h-297*72/25.4)<.51 for w,h in paginas_pdf(ruta)[1]))
    def test_SLAM09_fallo_de_exportacion_conserva_archivo_anterior(self):
        """REQ-EDT-11, REQ-DAT-01: un fallo de exportación no destruye la salida anterior ni deja temporales."""
        d=self.documento()
        for extension,exportar in (('pdf',d.exportar_pdf),('svg',d.exportar_svg)):
            ruta=self.root/('anterior.'+extension);ruta.write_bytes(b'anterior')
            with patch('escritorio.laminas.os.replace',side_effect=OSError('fallo simulado')):
                with self.assertRaises(OSError):exportar(ruta)
            self.assertEqual(ruta.read_bytes(),b'anterior');self.assertFalse(list(self.root.glob('.lamina-*')))
    def test_SLAM10_vista_previa_navega_y_aplica_campos_con_eventos(self):
        """REQ-EDT-11: la vista previa pasa hojas y aplica el cajetín mediante sus controles reales."""
        d=DialogoLaminas(self.e.M,{},dict(modo='escala',unidad_mm=1.),self.ed.set_sheet_settings)
        try:
            d.show();QApplication.processEvents();self.assertGreater(d.documento.total,1)
            QTest.mouseClick(d.siguiente,Qt.MouseButton.LeftButton);self.assertEqual(d.indice,1)
            QTest.mouseClick(d.anterior,Qt.MouseButton.LeftButton);self.assertEqual(d.indice,0)
            d.campos['titulo'].selectAll();QTest.keyClicks(d.campos['titulo'],'Linea de prueba')
            QTest.mouseClick(d.guardar_ajustes,Qt.MouseButton.LeftButton);self.assertEqual(self.ed.sheet_settings()['campos']['titulo'],'Linea de prueba')
            salida=self.root/'desde-vista.svg'
            with patch('escritorio.laminas.QFileDialog.getSaveFileName',return_value=(str(salida),'Dibujo SVG (*.svg)')):
                QTest.mouseClick(d.b_exportar,Qt.MouseButton.LeftButton)
            self.assertTrue(d.documento.rutas_svg(salida)[0].exists())
        finally:d.close();d.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SLAM12_notas_imagenes_y_reparto_en_dos_ejes(self):
        """REQ-EDT-11, REQ-DAT-02: notas e imágenes se conservan y el mosaico numera por filas y columnas."""
        import base64
        from PySide6.QtCore import QByteArray,QBuffer,QIODevice
        from PySide6.QtGui import QImage,QColor
        imagen=QImage(20,10,QImage.Format.Format_ARGB32);imagen.fill(QColor('#326dcb'))
        datos=QByteArray();buffer=QBuffer(datos);buffer.open(QIODevice.OpenModeFlag.WriteOnly);imagen.save(buffer,'PNG');buffer.close()
        self.ed.add_annotation('image',(600,600),data='data:image/png;base64,'+base64.b64encode(bytes(datos)).decode(),width=100,height=50)
        self.ed.add_annotation('text',(450,250),text='Nota exportada',width=100,height=50)
        self.e.cambia();d=self.documento();ruta=self.root/'con-notas.svg';d.exportar_svg(ruta)
        xml=ET.parse(ruta).getroot();self.assertTrue(xml.findall('.//s:image',NS));self.assertIn('Nota exportada',' '.join(''.join(xml.itertext()).split()))
        mosaico=self.documento(modo='escala',unidad_mm=1.);self.assertGreater(len(mosaico.xs),1);self.assertGreater(len(mosaico.ys),1)
        self.assertEqual(mosaico.total,len(mosaico.xs)*len(mosaico.ys))
        self.assertEqual(mosaico.fuente(len(mosaico.xs)).left(),mosaico.fuente(0).left())
        self.assertGreater(mosaico.fuente(len(mosaico.xs)).top(),mosaico.fuente(0).top())
    def test_SLAM13_cerrar_previa_sin_cambios_no_ensucia_el_proyecto(self):
        """REQ-EDT-11: consultar la vista previa sin cambios no añade metadatos ni una operación de deshacer."""
        antes=copy.deepcopy(self.ed.presentation)
        with patch.object(self.ed,'set_sheet_settings') as aplicar:
            d=DialogoLaminas(self.e.M,{},self.ed.sheet_settings(),aplicar)
            d.show();QApplication.processEvents();d.close();aplicar.assert_not_called()
            d.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.assertEqual(self.ed.presentation,antes)

    def test_SLAM14_texto_largo_del_cajetin_no_invade_otras_celdas_en_svg(self):
        """REQ-EDT-11: el SVG emite solo las líneas que caben en cada celda del cajetín, igual que Qt/PDF."""
        d=self.documento(campos={'titulo':'palabra '*120});ruta=self.root/'largo.svg';d.exportar_svg(ruta)
        xml=ET.parse(ruta).getroot();palabras=sum((e.text or '').count('palabra') for e in xml.findall('.//s:text',NS))
        self.assertGreater(palabras,0);self.assertLess(palabras,40)
        self.assertEqual(xml.find('s:title',NS).text,'palabra '*120)

    def test_SLAM15_paginar_conserva_cajas_y_textos_del_dibujo(self):
        """REQ-EDT-11: crear el mosaico no destruye los símbolos de QGraphicsScene."""
        import gc
        ajuste=self.documento();fijo=self.documento(modo='escala',unidad_mm=1.);gc.collect()
        def inventario(d):
            return sorted((type(i).__name__,i.zValue(),i.sceneBoundingRect().getRect()) for i in d.escena.items())
        self.assertEqual(inventario(fijo),inventario(ajuste))
        self.assertEqual(sum(isinstance(i,QGraphicsTextItem) for i in fijo.escena.items()),6)


@unittest.skipUnless(QT,'requiere PySide6')
class FlujoLaminas(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    def test_SLAM11_menu_y_ctrl_p_abren_laminas_y_guarda_cajetin(self):
        """REQ-EDT-01, REQ-EDT-11: Proyecto y Ctrl+P abren la vista, imprimen y guardan el cajetín en .grafnet."""
        w,e=self.vacio();s=e.ed.add_step('g','1',True);plan=e.ed.add_sheet_plan('Plano');hoja=e.ed.add_plan_page(plan,ajustes_lamina());e.ed.set_page_graphics(hoja,[{'refs':[s],'porcentaje':100.,'offset_mm':[0.,0.]}]);e.cambia();w.show();QApplication.processEvents();antes=copy.deepcopy(e.ed.model)
        with patch.object(DocumentoLaminas,'imprimir',return_value=True) as imprimir,patch.object(DialogoLaminas,'exec') as emergente:
            w.diagrama.setFocus();QTest.keyClick(w.diagrama,Qt.Key.Key_P,Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(imprimir.call_count,1);emergente.assert_not_called()
        self.assertEqual(w.paginas_es.currentIndex(),2);d=w.panel_planos.editor
        self.assertFalse(d.isWindow());d.campos['titulo'].setText('Proyecto probado');w.panel_planos.aplicar()
        self.assertEqual(e.ed.model,antes);self.assertIn(' *',w.windowTitle())
        ruta=Path(self.tmp.name)/'laminas.grafnet';
        with patch('escritorio.archivos.QMessageBox.warning') as aviso:
            self.assertTrue(w._guardar_archivo(ruta),aviso.call_args)
        self.assertTrue(w.abrir_ruta(ruta))
        self.assertEqual(w.edicion.ed.sheet_links()[0]['ajustes']['campos']['titulo'],'Proyecto probado')
        proyecto=w.menuBar().actions()[0].menu();rotulos=[a.text().replace('&','') for a in proyecto.actions()]
        for texto in ('Planos…','Exportar…','Imprimir…'):self.assertIn(texto,rotulos)
