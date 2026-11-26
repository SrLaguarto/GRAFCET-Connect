"""Pruebas de regresión del Ciclo 4 (paridad visual v2: C2, C7, C8, C9, C9b, C10, C13, C15, C17a-c)."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(1, str(ROOT / "tests"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from grafcet.builder import M
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    from conexion.configuracion import Configuracion
    from escritorio import estilo
    from escritorio.edicion import Edicion
    from escritorio.entradas_salidas import PanelES
    from escritorio.filtro_senales import ConfiguracionDirecta
    from escritorio.hojas import CrearHoja
    from escritorio.paleta_variables import TituloGrupo
    from escritorio.paneles import ANCHO_MARCADOR, CajaSeccion, TituloSeccion
    from escritorio.partes_propiedades import ConmutadorPartes
    from escritorio.planos import MesaVaciaPlanos
    from escritorio.traer_celdas import ROL_AUTO
    from escritorio.traer_dialogo import DialogoTraer
    from escritorio.ventana.widgets import TablaConsola
    from grafcet.editor import Editor, new_grafcet_document
    from servidor_directo_falso import ServidorDirecto, senal


def _bombear(n: int = 5) -> None:
    app = QApplication.instance()
    for _ in range(n):
        app.processEvents()


@unittest.skipUnless(QT, "requiere PySide6")
class PulidoCiclo4Qt(BaseQt):
    def setUp(self):
        self._docs = tempfile.TemporaryDirectory()
        self.addCleanup(self._docs.cleanup)
        patcher = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=self._docs.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.addCleanup(self.w.hide)

    def test_PC4_01_c2_boton_simular_en_edicion_y_stop_al_simular(self):
        w, e = self.vacio()
        e.ed.add_variable("marcha", "input", {"kind": "bool"})
        s0 = e.ed.add_step("g", "0", True, at=(100, 80))
        s1 = e.ed.add_step("g", "1", False, at=(100, 220))
        e.ed.add_transition("g", "marcha", [s0], [s1], at=(100, 150))
        e.cambia()
        w.resize(1366, 768)
        w.show()
        _bombear()
        self.assertEqual(w.a_ejecutar.text(), "Simular")
        self.assertIn("Simular", w.a_ejecutar.toolTip())
        boton = w.tb_sim.widgetForAction(w.a_ejecutar)
        ancho = boton.width()
        w.a_ejecutar.setChecked(True)
        w.rt.stop()
        _bombear()
        self.assertEqual(w.modo, "simular")
        self.assertEqual(w.a_ejecutar.text(), "Detener")
        self.assertEqual(boton.width(), ancho)
        w.a_ejecutar.setChecked(False)
        _bombear()
        self.assertEqual(w.a_ejecutar.text(), "Simular")

    def test_PC4_02_c7_consola_simulacion_estilo_tarjetas_y_cuatro_columnas(self):
        w, e = self.vacio()
        e.nueva_variable("marcha", "input", {"kind": "bool"})
        e.nueva_variable("paro", "input", {"kind": "bool"})
        e.nueva_variable("motor", "output", {"kind": "bool"})
        e.nueva_variable("ct", "internal", {"kind": "int"})
        s0 = e.poner_etapa(QPointF(140, 80))
        e.tipo_etapa(s0, True)
        t1 = e.poner_transicion(QPointF(140, 160))
        s1 = e.poner_etapa(QPointF(140, 240))
        t2 = e.poner_transicion(QPointF(140, 320))
        e.conectar(s0, t1)
        e.conectar(t1, s1)
        e.conectar(s1, t2)
        e.conectar(t2, s0)
        e.poner_condicion(t1, "2s/X0 AND marcha")
        e.poner_condicion(t2, "paro")
        e.poner_accion(s1, {"variable": "motor", "tipo": "continua"})
        e.cambia()
        w.resize(1366, 768)
        w.show()
        w.a_ejecutar.setChecked(True)
        w.rt.stop()
        _bombear()

        self.assertEqual(w.modo, "simular")
        self.assertEqual(w.titulo_sim.text(), "Consola de simulación")
        self.assertEqual(w.l_cont_sim.text(), "4")
        self.assertIsInstance(w.t_vars, TablaConsola)
        self.assertIsInstance(w.t_temp, TablaConsola)
        for t in (w.t_vars, w.t_temp):
            hoja = t.styleSheet()
            self.assertIn("gridline-color: transparent", hoja)
            self.assertIn("background: transparent", hoja)
            self.assertIn("item:selected", hoja)
            self.assertEqual(t.verticalHeader().defaultSectionSize(), estilo.ALTO_FILA + 2)
        self.assertEqual([w.t_vars.isColumnHidden(c) for c in range(4)], [False] * 4)
        self.assertEqual([w.t_temp.isColumnHidden(c) for c in range(4)], [False] * 4)
        self.assertEqual(
            [w.t_vars.horizontalHeaderItem(c).text() for c in range(4)],
            ["Variable", "Modo", "Valor", "Contribuyen"],
        )

        # Ctrl+clic sigue enclavando la entrada y pintando sin errores
        vid_marcha = next(v["id"] for v in e.ed.model["variables"] if v["name"] == "marcha")
        QTest.mouseClick(w.botones[vid_marcha], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(w.botones[vid_marcha].isChecked())
        self.assertEqual(w.botones[vid_marcha].text(), "marcha = 1")
        w._act("avanzar", us=2_000_000)
        _bombear()
        fila_motor = next(r for r in range(w.t_vars.rowCount()) if w.t_vars.item(r, 0).text() == "motor")
        self.assertEqual(w.t_vars.item(fila_motor, 2).text(), "ON")
        self.assertFalse(w.derecho.grab().isNull())

    def test_PC4_03_c8_c9_c9b_planos_vacio_barra_y_hojas_sin_duplicar(self):
        w, _ = self.vacio()
        w.resize(1366, 768)
        w.show()
        _bombear()
        tabs = w.pestanas_vistas
        QTest.mouseClick(tabs, Qt.MouseButton.LeftButton, pos=tabs.tabRect(1).center())
        _bombear(8)
        p = w.panel_planos

        self.assertTrue(p.titulo.isHidden())
        self.assertTrue(p.scroll_hojas.isAncestorOf(p.b_hoja))
        self.assertTrue(p.b_hoja.isHidden())
        self.assertEqual(p.b_hoja.text(), "+ Añadir otra hoja")
        self.assertFalse(any("hoja" in a.text().lower() for a in p.barra.actions()))
        self.assertGreater(p.caja_zoom.geometry().left(), p.barra.width() // 2)
        self.assertTrue(p.b_encajar_zoom.isVisible())
        self.assertEqual(p.titulo_hojas.text(), "Hojas")
        self.assertEqual(p.l_cont_hojas.text(), "0")
        self.assertTrue(p.l_sin_hojas.isVisible())
        self.assertEqual(p.l_sin_hojas.text(), "Sin hojas todavía")
        self.assertIsInstance(p.vacio, MesaVaciaPlanos)
        self.assertTrue(p.vacio.b_crear_primera.isVisible())
        self.assertEqual(p.vacio.b_crear_primera.text(), "+ Crear primera hoja")
        self.assertEqual(p.vacio.text(), "Todavía no hay hojas de plano")
        self.assertEqual([b for b in p.scroll_hojas.findChildren(QPushButton) if b.isVisible()], [])

        with mock.patch.object(CrearHoja, "exec", lambda d: (d.accept() or QDialog.DialogCode.Accepted)):
            p.vacio.b_crear_primera.click()
        _bombear(6)
        self.assertEqual(p.l_cont_hojas.text(), "1")
        self.assertFalse(p.l_sin_hojas.isVisible())
        self.assertTrue(p.vacio.isHidden())
        self.assertTrue(p.b_hoja.isVisible())

        p.lista.setCurrentRow(0)
        p.eliminar_hoja()
        _bombear(6)
        self.assertEqual(p.l_cont_hojas.text(), "0")
        self.assertTrue(p.b_hoja.isHidden())
        self.assertTrue(p.vacio.isVisible())

    def test_PC4_04_c10_es_sin_boton_volver_y_retorno_por_pestana(self):
        w, _ = self.vacio()
        w.resize(1366, 768)
        w.show()
        _bombear()
        w.mostrar_es()
        _bombear()
        p = w.panel_es
        self.assertFalse(hasattr(p, "b_volver"))
        self.assertFalse(any("volver" in b.text().lower() for b in p.cabecera.findChildren(QPushButton)))
        QTest.mouseClick(w.pestanas_vistas, Qt.MouseButton.LeftButton, pos=w.pestanas_vistas.tabRect(0).center())
        _bombear()
        self.assertEqual(w.paginas_es.currentIndex(), 0)

    def test_PC4_05_c13_modbus_cabecera_en_una_fila_y_texto_conectado(self):
        doc = M().var("marcha").var("motor", "output").step("0", True).doc
        panel_vacio = PanelES()
        self.addCleanup(panel_vacio.close)
        panel_vacio.escalar("", "normal")
        self.assertTrue(panel_vacio.dialogo_config.styleSheet().startswith(estilo.hoja_global()))

        p = PanelES()
        self.addCleanup(p.close)
        p.escalar(estilo.hoja_global(), "normal")
        p.cargar(doc)
        for tamano in ((1366, 768), (960, 520)):
            p.resize(*tamano)
            p.show()
            _bombear(6)
            l = p.lienzo
            self.assertLessEqual(l.edicion_destino.sizeHint().width(), 2 * p.ancho_interior, tamano)
            self.assertLessEqual(abs(l.ip.y() - l.puerto.y()), 4, tamano)
            self.assertLessEqual(abs(l.puerto.y() - l.unidad.y()), 4, tamano)
            self.assertLess(l.ip.x(), l.puerto.x())
            self.assertLess(l.puerto.x(), l.unidad.x())
            self.assertEqual(p.destino.text(), "(192.168.1.133:502) · ID 1")
            self.assertNotIn("\n", p.destino.text())
            cab_size = l.cabecera_marco.size()
            p.ocupado(True)
            _bombear(4)
            self.assertEqual(l.cabecera_marco.size(), cab_size)
            p.ocupado(False)
            _bombear(4)

    def test_PC4_06_c15_traer_tabla_unica_con_sentido_auto_y_grupos_plegados(self):
        servidor = ServidorDirecto([
            senal("a", "Start Button"),
            senal("b", "Diffuse Sensor #1"),
            senal("c", "2nd Conveyor", papel="Output"),
            senal("i", "Simulador I/O (Running)", direccion=496),
        ])
        self.addCleanup(servidor.cerrar)
        ed = Edicion(Editor(new_grafcet_document("m")), "Prueba C15")
        panel = PanelES()
        self.addCleanup(panel.close)
        panel.directa.establecer_edicion(ed)
        panel.cargar(ed.ed.model, Configuracion(host="127.0.0.1", puerto=servidor.puerto, modo="directo"))
        d = DialogoTraer(panel.directa)
        self.addCleanup(d.reject)
        d.show()
        limite = time.monotonic() + 3
        while d.propuestas is None and time.monotonic() < limite:
            _bombear(1)
            time.sleep(0.005)
        self.assertIsNotNone(d.propuestas)
        self.assertEqual(len(d.tablas), 2)

        tabla, filas = d.tablas[0]
        self.assertEqual(
            [tabla.horizontalHeaderItem(c).text() for c in range(5)],
            ["Usar", "Señal en el simulador", "Nombre de variable en GRAFCET Connect", "Sentido", "Tipo"],
        )
        self.assertEqual([tabla.item(r, 3).text() for r in range(3)], ["Entrada", "Entrada", "Salida"])
        idx_cambiado = next(r for r, f in enumerate(filas) if f.cambiado)
        self.assertTrue(bool(tabla.item(idx_cambiado, 2).data(ROL_AUTO)))
        self.assertTrue(d.leyenda_auto.isVisible())
        _bombear(4)
        self.assertFalse(tabla.verticalScrollBar().isVisible())
        self.assertGreaterEqual(
            tabla.columnWidth(2),
            tabla.horizontalHeader().fontMetrics().horizontalAdvance("Nombre de variable en GRAFCET Connect"),
        )

        titulos = d.findChildren(TituloGrupo)
        self.assertEqual(len(titulos), 3)
        self.assertFalse(titulos[0].plegado)
        self.assertTrue(titulos[1].plegado)
        self.assertTrue(titulos[2].plegado)

    def test_PC4_07_c17_config_directa_abierta_una_fila_y_cancelar_aceptar(self):
        panel = PanelES()
        self.addCleanup(panel.close)
        doc = M().var("marcha").step("0", True).doc
        panel.cargar(doc, Configuracion(host="localhost", puerto=7410, modo="directo", modelo=doc["id"]))
        panel.directa.catalogo = [senal("s1", "Sensor 1"), senal("sys", "Simulador I/O (Run)", direccion=496)]
        panel.resize(1366, 768)
        d = ConfiguracionDirecta(panel.directa)
        self.addCleanup(d.close)
        d.show()
        _bombear()

        self.assertFalse(hasattr(d, "b_avanzado"))
        self.assertTrue(d.avanzado.isVisible())
        self.assertTrue(d.tabla.isVisible())
        p_spin, t_spin = d.controles["periodo_ms"], d.controles["timeout_ms"]
        self.assertLessEqual(abs(p_spin.y() - t_spin.y()), 2)
        self.assertLess(p_spin.x(), t_spin.x())
        self.assertLessEqual(abs(d.b_cancelar.y() - d.b_aceptar.y()), 2)
        self.assertLess(d.b_cancelar.x(), d.b_aceptar.x())
        self.assertEqual((d.b_cancelar.text(), d.b_aceptar.text()), ("Cancelar", "Aceptar"))

        p_spin.setValue(45)
        d.b_aceptar.click()
        self.assertEqual(d.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(d.config.periodo_ms, 45)

    def test_PC4_08_cositas_b1_b2_b3_y_d1_d4(self):
        w, e = self.vacio()
        w.resize(1366, 768)
        w.show()
        _bombear()

        # B1=1C y D2: micro-etiqueta plana y scrollbars de 10 px
        self.assertEqual(estilo.ANCHO_BARRA, 10)
        self.assertEqual(w.estado.objectName(), "estadoModo")
        self.assertFalse(w.estado.grab().isNull())

        # B2=2A: filete vertical 3 px en cabeceras y subsecciones sin marcador
        self.assertEqual(ANCHO_MARCADOR, 3)
        t_cond = e.ed.add_transition("g", "", [], [], at=(100, 140))[0]
        e.seleccionar([t_cond])
        w._abrir_opciones()
        _bombear()
        self.assertFalse(w.flot.principal.l_sub_titulo.con_marcador)
        self.assertTrue(w.flot.principal.titulo.con_marcador)
        caja = CajaSeccion("Sub")
        self.addCleanup(caja.deleteLater)
        self.assertEqual(caja.title(), "Sub")

        # B3: el conmutador Evento/Acción ya no lleva punto ámbar de aviso
        conm = ConmutadorPartes([("formula", "Evento", estilo.ACENTO), ("accion", "Acción", estilo.ACENTO)])
        self.addCleanup(conm.deleteLater)
        conm.show()
        _bombear()
        self.assertFalse(hasattr(conm, "avisar"))
        img_act = conm.botones["formula"].grab().toImage()
        self.assertFalse(any(img_act.pixelColor(x, y).name() == estilo.AVISO_BORDE
                             for x in range(img_act.width()) for y in range(img_act.height())))

        # D3 y D4: ayuda de entradas compacta y campos de ConfiguracionDirecta agrupados
        self.assertEqual(w.l_ayuda_entradas.text(), "Clic: pulsar · Ctrl: enclavar · Der.: tipo")
        panel = PanelES()
        self.addCleanup(panel.close)
        doc = M().var("marcha").step("0", True).doc
        panel.cargar(doc, Configuracion(host="localhost", puerto=7410, modo="directo", modelo=doc["id"]))
        panel.resize(1366, 768)
        dlg = ConfiguracionDirecta(panel.directa)
        self.addCleanup(dlg.close)
        dlg.show()
        _bombear()
        p_spin, t_spin = dlg.controles["periodo_ms"], dlg.controles["timeout_ms"]
        hueco = t_spin.x() - (p_spin.x() + p_spin.width())
        self.assertLessEqual(hueco, 80)

    def test_PC4_09_candado_preparar_carga_y_refresco_catalogo(self):
        from types import SimpleNamespace
        from conexion.coordinador import Coordinador
        from conexion.hilos import COORDINADOR, Candado, proteger
        from conexion.intercambio_directo import TransporteDirecto
        from escritorio.conexion_ventana import preparar_carga
        from escritorio.refresco_conexion import RefrescoConexion

        candado = Candado()
        coord = Coordinador()
        self.addCleanup(coord.cerrar)
        coord.estado = "conectado"
        coord.adaptador = SimpleNamespace(
            config=Configuracion(modo="modbus"),
            entradas=[],
            salidas=[],
            salidas_control=[],
            redondeos={},
        )
        proteger(coord, COORDINADOR, candado, "Coordinador")
        ciclo = mock.Mock()
        ventana = SimpleNamespace(modbus=coord, candado=candado, ciclo=ciclo)
        with mock.patch.dict(os.environ, {"GRAFCONNECT_COMPROBAR_HILOS": "1"}):
            # Re-proteger si la variable no estaba activa al construir, o aprovechar el entorno actual.
            proteger(coord, COORDINADOR, candado, "Coordinador")
            with candado.hilo_de_control():
                preparar_carga(ventana, Configuracion(modo="directo"))
        self.assertEqual(coord.estado, "cerrando")
        ciclo.despertar.assert_called_once()

        w, _ = self.vacio()
        doc = M().var("marcha").step("0", True).doc
        cfg = Configuracion(host="localhost", puerto=7410, modo="directo", modelo=doc["id"])
        w.panel_es.cargar(doc, cfg)
        cliente = TransporteDirecto(cfg)
        cliente.senales = {"s1": {"id": "s1", "name": "Marcha", "type": "Bit", "kind": "Input"}}
        with w.candado:
            w.modbus.cliente = cliente
            w.modbus.futuro = None
        estados_candado = []
        dibujar_orig = w.panel_es.directa.dibujar

        def spy_dibujar():
            estados_candado.append(w.candado.cogido_por_este_hilo())
            return dibujar_orig()

        with mock.patch.object(w.panel_es.directa, "dibujar", side_effect=spy_dibujar):
            RefrescoConexion(w).actualizar()
        self.assertEqual(estados_candado, [False])


if __name__ == "__main__":
    unittest.main()
