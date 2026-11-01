"""Selección de marcos completos mediante los gestos reales del lazo."""
import unittest
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF
    from escritorio.diagrama import cajas_parciales


@unittest.skipUnless(QT, "PySide6 no está instalado")
class LazoMarcos(BaseQt):
    def enlazar_lazo(self, e, c, margen=16):
        a, b = QPointF(c["x0"] - margen, c["y0"] - margen), QPointF(c["x1"] + margen, c["y1"] + margen)
        self.assertTrue(e.prensar(a))
        self.assertIsNotNone(e.lazo)
        self.assertTrue(e.mover(b))
        self.assertTrue(e.soltar(b))

    def test_SLAZ01_parcial_vacio_se_selecciona_se_mueve_y_se_borra(self):
        """REQ-EDT-02, REQ-EDT-03, REQ-EDT-05: el marco vacío completo entra en el lazo, se mueve y se borra con deshacer."""
        w, e = self.vacio()
        g = e.poner_parcial(QPointF(700, 220))
        c = cajas_parciales(e.M)[g]
        self.enlazar_lazo(e, c)
        self.assertEqual(e.sel, [g])
        antes, n = self.estado(e), len(e.ed.undo_stack)
        p = QPointF(c["x0"], c["y0"] + 12)
        e.prensar(p)
        e.mover(p + QPointF(60, 40))
        e.soltar(p + QPointF(60, 40))
        despues = cajas_parciales(e.M)[g]
        self.assertEqual((despues["x0"] - c["x0"], despues["y0"] - c["y0"]), (60, 40))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)
        self.enlazar_lazo(e, c)
        self.assertTrue(e.borrar())
        self.assertNotIn(g, cajas_parciales(e.M))
        e.deshacer()
        self.assertIn(g, cajas_parciales(e.M))

    def test_SLAZ02_lazo_parcial_no_incluye_el_marco(self):
        """REQ-EDT-02: tocar o contener solo parte del marco no lo selecciona."""
        w, e = self.vacio()
        g = e.poner_parcial(QPointF(700, 220))
        c = cajas_parciales(e.M)[g]
        self.enlazar_lazo(e, dict(c, x1=c["x1"] - 40), margen=8)
        self.assertNotIn(g, e.sel)

    def test_SLAZ03_recinto_con_contenido_consulta_borrado_y_cancela(self):
        """REQ-EDT-02, REQ-EDT-05: el recinto completo entra en el lazo y conserva la confirmación de jerarquía."""
        w, e, d = self.con_recinto()
        c = cajas_parciales(e.M)[d["r"]]
        self.enlazar_lazo(e, c)
        self.assertTrue({d["r"], d["a"], d["b"]} <= set(e.sel))
        antes, n = self.estado(e), len(e.ed.undo_stack)
        planes = []
        e.confirmar_borrado = lambda plan: planes.append(plan) or False
        self.assertFalse(e.borrar())
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertEqual(len(planes), 1)
        self.assertIn(d["r"], planes[0]["elements"])
        e.confirmar_borrado = lambda plan: True
        self.assertTrue(e.borrar())
        self.assertNotIn(d["r"], {p["id"] for p in e.ed.model["partials"]})
        self.assertIn(d["e0"], {s["id"] for s in e.ed.model["steps"]})
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SLAZ04_marco_con_contenido_mueve_su_seleccion_sin_duplicar(self):
        """REQ-EDT-03, REQ-EDT-05: agarrar el marco seleccionado desplaza su contenido una sola vez y se deshace junto."""
        w, e, d = self.con_recinto()
        c = cajas_parciales(e.M)[d["r"]]
        self.enlazar_lazo(e, c)
        seleccion = set(e.sel)
        antes, pos, n = self.estado(e), self.pos(e), len(e.ed.undo_stack)
        p = QPointF(c["x0"], c["y0"] + 12)
        e.prensar(p)
        self.assertEqual(e.arrastre["tipo"], "grupo")
        e.mover(p + QPointF(60, 40))
        e.soltar(p + QPointF(60, 40))
        self.assertEqual(set(e.sel), seleccion)
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        nuevos = self.pos(e)
        for i in seleccion & pos.keys():
            if i != d["r"]:
                self.assertEqual((nuevos[i][0] - pos[i][0], nuevos[i][1] - pos[i][1]), (60, 40))
        self.assertEqual((cajas_parciales(e.M)[d["r"]]["x0"] - c["x0"], cajas_parciales(e.M)[d["r"]]["y0"] - c["y0"]), (60, 40))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SLAZ05_recinto_vacio_entra_en_lazo(self):
        """REQ-JER-05, REQ-EDT-02: un recinto sin etapas también queda seleccionado por su rectángulo completo."""
        w, e = self.vacio()
        h = e.poner_etapa(QPointF(260, 100), tipo="enclosing")
        r = e.anadir_recinto(h)
        self.enlazar_lazo(e, cajas_parciales(e.M)[r])
        self.assertEqual(e.sel, [r])

    def test_SLAZ06_parcial_suelto_con_contenido_se_borra_y_restaura(self):
        """REQ-EDT-02, REQ-EDT-05: el parcial suelto poblado se selecciona entero y Supr conserva su confirmación."""
        w, e = self.vacio()
        g = e.poner_parcial(QPointF(700, 220))
        c = cajas_parciales(e.M)[g]
        sid = e.poner_etapa(QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
        self.enlazar_lazo(e, cajas_parciales(e.M)[g])
        self.assertEqual(set(e.sel), {g, sid})
        antes, n = self.estado(e), len(e.ed.undo_stack)
        planes = []
        e.confirmar_borrado = lambda plan: planes.append(plan) or False
        w.a_borrar.trigger()
        self.assertEqual(len(planes), 1)
        self.assertEqual((self.estado(e), len(e.ed.undo_stack)), (antes, n))
        self.assertTrue({g, sid} <= set(planes[0]["elements"]))
        e.confirmar_borrado = lambda plan: planes.append(plan) or True
        w.a_borrar.trigger()
        self.assertEqual(len(planes), 2)
        self.assertNotIn(g, {p["id"] for p in e.ed.model["partials"]})
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SLAZ07_dos_marcos_vacios_se_mueven_con_la_seleccion(self):
        """REQ-EDT-03, REQ-EDT-05: varios marcos vacíos seleccionados por lazo se mueven juntos y una sola vez."""
        w, e = self.vacio()
        g1 = e.poner_parcial(QPointF(700, 200))
        g2 = e.poner_parcial(QPointF(700, 450))
        cajas = cajas_parciales(e.M)
        c = {k: (min if k in ("x0", "y0") else max)(cajas[g][k] for g in (g1, g2)) for k in ("x0", "x1", "y0", "y1")}
        self.enlazar_lazo(e, c)
        self.assertEqual(set(e.sel), {g1, g2})
        antes, n = self.estado(e), len(e.ed.undo_stack)
        p = QPointF(cajas[g1]["x0"], cajas[g1]["y0"] + 12)
        e.prensar(p)
        e.mover(p + QPointF(60, 40))
        e.soltar(p + QPointF(60, 40))
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        for g in (g1, g2):
            self.assertEqual((cajas_parciales(e.M)[g]["x0"] - cajas[g]["x0"], cajas_parciales(e.M)[g]["y0"] - cajas[g]["y0"]), (60, 40))
        e.deshacer()
        self.assertEqual(self.estado(e), antes)

    def test_SLAZ08_borde_recinto_lleno_mueve_rutas_y_deshace_junto(self):
        """REQ-EDT-03, REQ-EDT-05, REQ-JER-05: borde sin selección previa mueve todo, rutas incluidas, en una operación."""
        w, e, d = self.con_recinto()
        tid = next(t["id"] for t in e.ed.model["transitions"] if t["partialRef"] == d["r"])
        lid = f"{tid}|{d['a']}|pre"
        ruta = {"route": {"laneX": "600", "exitY": "300", "entryY": "360", "middleY": "320"}}
        e.ed.set_link_style(lid, ruta); e.cambia()
        antes, pos, n = self.estado(e), self.pos(e), len(e.ed.undo_stack)
        c = cajas_parciales(e.M)[d["r"]]; e.sel = []
        p = QPointF(c["x0"], c["y0"] + 12)
        e.prensar(p); self.assertEqual(e.sel, [d["r"]]); self.assertEqual(e.arrastre["tipo"], "grupo")
        e.mover(p + QPointF(60, 40)); e.soltar(p + QPointF(60, 40))
        for i in (d["a"], d["b"], tid):
            self.assertEqual(self.pos(e)[i], (pos[i][0]+60, pos[i][1]+40))
        self.assertEqual(self.pos(e)[d["e0"]], pos[d["e0"]])
        self.assertEqual(e.ed.link_styles()[lid]["route"], {"laneX": "660", "exitY": "340", "entryY": "400", "middleY": "360"})
        self.assertEqual(len(e.ed.undo_stack), n+1)
        e.deshacer(); self.assertEqual(self.estado(e), antes)

    def test_SLAZ09_nombre_parcial_lleno_y_clic_interior(self):
        """REQ-EDT-02, REQ-EDT-03: el nombre mueve el parcial lleno; el interior conserva la selección de elementos."""
        from escritorio.diagrama import SX
        w, e = self.vacio(); g = e.poner_parcial(QPointF(700, 220))
        c = cajas_parciales(e.M)[g]; e.colocar("etapa", QPointF(c["x0"]+80, c["y0"]+60)); sid=e.sel[0]
        c = cajas_parciales(e.M)[g]; p=QPointF(c["x0"]+34, c["y1"]+10)
        antes=self.pos(e)[sid]; e.sel=[]; e.prensar(p)
        self.assertEqual(e.arrastre["tipo"], "grupo")
        e.mover(p+QPointF(60, 40)); e.soltar(p+QPointF(60, 40))
        self.assertEqual(self.pos(e)[sid], (antes[0]+60, antes[1]+40))
        x,y=self.pos(e)[sid]; e.prensar(QPointF(x+SX,y)); e.soltar(QPointF(x+SX,y))
        self.assertEqual(e.sel, [sid])

    def test_SLAZ10_marco_lleno_rechaza_solape_sin_historial(self):
        """REQ-EDT-03, REQ-EDT-05: el arrastre por borde conserva el rechazo y aviso de solape del movimiento múltiple."""
        from escritorio.diagrama import SX
        w,e,d=self.con_recinto(); c=cajas_parciales(e.M)[d["r"]]
        pos=self.pos(e); dx=pos[d["h"]][0]-pos[d["a"]][0]; dy=pos[d["h"]][1]-pos[d["a"]][1]
        antes,n=self.estado(e),len(e.ed.undo_stack); avisos=[]; e.informar=avisos.append; e.sel=[]
        p=QPointF(c["x0"],c["y0"]+12); e.prensar(p); e.mover(p+QPointF(dx,dy)); e.soltar(p+QPointF(dx,dy))
        self.assertEqual(self.estado(e),antes); self.assertEqual(len(e.ed.undo_stack),n); self.assertTrue(avisos)

    def test_SLAZ11_marco_lleno_lleva_hijo_vacio_sin_doble_desplazamiento(self):
        """REQ-JER-05, REQ-EDT-03: un recinto anidado vacío acompaña al contenido y se deshace con él."""
        w,e,d=self.con_recinto(); e.ed.set_step_kind(d["a"], "enclosing"); e.cambia()
        e.pedir_texto=lambda *args: "Hijo"; hijo=e.anadir_recinto(d["a"]); c=cajas_parciales(e.M)[d["r"]]
        antes=self.estado(e); pos=self.pos(e); e.sel=[]; p=QPointF(c["x0"],c["y0"]+12)
        e.prensar(p); self.assertIn(hijo,e.arrastre["ids"])
        e.mover(p+QPointF(60,40)); e.soltar(p+QPointF(60,40))
        self.assertEqual(self.pos(e)[hijo],(pos[hijo][0]+60,pos[hijo][1]+40))
        e.deshacer(); self.assertEqual(self.estado(e),antes)

    def test_SLAZ12_marco_lleno_lleva_barras_y_acciones_sueltas(self):
        """REQ-EDT-03, REQ-EDT-05: todo lo contenido en el marco, incluidas barras y acciones sueltas, se mueve junto."""
        w,e,d=self.con_recinto(); pos=self.pos(e); ax,ay=pos[d["a"]]
        e.ed.move(d["b"],ax+320,ay+320)
        bid=e.ed.add_bar("Y",(ax+100,ay+180),width=80)
        aid=e.ed.add_draft_action((ax+100,ay+250)); e.cambia()
        antes=self.estado(e); c=cajas_parciales(e.M)[d["r"]]; p=QPointF(c["x0"],c["y0"]+12);e.sel=[]
        e.prensar(p); self.assertTrue({bid,aid} <= set(e.arrastre["ids"]))
        e.mover(p+QPointF(60,40));e.soltar(p+QPointF(60,40))
        bar=next(b for b in e.ed.bars() if b["id"]==bid); accion=next(a for a in e.ed.draft_actions() if a["id"]==aid)
        self.assertEqual((float(bar["x"]),float(bar["y"])),(ax+160,ay+220))
        self.assertEqual((float(accion["x"]),float(accion["y"])),(ax+160,ay+290))
        e.deshacer();self.assertEqual(self.estado(e),antes)
