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
        """REQ-UX-01: Reiniciar y Deshacer tienen un separador visible entre sus barras y el contenido de Play y de Stop queda centrado en su botón de ancho fijo."""
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        for _ in range(6):
            QApplication.processEvents()
        self.addCleanup(w.hide)
        from escritorio.separadores_barra import SeparadorBarra
        separador, = w.herramientas_grafcet.findChildren(SeparadorBarra)
        self.assertTrue(separador.isVisible())
        self.assertLess(w.tb_sim.geometry().right(), separador.geometry().left())
        self.assertLess(separador.geometry().right(), w.tb_edit.geometry().left())
        self.assertIs(w.tb_edit.actions()[0], w.a_deshacer)
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
        from PySide6.QtCore import QRect
        p._pantalla_libre = lambda: QRect(0, 0, 2000, 1100)  # (la pantalla de pruebas mide 800 px: se emula la de 2000)
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
        self.assertEqual(t.horizontalHeaderItem(5).text(), "Dir.\n(base 0)")
        self.assertEqual(t.horizontalHeaderItem(5).toolTip(), "Dirección (base 0)")
        self.assertLessEqual(t.columnWidth(5), 130)
        self.assertGreaterEqual(t.cellWidget(0, 5).width(), t.columnWidth(5) - 4, "el campo de la dirección ocupa su celda")
        for col in (4, 6):
            control = t.cellWidget(0, col)
            self.assertGreaterEqual(t.columnWidth(col), control.sizeHint().width(), "el texto del desplegable se lee entero")
        self.assertFalse(t.horizontalScrollBar().isVisible())
        self.assertGreater(t.columnWidth(7), 60, "Escala se ve")

    def test_SBAR03_puerto_y_esclavo_estrechos_y_el_marco_no_cambia_de_ancho(self):
        """REQ-SIM-03, IM3: Puerto (5 cifras) y Esclavo ID (4 cifras visuales) estrechos en la cabecera y en Configuración.
        El marco mide lo mismo con
        la cabecera de edición o con la de solo lectura."""
        p = self.panel()
        for puerto, unidad in ((p.puerto, p.unidad), (p.lienzo.puerto, p.lienzo.unidad)):
            self.assertLessEqual(puerto.width(), 90)
            self.assertLessEqual(unidad.width(), 70)
            self.assertGreater(puerto.width(), unidad.width())
            self.assertEqual(puerto.width(), puerto.fontMetrics().horizontalAdvance("88888") + 28)
            self.assertEqual(unidad.width(), unidad.fontMetrics().horizontalAdvance("8888") + 28)
        c = p.lienzo.cabecera_marco
        medidas = []
        for pagina in (p.lienzo.edicion_destino, p.lienzo.destino):
            c.setCurrentWidget(pagina)
            QApplication.processEvents()
            medidas.append((c.width(), c.height(), p.lienzo.marco.width()))
        self.assertEqual(medidas[0], medidas[1])

    def test_SBAR04_cabecera_de_es_sin_volver_y_uniones_punteadas_de_dependencias(self):
        """REQ-UX-01: la cabecera de E/S ya no duplica botón «Volver» (C10); el icono de dependencias recupera las dos uniones diagonales finas y punteadas entre el cuadrado y el marco (J5)."""
        from PySide6.QtCore import QSize
        from escritorio import estilo
        p = self.panel()
        self.assertFalse(hasattr(p, "b_volver"))
        self.assertEqual(p.titulo_es.text(), "Asignación de E/S")
        img = estilo.icono("dependencias").pixmap(QSize(48, 48)).toImage()
        # J5 recupera dos diagonales; el centro del icono queda vacío.
        for signo in (-1, 1):
            muestras = []
            for x in range(21, 29):
                y = round(24 + signo * (5 * x / 6 - 9))
                tinta = sum(img.pixelColor(x, fila).alpha() > 60 for fila in range(y - 1, y + 2))
                muestras.append(tinta)
            self.assertTrue(any(tinta > 0 for tinta in muestras), "ambas diagonales tienen tinta")
            self.assertTrue(any(tinta == 0 for tinta in muestras), "los puntos dejan huecos")
