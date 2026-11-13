"""SPVU: paleta booleana unificada, filtro y conservación del arrastre."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # (para poder ejecutarla suelta, como las demás)

try:
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

if QT:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFontMetrics

    from escritorio import bloques, estilo
    from escritorio.paleta_variables import GRUPOS, MENSAJE_VACIO


@unittest.skipUnless(QT, "requiere PySide6")
class PaletaVariables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def programador(self, variables=None, etapas=None, **opciones):
        p = bloques.Programador(lambda: (variables or {}, etapas or []), **opciones)
        self.addCleanup(p.close)
        return p

    def test_SPVU01_pestanas_y_grupos_en_orden(self):
        p = self.programador({"I10": ("input", "bool"), "I2": ("input", "bool"),
                              "M": ("internal", "bool"), "Q": ("output", "bool")}, ["X10", "X2"])
        self.assertEqual([b.text() for b in p.categorias.values()],
                         ["Variables", "Operadores", "Temporizadores", "Comparaciones", "Constantes"])
        self.assertEqual(p.paleta.clave, "variables")
        self.assertEqual([(c, t) for c, t, _, _ in p.paleta.grupos], list(GRUPOS))
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["I2", "I10", "X2", "X10", "M", "Q"])
        pixmap = p.categorias["variables"].icon().pixmap(10, 10).toImage()
        self.assertEqual(pixmap.pixelColor(5, 5).name(), estilo.TINTA_2)

    def test_SPVU02_grupos_vacios_no_tienen_titulo_ni_ficha(self):
        p = self.programador({"M": ("internal", "bool"), "CT": ("internal", "int")})
        self.assertEqual([(c, t) for c, t, _, _ in p.paleta.grupos], [("interna", "Memorias")])
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["M"])

    def test_SPVU03_mensaje_completo_a_la_anchura_minima(self):
        p = self.programador()
        p.resize(400, 170)
        p._sc_paleta.setFixedHeight(60)
        p.show()
        QApplication.processEvents()
        paleta = p.paleta
        aviso = paleta.mensaje
        self.assertEqual(p._sc_paleta.width(), p.PALETA_MIN)
        self.assertEqual(aviso.text(), MENSAJE_VACIO)
        self.assertNotIn("…", aviso.text())
        self.assertTrue(aviso.wordWrap())
        self.assertEqual(aviso.alignment(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.assertEqual((aviso.x(), aviso.y()), (estilo.E2, estilo.E2))
        self.assertIn(estilo.TINTA_2, aviso.styleSheet())
        requerido = QFontMetrics(aviso.font()).boundingRect(
            0, 0, aviso.width(), 10000, Qt.TextFlag.TextWordWrap, MENSAJE_VACIO).height()
        self.assertGreater(requerido, QFontMetrics(aviso.font()).height())
        self.assertGreaterEqual(aviso.height(), requerido)
        self.assertLessEqual(aviso.geometry().bottom() + estilo.E2, paleta.height())
        self.assertGreater(p._sc_paleta.verticalScrollBar().maximum(), 0)
        self.assertEqual(paleta.bloques(), [])
        self.assertEqual(paleta.grupos, [])

    def test_SPVU04_umbral_busqueda_acentos_y_grupos_filtrados(self):
        variables = {f"I{i}": ("input", "bool") for i in range(11)}
        variables["VÁLvula"] = ("output", "bool")
        p = self.programador(variables)
        self.assertTrue(p.paleta.filtro.isHidden())
        variables["memoria"] = ("internal", "bool")
        p.refrescar()
        self.assertFalse(p.paleta.filtro.isHidden())
        self.assertEqual(p.paleta.filtro.placeholderText(), "Filtrar…")
        p.paleta.filtro.setText("valVULA")
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["VÁLvula"])
        self.assertEqual([t for _, t, _, _ in p.paleta.grupos], ["Salidas"])
        p.seleccionar_elemento("t1")
        self.assertEqual(p.paleta.filtro.text(), "")
        p.paleta.filtro.setText("I1")
        p.seleccionar_elemento("t1")
        self.assertEqual(p.paleta.filtro.text(), "I1")
        p.seleccionar_elemento("t2")
        self.assertEqual(p.paleta.filtro.text(), "")
        variables.pop("memoria")
        p.refrescar()
        self.assertTrue(p.paleta.filtro.isHidden())

    def test_SPVU05_arrastre_preseleccionado_y_desplegables_por_papel(self):
        variables = {"I": ("input", "bool"), "M": ("internal", "bool"), "Q": ("output", "bool")}
        p = self.programador(variables, ["X2"])
        for indice, nodo in enumerate(p.paleta.bloques()):
            drag = mock.Mock()
            with mock.patch.object(bloques, "QDrag", return_value=drag):
                p.paleta._arrastrar((indice,))
            mime = drag.setMimeData.call_args.args[0]
            datos = json.loads(bytes(mime.data(bloques.MIME)))
            self.assertEqual(datos["nodo"], nodo)
            p.lienzo.poner_arbol(None)
            self.assertTrue(p.lienzo.soltar((), datos["nodo"]))
            self.assertEqual(p.lienzo.arbol, nodo)
        for papel, nombre in (("entrada", "I"), ("interna", "M"), ("salida", "Q"), ("etapa", "X2")):
            self.assertEqual(p.opciones(papel), [(nombre, nombre)])

    def test_SPVU06_programador_numerico_no_cambia(self):
        p = self.programador({"CT": ("internal", "int")}, valor=True)
        self.assertEqual(list(p.categorias), ["numero", "vnum", "aritm"])
        self.assertEqual(p.paleta.clave, "numero")
        self.assertIs(type(p.paleta), bloques.PaletaBloques)
        p.elegir_categoria("vnum")
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["CT"])

    def test_SPVU07_subtitulos_en_columna_fluido_y_una_fila(self):
        p = self.programador({"I": ("input", "bool"), "Q": ("output", "bool")}, ["X1"])
        for columna, fila in ((True, False), (False, False), (False, True)):
            p.paleta.columna = columna
            p.paleta.una_fila = fila
            p.paleta.invalidar()
            p.paleta._calcular(1000)
            for (_, _, inicio, _), (_, _, rect) in zip(p.paleta.grupos, p.paleta._titulos):
                caja, x, y = p.paleta._cajas[inicio]
                if fila:
                    self.assertGreaterEqual(x - rect.right(), estilo.E2)
                    self.assertEqual(y, rect.y())
                else:
                    self.assertEqual(x, estilo.E2)
                    self.assertGreaterEqual(y - rect.bottom(), estilo.E2)

    def test_SPVU08_refresco_y_busqueda_por_nombre_visible_de_etapa(self):
        variables = {f"I{i}": ("input", "bool") for i in range(12)}
        etapas = ["active(Inicio)"]
        p = self.programador(variables, etapas)
        p.paleta.filtro.setText("xinicio")
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["active(Inicio)"])
        etapas[:] = ["active(Final)"]
        p.refrescar()
        self.assertEqual(p.paleta.bloques(), [])
        p.paleta.filtro.setText("final")
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["active(Final)"])
        p.elegir_categoria("operador")
        p.seleccionar_elemento("otra transicion")
        self.assertEqual([n["k"] for n in p.paleta.bloques()], ["y", "o", "no", "par", "sube", "baja"])
        p.elegir_categoria("variables")
        variables.pop("I2")
        variables["Marcha"] = variables.pop("I3")
        p.refrescar()
        nombres = [n["n"] for n in p.paleta.bloques()]
        self.assertNotIn("I2", nombres)
        self.assertNotIn("I3", nombres)
        self.assertIn("Marcha", nombres)

    def test_SPVU09_aviso_completo_al_estrechar_la_paleta_horizontal(self):
        p = self.programador()
        p.resize(1000, 300)
        p.show()
        QApplication.processEvents()
        p.modo_fila(True)
        QApplication.processEvents()
        p.resize(300, 300)
        for _ in range(4):
            QApplication.processEvents()
        aviso = p.paleta.mensaje
        self.assertGreaterEqual(aviso.height(), aviso.heightForWidth(aviso.width()))
        self.assertLessEqual(aviso.geometry().bottom() + estilo.E2, p.paleta.height())
        self.assertLessEqual(p.paleta.height(), p._sc_paleta.viewport().height())


    # -- grupos plegables (encargo 18)
    def con_ajustes(self):
        """Una paleta con unos ajustes propios (en un .ini temporal); los restablece al terminar."""
        import tempfile
        from PySide6.QtCore import QSettings
        from escritorio.paleta_variables import PaletaVariables as PV
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ajustes = QSettings(str(Path(tmp.name) / "a.ini"), QSettings.Format.IniFormat)
        anterior = PV.ajustes
        PV.ajustes = ajustes
        self.addCleanup(setattr, PV, "ajustes", anterior)
        return ajustes

    VARS = {"I1": ("input", "bool"), "I2": ("input", "bool"), "M": ("internal", "bool"), "Q": ("output", "bool")}

    def titulos(self, p):
        from escritorio.paleta_variables import TituloGrupo
        return {t.papel: t for t in p.paleta.findChildren(TituloGrupo) if not t.isHidden()}

    def test_SPVU10_subtitulos_con_triangulo_y_clic_que_pliega_y_recuerda(self):
        """REQ-EDT-02: cada subtítulo es un botón con triángulo del color del papel; un clic pliega o despliega su grupo y se recuerda."""
        from escritorio.paleta_variables import CLAVE_PLEGADOS
        ajustes = self.con_ajustes()
        p = self.programador(self.VARS, ["X1"])
        p.resize(500, 300)
        p.show()
        QApplication.processEvents()
        t = self.titulos(p)
        self.assertEqual(list(t), ["entrada", "etapa", "interna", "salida"])
        self.assertFalse(any(b.plegado for b in t.values()), "por defecto, todos desplegados")
        antes = [n["n"] for n in p.paleta.bloques()]
        self.assertEqual(antes, ["I1", "I2", "X1", "M", "Q"])
        t["entrada"].click()
        QApplication.processEvents()
        self.assertTrue(t["entrada"].plegado and not t["etapa"].plegado)
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["X1", "M", "Q"])
        self.assertEqual(ajustes.value(CLAVE_PLEGADOS), "entrada")
        imagen = t["entrada"].grab().toImage()  # el triángulo, con el color del papel (▸ plegado)
        color = bloques.COLORES["entrada"].lower()
        self.assertTrue(any(imagen.pixelColor(x, y).name() == color for x in range(0, 10) for y in range(imagen.height())))
        otra = self.programador(self.VARS, ["X1"])  # otra paleta (la barra o la flotante): lo recuerda y lo comparte
        self.assertEqual([n["n"] for n in otra.paleta.bloques()], ["X1", "M", "Q"])
        t["entrada"].click()
        QApplication.processEvents()
        self.assertEqual([n["n"] for n in otra.paleta.bloques()], ["I1", "I2", "X1", "M", "Q"], "la otra paleta lo sigue")
        self.assertEqual(ajustes.value(CLAVE_PLEGADOS), "")

    def test_SPVU11_subtitulos_accesibles_con_teclado(self):
        """REQ-EDT-02: se llega al subtítulo con Tab y Espacio o Intro lo pliega o lo despliega."""
        from PySide6.QtTest import QTest
        self.con_ajustes()
        p = self.programador(self.VARS, ["X1"])
        p.resize(500, 300)
        p.show()
        QApplication.processEvents()
        t = self.titulos(p)["salida"]
        self.assertTrue(bool(t.focusPolicy() & Qt.FocusPolicy.TabFocus))
        t.setFocus(Qt.FocusReason.TabFocusReason)
        self.assertTrue(t.hasFocus())
        QTest.keyClick(t, Qt.Key.Key_Space)
        self.assertTrue(t.plegado)
        QTest.keyClick(t, Qt.Key.Key_Return)
        self.assertFalse(t.plegado)
        QTest.keyClick(t, Qt.Key.Key_Enter)
        self.assertTrue(t.plegado)
        self.assertIn("plegado", t.accessibleName())

    def test_SPVU12_con_filtro_los_grupos_con_coincidencias_se_ven_y_al_borrarlo_vuelven(self):
        """REQ-EDT-02: con el filtro escrito, los grupos con coincidencias se muestran desplegados aunque estén plegados; al borrarlo,
        vuelven a su estado."""
        self.con_ajustes()
        variables = {f"I{i}": ("input", "bool") for i in range(11)}
        variables.update({"M1": ("internal", "bool"), "Q1": ("output", "bool"), "Q2": ("output", "bool")})
        p = self.programador(variables)
        p.resize(500, 400)
        p.show()
        QApplication.processEvents()
        self.titulos(p)["entrada"].click()
        self.titulos(p)["salida"].click()
        QApplication.processEvents()
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["M1"])
        p.paleta.filtro.setText("q")
        QApplication.processEvents()
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["Q1", "Q2"], "el grupo plegado con coincidencias se ve")
        self.assertFalse(self.titulos(p)["salida"].plegado)
        p.paleta.filtro.setText("")
        QApplication.processEvents()
        self.assertEqual([n["n"] for n in p.paleta.bloques()], ["M1"], "al borrar el filtro vuelve a su estado")
        self.assertTrue(self.titulos(p)["salida"].plegado)


if __name__ == "__main__":
    unittest.main()
