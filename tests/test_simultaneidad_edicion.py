"""Barras de simultaneidad al editar (P-IMP-125): el lado de la barra es el que se ve, los avisos dicen qué hay unido y cada
cosa se avisa una vez; lo que ya no existe se limpia al abrir y lo que el dibujo une pero el grafcet no, se avisa."""
import copy
import unittest
from unittest import mock

from grafcet.builder import M
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF
    from escritorio.diagrama import SX, anclas
    from escritorio.edicion import Edicion
    from grafcet.editor import Editor
    from grafcet.routing import validar_barras


@unittest.skipUnless(QT, "requiere PySide6")
class BarrasAlEditar(BaseQt):
    @staticmethod
    def punto(e, ident, lado):
        return next(a for a in anclas(e.M, ident) if a["lado"] == lado)["pos"]

    def arrastrar(self, e, a, b):
        p0, p1 = self.punto(*a), self.punto(*b)
        e.prensar(p0)
        for k in range(1, 7):
            e.mover(p0 + (p1 - p0) * k / 6)
        e.soltar(p1)

    def montar(self):
        """Dos etapas iniciales encima de una barra Y, una transición debajo y la etapa que sigue."""
        w, e = self.vacio()
        P = lambda x, y: QPointF(x + SX, y)
        a = e.poner_etapa(P(150, 100), inicial=True)
        b = e.poner_etapa(P(350, 100), inicial=True)
        barra = e.poner_barra(P(250, 220), "Y")
        t = e.poner_transicion(P(250, 340))
        e.poner_condicion(t, "true")
        c = e.poner_etapa(P(250, 460))
        e.cambia()
        return w, e, a, b, barra, t, c

    def bloqueos(self, e):
        return [d for d in e.diagnosticos() if d["blocks"]]

    def test_SSIM01_una_etapa_soltada_en_el_punto_de_abajo_de_la_barra_se_une_por_arriba(self):
        """REQ-MOD-03, REQ-EDT-02: una etapa dibujada encima de la barra queda unida por arriba aunque se suelte en el punto
        de unión inferior de la barra (antes quedaba «por abajo»: un borrador y un aviso de barra sin nada visible mal)."""
        w, e, a, b, barra, t, c = self.montar()
        self.arrastrar(e, (e, a, "abajo"), (e, barra, "arriba"))
        self.arrastrar(e, (e, b, "abajo"), (e, barra, "abajo"))  # la otra punta de la barra
        self.arrastrar(e, (e, barra, "abajo"), (e, t, "arriba"))
        self.arrastrar(e, (e, t, "abajo"), (e, c, "arriba"))
        bar = e.ed.bars()[0]
        self.assertEqual((sorted(bar["arriba"]), bar["abajo"]), (sorted([a, b]), [t]))
        self.assertEqual(e.ed.model["draftLinks"], [])
        self.assertEqual(self.bloqueos(e), [])
        self.assertTrue(e.ed.validate().can_simulate)
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertTrue(w._preparar_sesion())
        self.assertFalse(aviso.called)

    def test_SSIM02_el_aviso_de_la_barra_nombra_lo_unido_y_no_repite_el_nombre(self):
        """REQ-MOD-03, REQ-EDT-09: una etapa y una transición por el mismo lado: el aviso las nombra (sin ID), dice qué queda
        y el panel no antepone otra vez el nombre de la barra; Play y la lista coinciden."""
        w, e, a, b, barra, t, c = self.montar()
        ed = e.ed
        ed.bar_link(barra, "arriba", a)
        ed.bar_link(barra, "arriba", b)
        ed.bar_link(barra, "abajo", c)   # la etapa de después, unida directamente a la barra...
        ed.bar_link(barra, "abajo", t)   # ...y la transición que debía ir en medio
        ed.connect(t, c)
        e.cambia()
        w.refrescar_edicion()
        textos = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        barra_ = [x for x in textos if "Simultaneidad 1" in x]
        self.assertEqual(len(barra_), 1, textos)
        self.assertTrue(barra_[0].startswith("Simultaneidad 1 tiene a la vez la etapa 2 y la transición t1 por abajo."), barra_[0])
        item = next(w.lista_diag.item(i) for i in range(w.lista_diag.count()) if "Simultaneidad 1" in w.lista_diag.item(i).text())
        self.assertIn("quite de la barra lo que sobre", item.toolTip())  # (la frase larga se parte: el resto, en la ayuda)
        self.assertEqual(barra_[0].count("Simultaneidad 1"), 1)
        for x in textos:
            self.assertNotRegex(x, r"[a-z]-[0-9a-f]{32}")
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertFalse(w._preparar_sesion())
        self.assertIn("Simultaneidad 1 tiene a la vez la etapa 2 y la transición t1 por abajo", aviso.call_args.args[2])

    def test_SSIM03_el_borrador_entre_etapas_se_explica_una_vez(self):
        """REQ-MOD-03, REQ-EDT-09: el aviso de un enlace en borrador entre dos etapas dice qué enlaza y cómo arreglarlo, una sola
        vez (sin repetir «enlace de borrador 4→3» delante)."""
        w, e, a, b, barra, t, c = self.montar()
        e.ed.connect(b, a)
        e.cambia()
        w.refrescar_edicion()
        textos = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        self.assertIn("Enlace en borrador entre las etapas 1 y 0: dos etapas no pueden ir seguidas. "
                      "Bórrelo o ponga una transición en medio.", textos)
        self.assertEqual(sum("borrador" in x.lower() for x in textos), 1)

    def test_SSIM04_lo_que_no_existe_se_limpia_al_abrir_y_no_avisa(self):
        """REQ-MOD-03, REQ-DAT-02: una barra de un fichero con una unión a un elemento que ya no existe (o repetida) se abre sin
        ese resto, sin aviso de barra y diciéndolo; el núcleo también lo ignora al validar."""
        w, e, a, b, barra, t, c = self.montar()
        ed = e.ed
        for lado, i in (("arriba", a), ("arriba", b), ("abajo", t)):
            ed.bar_link(barra, lado, i)
        pres = copy.deepcopy(ed.presentation)
        pres["barras"][0]["abajo"] += ["t-fantasma", t]
        pres["barras"][0]["arriba"].append("s-fantasma")
        sucio = Editor(copy.deepcopy(ed.model), pres)
        self.assertEqual(sucio.cleaned_bar_refs, 3)
        self.assertEqual((sorted(sucio.bars()[0]["arriba"]), sucio.bars()[0]["abajo"]), (sorted([a, b]), [t]))
        self.assertTrue(sucio.dirty)
        self.assertNotIn("D-SIMULTANEIDAD", [d.code for d in sucio.validate().diagnostics])
        self.assertEqual(validar_barras(ed.model, pres["barras"]), [])
        self.assertEqual(Edicion(sucio, "x").barras_limpiadas, 3)

    def test_SSIM05_una_pareja_que_la_barra_dibuja_unida_y_el_grafcet_no_se_avisa(self):
        """REQ-MOD-03, REQ-EDT-09: si el dibujo une dos elementos por la barra y el modelo no tiene ese enlace, el aviso lo dice
        (el dibujo y el modelo no coinciden)."""
        w, e, a, b, barra, t, c = self.montar()
        ed = e.ed
        for lado, i in (("arriba", a), ("arriba", b), ("abajo", t)):
            ed.bar_link(barra, lado, i)
        self.assertEqual(validar_barras(ed.model, ed.bars()), [])
        modelo = copy.deepcopy(ed.model)
        next(x for x in modelo["transitions"] if x["id"] == t)["preRefs"].remove(b)
        diag = validar_barras(modelo, ed.bars())
        self.assertEqual(len(diag), 1)
        self.assertIn(f"{b}→{t}", diag[0].message)
        self.assertIn("no lo están", diag[0].message)


