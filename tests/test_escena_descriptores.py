"""SESC01..SESC04: la grabadora de descriptores del dibujo (V2-E3, paso 1)."""
from importlib.util import find_spec
from unittest import TestCase, skipUnless

from escritorio.escena.descriptores import Grabadora, Servicios

QT = bool(find_spec("PySide6"))


def servicios_falsos():
    return Servicios(
        contenido=lambda segs, verdaderos: "".join(s["t"] for s in segs), negados=lambda segs: [
            (i, i + 1) for i, s in enumerate(segs) if s.get("o")],
        medir=lambda contenido, size, bold, mono: (7.0 * len(contenido), 1.5 * size),
        limites_de=lambda contenido, size, bold, mono, segs: [float(i * 7) for i in range(len(segs) + 1)],
        ancho=lambda segs, size, bold=False: 7.0 * sum(len(s["t"]) for s in segs), limites=lambda *a, **k: [0.0],
        ascenso=lambda size, bold=False: 0.8 * size, ascenso_texto=lambda size, bold, mono: 0.8 * size,
        alto_comentario=lambda texto, ancho: 20.0, grosor_negado=1.25, ancho_comentario=240.0)


class Grabadora_(TestCase):
    def test_SESC01_primitivas_con_parcial_y_elementos(self):
        """REQ-EDT-01: cada primitiva queda anotada como una tupla comparable, con su parcial y sus elementos."""
        g = Grabadora(servicios_falsos())
        g.parcial, g.elementos = "g", ("s1",)
        pluma = g.pen("text", 2.4, (5, 4))
        g.line(0, 0, 10, 0, pluma, 1.0, "tip")
        g.poly([(0, 0), (5, 5)], pluma, 1.0)
        g.rect(1, 2, 3, 4, None, 3.0, "panel", radius=16)
        g.circle(5, 5, 3.5, "active", 3.05)
        tipos = [d[0] for _, d in g.secuencia]
        self.assertEqual(tipos, ["linea", "camino", "rect", "elipse"])
        self.assertEqual(g.secuencia[0][1], ("linea", 0, 0, 10, 0, ("pluma", "text", 2.4, (5, 4)), 1.0, "tip", "g", ("s1",)))
        self.assertEqual(g.secuencia[2][1][:6], ("rect", 1, 2, 3, 4, None))
        again = Grabadora(servicios_falsos())
        again.parcial, again.elementos = "g", ("s1",)
        again.line(0, 0, 10, 0, again.pen("text", 2.4, (5, 4)), 1.0, "tip")
        self.assertEqual(again.secuencia[0], g.secuencia[0])

    def test_SESC02_texto_devuelve_su_ancho_y_anota_negacion_y_halo(self):
        """REQ-EDT-01: un texto anota su sitio según el ancla, la barra de cada tramo negado y el fondo del rótulo."""
        g = Grabadora(servicios_falsos())
        segs = [{"t": "ab"}, {"t": "cd", "o": True}]
        w = g.text(100, 50, segs, 10, "text", 3.0, "middle", halo=True)
        self.assertEqual(w, 28.0)
        tipos = [d[0] for _, d in g.secuencia]
        self.assertEqual(tipos, ["texto", "linea", "rect"])
        texto = g.secuencia[0][1]
        self.assertEqual((texto[1], texto[2], texto[3], texto[4], texto[5], texto[6]), ("abcd", "text", (10, False, False), 86.0, 42.0, 3.02))
        self.assertEqual(g.text(0, 0, None, 10, "text", 3.0), 0.0)
        self.assertEqual(len(g.secuencia), 3)

    def test_SESC03_grupos_en_orden_de_aparicion(self):
        """REQ-EDT-01: lo anotado pertenece al grupo actual y el orden de los grupos es el de su primer descriptor; volver a un
        grupo del que se salió abre otro con clave propia (cada clave es contigua)."""
        g = Grabadora(servicios_falsos())
        g.entrar(("etapa", "s1"))
        g.line(0, 0, 1, 1, g.pen("text"), 1)
        previo = g.entrar(("comentario", "s1"))
        g.comentario(10, 20, "hola", 3.0)
        g.entrar(previo)
        g.circle(0, 0, 1, "active", 3)
        g.entrar(("etapa", "s2"))
        g.line(0, 0, 2, 2, g.pen("text"), 1)
        segundo = ("etapa", "s1", "#2")
        self.assertEqual(g.orden, (("etapa", "s1"), ("comentario", "s1"), segundo, ("etapa", "s2")))
        self.assertEqual([d[0] for d in g.objetos[("etapa", "s1")]], ["linea"])
        self.assertEqual([d[0] for d in g.objetos[segundo]], ["elipse"])
        self.assertEqual(g.objetos[("comentario", "s1")][0][:5], ("comentario", "hola", 240.0, 10, 10.0))
        self.assertEqual([c for c, _ in g.secuencia], [("etapa", "s1"), ("comentario", "s1"), segundo, ("etapa", "s2")])

    def test_SESC04_notas_congeladas(self):
        """REQ-EDT-01: una nota se anota como datos inmutables con su selección."""
        g = Grabadora(servicios_falsos())
        g.notas({"annotations": [{"id": "n1", "kind": "text", "x": 1, "text": "a", "tags": ["u", "v"]}]}, {"n1"})
        (clave, d), = g.secuencia
        self.assertEqual(clave, ("nota", "n1"))
        self.assertTrue(d[2])
        hash(d)


