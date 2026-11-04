"""Mapa en vivo, contactos NC, pie E/S y selección de acciones pendientes."""
import copy
import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch
from conexion.configuracion import Configuracion, Senal, CANALES_INICIALES
from conexion.coordinador import Coordinador
from conexion.adaptador import MonitorEntradas
from grafcet.builder import M
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import Qt, QTimer, QEvent, QPoint
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtTest import QTest


class MapaVivo(unittest.TestCase):
    def test_SMAP01_cero_anterior_antes_de_publicar_mapa_sin_cerrar_tcp(self):
        """REQ-SIM-03: las peticiones en vuelo terminan con su mapa; se confirma cero antes de sustituirlo."""
        doc=M().var('motor','output').step('0',True).doc
        anterior=Configuracion(modelo=doc['id'],senales=[Senal('motor','coil',0)])
        nuevo=copy.deepcopy(anterior);nuevo.senales[0].direccion=3
        c=Coordinador();escrituras=[]
        class Cliente:
            def escribir_coils(self,inicio,valores):escrituras.append((inicio,list(valores)))
            def cerrar(self):pass
        c.cliente=Cliente();c.estado='conectado';c.adaptador=MonitorEntradas(anterior,doc)
        c._enviar('leer',lambda:{})
        c.futuro.result()
        try:
            c.reasignar(nuevo,doc)
            self.assertEqual(c.adaptador.config.senales[0].direccion,0)
            c.tick(False);self.assertEqual(c.fase,'mapa')
            c.futuro.result();self.assertEqual(escrituras,[(0,[False]),(3,[False])])
            self.assertEqual(c.adaptador.config.senales[0].direccion,0)
            c.tick(False)
            self.assertEqual(c.adaptador.config.senales[0].direccion,3)
            self.assertEqual(c.estado,'conectado')
            vacio=copy.deepcopy(nuevo);vacio.senales=[]
            c.reasignar(vacio,doc)
            for _ in range(8):
                if c.futuro:c.futuro.result()
                c.tick(False)
                if not c._mapa_pendiente and c.fase!='mapa':break
            self.assertFalse(c.adaptador.config.senales)
            self.assertIn((3,[False]),escrituras)
        finally:c.cerrar()


    def test_SMAP11_play_invalida_un_mapa_en_vuelo_sin_resucitar_monitor(self):
        """REQ-SIM-03: una respuesta antigua de reasignación no reemplaza la sesión nueva de Play."""
        from helpers import session
        m=M().var('motor','output').step('0',True);cfg=Configuracion(senales=[Senal('motor','coil',0)])
        c=Coordinador();c.estado='conectado';c.adaptador=MonitorEntradas(cfg,m.doc)
        class Cliente:
            def escribir_coils(self,*args):pass
            def cerrar(self):pass
        c.cliente=Cliente()
        try:
            c.reasignar(cfg,m.doc);c.tick(False);c.futuro.result()
            nueva=session(m.compile());c.vincular(nueva,cfg,m.doc);c.tick(True)
            self.assertIs(c.adaptador.sesion,nueva)
        finally:c.cerrar()


