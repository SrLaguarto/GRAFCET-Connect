"""Capa de traducción de avisos: del texto del núcleo al texto que lee el alumno.

El núcleo (`grafcet/`) escribe sus diagnósticos con su vocabulario (evoluciones, presupuesto, τ, lecturas…) y los
usan el banco de pruebas y los casos T, así que no se tocan. Aquí se traducen al mostrarlos: frases cortas, sin jerga y
sin códigos.
Los códigos y el texto técnico siguen en los datos y en la ayuda emergente («Referencia: …»).
"""
from __future__ import annotations

import re
from typing import Any

from grafcet.notation import x_etapa

LIMITE_LINEA = 130  # a partir de aquí, el aviso se parte: una frase en la lista y el resto en la ayuda emergente
MAX_NOMBRES = 4  # cuántas transiciones o etapas se nombran en un aviso de bucle
RECIENTES = 6  # cuántas de las últimas evoluciones se miran para saber qué se repite

# (patrón del mensaje del núcleo, texto para el usuario); la primera coincidencia manda
REGLAS: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(p, re.S), t) for p, t in (
    (r"^presupuesto de \d+ evoluciones agotado.*",
     "El grafcet no alcanza una situación estable: evoluciona sin fin."),
    (r"^contexto abandonado tras el límite",
     "Se abandonó la evolución: el grafcet no alcanzaba una situación estable."),
    (r"^espacio de traza insuficiente.*", "El registro de la simulación está lleno."),
    (r"^conflicto de escritura seguro sobre ([^:]+):.*",
     r"Dos acciones dan valores distintos a \1 a la vez. Cambia sus condiciones."),
    (r"^varias asignaciones simultáneas sobre (.+)$", r"Varias acciones dan valores distintos a \1 a la vez."),
    (r"^asignaciones sucesivas distintas sobre (.+) en el mismo instante.*",
     r"\1 recibe valores distintos en el mismo instante."),
    (r"^.+ lee .+, que .+ escribe .*",
     "Una acción lee una variable que otra escribe a la vez. Usa una variable auxiliar o separa las asignaciones."),
    (r"^transición→transición: (.+?) enlaza con la transición (.+)$",
     r"\1 está unida a la transición \2: entre dos transiciones debe haber una etapa."),
    (r"^(.+?)→(.+?) une dos elementos del mismo tipo.*",
     r"\1 y \2 son dos elementos del mismo tipo: solo se unen una etapa y una transición."
     " Queda como borrador y no se simula."),
    (r"^enlace de borrador (.+?)→(.+?) viola la alternancia.*\(etapa→etapa\)$",
     r"Enlace en borrador entre las etapas \1 y \2: dos etapas no pueden ir seguidas. "
     "Bórralo o pon una transición en medio."),
    (r"^enlace de borrador (.+?)→(.+?) viola la alternancia.*\(transición→transición\)$",
     r"Enlace en borrador entre las transiciones \1 y \2: dos transiciones no pueden ir seguidas. "
     "Bórralo o pon una etapa en medio."),
    (r"^enlace de borrador (.+?)→(.+?) viola la alternancia.*",
     r"Enlace en borrador entre \1 y \2: no respeta la alternancia etapa-transición. Bórralo o corrígelo."),
    (r"^etiqueta «(.+)» (?:repetida|ya existe) en el parcial.*", r"Ya existe otra etapa llamada «\1» en este grafcet."),
    (r"^(?:nombre|variable) «(.+)» (?:repetido|ya existe) en el ámbito.*", r"Ya existe otra variable llamada «\1»."),
    (r"^«(.+)» ya existe(?: en el ámbito)?; el ID no cambia", r"Ya existe «\1»: elige otro nombre."),
    (r"^grafcet sin etapas iniciales.*", "Falta una etapa inicial: marca al menos una."),
    (r"^transición sin etapas antes ni después.*",
     "Una transición necesita al menos una etapa unida, antes o después."),
    (r"^transición fuente con receptividad de nivel.*",
     "Una transición sin etapa anterior necesita un flanco (↑ o ↓) en su receptividad."),
    (r"^retardo cero:.*", "Un retardo de 0 s no se admite: usa otra duración."),
    (r"^lectura de salida continua .*",
     "Una condición lee una salida que se da de forma continua, y eso no se admite."),
    (r"^(.+) recibe acciones continuas y memorizadas$",
     r"\1 recibe acciones continuas y memorizadas a la vez: usa solo un tipo."),
    (r"^la expresión .+ debe ser booleana", "La condición debe ser verdadera o falsa."),
    (r"^un evento no puede usarse como condición continua o valor.*",
     "Un flanco (↑ o ↓) solo sirve como evento, no como condición continua."),
    (r"^el disparador .+ debe ser un evento.*", "El disparador debe ser un flanco (↑ o ↓)."),
    (r"^el valor .+ no es asignable a (.+?) \(.+\)$", r"El valor no se puede asignar a \1: es de otro tipo."),
    (r"^unidad .+ asignada a .+", "Las unidades no coinciden."),
    (r"^se sale de (.+?) con (.+?) aún activas en su expansión.*",
     r"Se sale de la macroetapa \1 con etapas aún activas en su expansión (\2). "
     "Sincroniza las ramas antes de la etapa de salida."),
    (r"^se fuerza el recinto (.+?) con su encapsulante (.+?) inactiva.*",
     r"Se fuerza el recinto \1, pero su encapsulante \2 no está activa."),
    (r"^órdenes (?:con igual destino|vigentes con el mismo destino).*",
     "Dos órdenes de forzado imponen situaciones distintas al mismo grafcet parcial."),
    (r"^situación inicial inestable \((.+?) franqueables al arrancar\).*",
     r"Al arrancar ya se puede franquear \1: la situación inicial no es estable."),
    (r"^división por cero$", "División por cero."),
    (r"^desbordamiento de entero de 64 bits.*", "El número es demasiado grande."),
    (r"^(.+) fuera de dominio$", r"El valor de \1 queda fuera de su rango."),
    (r"^(?:ciclo en la propiedad de parciales|ciclo en la relación de forzado|recursión de expansión).*",
     "Hay un ciclo en la jerarquía: algo depende de sí mismo."),
    (r"^etapas iniciales .+ dentro de un recinto cuya encapsulante no es inicial.*",
     "Hay una etapa inicial dentro de un recinto cuya encapsulante no es inicial."),
    (r"^etapas iniciales (.+) dentro de la expansión (.+?): no se admiten.*",
     r"Hay etapas iniciales (\1) dentro de la expansión \2, y los ajustes de simulación actuales no lo admiten."),
    (r"^encapsulante inicial con recinto sin etapa inicial.*",
     "La encapsulante es inicial, pero su recinto no tiene etapa inicial."),
    (r"^las variables que no son entradas empiezan en 0:.*",
     "Solo las entradas tienen valor inicial. Para otro valor, usa una acción «al activar» en la etapa inicial."),
))
LISTAS = re.compile(r"\[((?:'[^']*'(?:, )?)+)\]")  # la lista de Python ["'a', 'b'"] se escribe «a, b»
REFERENCIAS_INTERNAS = re.compile(r"\s*[(;,]?\s*\(?(?:lectura|opción|respuesta|hoja)\s+\d[\d.,A-Z ]*\)?")
TUTEOS_NUCLEO: tuple[tuple[str, str], ...] = (
    ("Quite uno de los dos de la barra y vuelva a unirlo.", "Quita uno de los dos de la barra y vuelve a unirlo."),
    ("Únala o bórrela.", "Únela o bórrala."),
    ("quite de la barra lo que sobre", "quita de la barra lo que sobre"),
    ("o use una barra de alternativa", "o usa una barra de alternativa"),
    ("para otro valor use una acción", "para otro valor usa una acción"),
    ("use una barra de simultaneidad.", "usa una barra de simultaneidad."),
    ("use una etapa encapsulante", "usa una etapa encapsulante"),
    ("quite antes esos usos", "quita antes esos usos"),
    ("bórrelos antes de ", "bórralos antes de "),
    ("quítele la marca antes de ", "quítale la marca antes de "),
    ("quítelas antes de ", "quítalas antes de "),
    ("quítelo antes de ", "quítalo antes de "),
    ("quítela de la orden antes de ", "quítala de la orden antes de "),
    ("vacíe la expansión antes", "vacía la expansión antes"),
    ("borre la macroetapa entera, no solo esa etapa", "borra la macroetapa entera, no solo esa etapa"),
    ("corrija los errores indicados", "corrige los errores indicados"),
    ("declare su estado temporal", "declara su estado temporal"),
)
CORRECCIONES = {
    "D-LIM-EVOL": "Revisa las receptividades de las transiciones que se repiten: no deben ser ciertas a la vez.",
    "D-TRAZA-LIM": "Reinicia la simulación para vaciar el registro.",
    "D-SEM-PENDIENTE": "Este caso depende de un ajuste de simulación sin decidir. Elígelo en Ajustes de simulación.",
    "D-EXP-PENDIENTE": "Completar la expresión con los bloques de la paleta.",
    "D-BARRA-SUELTA": "Une la barra a lo que va por encima y por debajo, o bórrala",
}


