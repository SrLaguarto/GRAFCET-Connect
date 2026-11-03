"""Clave de sello de esta distribución; la clave real se incorpora solo en el área temporal de construcción."""
import hashlib
try:
    from ._clave_sello import CLAVE
    DESARROLLO = False
except ModuleNotFoundError as exc:
    if exc.name != __package__+'._clave_sello':raise
    CLAVE = hashlib.sha256(b'GrafConnect clave publica de desarrollo v1').digest()
    DESARROLLO = True

POLITICA_SELLO = "rechazar"
