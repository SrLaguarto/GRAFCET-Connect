"""Representación canónica JSON y digest SHA-256 (documento 09, REQ-DAT-05, REQ-DAT-08).

Reglas: claves ordenadas por punto de código; UTF-8 sin BOM ni espacios; en cadenas
se escapan comillas y barra inversa, U+0000..U+001F como \\u00xx en minúsculas y el
resto se emite directamente; se rechazan sustitutos aislados; los únicos números JSON
nativos son enteros de metadatos entre 0 y 2^31-1.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_META_INT = 2**31 - 1
# Cada nodo de expresión ocupa dos niveles JSON (objeto + lista de operandos); con la
# profundidad de expresión 64 del documento 10 y el envoltorio del documento se llega a
# unos 135 niveles. El límite se deriva de ese presupuesto con margen.
MAX_JSON_DEPTH = 2 * 64 + 32


class CanonicalError(ValueError):
    pass


def _string(s: str, out: list[str]) -> None:
    out.append('"')
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        elif 0xD800 <= o <= 0xDFFF:
            raise CanonicalError("sustituto Unicode aislado")
        else:
            out.append(ch)
    out.append('"')


def _emit(value: Any, out: list[str], depth: int) -> None:
    if depth > MAX_JSON_DEPTH:
        raise CanonicalError("profundidad excesiva")
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, int):
        if not 0 <= value <= MAX_META_INT:
            raise CanonicalError(f"entero nativo fuera de metadatos: {value}")
        out.append(str(value))
    elif isinstance(value, float):
        raise CanonicalError("número no entero: use cadena tipada")
    elif isinstance(value, str):
        _string(value, out)
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for i, item in enumerate(value):
            if i:
                out.append(",")
            _emit(item, out, depth + 1)
        out.append("]")
    elif isinstance(value, dict):
        out.append("{")
        for i, key in enumerate(sorted(value)):
            if not isinstance(key, str):
                raise CanonicalError("clave no textual")
            if i:
                out.append(",")
            _string(key, out)
            out.append(":")
            _emit(value[key], out, depth + 1)
        out.append("}")
    else:
        raise CanonicalError(f"tipo no serializable: {type(value).__name__}")


def canonical_text(value: Any) -> str:
    out: list[str] = []
    _emit(value, out, 0)
    return "".join(out)


def canonical_bytes(value: Any) -> bytes:
    return canonical_text(value).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    return sha256_hex(canonical_bytes(value))


# --- Lectura estricta (REQ-DAT-06) ---------------------------------------------------

def _depth_scan(text: str) -> int:
    depth = best = 0
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            best = max(best, depth)
        elif ch in "]}":
            depth -= 1
    return best


def _no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in pairs:
        if k in result:
            raise CanonicalError(f"clave duplicada: {k}")
        result[k] = v
    return result


def _reject_float(text: str) -> Any:
    raise CanonicalError(f"número no entero no admitido: {text}")


def _int(text: str) -> int:
    v = int(text)
    if not 0 <= v <= MAX_META_INT:
        raise CanonicalError(f"entero nativo fuera de metadatos: {text}")
    return v


def _reject_const(text: str) -> Any:
    raise CanonicalError(f"constante no admitida: {text}")


def strict_loads(data: bytes, max_depth: int = MAX_JSON_DEPTH) -> Any:
    """Decodifica JSON rechazando BOM, flotantes, NaN/infinito, claves duplicadas y profundidad excesiva."""
    if data.startswith(b"\xef\xbb\xbf"):
        raise CanonicalError("BOM no admitido")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CanonicalError(f"UTF-8 inválido: {exc}") from exc
    if _depth_scan(text) > max_depth:
        raise CanonicalError("profundidad excesiva")
    try:
        return json.loads(text, object_pairs_hook=_no_dupes, parse_float=_reject_float,
                          parse_int=_int, parse_constant=_reject_const)
    except json.JSONDecodeError as exc:
        raise CanonicalError(f"JSON inválido: {exc}") from exc
