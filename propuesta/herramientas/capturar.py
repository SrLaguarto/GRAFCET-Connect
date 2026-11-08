"""Capturas de la ventana de GRAFCET Connect a los cuatro tamaños de la propuesta de diseño.

Uso, desde la raíz del repositorio:

    python propuesta/herramientas/capturar.py
    python propuesta/herramientas/capturar.py --escenas editor simulacion --tamanos 1366 cuarto
    python propuesta/herramientas/capturar.py --salida otra/carpeta
    GRAFCET_RAIZ=<otra copia del repositorio> python propuesta/herramientas/capturar.py --salida antes   (mismas escenas en `main`)

Guarda `propuesta/capturas/despues/<escena>-<tamaño>.png` (o en `--salida`). Tamaños: `completa` 1920×1080, `partida`
960×1040 (pantalla partida vertical), `cuarto` 960×520 (un cuarto de pantalla) y `1366` 1366×768. Escenas:

- `editor`       proyecto editable (el ejemplo «temporizada» abierto para editar, sin «solo lectura») con la paleta.
- `propiedades`  una transición seleccionada y el panel inferior de Propiedades abierto.
- `simulacion`   Play en marcha, la entrada «marcha» pulsada y la etapa activa a la vista.
- `planos`       la pestaña PLANOS con una hoja que lleva el grafcet.
- `es`           la vista de E/S externas.
- `foco`         (extra) el foco de teclado en Play, para ver el anillo discontinuo de 2 px.

Funciona sin pantalla (plataforma Qt `offscreen`) y no escribe en la carpeta de documentos del usuario ni en su
configuración: usa una configuración y carpetas temporales.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
RAIZ = Path(os.environ.get("GRAFCET_RAIZ") or Path(__file__).resolve().parents[2])  # GRAFCET_RAIZ: capturar otra copia (p. ej. `main`)
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

TAMANOS = {"completa": (1920, 1080), "partida": (960, 1040), "cuarto": (960, 520), "1366": (1366, 768),
           "estrecha": (640, 800), "minima": (640, 520)}  # media pantalla de un portátil de 1280×800 al 150 %, y esa misma anchura a 1/4 de alto
PRINCIPALES = ("completa", "partida", "cuarto", "1366")
ESCENAS = ("editor", "propiedades", "simulacion", "planos", "es", "foco")
EXTRAS = ("maqueta-panel-bajo",)  # no se capturan por defecto: ver PROPUESTAS_PENDIENTES.md
EJEMPLO = "temporizada"


def _reposo(app, veces: int = 20) -> None:
    for _ in range(veces):
        app.processEvents()


def _editable(w, app) -> None:
    """El ejemplo abierto y editable: Qt lo abre en solo lectura; se pasa a la copia editable que ya tiene la ventana."""
    w.cargar_ejemplo(EJEMPLO)
    w.solo_lectura = False
    w._poner_modo()
    w.refrescar_edicion()
    _reposo(app)
    w.diagrama.ajustar()
    _reposo(app)


def _transicion(w) -> str:
    return w.edicion.M["transitions"][0]["id"]


def escena_editor(w, app) -> None:
    _editable(w, app)
    w.edicion.seleccionar([])


def escena_propiedades(w, app) -> None:
    _editable(w, app)
    w.edicion.seleccionar([_transicion(w)])
    _reposo(app)
    w._abrir_opciones()
    _reposo(app, 40)


def escena_simulacion(w, app) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    _editable(w, app)
    w.a_ejecutar.setChecked(True)
    w.rt.stop()
    _reposo(app)
    w.diagrama.ajustar()  # como al pulsar «Centrar todo»: el dibujo entero a la vista
    _reposo(app)
    var = next(v for v in w.botones if w.nombre(v) == "marcha")
    boton = w.botones[var]
    QTest.mousePress(boton, Qt.MouseButton.LeftButton)  # la entrada queda pulsada mientras se captura
    _reposo(app, 30)
    w._captura_boton = boton


def escena_maqueta_panel_bajo(w, app) -> None:
    """Maqueta de una propuesta pendiente: en un cuarto de pantalla, el panel de Propiedades con 190 px (lo que podría pedir
    la transición si la paleta de operadores se desplazara en horizontal) en lugar de los ≈334 px actuales."""
    escena_propiedades(w, app)
    w._opciones_automaticas = False
    total = sum(w.vsplit.sizes())
    w.vsplit.setSizes([total - 190, 190])
    _reposo(app, 40)


def escena_foco(w, app) -> None:
    """El foco de teclado (trazo discontinuo de 2 px) en el botón Play, como tras pulsar Tab."""
    from PySide6.QtCore import Qt
    _editable(w, app)
    w.edicion.seleccionar([_transicion(w)])
    _reposo(app)
    from PySide6.QtTest import QTest
    w.activateWindow()
    w.diagrama.setFocus(Qt.FocusReason.OtherFocusReason)
    _reposo(app)
    for _ in range(40):  # con Tab de verdad: sale el anillo
        if app.focusWidget() is w.tb_sim.widgetForAction(w.a_ejecutar):
            break
        QTest.keyClick(app.focusWidget(), Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier if app.focusWidget() is w.diagrama else Qt.KeyboardModifier.NoModifier)
        _reposo(app, 3)
    _reposo(app)


def escena_planos(w, app, carpeta: str) -> None:
    from grafcet.laminas import ajustes_lamina
    from escritorio.carpetas import predeterminada
    _editable(w, app)
    e = w.edicion
    plan = e.ed.add_sheet_plan("Plano de la secuencia")
    refs = [s["id"] for s in e.M["steps"]] + [t["id"] for t in e.M["transitions"]]
    ident = e.ed.add_plan_page(plan, ajustes_lamina({"plantilla": predeterminada()}))
    e.ed.set_page_graphics(ident, [{"refs": refs, "porcentaje": 100.0, "offset_mm": [0.0, 0.0]}])
    e.cambia()
    w._mostrar_pagina("planos")
    w.mostrar_hoja(ident)
    _reposo(app, 60)


def escena_es(w, app) -> None:
    _editable(w, app)
    w.mostrar_es()
    _reposo(app, 40)


def capturar(tamano: str, escena: str, salida: Path) -> Path:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from escritorio.ventana import Ventana
    app = QApplication.instance() or QApplication([])
    ancho, alto = TAMANOS[tamano]
    with tempfile.TemporaryDirectory() as tmp:
        docs = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=tmp)
        docs.start()
        try:
            w = Ventana(QSettings(tmp + "/ui.ini", QSettings.Format.IniFormat), Path(tmp) / "recuperacion")
            w.resize(ancho, alto)
            w.show()
            _reposo(app)
            w.resize(ancho, alto)  # (al mostrarse, el mínimo de la ventana aún era el de antes de adaptarse al tamaño)
            _reposo(app)
            if escena == "planos":
                escena_planos(w, app, tmp)
            else:
                {"editor": escena_editor, "propiedades": escena_propiedades, "simulacion": escena_simulacion,
                 "es": escena_es, "foco": escena_foco, "maqueta-panel-bajo": escena_maqueta_panel_bajo}[escena](w, app)
            # (sin `clearFocus()`: lo que se captura es lo que se ve; ningún anillo sin teclado lo comprueba `foco.py`)
            _reposo(app, 30)
            destino = salida / f"{escena}-{tamano}.png"
            w.grab().save(str(destino))
            boton = getattr(w, "_captura_boton", None)
            if boton is not None:
                from PySide6.QtCore import Qt
                from PySide6.QtTest import QTest
                QTest.mouseRelease(boton, Qt.MouseButton.LeftButton)
            w.rt.stop()
            w.a_ejecutar.blockSignals(True)
            w.a_ejecutar.setChecked(False)
            w.a_ejecutar.blockSignals(False)
            if w.paginas_es.currentIndex() != 0:
                w._mostrar_pagina(False)  # sale de PLANOS / E/S antes de destruir la ventana
                _reposo(app)
            w.edicion = None
            w.hide()
            w.deleteLater()
            _reposo(app)
        finally:
            docs.stop()
    return destino


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tamanos", nargs="+", choices=list(TAMANOS), default=list(TAMANOS), help="por defecto, los seis")
    ap.add_argument("--escenas", nargs="+", choices=ESCENAS + EXTRAS, default=list(ESCENAS))
    ap.add_argument("--salida", type=Path, default=Path(__file__).resolve().parents[1] / "capturas" / "despues")
    args = ap.parse_args(argv)
    args.salida.mkdir(parents=True, exist_ok=True)
    for escena in args.escenas:
        for tamano in args.tamanos:
            try:
                print(capturar(tamano, escena, args.salida))
            except Exception as exc:  # una escena rota no impide las demás
                print(f"{escena}-{tamano}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
