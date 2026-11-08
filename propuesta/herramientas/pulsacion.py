"""Mantener pulsada una entrada de la simulación se comporta como en `main` (P-IMP-75): el pulsador sigue a 1 y apretado mientras
dure el clic, sin soltarse solo ni abrir ningún menú; el clic derecho abre el menú de tipo; Ctrl+clic enclava.

Uso, desde la raíz del repositorio (con el Python del proyecto):

    python propuesta/herramientas/pulsacion.py                          # esta rama
    GRAFCET_RAIZ=<copia de main> python propuesta/herramientas/pulsacion.py   # la misma comprobación en `main`

Imprime una línea por comprobación y termina con código 0 si todas se cumplen (1 si alguna falla).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capturar  # noqa: E402  (fija la plataforma offscreen y la raíz del repositorio)


def main() -> int:
    from PySide6.QtCore import QSettings, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from escritorio.ventana import Ventana
    app = QApplication.instance() or QApplication([])
    fallos: list[str] = []

    def comprobar(nombre: str, ok: bool, detalle: str = "") -> None:
        print(f"{'OK  ' if ok else 'FALLA'} {nombre}{(' · ' + detalle) if detalle else ''}")
        if not ok:
            fallos.append(nombre)

    with tempfile.TemporaryDirectory() as tmp:
        parche = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=tmp)
        parche.start()
        w = Ventana(QSettings(tmp + "/ui.ini", QSettings.Format.IniFormat), Path(tmp) / "recuperacion")
        w.resize(1366, 768)
        w.show()
        capturar._reposo(app, 20)
        capturar._editable(w, app)
        w.a_ejecutar.setChecked(True)
        w.rt.stop()
        capturar._reposo(app, 20)
        menus: list[list[str]] = []

        def vigila() -> None:
            m = QApplication.activePopupWidget()
            if m is not None:
                menus.append([a.text() for a in m.actions() if a.text()])
                m.close()
        reloj = QTimer()
        reloj.timeout.connect(vigila)
        reloj.start(20)
        var = next(v for v in w.botones if w.nombre(v) == "marcha")
        b = w.botones[var]

        def valor():
            return w.v.state().get("values", {}).get(var)
        ayuda = getattr(w, "l_ayuda_entradas", None)  # (en `main` no hay rótulo bajo «Entradas»)
        if ayuda is not None:
            print("texto de ayuda bajo «Entradas»:", repr(ayuda.text()))
            comprobar("rótulo bajo «Entradas» sin «mantener»", "mantener" not in ayuda.text().lower(), ayuda.text())
            comprobar("rótulo bajo «Entradas» dice clic, Ctrl+clic y clic derecho",
                      all(x in ayuda.text() for x in ("Clic: pulsar", "Ctrl+clic: enclavar", "Clic derecho")))
        comprobar("tooltip sin «mantener pulsado»", "mantener pulsado" not in b.toolTip(), b.toolTip().replace("\n", " | "))
        comprobar("reposo: la entrada vale 0", valor() is not True)
        QTest.mousePress(b, Qt.MouseButton.LeftButton)
        QTest.qWait(1500)
        comprobar("mantenido 1,5 s: la entrada vale 1", valor() is True, f"valor={valor()}")
        comprobar("mantenido 1,5 s: el botón sigue apretado (down=True)", b.isDown())
        comprobar("mantenido 1,5 s: no se abrió ningún menú", not menus, str(menus))
        QTest.mouseRelease(b, Qt.MouseButton.LeftButton)
        QTest.qWait(80)
        comprobar("al soltar vuelve a 0", valor() is not True, f"valor={valor()}")
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QContextMenuEvent
        QApplication.sendEvent(b, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(20, 10), b.mapToGlobal(QPoint(20, 10))))
        QTest.qWait(120)
        comprobar("clic derecho: menú de tipo", bool(menus) and any("interruptor" in t.lower() for t in menus[-1]), str(menus))
        menus.clear()
        QTest.mousePress(b, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(700)
        comprobar("Ctrl+clic mantenido: enclavado a 1", valor() is True and b.enclavado, f"valor={valor()} enclavado={b.enclavado}")
        QTest.mouseRelease(b, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(80)
        comprobar("Ctrl+clic: sigue a 1 tras soltar el ratón", valor() is True)
        QTest.mouseClick(b, Qt.MouseButton.LeftButton)
        QTest.qWait(80)
        comprobar("otro clic lo libera", valor() is not True)
        # el foco por clic es el de `main`: clic y luego Espacio repite la pulsación (y el anillo no sale con el ratón)
        w.activateWindow()
        QTest.qWait(60)
        QTest.mouseClick(b, Qt.MouseButton.LeftButton)
        QTest.qWait(60)
        comprobar("un clic da el foco a la entrada", b.hasFocus(), str(app.focusWidget()))
        comprobar("el foco por clic no pinta el anillo", not b.property("tecl"))
        QTest.keyPress(b, Qt.Key.Key_Space)
        QTest.qWait(150)
        comprobar("clic y luego Espacio mantenido: la entrada vale 1", valor() is True, f"valor={valor()}")
        QTest.keyRelease(b, Qt.Key.Key_Space)
        QTest.qWait(150)
        comprobar("al soltar Espacio vuelve a 0", valor() is not True, f"valor={valor()}")
        detalle = getattr(w, "l_detalle", None)  # (en `main` no hay línea de detalle)
        if detalle is not None:
            # el nombre entero sin teclado y sin esperar a la ayuda emergente: al pulsar la entrada y al pasar el ratón por encima
            QTest.mouseClick(w.diagrama.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
            QTest.qWait(60)
            comprobar("sin nada señalado, la línea de detalle está escondida", not detalle.isVisibleTo(w), detalle.text())
            QTest.mouseClick(b, Qt.MouseButton.LeftButton)
            QTest.qWait(60)
            comprobar("al pulsar una entrada, la línea de detalle dice su nombre", "marcha" in detalle.text() and detalle.isVisibleTo(w), detalle.text())
            QTest.mouseClick(w.diagrama.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
            QTest.qWait(60)
            QTest.mouseMove(b, QPoint(20, 10))
            QTest.qWait(100)
            comprobar("al pasar el ratón por una entrada, la línea de detalle dice su nombre", "marcha" in detalle.text() and detalle.isVisibleTo(w), detalle.text())
            QTest.mouseMove(w.diagrama.viewport(), QPoint(40, 40))
            QTest.qWait(100)
            comprobar("al salir el ratón, la línea de detalle se esconde", not detalle.isVisibleTo(w), detalle.text())
            tabla = w.t_vars
            if tabla.rowCount():
                QTest.mouseMove(tabla.viewport(), tabla.visualRect(tabla.model().index(0, 0)).center())
                QTest.qWait(100)
                esperado = tabla.item(0, 0).text()
                comprobar("al pasar el ratón por una fila de la tabla, la línea de detalle dice su nombre entero", esperado in detalle.text(), detalle.text())
                QTest.mouseMove(w.diagrama.viewport(), QPoint(40, 40))
                QTest.qWait(100)
                comprobar("al salir de la tabla, la línea de detalle se esconde", not detalle.isVisibleTo(w), detalle.text())
        reloj.stop()
        w.rt.stop()
        w.a_ejecutar.blockSignals(True)
        w.a_ejecutar.setChecked(False)
        w.a_ejecutar.blockSignals(False)
        w.edicion = None
        w.hide()
        w.deleteLater()
        capturar._reposo(app)
        parche.stop()
    print("RESULTADO:", "todas las comprobaciones se cumplen" if not fallos else f"fallan {len(fallos)}: {fallos}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
