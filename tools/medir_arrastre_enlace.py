"""Mide por fases el arrastre que crea una acción o una transición desde un punto de unión (V2-E9).

Desde el punto de la derecha de una etapa se arrastra a un hueco y se suelta: crea una acción. Desde el punto de salida de una
etapa o de una transición, a un hueco: abre una rama (crea una transición o una etapa). Por gesto se anota cuánto tardan, con la escena ya
pintada (se bombean los eventos de Qt tras cada paso, como hace el banco de E0):

  pulsar      `prensar` (+ pintado)
  movimiento  cada `mover` (+ pintado): mediana, P95 y máximo de los fotogramas intermedios
  soltar      `soltar` (+ pintado)

  python tools/medir_arrastre_enlace.py                         # Linea larga, 15 repeticiones
  python tools/medir_arrastre_enlace.py --proyecto gemma --eventos
"""
from argparse import ArgumentParser
from cProfile import Profile
from pathlib import Path
from pstats import Stats
from statistics import median
from time import perf_counter_ns
import json
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.entorno_v2_e0 import GEMMA, ventana  # noqa: E402
from tools.hoja_contactos import _bombear as bombear  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from escritorio.diagrama import SX, anclas, elemento_en, posiciones  # noqa: E402

LINEA = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "referencia" / "linea_larga.grafnet"
FOTOGRAMAS = 8


def ms(f, *args):
    t = perf_counter_ns()
    r = f(*args)
    bombear()
    return (perf_counter_ns() - t) / 1e6, r


def transicion_libre(e):
    """Una transición sin etapa siguiente, a la derecha de todo lo dibujado (en Linea larga todas tienen): de ella se arrastra para crear una etapa."""
    pos = posiciones(e.M)
    x = max(p[0] for p in pos.values()) - SX + 260
    y = min(p[1] for p in pos.values()) + 60
    ident, _ = e.ed.add_transition(e.ed.model["partials"][0]["id"], "", [], [], at=(round(x / 10) * 10, round(y / 10) * 10), label=e.ed.next_label("transition"))
    e.cambia()
    return ident


def candidatos(e, tipo):
    """(origen, destino) de gestos posibles. `accion`: del punto derecho de una etapa (crea una acción). `desde_etapa`: del punto de salida de
    una etapa a un hueco (abre una rama: crea una transición). `desde_transicion`: del punto de salida de una transición sin etapa siguiente
    a un hueco (crea una etapa); esa transición se crea antes de cada gesto."""
    pos = posiciones(e.M)
    if tipo == "desde_transicion":
        ident = transicion_libre(e)
        pos = posiciones(e.M)
        ids = [ident]
    else:
        ids = [s["id"] for s in e.M["steps"]]
    lado = "der" if tipo == "accion" else "abajo"
    desplazamientos = (QPointF(90, 0),) if tipo == "accion" else (QPointF(150, 100), QPointF(-150, 100), QPointF(200, 60), QPointF(-200, 60))
    for ident in ids:
        for a in anclas(e.M, ident, pos):
            if a["lado"] != lado:
                continue
            for d in desplazamientos:
                destino = a["pos"] + d
                if elemento_en(e.M, destino) is None and e.accion_en(destino) is None and e.orden_en(destino) is None:
                    yield a["pos"], destino
                    break


def punto_vista(w, p):
    return w.diagrama.mapFromScene(p)


