"""El anillo de foco: solo con teclado, y con teclado en cada parada.

Uso, desde la raíz del repositorio (con el Python del proyecto):

    python propuesta/herramientas/foco.py                 # las dos comprobaciones a 1366×768 y a 640×520
    python propuesta/herramientas/foco.py --tamanos 1366  # solo uno
    python propuesta/herramientas/foco.py --json foco.json

**A. Sin teclado, ningún anillo.** Recorre con el ratón (clics reales de `QTest`) el arranque, el clic en la luz de E/S y la vuelta con
«←», el paso a PLANOS y de vuelta, abrir Propiedades, cambiar de pestaña de panel, pulsar Play y Stop, el zoom y pulsar una entrada.
Después de cada paso comprueba, por **estado** (ningún control visible con la propiedad `tecl`) y por **píxeles** (el control que tiene
el foco se pinta igual con la propiedad `tecl` puesta a falso: si cambia, había anillo), que no hay ninguno.

**B. Con Tab, anillo en cada parada.** Recorre con la tecla Tab (teclas reales) todo lo alcanzable, en edición con Propiedades abierto y en
simulación (incluidas las entradas), y en cada parada comprueba por píxeles que el control con el foco muestra un anillo, y mide su
contraste (anillo contra lo que tapa) para exigir 3:1. Al final, un clic de ratón lo quita.

Termina con código 0 si todo se cumple. No escribe en la carpeta de documentos ni en la configuración del usuario.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capturar  # noqa: E402  (fija la plataforma offscreen y la raíz del repositorio)
import medir  # noqa: E402

ULTIMA_CAJA = None  # dónde cambiaron los píxeles en la última comparación (para explicar un fallo)
RESULTADO: dict = {}
FALLOS: list[str] = []


def anotar(clave: str, ok: bool, detalle: str = "") -> None:
    print(f"{'OK  ' if ok else 'FALLA'} {clave}{(' · ' + detalle) if detalle else ''}")
    if not ok:
        FALLOS.append(clave)


def _ratio(a, b) -> float:
    return medir._ratio(a, b)


def _iguales(a, b) -> int:
    """Cuántos píxeles difieren entre dos imágenes del mismo tamaño."""
    if a.size() != b.size():
        return max(a.width() * a.height(), 1)
    return sum(1 for y in range(a.height()) for x in range(a.width()) if a.pixel(x, y) != b.pixel(x, y))


def estado_anillos(w) -> list[str]:
    """Los controles visibles con la propiedad `tecl` cierta (los que pintarían anillo)."""
    from PySide6.QtWidgets import QAbstractButton, QAbstractScrollArea, QTabBar
    return [f"{type(c).__name__}:{(getattr(c, 'text', lambda: '')() or c.objectName())[:20]}"
            for clase in (QAbstractButton, QTabBar, QAbstractScrollArea) for c in w.findChildren(clase)
            if c.isVisible() and c.property("tecl")]


def anillo_en(widget):
    """(¿hay anillo?, píxeles que cambian, contraste del anillo contra lo que tapa) del control con el foco, por píxeles: se pinta la
    ventana con el foco y sin él (sin tocar ninguna propiedad: da igual cómo lo consiga la hoja de estilo), se recorta el control con
    2 px de margen (así los controles de fondo transparente se ven sobre su fondo real) y se comparan."""
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    ventana = widget.window()
    recorte = QRect(widget.mapTo(ventana, QPoint(0, 0)), widget.size()).adjusted(-2, -2, 2, 2).intersected(ventana.rect())
    a = ventana.grab().toImage().copy(recorte)
    widget.clearFocus()
    capturar._reposo(app, 3)
    b = ventana.grab().toImage().copy(recorte)
    widget.setFocus(Qt.FocusReason.OtherFocusReason)
    capturar._reposo(app, 3)
    global ULTIMA_CAJA
    ULTIMA_CAJA = None
    banda = 6  # el anillo está en el borde del control: solo cuentan los píxeles de esa banda (el contenido, p. ej. lo dibujado, no es anillo)
    ratios = []
    for y in range(a.height()):
        for x in range(a.width()):
            if (x < banda or y < banda or x >= a.width() - banda or y >= a.height() - banda) and a.pixel(x, y) != b.pixel(x, y):
                ratios.append(_ratio(QColor.fromRgb(a.pixel(x, y) & 0xFFFFFF), QColor.fromRgb(b.pixel(x, y) & 0xFFFFFF)))
    n = len(ratios)
    contraste = 0.0
    if ratios:  # el percentil 75: el trazo discontinuo deja huecos y bordes suavizados que no son el anillo entero
        ratios.sort()
        contraste = ratios[int(len(ratios) * .75)]
    return n > 0, n, contraste

def crear(tamano: str, tmp: str):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from escritorio.ventana import Ventana
    app = QApplication.instance() or QApplication([])
    w = Ventana(QSettings(tmp + "/ui.ini", QSettings.Format.IniFormat), Path(tmp) / "recuperacion")
    ancho, alto = capturar.TAMANOS[tamano]
    w.resize(ancho, alto)
    w.show()
    w.activateWindow()
    capturar._reposo(app)
    w.resize(ancho, alto)
    capturar._reposo(app)
    return w, app


def liberar(w, app) -> None:
    w.rt.stop()
    w.a_ejecutar.blockSignals(True)
    w.a_ejecutar.setChecked(False)
    w.a_ejecutar.blockSignals(False)
    if w.paginas_es.currentIndex() != 0:
        w._mostrar_pagina(False)
        capturar._reposo(app)
    w.edicion = None
    w.hide()
    w.deleteLater()
    capturar._reposo(app)


def sin_teclado(tamano: str) -> dict:
    """A. Escenarios con el ratón: ningún anillo."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    out: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        parche = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=tmp)
        parche.start()
        w, app = crear(tamano, tmp)
        escenarios: list[tuple[str, object]] = []

        def paso(nombre: str, accion) -> None:
            accion()
            capturar._reposo(app, 25)
            QTest.qWait(60)
            foco = QApplication.focusWidget()
            estados = estado_anillos(w)
            hay, n, _ = anillo_en(foco) if foco is not None else (False, 0, 0.0)
            quien = f"{type(foco).__name__}:{(getattr(foco, 'text', lambda: '')() or foco.objectName())[:18]}" if foco is not None else "ninguno"
            ok = not estados and not hay
            anotar(f"[{tamano}] sin teclado · {nombre}", ok, f"foco en {quien}; estado {estados or 'sin anillos'}; píxeles de anillo en el borde {n}")
            out[nombre] = {"foco": quien, "controles con anillo": estados, "píxeles de anillo en el borde": n}

        paso("arranque", lambda: None)
        capturar._editable(w, app)
        paso("abrir el ejemplo editable", lambda: None)
        paso("clic en la luz de E/S", lambda: QTest.mouseClick(w.luz_es, Qt.MouseButton.LeftButton))
        paso("volver con «←»", lambda: QTest.mouseClick(w.panel_es.b_volver, Qt.MouseButton.LeftButton))
        tab = w.pestanas_vistas.tabRect(1).center()
        paso("pasar a PLANOS (pestaña)", lambda: QTest.mouseClick(w.pestanas_vistas, Qt.MouseButton.LeftButton, pos=tab))
        tab0 = w.pestanas_vistas.tabRect(0).center()
        paso("volver a GRAFCET (pestaña)", lambda: QTest.mouseClick(w.pestanas_vistas, Qt.MouseButton.LeftButton, pos=tab0))
        vp = w.diagrama.viewport()
        paso("clic en el dibujo", lambda: QTest.mouseClick(vp, Qt.MouseButton.LeftButton, pos=QPoint(40, 40)))
        t = w.edicion.M["transitions"][0]["id"]

        def abrir_propiedades() -> None:
            w.edicion.seleccionar([t])
            capturar._reposo(app)
            w._abrir_opciones()
        paso("abrir Propiedades", abrir_propiedades)
        pest = w.pestanas["derecho"]
        paso("zoom −", lambda: QTest.mouseClick(w.diagrama.b_menos, Qt.MouseButton.LeftButton))
        paso("zoom + y Centrar todo", lambda: (QTest.mouseClick(w.diagrama.b_mas, Qt.MouseButton.LeftButton),
                                              QTest.mouseClick(w.diagrama.b_ajustar, Qt.MouseButton.LeftButton)))
        paso("plegar el panel Variables (◂▸)", lambda: QTest.mouseClick(w.flechas["derecho"], Qt.MouseButton.LeftButton))
        paso("desplegar el panel Variables (pestaña)", lambda: QTest.mouseClick(pest, Qt.MouseButton.LeftButton) if pest.isVisible() else None)
        play = w.tb_sim.widgetForAction(w.a_ejecutar)
        paso("Play", lambda: QTest.mouseClick(play, Qt.MouseButton.LeftButton))
        w.rt.stop()
        var = next((v for v in w.botones if w.nombre(v) == "marcha"), None)
        if var is not None:
            paso("pulsar una entrada", lambda: (QTest.mousePress(w.botones[var], Qt.MouseButton.LeftButton), QTest.qWait(200),
                                                QTest.mouseRelease(w.botones[var], Qt.MouseButton.LeftButton)))
        paso("clic en la luz de E/S en Play", lambda: QTest.mouseClick(w.luz_es, Qt.MouseButton.LeftButton))
        paso("volver con «←» en Play", lambda: QTest.mouseClick(w.panel_es.b_volver, Qt.MouseButton.LeftButton))
        paso("Stop", lambda: QTest.mouseClick(play, Qt.MouseButton.LeftButton))
        liberar(w, app)
        parche.stop()
    return out


