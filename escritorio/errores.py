"""Errores no previstos: en el ejecutable no hay consola, así que un fallo dentro de una orden del menú se perdía
sin que el usuario viera nada. Aquí se muestran en un aviso y se guardan en «registro_errores.txt», junto a los
proyectos (Documentos/GRAFCET Connect)."""
from __future__ import annotations

from datetime import datetime
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from . import VERSION
from .carpetas import directorios

NOMBRE_REGISTRO = "registro_errores.txt"


def ruta_registro():
    return directorios()["raiz"] / NOMBRE_REGISTRO


def _guardar(texto: str):
    try:
        ruta = ruta_registro()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now().isoformat(timespec='seconds')} · GRAFCET Connect {VERSION}\n{texto}\n")
        return ruta
    except OSError:
        return None


def _avisar(tipo, valor, rastro):
    texto = "".join(traceback.format_exception(tipo, valor, rastro))
    if sys.stderr is not None:
        sys.stderr.write(texto)
    ruta = _guardar(texto)
    if QApplication.instance() is None:
        return
    donde = f"\n\nEl detalle se ha guardado en:\n{ruta}" if ruta else ""
    QMessageBox.warning(None, "GRAFCET Connect", "No se ha podido completar la orden por un error inesperado: "
                        f"{valor}{donde}\n\nPuede comunicarlo en GitHub (Ayuda > Acerca de > Comunicar un fallo).")


def instalar():
    """Sustituye el gestor de excepciones: aviso visible y registro en archivo."""
    sys.excepthook = _avisar
