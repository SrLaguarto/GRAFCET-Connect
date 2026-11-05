"""Lectura y guardado de un proyecto completo .grafnet con recursos."""
import copy
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import tempfile
from grafcet.contenedor import (empaquetar,extraer_completo,guardar_atomico,inspeccionar,construir_info,
                                serializar_info,sello_valido,MAX_BYTES,ErrorContenedor)
from grafcet.persistence import open_project,save_project
from grafcet.profile import APP_VERSION


class EspacioTemporal:
    """Área de trabajo propiedad de ProyectoArchivo; se elimina también al liberar ciclos de Qt."""
    def __init__(self,prefix):
        self.name=tempfile.mkdtemp(prefix=prefix)
    def cleanup(self):
        p=Path(self.name)
        if p.exists():
            if p.resolve().parent != Path(tempfile.gettempdir()).resolve():
                raise ValueError('Área temporal fuera de su ubicación prevista')
            shutil.rmtree(p)


@dataclass
class ProyectoArchivo:
    archivo: Path
    temporal: EspacioTemporal
    proyecto: object
    sello_valido: bool
    info: dict = field(default_factory=dict)  # `_grafnet/info.json` validado; {} si no lo tenía
    huella: str = ''  # SHA-256 (hex) de las entradas selladas
    firma: str = 'valida'  # 'valida' (clave de esta versión), 'desarrollo' o 'sin_firma' (sin sello, otra clave o modificado)

    @property
    def raiz(self):return Path(self.temporal.name)

    def cerrar(self):self.temporal.cleanup()

    def __del__(self):
        self.cerrar()


FIRMA_VALIDA,FIRMA_DESARROLLO,SIN_FIRMA='valida','desarrollo','sin_firma'


def abrir_grafnet(archivo,clave,politica='importar',clave_desarrollo=None):
    """Abre un .grafnet. Con 'importar' (lo que usa el programa) la firma no bloquea: se registra en `firma`.
    `clave_desarrollo` solo se pasa en una versión de distribución, para reconocer los archivos de desarrollo."""
    archivo=Path(archivo)
    if archivo.stat().st_size>MAX_BYTES:raise ErrorContenedor('El archivo supera el tamaño permitido')
    datos=archivo.read_bytes()
    temporal=EspacioTemporal(prefix='grafconnect-proyecto-')
    try:
        extraccion=extraer_completo(datos,Path(temporal.name),clave,politica)
        proyecto=open_project(Path(temporal.name))
        if not proyecto.models():raise ErrorContenedor('El proyecto no contiene ningún modelo')
        if extraccion.valido:firma=FIRMA_VALIDA
        elif clave_desarrollo is not None and clave_desarrollo!=clave and sello_valido(datos,clave_desarrollo):firma=FIRMA_DESARROLLO
        else:firma=SIN_FIRMA
        return ProyectoArchivo(archivo,temporal,proyecto,extraccion.valido,extraccion.info,extraccion.huella,firma)
    except BaseException:
        temporal.cleanup();raise


def guardar_grafnet(archivo,proyecto,clave,origen=None,preparar=None,info_previa=None,autor=''):
    """Solo sustituye el destino después de preparar y sellar el proyecto entero. `info_previa` son los metadatos del
    archivo abierto (None en un proyecto nuevo): se conservan creado y version_creacion y se actualiza el resto.
    `clave` None: se guarda sin sello (archivo abierto sin firma válida)."""
    temporal=EspacioTemporal(prefix='grafconnect-guardar-')
    try:
        raiz=Path(temporal.name)
        if origen is not None:
            origen=Path(origen)
            if origen.is_dir():
                for p in origen.rglob('*'):
                    rel=p.relative_to(origen)
                    if any(x in ('_grafnet','.recuperacion','__pycache__') for x in rel.parts):continue
                    if p.is_symlink():raise ErrorContenedor('No se admiten recursos enlazados fuera del proyecto')
                    if p.is_file() and p.suffix.lower() not in ('.grafnet','.new','.tmp') and p.name!='commit.json':
                        destino=raiz/rel;destino.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,destino)
        proyecto=copy.deepcopy(proyecto)
        save_project(raiz,proyecto)
        if preparar is not None:preparar(raiz)
        info=construir_info(info_previa,autor,APP_VERSION)
        datos=empaquetar(raiz,clave,serializar_info(info))
        if len(datos)>MAX_BYTES:raise ErrorContenedor("El archivo supera el tamaño permitido")
        guardar_atomico(Path(archivo),datos)
        firmado=clave is not None
        return ProyectoArchivo(Path(archivo),temporal,proyecto,firmado,info,inspeccionar(datos)[1],
                               FIRMA_VALIDA if firmado else SIN_FIRMA)
    except BaseException:
        temporal.cleanup();raise


def comprobar_contenedor():
    """Comprobación interna del ejecutable: ZIP y sello deben funcionar ya empaquetados."""
    from grafcet.editor import Editor,new_grafcet_document
    from grafcet.persistence import new_project,add_document
    from .sello import CLAVE
    e=Editor(new_grafcet_document('comprobacion'));e.add_step('g','1',True)
    p=new_project('comprobacion','Comprobación del contenedor');add_document(p,e.model);add_document(p,e.presentation)
    with tempfile.TemporaryDirectory(prefix='grafconnect-comprobacion-') as tmp:
        ruta=Path(tmp)/'comprobacion.grafnet'
        guardado=guardar_grafnet(ruta,p,CLAVE)
        try:
            abierto=abrir_grafnet(ruta,CLAVE)
            try:
                if abierto.proyecto.documents != guardado.proyecto.documents:raise ValueError('El contenedor no conserva los documentos')
            finally:abierto.cerrar()
        finally:guardado.cerrar()
