"""Propiedades del archivo en el ejecutable compilado (Nuitka): sys.executable apunta a un python.exe inexistente."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from escritorio import propiedades_archivo as pa


class PropiedadesEnEjecutable(unittest.TestCase):
    def test_SPEX01_fecha_de_instalacion_con_sys_executable_inexistente(self):
        """Con Nuitka, sys.executable no existe: la fecha sale del ejecutable real (sys.argv[0]) y no falla."""
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "GRAFCET Connect.exe"
            exe.write_bytes(b"MZ")
            with patch.object(pa, "EMPAQUETADO", True), patch.object(sys, "executable", str(Path(tmp) / "python.exe")),                     patch.object(sys, "argv", [str(exe)]):
                texto, instalado = pa.descripcion_programa()
        self.assertIn("GRAFCET Connect", texto)
        self.assertRegex(instalado, r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")

    def test_SPEX02_sin_ningun_ejecutable_localizable_no_falla(self):
        with patch.object(pa, "EMPAQUETADO", True), patch.object(sys, "executable", "Z:/no/existe/python.exe"),                 patch.object(sys, "argv", ["Z:/no/existe/GRAFCET Connect.exe"]):
            self.assertEqual(pa.descripcion_programa()[1], "desconocida")


if __name__ == "__main__":
    unittest.main()
