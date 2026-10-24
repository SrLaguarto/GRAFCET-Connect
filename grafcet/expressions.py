"""Expresiones: sintaxis textual P, significado estructurado, tipos y evaluación pura.

Documento 05 (tabla de expresiones y precedencia) y documento 09 (Expression/Meaning).
- REQ-EXP-01: tipos, unidades y precedencia sin conversiones ocultas.
- REQ-EXP-02: la evaluación no tiene efectos laterales.
- REQ-DAT-08 / REQ-MOD-05: el texto se vuelve a analizar con sus vínculos y se
  compara con el significado guardado (D-EXP-DIVERGENTE).
Precedencia (de mayor a menor): agrupación y funciones; signo unario; * /; + -;
una comparación; NOT; AND; OR. Las comparaciones encadenadas se rechazan.
Sintaxis no fijada por el paquete y propuesta en P-IMP-06 (hallazgo H-15): literales de
duración «2 s», «1.5 s», «1500 ms», «10 us»; nombres con espacios entre acentos graves;
literales numéricos sin unidad, compatibles con cualquier unidad.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Protocol

from .diagnostics import Diagnostic, DiagnosticError
from .timeutil import parse_duration
from .values import INT64_MAX, INT64_MIN, TypeSpec, Value, format_value

KEYWORDS = {"NOT", "AND", "OR", "true", "false"}
FUNCS_REF = {"active": "step", "activePartial": "partial", "activeMacro": "macro", "elapsed": "step"}
FUNCS_EXPR = {"rise", "fall"}
CMP = {"=": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
CMP_TEXT = {v: k for k, v in CMP.items()}
ARITH_TEXT = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
OPERATORS = ({"lit", "ref", "not", "and", "or", "neg", "delay"} | set(CMP.values()) | set(ARITH_TEXT)
             | set(FUNCS_REF) | FUNCS_EXPR)

_TOKEN = re.compile(r"""
 (?P<ws>\s+)
