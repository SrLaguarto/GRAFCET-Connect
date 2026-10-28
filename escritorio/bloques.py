"""Programador por bloques de receptividades y condiciones (P-IMP-38).

La expresión se arma con bloques de colores que se arrastran desde una paleta (Entradas, Salidas, Memorias, Etapas,
Operadores, Comparaciones, Tiempo) y encajan unos dentro de otros. Las condiciones son bloques hexagonales: una
variable booleana o una etapa (con un desplegable para elegir cuál), «y» y «o» con dos huecos, «no» y los flancos ↑ ↓
que envuelven a otro bloque, las constantes 1 y 0, «temporizar» (t1 y t2 como en la norma: 3s/X1, X1/2s) y la
comparación de una variable numérica con un valor.

Los bloques solo escriben el texto en la notación del usuario (↑a, X1, 3s/X1, NOT, AND, OR, 1/0), que es lo que se
guarda y lo que el núcleo analiza como siempre (grafcet/notation.py y grafcet/expressions.py no cambian). La primera
parte de este fichero es el modelo, sin dibujo: un árbol de nodos (diccionarios) que se convierte de texto y a texto, y
las operaciones de soltar, envolver, sustituir y quitar. La segunda, el dibujo y la interacción en Qt.
"""
from __future__ import annotations

import copy
import json
import re
from collections import Counter
from typing import Any, Callable

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QCursor, QDrag, QFont, QFontMetricsF, QKeySequence, QPainter, QPen, QPixmap,
                           QPolygonF, QShortcut)
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QMenu, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget, QWidgetItem)

from grafcet.expressions import CMP, FUNCS_EXPR, FUNCS_REF, KEYWORDS, ParseError, parse, render
from grafcet.notation import a_nucleo, a_usuario, normalizar_espacios, x_etapa

# -- modelo: el árbol de bloques --------------------------------------------------------------------------
# Un nodo es un diccionario con su clase en "k"; un hueco es None:
#   var(n, papel)  etapa(n)  const(v)  y(a, b)  o(a, b)  no(a)  sube(a)  baja(a)  temp(t1, t2, a)
#   cmp(n, op, v)  texto(s)  (lo que no se representa con bloques: aritmética, nombres que no existen)
HIJOS = {"y": ("a", "b"), "o": ("a", "b"), "no": ("a",), "sube": ("a",), "baja": ("a",), "temp": ("a",)}
ENVUELVEN = frozenset(HIJOS)  # soltados sobre un hueco ocupado, el bloque que había entra en su primer hueco
HUECO = "__hueco__"  # nombre reservado con que se lee un «?» (hueco) del texto
OPERADORES_CMP = ("=", "!=", "<", "<=", ">", ">=")
OP_VISIBLE = {"=": "=", "!=": "≠", "<": "<", "<=": "≤", ">": ">", ">=": "≥"}
PAPEL = {"entrada": "input", "salida": "output", "interna": "internal"}  # categoría de la paleta -> papel
_SIMPLE = re.compile(r"[^\W\d]\w*(?:\.[^\W\d]\w*)*")
_RESERVADAS = KEYWORDS | set(FUNCS_REF) | set(FUNCS_EXPR) | {"delay"}
_DURACION = re.compile(r"(\d+(?:[.,]\d+)?)\s*(us|µs|μs|ms|s)")
_TOP_PREC = {"or": 1, "and": 2, "not": 3, **{c: 4 for c in CMP.values()}}


def nuevo(k: str, **campos: Any) -> dict[str, Any]:
    """Un bloque nuevo de la clase `k`, con sus huecos vacíos."""
    base: dict[str, Any] = {
        "var": {"n": None, "papel": "input"}, "etapa": {"n": None}, "const": {"v": 1}, "y": {"a": None, "b": None},
        "o": {"a": None, "b": None}, "no": {"a": None}, "sube": {"a": None}, "baja": {"a": None},
        "temp": {"t1": "3s", "t2": "", "a": None}, "cmp": {"n": None, "op": "=", "v": "0"}, "texto": {"s": ""}}[k]
    return {"k": k, **copy.deepcopy(base), **campos}


def var(nombre: str | None, papel: str = "input") -> dict[str, Any]:
    return nuevo("var", n=nombre, papel=papel)


def hijos(n: dict[str, Any] | None) -> tuple[str, ...]:
    return HIJOS.get(n["k"], ()) if n else ()


