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
_ATOMO = r"(?:NOT\s+)?[↑↓]?(?:\([^()]*\)|[^\W\d]\w*(?:\.\w+)?(?:\([^()]*\))?)"
_RETARDO = re.compile(rf"(?<![\w./])({_DUR})\s*/\s*({_ATOMO})(?:\s*/\s*({_DUR}))?(?![\w.(])")
_RETARDO_T2 = re.compile(rf"(?<![\w./])({_ATOMO})\s*/\s*({_DUR})(?![\w.])")


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


def a_nucleo(texto: str, etapas: Iterable[str] = (), variables: Iterable[str] = ()) -> str:
    """De la notación del usuario a la del analizador: `↑a` → `rise(a)`, `↓(a AND b)` → `fall(a AND b)`, `X1` →
    `active(E1)` si existe una etapa E1 (o 1) y ninguna variable llamada X1."""
    etapas, variables = set(etapas), set(variables)
    t = normalizar_espacios(texto)
    # Retardos como en la norma: 3s/X1, X1/2s, 3s/NOT marcha/2s  ->  delay(3 s, X1, 0 s)...
    t = _RETARDO.sub(lambda m: f"delay({_dur(m.group(1))}, {m.group(2)}, {_dur(m.group(3)) if m.group(3) else '0 s'})", t)
    t = _RETARDO_T2.sub(lambda m: f"delay(0 s, {m.group(1)}, {_dur(m.group(2))})", t)
    while True:  # las flechas, de dentro afuera: la primera que tiene operando
        for m in re.finditer("[↑↓]", t):
            op = _operando(t, m.end())
            if op:
                cuerpo, fin = op
                t = t[:m.start()] + ("rise" if m.group(0) == "↑" else "fall") + f"({a_nucleo(cuerpo, etapas, variables)})" + t[fin:]
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
            return ("↑" if mo.group(1) == "rise" else "↓") + (cuerpo if re.fullmatch(_NOMBRE, cuerpo) else f"({cuerpo})")
        t = re.sub(r"\b(rise|fall)\(([^()]*)\)", flecha, t)
    return _retardos(t)


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
                    simple = re.fullmatch(r"(?:NOT )?[↑↓]?[^\W\d]\w*(?:\.\w+)?", base) or re.fullmatch(r"\([^()]*\)", base)
                    base = base if simple else f"({base})"
                    partes = ([] if _cero(d1) else [re.sub(r"\s+", "", d1)]) + [base] + ([] if _cero(d2) else [re.sub(r"\s+", "", d2)])
                    t = t[:m.start()] + "/".join(partes) + t[r[1]:]
                    break
        else:
            return t


def _cero(d: str) -> bool:
    return float(re.match(r"[\d.,]+", d).group(0).replace(",", ".")) == 0
