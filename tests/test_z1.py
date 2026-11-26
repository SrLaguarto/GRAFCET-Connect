"""Remates Z1: el submenú «Tipo de acción» del botón derecho (iconos de 20 px, filas de 32 px, ✓ en el tipo activo)."""
import unittest

from test_editor_cadenas import BaseQt, QT, centro_caja

if QT:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QMenu

    from escritorio import estilo


@unittest.skipUnless(QT, "requiere PySide6")
class SubmenuTipoAccion(BaseQt):
    def test_SZ101_submenu_tipo_de_accion_iconos_20_filas_32_y_marca(self):
        """REQ-UX-01 (Carbon #9.1): el submenú «Tipo de acción» tiene iconos de 20 px, filas de 32 px y la marca ✓ estándar en el tipo activo."""
        w, e = self.vacio()
        e.pedir_accion = lambda *a: None
        h = e.poner_etapa(QPointF(260, 80), inicial=True)
        e.nueva_variable("Q00", "output")
        w.resize(1360, 860)
        w.show()
        self.app.processEvents()
        self.assertIsNone(e.poner_accion(h, {"tipo": "continua", "variable": "Q00"}))
        (aid,) = [a["id"] for a in e.ed.model["actions"]]
        menu = w.diagrama.menu_contextual(e.menu(centro_caja(w, aid)))
        sub = next(a.menu() for a in menu.actions() if a.text() == "Tipo de acción")
        sub.ensurePolished()
        sub.show()
        self.app.processEvents()
        acciones = sub.actions()
        self.assertGreaterEqual(len(acciones), 6)
        self.assertEqual(sub.style().pixelMetric(sub.style().PixelMetric.PM_SmallIconSize), 20)
        alturas = {sub.actionGeometry(a).height() for a in acciones}
        self.assertEqual(alturas, {estilo.ALTO_ESTANDAR})
        marcadas = [a.text() for a in acciones if a.isChecked()]
        self.assertEqual(marcadas, ["Continua"])
        self.assertFalse(any(a.font().bold() for a in acciones), "el tipo activo no va en negrita: lleva la marca ✓")
        sub.close()
