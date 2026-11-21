"""SESC43..SESC48: los enlaces viven en el modelo de la vista, sin caché global de rutas (V2-E3, paso 6)."""
from importlib.util import find_spec
from unittest import TestCase, mock, skipUnless

QT = bool(find_spec("PySide6"))


@skipUnless(QT, "requiere PySide6")
class EnlacesSinCache(TestCase):
    def setUp(self):
        from tools.choque_escena import reiniciar
        from tools.entorno_v2_e0 import GEMMA, ventana
        self.contexto = ventana()
        self.w = self.contexto.__enter__()
        self.addCleanup(self.contexto.__exit__, None, None, None)
        reiniciar(self.w, GEMMA)
        self.e = self.w.edicion

    def limpios(self, M):
        from escritorio.geometria.enlaces import _ajustar_enlaces
        from grafcet import routing
        return _ajustar_enlaces(M, routing.enlaces(M))

    def test_SESC43_no_queda_cache_global_de_rutas(self):
        """REQ-EDT-01: ya no existen `rutas_diagrama`, `geometria.rutas` ni el nombre `rutas` en la fachada de Edicion."""
        import importlib
        import escritorio.edicion as ed
        for modulo in ("escritorio.rutas_diagrama", "escritorio.geometria.rutas"):
            with self.assertRaises(ModuleNotFoundError, msg=modulo):
                importlib.import_module(modulo)
        self.assertFalse(hasattr(ed, "rutas"))

    def test_SESC44_enlaces_lee_el_modelo_sin_recalcular_el_recorrido(self):
        """REQ-EDT-01: tras reconstruir, `enlaces(M)` no vuelve a llamar a `routing.enlaces`, por muchas veces que se pida."""
        from escritorio.diagrama import enlaces
        from grafcet import routing
        with mock.patch.object(routing, "enlaces", wraps=routing.enlaces) as calcular:
            for _ in range(20):
                enlaces(self.e.M)
        calcular.assert_not_called()

    def test_SESC45_reconstruir_calcula_el_recorrido_una_sola_vez(self):
        """REQ-EDT-01: una reconstrucción hace una sola llamada a `routing.enlaces` (la de la `Vista`) cuando no hay nombres con
        comillas invertidas que cambien el ancho de los textos."""
        from grafcet import routing
        with mock.patch.object(routing, "enlaces", wraps=routing.enlaces) as calcular:
            self.e.reconstruir()
        self.assertEqual(calcular.call_count, 1)

    def test_SESC46_quitar_comillas_dice_si_cambio_algo(self):
        """REQ-EDT-01: `quitar_comillas_vista` devuelve si cambió algún texto (entonces el recorrido se recalcula)."""
        from escritorio.edicion.utilidades import quitar_comillas_vista
        M = {"transitions": [{"cond": [{"t": "`Mi variable` y x"}]}], "steps": [{"actions": [{"text": [{"t": "A"}]}]}]}
        self.assertTrue(quitar_comillas_vista(M))
        self.assertEqual(M["transitions"][0]["cond"][0]["t"], "Mi variable y x")
        self.assertFalse(quitar_comillas_vista(M))

    def test_SESC47_enlaces_coincide_con_el_calculo_en_limpio_tras_cualquier_operacion(self):
        """REQ-EDT-01: tras 40 operaciones al azar, `enlaces(M)` es el cálculo en limpio y `recalcular` lo rehace tras tocar `M`
        a mano."""
        from escritorio.diagrama import enlaces
        from escritorio.geometria.enlaces import recalcular
        from tools import choque_escena as c
        for reg in c.generar(47, 40):
            try:
                c.aplicar(self.w, reg)
            except Exception as exc:  # noqa: BLE001
                if not c._aviso_de_interfaz(exc):
                    raise
            if self.w.modo == "editar":
                self.assertEqual(enlaces(self.e.M), self.limpios(self.e.M), reg["op"])
        if self.w.modo != "editar":
            self.w.a_ejecutar.trigger()
        M = self.e.M
        giro = M["transitions"][0]
        giro["orient"] = "derecha"
        self.assertNotEqual(enlaces(M), self.limpios(M), "tocar M a mano no actualiza los enlaces por sí solo")
        recalcular(M)
        self.assertEqual(enlaces(M), self.limpios(M))

    def test_SESC48_un_modelo_sin_enlaces_calculados_se_resuelve_sin_recordar(self):
        """REQ-SIM-01: el modelo de una vista de simulación (que trae `links` pero no `enlaces`) y uno hecho a mano se resuelven
        al pedirlos, y no se guardan en ninguna parte."""
        from escritorio.diagrama import enlaces
        M = {k: v for k, v in self.e.M.items() if k not in ("enlaces",)}
        self.assertEqual(enlaces(M), self.limpios(M))
        self.assertNotIn("enlaces", M)
        sin_links = {k: v for k, v in M.items() if k not in ("links",)}
        self.assertEqual(enlaces(sin_links), self.limpios(sin_links))

    def seleccion(self):
        """Tres etapas y dos transiciones seguidas de GEMMA."""
        e = self.e
        t = next(t for t in e.ed.model["transitions"] if t["preRefs"] and t["postRefs"])
        pasos = list(dict.fromkeys([*t["preRefs"], *t["postRefs"]]))
        t2 = next((u for u in e.ed.model["transitions"] if u["id"] != t["id"] and set(u["preRefs"]) & set(pasos)), None)
        refs = [t["id"], *pasos] + ([t2["id"], *t2["postRefs"], *t2["preRefs"]] if t2 else [])
        return list(dict.fromkeys(refs))

    def test_SESC49_un_dibujo_vinculado_solo_pinta_los_enlaces_de_su_seleccion(self):
        """REQ-EDT-01: la copia filtrada de una selección (hojas y planos) no conserva los recorridos de toda la vista: `enlaces` da
        el cálculo limpio de lo que queda y se pintan los mismos ítems que sin la clave `enlaces`."""
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio import diagrama as dg
        from escritorio.diagrama import enlaces
        from escritorio.hojas import dibujo_vinculado
        from escritorio.geometria.enlaces import _ajustar_enlaces
        from grafcet import routing
        refs = self.seleccion()
        salida = dibujo_vinculado(self.e, refs)
        limpios = _ajustar_enlaces(salida, routing.enlaces(salida))
        self.assertEqual(enlaces(salida), limpios)
        self.assertLess(len(enlaces(salida)), len(self.e.M["enlaces"]))
        sin_clave = {k: v for k, v in salida.items() if k not in ("enlaces", "_enlaces_de")}
        a, b, completa = QGraphicsScene(), QGraphicsScene(), QGraphicsScene()
        dg.dibujar(a, salida, {})
        dg.dibujar(b, sin_clave, {})
        dg.dibujar(completa, self.e.M, {})
        self.assertEqual(len(a.items()), len(b.items()))
        self.assertLess(len(a.items()), len(completa.items()) // 2)

    def test_SESC50_un_documento_de_hoja_vacio_no_dibuja_enlaces(self):
        """REQ-EDT-01: `DocumentoHoja` vacía las listas del modelo y no puede conservar los recorridos de la vista completa."""
        from escritorio.diagrama import enlaces
        from escritorio.laminas import DocumentoHoja
        d = DocumentoHoja({**self.e.M, "_graficos": []}, {}, {})
        self.assertEqual(enlaces(d.modelo), [])
        self.assertEqual(d.escena.items(), [])

    def test_SESC51_los_recorridos_valen_solo_con_las_mismas_listas(self):
        """REQ-EDT-01: sustituir `links`, etapas, transiciones, barras o estilos invalida `M["enlaces"]`; copiar `M` lo conserva."""
        import copy
        from escritorio.diagrama import enlaces
        from escritorio.geometria.enlaces import _ENTRADAS
        M = self.e.M
        self.assertIs(enlaces(M), M["enlaces"])
        copia = copy.deepcopy(M)
        self.assertIs(enlaces(copia), copia["enlaces"], "una copia completa conserva los recorridos vigentes")
        self.assertEqual(enlaces(copia), M["enlaces"])
        for clave in _ENTRADAS:
            otra = copy.deepcopy(M)
            otra[clave] = type(otra[clave])(otra[clave])  # una lista o diccionario nuevo con lo mismo
            self.assertIsNot(enlaces(otra), otra["enlaces"], clave)
        parcial = copy.deepcopy(M)
        parcial["transitions"] = parcial["transitions"][:3]
        parcial["links"] = [l for l in parcial["links"] if l["tid"] in {t["id"] for t in parcial["transitions"]}]
        self.assertTrue(all(l["tid"] in {t["id"] for t in parcial["transitions"]} for l in enlaces(parcial)))
