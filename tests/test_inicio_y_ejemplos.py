"""Inicio limpio, bloques con Supr, ejemplos de consulta y asignación de variables nuevas."""
import copy
import unittest
from unittest.mock import patch
from test_editor_cadenas import BaseQt, QT
from grafcet.ejemplos_aula import DIDACTICOS
from grafcet.view import Vista
from grafcet.profile import normalize_options
from conexion.configuracion import CANALES_INICIALES

if QT:
    from PySide6.QtCore import Qt,QEvent,QPointF
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest


class EjemplosAula(unittest.TestCase):
    def test_SIEJ01_siete_ejemplos_compilan_con_entradas_y_salidas(self):
        """REQ-SIM-01, REQ-JER-04: los siete ejemplos tienen entradas, salidas y posiciones, y arrancan sin diagnósticos."""
        self.assertEqual(len(DIDACTICOS),7)
        for clave,(titulo,ayuda,crear) in DIDACTICOS.items():
            with self.subTest(clave=clave):
                v=Vista(clave,titulo,ayuda,crear,normalize_options(None))
                self.assertTrue(v.model['compilable'],v.state().get('diagnostics'))
                self.assertEqual(v.state()['status'],'pausada-estable')
                self.assertTrue(v.doc['transitions'])
                self.assertTrue(any(x['role']=='input' for x in v.doc['variables']))
                self.assertTrue(any(x['role']=='output' for x in v.doc['variables']))
                self.assertFalse(v.state().get('diagnostics'))

    def test_SIEJ06_evoluciones_de_los_siete_ejemplos(self):
        """REQ-SIM-01, REQ-TMP-01, REQ-JER-04: cada ejemplo responde a sus entradas y alcanza la salida descrita."""
        casos={
            'aula_marcha':([{'marcha':True},{'marcha':False,'paro':True}],{'0'}),
            'aula_eleccion':([{'izquierda':True},{'izquierda':False,'fin':True}],{'0'}),
            'aula_simultaneidad':([{'marcha':True},{'marcha':False,'fin_izq':True},{'fin_der':True}],{'0'}),
            'aula_macro':([{'marcha':True},{'marcha':False,'fin':True}],{'0'}),
            'aula_encapsulada':([{'marcha':True},{'marcha':False,'fin':True},{'paro':True}],{'0'}),
            'aula_temporizacion':([{'marcha':True},3000000],{'E2'}),
            'aula_repeticion':([{'marcha':True},{'marcha':False,'avance':True},{'avance':False,'repetir':True}],{'1'}),
        }
        for clave,(pasos,final) in casos.items():
            with self.subTest(clave=clave):
                titulo,ayuda,crear=DIDACTICOS[clave];v=Vista(clave,titulo,ayuda,crear,normalize_options(None))
                for paso in pasos:
                    v.act('avanzar',{'us':paso}) if isinstance(paso,int) else v.act('fijar',{'cambios':paso})
                self.assertEqual(set(v.state()['situation']),final)
                self.assertFalse(v.state().get('diagnostics'))


