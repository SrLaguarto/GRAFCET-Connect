"""SESC60..SESC65: la lupa de Propiedades aplica solo la diferencia del modelo visual (V2-E3, paso 8)."""
from importlib.util import find_spec
from unittest import TestCase, mock, skipUnless

QT = bool(find_spec("PySide6"))


@skipUnless(QT, "requiere PySide6")
class LupaIncremental(TestCase):
    def setUp(self):
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, bombear, ventana
        self.contexto = ventana()
        self.w = self.contexto.__enter__()
        self.addCleanup(self.contexto.__exit__, None, None, None)
        reiniciar(self.w, GEMMA)
        self.e = self.w.edicion
        self.tid = self.e.ed.model["transitions"][2]["id"]
        self.w.editar_condicion(self.tid)
        bombear()
        self.lupa = self.w.flot.principal.lupa
        self.sc = self.lupa._escena

    def mover(self, sid, dx):
        from PySide6.QtCore import QPointF
        from escritorio.diagrama import posiciones
        o = QPointF(*posiciones(self.e.M)[sid])
        self.e.prensar(o)
        self.e.mover(o + QPointF(dx, 0))
        self.e.soltar(o + QPointF(dx, 0))

    def comprobar(self):
        from tools import choque_escena as c
        c.comprobar_lupa(self.w, "test")

    def test_SESC60_la_lupa_usa_una_escena_incremental_y_coincide_con_el_dibujo_directo(self):
        """REQ-EDT-01: la lupa tiene registro de objetos y su escena es la del dibujo directo del modelo del editor."""
        from escritorio.escena.escena import EscenaIncremental
        self.assertIsInstance(self.sc, EscenaIncremental)
        self.assertIsNotNone(self.sc.modelo)
        self.assertIs(self.lupa._modelo, self.e.M)
        self.comprobar()

    def test_SESC61_un_cambio_pequeno_solo_crea_lo_que_cambia_y_conserva_los_demas_items(self):
        """REQ-EDT-01: mover una etapa crea muy pocos ítems en la lupa, los de lo lejano conservan su identidad y no se rehace."""
        from PySide6.QtWidgets import QGraphicsTextItem
        from escritorio.escena import realizador
        lejos = self.e.ed.model["steps"][-1]["id"]
        textos = {id(i) for i in self.sc.items() if isinstance(i, QGraphicsTextItem) and lejos in (i.data(43) or ())}
        total = len(self.sc.items())
        sid = next(s["id"] for s in self.e.ed.model["steps"] if s["label"] == "100")
        with mock.patch.object(realizador, "crear", wraps=realizador.crear) as crear, \
                mock.patch.object(self.sc, "_rehacer", wraps=self.sc._rehacer) as rehacer:
            self.mover(sid, -80)
        self.assertFalse(rehacer.called)
        self.assertLess(crear.call_count, total // 3)
        self.assertTrue(textos <= {id(i) for i in self.sc.items()})
        self.comprobar()

    def test_SESC62_un_modelo_igual_no_toca_la_escena_y_la_misma_identidad_no_redibuja(self):
        """REQ-EDT-01: preparar el dibujo con el mismo modelo no hace nada; con otro modelo de igual contenido, la diferencia
        sale vacía y no se crea ningún ítem."""
        import copy
        from escritorio.escena import realizador
        antes = [id(i) for i in self.sc.items()]
        with mock.patch.object(realizador, "crear", wraps=realizador.crear) as crear, \
                mock.patch.object(realizador, "actualizar", wraps=realizador.actualizar) as actualizar:
            self.lupa.preparar_dibujo(self.e.M, self.lupa._dependencias)
            self.lupa.preparar_dibujo(copy.deepcopy(self.e.M), self.lupa._dependencias)
        self.assertEqual((crear.call_count, actualizar.call_count), (0, 0))
        self.assertEqual([id(i) for i in self.sc.items()], antes)

    def test_SESC63_si_construir_falla_la_lupa_conserva_su_escena_y_su_modelo(self):
        """REQ-EDT-09: una excepción al construir deja la escena de la lupa y su modelo como estaban."""
        from escritorio import flotantes
        antes, modelo = [id(i) for i in self.sc.items()], self.lupa._modelo
        with mock.patch.object(flotantes, "construir", side_effect=KeyError("fallo simulado")):
            with self.assertRaises(KeyError):
                self.lupa.preparar_dibujo({**self.e.M}, self.lupa._dependencias)
        self.assertEqual([id(i) for i in self.sc.items()], antes)
        self.assertIs(self.lupa._modelo, modelo)

    def test_SESC64_pintar_la_lupa_no_deja_items_ocultos_y_su_imagen_es_la_del_dibujo_directo(self):
        """REQ-EDT-01: `paintEvent` oculta los vecinos mientras pinta y los restituye; la imagen de la lupa es idéntica a la que daba
        con la escena dibujada entera con el dibujo directo."""
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio import diagrama as dg
        sid = self.e.ed.model["steps"][3]["id"]
        self.mover(sid, 60)
        incremental = self.lupa.grab().toImage()
        self.assertTrue(all(i.isVisible() for i in self.sc.items()))
        directa = QGraphicsScene()
        dg.dibujar_directo(directa, self.lupa._modelo, {}, None, None, None, [], [], self.lupa._dependencias)
        propia, self.lupa._escena = self.lupa._escena, directa
        try:
            esperada = self.lupa.grab().toImage()
        finally:
            self.lupa._escena = propia
        self.assertFalse(incremental.isNull())
        self.assertEqual(incremental, esperada)
        self.comprobar()


@skipUnless(QT, "requiere PySide6")
class LupaChoque(TestCase):
    def test_SESC65_la_prueba_de_choque_detecta_un_fallo_en_la_lupa_y_pasa_sin_el(self):
        """REQ-EDT-09: si la lupa pierde una figura, ESC-3 lo detecta; con 60 operaciones al azar y la lupa abierta a ratos, sin el
        fallo no hay ninguna diferencia."""
        from escritorio.escena.escena import EscenaIncremental
        from tools import choque_escena as c
        from tools.entorno_v2_e0 import GEMMA
        original = EscenaIncremental.aplicar

        def pierde_en_la_lupa(escena, mv):
            original(escena, mv)
            if escena.parent().__class__.__name__ == "Lupa" and escena.modelo is not None:
                for nodo in escena.nodos.values():
                    if nodo and nodo[0][1] and nodo[0][1][0].scene() is escena:
                        escena.removeItem(nodo[0][1][0])
                        break
        base = {"k2": 0, "dx": 100, "dy": 0, "v": 0, "auto": []}
        secuencia = [{**base, "op": "propiedades", "k": 3}, {**base, "op": "mover", "k": 5, "mitad": None},
                     {**base, "op": "mover", "k": 9, "mitad": None}]
        with mock.patch.object(EscenaIncremental, "aplicar", pierde_en_la_lupa):
            f = c.ejecutar_nuevo(GEMMA, secuencia)
        self.assertIsNotNone(f, "no se detectó la figura perdida en la lupa")
        self.assertIn(f.tipo, ("ESC-1", "ESC-3"))
        self.assertIsNone(c.ejecutar_nuevo(GEMMA, c.generar(13, 60)))
