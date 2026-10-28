"""Notación de usuario para escribir receptividades y condiciones (paso 3, P-IMP-32).

El analizador (grafcet/expressions.py) usa su propia sintaxis de texto: `rise(marcha)`, `fall(p)`, `active(E1)`. Quien
dibuja un grafcet piensa en la notación de la norma: `↑marcha`, `↓p`, `X1`. Este módulo solo traduce entre las dos
escrituras, antes de analizar y al mostrar el texto; no cambia el analizador ni la semántica. Los espacios no cuentan
al escribir y se normalizan siempre al guardar (un espacio entre palabras, ninguno junto a paréntesis ni comas).
"""
from __future__ import annotations

import re
from typing import Iterable

_NOMBRE = r"[^\W\d]\w*(?:\.\w+)?"
_DUR = r"\d+(?:[.,]\d+)?\s*(?:us|µs|μs|ms|s)\b"
_DUR_RE = re.compile(_DUR)
_NOMBRE_RE = re.compile(_NOMBRE)
_ANTES_RETARDO = re.compile(r"[\w./]")


def _cierre(t: str, i: int) -> int | None:
    """Índice posterior al «)» que cierra el «(» de t[i] (paréntesis equilibrados), o None."""
    nivel = 0
    for j in range(i, len(t)):
        nivel += (t[j] == "(") - (t[j] == ")")
        if nivel == 0:
            return j + 1
    return None


def _atomo(t: str, i: int) -> int | None:
    """Fin del átomo que empieza en t[i]: `NOT`, flanco, y un grupo entre paréntesis equilibrados o un nombre
    (con su llamada, si la lleva)."""
    m = re.compile(r"NOT\s+").match(t, i)
    if m:
        i = m.end()
    if i < len(t) and t[i] in "↑↓":
        i += 1
    if i < len(t) and t[i] == "(":
        return _cierre(t, i)
    m = _NOMBRE_RE.match(t, i)
    if not m:
        n = re.compile(r"\d+(?![\w.])").match(t, i)  # un 1 o un 0: la constante se traduce después
        return n.end() if n else None
    return _cierre(t, m.end()) if m.end() < len(t) and t[m.end()] == "(" else m.end()


def _anidados(base: str) -> str:
    """Los retardos que lleva dentro la base de otro retardo (`3s/(3s/a/2s)`)."""
    return _sustituir(_sustituir(base, _retardo_1), _retardo_2)


def _retardo_1(t: str, i: int) -> tuple[str, int] | None:
    """`3s/atomo` o `3s/atomo/2s` que empieza en t[i]."""
    if i and _ANTES_RETARDO.match(t[i - 1]):
        return None
    d1 = _DUR_RE.match(t, i)
    sep = re.compile(r"\s*/\s*").match(t, d1.end()) if d1 else None
    fin = _atomo(t, sep.end()) if sep else None
    if fin is None:
        return None
    base = _anidados(t[sep.end():fin])
    sep2 = re.compile(r"\s*/\s*").match(t, fin)
    d2 = _DUR_RE.match(t, sep2.end()) if sep2 else None
    for hasta, d in ((d2.end() if d2 else None, d2), (fin, None)):
        if hasta is not None and not (hasta < len(t) and re.match(r"[\w.(]", t[hasta])):
            return f"delay({_dur(d1.group(0))}, {base}, {_dur(d.group(0)) if d else '0 s'})", hasta
    return None


def _retardo_2(t: str, i: int) -> tuple[str, int] | None:
    """`atomo/2s` que empieza en t[i]."""
    if i and _ANTES_RETARDO.match(t[i - 1]):
        return None
    fin = _atomo(t, i)
    sep = re.compile(r"\s*/\s*").match(t, fin) if fin is not None else None
    d = _DUR_RE.match(t, sep.end()) if sep else None
    if d is None or (d.end() < len(t) and re.match(r"[\w.]", t[d.end()])):
        return None
    return f"delay(0 s, {_anidados(t[i:fin])}, {_dur(d.group(0))})", d.end()


def _sustituir(t: str, intento) -> str:
    out, i = [], 0
    while i < len(t):
        r = intento(t, i)
        if r:
            out.append(r[0])
            i = r[1]
        else:
            out.append(t[i])
            i += 1
    return "".join(out)


_LIT01 = re.compile(r"`[^`]*`|(?<![\w.])(?<!\d,)\d+(?:[.,]\d+)?(?![\w.]|[.,]\d)")
_LIT_BOOL = re.compile(r"`[^`]*`|(?<![\w.])(?:true|false)(?![\w.(])")
_CLAVES = ("AND", "OR", "NOT")


