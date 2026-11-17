"""Presión de streams C equivalente a las 509 aperturas de fuentes observadas."""
import ctypes
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFont, QFontMetrics
from tools import hoja_contactos as hc


def main():
    app = hc.aplicacion()
    crt = ctypes.CDLL("ucrtbase")
    crt.fopen.argtypes = (ctypes.c_char_p, ctypes.c_char_p)
    crt.fopen.restype = ctypes.c_void_p
    crt.fclose.argtypes = (ctypes.c_void_p,)
    streams = []
    try:
        for numero in range(509):
            stream = crt.fopen(b"NUL", b"r")
            assert stream, f"Sin capacidad para la apertura {numero + 1}"
            streams.append(stream)
        fuente = QFont("Segoe UI")
        fuente.setPixelSize(11)
        fm = QFontMetrics(fuente)
        estrecha = fm.horizontalAdvance("iiii")
        ancha = fm.horizontalAdvance("WWWW")
        assert estrecha < ancha, "Se pierden las métricas reales con la presión de fuentes observada"
        resultado = {"limite": crt._getmaxstdio(), "aperturas_simuladas": len(streams),
                     "estrecha": estrecha, "ancha": ancha}
    finally:
        for stream in streams:
            crt.fclose(stream)
    print(json.dumps(resultado))
    app.processEvents()


if __name__ == "__main__":
    main()
