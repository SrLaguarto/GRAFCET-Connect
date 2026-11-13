"""Propiedades centradas con lupa viva. Pruebas suplementarias REQ-EDT-02 y REQ-EDT-09."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSettings, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication, QPushButton, QToolButton
    from tools import hoja_contactos as HC
    from escritorio import bloques
    from escritorio.flotantes import AMPLIACION_MAXIMA, VentanaFlotante
    from escritorio.propiedades import PanelPropiedades
    QT = True
except ImportError:  # sin PySide6
    QT = False


@unittest.skipUnless(QT, "Falta PySide6")
class PropiedadesFlotante(unittest.TestCase):
    def setUp(self):
        HC.aplicacion()
        self.c = HC.Contexto(1366, 768)
        self.addCleanup(self.c.cerrar)
        HC._edicion(self.c)
        self.w, self.e, self.ids = self.c.w, self.c.e, self.c.ids
        self.w._cambiar_modo_propiedades("flotante")
        HC._bombear(6)

    # -- ayudas
    def abrir(self, sel):
        self.e.seleccionar(sel)
        self.w._abrir_opciones()
        HC._bombear(10)

    def accion(self, tipo):
        return next(a["id"] for a in self.e.ed.model["actions"] if self.e.datos_accion(a["id"])["tipo"] == tipo)

    def abrir_accion(self, aid, sid):
        self.e.accion, self.e.ver_accion, self.e.sel = aid, True, [sid]
        self.e.cambiado.emit()
        self.w._abrir_opciones()
        HC._bombear(10)

    def ventanas(self):
        f = self.w.flot
        return [v for v in self.w.findChildren(VentanaFlotante) if v.isVisible()]

    def comprobar_colocacion(self, numero):
        """Centrada, con margen de 24 px y una línea por panel desde su parte ampliada."""
        f = self.w.flot
        v = f.principal
        area = f._area()
        self.assertEqual(len(self.ventanas()), 1)
        self.assertTrue(area.adjusted(24, 24, -24, -24).contains(v.geometry()))
        self.assertLessEqual(abs(v.geometry().center().x() - area.center().x()), 1)
        self.assertLessEqual(abs(v.geometry().center().y() - area.center().y()), 1)
        self.assertTrue(f.enlaces.isVisible())
        zonas = f._zonas()
        self.assertEqual(len(f.enlaces.pares), numero)
        for (panel, original), (parte, destino) in zip(zonas, f.enlaces.pares):
            esperado = v.lupa.transformar().mapRect(original).translated(v.lupa.pos())
            self.assertEqual(parte, esperado)
            self.assertTrue(v.lupa.origen.contains(original))
            self.assertEqual(destino.topLeft().toPoint(), panel.mapTo(v.cuerpo, QPoint()))
            self.assertLess(parte.right(), destino.left())

    # -- SPFL01
    def test_SPFL01_modo_en_ver_y_persistencia(self):
        """REQ-EDT-02: Ver tiene «Propiedades: abajo» y «Propiedades: flotante», excluyentes, y la elección se
        recuerda."""
        w = self.w
        self.assertEqual({m: a.text().replace("&", "") for m, a in w.a_props.items()},
                         {"abajo": "Propiedades: abajo", "flotante": "Propiedades: flotante"})
        self.assertTrue(w.a_props["flotante"].isChecked() and not w.a_props["abajo"].isChecked())
        w.a_props["abajo"].trigger()
        self.assertEqual((w.modo_propiedades, w.a_props["flotante"].isChecked()), ("abajo", False))
        self.assertEqual(w.ajustes.value("paneles/propiedades"), "abajo")
        w.a_props["flotante"].trigger()
        self.assertEqual(w.ajustes.value("paneles/propiedades"), "flotante")
        ruta = w.ajustes.fileName()
        w.ajustes.sync()
        from escritorio.ventana import Ventana
        otra = Ventana(QSettings(ruta, QSettings.Format.IniFormat))
        self.addCleanup(otra.deleteLater)
        self.assertEqual(otra.modo_propiedades, "flotante")
        self.assertTrue(otra.a_props["flotante"].isChecked())

    # -- SPFL02 / SPFL03
    def test_SPFL02_doble_clic_en_etapa_abre_ventana_unida(self):
        """REQ-EDT-02, REQ-EDT-09: doble clic en una etapa (flotante): una ventana centrada con una línea interior."""
        sid = self.ids["etapas"][0]
        zona = self.e.zonas_propiedades(sid)["elemento"]
        self.e.doble(zona.center())
        HC._bombear(10)
        (v,) = self.ventanas()
        self.assertEqual(v.titulo.text(), "Propiedades · Etapa")
        self.assertTrue(self.w.flot.panel.s_etiqueta.isVisible())
        self.assertTrue(self.w.props.parent() is not None)
        self.assertFalse(self.w._plegables["inferior"].isVisible(), "la barra inferior no se usa")
        self.comprobar_colocacion(1)
        self.assertFalse(v.isWindow())

    def test_SPFL03_doble_clic_en_transicion_abre_ventana_unida(self):
        """REQ-EDT-02: doble clic en una transición (flotante): ventana con la receptividad (programador por bloques),
        con lupa y línea interior."""
        tid = self.ids["transiciones"][0]
        zona = self.e.zonas_propiedades(tid)["elemento"]
        self.e.doble(zona.center())
        HC._bombear(10)
        (v,) = self.ventanas()
        p = self.w.flot.panel
        self.assertEqual(v.titulo.text(), "Propiedades · Transición")
        self.assertTrue(p.prog.isVisible() and p.t_etiqueta.isVisible())
        self.comprobar_colocacion(1)
        p._desde_bloques("paro")
        self.assertEqual(self.e.texto_usuario(tid), "paro", "lo que se edita llega al dibujo al momento")

    def test_SPFL04_centrada_al_redimensionar_y_sin_fijar(self):
        """REQ-EDT-02: una ventana centrada al redimensionar, sin botones Fijar visibles."""
        self.abrir([self.ids["etapas"][0]])
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            self.w.resize(ancho, alto)
            HC._bombear(12)
            self.w._escala_tras_la_rafaga()
            HC._bombear(10)
            self.comprobar_colocacion(1)
            v = self.w.flot.principal
            self.assertFalse([b for b in v.findChildren(QToolButton) if b.isVisible() and b.text() == "Fijar"])

    def test_SPFL05_lupa_real_sin_marcas_y_con_tope(self):
        """REQ-EDT-09: la lupa renderiza la escena real, con tope 125 %, sin modificar la selección."""
        self.abrir([self.ids["etapas"][0]])
        d, v = self.w.diagrama, self.w.flot.principal
        items = d.scene().items()
        antes = [(i, i.isVisible()) for i in items]
        imagen = v.lupa.grab().toImage()
        self.assertFalse(imagen.isNull())
        self.assertEqual([(i, i.isVisible()) for i in items], antes)
        self.assertLessEqual(v.lupa.transformar().m11(), AMPLIACION_MAXIMA)
        d.marcar_anclas([{"id": "prueba", "lado": "arriba", "pos": v.lupa.origen.center()}])
        d.lazo(v.lupa.origen.topLeft(), v.lupa.origen.bottomRight())
        self.assertEqual(imagen, v.lupa.grab().toImage(), "sin anclas ni arrastres en la lupa")
        escala = d.escala()
        evento = QWheelEvent(
            QPointF(20, 20), QPointF(20, 20), QPoint(), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        QApplication.sendEvent(v.lupa, evento)
        self.assertEqual(d.escala(), escala, "la rueda no cambia el dibujo desde la lupa")
        self.assertTrue(any(imagen.pixelColor(x, y).lightness() < 100
                            for x in range(imagen.width()) for y in range(imagen.height())))

    def test_SPFL06_zoom_desplazamiento_y_movimiento_no_recolocan(self):
        """REQ-EDT-09: zoom, desplazamiento y movimiento mantienen fija la ventana."""
        sid = self.ids["etapas"][0]
        self.abrir([sid])
        d = self.w.diagrama
        antes = QRect(self.w.flot.principal.geometry())
        for cambio in (
            lambda: d.zoom(1.5),
            lambda: d.horizontalScrollBar().setValue(d.horizontalScrollBar().value() + 40),
            lambda: self.e.mover_teclado(40, 0),
        ):
            cambio()
            HC._bombear(8)
            self.assertEqual(self.w.flot.principal.geometry(), antes)
            self.comprobar_colocacion(1)

    # -- SPFL07 / SPFL08
    def test_SPFL07_condicionada_dos_paneles(self):
        """REQ-EDT-02: una acción condicionada abre paneles «Condición» y «Acción», unidos a su parte ampliada; lo
        que se edita en cada una cambia el dibujo."""
        aid, sid = self.accion("condicionada"), self.ids["etapas"][2]
        self.abrir_accion(aid, sid)
        f = self.w.flot
        self.assertEqual([v.titulo.text() for v in self.ventanas()], ["Propiedades · Acción condicionada"])
        self.assertLess(f.principal.condicion.geometry().bottom(), f.principal.accion.geometry().top())
        self.comprobar_colocacion(2)
        self.assertTrue(f.panel.prog.isVisible() and f.panel.accion.variable.isVisible())
        self.assertIs(f.panel.pagina_bloques.parentWidget(), f.principal.condicion.cuerpo)
        f.panel._desde_bloques("paro")
        self.assertEqual(self.e.datos_accion(aid)["condicion"], "paro")
        textos = [
            seg["t"] for s in self.e.M["steps"] for a in s.get("actions", [])
            if a["id"] == aid for seg in a.get("cond") or []
        ]
        self.assertIn("paro", "".join(textos), "el dibujo muestra la condición nueva")
        imagen_antes = f.principal.lupa.grab().toImage()
        f.panel.accion.poner_variable("aux")
        HC._bombear(8)
        self.assertNotEqual(imagen_antes, f.principal.lupa.grab().toImage())
        self.assertEqual(self.e.datos_accion(aid)["variable"], "aux")
        textos = [
            seg["t"] for s in self.e.M["steps"] for a in s.get("actions", [])
            if a["id"] == aid for seg in a["text"]
        ]
        self.assertIn("aux", textos)

    def test_SPFL08_evento_dos_paneles(self):
        """REQ-EDT-02: una acción por evento abre paneles «Evento» y «Acción» (con el valor), sin solaparse."""
        sid = self.ids["etapas"][2]
        self.assertIsNone(self.e.poner_accion(
            sid, {"tipo": "evento", "variable": "aux", "valor": "1", "evento": "↑marcha"},
        ))
        aid = self.accion("evento")
        self.abrir_accion(aid, sid)
        f = self.w.flot
        self.assertEqual([v.titulo.text() for v in self.ventanas()], ["Propiedades · Acción por evento"])
        self.comprobar_colocacion(2)
        self.assertTrue(f.panel.accion.caja_valor.isVisible(), "la ventana «Acción» lleva el valor")
        f.panel._desde_bloques("↓marcha")
        self.assertEqual(self.e.datos_accion(aid)["evento"], "↓marcha")
        textos = [
            seg["t"] for s in self.e.M["steps"] for a in s.get("actions", [])
            if a["id"] == aid for seg in a.get("event") or []
        ]
        self.assertIn("↓", "".join(textos))
        f.panel.accion._poner_valor("0")
        self.assertEqual(self.e.datos_accion(aid)["valor"], "0")

    # -- SPFL09
    def test_SPFL09_fijar_y_cerrar(self):
        """REQ-EDT-02: sin «Fijar», un clic en otro elemento cierra la ventana; con «Fijar» sigue y muestra el elemento
        nuevo; «✕» la cierra."""
        s0, t0 = self.ids["etapas"][0], self.ids["transiciones"][0]
        self.abrir([s0])
        self.assertEqual(len(self.ventanas()), 1)
        self.e.prensar(self.e.zonas_propiedades(t0)["elemento"].center())
        self.e.soltar(self.e.zonas_propiedades(t0)["elemento"].center())
        HC._bombear(6)
        self.assertEqual(self.ventanas(), [], "sin fijar se esconde")
        self.abrir([s0])
        v = self.w.flot.principal
        self.w.props.t_fijar.click()
        self.assertTrue(self.w.props.t_fijar.isChecked())
        pto = self.e.zonas_propiedades(t0)["elemento"].center()
        self.e.prensar(pto)
        self.e.soltar(pto)
        HC._bombear(6)
        self.assertEqual(v.titulo.text(), "Propiedades · Transición")
        v.b_cerrar.click()
        HC._bombear(4)
        self.assertEqual(self.ventanas(), [])

    # -- SPFL10 / SPFL11
    def test_SPFL10_continua_no_abre_ventana(self):
        """REQ-EDT-02: el doble clic en una acción continua solo despliega su variable sobre ella: ninguna ventana
        flotante."""
        aid = self.accion("continua")
        caja = self.e.accion_en_id(aid)
        x, y, w, h = caja["rect"]
        self.e.doble(QPointF(x + w / 2, y + h / 2))
        HC._bombear(10)
        self.assertEqual(self.ventanas(), [])
        self.assertIsNotNone(getattr(self.w.diagrama, "_selector", None), "el desplegable sobre la acción")

    def test_SPFL11_continua_seleccionada_oculta_ventana(self):
        """REQ-EDT-02: con la ventana abierta y fijada por otro elemento, seleccionar una continua oculta la ventana."""
        self.abrir([self.ids["etapas"][0]])
        self.w.props.t_fijar.click()
        self.abrir_accion(self.accion("continua"), self.ids["etapas"][1])
        p = self.w.flot.panel
        self.assertEqual(self.ventanas(), [])
        self.assertTrue(p.continua)

    def test_SPFL12_continua_en_la_barra_solo_la_frase(self):
        """REQ-EDT-02: con la barra inferior, una acción continua seleccionada no muestra campos, como el lienzo vacío:
        solo la frase."""
        self.w._cambiar_modo_propiedades("abajo")
        self.abrir_accion(self.accion("continua"), self.ids["etapas"][1])
        p = self.w.props
        self.assertTrue(p.isVisible())
        self.assertEqual(
            p.vacio.text(), "Haz doble clic sobre la acción continua para desplegar las variables disponibles.",
        )
        self.assertTrue(p.vacio.isVisible())
        self.assertFalse(p.cuerpo.isVisible() or p.izq.isVisible() or p.accion.variable.isVisible())

    # -- SPFL13
    def test_SPFL13_barra_resalta_la_parte_editada(self):
        """REQ-EDT-09: con la barra inferior, al editar una acción condicionada se resalta la condición (foco en los
        bloques) o el rectángulo de
        la acción (foco en el resto); con el foco en otra parte, no se resalta otra cosa."""
        self.w._cambiar_modo_propiedades("abajo")
        aid, sid = self.accion("condicionada"), self.ids["etapas"][2]
        self.abrir_accion(aid, sid)
        p = self.w.props
        self.assertFalse([m for m in self.e.seleccion_dibujo() if m.startswith("parte:")])
        n0 = len(self.w.diagrama.scene().items())
        self.assertFalse(any(m.startswith("parte:") for m in self.e.seleccion_dibujo()))
        p.prog.lienzo.setFocus()
        HC._bombear(6)
        self.assertIn(f"parte:{aid}:condicion", self.e.seleccion_dibujo())
        self.assertGreater(len(self.w.diagrama.scene().items()), n0, "el dibujo resalta la banderita")
        p.accion.variable.setFocus()
        HC._bombear(6)
        marcas = [m for m in self.e.seleccion_dibujo() if m.startswith("parte:")]
        self.assertEqual(marcas, [f"parte:{aid}:accion"])
        self.e.seleccionar([])
        HC._bombear(6)
        self.assertFalse([m for m in self.e.seleccion_dibujo() if m.startswith("parte:")])

    # -- SPFL14
    def test_SPFL14_ampliar_ya_no_existe(self):
        """REQ-EDT-02: el botón «Ampliar» y su ventana flotante han desaparecido del programador y de Propiedades."""
        prog = bloques.Programador(lambda: ({}, []))
        self.assertFalse(hasattr(prog, "ampliar") or hasattr(prog, "ampliar_ventana"))
        self.abrir([self.ids["transiciones"][0]])
        for panel in (self.w.props, self.w.flot.panel):
            self.assertFalse([b for b in panel.findChildren(QPushButton) if "Ampliar" in b.text()])

    # -- SPFL15
    def test_SPFL15_volver_a_abajo_y_simular_esconden_las_ventanas(self):
        """REQ-EDT-02: pasar a «abajo» esconde las ventanas y abre la barra; al simular no queda ninguna ventana
        flotante."""
        self.abrir([self.ids["etapas"][0]])
        self.assertEqual(len(self.ventanas()), 1)
        self.w._cambiar_modo_propiedades("abajo")
        HC._bombear(10)
        self.assertEqual(self.ventanas(), [])
        self.assertTrue(self.w._plegables["inferior"].isVisible() and self.w.props.isVisible())
        self.w._cambiar_modo_propiedades("flotante")
        HC._bombear(10)
        self.assertEqual(len(self.ventanas()), 1)
        self.w.cambiar_modo("simular")
        HC._bombear(10)
        self.assertEqual(self.ventanas(), [])
        self.w.a_ejecutar.setChecked(False)

    def test_SPFL16_maquetacion_tres_tamanos(self):
        """REQ-EDT-02: M1, M2, C1 y C2 sin excepciones nuevas en las tres resoluciones."""
        from test_auditoria_maquetacion import REGLAS, permitida
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 1032)):
            for tipo in ("etapa", "transicion", "condicionada", "evento"):
                with self.subTest(tamano=(ancho, alto), tipo=tipo):
                    c = HC.Contexto(ancho, alto)
                    try:
                        HC._flotante(tipo)(c)
                        for regla in ("M1", "M2", "C1", "C2"):
                            errores = [e for e in REGLAS[regla](c.w) if not permitida(regla, e)]
                            self.assertEqual(errores, [], (regla, errores))
                        f = c.w.flot
                        self.assertTrue(f._area().adjusted(24, 24, -24, -24).contains(f.principal.geometry()))
                        self.assertIs(f.principal.parentWidget(), c.w.centralWidget())
                    finally:
                        c.cerrar()

    def test_SPFL17_flechas_completas_al_activar_y_desactivar(self):
        """REQ-EDT-09: el recorte incluye la punta de ambas flechas, también en una acción suelta."""
        for tipo in ("activacion", "desactivacion"):
            for suelta in (False, True):
                with self.subTest(tipo=tipo, suelta=suelta):
                    if suelta:
                        aid = self.e.poner_accion_suelta(QPointF(450, 120), tipo=tipo)
                        self.abrir([aid])
                    else:
                        sid = self.ids["etapas"][0]
                        self.e.poner_accion(sid, {"tipo": tipo, "variable": "aux", "valor": "1"})
                        aid = self.accion(tipo)
                        self.abrir_accion(aid, sid)
                    v = self.w.flot.principal
                    marca = QRectF(*self.e.accion_en_id(aid)["marca"])
                    self.assertTrue(v.lupa.origen.contains(marca))
                    if tipo == "activacion":
                        marca.setBottom(marca.top() + 6)
                    else:
                        marca.setTop(marca.bottom() - 6)
                    punta = v.lupa.transformar().mapRect(marca).toAlignedRect()
                    self.assertTrue(v.lupa.rect().contains(punta))
                    imagen = v.lupa.grab().toImage()
                    oscuros = sum(imagen.pixelColor(x, y).lightness() < 100
                                  for x in range(punta.left(), punta.right() + 1)
                                  for y in range(punta.top(), punta.bottom() + 1))
                    self.assertGreater(oscuros, 5, "la punta triangular se ve entera en la vista previa")

    def test_SPFL18_media_pantalla_prioriza_formulador(self):
        """REQ-EDT-02: a media pantalla usa el área de la aplicación y reserva el ancho al formulador."""
        for ancho, alto in ((960, 1032), (683, 768)):
            c = HC.Contexto(ancho, alto)
            try:
                HC._flotante("activacion_numerica")(c)
                f = c.w.flot
                v, p = f.principal, f.panel
                self.assertGreater(v.width(), c.w.width() * .85)
                self.assertGreater(v.columna.width(), v.lupa.width() * 3)
                self.assertGreater(p.accion.prog.width(), v.lupa.width() * 2)
                self.assertLessEqual(v.lupa.transformar().m11(), AMPLIACION_MAXIMA)
                self.assertEqual(v.accion.scroll.horizontalScrollBar().maximum(), 0)
                self.assertTrue(p.accion.variable.isVisible())
            finally:
                c.cerrar()

    def test_SPFL19_cambiar_de_pagina_oculta_y_restaurar_recupera(self):
        """REQ-EDT-02: la ventana no invade PLANOS al dejar el dibujo, aunque sea hija de la aplicación."""
        self.abrir([self.ids["etapas"][0]])
        self.w.paginas_es.setCurrentIndex(2)
        HC._bombear(6)
        self.assertFalse(self.w.flot.hay_ventanas())
        self.w.paginas_es.setCurrentIndex(0)
        HC._bombear(6)
        self.assertTrue(self.w.flot.hay_ventanas())

    def test_SPFL20_valor_booleano_entero_sin_desplazar(self):
        """REQ-EDT-02: las fichas 1/0 quedan visibles, sin desplazarse bajo el selector de variable."""
        sid = self.ids["etapas"][0]
        self.e.poner_accion(sid, {"tipo": "desactivacion", "variable": "aux", "valor": "1"})
        self.abrir_accion(self.accion("desactivacion"), sid)
        for ancho, alto in ((1366, 768), (960, 1032), (683, 768)):
            with self.subTest(tamano=(ancho, alto)):
                self.w.resize(ancho, alto)
                HC._bombear(10)
                f = self.w.flot
                self.assertEqual(f.principal.accion.scroll.verticalScrollBar().maximum(), 0)
                self.assertTrue(f.panel.accion.caja_fichas.isVisible())

    def test_SPFL21_formulador_mas_bajo_y_con_dibujo_alrededor(self):
        """REQ-EDT-02: reduce la altura sin arrinconar la ventana contra los bordes de la aplicación."""
        self.e.nueva_variable("CT", "internal", {"kind": "int"})
        sid = self.ids["etapas"][0]
        self.e.poner_accion(sid, {"tipo": "activacion", "variable": "CT", "valor": "1"})
        self.abrir_accion(self.accion("activacion"), sid)
        for ancho, alto in ((960, 1032), (683, 768), (2000, 1250)):
            with self.subTest(tamano=(ancho, alto)):
                self.w.resize(ancho, alto)
                HC._bombear(10)
                f = self.w.flot
                area = f._area()
                ventana = f.principal.geometry()
                self.assertLessEqual(ventana.height(), area.height() * .75)
                self.assertGreaterEqual(ventana.left() - area.left(), 48)
                self.assertGreaterEqual(area.right() - ventana.right(), 48)
                self.assertEqual(f.principal.accion.scroll.horizontalScrollBar().maximum(), 0)

    def test_SPFL22_panel_inferior_completo_en_acciones_sueltas(self):
        """REQ-EDT-02: reserva altura para campos y fórmula sin barras de desplazamiento evitables."""
        for ancho, alto in ((1366, 768), (1707, 1024), (2000, 1250), (960, 1032)):
            for tipo in ("condicionada", "evento"):
                with self.subTest(tamano=(ancho, alto), tipo=tipo):
                    c = HC.Contexto(ancho, alto)
                    try:
                        HC._edicion(c)
                        c.e.nueva_variable("hh", "output", {"kind": "int"})
                        c.w._cambiar_modo_propiedades("flotante")
                        aid = c.e.poner_accion_suelta(QPointF(450, 180), tipo=tipo)
                        c.e.seleccionar([aid])
                        c.w._abrir_opciones()
                        HC._bombear(10)
                        f = c.w.flot
                        f.panel.accion.poner_variable("hh" if tipo == "evento" else "aux")
                        f.panel._desde_bloques("marcha" if tipo == "evento" else "")
                        HC._bombear(10)
                        scroll = f.principal.accion.scroll
                        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
                        campos = [f.panel.accion.variable]
                        if tipo == "evento":
                            campos.append(f.panel.accion.valor)
                        for campo in campos:
                            rectangulo = QRect(campo.mapTo(scroll.viewport(), QPoint()), campo.size())
                            self.assertTrue(scroll.viewport().rect().contains(rectangulo))
                    finally:
                        c.cerrar()


if __name__ == "__main__":
    unittest.main()
