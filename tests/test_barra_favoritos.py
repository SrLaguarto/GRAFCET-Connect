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
            self.assertIn("border: 1px solid transparent", boton.styleSheet())
            self.assertIn("border-radius: 5px", boton.styleSheet())
            if clave in barra._visibles:
                self.assertEqual(boton.height(), barra.height() - 6)
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

    def test_SFAV04_arrastre_conserva_mime_figura_y_suelta(self):
        w, e, barra = self.preparar()

        def resumen():
            return (len(e.M["steps"]), len(e.M["transitions"]), len(e.ed.draft_actions()), len(e.M["partials"]))

        for clave in ("etapa", "transicion", "accion:condicionada", "parcial"):
            with self.subTest(clave=clave):
                boton = barra.botones[clave]
                datos, figura, punto = self._capturar_arrastre(lambda: w.paleta.arrastrar_elemento(clave, boton))
                esperado, ancla = propiedades.figura(clave, w.diagrama.escala(), boton.devicePixelRatioF())
                self.assertEqual(datos.formats(), ["text/plain"])
                self.assertEqual(datos.text(), clave)
                self.assertEqual(figura.toImage(), esperado.toImage())
                self.assertEqual(punto, ancla)
                antes = resumen()
                self._soltar(w, datos)
                self.assertNotEqual(resumen(), antes)
                e.deshacer()
                self.assertEqual(resumen(), antes)

    def test_SFAV05_gesto_de_arrastre_desde_boton_y_menu(self):
        w, e, barra = self.preparar(683, 768)
        for boton in (barra.botones["etapa"], barra.crear_menu_desborde().actions()[0].defaultWidget()):
            with mock.patch.object(w.paleta, "arrastrar_elemento") as arrastrar:
                QTest.mousePress(boton, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
                mover = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(40, 4), QPointF(40, 4),
                                   Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                                   Qt.KeyboardModifier.NoModifier)
                boton.mouseMoveEvent(mover)
                arrastrar.assert_called_once_with(boton.clave, boton)

    def test_SFAV06_catalogo_fijo_y_arrastre_de_las_quince_fichas(self):
        """REQ-EDT-09: las quince fichas fijas arrastran, incluso desde el menú de desborde."""
        w, e, barra = self.preparar(683, 768)
        self.assertTrue(barra.ocultos)
        self.assertEqual(barra.orden, list(PREDETERMINADOS))
        menu = barra.crear_menu_desborde()
        self.addCleanup(menu.deleteLater)
        botones = [barra.botones[c] for c in barra._visibles] + [a.defaultWidget() for a in menu.actions()]
        self.assertEqual([b.clave for b in botones], list(PREDETERMINADOS))
        for boton in botones:
            with self.subTest(clave=boton.clave):
                datos, figura, punto = self._capturar_arrastre(lambda: self._arrastrar_boton(boton))
                self.assertEqual(datos.text(), boton.clave)
                self.assertFalse(figura.isNull())
                self.assertTrue(figura.rect().contains(punto))

    @staticmethod
    def _arrastrar_boton(boton):
        QTest.mousePress(boton, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
        mover = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(40, 4), QPointF(40, 4),
                            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        boton.mouseMoveEvent(mover)

    def test_SFAV07_reordenacion_marca_insercion_y_persistencia(self):
        """REQ-EDT-09: J4 ignora soltar dentro de la barra; el arrastre al dibujo conserva SFAV04/05."""
        w, e, barra = self.preparar()
        mime = QMimeData()
        mime.setText("accion:condicionada")
        evento = QDropEvent(QPointF(4, 4), Qt.DropAction.CopyAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        barra.dropEvent(evento)
        self.assertFalse(evento.isAccepted())
        self.assertFalse(barra.acceptDrops())
        self.assertEqual(barra.orden, list(PREDETERMINADOS))


    def test_SFAV08_ignora_claves_desconocidas_y_nuevas_no_elegidas(self):
        """REQ-EDT-09: J4 borra listas antiguas, vacías o con claves desconocidas."""
        w, e, barra = self.preparar()
        for antigua in (["desconocida", "transicion", "etapa"], []):
            w.ajustes.setValue(barra.CLAVE_AJUSTES, antigua)
            recuperada = BarraFavoritos(w.ajustes, w.paleta)
            self.addCleanup(recuperada.deleteLater)
            self.assertEqual(recuperada.orden, list(PREDETERMINADOS))
            self.assertFalse(w.ajustes.contains(barra.CLAVE_AJUSTES))


    def test_SFAV09_desborde_y_zoom_antes_de_ocultar_favoritos(self):
        w, e, barra = self.preparar(960, 1032)
        self.assertTrue(w.diagrama._solo_iconos)
        self.assertTrue(w.diagrama.l_zoom.isVisible())
        self.assertFalse(barra.ocultos, "a 960 caben las quince fichas y el porcentaje")
        w.resize(683, 768)
        self.asentar_escala(w)
        for _ in range(5):
            QApplication.processEvents()
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
            self.assertLess(barra.geometry().right(), w.diagrama.barra.x())
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
            self.assertIs(w.pestanas_vistas.parentWidget(), w.estuche_vistas)
            self.assertIs(w.luz_es.parentWidget(), w.estuche_vistas)
            self.assertGreater(w.luz_es.x(), w.pestanas_vistas.geometry().right())
            self.assertLess(estado.geometry().right(), w.estuche_vistas.x())
            self.assertGreater(estado.x(), w.menu_cluster.geometry().right())
            centro_modo = (estado.x() + estado.geometry().right()) / 2
            self.assertLessEqual(abs(centro_modo - w.fila_pestanas.width() / 2), 2)
            self.assertLessEqual(w.estuche_vistas.geometry().right(), w.fila_pestanas.width() - 9)
        for modo, color in (("editar", estilo.ACENTO), ("simular", "#22c55e"),
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
        self.assertLess(w.estado.x(), (w.fila_pestanas.width() - w.estado.width()) // 2)
        self.assertEqual(w.estado.geometry().right() + 1 + estilo.E2, w.estuche_vistas.x())
        self.assertGreater(w.estado.x(), w.menu_cluster.geometry().right())
        self.assertLessEqual(w.estuche_vistas.geometry().right(), w.fila_pestanas.width() - 9)

    def test_SFAV14_sin_logo_y_menu_sin_plegar(self):
        """IM4 & IM5: sin logo junto al menú, con menús visibles sin «» desde 1024 px."""
        from PySide6.QtWidgets import QToolButton
        w, _, _ = self.preparar(1024, 768)
        self.assertFalse(hasattr(w, "l_logo"))
        for ancho, alto in ((1024, 768), (1280, 720)):
            w.resize(ancho, alto)
            self.asentar_escala(w)
            for _ in range(5):
                QApplication.processEvents()
            ext = w._menu_bar.findChild(QToolButton, "qt_menubar_ext_button")
            self.assertTrue(ext is None or not ext.isVisible(), (ancho, ext and ext.isVisible()))

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
        self.assertEqual(recuperada.orden, list(PREDETERMINADOS))

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
        self.assertFalse(w.ajustes.contains(barra.CLAVE_AJUSTES))
