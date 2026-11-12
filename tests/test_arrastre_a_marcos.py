"""Grafcet parcial recién soltado y arrastre de elementos a otro marco (encargo 11 del rediseño, B1 y B2).

B1: un grafcet parcial recién soltado (marco vacío, sin etapas ni transiciones en todo el dibujo) se ve en el acto.
B2: arrastrar elementos ya dibujados y soltarlos con el puntero dentro del marco de un grafcet parcial o del recinto de una
encapsulante, distinto del suyo, los pasa a ese parcial con las reglas de cortar y pegar dentro, en una sola operación de
deshacer; el marco de destino se resalta mientras se arrastra. Ninguna es oráculo del documento 11.
"""
import unittest
from pathlib import Path

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication
    from escritorio.diagrama import cajas_parciales, SX


def _centro(b):
    return QPointF((b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2)


@unittest.skipUnless(QT, "Falta PySide6")
class ArrastreAMarcos(BaseQt):
    def setUp(self):
        super().setUp()
        self.w.resize(1360, 860)
        self.w.show()
        self.w, self.e = self.vacio()
        QApplication.processEvents()
        self.addCleanup(self.w.hide)

    @staticmethod
    def png(nombre):
        carpeta = Path(__file__).resolve().parent.parent / "artifacts" / "arrastre_marcos"
        carpeta.mkdir(parents=True, exist_ok=True)
        return str(carpeta / f"{nombre}.png")

    def foto(self, nombre, encajar=True):
        """Captura de la ventana a 2000×1250 (para revisar a ojo); con `encajar`, con todo el dibujo a la vista."""
        self.w.resize(2000, 1250)
        QApplication.processEvents()
        if encajar:
            self.w.diagrama.ajustar()
            QApplication.processEvents()
        self.w.grab().save(self.png(nombre))

    def items(self):
        return len(self.w.diagrama.scene().items())

    def por_nombre(self):
        """{nombre: (parcial, posición)} de las etapas y transiciones del modelo."""
        e = self.e
        from escritorio.diagrama import posiciones
        pos = posiciones(e.M)
        return {e.nombres[i]: (e.parcial_de(i), pos[i]) for i in pos if i in e.nombres}

    def cadena_dos_etapas(self):
        """0 -[marcha]-> 1, a la izquierda del dibujo (en el parcial raíz)."""
        ids = self.cadena(self.e, filas=((60, "0"), (140, None), (220, "1")), entradas=("marcha",))
        self.e.seleccionar([])
        return ids

    def arrastrar(self, ids, desde, hasta, pasos=4, parar_antes=False):
        """Selecciona `ids`, pulsa en `desde` y arrastra con el puntero hasta `hasta` (suelta salvo `parar_antes`)."""
        e = self.e
        e.seleccionar(list(ids))
        e.prensar(desde)
        for k in range(1, pasos + 1):
            e.mover(desde + (hasta - desde) * (k / pasos))
        if not parar_antes:
            e.soltar(hasta)

    # -- B1 ----------------------------------------------------------------------------------------------------
    def test_SARM01_un_parcial_recien_soltado_se_ve_sin_otra_accion(self):
        """REQ-EDT-02: soltar la ficha «Grafcet parcial» en un dibujo sin etapas ni transiciones deja su marco en la escena
        enseguida (antes no se dibujaba hasta soltar otro elemento); igual con «Encapsulante» y «Macroetapa»."""
        e = self.e
        self.assertEqual(self.items(), 0)
        self.soltar_ficha("parcial", QPointF(400, 300))
        (g,) = [q["id"] for q in e.M["partials"] if q.get("vacio")]
        self.assertIn(g, cajas_parciales(e.M))
        self.assertGreater(self.items(), 0, "el marco vacío está dibujado justo después de soltar")
        n = self.items()
        self.soltar_ficha("parcial", QPointF(900, 300))
        self.assertGreater(self.items(), n, "y el segundo, también")
        for tipo, x in (("encapsulante", 400), ("macroetapa", 650)):
            n = self.items()
            self.soltar_ficha(tipo, QPointF(x, 700))
            self.assertGreater(self.items(), n, tipo)

    # -- B2 ----------------------------------------------------------------------------------------------------
    def test_SARM02_arrastrar_un_grafcet_a_un_parcial_lo_mete_en_el_parcial(self):
        """REQ-EDT-02, REQ-EDT-14: un grafcet de dos etapas y una transición, arrastrado con el puntero hasta dentro de un grafcet
        parcial vacío, pasa a ser de ese parcial (con las posiciones relativas y el desplazamiento del arrastre); una sola
        operación de deshacer, que lo devuelve al raíz."""
        e = self.e
        ids = self.cadena_dos_etapas()
        g = e.poner_parcial(QPointF(900, 450))
        e.seleccionar([])
        antes_nombres = self.por_nombre()
        self.assertEqual({p for p, _ in antes_nombres.values()}, {e.raiz})
        estado, n = self.estado(e), len(e.ed.undo_stack)
        destino = _centro(cajas_parciales(e.M)[g])
        desde = QPointF(SX, 60)
        self.arrastrar(ids, desde, destino)
        despues = self.por_nombre()
        self.assertEqual(set(despues), set(antes_nombres), "mismos elementos (nombres)")
        self.assertEqual({p for p, _ in despues.values()}, {g}, "ahora son del parcial")
        d = destino - desde
        corrimientos = {(despues[n][1][0] - x, despues[n][1][1] - y) for n, (_, (x, y)) in antes_nombres.items()}
        self.assertEqual(len(corrimientos), 1, "todos se desplazan lo mismo: posiciones relativas conservadas")
        (cx, cy), = corrimientos
        self.assertTrue(abs(cx - d.x()) <= 10 and abs(cy - d.y()) <= 10, "el desplazamiento del arrastre (ajustado a la rejilla)")
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación de deshacer")
        self.assertTrue(e.ed.validate().diagnostics is not None)
        self.assertEqual(len(e.ed.model["steps"]), 2)
        self.assertFalse(next(q for q in e.M["partials"] if q["id"] == g).get("vacio"), "el marco ya es el de sus etapas")
        e.deshacer()
        self.assertEqual(self.estado(e), estado)
        self.assertEqual({p for p, _ in self.por_nombre().values()}, {e.raiz})
        e.rehacer()
        self.assertEqual({p for p, _ in self.por_nombre().values()}, {g})

    def test_SARM03_se_resalta_el_marco_de_destino_mientras_se_arrastra(self):
        """REQ-UX-01: con el puntero sobre el marco de un grafcet parcial, ese marco se recuadra (borde de acento); fuera de él o
        sobre el marco en el que ya están los elementos, no se recuadra nada; al soltar desaparece."""
        w, e = self.w, self.e
        ids = self.cadena_dos_etapas()
        g = e.poner_parcial(QPointF(900, 450))
        caja = cajas_parciales(e.M)[g]
        desde = QPointF(SX, 60)
        self.foto("antes")  # (encaja el dibujo en la ventana grande: las capturas de después no vuelven a encajarlo)
        e.seleccionar(ids)
        e.prensar(desde)
        e.mover(QPointF(SX + 300, 200))
        e.mover(QPointF(SX + 301, 201))
        self.assertIsNone(w.diagrama.destino, "en un hueco: nada recuadrado")
        e.mover(_centro(caja))
        self.assertIsNotNone(w.diagrama.destino, "sobre el marco del parcial")
        r = w.diagrama.destino.rect()
        self.assertEqual((r.left(), r.top(), r.right(), r.bottom()),
                         (caja["x0"] - 4, caja["y0"] - 4, caja["x1"] + 4, caja["y1"] + 4))
        self.assertEqual(w.diagrama.prohibidos, [], "sin marcas de «encima de otro elemento»")
        self.foto("resaltado", encajar=False)
        e.mover(QPointF(SX + 300, 200))
        self.assertIsNone(w.diagrama.destino, "al salir del marco se quita")
        e.mover(_centro(caja))
        e.soltar(_centro(caja))
        self.assertIsNone(w.diagrama.destino, "al soltar se quita")
        self.foto("resultado", encajar=False)

    def test_SARM04_arrastrar_al_recinto_de_una_encapsulante(self):
        """REQ-EDT-02, REQ-EDT-14: igual que con un parcial, soltar un grafcet dentro del recinto de una encapsulante lo hace del
        recinto."""
        e = self.e
        ids = self.cadena_dos_etapas()
        e.colocar("encapsulante", QPointF(SX + 700, 120))
        enc = e.sel[0]
        e.pedir_texto = lambda *a: "R"
        r = e.anadir_recinto(enc)
        caja = cajas_parciales(e.M)[r]
        e.seleccionar([])
        n = len(e.ed.undo_stack)
        self.arrastrar(ids, QPointF(SX, 60), _centro(caja))
        despues = self.por_nombre()
        self.assertEqual({despues[k][0] for k in ("0", "1")}, {r})
        self.assertEqual(despues["0"][0], r)
        self.assertEqual(len(e.ed.undo_stack), n + 1, "una sola operación de deshacer")
        e.deshacer()
        self.assertEqual({p for k, (p, _) in self.por_nombre().items() if k in ("0", "1")}, {e.raiz})

    def test_SARM05_soltar_fuera_o_en_el_mismo_marco_solo_mueve(self):
        """REQ-EDT-02: soltar en un hueco, o dentro del marco en el que ya estaban, no cambia la pertenencia (solo mueve, como
        hasta ahora): sin elementos nuevos ni IDs distintos."""
        e = self.e
        ids = self.cadena_dos_etapas()
        g = e.poner_parcial(QPointF(900, 450))
        e.seleccionar([])
        self.arrastrar(ids, QPointF(SX, 60), QPointF(SX + 200, 260))  # a un hueco
        self.assertEqual({p for p, _ in self.por_nombre().values()}, {e.raiz})
        self.assertEqual({i["id"] for i in e.ed.model["steps"]} | {t["id"] for t in e.ed.model["transitions"]}, set(ids))
        # ya dentro del parcial: moverlos dentro del mismo marco conserva los IDs
        self.arrastrar(ids, QPointF(SX + 200, 260), _centro(cajas_parciales(e.M)[g]))
        nuevos = [i for i in e.nombres if e.parcial_de(i) == g]
        self.assertEqual(len(nuevos), 3)
        marcados = set(nuevos)
        pos = {i: p for i, p in __import__("escritorio.diagrama", fromlist=["posiciones"]).posiciones(e.M).items()}
        a = pos[next(i for i in nuevos if e.nombres[i] == "0")]
        n = len(e.ed.undo_stack)
        self.arrastrar(nuevos, QPointF(*a), QPointF(a[0] + 20, a[1] + 20))
        self.assertEqual({i for i in e.nombres if e.parcial_de(i) == g}, marcados, "mismos IDs: no se recreó nada")
        self.assertEqual(len(e.ed.undo_stack), n + 1)

    def test_SARM06_un_elemento_suelto_tambien_entra_y_sacarlo_no_cambia_su_pertenencia(self):
        """REQ-EDT-02: una etapa sola arrastrada a un marco pasa a ser suyo; sacarla a un hueco la mueve pero sigue siendo del
        parcial (como hoy: mover a otro marco es solo de presentación)."""
        e = self.e
        e.colocar("etapa", QPointF(SX + 100, 100))
        s = e.sel[0]
        g = e.poner_parcial(QPointF(900, 450))
        e.seleccionar([])
        self.arrastrar([s], QPointF(SX + 100, 100), _centro(cajas_parciales(e.M)[g]))
        (nueva,) = [q["id"] for q in e.ed.model["steps"]]
        self.assertEqual(e.parcial_de(nueva), g)
        from escritorio.diagrama import posiciones
        x, y = posiciones(e.M)[nueva]
        self.arrastrar([nueva], QPointF(x, y), QPointF(SX + 100, 650))
        (otra,) = [q["id"] for q in e.ed.model["steps"]]
        self.assertEqual((otra, e.parcial_de(otra)), (nueva, g), "sacarla no cambia su parcial: solo se mueve")


if __name__ == "__main__":
    unittest.main()
