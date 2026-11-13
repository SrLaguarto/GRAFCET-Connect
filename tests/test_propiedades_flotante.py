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
    from escritorio import bloques, estilo
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
        """Centrada, con margen de 24 px y, con dos paneles, una línea por panel desde su parte ampliada (con uno solo, ninguna)."""
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
        """REQ-EDT-02: Ver ▸ Panel de opciones tiene «Flotante» y «Abajo», excluyentes, y la elección se
        recuerda."""
        w = self.w
        self.assertEqual({m: a.text().replace("&", "") for m, a in w.a_props.items()},
                         {"flotante": "Flotante", "abajo": "Abajo"})
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
        """REQ-EDT-02, REQ-EDT-09: doble clic en una etapa (flotante): una ventana centrada, sin línea de puntos (un solo panel)."""
        sid = self.ids["etapas"][0]
        zona = self.e.zonas_propiedades(sid)["elemento"]
        self.e.doble(zona.center())
        HC._bombear(10)
        (v,) = self.ventanas()
        self.assertEqual(v.titulo.text(), "Propiedades · Etapa")
        self.assertTrue(self.w.flot.panel.s_etiqueta.isVisible())
        self.assertTrue(self.w.props.parent() is not None)
        self.assertFalse(self.w._plegables["inferior"].isVisible(), "la barra inferior no se usa")
        self.comprobar_colocacion(0)
        self.assertFalse(v.isWindow())

    def test_SPFL03_doble_clic_en_transicion_abre_ventana_unida(self):
        """REQ-EDT-02: doble clic en una transición (flotante): ventana con la receptividad (programador por bloques),
        con lupa y sin línea de puntos."""
        tid = self.ids["transiciones"][0]
        zona = self.e.zonas_propiedades(tid)["elemento"]
        self.e.doble(zona.center())
        HC._bombear(10)
        (v,) = self.ventanas()
        p = self.w.flot.panel
        self.assertEqual(v.titulo.text(), "Propiedades · Transición")
        self.assertTrue(p.prog.isVisible() and p.t_etiqueta.isVisible())
        self.comprobar_colocacion(0)
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
            self.comprobar_colocacion(0)
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
            self.comprobar_colocacion(0)

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

    # -- presentación (SPFL23 en adelante): tarjetas, márgenes, cabecera y lupa
    TAMANOS = ((960, 1032), (1366, 768), (2000, 1250))
    CASOS = ("etapa", "transicion", "condicionada", "evento", "activacion")

    def casos(self, tipos=None):
        """Un contexto con la ventana abierta por cada tamaño y caso; lo cierra al terminar cada uno."""
        for ancho, alto in self.TAMANOS:
            for tipo in tipos or self.CASOS:
                c = HC.Contexto(ancho, alto)
                try:
                    HC._flotante(tipo)(c)
                    f = c.w.flot
                    self.assertTrue(f.principal.isVisible(), (ancho, alto, tipo))
                    with self.subTest(tamano=(ancho, alto), tipo=tipo):
                        yield c, f.principal
                finally:
                    c.cerrar()

    @staticmethod
    def tarjetas(v):
        return [t for t in (v.condicion, v.accion) if t.isVisible()]

    @staticmethod
    def color(imagen, x, y):
        return imagen.pixelColor(x, y).name()

    def test_SPFL23_margenes_de_la_ventana_y_cabecera(self):
        """REQ-EDT-02: el cuerpo empieza a E4 de los cuatro bordes de la ventana (bajo la línea de la cabecera, también);
        la cabecera mide ALTO_CONTROL + 2·E2, con el título de sección normal, el ✕ a la derecha y una línea de 1 px
        de color BORDE debajo."""
        for c, v in self.casos():
            lupa, columna = v.lupa.geometry(), v.columna.geometry()
            izq = v.cuerpo.mapTo(v, lupa.topLeft()).x()
            der = v.width() - v.cuerpo.mapTo(v, columna.topRight()).x() - 1
            abajo = v.height() - v.cuerpo.mapTo(v, lupa.bottomLeft()).y() - 1
            arriba = v.cuerpo.mapTo(v, lupa.topLeft()).y() - (v.linea.geometry().bottom() + 1)
            self.assertEqual([izq, der, abajo, arriba], [estilo.E4] * 4)
            self.assertEqual(v.cabecera.height(), estilo.ALTO_CONTROL + 2 * estilo.E2)
            self.assertEqual(v.titulo.objectName(), "tituloPanel", "título de sección normal, no reducido")
            self.assertTrue(v.linea.isVisible() and v.linea.height() == 1)
            self.assertEqual(v.linea.geometry().top(), v.cabecera.geometry().bottom() + 1)
            self.assertLessEqual(abs(v.linea.width() - (v.width() - 2)), 1, "de lado a lado")
            imagen = v.grab().toImage()
            y = v.linea.geometry().center().y()
            self.assertEqual(self.color(imagen, v.width() // 2, y), estilo.BORDE)
            centro_cab = v.cabecera.geometry().center().y()
            self.assertLessEqual(abs(v.b_cerrar.geometry().center().y() - centro_cab), 1, "✕ centrada en vertical")
            self.assertLessEqual(abs(v.titulo.geometry().center().y() - centro_cab), 1)
            self.assertGreater(v.b_cerrar.geometry().left(), v.width() // 2, "✕ a la derecha")
            self.assertLessEqual(v.cabecera.width() - v.b_cerrar.geometry().right() - 1, estilo.E2 + 1)

    def test_SPFL24_tarjetas_iguales_con_margen_interior_y_titulo_dentro(self):
        """REQ-EDT-02: cada panel es una tarjeta con un único fondo igual en todas, margen interior ≥ E3, el título
        dentro arriba con E2 debajo y ningún fondo gris anidado."""
        from PySide6.QtWidgets import QWidget
        for c, v in self.casos():
            fondos = set()
            for t in self.tarjetas(v):
                hijos = [h for h in t.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly) if h.isVisible()]
                self.assertTrue(hijos)
                for h in hijos:
                    g = h.geometry()
                    self.assertGreaterEqual(min(g.left(), g.top(), t.width() - g.right() - 1, t.height() - g.bottom() - 1),
                                            estilo.E3, (t.objectName(), h.objectName() or type(h).__name__))
                self.assertTrue(t.rect().contains(t.titulo.geometry()), "el título va dentro de la tarjeta")
                self.assertEqual(t.scroll.geometry().top() - t.titulo.geometry().bottom() - 1, estilo.E2)
                self.assertLess(t.titulo.geometry().top(), t.height() // 3)
                imagen = t.grab().toImage()
                fondos.add(self.color(imagen, estilo.E1, t.height() // 2))
                self.assertEqual(self.color(imagen, t.width() // 2, 0), estilo.BORDE, "borde de 1 px")
                grises = sum(imagen.pixelColor(x, y).name() == estilo.FONDO
                             for x in range(0, imagen.width(), 2) for y in range(0, imagen.height(), 2))
                self.assertEqual(grises, 0, "ningún fondo gris anidado dentro de la tarjeta")
            self.assertEqual(fondos, {estilo.SUPERFICIE_2}, "el mismo fondo en todas las tarjetas")

    def test_SPFL25_lupa_con_marco_hueco_y_lineas_hasta_la_tarjeta(self):
        """REQ-EDT-09: la lupa es una tarjeta con borde, el hueco hasta las tarjetas es E5 (24 px) y cada línea de
        puntos acaba sobre el borde izquierdo de su tarjeta, nunca en el vacío."""
        for c, v in self.casos():
            f = c.w.flot
            imagen = v.lupa.grab().toImage()
            self.assertEqual(self.color(imagen, 0, v.lupa.height() // 2), estilo.BORDE)
            self.assertEqual(self.color(imagen, estilo.E1, v.lupa.height() // 2), estilo.SUPERFICIE)
            self.assertEqual(v.columna.geometry().left() - v.lupa.geometry().right() - 1, estilo.E6)
            zonas = f._zonas()
            self.assertEqual(len(f.enlaces.finales), len(zonas) if len(zonas) == 2 else 0)
            for (tarjeta, _), (parte, destino), fin in zip(zonas, f.enlaces.pares, f.enlaces.finales):
                izq = tarjeta.mapTo(v.cuerpo, QPoint()).x()
                alto = tarjeta.mapTo(v.cuerpo, QPoint()).y()
                self.assertLessEqual(abs(fin.x() - izq), 1, "acaba en el borde izquierdo de la tarjeta")
                self.assertTrue(alto <= fin.y() <= alto + tarjeta.height(), "dentro del alto de la tarjeta")
                titulo = tarjeta.titulo.mapTo(v.cuerpo, tarjeta.titulo.rect().center()).y()
                self.assertLessEqual(abs(fin.y() - titulo), 1, "a la altura de la línea del título")
                self.assertLess(parte.right(), fin.x())
                self.assertTrue(v.lupa.geometry().contains(parte.toRect().center()), "sale de la parte ampliada")

    def test_SPFL26_ningun_texto_recortado(self):
        """REQ-EDT-02: el texto de cada etiqueta y botón visible cabe en su ancho, o acaba en «…» con ayuda emergente."""
        from PySide6.QtWidgets import QAbstractButton, QLabel
        for c, v in self.casos():
            for w in v.findChildren(QLabel) + v.findChildren(QAbstractButton):
                if not w.isVisible() or w.parent() is v.lupa:
                    continue
                texto = w.text().replace("&", "")
                if not texto or isinstance(w, QLabel) and w.wordWrap():
                    continue
                ancho = w.fontMetrics().horizontalAdvance(texto)
                cabe = ancho <= w.width()
                elidido = "…" in texto and bool(w.toolTip())
                self.assertTrue(cabe or elidido, (type(w).__name__, texto, ancho, w.width()))

    def test_SPFL27_lupa_solo_dibuja_el_elemento_seleccionado(self):
        """REQ-EDT-09: la lupa recorta el dibujo a la caja de la acción, su marca y, si es la primera unida a la etapa,
        su trazo de unión: ningún trazo de las cajas vecinas a su izquierda."""
        for c, v in self.casos(("evento", "condicionada")):
            f = c.w.flot
            caja = c.e.accion_en_id(f.panel.ident)
            primera = caja["cabeza"] == caja["id"] and not caja["suelta"]
            t = v.lupa.transformar()
            x, y, w, h = caja["rect"]
            r = t.mapRect(QRectF(x, y, w, h))
            imagen = v.lupa.grab().toImage()
            esc = t.m11()
            medio = 0.8 * esc  # mitad del trazo de la caja
            izq, der = int(r.left() - medio), int(r.right() + medio) + 1  # los píxeles de más allá del borde exterior (el que lo cruza queda dentro)
            for py in range(imagen.height()):
                for px in range(izq):
                    if imagen.pixelColor(px, py).lightness() < 100:
                        unido = primera and abs(py - r.center().y()) <= 2 * esc + 2
                        self.assertTrue(unido, ("trazo ajeno a la izquierda de la caja", px, py))
            for py in range(int(r.top() - medio), int(r.bottom() + medio) + 1):  # en las filas de sus líneas de arriba y abajo
                for px in range(der, imagen.width()):
                    self.assertGreaterEqual(imagen.pixelColor(px, py).lightness(), 100, ("rebaba a la derecha de la caja", px, py))
                for px in range(max(izq - 3, 0), izq):
                    if abs(py - r.center().y()) > 2 * esc + 2:
                        self.assertGreaterEqual(imagen.pixelColor(px, py).lightness(), 100, ("rebaba a la izquierda de la caja", px, py))
            for px in (int(r.left() + 2), int(r.right() - 2)):  # los cuatro bordes de la caja se ven enteros (no recortados a medias)
                self.assertLess(imagen.pixelColor(px, int(r.top())).lightness(), 100, "línea de arriba entera")
                self.assertLess(imagen.pixelColor(px, int(r.bottom())).lightness(), 100, "línea de abajo entera")
            for py in (int(r.top() + 3), int(r.bottom() - 3)):
                self.assertLess(imagen.pixelColor(int(r.left()), py).lightness(), 100, "borde izquierdo entero")
                self.assertLess(imagen.pixelColor(int(r.right()), py).lightness(), 100, "borde derecho entero")
            if primera:
                oscuros = [px for px in range(int(r.left() - 2)) if imagen.pixelColor(px, int(r.center().y())).lightness() < 100]
                self.assertTrue(oscuros, "el trazo de unión de la primera acción se ve")

    def test_SPFL28_linea_de_condicion_sale_de_la_esquina_de_la_marca(self):
        """REQ-EDT-09: la línea de la condición o del evento sale de la esquina superior izquierda de la marca ampliada
        y no cruza el texto de la marca ni la caja."""
        for c, v in self.casos(("evento", "condicionada")):
            f = c.w.flot
            caja = c.e.accion_en_id(f.panel.ident)
            t = v.lupa.transformar()
            marca = t.mapRect(QRectF(*caja["marca"])).translated(QPointF(v.lupa.pos()))
            ini, fin = f.enlaces.inicios[0], f.enlaces.finales[0]
            self.assertLessEqual(abs(ini.x() - marca.left()), 1)
            self.assertLessEqual(abs(ini.y() - marca.top()), 1)
            x, y, w, h = caja["rect"]
            cajaw = t.mapRect(QRectF(x, y, w, h)).translated(QPointF(v.lupa.pos()))
            for rect in (marca.adjusted(2, 2, -2, -2), cajaw.adjusted(2, 2, -2, -2)):
                for i in range(1, 200):
                    p = ini + (fin - ini) * (i / 200)
                    self.assertFalse(rect.contains(p), ("la línea cruza el elemento", p, rect))
            accion = f.enlaces.inicios[1]
            self.assertLessEqual(abs(accion.x() - cajaw.right()), 6, "la de la acción sigue saliendo de su borde derecho")

    # -- encargo 18: ventana más limpia (sin fila Fórmula, aviso ni frase), más alto para los bloques, grupos plegables, lupa recortada y Esc
    def con_entradas(self, c, n=8):
        for i in range(n):
            c.e.nueva_variable(f"sen{i}", "input", None)

    def test_SPFL29_flotante_sin_formula_ni_aviso_ni_frase_y_la_barra_igual(self):
        """REQ-EDT-02: en la ventana flotante no hay fila «Fórmula», ni aviso de «correcta», ni la frase de la acción; en la barra inferior
        todo sigue."""
        for c, v in self.casos(("condicionada", "evento", "transicion")):
            p = c.w.flot.panel
            self.assertFalse(p._l_formula.isVisible() or p.t_texto.isVisible(), "sin la fila Fórmula")
            self.assertFalse(p.t_estado.isVisible(), "sin el aviso de fórmula correcta")
            self.assertFalse(p.accion.frase.isVisible(), "sin la frase de la acción")
            self.assertTrue(p.prog.papelera.isVisible())
        c = HC.Contexto(1366, 768)
        try:
            HC._con_seleccion("accion")(c)
            p = c.w.props
            self.assertTrue(p._l_formula.isVisible() and p.t_texto.isVisible() and p.t_estado.isVisible() and p.accion.frase.isVisible())
            self.assertIn("correcta", p.t_estado.text())
            self.assertTrue(p.accion.frase.text())
            self.assertIs(p.prog.papelera.parentWidget(), p.caja_formula, "la papelera, en la fila de la fórmula")
        finally:
            c.cerrar()

    def test_SPFL30_error_de_formula_una_linea_roja_y_papelera_que_borra(self):
        """REQ-EDT-02: con la fórmula errónea sale una línea roja de una línea bajo el área de bloques; la papelera, junto a las categorías,
        borra la fórmula."""
        from escritorio.diagrama import COL
        for ancho, alto in ((1366, 768), (2000, 1250)):
            with self.subTest(tamano=(ancho, alto)):
                c = HC.Contexto(ancho, alto)
                try:
                    HC._flotante("evento")(c)
                    f = c.w.flot
                    p = f.panel
                    aid = self.accion_de(c, "evento")
                    self.assertFalse(p.t_estado.isVisible(), "correcto: nada")
                    c.e.poner_texto_accion(aid, "evento", "3s/?")
                    HC._bombear(12)
                    e = p.t_estado
                    self.assertTrue(e.isVisible())
                    self.assertTrue(e.text().startswith("Error de sintaxis"))
                    self.assertIn(COL["err"], e.styleSheet())
                    self.assertLessEqual(e.height(), e.fontMetrics().height() + 4, "una sola línea")
                    if e.texto_visible() != " ".join(e.text().splitlines()):
                        self.assertIn("…", e.texto_visible())
                        self.assertTrue(e.toolTip(), "el texto entero, en la ayuda emergente")
                    self.assertGreaterEqual(e.mapTo(p, QPoint()).y(), p.prog.mapTo(p, QPoint()).y() + p.prog.height() - 2, "bajo el área")
                    aid = p.objetivo_bloques()[1]  # (con un evento a medias la acción puede cambiar de identidad)
                    c.e.poner_texto_accion(aid, "evento", "↑marcha")
                    HC._bombear(12)
                    aid = p.objetivo_bloques()[1]
                    self.assertFalse(p.t_estado.isVisible())
                    # la papelera: junto a las categorías, no en el pie
                    pap = p.prog.papelera
                    self.assertTrue(pap.isVisible() and pap.toolTip())
                    self.assertLess(pap.mapTo(p.prog, QPoint()).y() + pap.height(), p.prog.lienzo.mapTo(p.prog, QPoint()).y() + 2)
                    self.assertGreater(pap.mapTo(p.prog, QPoint()).x(), p.prog.width() // 2)
                    self.assertTrue(p.prog.texto())
                    pap.al_soltar({"origen": (0,), "grupo": p.prog.grupo})
                    HC._bombear(8)
                    self.assertEqual(p.prog.texto(), "", "la papelera borró la fórmula")
                finally:
                    c.cerrar()

    @staticmethod
    def accion_de(c, tipo):
        return next(a["id"] for a in c.e.ed.model["actions"] if c.e.datos_accion(a["id"])["tipo"] == tipo)

    def test_SPFL31_area_de_bloques_alta_y_sin_desplazamiento_evitable(self):
        """REQ-EDT-02: el área de bloques de la ventana flotante ve al menos 6 fichas de variables a 1366×768 y el doble aproximadamente a
        2000×1250, y las tarjetas no se desplazan."""
        vistas = {}
        for ancho, alto in ((1366, 768), (2000, 1250)):
            for tipo in ("condicionada", "evento", "transicion"):
                c = HC.Contexto(ancho, alto)
                try:
                    self.con_entradas(c, 12)
                    HC._flotante(tipo)(c)
                    f = c.w.flot
                    paleta = f.panel.prog.paleta
                    visor = f.panel.prog._sc_paleta.viewport().height()
                    fichas = sum(1 for caja, x, y in paleta._cajas if y + caja.h <= visor)
                    vistas[(ancho, tipo)] = fichas
                    for tarjeta in (t for t in (f.principal.condicion, f.principal.accion) if t.isVisible()):
                        self.assertEqual(tarjeta.scroll.verticalScrollBar().maximum(), 0, (ancho, tipo, tarjeta.titulo.text()))
                finally:
                    c.cerrar()
        for tipo in ("condicionada", "evento", "transicion"):
            self.assertGreaterEqual(vistas[(1366, tipo)], 6, vistas)
            self.assertGreaterEqual(vistas[(2000, tipo)], int(vistas[(1366, tipo)] * 1.6), vistas)

    def test_SPFL32_lineas_de_puntos_solo_con_dos_paneles(self):
        """REQ-EDT-09: sin línea de puntos en etapa, transición ni acciones de un solo panel; dos líneas en condicionada y evento."""
        for c, v in self.casos(("etapa", "transicion", "activacion", "condicionada", "evento")):
            esperadas = 2 if v.condicion.isVisible() else 0
            f = c.w.flot
            self.assertEqual((len(f.enlaces.pares), len(f.enlaces.finales), len(f.enlaces.inicios)), (esperadas,) * 3)

    def mover_etapa(self, c, ident, y):
        for s in c.e.ed.model["steps"]:
            if s["id"] == ident:
                s["y"] = y
        c.e.cambiado.emit()

    def test_SPFL33_lupa_de_transicion_y_etapa_sin_trozos_vecinos(self):
        """REQ-EDT-09: la lupa de una transición dibuja su trazo, su barra y su texto con los muñones del enlace, sin la etapa de debajo (ni
        de arriba); la de una etapa, su caja y sus muñones."""
        from escritorio.diagrama import posiciones
        for caso in ("transicion", "etapa"):
            c = HC.Contexto(1366, 768)
            try:
                HC._edicion(c)
                c.w._cambiar_modo_propiedades("flotante")
                tid, e = c.ids["transiciones"][0], c.e
                z0 = e.zonas_propiedades(tid)["elemento"]
                self.mover_etapa(c, c.ids["etapas"][1], int(z0.bottom() + 3 + 22))  # la etapa de debajo casi pegada a la zona de la transición
                self.mover_etapa(c, c.ids["etapas"][0], int(z0.top() - 3 - 22))  # y la de arriba también
                HC._bombear(6)
                e.seleccionar([tid if caso == "transicion" else c.ids["etapas"][1]])
                c.w._abrir_opciones()
                HC._bombear(12)
                v = c.w.flot.principal
                ident = c.w.flot.panel.ident
                zona = e.zonas_propiedades(ident)["elemento"]
                t = v.lupa.transformar()
                esc = t.m11()
                zr = t.mapRect(zona)
                xc = t.map(QPointF(*posiciones(e.M)[ident])).x()
                imagen = v.lupa.grab().toImage()
                ancho_muñon = 2 * esc + 2
                for y in range(imagen.height()):
                    if zr.top() - 2 <= y <= zr.bottom() + 2:
                        continue
                    for x in range(4, imagen.width() - 4):
                        if abs(x - xc) <= ancho_muñon:
                            continue
                        if caso == "etapa" and zr.center().y() - ancho_muñon <= y <= zr.center().y() + ancho_muñon and x > zr.right():
                            continue  # el muñón del enlace a la acción
                        self.assertGreaterEqual(imagen.pixelColor(x, y).lightness(), 100, (caso, "trozo ajeno", x, y))
                oscuros = [x for x in range(imagen.width()) if imagen.pixelColor(x, int(zr.center().y())).lightness() < 100]
                self.assertTrue(oscuros, "el propio elemento se ve")
            finally:
                c.cerrar()

    def test_SPFL34_esc_cierra_la_ventana(self):
        """REQ-EDT-02: con la ventana abierta, Esc la cierra, con el foco en ella o en el dibujo (sin deseleccionar); con un desplegable
        abierto, el primer Esc solo lo cierra."""
        from PySide6.QtTest import QTest
        sid = self.ids["etapas"][0]
        self.abrir([sid])
        f = self.w.flot
        f.panel.s_etiqueta.setFocus()
        HC._bombear(4)
        QTest.keyClick(f.panel.s_etiqueta, Qt.Key.Key_Escape)
        HC._bombear(6)
        self.assertEqual(self.ventanas(), [], "Esc con el foco en la ventana")
        self.abrir([sid])
        self.assertEqual(len(self.ventanas()), 1)
        self.w.diagrama.setFocus()
        HC._bombear(4)
        QTest.keyClick(self.w.diagrama.viewport(), Qt.Key.Key_Escape)
        HC._bombear(6)
        self.assertEqual(self.ventanas(), [], "Esc con el foco en el dibujo")
        self.assertIn(sid, self.e.sel, "no deselecciona a la vez")
        self.abrir([sid])
        combo = f.panel.s_tipo
        combo.setFocus()
        combo.showPopup()
        HC._bombear(6)
        popup = QApplication.activePopupWidget()
        self.assertIsNotNone(popup, "desplegable abierto")
        QTest.keyClick(popup, Qt.Key.Key_Escape)
        HC._bombear(6)
        self.assertEqual(len(self.ventanas()), 1, "el primer Esc solo cierra el desplegable")
        self.assertIsNone(QApplication.activePopupWidget())
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_Escape)
        HC._bombear(6)
        self.assertEqual(self.ventanas(), [], "el siguiente cierra la ventana")

    def test_SPFL35_grupos_plegables_en_la_barra_y_en_la_flotante(self):
        """REQ-EDT-02: los subtítulos de la paleta de variables plegan su grupo con clic y con el teclado, se recuerdan y se comparten entre la
        barra inferior y la ventana flotante."""
        from PySide6.QtTest import QTest
        from escritorio.paleta_variables import CLAVE_PLEGADOS, TituloGrupo
        for modo in ("abajo", "flotante"):
            with self.subTest(modo=modo):
                c = HC.Contexto(1366, 768)
                try:
                    (HC._flotante("condicionada") if modo == "flotante" else HC._con_seleccion("accion"))(c)
                    self.con_entradas(c, 3)
                    HC._bombear(10)
                    panel = c.w.flot.panel if modo == "flotante" else c.w.props
                    otro = c.w.props if modo == "flotante" else c.w.flot.panel if c.w.flot.panel is not None else None
                    paleta = panel.prog.paleta
                    titulos = {t.papel: t for t in paleta.findChildren(TituloGrupo) if t.isVisible()}
                    self.assertIn("entrada", titulos)
                    self.assertFalse(titulos["entrada"].plegado, "por defecto, desplegados")
                    antes = len(paleta.bloques())
                    titulos["entrada"].click()
                    HC._bombear(4)
                    self.assertTrue(titulos["entrada"].plegado)
                    self.assertLess(len(paleta.bloques()), antes)
                    self.assertEqual(c.w.ajustes.value(CLAVE_PLEGADOS), "entrada")
                    if otro is not None:
                        self.assertTrue(any(g[0] == "entrada" and g[3] == 0 for g in otro.prog.paleta.grupos), "el otro control lo sigue")
                    titulos["entrada"].setFocus(Qt.FocusReason.TabFocusReason)
                    QTest.keyClick(titulos["entrada"], Qt.Key.Key_Space)
                    HC._bombear(4)
                    self.assertFalse(titulos["entrada"].plegado)
                    QTest.keyClick(titulos["entrada"], Qt.Key.Key_Return)
                    HC._bombear(4)
                    self.assertTrue(titulos["entrada"].plegado)
                    self.assertEqual(c.w.ajustes.value(CLAVE_PLEGADOS), "entrada")
                    titulos["entrada"].click()  # desplegado otra vez, para el siguiente modo
                finally:
                    c.cerrar()


if __name__ == "__main__":
    unittest.main()
