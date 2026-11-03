"""Conversión de datos JSON de prueba al archivo que admite la interfaz; no forma parte de la aplicación."""
import atexit
from pathlib import Path
import sys
import tempfile
import uuid
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from grafcet.persistence import open_project,open_model,new_project,add_document
from escritorio.proyecto_archivo import guardar_grafnet
from escritorio.sello import CLAVE
_area=tempfile.TemporaryDirectory(prefix='grafnet-fixtures-')
atexit.register(_area.cleanup)


def fixture_grafnet(ruta):
    ruta=Path(ruta)
    if ruta.suffix.lower()=='.grafnet':return ruta
    raiz=ruta if ruta.is_dir() else ruta.parent
    if (raiz/'manifest.json').is_file():proyecto=open_project(raiz)
    else:
        op=open_model(ruta);proyecto=new_project(op.doc['id'],op.title);add_document(proyecto,op.doc)
        for p in op.presentations:add_document(proyecto,p)
    destino=Path(_area.name)/(uuid.uuid4().hex+'.grafnet')
    archivo=guardar_grafnet(destino,proyecto,CLAVE,raiz);archivo.cerrar()
    return destino
