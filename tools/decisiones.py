"""Catálogo del comparador de decisiones (P-IMP-21).

Cada cuestión de la hoja 08 que el motor puede simular lleva un ejemplo, un guion de pasos y, para cada
lectura, lo que se espera ver. El comparador ejecuta el mismo ejemplo una vez por lectura, en paralelo, para
que el responsable elija viendo cómo evoluciona cada grafcet. Las cuestiones que aún no se pueden simular
(jerarquías, encapsulación, elapsed) se presentan solo con su texto.

`checks` fija, por lectura y por paso del guion (0 = tras el arranque), lo que debe cumplirse; las pruebas de
tests/test_comparador.py lo comprueban, así que el texto que ve el responsable y lo que hace el motor no se
pueden separar sin que falle una prueba. Ninguna lectura es conformidad: elegir una es una decisión del
responsable, que después se implementa con su prueba y su referencia a la hoja.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from helpers import M, S  # constructor de modelos con el formato del documento 09

Layout = dict[str, tuple[int, int]]


@dataclass
class Decision:
    id: str
    block: str
    title: str
    question: str
    choices: list[tuple[str, str]]  # (valor, texto) tal como se elige; en las simulables, valor de SEMANTIC_OPTIONS
    option: str | None = None  # clave de SEMANTIC_OPTIONS; None si aún no se puede simular
    example: str = ""
    build: Callable[[], tuple[M, Layout]] | None = None
    init: dict[str, Any] = field(default_factory=dict)
    batches: list[tuple[int, int, dict[str, Any]]] = field(default_factory=list)
    base: dict[str, str] = field(default_factory=dict)  # otras lecturas que el ejemplo necesita para avanzar
    script: list[dict[str, Any]] = field(default_factory=list)
    expect: dict[str, str] = field(default_factory=dict)
    checks: dict[str, dict[int, dict[str, Any]]] = field(default_factory=dict)
    note: str = ""

    @property
    def simulable(self) -> bool:
        return self.option is not None and self.build is not None


def fijar(texto: str, **cambios: Any) -> dict[str, Any]:
    return {"op": "fijar", "cambios": cambios, "texto": texto}


def hasta(texto: str, us: int) -> dict[str, Any]:
    return {"op": "hasta", "us": us, "texto": texto}


def avanzar(texto: str, us: int) -> dict[str, Any]:
    return {"op": "avanzar", "us": us, "texto": texto}


def _cadena(*ids: str, x: int = 160, y0: int = 60) -> Layout:
    """Etapas y transiciones en vertical, alternadas (etapa, transición, etapa…)."""
    return {i: (x, y0 + 80 * n) for n, i in enumerate(ids)}


# --- 1. Inicialización (U-09) ---------------------------------------------------------

def m11() -> tuple[M, Layout]:
    g = M().var("p").var("luz", "output").var("n", "internal", "int")
    g.step("E0", True).step("E1")
    g.stored("E0", "n", "activation", "1").cont("E0", "luz", "n = 1")
    g.trans("t1", ["E0"], ["E1"], "p")
    return g, _cadena("E0", "t1", "E1")


def m12() -> tuple[M, Layout]:
    g = M().var("p").var("q").var("motor", "output")
    g.step("E0", True).step("E1")
    g.trans("t1", ["E0"], ["E1"], "p").cont("E1", "motor")
    return g, _cadena("E0", "t1", "E1")


def m13() -> tuple[M, Layout]:
    g = M().var("p").var("motor", "output")
    g.step("E0", True).step("E1")
    g.trans("t1", ["E0"], ["E1"], "delay(3 s, p, 0 s)").cont("E1", "motor")
    return g, _cadena("E0", "t1", "E1")


def m15() -> tuple[M, Layout]:
    g = M().var("p").var("luz", "output").var("n", "internal", "int", init="5")
    g.step("E0", True).step("E1")
    g.cont("E0", "luz", "n = 5").trans("t1", ["E0"], ["E1"], "p").stored("E1", "n", "activation", "n + 1")
    return g, _cadena("E0", "t1", "E1")


# --- 2. Lecturas y escrituras en el mismo instante (U-05) -------------------------------

def m21() -> tuple[M, Layout]:
    g = M().var("p").var("n", "internal", "int")
    g.step("A", True).step("B").step("C")
    g.trans("t", ["A"], ["B", "C"], "p")
    g.stored("B", "n", "activation", "n + 1", aid="aB").stored("C", "n", "activation", "n + 1", aid="aC")
    return g, {"A": (220, 60), "t": (220, 130), "B": (130, 215), "C": (330, 215)}


def m22() -> tuple[M, Layout]:
    g = M().var("p").var("x", "internal", "int").var("y", "internal", "int")
    g.step("A", True).step("B")
    g.stored("A", "x", "activation", "2", aid="ax").stored("A", "y", "activation", "5", aid="ay")
    g.trans("t", ["A"], ["B"], "p")
    g.stored("B", "x", "activation", "y", aid="bx").stored("B", "y", "activation", "x", aid="by")
    return g, _cadena("A", "t", "B")


def m23() -> tuple[M, Layout]:
    g = M().var("p").var("q").var("luz", "output").var("n", "internal", "int")
    g.step("A", True).step("B").step("C")
    g.trans("t1", ["A"], ["B"], "p").stored("B", "n", "activation", "1")
    g.trans("t2", ["B"], ["C"], "n = 1").cont("C", "luz")
    return g, _cadena("A", "t1", "B", "t2", "C")


def m24() -> tuple[M, Layout]:
    g = M().var("p").var("z", "internal", "int")
    g.step("A", True).step("B").step("C")
    g.trans("t1", ["A"], ["B"], "p").stored("B", "z", "activation", "1", aid="aB")
    g.trans("t2", ["B"], ["C"], "true").stored("C", "z", "activation", "2", aid="aC")
    return g, _cadena("A", "t1", "B", "t2", "C")


def m25() -> tuple[M, Layout]:
    g = M().var("pulso").var("alarma", "output").var("n", "internal", "int")
    g.step("A", True)
    g.cont("A", "alarma", "n >= 3").stored("A", "n", "event", "n + 1", event="rise(pulso)")
    return g, {"A": (160, 60)}


# --- 3. Etapa activada y desactivada a la vez (U-04) ------------------------------------
# u lleva p·X_A para que solo franquee junto con t: con p a secas volvería a franquear en la evolución
# siguiente (B sigue activa y p sigue a 1) y el ejemplo mezclaría otra cosa.

def m31() -> tuple[M, Layout]:
    g = M().var("p").var("n", "internal", "int").var("m", "internal", "int")
    g.step("A", True).step("B", True).step("C")
    g.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "p AND active(A)")
    g.stored("B", "n", "activation", "n + 1", aid="bn").stored("B", "m", "deactivation", "m + 1", aid="bm")
    return g, _cadena("A", "t", "B", "u", "C")


def m32() -> tuple[M, Layout]:
    g = M().var("p").var("luz", "output")
    g.step("A", True).step("B", True).step("C").step("D")
    g.trans("t", ["A"], ["B"], "p").trans("u", ["B"], ["C"], "p AND active(A)")
    g.trans("v", ["B"], ["D"], "delay(5 s, active(B), 0 s)").cont("D", "luz")
    return g, {"A": (180, 60), "t": (180, 140), "B": (180, 220), "u": (100, 300), "v": (280, 300),
               "C": (100, 380), "D": (280, 380)}


def m33() -> tuple[M, Layout]:
    g = M().var("p").var("n", "internal", "int")
    g.step("A", True).step("B", True)
    g.trans("t", ["A"], ["B"], "p").stored("B", "n", "activation", "n + 1")
    return g, _cadena("A", "t", "B")


# --- 4. Fronteras de tiempo (U-06) ------------------------------------------------------

def m41() -> tuple[M, Layout]:
    g = M().var("p").var("motor", "output")
    g.step("A", True).step("B")
    g.trans("t", ["A"], ["B"], "delay(2 s, p, 0 s)").cont("B", "motor")
    return g, _cadena("A", "t", "B")


def m42() -> tuple[M, Layout]:
    g = M().var("p").var("luz", "output")
    g.step("A", True)
    g.cont("A", "luz", "delay(1 s, p, 2 s)")
    return g, {"A": (160, 60)}


def m43() -> tuple[M, Layout]:
    g = M().var("q").var("motor", "output").var("luz", "output")
    g.step("A", True).step("B").step("C")
    g.trans("t1", ["A"], ["B"], "delay(2 s, active(A), 0 s)").trans("t2", ["A"], ["C"], "q")
    g.cont("B", "motor").cont("C", "luz")
    return g, {"A": (200, 60), "t1": (110, 150), "t2": (300, 150), "B": (110, 240), "C": (300, 240)}


def m44() -> tuple[M, Layout]:
    g = M().var("p").var("motor", "output")
    g.step("A", True).step("B")
    g.trans("t", ["A"], ["B"], "delay(0 s, p, 0 s)").cont("B", "motor")
    return g, _cadena("A", "t", "B")


# --- 5. Flancos durante el recorrido (U-03) ---------------------------------------------

def m51() -> tuple[M, Layout]:
    g = M().var("p").var("reinicio").step("A", True).step("B").step("C")
    g.trans("t", ["A"], ["B"], "rise(p)").trans("u", ["B"], ["C"], "rise(p)").trans("v", ["C"], ["A"], "reinicio")
    return g, _cadena("A", "t", "B", "u", "C", "v")


def m52() -> tuple[M, Layout]:
    g = M().var("a").var("n", "internal", "int")
    g.step("A", True).step("B")
    g.stored("A", "n", "event", "n + 1", event="rise(a)").trans("t", ["A"], ["B"], "rise(a)")
    return g, _cadena("A", "t", "B")


def m53() -> tuple[M, Layout]:
    g = M().var("a").var("n", "internal", "int")
    g.step("A", True).step("B")
    g.trans("t", ["A"], ["B"], "rise(a)").stored("B", "n", "event", "n + 1", event="rise(a)")
    return g, _cadena("A", "t", "B")


# --- 6. Transiciones fuente y arranque vacío (U-07) -------------------------------------

def m61() -> tuple[M, Layout]:
    g = M().var("p").var("q")
    g.step("A").step("B")
    g.trans("t0", [], ["A"], "rise(q)").trans("t1", ["A"], ["B"], "p")
    return g, _cadena("t0", "A", "t1", "B", y0=30)


def m62() -> tuple[M, Layout]:
    g = M().var("p").var("q").var("luz", "output")
    g.step("E0", True).step("A").step("B")
    g.trans("t0", [], ["A"], "p").trans("t1", ["A"], ["B"], "q").cont("A", "luz")
    return g, {"E0": (60, 110), **_cadena("t0", "A", "t1", "B", x=220, y0=30)}


def m63() -> tuple[M, Layout]:
    g = M().var("p")
    g.step("E0", True).step("A").step("B")
    g.trans("t0", [], ["A"], "rise(p)").trans("t1", ["A"], ["B"], "true")
    return g, {"E0": (60, 110), **_cadena("t0", "A", "t1", "B", x=220, y0=30)}


def m64() -> tuple[M, Layout]:
    g = M().var("p").step("A", True).step("B")
    g.trans("t", ["A"], ["B"], "p").trans("t9", [], [], "p")
    return g, {**_cadena("A", "t", "B"), "t9": (330, 140)}


# --- 8. Otras dudas (H-08, H-10) --------------------------------------------------------

def m81() -> tuple[M, Layout]:
    g = M().partial("G1").partial("G2", owner="G1")
    g.step("E0", True).step("E1").step("X", partial="G1").step("Y", True, partial="G2")
    g.trans("t", ["E0"], ["E1"], "activePartial(G1)")
    return g, {**_cadena("E0", "t", "E1"), "X": (330, 60), "Y": (330, 180)}


def m82() -> tuple[M, Layout]:
    g = M().var("p").var("q").var("y", "output").var("luz", "output")
    g.step("A", True).step("B").step("C")
    g.trans("t1", ["A"], ["B"], "p").cont("B", "y").trans("t2", ["B"], ["C"], "y").cont("C", "luz")
    return g, _cadena("A", "t1", "B", "t2", "C")


# --- 3.4 y 7. Jerarquías (U-04, U-08) -------------------------------------------------

def m34() -> tuple[M, Layout]:
    g = M().partial("R").var("p").var("q")
    g.step("A", True).step("H", True, kind="enclosing").step("C")
    g.step("I", True, partial="R").step("J", partial="R").step("K", partial="R")
    g.trans("t", ["A"], ["H"], "p").trans("u", ["H"], ["C"], "p AND active(A)").trans("v", ["I"], ["J"], "q", partial="R")
    g.enclosure("H", "R", ["K"])
    return g, {**_cadena("A", "t", "H", "u", "C"), "I": (420, 140), "v": (420, 220), "J": (420, 300), "K": (540, 140)}


def m72() -> tuple[M, Layout]:
    g = M().partial("G").var("p").var("n", "internal", "int")
    g.step("Z", True).step("H").step("A", True, partial="G").step("B", partial="G").step("C", partial="G")
    g.trans("t", ["Z"], ["H"], "p").trans("u", ["A"], ["B"], "p", partial="G").stored("B", "n", "activation", "1")
    g.force("F", "H", "G", "explicit", ["C"])
    return g, {**_cadena("Z", "t", "H"), "A": (430, 60), "u": (430, 140), "B": (430, 220), "C": (560, 60)}


def m73() -> tuple[M, Layout]:
    g = M().partial("G").var("p").var("q").var("luz", "output")
    g.step("Z", True).step("H").step("A", True, partial="G").step("B", partial="G")
    g.trans("t", ["Z"], ["H"], "p").trans("v", ["H"], ["Z"], "q")
    g.trans("w", ["A"], ["B"], "delay(3 s, active(A), 0 s)", partial="G").cont("B", "luz")
    g.force("F", "H", "G", "current")
    return g, {"Z": (160, 60), "t": (160, 140), "H": (160, 220), "v": (160, 290),
               "A": (440, 60), "w": (440, 140), "B": (440, 220)}


def m74() -> tuple[M, Layout]:
    g = M().partial("R").var("p")
    g.step("P0", True).step("H", kind="enclosing").step("F0", True).step("I", partial="R").step("J", partial="R")
    g.trans("t", ["P0"], ["H"], "p").enclosure("H", "R", ["I"]).force("F", "F0", "R", "explicit", ["J"])
    return g, {**_cadena("P0", "t", "H"), "F0": (160, 340), "I": (420, 140), "J": (420, 230)}


def m75() -> tuple[M, Layout]:
    g = M().partial("X").var("p").var("q").var("s").step("A", True).step("B")
    g.step("E1", kind="entry", partial="X").step("K", partial="X").step("S1", kind="exit", partial="X")
    g.trans("tq", ["E1"], ["K", "S1"], "q", partial="X")
    g.macro("M", "X", "E1", "S1").trans("tp", ["A"], ["M"], "p").trans("ts", ["M"], ["B"], "s")
    return g, {**_cadena("A", "tp", "M", "ts", "B"), "E1": (430, 100), "tq": (430, 180), "K": (370, 280), "S1": (500, 280)}


def m76() -> tuple[M, Layout]:
    g = M().partial("R").var("p").var("n", "internal", "int")
    g.step("H", True, kind="enclosing").step("Z").step("A", True, partial="R").step("B", partial="R")
    g.trans("ti", ["A"], ["B"], "delay(2 s, active(A), 0 s)", partial="R").trans("to", ["H"], ["Z"], "p")
    g.stored("B", "n", "activation", "1").enclosure("H", "R", ["A"])
    return g, {**_cadena("H", "to", "Z"), "A": (430, 60), "ti": (430, 140), "B": (430, 220)}


def m77() -> tuple[M, Layout]:
    g = M().partial("X").var("p").var("q").var("r").step("A", True).step("B")
    g.step("E1", kind="entry", partial="X").step("K", True, partial="X").step("S1", kind="exit", partial="X")
    g.trans("tq", ["E1"], ["K"], "q", partial="X").trans("tr", ["K"], ["S1"], "r", partial="X")
    g.macro("M", "X", "E1", "S1").trans("tp", ["A"], ["M"], "p").trans("ts", ["M"], ["B"], "true")
    return g, {**_cadena("A", "tp", "M", "ts", "B"), **_cadena("E1", "tq", "K", "tr", "S1", x=430, y0=60)}


def m78() -> tuple[M, Layout]:
    g = M().partial("G").var("p").var("n", "internal", "int")
    g.step("Z", True).step("H").step("A", True, partial="G").step("B", partial="G")
    g.trans("t", ["Z"], ["H"], "p").stored("B", "n", "activation", "1").force("F", "H", "G", "explicit", ["B"])
    return g, {**_cadena("Z", "t", "H"), "A": (430, 60), "B": (430, 180)}


ARRANQUE = "Arranque"

CATALOGO: list[Decision] = [
    Decision(
        "1.1", "1. Inicialización (U-09)", "Acción «al activar» en una etapa inicial",
        "Al arrancar, ¿se ejecuta la acción «al activar» de la etapa inicial?",
        [("A", "Sí: arrancar cuenta como activar E0"), ("B", "No: la situación inicial no es una activación")],
        "1.1", "E0 es inicial y tiene n := 1 al activar. La luz se enciende si n = 1.", m11,
        script=[fijar("p sube: se pasa a E1", p=True)],
        expect={"A": "Al arrancar se ejecuta n := 1: n = 1 y la luz se enciende en E0.",
                "B": "No se ejecuta: n se queda en 0 y la luz no se enciende."},
        checks={"A": {0: {"situation": ["E0"], "values": {"n": "1"}, "outputs": {"luz": True}}},
                "B": {0: {"situation": ["E0"], "values": {"n": "0"}, "outputs": {"luz": False}}}}),
    Decision(
        "1.2", "1. Inicialización (U-09)", "Situación inicial inestable",
        "Si al arrancar ya hay una transición franqueable, ¿qué pasa en τ = 0?",
        [("A", "Evoluciona en ese mismo instante"), ("B", "Espera al primer cambio de entradas"),
         ("C", "Error de diseño: no arranca")],
        "1.2", "p vale 1 desde el arranque, así que t1 ya es franqueable en τ = 0. q no interviene en el grafcet.",
        m12, init={"p": True},
        script=[fijar("q sube (no interviene): es el primer cambio de entradas", q=True)],
        expect={"A": "En τ = 0 franquea t1: E0 queda inestable y se arranca en E1 con el motor en marcha.",
                "B": "Se arranca en E0 y se queda ahí; al cambiar q (cualquier entrada) franquea t1.",
                "C": "El programa no arranca: D-FORMATO (situación inicial inestable)."},
        checks={"A": {0: {"situation": ["E1"], "outputs": {"motor": True}}},
                "B": {0: {"situation": ["E0"]}, 1: {"situation": ["E1"]}},
                "C": {0: {"code": "D-FORMATO"}}}),
    Decision(
        "1.3", "1. Inicialización (U-09)", "Temporizador sobre una entrada ya verdadera al arrancar",
        "t1 tiene 3s/p y p vale 1 desde el arranque. ¿Cuándo franquea?",
        [("A", "A los 3 s: cuenta desde el arranque"), ("B", "Hace falta una subida real de p")],
        "1.3", "p vale 1 desde τ = 0.", m13, init={"p": True},
        script=[avanzar("Pasan 3 s con p = 1", 3 * S), fijar("p baja", p=False),
                fijar("p vuelve a subir: ahora sí hay una subida", p=True), avanzar("Pasan otros 3 s", 3 * S)],
        expect={"A": "A los 3 s del arranque franquea t1 y el motor arranca.",
                "B": "A los 3 s sigue en E0; solo tras bajar y volver a subir p, y pasar 3 s, llega a E1."},
        checks={"A": {1: {"situation": ["E1"]}},
                "B": {1: {"situation": ["E0"]}, 4: {"situation": ["E1"]}}}),
    Decision(
        "1.4", "1. Inicialización (U-09)", "Duración de una etapa inicial",
        "E0 inicial; t1 con 3s/X0. ¿Franquea t1 a los 3 s del arranque?",
        [("A", "Sí, como está ahora"), ("B", "No")],
        note="Ya está implementado como A (oráculos T-12a y T-12c); no hay otra lectura que simular."),
    Decision(
        "1.5", "1. Inicialización (U-09)", "Variable memorizada con valor inicial distinto de cero",
        "La variable interna n se declara con valor inicial 5. ¿Se admite?",
        [("A", "No: siempre empieza en 0 (no compila)"), ("B", "Sí: empieza con el valor declarado")],
        "1.5", "n se declara con valor inicial 5. La luz de E0 se enciende si n = 5; E1 suma 1 a n.", m15,
        script=[fijar("p sube: se pasa a E1", p=True)],
        expect={"A": "No compila: el valor inicial se pone con una acción al activar en E0 (respuesta 1.1).",
                "B": "Arranca con n = 5 y la luz encendida; al pasar a E1, n = 6."},
        checks={"A": {0: {"code": "D-FORMATO"}},
                "B": {0: {"values": {"n": "5"}, "outputs": {"luz": True}}, 1: {"values": {"n": "6"}}}}),
    Decision(
        "2.1", "2. Mismo instante (U-05)", "Dos incrementos simultáneos",
        "t activa B y C a la vez y las dos hacen n := n + 1. ¿Cuánto vale n?",
        [("A", "1: las dos leen el valor anterior"), ("B", "2: se acumulan"), ("C", "Conflicto: no compila")],
        "2.1", "n = 0 antes de subir p.", m21, script=[fijar("p sube: t activa B y C", p=True)],
        expect={"A": "Las dos leen n = 0 y escriben 1: n = 1.", "B": "Se suman una detrás de otra: n = 2.",
                "C": "No compila: D-ESCRITURA-CONFLICTO (las dos se activan a la vez)."},
        checks={"A": {1: {"situation": ["B", "C"], "values": {"n": "1"}}},
                "B": {1: {"values": {"n": "2"}}}, "C": {0: {"code": "D-ESCRITURA-CONFLICTO"}}}),
    Decision(
        "2.2", "2. Mismo instante (U-05)", "Intercambio de valores",
        "Al activarse B se ejecutan x := y e y := x a la vez. ¿Resultado?",
        [("A", "Se intercambian: ambas leen el estado anterior"), ("B", "Error: dependencia cruzada, no compila")],
        "2.2", "Al arrancar, A pone x = 2 e y = 5 (acciones al activar de la etapa inicial).", m22,
        script=[fijar("p sube: se activa B", p=True)],
        expect={"A": "x = 5 e y = 2.", "B": "No compila: D-DEPENDENCIA-CRUZADA."},
        checks={"A": {0: {"values": {"x": "2", "y": "5"}}, 1: {"values": {"x": "5", "y": "2"}}},
                "B": {0: {"code": "D-DEPENDENCIA-CRUZADA"}}}),
    Decision(
        "2.3", "2. Mismo instante (U-05)", "Receptividad que lee un valor recién asignado",
        "B pone n := 1 al activarse y t2 tiene [n = 1]. ¿Pasa a C en el mismo instante?",
        [("A", "Sí: ve n = 1 (B queda inestable)"), ("B", "No: ve el valor de antes del instante")],
        "2.3", "n = 0 al principio. q no interviene en el grafcet.", m23,
        script=[fijar("p sube: A → B y n := 1", p=True), fijar("q cambia (no interviene): siguiente instante", q=True)],
        expect={"A": "En el mismo instante pasa a C: B queda inestable (su acción memorizada sí se ejecuta).",
                "B": "Se queda en B; pasa a C en el siguiente cambio de entradas."},
        checks={"A": {1: {"situation": ["C"], "values": {"n": "1"}, "outputs": {"luz": True}}},
                "B": {1: {"situation": ["B"], "values": {"n": "1"}}, 2: {"situation": ["C"]}}}),
    Decision(
        "2.4", "2. Mismo instante (U-05)", "Dos asignaciones distintas sucesivas en el mismo instante",
        "Se recorre A → B → C en un instante; B pone z := 1 y C pone z := 2. ¿Cuánto vale z?",
        [("A", "2: vale la última del recorrido"), ("B", "Conflicto de escritura")],
        "2.4", "t2 es siempre verdadera, así que B es inestable.", m24, script=[fijar("p sube", p=True)],
        expect={"A": "z = 2 y la situación es C.", "B": "El motor se detiene con D-ESCRITURA-CONFLICTO."},
        checks={"A": {1: {"situation": ["C"], "values": {"z": "2"}}}, "B": {1: {"code": "D-ESCRITURA-CONFLICTO"}}}),
    Decision(
        "2.5", "2. Mismo instante (U-05)", "Salida continua que lee una memoria cambiada en el instante",
        "alarma si [n ≥ 3]. Una subida de «pulso» lleva n de 2 a 3. ¿Se enciende la alarma en ese instante?",
        [("A", "Sí: usa el valor final del instante"), ("B", "No: en el instante siguiente")],
        "2.5", "Cada subida de pulso suma 1 a n.", m25,
        script=[fijar("pulso sube: n = 1", pulso=True), fijar("pulso baja", pulso=False),
                fijar("pulso sube: n = 2", pulso=True), fijar("pulso baja", pulso=False),
                fijar("pulso sube por tercera vez: n pasa de 2 a 3", pulso=True),
                fijar("pulso baja: siguiente instante", pulso=False)],
        expect={"A": "La alarma se enciende en el mismo instante en que n llega a 3.",
                "B": "La alarma no se enciende hasta el instante siguiente (cuando pulso baja)."},
        checks={"A": {5: {"values": {"n": "3"}, "outputs": {"alarma": True}}},
                "B": {5: {"values": {"n": "3"}, "outputs": {"alarma": False}}, 6: {"outputs": {"alarma": True}}}}),
    Decision(
        "3.1", "3. Activada y desactivada a la vez (U-04)", "Acciones de una etapa en permanencia activa",
        "t: A → B y u: B → C franquean a la vez; B sigue activa (regla 5). ¿Se ejecutan sus acciones "
        "«al activar» (n := n + 1) y «al desactivar» (m := m + 1)?",
        [("A", "No se ejecuta ninguna: B no cambia de estado"), ("B", "Se ejecutan las dos")],
        "3.1", "A y B son iniciales: al arrancar se ejecuta n := n + 1 de B (respuesta 1.1), por eso n = 1. "
        "u lleva p·X_A para que solo franquee junto con t.", m31, script=[fijar("p sube: t y u franquean a la vez", p=True)],
        expect={"A": "B sigue activa y no se ejecuta nada: n = 1, m = 0.",
                "B": "B «sale y entra» a efectos de acciones: n = 2, m = 1."},
        checks={"A": {0: {"values": {"n": "1"}}, 1: {"situation": ["B", "C"], "values": {"n": "1", "m": "0"}}},
                "B": {1: {"situation": ["B", "C"], "values": {"n": "2", "m": "1"}}}}),
    Decision(
        "3.2", "3. Activada y desactivada a la vez (U-04)", "Temporizador de una etapa en permanencia activa",
        "v tiene 5s/X_B. B lleva 2 s activa cuando t y u franquean a la vez y B sigue activa. ¿Cuándo vence?",
        [("A", "Sigue contando: vence 3 s después (coherente con P-IMP-18)"), ("B", "Vuelve a empezar: vence 5 s después")],
        "3.2", "A y B son iniciales. u lleva p·X_A para que solo franquee junto con t.", m32,
        script=[avanzar("Pasan 2 s", 2 * S), fijar("p sube: t y u franquean a la vez; B sigue activa", p=True),
                avanzar("Pasan 3 s más (τ = 5 s)", 3 * S), avanzar("Pasan 2 s más (τ = 7 s)", 2 * S)],
        expect={"A": "A los 5 s del arranque vence 5s/X_B: B → D y se enciende la luz.",
                "B": "A los 5 s no pasa nada; vence a los 7 s (5 s desde la permanencia)."},
        checks={"A": {2: {"situation": ["B", "C"]}, 3: {"situation": ["C", "D"], "outputs": {"luz": True}}},
                "B": {3: {"situation": ["B", "C"]}, 4: {"situation": ["C", "D"]}}}),
    Decision(
        "3.3", "3. Activada y desactivada a la vez (U-04)", "Activar una etapa que ya estaba activa (H-05)",
        "A y B activas; t: A → B franquea (B no es precedente de t). ¿Se ejecuta n := n + 1 de B?",
        [("A", "No: B ya estaba activa"), ("B", "Sí: hay una activación de B")],
        "3.3", "A y B son iniciales: al arrancar n = 1 (acción al activar de B, respuesta 1.1).", m33,
        script=[fijar("p sube: t activa B, que ya estaba activa", p=True)],
        expect={"A": "n se queda en 1.", "B": "n pasa a 2."},
        checks={"A": {1: {"situation": ["B"], "values": {"n": "1"}}}, "B": {1: {"situation": ["B"], "values": {"n": "2"}}}}),
    Decision(
        "3.4", "3. Activada y desactivada a la vez (U-04)", "Etapa encapsulante en permanencia activa",
        "Si la encapsulante H se activa y se desactiva a la vez, ¿su contenido…",
        [("A", "…se mantiene como estaba"), ("B", "…se reinicia con sus etapas de activación")],
        "3.4", "A y H son iniciales; H encapsula el recinto R (I inicial; K con enlace de activación *). u lleva p·X_A para "
        "que solo franquee junto con t.", m34,
        script=[fijar("q sube: dentro de R, I → J", q=True), fijar("p sube: t y u franquean a la vez; H sigue activa", p=True)],
        expect={"A": "H no cambia de estado: R sigue en J.", "B": "R vuelve a empezar desde K, la etapa marcada con *."},
        checks={"A": {1: {"situation": ["A", "H", "J"]}, 2: {"situation": ["C", "H", "J"]}},
                "B": {2: {"situation": ["C", "H", "K"]}}}),
    Decision(
        "4.1", "4. Fronteras de tiempo (U-06)", "La entrada cae exactamente al vencer el retardo",
        "t tiene 2s/p. p sube a 0 s y baja exactamente a 2 s. ¿Franquea?",
        [("A", "Franquea: el vencimiento llega antes que la caída"), ("B", "No franquea: la caída cancela el retardo")],
        "4.1", "Los cambios de p vienen del escenario, en instantes exactos.", m41,
        batches=[(0, 0, {"p": True}), (2 * S, 0, {"p": False})],
        script=[hasta("τ = 0: p sube", 0), hasta("τ = 2 s: vence el retardo y, en el mismo instante, p baja", 2 * S)],
        expect={"A": "Franquea t: se pasa a B (el motor arranca).", "B": "No franquea: se queda en A."},
        checks={"A": {2: {"situation": ["B"]}}, "B": {2: {"situation": ["A"]}}}),
    Decision(
        "4.2", "4. Fronteras de tiempo (U-06)", "Rebote durante el retardo de desconexión",
        "luz si [1s/p/2s]. p sube a 0 s, baja a 3 s (seguiría verdadera hasta 5 s) y vuelve a subir a 4 s.",
        [("A", "Sigue verdadera sin interrupción"), ("B", "Se mantiene el plazo de 5 s y luego hace falta 1 s de p")],
        "4.2", "Los cambios de p vienen del escenario, en instantes exactos.", m42,
        batches=[(0, 0, {"p": True}), (3 * S, 0, {"p": False}), (4 * S, 0, {"p": True})],
        script=[hasta("τ = 0: p sube", 0), hasta("τ = 1 s: la condición pasa a verdadera", S),
                hasta("τ = 3 s: p baja (seguiría verdadera hasta 5 s)", 3 * S),
                hasta("τ = 4 s: p vuelve a subir (rebote)", 4 * S), hasta("τ = 5 s: fin del plazo de desconexión", 5 * S),
                hasta("τ = 6 s", 6 * S)],
        expect={"A": "La luz no se apaga en ningún momento desde 1 s.",
                "B": "La luz se apaga a los 5 s y vuelve a encenderse a los 6 s."},
        checks={"A": {2: {"outputs": {"luz": True}}, 5: {"outputs": {"luz": True}}},
                "B": {4: {"outputs": {"luz": True}}, 5: {"outputs": {"luz": False}}, 6: {"outputs": {"luz": True}}}}),
    Decision(
        "4.3", "4. Fronteras de tiempo (U-06)", "Cambio de entrada y vencimiento en el mismo instante",
        "Un retardo vence a 2 s y, también a 2 s, cambia una entrada. ¿En qué orden se procesan?",
        [("A", "Juntos, como un solo instante"), ("B", "Primero el vencimiento"), ("C", "Primero la entrada"),
         ("D", "Solo se detiene si el resultado depende del orden")],
        "4.3", "Si las dos cosas no se tocan, todas las lecturas dan el mismo resultado (solo cambia la traza). El "
        "ejemplo muestra cuándo importa: a los 2 s vence 2s/X_A (t1) y sube q (t2), las dos salidas de A.", m43,
        batches=[(2 * S, 0, {"q": True})], script=[hasta("τ = 2 s: vence 2s/X_A y, en el mismo instante, q sube", 2 * S)],
        expect={"A": "Las dos receptividades son verdaderas a la vez: franquean t1 y t2 y quedan activas B y C.",
                "B": "Primero vence el retardo: A → B; después q ya no encuentra A activa.",
                "C": "Primero q: A → C; el retardo se cancela al desactivarse A.",
                "D": "Como el resultado depende del orden, se detiene."},
        checks={"A": {1: {"situation": ["B", "C"]}}, "B": {1: {"situation": ["B"]}}, "C": {1: {"situation": ["C"]}},
                "D": {1: {"code": "D-SEM-PENDIENTE"}}}),
    Decision(
        "4.4", "4. Fronteras de tiempo (U-06)", "Retardo cero",
        "¿Qué significa 0s/p?", [("A", "Equivale a p"), ("B", "Se prohíbe: no compila")],
        "4.4", "t tiene 0s/p.", m44, script=[fijar("p sube", p=True)],
        expect={"A": "Al subir p se pasa a B en ese mismo instante.", "B": "No compila: D-FORMATO."},
        checks={"A": {1: {"situation": ["B"]}}, "B": {0: {"code": "D-FORMATO"}}}),
    Decision(
        "4.5", "4. Fronteras de tiempo (U-06)", "Duración T de una etapa inactiva",
        "¿Cuánto vale elapsed(etapa) con la etapa inactiva?",
        [("A", "Vale 0"), ("B", "No tiene valor: leerla es un error"), ("C", "Conserva la última duración")],
        note="elapsed aún no se ejecuta: no hay simulación. Se puede responder igualmente."),
    Decision(
        "5.1", "5. Flancos durante el recorrido (U-03)", "Lectura por defecto de U-03",
        "Dos transiciones seguidas con ↑p. Una subida de p, ¿deja la situación en B o en C?",
        [("detener", "Por defecto «detener»"), ("situacion-anterior", "Por defecto «de uno en uno» (situación anterior)"),
         ("recorrido", "Por defecto «por ciclo» (recorrido)")],
        "U-03", "Es el ejemplo «Bloqueo por U-03» del banco. Recuerde H-23: con «recorrido», un modelo con retorno "
        "puede girar sin fin.", m51, script=[fijar("p sube", p=True)],
        expect={"detener": "Se detiene con D-SEM-PENDIENTE (U-03) y no elige.",
                "situacion-anterior": "El flanco solo vale para t, validada antes de él: se queda en B.",
                "recorrido": "El flanco sigue disponible en el recorrido: franquea t y u y llega a C."},
        checks={"detener": {1: {"code": "D-SEM-PENDIENTE"}}, "situacion-anterior": {1: {"situation": ["B"]}},
                "recorrido": {1: {"situation": ["C"]}}}),
    Decision(
        "5.2", "5. Flancos durante el recorrido (U-03)", "Acción por evento en una etapa que se desactiva con ese evento",
        "A tiene n := n + 1 por ↑a, y t: A → B tiene ↑a. ¿Se ejecuta la acción?",
        [("A", "Sí: A estaba activa cuando ocurrió el evento"), ("B", "No")],
        "5.2", "n = 0 al principio.", m52, script=[fijar("a sube", a=True)],
        expect={"A": "Se pasa a B y n = 1.", "B": "Se pasa a B y n = 0."},
        checks={"A": {1: {"situation": ["B"], "values": {"n": "1"}}}, "B": {1: {"situation": ["B"], "values": {"n": "0"}}}}),
    Decision(
        "5.3", "5. Flancos durante el recorrido (U-03)", "Acción por evento en una etapa que se activa con ese evento",
        "B tiene n := n + 1 por ↑a, y t: A → B tiene ↑a. ¿Se ejecuta la acción?",
        [("A", "No: B no estaba activa al ocurrir el evento"), ("B", "Sí")],
        "5.3", "n = 0 al principio.", m53, script=[fijar("a sube", a=True)],
        expect={"A": "Se pasa a B y n = 0.", "B": "Se pasa a B y n = 1."},
        checks={"A": {1: {"situation": ["B"], "values": {"n": "0"}}}, "B": {1: {"situation": ["B"], "values": {"n": "1"}}}}),
    Decision(
        "6.1", "6. Fuentes y arranque vacío (U-07)", "Grafcet sin etapas iniciales",
        "Ninguna etapa es inicial. ¿Qué pasa al arrancar?",
        [("A", "Error: no compila"), ("B", "Arranca sin etapas activas (solo lo activan transiciones fuente)")],
        "6.1", "t0 es una transición fuente con ↑q, que franquea una vez por flanco (respuesta 6.3 A). La opción C "
        "de la hoja (arrancar con advertencia) se comporta como B.", m61,
        script=[fijar("q sube: la fuente activa A", q=True), fijar("p sube: A → B", p=True)],
        expect={"A": "No compila: D-FORMATO.", "B": "Arranca sin etapas activas; ↑q activa A y p lleva a B."},
        checks={"A": {0: {"code": "D-FORMATO"}},
                "B": {0: {"situation": []}, 1: {"situation": ["A"]}, 2: {"situation": ["B"]}}}),
    Decision(
        "6.2", "6. Fuentes y arranque vacío (U-07)", "Transición fuente con receptividad de nivel",
        "t0 no tiene etapa anterior y su receptividad es p (sin flanco). ¿Se admite?",
        [("A", "No se permite: no compila"), ("B", "Mientras p = 1, mantiene A activa (imposición continua)")],
        "6.2", "E0 es inicial y no interviene. A enciende la luz.", m62,
        script=[fijar("p sube: la fuente activa A", p=True), fijar("p baja: A sigue activa", p=False),
                fijar("q sube con p = 0: A → B", q=True),
                fijar("p sube con q = 1: la fuente activa A y t1 la desactiva otra vez", p=True)],
        expect={"A": "No compila: D-FORMATO.",
                "B": "p activa A; con p = 1 y q = 1 la fuente y t1 se alternan sin fin en el mismo instante y el "
                     "motor lo corta con D-LIM-EVOL."},
        checks={"A": {0: {"code": "D-FORMATO"}},
                "B": {1: {"situation": ["A", "E0"]}, 3: {"situation": ["B", "E0"]}, 4: {"code": "D-LIM-EVOL"}}}),
    Decision(
        "6.3", "6. Fuentes y arranque vacío (U-07)", "Transición fuente con flanco",
        "t0 no tiene etapa anterior y su receptividad es ↑p. ¿Cuántas veces franquea?",
        [("detener", "Detener si en el mismo instante seguiría validada"),
         ("A", "Franquea exactamente una vez por cada subida de p")],
        "6.3", "t1 es siempre verdadera, así que A es inestable y t0 sigue validada en la evolución siguiente.", m63,
        script=[fijar("p sube", p=True)],
        expect={"detener": "Se detiene con D-SEM-PENDIENTE (U-07).",
                "A": "t0 franquea una sola vez: A queda inestable y se llega a B."},
        checks={"detener": {1: {"code": "D-SEM-PENDIENTE"}}, "A": {1: {"situation": ["B", "E0"]}}}),
    Decision(
        "6.4", "6. Fuentes y arranque vacío (U-07)", "Transición sin etapas antes ni después",
        "t9 no tiene etapas antes ni después. ¿Se admite?",
        [("A", "No se permite"), ("B", "Se permite, sin efecto")],
        "6.4", "El resto del grafcet funciona con normalidad.", m64, script=[fijar("p sube", p=True)],
        expect={"A": "No compila: D-FORMATO.", "B": "Compila; t9 no hace nada y p lleva de A a B."},
        checks={"A": {0: {"code": "D-FORMATO"}}, "B": {1: {"situation": ["B"]}}}),
    Decision("7.1", "7. Jerarquías (U-08, U-02)", "Quién fuerza a quién (U-02)",
             "La frase del §7.3 sobre el sentido jerárquico parece invertir sujeto y objeto.",
             [("A", "La etapa de un parcial superior fuerza a un parcial inferior"), ("B", "Es al revés")],
             note="El documento 06 lo fija como interpretación I: una orden de una etapa de un parcial superior impone "
                  "una situación a un parcial inferior (A). Es lo que ejecuta el programa; la duda U-02 es sobre la redacción "
                  "del §7.3. Se puede responder igualmente."),
    Decision(
        "7.2", "7. Jerarquías (U-08, U-02)", "Cuándo se aplica el forzado (H-18)",
        "La orden F (de H, que fuerza G = {C}) entra en vigor en una evolución en la que G también evoluciona. ¿Qué pasa?",
        [("A", "El forzado se aplica en esa misma evolución y gana"), ("B", "G evoluciona y el forzado se aplica en la siguiente")],
        "7.2", "p activa H (t) y, a la vez, haría avanzar G de A a B (u). B pone n := 1 al activarse.", m72,
        script=[fijar("p sube: t activa H, que fuerza G = {C}, y u querría llevar G de A a B", p=True)],
        expect={"A": "El forzado gana: G pasa directamente a {C}; B nunca se activa y n = 0.",
                "B": "G avanza a B (n := 1) y, en la evolución siguiente, el forzado lo lleva a {C}: B queda inestable."},
        checks={"A": {1: {"situation": ["C", "H"], "values": {"n": "0"}}},
                "B": {1: {"situation": ["C", "H"], "values": {"n": "1"}}}}),
    Decision(
        "7.3", "7. Jerarquías (U-08, U-02)", "Temporizadores de un parcial forzado",
        "Mientras G está forzado, ¿qué pasa con sus temporizadores (3s/X_A)?",
        [("A", "Siguen contando"), ("B", "Se congelan mientras dura el forzado")],
        "7.3", "A está activa desde τ = 0. A 1 s, H fuerza G en su situación actual ({A}); a 5 s se retira el forzado.", m73,
        batches=[(S, 0, {"p": True}), (5 * S, 0, {"p": False, "q": True})],
        script=[hasta("τ = 1 s: p activa H, que fuerza G = {A}", S), hasta("τ = 5 s: q retira el forzado", 5 * S),
                hasta("τ = 7 s", 7 * S)],
        expect={"A": "El tiempo de A siguió corriendo: al retirarse el forzado (5 s), A → B en el acto.",
                "B": "A solo llevaba 1 s cuando empezó el forzado: tras retirarlo le faltan 2 s y pasa a B a los 7 s."},
        checks={"A": {2: {"situation": ["B", "Z"]}}, "B": {2: {"situation": ["A", "Z"]}, 3: {"situation": ["B", "Z"]}}}),
    Decision(
        "7.4", "7. Jerarquías (U-08, U-02)", "Forzar un recinto cuya encapsulante está inactiva",
        "F0 fuerza el recinto R = {J}, pero su encapsulante H no está activa al arrancar. ¿Qué pasa?",
        [("A", "Error de diseño: se detiene con error"), ("B", "Se fuerza igualmente"),
         ("C", "El forzado se ignora mientras la encapsulante esté inactiva")],
        "7.4", "F0 es inicial y su orden F/R:{J} está vigente desde el arranque. p activa H.", m74,
        script=[fijar("p sube: se activa H", p=True)],
        expect={"A": "Se detiene con D-FORZADO-RECINTO.",
                "B": "J está activa desde el arranque, aunque H no lo esté (se rompe la regla del recinto).",
                "C": "Al arrancar R está vacío; cuando H se activa, el forzado lo lleva a {J}."},
        checks={"A": {0: {"code": "D-FORZADO-RECINTO"}}, "B": {0: {"situation": ["F0", "J", "P0"]}, 1: {"situation": ["F0", "H", "J"]}},
                "C": {0: {"situation": ["F0", "P0"]}, 1: {"situation": ["F0", "H", "J"]}}}),
    Decision(
        "7.5", "7. Jerarquías (U-08, U-02)", "Salir de una macroetapa con ramas internas aún activas",
        "La expansión de M tiene dos ramas (K y la salida S1). Cuando se sale de M por S1, ¿qué pasa con K?",
        [("A", "Se desactivan todas las etapas de la expansión"), ("B", "Las ramas siguen activas"),
         ("C", "Error de diseño: se detiene con error")],
        "7.5", "Es el caso T-18d del documento 11. s permite salir de M en cuanto Sx está activa.", m75,
        script=[fijar("p sube: se entra en M (E1)", p=True), fijar("q sube: E1 → K y S1", q=True),
                fijar("s sube: se sale de M por S1", s=True)],
        expect={"A": "Se pasa a B y K se desactiva.", "B": "Se pasa a B y K sigue activa dentro de la expansión.",
                "C": "Se detiene con D-JERARQUIA-RAMA."},
        checks={"A": {3: {"situation": ["B"]}}, "B": {3: {"situation": ["B", "K"]}}, "C": {3: {"code": "D-JERARQUIA-RAMA"}}}),
    Decision(
        "7.6", "7. Jerarquías (U-08, U-02)", "Desactivar la encapsulante cuando vence un temporizador interno",
        "A 2 s vence 2s/X_A dentro del recinto de H y, en el mismo instante, p desactiva H. ¿Qué pasa?",
        [("A", "Gana la desactivación: el temporizador interno no tiene efecto"),
         ("B", "Primero actúa el temporizador interno y luego se desactiva")],
        "7.6", "Es el caso T-20a del documento 11. B pone n := 1 al activarse.", m76,
        batches=[(2 * S, 0, {"p": True})], script=[hasta("τ = 2 s: vence 2s/X_A y p desactiva H a la vez", 2 * S)],
        expect={"A": "Se pasa a Z; B nunca se activa (n = 0).", "B": "B se activa (n := 1) y queda inestable; se pasa a Z."},
        checks={"A": {1: {"situation": ["Z"], "values": {"n": "0"}}}, "B": {1: {"situation": ["Z"], "values": {"n": "1"}}}}),
    Decision(
        "7.7", "7. Jerarquías (U-08, U-02)", "Etapas iniciales dentro de la expansión de una macroetapa",
        "K, dentro de la rama de la expansión de M (E1 → K → S1), está marcada como inicial. ¿Se admite?",
        [("A", "Se permiten: están activas al arrancar"), ("B", "No se permiten: no compila")],
        "7.7", "Con K activa al arrancar, M cuenta como activa aunque no se haya entrado por E1. Al subir r, K → S1 y, "
        "como ts es siempre verdadera, se sale de M.", m77,
        script=[fijar("r sube: K → S1 y se sale de M", r=True)],
        expect={"A": "Al arrancar, A y K están activas (M cuenta como activa); con r se sale de M a B, mientras A sigue activa.",
                "B": "No compila: D-FORMATO."},
        checks={"A": {0: {"situation": ["A", "K"]}, 1: {"situation": ["A", "B"]}}, "B": {0: {"code": "D-FORMATO"}}}),
    Decision(
        "7.8", "7. Jerarquías (U-08, U-02)", "Acciones de las etapas que cambia un forzado (H-24)",
        "El forzado activa B, que tiene n := 1 al activarse. ¿Se ejecuta esa acción?",
        [("A", "Sí: es una activación"), ("B", "No: el forzado impone la situación sin acciones")],
        "7.8", "Duda nueva al implementar (H-24): la hoja 08 no la recogía. p activa H, que fuerza G = {B}.", m78,
        script=[fijar("p sube: H fuerza G = {B}", p=True)],
        expect={"A": "B se activa por el forzado y n = 1.", "B": "B se activa por el forzado y n sigue en 0."},
        checks={"A": {1: {"situation": ["B", "H"], "values": {"n": "1"}}}, "B": {1: {"situation": ["B", "H"], "values": {"n": "0"}}}}),
    Decision(
        "8.1", "8. Otras dudas (H-08, H-10)", "Parcial dentro de otro sin encapsulante (H-08)",
        "En la norma, los parciales (G1, G2…) van uno al lado del otro; uno solo está «dentro» de otro como recinto de una "
        "encapsulante (y entonces G2 activo implica la encapsulante activa, así que G1 también lo está). El formato de "
        "archivo permite además meter G2 dentro de G1 sin encapsulante. G1 tiene su etapa X, inactiva; G2 tiene Y, activa; "
        "t tiene X_G1. ¿Qué se hace?",
        [("A", "Se admite: lo que está dentro de G1 también cuenta"), ("B", "Se admite: solo cuentan las etapas propias de G1"),
         ("C", "No se admite sin encapsulante: no compila")],
        "8.1", "El responsable señaló que un parcial dentro de otro necesita encapsulante; con ella, A y B dan lo mismo.", m81,
        expect={"A": "G1 cuenta como activo por Y (que está dentro): t franquea al arrancar y se pasa a E1.",
                "B": "La única etapa propia de G1 es X, inactiva: G1 no cuenta como activo y se queda en E0.",
                "C": "No compila: D-FORMATO (G2 está dentro de G1 sin encapsulante)."},
        checks={"A": {0: {"situation": ["E1", "Y"]}}, "B": {0: {"situation": ["E0", "Y"]}}, "C": {0: {"code": "D-FORMATO"}}}),
    Decision(
        "8.2", "8. Otras dudas (H-08, H-10)", "Receptividad que lee una salida continua (H-10)",
        "B tiene la salida continua y; t2: B → C tiene y. ¿Qué valor de y ve t2 durante el recorrido?",
        [("A", "Se prohíbe leer salidas continuas en receptividades"), ("B", "El valor de la situación estable anterior"),
         ("C", "El valor según la situación inestable del momento")],
        "8.2", "q no interviene en el grafcet.", m82,
        script=[fijar("p sube: A → B", p=True), fijar("q cambia (no interviene): siguiente instante", q=True)],
        expect={"A": "No compila: D-FORMATO.",
                "B": "Al llegar a B, t2 ve y = 0 (de antes): se queda en B con y encendida; pasa a C en el siguiente instante.",
                "C": "t2 ve y = 1 en cuanto B está activa: pasa a C en el mismo instante; B queda inestable e y no llega a salir."},
        checks={"A": {0: {"code": "D-FORMATO"}},
                "B": {1: {"situation": ["B"], "outputs": {"y": True}}, 2: {"situation": ["C"]}},
                "C": {1: {"situation": ["C"], "outputs": {"y": False}}}}),
]

POR_ID: dict[str, Decision] = {d.id: d for d in CATALOGO}

# Respuestas ya dadas en la hoja 08 (bloques 1 y 2), con las que se precarga docs/decisiones.json; son lecturas
# por defecto desde P-IMP-19 y P-IMP-20
RESPUESTAS_HOJA_08: dict[str, tuple[str, str]] = {
    "1.1": ("A", ""), "1.2": ("A", ""), "1.3": ("A", ""), "1.4": ("A", ""),
    "1.5": ("A", "Las memorizadas empiezan en 0; otro valor inicial se pone con una acción «al activar» en la "
                 "etapa inicial (n := 5 en E0), que se ejecuta al arrancar por la respuesta 1.1."),
    "2.1": ("C", "Dar conflicto si las dos se activan a la vez."), "2.2": ("B", ""),
    "2.3": ("A", "Realmente no es virtual, ya que cambia un valor: en la norma es una «etapa inestable»."),
    "2.4": ("A", ""), "2.5": ("A", ""),
}

# Respuestas dadas en el comparador el 27-10-2026 e incorporadas en P-IMP-22. 3.4 y 4.5 quedan registradas: se
# aplicarán cuando se ejecuten la encapsulación y elapsed (la encapsulación se ejecuta desde P-IMP-23).
RESPUESTAS_COMPARADOR: dict[str, str] = {
    "3.1": "A", "3.2": "A", "3.3": "A", "3.4": "A", "4.1": "A", "4.2": "A", "4.3": "A", "4.4": "B", "4.5": "A",
    "5.1": "situacion-anterior", "5.2": "B", "5.3": "A", "6.1": "A", "6.2": "A", "6.3": "A", "6.4": "A",
    # Segunda tanda, incorporada en P-IMP-26: 7.1 queda registrada (el programa ya hace A, documento 06)
    "7.1": "A", "7.3": "A", "7.4": "C", "7.5": "A", "7.8": "A", "8.2": "C",
}

# Respuestas dadas en el chat el 27-10-2026 e incorporadas en P-IMP-24 (7.7), P-IMP-25 (7.2 y 7.6) y P-IMP-27 (8.1)
RESPUESTAS_CHAT: dict[str, str] = {"7.7": "A", "7.2": "B", "7.6": "B", "8.1": "C"}

# Lo que el programa aplica hoy: el comparador muestra si la respuesta guardada ya está incorporada
RESPUESTAS_INCORPORADAS: dict[str, str] = {**{k: v for k, (v, _) in RESPUESTAS_HOJA_08.items()}, **RESPUESTAS_COMPARADOR,
                                           **RESPUESTAS_CHAT}
