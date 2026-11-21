"""SESC88..SESC89: la memoria de medidas del modelo visual no cambia lo que se dibuja (V2-E4, paso 3)."""
from importlib.util import find_spec
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

QT = bool(find_spec("PySide6"))


@skipUnless(QT, "requiere PySide6")
class MemoriaDeMedidas(TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_SESC88_construir_con_memoria_es_construir_sin_ella_en_todos_los_proyectos(self):
        """REQ-DIB-01: `modelo_visual.construir` da el mismo modelo con la memoria de medidas (en frío y en caliente) que midiendo siempre de
        nuevo, en los ejemplos, los fixtures, GEMMA, el proyecto de 100 etapas y Linea larga, en edición y en simulación tras varios pasos."""
        from escritorio import diagrama as dg
        from escritorio.escena.modelo_visual import construir
        from tools.equivalencia_nucleo import proyectos, vista_de
        from grafcet.editor import Editor
        from grafcet.ids import IdGenerator
        import copy
        comparados = 0
        with TemporaryDirectory() as temporal:
            for nombre, doc, pres in proyectos(temporal):
                with self.subTest(proyecto=nombre):
                    ed = Editor(copy.deepcopy(doc), copy.deepcopy(pres), ids=IdGenerator("eq-"))
                    v = vista_de(ed)
                    M = v.model
                    pos = {s["id"]: (s["x"] + dg.SX, s["y"]) for s in M["steps"]}
                    pos.update({m["id"]: (m["x"] + dg.SX, m["y"]) for m in M.get("macros", [])})
                    self.assertEqual(dg.cajas_parciales(M, pos), dg.cajas_parciales(M, dg.posiciones(M)),
                                     f"{nombre}: los marcos que calcula el recorrido son los que calcularían los realces")
                    estados = [("edicion", {})]
                    if v.s is not None:
                        entradas = sorted(k for k, x in v.s.cm.variables.items() if x.role == "input" and x.type.kind == "bool")
                        for n in range(6):
                            try:
                                if entradas and n % 2 == 1:
                                    v.act("entrada", {"var": entradas[n % len(entradas)]})
                                else:
                                    v.act("avanzar", {"us": 1_000_000})
                            except Exception:  # noqa: BLE001  (una situación sin más evolución: basta con los estados ya vistos)
                                break
                            estados.append(("paso", copy.deepcopy(v.state())))
                    for etiqueta, S in estados:
                        dg.Memoria.vaciar()
                        dg.Memoria.activa = False
                        try:
                            sin = construir(v.model, S, dependencias=True)
                        finally:
                            dg.Memoria.activa = True
                        frio = construir(v.model, S, dependencias=True)
                        caliente = construir(v.model, S, dependencias=True)
                        self.assertEqual(sin, frio, f"{nombre} ({etiqueta}): en frío")
                        self.assertEqual(sin, caliente, f"{nombre} ({etiqueta}): en caliente")
                        comparados += 1
        self.assertGreater(comparados, 40)

    def test_SESC89_la_memoria_tiene_tope_y_su_clave_lleva_la_letra(self):
        """REQ-DIB-01: la memoria de medidas se vacía al llegar a su tope (sigue midiendo bien) y su clave incluye `QFont.key()`: la misma
        medida con otra letra no se confunde; los marcos salen de una sola `cajas_parciales` por dibujo."""
        from escritorio import diagrama as dg
        memoria = dg.Memoria(3)
        for i in range(10):
            self.assertEqual(memoria.obtener((i,), lambda i=i: i * 2), i * 2)
            self.assertLessEqual(len(memoria.datos), 3)
        self.assertNotEqual(dg._letra(12, False, False)[1], dg._letra(12, True, False)[1])
        self.assertNotEqual(dg._letra(12, False, False)[1], dg._letra(12, False, True)[1])
        self.assertNotEqual(dg._letra(12, False, False)[1], dg._letra(14, False, False)[1])
        self.assertEqual(dg._medir_texto("Etapa", 12, False, False), dg._medir_texto("Etapa", 12, False, False))
        self.assertNotEqual(dg._medir_texto("Etapa", 12, False, False), dg._medir_texto("Etapa", 12, True, False))
        self.assertNotEqual(dg._medir_texto("Etapa", 12, False, False), dg._medir_texto("Etapa", 16, False, False))
        from tools.entorno_v2_e0 import GEMMA
        from tools.equivalencia_nucleo import proyectos  # noqa: F401
        llamadas = []
        original = dg.cajas_parciales
        dg.cajas_parciales = lambda *a, **k: (llamadas.append(1), original(*a, **k))[1]
        try:
            from escritorio.escena.modelo_visual import construir
            from grafcet.persistence import open_model
            from escritorio.proyecto_archivo import abrir_grafnet
            from escritorio.sello import CLAVE
            from grafcet.view import layout_from_presentation
            from tools.equivalencia_nucleo import vista_de
            from grafcet.editor import Editor
            from grafcet.ids import IdGenerator
            import copy
            contenedor = abrir_grafnet(GEMMA, CLAVE)
            try:
                abierto = open_model(contenedor.raiz)
                ed = Editor(copy.deepcopy(abierto.doc), copy.deepcopy((abierto.presentations or [{}])[0]), ids=IdGenerator("eq-"))
            finally:
                contenedor.cerrar()
            v = vista_de(ed)
            construir(v.model, {}, sel={v.model["steps"][0]["id"]}, dependencias=True)
        finally:
            dg.cajas_parciales = original
        self.assertEqual(len(llamadas), 1)


@skipUnless(QT, "requiere PySide6")
class TextosEnElSitio(TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def imagen(escena):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QImage, QPainter
        r = escena.itemsBoundingRect().adjusted(-10, -10, 10, 10)
        im = QImage(int(r.width()) + 1, int(r.height()) + 1, QImage.Format.Format_ARGB32)
        im.fill(QColor("white"))
        p = QPainter(im)
        escena.render(p, QRectF(0, 0, im.width(), im.height()), r)
        p.end()
        return im

    def test_SESC90_un_texto_actualizado_en_el_sitio_se_ve_igual_que_creado_de_nuevo(self):
        """REQ-DIB-01: un texto cuyo contenido o color cambian se actualiza en el ítem que ya está en la escena y da la misma imagen, al
        píxel, que crearlo de nuevo (etiquetas de etapa activa o inactiva, receptividades con su verdad, valores, temporizadores, acciones)."""
        import copy
        from PySide6.QtWidgets import QGraphicsScene
        from escritorio.escena.escena import EscenaIncremental
        from escritorio.escena.modelo_visual import construir
        from escritorio.escena import realizador
        from tools.equivalencia_nucleo import proyectos, vista_de
        from grafcet.editor import Editor
        from grafcet.ids import IdGenerator
        cambiados = comparados = 0
        enplace = []
        original = realizador.actualizar

        def vigila(items, antes, ahora):
            ok = original(items, antes, ahora)
            if ok and ahora[0] == "texto" and (ahora[1] != antes[1] or ahora[2] != antes[2]):
                enplace.append(1)
            return ok
        realizador.actualizar = vigila
        try:
            with TemporaryDirectory() as temporal:
                for nombre, doc, pres in proyectos(temporal):
                    if not nombre.startswith(("aula/aula_temporizacion", "aula/aula_marcha", "aula/aula_macro", "fixtures/referencia/guia_gemma")):
                        continue
                    ed = Editor(copy.deepcopy(doc), copy.deepcopy(pres), ids=IdGenerator("eq-"))
                    v = vista_de(ed)
                    if v.s is None:
                        continue
                    entradas = sorted(k for k, x in v.s.cm.variables.items() if x.role == "input" and x.type.kind == "bool")
                    escena = EscenaIncremental(None)
                    for n in range(8):
                        try:
                            if n:
                                v.act("entrada", {"var": entradas[n % len(entradas)]}) if entradas and n % 2 else v.act("avanzar", {"us": 700_000})
                        except Exception:  # noqa: BLE001
                            break
                        S = copy.deepcopy(v.state())
                        mv = construir(v.model, S, dependencias=True)
                        escena.aplicar(mv)
                        fresca = EscenaIncremental(None)
                        fresca.aplicar(mv)
                        with self.subTest(proyecto=nombre, paso=n):
                            self.assertTrue(self.imagen(escena) == self.imagen(fresca), "la imagen del texto actualizado difiere")
                        comparados += 1
        finally:
            realizador.actualizar = original
        self.assertGreater(comparados, 16)
        self.assertGreater(len(enplace), 10, "la prueba debe ejercitar textos actualizados en el sitio")
