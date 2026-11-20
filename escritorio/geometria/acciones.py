"""Distribución de las cajas de acción y sus trazos, con anchos inyectados."""
from typing import Any, Callable

from .base import ACT_BUS, ACT_CANAL, ACT_COL, ACT_GAP, ACT_LINK, ACT_MIN, H, RADIO_ANCLA, SX, TMR_EXTRA
from .base import MedirTexto, Punto, posiciones

CLAVE = "actionOrder"
IMAN_ACCION = 16
BORDE_ACCION = RADIO_ANCLA

CajaAccion = tuple[dict[str, Any], float, float, float]


def ordenar(elementos: list[dict[str, Any]], orden: list[str]) -> list[dict[str, Any]]:
    por_id = {a["id"]: a for a in elementos}
    ids = dict.fromkeys(i for i in orden if isinstance(i, str) and i in por_id)
    for a in elementos:
        ids.setdefault(a["id"], None)
    return [por_id[i] for i in ids]


def acciones_etapa(vista: dict[str, Any], etapa: dict[str, Any]) -> list[dict[str, Any]]:
    elementos = etapa["actions"] + [d for d in vista.get("draftActions", []) if d.get("etapa") == etapa["id"]]
    orden = vista.get(CLAVE, {}).get(etapa["id"], [])
    return ordenar(elementos, orden) if orden else elementos


