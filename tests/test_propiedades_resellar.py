"""Metadatos del archivo (`_grafnet/info.json`), Proyecto > Propiedades del archivo… y tools/resellar.py."""
import contextlib
from datetime import datetime, timedelta
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from grafcet.contenedor import (INFO, SELLO, ErrorContenedor, construir_info, empaquetar, huella, inspeccionar,
                                sello_valido)
from grafcet.editor import Editor, new_grafcet_document
from grafcet.persistence import add_document, new_project, save_project
from grafcet.profile import APP_VERSION
from escritorio import VERSION
from escritorio.proyecto_archivo import abrir_grafnet, guardar_grafnet
from escritorio.sello import CLAVE, CLAVE_DESARROLLO
from tools import resellar
from test_editor_cadenas import BaseQt, QT
if QT:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication
    from escritorio import propiedades_archivo as pa


def proyecto_de_prueba():
    e = Editor(new_grafcet_document('m'))
    e.add_step('g', '1', True)
    p = new_project('p', 'Proyecto')
    add_document(p, e.model)
    add_document(p, e.presentation)
    return p


def entradas_de(datos):
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        return {n: z.read(n) for n in z.namelist()}


class Metadatos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.proyecto = proyecto_de_prueba()

    def tearDown(self):
        self.tmp.cleanup()

    def guardar(self, nombre='p.grafnet', previa=None, autor=''):
        archivo = guardar_grafnet(self.root / nombre, self.proyecto, CLAVE, None, None, previa, autor)
        archivo.cerrar()
        return self.root / nombre

    def antiguo(self):
        raiz = self.root / 'antiguo'
        save_project(raiz, self.proyecto)
        destino = self.root / 'antiguo.grafnet'
        destino.write_bytes(empaquetar(raiz, CLAVE))
        return destino

    def test_SPRP01_info_sellada_con_autor_fechas_y_versiones(self):
        """REQ-DAT-02: cada guardado escribe `_grafnet/info.json` sellado con los cinco campos."""
        destino = self.guardar(autor='Ana')
        self.assertIn(INFO, entradas_de(destino.read_bytes()))
        abierto = abrir_grafnet(destino, CLAVE, 'rechazar')
        try:
            info = abierto.info
            self.assertEqual(info['autor'], 'Ana')
            self.assertEqual((info['version_creacion'], info['version_guardado']), (APP_VERSION, APP_VERSION))
            self.assertEqual(datetime.fromisoformat(info['creado']).tzinfo is not None, True)
            self.assertEqual(set(info), {'autor', 'creado', 'modificado', 'version_creacion', 'version_guardado'})
        finally:
            abierto.cerrar()

    def test_SPRP02_creado_se_conserva_y_modificado_cambia(self):
        """REQ-DAT-02: entre guardados, creado y version_creacion se conservan; modificado y version_guardado se actualizan."""
        antes = datetime.now().astimezone() - timedelta(days=3)
        previa = construir_info(None, 'Ana', '0.9.0', antes)
        nueva = construir_info(previa, 'Ana', '1.0.0')
        self.assertEqual((nueva['creado'], nueva['version_creacion']), (previa['creado'], '0.9.0'))
        self.assertNotEqual(nueva['modificado'], previa['modificado'])
        self.assertEqual(nueva['version_guardado'], '1.0.0')
        destino = self.guardar()
        primero = abrir_grafnet(destino, CLAVE, 'rechazar')
        try:
            segundo = guardar_grafnet(destino, self.proyecto, CLAVE, None, None, primero.info, 'Luis')
            segundo.cerrar()
            final = abrir_grafnet(destino, CLAVE, 'rechazar')
            try:
                self.assertEqual(final.info['creado'], primero.info['creado'])
                self.assertEqual(final.info['autor'], 'Luis')
            finally:
                final.cerrar()
        finally:
            primero.cerrar()

    def test_SPRP03_archivo_anterior_sin_info_abre_y_no_inventa_creacion(self):
        """REQ-DAT-02: un archivo sin info.json abre igual; al guardarlo no se inventan creado ni version_creacion."""
        destino = self.antiguo()
        abierto = abrir_grafnet(destino, CLAVE, 'rechazar')
        try:
            self.assertEqual(abierto.info, {})
            info = construir_info(abierto.info, '', APP_VERSION)
            self.assertNotIn('creado', info)
            self.assertNotIn('version_creacion', info)
        finally:
            abierto.cerrar()

    def test_SPRP04_info_manipulado_sin_resellar_se_rechaza(self):
        """REQ-DAT-02: info.json está cubierto por el sello: cambiarlo sin resellar rechaza el archivo."""
        destino = self.guardar(autor='Ana')
        entradas = entradas_de(destino.read_bytes())
        entradas[INFO] = entradas[INFO].replace(b'Ana', b'Eva')
        manipulado = self.root / 'manipulado.grafnet'
        with zipfile.ZipFile(manipulado, 'w') as z:
            for nombre, datos in entradas.items():
                z.writestr(nombre, datos)
        with self.assertRaises(ErrorContenedor):
            abrir_grafnet(manipulado, CLAVE, 'rechazar')

    def test_SPRP05_info_mal_formado_con_sello_valido_se_ignora(self):
        """REQ-DAT-02: un info.json con tipos o tamaño incorrectos no rechaza el archivo: datos desconocidos."""
        raiz = self.root / 'raiz'
        save_project(raiz, self.proyecto)
        malos = [b'[1,2]', b'no es json', b'{"autor": 5}', b'{"creado": "ayer"}', b'{"autor": "' + b'x' * 5000 + b'"}']
        for i, malo in enumerate(malos):
            destino = self.root / f'malo{i}.grafnet'
            destino.write_bytes(empaquetar(raiz, CLAVE, malo))
            abierto = abrir_grafnet(destino, CLAVE, 'rechazar')
            try:
                self.assertEqual(abierto.info, {}, malo[:20])
            finally:
                abierto.cerrar()

    def test_SPRP06_huella_cambia_con_el_contenido_y_no_con_la_clave(self):
        """REQ-DAT-02: la huella (sin clave) identifica el contenido sellado."""
        raiz = self.root / 'raiz'
        save_project(raiz, self.proyecto)
        a = empaquetar(raiz, CLAVE, b'{"autor": "A"}')
        b = empaquetar(raiz, os.urandom(32), b'{"autor": "A"}')
        c = empaquetar(raiz, CLAVE, b'{"autor": "B"}')
        self.assertEqual(inspeccionar(a)[1], inspeccionar(b)[1])
        self.assertNotEqual(inspeccionar(a)[1], inspeccionar(c)[1])
        self.assertEqual(len(huella(entradas_de(a))), 64)

    def test_SPRP07_version_del_programa_y_manifiesto_no_divergen(self):
        """REQ-NOR-02: escritorio.VERSION, APP_VERSION y appVersion del manifiesto son la misma, 1.0.0."""
        self.assertEqual(VERSION, APP_VERSION)
        self.assertEqual(APP_VERSION, '1.0.0')
        self.assertEqual(self.proyecto.manifest['appVersion'], '1.0.0')


