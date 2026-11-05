"""Clave de sello de esta distribución; la clave real se incorpora solo en el área temporal de construcción."""
import hashlib

CLAVE_DESARROLLO = hashlib.sha256(b'GrafConnect clave publica de desarrollo v1').digest()
try:
    from ._clave_sello import CLAVE
    DESARROLLO = False
except ModuleNotFoundError as exc:
    if exc.name != __package__+'._clave_sello':raise
    CLAVE = CLAVE_DESARROLLO
    DESARROLLO = True

POLITICA_SELLO = "rechazar"
