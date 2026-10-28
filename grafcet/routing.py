"""Recorridos de enlaces compartidos por Qt, selección con ratón y banco web. Sin dependencias Qt."""
from typing import Any

SX, H, SIMUL, BARRA_GROSOR = 100, 22, 14, 4
TALLO_E = 16  # tramo vertical mínimo de un enlace al salir de una etapa o al llegar a ella
TALLO_T = 24  # ... y a cada lado de una transición: el trazo nunca llega de lado

def posiciones(M):
    return {n["id"]: (n["x"] + SX, n["y"]) for key in ("steps", "macros", "transitions") for n in M.get(key, [])}

def barra(b):
    return b["x"] + SX, b["y"], b["ancho"], BARRA_GROSOR if b["kind"] == "Y" else 0

def _parcial(pid):
    return "" if pid in (None, "g") else pid

def _izquierda(M: dict[str, Any], pos: dict[str, tuple[float, float]]) -> tuple[dict[str, float], float]:
    """Borde izquierdo de cada parcial (por donde sube un enlace ascendente) y del dibujo."""
    left: dict[str, float] = {}
    for s in M["steps"]:
        k = _parcial(s.get("partial"))
        left[k] = min(left.get(k, pos[s["id"]][0]), pos[s["id"]][0])
    for m in M.get("macros", []):
        left[""] = min(left.get("", pos[m["id"]][0]), pos[m["id"]][0])
    return left, min((p[0] for p in pos.values()), default=SX)


def _carril(lanes: dict[Any, int], left: dict[str, float], min_x: float, t: dict[str, Any], tx: float, px: float) -> float:
    """Por dónde sube un enlace ascendente: por la derecha si su transición está a la derecha de la etapa a la que vuelve
    (la rama vuelve por su lado, como una C), y si no, por la izquierda del parcial. Cada enlace, en su carril."""
    k = _parcial(t.get("partial"))
    lado = "d" if tx > px + 30 else "i"
    n = lanes.get((lado, k), 0)
    lanes[(lado, k)] = n + 1
    return max(tx, px) + 70 + 26 * n if lado == "d" else min(left.get(k, min_x), tx) - 70 - 26 * n


def _bajada(a: tuple[float, float], b: tuple[float, float], tallo_a: float, tallo_b: float, comun: float | None,
            comun_en_a: bool) -> list[tuple[float, float]]:
    """Enlace descendente de `a` (salida inferior) a `b` (entrada superior) con su tramo horizontal a media altura, sin
    comerse el tramo vertical mínimo de cada extremo. `comun` es la línea horizontal que comparten las ramas (del lado de
    `a` o de `b`). Si los dos elementos están tan cerca en altura que no caben los dos tramos, el enlace baja su tramo
    desde `a`, cruza por en medio, sube hasta encima de `b` y entra por arriba (con flecha, porque sube)."""
    lo, hi = a[1] + tallo_a, b[1] - tallo_b
    mid = comun if comun is not None else (a[1] + b[1]) / 2
    if abs(a[0] - b[0]) < 1:
        return [a, (a[0], mid), (b[0], mid), b]
    if lo <= hi:
        mid = min(max(mid, lo), hi)
        return [a, (a[0], mid), (b[0], mid), b]
    y1, y2 = (max(mid, lo), hi) if comun is not None and comun_en_a else (lo, min(mid, hi)) if comun is not None else (lo, hi)
    xm = (a[0] + b[0]) / 2
    return [a, (a[0], y1), (xm, y1), (xm, y2), (b[0], y2), b]