def obtener(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> dict[str, Any] | None:
    """El nodo (o el hueco) que hay en `ruta`, una tupla de claves de hijo ("a", "b") desde la raíz."""
    n = raiz
    for c in ruta:
        if n is None or c not in hijos(n):
            raise KeyError(ruta)
        n = n[c]
    return n


def con_nodo(raiz: dict[str, Any] | None, ruta: tuple[str, ...], nodo: dict[str, Any] | None) -> dict[str, Any] | None:
    """Copia del árbol con `nodo` en `ruta` (la raíz, si la ruta es vacía)."""
    nodo = copy.deepcopy(nodo)
    if not ruta:
        return nodo
    r = copy.deepcopy(raiz)
    obtener(r, ruta[:-1])[ruta[-1]] = nodo
    return r


def primer_hueco(n: dict[str, Any] | None, ruta: tuple[str, ...] = ()) -> tuple[str, ...] | None:
    """Ruta del primer hueco vacío del nodo, en orden (primero «a», luego «b», y dentro de cada uno, sus huecos)."""
    for c in hijos(n):
        if n[c] is None:
            return ruta + (c,)
        h = primer_hueco(n[c], ruta + (c,))
        if h is not None:
            return h
    return None


def soltar(raiz: dict[str, Any] | None, ruta: tuple[str, ...], nodo: dict[str, Any]) -> dict[str, Any] | None:
    """Suelta un bloque en un hueco o sobre un bloque. Un hueco vacío lo recibe. Sobre uno ocupado: si el bloque
    envuelve (no, ↑, ↓, temporizar, y, o) y tiene un hueco, el bloque que había entra en su primer hueco; si no, lo
    sustituye."""
    actual = obtener(raiz, ruta)
    nodo = copy.deepcopy(nodo)
    if actual is not None and nodo["k"] in ENVUELVEN:
        h = primer_hueco(nodo)
        if h is not None:
            nodo = con_nodo(nodo, h, actual)
    return con_nodo(raiz, ruta, nodo)


def quitar(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> dict[str, Any] | None:
    """Quita el bloque (con lo que lleva dentro) y deja su hueco: los demás huecos no cambian de sitio."""
    return con_nodo(raiz, ruta, None)


def mover(raiz: dict[str, Any] | None, origen: tuple[str, ...], destino: tuple[str, ...]) -> dict[str, Any] | None:
    """Lleva el bloque de `origen` a `destino`. Soltarlo sobre sí mismo o sobre algo suyo no cambia nada."""
    if destino[:len(origen)] == origen:
        return raiz
    return soltar(quitar(raiz, origen), destino, obtener(raiz, origen))


def con_texto(n: dict[str, Any] | None) -> bool:
    """Si el árbol tiene algún bloque de texto (para releerlo cuando cambian las variables)."""
    return n is not None and (n["k"] == "texto" or any(con_texto(n[c]) for c in hijos(n)))


def normalizar_duracion(texto: str) -> str | None:
    """«3 s» -> «3s»; vacío o 0 -> «» (sin retardo); lo que no es una duración, None."""
    t = texto.strip()
    if t in ("", "0"):
        return ""
    m = _DURACION.fullmatch(t)
    if not m:
        return None
    return "" if float(m.group(1).replace(",", ".")) == 0 else re.sub(r"\s+", "", t)


def _citar(nombre: str) -> str:
    return nombre if _SIMPLE.fullmatch(nombre) and nombre not in _RESERVADAS else f"`{nombre}`"


# -- texto -> árbol ----------------------------------------------------------------------------------------
def _etiquetas(etapas: list[str]) -> list[str]:
    """Etiquetas de etapa con que `a_nucleo` resuelve las X…: «X1» -> «1»; si hay dos («E1» y «1»), las dos."""
    out: list[str] = []
    for x, c in Counter(etapas).items():
        m = re.fullmatch(r"X(\w+)", x)
        if m:
            out += [f"E{m.group(1)}", m.group(1)] if c > 1 else [m.group(1)]
    return out


def _dur_usuario(us: int) -> str:
    """Microsegundos -> «3s» (entero en s), «500ms» (entero en ms) o «1500us»."""
    return f"{us // 1_000_000}s" if us % 1_000_000 == 0 else f"{us // 1000}ms" if us % 1000 == 0 else f"{us}us"


def _crudo_de(m: dict[str, Any]) -> str:
    """El significado como texto del usuario; las duraciones (que `render` da en µs) como las escribe quien dibuja."""
    t = re.sub(r"`[^`]*`|(?<![\w.])(\d+) us\b", lambda mo: mo.group(0) if mo.group(1) is None
               else _dur_usuario(int(mo.group(1))), render(m, lambda r: r))
    return a_usuario(t).replace(HUECO, "?")


def _duracion(m: dict[str, Any]) -> str | None:
    """Duración literal (en µs) -> «3s», «500ms», «1500us»; la de 0, vacía; lo que no es una duración, None."""
    lit = m.get("literal") if m["operator"] == "lit" else None
    if not lit or lit["type"] != "duration":
        return None
    us = int(lit["value"])
    return "" if us == 0 else _dur_usuario(us)


def _desde_significado(m: dict[str, Any], variables: dict[str, tuple[str, str]], etapas: list[str]) -> dict[str, Any] | None:
    op = m["operator"]
    hijo = lambda o: _desde_significado(o, variables, etapas)  # noqa: E731
    texto = lambda: nuevo("texto", s=_crudo_de(m))  # noqa: E731
    if op == "lit":
        lit = m["literal"]
        return nuevo("const", v=1 if lit["value"] else 0) if lit["type"] == "bool" else texto()
    if op == "ref":
        nombre = m["reference"]
        if nombre == HUECO:
            return None
        if nombre in variables and variables[nombre][1] == "bool":
            return var(nombre, variables[nombre][0])
        return texto()
    if op == "active":
        x = x_etapa(m["reference"])
        if x not in etapas or (etapas.count(x) > 1 and x == "X" + m["reference"]):
            return texto()  # no existe, o es «active(`1`)» con una etapa E1 que también se escribiría X1
        return nuevo("etapa", n=x)
    if op in ("and", "or"):
        a, b = m["operands"]
        return nuevo("y" if op == "and" else "o", a=hijo(a), b=hijo(b))
    if op in ("not", "rise", "fall"):
        return nuevo({"not": "no", "rise": "sube", "fall": "baja"}[op], a=hijo(m["operands"][0]))
    if op == "delay":
        t1, a, t2 = m["operands"]
        d1, d2 = _duracion(t1), _duracion(t2)
        return texto() if d1 is None or d2 is None else nuevo("temp", t1=d1, t2=d2, a=hijo(a))
    if op in CMP.values():
        izq, der = m["operands"]
        nombre = izq["reference"] if izq["operator"] == "ref" else None
        if nombre == HUECO or (nombre in variables and variables[nombre][1] != "bool"):
            return nuevo("cmp", n=None if nombre == HUECO else nombre,
                         op={v: k for k, v in CMP.items()}[op],
                         v=("true" if der["literal"]["value"] else "false") if der["operator"] == "lit"
                         and der["literal"]["type"] == "bool" else _crudo_de(der))
    return texto()


def texto_a_arbol(texto: str, variables: dict[str, tuple[str, str]], etapas: list[str]) -> dict[str, Any] | None:
    """Texto en la notación del usuario -> árbol de bloques (vacío: sin raíz). Un «?» es un hueco. Si no se puede
    analizar, lanza ValueError con el motivo, breve."""
    t = texto.strip()
    if not t:
        return None
    t = re.sub(r"`[^`]*`|\?", lambda m: HUECO if m.group(0) == "?" else m.group(0), t)
    try:
        nucleo = a_nucleo(t, _etiquetas(etapas), variables.keys(), True)
        significado = parse(nucleo, lambda clase, nombre: nombre)
        return _desde_significado(significado, variables, etapas)
    except ParseError as e:
        raise ValueError(re.sub(r"\s*\(posición \d+\)$", "", str(e)).replace(HUECO, "?")) from e
    except Exception as e:  # noqa: BLE001 - un texto a medias no debe romper la interfaz
        raise ValueError(str(e).replace(HUECO, "?")) from e


# -- árbol -> texto ----------------------------------------------------------------------------------------
_PREC_TEXTO: dict[str, int] = {}


def _prec_texto(s: str) -> int:
    """Precedencia (OR 1, AND 2, NOT 3, comparación 4, el resto 9) del texto crudo de un bloque de texto."""
    if s not in _PREC_TEXTO:
        try:
            top = parse(a_nucleo(re.sub(r"`[^`]*`|\?", lambda m: HUECO if m.group(0) == "?" else m.group(0), s)),
                        lambda clase, nombre: nombre)["operator"]
            _PREC_TEXTO[s] = _TOP_PREC.get(top, 9)
        except Exception:  # noqa: BLE001
            _PREC_TEXTO[s] = 0
    return _PREC_TEXTO[s]


def _efectivo(n: dict[str, Any] | None) -> dict[str, Any] | None:
    """Un «temporizar» sin retardos no cambia el texto: se escribe lo que lleva dentro."""
    while n is not None and n["k"] == "temp" and not (n["t1"] or n["t2"]):
        n = n["a"]
    return n


def _prec(n: dict[str, Any] | None) -> int:
    n = _efectivo(n)
    if n is None:
        return 9
    return {"y": 2, "o": 1, "no": 3, "cmp": 4}.get(n["k"]) or (_prec_texto(n["s"]) if n["k"] == "texto" else 9)


def _atomo(n: dict[str, Any] | None) -> bool:
    """Un nombre o una etapa: lo que puede ir tras ↑, ↓ o la barra de un retardo sin paréntesis."""
    n = _efectivo(n)
    return n is None or n["k"] in ("etapa", "const") or (n["k"] == "var" and (n["n"] is None or _citar(n["n"]) == n["n"])) \
        or (n["k"] == "texto" and bool(_SIMPLE.fullmatch(n["s"])) and n["s"] not in _RESERVADAS)


def _t(n: dict[str, Any] | None, req: int = 0) -> str:
    """Texto del nodo; entre paréntesis si su precedencia es menor que la que exige el sitio donde va."""
    n = _efectivo(n)
    s = _crudo(n)
    return f"({s})" if _prec(n) < req else s


def _crudo(n: dict[str, Any] | None) -> str:
    if n is None:
        return "?"
    k = n["k"]
    if k == "var":
        return _citar(n["n"]) if n["n"] else "?"
    if k == "etapa":
        return n["n"] or "?"
    if k == "const":
        return str(n["v"])
    if k == "y":
        return f"{_t(n['a'], 2)} AND {_t(n['b'], 3)}"
    if k == "o":
        return f"{_t(n['a'], 1)} OR {_t(n['b'], 2)}"
    if k == "no":
        a = _efectivo(n["a"])
        return f"NOT ({_t(a)})" if a is not None and a["k"] == "temp" else f"NOT {_t(a, 3)}"
    if k in ("sube", "baja"):
        a = _efectivo(n["a"])
        s = _t(a, 9) if a is None or a["k"] in ("sube", "baja") or _atomo(a) else f"({_t(a)})"
        return ("↑" if k == "sube" else "↓") + s
    if k == "temp":
        a = _efectivo(n["a"])
        if _atomo(a) or (a is not None and a["k"] in ("no", "sube", "baja") and _atomo(a["a"])):
            base = _t(a, 0)
        else:
            base = f"({_t(a)})"
        return "/".join(([n["t1"]] if n["t1"] else []) + [base] + ([n["t2"]] if n["t2"] else []))
    if k == "cmp":
        return f"{_citar(n['n']) if n['n'] else '?'} {n['op']} {n['v'].strip() or '0'}"
    return n["s"].strip() or "?"


def arbol_a_texto(n: dict[str, Any] | None) -> str:
    """Árbol -> texto en la notación del usuario, con paréntesis solo donde la precedencia lo exige (OR < AND < NOT <
    comparación) y en el operando derecho de igual precedencia; los huecos, como «?»."""
    return "" if n is None else _t(n)


# -- dibujo ------------------------------------------------------------------------------------------------
COLORES = {"entrada": "#2F6FDE", "salida": "#2E9E57", "interna": "#E07B1A", "etapa": "#7C4DDB",
           "operador": "#4B5B73", "comparacion": "#159AAE", "tiempo": "#B07A12", "texto": "#6B7280", "error": "#C0392B",
           "y": "#5F7F0B", "o": "#B83DBA"}  # «y» (oliva) y «o» (fucsia): operadores, pero cada uno con su color
CATEGORIAS = (("entrada", "Entradas"), ("salida", "Salidas"), ("interna", "Memorias"), ("etapa", "Etapas (X)"),
              ("operador", "Operadores"), ("comparacion", "Comparaciones"), ("tiempo", "Tiempo"))
_PAPEL_CAT = {"input": "entrada", "output": "salida", "internal": "interna"}
PADX, PADX_PILA, PADV, GAP, FILA = 10, 7, 3, 4, 3  # relleno lateral y vertical de un bloque, hueco entre piezas y entre filas
ALTO = 20  # alto de las piezas (desplegables, campos)
HUECO_W, HUECO_H = 34, 22
SANGRIA = {"no": 8, "sube": 8, "baja": 8, "temp": 8}  # el hijo de un bloque que envuelve, algo hundido
PUNTA = 8  # cuánto entra la punta de un hexágono
MARGEN = 6
MIME = "application/x-grafcet-bloque"
_ARRASTRE = {"resuelto": False}  # el arrastre en curso (solo hay uno): si algún programador lo recibió


class _Pieza:
    """Una pieza ya medida de un bloque: texto, desplegable o campo."""
    __slots__ = ("tipo", "clave", "texto", "vacio", "w", "h")

    def __init__(self, tipo: str, clave: str, texto: str, vacio: bool, w: float, h: float) -> None:
        self.tipo, self.clave, self.texto, self.vacio, self.w, self.h = tipo, clave, texto, vacio, w, h


class _Caja:
    """Un bloque (o un hueco) ya medido, con sus piezas y cajas hijas colocadas dentro: (x, y, pieza o caja)."""

    def __init__(self, nodo: dict[str, Any] | None, ruta: tuple, w: float, h: float, cat: str = "") -> None:
        self.nodo, self.ruta, self.w, self.h, self.cat = nodo, ruta, w, h, cat
        self.items: list[tuple[float, float, Any]] = []


class Motor:
    """Mide y dibuja bloques. Un bloque se dibuja en línea si cabe; si no, «y»/«o» apilan primer operando, rótulo y
    segundo operando, y los que envuelven ponen su hijo debajo, con sangría. `fuente()` da las variables
    {nombre: (papel, tipo)} y las etapas (en notación X) del modelo."""

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]]) -> None:
        self.fuente = fuente
        self.vars: dict[str, tuple[str, str]] = {}
        self.etapas: list[str] = []
        self.f = QFont()
        self.f.setPixelSize(12)
        self.fb = QFont(self.f)
        self.fb.setBold(True)
        self.m, self.mb = QFontMetricsF(self.f), QFontMetricsF(self.fb)
        self.nat: dict[tuple, float] = {}

    def reiniciar(self) -> None:
        self.vars, self.etapas = self.fuente()
        self.nat = {}

    # -- qué lleva cada bloque
    @staticmethod
    def elementos(n: dict[str, Any]) -> list[tuple]:
        k = n["k"]
        if k in ("var", "etapa"):
            return [("drop", "n", n["n"] or "elegir")]
        if k == "const":
            return [("txt", "", str(n["v"]))]
        if k in ("y", "o"):
            return [("hijo", "a"), ("txt", "", "y" if k == "y" else "o"), ("hijo", "b")]
        if k == "no":
            return [("txt", "", "no"), ("hijo", "a")]
        if k in ("sube", "baja"):
            return [("txt", "", "flanco ↑" if k == "sube" else "flanco ↓"), ("hijo", "a")]
        if k == "temp":
            return [("txt", "", "temporizar"), ("campo", "t1", n["t1"], "t1"), ("txt", "", "/"), ("hijo", "a"),
                    ("txt", "", "/"), ("campo", "t2", n["t2"], "t2")]
        if k == "cmp":
            return [("drop", "n", n["n"] or "elegir"), ("drop", "op", OP_VISIBLE[n["op"]]),
                    ("campo", "v", n["v"], "valor")]
        return [("campo", "s", n["s"], "texto")]

    def categoria(self, n: dict[str, Any]) -> str:
        k = n["k"]
        if k == "var":
            v = self.vars.get(n["n"]) if n["n"] else None
            if n["n"] and v is None:
                return "error"
            return _PAPEL_CAT.get(v[0] if v else n.get("papel"), "texto")
        if k == "etapa":
            return "etapa" if n["n"] is None or n["n"] in self.etapas else "error"
        if k == "cmp":
            return "error" if n["n"] and n["n"] not in self.vars else "comparacion"
        if k == "temp":
            return "tiempo"
        if k == "texto":
            return "error" if _SIMPLE.fullmatch(n["s"]) else "texto"
        return k if k in ("y", "o") else "operador"

    # -- medidas
    def pieza(self, e: tuple, maxw: float = 100000) -> _Pieza:
        tipo = e[0]
        if tipo == "txt":
            return _Pieza("txt", "", e[2], False, self.mb.horizontalAdvance(e[2]), 16)
        texto = e[2] or (e[3] if tipo == "campo" else "")
        vacio = tipo == "campo" and not e[2]
        extra = 22 if tipo == "drop" else 12
        vis = self.m.elidedText(texto, Qt.TextElideMode.ElideRight, max(maxw - extra, 20))
        return _Pieza(tipo, e[1], vis, vacio, max(30 if tipo == "campo" else 0, self.m.horizontalAdvance(vis) + extra), ALTO)

    def natural(self, n: dict[str, Any] | None, ruta: tuple) -> float:
        if n is None:
            return HUECO_W
        if ruta not in self.nat:
            ws = [self.natural(n[e[1]], ruta + (e[1],)) if e[0] == "hijo" else self.pieza(e).w
                  for e in self.elementos(n)]
            self.nat[ruta] = 2 * PADX + sum(ws) + GAP * (len(ws) - 1)
        return self.nat[ruta]

    def caja(self, n: dict[str, Any] | None, ruta: tuple, ancho: float) -> _Caja:
        if n is None:
            return _Caja(None, ruta, HUECO_W, HUECO_H)
        elems = self.elementos(n)
        c = _Caja(n, ruta, 0, 0, self.categoria(n))
        if self.natural(n, ruta) <= ancho:  # todo en una fila
            x, partes = PADX, []
            for e in elems:
                p = self.caja(n[e[1]], ruta + (e[1],), self.natural(n[e[1]], ruta + (e[1],))) if e[0] == "hijo" \
                    else self.pieza(e)
                partes.append((x, p))
                x += p.w + GAP
            c.h = max(p.h for _, p in partes) + 2 * PADV
            c.w = x - GAP + PADX
            c.items = [(x, (c.h - p.h) / 2, p) for x, p in partes]
            return c
        px = PADX_PILA  # apilado, menos relleno: así caben más niveles en poco ancho
        interior = max(ancho - 2 * px, 40)
        sangria = SANGRIA.get(n["k"], 0)
        y, derecha, grupo = float(PADV), 0.0, []

        def vaciar() -> None:
            nonlocal y, derecha
            lineas: list[list[_Pieza]] = [[]]
            x = 0.0
            for p in grupo:
                if lineas[-1] and x + p.w > interior:
                    lineas.append([])
                    x = 0.0
                lineas[-1].append(p)
                x += p.w + GAP
            for linea in lineas:
                if not linea:
                    continue
                h, x = max(p.h for p in linea), float(px)
                for p in linea:
                    c.items.append((x, y + (h - p.h) / 2, p))
                    x += p.w + GAP
                derecha = max(derecha, x - GAP)
                y += h + FILA
            grupo.clear()
        for e in elems:
            if e[0] == "hijo":
                vaciar()
                h = self.caja(n[e[1]], ruta + (e[1],), interior - sangria)
                c.items.append((px + sangria, y, h))
                derecha = max(derecha, px + sangria + h.w)
                y += h.h + FILA
            else:
                grupo.append(self.pieza(e, interior))
        vaciar()
        c.h, c.w = y - FILA + PADV, derecha + px
        return c

    # -- registro de lo que hay en cada sitio (para el ratón)
    def registrar(self, c: _Caja, ox: float, oy: float, bloques: list, piezas: list) -> None:
        bloques.append((QRectF(ox, oy, c.w, c.h), c.ruta, c.nodo))
        for x, y, it in c.items:
            if isinstance(it, _Caja):
                self.registrar(it, ox + x, oy + y, bloques, piezas)
            elif it.tipo != "txt":
                piezas.append((QRectF(ox + x, oy + y, it.w, it.h), it.tipo, c.ruta, it.clave))

    # -- dibujo
    @staticmethod
    def hexagono(r: QRectF) -> QPolygonF:
        d, cy = min(PUNTA, r.height() / 2), r.center().y()
        return QPolygonF([QPointF(r.left(), cy), QPointF(r.left() + d, r.top()), QPointF(r.right() - d, r.top()),
                          QPointF(r.right(), cy), QPointF(r.right() - d, r.bottom()), QPointF(r.left() + d, r.bottom())])

    def pintar(self, p: QPainter, c: _Caja, ox: float, oy: float, padre: QColor | None = None,
               objetivo: tuple | None = None) -> None:
        r = QRectF(ox, oy, c.w, c.h)
        if c.nodo is None:  # un hueco: hexágono hundido y punteado
            fondo = QColor(padre).darker(165) if padre else QColor("#EEF0F4")
            borde = QColor(padre).lighter(185) if padre else QColor("#9AA3B5")
            p.setPen(QPen(borde, 1.2, Qt.PenStyle.DashLine))
            p.setBrush(fondo)
            p.drawPolygon(self.hexagono(r.adjusted(0.5, 0.5, -0.5, -0.5)))
        else:
            color = QColor(COLORES[c.cat])
            p.setPen(QPen(color.darker(145), 1.2))
            p.setBrush(color)
            p.drawPolygon(self.hexagono(r.adjusted(0.5, 0.5, -0.5, -0.5)))
            for x, y, it in c.items:
                if isinstance(it, _Caja):
                    self.pintar(p, it, ox + x, oy + y, color, objetivo)
                else:
                    self._pintar_pieza(p, it, QRectF(ox + x, oy + y, it.w, it.h))
        if objetivo is not None and c.ruta == objetivo:  # el sitio donde caería lo que se arrastra
            p.setPen(QPen(QColor("#FFD43B"), 2.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(self.hexagono(r.adjusted(-0.5, -0.5, 0.5, 0.5)))

    def _pintar_pieza(self, p: QPainter, it: _Pieza, r: QRectF) -> None:
        if it.tipo == "txt":
            p.setFont(self.fb)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, it.texto)
            return
        p.setPen(QPen(QColor(0, 0, 0, 70), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 5, 5)
        p.setFont(self.f)
        if it.tipo == "drop":
            p.setPen(QColor("#1F2937"))
            p.drawText(QRectF(r.left() + 6, r.top(), r.width() - 18, r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, it.texto)
            p.setPen(QColor("#6B7280"))
            p.drawText(QRectF(r.right() - 16, r.top(), 12, r.height()), Qt.AlignmentFlag.AlignCenter, "▾")
        else:
            p.setPen(QColor("#9CA3AF" if it.vacio else "#1F2937"))
            p.drawText(r.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, it.texto)

    def pixmap(self, n: dict[str, Any], ancho: float = 240, dpr: float = 1.0) -> QPixmap:
        """El bloque tal como se ve, para llevarlo pegado al puntero al arrastrarlo."""
        self.reiniciar()
        c = self.caja(n, ("arrastre",), ancho)
        pm = QPixmap(round((c.w + 4) * dpr), round((c.h + 4) * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(0.9)
        self.pintar(p, c, 2, 2)
        p.end()
        return pm


class _Editor(QLineEdit):
    """El campo de texto que se abre sobre una pieza editable: Intro o salir lo aplica, Esc lo descarta."""
    cancelado = Signal()

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.cancelado.emit()
        else:
            super().keyPressEvent(event)


class _Superficie(QWidget):
    """Un lienzo con bloques: los dibuja al ancho disponible (crece en alto, sin barras), abre el desplegable o el
    campo de la pieza donde se hace clic y arrastra el bloque de donde se pulsa."""
    avisa = Signal(str)
    mueve = False  # arrastrar un bloque lo saca de aquí (el área); en la paleta, lo copia

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str = "") -> None:
        super().__init__()
        self.motor = Motor(fuente)
        self.grupo = grupo
        self._raices: list[dict[str, Any] | None] = []
        self._cajas: list[tuple[_Caja, float, float]] = []
        self._bloques: list[tuple[QRectF, tuple, Any]] = []
        self._piezas: list[tuple[QRectF, str, tuple, str]] = []
        self._alto, self._necesario, self._ancho = 40, 0.0, -1
        self._objetivo: tuple | None = None
        self._pulsado: tuple[QPointF, Any] | None = None
        self._editor: _Editor | None = None
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    # -- disposición
    def _maqueta(self, ancho: float) -> tuple[list[tuple[_Caja, float, float]], float]:
        raise NotImplementedError

    def _calcular(self, ancho: int) -> None:
        if ancho == self._ancho:
            return
        self.motor.reiniciar()
        self._cajas, self._alto = self._maqueta(max(ancho, 60))
        self._bloques, self._piezas = [], []
        for c, x, y in self._cajas:
            self.motor.registrar(c, x, y, self._bloques, self._piezas)
        self._necesario = max([x + c.w for c, x, y in self._cajas] or [0]) + MARGEN
        self._ancho = ancho

    def invalidar(self) -> None:
        self._ancho = -1
        self.setMinimumHeight(self.heightForWidth(max(self.width(), 80)))
        self.updateGeometry()
        self.update()

    def ancho_necesario(self, ancho: int) -> float:
        """Hasta dónde llegan los bloques a ese ancho (si pasa de él, se saldrían del lienzo)."""
        self._calcular(ancho)
        return self._necesario

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        self._calcular(w)
        return int(self._alto)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(240, self.heightForWidth(240))  # fijo: un ancho que dependiera del actual no dejaría estrechar

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(80, 40)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.setMinimumHeight(self.heightForWidth(self.width()))

    # -- cambios (los de las raíces se anotan en `_fijar`)
    def _fijar(self, i: int, nueva: dict[str, Any] | None) -> None:
        self._raices[i] = nueva
        self.invalidar()

    def _validar(self, i: int, nueva: dict[str, Any] | None) -> str:
        return ""

    def _partir(self, ruta: tuple) -> tuple[int, tuple]:
        return ruta[0], tuple(ruta[1:])

    def opciones_desplegable(self, n: dict[str, Any], clave: str) -> list[tuple[str, str]]:
        """Las opciones de un desplegable: variables del papel (booleanas), etapas, variables numéricas u operadores."""
        self.motor.reiniciar()
        v, k = self.motor.vars, n["k"]
        if k == "etapa":
            return [(x, x) for x in dict.fromkeys(self.motor.etapas)]
        if clave == "op":
            return [(OP_VISIBLE[o], o) for o in OPERADORES_CMP]
        if k == "cmp":
            return [(nom, nom) for nom, (_, t) in v.items() if t != "bool"]
        papel = (v[n["n"]][0] if n["n"] in v else None) or n.get("papel")
        return [(nom, nom) for nom, (r, t) in v.items() if r == papel and t == "bool"]

    def elegir(self, ruta: tuple, clave: str, valor: str) -> None:
        """Elige en el desplegable de un bloque (la variable, la etapa o el operador de una comparación)."""
        i, r = self._partir(ruta)
        nueva = copy.deepcopy(self._raices[i])
        n = obtener(nueva, r)
        n[clave] = valor
        if n["k"] == "var" and valor in self.motor.vars:
            n["papel"] = self.motor.vars[valor][0]
        self._fijar(i, nueva)

    @staticmethod
    def _no_numerico(texto: str) -> bool:
        """Si el valor escrito es, en el nivel superior, un operador lógico o una comparación (no un operando numérico)."""
        try:
            top = parse(a_nucleo(re.sub(r"`[^`]*`|\?", lambda m: HUECO if m.group(0) == "?" else m.group(0), texto),
                                 booleana=False), lambda clase, nombre: nombre)["operator"]
        except Exception:  # noqa: BLE001 - lo que no se analiza lo rechaza _validar con su motivo
            return False
        return top in ("and", "or", "not", *CMP.values())

    def editar_campo(self, ruta: tuple, clave: str, texto: str) -> bool:
        """Escribe en el campo de un bloque (t1 y t2 de «temporizar», el valor de una comparación, un texto). Un
        retardo que no es una duración, o un valor que no se puede analizar, se rechaza y se avisa."""
        i, r = self._partir(ruta)
        nueva = copy.deepcopy(self._raices[i])
        n = obtener(nueva, r)
        if n["k"] == "temp":
            d = normalizar_duracion(texto)
            if d is None:
                self.avisa.emit("Retardo no válido: escriba «3s», «500ms» o déjelo vacío.")
                return False
            n[clave] = d
        elif n["k"] == "cmp" and clave == "v" and self._no_numerico(texto):
            self.avisa.emit("No válido: el valor de una comparación es un número, un nombre o una operación aritmética.")
            return False
        else:
            n[clave] = texto.strip() or ("0" if n["k"] == "cmp" else "")
        motivo = self._validar(i, nueva)
        if motivo:
            self.avisa.emit(motivo)
            return False
        self._fijar(i, nueva)
        return True

    # -- dibujo
    def _fondo(self, p: QPainter) -> None:
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#C3C9D6"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        self._calcular(self.width())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._fondo(p)
        for c, x, y in self._cajas:
            self.motor.pintar(p, c, x, y, None, self._objetivo)
        self._extra(p)
        p.end()

    def _extra(self, p: QPainter) -> None:
        pass

    # -- ratón
    def _bloque_en(self, pos: QPointF) -> tuple | None:
        """El bloque más interior bajo el puntero (no un hueco): su ruta completa."""
        self._calcular(self.width())
        dentro = [(r.width() * r.height(), ruta) for r, ruta, n in self._bloques if n is not None and r.contains(pos)]
        return min(dentro)[1] if dentro else None

    def ruta_en(self, pos: QPointF) -> tuple | None:
        """El sitio (hueco o bloque) más interior bajo el puntero: donde caería un bloque soltado ahí."""
        self._calcular(self.width())
        dentro = [(r.width() * r.height(), ruta) for r, ruta, n in self._bloques if r.contains(pos)]
        return min(dentro)[1] if dentro else None

    def _pieza_en(self, pos: QPointF) -> tuple | None:
        self._calcular(self.width())
        return next(((r, t, ruta, clave) for r, t, ruta, clave in self._piezas if r.contains(pos)), None)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._cerrar_editor(True)
        pos = event.position()
        pieza = self._pieza_en(pos)
        self._pulsado = (pos, pieza or self._bloque_en(pos), pieza is not None)

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if self._pulsado is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        pos, que, es_pieza = self._pulsado
        if (event.position() - pos).manhattanLength() < 6 or que is None:
            return
        ruta = que[2] if es_pieza else que
        self._pulsado = None
        self._arrastrar(tuple(ruta))

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if self._pulsado is None:
            return
        _, que, es_pieza = self._pulsado
        self._pulsado = None
        if es_pieza:
            r, tipo, ruta, clave = que
            if tipo == "drop":
                self._menu(ruta, clave, r)
            else:
                self._abrir_editor(r, ruta, clave)

    def _menu(self, ruta: tuple, clave: str, r: QRectF) -> None:
        i, rr = self._partir(ruta)
        n = obtener(self._raices[i], rr)
        menu = QMenu(self)
        ops = self.opciones_desplegable(n, clave)
        for texto, valor in ops:
            menu.addAction(texto, lambda v=valor: self.elegir(ruta, clave, v))
        if not ops:
            menu.addAction("(no hay ninguna: créela en el panel Variables)").setEnabled(False)
        menu.exec(self.mapToGlobal(r.bottomLeft().toPoint()))

    def _abrir_editor(self, r: QRectF, ruta: tuple, clave: str) -> None:
        i, rr = self._partir(ruta)
        ed = _Editor(self)
        ed.setText(obtener(self._raices[i], rr)[clave])
        ed.setProperty("destino", (ruta, clave))
        ed.setGeometry(QRect(int(r.left()), int(r.top()) - 1, int(max(r.width(), 70)), int(r.height()) + 2))
        ed.editingFinished.connect(lambda: self._cerrar_editor(True))
        ed.cancelado.connect(lambda: self._cerrar_editor(False))
        self._editor = ed
        ed.show()
        ed.setFocus()
        ed.selectAll()

    def _cerrar_editor(self, aplicar: bool) -> None:
        ed, self._editor = self._editor, None
        if ed is None:
            return
        ruta, clave = ed.property("destino")
        texto = ed.text()
        ed.hide()
        ed.deleteLater()
        if aplicar:
            self.editar_campo(tuple(ruta), clave, texto)

    # -- arrastrar
    def _arrastrar(self, ruta: tuple) -> None:
        i, r = self._partir(ruta)
        nodo = obtener(self._raices[i], r)
        mime = QMimeData()
        mime.setData(MIME, json.dumps({"nodo": nodo, "grupo": self.grupo,
                                       "origen": list(r) if self.mueve else None}).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.motor.pixmap(nodo, 240, self.devicePixelRatioF()))
        drag.setHotSpot(QPoint(12, 12))
        _ARRASTRE["resuelto"] = False
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
        if self.mueve and not _ARRASTRE["resuelto"] and not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.quitar(tuple(r))  # soltado fuera del área: se quita
        self._pulsado = None
        self.invalidar()

    def quitar(self, ruta: tuple) -> None:
        pass


class PaletaBloques(_Superficie):
    """Los bloques de una categoría, uno tras otro (pasan de línea). Sus desplegables y campos se pueden cambiar antes de
    arrastrar el bloque."""

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str = "",
                 columna: bool = False) -> None:
        super().__init__(fuente, grupo)
        self.clave = "entrada"
        self.columna = columna  # uno debajo de otro (el programador); si no, uno tras otro, pasando de línea
        self.cargar("entrada")

    def _maqueta(self, ancho: float) -> tuple[list[tuple[_Caja, float, float]], float]:
        x, y, lh, out = float(MARGEN), float(MARGEN), 0.0, []
        for i, n in enumerate(self._raices):
            c = self.motor.caja(n, (i,), min(self.motor.natural(n, (i,)), ancho - 2 * MARGEN))
            if x > MARGEN and (self.columna or x + c.w > ancho - MARGEN):
                x, y, lh = float(MARGEN), y + lh + GAP * 2, 0.0
            out.append((c, x, y))
            x += c.w + GAP * 2
            lh = max(lh, c.h)
        return out, y + lh + MARGEN

    def cargar(self, clave: str) -> None:
        """Pone los bloques de la categoría con las variables y etapas del modelo; conserva lo elegido en un
        desplegable si sigue existiendo."""
        self.clave = clave
        self.motor.reiniciar()
        v, etapas = self.motor.vars, list(dict.fromkeys(self.motor.etapas))
        previo = {n["k"]: n for n in self._raices if n is not None} if getattr(self, "_clave_previa", None) == clave else {}
        self._clave_previa = clave
        if clave in PAPEL:
            validas = [nom for nom, (r, t) in v.items() if r == PAPEL[clave] and t == "bool"]
            elegido = previo.get("var", {}).get("n")
            nodos = [var(elegido if elegido in validas else (validas[0] if validas else None), PAPEL[clave])]
        elif clave == "etapa":
            elegido = previo.get("etapa", {}).get("n")
            nodos = [nuevo("etapa", n=elegido if elegido in etapas else (etapas[0] if etapas else None))]
        elif clave == "operador":
            nodos = [nuevo("y"), nuevo("o"), nuevo("no"), nuevo("sube"), nuevo("baja"), nuevo("const", v=1),
                     nuevo("const", v=0)]
        elif clave == "comparacion":
            numericas = [nom for nom, (_, t) in v.items() if t != "bool"]
            c = previo.get("cmp") or nuevo("cmp")
            nodos = [{**c, "n": c["n"] if c["n"] in numericas else (numericas[0] if numericas else None)}]
        else:
            nodos = [previo.get("temp") and {**previo["temp"], "a": None} or nuevo("temp")]
        self._raices = nodos
        self.invalidar()

    def bloques(self) -> list[dict[str, Any]]:
        return copy.deepcopy([n for n in self._raices if n is not None])


class AreaBloques(_Superficie):
    """El área de trabajo: el árbol de bloques, con un hueco como raíz si está vacía. Recibe los bloques que se sueltan
    (de la paleta o de ella misma) y los arrastres de una pieza a otra. `modificado` se emite en cada cambio hecho
    con el ratón o con las operaciones de abajo; `poner_arbol` no lo emite."""
    modificado = Signal()
    mueve = True

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str = "") -> None:
        super().__init__(fuente, grupo)
        self._raices = [None]
        self.previo: dict[str, Any] | None = None
        self.setAcceptDrops(True)

    @property
    def arbol(self) -> dict[str, Any] | None:
        return self._raices[0]

    def poner_arbol(self, arbol: dict[str, Any] | None) -> None:
        self._raices = [copy.deepcopy(arbol)]
        self.invalidar()

    def texto(self) -> str:
        return arbol_a_texto(self.arbol)

    def _maqueta(self, ancho: float) -> tuple[list[tuple[_Caja, float, float]], float]:
        if self.arbol is None:
            c = _Caja(None, (0,), min(max(HUECO_W, self.motor.m.horizontalAdvance("arrastre aquí un bloque") + 30),
                                      ancho - 2 * MARGEN), 28)
        else:
            c = self.motor.caja(self.arbol, (0,), ancho - 2 * MARGEN)
        return [(c, float(MARGEN), float(MARGEN))], c.h + 2 * MARGEN

    def _fijar(self, i: int, nueva: dict[str, Any] | None) -> None:
        self.previo = self._raices[i]
        super()._fijar(i, nueva)
        self.modificado.emit()

    def _validar(self, i: int, nueva: dict[str, Any] | None) -> str:
        """Un valor escrito a mano debe poder leerse otra vez como bloques."""
        try:
            texto_a_arbol(arbol_a_texto(nueva), *self._datos())
        except ValueError as e:
            return f"No válido: {e}"
        return ""

    def _datos(self) -> tuple[dict[str, tuple[str, str]], list[str]]:
        return self.motor.fuente()

    # -- operaciones (lo que hacen el ratón y las pruebas)
    def soltar(self, ruta: tuple | None, nodo: dict[str, Any], origen: tuple | None = None) -> bool:
        """Suelta `nodo` en la `ruta` (hueco o bloque; sin ruta, el área vacía) y devuelve si cambió algo. Con
        `origen`, el bloque ya estaba en el árbol y se mueve (se quita de allí). En el área vacía solo sirve si no hay
        raíz: pasa a serlo."""
        if ruta is None:
            if self.arbol is not None:
                return False
            ruta = ()
        ruta = tuple(ruta)
        try:
            nueva = mover(self.arbol, tuple(origen), ruta) if origen is not None else soltar(self.arbol, ruta, nodo)
        except KeyError:
            return False
        if nueva == self.arbol:
            return False
        self._fijar(0, nueva)
        return True

    def quitar(self, ruta: tuple) -> None:
        ruta = tuple(ruta)
        if ruta and ruta[0] == 0:
            ruta = ruta[1:]  # las rutas de la superficie llevan el índice de la raíz; las del modelo, no
        if obtener(self.arbol, ruta) is not None:
            self._fijar(0, quitar(self.arbol, ruta))

    def _partir(self, ruta: tuple) -> tuple[int, tuple]:
        return (0, tuple(ruta)) if not ruta or ruta[0] != 0 else (0, tuple(ruta[1:]))

    # -- arrastres que llegan
    def _datos_mime(self, mime: QMimeData) -> dict[str, Any] | None:
        return json.loads(bytes(mime.data(MIME)).decode()) if mime.hasFormat(MIME) else None

    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: Any) -> None:  # noqa: N802
        d = self._datos_mime(event.mimeData())
        if d is None:
            return
        self._objetivo = self.ruta_en(event.position())
        self.update()
        event.setDropAction(Qt.DropAction.MoveAction if d.get("origen") is not None and d["grupo"] == self.grupo
                            else Qt.DropAction.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event: Any) -> None:  # noqa: N802
        self._objetivo = None
        self.update()

    def dropEvent(self, event: Any) -> None:  # noqa: N802
        d = self._datos_mime(event.mimeData())
        self._objetivo = None
        if d is None:
            return
        ruta = self.ruta_en(event.position())
        origen = tuple(d["origen"]) if d.get("origen") is not None and d["grupo"] == self.grupo else None
        _ARRASTRE["resuelto"] = True
        event.setDropAction(Qt.DropAction.MoveAction if origen is not None else Qt.DropAction.CopyAction)
        event.accept()
        self.soltar(None if ruta is None else tuple(ruta[1:]), d["nodo"], origen)
        self.update()

    def _extra(self, p: QPainter) -> None:
        if self.arbol is None:
            c, x, y = self._cajas[0]
            p.setFont(self.motor.f)
            p.setPen(QColor("#6B7385"))
            p.drawText(QRectF(x, y, c.w, c.h), Qt.AlignmentFlag.AlignCenter, "arrastre aquí un bloque")


class Papelera(QWidget):
    """Papelera visible: soltar aquí un bloque del área lo quita."""

    def __init__(self, al_soltar: Callable[[dict[str, Any]], None]) -> None:
        super().__init__()
        self.al_soltar, self._encima = al_soltar, False
        self.setAcceptDrops(True)
        self.setFixedSize(34, 30)
        self.setToolTip("Papelera: suelte aquí un bloque para quitarlo")

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#C0392B" if self._encima else "#6B7385")
        p.setPen(QPen(color, 1.6))
        p.setBrush(QColor("#FDECEA") if self._encima else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        cx = self.width() / 2
        p.drawLine(QPointF(cx - 7, 9), QPointF(cx + 7, 9))
        p.drawLine(QPointF(cx - 2, 6), QPointF(cx + 2, 6))
        p.drawPolyline(QPolygonF([QPointF(cx - 6, 9), QPointF(cx - 5, 24), QPointF(cx + 5, 24), QPointF(cx + 6, 9)]))
        p.drawLine(QPointF(cx - 2, 12), QPointF(cx - 2, 21))
        p.drawLine(QPointF(cx + 2, 12), QPointF(cx + 2, 21))
        p.end()

    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME):
            self._encima = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: Any) -> None:  # noqa: N802
        self._encima = False
        self.update()

    def dropEvent(self, event: Any) -> None:  # noqa: N802
        self._encima = False
        self.update()
        _ARRASTRE["resuelto"] = True
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
        self.al_soltar(json.loads(bytes(event.mimeData().data(MIME)).decode()))


