"""Rendimiento, diagnósticos y geometría de Propiedades de AD."""
from pathlib import Path
from statistics import median
import sys
import tempfile
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QEvent, QObject, QPointF, QStandardPaths, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QGraphicsTextItem

    from artifacts.ad_118.medir_100_etapas import construir, muestra
    from escritorio.diagrama import _ajustar_enlaces, enlaces, posiciones
    from escritorio.edicion import DY
    from escritorio.rutas_diagrama import rutas
    from grafcet import routing
    from tools import hoja_contactos as HC

    class CambiosGeometria(QObject):
        def __init__(self):
            super().__init__()
            self.cambios = []

        def eventFilter(self, objeto, evento):
            if evento.type() in (QEvent.Type.Move, QEvent.Type.Resize):
                self.cambios.append(objeto.geometry().getRect())
            return False


@unittest.skipUnless(QT, "requiere PySide6")
class InterfazAD(BaseQt):
    def setUp(self):
        documentos = self.enterContext(tempfile.TemporaryDirectory())
        ubicacion_original = QStandardPaths.writableLocation

        def ubicacion(clase):
            if clase == QStandardPaths.StandardLocation.DocumentsLocation:
                return documentos
            return ubicacion_original(clase)

        self.enterContext(patch.object(QStandardPaths, "writableLocation", ubicacion))
        super().setUp()

    def test_SAD1_rutas_vigentes_al_editar_y_cambiar_de_proyecto(self):
        w, e = self.vacio()
        ids = HC.grafcet_de_ejemplo(e)
        t = ids["transiciones"][0]
        ruta_id = f"{t}|{ids['etapas'][1]}|post"

        def puntos():
            base = routing.enlaces(e.M)
            self.assertEqual(enlaces(e.M), _ajustar_enlaces(e.M, base))
            return next(r["pts"] for r in enlaces(e.M) if r["id"] == ruta_id)

        antes = puntos()
        with patch.object(routing, "enlaces", wraps=routing.enlaces) as calcular:
            enlaces(e.M)
            enlaces(e.M)
            calcular.assert_not_called()
        e.ed.move(t, 420, 190)
        e.cambia()
        movidos = puntos()
        self.assertNotEqual(movidos, antes)
        e.deshacer()
        self.assertEqual(puntos(), antes)
        e.rehacer()
        self.assertEqual(puntos(), movidos)
        self.assertTrue(e.equidistanciar())
        self.assertNotEqual(puntos(), movidos)
        e.ed.dirty = False
        w.nuevo()
        self.assertEqual(enlaces(w.edicion.M), [])

    def test_SAD1_saltos_retornos_orientaciones_y_ruta_manual_recalculan(self):
        _, e = self.vacio()
        ids = HC.grafcet_de_ejemplo(e)
        t = ids["transiciones"][-1]
        lid = f"{t}|{ids['etapas'][0]}|post"
        self.assertTrue(next(r for r in enlaces(e.M) if r["id"] == lid)["arriba"])
        base = enlaces(e.M)
        modelo_t = next(tr for tr in e.M["transitions"] if tr["id"] == t)
        modelo_t["orient"] = "derecha"
        e.M.setdefault("linkStyles", {})[lid] = {"arrows": {"flow": {"visible": False}}}
        nuevas = enlaces(e.M)
        self.assertNotEqual(nuevas, base)
        self.assertEqual(nuevas, _ajustar_enlaces(e.M, routing.enlaces(e.M)))
        self.assertFalse(next(r for r in nuevas if r["id"] == lid)["arrows"])
        modelo_t["postDib"] = [ids["etapas"][1]]
        self.assertNotIn(lid, {r["id"] for r in enlaces(e.M)})
        rutas.vaciar()

    def test_SAD1_textos_se_reusan_y_se_actualizan_al_renombrar_y_parar(self):
        w, e = self.vacio()
        HC.grafcet_de_ejemplo(e)
        w.show()
        HC._bombear()

        def textos():
            return [i for i in w.diagrama.scene().items() if isinstance(i, QGraphicsTextItem)]

        anterior = next(i for i in textos() if i.toPlainText() == "marcha")
        w._redibujar_edicion()
        self.assertIn(anterior, textos())
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "marcha")
        self.assertIsNone(e.cambiar_variable(vid, nombre="Arranque"))
        self.assertNotIn("marcha", [i.toPlainText() for i in textos()])
        self.assertIn("Arranque", [i.toPlainText() for i in textos()])
        w.a_ejecutar.setChecked(True)
        w.rt.stop()
        HC._bombear()
        self.assertEqual(w.modo, "simular")
        simulacion = next(i for i in textos() if i.toPlainText() == "Arranque")
        w.a_ejecutar.setChecked(False)
        HC._bombear()
        self.assertNotIn(simulacion, textos())
        self.assertIn("Arranque", [i.toPlainText() for i in textos()])

    def test_SAD1_una_escena_y_limite_holgado_al_anadir_con_100_etapas(self):
        from escritorio import diagrama
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        sid = construir(c)
        aid = c.e.acciones(sid)[0]["id"]
        muestra(c, aid)
        original = diagrama.dibujar
        sueltas = []

        def contar_durante_suelta(punto):
            with patch.object(diagrama, "dibujar", wraps=original) as dibujo:
                resultado = soltar(punto)
                self.assertEqual(dibujo.call_count, 1)
                return resultado

        soltar = c.e.soltar
        with patch.object(c.e, "soltar", contar_durante_suelta):
            for _ in range(5):
                sueltas.append(muestra(c, aid)["total_ms"])
        self.assertLess(median(sueltas), 350, sueltas)

    def test_SAD2_el_aviso_enumera_etapas_en_orden_natural_y_sin_repetir(self):
        _, e = self.vacio()
        ed = e.ed
        etapas = {n: ed.add_step("g", str(n), initial=n == 1, at=(100, 60 * n)) for n in (10, 2, 4, 1)}
        vid = ed.add_variable("Tope 1", "output", {"kind": "bool"})
        for n in (10, 2, 2, 4):
            ed.add_continuous_action(etapas[n], vid)
        ed.add_stored_action(etapas[1], vid, "activation", "true")
        e.cambia()
        aviso = next(d for d in e.diagnosticos() if d["code"] == "D-MODO-SALIDA")
        self.assertEqual(aviso["message"],
                         "Tope 1 recibe acciones continuas (X2, X4 y X10) y memorizadas (X1) a la vez: use solo un tipo.")
        self.assertEqual(aviso["element"], vid)
        self.assertTrue(aviso["blocks"])
        self.assertFalse(ed.validate().can_simulate)

    def test_SAD3_la_ventana_no_salta_al_completar_o_editar_acciones(self):
        for tipo, variable, valor_primero in (
            ("evento", "aux", True), ("evento", "aux", False), ("evento", "Cuenta", False),
            ("condicionada", "luz", False),
        ):
            with self.subTest(tipo=tipo, variable=variable, valor_primero=valor_primero):
                self.probar_propiedades(tipo, variable, valor_primero)

    def probar_propiedades(self, tipo, variable, valor_primero):
        c = HC.Contexto(960, 1032)
        try:
            HC._edicion(c)
            c.e.nueva_variable("Cuenta", "output", {"kind": "int"})
            sid = c.ids["etapas"][0]
            aid = c.e.ed.add_draft_action((450, 180), {"tipo": tipo, "etapa": sid})
            c.e.cambia()
            c.w.editar_accion(sid, aid)
            HC._bombear()
            f = c.w.flot
            inicio = f.principal.geometry()
            sensor = CambiosGeometria()
            f.principal.installEventFilter(sensor)
            p = f.panel
            a = p.accion
            a.poner_variable(variable)
            if valor_primero:
                QTest.mouseClick(a.fichas["0"], Qt.MouseButton.LeftButton)
            p._desde_bloques("marcha" if tipo == "condicionada" else "↑marcha")
            if variable == "aux":
                for valor in ("1", "0"):
                    QTest.mouseClick(a.fichas[valor], Qt.MouseButton.LeftButton)
                    self.assertEqual(a.datos()["valor"], valor)
            if variable == "Cuenta":
                a._desde_bloques("1")
                self.assertEqual(a.datos()["valor"], "1")
            self.assertNotEqual(a.aid, aid)
            p._desde_bloques("")
            p._desde_bloques("paro" if tipo == "condicionada" else "↓paro")
            HC._bombear()
            self.assertTrue(f.principal.isVisible())
            self.assertEqual(f.principal.geometry(), inicio)
            self.assertEqual(sensor.cambios, [])
        finally:
            c.cerrar()

    def test_SAD4_dos_pasos_en_simultaneidad_con_acciones_normales(self):
        for explicita in (False, True):
            with self.subTest(explicita=explicita):
                _, e = self.vacio()
                ed = e.ed
                vid = ed.add_variable("Motor", "output", {"kind": "bool"})
                s0 = ed.add_step("g", "0", True, at=(100, 60))
                a = ed.add_step("g", "1", at=(100, 280))
                b = ed.add_step("g", "2", at=(460, 280))
                s3 = ed.add_step("g", "3", at=(100, 560))
                t1, _ = ed.add_transition("g", "1", [s0], [] if explicita else [a, b], at=(100, 140))
                t2, _ = ed.add_transition("g", "1", [] if explicita else [a, b], [s3], at=(100, 460))
                for sid in (a, b):
                    ed.add_continuous_action(sid, vid)
                if explicita:
                    for y, arriba, abajo in ((200, [t1], [a, b]), (380, [a, b], [t2])):
                        barra = ed.add_bar("Y", (100, y), 360)
                        for lado, ids in (("arriba", arriba), ("abajo", abajo)):
                            for ident in ids:
                                ed.bar_link(barra, lado, ident)
                e.cambia()
                antes = posiciones(e.M)
                self.assertTrue(e.equidistanciar())
                pos = posiciones(e.M)
                self.assertEqual((pos[a][1] - pos[t1][1], pos[t2][1] - pos[a][1]), (2 * DY, 2 * DY))
                self.assertEqual(pos[a][1], pos[b][1])
                self.assertEqual(e.equidistanciar(), [])
                e.deshacer()
                self.assertEqual(posiciones(e.M), antes)
                for _ in range(3):
                    ed.add_continuous_action(a, vid)
                ed.set_action_layout(a, "columna")
                e.cambia()
                self.assertTrue(e.equidistanciar())
                pos = posiciones(e.M)
                self.assertGreater(pos[t2][1] - pos[a][1], 2 * DY)
                self.assertEqual(e.equidistanciar(), [])
