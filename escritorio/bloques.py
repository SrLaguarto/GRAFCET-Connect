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
_DURACION = re.compile(r"(\d+(?:[.,]\d+)?)\s*(us|µs|μs|ms|s)")
_TOP_PREC = {"or": 1, "and": 2, "not": 3, **{c: 4 for c in CMP.values()}}


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


def faltan(raiz: dict[str, Any] | None) -> int:
    """Cuántos huecos le faltan a la fórmula: los que `arbol_a_texto` escribe como «?» (huecos vacíos y fichas sin nombre). Sin fórmula
    (raíz vacía) no falta nada: no hay qué completar."""
    def cuenta(n: dict[str, Any] | None) -> int:
        if n is None:
            return 1
        k = n["k"]
        propio = (k in ("var", "etapa", "vnum", "cmp") and not n["n"]) or (k == "texto" and not n["s"].strip())
        return int(propio) + sum(cuenta(n[c]) for c in hijos(n))
    return 0 if raiz is None else cuenta(raiz)


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
        return f"{_citar(n['n']) if n['n'] else '?'} {n['op']} {n['v'].strip() or '0'}"
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
COLORES = {"entrada": estilo.ACENTO, "salida": estilo.SIMULACION, "interna": estilo.ORIGEN_MEMORIA, "etapa": estilo.EDICION,
           "operador": "#486078", "comparacion": "#398C9E", "tiempo": "#A38636", "texto": "#6B7280", "error": estilo.ERROR,
           "y": "#5F7F0B", "o": "#B83DBA",  # «y» (oliva) y «o» (fucsia): operadores, pero cada uno con su color
           "constante": "#8A5A44"}  # las fichas 1 (verdadero) y 0 (falso): su propia categoría, no se pierden entre los operadores
CATEGORIAS_BANDA = (("operador", "Operadores"), ("tiempo", "Temp."), ("comparacion", "Comp."),
                    ("constante", "Const."))  # (abreviadas para caber en una fila; el nombre entero sale en su ayuda)  # la banda de botones del programador de condiciones
CATEGORIAS_BANDA_VALOR = (("aritm", "Operadores"), ("numero", "Const."))  # la del programador de valores (modo «valor»)
_PAPEL_CAT = {"input": "entrada", "output": "salida", "internal": "interna"}
TAG_ORIGEN = {"entrada": "E", "salida": "S", "interna": "M"}  # la letra de origen de una ficha (las etapas ya se llaman X1, X2…)
PADX, PADX_PILA, PADV, GAP, FILA = 8, 6, 4, 4, 4  # relleno lateral y vertical de un contenedor, hueco entre piezas y entre filas
ALTO = 20  # alto de las piezas (desplegables, campos)
HUECO_W, HUECO_H = 34, 24
PAREN_W = 8  # ancho de cada paréntesis del bloque «( )»; miden lo que el bloque que encierran
PAD_PAR, GAP_PAR = 4, 3  # relleno y hueco del bloque «( )»: poco, porque se anida mucho
SANGRIA = {"no": 8, "sube": 8, "baja": 8, "temp": 8}  # el hijo de un bloque que envuelve, algo hundido
CHAFLAN = 5  # lado del chaflán de una ficha
BARRA = 4  # ancho de la barra de origen
RELLENO_FICHA = 6
R_PIEZA = 4  # radio de las cajas pequeñas (huecos, campos de texto, el hueco pendiente)
MARGEN = 6
MIME = "application/x-grafcet-bloque"
MIME_FORMULA = "application/x-grafcet-formula"
MIME_TIPO = "application/x-grafcet-formula-tipo"  # de qué programador viene lo copiado: «condicion» o «valor» (lo mira el botón Pegar)
_ARRASTRE = {"resuelto": False}  # el arrastre en curso (solo hay uno): si algún programador lo recibió