def amable(mensaje: str, codigo: str | None = None) -> str:
    """El mensaje del núcleo en lenguaje llano. Lo que no tiene regla pasa tal cual, sin referencias internas
    («lectura 6.1 A», «hoja 08, 2.2») ni el símbolo τ."""
    texto = LISTAS.sub(lambda m: m.group(1).replace("'", ""), mensaje.strip())
    for patron, plantilla in REGLAS:
        if patron.match(texto):
            return patron.sub(plantilla, texto, count=1)
    texto = REFERENCIAS_INTERNAS.sub("", texto)
    for antes, despues in TUTEOS_NUCLEO:
        texto = texto.replace(antes, despues)
    texto = texto.replace("τ = 0", "el instante inicial").replace("τ=0", "el instante inicial")
    return texto.replace("τ", "el tiempo").strip()


def correccion_amable(codigo: str, correccion: str) -> str:
    """La sugerencia del catálogo de diagnósticos, o la nuestra si la del catálogo usa jerga."""
    return CORRECCIONES.get(codigo, correccion)


def partir(texto: str, limite: int = LIMITE_LINEA) -> tuple[str, str]:
    """(principal, resto): si el texto pasa del límite, su primera frase y lo demás para la ayuda emergente."""
    if len(texto) <= limite:
        return texto, ""
    corte = re.search(r"[.;:]\s", texto)
    if corte is None or corte.start() + 1 > limite:
        return texto[:limite].rsplit(" ", 1)[0] + "…", texto
    return texto[:corte.start() + 1], texto


