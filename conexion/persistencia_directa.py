"""Recurso adicional que las versiones anteriores del proyecto pueden ignorar."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .uniones import Union


def recurso(ruta):
    identidad = hashlib.sha256(Path(ruta).name.encode("utf-8")).hexdigest()[:16]
    return Path(ruta).with_name(f"conexion-directa-{identidad}.json")


def guardar(config, ruta, documento):
    destino = recurso(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    uniones = []
    for union in config.uniones:
        datos = asdict(union)
        datos.pop("motivo")
        uniones.append(datos)
    datos = {"version": 1, "modelo": documento["id"], "uniones": uniones}
    fd, temporal = tempfile.mkstemp(dir=destino.parent, prefix=destino.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, destino)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def cargar(config, ruta, documento):
    origen = recurso(ruta)
    if not origen.exists():
        return config
    try:
        datos = json.loads(origen.read_text(encoding="utf-8"))
        if datos["version"] != 1 or datos["modelo"] != documento["id"]:
            raise ValueError("El recurso de uniones pertenece a otro modelo o versión")
        config.uniones = [Union(**union) for union in datos["uniones"]]
        config.validar(documento)
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError("Recurso de uniones inválido") from exc
    return config