@unittest.skipUnless(QT, "requiere PySide6")
class BarraInferiorDeUnaConvergencia(BaseQt):
    punto = staticmethod(BarrasAlEditar.punto)
    arrastrar = BarrasAlEditar.arrastrar

    def montar_dos_ramas(self, unir_la_primera):
        """0 → barra Y → ramas 1→t→2 y 3→t→4 → barra Y inferior ancha (la segunda rama aún sin unir)."""
        w, e = self.vacio()
        P = lambda x, y: QPointF(x + SX, y)
        s0 = e.poner_etapa(P(250, 80), inicial=True); t0 = e.poner_transicion(P(250, 180)); b1 = e.poner_barra(P(250, 260), "Y")
        s1, s3 = e.poner_etapa(P(150, 340)), e.poner_etapa(P(350, 340))
        t1, t3 = e.poner_transicion(P(150, 420)), e.poner_transicion(P(350, 420))
        s2, s4 = e.poner_etapa(P(150, 500)), e.poner_etapa(P(350, 500))
        b2 = e.poner_barra(P(250, 620), "Y")
        for b in (b1, b2):
            e.ed.resize_bar(b, 80, 400)
        e.cambia()
        for t in (t0, t1, t3):
            e.poner_condicion(t, "true")
        for a, b in ((s0, t0), (t0, b1), (s1, t1), (t1, s2), (s3, t3), (t3, s4)):
            self.arrastrar(e, (e, a, "abajo"), (e, b, "arriba"))
        self.arrastrar(e, (e, b1, "abajo"), (e, s1, "arriba"))
        self.arrastrar(e, (e, b1, "abajo"), (e, s3, "arriba"))
        if unir_la_primera:
            self.arrastrar(e, (e, s2, "abajo"), (e, b2, "arriba"))
        return w, e, s2, s4, b2

    def test_SSIM06_la_salida_de_una_etapa_y_la_barra_inferior_se_unen_se_arrastre_de_donde_se_arrastre(self):
        """REQ-MOD-03, REQ-EDT-02: arrastrar la salida de una etapa a cualquier punto de la barra (su punto de abajo incluido, y
        con la otra rama ya unida o no), o de la barra a la salida de la etapa, une la etapa a la barra por arriba: nunca un
        borrador etapa-etapa entre las dos ramas (antes, soltar en el punto de abajo la dejaba «por abajo» y creaba el borrador)."""
        for unida in (True, False):
            for modo in ("arriba", "abajo", "cuerpo", "desde_abajo", "desde_arriba"):
                for x in (5, 120, 200, 395):
                    w, e, s2, s4, b2 = self.montar_dos_ramas(unida)
                    b = next(q for q in e.M["bars"] if q["id"] == b2)
                    bx, by = b["x"] + SX, b["y"]
                    p4 = self.punto(e, s4, "abajo")
                    y = {"arriba": by - 9, "abajo": by + 17, "cuerpo": by + 4, "desde_abajo": by + 17, "desde_arriba": by - 9}[modo]
                    destino = QPointF(bx + x, y)
                    if modo.startswith("desde"):
                        e.prensar(destino)
                        for k in range(1, 7):
                            e.mover(destino + (p4 - destino) * k / 6)
                        e.soltar(p4)
                    else:
                        e.prensar(p4)
                        for k in range(1, 7):
                            e.mover(p4 + (destino - p4) * k / 6)
                        e.soltar(destino)
                    nombre = f"unida={unida} {modo} x={x}"
                    bar = next(q for q in e.ed.bars() if q["id"] == b2)
                    self.assertIn(s4, bar["arriba"], nombre)
                    self.assertEqual(bar["abajo"], [], nombre)
                    self.assertEqual(e.ed.model["draftLinks"], [], nombre)