def _es_llamada(t: str, i: int) -> bool:
    """Si el «(» de t[i] abre los argumentos de una función (y no un grupo, ni sigue a AND, OR o NOT)."""
    m = re.search(r"([^\W\d][\w.]*)\s*$", t[:i])
    return bool(m) and m.group(1) not in _CLAVES


def _operando_completo(t: str, ini: int, fin: int) -> bool:
    """Si el literal t[ini:fin] es un operando booleano completo. Los paréntesis que lo rodean no cuentan: se mira a
    la izquierda del «(» más exterior que solo lo envuelve y a la derecha de su «)». Frontera izquierda: inicio, AND,
    OR, NOT, el «(» de un grupo (no el de una llamada), coma o flecha; derecha: fin, AND, OR, «)» o coma. Nunca una
    comparación o una operación aritmética."""
    while True:
        antes, despues = t[:ini].rstrip(), t[fin:].lstrip()
        if antes.endswith("(") and despues.startswith(")") and not _es_llamada(t, len(antes) - 1):
            ini, fin = len(antes) - 1, len(t) - len(despues) + 1
        else:
            break
    izq = (not antes or antes[-1] in ",↑↓" or re.search(r"(?<![\w.`])(?:AND|OR|NOT)$", antes) is not None
           or (antes.endswith("(") and not _es_llamada(t, len(antes) - 1)))
    der = not despues or despues[0] in ",)" or re.match(r"(?:AND|OR)\b", despues) is not None
    return izq and der


def _constantes_a_nucleo(t: str) -> str:
    """`1` y `0` son `true` y `false` solo si son un operando booleano completo (ver `_operando_completo`)."""
    def lit(m: re.Match[str]) -> str:
        if m.group(0) not in ("0", "1") or not _operando_completo(t, m.start(), m.end()):
            return m.group(0)
        return "true" if m.group(0) == "1" else "false"
    return _LIT01.sub(lit, t)


def _constantes_a_usuario(t: str) -> str:
    """`true` y `false` se escriben 1 y 0 solo como operando booleano completo; en una comparación quedan."""
    def lit(m: re.Match[str]) -> str:
        if m.group(0)[0] == "`" or not _operando_completo(t, m.start(), m.end()):
            return m.group(0)
        return "1" if m.group(0) == "true" else "0"
    return _LIT_BOOL.sub(lit, t)


def _dur(d: str) -> str:
    """«3s» o «1,5 ms» como el analizador las lee: «3 s», «1.5 ms»."""
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(\S+)", d.strip())
    return f"{m.group(1).replace(',', '.')} {m.group(2)}" if m else d


def normalizar_espacios(texto: str) -> str:
    """Un solo espacio entre palabras; ninguno tras «(», antes de «)» o «,» ni entre «↑»/«↓» y su operando."""
    t = re.sub(r"\s+", " ", texto.strip())
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r"([↑↓])\s+", r"\1", t)
    return t


def _operando(t: str, i: int) -> tuple[str, int] | None:
    """Operando que sigue a una flecha: un nombre o un grupo entre paréntesis equilibrados."""
    while i < len(t) and t[i] == " ":
        i += 1
    if i < len(t) and t[i] == "(":
        nivel = 0
        for j in range(i, len(t)):
            nivel += (t[j] == "(") - (t[j] == ")")
            if nivel == 0:
                return t[i + 1:j], j + 1
        return None
    m = re.compile(_NOMBRE).match(t, i)
    if not m:
        return None
    if m.end() < len(t) and t[m.end()] == "(":  # una función: su operando es toda la llamada
        g = _operando(t, m.end())
        return (m.group(0) + "(" + g[0] + ")", g[1]) if g else None
    return m.group(0), m.end()


def x_etapa(etiqueta: str) -> str:
    """Cómo se escribe la actividad de una etapa en la notación del usuario: `X1` para «1» o «E1»; las demás, con
    `active(…)`."""
    return a_usuario(f"active({etiqueta})" if re.fullmatch(_NOMBRE, etiqueta) else f"active(`{etiqueta}`)")


def etapas_ambiguas(texto: str, etapas: Iterable[str] = (), variables: Iterable[str] = ()) -> list[str]:
    """Los `X…` del texto que podrían ser dos etapas: existen a la vez «E1» y «1» (y ninguna variable X1). `a_nucleo`
    resuelve esos casos a «E1»; la otra etapa se escribe `active(`1`)`."""
    etapas, variables, out = set(etapas), set(variables), []
    for mo in re.finditer(r"(?<![\w.])X(\w+)(?![\w(])", texto):
        n = mo.group(1)
        if mo.group(0) not in variables and f"E{n}" in etapas and n in etapas and mo.group(0) not in out:
            out.append(mo.group(0))
    return out


