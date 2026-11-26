"""Pruebas de aceptación de la tanda C3: Propiedades (#4), submenú/favoritos/buscador (#9), Navegación y ORIGEN_MEMORIA."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

try:
    from PySide6.QtCore import QPoint, QPointF, QSize, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio import estilo
    from escritorio.componentes_comunes import CabeceraDialogo
    from tools import hoja_contactos as HC
    QT = True
except ImportError:
    QT = False


def _contexto(test: unittest.TestCase, tipo: str = "etapa", ancho: int = 1366, alto: int = 768):
    HC.aplicacion()
    c = HC.Contexto(ancho, alto)
    test.addCleanup(c.cerrar)
    if tipo == "macroetapa":
        HC._edicion(c)
        mid = c.e.poner_macro(QPointF(500, 200))
        c.e.seleccionar([mid])
        c.w._abrir_opciones()
    else:
        HC._flotante(tipo)(c)
    HC._bombear(10)
    return c, c.w.flot.panel, c.w.flot.principal


@unittest.skipUnless(QT, "requiere PySide6")
class TestC3PropiedadesYRemates(unittest.TestCase):
    def test_C301_etapa_controles_320px_sin_scroll(self) -> None:
        """#4.1: en Etapa los controles miden 320 px y no aparece barra de scroll vertical innecesaria."""
        c, p, v = _contexto(self, "etapa", 1366, 768)
        for campo in (p.s_etiqueta, p.s_tipo, p.s_comentario, p.s_colocacion):
            self.assertEqual(campo.width(), 320)
        self.assertFalse(v.accion.scroll.verticalScrollBar().isVisible())
        self.assertFalse(p.der.isVisible())

    def test_C302_macroetapa_selector_tipo_y_tarjeta_compacta(self) -> None:
        """#4.2: Macroetapa sustituye las 3 casillas por el selector «Tipo», agrupa expansión y nota en tarjeta y oculta `der`."""
        c, p, v = _contexto(self, "macroetapa", 1366, 768)
        self.assertTrue(p.m_formulario.isVisible())
        self.assertTrue(p.m_tipo.isVisible())
        self.assertEqual(p.m_tipo.currentData(), "Macroetapa")
        for b_ocultar in ("Etapa", "Encapsulante", "Macroetapa", "Renombrar…"):
            self.assertTrue(p.ficha_izq.botones[b_ocultar].isHidden(), b_ocultar)
        self.assertTrue(p.ficha_izq.botones["Encuadrar la expansión"].isVisible())
        self.assertTrue(p.ficha_izq.nota.isVisible())
        self.assertTrue(p.tarjeta_macro.isVisible())
        self.assertTrue(p.tarjeta_macro.property("tarjeta"))
        self.assertFalse(p.der.isVisible())

        # Cambiar tipo desde `m_tipo` convierte a etapa con deshacer.
        mid = p.ident
        n_undo = len(c.e.ed.undo_stack)
        idx_etapa = p.m_tipo.findData("Etapa")
        p.m_tipo.setCurrentIndex(idx_etapa)
        p.m_tipo.activated.emit(idx_etapa)
        HC._bombear(4)
        self.assertTrue(any(s["id"] == mid for s in c.e.ed.model["steps"]))
        self.assertGreater(len(c.e.ed.undo_stack), n_undo)
        c.e.deshacer()
        self.assertTrue(any(x["id"] == mid for x in c.e.ed.model["hierarchy"]["macros"]))

    def test_C303_accion_booleana_alto_ajustado_y_sin_pastilla_duplicada(self) -> None:
        """#4.3: acción booleana al activar/desactivar reduce el alto al contenido y no duplica la pastilla de variable."""
        for tipo in ("activacion", "desactivacion"):
            with self.subTest(tipo=tipo):
                c, p, v = _contexto(self, tipo, 1366, 768)
                self.assertLessEqual(v.height(), 360)
                self.assertFalse(v.accion.scroll.verticalScrollBar().isVisible())
                self.assertTrue(p.accion.l_var_bool.isHidden())
                self.assertTrue(v.caja_dest.isVisible())
                self.doCleanups()

        # En escala grande también se mantiene compacta y sin barra de desplazamiento.
        c, p, v = _contexto(self, "activacion", 1920, 1080)
        self.assertLess(v.height(), 460)
        self.assertFalse(v.accion.scroll.verticalScrollBar().isVisible())
        self.doCleanups()

        c, p, v = _contexto(self, "activacion_numerica", 1366, 768)
        self.assertGreater(v.height(), 460)

    def test_C304_submenu_tipo_accion_iconos_20px_y_origen_memoria_unificado(self) -> None:
        """#9.1 y C3: ORIGEN_MEMORIA coincide con PAPEL_MEMORIA y «Tipo de acción» usa iconos nativos de 20×20 px."""
        self.assertEqual(estilo.ORIGEN_MEMORIA, estilo.PAPEL_MEMORIA)
        self.assertEqual(estilo.ORIGEN_MEMORIA, "#6d28d9")

        HC.aplicacion()
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        HC._edicion(c)
        c.e.nueva_variable("Q0", "output")
        sid = c.ids["etapas"][0]
        c.e.poner_accion(sid, {"tipo": "continua", "variable": "Q0"})
        aid = c.e.ed.model["actions"][0]["id"]
        caja = c.e.accion_en_id(aid)
        x, y, w_c, h_c = caja["rect"]
        opciones = dict(c.e.menu(QPointF(x + w_c / 2, y + h_c / 2)))
        sub = opciones["Tipo de acción"]
        self.assertEqual(len(sub), 6)
        for texto, _fn, icono in sub:
            self.assertFalse(icono.isNull(), texto)
            self.assertEqual(icono.actualSize(QSize(20, 20)), QSize(20, 20), texto)
            self.assertEqual(icono.availableSizes(), [QSize(40, 40)], texto)
            self.assertEqual(icono.pixmap(QSize(20, 20), 2.0).devicePixelRatio(), 2.0, texto)

    def test_C305_favoritos_agrupados_con_tres_separadores(self) -> None:
        """#9.2: la barra de favoritos muestra 3 separadores entre los 4 grupos y cabe completa a 960×1032."""
        for ancho, alto in ((1366, 768), (960, 1032)):
            with self.subTest(ancho=ancho, alto=alto):
                c, _, _ = _contexto(self, "etapa", ancho, alto)
                barra = c.w.favoritos
                self.assertFalse(barra.ocultos)
                self.assertEqual(len(barra._separadores), 3)
                # Los 3 separadores caen entre grupos: tras el 4.º, 10.º y 13.º botón.
                limites = (barra.orden[3], barra.orden[9], barra.orden[12])
                siguientes = (barra.orden[4], barra.orden[10], barra.orden[13])
                for x_sep, prev_c, sig_c in zip(barra._separadores, limites, siguientes):
                    r_prev = barra.botones[prev_c].geometry()
                    r_sig = barra.botones[sig_c].geometry()
                    self.assertGreater(x_sep, r_prev.right())
                    self.assertLess(x_sep, r_sig.left())
                self.doCleanups()

    def test_C306_buscador_compacto_lupa_sin_resultados_y_cabecera_navegacion(self) -> None:
        """#9.3 y C5: buscador Ctrl+F sin hueco, icono de lupa, «Sin resultados» en ámbar y cabecera en Navegación."""
        c, _, _ = _contexto(self, "etapa", 1366, 768)
        w = c.w
        w.flot.cerrar()
        nav = w.navegacion
        nav.abrir()
        HC._bombear(4)
        self.assertTrue(nav.isVisible())
        self.assertGreaterEqual(len(nav.buscar.actions()), 1)
        self.assertTrue(nav.contador.isHidden())

        QTest.keyClicks(nav.buscar, "no-existe-elemento")
        HC._bombear(2)
        self.assertTrue(nav.contador.isVisible())
        self.assertEqual(nav.contador.text(), "Sin resultados")
        self.assertIn(estilo.AVISO_FONDO, nav.contador.styleSheet())
        hueco = nav.anterior.x() - nav.contador.geometry().right() - 1
        self.assertLessEqual(hueco, 12)

        cab = nav.opciones.findChild(CabeceraDialogo)
        self.assertIsNotNone(cab)
        nav.abrir_opciones()
        HC._bombear(2)
        self.assertTrue(nav.opciones.isVisible())
        self.assertTrue(cab.isVisible())
        cab.cerrar_pedido.emit()
        HC._bombear(2)
        self.assertFalse(nav.opciones.isVisible())


if __name__ == "__main__":
    unittest.main()
