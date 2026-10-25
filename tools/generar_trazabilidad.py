"""Genera la matriz requisito ↔ implementación ↔ prueba a partir del paquete y de los resultados.

Uso:  python tools/ejecutar_pruebas.py && python tools/generar_trazabilidad.py
Escribe docs/02_Alcance_implementable.md, docs/05_Trazabilidad.md y
docs/06_Declaracion_de_cobertura.md. Falla si algún requisito del paquete no está
clasificado o si algún caso carece de tratamiento explícito.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import paquete  # noqa: E402
from grafcet.declaration import coverage_declaration, render_markdown  # noqa: E402
from spec.clasificacion import CASOS, CATEGORIAS, REQ  # noqa: E402

DOCS = ROOT / "docs"


def case_status(cid: str, case: dict, results: list[dict]) -> tuple[str, str]:
    mine = [r for r in results if r["case"] == cid]
    kind, note = CASOS.get(cid, ("oraculo", ""))
    if not mine:
        if kind == "no-ejecutado":
            return "NO EJECUTADO", note
        return "SIN PRUEBA", "caso sin prueba asignada"
    if any(r["outcome"] != "pasa" for r in mine):
        return "FALLA", ", ".join(r["test"] for r in mine if r["outcome"] != "pasa")
    label = {"oraculo": f"PASA (oráculo {case['estado']})", "bloqueo-U": "BLOQUEO VERIFICADO",
             "decision": f"PASA SEGÚN DECISIÓN (en el documento 11: {case['estado']}, depende de U)",
             "parcial": "PARCIAL", "no-impl-bloqueo": "NO IMPLEMENTADO (bloqueo verificado)"}[kind]
    return label, note


def main() -> int:
    reqs = paquete.load_requirements()
    cases = paquete.load_cases()
    res_file = DOCS / "resultados_pruebas.json"
    if not res_file.exists():
        print("falta docs/resultados_pruebas.json: ejecute tools/ejecutar_pruebas.py")
        return 2
    run = json.loads(res_file.read_text(encoding="utf-8"))
    results = run["results"]
    problems = [f"requisito sin clasificar: {r}" for r in reqs if r not in REQ]
    problems += [f"clasificación de requisito inexistente: {r}" for r in REQ if r not in reqs]
    problems += [f"tratamiento de caso inexistente: {c}" for c in CASOS if c not in cases]

    status = {cid: case_status(cid, c, results) for cid, c in cases.items()}
    problems += [f"{cid}: {st}" for cid, (st, _) in status.items() if st in ("SIN PRUEBA", "FALLA")]
    supp = [r for r in results if r["case"] and r["case"].startswith("S-")]
    other = [r for r in results if not r["case"]]

    # Casos asociados a cada requisito: filas del requisito + filas de casos que lo citan + suplementarias
    linked: dict[str, list[str]] = {r: list(v["pruebas"]) for r, v in reqs.items()}
    for cid, c in cases.items():
        for r in c["reqs"]:
            if r in linked and cid not in linked[r]:
                linked[r].append(cid)
    for r in supp:
        for q in r["requirements"]:
            if q in linked and r["case"] not in linked[q]:
                linked[q].append(r["case"])
    short = {"PASA": "✔", "PASA SEGÚN DECISIÓN": "◆", "BLOQUEO VERIFICADO": "⛔", "PARCIAL": "◐", "NO IMPLEMENTADO (bloqueo verificado)": "∅",
             "NO EJECUTADO": "—", "FALLA": "✘", "SIN PRUEBA": "?"}

    def mark(cid: str) -> str:
        if cid.startswith("R-"):
            return f"{cid} (documental)"
        if cid.startswith("S-"):
            ok = all(r["outcome"] == "pasa" for r in supp if r["case"] == cid)
            return f"{cid} {'✔' if ok else '✘'}"
        st = status[cid][0]
        return f"{cid} {short.get(st.split(' (')[0] if st.startswith('PASA') else st, '?')}"

    cat_count = Counter(REQ[r][0] for r in reqs)
    st_count = Counter(s.split(" (")[0] for s, _ in status.values())
    head = (f"Generado el {run['date']} · Python {run['python']} · {run['platform']} · "
            f"{run['total']} pruebas ejecutadas, {run['failures']} fallos, {run['errors']} errores.")

    # --- 05 Trazabilidad
    L = ["# 05. Trazabilidad requisito ↔ implementación ↔ prueba", "",
         "Documento **generado** por `tools/generar_trazabilidad.py`; no editar a mano.", "", head, "",
         "Leyenda: ✔ pasa · ◆ pasa según una decisión del responsable sobre una U (no es el oráculo del "
         "documento 11, que pedía detener; contraste U-01 pendiente) · ⛔ bloqueo por U verificado (el oráculo "
         "semántico sigue abierto) · ◐ parcial · "
         "∅ capacidad no implementada en esta iteración (se verifica que no se ejecuta) · — no ejecutado · "
         "✘ falla. **Un ✔ con oráculo I es provisional (U-01): no prueba conformidad.**", "",
         "## Resumen", "", "| Categoría del requisito | Nº |", "|---|---|"]
    L += [f"| {CATEGORIAS[k]} (`{k}`) | {cat_count.get(k, 0)} |" for k in CATEGORIAS]
    L += ["", "| Estado de los 102 casos del documento 11 | Nº |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(st_count.items())]
    L += ["", f"Pruebas suplementarias S-xx: {len({r['case'] for r in supp})} casos, {len(supp)} pruebas, "
          f"{sum(r['outcome'] == 'pasa' for r in supp)} pasan.", ""]
    if problems:
        L += ["## Incidencias de trazabilidad", ""] + [f"- {p}" for p in problems] + [""]
    L += ["## Requisitos", "", "| Requisito | Clase/prio. | Doc. | Categoría | Implementación | Casos | Nota |",
          "|---|---|---|---|---|---|---|"]
    for rid in sorted(reqs, key=lambda r: (reqs[r]["doc"], r)):
        v = reqs[rid]
        cat, mods, note = REQ[rid]
        L.append(f"| {rid} | {v['clase']}/{v['prioridad']} | {v['doc']} | {cat} | {mods} | "
                 f"{', '.join(mark(c) for c in linked[rid])} | {note} |")
    L += ["", "## Casos del documento 11", "", "| Caso | Requisitos | Oráculo (11) | Resultado | Pruebas | Observación |",
          "|---|---|---|---|---|---|"]
    for cid in sorted(cases):
        st, note = status[cid]
        tests = ", ".join(f"`{r['test'].rsplit('.', 1)[-1]}`" for r in results if r["case"] == cid) or "—"
        L.append(f"| {cid} | {', '.join(cases[cid]['reqs'])} | {cases[cid]['estado']} | {st} | {tests} | {note} |")
    L += ["", "## Pruebas suplementarias (diseñadas por la implementación)", "",
          "No sustituyen oráculos del paquete; cubren hallazgos, bloqueos U y reglas P internas.", "",
          "| Caso | Requisitos | Resultado | Prueba | Descripción |", "|---|---|---|---|---|"]
    for r in sorted(supp, key=lambda r: r["case"]):
        L.append(f"| {r['case']} | {', '.join(r['requirements'])} | {r['outcome']} | `{r['test'].rsplit('.', 1)[-1]}` | "
                 f"{r['summary'].split(':', 1)[-1].strip()} |")
    if other:
        L += ["", "Pruebas sin caso asignado: " + ", ".join(r["test"] for r in other)]
    bi = paquete.bidirectional(reqs, cases)
    L += ["", "## Revisión bidireccional del paquete", "",
          "Referencias que el paquete declara en un solo sentido. No son errores: el documento 11 no exige "
          "simetría fila a fila. Se listan para que el revisor decida si deben completarse.", ""]
    for k, items in bi.items():
        L.append(f"- **{k}** ({len(items)}): " + (", ".join(f"{a}→{b}" for a, b in items) or "ninguna"))
    (DOCS / "05_Trazabilidad.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")

    # --- 02 Alcance implementable (propuesta para U-12)
    A = ["# 02. Alcance implementable sin cuestiones U (propuesta para cerrar U-12)", "",
         "Documento **generado** por `tools/generar_trazabilidad.py` desde `spec/clasificacion.py`.", "",
         "U-12 corresponde al responsable del proyecto: esta lista es una **propuesta** de subconjunto aprobable, "
         "con sus restricciones, y no modifica el manifiesto del paquete. Ningún elemento de la lista constituye "
         "conformidad.", "", "## Criterio", "",
         "- **P sin U**: implementable y verificable ya con oráculo P.",
         "- **I sin U propia**: implementable como perfil provisional. U-01 impide promoverlo a N, pero el oráculo I "
         "es concreto, así que implementarlo no resuelve ninguna U.",
         "- **Depende de U**: solo se implementa la detención diagnosticada. La implementación nunca elige una "
         "alternativa; si todas las lecturas posibles dan el mismo observable, el resultado no depende de la U y se "
         "acepta.",
         "- **Pendiente**: implementable, pero fuera de esta iteración (interfaz, plataforma, ejecución jerárquica).",
         "", "## Recuento", "", "| Categoría | Nº | Requisitos |", "|---|---|---|"]
    for k in CATEGORIAS:
        ids = sorted(r for r in reqs if REQ[r][0] == k)
        A.append(f"| {CATEGORIAS[k]} | {len(ids)} | {', '.join(ids)} |")
    A += ["", "## Restricciones de la propuesta", "",
          "1. Perfil `grafcet-impl-provisional`: ninguna capacidad «aprobada»; las I son provisionales.",
          "2. Formato 0.1 implementado como provisional hasta que se ratifique U-11.",
          "3. La duración de una etapa inicial cuenta desde τ=0 según T-12a/T-12c (tensión H-02). Si el revisor "
          "normativo extiende U-09 a este caso, la capacidad `temporal.duracion-etapa-inicial` pasa a no soportada.",
          "4. La coincidencia de lote y vencimiento se bloquea siempre (H-17). Es un sobrebloqueo consciente.",
          "5. La ejecución jerárquica (forzado, macroetapas, encapsulación) es la siguiente iteración. Su estructura ya "
          "se edita, guarda y valida (discriminante de U-12).",
          "", "Responsables según el paquete: decisiones P → responsable de producto; I/U → revisor normativo; "
          "evidencia → segunda IA y revisor de pruebas.", ""]
    (DOCS / "02_Alcance_implementable.md").write_text("\n".join(A) + "\n", encoding="utf-8", newline="\n")
    (DOCS / "06_Declaracion_de_cobertura.md").write_text(render_markdown(coverage_declaration()), encoding="utf-8", newline="\n")
    for p in problems:
        print("INCIDENCIA:", p)
    print(f"requisitos {len(reqs)} · casos {len(cases)} · categorías {dict(cat_count)} · estados {dict(st_count)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
