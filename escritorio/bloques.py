"""Programador por bloques de receptividades y condiciones (P-IMP-38).

La expresión se arma con bloques que se arrastran (o se pulsan) desde el catálogo de variables y etapas y desde la banda de
categorías (Operadores, Temporizadores, Comparaciones, Constantes) y encajan unos dentro de otros. Las condiciones son fichas:
una variable booleana o una etapa (con un desplegable para elegir cuál), «y» y «o» con dos huecos, «no» y los flancos ↑ ↓
que envuelven a otro bloque (sobre una variable, se dibujan como una sola ficha), las constantes 1 (verdadero) y 0 (falso),
«temporizar» (t1 y t2 como en la norma: 3s/X1, X1/2s) y la comparación de una variable numérica con un valor.

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

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QCursor, QDrag, QFont, QFontMetricsF, QKeySequence, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF, QShortcut)
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QMenu, QPushButton,
    QScrollArea, QSizePolicy, QToolTip, QVBoxLayout, QWidget, QWidgetItem,
)

from grafcet.expressions import CMP, FUNCS_EXPR, FUNCS_REF, KEYWORDS, ParseError, _Parser, parse, render
from grafcet.notation import a_nucleo, a_usuario, normalizar_espacios, x_etapa

from . import estilo
from .arrastre_popup import ejecutar_arrastre
from .ayudas_emergentes import mostrar_ayuda

# -- modelo: el árbol de bloques --------------------------------------------------------------------------
# Un nodo es un diccionario con su clase en "k"; un hueco es None:
#   var(n, papel)  etapa(n)  const(v)  y(a, b, c…)  o(a, b, c…)  no(a)  sube(a)  baja(a)  temp(t1, t2, a)
#   cmp(n, op, v)  par(a)  texto(s)  (lo que no se representa con bloques: aritmética, nombres que no existen)
# par(a) es un paréntesis de agrupación (P-IMP-46): se escribe «(…)» y solo agrupa, no cambia lo que significa.
# Solo el programador de valores de una acción (modo «valor», P-IMP-44): num(v)  vnum(n)  ar(op, a, b)
HIJOS = {"y": ("a", "b"), "o": ("a", "b"), "no": ("a",), "sube": ("a",), "baja": ("a",), "temp": ("a",),
         "ar": ("a", "b"), "par": ("a",)}
ENVUELVEN = frozenset(HIJOS)  # soltados sobre un hueco ocupado, el bloque que había entra en su primer hueco
HUECO = "__hueco__"  # nombre reservado con que se lee un «?» (hueco) del texto
OPERADORES_CMP = ("=", "!=", "<", "<=", ">", ">=")
OP_VISIBLE = {"=": "=", "!=": "≠", "<": "<", "<=": "≤", ">": ">", ">=": "≥"}
OP_ARIT = {"+": "+", "-": "−", "*": "×", "/": "÷"}  # operadores del programador de valores: texto escrito -> el que se ve
PAPEL = {"entrada": "input", "salida": "output", "interna": "internal"}  # categoría de la paleta -> papel
_SIMPLE = re.compile(r"[^\W\d]\w*(?:\.[^\W\d]\w*)*")
_RESERVADAS = KEYWORDS | set(FUNCS_REF) | set(FUNCS_EXPR) | {"delay"}
_DURACION = re.compile(r"(\d+(?:[.,]\d+)?)\s*(us|µs|μs|ms|s)?")
_TOP_PREC = {"or": 1, "and": 2, "not": 3, **{c: 4 for c in CMP.values()}}
AVISO_FLANCO_TEMP = (
    "Un flanco (↑a) no puede usarse en una temporización, "
    "ni a la conexión ni a la desconexión, porque dura un instante."
)


def _contiene_flanco(n: dict[str, Any] | None) -> bool:
    if n is None:
        return False
    if n["k"] in ("sube", "baja"):
        return True
    if n["k"] == "texto":
        s = n.get("s", "")
        return "↑" in s or "↓" in s or bool(re.search(r"\b(?:rise|fall)\s*\(", s))
    return any(_contiene_flanco(n[c]) for c in hijos(n))


def _es_dentro_de_temp(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> bool:
    """True si `ruta` apunta dentro de la condición base (`a`) de un temporizador."""
    if raiz is None or not ruta:
        return False
    for k in range(1, len(ruta) + 1):
        if ruta[k - 1] != "a":
            continue
        try:
            padre = obtener(raiz, ruta[:k - 1])
        except KeyError:
            return False
        if padre is not None and padre["k"] == "temp":
            return True
    return False


def _cmp_solo_lectura(n: dict[str, Any]) -> bool:
    """True si una comparación guardada excede `[variable | operador | número]` y se abre en solo lectura."""
    if n.get("izq"):
        return True
    v = (n.get("v") or "").strip()
    return bool(v) and not bool(re.fullmatch(r"-?\d+(?:[.,]\d+)?", v))


def nuevo(k: str, **campos: Any) -> dict[str, Any]:
    """Un bloque nuevo de la clase `k`, con sus huecos vacíos."""
    base: dict[str, Any] = {
        "var": {"n": None, "papel": "input"}, "etapa": {"n": None}, "const": {"v": 1}, "y": {"a": None, "b": None},
        "o": {"a": None, "b": None}, "no": {"a": None}, "sube": {"a": None}, "baja": {"a": None},
        "temp": {"t1": "3s", "t2": "", "a": None}, "cmp": {"n": None, "op": "=", "v": "0"}, "texto": {"s": ""},
        "num": {"v": "1"}, "vnum": {"n": None}, "ar": {"op": "+", "a": None, "b": None}, "par": {"a": None}}[k]
    return {"k": k, **copy.deepcopy(base), **campos}


def var(nombre: str | None, papel: str = "input") -> dict[str, Any]:
    return nuevo("var", n=nombre, papel=papel)


MAX_ENTRADAS = 26  # un «y» o un «o» llega a tantos huecos como letras (a…z)
_LETRAS = "abcdefghijKlmnopqrstuvwxyz"  # claves de operando; la «k» minúscula es la clase del nodo, no puede ser un hueco


def hijos(n: dict[str, Any] | None) -> tuple[str, ...]:
    """Las claves de los huecos de un bloque. Un «y» o un «o» tiene dos o más (a, b, c…), uno por operando."""
    if not n:
        return ()
    if n["k"] in ("y", "o"):
        out: list[str] = []
        for c in _LETRAS:
            if c not in n:
                break
            out.append(c)
        return tuple(out)
    return HIJOS.get(n["k"], ())


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


def anadir_hueco(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> dict[str, Any] | None:
    """Copia del árbol con otro hueco al final del «y» o el «o» que hay en `ruta` (sin cambio si no lo es o ya tiene
    MAX_ENTRADAS)."""
    nueva = copy.deepcopy(raiz)
    n = obtener(nueva, ruta)
    if n is None or n["k"] not in ("y", "o") or len(hijos(n)) >= MAX_ENTRADAS:
        return raiz
    n[_LETRAS[len(hijos(n))]] = None
    return nueva


def quitar_hueco(raiz: dict[str, Any] | None, ruta: tuple[str, ...], clave: str) -> dict[str, Any] | None:
    """Copia del árbol sin el hueco `clave` del «y» o el «o» de `ruta`, si está vacío y quedan al menos dos más: los de
    detrás pasan a ocupar su lugar. Si no se puede, sin cambio."""
    nueva = copy.deepcopy(raiz)
    n = obtener(nueva, ruta)
    if n is None or n["k"] not in ("y", "o") or clave not in hijos(n) or n[clave] is not None or len(hijos(n)) <= 2:
        return raiz
    cs = list(hijos(n))
    valores = [n[c] for c in cs if c != clave]
    for c in cs:
        del n[c]
    for c, v in zip(_LETRAS, valores):
        n[c] = v
    return nueva


_SENTINELA = {"k": "texto", "s": "\0retirado"}  # marca el sitio de un bloque que sale, mientras se coloca en otro


def _ruta_de(n: dict[str, Any] | None, objeto: dict[str, Any], ruta: tuple[str, ...] = ()) -> tuple[str, ...] | None:
    """La ruta del nodo `objeto` (por identidad) dentro de `n`."""
    if n is objeto:
        return ruta
    for c in hijos(n):
        r = _ruta_de(n[c], objeto, ruta + (c,))
        if r is not None:
            return r
    return None


def _buscar_marca(raiz: dict[str, Any] | None) -> dict[str, Any] | None:
    """El nodo marcado (el único con la sentinela) de un árbol."""
    if raiz is None:
        return None
    if raiz["k"] == "texto" and raiz["s"] == _SENTINELA["s"]:
        return raiz
    return next((x for x in (_buscar_marca(raiz[c]) for c in hijos(raiz)) if x is not None), None)


def _sin_marca(raiz: dict[str, Any] | None) -> dict[str, Any] | None:
    """Copia sin el sitio de la marca: su hueco desaparece si estaba en un «y» o un «o» de más de dos huecos; si no, queda
    vacío."""
    marca = _buscar_marca(raiz)
    ruta = None if marca is None else _ruta_de(raiz, marca)
    if ruta is None:
        return raiz
    vacio = con_nodo(raiz, ruta, None)
    return vacio if not ruta else quitar_hueco(vacio, ruta[:-1], ruta[-1])


def retirar(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> dict[str, Any] | None:
    """Saca el bloque de `ruta`: si estaba en un «y» o un «o» de más de dos huecos, su hueco desaparece (nunca baja de
    dos); si no, queda su hueco vacío."""
    return _sin_marca(con_nodo(raiz, ruta, copy.deepcopy(_SENTINELA)))


def soltar_en_mas(raiz: dict[str, Any] | None, ruta: tuple[str, ...], nodo: dict[str, Any],
                  origen: tuple[str, ...] | None = None) -> dict[str, Any] | None:
    """Suelta un bloque sobre el «+» del «y» o el «o» de `ruta`: lo añade en un hueco nuevo al final. Con `origen`, el
    bloque ya estaba en el árbol y se mueve (se quita de allí); soltarlo sobre algo suyo no cambia nada."""
    base = raiz
    if origen is not None:
        if ruta[:len(origen)] == origen:
            return raiz
        nodo, base = obtener(raiz, origen), con_nodo(raiz, origen, copy.deepcopy(_SENTINELA))
    con_hueco = anadir_hueco(base, ruta)
    if con_hueco is base:
        return raiz
    puesto = con_nodo(con_hueco, ruta + (hijos(obtener(con_hueco, ruta))[-1],), nodo)
    return _sin_marca(puesto) if origen is not None else puesto


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
    """Lleva el bloque de `origen` a `destino`; su hueco de origen desaparece si era de un «y» o un «o» de más de dos.
    Soltarlo sobre sí mismo o sobre algo suyo no cambia nada."""
    if destino[:len(origen)] == origen:
        return raiz
    marcada = con_nodo(raiz, origen, copy.deepcopy(_SENTINELA))
    return _sin_marca(soltar(marcada, destino, obtener(raiz, origen)))


# -- modificadores (NOT, ↑, ↓), envolver y huecos pendientes: operaciones puras del formulador (E8) --------------------------
# NOT, ↑ y ↓ son nodos que envuelven a otro (`no`, `sube`, `baja`): no cambian el modelo ni lo que se escribe. Sobre una ficha se
# aplican en el orden en que se pulsan (`↑(NOT a)` es NOT y luego ↑; `NOT ↑a`, ↑ y luego NOT). Una «cadena» es el bloque con todos
# sus modificadores seguidos: la ficha que el usuario ve y a la que se aplican.
MODIFICADORES = ("no", "sube", "baja")


def cadena_modificadores(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> tuple[tuple[str, ...], list[str]]:
    """La cadena de modificadores que contiene el bloque (o el hueco) de `ruta`: sube mientras el padre sea `no`, `sube` o `baja` y baja
    por los que lleva dentro. Devuelve la ruta del más externo y las clases de los modificadores de dentro afuera (vacía: el bloque no
    lleva ninguno). Desde cualquier eslabón de la cadena, o desde el bloque de dentro, da lo mismo; la ruta del bloque de dentro es
    `externa + ("a",) * len(mods)`."""
    while ruta and obtener(raiz, ruta[:-1])["k"] in MODIFICADORES:
        ruta = ruta[:-1]
    mods: list[str] = []
    n = obtener(raiz, ruta)
    while n is not None and n["k"] in MODIFICADORES:
        mods.append(n["k"])
        n = n["a"]
    return ruta, mods[::-1]


def alternar_modificador(raiz: dict[str, Any] | None, ruta: tuple[str, ...], clase: str) -> dict[str, Any] | None:
    """Pulsa NOT, ↑ o ↓ sobre la ficha de `ruta` (un bloque cualquiera, su cadena de modificadores o un hueco). NOT: si ya lo lleva, se
    quita; si no, se pone por fuera. Flanco: si ya lleva ese mismo, se quita; si lleva el otro, lo cambia (↑ por ↓) en su sitio; si no
    lleva ninguno, se pone por fuera. Sobre un hueco deja el modificador con su hueco (`NOT ?`). La ruta del bloque más externo no
    cambia. Una clase que no es modificador no hace nada. Devuelve un árbol nuevo."""
    if clase not in MODIFICADORES:
        return raiz
    externa, mods = cadena_modificadores(raiz, ruta)
    nueva = list(mods)
    if clase == "no":
        if "no" in nueva:
            nueva.remove("no")
        else:
            nueva.append("no")
    else:
        flancos = [i for i, m in enumerate(nueva) if m != "no"]
        if not flancos:
            nueva.append(clase)
        elif nueva[flancos[0]] == clase:
            del nueva[flancos[0]]
        else:
            nueva[flancos[0]] = clase
    nodo = obtener(raiz, externa + ("a",) * len(mods))
    for m in nueva:
        nodo = nuevo(m, a=copy.deepcopy(nodo))
    return con_nodo(raiz, externa, nodo)


def envolver(raiz: dict[str, Any] | None, ruta: tuple[str, ...], clase: str) -> dict[str, Any] | None:
    """Envuelve el bloque (o el hueco) de `ruta` en un bloque nuevo de `clase`, que lo lleva en su primer hueco: «Envolver ( … )»
    (`par`), «temporizar» (`temp`), NOT, ↑, ↓. Es lo que `soltar` hace con un bloque de esa clase sobre uno ocupado. Una clase sin
    huecos no hace nada."""
    envoltorio = nuevo(clase)
    h = primer_hueco(envoltorio)
    if clase not in ENVUELVEN or h is None:
        return raiz
    return con_nodo(raiz, ruta, con_nodo(envoltorio, h, obtener(raiz, ruta)))


def desenvolver(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> dict[str, Any] | None:
    """«Quitar paréntesis», «Quitar retardo», quitar un modificador: el bloque de `ruta` (`par`, `temp`, `no`, `sube` o `baja`) se
    sustituye por el que lleva dentro, o por un hueco si estaba vacío. Con cualquier otro bloque no hace nada."""
    n = obtener(raiz, ruta)
    if n is None or n["k"] not in ("par", "temp", *MODIFICADORES):
        return raiz
    return con_nodo(raiz, ruta, n["a"])


def a_lista(n: dict[str, Any] | None) -> tuple[list[dict[str, Any] | None], list[str]]:
    """Árbol de `y`/`o` -> (operandos, conectores entre ellos: 'y' o 'o'). Un `par` queda como un operando más."""
    if n is None or n["k"] not in ("y", "o"):
        return ([], []) if n is None else ([n], [])
    if n["k"] == "y":
        hs = [n[c] for c in hijos(n)]
        return hs, ["y"] * (len(hs) - 1)
    ops: list[dict[str, Any] | None] = []
    cons: list[str] = []
    for i, c in enumerate(hijos(n)):
        if i:
            cons.append("o")
        h = n[c]
        if h is not None and h["k"] == "y":
            sub_ops, sub_cons = a_lista(h)
            ops.extend(sub_ops)
            cons.extend(sub_cons)
        else:
            ops.append(h)
    return ops, cons


def _tramos_lista(ops: list[dict[str, Any] | None], cons: list[str]) -> list[list[dict[str, Any] | None]]:
    if not ops:
        return []
    tramos: list[list[dict[str, Any] | None]] = [[ops[0]]]
    for op, c in zip(ops[1:], cons):
        if c == "o":
            tramos.append([op])
        else:
            tramos[-1].append(op)
    return tramos


def de_lista(ops: list[dict[str, Any] | None], cons: list[str]) -> dict[str, Any] | None:
    """(operandos, conectores) -> árbol de `o` y `y` con la precedencia `OR < AND`."""
    tramos = _tramos_lista(ops, cons)
    if not tramos:
        return None
    nodos_o = [
        t[0] if len(t) == 1 else nuevo("y", **{k: v for k, v in zip(_LETRAS, t[:MAX_ENTRADAS])})
        for t in tramos
    ]
    if len(nodos_o) == 1:
        return nodos_o[0]
    return nuevo("o", **{k: v for k, v in zip(_LETRAS, nodos_o[:MAX_ENTRADAS])})


def _raiz_yo(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> tuple[str, ...]:
    """Sube desde `ruta` mientras esté en un `y` cuyo padre sea un `o` (la misma lista plana)."""
    actual = tuple(ruta)
    while actual:
        n = obtener(raiz, actual)
        padre = obtener(raiz, actual[:-1])
        if n is not None and n["k"] == "y" and padre is not None and padre["k"] == "o":
            actual = actual[:-1]
        else:
            break
    return actual


def _rutas_lista(raiz: dict[str, Any] | None, ruta_yo: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Las rutas en `raiz` de cada operando que devuelve `a_lista(obtener(raiz, ruta_yo))`."""
    n = obtener(raiz, ruta_yo)
    if n is None or n["k"] not in ("y", "o"):
        return [] if n is None else [ruta_yo]
    if n["k"] == "y":
        return [ruta_yo + (c,) for c in hijos(n)]
    out: list[tuple[str, ...]] = []
    for c in hijos(n):
        h = n[c]
        if h is not None and h["k"] == "y":
            out.extend(ruta_yo + (c, sc) for sc in hijos(h))
        else:
            out.append(ruta_yo + (c,))
    return out


def cambiar_conector_lista(raiz: dict[str, Any] | None, ruta: tuple[str, ...], indice: int) -> dict[str, Any] | None:
    """Alterna entre `y` (`·`) y `o` (`+`) el conector `indice` en la lista plana `a_lista` del bloque `y`/`o` de `ruta`."""
    n = obtener(raiz, ruta)
    if n is None or n["k"] not in ("y", "o"):
        return raiz
    ops, cons = a_lista(n)
    if not (0 <= indice < len(cons)):
        return raiz
    nuevos_cons = list(cons)
    nuevos_cons[indice] = "o" if nuevos_cons[indice] == "y" else "y"
    return con_nodo(raiz, ruta, de_lista(ops, nuevos_cons))


def cambiar_conector(raiz: dict[str, Any] | None, ruta: tuple[str, ...], indice: int) -> dict[str, Any] | None:
    """Alterna entre `y` (· Y) y `o` (+ O) el conector `indice` del bloque `y`/`o` de `ruta` (`OR < AND`)."""
    n = obtener(raiz, ruta)
    if n is None or n["k"] not in ("y", "o"):
        return raiz
    hs = hijos(n)
    if not (0 <= indice < len(hs) - 1):
        return raiz
    if n["k"] == "o":
        base = ruta
        ops, cons = a_lista(n)
        anteriores = sum(
            len(hijos(n[c])) if n[c] is not None and n[c]["k"] == "y" else 1
            for c in hs[:indice + 1]
        )
        pos = anteriores - 1
    else:
        base = _raiz_yo(raiz, ruta)
        nodo_base = obtener(raiz, base)
        ops, cons = a_lista(nodo_base)
        desplazamiento = 0
        if base != ruta:
            clave_rama = ruta[len(base)]
            for c in hijos(nodo_base):
                if c == clave_rama:
                    break
                h = nodo_base[c]
                desplazamiento += len(hijos(h)) if h is not None and h["k"] == "y" else 1
        pos = desplazamiento + indice
    if not (0 <= pos < len(cons)):
        return raiz
    nuevos_cons = list(cons)
    nuevos_cons[pos] = "o" if nuevos_cons[pos] == "y" else "y"
    tramos = _tramos_lista(ops, nuevos_cons)
    if len(tramos) > MAX_ENTRADAS or any(len(t) > MAX_ENTRADAS for t in tramos):
        return raiz
    return con_nodo(raiz, base, de_lista(copy.deepcopy(ops), nuevos_cons))


def a_lista_ar(n: dict[str, Any] | None) -> tuple[list[dict[str, Any] | None], list[str]]:
    """Operación aritmética en línea -> (operandos, operadores entre ellos: '+', '-', '*', '/')."""
    if n is None or n["k"] != "ar":
        return ([], []) if n is None else ([n], [])
    ops: list[dict[str, Any] | None] = []
    cons: list[str] = []

    def rec(m: dict[str, Any]) -> None:
        pr = 5 if m["op"] in "+-" else 6
        for clave, req in (("a", pr), ("b", pr + 1)):
            if clave == "b":
                cons.append(m["op"])
            h = m[clave]
            if h is not None and h["k"] == "ar" and (5 if h["op"] in "+-" else 6) >= req:
                rec(h)
            else:
                ops.append(h)

    rec(n)
    return ops, cons


def de_lista_ar(ops: list[dict[str, Any] | None], cons: list[str]) -> dict[str, Any] | None:
    """(operandos, operadores) -> árbol de `ar` con precedencia (*, / antes que +, -) y asociatividad izquierda."""
    if not ops:
        return None
    tramos: list[dict[str, Any] | None] = [ops[0]]
    sumas: list[str] = []
    for op, c in zip(ops[1:], cons):
        if c in "+-":
            sumas.append(c)
            tramos.append(op)
        else:
            tramos[-1] = nuevo("ar", op=c, a=tramos[-1], b=op)
    res = tramos[0]
    for op, c in zip(tramos[1:], sumas):
        res = nuevo("ar", op=c, a=res, b=op)
    return res


def cambiar_operador_ar(raiz: dict[str, Any] | None, ruta: tuple[str, ...], indice: int) -> dict[str, Any] | None:
    """Cicla el operador `indice` (+ -> - -> * -> /) de la operación aritmética en línea de `ruta`."""
    n = obtener(raiz, ruta)
    if n is None or n["k"] != "ar":
        return raiz
    ops, cons = a_lista_ar(n)
    if not (0 <= indice < len(cons)):
        return raiz
    orden = ("+", "-", "*", "/")
    nuevos_cons = list(cons)
    nuevos_cons[indice] = orden[(orden.index(nuevos_cons[indice]) + 1) % len(orden)]
    return con_nodo(raiz, ruta, de_lista_ar(copy.deepcopy(ops), nuevos_cons))