def _lista(nombres: list[str]) -> str:
    """«t1», «t1 y t2», «t1, t2 y t3», con «…» si hay más de las que se nombran."""
    visibles = nombres[:MAX_NOMBRES]
    resto = "…" if len(nombres) > MAX_NOMBRES else ""
    if len(visibles) == 1:
        return visibles[0] + resto
    return ", ".join(visibles[:-1]) + " y " + visibles[-1] + resto


def _clave_natural(texto: str) -> list[tuple[int, int | str]]:
    """Clave de orden natural (`t5, t6, t7 y t8`, `E2` antes que `E10`)."""
    return [(0, int(p)) if p.isdecimal() else (1, p.casefold()) for p in re.split(r"(\d+)", texto)]


def mezcla_acciones(modelo: dict[str, Any], nombres: dict[str, str], variable: str) -> str:
    etapas = {e["id"]: nombres.get(e["id"], e["label"]) for e in modelo["steps"]}
    modos: dict[str, set[str]] = {"continuous": set(), "stored": set()}
    for accion in modelo["actions"]:
        etapa = accion.get("stepRef")
        modo = accion.get("mode")
        if accion.get("targetRef") == variable and etapa in etapas and modo in modos:
            modos[modo].add(etapa)

    def lista(ids: set[str]) -> str:
        etiquetas = (x_etapa(etapas[ident]) for ident in ids)
        orden = sorted(etiquetas, key=_clave_natural)
        return f" ({', '.join(orden[:-1]) + ' y ' if len(orden) > 1 else ''}{orden[-1]})" if orden else ""

    continuas, memorizadas = lista(modos["continuous"]), lista(modos["stored"])
    nombre = nombres.get(variable, variable)
    return f"{nombre} recibe acciones continuas{continuas} y memorizadas{memorizadas} a la vez: usa solo un tipo."


