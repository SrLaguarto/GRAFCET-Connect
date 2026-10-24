"""Escenarios: entradas iniciales, lotes y condición de parada (documentos 05, 08, 09).

REQ-EVT-02: un lote es simultáneo y admite como máximo una escritura por entrada;
dos lotes con igual tiempo y ordinal distinto son hechos distintos y ordenados.
REQ-SIM-02: los lotes conservan origen (escenario/manual) y agrupación.
P-IMP-02 (H-06): el escenario es la fuente del valor inicial de las entradas en la ejecución.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .diagnostics import Diagnostic, DiagnosticError
from .ids import valid_id
from .model import CompiledModel
from .profile import PROFILE_ID, unsupported
from .timeutil import parse_time_field
from .values import Value, in_domain, parse_value

FIELDS = {"family", "formatVersion", "id", "modelRevision", "semanticProfile", "initialInputs", "batches",
          "stopCondition", "timeUnit"}
OPTIONAL = {"extensions", "minorAddsSemantics"}
MAX_BATCHES = 100_000


@dataclass(frozen=True)
class Batch:
    id: str
    time: int
    ordinal: int
    changes: tuple[tuple[str, Value], ...]
    origin: str = "escenario"

    def to_dict(self, cm: CompiledModel) -> dict[str, Any]:
        from .values import format_value
        return {"id": self.id, "timeUs": str(self.time), "ordinalAtTime": self.ordinal, "origin": self.origin,
                "changes": [{"variableRef": v, "value": format_value(cm.variables[v].type, val)}
                            for v, val in self.changes]}


@dataclass
class Scenario:
    id: str
    initial: dict[str, Value]
    batches: list[Batch]
    horizon: int | None
    max_contexts: int
    predicate: str | None = None
    doc: dict[str, Any] = field(default_factory=dict)


def _change(cm: CompiledModel, raw: Any, where: str) -> tuple[str, Value]:
    if not isinstance(raw, dict) or set(raw) != {"variableRef", "value"}:
        raise DiagnosticError(Diagnostic("D-FORMATO", "cambio de lote mal formado", element=where))
    var = cm.variables.get(raw["variableRef"])
    if var is None:
        raise DiagnosticError(Diagnostic("D-REF", f"variable inexistente {raw['variableRef']}", element=where))
    if var.role != "input":
        raise DiagnosticError(Diagnostic("D-ESCRITURA-ROL", f"el escenario solo escribe entradas ({var.id} es {var.role})",
                                         element=where))
    value = parse_value(var.type, raw["value"])
    if not in_domain(var.type, var.domain, value):
        raise DiagnosticError(Diagnostic("D-NUM", f"valor fuera de dominio para {var.id}", element=where))
    return var.id, value


def load_scenario(doc: dict[str, Any], cm: CompiledModel) -> tuple[Scenario | None, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    if not isinstance(doc, dict) or FIELDS - set(doc):
        missing = sorted(FIELDS - set(doc)) if isinstance(doc, dict) else []
        return None, [Diagnostic("D-FORMATO", f"campos obligatorios ausentes en escenario: {missing}")]
    unknown = set(doc) - FIELDS - OPTIONAL
    if unknown:
        diags.append(Diagnostic("D-FORMATO", f"campos desconocidos en escenario: {sorted(unknown)}", severity="bloqueo"))
    sid = doc["id"]
    if doc["modelRevision"] != cm.revision:
        diags.append(Diagnostic("D-REF", f"el escenario pertenece a la revisión {doc['modelRevision']}, no a {cm.revision}",
                                element=sid, field="modelRevision"))
    if doc["semanticProfile"] != PROFILE_ID:
        diags.append(Diagnostic("D-REF", f"perfil semántico distinto: {doc['semanticProfile']}", element=sid,
                                field="semanticProfile"))
    if doc["timeUnit"] != "us":
        diags.append(Diagnostic("D-FORMATO", "timeUnit debe ser «us»", element=sid, field="timeUnit"))
    initial: dict[str, Value] = {}
    raw_init = doc["initialInputs"]
    if not isinstance(raw_init, dict):
        return None, diags + [Diagnostic("D-FORMATO", "initialInputs debe ser un objeto", element=sid)]
    for vid, raw in raw_init.items():
        try:
            k, val = _change(cm, {"variableRef": vid, "value": raw}, sid)
            initial[k] = val
        except DiagnosticError as exc:
            diags.extend(exc.diagnostics)
    for vid in sorted(cm.inputs - set(initial)):
        diags.append(Diagnostic("D-ENTRADA-SIN-VALOR", f"la entrada {vid} no tiene valor inicial; no se supone false",
                                element=vid))
    batches: list[Batch] = []
    raw_batches = doc["batches"]
    if not isinstance(raw_batches, list):
        return None, diags + [Diagnostic("D-FORMATO", "batches debe ser una lista", element=sid)]
    if len(raw_batches) > MAX_BATCHES:
        diags.append(Diagnostic("D-LIM-DATOS", f"{len(raw_batches)} lotes superan el límite {MAX_BATCHES}", element=sid))
        return None, diags
    seen_ids: set[str] = set()
    last: tuple[int, int] | None = None
    for raw in raw_batches:
        if not isinstance(raw, dict) or {"id", "timeUs", "ordinalAtTime", "changes", "origin"} - set(raw):
            diags.append(Diagnostic("D-FORMATO", "lote mal formado", element=sid))
            continue
        bid = raw["id"]
        if not valid_id(bid) or bid in seen_ids:
            diags.append(Diagnostic("D-ID", f"ID de lote inválido o duplicado: {bid!r}", element=sid))
            continue
        seen_ids.add(bid)
        try:
            t = parse_time_field(raw["timeUs"])
        except DiagnosticError as exc:
            diags.extend(exc.diagnostics)
            continue
        ordinal = raw["ordinalAtTime"]
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            diags.append(Diagnostic("D-FORMATO", "ordinalAtTime debe ser entero", element=bid))
            continue
        key = (t, ordinal)
        if last is not None and key <= last:
            diags.append(Diagnostic("D-LOTE", "lotes no ordenados por (tiempo, ordinal) o pareja repetida; "
                                    "no se deduce simultaneidad por igualdad de tiempo", element=bid,
                                    evidence={"anterior": str(last), "actual": str(key)}))
            continue
        last = key
        if raw["origin"] not in ("escenario", "manual"):
            diags.append(Diagnostic("D-FORMATO", f"origen de lote desconocido: {raw['origin']!r}", element=bid))
            continue
        changes: dict[str, Value] = {}
        bad = False
        for ch in raw["changes"] if isinstance(raw["changes"], list) else []:
            try:
                k, val = _change(cm, ch, bid)
            except DiagnosticError as exc:
                diags.extend(exc.diagnostics)
                bad = True
                continue
            if k in changes:
                diags.append(Diagnostic("D-LOTE", f"más de una escritura sobre {k} en el mismo lote",
                                        element=bid, evidence={"valores": f"{changes[k]!r}, {val!r}"}))
                bad = True
            changes[k] = val
        if not bad:
            batches.append(Batch(bid, t, ordinal, tuple(sorted(changes.items())), raw["origin"]))
    stop = doc["stopCondition"]
    horizon = predicate = None
    max_ctx = 0
    if not isinstance(stop, dict) or "maxContexts" not in stop:
        diags.append(Diagnostic("D-FORMATO", "stopCondition requiere maxContexts finito", element=sid))
    else:
        max_ctx = stop["maxContexts"]
        if not isinstance(max_ctx, int) or isinstance(max_ctx, bool) or max_ctx < 1:
            diags.append(Diagnostic("D-FORMATO", "maxContexts debe ser un entero positivo", element=sid))
        if "horizonUs" in stop:
            try:
                horizon = parse_time_field(stop["horizonUs"])
            except DiagnosticError as exc:
                diags.extend(exc.diagnostics)
        predicate = stop.get("predicateRef")
        if predicate is not None:
            diags.append(unsupported("escenario.predicado-parada", "condición de parada por predicado", sid))
    if any(d.blocks_start for d in diags):
        return None, diags
    return Scenario(sid, initial, batches, horizon, max_ctx, predicate, doc), diags