def grupos_sueltos(M: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grupos: dict[str, list[dict[str, Any]]] = {}
    for d in M.get("draftActions", []):
        if not d.get("etapa"):
            grupos.setdefault(d.get("grupo") or d["id"], []).append(d)
    return grupos


def extra(a: dict[str, Any]) -> tuple[int, int]:
    """Lo que sobresale la marca de una acción por encima y por debajo de su caja (condición, flecha, banderita), y el
    tiempo transcurrido de su temporizador, que va encima de la condición o del evento (`tmr`)."""
    if a["kind"] == "continuous" and a.get("cond"):
        return 20 + (TMR_EXTRA if a.get("tmr") else 0), 0
    arriba, abajo = {"event": (24, 0), "activation": (20, 0), "deactivation": (0, 20)}.get(a.get("trigger"), (0, 0))
    return arriba + (TMR_EXTRA if a.get("tmr") and a.get("trigger") == "event" else 0), abajo


def ancho_accion(a: dict[str, Any], medir: MedirTexto) -> float:
    """Ancho de la caja de una acción: el de su texto y, si lleva condición o evento encima, el que éstos necesitan para
    no invadir a la caja vecina (el estado de un temporizador, que cambia al simular, no cuenta)."""
    w = max(ACT_MIN, medir(a["text"], 15) + 24)
    marca = a.get("cond") if a["kind"] == "continuous" else a.get("event") if a.get("trigger") == "event" else None
    return max(w, 12 + 5 + medir(marca, 13) + 8) if marca else w


def geometria_acciones(x: float, y: float, actions: list[dict[str, Any]], disposicion: str,
                        suelto: bool = False, *, medir: MedirTexto) -> tuple[list[CajaAccion], list[list[Punto]]]:
    """Dónde va cada acción ({acción, x, y del centro, ancho}) y los trazos que las unen entre sí y con la etapa
    (polilíneas). Cuatro colocaciones (figuras (1)–(3) de la norma): «fila» (por defecto; cajas contiguas, la
    representación (2)), «fila-separada» (cajas separadas, unidas a una línea común que sale de la etapa), «matriz-2»
    (cuadrícula de dos columnas, de izquierda a derecha y de arriba abajo; una barra vertical común a su izquierda con
    una derivación a cada fila: la de la segunda columna pasa por debajo de la caja de la primera y sube a la suya) y
    «columna» (una debajo de otra, unidas por una línea vertical que sale de la etapa). Una etapa está en (x, y) y
    las acciones
    salen de su lado derecho; un grupo suelto empieza en (x, y), el punto medio de su lado izquierdo."""
    ax = x if suelto else x + H + ACT_LINK
    union: list[list[tuple[float, float]]] = [] if suelto else [[(x + H, y), (ax, y)]]
    if not actions:
        return [], union
    bx = ax - ACT_LINK / 2
    if disposicion == "columna":
        ancho, ys = max(ancho_accion(a, medir) for a in actions), [y]
        for previa, a in zip(actions, actions[1:]):  # el hueco deja sitio a las marcas de las dos cajas vecinas
            ys.append(ys[-1] + 2 * H + max(ACT_COL, extra(previa)[1] + extra(a)[0] + 4))
        if len(ys) > 1:
            union.append([(bx, y), (bx, ys[-1])])
            union += [[(bx, cy), (ax, cy)] for cy in (ys if suelto else ys[1:])]
        return [(a, ax, cy, max(ancho, ancho_accion(a, medir))) for a, cy in zip(actions, ys)], union
    if disposicion == "matriz-2":
        return _matriz_acciones(ax, y, bx, actions, suelto, medir, union)
    if disposicion == "fila-separada":
        cajas, entradas = [], []
        for i, a in enumerate(actions):
            if i:
                ax += ACT_GAP
                entradas.append(ax - 14)
            w = ancho_accion(a, medir)
            cajas.append((a, ax, y, w))
            ax += w
        if entradas:
            yb = y + H + ACT_BUS
            union.append([(bx, y), (bx, yb), (entradas[-1], yb)])
            if suelto:
                union.append([(bx, y), (cajas[0][1], y)])
            union += [[(ex, yb), (ex, y), (ex + 14, y)] for ex in entradas]
        return cajas, union
    cajas = []
    for a in actions:
        w = ancho_accion(a, medir)
        cajas.append((a, ax, y, w))
        ax += w
    return cajas, union


def _matriz_acciones(ax, y, bx, actions, suelto, medir, union):
    filas = [actions[i:i + 2] for i in range(0, len(actions), 2)]
    w1 = max(ancho_accion(f[0], medir) for f in filas)
    w2 = max((ancho_accion(f[1], medir) for f in filas if len(f) > 1), default=0)
    x2, ys, canales = ax + w1 + ACT_GAP, [y], []
    for n, f in enumerate(filas):
        if n:  # el hueco deja sitio a las marcas y al canal de la derivación de la fila de arriba
            ys.append(ys[-1] + 2 * H + max(ACT_COL, max(extra(a)[1] for a in filas[n - 1])
                                           + max(extra(a)[0] for a in f) + 2 * ACT_CANAL))
        canales.append(ys[-1] + H + max(extra(a)[1] for a in f) + ACT_CANAL)
    cajas = [(a, ax if i % 2 == 0 else x2, ys[i // 2], w1 if i % 2 == 0 else w2) for i, a in enumerate(actions)]
    if len(actions) > 1:
        fin = canales[-1] if len(filas[-1]) > 1 else ys[-1]
        union.append([(bx, y), (bx, fin)])
        union += [[(bx, cy), (ax, cy)] for cy in (ys if suelto else ys[1:])]
        union += [[(bx, canales[n]), (x2 - 14, canales[n]), (x2 - 14, ys[n]), (x2, ys[n])]
                  for n, f in enumerate(filas) if len(f) > 1]
    return cajas, union


def colocadas(M: dict[str, Any], medir: MedirTexto) -> list[dict[str, Any]]:
    """Dónde quedan las acciones de cada etapa y de cada grupo suelto según el modelo y su colocación, sin esperar a
    que se dibujen: {id, etapa, grupo, rect, extra: lo que sobresalen sus marcas por arriba y por abajo}."""
    pos, out = posiciones(M), []

    def anotar(acciones: list[dict[str, Any]], x: float, y: float, disposicion: str, suelto: bool, etapa: str,
               grupo: str) -> None:
        for a, ax, cy, w in geometria_acciones(x, y, acciones, disposicion, suelto, medir=medir)[0]:
            out.append({"id": a.get("id", ""), "etapa": etapa, "grupo": grupo, "rect": (ax, cy - H, w, 2 * H),
                        "extra": extra(a), "evento": a.get("trigger") == "event"})
    for s in M["steps"]:
        acciones = acciones_etapa(M, s)
        if acciones:
            anotar(acciones, *pos[s["id"]], s.get("actionLayout", "fila"), False, s["id"], "")
    for g, miembros in grupos_sueltos(M).items():
        anotar(miembros, miembros[0]["x"] + SX, miembros[0]["y"], (M.get("actionLayouts") or {}).get(g, "fila"),
               True, "", g)
    return out


def situacion(M: dict[str, Any], clave: str) -> tuple[float, float, list[dict[str, Any]], bool] | None:
    """Dónde empiezan (x, y en el dibujo) y cuáles son las acciones de la etapa o del grupo suelto `clave`, y si es un
    grupo suelto; None si no tiene ninguna (con el modelo ya rehecho: `reconstruir`)."""
    unidas = M.get("draftActions", [])
    if any(s["id"] == clave for s in M["steps"]):
        paso = next(s for s in M["steps"] if s["id"] == clave)
        acciones = acciones_etapa(M, paso)
        return (*posiciones(M)[clave], acciones, False) if acciones else None
    acciones = [d for d in unidas if not d.get("etapa") and (d.get("grupo") or d["id"]) == clave]
    return (acciones[0]["x"] + SX, acciones[0]["y"], acciones, True) if acciones else None


def firmas(cajas: list[dict[str, Any]]) -> dict[str, tuple[Any, ...]]:
    """Por cada etapa y grupo suelto con acciones, dónde y de qué tamaño quedan sus cajas (con el modelo ya rehecho);
    cambia si se añade, se quita, se ensancha o se coloca de otro modo alguna de sus acciones."""
    out: dict[str, list[Any]] = {}
    for c in cajas:
        out.setdefault(c["etapa"] or c["grupo"], []).append((c["id"], *(round(v, 1) for v in c["rect"]), *c["extra"]))
    return {k: tuple(v) for k, v in out.items()}


def buscar_iman(cajas, ids: list[str], x: float, y: float,
                colocacion: Callable[[dict[str, Any]], str]) -> dict[str, Any] | None:
    """Si una acción suelta (la primera de `ids`, con su lado izquierdo en el punto del modelo (x, y)) toca el lado
    derecho de otra acción, o el inferior si va en columna, a menos de IMAN_ACCION: la acción a cuya espalda se pegaría
    ({objetivo, lado, linea: el lado que se resalta}). Las acciones de `ids` no cuentan."""
    izq, arriba = x + SX, y - H
    mejor: tuple[float, dict[str, Any]] | None = None
    for c in cajas:
        if c["id"] in ids:
            continue
        tx, ty, tw, th = c["rect"]
        candidatos = []
        dx, dy = abs(izq - (tx + tw)), abs(y - (ty + th / 2))
        if dx <= IMAN_ACCION and dy <= H:  # al lado derecho
            candidatos.append((dx + dy, "der", ((tx + tw, ty), (tx + tw, ty + th))))
        hueco = arriba - (ty + th)
        if colocacion(c) == "columna" and -IMAN_ACCION <= hueco <= IMAN_ACCION + 12 and abs(izq - tx) <= tw / 2:
            candidatos.append((abs(hueco) + abs(izq - tx), "abajo", ((tx, ty + th), (tx + tw, ty + th))))
        for puntos, lado, linea in candidatos:
            if mejor is None or puntos < mejor[0]:
                mejor = (puntos, {"objetivo": c["id"], "lado": lado, "linea": linea})
    return mejor[1] if mejor else None


def iman_en_punto(cajas, punto, radio, excluir=()):
    """El punto de unión derecho más próximo, fuera de las cajas que se arrastran."""
    candidatos = []
    for caja in cajas:
        if caja["id"] in excluir or caja.get("forzado"):
            continue
        x, y, ancho, alto = caja["rect"]
        derecha = x + ancho
        distancia = abs(punto[0] - derecha) + abs(punto[1] - (y + alto / 2))
        if distancia <= radio:
            candidatos.append((distancia, caja["id"], derecha, y, alto))
    if not candidatos:
        return None
    _, ident, derecha, y, alto = min(candidatos)
    return {"objetivo": ident, "linea": ((derecha, y), (derecha, y + alto))}


def borde_accion(caja: dict[str, Any], p: tuple[float, float], colocacion_de) -> str | None:
    """«der» o «abajo» si el punto está en el borde de la caja de una acción de una etapa del que se tira para sacar
    otra
    acción; None si no. Se agarra a los dos lados del borde, a BORDE_ACCION del dibujo (lo mismo que un punto de
    unión, y
    a cualquier zoom), sin pasar de un tercio del lado de la caja por dentro, para que el cuerpo siga agarrándose para
    seleccionar y mover. Depende de la colocación de las acciones de la etapa, que nunca cambia por esto: en «fila»
    y «fila
    separada», solo el borde derecho; en «columna», solo el inferior (la nueva va debajo); en «matriz 2», ninguno."""
    if not caja.get("etapa") or caja.get("forzado") or caja.get("suelta"):
        return None
    x, y, w, h = caja["rect"]
    colocacion = colocacion_de(caja["etapa"])
    if colocacion in ("fila", "fila-separada"):
        dentro = min(BORDE_ACCION, w / 3)
        return "der" if y <= p[1] <= y + h and x + w - dentro <= p[0] <= x + w + BORDE_ACCION else None
    if colocacion == "columna":
        dentro = min(BORDE_ACCION, h / 3)
        return "abajo" if x <= p[0] <= x + w and y + h - dentro <= p[1] <= y + h + BORDE_ACCION else None
    return None  # matriz de 2: la acción nueva no tiene un sitio evidente, se añade desde la etapa
