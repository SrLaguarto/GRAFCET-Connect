"""Nombres de variable con «+» y «-» («A+», «A-», «1V1-14», «Cilindro A+»): decisión del responsable (12-nov-2026), notación de
neumática; se suman a los espacios de P-IMP-142.

La fórmula no se escribe a mano: el núcleo escribe entre comillas invertidas todo nombre que no es una palabra simple (`A+`,
como `Marcha motor` o `1M1`) y el usuario nunca las ve. Ninguna es oráculo del documento 11: comprueban la regla de nombres de la
interfaz y que cada sitio donde un nombre se muestra, se compara o se convierte a texto de fórmula funciona con «+» y «-», sin
confundirlos con el OR (« + »), la resta ni un signo.
"""
import unittest
from pathlib import Path

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication
    from escritorio import bloques
    from escritorio.edicion import Edicion
    from grafcet.persistence import open_model

AMAS, AMENOS, BMENOS, V1, CIL, CUENTA = "A+", "A-", "B-", "1V1-14", "Cilindro A+", "Cuenta-1"


def _texto(e, tid):
    return "".join(x["t"] for x in next(t for t in e.M["transitions"] if t["id"] == tid)["cond"]).replace(" ", " ")


@unittest.skipUnless(QT, "Falta PySide6")
class NombresConSignos(BaseQt):
    def setUp(self):
        super().setUp()
        self.w.resize(1360, 860)
        self.w.show()
        self.w, self.e = self.vacio()
        QApplication.processEvents()
        self.addCleanup(self.w.hide)

    def nombres(self):
        return [v["name"] for v in self.e.ed.model["variables"]]

    def declarar(self, *datos):
        for n, papel, tipo in datos:
            self.assertIsNone(self.e.nueva_variable(n, papel, {"kind": tipo}), n)

    def construir(self):
        """E0 -[A+ OR B-]-> E1 -[A+ AND NOT A-]-> E0; E1 activa «Cilindro A+» y hace «Cuenta-1 := Cuenta-1 + 1» al activarse."""
        e, w = self.e, self.w
        self.declarar((AMAS, "input", "bool"), (AMENOS, "input", "bool"), (BMENOS, "input", "bool"),
                      (CIL, "output", "bool"), (CUENTA, "internal", "int"))
        e0, t1, e1, t2 = self.cadena(e, entradas=())
        e.conectar(t2, e0)
        e.seleccionar([t1])
        lienzo = w.props.prog.lienzo
        lienzo.soltar((), bloques.nuevo("o"))
        lienzo.soltar(("a",), bloques.var(AMAS, "input"))
        lienzo.soltar(("b",), bloques.var(BMENOS, "input"))
        e.seleccionar([t2])
        lienzo = w.props.prog.lienzo
        lienzo.soltar((), bloques.var(AMAS, "input"))
        lienzo.soltar((), bloques.nuevo("y"))
        lienzo.soltar(("b",), bloques.nuevo("no", a=bloques.var(AMENOS, "input")))
        e.seleccionar([e1])
        e.anadir_accion(e1)
        d = w.props.accion
        d.variable.setCurrentText(CIL)
        e.anadir_accion(e1)
        d = w.props.accion
        d.e.tipo_accion(d.aid, "activacion")
        d.variable.setCurrentText(CUENTA)
        d._desde_bloques(f"`{CUENTA}` + 1")
        return e0, t1, e1, t2

    def test_SNSG01_regla_de_nombres_con_signos(self):
        """REQ-EDT-07, REQ-EDT-09: «+» y «-» se admiten dentro de un nombre pero no como primer carácter; los demás símbolos
        siguen rechazados; las demás reglas (reservadas, número, duración, parecido a X1, espacios) siguen."""
        m = Edicion.motivo_nombre
        for n in ("A+", "A-", "B-", "1V1-14", "Cilindro A+", "Cuenta-1", "A+-", "A--", "A++", "a-b", "a b-c", "S1+ final",
                  "Fin-de-carrera", "2S1+", "Pos A-", "Cilindro +A"):
            self.assertIsNone(m(n), n)
        for n in ("+A", "-1", "-", "+", "A *", "A*", "A/B", "A=B", "A+ ", " A+", "A+  B", "(x) y", "A+(", "A!", "a, b",
                  "A + B", "A -", "1-2", "1+", "-A"):
            self.assertIn("no puede ser nombre de variable", m(n) or "", repr(n))
        self.assertIn("solo un número", m("12") or "")
        self.assertIn("debe empezar", m("1-2") or "", "«1-2» no tiene letra: parece una resta de números")
        self.assertIn("duración", m("3s") or "")
        self.assertIn("palabra de las fórmulas", m("AND") or "")
        self.assertIn("se confundiría con la actividad de la etapa 1", m("X1") or "")

    def test_SNSG02_receptividad_con_bloques_se_lee_sin_comillas_y_con_el_or_espaciado(self):
        """REQ-EDT-02, REQ-EDT-07, REQ-EDT-09: «A+ OR B-» y «A+ AND NOT A-» con bloques; en el dibujo el OR es « + » y el AND
        « · » con espacios, y los nombres se leen tal cual: «A+ + B-»."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        self.assertEqual(e.texto_condicion(t1), f"`{AMAS}` OR `{BMENOS}`")
        self.assertEqual(e.texto_condicion(t2), f"`{AMAS}` AND NOT `{AMENOS}`")
        self.assertEqual(_texto(e, t1), "A+ + B-")
        self.assertEqual(_texto(e, t2), "A+ · A-", "(el NOT es un sobrerrayado: el texto no lo repite)")
        self.assertTrue(e.ed.validate().can_simulate, [str(d) for d in e.ed.validate().diagnostics])
        e.seleccionar([t1])
        self.assertEqual(w.props.prog.lienzo.arbol["a"], {"k": "var", "n": AMAS, "papel": "input"})
        p = w.props
        p._previsualizar()
        html = (p.t_texto.html_mostrado() or "").replace("&nbsp;", " ")
        self.assertNotIn("`", html)
        self.assertIn("A+ + B-", html)
        self.assertNotIn("`", p.t_dibujo.text())
        motor = bloques.Motor(w.props.prog.fuente)
        motor.reiniciar()
        self.assertEqual([x[2] for x in motor.elementos(w.props.prog.lienzo.arbol["a"])], [AMAS])
        e.anadir_accion(e1)
        d = w.props.accion
        self.assertIn(CIL, [d.variable.itemData(i) for i in range(d.variable.count())])

    def test_SNSG03_simular_y_evolucionar(self):
        """REQ-SIM-01, REQ-EDT-07: con «A+», «B-» y «A-» la red evoluciona (y «NOT A-» la retiene); las acciones se ejecutan y la traza y los botones
        no llevan comillas invertidas."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.v.state()["situation"], [e0])
        vid = {v["name"]: v["id"] for v in e.ed.model["variables"]}
        self.assertEqual(w.botones[vid[AMAS]].text(), f"{AMAS} = 0")
        for n in (AMAS, AMENOS, BMENOS):
            w._cambiar_tipo_entrada(vid[n], True)
        w.botones[vid[BMENOS]].click()
        self.assertEqual(w.v.state()["situation"], [e1], "B- = 1 satisface A+ OR B-")
        estado = w.v.state()
        self.assertEqual((estado["outputs"][vid[CIL]]["value"], estado["values"][vid[CUENTA]]), (True, "1"))
        w.botones[vid[BMENOS]].click()
        w.botones[vid[AMENOS]].click()
        w.botones[vid[AMAS]].click()
        self.assertEqual(w.v.state()["situation"], [e1], "A+ = 1 pero A- = 1: NOT A- lo impide")
        textos = [w.traza.item(i).text() for i in range(w.traza.count())]
        self.assertFalse(any("`" in t for t in textos), textos)
        self.assertFalse(any("`" in b.text() for b in w.botones.values()))

    def test_SNSG04_accion_con_aritmetica_sobre_una_memoria_con_guion(self):
        """REQ-EDT-02, REQ-EDT-07: «Cuenta-1 := Cuenta-1 + 1»: el guion del nombre no se lee como resta; el resumen y el dibujo
        lo dicen tal cual, y la acción sobre «Cilindro A+» es continua."""
        e = self.e
        e0, t1, e1, t2 = self.construir()
        resumenes = [e.resumen_accion(a) for a in e.acciones(e1)]
        self.assertIn(f"{CUENTA} := {CUENTA} + 1   (al activar ↑)", resumenes)
        self.assertIn(f"{CIL}   (continua)", resumenes)
        self.assertFalse(any("`" in r for r in resumenes), resumenes)
        textos = ["".join(t["t"] for t in a["text"]).replace(" ", " ")
                  for s in e.M["steps"] if s["id"] == e1 for a in s["actions"]]
        self.assertTrue(any("Cuenta-1 := Cuenta-1 + 1" in t for t in textos), textos)
        aid = next(a["id"] for a in e.acciones(e1) if a["variable"] == CUENTA)
        self.assertIsNone(e.cambiar_accion(aid, {**e.datos_accion(aid), "valor": f"`{CUENTA}` - 1"}))
        self.assertIn(f"{CUENTA} := {CUENTA} - 1", [r.split("   ")[0] for r in (e.resumen_accion(a) for a in e.acciones(e1))])
        self.assertTrue(e.ed.validate().can_simulate)

    def test_SNSG05_guardar_abrir_renombrar_y_copiar(self):
        """REQ-DAT-01, REQ-EDT-07, REQ-EDT-14: el proyecto con «+» y «-» se guarda y se abre igual; renombrar reescribe los usos
        y copiar y pegar conserva los nombres."""
        e = self.e
        e0, t1, e1, t2 = self.construir()
        destino = Path(self.tmp.name) / "con-signos"
        e.guardar(destino)
        ab = open_model(destino)
        self.assertEqual({v["name"] for v in ab.doc["variables"]}, {AMAS, AMENOS, BMENOS, CIL, CUENTA})
        e2 = Edicion.desde(ab.doc, {}, "abierto", destino, ab.presentations[0])
        self.assertEqual(e2.texto_condicion(t1), f"`{AMAS}` OR `{BMENOS}`")
        self.assertTrue(e2.ed.validate().can_simulate)
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == AMENOS)
        self.assertIsNone(e.cambiar_variable(vid, nombre="1V1-14"))
        self.assertEqual(e.texto_condicion(t2), f"`{AMAS}` AND NOT `1V1-14`")
        self.assertIsNone(e.cambiar_variable(vid, nombre="fin"))
        self.assertEqual(e.texto_condicion(t2), f"`{AMAS}` AND NOT fin")
        self.assertIsNone(e.cambiar_variable(vid, nombre="A-"))
        self.assertIn("no puede ser", e.cambiar_variable(vid, nombre="-A") or "")
        n = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]))
        frag = e.copiar_fragmento([e0, t1, e1, t2])
        self.assertTrue(e.pegar_fragmento(frag, QPointF(500, 300)))
        self.assertEqual((len(e.ed.model["steps"]), len(e.ed.model["transitions"])), (2 * n[0], 2 * n[1]))
        self.assertEqual(sorted(self.nombres()), sorted([AMAS, AMENOS, BMENOS, CIL, CUENTA]))
        self.assertTrue(e.ed.validate().can_simulate)

    def test_SNSG06_pegar_desde_una_hoja_de_calculo(self):
        """REQ-EDT-07: «A+» y «A-» en la celda del nombre se crean como nombres, no se toman por signos; «+A» y «A*» quedan con
        su error."""
        pv = self.w.variables
        pv.pegar_texto("A+\tEntrada\tBooleana\nA-\tEntrada\tBooleana\n1V1-14\tSalida\nCilindro A+\tSalida\n+A\tEntrada\nA*\tEntrada\n")
        self.assertEqual(self.nombres(), [AMAS, AMENOS, V1, CIL])
        errores = {f["nombre"]: f["err"][0] for f in pv._pend}
        self.assertEqual(set(errores), {"+A", "A*"})
        self.assertIn("no puede ser nombre", errores["+A"])

    def test_SNSG07_tabla_de_variables_buscador_y_es(self):
        """REQ-EDT-07: la tabla de variables, el buscador y la vista de E/S admiten y muestran los nombres con signos."""
        w = self.w
        self.construir()
        QApplication.processEvents()
        pv = w.variables
        self.assertTrue({AMAS, AMENOS, BMENOS, CIL, CUENTA} <= {pv.tabla.item(r, 0).text() for r in range(pv.tabla.rowCount())})
        pv.nueva()
        fila = pv.tabla.rowCount() - 1
        pv.tabla.item(fila, 0).setText("+X")
        self.assertIn("no puede ser", pv.msg.text())
        pv.parpadeo.parar()
        pv.tabla.item(fila, 0).setText(V1)
        self.assertIn(V1, self.nombres())
        textos = [x["texto"] for x in w.navegacion.datos]
        self.assertTrue(any(CIL in t for t in textos) and any(CUENTA in t for t in textos), textos)
        self.assertFalse(any("`" in t for t in textos), textos)
        self.assertIn(AMAS, [v["name"] for v in w.panel_es.variables])

    def test_SNSG08_formula_a_medias_y_diagnosticos_sin_comillas(self):
        """REQ-EDT-02, REQ-EDT-09: una fórmula a medias con un «?» y un nombre con signos no muestra comillas invertidas."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        e.seleccionar([t2])
        w.props.prog.lienzo.soltar((), bloques.nuevo("y"))
        self.assertIn("?", e.texto_condicion(t2))
        self.assertNotIn("`", _texto(e, t2))
        mensajes = [x["message"] for x in e.diagnosticos()]
        self.assertFalse(any("`" in m for m in mensajes), mensajes)
        self.assertNotIn("`", w.props.t_estado.text())

    def test_SNSG09_comparaciones_flancos_temporizaciones_y_valor_de_la_accion(self):
        """REQ-EDT-02, REQ-EDT-07: un nombre con guion en una comparación, un flanco, una temporización y como operando de la
        cuenta de una acción se escribe y se vuelve a leer en bloques sin comillas ni confundirse con una resta."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        self.declarar((V1, "input", "bool"))
        e.seleccionar([t2])
        lienzo = w.props.prog.lienzo
        lienzo.soltar((), bloques.nuevo("y"))
        lienzo.soltar(("a",), bloques.nuevo("cmp", n=CUENTA, op=">=", v="3"))
        lienzo.soltar(("b",), bloques.nuevo("sube", a=bloques.var(V1, "input")))
        self.assertEqual(e.texto_condicion(t2), f"`{CUENTA}` >= 3 AND rise(`{V1}`)")
        e.seleccionar([t1])
        e.seleccionar([t2])
        self.assertEqual(w.props.prog.lienzo.arbol["a"]["n"], CUENTA, "se vuelve a leer en bloques")
        self.assertEqual(w.props.prog.lienzo.arbol["b"]["a"]["n"], V1)
        e.seleccionar([t1])
        lienzo = w.props.prog.lienzo
        lienzo.soltar((), bloques.nuevo("temp", t1="2s", a=bloques.var(V1, "input")))
        self.assertEqual(e.texto_condicion(t1), f"delay(2 s, (`{V1}`), 0 s)")
        self.assertNotIn("`", _texto(e, t1))
        self.assertIn("1V1-14", _texto(e, t1))
        self.assertTrue(e.ed.validate().can_simulate, [str(d) for d in e.ed.validate().diagnostics])
        # el valor de la acción vuelve a leerse en bloques: «Cuenta-1 + 1» (nombre con guion, suma) sin romperse
        aid = next(a["id"] for a in e.acciones(e1) if a["variable"] == CUENTA)
        e.seleccionar([e1])
        w.props.accion.mostrar(e, aid)
        d = w.props.accion
        self.assertEqual(d.valor.text(), f"`{CUENTA}` + 1")
        html = (d.valor.html_mostrado() or "").replace("&nbsp;", " ")
        self.assertIn(f"{CUENTA} + 1", html)
        self.assertNotIn("`", html)
        self.assertEqual(d.prog.lienzo.arbol["a"]["n"], CUENTA, "el valor se vuelve a leer en bloques")


if __name__ == "__main__":
    unittest.main()
