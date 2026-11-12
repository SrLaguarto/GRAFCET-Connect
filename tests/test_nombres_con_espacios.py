"""Nombres de variable con espacios interiores («Marcha motor», «Fin de carrera 1»): decisión del responsable (12-nov-2026).

La fórmula ya no se escribe a mano (solo se monta con bloques): el núcleo escribe entre comillas invertidas todo nombre que no
es una palabra simple (`Marcha motor`, igual que `1M1`, P-IMP-46) y el usuario nunca las ve ni las teclea. Ninguna es oráculo
del documento 11: comprueban la regla de nombres de la interfaz y que cada sitio donde se muestra, se compara o se convierte
a texto de fórmula un nombre de variable funciona con espacios.
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

MARCHA, FIN, LUZ, CUENTA = "Marcha motor", "Fin de carrera 1", "Luz de aviso", "Cuenta total"


@unittest.skipUnless(QT, "Falta PySide6")
class NombresConEspacios(BaseQt):
    def setUp(self):
        super().setUp()
        self.w.resize(1360, 860)
        self.w.show()
        self.w, self.e = self.vacio()
        QApplication.processEvents()
        self.addCleanup(self.w.hide)

    # -- ayudas -----------------------------------------------------------------------------------------------
    def construir(self):
        """E0 -[Marcha motor AND NOT Fin de carrera 1]-> E1 -[Fin de carrera 1]-> E0; E1 activa «Luz de aviso» y
        suma 1 a «Cuenta total» al activarse. Las fórmulas, con bloques, como las monta el usuario."""
        e, w = self.e, self.w
        for n, papel, tipo in ((MARCHA, "input", "bool"), (FIN, "input", "bool"), (LUZ, "output", "bool"),
                               (CUENTA, "internal", "int")):
            self.assertIsNone(e.nueva_variable(n, papel, {"kind": tipo}), n)
        ids = self.cadena(e, entradas=())
        e0, t1, e1, t2 = ids
        e.conectar(t2, e0)
        e.seleccionar([t1])
        lienzo = w.props.prog.lienzo
        lienzo.soltar((), bloques.var(MARCHA, "input"))
        lienzo.soltar((), bloques.nuevo("y"))
        lienzo.soltar(("b",), bloques.nuevo("no", a=bloques.var(FIN, "input")))
        e.seleccionar([t2])
        w.props.prog.lienzo.soltar((), bloques.var(FIN, "input"))
        e.seleccionar([e1])
        d = self.panel_accion(e1)
        d.variable.setCurrentText(LUZ)
        d = self.panel_accion(e1)
        self.poner_tipo(d, "activacion")
        d.variable.setCurrentText(CUENTA)
        d._desde_bloques(f"`{CUENTA}` + 1")
        return e0, t1, e1, t2

    def panel_accion(self, sid):
        w, e = self.w, self.e
        e.anadir_accion(sid)
        return w.props.accion

    @staticmethod
    def poner_tipo(d, tipo):
        d.e.tipo_accion(d.aid, tipo)

    def nombres(self):
        return [v["name"] for v in self.e.ed.model["variables"]]

    # -- la regla ---------------------------------------------------------------------------------------------
    def test_SNES01_regla_de_nombres_con_espacios(self):
        """REQ-EDT-07, REQ-EDT-09: se admite un espacio interior entre palabras; no al principio, al final ni dos seguidos; los
        símbolos, las palabras reservadas, solo cifras, la duración y el parecido a X1 siguen rechazados."""
        m = Edicion.motivo_nombre
        for n in ("Marcha motor", "Fin de carrera 1", "mi var", "a b", "Eje X", "1 M1", "Sensor I0.1", "Posición 2 final",
                  "Bomba de agua 2", "Válvula Sí"):
            self.assertIsNone(m(n), n)
        for n in ("a  b", " a", "a ", "  ", "a   b", "Marcha  motor"):
            self.assertIn("espacio", m(n) or "", repr(n))
        for n in ("a-b", "a b-c", "(x) y", "a+ b", "a\tb", "a b", "a, b", "a `b`", "mi var!"):
            self.assertIn("no puede ser nombre de variable", m(n) or "", repr(n))
        self.assertIn("debe empezar", m("1 2") or "", "cifras separadas por un espacio: sin letra")
        self.assertIn("palabra de las fórmulas", m("AND") or "")
        self.assertIn("palabra de las fórmulas", m(" and ") or "")
        self.assertIn("duración", m("1 s") or "")
        self.assertIn("se confundiría con la actividad de la etapa 1", m("X 1") or "")
        self.assertIn("se confundiría con la actividad de la etapa 12", m("X12") or "")
        self.assertIn("empieza por X", m("Fin X1") or "", "una palabra X… dentro de un nombre se leería como etapa")
        self.assertIsNone(m("XX1"))
        self.assertIsNone(m("Xmarcha"))

    def test_SNES02_los_espacios_de_los_extremos_se_recortan_y_los_repetidos_se_detectan(self):
        """REQ-EDT-07, REQ-EDT-09: al confirmar se recortan los espacios del principio y del final; «a b» repetido se rechaza
        igual escrito con espacios de más en los extremos."""
        e = self.e
        self.assertIsNone(e.nueva_variable("  Marcha motor  "))
        self.assertEqual(self.nombres(), [MARCHA])
        self.assertIn("espacio", e.nueva_variable("Marcha  motor") or "")
        self.assertEqual(e.motivo_variable_nueva(" Marcha motor "), f"variable «{MARCHA}» ya existe en el ámbito")
        self.assertIn("Ya existe otra variable", e.nueva_variable("Marcha motor ") or "")
        self.assertEqual(self.nombres(), [MARCHA])
        self.assertEqual(e.motivo_variable_nueva("   "), "Falta el nombre.")
        self.assertIsNone(e.nueva_variable("Fin de carrera 1"))
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == FIN)
        self.assertIn("Ya existe", e.cambiar_variable(vid, nombre=" Marcha motor ") or "")
        self.assertIsNone(e.cambiar_variable(vid, nombre="  Fin de carrera 2 "))
        self.assertEqual(self.nombres(), [MARCHA, "Fin de carrera 2"])

    # -- crear, usar, simular ---------------------------------------------------------------------------------
    def test_SNES03_receptividad_y_acciones_con_bloques_se_simulan(self):
        """REQ-EDT-02, REQ-EDT-07, REQ-SIM-01: «Marcha motor AND NOT Fin de carrera 1» montada con bloques y acciones sobre
        variables con espacios; el modelo guarda el nombre tal cual (entre comillas invertidas en el texto del núcleo) y el
        grafcet evoluciona al simular."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        self.assertEqual(e.texto_condicion(t1), f"`{MARCHA}` AND NOT `{FIN}`")
        self.assertEqual(e.texto_condicion(t2), f"`{FIN}`")
        e.seleccionar([t1])
        self.assertEqual(w.props.prog.lienzo.arbol["a"], {"k": "var", "n": MARCHA, "papel": "input"})
        self.assertEqual(w.props.prog.lienzo.arbol["b"]["a"], {"k": "var", "n": FIN, "papel": "input"})
        self.assertEqual({a["targetRef"] for a in e.ed.model["actions"]},
                         {v["id"] for v in e.ed.model["variables"] if v["name"] in (LUZ, CUENTA)})
        self.assertTrue(e.ed.validate().can_simulate, [str(d) for d in e.ed.validate().diagnostics])
        self.assertTrue(w.cambiar_modo("simular"))
        self.assertEqual(w.v.state()["situation"], [e0])
        vid = {v["name"]: v["id"] for v in e.ed.model["variables"]}
        self.assertEqual(w.botones[vid[MARCHA]].text(), f"{MARCHA} = 0")
        w._cambiar_tipo_entrada(vid[MARCHA], True)
        w.botones[vid[MARCHA]].click()
        self.assertEqual(w.v.state()["situation"], [e1], "Marcha motor = 1 y Fin de carrera 1 = 0: avanza")
        estado = w.v.state()
        self.assertEqual((estado["outputs"][vid[LUZ]]["value"], estado["values"][vid[CUENTA]]), (True, "1"), "las acciones se ejecutan")
        w._cambiar_tipo_entrada(vid[FIN], True)
        w.botones[vid[FIN]].click()
        self.assertEqual(w.v.state()["situation"], [e0], "Fin de carrera 1 = 1 devuelve a E0")
        # la traza y el panel dicen los nombres tal cual, sin comillas invertidas
        textos = [w.traza.item(i).text() for i in range(w.traza.count())]
        self.assertFalse(any("`" in t for t in textos), textos)
        self.assertFalse(any("`" in b.text() for b in w.botones.values()))

    def test_SNES04_dibujo_formula_y_propiedades_sin_comillas_invertidas(self):
        """REQ-EDT-02, REQ-EDT-09: lo que se ve en el dibujo, en el campo «Fórmula» (solo lectura), en «Se dibuja», en el
        desplegable de la acción y en la tabla lleva el nombre con espacios y sin comillas invertidas."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        e.seleccionar([t1])
        p = w.props
        p._previsualizar()
        html_formula = (p.t_texto.html_mostrado() or "").replace("&nbsp;", " ")
        self.assertIn(MARCHA, html_formula)
        self.assertIn(FIN, html_formula)
        self.assertNotIn("`", html_formula)
        dibujo = p.t_dibujo.text().replace("&nbsp;", " ")
        self.assertNotIn("`", dibujo)
        self.assertIn(FIN, dibujo)
        self.assertTrue(p.t_texto.isReadOnly())
        cond = "".join(x["t"] for x in next(t for t in e.M["transitions"] if t["id"] == t1)["cond"]).replace(" ", " ")
        self.assertIn(MARCHA, cond)
        self.assertIn(FIN, cond)
        self.assertNotIn("`", cond)
        for a in next(s for s in e.M["steps"] if s["id"] == e1)["actions"]:
            self.assertNotIn("`", "".join(t["t"] for t in a["text"]))
        textos = [x for x in (a for s in e.M["steps"] for a in s["actions"])]
        self.assertTrue(any(CUENTA in "".join(t["t"] for t in a["text"]) for a in textos))
        # los bloques: el desplegable de las fichas ofrece el nombre tal cual
        motor = bloques.Motor(w.props.prog.fuente)
        motor.reiniciar()
        e.seleccionar([t1])
        nombres_ficha = [x[2] for x in motor.elementos(w.props.prog.lienzo.arbol["a"])]
        self.assertEqual(nombres_ficha, [MARCHA])
        d = self.panel_accion(e1)
        self.assertIn(LUZ, [d.variable.itemData(i) for i in range(d.variable.count())])
        # la tabla de variables
        pv = w.variables
        self.assertTrue({MARCHA, FIN, LUZ, CUENTA} <= {pv.tabla.item(r, 0).text() for r in range(pv.tabla.rowCount())})

    def test_SNES05_guardar_abrir_renombrar_y_copiar(self):
        """REQ-DAT-01, REQ-EDT-07, REQ-EDT-14: el proyecto con nombres con espacios se guarda y se abre igual; renombrar una
        variable reescribe sus usos (entre comillas invertidas si hay espacios); copiar y pegar la transición conserva los
        nombres."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        destino = Path(self.tmp.name) / "con-espacios"
        e.guardar(destino)
        ab = open_model(destino)
        self.assertEqual({v["name"] for v in ab.doc["variables"]}, {MARCHA, FIN, LUZ, CUENTA})
        e2 = Edicion.desde(ab.doc, {}, "abierto", destino, ab.presentations[0])
        self.assertEqual(e2.texto_condicion(t1), f"`{MARCHA}` AND NOT `{FIN}`")
        self.assertTrue(e2.ed.validate().can_simulate)
        # renombrar a otro nombre con espacios, a uno simple y de uno simple a uno con espacios
        vid = next(v["id"] for v in e.ed.model["variables"] if v["name"] == FIN)
        self.assertIsNone(e.cambiar_variable(vid, nombre="Final de recorrido 2"))
        self.assertEqual(e.texto_condicion(t1), f"`{MARCHA}` AND NOT `Final de recorrido 2`")
        self.assertEqual(e.texto_condicion(t2), "`Final de recorrido 2`")
        self.assertIsNone(e.cambiar_variable(vid, nombre="final"))
        self.assertEqual(e.texto_condicion(t2), "final")
        self.assertEqual(e.texto_condicion(t1), f"`{MARCHA}` AND NOT final")
        self.assertIsNone(e.cambiar_variable(vid, nombre="Fin de carrera 1"))
        self.assertEqual(e.texto_condicion(t1), f"`{MARCHA}` AND NOT `{FIN}`")
        self.assertIn("espacio", e.cambiar_variable(vid, nombre="Fin  de carrera") or "")
        self.assertTrue(e.ed.validate().can_simulate)
        # copiar y pegar
        n = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]))
        frag = e.copiar_fragmento([e0, t1, e1, t2])
        self.assertTrue(e.pegar_fragmento(frag, QPointF(500, 300)))
        self.assertEqual((len(e.ed.model["steps"]), len(e.ed.model["transitions"])), (2 * n[0], 2 * n[1]))
        self.assertEqual(sorted(self.nombres()), sorted([MARCHA, FIN, LUZ, CUENTA]), "las variables no se duplican")
        textos = [e.texto_condicion(t["id"]) for t in e.ed.model["transitions"]]
        self.assertEqual(sorted(textos), sorted([f"`{MARCHA}` AND NOT `{FIN}`", f"`{FIN}`"] * 2))
        self.assertTrue(e.ed.validate().diagnostics is not None)

    def test_SNES06_pegar_variables_desde_una_hoja_de_calculo(self):
        """REQ-EDT-07: una fila pegada con un nombre con espacios se crea (con los espacios de los extremos recortados); la
        de dos espacios seguidos o con símbolos queda con error y su motivo."""
        pv = self.w.variables
        texto = "Marcha motor\tEntrada\tBooleana\n  Fin de carrera 1 \tEntrada\tBooleana\nLuz  de aviso\tSalida\nVálvula (2)\tSalida\n"
        pv.pegar_texto(texto)
        self.assertEqual(self.nombres(), [MARCHA, FIN])
        errores = {f["nombre"]: f["err"][0] for f in pv._pend}
        self.assertEqual(set(errores), {"Luz  de aviso", "Válvula (2)"})
        self.assertIn("espacio", errores["Luz  de aviso"])
        self.assertIn("símbolos", errores["Válvula (2)"])
        # se corrige el nombre con espacios de más y se crea
        f = next(f for f in pv._pend if f["nombre"] == "Luz  de aviso")
        pv.tabla.item(pv._filas.index(f), 0).setText("Luz de aviso")
        QApplication.processEvents()
        self.assertIn(LUZ, self.nombres())

    def test_SNES07_la_tabla_de_variables_rechaza_dos_espacios_y_solo_espacios(self):
        """REQ-EDT-07: en la tabla, «  » no crea nada; «a  b» se rechaza con su motivo; «a b» se crea y se puede renombrar a
        otro con espacios."""
        pv, e = self.w.variables, self.e
        pv.nueva()
        fila = pv.tabla.rowCount() - 1
        pv.tabla.item(fila, 0).setText("  ")
        self.assertEqual(self.nombres(), [])
        pv.tabla.item(fila, 0).setText("a  b")
        self.assertIn("espacio", pv.msg.text())
        self.assertEqual(self.nombres(), [])
        pv.parpadeo.parar()
        pv.tabla.item(fila, 0).setText("Marcha motor")
        self.assertEqual((pv.msg.text(), self.nombres()), ("", [MARCHA]))
        r = next(r for r in range(pv.tabla.rowCount()) if pv.tabla.item(r, 0).text() == MARCHA)
        pv.tabla.item(r, 0).setText("Marcha motor 2")
        self.assertEqual(self.nombres(), ["Marcha motor 2"])
        pv.tabla.item(r, 0).setText("Marcha  motor")
        self.assertIn("espacio", pv.msg.text())
        self.assertEqual(self.nombres(), ["Marcha motor 2"])
        self.assertTrue(len(e.ed.undo_stack) >= 2)

    # -- el resto de sitios donde se ve el nombre ---------------------------------------------------------------
    def test_SNES08_lista_de_acciones_buscador_y_formulas_a_medias_sin_comillas(self):
        """REQ-EDT-02, REQ-EDT-09: la lista de acciones de la etapa, el buscador, el dibujo y los diagnósticos de una fórmula
        a medias (con un «?») citan el nombre con espacios sin comillas invertidas."""
        w, e = self.w, self.e
        e0, t1, e1, t2 = self.construir()
        resumenes = [e.resumen_accion(a) for a in e.acciones(e1)]
        self.assertIn(f"{CUENTA} := {CUENTA} + 1   (al activar ↑)", resumenes)
        self.assertIn(f"{LUZ}   (continua)", resumenes)
        self.assertFalse(any("`" in r for r in resumenes), resumenes)
        # una condición de acción con un nombre con espacios
        aid = next(a["id"] for a in e.acciones(e1) if a["variable"] == LUZ)
        self.assertIsNone(e.cambiar_accion(aid, {**e.datos_accion(aid), "tipo": "condicionada", "condicion": f"`{MARCHA}`"}))
        self.assertIn(f"{LUZ}   si {MARCHA}", [e.resumen_accion(a) for a in e.acciones(e1)])
        textos = [x["texto"] for x in w.navegacion.datos]
        self.assertTrue(any(LUZ in t for t in textos) and any(CUENTA in t for t in textos), textos)
        self.assertFalse(any("`" in t for t in textos), textos)
        # una fórmula a medias: ni el dibujo, ni el diagnóstico, ni el campo (su pintado) llevan comillas invertidas
        e.seleccionar([t2])
        w.props.prog.lienzo.soltar((), bloques.nuevo("y"))
        self.assertEqual(e.texto_condicion(t2), f"`{FIN}` AND ?")
        self.assertEqual("".join(x["t"] for x in next(t for t in e.M["transitions"] if t["id"] == t2)["cond"]), f"{FIN} AND ?")
        mensajes = [x["message"] for x in e.diagnosticos()]
        self.assertTrue(any(FIN in m for m in mensajes), mensajes)
        self.assertFalse(any("`" in m for m in mensajes), mensajes)
        self.assertNotIn("`", w.props.t_estado.text())
        self.assertIsNone(w.props.t_texto.html_mostrado(), "no se interpreta: se pinta el texto")
        self.assertIn("`", w.props.t_texto.text(), "(el texto interno del campo no cambia)")

    def test_SNES09_vista_de_es_y_modbus_usan_el_id_no_el_nombre(self):
        """REQ-DAT-01, REQ-EDT-07: la vista de E/S muestra los nombres con espacios; la configuración Modbus asigna las señales por
        el id de la variable, así que un nombre con espacios (o renombrar) no cambia el mapa."""
        w, e = self.w, self.e
        self.construir()
        QApplication.processEvents()
        p = w.panel_es
        vid = {v["name"]: v["id"] for v in e.ed.model["variables"]}
        self.assertEqual([v["name"] for v in p.variables], [MARCHA, FIN, LUZ])
        self.assertEqual(p.autoasignar(set(vid.values())), [])
        senales = {s.variable: (s.area, s.direccion) for s in p.config.senales}
        self.assertEqual(senales, {vid[MARCHA]: ("discrete", 0), vid[FIN]: ("discrete", 1), vid[LUZ]: ("coil", 0)})
        self.assertFalse(any(" " in s.variable for s in p.config.senales))
        self.assertIsNone(e.cambiar_variable(vid[LUZ], nombre="Luz de alarma roja"))
        QApplication.processEvents()
        p.cargar(e.ed.model, p.config)
        self.assertEqual({s.variable: (s.area, s.direccion) for s in p.config.senales}, senales, "el mapa no cambia")
        self.assertIn("Luz de alarma roja", [v["name"] for v in p.variables])


if __name__ == "__main__":
    unittest.main()
