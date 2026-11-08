"""Comprueba que los nombres largos se siguen distinguiendo: con los ejemplos de nombres largos que usa el árbitro (32 sensores
«sensor_final_carrera_cilindro_NN_avance», 6 actuadores «electrovalvula_cilindro_NN_avance_principal» y cuatro entradas de cinta
transportadora), **todos los textos que se ven en una misma lista son distintos**, en cada tamaño de ventana.

Uso, desde la raíz del repositorio (con el Python del proyecto):

    python propuesta/herramientas/nombres_largos.py
    python propuesta/herramientas/nombres_largos.py --tamanos 1366 cuarto
    python propuesta/herramientas/nombres_largos.py --detalle          # enseña lo que se ve de cada nombre

Las listas (cada una es «una misma lista» para quien lee):
- `Variables`            la tabla del panel de variables (al editar), columna del nombre.
- `Entradas`             los botones de entrada de la simulación (el texto que se pinta, con su « = 0»).
- `Salidas y variables`  la tabla de estado de la simulación, columnas «Variable» y «Contribuyen».
- `Temporizadores`       la tabla de estado, columna «Dónde».
- `E/S sensores` y `E/S actuadores`   las listas laterales de la vista de E/S.
- `E/S canales izquierda` y `E/S canales derecha`   los nombres asignados a los canales, a cada lado del PLC.

El texto que se ve es el que pintan el delegado de la tabla, el botón o la etiqueta (no el de la celda, que es siempre el entero): se
pide a los mismos objetos que lo pintan. Termina con código 1 si en alguna lista dos nombres distintos se ven igual."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capturar  # noqa: E402  (fija la plataforma offscreen y la raíz del repositorio)
import medir  # noqa: E402

TAMANOS = ("completa", "partida", "cuarto", "1366", "estrecha", "minima")
CINTA = [f"sensor_final_de_carrera_cinta_transportadora_{n}" for n in range(1, 5)]


def _celda(tabla, fila: int, columna: int) -> str:
    """Lo que se ve en una celda: el texto tal como lo deja el delegado de su columna."""
    from PySide6.QtWidgets import QStyleOptionViewItem
    indice = tabla.model().index(fila, columna)
    opcion = QStyleOptionViewItem()
    opcion.initFrom(tabla.viewport())
    opcion.rect = tabla.visualRect(indice)
    opcion.font = tabla.font()
    (tabla.itemDelegateForColumn(columna) or tabla.itemDelegate()).initStyleOption(opcion, indice)
    return opcion.text


def _revisar(nombre: str, enteros: list[str], vistos: list[str], informe: dict, detalle: bool) -> bool:
    """Una lista: dos nombres distintos no pueden verse igual."""
    repetidos: dict[str, list[str]] = {}
    for entero, visto in zip(enteros, vistos):
        repetidos.setdefault(visto, []).append(entero)
    iguales = {v: n for v, n in repetidos.items() if len(set(n)) > 1}
    informe[nombre] = {"nombres": len(set(enteros)), "textos distintos": len(set(vistos)),
                       "recortados": sum(1 for e, v in zip(enteros, vistos) if e != v),
                       "iguales": {v: sorted(set(n)) for v, n in iguales.items()}}
    if detalle:
        informe[nombre]["se ve"] = sorted(set(vistos))
    return not iguales


def comprobar(tamano: str, detalle: bool = False) -> tuple[bool, dict]:
    from PySide6.QtWidgets import QApplication
    informe: dict = {}
    bien = True
    with medir.Ventana(tamano, "editor") as w:
        app = QApplication.instance()
        e = w.edicion
        for i in range(32):
            e.ed.add_variable(f"sensor_final_carrera_cilindro_{i:02d}_avance", "input", {"kind": "bool"})
        for i in range(6):
            e.ed.add_variable(f"electrovalvula_cilindro_{i:02d}_avance_principal", "output", {"kind": "bool"})
        for n in CINTA:
            e.ed.add_variable(n, "input", {"kind": "bool"})
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
    ap.add_argument("--detalle", action="store_true", help="enseña también el texto que se ve de cada nombre")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    todo_bien = True
    for tamano in a.tamanos:
        bien, informe = comprobar(tamano, a.detalle)
        todo_bien &= bien
        print(f"== {tamano} {capturar.TAMANOS[tamano]}: {'TODOS DISTINTOS' if bien else 'HAY NOMBRES QUE SE VEN IGUAL'}")
        for lista, datos in informe.items():
            marca = "OK " if not datos["iguales"] else "MAL"
            extra = {k: v for k, v in datos.items() if k not in ("nombres", "textos distintos", "recortados", "iguales", "se ve")}
            print(f"  {marca} {lista}: {datos['nombres']} nombres, {datos['textos distintos']} textos distintos, {datos['recortados']} recortados {extra or ''}")
            for visto, nombres in datos["iguales"].items():
                print(f"       «{visto}» ← {nombres}")
            if a.detalle:
                for visto in datos.get("se ve", []):
                    print(f"       {visto}")
    print("RESULTADO:", "todas las listas se distinguen" if todo_bien else "FALLO")
    return 0 if todo_bien else 1


if __name__ == "__main__":
    sys.exit(main())
