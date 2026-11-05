"""Segunda tanda de ajustes de la interfaz: casilla «Enlace de activación» del panel, canales iniciales de E/S,
«Ajustes de simulación», avisos sin códigos internos, «Basado en IEC 60848» y el botón «+ Añadir hoja» de Planos.

Ninguna prueba es oráculo del documento 11: comprueban lo que ve el usuario (textos, estilos, cantidades) y que cada
cambio sigue siendo una sola operación de deshacer."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers_grafnet import fixture_grafnet
from test_editor_cadenas import BaseQt, QT
import test_pulido_es

from conexion.configuracion import ARCHIVO, CANALES_INICIALES, Configuracion
from grafcet.profile import SEMANTIC_OPTIONS

if QT:
    from PySide6.QtCore import QPointF, QSettings
    from PySide6.QtWidgets import QLabel, QRadioButton

CODIGO = re.compile(r"\b(?:[DUH]-[A-Z0-9]|REQ-|P-IMP-)")


@unittest.skipUnless(QT, "PySide6 no está instalado")
class AjustesYAvisos(BaseQt):
    # -- 1: enlace de activación en el panel -------------------------------------------------------------------
    def test_SAJU01_el_panel_de_una_etapa_de_un_recinto_tiene_la_casilla_enlace_de_activacion(self):
        """REQ-JER-05, REQ-EDT-09: el panel de opciones de una etapa de un recinto muestra la casilla «Enlace de
        activación», marcada según el estado, que hace lo mismo que el menú (una operación de deshacer); una
        etapa fuera de un recinto no la lleva."""
        w, e, d = self.con_recinto()
        w.show()
        w._abrir_opciones()
        self.app.processEvents()
        a, h = d["a"], d["h"]
        e.seleccionar([a])
        self.app.processEvents()
        casilla = w.props.s_enlace
        self.assertEqual((casilla.isVisible(), casilla.isCheckable(), casilla.isChecked()), (True, True, False))
        n = len(e.ed.undo_stack)
        casilla.click()
        self.app.processEvents()
        marcas = e.ed.model["hierarchy"]["enclosures"][0]["activationRefs"]
        self.assertEqual((marcas, len(e.ed.undo_stack)), ([a], n + 1))
        self.assertTrue(casilla.isChecked())
        casilla.click()
        marcas = e.ed.model["hierarchy"]["enclosures"][0]["activationRefs"]
        self.assertEqual((marcas, len(e.ed.undo_stack)), ([], n + 2))
        e.deshacer()
        self.assertEqual(e.ed.model["hierarchy"]["enclosures"][0]["activationRefs"], [a])
        e.seleccionar([h])
        self.app.processEvents()
        self.assertTrue(w.props.s_enlace.isHidden())

    # -- 2: canales iniciales de E/S ---------------------------------------------------------------------------
    @staticmethod
    def canales_antiguos():
        return {a: {"offset": 0, "cantidad": 16 if a in ("discrete", "coil") else 8}
                for a in ("discrete", "coil", "input-register", "holding")}

    def test_SAJU02_un_proyecto_nuevo_no_hereda_los_16_8_recordados_de_una_version_anterior(self):
        """REQ-SIM-03, REQ-DAT-02: las preferencias recordadas por una versión anterior (16 digitales y 8 numéricas)
        ya no imponen sus cantidades a un proyecto sin mapa propio: abre con 32 y 12; sigue heredando el
        servidor."""
        from escritorio.ventana import Ventana
        ruta = Path(self.tmp.name) / "a.ini"
        self.w.ajustes.setValue("modbus/configuracion", json.dumps(
            {"host": "10.0.0.7", "puerto": 502, "unidad": 1, "periodo_ms": 20, "timeout_ms": 500,
             "canales": self.canales_antiguos(), "escalas": {}}))
        self.w.ajustes.sync()
        self.w.a_ejecutar.setChecked(False)
        self.w.edicion = None
        self.w.deleteLater()
        self.w = Ventana(QSettings(str(ruta), QSettings.Format.IniFormat))
        d = self.w._leer_parametros_recordados()
        self.assertEqual((d["host"], d["canales"]), ("10.0.0.7", CANALES_INICIALES))
        w, p = test_pulido_es.PulidoES.modelo(self)
        c = p.obtener()
        self.assertEqual((c.host, c.canales), ("10.0.0.7", CANALES_INICIALES))
        areas = ("discrete", "coil", "input-register", "holding")
        self.assertEqual([p.cantidades[a].value() for a in areas], [32, 32, 12, 12])

    def test_SAJU03_las_cantidades_de_un_proyecto_concreto_se_respetan_y_no_se_recuerdan_globalmente(self):
        """REQ-DAT-02, REQ-SIM-03: un proyecto con su propio mapa conserva sus cantidades; lo que se recuerda para los
        proyectos nuevos son siempre las iniciales, aunque el proyecto tuviera otras."""
        w, p = test_pulido_es.PulidoES.modelo(self)
        canales = self.canales_antiguos()
        w._recordar_parametros(Configuracion(host="10.0.0.8", canales=copy.deepcopy(canales)))
        prefs = json.loads(w.ajustes.value("modbus/configuracion"))
        self.assertEqual(prefs["canales"], CANALES_INICIALES)
        raiz = Path(self.tmp.name) / "guardado"
        w.edicion.guardar(raiz)
        Configuracion(host="10.0.0.9", canales=canales, modelo=p.doc["id"]).guardar(raiz / ARCHIVO, p.doc)
        self.assertTrue(w.abrir_ruta(fixture_grafnet(raiz)))
        self.assertEqual(p.obtener().canales, canales)
        self.assertEqual((p.cantidades["discrete"].value(), p.cantidades["input-register"].value()), (16, 8))

    # -- 3 y 5: ajustes de simulación y barra de estado --------------------------------------------------------
    def test_SAJU04_el_dialogo_de_ajustes_de_simulacion_tiene_una_sola_opcion_con_palabras_normales(self):
        """REQ-SEM-09: «Ajustes de simulación» muestra solo la lectura de los eventos de entrada, con dos textos sin
        jerga (de uno en uno = «situacion-anterior», todo de una vez = «recorrido»); las demás lecturas no se
        tocan."""
        from escritorio.ventana import Lecturas
        w = self.w
        titulos = [a.text().replace("&", "") for m in w.menuBar().actions() if m.menu() for a in m.menu().actions()]
        self.assertIn("Ajustes de simulación…", titulos)
        self.assertNotIn("Lecturas de interpretación…", titulos)
        d = Lecturas(w, w.options)
        self.assertEqual(d.windowTitle(), "Ajustes de simulación")
        self.assertEqual(sorted(d.botones), ["recorrido", "situacion-anterior"])
        self.assertEqual(len(d.findChildren(QRadioButton)), 2)
        textos = " ".join(x.text() for x in d.findChildren(QLabel) + d.findChildren(QRadioButton))
        self.assertIsNone(CODIGO.search(textos), textos)
        self.assertEqual(d.options(), w.options, "sin tocar nada, las lecturas no cambian")
        self.assertTrue(d.botones[SEMANTIC_OPTIONS["U-03"]["default"]].isChecked())
        d.botones["recorrido"].setChecked(True)
        self.assertEqual(d.options(), {**w.options, "U-03": "recorrido"})
        d._defaults()
        self.assertEqual(d.options(), w.options)
        base = {**w.options, "1.1": "B"}
        self.assertEqual(Lecturas(w, base).options()["1.1"], "B",
                         "las demás lecturas conservan su valor, aunque no se vean")

    def test_SAJU05_barra_de_estado_basado_en_iec_60848_y_aviso_de_ajuste_no_habitual(self):
        """REQ-NOR-02, REQ-SEM-09: la barra de estado dice «Basado en IEC 60848» (sin «conformidad» ni
        «provisional»); el aviso de un ajuste no habitual va en palabras normales y sin códigos."""
        w = self.w
        self.assertEqual(w.l_aviso.text(), "Basado en IEC 60848")
        w.cargar_ejemplo("bloqueo-u03")
        try:
            w._opciones({**w.options, "U-03": "recorrido"})
            self.assertEqual(w.l_lect.text(), "Ajustes de simulación no habituales · ")
            self.assertIsNone(CODIGO.search(w.l_lect.text() + w.l_lect.toolTip()))
        finally:
            w._opciones({})
        self.assertEqual(w.l_lect.text(), "")
        for texto in (w.l_aviso.text(), w.l_aviso.toolTip()):
            self.assertNotRegex(texto.lower(), "conform|provisional")

    # -- 4: avisos sin códigos ---------------------------------------------------------------------------------
    def test_SAJU06_los_avisos_no_llevan_codigos_internos_ni_rojo_agresivo(self):
        """REQ-EDT-09: la lista de diagnósticos dice «t1: la receptividad está vacía» (sin D-…, U-… ni H-…), con
        texto de color normal y un icono ámbar; los rechazos y el resumen tampoco muestran códigos, que siguen en
        el objeto diagnóstico."""
        from escritorio.diagrama import COL
        w, e = self.vacio()
        w.show()
        s = e.poner_etapa(QPointF(260, 60), inicial=True)
        t = e.poner_transicion(QPointF(260, 140))
        e.conectar(s, t)
        self.app.processEvents()
        diag = next(x for x in e.diagnosticos() if x["code"] == "D-EXP-PENDIENTE")
        self.assertEqual(diag["message"], "la receptividad está vacía")
        textos = [w.lista_diag.item(i).text() for i in range(w.lista_diag.count())]
        self.assertIn(f"{e.nombre(t)}: la receptividad está vacía", textos)
        for i in range(w.lista_diag.count()):
            item = w.lista_diag.item(i)
            self.assertIsNone(CODIGO.search(item.text()), item.text())
            self.assertEqual(item.foreground().color().name(), COL["text"])
        icono = w.diagrama.indicador_diagnosticos.pixmap().toImage()
        self.assertEqual(icono.pixelColor(12, 31).name(), COL["aviso"])
        self.assertIsNone(CODIGO.search(" ".join(e.resumen(e.diagnosticos()))))
        e.rechazar("D-REF: no existe la etapa (U-03) [jerarquia.macro-inicial]")
        self.assertEqual(e.mensaje, "no existe la etapa")
        e.informar("Basta con H-23 y P-IMP-80")
        self.assertIsNone(CODIGO.search(e.mensaje), e.mensaje)
        self.assertEqual(w.l_resumen.styleSheet().count(COL["err"]), 1, "el rojo queda para lo que impide simular")

    def test_SAJU07_los_rechazos_del_nucleo_se_muestran_sin_codigos(self):
        """REQ-EDT-09: un rechazo del núcleo (aquí, convertir en macroetapa una etapa inicial) se enseña sin código."""
        w, e = self.vacio()
        s = e.poner_etapa(QPointF(260, 80), inicial=True)
        e.cambiar_tipo_etapa(s, "macro")
        self.assertTrue(e.mensaje and not e.mensaje_info)
        self.assertIsNone(CODIGO.search(e.mensaje), e.mensaje)

    # -- 6: botón «+ Añadir hoja» ------------------------------------------------------------------------------
    def test_SAJU08_el_boton_anadir_hoja_es_principal_y_parpadea_mientras_no_hay_hojas(self):
        """REQ-EDT-11: con la pestaña Planos sin hojas, «+ Añadir hoja» tiene el fondo del acento y texto blanco y
        parpadea al entrar; con hojas vuelve a su estilo normal."""
        from grafcet.laminas import ajustes_lamina
        docs = tempfile.TemporaryDirectory()
        rutas = patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=docs.name)
        rutas.start()
        try:
            w, e = self.vacio()
            e.ed.add_step("g", "1", True)
            e.cambia()
            w.show()
            self.app.processEvents()
            w._mostrar_pagina("planos")
            p = w.panel_planos
            estilo = p.b_hoja.styleSheet()
            self.assertIn(p.ACENTO_HOJA, estilo)
            self.assertIn("color:white", estilo)
            self.assertTrue(p.t_hoja.isActive(), "parpadea al entrar")
            p.parpadeos_hoja = 1
            p._paso_parpadeo_hoja()
            self.assertFalse(p.t_hoja.isActive(), "son dos o tres parpadeos, no indefinidos")
            self.assertIn(p.ACENTO_HOJA, p.b_hoja.styleSheet())
            e.ed.add_plan_page(None, ajustes_lamina({}), "Hoja 1")
            p.mostrar()
            self.assertEqual(p.b_hoja.styleSheet(), "")
            self.assertFalse(p.t_hoja.isActive())
            w._mostrar_pagina(False)
            w._mostrar_pagina("planos")
            self.assertFalse(p.t_hoja.isActive(), "con hojas no parpadea")
        finally:
            self.w.panel_planos.guardar_timer.stop()
            rutas.stop()
            docs.cleanup()

    # -- 7 y 8: submenú marcado y «Acerca de» ------------------------------------------------------------------
    def test_SAJU09_la_opcion_marcada_del_submenu_tipo_de_etapa_se_distingue(self):
        """REQ-EDT-09: en «Tipo de etapa» el orden es Etapa, Etapa inicial, Encapsulante, Macroetapa y la fila marcada
        se distingue con la marca, la negrita y un icono con fondo."""
        w, e = self.vacio()
        s = e.poner_etapa(QPointF(260, 80))
        from escritorio.diagrama import posiciones
        menu = w.diagrama.menu_contextual(e.menu(QPointF(*posiciones(e.M)[s])))
        sub = next(a.menu() for a in menu.actions() if a.text() == "Tipo de etapa")
        self.assertEqual([a.text() for a in sub.actions()], ["Etapa", "Etapa inicial", "Encapsulante", "Macroetapa"])
        self.assertEqual([(a.text(), a.isChecked(), a.font().bold()) for a in sub.actions()],
                         [("Etapa", True, True), ("Etapa inicial", False, False), ("Encapsulante", False, False),
                          ("Macroetapa", False, False)])
        normal = sub.actions()[2].icon().pixmap(48, 48).toImage()
        marcado = sub.actions()[0].icon().pixmap(48, 48).toImage()
        self.assertEqual(marcado.pixelColor(8, 8).name(), "#cfeee6")
        self.assertNotEqual(normal.pixelColor(8, 8).name(), "#cfeee6")

    def test_SAJU10_acerca_de_se_abre_desde_el_menu_ayuda_con_version_licencia_y_enlaces(self):
        """REQ-NOR-02: «Ayuda > Acerca de GRAFCET Connect…» abre un diálogo con la versión (la de escritorio.VERSION),
        la licencia GPL-3.0 y los dos enlaces (código e incidencias), que se abren con QDesktopServices; Cerrar lo
        cierra."""
        from escritorio import VERSION
        from escritorio.ventana import AcercaDe, URL_CODIGO, URL_FALLOS
        from PySide6.QtWidgets import QPushButton
        ayuda = next(m.menu() for m in self.w.menuBar().actions() if m.text().replace("&", "") == "Ayuda")
        accion = next(a for a in ayuda.actions() if "Acerca de" in a.text())
        self.assertEqual(accion.text().replace("&", ""), "Acerca de GRAFCET Connect…")
        abiertos = []
        def abrir(url):
            abiertos.append(url.toString())

        def exec_falso(dialogo):
            AcercaDe.ultimo = dialogo
            return 0
        with patch("escritorio.ventana.QDesktopServices.openUrl", side_effect=abrir):
            with patch.object(AcercaDe, "exec", exec_falso):
                accion.trigger()
                d = AcercaDe.ultimo
                textos = " ".join(x.text() for x in d.findChildren(QLabel))
                for esperado in ("GRAFCET Connect", f"Versión {VERSION}", "Basado en IEC 60848", "GPL-3.0", URL_CODIGO,
                                 "sin ninguna garantía", "LICENSE"):
                    self.assertIn(esperado, textos)
                d.l_licencia.linkActivated.emit(URL_CODIGO)
                d.b_fallo.click()
        self.assertEqual(abiertos, [URL_CODIGO, URL_FALLOS])
        self.assertEqual(URL_FALLOS, URL_CODIGO + "/issues")
        self.assertEqual(d.b_fallo.text(), "Comunicar un fallo")
        self.assertIn("Cerrar", [b.text() for b in d.findChildren(QPushButton)])

    def test_SAJU11_la_version_es_una_sola_constante_compartida_con_el_constructor(self):
        """REQ-NOR-02: tools/construir_ejecutable.py lee la versión de escritorio.VERSION, sin duplicar el número."""
        import sys
        from escritorio import VERSION
        raiz = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(raiz / "tools"))
        try:
            import construir_ejecutable
        finally:
            sys.path.remove(str(raiz / "tools"))
        self.assertEqual(construir_ejecutable.VERSION, VERSION)
        self.assertNotRegex((raiz / "tools" / "construir_ejecutable.py").read_text(encoding="utf-8"),
                            r'VERSION\s*=\s*"[0-9]')


if __name__ == "__main__":
    unittest.main()
