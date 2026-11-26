"""Contenedor GRAFNET: ZIP versionado, sello canónico y sustitución atómica. Sin Qt."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
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
INFO = '_grafnet/info.json'  # opcional: autor, fechas y versiones del programa; sellada como el resto
FORMATO_VERSION = 1
CAMPOS_INFO = ('autor', 'creado', 'modificado', 'version_creacion', 'version_guardado')
MAX_INFO = 4096
MAX_CAMPO_INFO = 500
MAX_AUTOR = 60
MAX_HISTORIAL_AUTORES = 20
HISTORIAL_AUTORES = 'historial_autores'
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


def _escribir_zip(entradas):
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in sorted(entradas.items()):
            z.writestr(nombre, datos)
    if salida.getbuffer().nbytes > MAX_BYTES:
        raise ErrorContenedor("El archivo supera el tamaño permitido")
    return salida.getvalue()


def empaquetar(raiz: Path, clave: bytes | None, info: bytes | None = None) -> bytes:
    """`clave` None: el archivo se escribe sin sello (un archivo abierto sin firma válida no se firma al guardarlo)."""
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
    if info is not None:
        entradas[INFO] = info
    if len(entradas) > MAX_ENTRADAS or sum(map(len,entradas.values())) > MAX_BYTES:
        raise ErrorContenedor('El proyecto supera el tamaño permitido')
    if clave is not None:
        entradas[SELLO] = _firma(entradas, clave)
    return _escribir_zip(entradas)


def _leer_entradas(datos: bytes) -> dict:
    """Entradas del ZIP (con el sello, sin verificarlo) tras comprobar rutas, tamaños y versión del contenedor."""
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
    if version != {'format':'grafnet','version':FORMATO_VERSION}:
        raise ErrorContenedor('Versión de contenedor .grafnet no compatible')
    return entradas


def _info_valida(datos: bytes | None) -> dict:
    """Metadatos de `_grafnet/info.json`; si faltan o están mal formados, {} (datos desconocidos, no un rechazo)."""
    if datos is None or len(datos) > MAX_INFO:
        return {}
    try:
        info = json.loads(datos)
    except (ValueError, UnicodeError, RecursionError):
        return {}
    if not isinstance(info, dict):
        return {}
    limpia = {}
    for campo in CAMPOS_INFO:
        if campo not in info:
            continue
        valor = info[campo]
        if not isinstance(valor, str) or len(valor) > MAX_CAMPO_INFO:
            return {}
        if campo in ('creado', 'modificado'):
            try:
                datetime.fromisoformat(valor)
            except ValueError:
                return {}
        limpia[campo] = valor
    historial = _historial_valido(info.get(HISTORIAL_AUTORES))
    if historial:
        limpia[HISTORIAL_AUTORES] = historial
    return limpia


def _fecha_historial(valor: str) -> datetime:
    fecha = datetime.fromisoformat(valor)
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


def _historial_valido(historial) -> list[dict]:
    """Valida el campo por separado y devuelve copias en orden de guardado."""
    if not isinstance(historial, list) or len(historial) > MAX_HISTORIAL_AUTORES:
        return []
    resultado = []
    for entrada in historial:
        if not isinstance(entrada, dict) or entrada.keys() != {'autor', 'desde', 'hasta'}:
            return []
        if not isinstance(entrada['autor'], str) or len(entrada['autor']) > MAX_AUTOR:
            return []
        desde, hasta = entrada['desde'], entrada['hasta']
        if not all(isinstance(fecha, str) and len(fecha) <= 42 for fecha in (desde, hasta)):
            return []
        try:
            entrada['autor'].encode('utf-8')
            if _fecha_historial(desde) > _fecha_historial(hasta):
                return []
        except ValueError:
            return []
        resultado.append(entrada.copy())
    return resultado


def huella(entradas: dict) -> str:
    """SHA-256 (hex) de las entradas selladas, en el orden canónico del sello y sin él. No usa la clave."""
    h = hashlib.sha256()
    for nombre, datos in sorted(entradas.items()):
        if nombre == SELLO:
            continue
        n = nombre.encode('utf-8')
        h.update(len(n).to_bytes(8, 'big'))
        h.update(n)
        h.update(len(datos).to_bytes(8, 'big'))
        h.update(datos)
    return h.hexdigest()


def construir_info(previa: dict | None, autor: str, version: str, ahora: datetime | None = None) -> dict:
    """Metadatos de un guardado. `previa` None = proyecto nuevo (se fijan creado y version_creacion); un dict, aunque
    esté vacío (archivo anterior a la 1.0), conserva lo que traiga y no inventa lo que falte."""
    fecha = (ahora or datetime.now().astimezone()).isoformat(timespec='seconds')
    autor = _texto_utf8(autor[:MAX_AUTOR])
    version = _texto_utf8(version[:MAX_CAMPO_INFO])
    info = {'autor': autor}
    if previa is None:
        info['creado'] = fecha
        info['version_creacion'] = version
    else:
        for campo in ('creado', 'version_creacion'):
            if campo in previa:
                info[campo] = _texto_utf8(previa[campo])
    info['modificado'] = fecha
    info['version_guardado'] = version
    historial = _historial_valido((previa or {}).get(HISTORIAL_AUTORES))
    if historial and historial[-1]['autor'] == autor:
        historial[-1]['hasta'] = max(historial[-1]['hasta'], fecha, key=_fecha_historial)
    else:
        historial.append({'autor': autor, 'desde': fecha, 'hasta': fecha})
    if len(historial) > MAX_HISTORIAL_AUTORES:
        del historial[1:len(historial) - MAX_HISTORIAL_AUTORES + 1]
    info[HISTORIAL_AUTORES] = historial
    _ajustar_tamano_info(info)
    return info


def _texto_utf8(texto: str) -> str:
    return texto.encode('utf-8', errors='replace').decode('utf-8')


def _ajustar_tamano_info(info: dict) -> None:
    historial = info[HISTORIAL_AUTORES]
    while len(historial) > 2 and len(serializar_info(info)) >= MAX_INFO:
        del historial[1]
    # Un campo antiguo de versión puede ocupar muchos bytes en JSON. Reserva espacio para ambos extremos del historial.
    for campo in ('version_creacion', 'version_guardado'):
        exceso = len(serializar_info(info)) - MAX_INFO + 1
        if exceso > 0 and campo in info:
            info[campo] = info[campo][:-exceso]


def serializar_info(info: dict) -> bytes:
    legible = (json.dumps(info, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    if len(legible) < MAX_INFO:
        return legible
    return (json.dumps(info, ensure_ascii=False, separators=(',', ': '), sort_keys=True) + '\n').encode('utf-8')


@dataclass
class Extraccion:
    valido: bool
    info: dict
    huella: str


def inspeccionar(datos: bytes) -> tuple[dict, str]:
    """Metadatos y huella de un contenedor, sin verificar el sello ni extraer nada."""
    entradas = _leer_entradas(datos)
    return _info_valida(entradas.get(INFO)), huella(entradas)


def sello_valido(datos: bytes, clave: bytes) -> bool:
    entradas = _leer_entradas(datos)
    sello = entradas.pop(SELLO, b'')
    return hmac.compare_digest(sello, _firma(entradas, clave))


def resellar(datos: bytes, clave: bytes) -> bytes:
    """Mismo contenido con el sello calculado con otra clave. No comprueba el sello anterior: lo hace el llamador."""
    entradas = _leer_entradas(datos)
    entradas.pop(SELLO, None)
    entradas[SELLO] = _firma(entradas, clave)
    return _escribir_zip(entradas)


def extraer_completo(datos: bytes, raiz: Path, clave: bytes, politica: str) -> Extraccion:
    """Verifica antes de extraer. Con política «importar» un sello no válido no rechaza (el llamador debe avisar)."""
    if politica not in ('rechazar', 'importar'):
        raise ValueError('Política de sello no válida')
    entradas = _leer_entradas(datos)
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
    return Extraccion(valido, _info_valida(entradas.get(INFO)), huella(entradas))


def extraer(datos: bytes, raiz: Path, clave: bytes, politica: str) -> bool:
    """Verifica antes de extraer. Devuelve True si el sello es válido; importar exige aviso del llamador."""
    return extraer_completo(datos, raiz, clave, politica).valido


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