class Resellado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clave = os.urandom(32)
        self.archivo_clave = self.root / 'clave.bin'
        self.archivo_clave.write_bytes(self.clave)
        self.proyecto = proyecto_de_prueba()
        self.dir = self.root / 'proyectos'
        self.dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def crear(self, nombre, clave):
        archivo = guardar_grafnet(self.dir / nombre, self.proyecto, clave, None, None, None, 'Ana')
        archivo.cerrar()
        return self.dir / nombre

    def ejecutar(self, *rutas, clave=None):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = resellar.main(['--archivo-clave', str(clave or self.archivo_clave), *map(str, rutas)])
        return codigo, salida.getvalue()

    def test_SRSL01_resella_sin_cambiar_el_contenido_salvo_el_sello(self):
        """REQ-DAT-02: un archivo sellado con la clave de desarrollo se copia a sellados_1.0 con la clave real."""
        origen = self.crear('a.grafnet', CLAVE_DESARROLLO)
        antes = origen.read_bytes()
        codigo, texto = self.ejecutar(origen)
        destino = self.dir / 'sellados_1.0' / 'a.grafnet'
        self.assertEqual(codigo, 0)
        self.assertEqual(origen.read_bytes(), antes, 'el original no se toca')
        nuevo = destino.read_bytes()
        self.assertTrue(sello_valido(nuevo, self.clave))
        self.assertFalse(sello_valido(nuevo, CLAVE_DESARROLLO))
        e_antes, e_despues = entradas_de(antes), entradas_de(nuevo)
        sello_antes, sello_despues = e_antes.pop(SELLO), e_despues.pop(SELLO)
        self.assertEqual(e_antes, e_despues)
        self.assertNotEqual(sello_antes, sello_despues)
        self.assertIn('1 resellados', texto)

    def test_SRSL02_ya_sellado_para_la_distribucion_no_hace_nada(self):
        """REQ-DAT-02: con la clave real ya válida, se informa y no se escribe nada."""
        origen = self.crear('b.grafnet', self.clave)
        codigo, texto = self.ejecutar(origen)
        self.assertEqual(codigo, 0)
        self.assertIn('ya sellado para la distribución', texto)
        self.assertFalse((self.dir / 'sellados_1.0').exists())

    def test_SRSL03_sello_no_valido_no_se_toca(self):
        """REQ-DAT-02: un sello válido con otra clave, o roto, no se resella ni se copia."""
        ajeno = self.crear('c.grafnet', os.urandom(32))
        roto = self.dir / 'd.grafnet'
        roto.write_bytes(b'no es un zip')
        antes = (ajeno.read_bytes(), roto.read_bytes())
        codigo, texto = self.ejecutar(self.dir)
        self.assertEqual(codigo, 1)
        self.assertIn('c.grafnet: sello no válido: no se toca', texto)
        self.assertEqual((ajeno.read_bytes(), roto.read_bytes()), antes)
        self.assertFalse((self.dir / 'sellados_1.0').exists())

    def test_SRSL04_carpeta_no_recursiva_y_destino_existente_se_sustituye(self):
        """REQ-DAT-02: una carpeta aporta sus .grafnet directos; repetir sustituye la copia anterior."""
        self.crear('e.grafnet', CLAVE_DESARROLLO)
        sub = self.dir / 'sub'
        sub.mkdir()
        guardar_grafnet(sub / 'f.grafnet', self.proyecto, CLAVE_DESARROLLO).cerrar()
        destino = self.dir / 'sellados_1.0' / 'e.grafnet'
        destino.parent.mkdir()
        destino.write_bytes(b'copia antigua')
        self.ejecutar(self.dir)
        self.assertTrue(sello_valido(destino.read_bytes(), self.clave))
        self.assertFalse((sub / 'sellados_1.0').exists())
        self.assertEqual(sorted(p.name for p in destino.parent.iterdir()), ['e.grafnet'])

    def test_SRSL05_clave_corta_se_rechaza_y_nunca_se_imprime(self):
        """REQ-DAT-02: la clave debe tener 32 bytes como mínimo y no aparece en la salida."""
        corta = self.root / 'corta.bin'
        corta.write_bytes(b'corta')
        origen = self.crear('g.grafnet', CLAVE_DESARROLLO)
        codigo, texto = self.ejecutar(origen, clave=corta)
        self.assertEqual(codigo, 2)
        self.assertFalse((self.dir / 'sellados_1.0').exists())
        codigo, texto = self.ejecutar(origen)
        self.assertNotIn(self.clave.hex(), texto)
        self.assertNotIn(self.clave.decode('latin-1'), texto)