def _repetidas(evoluciones: list[dict[str, Any]], nombres: dict[str, str]) -> tuple[list[str], list[str]]:
    """Las transiciones que se franquean en las últimas evoluciones y las etapas que cambian entre ellas, en orden natural."""
    ultimas = [e for e in evoluciones if e.get("evolutionIndex", 0) > 0][-RECIENTES:]
    transiciones = sorted(
        list(dict.fromkeys(nombres.get(t, t) for e in ultimas for t in e.get("cleared", []))),
        key=_clave_natural,
    )
    situaciones = [set(e.get("situation", [])) for e in ultimas]
    if not situaciones:
        return transiciones, []
    cambian = set().union(*situaciones) - set.intersection(*situaciones)
    return transiciones, sorted((nombres.get(s, s) for s in cambian), key=_clave_natural)


def motivo_parada(codigo: str, mensaje: str, evoluciones: list[dict[str, Any]],
                  nombres: dict[str, str]) -> list[tuple[str, str]]:
    """Por qué se ha parado el motor, como pares (texto, ayuda emergente) para la lista de avisos. Un ciclo de
    evoluciones sin fin (D-LIM-EVOL) nombra las transiciones y etapas que se repiten; lo demás, el mensaje traducido."""
    if codigo != "D-LIM-EVOL":
        texto, completo = partir(amable(mensaje, codigo))
        return [("Simulación detenida: " + texto[:1].lower() + texto[1:], completo or mensaje)]
    transiciones, etapas = _repetidas(evoluciones, nombres)
    principal = "Simulación detenida: el grafcet no alcanza una situación estable."
    if not transiciones:
        return [(principal, mensaje)]
    una = len(transiciones) == 1
    causa = (f"{'La transición' if una else 'Las transiciones'} {_lista(transiciones)} se "
             f"{'franquea' if una else 'franquean'} en ciclo sin fin porque "
             f"{'su receptividad es cierta' if una else 'sus receptividades son ciertas a la vez'}"
             f". Revisa "
             f"{'esa receptividad' if una else 'esas receptividades'}.")
    detalle = causa + (f" Cambian de estado las etapas {_lista(etapas)}." if etapas else "")
    detalle += f"\nDetalle técnico: {mensaje}"
    return [(principal, detalle), (causa, detalle)]


CORRECCION_VENCIMIENTOS = "Usa tiempos distintos o evita que compitan por la misma etapa."
PREFIJO_VENCIMIENTOS = "vencimientos simultáneos cuyo resultado depende del orden"


def _dueno_del_temporizador(modelo: dict[str, Any], clave: str) -> tuple[str, str] | None:
    """(«transicion» | «accion» | «limite», id) del elemento donde está el temporizador de esa clave: la clave de un retardo es el ID
    de su expresión (con sufijo «.i» si está anidado) y la de una acción limitada, «limit:<acción>»."""
    if clave.startswith("limit:"):
        aid = clave[len("limit:"):]
        return ("limite", aid) if any(a["id"] == aid for a in modelo.get("actions", [])) else None
    eid = clave.split(".")[0]
    for t in modelo.get("transitions", []):
        if t.get("conditionRef") == eid:
            return "transicion", t["id"]
    for a in modelo.get("actions", []):
        if eid in (a.get("conditionRef"), a.get("valueRef"), (a.get("trigger") or {}).get("expressionRef")):
            return "accion", a["id"]
    return None


def _tras(modelo: dict[str, Any], nombres: dict[str, str], tid: str) -> str:
    """«tras X1», «tras X1 y X2» o «en una transición fuente»: cómo se sitúa una transición por las etapas que tiene encima."""
    t = next((t for t in modelo.get("transitions", []) if t["id"] == tid), {})
    previas = [x_etapa(nombres.get(s, s)) for s in t.get("preRefs", [])]
    if not previas:
        return "en una transición fuente"
    return "tras " + (previas[0] if len(previas) == 1 else ", ".join(previas[:-1]) + " y " + previas[-1])


def _claves_de_corchetes(mensaje: str) -> list[str]:
    mo = re.search(r"\[([^\]]+)\]", mensaje)
    if not mo:
        return []
    return [p.strip().strip("'\"") for p in mo.group(1).split(",") if p.strip().strip("'\"")]


