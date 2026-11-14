"""SG1: remates de interfaz 1.1.1; ejecutable suelto con la raíz del repositorio en sys.path."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap, QRegion
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QGraphicsScene, QLabel, QToolButton
    QT = True
except ImportError:
    QT = False

if QT:
    from test_editor_cadenas import BaseQt
    from escritorio import carpetas, estilo, leyenda
    from escritorio.favoritos import LADO_MINI, PREDETERMINADOS, icono_mini
    from escritorio.planos_controles import AVISO_NO_CABE
    from grafcet.laminas import ajustes_lamina
    from grafcet.plantillas_tecnicas import plantilla_tecnica
else:
    BaseQt = unittest.TestCase


@unittest.skipUnless(QT, "requiere PySide6")
class Interfaz111(BaseQt):
    def setUp(self):
        super().setUp()
        self.documentos = tempfile.TemporaryDirectory()
        self.addCleanup(self.documentos.cleanup)
        self.rutas = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation",
                                return_value=self.documentos.name)
        self.rutas.start()
        self.addCleanup(self.rutas.stop)

    def ventana(self, ancho=1366, alto=768):
        w, e = self.vacio()
        w.resize(ancho, alto)
        w.show()
        self.pasar_arranque(w)
        self.asentar_escala(w)
        self.bombear()
        return w, e

    def bombear(self):
        for _ in range(8):
            QApplication.processEvents()

    def plano(self, cfg=None):
        w, e = self.ventana()
        sid = e.poner_etapa(QPointF(100, 60))
        hoja = e.ed.add_plan_page(None, cfg or ajustes_lamina({"plantilla": carpetas.predeterminada()}))
        e.cambia()
        w.mostrar_hoja(hoja)
        self.bombear()
        return w, e, w.panel_planos, hoja, sid

    def test_SG101_favoritos_24_caja_comun_trazo_y_tres_dpr(self):
        """REQ-EDT-02: iconos propios de 24, sin subir la fila, y render nativo en las tres escalas."""
        w, e = self.ventana()
        self.assertEqual(LADO_MINI, 24)
        alto = w.favoritos.height()
        for clave in PREDETERMINADOS:
            boton = w.favoritos.botones[clave]
            self.assertEqual(boton.iconSize(), QSize(w.favoritos.lado_icono, w.favoritos.lado_icono))
            for dpr in (1., 1.25, 1.5):
                pixmap = icono_mini(clave).pixmap(QSize(24, 24), dpr)
                self.assertEqual(pixmap.size(), QSize(round(24 * dpr), round(24 * dpr)))
                self.assertEqual(pixmap.devicePixelRatioF(), dpr)
                limites = QRegion(pixmap.mask()).boundingRect()
                self.assertTrue(pixmap.rect().adjusted(1, 1, -1, -1).contains(limites), clave)
        self.assertGreaterEqual(alto, 24)
        alto_cabecera = w._cab.geometry().height()
        for boton in w.favoritos.botones.values():
            boton.setIconSize(QSize(20, 20))
        w._ajustar_cabecera()
        self.bombear()
        self.assertEqual((w.favoritos.height(), w._cab.geometry().height()), (alto, alto_cabecera))
        for boton in w.favoritos.botones.values():
            boton.setIconSize(QSize(w.favoritos.lado_icono, w.favoritos.lado_icono))
        self.assertEqual(alto, w.favoritos.botones["etapa"].height())

    def test_SG102_luz_completa_en_estados_y_dpr(self):
        """REQ-SIM-03: círculo o rombo completo dentro de la pastilla, también abierta y a distintos DPR."""
        w, e = self.ventana()
        for estado in ("desconectado", "conectado", "error"):
            for abierta in (False, True):
                w._luz_es(estado, "Estado de prueba")
                estilo.poner(w.luz_es, abierta=abierta)
                self.bombear()
                clave = {"desconectado": "desconectada", "conectado": "conectada", "error": "error"}[estado]
                color = QColor(estilo.LUZ[clave])
                b = w.luz_es
                for dpr in (1., 1.25, 1.5):
                    pix = QPixmap(round(b.width() * dpr), round(b.height() * dpr))
                    pix.setDevicePixelRatio(dpr)
                    pix.fill(Qt.GlobalColor.transparent)
                    pintor = QPainter(pix)
                    b.render(pintor, QPoint())
                    pintor.end()
                    imagen = pix.toImage()
                    puntos = []
                    for x in range(round(estilo.E2 * dpr), round(b.width() * dpr / 2)):
                        for y in range(round(5 * dpr), round((b.height() - 5) * dpr)):
                            if sum(abs(a - b) for a, b in zip(imagen.pixelColor(x, y).getRgb()[:3],
                                                            color.getRgb()[:3])) < 70:
                                puntos.append((x, y))
                    self.assertTrue(puntos, (estado, abierta, dpr))
                    izquierda = min(x for x, y in puntos)
                    puntos = [(x, y) for x, y in puntos if x <= izquierda + 14 * dpr]
                    ancho = max(x for x, y in puntos) - min(x for x, y in puntos) + 1
                    alto = max(y for x, y in puntos) - min(y for x, y in puntos) + 1
                    self.assertLessEqual(abs(ancho - alto), 2 * dpr, (estado, abierta, dpr, ancho, alto))
                    self.assertGreaterEqual(ancho, 9 * dpr)

    def test_SG103_dependencias_dentro_de_caja(self):
        """REQ-EDT-09: el dibujo no toca los límites de su icono en reposo ni marcado."""
        w, e = self.ventana()
        for dpr in (1., 1.25, 1.5):
            pix = estilo.icono("dependencias").pixmap(QSize(24, 24), dpr)
            limites = QRegion(pix.mask()).boundingRect()
            self.assertTrue(pix.rect().adjusted(1, 1, -1, -1).contains(limites))
        for marcado in (False, True):
            w.diagrama.b_dependencias.setChecked(marcado)
            self.assertFalse(w.diagrama.b_dependencias.grab().isNull())

    def test_SG104_cabecera_es_una_fila_y_margenes_iguales(self):
        """REQ-SIM-03: estado solo en la pastilla; cabecera de una fila y margen M4 simétrico."""
        w, e = self.ventana()
        w.mostrar_es()
        self.bombear()
        p = w.panel_es
        for estado in ("desconectado", "conectado", "error"):
            p.mostrar_estado(estado, "Mensaje completo de conexión")
            self.bombear()
            self.assertFalse(p.estado.isVisible())
            self.assertFalse(p.check.isVisible())
            self.assertLessEqual(p.cabecera.height(), p.fila_alta.height() + 2)
            m = p.fila_alta.layout().contentsMargins()
            self.assertEqual((m.left(), m.right()), (estilo.E2, estilo.E2))
            margen_derecho = p.fila_alta.width() - p.b_configuracion.geometry().right() - 1
            self.assertLessEqual(abs(p.b_volver.x() - margen_derecho), 1)

    def test_SG105_carpeta_planos_sin_tocar_laminas(self):
        """REQ-DAT-01: nueva carpeta Planos y carpeta Láminas anterior intacta."""
        antigua = Path(self.documentos.name) / "GRAFCET Connect" / "Láminas"
        antigua.mkdir(parents=True)
        archivo = antigua / "anterior.pdf"
        archivo.write_bytes(b"contenido anterior")
        rutas = carpetas.asegurar_carpetas()
        self.assertEqual(rutas["laminas"].name, "Planos")
        self.assertTrue(rutas["laminas"].is_dir())
        self.assertEqual(archivo.read_bytes(), b"contenido anterior")
        self.assertEqual(list(antigua.iterdir()), [archivo])

    def test_SG106_traer_no_cabe_aviso_y_hoja_intacta(self):
        """REQ-EDT-11: aviso con instrucciones, sin reducir el dibujo ni cambiar la hoja."""
        w, e, p, hoja, a = self.plano()
        b = e.poner_etapa(QPointF(100, 5000))
        e.seleccionar([a, b])
        antes = copy.deepcopy(e.ed.sheet_links())
        w.destino_traer = (e, hoja)
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.confirmar_traer()
        self.assertEqual(aviso.call_args.args[2], AVISO_NO_CABE)
        self.assertEqual(e.ed.sheet_links(), antes)

    def test_SG114_enviar_a_hoja_nueva_no_crea_hoja_si_no_cabe(self):
        """REQ-EDT-11: la segunda ruta de entrada también rechaza antes de crear la hoja."""
        w, e = self.ventana()
        a = e.poner_etapa(QPointF(100, 60))
        b = e.poner_etapa(QPointF(100, 5000))
        e.seleccionar([a, b])
        antes = copy.deepcopy(e.ed.sheet_links())
        with mock.patch("escritorio.hojas.CrearHoja.exec", return_value=1), \
                mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.enviar_seleccion_lamina()
        self.assertEqual(aviso.call_args.args[2], AVISO_NO_CABE)
        self.assertEqual(e.ed.sheet_links(), antes)

    def test_SG107_barra_tres_grupos_una_fila_y_navegacion_por_miniaturas(self):
        """REQ-EDT-11: contenido/salida/vista, sin distintivo ni navegación inferior duplicados."""
        w, e, p, hoja, a = self.plano()
        otra = e.ed.add_plan_page(None, ajustes_lamina())
        p.mostrar(hoja)
        for ancho, alto in ((1366, 768), (2000, 1250)):
            w.resize(ancho, alto)
            self.asentar_escala(w)
            self.bombear()
            acciones = p.barra.actions()
            visibles = [a for a in acciones if a.isVisible()]
            self.assertEqual(sum(a.isSeparator() for a in visibles), 2)
            self.assertFalse(visibles[0].isSeparator() or visibles[-1].isSeparator())
            for accion in visibles:
                boton = p.barra.widgetForAction(accion)
                self.assertTrue(p.barra.rect().contains(boton.geometry()), accion.text())
            for campo in (p.editor.predeterminadas, p.editor.b_opciones_plantilla,
                          p.editor.formato, p.editor.orientacion, p.editor.margen):
                scroll = p.editor.propiedades.widget(0)
                posicion = campo.mapTo(scroll.viewport(), QPoint())
                self.assertTrue(scroll.viewport().rect().contains(QRect(posicion, campo.size())),
                                (ancho, campo.objectName(), posicion, campo.size()))
            self.assertIsNone(p.editor.navegacion_fila)
            self.assertFalse(p.editor.anterior.isVisible() or p.editor.siguiente.isVisible())
            self.assertFalse(any("EDICIÓN DE PLANO" in l.text() for l in p.findChildren(QLabel)))
            self.assertFalse(any("plantilla" in a.text().lower() for a in acciones))
        destino = p.lista.item(1)
        QTest.mouseClick(p.lista.viewport(), Qt.MouseButton.LeftButton, pos=p.lista.visualItemRect(destino).center())
        self.assertEqual(p.hoja_id, otra)
        self.assertIn("Hoja", p.titulo.text())

    def test_SG108_plantillas_filtradas_y_guardada_contradictoria(self):
        """REQ-EDT-11: manda la plantilla guardada y los cambios de formato/orientación eligen su predeterminada."""
        cfg = ajustes_lamina({"formato": "A3", "orientacion": "horizontal", "plantilla": plantilla_tecnica(210, 297)})
        w, e, p, hoja, a = self.plano(cfg)
        d = p.editor
        self.assertEqual((d.formato.currentText(), d.orientacion.currentData()), ("A4", "vertical"))
        p.aplicar()
        guardada = next(h for h in e.ed.sheet_links() if h["id"] == hoja)["ajustes"]
        self.assertEqual((guardada["formato"], guardada["orientacion"]), ("A4", "vertical"))
        for formato, orientacion in (("A3", "horizontal"), ("A4", "horizontal"), ("A4", "vertical")):
            d.formato.setCurrentText(formato)
            d.orientacion.setCurrentIndex(d.orientacion.findData(orientacion))
            self.bombear()
            self.assertEqual(d.predeterminadas.count(), 1)
            self.assertEqual(d.predeterminadas.currentData(), (formato, orientacion))
            ancho, alto = {"A4": (210, 297), "A3": (297, 420)}[formato]
            if orientacion == "horizontal":
                ancho, alto = alto, ancho
            self.assertEqual(d.plantilla["size"], [ancho, alto])

    def test_SG109_menu_plantilla_cuatro_ordenes_operativas(self):
        """REQ-EDT-11: importar, estándar, editar y quitar desde el panel derecho."""
        w, e, p, hoja, a = self.plano()
        d = p.editor
        self.assertEqual(d.b_opciones_plantilla.menu().actions(),
                         [d.a_importar, d.a_estandar, d.a_editar_plantilla, d.a_quitar_plantilla])
        ruta = Path(self.documentos.name) / "personalizada.json"
        carpetas.guardar_plantilla(ruta, plantilla_tecnica(420, 297))
        with mock.patch("escritorio.laminas.QFileDialog.getOpenFileName", return_value=(str(ruta), "")):
            d.a_importar.trigger()
        self.assertEqual((d.formato.currentText(), d.orientacion.currentData()), ("A3", "horizontal"))
        d.a_editar_plantilla.trigger()
        self.assertTrue(d.editando_plantilla)
        d.a_editar_plantilla.trigger()
        self.assertFalse(d.editando_plantilla)
        d.a_estandar.trigger()
        self.assertEqual(d.plantilla["source"], "GrafConnect")
        d.a_quitar_plantilla.trigger()
        self.assertEqual(d.plantilla["primitives"], [])

    def test_SG110_cuarto_pantalla_sin_colision_ni_desborde_fuera(self):
        """REQ-EDT-09: sin modo solapado y extensión de herramientas dentro de su barra, separada de E/S."""
        for ancho, alto in ((683, 384), (960, 540)):
            w, e = self.ventana(ancho, alto)
            self.assertTrue(w.fila_pestanas.property("fusion"))
            self.assertFalse(w.estado.isVisible())
            self.assertLessEqual(w.herramientas_grafcet.geometry().right() + estilo.E2, w.luz_es.x())
            for barra in (w.tb_sim, w.tb_edit):
                acciones = [a for a in barra.actions() if a.isVisible()
                            and barra.widgetForAction(a).isVisible()]
                if acciones:
                    self.assertFalse(acciones[0].isSeparator() or acciones[-1].isSeparator())
                extension = barra.findChild(QToolButton, "qt_toolbar_ext_button")
                if extension.isVisible():
                    self.assertTrue(barra.rect().contains(extension.geometry()),
                                    (ancho, barra.objectName(), barra.size(), extension.geometry()))

    def test_SG113_biblioteca_filtrada_y_plantilla_personalizada_conservada(self):
        """REQ-EDT-11: las plantillas propias se filtran sin alterar las que ya contiene el proyecto."""
        rutas = carpetas.asegurar_carpetas()
        propia = plantilla_tecnica(210, 297)
        propia["source"] = "Propia"
        propia["primitives"].append({"kind": "text", "text": "Mi plantilla", "x": 20, "y": 20,
                                    "height": 3, "font": "Arial"})
        carpetas.guardar_plantilla(rutas["plantillas"] / "propia_a4.json", propia)
        carpetas.guardar_plantilla(rutas["plantillas"] / "otra_a3.json", plantilla_tecnica(420, 297))
        w, e, p, hoja, a = self.plano(ajustes_lamina({"plantilla": propia}))
        d = p.editor
        self.assertEqual(d.predeterminadas.count(), 3)
        self.assertIn("Mi plantilla", [t.get("text") for t in d.plantilla["primitives"]])
        d.formato.setCurrentText("A3")
        d.orientacion.setCurrentIndex(d.orientacion.findData("horizontal"))
        self.bombear()
        self.assertEqual(d.predeterminadas.count(), 2)
        self.assertTrue(any("otra_a3" in d.predeterminadas.itemText(i) for i in range(2)))
        d.formato.setCurrentText("A4")
        d.orientacion.setCurrentIndex(d.orientacion.findData("vertical"))
        self.bombear()
        indice = next(i for i in range(d.predeterminadas.count()) if "propia_a4" in d.predeterminadas.itemText(i))
        d.predeterminadas.setCurrentIndex(indice)
        self.assertIn("Mi plantilla", [t.get("text") for t in d.plantilla["primitives"]])

    def test_SG115_personalizado_orientacion_fija_hasta_elegir_iso(self):
        """REQ-EDT-11: una plantilla no ISO conserva su orientación hasta elegir formato ISO."""
        plantilla = plantilla_tecnica(230, 310)
        plantilla["source"] = "Personalizada"
        w, e, p, hoja, a = self.plano(ajustes_lamina({"plantilla": plantilla}))
        d = p.editor
        self.assertEqual(d.formato.currentText(), "Personalizado")
        self.assertEqual(d.orientacion.currentData(), "vertical")
        self.assertFalse(d.orientacion.isEnabled())
        self.assertTrue(d.formato.isEnabled())
        self.assertEqual(d.plantilla["size"], [230, 310])
        d.formato.setCurrentText("A3")
        self.bombear()
        self.assertTrue(d.orientacion.isEnabled())
        d.orientacion.setCurrentIndex(d.orientacion.findData("horizontal"))
        self.bombear()
        self.assertEqual(d.plantilla["size"], [420, 297])
        self.assertEqual(d.predeterminadas.currentData(), ("A3", "horizontal"))

    def test_SG111_leyenda_recinto_y_temporizadores_actuales(self):
        """REQ-EDT-09: marco entero y tiempos reales de la simulación, con espacio en torno al elemento."""
        from escritorio.diagrama import dibujar
        for nombre, crear in (("recinto", leyenda._recinto), ("contando", leyenda._temporizador_contando),
                              ("vencido", leyenda._temporizador_vencido)):
            modelo, estado, region = crear()
            escena = QGraphicsScene()
            dibujar(escena, modelo, estado, dependencias=False)
            caja = QRect(region[0], region[1], region[2] - region[0], region[3] - region[1])
            if nombre == "recinto":
                self.assertTrue(caja.contains(escena.itemsBoundingRect().toRect()))
            else:
                tiempos = list(estado["temporal"].values())
                self.assertTrue(any(t["shown"] == ("1,50 s" if nombre == "contando" else "3,00 s ✓") for t in tiempos))
                for item in escena.items():
                    if item.toolTip().startswith("Transición t1:"):
                        self.assertTrue(caja.contains(item.sceneBoundingRect().toRect()))
            pix = leyenda.dibujo(leyenda.Entrada(nombre, "", crear))
            self.assertFalse(pix.isNull())

    def test_SG112_macro_comentario_guardado_deshacer_y_menu_conservado(self):
        """REQ-EDT-02, REQ-DAT-02: comentario de M persistente y con deshacer, sin Renombrar en la ficha."""
        w, e = self.ventana()
        mid = e.poner_macro(QPointF(250, 150))
        e.seleccionar([mid])
        w._abrir_opciones()
        p = w.props
        self.assertFalse(p.ficha_izq.botones["Renombrar…"].isVisible())
        self.assertIn("Renombrar…", [t for t, f, marca in e.acciones_jerarquia(mid)])
        n = len(e.ed.undo_stack)
        p.m_comentario.setText("Comentario de prueba")
        p.m_comentario.editingFinished.emit()
        self.assertEqual(e.comentario(mid), "Comentario de prueba")
        self.assertEqual(len(e.ed.undo_stack), n + 1)
        e.deshacer()
        self.assertEqual(e.comentario(mid), "")
        e.rehacer()
        ruta = Path(self.documentos.name) / "macro.grafnet"
        self.assertTrue(w._guardar_archivo(ruta))
        self.assertTrue(w.abrir_ruta(ruta))
        nuevo = w.edicion
        nuevo.seleccionar([mid])
        w._abrir_opciones()
        self.assertEqual(w.props.m_comentario.text(), "Comentario de prueba")


if __name__ == "__main__":
    unittest.main()
