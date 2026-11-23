"""SARR01..SARR03: los fotogramas de un arrastre de enlace (V2-E9) solo hacen la búsqueda del destino, y la hacen sin repetir trabajo."""
import json
import unittest
from pathlib import Path
from random import Random
from unittest import mock
from zipfile import ZipFile

from escritorio.geometria import marcos, seleccion
from escritorio.geometria.base import H, RADIO_ANCLA, Rect, posiciones
from grafcet.view import Vista, layout_from_presentation

REFERENCIA = Path(__file__).with_name("fixtures") / "referencia"


def ancho(segmentos, tamano=None):
    return sum(len(s["t"]) * 8 for s in segmentos)


def modelo_visual(nombre):
    with ZipFile(REFERENCIA / nombre) as z:
        modelo = next(json.loads(z.read(n)) for n in z.namelist() if n.startswith("model-"))
        presentacion = next(json.loads(z.read(n)) for n in z.namelist() if n.startswith("presentation-"))
    layout = layout_from_presentation(presentacion)
    return Vista(modelo["id"], "t", "", lambda: (modelo, layout), {}, presentation=presentacion).model


def ancla_en_antigua(M, p, radio=RADIO_ANCLA, sin_der=False):
    """`ancla_en` como era antes de E9 (`anclas` sin las posiciones: las rehace por cada elemento)."""
    best = None
    ocupadas = {s["id"] for s in M["steps"] if s["actions"]}
    ocupadas.update(d["etapa"] for d in M.get("draftActions", []) if d.get("etapa"))
    cuadrados = {s["id"] for s in M["steps"]} | {s["id"] for s in M.get("macros", [])}
    for ident, (cx, cy) in posiciones(M).items():
        if ident in cuadrados and Rect(cx - H + 2, cy - H + 2, 2 * H - 4, 2 * H - 4).contiene(p):
            continue
        for a in seleccion.anclas(M, ident):
            if a["lado"] == "der" and sin_der:
                continue
            d = ((a["pos"][0] - p[0]) ** 2 + (a["pos"][1] - p[1]) ** 2) ** 0.5
            limite = min(radio, 8) if a["lado"] == "der" and ident in ocupadas else radio
            if d <= limite and (best is None or d < best[0]):
                best = (d, a)
    for d in M.get("draftActions", []):
        for a in seleccion.anclas(M, d["id"]):
            dist = ((a["pos"][0] - p[0]) ** 2 + (a["pos"][1] - p[1]) ** 2) ** 0.5
            if dist <= radio and (best is None or dist < best[0]):
                best = (dist, a)
    for b in M.get("bars", []):
        bx, by, w, h = seleccion.barra(b)
        if bx - 4 <= p[0] <= bx + w + 4:
            x = min(max(p[0], bx), bx + w)
            for lado, y in (("arriba", by - 9), ("abajo", by + h + 9)):
                d = abs(p[1] - y)
                if d <= min(radio, 7) and (best is None or d < best[0]):
                    best = (d, {"id": b["id"], "lado": lado, "pos": (x, y)})
    return best[1] if best else None


