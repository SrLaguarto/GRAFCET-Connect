"""Ayudas de presentación: la validación sigue perteneciendo a Edicion."""
import re

from grafcet.ids import MAX_LABEL, label_key


SIGNOS = {".": "punto", "(": "paréntesis", ")": "paréntesis", "/": "barra", "\\": "barra",
          ":": "dos puntos", ",": "coma", "&": "signo &", "!": "exclamación", "?": "interrogación"}


def aviso_corto(nombre, motivo):
    signos = list(dict.fromkeys(SIGNOS.get(c, f"signo «{c}»") for c in nombre
                                if not (c.isalnum() or c in "_ +-")))
    if signos and "símbolos" in motivo:
        return f"No se admite: {signos[0]}."
    if "existe" in motivo or "mismo nombre" in motivo or "Ya hay" in motivo:
        return "Ese nombre ya existe."
    if "espacio" in motivo:
        return "Revisa los espacios."
    if "Falta" in motivo:
        return "Escribe un nombre."
    if "duración" in motivo or "número" in motivo:
        return "Añade letras al nombre."
    if "etapa" in motivo:
        return "Se confunde con una etapa."
    if "fórmulas" in motivo:
        return "Palabra reservada."
    return "Revisa el nombre."


def resumen_nombres(filas):
    if not filas:
        return ""
    signos = list(dict.fromkeys(SIGNOS.get(c, f"signo «{c}»") for f in filas if "símbolos" in f.motivo for c in f.nombre
                                if not (c.isalnum() or c in "_ +-")))
    if signos:
        sujeto = "1 nombre lleva" if len(filas) == 1 else f"{len(filas)} nombres llevan"
        return f"{sujeto} un signo que no se puede usar: {', '.join(signos)}."
    return "1 nombre por corregir." if len(filas) == 1 else f"{len(filas)} nombres por corregir."


def corregir_nombres(propuestas):
    """Corrige solo las filas pendientes; reserva también nombres de filas sin marcar."""
    propuestas.validar()
    pendientes = [f for f in propuestas.elegidas() if f.motivo]
    ocupados = {label_key(v["name"]) for v in propuestas.edicion.ed.model["variables"]}
    ocupados.update(label_key(f.nombre) for f in propuestas.filas if f not in pendientes)
    for fila in pendientes:
        anterior = fila.nombre
        base = " ".join(re.sub(r"[^\w +\-]", " ", fila.nombre).split())
        base = base.lstrip("+-")[:MAX_LABEL].strip() or "Variable"
        if propuestas.edicion.motivo_nombre(base):
            base = f"Variable {base}"[:MAX_LABEL]
        # Una palabra que empieza por X puede seguir siendo ambigua en un nombre compuesto.
        if propuestas.edicion.motivo_nombre(base):
            base = "Variable"
        nombre = base
        numero = 2
        while label_key(nombre) in ocupados or propuestas.edicion.motivo_variable_nueva(nombre):
            sufijo = f" {numero}"
            nombre = base[:MAX_LABEL - len(sufijo)].rstrip() + sufijo
            numero += 1
        fila.nombre = nombre
        fila.cambiado = fila.cambiado or (nombre != anterior)
        ocupados.add(label_key(nombre))
    propuestas.validar()
