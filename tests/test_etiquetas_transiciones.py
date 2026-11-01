"""Visibilidad inicial de las etiquetas de las transiciones nuevas."""
import copy
import unittest
from pathlib import Path
from test_editor_cadenas import BaseQt,QT,nuevo
from grafcet.persistence import open_model
if QT:
    from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.edicion import Edicion


class Nucleo(unittest.TestCase):
    def test_SETI01_transicion_nueva_oculta_en_la_misma_operacion_deshacer(self):
        """REQ-EDT-02, REQ-EDT-05: la transición colocada nace sin etiqueta visible y se deshace en una operación."""
        ed=nuevo();antes=copy.deepcopy((ed.model,ed.presentation));n=len(ed.undo_stack)
        t,_=ed.add_transition("g","false",at=(100,180),label="t1")
        self.assertIn(t,ed.hidden_labels());self.assertEqual(len(ed.undo_stack),n+1)
        ed.undo();self.assertEqual((ed.model,ed.presentation),antes)
        ed.redo();self.assertIn(t,ed.hidden_labels())
        revision=ed.revision;ed.set_label_visible(t,True);self.assertNotIn(t,ed.hidden_labels())
        self.assertEqual(ed.revision,revision);ed.undo();self.assertIn(t,ed.hidden_labels())


@unittest.skipUnless(QT,"requiere PySide6")
class Interfaz(BaseQt):
    def tearDown(self):
        self.w.hide();super().tearDown();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_SETI02_opcion_desmarcada_y_etiqueta_oculta_al_colocar(self):
        """REQ-EDT-02, REQ-EDT-09: la ficha crea una transición oculta; el clic en Mostrar etiqueta la activa y se puede deshacer."""
        w,e=self.vacio();w.resize(1366,768);w.show();QTest.qWait(10)
        e.colocar("transicion",QPointF(200,180));t=e.sel[0];e.seleccionar([t]);w.editar_condicion(t);QApplication.processEvents()
        self.assertFalse(w.props.t_mostrar.isChecked());self.assertFalse(e.M["transitions"][0]["showLabel"])
        textos=lambda:[it.toPlainText() for it in w.diagrama.scene().items() if hasattr(it,"toPlainText")]
        self.assertNotIn("(t1)",textos())
        self.assertTrue(w.props.t_mostrar.isVisible())
        QTest.mouseClick(w.props.t_mostrar,Qt.MouseButton.LeftButton,pos=QPoint(8,w.props.t_mostrar.height()//2))
        self.assertTrue(e.M["transitions"][0]["showLabel"]);self.assertIn("(t1)",textos())
        e.deshacer();self.assertFalse(e.M["transitions"][0]["showLabel"]);self.assertNotIn("(t1)",textos())

    def test_SETI03_guardar_y_abrir_conserva_una_visible_y_otra_oculta(self):
        """REQ-EDT-02, REQ-DAT-02: el nuevo valor inicial no cambia la elección ya guardada en un proyecto."""
        w,e=self.vacio()
        a,_=e.ed.add_transition("g","false",at=(100,180),label="t1")
        b,_=e.ed.add_transition("g","false",at=(300,180),label="t2")
        e.ed.set_label_visible(a,True);e.cambia();ruta=Path(self.tmp.name)/"etiquetas"
        e.guardar(ruta);op=open_model(ruta)
        abierto=Edicion.desde(op.doc,{},"Etiquetas",ruta,op.presentations[0])
        self.assertEqual(abierto.ed.hidden_labels(),{b})
        self.assertEqual({t["id"]:t["showLabel"] for t in abierto.M["transitions"]},{a:True,b:False})
