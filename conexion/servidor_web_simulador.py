"""Localización por contenido y activación conservadora del servidor web del simulador."""
from dataclasses import dataclass
import ctypes
import os
from pathlib import Path
import re
import tempfile

PATRON = re.compile(r"(?im)^([ \t]*app[ \t]*\.[ \t]*web_server[ \t]*=[ \t]*)([^\r\n#;]*)([^\r\n]*)")


@dataclass(frozen=True)
class Resultado:
    correcto: bool
    motivo: str
    carpeta: Path | None = None
    cambiado: bool = False
    ambiguo: bool = False


def documentos_usuario():
    """Documentos de esta cuenta, con su redirección de Windows; no se supone una ruta bajo HOME."""
    if os.name != "nt":
        raise OSError("No se pudo localizar Documentos: esta operación requiere Windows")
    ruta = ctypes.create_unicode_buffer(32768)
    codigo = ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, ruta)
    if codigo != 0 or not ruta.value:
        raise OSError("No se pudo localizar la carpeta Documentos del usuario")
    return Path(ruta.value)


def localizar(documentos=None):
    documentos = Path(documentos) if documentos is not None else documentos_usuario()
    if not documentos.is_dir():
        return Resultado(False, "No se encuentra la carpeta Documentos del usuario")
    candidatas = [p for p in documentos.iterdir() if p.is_dir() and (p / "My Scenes").is_dir()]
    if len(candidatas) > 1:
        preferidas = [p for p in candidatas if (p / "CertificatesStore").is_dir()
                      or (p / "Screenshots").is_dir() or (p / "auto.cfg").is_file()]
        candidatas = preferidas or candidatas
    if len(candidatas) == 1:
        return Resultado(True, "Carpeta reconocida por su contenido", candidatas[0])
    if candidatas:
        return Resultado(False, "Hay varias carpetas con la firma del simulador; no se ha escrito nada", ambiguo=True)
    return Resultado(False, "No se encontró una carpeta con My Scenes en Documentos")


def buscar_carpeta(documentos=None) -> Path | None:
    """El motivo de una búsqueda sin resultado está disponible en localizar()."""
    return localizar(documentos).carpeta


def _decodificar(datos):
    for bom, codificacion in ((b"\xff\xfe\x00\x00", "utf-32-le"), (b"\x00\x00\xfe\xff", "utf-32-be"),
                              (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"),
                              (b"\xef\xbb\xbf", "utf-8")):
        if datos.startswith(bom):
            return bom, codificacion, datos[len(bom):].decode(codificacion)
    if b"\x00" in datos:
        raise ValueError("No se reconoce la codificación de auto.cfg; no se ha modificado")
    # Vista reversible de bytes: UTF-8 y páginas de códigos conservan incluso los bytes ajenos a la orden.
    return b"", "latin-1", datos.decode("latin-1")


def _preparar(datos):
    bom, codificacion, texto = _decodificar(datos)
    asignaciones = list(PATRON.finditer(texto))
    if asignaciones and all(m.group(2).strip().casefold() == "true" for m in asignaciones):
        return datos
    if asignaciones:
        def reemplazar(m):
            if m.group(2).strip().casefold() == "true":
                return m.group(0)
            valor = m.group(2)
            margen = valor[len(valor.rstrip(" \t")):]
            return m.group(1) + "True" + margen + m.group(3)
        texto = PATRON.sub(reemplazar, texto)
    else:
        salto = next(iter(re.findall(r"\r\n|\n|\r", texto)), "\r\n")
        if texto and not texto.endswith(("\n", "\r")):
            texto += salto
        texto += "app.web_server = True" + salto
    return bom + texto.encode(codificacion)


def estado(documentos=None):
    resultado = localizar(documentos)
    if resultado.carpeta is None:
        return "varias" if resultado.ambiguo else "sin_carpeta"
    archivo = resultado.carpeta / "auto.cfg"
    if not archivo.exists():
        return "falta"
    datos = archivo.read_bytes()
    _, _, texto = _decodificar(datos)
    asignaciones = list(PATRON.finditer(texto))
    return "activo" if asignaciones and all(m.group(2).strip().casefold() == "true" for m in asignaciones) else "falta"


def _guardar(archivo, anterior, nuevo):
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(dir=archivo.parent, prefix=".auto-", suffix=".tmp", delete=False) as f:
            temporal = Path(f.name)
            f.write(nuevo)
        actual = archivo.read_bytes() if archivo.exists() else None
        if actual != anterior:
            raise OSError("auto.cfg cambió durante la operación; no se ha sobrescrito")
        os.replace(temporal, archivo)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)


def activar(documentos=None):
    try:
        resultado = localizar(documentos)
        if not resultado.correcto:
            return resultado
        archivo = resultado.carpeta / "auto.cfg"
        anterior = archivo.read_bytes() if archivo.exists() else None
        nuevo = _preparar(anterior or b"")
        if anterior == nuevo:
            return Resultado(True, "El servidor web ya está activado en su configuración", resultado.carpeta)
        _guardar(archivo, anterior, nuevo)
        return Resultado(True, "Servidor web activado", resultado.carpeta, True)
    except (OSError, UnicodeError, ValueError) as exc:
        return Resultado(False, f"No se pudo activar el servidor web: {motivo_error(exc)}")


def motivo_error(exc):
    """Explica el fallo sin incluir rutas que contengan el nombre de la carpeta del simulador."""
    if isinstance(exc, OSError):
        return exc.strerror or str(exc.args[0]) if exc.args else "Error de acceso a auto.cfg"
    return str(exc)
