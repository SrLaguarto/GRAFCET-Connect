"""Navegación visual y operaciones de teclado, sin cambiar la semántica del modelo."""
import copy
import json
import unittest
from pathlib import Path
from test_editor_cadenas import BaseQt, QT
from grafcet.builder import M

if QT:
    from PySide6.QtCore import Qt, QPoint, QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.edicion import Edicion
    from escritorio.diagrama import REJILLA


@unittest.skipUnless(QT, 'requiere PySide6')
class NavegacionTeclado(BaseQt):
    def tearDown(self):
        self.w.hide()
        super().tearDown()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def preparar(self, otro=False):
        m = M().var('a').step('1', True).step('2').trans('t', ['1'], ['2'], 'a')
        e = Edicion.desde(m.doc, {'1': (100,80), 't': (100,180), '2': (100,280)}, 'Navegación')
        if otro:
            pid = e.ed.add_partial('Remoto')
            e.ed.add_step(pid, 'Lejana', True, at=(1500,200))
            e.cambia()
        w = self.w
        w._establecer_edicion(e); w._poner_modo(); w.refrescar_edicion(); w.resize(1366,768); w.show(); w.activateWindow()
        QApplication.processEvents(); w.diagrama.setFocus(); QApplication.processEvents()
        return w, e

    def tecla(self, widget, key, mods=None):
        QTest.keyClick(widget, key, mods if mods is not None else Qt.KeyboardModifier.NoModifier); QApplication.processEvents()

    def test_SNAV01_buscar_revela_encuadra_y_selecciona_sin_modificar(self):
        """REQ-EDT-12: Ctrl+F encuentra por nombre y revela un elemento de un parcial oculto sin editarlo."""
        w,e = self.preparar(True); n=w.navegacion
        original=copy.deepcopy(e.ed.model); presentacion=copy.deepcopy(e.ed.presentation)
        n.parcial.setCurrentIndex(1); n.modo.setCurrentIndex(1)
        self.tecla(w.diagrama, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        self.assertIs(QApplication.focusWidget(), n.buscar)
        QTest.keyClicks(n.buscar, 'Lejana'); self.tecla(n.buscar, Qt.Key.Key_Return)
        sid=next(s['id'] for s in e.M['steps'] if s['label']=='Lejana')
        self.assertEqual(e.sel,[sid]); self.assertIsNone(n.parcial.currentData())
        caja=next(d['caja'] for d in n.datos if d['id']==sid)
        self.assertTrue(w.diagrama.mapToScene(w.diagrama.viewport().rect()).boundingRect().contains(caja))
        self.assertEqual(e.ed.model,original); self.assertEqual(e.ed.presentation,presentacion)

    def test_SNAV02_filtro_informa_y_solo_afecta_a_la_vista(self):
        """REQ-EDT-12: ocultar o atenuar no cambia el modelo ni el estado que recibe la vista."""
        w,e=self.preparar(True); n=w.navegacion; estado={'situation':['1'], 'virtual':[]}
        w.diagrama.mostrar(e.M,estado)
        antes=copy.deepcopy(e.ed.model); n.parcial.setCurrentIndex(n.parcial.findData('g'))
        pid=n.parcial.currentData(); self.assertIsNotNone(pid)
        ajenos=[i for i in w.diagrama.scene().items() if i.data(42) and i.data(42)!=pid]
        self.assertTrue(ajenos); self.assertTrue(all(i.opacity()==.18 for i in ajenos))
        self.assertIn('atenuados',n.aviso.text()); n.modo.setCurrentIndex(1)
        self.assertTrue(all(not i.isVisible() for i in ajenos)); self.assertIn('ocultos',n.aviso.text())
        self.assertIn('se simula todo',n.aviso.text())
        self.assertEqual(w.diagrama._ultimo[1],estado); self.assertEqual(e.ed.model,antes)
        n.parcial.setCurrentIndex(0)
        self.assertTrue(all(i.isVisible() and i.opacity()==1 for i in ajenos))

    def test_SNAV03_busqueda_compacta_sin_minimapa(self):
        """REQ-EDT-12: Ctrl+F muestra la búsqueda en la cabecera, sin lista expandida ni minimapa."""
        w,e=self.preparar(True); n=w.navegacion
        self.assertTrue(n.isHidden()); self.assertFalse(hasattr(w.diagrama,'minimapa'))
        alto=w.diagrama.height()
        self.tecla(w.diagrama,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(n.isVisible()); self.assertLess(abs(w.diagrama.height()-alto),3)
        self.assertLessEqual(abs(n.mapTo(w,n.rect().topLeft()).y()-w.titulo.mapTo(w,w.titulo.rect().topLeft()).y()),12)
        QTest.keyClicks(n.buscar,'Lejana'); self.assertEqual(n.contador.text(),'1/1'); self.assertTrue(n.lista.isHidden())
        self.tecla(n.buscar,Qt.Key.Key_Escape); self.assertTrue(n.isHidden()); self.assertIs(QApplication.focusWidget(),w.diagrama)

    def test_SNAV06_siguiente_anterior_y_sin_resultados(self):
        """REQ-EDT-12: las flechas y el teclado recorren coincidencias repetidas con contador y sin cambiar el modelo."""
        w,e=self.preparar(True); n=w.navegacion; e.ed.rename('1','Lejana'); e.cambia()
        antes=copy.deepcopy(e.ed.model)
        self.tecla(w.diagrama,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(n.buscar,'Lejana'); self.assertEqual(n.contador.text(),'1/2'); primero=list(e.sel)
        self.tecla(n.buscar,Qt.Key.Key_Down); self.assertEqual(n.contador.text(),'2/2'); self.assertNotEqual(e.sel,primero)
        QTest.mouseClick(n.anterior,Qt.MouseButton.LeftButton); self.assertEqual(e.sel,primero)
        n.buscar.setFocus(); self.tecla(n.buscar,Qt.Key.Key_Return); self.assertEqual(n.contador.text(),'2/2')
        self.tecla(n.buscar,Qt.Key.Key_Return,Qt.KeyboardModifier.ShiftModifier); self.assertEqual(e.sel,primero)
        n.buscar.selectAll(); QTest.keyClicks(n.buscar,'No existe'); self.assertEqual(n.contador.text(),'0/0'); self.assertFalse(n.siguiente.isEnabled())
        self.assertEqual(e.ed.model,antes)

    def test_SNAV07_textos_de_atajos_y_menu_sin_seleccionar(self):
        """REQ-EDT-13: el menú muestra Ctrl+Enter y Supr y omite Seleccionar, sin perder los atajos reales."""
        from PySide6.QtWidgets import QMenu,QStyleOptionMenuItem
        w,e=self.preparar(); menu=next(a.menu() for a in w.menuBar().actions() if a.text()=='&Edición')
        self.assertFalse(any(a in menu.actions() for a in w.a_herr.values()))
        for accion,rotulo in ((w.a_borrar,'Supr'),(w.a_debajo,'Ctrl+Enter')):
            opcion=QStyleOptionMenuItem(); menu.initStyleOption(opcion,accion); self.assertEqual(opcion.text.split('\t')[-1],rotulo)

    def test_SNAV05_filtro_y_busqueda_con_simulacion_real(self):
        """REQ-EDT-12: la búsqueda y el filtro conservan la situación completa de una simulación real."""
        w,e=self.preparar(True)
        self.tecla(w.diagrama,Qt.Key.Key_F5); w.rt.stop()
        self.assertEqual(w.modo,'simular')
        antes=copy.deepcopy(w.v.state()); self.assertEqual(len(antes['situation']),2)
        n=w.navegacion; n.parcial.setCurrentIndex(n.parcial.findData('g')); n.modo.setCurrentIndex(1)
        self.tecla(w.diagrama,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(n.buscar,'Lejana'); self.tecla(n.buscar,Qt.Key.Key_Return)
        self.assertEqual(w.v.state(),antes)
        self.assertIsNone(n.parcial.currentData())
        self.assertTrue(w.diagrama.seleccion_navegacion)

    def test_SACC01_tab_inverso_esc_y_salida_sin_trampa(self):
        """REQ-EDT-13: Tab recorre elementos, Mayús+Tab vuelve y Ctrl+Tab sale hacia controles."""
        w,e=self.preparar(); v=w.diagrama
        e.seleccionar(['1']); v.setFocus()
        self.tecla(v,Qt.Key.Key_Tab); self.assertEqual(e.sel,['2'])
        self.tecla(v,Qt.Key.Key_Backtab,Qt.KeyboardModifier.ShiftModifier); self.assertEqual(e.sel,['1'])
        self.tecla(v,Qt.Key.Key_Escape); self.assertEqual(e.sel,[])
        self.tecla(v,Qt.Key.Key_Tab,Qt.KeyboardModifier.ControlModifier)
        self.assertIsNot(QApplication.focusWidget(),v)

    def test_SACC02_flecha_rejilla_deshacer_e_intro(self):
        """REQ-EDT-13: flechas mueven un paso con deshacer; Intro permite editar la etiqueta sin ratón."""
        w,e=self.preparar(); v=w.diagrama; e.seleccionar(['1']); v.setFocus()
        x=next(s['x'] for s in e.M['steps'] if s['id']=='1')
        self.tecla(v,Qt.Key.Key_Right)
        self.assertEqual(next(s['x'] for s in e.M['steps'] if s['id']=='1'),x+REJILLA)
        self.tecla(v,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(next(s['x'] for s in e.M['steps'] if s['id']=='1'),x)
        v.setFocus(); e.seleccionar(['1']); self.tecla(v,Qt.Key.Key_Return)
        self.assertIs(QApplication.focusWidget(),w.props.s_etiqueta)
        QTest.keyClicks(w.props.s_etiqueta,'Nuev'); self.tecla(w.props.s_etiqueta,Qt.Key.Key_Tab)
        self.assertEqual(next(s['label'] for s in e.M['steps'] if s['id']=='1'),'Nuev')

    def test_SACC03_supr_borra_y_respeta_el_campo_de_texto(self):
        """REQ-EDT-13: Supr en el dibujo borra; dentro de una etiqueta solo edita el texto."""
        w,e=self.preparar(); v=w.diagrama; e.seleccionar(['2']); v.setFocus()
        self.tecla(v,Qt.Key.Key_Return); w.props.s_etiqueta.selectAll()
        self.tecla(w.props.s_etiqueta,Qt.Key.Key_Delete)
        self.assertTrue(any(s['id']=='2' for s in e.M['steps']))
        w.props.s_etiqueta.setText('2'); self.tecla(w.props.s_etiqueta,Qt.Key.Key_Tab)
        v.setFocus(); e.confirmar_borrado=lambda plan: True; self.tecla(v,Qt.Key.Key_Delete)
        self.assertFalse(any(s['id']=='2' for s in e.M['steps']))
        self.tecla(v,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(any(s['id']=='2' for s in e.M['steps']))

    def test_SACC04_lista_textual_estados_relaciones_y_foco(self):
        """REQ-EDT-13: estados y relaciones se leen sin depender del color; botones y paneles tienen nombre."""
        w,e=self.preparar(); n=w.navegacion
        w.diagrama.mostrar(e.M,{'situation':['1'],'virtual':['2'],'forces':[{'target':'g'}]})
        n.abrir_opciones(); QApplication.processEvents(); QTest.mouseClick(n.b_lista,Qt.MouseButton.LeftButton)
        textos='\n'.join(n.lista.item(i).text() for i in range(n.lista.count()))
        for texto in ('inicial','activa','transitoria','parcial forzado','antes: 1','después: 2'):
            self.assertIn(texto,textos)
        for b in (n.anterior,n.siguiente,n.b_lista):
            self.assertTrue(b.accessibleName()); self.assertTrue(b.accessibleDescription())
        for panel in w._plegables.values(): self.assertTrue(panel.accessibleName())
        self.assertIn('dashed',w.styleSheet()); self.assertTrue(n.lista.accessibleName())

    def test_SACC05_crear_editar_simular_y_guardar_sin_raton(self):
        """REQ-EDT-13, T-26a: creación enlazada, propiedades, validación al Play, Stop y guardar mediante teclado."""
        from unittest.mock import patch
        w,e=self.preparar(); e.ed.dirty=False
        self.tecla(w.diagrama,Qt.Key.Key_N,Qt.KeyboardModifier.ControlModifier)
        e=w.edicion
        self.tecla(w,Qt.Key.Key_E,Qt.KeyboardModifier.AltModifier)
        menu=QApplication.activePopupWidget(); self.assertIsNotNone(menu)
        self.tecla(menu,Qt.Key.Key_E)
        submenu=QApplication.activePopupWidget(); self.assertIsNotNone(submenu)
        self.tecla(submenu,Qt.Key.Key_I)
        self.assertEqual(len(e.M['steps']),1); self.assertTrue(e.M['steps'][0]['initial'])
        self.tecla(w.diagrama,Qt.Key.Key_Return,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(e.M['steps']),2); self.assertEqual(len(e.M['transitions']),1)
        t=e.M['transitions'][0]
        self.assertTrue(t['pre']); self.assertTrue(t['post'])
        self.tecla(w.diagrama,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(w.navegacion.buscar,t['label']); self.tecla(w.navegacion.buscar,Qt.Key.Key_Return); self.tecla(w.navegacion.buscar,Qt.Key.Key_Escape)
        self.tecla(w.diagrama,Qt.Key.Key_Return)
        self.assertFalse(hasattr(w.props,'t_manual'))
        w.props._desde_bloques('1')
        self.assertFalse([d for d in e.diagnosticos() if d['blocks']])
        self.tecla(w.diagrama,Qt.Key.Key_F5); self.assertEqual(w.modo,'simular')
        self.tecla(w.diagrama,Qt.Key.Key_F5); self.assertEqual(w.modo,'editar')
        destino=Path(self.tmp.name)/'Teclado.grafnet'
        with patch('escritorio.archivos.QFileDialog.getSaveFileName',return_value=(str(destino),'')):
            self.tecla(w.diagrama,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(destino.is_file()); self.assertFalse(e.ed.dirty)

    def test_SACC06_conectar_desde_menu_con_destino_por_teclado(self):
        """REQ-EDT-13: Ctrl+K permite enlazar elementos existentes sin gesto de ratón."""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QComboBox
        w,e=self.preparar()
        sid=e.ed.add_step('g','3',at=(700,280)); e.ed.disconnect('t','2'); e.cambia(); e.seleccionar(['t']); w.diagrama.setFocus()
        def elegir():
            dialogo=QApplication.activeModalWidget()
            combo=dialogo.findChild(QComboBox)
            QTest.keyClick(combo,Qt.Key.Key_End)
            QTest.keyClick(dialogo,Qt.Key.Key_Return)
        QTimer.singleShot(20,elegir)
        self.tecla(w,Qt.Key.Key_K,Qt.KeyboardModifier.ControlModifier)  # Ctrl+K (P-IMP-104)
        self.assertIn(sid,e.M['transitions'][0]['post'])
        self.assertIs(QApplication.focusWidget(),w.diagrama)

    def test_SACC07_movimiento_multiple_y_vista_vacia_sin_trampa(self):
        """REQ-EDT-13: las flechas desplazan toda la selección en una operación; Tab sale de un dibujo vacío."""
        w,e=self.preparar(); e.seleccionar(['1','2']); w.diagrama.setFocus()
        antes={s['id']:s['x'] for s in e.M['steps']}
        self.tecla(w.diagrama,Qt.Key.Key_Right)
        self.assertEqual({s['id']:s['x'] for s in e.M['steps']},{i:x+REJILLA for i,x in antes.items()})
        self.tecla(w.diagrama,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual({s['id']:s['x'] for s in e.M['steps']},antes)
        e.ed.dirty=False; self.tecla(w.diagrama,Qt.Key.Key_N,Qt.KeyboardModifier.ControlModifier)
        w.diagrama.setFocus(); self.tecla(w.diagrama,Qt.Key.Key_Tab)
        self.assertIsNot(QApplication.focusWidget(),w.diagrama)


@unittest.skipUnless(QT,'requiere PySide6')
class FiltroWeb(unittest.TestCase):
    def test_SNAV04_filtro_web_como_qt(self):
        """REQ-EDT-12: el renderizador web etiqueta los parciales y oculta/atenúa solo el resto, con aviso."""
        try:
            from PySide6.QtQml import QJSEngine
        except ImportError:
            self.skipTest('requiere QtQml para ejecutar el renderizador web')
        from test_dibujo_vista import MOCK_DOM, ROOT
        app=QApplication.instance() or QApplication([])
        e=Edicion.desde(M().step('1',True).doc,{'1':(100,100)},'Filtro')
        pid=e.ed.add_partial('Otro'); e.ed.add_step(pid,'2',True,at=(500,100)); e.cambia()
        fuente=(ROOT/'tools/dibujo.js').read_text(encoding='utf-8').replace('{x, y, ...attrs}','Object.assign({x, y}, attrs)')
        extension="""
        MockEl.prototype.getAttribute=function(k){return this.attrs[k];};
        MockEl.prototype.querySelectorAll=function(s){var r=[];this.children.forEach(function(c){if(c.attrs['data-parcial'])r.push(c);r=r.concat(c.querySelectorAll(s));});return r;};
        var crear=document.createElementNS;document.createElementNS=function(ns,t){var e=crear(ns,t);e.style={};return e;};
        """
        for modo in ('ocultar','atenuar'):
            js=QJSEngine(); r=js.evaluate(MOCK_DOM+extension+fuente)
            self.assertFalse(r.isError(),r.toString())
            r=js.evaluate("var svg=new MockEl('svg');drawDiagram(svg,%s,{},%s);JSON.stringify(svg.querySelectorAll('[data-parcial]').map(function(e){return [e.attrs['data-parcial'],e.style];}));" % (json.dumps(e.M),json.dumps({'parcial':'g','filtro':modo})))
            self.assertFalse(r.isError(),r.toString()); datos=json.loads(r.toString())
            ajenos=[s for p,s in datos if p==pid]; propios=[s for p,s in datos if p=='g']
            self.assertTrue(ajenos); self.assertTrue(propios)
            self.assertTrue(all(s.get('display')=='none' if modo=='ocultar' else float(s.get('opacity',1))==.18 for s in ajenos))
            self.assertTrue(all(not s for s in propios))
            self.assertIn('se simula todo',js.evaluate('svg.textContent').toString())
