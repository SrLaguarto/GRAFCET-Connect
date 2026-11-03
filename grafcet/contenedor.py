"""Contenedor GRAFNET: ZIP versionado, sello canónico y sustitución atómica. Sin Qt."""
from __future__ import annotations
import hashlib
import hmac
import io
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile
import zlib

VERSION = '_grafnet/version.json'
SELLO = '_grafnet/sello.sha256'
MAX_BYTES = 512 * 1024 * 1024
MAX_ENTRADAS = 10000


class ErrorContenedor(ValueError):
    pass


def _nombre(nombre):
    p = PurePosixPath(nombre)
    if (not nombre or '\\' in nombre or ':' in nombre or p.is_absolute()
            or any(x in ('', '.', '..') for x in nombre.split('/'))):
        raise ErrorContenedor('El archivo contiene una ruta no válida')
    return p


def _firma(entradas, clave):
    if not isinstance(clave, bytes) or len(clave) < 32:
        raise ValueError('La clave del sello debe tener al menos 32 bytes')
    mac = hmac.new(clave, digestmod=hashlib.sha256)
    for nombre, datos in sorted(entradas.items()):
        n = nombre.encode('utf-8')
        mac.update(len(n).to_bytes(8, 'big'));mac.update(n)
        mac.update(len(datos).to_bytes(8, 'big'));mac.update(datos)
    return mac.hexdigest().encode('ascii')


def empaquetar(raiz: Path, clave: bytes) -> bytes:
    entradas = {}
    raiz = Path(raiz)
    for p in raiz.rglob('*'):
        if p.is_symlink():
            raise ErrorContenedor('No se admiten recursos enlazados fuera del proyecto')
        if p.is_file():
            nombre = p.relative_to(raiz).as_posix();_nombre(nombre)
            if nombre.startswith('_grafnet/'):
                continue
            entradas[nombre] = p.read_bytes()
    if 'manifest.json' not in entradas:
        raise ErrorContenedor('El proyecto no contiene manifest.json')
    entradas[VERSION] = b'{"format":"grafnet","version":1}\n'
    if len(entradas) > MAX_ENTRADAS or sum(map(len,entradas.values())) > MAX_BYTES:
        raise ErrorContenedor('El proyecto supera el tamaño permitido')
    entradas[SELLO] = _firma(entradas, clave)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in sorted(entradas.items()):
            z.writestr(nombre, datos)
    if salida.getbuffer().nbytes>MAX_BYTES:raise ErrorContenedor("El archivo supera el tamaño permitido")
    return salida.getvalue()


def extraer(datos: bytes, raiz: Path, clave: bytes, politica: str) -> bool:
    """Verifica antes de extraer. Devuelve True si el sello es válido; importar exige aviso del llamador."""
    if politica not in ('rechazar', 'importar'):
        raise ValueError('Política de sello no válida')
    if len(datos) > MAX_BYTES:
        raise ErrorContenedor('El archivo supera el tamaño permitido')
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            infos = z.infolist()
            if len(infos) > MAX_ENTRADAS or sum(i.file_size for i in infos) > MAX_BYTES:
                raise ErrorContenedor('El contenido supera el tamaño permitido')
            entradas = {}
            for i in infos:
                nombre=i.orig_filename.rstrip('/') if i.is_dir() else i.orig_filename
                _nombre(nombre)
                if nombre in entradas or (i.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ErrorContenedor('El archivo contiene entradas repetidas o enlaces no válidos')
                if i.is_dir():continue
                entradas[nombre]=z.read(i)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, zlib.error, EOFError) as exc:
        raise ErrorContenedor('El archivo .grafnet está dañado o no es compatible') from exc
    try:
        version=json.loads(entradas[VERSION])
    except (KeyError, ValueError, UnicodeError) as exc:
        raise ErrorContenedor('Falta la versión del contenedor .grafnet o no es válida') from exc
    if version != {'format':'grafnet','version':1}:
        raise ErrorContenedor('Versión de contenedor .grafnet no compatible')
    sello=entradas.pop(SELLO,b'')
    valido=hmac.compare_digest(sello,_firma(entradas,clave))
    if not valido and politica == 'rechazar':
        raise ErrorContenedor('El sello de integridad falta o no es válido. El archivo no se ha abierto.')
    if 'manifest.json' not in entradas:
        raise ErrorContenedor('El archivo no contiene un proyecto')
    raiz=Path(raiz)
    for nombre, contenido in entradas.items():
        if nombre.startswith('_grafnet/'):continue
        destino=raiz.joinpath(*_nombre(nombre).parts)
        if not destino.resolve().is_relative_to(raiz.resolve()):
            raise ErrorContenedor('Ruta de recurso fuera del proyecto')
        destino.parent.mkdir(parents=True,exist_ok=True);destino.write_bytes(contenido)
    return valido


def guardar_atomico(destino: Path, datos: bytes) -> None:
    destino=Path(destino)
    destino.parent.mkdir(parents=True,exist_ok=True)
    fd,nombre=tempfile.mkstemp(prefix='.'+destino.name+'-',suffix='.tmp',dir=destino.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(datos);f.flush();os.fsync(f.fileno())
        os.replace(nombre,destino)
    finally:
        Path(nombre).unlink(missing_ok=True)