def envolver_varios(
    raiz: dict[str, Any] | None,
    rutas: list[tuple[str, ...]],
) -> tuple[dict[str, Any] | None, tuple[str, ...] | None]:
    """Envuelve entre paréntesis (`par`) varios operandos contiguos seleccionados de una misma lista `y`/`o`."""
    limpias = [tuple(r) for r in rutas if r is not None]
    if not limpias:
        return raiz, None
    if len(limpias) == 1:
        r = limpias[0]
        return (envolver(raiz, r, "par"), r) if obtener(raiz, r) is not None else (raiz, None)
    base = _raiz_yo(raiz, limpias[0][:-1])
    rutas_op = _rutas_lista(raiz, base)
    indices = sorted(i for i, ro in enumerate(rutas_op) if any(ro == r or r[:len(ro)] == ro for r in limpias))
    if len(indices) < 2:
        return raiz, None
    i0, i1 = indices[0], indices[-1]
    if indices != list(range(i0, i1 + 1)):
        return raiz, None
    nodo_base = obtener(raiz, base)
    ops, cons = a_lista(nodo_base)
    if len(indices) == len(ops):
        return envolver(raiz, base, "par"), base
    sub_ops = copy.deepcopy(ops[i0:i1 + 1])
    sub_cons = list(cons[i0:i1])
    grupo = nuevo("par", a=de_lista(sub_ops, sub_cons))
    nuevos_ops = copy.deepcopy(ops[:i0]) + [grupo] + copy.deepcopy(ops[i1 + 1:])
    nuevos_cons = list(cons[:i0]) + list(cons[i1:])
    nuevo_base = de_lista(nuevos_ops, nuevos_cons)
    nueva_raiz = con_nodo(raiz, base, nuevo_base)
    rutas_nuevas = _rutas_lista(nueva_raiz, base)
    ruta_grupo = rutas_nuevas[i0] if i0 < len(rutas_nuevas) else base
    return nueva_raiz, ruta_grupo


