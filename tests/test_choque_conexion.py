"""SCHC01..SCHC02: la herramienta de choque de la conexión (`tools/choque_conexion.py`, V2-E7 paso 4) funciona: una secuencia corta pasa y un defecto
inyectado (el hilo de control no se para) se detecta. Se omiten si falta PySide6."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

try:
    import PySide6  # noqa: F401
    QT = True
except ImportError:
    QT = False

ENTORNO = dict(os.environ, QT_QPA_PLATFORM="offscreen", GRAFCONNECT_SIN_ACTUALIZAR="1", PYTHONIOENCODING="utf-8")
if Path("C:/Windows/Fonts").is_dir():
    ENTORNO.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

DEFECTO = """
import sys
sys.path.insert(0, ".")
from tools import choque_conexion as c
from conexion.ciclo import CicloES
CicloES.parar = lambda self: None  # defecto inyectado: el hilo no se para
f = c.ejecutar("gemma", c.generar(13, 12))
print("TIPO", f.tipo if f else None)
"""


@unittest.skipUnless(QT, "requiere PySide6")
class ChoqueConexion(unittest.TestCase):
    def correr(self, *args, **kw):
        return subprocess.run([sys.executable, "-X", "faulthandler", *args], cwd=RAIZ, env=ENTORNO, capture_output=True, text=True, timeout=240, **kw)

    def test_SCHC01_una_secuencia_corta_con_conexion_no_da_fallos(self):
        """REQ-SIM-03: 12 operaciones al azar (conectar, Play, ediciones, mapa en vivo, red cortada...) con la guarda de hilos no dan fallos
        ni dejan hilos vivos al cerrar la ventana."""
        r = self.correr("tools/choque_conexion.py", "--proyecto", "gemma", "--semilla", "13", "--ops", "12")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sin fallos", r.stdout)

    def test_SCHC02_un_hilo_de_control_que_no_se_para_se_detecta(self):
        """REQ-SIM-03: si al desconectar el hilo de control sigue vivo, la herramienta lo dice (CON-2 o CON-3)."""
        r = self.correr("-c", DEFECTO)
        self.assertIn("TIPO CON-", r.stdout, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
