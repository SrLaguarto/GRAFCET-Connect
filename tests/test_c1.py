"""Pruebas de la tanda C1: consola de simulación, cápsula del temporizador, traza en GRAFCET español y avisos."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(1, str(ROOT / "tests"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from test_editor_cadenas import BaseQt, QT  # noqa: E402

if QT:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QApplication, QGraphicsScene
    from grafcet.builder import M
    from grafcet.profile import normalize_options
    from grafcet.view import Vista, display_names
    from escritorio import estilo, leyenda
    from escritorio.diagrama import COL, dibujar, dibujar_directo
    from escritorio.mensajes import motivo_parada, vencimientos_en_palabras
    from escritorio.traza_panel import DelegadoTraza, formatear_texto_traza
    from escritorio.ventana.simulacion import ROL_BOOLEANO_CONSOLA, ROL_PAPEL_CONSOLA


@unittest.skipUnless(QT, "Falta PySide6")
class TestC1SimulacionTrazaYAvisos(BaseQt):
    def test_C101_consola_pastillas_0_1_barra_papel_etapas_y_margen_10px(self) -> None:
        """#1.1 y #1.2: entradas y tabla usan `0`/`1`, barra semántica de papel, columna `Etapas` con chips `X`, y 10 px de margen."""
        w, e = self.vacio()
        v_marcha = e.ed.add_variable("marcha", "input", {"kind": "bool"})
        v_motor = e.ed.add_variable("motor", "output", {"kind": "bool"})
        v_mem_b = e.ed.add_variable("mem_b", "internal", {"kind": "bool"})
        v_cuenta = e.ed.add_variable("cuenta", "internal", {"kind": "int"})
        s0 = e.ed.add_step("g", "0", True, at=(120, 80))
        s1 = e.ed.add_step("g", "1", at=(120, 220))
        t1, _ = e.ed.add_transition("g", "marcha", [s0], [s1], at=(120, 150))
        del t1
        e.ed.add_continuous_action(s1, v_motor)
        e.ed.add_stored_action(s1, v_mem_b, "activation", "true")
        e.ed.add_stored_action(s1, v_cuenta, "activation", "5")
        e.cambia()
        self.assertEqual(e.diagnosticos(), [])

        w.resize(1366, 768)
        w.show()
        self.addCleanup(w.hide)
        self.assertTrue(w.cambiar_modo("simular"))
        QApplication.processEvents()

        m_lado = w.lado.contentsMargins()
        self.assertEqual((m_lado.left(), m_lado.right()), (10, 10))
        self.assertEqual(w.t_vars.horizontalHeaderItem(3).text(), "Etapas")

        # En reposo: todo a 0 y etapas en guion
        b_marcha = w.botones[v_marcha]
        self.assertEqual(b_marcha.text(), "marcha = 0")
        img_btn_0 = b_marcha.grab().toImage()

        w._cambiar_tipo_entrada(v_marcha, True)
        b_marcha.click()
        QApplication.processEvents()
        self.assertEqual(b_marcha.text(), "marcha = 1")
        self.assertNotEqual(img_btn_0, b_marcha.grab().toImage())

        filas = {
            w.t_vars.item(r, 0).text(): (
                w.t_vars.item(r, 0).data(ROL_PAPEL_CONSOLA),
                w.t_vars.item(r, 2).text(),
                w.t_vars.item(r, 2).data(ROL_BOOLEANO_CONSOLA),
                w.t_vars.item(r, 3).text(),
            )
            for r in range(w.t_vars.rowCount())
        }
        self.assertEqual(filas["motor"], ("output", "1", True, "X1"))
        self.assertEqual(filas["mem_b"], ("internal", "1", True, "—"))
        self.assertEqual(filas["cuenta"], ("internal", "5", False, "—"))
        for r in range(w.t_vars.rowCount()):
            self.assertNotIn(w.t_vars.item(r, 2).text(), ("ON", "OFF", "True", "False"))

    def test_C102_capsula_temporizador_en_qt_escena_y_dibujo_js(self) -> None:
        """#1.3: el temporizador activo se pinta en cápsula azul sobre Qt (escena y directo) y en `tools/dibujo.js`."""
        m = M().var("p").step("E1", True).step("E2").trans("t1", ["E1"], ["E2"], "delay(3 s, p, 0 s)")
        v = Vista("c1_tmr", "", "", lambda: (m, {"E1": (40, 40), "t1": (40, 120), "E2": (40, 200)}), normalize_options(None))
        v.act("fijar", {"cambios": {"p": True}})
        v.act("avanzar", {"us": 1_200_000})

        sc = QGraphicsScene()
        sc_dir = QGraphicsScene()
        dibujar(sc, v.model, v.state())
        dibujar_directo(sc_dir, v.model, v.state())

        txt = next(it for it in sc.items() if hasattr(it, "toPlainText") and it.toPlainText() == "1,20 s")
        self.assertEqual(txt.defaultTextColor().name(), COL["timer_text"])
        pills = [
            it for it in sc.items()
            if hasattr(it, "brush") and it.brush().style() != Qt.BrushStyle.NoBrush
            and it.brush().color().name() == COL["timer_bg"]
        ]
        self.assertEqual(len(pills), 1)
        self.assertTrue(pills[0].sceneBoundingRect().contains(txt.sceneBoundingRect().center()))
        # Paridad entre dibujar y dibujar_directo
        pills_dir = [
            it for it in sc_dir.items()
            if hasattr(it, "brush") and it.brush().style() != Qt.BrushStyle.NoBrush
            and it.brush().color().name() == COL["timer_bg"]
        ]
        self.assertEqual(len(pills_dir), 1)
        self.assertEqual(pills[0].sceneBoundingRect(), pills_dir[0].sceneBoundingRect())

        js = (ROOT / "tools" / "dibujo.js").read_text(encoding="utf-8")
        css = (ROOT / "tools" / "dibujo.css").read_text(encoding="utf-8")
        self.assertIn("timer-pill", js)
        self.assertIn("timer-pill", css)
        self.assertIn("#eff6ff", css)

    def test_C103_leyenda_cabecera_estandar_y_capsula_temporizador(self) -> None:
        """C1 incorpora en `leyenda.py` las frases de cápsula y la cabecera estándar con cierre."""
        todo = " ".join(leyenda.textos())
        self.assertIn("cápsula", todo)
        dlg = leyenda.Leyenda()
        self.addCleanup(dlg.close)
        self.assertIsNotNone(getattr(dlg, "cabecera", None))
        self.assertEqual(dlg.cabecera.etiqueta_titulo.text(), "Leyenda del dibujo")
        self.assertIsNotNone(dlg.cabecera.boton_cerrar)
        dlg.show()
        dlg.cabecera.boton_cerrar.click()
        self.assertFalse(dlg.isVisible())

    def test_C104_traza_en_espanol_grafcet_y_dock_acotado_al_lienzo(self) -> None:
        """#7.1 y #7.2: la traza traduce `lote manual`, `=true/false` y `rise`/`fall`, con 16 px y sin tapar la consola derecha."""
        self.assertEqual(
            formatear_texto_traza("lote manual: Pulsador marcha=false, Caja en T1=true · eventos: rise('Caja en T1')"),
            "Entradas: Pulsador marcha = 0, Caja en T1 = 1 · Flanco ↑Caja en T1",
        )
        self.assertEqual(
            formatear_texto_traza("vencimiento temporal: sin cambio de entradas"),
            "Temporizador vencido",
        )
        self.assertEqual(
            formatear_texto_traza("Evolución 1: franquea {t1} → S = {1}"),
            "Evolución 1: franquea {t1} → Situación = {1}",
        )

        w, e = self.vacio()
        v_caja = e.ed.add_variable("Caja en T1", "input", {"kind": "bool"})
        s0 = e.ed.add_step("g", "0", True, at=(100, 80))
        s1 = e.ed.add_step("g", "1", at=(100, 220))
        e.ed.add_transition("g", "rise(`Caja en T1`)", [s0], [s1], at=(100, 150))
        e.cambia()
        self.assertEqual(e.diagnosticos(), [])
        w.resize(1366, 768)
        w.show()
        self.addCleanup(w.hide)
        self.assertTrue(w.cambiar_modo("simular"))
        w._mostrar_panel("inferior", True)
        w._cambiar_tipo_entrada(v_caja, True)
        w.botones[v_caja].click()
        QApplication.processEvents()

        self.assertIsInstance(w.traza.itemDelegate(), DelegadoTraza)
        self.assertEqual(DelegadoTraza.MARGEN_IZQ, 16)
        self.assertGreater(w.traza.count(), 0)
        delegado = w.traza.itemDelegate()
        visibles = [delegado.displayText(w.traza.item(i).text(), None) for i in range(w.traza.count())]
        self.assertTrue(any("Entradas: Caja en T1 = 1 · Flanco ↑Caja en T1" in t for t in visibles), visibles)
        self.assertTrue(any("Situación = {1}" in t for t in visibles), visibles)

        # El dock inferior no invade la columna de la consola lateral derecha
        r_inf = w._plegables["inferior"].geometry()
        r_der = w._plegables["derecho"].geometry()
        self.assertFalse(r_inf.intersects(r_der), (r_inf, r_der))
        self.assertEqual(w._plegables["inferior"].width(), w.vsplit.width())

    def test_C105_avisos_orden_natural_sin_prefijo_duplicado_tarjeta_y_coincidencias(self) -> None:
        """#7.3 y encargo A: orden natural `t5, t6, t7 y t8`, sin `t1: Transición t1…`, tarjeta visible y coincidencias 4.1/4.3."""
        # Orden natural en bucle inestable
        nombres = {"t7": "t7", "t5": "t5", "t8": "t8", "t6": "t6", "s1": "1", "s2": "2"}
        evos = [{"evolutionIndex": i + 1, "cleared": [tid], "situation": ["s1"]} for i, tid in enumerate(("t5", "t7", "t6", "t8"))]
        motivos = motivo_parada("D-LIM-EVOL", "presupuesto de 10000 evoluciones agotado", evos, nombres)
        self.assertIn("t5, t6, t7 y t8", motivos[1][0])

        # Traducción de coincidencias lote–vencimiento (4.1, 4.3 detener, 4.3 D)
        m = M().var("a").step("0", True).step("1").trans("t1", ["0"], ["1"], "delay(2 s, a, 0 s)")
        names = display_names(m.doc)
        eid = next(iter(m.doc["expressions"]))["id"] if False else m.doc["transitions"][0]["conditionRef"]
        for bruto in (
            f"el lote manual cambia la base de [{eid!r}] justo cuando vence (2000000 µs): no se fija qué va primero",
            f"lote manual y vencimientos [{eid!r}] en el mismo instante 2000000 µs: no se fija orden de cola",
            f"lote manual y vencimientos [{eid!r}] en 2000000 µs: el resultado depende del orden (lectura 4.3 D)",
        ):
            llano = vencimientos_en_palabras({"code": "D-SEM-PENDIENTE", "message": bruto}, m.doc, names)
            self.assertIsNotNone(llano)
            assert llano is not None
            self.assertIn("transición t1", llano[0])
            self.assertNotIn(eid, llano[0] + llano[1])
            self.assertNotIn("µs", llano[0] + llano[1])
            self.assertNotIn("lote", llano[0].lower())

        # Sin prefijo duplicado en diagnósticos y tarjeta sobre el lienzo
        w, e = self.vacio()
        s0 = e.ed.add_step("g", "0", True, at=(100, 80))
        s1 = e.ed.add_step("g", "1", at=(100, 220))
        s2 = e.ed.add_step("g", "2", at=(280, 80))
        s3 = e.ed.add_step("g", "3", at=(280, 220))
        ta, _ = e.ed.add_transition("g", "1", [s0], [s1], label="t1", at=(100, 150))
        tb, _ = e.ed.add_transition("g", "1", [s2], [s3], label="t1", at=(280, 150))
        e.ed.get(ta)["label"] = "t1"
        e.ed.get(tb)["label"] = "t1"
        e.cambia()
        w.resize(1366, 768)
        w.show()
        self.addCleanup(w.hide)
        w.b_errores.setChecked(True)
        QApplication.processEvents()

        items = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        rep = next((t for t in items if "Transición t1 repetida" in t), "")
        self.assertTrue(rep, items)
        self.assertFalse(rep.startswith("t1: "), rep)
        self.assertTrue(w.diagrama.tarjeta_diagnosticos.isVisible())
        self.assertIn(estilo.PELIGRO_FONDO, w.diagrama.tarjeta_diagnosticos.styleSheet())


if __name__ == "__main__":
    unittest.main()
