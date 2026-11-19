"""SAB1..SAB5: encargo AB (1.1.7): comentarios de transición junto a su receptividad y sin superposiciones, y equidistancia
con un único paso."""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_editor_cadenas import BaseQt, QT  # noqa: E402

if QT:
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtWidgets import QApplication
    from escritorio import edicion as modulo
    from escritorio.diagrama import SX, posiciones, rects_comentarios
    from grafcet.view import layout_from_presentation

COMENTARIO = "Retorno cada pareja… “ya han salido 2 por cada lado”"


@unittest.skipUnless(QT, "requiere PySide6")
class EncargoAB(BaseQt):
    @staticmethod
    def bombear(n=5):
        for _ in range(n):
            QApplication.processEvents()

    def abierta(self):
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        self.bombear()
        return w, e

    def textos(self, w, e):
        """{texto: rectángulo en la escena} de lo que se dibuja."""
        self.bombear()
        return {i.toPlainText(): i.sceneBoundingRect() for i in w.diagrama.scene().items()
                if type(i).__name__ == "QGraphicsTextItem"}

    def pos(self, e):
        return layout_from_presentation(e.ed.presentation)

    def separados(self, w, e, tid, cond, margen=10):
        """El comentario de la transición está a la derecha de su receptividad, sin tocarla (con `margen` de aire)."""
        t = self.textos(w, e)
        c = t[cond]
        com = next(r for k, r in t.items() if k.startswith("“Retorno"))
        self.assertGreaterEqual(com.left(), c.right() + margen, f"comentario {com.getRect()} sobre receptividad {c.getRect()}")
        self.assertFalse(com.intersects(c))
        return c, com

    # -- AB1 -------------------------------------------------------------------------------------------------------
    def test_SAB1a_el_comentario_empieza_a_la_derecha_de_la_receptividad_larga_con_etiqueta(self):
        """REQ-EDT-09: con la etiqueta (tN) a la izquierda y una receptividad larga con sufijo «· condición», el comentario
        empieza a la derecha de su final con el margen de siempre."""
        w, e = self.abierta()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (220, "1"), (300, None)), x=100, entradas=("marcha", "paro"))
        e.poner_condicion(ids[1], "rise(marcha) AND paro")
        e.poner_comentario(ids[1], COMENTARIO)
        c, com = self.separados(w, e, ids[1], "↑marcha · paro", margen=14)
        self.assertAlmostEqual(com.left() - c.right(), 14, delta=1.5)

    def test_SAB1b_en_una_divergencia_tampoco_se_monta(self):
        """REQ-EDT-09: dos transiciones que salen de una misma etapa (divergencia): el comentario de cada una queda a la
        derecha de su receptividad."""
        w, e = self.abierta()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (220, "1")), x=0, entradas=("marcha", "paro"))
        e.nueva_variable("sel", "input")
        otra = e.poner_transicion(QPointF(SX + 300, 140))
        e.conectar(ids[0], otra)
        e.poner_condicion(otra, "rise(sel) AND paro")
        e.poner_comentario(otra, COMENTARIO)
        e.poner_condicion(ids[1], "rise(marcha) AND paro")
        e.poner_comentario(ids[1], COMENTARIO.replace("pareja", "pareja otra"))
        t = self.textos(w, e)
        for cond in ("↑sel · paro", "↑marcha · paro"):
            c = t[cond]
            otros = [r for k, r in t.items() if k.startswith("“Retorno") and abs(r.center().y() - c.center().y()) < 12
                     and r.left() > c.left()]
            self.assertTrue(otros)
            self.assertGreaterEqual(min(r.left() for r in otros), c.right() + 13)

    def test_SAB1c_en_un_retorno_o_un_salto_tampoco_se_monta(self):
        """REQ-EDT-09: la transición que vuelve a la etapa inicial, de evolución hacia abajo y con la evolución girada
        (tramo horizontal), deja su comentario a la derecha de la receptividad."""
        w, e = self.abierta()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (220, "1"), (300, None)), x=100, entradas=("marcha", "paro"))
        e.conectar(ids[3], ids[0])  # la última transición vuelve a la etapa inicial
        e.poner_condicion(ids[3], "rise(marcha) AND paro")
        e.poner_comentario(ids[3], COMENTARIO)
        self.separados(w, e, ids[3], "↑marcha · paro", margen=14)
        for giro in ("izquierda", "derecha"):
            e.ed.set_transition_orientations({ids[3]: giro})
            e.cambia()
            c, com = self.separados(w, e, ids[3], "↑marcha · paro", margen=14)

    def test_SAB1d_una_transicion_a_la_izquierda_del_origen_no_manda_su_comentario_a_x_8(self):
        """REQ-EDT-09: causa de AB1 y AB4: sin temporizador, `derecha` valía 0 y el comentario nunca empezaba antes de la x 8 del
        dibujo; una transición a la izquierda de ahí (la rama de un retorno) lo tenía montado sobre otras o lejos de ella."""
        w, e = self.abierta()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (220, "1"), (300, None)), x=-500, entradas=("marcha", "paro"))
        e.poner_condicion(ids[1], "rise(marcha) AND paro")
        e.poner_comentario(ids[1], "Retorno: otra pareja")
        tx = posiciones(e.M)[ids[1]][0]
        self.assertLess(tx + 200, 0, "la transición y su receptividad quedan a la izquierda de x = 0")
        c, com = self.separados(w, e, ids[1], "↑marcha · paro", margen=14)
        self.assertAlmostEqual(com.left() - c.right(), 14, delta=1.5)
        e.ed.set_transition_orientations({ids[1]: "izquierda"})  # y con el tramo horizontal (AB4)
        e.cambia()
        c, com = self.separados(w, e, ids[1], "↑marcha · paro", margen=14)
        self.assertAlmostEqual(com.left() - c.right(), 14, delta=1.5)

    # -- AB4 -------------------------------------------------------------------------------------------------------
    def test_SAB4_el_comentario_de_una_transicion_de_retorno_esta_junto_a_ella_y_la_sigue(self):
        """REQ-EDT-09: el comentario de una transición en un tramo horizontal está junto a su receptividad (a su derecha) y
        se mueve con ella al moverla."""
        w, e = self.abierta()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (220, "1"), (300, None)), x=100, entradas=("marcha", "paro"))
        e.conectar(ids[3], ids[0])
        e.poner_condicion(ids[3], "rise(marcha) AND paro")
        e.poner_comentario(ids[3], COMENTARIO)
        e.ed.set_transition_orientations({ids[3]: "izquierda"})
        e.cambia()
        c, com = self.separados(w, e, ids[3], "↑marcha · paro", margen=14)
        tx, ty = posiciones(e.M)[ids[3]]
        self.assertLess(abs(com.center().y() - c.center().y()), 12, "en la altura de su receptividad")
        self.assertLess(com.left() - c.right(), 20, "pegado, no lejos")
        for dx, dy in ((200, 0), (0, 60), (-80, 40)):
            e.ed.move(ids[3], tx - SX + dx, ty + dy)
            e.cambia()
            c2, com2 = self.separados(w, e, ids[3], "↑marcha · paro", margen=14)
            self.assertAlmostEqual(com2.left() - c2.right(), com.left() - c.right(), delta=1)
            self.assertAlmostEqual(com2.center().y() - c2.center().y(), com.center().y() - c.center().y(), delta=1)
            e.ed.move(ids[3], tx - SX, ty)
            e.cambia()

    # -- AB2 -------------------------------------------------------------------------------------------------------
    def test_SAB2a_los_comentarios_de_etapas_y_transiciones_cuentan_como_obstaculos(self):
        """REQ-EDT-05: soltar una etapa sobre el comentario de una etapa o de una transición no la coloca y avisa."""
        w, e = self.abierta()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (220, "1"), (300, None)), x=0, entradas=("marcha", "paro"))
        e.poner_comentario(ids[0], "Esperar a que el operario esté listo")
        e.poner_comentario(ids[1], "Comentario de la transición")
        self.bombear()
        rects = dict(rects_comentarios(e.M))
        self.assertEqual(set(rects), {ids[0], ids[1]})
        for ident in (ids[0], ids[1]):
            n = len(e.M["steps"])
            e.colocar("etapa", QPointF(rects[ident].center().x() + 20, rects[ident].center().y()))
            self.assertEqual((len(e.M["steps"]), e.mensaje), (n, modulo.MSG_SOLAPE), f"comentario de {ident}")
        # y fuera del comentario sí cabe
        n = len(e.M["steps"])
        e.colocar("etapa", QPointF(rects[ids[0]].right() + 120, rects[ids[0]].center().y() + 200))
        self.assertEqual(len(e.M["steps"]), n + 1)

    def test_SAB2b_las_acciones_nuevas_apartan_el_comentario_de_otra_transicion_en_vez_de_taparlo(self):
        """REQ-EDT-05: abrir hueco a las acciones de una etapa aparta a la derecha, con su transición, un comentario que
        quedaba en su camino; no quedan encima ni se avisa."""
        w, e = self.abierta()
        a = self.cadena(e, filas=((60, "0"), (140, None), (220, "1")), x=0, entradas=("marcha",))
        b = self.cadena(e, filas=((60, "2"), (140, None), (220, "3")), x=330, entradas=("paro",))
        e.poner_comentario(b[1], "Un comentario largo que se extiende bastante hacia la derecha")
        e.poner_comentario(b[0], "Nota de la etapa 2")
        self.bombear()
        x0 = posiciones(e.M)[b[0]][0]
        for n in range(4):
            e.nueva_variable(f"Salida{n}", "output")
            self.assertIsNone(e.poner_accion(a[0], {"tipo": "continua", "variable": f"Salida{n}"}))
            self.bombear()
            self.assertNotEqual(e.mensaje, modulo.MSG_ENCIMA)
            self.assertEqual(e.parpadeo.ids, set(), "no parpadea nada")
        self.assertGreater(posiciones(e.M)[b[0]][0], x0, "la otra columna se apartó")
        cajas = [QRectF(*c["rect"]) for c in e.diagrama.cajas_acciones]
        for ident, r in rects_comentarios(e.M):
            self.assertFalse(any(r.intersects(c) for c in cajas), f"comentario de {ident} tapado por una acción")

    def test_SAB2c_un_comentario_que_ya_chocaba_antes_no_hace_parpadear(self):
        """REQ-EDT-09: un comentario que ya se montaba sobre una etapa antes de la operación no dispara el aviso de «queda
        encima» ni el parpadeo al añadir acciones a otra etapa (AA1)."""
        w, e = self.abierta()
        a = self.cadena(e, filas=((60, "0"), (140, None), (220, "1")), x=0, entradas=("marcha",))
        b = self.cadena(e, filas=((300, "2"), (380, None), (460, "3")), x=60, entradas=("paro",))
        e.poner_comentario(a[2], "Comentario que llega hasta la etapa de abajo y más allá todavía")
        e.ed.move(b[0], 60 + 40, 220)  # la etapa 2 queda dentro del comentario de la etapa 1: un choque previo
        e.cambia()
        self.bombear()
        r = dict(rects_comentarios(e.M))[a[2]]
        self.assertTrue(r.intersects(QRectF(posiciones(e.M)[b[0]][0] - 22, 198, 44, 44)), "el choque ya existe")
        x, y = posiciones(e.M)[a[0]]
        for _ in range(2):
            e.colocar("accion:continua", QPointF(x + 300, y))
            self.bombear()
            self.assertEqual(e.parpadeo.ids, set())
            self.assertNotEqual(e.mensaje, modulo.MSG_ENCIMA)

    def test_SAB2d_soltar_con_90_elementos_no_empeora(self):
        """REQ-EDT-02: con 90 elementos (la mitad con comentario) el coste de decidir si lo que se suelta cabe es de milisegundos
        y los comentarios no lo multiplican."""
        w, e = self.abierta()
        for k in range(3):
            filas = tuple((60 + 80 * n, str(n + 30 * k) if n % 2 == 0 else None) for n in range(30))
            ids = self.cadena(e, filas=filas, x=k * 400, entradas=("marcha", "paro"))
            for i in ids[1::4]:
                e.poner_comentario(i, "Comentario de prueba" if i != ids[1] else "Otro")
            for i in ids[::4]:
                e.poner_comentario(i, "Nota de la etapa")
        self.bombear()
        self.assertGreaterEqual(len(e.M["steps"]) + len(e.M["transitions"]), 90)

        def medir():
            t = time.perf_counter()
            for _ in range(20):
                e._huella_ficha("etapa", QPointF(SX + 1700, 200))
            return (time.perf_counter() - t) / 20 * 1000
        con = min(medir() for _ in range(3))
        with mock.patch.object(modulo, "rects_comentarios", lambda M: []):
            sin = min(medir() for _ in range(3))
        self.assertLess(con, 25, f"con comentarios: {con:.2f} ms")
        self.assertLess(con, sin * 3 + 3, f"con comentarios {con:.2f} ms, sin {sin:.2f} ms")

    # -- AB3 -------------------------------------------------------------------------------------------------------
    def test_SAB3_al_equidistanciar_la_barra_de_simultaneidad_es_un_elemento_mas_de_la_cadena(self):
        """REQ-EDT-02, REQ-EDT-03: la distancia de una transición a una barra de simultaneidad, y la de la barra a las
        etapas que salen de ella, es el paso (DY), como entre etapa y transición."""
        w, e = self.abierta()
        ids = self.cadena(e, filas=((60, "0"), (140, None), (240, "1"), (300, None)), x=100)
        e.colocar("etapa", QPointF(SX + 20, 580))
        e.colocar("etapa", QPointF(SX + 260, 600))
        a, b = e.M["steps"][-2]["id"], e.M["steps"][-1]["id"]
        barra = e.poner_barra(QPointF(SX + 200, 440), "Y")
        self.unir(e, ids[3], "abajo", barra, "arriba")
        for x in (a, b):
            self.unir(e, x, "arriba", barra, "abajo")
        self.assertIsNotNone(e.equidistanciar(None))
        pos = self.pos(e)
        by = float(next(x for x in e.ed.bars() if x["id"] == barra)["y"])
        self.assertEqual((by - pos[ids[3]][1], pos[a][1] - by, pos[b][1] - by), (modulo.DY,) * 3)

    def divergencia_y_convergencia(self, e):
        """0 -t1- (1, 2) simultáneas -t2- 3: la transición t1 con dos etapas detrás (doble trazo bajo ella) y t2 con dos delante
        (doble trazo sobre ella), con gestos del editor."""
        e.nueva_variable("marcha", "input")
        ed = e.ed
        s0 = ed.add_step("g", "0", True, at=(100, 60))
        a, b = ed.add_step("g", "1", at=(40, 200)), ed.add_step("g", "2", at=(160, 200))
        s3 = ed.add_step("g", "3", at=(100, 360))
        t1, _ = ed.add_transition("g", "marcha", pre=[s0], post=[a, b], at=(100, 120), label="t1")
        t2, _ = ed.add_transition("g", "marcha", pre=[a, b], post=[s3], at=(100, 300), label="t2")
        e.cambia()
        return s0, t1, a, b, t2, s3

    def test_SAB3b_la_doble_linea_de_la_transicion_es_un_elemento_mas_de_la_cadena(self):
        """REQ-EDT-02, REQ-EDT-03: al equidistanciar, la doble línea de una divergencia (bajo su transición) y la de una
        convergencia (sobre la suya) quedan a un paso (DY) de la transición y a un paso de la etapa; el dibujo, los enlaces y
        los puntos de unión las siguen; un dibujo sin equidistanciar no cambia."""
        from escritorio.diagrama import BARRA_GROSOR, SIMUL, anclas, enlaces
        w, e = self.abierta()
        s0, t1, a, b, t2, s3 = self.divergencia_y_convergencia(e)
        ts = {t["id"]: t for t in e.M["transitions"]}
        self.assertTrue(ts[t1]["simulPost"] and ts[t2]["simulPre"])
        pos = posiciones(e.M)
        lineas = lambda: sorted({round(i.line().y1(), 1) for i in w.diagrama.scene().items()  # noqa: E731
                                 if type(i).__name__ == "QGraphicsLineItem" and i.line().y1() == i.line().y2()
                                 and i.line().x2() - i.line().x1() > 100})
        self.bombear()
        antes = lineas()
        self.assertIn(round(pos[t1][1] + SIMUL, 1), antes, "sin equidistanciar: a 14, como siempre")
        self.assertIsNotNone(e.equidistanciar(None))
        pos = posiciones(e.M)
        self.assertEqual((pos[a][1] - pos[t1][1], pos[t2][1] - pos[a][1]), (2 * modulo.DY, 2 * modulo.DY))
        self.assertEqual(pos[a][1], pos[b][1])
        ly = lineas()
        for y in (pos[t1][1] + modulo.DY, pos[t1][1] + modulo.DY + BARRA_GROSOR, pos[t2][1] - modulo.DY,
                  pos[t2][1] - modulo.DY - BARRA_GROSOR):
            self.assertIn(round(y, 1), ly)
        self.assertEqual((pos[a][1] - (pos[t1][1] + modulo.DY + BARRA_GROSOR) - 22,), (modulo.DY - BARRA_GROSOR - 22,))
        # los enlaces llegan a la doble línea nueva y los puntos de unión quedan fuera de ella
        ya = {(l["tid"], l["rol"]): l["pts"] for l in enlaces(e.M) if l["sid"] in (a, b)}
        self.assertEqual(ya[(t1, "post")][0][1], pos[t1][1] + modulo.DY + BARRA_GROSOR)
        self.assertEqual(ya[(t2, "pre")][-1][1], pos[t2][1] - modulo.DY - BARRA_GROSOR)
        an = {x["lado"]: x["pos"].y() for x in anclas(e.M, t1)}
        self.assertGreater(an["abajo"], pos[t1][1] + modulo.DY + BARRA_GROSOR)
        self.assertEqual(e.equidistanciar(None), [], "ya está equidistanciado")

    def test_SAB3c_tools_dibujo_js_dibuja_la_doble_linea_como_qt(self):
        """REQ-EDT-02: tools/dibujo.js y escritorio/diagrama.py colocan igual la doble línea de una transición con hueco de dos pasos."""
        from test_dibujo_vista import QJS, dibujar_con_js
        if not QJS:
            self.skipTest("requiere QtQml")
        from escritorio.diagrama import enlaces
        w, e = self.abierta()
        s0, t1, a, b, t2, s3 = self.divergencia_y_convergencia(e)
        e.equidistanciar(None)
        self.bombear()
        modelo = dict(e.M, links=[dict(l, pts=[list(p) for p in l["pts"]]) for l in enlaces(e.M)])

        def dobles(nodo, out):
            if "dbl" in str((nodo.get("attrs") or {}).get("class", "")) and nodo.get("tag") == "line":
                out.add(round(float(nodo["attrs"]["y1"]), 1))
            for h in nodo.get("hijos", nodo.get("children", [])):
                dobles(h, out)
            return out
        js = dobles(dibujar_con_js(modelo, e.vista.state()), set())
        pos = posiciones(e.M)
        esperado = {round(pos[t1][1] + modulo.DY, 1), round(pos[t1][1] + modulo.DY + 8, 1),
                    round(pos[t2][1] - modulo.DY, 1), round(pos[t2][1] - modulo.DY - 8, 1)}
        self.assertEqual(js, esperado)

    # -- AB5 -------------------------------------------------------------------------------------------------------
    def test_SAB5_todas_las_cadenas_comparten_un_unico_paso_salvo_los_huecos_que_lo_piden(self):
        """REQ-EDT-03, REQ-EDT-05: tras equidistanciar, entre etapa y transición hay siempre DY, en todas las cadenas y ramas;
        solo se agranda (en múltiplos de la rejilla) el hueco de una etapa con una acción por evento (banderita), y las
        transiciones en tramo horizontal no cuentan para el paso vertical."""
        w, e = self.abierta()
        a = self.cadena(e, filas=((60, "0"), (150, None), (250, "1"), (310, None), (440, "2"), (500, None)), x=0,
                        entradas=("marcha", "paro", "sel"))
        b = self.cadena(e, filas=((80, "3"), (170, None), (300, "4"), (380, None)), x=400, entradas=("m2", "p2"))
        # una rama más desde la etapa 2 (divergencia) y los retornos, uno de ellos con la evolución girada
        rama = e.poner_transicion(QPointF(SX - 160, 500))
        e.conectar(a[4], rama)
        e.conectar(rama, a[2])
        e.poner_condicion(rama, "marcha")
        e.conectar(a[5], a[0])
        e.ed.set_transition_orientations({b[3]: "izquierda"})
        e.conectar(b[3], b[0])
        # la etapa 2 con una acción por evento (lleva banderita)
        e.nueva_variable("C", "output")
        e.poner_accion(a[4], {"tipo": "evento", "variable": "C", "valor": "1", "evento": "rise(marcha)"})
        e.cambia()
        self.bombear()
        self.assertIsNotNone(e.equidistanciar(None))
        pos = self.pos(e)
        extra = e._extensiones()
        self.assertEqual(extra[a[4]][0], 22, "la banderita no cuenta: la etapa ocupa lo mismo que con una acción normal")
        self.assertEqual(modulo.DY, 60)
        huecos = []
        for cadena in ([*a, rama], b):  # cada cadena por sus niveles (las dos conservan la altura de su primer elemento)
            niveles = sorted({round(pos[i][1]) for i in cadena})
            huecos.append([y2 - y1 for y1, y2 in zip(niveles, niveles[1:])])
        self.assertEqual(huecos[0], [modulo.DY] * 5, "también el hueco de la etapa 2, la de la banderita")
        self.assertEqual(huecos[1], [modulo.DY] * 3, "la otra cadena, sin acciones, con el mismo paso")
        self.assertEqual(pos[rama][1], pos[a[5]][1], "la rama comparte nivel con su hermana")
        # la banderita (con su evento) no pisa la transición de encima: se mide lo que se dibuja
        self.bombear()
        textos = {i.toPlainText(): i.sceneBoundingRect() for i in w.diagrama.scene().items() if type(i).__name__ == "QGraphicsTextItem"}
        evento, cond = textos["↑marcha"], textos["paro"]
        self.assertFalse(evento.intersects(cond))
        self.assertGreater(evento.top() - cond.bottom(), 0, f"banderita {evento.getRect()} y transición {cond.getRect()}")
        self.assertGreaterEqual(evento.top() - cond.bottom(), 5, "a 60 quedan 7 px entre el texto del evento y el de la transición")


