"""SPF1: remates de Propiedades para 1.1.1 (REQ-EDT-02, REQ-EDT-09, REQ-JER-07)."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # (para poder ejecutarla suelta, como las demás)

try:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget
    QT = True
except ImportError:
    QT = False

if QT:
    from tools import hoja_contactos as HC
    from escritorio import estilo
    from escritorio.acciones import ANCHO_MAX_VARIABLE
    from escritorio.flotantes import ALFA_RESALTADO, SENAL_ACCION, SENAL_CONDICION
    from escritorio.propiedades import AYUDAS


@unittest.skipUnless(QT, "requiere PySide6")
class Propiedades111(unittest.TestCase):
    def contexto(self, tipo="evento", ancho=1366, alto=768):
        HC.aplicacion()
        c = HC.Contexto(ancho, alto)
        self.addCleanup(c.cerrar)
        HC._flotante(tipo)(c)
        return c, c.w.flot.panel, c.w.flot.principal

    def test_SPF101_modal_bloquea_dibujo_y_barras_y_cierra(self):
        """REQ-EDT-02: modal de la principal, fondo sin interacción; Esc y cruz cierran."""
        c, p, v = self.contexto("etapa")
        self.assertIs(QApplication.activeModalWidget(), v)
        self.assertEqual(v.windowModality(), Qt.WindowModality.WindowModal)
        antes = list(c.e.sel)
        modo = c.w.modo
        QTest.mouseClick(c.w.diagrama.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        QTest.mouseClick(c.w.tb_sim.widgetForAction(c.w.a_ejecutar), Qt.MouseButton.LeftButton)
        HC._bombear(4)
        self.assertEqual(c.e.sel, antes)
        self.assertEqual(c.w.modo, modo)
        QTest.keyClick(p.s_etiqueta, Qt.Key.Key_Escape)
        HC._bombear(4)
        self.assertFalse(v.isVisible())
        c.w._abrir_opciones()
        HC._bombear(4)
        QTest.mouseClick(v.b_cerrar, Qt.MouseButton.LeftButton)
        HC._bombear(4)
        self.assertFalse(v.isVisible())
        self.assertIsNone(QApplication.activeModalWidget())

    def test_SPF102_transicion_alto_limitado_y_lupa_igual(self):
        """REQ-EDT-09: contenido acotado, centrado y lupa de la altura de su tarjeta."""
        alturas = []
        for ancho, alto in ((1366, 768), (2000, 1250)):
            c, p, v = self.contexto("transicion", ancho, alto)
            f = c.w.flot
            filas = 11 if estilo.ESCALA == "grande" else 9
            necesario = max(p.minimumSizeHint().height(), (filas + 2) * estilo.ALTO_CONTROL)
            tope = necesario + f._marco_ventana() + f._marco_tarjeta()
            self.assertLessEqual(v.height(), tope)
            self.assertLess(v.height(), f._area().height() - 2 * estilo.E6)
            self.assertEqual(v.lupa.height(), v.accion.height())
            centro = v.lupa.transformar().map(v.lupa.origen.center())
            self.assertLessEqual(abs(centro.y() - v.lupa.height() / 2), 1)
            alturas.append(v.height())
        self.assertGreater(alturas[1], alturas[0])

    def test_SPF103_sin_variable_fichas_deshabilitadas_y_numerica_solo_con_tipo(self):
        """REQ-EDT-02: sin variable, 1/0 inertes; numérica solo después de elegirla, abajo y flotante."""
        for flotante in (True, False):
            c, p, v = self.contexto()
            if not flotante:
                c.w._cambiar_modo_propiedades("abajo")
                HC._bombear(4)
                p = c.w.props
            aid = p.accion.aid
            d = c.e.datos_accion(aid)
            d["variable"], d["valor"] = "", ""
            self.assertIsNone(c.e.cambiar_accion(aid, d))
            HC._bombear(6)
            a = p.accion
            self.assertTrue(a.caja_fichas.isVisible())
            self.assertFalse(a.caja_numerica.isVisible())
            self.assertEqual(a.l_fichas.text(), "? :=")
            for boton in a.fichas.values():
                self.assertFalse(boton.isEnabled())
                self.assertIn("primero", boton.toolTip())
            c.e.nueva_variable("cuenta", "internal", {"kind": "int"})
            a.poner_variable("cuenta")
            HC._bombear(6)
            self.assertTrue(a.caja_numerica.isVisible())
            self.assertFalse(a.caja_fichas.isVisible())
            a.poner_variable("aux")
            HC._bombear(6)
            self.assertFalse(a.caja_numerica.isVisible())
            self.assertTrue(all(b.isEnabled() for b in a.fichas.values()))

    def test_SPF104_selector_mide_opciones_y_elide_con_ayuda(self):
        """REQ-EDT-02: caja y lista iguales si caben; tope y ayuda para nombre largo."""
        c, p, v = self.contexto()
        c.e.nueva_variable("Cinta6M1", "output")
        p.accion.poner_variable("Cinta6M1")
        HC._bombear(8)
        combo = p.accion.variable
        self.assertEqual(combo.width(), combo.ancho_lista())
        combo.showPopup()
        HC._bombear(4)
        self.assertEqual(combo.view().window().width(), combo.width())
        combo.hidePopup()
        _, rect = combo.rectangulo_texto()
        self.assertLessEqual(combo.fontMetrics().horizontalAdvance("Cinta6M1"), rect.width())
        anterior = combo.width()
        combo.setStyleSheet(combo.styleSheet() +
                           f"QComboBox#selectorVariableAccion {{ font-size: {estilo.T_BASE + 3}px; }}")
        HC._bombear(4)
        self.assertGreater(combo.width(), anterior)
        largo = "Salida_con_un_nombre_muy_largo_para_comprobar_la_ayuda_completa"
        c.e.nueva_variable(largo, "output")
        p.accion.poner_variable(largo)
        HC._bombear(8)
        self.assertEqual(combo.width(), ANCHO_MAX_VARIABLE)
        combo.grab()
        self.assertEqual(combo.toolTip(), largo)
        _, rect = combo.rectangulo_texto()
        texto = combo.fontMetrics().elidedText(largo, Qt.TextElideMode.ElideRight, rect.width())
        self.assertIn("…", texto)
        self.assertGreater(combo.ancho_lista(), combo.width())

    def macro(self, antiguos=False):
        c, p, v = self.contexto("etapa")
        c.w._mostrar_panel("inferior", False)
        mid = c.e.poner_macro(QPointF(600, 200))
        info = c.e.ed.macro_info(mid)
        if antiguos:
            c.e.ed.rename(info.entry, "EntradaAntigua")
            c.e.ed.rename(info.exit, "SalidaAntigua")
            c.e.reconstruir()
        c.e.seleccionar([mid])
        c.w._abrir_opciones()
        HC._bombear(6)
        return c, c.w.flot.panel, mid, info

    def test_SPF105_macro_renombra_entrada_salida_expansion_y_deshace(self):
        """REQ-JER-07, REQ-EDT-02: etiqueta editable, arrastre de E/S y expansión; un único deshacer."""
        c, p, mid, info = self.macro()
        antes = copy.deepcopy(c.e.ed.model)
        numero = len(c.e.ed.undo_stack)
        p.m_etiqueta.setText("M13")
        p.m_etiqueta.editingFinished.emit()
        HC._bombear(6)
        self.assertEqual([c.e.nombres[i] for i in (mid, info.entry, info.exit, info.partial)],
                         ["M13", "E13", "S13", "M13"])
        self.assertEqual(len(c.e.ed.undo_stack), numero + 1)
        c.e.deshacer()
        self.assertEqual(c.e.ed.model, antes)
        c.e.rehacer()
        self.assertEqual(c.e.nombres[info.entry], "E13")
        for sid in (info.entry, info.exit):
            c.e.seleccionar([sid])
            HC._bombear(4)
            self.assertTrue(p.s_etiqueta.isReadOnly())
            self.assertEqual(p.s_etiqueta.toolTip(), "Sigue el nombre de la macroetapa M13")

    def test_SPF106_macro_choque_atomico_y_nombres_antiguos(self):
        """REQ-JER-07: colisión rechazada sin cambios ni historial; nombres antiguos conservados."""
        c, p, mid, info = self.macro()
        c.e.ed.add_step(info.partial, "E13")
        c.e.reconstruir()
        antes = copy.deepcopy(c.e.ed.model)
        numero = len(c.e.ed.undo_stack)
        motivo = c.e.cambiar_nombre_macro(mid, "M13")
        self.assertIn("E13", motivo)
        self.assertEqual(c.e.ed.model, antes)
        self.assertEqual(len(c.e.ed.undo_stack), numero)
        otro, panel, macro, datos = self.macro(antiguos=True)
        self.assertIsNone(otro.e.cambiar_nombre_macro(macro, "M13"))
        self.assertEqual([otro.e.nombres[i] for i in (datos.entry, datos.exit)], ["EntradaAntigua", "SalidaAntigua"])

    def test_SPF107_senales_sin_lineas_y_colores_compartidos(self):
        """REQ-EDT-09: dos resaltados suaves y franjas/títulos con la misma señal, sin capa de líneas."""
        for tipo in ("condicionada", "evento"):
            c, p, v = self.contexto(tipo)
            self.assertFalse(v.findChildren(QWidget, "enlacesFlotantes"))
            self.assertEqual([color for _, color in v.lupa.senales], [SENAL_CONDICION, SENAL_ACCION])
            self.assertGreaterEqual(ALFA_RESALTADO, .15)
            self.assertLessEqual(ALFA_RESALTADO, .20)
            for tarjeta, color in ((v.condicion, SENAL_CONDICION), (v.accion, SENAL_ACCION)):
                self.assertEqual(tarjeta.titulo.senal, color)
                imagen = tarjeta.grab().toImage()
                self.assertEqual(imagen.pixelColor(2, tarjeta.height() // 2).name(), color)

    def test_SPF108_ayudas_sin_descripciones_de_forma_ni_propiedades(self):
        """REQ-EDT-02: instrucciones directas, sin alternativas ni descripciones visuales redundantes."""
        self.assertNotIn("alternativas", AYUDAS["simultaneidad"].lower())
        for clave in ("macroetapa", "encapsulante", "parcial", "forzado"):
            self.assertFalse(AYUDAS[clave].partition(":")[0].count("("))
        for clave, texto in AYUDAS.items():
            if clave.startswith("accion:"):
                self.assertIn("configúrela con doble clic.", texto)
                self.assertNotIn("en Propiedades", texto)

    def test_SPF109_ocultar_principal_cierra_modal_y_mover_la_recoloca(self):
        """REQ-EDT-02: la modal sigue a su propietaria y no queda huérfana al ocultarla."""
        c, p, v = self.contexto("transicion")
        c.w.move(c.w.pos() + QPoint(20, 30))
        HC._bombear(4)
        self.assertLessEqual(abs(v.geometry().center().x() - c.w.flot._area().center().x()), 1)
        c.w.hide()
        HC._bombear(4)
        self.assertFalse(v.isVisible())
        self.assertFalse(c.w.flot._vigilando)
        self.assertIsNone(QApplication.activeModalWidget())

    def test_SPF110_auditoria_de_las_raices_modales_sin_excepciones_nuevas(self):
        """REQ-EDT-09: las mismas reglas de auditoría también se aplican a la raíz modal nativa."""
        from test_auditoria_maquetacion import REGLAS, permitida
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            for tipo in ("transicion", "condicionada", "evento"):
                c, p, v = self.contexto(tipo, ancho, alto)
                for regla, comprobar in REGLAS.items():
                    if regla in ("B1", "B2"):
                        continue
                    hallazgos = [h for h in comprobar(v) if not permitida(regla, h)]
                    self.assertEqual(hallazgos, [], (ancho, alto, tipo, regla))
                c.w._mostrar_panel("inferior", False)
