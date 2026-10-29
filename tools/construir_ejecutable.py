"""Construye la versión portable para Windows del simulador de escritorio (P-IMP-29).

Uso:  python tools/construir_ejecutable.py
      o doble clic en «Construir ejecutable.bat»

Resultado: dist/GRAFCET/GRAFCET.exe con sus bibliotecas al lado (modo carpeta de PyInstaller, sin instalador).
La carpeta dist/GRAFCET entera es el programa: se copia donde se quiera y se abre GRAFCET.exe. Las bibliotecas de
Qt (LGPL v3) quedan como ficheros separados y sustituibles. Necesita PySide6-Essentials y pyinstaller (PyPI).
"""
from __future__ import annotations

import shutil
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOMBRE = "GRAFCET"
# Del Qt completo solo se usan QtCore, QtGui y QtWidgets; el resto no se empaqueta
EXCLUIR = ["tkinter", "unittest", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf",
           "PySide6.QtSvg", "PySide6.QtOpenGL", "PySide6.QtMultimedia", "PySide6.QtWebEngineCore"]


def main() -> int:
    work = ROOT / "build"
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
            "--name", NOMBRE, "--paths", str(ROOT), "--distpath", str(ROOT / "dist"), "--workpath", str(work),
            "--specpath", str(work), *[f"--exclude-module={m}" for m in EXCLUIR],
            str(ROOT / "escritorio" / "simulador.py")]
    print(" ".join(args), flush=True)
    # PATH de herramientas ajenas puede contener DLL con el mismo nombre y otra ABI
    # (p. ej. icuuc.dll de Poppler). Qt usa la ICU de Windows. La compilación solo
    # necesita el intérprete actual y las herramientas del sistema, no ese PATH.
    env = os.environ.copy()
    windows = Path(env.get("SystemRoot", r"C:\Windows"))
    env["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent, windows / "System32", windows)))
    r = subprocess.run(args, cwd=ROOT, env=env)
    if r.returncode:
        return r.returncode
    dist = ROOT / "dist" / NOMBRE
    shutil.copy(ROOT / "escritorio" / "LEEME.txt", dist / "LEEME.txt")
    shutil.copytree(ROOT / "pruebas_manuales" / "factoryio_digital", dist / "prueba_factoryio_digital", dirs_exist_ok=True)
    shutil.copy(ROOT / "docs" / "PRIMERA_CONEXION_FACTORY_IO.md", dist / "PRIMERA_CONEXION_FACTORY_IO.md")
    # Un build correcto no basta: comprobar la carga de Qt y el dibujo en el EXE.
    with tempfile.TemporaryDirectory(prefix="grafcet-arranque-") as tmp:
        captura = Path(tmp) / "arranque.png"
        prueba_env = {**env, "QT_QPA_PLATFORM": "offscreen", "QT_QPA_FONTDIR": str(windows / "Fonts")}
        try:
            prueba = subprocess.run([str(dist / (NOMBRE + ".exe")), "--ejemplo", "repeticion", "--captura", str(captura)],
                                    cwd=dist, env=prueba_env, timeout=30)
        except subprocess.TimeoutExpired:
            print("ERROR: el ejecutable no completó la prueba de arranque en 30 s.", flush=True)
            return 1
        if prueba.returncode or not captura.is_file() or captura.stat().st_size == 0:
            print("ERROR: el ejecutable no pudo arrancar y generar su captura.", flush=True)
            return 1
        print("Prueba de arranque del ejecutable superada (Qt y captura).", flush=True)
    size = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    print(f"\nListo: {dist / (NOMBRE + '.exe')}  ({size / 1e6:.0f} MB en la carpeta)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