def alto_ficha() -> int:
    """Alto de una ficha: 28 px a escala normal (los controles compactos menos 2), con la escala de la aplicación."""
    return estilo.ALTO_CONTROL_COMPACTO - 2


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
        self._est = {"": (self.fb, self.mb, 0), "y": (self.fb, self.mb, 12), "o": (self.fb, self.mb, 12),
                     "barra": (self.fg, self.mg, 0), "pp": (self.fp, self.mp, 0), "br": (self.fg, self.mg, 0),
                     "op": (self.fg, self.mg, 0), "ins": (self.fm, self.mm, 12), "insw": (self.fm, self.mm, 12),
                     "pf": (self.fm, self.mm, 10), "pend": (self.fb, self.mb, 0), "const": (self.fg, self.mg, 0)}
        self.nat: dict[tuple, float] = {}
        self.botones = True  # el «+» del «y» y el «o»: en la paleta no hay
        self.fijo = False  # en el catálogo, una ficha por elemento: el nombre ya va elegido y no lleva desplegable (▾)

    def reiniciar(self) -> None:
        self.vars, self.etapas = self.fuente()
        self.nat = {}
        self.recortadas: list[tuple[QRectF, str]] = []  # (sitio, texto entero) de las piezas con el texto recortado

    # -- qué lleva cada bloque
    @staticmethod
    def _insignia(n: dict[str, Any]) -> tuple[str, str]:
        """Cómo se escribe un retardo (t/X, X/t, t1/X/t2) y su estilo; sin tiempos, la advertencia de que no escribe nada."""
        if n["t1"] and n["t2"]:
            return "t1/X/t2", "ins"
        return ("t/X", "ins") if n["t1"] else ("X/t", "ins") if n["t2"] else ("sin retardo", "insw")

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
                    out.append(("txt", k, "· Y" if k == "y" else "+ O"))
                out.append(("hijo", c))
            if self.botones and len(hs) < MAX_ENTRADAS:
                out.append(("boton", "mas", "+"))
            return out
        if k in MODIFICADORES:  # una cadena de modificadores sobre algo que no es una variable: sus insignias y, a su lado, lo que modifica
            mods, _ = self._cadena(n)
            return [("mod", m, {"no": "NOT", "sube": "↑", "baja": "↓"}[m]) for m in mods] + [("hijo", ("a",) * len(mods))]
        if k == "temp":
            t, estilo_ins = self._insignia(n)
            base = _efectivo(n["a"])
            parens = not (_atomo(base) or (base is not None and base["k"] in MODIFICADORES and _atomo(base["a"])))
            return ([("txt", estilo_ins, t), ("campo", "t1", n["t1"], "t1"), ("txt", "barra", "/")]
                    + ([("txt", "pp", "(")] if parens else []) + [("hijo", "a")] + ([("txt", "pp", ")")] if parens else [])
                    + [("txt", "barra", "/"), ("campo", "t2", n["t2"], "t2")])
        if k == "cmp":
            return [("txt", "br", "["), ("drop", "n", n["n"] or "elegir"), ("drop", "op", OP_VISIBLE[n["op"]]),
                    ("campo", "v", n["v"], "valor"), ("txt", "br", "]")]
        if k == "num":
            return [("campo", "v", n["v"], "número")]
        if k == "vnum":
            return [("drop", "n", n["n"] or "elegir")]
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
            return _Pieza("txt", e[1], vis, False, medidas.horizontalAdvance(vis) + extra, ALTO, e[2] if vis != e[2] else "")
        if tipo == "boton":
            return _Pieza("boton", e[1], e[2], False, 22, 22)
        if tipo == "mod":  # la insignia de un flanco o de una negación sobre una cadena: se pulsa para cambiarla o quitarla
            return _Pieza("mod", e[1], e[2], False, self.mm.horizontalAdvance(e[2]) + 12, ALTO)
        if tipo == "paren":
            return _Pieza("paren", e[1], e[2], False, PAREN_W, 16)
        texto = e[2] or (e[3] if tipo == "campo" else "")
        vacio = tipo == "campo" and not e[2]
        if tipo == "campo":
            vis = self.mm.elidedText(texto, Qt.TextElideMode.ElideRight, max(maxw - 14, 20))
            return _Pieza(tipo, e[1], vis, vacio, max(36, self.mm.horizontalAdvance(vis) + 16), ALTO, texto if vis != texto else "")
        metricas = self.mm if e[1] == "op" else self.ms
        extra = 14 if e[1] == "op" else 18  # el desplegable lleva su ▾; el operador de una comparación, una caja pequeña
        vis = metricas.elidedText(texto, Qt.TextElideMode.ElideRight, max(maxw - extra, 20))
        return _Pieza(tipo, e[1], vis, vacio, metricas.horizontalAdvance(vis) + extra + (6 if e[1] == "op" else 0), ALTO,
                      texto if vis != texto else "")

    def natural(self, n: dict[str, Any] | None, ruta: tuple) -> float:
        if n is None:
            return HUECO_W
        if ruta not in self.nat:
            if n["k"] == "par":
                w = 2 * PAD_PAR + 2 * PAREN_W + 2 * GAP_PAR + self.natural(n["a"], ruta + ("a",))
            elif self._es_simple(n):
                w = self._caja_simple(n, ruta, 10 ** 6).w
            else:
                ws = [self.natural(*self._sub(n, e[1], ruta)) if e[0] == "hijo" else self.pieza(e).w for e in self.elementos(n)]
                w = 2 * PADX + sum(ws) + GAP * (len(ws) - 1)
            self.nat[ruta] = w
        return self.nat[ruta]

    @staticmethod
    def _es_simple(n: dict[str, Any]) -> bool:
        """Si el bloque se dibuja como una ficha o una cápsula de una sola fila (sin bloques dentro)."""
        return n["k"] in ("const", "cmp", "num", "vnum", "texto") or ficha_cadena(n) is not None

    def caja(self, n: dict[str, Any] | None, ruta: tuple, ancho: float) -> _Caja:
        if n is None:
            return _Caja(None, ruta, HUECO_W, HUECO_H)
        if n["k"] == "par":
            return self._caja_par(n, ruta, ancho)
        if n["k"] == "ar":
            return self._caja_ar(n, ruta, ancho)
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
        if n["k"] in ("y", "o"):  # no caben en una fila: los operandos y conectores fluyen, saltando de línea solo cuando no caben
            px = PADX_PILA
            interior = max(ancho - 2 * px, 40)
            partes = []
            for e in elems:
                partes.append(self.caja(*self._sub(n, e[1], ruta), min(self.natural(*self._sub(n, e[1], ruta)), interior))
                              if e[0] == "hijo" else self.pieza(e))
            lineas: list[list[Any]] = [[]]
            x = 0.0
            for i, p in enumerate(partes):
                if lineas[-1] and x + p.w > interior:
                    lineas.append([])
                    x = 0.0
                lineas[-1].append(p)
                x += p.w + GAP
            y, derecha = float(PADV), 0.0
            for linea in lineas:
                h, x = max(p.h for p in linea), float(px)
                for p in linea:
                    c.items.append((x, y + (h - p.h) / 2, p))
                    x += p.w + GAP
                derecha = max(derecha, x - GAP)
                y += h + FILA
            c.h, c.w = y - FILA + PADV, derecha + px
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
        """Una ficha (variable o etapa, con sus modificadores si los lleva), una constante, una comparación, una cápsula numérica o un
        texto: una sola fila de alto fijo. Con una ficha con modificadores, el bloque es el más externo de la cadena (el que se arrastra
        y se selecciona) y las piezas responden a la variable de dentro."""
        k, alto = n["k"], alto_ficha() - (6 if self.fijo else 0)  # (en el catálogo, filas más compactas)
        if k in MODIFICADORES or k in ("var", "etapa"):
            return self._caja_ficha(n, ruta, ancho, alto)
        c = _Caja(n, ruta, 0, alto, self.categoria(n))
        elems = self.elementos(n)
        if k == "const":
            c.forma, x0 = "hundida", 12
        elif k == "cmp":
            c.forma, x0 = "ficha", RELLENO_FICHA
        elif k in ("num", "vnum"):
            c.forma, x0 = "capsula", 10 + 6 + 4  # el punto de origen
        else:
            c.forma, x0 = "texto", 6
        piezas = [self.pieza(e, max(ancho - 2 * x0 - 6, 24) if k != "cmp" else 100000) for e in elems]
        if self.fijo and k == "vnum" and n["n"]:  # en el catálogo, el nombre ya va elegido
            vis = self.ms.elidedText(n["n"], Qt.TextElideMode.ElideRight, max(ancho - x0 - 8, 24))
            piezas = [_Pieza("txt", "nom", vis, False, self.ms.horizontalAdvance(vis), ALTO, n["n"] if vis != n["n"] else "")]
        x = float(x0)
        for p in piezas:
            c.items.append((x, (alto - p.h) / 2, p))
            x += p.w + (2 if k == "cmp" else 0)
        c.w = x - (2 if k == "cmp" else 0) + (x0 if k in ("const", "cmp", "texto") else 8)
        return c

    def _caja_ficha(self, n: dict[str, Any], ruta: tuple, ancho: float, alto: float) -> _Caja:
        mods, hoja = self._cadena(n)
        destino = ruta + ("a",) * len(mods)
        c = _Caja(n, ruta, 0, alto, self.categoria(hoja) if hoja is not None else "operador")
        c.destino, c.mods = destino, mods
        flanco = next((m for m in mods if m != "no"), None)
        if hoja is None:  # «[NOT | pulsa o arrastra variable…]»: la ficha que espera su variable
            c.forma = "pendiente"
            sufijo = " ".join({"no": "NOT", "sube": "↑", "baja": "↓"}[m] for m in mods)
            p1 = self.pieza(("txt", "pf", sufijo))
            p2 = self.pieza(("txt", "pend", "pulsa o arrastra variable…"), max(ancho - p1.w - 24, 40))
            c.items = [(8, (alto - p1.h) / 2, p1), (8 + p1.w + 6, (alto - p2.h) / 2, p2)]
            c.w = 8 + p1.w + 6 + p2.w + 8
            return c
        c.forma = "ficha"
        if "no" in mods:
            c.negada = "todo" if flanco is not None and mods.index("no") < mods.index(flanco) else "nombre"
        x = float(BARRA + RELLENO_FICHA)
        if flanco is not None:
            ins = _Pieza("mod", flanco, "↑" if flanco == "sube" else "↓", False, 22, ALTO, ruta=destino)
            c.items.append((x, (alto - ins.h) / 2, ins))
            x += ins.w + GAP
        nombre = etapa_visible(hoja["n"]) if hoja["k"] == "etapa" else hoja["n"]
        tag = "" if hoja["k"] == "etapa" else TAG_ORIGEN.get(c.cat, TAG_ORIGEN.get(_PAPEL_CAT.get(hoja.get("papel"), ""), ""))
        ancho_tag = (self.mb.horizontalAdvance(tag) + GAP) if tag else 0.0
        fila = self.fijo and bool(hoja["n"])  # en el catálogo: una fila con la letra de origen a la derecha
        flecha = 0 if fila else 18
        disponible = max(ancho - x - RELLENO_FICHA - ancho_tag - flecha, 20)
        texto = nombre or "elegir"
        vis = self.ms.elidedText(texto, Qt.TextElideMode.ElideRight, disponible)
        w = (0 if fila else ancho_tag) + self.ms.horizontalAdvance(vis) + flecha
        tipo = "txt" if fila else "drop"
        p = _Pieza(tipo, "nom" if tipo == "txt" else "n", vis, not nombre, w, ALTO, texto if vis != texto else "",
                   ruta=destino, extra=(tag if not fila else "", COLORES[c.cat]) if tag or c.cat else None)
        c.items.append((x, (alto - p.h) / 2, p))
        c.w = x + p.w + RELLENO_FICHA
        if fila:
            if tag:
                c.w += ancho_tag
            if ancho < 10 ** 5:
                c.w = max(c.w, ancho)
            if tag:
                t = _Pieza("txt", "tagd", tag, False, ancho_tag - GAP, ALTO, extra=(tag, COLORES[c.cat]))
                c.items.append((c.w - RELLENO_FICHA - t.w, (alto - t.h) / 2, t))
        return c

    def _caja_par(self, n: dict[str, Any], ruta: tuple, ancho: float) -> _Caja:
        """El bloque «( )»: un paréntesis a cada lado del bloque que encierra, tan altos como él (también si éste se apila)."""
        clave = ruta + ("a",)
        interior = max(ancho - 2 * PAD_PAR - 2 * PAREN_W - 2 * GAP_PAR, 40)
        h = self.caja(n["a"], clave, min(self.natural(n["a"], clave), interior))
        h.sin_fondo = n["a"] is not None and n["a"]["k"] == "ar"  # una operación dentro de «( )»: ya está rodeada
        c = _Caja(n, ruta, 2 * PAD_PAR + 2 * PAREN_W + 2 * GAP_PAR + h.w, h.h + 2 * PADV, self.categoria(n))
        c.forma = "par"
        c.items = [(PAD_PAR, PADV, _Pieza("paren", "izq", "(", False, PAREN_W, h.h)),
                   (PAD_PAR + PAREN_W + GAP_PAR, PADV, h),
                   (PAD_PAR + PAREN_W + 2 * GAP_PAR + h.w, PADV, _Pieza("paren", "der", ")", False, PAREN_W, h.h))]
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
                    elems.append(("txt", "op", OP_ARIT[m["op"]]))
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
        """Una operación aritmética: sus elementos en una fila si caben y, si no, en varias, pasando de línea sin dejar un
        operador al final de una (va con el operando que le sigue)."""
        elems, fantasmas = self._plano(n)
        c = _Caja(n, ruta, 0, 0, self.categoria(n))
        c.forma = "ar"
        px = PADX if self.natural(n, ruta) <= ancho else PADX_PILA
        interior = max(ancho - 2 * px, 40)
        partes: list[Any] = []
        for e in elems:
            if e[0] == "hijo":
                nodo, r = self._sub(n, e[1], ruta)
                partes.append(self.caja(nodo, r, min(self.natural(nodo, r), interior)))
            else:
                partes.append(self.pieza(e))
        unidades: list[list[int]] = []  # un operador va con el operando que le sigue
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
        y, derecha = float(PADV), 0.0
        for linea in lineas:
            h = max(partes[i].h for i in linea)
            x = float(px)
            for i in linea:
                p = partes[i]
                c.items.append((x, y + (h - p.h) / 2, p))
                rects[i] = (x, y + (h - p.h) / 2, p.w, p.h)
                x += p.w + GAP
            derecha = max(derecha, x - GAP)
            y += h + FILA
        c.h, c.w = y - FILA + PADV, derecha + px
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
        if c.nodo is None:  # un hueco: caja hundida y punteada
            p.setPen(QPen(QColor(estilo.BORDE_CONTROL), 1.2, Qt.PenStyle.DashLine))
            p.setBrush(QColor(estilo.SUPERFICIE))
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

    def _pintar_caja(self, p: QPainter, c: _Caja, r: QRectF, padre: QColor | None) -> QColor | None:
        """El fondo y el contorno del bloque, según su forma; devuelve el fondo que ven sus hijos."""
        forma, cat = c.forma, c.cat
        error = cat == "error"
        ra = r.adjusted(0.5, 0.5, -0.5, -0.5)
        if forma in ("ficha", "hundida"):
            p.setPen(QPen(QColor(estilo.ERROR if error else estilo.BORDE_CONTROL), 1))
            p.setBrush(QColor(estilo.ERROR_FONDO if error else estilo.SUPERFICIE_2 if forma == "hundida" else estilo.SUPERFICIE))
            contorno = self.poligono_ficha(ra)
            p.drawPolygon(contorno)
            if forma == "ficha" and c.mods is not None and c.nodo is not None and c.cat in COLORES and c.items \
                    and (c.items[-1][2].tipo in ("drop", "txt") and c.items[-1][2].clave in ("n", "nom")):
                camino = QPainterPath()
                camino.addPolygon(contorno)
                p.save()
                p.setClipPath(camino)
                p.fillRect(QRectF(r.left(), r.top(), BARRA, r.height()), QColor(COLORES[cat]))
                p.restore()
            if c.negada == "todo":  # la barra de la negación cubre el flanco y la variable
                p.fillRect(QRectF(r.left() + 8, r.top() + 2, r.width() - 14, 2), QColor(estilo.TINTA))
            return padre
        if forma == "capsula":
            p.setPen(QPen(QColor(estilo.ERROR if error else estilo.BORDE_CONTROL), 1))
            p.setBrush(QColor(estilo.ERROR_FONDO if error else estilo.SUPERFICIE))
            p.drawRoundedRect(ra, r.height() / 2, r.height() / 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(COLORES.get(cat, COLORES["texto"])))
            p.drawEllipse(QPointF(r.left() + 13, r.center().y()), 3, 3)
            return padre
        if forma == "pendiente":
            p.setPen(QPen(QColor(estilo.ACENTO), 1.5, Qt.PenStyle.DashLine))
            p.setBrush(QColor(estilo.ACENTO_SUAVE))
            p.drawRoundedRect(ra, R_PIEZA, R_PIEZA)
            return padre
        if forma == "texto":
            p.setPen(QPen(QColor(estilo.ERROR if error else estilo.BORDE_CONTROL), 1))
            p.setBrush(QColor(estilo.ERROR_FONDO if error else estilo.SUPERFICIE_2))
            p.drawRoundedRect(ra, R_PIEZA, R_PIEZA)
            return padre
        if c.sin_fondo:
            return padre
        fondo = QColor(estilo.SUPERFICIE) if forma == "temp" else self._fondo_hijo(padre)
        if forma in ("y", "o"):
            p.setPen(QPen(QColor(COLORES[forma]), 1.2))
        elif forma == "temp":
            p.setPen(QPen(QColor(estilo.TINTA_3), 1.2, Qt.PenStyle.DashLine))
        else:
            p.setPen(QPen(QColor(estilo.BORDE_CONTROL), 1))
        p.setBrush(fondo)
        p.drawRoundedRect(ra, 14 if forma == "ar" else 6, 14 if forma == "ar" else 6)
        if forma == "cadena" and "no" in c.mods:  # una negación sobre un bloque: la barra superior sobre todo él
            p.fillRect(QRectF(r.left() + 3, r.top(), r.width() - 6, 3), QColor(estilo.TINTA))
        return fondo

    def _pintar_pieza(self, p: QPainter, it: _Pieza, r: QRectF, c: _Caja | None = None) -> None:
        tinta, borde = QColor(estilo.TINTA), QColor(estilo.BORDE_CONTROL)
        centro = Qt.AlignmentFlag.AlignCenter
        if it.tipo == "txt" and it.clave == "tagd":  # la letra de origen, a la derecha de la fila del catálogo
            p.setFont(self.fb)
            p.setPen(QColor(it.extra[1]))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, it.texto)
            return
        if it.tipo == "txt" and it.clave == "nom":  # el nombre de una ficha del catálogo (sin desplegable)
            self._pintar_nombre(p, it, r, c, False)
            return
        if it.tipo == "txt":
            fuente = self._est.get(it.clave, self._est[""])[0]
            p.setFont(fuente)
            if it.clave in ("y", "o"):  # el conector de un «y» o un «o»: una pastilla con la letra de su color
                p.setPen(QPen(QColor(estilo.BORDE), 1))
                p.setBrush(QColor(estilo.SUPERFICIE))
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
                p.setPen(QColor(COLORES[it.clave]))
            elif it.clave in ("ins", "insw", "pf"):
                aviso = it.clave == "insw"
                p.setPen(QPen(QColor(estilo.AVISO_BORDE), 1) if aviso else Qt.PenStyle.NoPen)
                p.setBrush(QColor(estilo.AVISO_FONDO if aviso else estilo.EDICION if it.clave == "ins" else estilo.SUPERFICIE))
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
                p.setPen(QColor(estilo.AVISO if aviso else "#FFFFFF" if it.clave == "ins" else estilo.TINTA))
            elif it.clave in ("barra", "pp", "br"):
                p.setPen(QColor(estilo.TINTA_3))
            elif it.clave == "pend":
                p.setPen(QColor(estilo.ACENTO_OSCURO))
            elif it.clave == "op":
                p.setPen(QColor(estilo.TINTA_2))
            else:
                p.setPen(tinta)
            p.drawText(r, centro, it.texto)
            return
        if it.tipo == "paren":  # un paréntesis alto y curvo
            izq = it.clave == "izq"
            punta, panza = (r.right() - 2, r.left() + 1.5) if izq else (r.left() + 2, r.right() - 1.5)
            camino = QPainterPath(QPointF(punta, r.top() + 1))
            camino.cubicTo(QPointF(panza, r.top() + r.height() * 0.28), QPointF(panza, r.bottom() - r.height() * 0.28),
                           QPointF(punta, r.bottom() - 1))
            p.setPen(QPen(QColor(estilo.TINTA_3), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(camino)
            return
        if it.tipo == "boton":  # «+» añade un hueco
            p.setPen(QPen(borde, 1, Qt.PenStyle.DashLine))
            p.setBrush(QColor(estilo.SUPERFICIE))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
            p.setFont(self.fb)
            p.setPen(QColor(estilo.TINTA_2))
            p.drawText(r, centro, it.texto)
            return
        if it.tipo == "mod":  # la insignia de un flanco (↑, ↓) o de una negación: se pulsa para cambiarla
            p.setPen(QPen(borde, 1))
            p.setBrush(QColor(estilo.SUPERFICIE_2))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
            p.setFont(self.fm)
            p.setPen(tinta)
            p.drawText(r, centro, it.texto)
            return
        if it.tipo == "campo":  # un valor o un retardo que se teclea: una pastilla
            p.setPen(QPen(borde, 1))
            p.setBrush(QColor(estilo.SUPERFICIE_2))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), r.height() / 2, r.height() / 2)
            p.setFont(self.fm)
            p.setPen(QColor(estilo.TINTA_3 if it.vacio else estilo.TINTA))
            p.drawText(r.adjusted(5, 0, -5, 0), centro, it.texto)
            return
        if it.clave == "op":  # el operador de una comparación: una caja pequeña con su ▾
            p.setPen(QPen(borde, 1))
            p.setBrush(QColor(estilo.SUPERFICIE_2))
            p.drawRoundedRect(r.adjusted(0.5, 2.5, -0.5, -2.5), 3, 3)
            p.setFont(self.fm)
            p.setPen(tinta)
            p.drawText(QRectF(r.left() + 2, r.top(), r.width() - 12, r.height()), centro, it.texto)
            p.setFont(self.f)
            p.setPen(QColor(estilo.TINTA_3))
            p.drawText(QRectF(r.right() - 12, r.top(), 10, r.height()), centro, "▾")
            return
        self._pintar_nombre(p, it, r, c, True)

    def _pintar_nombre(self, p: QPainter, it: _Pieza, r: QRectF, c: _Caja | None, desplegable: bool) -> None:
        """El nombre de una variable, etapa o cantidad: su letra de origen (si la ficha la lleva), el texto y, si se elige, la ▾."""
        x = r.left()
        if it.extra and it.extra[0]:
            p.setFont(self.fb)
            p.setPen(QColor(it.extra[1]))
            ancho = self.mb.horizontalAdvance(it.extra[0])
            p.drawText(QRectF(x, r.top(), ancho, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, it.extra[0])
            x += ancho + GAP
        p.setFont(self.fs)
        p.setPen(QColor(estilo.ERROR if c is not None and c.cat == "error" and c.forma in ("ficha", "capsula") else estilo.TINTA))
        fin = r.right() - (16 if desplegable else 0)
        texto = QRectF(x, r.top(), max(fin - x, 1), r.height())
        p.drawText(texto, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, it.texto)
        if c is not None and c.negada and it.extra is not None:  # la barra de la negación sobre el nombre
            ancho_texto = min(self.ms.horizontalAdvance(it.texto), texto.width())
            p.fillRect(QRectF(x, r.top() + 2, ancho_texto, 2), QColor(estilo.TINTA))
        if desplegable:
            p.setFont(self.f)
            p.setPen(QColor(estilo.TINTA_3))
            p.drawText(QRectF(r.right() - 16, r.top(), 12, r.height()), Qt.AlignmentFlag.AlignCenter, "▾")

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


GUIA = "pulsa o arrastra un bloque…"  # lo que dice el área vacía
_REJILLA: list[QPixmap] = []


def _rejilla() -> QPixmap:
    """El mosaico de 16 px con un punto, que da el fondo del área."""
    if not _REJILLA:
        pm = QPixmap(16, 16)
        pm.fill(QColor(estilo.SUPERFICIE))
        p = QPainter(pm)
        p.setPen(QColor(estilo.BORDE))
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
        elif n["k"] == "num":
            v = texto.strip().replace(",", ".")
            if not re.fullmatch(r"-?\d+(?:\.\d+)?", v):
                self.avisa.emit("Escriba un número (por ejemplo 5 o 2.5).")
                return False
            n[clave] = v
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
    """El catálogo: una ficha por cada variable (o etapa) que existe, una tras otra (pasan de línea) o en columna. Ya van elegidas: se
    arrastran tal cual o se pulsan para insertarlas en la fórmula (`elegido`). Los operadores, temporizadores, comparaciones y constantes
    están en la banda de categorías (`banda_bloques.py`)."""

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str = "",
                 columna: bool = False, valor: bool = False) -> None:
        super().__init__(fuente, grupo)
        self.motor.botones = False
        self.motor.fijo = True
        self.valor = valor  # el catálogo de un valor numérico: sus variables numéricas
        self.clave = "vnum" if valor else "entrada"
        self.columna = columna  # uno debajo de otro (el programador); si no, uno tras otro, pasando de línea
        self.una_fila = False  # uno tras otro sin pasar de línea (el programador en una ventana baja: el área se desplaza a los lados)
        self.cargar(self.clave)

    def _maqueta(self, ancho: float) -> tuple[list[tuple[_Caja, float, float]], float]:
        x, y, lh, out = float(MARGEN), float(MARGEN), 0.0, []
        for i, n in enumerate(self._raices):
            c = self.motor.caja(n, (i,), min(self.motor.natural(n, (i,)), ancho - 2 * MARGEN))
            if x > MARGEN and (self.columna or (not self.una_fila and x + c.w > ancho - MARGEN)):
                x, y, lh = float(MARGEN), y + lh + (2 if self.columna else GAP * 2), 0.0
            out.append((c, x, y))
            x += c.w + GAP * 2
            lh = max(lh, c.h)
        return out, y + lh + MARGEN

    @staticmethod
    def _orden(nombre: str) -> list[Any]:
        """Orden natural y sin distinguir mayúsculas: I2 antes que I10; las etapas, por su número."""
        return [(0, int(x), "") if x.isdigit() else (1, 0, x.lower()) for x in re.split(r"(\d+)", nombre) if x]

    def cargar(self, clave: str) -> None:
        """Pone las fichas de la clave (entradas, salidas, memorias, etapas o variables numéricas) con las variables y etapas del
        modelo: una por cada elemento que existe (etapas por número, variables por nombre), ya elegido, que se arrastra tal cual;
        sin elementos, una ficha vacía."""
        self.clave = clave
        self.motor.reiniciar()
        v, etapas = self.motor.vars, list(dict.fromkeys(self.motor.etapas))
        if clave == "vnum":
            numericas = sorted((nom for nom, (_, t) in v.items() if t != "bool"), key=self._orden)
            nodos = [nuevo("vnum", n=nom) for nom in numericas] or [nuevo("vnum", n=None)]
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
        self._raices = [None]
        self.previo: dict[str, Any] | None = None
        self._bloque_sel: tuple | None = None
        self._hueco_sel: tuple | None = None  # el hueco vacío seleccionado (se quita con Supr)
        self._propio = False  # se arrastra un bloque de aquí
        self._fuera = False  # y el puntero está fuera del área: soltarlo lo quita
        self.arrastrando.connect(self._al_arrastrar)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setAcceptDrops(True)
        self.setToolTip("Para quitar un bloque, arrástrelo fuera o pulse Supr")

    @property
    def arbol(self) -> dict[str, Any] | None:
        return self._raices[0]

    def poner_arbol(self, arbol: dict[str, Any] | None) -> None:
        self._raices = [copy.deepcopy(arbol)]
        self._bloque_sel = None
        self.invalidar()

    def texto(self) -> str:
        return arbol_a_texto(self.arbol)

    def _maqueta(self, ancho: float) -> tuple[list[tuple[_Caja, float, float]], float]:
        if self.arbol is None:
            c = _Caja(None, (0,), min(max(HUECO_W, self.motor.m.horizontalAdvance(GUIA) + 30), ancho - 2 * MARGEN), alto_ficha())
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
            if origen is None and nodo["k"] in MODIFICADORES and nodo["a"] is None \
                    and ficha_cadena(obtener(self.arbol, ruta)) is not None:
                nueva = alternar_modificador(self.arbol, ruta, nodo["k"])  # sobre una ficha o su hueco pendiente: se aplica a la ficha
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
            self.setFocus()
            self.update()
            self.seleccion_cambiada.emit()

    def insertar(self, nodo: dict[str, Any]) -> bool:
        """Pulsar un bloque del catálogo o de la banda: lo pone en el hueco o el bloque seleccionado (un bloque que envuelve envuelve al
        elegido; uno que no, lo sustituye) y, sin elección, en el primer hueco libre (o de raíz si la fórmula está vacía). Una constante
        sin elección es la fórmula entera (P-IMP-69). Si no hay sitio, avisa y no inserta. Devuelve si cambió algo."""
        if nodo["k"] in MODIFICADORES and nodo["a"] is None:
            return self.aplicar_modificador(nodo["k"])
        ruta = self._sitio_elegido()
        if ruta is None:
            if nodo["k"] == "const":
                return self.sustituir(nodo)
            ruta = () if self.arbol is None else primer_hueco(self.arbol)
            if ruta is None:
                self.avisa.emit("No queda ningún hueco libre: elija un bloque de la fórmula para sustituirlo o quítelo.")
                return False
        if not self.soltar(ruta, nodo):
            return False
        self._elegir_ficha(ruta)
        return True

    def aplicar_modificador(self, clase: str) -> bool:
        """NOT, ↑ o ↓ sobre la ficha elegida, en el orden en que se pulsan. Sin elección, un modificador con su hueco pendiente en el
        primer hueco libre («NOT ?»), que la siguiente variable pulsada rellena."""
        ruta = self._sitio_elegido()
        if ruta is None:
            ruta = () if self.arbol is None else primer_hueco(self.arbol)
            if ruta is None:
                self.avisa.emit("No queda ningún hueco libre: elija una ficha para aplicarle el modificador.")
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
        return True

    def _modificador(self, ruta: tuple, clase: str) -> None:
        """Se pulsó la insignia de una ficha: un flanco pasa al otro (↑ por ↓), la negación se quita."""
        r = tuple(self._partir(ruta)[1])
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
            self._fijar(0, retirar(self.arbol, ruta))

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
        self.previo = self._raices[i]
        super()._fijar(i, nueva)
        self.modificado.emit()
        self.seleccion_cambiada.emit()

    def envolver_elegido(self) -> bool:
        """«Envolver ( … )»: el bloque elegido pasa a ir entre paréntesis."""
        ruta = self._sitio_elegido()
        if ruta is None or obtener(self.arbol, ruta) is None:
            return False
        nueva = envolver(self.arbol, ruta, "par")
        self._fijar(0, nueva)
        self._bloque_sel = (0,) + tuple(ruta)
        self.seleccion_cambiada.emit()
        self.update()
        return True

    def quitar_elegido(self) -> bool:
        """«Quitar (Supr)»: quita el bloque elegido."""
        sel = self._bloque_sel
        if sel is None:
            return False
        self.quitar(sel)
        return True

    def hay_seleccion(self) -> bool:
        return self._bloque_sel is not None

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._hueco_sel = None
        self._bloque_sel = self._bloque_en(event.position())
        if self._bloque_sel is not None: self.setFocus()
        if self._pieza_en(event.position()) is None:  # un clic en un hueco vacío lo selecciona
            ruta = self.ruta_en(event.position())
            if ruta is not None and self.hueco_quitable(ruta):
                self._hueco_sel = tuple(ruta)
                self.setFocus()
        self.update()
        self.seleccion_cambiada.emit()

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
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self._bloque_sel is not None:
            ruta, self._bloque_sel = self._bloque_sel, None
            self.quitar(ruta); event.accept(); return
        super().keyPressEvent(event)

    def event(self, ev: Any) -> bool:
        if ev.type() == QEvent.Type.ShortcutOverride and (
            ev.matches(QKeySequence.StandardKey.Copy) or ev.matches(QKeySequence.StandardKey.Paste)
        ):
            ev.accept()
            return True
        if ev.type() == QEvent.Type.ShortcutOverride and (self._hueco_sel is not None or self._bloque_sel is not None) \
                and ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            ev.accept()  # Supr con un hueco seleccionado es para el hueco, no para el atajo «Borrar» de la ventana
            return True
        return super().event(ev)

    def contextMenuEvent(self, ev: Any) -> None:  # noqa: N802
        ruta = self.ruta_en(QPointF(ev.pos()))
        if ruta is not None and self.hueco_quitable(ruta):
            menu = QMenu(self)
            menu.addAction("Quitar hueco", lambda: self.quitar_hueco_en(ruta))
            menu.exec(ev.globalPos())

    def soltar_en_mas(self, ruta: tuple, nodo: dict[str, Any], origen: tuple | None = None) -> bool:
        """Suelta un bloque sobre el «+» del «y» o el «o» de `ruta`: lo añade en un hueco nuevo."""
        try:
            nueva = soltar_en_mas(self.arbol, tuple(self._partir(ruta)[1]), nodo,
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

    def dragMoveEvent(self, event: Any) -> None:  # noqa: N802
        d = self._datos_mime(event.mimeData())
        if d is None:
            return
        mas = self._mas_en(event.position())
        self._objetivo = None if mas else self.ruta_en(event.position())
        self._resalte_mas = mas[0] if mas else None
        self.update()
        event.setDropAction(Qt.DropAction.MoveAction if d.get("origen") is not None and d["grupo"] == self.grupo
                            else Qt.DropAction.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event: Any) -> None:  # noqa: N802
        self._objetivo = None
        self._resalte_mas = None
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
        if d is None:
            return
        mas = self._mas_en(event.position())
        ruta = None if mas else self.ruta_en(event.position())
        origen = tuple(d["origen"]) if d.get("origen") is not None and d["grupo"] == self.grupo else None
        _ARRASTRE["resuelto"] = True
        event.setDropAction(Qt.DropAction.MoveAction if origen is not None else Qt.DropAction.CopyAction)
        event.accept()
        if mas:  # sobre el «+»: en un hueco nuevo
            self.soltar_en_mas(mas[1], d["nodo"], origen)
        else:
            self.soltar(None if ruta is None else tuple(ruta[1:]), d["nodo"], origen)
        self.update()

    def _fondo(self, p: QPainter) -> None:
        """Un lienzo de puntos (la rejilla de la maqueta); con un bloque en arrastre fuera de él, el borde en rojo."""
        p.fillRect(self.rect(), QColor(estilo.SUPERFICIE))
        p.drawTiledPixmap(QRect(1, 1, self.width() - 2, self.height() - 2), _rejilla(), QPoint(-1, -1))
        fuera = self._propio and self._fuera
        p.setPen(QPen(QColor(estilo.ERROR if fuera else estilo.BORDE), 2 if fuera else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), estilo.R_M, estilo.R_M)

    def _extra(self, p: QPainter) -> None:
        if self._hueco_sel is not None or self._bloque_sel is not None:
            seleccion = self._hueco_sel if self._hueco_sel is not None else self._bloque_sel
            r = next((r for r, ruta, n in self._bloques if ruta == seleccion), None)
            if r is not None:
                self.motor.trazo_seleccion(p, r.adjusted(-0.5, -0.5, 0.5, 0.5), 2.2)
        if getattr(self, "_resalte_mas", None) is not None:  # el «+» donde caería lo que se arrastra
            self.motor.trazo_seleccion(p, self._resalte_mas.adjusted(-1, -1, 1, 1), 2.6)
        if self.arbol is None:
            c, x, y = self._cajas[0]
            p.setFont(self.motor.f)
            p.setPen(QColor(estilo.TINTA_3))
            p.drawText(QRectF(x, y, c.w, c.h), Qt.AlignmentFlag.AlignCenter, GUIA)


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
        self.setToolTip("Arrastre para cambiar el ancho del catálogo")
        self.setAccessibleName("Borde del catálogo")

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setPen(QPen(QColor(estilo.ACENTO if self._inicio is not None else estilo.BORDE_CONTROL), 1.5, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        x, h = self.width() / 2, self.height()
        p.drawLine(QPointF(x, h / 2 - 10), QPointF(x, h / 2 + 10))
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


class Programador(QWidget):
    """Programador por bloques: a la izquierda, el catálogo de variables y etapas, siempre a la vista y con un borde arrastrable; a su
    derecha, la banda de categorías (Operadores, Temporizadores, Comparaciones, Constantes: clic o arrastre, y las herramientas Copiar
    fórmula, Pegar y Limpiar) y, debajo, el área de trabajo con la fórmula (en línea si cabe) con el aviso. `fuente()` devuelve las
    variables {nombre: (papel, tipo)} y las etapas (en notación X) del modelo en curso. `cambiado(texto)` se emite en cada cambio
    hecho con bloques (no al llamar a `poner`). Con `historial`, Ctrl+Z y Ctrl+Mayús+Z deshacen y rehacen los cambios de bloques; sin
    él, el deshacer lo pone quien lo usa (`al_deshacer`, `al_rehacer`)."""

    cambiado = Signal(str)
    franja_cambiada = Signal()  # la banda cambió de alto (al cambiar de ancho): el panel que lo contiene puede necesitar más
    PALETA_MIN, PALETA_INICIAL, PALETA_MAX = 110, 170, 360  # el ancho del catálogo: el de apertura y los límites del borde arrastrable
    CLAVE_ANCHO = "formulador/ancho_catalogo"  # donde se recuerda (`QSettings`), compartido por todos los programadores
    CUERPO_MIN = 68  # alto mínimo del catálogo y el área

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
        # El catálogo ocupa todo el alto a la izquierda (el alto de la ventana de Propiedades no sobra: así se ven al menos seis fichas); a
        # su derecha, la banda de categorías (con las herramientas Copiar fórmula, Pegar y Limpiar), el área y el aviso
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(5)
        lay = QBoxLayout(QBoxLayout.Direction.LeftToRight)  # (en ventanas bajas, el catálogo encima: `modo_fila`)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._lay_cuerpo = lay
        self.en_fila = False
        from .banda_bloques import BandaBloques, BotonCompacto
        # Las herramientas (Copiar fórmula, Pegar, Limpiar) van en una fila sobre la banda, a la derecha; la ventana de Propiedades las lleva
        # a la franja del título de su tarjeta (`adoptar_herramientas`) y esta fila se oculta
        self._fila_herr = QWidget()
        fh = QHBoxLayout(self._fila_herr)
        fh.setContentsMargins(0, 0, 0, 0)
        fh.setSpacing(6)
        fh.addStretch(1)
        self.herramientas = QWidget(self)
        hl = QHBoxLayout(self.herramientas)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)
        self._adoptada = False
        self.b_copiar = BotonCompacto("Copiar fórmula", self.herramientas)
        self.b_pegar = BotonCompacto("Pegar", self.herramientas)
        self.b_limpiar = BotonCompacto("Limpiar", self.herramientas)
        for b, ayuda in ((self.b_copiar, "Copia la fórmula entera (Ctrl+C copia el bloque elegido)"),
                         (self.b_pegar, "Pega la fórmula copiada, sustituyendo la actual (Ctrl+V la pega en el hueco o el bloque elegido)"),
                         (self.b_limpiar, "Vacía la fórmula")):
            b.setToolTip(ayuda)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.banda = BandaBloques(fuente, self.grupo, valor)
        # Un valor numérico solo tiene «Limpiar» (como la maqueta): lo que se arma es corto y no se copia de una ventana a otra
        for b in ([self.b_limpiar] if valor else [self.b_copiar, self.b_pegar, self.b_limpiar]):
            hl.addWidget(b)
        fh.addWidget(self.herramientas)
        self.banda.anadir_herramientas([self.b_copiar, self.b_pegar, self.b_limpiar], flujo=False)
        if valor:
            self.b_copiar.hide()
            self.b_pegar.hide()
        self.categorias = self.banda.categorias  # los rótulos de las categorías de la banda, por su clave
        self.banda.alto_cambiado.connect(self._banda_cambiada)
        # El catálogo: su título y, debajo, las fichas
        if valor:
            self.paleta = PaletaBloques(fuente, self.grupo, columna=True, valor=True)
        else:
            from .paleta_variables import PaletaVariables
            self.paleta = PaletaVariables(fuente, self.grupo, columna=True)
        self.paleta.elegido.connect(self._elegido)
        self._sc_paleta = _desplazable(self.paleta)
        self.t_catalogo = QLabel("Variables numéricas" if valor else "Variables y etapas")
        self.t_catalogo.setStyleSheet(f"color: {estilo.TINTA_2}; font-weight: 600; background: transparent; padding: 0 {estilo.E1}px;")
        self.t_catalogo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._col_catalogo = QWidget()
        col = QVBoxLayout(self._col_catalogo)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(estilo.E1)
        col.addWidget(self.t_catalogo)
        col.addWidget(self._sc_paleta, 1)
        lay.addWidget(self._col_catalogo)
        self.asa = AsaAncho(self._col_catalogo)
        self.asa.movida.connect(self.poner_ancho_catalogo)
        self.asa.soltada.connect(self._recordar_ancho)
        lay.addWidget(self.asa)
        if not valor:
            self.paleta.geometria_cambiada.connect(self._medir_paleta)
        # El área de trabajo y, debajo, el aviso
        derecha = QVBoxLayout()
        derecha.setSpacing(4)
        raiz.addWidget(self._fila_herr)
        raiz.addWidget(self.banda)  # la banda a todo el ancho, sobre el catálogo y el área (como la maqueta)
        raiz.addLayout(lay, 1)
        self.lienzo = AreaBloques(fuente, self.grupo, valor)
        self.lienzo.modificado.connect(self._tras_cambio)
        self.lienzo.avisa.connect(self._avisar)
        self.lienzo.arrastrando.connect(self._arrastrando)
        derecha.addWidget(_desplazable(self.lienzo), 1)  # el área es la que crece
        pie = QHBoxLayout()
        self.pie = pie
        pie.setContentsMargins(0, 0, 0, 0)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self._estilo_aviso(False)
        self.aviso.setVisible(False)
        self.aviso.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # no impone su ancho
        pie.addWidget(self.aviso, 1)
        from .banda_bloques import BotonCompacto
        self.b_envolver = BotonCompacto("Envolver ( … )", self)
        self.b_quitar = BotonCompacto("Quitar (Supr)", self)
        self.b_envolver.setToolTip("Envuelve el bloque elegido entre paréntesis")
        self.b_quitar.setToolTip("Quita el bloque elegido (también Supr, o arrastrarlo fuera)")
        self.banda.anadir_herramientas([self.b_envolver, self.b_quitar], flujo=False)  # (solo su tamaño)
        pie.addWidget(self.b_envolver, 0, Qt.AlignmentFlag.AlignRight)
        pie.addWidget(self.b_quitar, 0, Qt.AlignmentFlag.AlignRight)
        derecha.addLayout(pie)
        lay.addLayout(derecha, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.banda.insertar.connect(self.lienzo.insertar)
        self.b_copiar.clicked.connect(self.lienzo.copiar_formula)
        self.b_pegar.clicked.connect(self.lienzo.pegar_formula)
        self.b_limpiar.clicked.connect(self.lienzo.limpiar)
        self.b_envolver.clicked.connect(self.lienzo.envolver_elegido)
        self.b_quitar.clicked.connect(self.lienzo.quitar_elegido)
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
    def adoptar_herramientas(self, anfitrion: QLayout) -> None:
        """Lleva las herramientas (Copiar fórmula, Pegar, Limpiar) a `anfitrion` (la franja del título de una tarjeta) y quita su fila."""
        if not self._adoptada or self.herramientas.parentWidget() is not anfitrion.parentWidget():
            anfitrion.addWidget(self.herramientas)
        self._adoptada = True
        self._fila_herr.hide()
        self.herramientas.setVisible(self.isVisible())

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self._adoptada:
            self.herramientas.show()
        self.poner_ancho_catalogo(self._ancho_recordado())
        self._cargar_paleta(self.paleta.clave)
        self._herramientas_al_dia()

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        super().hideEvent(event)
        if self._adoptada:
            self.herramientas.hide()

    def escalar(self) -> None:
        """Cambió la escala de letra y de controles: los botones y la banda se miden otra vez."""
        self.banda.escalar()
        self.lienzo.invalidar()
        self.paleta.invalidar()
        self._herramientas_al_dia()
        self.updateGeometry()

    def _herramientas_al_dia(self, *_: Any) -> None:
        """Copiar y Limpiar valen con una fórmula; Pegar, con una fórmula copiada que sirva en esta área."""
        hay = self.lienzo.arbol is not None
        self.b_copiar.setEnabled(hay)
        self.b_limpiar.setEnabled(hay)
        self.b_pegar.setEnabled(self.lienzo.puede_pegar())
        self.b_envolver.setEnabled(self.lienzo.hay_seleccion())
        self.b_quitar.setEnabled(self.lienzo.hay_seleccion())

    def _banda_cambiada(self) -> None:
        self.updateGeometry()
        self.franja_cambiada.emit()

    def _estilo_aviso(self, arrastre: bool) -> None:
        """El aviso del pie: ámbar para un aviso; mientras se arrastra un bloque fuera del área, el aviso de que soltarlo lo quita."""
        if arrastre:
            self.aviso.setStyleSheet(f"color: {estilo.ERROR}; background: {estilo.ERROR_FONDO}; border: 1px dashed {estilo.ERROR}; "
                                     f"border-radius: {estilo.R_S}px; padding: 2px {estilo.E2}px; font-weight: 600;")
        else:
            self.aviso.setStyleSheet("color: #B45309")

    def _arrastrando(self, en_curso: bool) -> None:
        """Mientras se arrastra un bloque del área, el pie dice que soltarlo fuera lo quita (`ERROR_FONDO`); al soltar, se retira."""
        if en_curso:
            self._estilo_aviso(True)
            self.aviso.setText("Suelta fuera del lienzo para quitar este bloque")
            self.aviso.setVisible(True)
        else:
            self._estilo_aviso(False)
            self._poner_aviso("")

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return False  # (la banda ajusta su propio alto y avisa con `franja_cambiada`; el alto no depende del ancho que se le dé)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        alto = self.banda.height() + 5 + (0 if self._adoptada else self._fila_herr.sizeHint().height() + 5) + (self.CUERPO_MIN + 4 if self.compacto else self.CUERPO_MIN)
        return QSize((180 if self.en_fila else self._col_catalogo.width() + self.asa.width() + 180), alto)

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
        self.t_catalogo.setVisible(not fila)
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
