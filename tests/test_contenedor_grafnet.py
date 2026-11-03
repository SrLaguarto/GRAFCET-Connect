"""Contenedor .grafnet, integridad y preparación de claves."""
import copy
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from grafcet.contenedor import empaquetar,extraer,guardar_atomico,ErrorContenedor,SELLO,VERSION
from grafcet.editor import Editor,new_grafcet_document
from grafcet.persistence import save_project,new_project,add_document,open_project
from escritorio.sello import CLAVE
from tools.clave_construccion import obtener_clave,fuentes_aisladas,ErrorClave


class Contenedores(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.proyecto=self.root/'original'
        e=Editor(new_grafcet_document('m'));e.add_step('g','1',True)
        e.add_annotation('text',(20,30),text='Nota',font='Arial',size=20,color='#326dcb')
        e.add_annotation('image',(200,30),data='data:image/png;base64,aW1hZ2Vu',width=80,height=40)
        p=new_project('p','Proyecto');add_document(p,e.model);add_document(p,e.presentation);save_project(self.proyecto,p)
        (self.proyecto/'conexion-factoryio.json').write_text('{"host":"192.168.1.133"}',encoding='utf-8')
        (self.proyecto/'recursos').mkdir();(self.proyecto/'recursos'/'foto.jpg').write_bytes(b'imagen original')
    def tearDown(self):self.tmp.cleanup()
    def cambiar(self,datos,fn):
        with zipfile.ZipFile(io.BytesIO(datos)) as z:contenido={n:z.read(n) for n in z.namelist()}
        fn(contenido);out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for n,b in contenido.items():z.writestr(n,b)
        return out.getvalue()
    def test_SGFN01_ida_vuelta_preserva_json_notas_imagenes_y_es(self):
        """REQ-DAT-01, REQ-DAT-02: el contenedor conserva byte a byte todos los documentos y recursos del proyecto."""
        datos=empaquetar(self.proyecto,CLAVE);dst=self.root/'abierto';self.assertTrue(extraer(datos,dst,CLAVE,'rechazar'))
        for p in self.proyecto.rglob('*'):
            if p.is_file():self.assertEqual(p.read_bytes(),(dst/p.relative_to(self.proyecto)).read_bytes())
        self.assertEqual(open_project(dst).documents,open_project(self.proyecto).documents)
    def test_SGFN02_fallo_atomico_conserva_archivo_anterior_y_limpia_temporal(self):
        """REQ-DAT-01: un fallo al sustituir no modifica el archivo anterior ni deja temporales."""
        dst=self.root/'proyecto.grafnet';dst.write_bytes(b'anterior')
        for operacion in ('replace','fsync'):
            with patch('grafcet.contenedor.os.'+operacion,side_effect=OSError('fallo simulado')):
                with self.assertRaises(OSError):guardar_atomico(dst,b'nuevo')
        self.assertEqual(dst.read_bytes(),b'anterior');self.assertFalse(list(self.root.glob('.*.tmp')))
    def test_SGFN03_sello_rechaza_modificado_sin_sello_otra_clave_y_manual(self):
        """REQ-DAT-01, REQ-DAT-02: contenido alterado, sin sello, de otra edición o hecho a mano no se acepta como válido."""
        datos=empaquetar(self.proyecto,CLAVE)
        alterado=self.cambiar(datos,lambda e:e.__setitem__(next(n for n in e if n.startswith('model-')),b'{"cambiado":true}'))
        sin=self.cambiar(datos,lambda e:e.pop(SELLO))
        manual=self.cambiar(datos,lambda e:[e.pop(k) for k in list(e) if k==SELLO or k.startswith('model-')])
        for i,(d,k) in enumerate(((alterado,CLAVE),(sin,CLAVE),(datos,b'x'*32),(manual,CLAVE))):
            with self.subTest(i=i),self.assertRaises(ErrorContenedor):extraer(d,self.root/str(i),k,'rechazar')
            self.assertFalse((self.root/str(i)).exists())
        self.assertFalse(extraer(sin,self.root/'importado',CLAVE,'importar'))
    def test_SGFN04_rutas_peligrosas_y_version_no_compatible_se_rechazan(self):
        """REQ-DAT-02: ni una importación autorizada admite rutas que escapen o una versión desconocida."""
        datos=empaquetar(self.proyecto,CLAVE)
        for nombre in ('../fuera','C:/fuera','a\\b'):
            mal=self.cambiar(datos,lambda e:e.__setitem__(nombre,b'x'))
            if nombre == 'a\\b':mal=mal.replace(b'a/b',b'a\\b')
            with self.assertRaises(ErrorContenedor):extraer(mal,self.root/'destino',CLAVE,'importar')
        mal=self.cambiar(datos,lambda e:e.__setitem__(VERSION,b'{"format":"grafnet","version":99}'))
        with self.assertRaises(ErrorContenedor):extraer(mal,self.root/'destino',CLAVE,'importar')
    def test_SGFN07_construccion_exige_clave_y_no_deja_modulo_en_repositorio(self):
        """REQ-DAT-02: sin clave se rechaza repartir; la clave se genera y elimina fuera del árbol de trabajo, incluso al fallar."""
        repo=Path(__file__).resolve().parents[1]
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ErrorClave):obtener_clave(repo)
            self.assertIsNone(obtener_clave(repo,desarrollo=True))
        destino=None
        with self.assertRaises(RuntimeError):
            with fuentes_aisladas(repo,b'z'*32) as area:
                destino=area;self.assertFalse(area.is_relative_to(repo));self.assertTrue((area/'escritorio'/'_clave_sello.py').exists())
                raise RuntimeError('fallo de construcción')
        self.assertFalse(destino.exists());self.assertFalse((repo/'escritorio'/'_clave_sello.py').exists())

    def test_SGFN16_construccion_real_sin_clave_no_invoca_compilador(self):
        """REQ-DAT-02: la orden de construcción se niega sin clave antes de llamar al empaquetador."""
        import contextlib
        from tools import construir_ejecutable as build
        with patch.dict(os.environ,{},clear=True),patch.object(build.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()) as salida:
            self.assertEqual(build.main([]),1);run.assert_not_called()
        self.assertIn('requiere una clave',salida.getvalue())
    def test_SGFN17_conversion_conserva_modelos_y_escenarios_adicionales(self):
        """REQ-DAT-02: abrir y guardar un contenedor conserva todos sus documentos, no solo el modelo editable."""
        from escritorio.proyecto_archivo import guardar_grafnet,abrir_grafnet
        proyecto=open_project(self.proyecto)
        segundo=Editor(new_grafcet_document('segundo'));segundo.add_step('g','9',True);add_document(proyecto,segundo.model)
        dst=self.root/'convertido.grafnet';archivo=guardar_grafnet(dst,proyecto,CLAVE,self.proyecto)
        try:
            self.assertEqual(len(archivo.proyecto.models()),2)
            abierto=abrir_grafnet(dst,CLAVE,'rechazar')
            try:
                self.assertEqual(abierto.proyecto.documents,archivo.proyecto.documents)
                self.assertEqual((abierto.raiz/'recursos'/'foto.jpg').read_bytes(),b'imagen original')
            finally:abierto.cerrar()
        finally:archivo.cerrar()
    def test_SGFN18_nuitka_ausente_no_instala_ni_cambia_de_via(self):
        """REQ-DAT-02: si no hay Nuitka se informa y no se sustituye silenciosamente la construcción elegida."""
        import contextlib
        from tools import construir_ejecutable as build
        with patch.dict(os.environ,{},clear=True),patch.object(build.importlib.util,'find_spec',return_value=None),patch.object(build.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()) as salida:
            self.assertEqual(build.main(['--desarrollo','--motor','nuitka']),1);run.assert_not_called()
        self.assertIn('Nuitka no está instalado',salida.getvalue())
