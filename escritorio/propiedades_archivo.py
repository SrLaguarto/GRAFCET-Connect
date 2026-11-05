"""Proyecto > Propiedades del archivo…: autor, fechas, versiones, sello y programa del proyecto abierto."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import getpass
import os
from pathlib import Path
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout,
                               QWidget)
from grafcet.contenedor import FORMATO_VERSION
from . import VERSION, sello

ALGORITMO = "HMAC-SHA256"
ANTIGUO = "desconocida (archivo anterior a la 1.0)"
# Nuitka marca cada módulo compilado con `__compiled__`; PyInstaller pone `sys.frozen`.
EMPAQUETADO = bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


@dataclass
class Propiedades:
    """Lo que muestra el diálogo, ya como texto."""
    nombre: str
    ruta: str
    autor: str
    creado: str
    modificado: str
    version_creacion: str
    version_guardado: str
    formato: str
    sello: str
    algoritmo: str
    huella: str
    programa: str
    instalado: str
    editable: bool


def autor_por_defecto() -> str:
    """Autor de un proyecto nuevo: el usuario de Windows (USERNAME o, de respaldo, getpass); vacío si no se obtiene."""
    nombre = os.environ.get("USERNAME", "")
    if nombre:
        return nombre
    try:
        return getpass.getuser()
    except (OSError, KeyError, ImportError):
        return ""


def autor_para_guardar(e) -> str:
    """Autor del próximo guardado: el puesto a mano, el del archivo abierto o, en un proyecto nuevo, el por defecto."""
    if e.autor_archivo is not None:
        return e.autor_archivo
    if e.info_archivo is None:
        return autor_por_defecto()
    return e.info_archivo.get("autor", "")


def _fecha(iso: str | None, falta: str) -> str:
    if not iso:
        return falta
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return falta


def huella_agrupada(huella: str) -> str:
    """Los 16 primeros hexadecimales, de 4 en 4, para comparar copias a simple vista."""
    corta = huella[:16]
    return " ".join(corta[i:i + 4] for i in range(0, len(corta), 4))


def _texto_sello(e) -> tuple[str, str, str]:
    if e.contenedor is None:
        return "Se firmará al guardar", "", ""
    if e.contenedor.firma == "valida":
        clave = "de desarrollo" if sello.DESARROLLO else "de distribución"
        texto = f"Firmado con esta versión de GRAFCET Connect (clave {clave})"
    elif e.contenedor.firma == "desarrollo":
        texto = "Firmado con la versión de desarrollo: no es una firma de esta versión"
    else:
        texto = ("Sin firma válida: sin sello, de otra versión o modificado fuera del programa. "
                 "Al guardarlo seguirá sin firma.")
    return texto, ALGORITMO, huella_agrupada(e.contenedor.huella)


def descripcion_programa() -> tuple[str, str]:
    """(texto de la versión, fecha de instalación): la del ejecutable si está empaquetado."""
    tipo = "versión de desarrollo" if sello.DESARROLLO else "versión de distribución"
    texto = f"GRAFCET Connect {VERSION} ({tipo})"
    if not EMPAQUETADO:
        return texto, "versión de desarrollo, sin instalar"
    modificado = datetime.fromtimestamp(Path(sys.executable).stat().st_mtime)
    return texto, modificado.strftime("%d/%m/%Y %H:%M")


def recopilar(e, editable: bool = True) -> Propiedades:
    """Propiedades del proyecto de la edición `e`; los datos aún sin guardar se describen como tales."""
    info = e.info_archivo
    nuevo = info is None
    info = info or {}
    sello_texto, algoritmo, huella = _texto_sello(e)
    programa, instalado = descripcion_programa()
    return Propiedades(
        nombre=e.archivo.name if e.archivo else "sin guardar",
        ruta=str(e.archivo.parent) if e.archivo else "sin guardar",
        autor=autor_para_guardar(e),
        creado=_fecha(info.get("creado"), "Se fijará al guardar" if nuevo else ANTIGUO),
        modificado=_fecha(info.get("modificado"), "sin guardar" if nuevo else ANTIGUO),
        version_creacion=info.get("version_creacion") or ("Se fijará al guardar" if nuevo else ANTIGUO),
        version_guardado=info.get("version_guardado") or ("sin guardar" if nuevo else ANTIGUO),
        formato=str(FORMATO_VERSION),
        sello=sello_texto, algoritmo=algoritmo, huella=huella,
        programa=programa, instalado=instalado, editable=editable)


def _etiqueta(texto: str) -> QLabel:
    et = QLabel(texto)
    et.setWordWrap(True)
    et.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return et


class PropiedadesArchivo(QDialog):
    """Diálogo de solo lectura salvo el autor. `autor()` devuelve lo escrito; la ventana decide si cambió."""

    def __init__(self, datos: Propiedades, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Propiedades del archivo")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.c_autor = QLineEdit(datos.autor)
        self.c_autor.setMaxLength(200)
        self.c_autor.setReadOnly(not datos.editable)
        self.c_autor.setAccessibleName("Autor")
        filas = [("Archivo", datos.nombre), ("Ruta", datos.ruta)]
        for nombre, valor in filas:
            form.addRow(nombre + ":", _etiqueta(valor))
        form.addRow("Autor:", self.c_autor)
        filas = [("Fecha de creación", datos.creado), ("Última edición", datos.modificado),
                 ("Creado con la versión", datos.version_creacion),
                 ("Guardado por última vez con la versión", datos.version_guardado),
                 ("Versión del formato .grafnet", datos.formato), ("Sello", datos.sello)]
        if datos.algoritmo:
            filas += [("Algoritmo del sello", datos.algoritmo), ("Huella del contenido", datos.huella)]
        filas += [("Este programa", datos.programa), ("Instalado el", datos.instalado)]
        for nombre, valor in filas:
            form.addRow(nombre + ":", _etiqueta(valor))
        lay.addLayout(form)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botones.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

    def autor(self) -> str:
        return self.c_autor.text().strip()


def abrir(ventana) -> None:
    """Abre el diálogo para la edición en curso. Si se cambia el autor, marca el proyecto como modificado."""
    e = ventana.edicion
    if e is None:
        QMessageBox.information(ventana, "Propiedades del archivo", "No hay ningún proyecto abierto.")
        return
    editable = not ventana.solo_lectura
    dialogo = PropiedadesArchivo(recopilar(e, editable), ventana)
    dialogo.exec()
    autor = dialogo.autor()
    if editable and autor != autor_para_guardar(e):
        e.autor_archivo = autor
        e.ed.dirty = True
        ventana._titulo_ventana()
