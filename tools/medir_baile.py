"""Medición reproducible del anclaje y del coste de redimensionar en Windows real.

python tools/medir_baile.py artifacts/baile/antes --capturas
Genera pasos.csv, pintados.csv y resumen.json. No modifica los ajustes del usuario.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import statistics
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["GRAFCONNECT_SIN_ACTUALIZAR"] = "1"

from PySide6.QtCore import QPoint, QPointF, QSettings  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if "--base" in sys.argv:
    import escritorio.diagrama as modulo_diagrama
    fuente = subprocess.check_output(["git", "show", "HEAD:escritorio/diagrama.py"], cwd=RAIZ)
    exec(compile(fuente, "escritorio/diagrama.py@HEAD", "exec"), modulo_diagrama.__dict__)

from escritorio.diagrama import VistaDiagrama  # noqa: E402
from escritorio.ventana import Ventana  # noqa: E402
from escritorio.anclaje import AnclajeVentana  # noqa: E402


def posicion(w, punto):
    d = w.diagrama
    v = d.viewport().mapTo(w, QPoint())
    p = d.viewport().mapTo(w, d.mapFromScene(punto))
    return {"vista_x": v.x(), "vista_y": v.y(), "punto_x": p.x(), "punto_y": p.y()}


class Medida:
    def __init__(self):
        self.tiempos = {}
        self.pintados = []
        self.paso = -1
        self.w = None
        self.punto = QPointF()
        self.activo = False
        self.referencia = {}
        self.pixeles = None

    def envolver(self, clase, nombre):
        original = getattr(clase, nombre)

        def medida(objeto, *args, **kwargs):
            if nombre == "paintEvent" and self.activo and objeto is self.w.diagrama:
                actual = posicion(self.w, self.punto)
                self.pintados.append({
                    "paso": self.paso, **actual,
                    "error_x": actual["punto_x"] - self.referencia["punto_x"],
                    "error_y": actual["punto_y"] - self.referencia["punto_y"],
                })
            inicio = perf_counter()
            try:
                return original(objeto, *args, **kwargs)
            finally:
                ms = (perf_counter() - inicio) * 1000
                clave = clase.__name__ + "." + nombre
                self.tiempos[clave] = self.tiempos.get(clave, 0) + ms

        return patch.object(clase, nombre, medida)


def win32_resize(w, ancho, alto):
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    exterior = wintypes.RECT()
    cliente = wintypes.RECT()
    for nombre, rectangulo in (("GetWindowRect", exterior), ("GetClientRect", cliente)):
        funcion = getattr(user32, nombre)
        funcion.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        funcion.restype = wintypes.BOOL
        if not funcion(int(w.winId()), ctypes.byref(rectangulo)):
            raise ctypes.WinError(ctypes.get_last_error())
    marco_x = exterior.right - exterior.left - cliente.right + cliente.left
    marco_y = exterior.bottom - exterior.top - cliente.bottom + cliente.top
    dpi = w.devicePixelRatioF()
    fisico_ancho = round(ancho * dpi) + marco_x
    fisico_alto = round(alto * dpi) + marco_y
    if not user32.SetWindowPos(int(w.winId()), None, 0, 0, fisico_ancho, fisico_alto,
                              0x0002 | 0x0004 | 0x0010):
        raise ctypes.WinError(ctypes.get_last_error())


def recorrido(paso, pantalla):
    anchos = list(range(1000, 2561, paso))
    altos = list(range(480, 1251, paso))
    for ancho in anchos + anchos[-2::-1]:
        yield "ancho", ancho, 1000
    for alto in altos + altos[-2::-1]:
        yield "alto", 1600, alto
    for ancho, alto in ((960, 1032), (1920, 1032), (1366, 768), (2000, 1250),
                        (pantalla.width() // 2, pantalla.height()), (pantalla.width(), pantalla.height())):
        yield "ajuste", ancho, alto


def escribir_csv(ruta, filas):
    campos = list(dict.fromkeys(k for fila in filas for k in fila))
    with ruta.open("w", newline="", encoding="utf-8-sig") as salida:
        escritor = csv.DictWriter(salida, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas)


def asentar():
    for _ in range(3):
        QApplication.processEvents()


def ejecutar_paso(w, metodo, familia, ancho, alto, medida, carpeta, capturas):
    medida.tiempos = {}
    medida.activo = True
    inicio = perf_counter()
    if familia == "maximizar":
        w.showMaximized()
    elif familia == "restaurar":
        w.showNormal()
    elif metodo == "resize":
        w.resize(ancho, alto)
    else:
        win32_resize(w, ancho, alto)
    if familia in ("escala_asentada", "maximizar", "restaurar"):
        QTest.qWait(180)
    asentar()
    w.diagrama.viewport().repaint()
    duracion = (perf_counter() - inicio) * 1000
    fila = {"paso": medida.paso, "modo": w.modo, "metodo": metodo, "familia": familia,
            "pedido_ancho": ancho, "pedido_alto": alto, "ancho": w.width(), "alto": w.height(),
            "escala": w._escala, "compacto": str(w._compacto), "zoom": w.diagrama.escala(),
            "cliente_pantalla_x": w.mapToGlobal(QPoint()).x(), "dpi": w.devicePixelRatioF(),
            **posicion(w, medida.punto), "paso_ms": duracion, **medida.tiempos}
    fila["error_x"] = fila["punto_x"] - medida.referencia["punto_x"]
    fila["error_y"] = fila["punto_y"] - medida.referencia["punto_y"]
    if capturas:
        capturar(w, fila, medida, carpeta)
    medida.activo = False
    return fila


def capturar(w, fila, medida, carpeta):
    x = medida.referencia["punto_x"]
    y = medida.referencia["punto_y"]
    imagen = w.screen().grabWindow(int(w.winId()), x - 8, y - 8, 32, 32).toImage()
    fila["captura_nula"] = imagen.isNull()
    pixeles = {(a, b) for a in range(imagen.width()) for b in range(imagen.height())
               if imagen.pixelColor(a, b).lightness() < 100}
    if medida.pixeles is None:
        medida.pixeles = pixeles
    fila["pixeles_distintos"] = len(pixeles.symmetric_difference(medida.pixeles))
    imagen.save(str(carpeta / f"punto_{medida.paso:05d}.png"))
    if fila["familia"] in ("ajuste", "maximizar", "restaurar"):
        w.screen().grabWindow(int(w.winId())).save(str(carpeta / f"ventana_{medida.paso:05d}.png"))


def resumen(filas, pintados, pantalla, modo_actualizacion, cache):
    grupos = {}
    for fila in filas:
        clave = "/".join((fila["modo"], fila["metodo"], fila["familia"]))
        grupos.setdefault(clave, []).append(fila)
    salida = {"plataforma": QApplication.platformName(), "pantalla": pantalla,
              "viewportUpdateMode": modo_actualizacion, "cacheMode": cache, "grupos": {},
              "error_maximo_pintado_x": max(abs(p["error_x"]) for p in pintados),
              "error_maximo_pintado_y": max(abs(p["error_y"]) for p in pintados)}
    for clave, grupo in grupos.items():
        tiempos = sorted(f["paso_ms"] for f in grupo)
        salida["grupos"][clave] = {
            "pasos": len(grupo),
            "rango_x": [min(f["punto_x"] for f in grupo), max(f["punto_x"] for f in grupo)],
            "rango_y": [min(f["punto_y"] for f in grupo), max(f["punto_y"] for f in grupo)],
            "mediana_ms": statistics.median(tiempos), "p95_ms": tiempos[int((len(tiempos) - 1) * .95)],
            "max_ms": max(tiempos),
        }
    salida["pintados"] = len(pintados)
    return salida


def barridos(w, args, medida, filas, pantalla):
    for modo in ("editar", "simular"):
        w.cambiar_modo(modo)
        if modo == "simular":
            w.rt.stop()
        for metodo in ("resize", "SetWindowPos"):
            w.resize(1366, 768)
            QTest.qWait(180)
            w.diagrama.zoom(1.1)
            w.diagrama._situar(medida.punto, QPointF(200, 180))
            w.diagrama._notificar()
            asentar()
            medida.referencia = posicion(w, medida.punto)
            medida.pixeles = None
            tamanos = list(recorrido(args.paso, pantalla))
            tamanos.extend((("maximizar", 0, 0), ("restaurar", 0, 0)))
            for familia, ancho, alto in tamanos:
                medida.paso += 1
                filas.append(ejecutar_paso(w, metodo, familia, ancho, alto, medida,
                                           args.carpeta, args.capturas))
                if familia == "ajuste":
                    medida.paso += 1
                    filas.append(ejecutar_paso(w, metodo, "escala_asentada", ancho, alto, medida,
                                               args.carpeta, args.capturas))
            print(modo, metodo, len(filas), "pasos", flush=True)


def medir(args):
    app = QApplication.instance() or QApplication([])
    if app.platformName() != "windows":
        raise RuntimeError("La medición requiere la plataforma windows, sin offscreen.")
    args.carpeta.mkdir(parents=True, exist_ok=True)
    filas = []
    medida = Medida()
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as pila:
        for clase, metodo in ((Ventana, "resizeEvent"), (Ventana, "_cambiar_escala"),
                              (Ventana, "_adaptar_tamano"), (Ventana, "_fusionar_filas"),
                              (AnclajeVentana, "restaurar"),
                              (VistaDiagrama, "resizeEvent"), (VistaDiagrama, "drawBackground"),
                              (VistaDiagrama, "paintEvent")):
            pila.enter_context(medida.envolver(clase, metodo))
        w = Ventana(QSettings(str(Path(tmp) / "medida.ini"), QSettings.Format.IniFormat))
        medida.w = w
        try:
            # Se carga un ejemplo real y se abre su copia editable, sin modificar archivos.
            w.cargar_ejemplo("temporizada")
            w._empezar_edicion(w._edicion_desde_fuente())
            w.resize(1366, 768)
            w.move(0, 0)
            w.show()
            QTest.qWait(700)
            paso = w.edicion.M["steps"][0]
            medida.punto = QPointF(paso["x"] + 100 - 20, paso["y"] - 20)
            pantalla = w.screen().availableGeometry()
            barridos(w, args, medida, filas, pantalla)
            resultado = resumen(filas, medida.pintados, pantalla.getRect(),
                                str(w.diagrama.viewportUpdateMode()), str(w.diagrama.cacheMode()))
        finally:
            medida.w = None
            w.a_ejecutar.setChecked(False)
            w.edicion = None
            w.close()
            w.deleteLater()
            asentar()
    escribir_csv(args.carpeta / "pasos.csv", filas)
    escribir_csv(args.carpeta / "pintados.csv", medida.pintados)
    (args.carpeta / "resumen.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("carpeta", type=Path)
    parser.add_argument("--paso", type=int, default=8)
    parser.add_argument("--capturas", action="store_true")
    parser.add_argument("--base", action="store_true", help="Usa diagrama.py de HEAD, sin alterar la copia de trabajo")
    medir(parser.parse_args())
