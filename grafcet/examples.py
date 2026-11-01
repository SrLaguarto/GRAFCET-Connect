"""Ejemplos del simulador y del banco de pruebas.

Cada ejemplo devuelve su modelo (documento 09, construido con grafcet.builder.M) y la posición de cada
elemento en el dibujo. Las explicaciones citan la respuesta o la decisión que muestran; ninguna declara
conformidad.
"""
from __future__ import annotations

from typing import Callable

from .builder import M


def ej_temporizada() -> tuple[M, dict]:
    m = M().var("marcha").var("fin").var("motor", "output").var("luz", "output").var("ciclos", "internal", "int")
    m.step("E0", True).step("E1").step("E2")
    m.trans("t1", ["E0"], ["E1"], "marcha").trans("t2", ["E1"], ["E2"], "delay(3 s, active(E1), 0 s)")
    m.trans("t3", ["E2"], ["E0"], "fin")
    m.cont("E1", "motor").cont("E2", "luz").stored("E2", "ciclos", "activation", "ciclos + 1")
    return m, {"E0": (220, 60), "t1": (220, 140), "E1": (220, 220), "t2": (220, 300), "E2": (220, 380), "t3": (220, 460)}


def ej_arranque() -> tuple[M, dict]:
    m = M().var("parar").var("motor", "output").var("n", "internal", "int")
    m.step("E0", True).step("E1").step("E2")
    m.stored("E0", "n", "activation", "5").cont("E1", "motor")
    m.trans("t1", ["E0"], ["E1"], "n = 5").trans("t2", ["E1"], ["E2"], "parar")
    return m, {"E0": (220, 60), "t1": (220, 140), "E1": (220, 220), "t2": (220, 300), "E2": (220, 380)}


def ej_paralelo() -> tuple[M, dict]:
    m = M().var("p").var("q").var("r").var("s")
    for sid in "ABCDEF":
        m.step(sid, sid == "A")
    m.trans("t1", ["A"], ["B", "C"], "p").trans("t2", ["B"], ["D"], "q").trans("t3", ["C"], ["E"], "r")
    m.trans("t4", ["D", "E"], ["F"], "s").trans("t5", ["F"], ["A"], "NOT s")
    return m, {"A": (220, 50), "t1": (220, 115), "B": (150, 190), "C": (290, 190), "t2": (150, 260), "t3": (290, 260),
               "D": (150, 330), "E": (290, 330), "t4": (220, 405), "F": (220, 480), "t5": (220, 545)}


def ej_contador() -> tuple[M, dict]:
    m = M().var("pulso").var("borrar").var("alarma", "output").var("n", "internal", "int")
    m.step("A", True).step("B")
    m.cont("A", "alarma", "n >= 3").stored("A", "n", "event", "n + 1", event="rise(pulso)")
    m.trans("t1", ["A"], ["B"], "borrar").trans("t2", ["B"], ["A"], "NOT borrar").stored("B", "n", "activation", "0")
    return m, {"A": (220, 70), "t1": (220, 150), "B": (220, 230), "t2": (220, 310)}


def ej_bloqueo_u03() -> tuple[M, dict]:
    m = M().var("p").var("reinicio").step("A", True).step("B").step("C")
    m.trans("t", ["A"], ["B"], "rise(p)").trans("u", ["B"], ["C"], "rise(p)").trans("v", ["C"], ["A"], "reinicio")
    return m, {"A": (220, 60), "t": (220, 140), "B": (220, 220), "u": (220, 300), "C": (220, 380), "v": (220, 460)}


def ej_conflicto() -> tuple[M, dict]:
    m = M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C")
    m.trans("t", ["A"], ["B", "C"], "p")
    m.stored("B", "z", "activation", "1", aid="aB").stored("C", "z", "activation", "2", aid="aC")
    return m, {"A": (220, 60), "t": (220, 130), "B": (150, 215), "C": (330, 215)}


def ej_conflicto_ejecucion() -> tuple[M, dict]:
    m = M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C", True).step("D")
    m.trans("t", ["A"], ["B"], "p").trans("u", ["C"], ["D"], "p")
    m.stored("B", "z", "activation", "1", aid="aB").stored("D", "z", "activation", "2", aid="aD")
    return m, {"A": (150, 60), "t": (150, 140), "B": (150, 220), "C": (330, 60), "u": (330, 140), "D": (330, 220)}


