"""Capacidad de fuentes para procesos de pruebas Qt offscreen en Windows."""
import ctypes
import os

LIMITE_STREAMS_FUENTES = 8192
_crt = None


def preparar_fuentes_offscreen():
    global _crt
    plataforma = os.environ.get("QT_QPA_PLATFORM", "").partition(":")[0]
    if os.name != "nt" or plataforma != "offscreen":
        return None
    if _crt is None:
        _crt = ctypes.CDLL("ucrtbase", use_errno=True)
        _crt._getmaxstdio.argtypes = ()
        _crt._getmaxstdio.restype = ctypes.c_int
        _crt._setmaxstdio.argtypes = (ctypes.c_int,)
        _crt._setmaxstdio.restype = ctypes.c_int
    actual = _crt._getmaxstdio()
    if actual < LIMITE_STREAMS_FUENTES:
        resultado = _crt._setmaxstdio(LIMITE_STREAMS_FUENTES)
        if resultado != LIMITE_STREAMS_FUENTES:
            raise OSError(ctypes.get_errno(), "No se pudo preparar la capacidad de fuentes del banco Qt")
    return _crt._getmaxstdio()
