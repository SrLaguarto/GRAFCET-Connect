"""Pruebas del flujo de selección y pegado de grupos de acciones."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QCursor
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False

if QT:
    from tools import hoja_contactos as HC
    from escritorio.diagrama import anclas, rects_comentarios


@unittest.skipUnless(QT, "requiere PySide6")
class AccionesAgrupadas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        HC.aplicacion()

    def preparar_acciones(self):
        self.c = HC.Contexto(1366, 768)
        self.addCleanup(self.c.cerrar)
        self.w, self.e = self.c.w, self.c.e
        self.c.mostrar()
        self.vista = self.w.diagrama
        for nombre in ("Cinta entrada", "Cinta 1", "Cinta 2", "Cinta 3"):
            self.assertIsNone(self.e.nueva_variable(nombre, "output"))
        self.destino = self.e.poner_etapa(QPointF(410, 400))
        self.assertIsNone(self.e.poner_accion(self.destino, {"tipo": "continua", "variable": "Cinta 2"}))
        self.cinta_2 = self.e.acciones(self.destino)[0]["id"]
        self.e.poner_comentario(self.destino, "Caja 2 lista en el puesto 1")
        self.grupo = self.crear_grupo("Cinta entrada", "Cinta 1")
        self.e.seleccionar([])
        self.vista.centrar_en(QPointF(475, 360))
        self.w.activateWindow()
        self.vista.setFocus()
        HC._bombear()

    def crear_grupo(self, *nombres):
        ids = []
        for nombre in nombres:
            punto = self.borde(ids[-1]) if ids else QPointF(340, 220)
            aid = self.e.poner_accion_suelta(punto)
            self.e.elegir_variable_accion(aid, nombre)
            ids.append(aid)
        self.assertEqual(self.e._ids_grupo(ids[0]), ids)
        return ids

    def caja(self, aid):
        return QRectF(*self.e.accion_en_id(aid)["rect"])

    def borde(self, aid):
        caja = self.caja(aid)
        return QPointF(caja.right(), caja.center().y())

    def pulsar_caja(self, aid, modificador=Qt.KeyboardModifier.NoModifier):
        vista = self.vista
        QTest.mouseClick(vista.viewport(), Qt.MouseButton.LeftButton, modificador,
                         vista.mapFromScene(self.caja(aid).center()))
        HC._bombear()

    def tecla(self, tecla, modificador=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(self.vista, tecla, modificador)
        HC._bombear()

    def copiar(self, *ids):
        self.e.seleccionar(list(ids or self.grupo))
        self.tecla(Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertIsNotNone(self.w._portapapeles)

    def arrastrar(self, origen, destino):
        self.e.prensar(origen)
        self.e.mover(destino)
        self.e.soltar(destino)
        HC._bombear()

    def comprobar_fila(self, sid, esperadas):
        acciones = self.e.acciones(sid)
        self.assertEqual([a["variable"] for a in acciones], esperadas)
        cajas = [self.caja(a["id"]) for a in acciones]
        self.assertEqual(len({c.center().y() for c in cajas}), 1)
        for izquierda, derecha in zip(cajas, cajas[1:]):
            self.assertEqual(izquierda.right(), derecha.left())

    def test_SAC1_clic_y_ctrl_clic_seleccionan_cajas_individuales(self):
        """REQ-EDT-02: el contorno de selección corresponde a las cajas pulsadas."""
        self.preparar_acciones()
        primera, segunda = self.grupo
        self.pulsar_caja(segunda)
        self.assertEqual(self.e.sel, [segunda])
        self.assertEqual(self.e.seleccion_dibujo(), {f"accion:{segunda}", segunda})
        self.pulsar_caja(primera, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.e.sel, [segunda, primera])
        self.pulsar_caja(segunda, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.e.sel, [primera])

    def test_SAC3_arrastrar_segunda_accion_mueve_el_grupo(self):
        """REQ-EDT-03: todas las cajas se mueven juntas aunque se agarre la segunda."""
        self.preparar_acciones()
        posiciones = [self.caja(aid).topLeft() for aid in self.grupo]
        origen = self.caja(self.grupo[1]).center()
        self.arrastrar(origen, origen + QPointF(60, 40))
        recorridos = [self.caja(aid).topLeft() - p for aid, p in zip(self.grupo, posiciones)]
        self.assertEqual(recorridos, [QPointF(60, 40)] * 2)

    def test_SAC4_supr_borra_solo_la_caja_y_cierra_el_hueco(self):
        """REQ-EDT-02, REQ-EDT-05: Supr quita una y Deshacer recupera la fila original."""
        self.preparar_acciones()
        tercera = self.e.poner_accion_suelta(self.borde(self.grupo[-1]))
        primera, segunda = self.grupo
        anterior = [self.caja(aid) for aid in (*self.grupo, tercera)]
        self.pulsar_caja(segunda)
        self.tecla(Qt.Key.Key_Delete)
        self.assertIsNone(self.e.accion_en_id(segunda))
        self.assertEqual(self.e._ids_grupo(primera), [primera, tercera])
        self.assertEqual(self.caja(tercera).left(), self.caja(primera).right())
        self.tecla(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual([self.caja(aid) for aid in (*self.grupo, tercera)], anterior)

    def test_SAC5_el_punto_izquierdo_conecta_el_grupo_entero(self):
        """REQ-EDT-02: el enlace del grupo conserva todas sus acciones en orden."""
        self.preparar_acciones()
        origen = anclas(self.e.M, self.grupo[0])[0]["pos"]
        self.arrastrar(origen, QPointF(410, 400))
        self.comprobar_fila(self.destino, ["Cinta 2", "Cinta entrada", "Cinta 1"])

    def test_SAC6_ctrl_v_usa_la_accion_seleccionada_y_aparta_el_comentario(self):
        """REQ-EDT-04, REQ-EDT-05: el destino seleccionado manda y Ctrl+Z restaura toda la operación."""
        self.preparar_acciones()
        self.copiar()
        self.pulsar_caja(self.cinta_2)
        texto_anterior = dict(rects_comentarios(self.e.M))[self.destino]
        pila = len(self.e.ed.undo_stack)
        QCursor.setPos(self.vista.viewport().mapToGlobal(self.vista.mapFromScene(QPointF(350, 580))))
        self.tecla(Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.comprobar_fila(self.destino, ["Cinta 2", "Cinta entrada", "Cinta 1"])
        ultimo = self.e.acciones(self.destino)[-1]["id"]
        self.assertGreater(dict(rects_comentarios(self.e.M))[self.destino].left(), self.caja(ultimo).right())
        self.assertEqual(len(self.e.ed.undo_stack), pila + 1)
        self.tecla(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.comprobar_fila(self.destino, ["Cinta 2"])
        self.assertEqual(dict(rects_comentarios(self.e.M))[self.destino], texto_anterior)
        self.assertEqual(self.e._ids_grupo(self.grupo[0]), self.grupo)

    def test_SAC7_pegar_en_punto_derecho_inserta_en_la_fila(self):
        """REQ-EDT-04: el menú ofrece Pegar en el punto de unión de una acción."""
        self.preparar_acciones()
        self.assertIsNone(self.e.poner_accion(self.destino, {"tipo": "continua", "variable": "Cinta 3"}))
        self.copiar()
        punto = self.borde(self.cinta_2)
        pegar = dict(self.w._menu_portapapeles(punto, True))["Pegar"]
        self.assertTrue(pegar())
        self.comprobar_fila(self.destino, ["Cinta 2", "Cinta entrada", "Cinta 1", "Cinta 3"])

    def test_SAC8_soltar_segunda_caja_del_grupo_en_punto_derecho(self):
        """REQ-EDT-02: cuenta el punto bajo el puntero aunque se arrastre desde la segunda caja."""
        self.preparar_acciones()
        pila = len(self.e.ed.undo_stack)
        self.arrastrar(self.caja(self.grupo[1]).center(), self.borde(self.cinta_2))
        self.comprobar_fila(self.destino, ["Cinta 2", "Cinta entrada", "Cinta 1"])
        self.assertEqual(self.e.ed.draft_actions(), [])
        self.assertEqual(len(self.e.ed.undo_stack), pila + 1)

    def test_SAC9_pegar_en_otra_etapa_y_no_unir_fragmento_mixto(self):
        """REQ-EDT-04: el grupo cambia de etapa. Un fragmento con una etapa sigue siendo espacial."""
        self.preparar_acciones()
        otra = self.e.poner_etapa(QPointF(260, 540))
        self.assertIsNone(self.e.poner_accion(otra, {"tipo": "continua", "variable": "Cinta 3"}))
        aid = self.e.acciones(otra)[0]["id"]
        self.copiar(self.cinta_2, self.grupo[0])
        self.pulsar_caja(aid)
        self.tecla(Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.comprobar_fila(otra, ["Cinta 3", "Cinta entrada", "Cinta 2"])
        self.comprobar_fila(self.destino, ["Cinta 2"])
        self.copiar(self.destino, self.grupo[0])
        self.assertTrue(self.e.pegar_fragmento(self.w._portapapeles, self.borde(aid), sobre_seleccion=True))
        self.assertEqual(len(self.e.ed.model["steps"]), 3)
        self.comprobar_fila(otra, ["Cinta 3", "Cinta entrada", "Cinta 2"])

    def test_SAC10_intro_y_doble_clic_editan_la_accion_pulsada(self):
        """REQ-EDT-13: la ventana de Propiedades recibe la acción pulsada."""
        self.preparar_acciones()
        primera, segunda = self.grupo
        self.e.tipo_accion(primera, "condicionada")
        self.e.tipo_accion(segunda, "condicionada")
        self.pulsar_caja(primera)
        self.tecla(Qt.Key.Key_Return)
        self.assertEqual(self.w.flot.panel.ident, primera)
        self.assertTrue(self.w.flot.hay_ventanas())
        self.w.flot.cerrar()
        QTest.mouseDClick(self.vista.viewport(), Qt.MouseButton.LeftButton,
                          pos=self.vista.mapFromScene(self.caja(segunda).center()))
        HC._bombear()
        self.assertEqual(self.w.flot.panel.ident, segunda)
        self.assertTrue(self.w.flot.hay_ventanas())
        self.w.flot.cerrar()
        self.e.unir_accion(primera, self.destino)
        self.pulsar_caja(primera)
        self.tecla(Qt.Key.Key_Return)
        self.assertEqual(self.w.flot.panel.ident, primera)
        self.assertTrue(self.w.flot.hay_ventanas())


if __name__ == "__main__":
    unittest.main()
