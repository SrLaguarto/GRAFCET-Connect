"""Precisión de la espera de un hilo en este Windows (V2-E7, paso 0): cuánto tarda de verdad en volver `Event.wait(0,005)` y `time.sleep(0,005)`.

Mide, con `perf_counter`, el tiempo real de N esperas de 5 ms (y de 1 ms y de 10 ms), sin y con `timeBeginPeriod(1)` (que sube la resolución del
temporizador del sistema de 15,6 ms a 1 ms mientras el proceso no llame a `timeEndPeriod`). También dice qué resolución tiene el temporizador del
sistema ahora (`NtQueryTimerResolution`). Cada medida va en un hilo propio, como el hilo de control de E7, y con el hilo principal parado.

  python tools/medir_espera_hilo.py                  # 300 esperas por caso
  python tools/medir_espera_hilo.py --n 1000 --salida artifacts/v2_e7/medidas/espera_hilo.json
"""
from argparse import ArgumentParser
from pathlib import Path
from statistics import median
import ctypes
import json
import sys
import threading
import time


def resolucion_sistema() -> dict | None:
    """(mínima, máxima, actual) del temporizador del sistema, en ms; None si no es Windows."""
    if sys.platform != "win32":
        return None
    minimo, maximo, actual = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
    ctypes.windll.ntdll.NtQueryTimerResolution(ctypes.byref(minimo), ctypes.byref(maximo), ctypes.byref(actual))
    return {"peor_ms": minimo.value / 1e4, "mejor_ms": maximo.value / 1e4, "actual_ms": actual.value / 1e4}


def en_hilo(funcion):
    salida = []
    h = threading.Thread(target=lambda: salida.append(funcion()))
    h.start()
    h.join()
    return salida[0]


def esperas(metodo: str, plazo_ms: float, n: int) -> list[float]:
    evento = threading.Event()
    if metodo == "Espera (hasta la hora)":  # la de `conexion.ciclo` (temporizador de alta resolución + evento)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from conexion.ciclo import Espera
        e = Espera()
        espera = lambda: e.esperar(time.perf_counter() + plazo_ms / 1000)  # noqa: E731
    elif metodo == "Event.wait":
        espera = lambda: evento.wait(plazo_ms / 1000)  # noqa: E731
    else:
        espera = lambda: time.sleep(plazo_ms / 1000)  # noqa: E731

    def trabajo():
        reales = []
        for _ in range(n):
            t0 = time.perf_counter()
            espera()
            reales.append((time.perf_counter() - t0) * 1000)
        return reales
    return en_hilo(trabajo)


def latencia_de_despertar(n: int) -> dict:
    """Cuánto tarda en volver una espera larga cuando otro hilo llama a `despertar` (lo que hace el trabajador de red al acabar una petición)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from conexion.ciclo import Espera
    e = Espera()
    lat = []
    for _ in range(n):
        marca = []

        def dormir():
            e.esperar(time.perf_counter() + 1)
            marca.append(time.perf_counter())
        h = threading.Thread(target=dormir)
        h.start()
        time.sleep(0.01)
        t0 = time.perf_counter()
        e.despertar()
        h.join()
        lat.append((marca[0] - t0) * 1000)
    e.cerrar()
    return resumen(lat)


def resumen(valores: list[float]) -> dict:
    ordenados = sorted(valores)
    return {"mediana": round(median(valores), 3), "p95": round(ordenados[int(.95 * (len(ordenados) - 1))], 3), "max": round(ordenados[-1], 3),
            "min": round(ordenados[0], 3)}


def main() -> int:
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--plazos", default="1,5,10", help="plazos en ms, separados por comas")
    ap.add_argument("--salida", type=Path)
    args = ap.parse_args()
    plazos = [float(p) for p in args.plazos.split(",")]
    resultado = {"sistema_antes": resolucion_sistema(), "casos": []}
    for periodo in (False, True):
        if periodo:
            if sys.platform != "win32":
                break
            ctypes.windll.winmm.timeBeginPeriod(1)
        try:
            actual = resolucion_sistema()
            for metodo in ("Event.wait", "time.sleep", "Espera (hasta la hora)"):
                for plazo in plazos:
                    fila = {"time_begin_period": periodo, "metodo": metodo, "plazo_ms": plazo, "resolucion_sistema_ms": actual and actual["actual_ms"],
                            **resumen(esperas(metodo, plazo, args.n))}
                    resultado["casos"].append(fila)
        finally:
            if periodo:
                ctypes.windll.winmm.timeEndPeriod(1)
    resultado["despertar_ms"] = latencia_de_despertar(args.n // 3 or 10)
    print(f"Latencia de `Espera.despertar` (del aviso a que vuelve la espera de 1 s): {resultado['despertar_ms']}")
    print(f"Resolución del temporizador del sistema antes de medir: {resultado['sistema_antes']}")
    print("\n| timeBeginPeriod(1) | resolución del sistema (ms) | método | plazo (ms) | mediana | P95 | máx. | mín. |\n| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |")
    for f in resultado["casos"]:
        print(f"| {'sí' if f['time_begin_period'] else 'no'} | {f['resolucion_sistema_ms']} | {f['metodo']} | {f['plazo_ms']:g} | {f['mediana']} | {f['p95']} | {f['max']} | {f['min']} |")
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
