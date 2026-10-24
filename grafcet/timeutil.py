"""Tiempo lógico exacto en microsegundos (documento 05, REQ-TMP-01, REQ-PLT-02).

Unidad canónica µs; rango 0..2^63-1; sin redondeo silencioso. La unidad visible
(s, ms, µs) y la configuración regional solo afectan a la entrada y presentación.
"""
from __future__ import annotations

import re
from fractions import Fraction

from .diagnostics import Diagnostic, DiagnosticError

MAX_US = 2**63 - 1
UNITS = {"us": 1, "µs": 1, "μs": 1, "ms": 1_000, "s": 1_000_000}
_DECIMAL_SEP = {"canonical": ".", "en-US": ".", "es-ES": ","}
_DUR_RE = {
    sep: re.compile(r"^\s*(-)?\s*(\d+)(?:" + re.escape(sep) + r"(\d+))?\s*(us|µs|μs|ms|s)\s*$")
    for sep in set(_DECIMAL_SEP.values())
}


def _err(msg: str, text: str) -> DiagnosticError:
    return DiagnosticError(Diagnostic("D-NUM", msg, evidence={"entrada": text}))


def parse_duration(text: str, locale: str = "canonical") -> int:
    """Convierte «1,25 s» (es-ES) o «1.25 s» (en-US / canónico) en µs exactos."""
    if locale not in _DECIMAL_SEP:
        raise _err(f"configuración regional no admitida: {locale}", text)
    m = _DUR_RE[_DECIMAL_SEP[locale]].match(text)
    if not m:
        raise _err("duración con formato no reconocido", text)
    neg, ent, frac, unit = m.groups()
    if neg:
        raise _err("tiempo negativo no admitido", text)
    value = Fraction(int(ent)) + (Fraction(int(frac), 10 ** len(frac)) if frac else 0)
    us = value * UNITS[unit]
    if us.denominator != 1:
        raise _err("precisión inferior a 1 µs: no se redondea", text)
    return check_time(int(us), text)


def check_time(us: int, text: str | None = None) -> int:
    if us < 0:
        raise _err("tiempo negativo no admitido", text if text is not None else str(us))
    if us > MAX_US:
        raise _err("tiempo fuera de rango (máximo 2^63-1 µs)", text if text is not None else str(us))
    return us


def parse_time_field(value: object) -> int:
    """Lee un tiempo serializado como cadena decimal canónica de µs (documento 09)."""
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise DiagnosticError(Diagnostic("D-FORMATO", "tiempo no canónico (cadena decimal de µs)",
                                         evidence={"valor": repr(value)}))
    return check_time(int(value), value)


def format_duration(us: int, unit: str = "s", locale: str = "canonical") -> str:
    factor = UNITS[unit]
    value = Fraction(us, factor)
    whole, rest = divmod(value.numerator, value.denominator)
    if rest == 0:
        num = str(whole)
    else:
        digits = 0
        while (value * 10**digits).denominator != 1:
            digits += 1
        scaled = int(value * 10**digits)
        num = f"{scaled // 10**digits}{_DECIMAL_SEP[locale]}{scaled % 10**digits:0{digits}d}"
    return f"{num} {unit}"