def desenvolver_en(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> dict[str, Any] | None:
    """Quita los paréntesis del `par` de `ruta`; si está dentro de un `y`/`o` y encierra un `y`/`o`, lo integra."""
    n = obtener(raiz, ruta)
    if n is None or n["k"] != "par":
        return desenvolver(raiz, ruta)
    hijo = n["a"]
    if ruta and hijo is not None and hijo["k"] in ("y", "o"):
        padre = obtener(raiz, ruta[:-1])
        if padre is not None and padre["k"] in ("y", "o"):
            base = _raiz_yo(raiz, ruta[:-1])
            rutas_op = _rutas_lista(raiz, base)
            if ruta in rutas_op:
                idx = rutas_op.index(ruta)
                ops, cons = a_lista(obtener(raiz, base))
                sub_ops, sub_cons = a_lista(hijo)
                nuevos_ops = copy.deepcopy(ops[:idx]) + copy.deepcopy(sub_ops) + copy.deepcopy(ops[idx + 1:])
                nuevos_cons = list(cons[:idx]) + list(sub_cons) + list(cons[idx:])
                tramos = _tramos_lista(nuevos_ops, nuevos_cons)
                if len(tramos) <= MAX_ENTRADAS and all(len(t) <= MAX_ENTRADAS for t in tramos):
                    return con_nodo(raiz, base, de_lista(nuevos_ops, nuevos_cons))
    return desenvolver(raiz, ruta)


def _rutas_ar(raiz: dict[str, Any] | None, base: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Las rutas en `raiz` de cada operando que devuelve `a_lista_ar(obtener(raiz, base))`."""
    n = obtener(raiz, base)
    if n is None or n["k"] != "ar":
        return [] if n is None else [base]
    out: list[tuple[str, ...]] = []

    def rec(m: dict[str, Any], camino: tuple[str, ...]) -> None:
        pr = 5 if m["op"] in "+-" else 6
        for clave, req in (("a", pr), ("b", pr + 1)):
            h = m[clave]
            if h is not None and h["k"] == "ar" and (5 if h["op"] in "+-" else 6) >= req:
                rec(h, camino + (clave,))
            else:
                out.append(camino + (clave,))

    rec(n, base)
    return out


def _quitar_limpio(raiz: dict[str, Any] | None, ruta: tuple[str, ...]) -> dict[str, Any] | None:
    """Elimina el bloque de `ruta` del carril SIN dejar huecos `?`: colapsa `y`/`o`/`ar` de 1 elemento, deja
    `par(a=None)` si se vacía un grupo `( … )` y devuelve `None` si se quita la raíz."""
    ruta = tuple(ruta)
    if raiz is None or not ruta:
        return None
    try:
        padre = obtener(raiz, ruta[:-1])
    except KeyError:
        return raiz
    if padre is None:
        return raiz
    pk = padre["k"]
    if pk in ("y", "o"):
        base = _raiz_yo(raiz, ruta[:-1])
        rutas_op = _rutas_lista(raiz, base)
        if ruta in rutas_op:
            idx = rutas_op.index(ruta)
            ops, cons = a_lista(obtener(raiz, base))
            ops = [copy.deepcopy(o) for i, o in enumerate(ops) if i != idx]
            cons = list(cons)
            if cons:
                del cons[0 if idx == 0 else idx - 1]
            nuevo_sub = de_lista(ops, cons) if ops else None
            return con_nodo(raiz, base, nuevo_sub)
    if pk == "ar":
        otro = "b" if ruta[-1] == "a" else "a"
        restante = copy.deepcopy(padre[otro])
        return con_nodo(raiz, ruta[:-1], restante)
    if pk == "par":
        return con_nodo(raiz, ruta, None)
    if pk == "temp":
        return con_nodo(raiz, ruta, None)
    if pk in MODIFICADORES:
        ext, _ = cadena_modificadores(raiz, ruta)
        return _quitar_limpio(raiz, ext)
    return retirar(raiz, ruta)


def _insertar_en_posicion(
    raiz: dict[str, Any] | None,
    base_cont: tuple[str, ...],
    indice: int,
    nodo: dict[str, Any],
    valor: bool = False,
) -> dict[str, Any] | None:
    """Inserta `nodo` en el contenedor `base_cont` (`()` para raíz, `r_par + ('a',)` o `r_temp + ('a',)` para interior)
    en la posición `indice` (`0..len`), conectándolo automáticamente con `·` (booleano) o `+` (aritmético)."""
    copia = copy.deepcopy(nodo)
    sub = raiz if not base_cont else obtener(raiz, base_cont)
    if sub is None:
        nuevo_sub = copia
    elif valor:
        ops, cons = a_lista_ar(sub)
        idx = max(0, min(indice, len(ops)))
        ops = [copy.deepcopy(o) for o in ops]
        cons = list(cons)
        ops.insert(idx, copia)
        cons.insert(0 if idx == 0 else idx - 1, "+")
        nuevo_sub = de_lista_ar(ops, cons)
    else:
        ops, cons = a_lista(sub)
        idx = max(0, min(indice, len(ops)))
        ops = [copy.deepcopy(o) for o in ops]
        cons = list(cons)
        ops.insert(idx, copia)
        cons.insert(0 if idx == 0 else idx - 1, "y")
        nuevo_sub = de_lista(ops, cons)
    return nuevo_sub if not base_cont else con_nodo(raiz, base_cont, nuevo_sub)


def _buscar_etiqueta(n: dict[str, Any] | None, ruta: tuple[str, ...] = ()) -> tuple[str, ...] | None:
    if n is None:
        return None
    if n.get("_tag_mov"):
        return ruta
    for c in hijos(n):
        hit = _buscar_etiqueta(n[c], ruta + (c,))
        if hit is not None:
            return hit
    return None


def _mover_en_posicion(
    raiz: dict[str, Any] | None,
    origen: tuple[str, ...],
    base_cont: tuple[str, ...],
    indice: int,
    valor: bool = False,
) -> dict[str, Any] | None:
    """Mueve el bloque de `origen` al contenedor `base_cont` en la posición `indice` sin dejar huecos `?`."""
    origen, base_cont = tuple(origen), tuple(base_cont)
    if raiz is None or base_cont[:len(origen)] == origen:
        return raiz
    try:
        nodo = copy.deepcopy(obtener(raiz, origen))
    except KeyError:
        return raiz
    if nodo is None:
        return raiz
    rutas_dest = _rutas_ar(raiz, base_cont) if valor else _rutas_lista(raiz, base_cont)
    if origen in rutas_dest:
        orig_idx = rutas_dest.index(origen)
        if orig_idx < indice:
            indice -= 1
        if orig_idx == indice:
            return raiz
    copia = copy.deepcopy(raiz)
    etiquetado = False
    if base_cont:
        padre_cont = obtener(copia, base_cont[:-1])
        if padre_cont is not None:
            padre_cont["_tag_mov"] = True
            etiquetado = True
    sin_orig = _quitar_limpio(copia, origen)
    if etiquetado:
        ruta_padre = _buscar_etiqueta(sin_orig)
        if ruta_padre is None:
            return raiz
        obtener(sin_orig, ruta_padre).pop("_tag_mov", None)
        nuevo_base = ruta_padre + (base_cont[-1],)
    else:
        nuevo_base = ()
    return _insertar_en_posicion(sin_orig, nuevo_base, indice, nodo, valor)


def faltan(raiz: dict[str, Any] | None) -> int:
    """Cuántos huecos le faltan a la fórmula: los que `arbol_a_texto` escribe como «?» (huecos vacíos y fichas sin nombre). Sin fórmula
    (raíz vacía) no falta nada: no hay qué completar."""
    def cuenta(n: dict[str, Any] | None) -> int:
        if n is None:
            return 1
        k = n["k"]
        propio = (
            (k in ("var", "etapa", "vnum") and not n["n"])
            or (k == "cmp" and not n.get("izq") and (not n["n"] or not (n.get("v") or "").strip()))
            or (k == "texto" and not n["s"].strip())
        )
        return int(propio) + sum(cuenta(n[c]) for c in hijos(n))
    return 0 if raiz is None else cuenta(raiz)


def con_texto(n: dict[str, Any] | None) -> bool:
    """Si el árbol tiene algún bloque de texto (para releerlo cuando cambian las variables)."""
    return n is not None and (n["k"] == "texto" or any(con_texto(n[c]) for c in hijos(n)))


def normalizar_duracion(texto: str) -> str | None:
    """«3 s» -> «3s»; «3» -> «3s» (asume segundos); vacío o 0 -> «» (sin retardo); lo que no es una duración, None."""
    t = texto.strip()
    if t in ("", "0"):
        return ""
    m = _DURACION.fullmatch(t)
    if not m:
        return None
    if float(m.group(1).replace(",", ".")) == 0:
        return ""
    unidad = m.group(2) or "s"
    return f"{m.group(1)}{unidad}"


def sin_comillas(texto: str) -> str:
    """El texto de una fórmula tal como se lee, sin las comillas invertidas con que el núcleo escribe un nombre que no es una
    palabra simple (`Marcha motor`, `1M1`): el usuario no las ve ni las teclea."""
    return re.sub(r"`([^`]*)`", r"\1", texto or "")


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


class _AnalizadorConGrupos(_Parser):
    """El analizador del núcleo, que descarta los paréntesis de agrupación, pero aquí cada «( … )» queda como un nodo
    `grupo` de un operando (solo para pasar a bloques, P-IMP-46): el núcleo, su significado y su forma canónica no cambian.
    Los paréntesis de una llamada (`rise(…)`, `delay(…)`) no son grupos."""

    def primary(self) -> dict[str, Any]:
        tipo, valor, _ = self.peek()
        if tipo == "op" and valor == "(":
            self.take()
            nodo = self.or_()
            self.take("op", ")")
            return {"operator": "grupo", "operands": [nodo]}
        return super().primary()


def _analizar(nucleo: str) -> dict[str, Any]:
    """Texto del núcleo -> significado con los paréntesis de agrupación como nodos `grupo`."""
    return _AnalizadorConGrupos(nucleo, lambda clase, nombre: nombre).parse()


def _render_grupos(m: dict[str, Any]) -> str:
    """`render` del núcleo, que escribe los paréntesis solo donde la precedencia los pide, más los nodos `grupo`: cada
    uno se escribe como «( … )». Los grupos se apartan con un nombre provisional (que `render` trata como un operando) y
    se vuelven a poner al final."""
    grupos: list[str] = []

    def sin_grupos(o: dict[str, Any]) -> dict[str, Any]:
        if o["operator"] == "grupo":
            grupos.append(_render_grupos(o["operands"][0]))
            return {"operator": "ref", "reference": f"__grupo{len(grupos) - 1}__"}
        return {**o, "operands": [sin_grupos(x) for x in o["operands"]]} if "operands" in o else o
    t = render(sin_grupos(m), lambda r: r)
    return re.sub(r"(?<![\w`])__grupo(\d+)__(?![\w`])", lambda mo: f"({grupos[int(mo.group(1))]})", t)


def _crudo_de(m: dict[str, Any]) -> str:
    """El significado como texto del usuario; las duraciones (que `render` da en µs) como las escribe quien dibuja."""
    t = re.sub(r"`[^`]*`|(?<![\w.])(\d+) us\b", lambda mo: mo.group(0) if mo.group(1) is None
               else _dur_usuario(int(mo.group(1))), _render_grupos(m))
    return a_usuario(t).replace(HUECO, "?")


def _duracion(m: dict[str, Any]) -> str | None:
    """Duración literal (en µs) -> «3s», «500ms», «1500us»; la de 0, vacía; lo que no es una duración, None."""
    lit = m.get("literal") if m["operator"] == "lit" else None
    if not lit or lit["type"] != "duration":
        return None
    us = int(lit["value"])
    return "" if us == 0 else _dur_usuario(us)


def etapa_visible(n: str | None) -> str | None:
    """Cómo se ve una ficha de etapa: «X1», «X0fsd»… En el árbol una etapa que no es «X<número>» va como `active(`0fsd`)`, que es lo que
    entiende el analizador pero no lo que se lee en la fórmula ni en el dibujo."""
    if n is None:
        return None
    mo = re.fullmatch(r"active\(`(.+)`\)|active\(([^\W\d]\w*(?:\.\w+)?)\)", n)
    return "X" + (mo.group(1) or mo.group(2)) if mo else n


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
        operandos: list[dict[str, Any]] = []  # una cadena del mismo operador (a OR b OR c) es un solo bloque de n huecos
        while m["operator"] == op:
            operandos.insert(0, m["operands"][1])
            m = m["operands"][0]
        operandos.insert(0, m)
        return nuevo("y" if op == "and" else "o", **{c: hijo(o) for c, o in zip(_LETRAS, operandos)})
    if op == "grupo":
        return nuevo("par", a=hijo(m["operands"][0]))
    if op in ("not", "rise", "fall"):
        return nuevo({"not": "no", "rise": "sube", "fall": "baja"}[op], a=hijo(m["operands"][0]))
    if op == "delay":
        t1, a, t2 = m["operands"]
        if a["operator"] == "grupo":  # el paréntesis de `3s/(…)` es de la escritura de «temporizar»; uno más sería un «( )»
            a = a["operands"][0]
        d1, d2 = _duracion(t1), _duracion(t2)
        return texto() if d1 is None or d2 is None else nuevo("temp", t1=d1, t2=d2, a=hijo(a))
    if op in CMP.values():
        izq, der = m["operands"]
        op_txt = {v: k for k, v in CMP.items()}[op]
        val_der = ("true" if der["literal"]["value"] else "false") if der["operator"] == "lit" \
            and der["literal"]["type"] == "bool" else _crudo_de(der)
        nombre = izq["reference"] if izq["operator"] == "ref" else None
        if nombre == HUECO or (nombre in variables and variables[nombre][1] != "bool"):
            return nuevo("cmp", n=None if nombre == HUECO else nombre, op=op_txt, v=val_der)
        if izq["operator"] in ("add", "sub", "mul", "div", "neg", "grupo"):
            return nuevo("cmp", n=None, izq=_crudo_de(izq), op=op_txt, v=val_der)
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
        return _desde_significado(_analizar(nucleo), variables, etapas)
    except ParseError as e:
        raise ValueError(re.sub(r"\s*\(posición \d+\)$", "", str(e)).replace(HUECO, "?")) from e
    except Exception as e:  # noqa: BLE001 - un texto a medias no debe romper la interfaz
        raise ValueError(str(e).replace(HUECO, "?")) from e


_ARIT_OP = {"add": "+", "sub": "-", "mul": "*", "div": "/"}


def _desde_valor(m: dict[str, Any], variables: dict[str, tuple[str, str]], etapas: list[str]) -> dict[str, Any] | None:
    """Significado de un valor numérico -> árbol de bloques de valor (número, variable numérica, operación)."""
    op = m["operator"]
    texto = lambda: nuevo("texto", s=_crudo_de(m))  # noqa: E731
    if op == "lit":
        return nuevo("num", v=_crudo_de(m)) if m["literal"]["type"] != "bool" else texto()
    if op == "neg" and m["operands"][0]["operator"] == "lit" and m["operands"][0]["literal"]["type"] != "bool":
        return nuevo("num", v="-" + _crudo_de(m["operands"][0]))
    if op == "ref":
        nombre = m["reference"]
        if nombre == HUECO:
            return None
        return nuevo("vnum", n=nombre) if nombre in variables and variables[nombre][1] != "bool" else texto()
    if op == "grupo":
        return nuevo("par", a=_desde_valor(m["operands"][0], variables, etapas))
    if op in _ARIT_OP:
        a, b = m["operands"]
        return nuevo("ar", op=_ARIT_OP[op], a=_desde_valor(a, variables, etapas), b=_desde_valor(b, variables, etapas))
    return texto()


def texto_a_arbol_valor(texto: str, variables: dict[str, tuple[str, str]], etapas: list[str]) -> dict[str, Any] | None:
    """Texto de un valor numérico (`CT + 1`, `5`, `CT * 2 - 1`) -> árbol de bloques de valor (vacío: sin raíz). Un «?» es
    un hueco. Si no se puede analizar, lanza ValueError con el motivo, breve."""
    t = texto.strip()
    if not t:
        return None
    t = re.sub(r"`[^`]*`|\?", lambda m: HUECO if m.group(0) == "?" else m.group(0), t)
    try:
        nucleo = a_nucleo(t, _etiquetas(etapas), variables.keys(), False)
        return _desde_valor(_analizar(nucleo), variables, etapas)
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
    if n["k"] == "ar":
        return 5 if n["op"] in "+-" else 6
    if n["k"] == "num" and n["v"].startswith("-"):
        return 7
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
    if k in ("y", "o"):  # el primer operando, a su precedencia; los demás, a una más (un «o» dentro de un «o» va entre paréntesis)
        req = 2 if k == "y" else 1
        return (" AND " if k == "y" else " OR ").join(_t(n[c], req if i == 0 else req + 1) for i, c in enumerate(hijos(n)))
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
        lado_izq = n.get("izq") or (_citar(n["n"]) if n.get("n") else "?")
        val_der = (n.get("v") or "").strip() or "?"
        return f"{lado_izq} {n['op']} {val_der}"
    if k == "num":
        return n["v"].strip() or "0"
    if k == "vnum":
        return _citar(n["n"]) if n["n"] else "?"
    if k == "par":  # el bloque «( )»: siempre se escribe con sus paréntesis
        return f"({_t(n['a'])})"
    if k == "ar":  # izquierda a su precedencia; derecha a una más (a - (b - c) lleva paréntesis)
        pr = 5 if n["op"] in "+-" else 6
        return f"{_t(n['a'], pr)} {n['op']} {_t(n['b'], pr + 1)}"
    return n["s"].strip() or "?"


def arbol_a_texto(n: dict[str, Any] | None) -> str:
    """Árbol -> texto en la notación del usuario, con paréntesis solo donde la precedencia lo exige (OR < AND < NOT <
    comparación) y en el operando derecho de igual precedencia; los huecos, como «?»."""
    return "" if n is None else _t(n)


# -- dibujo ------------------------------------------------------------------------------------------------
# Las fichas de la maqueta v3 (E8): una booleana es una ficha con chaflán de 45° y una barra de 4 px del color de su origen
# (entrada, salida, etapa o memoria); una numérica, una cápsula con su punto de origen; la comparación va entre corchetes; la
# constante, hundida; «temporizar», un contenedor discontinuo con su insignia (t/X, X/t); «y» y «o», contenedores sobrios con un
# conector de su color entre un operando y el siguiente. Cambia el dibujo, no el modelo: los huecos, las rutas y los bloques son
# los de siempre.
COLORES = {"entrada": estilo.ACENTO, "salida": estilo.SIMULACION, "interna": estilo.PAPEL_MEMORIA,
           "etapa": estilo.EDICION,
           "operador": "#486078", "comparacion": "#0369a1", "tiempo": "#b45309", "texto": "#6B7280", "error": estilo.ERROR,
           "y": "#16263a", "o": "#075985",
           "constante": "#4a5b6e"}
CATEGORIAS_BANDA = (("operador", "Operadores"), ("tiempo", "Temp."), ("comparacion", "Comp."),
                    ("constante", "Const."))
_PAPEL_CAT = {"input": "entrada", "output": "salida", "internal": "interna"}
PADX, PADX_PILA, PADV, GAP, FILA = 6, 6, 4, 6, 6
ALTO = 21
HUECO_W, HUECO_H = 34, 24
PAREN_W = 9
PAD_PAR, GAP_PAR = 7, 4
SANGRIA = {"no": 8, "sube": 8, "baja": 8, "temp": 8}
CHAFLAN = 5
BARRA = 5
RELLENO_FICHA = 7
ANCHO_MAX_FICHA = 240
R_PIEZA = 4
MARGEN = 12
MIME = "application/x-grafcet-bloque"
MIME_FORMULA = "application/x-grafcet-formula"
MIME_TIPO = "application/x-grafcet-formula-tipo"
_ARRASTRE = {"resuelto": False}


def alto_ficha() -> int:
    """Alto de una ficha en el carril: 29 px a escala normal (maqueta 2.0.1)."""
    return 29 if estilo.ESCALA == "normal" else 31


def ficha_cadena(n: dict[str, Any] | None) -> tuple[list[str], dict[str, Any] | None] | None:
    """Si el bloque se dibuja como **una sola ficha** con sus modificadores: (los modificadores de fuera adentro, la variable o etapa de
    dentro o None si es un hueco pendiente). Solo si lleva como mucho un NOT y un flanco; con más (una fórmula guardada así) o sobre otra
    cosa que una variable o una etapa, se dibuja como contenedor. Un hueco sin modificadores no es una ficha."""
    mods: list[str] = []
    while n is not None and n["k"] in MODIFICADORES:
        mods.append(n["k"])
        n = n["a"]
    if (n is None and not mods) or (n is not None and n["k"] not in ("var", "etapa")):
        return None
    if mods.count("no") > 1 or sum(m != "no" for m in mods) > 1:
        return None
    return mods, n


class _Pieza:
    """Una pieza ya medida de un bloque: texto, desplegable o campo."""
    __slots__ = ("tipo", "clave", "texto", "vacio", "w", "h", "completo", "ruta", "extra")

    def __init__(self, tipo: str, clave: str, texto: str, vacio: bool, w: float, h: float, completo: str = "",
                 ruta: tuple | None = None, extra: Any = None) -> None:
        self.tipo, self.clave, self.texto, self.vacio, self.w, self.h = tipo, clave, texto, vacio, w, h
        self.completo = completo  # el texto entero, si el que se ve está recortado con «…» (sale en la ayuda emergente)
        self.ruta = ruta  # la ruta del bloque al que responde (si no es el de la caja que la contiene: una ficha con modificadores)
        self.extra = extra  # la letra de origen de una ficha con su color: (letra, color)


class _Caja:
    """Un bloque (o un hueco) ya medido, con sus piezas y cajas hijas colocadas dentro: (x, y, pieza o caja)."""

    def __init__(self, nodo: dict[str, Any] | None, ruta: tuple, w: float, h: float, cat: str = "") -> None:
        self.nodo, self.ruta, self.w, self.h, self.cat = nodo, ruta, w, h, cat
        self.items: list[tuple[float, float, Any]] = []
        self.fantasmas: list[tuple[QRectF, tuple, dict[str, Any]]] = []  # operaciones en línea: sin dibujo propio, pero con sitio
        self.sin_fondo = False  # no pinta su fondo (el de fuera ya los rodea): una operación dentro de un paréntesis
        self.forma = ""  # cómo se dibuja: ficha, hundida, capsula, pendiente, texto, y, o, temp, cadena, par, ar
        self.destino = ruta  # el sitio que recibe lo que se suelta encima (en una ficha con modificadores, la variable de dentro)
        self.mods: list[str] = []  # los modificadores de una ficha o de una cadena, de fuera adentro
        self.negada = ""  # una ficha con NOT: «todo» si la barra cubre también el flanco, «nombre» si solo la variable


class Motor:
    """Mide y dibuja bloques. Un bloque se dibuja en línea si cabe; si no, «y»/«o» apilan primer operando, rótulo y
    segundo operando, y los que envuelven ponen su hijo debajo, con sangría. `fuente()` da las variables
    {nombre: (papel, tipo)} y las etapas (en notación X) del modelo."""

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]]) -> None:
        self.fuente = fuente
        self.vars: dict[str, tuple[str, str]] = {}
        self.etapas: list[str] = []
        self.resaltar_huecos = False  # los huecos vacíos de una fórmula a medias se remarcan (en gris azulado, no en rojo)
        # La letra de las fichas lleva su familia explícita: con `QFont()` (la de la plataforma) se medía con una y se pintaba con
        # otra (en el pintor, el dispositivo le pone la de la hoja de estilo) y el texto se salía de la ficha: «ʼin», «narch».
        self.f = QFont(estilo.FUENTE)
        self.f.setPixelSize(12)
        self.fb = QFont(self.f)
        self.fb.setBold(True)
        self.fs = QFont(self.f)  # el nombre de una variable: seminegrita, como la maqueta
        self.fs.setWeight(QFont.Weight.DemiBold)
        self.fm = QFont(estilo.FUENTE_MONO)  # cifras, insignias y campos
        self.fm.setPixelSize(12)
        self.fm.setBold(True)
        self.fg = QFont(self.fm)
        self.fg.setPixelSize(14)
        self.fp = QFont(self.fm)  # el paréntesis de un temporizador
        self.fp.setPixelSize(17)
        self.m, self.mb, self.ms = QFontMetricsF(self.f), QFontMetricsF(self.fb), QFontMetricsF(self.fs)
        self.mm, self.mg, self.mp = QFontMetricsF(self.fm), QFontMetricsF(self.fg), QFontMetricsF(self.fp)
        # la letra de cada estilo de texto suelto: (fuente, medidas, ancho extra de la caja que lo lleva)
        self._est = {"": (self.fb, self.mb, 0), "y": (self.fg, self.mg, 14), "o": (self.fg, self.mg, 14),
                     "barra": (self.fg, self.mg, 0), "pp": (self.fp, self.mp, 0), "br": (self.fg, self.mg, 0),
                     "op": (self.fg, self.mg, 14), "ins": (self.fm, self.mm, 12), "insw": (self.fm, self.mm, 12),
                     "pf": (self.fm, self.mm, 10), "pend": (self.fb, self.mb, 0), "const": (self.fg, self.mg, 0)}
        self.nat: dict[tuple, float] = {}
        self.conectores: list[tuple[QRectF, tuple, str, int]] = []
        self.botones = False  # sin botón «+»: las fichas se añaden directamente al carril
        self.fijo = False  # en el catálogo: fila plana (.var-row) sin chaflán ni desplegable
        self.activo: tuple | None = None
        self.seleccionados: set[tuple] = set()
        self.destino_par: tuple | None = None
        self.hover_ruta: tuple | None = None
        self.valor_modo: bool = False

    def reiniciar(self) -> None:
        self.vars, self.etapas = self.fuente()
        self.nat = {}
        self.recortadas: list[tuple[QRectF, str]] = []  # (sitio, texto entero) de las piezas con el texto recortado
        self.conectores = []  # (sitio, ruta del contenedor, clave 'y'/'o'/'op', índice del conector)

    # -- qué lleva cada bloque
    def elementos(self, n: dict[str, Any]) -> list[tuple]:
        k = n["k"]
        visible = etapa_visible(n["n"]) if k == "etapa" else n.get("n")  # (una etapa se ve «X1», «X0fsd», como en la fórmula y en el dibujo)
        if k in ("var", "etapa", "vnum") and self.fijo and n["n"]:
            return [("txt", "", visible)]
        if k in ("var", "etapa"):
            return [("drop", "n", visible or "elegir")]
        if k == "const":
            return [("txt", "const", str(n["v"]))]
        if k in ("y", "o"):
            hs = hijos(n)
            out: list[tuple] = []
            for i, c in enumerate(hs):
                if i:
                    out.append(("txt", k, "·" if k == "y" else "+", i - 1))
                out.append(("hijo", c))
            return out
        if k in MODIFICADORES:  # una cadena de modificadores sobre algo que no es una variable: sus insignias y, a su lado, lo que modifica
            mods, _ = self._cadena(n)
            return [("mod", m, {"no": "NOT", "sube": "↑", "baja": "↓"}[m]) for m in mods] + [("hijo", ("a",) * len(mods))]
        if k == "temp":
            base = _efectivo(n["a"])
            parens = not (_atomo(base) or (base is not None and base["k"] in MODIFICADORES and _atomo(base["a"])))
            return ([("campo", "t1", n["t1"], "t1"), ("txt", "barra", "/")]
                    + ([("txt", "pp", "(")] if parens else []) + [("hijo", "a")] + ([("txt", "pp", ")")] if parens else [])
                    + [("txt", "barra", "/"), ("campo", "t2", n["t2"], "t2")])
        if k == "cmp":
            op_v = OP_VISIBLE.get(n["op"], n["op"])
            if _cmp_solo_lectura(n):
                izq_txt = n.get("izq") or (etapa_visible(n["n"]) if n.get("n") in self.etapas else n.get("n")) or "?"
                der_txt = (n.get("v") or "").replace(".", ",") or "0"
                return [("txt", "br", "["), ("txt", "ro", f"{izq_txt} {op_v} {der_txt}"), ("txt", "br", "]")]
            val_vis = (n.get("v") or "").replace(".", ",")
            return [("txt", "br", "["), ("drop", "n", n["n"] or "elegir"), ("drop", "op", op_v),
                    ("campo", "v", val_vis, "Núm"), ("txt", "br", "]")]
        if k == "num":
            return [("campo", "v", n["v"], "0")]
        if k == "vnum":
            return [("txt", "nom", n["n"] or "elegir")] if not self.fijo else [("txt", "", n["n"] or "elegir")]
        if k == "ar":
            return self._plano(n)[0]
        if k == "par":
            return [("paren", "izq", "("), ("hijo", "a"), ("paren", "der", ")")]
        return [("campo", "s", n["s"], "texto")]

    @staticmethod
    def _cadena(n: dict[str, Any] | None) -> tuple[list[str], dict[str, Any] | None]:
        """Los modificadores de fuera adentro y el bloque (o el hueco) que modifican."""
        mods: list[str] = []
        while n is not None and n["k"] in MODIFICADORES:
            mods.append(n["k"])
            n = n["a"]
        return mods, n

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
        if k == "num":
            return "comparacion"
        if k == "vnum":
            v = self.vars.get(n["n"]) if n["n"] else None
            return "error" if n["n"] and v is None else _PAPEL_CAT.get(v[0], "texto") if v else "interna"
        if k == "ar":
            return "operador"
        if k == "temp":
            return "tiempo"
        if k == "const":
            return "constante"
        if k == "texto":
            return "error" if _SIMPLE.fullmatch(n["s"]) else "texto"
        return k if k in ("y", "o") else "operador"

    # -- medidas
    def pieza(self, e: tuple, maxw: float = 100000) -> _Pieza:
        tipo = e[0]
        if tipo == "txt":
            fuente, medidas, extra = self._est.get(e[1], self._est[""])
            vis = medidas.elidedText(e[2], Qt.TextElideMode.ElideRight, maxw) if maxw < 100000 else e[2]
            w = max(22.0, medidas.horizontalAdvance(vis) + extra) if e[1] in ("y", "o", "op") else medidas.horizontalAdvance(vis) + extra
            h = 22.0 if e[1] in ("y", "o", "op") else ALTO
            return _Pieza("txt", e[1], vis, False, w, h, e[2] if vis != e[2] else "",
                          extra=e[3] if len(e) > 3 else None)
        if tipo == "boton":
            return _Pieza("boton", e[1], e[2], False, 22, 22)
        if tipo == "mod":  # la insignia de un flanco (↑, ↓) o de una negación sobre una cadena
            return _Pieza("mod", e[1], e[2], False, max(19.0, self.mm.horizontalAdvance(e[2]) + 10), 19.0)
        if tipo == "paren":
            return _Pieza("paren", e[1], e[2], False, PAREN_W, 18)
        texto = e[2] or (e[3] if tipo == "campo" else "")
        vacio = tipo == "campo" and not e[2]
        if tipo == "campo":
            vis = self.mm.elidedText(texto, Qt.TextElideMode.ElideRight, max(maxw - 14, 20))
            min_w = 38.0 if e[1] in ("t1", "t2") else 40.0
            return _Pieza(tipo, e[1], vis, vacio, max(min_w, self.mm.horizontalAdvance(vis) + 12), ALTO, texto if vis != texto else "")
        metricas = self.mm if e[1] == "op" else self.ms
        extra = 14 if e[1] == "op" else 16
        vis = metricas.elidedText(texto, Qt.TextElideMode.ElideRight, max(maxw - extra, 20))
        return _Pieza(tipo, e[1], vis, vacio, metricas.horizontalAdvance(vis) + extra + (6 if e[1] == "op" else 0), ALTO,
                      texto if vis != texto else "")

    def natural(self, n: dict[str, Any] | None, ruta: tuple) -> float:
        if n is None:
            return HUECO_W
        if ruta not in self.nat:
            if n["k"] == "no" and n["a"] is not None and n["a"]["k"] in ("par", "temp", "cmp"):
                w = self.natural(n["a"], ruta + ("a",))
            elif n["k"] == "par":
                extra_caret = 8.0 if ruta == self.destino_par else 0.0
                inner_w = 22.0 if n["a"] is None else self.natural(n["a"], ruta + ("a",))
                w = 2 * PAD_PAR + 2 * PAREN_W + 2 * GAP_PAR + inner_w + extra_caret
            elif n["k"] in ("y", "o"):
                ops, cons = a_lista(n)
                rutas_ops = _rutas_lista(n, ())
                ws = [self.natural(op, ruta + ro) for op, ro in zip(ops, rutas_ops)]
                w = sum(ws) + len(cons) * 22.0 + GAP * (len(ws) + len(cons) - 1)
            elif n["k"] == "temp":
                w = self._caja_temp(n, ruta, 10 ** 6).w
            elif self._es_simple(n):
                w = self._caja_simple(n, ruta, 10 ** 6).w
            elif n["k"] == "ar":
                elems, _ = self._plano(n)
                ws = [self.natural(*self._sub(n, e[1], ruta)) if e[0] == "hijo" else self.pieza(e).w for e in elems]
                w = sum(ws) + GAP * (len(ws) - 1)
            else:
                ws = [self.natural(*self._sub(n, e[1], ruta)) if e[0] == "hijo" else self.pieza(e).w for e in self.elementos(n)]
                w = 2 * PADX + sum(ws) + GAP * (len(ws) - 1)
            self.nat[ruta] = w
        return self.nat[ruta]

    @staticmethod
    def _es_simple(n: dict[str, Any]) -> bool:
        """Si el bloque se dibuja como una ficha o una cápsula de una sola fila (sin bloques dentro)."""
        return n["k"] in ("const", "cmp", "num", "vnum", "texto") or ficha_cadena(n) is not None

    def _caja_lista(self, n: dict[str, Any], ruta: tuple, ancho: float) -> _Caja:
        """Flujo plano de operandos separados por botones conectores cuadrados `·` / `+` (sin caja contenedora)."""
        ops, cons = a_lista(n)
        rutas_ops = _rutas_lista(n, ())
        c = _Caja(n, ruta, 0, 0, self.categoria(n))
        c.forma = n["k"]
        c.sin_fondo = True
        partes: list[Any] = []
        interior = max(ancho, 40.0)
        for i, (op, ro) in enumerate(zip(ops, rutas_ops)):
            if i > 0:
                con_k = cons[i - 1]
                partes.append(self.pieza(("txt", con_k, "·" if con_k == "y" else "+", i - 1)))
            r_op = ruta + ro
            partes.append(self.caja(op, r_op, min(self.natural(op, r_op), interior)))
        lineas: list[list[Any]] = [[]]
        x = 0.0
        for p in partes:
            if lineas[-1] and x + p.w > interior:
                lineas.append([])
                x = 0.0
            lineas[-1].append(p)
            x += p.w + GAP
        y, derecha = 0.0, 0.0
        for linea in lineas:
            h = max(p.h for p in linea)
            x = 0.0
            for p in linea:
                c.items.append((x, y + (h - p.h) / 2, p))
                x += p.w + GAP
            derecha = max(derecha, x - GAP)
            y += h + FILA
        c.h, c.w = max(0.0, y - FILA), derecha
        return c

    def _caja_temp(self, n: dict[str, Any], ruta: tuple, ancho: float) -> _Caja:
        """Temporizador en ficha achaflanada: `[t1] / [hueco o expresión] / [t2]`."""
        alto = alto_ficha()
        base = n["a"]
        c = _Caja(n, ruta, 0, 0, "tiempo")
        c.forma = "ficha"
        p_t1 = self.pieza(("campo", "t1", n["t1"], "t1"))
        p_s1 = self.pieza(("txt", "barra", "/"))
        p_s2 = self.pieza(("txt", "barra", "/"))
        p_t2 = self.pieza(("campo", "t2", n["t2"], "t2"))
        fijo = 2 * RELLENO_FICHA + p_t1.w + p_s1.w + p_s2.w + p_t2.w + 12
        hijo = self.caja(base, ruta + ("a",), max(ancho - fijo, 40.0))
        partes = [p_t1, p_s1, hijo, p_s2, p_t2]
        c.h = max(alto, max(p.h for p in partes) + 6)
        x = float(RELLENO_FICHA)
        for p in partes:
            c.items.append((x, (c.h - p.h) / 2, p))
            x += p.w + 3
        c.w = x - 3 + RELLENO_FICHA
        return c

    def caja(self, n: dict[str, Any] | None, ruta: tuple, ancho: float) -> _Caja:
        if n is None:
            return _Caja(None, ruta, HUECO_W, HUECO_H)
        if n["k"] == "no" and n["a"] is not None and n["a"]["k"] in ("par", "temp", "cmp"):
            inner_k = n["a"]["k"]
            if inner_k == "par":
                c = self._caja_par(n["a"], ruta + ("a",), ancho)
            elif inner_k == "temp":
                c = self._caja_temp(n["a"], ruta + ("a",), ancho)
            else:
                c = self._caja_simple(n["a"], ruta + ("a",), ancho)
            for _x, _y, it in c.items:
                if isinstance(it, _Pieza) and it.ruta is None:
                    it.ruta = ruta + ("a",)
            c.ruta, c.nodo, c.negada = ruta, n, "todo"
            return c
        if n["k"] == "par":
            return self._caja_par(n, ruta, ancho)
        if n["k"] in ("y", "o"):
            return self._caja_lista(n, ruta, ancho)
        if n["k"] == "ar":
            return self._caja_ar(n, ruta, ancho)
        if n["k"] == "temp":
            return self._caja_temp(n, ruta, ancho)
        if self._es_simple(n):
            return self._caja_simple(n, ruta, ancho)
        elems = self.elementos(n)
        c = _Caja(n, ruta, 0, 0, self.categoria(n))
        c.forma = "cadena" if n["k"] in MODIFICADORES else n["k"]
        if n["k"] in MODIFICADORES:
            c.mods = self._cadena(n)[0]
        if self.natural(n, ruta) <= ancho:  # todo en una fila
            x, partes = PADX, []
            for e in elems:
                p = self.caja(*self._sub(n, e[1], ruta), self.natural(*self._sub(n, e[1], ruta))) if e[0] == "hijo" \
                    else self.pieza(e)
                partes.append((x, p))
                x += p.w + GAP
            c.h = max(p.h for _, p in partes) + 2 * PADV
            c.w = x - GAP + PADX
            c.items = [(x, (c.h - p.h) / 2, p) for x, p in partes]
            return c
        px = PADX_PILA
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
                h = self.caja(*self._sub(n, e[1], ruta), interior - sangria)
                c.items.append((px + sangria, y, h))
                derecha = max(derecha, px + sangria + h.w)
                y += h.h + FILA
            else:
                grupo.append(self.pieza(e, interior))
        vaciar()
        c.h, c.w = y - FILA + PADV, derecha + px
        return c

    def _caja_simple(self, n: dict[str, Any], ruta: tuple, ancho: float) -> _Caja:
        """Una ficha, constante, comparación, cápsula numérica o fila plana del catálogo."""
        k = n["k"]
        alto = 26 if self.fijo else alto_ficha()
        if k in MODIFICADORES or k in ("var", "etapa"):
            return self._caja_ficha(n, ruta, min(ancho, ANCHO_MAX_FICHA), alto)
        if k == "vnum":
            ancho = min(ancho, ANCHO_MAX_FICHA)
        if self.fijo and k == "vnum":  # fila plana del catálogo numérico (.var-row)
            c = _Caja(n, ruta, 0, alto, self.categoria(n))
            c.forma = "catalogo"
            nombre = n.get("n") or "elegir"
            tipo_raw = self.vars.get(nombre, ("", ""))[1]
            etiqueta_tipo = {"int": "INT", "decimal": "DEC", "duration": "DUR"}.get(tipo_raw, "")
            ancho_tipo = (self.mb.horizontalAdvance(etiqueta_tipo) + 8) if etiqueta_tipo else 0.0
            x = 27.0
            disp = max(ancho - x - 8 - ancho_tipo, 24.0)
            vis = self.m.elidedText(nombre, Qt.TextElideMode.ElideRight, disp)
            p_nom = _Pieza("txt", "nom", vis, False, self.m.horizontalAdvance(vis), ALTO, nombre if vis != nombre else "")
            c.items.append((x, (alto - p_nom.h) / 2, p_nom))
            c.w = max(x + p_nom.w + 8 + ancho_tipo, ancho if ancho < 10 ** 5 else 0.0)
            if etiqueta_tipo:
                p_t = _Pieza("txt", "tagd", etiqueta_tipo, False, ancho_tipo - 4, ALTO, extra=(etiqueta_tipo, "#5b6b7d"))
                c.items.append((c.w - 6 - p_t.w, (alto - p_t.h) / 2, p_t))
            return c
        c = _Caja(n, ruta, 0, alto, self.categoria(n))
        elems = self.elementos(n)
        if k == "const":
            c.forma, x0 = "hundida", 11
        elif k == "cmp":
            c.forma, x0 = "ficha", RELLENO_FICHA
        elif k == "num":
            c.forma, x0 = "numconst", 4
        elif k == "vnum":
            c.forma, x0 = "capsula", 18  # punto azul + hueco
        else:
            c.forma, x0 = "texto", 6
        hueco = ancho - x0 - 10 if k == "vnum" else ancho - 2 * x0 - 6
        piezas = [self.pieza(e, max(hueco, 24) if k != "cmp" else 100000) for e in elems]
        x = float(x0)
        for p in piezas:
            c.items.append((x, (alto - p.h) / 2, p))
            x += p.w + (4 if k == "cmp" else 0)
        c.w = x - (4 if k == "cmp" else 0) + (x0 if k in ("const", "cmp", "texto", "num") else 10)
        return c

    def _caja_ficha(self, n: dict[str, Any], ruta: tuple, ancho: float, alto: float) -> _Caja:
        mods, hoja = self._cadena(n)
        destino = ruta + ("a",) * len(mods)
        c = _Caja(n, ruta, 0, alto, self.categoria(hoja) if hoja is not None else "operador")
        c.destino, c.mods = destino, mods
        flanco = next((m for m in mods if m != "no"), None)
        if hoja is None:
            c.forma = "pendiente"
            sufijo = " ".join({"no": "NOT", "sube": "↑", "baja": "↓"}[m] for m in mods)
            p1 = self.pieza(("txt", "pf", sufijo))
            p2 = self.pieza(("txt", "pend", "pulsa o arrastra variable…"), max(ancho - p1.w - 24, 40))
            c.items = [(8, (alto - p1.h) / 2, p1), (8 + p1.w + 6, (alto - p2.h) / 2, p2)]
            c.w = 8 + p1.w + 6 + p2.w + 8
            return c
        nombre = etapa_visible(hoja["n"]) if hoja["k"] == "etapa" else hoja["n"]
        if self.fijo and bool(hoja["n"]):  # catálogo izquierdo: fila plana (.var-row) sin chaflán ni letra derecha
            c.forma = "catalogo"
            x = 27.0  # 6 px margen + grip ⋮⋮ + 3 px barra + 7 px hueco
            disponible = max(ancho - x - 8, 24.0)
            vis = self.m.elidedText(nombre, Qt.TextElideMode.ElideRight, disponible)
            p = _Pieza("txt", "nom", vis, False, self.m.horizontalAdvance(vis), ALTO, nombre if vis != nombre else "", ruta=destino)
            c.items.append((x, (alto - p.h) / 2, p))
            c.w = max(x + p.w + 8, ancho if ancho < 10 ** 5 else 0.0)
            return c
        # Carril derecho: ficha achaflanada limpia (barra de color + opcional ↑/↓ + nombre sin letra E/S/M ni ▾)
        c.forma = "ficha"
        if "no" in mods:
            c.negada = "todo" if flanco is not None and mods.index("no") < mods.index(flanco) else "nombre"
        x = float(BARRA + RELLENO_FICHA)
        if flanco is not None:
            ins = _Pieza("mod", flanco, "↑" if flanco == "sube" else "↓", False, 19.0, 19.0, ruta=destino)
            c.items.append((x, (alto - ins.h) / 2, ins))
            x += ins.w + 5
        disponible = max(ancho - x - RELLENO_FICHA - 4, 20.0)
        texto = nombre or "elegir"
        vis = self.ms.elidedText(texto, Qt.TextElideMode.ElideRight, disponible)
        w = self.ms.horizontalAdvance(vis) + 2
        p = _Pieza("txt", "nom", vis, not nombre, w, ALTO, texto if vis != texto else "", ruta=destino, extra=("", COLORES.get(c.cat, estilo.TINTA)))
        c.items.append((x, (alto - p.h) / 2, p))
        c.w = x + p.w + RELLENO_FICHA + 2
        return c

    def _caja_par(self, n: dict[str, Any], ruta: tuple, ancho: float) -> _Caja:
        """Grupo `( … )` recursivo con tinte azulado suave, paréntesis altos y caret turquesa si es el destino activo."""
        clave = ruta + ("a",)
        es_dest = ruta == self.destino_par
        caret_w = 8.0 if es_dest else 0.0
        interior = max(ancho - 2 * PAD_PAR - 2 * PAREN_W - 2 * GAP_PAR - caret_w, 40)
        if n["a"] is None:
            h = _Pieza("boton", "vacio_par", "…", True, 22.0, 22.0)
            hw, hh = h.w, h.h
        else:
            h = self.caja(n["a"], clave, min(self.natural(n["a"], clave), interior))
            h.sin_fondo = True
            hw, hh = h.w, h.h
        alto = max(hh, 29.0) + 2 * PADV
        c = _Caja(n, ruta, 2 * PAD_PAR + 2 * PAREN_W + 2 * GAP_PAR + hw + caret_w, alto, self.categoria(n))
        c.forma = "par"
        items: list[tuple[float, float, Any]] = [
            (PAD_PAR, (alto - max(hh, 22.0)) / 2, _Pieza("paren", "izq", "(", False, PAREN_W, max(hh, 22.0))),
            (PAD_PAR + PAREN_W + GAP_PAR, (alto - hh) / 2, h),
        ]
        x_der = PAD_PAR + PAREN_W + 2 * GAP_PAR + hw
        if es_dest:
            items.append((x_der, (alto - 18.0) / 2, _Pieza("txt", "caret", "|", False, 4.0, 18.0)))
            x_der += caret_w
        items.append((x_der, (alto - max(hh, 22.0)) / 2, _Pieza("paren", "der", ")", False, PAREN_W, max(hh, 22.0))))
        c.items = items
        return c

    @staticmethod
    def _sub(n: dict[str, Any], clave: str | tuple, ruta: tuple) -> tuple[dict[str, Any] | None, tuple]:
        """El bloque (o hueco) de un hijo y su ruta. La clave es la del hijo, o un camino de claves (las operaciones
        aritméticas puestas en línea, ver `_plano`; los modificadores de una cadena)."""
        camino = clave if isinstance(clave, tuple) else (clave,)
        return obtener(n, camino), ruta + camino

    @staticmethod
    def _prec_ar(n: dict[str, Any]) -> int:
        return 5 if n["op"] in "+-" else 6

    def _plano(self, n: dict[str, Any]) -> tuple[list[tuple], list[tuple]]:
        """Los elementos de una operación aritmética, con puestas en línea las operaciones encadenadas que, escritas, no
        llevan paréntesis (la de la izquierda de igual o mayor precedencia, la de la derecha de mayor): `a - b + c` se ve
        «a − b + c», de izquierda a derecha, y no con bloques uno dentro de otro. Una que sí los lleva queda como un bloque
        dentro. Devuelve los elementos (`("hijo", camino)` o `("txt", "op", operador)`) y las operaciones en línea
        (camino, nodo, primer elemento, último + 1)."""
        elems: list[tuple] = []
        fantasmas: list[tuple] = []

        def rec(m: dict[str, Any], camino: tuple) -> None:
            pr, desde = self._prec_ar(m), len(elems)
            for clave, req in (("a", pr), ("b", pr + 1)):
                if clave == "b":
                    idx_op = sum(1 for x in elems if x[0] == "txt" and x[1] == "op")
                    elems.append(("txt", "op", OP_ARIT[m["op"]], idx_op))
                h = m[clave]
                if h is not None and h["k"] == "ar" and self._prec_ar(h) >= req:
                    rec(h, camino + (clave,))
                else:
                    elems.append(("hijo", camino + (clave,)))
            if camino:
                fantasmas.append((camino, m, desde, len(elems)))
        rec(n, ())
        return elems, fantasmas

    def _caja_ar(self, n: dict[str, Any], ruta: tuple, ancho: float) -> _Caja:
        """Flujo plano de operandos aritméticos separados por botones conectores (+, −, ×, ÷), sin caja externa."""
        elems, fantasmas = self._plano(n)
        c = _Caja(n, ruta, 0, 0, self.categoria(n))
        c.forma = "ar"
        c.sin_fondo = True
        interior = max(ancho, 40.0)
        partes: list[Any] = []
        for e in elems:
            if e[0] == "hijo":
                nodo, r = self._sub(n, e[1], ruta)
                partes.append(self.caja(nodo, r, min(self.natural(nodo, r), interior)))
            else:
                partes.append(self.pieza(e))
        unidades: list[list[int]] = []
        for i, e in enumerate(elems):
            if unidades and elems[unidades[-1][-1]][0] == "txt":
                unidades[-1].append(i)
            else:
                unidades.append([i])
        lineas: list[list[int]] = [[]]
        x = 0.0
        for u in unidades:
            ancho_u = sum(partes[i].w for i in u) + GAP * (len(u) - 1)
            if lineas[-1] and x + ancho_u > interior:
                lineas.append([])
                x = 0.0
            lineas[-1].extend(u)
            x += ancho_u + GAP
        rects: dict[int, tuple[float, float, float, float]] = {}
        y, derecha = 0.0, 0.0
        for linea in lineas:
            h = max(partes[i].h for i in linea)
            x = 0.0
            for i in linea:
                p = partes[i]
                c.items.append((x, y + (h - p.h) / 2, p))
                rects[i] = (x, y + (h - p.h) / 2, p.w, p.h)
                x += p.w + GAP
            derecha = max(derecha, x - GAP)
            y += h + FILA
        c.h, c.w = max(0.0, y - FILA), derecha
        for camino, nodo, desde, hasta in fantasmas:
            rs = [rects[i] for i in range(desde, hasta)]
            x0, y0 = min(r[0] for r in rs) - 3, min(r[1] for r in rs) - 2
            x1, y1 = max(r[0] + r[2] for r in rs) + 3, max(r[1] + r[3] for r in rs) + 2
            c.fantasmas.append((QRectF(x0, y0, x1 - x0, y1 - y0), ruta + camino, nodo))
        return c

    # -- registro de lo que hay en cada sitio (para el ratón)
    def registrar(self, c: _Caja, ox: float, oy: float, bloques: list, piezas: list) -> None:
        bloques.append((QRectF(ox, oy, c.w, c.h), c.ruta, c.nodo))
        bloques.extend((r.translated(ox, oy), ruta, nodo) for r, ruta, nodo in c.fantasmas)
        for x, y, it in c.items:
            if isinstance(it, _Caja):
                self.registrar(it, ox + x, oy + y, bloques, piezas)
                continue
            if it.completo:
                self.recortadas.append((QRectF(ox + x, oy + y, it.w, it.h), it.completo))
            if it.tipo == "txt" and it.clave in ("y", "o", "op") and isinstance(it.extra, int):
                self.conectores.append((QRectF(ox + x, oy + y, it.w, it.h), c.ruta, it.clave, it.extra))
            if it.tipo not in ("txt", "paren"):
                piezas.append((QRectF(ox + x, oy + y, it.w, it.h), it.tipo, it.ruta or c.ruta, it.clave))

    # -- dibujo
    @staticmethod
    def poligono_ficha(r: QRectF) -> QPolygonF:
        """El contorno de una ficha: un rectángulo con los cuatro vértices cortados a 45°."""
        ch = min(CHAFLAN, r.height() / 2, r.width() / 2)
        return QPolygonF([QPointF(r.left() + ch, r.top()), QPointF(r.right() - ch, r.top()), QPointF(r.right(), r.top() + ch),
                          QPointF(r.right(), r.bottom() - ch), QPointF(r.right() - ch, r.bottom()),
                          QPointF(r.left() + ch, r.bottom()), QPointF(r.left(), r.bottom() - ch), QPointF(r.left(), r.top() + ch)])

    @staticmethod
    def trazo_seleccion(p: QPainter, r: QRectF, grosor: float = 2.4) -> None:
        """El contorno de lo seleccionado o de donde caería lo que se arrastra: el trazo del acento."""
        p.setPen(QPen(QColor(estilo.ACENTO), grosor))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 6, 6)

    def _fondo_hijo(self, padre: QColor | None) -> QColor:
        """Los contenedores anidados alternan dos fondos para distinguirse unos de otros."""
        return QColor(estilo.FONDO if padre is not None and QColor(padre) == QColor(estilo.SUPERFICIE_2) else estilo.SUPERFICIE_2)

    def pintar(self, p: QPainter, c: _Caja, ox: float, oy: float, padre: QColor | None = None,
               objetivo: tuple | None = None) -> None:
        r = QRectF(ox, oy, c.w, c.h)
        if c.nodo is None:
            if c.ruta != (0,):  # el hueco raíz vacío lo pinta AreaBloques._extra como `.rail-empty-hint`
                p.setPen(QPen(QColor(estilo.ACENTO if self.resaltar_huecos else estilo.BORDE_CONTROL), 1.8 if self.resaltar_huecos else 1.2,
                              Qt.PenStyle.DashLine))
                p.setBrush(QColor(estilo.ACENTO_SUAVE if self.resaltar_huecos else estilo.SUPERFICIE))
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), R_PIEZA, R_PIEZA)
        else:
            fondo = self._pintar_caja(p, c, r, padre)
            for x, y, it in c.items:
                if isinstance(it, _Caja):
                    self.pintar(p, it, ox + x, oy + y, fondo, objetivo)
                else:
                    self._pintar_pieza(p, it, QRectF(ox + x, oy + y, it.w, it.h), c)
        if objetivo is not None and (c.ruta == objetivo or c.destino == objetivo):  # el sitio donde caería lo que se arrastra
            self.trazo_seleccion(p, r.adjusted(-0.5, -0.5, 0.5, 0.5), 2.6)
        for fr, ruta, _ in c.fantasmas:  # una operación puesta en línea que recibiría lo arrastrado: se remarca su tramo
            if objetivo is not None and ruta == objetivo:
                self.trazo_seleccion(p, fr.translated(ox, oy), 2.6)

    def _estado_sel(self, ruta: tuple) -> str:
        """Estado visual de un bloque en el carril: 'multi', 'active' o ''."""
        if len(self.seleccionados) > 1 and ruta in self.seleccionados:
            return "multi"
        if ruta == self.activo or ruta in self.seleccionados:
            return "active"
        return ""

    def _pintar_caja(self, p: QPainter, c: _Caja, r: QRectF, padre: QColor | None) -> QColor | None:
        """El fondo y el contorno del bloque según el diseño 2.0.1."""
        forma, cat = c.forma, c.cat
        error = cat == "error"
        ra = r.adjusted(0.5, 0.5, -0.5, -0.5)
        sel = self._estado_sel(c.ruta)
        if forma == "catalogo":  # fila plana del catálogo izquierdo (.var-row)
            if c.ruta == self.hover_ruta:
                p.setPen(QPen(QColor("#cdd6e0"), 1))
                p.setBrush(QColor("#e4ecf3"))
                p.drawRoundedRect(ra, 4, 4)
            # grip ⋮⋮ (6 puntitos discretos)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#9aa9ba"))
            cy = r.center().y()
            for gx in (r.left() + 6.5, r.left() + 10.0):
                for gy in (cy - 3.5, cy, cy + 3.5):
                    p.drawEllipse(QPointF(gx, gy), 0.9, 0.9)
            # franja vertical de 3×14 px del color del origen
            p.setBrush(QColor(COLORES.get(cat, estilo.ACENTO)))
            p.drawRoundedRect(QRectF(r.left() + 17.5, cy - 7.0, 3.0, 14.0), 1.5, 1.5)
            return padre
        if forma in ("ficha", "hundida"):
            borde_col = (estilo.ERROR if error else "#075985" if sel == "multi"
                         else estilo.ACENTO if sel == "active" else "#aebfd1")
            fondo_col = (estilo.ERROR_FONDO if error else "#edf6fc" if sel == "multi"
                         else "#eef9f6" if sel == "active"
                         else "#f6f8fb" if forma == "hundida" else "#ffffff")
            p.setPen(QPen(QColor(borde_col), 1.5 if sel else 1.0))
            p.setBrush(QColor(fondo_col))
            contorno = self.poligono_ficha(ra)
            p.drawPolygon(contorno)
            # Franja lateral de color para variables y etapas booleanas
            if forma == "ficha" and c.nodo is not None and c.cat in ("entrada", "salida", "interna", "etapa"):
                camino = QPainterPath()
                camino.addPolygon(contorno)
                p.save()
                p.setClipPath(camino)
                p.fillRect(QRectF(r.left(), r.top(), BARRA, r.height()), QColor(COLORES[cat]))
                p.restore()
            if c.negada == "todo":  # barra superior sobre toda la ficha (NOT ↑x, NOT temp, NOT cmp)
                x_ini = r.left() + (BARRA + 5 if c.cat in ("entrada", "salida", "interna", "etapa") else 7)
                p.fillRect(QRectF(x_ini, r.top() + 3.0, max(4.0, r.right() - x_ini - 7.0), 1.8), QColor("#16263a"))
            return padre
        if forma == "numconst":  # constante numérica en el carril (`.num-const-wrap`)
            if sel:
                p.setPen(QPen(QColor("#075985" if sel == "multi" else estilo.ACENTO), 1.2))
                p.setBrush(QColor("#edf6fc" if sel == "multi" else "#eef9f6"))
                p.drawRoundedRect(ra, 14, 14)
            return padre
        if forma == "capsula":
            borde_col = (estilo.ERROR if error else "#075985" if sel == "multi"
                         else estilo.ACENTO if sel == "active" else "#96bdd6")
            fondo_col = (estilo.ERROR_FONDO if error else "#edf6fc" if sel == "multi"
                         else "#eef9f6" if sel == "active" else "#ffffff")
            p.setPen(QPen(QColor(borde_col), 1.5 if sel else 1.0))
            p.setBrush(QColor(fondo_col))
            p.drawRoundedRect(ra, 14, 14)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(COLORES.get(cat, estilo.TINTA_2)))
            p.drawEllipse(QPointF(r.left() + 10.5, r.center().y()), 3.0, 3.0)
            return padre
        if forma == "pendiente":
            p.setPen(QPen(QColor(estilo.ACENTO), 1.5, Qt.PenStyle.DashLine))
            p.setBrush(QColor(estilo.ACENTO_SUAVE))
            p.drawRoundedRect(ra, R_PIEZA, R_PIEZA)
            return padre
        if forma == "texto":
            p.setPen(QPen(QColor(estilo.ERROR if error else "#aebfd1"), 1))
            p.setBrush(QColor(estilo.ERROR_FONDO if error else "#f6f8fb"))
            p.drawRoundedRect(ra, R_PIEZA, R_PIEZA)
            return padre
        if c.sin_fondo:
            return padre
        if forma == "par":  # grupo entre paréntesis recursivo (`.paren-group`)
            es_dest = c.ruta == self.destino_par or (c.nodo is not None and c.nodo["k"] == "no" and c.ruta + ("a",) == self.destino_par)
            odd = padre is not None and padre == QColor(232, 240, 248, 184)
            if sel == "multi":
                fondo = QColor(232, 244, 252, 217)
                borde_col = "#075985"
            elif es_dest:
                fondo = QColor(235, 248, 246, 204)
                borde_col = estilo.ACENTO
            elif sel == "active":
                fondo = QColor(235, 248, 246, 204)
                borde_col = estilo.ACENTO_OSCURO
            elif self.valor_modo:
                fondo = QColor(229, 242, 250, 184)
                borde_col = "#9bc0da"
            else:
                fondo = QColor(223, 234, 245, 199) if odd else QColor(232, 240, 248, 184)
                borde_col = "#9db3ca" if odd else "#b3c4d6"
            radio = 14 if self.valor_modo else 6
            p.setPen(QPen(QColor(borde_col), 1.6 if (sel or es_dest) else 1.0))
            p.setBrush(fondo)
            p.drawRoundedRect(ra, radio, radio)
            if c.negada == "todo":  # NOT ( … ): barra sólida de 2.8 px en el borde superior
                p.fillRect(QRectF(r.left() + 2, r.top(), r.width() - 4, 2.8), QColor("#16263a"))
            return fondo
        fondo = self._fondo_hijo(padre)
        p.setPen(QPen(QColor("#b3c4d6"), 1))
        p.setBrush(fondo)
        p.drawRoundedRect(ra, 6, 6)
        if forma == "cadena" and "no" in c.mods:
            p.fillRect(QRectF(r.left() + 3, r.top(), r.width() - 6, 2.8), QColor("#16263a"))
        return fondo

    def _pintar_pieza(self, p: QPainter, it: _Pieza, r: QRectF, c: _Caja | None = None) -> None:
        tinta, borde = QColor("#16263a"), QColor("#b5c4d4")
        centro = Qt.AlignmentFlag.AlignCenter
        if it.tipo == "txt" and it.clave == "caret":  # cursor vertical turquesa dentro de un ( … ) activo
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(estilo.ACENTO))
            p.drawRoundedRect(QRectF(r.left() + 0.5, r.top(), 2.5, r.height()), 1.2, 1.2)
            return
        if it.tipo == "txt" and it.clave == "tagd":  # tipo numérico (INT / DEC) a la derecha en el catálogo
            f = QFont(self.f)
            f.setPixelSize(10)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(QColor(it.extra[1] if it.extra else "#5b6b7d"))
            p.drawText(r, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, it.texto)
            return
        if it.tipo == "txt" and it.clave == "nom":
            self._pintar_nombre(p, it, r, c, False)
            return
        if it.tipo == "txt":
            fuente = self._est.get(it.clave, self._est[""])[0]
            p.setFont(fuente)
            if it.clave in ("y", "o", "op"):  # botón conector cuadrado `.conn-btn` (`·`, `+`, `−`, `×`, `÷`)
                es_or = it.clave == "o"
                p.setPen(QPen(QColor("#93b5d1" if es_or else "#c1cedc"), 1))
                p.setBrush(QColor("#eef4fa" if es_or else "#e7eef5"))
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
                p.setPen(QColor("#075985" if es_or else "#16263a"))
            elif it.clave in ("ins", "insw", "pf"):
                aviso = it.clave == "insw"
                p.setPen(QPen(QColor(estilo.AVISO_BORDE), 1) if aviso else Qt.PenStyle.NoPen)
                p.setBrush(QColor(estilo.AVISO_FONDO if aviso else estilo.EDICION if it.clave == "ins" else estilo.SUPERFICIE))
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
                p.setPen(QColor(estilo.AVISO if aviso else "#FFFFFF" if it.clave == "ins" else estilo.TINTA))
            elif it.clave in ("barra", "pp", "br"):
                p.setPen(QColor("#5b6b7d"))
            elif it.clave == "pend":
                p.setPen(QColor(estilo.ACENTO_OSCURO))
            else:
                p.setPen(tinta)
            p.drawText(r, centro, it.texto)
            return
        if it.tipo == "paren":  # paréntesis curvos sobrios (`.paren-sym`)
            izq = it.clave == "izq"
            punta, panza = (r.right() - 2, r.left() + 1.5) if izq else (r.left() + 2, r.right() - 1.5)
            camino = QPainterPath(QPointF(punta, r.top() + 1))
            camino.cubicTo(QPointF(panza, r.top() + r.height() * 0.28), QPointF(panza, r.bottom() - r.height() * 0.28),
                           QPointF(punta, r.bottom() - 1))
            p.setPen(QPen(QColor("#5b6b7d"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(camino)
            return
        if it.tipo == "boton":  # `…` dentro de un grupo vacío (`.paren-add`)
            p.setPen(QPen(QColor("#8fa0b3"), 1, Qt.PenStyle.DashLine))
            p.setBrush(QColor(255, 255, 255, 224))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
            p.setFont(self.fb)
            p.setPen(QColor("#4a5b6e"))
            p.drawText(r, centro, it.texto)
            return
        if it.tipo == "mod":  # insignia turquesa `.mod-chip` (↑, ↓)
            p.setPen(QPen(QColor("#9fd4d0"), 1))
            p.setBrush(QColor("#e6f4f1"))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
            p.setFont(self.fm)
            p.setPen(QColor(estilo.ACENTO_OSCURO))
            p.drawText(r, centro, it.texto)
            return
        if it.tipo == "campo":  # pastilla editable in-situ (`.inline-input`, discontinua cuando está vacía)
            es_num_cmp = c is not None and c.nodo is not None and c.nodo["k"] == "cmp" and it.clave == "v"
            pen_style = Qt.PenStyle.DashLine if it.vacio else Qt.PenStyle.SolidLine
            borde_c = QColor("#96bdd6") if es_num_cmp else borde
            fondo_c = QColor("#ffffff" if es_num_cmp else "#fafcff" if it.vacio else "#f4f7fa")
            p.setPen(QPen(borde_c, 1, pen_style))
            p.setBrush(fondo_c)
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), r.height() / 2, r.height() / 2)
            f = QFont(self.fm)
            f.setBold(not it.vacio)
            p.setFont(f)
            p.setPen(QColor("#7b8a9c" if it.vacio else "#16263a"))
            p.drawText(r.adjusted(4, 0, -4, 0), centro, it.texto)
            return
        if it.clave == "op":  # operador de comparación en pastilla azul (`.mini-badge.cmp`)
            p.setPen(QPen(QColor("#7dd3fc"), 1))
            p.setBrush(QColor("#e0f2fe"))
            p.drawRoundedRect(r.adjusted(0.5, 1.5, -0.5, -1.5), 3, 3)
            p.setFont(self.fm)
            p.setPen(QColor("#075985"))
            p.drawText(QRectF(r.left() + 2, r.top(), r.width() - 12, r.height()), centro, it.texto)
            p.setFont(self.f)
            p.setPen(QColor("#075985"))
            p.drawText(QRectF(r.right() - 12, r.top(), 10, r.height()), centro, "▾")
            return
        self._pintar_nombre(p, it, r, c, True)

    def _pintar_nombre(self, p: QPainter, it: _Pieza, r: QRectF, c: _Caja | None, desplegable: bool) -> None:
        """Nombre limpio (sin letra E/S/M); sobrerrayado si está negado y ▾ solo en desplegables de temp/cmp."""
        x = r.left()
        es_cat = c is not None and c.forma == "catalogo"
        p.setFont(self.f if es_cat else self.fs)
        p.setPen(QColor(estilo.ERROR if c is not None and c.cat == "error" and c.forma in ("ficha", "capsula") else "#16263a"))
        fin = r.right() - (14 if desplegable else 0)
        texto = QRectF(x, r.top(), max(fin - x, 1), r.height())
        p.drawText(texto, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, it.texto)
        if c is not None and c.negada == "nombre":  # barra superior solo sobre el nombre de la variable
            ancho_texto = min(self.ms.horizontalAdvance(it.texto), texto.width())
            p.fillRect(QRectF(x, r.top() + 2.0, ancho_texto, 1.7), QColor("#16263a"))
        if desplegable:
            p.setFont(self.f)
            p.setPen(QColor("#64748b"))
            p.drawText(QRectF(r.right() - 14, r.top(), 12, r.height()), Qt.AlignmentFlag.AlignCenter, "▾")

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


GUIA = "Pulsa o arrastra variables desde la paleta izquierda para construir la fórmula…"
_REJILLA: list[QPixmap] = []


def _rejilla() -> QPixmap:
    """El mosaico de 16 px con un punto sutil (`#fbfdff` + `#d5dfe9`), como `.block-rail`."""
    if not _REJILLA:
        pm = QPixmap(16, 16)
        pm.fill(QColor("#fbfdff"))
        p = QPainter(pm)
        p.setPen(QColor("#d5dfe9"))
        p.drawPoint(1, 1)
        p.end()
        _REJILLA.append(pm)
    return _REJILLA[0]


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
    arrastrando = Signal(bool)  # empieza y termina el arrastre de un bloque de aquí (el área avisa de que soltarlo fuera lo quita)
    elegido = Signal(object)  # se pulsó un bloque (sin arrastrarlo): su nodo (el catálogo lo inserta en la fórmula)
    mueve = False  # arrastrar un bloque lo saca de aquí (el área); en la paleta, lo copia
    margen: int = MARGEN

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
        self._necesario = max([x + c.w for c, x, y in self._cajas] or [0]) + self.margen
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
            return [(etapa_visible(x), x) for x in dict.fromkeys(self.motor.etapas)]
        if clave == "op":
            return [(OP_VISIBLE[o], o) for o in OPERADORES_CMP]
        if k in ("cmp", "vnum"):
            return [(nom, nom) for nom, (_, t) in v.items() if t != "bool"]
        papel = (v[n["n"]][0] if n["n"] in v else None) or n.get("papel")
        return [(nom, nom) for nom, (r, t) in v.items() if r == papel and t == "bool"]

    def elegir(self, ruta: tuple, clave: str, valor: str) -> None:
        """Elige en el desplegable de un bloque (la variable, la etapa o el operador de una comparación)."""
        i, r = self._partir(ruta)
        nueva = copy.deepcopy(self._raices[i])
        n = obtener(nueva, r)
        if n is not None and n["k"] == "cmp" and _cmp_solo_lectura(n):
            return
        n[clave] = valor
        if n["k"] == "var" and valor in self.motor.vars:
            n["papel"] = self.motor.vars[valor][0]
        self._fijar(i, nueva)

    def editar_campo(self, ruta: tuple, clave: str, texto: str) -> bool:
        """Escribe en el campo de un bloque (t1 y t2 de «temporizar», el valor de una comparación, un texto). Un
        retardo que no es una duración, o un valor que no se puede analizar, se rechaza y se avisa."""
        i, r = self._partir(ruta)
        nueva = copy.deepcopy(self._raices[i])
        n = obtener(nueva, r)
        if n["k"] == "temp":
            d = normalizar_duracion(texto)
            if d is None:
                self.avisa.emit("Retardo no válido: escribe «3s», «500ms» o déjalo vacío.")
                return False
            n[clave] = d
        elif n["k"] == "num":
            v = texto.strip().replace(",", ".")
            if not re.fullmatch(r"-?\d+(?:\.\d+)?", v):
                self.avisa.emit("Escribe un número (por ejemplo 5 o 2.5).")
                return False
            n[clave] = v
        elif n["k"] == "cmp":
            if _cmp_solo_lectura(n) or clave != "v":
                return False
            t = texto.strip()
            if not t:
                n["v"] = ""
            else:
                self.motor.reiniciar()
                tipo_var = self.motor.vars.get(n.get("n") or "", ("", ""))[1]
                canon = t.replace(",", ".")
                if tipo_var == "int":
                    if not re.fullmatch(r"-?\d+", canon):
                        self.avisa.emit("Valor no válido: la variable es entera, escribe un número entero.")
                        return False
                elif not re.fullmatch(r"-?\d+(?:\.\d+)?", canon):
                    self.avisa.emit("Valor no válido: escribe un número (por ejemplo 10 o 2,5).")
                    return False
                n["v"] = canon
        else:
            n[clave] = texto.strip()
        motivo = self._validar(i, nueva)
        if motivo:
            self.avisa.emit(motivo)
            return False
        self._fijar(i, nueva)
        return True

    # -- dibujo
    def _fondo(self, p: QPainter) -> None:
        p.fillRect(self.rect(), QColor(estilo.SUPERFICIE))
        p.setPen(QPen(QColor(estilo.BORDE), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), estilo.R_M, estilo.R_M)

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
        """El sitio (hueco o bloque) más interior bajo el puntero: donde caería un bloque soltado ahí. Sobre una ficha con modificadores,
        la variable de dentro (o su hueco pendiente): lo soltado la sustituye y los modificadores se quedan."""
        self._calcular(self.width())
        dentro = [(r.width() * r.height(), ruta) for r, ruta, n in self._bloques if r.contains(pos)]
        return self._destino(min(dentro)[1]) if dentro else None

    def _destino(self, ruta: tuple) -> tuple:
        """El sitio que recibe lo soltado sobre el bloque de `ruta`: el mismo, salvo en una ficha con modificadores (se dibuja como una
        sola ficha), donde es la variable de dentro."""
        i, r = self._partir(ruta)
        try:
            n = obtener(self._raices[i], r)
        except (KeyError, IndexError):
            return ruta
        if n is None or n["k"] not in MODIFICADORES:
            return ruta
        ficha = ficha_cadena(n)
        return ruta if ficha is None else tuple(ruta) + ("a",) * len(ficha[0])

    def _ruta_arrastre(self, ruta: tuple) -> tuple:
        """Qué se lleva al arrastrar desde `ruta`: el bloque tal cual (en el área, una ficha con modificadores se lleva entera)."""
        return ruta

    def _completo_en(self, pos: QPointF) -> str:
        """El texto entero de la pieza recortada («…») que hay bajo el puntero, o vacío."""
        self._calcular(self.width())
        return next((t for r, t in self.motor.recortadas if r.contains(pos)), "")

    def event(self, ev: Any) -> bool:
        if ev.type() == QEvent.Type.ToolTip:
            texto = self._completo_en(QPointF(ev.pos()))
            if texto:
                mostrar_ayuda(ev.globalPos(), texto, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(ev)

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
        if (event.position() - pos).manhattanLength() < 6 or que is None or (es_pieza and que[1] == "boton"):
            return
        ruta = que[2] if es_pieza else que
        self._pulsado = None
        self._arrastrar(tuple(self._ruta_arrastre(tuple(ruta))))

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if self._pulsado is None:
            return
        _, que, es_pieza = self._pulsado
        self._pulsado = None
        if es_pieza:
            r, tipo, ruta, clave = que
            if tipo == "drop":
                self._menu(ruta, clave, r)
            elif tipo == "boton":
                self._boton(ruta, clave)
            elif tipo == "mod":
                self._modificador(ruta, clave)
            else:
                self._abrir_editor(r, ruta, clave)
        elif que is not None:
            self._pulsado_bloque(tuple(que))

    def _boton(self, ruta: tuple, clave: str) -> None:
        pass

    def _modificador(self, ruta: tuple, clase: str) -> None:
        pass

    def _pulsado_bloque(self, ruta: tuple) -> None:
        """Un clic sobre un bloque, sin pieza: en el catálogo, lo elige para insertarlo."""
        pass

    def _menu(self, ruta: tuple, clave: str, r: QRectF) -> None:
        i, rr = self._partir(ruta)
        n = obtener(self._raices[i], rr)
        if n is not None and n["k"] == "cmp" and _cmp_solo_lectura(n):
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: #ffffff; color: #16263a; border: 1px solid #7b8a9c; border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 4px 18px 4px 12px; border-radius: 4px; font-size: 12px; }}"
            f"QMenu::item:selected {{ background: #cfeee6; color: #095259; }}"
            f"QMenu::separator {{ height: 1px; background: #e2e8f0; margin: 4px 6px; }}"
        )
        ops = self.opciones_desplegable(n, clave)
        for texto, valor in ops:
            menu.addAction(texto, lambda v=valor: self.elegir(ruta, clave, v))
        if not ops:
            menu.addAction("(no hay ninguna: créala en el panel Variables)").setEnabled(False)
        menu.exec(self.mapToGlobal(r.bottomLeft().toPoint()))

    def _abrir_editor(self, r: QRectF, ruta: tuple, clave: str) -> None:
        i, rr = self._partir(ruta)
        ed = _Editor(self)
        nodo = obtener(self._raices[i], rr)
        val_ini = (nodo.get("v") or "").replace(".", ",") if (nodo["k"] == "cmp" and clave == "v") else nodo[clave]
        ed.setText(val_ini)
        ed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ed.setStyleSheet(
            f"QLineEdit {{ min-height: 0; max-height: 22px; padding: 0 5px; border: 1.5px solid {estilo.ACENTO}; "
            f"border-radius: 10px; background: #ffffff; color: #16263a; "
            f"font-family: {estilo.FAMILIA_MONO}; font-size: 12px; font-weight: 600; }}"
            f"QLineEdit:focus {{ min-height: 0; max-height: 22px; padding: 0 5px; border: 1.5px solid {estilo.ACENTO}; }}"
        )
        ed.setProperty("destino", (ruta, clave))
        ed.setGeometry(QRect(int(r.left()), int(r.top()), int(max(r.width() + 6, 46)), 22))
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
        if self.mueve:
            self.arrastrando.emit(True)
        try:
            ejecutar_arrastre(drag, self.window())
        finally:
            if self.mueve:
                self.arrastrando.emit(False)
        if self.mueve and not _ARRASTRE["resuelto"] and not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.quitar(tuple(r))  # soltado fuera del área: se quita
        self._pulsado = None
        self.invalidar()

    def quitar(self, ruta: tuple) -> None:
        pass


class PaletaBloques(_Superficie):
    """El catálogo izquierdo: filas planas limpias (.var-row) que se pulsan para insertar o se arrastran al carril."""
    margen: int = 6

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str = "",
                 columna: bool = False, valor: bool = False) -> None:
        super().__init__(fuente, grupo)
        self.motor.botones = False
        self.motor.fijo = True
        self.valor = valor
        self.clave = "vnum" if valor else "entrada"
        self.columna = columna
        self.una_fila = False
        self._filtro_texto = ""
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cargar(self.clave)

    def _fondo(self, p: QPainter) -> None:
        p.fillRect(self.rect(), QColor("#ffffff"))

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        b = self._bloque_en(event.position())
        if b != self.motor.hover_ruta:
            self.motor.hover_ruta = b
            self.update()

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        super().leaveEvent(event)
        if self.motor.hover_ruta is not None:
            self.motor.hover_ruta = None
            self.update()

    def filtrar_texto(self, texto: str) -> None:
        """Filtra la paleta numérica por texto (para el cuadro «Filtrar numéricas…»)."""
        self._filtro_texto = texto.strip().casefold()
        self.cargar(self.clave)

    def _maqueta(self, ancho: float) -> tuple[list[tuple[_Caja, float, float]], float]:
        margen = 6.0
        x, y, lh, out = margen, margen, 0.0, []
        for i, n in enumerate(self._raices):
            w_caja = (ancho - 2 * margen) if self.columna else min(self.motor.natural(n, (i,)), ancho - 2 * margen)
            c = self.motor.caja(n, (i,), w_caja)
            if x > margen and (self.columna or (not self.una_fila and x + c.w > ancho - margen)):
                x, y, lh = margen, y + lh + (2 if self.columna else GAP * 2), 0.0
            out.append((c, x, y))
            x += c.w + GAP * 2
            lh = max(lh, c.h)
        return out, y + lh + margen

    @staticmethod
    def _orden(nombre: str) -> list[Any]:
        """Orden natural y sin distinguir mayúsculas: I2 antes que I10; las etapas, por su número."""
        return [(0, int(x), "") if x.isdigit() else (1, 0, x.lower()) for x in re.split(r"(\d+)", nombre) if x]

    def cargar(self, clave: str) -> None:
        """Pone las filas del catálogo (entradas, salidas, memorias, etapas o variables numéricas)."""
        self.clave = clave
        self.motor.reiniciar()
        v, etapas = self.motor.vars, list(dict.fromkeys(self.motor.etapas))
        if clave == "vnum":
            numericas = sorted((nom for nom, (_, t) in v.items() if t != "bool"), key=self._orden)
            if self._filtro_texto:
                numericas = [nom for nom in numericas if self._filtro_texto in nom.casefold()]
            nodos = [nuevo("vnum", n=nom) for nom in numericas] or ([nuevo("vnum", n=None)] if not self._filtro_texto else [])
        elif clave in PAPEL:
            validas = sorted((nom for nom, (r, t) in v.items() if r == PAPEL[clave] and t == "bool"), key=self._orden)
            nodos = [var(nom, PAPEL[clave]) for nom in validas] or [var(None, PAPEL[clave])]
        else:
            por_numero = lambda x: (0, int(x[1:]), "") if re.fullmatch(r"X\d+", x) else (1, 0, x.lower())  # noqa: E731
            nodos = [nuevo("etapa", n=x) for x in sorted(etapas, key=por_numero)] or [nuevo("etapa", n=None)]
        self._raices = nodos
        self.invalidar()

    def _pulsado_bloque(self, ruta: tuple) -> None:
        i, r = self._partir(ruta)
        nodo = obtener(self._raices[i], r)
        if nodo is not None and (nodo.get("n") or nodo["k"] not in ("var", "etapa", "vnum")):
            self.elegido.emit(copy.deepcopy(nodo))

    def bloques(self) -> list[dict[str, Any]]:
        return copy.deepcopy([n for n in self._raices if n is not None])


class AreaBloques(_Superficie):
    """El área de trabajo: el árbol de bloques, con un hueco como raíz si está vacía. Recibe los bloques que se sueltan
    (de la paleta o de ella misma) y los arrastres de una pieza a otra. `modificado` se emite en cada cambio hecho
    con el ratón o con las operaciones de abajo; `poner_arbol` no lo emite."""
    modificado = Signal()
    seleccion_cambiada = Signal()  # se eligió o se dejó de elegir un bloque
    mueve = True

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str = "",
                 valor: bool = False) -> None:
        super().__init__(fuente, grupo)
        self.valor = valor  # el área de un valor numérico: su texto se lee con las reglas de los valores
        self.motor.valor_modo = valor
        self._raices = [None]
        self.previo: dict[str, Any] | None = None
        self._bloque_sel: tuple | None = None
        self._bloques_sel: list[tuple] = []
        self._hueco_sel: tuple | None = None
        self._destino_par: tuple | None = None  # grupo `( … )` enfocado donde se insertan los siguientes bloques
        self._marca_drop: dict[str, Any] | None = None  # guía visual de inserción (antes / después / dentro)
        self._resalte_mas: QRectF | None = None
        self._propio = False
        self._fuera = False
        self.arrastrando.connect(self._al_arrastrar)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setAcceptDrops(True)
        self.setToolTip("Para quitar un bloque, arrástralo fuera o pulsa Supr")

    @property
    def arbol(self) -> dict[str, Any] | None:
        return self._raices[0]

    def marcar_huecos(self, resaltar: bool) -> None:
        """Remarca (o no) los huecos vacíos del área: la fórmula está a medias y se avisa de lo que falta."""
        if resaltar != self.motor.resaltar_huecos:
            self.motor.resaltar_huecos = resaltar
            self.update()

    def _sincronizar_motor(self) -> None:
        self.motor.activo = self._bloque_sel
        self.motor.seleccionados = set(self._bloques_sel) if self._bloques_sel else ({self._bloque_sel} if self._bloque_sel else set())
        self.motor.destino_par = self._destino_par

    def poner_arbol(self, arbol: dict[str, Any] | None) -> None:
        self._raices = [copy.deepcopy(arbol)]
        self._bloque_sel = None
        self._bloques_sel = []
        self._destino_par = None
        self._sincronizar_motor()
        self.invalidar()

    def texto(self) -> str:
        return arbol_a_texto(self.arbol)

    def _maqueta(self, ancho: float) -> tuple[list[tuple[_Caja, float, float]], float]:
        self._sincronizar_motor()
        if self.arbol is None:
            w_hint = min(max(200.0, self.motor.m.horizontalAdvance(GUIA) + 32.0), max(80.0, ancho - 2 * MARGEN))
            c = _Caja(None, (0,), w_hint, 36.0)
        else:
            c = self.motor.caja(self.arbol, (0,), ancho - 2 * MARGEN)
        return [(c, float(MARGEN), float(MARGEN))], c.h + 2 * MARGEN

    def _validar(self, i: int, nueva: dict[str, Any] | None) -> str:
        """Un valor escrito a mano debe poder leerse otra vez como bloques."""
        try:
            (texto_a_arbol_valor if self.valor else texto_a_arbol)(arbol_a_texto(nueva), *self._datos())
        except ValueError as e:
            return f"No válido: {e}"
        return ""

    def _datos(self) -> tuple[dict[str, tuple[str, str]], list[str]]:
        return self.motor.fuente()

    # -- operaciones (lo que hacen el ratón y las pruebas)
    def _rechazar_flanco_en_temp(self, ruta: tuple | None, nodo: dict[str, Any] | None) -> bool:
        """IM1 (24-nov-2026): impide usar o soltar un flanco dentro de la base de un temporizador."""
        if ruta is None or nodo is None:
            return False
        pos = tuple(ruta)
        if _es_dentro_de_temp(self.arbol, pos) and _contiene_flanco(nodo):
            self.avisa.emit(AVISO_FLANCO_TEMP)
            return True
        if nodo.get("k") == "temp" and nodo.get("a") is None and self.arbol is not None:
            try:
                destino = obtener(self.arbol, pos)
            except KeyError:
                destino = None
            if _contiene_flanco(destino):
                self.avisa.emit(AVISO_FLANCO_TEMP)
                return True
        return False

    def soltar(self, ruta: tuple | None, nodo: dict[str, Any], origen: tuple | None = None) -> bool:
        """Suelta `nodo` en la `ruta` (hueco o bloque; sin ruta, lo añade al final del carril o al grupo activo)."""
        if ruta is None:
            if self.arbol is None:
                ruta = ()
            elif origen is None:
                # Arrastrar una nueva variable u operador sobre cualquier zona libre del carril lo añade directamente
                return self.insertar(nodo)
            else:
                return False
        ruta = tuple(ruta)
        if self._rechazar_flanco_en_temp(ruta, nodo):
            return False
        try:
            if origen is None and nodo["k"] in MODIFICADORES and nodo["a"] is None \
                    and ficha_cadena(obtener(self.arbol, ruta)) is not None:
                nueva = alternar_modificador(self.arbol, ruta, nodo["k"])
            else:
                nueva = mover(self.arbol, tuple(origen), ruta) if origen is not None else soltar(self.arbol, ruta, nodo)
        except KeyError:
            return False
        if nueva == self.arbol:
            return False
        self._fijar(0, nueva)
        return True

    def sustituir(self, nodo: dict[str, Any] | None) -> bool:
        """Pone `nodo` como toda la fórmula (Pegar, Limpiar, una constante sola). Devuelve si cambió algo."""
        if nodo == self.arbol:
            return False
        self._fijar(0, nodo)
        return True

    def limpiar(self) -> bool:
        """Vacía la fórmula."""
        return self.sustituir(None)

    def _sitio_elegido(self) -> tuple | None:
        """La ruta del modelo del hueco o del bloque seleccionado (con su variable, si es una ficha con modificadores), o None."""
        sel = self._hueco_sel if self._hueco_sel is not None else self._bloque_sel
        return None if sel is None else tuple(self._destino(sel)[1:])

    def _elegir_ficha(self, ruta: tuple, siempre: bool = False) -> None:
        """Deja seleccionada la ficha con modificadores que contiene `ruta` (para seguir aplicándole modificadores o rellenar su hueco). Con
        `siempre`, también la que se quedó sin ellos."""
        try:
            externa, mods = cadena_modificadores(self.arbol, tuple(ruta))
            ficha = ficha_cadena(obtener(self.arbol, externa))
        except KeyError:
            return
        if (mods or siempre) and ficha is not None:
            self._bloque_sel = (0,) + tuple(externa)
            self._bloques_sel = [self._bloque_sel]
            self.setFocus()
            self.update()
            self.seleccion_cambiada.emit()

    def _anadir_en_contenedor(self, subarbol: dict[str, Any] | None, nodo: dict[str, Any]) -> dict[str, Any]:
        """Añade `nodo` al final de un contenedor (raíz o grupo `( … )`) conectado con `·` (AND) o `+` (aritmético)."""
        copia = copy.deepcopy(nodo)
        if subarbol is None:
            return copia
        if self.valor:
            return nuevo("ar", op="+", a=copy.deepcopy(subarbol), b=copia)
        ops, cons = a_lista(subarbol)
        return de_lista(ops + [copia], cons + ["y"])

    def _ruta_par_valido(self) -> tuple | None:
        if self._destino_par is None or self.arbol is None:
            return None
        r = tuple(self._partir(self._destino_par)[1])
        try:
            n = obtener(self.arbol, r)
        except KeyError:
            return None
        if n is not None and n["k"] == "par":
            return r
        return None

    def _envolver_en_temp(self, t1: str = "5s", t2: str = "") -> bool:
        """Envuelve el bloque o los bloques seleccionados en un temporizador `t1/…/t2`."""
        if self.arbol is None:
            return False
        if len(self._bloques_sel) > 1:
            rutas = [tuple(self._partir(s)[1]) for s in self._bloques_sel]
            if any(_contiene_flanco(obtener(self.arbol, r)) for r in rutas):
                self.avisa.emit(AVISO_FLANCO_TEMP)
                return False
            nueva_par, ruta_grupo = envolver_varios(self.arbol, rutas)
            if nueva_par == self.arbol or ruta_grupo is None:
                return False
            par_nodo = obtener(nueva_par, ruta_grupo)
            temp_nodo = nuevo("temp", t1=t1, t2=t2, a=copy.deepcopy(par_nodo["a"]))
            nueva = con_nodo(nueva_par, ruta_grupo, temp_nodo)
            self._fijar(0, nueva)
            self._bloque_sel = (0,) + tuple(ruta_grupo)
            self._bloques_sel = [self._bloque_sel]
            self._sincronizar_motor()
            self.invalidar()
            self.seleccion_cambiada.emit()
            return True
        if self._bloque_sel is None:
            return False
        r = tuple(self._partir(self._bloque_sel)[1])
        nodo = obtener(self.arbol, r)
        if nodo is None:
            return False
        if _contiene_flanco(nodo):
            self.avisa.emit(AVISO_FLANCO_TEMP)
            return False
        inner = copy.deepcopy(nodo["a"]) if nodo["k"] == "par" and nodo["a"] is not None else copy.deepcopy(nodo)
        temp_nodo = nuevo("temp", t1=t1, t2=t2, a=inner)
        nueva = con_nodo(self.arbol, r, temp_nodo)
        self._fijar(0, nueva)
        self._bloque_sel = (0,) + r
        self._bloques_sel = [self._bloque_sel]
        self._sincronizar_motor()
        self.invalidar()
        self.seleccion_cambiada.emit()
        return True

    def _seleccion_con_flanco(self) -> bool:
        if self.arbol is None:
            return False
        sels = self._bloques_sel or ([self._bloque_sel] if self._bloque_sel is not None else [])
        return any(_contiene_flanco(obtener(self.arbol, tuple(self._partir(s)[1]))) for s in sels)

    def insertar(self, nodo: dict[str, Any]) -> bool:
        """Inserción directa en el carril (o en el grupo `( … )` activo), sin exigir huecos `?` previos.
        Si hay un hueco `?` seleccionado explícitamente, lo rellena; si se pulsa `( … )` o `Temporizador` con bloques
        seleccionados, los envuelve; `1`/`0` en raíz sustituye la fórmula entera (como en la maqueta)."""
        if nodo["k"] in MODIFICADORES and nodo["a"] is None:
            return self.aplicar_modificador(nodo["k"])
        if nodo["k"] == "par" and nodo["a"] is None and self.hay_seleccion():
            return self.envolver_elegido()
        if nodo["k"] == "temp" and self.hay_seleccion() and not self.valor:
            if self._envolver_en_temp(nodo.get("t1", "5s"), nodo.get("t2", "")):
                return True
            if self._seleccion_con_flanco():
                return False
        if self._hueco_sel is not None:
            ruta_h = tuple(self._partir(self._hueco_sel)[1])
            return self.soltar(ruta_h, nodo)
        r_par = self._ruta_par_valido()
        if r_par is not None:
            if self._rechazar_flanco_en_temp(r_par + ("a",), nodo):
                return False
            par_actual = obtener(self.arbol, r_par)
            if par_actual["a"] is not None and nodo["k"] in ("var", "etapa", "vnum", "num", "const"):
                hueco_par = primer_hueco(par_actual["a"])
                if hueco_par is not None:
                    return self.soltar(r_par + ("a",) + hueco_par, nodo)
            nuevo_dentro = self._anadir_en_contenedor(par_actual["a"], nodo)
            nueva = con_nodo(self.arbol, r_par + ("a",), nuevo_dentro)
            self._fijar(0, nueva)
            self._destino_par = (0,) + r_par
            self._sincronizar_motor()
            self.invalidar()
            self.seleccion_cambiada.emit()
            return True
        # Si hay un hueco pendiente en la fórmula (por ej. un NOT ? o `a AND ?`) y se inserta una variable/constante, rellénalo
        if self.arbol is not None:
            hueco = primer_hueco(self.arbol)
            if hueco is not None and nodo["k"] in ("var", "etapa", "vnum", "num", "const"):
                return self.soltar(hueco, nodo)
        if not self.valor and nodo["k"] == "const":
            # Constante 1 o 0 en la raíz: sustituye la fórmula completa (maqueta `setRootConst`)
            self._fijar(0, copy.deepcopy(nodo))
            self._bloque_sel = (0,)
            self._bloques_sel = [(0,)]
            self._sincronizar_motor()
            self.update()
            self.seleccion_cambiada.emit()
            return True
        if self.arbol is None or (not self.valor and self.arbol["k"] == "const"):
            nueva = copy.deepcopy(nodo)
            self._fijar(0, nueva)
            if nodo["k"] == "par":
                self._destino_par = (0,)
                self._sincronizar_motor()
                self.invalidar()
                self.seleccion_cambiada.emit()
            return True
        # Inserción directa al final del carril raíz (conectada automáticamente con `·` o `+`)
        nueva = self._anadir_en_contenedor(self.arbol, nodo)
        self._fijar(0, nueva)
        if nodo["k"] == "par":
            rutas_r = _rutas_lista(nueva, ()) if not self.valor else [("b",)]
            if rutas_r:
                self._destino_par = (0,) + tuple(rutas_r[-1])
                self._sincronizar_motor()
                self.invalidar()
                self.seleccion_cambiada.emit()
        return True

    def quitar_modificadores(self) -> bool:
        """Botón «Normal» de la barra contextual: quita NOT, ↑ y ↓ de los bloques seleccionados."""
        sels = list(self._bloques_sel) if self._bloques_sel else ([self._bloque_sel] if self._bloque_sel else [])
        if not sels or self.arbol is None:
            return False
        nueva = self.arbol
        nuevas_sel: list[tuple] = []
        for sel in sels:
            r = tuple(self._partir(sel)[1])
            try:
                ext, mods = cadena_modificadores(nueva, r)
                if mods:
                    hoja = obtener(nueva, ext + ("a",) * len(mods))
                    nueva = con_nodo(nueva, ext, copy.deepcopy(hoja))
                nuevas_sel.append((0,) + tuple(ext))
            except KeyError:
                continue
        if nueva == self.arbol:
            return False
        self._fijar(0, nueva)
        self._bloques_sel = nuevas_sel
        self._bloque_sel = nuevas_sel[-1] if nuevas_sel else None
        self._sincronizar_motor()
        self.invalidar()
        self.seleccion_cambiada.emit()
        return True

    def alternar_not_interior_temp(self) -> bool:
        """Alterna NOT sobre la señal/fórmula interior de un temporizador seleccionado (`5s/X0` ↔ `5s/NOT X0`)."""
        if self._bloque_sel is None or self.arbol is None:
            return False
        r = tuple(self._partir(self._bloque_sel)[1])
        try:
            ext, mods = cadena_modificadores(self.arbol, r)
            r_temp = ext + ("a",) * len(mods)
            nodo = obtener(self.arbol, r_temp)
        except KeyError:
            return False
        if nodo is None or nodo["k"] != "temp":
            return False
        nueva = alternar_modificador(self.arbol, r_temp + ("a",), "no")
        if nueva == self.arbol:
            return False
        sel_antes = self._bloque_sel
        self._fijar(0, nueva)
        self._bloque_sel = sel_antes
        self._bloques_sel = [sel_antes]
        self._sincronizar_motor()
        self.invalidar()
        self.seleccion_cambiada.emit()
        return True

    def salir_a_raiz(self) -> None:
        """Sale del grupo `( … )` activo para volver a insertar en la raíz."""
        if self._destino_par is not None:
            self._destino_par = None
            self._sincronizar_motor()
            self.invalidar()
            self.seleccion_cambiada.emit()

    def info_seleccion(self) -> dict[str, Any]:
        """Resumen de la selección actual para la barra contextual `.ctx-bar`."""
        sels = list(self._bloques_sel) if self._bloques_sel else ([self._bloque_sel] if self._bloque_sel else [])
        en_grupo = self._ruta_par_valido() is not None
        if not sels or self.arbol is None:
            return {"count": 0, "en_grupo": en_grupo, "es_valor": self.valor}
        if len(sels) > 1:
            mods_union: set[str] = set()
            for sel in sels:
                try:
                    _, ms = cadena_modificadores(self.arbol, tuple(self._partir(sel)[1]))
                    mods_union.update(ms)
                except KeyError:
                    pass
            return {
                "count": len(sels),
                "nombre": f"{len(sels)} bloques",
                "mods": mods_union,
                "es_par": False,
                "es_temp": False,
                "es_cmp": False,
                "temp_neg_int": False,
                "puede_mod": not self.valor,
                "en_grupo": en_grupo,
                "es_valor": self.valor,
            }
        r = tuple(self._partir(sels[0])[1])
        try:
            nodo = obtener(self.arbol, r)
            ext, mods = cadena_modificadores(self.arbol, r)
            hoja = obtener(self.arbol, ext + ("a",) * len(mods))
        except KeyError:
            return {"count": 0, "en_grupo": en_grupo, "es_valor": self.valor}
        if nodo is None:
            return {"count": 0, "en_grupo": en_grupo, "es_valor": self.valor}
        es_par = hoja is not None and hoja["k"] == "par"
        es_temp = hoja is not None and hoja["k"] == "temp"
        es_cmp = hoja is not None and hoja["k"] == "cmp"
        temp_neg_int = bool(es_temp and hoja.get("a") is not None and "no" in Motor._cadena(hoja["a"])[0])
        if es_par:
            nombre = "Grupo ( … )"
        elif es_temp:
            nombre = "Temporizador"
        elif es_cmp:
            lado = hoja.get("izq") or hoja.get("n") or "?"
            nombre = f"Comparación ({lado})"
        elif hoja is not None and hoja["k"] == "etapa":
            nombre = etapa_visible(hoja["n"]) if hoja.get("n") else "Etapa"
        elif hoja is not None and hoja["k"] in ("var", "vnum"):
            nombre = hoja.get("n") or "?"
        elif hoja is not None and hoja["k"] in ("const", "num"):
            nombre = str(hoja.get("v", ""))
        else:
            nombre = arbol_a_texto(nodo) or "Bloque"
        return {
            "count": 1,
            "nombre": nombre,
            "mods": set(mods),
            "es_par": es_par,
            "es_temp": es_temp,
            "es_cmp": es_cmp,
            "temp_neg_int": temp_neg_int,
            "puede_mod": not self.valor and hoja is not None and hoja["k"] not in ("const",),
            "en_grupo": en_grupo,
            "es_valor": self.valor,
        }

    def aplicar_modificador(self, clase: str) -> bool:
        """NOT, ↑ o ↓ sobre la ficha elegida (o sobre una multiselección: NOT envuelve y niega el grupo).
        Sin elección, deja un modificador con su hueco pendiente en el primer hueco libre («NOT ?»)."""
        if len(self._bloques_sel) > 1:
            rutas = [tuple(self._partir(s)[1]) for s in self._bloques_sel]
            if clase == "no":
                nueva_par, ruta_grupo = envolver_varios(self.arbol, rutas)
                if nueva_par == self.arbol or ruta_grupo is None:
                    self.avisa.emit("Para negar varios bloques a la vez, elige operandos seguidos.")
                    return False
                nueva = alternar_modificador(nueva_par, ruta_grupo, "no")
                self._fijar(0, nueva)
                self._bloque_sel = (0,) + tuple(ruta_grupo)
                self._bloques_sel = [self._bloque_sel]
                self._sincronizar_motor()
                self.invalidar()
                self.seleccion_cambiada.emit()
                return True
            if clase in ("sube", "baja") and any(_es_dentro_de_temp(self.arbol, r) for r in rutas):
                self.avisa.emit(AVISO_FLANCO_TEMP)
                return False
            nueva = self.arbol
            nuevas_sel: list[tuple] = []
            for sel in self._bloques_sel:
                r = tuple(self._destino(sel)[1:])
                try:
                    ext = cadena_modificadores(nueva, r)[0]
                    nueva = alternar_modificador(nueva, r, clase)
                    nuevas_sel.append((0,) + tuple(ext))
                except KeyError:
                    continue
            if nueva == self.arbol:
                return False
            self._fijar(0, nueva)
            self._bloques_sel = nuevas_sel
            self._bloque_sel = nuevas_sel[-1] if nuevas_sel else None
            self.setFocus()
            self.update()
            self.seleccion_cambiada.emit()
            return True
        ruta = self._sitio_elegido()
        if ruta is None:
            ruta = () if self.arbol is None else primer_hueco(self.arbol)
            if ruta is None:
                self.avisa.emit("No queda ningún hueco libre: elige una ficha para aplicarle el modificador.")
                return False
        if clase in ("sube", "baja") and _es_dentro_de_temp(self.arbol, ruta):
            self.avisa.emit(AVISO_FLANCO_TEMP)
            return False
        try:
            nueva = alternar_modificador(self.arbol, ruta, clase)
            externa = cadena_modificadores(self.arbol, ruta)[0]
        except KeyError:
            return False
        if nueva == self.arbol:
            return False
        self._fijar(0, nueva)
        self._elegir_ficha(externa, True)
        if self._bloque_sel is None and obtener(self.arbol, externa) is not None:
            self._bloque_sel = (0,) + tuple(externa)
            self._bloques_sel = [self._bloque_sel]
            self.setFocus()
            self.update()
            self.seleccion_cambiada.emit()
        return True

    def _modificador(self, ruta: tuple, clase: str) -> None:
        """Se pulsó la insignia de una ficha: un flanco pasa al otro (↑ por ↓), la negación se quita."""
        r = tuple(self._partir(ruta)[1])
        if clase != "no" and _es_dentro_de_temp(self.arbol, r):
            self.avisa.emit(AVISO_FLANCO_TEMP)
            return
        if clase != "no":
            clase = "baja" if clase == "sube" else "sube"
        nueva = alternar_modificador(self.arbol, r, clase)
        if nueva != self.arbol:
            externa = cadena_modificadores(self.arbol, r)[0]
            self._fijar(0, nueva)
            self._elegir_ficha(externa, True)

    def _ruta_arrastre(self, ruta: tuple) -> tuple:
        """Una ficha con modificadores se lleva entera, venga el arrastre de donde venga de ella."""
        i, r = self._partir(ruta)
        try:
            externa, mods = cadena_modificadores(self._raices[i], tuple(r))
            if mods and ficha_cadena(obtener(self._raices[i], externa)) is not None:
                return (i,) + tuple(externa)
        except (KeyError, IndexError):
            pass
        return ruta

    def quitar(self, ruta: tuple) -> None:
        ruta = tuple(ruta)
        if ruta and ruta[0] == 0:
            ruta = ruta[1:]  # las rutas de la superficie llevan el índice de la raíz; las del modelo, no
        if obtener(self.arbol, ruta) is not None:
            self._fijar(0, _quitar_limpio(self.arbol, ruta))

    def anadir_hueco(self, ruta: tuple) -> bool:
        """El «+» de un «y» o un «o»: otro hueco al final. Devuelve si cambió algo."""
        nueva = anadir_hueco(self.arbol, tuple(self._partir(ruta)[1]))
        if nueva is self.arbol:
            return False
        self._fijar(0, nueva)
        return True

    def quitar_hueco(self, ruta: tuple, clave: str) -> bool:
        """Quita un hueco vacío de un «y» o un «o» de más de dos (botón derecho → «Quitar hueco», o seleccionarlo y Supr)."""
        nueva = quitar_hueco(self.arbol, tuple(self._partir(ruta)[1]), clave)
        if nueva is self.arbol:
            return False
        self._fijar(0, nueva)
        return True

    def hueco_quitable(self, ruta: tuple) -> bool:
        """Si el sitio de `ruta` (de la superficie) es un hueco vacío de un «y» o un «o» de más de dos huecos."""
        r = self._partir(ruta)[1]
        if not r:
            return False
        try:
            padre = obtener(self.arbol, r[:-1])
            return obtener(self.arbol, r) is None and padre is not None and padre["k"] in ("y", "o") \
                and len(hijos(padre)) > 2
        except KeyError:
            return False

    def quitar_hueco_en(self, ruta: tuple) -> bool:
        r = self._partir(ruta)[1]
        return self.hueco_quitable(ruta) and self.quitar_hueco(r[:-1], r[-1])

    def _fijar(self, i: int, nueva: dict[str, Any] | None) -> None:
        self._hueco_sel = None
        self._bloque_sel = None
        self._bloques_sel = []
        self._destino_par = None
        self.previo = self._raices[i]
        self._sincronizar_motor()
        super()._fijar(i, nueva)
        self.modificado.emit()
        self.seleccion_cambiada.emit()

    def envolver_elegido(self) -> bool:
        """«Envolver ( … )»: envuelve el bloque elegido (o varios operandos seguidos con Ctrl+clic / Shift+clic)
        entre paréntesis; si lo elegido es ya un grupo `( … )`, le quita los paréntesis."""
        if len(self._bloques_sel) > 1:
            rutas = [tuple(self._partir(s)[1]) for s in self._bloques_sel]
            nueva, ruta_grupo = envolver_varios(self.arbol, rutas)
            if nueva == self.arbol or ruta_grupo is None:
                self.avisa.emit("Para envolver varios bloques entre paréntesis, elige operandos seguidos.")
                return False
            self._fijar(0, nueva)
            self._bloque_sel = (0,) + tuple(ruta_grupo)
            self._bloques_sel = [self._bloque_sel]
            self.seleccion_cambiada.emit()
            self.update()
            return True
        if self._bloque_sel is not None:
            r_sel = tuple(self._partir(self._bloque_sel)[1])
            nodo_sel = obtener(self.arbol, r_sel)
            if nodo_sel is not None and nodo_sel["k"] == "par":
                return self.desenvolver_elegido(r_sel)
        ruta = self._sitio_elegido()
        if ruta is None or obtener(self.arbol, ruta) is None:
            return False
        nueva = envolver(self.arbol, ruta, "par")
        self._fijar(0, nueva)
        self._bloque_sel = (0,) + tuple(ruta)
        self._bloques_sel = [self._bloque_sel]
        self.seleccion_cambiada.emit()
        self.update()
        return True

    def desenvolver_elegido(self, ruta: tuple | None = None) -> bool:
        """Quita los paréntesis del grupo `( … )` de `ruta` (o del bloque elegido)."""
        if ruta is None:
            if self._bloque_sel is None:
                return False
            ruta = tuple(self._partir(self._bloque_sel)[1])
        else:
            ruta = tuple(self._partir(ruta)[1])
        nueva = desenvolver_en(self.arbol, ruta)
        if nueva == self.arbol:
            return False
        self._fijar(0, nueva)
        if obtener(self.arbol, ruta) is not None:
            self._bloque_sel = (0,) + tuple(ruta)
            self._bloques_sel = [self._bloque_sel]
        self.seleccion_cambiada.emit()
        self.update()
        return True

    def quitar_elegido(self) -> bool:
        """«Quitar (Supr)»: quita el bloque elegido (o todos los de una selección múltiple) sin dejar huecos `?`."""
        if len(self._bloques_sel) > 1 and self.arbol is not None:
            copia = copy.deepcopy(self.arbol)
            etiquetados = 0
            for sel in self._bloques_sel:
                r = tuple(self._partir(sel)[1])
                try:
                    n = obtener(copia, r)
                    if n is not None:
                        n["_tag_mov"] = True
                        etiquetados += 1
                except KeyError:
                    continue
            if not etiquetados:
                return False
            nueva = copia
            while True:
                r_tag = _buscar_etiqueta(nueva)
                if r_tag is None:
                    break
                obtener(nueva, r_tag).pop("_tag_mov", None)
                nueva = _quitar_limpio(nueva, r_tag)
            if nueva == self.arbol:
                return False
            self._fijar(0, nueva)
            return True
        sel = self._bloque_sel
        if sel is None:
            return False
        self.quitar(sel)
        return True

    def hay_seleccion(self) -> bool:
        return self._bloque_sel is not None or bool(self._bloques_sel)

    def _conector_en(self, pos: QPointF) -> tuple[QRectF, tuple, str, int] | None:
        self._calcular(self.width())
        return next((c for c in self.motor.conectores if c[0].contains(pos)), None)

    def alternar_conector(self, ruta: tuple, clave: str, indice: int) -> bool:
        """Pulsa un conector `·` / `+` (o un operador aritmético +, −, ×, ÷) para alternarlo."""
        r = tuple(self._partir(ruta)[1])
        try:
            if clave == "op":
                nueva = cambiar_operador_ar(self.arbol, r, indice)
            else:
                nueva = cambiar_conector_lista(self.arbol, r, indice)
        except (KeyError, IndexError):
            return False
        if nueva == self.arbol:
            return False
        self._fijar(0, nueva)
        return True

    def _actualizar_multiseleccion(self, pulsado: tuple | None, mods: Qt.KeyboardModifier) -> None:
        if pulsado is None:
            self._bloque_sel = None
            self._bloques_sel = []
            return
        r_pulsado = tuple(self._partir(pulsado)[1])
        base_pulsado = _raiz_yo(self.arbol, r_pulsado[:-1]) if r_pulsado else ()
        rutas_lista = [(0,) + ro for ro in _rutas_lista(self.arbol, base_pulsado)] if r_pulsado else []
        if self._bloques_sel:
            actuales = list(self._bloques_sel)
        elif self._bloque_sel is not None:
            actuales = [self._bloque_sel]
        else:
            actuales = []
        misma_lista = bool(
            rutas_lista and pulsado in rutas_lista and actuales and all(a in rutas_lista for a in actuales)
        )
        if (mods & Qt.KeyboardModifier.ShiftModifier) and misma_lista and self._bloque_sel in rutas_lista:
            i0, i1 = rutas_lista.index(self._bloque_sel), rutas_lista.index(pulsado)
            lo, hi = min(i0, i1), max(i0, i1)
            self._bloques_sel = rutas_lista[lo:hi + 1]
            return
        if (mods & Qt.KeyboardModifier.ControlModifier) and misma_lista:
            if pulsado in actuales:
                nuevas = [a for a in actuales if a != pulsado]
            else:
                nuevas = [r for r in rutas_lista if r in actuales or r == pulsado]
            self._bloques_sel = nuevas
            self._bloque_sel = nuevas[-1] if nuevas else None
            return
        self._bloque_sel = pulsado
        self._bloques_sel = [pulsado]

    def _par_ancestro(self, ruta: tuple[str, ...]) -> tuple[str, ...] | None:
        """El grupo `( … )` más interior que contiene `ruta` (o `ruta` misma si es un `par`), o None si está en la raíz."""
        if self.arbol is None:
            return None
        try:
            nodo_p = obtener(self.arbol, ruta)
        except KeyError:
            return None
        if nodo_p is not None and nodo_p["k"] == "par":
            return ruta
        if nodo_p is not None and nodo_p["k"] == "no" and nodo_p["a"] is not None and nodo_p["a"]["k"] == "par":
            return ruta + ("a",)
        for k in range(len(ruta) - 1, -1, -1):
            pref = ruta[:k]
            try:
                anc = obtener(self.arbol, pref)
            except KeyError:
                continue
            if anc is not None and anc["k"] == "par":
                return pref
        return None

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._hueco_sel = None
        if self._conector_en(event.position()) is not None:
            return
        prev_dest = self._destino_par
        pulsado = self._bloque_en(event.position())
        self._actualizar_multiseleccion(pulsado, event.modifiers())
        # Como en la maqueta (`targetContainerId = node.type === 'group' ? node.id : parent.id`):
        # pulsar un `( … )` o un bloque dentro de él mantiene el foco dentro del grupo; pulsar en raíz o fondo vuelve a raíz.
        if pulsado is None:
            self._destino_par = None
        else:
            r_p = tuple(self._partir(pulsado)[1])
            anc = self._par_ancestro(r_p)
            self._destino_par = None if anc is None else (0,) + anc
        if self._bloque_sel is not None:
            self.setFocus()
        if self._pieza_en(event.position()) is None:
            ruta = self.ruta_en(event.position())
            if ruta is not None and self.hueco_quitable(ruta):
                self._hueco_sel = tuple(ruta)
                self.setFocus()
        self._sincronizar_motor()
        if self._destino_par != prev_dest:
            self.invalidar()
        else:
            self.update()
        self.seleccion_cambiada.emit()

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if self._pulsado is not None:
            pos_ini = self._pulsado[0]
            con = self._conector_en(event.position())
            if con is not None and (event.position() - pos_ini).manhattanLength() < 6:
                self._pulsado = None
                self.alternar_conector(con[1], con[2], con[3])
                return
        super().mouseReleaseEvent(event)

    def copiar_formula(self) -> bool:
        """Copia la fórmula entera al portapapeles (el formato que lee «Pegar» y Ctrl+V, en esta y en otras ventanas)."""
        if self.arbol is None:
            return False
        datos = QMimeData()
        datos.setData(MIME_FORMULA, arbol_a_texto(self.arbol).encode("utf-8"))
        datos.setData(MIME_TIPO, self._tipo().encode())
        QApplication.clipboard().setMimeData(datos)
        return True

    def _tipo(self) -> str:
        return "valor" if self.valor else "condicion"

    def formula_del_portapapeles(self, estricto: bool = True) -> dict[str, Any] | None:
        """El bloque que hay copiado, leído con las reglas de esta área (una condición no se pega en un valor ni al revés). None si no hay
        nada copiado o no vale aquí."""
        datos = QApplication.clipboard().mimeData()
        if datos is None or not datos.hasFormat(MIME_FORMULA):
            return None
        if estricto and datos.hasFormat(MIME_TIPO) and bytes(datos.data(MIME_TIPO)).decode() != self._tipo():
            return None  # (el botón Pegar no pega una condición en un valor ni al revés)
        analizar = texto_a_arbol_valor if self.valor else texto_a_arbol
        try:
            return analizar(bytes(datos.data(MIME_FORMULA)).decode("utf-8"), *self._datos())
        except ValueError:
            return None

    def puede_pegar(self) -> bool:
        return self.formula_del_portapapeles() is not None

    def pegar_formula(self) -> bool:
        """El botón «Pegar»: la fórmula copiada sustituye a la entera (Ctrl+V pega en el hueco o el bloque elegido)."""
        nodo = self.formula_del_portapapeles()
        return nodo is not None and self.sustituir(nodo)

    def _portapapeles_formula(self, evento: Any) -> bool:
        portapapeles = QApplication.clipboard()
        if evento.matches(QKeySequence.StandardKey.Copy):
            ruta = self._bloque_sel[1:] if self._bloque_sel else ()
            bloque = obtener(self.arbol, ruta)
            if bloque is not None:
                datos = QMimeData()
                datos.setData(MIME_FORMULA, arbol_a_texto(bloque).encode("utf-8"))
                datos.setData(MIME_TIPO, self._tipo().encode())
                portapapeles.setMimeData(datos)
            return True
        if not evento.matches(QKeySequence.StandardKey.Paste):
            return False
        nodo = self.formula_del_portapapeles(False)  # (Ctrl+V pega lo que haya, como siempre)
        if nodo is not None:
            ruta = self._hueco_sel or self._bloque_sel or (0,)
            self.soltar(ruta[1:], nodo)
        return True

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if self._portapapeles_formula(event):
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self._hueco_sel is not None:
            ruta, self._hueco_sel = self._hueco_sel, None
            self.quitar_hueco_en(ruta)
            self.update()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and (self._bloque_sel is not None or self._bloques_sel):
            self.quitar_elegido()
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, ev: Any) -> bool:
        if ev.type() == QEvent.Type.ShortcutOverride and (
            ev.matches(QKeySequence.StandardKey.Copy) or ev.matches(QKeySequence.StandardKey.Paste)
        ):
            ev.accept()
            return True
        if ev.type() == QEvent.Type.ShortcutOverride and (self._hueco_sel is not None or self.hay_seleccion()) \
                and ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            ev.accept()  # Supr con un hueco seleccionado es para el hueco, no para el atajo «Borrar» de la ventana
            return True
        return super().event(ev)

    def contextMenuEvent(self, ev: Any) -> None:  # noqa: N802
        pos = QPointF(ev.pos())
        ruta = self.ruta_en(pos)
        if ruta is not None and self.hueco_quitable(ruta):
            menu = QMenu(self)
            menu.addAction("Quitar hueco", lambda: self.quitar_hueco_en(ruta))
            menu.exec(ev.globalPos())
            return
        bloque = self._bloque_en(pos)
        if bloque is not None:
            r = tuple(self._partir(bloque)[1])
            nodo = obtener(self.arbol, r)
            if nodo is not None and nodo["k"] == "par":
                menu = QMenu(self)
                menu.addAction("Quitar paréntesis", lambda: self.desenvolver_elegido(r))
                menu.exec(ev.globalPos())

    def soltar_en_mas(self, ruta: tuple, nodo: dict[str, Any], origen: tuple | None = None) -> bool:
        """Suelta un bloque sobre el «+» del «y» o el «o» de `ruta`: lo añade en un hueco nuevo."""
        r_dest = tuple(self._partir(ruta)[1])
        if self._rechazar_flanco_en_temp(r_dest, nodo):
            return False
        try:
            nueva = soltar_en_mas(self.arbol, r_dest, nodo,
                                  None if origen is None else tuple(origen))
        except KeyError:
            return False
        if nueva == self.arbol:
            return False
        self._fijar(0, nueva)
        return True

    def _boton(self, ruta: tuple, clave: str) -> None:
        if clave == "mas":
            self.anadir_hueco(ruta)

    def _partir(self, ruta: tuple) -> tuple[int, tuple]:
        return (0, tuple(ruta)) if not ruta or ruta[0] != 0 else (0, tuple(ruta[1:]))

    # -- arrastres que llegan
    def _datos_mime(self, mime: QMimeData) -> dict[str, Any] | None:
        return json.loads(bytes(mime.data(MIME)).decode()) if mime.hasFormat(MIME) else None

    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME):
            self._fuera = False
            self.update()
            event.acceptProposedAction()

    def _al_arrastrar(self, en_curso: bool) -> None:
        """Empieza o acaba el arrastre de un bloque de esta área: mientras dura, el borde se pone rojo si el puntero sale (soltarlo fuera
        lo quita)."""
        self._propio, self._fuera = en_curso, False
        self.update()

    def _contenedor_de_operando(self, ruta_op: tuple[str, ...]) -> tuple[tuple[str, ...], int]:
        """Dada la ruta de un bloque operando en el carril, devuelve `(base_contenedor, indice)` dentro de su lista plana."""
        if self.arbol is None:
            return (), 0
        if not ruta_op:
            return (), 0
        padre = obtener(self.arbol, ruta_op[:-1])
        if padre is not None and padre["k"] in ("y", "o"):
            base = _raiz_yo(self.arbol, ruta_op[:-1])
            rutas_l = _rutas_lista(self.arbol, base)
            if ruta_op in rutas_l:
                return base, rutas_l.index(ruta_op)
        if padre is not None and padre["k"] == "ar":
            # Sube hasta la raíz de la cadena aritmética del mismo contenedor (raíz o hijo de `par`)
            base = ruta_op[:-1]
            while base and obtener(self.arbol, base[:-1])["k"] == "ar":
                base = base[:-1]
            rutas_a = _rutas_ar(self.arbol, base)
            if ruta_op in rutas_a:
                return base, rutas_a.index(ruta_op)
        if padre is not None and padre["k"] in ("par", "temp"):
            return ruta_op, 0
        return (), 0

    def _calcular_destino_arrastre(
        self, pos: QPointF, nodo: dict[str, Any], origen: tuple | None
    ) -> dict[str, Any] | None:
        """Calcula el destino exacto de soltar en `pos` siguiendo la maqueta (`antes`, `despues`, `dentro`, `hueco`, `final`):
        nunca destruye un grupo `( … )` ni deja huecos `?`."""
        self._calcular(self.width())
        if self.arbol is None:
            return {"tipo": "final", "base": (), "indice": 0, "rect": None}
        # Bloques concretos bajo el puntero (excluyendo contenedores invisibles `y`/`o`/`ar`)
        candidatos = [
            (r.width() * r.height(), r, ruta, n)
            for r, ruta, n in self._bloques
            if r.contains(pos) and (n is None or n["k"] not in ("y", "o", "ar"))
        ]
        if not candidatos:
            # Zona libre del carril: al final del grupo activo (si hay) o de la raíz
            r_par = self._ruta_par_valido() if origen is None else None
            base = (r_par + ("a",)) if r_par is not None else ()
            sub = self.arbol if not base else obtener(self.arbol, base)
            ops = a_lista_ar(sub)[0] if self.valor else a_lista(sub)[0]
            return {"tipo": "final", "base": base, "indice": len(ops), "rect": None}
        _, rect, ruta_full, target = min(candidatos, key=lambda x: x[0])
        r = tuple(self._partir(ruta_full)[1])
        if origen is not None and r[:len(origen)] == tuple(origen):
            return None
        # Hueco vacío explícito (p. ej. interior vacío de `( … )` o `NOT ?`)
        if target is None:
            return {"tipo": "hueco", "ruta": r, "rect": rect}
        # Ficha pendiente con modificadores sin operando (`NOT ?`, `↑ ?`, `↓ ?`): soltar encima rellena su hueco
        if target["k"] in MODIFICADORES and ficha_cadena(target) is not None and Motor._cadena(target)[1] is None:
            mods_p = Motor._cadena(target)[0]
            return {"tipo": "hueco", "ruta": r + ("a",) * len(mods_p), "rect": rect}
        # Modificador soltado desde fuera sobre un bloque: envuelve/alterna el modificador
        if origen is None and nodo["k"] in MODIFICADORES and nodo["a"] is None:
            return {"tipo": "mod", "ruta": r, "rect": rect}
        # Grupo `( … )` (o `NOT ( … )`): zona central 20 %–80 % inserta DENTRO al final; bordes insertan antes/después
        es_par = target["k"] == "par" or (target["k"] == "no" and target.get("a") is not None and target["a"]["k"] == "par")
        r_par = r + ("a",) if (target["k"] == "no" and es_par) else r
        if es_par:
            en_centro = (rect.left() + rect.width() * 0.18) <= pos.x() <= (rect.right() - rect.width() * 0.18)
            if en_centro or target.get("a") is None:
                base_in = r_par + ("a",)
                sub = obtener(self.arbol, base_in)
                ops = a_lista_ar(sub)[0] if self.valor else a_lista(sub)[0]
                return {"tipo": "dentro", "base": base_in, "indice": len(ops), "r_par": r_par, "rect": rect}
        # Temporizador: zona central permite insertar/encadenar dentro de la fórmula evaluada del temporizador
        es_temp = target["k"] == "temp" or (target["k"] == "no" and target.get("a") is not None and target["a"]["k"] == "temp")
        r_temp = r + ("a",) if (target["k"] == "no" and es_temp) else r
        if es_temp and not self.valor:
            en_centro = (rect.left() + rect.width() * 0.25) <= pos.x() <= (rect.right() - rect.width() * 0.25)
            if en_centro:
                base_in = r_temp + ("a",)
                sub = obtener(self.arbol, base_in)
                ops = a_lista(sub)[0]
                return {"tipo": "dentro", "base": base_in, "indice": len(ops), "r_par": None, "rect": rect}
        # Cualquier otro bloque (o los bordes izq/der de `( … )`): insertar ANTES o DESPUÉS en su lista
        # Si `r` es el interior de una cadena de modificadores, subir al exterior de la ficha
        try:
            r_ext, _ = cadena_modificadores(self.arbol, r)
        except KeyError:
            r_ext = r
        base_c, idx = self._contenedor_de_operando(r_ext)
        despues = pos.x() >= rect.center().x()
        return {
            "tipo": "despues" if despues else "antes",
            "base": base_c,
            "indice": idx + (1 if despues else 0),
            "rect": rect,
        }

    def dragMoveEvent(self, event: Any) -> None:  # noqa: N802
        d = self._datos_mime(event.mimeData())
        if d is None:
            return
        origen = tuple(d["origen"]) if d.get("origen") is not None and d["grupo"] == self.grupo else None
        mas = self._mas_en(event.position())
        self._resalte_mas = mas[0] if mas else None
        self._marca_drop = None if mas else self._calcular_destino_arrastre(event.position(), d["nodo"], origen)
        self._objetivo = (
            (0,) + tuple(self._marca_drop["ruta"])
            if self._marca_drop is not None and self._marca_drop["tipo"] in ("hueco", "mod")
            else None
        )
        self.update()
        event.setDropAction(Qt.DropAction.MoveAction if origen is not None else Qt.DropAction.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event: Any) -> None:  # noqa: N802
        self._objetivo = None
        self._resalte_mas = None
        self._marca_drop = None
        self._fuera = self._propio
        self.update()

    def _mas_en(self, pos: QPointF) -> tuple | None:
        """El «+» de un «y» o un «o» bajo el puntero, si lo hay: (su rectángulo, la ruta del bloque)."""
        pieza = self._pieza_en(pos)
        return (pieza[0], pieza[2]) if pieza and pieza[1] == "boton" and pieza[3] == "mas" else None

    def dropEvent(self, event: Any) -> None:  # noqa: N802
        d = self._datos_mime(event.mimeData())
        self._objetivo = None
        self._resalte_mas = None
        self._marca_drop = None
        if d is None:
            return
        mas = self._mas_en(event.position())
        origen = tuple(d["origen"]) if d.get("origen") is not None and d["grupo"] == self.grupo else None
        _ARRASTRE["resuelto"] = True
        event.setDropAction(Qt.DropAction.MoveAction if origen is not None else Qt.DropAction.CopyAction)
        event.accept()
        if mas:  # sobre el «+»: en un hueco nuevo
            self.soltar_en_mas(mas[1], d["nodo"], origen)
            self.update()
            return
        dest = self._calcular_destino_arrastre(event.position(), d["nodo"], origen)
        if dest is None:
            self.update()
            return
        tipo = dest["tipo"]
        if tipo in ("hueco", "mod"):
            self.soltar(dest["ruta"], d["nodo"], origen)
        elif self._rechazar_flanco_en_temp(dest["base"], d["nodo"]):
            self.update()
            return
        elif origen is not None:
            nueva = _mover_en_posicion(self.arbol, origen, dest["base"], dest["indice"], self.valor)
            if nueva != self.arbol:
                self._fijar(0, nueva)
        else:
            nodo_ins = d["nodo"]
            # Reemplazar constante raíz 1/0 sola al soltar un bloque nuevo (maqueta)
            if not self.valor and dest["base"] == () and self.arbol is not None and self.arbol["k"] == "const":
                self._fijar(0, copy.deepcopy(nodo_ins))
            else:
                nueva = _insertar_en_posicion(self.arbol, dest["base"], dest["indice"], nodo_ins, self.valor)
                if nueva != self.arbol:
                    self._fijar(0, nueva)
                    if dest.get("r_par") is not None:
                        self._destino_par = (0,) + tuple(dest["r_par"])
                        self._sincronizar_motor()
                        self.invalidar()
                        self.seleccion_cambiada.emit()
        self.update()

    def _fondo(self, p: QPainter) -> None:
        """Lienzo `.block-rail` limpio de borde a borde (`#fbfdff` + puntos de 16 px, sin marco exterior)."""
        self._sincronizar_motor()
        p.fillRect(self.rect(), QColor("#fbfdff"))
        p.drawTiledPixmap(self.rect(), _rejilla(), QPoint(0, 0))
        if self._propio and self._fuera:
            p.setPen(QPen(QColor("#c62828"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(self.rect().adjusted(1, 1, -1, -1))

    def _extra(self, p: QPainter) -> None:
        if self._hueco_sel is not None:
            r = next((r for r, ruta, n in self._bloques if ruta == self._hueco_sel), None)
            if r is not None:
                self.motor.trazo_seleccion(p, r.adjusted(-0.5, -0.5, 0.5, 0.5), 2.0)
        if self._resalte_mas is not None:
            self.motor.trazo_seleccion(p, self._resalte_mas.adjusted(-1, -1, 1, 1), 2.4)
        md = self._marca_drop
        if md is not None and md.get("rect") is not None:
            rect: QRectF = md["rect"]
            tipo = md["tipo"]
            if tipo in ("antes", "despues"):
                lx = rect.left() - 3.0 if tipo == "antes" else rect.right() + 3.0
                p.setPen(QPen(QColor(estilo.ACENTO), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(lx, rect.top() - 2.0), QPointF(lx, rect.bottom() + 2.0))
            elif tipo in ("dentro", "hueco", "mod"):
                p.setPen(QPen(QColor(estilo.ACENTO), 2.0))
                p.setBrush(QColor(11, 110, 117, 26))
                p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 6, 6)
        if self.arbol is None and self._cajas:
            c, x, y = self._cajas[0]
            r_hint = QRectF(x, y, c.w, c.h)
            p.setPen(QPen(QColor("#b9c7d6"), 1.5, Qt.PenStyle.DashLine))
            p.setBrush(QColor(255, 255, 255, 204))
            p.drawRoundedRect(r_hint.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
            p.setFont(self.motor.f)
            p.setPen(QColor("#5b6b7d"))
            p.drawText(r_hint.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, GUIA)


# -- el programador: paleta y área ------------------------------------------------------------------
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


class AsaAncho(QWidget):
    """El borde arrastrable del catálogo: entre éste y el área, una franja fina que cambia el ancho del catálogo al arrastrarla."""
    movida = Signal(int)  # el ancho que se pide para el catálogo
    soltada = Signal(int)  # el ancho con que se quedó

    def __init__(self, catalogo: QWidget) -> None:
        super().__init__()
        self.catalogo = catalogo
        self._inicio: tuple[int, int] | None = None
        self.setFixedWidth(estilo.E2)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setToolTip("Arrastra para cambiar el ancho del catálogo")
        self.setAccessibleName("Borde del catálogo")

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        if self._inicio is None and not self.underMouse():
            return
        p = QPainter(self)
        p.setPen(QPen(QColor(estilo.ACENTO if self._inicio is not None else "#9aa9ba"), 1.5, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        x, h = self.width() / 2, self.height()
        p.drawLine(QPointF(x, h / 2 - 12), QPointF(x, h / 2 + 12))
        p.end()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._inicio = (int(event.globalPosition().x()), self.catalogo.width())
            self.update()

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if self._inicio is not None:
            self.movida.emit(self._inicio[1] + int(event.globalPosition().x()) - self._inicio[0])

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if self._inicio is not None:
            self._inicio = None
            self.update()
            self.soltada.emit(self.catalogo.width())


class _ZonaPapelera(QLabel):
    """Aviso y zona de papelera (`.trash-dropzone`): al soltar un bloque arrastrado desde el carril, lo elimina."""

    def __init__(self, lienzo: AreaBloques) -> None:
        super().__init__()
        self.lienzo = lienzo
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802
        d = self.lienzo._datos_mime(event.mimeData())
        if d is not None and d.get("origen") is not None and d.get("grupo") == self.lienzo.grupo:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()

    def dropEvent(self, event: Any) -> None:  # noqa: N802
        d = self.lienzo._datos_mime(event.mimeData())
        if d is None or d.get("origen") is None or d.get("grupo") != self.lienzo.grupo:
            return
        _ARRASTRE["resuelto"] = True
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
        origen = tuple(d["origen"])
        if len(self.lienzo._bloques_sel) > 1 and (0,) + origen in self.lienzo._bloques_sel:
            self.lienzo.quitar_elegido()
        else:
            self.lienzo.quitar(origen)


class BarraContextual(QFrame):
    """Barra contextual inferior del carril (`.ctx-bar`): muestra pista sin selección, o controles del bloque o selección múltiple.
    Usa distribución con ajuste de línea (`FlowLayout`) para que ningún botón se recorte a media pantalla."""

    def __init__(self, lienzo: AreaBloques) -> None:
        super().__init__()
        self.lienzo = lienzo
        self.setObjectName("barraContextual")
        self.setStyleSheet(
            f"QFrame#barraContextual {{ background: {estilo.SUPERFICIE_2}; border: 0; "
            f"border-radius: {estilo.R_CONTROL}px; }}"
            f"QFrame#barraContextual QLabel#ctxTexto {{ color: #4a5b6e; font-size: 11.5px; background: transparent; border: 0; }}"
            f"QFrame#barraContextual QPushButton {{ min-height: 23px; max-height: 25px; padding: 0 9px; border-radius: 4px; "
            f"border: 1px solid #cdd6e0; background: #f6f8fb; color: #4a5b6e; font-size: 11.5px; font-weight: 600; }}"
            f"QFrame#barraContextual QPushButton:hover:enabled {{ background: #e4ecf3; color: #16263a; }}"
            f"QFrame#barraContextual QPushButton[activo=\"true\"] {{ background: {estilo.ACENTO}; border-color: {estilo.ACENTO_OSCURO}; color: #ffffff; }}"
            f"QFrame#barraContextual QPushButton[activo=\"true\"]:hover {{ background: {estilo.ACENTO_OSCURO}; color: #ffffff; }}"
            f"QFrame#barraContextual QPushButton[peligro=\"true\"]:hover:enabled {{ background: #fdecea; border-color: #e5a5a5; color: #c62828; }}"
        )
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(10, 6, 10, 6)
        raiz.setSpacing(5)

        self.l_texto = QLabel()
        self.l_texto.setObjectName("ctxTexto")
        self.l_texto.setWordWrap(True)
        raiz.addWidget(self.l_texto)

        self._caja_btns = QWidget(self)
        self._caja_btns.setObjectName("ctxBtns")
        self._caja_btns.setStyleSheet("QWidget#ctxBtns { background: transparent; }")
        self._flow = FlowLayout(self._caja_btns, sep=5)
        raiz.addWidget(self._caja_btns)

        def _btn(texto: str, tip: str, peligro: bool = False) -> QPushButton:
            b = QPushButton(texto, self._caja_btns)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            if peligro:
                b.setProperty("peligro", True)
            self._flow.addWidget(b)
            return b

        self.b_normal = _btn("Normal", "Quitar negación y flancos")
        self.b_not = _btn("NOT", "Negar el bloque seleccionado (barra superior)")
        self.b_sube = _btn("↑", "Flanco de subida")
        self.b_baja = _btn("↓", "Flanco de bajada")
        self.b_not_int = _btn("NOT señal", "Negar la señal o fórmula evaluada dentro del temporizador")
        self.b_envolver = _btn("Envolver ( … )", "Envuelve o desenvuelve en paréntesis")
        self.b_salir = _btn("Salir a raíz", "Volver a insertar fuera del paréntesis")
        self.b_quitar = _btn("Quitar", "Quitar la selección (Supr)", peligro=True)

        self.b_normal.clicked.connect(self.lienzo.quitar_modificadores)
        self.b_not.clicked.connect(lambda: self.lienzo.aplicar_modificador("no"))
        self.b_sube.clicked.connect(lambda: self.lienzo.aplicar_modificador("sube"))
        self.b_baja.clicked.connect(lambda: self.lienzo.aplicar_modificador("baja"))
        self.b_not_int.clicked.connect(self.lienzo.alternar_not_interior_temp)
        self.b_envolver.clicked.connect(self.lienzo.envolver_elegido)
        self.b_salir.clicked.connect(self.lienzo.salir_a_raiz)
        self.b_quitar.clicked.connect(self.lienzo.quitar_elegido)
        self.actualizar()

    @staticmethod
    def _marcar(b: QPushButton, activo: bool) -> None:
        if bool(b.property("activo")) != activo:
            b.setProperty("activo", activo)
            b.style().unpolish(b)
            b.style().polish(b)

    def _ajustar_btns(self) -> None:
        visibles = any(not b.isHidden() for b in (
            self.b_normal, self.b_not, self.b_sube, self.b_baja,
            self.b_not_int, self.b_envolver, self.b_salir, self.b_quitar,
        ))
        self._caja_btns.setVisible(visibles)
        if visibles:
            w = max(self.width() - 22, 160)
            h = max(25, self._flow.heightForWidth(w))
            self._caja_btns.setFixedHeight(h)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._ajustar_btns()

    def actualizar(self) -> None:
        info = self.lienzo.info_seleccion()
        count = info["count"]
        en_grupo = info["en_grupo"]
        if count == 0:
            self.l_texto.setText(
                "Insertando dentro de ( … ) · Pulsa variables para añadir o sal a raíz."
                if en_grupo else
                "Clic en un bloque para editar · Ctrl+clic varios para negar, flanco o envolver en ( … ) · Supr o arrastrar fuera para quitar."
            )
            for b in (self.b_normal, self.b_not, self.b_sube, self.b_baja,
                      self.b_not_int, self.b_envolver, self.b_quitar):
                b.hide()
            self.b_salir.setVisible(en_grupo)
            self._ajustar_btns()
            return
        mods = info["mods"]
        puede_mod = info["puede_mod"]
        es_par = info["es_par"]
        es_temp = info["es_temp"]
        if count > 1:
            self.l_texto.setText(f"Seleccionados: {count} bloques")
        else:
            self.l_texto.setText(f"Seleccionado: {info['nombre']}")
        for b in (self.b_normal, self.b_not, self.b_sube, self.b_baja):
            b.setVisible(puede_mod)
        if puede_mod:
            self._marcar(self.b_normal, not mods)
            self._marcar(self.b_not, "no" in mods)
            self._marcar(self.b_sube, "sube" in mods)
            self._marcar(self.b_baja, "baja" in mods)
        self.b_not_int.setVisible(es_temp)
        if es_temp:
            self._marcar(self.b_not_int, bool(info.get("temp_neg_int")))
        self.b_envolver.setText("Quitar paréntesis" if es_par else "Envolver ( … )")
        self._marcar(self.b_envolver, count > 1)
        self.b_envolver.show()
        self.b_salir.setVisible(en_grupo)
        self.b_quitar.setText(f"Quitar ({count})" if count > 1 else "Quitar")
        self.b_quitar.show()
        self._ajustar_btns()


class _MarcoCarril(QWidget):
    """Contenedor `.block-rail` con fondo de puntos `#fbfdff`, área de bloques arriba y barra contextual abajo."""

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#fbfdff"))
        p.drawTiledPixmap(self.rect(), _rejilla(), QPoint(0, 0))
        p.end()


class Programador(QWidget):
    """Editor de bloques de precisión 2.0.1 (`.editor-grid`):
    - Izquierda (`208 px`, `#ffffff`, borde derecho `#cdd6e0`): buscador siempre visible + catálogo plano.
    - Derecha: cinta fija `.op-ribbon` arriba + carril `.block-rail` con flujo directo, zona de papelera y barra contextual `.ctx-bar`."""

    cambiado = Signal(str)
    franja_cambiada = Signal()
    PALETA_MIN, PALETA_INICIAL, PALETA_MAX = 140, 208, 340
    CLAVE_ANCHO = "formulador/ancho_catalogo"
    CUERPO_MIN = 220

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], historial: bool = False,
                 grupo: str | None = None, valor: bool = False, compacto: bool = False) -> None:
        super().__init__()
        self.fuente, self.historial, self.valor = fuente, historial, valor
        self.compacto = compacto
        self._elemento_seleccionado = None
        self.grupo = grupo or f"programador-{id(self)}"
        self.al_deshacer: Callable[[], Any] | None = None
        self.al_rehacer: Callable[[], Any] | None = None
        self._pila: list[Any] = []
        self._rehecho: list[Any] = []
        self.en_fila = False
        self._adoptada = False

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        lay = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._lay_cuerpo = lay
        raiz.addLayout(lay, 1)

        from .banda_bloques import BandaBloques, BotonCompacto

        # -- Columna izquierda: catálogo con búsqueda fija siempre visible (.catalog-pane) --
        self._col_catalogo = QFrame()
        self._col_catalogo.setObjectName("colCatalogo")
        self._col_catalogo.setStyleSheet(
            "QFrame#colCatalogo { background: #ffffff; border: 0; border-right: 1px solid #cdd6e0; }"
            "QFrame#cajaBuscarCatalogo { background: #f8fafc; border: 0; border-bottom: 1px solid #e5ebf2; }"
            "QFrame#cajaBuscarCatalogo QLineEdit { min-height: 24px; max-height: 26px; font-size: 12px; "
            "padding: 2px 8px; border-radius: 4px; border: 1px solid #cdd6e0; background: #ffffff; color: #16263a; }"
            "QFrame#cajaBuscarCatalogo QLineEdit:focus { border-color: #0b6e75; }"
        )
        col = QVBoxLayout(self._col_catalogo)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        if valor:
            self.paleta = PaletaBloques(fuente, self.grupo, columna=True, valor=True)
            self._filtro_num = QLineEdit()
            self._filtro_num.setPlaceholderText("Filtrar numéricas…")
            self._filtro_num.setClearButtonEnabled(True)
            self._filtro_num.textChanged.connect(self.paleta.filtrar_texto)
            campo_buscar = self._filtro_num
        else:
            from .paleta_variables import PaletaVariables
            self.paleta = PaletaVariables(fuente, self.grupo, columna=True)
            self.paleta.filtro_externo = True
            self.paleta.filtro.setPlaceholderText("Filtrar variables…")
            campo_buscar = self.paleta.filtro
            self._filtro_num = None

        self._caja_buscar = QFrame()
        self._caja_buscar.setObjectName("cajaBuscarCatalogo")
        bl = QVBoxLayout(self._caja_buscar)
        bl.setContentsMargins(8, 7, 8, 7)
        bl.setSpacing(0)
        bl.addWidget(campo_buscar)
        col.addWidget(self._caja_buscar)

        self.t_catalogo = QLabel("Variables numéricas" if valor else "Variables y etapas")
        self.t_catalogo.hide()  # reemplazado por el buscador superior siempre visible (maqueta 2.0.1)

        self.paleta.elegido.connect(self._elegido)
        self._sc_paleta = _desplazable(self.paleta)
        self._sc_paleta.setStyleSheet("QScrollArea { background: #ffffff; border: 0; }")
        col.addWidget(self._sc_paleta, 1)
        lay.addWidget(self._col_catalogo)

        self.asa = AsaAncho(self._col_catalogo)
        self.asa.setFixedWidth(4)
        self.asa.movida.connect(self.poner_ancho_catalogo)
        self.asa.soltada.connect(self._recordar_ancho)
        lay.addWidget(self.asa)
        if not valor:
            self.paleta.geometria_cambiada.connect(self._medir_paleta)

        # -- Columna derecha: cinta .op-ribbon + carril .block-rail con .ctx-bar --
        derecha = QVBoxLayout()
        derecha.setContentsMargins(0, 0, 0, 0)
        derecha.setSpacing(0)

        self._fila_herr = QWidget()
        self._fila_herr.hide()
        self.herramientas = QWidget(self)
        self.herramientas.hide()

        self.banda = BandaBloques(fuente, self.grupo, valor)
        self.b_copiar = BotonCompacto("Copiar", self.banda)
        self.b_pegar = BotonCompacto("Pegar", self.banda)
        self.b_deshacer = BotonCompacto("↶", self.banda)
        self.b_rehacer = BotonCompacto("↷", self.banda)
        self.b_limpiar = BotonCompacto("Limpiar", self.banda)
        for b, ayuda in (
            (self.b_copiar, "Copia la fórmula entera (Ctrl+C copia el bloque elegido)"),
            (self.b_pegar, "Pega la fórmula copiada"),
            (self.b_deshacer, "Deshacer (Ctrl+Z)"),
            (self.b_rehacer, "Rehacer (Ctrl+Y)"),
            (self.b_limpiar, "Vacía la fórmula"),
        ):
            b.setToolTip(ayuda)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.banda.anadir_herramientas([self.b_copiar, self.b_pegar, self.b_deshacer, self.b_rehacer, self.b_limpiar], flujo=True)
        self.categorias = self.banda.categorias
        self.banda.alto_cambiado.connect(self._banda_cambiada)
        derecha.addWidget(self.banda)

        self.marco_carril = _MarcoCarril()
        mc = QVBoxLayout(self.marco_carril)
        mc.setContentsMargins(0, 0, 0, 10)
        mc.setSpacing(8)

        self.lienzo = AreaBloques(fuente, self.grupo, valor)
        self.lienzo.modificado.connect(self._tras_cambio)
        self.lienzo.avisa.connect(self._avisar)
        self.lienzo.arrastrando.connect(self._arrastrando)
        sc_lienzo = _desplazable(self.lienzo)
        sc_lienzo.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }")
        mc.addWidget(sc_lienzo, 1)

        # Aviso / Zona discreta de papelera sobre la barra contextual
        caja_pie = QWidget()
        caja_pie.setStyleSheet("background: transparent;")
        cpl = QVBoxLayout(caja_pie)
        cpl.setContentsMargins(12, 0, 12, 0)
        cpl.setSpacing(6)
        self.aviso = _ZonaPapelera(self.lienzo)
        self._estilo_aviso(False)
        self.aviso.setVisible(False)
        cpl.addWidget(self.aviso)

        self.barra_ctx = BarraContextual(self.lienzo)
        cpl.addWidget(self.barra_ctx)
        mc.addWidget(caja_pie)
        derecha.addWidget(self.marco_carril, 1)

        # Alias para compatibilidad con código/pruebas que inspeccionan `b_envolver` y `b_quitar`
        self.b_envolver = self.barra_ctx.b_envolver
        self.b_quitar = self.barra_ctx.b_quitar
        self.pie = cpl

        lay.addLayout(derecha, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.banda.insertar.connect(self.lienzo.insertar)
        self.b_copiar.clicked.connect(self.lienzo.copiar_formula)
        self.b_pegar.clicked.connect(self.lienzo.pegar_formula)
        self.b_deshacer.clicked.connect(self.deshacer)
        self.b_rehacer.clicked.connect(self.rehacer)
        self.b_limpiar.clicked.connect(self.lienzo.limpiar)
        self.lienzo.seleccion_cambiada.connect(self._herramientas_al_dia)
        self.lienzo.modificado.connect(self._herramientas_al_dia)
        QApplication.clipboard().dataChanged.connect(self._herramientas_al_dia)
        if historial:
            for atajo, f in (("Ctrl+Z", self.deshacer), ("Ctrl+Shift+Z", self.rehacer), ("Ctrl+Y", self.rehacer)):
                s = QShortcut(QKeySequence(atajo), self)
                s.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                s.activated.connect(f)
        self.poner_ancho_catalogo(self._ancho_recordado())
        self.escalar()
        self._cargar_paleta("vnum" if valor else "variables")

    # -- herramientas y aspecto
    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        self.poner_ancho_catalogo(self._ancho_recordado())
        self._cargar_paleta(self.paleta.clave)
        self._herramientas_al_dia()

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        super().hideEvent(event)

    def escalar(self) -> None:
        """Cambió la escala de letra y de controles: los botones y la banda se miden otra vez."""
        self.banda.escalar()
        self.lienzo.invalidar()
        self.paleta.invalidar()
        self._herramientas_al_dia()
        self.updateGeometry()

    def _herramientas_al_dia(self, *_: Any) -> None:
        """Actualiza los botones de la cinta y la barra contextual `.ctx-bar`."""
        hay = self.lienzo.arbol is not None
        self.b_copiar.setEnabled(hay)
        self.b_limpiar.setEnabled(hay)
        self.b_pegar.setEnabled(self.lienzo.puede_pegar())
        if self.historial:
            self.b_deshacer.setEnabled(bool(self._pila))
            self.b_rehacer.setEnabled(bool(self._rehecho))
        self.barra_ctx.actualizar()

    def _banda_cambiada(self) -> None:
        self.updateGeometry()
        self.franja_cambiada.emit()

    def _estilo_aviso(self, arrastre: bool) -> None:
        if arrastre:
            self.aviso.setStyleSheet(
                f"color: #c62828; background: {estilo.ERROR_FONDO}; border: 1.5px dashed #e5a5a5; "
                f"border-radius: 6px; padding: 6px 12px; font-size: 12px; font-weight: 600;"
            )
        else:
            self.aviso.setStyleSheet("color: #b45309; font-size: 11.5px; background: transparent;")

    def _arrastrando(self, en_curso: bool) -> None:
        if en_curso:
            self._estilo_aviso(True)
            self.aviso.setText("Suelta fuera del carril para quitar este bloque")
            self.aviso.setVisible(True)
        else:
            self._estilo_aviso(False)
            self._poner_aviso("")

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return False

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        alto = self.banda.height() + self.CUERPO_MIN
        return QSize((200 if self.en_fila else self._col_catalogo.width() + self.asa.width() + 260), alto)

    def sizeHint(self) -> QSize:  # noqa: N802
        natural = super().sizeHint()
        return QSize(natural.width(), self.minimumSizeHint().height())

    # -- el catálogo: su ancho (con borde arrastrable) y su disposición
    @staticmethod
    def _ajustes() -> Any:
        from .paleta_variables import PaletaVariables
        return PaletaVariables.ajustes

    def _ancho_recordado(self) -> int:
        ajustes = self._ajustes()
        try:
            return int(ajustes.value(self.CLAVE_ANCHO, self.PALETA_INICIAL)) if ajustes is not None else self.PALETA_INICIAL
        except (TypeError, ValueError):
            return self.PALETA_INICIAL

    def poner_ancho_catalogo(self, ancho: int) -> None:
        """Ancho del catálogo, entre `PALETA_MIN` y `PALETA_MAX` (y sin quitarle al área sus 180 px)."""
        tope = self.PALETA_MAX if self.width() < 400 else max(self.PALETA_MIN, min(self.PALETA_MAX, self.width() - 180 - self.asa.width()))
        ancho = max(self.PALETA_MIN, min(int(ancho), tope))
        if self.en_fila or ancho == self._col_catalogo.width():
            return
        self._col_catalogo.setFixedWidth(ancho)
        self.updateGeometry()

    def _recordar_ancho(self, ancho: int) -> None:
        ajustes = self._ajustes()
        if ajustes is not None:
            ajustes.setValue(self.CLAVE_ANCHO, int(ancho))
            ajustes.sync()

    def modo_fila(self, fila: bool) -> None:
        """Con la ventana baja (P1) el catálogo va **en una sola fila** sobre el área, con desplazamiento horizontal, en vez de en una
        columna a su izquierda: el panel necesita así mucho menos alto. `en_fila` dice cuál está activo."""
        if fila == self.en_fila:
            return
        self.en_fila = fila
        self._lay_cuerpo.setDirection(QBoxLayout.Direction.TopToBottom if fila else QBoxLayout.Direction.LeftToRight)
        self.paleta.columna, self.paleta.una_fila = not fila, fila
        self._sc_paleta.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if fila else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._sc_paleta.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff if fila else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.asa.setVisible(not fila)
        if not fila:
            self._sc_paleta.setMinimumHeight(0)
            self._sc_paleta.setMaximumHeight(16777215)
            self.paleta.setMinimumWidth(80)
            self._sc_paleta.setMinimumWidth(0)
            self._sc_paleta.setMaximumWidth(16777215)
            self._col_catalogo.setMaximumWidth(16777215)
            self._col_catalogo.setMinimumWidth(0)
            self.poner_ancho_catalogo(self._ancho_recordado())
        else:
            self._col_catalogo.setMinimumWidth(0)
            self._col_catalogo.setMaximumWidth(16777215)
        self._cargar_paleta(self.paleta.clave)
        self.updateGeometry()
        self.franja_cambiada.emit()

    # -- paleta
    def _cargar_paleta(self, clave: str) -> None:
        """Pone las fichas del catálogo (las variables y etapas, o las numéricas)."""
        self.paleta.cargar(clave)
        self._medir_paleta()

    def _medir_paleta(self) -> None:
        if not self.en_fila:  # en columna, el ancho es el que dejó el borde arrastrable
            return
        self.paleta.invalidar()  # una fila: el ancho es el de todas las fichas juntas (el catálogo se desplaza a los lados) y el alto, el de una fila más la barra
        self.paleta.setMinimumWidth(int(self.paleta.ancho_necesario(10 ** 5)))
        ancho = 10 ** 5
        if not self.valor and self.paleta.clave == "variables" and not self.paleta.bloques():
            ancho = max(80, self._sc_paleta.viewport().width())
        alto = self.paleta.heightForWidth(ancho) + self._sc_paleta.horizontalScrollBar().sizeHint().height()
        if self._sc_paleta.minimumHeight() != alto:
            self._sc_paleta.setFixedHeight(alto)
            self.franja_cambiada.emit()

    def _elegido(self, nodo: dict[str, Any]) -> None:
        """Se pulsó una ficha del catálogo: va a la fórmula."""
        self.lienzo.insertar(nodo)

    def seleccionar_elemento(self, identificador) -> None:
        """Vacía la búsqueda al cambiar de elemento, aunque su fórmula coincida."""
        if identificador != self._elemento_seleccionado:
            self._elemento_seleccionado = identificador
            if not self.valor:
                self.paleta.filtro.clear()

    def opciones(self, cajon: str) -> list[tuple[str, str]]:
        """(texto, valor) de lo que ofrece un desplegable de la paleta: variables booleanas de un papel, o etapas."""
        variables, etapas = self.fuente()
        if cajon == "etapa":
            return [(etapa_visible(x), x) for x in dict.fromkeys(etapas)]
        return [(n, n) for n, (r, t) in variables.items() if r == PAPEL[cajon] and t == "bool"]

    def refrescar(self) -> None:
        """Las variables o las etapas del modelo cambiaron (se creó, renombró, quitó o cambió de papel o tipo una
        variable): la paleta y los desplegables y colores del área se ponen al día en el acto. Sin cambios, no hace nada."""
        firma = repr(self.fuente())
        if firma == getattr(self, "_firma", None):
            return
        self._firma = firma
        self._cargar_paleta(self.paleta.clave)
        self.lienzo.invalidar()

    # -- texto <-> bloques
    def texto(self) -> str:
        return self.lienzo.texto()

    def poner(self, texto: str) -> None:
        """Muestra un texto (el guardado, o lo escrito a mano) como bloques, sin emitir `cambiado`. Si no se puede
        analizar, los bloques no cambian y se avisa. Si es el mismo que ya hay, no toca el árbol (salvo para releer los
        bloques de texto: una variable pudo crearse)."""
        variables, etapas = self.fuente()
        self._firma = repr((variables, etapas))
        self._cargar_paleta(self.paleta.clave)
        self.lienzo.invalidar()
        try:
            if normalizar_espacios(texto) == self.texto():
                nuevo_ = self.lienzo.arbol
                if con_texto(nuevo_):
                    releido = (texto_a_arbol_valor if self.valor else texto_a_arbol)(texto, variables, etapas)
                    if arbol_a_texto(releido) == self.texto():
                        nuevo_ = releido
            else:
                nuevo_ = (texto_a_arbol_valor if self.valor else texto_a_arbol)(texto, variables, etapas)
                self._pila.clear()
                self._rehecho.clear()
        except ValueError as e:
            self._avisar(f"No se puede pasar a bloques: {e}")
            return
        self._avisar("")
        self._fijar_arbol(nuevo_)

    def faltan_huecos(self) -> int:
        """Cuántos huecos le faltan a la fórmula del área (0 sin fórmula)."""
        return faltan(self.lienzo.arbol)

    def marcar_huecos(self, resaltar: bool) -> None:
        self.lienzo.marcar_huecos(resaltar)

    def _fijar_arbol(self, arbol: dict[str, Any] | None) -> None:
        self.lienzo.poner_arbol(arbol)
        self._herramientas_al_dia()

    def _avisar(self, texto: str) -> None:
        self._poner_aviso(texto)

    def _poner_aviso(self, texto: str) -> None:
        self.aviso.setText(texto)
        self.aviso.setVisible(bool(texto))

    def _tras_cambio(self) -> None:
        if self.historial:
            self._pila.append(self.lienzo.previo)
            self._rehecho.clear()
        self._avisar("")
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
