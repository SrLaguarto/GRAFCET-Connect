"""Mide la ventana a los cuatro tamaños: alto de cada franja sobre el dibujo, tamaño del dibujo y de los controles principales.

Uso, desde la raíz del repositorio:  python propuesta/herramientas/medir.py [--escena editor|simulacion]

Sirve para vigilar el presupuesto de alto (las pruebas fijan que el dibujo empiece antes de los 140 px a 1366×768) y los
objetivos táctiles (los controles principales miden al menos 32 px de alto).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capturar  # noqa: E402  (fija la plataforma offscreen y la raíz del repositorio)


def medir(tamano: str, escena: str) -> dict:
    from PySide6.QtCore import QPoint, QSettings
    from PySide6.QtWidgets import QApplication, QAbstractButton, QComboBox, QLineEdit
    from unittest import mock
    import tempfile
    from escritorio.ventana import Ventana
    app = QApplication.instance() or QApplication([])
    ancho, alto = capturar.TAMANOS[tamano]
    with tempfile.TemporaryDirectory() as tmp, mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=tmp):
        w = Ventana(QSettings(tmp + "/ui.ini", QSettings.Format.IniFormat), Path(tmp) / "recuperacion")
        w.resize(ancho, alto)
        w.show()
        capturar._reposo(app)
        {"editor": capturar.escena_editor, "simulacion": capturar.escena_simulacion}[escena](w, app)
        capturar._reposo(app, 30)
        arriba = lambda x: x.mapTo(w, QPoint(0, 0)).y()
        datos = {
            "menu": w.menuBar().height(),
            "fila de pestañas": w.fila_pestanas.height(),
            "herramientas": w.herramientas_grafcet.height() if not w.herramientas_grafcet.isHidden() else 0,
            "dibujo empieza en y": arriba(w.diagrama),
            "dibujo (ancho×alto)": f"{w.diagrama.width()}×{w.diagrama.height()}",
            "estado": w.statusBar().height(),
        }
        pequenos = []
        for clase in (QAbstractButton, QComboBox, QLineEdit):
            for c in w.findChildren(clase):
                if c.isVisible() and 0 < c.height() < 32 and c.width() > 12 and not c.objectName().startswith("quitar"):
                    pequenos.append(f"{c.metaObject().className()}:{(getattr(c, 'text', lambda: '')() or c.objectName() or c.toolTip())[:22]}={c.height()}")
        datos["controles visibles de menos de 32 px"] = pequenos
        w.rt.stop()
        w.a_ejecutar.blockSignals(True)
        w.a_ejecutar.setChecked(False)
        w.a_ejecutar.blockSignals(False)
        w.edicion = None
        w.hide()
        w.deleteLater()
        capturar._reposo(app)
    return datos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--escena", choices=("editor", "simulacion"), default="editor")
    ap.add_argument("--tamanos", nargs="+", choices=list(capturar.TAMANOS), default=list(capturar.TAMANOS))
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for tamano in args.tamanos:
        print(f"== {tamano} {capturar.TAMANOS[tamano]} · {args.escena}")
        for k, v in medir(tamano, args.escena).items():
            print(f"   {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