@unittest.skipUnless(QT,'requiere PySide6')
class InterfazMapaVivo(BaseQt):
    def activar(self):
        from conexion.adaptador import MonitorEntradas
        w=self.w;w.modbus.estado='conectado'
        w.modbus.adaptador=MonitorEntradas(copy.deepcopy(w.panel_es.config),w.edicion.ed.model)
        w.panel_es.ocupado(True)
        return w

    def tearDown(self):
        self.w.modbus.estado='desconectado'
        super().tearDown()

    def test_SMAP02_altas_renombres_bajas_y_arrastre_conectado(self):
        """REQ-EDT-07, REQ-SIM-03: las variables y el mapa cambian en vivo conservando la asignación al renombrar."""
        w=self.activar();e=w.edicion;p=w.panel_es
        with patch.object(w.modbus,'reasignar') as cambiar:
            e.nueva_variable('a','input');e.nueva_variable('motor','output');e.nueva_variable('mem','internal')
            self.assertEqual({v['name'] for v in p.variables},{'a','motor'})
            self.assertEqual(len(p.config.senales),2)
            self.assertTrue(p.lista_entradas.dragEnabled())
            motor=next(v['id'] for v in e.ed.model['variables'] if v['name']=='motor')
            self.assertTrue(p.asignar(motor,'coil',4))
            p.quitar(motor);self.assertFalse(any(s.variable==motor for s in p.config.senales))
            self.assertTrue(cambiar.called)
            a=next(v['id'] for v in e.ed.model['variables'] if v['name']=='a')
            e.ed.rename(a,'sensor');e.cambia()
            self.assertIn('sensor',{v['name'] for v in p.variables})
            self.assertEqual(next(s.direccion for s in p.config.senales if s.variable==a),0)
            e.ed.delete_variable(a);e.cambia()
            self.assertNotIn(a,{v['id'] for v in p.variables})
            self.assertFalse(any(s.variable==a for s in p.config.senales))

    def test_SMAP03_cantidades_cero_y_restablecer_sin_pisar_asignaciones(self):
        """REQ-SIM-03: cero canales es válido; restablecer propone 32/12 y conserva direcciones ocupadas."""
        p=self.w.panel_es
        self.assertEqual([x['cantidad'] for x in CANALES_INICIALES.values()],[32,32,12,12])
        for c in p.cantidades.values():c.setValue(0)
        self.assertTrue(all(x['cantidad']==0 for x in p.obtener().canales.values()))
        self.assertFalse(p.terminales)
        p.restablecer_canales()
        self.assertEqual(p.obtener().canales,CANALES_INICIALES)

    def test_SMAP04_ayuda_siempre_en_pie_y_nunca_ventana(self):
        """REQ-EDT-09, REQ-ROB-01: quitar asignaciones y cambiar de vista no crea una ventana de ayuda."""
        w=self.w;e=w.edicion;e.nueva_variable('a','input');w.resize(1366,768);w.show();w.mostrar_es()
        p=w.panel_es;a=e.ed.model['variables'][0]['id'];p.quitar(a);QApplication.processEvents()
        ayuda=p.ayuda_vacio
        self.assertEqual(ayuda.parentWidget().objectName(),'pieES');self.assertFalse(ayuda.isWindow())
        self.assertTrue(ayuda.isVisible());w._mostrar_pagina(False);QApplication.processEvents()
        self.assertFalse(ayuda.isVisible())
        self.assertNotIn(ayuda,QApplication.topLevelWidgets())

    def test_SMAP05_cadena_para_plano_incluye_accion_interrogante(self):
        """REQ-EDT-11: traer una cadena conserva su acción pendiente y su diagnóstico sin exigir compilar."""
        from escritorio.hojas import SeleccionParaHoja, dibujo_vinculado
        w=self.w;e=w.edicion;sid=e.ed.add_step('g','1',True,at=(100,100))
        aid=e.ed.add_draft_action((160,100),{'etapa':sid});e.cambia()
        selector=SeleccionParaHoja(e)
        refs=selector._cadena(sid);self.assertIn(aid,refs)
        dibujo=dibujo_vinculado(e,refs)
        self.assertIn(aid,[a['id'] for a in dibujo['draftActions']])
        self.assertTrue(any(d['blocks'] for d in e.diagnosticos()))
        from escritorio.laminas import DocumentoLaminas
        doc=DocumentoLaminas(dibujo,{},e.ed.sheet_settings())
        from PySide6.QtWidgets import QGraphicsTextItem
        self.assertTrue(any('?' in x.toPlainText() for x in doc.escena.items() if isinstance(x,QGraphicsTextItem)))

    def test_SMAP06_conectar_correcto_error_y_desconexion_conservan_es(self):
        """REQ-SIM-03: iniciar desde E/S, incluso con Play previo, no cambia la pestaña ni al fallar."""
        w=self.w;e=w.edicion;e.ed.add_step('g','1',True);e.cambia()
        w.a_ejecutar.setChecked(True);w.rt.stop();w.mostrar_es()
        for error in (None,ValueError('rechazada'),RuntimeError('timeout')):
            with patch.object(w.modbus,'iniciar',side_effect=error):
                w._conectar_modbus();w.rt.stop()
                self.assertEqual(w.paginas_es.currentIndex(),1)
        with patch.object(w.modbus,'desconectar'):w._desconectar_modbus();w.rt.stop()
        self.assertEqual(w.paginas_es.currentIndex(),1)

    def test_SMAP07_contacto_nc_menu_presion_y_suelta(self):
        """REQ-SIM-02: el menú NC invierte reposo y pulsación, produciendo dos cambios reales."""
        w=self.w;e=w.edicion;e.nueva_variable('p','input');p=e.ed.model['variables'][0]['id']
        a=e.ed.add_step('g','1',True);fin=e.ed.add_step('g','2')
        e.ed.add_transition('g','p',pre=[a],post=[fin]);e.ed.add_transition('g','NOT p',pre=[fin],post=[a])
        e.cambia();w.show();w.a_ejecutar.setChecked(True);w.rt.stop()
        b=w.botones[p]
        def elegir():
            menu=QApplication.activePopupWidget()
            next(a for a in menu.actions() if a.text()=='Normalmente cerrado (NC)').trigger();menu.close()
        QTimer.singleShot(0,elegir)
        QApplication.sendEvent(b,QContextMenuEvent(QContextMenuEvent.Reason.Mouse,b.rect().center(),b.mapToGlobal(b.rect().center())))
        self.assertTrue(w.v.state()['values'][p]);self.assertEqual(w.v.state()['situation'],[fin])
        QTest.mousePress(b,Qt.MouseButton.LeftButton);self.assertFalse(w.v.state()['values'][p]);self.assertEqual(w.v.state()['situation'],[a])
        QTest.mouseRelease(b,Qt.MouseButton.LeftButton);self.assertTrue(w.v.state()['values'][p])
        QTest.mouseClick(b,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(w.v.state()['values'][p]);self.assertTrue(b.enclavado)
        QTest.mouseClick(b,Qt.MouseButton.LeftButton);self.assertTrue(w.v.state()['values'][p])
        w.a_ejecutar.setChecked(False);w.a_ejecutar.setChecked(True);w.rt.stop()
        self.assertTrue(w.v.state()['values'][p])

    def test_SMAP08_red_correcta_rechazada_timeout_y_caida_no_cambian_pagina(self):
        """REQ-SIM-03: los resultados asíncronos de red conservan E/S, también con error o caída."""
        w=self.w;original=w.modbus;w.mostrar_es()
        class Cliente:
            def __init__(self,host,puerto,unidad,timeout):self.host,self.puerto,self.unidad=host,puerto,unidad
            def conectar(self):
                if fallo:raise fallo
            def cerrar(self):pass
        try:
            for fallo in (None,ConnectionRefusedError('rechazada'),TimeoutError('timeout')):
                w.modbus=Coordinador()
                with patch('conexion.coordinador.ClienteModbus',Cliente):w._conectar_modbus()
                w.rt.stop()
                limite=time.monotonic()+2
                while w.modbus.estado=='conectando' and time.monotonic()<limite:
                    w._tick();QApplication.processEvents();time.sleep(.001)
                self.assertEqual(w.modbus.estado,'error' if fallo else 'conectado')
                self.assertEqual(w.paginas_es.currentIndex(),1)
                if fallo is None:
                    if w.modbus.futuro:w.modbus.futuro.result();w._tick()
                    if w.modbus.futuro:w.modbus.futuro.result();w._tick()
                    # Una respuesta de lectura falla después de haberse conectado.
                    while w.modbus.futuro:
                        w.modbus.futuro.result();w.modbus.proxima=time.perf_counter()+1;w._tick()
                    def caer():raise ConnectionResetError('caída')
                    w.modbus._enviar('leer',caer)
                    try:w.modbus.futuro.result()
                    except ConnectionResetError:pass
                    w._tick();self.assertEqual(w.modbus.estado,'error')
                    self.assertEqual(w.paginas_es.currentIndex(),1)
                w.modbus.cerrar()
        finally:w.modbus=original;w.rt.stop()

