"""Construye la versión portable para Windows del simulador de escritorio (P-IMP-29).

Uso:  python tools/construir_ejecutable.py --archivo-clave RUTA   (repartible, Nuitka)
      python tools/construir_ejecutable.py --desarrollo           (clave pública, PyInstaller)

Resultado: «dist/GRAFCET Connect/GRAFCET Connect.exe» con sus bibliotecas al lado (modo carpeta, sin instalador).
Esa carpeta entera es el programa. Las bibliotecas de Qt (LGPL v3) quedan como ficheros separados y sustituibles.
Necesita PySide6-Essentials y Nuitka (o pyinstaller con --motor pyinstaller). La clave de distribución debe ser
la misma en todas las versiones: si cambia, los proyectos .grafnet guardados antes dejan de abrirse.
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOMBRE = "GRAFCET Connect"
sys.path.insert(0, str(ROOT))
from escritorio import VERSION  # noqa: E402  (la versión se define una sola vez, en escritorio/__init__.py)
ICONO = ROOT / "escritorio" / "recursos" / "grafcet_connect.ico"
try:
    from tools.clave_construccion import obtener_clave, fuentes_aisladas, ErrorClave
except ModuleNotFoundError:
    from clave_construccion import obtener_clave, fuentes_aisladas, ErrorClave
# QtSvg y QtPrintSupport se incluyen para exportar e imprimir láminas.
EXCLUIR = ["tkinter", "unittest", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf",
           "PySide6.QtOpenGL", "PySide6.QtMultimedia", "PySide6.QtWebEngineCore"]


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Construir GRAFCET Connect con su clave de sello")
    parser.add_argument("--archivo-clave",type=Path,help="Archivo de clave, fuera del repositorio (al menos 32 bytes)")
    parser.add_argument("--desarrollo",action="store_true",help="Construcción explícita con la clave pública de desarrollo")
    parser.add_argument("--motor",choices=("nuitka","pyinstaller"),help="Repartible: Nuitka por defecto; PyInstaller como alternativa. Desarrollo: PyInstaller por defecto.")
    opciones=parser.parse_args(argv)
    try:
        clave=obtener_clave(ROOT,opciones.archivo_clave,opciones.desarrollo)
    except ErrorClave as exc:
        print("ERROR:",str(exc),flush=True);return 1
    with fuentes_aisladas(ROOT,clave) as fuentes:
        return _construir(fuentes,clave,opciones.motor or ("pyinstaller" if opciones.desarrollo else "nuitka"))


def _construir(fuentes, clave, motor) -> int:
    repartible=clave is not None
    work = ROOT / "build"
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
            "--name", NOMBRE, "--paths", str(fuentes), "--distpath", str(ROOT / "dist"), "--workpath", str(work),
            "--specpath", str(work), "--collect-all=pypdfium2_raw", "--icon", str(ICONO),
            "--add-data", str(ICONO) + os.pathsep + "escritorio/recursos",
            *[f"--exclude-module={m}" for m in EXCLUIR],
            *(["--hidden-import=escritorio._clave_sello"] if repartible else []),
            str(fuentes / "escritorio" / "simulador.py")]
    if motor == "nuitka":
        if importlib.util.find_spec("nuitka") is None:
            print("ERROR: Nuitka no está instalado. No se ha instalado ni cambiado de vía automáticamente; puede elegir --motor pyinstaller.",flush=True)
            return 1
        args = [
            sys.executable, "-m", "nuitka", "--mode=standalone", "--enable-plugin=pyside6",
            "--assume-yes-for-downloads", "--windows-console-mode=disable",
            "--include-package-data=pypdfium2_raw", "--include-package-data=ezdxf",
            "--windows-icon-from-ico=" + str(ICONO),
            "--include-data-files=" + str(ICONO) + "=escritorio/recursos/grafcet_connect.ico",
            "--company-name=" + NOMBRE, "--product-name=" + NOMBRE,
            "--file-description=" + NOMBRE + ": editor y simulador GRAFCET",
            "--file-version=" + VERSION + ".0", "--product-version=" + VERSION + ".0",
            "--output-filename=" + NOMBRE + ".exe", "--output-dir=" + str(work / "nuitka"),
            *(["--include-module=escritorio._clave_sello"] if repartible else []),
            str(fuentes / "escritorio" / "simulador.py"),
        ]
    print(" ".join(args), flush=True)
    # PATH de herramientas ajenas puede contener DLL con el mismo nombre y otra ABI
    # (p. ej. icuuc.dll de Poppler). Qt usa la ICU de Windows. La compilación solo
    # necesita el intérprete actual y las herramientas del sistema, no ese PATH.
    env = os.environ.copy()
    env.pop("GRAFCONNECT_CLAVE_SELLO",None)
    windows = Path(env.get("SystemRoot", r"C:\Windows"))
    env["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent, windows / "System32", windows)))
    r = subprocess.run(args, cwd=ROOT, env=env)
    if r.returncode:
        return r.returncode
    dist = ROOT / "dist" / NOMBRE
    if motor == "nuitka":
        origen=work/"nuitka"/"simulador.dist"
        if not origen.is_dir():
            print("ERROR: Nuitka no generó la carpeta standalone esperada.",flush=True);return 1
        if dist.exists():
            if not dist.resolve().is_relative_to((ROOT/"dist").resolve()):raise ValueError("Destino de construcción no válido")
            shutil.rmtree(dist)
        shutil.copytree(origen,dist)
    shutil.copy(ROOT / "escritorio" / "LEEME.txt", dist / "LEEME.txt")
    # El ejemplo que se entrega también lleva el sello de la misma distribución.
    sys.path.insert(0,str(ROOT))
    from grafcet.contenedor import empaquetar,guardar_atomico
    from escritorio.sello import CLAVE as CLAVE_DESARROLLO
    guardar_atomico(dist/"Prueba-Modbus.grafnet",empaquetar(ROOT/"pruebas_manuales"/"factoryio_digital",clave if clave is not None else CLAVE_DESARROLLO))
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
        try:
            archivo=subprocess.run([str(dist/(NOMBRE+".exe")),"--prueba-contenedor"],cwd=dist,env=prueba_env,timeout=30)
        except subprocess.TimeoutExpired:
            print("ERROR: el ejecutable no completó la comprobación de ZIP y sello.",flush=True);return 1
        if archivo.returncode:
            print("ERROR: falló ZIP o sello en el ejecutable empaquetado.",flush=True);return 1
        print("Contenedor y sello del ejecutable comprobados.",flush=True)
    size = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    print(f"\nListo: {dist / (NOMBRE + '.exe')}  ({size / 1e6:.0f} MB en la carpeta)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
