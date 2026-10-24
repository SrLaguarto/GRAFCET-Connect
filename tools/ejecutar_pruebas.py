"""Ejecuta la batería y registra el resultado de cada prueba con su caso (T-xx o S-xx).

Uso:  python tools/ejecutar_pruebas.py
Escribe docs/resultados_pruebas.json (evidencia reproducible: versión de Python, sistema,
fecha y resultado por prueba). Sale con código distinto de cero si alguna prueba falla.
"""
from __future__ import annotations

import datetime
import json
import platform
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))


def case_of(method: str) -> str | None:
    m = re.match(r"test_(T\d{2}[a-z])_", method)
    if m:
        return f"{m.group(1)[:1]}-{m.group(1)[1:]}"
    m = re.match(r"test_S([A-Z0-9]+[a-z]?)_", method)
    return f"S-{m.group(1)}" if m else None


class Recorder(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.outcomes: dict[str, str] = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()] = "pasa"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "falla"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "error"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "omitida"


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py", top_level_dir=str(ROOT / "tests"))
    tests = {}

    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                walk(t)
            else:
                tests[t.id()] = t
    walk(suite)
    runner = unittest.TextTestRunner(resultclass=Recorder, verbosity=1)
    result = runner.run(suite)
    out = []
    for tid, outcome in sorted(result.outcomes.items()):
        method = tid.rsplit(".", 1)[-1]
        doc = (getattr(tests.get(tid), method, None).__doc__ or "") if tid in tests else ""
        out.append({"test": tid, "case": case_of(method), "outcome": outcome,
                    "requirements": sorted(set(re.findall(r"REQ-[A-Z]+-\d{2}", doc.split("\n")[0]))),
                    "summary": doc.strip().split("\n")[0]})
    report = {"date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
              "python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine(),
              "total": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "results": out}
    (ROOT / "docs" / "resultados_pruebas.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                                                          encoding="utf-8", newline="\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