def _describir_duenos(duenos: list[tuple[str, str]], modelo: dict[str, Any], nombres: dict[str, str]) -> list[str]:
    partes: list[str] = []
    for tipo, i in sorted(duenos, key=lambda item: _clave_natural(nombres.get(item[1], item[1]))):
        if tipo == "transicion":
            partes.append(f"la transición {nombres.get(i, i)} ({_tras(modelo, nombres, i)})")
            continue
        a = next((x for x in modelo.get("actions", []) if x["id"] == i), None)
        if a is None:
            partes.append(nombres.get(i, i))
            continue
        accion = f"la acción de {nombres.get(a.get('targetRef'), a.get('targetRef'))} en la etapa {x_etapa(nombres.get(a['stepRef'], a['stepRef']))}"
        partes.append(("el límite de " if tipo == "limite" else "") + accion)
    return partes


def vencimientos_en_palabras(d: dict[str, Any], modelo: dict[str, Any], nombres: dict[str, str]) -> tuple[str, str] | None:
    """(mensaje, corrección) en lenguaje llano para el diagnóstico de vencimientos simultáneos o coincidencias lote–vencimiento
    (`D-SEM-PENDIENTE`, «temporal.coincidencias»), con los elementos nombrados por su etiqueta. `None` si `d` no es de ese tipo."""
    if d.get("code") != "D-SEM-PENDIENTE":
        return None
    bruto = str(d.get("message", ""))
    if bruto.startswith(("el lote ", "lote ")):
        claves = _claves_de_corchetes(bruto)
        duenos = list(dict.fromkeys(x for x in (_dueno_del_temporizador(modelo, c) for c in claves) if x is not None))
        partes = _describir_duenos(duenos, modelo, nombres)
        quien = _lista(partes) if partes else "un temporizador"
        if "cambia la base" in bruto:
            return (
                f"Una entrada cambia al mismo tiempo que vence {quien}, y falta decidir qué ocurre primero.",
                "Evita que el cambio de entrada coincida justo con ese vencimiento o cambia la duración del temporizador.",
            )
        if "depende del orden" in bruto:
            return (
                f"Un cambio de entrada y el vencimiento de {quien} ocurren a la vez y el resultado depende del orden.",
                "Separa en el tiempo el cambio de entrada y ese vencimiento, o revisa cómo interactúan.",
            )
        return (
            f"Un cambio de entrada coincide en el mismo instante con el vencimiento de {quien}, y falta decidir el orden.",
            "Separa ese cambio de entrada del vencimiento temporal o ajusta la duración del temporizador.",
        )

    if not bruto.startswith(PREFIJO_VENCIMIENTOS):
        return None
    claves = [c.strip() for c in str((d.get("evidence") or {}).get("claves", "")).split(",") if c.strip()]
    duenos = list(dict.fromkeys(x for x in (_dueno_del_temporizador(modelo, c) for c in claves) if x is not None))
    final = "tienen temporizadores que vencen en el mismo instante y el resultado depende de cuál vaya primero."
    if not duenos:
        return "Varios temporizadores vencen en el mismo instante y el resultado depende de cuál vaya primero.", CORRECCION_VENCIMIENTOS
    if all(tipo == "transicion" for tipo, _ in duenos):
        duenos_ord = sorted(duenos, key=lambda item: _clave_natural(nombres.get(item[1], item[1])))
        etiquetas = [nombres.get(i, i) for _, i in duenos_ord]
        tras = [_tras(modelo, nombres, i) for _, i in duenos_ord]
        if len(set(tras)) == 1:
            situadas, lugar = etiquetas, f" ({tras[0]})"
        else:
            situadas, lugar = [f"{e} ({t})" for e, t in zip(etiquetas, tras)], ""
        if len(duenos_ord) == 1:
            return f"La transición {situadas[0]}{lugar} {final.replace('tienen', 'tiene varios', 1)}", CORRECCION_VENCIMIENTOS
        return f"Las transiciones {_lista(situadas)}{lugar} {final}", CORRECCION_VENCIMIENTOS
    partes = _describir_duenos(duenos, modelo, nombres)
    return f"Los temporizadores de {_lista(partes)} vencen en el mismo instante y el resultado depende de cuál vaya primero.", \
        CORRECCION_VENCIMIENTOS