def ej_contador_inestable() -> tuple[M, dict]:
    """Ejemplo aportado por el responsable el 27-10-2026: la etapa 2 suma aunque sea inestable."""
    m = M().var("I00").var("I02").var("Q00", "output").var("Q01", "output").var("CT", "internal", "int")
    m.step("0", True).step("1").step("2")
    m.trans("t1", ["0"], ["1"], "I00").trans("t2", ["1"], ["2"], "fall(I02)")
    m.trans("t3", ["2"], ["0"], "CT >= 3").trans("t4", ["2"], ["1"], "CT < 3")
    m.cont("1", "Q00").cont("1", "Q01").stored("2", "CT", "activation", "CT + 1").cont("2", "Q00").cont("2", "Q01")
    return m, {"0": (160, 60), "t1": (160, 140), "1": (160, 230), "t2": (160, 320), "2": (160, 410),
               "t3": (160, 500), "t4": (320, 500)}


def ej_contador_flanco() -> tuple[M, dict]:
    """Segundo ejemplo aportado por el responsable el 27-10-2026: CT cuenta cada subida de I02 mientras 1 está activa."""
    m = M().var("I00").var("I01").var("I02").var("Q00", "output").var("Q01", "output").var("CT", "internal", "int")
    m.step("0", True).step("1")
    m.trans("t1", ["0"], ["1"], "I00").trans("t2", ["1"], ["0"], "I01")
    m.stored("1", "CT", "event", "CT + 1", event="rise(I02)").cont("1", "Q00").cont("1", "Q01")
    return m, {"0": (160, 60), "t1": (160, 140), "1": (160, 230), "t2": (160, 320)}


def ej_macroetapa() -> tuple[M, dict]:
    m = M().partial("X").var("p").var("q").var("r").var("s").var("motor", "output")
    m.step("A", True).step("B").step("E1", kind="entry", partial="X").step("K", partial="X").step("S1", kind="exit", partial="X")
    m.trans("tq", ["E1"], ["K"], "q", partial="X").trans("tr", ["K"], ["S1"], "r", partial="X").cont("K", "motor")
    m.macro("M", "X", "E1", "S1").trans("tp", ["A"], ["M"], "p").trans("ts", ["M"], ["B"], "s").trans("tb", ["B"], ["A"], "NOT s")
    return m, {"A": (160, 60), "tp": (160, 140), "M": (160, 220), "ts": (160, 300), "B": (160, 380), "tb": (160, 450),
               "E1": (430, 100), "tq": (430, 180), "K": (430, 260), "tr": (430, 340), "S1": (430, 420)}


def ej_alternativas() -> tuple[M, dict]:
    """Una secuencia con una alternativa que la salta (E0 → E2) y una rama que vuelve (E2 → E1), para probar el editor."""
    m = M()
    for v in ("marcha", "rapida", "fin1", "fin2", "repetir", "reinicio"):
        m.var(v)
    m.var("motor", "output").var("luz", "output").var("fin", "output")
    m.step("E0", True).step("E1").step("E2").step("E3")
    m.trans("t1", ["E0"], ["E1"], "marcha").trans("t2", ["E1"], ["E2"], "fin1").trans("t3", ["E2"], ["E3"], "fin2")
    m.trans("t4", ["E3"], ["E0"], "reinicio")
    m.trans("t5", ["E0"], ["E2"], "rapida")      # salto de secuencia: se salta t1, E1 y t2
    m.trans("t6", ["E2"], ["E1"], "repetir")     # rama que vuelve al enlace entre t1 y E1
    m.cont("E1", "motor").cont("E2", "luz").cont("E3", "fin")
    return m, {"E0": (220, 60), "t1": (220, 140), "E1": (220, 220), "t2": (220, 300), "E2": (220, 380),
               "t3": (220, 460), "E3": (220, 540), "t4": (220, 620), "t5": (400, 260), "t6": (400, 440)}


def ej_encapsulacion() -> tuple[M, dict]:
    m = M().partial("R").var("p").var("q").var("r").var("luz", "output")
    m.step("H", True, kind="enclosing").step("Z")
    m.step("I", True, partial="R").step("J", partial="R").step("K", partial="R")
    m.trans("t", ["H"], ["Z"], "p").trans("u", ["Z"], ["H"], "q")
    m.trans("v", ["I"], ["J"], "r", partial="R").trans("w", ["K"], ["J"], "r", partial="R").cont("J", "luz")
    m.enclosure("H", "R", ["K"])
    return m, {"H": (160, 60), "t": (160, 140), "Z": (160, 220), "u": (160, 290),
               "I": (430, 70), "v": (430, 150), "J": (430, 230), "K": (580, 70), "w": (580, 150)}


