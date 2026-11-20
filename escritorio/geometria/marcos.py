"""Extensión de los parciales y trazos de dependencia."""
from typing import Any

from grafcet.routing import NORMAL, TALLO_T, orientacion, punto_t

from .acciones import acciones_etapa, extra, geometria_acciones
from .base import BARRA_GROSOR, H, MARGEN_MARCO_X, MARGEN_MARCO_Y, SIMUL, SX, TB, VACIO_H, VACIO_W
from .base import MedirTexto, Punto, barra, posiciones
from .enlaces import enlaces, simul_d
from .textos import rects_textos_t


def _contenido_parciales(M: dict[str, Any], pos: dict[str, Punto], medir: MedirTexto) -> dict[str, list[float]]:
    """Por parcial, el rectángulo [x0, y0, x1, y1] (en el dibujo, sin márgenes) de todo lo que se dibuja de él: sus
    etapas y
    macroetapas, sus transiciones (el trazo, su designación a la izquierda y su receptividad a la derecha, y los
    trazos de
    una simultaneidad), las acciones y órdenes unidas a sus etapas (con las marcas que sobresalen y los trazos que
    las unen),
    los recorridos de sus enlaces (también los de retorno, por fuera) y las barras que unen elementos suyos. No
    cuenta lo que
    depende del estado de la simulación (el tiempo de un temporizador, las etiquetas «inestable»…) ni los
    comentarios: el marco
    no cambia al simular. Igual que `drawFrames` de tools/dibujo.js."""
    out: dict[str, list[float]] = {}
    de: dict[str, str | None] = {}

    def anotar(pid: str | None, x0: float, y0: float, x1: float, y1: float) -> None:
        if not pid:
            return
        b = out.setdefault(pid, [x0, y0, x1, y1])
        b[:] = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]
    for s in M["steps"]:
        x, y = pos[s["id"]]
        de[s["id"]] = pid = s.get("partial")
        anotar(pid, x - H, y - H, x + H, y + H)
        acciones = acciones_etapa(M, s)
        if acciones and pid:
            cajas, union = geometria_acciones(x, y, acciones, s.get("actionLayout", "fila"), medir=medir)
            for a, ax, cy, w in cajas:
                arriba, abajo = extra(a)
                anotar(pid, ax, cy - H - arriba, ax + w, cy + H + abajo)
            for tramo in union:
                for px, py in tramo:
                    anotar(pid, px, py, px, py)
    for m in M.get("macros", []):
        x, y = pos[m["id"]]
        de[m["id"]] = pid = m.get("partial")
        anotar(pid, x - H, y - H, x + H, y + H)
    for t in M["transitions"]:
        tx, ty = t["x"] + SX, t["y"]
        de[t["id"]] = pid = t.get("partial")
        _anotar_transicion(t, tx, ty, pid, pos, medir, anotar)
    # Un enlace es del parcial de su transición o, si es de barra, del elemento enlazado.
    for e in M["links"] if "links" in M else enlaces(M):
        pid = de.get(e["sid"] if e["rol"] == "barra" else e["tid"])
        for px, py in e["pts"]:
            anotar(pid, px, py, px, py)
    for b in M.get("bars", []):
        bx, by, w, h = barra(b)
        for ident in list(b["arriba"]) + list(b["abajo"]):
            anotar(de.get(ident), bx, by, bx + w, by + h)
    return out


