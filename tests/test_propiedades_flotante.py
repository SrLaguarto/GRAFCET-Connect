"""Propiedades flotante, resaltado de la parte editada y fin de «Ampliar» (encargo 12 del rediseño). Ninguna es oráculo del documento 11.

Ver > «Propiedades: abajo» / «Propiedades: flotante» (se recuerda). En flotante, el doble clic abre una ventana sobre el dibujo (no del sistema) con el
contenido de la barra, colocada sola junto al elemento (derecha, si no izquierda; dentro del lienzo; sin tapar el elemento) y unida a él con líneas de
puntos; no se mueve ni se redimensiona ni recuerda nada: ante zoom, desplazamiento o movimiento del elemento se vuelve a colocar. Una acción
condicionada o por evento abre dos ventanas (condición o evento, y acción). Una continua no abre ninguna y, seleccionada, solo muestra una frase. Con la
barra inferior, se resalta en el dibujo la parte que se edita.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSettings, QSize
    from PySide6.QtWidgets import QApplication, QPushButton
    from tools import hoja_contactos as HC
    from escritorio import bloques
    from escritorio.flotantes import colocar, tangentes
    from escritorio.propiedades import PanelPropiedades
    QT = True
except ImportError:  # sin PySide6
    QT = False


def _vista(c, r: QRectF) -> QRect:
    """El rectángulo del dibujo `r` en coordenadas de la vista del dibujo (las de las ventanas flotantes)."""
    d = c.w.diagrama
    return d.mapFromScene(r).boundingRect().translated(d.viewport().pos())


@unittest.skipUnless(QT, "Falta PySide6")
class PropiedadesFlotante(unittest.TestCase):
    def setUp(self):
        HC.aplicacion()
        self.c = HC.Contexto(1366, 768)
        self.addCleanup(self.c.cerrar)
        HC._edicion(self.c)
        self.w, self.e, self.ids = self.c.w, self.c.e, self.c.ids
        self.w.resize(1800, 1000)  # (con sitio de sobra: a 1366×768 una acción por evento no deja sitio sin tapar algo de ella, y la ventana se queda con lo menos malo)
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
        return [v for v in (f.principal, f.otra) if v is not None and v.isVisible()]

    def comprobar_colocacion(self, partes):
        """Dentro del lienzo, sin tapar su parte del dibujo y sin solaparse entre sí; las líneas de puntos las unen."""
        f = self.w.flot
        area = f._area()
        vs = [f.otra, f.principal] if f.otra.isVisible() else [f.principal]  # (el orden de `partes`: la de arriba primero)
        for v in vs:
            self.assertTrue(area.contains(v.geometry()), f"{v.titulo.text()} fuera del lienzo: {v.geometry()} / {area}")
        for v, parte in zip(vs, partes):
            self.assertFalse(v.geometry().intersects(parte.adjusted(-2, -2, 2, 2)), f"{v.titulo.text()} tapa su elemento")
        for i, a in enumerate(vs):
            for b in vs[i + 1:]:
                self.assertFalse(a.geometry().intersects(b.geometry()), "dos ventanas solapadas")
        self.assertTrue(f.enlaces.isVisible())
        self.assertEqual(len(f.enlaces.pares), len(vs))
        for parte_dib, ventana in f.enlaces.pares:
            self.assertEqual(len(tangentes(parte_dib, ventana)), 2, "dos líneas por ventana")

    # -- SPFL01
    def test_SPFL01_modo_en_ver_y_persistencia(self):
        """REQ-EDT-02: Ver tiene «Propiedades: abajo» y «Propiedades: flotante», excluyentes, y la elección se recuerda."""
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
        """REQ-EDT-02, REQ-EDT-09: doble clic en una etapa (flotante): una ventana con su contenido, junto a ella y unida por líneas de puntos."""
        sid = self.ids["etapas"][0]
        zona = self.e.zonas_propiedades(sid)["elemento"]
        self.e.doble(zona.center())
        HC._bombear(10)
        (v,) = self.ventanas()
        self.assertEqual(v.titulo.text(), "Propiedades · Etapa")
        self.assertTrue(self.w.flot.panel.s_etiqueta.isVisible())
        self.assertTrue(self.w.props.parent() is not None and not self.w._plegables["inferior"].isVisible(), "la barra inferior no se usa")
        self.comprobar_colocacion([_vista(self, zona)])
        self.assertGreater(v.geometry().left(), _vista(self, zona).right(), "a la derecha si cabe")

    def test_SPFL03_doble_clic_en_transicion_abre_ventana_unida(self):
        """REQ-EDT-02: doble clic en una transición (flotante): ventana con la receptividad (programador por bloques), junto a ella y unida."""
        tid = self.ids["transiciones"][0]
        zona = self.e.zonas_propiedades(tid)["elemento"]
        self.e.doble(zona.center())
        HC._bombear(10)
        (v,) = self.ventanas()
        p = self.w.flot.panel
        self.assertEqual(v.titulo.text(), "Propiedades · Transición")
        self.assertTrue(p.prog.isVisible() and p.t_etiqueta.isVisible())
        self.comprobar_colocacion([_vista(self, zona)])
        p._desde_bloques("paro")
        self.assertEqual(self.e.texto_usuario(tid), "paro", "lo que se edita llega al dibujo al momento")

    def test_SPFL04_sin_sitio_a_la_derecha_va_a_la_izquierda(self):
        """REQ-EDT-02: la colocación automática: derecha si cabe; si no, izquierda; dentro del lienzo y sin tapar; dos ventanas apiladas sin solaparse."""
        area = QRect(0, 0, 1000, 600)
        el = QRect(100, 280, 40, 40)
        (r,) = colocar(area, el, [[QSize(300, 200)]])
        self.assertGreater(r.left(), el.right())
        el = QRect(800, 280, 40, 40)
        (r,) = colocar(area, el, [[QSize(300, 200)]])
        self.assertLess(r.right(), el.left())
        self.assertTrue(area.contains(r))
        a, b = colocar(area, QRect(100, 280, 40, 40), [[QSize(300, 200)], [QSize(250, 150)]])
        self.assertFalse(a.intersects(b))
        self.assertLess(a.top(), b.top(), "una encima de otra")
        self.assertTrue(area.contains(a) and area.contains(b))
        (r,) = colocar(QRect(0, 0, 300, 200), QRect(130, 80, 40, 40), [[QSize(280, 180)]])
        self.assertTrue(QRect(0, 0, 300, 200).contains(r), "sin sitio libre, igual dentro del lienzo")
        a, b = colocar(QRect(0, 0, 1000, 400), QRect(100, 170, 40, 40), [[QSize(300, 300), QSize(700, 180)], [QSize(800, 150)]])
        self.assertFalse(a.intersects(b))

    def test_SPFL05_lineas_de_lupa_no_cruzan_las_cajas(self):
        """REQ-EDT-09: dos líneas entre las esquinas del elemento y las de la ventana, las tangentes que no cruzan ninguna de las dos."""
        a, b = QRectF(10, 10, 20, 20), QRectF(100, 0, 200, 100)
        lineas = tangentes(a, b)
        self.assertEqual(len(lineas), 2)
        for p, q in lineas:
            esq = lambda r: (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight())
            self.assertTrue((p in esq(a) and q in esq(b)) or (q in esq(a) and p in esq(b)))
        self.assertEqual(tangentes(a, QRectF(15, 15, 50, 50)), [], "tocándose, no hay líneas")

    # -- SPFL06
    def test_SPFL06_zoom_desplazamiento_y_movimiento_recolocan(self):
        """REQ-EDT-09: tras zoom, desplazamiento del dibujo o movimiento del elemento, ventana y líneas quedan otra vez junto al elemento."""
        sid = self.ids["etapas"][0]
        self.abrir([sid])
        d = self.w.diagrama

        def revisar():
            HC._bombear(6)
            zona = _vista(self, self.e.zonas_propiedades(sid)["elemento"])
            (v,) = self.ventanas()
            self.assertFalse(v.geometry().intersects(zona.adjusted(-2, -2, 2, 2)))
            parte, _ = self.w.flot.enlaces.pares[0][0], None
            self.assertEqual(QRect(parte.toAlignedRect()).translated(d.viewport().pos()).center(), zona.center())
            return v.geometry(), zona

        antes = revisar()
        d.zoom(1.5)
        despues = revisar()
        self.assertNotEqual(antes[1], despues[1])
        d.horizontalScrollBar().setValue(d.horizontalScrollBar().value() + 40)
        revisar()
        self.e.mover_teclado(40, 0)
        revisar()

    # -- SPFL07 / SPFL08
    def test_SPFL07_condicionada_dos_ventanas(self):
        """REQ-EDT-02: una acción condicionada abre «Condición» (unida a su marca) y «Acción» (unida a su rectángulo), sin solaparse; lo
        que se edita en cada una cambia el dibujo."""
        aid, sid = self.accion("condicionada"), self.ids["etapas"][2]
        self.abrir_accion(aid, sid)
        f = self.w.flot
        self.assertEqual(sorted(v.titulo.text() for v in self.ventanas()), ["Propiedades · Acción", "Propiedades · Condición"])
        self.assertTrue(f.otra.geometry().bottom() < f.principal.geometry().top(), "Condición encima de Acción")
        z = self.e.zonas_propiedades(None, programable=(aid, "condicion"))
        self.comprobar_colocacion([_vista(self, z["condicion"]), _vista(self, z["accion"])])
        self.assertTrue(f.panel.prog.isVisible() and f.panel.accion.variable.isVisible())
        self.assertIs(f.panel.pagina_bloques.parentWidget(), f.otra.cuerpo)
        f.panel._desde_bloques("paro")
        self.assertEqual(self.e.datos_accion(aid)["condicion"], "paro")
        textos = [seg["t"] for s in self.e.M["steps"] for a in s.get("actions", []) if a["id"] == aid for seg in a.get("cond") or []]
        self.assertIn("paro", "".join(textos), "el dibujo muestra la condición nueva")
        f.panel.accion.poner_variable("aux")
        self.assertEqual(self.e.datos_accion(aid)["variable"], "aux")
        self.assertIn("aux", [seg["t"] for s in self.e.M["steps"] for a in s.get("actions", []) if a["id"] == aid for seg in a["text"]])

    def test_SPFL08_evento_dos_ventanas(self):
        """REQ-EDT-02: una acción por evento abre «Evento» (unida a su banderita) y «Acción» (con el valor), sin solaparse."""
        sid = self.ids["etapas"][2]
        self.assertIsNone(self.e.poner_accion(sid, {"tipo": "evento", "variable": "aux", "valor": "1", "evento": "↑marcha"}))
        aid = self.accion("evento")
        self.abrir_accion(aid, sid)
        f = self.w.flot
        self.assertEqual(sorted(v.titulo.text() for v in self.ventanas()), ["Propiedades · Acción", "Propiedades · Evento"])
        z = self.e.zonas_propiedades(None, programable=(aid, "evento"))
        self.comprobar_colocacion([_vista(self, z["evento"]), _vista(self, z["accion"])])
        self.assertTrue(f.panel.accion.caja_valor.isVisible(), "la ventana «Acción» lleva el valor")
        f.panel._desde_bloques("↓marcha")
        self.assertEqual(self.e.datos_accion(aid)["evento"], "↓marcha")
        self.assertIn("↓", "".join(seg["t"] for s in self.e.M["steps"] for a in s.get("actions", []) if a["id"] == aid for seg in a.get("event") or []))
        f.panel.accion._poner_valor("0")
        self.assertEqual(self.e.datos_accion(aid)["valor"], "0")

    # -- SPFL09
    def test_SPFL09_fijar_y_cerrar(self):
        """REQ-EDT-02: sin «Fijar», un clic en otro elemento cierra la ventana; con «Fijar» sigue y muestra el elemento nuevo; «✕» la cierra."""
        s0, t0 = self.ids["etapas"][0], self.ids["transiciones"][0]
        self.abrir([s0])
        self.assertEqual(len(self.ventanas()), 1)
        self.e.prensar(self.e.zonas_propiedades(t0)["elemento"].center())
        self.e.soltar(self.e.zonas_propiedades(t0)["elemento"].center())
        HC._bombear(6)
        self.assertEqual(self.ventanas(), [], "sin fijar se esconde")
        self.abrir([s0])
        v = self.w.flot.principal
        v.t_fijar.click()
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
        """REQ-EDT-02: el doble clic en una acción continua solo despliega su variable sobre ella: ninguna ventana flotante."""
        aid = self.accion("continua")
        caja = self.e.accion_en_id(aid)
        x, y, w, h = caja["rect"]
        self.e.doble(QPointF(x + w / 2, y + h / 2))
        HC._bombear(10)
        self.assertEqual(self.ventanas(), [])
        self.assertIsNotNone(getattr(self.w.diagrama, "_selector", None), "el desplegable sobre la acción")

    def test_SPFL11_continua_seleccionada_solo_la_frase(self):
        """REQ-EDT-02: con la ventana abierta y fijada por otro elemento, seleccionar una continua muestra solo la frase, sin campos."""
        self.abrir([self.ids["etapas"][0]])
        self.w.flot.principal.t_fijar.click()
        self.abrir_accion(self.accion("continua"), self.ids["etapas"][1])
        p = self.w.flot.panel
        (v,) = self.ventanas()
        self.assertEqual(p.vacio.text(), "Haz doble clic sobre la acción continua para desplegar las variables disponibles.")
        self.assertTrue(p.vacio.isVisible())
        self.assertFalse(p.cuerpo.isVisible() or p.izq.isVisible() or p.accion.variable.isVisible())
        self.assertEqual(v.titulo.text(), "Propiedades · Acción")

    def test_SPFL12_continua_en_la_barra_solo_la_frase(self):
        """REQ-EDT-02: con la barra inferior, una acción continua seleccionada no muestra campos, como el lienzo vacío: solo la frase."""
        self.w._cambiar_modo_propiedades("abajo")
        self.abrir_accion(self.accion("continua"), self.ids["etapas"][1])
        p = self.w.props
        self.assertTrue(p.isVisible())
        self.assertEqual(p.vacio.text(), "Haz doble clic sobre la acción continua para desplegar las variables disponibles.")
        self.assertTrue(p.vacio.isVisible())
        self.assertFalse(p.cuerpo.isVisible() or p.izq.isVisible() or p.accion.variable.isVisible())

    # -- SPFL13
    def test_SPFL13_barra_resalta_la_parte_editada(self):
        """REQ-EDT-09: con la barra inferior, al editar una acción condicionada se resalta la condición (foco en los bloques) o el rectángulo de
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
        """REQ-EDT-02: pasar a «abajo» esconde las ventanas y abre la barra; al simular no queda ninguna ventana flotante."""
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


if __name__ == "__main__":
    unittest.main()