@unittest.skipUnless(QT,'requiere PySide6')
class InicioInterfaz(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SIEJ02_inicio_vacio_paneles_y_cabecera_en_una_fila(self):
        """REQ-EDT-09: el inicio es un proyecto vacío con laterales abiertos y propiedades plegadas; ayuda junto al título."""
        w=self.w;w.resize(1366,768);w.show();QApplication.processEvents()
        self.assertFalse(w.edicion.M['steps']);self.assertFalse(w.edicion.ed.dirty)
        self.assertTrue(w._plegables['izquierdo'].abierto);self.assertTrue(w._plegables['derecho'].abierto)
        self.assertFalse(w._plegables['inferior'].abierto)
        self.assertAlmostEqual(w._plegables['derecho'].width(),w.ancho_derecho,delta=2)
        self.assertLess(abs(w.ayuda.mapTo(w, w.ayuda.rect().center()).y()
                            - w.favoritos.mapTo(w, w.favoritos.rect().center()).y()), 4)
        self.assertGreater(w.ayuda.mapTo(w, w.ayuda.rect().topLeft()).x(),
                           w.favoritos.mapTo(w, w.favoritos.rect().topRight()).x())

    def test_SIEJ03_ejemplo_solo_lectura_incluso_tras_play_stop(self):
        """REQ-EDT-05, REQ-SIM-01: los ejemplos permiten simular e imprimir, sin editar ni guardar copias editables."""
        w=self.w;w.cargar_ejemplo('aula_marcha');w.show();QApplication.processEvents()
        original=copy.deepcopy((w.edicion.ed.model,w.edicion.ed.presentation))
        for tecla,mod in ((Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier),(Qt.Key.Key_Return,Qt.KeyboardModifier.ControlModifier),(Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier)):
            w.diagrama.setFocus();QTest.keyClick(w.diagrama,tecla,mod)
        self.assertTrue(w.solo_lectura);self.assertIsNone(w.diagrama.controlador)
        self.assertFalse(w.a_guardar.isEnabled());self.assertFalse(w.a_guardar_como.isEnabled());self.assertFalse(w.guardar_como())
        with patch('escritorio.laminas.DocumentoLaminas.imprimir') as imprimir:
            w.abrir_laminas('imprimir');imprimir.assert_called_once()
        for _ in range(2):
            QTest.keyClick(w.diagrama,Qt.Key.Key_F5);QApplication.processEvents()
        self.assertTrue(w.solo_lectura);self.assertIsNone(w.diagrama.controlador)
        self.assertEqual((w.edicion.ed.model,w.edicion.ed.presentation),original)
        w.nuevo();self.assertFalse(w.solo_lectura);self.assertIs(w.diagrama.controlador,w.edicion)

    def test_SIEJ04_autoasignar_nuevas_respetando_mapa_y_memorias(self):
        """REQ-EDT-07: las nuevas E/S ocupan el primer canal libre compatible; no se asignan memorias ni se pisa un canal."""
        w=self.w;e=w.edicion
        self.assertEqual({k:v['cantidad'] for k,v in CANALES_INICIALES.items()},{'discrete':32,'coil':32,'input-register':12,'holding':12})
        for nombre,papel,tipo in (('a','input',None),('b','input',None),('motor','output',None),('n','internal',None),('nivel','input',{'kind':'decimal','scale':2})):
            self.assertIsNone(e.nueva_variable(nombre,papel,tipo))
        mapa={next(v['name'] for v in e.ed.model['variables'] if v['id']==s.variable):(s.area,s.direccion) for s in w.panel_es.config.senales}
        self.assertEqual(mapa,{'a':('discrete',0),'b':('discrete',1),'motor':('coil',0),'nivel':('input-register',0)})
        a=next(v['id'] for v in e.ed.model['variables'] if v['name']=='a')
        w.panel_es.asignar(a,'discrete',5);e.nueva_variable('c','input')
        mapa={s.variable:s.direccion for s in w.panel_es.config.senales if s.area=='discrete'}
        self.assertEqual(mapa[a],5)
        c=next(v['id'] for v in e.ed.model['variables'] if v['name']=='c');self.assertEqual(mapa[c],0)

    def test_SIEJ05_supr_bloque_no_borra_la_etapa(self):
        """REQ-EDT-13: Supr elimina el bloque seleccionado, conservando el resto del árbol y el elemento GRAFCET."""
        from escritorio.bloques import AreaBloques,texto_a_arbol
        from PySide6.QtWidgets import QVBoxLayout,QWidget
        w=self.w;e=w.edicion
        sid=e.ed.add_step('g','1',True);e.cambia();e.seleccionar([sid])
        area=AreaBloques(lambda:({'a':('input','bool'),'b':('input','bool')},[]))
        contenedor=QWidget(w);QVBoxLayout(contenedor).addWidget(area);contenedor.resize(400,100);contenedor.show()
        area.poner_arbol(texto_a_arbol('a AND b',{'a':('input','bool'),'b':('input','bool')},[]));area._calcular(400)
        ruta=next(ruta for rect,ruta,n in area._bloques if n and n.get('k')=='y')
        rect=next(rect for rect,r,n in area._bloques if r==ruta)
        p=QPointF(rect.left()+3,rect.center().y()).toPoint()
        QTest.mouseClick(area,Qt.MouseButton.LeftButton,pos=p);QTest.keyClick(area,Qt.Key.Key_Delete)
        self.assertIsNone(area.arbol);self.assertTrue(any(s['id']==sid for s in e.M['steps']))
        contenedor.deleteLater()

    def test_SIEJ07_autoasignacion_no_pisa_si_no_hay_capacidad(self):
        """REQ-EDT-07: agotar canales deja la nueva variable sin asignar, con aviso, y conserva las existentes."""
        w=self.w;e=w.edicion;e.nueva_variable('a','input')
        w.panel_es.cantidades['discrete'].setValue(1)
        antes=copy.deepcopy(w.panel_es.config.senales)
        e.nueva_variable('b','input')
        self.assertEqual(w.panel_es.config.senales,antes);self.assertIn('b',w.statusBar().currentMessage())

    def test_SIEJ08_autoasignacion_inmediata_con_conexion_activa(self):
        """REQ-EDT-07: conectado se publica la variable y se solicita el mapa nuevo sin esperar a desconectar."""
        from conexion.adaptador import MonitorEntradas
        w=self.w;e=w.edicion
        w.modbus.estado='conectado';w.modbus.adaptador=MonitorEntradas(w.panel_es.config,e.ed.model)
        with patch.object(w.modbus,'reasignar') as reasignar:
            e.nueva_variable('a','input')
            self.assertEqual(len(w.panel_es.config.senales),1)
            self.assertTrue(reasignar.called)
        w.modbus.estado='desconectado'
        self.assertFalse(w._auto_es_pendientes)