|(?P<dur>\d+(?:\.\d+)?\s*(?:us|µs|μs|ms|s)(?![\w.]))
|(?P<num>\d+(?:\.\d+)?)
|(?P<quoted>`[^`]+`)
|(?P<name>[^\W\d]\w*(?:\.[^\W\d]\w*)*)
|(?P<op><=|>=|!=|[()+\-*/=<>,])
""", re.VERBOSE)


class ParseError(Exception):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} (posición {position})")
        self.position = position


# --- Análisis textual ----------------------------------------------------------------

def tokenize(text: str) -> list[tuple[str, str, int]]:
    pos, out = 0, []
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ParseError(f"carácter inesperado «{text[pos]}»", pos)
        kind = m.lastgroup
        if kind != "ws":
            value = m.group(kind)
            if kind == "quoted":
                kind, value = "name", value[1:-1]
            elif kind == "name" and value in KEYWORDS:
                kind = "kw"
            out.append((kind, value, pos))
        pos = m.end()
    out.append(("end", "", len(text)))
    return out


Resolver = Callable[[str, str], str]  # (clase, nombre) -> ID


class _Parser:
    def __init__(self, text: str, resolve: Resolver) -> None:
        self.toks = tokenize(text)
        self.i = 0
        self.resolve = resolve

    def peek(self) -> tuple[str, str, int]:
        return self.toks[self.i]

    def take(self, kind: str | None = None, value: str | None = None) -> tuple[str, str, int]:
        tok = self.toks[self.i]
        if (kind and tok[0] != kind) or (value is not None and tok[1] != value):
            raise ParseError(f"se esperaba {value or kind}, se encontró «{tok[1] or 'fin'}»", tok[2])
        self.i += 1
        return tok

    def at(self, kind: str, value: str | None = None) -> bool:
        tok = self.peek()
        return tok[0] == kind and (value is None or tok[1] == value)

    def parse(self) -> dict[str, Any]:
        node = self.or_()
        if not self.at("end"):
            raise ParseError(f"texto sobrante «{self.peek()[1]}»", self.peek()[2])
        return node

    def or_(self) -> dict[str, Any]:
        node = self.and_()
        while self.at("kw", "OR"):
            self.take()
            node = {"operator": "or", "operands": [node, self.and_()]}
        return node

    def and_(self) -> dict[str, Any]:
        node = self.not_()
        while self.at("kw", "AND"):
            self.take()
            node = {"operator": "and", "operands": [node, self.not_()]}
        return node

    def not_(self) -> dict[str, Any]:
        if self.at("kw", "NOT"):
            self.take()
            return {"operator": "not", "operands": [self.not_()]}
        return self.cmp()

    def cmp(self) -> dict[str, Any]:
        left = self.add()
        tok = self.peek()
        if tok[0] == "op" and tok[1] in CMP:
            self.take()
            right = self.add()
            nxt = self.peek()
            if nxt[0] == "op" and nxt[1] in CMP:
                raise ParseError("comparación encadenada: exprésela con AND", nxt[2])
            return {"operator": CMP[tok[1]], "operands": [left, right]}
        return left

    def add(self) -> dict[str, Any]:
        node = self.mul()
        while self.peek()[0] == "op" and self.peek()[1] in "+-":
            op = "add" if self.take()[1] == "+" else "sub"
            node = {"operator": op, "operands": [node, self.mul()]}
        return node

    def mul(self) -> dict[str, Any]:
        node = self.unary()
        while self.peek()[0] == "op" and self.peek()[1] in "*/":
            op = "mul" if self.take()[1] == "*" else "div"
            node = {"operator": op, "operands": [node, self.unary()]}
        return node

    def unary(self) -> dict[str, Any]:
        if self.at("op", "-"):
            self.take()
            return {"operator": "neg", "operands": [self.unary()]}
        return self.primary()

    def primary(self) -> dict[str, Any]:
        kind, value, pos = self.peek()
        if kind == "op" and value == "(":
            self.take()
            node = self.or_()
            self.take("op", ")")
            return node
        if kind == "kw" and value in ("true", "false"):
            self.take()
            return {"operator": "lit", "literal": {"type": "bool", "value": value == "true"}}
        if kind == "num":
            self.take()
            if "." in value:
                frac = value.partition(".")[2]
                if len(frac) > 9:
                    raise ParseError("literal decimal con más de 9 decimales: no se redondea", pos)
                canon = format_value(TypeSpec("decimal", len(frac)), Fraction(value))
                return {"operator": "lit", "literal": {"type": "decimal", "value": canon}}
            return {"operator": "lit", "literal": {"type": "int", "value": str(int(value))}}
        if kind == "dur":
            self.take()
            try:
                us = parse_duration(value)
            except DiagnosticError as exc:
                raise ParseError(exc.diagnostics[0].message, pos) from exc
            return {"operator": "lit", "literal": {"type": "duration", "value": str(us)}}
        if kind == "name":
            self.take()
            if self.at("op", "("):
                return self.call(value, pos)
            return {"operator": "ref", "reference": self.resolve("var", value)}
        raise ParseError(f"se esperaba un operando, se encontró «{value or 'fin'}»", pos)

    def call(self, fname: str, pos: int) -> dict[str, Any]:
        self.take("op", "(")
        if fname in FUNCS_REF:
            kind, name, npos = self.take("name")
            self.take("op", ")")
            return {"operator": fname, "reference": self.resolve(FUNCS_REF[fname], name)}
        if fname in FUNCS_EXPR:
            arg = self.or_()
            self.take("op", ")")
            return {"operator": fname, "operands": [arg]}
        if fname == "delay":
            a = self.or_()
            self.take("op", ",")
            b = self.or_()
            self.take("op", ",")
            c = self.or_()
            self.take("op", ")")
            return {"operator": "delay", "operands": [a, b, c]}
        raise ParseError(f"función desconocida «{fname}»", pos)


class Unresolved(Exception):
    def __init__(self, kind: str, name: str) -> None:
        super().__init__(f"nombre sin resolver: {name} ({kind})")
        self.kind, self.name = kind, name


def parse(text: str, resolve: Resolver) -> dict[str, Any]:
    """Texto -> significado. Lanza ParseError o Unresolved."""
    return _Parser(text, resolve).parse()


def bindings_resolver(bindings: dict[str, str]) -> Resolver:
    def resolve(kind: str, name: str) -> str:
        if name not in bindings:
            raise Unresolved(kind, name)
        return bindings[name]
    return resolve


def recording_resolver(lookup: Callable[[str, str], str | None]) -> tuple[Resolver, dict[str, str]]:
    """Resolutor del editor: busca por nombre y registra los vínculos usados."""
    found: dict[str, str] = {}

    def resolve(kind: str, name: str) -> str:
        ident = lookup(kind, name)
        if ident is None:
            raise Unresolved(kind, name)
        found[name] = ident
        return ident
    return resolve, found


# --- Presentación textual ------------------------------------------------------------

_PREC = {"or": 1, "and": 2, "not": 3, **{c: 4 for c in CMP.values()}, "add": 5, "sub": 5,
         "mul": 6, "div": 6, "neg": 7}
_NAME_RE = re.compile(r"^[^\W\d]\w*(?:\.[^\W\d]\w*)*$")


def _name(text: str) -> str:
    return text if _NAME_RE.match(text) and text not in KEYWORDS and text not in FUNCS_REF \
        and text not in FUNCS_EXPR and text != "delay" else f"`{text}`"


def render(m: dict[str, Any], name_of: Callable[[str], str]) -> str:
    """Significado -> texto equivalente (usado para actualizar usos tras un renombrado)."""
    op = m["operator"]
    if op == "lit":
        lit = m["literal"]
        if lit["type"] == "bool":
            return "true" if lit["value"] else "false"
        if lit["type"] == "duration":
            return f"{lit['value']} us"
        if lit["type"] == "decimal" and "." not in lit["value"]:
            return lit["value"] + ".0"  # conserva el tipo decimal del literal al volver a analizar
        return lit["value"]
    if op == "ref":
        return _name(name_of(m["reference"]))
    if op in FUNCS_REF:
        return f"{op}({_name(name_of(m['reference']))})"
    if op in FUNCS_EXPR:
        return f"{op}({render(m['operands'][0], name_of)})"
    if op == "delay":
        return "delay(" + ", ".join(render(o, name_of) for o in m["operands"]) + ")"
    prec = _PREC[op]

    def sub(o: dict[str, Any], right: bool = False) -> str:
        p = _PREC.get(o["operator"], 9)
        txt = render(o, name_of)
        return f"({txt})" if p < prec or (right and p == prec) or (p == 4 and prec == 4) else txt
    if op == "not":
        return f"NOT {sub(m['operands'][0])}"
    if op == "neg":
        return f"-{sub(m['operands'][0])}"
    a, b = m["operands"]
    sym = {"and": "AND", "or": "OR", **CMP_TEXT, **ARITH_TEXT}[op]
    return f"{sub(a)} {sym} {sub(b, right=True)}"


# --- Comprobación estructural de un significado guardado -----------------------------

_ARITY = {"not": 1, "neg": 1, "rise": 1, "fall": 1, "delay": 3, "and": 2, "or": 2,
          **{c: 2 for c in CMP.values()}, **{a: 2 for a in ARITH_TEXT}}


def check_meaning_shape(m: Any, depth: int = 0, max_depth: int = 64, counter: list[int] | None = None) -> None:
    """Rechaza operadores no enumerados, estructura inválida y profundidad excesiva (REQ-DAT-06)."""
    counter = counter if counter is not None else [0]
    counter[0] += 1
    if depth >= max_depth:
        raise DiagnosticError(Diagnostic("D-LIM-DATOS", f"profundidad de expresión superior a {max_depth}"))
    if not isinstance(m, dict) or m.get("operator") not in OPERATORS:
        raise DiagnosticError(Diagnostic("D-FORMATO", "operador no enumerado en el significado",
                                         evidence={"operador": repr(m.get("operator") if isinstance(m, dict) else m)}))
    op = m["operator"]
    allowed = {"operator", "operands", "literal", "reference"}
    if set(m) - allowed:
        raise DiagnosticError(Diagnostic("D-FORMATO", "campo desconocido en significado ejecutable",
                                         evidence={"campos": sorted(set(m) - allowed)}))
    if op == "lit":
        lit = m.get("literal")
        if not isinstance(lit, dict) or lit.get("type") not in ("bool", "int", "decimal", "duration"):
            raise DiagnosticError(Diagnostic("D-FORMATO", "literal inválido"))
        return
    if op == "ref" or op in FUNCS_REF:
        if not isinstance(m.get("reference"), str):
            raise DiagnosticError(Diagnostic("D-FORMATO", "referencia ausente en significado"))
        return
    ops = m.get("operands")
    if not isinstance(ops, list) or len(ops) != _ARITY[op]:
        raise DiagnosticError(Diagnostic("D-FORMATO", f"aridad inválida para {op}"))
    for o in ops:
        check_meaning_shape(o, depth + 1, max_depth, counter)


# --- Tipos y unidades ----------------------------------------------------------------

@dataclass
class TypeInfo:
    kind: str  # bool | int | dec | dur | numlit | declit
    unit: str = ""
    event: bool = False
    temporal: bool = False


@dataclass
class CheckContext:
    var_type: Callable[[str], tuple[TypeSpec, str] | None]  # id -> (tipo, unidad)
    has_step: Callable[[str], bool]
    has_partial: Callable[[str], bool]
    has_macro: Callable[[str], bool]
    diags: list[Diagnostic] = field(default_factory=list)
    element: str | None = None

    def err(self, code: str, msg: str, **ev: Any) -> None:
        self.diags.append(Diagnostic(code, msg, element=self.element, evidence={k: str(v) for k, v in ev.items()}))


_KIND = {"bool": "bool", "int": "int", "decimal": "dec", "duration": "dur"}
_NUMERIC = {"int", "dec", "dur", "numlit", "declit"}


def _unify(a: TypeInfo, b: TypeInfo, ctx: CheckContext, op: str) -> TypeInfo:
    if a.unit and b.unit and a.unit != b.unit:
        ctx.err("D-UNIDAD", f"unidades incompatibles en {op}: {a.unit} y {b.unit}")
    unit = a.unit or b.unit
    ka, kb = a.kind, b.kind
    if ka == kb:
        return TypeInfo(ka, unit)
    pair = {ka, kb}
    table = {frozenset({"numlit", "int"}): "int", frozenset({"numlit", "dec"}): "dec",
             frozenset({"numlit", "declit"}): "declit", frozenset({"declit", "dec"}): "dec"}
    res = table.get(frozenset(pair))
    if res is None:
        ctx.err("D-TIPO", f"tipos incompatibles en {op}: {ka} y {kb} (sin conversión implícita)")
        return TypeInfo("bool" if "bool" in pair else ka, unit)
    return TypeInfo(res, unit)


def typecheck(m: dict[str, Any], ctx: CheckContext) -> TypeInfo:
    op = m["operator"]
    if op == "lit":
        return TypeInfo({"bool": "bool", "int": "numlit", "decimal": "declit", "duration": "dur"}[m["literal"]["type"]])
    if op == "ref":
        vt = ctx.var_type(m["reference"])
        if vt is None:
            ctx.err("D-REF", f"variable inexistente: {m['reference']}")
            return TypeInfo("bool")
        return TypeInfo(_KIND[vt[0].kind], vt[1])
    if op in FUNCS_REF:
        exists = {"step": ctx.has_step, "partial": ctx.has_partial, "macro": ctx.has_macro}[FUNCS_REF[op]]
        if not exists(m["reference"]):
            ctx.err("D-REF", f"{op}: referencia inexistente {m['reference']}")
        return TypeInfo("dur" if op == "elapsed" else "bool")
    kids = [typecheck(o, ctx) for o in m["operands"]]
    ev = any(k.event for k in kids)
    tm = any(k.temporal for k in kids)
    if op in ("not", "and", "or"):
        for k in kids:
            if k.kind != "bool":
                ctx.err("D-TIPO", f"{op.upper()} requiere operandos booleanos (sin conversión numérica)")
        return TypeInfo("bool", "", ev, tm)
    if op in FUNCS_EXPR:
        k = kids[0]
        if k.kind != "bool":
            ctx.err("D-TIPO", f"{op} requiere una proposición booleana")
        if k.event:
            ctx.err("D-TIPO-EVENTO", f"{op} sobre otro evento no admitido")
        return TypeInfo("bool", "", True, k.temporal)
    if op == "delay":
        d1, base, d2 = m["operands"]
        for d in (d1, d2):
            if d["operator"] != "lit" or d["literal"]["type"] != "duration":
                ctx.err("D-TIPO", "delay requiere duraciones literales constantes")
        if kids[1].kind != "bool":
            ctx.err("D-TIPO", "la condición de delay debe ser booleana")
        if kids[1].event:
            ctx.err("D-TIPO-EVENTO", "un evento no puede ser condición base de delay")
        return TypeInfo("bool", "", False, True)
    if op in ("eq", "ne") and kids[0].kind == "bool" and kids[1].kind == "bool":
        return TypeInfo("bool", "", ev, tm)
    for k in kids:
        if k.kind not in _NUMERIC:
            ctx.err("D-TIPO", f"operador {op} requiere operandos numéricos")
            return TypeInfo("bool" if op in CMP_TEXT else "int", "", ev, tm)
    if op == "neg":
        return TypeInfo(kids[0].kind, kids[0].unit, ev, tm)
    if op in CMP_TEXT:
        _unify(kids[0], kids[1], ctx, op)
        return TypeInfo("bool", "", ev, tm)
    if op in ("add", "sub"):
        t = _unify(kids[0], kids[1], ctx, op)
        t.event, t.temporal = ev, tm
        return t
    # mul / div
    if "dur" in (kids[0].kind, kids[1].kind):
        ctx.err("D-TIPO", f"{op} sobre duraciones no admitido en este perfil")
    if kids[0].unit and kids[1].unit:
        ctx.err("D-UNIDAD", f"{op} entre dos magnitudes con unidad no admitido (P-IMP-06)")
    unit = kids[0].unit or kids[1].unit
    if op == "mul":
        t = _unify(TypeInfo(kids[0].kind), TypeInfo(kids[1].kind), ctx, op)
        return TypeInfo(t.kind, unit, ev, tm)
    if {"int", "dec"} <= {kids[0].kind, kids[1].kind}:
        ctx.err("D-TIPO", "división entre entero y decimal sin conversión explícita")
    return TypeInfo("dec", unit, ev, tm)


def assignable(target: TypeSpec, t: TypeInfo) -> bool:
    if t.kind == "bool":
        return target.kind == "bool"
    return {"int": {"int", "numlit"}, "decimal": {"dec", "declit", "numlit"},
            "duration": {"dur"}, "bool": set()}[target.kind].__contains__(t.kind)


def is_event_positive(m: dict[str, Any]) -> bool:
    """Una expresión de disparo debe ser falsa cuando no hay eventos (P-IMP-06)."""
    op = m["operator"]
    if op in FUNCS_EXPR:
        return True
    if op == "and":
        return any(is_event_positive(o) for o in m["operands"])
    if op == "or":
        return all(is_event_positive(o) for o in m["operands"])
    return False


# --- Nodos compilados y evaluación pura ----------------------------------------------

class Node:
    __slots__ = ("op", "kids", "ref", "value", "key")

    def __init__(self, op: str, kids: list["Node"], ref: str | None, value: Any, key: str) -> None:
        self.op, self.kids, self.ref, self.value, self.key = op, kids, ref, value, key


def build(m: dict[str, Any], key: str) -> Node:
    op = m["operator"]
    if op == "lit":
        lit = m["literal"]
        t = lit["type"]
        val = lit["value"] if t == "bool" else (Fraction(lit["value"]) if t == "decimal" else int(lit["value"]))
        return Node(op, [], None, val, key)
    if op == "ref" or op in FUNCS_REF:
        return Node(op, [], m["reference"], None, key)
    return Node(op, [build(o, f"{key}.{i}") for i, o in enumerate(m["operands"])], None, None, key)


class Env(Protocol):
    def var(self, vid: str) -> Value: ...
    def active(self, sid: str) -> bool: ...
    def active_partial(self, pid: str) -> bool: ...
    def active_macro(self, mid: str) -> bool: ...
    def elapsed(self, sid: str) -> int: ...
    def event(self, key: str) -> bool: ...
    def temporal(self, key: str) -> bool: ...


def _check_int(v: Value) -> Value:
    if isinstance(v, int) and not isinstance(v, bool) and not INT64_MIN <= v <= INT64_MAX:
        raise DiagnosticError(Diagnostic("D-NUM", "desbordamiento de entero de 64 bits", evidence={"valor": str(v)}))
    return v


def evaluate(n: Node, env: Env) -> Value:
    """Evaluación pura: no modifica memorias, contadores ni tiempo (REQ-EXP-02)."""
    op = n.op
    if op == "lit":
        return n.value
    if op == "ref":
        return env.var(n.ref)
    if op == "active":
        return env.active(n.ref)
    if op == "activePartial":
        return env.active_partial(n.ref)
    if op == "activeMacro":
        return env.active_macro(n.ref)
    if op == "elapsed":
        return env.elapsed(n.ref)
    if op in FUNCS_EXPR:
        return env.event(n.key)
    if op == "delay":
        return env.temporal(n.key)
    if op == "not":
        return not evaluate(n.kids[0], env)
    if op == "and":
        a = evaluate(n.kids[0], env)
        b = evaluate(n.kids[1], env)  # sin cortocircuito: ambas ramas se comprueban igual
        return a and b
    if op == "or":
        a = evaluate(n.kids[0], env)
        b = evaluate(n.kids[1], env)
        return a or b
    if op == "neg":
        return _check_int(-evaluate(n.kids[0], env))
    a = evaluate(n.kids[0], env)
    b = evaluate(n.kids[1], env)
    if op == "eq":
        return a == b
    if op == "ne":
        return a != b
    if op == "lt":
        return a < b
    if op == "le":
        return a <= b
    if op == "gt":
        return a > b
    if op == "ge":
        return a >= b
    if op == "add":
        return _check_int(a + b)
    if op == "sub":
        return _check_int(a - b)
    if op == "mul":
        return _check_int(a * b)
    if op == "div":
        if b == 0:
            raise DiagnosticError(Diagnostic("D-NUM", "división por cero"))
        return Fraction(a) / Fraction(b)
    raise DiagnosticError(Diagnostic("D-FORMATO", f"operador desconocido {op}"))


@dataclass
class Support:
    vars: set[str] = field(default_factory=set)
    steps: set[str] = field(default_factory=set)
    partials: set[str] = field(default_factory=set)
    macros: set[str] = field(default_factory=set)
    elapsed: set[str] = field(default_factory=set)
    events: list[Node] = field(default_factory=list)
    temporals: list[Node] = field(default_factory=list)


def support(n: Node, s: Support | None = None) -> Support:
    s = s if s is not None else Support()
    if n.op == "ref":
        s.vars.add(n.ref)
    elif n.op == "active":
        s.steps.add(n.ref)
    elif n.op == "activePartial":
        s.partials.add(n.ref)
    elif n.op == "activeMacro":
        s.macros.add(n.ref)
    elif n.op == "elapsed":
        s.elapsed.add(n.ref)
    elif n.op in FUNCS_EXPR:
        s.events.append(n)
    elif n.op == "delay":
        s.temporals.append(n)
    for k in n.kids:
        support(k, s)
    return s