# -- el programador: paleta, área, papelera ------------------------------------------------------------------
class FlowLayout(QLayout):
    """Los controles uno tras otro, y a la línea siguiente cuando no caben: el panel se puede estrechar."""

    def __init__(self, parent: QWidget | None = None, sep: int = 4) -> None:
        super().__init__(parent)
        self._items: list[Any] = []
        self.sep = sep
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: Any) -> None:  # noqa: N802
        self._items.append(item)

    def addWidget(self, w: QWidget) -> None:  # noqa: N802
        self.addChildWidget(w)
        self.addItem(QWidgetItem(w))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int) -> Any:  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int) -> Any:  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return self._colocar(QRect(0, 0, w, 0), True)

    def setGeometry(self, r: QRect) -> None:  # noqa: N802
        super().setGeometry(r)
        self._colocar(r, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _colocar(self, r: QRect, solo_medir: bool) -> int:
        x, y, alto = r.x(), r.y(), 0
        for it in self._items:
            if it.widget() is not None and it.widget().isHidden():
                continue
            h = it.sizeHint()
            if x + h.width() > r.right() + 1 and alto > 0:
                x, y, alto = r.x(), y + alto + self.sep, 0
            if not solo_medir:
                it.setGeometry(QRect(QPoint(x, y), h))
            x += h.width() + self.sep
            alto = max(alto, h.height())
        return y + alto - r.y()


def _circulo(color: str, d: int = 14) -> QPixmap:
    """El círculo de color de una carpeta de la paleta."""
    pm = QPixmap(d, d)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color).darker(140), 1))
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(1, 1, d - 2, d - 2))
    p.end()
    return pm


