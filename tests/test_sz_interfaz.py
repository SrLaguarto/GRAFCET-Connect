"""SZ: avisos amables, categorías coherentes, catálogo de ejemplos y vigencia."""
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QPA_FONTDIR', 'C:/Windows/Fonts')
os.environ.setdefault('GRAFCONNECT_SIN_ACTUALIZAR', '1')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from escritorio import estilo
from escritorio.edicion import Edicion, MSG_SIN_DESTINO
from escritorio.traer_modelo import Propuestas
from escritorio.avisos_nombres import corregir_nombres, resumen_nombres
from grafcet.editor import Editor, new_grafcet_document
from conexion.configuracion import Configuracion
from servidor_directo_falso import ServidorDirecto, senal
from tools import hoja_contactos as HC

NOMBRES = ['Pos. raise lids', 'Pos. at limit (lids)', 'Pos. raise bases', 'Pos. at limit bases']


class InterfazZ(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = HC.aplicacion()

    def edicion(self):
        return Edicion(Editor(new_grafcet_document('m')), 'Prueba')

    def dialogo(self, nombres=None, panel=None):
        from escritorio.entradas_salidas import PanelES
        from escritorio.traer_dialogo import DialogoTraer
        servidor = ServidorDirecto([senal(str(i), n) for i, n in enumerate(NOMBRES if nombres is None else nombres)])
        self.addCleanup(servidor.cerrar)
        if panel is None:
            panel = PanelES()
            self.addCleanup(panel.close)
            panel.directa.edicion = self.edicion()
        panel.cargar(panel.directa.edicion.ed.model,
                     Configuracion(host='127.0.0.1', puerto=servidor.puerto, modo='directo'))
        d = DialogoTraer(panel.directa)
        self.addCleanup(d.reject)
        limite = time.monotonic() + 5
        while d.propuestas is None and time.monotonic() < limite:
            self.app.processEvents()
            time.sleep(.005)
        self.assertIsNotNone(d.propuestas)
        return d

    def test_SZ1_aviso_corto_con_cuenta_y_signo(self):
        """REQ-EDT-09: al abrir se corrigen automáticamente; si el usuario escribe nombres con signos, un renglón lo explica."""
        d = self.dialogo()
        self.assertTrue(d.b_traer.isEnabled())
        tabla, _ = d.tablas[0]
        for row, n in enumerate(NOMBRES):
            tabla.item(row, 2).setText(n)
        self.assertIn('4 nombres', d.motivos.text())
        self.assertIn('punto', d.motivos.text())
        self.assertNotIn('\n', d.motivos.text())
        self.assertFalse(d.motivos.wordWrap())
        self.assertTrue(d.b_corregir.isEnabled())
        self.assertEqual(d.b_corregir.text(), "Corregir nombres incompatibles")

    def test_SZ_traer_centrada_y_acotada_en_la_ventana_principal(self):
        from PySide6.QtCore import QPoint, QRect
        from escritorio.medidas_propiedades import ancho_maximo

        for ancho, alto in ((683, 440), (960, 768), (1366, 768)):
            with self.subTest(ancho=ancho, alto=alto):
                c = HC.Contexto(ancho, alto)
                self.addCleanup(c.cerrar)
                c.w.paginas_es.setCurrentWidget(c.w.panel_es)
                c.mostrar()
                d = self.dialogo(panel=c.w.panel_es)
                d.show()
                HC._bombear(5)
                area = QRect(c.w.mapToGlobal(QPoint()), c.w.size())
                area = area.intersected(c.w.screen().availableGeometry())
                marco = d.frameGeometry()
                self.assertTrue(area.contains(marco), (area, marco))
                self.assertLessEqual(marco.width(), ancho_maximo())
                self.assertLessEqual((marco.center() - area.center()).manhattanLength(), 2)
                self.assertTrue(d.b_leer.isVisible() and d.b_traer.isVisible())
                imagen = d.grab().toImage()
                centro = imagen.width() // 2
                self.assertEqual(imagen.pixelColor(centro, 4), QColor(estilo.FONDO))
                self.assertEqual(imagen.pixelColor(0, 0).alpha(), 0)
                self.assertTrue(d.b_traer.isEnabled())
                d.tablas[0][0].item(0, 2).setText(NOMBRES[0])
                HC._bombear(2)
                self.assertGreaterEqual(d.b_corregir.width(), d.b_corregir.sizeHint().width())
                d.b_corregir.click()
                self.assertTrue(d.b_traer.isEnabled())
                d.reject()

    def test_SZ_traer_recorta_al_arrastrar_y_al_estrechar_la_ventana(self):
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtGui import QRegion
        from PySide6.QtTest import QTest

        c = HC.Contexto(960, 768)
        self.addCleanup(c.cerrar)
        c.w.paginas_es.setCurrentWidget(c.w.panel_es)
        c.mostrar()
        d = self.dialogo(panel=c.w.panel_es)
        d.show()
        HC._bombear(5)

        original = d.geometry()
        punto = d.titulo.rect().center()
        recorrido = QPoint(c.w.width() // 2, 0)
        QTest.mousePress(d.titulo, Qt.MouseButton.LeftButton, pos=punto)
        QTest.mouseMove(d.titulo, punto + recorrido)
        QTest.mouseRelease(d.titulo, Qt.MouseButton.LeftButton, pos=punto + recorrido)
        self.assertGreater(d.x(), original.x())
        self.assertEqual(d.size(), original.size())

        for ancho in (960, 683):
            c.w.resize(ancho, c.w.height())
            HC._bombear(5)
            cliente = QRect(c.w.mapToGlobal(QPoint()), c.w.size())
            visible = cliente.intersected(d.geometry()).translated(-d.pos())
            self.assertGreater(visible.width(), 0)
            self.assertLess(visible.width(), d.width())
            self.assertEqual(d.mask(), QRegion(visible))

        d.arrastre.limitar(original.topLeft())
        c.w.resize(960, c.w.height())
        HC._bombear(5)
        self.assertTrue(d.mask().isEmpty())
        d.reject()

    def test_SZ2_correccion_valida_unica_y_verde(self):
        """REQ-EDT-02: corregir conserva la edición manual y resuelve duplicados."""
        d = self.dialogo()
        e = d.propuestas.edicion
        e.nueva_variable('Pos at limit lids', 'output')
        d.corregir_nombres()
        self.assertEqual(d.propuestas.pendientes(), 0)
        nombres = [f.nombre for f in d.propuestas.filas]
        self.assertIn('Pos at limit lids 2', nombres)
        self.assertEqual(len(nombres), len(set(nombres)))
        for tabla, filas in d.tablas:
            for row, f in enumerate(filas):
                self.assertIsNone(e.motivo_variable_nueva(f.nombre))
                self.assertEqual(tabla.item(row, 2).foreground().color(), QColor(estilo.OK))
        tabla, filas = d.tablas[0]
        tabla.item(0, 2).setText('Otro nombre')
        self.assertEqual(filas[0].nombre, 'Otro nombre')

    def test_SZ3_detalle_en_ayuda_celda_naranja(self):
        """REQ-EDT-09: el motivo y la regla completos siguen disponibles en la celda cuando se escribe un nombre inválido."""
        d = self.dialogo()
        tabla, filas = d.tablas[0]
        for row, n in enumerate(NOMBRES):
            tabla.item(row, 2).setText(n)
        for row, f in enumerate(filas):
            self.assertEqual(tabla.item(row, 2).toolTip(), f.motivo)
            self.assertIn('nombre de variable', f.motivo)
            self.assertEqual(tabla.item(row, 2).background().color(), QColor(estilo.NOMBRE_PENDIENTE_FONDO))

    def test_SZ4_orden_y_categoria_inicial(self):
        """REQ-EDT-02: ambos programadores siguen el mismo orden relativo."""
        from escritorio.bloques import Programador
        for valor, claves, botones in (
            (False, ['operador', 'tiempo', 'comparacion', 'constante'], ['( … )', 'Temporizador', '= ≠ < ≥', '1', '0']),
            (True, ['aritm', 'numero'], ['( … )', '+ Constante']),
        ):
            p = Programador(lambda: ({}, []), valor=valor)
            self.addCleanup(p.deleteLater)
            self.assertEqual(list(p.categorias), claves)
            self.assertEqual(p.banda.l_prefijo.text(), 'Insertar:')
            self.assertEqual([b.text() for bs in p.banda.botones.values() for b in bs], botones)
            self.assertEqual(p.paleta.clave, "vnum" if valor else "variables")

    def test_SZ5_ejemplos_solo_como_archivos_sin_firma(self):
        """REQ-EDT-10: se instalan una vez y abren como cualquier otro proyecto."""
        import tempfile
        from escritorio.ejemplos_archivos import instalar_ejemplos, nombres_ejemplos
        from grafcet.contenedor import sello_valido
        from escritorio import sello

        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        menus = [a.menu() for a in c.w.menuBar().actions()]
        self.assertFalse(any("Ejemplos" in a.text() for menu in menus for a in menu.actions()))
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta)
            archivos = instalar_ejemplos(destino, c.w.ajustes)
            self.assertEqual(len(archivos), 23)
            self.assertEqual(set(p.name for p in archivos), set(nombres_ejemplos().values()))
            self.assertTrue(all(p.parent == destino / "Ejemplos" for p in archivos))
            self.assertTrue(all(not sello_valido(p.read_bytes(), sello.CLAVE) for p in archivos))
            with patch("escritorio.ventana.QMessageBox.information"):
                self.assertTrue(c.w.abrir_ruta(destino / "Ejemplos" / "Ejemplo - Marcha y paro.grafnet"))
            self.assertFalse(c.w.solo_lectura)
            self.assertFalse(c.w.edicion.puede_firmarse)
            self.assertEqual(c.w.l_firma.text(), "Archivo sin firma")
            archivos[0].write_bytes(b"editado")
            archivos[1].unlink()
            self.assertEqual(instalar_ejemplos(destino, c.w.ajustes), [])
            self.assertEqual(archivos[0].read_bytes(), b"editado")
            self.assertFalse(archivos[1].exists())
            from escritorio import ejemplos_archivos
            datos = dict(ejemplos_archivos.EJEMPLOS)
            datos["ejemplo-nuevo"] = ("Ejemplo nuevo de prueba", *datos["aula_marcha"][1:])
            with patch.object(ejemplos_archivos, "EJEMPLOS", datos):
                nuevos = instalar_ejemplos(destino, c.w.ajustes)
                self.assertEqual([p.name for p in nuevos], ["Ejemplo - Ejemplo nuevo de prueba.grafnet"])
            self.assertEqual(archivos[0].read_bytes(), b"editado")
            self.assertFalse(archivos[1].exists())

    def test_SZ6_corregir_reservados_vacios_largos_y_signos(self):
        """REQ-EDT-02: la propuesta usa las reglas existentes también en casos límite."""
        e = self.edicion()
        p = Propuestas(e, Configuracion(), [senal(str(i), n) for i, n in enumerate(
            ['AND', '123', 'X1', 'inicio Xmotor', '///', 'abc. def', 'a' * 270, 'A / B', 'A / B'])])
        for fila in p.filas:
            fila.marcada = True
        corregir_nombres(p)
        self.assertFalse(p.pendientes())
        self.assertEqual(len({f.nombre for f in p.filas}), len(p.filas))
        for f in p.filas:
            self.assertIsNone(e.motivo_variable_nueva(f.nombre))

    def test_SZ7_edicion_manual_y_deshacer_en_celda(self):
        """REQ-EDT-02: la corrección no impide escribir y deshacer en el editor de celda."""
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtTest import QTest
        d = self.dialogo()
        d.show()
        d.corregir_nombres()
        tabla, filas = d.tablas[0]
        item = tabla.item(0, 2)
        tabla.editItem(item)
        editor = tabla.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        original = editor.text()
        editor.selectAll()
        QTest.keyClicks(editor, 'Nombre manual')
        QTest.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(editor.text(), original)

    def test_SZ8_categorias_en_todas_las_propiedades(self):
        """REQ-EDT-02: las ventanas reales utilizan el orden común sin perder sus controles."""
        from escritorio.bloques import Programador
        for tipo in ('transicion', 'condicionada', 'evento', 'activacion', 'desactivacion',
                     'activacion_numerica', 'evento_numerico'):
            with self.subTest(tipo=tipo):
                c = HC.Contexto(1366, 768)
                try:
                    HC._flotante(tipo)(c)
                    self.assertTrue(c.w.flot.principal.isVisible())
                    for prog in c.w.flot.panel.findChildren(Programador):
                        if prog.valor:
                            self.assertEqual(list(prog.categorias), ['aritm', 'numero'])
                            self.assertEqual([b.text() for bs in prog.banda.botones.values() for b in bs],
                                             ['( … )', '+ Constante'])
                            prefijo = prog.banda.l_prefijo.text()
                            self.assertTrue(prefijo == 'Insertar:' or prefijo.endswith(':='), prefijo)
                        else:
                            self.assertEqual(list(prog.categorias), ['operador', 'tiempo', 'comparacion', 'constante'])
                            self.assertEqual([b.text() for bs in prog.banda.botones.values() for b in bs],
                                             ['( … )', 'Temporizador', '= ≠ < ≥', '1', '0'])
                            self.assertEqual(prog.banda.l_prefijo.text(), 'Insertar:')
                finally:
                    c.cerrar()

    def test_SZ9_zoom_natural_con_y_sin_aviso(self):
        """REQ-UX-01: el zoom conserva el ancho de la 1.1.5 y su alineación derecha."""
        referencia = {"1366": 435, "1920": 445}  # Medidas de la 1.1.5; evidencia en zoom_115.json.
        for ancho, alto in ((1366, 768), (1920, 1080)):
            c = HC.Contexto(ancho, alto)
            try:
                c.mostrar()
                HC._bombear(20)
                barra = c.w.diagrama.barra
                antes = barra.geometry()
                self.assertLessEqual(abs(barra.width() - referencia[str(ancho)]), 2)
                c.e.rechazar(MSG_SIN_DESTINO)
                c.e.cambiado.emit()
                HC._bombear(20)
                self.assertLessEqual(abs(barra.width() - antes.width()), 2)
                self.assertLessEqual(abs(barra.geometry().right() - antes.right()), 2)
            finally:
                c.cerrar()

    def test_SZ10_traza_y_flecha_dentro_de_su_cabecera(self):
        """REQ-SIM-03, REQ-UX-01: se conserva la traza y su flecha no pisa la lista."""
        from PySide6.QtCore import QPoint
        for ancho, alto in ((1366, 768), (1920, 1080), (960, 1032)):
            c = HC.Contexto(ancho, alto)
            try:
                HC._simulacion(c)
                c.w._mostrar_panel('inferior', True)
                HC._bombear(15)
                self.assertTrue(c.w.traza.isVisible())
                self.assertGreater(c.w.traza.count(), 0)
                cierre = c.w.flechas['inferior']
                caja = c.w.inferior.widget(0)
                posicion = cierre.mapToGlobal(QPoint(0, 0)) - caja.mapToGlobal(QPoint(0, 0))
                cuerpo = c.w.traza.mapTo(caja, QPoint(0, 0))
                self.assertGreaterEqual(posicion.y(), 0)
                self.assertLessEqual(posicion.y() + cierre.height(), cuerpo.y())
                self.assertLessEqual(posicion.x() + cierre.width(), caja.width())
                cierre.click()
                HC._bombear(5)
                self.assertFalse(c.w.traza.isVisible())
            finally:
                c.cerrar()

    def test_SZ11_sin_entrada_panel_inferior_y_con_separadores(self):
        """REQ-UX-01: Ver no ofrece el inferior y las cuatro separaciones se ven."""
        for ancho, alto in ((1366, 768), (960, 1032)):
            c = HC.Contexto(ancho, alto)
            try:
                c.mostrar()
                HC._bombear(15)
                ver = next(a.menu() for a in c.w.menuBar().actions() if a.text().replace('&', '') == 'Ver')
                self.assertNotIn(c.w.a_inferior, ver.actions())
                self.assertEqual(c.w.a_inferior.shortcut().toString(), 'Ctrl+J')
                from escritorio.separadores_barra import SeparadorBarra
                externos = c.w.herramientas_grafcet.findChildren(SeparadorBarra)
                self.assertEqual(len(externos), 1)
                internos = [barra.widgetForAction(a) for barra in (c.w.tb_sim, c.w.tb_edit)
                            for a in barra.actions() if a.isSeparator()]
                self.assertEqual(len(internos), 2)
                self.assertIs(c.w.diagrama.b_dependencias.parent(), c.w.tb_vista_der)
                self.assertIs(c.w.b_errores.parent(), c.w.tb_vista_der)
                for separador in [*internos, *externos]:
                    self.assertTrue(separador.isVisible())
                    im = separador.grab().toImage()
                    color = im.pixelColor(im.width() // 2, im.height() // 2)
                    self.assertEqual(color, QColor(estilo.BORDE))
            finally:
                c.cerrar()

    def test_SZ12_todas_las_nuevas_marcadas_y_casillas_enteras(self):
        """REQ-EDT-07, REQ-UX-01: nombres originales marcados y casillas dentro de cada fila."""
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtWidgets import QStyle, QStyleOptionButton
        anterior = estilo.ESCALA
        try:
            for escala in ('normal', 'grande'):
                estilo.activar_escala(escala)
                d = self.dialogo(['Remover 2', 'Emergency Stop 0', 'Marcha', 'Auto'])
                d.show()
                HC._bombear(10)
                self.assertTrue(all(f.marcada for f in d.propuestas.filas))
                for tabla, filas in d.tablas:
                    for fila, datos in enumerate(filas):
                        tabla.scrollToItem(tabla.item(fila, 0))
                        HC._bombear(4)
                        caja = tabla.cellWidget(fila, 0)
                        self.assertTrue(caja.isChecked())
                        casilla = caja.casilla
                        opcion = QStyleOptionButton()
                        casilla.initStyleOption(opcion)
                        indicador = casilla.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator,
                                                                 opcion, casilla)
                        self.assertTrue(casilla.rect().contains(indicador))
                        self.assertTrue(caja.rect().contains(casilla.geometry()))
                        rect = tabla.visualItemRect(tabla.item(fila, 0))
                        punto = casilla.mapToGlobal(QPoint()) - tabla.viewport().mapToGlobal(QPoint())
                        self.assertTrue(rect.contains(QRect(punto, casilla.size())))
                tabla, filas = d.tablas[0]
                tabla.cellWidget(0, 0).setChecked(False)
                self.assertFalse(filas[0].marcada)
                d.reject()
        finally:
            estilo.activar_escala(anterior)

    def test_SZ13_panel_cerrado_no_reconstruye_controles(self):
        """REQ-UX-01: el panel oculto se prepara al consultarlo, no con cada colocación."""
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        c.w.nuevo()
        panel = c.w.flot.panel
        with patch.object(panel, 'mostrar', wraps=panel.mostrar) as mostrar:
            for i in range(30):
                c.w.edicion.colocar('etapa', QPointF(200 + 140 * (i % 9), 150 + 120 * (i // 9)))
            self.assertEqual(mostrar.call_count, 0)
            self.assertIs(c.w.props, panel)
            self.assertEqual(mostrar.call_count, 1)
            self.assertIs(c.w.props, panel)
            self.assertEqual(mostrar.call_count, 1)
            c.w._abrir_opciones()
            HC._bombear(10)
            self.assertTrue(c.w.flot.principal.isVisible())
            self.assertTrue(panel.isVisible())

    def test_SZ14_propiedades_confirma_y_cancela_sesion(self):
        """REQ-UX-01: Esc revierte dos cambios e Intro guarda el campo enfocado."""
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        HC._edicion(c)
        tid = c.ids["transiciones"][0]
        c.e.seleccionar([tid])
        c.w._abrir_opciones()
        HC._bombear(10)
        anterior = (c.e.ed.model, c.e.ed.presentation, len(c.e.ed.undo_stack))
        self.assertIsNone(c.e.renombrar(tid, "prueba"))
        c.e.poner_comentario(tid, "Texto provisional")
        QTest.keyClick(c.w.flot.principal, Qt.Key.Key_Escape)
        HC._bombear(10)
        self.assertFalse(c.w._props_abiertas())
        self.assertEqual((c.e.ed.model, c.e.ed.presentation, len(c.e.ed.undo_stack)), anterior)
        c.e.seleccionar([tid])
        c.w._abrir_opciones()
        HC._bombear(10)
        campo = c.w.props.t_comentario
        campo.setFocus()
        campo.selectAll()
        QTest.keyClicks(campo, "Comentario confirmado")
        QTest.keyClick(campo, Qt.Key.Key_Return)
        HC._bombear(10)
        self.assertFalse(c.w._props_abiertas())
        self.assertEqual(c.e.ed.comments()[tid], "Comentario confirmado")
        c.e.seleccionar([tid])
        c.w._abrir_opciones()
        HC._bombear(10)
        campo = c.w.props.t_comentario
        campo.setFocus()
        campo.selectAll()
        QTest.keyClicks(campo, "Comentario al hacer clic fuera")
        fuera = QPoint(3, 3)
        viewport = c.w.diagrama.viewport()
        self.assertFalse(c.w.flot.principal.frameGeometry().contains(viewport.mapToGlobal(fuera)))
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=fuera)
        HC._bombear(10)
        self.assertFalse(c.w._props_abiertas())
        self.assertEqual(c.e.ed.comments()[tid], "Comentario al hacer clic fuera")
        c.e.deshacer()
        self.assertEqual(c.e.ed.comments()[tid], "Comentario confirmado")


    def test_SZ15_portapapeles_entre_formuladores(self):
        """REQ-EDT-13: Ctrl+C y Ctrl+V trasladan una fórmula entre dos editores."""
        from PySide6.QtTest import QTest
        from escritorio.bloques import AreaBloques, texto_a_arbol
        fuente = lambda: ({"marcha": ("input", "bool")}, [])
        origen = AreaBloques(fuente)
        destino = AreaBloques(fuente)
        self.addCleanup(origen.close)
        self.addCleanup(destino.close)
        self.addCleanup(self.app.clipboard().clear)
        origen.poner_arbol(texto_a_arbol("NOT marcha", *fuente()))
        QTest.keyClick(origen, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(destino, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(destino.texto(), origen.texto())
        self.assertTrue(destino.texto())

    def test_SZ16_ver_comparte_dependencias_y_errores(self):
        """REQ-UX-01: los dos controles de Ver reflejan la barra y la preferencia."""
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        c.mostrar()
        c.w._sincronizar_menu_dibujo()
        self.assertTrue(c.w.a_ver_dependencias.isChecked())
        self.assertFalse(c.w.a_ver_errores.isChecked())
        c.w.a_ver_dependencias.trigger()
        self.assertFalse(c.w.diagrama.b_dependencias.isChecked())
        c.w.a_ver_errores.trigger()
        self.assertTrue(c.w.b_errores.isChecked())

    def test_SZ17_rama_a_la_misma_distancia(self):
        """REQ-EDT-02: alargar el gesto no cambia la distancia al crear la siguiente ficha."""
        from escritorio.diagrama import anclas, posiciones
        from escritorio.edicion import DY
        for recorrido in (100, 220):
            e = self.edicion()
            sid = e.poner_etapa(QPointF(200, 220))
            punto = next(a for a in anclas(e.M, sid) if a["lado"] == "abajo")
            tid = e.crear_desde(punto, punto["pos"] + QPointF(0, recorrido))
            siguiente = next(a for a in anclas(e.M, tid) if a["lado"] == "abajo")
            eid = e.crear_desde(siguiente, siguiente["pos"] + QPointF(0, recorrido))
            pos = posiciones(e.M)
            self.assertEqual(pos[tid][1] - pos[sid][1], DY)
            self.assertEqual(pos[eid][1] - pos[tid][1], DY)

    def test_SZmas1_aviso_caduca_con_operaciones(self):
        """REQ-EDT-09: borrar, deshacer y crear destinos quitan el aviso anterior."""
        for operacion in ('borrar', 'deshacer', 'parcial', 'macroetapa', 'recinto'):
            with self.subTest(operacion=operacion):
                e = self.edicion()
                if operacion == 'recinto':
                    e.colocar('encapsulante', QPointF(800, 600))
                    sid = e.sel[0]
                e.colocar('forzado', QPointF(200, 200))
                e.configurar_orden(e.sel[0])
                self.assertEqual(e.mensaje, MSG_SIN_DESTINO)
                if operacion == 'borrar':
                    e.borrar()
                elif operacion == 'deshacer':
                    e.deshacer()
                elif operacion == 'recinto':
                    with patch.object(e, 'pedir_texto', return_value='Recinto'):
                        e.anadir_recinto(sid)
                else:
                    e.colocar(operacion, QPointF(700, 200))
                self.assertNotEqual(e.mensaje, MSG_SIN_DESTINO)

    def test_SZmas3_nuevo_proyecto_y_otro_aviso(self):
        """REQ-EDT-09: Nuevo no hereda avisos y los otros rechazos caducan igual."""
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        c.w.nuevo()
        e = c.w.edicion
        e.colocar('forzado', QPointF(200, 200))
        e.configurar_orden(e.sel[0])
        self.assertEqual(e.mensaje, MSG_SIN_DESTINO)
        with patch.object(c.w, '_salir_de_edicion', return_value=True):
            c.w.nuevo()
        self.assertNotEqual(c.w.edicion.mensaje, MSG_SIN_DESTINO)
        e = c.w.edicion
        e.rechazar('Aviso anterior')
        e.colocar('etapa', QPointF(200, 200))
        self.assertNotEqual(e.mensaje, 'Aviso anterior')

    def test_SZmas4_franja_seleccion_nombre_borrado_y_estado(self):
        """REQ-EDT-09: franja y estado siguen la selección y los nombres vivos."""
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        c.w.nuevo()
        e = c.w.edicion
        pid = e.poner_parcial(QPointF(600, 300))
        c.w._ayuda_abierta = True
        c.w._ajustar_cabecera()
        self.assertIn('G1', c.w.ayuda_larga.text())
        e.renombrar(pid, 'G2')
        self.assertIn('G2', c.w.ayuda.text())
        self.assertNotIn('G1', c.w.ayuda.text())
        self.assertEqual(c.w.statusBar().currentMessage(), c.w.ayuda.text())
        self.assertIn('G2', c.w.ayuda_larga.text())
        sid = e.poner_etapa(QPointF(900, 500))
        e.seleccionar([sid])
        self.assertNotIn('Grafcet parcial', c.w.ayuda.text())
        e.seleccionar([pid])
        self.assertIn('G2', c.w.ayuda.text())
        e.borrar()
        e.seleccionar([])
        self.assertEqual(c.w.ayuda.text(), '')
        self.assertFalse(c.w.ayuda_larga.isVisible())
        self.assertFalse(c.w.ayuda.isVisible())
        self.assertEqual(c.w.statusBar().currentMessage(), '')

    def test_SZmas5_recuento_ayuda_por_cambio_y_seleccion(self):
        """REQ-EDT-09: el texto de ayuda no se calcula por movimiento del ratón."""
        import escritorio.vigencia_avisos as avisos
        c = HC.Contexto(1366, 768)
        self.addCleanup(c.cerrar)
        c.w.nuevo()
        e = c.w.edicion
        sid = e.poner_etapa(QPointF(200, 200))
        e.seleccionar([sid])
        e.prensar(QPointF(200, 200))
        cambios = []
        e.cambiado.connect(lambda: cambios.append(1))
        with patch.object(avisos, 'texto_estado', wraps=avisos.texto_estado) as decidir:
            t = time.monotonic()
            while time.monotonic() - t < 2:
                e.mover(QPointF(300, 300))
            self.assertEqual(decidir.call_count, 0)
            e.soltar(QPointF(300, 300))
            decidir.reset_mock()
            cambios.clear()
            for i in range(30):
                e.colocar('etapa', QPointF(200 + 140 * (i % 9), 150 + 120 * (i // 9)))
            self.assertLessEqual(decidir.call_count, len(cambios))
            antes = decidir.call_count
            e.seleccionar([])
            self.assertLessEqual(decidir.call_count - antes, 1)

    def test_SZmas2_movimiento_no_recalcula(self):
        """REQ-EDT-09: mover no decide avisos; cada soltar los decide como máximo una vez."""
        e = self.edicion()
        e.colocar('etapa', QPointF(200, 200))
        e.prensar(QPointF(200, 200))
        self.assertIsNotNone(e.arrastre)
        cambios = []
        e.cambiado.connect(lambda: cambios.append(1))
        with patch.object(e.vigencia_aviso, 'cambio', wraps=e.vigencia_aviso.cambio) as cambio:
            t = time.monotonic()
            while time.monotonic() - t < 2:
                e.mover(QPointF(300, 300))
            self.assertEqual(cambio.call_count, 0)
            e.soltar(QPointF(300, 300))
            cambio.reset_mock()
            cambios.clear()
            for i in range(30):
                antes = cambio.call_count
                senales = len(cambios)
                e.colocar('etapa', QPointF(200 + 140 * (i % 9), 150 + 120 * (i // 9)))
                self.assertLessEqual(cambio.call_count - antes, len(cambios) - senales)


if __name__ == '__main__':
    unittest.main()
