"""SESC40..SESC42: el filtro de parcial sobre la escena incremental y la reserva de textos de la simulación (V2-E3, paso 5)."""
from importlib.util import find_spec
from unittest import TestCase, mock, skipUnless

QT = bool(find_spec("PySide6"))


@skipUnless(QT, "requiere PySide6")
class NavegacionYEscena(TestCase):
    def setUp(self):
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        self.contexto = ventana()
        self.w = self.contexto.__enter__()
        self.addCleanup(self.contexto.__exit__, None, None, None)
        reiniciar(self.w, GEMMA)
        self.e, self.d = self.w.edicion, self.w.diagrama
        self.sc = self.d.scene()

    def test_SESC40_sin_filtro_mostrar_no_recorre_la_escena_para_filtrar(self):
        """REQ-EDT-02: sin filtro de parcial, redibujar no recorre todos los ítems de la escena (nada que ocultar ni atenuar)."""
        with mock.patch.object(self.sc, "items", wraps=self.sc.items) as items:
            self.d.mostrar(*self.d._ultimo)
        self.assertEqual(items.call_count, 0)

    def test_SESC41_el_filtro_se_aplica_y_se_retira_del_todo_aunque_se_redibuje_entre_medias(self):
        """REQ-EDT-02: con el filtro puesto, los ítems de otros parciales se ocultan o atenúan también tras redibujar; al quitarlo
        vuelven a verse todos, y la escena queda como el dibujo directo."""
        from tools import choque_escena as c
        nav = self.w.navegacion
        self.assertGreater(nav.parcial.count(), 2, "GEMMA tiene varios parciales")
        for modo in range(nav.modo.count()):
            nav.modo.setCurrentIndex(modo)
            nav.parcial.setCurrentIndex(2)
            self.d.mostrar(*self.d._ultimo)
            c.comprobar(self.w, momento=f"con el filtro, modo {modo}")
            self.assertTrue(any(not i.isVisible() or i.opacity() < 1 for i in self.sc.items()), "el filtro debe notarse")
            nav.parcial.setCurrentIndex(0)
            self.d.mostrar(*self.d._ultimo)
            c.comprobar(self.w, momento=f"sin el filtro, modo {modo}")
            self.assertTrue(all(i.isVisible() and i.opacity() == 1 for i in self.sc.items()))

    def test_SESC42_un_texto_reutilizado_por_la_simulacion_no_conserva_ocultacion_ni_opacidad(self):
        """REQ-SIM-01: la reserva de textos devuelve ítems visibles y opacos aunque quedaran ocultos o atenuados (H3)."""
        from PySide6.QtGui import QColor, QFont
        from escritorio.textos_diagrama import EscenaDiagrama
        sc = EscenaDiagrama(None)
        sc.comenzar_dibujo()
        t = sc.texto("hola", QColor("black"), QFont("Arial"))
        sc.addItem(t)
        t.setVisible(False)
        t.setOpacity(0.18)
        sc.comenzar_dibujo()
        reutilizado = sc.texto("hola", QColor("black"), QFont("Arial"))
        self.assertIs(reutilizado, t)
        self.assertTrue(reutilizado.isVisible() or reutilizado.scene() is None)
        self.assertEqual(reutilizado.opacity(), 1.0)
        sc.addItem(reutilizado)
        self.assertTrue(reutilizado.isVisible())
        sc.terminar_dibujo()