def _anotar_transicion(t, tx, ty, pid, pos, medir, anotar):
    pre = [pos[p] for p in t.get("preDib", t["pre"]) if p in pos]
    post = [pos[p] for p in t.get("postDib", t["post"]) if p in pos]
    if orientacion(t) != "abajo":  # transición girada: su trazo, sus tramos rectos y sus textos
        n = NORMAL[orientacion(t)]
        for u, v in ((0, -TB), (0, TB), (-TALLO_T if not pre else 0, 0), (TALLO_T if not post else 0, 0)):
            anotar(pid, *punto_t(t, tx, ty, u, v), *punto_t(t, tx, ty, u, v))
        for r in rects_textos_t(t, tx, ty, medir):
            if r is not None:
                anotar(pid, r.left(), r.top(), r.right(), r.bottom())
        for signo, otros, hay in ((-1, pre, len(pre) > 1 or t.get("simulPre")), (1, post, t.get("simulPost"))):
            if hay:
                vs = [(p[0] - tx) * n[0] + (p[1] - ty) * n[1] for p in otros] + [0.0]
                for u in (signo * SIMUL, signo * (SIMUL + BARRA_GROSOR)):
                    for v in (min(vs) - 8, max(vs) + 8):
                        anotar(pid, *punto_t(t, tx, ty, u, v), *punto_t(t, tx, ty, u, v))
        return
    anotar(pid, tx - TB, ty - (TALLO_T if not pre else 0), tx + TB, ty + (TALLO_T if not post else 0))
    if t.get("showLabel", True):
        w = medir([{"t": f"({t.get('label', t['id'])})"}], 13)
        anotar(pid, tx - TB - 6 - w, ty - 12, tx - TB - 6, ty + 9)
    if t.get("cond"):
        anotar(pid, tx + TB + 8, ty - 12, tx + TB + 8 + medir(t["cond"], 14), ty + 9)
    if len(pre) > 1 or t.get("simulPre"):  # el doble trazo de una divergencia o convergencia simultánea
        xs = [p[0] for p in pre] + [tx]
        d = simul_d(t, tx, ty, pre, -1)
        anotar(pid, min(xs) - 8, ty - d - BARRA_GROSOR, max(xs) + 8, ty - d)
    if t.get("simulPost"):
        xs = [p[0] for p in post] + [tx]
        d = simul_d(t, tx, ty, post, 1)
        anotar(pid, min(xs) - 8, ty + d, max(xs) + 8, ty + d + BARRA_GROSOR)


def cajas_parciales(M: dict[str, Any], pos: dict[str, tuple[float, float]] | None = None, *,
                    medir: MedirTexto) -> dict[str, dict[str, float]]:
    """El rectángulo (x0, y0, x1, y1, en el dibujo) de cada parcial con contenido: el que rodea todo lo que se
    dibuja de él
    (`_contenido_parciales`: etapas, transiciones con sus textos, acciones y órdenes unidas, barras y los recorridos
    de sus
    enlaces, también los de retorno) con el margen de la norma (MARGEN_MARCO_X, MARGEN_MARCO_Y) y, como mínimo, el
    de siempre
    alrededor de sus etapas y transiciones (por la derecha, más ancho, para sus acciones), más el de sus parciales
    hijos. Es
    el marco que pinta `_marcos` (un recinto o un parcial) y, en una expansión, la zona que ocupa aunque no se
    dibuje (el
    editor la usa para saber en qué parcial cae lo que se suelta). Solo el editor anota un parcial con `vacio` (un
    recinto
    recién creado, sin etapas), con su esquina superior izquierda en `x`, `y` (coordenadas del modelo): se dibuja
    como marco
    vacío de VACIO_W × VACIO_H. Un parcial sin contenido ni `vacio` no tiene caja."""
    pos = pos if pos is not None else posiciones(M)
    parts = M.get("partials") or []
    box: dict[str, dict[str, float] | None] = {}
    dibujado = _contenido_parciales(M, pos, medir)

    def own(pid: str) -> list[tuple[float, float]]:
        return ([pos[s["id"]] for s in M["steps"] if s.get("partial") == pid]
                + [pos[m["id"]] for m in M.get("macros", []) if m.get("partial") == pid]
                + [(t["x"] + SX, t["y"]) for t in M["transitions"] if t.get("partial") == pid])

    def frame(pid: str) -> dict[str, float] | None:
        if pid in box:
            return box[pid]
        pts = own(pid)
        b = ({"x0": min(p[0] for p in pts) - H - 26, "x1": max(p[0] for p in pts) + H + 70,
              "y0": min(p[1] for p in pts) - H - 22, "y1": max(p[1] for p in pts) + H + 22} if pts else None)
        if pid in dibujado:  # todo lo que se dibuja de él queda dentro, con margen
            x0, y0, x1, y1 = dibujado[pid]
            e = {"x0": x0 - MARGEN_MARCO_X, "x1": x1 + MARGEN_MARCO_X,
                 "y0": y0 - MARGEN_MARCO_Y, "y1": y1 + MARGEN_MARCO_Y}
            b = e if b is None else {"x0": min(b["x0"], e["x0"]), "x1": max(b["x1"], e["x1"]),
                                     "y0": min(b["y0"], e["y0"]), "y1": max(b["y1"], e["y1"])}
        if b is None:
            vacio = next((c for c in parts if c["id"] == pid and c.get("vacio")), None)
            if vacio is not None:
                b = {"x0": vacio["x"] + SX, "x1": vacio["x"] + SX + VACIO_W,
                     "y0": vacio["y"], "y1": vacio["y"] + VACIO_H}
        for c in parts:
            if c.get("owner") == pid and c["kind"] == "partial":
                cb = frame(c["id"])
                if not cb:
                    continue
                e = {"x0": cb["x0"] - 12, "x1": cb["x1"] + 12, "y0": cb["y0"] - 12, "y1": cb["y1"] + 16}
                b = e if b is None else {"x0": min(b["x0"], e["x0"]), "x1": max(b["x1"], e["x1"]),
                                         "y0": min(b["y0"], e["y0"]), "y1": max(b["y1"], e["y1"])}
        box[pid] = b
        return b

    return {c["id"]: b for c in parts if (b := frame(c["id"]))}


