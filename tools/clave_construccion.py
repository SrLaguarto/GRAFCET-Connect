"""Preparación aislada de la clave de una construcción; nunca se guarda en el árbol de trabajo."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile


class ErrorClave(ValueError):
    pass


def obtener_clave(raiz, archivo=None, desarrollo=False):
    if desarrollo:
        if archivo or os.environ.get('GRAFCONNECT_CLAVE_SELLO'):
            raise ErrorClave('No combine construcción de desarrollo con una clave de distribución')
        return None
    if archivo:
        ruta=Path(archivo).resolve()
        if ruta.is_relative_to(Path(raiz).resolve()):
            raise ErrorClave('El archivo de clave debe estar fuera del repositorio')
        try:clave=ruta.read_bytes()
        except OSError as exc:raise ErrorClave('No se pudo leer el archivo externo de clave') from None
    else:
        clave=os.environ.get('GRAFCONNECT_CLAVE_SELLO','').encode('utf-8')
    if len(clave)<32:
        raise ErrorClave('La construcción repartible requiere una clave de al menos 32 bytes: GRAFCONNECT_CLAVE_SELLO o --archivo-clave. Para una construcción de desarrollo use --desarrollo.')
    return clave


@contextmanager
def fuentes_aisladas(raiz,clave):
    with tempfile.TemporaryDirectory(prefix='grafconnect-fuentes-') as tmp:
        dst=Path(tmp)
        for nombre in ('escritorio','grafcet','conexion'):
            shutil.copytree(Path(raiz)/nombre,dst/nombre,ignore=shutil.ignore_patterns('__pycache__','_clave_sello.py','*.pyc'))
        if clave is not None:
            p=dst/'escritorio'/'_clave_sello.py'
            p.write_text('CLAVE = bytes.fromhex('+repr(clave.hex())+')\n',encoding='utf-8')
        try:yield dst
        finally:
            (dst/'escritorio'/'_clave_sello.py').unlink(missing_ok=True)
