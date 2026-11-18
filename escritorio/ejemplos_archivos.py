"""Instalación inicial de los ejemplos como proyectos editables sin firma."""
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from grafcet.contenedor import empaquetar, guardar_atomico
from grafcet.ejemplos_aula import DIDACTICOS
from grafcet.examples import EJEMPLOS
from grafcet.persistence import add_document, new_project, save_project
from grafcet.view import presentation_for

COPIADOS = "ejemplos/copied"


def nombres_ejemplos() -> dict[str, str]:
    titulos = {
        clave: "Selección de secuencia" if titulo == "Elección de secuencia" else titulo
        for clave, (titulo, _, _) in EJEMPLOS.items()
    }
    repetidos = Counter(titulos.values())
    nombres = {}
    for clave, titulo in titulos.items():
        if repetidos[titulo] > 1 and clave not in DIDACTICOS:
            titulo = f"{titulo} (caso de estudio)"
        nombres[clave] = f"Ejemplo - {titulo}.grafnet"
    return nombres


def instalar_ejemplos(carpeta_guardado: Path, ajustes) -> list[Path]:
    destino = carpeta_guardado / "Ejemplos"
    nombres = nombres_ejemplos()
    if not ajustes.contains(COPIADOS) and destino.exists():
        # Una carpeta previa puede contener archivos editados o haber sufrido borrados.
        ajustes.setValue(COPIADOS, list(nombres))
        ajustes.sync()
        return []
    copiados = set(ajustes.value(COPIADOS, [], type=list))
    pendientes = {clave: nombre for clave, nombre in nombres.items() if clave not in copiados}
    if not pendientes:
        return []
    destino.mkdir(exist_ok=True)
    ajustes.setValue(COPIADOS, sorted(copiados))
    ajustes.sync()
    creados = []
    for clave, nombre in pendientes.items():
        archivo = destino / nombre
        if not archivo.exists():
            _crear_ejemplo(clave, archivo)
            creados.append(archivo)
        copiados.add(clave)
        ajustes.setValue(COPIADOS, sorted(copiados))
        ajustes.sync()
    return creados


def _crear_ejemplo(clave: str, archivo: Path) -> None:
    titulo, _, construir = EJEMPLOS[clave]
    modelo, posiciones = construir()
    documento = modelo.doc if hasattr(modelo, "doc") else modelo
    proyecto = new_project(documento["id"], titulo)
    add_document(proyecto, documento)
    add_document(proyecto, presentation_for(documento, posiciones))
    with TemporaryDirectory(dir=archivo.parent, prefix=".preparar-") as tmp:
        save_project(Path(tmp), proyecto)
        guardar_atomico(archivo, empaquetar(Path(tmp), None))
