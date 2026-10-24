"""Declaración de base normativa, perfil y cobertura (REQ-NOR-01, REQ-NOR-02, REQ-ALC-03).

La declaración nunca afirma conformidad: enumera cada capacidad con su estado y excluye
explícitamente toda materia con una cuestión U crítica pendiente.
"""
from __future__ import annotations

from typing import Any

from .profile import APP_VERSION, CAPABILITIES, FINDINGS, FORMAT_VERSION, NORMATIVE_BASE, PROFILE_ID, \
    PROFILE_VERSION, U_REGISTRY

CRITICAL_U = {"U-01", "U-03", "U-04", "U-05", "U-06", "U-07", "U-08", "U-09", "U-12"}


def coverage_declaration() -> dict[str, Any]:
    caps = sorted(CAPABILITIES.values(), key=lambda c: c.id)
    excluded = [c for c in caps if c.status != "aprobada" and any(u in c.reason for u in CRITICAL_U - {"U-01"})]
    return {
        "conformityClaimed": False,
        "statement": ("No se declara conformidad con IEC 60848:2013 ni con UNE-EN 60848:2022. Ninguna capacidad está "
                      "aprobada: las capacidades I son provisionales por U-01 y las que dependen de una cuestión "
                      "abierta están bloqueadas. No se afirma certificación, aprobación UNE ni seguridad funcional."),
        "normativeBase": NORMATIVE_BASE,
        "versions": {"format": FORMAT_VERSION, "application": APP_VERSION, "profile": f"{PROFILE_ID}@{PROFILE_VERSION}",
                     "standard": f"{NORMATIVE_BASE['standard']}:2013 ed. {NORMATIVE_BASE['edition']}"},
        "capabilities": [{"id": c.id, "status": c.status, "reason": c.reason, "requirements": list(c.requirements),
                          "description": c.description} for c in caps],
        "excludedMatters": [{"capability": c.id, "question": c.reason} for c in excluded],
        "openQuestions": U_REGISTRY,
        "findings": FINDINGS,
    }


def render_markdown(decl: dict[str, Any]) -> str:
    status_es = {"provisional": "provisional (especificada, sin contraste normativo)", "no-soportada": "pendiente / bloqueada",
                 "aprobada": "aprobada"}
    lines = ["# 06. Declaración de cobertura", "",
             "Documento generado por `tools/generar_trazabilidad.py` a partir de `grafcet/profile.py`.", "",
             f"**{decl['statement']}**", "",
             "| Eje de versión | Valor |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in decl["versions"].items()]
    lines += ["", f"Base normativa declarada: {decl['normativeBase']['standard']} edición {decl['normativeBase']['edition']} "
              f"({decl['normativeBase']['publication']}), adopción {decl['normativeBase']['adoption']}. No se sustituye "
              "silenciosamente (REQ-NOR-01).", "", "## Capacidades", "",
              "| Capacidad | Estado | Motivo | Requisitos |", "|---|---|---|---|"]
    for c in decl["capabilities"]:
        lines.append(f"| `{c['id']}` — {c['description']} | {status_es[c['status']]} | {c['reason']} | "
                     f"{', '.join(c['requirements'])} |")
    lines += ["", "## Materias excluidas por cuestiones críticas abiertas (REQ-NOR-02)", ""]
    lines += [f"- `{x['capability']}`: {x['question']}" for x in decl["excludedMatters"]]
    lines.append("")
    return "\n".join(lines)
