"""Traza de ejecución (documentos 08 y 09; REQ-SIM-05, REQ-DAT-08).

Formato propuesto P-IMP-07: JSON Lines canónico. Primera línea = cabecera; después,
registros con secuencia monótona; última línea = cierre con recuento y digest de
contenido. Si falta el cierre, o el recuento o el digest no coinciden, la traza se
marca truncada (D-INTEGRIDAD) y solo se ofrece el prefijo verificado.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .canonical import CanonicalError, canonical_text, strict_loads
from .diagnostics import Diagnostic

MAX_RECORDS = 1_000_000


@dataclass
class Trace:
    header: dict[str, Any]
    records: list[dict[str, Any]] = field(default_factory=list)
    closure: dict[str, Any] | None = None
    max_records: int = MAX_RECORDS

    def add(self, kind: str, **data: Any) -> dict[str, Any]:
        rec = {"sequence": len(self.records) + 1, "kind": kind, **data}
        self.records.append(rec)
        return rec

    def remaining(self) -> int:
        return self.max_records - len(self.records)

    def _lines(self) -> list[str]:
        return [canonical_text({"type": "header", **self.header})] + \
               [canonical_text({"type": "record", **r}) for r in self.records]

    def close(self, completion: str, final_state_ref: str | None = None) -> dict[str, Any]:
        h = hashlib.sha256()
        for line in self._lines():
            h.update(line.encode("utf-8") + b"\n")
        self.closure = {"completionState": completion, "recordCount": len(self.records),
                        "finalStateRef": final_state_ref, "contentDigest": h.hexdigest()}
        return self.closure

    def to_jsonl(self) -> bytes:
        lines = self._lines()
        if self.closure is not None:
            lines.append(canonical_text({"type": "closure", **self.closure}))
        return ("\n".join(lines) + "\n").encode("utf-8")


@dataclass
class TraceCheck:
    complete: bool
    header: dict[str, Any] | None
    records: list[dict[str, Any]]
    diagnostics: list[Diagnostic]


def verify_trace(data: bytes) -> TraceCheck:
    """Verifica cierre, recuento y digest; conserva el prefijo válido si hay pérdida."""
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    header = None
    records: list[dict[str, Any]] = []
    h = hashlib.sha256()
    closure = None
    for i, raw in enumerate(lines):
        try:
            obj = strict_loads(raw)
        except CanonicalError as exc:
            return TraceCheck(False, header, records, [Diagnostic(
                "D-INTEGRIDAD", f"línea {i + 1} ilegible ({exc}); traza truncada, prefijo verificado disponible",
                evidence={"registrosVerificados": str(len(records))})])
        kind = obj.pop("type", None)
        if i == 0 and kind != "header":
            return TraceCheck(False, None, [], [Diagnostic("D-FORMATO", "la traza no comienza por cabecera")])
        if kind == "closure":
            closure = obj
            if i != len(lines) - 1:
                return TraceCheck(False, header, records, [Diagnostic("D-INTEGRIDAD", "contenido después del cierre")])
            break
        h.update(raw + b"\n")
        if kind == "header":
            header = obj
        elif kind == "record":
            if obj.get("sequence") != len(records) + 1:
                return TraceCheck(False, header, records, [Diagnostic("D-INTEGRIDAD", "secuencia no monótona")])
            records.append(obj)
    if closure is None:
        return TraceCheck(False, header, records, [Diagnostic(
            "D-INTEGRIDAD", "traza sin cierre: marcada truncada; no demuestra finalización",
            evidence={"registrosVerificados": str(len(records))})])
    if closure.get("recordCount") != len(records) or closure.get("contentDigest") != h.hexdigest():
        return TraceCheck(False, header, records, [Diagnostic(
            "D-INTEGRIDAD", "recuento o digest de la traza no coinciden", evidence={"registros": str(len(records))})])
    return TraceCheck(True, header, records, [])


SEMANTIC_KINDS = {"inicio", "contexto", "evolucion", "estable", "fallo", "limite", "intervencion", "entrada-manual"}
_DROP = {"sequence", "runId", "snapshot", "contextRef"}


def semantic_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Observables canónicos comparables entre ejecuciones (REQ-SEM-08, REQ-PLT-01)."""
    out = []
    for r in records:
        if r["kind"] in SEMANTIC_KINDS:
            out.append({k: v for k, v in r.items() if k not in _DROP})
    return out
