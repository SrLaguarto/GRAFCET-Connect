"""Prueba del selector real de PanelAccion en un proceso con una escala de pantalla concreta."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEvent, QPointF, QSignalBlocker, Qt
from PySide6.QtTest import QTest
from escritorio import estilo
from escritorio.acciones import PanelAccion
from escritorio.estilo_botones import instalar
from tools import hoja_contactos as hc


def bombear():
    hc._bombear(8)


def elegir_raton(combo, dato, nombre):
    QTest.qWait(160)  # Qt protege de soltar el clic que acaba de abrir el desplegable.
    modelo = combo.model().index(combo.findData(dato), 0)
    combo.view().scrollTo(modelo)
    bombear()
    fila = combo.view().visualRect(modelo)
    assert fila.isValid(), "La fila elegible debe tener geometría"
    captura = os.environ.get("V_CAPTURAS")
    if captura:
        salida = Path(captura)
        salida.mkdir(parents=True, exist_ok=True)
        factor = os.environ["QT_SCALE_FACTOR"]
        combo.view().window().grab().save(str(salida / f"{nombre}_{factor}.png"))
    QTest.mouseMove(combo.view().viewport(), fila.center())
    QTest.qWait(30)
    QTest.mouseClick(combo.view().viewport(), Qt.MouseButton.LeftButton, pos=fila.center())
    bombear()


def comprobar(c, tipo):
    if tipo == "evento":
        c.e.poner_accion(c.ids["etapas"][2],
                         {"tipo": tipo, "variable": "aux", "valor": "1", "evento": "↑marcha"})
    aid = next(a["id"] for a in c.e.ed.model["actions"] if c.e.datos_accion(a["id"])["tipo"] == tipo)
    panel = PanelAccion()
    panel.setStyleSheet(estilo.hoja_global())
    panel.mostrar(c.e, aid)
    panel.resize(540, 360)
    panel.show()
    bombear()
    combo = panel.variable
    try:
        assert combo.isVisible() and combo.isEnabled(), "El selector debe estar visible y habilitado"
        assert not combo.testAttribute(Qt.WidgetAttribute.WA_SetStyle), "No debe imponer un estilo propio"
        factor = float(os.environ["QT_SCALE_FACTOR"])
        assert abs(panel.devicePixelRatioF() - factor) < 0.02, panel.devicePixelRatioF()
        QTest.mouseClick(combo, Qt.MouseButton.LeftButton, pos=combo.rect().center())
        bombear()
        assert combo.view().isVisible(), "El ratón debe abrir la lista"
        elegir_raton(combo, "motor", tipo)
        assert not combo.view().isVisible(), "La elección con ratón debe cerrar la lista"
        assert c.e.datos_accion(aid)["variable"] == "motor", "El ratón debe aplicar la variable elegida"
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_F4)
        bombear()
        assert combo.view().isVisible(), "F4 debe abrir la lista"
        QTest.keyClick(combo.view(), Qt.Key.Key_End)
        QTest.keyClick(combo.view(), Qt.Key.Key_Return)
        bombear()
        assert c.e.datos_accion(aid)["variable"] == "aux", "El teclado debe aplicar la variable elegida"
        assert not combo.view().isVisible(), "Intro debe cerrar la lista"
        combo.showPopup()
        bombear()
        assert combo.view().isVisible()
        QTest.keyClick(combo.view(), Qt.Key.Key_Escape)
        bombear()
        assert not combo.view().isVisible(), "Esc debe cerrar la lista"
        assert c.e.datos_accion(aid)["variable"] == "aux", "Esc no cambia la variable"
        return {"tipo": tipo, "dpr": panel.devicePixelRatioF(), "raton": True, "teclado": True, "esc": True}
    finally:
        panel.close()
        panel.deleteLater()


def abrir_sobre_dibujo(c, aid):
    vista = c.w.diagrama
    caja = next(caja for caja in vista.cajas_acciones if caja["id"] == aid)
    x, y, ancho, alto = caja["rect"]
    punto = vista.mapFromScene(QPointF(x + ancho / 2, y + alto / 2))
    QTest.mouseDClick(vista.viewport(), Qt.MouseButton.LeftButton, pos=punto)
    bombear()
    combo = vista._selector
    assert combo is not None, "El doble clic debe abrir el selector sobre el dibujo"
    assert combo.view().isVisible(), "La lista sobre el dibujo debe permanecer abierta"
    assert not combo.testAttribute(Qt.WidgetAttribute.WA_SetStyle)
    return combo


def comprobar_dibujo(c):
    with QSignalBlocker(c.e):
        for numero in range(15):
            c.e.nueva_variable(f"variable_de_prueba_{numero:02d}", "output")
    c.e.cambiado.emit()
    sid = c.ids["etapas"][1]
    for numero in range(3):
        aid = c.e.poner_accion_suelta(QPointF(500 + numero * 100, 200))
        c.e.unir_accion(aid, sid)
    bombear()
    combo = abrir_sobre_dibujo(c, aid)
    elegir_raton(combo, "variable_de_prueba_14", "sobre_dibujo")
    assert c.w.diagrama._selector is None, "Elegir con ratón debe cerrar el selector sobre el dibujo"
    pendientes = [a for a in c.e.acciones(sid) if a.get("borrador")]
    assert len(pendientes) == 2 and all(not a["variable"] for a in pendientes)
    caja = next(caja for caja in c.w.diagrama.cajas_acciones
                if c.e.datos_accion(caja["id"])["variable"] == "variable_de_prueba_14")
    aid = caja["id"]
    combo = abrir_sobre_dibujo(c, aid)
    QTest.keyClick(combo.view(), Qt.Key.Key_End)
    QTest.keyClick(combo.view(), Qt.Key.Key_Return)
    bombear()
    assert c.w.diagrama._selector is None, "Intro debe cerrar el selector sobre el dibujo"
    assert c.e.datos_accion(aid)["variable"] == "aux"
    combo = abrir_sobre_dibujo(c, aid)
    QTest.keyClick(combo.view(), Qt.Key.Key_Escape)
    bombear()
    assert c.w.diagrama._selector is None, "Esc debe cerrar el selector sobre el dibujo"
    assert c.e.datos_accion(aid)["variable"] == "aux"
    return {"tipo": "continua_sobre_dibujo", "dpr": c.w.devicePixelRatioF(),
            "raton": True, "teclado": True, "esc": True}


def main():
    app = hc.aplicacion()
    instalar(app)
    c = hc.Contexto(1366, 768)
    try:
        hc._edicion(c)
        resultados = [comprobar(c, tipo) for tipo in ("condicionada", "evento")]
        resultados.append(comprobar_dibujo(c))
        print(json.dumps(resultados))
    finally:
        c.cerrar()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    main()
