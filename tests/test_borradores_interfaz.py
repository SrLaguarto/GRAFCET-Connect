"""Diagnósticos de borradores y reparación al abrir desde la interfaz."""
import unittest
from pathlib import Path
from unittest import mock
from test_editor_cadenas import BaseQt, QT

if QT:
    from PySide6.QtCore import QPointF
    from escritorio.diagrama import cajas_parciales


@unittest.skipUnless(QT, "PySide6 no está instalado")
class BorradoresInterfaz(BaseQt):
    def preparado(self):
        w, e = self.vacio()
        e.pedir_accion = lambda *a: None
        h = e.poner_etapa(QPointF(260, 80), inicial=True)
        e.renombrar(h, "2")
        g = e.poner_parcial(QPointF(700, 220))
        c = cajas_parciales(e.M)[g]
        b = e.poner_etapa(QPointF((c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2))
        return w, e, h, g, b

    def comprobar_play_bloqueado(self, w, e, did, texto):
        self.assertTrue(e.ed.validate().can_simulate, "el bloqueo pertenece a la edición de la presentación")
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.a_ejecutar.setChecked(True)
        self.assertEqual(w.modo, "editar")
        self.assertFalse(w.a_ejecutar.isChecked())
        aviso.assert_called_once()
        mensaje = aviso.call_args.args[2]
        self.assertIn("El grafcet no compila", mensaje)
        self.assertIn(texto, mensaje)
        self.assertNotIn(did, mensaje)
        self.assertIn(did, e.parpadeo.ids)
        self.assertIn(did, e.marcados())
        return mensaje

    def test_SFBR01_forzado_suelto_bloquea_play_y_parpadea_su_caja(self):
        """REQ-EDT-02, REQ-EDT-09: la orden suelta sin configurar impide Play, se nombra y parpadea."""
        w, e, h, g, b = self.preparado()
        did = e.poner_orden_ficha(QPointF(500, 500))
        self.comprobar_play_bloqueado(w, e, did, "Orden de forzado sin configurar suelta")
        self.assertTrue(any(c["id"] == did for c in w.diagrama.cajas_acciones))

    def test_SFBR02_forzado_unido_incompleto_y_completo(self):
        """REQ-JER-02, REQ-EDT-09: faltan destino, forma o etapas; completar elimina el bloqueo y permite Play."""
        w, e, h, g, b = self.preparado()
        did = e.poner_orden_ficha(QPointF(500, 500))
        self.unir(e, did, "izq", h, "arriba")
        for datos, falta in (({}, "parcial destino, forma"), ({"destino": g}, "forma"),
                             ({"destino": g, "forma": "explicit"}, "etapas")):
            e.ed.update_draft_action(did, **datos)
            e.cambia()
            self.comprobar_play_bloqueado(w, e, did, "Orden de forzado sin configurar en la etapa 2")
            self.assertIn(falta, next(d["message"] for d in e.diagnosticos() if d["element"] == did))
        e.pedir_forzado = lambda datos: {"destino": g, "forma": "explicit", "etapas": [b]}
        fid = e.configurar_orden(did)
        self.assertFalse(e.ed.draft_actions())
        self.assertNotEqual(fid, did)
        self.assertFalse(any(d["blocks"] for d in e.diagnosticos()))
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.a_ejecutar.setChecked(True)
        self.assertEqual(w.modo, "simular")
        aviso.assert_not_called()

    def test_SFBR03_accion_normal_suelta_bloquea_y_al_completar_se_puede_simular(self):
        """REQ-ACT-01, REQ-EDT-09: la acción normal suelta bloquea Play; unirla y completarla retira el error."""
        w, e, h, g, b = self.preparado()
        did = e.poner_accion_suelta(QPointF(500, 500))
        self.comprobar_play_bloqueado(w, e, did, "Acción sin configurar suelta")
        e.nueva_variable("salida", "output")
        self.unir(e, did, "izq", h, "arriba")
        self.assertIsNone(e.poner_accion(h, {"tipo": "continua", "variable": "salida"}, did))
        self.assertFalse(e.ed.draft_actions())
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.a_ejecutar.setChecked(True)
        self.assertEqual(w.modo, "simular")
        aviso.assert_not_called()

    def test_SFBR04_accion_normal_unida_incompleta_bloquea_y_parpadea(self):
        """REQ-EDT-02, REQ-EDT-09: la acción normal unida sin variable también bloquea Play con nombre y parpadeo."""
        w, e, h, g, b = self.preparado()
        did = e.anadir_accion(h)
        self.comprobar_play_bloqueado(w, e, did, "Acción sin configurar en la etapa 2 (variable)")
        e.nueva_variable("salida", "output")
        self.assertIsNone(e.poner_accion(h, {"tipo": "continua", "variable": "salida"}, did))
        self.assertFalse(any(d["blocks"] for d in e.diagnosticos()))
        with mock.patch("escritorio.ventana.QMessageBox.warning") as aviso:
            w.a_ejecutar.setChecked(True)
        self.assertEqual(w.modo, "simular")
        aviso.assert_not_called()

    def test_SFBR05_guardar_y_abrir_conserva_bloqueos_de_borradores(self):
        """REQ-DAT-01, REQ-EDT-09: el proyecto conserva las órdenes y acciones sueltas y sus bloqueos al abrir."""
        w, e, h, g, b = self.preparado()
        forzado = e.poner_orden_ficha(QPointF(500, 500))
        accion = e.poner_accion_suelta(QPointF(850, 500))
        destino = Path(self.tmp.name) / "borradores"
        e.guardar(destino)
        self.assertTrue(w.abrir_ruta(destino))
        e = w.edicion
        self.assertEqual({d["id"] for d in e.ed.draft_actions()}, {forzado, accion})
        self.comprobar_play_bloqueado(w, e, forzado, "Orden de forzado sin configurar suelta")
        self.assertIn(accion, e.parpadeo.ids)

    def test_SFBR06_abrir_fixture_limpia_y_avisa_una_vez(self):
        """REQ-EDT-01, REQ-EDT-09: abrir el proyecto real retira el enlace huérfano y avisa una vez."""
        w, e = self.vacio()
        ruta = Path(__file__).parent / "fixtures" / "salto_de_etapas"
        with mock.patch("escritorio.ventana.QMessageBox.information") as aviso:
            self.assertTrue(w.abrir_ruta(ruta))
            e = w.edicion
            self.assertFalse(e.ed.model["draftLinks"])
            self.assertTrue(e.ed.dirty)
            self.assertIn("Se quitó un enlace en borrador que apuntaba a elementos que ya no existen", aviso.call_args.args[2])
            w.refrescar_edicion()
            w._establecer_edicion(e)
            with mock.patch("escritorio.ventana.QMessageBox.warning"):
                w.a_ejecutar.setChecked(True)
            aviso.assert_called_once()
        self.assertFalse(any(d["code"] == "D-ALTERNANCIA" for d in e.diagnosticos()))
        w.a_ejecutar.setChecked(False)
        destino = Path(self.tmp.name) / "saneado"
        e.guardar(destino)
        with mock.patch("escritorio.ventana.QMessageBox.information") as aviso:
            self.assertTrue(w.abrir_ruta(destino))
            aviso.assert_not_called()
        self.assertFalse(w.edicion.ed.cleaned_draft_link_ids)
