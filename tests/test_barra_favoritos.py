"""SFAV: favoritos persistentes y arrastrables, desborde y estado en pestañas."""
import copy
import unittest
from unittest import mock

try:
    from PySide6.QtWidgets import QApplication
    QT = True
except ImportError:
    QT = False

if QT:
    from test_editor_cadenas import BaseQt
    from PySide6.QtCore import QMimeData, QPoint, QPointF, QSize, Qt
    from PySide6.QtGui import QDropEvent, QMouseEvent, QRegion
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QAbstractButton, QLabel

    from escritorio import propiedades, estilo
    from escritorio.favoritos import BarraFavoritos, PREDETERMINADOS, icono_mini, pintar_mini

else:
    BaseQt = unittest.TestCase

@unittest.skipUnless(QT, "requiere PySide6")
class Favoritos(BaseQt):
    def preparar(self, ancho=1366, alto=768):
        w, e = self.vacio()
        w.resize(ancho, alto)
        w.show()
        self.pasar_arranque(w)
        for _ in range(5):
            QApplication.processEvents()
        return w, e, w.favoritos

    def test_SFAV01_predeterminados_iconos_y_ayuda(self):
        w, e, barra = self.preparar()
        self.assertTrue(barra.isVisible())
        self.assertEqual(barra.orden, list(PREDETERMINADOS))
        for clave, boton in barra.botones.items():
            from escritorio.ayudas_emergentes import texto_plano
            ayuda = texto_plano(boton.toolTip())
            self.assertIn(propiedades.Paleta.nombre(clave), ayuda)
            self.assertIn(propiedades.Paleta.texto_ayuda(clave), ayuda)
            self.assertEqual(boton.iconSize(), QSize(barra.lado_icono, barra.lado_icono))
            self.assertEqual(boton.text(), "")
            self.assertFalse(boton.icon().isNull())
            self.assertIn("background: transparent", boton.styleSheet())
            self.assertIn("border: none", boton.styleSheet())
            if clave in barra._visibles:
                self.assertEqual(boton.height(), barra.height())
            self.assertEqual(boton.icon().actualSize(QSize(24, 24)), QSize(24, 24))
            self.assertEqual(boton.icon().pixmap(24, 24).size(), QSize(24, 24))

    def test_SFAV02_se_ocultan_al_simular_y_vuelven_al_editar(self):
        w, e, barra = self.preparar()
        self.cadena(e)
        anterior = list(barra.orden)
        w.cambiar_modo("simular")
        QApplication.processEvents()
        self.assertFalse(barra.isVisible())
        self.assertIn("SIMULACIÓN", w.estado.text())
        w.cambiar_modo("editar")
        QApplication.processEvents()
        self.assertTrue(barra.isVisible())
        self.assertEqual(barra.orden, anterior)

    def test_SFAV03_un_clic_no_crea_elementos(self):
        w, e, barra = self.preparar()
        antes = copy.deepcopy((e.ed.model, e.ed.presentation))
        for clave in PREDETERMINADOS:
            QTest.mouseClick(barra.botones[clave], Qt.MouseButton.LeftButton)
        self.assertEqual((e.ed.model, e.ed.presentation), antes)

    def _capturar_arrastre(self, llamada):
        drag = mock.Mock()
        with mock.patch.object(propiedades, "QDrag", return_value=drag):
            llamada()
        return (drag.setMimeData.call_args.args[0], drag.setPixmap.call_args.args[0],
                drag.setHotSpot.call_args.args[0])

    def _soltar(self, w, mime):
        evento = QDropEvent(QPointF(400, 300), Qt.DropAction.CopyAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        w.diagrama.dropEvent(evento)
        self.assertTrue(evento.isAccepted())

    def test_SFAV04_arrastre_compartido_y_mismo_resultado_al_soltar(self):
        w, e, barra = self.preparar()
        def resumen():
            return (len(e.M["steps"]), len(e.M["transitions"]), len(e.ed.draft_actions()), len(e.M["partials"]))
        for clave in ("etapa", "transicion", "accion:condicionada", "parcial"):
            with self.subTest(clave=clave):
                item = next(w.paleta.item(i) for i in range(w.paleta.count())
                            if w.paleta.item(i).data(Qt.ItemDataRole.UserRole) == clave)
                w.paleta.setCurrentItem(item)
                original = self._capturar_arrastre(lambda: w.paleta.startDrag(Qt.DropAction.CopyAction))
                favorito = self._capturar_arrastre(lambda: w.paleta.arrastrar_elemento(clave, barra.botones[clave]))
                self.assertEqual(original[0].formats(), favorito[0].formats())
                for formato in original[0].formats():
                    self.assertEqual(original[0].data(formato), favorito[0].data(formato))
                self.assertEqual(original[1].toImage(), favorito[1].toImage())
                self.assertEqual(original[2], favorito[2])
                antes = resumen()
                self._soltar(w, original[0])
                esperado = resumen()
                self.assertNotEqual(esperado, antes)
                e.deshacer()
                self.assertEqual(resumen(), antes)
                self._soltar(w, favorito[0])
                self.assertEqual(resumen(), esperado)
                e.deshacer()

    def test_SFAV05_gesto_de_arrastre_desde_boton_y_menu(self):
        w, e, barra = self.preparar(960, 1032)
        for boton in (barra.botones["etapa"], barra.crear_menu_desborde().actions()[0].defaultWidget()):
            with mock.patch.object(w.paleta, "arrastrar_elemento") as arrastrar:
                QTest.mousePress(boton, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
                mover = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(40, 4), QPointF(40, 4),
                                   Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                                   Qt.KeyboardModifier.NoModifier)
                boton.mouseMoveEvent(mover)
                arrastrar.assert_called_once_with(boton.clave, boton)

    def test_SFAV06_menu_por_secciones_no_se_cierra_y_persiste(self):
        w, e, barra = self.preparar()
        menu = barra.crear_menu_seleccion()
        self.addCleanup(menu.close)
        secciones = [a.text() for a in menu.actions() if a.isSeparator()]
        self.assertEqual(secciones, [t for t, _ in propiedades.SECCIONES])
        acciones = {a.data(): a for a in menu.actions() if a.isCheckable()}
        self.assertEqual(list(acciones), list(propiedades.COLOCABLES))
        menu.popup(barra.mapToGlobal(QPoint(0, barra.height())))
        QApplication.processEvents()
        QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(acciones["etapa"]).center())
        self.assertTrue(menu.isVisible())
        self.assertNotIn("etapa", barra.orden)
        acciones["texto"].trigger()
        self.assertNotIn("texto", barra.orden)
        acciones["texto"].trigger()
        self.assertIn("texto", barra.orden)
        self.assertEqual(w.ajustes.value(barra.CLAVE_AJUSTES), barra.orden)
        recuperada = BarraFavoritos(w.ajustes, w.paleta)
        self.addCleanup(recuperada.deleteLater)
        self.assertEqual(recuperada.orden, barra.orden)

    def test_SFAV07_reordenacion_marca_insercion_y_persistencia(self):
        w, e, barra = self.preparar()
        mime = QMimeData()
        mime.setText("accion:condicionada")
        evento = mock.Mock()
        evento.source.return_value = barra.botones["accion:condicionada"]
        evento.mimeData.return_value = mime
        evento.position.return_value = QPointF(estilo.E2, 10)
        barra.dragEnterEvent(evento)
        barra.dragMoveEvent(evento)
        self.assertEqual(barra._insercion, 0)
        imagen = barra.grab().toImage()
        self.assertEqual(imagen.pixelColor(estilo.E2, estilo.E2).name(), estilo.ACENTO)
        barra.dropEvent(evento)
        self.assertEqual(barra.orden[0], "accion:condicionada")
        self.assertIsNone(barra._insercion)
        self.assertEqual(w.ajustes.value(barra.CLAVE_AJUSTES), barra.orden)
        antes = list(barra.orden)
        barra.dragMoveEvent(evento)
        barra.dragLeaveEvent(mock.Mock())
        self.assertEqual(barra.orden, antes)
        self.assertIsNone(barra._insercion)
        recuperada = BarraFavoritos(w.ajustes, w.paleta)
        self.addCleanup(recuperada.deleteLater)
        self.assertEqual(recuperada.orden, antes)

    def test_SFAV08_ignora_claves_desconocidas_y_nuevas_no_elegidas(self):
        w, e, barra = self.preparar()
        w.ajustes.setValue(barra.CLAVE_AJUSTES, ["desconocida", "transicion", "etapa", "transicion"])
        recuperada = BarraFavoritos(w.ajustes, w.paleta)
        self.addCleanup(recuperada.deleteLater)
        self.assertEqual(recuperada.orden, ["transicion", "etapa"])
        w.ajustes.setValue(barra.CLAVE_AJUSTES, [])
        vacia = BarraFavoritos(w.ajustes, w.paleta)
        self.addCleanup(vacia.deleteLater)
        self.assertEqual(vacia.orden, [])

    def test_SFAV09_desborde_y_zoom_antes_de_ocultar_favoritos(self):
        w, e, barra = self.preparar(960, 1032)
        self.assertTrue(w.diagrama._solo_iconos)
        self.assertTrue(barra.desborde.isVisible())
        self.assertTrue(barra.ocultos)
        menu = barra.crear_menu_desborde()
        self.addCleanup(menu.deleteLater)
        self.assertEqual([a.data() for a in menu.actions()], barra.ocultos)
        self.assertTrue(all(not a.icon().isNull() and a.text() for a in menu.actions()))
        for ancho, alto in ((1366, 768), (2000, 1250)):
            w.resize(ancho, alto)
            self.asentar_escala(w)
            for _ in range(5):
                QApplication.processEvents()
            self.assertFalse(barra.ocultos)
            self.assertFalse(barra.desborde.isVisible())
            self.assertLess(barra.geometry().right(), w.b_ayuda.x())
            self.assertLess(w.b_ayuda.geometry().right(), w.diagrama.barra.x())
        self.assertFalse(w.diagrama._solo_iconos)

    def test_SFAV10_modo_centrado_en_pestanas_sin_aspecto_de_boton(self):
        w, e, barra = self.preparar()
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            w.resize(ancho, alto)
            self.asentar_escala(w)
            for _ in range(5):
                QApplication.processEvents()
            estado = w.estado
            self.assertIs(estado.parentWidget(), w.fila_pestanas)
            self.assertIsInstance(estado, QLabel)
            self.assertNotIsInstance(estado, QAbstractButton)
            self.assertNotEqual(estado.cursor().shape(), Qt.CursorShape.PointingHandCursor)
            self.assertIn("background: transparent", estado.styleSheet())
            self.assertIn(estilo.TINTA_2, estado.styleSheet())
            self.assertGreater(estado.x(), w.pestanas_vistas.geometry().right())
            self.assertLess(estado.geometry().right(), w.luz_es.x())
            if ancho != 960:
                self.assertLessEqual(abs(estado.geometry().center().x() - w.fila_pestanas.width() / 2), 1)
        for modo, color in (("editar", estilo.ACENTO), ("simular", estilo.SIMULACION),
                            ("aviso", estilo.AVISO), ("error", estilo.ERROR)):
            w._poner_chip(modo, "SIMULACIÓN · ESTABLE", "Descripción completa")
            self.assertEqual(w.estado.color_modo, color)
            self.assertEqual(w.estado.toolTip(), "Descripción completa")

    def test_SFAV11_nombre_solo_en_la_ventana_y_sin_etiqueta_en_cabecera(self):
        w, e, barra = self.preparar()
        self.assertFalse(hasattr(w, "titulo"))
        self.assertIn(e.titulo, w.windowTitle())
        widgets = [w._cab.itemAt(i).widget() for i in range(w._cab.count())]
        self.assertIn(barra, widgets)
        self.assertNotIn(w.estado, widgets)
        self.assertFalse([x for x in widgets if isinstance(x, QLabel) and x.text() == e.titulo])

    def test_SFAV12_modo_va_tras_pestanas_si_el_centro_no_cabe(self):
        w, e, barra = self.preparar(960, 1032)
        w.luz_es.setFixedWidth(430)
        w._poner_chip("simular", "SIMULACIÓN · ESTABLE", "Estado de la simulación")
        for _ in range(5):
            QApplication.processEvents()
        izquierda = w.pestanas_vistas.geometry().right() + estilo.E2
        self.assertEqual(w.estado.x(), izquierda)
        self.assertLess(w.estado.geometry().right(), w.luz_es.x())

    def test_SFAV13_nuevo_orden_predeterminado_sin_sustituir_el_guardado(self):
        w, e, barra = self.preparar()
        nombres = [propiedades.Paleta.nombre(h) for h in barra.orden]
        self.assertEqual(nombres, [
            "Etapa inicial", "Etapa", "Transición", "Simultaneidad", "Continua", "Condicionada", "Al activar",
            "Al desactivar", "Por evento", "Forzado", "Macroetapa", "Encapsulante", "Grafcet parcial",
            "Texto", "Imagen",
        ])
        w.ajustes.setValue(barra.CLAVE_AJUSTES, ["accion:evento", "texto", "etapa"])
        recuperada = BarraFavoritos(w.ajustes, w.paleta)
        self.addCleanup(recuperada.deleteLater)
        self.assertEqual(recuperada.orden, ["accion:evento", "texto", "etapa"])

    def test_SFAV14_rectangulos_de_acciones_y_forzado_alineados(self):
        rectangulos = []
        for clave in ["accion:" + t for t in (
                "continua", "condicionada", "activacion", "desactivacion", "evento")] + ["forzado"]:
            pintor = mock.Mock()
            pintar_mini(pintor, clave)
            cuerpo = pintor.drawRect.call_args_list[0].args[0]
            rectangulos.append(cuerpo)
            self.assertAlmostEqual(cuerpo.center().y(), 12, delta=0.5)
            self.assertAlmostEqual(cuerpo.width(), 18, delta=0.5)
            self.assertAlmostEqual(cuerpo.height(), 8.4, delta=0.5)
            pintor.drawText.assert_not_called()
            lapiz = pintor.setPen.call_args.args[0]
            self.assertEqual(lapiz.widthF(), 1.5)
            self.assertEqual(lapiz.color().name(), estilo.TINTA.lower())
        for cuerpo in rectangulos[1:]:
            for valor, esperado in zip(cuerpo.getRect(), rectangulos[0].getRect()):
                self.assertAlmostEqual(valor, esperado, delta=0.5)

    def test_SFAV15_parcial_apaisado_y_g_legible(self):
        pintor = mock.Mock()
        pintar_mini(pintor, "parcial")
        marco = pintor.drawRoundedRect.call_args.args[0]
        self.assertGreaterEqual(marco.width() / marco.height(), 1.4)
        letra = pintor.drawPath.call_args.args[0].boundingRect()
        self.assertTrue(marco.contains(letra))
        self.assertGreaterEqual(letra.height(), 6)
        for ratio in (1, 1.25, 1.5):
            imagen = icono_mini("parcial").pixmap(QSize(24, 24), ratio)
            limites = QRegion(imagen.mask()).boundingRect()
            self.assertGreaterEqual(limites.width() / limites.height(), 1.4)

    def test_SFAV16_caja_comun_y_render_nativo_a_tres_dpr(self):
        with mock.patch.object(propiedades, "icono", side_effect=AssertionError("No reducir la ficha")), \
                mock.patch.object(propiedades, "figura", side_effect=AssertionError("No reducir el arrastre")):
            for clave in propiedades.COLOCABLES:
                pintor = mock.Mock()
                pintar_mini(pintor, clave)
                for llamada in pintor.setPen.call_args_list:
                    self.assertEqual(llamada.args[0].widthF(), 1.5)
                    self.assertEqual(llamada.args[0].color().name(), estilo.TINTA.lower())
                icono = icono_mini(clave)
                self.assertEqual(icono.actualSize(QSize(24, 24)), QSize(24, 24))
                for ratio in (1, 1.25, 1.5):
                    with self.subTest(clave=clave, ratio=ratio):
                        imagen = icono.pixmap(QSize(24, 24), ratio)
                        self.assertEqual(imagen.size(), QSize(round(24 * ratio), round(24 * ratio)))
                        self.assertEqual(imagen.devicePixelRatioF(), ratio)
                        limites = QRegion(imagen.mask()).boundingRect()
                        self.assertFalse(limites.isEmpty())
                        self.assertTrue(imagen.rect().contains(limites))

    def test_SFAV17_encapsulante_conserva_cuadrado_y_diagonales_interiores(self):
        etapa = mock.Mock()
        pintar_mini(etapa, "etapa")
        pintor = mock.Mock()
        pintar_mini(pintor, "encapsulante")
        cuerpo = pintor.drawRect.call_args.args[0]
        self.assertEqual(cuerpo, etapa.drawRect.call_args.args[0])
        self.assertEqual(pintor.drawLine.call_count, 4)
        pintor.drawPolygon.assert_not_called()
        for llamada in pintor.drawLine.call_args_list:
            a, b = llamada.args
            self.assertTrue(cuerpo.contains(a))
            self.assertTrue(cuerpo.contains(b))
            self.assertNotEqual(a.x(), b.x())
            self.assertNotEqual(a.y(), b.y())

    def test_SFAV18_ejemplos_sin_barra_y_retorno_a_proyecto_editable(self):
        w, e, barra = self.preparar()
        barra.reordenar("accion:evento", 0)
        anterior = list(barra.orden)
        w.cargar_ejemplo("aula_marcha")
        QApplication.processEvents()
        self.assertTrue(w.solo_lectura)
        self.assertEqual(w.modo, "editar")
        self.assertFalse(barra.isVisible())
        for modo in ("simular", "editar"):
            w.cambiar_modo(modo)
            QApplication.processEvents()
            self.assertFalse(barra.isVisible())
        w.edicion.ed.dirty = False
        w.nuevo()
        QApplication.processEvents()
        self.assertFalse(w.solo_lectura)
        self.assertTrue(barra.isVisible())
        self.assertEqual(barra.orden, anterior)
        self.assertEqual(w.ajustes.value(barra.CLAVE_AJUSTES), anterior)
