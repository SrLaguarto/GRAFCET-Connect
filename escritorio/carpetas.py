"""Biblioteca del usuario en Documentos; nunca se escribe en la instalación."""
import json
import os
from pathlib import Path
import tempfile
from PySide6.QtCore import QStandardPaths
from grafcet.plantillas import serializable,validar_plantilla
from grafcet.plantillas_tecnicas import PREDETERMINADAS,plantilla_tecnica


def directorios():
    documentos=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if not documentos:raise OSError('No se pudo localizar la carpeta Documentos del usuario')
    raiz=Path(documentos)/'GrafConnect'
    return {'raiz':raiz,'plantillas':raiz/'Plantillas','grafcet':raiz/'GRAFCET','laminas':raiz/'Láminas'}


def asegurar_carpetas():
    rutas=directorios()
    for p in rutas.values():p.mkdir(parents=True,exist_ok=True)
    for nombre,size in PREDETERMINADAS.items():
        carpeta=rutas['plantillas']/nombre;carpeta.mkdir(exist_ok=True);archivo=carpeta/'plantilla.json'
        if archivo.exists():continue
        datos=json.dumps(serializable(plantilla_tecnica(*size)),ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
        # O_EXCL protege incluso si otra instancia crea el archivo al mismo tiempo.
        try:fd=os.open(archivo,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        except FileExistsError:continue
        with os.fdopen(fd,'wb') as f:f.write(datos)
    return rutas


def cargar_plantilla(ruta):
    try:return validar_plantilla(json.loads(Path(ruta).read_text(encoding='utf-8-sig')))
    except (ValueError,TypeError,KeyError) as exc:raise ValueError(f'Plantilla no válida: {Path(ruta).name}') from exc


def predeterminada(formato='A4',orientacion='vertical',margen=10.):
    from grafcet.laminas import FORMATOS
    nombre=f'{formato}_{orientacion}';rutas=asegurar_carpetas()
    if nombre in PREDETERMINADAS and abs(margen-10)<1e-9:
        return cargar_plantilla(rutas['plantillas']/nombre/'plantilla.json')
    w,h=FORMATOS[formato]
    if orientacion=='horizontal':w,h=h,w
    return plantilla_tecnica(w,h,margen)


def guardar_plantilla(ruta,plantilla):
    ruta=Path(ruta);p=validar_plantilla(plantilla)
    datos=json.dumps(serializable(p),ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
    ruta.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.plantilla-',suffix='.tmp',dir=ruta.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(datos);f.flush();os.fsync(f.fileno())
        os.replace(tmp,ruta)
    finally:Path(tmp).unlink(missing_ok=True)


def nombre_proyecto(titulo):
    import re
    seguro=re.sub(r'[\\/:*?"<>|]','_',titulo).strip(' .') or 'Sin título'
    return seguro+'.grafnet'
