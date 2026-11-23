"""Mide por fases el tiempo de abrir un proyecto en la ventana (V2-E9): leer el archivo, abrir el modelo (validar), construir (`_cargar`: la vista, la
edición y la escena) y el primer dibujo (los eventos de Qt que quedan por atender). La meta del plan es < 2 s.

  python tools/medir_apertura.py "artifacts/escena_examen/Examen grande (escalonado).grafnet"
  python tools/medir_apertura.py RUTA --repeticiones 5 --perfil     # y el perfil de la construcción
"""
from argparse import ArgumentParser
from cProfile import Profile
from pathlib import Path
from pstats import Stats
from statistics import median
from time import perf_counter_ns
from unittest import mock
import json
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.entorno_v2_e0 import ventana  # noqa: E402
from tools.hoja_contactos import _bombear as bombear  # noqa: E402
from escritorio.ventana import archivos as modulo_archivos  # noqa: E402


def cronometrar(destino, nombre, acumulado):
    original = getattr(destino, nombre)

    def envuelta(*a, **k):
        t = perf_counter_ns()
        try:
            return original(*a, **k)
        finally:
            acumulado[nombre] = acumulado.get(nombre, 0) + (perf_counter_ns() - t) / 1e6
    return envuelta


def main():
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ruta", type=Path)
    ap.add_argument("--repeticiones", type=int, default=4)
    ap.add_argument("--perfil", action="store_true")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    filas = []
    with ventana() as w:
        clase = type(w)
        for k in range(a.repeticiones + 1):
            acum: dict[str, float] = {}
            parches = [mock.patch.object(clase, "_leer_grafnet_gui", cronometrar(clase, "_leer_grafnet_gui", acum)),
                       mock.patch.object(clase, "_cargar", cronometrar(clase, "_cargar", acum)),
                       mock.patch.object(modulo_archivos, "open_model", cronometrar(modulo_archivos, "open_model", acum))]
            perfil = Profile() if a.perfil and k == 1 else None
            for p in parches:
                p.start()
            try:
                t = perf_counter_ns()
                if perfil:
                    perfil.enable()
                assert w.abrir_ruta(a.ruta), "no se pudo abrir"
                if perfil:
                    perfil.disable()
                total_sin_pintar = (perf_counter_ns() - t) / 1e6
                t = perf_counter_ns()
                bombear()
                pintar = (perf_counter_ns() - t) / 1e6
            finally:
                for p in parches:
                    p.stop()
            fila = {"leer": acum["_leer_grafnet_gui"], "abrir_modelo": acum["open_model"], "construir": acum["_cargar"],
                    "resto_de_abrir_ruta": total_sin_pintar - sum(acum.values()), "primer_dibujo": pintar, "total": total_sin_pintar + pintar}
            filas.append({x: round(v, 1) for x, v in fila.items()})
            print(("primera (en frío)" if k == 0 else f"repetición {k}"), json.dumps(filas[-1]), flush=True)
            if perfil:
                Stats(perfil).sort_stats("cumulative").print_stats(28)
    resumen = {x: round(median(f[x] for f in filas[1:]), 1) for x in filas[0]}
    print("mediana de las repeticiones", json.dumps(resumen))
    if a.salida:
        a.salida.write_text(json.dumps({"primera": filas[0], "mediana": resumen, "todas": filas}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
