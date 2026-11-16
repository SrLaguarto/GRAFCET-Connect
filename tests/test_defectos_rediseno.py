"""Defectos abiertos tras el veredicto de la rama de rediseño (F2 a F10) y lo que halló la revisión técnica (R1 a R3)."""
import re
import unittest
from pathlib import Path

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtWidgets import QApplication
    from escritorio import estilo

AULA_ENTRADAS = ["pulsador_marcha", "pulsador_paro", "seta_emergencia", "selector_manual", "selector_automatico", "sensor_pieza_cinta",
                 "detector_inductivo_metal", "detector_capacitivo_plastico", "presostato_linea_aire"] \
    + [f"final_carrera_cilindro_{c}_{s}" for c in "ABC" for s in ("avance", "retroceso")]
AULA_SALIDAS = ["motor_cinta_transportadora", "piloto_marcha", "piloto_averia"] \
    + [f"electrovalvula_cilindro_{c}_{s}" for c in "ABC" for s in ("avance", "retroceso")]


@unittest.skipUnless(QT, "requiere PySide6")
class Defectos(BaseQt):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.w.hide)

    def _simulacion(self, n_entradas, ancho, alto):
        w, e = self.vacio()
        self.cadena(e)
        for k in range(n_entradas):
            e.ed.add_variable(AULA_ENTRADAS[k % len(AULA_ENTRADAS)] + ("" if k < len(AULA_ENTRADAS) else f"_{k}"), "input", {"kind": "bool"})
        for n in AULA_SALIDAS:
            e.ed.add_variable(n, "output", {"kind": "bool"})
        e.cambia()
        w.resize(ancho, alto)
        w.show()
        QApplication.processEvents()
        self.assertTrue(w.cambiar_modo("simular"))
        for _ in range(4):
            QApplication.processEvents()
        return w, e

    @staticmethod
    def _filas_visibles(w):
        vp, t = w.scroll.viewport(), w.t_vars
        y = t.mapTo(vp, QPoint(0, 0)).y() + t.horizontalHeader().height()
        visibles = 0
        for r in range(t.rowCount()):
            y += t.rowHeight(r)
            if y <= vp.height():
                visibles += 1
        return visibles

    def test_SRED07_las_entradas_se_desplazan_por_dentro_y_dejan_ver_cuatro_filas_de_salidas(self):
        """REQ-SIM-03, REQ-EDT-09 (F2): con 6, 10, 14 y 17 entradas de nombre largo, a 1366, 1920 y 960×1040, «Salidas y variables» deja
        ver al menos cuatro filas (o todas, si hay menos) sin desplazar el panel; la caja «Entradas» se desplaza por dentro."""
        for ancho, alto in ((1366, 768), (1920, 1080), (960, 1040)):
            for n in (6, 10, 14, 17):
                w, e = self._simulacion(n, ancho, alto)
                filas = w.t_vars.rowCount()
                self.assertGreaterEqual(filas, 6)
                self.assertGreaterEqual(self._filas_visibles(w), min(4, filas), (ancho, alto, n, w.scroll.height(), w.sc_entradas.height(), w.t_vars.height(), [w.t_vars.rowHeight(r) for r in range(filas)], w.derecho.width(), w.size()))
                if n >= 14 and (ancho, alto) == (1366, 768):
                    self.assertGreater(w.sc_entradas.verticalScrollBar().maximum(), 0, "con muchas entradas, la caja se desplaza por dentro")
                    self.assertEqual(w.scroll.horizontalScrollBar().maximum(), 0)
                w.cambiar_modo("editar")
                w.hide()

    def test_SRED08_foco_de_teclado_en_planos(self):
        """REQ-EDT-09 (F3): el lienzo de la hoja lleva anillo de foco de teclado como los demás controles, y las áreas de desplazamiento de
        PLANOS (que no hacen nada con el teclado) no reciben el foco."""
        from escritorio.laminas import VistaLamina
        from escritorio.ventana import _FocoTeclado
        self.assertIn(VistaLamina, _FocoTeclado.CON_ANILLO)
        vista = VistaLamina()
        vista.resize(200, 160)
        vista.show()
        QApplication.processEvents()
        vista.setFocus(Qt.FocusReason.TabFocusReason)
        QApplication.processEvents()
        sin = vista.grab().toImage()
        estilo.poner(vista, tecl=True)
        con = vista.grab().toImage()
        self.assertNotEqual(sin, con, "con el foco de teclado se pinta el anillo")
        estilo.poner(vista, tecl=False)
        self.assertEqual(vista.grab().toImage(), sin, "con el ratón, no")
        vista.close()
        self.assertEqual(self.w.panel_planos.scroll_hojas.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_SRED09_el_boton_de_plegar_no_tapa_las_entradas(self):
        """REQ-SIM-03, REQ-EDT-09 (F4): el botón de plegar el panel derecho está en una fila de título propia sobre el área que se
        desplaza: ni siquiera con el panel desplazado tapa la primera entrada."""
        w, e = self._simulacion(14, 1366, 768)
        w.scroll.verticalScrollBar().setValue(w.scroll.verticalScrollBar().maximum())
        QApplication.processEvents()
        boton = w.flechas["derecho"]
        r_boton = QRect(boton.mapTo(w, QPoint(0, 0)), boton.size())
        r_area = QRect(w.scroll.mapTo(w, QPoint(0, 0)), w.scroll.size())
        self.assertFalse(r_boton.intersects(r_area), (r_boton, r_area))
        self.assertEqual(w.titulo_sim.text(), "Simulación")

    def test_SRED10_nombre_en_titulo_nativo_y_estado_en_pestanas(self):
        """Encargos D/G8: nombre en la ventana y modo visible salvo cuando se fusionan las herramientas."""
        w, e = self.vacio()
        self.assertIn(e.titulo, w.windowTitle())
        self.assertFalse(hasattr(w, "titulo"))
        for ancho, alto, visible in ((1366, 768, True), (960, 1032, True),
                                      (683, 384, False), (960, 540, False)):
            w.resize(ancho, alto)
            w.show()
            self.pasar_arranque(w)
            self.asentar_escala(w)
            for _ in range(3):
                QApplication.processEvents()
            self.assertIs(w.estado.parentWidget(), w.fila_pestanas)
            self.assertEqual(w.estado.isVisible(), visible)
            if visible:
                self.assertIn("EDICIÓN", w.estado.elegida())
                self.assertGreater(w.estado.x(), w.pestanas_vistas.geometry().right())
                self.assertLess(w.estado.geometry().right(), w.luz_es.x())

    def test_SRED11_variables_a_un_cuarto_de_pantalla_lleva_una_sola_barra_vertical(self):
        """REQ-EDT-07, REQ-EDT-09 (F10): con muchas variables en un panel bajo, se desplaza la tabla o el panel, no los dos a la vez."""
        w, e = self.vacio()
        for k in range(29):
            e.ed.add_variable(f"variable_larga_{k:02d}", "input", {"kind": "bool"})
        e.cambia()
        w.resize(960, 520)
        w.show()
        w._mostrar_panel("derecho", True)
        for _ in range(4):
            QApplication.processEvents()
        pagina, tabla = w.derecho.widget(1), w.variables.tabla
        self.assertTrue(tabla.verticalScrollBar().isVisible() or pagina.verticalScrollBar().isVisible())
        self.assertFalse(tabla.verticalScrollBar().isVisible() and pagina.verticalScrollBar().isVisible(), "una sola barra vertical")

    def test_SRED12_histeresis_de_la_escala_en_el_umbral(self):
        """REQ-EDT-09 (F7, R2): ya en la escala grande, no se vuelve a la normal hasta 40 px por debajo del umbral de 1600×900; arrastrar
        el borde justo por el umbral no reaplica la hoja una y otra vez."""
        self.assertEqual(estilo.escala_para(1600, 900), "grande")
        self.assertEqual(estilo.escala_para(1599, 900), "normal")
        self.assertEqual(estilo.escala_para(1570, 880, "grande"), "grande")
        self.assertEqual(estilo.escala_para(1559, 900, "grande"), "normal")
        self.assertEqual(estilo.escala_para(1590, 900, "normal"), "normal", "para subir, el umbral de siempre")
        from unittest import mock
        w, e = self.vacio()
        w.resize(1700, 950)
        w.show()
        QApplication.processEvents()
        self.assertEqual(w._escala, "grande")
        self.pasar_arranque(w)
        original = type(w)._cambiar_escala
        with mock.patch.object(type(w), "_cambiar_escala", autospec=True, side_effect=original) as cambio:
            for ancho in (1598, 1605, 1596, 1602, 1580, 1610):
                w.resize(ancho, 950)
                QApplication.processEvents()
            self.assertEqual(cambio.call_count, 0, "oscilar alrededor del umbral no cambia la escala")
            self.assertEqual(w._escala, "grande")
            w._ancho_forzado = 500
            w.resize(1500, 950)
            QApplication.processEvents()
            self.assertEqual(w._escala, "grande", "la escala nueva se aplica al acabar la ráfaga, no en el acto")
            self.asentar_escala(w)
            self.assertEqual(w._escala, "normal")
            self.assertEqual(cambio.call_count, 1)
        self.assertEqual(w._ancho_forzado, 0, "al cambiar de escala se vuelve a medir «Reiniciar» (R2)")

    def test_SRED13_las_tablas_de_estado_a_218_px_no_se_desplazan_a_los_lados(self):
        """REQ-SIM-03 (desplazamiento horizontal): con el panel de 218 px (con y sin barra vertical) las columnas suman justo el visor de la
        tabla: ni barra ni desplazamiento horizontal, y ninguna columna se esconde."""
        for n in (0, 12):
            w, e = self._simulacion(n, 960, 1040)
            self.assertEqual(w.derecho.width(), 218)
            for t in (w.t_vars, w.t_temp):
                self.assertEqual(t.horizontalScrollBar().maximum(), 0, (n, t.columnCount()))
                self.assertLessEqual(sum(t.columnWidth(c) for c in range(4)), t.viewport().width(), n)
                self.assertEqual([t.isColumnHidden(c) for c in range(4)], [False] * 4)
                self.assertGreaterEqual(t.columnWidth(0), 84)
            w.cambiar_modo("editar")
            w.hide()

    def test_SRED14_los_nombres_de_salidas_y_variables_ocupan_dos_lineas_como_mucho(self):
        """REQ-SIM-03 (F9): a 1366 y a 1920 los nombres de «Salidas y variables» se reparten en dos líneas como máximo y «Contribuyen» no
        pasa de dos."""
        for ancho, alto in ((1366, 768), (1920, 1080)):
            w, e = self._simulacion(6, ancho, alto)
            t, d = w.t_vars, w._del_vars
            for r in range(t.rowCount()):
                for c, delegado in ((0, d[0]), (3, d[1])):
                    if t.item(r, c) is not None and t.item(r, c).text():
                        self.assertLessEqual(delegado.texto_visible(t, r, c).count("\n") + 1, 2, (ancho, r, c, t.item(r, c).text()))
            w.cambiar_modo("editar")
            w.hide()

    def test_SRED15_bajar_de_1920_a_683_o_640_cabe_en_una_sola_peticion(self):
        """REQ-EDT-09 (F6): con la escala grande los paneles laterales ya no suben el mínimo de la ventana: pedir 683 o 640 px de ancho desde
        1920×1080 se cumple a la primera."""
        for pedido in (683, 640):
            w, e = self.vacio()
            w.resize(1920, 1080)
            w.show()
            for _ in range(3):
                QApplication.processEvents()
            self.assertEqual(w._escala, "grande")
            w.resize(pedido, 600)
            QApplication.processEvents()
            self.assertEqual(w.width(), pedido)
            self.assertEqual((w.ancho_lateral, w.ancho_derecho), (218, 218))
            w.hide()

    def test_SRED16_ningun_singleshot_de_la_ventana_sin_objeto_de_contexto(self):
        """REQ-EDT-09 (R1): los temporizadores de un disparo de la ventana llevan `self` como contexto (si la ventana se destruye antes de
        que salten no llaman a objetos C++ ya borrados)."""
        fuente = (Path(__file__).resolve().parents[1] / "escritorio" / "ventana.py").read_text(encoding="utf-8")
        sin_contexto = re.findall(r"QTimer\.singleShot\((?!300,|1500,)\d+,\s*(?:lambda|self\.[_a-z]\w*\s*\))", fuente)
        self.assertEqual(sin_contexto, [])

    def test_SRED17_las_etiquetas_de_los_canales_ganan_sitio_con_poco_ancho(self):
        """REQ-SIM-03 (F5): con media pantalla y un cuarto, la mitad del marco que cae dentro mide lo que necesita (no 200 px) y el mapa se
        lleva más que las listas: la etiqueta de la variable asignada mide bastante más de los 65-71 px de antes."""
        from escritorio.entradas_salidas import PanelES
        from grafcet.builder import M
        p = PanelES()
        p.cargar(M().var("pulsador_de_marcha_general", "input").step("0", True).doc)
        p.resize(960, 520)
        p.show()
        p.autoasignar({v["id"] for v in p.variables})
        for _ in range(3):
            QApplication.processEvents()
        t = next(t for t in p.terminales.values() if t.variable)
        self.assertLess(p.ancho_interior, 200)
        self.assertGreaterEqual(t.nombre.width(), 100)
        p.resize(1366, 768)
        for _ in range(3):
            QApplication.processEvents()
        self.assertEqual(p.ancho_interior, 200, "con ancho de sobra, el de la escala")
        p.close()

    def test_SRED18_el_delegado_de_nombres_ya_no_lleva_columna_secundaria(self):
        """REQ-EDT-09 (R3): tras mantener todas las columnas de las tablas de estado, `DelegadoNombres` no necesita `secundaria`."""
        from escritorio.paneles import DelegadoNombres
        self.assertFalse(hasattr(DelegadoNombres(self.w.t_temp, (0,)), "secundaria"))

    def test_SRED19_la_zona_de_edicion_esta_fija_al_abrir_y_cerrar_propiedades(self):
        """REQ-EDT-09: el zoom va siempre en la cabecera y el dibujo empieza siempre a la misma altura: a 2000×1250, 1366×768 y 960×1040,
        con Propiedades cerrado, abierto con una etapa y abierto con una transición, el origen del visor del dibujo, el recuadro del zoom
        y el aviso de diagnósticos no cambian de sitio."""
        from PySide6.QtCore import QPointF
        for ancho, alto in ((2000, 1250), (1366, 768), (960, 1040)):
            w, e = self.vacio()
            ids = self.cadena(e)
            w.resize(ancho, alto)
            w.show()
            for _ in range(4):
                QApplication.processEvents()
            d = w.diagrama
            medidas = []
            for estado in ("cerrado", "etapa", "transicion"):
                if estado == "cerrado":
                    e.seleccionar([])
                    w._mostrar_panel("inferior", False)
                else:
                    e.seleccionar([ids[0] if estado == "etapa" else ids[1]])
                    w._abrir_opciones()
                for _ in range(6):
                    QApplication.processEvents()
                lista = d.lista_diagnosticos
                medidas.append((estado, d.viewport().mapToGlobal(QPoint(0, 0)).y(), d.barra.mapToGlobal(QPoint(0, 0)),
                                d.barra_integrada, d.barra.width(), lista.mapTo(d, QPoint(0, 0)), lista.width()))
            for m in medidas[1:]:
                self.assertEqual(m[1:], medidas[0][1:], (ancho, alto, m[0]))
            w.hide()

    @staticmethod
    def _tinta(widget):
        img = widget.grab().toImage()
        return sum(1 for y in range(0, img.height(), 3) for x in range(0, img.width(), 3) if img.pixelColor(x, y).lightness() < 200)

    def test_SRED20_cruzar_el_umbral_de_la_escala_no_deja_vacio_ningun_panel(self):
        """REQ-EDT-09: cruzar 1600×900 en los dos sentidos varias veces (con resize y con showMaximized) deja la paleta de Elementos, la tabla
        de Variables, el panel de simulación, Propiedades, PLANOS y la vista de E/S con su contenido a la vista y repintándose (una paleta
        con `updatesEnabled` falso se veía vacía al maximizar)."""
        w, e = self.vacio()
        ids = self.cadena(e)
        tamanos = [(1680, 1100), (2000, 1250), (1366, 768), (2000, 1250), (1500, 1000), (1700, 1000), (1366, 768)]
        w.show()
        for ancho, alto in tamanos:
            w.resize(ancho, alto)
            for _ in range(4):
                QApplication.processEvents()
            e.seleccionar([ids[1]])
            w._abrir_opciones()
            for _ in range(3):
                QApplication.processEvents()
            p = w.paleta
            self.assertTrue(p.isVisible() and p.width() > 0 and p.height() > 0 and p.count() >= 10, (ancho, alto))
            for panel in (p, w.variables.tabla, w.props, w.dock, w.derecho):
                self.assertTrue(panel.updatesEnabled(), (ancho, alto, type(panel).__name__))
            vis = [i for i in range(p.count()) if p.viewport().rect().intersects(p.visualItemRect(p.item(i)))]
            self.assertGreaterEqual(len(vis), 4, (ancho, alto))
            self.assertGreater(self._tinta(w.dock), 200, f"la paleta de Elementos se ve a {ancho}×{alto}")
            self.assertGreater(self._tinta(w.variables), 50)
            self.assertGreater(self._tinta(w.props), 50)
        for tamano in ((1366, 768), (2000, 1250), (1366, 768), (2000, 1250)):
            w.resize(*tamano)
            QApplication.processEvents()
            w.mostrar_es()
            for _ in range(3):
                QApplication.processEvents()
            self.assertTrue(w.panel_es.updatesEnabled())
            self.assertGreater(self._tinta(w.panel_es), 200, tamano)
            w._mostrar_pagina("planos")
            for _ in range(3):
                QApplication.processEvents()
            self.assertTrue(w.panel_planos.updatesEnabled())
            self.assertGreater(self._tinta(w.panel_planos), 100, tamano)
            w._mostrar_pagina(False)
        w.showMaximized()
        for _ in range(4):
            QApplication.processEvents()
        w.showNormal()
        w.resize(1680, 1100)
        for _ in range(4):
            QApplication.processEvents()
        self.assertGreater(self._tinta(w.dock), 200)
        self.assertTrue(w.cambiar_modo("simular"))
        for tamano in ((1366, 768), (2000, 1250), (1366, 768)):
            w.resize(*tamano)
            for _ in range(4):
                QApplication.processEvents()
            self.assertTrue(w.derecho.updatesEnabled() and w.t_vars.updatesEnabled())
            self.assertGreater(self._tinta(w.derecho), 100, tamano)

    def test_SRED21_el_marco_del_editor_de_una_celda_de_variables_se_ve_entero(self):
        """REQ-EDT-07, REQ-EDT-09: con el editor abierto en la última fila (y en la primera) de la tabla de Variables, nombre, papel y tipo, el
        editor cabe en su celda y el borde inferior de su marco aparece en la imagen de la tabla."""
        from PySide6.QtWidgets import QLineEdit, QComboBox
        w, e = self.vacio()
        for k in range(4):
            e.ed.add_variable(f"variable_{k}", "input", {"kind": "bool"})
        e.cambia()
        w.resize(1366, 768)
        w.show()
        w._mostrar_panel("derecho", True)
        for _ in range(4):
            QApplication.processEvents()
        t = w.variables.tabla
        for fila in (0, t.rowCount() - 1):
            for col in (0, 1, 2):
                t.setCurrentCell(fila, col)
                t.edit(t.model().index(fila, col))
                for _ in range(3):
                    QApplication.processEvents()
                celda = t.visualRect(t.model().index(fila, col))
                editor = next(x for x in [*t.viewport().findChildren(QLineEdit), *t.viewport().findChildren(QComboBox)] if x.isVisible() and x.geometry().intersects(celda))
                g = editor.geometry()
                self.assertLessEqual(g.bottom(), t.viewport().rect().bottom(), (fila, col, g, t.viewport().rect()))
                if col == 0:
                    self.assertLessEqual(g.height(), celda.height() + 1, (fila, col))
                    imagen = t.grab().toImage()
                    origen = t.viewport().mapTo(t, g.bottomLeft())
                    oscuros = sum(1 for x in range(g.width()) if imagen.pixelColor(origen.x() + x, origen.y()).lightness() < 120)
                    self.assertGreater(oscuros, g.width() // 4, f"el borde inferior del marco se dibuja (fila {fila})")
                t.closePersistentEditor(t.item(fila, col)) if t.item(fila, col) is not None else None
                t.setFocus()
                QApplication.processEvents()

    def test_SRED22_la_aplicacion_arranca_maximizada_y_el_constructor_no(self):
        """REQ-EDT-09: el arranque real (`main`) muestra la ventana maximizada, salvo con `--captura`; crear una `Ventana` no la maximiza
        ni la muestra (las pruebas no se ven afectadas)."""
        import os
        import tempfile
        from unittest import mock
        from escritorio import ventana as v
        self.assertFalse(self.w.isMaximized())
        tmp = tempfile.TemporaryDirectory()  # (instancia única en una carpeta propia: nunca la del usuario ni la de otro programa abierto)
        self.addCleanup(tmp.cleanup)
        for argv, maximizada in (([], True), (["--captura", "x.png"], False)):
            with mock.patch("escritorio.instancia_unica.directorio_instancia", return_value=Path(tmp.name) / "instancia"),                     mock.patch.object(v, "Ventana") as clase, mock.patch.object(QApplication, "exec", return_value=0),                     mock.patch("escritorio.errores.instalar"), mock.patch("escritorio.carpetas.asegurar_carpetas"),                     mock.patch.object(v.QTimer, "singleShot"), mock.patch.dict(os.environ, {v.actualizaciones.VARIABLE_SIN_ACTUALIZAR: "1"}):
                self.assertEqual(v.main(argv), 0)
                ventana = clase.return_value
                self.assertEqual(ventana.showMaximized.called, maximizada, argv)
                self.assertEqual(ventana.show.called, not maximizada, argv)

    def test_SRED23_sin_formulario_la_cabecera_va_arriba_y_el_panel_mide_lo_que_pide(self):
        """REQ-EDT-09: con varios elementos elegidos (o ninguno), la cabecera de Propiedades está arriba, en el mismo sitio y con el mismo alto que
        con una transición, el mensaje va justo debajo alineado arriba a la izquierda y el panel no deja bandas vacías."""
        for ancho, alto in ((2000, 1250), (1366, 768), (960, 1040)):
            w, e = self.vacio()
            ids = self.cadena(e)
            w.resize(ancho, alto)
            w.show()
            for _ in range(4):
                QApplication.processEvents()
            p = w.props
            e.seleccionar([ids[1]])
            w._abrir_opciones()
            for _ in range(5):
                QApplication.processEvents()
            self.assertEqual(p.pagina, "transicion")
            ref = (p.cabecera.mapTo(p, QPoint(0, 0)), p.cabecera.height(), p.titulo.mapTo(p, QPoint(0, 0)).y(), p.t_fijar.mapTo(p, QPoint(0, 0)).y())
            for seleccion in ([ids[0], ids[1], ids[2]], []):
                e.seleccionar(seleccion)
                for _ in range(6):
                    QApplication.processEvents()
                self.assertEqual(p.pagina, "vacio")
                self.assertEqual((p.cabecera.mapTo(p, QPoint(0, 0)), p.cabecera.height(), p.titulo.mapTo(p, QPoint(0, 0)).y(),
                                  p.t_fijar.mapTo(p, QPoint(0, 0)).y()), ref, (ancho, alto, seleccion))
                self.assertEqual(p.vacio.y(), p.cabecera.y() + p.cabecera.height(), "el mensaje, justo bajo la cabecera")
                self.assertTrue(p.vacio.alignment() & Qt.AlignmentFlag.AlignTop)
                self.assertLessEqual(w.inferior.height(), p.minimumSizeHint().height() + 12, "el panel mide lo que pide su contenido")
                if seleccion:
                    self.assertIn("elementos seleccionados", p.titulo.text())
            w.hide()

    def test_SRED24_las_categorias_de_bloques_van_en_la_fila_de_la_cabecera_si_caben(self):
        """REQ-EDT-09: con una transición elegida, a 1920 y 2000 las categorías están en la fila de la cabecera (empiezan donde la paleta y el
        área, entre el título y «Fijar»); a 960 vuelven a su fila propia, en dos filas, sin cortarse; el alto que pide el panel baja una fila."""
        from escritorio.alto_opciones import alto_minimo_transicion
        altos = {}
        for ancho, alto in ((2000, 1250), (1920, 1080), (1366, 768), (960, 1040)):
            w, e = self.vacio()
            ids = self.cadena(e)
            w.resize(ancho, alto)
            w.show()
            e.seleccionar([ids[1]])
            w._abrir_opciones()
            for _ in range(6):
                QApplication.processEvents()
            p, prog = w.props, w.props.prog
            sc = prog._sc_carpetas
            if ancho >= 1366:
                self.assertTrue(prog.cat_en_cabecera, (ancho, alto))
                self.assertTrue(sc.parentWidget().isAncestorOf(sc) and p.cabecera.isAncestorOf(sc))
                self.assertEqual(sc.mapTo(p, QPoint(0, 0)).x(), prog._sc_paleta.mapTo(p, QPoint(0, 0)).x(), "empiezan donde la paleta")
                self.assertGreater(sc.mapTo(p, QPoint(0, 0)).x(), p.titulo.mapTo(p, QPoint(0, 0)).x() + p.titulo.width() - 1)
                self.assertLess(sc.mapTo(p, QPoint(0, 0)).x() + sc.width(), p.t_fijar.mapTo(p, QPoint(0, 0)).x(), "antes de «Fijar»")
                self.assertEqual(sc.mapTo(p, QPoint(0, 0)).y(), p.titulo.mapTo(p, QPoint(0, 0)).y() + (p.titulo.height() - sc.height()) // 2)
                self.assertEqual(prog._sc_paleta.mapTo(p, QPoint(0, 0)).y(), p.izq.mapTo(p, QPoint(0, 0)).y(), "paleta y campos, justo bajo la cabecera")
                self.assertEqual(sc.horizontalScrollBar().maximum(), 0)
            else:
                self.assertFalse(prog.cat_en_cabecera)
                for b in prog.categorias.values():
                    sc.ensureWidgetVisible(b, 0, 0)
                    QApplication.processEvents()
                    self.assertTrue(sc.viewport().rect().contains(QRect(b.mapTo(sc.viewport(), QPoint(0, 0)), b.size())), b.text())
            altos[(ancho, alto)] = alto_minimo_transicion(p)
            w.hide()
        self.assertLess(altos[(1366, 768)], 330, "con las categorías en la cabecera el panel gana una fila (antes ≈ 334 px)")

    def test_SRED25_ningun_panel_tapa_el_borde_de_otro(self):
        """REQ-EDT-09: con Propiedades abierto (y plegado), el borde de las tarjetas de arriba —Elementos, el dibujo y Variables— y el de
        Propiedades se ve entero en el `grab()` de la ventana: los píxeles de sus cuatro lados son del color del borde, a escala normal y grande."""
        for ancho, alto in ((1366, 768), (2000, 1250)):
            w, e = self.vacio()
            ids = self.cadena(e)
            w.resize(ancho, alto)
            w.show()
            e.seleccionar([ids[1]])
            w._abrir_opciones()
            for _ in range(6):
                QApplication.processEvents()
            for abierto in (True, False):
                w._mostrar_panel("inferior", abierto)
                for _ in range(6):
                    QApplication.processEvents()
                imagen = w.grab().toImage()
                tarjetas = [("Elementos", w.dock), ("dibujo", w.diagrama.parentWidget()), ("Variables", w.derecho.widget(1).widget())]
                if abierto:
                    tarjetas.append(("Propiedades", w.props))
                for nombre, t in tarjetas:
                    r = QRect(t.mapTo(w, QPoint(0, 0)), t.size())
                    if t.window() is not w or not t.isVisible():
                        continue
                    cx, cy = r.left() + r.width() // 2, r.top() + r.height() // 2
                    for lado, (x, y) in (("arriba", (cx, r.top())), ("abajo", (cx, r.bottom())), ("izquierda", (r.left(), cy)), ("derecha", (r.right(), cy))):
                        if nombre == "dibujo" and lado == "arriba":
                            continue  # (el borde de arriba del dibujo lo lleva la franja de modo, a propósito)
                        self.assertEqual(imagen.pixelColor(x, y).name(), estilo.BORDE, (ancho, alto, abierto, nombre, lado, x, y))
            w.hide()


if __name__ == "__main__":
    unittest.main()
