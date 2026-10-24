"""Parte automatizable de R-02 (REQ-ALC-02, REQ-CR-02): el paquete de transferencia sigue
siendo exactamente doce Markdown y coincide con la versión contra la que se implementó.

Uso:  python tools/comprobar_paquete.py            (comprueba)
      python tools/comprobar_paquete.py --registrar (fija la línea base; solo al adoptar una versión nueva)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paquete

BASE = Path(__file__).resolve().parents[1] / "spec" / "paquete_base.json"


def main() -> int:
    hashes = paquete.package_hashes()
    errors = []
    if len(hashes) != 12 or not all(n.endswith(".md") for n in hashes):
        errors.append(f"el paquete debe contener exactamente doce Markdown; contiene: {sorted(hashes)}")
    if "--registrar" in sys.argv:
        BASE.write_text(json.dumps({"version": "0.1", "sha256": hashes}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"línea base registrada: {len(hashes)} archivos")
    elif BASE.exists():
        base = json.loads(BASE.read_text(encoding="utf-8"))["sha256"]
        for name in sorted(set(base) | set(hashes)):
            if base.get(name) != hashes.get(name):
                errors.append(f"{name}: distinto de la línea base (¿nueva versión del paquete?)")
    for e in errors:
        print("ERROR:", e)
    if not errors:
        print("R-02, parte automatizable, superada: 12 Markdown con huellas iguales a la línea base")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