@skipUnless(QT, "requiere PySide6")
class GrabadoraConQt(TestCase):
    def test_SESC04b_cada_figura_directa_tiene_su_descriptor(self):
        """REQ-EDT-01: sobre la guía GEMMA, la grabadora anota tantos descriptores de cada tipo como ítems crea el dibujo directo
        y un grupo por cada elemento."""
        from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsRectItem,
                                       QGraphicsScene, QGraphicsTextItem)
        from escritorio import diagrama as dg
        from tools.entorno_v2_e0 import GEMMA, ventana
        from tools.choque_escena import reiniciar
        with ventana() as w:
            reiniciar(w, GEMMA)
            e = w.edicion
            sel = e.seleccion_dibujo() | {e.ed.model["steps"][0]["id"]}
            marcados = {e.ed.model["transitions"][0]["id"]}
            escena = QGraphicsScene()
            dg._recorrer(dg._Pintor(escena), e.M, {}, sel, marcados, {e.ed.model["steps"][1]["id"]}, [], [], True)
            g = Grabadora(dg.servicios())
            cajas_g = dg._recorrer(g, e.M, {}, sel, marcados, {e.ed.model["steps"][1]["id"]}, [], [], True)
            items = escena.items()
            cuenta = lambda clase: sum(type(i) is clase for i in items)  # noqa: E731
            d = [x for _, x in g.secuencia]
            self.assertEqual(cuenta(QGraphicsLineItem), sum(x[0] == "linea" for x in d))
            self.assertEqual(cuenta(QGraphicsEllipseItem), sum(x[0] == "elipse" for x in d))
            self.assertEqual(cuenta(QGraphicsRectItem), sum(x[0] == "rect" and not x[7] for x in d))
            self.assertEqual(cuenta(QGraphicsPathItem), sum(x[0] == "camino" or (x[0] == "rect" and bool(x[7])) for x in d))
            self.assertEqual(cuenta(QGraphicsTextItem), sum(x[0] in ("texto", "comentario") for x in d))
            claves = set(g.objetos)
            for s in e.ed.model["steps"]:
                self.assertIn(("etapa", s["id"]), claves)
            for t in e.ed.model["transitions"]:
                self.assertIn(("transicion", t["id"]), claves)
            for r in e.M["links"]:
                self.assertIn(("enlace", r["id"]), claves)
            self.assertTrue(all(c != ("sin_grupo",) for c, _ in g.secuencia))
            self.assertTrue(cajas_g)
