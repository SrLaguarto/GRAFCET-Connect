"""SAA1..SAA5: encargo AA (1.1.7): parpadeo naranja falso, cajas y textos de acciones que no desaparecen, entradas que no
bailan y última carpeta de proyectos."""
import random
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
FIX = ROOT / "tests" / "fixtures" / "aa117"

from test_editor_cadenas import BaseQt, QT  # noqa: E402

if QT:
    from PySide6.QtCore import QPoint, QPointF, QRectF
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication
    from escritorio import edicion as modulo
    from escritorio.diagrama import posiciones


@unittest.skipUnless(QT, "requiere PySide6")
class EncargoAA(BaseQt):
    def abrir(self, nombre, ancho=1366, alto=768):
        w = self.w
        w.resize(ancho, alto)
        w.show()
        self.pasar_arranque(w)
        self.asentar_escala(w)
        copia = Path(self.tmp.name) / nombre
        shutil.copy(FIX / nombre, copia)
        self.assertTrue(w.abrir_ruta(copia))
        self.bombear()
        return w, w.edicion

    @staticmethod
    def bombear(n=8):
        for _ in range(n):
            QApplication.processEvents()

    def test_SAA1_anadir_una_accion_no_hace_parpadear_la_etapa_de_la_banderita(self):
        """REQ-EDT-09: la acción condicionada con su banderita ya rozaba un texto de transición antes de la operación; añadir otra
        acción a esa etapa no es «quedar encima» y no hace parpadear nada ni muestra el aviso."""
        w, e = self.abrir("desaparece.grafnet")
        sid = next(s["id"] for s in e.M["steps"] if s["label"] == "2")
        x, y = posiciones(e.M)[sid]
        for _ in range(2):
            e.colocar("accion:continua", QPointF(x + 300, y))
            self.bombear()
            self.assertEqual(e.parpadeo.ids, set(), "no parpadea nada")
            self.assertNotEqual(e.mensaje, modulo.MSG_ENCIMA)

    def _comprobar_acciones(self, d):
        sc = d.scene()
        for c in d.cajas_acciones:
            r = QRectF(*c["rect"])
            rects = [i for i in sc.items(r.center()) if type(i).__name__ == "QGraphicsRectItem" and i.isVisible()
                     and abs(i.sceneBoundingRect().width() - r.width()) < 3]
            textos = [i for i in sc.items(r) if type(i).__name__ == "QGraphicsTextItem" and i.isVisible()
                      and r.contains(i.sceneBoundingRect().center())]
            self.assertTrue(rects, f"caja de {c['id']}")
            self.assertTrue(textos and all(t.toPlainText() for t in textos), f"texto de {c['id']}")

    def _borde_izquierdo_oscuro(self, d, c):
        pm = QPixmap(d.viewport().size())
        d.viewport().render(pm)
        im = pm.toImage()
        p = d.mapFromScene(QPointF(c["rect"][0], c["rect"][1] + c["rect"][3] / 2))
        if not d.viewport().rect().adjusted(4, 4, -4, -4).contains(p):
            return True
        return min((im.pixel(p.x() + dx, p.y()) & 0xff) for dx in (-1, 0, 1)) < 140

    def test_SAA2_con_errores_tras_desplazar_y_zoom_cada_accion_conserva_su_caja(self):
        """REQ-EDT-09: con «Mostrar errores», desplazando y acercando, cada acción mantiene su caja y su texto en la escena y en
        lo que se pinta."""
        w, e = self.abrir("desaparece.grafnet")
        w.b_errores.setChecked(True)
        self.bombear()
        d = w.diagrama
        azar = random.Random(4)
        for i in range(12):
            d.verticalScrollBar().setValue(d.verticalScrollBar().value() + azar.randint(-60, 60))
            d.horizontalScrollBar().setValue(d.horizontalScrollBar().value() + azar.randint(-60, 60))
            if i % 3 == 0:
                d.zoom(azar.choice([1.1, 0.9]), QPointF(300, 200))
            self.bombear(3)
            self._comprobar_acciones(d)
            for c in d.cajas_acciones:
                self.assertTrue(self._borde_izquierdo_oscuro(d, c), f"borde de {c['id']} en el paso {i}")

    def test_SAA3_200_pasos_de_simulacion_no_pierden_texto_ni_caja(self):
        """REQ-SIM-01: durante 200 cambios de entrada, ninguna acción pierde su caja ni su texto."""
        w, e = self.abrir("reto6.grafnet")
        w.a_ejecutar.setChecked(True)
        self.bombear(20)
        d = w.diagrama
        entradas = [v for v, b in w.botones.items() if hasattr(b, "lineas_visibles")]
        azar = random.Random(5)
        for _ in range(200):
            v = azar.choice(entradas)
            if w.botones[v].isEnabled():
                w._act("entrada", var=v)
            self.bombear(2)
            self._comprobar_acciones(d)
        w.a_ejecutar.setChecked(False)

    def test_SAA4_las_entradas_no_bailan_al_alternar_su_estado(self):
        """REQ-SIM-01: al pasar una entrada de 0 a 1 y de 1 a 0 no cambian ni la posición y el alto de las fichas ni el desplazamiento
        de la lista (el alto de la ficha no depende del estado, a las dos escalas)."""
        for ancho, alto in ((1366, 768), (2000, 1250)):
            with self.subTest(ancho=ancho):
                w, e = self.abrir("reto6.grafnet", ancho, alto)
                w.a_ejecutar.setChecked(True)
                self.bombear(20)
                sc = w.sc_entradas
                fichas = {v: b for v, b in w.botones.items() if hasattr(b, "lineas_visibles")}

                def medir():
                    return ({v: (b.mapTo(w.cont_rejilla, QPoint(0, 0)).y(), b.height()) for v, b in fichas.items()},
                            sc.verticalScrollBar().value(), sc.verticalScrollBar().maximum())
                sc.verticalScrollBar().setValue(sc.verticalScrollBar().maximum() // 2)
                self.bombear(3)
                base = medir()
                for v in fichas:
                    w._act("entrada", var=v)
                    self.bombear(5)
                    self.assertEqual(medir(), base, f"al activar {w.nombre(v)}")
                    w._act("entrada", var=v)
                    self.bombear(5)
                    self.assertEqual(medir(), base, f"al desactivar {w.nombre(v)}")
                w.a_ejecutar.setChecked(False)

    # -- AA5 --------------------------------------------------------------------------------------------------------
    def _carpetas(self):
        docs = Path(self.tmp.name) / "docs"
        docs.mkdir()
        parche = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=str(docs))
        parche.start()
        self.addCleanup(parche.stop)
        return docs

    def test_SAA5_se_recuerda_la_carpeta_tras_abrir_y_tras_guardar(self):
        """REQ-EDT-01: «Abrir» y «Guardar como» empiezan en la última carpeta con la que se abrió o guardó un .grafnet."""
        from escritorio.carpetas import asegurar_carpetas
        self._carpetas()
        w, e = self.vacio()
        defecto = asegurar_carpetas()["grafcet"]
        self.assertEqual(w.carpeta_proyectos(), defecto)
        uno = Path(self.tmp.name) / "uno"
        uno.mkdir()
        copia = uno / "a.grafnet"
        shutil.copy(FIX / "reto6.grafnet", copia)
        e.ed.dirty = False
        self.assertTrue(w.abrir_ruta(copia))
        self.assertEqual(w.ajustes.value("archivos/ultima_carpeta"), str(uno))
        with mock.patch("escritorio.ventana.QFileDialog.getOpenFileName", return_value=("", "")) as dlg:
            w.abrir()
        self.assertEqual(Path(dlg.call_args.args[2]), uno)
        w.edicion.ed.dirty = False
        dos = Path(self.tmp.name) / "dos"
        dos.mkdir()
        w.edicion.archivo = None
        with mock.patch("escritorio.archivos.QFileDialog.getSaveFileName", return_value=(str(dos / "b.grafnet"), "")) as dlg:
            self.assertTrue(w.guardar_como())
        self.assertEqual(Path(dlg.call_args.args[2]).parent, uno, "sin archivo propio propone la última carpeta")
        self.assertEqual(w.ajustes.value("archivos/ultima_carpeta"), str(dos))
        w.edicion.ed.dirty = False

    def test_SAA5_carpeta_inexistente_vuelve_a_la_de_por_defecto_y_cancelar_no_cambia_nada(self):
        """REQ-EDT-01: una carpeta guardada que ya no existe se sustituye por la de siempre; cancelar no cambia la guardada."""
        from escritorio.carpetas import asegurar_carpetas
        self._carpetas()
        w, e = self.vacio()
        w.ajustes.setValue("archivos/ultima_carpeta", str(Path(self.tmp.name) / "no_existe"))
        self.assertEqual(w.carpeta_proyectos(), asegurar_carpetas()["grafcet"])
        real = Path(self.tmp.name) / "real"
        real.mkdir()
        w.ajustes.setValue("archivos/ultima_carpeta", str(real))
        with mock.patch("escritorio.archivos.QFileDialog.getSaveFileName", return_value=("", "")):
            self.assertFalse(w.guardar_como())
        with mock.patch("escritorio.ventana.QFileDialog.getOpenFileName", return_value=("", "")):
            w.abrir()
        self.assertEqual(w.ajustes.value("archivos/ultima_carpeta"), str(real))
        with mock.patch("escritorio.ventana.QMessageBox.warning"):
            self.assertFalse(w.abrir_ruta(real / "nada.grafnet"))
        self.assertEqual(w.ajustes.value("archivos/ultima_carpeta"), str(real), "un fallo tampoco la cambia")


if __name__ == "__main__":
    unittest.main()