def parciales_dibujo(M):
    """Pertenencia visual: las barras heredan el parcial de sus extremos, sin cambiar el modelo."""
    partes = {x["id"]: x.get("partial") or "g" for k in ("steps", "transitions", "macros") for x in M.get(k, [])}
    for b in M.get("bars", []):
        extremos = {partes[i] for i in b.get("arriba", []) + b.get("abajo", []) if i in partes}
        partes[b["id"]] = next(iter(extremos)) if len(extremos) == 1 else (None if extremos else "g")
    return partes


def _dependencias_recinto(b: dict[str, float], ox: float, oy: float, inicial: bool = False
                          ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Los dos trazos de dependencia de una encapsulante centrada en (ox, oy) a su recinto de marco `b`, como en la
    figura de la
    norma: cada uno llega a una de las dos esquinas del lado del marco que mira hacia la encapsulante (el lado cuya
    normal
    apunta a su centro, según el eje de mayor diferencia entre los centros; en empate, el vertical): con el recinto
    debajo, a sus
    dos esquinas de arriba; a la derecha, a las dos de la izquierda; y así. Salen de la esquina de la encapsulante
    más cercana a
    cada esquina de destino: en las esquinas cortadas de la etapa, el punto medio de su diagonal (en una inicial, la
    esquina
    del cuadrado exterior). Se eligen al dibujar, según la posición de ahora: si el marco cambia de lado, cambian.
    Igual en
    tools/dibujo.js."""
    dx, dy = ox - (b["x0"] + b["x1"]) / 2, oy - (b["y0"] + b["y1"]) / 2
    if abs(dy) >= abs(dx):
        y = b["y0"] if dy <= 0 else b["y1"]
        destinos = [(b["x0"], y), (b["x1"], y)]
    else:
        x = b["x0"] if dx < 0 else b["x1"]
        destinos = [(x, b["y0"]), (x, b["y1"])]
    c = H if inicial else H - round(0.22 * 2 * H) / 2
    esquinas = [(ox + sx * c, oy + sy * c) for sy in (-1, 1) for sx in (-1, 1)]
    return [(min(esquinas, key=lambda e: (e[0] - d[0]) ** 2 + (e[1] - d[1]) ** 2), d) for d in destinos]


def _dependencia_cajas(a: tuple[float, float], b: tuple[float, float], superior: bool = True,
                        lado: float | None = None) -> tuple[tuple[float, float], tuple[float, float]]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    lado = dx if lado is None else lado
    if lado == 0:
        k = min(.5, H / max(abs(dx), abs(dy))) if dx or dy else 0
        return (a[0] + dx * k, a[1] + dy * k), (b[0] - dx * k, b[1] - dy * k)
    hx, hy = (H if lado > 0 else -H), (-H if superior else H)
    return (a[0] + hx, a[1] + hy), (b[0] - hx, b[1] + hy)
