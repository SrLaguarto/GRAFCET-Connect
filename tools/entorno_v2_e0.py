"""Entorno Qt aislado y fuentes de proyectos compartidos por los bancos."""
import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.update(QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR="1", GRAFCONNECT_SIN_ACTUALIZAR="1")
if Path("C:/Windows/Fonts").is_dir():
    os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"

from PySide6.QtCore import QLocale, QStandardPaths
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import QMessageBox

from escritorio.proyecto_archivo import guardar_grafnet
from escritorio.sello import CLAVE
from grafcet.persistence import add_document, new_project
from tools.hoja_contactos import Contexto, RAIZ, _bombear, aplicacion
from tools.proyecto_referencia import NOMBRE, construir

TAMANO = (1366, 768)
FIXTURES = RAIZ / "tests" / "fixtures"
GEMMA = FIXTURES / "referencia" / "guia_gemma.grafnet"
SEGUNDO = 1_000_000


def escribir_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _aviso(_, titulo, mensaje, *args, **kwargs):
    raise RuntimeError(f"{titulo} — {mensaje}")


@contextmanager
def ventana():
    """Reutiliza el contexto de AD y mantiene preferencias, biblioteca y avisos aislados."""
    app = aplicacion()
    anterior = app.font()
    idioma = QLocale()
    app.setFont(QFont("Arial", 10))
    QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Spain))
    ubicacion = QStandardPaths.writableLocation
    with TemporaryDirectory(prefix="documentos-e0-") as documentos:
        def temporal(clase):
            return documentos if clase == QStandardPaths.StandardLocation.DocumentsLocation else ubicacion(clase)

        with (patch.object(QStandardPaths, "writableLocation", temporal),
              patch.object(QMessageBox, "warning", _aviso),
              patch.object(QMessageBox, "critical", _aviso),
              patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok),
              patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard)):
            c = Contexto(*TAMANO)
            try:
                c.mostrar()
                QCursor.setPos(-100, -100)
                yield c.w
            finally:
                c.cerrar()
                app.setFont(anterior)
                QLocale.setDefault(idioma)


def archivo_referencia(carpeta, ed=None):
    """Materializa solo el proyecto sintético en un archivo temporal para medir Abrir."""
    ed = construir() if ed is None else ed
    ruta = carpeta / "referencia_100.grafnet"
    proyecto = new_project(ed.model["id"], NOMBRE)
    add_document(proyecto, ed.model)
    add_document(proyecto, ed.presentation)
    guardar_grafnet(ruta, proyecto, CLAVE).cerrar()
    return ruta


def play(w):
    w.a_ejecutar.trigger()
    w.rt.stop()  # solo cuentan los estímulos explícitos del guion
    if w.modo != "simular":
        raise RuntimeError("Play no arrancó")


def paso(w, operacion="avanzar", **datos):
    w._act(operacion, **datos)
    if w.v.s.status != "pausada-estable" or w.aviso.isVisible():
        raise RuntimeError(f"Paso de simulación fallido: {w.v.s.status}. {w.aviso.text()}")


def bombear():
    _bombear(5)
