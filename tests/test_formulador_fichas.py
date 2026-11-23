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
    from escritorio.bloques import (COLORES, MIME, MIME_FORMULA, AreaBloques, Motor, Programador, _Caja, arbol_a_texto, nuevo, texto_a_arbol,
                                    texto_a_arbol_valor, var)
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
        # arrastrar desde el nombre: se lleva la ficha entera con sus modificadores
        a._calcular(a.width())
        nombre = next(x for x in a._piezas if x[1] == "drop")
        self.assertEqual(a._ruta_arrastre(tuple(nombre[2])), (0,), "la ruta que se lleva es la de la ficha entera")
        mime = {}
        with mock.patch.object(bloques, "QDrag") as qdrag, mock.patch.object(bloques, "ejecutar_arrastre"):
            a._arrastrar(a._ruta_arrastre(tuple(nombre[2])))
            mime["datos"] = json.loads(bytes(qdrag.return_value.setMimeData.call_args.args[0].data(MIME)))
        self.assertEqual(arbol_a_texto(mime["datos"]["nodo"]), "NOT ↑marcha")

    def test_SP8B03_cada_origen_con_su_color_y_barra(self):
        """REQ-EDT-02, REQ-EDT-07: entrada ACENTO, salida SIMULACION, etapa EDICION y memoria ORIGEN_MEMORIA, en los colores y en la barra de 4 px
        de la ficha (se mira el píxel)."""
        self.assertEqual((COLORES["entrada"], COLORES["salida"], COLORES["etapa"], COLORES["interna"]),
                         (estilo.ACENTO, estilo.SIMULACION, estilo.EDICION, estilo.ORIGEN_MEMORIA))
        p = self.programador()
        for texto, color in (("marcha", estilo.ACENTO), ("Motor", estilo.SIMULACION), ("X0", estilo.EDICION), ("M1", estilo.ORIGEN_MEMORIA)):
            with self.subTest(texto):
                p.poner(texto)
                imagen = p.lienzo.grab().toImage()
                cerca = {imagen.pixelColor(x, y).name() for x in range(bloques.MARGEN, bloques.MARGEN + 8)
                         for y in range(bloques.MARGEN, bloques.MARGEN + 28)}
                self.assertIn(QColor(color).name(), cerca, texto)
        # el catálogo lleva las mismas fichas: la barra de la primera entrada
        self.assertEqual(p.paleta._cajas[0][0].cat, "entrada")

    def test_SP8B04_temporizador_contenedor_y_conectores_y_o(self):
        """REQ-EDT-02: el temporizador es un contenedor con su insignia (t/X, X/t, t1/X/t2; «sin retardo» avisa), con paréntesis solo si la
        base no es una variable; «y» y «o» son contenedores con un conector de su color; ninguno se llama TON ni TOF."""
        m = Motor(lambda: (VARS, ETAPAS))
        for texto, insignia in (("3s/marcha", "t/X"), ("marcha/2s", "X/t"), ("3s/marcha/2s", "t1/X/t2")):
            with self.subTest(texto):
                m.reiniciar()
                c = m.caja(texto_a_arbol(texto, VARS, ETAPAS), (0,), 2000)
                self.assertEqual(c.forma, "temp")
                self.assertEqual(c.items[0][2].texto, insignia)
                self.assertNotIn("(", [it.texto for _, _, it in c.items if not isinstance(it, _Caja)], "sin paréntesis con una variable")
        m.reiniciar()
        arbol = nuevo("temp", t1="", t2="", a=None)
        self.assertEqual(m.caja(arbol, (0,), 2000).items[0][2].texto, "sin retardo")
        c = m.caja(texto_a_arbol("3s/(marcha AND paro)", VARS, ETAPAS), (0,), 2000)
        self.assertEqual([it.texto for _, _, it in c.items if not isinstance(it, _Caja)].count("("), 1, "con una expresión, entre paréntesis")
        y, o = (m.caja(texto_a_arbol(t, VARS, ETAPAS), (0,), 2000) for t in ("marcha AND paro", "marcha OR paro"))
        self.assertEqual((y.forma, o.forma), ("y", "o"))
        self.assertEqual([it.texto for _, _, it in y.items if not isinstance(it, _Caja) and it.tipo == "txt"], ["· Y"])
        self.assertEqual([it.texto for _, _, it in o.items if not isinstance(it, _Caja) and it.tipo == "txt"], ["+ O"])
        self.assertNotEqual(COLORES["y"].lower(), COLORES["o"].lower(), "distinguibles por color")
        p = self.programador()
        textos = [b.text() for bs in p.banda.botones.values() for b in bs] + [r.text() for r in p.categorias.values()]
        self.assertFalse([t for t in textos if "TON" in t or "TOF" in t])

    def test_SP8B05_comparacion_en_ficha_y_constantes(self):
        """REQ-EDT-02: la comparación va entre corchetes, con sus tres piezas (variable, operador, valor); la constante es una ficha hundida."""
        m = Motor(lambda: (VARS, ETAPAS))
        m.reiniciar()
        c = m.caja(texto_a_arbol("CT >= 10", VARS, ETAPAS), (0,), 2000)
        self.assertEqual(c.forma, "ficha")
        self.assertEqual([(it.tipo, it.texto) for _, _, it in c.items],
                         [("txt", "["), ("drop", "CT"), ("drop", "≥"), ("campo", "10"), ("txt", "]")])
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
        """REQ-EDT-02, REQ-UX-01: cada botón de la banda, pulsado con la fórmula vacía, pone su bloque; «Y» y «O» están en Operadores."""
        p = self.programador()
        esperado = {"no": "NOT ?", "sube": "↑?", "baja": "↓?", "par": "(?)", "y": "? AND ?", "o": "? OR ?", "retardo_activar": "3s/?",
                    "retardo_desactivar": "?/3s", "cmp": "CT = 0", "uno": "1", "cero": "0"}
        for b in (b for bs in p.banda.botones.values() for b in bs):
            with self.subTest(b.clave):
                p.lienzo.limpiar()
                b.click()
                self.assertEqual(p.texto(), esperado[b.clave])
                self.assertTrue(b.toolTip())
        self.assertEqual([b.text() for b in p.banda.botones["operador"]], ["NOT", "↑", "↓", "( … )", "Y", "O"])
        self.assertEqual([b.text() for b in p.banda.botones["tiempo"]], ["t/X", "X/t"])

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
        """REQ-EDT-02, REQ-UX-01: el catálogo de variables y etapas no es una pestaña (está siempre a la vista, 170 px al abrirse); su borde
        se arrastra, con límites, y el ancho se recuerda en QSettings (y lo adopta otro programador)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ajustes = QSettings(str(Path(tmp.name) / "a.ini"), QSettings.Format.IniFormat)
        anterior = PaletaVariables.ajustes
        PaletaVariables.ajustes = ajustes
        self.addCleanup(setattr, PaletaVariables, "ajustes", anterior)
        p = self.programador()
        self.assertTrue(p._sc_paleta.isVisible())
        self.assertEqual(p.paleta.clave, "variables")
        self.assertEqual(p._sc_paleta.width(), Programador.PALETA_INICIAL)
        self.assertEqual(Programador.PALETA_INICIAL, 170)
        self.assertFalse(any(hasattr(p, n) for n in ("elegir_categoria", "lista_categorias")), "sin pestañas")
        for q in (p, self.programador(valor=True)):
            self.assertLess(q.banda.mapTo(q, q.banda.rect().topLeft()).y(), q._sc_paleta.mapTo(q, q._sc_paleta.rect().topLeft()).y(),
                            "la banda, a todo el ancho, sobre el catálogo y el área")
        # arrastrar el borde
        x0 = p.asa.mapToGlobal(p.asa.rect().center()).x()
        centro = p.asa.rect().center()
        QTest.mousePress(p.asa, Qt.MouseButton.LeftButton, pos=centro)
        p.asa.movida.emit(250)
        QTest.mouseRelease(p.asa, Qt.MouseButton.LeftButton, pos=centro)
        QApplication.processEvents()
        self.assertEqual(p._sc_paleta.width(), 250)
        self.assertEqual(int(ajustes.value(Programador.CLAVE_ANCHO)), 250, "se recuerda")
        p.poner_ancho_catalogo(5)
        self.assertEqual(p._sc_paleta.width(), Programador.PALETA_MIN, "con un mínimo")
        p.poner_ancho_catalogo(5000)
        self.assertLessEqual(p._sc_paleta.width(), Programador.PALETA_MAX, "con un máximo")
        p.poner_ancho_catalogo(250)
        p._recordar_ancho(250)
        otro = self.programador()
        self.assertEqual(otro._sc_paleta.width(), 250, "otro programador adopta el ancho recordado")
        self.assertIsNotNone(x0)

    def test_SP8B14_filtro_del_catalogo_con_mas_de_doce(self):
        """REQ-EDT-02: el catálogo ofrece el filtro con más de doce elementos y no antes."""
        pocas = self.programador()
        self.assertTrue(pocas.paleta.filtro.isHidden())
        muchas = self.programador(vars_={f"I{i}": ("input", "bool") for i in range(13)})
        self.assertFalse(muchas.paleta.filtro.isHidden())
        muchas.paleta.filtro.setText("I1")
        self.assertEqual([n["n"] for n in muchas.paleta.bloques()], ["I1", "I10", "I11", "I12"])

    def test_SP8B15_banda_cabe_entera_y_pasa_de_fila(self):
        """REQ-EDT-09: todas las categorías y sus botones caben dentro de la banda, a cualquier ancho (si no caben en una fila, pasan a otra)."""
        for ancho in (400, 700, 1000, 1400):
            with self.subTest(ancho=ancho):
                p = self.programador()
                p.resize(ancho, 400)
                QApplication.processEvents()
                for rotulo in p.categorias.values():
                    self.assertTrue(p.banda.rect().contains(rotulo.mapTo(p.banda, rotulo.rect().topLeft())), rotulo.text())
                    self.assertGreaterEqual(rotulo.width(), rotulo.fontMetrics().horizontalAdvance(rotulo.text()), rotulo.text())
                for b in (b for bs in p.banda.botones.values() for b in bs):
                    self.assertTrue(b.isVisible())
                    caja = b.mapTo(p.banda, b.rect().topLeft())
                    self.assertTrue(p.banda.rect().contains(caja) and p.banda.rect().contains(caja + b.rect().bottomRight()), b.text())
                    self.assertGreaterEqual(b.width(), b.fontMetrics().horizontalAdvance(b.text()), b.text())
                    self.assertIn(b.height(), {estilo.ALTO_CONTROL, estilo.ALTO_CONTROL_COMPACTO, estilo.ALTO_BARRA, estilo.ALTO_BARRA_COMPACTA},
                                  "el alto de un token (regla C1)")
        ancho_fila = 1400
        p = self.programador()
        p.resize(ancho_fila, 400)
        QApplication.processEvents()
        self.assertEqual(len({r.y() for r in p.categorias.values()}), 1, "a 1400 px, las cuatro categorías en una fila")

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
        # el contenido de otro tipo no se pega con el botón: un valor no es una condición (el de un valor solo tiene «Limpiar», como la maqueta)
        v = self.programador(valor=True)
        self.assertTrue(v.b_copiar.isHidden() and v.b_pegar.isHidden() and not v.b_limpiar.isHidden())
        v.poner("CT + 1")
        v.lienzo.copiar_formula()
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
        """REQ-EDT-02: pulsar una ficha del catálogo la pone en el bloque o hueco elegido y, sin elección, en el primer hueco libre; sin
        huecos libres no inserta y lo dice."""
        p = self.programador()
        a = p.lienzo
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
        avisos = []
        a.avisa.connect(avisos.append)
        pulsar("M1")
        self.assertEqual(p.texto(), "paro AND Motor", "sin huecos libres no inserta")
        self.assertTrue(avisos and "hueco" in avisos[0])
        # con un bloque elegido: lo sustituye
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0, "b")))
        pulsar("M1")
        self.assertEqual(p.texto(), "paro AND M1")

    def test_SP8B23_modificadores_desde_la_banda_en_el_orden_en_que_se_pulsan(self):
        """REQ-EDT-02: NOT sin selección deja «NOT ?»; la variable pulsada después la rellena; sobre una ficha elegida, NOT, ↑ y ↓ se aplican
        en el orden en que se pulsan (↑(NOT a) o NOT ↑a) y volver a pulsar los quita."""
        p = self.programador()
        boton = lambda clave: next(b for bs in p.banda.botones.values() for b in bs if b.clave == clave)  # noqa: E731
        boton("no").click()
        self.assertEqual(p.texto(), "NOT ?")
        p.paleta._calcular(p.paleta.width())
        caja, x, y = p.paleta._cajas[0]
        QTest.mouseClick(p.paleta, Qt.MouseButton.LeftButton, pos=QPointF(x + caja.w / 2, y + caja.h / 2).toPoint())
        self.assertEqual(p.texto(), "NOT marcha")
        boton("sube").click()
        self.assertEqual(p.texto(), "↑(NOT marcha)", "se aplicó a la ficha elegida, en su orden: NOT y luego ↑")
        boton("no").click()
        self.assertEqual(p.texto(), "↑marcha")
        boton("no").click()
        self.assertEqual(p.texto(), "NOT ↑marcha")
        boton("baja").click()
        self.assertEqual(p.texto(), "NOT ↓marcha", "cambia el flanco en su sitio")
        boton("baja").click()
        self.assertEqual(p.texto(), "NOT marcha")
        # el orden contrario
        p.lienzo.limpiar()
        p.poner("marcha")
        a = p.lienzo
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0,)))
        boton("sube").click()
        boton("no").click()
        self.assertEqual(p.texto(), "NOT ↑marcha")
        p.poner("marcha")
        QTest.mouseClick(a, Qt.MouseButton.LeftButton, pos=self.borde(a, (0,)))
        boton("no").click()
        boton("sube").click()
        self.assertEqual(p.texto(), "↑(NOT marcha)")

    def test_SP8B24_constantes_1_y_0_segun_la_decision_del_responsable(self):
        """REQ-EDT-02, P-IMP-69: con el lienzo vacío, o sin hueco elegido, «1» y «0» son la fórmula entera; sobre un hueco elegido se combinan
        como siempre; una fórmula guardada como «a AND 1» se abre y se escribe igual."""
        p = self.programador()
        uno = next(b for b in p.banda.botones["constante"] if b.clave == "uno")
        cero = next(b for b in p.banda.botones["constante"] if b.clave == "cero")
        uno.click()
        self.assertEqual(p.texto(), "1", "con el lienzo vacío, la fórmula entera")
        p.poner("marcha AND ?")
        uno.click()
        self.assertEqual(p.texto(), "1", "sin hueco elegido, sustituye la fórmula entera")
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
        self.assertEqual(p.texto(), "? AND paro", "el bloque se quitó")

    # -- P7: modo valor
    def test_SP8B40_modo_valor_con_capsulas_y_banda_numerica(self):
        """REQ-EDT-02: el programador de un valor lleva el catálogo de variables numéricas (cápsulas con el punto de su origen) y una banda con
        Operadores (+ − × ÷ y el paréntesis) y Constantes (Número); cada botón inserta su bloque."""
        p = self.programador(valor=True)
        self.assertEqual([r.text() for r in p.categorias.values()], ["Operadores", "Const."])
        self.assertEqual(p.t_catalogo.text(), "Variables numéricas")
        self.assertEqual(p.paleta.clave, "vnum")
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["CT"])
        self.assertEqual(p.paleta._cajas[0][0].forma, "capsula")
        self.assertEqual([b.text() for b in p.banda.botones["aritm"]], ["+", "−", "×", "÷", "( … )"])
        num = p.banda.botones["numero"][0]
        num.click()
        self.assertEqual(p.texto(), "1")
        p.lienzo.limpiar()
        p.banda.botones["aritm"][2].click()
        self.assertEqual(p.texto(), "? * ?")
        p.paleta._calcular(p.paleta.width())
        caja, x, y = p.paleta._cajas[0]
        QTest.mouseClick(p.paleta, Qt.MouseButton.LeftButton, pos=QPointF(x + caja.w / 2, y + caja.h / 2).toPoint())
        self.assertEqual(p.texto(), "CT * ?", "una variable numérica pulsada va al primer hueco")
        m = Motor(lambda: (VARS, ETAPAS))
        m.reiniciar()
        c = m.caja(texto_a_arbol_valor("CT + 1", VARS, ETAPAS), (0,), 2000)
        self.assertEqual([x[2].forma if isinstance(x[2], _Caja) else x[2].tipo for x in c.items], ["capsula", "txt", "capsula"])

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
                            piezas = [b for bs in prog.banda.botones.values() for b in bs] + list(prog.categorias.values())                                 + [prog.b_copiar, prog.b_pegar, prog.b_limpiar, prog.b_envolver, prog.b_quitar]
                            for w in piezas:
                                if not w.isVisible():
                                    continue
                                visto += 1
                                texto = w.text()
                                self.assertLessEqual(w.fontMetrics().horizontalAdvance(texto), w.width(),
                                                     f"{texto!r} recortado: {w.width()} px")
                        self.assertGreater(visto, 8)
                        for prog in c.w.flot.principal.findChildren(Programador):
                            if prog.isVisible() and not prog.valor and tipo == "transicion":  # la banda, en una sola fila (las categorías no se parten)
                                self.assertEqual(len({r.mapToGlobal(r.rect().topLeft()).y() for r in prog.categorias.values()}), 1)
                    finally:
                        c.cerrar()


if __name__ == "__main__":
    unittest.main()
