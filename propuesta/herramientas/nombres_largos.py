"""Comprueba que los nombres largos se leen: con dos juegos de nombres (los de la propuesta, «sensor_final_carrera_cilindro_NN_avance», y los
de un aula de neumática, «final_carrera_cilindro_A_avance», «electrovalvula_cilindro_B_retroceso», «piloto_marcha»…), en cada tamaño de ventana
y en cada lista, **todos los textos que se ven son distintos y legibles**:

- no hay dos nombres distintos que se vean igual;
- ningún nombre visible tiene menos de 6 caracteres significativos (letras y cifras) si el nombre entero los tiene: nada de «…_…e»;
- los nombres de las tablas de la simulación, de Variables y de las entradas se enseñan **enteros**, partidos por los «_» en varias
  líneas (no se elide ninguno mientras quepan en tres líneas); solo las listas de la vista de E/S, de filas planas de 16 px (P-IMP-63),
  siguen en una línea y, si no cabe, se elide por el medio conservando lo que las distingue.

Uso, desde la raíz del repositorio (con el Python del proyecto):

    python propuesta/herramientas/nombres_largos.py
    python propuesta/herramientas/nombres_largos.py --tamanos 1366 cuarto
    python propuesta/herramientas/nombres_largos.py --juegos aula --detalle    # enseña lo que se ve de cada nombre

Las listas (cada una es «una misma lista» para quien lee):
- `Variables`            la tabla del panel de variables (al editar), columna del nombre.
- `Entradas`             los botones de entrada de la simulación (el texto que se pinta, con su « = 0»).
- `Salidas y variables`  la tabla de estado de la simulación, columnas «Variable» y «Contribuyen» (la de «Modo» se esconde si no hay sitio).
- `Temporizadores`       la tabla de estado, columna «Dónde».
- `E/S sensores` y `E/S actuadores`   las listas laterales de la vista de E/S.
- `E/S canales izquierda` y `E/S canales derecha`   los nombres asignados a los canales, a cada lado del PLC.

El texto que se ve es el que pintan el delegado de la tabla, el botón o la etiqueta (no el de la celda, que es siempre el entero): se
pide a los mismos objetos que lo pintan. Termina con código 1 si en alguna lista dos nombres distintos se ven igual o alguno es ilegible."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capturar  # noqa: E402  (fija la plataforma offscreen y la raíz del repositorio)
import medir  # noqa: E402

TAMANOS = ("completa", "partida", "cuarto", "1366", "estrecha", "minima")
CINTA = [f"sensor_final_de_carrera_cinta_transportadora_{n}" for n in range(1, 5)]
SIGNIFICATIVOS = 6  # lo menos que ha de quedar de un nombre largo: letras y cifras
SALTO = " "
JUEGOS = {
    "propio": ([f"sensor_final_carrera_cilindro_{i:02d}_avance" for i in range(32)] + CINTA,
               [f"electrovalvula_cilindro_{i:02d}_avance_principal" for i in range(6)]),
    "aula": (["pulsador_marcha", "pulsador_paro", "seta_emergencia", "selector_manual", "selector_automatico", "sensor_pieza_cinta",
              "detector_inductivo_metal", "detector_capacitivo_plastico", "presostato_linea_aire"]
             + [f"final_carrera_cilindro_{c}_{s}" for c in "ABC" for s in ("avance", "retroceso")],
             ["motor_cinta_transportadora", "piloto_marcha", "piloto_averia"]
             + [f"electrovalvula_cilindro_{c}_{s}" for c in "ABC" for s in ("avance", "retroceso")]),
}


def _celda(tabla, fila: int, columna: int) -> str:
    """Lo que se ve en una celda: el texto tal como lo deja el delegado de su columna (las líneas, separadas por «\\n»)."""
    from PySide6.QtWidgets import QStyleOptionViewItem
    indice = tabla.model().index(fila, columna)
    opcion = QStyleOptionViewItem()
    opcion.initFrom(tabla.viewport())
    opcion.rect = tabla.visualRect(indice)
    opcion.font = tabla.font()
    (tabla.itemDelegateForColumn(columna) or tabla.itemDelegate()).initStyleOption(opcion, indice)
    return opcion.text.replace(SALTO, "\n")


def _significativos(texto: str) -> int:
    return sum(1 for c in texto if c.isalnum())


def _revisar(nombre: str, enteros: list[str], vistos: list[str], informe: dict, detalle: bool) -> bool:
    """Una lista: dos nombres distintos no pueden verse igual y ninguno puede quedar ilegible (menos de 6 caracteres significativos)."""
    repetidos: dict[str, list[str]] = {}
    for entero, visto in zip(enteros, vistos):
        repetidos.setdefault(visto, []).append(entero)
    iguales = {v: n for v, n in repetidos.items() if len(set(n)) > 1}
    ilegibles = sorted({f"{e} → «{v}»" for e, v in zip(enteros, vistos)
                        if _significativos(e) >= SIGNIFICATIVOS and _significativos(v) < SIGNIFICATIVOS})
    partidos = sum(1 for e, v in zip(enteros, vistos) if "\n" in v)
    enteros_vistos = sum(1 for e, v in zip(enteros, vistos) if v.replace("\n", "") == e or v.replace("\n", " ") == e)
    informe[nombre] = {"nombres": len(set(enteros)), "textos distintos": len(set(vistos)), "partidos en líneas": partidos,
                       "recortados con «…»": sum(1 for v in vistos if "…" in v), "enteros": enteros_vistos,
                       "iguales": {v: sorted(set(n)) for v, n in iguales.items()}, "ilegibles": ilegibles,
                       "líneas como máximo": max((v.count("\n") + 1 for v in vistos), default=0)}
    if detalle:
        informe[nombre]["se ve"] = sorted(set(vistos))
    return not iguales and not ilegibles


def comprobar(tamano: str, juego: str = "propio", detalle: bool = False) -> tuple[bool, dict]:
    from PySide6.QtWidgets import QApplication
    entradas, salidas = JUEGOS[juego]
    informe: dict = {}
    bien = True
    with medir.Ventana(tamano, "editor") as w:
        app = QApplication.instance()
        e = w.edicion
        for n in entradas:
            e.ed.add_variable(n, "input", {"kind": "bool"})
        for n in salidas:
            e.ed.add_variable(n, "output", {"kind": "bool"})
        e.cambia()
        w.refrescar_edicion()
        capturar._reposo(app, 40)
        # 1. el panel de variables, al editar
        w._mostrar_panel("derecho", True)
        capturar._reposo(app, 40)
        t = w.variables.tabla
        enteros = [t.item(r, 0).text() for r in range(t.rowCount())]
        bien &= _revisar("Variables", enteros, [_celda(t, r, 0) for r in range(t.rowCount())], informe, detalle)
        informe["Variables"]["ancho de la columna del nombre"] = t.columnWidth(0)
        # 2. la simulación
        w.a_ejecutar.setChecked(True)
        w.rt.stop()
        capturar._reposo(app, 40)
        w.refrescar()
        capturar._reposo(app, 30)
        botones = [b for b in w.botones.values() if hasattr(b, "texto_visible")]
        bien &= _revisar("Entradas", [b.nombre_completo() for b in botones], [b.texto_visible().rpartition(" = ")[0] for b in botones], informe, detalle)
        for nombre, tabla, col in (("Salidas y variables", w.t_vars, 0), ("Salidas y variables (Contribuyen)", w.t_vars, 3), ("Temporizadores", w.t_temp, 0)):
            textos = [tabla.item(r, col).text() for r in range(tabla.rowCount()) if tabla.item(r, col) is not None]
            if textos:
                bien &= _revisar(nombre, textos, [_celda(tabla, r, col) for r in range(tabla.rowCount()) if tabla.item(r, col) is not None], informe, detalle)
        informe["Salidas y variables"]["ancho de la columna del nombre"] = w.t_vars.columnWidth(0)
        informe["Salidas y variables"]["columnas visibles"] = [w.t_vars.horizontalHeaderItem(c).text() for c in range(4) if not w.t_vars.isColumnHidden(c)]
        if "ancho de la columna del nombre" not in informe["Temporizadores"]:
            informe["Temporizadores"]["ancho de la columna del nombre"] = w.t_temp.columnWidth(0)
        w.a_ejecutar.setChecked(False)
        capturar._reposo(app, 30)
        # 3. la vista de E/S
        w.mostrar_es()
        capturar._reposo(app, 60)
        p = w.panel_es
        for nombre, lista in (("E/S sensores", p.lista_entradas), ("E/S actuadores", p.lista_salidas)):
            enteros = [lista.item(i).text() for i in range(lista.count())]
            d = lista.itemDelegate()
            vistos = [d.texto_visible(lista.model().index(i, 0), lista.viewport().width() - 8) for i in range(lista.count())]
            bien &= _revisar(nombre, enteros, vistos, informe, detalle)
        for nombre, areas in (("E/S canales izquierda", ("discrete", "input-register")), ("E/S canales derecha", ("coil", "holding"))):
            ts = [t for (area, _d), t in p.terminales.items() if area in areas and t.variable]
            ts.sort(key=lambda t: (t.area, t.direccion))
            bien &= _revisar(nombre, [t.variable["name"] for t in ts], [t.nombre.texto_visible() for t in ts], informe, detalle)
            if ts:
                informe[nombre]["ancho de la etiqueta"] = ts[0].nombre.width()
        w._mostrar_pagina(False)
    return bien, informe


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tamanos", nargs="+", choices=list(capturar.TAMANOS), default=list(TAMANOS))
    ap.add_argument("--juegos", nargs="+", choices=list(JUEGOS), default=list(JUEGOS))
    ap.add_argument("--detalle", action="store_true", help="enseña también el texto que se ve de cada nombre")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    todo_bien = True
    for juego in a.juegos:
        for tamano in a.tamanos:
            bien, informe = comprobar(tamano, juego, a.detalle)
            todo_bien &= bien
            print(f"== {juego} · {tamano} {capturar.TAMANOS[tamano]}: {'TODOS DISTINTOS Y LEGIBLES' if bien else 'HAY NOMBRES REPETIDOS O ILEGIBLES'}")
            for lista, datos in informe.items():
                malo = datos["iguales"] or datos["ilegibles"]
                extra = {k: v for k, v in datos.items() if k not in ("nombres", "textos distintos", "partidos en líneas", "recortados con «…»", "enteros",
                                                                    "iguales", "ilegibles", "líneas como máximo", "se ve")}
                print(f"  {'MAL' if malo else 'OK '} {lista}: {datos['nombres']} nombres, {datos['textos distintos']} textos distintos, "
                      f"{datos['enteros']} enteros ({datos['partidos en líneas']} en varias líneas, hasta {datos['líneas como máximo']}), "
                      f"{datos['recortados con «…»']} con «…» {extra or ''}")
                for visto, nombres in datos["iguales"].items():
                    print(f"       «{visto}» ← {nombres}")
                for x in datos["ilegibles"]:
                    print(f"       ilegible: {x}")
                if a.detalle:
                    for visto in datos.get("se ve", []):
                        print("       " + visto.replace("\n", " ⏎ "))
    print("RESULTADO:", "todas las listas se distinguen y se leen" if todo_bien else "FALLO")
    return 0 if todo_bien else 1


if __name__ == "__main__":
    sys.exit(main())
