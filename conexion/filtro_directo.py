"""Selección de señales excluidas por identidad, sin alterar las uniones existentes."""
from copy import deepcopy
from uuid import UUID

from .catalogo_directo import interna


def id_valido(texto):
    try:
        return isinstance(texto, str) and str(UUID(texto)) == texto.lower()
    except (ValueError, AttributeError):
        return False


def actualizar(config, catalogo):
    anteriores = config.filtro_senales if config.recordar_filtro else []
    filas = {f["id"]: deepcopy(f) for f in anteriores}
    for senal in catalogo:
        identidad = senal["id"]
        if identidad not in filas and interna(senal):
            filas[identidad] = dict(id=identidad, excluir=True)
        if identidad in filas:
            filas[identidad].update(nombre=senal["name"], tipo=senal["type"])
    config.filtro_senales = list(filas.values())


def excluida(config, senal):
    if any(u.id == senal["id"] for u in config.uniones):
        return False
    fila = next((f for f in config.filtro_senales if f["id"] == senal["id"]), None)
    return bool(fila["excluir"]) if fila else interna(senal)


def anadir(config, identidad, catalogo):
    identidad = identidad.strip().lower()
    if not id_valido(identidad):
        raise ValueError("Escriba un ID válido: 32 cifras hexadecimales en grupos 8-4-4-4-12")
    if any(f["id"].lower() == identidad and not f.get("quitada", False) for f in config.filtro_senales):
        raise ValueError("Ese ID ya está en la lista")
    config.filtro_senales = [f for f in config.filtro_senales if f["id"].lower() != identidad]
    fila = dict(id=identidad, excluir=True)
    senal = next((s for s in catalogo if s["id"].lower() == identidad), None)
    if senal:
        fila.update(nombre=senal["name"], tipo=senal["type"])
    config.filtro_senales.append(fila)


def quitar(config, identidad):
    for fila in config.filtro_senales:
        if fila["id"] == identidad:
            fila.update(excluir=False, quitada=True)


def validar(config):
    if type(config.recordar_filtro) is not bool or not isinstance(config.filtro_senales, list):
        raise ValueError("Filtro de señales inválido")
    ids = set()
    for fila in config.filtro_senales:
        if (not isinstance(fila, dict) or not isinstance(fila.get("id"), str) or not fila["id"]
                or type(fila.get("excluir")) is not bool or fila["id"] in ids
                or type(fila.get("quitada", False)) is not bool
                or not isinstance(fila.get("nombre", ""), str) or not isinstance(fila.get("tipo", ""), str)):
            raise ValueError("Identidad o selección del filtro inválida")
        ids.add(fila["id"])
