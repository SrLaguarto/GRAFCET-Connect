"""Reconocimiento neutral de las señales de sistema y nombres automáticos."""
import re


def interna(senal):
    return (senal.get("_sistema", False) or senal.get("address") in (240, 496, 497, 498)
            or re.match(r"^[A-Z][A-Z\d_]*\s*\(", senal["name"]) is not None)


def nombre_visible(senal):
    nombre = senal["name"]
    if interna(senal):
        return re.sub(r"^[A-Z][A-Z\d_]*\s*(?=\()", "Simulador ", nombre)
    return nombre


def de_fabrica(nombre):
    return re.search(r"\d+\s*(?:\([^)]*\)\s*)?$", nombre) is not None
