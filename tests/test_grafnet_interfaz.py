"""Flujo de archivo único: atajos, recursos, E/S e integridad."""
import copy
import os
import zipfile
from pathlib import Path
import unittest
from unittest.mock import patch
from test_editor_cadenas import BaseQt,QT
from escritorio import sello
from escritorio.proyecto_archivo import abrir_grafnet,guardar_grafnet
from grafcet.contenedor import INFO,SELLO
from grafcet.persistence import open_project
if QT:
    from PySide6.QtCore import Qt,QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QLabel,QMessageBox
    from escritorio.ventana import AcercaDe
    from conexion.configuracion import Configuracion,ARCHIVO


@unittest.skipUnless(QT,'requiere PySide6')
class GrafnetInterfaz(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    def preparar(self):
        w,e=self.vacio();s=e.ed.add_step('g','1',True);e.ed.add_annotation('text',(300,120),text='Nota de proyecto')
        e.cambia();w.resize(1366,768);w.show();QApplication.processEvents();return w,e
    def guardar(self,nombre='proyecto.grafnet'):
        w=self.w;destino=Path(self.tmp.name)/nombre
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=(str(destino),'')):
            self.assertTrue(w.guardar_como())
        return destino
    def test_SGFN08_ctrl_s_guardar_como_y_nombre_con_asterisco(self):
        """REQ-EDT-01, REQ-EDT-05: Ctrl+S crea un archivo, Ctrl+Mayús+S guarda otra copia y el título sigue nombre y cambios."""
        w,e=self.preparar();destino=Path(self.tmp.name)/'atajo.grafnet';w.diagrama.setFocus()
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=(str(destino),'')):
            QTest.keyClick(w.diagrama,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(destino.is_file());self.assertIn(destino.name,w.windowTitle());self.assertNotIn(' *',w.windowTitle());self.assertNotIn(' *',w.titulo.text())
        e.ed.update_annotation(e.ed.annotations()[0]['id'],text='Cambiado');e.cambia();self.assertIn(' *',w.windowTitle())
        copia=Path(self.tmp.name)/'otra.grafnet'
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=(str(copia),'')):
            QTest.keyClick(w.diagrama,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(copia.exists());self.assertEqual(e.archivo,copia)
        self.assertTrue(w.abrir_ruta(destino));self.assertEqual(w.edicion.ed.annotations()[0]['text'],'Nota de proyecto')
    def test_SGFN10_archivo_manipulado_conserva_edicion_actual(self):
        """REQ-EDT-05, REQ-DAT-02: rechazar un archivo manipulado no descarta ni sustituye la edición actual."""
        w,e=self.preparar();destino=self.guardar();e.ed.add_step('g','2');e.cambia();antes=copy.deepcopy(e.ed.model)
        destino.write_bytes(b'archivo manipulado')
        with patch('escritorio.ventana.QMessageBox.warning') as aviso,patch.object(w,'_salir_de_edicion') as salir:
            self.assertFalse(w.abrir_ruta(destino));aviso.assert_called_once();salir.assert_not_called()
        self.assertIs(w.edicion,e);self.assertEqual(e.ed.model,antes);self.assertTrue(e.ed.dirty)
    def test_SGFN11_archivo_conserva_mapa_y_recursos(self):
        """REQ-DAT-01, REQ-DAT-02: el archivo conserva E/S y recursos sin exponer carpetas como formato de proyecto."""
        w,e=self.preparar();destino=self.guardar()
        (e.ruta/'recursos').mkdir();(e.ruta/'recursos'/'imagen.png').write_bytes(b'recurso conservado')
        w.panel_es.host.setText('10.20.30.40');w.panel_es.host.editingFinished.emit()
        self.assertTrue(w.guardar());self.assertTrue(w.abrir_ruta(destino))
        self.assertEqual(w.panel_es.obtener().host,'10.20.30.40')
        self.assertEqual((w.edicion.ruta/'recursos'/'imagen.png').read_bytes(),b'recurso conservado')
    def test_SGFN12_rechaza_carpetas_y_json_pero_abre_con_otro_sello(self):
        """REQ-DAT-02: carpetas y JSON sueltos se rechazan; un .grafnet con otra clave se abre sin firma válida."""
        w,e=self.preparar();carpeta=Path(self.tmp.name)/'antiguo';e.guardar(carpeta);destino=self.guardar()
        with patch('escritorio.ventana.QMessageBox.warning'):
            self.assertFalse(w.abrir_ruta(carpeta));self.assertFalse(w.abrir_ruta(next(carpeta.glob('model-*.json'))))
        with patch.object(sello,'CLAVE',os.urandom(32)),patch('escritorio.ventana.QMessageBox.warning') as aviso:
            self.assertTrue(w.abrir_ruta(destino));aviso.assert_not_called()
        self.assertEqual(w.edicion.contenedor.firma,'sin_firma')
    def test_SGFN14_fallo_al_guardar_no_cambia_destino_ni_dirty(self):
        """REQ-DAT-01, REQ-EDT-05: fallar Guardar como conserva el archivo, el estado anteriores."""
        w,e=self.preparar();destino=self.guardar();anterior=destino.read_bytes();e.ed.add_step('g','2');e.cambia()
        with patch('grafcet.contenedor.os.replace',side_effect=OSError('fallo simulado')),patch('escritorio.archivos.QMessageBox.warning'):
            self.assertFalse(w._guardar_archivo(destino))
        self.assertEqual(destino.read_bytes(),anterior);self.assertTrue(e.ed.dirty);self.assertEqual(e.archivo,destino)

    def test_SGFN19_acerca_distingue_desarrollo_sin_mostrar_clave(self):
        """REQ-DAT-02: Acerca de identifica desarrollo sin revelar la clave y la marca no aparece en una versión repartible."""
        w,e=self.preparar()
        for desarrollo in (True,False):
            vistos=[]
            with patch.object(sello,'DESARROLLO',desarrollo),patch.object(AcercaDe,'exec',lambda d:vistos.append(d) or 0):
                w.acerca();texto=' '.join(x.text() for x in vistos[0].findChildren(QLabel))
                self.assertEqual('versión de desarrollo' in texto,desarrollo)
                self.assertNotIn(sello.CLAVE.hex(),texto)

    def test_SGFN20_extension_y_cancelacion_no_sobrescriben_ni_modifican(self):
        """REQ-EDT-05, REQ-DAT-01: añadir .grafnet respeta un archivo existente y cancelar Guardar como conserva la edición."""
        w,e=self.preparar();destino=Path(self.tmp.name)/'nombre.grafnet';destino.write_bytes(b'anterior')
        antes=copy.deepcopy(e.ed.model)
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=(str(destino.with_suffix('')),'')),patch('escritorio.archivos.QMessageBox.question',return_value=QMessageBox.StandardButton.No):
            self.assertFalse(w.guardar_como())
        self.assertEqual(destino.read_bytes(),b'anterior');self.assertEqual(e.ed.model,antes);self.assertTrue(e.ed.dirty)
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=('','')):
            self.assertFalse(w.guardar_como())
        self.assertIsNone(e.archivo)


    def test_SGFN23_aplicacion_sin_recuperacion_ni_opciones_de_password(self):
        """REQ-EDT-09: la aplicación no inicia autoguardado ni conserva controles o diálogos de contraseña y recuperación."""
        w,e=self.preparar()
        for nombre in ('recup','t_auto','autoguardar','ofrecer_recuperacion','_opciones_password','_pedir_password_archivo'):
            self.assertFalse(hasattr(w,nombre),nombre)
        self.assertFalse(hasattr(e,'password'))
    def test_SGFN24_guardar_como_no_abre_dialogos_adicionales(self):
        """REQ-EDT-01, REQ-EDT-09: elegir el nombre es suficiente para guardar el proyecto, sin un diálogo de protección."""
        from PySide6.QtWidgets import QDialog
        w,e=self.preparar();ruta=Path(self.tmp.name)/'directo.grafnet'
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=(str(ruta),'')) as elegir,patch.object(QDialog,'exec') as dialogo:
            self.assertTrue(w.guardar_como());elegir.assert_called_once();dialogo.assert_not_called()
        self.assertTrue(ruta.is_file());self.assertTrue(w.abrir_ruta(ruta))
    def test_SGFN25_no_se_guarda_un_proyecto_como_carpeta(self):
        """REQ-DAT-02, REQ-EDT-01: la interfaz solo escribe proyectos .grafnet y nunca crea la carpeta del formato anterior."""
        w,e=self.preparar();ruta=Path(self.tmp.name)/'carpeta'
        with self.assertRaises(ValueError):w.guardar_en(ruta)
        self.assertFalse(ruta.exists());self.assertTrue(e.ed.dirty)

    def archivo_con(self,nombre,clave):
        """Copia del proyecto actual guardada con `clave` (None: sin sello)."""
        w=self.w;e=w.edicion;destino=Path(self.tmp.name)/nombre
        guardado=guardar_grafnet(destino,e.proyecto(),clave,e.ruta);guardado.cerrar();return destino
    def con_sello(self,ruta):
        with zipfile.ZipFile(ruta) as z:return SELLO in z.namelist()
    def abrir_limpio(self,ruta):
        self.w.edicion.ed.dirty=False
        with patch('escritorio.ventana.QMessageBox.warning') as aviso:
            self.assertTrue(self.w.abrir_ruta(ruta));aviso.assert_not_called()
        return self.w.edicion

    def test_SGFN30_archivo_sin_sello_abre_sin_firma_con_indicacion_en_la_barra(self):
        """REQ-DAT-02: un archivo sin sello se abre sin cuadros modales, con estado sin_firma y «Archivo sin firma» en la barra."""
        w,e=self.preparar();self.guardar();sin=self.archivo_con('sin.grafnet',None)
        self.assertFalse(self.con_sello(sin));self.assertFalse(w.l_firma.isVisible())
        e2=self.abrir_limpio(sin)
        self.assertEqual(e2.contenedor.firma,'sin_firma');self.assertFalse(e2.puede_firmarse)
        self.assertTrue(w.l_firma.isVisible());self.assertEqual(w.l_firma.text(),'Archivo sin firma')
        self.assertIn('seguirá sin firma',w.l_firma.toolTip())
        self.assertTrue(self.abrir_limpio(self.archivo_con('con.grafnet',sello.CLAVE)).puede_firmarse);self.assertFalse(w.l_firma.isVisible())
    def test_SGFN31_clave_de_desarrollo_en_version_de_distribucion_es_estado_desarrollo(self):
        """REQ-DAT-02: con clave de distribución, un archivo firmado con la de desarrollo abre con estado «desarrollo»."""
        w,e=self.preparar();self.guardar();dev=self.archivo_con('dev.grafnet',sello.CLAVE_DESARROLLO)
        with patch.object(sello,'CLAVE',os.urandom(32)),patch.object(sello,'DESARROLLO',False):
            e2=self.abrir_limpio(dev);self.assertEqual(e2.contenedor.firma,'desarrollo');self.assertFalse(e2.puede_firmarse)
            self.assertIn('versión de desarrollo',w.l_firma.text());self.assertTrue(w.l_firma.isVisible())
            self.assertTrue(w.guardar_proyecto());self.assertFalse(self.con_sello(dev))
    def test_SGFN32_guardar_y_guardar_como_de_archivo_sin_firma_no_firman(self):
        """REQ-DAT-02: un archivo abierto sin firma sigue sin firma al guardarlo, con Guardar y con Guardar como."""
        w,e=self.preparar();self.guardar();sin=self.archivo_con('sin.grafnet',None);e2=self.abrir_limpio(sin)
        e2.ed.add_step('g','2');e2.cambia();self.assertTrue(w.guardar_proyecto())
        self.assertFalse(self.con_sello(sin));self.assertEqual(self.abrir_limpio(sin).contenedor.firma,'sin_firma')
        copia=self.guardar('copia.grafnet');self.assertFalse(self.con_sello(copia))
        self.assertEqual(self.abrir_limpio(copia).contenedor.firma,'sin_firma');self.assertTrue(w.l_firma.isVisible())
    def test_SGFN33_proyecto_nuevo_y_archivo_firmado_se_siguen_firmando(self):
        """REQ-DAT-02: un proyecto nuevo se firma al guardar y uno abierto con firma válida sigue firmado al guardarlo."""
        w,e=self.preparar();self.assertTrue(e.puede_firmarse);destino=self.guardar()
        self.assertTrue(self.con_sello(destino));self.assertEqual(e.contenedor.firma,'valida')
        e2=self.abrir_limpio(destino);self.assertEqual(e2.contenedor.firma,'valida')
        e2.ed.add_step('g','2');e2.cambia();self.assertTrue(w.guardar_proyecto())
        self.assertTrue(self.con_sello(destino));self.assertEqual(self.abrir_limpio(destino).contenedor.firma,'valida')
        self.guardar('otra.grafnet');self.assertTrue(self.con_sello(Path(self.tmp.name)/'otra.grafnet'))
    def test_SGFN34_archivo_manipulado_abre_sin_firma(self):
        """REQ-DAT-02: un archivo con el contenido cambiado sin re-sellar no se rechaza: abre como sin_firma."""
        w,e=self.preparar();destino=self.guardar();manipulado=Path(self.tmp.name)/'manipulado.grafnet'
        with zipfile.ZipFile(destino) as z:entradas={n:z.read(n) for n in z.namelist()}
        entradas[INFO]=entradas[INFO].replace(b'"autor": "',b'"autor": "Otro ')
        with zipfile.ZipFile(manipulado,'w') as z:
            for n,d in entradas.items():z.writestr(n,d)
        e2=self.abrir_limpio(manipulado);self.assertEqual(e2.contenedor.firma,'sin_firma');self.assertTrue(w.l_firma.isVisible())
