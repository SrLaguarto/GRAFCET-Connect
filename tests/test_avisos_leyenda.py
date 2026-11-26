"""Leyenda con miniaturas, alto mínimo del panel de una transición, avisos entendibles y dibujo anclado al redimensionar."""
import unittest
from unittest import mock

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtGui import QPixmap
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from escritorio import leyenda
from escritorio.mensajes import amable, motivo_parada, partir

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



    def test_SRCT01_cambiar_el_tamaño_de_la_ventana_no_recentra_y_ancla_al_area_cliente(self):
        """REQ-EDT-09: al redimensionar conserva zoom y coordenadas respecto al área cliente de la ventana.
        Incluye el cambio de ancho de los paneles y el modo compacto, sin recentrado diferido."""
        from PySide6.QtCore import QPointF
        w, e = self.vacio()
        self.cadena(e)
        self.addCleanup(w.hide)
        w.resize(1200, 700)
        w.show()
        for _ in range(6):
            QApplication.processEvents()
        d = w.diagrama
        self.assertFalse(hasattr(w, "recentrado"), "ya no hay temporizador de recentrado")
        d.zoom(1.37)
        d.horizontalScrollBar().setValue(d.horizontalScrollBar().value() + 40)
        for _ in range(4):
            QApplication.processEvents()
        antes = (d.escala(), d.viewport().mapTo(w, d.mapFromScene(QPointF())))
        for ancho, alto in ((1500, 900), (900, 600), (1100, 650)):
            w.resize(ancho, alto)
            for _ in range(6):
                QApplication.processEvents()
            QTest.qWait(300)
            self.assertAlmostEqual(d.escala(), antes[0], places=6, msg=(ancho, alto, "mismo zoom"))
            punto = d.viewport().mapTo(w, d.mapFromScene(QPointF()))
            self.assertEqual(punto, antes[1], (ancho, alto, punto, antes[1]))
        w._mostrar_panel("derecho", False)
        for _ in range(6):
            QApplication.processEvents()
        QTest.qWait(300)
        self.assertAlmostEqual(d.escala(), antes[0], places=6, msg="plegar un panel tampoco cambia el zoom")
        d.ajustar()
        self.assertNotAlmostEqual(d.escala(), antes[0], places=3, msg="«Centrar todo» sigue encajando")


    def test_SAVI20_la_ventana_cuenta_los_vencimientos_simultaneos_con_etiquetas(self):
        """REQ-TMP-02, REQ-UX-01: el diagnóstico de vencimientos simultáneos llega a la pantalla nombrando las transiciones y sin proponer
        Ajustes de simulación."""
        from types import SimpleNamespace
        from grafcet.builder import M
        from grafcet.view import display_names
        w, e = self.vacio()
        m = M().step("E0", True).step("E1").step("E2")
        m.trans("t1", ["E0"], ["E1"], "delay(2 s, active(E0), 0 s)").trans("t2", ["E0"], ["E2"], "delay(2 s, active(E0), 0 s)")
        w.v = SimpleNamespace(doc=m.doc, names=display_names(m.doc))
        crudo = {"code": "D-SEM-PENDIENTE", "correction": "Cerrar la cuestión indicada",
                 "message": "vencimientos simultáneos cuyo resultado depende del orden (e2, e1 frente a e1, e2; grupo e1, e2) [temporal.coincidencias]",
                 "evidence": {"capacidad": "temporal.coincidencias", "claves": "e1, e2"}}
        d = w._diag_llano(crudo)
        self.assertTrue(d["message"].startswith("Las transiciones t1 y t2 (tras X0)"), d["message"])
        self.assertNotIn("Ajustes de simulación", d["message"] + d["correction"])
        self.assertEqual(d["correction"], "Use tiempos distintos o evite que compitan por la misma etapa.")
        motivos = motivo_parada(d["code"], d["message"], [], w.v.names)
        self.assertIn("t1 y t2", motivos[0][0])
        w.v = None
        self.assertIs(w._diag_llano(crudo), crudo)


if __name__ == "__main__":
    unittest.main()
