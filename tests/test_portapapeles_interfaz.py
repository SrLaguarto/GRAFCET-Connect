"""Portapapeles de diagrama y aislamiento de los editores de texto y variables."""
import copy
import unittest
from unittest import mock
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF, QPoint, Qt, QTimer
    from PySide6.QtGui import QCursor, QContextMenuEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit, QMenu
    from escritorio.diagrama import posiciones, SX, cajas_parciales, barra


@unittest.skipUnless(QT, "PySide6 no está instalado")
class PortapapelesInterfaz(BaseQt):
    def preparar(self):
        w, e = self.vacio()
        a = e.poner_etapa(QPointF(200, 100), inicial=True)
        w.resize(1366, 768); w.show(); QApplication.processEvents()
        w.diagrama._manual = True
        w.diagrama.resetTransform()
        w.diagrama.setSceneRect(0, 0, 1600, 1200)
        w.diagrama.centerOn(600, 400)
        e.seleccionar([a])
        w.diagrama.setFocus(); QApplication.processEvents()
        return w, e, a

    def tecla(self, w, key):
        QTest.keyClick(w.diagrama, key, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()

    def test_SCLQ01_atajos_copiar_cortar_pegar_y_deshacer(self):
        """REQ-EDT-04, REQ-EDT-05, REQ-EDT-13: los atajos reales copian, cortan y pegan en transacciones atómicas."""
        w, e, a = self.preparar()
        n = len(e.ed.undo_stack)
        self.tecla(w, Qt.Key.Key_C)
        self.assertIsNotNone(w._portapapeles)
        self.assertEqual(len(e.ed.undo_stack), n)
        QCursor.setPos(w.mapToGlobal(QPoint(5, 5)))
        esperado = w.diagrama.mapToScene(w.diagrama.viewport().rect().center())
        self.tecla(w, Qt.Key.Key_V)
        self.assertEqual(len(e.ed.model["steps"]), 2)
        nuevo = e.sel[0]
        x, y = posiciones(e.M)[nuevo]
        self.assertLessEqual(abs(x - esperado.x()), 10)
        self.assertLessEqual(abs(y - esperado.y()), 10)
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer(); self.assertEqual([s["id"] for s in e.ed.model["steps"]], [a])
        e.seleccionar([a]); w.diagrama.setFocus()
        self.tecla(w, Qt.Key.Key_X)
        self.assertEqual(e.ed.model["steps"], [])
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer(); self.assertEqual([s["id"] for s in e.ed.model["steps"]], [a])

    def test_SCLQ02_teclado_pega_bajo_el_raton_en_el_dibujo(self):
        """REQ-EDT-03, REQ-EDT-04: el cursor sobre el dibujo determina el punto de pegado ajustado a rejilla."""
        w, e, a = self.preparar(); self.tecla(w, Qt.Key.Key_C)
        local = w.diagrama.viewport().rect().center() + QPoint(60, 25)
        p = w.diagrama.mapToScene(local)
        self.assertTrue(w.diagrama.viewport().rect().contains(local))
        QCursor.setPos(w.diagrama.viewport().mapToGlobal(local))
        self.tecla(w, Qt.Key.Key_V)
        x, y = posiciones(e.M)[e.sel[0]]
        self.assertLessEqual(abs(x - p.x()), 10); self.assertLessEqual(abs(y - p.y()), 10)

    def test_SCLQ03_texto_y_tabla_no_disparan_el_portapapeles_del_diagrama(self):
        """REQ-EDT-04, REQ-EDT-07, REQ-EDT-13: Ctrl+C/X/V respeta el foco de campos y tabla de variables."""
        w, e, a = self.preparar(); self.tecla(w, Qt.Key.Key_C)
        fragmento = w._portapapeles
        campo = QLineEdit(w); campo.setText("texto"); campo.show(); campo.setFocus(); campo.selectAll()
        QApplication.processEvents()
        estado, n = self.estado(e), len(e.ed.undo_stack)
        QTest.keyClick(campo, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(QApplication.clipboard().text(), "texto")
        QTest.keyClick(campo, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(campo.text(), "")
        QTest.keyClick(campo, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(campo.text(), "texto")
        self.assertIs(w._portapapeles, fragmento)
        campo.hide()
        e.nueva_variable("entrada", "input")
        tabla = w.variables.tabla
        tabla.setFocus(); QApplication.processEvents()
        estado, n = self.estado(e), len(e.ed.undo_stack)
        for key in (Qt.Key.Key_C, Qt.Key.Key_X, Qt.Key.Key_V):
            QTest.keyClick(tabla, key, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (estado, n))
        self.assertIs(w._portapapeles, fragmento)

    def test_SCLQ04_otro_proyecto_conserva_portapapeles_y_exige_variables(self):
        """REQ-EDT-04, REQ-EDT-01: cambiar de proyecto conserva la copia y avisa sin pegar si falta una variable."""
        w, e, a = self.preparar()
        e.nueva_variable("salida", "output")
        e.pedir_accion = lambda *args: None
        did = e.anadir_accion(a)
        e.poner_accion(a, {"tipo": "continua", "variable": "salida"}, did)
        e.seleccionar([a]); w.diagrama.setFocus(); self.tecla(w, Qt.Key.Key_C)
        original = w._portapapeles
        e.ed.dirty = False; w.nuevo(); e = w.edicion
        self.assertIs(w._portapapeles, original)
        before = self.estado(e)
        self.assertFalse(w._portapapeles_accion("pegar", QPointF(700, 400)))
        self.assertEqual(self.estado(e), before); self.assertIn("salida", e.mensaje)
        e.nueva_variable("salida", "output"); w.diagrama.setFocus(); QApplication.processEvents()
        self.assertTrue(w._portapapeles_accion("pegar", QPointF(700, 400)))
        self.assertEqual(len(e.ed.model["variables"]), 1)
        self.assertEqual(len(e.ed.model["actions"]), 1)

    def test_SCLQ05_solape_busca_hueco_mas_cercano_y_permite_arrastrar(self):
        """REQ-EDT-03, REQ-EDT-04, REQ-EDT-05: pegar encima busca el hueco más cercano, selecciona y se deshace junto."""
        w,e,a=self.preparar();self.tecla(w,Qt.Key.Key_C)
        antes=self.estado(e);n=len(e.ed.undo_stack);p=QPointF(*posiciones(e.M)[a])
        self.assertTrue(w._portapapeles_accion("pegar",p));self.assertEqual(len(e.ed.undo_stack),n+1)
        nuevo=e.sel[0];x,y=posiciones(e.M)[nuevo]
        self.assertEqual((x-p.x())**2+(y-p.y())**2,60**2)
        self.assertFalse(e._pares_solape({nuevo}))
        q=QPointF(x,y);e.prensar(q);e.mover(q+QPointF(80,80));e.soltar(q+QPointF(80,80))
        self.assertEqual(posiciones(e.M)[nuevo],(x+80,y+80))
        e.deshacer();self.assertEqual(posiciones(e.M)[nuevo],(x,y))
        e.deshacer();self.assertEqual(self.estado(e),antes)

    def test_SCLQ06_cortar_jerarquia_cancela_o_se_deshace_junto(self):
        """REQ-EDT-04, REQ-EDT-05: cortar un marco consulta el borrado y la cancelación no cambia la copia anterior."""
        w, e, a = self.preparar(); self.tecla(w, Qt.Key.Key_C)
        old = w._portapapeles
        g = e.poner_parcial(QPointF(700, 220))
        c = cajas_parciales(e.M)[g]
        b = e.poner_etapa(QPointF((c["x0"]+c["x1"])/2, (c["y0"]+c["y1"])/2))
        e.seleccionar([g, b]); w.diagrama.setFocus()
        before, n = self.estado(e), len(e.ed.undo_stack)
        planes = []
        e.confirmar_borrado = lambda p: planes.append(p) or False
        self.tecla(w, Qt.Key.Key_X)
        self.assertEqual(self.estado(e), before); self.assertIs(w._portapapeles, old)
        self.assertEqual(len(planes), 1)
        e.confirmar_borrado = lambda p: True
        self.tecla(w, Qt.Key.Key_X)
        self.assertNotIn(g, {p["id"] for p in e.ed.model["partials"]})
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer(); self.assertEqual(self.estado(e), before)

    def test_SCLQ07_menus_reales_y_pegar_desactivado_si_vacio(self):
        """REQ-EDT-04, REQ-EDT-13: menú Edición y clic derecho ofrecen las acciones con el estado del portapapeles."""
        w, e, a = self.preparar()
        menu = next(x.menu() for x in w.menuBar().actions() if x.text() == "&Edición")
        self.assertTrue({"Cortar", "Copiar", "Pegar"} <= {x.text() for x in menu.actions()})
        menus = []
        def abrir():
            menu = QApplication.activePopupWidget()
            self.assertIsInstance(menu, QMenu)
            menus.append([(x.text(), x.isEnabled()) for x in menu.actions() if not x.isSeparator()])
            menu.close()
        def contexto(p):
            local = w.diagrama.mapFromScene(p)
            event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, w.diagrama.viewport().mapToGlobal(local))
            QTimer.singleShot(0, abrir)
            w.diagrama.contextMenuEvent(event)
        contexto(QPointF(700, 400))
        self.assertIn(("Pegar", False), menus[-1])
        contexto(QPointF(*posiciones(e.M)[a]))
        self.assertTrue({("Cortar", True), ("Copiar", True)} <= set(menus[-1]))
        w.a_copiar.trigger()
        contexto(QPointF(700, 400))
        self.assertIn(("Pegar", True), menus[-1])

    def test_SCLQ08_accion_unida_copiada_sola_se_pega_suelta(self):
        """REQ-EDT-04, REQ-ACT-01: Ctrl+C sobre la caja copia solo la acción, no su etapa ni otras acciones."""
        w, e, a = self.preparar(); e.nueva_variable("salida", "output")
        e.pedir_accion = lambda *args: None
        did = e.anadir_accion(a); e.poner_accion(a, {"tipo": "continua", "variable": "salida"}, did)
        aid = e.ed.model["actions"][0]["id"]
        e.accion, e.sel = aid, [a]; w.diagrama.setFocus(); QApplication.processEvents()
        self.tecla(w, Qt.Key.Key_C)
        self.assertTrue(w._portapapeles_accion("pegar", QPointF(750, 400)))
        self.assertEqual(len(e.ed.model["steps"]), 1)
        self.assertEqual(len(e.ed.model["actions"]), 1)
        self.assertEqual(len(e.ed.draft_actions()), 1)
        self.assertFalse(e.ed.draft_actions()[0].get("etapa"))

    def test_SCLQ09_marco_incluye_accion_suelta_y_barra_vacia_interiores(self):
        """REQ-EDT-04, REQ-ACT-01: los elementos sin propietario que están dentro del marco viajan con él."""
        w, e, a = self.preparar()
        g = e.poner_parcial(QPointF(650, 200))
        c = cajas_parciales(e.M)[g]
        # Amplía el contenido para que quepan los elementos de presentación en un hueco del marco.
        x, y = c["x0"] + 50, c["y0"] + 50
        s1 = e.poner_etapa(QPointF(x, y))
        s2 = e.ed.add_step(g, "interior", at=(x + 400 - SX, y + 300))
        e.cambia()
        did = e.poner_accion_suelta(QPointF(x + 160, y + 140))
        bar = e.poner_barra(QPointF(x + 150, y + 230), "Y")
        self.assertIsNotNone(did); self.assertIsNotNone(bar)
        e.seleccionar([g])
        frag = e.copiar_fragmento()
        self.assertIn(did, {d["id"] for d in frag.presentation["draftActions"]})
        self.assertIn(bar, {b["id"] for b in frag.presentation["barras"]})
        self.assertTrue({s1, s2} <= {s["id"] for s in frag.entities["steps"]})

    def test_SCLQ10_clic_derecho_barra_aislada_copia_la_barra_no_otra_seleccion(self):
        """REQ-EDT-04, REQ-MOD-03: el menú de una barra aislada opera sobre ella y nunca sobre una selección anterior."""
        w, e, a = self.preparar()
        bid = e.poner_barra(QPointF(650, 300), "Y")
        e.seleccionar([a])
        b = next(x for x in e.M["bars"] if x["id"] == bid)
        x, y, width, height = barra(b)
        local = w.diagrama.mapFromScene(QPointF(x + width / 2, y + height / 2))
        def copiar():
            menu = QApplication.activePopupWidget()
            next(x for x in menu.actions() if x.text() == "Copiar").trigger()
            menu.close()
        QTimer.singleShot(0, copiar)
        w.diagrama.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local,
                                                      w.diagrama.viewport().mapToGlobal(local)))
        self.assertEqual([b["id"] for b in w._portapapeles.presentation["barras"]], [bid])
        self.assertEqual(w._portapapeles.entities["steps"], [])

    def test_SCLQ11_grupo_pega_cerca_con_disposicion_y_un_solo_deshacer(self):
        """REQ-EDT-03, REQ-EDT-04, REQ-EDT-05: la búsqueda desplaza todo el fragmento sin alterar sus posiciones relativas."""
        w,e,a=self.preparar();e.colocar("etapa",QPointF(400,100));b=e.sel[0]
        e.seleccionar([a,b]);frag=e.copiar_fragmento();pos=posiciones(e.M);antes=self.estado(e);n=len(e.ed.undo_stack)
        self.assertTrue(e.pegar_fragmento(frag,QPointF(*pos[a])))
        self.assertEqual(len(e.sel),2);self.assertEqual(len(e.ed.undo_stack),n+1)
        actual=posiciones(e.M);aa,bb=e.sel
        self.assertEqual((actual[bb][0]-actual[aa][0],actual[bb][1]-actual[aa][1]),(pos[b][0]-pos[a][0],pos[b][1]-pos[a][1]))
        self.assertFalse(any(not {a,b}<=set(e.sel) for a,b in e._pares_solape(set(e.sel))))
        e.deshacer();self.assertEqual(self.estado(e),antes)
