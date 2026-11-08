"""Ejecuta la suite módulo a módulo, cada uno en su propio proceso y con tiempo máximo, y resume el resultado.

Uso (con el Python del proyecto):

    python propuesta/herramientas/correr_pruebas.py                       # esta copia del repositorio
    python propuesta/herramientas/correr_pruebas.py --raiz <otra copia>   # p. ej. la de `main`
    python propuesta/herramientas/correr_pruebas.py --modulos test_aula_cambios test_vista_simulacion --paralelo 1
    python propuesta/herramientas/correr_pruebas.py --json resultado.json

- Un módulo que se cuelga o se cae no impide los demás: se marca TIMEOUT o CAIDO.
- `test_planos_integrados.test_SPAG18…` (importar un PDF real) se cuelga si falta `pypdfium2`: se ejecuta aparte, con su propio
  tiempo máximo, y el resto del módulo corre sin él.
- Con mucha carga fallan por tiempo `SRCT01`, `SFIO31`, `SMOD05`, `SFIO49` y `SFIO60`: el paralelismo por defecto es 2.
- No escribe nada en el repositorio (solo usa `unittest discover`; no toca `docs/` ni regenera nada).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ_POR_DEFECTO = Path(__file__).resolve().parents[2]
COLGANTES = {"test_planos_integrados.py": ("SPAG18",)}  # pruebas que se ejecutan aparte (dependen de pypdfium2)


def _entorno() -> dict:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _matar(proceso: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proceso.pid)], capture_output=True)
    else:
        proceso.kill()


def _ejecutar(raiz: Path, patron: str, nombres: list[str], tiempo: int) -> dict:
    orden = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "tests", "-p", patron]
    for n in nombres:
        orden += ["-k", n]
    inicio = time.time()
    p = subprocess.Popen(orden, cwd=raiz, env=_entorno(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    try:
        salida, _ = p.communicate(timeout=tiempo)
        estado = "OK"
    except subprocess.TimeoutExpired:
        _matar(p)
        salida = (p.communicate()[0] or "")
        estado = "TIMEOUT"
    r = {"modulo": patron, "estado": estado, "segundos": round(time.time() - inicio, 1), "ran": 0, "fallos": 0, "errores": 0,
         "omitidas": 0, "lista": []}
    m = re.search(r"^Ran (\d+) tests? in", salida, re.M)
    if m:
        r["ran"] = int(m.group(1))
    elif estado == "OK":
        r["estado"] = "CAIDO"  # sin resumen: el proceso murió (p. ej. un fallo nativo)
    m = re.search(r"^(?:OK|FAILED)\s*\((.*)\)\s*$", salida, re.M)
    if m:
        for k, v in re.findall(r"(failures|errors|skipped)=(\d+)", m.group(1)):
            r[{"failures": "fallos", "errors": "errores", "skipped": "omitidas"}[k]] = int(v)
    r["lista"] = sorted({f"{t}: {n}" for t, n in re.findall(r"^(FAIL|ERROR): (\S+)", salida, re.M)})
    if r["estado"] == "OK" and (r["fallos"] or r["errores"]):
        r["estado"] = "FALLOS"
    return r


def _nombres(raiz: Path, modulo: str, excluir: tuple[str, ...]) -> list[str]:
    texto = (raiz / "tests" / modulo).read_text(encoding="utf-8")
    return [n for n in re.findall(r"^\s+def (test_\w+)", texto, re.M) if not any(x in n for x in excluir)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", type=Path, default=RAIZ_POR_DEFECTO, help="raíz del repositorio (con tests/)")
    ap.add_argument("--modulos", nargs="*", help="módulos a ejecutar (con o sin .py); por defecto, todos")
    ap.add_argument("--paralelo", type=int, default=2)
    ap.add_argument("--tiempo", type=int, default=1800, help="segundos máximos por módulo (test_editor_escritorio tarda ≈ 15 min: 174 pruebas con ventana)")
    ap.add_argument("--tiempo-aparte", type=int, default=120, help="segundos máximos de las pruebas que se ejecutan aparte")
    ap.add_argument("--json", type=Path, help="guarda el resumen en este fichero")
    a = ap.parse_args(argv)
    raiz = a.raiz.resolve()
    todos = sorted(p.name for p in (raiz / "tests").glob("test_*.py"))
    if a.modulos:
        pedidos = {m if m.endswith(".py") else m + ".py" for m in a.modulos}
        todos = [m for m in todos if m in pedidos]
    trabajos = []
    for m in todos:
        aparte = COLGANTES.get(m)
        if aparte:
            trabajos.append((m, _nombres(raiz, m, aparte), a.tiempo))
            for x in aparte:
                trabajos.append((m + f" [solo {x}]", [x], a.tiempo_aparte))
        else:
            trabajos.append((m, [], a.tiempo))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"Raíz: {raiz} · {len(trabajos)} procesos · paralelo {a.paralelo}", flush=True)

    def correr(t):
        etiqueta, nombres, tiempo = t
        r = _ejecutar(raiz, etiqueta.split(" ")[0], nombres, tiempo)
        r["modulo"] = etiqueta
        print(f"  {r['estado']:<7} {etiqueta:<52} ran {r['ran']:>4}  fallos {r['fallos']}  errores {r['errores']}  omitidas {r['omitidas']}  {r['segundos']} s",
              flush=True)
        return r

    with ThreadPoolExecutor(max_workers=max(1, a.paralelo)) as pool:
        resultados = list(pool.map(correr, trabajos))
    total = {k: sum(r[k] for r in resultados) for k in ("ran", "fallos", "errores", "omitidas")}
    print(f"\nTOTAL ran {total['ran']} · fallos {total['fallos']} · errores {total['errores']} · omitidas {total['omitidas']}")
    anomalos = [r for r in resultados if r["estado"] in ("TIMEOUT", "CAIDO")]
    for r in anomalos:
        print(f"  {r['estado']}: {r['modulo']}")
    lista = sorted({f"{r['modulo']}: {x}" for r in resultados for x in r["lista"]})
    print("FAIL/ERROR:" if lista else "Sin FAIL ni ERROR.")
    for x in lista:
        print("  " + x)
    if a.json:
        a.json.write_text(json.dumps({"raiz": str(raiz), "total": total, "modulos": resultados}, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return 1 if lista or anomalos else 0


if __name__ == "__main__":
    sys.exit(main())
