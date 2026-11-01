"""Distancia estándar compacta y nombres de referencias a etapas borradas."""
import copy
import unittest
from pathlib import Path
from grafcet.editor import Editor,new_grafcet_document
from grafcet.view import Vista,auto_layout
from grafcet.profile import normalize_options
from test_editor_cadenas import BaseQt,QT


def caso():
    e=Editor(new_grafcet_document('m'));a=e.add_step('g','0',True,at=(120,300));b=e.add_step('g','1',at=(500,380))
    t,_=e.add_transition('g','delay(3 s, active(`1`), 0 s) AND active(`1`)',pre=[a],post=[a],label='t3',at=(120,200))
    return e,a,b,t


class ReferenciasVista(unittest.TestCase):
    def test_SDRF01_referencia_borrada_conserva_nombre_y_bloqueo(self):
        """REQ-EDT-09, REQ-EDT-05: borrar una etapa referenciada conserva X1 en la vista, el significado inválido y deshacer."""
        e,a,b,t=caso();antes=copy.deepcopy(e.model);exp=copy.deepcopy(e.model['expressions'])
        e.delete([b]);self.assertEqual(e.model['expressions'],exp)
        v=Vista('m','','',lambda:(e.model,None),normalize_options(None))
        segmentos=v.model['transitions'][0]['cond'];self.assertEqual([s['t'] for s in segmentos if s.get('s')],['1','1'])
        self.assertNotIn(b,str(segmentos));self.assertEqual(v.names[b],'1')
        self.assertIn('D-REF',{d.code for d in v.compile_diags});self.assertIsNone(v.s)
        e.undo();self.assertEqual(e.model,antes)

    def test_SDRF02_disposicion_automatica_usa_60_sin_cambiar_modelo(self):
        """REQ-EDT-03: el dibujo automático deja 60 entre etapa y transición, 120 entre etapas; no cambia el modelo."""
        e=Editor(new_grafcet_document('m'));a=e.add_step('g','1',True);b=e.add_step('g','2');t,_=e.add_transition('g','false',pre=[a],post=[b])
        antes=copy.deepcopy(e.model);p=auto_layout(e.model)
        self.assertEqual(p[t][1]-p[a][1],60);self.assertEqual(p[b][1]-p[t][1],60);self.assertEqual(e.model,antes)

if QT:
    from PySide6.QtCore import Qt,QPointF,QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QGraphicsTextItem
    from escritorio.edicion import Edicion


@unittest.skipUnless(QT,'requiere PySide6')
class DistanciasReferenciasInterfaz(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SDRF03_anadir_automatico_y_equidistanciar_comparten_60_y_deshacer(self):
        """REQ-EDT-03, REQ-EDT-05: Ctrl+Intro añade a 60 y equidistanciar usa el mismo paso en una operación reversible."""
        w,e=self.vacio();w.resize(1366,768);w.show();s=e.ed.add_step('g','1',True,at=(120,100));e.seleccionar([s]);e.cambia();w.diagrama.setFocus();QApplication.processEvents()
        QTest.keyClick(w.diagrama,Qt.Key.Key_Return,Qt.KeyboardModifier.ControlModifier);QApplication.processEvents()
        t=e.ed.model['transitions'][0]['id'];z=e.sel[0];p=self.pos(e)
        self.assertEqual((p[t][1],p[z][1]),(160,220))
        e.ed.move(z,120,400);e.cambia();antes=copy.deepcopy(e.ed.presentation);n=len(e.ed.undo_stack)
        e.equidistanciar([s]);self.assertEqual((self.pos(e)[t][1],self.pos(e)[z][1]),(160,220));self.assertEqual(len(e.ed.undo_stack),n+1)
        e.ed.undo();self.assertEqual(e.ed.presentation,antes)

    def test_SDRF04_supr_no_expone_ids_en_qt_js_ni_tras_reabrir(self):
        """REQ-EDT-05, REQ-EDT-09, REQ-DAT-02: Supr conserva subíndices legibles, bloquea Play y se guarda/abre sin IDs visibles."""
        from test_dibujo_vista import dibujar_con_js
        core,a,b,t=caso();w=self.w;e=Edicion.desde(core.model,{a:(120,300),b:(500,380),t:(120,200)},'Referencia eliminada',presentacion=core.presentation)
        w._establecer_edicion(e);w.resize(1366,768);w.show();e.seleccionar([b]);w.diagrama.setFocus();QApplication.processEvents()
        QTest.keyClick(w.diagrama,Qt.Key.Key_Delete);QApplication.processEvents();self.assertNotIn(b,{s['id'] for s in e.ed.model['steps']})
        textos=[i.toPlainText() for i in w.diagrama.scene().items() if isinstance(i,QGraphicsTextItem)]
        self.assertNotIn(b,''.join(textos));self.assertIn('3s/X1·X1',textos)
        self.assertIn('D-REF',{d['code'] for d in e.diagnosticos()})
        dom=dibujar_con_js(e.M,{})
        self.assertNotIn(b,str(dom))
        p=Path(self.tmp.name)/'referencias';e.guardar(p);e.ed.dirty=False;self.assertTrue(w.abrir_ruta(p))
        segmentos=w.edicion.M['transitions'][0]['cond'];self.assertEqual([s['t'] for s in segmentos if s.get('s')],['1','1'])
        self.assertIsNone(w.edicion.vista.s)
