"""Extractor del paquete de doce documentos: requisitos, casos y referencias cruzadas.

Lee directamente los Markdown de `Definición del proyecto/` para que la trazabilidad
dependa del paquete y no de una copia manual. Solo lee; nunca escribe en el paquete.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / "Definición del proyecto"
CLASS_RE = re.compile(r"^([NIPEU])/(crítica|alta|media)$")
TEST_RE = re.compile(r"T-(\d{2})([a-z](?:,[a-z])*)")
REQREF_RE = re.compile(r"\b([A-Z]{2,3})-(\d{2})((?:,\d{2})*)")
EDT_CRITICAL = {"REQ-EDT-04", "REQ-EDT-05", "REQ-EDT-06", "REQ-EDT-10", "REQ-EDT-14"}  # documento 07, texto


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def expand_tests(text: str) -> list[str]:
    out = []
    for num, letters in TEST_RE.findall(text):
        out += [f"T-{num}{x}" for x in letters.split(",")]
    out += re.findall(r"\bR-0\d\b", text)
    return list(dict.fromkeys(out))


def expand_reqs(text: str) -> list[str]:
    out = []
    for fam, first, rest in REQREF_RE.findall(text):
        nums = [first] + [n for n in rest.split(",") if n]
        out += [f"REQ-{fam}-{n}" for n in nums]
    return list(dict.fromkeys(out))


def load_requirements(pkg: Path = PKG) -> dict[str, dict]:
    reqs: dict[str, dict] = {}
    for f in sorted(pkg.glob("*.md")):
        doc = f.name[:2]
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| REQ-"):
                continue
            cells = _cells(line)
            rid = cells[0]
            cls_idx = next((i for i, c in enumerate(cells) if CLASS_RE.match(c)), None)
            if cls_idx is not None:
                clase, prio = CLASS_RE.match(cells[cls_idx]).groups()
                text = cells[cls_idx + 1]
            else:  # documento 07: P/alta salvo las críticas declaradas en el texto
                clase, prio = "P", ("crítica" if rid in EDT_CRITICAL else "alta")
                text = cells[1]
            reqs[rid] = {"id": rid, "clase": clase, "prioridad": prio, "doc": doc, "texto": text,
                         "pruebas": expand_tests(line), "u": sorted(set(re.findall(r"U-\d{2}", line)))}
    return reqs


def load_cases(pkg: Path = PKG) -> dict[str, dict]:
    cases: dict[str, dict] = {}
    for line in (pkg / "11_Trazabilidad_y_plan_de_pruebas.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (T-\d{2}[a-z]) \|", line)
        if not m:
            continue
        cells = _cells(line)
        cases[m.group(1)] = {"id": m.group(1), "reqs": expand_reqs(cells[1]), "estado": cells[-1],
                             "u": sorted(set(re.findall(r"U-\d{2}", line))), "oraculo": cells[3]}
    return cases


def bidirectional(reqs: dict[str, dict], cases: dict[str, dict]) -> dict[str, list[tuple[str, str]]]:
    """Referencias que solo aparecen en un sentido (revisión bidireccional del documento 11)."""
    req_only = [(r, t) for r, v in reqs.items() for t in v["pruebas"] if t.startswith("T-")
                and t in cases and r not in cases[t]["reqs"]]
    case_only = [(t, r) for t, v in cases.items() for r in v["reqs"] if r in reqs and t not in reqs[r]["pruebas"]]
    dangling = [(r, t) for r, v in reqs.items() for t in v["pruebas"] if t.startswith("T-") and t not in cases]
    unknown = [(t, r) for t, v in cases.items() for r in v["reqs"] if r not in reqs]
    return {"requisito→caso sin retorno": req_only, "caso→requisito sin retorno": case_only,
            "caso inexistente": dangling, "requisito inexistente": unknown}


def package_hashes(pkg: Path = PKG) -> dict[str, str]:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(pkg.iterdir())}
