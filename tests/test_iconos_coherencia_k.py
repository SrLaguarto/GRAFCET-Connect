"""SK1: tinta común, módulos directos y controles coherentes."""
import os
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from conexion.configuracion import Configuracion
from conexion.uniones import Union
from escritorio import estilo, favoritos
from escritorio.edicion import Edicion
from escritorio.entradas_salidas import PanelES, TerminalES
from escritorio.paleta_variables import TituloGrupo
from escritorio.traer_dialogo import DialogoTraer
from grafcet.builder import M
from grafcet.editor import Editor
from medidas_iconos_k import medir
from servidor_directo_falso import ServidorDirecto, senal


class CoherenciaK(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        estilo.activar_escala("normal")
        self.addCleanup(estilo.activar_escala, "normal")

    def panel(self):
        doc = M().var("marcha").var("motor", "output").step("0", True).doc
        panel = PanelES()
        self.addCleanup(panel.close)
        panel.cargar(doc)
        panel.directa.establecer_edicion(Edicion(Editor(doc), "Prueba K"))
        panel.resize(1366, 650)
        panel.show()
        panel.directa.selector.setCurrentIndex(1)
        panel.directa.catalogo = [senal("s", "Pulsador"), senal("q", "Motor", papel="Output"),
                                  senal("interno", "Simulador I/O (Running)", direccion=496)]
        panel.config.uniones = [Union(doc["variables"][0]["id"], "s", "Pulsador", "Bit", "input")]
        panel.directa.catalogo_leido = True
        panel.directa.dibujar()
        self.app.processEvents()
        return panel

    def dialogo(self, panel):
        servidor = ServidorDirecto([senal("s", "Pulsador"), senal("nuevo", "Xmotor permiso"),
                                   senal("interno", "Simulador I/O (Running)", direccion=496)])
        self.addCleanup(servidor.cerrar)
        panel.directa.host.setText("127.0.0.1")
        panel.directa.puerto.setValue(servidor.puerto)
        dialogo = DialogoTraer(panel.directa)
        self.addCleanup(dialogo.reject)
        dialogo.show()
        limite = time.monotonic() + 4
        while dialogo.propuestas is None and time.monotonic() < limite:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertIsNotNone(dialogo.propuestas)
        return dialogo

    def test_SK101_quince_anchos_comunes_y_margen_en_tres_dpr(self):
        for lado in (28, 30):
            for dpr in (1.0, 1.25, 1.5):
                medidas, imagenes = medir(favoritos, lado, dpr)
                self.assertEqual(len(medidas), 15)
                w = 19.5 * lado / 24
                for clave, dato in medidas.items():
                    with self.subTest(caja=lado, dpr=dpr, clave=clave):
                        self.assertAlmostEqual(dato["ancho_tinta"], w, delta=0.5)
                        self.assertFalse(dato["toca_borde"])

    def test_SK102_seis_cuadrados_y_acciones_alineadas(self):
        for clave in ("etapa", "etapa_inicial", "macroetapa", "encapsulante", "texto", "imagen"):
            pintor = mock.Mock()
            if clave == "encapsulante":
                from PySide6.QtGui import QColor, QPen
                pintor.pen.return_value = QPen(QColor(estilo.TINTA), 1.5)
            favoritos.pintar_mini(pintor, clave)
            caja = pintor.drawRect.call_args_list[0].args[0]
            self.assertEqual((caja.width(), caja.height()), (18, 18))
        cuerpos = []
        for clave in [c for c in favoritos.PREDETERMINADOS if c.startswith("accion:")] + ["forzado"]:
            pintor = mock.Mock()
            favoritos.pintar_mini(pintor, clave)
            cuerpos.append(pintor.drawRect.call_args_list[0].args[0])
        self.assertTrue(all(c == cuerpos[0] for c in cuerpos))

    def test_SK103_controles_altura_de_token_en_ambas_escalas(self):
        panel = self.panel()
        for escala in ("normal", "grande"):
            estilo.activar_escala(escala)
            panel.escalar(estilo.hoja_global(), escala)
            self.app.processEvents()
            alto = estilo.ESCALAS[escala]["ALTO_CONTROL"]
            for control in (panel.directa.b_traer, panel.directa.selector, panel.b_conectar):
                self.assertEqual(control.height(), alto, (escala, control.objectName()))
            dialogo = self.dialogo(panel)
            for boton in dialogo.findChildren(QPushButton):
                self.assertEqual(boton.height(), alto, (escala, boton.text()))
            dialogo.reject()

    def test_SK104_titulos_reutilizados_sin_pastilla_en_ambos_estados(self):
        dialogo = self.dialogo(self.panel())
        titulos = dialogo.findChildren(TituloGrupo)
        self.assertEqual(len(titulos), 4)
        self.assertTrue(any(t.text().startswith("De otra escena ·") for t in titulos))
        for titulo in titulos:
            self.assertIn(" · ", titulo.text())
            self.assertNotIn(") (", titulo.text())
            hoja = titulo.styleSheet()
            plegado = titulo.plegado
            alto = titulo.height()
            titulo.click()
            self.assertEqual(titulo.plegado, not plegado)
            self.assertEqual(titulo.styleSheet(), hoja)
            self.assertEqual(titulo.height(), alto)

    def test_SK105_motivo_visible_y_ya_traida_centrada(self):
        dialogo = self.dialogo(self.panel())
        self.assertTrue(dialogo.motivos.isVisible())
        self.assertIn("Xmotor permiso", dialogo.motivos.toolTip())
        self.assertIn("se confundiría", dialogo.motivos.toolTip())
        self.assertFalse(dialogo.b_traer.isEnabled())
        tabla, filas = dialogo.tablas[0]
        self.assertEqual(tabla.item(0, 0).text(), "ya traída")
        self.assertTrue(tabla.item(0, 0).textAlignment() & Qt.AlignmentFlag.AlignHCenter)
        self.assertEqual(tabla.item(0, 0).foreground().color().name(), estilo.TINTA_2)

    def test_SK106_mismo_terminal_internas_ocultas_y_valor_por_piloto(self):
        panel = self.panel()
        marco = panel.directa.dibujo
        self.assertNotIn("interno", marco.terminales)
        self.assertTrue(all(isinstance(t, TerminalES) for t in marco.terminales.values()))
        self.assertEqual(marco.terminales["q"].nombre.text(), "")
        vid = panel.config.uniones[0].variable
        for valor in (True, False):
            panel.mostrar_valores({vid: valor})
            self.assertEqual(marco.terminales["s"].valor.text(), "")
            self.assertFalse(marco.terminales["s"].valor.isVisible())
        panel.config.uniones.append(Union(panel.variables[1]["id"], "interno", "Simulador (Running)", "Bit", "input"))
        panel.directa.dibujar()
        self.assertIn("interno", marco.terminales)

    def test_SK107_ambar_en_fila_y_estado_sin_cambiar_variables(self):
        panel = self.panel()
        panel.config.uniones[0].motivo = "señal no encontrada"
        panel.directa.catalogo = []
        panel.directa.dibujar()
        terminal = panel.directa.dibujo.terminales["s"]
        self.assertTrue(terminal.nombre.property("aviso"))
        self.assertIn("no encontrada", terminal.toolTip())
        resumen = panel.directa.resumen_escena
        self.assertIn("no encontrada", resumen.detalle.toPlainText())
        self.assertTrue(resumen.isVisible())
        self.assertTrue(resumen.detalle.isHidden())

    def test_SK108_cabeceras_y_leyenda_mismo_pie(self):
        panel = self.panel()
        for cabecera in panel.cuentas.values():
            self.assertIn("font-weight:400", cabecera.text())
        self.assertTrue(panel.ayuda_vacio.isVisible())
        pie = panel.ayuda_vacio.parentWidget()
        self.assertTrue(pie.isAncestorOf(panel.resumen))
        self.assertTrue(panel.resumen.text().endswith("uniones"))
        self.assertIn("«Ninguno»", panel.ayuda_vacio.text())

    def test_SK109_auditoria_de_panel_y_dialogo_sin_excepciones_nuevas(self):
        import test_auditoria_maquetacion as auditoria
        panel = self.panel()
        for ancho, alto in ((1366, 768), (2000, 1250), (960, 540)):
            escala = "grande" if ancho == 2000 else "normal"
            estilo.activar_escala(escala)
            panel.escalar(estilo.hoja_global(), escala)
            panel.resize(ancho, alto - 100)
            dialogo = self.dialogo(panel)
            dialogo.resize(min(ancho - 64, 1120), min(alto - 64, 720))
            for _ in range(8):
                self.app.processEvents()
            for nombre, raiz in (("panel", panel), ("diálogo", dialogo)):
                for regla, comprobar in auditoria.REGLAS.items():
                    if regla in ("B1", "B2"):
                        continue
                    malos = [x for x in comprobar(raiz) if not auditoria.permitida(regla, x)]
                    self.assertEqual(malos, [], (ancho, nombre, regla, malos))
                self.assertEqual(auditoria.regla_TB3(raiz, ancho), [])
            dialogo.reject()

    def test_SK110_dialogos_generales_usan_la_escala_actual(self):
        from test_editor_cadenas import BaseQt
        from escritorio.ventana import AcercaDe
        from escritorio.propiedades_archivo import PropiedadesArchivo, recopilar
        BaseQt.setUpClass()
        caso = BaseQt()
        caso.setUp()
        self.addCleanup(caso.tearDown)
        self.addCleanup(caso.w.hide)
        ventana, edicion = caso.vacio()
        ventana.resize(2000, 1250)
        ventana.show()
        for _ in range(8):
            self.app.processEvents()
        self.assertEqual(estilo.ESCALA, "grande")
        dialogos = (AcercaDe(ventana),
                    PropiedadesArchivo(recopilar(edicion, True), ventana))
        for dialogo in dialogos:
            self.addCleanup(dialogo.close)
            dialogo.show()
            self.app.processEvents()
            for boton in dialogo.findChildren(QPushButton):
                self.assertEqual(boton.height(), estilo.ALTO_CONTROL)
            dialogo.close()


if __name__ == "__main__":
    unittest.main()
