"""Construye la versión portable para Windows del simulador de escritorio (P-IMP-29).

Uso:  python tools/construir_ejecutable.py
      o doble clic en «Construir ejecutable.bat»

Resultado: dist/GRAFCET/GRAFCET.exe con sus bibliotecas al lado (modo carpeta de PyInstaller, sin instalador).
La carpeta dist/GRAFCET entera es el programa: se copia donde se quiera y se abre GRAFCET.exe. Las bibliotecas de
Qt (LGPL v3) quedan como ficheros separados y sustituibles. Necesita PySide6-Essentials y pyinstaller (PyPI).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
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
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode:
        return r.returncode
    dist = ROOT / "dist" / NOMBRE
    shutil.copy(ROOT / "escritorio" / "LEEME.txt", dist / "LEEME.txt")
    size = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    print(f"\nListo: {dist / (NOMBRE + '.exe')}  ({size / 1e6:.0f} MB en la carpeta)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
