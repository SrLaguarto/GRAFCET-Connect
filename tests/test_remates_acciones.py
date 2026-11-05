"""Regresiones de gestos, acciones, flancos y bloques Modbus."""
import unittest
from unittest import mock
from conexion.adaptador import leer_entradas, escribir_salidas, _bloques
from conexion.configuracion import Configuracion, Senal
from grafcet.editor import Editor, new_grafcet_document
from grafcet.view import norm
from test_editor_cadenas import BaseQt, QT
from test_dibujo_vista import vista, dibujo, texto
from grafcet.builder import M
if QT:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.diagrama import posiciones, COL
    from test_verdad_visual import colores


class RematesNucleo(unittest.TestCase):
    def test_SCOR01_copiar_continua_sola_conserva_tipo(self):
        """REQ-EDT-04: una continua copiada sola no adquiere una condición literal."""
        ed = Editor(new_grafcet_document('m'))
        v = ed.add_variable('motor','output',{'kind':'bool'})
        s = ed.add_step('g','0',True)
        a = ed.add_continuous_action(s,v)
        frag = ed.copy([a])
        self.assertEqual(frag.presentation['draftActions'][0]['tipo'],'continua')
        self.assertEqual(frag.presentation['draftActions'][0]['condicion'],'')
        ed.paste(frag,'g')
        self.assertEqual(ed.draft_actions()[0]['tipo'],'continua')
        ed.undo();self.assertEqual(ed.draft_actions(),[])
        cond = ed.add_continuous_action(s,v,'false')
        self.assertEqual(ed.copy([cond]).presentation['draftActions'][0]['tipo'],'condicionada')

    def test_SCOR02_bloques_sin_huecos_y_limites(self):
        """REQ-SIM-03: bloques contiguos limitados, sin escribir canales no asignados."""
        senales = [Senal('b','coil',1),Senal('a','coil',0),Senal('d','coil',3),Senal('r','holding',0,'UINT16')]
        cliente = mock.Mock()
        escribir_salidas(cliente,senales,{'a':True,'b':True,'d':False,'r':123})
        self.assertEqual(cliente.escribir_coils.call_args_list,[mock.call(0,[True,True]),mock.call(3,[False])])
        cliente.escribir_registros.assert_called_once_with(0,[123])
        limite = [Senal(str(i),'coil',i) for i in range(1970)]
        self.assertEqual([len(b) for b in _bloques(limite,1968,123)],[1968,2])
        limite = [Senal(str(i),'holding',i,'UINT16') for i in range(124)]
        self.assertEqual([len(b) for b in _bloques(limite,1968,123)],[123,1])

    def test_SCOR03_lectura_completa_en_bloque(self):
        """REQ-SIM-03, REQ-ROB-01: una lectura por bloque; una respuesta incompleta no se publica."""
        cliente = mock.Mock();cliente.leer_bits.return_value=[True,False,True]
        senales=[Senal(str(i),'discrete',i) for i in range(3)]
        self.assertEqual(leer_entradas(cliente,senales),{'0':True,'1':False,'2':True})
        cliente.leer_bits.assert_called_once_with(0,3,entradas=True)
        cliente.leer_bits.return_value=[True]
        with self.assertRaisesRegex(ValueError,'incompleta'):leer_entradas(cliente,senales)
        self.assertEqual(Configuracion().host,'192.168.1.133')

    def test_SCOR04_flanco_colorea_su_operando_segun_evento(self):
        """REQ-SIM-03: todo el texto de un flanco usa su valor, no el nivel de la variable."""
        for op in ('rise','fall'):
            m={'operator':op,'operands':[{'operator':'ref','reference':'p'}]}
            for s in norm(m,key='e'):
                self.assertEqual(s['eval'],['e'])  # raíz del flanco, nunca e.0

    def test_SCOR10_escritura_tcp_conjunta_sin_estado_intermedio(self):
        """REQ-SIM-03: dos actuadores activos se publican juntos, sin pulsos entre peticiones."""
        from test_modbus import servidor
        estados=[]
        planta=[False,False]
        def responder(p):
            self.assertEqual(p[0],15)
            direccion=int.from_bytes(p[1:3],'big');cantidad=int.from_bytes(p[3:5],'big')
            for i in range(cantidad):planta[direccion+i]=bool((p[6+i//8]>>(i%8))&1)
            estados.append(tuple(planta))
            return p[:5]
        senales=[Senal('cinta','coil',0),Senal('transferidor','coil',1)]
        with servidor(responder) as cliente:
            for _ in range(5):escribir_salidas(cliente,senales,{'cinta':True,'transferidor':True})
            escribir_salidas(cliente,senales,{'cinta':False,'transferidor':False})
        self.assertEqual(estados,[(True,True)]*5+[(False,False)])


@unittest.skipUnless(QT,'Falta PySide6')
class RematesQt(BaseQt):
    def preparar(self):
        w,e=self.vacio();s=e.poner_etapa(QPointF(200,100),inicial=True)
        e.pedir_accion=lambda *args:None
        e.nueva_variable('motor','output',{'kind':'bool'})
        w.resize(1366,768);w.show();QApplication.processEvents()
        return w,e,s

    def test_SCOR05_arrastre_real_crea_continua_deshacer(self):
        """REQ-ACT-01, REQ-EDT-02, REQ-EDT-05: arrastre derecho crea una continua en una operación."""
        w,e,s=self.preparar();n=len(e.ed.undo_stack)
        x,y=posiciones(e.M)[s];ini=QPointF(x+22,y);fin=ini+QPointF(120,0)
        view=w.diagrama;view._manual=True;view.resetTransform();view.setSceneRect(0,0,1000,600)
        view.centerOn(400,220);QApplication.processEvents()
        QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=view.mapFromScene(ini))
        QTest.mouseMove(view.viewport(),view.mapFromScene(fin),20)
        QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=view.mapFromScene(fin))
        QApplication.processEvents()
        self.assertEqual(len(e.ed.undo_stack),n+1)
        d=e.ed.draft_actions()[0];self.assertEqual((d['tipo'],d['etapa']),('continua',s))
        self.assertEqual(e.accion,d['id'])
        e.deshacer();self.assertEqual(e.ed.draft_actions(),[])
        e.rehacer();self.assertEqual(e.ed.draft_actions()[0]['id'],d['id'])

    def test_SCOR06_accion_sola_y_etapa_con_accion(self):
        """REQ-EDT-04: selección de acción distinta de seleccionar la etapa con su acción."""
        w,e,s=self.preparar();e.poner_accion(s,{'tipo':'continua','variable':'motor'});e.cambia()
        a=e.acciones(s)[0]['id'];c=e._colocadas()[0]['rect'];p=QPointF(c[0]+c[2]/2,c[1]+c[3]/2)
        e.prensar(p);e.soltar(p)
        self.assertNotIn(s,e.seleccion_dibujo());self.assertIn('accion:'+a,e.seleccion_dibujo())
        f=e.copiar_fragmento();self.assertEqual(f.entities['steps'],[])
        self.assertEqual(f.presentation['draftActions'][0]['condicion'],'')
        self.assertTrue(e.pegar_fragmento(f,QPointF(700,400)))
        self.assertEqual(len(e.ed.model['steps']),1)
        self.assertEqual(e._datos_borrador(e.ed.draft_actions()[0])['tipo'],'continua')
        e.deshacer();e.seleccionar([s])
        class Mayus:
            def modifiers(self):return Qt.KeyboardModifier.ShiftModifier
        e.prensar(p,Mayus());e.soltar(p)
        f=e.copiar_fragmento();self.assertEqual([x['id'] for x in f.entities['steps']],[s])
        self.assertEqual([x['id'] for x in f.entities['actions']],[a])
        self.assertTrue(e.pegar_fragmento(f,QPointF(700,400)))
        self.assertEqual(len(e.ed.model['steps']),2)
        self.assertEqual(len(e.ed.model['actions']),2)
        e.deshacer();self.assertEqual(len(e.ed.model['steps']),1)

    def test_SCOR07_selector_no_se_comprime_por_el_estilo(self):
        """REQ-EDT-02: el estilo general no comprime el selector dibujado como una acción."""
        w,e,s=self.preparar();d=e.anadir_accion(s);w.editar_accion(s,d);QApplication.processEvents()
        self.assertGreaterEqual(w.props.accion.variable.height(),62)
        self.assertGreaterEqual(w._minimo_panel('inferior'),w.props.layout().totalHeightForWidth(w.props.width()))

    def test_SCOR11_selector_de_variable_no_se_aplasta_tras_parpadear_ni_con_el_panel_alto_o_bajo(self):
        """REQ-EDT-02, REQ-EDT-09: el desplegable «Variable» de una acción nunca es más bajo que un campo de texto del
        panel, con el panel a su altura mínima o más alto y tras el parpadeo (que antes le quitaba su hoja de estilo)."""
        w,e,s=self.preparar();e.nueva_variable('Abrir','output',{'kind':'int'})
        self.assertIsNone(e.poner_accion(s,{'tipo':'activacion','variable':'Abrir','valor':'5'}))
        w.editar_accion(s,e.acciones(s)[0]['id']);QApplication.processEvents()
        acc=w.props.accion;total=sum(w.vsplit.sizes())
        def comprobar(contexto):
            QApplication.processEvents()
            self.assertGreaterEqual(acc.variable.height(),acc.valor.height(),contexto)
            self.assertGreaterEqual(acc.variable.height(),acc.valor.sizeHint().height(),contexto)
            self.assertGreaterEqual(acc.variable.height(),62,contexto)
        for alto in (w._minimo_panel('inferior'),w._minimo_panel('inferior')+200):
            w.vsplit.setSizes([total-alto,alto]);comprobar(f'alto {alto}')
            acc.parpadeo.iniciar({'variable'});comprobar(f'parpadeando con alto {alto}')
            acc.parpadeo.parar();acc._pintar();comprobar(f'tras parpadear con alto {alto}')

    def test_SCOR08_color_flanco_en_qt(self):
        """REQ-SIM-03: un nivel verdadero sin flanco conserva el color normal."""
        m=M().var('p').step('A',True).step('B');m.trans('t',['B'],['A'],'rise(p)')
        v=vista(m,{'A':(180,100),'t':(180,220),'B':(180,340)})
        v.act('fijar',{'cambios':{'p':True}})
        sc,_=dibujo(v);t=texto(sc,'↑p')
        self.assertTrue(all(c==COL['true_text'] for c in colores(t)))
        v.act('avanzar',{'us':1000})
        sc,_=dibujo(v);t=texto(sc,'↑p')
        self.assertTrue(all(c!=COL['true_text'] for c in colores(t)))

    def test_SCOR09_retorno_no_atraviesa_acciones_y_js_usa_la_misma_ruta(self):
        """REQ-EDT-02, REQ-MOD-03: carril de retorno fuera de las cajas, compartido por Qt y JS."""
        from escritorio.diagrama import _geometria_acciones, SX
        from test_dibujo_vista import dibujar_con_js, QJS
        m=M().var('CintaIzquierda','output').var('TransferidorCarga','output')
        m.step('A',True).step('B').step('C').step('D')
        m.trans('t1',['A'],['B'],'false').trans('t2',['B'],['C'],'false')
        m.trans('t3',['C'],['D'],'false').trans('ret',['D'],['A'],'false')
        m.cont('C','CintaIzquierda').cont('C','TransferidorCarga')
        v=vista(m,{'A':(300,100),'t1':(300,180),'B':(550,260),'t2':(550,340),
                   'C':(550,420),'t3':(550,500),'D':(550,580),'ret':(550,660)})
        retorno=next(e for e in v.model['links'] if e['tid']=='ret' and e['rol']=='post')
        paso=next(s for s in v.model['steps'] if s['id']=='C')
        cajas,_=_geometria_acciones(paso['x']+SX,paso['y'],paso['actions'],'fila')
        for _,x,y,w in cajas:
            for a,b in zip(retorno['pts'],retorno['pts'][1:]):
                choque=(a[0]==b[0] and x<a[0]<x+w and max(min(a[1],b[1]),y-22)<min(max(a[1],b[1]),y+22)) or (a[1]==b[1] and y-22<a[1]<y+22 and max(min(a[0],b[0]),x)<min(max(a[0],b[0]),x+w))
                self.assertFalse(choque,(retorno['pts'],(x,y,w)))
        if QJS:
            arbol=dibujar_con_js(v.model,{})
            def paths(n):
                return ([n['attrs']['d']] if n['tag']=='path' and 'd' in n['attrs'] else []) + [p for h in n.get('hijos',[]) for p in paths(h)]
            d=' '.join(('M' if i==0 else 'L')+f'{x:g},{y:g}' for i,(x,y) in enumerate(retorno['pts']))
            self.assertIn(d,paths(arbol))
