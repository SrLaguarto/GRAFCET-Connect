"""Barra superior (separador y Play centrado), tabla avanzada de E/S (casilla centrada, columnas) y cajas de Puerto y Esclavo ID."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtWidgets import QApplication
    from escritorio.entradas_salidas import PanelES
    from grafcet.builder import M


def hueco_de_tinta(boton):
    """(lo que hay a la izquierda del icono y el texto, lo que hay a la derecha) en píxeles, mirando lo claro sobre el fondo del botón."""
    img = boton.grab().toImage()
    xs = [x for x in range(img.width()) if any(min(c.red(), c.green(), c.blue()) > 200 for c in (img.pixelColor(x, y) for y in range(img.height())))]
    return xs[0], img.width() - 1 - xs[-1]


@unittest.skipUnless(QT, "Falta PySide6")
class BarraYTablaES(BaseQt):
    def test_SBAR01_separador_entre_reiniciar_y_deshacer_y_play_centrado(self):
        """REQ-UX-01: la barra de edición empieza con un separador (tras Reiniciar) y el contenido de Play y de Stop queda centrado en su botón de ancho fijo."""
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        for _ in range(6):
            QApplication.processEvents()
        self.addCleanup(w.hide)
        acciones = w.tb_edit.actions()
        self.assertTrue(acciones[0].isSeparator())
        self.assertIs(acciones[1], w.a_deshacer)
        boton = w.tb_sim.widgetForAction(w.a_ejecutar)
        ancho = boton.width()
        for on in (False, True):
            w._marcar_play(on)
            izq, der = hueco_de_tinta(boton)
            self.assertLessEqual(abs(izq - der), 2, (on, izq, der))
            self.assertEqual(boton.width(), ancho, "el botón no cambia de ancho")
        w._marcar_play(False)

    def panel(self):
        p = PanelES()
        p.cargar(M().var("a").var("b").var("q", "output").step("0", True).doc)
        p.resize(1200, 700)
        p.show()
        p.abrir_configuracion()
        p._alternar_avanzado()
        p.dialogo_config.resize(1050, 700)
        for _ in range(6):
            QApplication.processEvents()
        self.addCleanup(lambda: (p.dialogo_config.close(), p.close()))
        return p

    def test_SBAR02_tabla_avanzada_casilla_centrada_y_columnas_justas(self):
        """REQ-SIM-03: la casilla «Usar» queda centrada en su columna; «Área» y «Formato» se leen enteros; «Dirección» es estrecha (cabecera en dos
        líneas) y su campo ocupa la celda, sin hueco; a 2000 px de pantalla se ven todas las columnas, con «Escala», sin barra horizontal."""
        p = self.panel()
        t = p.tabla
        casilla = t.cellWidget(0, 0).casilla
        centro = casilla.mapTo(t.viewport(), casilla.rect().center()).x()
        self.assertLessEqual(abs(centro - (t.columnViewportPosition(0) + t.columnWidth(0) // 2)), 2)
        self.assertEqual(t.horizontalHeaderItem(5).text(), "Dirección\n(base 0)")
        self.assertLessEqual(t.columnWidth(5), 130)
        self.assertGreaterEqual(t.cellWidget(0, 5).width(), t.columnWidth(5) - 4, "el campo de la dirección ocupa su celda")
        for col in (4, 6):
            control = t.cellWidget(0, col)
            self.assertGreaterEqual(t.columnWidth(col), control.sizeHint().width(), "el texto del desplegable se lee entero")
        self.assertFalse(t.horizontalScrollBar().isVisible())
        self.assertGreater(t.columnWidth(7), 60, "Escala se ve")

    def test_SBAR03_puerto_y_esclavo_estrechos_y_el_marco_no_cambia_de_ancho(self):
        """REQ-SIM-03: Puerto (5 cifras) y Esclavo ID (3 cifras) más estrechos en la cabecera del marco y en Configuración; el marco mide lo mismo con
        la cabecera de edición o con la de solo lectura."""
        p = self.panel()
        for puerto, unidad in ((p.puerto, p.unidad), (p.lienzo.puerto, p.lienzo.unidad)):
            self.assertLessEqual(puerto.width(), 90)
            self.assertLessEqual(unidad.width(), 70)
            self.assertLess(unidad.width(), puerto.width())
            self.assertGreaterEqual(puerto.width(), puerto.fontMetrics().horizontalAdvance("65535") + 18)
        c = p.lienzo.cabecera_marco
        medidas = []
        for pagina in (p.lienzo.edicion_destino, p.lienzo.destino):
            c.setCurrentWidget(pagina)
            QApplication.processEvents()
            medidas.append((c.width(), c.height(), p.lienzo.marco.width()))
        self.assertEqual(medidas[0], medidas[1])

    def test_SBAR04_boton_volver_de_la_cabecera_de_es_y_uniones_punteadas_de_dependencias(self):
        """REQ-UX-01: «Volver» lleva icono de flecha y texto, mide el alto de los botones de la cabecera y tiene ayuda sin atajo; el icono de
        dependencias une el cuadrado con el rectángulo con trazos punteados y finos (menos tinta que una línea continua)."""
        from PySide6.QtCore import QSize
        from escritorio import estilo
        p = self.panel()
        b = p.b_volver
        self.assertEqual((b.text(), b.toolTip()), ("Volver", "Volver al dibujo GRAFCET"))
        self.assertFalse(b.icon().isNull())
        self.assertEqual(b.height(), p.b_configuracion.height())
        img = estilo.icono("dependencias").pixmap(QSize(48, 48)).toImage()
        tinta = sum(1 for x in range(18, 30) for y in range(8, 40) if img.pixelColor(x, y).alpha() > 60)
        self.assertLess(tinta, 120)  # (con las uniones continuas de 1,75 px, la zona entre el cuadrado y el rectángulo son unos 158 píxeles)