def gesto(w, tipo, repeticiones, eventos, perfil=None):
    """Por gesto: tiempo de pulsar, de cada fotograma de movimiento y de soltar. Con `eventos`, por los eventos reales de ratón sobre la vista
    (QTest); si no, llamando al controlador (`prensar`, `mover`, `soltar`)."""
    e = w.edicion
    fases = {"pulsar": [], "movimiento": [], "soltar": []}
    hechas = 0
    vp = w.diagrama.viewport()
    for _ in range(repeticiones * 3):
        if hechas >= repeticiones:
            break
        base = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.draft_actions()))
        candidato = next(candidatos(e, tipo), None)
        if candidato is None:
            break
        origen, destino = candidato
        w.diagrama.centrar_en(origen)
        e.seleccionar([])
        bombear()
        antes = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.draft_actions()))
        if perfil:
            perfil.enable()
        if eventos:
            t, _ = ms(QTest.mousePress, vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punto_vista(w, origen))
        else:
            t, _ = ms(e.prensar, origen)
        fotogramas = []
        if e.enlace:
            for k in range(1, FOTOGRAMAS + 1):
                p = origen + (destino - origen) * (k / FOTOGRAMAS)
                if eventos:
                    fotogramas.append(ms(QTest.mouseMove, vp, punto_vista(w, p))[0])
                else:
                    fotogramas.append(ms(e.mover, p)[0])
        if eventos:
            s, _ = ms(QTest.mouseRelease, vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punto_vista(w, destino))
        else:
            s, _ = ms(e.soltar, destino)
        if perfil:
            perfil.disable()
        despues = (len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.draft_actions()))
        creado = despues != antes
        if tipo == "desde_transicion":  # `antes` ya cuenta la transición libre: tiene que haber nacido una etapa
            creado = despues[0] == antes[0] + 1
        if creado and fotogramas:
            fases["pulsar"].append(t)
            fases["movimiento"].extend(fotogramas)
            fases["soltar"].append(s)
            hechas += 1
        for _ in range(4):  # hasta dejar el proyecto como estaba
            if (len(e.ed.model["steps"]), len(e.ed.model["transitions"]), len(e.ed.draft_actions())) == base:
                break
            e.deshacer()
        bombear()
    mov = sorted(fases["movimiento"])
    return {"pulsar": round(median(fases["pulsar"]), 1) if hechas else None,
            "movimiento_mediana": round(median(mov), 2) if mov else None,
            "movimiento_p95": round(mov[int(len(mov) * 0.95)], 2) if mov else None,
            "movimiento_max": round(mov[-1], 2) if mov else None,
            "soltar": round(median(fases["soltar"]), 1) if hechas else None, "gestos": hechas}


def main():
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--proyecto", choices=("gemma", "linea"), default="linea")
    ap.add_argument("--ruta", type=Path, help="otro .grafnet (por ejemplo, el del examen, que se lee de donde está)")
    ap.add_argument("--carga", action="store_true", help="con un proceso de cálculo por núcleo en otros procesos (como `con_carga` de medir_ciclo_es.py)")
    ap.add_argument("--conectado", action="store_true", help="con la conexión Modbus abierta a un servidor de prueba (el proyecto tiene que traer su mapa)")
    ap.add_argument("--repeticiones", type=int, default=15)
    ap.add_argument("--eventos", action="store_true", help="por eventos de ratón reales sobre la vista (QTest) en vez de llamar al controlador")
    ap.add_argument("--perfil", action="store_true", help="perfil del gesto entero (cProfile)")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    ruta = a.ruta or (GEMMA if a.proyecto == "gemma" else LINEA)
    resultado = {}
    cargas = []
    with ventana() as w:
        if not w.abrir_ruta(ruta):
            raise SystemExit(f"no se pudo abrir {ruta}")
        bombear()
        servidor = None
        if a.conectado:
            from tools.medir_ciclo_es import Servidor
            servidor = Servidor().__enter__()
            config = w.panel_es.obtener()
            config.host, config.puerto, config.periodo_ms, config.modo = "127.0.0.1", servidor.puerto, 10, "modbus"
            w.panel_es.cargar(w.edicion.ed.model, config)
            w._conectar_modbus()
            fin = perf_counter_ns() + 10_000_000_000
            while not (w.modbus.estado == "conectado" and w.modbus.futuro is None):
                bombear()
                if perf_counter_ns() > fin:
                    raise SystemExit("no conectó: " + w.modbus.mensaje)
        if a.carga:
            import atexit
            import os
            import subprocess
            import time
            for _ in range(max(2, os.cpu_count() or 2)):
                cargas.append(subprocess.Popen([sys.executable, "-c", "while True: pass"]))
            atexit.register(lambda: [c.kill() for c in cargas])  # (si algo falla, que no queden procesos girando)
            time.sleep(0.3)
        for tipo in ("accion", "desde_etapa", "desde_transicion"):
            gesto(w, tipo, 2, a.eventos)  # calentamiento
            resultado[tipo] = gesto(w, tipo, a.repeticiones, a.eventos)
            print(tipo, json.dumps(resultado[tipo]), flush=True)
        if a.perfil:
            perfil = Profile()
            gesto(w, "accion", 4, a.eventos, perfil)
            Stats(perfil).sort_stats("cumulative").print_stats(35)
    for c in cargas:
        c.kill()
    if servidor is not None:
        servidor.__exit__()
    if a.salida:
        a.salida.write_text(json.dumps({a.proyecto: resultado}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
