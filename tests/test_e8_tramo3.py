"""SP8C (E8, tramo 3): acciones memorizadas con la fila «Variable := Valor», conmutador de partes, menú común de variable, «Falta N huecos»,
«Etiquetas de transiciones» en Ver y abrir en la parte pulsada."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from tools import hoja_contactos as HC
    from escritorio import estilo
    from escritorio.menu_variable import ROL_PAPEL, ROL_TIPO, UMBRAL_FILTRO
    QT = True
except ImportError:
    QT = False


def _bombear(n=8):
    for _ in range(n):
        QApplication.processEvents()


@unittest.skipUnless(QT, "requiere PySide6")
class Base(unittest.TestCase):
    def contexto(self, tipo, ancho=1366, alto=768):
        HC.aplicacion()
        c = HC.Contexto(ancho, alto)
        self.addCleanup(c.cerrar)
        HC._flotante(tipo)(c)
        return c, c.w.flot.panel, c.w.flot.principal

    @staticmethod
    def pixel(widget, x, y):
        img = widget.grab().toImage()
        d = img.devicePixelRatio()
        return img.pixelColor(round(x * d), round(y * d)).name()


class Memorizadas(Base):
    def test_SP8C01_titulos_exactos_de_las_acciones(self):
        """REQ-EDT-02, REQ-UX-01: el título de la ventana dice el tipo de acción: al activar, al desactivar, condicionada y por evento."""
        esperado = {"activacion": "Propiedades · Acción al activar", "evento": "Propiedades · Acción por evento",
                    "condicionada": "Propiedades · Acción condicionada"}
        for tipo, titulo in esperado.items():
            with self.subTest(tipo=tipo):
                c, p, v = self.contexto(tipo)
                self.assertEqual(v.titulo.text(), titulo)
        c, p, v = self.contexto("activacion")
        aid = c.e.accion_activa()
        d = dict(c.e.datos_accion(aid))
        d["tipo"] = "desactivacion"
        self.assertIsNone(c.e.cambiar_accion(aid, d))
        _bombear()
        self.assertEqual(c.w.flot.principal.titulo.text(), "Propiedades · Acción al desactivar")

    def test_SP8C02_titulo_de_la_limitada_heredada(self):
        """REQ-EDT-02: una acción limitada (de ficheros antiguos) se titula «Acción limitada»."""
        from escritorio.propiedades import TITULOS_ACCION
        self.assertEqual(TITULOS_ACCION["limitada"], "Acción limitada")
        self.assertEqual(TITULOS_ACCION["evento"], "Acción por evento")

    def test_SP8C03_la_fila_variable_asigna_valor_esta_en_una_fila_y_el_elegido_va_relleno(self):
        """REQ-EDT-02, REQ-UX-01: `Variable [▾] := [1 | 0]` en una sola fila de la tarjeta; el valor elegido, relleno del color de la acción y sin el
        borde naranja de los avisos."""
        c, p, v = self.contexto("activacion")
        a = p.accion
        fila = a.fila_variable
        for w in (a.l_variable, a.variable, a.l_fichas, a.caja_fichas):
            self.assertIs(w.parentWidget(), fila)
        ys = {w.geometry().center().y() for w in (a.variable, a.l_fichas, a.caja_fichas)}
        self.assertLessEqual(max(ys) - min(ys), 2, "los cuatro, a la misma altura")
        self.assertEqual(a.l_fichas.text(), ":=")
        a.fichas["1"].click()
        _bombear()
        self.assertTrue(a.fichas["1"].isChecked())
        from escritorio.acciones import ESTILO_FICHA
        self.assertNotIn(estilo.AVISO_BORDE, ESTILO_FICHA)
        centro = a.fichas["1"].mapTo(v, QPoint(6, a.fichas["1"].height() // 2))
        self.assertEqual(self.pixel(v, centro.x(), centro.y()), estilo.SENAL_ACCION.lower())
        otro = a.fichas["0"].mapTo(v, QPoint(a.fichas["0"].width() // 2, 4))
        self.assertEqual(self.pixel(v, otro.x(), otro.y()), estilo.SUPERFICIE)

    def test_SP8C04_sin_variable_1_y_0_desactivados(self):
        """REQ-EDT-02, P-IMP-156: sin variable, `? :=` con 1 y 0 desactivados."""
        c, p, v = self.contexto("activacion")
        aid = c.e.accion_activa()
        d = dict(c.e.datos_accion(aid))
        d["variable"] = ""
        c.e.cambiar_accion(aid, d)
        _bombear()
        a = c.w.flot.panel.accion
        self.assertEqual(a.variable.currentText(), "")
        self.assertTrue(all(not b.isEnabled() for b in a.fichas.values()))
        self.assertTrue(a.l_fichas.isVisible())

    def test_SP8C05_con_variable_numerica_el_valor_se_arma_en_la_misma_tarjeta(self):
        """REQ-EDT-02: con una variable numérica, el valor se arma con el formulador de la misma tarjeta, bajo la fila; no hay un segundo cuadro
        de fórmula a la vista."""
        c, p, v = self.contexto("activacion_numerica")
        a = p.accion
        self.assertTrue(v.accion.isAncestorOf(a.prog))
        self.assertTrue(a.prog.isVisible() and a.caja_fichas.isHidden())
        self.assertFalse(a.valor.isVisible(), "el texto del valor vive en un campo oculto")
        arriba = a.variable.mapTo(v, QPoint(0, 0)).y()
        abajo = a.prog.mapTo(v, QPoint(0, 0)).y()
        self.assertGreater(abajo, arriba + a.variable.height(), "el formulador, debajo de la fila")
        a.prog.lienzo.limpiar()
        a.prog.lienzo.insertar({"k": "num", "v": "5"})
        _bombear()
        self.assertEqual(c.e.datos_accion(c.e.accion_activa())["valor"], "5")


class Conmutador(Base):
    def _evento(self):
        c, p, v = self.contexto("evento")
        return c, c.w.flot, c.w.flot.panel, c.w.flot.principal

    def test_SP8C10_un_solo_formulador_a_la_vez_y_la_ventana_no_cambia_de_tamano(self):
        """REQ-EDT-02, P-IMP-173: Evento | Acción: una tarjeta cada vez, en la misma celda; al conmutar la ventana no cambia de tamaño."""
        c, f, p, v = self._evento()
        self.assertTrue(v.conmutadores[v.condicion].isVisible())
        self.assertTrue(v.condicion.isVisible() and not v.accion.isVisible())
        self.assertTrue(p.prog.isVisible() and not p.accion.variable.isVisible())
        tam = v.size()
        v.conmutadores[v.condicion].botones["accion"].click()
        _bombear()
        self.assertTrue(v.accion.isVisible() and not v.condicion.isVisible())
        self.assertTrue(p.accion.variable.isVisible() and not p.prog.isVisible())
        self.assertEqual(v.size(), tam)
        self.assertEqual(v.conmutadores[v.accion].botones["formula"].text(), "Evento")
        v.conmutadores[v.accion].botones["formula"].click()
        _bombear()
        self.assertTrue(v.condicion.isVisible())
        self.assertEqual(v.size(), tam)

    def test_SP8C11_la_condicionada_dice_condicion(self):
        """REQ-EDT-02: la parte de fórmula de una condicionada se llama «Condición», la de una acción por evento, «Evento»."""
        c, p, v = self.contexto("condicionada")
        self.assertEqual(v.conmutadores[v.condicion].botones["formula"].text(), "Condición")
        c2, p2, v2 = self.contexto("evento")
        self.assertEqual(v2.conmutadores[v2.condicion].botones["formula"].text(), "Evento")

    def test_SP8C12_clic_en_la_marca_o_en_la_caja_de_la_franja_cambia_de_parte(self):
        """REQ-EDT-02: un clic en la marca de la vista previa elige la condición o el evento; en la caja, la acción. La parte que no se edita va en gris."""
        c, p, v = self.contexto("evento")
        f, lupa = c.w.flot, v.lupa
        (marca, _), (caja, _) = lupa.partes
        t = lupa.transformar()
        QTest.mouseClick(lupa, Qt.MouseButton.LeftButton, pos=t.map(caja.center()).toPoint())
        _bombear()
        self.assertEqual(f._parte, "accion")
        self.assertTrue(v.accion.isVisible())
        colores = {es_caja: color for _, color, es_caja in lupa.senales}
        self.assertEqual(colores[True], estilo.SENAL_ACCION)
        self.assertEqual(colores[False], estilo.DESHABILITADO)
        QTest.mouseClick(lupa, Qt.MouseButton.LeftButton, pos=t.map(marca.center()).toPoint())
        _bombear()
        self.assertEqual(f._parte, "formula")
        self.assertTrue(v.condicion.isVisible())
        colores = {es_caja: color for _, color, es_caja in lupa.senales}
        self.assertEqual(colores[False], estilo.SENAL_CONDICION)
        self.assertEqual(colores[True], estilo.DESHABILITADO)

    def test_SP8C13_punto_de_aviso_en_la_parte_incompleta(self):
        """REQ-EDT-02: el punto de aviso del conmutador marca la parte a la que le falta algo."""
        c, p, v = self.contexto("evento")
        con = v.conmutadores[v.condicion]
        self.assertFalse(con.botones["formula"].aviso)
        self.assertFalse(con.botones["accion"].aviso)
        p.accion.poner_variable("aux")
        p._desde_bloques("")
        _bombear()
        self.assertTrue(con.botones["formula"].aviso, "sin evento, falta la parte de fórmula")
        self.assertFalse(con.botones["accion"].aviso)
        aid = c.e.accion_activa()
        d = dict(c.e.datos_accion(aid))
        d["variable"] = ""
        c.e.cambiar_accion(aid, d)
        _bombear()
        self.assertTrue(v.conmutadores[v.accion].botones["accion"].aviso, "sin variable, falta la acción")

    def test_SP8C14_esc_e_intro_funcionan_en_las_dos_pestanas(self):
        """REQ-EDT-02: Esc cierra la ventana sin guardar y Intro la cierra guardando, tanto con la condición como con la acción a la vista."""
        for parte in ("formula", "accion"):
            for tecla in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
                with self.subTest(parte=parte, tecla=tecla):
                    c, p, v = self.contexto("condicionada")
                    f = c.w.flot
                    f.elegir_parte(parte)
                    _bombear()
                    self.assertTrue(f.hay_ventanas())
                    QTest.keyClick(v, tecla)
                    _bombear()
                    self.assertFalse(f.hay_ventanas())

    def test_SP8C15_el_foco_pasa_a_la_parte_elegida(self):
        """REQ-EDT-02: al conmutar, el foco pasa a la tarjeta que se enseña (el área de bloques o la variable)."""
        c, f, p, v = self._evento()
        f.elegir_parte("accion")
        _bombear()
        self.assertIs(QApplication.focusWidget(), p.accion.variable)
        f.elegir_parte("formula")
        _bombear()
        self.assertIs(QApplication.focusWidget(), p.prog.lienzo)

    def test_SP8C16_sin_lateral(self):
        """REQ-EDT-02: la vista previa va siempre en franja (ya no existe el reparto lateral provisional)."""
        from escritorio.flotantes import GestorFlotantes
        self.assertFalse(hasattr(GestorFlotantes, "_lateral"))
        self.assertFalse(hasattr(GestorFlotantes, "_repartir_paneles"))
        c, f, p, v = self._evento()
        self.assertGreater(v.lupa.width(), v.width() // 2)


class Abrir(Base):
    def _caja(self, c, tipo):
        aid = next(a["id"] for a in c.e.ed.model["actions"] if c.e.datos_accion(a["id"])["tipo"] == tipo)
        return aid, next(x for x in c.w.diagrama.cajas_acciones if x["id"] == aid)

    def test_SP8C20_doble_clic_en_la_marca_abre_la_condicion_y_en_la_caja_la_accion(self):
        """REQ-EDT-02, REQ-UX-01: el doble clic en la marca abre Condición o Evento; en la caja, Acción."""
        HC.aplicacion()
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        HC._edicion(c)
        aid, caja = self._caja(c, "condicionada")
        x, y, w, h = caja["marca"]
        c.e.doble(QPointF(x + w / 2, y + h / 2))
        _bombear(10)
        f = c.w.flot
        self.assertEqual(f._parte, "formula")
        self.assertTrue(f.principal.condicion.isVisible())
        f.cerrar()
        _bombear()
        c.e.seleccionar([])
        x, y, w, h = caja["rect"]
        c.e.doble(QPointF(x + w / 2, y + h / 2))
        _bombear(10)
        self.assertEqual(f._parte, "accion")
        self.assertTrue(f.principal.accion.isVisible() and not f.principal.condicion.isVisible())
        f.cerrar()
        _bombear()
        self.assertIsNone(c.e.parte_pedida)


class Menu(Base):
    def test_SP8C30_menu_agrupado_con_tipo_corto_donde_varia(self):
        """REQ-EDT-02, P-IMP-154: el menú de la variable agrupa en Salidas y Memorias, con la barra de origen y el tipo corto solo donde varía."""
        c, p, v = self.contexto("activacion_numerica")
        combo = p.accion.variable
        filas = [(combo.itemData(i), combo.itemData(i, ROL_PAPEL), combo.itemData(i, ROL_TIPO)) for i in range(combo.count())
                 if isinstance(combo.itemData(i), str) and combo.itemData(i)]
        por_nombre = {n: (papel, tipo) for n, papel, tipo in filas}
        self.assertEqual(por_nombre["aux"][0], "internal")
        self.assertEqual(por_nombre["CT"], ("internal", "Ent"))
        self.assertEqual(por_nombre["aux"][1], "", "una booleana no lleva tipo")
        textos = [combo.itemText(i).strip() for i in range(combo.count())]
        self.assertIn("Salidas", textos)
        self.assertIn("Memorias", textos)
        combo.showPopup()
        _bombear()
        self.assertTrue(combo.view().isVisible())
        combo.hidePopup()

    def test_SP8C31_el_lienzo_usa_el_mismo_menu_y_solo_booleanas(self):
        """REQ-EDT-09: el desplegable sobre la acción continua usa la misma lista (delegado y vista) y solo ofrece booleanas."""
        from escritorio.menu_variable import DelegadoMenu, FiltroMenu
        HC.aplicacion()
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        HC._edicion(c)
        c.e.nueva_variable("CT", "internal", {"kind": "int"})
        aid = c.e.accion_activa() or next(a["id"] for a in c.e.ed.model["actions"])
        opciones = c.e.opciones_variable_accion(aid)
        self.assertNotIn("CT", [dato for _, dato, _, _ in opciones], "una continua solo ofrece booleanas")
        c.w.diagrama.abrir_selector((100, 100, 120, 44), opciones, "", lambda _: None)
        cb = c.w.diagrama._selector
        self.assertIsInstance(cb.filtro_menu, FiltroMenu)
        self.assertIsInstance(cb.view().itemDelegate(), DelegadoMenu)
        c.w.diagrama.cerrar_selector()

    def test_SP8C32_filtro_con_mas_de_doce_variables(self):
        """REQ-EDT-09: con más de 12 variables, lo que se escribe filtra la lista; con 12 o menos, no hay filtro."""
        from escritorio.menu_variable import ComboMenu, DelegadoMenu
        HC.aplicacion()
        combo = ComboMenu()
        self.addCleanup(combo.deleteLater)
        for i in range(UMBRAL_FILTRO + 3):
            combo.addItem(f"var{i:02d}", f"var{i:02d}")
            combo.setItemData(combo.count() - 1, "output", ROL_PAPEL)
        self.assertTrue(combo.con_filtro())
        vista = combo.view()
        combo.filtro_menu.poner_filtro("var1")
        ocultas = [vista.isRowHidden(i) for i in range(combo.count())]
        self.assertEqual(ocultas.count(False), 5)  # var10 a var14
        combo.filtro_menu.poner_filtro("")
        self.assertFalse(any(vista.isRowHidden(i) for i in range(combo.count())))
        pocos = ComboMenu()
        self.addCleanup(pocos.deleteLater)
        for i in range(UMBRAL_FILTRO):
            pocos.addItem(f"v{i}", f"v{i}")
        self.assertFalse(pocos.con_filtro())


class Huecos(Base):
    def test_SP8C40_falta_un_hueco_en_gris_con_huecos_resaltados(self):
        """REQ-EDT-02, P-IMP-155: una fórmula con huecos dice «Falta 1 hueco» o «Faltan N huecos» en gris y remarca los huecos del área; el rojo
        queda para los errores de verdad."""
        from escritorio.propiedades import GRIS_HUECOS
        from escritorio.bloques import texto_a_arbol
        from grafcet import expressions  # noqa: F401
        c, p, v = self.contexto("transicion")
        p._desde_bloques("marcha AND ?")
        _bombear()
        self.assertEqual(p.t_estado.text(), "Falta 1 hueco")
        self.assertEqual(p.t_estado.styleSheet(), GRIS_HUECOS)
        self.assertTrue(p.prog.lienzo.motor.resaltar_huecos)
        self.assertTrue(p.t_estado.isVisibleTo(p.caja_formula))
        p._desde_bloques("? AND ?")
        _bombear()
        self.assertEqual(p.t_estado.text(), "Faltan 2 huecos")
        p._desde_bloques("marcha AND paro")
        _bombear()
        self.assertFalse(p.prog.lienzo.motor.resaltar_huecos)
        self.assertNotIn("hueco", p.t_estado.text())

    def test_SP8C41_un_error_real_sigue_en_rojo(self):
        """REQ-EDT-02: lo que no es un hueco (una sintaxis rota) sigue en rojo."""
        from escritorio.propiedades import GRIS_HUECOS
        c, p, v = self.contexto("transicion")
        p.t_texto.setText("marcha AND AND paro")
        p._previsualizar()
        self.assertNotEqual(p.t_estado.styleSheet(), GRIS_HUECOS)
        self.assertIn("Error", p.t_estado.text())


class Etiquetas(Base):
    def _preparar(self):
        HC.aplicacion()
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        HC._edicion(c)
        return c, c.w, c.e

    def test_SP8C50_ver_etiquetas_deriva_de_labelVisible_y_se_deshace_de_una_vez(self):
        """REQ-EDT-02, REQ-EDT-05: «Etiquetas de transiciones» (Ver) se marca si todas las transiciones dibujan su etiqueta; cambiarla es una sola
        operación de deshacer; el modelo no cambia."""
        c, w, e = self._preparar()
        ids = [t["id"] for t in e.M["transitions"]]
        self.assertGreater(len(ids), 1)
        e.poner_etiquetas(True)
        self.assertTrue(e.etiquetas_visibles())
        w._sincronizar_menu_dibujo()
        self.assertTrue(w.a_ver_etiquetas.isChecked() and w.a_ver_etiquetas.isEnabled())
        modelo = repr(e.ed.model)
        n = len(e.ed.undo_stack)
        w.a_ver_etiquetas.setChecked(False)
        self.assertFalse(e.etiquetas_visibles())
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación")
        self.assertTrue(all(i in e.ed.hidden_labels() for i in ids))
        self.assertEqual(repr(e.ed.model), modelo)
        e.deshacer()
        self.assertTrue(e.etiquetas_visibles())

    def test_SP8C51_la_transicion_nueva_nace_como_estan_las_demas(self):
        """REQ-EDT-02: con las etiquetas a la vista, la transición nueva nace visible; con alguna oculta, o sin ninguna, nace oculta; todo en la misma
        operación que la crea."""
        c, w, e = self._preparar()
        e.poner_etiquetas(True)
        n = len(e.ed.undo_stack)
        t = e.poner_transicion(QPointF(900, 300))
        self.assertNotIn(t, e.ed.hidden_labels())
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.poner_etiquetas(False)
        t2 = e.poner_transicion(QPointF(900, 400))
        self.assertIn(t2, e.ed.hidden_labels())
        self.assertFalse(e.etiquetas_visibles())

    def test_SP8C52_sin_transiciones_la_opcion_esta_desactivada(self):
        """REQ-EDT-02: sin transiciones no hay estado que marcar: la opción de Ver se desactiva y la primera transición nace oculta."""
        c, w, e = self._preparar()
        for t in [t["id"] for t in e.M["transitions"]]:
            e.seleccionar([t])
            e.borrar()
        self.assertFalse(e.M["transitions"])
        w._sincronizar_menu_dibujo()
        self.assertFalse(w.a_ver_etiquetas.isEnabled() or w.a_ver_etiquetas.isChecked())
        t = e.poner_transicion(QPointF(900, 300))
        self.assertIn(t, e.ed.hidden_labels())

    def test_SP8C53_la_ventana_ya_no_tiene_mostrar_etiqueta(self):
        """REQ-EDT-02: «Mostrar etiqueta» sale de la ventana de la transición (lo reemplaza «Etiquetas de transiciones» de Ver)."""
        c, p, v = self.contexto("transicion")
        self.assertFalse(hasattr(p, "t_mostrar"))
        self.assertTrue(v.pie.isVisible())
        textos = [x.text() for x in v.pie.findChildren(type(v.pie.l_etiqueta))]
        self.assertNotIn("Mostrar etiqueta", textos)


if __name__ == "__main__":
    unittest.main()
