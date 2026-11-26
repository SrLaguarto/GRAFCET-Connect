"""SP8B: el formulador de la 2.0 (E8, P4 a P7): fichas nuevas, catálogo siempre visible, banda de categorías, herramientas y modo valor.
El modelo de la fórmula no cambia (lo prueban `test_formulas_ida_y_vuelta.py` y `test_bloques_modificadores.py`): aquí se prueba el dibujo (una
ficha con modificadores es una sola caja), la organización (catálogo y banda, sin pestañas) y las operaciones del área (pulsar, pegar, limpiar)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

try:
    from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt
    from PySide6.QtGui import QColor, QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

if QT:
    from escritorio import bloques, estilo
    from escritorio.bloques import (
        AVISO_FLANCO_TEMP, COLORES, MIME, MIME_FORMULA, AreaBloques, Motor, Programador,
        _Caja, arbol_a_texto, faltan, nuevo, texto_a_arbol, texto_a_arbol_valor, var,
    )
    from escritorio.paleta_variables import PaletaVariables

VARS = {"marcha": ("input", "bool"), "paro": ("input", "bool"), "Motor": ("output", "bool"), "M1": ("internal", "bool"),
        "CT": ("internal", "int")}
ETAPAS = ["X0", "X1"]


@unittest.skipUnless(QT, "requiere PySide6")
class FormuladorFichas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def programador(self, valor=False, historial=True, vars_=None, etapas=None):
        p = Programador(lambda: (vars_ or VARS, ETAPAS if etapas is None else etapas), historial=historial, valor=valor)
        self.addCleanup(p.close)
        p.resize(1000, 400)
        p.show()
        QApplication.processEvents()
        return p

    def caja(self, texto):
        """La caja que el Motor dibuja para la fórmula `texto` (a un ancho que cabe todo en una fila)."""
        m = Motor(lambda: (VARS, ETAPAS))
        m.reiniciar()
        arbol = texto_a_arbol(texto, VARS, ETAPAS)
        return m, m.caja(arbol, (0,), 2000)

    @staticmethod
    def borde(area, ruta):
        """Un punto sobre la barra de origen de la ficha de `ruta` (sin pieza: un clic ahí la elige, no abre su desplegable)."""
        area._calcular(area.width())
        r = next(r for r, rt, n in area._bloques if rt == ruta)
        return QPointF(r.left() + 2, r.center().y()).toPoint()

    def soltar(self, area, nodo, pos, origen=None):
        mime = QMimeData()
        mime.setData(MIME, json.dumps({"nodo": nodo, "grupo": area.grupo, "origen": origen}).encode())
        area.dropEvent(QDropEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))

    # -- P4: las fichas
    def test_SP8B01_ficha_con_modificadores_es_una_sola_caja(self):
        """REQ-EDT-02: una variable con NOT, ↑ o ↓ se dibuja como una sola ficha (no cajas anidadas), con su insignia y la barra de la
        negación; el hueco con modificador es la ficha pendiente."""
        for texto, mods, negada in (("marcha", [], ""), ("↑marcha", ["sube"], ""), ("↓marcha", ["baja"], ""), ("NOT marcha", ["no"], "nombre"),
                                    ("NOT ↑marcha", ["no", "sube"], "todo"), ("↑(NOT marcha)", ["sube", "no"], "nombre"),
                                    ("NOT X1", ["no"], "nombre")):
            with self.subTest(texto):
                m, c = self.caja(texto)
                self.assertEqual((c.forma, c.mods, c.negada), ("ficha", mods, negada))
                self.assertFalse([it for _, _, it in c.items if isinstance(it, _Caja)], "una sola caja")
                insignias = [it.clave for _, _, it in c.items if not isinstance(it, _Caja) and it.tipo == "mod"]
                self.assertEqual(insignias, [x for x in mods if x != "no"])
                self.assertEqual(c.destino, (0,) + ("a",) * len(mods), "lo que se suelta encima va a la variable de dentro")
        m, c = self.caja("NOT ?")
        self.assertEqual((c.forma, c.mods), ("pendiente", ["no"]))
        self.assertEqual(c.destino, (0, "a"))
        textos = [it.texto for _, _, it in c.items]
        self.assertEqual(textos, ["NOT", "pulsa o arrastra variable…"])
        m, c = self.caja("↑(NOT ?)")
        self.assertEqual([it.texto for _, _, it in c.items][0], "↑ NOT")

    def test_SP8B02_la_insignia_alterna_el_flanco_y_la_ficha_se_arrastra_entera(self):
        """REQ-EDT-02: pulsar la insignia ↑ de una ficha la cambia por ↓ (y al revés); arrastrar la ficha se lleva sus modificadores."""
        p = self.programador()
        p.poner("NOT ↑marcha")
        a = p.lienzo
        a._calcular(a.width())
        rect, tipo, ruta, clave = next(x for x in a._piezas if x[1] == "mod")
        self.assertEqual(clave, "sube")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
        self.assertEqual(p.texto(), "NOT ↓marcha")
        a._calcular(a.width())
        rect = next(x for x in a._piezas if x[1] == "mod")[0]
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
        self.assertEqual(p.texto(), "NOT ↑marcha", "y vuelve")
        # arrastrar desde la ficha (sin desplegable ▾ en 2.0.1): se lleva la ficha entera con sus modificadores
        a._calcular(a.width())
        self.assertEqual(a._ruta_arrastre((0, "a", "a")), (0,), "la ruta que se lleva es la de la ficha entera")
        self.assertFalse([x for x in a._piezas if x[1] == "drop"], "ficha booleana sin ▾ en el carril")
        mime = {}
        with mock.patch.object(bloques, "QDrag") as qdrag, mock.patch.object(bloques, "ejecutar_arrastre"):
            a._arrastrar(a._ruta_arrastre((0, "a", "a")))
            mime["datos"] = json.loads(bytes(qdrag.return_value.setMimeData.call_args.args[0].data(MIME)))
        self.assertEqual(arbol_a_texto(mime["datos"]["nodo"]), "NOT ↑marcha")

    def test_SP8B03_cada_origen_con_su_color_y_barra(self):
        """REQ-EDT-02, REQ-EDT-07: entrada ACENTO, salida SIMULACION, etapa EDICION y memoria ámbar (#b45309), en los colores y en la barra
        lateral de la ficha (se mira el píxel)."""
        self.assertEqual((COLORES["entrada"], COLORES["salida"], COLORES["etapa"], COLORES["interna"]),
                         (estilo.ACENTO, estilo.SIMULACION, estilo.EDICION, "#b45309"))
        p = self.programador()
        for texto, color in (("marcha", estilo.ACENTO), ("Motor", estilo.SIMULACION), ("X0", estilo.EDICION), ("M1", "#b45309")):
            with self.subTest(texto):
                p.poner(texto)
                imagen = p.lienzo.grab().toImage()
                cerca = {imagen.pixelColor(x, y).name() for x in range(bloques.MARGEN, bloques.MARGEN + 8)
                         for y in range(bloques.MARGEN, bloques.MARGEN + 28)}
                self.assertIn(QColor(color).name(), cerca, texto)
        # el catálogo lleva las mismas categorías de origen: la primera entrada
        self.assertEqual(p.paleta._cajas[0][0].cat, "entrada")

    def test_SP8B04_temporizador_contenedor_y_conectores_y_o(self):
        """REQ-EDT-02: el temporizador lleva hueco de bloques `[t1] / [base] / [t2]` (sin desplegable enorme ni TON/TOF);
        «y» y «o» son flujos planos (`sin_fondo=True`) con conectores `·` y `+`."""
        m = Motor(lambda: (VARS, ETAPAS))
        for texto, t1, t2 in (
            ("3s/marcha", "3s", "t2"),
            ("marcha/2s", "t1", "2s"),
            ("3s/marcha/2s", "3s", "2s"),
        ):
            with self.subTest(texto):
                m.reiniciar()
                c = m.caja(texto_a_arbol(texto, VARS, ETAPAS), (0,), 2000)
                self.assertEqual(c.forma, "ficha")
                self.assertEqual(len(c.items), 5)
                self.assertEqual((c.items[0][2].tipo, c.items[0][2].texto), ("campo", t1))
                self.assertEqual((c.items[1][2].tipo, c.items[1][2].texto), ("txt", "/"))
                self.assertIsInstance(c.items[2][2], _Caja)
                self.assertEqual(c.items[2][2].forma, "ficha")
                self.assertEqual((c.items[3][2].tipo, c.items[3][2].texto), ("txt", "/"))
                self.assertEqual((c.items[4][2].tipo, c.items[4][2].texto), ("campo", t2))
        m.reiniciar()
        arbol = nuevo("temp", t1="", t2="", a=None)
        c_vacio = m.caja(arbol, (0,), 2000)
        self.assertEqual(c_vacio.forma, "ficha")
        self.assertEqual((c_vacio.items[0][2].texto, c_vacio.items[-1][2].texto), ("t1", "t2"))
        self.assertIsNone(c_vacio.items[2][2].nodo)
        c = m.caja(texto_a_arbol("3s/(marcha AND paro)", VARS, ETAPAS), (0,), 2000)
        self.assertEqual(c.forma, "ficha")
        self.assertTrue(any(isinstance(it, _Caja) and it.forma == "y" for _, _, it in c.items), "con una expresión, encierra el bloque compuesto")
        y, o = (m.caja(texto_a_arbol(t, VARS, ETAPAS), (0,), 2000) for t in ("marcha AND paro", "marcha OR paro"))
        self.assertEqual((y.forma, o.forma, y.sin_fondo, o.sin_fondo), ("y", "o", True, True))
        self.assertEqual([it.texto for _, _, it in y.items if not isinstance(it, _Caja) and it.tipo == "txt"], ["·"])
        self.assertEqual([it.texto for _, _, it in o.items if not isinstance(it, _Caja) and it.tipo == "txt"], ["+"])
        self.assertNotEqual(COLORES["y"].lower(), COLORES["o"].lower(), "distinguibles por color")
        p = self.programador()
        textos = [b.text() for bs in p.banda.botones.values() for b in bs] + [r.text() for r in p.categorias.values()]
        self.assertFalse([t for t in textos if "TON" in t or "TOF" in t])

    def test_SP8B05_comparacion_en_ficha_y_constantes(self):
        """REQ-EDT-02: la comparación lleva corchetes `[var ▾ | op ▾ | Núm]` y marcador «Núm» si está vacía; la constante es una ficha hundida."""
        m = Motor(lambda: (VARS, ETAPAS))
        m.reiniciar()
        c = m.caja(texto_a_arbol("CT >= 10", VARS, ETAPAS), (0,), 2000)
        self.assertEqual(c.forma, "ficha")
        self.assertEqual([(it.tipo, it.texto) for _, _, it in c.items],
                         [("txt", "["), ("drop", "CT"), ("drop", "≥"), ("campo", "10"), ("txt", "]")])
        c_vacio = m.caja(nuevo("cmp", n="CT", op="=", v=""), (0,), 2000)
        self.assertEqual([(it.tipo, it.texto) for _, _, it in c_vacio.items],
                         [("txt", "["), ("drop", "CT"), ("drop", "="), ("campo", "Núm"), ("txt", "]")])
        c = m.caja(nuevo("const", v=1), (0,), 2000)
        self.assertEqual((c.forma, c.items[0][2].texto), ("hundida", "1"))

    def test_SP8B06_hueco_pendiente_se_pinta_y_se_rellena_al_soltar(self):
        """REQ-EDT-02: «NOT ?» es la ficha pendiente; una variable soltada encima la rellena y conserva el NOT; un NOT soltado sobre una
        ficha se aplica a ella (no la anida)."""
        p = self.programador()
        p.poner("NOT ?")
        a = p.lienzo
        a._calcular(a.width())
        centro = next(r for r, ruta, n in a._bloques if ruta == (0,)).center()
        self.assertEqual(a.ruta_en(centro), (0, "a"), "lo soltado sobre la ficha pendiente va al hueco de dentro")
        self.soltar(a, var("marcha", "input"), centro)
        self.assertEqual(p.texto(), "NOT marcha")
        a._calcular(a.width())
        centro = next(r for r, ruta, n in a._bloques if ruta == (0,)).center()
        self.soltar(a, nuevo("sube"), centro)
        self.assertEqual(p.texto(), "↑(NOT marcha)", "el flanco se aplica a la ficha, por fuera del NOT que ya llevaba")
        self.assertFalse(a.grab().isNull())

    # -- P5: catálogo y banda
    def test_SP8B10_banda_cada_boton_inserta_su_bloque(self):
        """REQ-EDT-02, REQ-UX-01: cada botón de la cinta `.op-ribbon`, pulsado con la fórmula vacía, inserta su bloque."""
        p = self.programador()
        esperado = {"par": "(?)", "temp": "5s/X0", "cmp": "CT >= 10", "uno": "1", "cero": "0"}
        for b in (b for bs in p.banda.botones.values() for b in bs):
            with self.subTest(b.clave):
                p.lienzo.limpiar()
                b.click()
                self.assertEqual(p.texto(), esperado[b.clave])
                self.assertTrue(b.toolTip())
        self.assertEqual(p.banda.l_prefijo.text(), "Insertar:")
        self.assertEqual([b.text() for b in p.banda.botones["operador"]], ["( … )"])
        self.assertEqual([b.text() for b in p.banda.botones["tiempo"]], ["Temporizador"])
        self.assertEqual([b.text() for b in p.banda.botones["comparacion"]], ["= ≠ < ≥"])
        self.assertEqual([b.text() for b in p.banda.botones["constante"]], ["1", "0"])

    def test_SP8B11_banda_arrastre_de_cada_boton_a_un_hueco(self):
        """REQ-EDT-02: cada botón se arrastra: lleva su bloque y, soltado sobre un hueco, lo coloca."""
        p = self.programador()
        a = p.lienzo
        for b in (b for bs in p.banda.botones.values() for b in bs):
            with self.subTest(b.clave):
                a.limpiar()
                a.soltar(None, nuevo("y"))
                with mock.patch("escritorio.banda_bloques.QDrag") as qdrag, mock.patch("escritorio.banda_bloques.ejecutar_arrastre"):
                    b._arrastrar()
                    datos = json.loads(bytes(qdrag.return_value.setMimeData.call_args.args[0].data(MIME)))
                self.assertEqual((datos["nodo"], datos["origen"]), (p.banda.nodo(b.clave), None))
                a._calcular(a.width())
                hueco = next(r for r, ruta, n in a._bloques if ruta == (0, "a") and n is None)
                self.soltar(a, datos["nodo"], hueco.center())
                self.assertIsNotNone(a.arbol["a"], b.clave)
                self.assertEqual(a.arbol["a"]["k"], p.banda.nodo(b.clave)["k"] if b.clave != "no" else "no")

    def test_SP8B12_boton_pulsado_y_movido_arrastra_en_vez_de_insertar(self):
        """REQ-EDT-02: un botón de la banda con clic inserta; con el ratón pulsado y movido, arrastra y no inserta."""
        p = self.programador()
        b = p.banda.botones["constante"][0]
        with mock.patch.object(b, "_arrastrar") as arrastrar:
            QTest.mousePress(b, Qt.MouseButton.LeftButton, pos=b.rect().center())
            QTest.mouseMove(b, b.rect().center() + QPoint(20, 20))
            QTest.mouseRelease(b, Qt.MouseButton.LeftButton, pos=b.rect().center())
        arrastrar.assert_called_once()
        self.assertEqual(p.texto(), "", "no se insertó nada")
        QTest.mouseClick(b, Qt.MouseButton.LeftButton)
        self.assertEqual(p.texto(), "1")

    def test_SP8B13_catalogo_siempre_visible_sin_pestanas_y_borde_arrastrable(self):
        """REQ-EDT-02, REQ-UX-01: el catálogo de variables y etapas no es una pestaña (está siempre a la vista, 208 px al abrirse); la cinta
        `.op-ribbon` ocupa solo la columna derecha encima del carril; el borde del catálogo se arrastra con límites y se recuerda en QSettings."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ajustes = QSettings(str(Path(tmp.name) / "a.ini"), QSettings.Format.IniFormat)
        anterior = PaletaVariables.ajustes
        PaletaVariables.ajustes = ajustes
        self.addCleanup(setattr, PaletaVariables, "ajustes", anterior)
        p = self.programador()
        self.assertTrue(p._sc_paleta.isVisible())
        self.assertEqual(p.paleta.clave, "variables")
        self.assertEqual(p._col_catalogo.width(), Programador.PALETA_INICIAL)
        self.assertEqual(Programador.PALETA_INICIAL, 208)
        self.assertFalse(any(hasattr(p, n) for n in ("elegir_categoria", "lista_categorias")), "sin pestañas")
        for q in (p, self.programador(valor=True)):
            self.assertGreaterEqual(q.banda.mapTo(q, q.banda.rect().topLeft()).x(), q._col_catalogo.width(),
                                    "la cinta va solo sobre la columna derecha")
            self.assertLess(q.banda.mapTo(q, q.banda.rect().topLeft()).y(), q.lienzo.mapTo(q, q.lienzo.rect().topLeft()).y(),
                            "la cinta queda encima del carril de bloques")
        # arrastrar el borde
        x0 = p.asa.mapToGlobal(p.asa.rect().center()).x()
        centro = p.asa.rect().center()
        QTest.mousePress(p.asa, Qt.MouseButton.LeftButton, pos=centro)
        p.asa.movida.emit(250)
        QTest.mouseRelease(p.asa, Qt.MouseButton.LeftButton, pos=centro)
        QApplication.processEvents()
        self.assertEqual(p._col_catalogo.width(), 250)
        self.assertEqual(int(ajustes.value(Programador.CLAVE_ANCHO)), 250, "se recuerda")
        p.poner_ancho_catalogo(5)
        self.assertEqual(p._col_catalogo.width(), Programador.PALETA_MIN, "con un mínimo")
        p.poner_ancho_catalogo(5000)
        self.assertLessEqual(p._col_catalogo.width(), Programador.PALETA_MAX, "con un máximo")
        p.poner_ancho_catalogo(250)
        p._recordar_ancho(250)
        otro = self.programador()
        self.assertEqual(otro._col_catalogo.width(), 250, "otro programador adopta el ancho recordado")
        self.assertIsNotNone(x0)

    def test_SP8B14_filtro_del_catalogo_con_mas_de_doce(self):
        """REQ-EDT-02: en 2.0.1 el buscador del catálogo está siempre visible en la cabecera fija superior."""
        pocas = self.programador()
        self.assertTrue(pocas.paleta.filtro_externo)
        self.assertFalse(pocas.paleta.filtro.isHidden())
        muchas = self.programador(vars_={f"I{i}": ("input", "bool") for i in range(13)})
        self.assertFalse(muchas.paleta.filtro.isHidden())
        muchas.paleta.filtro.setText("I1")
        self.assertEqual([n["n"] for n in muchas.paleta.bloques()], ["I1", "I10", "I11", "I12"])

    def test_SP8B15_banda_cabe_entera_y_pasa_de_fila(self):
        """REQ-EDT-09: la cinta fija `.op-ribbon` aloja el prefijo, los botones de inserción y las herramientas en una fila de 26 px de alto."""
        for ancho in (800, 1000, 1400):
            with self.subTest(ancho=ancho):
                p = self.programador()
                p.resize(ancho, 400)
                QApplication.processEvents()
                rotulo = p.banda.l_prefijo
                self.assertTrue(p.banda.rect().contains(rotulo.mapTo(p.banda, rotulo.rect().topLeft())), rotulo.text())
                self.assertGreaterEqual(rotulo.width(), rotulo.fontMetrics().horizontalAdvance(rotulo.text()), rotulo.text())
                for b in [b for bs in p.banda.botones.values() for b in bs] + [p.b_copiar, p.b_pegar, p.b_deshacer, p.b_rehacer, p.b_limpiar]:
                    self.assertTrue(b.isVisible())
                    caja = b.mapTo(p.banda, b.rect().topLeft())
                    self.assertTrue(p.banda.rect().contains(caja) and p.banda.rect().contains(caja + b.rect().bottomRight()), b.text())
                    self.assertGreaterEqual(b.width(), b.fontMetrics().horizontalAdvance(b.text()), b.text())
                    self.assertEqual(b.height(), 26, "alto compacto de la cinta `.op-ribbon`")
                self.assertEqual(len({b.y() for bs in p.banda.botones.values() for b in bs}), 1, "cinta en una sola fila")

    # -- P6: herramientas
    def test_SP8B20_copiar_pegar_y_limpiar(self):
        """REQ-EDT-02: «Copiar fórmula» copia la entera; «Pegar» la sustituye; «Limpiar» la vacía; Ctrl+Z deshace cada cosa."""
        p = self.programador()
        q = self.programador()
        self.assertFalse(p.b_copiar.isEnabled() or p.b_limpiar.isEnabled(), "sin fórmula, nada que copiar ni limpiar")
        QApplication.clipboard().clear()
        QApplication.processEvents()
        self.assertFalse(q.b_pegar.isEnabled(), "sin nada copiado")
        p.poner("marcha AND (paro OR 3s/M1)")
        self.assertTrue(p.b_copiar.isEnabled() and p.b_limpiar.isEnabled())
        p.b_copiar.click()
        QApplication.processEvents()
        self.assertEqual(bytes(QApplication.clipboard().mimeData().data(MIME_FORMULA)).decode(), "marcha AND (paro OR 3s/M1)")
        self.assertTrue(q.b_pegar.isEnabled(), "con una fórmula copiada")
        q.poner("Motor")
        q.b_pegar.click()
        self.assertEqual(q.texto(), "marcha AND (paro OR 3s/M1)", "Pegar sustituye la fórmula entera")
        q.deshacer()
        self.assertEqual(q.texto(), "Motor", "y se deshace")
        q.b_limpiar.click()
        self.assertEqual(q.texto(), "")
        self.assertFalse(q.b_limpiar.isEnabled())
        q.deshacer()
        self.assertEqual(q.texto(), "Motor")
        # el contenido de otro tipo no se pega con el botón: un valor no es una condición (en 2.0.1 el valor también muestra Copiar/Pegar/Limpiar)
        v = self.programador(valor=True)
        self.assertFalse(v.b_copiar.isHidden() or v.b_pegar.isHidden() or v.b_limpiar.isHidden())
        v.poner("CT + 1")
        v.b_copiar.click()
        QApplication.processEvents()
        self.assertFalse(p.b_pegar.isEnabled(), "un valor no se pega en una condición")
        v.b_limpiar.click()
        self.assertEqual(v.texto(), "")

    def test_SP8B21_ctrl_c_y_ctrl_v_conservan_su_conducta(self):
        """REQ-EDT-02: Ctrl+C copia el bloque elegido; Ctrl+V lo pega en el hueco o el bloque elegido (el botón Pegar sustituye todo)."""
        p = self.programador()
        p.poner("marcha AND paro")
        a = p.lienzo
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0, "b")))
        self.assertEqual(a._bloque_sel, (0, "b"))
        QTest.keyClick(a, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(bytes(QApplication.clipboard().mimeData().data(MIME_FORMULA)).decode(), "paro")
        p.poner("marcha AND Motor")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0, "a")))
        QTest.keyClick(a, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(p.texto(), "paro AND Motor", "Ctrl+V pega en el bloque elegido, no sustituye la fórmula")

    def test_SP8B22_clic_en_el_catalogo_inserta(self):
        """REQ-EDT-02: en 2.0.1 pulsar una ficha del catálogo la pone en el área vacía, rellena huecos pendientes si existen, o la añade
        directamente al final del carril conectada con AND sin exigir huecos `?` previos."""
        p = self.programador()
        ficha = lambda nombre: next(i for i, n in enumerate(p.paleta._raices) if n["n"] == nombre)  # noqa: E731

        def pulsar(nombre):
            p.paleta._calcular(p.paleta.width())
            caja, x, y = p.paleta._cajas[ficha(nombre)]
            QTest.mouseClick(p.paleta, Qt.MouseButton.LeftButton, pos=QPointF(x + caja.w / 2, y + caja.h / 2).toPoint())
        pulsar("marcha")
        self.assertEqual(p.texto(), "marcha", "en el área vacía, es la raíz")
        p.poner("? AND ?")
        pulsar("paro")
        self.assertEqual(p.texto(), "paro AND ?", "en el primer hueco")
        pulsar("Motor")
        self.assertEqual(p.texto(), "paro AND Motor")
        pulsar("M1")
        self.assertEqual(p.texto(), "paro AND Motor AND M1", "sin huecos libres añade directamente al carril con AND")

    def test_SP8B23_modificadores_desde_la_banda_en_el_orden_en_que_se_pulsan(self):
        """REQ-EDT-02: `aplicar_modificador("no")` sin selección deja «NOT ?»; la variable pulsada después la rellena; sobre una ficha elegida,
        los botones de la barra contextual (`barra_ctx`: NOT, ↑ y ↓) se aplican en el orden en que se pulsan y volver a pulsar los quita."""
        p = self.programador()
        a = p.lienzo
        a.aplicar_modificador("no")
        self.assertEqual(p.texto(), "NOT ?")
        p.paleta._calcular(p.paleta.width())
        caja, x, y = p.paleta._cajas[0]
        QTest.mouseClick(p.paleta, Qt.MouseButton.LeftButton, pos=QPointF(x + caja.w / 2, y + caja.h / 2).toPoint())
        self.assertEqual(p.texto(), "NOT marcha")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0,)))
        self.assertTrue(p.barra_ctx.b_not.isVisible() and p.barra_ctx.b_sube.isVisible() and p.barra_ctx.b_baja.isVisible())
        p.barra_ctx.b_sube.click()
        self.assertEqual(p.texto(), "↑(NOT marcha)", "se aplicó a la ficha elegida, en su orden: NOT y luego ↑")
        p.barra_ctx.b_not.click()
        self.assertEqual(p.texto(), "↑marcha")
        p.barra_ctx.b_not.click()
        self.assertEqual(p.texto(), "NOT ↑marcha")
        p.barra_ctx.b_baja.click()
        self.assertEqual(p.texto(), "NOT ↓marcha", "cambia el flanco en su sitio")
        p.barra_ctx.b_baja.click()
        self.assertEqual(p.texto(), "NOT marcha")
        # el orden contrario
        p.lienzo.limpiar()
        p.poner("marcha")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0,)))
        p.barra_ctx.b_sube.click()
        p.barra_ctx.b_not.click()
        self.assertEqual(p.texto(), "NOT ↑marcha")
        p.poner("marcha")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0,)))
        p.barra_ctx.b_not.click()
        p.barra_ctx.b_sube.click()
        self.assertEqual(p.texto(), "↑(NOT marcha)")

    def test_SP8B24_constantes_1_y_0_segun_la_decision_del_responsable(self):
        """REQ-EDT-02, P-IMP-69: con el lienzo vacío «1» y «0» son la fórmula entera; con huecos rellenan el hueco; sin huecos se añaden
        directamente al carril con AND; una fórmula guardada como «marcha AND 1» se abre y se escribe igual."""
        p = self.programador()
        uno = next(b for b in p.banda.botones["constante"] if b.clave == "uno")
        cero = next(b for b in p.banda.botones["constante"] if b.clave == "cero")
        uno.click()
        self.assertEqual(p.texto(), "1", "con el lienzo vacío, la fórmula entera")
        p.poner("marcha AND ?")
        uno.click()
        self.assertEqual(p.texto(), "marcha AND 1", "con un hueco pendiente, lo rellena")
        p.deshacer()
        self.assertEqual(p.texto(), "marcha AND ?")
        a = p.lienzo
        a.soltar(("b",), nuevo("const", v=0))
        self.assertEqual(p.texto(), "marcha AND 0", "soltada sobre un hueco, se combina")
        p.poner("marcha AND ?")
        a.soltar(("b",), nuevo("const", v=1))
        self.assertEqual(p.texto(), "marcha AND 1")
        p.poner("marcha AND 1")
        self.assertEqual((a.arbol["b"]["k"], p.texto()), ("const", "marcha AND 1"), "se abre y se escribe igual")
        a.limpiar()
        cero.click()
        self.assertEqual(p.texto(), "0")

    # -- P6: aviso al arrastrar fuera
    def test_SP8B30_aviso_al_arrastrar_fuera_y_el_bloque_se_quita(self):
        """REQ-EDT-02: mientras se arrastra un bloque del área, el pie avisa (ERROR_FONDO) de que soltarlo fuera lo quita y el borde se pone
        rojo si el puntero sale; al soltar, el aviso desaparece y, fuera del área, el bloque se quita."""
        p = self.programador()
        p.poner("marcha AND paro")
        a = p.lienzo
        visto = {}

        def arrastre(drag, ventana):
            visto["visible"] = p.aviso.isVisible()
            visto["texto"] = p.aviso.text()
            visto["fondo"] = estilo.ERROR_FONDO in p.aviso.styleSheet()
            a.dragLeaveEvent(mock.Mock())
            visto["fuera"] = a._fuera
        with mock.patch.object(bloques, "ejecutar_arrastre", arrastre), mock.patch.object(bloques, "QDrag"), \
                mock.patch.object(bloques.QCursor, "pos", return_value=a.mapToGlobal(a.rect().bottomRight()) + QPoint(500, 500)):
            a._arrastrar((0, "a"))
        self.assertEqual((visto["visible"], visto["fondo"], visto["fuera"]), (True, True, True))
        self.assertIn("fuera", visto["texto"])
        self.assertFalse(p.aviso.isVisible(), "al terminar el arrastre, el aviso desaparece")
        self.assertFalse(a._propio or a._fuera)
        self.assertEqual(p.texto(), "paro", "el bloque se quitó sin dejar huecos")

    # -- P7: modo valor
    def test_SP8B40_modo_valor_con_capsulas_y_banda_numerica(self):
        """REQ-EDT-02: en 2.0.1 el programador de un valor lleva el catálogo plano de variables numéricas (`catalogo`), una cinta con `( … )` y
        `+ Constante`, inserción directa con `+` y en el carril `capsula` para variables y `numconst` para números."""
        p = self.programador(valor=True)
        self.assertEqual(list(p.categorias), ["aritm", "numero"])
        self.assertEqual(p.banda.l_prefijo.text(), "Insertar:")
        self.assertEqual(p.paleta.clave, "vnum")
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["CT"])
        self.assertEqual(p.paleta._cajas[0][0].forma, "catalogo")
        self.assertEqual([b.text() for b in p.banda.botones["aritm"]], ["( … )"])
        self.assertEqual([b.text() for b in p.banda.botones["numero"]], ["+ Constante"])
        num = p.banda.botones["numero"][0]
        num.click()
        self.assertEqual(p.texto(), "1")
        p.lienzo.limpiar()
        p.paleta._calcular(p.paleta.width())
        caja, x, y = p.paleta._cajas[0]
        QTest.mouseClick(p.paleta, Qt.MouseButton.LeftButton, pos=QPointF(x + caja.w / 2, y + caja.h / 2).toPoint())
        self.assertEqual(p.texto(), "CT")
        num.click()
        self.assertEqual(p.texto(), "CT + 1", "inserción directa conectada con +")
        m = Motor(lambda: (VARS, ETAPAS))
        m.reiniciar()
        c = m.caja(texto_a_arbol_valor("CT + 1", VARS, ETAPAS), (0,), 2000)
        self.assertEqual((c.forma, c.sin_fondo), ("ar", True))
        self.assertEqual([x[2].forma if isinstance(x[2], _Caja) else x[2].tipo for x in c.items], ["capsula", "txt", "numconst"])

    def test_SP8B41_el_texto_guardado_no_cambia(self):
        """REQ-EDT-02: el texto que escribe el formulador es el de siempre (el arreglo es de aspecto): una fórmula con todas las clases de
        bloque va y vuelve igual."""
        p = self.programador()
        for t in ("↑(NOT marcha) AND paro AND 5s/(M1 OR Motor) OR CT >= 10 OR ↑Motor AND NOT M1", "(marcha) OR NOT X0", "NOT (3s/marcha)",
                  "1 AND marcha", "marcha/2s", "↓marcha AND ↑(NOT paro)"):
            with self.subTest(t):
                p.poner(t)
                self.assertEqual(p.texto(), arbol_a_texto(texto_a_arbol(t, VARS, ETAPAS)))
                self.assertFalse(p.lienzo.grab().isNull())

    def test_SP8B42_conectores_clicables_y_multiseleccion_ctrl_clic(self):
        """REQ-EDT-02: clic en «· Y» o «+ O» alterna el conector; Ctrl+clic selecciona varios bloques para aplicarles
        NOT/↑/↓, envolverlos en `( … )` o quitarlos con Supr; `Envolver ( … )` sobre un grupo le quita los paréntesis."""
        p = self.programador()
        p.poner("marcha AND paro AND Motor")
        a = p.lienzo
        a._calcular(a.width())
        self.assertEqual(len(a.motor.conectores), 2)
        # Clic en el segundo conector «· Y» -> pasa a «+ O» (marcha AND paro OR Motor)
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=a.motor.conectores[1][0].center().toPoint())
        self.assertEqual(p.texto(), "marcha AND paro OR Motor")
        a._calcular(a.width())
        # Clic en «+ O» -> vuelve a «· Y»
        con_o = next(c for c in a.motor.conectores if c[2] == "o")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=con_o[0].center().toPoint())
        self.assertEqual(p.texto(), "marcha AND paro AND Motor")
        # Multiselección con Ctrl+clic sobre el segundo y tercer operando
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0, "b")))
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, pos=self.borde(a, (0, "c")))
        self.assertEqual(a._bloques_sel, [(0, "b"), (0, "c")])
        # Aplicar NOT a varios bloques contiguos seleccionados los envuelve en ( … ) y niega el grupo (IM10-A)
        boton_no = p.barra_ctx.b_not
        boton_no.click()
        self.assertEqual(p.texto(), "marcha AND NOT (paro AND Motor)")
        self.assertEqual(a._bloque_sel, (0, "b"))
        # Volver a pulsar NOT sobre el grupo negado quita el NOT (conservando el grupo `( … )`)
        boton_no.click()
        self.assertEqual(p.texto(), "marcha AND (paro AND Motor)")
        # Pulsar «Envolver ( … )» sobre el grupo le quita los paréntesis
        p.b_envolver.click()
        self.assertEqual(p.texto(), "marcha AND paro AND Motor")
        # Shift+clic selecciona rango y Supr quita los seleccionados
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0, "b")))
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=self.borde(a, (0, "c")))
        self.assertEqual(len(a._bloques_sel), 2)
        QTest.keyClick(a, Qt.Key.Key_Delete)
        self.assertEqual(p.texto(), "marcha")
        # Modo valor: clic sobre un operador aritmético (+ -> -)
        pv = self.programador(valor=True)
        pv.poner("CT + 1")
        av = pv.lienzo
        av._calcular(av.width())
        QTest.mouseClick(av, Qt.MouseButton.LeftButton, pos=av.motor.conectores[0][0].center().toPoint())
        self.assertEqual(pv.texto(), "CT - 1")

    def test_SP8B50_ningun_boton_del_formulador_con_el_texto_recortado(self):
        """REQ-EDT-09: en la ventana de Propiedades a 1366×768 y a 1920×1080, todos los botones y rótulos del formulador (banda, herramientas
        de la franja del título, «Envolver ( … )» y «Quitar (Supr)») se ven enteros: el ancho del texto es como mucho el del botón."""
        from tools import hoja_contactos as HC
        for ancho, alto in ((1366, 768), (1920, 1080)):
            for tipo in ("transicion", "condicionada", "evento", "activacion_numerica"):
                with self.subTest(ancho=ancho, tipo=tipo):
                    c = HC.Contexto(ancho, alto)
                    try:
                        HC._flotante(tipo)(c)
                        HC._bombear(10)
                        visto = 0
                        for prog in c.w.flot.principal.findChildren(Programador):
                            if not prog.isVisible():
                                continue
                            piezas = ([prog.banda.l_prefijo] + [b for bs in prog.banda.botones.values() for b in bs]
                                      + [prog.b_copiar, prog.b_pegar, prog.b_deshacer, prog.b_rehacer, prog.b_limpiar,
                                         prog.b_envolver, prog.b_quitar])
                            for w in piezas:
                                if not w.isVisible():
                                    continue
                                visto += 1
                                texto = w.text()
                                self.assertLessEqual(w.fontMetrics().horizontalAdvance(texto), w.width(),
                                                     f"{texto!r} recortado: {w.width()} px")
                        self.assertGreaterEqual(visto, 8)
                        for prog in c.w.flot.principal.findChildren(Programador):
                            if prog.isVisible() and not prog.valor and tipo == "transicion":  # la cinta, en una sola fila
                                self.assertEqual(len({b.mapToGlobal(b.rect().topLeft()).y()
                                                      for bs in prog.banda.botones.values() for b in bs}), 1)
                    finally:
                        c.cerrar()

    def test_SP8B51_flanco_en_temporizador_rechazado_sin_mutar(self):
        """IM1 (24-nov-2026): soltar, insertar, envolver o aplicar un flanco en la base de un temporizador se rechaza con el aviso exacto."""
        p = self.programador()
        a = p.lienzo
        avisos = []
        a.avisa.connect(avisos.append)
        # 1) Aplicar ↑ sobre una variable dentro de 3s/marcha
        p.poner("3s/marcha")
        a._calcular(a.width())
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0, "a")))
        self.assertFalse(a.aplicar_modificador("sube"))
        self.assertEqual(p.texto(), "3s/marcha")
        self.assertEqual(avisos[-1], AVISO_FLANCO_TEMP)
        # 2) Soltar ↑paro dentro del hueco vacío de 3s/?
        p.poner("3s/?")
        self.assertFalse(a.soltar(("a",), nuevo("sube", a=var("paro", "input"))))
        self.assertEqual(p.texto(), "3s/?")
        self.assertEqual(avisos[-1], AVISO_FLANCO_TEMP)
        # 3) Intentar envolver un flanco seleccionado en un temporizador desde la cinta
        p.poner("↑marcha")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0,)))
        self.assertFalse(a.insertar(nuevo("temp", t1="5s", t2="")))
        self.assertEqual(p.texto(), "↑marcha")
        self.assertEqual(avisos[-1], AVISO_FLANCO_TEMP)

    def test_SP8B52_comparador_fijo_decimales_y_legado_solo_lectura(self):
        """Comparador 24-nov: entero/decimal validado con coma en pantalla, sin Fórmula izq., y complejos heredados en solo lectura."""
        vars_mix = {**VARS, "T": ("input", "decimal")}
        p = self.programador(vars_=vars_mix)
        a = p.lienzo
        self.assertFalse(hasattr(p.barra_ctx, "b_formula_cmp"))
        self.assertFalse(hasattr(a, "editar_formula_izq_cmp"))
        # Entero vs decimal con coma
        p.poner("T >= 2.5")
        c = a.motor.caja(a.arbol, (0,), 2000)
        self.assertEqual([(it.tipo, it.texto) for _, _, it in c.items],
                         [("txt", "["), ("drop", "T"), ("drop", "≥"), ("campo", "2,5"), ("txt", "]")])
        self.assertTrue(a.editar_campo((), "v", "3,75"))
        self.assertEqual(p.texto(), "T >= 3.75")
        self.assertTrue(a.editar_campo((), "v", ""))
        self.assertEqual(p.texto(), "T >= ?")
        self.assertEqual(faltan(a.arbol), 1)
        a.elegir((), "n", "CT")
        self.assertFalse(a.editar_campo((), "v", "2,5"))
        self.assertTrue(a.editar_campo((), "v", "8"))
        self.assertEqual(p.texto(), "CT >= 8")
        # Comparadores heredados complejos abren y guardan igual en solo lectura (sin drops ni campos)
        for complejo in ("(CT + 1) > 5", "CT != T"):
            with self.subTest(complejo):
                p.poner(complejo)
                box = a.motor.caja(a.arbol, (0,), 2000)
                self.assertTrue(all(it.tipo == "txt" for _, _, it in box.items))
                self.assertEqual(p.texto(), arbol_a_texto(texto_a_arbol(complejo, vars_mix, ETAPAS)))
                self.assertFalse(a.editar_campo((), "v", "99"))


if __name__ == "__main__":
    unittest.main()