def _desplazable(w: QWidget, ancho: int | None = None) -> QScrollArea:
    """Una columna que se desplaza en vertical si no cabe (nunca en horizontal)."""
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.Shape.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sc.setWidget(w)
    if ancho:
        sc.setFixedWidth(ancho)
    return sc


class Programador(QWidget):
    """Programador por bloques, a la manera de Scratch: a la izquierda las categorías como carpetas (círculo de color y
    nombre), a su derecha los bloques de la categoría elegida, uno debajo de otro y que se arrastran, y en el resto el
    área de trabajo con la fórmula (en línea si cabe) con el aviso, «⤢ Ampliar» y la papelera. `fuente()` devuelve las
    variables {nombre: (papel, tipo)} y las etapas (en notación X) del modelo en curso. `cambiado(texto)` se emite en
    cada cambio hecho con bloques (no al llamar a `poner`). Con `historial`, Ctrl+Z y Ctrl+Mayús+Z deshacen y rehacen
    los cambios de bloques; sin él, el deshacer lo pone quien lo usa (`al_deshacer`, `al_rehacer`). «⤢ Ampliar» abre el
    mismo programador en una ventana más grande, sincronizada con éste."""

    cambiado = Signal(str)
    PALETA_MIN, PALETA_MAX = 110, 240  # la columna de bloques mide lo justo para el más ancho, entre estos límites

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], historial: bool = False,
                 ampliable: bool = True, grupo: str | None = None) -> None:
        super().__init__()
        self.fuente, self.historial = fuente, historial
        self.grupo = grupo or f"programador-{id(self)}"
        self.al_deshacer: Callable[[], Any] | None = None
        self.al_rehacer: Callable[[], Any] | None = None
        self._pila: list[Any] = []
        self._rehecho: list[Any] = []
        self._espejo: Programador | None = None
        self._ventana: QWidget | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        # columna 1: las categorías, como carpetas
        carpetas = QWidget()
        cl = QVBoxLayout(carpetas)
        cl.setContentsMargins(0, 0, 2, 0)
        cl.setSpacing(1)
        self.categorias: dict[str, QPushButton] = {}
        for clave, titulo in CATEGORIAS:
            b = QPushButton(titulo)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setIcon(_circulo(COLORES[clave]))
            b.setIconSize(QSize(14, 14))
            b.setToolTip(titulo)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("QPushButton { text-align: left; padding: 2px 6px; border: 1px solid transparent; "
                            "border-radius: 5px; background: transparent; }"
                            "QPushButton:hover { background: #F0F2F7; }"
                            "QPushButton:checked { background: #E3E8F3; border: 1px solid #9AA3B5; font-weight: 600; }")
            b.clicked.connect(lambda _=False, c=clave: self.elegir_categoria(c))
            cl.addWidget(b)
            self.categorias[clave] = b
        cl.addStretch(1)
        self._sc_carpetas = _desplazable(carpetas, max(b.sizeHint().width() for b in self.categorias.values()) + 10)
        lay.addWidget(self._sc_carpetas)
        # columna 2: los bloques de la categoría elegida
        self.paleta = PaletaBloques(fuente, self.grupo, columna=True)
        self._sc_paleta = _desplazable(self.paleta)
        lay.addWidget(self._sc_paleta)
        # columna 3: el área de trabajo y, debajo, el aviso, «Ampliar» y la papelera
        derecha = QVBoxLayout()
        derecha.setSpacing(4)
        self.lienzo = AreaBloques(fuente, self.grupo)
        self.lienzo.modificado.connect(self._tras_cambio)
        self.lienzo.avisa.connect(self._avisar)
        derecha.addWidget(_desplazable(self.lienzo), 1)  # el área es la que crece
        pie = QHBoxLayout()
        pie.setContentsMargins(0, 0, 0, 0)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet("color: #B45309")
        self.aviso.setVisible(False)
        self.aviso.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # no impone su ancho
        pie.addWidget(self.aviso, 1)
        pie.addStretch(1)
        self.ampliar = QPushButton("⤢ Ampliar")
        self.ampliar.setToolTip("Abrir el programador en una ventana más grande (sigue sincronizado con éste)")
        self.ampliar.clicked.connect(self.ampliar_ventana)
        self.ampliar.setVisible(ampliable)
        pie.addWidget(self.ampliar)
        self.papelera = Papelera(self._a_la_papelera)
        pie.addWidget(self.papelera)
        derecha.addLayout(pie)
        lay.addLayout(derecha, 1)
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if historial:
            for atajo, f in (("Ctrl+Z", self.deshacer), ("Ctrl+Shift+Z", self.rehacer), ("Ctrl+Y", self.rehacer)):
                s = QShortcut(QKeySequence(atajo), self)
                s.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                s.activated.connect(f)
        self.elegir_categoria("entrada")

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._sc_carpetas.width() + self._sc_paleta.width() + 180, 140)

    # -- paleta
    def _cargar_paleta(self, clave: str) -> None:
        """Pone los bloques de la categoría y ajusta la columna a su bloque más ancho (más el margen y la barra)."""
        self.paleta.cargar(clave)
        m = self.paleta.motor
        natural = max([m.natural(n, (i,)) for i, n in enumerate(self.paleta._raices)] or [0])
        self._sc_paleta.setFixedWidth(int(min(max(natural + 2 * MARGEN + 16, self.PALETA_MIN), self.PALETA_MAX)))

    def elegir_categoria(self, clave: str) -> None:
        self.categorias[clave].setChecked(True)
        self._cargar_paleta(clave)

    def opciones(self, cajon: str) -> list[tuple[str, str]]:
        """(texto, valor) de lo que ofrece un desplegable de la paleta: variables booleanas de un papel, o etapas."""
        variables, etapas = self.fuente()
        if cajon == "etapa":
            return [(x, x) for x in dict.fromkeys(etapas)]
        return [(n, n) for n, (r, t) in variables.items() if r == PAPEL[cajon] and t == "bool"]

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        self._cargar_paleta(self.paleta.clave)

    # -- texto <-> bloques
    def texto(self) -> str:
        return self.lienzo.texto()

    def poner(self, texto: str) -> None:
        """Muestra un texto (el guardado, o lo escrito a mano) como bloques, sin emitir `cambiado`. Si no se puede
        analizar, los bloques no cambian y se avisa. Si es el mismo que ya hay, no toca el árbol (salvo para releer los
        bloques de texto: una variable pudo crearse)."""
        variables, etapas = self.fuente()
        self._cargar_paleta(self.paleta.clave)
        try:
            if normalizar_espacios(texto) == self.texto():
                nuevo_ = self.lienzo.arbol
                if con_texto(nuevo_):
                    releido = texto_a_arbol(texto, variables, etapas)
                    if arbol_a_texto(releido) == self.texto():
                        nuevo_ = releido
            else:
                nuevo_ = texto_a_arbol(texto, variables, etapas)
                self._pila.clear()
                self._rehecho.clear()
        except ValueError as e:
            self._avisar(f"No se puede pasar a bloques: {e}")
            return
        self._avisar("")
        self._fijar_arbol(nuevo_)

    def _fijar_arbol(self, arbol: dict[str, Any] | None) -> None:
        self.lienzo.poner_arbol(arbol)
        if self._espejo is not None:
            self._espejo._recibir(arbol, self.aviso.text())

    def _recibir(self, arbol: dict[str, Any] | None, aviso: str) -> None:
        self.lienzo.poner_arbol(arbol)
        self._poner_aviso(aviso)

    def _avisar(self, texto: str) -> None:
        self._poner_aviso(texto)
        if self._espejo is not None:
            self._espejo._poner_aviso(texto)

    def _poner_aviso(self, texto: str) -> None:
        self.aviso.setText(texto)
        self.aviso.setVisible(bool(texto))

    def _tras_cambio(self) -> None:
        if self.historial:
            self._pila.append(self.lienzo.previo)
            self._rehecho.clear()
        self._avisar("")
        if self._espejo is not None:
            self._espejo._recibir(self.lienzo.arbol, "")
        self.cambiado.emit(self.texto())

    def colocar(self, nodo: dict[str, Any]) -> bool:
        """Pone un bloque en el primer hueco del árbol (o como raíz, si está vacío). Devuelve si había sitio."""
        arbol = self.lienzo.arbol
        ruta = () if arbol is None else primer_hueco(arbol)
        return ruta is not None and self.lienzo.soltar(ruta, nodo)

    # -- deshacer
    def deshacer(self) -> None:
        """Con historial local, el último cambio de bloques; si no, lo que haya puesto `al_deshacer`."""
        if not self.historial:
            if self.al_deshacer:
                self.al_deshacer()
            return
        if self._pila:
            self._rehecho.append(self.lienzo.arbol)
            self._restaurar(self._pila.pop())

    def rehacer(self) -> None:
        if not self.historial:
            if self.al_rehacer:
                self.al_rehacer()
            return
        if self._rehecho:
            self._pila.append(self.lienzo.arbol)
            self._restaurar(self._rehecho.pop())

    def _restaurar(self, arbol: dict[str, Any] | None) -> None:
        self._fijar_arbol(arbol)
        self.cambiado.emit(self.texto())

    def _a_la_papelera(self, datos: dict[str, Any]) -> None:
        if datos.get("origen") is not None and datos.get("grupo") == self.grupo:
            self.lienzo.quitar(tuple(datos["origen"]))

    # -- ventana ampliada
    def ampliar_ventana(self) -> QWidget:
        """Abre (o trae al frente) el programador en una ventana propia, no modal y sincronizada con éste."""
        if self._ventana is not None:
            self._ventana.show()
            self._ventana.raise_()
            self._ventana.activateWindow()
            return self._ventana
        v = QWidget(self.window(), Qt.WindowType.Window)
        v.setWindowTitle("Programador de bloques")
        v.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        v.resize(980, 600)
        lay = QVBoxLayout(v)
        grande = Programador(self.fuente, ampliable=False, grupo=self.grupo)
        grande.lienzo.modificado.connect(lambda: self._cambio_en_ventana(grande))  # se aplica igual que uno del panel
        grande.al_deshacer, grande.al_rehacer = self.deshacer, self.rehacer
        lay.addWidget(grande)
        for atajo, f in (("Ctrl+Z", self.deshacer), ("Ctrl+Shift+Z", self.rehacer), ("Ctrl+Y", self.rehacer)):
            QShortcut(QKeySequence(atajo), v).activated.connect(f)
        grande.lienzo.poner_arbol(self.lienzo.arbol)
        grande._poner_aviso(self.aviso.text())
        grande.elegir_categoria(self.paleta.clave)
        self._espejo, grande._espejo = grande, self
        v.programador = grande  # type: ignore[attr-defined]
        v.destroyed.connect(self._cerrada)
        self._ventana = v
        v.show()
        return v

    def _cambio_en_ventana(self, grande: Programador) -> None:
        """Un cambio hecho en la ventana ampliada (su árbol ya llegó aquí): historial, aviso y `cambiado`, como si se
        hubiera hecho en este programador."""
        if self.historial:
            self._pila.append(grande.lienzo.previo)
            self._rehecho.clear()
        self._avisar("")
        self.cambiado.emit(self.texto())

    def _cerrada(self, *_: Any) -> None:
        self._ventana, self._espejo = None, None
