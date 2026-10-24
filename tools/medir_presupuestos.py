"""Medición INDICATIVA de presupuestos del documento 10 (REQ-PLT-04, T-25d).

No es una aceptación: el equipo de referencia y la matriz de sistemas siguen pendientes
(U-10). Mide en el equipo actual el modelo de referencia (5 000 etapas, 5 000 transiciones,
10 000 acciones) con cinco repeticiones de validación y de guardado/apertura, y 100
operaciones de vista en el editor sin interfaz.
Uso:  python tools/medir_presupuestos.py   → docs/07_Medicion_indicativa.md
"""
from __future__ import annotations

import os
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from grafcet.editor import Editor, new_model_document  # noqa: E402
from grafcet.ids import IdGenerator  # noqa: E402
from grafcet.model import validate_model  # noqa: E402
from grafcet.persistence import add_document, new_project, open_project, save_project  # noqa: E402


def reference_model(n: int = 5000) -> dict:
    doc = new_model_document("ref")
    doc["partials"].append({"id": "g", "label": "g", "stepRefs": [], "transitionRefs": []})
    doc["variables"] += [{"id": "p", "name": "p", "scopeRef": "ref", "role": "input", "type": {"kind": "bool"},
                          "unit": "", "domain": {}, "initialValue": False},
                         {"id": "y", "name": "y", "scopeRef": "ref", "role": "output", "type": {"kind": "bool"},
                          "unit": "", "domain": {}, "initialValue": False}]
    for i in range(n):
        sid, tid = f"s{i}", f"t{i}"
        doc["steps"].append({"id": sid, "label": sid, "partialRef": "g", "kind": "ordinary", "initial": i == 0,
                             "actionRefs": [f"a{i}a", f"a{i}b"]})
        doc["partials"][0]["stepRefs"].append(sid)
        doc["expressions"].append({"id": f"e{i}", "mode": "executable", "text": "p", "bindings": {"p": "p"},
                                   "meaning": {"operator": "ref", "reference": "p"}})
        doc["transitions"].append({"id": tid, "partialRef": "g", "preRefs": [sid], "postRefs": [f"s{(i + 1) % n}"],
                                   "conditionRef": f"e{i}"})
        doc["partials"][0]["transitionRefs"].append(tid)
        for suffix in ("a", "b"):
            doc["expressions"].append({"id": f"c{i}{suffix}", "mode": "executable", "text": "true", "bindings": {},
                                       "meaning": {"operator": "lit", "literal": {"type": "bool", "value": True}}})
            doc["actions"].append({"id": f"a{i}{suffix}", "stepRef": sid, "mode": "continuous", "targetRef": "y",
                                   "conditionRef": f"c{i}{suffix}"})
    return doc


def timed(fn, reps: int) -> list[float]:
    out = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t0)
    return out


def main() -> None:
    doc = reference_model()
    val = timed(lambda: validate_model(doc), 5)
    tracemalloc.start()
    validate_model(doc)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    with tempfile.TemporaryDirectory() as tmp:
        pj = new_project("proy", "ref")
        add_document(pj, doc)
        save = timed(lambda: save_project(Path(tmp), pj), 5)
        size = sum(f.stat().st_size for f in Path(tmp).glob("*.json"))
        load = timed(lambda: open_project(Path(tmp)), 5)
    pres = {"family": "presentation", "formatVersion": "0.1", "id": "ref.vista", "modelId": "ref",
            "views": [{"id": "v", "label": "principal"}], "notes": [],
            "elementLayouts": [{"elementRef": x["id"], "viewRef": "v", "x": str(i % 100 * 50), "y": str(i // 100 * 50)}
                               for i, x in enumerate(doc["steps"] + doc["transitions"])]}
    ed = Editor(doc, pres, ids=IdGenerator("m"))
    for i in range(10):  # calentamiento
        ed.move(f"s{i}", i, i)
    view = sorted(timed(lambda: ed.move("s1", 5, 5), 100))
    p95 = view[94]
    sem = timed(lambda: ed.rename("s2", f"etapa-{time.perf_counter_ns()}"), 5)
    rows = [("Validación completa (≤5 s)", val), ("Guardar modelo (≤5 s)", save), ("Abrir modelo (≤5 s)", load)]
    lines = ["# 07. Medición indicativa de presupuestos", "",
             "**No es aceptación (U-10).** El equipo no es el de referencia (aún sin fijar), así que estas cifras no "
             "comprometen ninguna promesa de rendimiento.", "",
             f"Equipo: {platform.platform()} · {platform.machine()} · {os.cpu_count()} CPU lógicas · Python "
             f"{platform.python_version()}. Modelo: 5 000 etapas, 5 000 transiciones, 10 000 acciones; archivo de "
             f"{size / 1e6:.1f} MB; presentación con 10 000 elementos dibujados.", "", "| Medida | Mediana | Máximo | Objetivo P (doc. 10) | Estado indicativo |",
             "|---|---|---|---|---|"]
    for name, xs in rows:
        lines.append(f"| {name} | {statistics.median(xs):.3f} s | {max(xs):.3f} s | ≤5 s | "
                     f"{'dentro' if max(xs) <= 5 else 'FUERA'} |")
    lines.append(f"| Operación de vista (mover), p95 de 100 | {statistics.median(view) * 1000:.0f} ms (mediana) | "
                 f"{max(view) * 1000:.0f} ms | p95 ≤100 ms | {'dentro' if p95 <= 0.1 else 'FUERA'} (p95 {p95 * 1000:.0f} ms) |")
    lines.append(f"| Edición semántica (renombrar), 5 repeticiones | {statistics.median(sem) * 1000:.0f} ms | "
                 f"{max(sem) * 1000:.0f} ms | sin objetivo en doc. 10 | informativo |")
    lines.append(f"| Pico de memoria de la validación | {peak / 2**20:.0f} MiB | — | ≤2 GiB | "
                 f"{'dentro' if peak <= 2**31 else 'FUERA'} |")
    lines += ["", "Observaciones:", "",
              "- Primera medición: una operación de vista tardaba unos 1 s de mediana (p95 2,7 s), fuera de objetivo, porque "
              "toda transacción copiaba el modelo y recalculaba su digest. Desde la corrección (P-IMP-08), una operación de vista "
              "solo copia la presentación y no recalcula la revisión semántica.",
              "- Una edición semántica sigue copiando el modelo y recalculando la revisión: su coste es O(tamaño del modelo). "
              "Si la interfaz lo necesita, el remedio previsto es un historial por diferencias, que no cambia ni contratos "
              "ni formato.",
              "- Las mediciones de aceptación deben repetirse en el equipo y los sistemas de U-10, con cinco repeticiones "
              "documentadas, como pide el documento 10.", ""]
    (ROOT / "docs" / "07_Medicion_indicativa.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