def ej_forzado() -> tuple[M, dict]:
    m = M().partial("G").var("f").var("a").var("b").var("c")
    m.step("H2", True).step("H").step("A", True, partial="G").step("B", partial="G").step("C", partial="G")
    m.trans("t1", ["H2"], ["H"], "f").trans("t2", ["H"], ["H2"], "NOT f")
    m.trans("ta", ["A"], ["B"], "a", partial="G").trans("tb", ["B"], ["C"], "b", partial="G").trans("tc", ["C"], ["A"], "c", partial="G")
    m.force("F", "H", "G", "explicit", ["B"])
    return m, {"H2": (160, 60), "t1": (160, 140), "H": (160, 220), "t2": (160, 290),
               "A": (480, 60), "ta": (480, 140), "B": (480, 220), "tb": (480, 300), "C": (480, 380), "tc": (480, 450)}


def ej_seleccion() -> tuple[M, dict]:
    """Selección de secuencia con condiciones mutuamente excluyentes (referencias del responsable)."""
    m = M().var("a").var("b")
    m.step("5", True).step("6").step("7")
    m.trans("t1", ["5"], ["6"], "a AND NOT b").trans("t2", ["5"], ["7"], "NOT a AND b")
    return m, {"5": (120, 60), "t1": (120, 160), "6": (120, 260), "t2": (340, 160), "7": (340, 260)}


def ej_salto() -> tuple[M, dict]:
    m = M()
    for v in ("avanzar1", "avanzar2", "avanzar3", "saltar"):
        m.var(v)
    m.step("1", True).step("2").step("3").step("4")
    for n in range(1, 4):
        m.trans(f"t{n}", [str(n)], [str(n+1)], f"avanzar{n}")
    m.trans("salto", ["1"], ["4"], "saltar")
    return m, {"1": (300, 60), "t1": (300, 140), "2": (300, 220), "t2": (300, 300),
               "3": (300, 380), "t3": (300, 460), "4": (300, 540), "salto": (80, 140)}


def ej_repeticion() -> tuple[M, dict]:
    _, layout = ej_salto()
    # Otro modelo: la decisión se toma después de 3; vuelve a 2 o continúa a 4.
    m = M()
    for v in ("inicio", "avance", "fin", "repetir"):
        m.var(v)
    m.step("1", True).step("2").step("3").step("4")
    m.trans("t1", ["1"], ["2"], "inicio").trans("t2", ["2"], ["3"], "avance")
    m.trans("t3", ["3"], ["4"], "fin AND NOT repetir")
    m.trans("retorno", ["3"], ["2"], "repetir")
    layout.pop("salto")
    layout["retorno"] = (80, 460)
    return m, layout


