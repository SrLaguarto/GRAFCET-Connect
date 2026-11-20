"""Casos de geometría de escritorio que se ejecutan sin Qt."""
import json
import unittest
from itertools import islice
from pathlib import Path
from zipfile import ZipFile

from escritorio.geometria import acciones, choques, enlaces, equidistancia, marcos, seleccion, textos
from escritorio.geometria.base import PASO, REJILLA, Rect, caja_barra, posiciones
from grafcet import routing
from grafcet.editor import Editor, new_grafcet_document
from grafcet.view import Vista, layout_from_presentation

GEMMA = Path(__file__).with_name("fixtures") / "referencia" / "guia_gemma.grafnet"


def ancho(segmentos, tamano):
    return sum(len(s["t"]) * 8 for s in segmentos)


def medir_comentario(texto):
    return 100, 24


def vista(modelo, presentacion):
    layout = layout_from_presentation(presentacion)
    return Vista(modelo["id"], "Geométrica", "", lambda: (modelo, layout), {}, presentation=presentacion).model


def accion(ident, **campos):
    return {"id": ident, "kind": "continuous", "text": [{"t": ident}], **campos}


class Geometria(unittest.TestCase):
    def test_gemma_posiciones_anclas_marcos_y_enlaces(self):
        with ZipFile(GEMMA) as z:
            modelo = next(json.loads(z.read(n)) for n in z.namelist() if n.startswith("model-"))
            presentacion = next(json.loads(z.read(n)) for n in z.namelist() if n.startswith("presentation-"))
        M = vista(modelo, presentacion)
        inicial = next(s for s in M["steps"] if s["label"] == "70")
        sid = inicial["id"]
        pos = posiciones(M)
        self.assertEqual(pos[sid], (2500, 60))
        self.assertEqual([a["pos"] for a in seleccion.anclas(M, sid)], [(2500, 38), (2500, 82), (2522, 60)])
        self.assertEqual(seleccion.ancla_en(M, (2500, 38))["lado"], "arriba")
        self.assertEqual(seleccion.elemento_en(M, pos[sid], ancho, lambda: None), sid)

        base = routing.enlaces(M)
        ajustados = enlaces.enlaces(M)
        self.assertEqual([e["id"] for e in ajustados], [e["id"] for e in base])
        cuadros = marcos.cajas_parciales(M, medir=ancho)
        for e in ajustados:
            ref = e["sid"] if e["rol"] == "barra" else e["tid"]
            parcial = marcos.parciales_dibujo(M)[ref]
            if parcial in cuadros:
                self.assertTrue(all(Rect(*_recta(cuadros[parcial])).contiene(pt) for pt in e["pts"]))

    def test_cajas_de_receptividad_y_comentario_de_transicion_girada(self):
        t = {"id": "t1", "x": 200, "y": 140, "orient": "derecha", "cond": [{"t": "Marcha"}], "comment": "nota"}
        self.assertEqual(caja_barra("derecha", 300, 140), Rect(298, 132, 4, 16))
        etiqueta, formula = textos.rects_textos_t(t, 300, 140, ancho)
        self.assertEqual(etiqueta, Rect(284, 150, 32, 21))
        self.assertEqual(formula, Rect(276, 106, 48, 21))
        M = {"steps": [], "transitions": [t]}
        self.assertEqual(textos.rects_comentarios(M, ancho, medir_comentario), [("t1", Rect(338, 106, 100, 24))])

    def test_grupo_pegado_en_su_orden_y_colocacion_en_columna(self):
        a, b, c = [accion(n, grupo="grupo", x=80, y=100) for n in ("A", "B", "C")]
        M = {"steps": [], "transitions": [], "draftActions": [a, b, c], "actionLayouts": {"grupo": "columna"}}
        cajas = acciones.colocadas(M, ancho)
        self.assertEqual([(k["id"], k["rect"]) for k in cajas],
                         [("A", (180, 78, 80, 44)), ("B", (180, 134, 80, 44)), ("C", (180, 190, 80, 44))])
        iman = acciones.iman_en_punto(cajas, (259, 156), 14, ("A",))
        self.assertEqual(iman, {"objetivo": "B", "linea": ((260, 134), (260, 178))})

    def test_choque_desplazamiento_por_rejilla_y_hueco_para_pegar(self):
        paso = {"id": "dueño", "x": 0, "y": 100, "actions": [accion("Motor")]}
        vecino = {"id": "vecino", "x": 150, "y": 100, "actions": []}
        M = {"steps": [paso, vecino], "transitions": []}
        resultado = choques.choques(M, "dueño", "fila", (), ancho, medir_comentario)
        self.assertEqual(resultado, [(Rect(228, 78, 44, 44), 250, 228, 236)])
        corte = choques.proximo_desplazamiento([(228, 250, 228, 236)], 122, 0)
        self.assertEqual(corte, (250, 20))
        self.assertIsNone(choques.proximo_desplazamiento([(228, 250, 228, 236)], 229, 0))
        plan = choques.plan_desplazamiento(M, [], [], {}, *corte, "dueño")
        self.assertEqual(plan.nodos, [("vecino", 170, 100)])
        self.assertEqual(list(islice(choques.posiciones_hueco((100, 120)), 5)),
                         [(0, 0), (-20, 0), (0, -20), (0, 20), (20, 0)])

        linea = Rect(0, 1, 2, 0)
        cuadrado = Rect(0, 0, 2, 2)
        self.assertTrue(choques.toca(linea, cuadrado))
        self.assertFalse(linea.intersects(cuadrado))

    def test_equidistancia_reserva_la_columna_de_acciones(self):
        # El caso SEDI249 reserva 160 unidades antes de la segunda transición.
        ed = Editor(new_grafcet_document("equidistancia"))
        a = ed.add_step("g", "0", True, at=(100, 60))
        b = ed.add_step("g", "1", at=(100, 240))
        t1, _ = ed.add_transition("g", "false", [a], [b], at=(100, 180))
        t2, _ = ed.add_transition("g", "false", [b], at=(100, 420))
        for nombre in ("Q00", "Q01", "Q02"):
            destino = ed.add_variable(nombre, "output", {"kind": "bool"})
            ed.add_continuous_action(b, destino)
        ed.set_action_layout(b, "columna")
        M = vista(ed.model, ed.presentation)
        ext = equidistancia.extensiones(M, ancho)
        self.assertEqual(ext[b], (22, 134))
        pos = equidistancia.posiciones_modelo(M)
        equidistancia.equidistribuir(ed, M, [a], pos, ext, PASO, choques.MARGEN_SOLAPE, REJILLA)
        nuevos = layout_from_presentation(ed.presentation)
        self.assertEqual([nuevos[i][1] for i in (a, t1, b, t2)], [60, 120, 180, 340])

    def test_banderita_de_evento_no_aumenta_el_paso(self):
        a = accion("A", kind="stored", trigger="event", event=[{"t": "↑Pulso"}])
        M = {"steps": [{"id": "s", "x": 0, "y": 100, "actions": [a]}], "transitions": []}
        self.assertEqual(equidistancia.extensiones(M, ancho), {"s": (22, 22)})

    def test_ajuste_de_simultaneidad_y_pegado_a_tramo_paralelo(self):
        M = {"steps": [{"id": "a", "x": 0, "y": 0}], "transitions": [
            {"id": "t", "x": 0, "y": 100, "pre": ["a"], "post": []},
        ]}
        original = {"id": "a|t", "tid": "t", "simul": True, "rol": "pre", "pts": [(100, 22), (100, 78)]}
        ajustado, = enlaces._ajustar_enlaces(M, [original])
        self.assertEqual(ajustado["pts"], [(100, 22), (100, 52)])
        self.assertEqual(original["pts"][-1], (100, 78))
        paralelo = {"id": "otra", "pts": [(0, 46), (100, 46)]}
        self.assertEqual(enlaces.pegar_a_paralelo([paralelo], 40, False, "propio", (60, 160)), 46)
        self.assertEqual(enlaces.pegar_a_paralelo([paralelo], 40, False, "propio", (106, 160)), 40)


def _recta(b):
    return b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"]
