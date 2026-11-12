"""Alturas de los controles (encargo 5 del rediseño): nada sobresale de su contenedor, los controles miden el alto de su token, la tabla de
Variables añade una fila visible por pulsación aunque haya un nombre en edición, la barra de edición y la IP en la cabecera del marco de E/S."""
import tempfile
import unittest
from pathlib import Path

from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPoint, QPointF, QRect, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractScrollArea, QApplication, QComboBox, QLineEdit, QMenu, QPushButton,
                                   QSpinBox, QVBoxLayout, QWidget)
    from escritorio import estilo

TAMANOS = ((1366, 768), (2000, 1250))


def _es_contenido_desplazable(w, ventana):
    """True si `w` vive dentro del visor de un área de desplazamiento (tabla, lista, QScrollArea) o de un menú: ahí lo que sale se recorta o se desplaza."""
    p = w.parentWidget()
    while p is not None and p is not ventana:
        if isinstance(p.parentWidget(), QAbstractScrollArea) and p is p.parentWidget().viewport():
            return True
        if isinstance(p, QMenu) or p.windowType() in (Qt.WindowType.Popup, Qt.WindowType.ToolTip):
            return True
        p = p.parentWidget()
    return False


def desbordes(ventana, tolerancia=0):
    """Los widgets visibles que se salen del rectángulo de su padre (salvo contenido de áreas de desplazamiento, popups y ventanas)."""
    fuera = []
    for w in ventana.findChildren(QWidget):
        p = w.parentWidget()
        if p is None or w.isWindow() or not w.isVisible() or not p.isVisible() or _es_contenido_desplazable(w, ventana):
            continue
        if w.width() <= 0 or w.height() <= 0:
            continue
        r = QRect(0, 0, p.width(), p.height()).adjusted(-tolerancia, -tolerancia, tolerancia, tolerancia)
        if not r.contains(w.geometry()):
            fuera.append((type(w).__name__, w.objectName(), w.text() if isinstance(w, QAbstractButton) else "", w.geometry().getRect(),
                          type(p).__name__, p.objectName(), p.rect().getRect()))
    return fuera


def solapes(ventana, permitidos=()):
    """Los hermanos visibles de un mismo layout que se solapan (más de 1 px en cada eje). `permitidos`: pares de nombres de clase u objectName que se
    pintan a propósito uno sobre otro (hoy ninguno)."""
    res = []
    for p in [ventana, *ventana.findChildren(QWidget)]:
        lay = p.layout()
        if lay is None or not p.isVisible():
            continue
        ws = [lay.itemAt(i).widget() for i in range(lay.count())]
        # (isinstance: con un hijo recién destruido, PySide puede devolver el envoltorio de otro objeto en su lugar; pasó una vez en la suite)
        ws = [w for w in ws if isinstance(w, QWidget) and w.isVisible() and w.width() > 0 and w.height() > 0 and not w.isWindow()]
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                r = a.geometry().intersected(b.geometry())
                if r.width() > 1 and r.height() > 1 and not ({type(a).__name__, a.objectName()} & set(permitidos) and {type(b).__name__, b.objectName()} & set(permitidos)):
                    res.append((type(p).__name__, p.objectName(), (type(a).__name__, a.objectName(), a.geometry().getRect()), (type(b).__name__, b.objectName(), b.geometry().getRect())))
    return res