class Fotogramas(unittest.TestCase):
    def test_SARR01_ancla_en_da_lo_mismo_que_la_version_que_rehacia_las_posiciones_por_elemento(self):
        """REQ-EDT-09: `ancla_en` coincide con la versión de antes en puntos al azar y sobre los puntos de unión de cada elemento, con y sin `sin_der`."""
        for nombre in ("guia_gemma.grafnet", "linea_larga.grafnet"):
            M = modelo_visual(nombre)
            azar = Random(5)
            pos = posiciones(M)
            puntos = [(x + azar.uniform(-30, 30), y + azar.uniform(-30, 30)) for x, y in azar.sample(sorted(pos.values()), min(60, len(pos)))]
            puntos += [a["pos"] for ident in list(pos)[:40] for a in seleccion.anclas(M, ident)]
            hallados = 0
            for p in puntos:
                for sin_der in (False, True):
                    esperado = ancla_en_antigua(M, p, sin_der=sin_der)
                    hallados += esperado is not None
                    self.assertEqual(seleccion.ancla_en(M, p, sin_der=sin_der), esperado, (nombre, p, sin_der))
            self.assertGreater(hallados, 20, nombre)

    def test_SARR02_marco_en_con_las_cajas_ya_calculadas_da_lo_mismo_y_sin_parciales_con_marco_no_las_calcula(self):
        """REQ-EDT-09: `marco_en` y `elemento_en` con las cajas de los parciales traídas dan lo mismo que sin ellas; un modelo sin recintos ni parciales no las calcula."""
        for nombre in ("guia_gemma.grafnet", "linea_larga.grafnet"):
            M = modelo_visual(nombre)
            cajas = marcos.cajas_parciales(M, medir=ancho)
            azar = Random(7)
            xs = [c["x0"] for c in cajas.values()] + [c["x1"] for c in cajas.values()]
            ys = [c["y0"] for c in cajas.values()] + [c["y1"] for c in cajas.values()]
            for _ in range(200):
                p = (azar.uniform(min(xs, default=0) - 20, max(xs, default=0) + 20), azar.uniform(min(ys, default=0) - 20, max(ys, default=0) + 20))
                self.assertEqual(seleccion.marco_en(M, p, medir=ancho, cajas=cajas), seleccion.marco_en(M, p, medir=ancho), (nombre, p))
                self.assertEqual(seleccion.elemento_en(M, p, ancho, lambda: None, cajas), seleccion.elemento_en(M, p, ancho, lambda: None), (nombre, p))
        M = modelo_visual("guia_gemma.grafnet")
        sin_marcos = dict(M, partials=[q for q in M.get("partials", []) if q["kind"] not in ("enclosure", "partial")])
        with mock.patch.object(seleccion, "cajas_parciales", side_effect=AssertionError("no debe calcularlas")):
            self.assertIsNone(seleccion.marco_en(sin_marcos, (0, 0), medir=ancho))

    def test_SARR03_un_arrastre_de_enlace_calcula_las_cajas_de_los_parciales_una_vez(self):
        """REQ-EDT-09: en los fotogramas de un arrastre de enlace, el destino se busca sin recalcular las cajas de los parciales en cada uno."""
        try:
            from PySide6.QtCore import QPointF
            from tools.entorno_v2_e0 import GEMMA, ventana
            from tools.hoja_contactos import _bombear as bombear
            from tools.medir_arrastre_enlace import candidatos
        except ImportError as exc:
            self.skipTest(str(exc))
        from escritorio.edicion import gestos
        with ventana() as w:
            self.assertTrue(w.abrir_ruta(GEMMA))
            bombear()
            e = w.edicion
            origen, destino = next(candidatos(e, "accion"))
            w.diagrama.centrar_en(origen)
            e.seleccionar([])
            real = gestos.cajas_parciales
            with mock.patch.object(gestos, "cajas_parciales", side_effect=real) as llamadas:
                e.prensar(origen)
                self.assertIsNotNone(e.enlace)
                for k in range(1, 9):
                    e.mover(origen + (destino - origen) * (k / 8))
                self.assertLessEqual(llamadas.call_count, 1)
                e.soltar(destino)
            self.assertIsNone(e._cajas_gesto)  # y al soltar se olvidan

    def test_SARR04_soltar_una_creacion_rehace_la_vista_lo_justo_y_deja_la_misma_que_rehacerla_otra_vez(self):
        """REQ-EDT-09: al soltar un enlace que crea una acción o una transición, la vista se rehace como mucho dos veces (antes, cuatro) y la que queda
        es igual a la que daría rehacerla de nuevo; el mensaje de estado y la selección son los de siempre."""
        try:
            from tools.entorno_v2_e0 import GEMMA, ventana
            from tools.hoja_contactos import _bombear as bombear
            from tools.medir_arrastre_enlace import candidatos
        except ImportError as exc:
            self.skipTest(str(exc))
        from escritorio.edicion import Edicion
        instantanea = lambda e: json.dumps([e.M, sorted(e.sel), e.accion], sort_keys=True, default=repr)  # noqa: E731
        with ventana() as w:
            self.assertTrue(w.abrir_ruta(GEMMA))
            bombear()
            e = w.edicion
            for tipo in ("accion", "desde_etapa"):
                with self.subTest(tipo=tipo):
                    origen, destino = next(candidatos(e, tipo))
                    w.diagrama.centrar_en(origen)
                    e.seleccionar([])
                    bombear()
                    antes = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.draft_actions()))
                    real = Edicion.reconstruir
                    with mock.patch.object(Edicion, "reconstruir", autospec=True, side_effect=real) as rehechas:
                        e.prensar(origen)
                        e.mover(destino)
                        rehechas.reset_mock()
                        e.soltar(destino)
                    self.assertNotEqual((len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.draft_actions())), antes)
                    self.assertLessEqual(rehechas.call_count, 2)
                    queda = instantanea(e)
                    e.reconstruir()
                    self.assertEqual(instantanea(e), queda, "la vista que quedó no es la que daría rehacerla")
                    e.deshacer()


if __name__ == "__main__":
    unittest.main()
