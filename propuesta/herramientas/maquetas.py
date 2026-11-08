"""Maquetas de las propuestas pendientes (`PROPUESTAS_PENDIENTES.md`): capturas de la ventana real, retocadas por script. No cambian
el código de la interfaz: el script recoloca controles o fuerza un ajuste solo en la ventana que se captura.

Uso, desde la raíz del repositorio (con el Python del proyecto):

    python propuesta/herramientas/maquetas.py                      # todas, en propuesta/capturas/maquetas/
    python propuesta/herramientas/maquetas.py --maquetas p2 p7

- `p1`  Propiedades en un cuarto de pantalla con la paleta de operadores en una fila (el panel a 190 px).
- `p2`  Entradas de la simulación en una banda bajo el dibujo, en pantalla partida (960×1040).
- `p3`  Vista de E/S con filas de 28 px (un modo «cómodo» para el panel táctil del portátil) a 1366×768.
- `p7`  «Modo aula»: la escala grande (letra base de 14 px, controles de 40 px) a 1366×768, donde hoy rige la normal.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capturar  # noqa: E402  (fija la plataforma offscreen y la raíz del repositorio)


def _ventana(ancho: int, alto: int, tmp: str):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from escritorio.ventana import Ventana
    app = QApplication.instance() or QApplication([])
    w = Ventana(QSettings(tmp + "/ui.ini", QSettings.Format.IniFormat), Path(tmp) / "recuperacion")
    w.resize(ancho, alto)
    w.show()
    capturar._reposo(app)
    w.resize(ancho, alto)
    capturar._reposo(app)
    return w, app


def _cerrar(w, app) -> None:
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


def maqueta_p1(salida: Path) -> Path:
    capturar.capturar("cuarto", "maqueta-panel-bajo", salida)
    destino = salida / "maqueta-p1-propiedades-cuarto.png"
    (salida / "maqueta-panel-bajo-cuarto.png").replace(destino)
    return destino


def maqueta_p2(salida: Path) -> Path:
    """Las entradas, en fila bajo el dibujo; salidas y temporizadores se quedan en el panel de la derecha, que gana alto."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget
    with tempfile.TemporaryDirectory() as tmp:
        parche = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=tmp)
        parche.start()
        w, app = _ventana(960, 1040, tmp)
        capturar.escena_simulacion(w, app)
        banda = QWidget()
        banda.setObjectName("bandaEntradas")
        banda.setStyleSheet("QWidget#bandaEntradas { background: white; border-top: 1px solid #cdd6e0; }")
        fila = QHBoxLayout(banda)
        fila.setContentsMargins(8, 4, 8, 4)
        fila.setSpacing(8)
        fila.addWidget(QLabel("Entradas"))
        caja = w._cajas_lado[0]
        for b in list(w.botones.values()):
            w.rejilla.removeWidget(b)
            b.setParent(banda)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)  # (en el panel eran «Ignored»: aquí cada una pide sus 190 px)
            b.setFixedWidth(190)
            fila.addWidget(b)
            b.show()
        fila.addStretch(1)
        caja.hide()  # el cuadro «Entradas» del panel derecho
        w.diagrama.parentWidget().layout().addWidget(banda)
        capturar._reposo(app, 40)
        destino = salida / "maqueta-p2-entradas-en-banda-partida.png"
        w.grab().save(str(destino))
        boton = getattr(w, "_captura_boton", None)
        if boton is not None:
            QTest.mouseRelease(boton, Qt.MouseButton.LeftButton)
        _cerrar(w, app)
        parche.stop()
    return destino


def maqueta_p3(salida: Path) -> Path:
    """La vista de E/S con las filas de canales y de variables a 28 px (hoy 16): caben menos y la lista se desplaza."""
    from escritorio import entradas_salidas as es
    with tempfile.TemporaryDirectory() as tmp:
        parche = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=tmp)
        parche.start()
        antes = (es.ALTO_FILA, es.ALTO_VARIABLE)
        es.ALTO_FILA = es.ALTO_VARIABLE = 28
        try:
            w, app = _ventana(1366, 768, tmp)
            capturar.escena_es(w, app)
            destino = salida / "maqueta-p3-es-filas-28px-1366.png"
            w.grab().save(str(destino))
            _cerrar(w, app)
        finally:
            es.ALTO_FILA, es.ALTO_VARIABLE = antes
            parche.stop()
    return destino


def maqueta_p7(salida: Path) -> Path:
    """La escala grande forzada en una ventana de 1366×768 (proyector de un aula): lo que sería el «Modo aula» elegido a mano."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    with tempfile.TemporaryDirectory() as tmp:
        parche = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=tmp)
        parche.start()
        w, app = _ventana(1366, 768, tmp)
        capturar.escena_simulacion(w, app)
        boton = getattr(w, "_captura_boton", None)
        if boton is not None:
            QTest.mouseRelease(boton, Qt.MouseButton.LeftButton)
        w._aplicar_escala("grande")  # a mano: por tamaño, a 1366×768 rige la normal
        capturar._reposo(app, 60)
        w.refrescar()
        capturar._reposo(app, 20)
        destino = salida / "maqueta-p7-modo-aula-1366.png"
        w.grab().save(str(destino))
        _cerrar(w, app)
        parche.stop()
    return destino


MAQUETAS = {"p1": maqueta_p1, "p2": maqueta_p2, "p3": maqueta_p3, "p7": maqueta_p7}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maquetas", nargs="+", choices=list(MAQUETAS), default=list(MAQUETAS))
    ap.add_argument("--salida", type=Path, default=Path(__file__).resolve().parents[1] / "capturas" / "maquetas")
    args = ap.parse_args(argv)
    args.salida.mkdir(parents=True, exist_ok=True)
    for m in args.maquetas:
        try:
            print(MAQUETAS[m](args.salida))
        except Exception as exc:  # una maqueta rota no impide las demás
            print(f"{m}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
