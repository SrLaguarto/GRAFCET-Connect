"""Reconocimiento neutral de las señales de sistema y nombres automáticos."""
import re


def interna(senal):
    nombre = senal.get("_nombre_original", senal["name"])
    return "I/O (" in nombre and senal.get("address") in (240, 496, 497, 498)


def nombre_visible(senal):
    nombre = senal["name"]
    if interna(senal):
        original = senal.get("_nombre_original", nombre)
        return "Simulador (" + original.split("I/O (", 1)[1]
    return nombre


def de_fabrica(nombre):
    return re.search(r"\d+\s*(?:\([^)]*\)\s*)?$", nombre) is not None