def enlaces(M: dict[str, Any]) -> list[dict[str, Any]]:
    """Cada enlace entre una transición y una etapa, con su recorrido en el dibujo y su rol («pre»: la etapa es anterior)."""
    pos = posiciones(M)
    left, min_x = _izquierda(M, pos)
    out, lanes = [], {}
    # Una misma etapa comparte la línea de selección/convergencia entre todas sus ramas.
    salidas, entradas = {}, {}
    for sid, (px, py) in pos.items():
        salen = [t for t in M["transitions"] if sid in t.get("preDib", t["pre"]) and not t.get("simulPre")]
        llegan = [t for t in M["transitions"] if sid in t.get("postDib", t["post"]) and not t.get("simulPost")]
        if len(salen) > 1:
            limites = [t["y"] - TALLO_T for t in salen if t["y"] > py + H]
            salidas[sid] = max(py + H + TALLO_E, min([py + H + 20] + limites))
        if len(llegan) > 1:
            limites = [t["y"] + TALLO_T for t in llegan if t["y"] < py - H]
            entradas[sid] = min(py - H - TALLO_E, max([py - H - 20] + limites))
    for t in M["transitions"]:
        tx, ty = pos[t["id"]]
        for sid in t.get("preDib", t["pre"]):
            if sid not in pos:
                continue
            px, py = pos[sid]
            if t.get("simulPre"):
                pts = [(px, py + H), (px, ty - SIMUL - 4)]
            elif py > ty:  # la etapa queda debajo: el enlace sube y entra en la transición por arriba, con flecha
                alto = ty - 30
                lx = _carril(lanes, left, min_x, t, tx, px)
                bajo = salidas.get(sid, py + H + TALLO_E)
                pts = [(px, py + H), (px, bajo), (lx, bajo), (lx, alto), (tx, alto), (tx, ty)]
            else:
                pts = _bajada((px, py + H), (tx, ty), TALLO_E, TALLO_T, salidas.get(sid), True)
            out.append({"id": f"{t['id']}|{sid}|pre", "tid": t["id"], "sid": sid, "rol": "pre", "pts": pts,
                        "tallos": (TALLO_E, 0 if t.get("simulPre") else TALLO_T),
                        "arriba": not t.get("simulPre") and any(b[1] < a[1] for a, b in zip(pts, pts[1:]))})
        for sid in t.get("postDib", t["post"]):
            if sid not in pos:
                continue
            px, py = pos[sid]
            if py <= ty:  # enlace ascendente, por la izquierda del parcial
                lx, top = _carril(lanes, left, min_x, t, tx, px), entradas.get(sid, py - H - TALLO_E)
                pts = [(tx, ty), (tx, ty + TALLO_T), (lx, ty + TALLO_T), (lx, top), (px, top), (px, py - H)]
                out.append({"id": f"{t['id']}|{sid}|post", "tid": t["id"], "sid": sid, "rol": "post", "pts": pts,
                            "tallos": (TALLO_T, TALLO_E), "arriba": True})
                continue
            if t.get("simulPost"):
                pts = [(px, ty + SIMUL + 4), (px, py - H)]
            else:
                pts = _bajada((tx, ty), (px, py - H), TALLO_T, TALLO_E, entradas.get(sid), False)
            out.append({"id": f"{t['id']}|{sid}|post", "tid": t["id"], "sid": sid, "rol": "post", "pts": pts,
                        "tallos": (0 if t.get("simulPost") else TALLO_T, TALLO_E),
                        "arriba": not t.get("simulPost") and any(b[1] < a[1] for a, b in zip(pts, pts[1:]))})
    steps = {s["id"] for s in M["steps"]}
    for b in M.get("bars", []):  # conectores de las barras: del elemento de arriba a la barra y de la barra al de abajo
        bx, by, w, h = barra(b)
        for lado, ids in (("arriba", b["arriba"]), ("abajo", b["abajo"])):
            for ident in ids:
                if ident not in pos:
                    continue
                ex, ey = pos[ident]
                cx = min(max(ex, bx), bx + w)
                if lado == "arriba":
                    y0 = ey + (H if ident in steps else 0)
                    mid = (y0 + by) / 2
                    pts = [(ex, y0), (ex, mid), (cx, mid), (cx, by)]
                else:
                    y0 = ey - (H if ident in steps else 0)
                    mid = (by + h + y0) / 2
                    pts = [(cx, by + h), (cx, mid), (ex, mid), (ex, y0)]
                out.append({"id": f"{b['id']}|{ident}|barra", "tid": b["id"], "sid": ident, "rol": "barra", "pts": pts,
                            "tallos": (0, 0), "arriba": False})
    llegadas = {}
    for e in out:
        if e["rol"] == "post":
            llegadas.setdefault(e["sid"], []).append(e["id"])
    for e in out:
        style = M.get("linkStyles", {}).get(e["id"], {})
        pts = e["pts"]
        route = style.get("route", {})
        # Un tramo fijado a mano tampoco se come el tramo vertical mínimo de cada extremo
        bajo, alto = pts[0][1] + e["tallos"][0], pts[-1][1] - e["tallos"][1]
        if "laneX" in route:
            x = float(route["laneX"]) + SX
            y1 = max(float(route.get("exitY", bajo)), bajo)
            y2 = min(float(route.get("entryY", alto)), alto)
            a, b = pts[0], pts[-1]
            pts = [a, (a[0], y1), (x, y1), (x, y2), (b[0], y2), b]
        elif "middleY" in route and len(pts) == 4:
            y = float(route["middleY"])
            y = min(max(y, bajo), alto) if bajo <= alto else y
            pts = [pts[0], (pts[0][0], y), (pts[-1][0], y), pts[-1]]
        e["pts"] = pts
        e["handles"] = [{"segment": i, "pos": (a[0]+0.35*(b[0]-a[0]), a[1]+0.35*(b[1]-a[1])),
                          "axis": "x" if a[0] == b[0] else "y"}
                         for i, (a, b) in enumerate(zip(pts, pts[1:]))
                         if 0 < i < len(pts)-2 and a != b]
        segments = [(i, a, b) for i, (a, b) in enumerate(zip(pts, pts[1:])) if a != b]
        e["arrows"] = []
        if not segments:
            continue
        upward = [(i, a, b) for i, a, b in segments if b[1] < a[1]]
        default = max(upward or segments, key=lambda s: abs(s[2][0]-s[1][0])+abs(s[2][1]-s[1][1]))[0]
        joins = llegadas.get(e["sid"], [])
        has_join = e["rol"] == "post" and len(joins) > 1 and joins[0] == e["id"]
        e["arrowKinds"] = ["flow"] + (["join"] if has_join or "join" in style.get("arrows", {}) else [])
        for key, auto, segment, ratio in (("flow", e["arriba"], default, 0.5),
                                          ("join", has_join, len(pts)-2, 0.5)):
            config = style.get("arrows", {}).get(key, {})
            if not config.get("visible", auto):
                continue
            index = max(0, min(int(config.get("segment", segment)), len(pts)-2))
            if pts[index] == pts[index+1]:
                index = default
            a, b = pts[index:index+2]
            k = max(0.0, min(1.0, float(config.get("ratio", ratio))))
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = (dx*dx+dy*dy)**0.5
            ux, uy = dx/length, dy/length  # la punta sigue el sentido lógico: darle la vuelta es invertir el enlace
            x, y = a[0]+k*dx, a[1]+k*dy
            triangle = [(x+6*ux, y+6*uy), (x-5*ux-5*uy, y-5*uy+5*ux), (x-5*ux+5*uy, y-5*uy-5*ux)]
            e["arrows"].append({"key": key, "pos": (x, y), "segment": index, "ratio": k, "pts": triangle})
    return out


def project_on_link(pts, point):
    """Proyección más cercana sobre el enlace; mantiene la flecha pegada al recorrido."""
    best = None
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length2 = dx*dx+dy*dy
        if not length2:
            continue
        k = max(0.0, min(1.0, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length2))
        distance = (point[0]-a[0]-k*dx)**2+(point[1]-a[1]-k*dy)**2
        if best is None or distance < best[0]:
            best = (distance, i, k)
    return (best[1], best[2]) if best else (0, 0.5)


