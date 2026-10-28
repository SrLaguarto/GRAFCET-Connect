"""Recorridos de enlaces compartidos por Qt, selección con ratón y banco web. Sin dependencias Qt."""
from typing import Any

SX, H, SIMUL, BARRA_GROSOR = 100, 22, 14, 4

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
            limites = [t["y"] for t in salen if t["y"] > py + H]
            salidas[sid] = min(py + H + 20, (py + H + min(limites)) / 2) if limites else py + H + 20
        if len(llegan) > 1:
            limites = [t["y"] for t in llegan if t["y"] < py - H]
            entradas[sid] = max(py - H - 20, (py - H + max(limites)) / 2) if limites else py - H - 20
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
                bajo = salidas.get(sid, py + H + 16)
                pts = [(px, py + H), (px, bajo), (lx, bajo), (lx, alto), (tx, alto), (tx, ty)]
            else:
                mid = salidas.get(sid, (py + H + ty) / 2)
                pts = [(px, py + H), (px, mid), (tx, mid), (tx, ty)]
            out.append({"id": f"{t['id']}|{sid}|pre", "tid": t["id"], "sid": sid, "rol": "pre", "pts": pts,
                        "arriba": py > ty and not t.get("simulPre")})
        for sid in t.get("postDib", t["post"]):
            if sid not in pos:
                continue
            px, py = pos[sid]
            if py <= ty:  # enlace ascendente, por la izquierda del parcial
                lx, top = _carril(lanes, left, min_x, t, tx, px), entradas.get(sid, py - H - 16)
                pts = [(tx, ty), (tx, ty + 14), (lx, ty + 14), (lx, top), (px, top), (px, py - H)]
                out.append({"id": f"{t['id']}|{sid}|post", "tid": t["id"], "sid": sid, "rol": "post", "pts": pts,
                            "arriba": True})
                continue
            if t.get("simulPost"):
                pts = [(px, ty + SIMUL + 4), (px, py - H)]
            else:
                mid = entradas.get(sid, (ty + py - H) / 2)
                pts = [(tx, ty), (tx, mid), (px, mid), (px, py - H)]
            out.append({"id": f"{t['id']}|{sid}|post", "tid": t["id"], "sid": sid, "rol": "post", "pts": pts,
                        "arriba": False})
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
                            "arriba": False})
    llegadas = {}
    for e in out:
        if e["rol"] == "post":
            llegadas.setdefault(e["sid"], []).append(e["id"])
    for e in out:
        style = M.get("linkStyles", {}).get(e["id"], {})
        pts = e["pts"]
        route = style.get("route", {})
        if "laneX" in route:
            x = float(route["laneX"]) + SX
            y1 = float(route.get("exitY", pts[0][1] + 16))
            y2 = float(route.get("entryY", pts[-1][1] - 16))
            a, b = pts[0], pts[-1]
            pts = [a, (a[0], y1), (x, y1), (x, y2), (b[0], y2), b]
        elif "middleY" in route and len(pts) == 4:
            y = float(route["middleY"])
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
            sign = -1 if config.get("reverse", False) else 1
            ux, uy = sign*dx/length, sign*dy/length
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