EJEMPLOS: dict[str, tuple[str, str, Callable[[], tuple[M, dict]]]] = {
    "seleccion": ("Selección de secuencia", "Desde 5, active solo a para ir a 6, o solo b para ir a 7. "
                  "Las dos transiciones salen de una línea común. En Stop puede cambiar las condiciones a a y NOT a.", ej_seleccion),
    "salto": ("Salto de etapas", "Desde 1, active saltar para ir directamente a 4. La rama lateral contiene su propia transición.", ej_salto),
    "repeticion": ("Repetición de secuencia", "Active inicio para ir a 2; desactívelo. Active avance para ir a 3 y desactívelo. "
                   "Active repetir para volver a 2, o fin para ir a 4. El retorno lleva una flecha ascendente automática.", ej_repeticion),
    "alternativas": ("Alternativas y salto de secuencia", "E0 → E1 → E2 → E3 con dos alternativas: «rapida» salta de E0 a E2 "
                     "(salto de secuencia) y «repetir» devuelve de E2 a E1 (rama que vuelve: dos ramas llegan a E1 y a "
                     "E2). Pulse «marcha» o «rapida» desde E0; en E2, «fin2» sigue y «repetir» vuelve. Pulse Stop "
                     "para ver cómo está construido y abrir sus propias ramas arrastrando de un punto de unión a un "
                     "hueco (crea el elemento siguiente) o a un enlace (la rama se une ahí).", ej_alternativas),
    "temporizada": ("Secuencia con temporización", "Pulse «marcha»: E1 activa el motor; a los 3 s pasa a E2 (luz, "
                    "ciclos+1). «fin» vuelve a E0. Pruebe a soltar «marcha» y poner «fin»=1 antes de los 3 s: E2 es "
                    "una etapa inestable (sin luz, pero ciclos+1 se ejecuta). Con «marcha»=1 y «fin»=1, E1 sale y vuelve "
                    "a entrar en el mismo instante sin interrumpir su duración (P-IMP-18): el temporizador sigue vencido, "
                    "el ciclo se repite sin fin en tiempo cero y el motor lo corta con D-LIM-EVOL.", ej_temporizada),
    "arranque": ("Arranque con acción inicial", "Al arrancar se ejecuta n := 5 en la etapa inicial E0 (hoja 08, "
                 "1.1) y t1 ve ese valor en el mismo instante (2.3), así que el grafcet evoluciona en τ = 0 (1.2): "
                 "E0 queda inestable y se arranca en E1 con el motor en marcha.", ej_arranque),
    "paralelo": ("Paralelismo y sincronización", "p divide en dos ramas; q y r avanzan cada una; s solo franquea t4 "
                 "cuando D y E están activas a la vez.", ej_paralelo),
    "contador": ("Contador por eventos", "Cada subida de «pulso» suma 1 a n (acción por evento). Pulsar sin soltar no "
                 "cuenta dos veces. Con n ≥ 3 se enciende «alarma». «borrar» pone n a 0.", ej_contador),
    "bloqueo-u03": ("Flanco en el recorrido (U-03)", "Dos transiciones seguidas con ↑p. Con la lectura por defecto, "
                    "«situación anterior» (comparador, 5.1), una subida de p solo franquea t y se queda en B. En las "
                    "lecturas de interpretación (Ajustes en el simulador; Opciones en el banco) puede probar «recorrido» "
                    "(llega a C; con «reinicio»=1 gira sin fin).", ej_bloqueo_u03),
    "contador-inestable": ("Contador con etapa inestable", "Ejemplo del responsable. I00 lleva a 1. Cada bajada de I02 "
                           "pasa por 2, que suma 1 a CT al activarse y, mientras CT < 3, vuelve a 1 en el mismo instante: 2 "
                           "queda inestable (no enciende sus salidas), pero la suma se hace. A la tercera bajada, CT = 3 y se "
                           "vuelve a 0. Con los flancos «por ciclo» en vez de «de uno en uno», una sola bajada de I02 daría la "
                           "vuelta tres veces en el mismo instante.", ej_contador_inestable),
    "contador-flanco": ("Contador por flanco en una etapa", "Ejemplo del responsable. I00 lleva a 1 e I01 vuelve a 0. "
                        "Mientras 1 está activa, cada subida de I02 suma 1 a CT (acción por evento ↑I02); mantener I02 "
                        "pulsada no vuelve a contar, y en 0 no cuenta. Si I02 sube en el mismo instante en que se sale de 1, "
                        "no cuenta (respuesta 5.2 B).", ej_contador_flanco),
    "macroetapa": ("Macroetapa (jerarquía)", "p lleva a la macroetapa M: se activa su etapa de entrada E1. q y r recorren la "
                   "expansión. Aunque s valga 1, solo se sale de M cuando su salida S1 está activa; la macroetapa cuenta como "
                   "activa mientras haya alguna etapa de su expansión activa.", ej_macroetapa),
    "encapsulacion": ("Encapsulación (jerarquía)", "Al arrancar, H e I (iniciales). p: sale de H y su recinto R se vacía. "
                      "q: vuelve a H y se activa K, la etapa marcada con *, no I ni la última situación. r mueve el contenido a "
                      "J y enciende la luz.", ej_encapsulacion),
    "forzado": ("Forzado (jerarquía)", "f activa H y la orden G{B} lleva el parcial G a {B}. Mientras H está activa, G no "
                "evoluciona aunque pulse a, b o c. Al quitar f se retira la orden y G sigue desde B.", ej_forzado),
    "conflicto": ("Conflicto de escritura al compilar", "t activa B y C en la misma evolución; B escribe z:=1 y C z:=2. "
                  "Es un conflicto seguro: el programa no puede compilarse.", ej_conflicto),
    "conflicto-ejecucion": ("Conflicto de escritura en ejecución", "t y u son independientes, pero ambas dependen de p: "
                            "al subir p se activan B y D a la vez y escriben valores distintos en z. Solo se sabe al "
                            "ejecutar: D-ESCRITURA-CONFLICTO, sin elegir valor.", ej_conflicto_ejecucion),
}
