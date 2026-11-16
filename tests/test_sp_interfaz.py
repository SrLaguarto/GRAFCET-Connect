"""SP1: tamaños, filtro editable y supresión de bloques, sin servicios externos."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")
try:
    from PySide6.QtCore import QEvent, QObject, QPoint, QSignalBlocker, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QFormLayout, QSpinBox, QWidget
    from conexion.configuracion import Configuracion
    from escritorio import estilo
    from escritorio.bloques import Programador, var
    from escritorio.campos_medidos import ajustar, ancho_numero
    from escritorio.entradas_salidas import PanelES
    from escritorio.filtro_senales import ConfiguracionDirecta
    from grafcet.builder import M
    from test_sp_filtro_directo import identidad
    from servidor_directo_falso import senal
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requiere PySide6")
class InterfazP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def panel(self, directo=False):
        p = PanelES()
        doc = M().var("marcha").var("motor", "output").step("0", True).doc
        config = Configuracion(modo="directo", host="localhost", puerto=7410) if directo else None
        p.cargar(doc, config)
        p.resize(1100, 650)
        p.show()
        self.app.processEvents()
        self.addCleanup(p.deleteLater)
        self.addCleanup(p.close)
        return p

    def test_SP109_numeros_no_se_estiran_y_sufijos(self):
        w = QWidget()
        w.setStyleSheet(estilo.hoja_global())
        form = QFormLayout(w)
        for clase in (QSpinBox, QDoubleSpinBox):
            spin = clase()
            spin.setRange(-10000, 10000)
            spin.setSuffix(" ms")
            form.addRow("Tiempo", spin)
        w.show()
        self.addCleanup(w.close)
        self.app.processEvents()
        for spin in w.findChildren(QSpinBox) + w.findChildren(QDoubleSpinBox):
            self.assertEqual(spin.width(), ancho_numero(spin))
            previo = spin.width()
            w.resize(1200, 500)
            self.app.processEvents()
            self.assertEqual(spin.width(), previo)

    def test_SP110_selector_centrado_misma_medida_ambos_modos(self):
        p = self.panel()
        selector = p.directa.selector
        ancho = selector.width()
        self.assertLess(ancho, selector.parentWidget().width())
        self.assertLessEqual(abs(selector.geometry().center().x() - selector.parentWidget().rect().center().x()), 2)
        selector.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(selector.width(), ancho)
        self.assertEqual(selector.height(), estilo.ESCALAS[p.escala]["ALTO_CONTROL"])

    def test_SP111_restablecer_mide_su_texto(self):
        p = self.panel()
        p.dialogo_config.show()
        self.addCleanup(p.dialogo_config.hide)
        self.app.processEvents()
        b = p.b_restaurar_canales
        self.assertLessEqual(b.width(), b.sizeHint().width() + 2)

    def test_SP112_dialogo_filtro_sin_servidor_y_aceptar_cancelar(self):
        p = self.panel(True)
        p.directa.catalogo = [senal(identidad(1), "Simulador I/O (Run)", direccion=496),
                             senal(identidad(2), "Sensor", direccion=0)]
        d = ConfiguracionDirecta(p.directa)
        self.addCleanup(d.close)
        self.assertEqual(set(d.controles), {"periodo_ms", "timeout_ms"})
        self.assertFalse(d.recordar.isChecked())
        self.assertEqual(d.tabla.rowCount(), 1)
        d.tabla.cellWidget(0, 0).setChecked(False)
        self.assertFalse(d.config.filtro_senales[0]["excluir"])
        self.assertEqual(p.config.filtro_senales, [])
        d.recordar.setChecked(True)
        d.identidad.setCurrentIndex(2)
        d.anadir()
        self.assertEqual(d.tabla.rowCount(), 2)
        d.anadir()
        self.assertIn("ya está", d.aviso.text())
        d.tabla.selectRow(0)
        d.quitar()
        self.assertEqual(d.tabla.rowCount(), 1)
        self.assertTrue(d.config.filtro_senales[0]["quitada"])

    def test_SP113_ausentes_se_conservan_grises_y_se_pueden_quitar(self):
        p = self.panel(True)
        p.config.recordar_filtro = True
        p.config.filtro_senales = [dict(id=identidad(9), excluir=False, nombre="Antigua", tipo="Bit")]
        d = ConfiguracionDirecta(p.directa)
        self.addCleanup(d.close)
        self.assertIn("no está en la escena abierta", d.tabla.item(0, 2).text())
        self.assertEqual(d.tabla.item(0, 2).foreground().color().name(), estilo.TINTA_3)
        d.quitar_ausentes()
        self.assertEqual(d.config.filtro_senales, [])

    def test_SP114_bloques_sin_papelera_supr_y_retroceso(self):
        for tecla in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            p = Programador(lambda: ({"marcha": ("input", "bool")}, []))
            self.addCleanup(p.close)
            self.assertFalse(any(type(w).__name__ == "Papelera" for w in p.findChildren(QWidget)))
            p.poner("marcha")
            p.lienzo._bloque_sel = (0,)
            QTest.keyClick(p.lienzo, tecla)
            self.assertEqual(p.texto(), "")
            self.assertIn("arrástrelo fuera", p.lienzo.toolTip())

    def test_SP115_arrastrar_fuera_quita_el_bloque(self):
        from escritorio import bloques
        p = Programador(lambda: ({"marcha": ("input", "bool")}, []))
        self.addCleanup(p.close)
        p.poner("marcha")
        a = p.lienzo
        fuera = a.mapToGlobal(QPoint(a.width() + 50, a.height() + 50))
        with patch.object(bloques, "QDrag", return_value=MagicMock()), \
                patch.object(bloques.QCursor, "pos", return_value=fuera):
            a._arrastrar((0,))
        self.assertEqual(p.texto(), "")

    def test_SP116_unida_excluida_sigue_en_modulo_y_traer(self):
        from conexion.uniones import Union
        from escritorio.edicion import Edicion
        from escritorio.traer_modelo import Propuestas
        from grafcet.editor import Editor
        p = self.panel(True)
        variable = next(v for v in p.doc["variables"] if v["name"] == "marcha")
        p.config.uniones = [Union(variable["id"], identidad(1), "Interna", "Bit", "input")]
        p.config.filtro_senales = [dict(id=identidad(1), excluir=True), dict(id=identidad(2), excluir=True)]
        p.directa.catalogo = [senal(identidad(1), "Interna"), senal(identidad(2), "Otra")]
        p.directa.dibujar()
        self.assertIn(identidad(1), p.directa.dibujo.terminales)
        self.assertNotIn(identidad(2), p.directa.dibujo.terminales)
        e = Edicion(Editor(p.doc), "Prueba")
        propuestas = Propuestas(e, p.config, p.directa.catalogo)
        self.assertEqual(len(propuestas.filas), 1)
        self.assertEqual(propuestas.filas[0].ya, "marcha")

    def test_SP117_popup_estable_con_27_variables_en_ambos_paneles(self):
        from tools import hoja_contactos as hc

        class Registro(QObject):
            def __init__(self, popup):
                super().__init__()
                self.eventos = []
                popup.installEventFilter(self)

            def eventFilter(self, objeto, evento):
                if evento.type() in (QEvent.Type.Show, QEvent.Type.Resize, QEvent.Type.Move):
                    self.eventos.append(evento.type())
                return False

        for tipo in ("condicionada", "evento"):
            for flotante in (True, False):
                with self.subTest(tipo=tipo, flotante=flotante):
                    c = hc.Contexto(1366, 768)
                    try:
                        hc._flotante(tipo)(c)
                        with QSignalBlocker(c.e):
                            for n in range(27):
                                c.e.nueva_variable(f"salida_con_nombre_muy_largo_{n:02d}", "output")
                        c.e.cambiado.emit()
                        if not flotante:
                            c.w._cambiar_modo_propiedades("abajo")
                            c.w._abrir_opciones()
                        hc._bombear(12)
                        p = c.w.flot.panel if flotante else c.w.props
                        marco = c.w.flot.principal if flotante else p
                        combo = p.accion.variable
                        antes = (marco.geometry(), p.geometry())
                        registro = Registro(combo.view().window())
                        combo.showPopup()
                        hc._bombear(8)
                        self.assertEqual((marco.geometry(), p.geometry()), antes)
                        inicio = registro.eventos.index(QEvent.Type.Show)
                        self.assertEqual(registro.eventos[inicio + 1:], [])
                        combo.hidePopup()
                    finally:
                        c.cerrar()

    def test_SP118_transicion_a_media_pantalla_y_categorias_a_1366(self):
        from tools import hoja_contactos as hc
        for ancho, alto in ((1366, 768), (683, 768), (960, 1080)):
            c = hc.Contexto(ancho, alto)
            try:
                hc._flotante("transicion")(c)
                p = c.w.flot.panel
                casilla = p.t_mostrar
                self.assertGreaterEqual(casilla.width(), casilla.fontMetrics().horizontalAdvance(casilla.text()) + 22)
                if ancho == 1366:
                    ys = {b.mapTo(p.prog, QPoint()).y() for b in p.prog.categorias.values()}
                    self.assertEqual(len(ys), 1)
            finally:
                c.cerrar()

    def test_SP129_dialogo_filtro_cumple_medidas_en_ambas_escalas(self):
        from tools import hoja_contactos as hc
        from test_auditoria_maquetacion import REGLAS
        for ancho, alto in ((1366, 768), (2000, 1250), (683, 768), (960, 1080)):
            with self.subTest(ancho=ancho):
                c = hc.Contexto(ancho, alto)
                try:
                    c.mostrar()
                    c.w.mostrar_es()
                    p = c.w.panel_es
                    p.directa.catalogo = [senal(identidad(1), "Simulador I/O (Run)", direccion=496),
                                         senal(identidad(2), "Sensor")]
                    d = ConfiguracionDirecta(p.directa)
                    c.extras.append(d)
                    d.b_avanzado.setChecked(True)
                    d.show()
                    hc._bombear(4)
                    for regla in ("M1", "M2", "C1", "C2", "C5", "TB1", "TB2"):
                        self.assertEqual(REGLAS[regla](d), [], regla)
                finally:
                    c.cerrar()

    def test_SP131_numericas_alineadas_tras_booleanas_desiguales(self):
        p = self.panel(True)
        p.directa.catalogo = [senal(identidad(1), "Número entrada", tipo="Float"),
                             senal(identidad(2), "Sensor"),
                             senal(identidad(3), "Número salida", tipo="Int", papel="Output")]
        p.directa.catalogo += [senal(identidad(10 + i), f"Motor {i}", papel="Output") for i in range(4)]
        for _ in range(2):
            p.directa.dibujar()
            self.app.processEvents()
            marco = p.directa.dibujo
            entrada = marco.terminales[identidad(1)].mapTo(marco, QPoint()).y()
            salida = marco.terminales[identidad(3)].mapTo(marco, QPoint()).y()
            self.assertEqual(entrada, salida)
            sensor = marco.terminales[identidad(2)].mapTo(marco, QPoint()).y()
            self.assertEqual(entrada - sensor, 4 * p.alto_fila)
            for i in range(4):
                motor = marco.terminales[identidad(10 + i)]
                self.assertLess(motor.mapTo(marco, QPoint()).y(), entrada)


if __name__ == "__main__":
    unittest.main()