@unittest.skipUnless(QT, "requiere PySide6")
class EncargoAC(unittest.TestCase):
    def test_SAC2_soltar_un_bloque_en_el_formulador_queda_colocado_en_milisegundos(self):
        """REQ-EDT-02: desde que se suelta un bloque en el formulador hasta que queda colocado y repintado pasan pocos
        milisegundos; el ajuste de la cabecera no busca las barras en toda la ventana cada vez (AC2)."""
        from tools import hoja_contactos as HC
        from PySide6.QtWidgets import QToolBar

        c = HC.Contexto(1366, 768)
        try:
            HC._flotante("transicion")(c)
            p = c.w.flot.panel
            for _ in range(5):
                QApplication.processEvents()
            paleta = p.prog.paleta
            paleta._calcular(paleta.width())
            nodo = next(n for r, ruta, n in paleta._bloques if n is not None)
            soltar, total = [], []
            for _ in range(9):
                p.prog.poner("")
                for _ in range(3):
                    QApplication.processEvents()
                t = time.perf_counter()
                self.assertTrue(p.prog.lienzo.soltar(None, nodo))
                soltar.append((time.perf_counter() - t) * 1000)
                for _ in range(5):
                    QApplication.processEvents()
                total.append((time.perf_counter() - t) * 1000)
            soltar.sort()
            total.sort()
            self.assertEqual(p.prog.texto(), "marcha")
            self.assertLess(soltar[4], 15, f"soltar: {soltar[4]:.1f} ms")
            self.assertLess(total[4], 60, f"hasta repintar: {total[4]:.1f} ms (antes ≈ 9 ms con la ventana de pruebas)")
            # los ajustes de la cabecera no recorren toda la ventana buscando barras una vez conocidas
            ubica = c.w._ubica_modo
            ubica.ajustar()
            self.assertTrue(ubica._barras and all(isinstance(b, QToolBar) for b in ubica._barras))
            with mock.patch.object(type(c.w), "findChildren", side_effect=AssertionError("busca en toda la ventana")):
                ubica.ajustar()
        finally:
            c.cerrar()


if __name__ == "__main__":
    unittest.main()
