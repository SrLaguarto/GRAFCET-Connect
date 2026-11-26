"""SP8 (E8): las piezas de la ventana de Propiedades rediseñada y la vista previa en franja con la transición de una sola tarjeta."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QMimeData, QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from tools import hoja_contactos as HC
    from escritorio import estilo
    from escritorio.partes_propiedades import (LINEAS_COMENTARIO, CampoComentario, ConmutadorPartes, PiePropiedades,
                                               una_linea)
    QT = True
except ImportError:
    QT = False


def _bombear(n=6):
    for _ in range(n):
        QApplication.processEvents()


@unittest.skipUnless(QT, "requiere PySide6")
class Piezas(unittest.TestCase):
    def setUp(self):
        HC.aplicacion()
        estilo.activar_escala("normal")

    def campo(self, ancho=300):
        c = CampoComentario()
        self.addCleanup(c.deleteLater)
        c.resize(ancho, c.height())
        c.show()
        _bombear()
        return c

    def test_SP801_el_comentario_es_de_una_linea(self):
        """REQ-EDT-02, REQ-UX-01: un salto pegado pasa a un espacio, Intro y Mayús+Intro no escriben un salto."""
        self.assertEqual(una_linea("a\nb\r\nc \n d"), "a b c d")
        c = self.campo()
        mime = QMimeData()
        mime.setText("uno\ndos\r\ntres")
        c.insertFromMimeData(mime)
        self.assertEqual(c.text(), "uno dos tres")
        c.setText("x\ny")
        self.assertEqual(c.text(), "x y")
        c.setFocus()
        for mods in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier, Qt.KeyboardModifier.ControlModifier):
            QTest.keyClick(c, Qt.Key.Key_Return, mods)
        QTest.keyClick(c, Qt.Key.Key_Enter)
        self.assertEqual(c.text(), "x y")
        self.assertNotIn("\n", c.toPlainText())

    def test_SP802_el_comentario_crece_con_el_texto_y_se_estira(self):
        """REQ-EDT-02: ajusta al ancho, crece hasta LINEAS_COMENTARIO, después se desplaza y se estira desde la esquina."""
        c = self.campo(160)
        una = c.height()
        c.setText("palabra " * 8)
        _bombear()
        dos = c.height()
        self.assertGreater(dos, una)
        c.setText("palabra " * 80)
        _bombear()
        tope = c.height()
        self.assertEqual(tope, c.alto_por_texto())
        self.assertLessEqual(tope, c._alto_para(LINEAS_COMENTARIO))
        c.estirar(tope + 60)
        self.assertGreater(c.height(), tope)
        c.estirar(0)
        self.assertEqual(c.height(), tope)
        c.setText("")
        _bombear()
        self.assertEqual(c.height(), una)
        agarre = c._agarre
        self.assertTrue(agarre.isVisible())
        self.assertLessEqual(agarre.geometry().right(), c.width())

    def test_SP803_foco_fuera_confirma(self):
        """REQ-EDT-02: `editingFinished` sale al perder el foco, como un campo de una línea."""
        c = self.campo()
        avisos = []
        c.editingFinished.connect(lambda: avisos.append(c.text()))
        c.setFocus()
        c.setText("nota")
        c.clearFocus()
        self.assertEqual(avisos, ["nota"])

    def test_SP804_conmutador_de_partes(self):
        """REQ-EDT-02: el botón pulsado cambia de parte y avisa; `poner` cambia sin avisar; no hay punto de aviso."""
        k = ConmutadorPartes([("condicion", "Condición", estilo.ACENTO), ("accion", "Acción", estilo.TINTA_2)])
        self.addCleanup(k.deleteLater)
        k.show()
        _bombear()
        vistas = []
        k.elegida.connect(vistas.append)
        self.assertEqual(k.clave(), "condicion")
        QTest.mouseClick(k.botones["accion"], Qt.MouseButton.LeftButton)
        self.assertEqual((k.clave(), vistas), ("accion", ["accion"]))
        k.poner("condicion")
        self.assertEqual((k.clave(), vistas), ("condicion", ["accion"]))
        self.assertFalse(hasattr(k, "avisar"))
        self.assertFalse(any(hasattr(b, "aviso") for b in k.botones.values()))
        self.assertEqual(k.botones["accion"].grab().size(), k.botones["accion"].size())

    def test_SP805_pie_con_etiqueta_y_comentario(self):
        """REQ-EDT-02: el pie coloca etiqueta, casilla y comentario en una fila, con el comentario a la derecha."""
        from PySide6.QtWidgets import QCheckBox, QLineEdit
        pie = PiePropiedades()
        self.addCleanup(pie.deleteLater)
        e, m, c = QLineEdit(), QCheckBox("Mostrar etiqueta"), CampoComentario()
        pie.poner(e, m, c)
        pie.resize(600, 44)
        pie.show()
        _bombear()
        self.assertLess(e.geometry().right(), m.geometry().left())
        self.assertLess(m.geometry().right(), c.geometry().left())
        self.assertEqual(pie.alto_nominal(), 44)  # 2.0.1: franja `.comment-row` de 44 px nominales

    def test_SP806_pie_de_la_maqueta_v3(self):
        """REQ-UX-01: el pie rotula «Etiqueta» y «Comentario» junto a sus campos, la etiqueta mide 62 px y los rótulos se centran con su campo."""
        from PySide6.QtWidgets import QCheckBox, QLineEdit
        pie = PiePropiedades()
        self.addCleanup(pie.deleteLater)
        e, m, c = QLineEdit(), QCheckBox("Mostrar etiqueta"), CampoComentario()
        pie.poner(e, m, c)
        pie.resize(700, 60)
        pie.show()
        _bombear()
        self.assertEqual(e.width(), 62)
        self.assertEqual((pie.l_etiqueta.text(), pie.l_comentario.text()), ("Etiqueta", "Comentario"))
        self.assertLess(pie.l_etiqueta.geometry().right(), e.geometry().left())
        self.assertLess(pie.l_comentario.geometry().right(), c.geometry().left())
        self.assertEqual(pie.l_comentario.height(), 26)  # 2.0.1: rótulo de 26 px fijos en `PiePropiedades.escalar`
        self.assertEqual(e.geometry().top(), estilo.E2)  # 2.0.1: márgenes (14, 8, 14, 8)

    def test_SP807_conmutador_con_los_colores_de_parte(self):
        """REQ-UX-01: el botón activo se rellena con el color de su parte y lleva el cuadradito blanco; el desactivado, en DESHABILITADO; ningún
        botón pinta el punto ámbar de aviso (la vista previa ya enseña «?» donde falta algo)."""
        k = ConmutadorPartes([("condicion", "Condición", estilo.SENAL_CONDICION), ("accion", "Acción", estilo.SENAL_ACCION)])
        self.addCleanup(k.deleteLater)
        k.show()
        _bombear()
        activo, otro = k.botones["condicion"], k.botones["accion"]
        imagen = activo.grab().toImage()
        self.assertEqual(imagen.pixelColor(imagen.width() // 2, 3).name(), estilo.SENAL_CONDICION)
        dpr = imagen.devicePixelRatio()
        self.assertEqual(imagen.pixelColor(round((estilo.E3 + 3) * dpr), imagen.height() // 2).name(), "#ffffff", "el cuadradito blanco del activo se queda")
        imagen = otro.grab().toImage()
        self.assertNotEqual(imagen.pixelColor(imagen.width() // 2, 3).name(), estilo.SENAL_ACCION)  # el inactivo no va relleno
        otro.setEnabled(False)
        _bombear()
        imagen = otro.grab().toImage()
        self.assertTrue(any(imagen.pixelColor(x, y).name() == estilo.DESHABILITADO for x in range(imagen.width()) for y in range(imagen.height())))
        for b in (activo, otro):
            img = b.grab().toImage()
            for x in range(img.width()):
                for y in range(img.height()):
                    self.assertNotEqual(img.pixelColor(x, y).name(), estilo.AVISO_BORDE, "no hay punto ámbar")

    def test_SP808_tokens_nuevos_de_estilo(self):
        """REQ-UX-01: `ORIGEN_MEMORIA` coincide con el morado unificado de memoria (distinto de AVISO y de los tipos) y las señales de parte, las de siempre."""
        self.assertEqual(estilo.ORIGEN_MEMORIA, "#6d28d9")
        self.assertNotIn(estilo.ORIGEN_MEMORIA, (estilo.AVISO, estilo.AVISO_BORDE, estilo.TIPO_ENTERA, estilo.TIPO_DECIMAL, estilo.TIPO_BOOL))
        from escritorio.flotantes import SENAL_ACCION, SENAL_CONDICION
        self.assertEqual((SENAL_CONDICION, SENAL_ACCION), (estilo.ACENTO, estilo.TINTA_2))


@unittest.skipUnless(QT, "requiere PySide6")
class Ventana(unittest.TestCase):
    def contexto(self, tipo, ancho=1366, alto=768):
        HC.aplicacion()
        c = HC.Contexto(ancho, alto)
        self.addCleanup(c.cerrar)
        HC._flotante(tipo)(c)
        return c, c.w.flot.panel, c.w.flot.principal

    def test_SP810_la_vista_previa_es_una_franja_de_ancho_completo_y_con_tope(self):
        """REQ-EDT-02: la lupa va arriba, ocupa el ancho de la ventana, mide su elemento (hasta el 125 %) y nunca pasa del tope de alto."""
        from escritorio.flotantes import FRANJA_FRACCION
        for tipo in ("etapa", "transicion", "activacion", "activacion_numerica"):  # (condicionada y evento: de lado hasta E8-P6)
            for ancho, alto in ((1366, 768), (960, 1032)):
                with self.subTest(tipo=tipo, ancho=ancho):
                    c, p, v = self.contexto(tipo, ancho, alto)
                    lupa, columna = v.lupa, v.columna
                    self.assertLess(lupa.geometry().bottom(), columna.geometry().top())
                    self.assertGreaterEqual(lupa.width(), v.cuerpo.width() - 2 * estilo.E4)
                    self.assertLessEqual(lupa.height(), max(estilo.ALTO_CONTROL + 2 * estilo.E3, round(c.w.flot._area().height() * FRANJA_FRACCION)))
                    self.assertGreaterEqual(lupa.height(), estilo.ALTO_CONTROL + 2 * estilo.E3)
                    t = lupa.transformar()
                    self.assertLessEqual(t.m11(), 1.25 + 1e-9)
                    destino = t.mapRect(lupa.origen)
                    self.assertAlmostEqual(destino.center().x(), lupa.width() / 2, delta=1)  # centrado
                    self.assertTrue(v.rect().contains(v.cuerpo.geometry()))

    def test_SP811_etapa_n_va_en_la_esquina_de_la_franja(self):
        """REQ-EDT-02: «Etapa N» solo informa, en la esquina inferior derecha de la vista previa, y no en el panel."""
        c, p, v = self.contexto("activacion")
        self.assertEqual(v.lupa.texto_esquina, p.accion.b_etapa.text())
        self.assertTrue(v.lupa.texto_esquina.startswith("Etapa "))
        self.assertFalse(p.accion.b_etapa.isVisible())
        c, p, v = self.contexto("transicion")
        self.assertEqual(v.lupa.texto_esquina, "")

    def test_SP812_la_transicion_es_una_tarjeta_receptividad_con_el_pie(self):
        """REQ-EDT-02, REQ-UX-01: en Transición, etiqueta inline en la barra de título, formulador plano a ancho completo y comentario al pie."""
        c, p, v = self.contexto("transicion")
        self.assertFalse(v.condicion.isVisible())
        self.assertEqual(v.titulo.text(), "Propiedades · Transición")
        self.assertTrue(v.accion.titulo.isHidden())
        self.assertTrue(v.subcabecera.isHidden())
        self.assertTrue(v.caja_etiqueta.isVisible())
        self.assertTrue(v.pie.isVisible())
        self.assertFalse(hasattr(p, "t_mostrar"), "E8: «Mostrar etiqueta» sale de la ventana (Ver > Etiquetas de transiciones)")
        self.assertTrue(p.t_etiqueta.isVisible())
        self.assertIs(p.t_etiqueta.parentWidget(), v.caja_etiqueta)
        self.assertTrue(p.t_comentario.isVisible())
        self.assertIs(p.t_comentario.parentWidget(), v.pie)
        self.assertGreater(v.pie.geometry().top(), v.columna.geometry().bottom())
        self.assertFalse(p.izq.isVisible())
        self.assertGreater(p.prog.width(), v.accion.width() // 2)  # el formulador, a todo el ancho del cuerpo
        # fuera de una transición, ni la etiqueta inline ni el pie de comentario están visibles
        c2, p2, v2 = self.contexto("etapa")
        self.assertFalse(v2.pie.isVisible())
        self.assertFalse(v2.caja_etiqueta.isVisible())

    def test_SP813_el_comentario_largo_no_cambia_el_tamano_de_la_ventana(self):
        """REQ-EDT-02, P-IMP-173: al crecer el comentario la ventana conserva su tamaño y es el formulador el que cede el alto."""
        c, p, v = self.contexto("transicion")
        tam, alto_prog = v.size(), p.prog.height()
        p.t_comentario.setText("texto largo " * 40)
        _bombear(8)
        self.assertEqual(v.size(), tam)
        self.assertGreater(p.t_comentario.height(), estilo.ALTO_CONTROL)
        self.assertLess(p.prog.height(), alto_prog)
        self.assertTrue(v.rect().contains(v.pie.geometry().translated(v.cuerpo.pos())))

    def test_SP814_intro_confirma_y_guarda_el_comentario_en_una_linea_y_esc_no(self):
        """REQ-UX-01, P-IMP-170: Intro en el comentario confirma y cierra; Mayús+Intro no escribe un salto; Esc deshace la sesión."""
        c, p, v = self.contexto("transicion")
        tid = c.ids["transiciones"][0]
        p.t_comentario.setFocus()
        _bombear()
        QTest.keyClicks(p.t_comentario, "paso uno")
        QTest.keyClick(p.t_comentario, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        QTest.keyClicks(p.t_comentario, " y dos")
        self.assertEqual(p.t_comentario.text(), "paso uno y dos")
        QTest.keyClick(p.t_comentario, Qt.Key.Key_Return)
        _bombear(8)
        self.assertFalse(c.w._props_abiertas())
        self.assertEqual(c.e.comentario(tid), "paso uno y dos")
        self.assertNotIn("\n", c.e.comentario(tid))
        # Esc: lo escrito en la sesión no se guarda
        c.e.seleccionar([tid])
        c.w._abrir_opciones()
        _bombear(8)
        p = c.w.flot.panel
        p.t_comentario.setFocus()
        _bombear()
        QTest.keyClicks(p.t_comentario, " (borrador)")
        QTest.keyClick(c.w.flot.principal, Qt.Key.Key_Escape)
        _bombear(8)
        self.assertFalse(c.w._props_abiertas())
        self.assertEqual(c.e.comentario(tid), "paso uno y dos")

    def test_SP815_el_comentario_pegado_con_saltos_se_guarda_en_una_linea(self):
        """REQ-EDT-02: un salto pegado pasa a un espacio y lo guardado es una sola línea."""
        c, p, v = self.contexto("transicion")
        tid = c.ids["transiciones"][0]
        mime = QMimeData()
        mime.setText("linea1\nlinea2\r\nlinea3")
        p.t_comentario.setFocus()
        p.t_comentario.insertFromMimeData(mime)
        p.t_comentario.clearFocus()
        _bombear()
        self.assertEqual(c.e.comentario(tid), "linea1 linea2 linea3")
        c.w.flot.cerrar()
        _bombear()
        self.assertEqual(c.e.comentario(tid), "linea1 linea2 linea3")

    def test_SP816_ventana_fondo_tarjeta_gris_y_franja_blanca(self):
        """REQ-UX-01, REQ-EDT-02: en 2.0.1 la ventana, la cabecera, la lupa y el panel interior son blancos (`#ffffff`),
        sin tarjeta gris anidada ni barra lateral de color; el pie del diálogo va en `#f6f8fb`."""
        c, p, v = self.contexto("transicion")
        imagen = v.grab().toImage()
        dpr = imagen.devicePixelRatio()
        pixel = lambda x, y: imagen.pixelColor(round(x * dpr), round(y * dpr)).name()  # noqa: E731
        self.assertEqual(pixel(5, 5), estilo.SUPERFICIE)
        self.assertEqual(pixel(v.width() // 2, v.cabecera.geometry().center().y()), estilo.SUPERFICIE)
        lupa = v.cuerpo.mapTo(v, v.lupa.geometry().center())
        self.assertEqual(pixel(lupa.x() - v.lupa.width() // 2 + 6, lupa.y()), estilo.SUPERFICIE)
        base = v.accion.mapTo(v, QPoint(0, 0))
        self.assertEqual(pixel(base.x() + 2, base.y() + v.accion.height() // 2), estilo.SUPERFICIE)
        pie_d = v.pie_dialogo.geometry()
        self.assertEqual(pixel(pie_d.left() + 6, pie_d.center().y()), "#f6f8fb")

    def test_SP817_botones_aceptar_y_cancelar_en_ventana_flotante(self):
        """REQ-UX-01, P-IMP-170: «Aceptar» confirma y cierra la sesión; «Cancelar» deshace los cambios y cierra."""
        c, p, v = self.contexto("transicion")
        tid = c.ids["transiciones"][0]
        self.assertTrue(v.b_aceptar.isVisible() and v.b_cancelar.isVisible())
        p._desde_bloques("paro")
        self.assertEqual(c.e.texto_usuario(tid), "paro")
        v.b_aceptar.click()
        _bombear(8)
        self.assertFalse(c.w._props_abiertas())
        self.assertEqual(c.e.texto_usuario(tid), "paro")
        # Nueva apertura: un cambio descartado con «Cancelar» vuelve al estado previo a abrir
        c.e.seleccionar([tid])
        c.w._abrir_opciones()
        _bombear(8)
        p = c.w.flot.panel
        p._desde_bloques("marcha AND paro")
        self.assertEqual(c.e.texto_usuario(tid), "marcha AND paro")
        c.w.flot.principal.b_cancelar.click()
        _bombear(8)
        self.assertFalse(c.w._props_abiertas())
        self.assertEqual(c.e.texto_usuario(tid), "paro")


if __name__ == "__main__":
    unittest.main()
