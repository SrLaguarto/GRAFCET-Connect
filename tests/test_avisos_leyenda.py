"""Leyenda con miniaturas, alto mínimo del panel de una transición, avisos entendibles y recentrado al redimensionar."""
import unittest
from unittest import mock

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtGui import QPixmap
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from escritorio import leyenda
    from escritorio.alto_opciones import alto_minimo_transicion
from escritorio.mensajes import amable, motivo_parada, partir
from escritorio.recentrado import RETARDO_MS

SECCIONES = ("Etapas", "Transiciones", "Acciones", "Jerarquía y forzado", "Temporizadores", "Ratón y teclado")


class Mensajes(unittest.TestCase):
    def test_SAVI01_parada_por_bucle_se_traduce_sin_jerga(self):
        """REQ-EDT-09, REQ-SIM-08: el presupuesto agotado se cuenta como «no se queda quieto», sin τ ni presupuesto."""
        crudo = "presupuesto de 10000 evoluciones agotado; situación no estabilizada; τ sin cambios"
        texto = amable(crudo, "D-LIM-EVOL")
        for jerga in ("presupuesto", "τ", "estabilizada", "evoluciones"):
            self.assertNotIn(jerga, texto)
        self.assertIn("no alcanza una situación estable", texto)

    def test_SAVI02_bucle_nombra_las_transiciones_y_etapas_que_se_repiten(self):
        """REQ-SIM-08: el motivo de parada nombra con sus nombres visibles las transiciones del bucle y deja el detalle
        técnico solo en la ayuda emergente."""
        nombres = {"id-t1": "t1", "id-t2": "t2", "s1": "1", "s2": "2"}
        evoluciones = [{"evolutionIndex": 9, "cleared": ["id-t1"], "situation": ["s1"]},
                       {"evolutionIndex": 10, "cleared": ["id-t2"], "situation": ["s2"]}]
        motivos = motivo_parada("D-LIM-EVOL", "presupuesto de 10000 evoluciones agotado", evoluciones, nombres)
        textos = [t for t, _ in motivos]
        self.assertIn("Simulación detenida: el grafcet no alcanza una situación estable.", textos)
        causa = next(t for t in textos if "t1 y t2" in t)
        self.assertIn("sus receptividades son ciertas a la vez", causa)
        self.assertIn("en ciclo sin fin", causa)
        for texto in textos:
            self.assertLessEqual(len(texto), 130)
            self.assertNotIn("id-t1", texto)
            self.assertNotIn("Evolución", texto)
        self.assertTrue(all("Detalle técnico" in ayuda for _, ayuda in motivos))

    def test_SAVI03_motivos_frecuentes_en_lenguaje_llano(self):
        """REQ-EDT-09: los diagnósticos más frecuentes se muestran sin referencias internas ni jerga."""
        casos = {
            "grafcet sin etapas iniciales: no se admite (lectura 6.1 A)": "Falta una etapa inicial",
            "conflicto de escritura seguro sobre Q: a y b escriben a la vez en la misma etapa; el programa no puede "
            "compilarse": "Dos acciones dan valores distintos a Q",
            "etiqueta «1» repetida en el parcial g": "Ya existe otra etapa llamada «1»",
            "A→B une dos elementos del mismo tipo; se guarda como borrador no ejecutable": "solo se unen una etapa",
            "contexto abandonado tras el límite": "no alcanzaba una situación estable",
        }
        for crudo, esperado in casos.items():
            texto = amable(crudo)
            self.assertIn(esperado, texto)
            self.assertNotIn("lectura", texto)
            self.assertNotIn("compilarse", texto)

    def test_SAVI04_aviso_largo_se_parte_en_frase_corta_y_ayuda(self):
        """REQ-EDT-09: un aviso largo deja una frase corta en la lista y el texto completo para la ayuda emergente."""
        largo = "Primera frase corta. " + "y mucho más texto " * 12
        principal, completo = partir(largo)
        self.assertEqual(principal, "Primera frase corta.")
        self.assertEqual(completo, largo)
        self.assertEqual(partir("Corto."), ("Corto.", ""))


