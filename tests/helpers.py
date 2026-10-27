"""Ayudas de las pruebas: sesiones, estados declarados y lectura de la traza.

El constructor de modelos y escenarios (M, scenario) está en grafcet/builder.py, porque también lo usan los
ejemplos del simulador; aquí se reexporta. Convención de las pruebas: el ID de cada etapa y variable coincide
con su etiqueta, y las entradas booleanas valen false salvo indicación (ficha común del documento 11).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grafcet.builder import M, S, fmt, scenario  # noqa: E402,F401  (el constructor está en el núcleo)
from grafcet.diagnostics import Diagnostic  # noqa: E402
from grafcet.engine import Session, declared_state  # noqa: E402
from grafcet.model import CompiledModel  # noqa: E402
from grafcet.timeutil import parse_duration  # noqa: E402


def session(cm: CompiledModel, init: dict[str, Any] | None = None, batches: list[tuple[int, int, dict[str, Any]]] = (),
            budget: int = 10_000, start: bool = True, options: dict[str, str] | None = None, **kw: Any) -> Session:
    s = Session(cm, scenario(cm, init, batches, **kw), budget=budget, options=options)
    if start:
        diags = s.start()
        assert not diags, [str(d) for d in diags]
    return s


def declared(cm: CompiledModel, situation: list[str], batches: list[tuple[int, int, dict[str, Any]]] = (),
             values: dict[str, Any] | None = None, budget: int = 10_000, options: dict[str, str] | None = None,
             **kw: Any) -> Session:
    """Sesión desde un estado previo declarado de prueba (no inicialización normativa). Desde la respuesta 6.1 A
    un modelo sin etapas iniciales no compila, así que los modelos de estas pruebas marcan una como inicial: la
    marca no influye, porque el estado declarado sustituye a la inicialización."""
    s = Session(cm, scenario(cm, None, batches, **kw), budget=budget, options=options)
    s.start_declared(declared_state(cm, situation, values))
    return s


def records(s: Session, kind: str) -> list[dict[str, Any]]:
    return [r for r in s.trace.records if r["kind"] == kind]


def last_diag(s: Session) -> Diagnostic:
    return s.diagnostics[-1]


def us(text: str) -> int:
    return parse_duration(text)
