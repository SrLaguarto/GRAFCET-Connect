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


if __name__ == "__main__":
    unittest.main()