@unittest.skipUnless(QT, "requiere PySide6")
class Interfaz(BaseQt):
    def test_SLEY01_leyenda_tiene_secciones_y_miniaturas_dibujadas_con_el_diagrama(self):
        """REQ-EDT-02: cada entrada con imagen lleva una miniatura dibujada con diagrama.dibujar; hay seis secciones y la
        ventana no es modal."""
        self.assertEqual(tuple(t for t, _ in leyenda.SECCIONES), SECCIONES)
        for _, entradas in leyenda.SECCIONES:
            for entrada in entradas:
                if entrada.miniatura is None:
                    continue
                pm = leyenda.dibujo(entrada)
                self.assertIsInstance(pm, QPixmap, entrada.titulo)
                self.assertFalse(pm.isNull(), entrada.titulo)
        self.w.leyenda()
        d = self.w._leyenda
        self.assertIsInstance(d, leyenda.Leyenda)
        self.assertTrue(d.isVisible() and not d.isModal())
        textos = " ".join(x.text() for x in d.findChildren(QLabel))
        self.assertIn("Etapa activa", textos)
        self.assertIn("Mostrar dependencias", textos)
        d.close()

    def test_SLEY02_la_leyenda_nombra_el_boton_de_dependencias_y_no_habla_de_la_navegacion_antigua(self):
        """REQ-EDT-02, REQ-JER-04, REQ-JER-05: explica que los trazos macroetapa-expansión y encapsulante-recinto solo se
        ven con «Mostrar dependencias»."""
        todo = " ".join(leyenda.textos())
        self.assertIn("«Mostrar dependencias»", todo)
        self.assertIn("macroetapa y expansión", todo)
        self.assertIn("encapsulante y recinto", todo)
        for viejo in ("Abrir expansión", "Ir a la macroetapa"):
            self.assertNotIn(viejo, todo)

    def _transicion_seleccionada(self):
        w, e = self.vacio()
        self.addCleanup(w.hide)
        w.resize(1366, 768)
        w.show()
        ids = self.cadena(e)
        e.seleccionar([ids[1]])
        w._abrir_opciones()
        QApplication.processEvents()
        QApplication.processEvents()
        return w, e, ids

    def test_SALT01_panel_de_transicion_enseña_todos_los_operadores_sin_barra(self):
        """REQ-EDT-09: al seleccionar una transición el panel inferior mide al menos lo justo para ver la paleta de
        operadores sin barra de desplazamiento; si es menor, se agranda."""
        w, e, ids = self._transicion_seleccionada()
        self.assertEqual(w.props.pagina, "transicion")
        self.assertGreaterEqual(w.vsplit.sizes()[1], alto_minimo_transicion(w.props), "al abrirlo ya cabe")
        total = sum(w.vsplit.sizes())
        w.vsplit.setSizes([total - 90, 90])  # el usuario lo deja pequeño con el divisor
        w.vsplit.splitterMoved.emit(total - 90, 1)
        e.seleccionar([ids[0]])
        QApplication.processEvents()
        e.seleccionar([ids[1]])
        QApplication.processEvents()
        QApplication.processEvents()
        self.assertGreaterEqual(w.vsplit.sizes()[1], alto_minimo_transicion(w.props))
        w.props.prog.elegir_categoria("operador")
        QApplication.processEvents()
        barra = w.props.prog._sc_paleta.verticalScrollBar()
        self.assertEqual(barra.maximum(), 0, "la paleta de operadores se ve entera")
        self.assertTrue(w.props.caja_formula.isVisible())

    def test_SALT02_un_panel_mayor_que_el_minimo_se_respeta(self):
        """REQ-EDT-09: si el usuario hace el panel más grande que el mínimo, seleccionar una transición no lo cambia."""
        w, e, ids = self._transicion_seleccionada()
        e.seleccionar([ids[0]])
        QApplication.processEvents()
        total = sum(w.vsplit.sizes())
        grande = alto_minimo_transicion(w.props) + 60
        w.vsplit.setSizes([total - grande, grande])
        w.vsplit.splitterMoved.emit(total - grande, 1)
        e.seleccionar([ids[1]])
        QApplication.processEvents()
        QApplication.processEvents()
        self.assertEqual(w.vsplit.sizes()[1], grande)

    def test_SRCT01_cambiar_el_tamaño_de_la_ventana_recentra_tras_el_retardo(self):
        """REQ-EDT-09: al redimensionar la ventana, un temporizador de disparo único llama a «Centrar todo»; plegar un
        panel no lo dispara."""
        w, e = self.vacio()
        self.addCleanup(w.hide)
        w.resize(1200, 700)
        w.show()
        QApplication.processEvents()
        w.recentrado.temporizador.stop()
        self.assertTrue(w.recentrado.temporizador.isSingleShot())
        self.assertEqual(w.recentrado.temporizador.interval(), RETARDO_MS)
        w._mostrar_panel("derecho", False)
        QApplication.processEvents()
        self.assertFalse(w.recentrado.temporizador.isActive(), "plegar un panel no recentra")
        w.resize(900, 600)
        QApplication.processEvents()
        self.assertTrue(w.recentrado.temporizador.isActive())
        with mock.patch.object(w.diagrama, "ajustar") as ajustar:
            QTest.qWait(RETARDO_MS + 150)
            self.assertEqual(ajustar.call_count, 1)


if __name__ == "__main__":
    unittest.main()
