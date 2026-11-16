"""SM1: activación del servidor web, siempre con Documentos temporales."""
import builtins
import codecs
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from conexion import servidor_web_simulador as servidor
from escritorio import arranque_servidor_web as arranque


class ArchivosServidor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.docs = Path(self.tmp.name)
        self.parche = patch.object(servidor, "documentos_usuario", return_value=self.docs)
        self.parche.start()
        self.addCleanup(self.parche.stop)

    def firma(self, nombre="planta"):
        carpeta = self.docs / nombre
        (carpeta / "My Scenes").mkdir(parents=True)
        (carpeta / "CertificatesStore").mkdir()
        return carpeta

    def test_SM101_firma_directa_ninguna_y_varias(self):
        self.assertIsNone(servidor.buscar_carpeta())
        self.assertEqual(servidor.estado(), "sin_carpeta")
        incompleta = self.docs / "otra"
        (incompleta / "My Scenes").mkdir(parents=True)
        self.assertIsNone(servidor.buscar_carpeta())
        carpeta = self.firma()
        self.assertEqual(servidor.buscar_carpeta(), carpeta)
        self.assertEqual(servidor.estado(), "falta")
        (carpeta / "Screenshots").mkdir()
        self.assertEqual(servidor.buscar_carpeta(), carpeta)
        self.firma("segunda")
        self.assertEqual(servidor.estado(), "varias")
        self.assertFalse(servidor.activar().correcto)
        self.assertFalse(any(self.docs.rglob("auto.cfg")))

    def test_SM102_no_busca_firmas_anidadas(self):
        self.firma("contenedor/planta")
        self.assertEqual(servidor.estado(), "sin_carpeta")
        self.assertFalse(servidor.activar().correcto)

    def test_SM103_crear_crlf_y_no_reescribir_si_ya_activo(self):
        f = self.firma() / "auto.cfg"
        self.assertTrue(servidor.activar().cambiado)
        self.assertEqual(f.read_bytes(), b"app.web_server = True\r\n")
        marca = f.stat().st_mtime_ns
        with patch.object(servidor.os, "replace") as reemplazar:
            self.assertTrue(servidor.activar().correcto)
            reemplazar.assert_not_called()
        self.assertEqual(f.stat().st_mtime_ns, marca)
        self.assertEqual(servidor.estado(), "activo")

    def test_SM104_true_con_espacios_mayusculas_y_comentario_intacto(self):
        f = self.firma() / "auto.cfg"
        datos = b"# caf\xe9\n  APP . WEB_SERVER = tRuE  # manual\n"
        f.write_bytes(datos)
        self.assertEqual(servidor.estado(), "activo")
        self.assertFalse(servidor.activar().cambiado)
        self.assertEqual(f.read_bytes(), datos)

    def test_SM105_otro_valor_solo_cambia_su_valor(self):
        f = self.firma() / "auto.cfg"
        datos = b"otra = 42\r\n\tApp.web_server  = False  # comentario\r\nultima = 3\n"
        f.write_bytes(datos)
        self.assertTrue(servidor.activar().correcto)
        self.assertEqual(f.read_bytes(), datos.replace(b"False", b"True"))

    def test_SM106_sin_linea_y_sin_salto_final(self):
        f = self.firma() / "auto.cfg"
        for datos, esperado in ((b"otra=1\n", b"otra=1\napp.web_server = True\n"),
                                (b"otra=1", b"otra=1\r\napp.web_server = True\r\n"),
                                (b"# caf\xe9\r\notra=1", b"# caf\xe9\r\notra=1\r\napp.web_server = True\r\n")):
            f.write_bytes(datos)
            self.assertTrue(servidor.activar().correcto)
            self.assertEqual(f.read_bytes(), esperado)

    def test_SM107_varias_asignaciones_todas_true_sin_borrar_lineas(self):
        f = self.firma() / "auto.cfg"
        for segundo in (b"False", b"True", b"tRuE"):
            datos = b"# app.web_server = False\r\napp.web_server=False # primero\nOTRA=3\r\n"
            datos += b"APP . WEB_SERVER = " + segundo + b"  # segundo"
            f.write_bytes(datos)
            esperado = datos.replace(b"=False # primero", b"=True # primero")
            if segundo == b"False":
                esperado = esperado.replace(b"= False  # segundo", b"= True  # segundo")
            self.assertTrue(servidor.activar().correcto)
            self.assertEqual(f.read_bytes(), esperado)
            self.assertEqual(servidor.estado(), "activo")

    def test_SM108_codificaciones_y_finales_mixtos(self):
        f = self.firma() / "auto.cfg"
        texto = "# café\r\napp.web_server = False\nvalor = 'ñ'\r\n"
        for bom, encoding in ((b"", "utf-8"), (b"", "cp1252"), (codecs.BOM_UTF8, "utf-8"),
                              (codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be"),
                              (codecs.BOM_UTF32_LE, "utf-32-le"), (codecs.BOM_UTF32_BE, "utf-32-be")):
            datos = bom + texto.encode(encoding)
            f.write_bytes(datos)
            self.assertTrue(servidor.activar().correcto)
            self.assertEqual(f.read_bytes(), bom + texto.replace("False", "True").encode(encoding))

    def test_SM109_permiso_y_reemplazo_fallido_no_danan_original(self):
        carpeta = self.firma()
        f = carpeta / "auto.cfg"
        datos = b"app.web_server=False\r\n# resto\r\n"
        f.write_bytes(datos)
        for objeto, nombre in ((servidor.tempfile, "NamedTemporaryFile"), (servidor.os, "replace")):
            with patch.object(objeto, nombre, side_effect=PermissionError("Sin permiso")):
                resultado = servidor.activar()
            self.assertFalse(resultado.correcto)
            self.assertIn("Sin permiso", resultado.motivo)
            self.assertEqual(f.read_bytes(), datos)
            self.assertFalse(list(carpeta.glob(".auto-*.tmp")))

    def test_SM110_codificacion_desconocida_no_se_mezcla(self):
        f = self.firma() / "auto.cfg"
        datos = b"a\x00p\x00p\x00"
        f.write_bytes(datos)
        self.assertFalse(servidor.activar().correcto)
        self.assertEqual(f.read_bytes(), datos)

    def test_SM111_arranque_sin_ventana_instancia_ni_actualizaciones(self):
        importar = builtins.__import__
        def vigilar(nombre, *args, **kwargs):
            if nombre in ("escritorio.ventana", "escritorio.instancia_unica", "escritorio.actualizaciones"):
                raise AssertionError("El modo oculto no debe cargar " + nombre)
            return importar(nombre, *args, **kwargs)
        for correcto, codigo in ((True, 0), (False, 2)):
            with patch.object(servidor, "activar", return_value=servidor.Resultado(correcto, "prueba")) as activar:
                with patch.object(sys, "argv", ["simulador.py", arranque.ARGUMENTO]):
                    with patch("builtins.__import__", side_effect=vigilar), self.assertRaises(SystemExit) as salida:
                        runpy.run_path(str(ROOT / "escritorio/simulador.py"), run_name="__main__")
            self.assertEqual(salida.exception.code, codigo)
            activar.assert_called_once_with(None)

    def test_SM112_ruta_del_instalador_y_prueba_segura(self):
        carpeta = self.firma()
        self.assertEqual(arranque.despachar([arranque.ARGUMENTO], self.docs), 0)
        self.assertTrue((carpeta / "auto.cfg").exists())
        resultado = subprocess.run([sys.executable, str(ROOT / "escritorio/simulador.py"), arranque.PRUEBA],
                                  capture_output=True, timeout=15, env={**os.environ, "QT_QPA_PLATFORM": "sin_gui"})
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_SM113_instalador_tarea_originaluser_y_sin_desinstalacion(self):
        texto = (ROOT / "tools/instalador.iss").read_text(encoding="utf-8")
        tarea = next(l for l in texto.splitlines() if l.startswith('Name: "servidorweb";'))
        self.assertNotIn("unchecked", tarea)
        self.assertIn('GroupDescription: "Conexión directa:"', tarea)
        run = next(l for l in texto.splitlines() if 'Parameters: "' + arranque.ARGUMENTO in l)
        flags = next(l for l in texto.splitlines() if l.startswith("#define FlagsServidorWeb "))
        run = run.replace("{#FlagsServidorWeb}", flags.split(chr(34))[1])
        for regla in ("runasoriginaluser", "runhidden", "waituntilterminated", "Tasks: servidorweb"):
            self.assertIn(regla, run)
        self.assertNotIn("auto.cfg", texto)


    @unittest.skipUnless(os.name == "nt", "resolución de Documentos en Windows")
    def test_SM122_documentos_redirigidos_resueltos_por_windows(self):
        def redirigir(ventana, carpeta, token, flags, buffer):
            self.assertEqual(carpeta, 5)
            buffer.value = str(self.docs)
            return 0
        self.parche.stop()
        with patch.object(servidor.ctypes.windll.shell32, "SHGetFolderPathW", side_effect=redirigir):
            self.assertEqual(servidor.documentos_usuario(), self.docs)
        self.parche.start()

    def test_SM123_no_toca_otra_orden_en_la_misma_linea(self):
        f = self.firma() / "auto.cfg"
        datos = b"app.web_server=False; otra=3 # conservar\r\n"
        f.write_bytes(datos)
        self.assertTrue(servidor.activar().correcto)
        self.assertEqual(f.read_bytes(), datos.replace(b"False", b"True"))


if __name__ == "__main__":
    unittest.main()
