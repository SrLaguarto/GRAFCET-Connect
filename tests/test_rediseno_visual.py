"""Pruebas de los accesos visuales nuevos a operaciones existentes."""
import unittest
from test_editor_cadenas import BaseQt, QT
if QT:
    from PySide6.QtCore import QPointF, Qt


@unittest.skipUnless(QT, "PySide6 no está instalado")
class RedisenoVisual(BaseQt):
    def test_SVIS01_inicial_solape_y_deshacer(self):
        """REQ-EDT-02: etapa inicial desde la paleta, sin permitir solapes y con deshacer."""
        w, e = self.vacio()
        e.colocar("etapa_inicial", QPointF(300, 100))
        self.assertTrue(e.M["steps"][0]["initial"])
        e.colocar("etapa_inicial", QPointF(300, 100))
        self.assertEqual(len(e.M["steps"]), 1)
        e.deshacer()
        self.assertEqual(e.M["steps"], [])

    def test_SVIS02_apertura_y_cierre_son_barras_Y(self):
        """REQ-EDT-02, REQ-MOD-03: ambos accesos crean barras Y sin semántica nueva."""
        w, e = self.vacio()
        for ficha, y in (("simultaneidad:apertura", 100), ("simultaneidad:cierre", 300)):
            revision = e.ed.revision
            e.colocar(ficha, QPointF(300, y))
            self.assertEqual(e.M["bars"][-1]["kind"], "Y")
            self.assertEqual(e.ed.revision, revision)
        self.assertEqual(len(e.M["bars"]), 2)
        e.deshacer()
        self.assertEqual(len(e.M["bars"]), 1)

    def test_SVIS03_cinco_acciones_desde_paleta(self):
        """REQ-ACT-01, REQ-EDT-02: cada ficha crea el borrador de acción de su tipo."""
        w, e = self.vacio()
        tipos = ["continua", "condicionada", "activacion", "desactivacion", "evento"]
        for i, tipo in enumerate(tipos):
            e.colocar("accion:" + tipo, QPointF(300, 100 + i * 140))
        self.assertEqual([a["tipo"] for a in e.ed.draft_actions()], tipos)
        self.assertEqual(e.ed.model["actions"], [])

    def test_SVIS04_encabezados_y_dependencias(self):
        """REQ-EDT-02, REQ-SIM-03: encabezados sin arrastre; dependencias accesible al editar y simular."""
        w, e = self.vacio()
        pa = w.paleta
        for i in range(pa.count()):
            it = pa.item(i)
            if not it.data(Qt.ItemDataRole.UserRole):
                self.assertFalse(it.flags() & (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled))
                self.assertFalse(pa.mimeData([it]).hasText())
        w.show()
        self.app.processEvents()
        b = w.diagrama.b_dependencias
        self.assertIs(b.parent(), w.tb_vista)
        self.assertTrue(b.isVisible())
        b.click()
        self.assertTrue(w.diagrama.dependencias)
        e.ed.dirty = False
        w.cargar_ejemplo("temporizada")
        self.assertTrue(w.cambiar_modo("simular"))
        self.app.processEvents()
        self.assertTrue(b.isVisible() and b.isChecked())

    def test_SVIS05_propiedades_compactas_y_divisor_manual_respetado(self):
        """REQ-EDT-02, REQ-EDT-09: sin selección se libera el lienzo; el reparto manual se conserva."""
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        for _ in range(5):
            self.app.processEvents()
        vacio = w.vsplit.sizes()[1]
        self.assertLessEqual(vacio, 100)
        e.colocar("transicion", QPointF(300, 180))
        for _ in range(5):
            self.app.processEvents()
        self.assertGreater(w.vsplit.sizes()[1], vacio)
        self.assertTrue(w.props.cuerpo.isVisible())
        w.vsplit.moveSplitter(w.vsplit.sizes()[0] - 35, 1)
        self.app.processEvents()
        manual = w.vsplit.sizes()
        e.seleccionar([])
        for _ in range(5):
            self.app.processEvents()
        self.assertEqual(w.vsplit.sizes(), manual)
        self.assertFalse(w.props.cuerpo.isVisible())
