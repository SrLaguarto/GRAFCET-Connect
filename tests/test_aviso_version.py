"""Aviso de versión nueva al arrancar: un diálogo emergente con el estilo de la aplicación. REQ-SIM-03."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from PySide6.QtCore import QPoint, QRect, QSettings
    from PySide6.QtWidgets import QAbstractButton, QLabel
    from tools import hoja_contactos as HC
    from escritorio import estilo
    from escritorio.aviso_version import DialogoVersionNueva
    from grafcet.profile import APP_VERSION
    QT = True
except ImportError:  # sin PySide6
    QT = False

URL = "https://github.com/SrLaguarto/GRAFCET-Connect/releases/tag/v999.0.0"


def _json(version):
    return json.dumps({"tag_name": version, "html_url": URL})


@unittest.skipUnless(QT, "Falta PySide6")
class AvisoVersionNueva(unittest.TestCase):
    def setUp(self):
        HC.aplicacion()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = str(Path(self.tmp.name) / "a.ini")
        self.respuesta = _json("v999.0.0")
        self.ventanas = []

    def ventana(self):
        from escritorio.ventana import Ventana
        w = Ventana(QSettings(self.ruta, QSettings.Format.IniFormat), lambda *a: self._responder())
        w.comprobador.sincrono = True
        w.show()
        HC._bombear(6)
        self.ventanas.append(w)
        self.addCleanup(self._cerrar, w)
        return w

    def _responder(self):
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta

    @staticmethod
    def _cerrar(w):
        if w._dialogo_version is not None:
            w._dialogo_version.reject()
        w.edicion = None
        w.hide()
        w.deleteLater()

    def dialogo(self):
        w = self.ventana()
        w.buscar_actualizaciones()
        HC._bombear(6)
        d = w._dialogo_version
        self.assertIsNotNone(d)
        self.assertTrue(d.isVisible())
        return w, d

    def test_SAVN01_sale_con_nueva_y_no_con_al_dia_ni_error(self):
        """REQ-SIM-03: el diálogo sale al arrancar con versión nueva y no con «al día» ni con error."""
        self.dialogo()
        for respuesta in (_json("v0.0.1"), OSError("sin conexión")):
            self.respuesta = respuesta
            w = self.ventana()
            w.buscar_actualizaciones()
            HC._bombear(4)
            self.assertIsNone(w._dialogo_version)

    def test_SAVN02_textos_y_versiones(self):
        """REQ-SIM-03: título, textos, versiones de la consulta real y botones del diálogo."""
        w, d = self.dialogo()
        self.assertEqual(d.windowTitle(), "GRAFCET Connect")
        self.assertEqual(d.width(), 440)
        self.assertTrue(d.isModal())
        textos = {l.text() for l in d.findChildren(QLabel)}
        for t in ("Hay una versión nueva", "GRAFCET Connect tiene una actualización disponible.", "Tiene instalada", "Disponible", "→"):
            self.assertIn(t, textos)
        self.assertEqual((d.l_instalada.text(), d.l_disponible.text()), (APP_VERSION, "999.0.0"))
        self.assertEqual([b.text() for b in d.findChildren(QAbstractButton)], ["Ahora no", "Descargar"])

    def test_SAVN03_caja_ajustada_y_centrada_y_bloque_centrado(self):
        """REQ-SIM-03: la caja de versiones va ajustada a su contenido y centrada en el diálogo, y su contenido centrado en ella."""
        w, d = self.dialogo()
        caja = d.caja.geometry()
        self.assertLessEqual(abs((caja.left()) - (d.width() - 1 - caja.right())), 1)
        self.assertLess(caja.width(), d.width() - 2 * estilo.E6)
        hijos = [x for x in d.caja.findChildren(QLabel) if x.isVisible()]
        izq = min(x.geometry().left() for x in hijos)
        der = max(x.geometry().right() for x in hijos)
        self.assertLessEqual(abs(izq - (d.caja.width() - 1 - der)), 1)
        self.assertEqual(izq, estilo.E6 + 1, "margen interior E6 a los lados (más el borde)")
        arriba = min(x.geometry().top() for x in hijos)
        self.assertGreaterEqual(arriba, estilo.E3)

    def test_SAVN04_descargar_es_el_predeterminado_y_abre_la_url(self):
        """REQ-SIM-03: «Descargar» es el botón por defecto y abre la URL segura; Esc equivale a «Ahora no»."""
        abiertas = []
        d = DialogoVersionNueva(None, "1.0.0", "9.9.9", URL, abrir=abiertas.append)
        d.show()
        self.assertTrue(d.b_descargar.isDefault() and not d.b_ahora_no.isDefault())
        d.b_descargar.click()
        self.assertEqual(abiertas, [URL])
        self.assertFalse(d.isVisible())
        d2 = DialogoVersionNueva(None, "1.0.0", "9.9.9", "https://otro.example/", abrir=abiertas.append)
        d2.show()
        d2.reject()  # (Esc y la ✕ llaman a reject)
        self.assertEqual(len(abiertas), 1)
        self.assertFalse(d2.isVisible())

    def test_SAVN05_ahora_no_no_guarda_y_vuelve_a_salir(self):
        """REQ-SIM-03: «Ahora no» no escribe nada en los ajustes y en el siguiente arranque vuelve a salir."""
        w, d = self.dialogo()
        antes = {k: w.ajustes.value(k) for k in w.ajustes.allKeys()}
        d.b_ahora_no.click()
        w.ajustes.sync()
        self.assertEqual({k: w.ajustes.value(k) for k in w.ajustes.allKeys()}, antes)
        self.assertFalse([k for k in w.ajustes.allKeys() if "ignorada" in k])
        w2, d2 = self.dialogo()  # otro arranque con los mismos ajustes
        self.assertTrue(d2.isVisible())

    def test_SAVN06_un_ajuste_antiguo_no_impide_el_aviso(self):
        """REQ-SIM-03: una versión «ignorada» de un ajuste antiguo ya no cuenta."""
        QSettings(self.ruta, QSettings.Format.IniFormat).setValue("actualizaciones/ignorada", "999.0.0")
        w, d = self.dialogo()
        self.assertTrue(d.isVisible())

    def test_SAVN07_la_busqueda_manual_usa_el_mismo_dialogo(self):
        """REQ-SIM-03: la comprobación manual con versión nueva abre el mismo diálogo; sin versión nueva informa como antes."""
        w = self.ventana()
        w.buscar_actualizaciones(True)
        HC._bombear(4)
        self.assertIsInstance(w._dialogo_version, DialogoVersionNueva)
        self.assertTrue(w._dialogo_version.isVisible())
        w._dialogo_version.reject()
        self.respuesta = _json("v0.0.1")
        textos = []
        with mock.patch("escritorio.ventana.QMessageBox.information", side_effect=lambda p, t, texto, *a: textos.append(texto)):
            w.buscar_actualizaciones(True)
        self.assertIn("última versión", textos[0])

    def test_SAVN08_sin_textos_recortados_y_botones_centrados(self):
        """REQ-SIM-03, guía C2 y C3: ningún texto del diálogo se corta y el contenido de sus botones va centrado."""
        from test_auditoria_maquetacion import CentradoBotones, REGLAS
        w, d = self.dialogo()
        self.assertEqual(REGLAS["C2"](d), [])
        imagen = d.grab().toImage()
        for b in d.findChildren(QAbstractButton):
            self.assertEqual(b.height(), estilo.ALTO_CONTROL)
            h = CentradoBotones.huecos(b, imagen)
            self.assertLessEqual(abs(h[0] - h[1]), 2, (b.text(), h))
        for l in d.findChildren(QLabel):
            if l.text():
                self.assertLessEqual(l.fontMetrics().horizontalAdvance(l.text()), l.width() + 1, l.text())


if __name__ == "__main__":
    unittest.main()
