"""Regresiones de uso: ventanas transitorias, configuración y carga íntegra."""
from helpers_grafnet import fixture_grafnet
import copy
from pathlib import Path
import unittest
from unittest import mock
from test_editor_cadenas import BaseQt, QT
from grafcet.builder import M
from grafcet.persistence import open_model
from conexion.configuracion import Configuracion, Senal, ARCHIVO
if QT:
    from PySide6.QtCore import QObject, QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDropEvent, QWheelEvent, QFontMetrics
    from PySide6.QtWidgets import QApplication, QSpinBox, QComboBox, QLineEdit, QStyle, QStyleOptionButton
    from escritorio.diagrama import cajas_parciales

    class VigilarVentanas(QObject):
        def __init__(self, permitidas):
            super().__init__(); self.permitidas=permitidas; self.extras=[]
        def eventFilter(self, obj, ev):
            if ev.type()==QEvent.Type.Show and obj.isWidgetType() and obj.isWindow() and obj not in self.permitidas:
                self.extras.append(type(obj).__name__)
            return False


@unittest.skipUnless(QT, "requiere PySide6")
class CorreccionesUso(BaseQt):
    def panel(self):
        w=self.w
        doc=(M().var("sensor").var("nivel",kind="decimal",scale=2).var("consigna","output","int").step("0",True).doc)
        w.fuente={"tipo":"fichero","ruta":Path(self.tmp.name)/"modelo.json","doc":doc,"layout":{},"titulo":"Uso","ayuda":"","raiz":None}
        w._cargar();w._mostrar_pagina(True);w.resize(1366,768);w.show();self.app.processEvents()
        return w,w.panel_es

    def test_SUSO01_tres_gestos_no_muestran_ventanas_sin_padre(self):
        """REQ-SIM-03, REQ-ROB-01: soltar variable, reducir canales y cerrar Configuración nunca muestran ventanas transitorias."""
        w,p=self.panel(); permitidas={w,p.dialogo_config};v=VigilarVentanas(permitidas);self.app.installEventFilter(v)
        try:
            item=next(p.lista_entradas.item(i) for i in range(p.lista_entradas.count()) if p.lista_entradas.item(i).data(Qt.ItemDataRole.UserRole)=="nivel")
            mime=p.lista_entradas.mimeData([item]);dest=p.terminales[("input-register",0)]
            enter=QDragEnterEvent(QPoint(5,5),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(dest,enter);self.assertTrue(enter.isAccepted())
            drop=QDropEvent(QPointF(5,5),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(dest,drop);self.assertTrue(drop.isAccepted());self.app.processEvents()
            self.assertEqual([s.variable for s in p.config.senales],["nivel"]);self.assertEqual(v.extras,[])
            p.abrir_configuracion();self.app.processEvents();p.cantidades["input-register"].setValue(4);self.app.processEvents()
            self.assertEqual(p.config.canales["input-register"]["cantidad"],4);self.assertEqual(v.extras,[])
            p.dialogo_config.close();self.app.processEvents();self.assertEqual(v.extras,[])
            self.assertFalse([x for x in self.app.topLevelWidgets() if x.isVisible() and x not in permitidas])
        finally:self.app.removeEventFilter(v)

    def test_SUSO02_rueda_no_edita_ningun_campo_de_configuracion(self):
        """REQ-SIM-03, REQ-EDT-09: la rueda ignora edición incluso con foco, sin quitar la edición por teclado."""
        w,p=self.panel();p.abrir_configuracion();p.b_avanzado.click();self.app.processEvents()
        campos=p.dialogo_config.findChildren(QSpinBox)+p.dialogo_config.findChildren(QComboBox)+p.dialogo_config.findChildren(QLineEdit)
        valor=lambda c:c.value() if isinstance(c,QSpinBox) else c.currentIndex() if isinstance(c,QComboBox) else c.text()
        for campo in campos:
            antes=valor(campo)
            for foco in (False,True):
                campo.setFocus() if foco else campo.clearFocus()
                for paso in (120,-120):
                    ev=QWheelEvent(QPointF(campo.rect().center()),QPointF(campo.mapToGlobal(campo.rect().center())),QPoint(),QPoint(0,paso),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
                    self.app.sendEvent(campo,ev);self.assertEqual(valor(campo),antes)
        p.puerto.setValue(1502);self.assertEqual(p.config.puerto,1502)

    def test_SUSO03_numericas_nuevas_100_y_escalas_guardadas_se_respetan(self):
        """REQ-SIM-03, REQ-DAT-02: las altas numéricas proponen 100 y guardar/abrir conserva incluso una escala explícita de 1."""
        w,p=self.panel()
        for var,area in (("nivel","input-register"),("consigna","holding")):
            self.assertTrue(p.asignar(var,area,0))
        self.assertEqual([s.escala for s in p.config.senales],["100","100"])
        c=copy.deepcopy(p.config);c.senales[0].escala="1";c.senales[1].escala="25"
        ruta=Path(self.tmp.name)/ARCHIVO;c.guardar(ruta,p.doc);p.cargar(p.doc,Configuracion.cargar(ruta,p.doc))
        self.assertEqual([s.escala for s in p.obtener().senales],["1","25"])
        self.assertEqual(Senal("nivel","input-register",0,"INT16").escala,"100")
        p.tabla.cellWidget(1,7).setText("50");p.tabla.cellWidget(1,7).editingFinished.emit()
        self.assertEqual(p.config.senales[0].escala,"50")

    def test_SUSO04_botones_variables_caben_con_su_texto(self):
        """REQ-EDT-07, REQ-EDT-09: la rejilla de dos columnas deja todo el texto visible con el ancho lateral habitual."""
        w,e=self.vacio();w.resize(1366,768);w.show();self.app.processEvents();p=w.variables
        self.assertEqual(w.derecho.width(),w.ancho_derecho)
        botones=[*p.b_nuevas.values(),p.b_quitar]
        self.assertEqual([b.text() for b in botones],["+ Entrada","+ Salida","+ Memoria","Eliminar"])
        self.assertEqual(len({b.y() for b in botones}),2)
        for b in botones:
            opcion=QStyleOptionButton();b.initStyleOption(opcion)
            r=b.style().subElementRect(QStyle.SubElement.SE_PushButtonContents,opcion,b)
            self.assertGreaterEqual(r.width(),QFontMetrics(b.font()).horizontalAdvance(b.text()))
            self.assertTrue(b.parentWidget().rect().contains(b.geometry()))

    def test_SUSO05_salto_de_etapas_carga_integro_y_simula(self):
        """REQ-EDT-01, REQ-DAT-02, REQ-SIM-03: limpiar un huérfano no pierde entidades, G1 ni la posibilidad de simular."""
        ruta=Path(__file__).parent/"fixtures"/"salto_de_etapas";antes={p.name:p.read_bytes() for p in ruta.iterdir() if p.is_file()}
        original=open_model(ruta).doc;w=self.w
        with mock.patch("escritorio.ventana.QMessageBox.information") as aviso, mock.patch("escritorio.ventana.QMessageBox.warning") as fallo:
            self.assertTrue(w.abrir_ruta(fixture_grafnet(ruta)));e=w.edicion
            for coll in ("steps","transitions","actions","forces","variables","partials"):
                self.assertEqual(e.ed.model[coll],original[coll],coll)
            for coll in ("macros","expansions","enclosures"):
                self.assertEqual(e.ed.model["hierarchy"][coll],original["hierarchy"][coll],coll)
            self.assertEqual({s["id"] for s in e.M["steps"]},{s["id"] for s in original["steps"]})
            self.assertEqual({t["id"] for t in e.M["transitions"]},{t["id"] for t in original["transitions"]})
            dibujadas=[a for s in e.M["steps"] for a in s["actions"]]
            self.assertEqual({a["id"] for a in dibujadas if a["kind"]!="force"},{a["id"] for a in original["actions"]})
            self.assertEqual({a["id"] for a in dibujadas if a["kind"]=="force"},{f["id"] for f in original["forces"]})
            self.assertTrue({v["id"] for v in original["variables"]} <= set(e.M["names"]))
            g1=next(p["id"] for p in original["partials"] if p["label"]=="G1")
            self.assertIn(g1,cajas_parciales(e.M));self.assertTrue(e.ed.validate().can_simulate)
            w.refrescar_edicion();w._establecer_edicion(e);w.a_ejecutar.setChecked(True);w.rt.stop()
            self.assertEqual(w.modo,"simular");self.assertIsNotNone(w.v.s.z)
            aviso.assert_called_once();fallo.assert_not_called()
        self.assertEqual({p.name:p.read_bytes() for p in ruta.iterdir() if p.is_file()},antes)
