"""Comprobaciones de la barra de estado, Variables y el formulador de C2."""
from pathlib import Path
import unittest

from test_editor_cadenas import BaseQt, QT


@unittest.skipUnless(QT, "requiere PySide6")
class InterfazC2(BaseQt):
    def test_SC201_barra_con_firma_mensaje_y_contador_en_tres_zonas(self):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QFontMetrics

        w, e = self.vacio()
        w.resize(960, 1040)
        w.show()
        w.l_firma.setText("Archivo sin firma")
        w.l_firma.show()
        w._poner_reloj("10 etapas · 10 transiciones")
        mensaje = "Acción Contador cajas con un nombre largo " * 6
        sb = w.statusBar()
        sb.showMessage(mensaje)
        w._detallar("Detalle durante el mensaje")
        self.app.processEvents()

        izquierda, centro, derecha = (w.l_firma, w.l_mensaje_estado, w.l_reloj)
        cuadros = [QRect(v.mapTo(sb, v.rect().topLeft()), v.size()) for v in (izquierda, centro, derecha)]
        self.assertTrue(all(v.isVisible() for v in (w.l_aviso, izquierda, centro, derecha)))
        self.assertFalse(w.l_detalle.isVisible())
        self.assertLess(cuadros[0].right(), cuadros[1].left())
        self.assertLess(cuadros[1].right(), cuadros[2].left())
        self.assertEqual(centro.toolTip(), mensaje)
        medidas = QFontMetrics(derecha.font())
        self.assertEqual(len({medidas.horizontalAdvance(str(d)) for d in range(10)}), 1)
        w._detallar("Detalle durante el mensaje")
        sb.clearMessage()
        self.assertTrue(w.l_detalle.isVisible())
        self.assertFalse(centro.isVisible())

    def test_SC202_media_pantalla_mantiene_los_rotulos_y_el_conteo_plegado(self):
        from PySide6.QtCore import Qt

        w, e = self.vacio()
        w.resize(960, 1040)
        w.show()
        w._mostrar_panel("derecho", False)
        e.nueva_variable("memoria_del_proyecto", "internal")
        self.app.processEvents()
        self.assertEqual(w.pestanas["derecho"].text(), "Variables · 1")
        for accion, texto in ((w.a_dependencias, "Dependencias"), (w.a_errores, "Errores")):
            boton = w.tb_vista_der.widgetForAction(accion)
            self.assertTrue(boton.isVisible())
            self.assertEqual(boton.text(), texto)
            self.assertEqual(boton.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def test_SC203_variables_uniformes_y_eliminar_separado(self):
        from PySide6.QtWidgets import QStyleOptionViewItem
        from escritorio import estilo
        from escritorio.variables import MARCADOR_PENDIENTE

        w, e = self.vacio()
        nombre = "entrada_con_un_nombre_muy_largo_que_no_aumenta_la_altura"
        e.nueva_variable(nombre, "input")
        w._mostrar_panel("derecho", True)
        w.resize(1366, 768)
        w.show()
        self.app.processEvents()
        panel = w.variables
        tabla = panel.tabla
        tabla.clearSelection()
        self.assertFalse(panel.b_quitar.isEnabled())
        tabla.selectRow(0)
        self.assertTrue(panel.b_quitar.isEnabled())
        self.assertEqual(tabla.rowHeight(0), 32)
        self.assertEqual(tabla.item(0, 0).toolTip(), nombre)
        opciones = QStyleOptionViewItem()
        delegado = tabla.itemDelegate()
        delegado.initStyleOption(opciones, tabla.model().index(0, 2))
        self.assertEqual(opciones.text, "Bool")
        self.assertEqual(tabla.item(0, 2).text(), "Booleana")
        altas = list(panel.b_nuevas.values())
        self.assertEqual(len({b.geometry().top() for b in altas}), 1)
        self.assertGreater(panel.b_quitar.geometry().top(), altas[0].geometry().bottom())

        panel.b_nuevas["internal"].click()
        self.app.processEvents()
        pendiente = tabla.rowCount() - 1
        delegado.initStyleOption(opciones, tabla.model().index(pendiente, 0))
        self.assertEqual(opciones.text, MARCADOR_PENDIENTE)
        self.assertEqual(delegado._papel_franja(pendiente), "internal")
        self.assertEqual(tabla.rowHeight(pendiente), estilo.ALTO_ESTANDAR)

    def test_SC204_lista_acotada_y_filtro_en_el_selector_del_dibujo(self):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtTest import QTest
        from escritorio import estilo
        from escritorio.menu_variable import ROL_PAPEL, UMBRAL_FILTRO

        w, e = self.vacio()
        for i in range(UMBRAL_FILTRO):
            e.nueva_variable(f"salida_{i:02}", "output")
        e.nueva_variable("motor_objetivo", "internal")
        self.cadena(e)
        w.resize(1360, 860)
        w.show()
        identidad = e.poner_accion_suelta(QPointF(500, 200))
        for _ in range(6):
            self.app.processEvents()
        caja = next(c for c in w.diagrama.cajas_acciones if c["id"] == identidad)
        e.desplegar_variable(caja)
        self.app.processEvents()
        combo = w.diagrama._selector
        self.assertIsNotNone(combo)
        vista = combo.view()
        self.assertTrue(combo.con_filtro())
        self.assertTrue(combo.filtro_menu.etiqueta.isVisible())
        self.assertLessEqual(vista.window().height(), estilo.ALTO_MAX_DESPLEGABLE)
        QTest.keyClicks(vista, "objetivo")
        self.assertTrue(vista.isRowHidden(0))
        modelo = combo.model()
        indice = modelo.index(modelo.rowCount() - 1, 0)
        self.assertEqual(combo.delegado._rotulo_sobre(indice), "Memorias")
        self.assertTrue(indice.data(ROL_PAPEL))
        QTest.keyClick(vista, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(e.datos_accion(identidad)["variable"], "motor_objetivo")

    def test_SC205_fichas_de_memoria_y_recurso_del_temporizador(self):
        from PySide6.QtSvg import QSvgRenderer
        from escritorio import estilo
        from escritorio.banda_bloques import BandaBloques
        from escritorio.bloques import COLORES, Motor, nuevo

        nombre = "memoria_del_formulador_" * 8
        fuente = lambda: ({nombre: ("internal", "int")}, [])
        motor = Motor(fuente)
        motor.reiniciar()
        n = nuevo("vnum", n=nombre)
        for fijo in (False, True):
            motor.fijo = fijo
            caja = motor.caja(n, (), 500)
            self.assertEqual(COLORES[caja.cat], estilo.PAPEL_MEMORIA)
            self.assertGreater(caja.w, 200)
            self.assertLessEqual(caja.w, 240)
            self.assertEqual(caja.items[0][2].completo, nombre)
        banda = BandaBloques(fuente, "a")
        boton, = banda.botones["tiempo"]
        self.assertEqual(boton.text(), "Temporizador")
        self.assertFalse(boton.icon().isNull())
        recurso = Path(__file__).resolve().parents[1] / "escritorio" / "recursos" / "temporizador.svg"
        self.assertTrue(QSvgRenderer(str(recurso)).isValid())
