"""SJ1: ayuda de pantalla, paneles, barra fija y edición explícita de plantillas."""
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

try:
    from PySide6.QtCore import QPoint, QSize, Qt
    from PySide6.QtGui import QContextMenuEvent, QRegion
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QToolButton
    QT = True
except ImportError:
    QT = False

if QT:
    import test_favoritos_principal as soporte
    from escritorio import estilo
    from escritorio.favoritos import PREDETERMINADOS


@unittest.skipUnless(QT, "requiere PySide6")
class InterfazJ(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        soporte.FavoritosPrincipal.setUpClass()

    def setUp(self):
        self.base = soporte.FavoritosPrincipal()
        self.base.setUp()

    def tearDown(self):
        self.base.tearDown()

    def crear(self, *args, **kwargs):
        return self.base.crear(*args, **kwargs)

    def bombear(self):
        self.base.bombear()

    def plantilla(self, tam=(1366, 768)):
        from tools.hoja_contactos import grafcet_de_ejemplo
        from grafcet.laminas import ajustes_lamina
        from escritorio.carpetas import predeterminada
        w = self.crear(tam=tam)
        grafcet_de_ejemplo(w.edicion)
        cfg = ajustes_lamina({"plantilla": predeterminada()})
        ident = w.edicion.ed.add_plan_page(None, cfg)
        w.edicion.cambia()
        w.mostrar_hoja(ident)
        self.bombear()
        d = w.panel_planos.editor
        cambios = []
        guardar_original = d.aplicar_callback
        def guardar(valores):
            cambios.append(valores)
            guardar_original(valores)
        d.aplicar_callback = guardar
        return w, d, cambios

    def test_SJ101_menu_primero_f1_y_escape_sin_boton(self):
        """REQ-EDT-09: ayuda contextual completa desde menú/F1, sin reservar cabecera."""
        w = self.crear()
        self.assertIsNone(w.findChild(QToolButton, "masAyuda"))
        menu = next(a.menu() for a in w.menuBar().actions() if a.text().replace("&", "") == "Ayuda")
        self.assertIs(menu.actions()[0], w.a_ayuda_pantalla)
        self.assertEqual(w.a_ayuda_pantalla.shortcut().toString(), "F1")
        from PySide6.QtCore import QPointF
        sid = w.edicion.poner_etapa(QPointF(200, 200))
        w.edicion.seleccionar([sid])
        w.activateWindow()
        w.diagrama.setFocus()
        QTest.keyClick(w, Qt.Key.Key_F1)
        self.bombear()
        self.assertTrue(w.ayuda_larga.isVisible())
        self.assertTrue(w.a_ayuda_pantalla.isChecked())
        self.assertEqual(w.ayuda_larga.text(), w.ayuda.text())
        QTest.keyClick(w.ayuda_larga, Qt.Key.Key_Escape)
        self.bombear()
        self.assertFalse(w.ayuda_larga.isVisible())
        self.assertFalse(w.a_ayuda_pantalla.isChecked())

    def test_SJ102_ayuda_por_modo_y_herramienta(self):
        """REQ-EDT-09, REQ-SIM-03: el menú conserva el texto contextual del modo actual."""
        from tools.hoja_contactos import grafcet_de_ejemplo
        w = self.crear()
        grafcet_de_ejemplo(w.edicion)
        for modo in ("editar", "simular", "editar"):
            w.cambiar_modo(modo)
            self.bombear()
            if w.a_ayuda_pantalla.isChecked():
                w.a_ayuda_pantalla.trigger()
            w.a_ayuda_pantalla.trigger()
            self.assertEqual(w.ayuda_larga.text(), w.ayuda.text())
            w.a_ayuda_pantalla.trigger()
            self.assertFalse(w.ayuda_larga.isVisible())

    def test_SJ103_cabecera_sin_solapes_en_cuatro_anchos(self):
        """REQ-UX-01: favoritos y zoom usan el hueco liberado incluso a media pantalla."""
        for tam in ((960, 1032), (1366, 768), (2000, 1250), (683, 384)):
            w = self.crear(tam=tam)
            widgets = [w._cab.itemAt(i).widget() for i in range(w._cab.count())]
            visibles = [x for x in widgets if x is not None and x.isVisible()]
            for i, primero in enumerate(visibles):
                for segundo in visibles[i + 1:]:
                    self.assertFalse(primero.geometry().intersects(segundo.geometry()), tam)
            self.assertEqual(w.favoritos._visibles + w.favoritos.ocultos, list(PREDETERMINADOS))

    def test_SJ104_plegar_conserva_pestana_y_libera_espacio(self):
        w = self.crear(tam=(2000, 1250))
        w._mostrar_panel("derecho", True)
        self.bombear()
        abierto = w.diagrama.width()
        w.flechas["derecho"].click()
        self.bombear()
        self.assertTrue(w.pestanas["derecho"].isVisible())
        self.assertGreater(w.diagrama.width(), abierto)
        w.pestanas["derecho"].click()
        self.bombear()
        self.assertTrue(w.derecho.isVisible())

    def test_SJ105_ctrl_b_alterna_plegado_sin_ocultar_panel(self):
        w = self.crear(tam=(2000, 1250))
        w._mostrar_panel("derecho", True)
        w.activateWindow()
        w.diagrama.setFocus()
        for abierto in (False, True):
            QTest.keyClick(w, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
            self.bombear()
            self.assertEqual(w.derecho.isVisible(), abierto)
            self.assertEqual(w.pestanas["derecho"].isVisible(), not abierto)
            self.assertTrue(w._plegables["derecho"].isVisible())

    def test_SJ106_barra_fija_borra_lista_antigua(self):
        """REQ-EDT-09: una lista antigua no oculta fichas ni altera su orden fijo."""
        for antigua in (["texto", "etapa"], [], "forzado"):
            w = self.crear({"favoritos/elementos": antigua})
            self.assertEqual(w.favoritos.orden, list(PREDETERMINADOS))
            self.assertFalse(w.ajustes.contains("favoritos/elementos"))
            self.assertFalse(w.favoritos.acceptDrops())
            evento = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(3, 3))
            QApplication.sendEvent(w.favoritos, evento)
            self.assertIsNone(w.favoritos._menu)

    def test_SJ107_dependencias_completo_y_uniones_en_tres_dpr(self):
        """REQ-UX-01: el símbolo completo deja margen y conserva las dos uniones finas."""
        w = self.crear()
        for dpr in (1., 1.25, 1.5):
            pix = estilo.icono("dependencias").pixmap(QSize(24, 24), dpr)
            caja = QRegion(pix.mask()).boundingRect()
            self.assertTrue(pix.rect().adjusted(1, 1, -1, -1).contains(caja), (dpr, caja))
            imagen = pix.toImage()
            for izquierda, arriba, derecha, abajo in ((9, 4, 15, 10), (9, 14, 15, 21)):
                tinta = sum(imagen.pixelColor(x, y).alpha() > 30
                            for x in range(round(izquierda * dpr), round(derecha * dpr))
                            for y in range(round(arriba * dpr), round(abajo * dpr)))
                self.assertGreater(tinta, 2, dpr)

    def test_SJ108_plantilla_ancho_completo_y_lista_legible(self):
        """REQ-UX-01: las plantillas actuales caben y el popup reserva su nombre completo."""
        for tam in ((1366, 768), (2000, 1250)):
            w, d, cambios = self.plantilla(tam)
            combo = d.predeterminadas
            combo.showPopup()
            self.bombear()
            for i in range(combo.count()):
                ancho = combo.fontMetrics().horizontalAdvance(combo.itemText(i))
                self.assertGreaterEqual(combo.view().viewport().width(), ancho)
            combo.hidePopup()
            from PySide6.QtWidgets import QStyle, QStyleOptionComboBox
            opcion = QStyleOptionComboBox()
            combo.initStyleOption(opcion)
            campo = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, opcion,
                                                QStyle.SubControl.SC_ComboBoxEditField, combo)
            self.assertLessEqual(combo.fontMetrics().horizontalAdvance(combo.currentText()), campo.width() - 6)
            self.assertEqual(combo.toolTip(), combo.currentText())

    def test_SJ109_guardar_plantilla_aplica_solo_al_aceptar(self):
        """REQ-EDT-11, REQ-DAT-02: Guardar conserva la edición en la hoja del proyecto."""
        w, d, cambios = self.plantilla()
        d.editar_plantilla()
        self.assertTrue(d.sesion_plantilla.barra.isVisible())
        d.editor_textos.elegir(0)
        d.editor_textos.contenido.setPlainText("Cambio de plantilla")
        self.assertEqual(cambios, [])
        d.sesion_plantilla.guardar.click()
        self.assertFalse(d.editando_plantilla)
        self.assertFalse(d.sesion_plantilla.barra.isVisible())
        self.assertTrue(any(t.get("text") == "Cambio de plantilla"
                            for t in cambios[-1]["plantilla"]["primitives"]))

    def test_SJ110_cancelar_y_escape_preguntan_si_hay_cambios(self):
        """REQ-EDT-11: Cancelar preserva la hoja y no descarta cambios sin confirmación."""
        w, d, cambios = self.plantilla()
        original = copy.deepcopy(d.plantilla)
        d.editar_plantilla()
        d.editor_textos.elegir(0)
        d.editor_textos.x.setValue(d.editor_textos.x.value() + 3)
        with mock.patch("escritorio.sesion_plantilla.QMessageBox.question",
                        return_value=QMessageBox.StandardButton.No) as pregunta:
            d.sesion_plantilla.cancelar_boton.click()
            self.assertTrue(d.editando_plantilla)
            self.assertEqual(pregunta.call_args.args[2], "¿Descartar los cambios de la plantilla?")
        w.activateWindow()
        d.vista.setFocus()
        with mock.patch("escritorio.sesion_plantilla.QMessageBox.question",
                        return_value=QMessageBox.StandardButton.Yes):
            QTest.keyClick(d.vista, Qt.Key.Key_Escape)
            self.bombear()
        self.assertFalse(d.editando_plantilla)
        self.assertEqual(d.plantilla, original)
        self.assertEqual(cambios, [])

    def test_SJ111_zona_unica_personalizada_y_automatica(self):
        """REQ-EDT-11: el rectángulo se dibuja en la hoja y Automática elimina la selección propia."""
        w, d, cambios = self.plantilla()
        d.editar_plantilla()
        t = d.editor_textos
        self.assertEqual(t.zona.count(), 2)
        t.zona.setCurrentIndex(1)
        v = d.vista
        k = min((v.width() - 24) / v.documento.ancho, (v.height() - 24) / v.documento.alto)
        def punto(x, y):
            return QPoint(round((v.width() - v.documento.ancho * k) / 2 + x * k),
                          round((v.height() - v.documento.alto * k) / 2 + y * k))
        a, b = punto(25, 25), punto(150, 180)
        QTest.mousePress(v, Qt.MouseButton.LeftButton, pos=a)
        QTest.mouseMove(v, b)
        QTest.mouseRelease(v, Qt.MouseButton.LeftButton, pos=b)
        self.assertIsNotNone(d.plantilla.get("zone"))
        self.assertAlmostEqual(d.plantilla["zone"][0], 25, delta=1)
        t.zona.setCurrentIndex(0)
        self.assertIsNone(d.plantilla.get("zone"))

    def test_SJ112_campos_en_fila_y_aviso_sin_seleccion(self):
        """REQ-UX-01: X, Y y Altura usan la misma fila y explican por qué no son editables."""
        w, d, cambios = self.plantilla()
        d.editar_plantilla()
        t = d.editor_textos
        t.elegir(-1)
        self.assertTrue(t.controles.aviso.isVisible())
        self.assertFalse(t.x.isEnabled())
        t.elegir(0)
        self.bombear()
        self.assertFalse(t.controles.aviso.isVisible())
        self.assertTrue(t.x.isEnabled())
        form = t.panel_propiedades.widget().layout()
        for campo in (t.x, t.y, t.altura):
            label = form.labelForField(campo)
            self.assertLess(label.geometry().right(), campo.x())
            self.assertLessEqual(abs(label.geometry().center().y() - campo.geometry().center().y()), 1)
        self.assertGreater(t.borrar.y(), t.giro.y())

    def test_SJ113_auditoria_del_panel_de_plantilla_sin_excepciones(self):
        """REQ-UX-01: panel y barra de edición cumplen la auditoría en las dos escalas."""
        from test_auditoria_maquetacion import REGLAS
        for tam in ((1366, 768), (2000, 1250)):
            w, d, cambios = self.plantilla(tam)
            d.editar_plantilla()
            d.editor_textos.elegir(0)
            self.bombear()
            for raiz in (d.editor_textos.panel_propiedades, d.sesion_plantilla.barra):
                for nombre in ("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C4"):
                    self.assertEqual(REGLAS[nombre](raiz), [], (tam, nombre))

    def test_SJ114_dialogos_estandar_sin_botones_vacios(self):
        """REQ-UX-01: texto, confirmación, guardado, errores y selectores conservan sus botones."""
        from PySide6.QtWidgets import (QColorDialog, QDialogButtonBox, QErrorMessage, QFileDialog,
                                       QFontDialog, QInputDialog)
        w = self.crear()
        dialogos = [QInputDialog(w), QMessageBox(w), QColorDialog(w), QFontDialog(w), QErrorMessage(w)]
        archivo = QFileDialog(w)
        archivo.setOption(QFileDialog.Option.DontUseNativeDialog)
        archivo.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialogos.append(archivo)
        dialogos[1].setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                       | QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                       | QMessageBox.StandardButton.Cancel)
        for dialogo in dialogos:
            for caja in dialogo.findChildren(QDialogButtonBox):
                self.assertTrue(caja.buttons(), type(dialogo).__name__)
                for boton in caja.buttons():
                    self.assertTrue(boton.text().strip(), type(dialogo).__name__)

    def test_SJ115_recuerda_plegado_e_ignora_ocultacion_antigua(self):
        for abierto in (True, False):
            w = self.crear({"paneles/derecho/visible": False}, tam=(2000, 1250))
            w._mostrar_panel("derecho", abierto)
            w.ajustes.sync()
            otra = self.crear(archivo=w.ajustes.fileName(), tam=(2000, 1250))
            self.assertFalse(otra.ajustes.contains("paneles/derecho/visible"))
            self.assertTrue(otra._plegables["derecho"].isVisible())
            self.assertEqual(otra.derecho.isVisible(), abierto)
            self.assertEqual(otra.pestanas["derecho"].isVisible(), not abierto)


if __name__ == "__main__":
    unittest.main()
