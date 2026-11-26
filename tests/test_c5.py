"""Historial de autores y presentación de los diálogos de C5."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from grafcet.contenedor import (
    HISTORIAL_AUTORES, INFO, MAX_AUTOR, MAX_HISTORIAL_AUTORES, MAX_INFO, _info_valida,
    construir_info, empaquetar, inspeccionar, sello_valido, serializar_info,
)
from grafcet.persistence import save_project
from escritorio.proyecto_archivo import abrir_grafnet, guardar_grafnet
from test_editor_cadenas import BaseQt, QT
from test_propiedades_resellar import proyecto_de_prueba


FECHA = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)
CLAVE_PRUEBA = bytes(range(32))


def _info_1x(datos):
    """Lector de metadatos de implementacion/grafcet/contenedor.py (1.x)."""
    if datos is None or len(datos) > 4096:
        return {}
    try:
        info = json.loads(datos)
    except (ValueError, UnicodeError, RecursionError):
        return {}
    if not isinstance(info, dict):
        return {}
    limpia = {}
    for campo in ('autor', 'creado', 'modificado', 'version_creacion', 'version_guardado'):
        if campo not in info:
            continue
        valor = info[campo]
        if not isinstance(valor, str) or len(valor) > 500:
            return {}
        if campo in ('creado', 'modificado'):
            try:
                datetime.fromisoformat(valor)
            except ValueError:
                return {}
        limpia[campo] = valor
    return limpia


class HistorialC5(unittest.TestCase):
    def test_SC501_autor_nuevo_repetido_y_retomado(self):
        primera = construir_info(None, 'Ana', '2.0.0', FECHA)
        hoy = FECHA.isoformat()
        manana = FECHA + timedelta(days=1)
        siguiente = construir_info(primera, 'Ana', '2.0.0', manana)
        self.assertEqual(primera[HISTORIAL_AUTORES], [{'autor': 'Ana', 'desde': hoy, 'hasta': hoy}])
        self.assertEqual(siguiente[HISTORIAL_AUTORES], [{'autor': 'Ana', 'desde': hoy, 'hasta': manana.isoformat()}])
        tercero = construir_info(siguiente, 'Bea', '2.0.0', FECHA + timedelta(days=2))
        cuarto = construir_info(tercero, 'Ana', '2.0.0', FECHA + timedelta(days=3))
        self.assertEqual([e['autor'] for e in cuarto[HISTORIAL_AUTORES]], ['Ana', 'Bea', 'Ana'])
        self.assertEqual(cuarto['autor'], 'Ana')

    def test_SC502_archivo_anterior_y_sello_del_historial(self):
        with TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            proyecto = proyecto_de_prueba()
            save_project(raiz / 'fuente', proyecto)
            previa = {'autor': 'La autora antigua', 'creado': FECHA.isoformat(), 'version_creacion': '1.0.0'}
            fichero = raiz / 'antiguo.grafnet'
            fichero.write_bytes(empaquetar(raiz / 'fuente', CLAVE_PRUEBA, serializar_info(previa)))
            abierto = abrir_grafnet(fichero, CLAVE_PRUEBA, 'rechazar')
            try:
                self.assertEqual(abierto.info, previa)
                nuevo = raiz / 'nuevo.grafnet'
                guardado = guardar_grafnet(nuevo, proyecto, CLAVE_PRUEBA, info_previa=abierto.info, autor='Ana')
                try:
                    self.assertEqual(guardado.info['creado'], previa['creado'])
                    entrada, = guardado.info[HISTORIAL_AUTORES]
                    fecha = guardado.info['modificado']
                    self.assertEqual(entrada, {'autor': 'Ana', 'desde': fecha, 'hasta': fecha})
                    self.assertEqual(inspeccionar(nuevo.read_bytes())[0], guardado.info)
                    info_alterada = {**guardado.info, HISTORIAL_AUTORES: [{**entrada, 'autor': 'Bea'}]}
                    copia = BytesIO()
                    with ZipFile(nuevo) as fuente, ZipFile(copia, 'w') as destino:
                        for nombre in fuente.namelist():
                            datos = serializar_info(info_alterada) if nombre == INFO else fuente.read(nombre)
                            destino.writestr(nombre, datos)
                    self.assertTrue(sello_valido(nuevo.read_bytes(), CLAVE_PRUEBA))
                    self.assertFalse(sello_valido(copia.getvalue(), CLAVE_PRUEBA))
                finally:
                    guardado.cerrar()
            finally:
                abierto.cerrar()

    def test_SC503_tope_y_presupuesto_utf8_compatibles_con_1x(self):
        for prefijo in ('', '\x00' * MAX_AUTOR, '\U0001f642' * MAX_AUTOR):
            with self.subTest(prefijo=prefijo[:1]):
                info = None
                autores = []
                for i in range(25):
                    autor = f'{i:02}{prefijo}'
                    autores.append(autor[:MAX_AUTOR])
                    info = construir_info(info, autor, '2.0.0', FECHA + timedelta(days=i))
                    datos = serializar_info(info)
                    self.assertLess(len(datos), MAX_INFO)
                    self.assertEqual(_info_valida(datos), info)
                    self.assertEqual(_info_1x(datos), {k: v for k, v in info.items() if k != HISTORIAL_AUTORES})
                historial = [e['autor'] for e in info[HISTORIAL_AUTORES]]
                if not prefijo:
                    self.assertEqual(len(historial), MAX_HISTORIAL_AUTORES)
                self.assertLessEqual(len(historial), MAX_HISTORIAL_AUTORES)
                self.assertEqual(historial, autores[:1] + autores[-(len(historial) - 1):])

        version_larga = '\x00' * 500
        anterior = construir_info(None, 'Ana', version_larga, FECHA)
        info = construir_info(anterior, 'Bea', version_larga, FECHA + timedelta(days=1))
        datos = serializar_info(info)
        self.assertLess(len(datos), MAX_INFO)
        self.assertEqual([e['autor'] for e in _info_valida(datos)[HISTORIAL_AUTORES]], ['Ana', 'Bea'])
        self.assertEqual(_info_1x(datos)['autor'], 'Bea')

    def test_SC504_historial_mal_formado_se_ignora_solo_el(self):
        base = {'autor': 'Ana', 'version_guardado': '2.0.0'}
        entrada = {'autor': 'Ana', 'desde': FECHA.isoformat(), 'hasta': FECHA.isoformat()}
        errores = (
            entrada, ['Ana'], [{**entrada, 'desde': 'ayer'}], [{**entrada, 'hasta': '2025-01-01'}],
            [{**entrada, 'autor': 8}], [{**entrada, 'autor': 'x' * (MAX_AUTOR + 1)}],
            [entrada] * (MAX_HISTORIAL_AUTORES + 1),
        )
        for mal in errores:
            with self.subTest(mal=mal):
                datos = json.dumps({**base, HISTORIAL_AUTORES: mal}).encode()
                self.assertEqual(_info_valida(datos), base)


@unittest.skipUnless(QT, 'requiere PySide6')
class InterfazC5(BaseQt):
    def test_SC505_guardar_como_y_propiedades_con_historial(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QLabel
        from escritorio.propiedades_archivo import PropiedadesArchivo, recopilar

        w, e = self.vacio()
        e.ed.add_step('g', '1', True)
        e.cambia()
        e.autor_archivo = 'Ana'
        origen = Path(self.tmp.name) / 'original.grafnet'
        self.assertTrue(w._guardar_archivo(origen))
        e.autor_archivo = 'Bea'
        destino = Path(self.tmp.name) / ('copia_' + 'a' * 70 + '.grafnet')
        with patch('escritorio.archivos.QFileDialog.getSaveFileName', return_value=(str(destino), '')):
            self.assertTrue(w.guardar_como())
        self.assertEqual([e['autor'] for e in inspeccionar(origen.read_bytes())[0][HISTORIAL_AUTORES]], ['Ana'])
        self.assertEqual([e['autor'] for e in inspeccionar(destino.read_bytes())[0][HISTORIAL_AUTORES]], ['Ana', 'Bea'])
        cuadro = PropiedadesArchivo(recopilar(e), w)
        try:
            self.assertEqual(cuadro.width(), 500)
            self.assertEqual(cuadro.ruta.modo, Qt.TextElideMode.ElideMiddle)
            self.assertEqual(cuadro.ruta.toolTip(), str(destino))
            cuadro.b_copiar.click()
            self.assertEqual(QApplication.clipboard().text(), str(destino))
            historial, = [v for v in cuadro.findChildren(QLabel) if v.accessibleName() == 'Historial de autores']
            self.assertTrue(historial.text().splitlines()[0].startswith('Ana · '))
            self.assertRegex(historial.text().splitlines()[1], r'^Bea · \d{2}-\d{2}-\d{4} → \d{2}-\d{2}-\d{4}$')
            self.assertFalse(cuadro.c_autor.isReadOnly())
        finally:
            cuadro.close()

    def test_SC506_renombrar_y_mensajes_conservan_los_botones_nativos(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QMessageBox

        resultado = []

        def recoger_renombrar():
            cuadro = QApplication.activeModalWidget()
            caja = cuadro.findChild(QDialogButtonBox)
            cancelar = caja.button(QDialogButtonBox.StandardButton.Cancel)
            aceptar = caja.button(QDialogButtonBox.StandardButton.Ok)
            resultado.append((cancelar.text(), aceptar.text(), cancelar.x() < aceptar.x(),
                              aceptar.property('primario')))
            cancelar.click()

        QTimer.singleShot(0, recoger_renombrar)
        self.assertIsNone(self.w._pedir_texto('Renombrar la macroetapa', 'Nuevo nombre', 'M1'))
        self.assertEqual(resultado, [('Cancelar', 'Aceptar', True, True)])

        cuadro = QMessageBox(QMessageBox.Icon.Question, 'Guardar proyecto', 'El archivo ya existe.',
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self.w)
        try:
            cuadro.setDefaultButton(QMessageBox.StandardButton.No)
            cuadro.show()
            QApplication.processEvents()
            no = cuadro.button(QMessageBox.StandardButton.No)
            si = cuadro.button(QMessageBox.StandardButton.Yes)
            self.assertLess(si.x(), no.x())
            self.assertTrue(no.property('primario'))
            self.assertIs(cuadro.defaultButton(), no)
            self.assertEqual(cuadro.layout().contentsMargins().left(), 20)
            titulo = cuadro.findChild(QLabel, 'titularMensaje')
            self.assertEqual(titulo.text(), 'Guardar proyecto')
            self.assertTrue(titulo.font().bold())
            self.assertEqual(cuadro.text(), 'El archivo ya existe.')
        finally:
            cuadro.close()

        cuadro = QMessageBox(QMessageBox.Icon.Warning, 'Aviso', 'El archivo tiene un problema.',
                             QMessageBox.StandardButton.Close, self.w)
        try:
            cuadro.setDetailedText('Más información del problema.')
            cuadro.show()
            QApplication.processEvents()
            cerrar = cuadro.button(QMessageBox.StandardButton.Close)
            caja = cuadro.findChild(QDialogButtonBox)
            detalles = next(boton for boton in caja.buttons() if boton is not cerrar)
            self.assertLess(detalles.x(), cerrar.x())
            self.assertTrue(cerrar.property('primario'))
        finally:
            cuadro.close()

    def test_SC507_editar_texto_muestra_color_y_usa_el_pie_comun(self):
        from PySide6.QtWidgets import QDialog, QFrame
        from escritorio.anotaciones import editar_texto
        from escritorio.componentes_comunes import PieDialogo

        def examinar(cuadro):
            pie = cuadro.findChild(PieDialogo)
            self.assertEqual((pie.boton_cancelar.text(), pie.boton_aceptar.text()), ('Cancelar', 'Aceptar'))
            muestra = cuadro.findChild(QFrame, 'muestraColorTexto')
            self.assertIn('background:#e33920', muestra.styleSheet())
            return QDialog.DialogCode.Rejected

        with patch.object(QDialog, 'exec', examinar):
            self.assertIsNone(editar_texto({'color': '#e33920'}, self.w))

    def test_SC508_traer_es_usa_cabecera_y_pie_comunes(self):
        from escritorio.componentes_comunes import CabeceraDialogo, PieDialogo
        from escritorio.traer_dialogo import DialogoTraer

        with patch.object(DialogoTraer, 'leer'):
            cuadro = DialogoTraer(self.w.panel_es.directa)
        try:
            self.assertIsInstance(cuadro.cabecera, CabeceraDialogo)
            self.assertIs(cuadro.titulo, cuadro.cabecera.etiqueta_titulo)
            pie = cuadro.findChild(PieDialogo)
            self.assertIs(cuadro.b_traer, pie.boton_aceptar)
            self.assertEqual(pie.boton_cancelar.text(), 'Cancelar')
            self.assertEqual(cuadro.b_leer.text(), 'Volver a leer')
            self.assertIs(cuadro.b_leer.parentWidget(), pie)
        finally:
            cuadro.reject()
