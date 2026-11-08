"""Mide la interfaz y escribe cifras que `CAMBIOS.md` puede citar: nada de lo que allí se declara sale de otro sitio.

Uso, desde la raíz del repositorio (con el Python del proyecto):

    python propuesta/herramientas/medir.py                       # todo, a los seis tamaños
    python propuesta/herramientas/medir.py alturas letras        # solo esas mediciones
    python propuesta/herramientas/medir.py --tamanos 1366 minima --json medidas.json

Mediciones:
- `franjas`   alto de cada franja sobre el dibujo, tamaño del dibujo y mínimo de la ventana (las pruebas fijan: dibujo antes de
              los 140 px a 1366×768).
- `alturas`   alto real de los controles principales y lista de los visibles de menos de 32 px.
- `letras`    tamaño de letra efectivo (px) de todo lo visible que lleva texto: el menor y los que bajan de 12 px.
- `ancho`     ancho mínimo de la ventana con nombres largos de grafcet, variable y entrada (a 1366 y a 640 px).
- `teclado`   orden de Tab, controles obligatorios alcanzables y activables con Espacio e Intro, y foco solo con teclado.
- `contraste` contraste WCAG medido sobre los píxeles de la ventana (texto sobre su fondo, anillo de foco, luz de E/S…).
- `propiedades` con una transición elegida y Propiedades abierto: alto del panel, alto del dibujo y si lo elegido se ve (P-IMP-93).
- `literales` colores y tamaños de letra escritos a mano en `escritorio/*.py` (no abre la ventana).
Los contrastes de las parejas de tokens (sin ventana) los comprueba `contrastes.py`.
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

LARGO = "Estación de clasificación y etiquetado de piezas con doble cilindro neumático y cinta transportadora (práctica 7)"
EXENTOS_ALTURA = {"PestanaPanel"}  # las pestañas de los paneles plegados miden 26 px (lo fijan las pruebas, ver PROPUESTAS_PENDIENTES P4)


class Ventana:
    """Una ventana nueva a un tamaño, en una escena de capturar.py, y su limpieza."""

    def __init__(self, tamano: str, escena: str = "editor") -> None:
        self.tamano, self.escena = tamano, escena

    def __enter__(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from escritorio.ventana import Ventana as V
        self.app = QApplication.instance() or QApplication([])
        self.tmp = tempfile.TemporaryDirectory()
        self.parche = mock.patch("escritorio.carpetas.QStandardPaths.writableLocation", return_value=self.tmp.name)
        self.parche.start()
        self.w = w = V(QSettings(self.tmp.name + "/ui.ini", QSettings.Format.IniFormat), Path(self.tmp.name) / "recuperacion")
        ancho, alto = capturar.TAMANOS[self.tamano]
        w.resize(ancho, alto)
        w.show()
        capturar._reposo(self.app)
        w.resize(ancho, alto)
        capturar._reposo(self.app)
        if self.escena == "planos":
            capturar.escena_planos(w, self.app, self.tmp.name)
        else:
            {"editor": capturar.escena_editor, "simulacion": capturar.escena_simulacion, "propiedades": capturar.escena_propiedades,
             "es": capturar.escena_es}[self.escena](w, self.app)
        capturar._reposo(self.app, 30)
        return w

    def __exit__(self, *a) -> None:
        w = self.w
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
            w._mostrar_pagina(False)
            capturar._reposo(self.app)
        w.edicion = None
        w.hide()
        w.deleteLater()
        capturar._reposo(self.app)
        self.parche.stop()
        self.tmp.cleanup()


def _y(w, x) -> int:
    from PySide6.QtCore import QPoint
    return x.mapTo(w, QPoint(0, 0)).y()


def franjas(tamano: str) -> dict:
    out = {}
    for escena in ("editor", "simulacion"):
        with Ventana(tamano, escena) as w:
            out[escena] = {"menu": w.menuBar().height(), "fila de pestañas": w.fila_pestanas.height(),
                           "herramientas": 0 if w.herramientas_grafcet.isHidden() else w.herramientas_grafcet.height(),
                           "herramientas fusionadas con las pestañas": w.herramientas_grafcet.parentWidget() is w.fila_pestanas,
                           "dibujo empieza en y": _y(w, w.diagrama), "dibujo": f"{w.diagrama.width()}×{w.diagrama.height()}",
                           "ancho de la ventana": w.width(), "mínimo de la ventana": w.minimumSizeHint().width(),
                           "barra de zoom en la cabecera": w.diagrama.barra_integrada, "estado": w.statusBar().height()}
    return out


def alturas(tamano: str) -> dict:
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit
    out = {}
    for escena in ("editor", "simulacion", "propiedades"):
        with Ventana(tamano, escena) as w:
            principales = {"Play/Stop": w.tb_sim.widgetForAction(w.a_ejecutar), "Reiniciar": w.tb_sim.widgetForAction(w.a_reiniciar),
                           "luz de E/S": w.luz_es, "Fijar": w.props.t_fijar, "zoom −": w.diagrama.b_menos, "zoom +": w.diagrama.b_mas,
                           "Centrar todo": w.diagrama.b_ajustar, "Centrar selección": w.diagrama.b_seleccion,
                           "+ Entrada": w.variables.b_nuevas["input"], "Eliminar": w.variables.b_quitar}
            for _n, b in list(w.botones.items())[:1]:
                principales["entrada de simulación"] = b
            if w.tb_edit.isVisible():
                principales["Añadir debajo"] = w.tb_edit.widgetForAction(w.a_debajo)
            principales["Mostrar dependencias"] = w.diagrama.b_dependencias
            if getattr(w.props, "prog", None) is not None and getattr(w.props.prog, "categorias", None):
                principales["categoría de bloques"] = next(iter(w.props.prog.categorias.values()))
            medidas = {k: v.height() for k, v in principales.items() if v.isVisibleTo(w)}
            pequenos = []
            for clase in (QAbstractButton, QComboBox, QLineEdit):
                for c in w.findChildren(clase):
                    if c.isVisible() and 0 < c.height() < 32 and c.width() > 12 and type(c).__name__ not in EXENTOS_ALTURA:
                        texto = (c.text() if hasattr(c, "text") else "") or c.toolTip() or c.objectName()
                        pequenos.append(f"{type(c).__name__}:{texto[:24]}={c.height()}")
            out[escena] = {"principales": medidas, "visibles de menos de 32 px": sorted(set(pequenos))}
    return out


def letras(tamano: str) -> dict:
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QHeaderView, QLabel, QLineEdit
    out = {}
    for escena in ("editor", "simulacion", "propiedades", "es", "planos"):
        with Ventana(tamano, escena) as w:
            menores, bajos = 99, set()
            for c in (w.findChildren(QLabel) + w.findChildren(QAbstractButton) + w.findChildren(QLineEdit) + w.findChildren(QComboBox)
                      + w.findChildren(QHeaderView)):
                if not c.isVisible() or c.width() < 6:
                    continue
                texto = getattr(c, "text", lambda: "x")()
                if not (texto or isinstance(c, (QHeaderView, QComboBox))):
                    continue
                px = c.fontInfo().pixelSize()
                menores = min(menores, px)
                if px < 12:
                    bajos.add(f"{type(c).__name__}:{str(texto)[:26]}={px}px")
            out[escena] = {"menor (px)": menores, "por debajo de 12 px": sorted(bajos)}
    return out


def ancho(tamano: str) -> dict:
    """Mínimo de la ventana con cadenas largas por todas partes (el tamaño dado sirve solo para crear la ventana)."""
    from PySide6.QtWidgets import QApplication
    out = {}
    with Ventana(tamano, "editor") as w:
        app = QApplication.instance()
        out["editor, nombres cortos"] = w.minimumSizeHint().width()
        e = w.edicion
        e.titulo = LARGO
        e.nueva_variable("variable_de_entrada_con_un_nombre_larguisimo_de_verdad_para_la_prueba", "input")
        e.nueva_variable("salida_con_un_nombre_larguisimo_de_verdad_para_la_prueba", "output")
        w.refrescar_edicion()
        capturar._reposo(app, 20)
        out["editor, título y variables largos"] = w.minimumSizeHint().width()
        w.a_ejecutar.setChecked(True)
        w.rt.stop()
        capturar._reposo(app, 30)
        out["simulación, título y entradas largos"] = w.minimumSizeHint().width()
        w.a_ejecutar.blockSignals(True)
        w.a_ejecutar.setChecked(False)
        w.a_ejecutar.blockSignals(False)
        w.mostrar_es()
        capturar._reposo(app, 30)
        out["E/S externas, variables largas"] = w.minimumSizeHint().width()
        w._mostrar_pagina(False)
        capturar._reposo(app, 10)
    return out


OBLIGATORIOS = (("luz de E/S", "luz_es"), ("Play", "play"), ("Reiniciar", "reiniciar"), ("Añadir debajo", "debajo"),
                ("Mostrar dependencias", "dependencias"), ("zoom −", "menos"), ("zoom +", "mas"), ("Centrar todo", "ajustar"),
                ("Centrar selección", "seleccion"), ("flecha ◂ del panel Elementos", "flecha_izq"),
                ("flecha ▸ del panel Variables", "flecha_der"), ("pestaña Propiedades", "pest_inf"), ("+ Entrada", "nueva_input"),
                ("+ Salida", "nueva_output"), ("+ Memoria", "nueva_internal"), ("Eliminar", "quitar"), ("Fijar", "fijar"))


def _objetivos(w) -> dict:
    d = w.diagrama
    return {"luz_es": w.luz_es, "play": w.tb_sim.widgetForAction(w.a_ejecutar), "reiniciar": w.tb_sim.widgetForAction(w.a_reiniciar),
            "debajo": w.tb_edit.widgetForAction(w.a_debajo), "dependencias": d.b_dependencias, "menos": d.b_menos, "mas": d.b_mas,
            "ajustar": d.b_ajustar, "seleccion": d.b_seleccion, "flecha_izq": w.flechas["izquierdo"],
            "flecha_der": w.flechas["derecho"], "pest_inf": w.pestanas["inferior"], "nueva_input": w.variables.b_nuevas["input"],
            "nueva_output": w.variables.b_nuevas["output"], "nueva_internal": w.variables.b_nuevas["internal"],
            "quitar": w.variables.b_quitar, "fijar": w.props.t_fijar}


def teclado(tamano: str) -> dict:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    out = {}
    with Ventana(tamano, "editor") as w:
        app = QApplication.instance()
        w.activateWindow()
        w.diagrama.setFocus(Qt.FocusReason.OtherFocusReason)
        capturar._reposo(app, 10)
        out["foco al arrancar en el dibujo y sin anillo"] = bool(w.focusWidget() is w.diagrama and not w.diagrama.property("tecl"))
        recorrido = []
        for _ in range(120):
            siguiente = w.focusNextPrevChild(True)
            capturar._reposo(app, 2)
            f = w.focusWidget()
            if f is w.diagrama and recorrido:
                break
            recorrido.append((type(f).__name__, (getattr(f, "text", lambda: "")() or f.objectName() or f.accessibleName())[:24]))
            if not siguiente:
                break
        out["Tab recorre (paradas)"] = len(recorrido)
        out["orden de Tab"] = [f"{a}:{b}" for a, b in recorrido]
        objetivos = _objetivos(w)
        ok, faltan = [], []
        for nombre, clave in OBLIGATORIOS:
            b = objetivos.get(clave)
            if b is None or not b.isVisibleTo(w):
                faltan.append(nombre + " (oculto a este tamaño o en este modo)")
                continue
            alcanzable = b.focusPolicy() in (Qt.FocusPolicy.TabFocus, Qt.FocusPolicy.StrongFocus)
            (ok if alcanzable else faltan).append(nombre)
        out["alcanzables con Tab"] = ok
        out["no alcanzables u ocultos"] = faltan
        activables = {}
        play = objetivos["play"]
        res = []
        for tecla in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            play.setFocus(Qt.FocusReason.TabFocusReason)
            w._mostrar_pagina(False)
            antes = w.a_ejecutar.isChecked()
            QTest.keyClick(play, tecla)
            QTest.qWait(180)
            res.append(w.a_ejecutar.isChecked() != antes)
            if w.a_ejecutar.isChecked():
                w.a_ejecutar.setChecked(False)  # (con sus señales: vuelve al modo de edición)
            w.rt.stop()
            capturar._reposo(app, 20)
        activables["Play"] = {"Espacio": res[0], "Intro": res[1]}
        for nombre, clave in OBLIGATORIOS:
            b = objetivos.get(clave)
            if clave == "debajo" and b is not None:
                w.edicion.seleccionar([w.edicion.M["steps"][0]["id"]])
                capturar._reposo(app, 10)
            if b is None or not b.isVisibleTo(w) or not b.isEnabled() or clave in ("play",):
                continue
            cuentas: list[int] = []
            b.clicked.connect(lambda *_a, c=cuentas: c.append(1))
            res = []
            for tecla in (Qt.Key.Key_Space, Qt.Key.Key_Return):
                if clave == "debajo":
                    w.edicion.seleccionar([w.edicion.M["steps"][0]["id"]])  # (solo se puede añadir debajo con un elemento elegido)
                    capturar._reposo(app, 10)
                if clave == "pest_inf":
                    w._mostrar_panel("inferior", False, guardar=False)  # (al abrirse el panel, su pestaña se esconde: se vuelve a plegar)
                    capturar._reposo(app, 10)
                b.setFocus(Qt.FocusReason.TabFocusReason)
                capturar._reposo(app, 2)
                antes = len(cuentas)
                QTest.keyClick(b, tecla)
                QTest.qWait(180)  # (Intro pulsa el botón con animateClick: el clic llega ~100 ms después)
                res.append(len(cuentas) > antes)
                if w.paginas_es.currentIndex() != 0:
                    w._mostrar_pagina(False)
                    capturar._reposo(app, 10)
            activables[nombre] = {"Espacio": res[0], "Intro": res[1]}
        out["activables (el clic sale con la tecla)"] = activables
        out["un clic de ratón no da foco a un botón"] = objetivos["menos"].focusPolicy() == Qt.FocusPolicy.TabFocus
    return out


def _luminancia(c) -> float:
    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c.redF()) + 0.7152 * f(c.greenF()) + 0.0722 * f(c.blueF())


def _ratio(a, b) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def contraste_px(imagen, rect) -> tuple[float, str, str]:
    """Contraste entre el color de fondo (el más frecuente del rectángulo) y el color más alejado de él, en píxeles de la captura."""
    from collections import Counter
    from PySide6.QtGui import QColor
    cuentas: Counter = Counter()
    for y in range(max(0, rect.top()), min(imagen.height(), rect.bottom() + 1)):
        for x in range(max(0, rect.left()), min(imagen.width(), rect.right() + 1)):
            cuentas[imagen.pixel(x, y) & 0xFFFFFF] += 1
    if not cuentas:
        return 0.0, "", ""
    fondo = QColor.fromRgb(cuentas.most_common(1)[0][0])
    frente = max((QColor.fromRgb(c) for c, n in cuentas.items() if n >= 2), key=lambda c: _ratio(c, fondo), default=fondo)
    return _ratio(frente, fondo), frente.name(), fondo.name()


def contraste(tamano: str) -> dict:
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtWidgets import QApplication
    out = {}

    def medir(w, nombre, widget, interior=0):
        imagen = w.grab().toImage()
        r = QRect(widget.mapTo(w, QPoint(0, 0)), widget.size()).adjusted(interior, interior, -interior, -interior)
        ratio, f, b = contraste_px(imagen, r)
        out[nombre] = f"{ratio:.2f}:1 ({f} sobre {b})"

    with Ventana(tamano, "editor") as w:
        app = QApplication.instance()
        medir(w, "chip EDICIÓN", w.estado, 3)
        medir(w, "Play", w.tb_sim.widgetForAction(w.a_ejecutar), 5)
        if w.tb_sim.widgetForAction(w.a_reiniciar).isVisibleTo(w):
            medir(w, "Reiniciar", w.tb_sim.widgetForAction(w.a_reiniciar), 5)
        medir(w, "luz de E/S cerrada", w.luz_es, 4)
        medir(w, "pestaña activa GRAFCET", w.pestanas_vistas, 2)
        medir(w, "título del grafcet", w.titulo, 0)
        play = w.tb_sim.widgetForAction(w.a_ejecutar)
        play.setFocus(Qt.FocusReason.TabFocusReason)
        capturar._reposo(app, 10)
        imagen = w.grab().toImage()
        r = QRect(play.mapTo(w, QPoint(0, 0)), play.size())
        banda = [imagen.pixelColor(x, y) for y in range(r.top(), r.bottom() + 1) for x in range(r.left(), r.right() + 1)]
        relleno = imagen.pixelColor(r.center().x(), r.bottom() - 8)
        fuera = imagen.pixelColor(r.left() - 3, r.center().y())
        anillo = min(banda, key=_luminancia)  # el trazo más oscuro del botón: el anillo discontinuo de 3 px
        out["Play con foco: anillo contra su relleno"] = f"{_ratio(anillo, relleno):.2f}:1 ({anillo.name()} sobre {relleno.name()})"
        out["Play con foco: anillo contra el fondo exterior"] = f"{_ratio(anillo, fuera):.2f}:1 ({anillo.name()} sobre {fuera.name()})"
        w.luz_es.click()
        capturar._reposo(app, 10)
        medir(w, "luz de E/S abierta (blanca, borde oscuro, negrita)", w.luz_es, 4)
        out["luz abierta: propiedad `abierta` activa"] = bool(w.luz_es.property("abierta"))
        w._mostrar_pagina(False)
    with Ventana(tamano, "editor") as w:
        app = QApplication.instance()
        w._mostrar_pagina("planos")  # sin hojas: «+ Añadir hoja» parpadea entre dos tonos
        capturar._reposo(app, 20)
        pl = w.panel_planos
        pl.t_hoja.stop()
        for fase, nombre in ((True, "«+ Añadir hoja», tono oscuro"), (False, "«+ Añadir hoja», tono claro del parpadeo")):
            pl.estilo_boton_hoja(fase)
            capturar._reposo(app, 10)
            medir(w, nombre, pl.b_hoja, 6)
        w._mostrar_pagina(False)
        capturar._reposo(app, 10)
        w.mostrar_es()
        capturar._reposo(app, 30)
        from escritorio.entradas_salidas import IndicadorES
        barras = [b for b in w.findChildren(IndicadorES) if b.isVisible() and b.width() <= 6]
        if barras:
            imagen = w.grab().toImage()
            b = barras[0]
            r = QRect(b.mapTo(w, QPoint(0, 0)), b.size()).adjusted(-3, -3, 3, 3)
            ratio, f, fondo = contraste_px(imagen, r)
            out["barra de canal de E/S (borde contra el fondo del panel)"] = f"{ratio:.2f}:1 ({f} sobre {fondo})"
        w._mostrar_pagina(False)
    with Ventana(tamano, "simulacion") as w:
        medir(w, "chip SIMULACIÓN", w.estado, 3)
        medir(w, "Stop", w.tb_sim.widgetForAction(w.a_ejecutar), 5)
        b = next(iter(w.botones.values()))
        medir(w, "entrada de simulación (texto)", b, 6)
        medir(w, "texto de ayuda de las entradas", w.l_ayuda_entradas, 0)
        from PySide6.QtGui import QColor
        from escritorio.diagrama import COL
        out["verde de «verdadero» del lienzo (COL true_text) sobre blanco"] = (
            f"{_ratio(QColor(COL['true_text']), QColor('white')):.2f}:1 ({COL['true_text']})")
        out["etapa activa (COL active)"] = COL["active"]
    return out


def propiedades(tamano: str) -> dict:
    """Con una transición elegida y el panel de Propiedades abierto: alto del panel, alto que queda al dibujo y si lo elegido se ve."""
    from PySide6.QtCore import QPointF, QRectF
    with Ventana(tamano, "propiedades") as w:
        d = w.diagrama
        caja = d._caja_seleccion()
        visible = d.mapToScene(d.viewport().rect()).boundingRect()
        return {"alto de la ventana": w.height(), "alto del panel inferior": w.inferior.height(),
                "alto del dibujo con el panel abierto": d.height(), "alto de la fila de categorías de bloques": w.props.prog._sc_carpetas.height()
                if getattr(w.props, "prog", None) is not None else None,
                "la transición elegida queda a la vista": bool(caja is not None and visible.contains(QRectF(caja))),
                "zoom": f"{round(d.transform().m11() * 100)} %"}


def literales(_tamano: str = "") -> dict:
    """Colores `#rrggbb`/`#rgb` y tamaños de letra escritos a mano en `escritorio/*.py`, por fichero (no necesita ventana).
    El dibujo (`diagrama`, `edicion`, `anotaciones`), los bloques, las plantillas de plano y los tipos de variable de E/S llevan
    colores propios del documento, no de la interfaz: se cuentan aparte."""
    import re
    carpeta = capturar.RAIZ / "escritorio"
    documento = {"anotaciones.py", "diagrama.py", "edicion.py", "bloques.py", "plantillas.py", "importar_plantillas.py", "laminas.py"}
    hexa, interfaz, pequenas = {}, {}, []
    for f in sorted(carpeta.glob("*.py")):
        texto = f.read_text(encoding="utf-8")
        n = len(re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", texto))
        if n:
            hexa[f.name] = n
            if f.name not in documento and f.name != "estilo.py":
                interfaz[f.name] = n
        for m in re.finditer(r"font-size\s*:\s*(\d+)px", texto):
            if int(m.group(1)) < 12:
                pequenas.append(f"{f.name}: font-size {m.group(1)}px")
    return {"colores literales por fichero": hexa, "de ellos, en estilo.py (las definiciones de los tokens)": hexa.get("estilo.py", 0),
            "en ficheros de interfaz (ni estilo.py ni documento)": interfaz, "total": sum(hexa.values()),
            "font-size de menos de 12 px escritos a mano": pequenas}


MEDICIONES = {"franjas": franjas, "alturas": alturas, "letras": letras, "ancho": ancho, "teclado": teclado, "contraste": contraste,
              "propiedades": propiedades, "literales": literales}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mediciones", nargs="*", choices=list(MEDICIONES), help="por defecto, todas")
    ap.add_argument("--tamanos", nargs="+", choices=list(capturar.TAMANOS), default=list(capturar.TAMANOS))
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    todo: dict = {}
    for m in a.mediciones or list(MEDICIONES):
        todo[m] = {}
        for t in a.tamanos:
            if m in ("teclado", "contraste", "ancho") and t not in ("1366", "minima", "completa"):
                continue  # estas se miden a los tamaños de referencia (el más habitual y el más pequeño)
            if m == "literales" and t != a.tamanos[0]:
                continue  # no depende del tamaño
            try:
                todo[m][t] = MEDICIONES[m](t)
            except Exception as exc:  # una medición rota no impide las demás
                todo[m][t] = f"{type(exc).__name__}: {exc}"
            print(f"== {m} · {t} {capturar.TAMANOS[t]}")
            print(json.dumps(todo[m][t], ensure_ascii=False, indent=1))
    if a.json:
        a.json.write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
