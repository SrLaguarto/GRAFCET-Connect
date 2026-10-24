"""Identidades, etiquetas y nombres de fichero (documento 09, REQ-MOD-01, REQ-DAT-01, REQ-PLT-02)."""
from __future__ import annotations

import re
import unicodedata
import uuid

ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
MAX_LABEL = 256
MAX_FILENAME_BYTES = 255  # límite habitual por componente (NTFS, ext4, APFS); hallazgo H-12


def valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value))


def has_lone_surrogate(text: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def valid_label(value: object) -> bool:
    if not isinstance(value, str) or has_lone_surrogate(value):
        return False
    return 1 <= len(value) <= MAX_LABEL


def label_key(label: str) -> str:
    """Clave de unicidad de etiqueta: NFC y sensible a mayúsculas."""
    return unicodedata.normalize("NFC", label)


def id_hex(identifier: str) -> str:
    return identifier.encode("ascii").hex()


def document_filename(family: str, identifier: str) -> str:
    """Nombre interno: familia + '-' + bytes ASCII del ID en hexadecimal minúsculo (P-IMP-03)."""
    return f"{family}-{id_hex(identifier)}.json"


def document_id_fits(family: str, identifier: str) -> bool:
    return len(document_filename(family, identifier).encode("ascii")) <= MAX_FILENAME_BYTES


class IdGenerator:
    """Generador de IDs que no derivan de etiquetas, orden ni coordenadas.

    Por defecto usa UUID aleatorios; las pruebas inyectan un prefijo determinista.
    """

    def __init__(self, prefix: str | None = None) -> None:
        self._prefix = prefix
        self._n = 0

    def new(self, kind: str) -> str:
        if self._prefix is None:
            return f"{kind}-{uuid.uuid4().hex}"
        self._n += 1
        return f"{self._prefix}{kind}-{self._n}"