def con_tab(tamano: str, escena: str) -> dict:
    """B. Recorrido con Tab: anillo en cada parada, con contraste de 3:1 o más."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    out: dict = {"paradas": []}
    with medir.Ventana(tamano, escena) as w:
        app = QApplication.instance()
        w.activateWindow()
        if escena == "propiedades":
            w.edicion.seleccionar([w.edicion.M["transitions"][0]["id"]])
            capturar._reposo(app, 20)
        w.diagrama.setFocus(Qt.FocusReason.OtherFocusReason)
        capturar._reposo(app, 20)
        paradas, sin_anillo, peor = [], [], 99.0
        inicio = None
        for i in range(90):
            foco = QApplication.focusWidget()
            if foco is w.diagrama:
                QTest.keyClick(foco, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)  # el dibujo guarda Tab para sus elementos
            else:
                QTest.keyClick(foco, Qt.Key.Key_Tab)
            capturar._reposo(app, 6)
            foco = QApplication.focusWidget()
            if foco is None:
                break
            clave = id(foco)
            if inicio is None:
                inicio = clave
            elif clave == inicio:
                break
            nombre = f"{type(foco).__name__}:{(getattr(foco, 'text', lambda: '')() or foco.objectName() or foco.accessibleName())[:22]}"
            hay, n, ratio = anillo_en(foco)
            paradas.append((nombre, hay, n, round(ratio, 2)))
            if not hay:
                sin_anillo.append(nombre)
            elif ratio:
                peor = min(peor, ratio)
        out["paradas"] = [f"{a}{'' if h else ' (SIN ANILLO)'} [{n}px, {r}:1]" for a, h, n, r in paradas]
        anotar(f"[{tamano}/{escena}] Tab recorre {len(paradas)} paradas", len(paradas) >= 8, f"{len(paradas)} paradas")
        anotar(f"[{tamano}/{escena}] anillo en cada parada", not sin_anillo, f"sin anillo: {sin_anillo}" if sin_anillo else f"{len(paradas)} de {len(paradas)}")
        anotar(f"[{tamano}/{escena}] contraste del anillo 3:1 o más", peor >= 3.0, f"mediana más baja {peor:.2f}:1")
        out.update({"sin anillo": sin_anillo, "contraste mediano más bajo": round(peor, 2)})
        # un clic de ratón lo quita
        QTest.mouseClick(w.diagrama.viewport(), Qt.MouseButton.LeftButton, pos=w.diagrama.viewport().rect().center())
        capturar._reposo(app, 20)
        anotar(f"[{tamano}/{escena}] un clic de ratón quita el anillo", not estado_anillos(w), str(estado_anillos(w)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tamanos", nargs="+", choices=list(capturar.TAMANOS), default=["1366", "minima"])
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for t in a.tamanos:
        RESULTADO[f"sin teclado {t}"] = sin_teclado(t)
        for escena in ("propiedades", "simulacion"):
            RESULTADO[f"con Tab {t} {escena}"] = con_tab(t, escena)
    print("RESULTADO:", "todas las comprobaciones se cumplen" if not FALLOS else f"fallan {len(FALLOS)}")
    for f in FALLOS:
        print("  -", f)
    if a.json:
        a.json.write_text(json.dumps(RESULTADO, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    sys.exit(main())
