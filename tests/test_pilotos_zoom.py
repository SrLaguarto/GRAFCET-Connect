"""SL1: pilotos y recorte de zoom; ejecutable sin preparar PYTHONPATH."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QWidget
from conexion.configuracion import Configuracion, Senal
from conexion.uniones import Union
from escritorio import estilo
from escritorio.entradas_salidas import COLOR_TIPO, IndicadorES, NIVEL_ACTIVO, NIVEL_ASIGNADO, NIVEL_TENUE, PanelES
from grafcet.builder import M
from servidor_directo_falso import senal
from test_editor_cadenas import BaseQt


def imagen_piloto(piloto):
    imagen = QImage(piloto.size(), QImage.Format.Format_ARGB32)
    imagen.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagen)
    piloto.render(pintor, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    pintor.end()
    return imagen


def contraste(a, b):
    def luminancia(texto):
        rgb = QColor(texto).getRgbF()[:3]
        lineal = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
        return sum(x * peso for x, peso in zip(lineal, (0.2126, 0.7152, 0.0722)))
    a, b = sorted((luminancia(a), luminancia(b)))
    return (b + 0.05) / (a + 0.05)


class PilotosZoom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        estilo.activar_escala("normal")
        self.addCleanup(estilo.activar_escala, "normal")

    def piloto(self, colores=None, nivel=NIVEL_ASIGNADO):
        piloto = IndicadorES()
        piloto.fijar(colores or (COLOR_TIPO["bool"],), nivel)
        self.addCleanup(piloto.deleteLater)
        return piloto

    def panel(self, directo=False):
        doc = M().var("sensor").var("motor", "output").var("velocidad", "output", "int").step("0", True).doc
        ids = [v["id"] for v in doc["variables"]]
        cfg = Configuracion(modelo=doc["id"], senales=[Senal(ids[0], "discrete", 0), Senal(ids[1], "coil", 0),
                                                      Senal(ids[2], "holding", 0, "INT16")])
        panel = PanelES()
        self.addCleanup(panel.deleteLater)
        self.addCleanup(panel.hide)
        panel.cargar(doc, cfg)
        panel.resize(1366, 700)
        panel.show()
        if directo:
            panel.directa.selector.setCurrentIndex(1)
            panel.directa.catalogo = [senal("s", "Sensor"), senal("q", "Motor", papel="Output"),
                                      senal("n", "Velocidad", "Int", "Output")]
            panel.config.uniones = [Union(v, s["id"], s["name"], s["type"], s["kind"].lower())
                                    for v, s in zip(ids, panel.directa.catalogo)]
            panel.directa.dibujar()
        self.app.processEvents()
        return panel, ids

    def ventana(self, ancho=960):
        BaseQt.setUpClass()
        caso = BaseQt()
        caso.setUp()
        self.addCleanup(caso.doCleanups)
        self.addCleanup(caso.tearDown)
        w, _ = caso.vacio()
        self.addCleanup(w.hide)
        w.resize(ancho, 540 if ancho <= 960 else 768)
        w.show()
        BaseQt.pasar_arranque(caso, w)
        BaseQt.asentar_escala(caso, w)
        for _ in range(6):
            self.app.processEvents()
        return w, caso

    def test_SL101_circulo_esquinas_transparentes_y_dentro_de_fila(self):
        for escala, alto in (("normal", 16), ("grande", 18)):
            estilo.activar_escala(escala)
            p = self.piloto(nivel=NIVEL_ACTIVO)
            imagen = imagen_piloto(p)
            self.assertEqual(p.width(), p.height())
            self.assertLessEqual(p.height(), alto)
            for x, y in ((0, 0), (0, p.height() - 1), (p.width() - 1, 0), (p.width() - 1, p.height() - 1)):
                self.assertEqual(imagen.pixelColor(x, y).alpha(), 0)
            self.assertEqual(imagen.pixelColor(p.width() // 2, p.height() // 2).name(), estilo.PILOTO_ENCENDIDO)

    def test_SL102_colores_halo_y_contraste_del_contorno(self):
        p = self.piloto()
        self.assertEqual(p.color().name(), estilo.PILOTO_APAGADO)
        apagado = imagen_piloto(p)
        p.fijar_nivel(NIVEL_ACTIVO)
        self.assertEqual(p.color().name(), estilo.PILOTO_ENCENDIDO)
        encendido = imagen_piloto(p)
        centro = p.width() // 2
        self.assertEqual(apagado.pixelColor(centro, 1).alpha(), 0)
        self.assertGreater(encendido.pixelColor(centro, 1).alpha(), 0)
        self.assertNotEqual(estilo.PILOTO_ENCENDIDO, estilo.SIMULACION)
        self.assertGreater(contraste(estilo.PILOTO_ENCENDIDO, estilo.PILOTO_APAGADO), 2)
        self.assertGreaterEqual(contraste(estilo.BORDE_CONTROL, estilo.SUPERFICIE_2), 3)

    def test_SL103_numericas_y_doble_color_no_se_vuelven_verdes(self):
        for tipo in ("int", "decimal"):
            p = self.piloto((COLOR_TIPO[tipo],), NIVEL_ACTIVO)
            self.assertEqual(p.color().name(), COLOR_TIPO[tipo])
        p = self.piloto((COLOR_TIPO["decimal"], COLOR_TIPO["int"]), NIVEL_ACTIVO)
        imagen = imagen_piloto(p)
        centro = p.width() // 2
        self.assertEqual(imagen.pixelColor(centro, 4).name(), COLOR_TIPO["decimal"])
        self.assertEqual(imagen.pixelColor(centro, p.height() - 5).name(), COLOR_TIPO["int"])

    def test_SL104_booleanas_sin_cifras_en_ambos_modos(self):
        for directo in (False, True):
            panel, ids = self.panel(directo)
            for valor in (False, True, 0, 1, None):
                panel.mostrar_valores({ids[0]: valor, ids[1]: valor, ids[2]: 123})
                for vid in ids[:2]:
                    led, texto = panel.indicadores[vid]
                    self.assertEqual(texto.text(), "")
                    self.assertFalse(texto.isVisible())
                    self.assertEqual(led.nivel, NIVEL_ACTIVO if valor else NIVEL_ASIGNADO)
                self.assertEqual(panel.indicadores[ids[2]][1].text(), "123")

    def test_SL105_posicion_y_leyenda_redonda(self):
        for directo in (False, True):
            panel, ids = self.panel(directo)
            for terminal in panel.terminales.values():
                led = terminal.led
                if terminal.area in ("discrete", "input-register"):
                    self.assertLess(led.x(), terminal.canal.x())
                else:
                    self.assertGreater(led.x(), terminal.canal.x())
                self.assertTrue(terminal.rect().contains(led.mapTo(terminal, QPoint(0, 0))))
                centro = led.mapTo(terminal, led.rect().center()).y()
                self.assertLessEqual(abs(centro - terminal.rect().center().y()), 1)
            pilotos = panel.ayuda_vacio.parentWidget().findChildren(IndicadorES)
            self.assertEqual(len(pilotos), 4)
            self.assertTrue(all(p.width() == p.height() for p in pilotos))
            self.assertEqual(pilotos[0].color().name(), estilo.PILOTO_APAGADO)

    def test_SL106_quince_favoritos_a_960_sin_solapes(self):
        w, _ = self.ventana()
        self.assertTrue(w.diagrama.l_zoom.isVisible())
        self.assertEqual(w.favoritos.ocultos, [])
        self.assertEqual(len(w.favoritos._visibles), 15)
        self.assertEqual(w.favoritos.lado_icono, 24)
        favoritos = w.favoritos.geometry()
        zoom = w.diagrama.barra.geometry()
        self.assertFalse(favoritos.intersects(zoom))
        self.assertTrue(w.diagrama.barra.parentWidget().rect().contains(zoom))

    def test_SL107_orden_de_recorte_y_retorno_del_porcentaje(self):
        w, caso = self.ventana()
        for ancho in (683, 900, 960, 1024, 1366, 2000, 960, 1366):
            w.resize(ancho, 1250 if ancho == 2000 else 768)
            BaseQt.asentar_escala(caso, w)
            for _ in range(8):
                self.app.processEvents()
            d = w.diagrama
            if w.favoritos.ocultos:
                self.assertTrue(d.l_zoom.isHidden(), ancho)
            if ancho == 960:
                self.assertFalse(w.favoritos.ocultos)
            if ancho >= 1366:
                self.assertFalse(d.l_zoom.isHidden(), ancho)
            if d.l_zoom.isHidden():
                self.assertEqual(d.b_ajustar.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonIconOnly)

    def test_SL108_ayudas_con_zoom_actual_y_restaura_las_originales(self):
        w, caso = self.ventana()
        w.resize(683, 768)
        BaseQt.asentar_escala(caso, w)
        for _ in range(8):
            self.app.processEvents()
        d = w.diagrama
        self.assertTrue(d.l_zoom.isHidden())
        d.zoom(1.5)
        for boton in (d.b_menos, d.b_mas):
            self.assertIn("zoom 150 %", boton.toolTip())
            self.assertTrue(boton.accessibleName())
        w.resize(2000, 1250)
        BaseQt.asentar_escala(caso, w)
        for _ in range(8):
            self.app.processEvents()
        self.assertFalse(d.l_zoom.isHidden())
        self.assertNotIn(" · zoom", d.b_menos.toolTip())
        self.assertEqual(d.l_zoom.text(), "150 %")


    def test_SL109_iconos_antes_de_desbordar_al_recuperar_textos(self):
        w, caso = self.ventana()
        for ancho in (1580, 1596, 1600, 1620, 1660):
            w.resize(ancho, 768)
            for _ in range(4):
                self.app.processEvents()
                BaseQt.asentar_escala(caso, w)
            self.assertEqual(w.favoritos.ocultos, [], ancho)
            self.assertFalse(w.diagrama.l_zoom.isHidden(), ancho)


if __name__ == "__main__":
    unittest.main()
