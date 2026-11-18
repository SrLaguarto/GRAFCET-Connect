"""Regresiones del salto de acciones al completar su variable o cambiar su tipo."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from escritorio.edicion import Edicion
from escritorio.orden_acciones import ids_etapa
from grafcet.persistence import open_model
from grafcet.view import Vista, layout_from_presentation
from tools import hoja_contactos as HC


class OrdenAcciones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = HC.aplicacion()

    def preparar(self):
        e = Edicion.nuevo()
        for nombre in ("Motor uno", "Motor dos", "Motor tres", "Motor cuatro"):
            self.assertIsNone(e.nueva_variable(nombre, "output", {"kind": "bool"}))
        self.assertIsNone(e.nueva_variable("Marcha", "input", {"kind": "bool"}))
        sid = e.poner_etapa(QPointF(200, 200))
        ids = [e.anadir_accion(sid) for _ in range(4)]
        return e, sid, ids

    def comprobar(self, e, sid, orden):
        self.assertEqual(ids_etapa(e.ed, sid), orden)
        self.assertEqual([a["id"] for a in e._colocadas() if a["etapa"] == sid], orden)
        self.assertEqual([a["id"] for a in e.acciones(sid)], orden)

    def test_SOA01_completar_derecha_no_la_adelanta(self):
        """REQ-EDT-09: elegir variable conserva la cuarta posición y la selección."""
        for colocacion in ("fila", "fila-separada", "columna", "matriz-2"):
            with self.subTest(colocacion=colocacion):
                e, sid, ids = self.preparar()
                e.colocar_acciones(sid, colocacion)
                e.elegir_variable_accion(ids[-1], "Motor cuatro")
                nuevo = e.accion
                self.assertNotEqual(nuevo, ids[-1])
                self.comprobar(e, sid, ids[:-1] + [nuevo])
                e.elegir_variable_accion(nuevo, "Motor dos")
                self.comprobar(e, sid, ids[:-1] + [nuevo])

    def test_SOA02_cambio_a_incompleta_y_vuelta_en_su_sitio(self):
        """REQ-EDT-09: completa, condicionada pendiente y completa conservan su ordinal."""
        e, sid, ids = self.preparar()
        e.elegir_variable_accion(ids[1], "Motor dos")
        completa = e.accion
        e.tipo_accion(completa, "condicionada")
        pendiente = e.accion
        self.comprobar(e, sid, [ids[0], pendiente, ids[2], ids[3]])
        self.assertIsNone(e.poner_texto_accion(pendiente, "condicion", "Marcha"))
        self.comprobar(e, sid, [ids[0], e.accion, ids[2], ids[3]])
        self.assertFalse(e._es_borrador(e.accion))

    def test_SOA03_una_operacion_deshacer_rehacer_y_persistencia(self):
        """REQ-EDT-10: el orden se deshace junto al valor y se conserva al reabrir."""
        e, sid, ids = self.preparar()
        antes = len(e.ed.undo_stack)
        e.elegir_variable_accion(ids[-1], "Motor cuatro")
        final = ids[:-1] + [e.accion]
        self.assertEqual(len(e.ed.undo_stack), antes + 1)
        e.deshacer()
        self.comprobar(e, sid, ids)
        e.rehacer()
        self.comprobar(e, sid, final)
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "proyecto"
            e.guardar(destino)
            abierto = open_model(destino)
            pres = abierto.presentations[0]
            otro = Edicion.desde(abierto.doc, layout_from_presentation(pres), abierto.title, presentacion=pres)
            self.comprobar(otro, sid, final)

    def test_SOA04_completar_en_orden_inverso_conserva_modelo_y_dibujo(self):
        """REQ-EDT-09: al completar todas, actionRefs y la vista de simulación coinciden."""
        e, sid, ids = self.preparar()
        orden = list(ids)
        nombres = ["Motor uno", "Motor dos", "Motor tres", "Motor cuatro"]
        for posicion in (3, 1, 2, 0):
            e.elegir_variable_accion(ids[posicion], nombres[posicion])
            orden[posicion] = e.accion
            self.comprobar(e, sid, orden)
        self.assertEqual(e.ed.get(sid)["actionRefs"], orden)
        vista = Vista("prueba", "", "", lambda: (e.ed.model, e.layout()), {})
        etapa = next(s for s in vista.model["steps"] if s["id"] == sid)
        self.assertEqual([a["id"] for a in etapa["actions"]], orden)

    def test_SOA05_insercion_y_movimiento_explicitos_se_respetan(self):
        """REQ-EDT-09: insertar detrás y mover explícitamente siguen definiendo el orden."""
        e, sid, ids = self.preparar()
        e.elegir_variable_accion(ids[1], "Motor dos")
        completa = e.accion
        e.mover_accion(completa, 1)
        orden = [ids[0], ids[2], completa, ids[3]]
        self.comprobar(e, sid, orden)
        e.elegir_variable_accion(ids[3], "Motor cuatro")
        self.comprobar(e, sid, orden[:-1] + [e.accion])

    def test_SOA06_clic_real_en_selector_conserva_ultima_caja(self):
        """REQ-UX-01: elegir con el ratón en el desplegable no cambia el ordinal dibujado."""
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        e, sid, ids = self.preparar()
        c.w._establecer_edicion(e)
        c.w._poner_modo()
        c.mostrar()
        c.w.refrescar_edicion()
        HC._bombear(10)
        caja = e.accion_en_id(ids[-1])
        self.assertIsNotNone(caja)
        e.desplegar_variable(caja)
        HC._bombear(10)
        combo = c.w.diagrama._selector
        indice = combo.model().index(combo.findData("Motor cuatro"), 0)
        combo.view().scrollTo(indice)
        HC._bombear(4)
        QTest.mouseClick(combo.view().viewport(), Qt.MouseButton.LeftButton,
                        pos=combo.view().visualRect(indice).center())
        HC._bombear(10)
        orden = ids[:-1] + [e.accion]
        self.assertIsNone(c.w.diagrama._selector)
        self.comprobar(e, sid, orden)
        self.assertEqual([a["id"] for a in c.w.diagrama.cajas_acciones], orden)

    def test_SOA07_ctrl_clic_y_enlace_de_copia_mueven_el_grupo(self):
        """REQ-EDT-09: Ctrl elige acciones sueltas de su etapa y su copia se une como grupo."""
        from PySide6.QtCore import QRectF
        from escritorio.diagrama import anclas

        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        e, sid, ids = self.preparar()
        for ident, nombre in zip(ids[:3], ("Motor uno", "Motor dos", "Motor tres")):
            e.elegir_variable_accion(ident, nombre)
        completas = e.ed.get(sid)["actionRefs"]
        objetivo = e.poner_etapa(QPointF(250, 440))
        c.w._establecer_edicion(e)
        c.w._poner_modo()
        c.mostrar()
        c.w.refrescar_edicion()
        vista = c.w.diagrama
        vista.ajustar()
        HC._bombear(8)
        for n, ident in enumerate(completas):
            caja = e.accion_en_id(ident)
            punto = vista.mapFromScene(QRectF(*caja["rect"]).center())
            mod = Qt.KeyboardModifier.ControlModifier if n else Qt.KeyboardModifier.NoModifier
            QTest.mouseClick(vista.viewport(), Qt.MouseButton.LeftButton, mod, punto)
        self.assertEqual(e.sel, completas)
        fragmento = e.copiar_fragmento()
        self.assertTrue(e.pegar_fragmento(fragmento, QPointF(560, 430)))
        pegadas = list(e.sel)
        self.assertEqual(len(pegadas), 3)
        self.assertEqual(e._ids_grupo(pegadas[0]), pegadas)
        origen = anclas(e.M, pegadas[0])[0]
        destino = next(a for a in anclas(e.M, objetivo) if a["lado"] == "der")
        e.prensar(origen["pos"])
        e.mover(destino["pos"])
        e.soltar(destino["pos"])
        self.assertEqual([a["variable"] for a in e.acciones(objetivo)], ["Motor uno", "Motor dos", "Motor tres"])
        self.assertFalse(any(e._es_borrador(i) for i in pegadas))


if __name__ == "__main__":
    unittest.main()
