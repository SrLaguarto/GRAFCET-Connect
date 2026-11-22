"""SSEL01..SSEL03: comprobación opcional de los documentos sellados (V2-E6, `GRAFCONNECT_COMPROBAR_SELLOS=1`)."""
import os
import unittest
from unittest import mock

from grafcet.editor import Editor, new_grafcet_document
from grafcet.model import COMPROBAR_SELLOS, SelloRoto, validate_model


class SellosComprobados(unittest.TestCase):
    def nuevo(self):
        from grafcet.view import presentation_for
        doc = new_grafcet_document("m-sellos")
        ed = Editor(doc, presentation_for(doc, {}))
        ed.add_step("g", "0", initial=True, at=(100, 100))
        return ed

    def test_SSEL01_con_la_variable_un_documento_sellado_modificado_en_el_sitio_se_detecta(self):
        """REQ-EDT-09: con `GRAFCONNECT_COMPROBAR_SELLOS=1`, `validate_model` recalcula la revisión y los diagnósticos en cada acierto de su
        memoria y falla con `SelloRoto` si alguien cambió en el sitio un documento que el editor sella."""
        ed = self.nuevo()
        with mock.patch.dict(os.environ, {COMPROBAR_SELLOS: "1"}):
            validate_model(ed.model)
            validate_model(ed.model)  # un acierto de la memoria, sin tocar nada: pasa
            ed.model["steps"][0]["initial"] = False  # modificado en el sitio, sin crear otro documento
            with self.assertRaises(SelloRoto) as r:
                validate_model(ed.model)
            self.assertIn("se modificó en el sitio", str(r.exception))

    def test_SSEL02_sin_la_variable_no_se_comprueba_nada(self):
        """REQ-EDT-09: sin la variable, `validate_model` no recalcula nada: devuelve lo recordado aunque el documento se hubiera tocado."""
        ed = self.nuevo()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(COMPROBAR_SELLOS, None)
            antes = validate_model(ed.model)
            ed.model["steps"][0]["initial"] = False
            self.assertEqual(validate_model(ed.model).diagnostics, antes.diagnostics)

    def test_SSEL03_con_la_variable_las_ediciones_normales_pasan(self):
        """REQ-EDT-09: con la variable activa, las operaciones del editor (que crean documentos nuevos y los sellan) y deshacer y rehacer no
        fallan, y dan los mismos diagnósticos que sin ella."""
        ed = self.nuevo()
        sin = validate_model(ed.model).diagnostics
        with mock.patch.dict(os.environ, {COMPROBAR_SELLOS: "1"}):
            self.assertEqual(validate_model(ed.model).diagnostics, sin)
            ed.add_step("g", "1", at=(100, 300))
            ed.validate()
            ed.undo()
            self.assertEqual(ed.validate().diagnostics, sin)
            ed.redo()
            ed.validate()


if __name__ == "__main__":
    unittest.main()
