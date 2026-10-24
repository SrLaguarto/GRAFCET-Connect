"""Tipos ejecutables y valores exactos (documento 05, REQ-EXP-01).

Booleano, entero con signo de 64 bits, decimal exacto de escala declarada (0..9
decimales, hasta 18 cifras significativas) y duración entera en µs. No hay lógica
ternaria ni conversiones implícitas; desbordamientos y valores no representables
producen D-NUM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Union

from .diagnostics import Diagnostic, DiagnosticError
from .timeutil import MAX_US

INT64_MIN, INT64_MAX = -(2**63), 2**63 - 1
MAX_SIG_DIGITS = 18
Value = Union[bool, int, Fraction]

_INT_RE = re.compile(r"^(0|-?[1-9][0-9]*)$")
_DEC_RE = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")


@dataclass(frozen=True)
class TypeSpec:
    kind: str  # "bool" | "int" | "decimal" | "duration"
    scale: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "scale": self.scale} if self.kind == "decimal" else {"kind": self.kind}


def num_error(msg: str, **evidence: Any) -> DiagnosticError:
    return DiagnosticError(Diagnostic("D-NUM", msg, evidence={k: str(v) for k, v in evidence.items()}))


def parse_type(raw: Any) -> TypeSpec:
    if not isinstance(raw, dict) or raw.get("kind") not in ("bool", "int", "decimal", "duration"):
        raise DiagnosticError(Diagnostic("D-FORMATO", "tipo de variable no reconocido", evidence={"tipo": repr(raw)}))
    if raw["kind"] == "decimal":
        scale = raw.get("scale")
        if not isinstance(scale, int) or isinstance(scale, bool) or not 0 <= scale <= 9:
            raise DiagnosticError(Diagnostic("D-FORMATO", "escala decimal fuera de 0..9", evidence={"tipo": repr(raw)}))
        return TypeSpec("decimal", scale)
    extra = set(raw) - {"kind"}
    if extra:
        raise DiagnosticError(Diagnostic("D-FORMATO", "campos de tipo no reconocidos", evidence={"campos": sorted(extra)}))
    return TypeSpec(raw["kind"])


def zero(t: TypeSpec) -> Value:
    return False if t.kind == "bool" else (Fraction(0) if t.kind == "decimal" else 0)


def sig_digits(v: Fraction, scale: int) -> int:
    scaled = abs(int(v * 10**scale))
    return len(str(scaled).lstrip("0")) or 1


def check_fits(t: TypeSpec, v: Value) -> Value:
    """Comprueba que un valor es representable en el tipo destino sin redondeo."""
    if t.kind == "bool":
        if not isinstance(v, bool):
            raise DiagnosticError(Diagnostic("D-TIPO", "se esperaba booleano"))
        return v
    if isinstance(v, bool):
        raise DiagnosticError(Diagnostic("D-TIPO", "booleano en contexto numérico"))
    if t.kind in ("int", "duration"):
        if isinstance(v, Fraction):
            if v.denominator != 1:
                raise num_error("valor no entero para destino entero", valor=v)
            v = int(v)
        lo, hi = (INT64_MIN, INT64_MAX) if t.kind == "int" else (0, MAX_US)
        if not lo <= v <= hi:
            raise num_error("valor fuera de rango del tipo", valor=v, tipo=t.kind)
        return v
    fv = Fraction(v)
    if (fv * 10**t.scale).denominator != 1:
        raise num_error("valor no representable en la escala declarada sin redondeo", valor=fv, escala=t.scale)
    if sig_digits(fv, t.scale) > MAX_SIG_DIGITS:
        raise num_error("más de 18 cifras significativas", valor=fv)
    return fv


def parse_value(t: TypeSpec, raw: Any) -> Value:
    """Lee un valor serializado: booleanos nativos; números como cadena canónica."""
    if t.kind == "bool":
        if not isinstance(raw, bool):
            raise DiagnosticError(Diagnostic("D-TIPO", "valor booleano esperado", evidence={"valor": repr(raw)}))
        return raw
    if not isinstance(raw, str):
        raise DiagnosticError(Diagnostic("D-FORMATO", "número no serializado como cadena", evidence={"valor": repr(raw)}))
    if t.kind in ("int", "duration"):
        if not _INT_RE.match(raw) or raw == "-0":
            raise DiagnosticError(Diagnostic("D-FORMATO", "entero no canónico", evidence={"valor": raw}))
        return check_fits(t, int(raw))
    m = _DEC_RE.match(raw)
    if not m or raw.startswith("-0") and Fraction(raw) == 0 or (m.group(2) and m.group(2).endswith("0")):
        raise DiagnosticError(Diagnostic("D-FORMATO", "decimal no canónico", evidence={"valor": raw}))
    if m.group(2) and len(m.group(2)) - 1 > t.scale:
        raise num_error("más decimales que la escala declarada", valor=raw, escala=t.scale)
    return check_fits(t, Fraction(raw))


def format_value(t: TypeSpec, v: Value) -> Any:
    if t.kind == "bool":
        return bool(v)
    if t.kind in ("int", "duration"):
        return str(int(v))
    fv = Fraction(v)
    scaled = int(fv * 10**t.scale)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, frac = divmod(scaled, 10**t.scale) if t.scale else (scaled, 0)
    text = str(whole)
    if t.scale and frac:
        text += "." + f"{frac:0{t.scale}d}".rstrip("0")
    return sign + text if (whole or frac) else "0"


def in_domain(t: TypeSpec, domain: dict[str, Any], v: Value) -> bool:
    if t.kind == "bool" or not domain:
        return True
    lo = parse_value(t, domain["min"]) if "min" in domain else None
    hi = parse_value(t, domain["max"]) if "max" in domain else None
    return (lo is None or v >= lo) and (hi is None or v <= hi)
