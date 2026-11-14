"""SH1: favoritos como paleta principal; pruebas ejecutables sin preparar PYTHONPATH."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

try:
    from PySide6.QtCore import QEvent, QPoint, QSettings, QSize, Qt
    from PySide6.QtGui import QHelpEvent
except ImportError:
    QEvent = None

if QEvent is not None:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QGuiApplication, QRegion
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtWidgets import QApplication, QToolTip
    from escritorio.ventana import Ventana
    from escritorio.favoritos import PREDETERMINADOS, icono_mini
    from escritorio.propiedades import COLOCABLES, SECCIONES, Paleta
    from escritorio.ayudas_emergentes import ANCHO_MAXIMO, texto_plano
    from escritorio.preferencias_paletas import MIGRACION, VISIBLE
    from test_editor_cadenas import BaseQt


@unittest.skipUnless(QEvent is not None, "requiere PySide6")
class FavoritosPrincipal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ventanas = []
        self.n = 0

    def tearDown(self):
        QToolTip.hideText()
        for w in self.ventanas:
            w.hide()
            w.edicion = None
            w.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.tmp.cleanup()

    def crear(self, valores=None, tam=(1366, 768), archivo=None):
        self.n += 1
        ruta = archivo or str(Path(self.tmp.name) / f"{self.n}.ini")
        ajustes = QSettings(ruta, QSettings.Format.IniFormat)
        for clave, valor in (valores or {}).items():
            ajustes.setValue(clave, valor)
        w = Ventana(ajustes)
        self.ventanas.append(w)
        w.nuevo()
        w.resize(*tam)
        w.show()
        BaseQt.pasar_arranque(self, w)
        BaseQt.asentar_escala(self, w)
        self.bombear()
        return w

    def bombear(self):
        for _ in range(5):
            self.app.processEvents()

    def test_SH101_iconos_margen_mitad_y_fila_sin_crecer(self):
        for tam in ((960, 1032), (1366, 768), (2000, 1250)):
            w = self.crear(tam=tam)
            barra = w.favoritos
            alto = barra.height()
            lado = barra.botones["etapa"].iconSize().height()
            self.assertLessEqual(abs((alto - lado) - (alto - 24) / 2), 1)
            self.assertGreater(alto - lado, 0)
            for boton in barra.botones.values():
                self.assertEqual(boton.iconSize(), QSize(lado, lado))
            cab = w._cab.geometry().height()
            for b in barra.botones.values():
                b.setIconSize(QSize(24, 24))
            w._ajustar_cabecera()
            self.bombear()
            self.assertEqual((barra.height(), w._cab.geometry().height()), (alto, cab))

    def test_SH102_todas_las_fichas_en_el_orden_solicitado(self):
        w = self.crear()
        esperado = ["etapa_inicial", "etapa", "transicion", "simultaneidad", "accion:continua",
                    "accion:condicionada", "accion:activacion", "accion:desactivacion", "accion:evento",
                    "forzado", "macroetapa", "encapsulante", "parcial", "texto", "imagen"]
        self.assertEqual(w.favoritos.orden, esperado)
        self.assertEqual(set(esperado), set(COLOCABLES))
        self.assertEqual(set(esperado), {h for _, claves in SECCIONES for h in claves})

    def test_SH103_lista_antigua_migra_una_vez_y_respeta_orden(self):
        w = self.crear({"favoritos/elementos": ["forzado", "etapa"]})
        self.assertEqual(w.favoritos.orden, ["forzado", "etapa", "texto", "imagen"])
        w.favoritos.mostrar_elemento("imagen", False)
        w.ajustes.sync()
        otra = self.crear(archivo=w.ajustes.fileName())
        self.assertEqual(otra.favoritos.orden, ["forzado", "etapa", "texto"])

    def test_SH104_defectos_y_dos_entradas_independientes_con_ctrl_l(self):
        w = self.crear()
        a = w.preferencias_paletas.accion
        self.assertEqual(w.a_izquierdo.text(), "Panel de elementos")
        self.assertEqual(w.a_izquierdo.shortcut().toString(), "Ctrl+L")
        self.assertEqual(a.text(), "Barra de favoritos")
        self.assertFalse(w.a_izquierdo.isChecked())
        self.assertTrue(a.isChecked())
        self.assertFalse(w.dock.isVisible())
        self.assertTrue(w.favoritos.isVisible())
        for panel, barra in ((True, True), (True, False), (False, False), (False, True)):
            w.a_izquierdo.setChecked(panel)
            a.setChecked(barra)
            self.bombear()
            self.assertEqual((w.dock.isVisible(), w.favoritos.isVisible()), (panel, barra))
        w.activateWindow()
        w.diagrama.setFocus()
        QTest.keyClick(w, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
        self.bombear()
        self.assertTrue(w.dock.isVisible())

    def test_SH105_recuerdo_de_las_dos_elecciones(self):
        w = self.crear()
        w.a_izquierdo.setChecked(True)
        w.preferencias_paletas.accion.setChecked(False)
        w.ajustes.sync()
        otra = self.crear(archivo=w.ajustes.fileName())
        self.assertTrue(otra.a_izquierdo.isChecked())
        self.assertFalse(otra.preferencias_paletas.accion.isChecked())
        self.assertTrue(otra.dock.isVisible())
        self.assertFalse(otra.favoritos.isVisible())

    def test_SH106_panel_antiguo_visible_o_plegado_recibe_nuevo_defecto_una_vez(self):
        for antiguo in (False, True):
            w = self.crear({"paneles/izquierdo": antiguo})
            self.assertTrue(w.ajustes.value(MIGRACION, type=bool))
            self.assertFalse(w.a_izquierdo.isChecked())
            w.a_izquierdo.setChecked(True)
            w.ajustes.sync()
            otra = self.crear(archivo=w.ajustes.fileName())
            self.assertTrue(otra.a_izquierdo.isChecked())

    def test_SH107_oculta_en_simulacion_y_solo_lectura_sin_perder_preferencia(self):
        w = self.crear()
        w.edicion.ed.add_step("g", "0", True)
        w.edicion.cambia()
        self.assertTrue(w.cambiar_modo("simular"))
        self.bombear()
        self.assertFalse(w.favoritos.isVisible())
        w.cambiar_modo("editar")
        self.bombear()
        self.assertTrue(w.favoritos.isVisible())
        w.solo_lectura = True
        w._poner_modo()
        w._ajustar_cabecera()
        self.assertFalse(w.favoritos.isVisible())
        self.assertTrue(w.preferencias_paletas.accion.isChecked())

    def test_SH108_ayudas_completas_de_paleta_y_favoritos(self):
        w = self.crear()
        for clave in COLOCABLES:
            item = next(w.paleta.item(i) for i in range(w.paleta.count())
                        if w.paleta.item(i).data(Qt.ItemDataRole.UserRole) == clave)
            for texto in (item.toolTip(), w.favoritos.botones[clave].toolTip()):
                self.assertIn("<b>", texto)
                self.assertIn(Paleta.nombre(clave), texto_plano(texto))
                self.assertIn(Paleta.texto_ayuda(clave), texto_plano(texto))

    def test_SH109_ninguna_ayuda_supera_maximo_o_limites_de_pantalla(self):
        w = self.crear(tam=(960, 1032))
        pantalla = w.screen().availableGeometry()
        punto = pantalla.bottomRight() - QPoint(5, 5)
        for clave in COLOCABLES:
            item = next(w.paleta.item(i) for i in range(w.paleta.count())
                        if w.paleta.item(i).data(Qt.ItemDataRole.UserRole) == clave)
            for texto in (item.toolTip(), w.favoritos.botones[clave].toolTip()):
                QToolTip.showText(punto, texto, w.favoritos)
                QTest.qWait(15)
                tips = [t for t in self.app.topLevelWidgets()
                        if t.windowType() == Qt.WindowType.ToolTip and t.isVisible()]
                self.assertEqual(len(tips), 1)
                rect = tips[0].frameGeometry()
                self.assertLessEqual(rect.width(), ANCHO_MAXIMO)
                self.assertTrue(pantalla.contains(rect), (clave, rect, pantalla))
                self.assertIn(Paleta.texto_ayuda(clave), texto_plano(QToolTip.text()))

    def test_SH110_ayuda_por_clic_aunque_el_panel_este_oculto(self):
        w = self.crear()
        aviso = QSignalSpy(w.paleta.ayuda)
        QTest.mouseClick(w.favoritos.botones["etapa"], Qt.MouseButton.LeftButton)
        self.assertEqual(aviso.count(), 1)
        self.assertIn(Paleta.texto_ayuda("etapa"), w.ayuda.text())
        self.assertFalse(w.dock.isVisible())

    def test_SH111_gana_ancho_y_no_cambia_el_documento(self):
        w = self.crear()
        antes = copy.deepcopy(w.edicion.ed.model)
        ancho = w.diagrama.width()
        w.a_izquierdo.setChecked(True)
        self.bombear()
        self.assertLess(w.diagrama.width(), ancho)
        w.a_izquierdo.setChecked(False)
        self.bombear()
        self.assertEqual(w.diagrama.width(), ancho)
        self.assertEqual(w.edicion.ed.model, antes)

    def test_SH112_tab_y_desborde_sin_panel_lateral(self):
        w = self.crear(tam=(683, 384))
        self.assertFalse(w.dock.isVisible())
        self.assertTrue(w.favoritos.ocultos)
        self.assertEqual(set(w.favoritos._visibles + w.favoritos.ocultos), set(COLOCABLES))
        foco = w.preferencias_paletas.foco()
        self.assertNotIn(w.paleta, foco)
        self.assertIn(w.favoritos.desborde, foco)
        w._orden_tab()
        foco[0].setFocus()
        QTest.keyClick(foco[0], Qt.Key.Key_Tab)
        self.assertIs(self.app.focusWidget(), foco[1])

    def test_SH113_render_nativo_de_la_caja_nueva_en_tres_dpr(self):
        w = self.crear()
        lado = w.favoritos.lado_icono
        for clave in COLOCABLES:
            for dpr in (1., 1.25, 1.5):
                pix = icono_mini(clave).pixmap(QSize(lado, lado), dpr)
                self.assertEqual(pix.size(), QSize(round(lado * dpr), round(lado * dpr)))
                self.assertEqual(pix.devicePixelRatioF(), dpr)
                self.assertTrue(pix.rect().adjusted(1, 1, -1, -1).contains(QRegion(pix.mask()).boundingRect()))

    def test_SH115_trazo_proporcional_y_comun_en_la_caja_ampliada(self):
        from PySide6.QtGui import QPainter, QPixmap
        from escritorio import favoritos
        w = self.crear()
        lado = w.favoritos.lado_icono
        trazos = []
        def medir(pintor, clave):
            trazos.append(pintor.pen().widthF() * pintor.worldTransform().m11())
        pix = QPixmap(lado, lado)
        pintor = QPainter(pix)
        try:
            with mock.patch.object(favoritos, "_pintar_accion_mini", side_effect=medir), \
                    mock.patch.object(favoritos, "_pintar_etapa_mini", side_effect=medir), \
                    mock.patch.object(favoritos, "_pintar_otros_mini", side_effect=medir):
                for clave in COLOCABLES:
                    favoritos.icono_mini(clave).paint(pintor, 0, 0, lado, lado)
        finally:
            pintor.end()
        self.assertEqual(len(trazos), len(COLOCABLES))
        for trazo in trazos:
            self.assertAlmostEqual(trazo, 1.5 * lado / 24)

    def test_SH116_listas_antiguas_vacias_unitarias_y_ya_completas(self):
        for antigua, esperada in (([], ["texto", "imagen"]),
                                  ("etapa", ["etapa", "texto", "imagen"]),
                                  (["imagen", "forzado", "texto"], ["imagen", "forzado", "texto"])):
            w = self.crear({"favoritos/elementos": antigua})
            self.assertEqual(w.favoritos.orden, esperada)

    def test_SH117_ayuda_de_celda_tambien_se_ajusta(self):
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
        w = self.crear(tam=(960, 1032))
        tabla = QTableWidget(1, 1, w)
        tabla.resize(200, 100)
        item = QTableWidgetItem("Dato")
        largo = "Descripción larga de un dato de la ventana. " * 15
        item.setToolTip(largo)
        tabla.setItem(0, 0, item)
        tabla.setHorizontalHeaderLabels(["Columna"])
        tabla.show()
        punto = tabla.visualItemRect(item).center()
        global_ = w.screen().availableGeometry().bottomRight() - QPoint(5, 5)
        self.app.sendEvent(tabla.viewport(), QHelpEvent(QEvent.Type.ToolTip, punto, global_))
        QTest.qWait(15)
        tips = [t for t in self.app.topLevelWidgets()
                if t.windowType() == Qt.WindowType.ToolTip and t.isVisible()]
        self.assertEqual(len(tips), 1)
        self.assertLessEqual(tips[0].width(), ANCHO_MAXIMO)
        self.assertEqual(texto_plano(QToolTip.text()).strip(), largo.strip())
        tabla.horizontalHeaderItem(0).setToolTip(largo)
        cabecera = tabla.horizontalHeader()
        self.app.sendEvent(cabecera.viewport(), QHelpEvent(QEvent.Type.ToolTip, QPoint(3, 3), global_))
        QTest.qWait(15)
        self.assertLessEqual(tips[0].width(), ANCHO_MAXIMO)
        self.assertEqual(texto_plano(QToolTip.text()).strip(), largo.strip())

    def test_SH118_identificador_largo_sin_espacios_no_desborda(self):
        w = self.crear(tam=(960, 1032))
        largo = "Identificador" * 30
        w.b_ayuda.setToolTip(largo)
        punto = w.screen().availableGeometry().bottomRight() - QPoint(5, 5)
        self.app.sendEvent(w.b_ayuda, QHelpEvent(QEvent.Type.ToolTip, QPoint(2, 2), punto))
        QTest.qWait(15)
        tips = [t for t in self.app.topLevelWidgets()
                if t.windowType() == Qt.WindowType.ToolTip and t.isVisible()]
        self.assertEqual(len(tips), 1)
        self.assertLessEqual(tips[0].width(), ANCHO_MAXIMO)
        self.assertTrue(w.screen().availableGeometry().contains(tips[0].frameGeometry()))
        self.assertEqual(texto_plano(QToolTip.text()).strip().replace("\u200b", ""), largo)

    def comprobar_ayuda_directa(self, w, largo):
        QTest.qWait(15)
        tips = [t for t in self.app.topLevelWidgets()
                if t.windowType() == Qt.WindowType.ToolTip and t.isVisible()]
        self.assertEqual(len(tips), 1)
        self.assertLessEqual(tips[0].width(), ANCHO_MAXIMO)
        self.assertTrue(w.screen().availableGeometry().contains(tips[0].frameGeometry()))
        self.assertEqual(texto_plano(QToolTip.text()).strip().replace("\u200b", ""), largo)

    def test_SH119_ayuda_directa_de_bloque_recortado_se_ajusta(self):
        from escritorio.bloques import PaletaBloques
        w = self.crear(tam=(960, 1032))
        largo = "IDENTIFICADOR_MUY_LARGO_" * 12
        paleta = PaletaBloques(lambda: ({largo: ("input", "bool")}, []), columna=True)
        paleta.setParent(w)
        paleta.resize(90, 60)
        paleta._calcular(90)
        rect, completo = paleta.motor.recortadas[0]
        self.assertEqual(completo, largo)
        punto = w.screen().availableGeometry().bottomRight() - QPoint(5, 5)
        self.app.sendEvent(paleta, QHelpEvent(QEvent.Type.ToolTip, rect.center().toPoint(), punto))
        self.comprobar_ayuda_directa(w, largo)

    def test_SH120_ayuda_directa_del_selector_recortado_se_ajusta(self):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QListWidget, QStyleOptionViewItem
        from escritorio.diagrama import _OpcionConPapel
        w = self.crear(tam=(960, 1032))
        largo = "VARIABLE_MUY_LARGA_" * 12
        vista = QListWidget(w)
        vista.addItem(largo + "  (S)")
        vista.item(0).setData(Qt.ItemDataRole.UserRole + 1, "S")
        opcion = QStyleOptionViewItem()
        opcion.rect = QRect(0, 0, 90, 30)
        opcion.fontMetrics = vista.fontMetrics()
        punto = w.screen().availableGeometry().bottomRight() - QPoint(5, 5)
        evento = QHelpEvent(QEvent.Type.ToolTip, QPoint(5, 5), punto)
        delegado = _OpcionConPapel(vista)
        self.assertTrue(delegado.helpEvent(evento, vista, opcion, vista.model().index(0, 0)))
        self.comprobar_ayuda_directa(w, largo)

    def test_SH114_otras_ayudas_largas_se_ajustan(self):
        w = self.crear(tam=(960, 1032))
        w.b_ayuda.setToolTip("Una descripción extensa de la ventana. " * 15)
        p = w.screen().availableGeometry().bottomRight() - QPoint(5, 5)
        self.app.sendEvent(w.b_ayuda, QHelpEvent(QEvent.Type.ToolTip, QPoint(2, 2), p))
        QTest.qWait(15)
        tips = [t for t in self.app.topLevelWidgets()
                if t.windowType() == Qt.WindowType.ToolTip and t.isVisible()]
        self.assertEqual(len(tips), 1)
        self.assertLessEqual(tips[0].width(), ANCHO_MAXIMO)
        self.assertTrue(w.screen().availableGeometry().contains(tips[0].frameGeometry()))


if __name__ == "__main__":
    unittest.main()
