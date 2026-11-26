"""Normalización de textos y valores al abrir el editor."""
from __future__ import annotations

import re
from typing import Any
from grafcet.diagnostics import DiagnosticError
from grafcet.values import format_value, parse_type, parse_value, zero
from ..bloques import sin_comillas
from .constantes import CODIGOS


def quitar_comillas_vista(M: dict[str, Any]) -> bool:
    """Lo que se dibuja de una fórmula que no se interpreta (a medias, con un «?») es su texto del núcleo: sin las comillas
    invertidas de los nombres con espacios, que el usuario no ve ni teclea. Devuelve si cambió algún texto (entonces cambia el
    ancho de las cajas y hay que volver a calcular los recorridos)."""
    cambio = False

    def segmentos(lista: Any) -> None:
        nonlocal cambio
        for seg in lista or []:
            if isinstance(seg, dict) and isinstance(seg.get("t"), str) and "`" in seg["t"]:
                seg["t"] = sin_comillas(seg["t"])
                cambio = True
    for t in M.get("transitions", []):
        segmentos(t.get("cond"))
    for s in M.get("steps", []):
        for a in s.get("actions", []):
            for campo in ("text", "cond", "event"):
                segmentos(a.get(campo))
    return cambio


def sin_codigos(texto: str) -> str:
    """El texto sin códigos internos (D-…, U-…, H-…, REQ-…, P-IMP-…) ni etiquetas de capacidad entre corchetes:
    «D-REF: no existe X» es «no existe X»; el código sigue en el objeto diagnóstico, no en lo que se enseña."""
    if not texto:
        return texto
    return re.sub(r"\s{2,}", " ", CODIGOS.sub("", texto)).strip()


def quitar_valores_iniciales(doc: dict[str, Any]) -> list[str]:
    """P-IMP-117: todas las variables empiezan en 0 (falso). Pone a cero los valores iniciales declarados en `doc` (un
    fichero hecho a mano o por otra herramienta) y devuelve una frase por variable cambiada, p. ej. «N empezaba en 3»."""
    quitadas = []
    for v in doc.get("variables", []):
        try:
            t = parse_type(v["type"])
            if parse_value(t, v["initialValue"]) == zero(t):
                continue
            antes = v["initialValue"]
            v["initialValue"] = format_value(t, zero(t))
        except (DiagnosticError, KeyError, TypeError, ValueError):
            continue  # un fichero mal formado lo informa la validación
        texto = {True: "verdadero", False: "falso"}.get(antes, antes)
        quitadas.append(f"{v['name']} empezaba en {texto}")
    return quitadas


def aviso_valores_iniciales(quitadas: list[str]) -> str:
    return (f"Valores iniciales quitados: {'; '.join(quitadas)}. En GRAFCET Connect todas las variables empiezan en 0; "
            "si la condición necesita un número, escríbelo en la receptividad (por ejemplo C = 3).")