@unittest.skipUnless(QT, 'requiere PySide6')
class DialogoPropiedades(BaseQt):
    def tearDown(self):
        self.w.hide()
        super().tearDown()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def propiedades(self):
        return pa.recopilar(self.w.edicion)

    def guardar(self, nombre='p.grafnet'):
        destino = Path(self.tmp.name) / nombre
        with patch('escritorio.archivos.QFileDialog.getSaveFileName', return_value=(str(destino), '')):
            self.assertTrue(self.w.guardar_como())
        return destino

    def escribir_autor(self, texto):
        def exec_(dialogo):
            dialogo.c_autor.setText(texto)
        with patch.object(pa.PropiedadesArchivo, 'exec', exec_):
            pa.abrir(self.w)

    def test_SPRP20_proyecto_nuevo_se_sellara_al_guardar_y_toma_el_usuario_como_autor(self):
        """REQ-DAT-02: sin guardar no hay sello ni fechas; el autor por defecto es el usuario del sistema."""
        w, e = self.vacio()
        with patch.dict(os.environ, {'USERNAME': 'maria'}):
            d = self.propiedades()
            self.assertEqual((d.nombre, d.sello, d.autor), ('sin guardar', 'Se sellará al guardar', 'maria'))
        with patch.dict(os.environ, {'USERNAME': ''}), patch.object(pa.getpass, 'getuser', return_value='respaldo'):
            self.assertEqual(pa.autor_por_defecto(), 'respaldo')
        with patch.dict(os.environ, {'USERNAME': ''}), patch.object(pa.getpass, 'getuser', side_effect=OSError):
            self.assertEqual(pa.autor_por_defecto(), '')

    def test_SPRP21_cambiar_el_autor_marca_modificado_lo_guarda_y_lo_recuerda(self):
        """REQ-DAT-02: el autor cambia en el diálogo, marca el asterisco y viaja en info.json."""
        w, e = self.vacio()
        e.ed.add_step('g', '1', True)
        e.cambia()
        destino = self.guardar()
        self.assertFalse(e.ed.dirty)
        self.escribir_autor('Luis')
        self.assertTrue(e.ed.dirty)
        self.assertIn(' *', w.windowTitle())
        self.assertTrue(w.guardar_proyecto())
        self.assertEqual(inspeccionar(destino.read_bytes())[0]['autor'], 'Luis')
        self.escribir_autor('Luis')
        self.assertFalse(e.ed.dirty)

    def test_SPRP22_proyecto_guardado_muestra_sello_algoritmo_huella_y_programa(self):
        """REQ-DAT-02: el diálogo informa del sello vigente, la huella agrupada y el programa, sin clave."""
        w, e = self.vacio()
        e.ed.add_step('g', '1', True)
        e.cambia()
        self.guardar()
        d = self.propiedades()
        self.assertTrue(d.sello.startswith('Válido: sellado con la clave de esta versión de GRAFCET Connect'))
        self.assertEqual(d.algoritmo, 'HMAC-SHA256')
        grupos = d.huella.split(' ')
        self.assertEqual([len(g) for g in grupos], [4, 4, 4, 4])
        self.assertEqual(d.version_creacion, APP_VERSION)
        self.assertEqual(d.formato, '1')
        self.assertIn(f'GRAFCET Connect {VERSION}', d.programa)
        self.assertNotIn(CLAVE.hex(), repr(d))
        if not pa.EMPAQUETADO:
            self.assertEqual(d.instalado, 'versión de desarrollo, sin instalar')

    def test_SPRP23_archivo_anterior_muestra_desconocida(self):
        """REQ-DAT-02: un archivo sin info.json abre y el diálogo dice «desconocida (archivo anterior a la 1.0)»."""
        w, e = self.vacio()
        raiz = Path(self.tmp.name) / 'raiz'
        save_project(raiz, proyecto_de_prueba())
        antiguo = Path(self.tmp.name) / 'antiguo.grafnet'
        antiguo.write_bytes(empaquetar(raiz, CLAVE))
        self.assertTrue(w.abrir_ruta(antiguo))
        d = self.propiedades()
        self.assertEqual(d.version_creacion, pa.ANTIGUO)
        self.assertEqual(d.creado, pa.ANTIGUO)
        self.assertEqual(d.nombre, 'antiguo.grafnet')
        self.assertTrue(d.sello.startswith('Válido'))


if __name__ == '__main__':
    unittest.main()