def a_nucleo(texto: str, etapas: Iterable[str] = (), variables: Iterable[str] = (), booleana: bool = True) -> str:
    """De la notación del usuario a la del analizador: `↑a` → `rise(a)`, `↓(a AND b)` → `fall(a AND b)`, `X1` →
    `active(E1)` si existe una etapa E1 (o 1) y ninguna variable llamada X1. Con `booleana` (receptividades,
    condiciones y eventos) un `1` o un `0` que es un operando completo pasa a `true` o `false`; un valor numérico
    (`n := 1`) se traduce con `booleana=False`."""
    etapas, variables = set(etapas), set(variables)
    t = normalizar_espacios(texto)
    # Retardos como en la norma: 3s/X1, X1/2s, 3s/NOT marcha/2s  ->  delay(3 s, X1, 0 s)...
    t = _sustituir(t, _retardo_1)
    t = _sustituir(t, _retardo_2)
    if booleana:  # tras los retardos, toda «/» que queda es una división y la coma separa argumentos
        t = _constantes_a_nucleo(t)
    while True:  # las flechas, de dentro afuera: la primera que tiene operando
        for m in re.finditer("[↑↓]", t):
            op = _operando(t, m.end())
            if op:
                cuerpo, fin = op
                t = t[:m.start()] + ("rise" if m.group(0) == "↑" else "fall") + f"({a_nucleo(cuerpo, etapas, variables, False)})" + t[fin:]
                break
        else:
            break

    def x(mo: re.Match[str]) -> str:
        n = mo.group(1)
        if mo.group(0) in variables:
            return mo.group(0)
        for etiqueta in (f"E{n}", n):
            if etiqueta in etapas:  # una etiqueta que empieza por cifra («1») va entre comillas invertidas
                return f"active({etiqueta})" if re.fullmatch(_NOMBRE, etiqueta) else f"active(`{etiqueta}`)"
        return mo.group(0)
    return normalizar_espacios(re.sub(r"(?<![\w.])X(\w+)(?![\w(])", x, t))


def a_usuario(texto: str) -> str:
    """De la notación del analizador a la del usuario: `rise(a)` → `↑a`, `active(E1)` y `active(`1`)` → `X1`."""
    t = re.sub(r"\bactive\((?:E(\d+)|`(\d+)`)\)", lambda mo: "X" + (mo.group(1) or mo.group(2)), texto)
    previo = None
    while previo != t:  # las funciones más internas primero
        previo = t

        def flecha(mo: re.Match[str]) -> str:
            cuerpo = mo.group(2).strip()
            if re.fullmatch(r"\d+(?:[.,]\d+)?", cuerpo):  # `rise(1)` no es booleano: se deja como está
                return mo.group(0)
            return ("↑" if mo.group(1) == "rise" else "↓") + (cuerpo if re.fullmatch(_NOMBRE, cuerpo) else f"({cuerpo})")
        t = re.sub(r"\b(rise|fall)\(([^()]*)\)", flecha, t)
    return _retardos(_constantes_a_usuario(t))


def _argumentos(t: str, i: int) -> tuple[list[str], int] | None:
    """Argumentos (separados por comas del primer nivel) de la llamada cuyo paréntesis abre en t[i]; y dónde acaba."""
    nivel, args, ini = 0, [], i + 1
    for j in range(i, len(t)):
        c = t[j]
        nivel += (c == "(") - (c == ")")
        if c == "," and nivel == 1:
            args.append(t[ini:j])
            ini = j + 1
        elif nivel == 0:
            args.append(t[ini:j])
            return args, j + 1
    return None


def _retardos(t: str) -> str:
    """`delay(3 s, X1, 0 s)` -> `3s/X1`; los tiempos de 0 s no se escriben (respuesta 4.4 revisada)."""
    while True:
        for m in re.finditer(r"\bdelay\(", t):
            r = _argumentos(t, m.end() - 1)
            if r and len(r[0]) == 3 and "delay(" not in "".join(r[0]):
                d1, base, d2 = (x.strip() for x in r[0])
                if all(re.fullmatch(_DUR, d) for d in (d1, d2)) and (_cero(d1) is False or _cero(d2) is False):
                    simple = re.fullmatch(r"(?:NOT )?[↑↓]?(?:[^\W\d]\w*(?:\.\w+)?|\d+)", base) or re.fullmatch(r"\(.*\)", base) and _cierre(base, 0) == len(base)
                    base = base if simple else f"({base})"
                    partes = ([] if _cero(d1) else [re.sub(r"\s+", "", d1)]) + [base] + ([] if _cero(d2) else [re.sub(r"\s+", "", d2)])
                    t = t[:m.start()] + "/".join(partes) + t[r[1]:]
                    break
        else:
            return t


def _cero(d: str) -> bool:
    return float(re.match(r"[\d.,]+", d).group(0).replace(",", ".")) == 0
