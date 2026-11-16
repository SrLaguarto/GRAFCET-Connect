"""Operaciones sin interfaz, resueltas antes de cargar ventana, instancia o actualizaciones."""
import sys
import tempfile
from pathlib import Path

from conexion import servidor_web_simulador as servidor

ARGUMENTO = "--activar-servidor-simulador"
PRUEBA = "--prueba-servidor-simulador"


def despachar(argv=None, documentos=None):
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if argumentos == [ARGUMENTO]:
        return 0 if servidor.activar(documentos).correcto else 2
    if argumentos == [PRUEBA]:
        return comprobar_empaquetado()
    return None


def comprobar_empaquetado():
    """La misma ruta del argumento del instalador, inyectando Documentos temporal; nunca usa los reales."""
    with tempfile.TemporaryDirectory(prefix="grafconnect-servidor-") as carpeta:
        documentos = Path(carpeta)
        simulador = documentos / "planta"
        (simulador / "My Scenes").mkdir(parents=True)
        (simulador / "CertificatesStore").mkdir()
        codigo = despachar([ARGUMENTO], documentos)
        datos = (simulador / "auto.cfg").read_bytes()
        return 0 if codigo == 0 and datos == b"app.web_server = True\r\n" else 3