@unittest.skipUnless(QT, "requiere PySide6")
class Alturas(BaseQt):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.w.hide)

    def _preparar(self, ancho, alto):
        w, e = self.vacio()
        for n in ("marcha", "paro"):
            e.nueva_variable(n, "input")
        e.nueva_variable("motor", "output")
        ids = self.cadena(e)
        w.resize(ancho, alto)
        w.show()
        for _ in range(4):
            QApplication.processEvents()
        return w, e, ids

    def _bombear(self, n=8):
        for _ in range(n):
            QApplication.processEvents()

    def test_SALC01_ningun_control_sobresale_de_su_contenedor_con_propiedades_y_variables(self):
        """REQ-EDT-09, REQ-UX-01: con Propiedades de una transición, de una etapa y de una acción, y con Variables, a 1366×768 y 2000×1250,
        ningún widget visible se sale del rectángulo de su padre (fuera de los visores de desplazamiento)."""
        for ancho, alto in TAMANOS:
            w, e, ids = self._preparar(ancho, alto)
            w._mostrar_panel("derecho", True)
            did = e.poner_accion_suelta(QPointF(400, 200))
            for nombre, sel in (("transicion", ids[1]), ("etapa", ids[0]), ("accion", did), ("varios", [ids[0], ids[1]])):
                e.seleccionar(sel if isinstance(sel, list) else [sel])
                w._abrir_opciones()
                self._bombear(10)
                self.assertEqual(desbordes(w, 0), [], (ancho, alto, nombre))
            w.hide()

    def test_SALC02_cabecera_de_propiedades_contiene_categorias_y_fijar_y_el_primer_campo_queda_debajo(self):
        """REQ-EDT-09: en la cabecera de Propiedades, los chips de categoría y «Fijar» caben con al menos 2 px arriba y abajo y el campo
        «Etiqueta» empieza por debajo de la franja del título, de una transición y de una etapa y a las dos pantallas."""
        for ancho, alto in TAMANOS:
            w, e, ids = self._preparar(ancho, alto)
            p = w.props
            for nombre, ident, campo in (("transicion", ids[1], None), ("etapa", ids[0], p.s_etiqueta)):
                e.seleccionar([ident])
                w._abrir_opciones()
                self._bombear(10)
                franja = p.cabecera.rect()  # (los hijos de la cabecera dan su geometría en las coordenadas de ella)
                self.assertTrue(p.t_fijar.isVisible())
                fijar = p.t_fijar.geometry()
                self.assertGreaterEqual(fijar.top() - franja.top(), 2, (ancho, alto, nombre))
                self.assertGreaterEqual(franja.bottom() - fijar.bottom(), 2, (ancho, alto, nombre))
                if nombre == "transicion":
                    self.assertTrue(p.prog.cat_en_cabecera, (ancho, alto, "las categorías suben a la cabecera"))
                    chips = p.prog._sc_carpetas.geometry()
                    self.assertGreaterEqual(chips.top() - franja.top(), 2, (ancho, alto, nombre))
                    self.assertGreaterEqual(franja.bottom() - chips.bottom(), 2, (ancho, alto, nombre))
                    for b in p.prog.categorias.values():
                        self.assertLessEqual(b.height(), p.prog._sc_carpetas.height())
                    campo = p.izq.currentWidget().findChildren(QLineEdit)[0]
                if campo is not None and campo.isVisible():
                    y = campo.mapTo(p, QPoint(0, 0)).y()
                    self.assertGreater(y, p.cabecera.geometry().bottom(), (ancho, alto, nombre, "el campo empieza por debajo de la franja"))
            w.hide()

    def test_SALC03_botones_campos_y_desplegables_miden_el_alto_de_su_token(self):
        """REQ-UX-01: un QPushButton, un QLineEdit, un QComboBox y un QSpinBox sueltos, con la hoja global, miden `ALTO_CONTROL` (±1) a las dos
        escalas (28 y 32 px), también con el foco (anillo de 2 px), y los botones de la barra de edición miden `ALTO_BARRA` (±2)."""
        anterior = estilo.ESCALA
        try:
            for escala, esperado, barra in (("normal", 28, 30), ("grande", 32, 34)):
                estilo.activar_escala(escala)
                self.assertEqual((estilo.ALTO_CONTROL, estilo.ALTO_BARRA), (esperado, barra))
                cont = QWidget()
                cont.setStyleSheet(estilo.hoja_global())
                lay = QVBoxLayout(cont)
                widgets = [QPushButton("Eliminar"), QLineEdit("x"), QComboBox(), QSpinBox()]
                widgets[2].addItem("Entradas digitales (Discrete Inputs)")
                for x in widgets:
                    lay.addWidget(x)
                cont.show()
                self._bombear(4)
                for x in widgets:
                    self.assertLessEqual(abs(x.height() - esperado), 1, (escala, type(x).__name__, x.height()))
                for x in widgets:
                    x.setProperty("tecl", True)
                    x.setFocus()
                    estilo.repulir(x)
                    self._bombear(2)
                    self.assertLessEqual(abs(x.height() - esperado), 1, (escala, "foco", type(x).__name__, x.height()))
                cont.hide()
                cont.deleteLater()
        finally:
            estilo.activar_escala(anterior)
        w, e, ids = self._preparar(1366, 768)
        for a in (w.a_deshacer, w.a_debajo):
            self.assertLessEqual(abs(w.tb_edit.widgetForAction(a).height() - estilo.ALTO_BARRA), 2)
        w.hide()

    def test_SALC04_variables_botones_y_celdas_miden_lo_que_su_fila(self):
        """REQ-UX-01: los botones de Variables miden `ALTO_CONTROL_COMPACTO` y el editor de una celda no pasa del alto de su fila, a las dos pantallas."""
        for ancho, alto in TAMANOS:
            w, e, ids = self._preparar(ancho, alto)
            w._mostrar_panel("derecho", True)
            self._bombear(6)
            v = w.variables
            for b in (*v.b_nuevas.values(), v.b_quitar):
                self.assertLessEqual(abs(b.height() - estilo.ALTO_CONTROL_COMPACTO), 1, (ancho, b.text(), b.height()))
            v.nueva("output")
            self._bombear(4)
            editor = v.tabla.indexWidget(v.tabla.currentIndex())
            self.assertIsInstance(editor, QLineEdit)
            self.assertLessEqual(editor.height(), v.tabla.rowHeight(v.tabla.currentRow()))
            w.hide()

    def test_SALC05_pagina_de_configuracion_y_tabla_avanzada_de_es(self):
        """REQ-EDT-09, REQ-DAT-02: en Configuración, la IP, el puerto, el esclavo y los canales miden el alto del token, y en la tabla avanzada las filas
        miden lo que sus desplegables y campos (ninguno más alto que su fila ni cortado), a las dos pantallas."""
        for ancho, alto in TAMANOS:
            w, e, ids = self._preparar(ancho, alto)
            w.mostrar_es()
            self._bombear(8)
            p = w.panel_es
            p.abrir_configuracion()
            p._alternar_avanzado()
            self._bombear(10)
            esperado = estilo.ALTO_CONTROL
            for caja in p.host.cajas:
                self.assertLessEqual(abs(caja.height() - esperado), 1, (ancho, "IP", caja.height()))
            for sp in (p.puerto, p.unidad, *p.offsets.values(), *p.cantidades.values()):
                self.assertLessEqual(abs(sp.height() - esperado), 1, (ancho, "spin", sp.height()))
            t = p.tabla
            self.assertEqual(t.rowCount(), 3)
            for fila in range(t.rowCount()):
                for col in (4, 5, 6, 7):
                    c = t.cellWidget(fila, col)
                    self.assertLessEqual(c.height(), t.rowHeight(fila), (ancho, fila, col, c.height(), t.rowHeight(fila)))
                combo = t.cellWidget(fila, 4)
                self.assertGreaterEqual(combo.height(), combo.fontMetrics().height() + 2, "el texto del desplegable cabe entero")
                self.assertGreaterEqual(t.columnWidth(4), combo.sizeHint().width(), "el área se lee entera")
            self.assertEqual(desbordes(p.dialogo_config, 0), [], (ancho, alto))
            p.dialogo_config.close()
            w.hide()

    def test_SALC06_con_un_nombre_en_edicion_cada_boton_anade_una_fila_visible(self):
        """REQ-EDT-09 (F): con un nombre escrito en una fila nueva y el editor abierto, pulsar «+ Salida» (clic real) confirma el nombre (se crea la
        variable) y añade UNA fila nueva visible con el cursor en su nombre; cada pulsación añade una fila; si el nombre se rechaza, se ve el motivo
        y no se añade otra."""
        w, e, ids = self._preparar(1366, 768)
        w._mostrar_panel("derecho", True)
        self._bombear(6)
        v = w.variables
        inicio = v.tabla.rowCount()
        QTest.mouseClick(v.b_nuevas["input"], Qt.MouseButton.LeftButton)
        self._bombear(4)
        self.assertEqual(v.tabla.rowCount(), inicio + 1)
        self.assertEqual(v.tabla.state(), QAbstractItemView.State.EditingState)
        QTest.keyClicks(v.tabla.indexWidget(v.tabla.currentIndex()), "sensor_nuevo")
        for k in range(1, 4):
            QTest.mouseClick(v.b_nuevas["output"], Qt.MouseButton.LeftButton)
            self._bombear(4)
            self.assertEqual(v.tabla.rowCount(), inicio + 1 + k, f"pulsación {k}: una fila más, a la vista")
            self.assertEqual(v.tabla.state(), QAbstractItemView.State.EditingState, "el cursor está en el nombre de la fila nueva")
            self.assertEqual(v.tabla.currentRow(), v.tabla.rowCount() - 1)
            self.assertTrue(v.tabla.indexWidget(v.tabla.currentIndex()).isVisible())
        self.assertIn("sensor_nuevo", [x["name"] for x in e.variables()], "el nombre escrito se confirmó")
        self.assertEqual(v.sin_nombre(), 3)
        # un nombre que se rechaza (repetido): se muestra el motivo y no se añade otra fila
        QTest.keyClicks(v.tabla.indexWidget(v.tabla.currentIndex()), "sensor_nuevo")
        filas = v.tabla.rowCount()
        QTest.mouseClick(v.b_nuevas["internal"], Qt.MouseButton.LeftButton)
        self._bombear(6)
        self.assertTrue(v.msg.text(), "el motivo del rechazo se ve")
        self.assertEqual(v.tabla.rowCount(), filas)
        w.hide()

    def test_SALC07_barra_de_edicion_orden_ayudas_y_anchura(self):
        """REQ-EDT-01, REQ-EDT-11: tras Play y Reiniciar, una sola fila: | Deshacer · Rehacer | Cortar · Copiar · Pegar · Borrar | Añadir debajo ·
        Dependencias · Errores; los seis primeros solo icono con el atajo en la ayuda; cabe a 1366×768 sin cortar nada; al simular quedan desactivados."""
        w, e, ids = self._preparar(1366, 768)
        acciones = list(w.tb_edit.actions())
        esperado = ["|", w.a_deshacer, w.a_rehacer, "|", w.a_cortar, w.a_copiar, w.a_pegar, w.a_borrar, "|", w.a_debajo, w.a_dependencias, w.a_errores]
        self.assertEqual([("|" if a.isSeparator() else a) for a in acciones], esperado)
        for a, atajo in ((w.a_deshacer, "Ctrl+Z"), (w.a_rehacer, "Ctrl+Y"), (w.a_cortar, "Ctrl+X"), (w.a_copiar, "Ctrl+C"),
                         (w.a_pegar, "Ctrl+V"), (w.a_borrar, "Supr")):
            self.assertIn(atajo, a.toolTip())
            boton = w.tb_edit.widgetForAction(a)
            self.assertEqual(boton.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonIconOnly)
            self.assertFalse(a.icon().isNull(), a.text())
            self.assertTrue(boton.isVisible())
        self.assertEqual(w.tb_edit.widgetForAction(w.a_debajo).toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.assertIs(w.diagrama.b_dependencias.parent(), w.tb_edit)
        self.assertLessEqual(w.tb_edit.geometry().right(), w.herramientas_grafcet.width())
        self.assertEqual(desbordes(w, 0), [])
        for a in (x for x in acciones if not x.isSeparator()):
            wd = w.tb_edit.widgetForAction(a)
            self.assertTrue(w.tb_edit.rect().contains(wd.geometry()), a.text())
        # la habilitación es la de las acciones: sin selección, Copiar y Borrar desactivadas
        e.seleccionar([])
        self._bombear(3)
        self.assertFalse(w.tb_edit.widgetForAction(w.a_borrar).isEnabled())
        self.assertFalse(w.tb_edit.widgetForAction(w.a_copiar).isEnabled())
        e.seleccionar([ids[0]])
        self._bombear(3)
        self.assertTrue(w.tb_edit.widgetForAction(w.a_borrar).isEnabled())
        # en simulación siguen ahí, desactivados, y Dependencias sigue activo
        self.assertTrue(w.cambiar_modo("simular"))
        self._bombear(6)
        for a in (w.a_deshacer, w.a_rehacer, w.a_cortar, w.a_copiar, w.a_pegar, w.a_borrar, w.a_debajo):
            self.assertTrue(w.tb_edit.widgetForAction(a).isVisible() and not w.tb_edit.widgetForAction(a).isEnabled(), a.text())
        self.assertTrue(w.diagrama.b_dependencias.isVisible() and w.diagrama.b_dependencias.isEnabled())
        self.assertTrue(w.b_errores.isVisible() and not w.b_errores.isEnabled(), "«Mostrar errores» se desactiva al simular, como los demás de edición")
        w.hide()

    def test_SALC08_barra_de_edicion_cabe_en_pantalla_partida(self):
        """REQ-EDT-11: a 1000×600 y 800×600 la barra de edición cabe en la fila (el texto de «Añadir debajo» y «Dependencias» se oculta antes
        que cualquier botón)."""
        for ancho, alto in ((1000, 600), (800, 600)):
            w, e, ids = self._preparar(ancho, alto)
            self._bombear(6)
            self.assertLessEqual(w.tb_sim.width() + w.tb_edit.sizeHint().width(), w.herramientas_grafcet.width(), (ancho, alto))
            for a in w.tb_edit.actions():
                if not a.isSeparator() and a.isVisible():
                    wd = w.tb_edit.widgetForAction(a)
                    self.assertTrue(wd.isVisible() and w.tb_edit.rect().contains(wd.geometry()), (ancho, a.text()))
            w.hide()

    # -- IP, puerto y esclavo en la cabecera del marco de E/S ------------------------------------------
    def _es(self):
        w, e, ids = self._preparar(1366, 768)
        w.mostrar_es()
        self._bombear(8)
        return w, w.panel_es

    def test_SALC09_ip_puerto_y_esclavo_se_editan_en_el_marco_y_se_ven_en_configuracion(self):
        """REQ-DAT-02, REQ-UX-01 (H): desconectado, la cabecera del marco muestra la IP, el puerto y el esclavo editables; lo que se cambia ahí se
        aplica (`config`), se ve en Configuración y se guarda en el mapa del proyecto; y al revés; un valor no válido se marca y no se aplica."""
        from conexion.configuracion import ARCHIVO, Configuracion
        w, p = self._es()
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        w._raiz_modbus = lambda: Path(carpeta.name)
        l = p.lienzo
        self.assertIs(l.cabecera_marco.currentWidget(), l.edicion_destino)
        self.assertEqual(l.ip.accessibleName(), "IP del servidor")
        self.assertEqual((l.puerto.accessibleName(), l.unidad.accessibleName()), ("Puerto", "Esclavo ID"))
        self.assertEqual([c.text() for c in l.ip.cajas], ["192", "168", "1", "133"])
        for caja, v in zip(l.ip.cajas, ("10", "0", "0", "7")):
            caja.setText(v)
        l.ip.editingFinished.emit()
        l.puerto.setValue(1502)
        l.unidad.setValue(3)
        self._bombear(4)
        self.assertEqual((p.host.text(), p.puerto.value(), p.unidad.value()), ("10.0.0.7", 1502, 3))
        self.assertEqual((p.config.host, p.config.puerto, p.config.unidad), ("10.0.0.7", 1502, 3))
        guardada = Configuracion.cargar(Path(carpeta.name) / ARCHIVO, p.doc)
        self.assertEqual((guardada.host, guardada.puerto, guardada.unidad), ("10.0.0.7", 1502, 3), "se guarda donde ya lo hacía Configuración")
        self.assertEqual(p.destino.text(), "(10.0.0.7:1502)\nEsclavo ID:3")
        # al revés: lo que se cambia en Configuración se ve en la cabecera
        p.puerto.setValue(503)
        for caja, v in zip(p.host.cajas, ("172", "16", "0", "9")):
            caja.setText(v)
        p.host.editingFinished.emit()
        p.unidad.setValue(5)
        self._bombear(4)
        self.assertEqual(([c.text() for c in l.ip.cajas], l.puerto.value(), l.unidad.value()), (["172", "16", "0", "9"], 503, 5))
        # un valor no válido (caja vacía) se marca y no se aplica
        antes = (p.config.host, p.config.puerto)
        l.ip.cajas[1].setText("")
        l.ip.editingFinished.emit()
        self._bombear(4)
        self.assertEqual((p.config.host, p.config.puerto), antes)
        self.assertTrue(all(c.property("invalido") for c in l.ip.cajas))
        self.assertIn("inválido", p.estado.text())
        l.ip.cajas[1].setText("16")
        l.ip.editingFinished.emit()
        self._bombear(4)
        self.assertFalse(any(c.property("invalido") for c in l.ip.cajas))
        w.hide()

    def test_SALC10_con_la_conexion_activa_la_cabecera_del_marco_es_solo_texto_y_no_cambia_de_ancho(self):
        """REQ-DAT-02, REQ-UX-01 (H): con la conexión activa vuelve el texto de solo lectura; el marco mide lo mismo con texto y con controles; los
        controles son alcanzables con Tab."""
        w, p = self._es()
        l = p.lienzo
        ancho, alto = l.cabecera_marco.width(), l.cabecera_marco.height()
        marco = l.marco.geometry()
        self.assertTrue(l.ip.isVisible() and l.puerto.isVisible() and l.unidad.isVisible())
        self.assertEqual(desbordes(w, 0), [])
        for x in (l.ip.cajas[0], l.puerto, l.unidad):
            self.assertTrue(x.focusPolicy() & Qt.FocusPolicy.TabFocus)
        p.ocupado(True)
        self._bombear(6)
        self.assertIs(l.cabecera_marco.currentWidget(), l.destino)
        self.assertFalse(l.ip.isVisible() or l.puerto.isVisible() or l.unidad.isVisible())
        self.assertEqual((l.cabecera_marco.width(), l.cabecera_marco.height()), (ancho, alto))
        self.assertEqual(l.marco.geometry(), marco)
        l.puerto.setValue(4000)  # (aunque se tocara, no se aplica)
        self.assertNotEqual(p.config.puerto, 4000)
        p.ocupado(False)
        self._bombear(4)
        self.assertIs(l.cabecera_marco.currentWidget(), l.edicion_destino)
        w.hide()

    def test_SALC11_ningun_hermano_visible_se_solapa_en_planos_y_en_es(self):
        """REQ-EDT-09, REQ-UX-01: en GRAFCET, PLANOS (sin hoja y con una) y la vista de E/S (desconectada y conectada), a 1366×768 y 2000×1250, ningún
        hermano visible de un mismo layout se solapa con otro, y nada sobresale de su contenedor; el marco de E/S empieza por debajo de la cabecera."""
        from escritorio.carpetas import predeterminada
        from grafcet.laminas import ajustes_lamina
        for ancho, alto in TAMANOS:
            w, e, ids = self._preparar(ancho, alto)
            barra = w.pestanas_vistas
            vistas = []
            QTest.mouseClick(barra, Qt.MouseButton.LeftButton, pos=barra.tabRect(1).center())
            self._bombear(8)
            vistas.append("planos sin hoja")
            self.assertEqual(solapes(w), [], (ancho, alto, "planos sin hoja"))
            self.assertEqual(desbordes(w, 0), [], (ancho, alto, "planos sin hoja"))
            plan = e.ed.add_sheet_plan("Plano de pruebas")
            ident = e.ed.add_plan_page(plan, ajustes_lamina({"plantilla": predeterminada()}))
            e.ed.set_page_graphics(ident, [{"refs": [ids[0]], "porcentaje": 100., "offset_mm": [0., 0.]}])
            e.cambia()
            QTest.mouseClick(barra, Qt.MouseButton.LeftButton, pos=barra.tabRect(0).center())
            QTest.mouseClick(barra, Qt.MouseButton.LeftButton, pos=barra.tabRect(1).center())
            self._bombear(10)
            self.assertEqual(w.panel_planos.lista.count(), 1)
            self.assertEqual(solapes(w), [], (ancho, alto, "planos con hoja"))
            self.assertEqual(desbordes(w, 0), [], (ancho, alto, "planos con hoja"))
            w.mostrar_es()
            self._bombear(8)
            self.assertEqual(solapes(w), [], (ancho, alto, "E/S desconectada"))
            self.assertEqual(desbordes(w, 0), [], (ancho, alto, "E/S desconectada"))
            lienzo = w.panel_es.lienzo
            self.assertGreaterEqual(lienzo.marco.y(), lienzo.cabecera_marco.y() - 4)
            titulo = lienzo.findChild(QWidget, "tituloPLC")
            texto = titulo.geometry().bottom() - titulo.contentsMargins().bottom()  # (el título lleva un margen inferior)
            self.assertGreaterEqual(lienzo.marco.y() - texto, 4, "el marco empieza por debajo del título de la sección, con aire")
            w.panel_es.mostrar_estado("conectado", "Conectado")
            self._bombear(8)
            self.assertEqual(solapes(w), [], (ancho, alto, "E/S conectada"))
            self.assertEqual(desbordes(w, 0), [], (ancho, alto, "E/S conectada"))
            self.assertGreaterEqual(lienzo.marco.y() - texto, 4)
            w.hide()


if __name__ == "__main__":
    unittest.main()
