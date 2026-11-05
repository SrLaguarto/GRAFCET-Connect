"""Capa de traducción de avisos: del texto del núcleo al texto que lee el alumno.

El núcleo (`grafcet/`) escribe sus diagnósticos con su vocabulario (evoluciones, presupuesto, τ, lecturas…) y los
usan el banco de pruebas y los casos T, así que no se tocan. Aquí se traducen al mostrarlos: frases cortas, sin jerga y
sin códigos.
Los códigos y el texto técnico siguen en los datos y en la ayuda emergente («Referencia: …»).
"""
from __future__ import annotations

import re
from typing import Any

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
     r"Dos acciones dan valores distintos a \1 a la vez. Cambie sus condiciones."),
    (r"^varias asignaciones simultáneas sobre (.+)$", r"Varias acciones dan valores distintos a \1 a la vez."),
    (r"^asignaciones sucesivas distintas sobre (.+) en el mismo instante.*",
     r"\1 recibe valores distintos en el mismo instante."),
    (r"^.+ lee .+, que .+ escribe .*",
     "Una acción lee una variable que otra escribe a la vez. Use una variable auxiliar o separe las asignaciones."),
    (r"^transición→transición: (.+?) enlaza con la transición (.+)$",
     r"\1 está unida a la transición \2: entre dos transiciones debe haber una etapa."),
    (r"^(.+?)→(.+?) une dos elementos del mismo tipo.*",
     r"\1 y \2 son dos elementos del mismo tipo: solo se unen una etapa y una transición."
     " Queda como borrador y no se simula."),
    (r"^enlace de borrador (.+?)→(.+?) viola la alternancia.*",
     r"Enlace de borrador \1→\2 no respeta la alternancia etapa-transición y no se simula."),
    (r"^etiqueta «(.+)» (?:repetida|ya existe) en el parcial.*", r"Ya existe otra etapa llamada «\1» en este grafcet."),
    (r"^(?:nombre|variable) «(.+)» (?:repetido|ya existe) en el ámbito.*", r"Ya existe otra variable llamada «\1»."),
    (r"^«(.+)» ya existe(?: en el ámbito)?; el ID no cambia", r"Ya existe «\1»: elija otro nombre."),
    (r"^grafcet sin etapas iniciales.*", "Falta una etapa inicial: marque al menos una."),
    (r"^transición sin etapas antes ni después.*",
     "Una transición necesita al menos una etapa unida, antes o después."),
    (r"^transición fuente con receptividad de nivel.*",
     "Una transición sin etapa anterior necesita un flanco (↑ o ↓) en su receptividad."),
    (r"^retardo cero:.*", "Un retardo de 0 s no se admite: use otra duración."),
    (r"^lectura de salida continua .*",
     "Una condición lee una salida que se da de forma continua, y eso no se admite."),
    (r"^(.+) recibe acciones continuas y memorizadas$",
     r"\1 recibe acciones continuas y memorizadas a la vez: use solo un tipo."),
    (r"^la expresión .+ debe ser booleana", "La condición debe ser verdadera o falsa."),
    (r"^un evento no puede usarse como condición continua o valor.*",
     "Un flanco (↑ o ↓) solo sirve como evento, no como condición continua."),
    (r"^el disparador .+ debe ser un evento.*", "El disparador debe ser un flanco (↑ o ↓)."),
    (r"^el valor .+ no es asignable a (.+?) \(.+\)$", r"El valor no se puede asignar a \1: es de otro tipo."),
    (r"^unidad .+ asignada a .+", "Las unidades no coinciden."),
    (r"^se sale de (.+?) con (.+?) aún activas en su expansión.*",
     r"Se sale de la macroetapa \1 con etapas aún activas en su expansión (\2). "
     "Sincronice las ramas antes de la etapa de salida."),
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
     "Solo las entradas tienen valor inicial. Para otro valor, use una acción «al activar» en la etapa inicial."),
))
LISTAS = re.compile(r"\[((?:'[^']*'(?:, )?)+)\]")  # la lista de Python ["'a', 'b'"] se escribe «a, b»
REFERENCIAS_INTERNAS = re.compile(r"\s*[(;,]?\s*\(?(?:lectura|opción|respuesta|hoja)\s+\d[\d.,A-Z ]*\)?")
CORRECCIONES = {
    "D-LIM-EVOL": "Revise las receptividades de las transiciones que se repiten: no deben ser ciertas a la vez.",
    "D-TRAZA-LIM": "Reinicie la simulación para vaciar el registro.",
    "D-SEM-PENDIENTE": "Este caso depende de un ajuste de simulación sin decidir. Elíjalo en Ajustes de simulación.",
    "D-EXP-PENDIENTE": "Completar la expresión con los bloques de la paleta.",
}


def amable(mensaje: str, codigo: str | None = None) -> str:
    """El mensaje del núcleo en lenguaje llano. Lo que no tiene regla pasa tal cual, sin referencias internas
    («lectura 6.1 A», «hoja 08, 2.2») ni el símbolo τ."""
    texto = LISTAS.sub(lambda m: m.group(1).replace("'", ""), mensaje.strip())
    for patron, plantilla in REGLAS:
        if patron.match(texto):
            return patron.sub(plantilla, texto, count=1)
    texto = REFERENCIAS_INTERNAS.sub("", texto)
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


def _repetidas(evoluciones: list[dict[str, Any]], nombres: dict[str, str]) -> tuple[list[str], list[str]]:
    """Las transiciones que se franquean en las últimas evoluciones y las etapas que cambian entre ellas."""
    ultimas = [e for e in evoluciones if e.get("evolutionIndex", 0) > 0][-RECIENTES:]
    transiciones = list(dict.fromkeys(nombres.get(t, t) for e in ultimas for t in e.get("cleared", [])))
    situaciones = [set(e.get("situation", [])) for e in ultimas]
    if not situaciones:
        return transiciones, []
    cambian = set().union(*situaciones) - set.intersection(*situaciones)
    return transiciones, sorted(nombres.get(s, s) for s in cambian)


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
             f". Revise "
             f"{'esa receptividad' if una else 'esas receptividades'}.")
    detalle = causa + (f" Cambian de estado las etapas {_lista(etapas)}." if etapas else "")
    detalle += f"\nDetalle técnico: {mensaje}"
    return [(principal, detalle), (causa, detalle)]