@unittest.skipUnless(QT, "requiere PySide6")
class SimultaneidadesAnidadas(BaseQt):
    """Una divergencia exterior cuya rama contiene otra divergencia y su convergencia, hecha solo con gestos."""
    punto = staticmethod(BarrasAlEditar.punto)
    arrastrar = BarrasAlEditar.arrastrar

    def construir(self, orden="lectura", interior=(120, 330), d=80):
        """0 -> t -> [barra exterior] -> rama A: a -> t -> [barra interior] -> a1, a2 -> t -> a3, a4 -> [barra interior] -> t -> a5
        y rama B: b -> t -> b2 -> [barra exterior] -> t -> fin. `interior` es (x, ancho) de las barras interiores; `d`, la
        separación vertical entre elementos."""
        w, e = self.vacio()
        P = lambda x, y: QPointF(x + SX, y)
        y = lambda n: 60 + d * n
        el = {}
        el["s0"] = e.poner_etapa(P(400, y(0)), inicial=True)
        for k, (x, n) in {"t0": (400, 1), "tA": (250, 4), "tA1": (180, 7), "tA2": (320, 7), "tAc": (250, 11),
                          "tB": (600, 4), "tfin": (400, 15)}.items():
            el[k] = e.poner_transicion(P(x, y(n)))
        for k, (x, n) in {"sA": (250, 3), "sB": (600, 3), "sA1": (180, 6), "sA2": (320, 6), "sA3": (180, 8), "sA4": (320, 8),
                          "sA5": (250, 12), "sB2": (600, 12), "sfin": (400, 16)}.items():
            el[k] = e.poner_etapa(P(x, y(n)))
        for k, (x, n, ancho) in {"O1": (60, 2, 740), "I1": (interior[0], 5, interior[1]), "I2": (interior[0], 10, interior[1]),
                                 "O2": (60, 14, 740)}.items():
            el[k] = e.poner_barra(P(x + ancho / 2, y(n)), "Y")
            e.ed.resize_bar(el[k], x, ancho)
        e.cambia()
        for k in ("t0", "tA", "tA1", "tA2", "tAc", "tB"):
            e.poner_condicion(el[k], "true")
        e.poner_condicion(el["tfin"], "go", crear=True)
        barras = {el[k] for k in ("O1", "I1", "I2", "O2")}

        def anclaje(i, lado, x):
            """El punto del elemento, o el de la barra bajo la x del otro extremo."""
            if i not in barras:
                return self.punto(e, i, lado)
            b = next(q for q in e.M["bars"] if q["id"] == i)
            bx = b["x"] + SX
            return QPointF(min(max(x, bx), bx + b["ancho"]), b["y"] - 9 if lado == "arriba" else b["y"] + 17)

        def unir(a, b):
            """Arrastra de la salida de `a` a la entrada de `b` (si uno es una barra, a lo largo de ella, bajo el otro)."""
            xa = self.punto(e, el[a], "abajo").x() if el[a] not in barras else self.punto(e, el[b], "arriba").x()
            p0, p1 = anclaje(el[a], "abajo", xa), anclaje(el[b], "arriba", xa)
            e.prensar(p0)
            for k in range(1, 7):
                e.mover(p0 + (p1 - p0) * k / 6)
            e.soltar(p1)
        grupos = {
            "L1": [("s0", "t0"), ("t0", "O1")],
            "L2": [("O1", "sA"), ("O1", "sB")],
            "L3": [("sA", "tA"), ("tA", "I1"), ("I1", "sA1"), ("I1", "sA2")],
            "L4": [("sA1", "tA1"), ("tA1", "sA3"), ("sA2", "tA2"), ("tA2", "sA4")],
            "L5": [("sA3", "I2"), ("sA4", "I2"), ("I2", "tAc"), ("tAc", "sA5")],
            "L6": [("sB", "tB"), ("tB", "sB2")],
            "L7": [("sA5", "O2"), ("sB2", "O2"), ("O2", "tfin"), ("tfin", "sfin")],
        }
        secuencias = {"lectura": ["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
                      "de_abajo_arriba": ["L7", "L6", "L5", "L4", "L3", "L2", "L1"],
                      "interior_primero": ["L3", "L4", "L5", "L1", "L2", "L6", "L7"]}[orden]
        for g in secuencias:
            for a, b in grupos[g]:
                unir(a, b)
        return w, e, el

    def comprobar(self, w, e, el, nombre):
        ed = e.ed
        self.assertEqual(e.diagnosticos(), [], nombre)
        self.assertEqual(ed.model["draftLinks"], [], nombre)
        bars = {b["id"]: b for b in ed.bars()}
        esperado = {"O1": ([el["t0"]], [el["sA"], el["sB"]]), "I1": ([el["tA"]], [el["sA1"], el["sA2"]]),
                    "I2": ([el["sA3"], el["sA4"]], [el["tAc"]]), "O2": ([el["sA5"], el["sB2"]], [el["tfin"]])}
        for k, (arr, aba) in esperado.items():
            self.assertEqual((sorted(bars[el[k]]["arriba"]), sorted(bars[el[k]]["abajo"])), (sorted(arr), sorted(aba)), f"{nombre} {k}")
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertTrue(w._preparar_sesion(), nombre)
        self.assertFalse(aviso.called, nombre)
        activas = lambda: set(w.v.s.z.situation)
        self.assertEqual(activas(), {el["sA5"], el["sB2"]}, nombre)  # las dos ramas llegan a su convergencia y esperan
        w.v.act("entrada", {"var": next(v["id"] for v in ed.model["variables"] if v["name"] == "go")})
        self.assertEqual(activas(), {el["sfin"]}, nombre)

    def test_SSIM07_simultaneidad_anidada_en_cualquier_orden_y_con_barras_interiores_dentro_solapadas_o_mas_anchas(self):
        """REQ-MOD-03, REQ-EDT-02, REQ-SIM-03: divergencia y convergencia interiores dentro de una rama de otra exterior, hechas
        con gestos en tres órdenes y con las barras interiores dentro del ancho de la exterior, solapadas con su otra rama o
        más anchas: cada gesto une a la barra que hay bajo el puntero, sin avisos, y Play activa las etapas esperadas."""
        for orden in ("lectura", "de_abajo_arriba", "interior_primero"):
            for interior in ((120, 330), (120, 560), (-80, 1000)):
                nombre = f"{orden} interior={interior}"
                w, e, el = self.construir(orden, interior)
                self.comprobar(w, e, el, nombre)

    def test_SSIM08_simultaneidad_anidada_con_las_barras_muy_juntas_en_vertical(self):
        """REQ-MOD-03, REQ-EDT-02, REQ-SIM-03: lo mismo con los elementos a 60 de distancia vertical (las barras interiores quedan
        a 120 de la exterior): cada gesto une a la barra que hay bajo el puntero."""
        for orden in ("lectura", "interior_primero"):
            w, e, el = self.construir(orden, (120, 330), d=60)
            self.comprobar(w, e, el, f"{orden} d=60")

    def test_SSIM09_soltar_sobre_otra_barra_une_a_la_que_hay_bajo_el_puntero(self):
        """REQ-MOD-03, REQ-EDT-02: la salida de una etapa soltada sobre una barra que no es la suya la une a ESA barra (nunca a
        otra, ni a una etapa vecina): no hay borrador ni se toca la barra que le tocaba."""
        w, e, el = self.construir("lectura", (120, 330))
        ed = e.ed
        P = lambda x, y: QPointF(x + SX, y)
        for objetivo, otra in (("I2", "O2"), ("O2", "I2")):
            nueva = e.poner_etapa(P(450, 200))
            antes = {k: copy.deepcopy(next(b for b in ed.bars() if b["id"] == el[k])) for k in ("I2", "O2")}
            b = next(q for q in e.M["bars"] if q["id"] == el[objetivo])
            p0 = self.punto(e, nueva, "abajo")
            p1 = QPointF(p0.x(), b["y"] - 9)
            e.prensar(p0)
            for k in range(1, 7):
                e.mover(p0 + (p1 - p0) * k / 6)
            e.soltar(p1)
            despues = {k: next(q for q in ed.bars() if q["id"] == el[k]) for k in ("I2", "O2")}
            self.assertIn(nueva, despues[objetivo]["arriba"])
            self.assertEqual(despues[otra], antes[otra])
            self.assertEqual(ed.model["draftLinks"], [])
            e.deshacer()
            e.deshacer()  # y la etapa nueva


@unittest.skipUnless(QT, "requiere PySide6")
class LadoEquivocadoSeVe(BaseQt):
    montar = BarrasAlEditar.montar
    punto = staticmethod(BarrasAlEditar.punto)
    def test_SSIM10_lo_unido_por_el_lado_contrario_se_dibuja_atravesando_la_barra_y_el_aviso_lo_dice(self):
        """REQ-MOD-03, REQ-EDT-09: un elemento unido por el lado contrario al que se ve asoma por el otro lado de la barra; los
        bien unidos se dibujan como siempre; si la barra no es válida, el aviso dice qué está unido al revés."""
        from grafcet.routing import CRUCE, enlaces
        w, e, a, b, barra, t, c = self.montar()
        ed = e.ed
        ed.bar_link(barra, "arriba", a)
        ed.bar_link(barra, "abajo", t)
        e.cambia()
        by = next(q for q in e.M["bars"] if q["id"] == barra)["y"]
        bien = {x["sid"]: x for x in enlaces(e.M) if x["rol"] == "barra"}
        self.assertEqual(bien[a]["pts"][-1][1], by)           # llega a la cara de arriba y se para
        self.assertEqual(bien[t]["pts"][0][1], by + 8)        # sale de la cara de abajo
        self.assertFalse(any(x.get("cruza") for x in bien.values()))
        ed.bar_link(barra, "abajo", b)  # b está encima de la barra: unida por abajo
        e.cambia()
        mal = next(x for x in enlaces(e.M) if x["rol"] == "barra" and x["sid"] == b)
        self.assertTrue(mal["cruza"])
        self.assertEqual(mal["pts"][0][1], by + 8)            # sale de la cara de abajo de la barra...
        self.assertEqual(mal["pts"][1][1], by + 8 + CRUCE)    # ...asoma por debajo y rodea por un carril lateral (no la atraviesa)
        self.assertNotEqual(mal["pts"][2][0], mal["pts"][0][0])  # y por un carril lateral
        self.assertEqual({x["sid"]: x["pts"] for x in enlaces(e.M) if x["rol"] == "barra" and x["sid"] != b}, {k: v["pts"] for k, v in bien.items()})
        aviso = next(d for d in e.diagnosticos() if d["code"] == "D-SIMULTANEIDAD")
        self.assertIn("unida por el lado contrario al que se ve", aviso["message"])
        self.assertEqual(aviso["message"].count("Simultaneidad 1"), 1)


@unittest.skipUnless(QT, "requiere PySide6")
class LadoPorElPuntoDeUnion(BaseQt):
    """El lado de la barra lo da el punto de unión del elemento (salida: por arriba; entrada: por abajo), no la punta elegida."""
    punto = staticmethod(BarrasAlEditar.punto)
    arrastrar = BarrasAlEditar.arrastrar
    bloqueos = BarrasAlEditar.bloqueos

    def retorno(self):
        """0 -> t1 -> barra Y -> {1, 0}: la divergencia lleva a la etapa 1 (debajo) y vuelve a la entrada de la 0 (encima)."""
        w, e = self.vacio()
        P = lambda x, y: QPointF(x + SX, y)
        s0 = e.poner_etapa(P(250, 100), inicial=True)
        t1 = e.poner_transicion(P(250, 200))
        b = e.poner_barra(P(250, 280), "Y")
        s1 = e.poner_etapa(P(250, 380))
        e.cambia()
        e.poner_condicion(t1, "go", crear=True)  # (con «true» la etapa 0 se reactivaría sin parar)
        self.arrastrar(e, (e, s0, "abajo"), (e, t1, "arriba"))
        self.arrastrar(e, (e, t1, "abajo"), (e, b, "arriba"))
        return w, e, s0, t1, b, s1

    def test_SSIM11_etapa_encima_de_su_salida_a_la_punta_inferior_y_al_reves_se_une_por_arriba(self):
        """REQ-MOD-03, REQ-EDT-02: una etapa encima de la barra, de su salida a la punta inferior de la barra o de esa punta a
        su salida, queda unida por arriba, sin borrador ni aviso (el caso de P-IMP-125)."""
        from grafcet.routing import enlaces
        for sentido in ("a_la_barra", "de_la_barra"):
            w, e = self.vacio()
            P = lambda x, y: QPointF(x + SX, y)
            s = e.poner_etapa(P(250, 100), inicial=True)
            b = e.poner_barra(P(250, 220), "Y")
            e.cambia()
            a, z = ((e, s, "abajo"), (e, b, "abajo")) if sentido == "a_la_barra" else ((e, b, "abajo"), (e, s, "abajo"))
            self.arrastrar(e, a, z)
            bar = e.ed.bars()[0]
            self.assertEqual((bar["arriba"], bar["abajo"]), ([s], []), sentido)
            self.assertEqual(e.ed.model["draftLinks"], [], sentido)
            self.assertEqual(self.bloqueos(e), [], sentido)
            self.assertFalse(any(x.get("cruza") for x in enlaces(e.M)), sentido)

    def test_SSIM12_de_la_punta_inferior_a_la_entrada_de_una_etapa_encima_es_una_divergencia_que_cruza_y_se_puede_simular(self):
        """REQ-MOD-03, REQ-EDT-02, REQ-SIM-03: t1 -> barra -> {1, 0} con la 0 encima: arrastrar de la punta inferior de la barra
        a la entrada de la 0 la une por abajo (no es error), sin aviso; se dibuja cruzando por un carril lateral, y Play se permite."""
        from grafcet.routing import enlaces
        w, e, s0, t1, b, s1 = self.retorno()
        self.arrastrar(e, (e, b, "abajo"), (e, s1, "arriba"))
        self.arrastrar(e, (e, b, "abajo"), (e, s0, "arriba"))
        bar = e.ed.bars()[0]
        self.assertEqual((bar["arriba"], sorted(bar["abajo"])), ([t1], sorted([s0, s1])))
        self.assertEqual(e.ed.model["draftLinks"], [])
        self.assertEqual([d["code"] for d in e.diagnosticos()], [])
        self.assertTrue(e.ed.validate().can_simulate)
        enl = {x["sid"]: x for x in enlaces(e.M) if x["rol"] == "barra"}
        self.assertTrue(enl[s0].get("cruza"))
        self.assertNotIn("cruza", enl[s1])
        pts = enl[s0]["pts"]
        px, py = next((s["x"] + SX, s["y"]) for s in e.M["steps"] if s["id"] == s0)
        self.assertNotEqual(pts[2][0], px)            # el carril queda a un lado de la etapa...
        self.assertGreater(abs(pts[2][0] - px), 22)
        self.assertEqual(pts[-1], (px, py - 22))      # ...y entra por su cara de arriba
        for a, z in zip(pts[:-1], pts[1:-1]):         # ningún tramo (salvo el de entrada) pasa por la etapa
            self.assertFalse(a[0] == z[0] == px and min(a[1], z[1]) < py + 22 and max(a[1], z[1]) > py - 22)
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertTrue(w._preparar_sesion())
        self.assertFalse(aviso.called)

    def test_SSIM13_etapa_debajo_a_su_entrada_se_une_por_abajo_sin_cruzar(self):
        """REQ-MOD-03, REQ-EDT-02: una etapa debajo de la barra, de la punta inferior o de la superior de la barra a su entrada,
        queda unida por abajo y se dibuja sin cruzar la barra."""
        from grafcet.routing import enlaces
        for punta in ("abajo", "arriba"):
            w, e, s0, t1, b, s1 = self.retorno()
            self.arrastrar(e, (e, b, punta), (e, s1, "arriba"))
            bar = e.ed.bars()[0]
            self.assertEqual((bar["arriba"], bar["abajo"]), ([t1], [s1]), punta)
            self.assertFalse(any(x.get("cruza") for x in enlaces(e.M)), punta)
            self.assertEqual(self.bloqueos(e), [], punta)

    def test_SSIM19_desde_la_barra_al_cuerpo_de_un_elemento_cuenta_donde_esta(self):
        """REQ-MOD-03, REQ-EDT-02: soltar en el cuerpo, sin apuntar a un punto de unión, no depende de la mitad de la etapa: la
        de debajo de la barra recibe de ella (también por su mitad baja) y la de encima emite hacia ella (también por la alta)."""
        def soltar_en(e, barra, ident, dy):
            p0 = self.punto(e, barra, "abajo")
            s = next(s for s in e.M["steps"] if s["id"] == ident)
            p1 = QPointF(s["x"] + SX, s["y"] + dy)
            e.prensar(p0)
            for k in range(1, 7):
                e.mover(p0 + (p1 - p0) * k / 6)
            e.soltar(p1)

        P = lambda x, y: QPointF(x + SX, y)
        w, e = self.vacio()
        b = e.poner_barra(P(250, 220), "Y")
        debajo, encima = e.poner_etapa(P(250, 340)), e.poner_etapa(P(250, 100), inicial=True)
        e.cambia()
        soltar_en(e, b, debajo, 12)
        soltar_en(e, b, encima, -12)
        bar = e.ed.bars()[0]
        self.assertEqual((bar["arriba"], bar["abajo"]), ([encima], [debajo]))

    def test_SSIM20_lo_que_da_la_vuelta_conserva_sus_tramos_minimos_colocado_a_mano(self):
        """REQ-EDT-02: el tramo de entrada de un retorno desde la barra no se pega a la etapa aunque se arrastre hasta ella."""
        from grafcet.routing import CRUCE, enlaces
        w, e, s0, t1, b, s1 = self.retorno()
        self.arrastrar(e, (e, b, "abajo"), (e, s0, "arriba"))
        ida = next(x for x in enlaces(e.M) if x["rol"] == "barra" and x["sid"] == s0)
        self.assertEqual(ida["tallos"][0], CRUCE)
        modelo = copy.deepcopy(e.M)
        y0 = ida["pts"][-1][1]
        modelo.setdefault("linkStyles", {})[ida["id"]] = {"route": {"laneX": ida["pts"][2][0] - SX, "entryY": y0}}
        pts = next(x for x in enlaces(modelo) if x["id"] == ida["id"])["pts"]
        self.assertLess(pts[-2][1], pts[-1][1])

    def test_SSIM14_cuando_el_lado_no_es_el_de_la_punta_se_dice_por_cual_se_ha_unido(self):
        """REQ-EDT-09: soltar la salida de una etapa en la punta inferior la une por arriba y el aviso informativo lo dice, con
        el nombre de la etapa; lo mismo con una entrada y la punta de arriba."""
        w, e = self.vacio()
        P = lambda x, y: QPointF(x + SX, y)
        s = e.poner_etapa(P(250, 100), inicial=True)
        b = e.poner_barra(P(250, 220), "Y")
        e.cambia()
        self.arrastrar(e, (e, s, "abajo"), (e, b, "abajo"))
        self.assertEqual(e.mensaje, f"«{e._nom(s)}» sale hacia la barra: se ha unido por arriba.")
        self.assertTrue(e.mensaje_info)
        w, e, s0, t1, b, s1 = self.retorno()
        self.arrastrar(e, (e, b, "arriba"), (e, s1, "arriba"))  # su entrada, desde la punta de arriba: por abajo
        self.assertEqual(e.mensaje, f"«{e._nom(s1)}» recibe de la barra: se ha unido por abajo.")
        self.assertTrue(e.mensaje_info)


@unittest.skipUnless(QT, "requiere PySide6")
class BarraSuelta(BaseQt):
    """Una barra con un lado vacío se avisa (D-BARRA-SUELTA), sin bloquear."""
    punto = staticmethod(BarrasAlEditar.punto)
    arrastrar = BarrasAlEditar.arrastrar
    montar = BarrasAlEditar.montar

    def avisos(self, e):
        return [d for d in e.diagnosticos() if d["code"] == "D-BARRA-SUELTA"]

    def test_SSIM15_una_barra_recien_puesta_avisa_de_los_dos_lados(self):
        """REQ-MOD-03, REQ-EDT-09: una barra sin nada unido se conserva, avisa «no tiene nada conectado» con su nombre (una vez),
        no bloquea y Play funciona; un clic en el aviso lleva a la barra."""
        w, e = self.vacio()
        e.poner_etapa(QPointF(250 + SX, 80), inicial=True)
        b = e.poner_barra(QPointF(250 + SX, 220), "Y")
        e.cambia()
        w.refrescar_edicion()
        (d,) = self.avisos(e)
        self.assertEqual(d["message"], "Simultaneidad 1 no tiene nada conectado. Únala o bórrela.")
        self.assertEqual((d["severity"], d["blocks"], d["target"]), ("advertencia", False, b))
        textos = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        self.assertIn("Simultaneidad 1 no tiene nada conectado. Únala o bórrela.", textos)
        self.assertEqual(sum("Simultaneidad 1" in x for x in textos), 1)
        for x in textos:
            self.assertNotRegex(x, r"[a-z]-[0-9a-f]{32}")
        self.assertEqual(len(e.ed.bars()), 1)  # se conserva
        res = e.ed.validate()
        self.assertTrue(res.can_simulate)
        self.assertFalse([x for x in res.diagnostics if x.blocks_start])
        item = next(w.lista_diag.item(i) for i in range(w.lista_diag.count()) if "Simultaneidad 1" in w.lista_diag.item(i).text())
        w._ir_a_diagnostico(item)
        self.assertEqual(e.sel, [b])
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            self.assertTrue(w._preparar_sesion())
        self.assertFalse(aviso.called)

    def test_SSIM16_con_un_lado_vacio_dice_cual_y_desaparece_al_conectar(self):
        """REQ-MOD-03, REQ-EDT-09: con algo solo por arriba avisa «por abajo»; con algo solo por abajo, «por arriba»; al conectar
        el otro lado el aviso desaparece y nada se bloquea."""
        w, e, a, b, barra, t, c = self.montar()
        e.ed.bar_link(barra, "arriba", a)
        e.cambia()
        (d,) = self.avisos(e)
        self.assertEqual(d["message"], "Simultaneidad 1 no tiene nada conectado por abajo. Únala o bórrela.")
        self.assertFalse(d["blocks"])
        self.arrastrar(e, (e, barra, "abajo"), (e, t, "arriba"))
        self.assertEqual(self.avisos(e), [])
        w, e, a, b, barra, t, c = self.montar()
        e.ed.bar_link(barra, "abajo", t)
        e.cambia()
        (d,) = self.avisos(e)
        self.assertEqual(d["message"], "Simultaneidad 1 no tiene nada conectado por arriba. Únala o bórrela.")
        self.assertFalse(d["blocks"])

    def test_SSIM17_la_barra_de_alternativa_tambien_avisa_y_lo_ya_borrado_no_cuenta(self):
        """REQ-MOD-03: la barra de alternativa sin conectar avisa igual que la Y; un elemento unido que ya no existe no cuenta
        como conectado."""
        w, e = self.vacio()
        e.poner_barra(QPointF(250 + SX, 220), "O")
        e.cambia()
        (d,) = self.avisos(e)
        self.assertTrue(d["message"].startswith("Alternativa 1 no tiene nada conectado."), d["message"])
        pres = copy.deepcopy(e.ed.presentation)
        pres["barras"][0]["arriba"] = ["s-fantasma"]
        diag = validar_barras(e.ed.model, pres["barras"])
        self.assertEqual([x.code for x in diag], ["D-BARRA-SUELTA"])
        self.assertIn("no tiene nada conectado.", diag[0].message)

    def test_SSIM18_vista_muestra_el_nombre_de_la_barra_y_no_su_id(self):
        """REQ-EDT-09: el mensaje que `Vista` da (no compilable en Play, y el aviso de barra suelta) usa «Simultaneidad 1», no el
        ID interno de la barra."""
        from grafcet.view import Vista
        w, e, a, b, barra, t, c = self.montar()
        ed = e.ed
        ed.bar_link(barra, "arriba", a)
        ed.bar_link(barra, "abajo", c)
        ed.bar_link(barra, "abajo", t)
        v = Vista(ed.model["id"], "x", "", lambda: (copy.deepcopy(ed.model), e.layout()), w.options, presentation=ed.presentation)
        S = v.state()
        self.assertEqual(S["status"], "no-compilable")
        mensajes = [d["message"] for d in S["diagnostics"]]
        self.assertTrue(any(m.startswith("Simultaneidad 1 ") for m in mensajes), mensajes)
        for m in mensajes:
            self.assertNotRegex(m, r"[a-z]-[0-9a-f]{32}")
        suelta = validar_barras(ed.model, [dict(ed.bars()[0], arriba=[], abajo=[])])
        self.assertEqual(suelta[0].code, "D-BARRA-SUELTA")
        self.assertEqual(v._diag(suelta[0])["message"], "Simultaneidad 1 no tiene nada conectado. Únala o bórrela.")
