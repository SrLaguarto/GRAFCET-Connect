"""Perfil semántico y capacidades (documentos 08, 09, 12; REQ-NOR-01, REQ-NOR-02, REQ-ALC-03).

Estados de capacidad según 09: aprobada / provisional / no-soportada. En este perfil
ninguna capacidad está «aprobada»: todo lo I es provisional por U-01, y lo que depende
de una U abierta, o no se ha implementado todavía, está «no-soportada» con su motivo.
Un importador no cambia provisional a aprobada (09).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .diagnostics import Diagnostic

PROFILE_ID = "grafcet-impl-provisional"
PROFILE_VERSION = "0.1.0"
FORMAT_VERSION = "0.1"
APP_VERSION = "1.0.0"
NORMATIVE_BASE = {
    "standard": "IEC 60848",
    "edition": "3.0",
    "publication": "2013-02-27",
    "adoption": "UNE-EN 60848:2022",
}

U_REGISTRY = {
    "U-01": "Integridad, edición y correcciones de la fuente normativa",
    "U-02": "Terminología y referencias locales dudosas",
    "U-03": "Alcance causal de eventos (lectura por defecto «situación anterior» y acciones por evento decididas por el "
            "responsable, comparador 5.1–5.3; eventos internos y de franqueamiento siguen abiertos; contraste U-01)",
    "U-04": "Permanencia activa y eventos internos (permanencia decidida por el responsable, comparador 3.1–3.4; "
            "contraste U-01)",
    "U-05": "Lecturas y escrituras en un contexto causal (cerrada por el responsable, hoja 08 2.1–2.5; contraste U-01)",
    "U-06": "Fronteras temporales y rebotes (cerrada por el responsable, comparador 4.1–4.5, salvo 0s/p/d2 con d2 > 0; "
            "contraste U-01)",
    "U-07": "Construcciones fuente, vacías y persistentes (cerrada por el responsable, comparador 6.1–6.4; contraste U-01)",
    "U-08": "Interacciones jerárquicas (cerrada por el responsable, 7.1–7.8, salvo vaciar por forzado un recinto con su "
            "encapsulante activa; la ejecución básica sigue el documento 06, P-IMP-23; contraste U-01)",
    "U-09": "Inicialización semántica (cerrada por el responsable, hoja 08 1.1–1.5, salvo arranque vacío U-07 y expansiones U-08; contraste U-01)",
    "U-10": "Sistemas soportados y rendimiento",
    "U-11": "Ratificación de formato e intercambio",
    "U-12": "Aceptación del paquete y cobertura final",
}

# Cuestiones nuevas devueltas por la implementación (docs/01_Revision_de_coherencia.md)
FINDINGS = {
    "H-02": "Duración de etapa inicial desde τ=0 (confirmada por el responsable, hoja 08 1.4)",
    "H-05": "Activación de etapa ya activa no incluida en D: no ejecuta sus acciones (comparador 3.3 A)",
    "H-07": "Valor inicial distinto de cero: no se admite; se usa una acción al activar (hoja 08 1.5)",
    "H-08": "Parcial dentro de otro sin encapsulante: no se admite (8.1 C)",
    "H-09": "Base temporal compuesta (la salida y reentrada en el mismo instante quedó decidida en P-IMP-18)",
    "H-10": "Lectura de salidas continuas en expresiones: según la situación del momento (8.2 C)",
    "H-18": "Momento de aplicación del forzado: el destino evoluciona y el forzado se aplica después (7.2 B)",
    "H-23": "La lectura «recorrido» de U-03, aplicada literalmente, produce ciclos transitorios sin fin",
    "H-24": "Acciones al activar o desactivar de las etapas que cambia un forzado: se ejecutan (7.8 A)",
}


@dataclass(frozen=True)
class Capability:
    id: str
    description: str
    status: str  # aprobada | provisional | no-soportada
    reason: str  # clase I/P, U o H que lo motiva
    requirements: tuple[str, ...]


def _c(cid: str, desc: str, status: str, reason: str, *reqs: str) -> Capability:
    return Capability(cid, desc, status, reason, tuple(reqs))


CAPABILITIES: dict[str, Capability] = {c.id: c for c in [
    _c("evolucion.ordinaria", "Validación, receptividad, cambio conjunto, simultaneidad y relación S'=(S\\D)∪A",
       "provisional", "I (U-01)", "REQ-SEM-02", "REQ-SEM-03", "REQ-SEM-04"),
    _c("situacion.inicial.explicita", "Situación inicial = etapas marcadas iniciales", "provisional", "I (U-01)", "REQ-SEM-01"),
    _c("situacion.inicial.vacia", "Arranque sin etapas iniciales (no compila)", "no-soportada", "decisión del responsable, comparador 27-10-2026, 6.1 A",
       "REQ-SEM-01", "REQ-MOD-04"),
    _c("inicio.inestable", "Transición franqueable en la situación inicial: evoluciona en τ=0", "provisional",
       "decisión del responsable, hoja 08 1.2 A", "REQ-SEM-01"),
    _c("inicio.acciones-activacion", "Acciones al activar de las etapas iniciales: se ejecutan al arrancar",
       "provisional", "decisión del responsable, hoja 08 1.1 A", "REQ-ACT-02"),
    _c("inicio.memoria-no-nula", "Variable memorizada con valor inicial distinto de cero (no compila)",
       "no-soportada", "decisión del responsable, hoja 08 1.5 A: se usa una acción al activar", "REQ-ACT-02"),
    _c("inicio.temporal-entrada-verdadera", "Condición temporal sobre entrada verdadera al iniciar: cuenta desde τ=0",
       "provisional", "decisión del responsable, hoja 08 1.3 A", "REQ-TMP-02"),
    _c("permanencia.actividad", "Etapa activada y desactivada a la vez permanece activa", "provisional", "I (U-01)", "REQ-SEM-05"),
    _c("permanencia.efectos", "Etapa en permanencia activa o reactivada: no ejecuta acciones al activar ni al desactivar "
       "y su duración sigue", "provisional", "decisión del responsable, comparador 27-10-2026, 3.1 A, 3.2 A y 3.3 A (cierra H-05)", "REQ-SEM-05", "REQ-EVT-03"),
    _c("transitorios", "Situaciones virtuales sin pulsos continuos; memorizadas conservadas", "provisional", "I (U-01)", "REQ-SEM-06"),
    _c("transiciones.sumidero", "Transición sin siguientes", "provisional", "I (U-01)", "REQ-MOD-04"),
    _c("transiciones.fuente-evento", "Transición fuente con receptividad de evento (primera evolución)", "provisional", "I (U-01)", "REQ-MOD-04"),
    _c("transiciones.fuente-nivel", "Transición fuente con receptividad de nivel (no compila)", "no-soportada", "decisión del responsable, comparador 27-10-2026, 6.2 A",
       "REQ-MOD-04"),
    _c("transiciones.fuente-repeticion", "Transición fuente por evento: franquea una sola vez por flanco",
       "provisional", "decisión del responsable, comparador 27-10-2026, 6.3 A", "REQ-MOD-04", "REQ-EVT-03"),
    _c("transiciones.sin-lados", "Transición sin precedentes ni siguientes (no compila)", "no-soportada", "decisión del responsable, comparador 27-10-2026, 6.4 A",
       "REQ-MOD-04"),
    _c("eventos.entradas", "Flancos sobre proposiciones de entradas en la primera evolución del contexto", "provisional", "I (U-01)", "REQ-EVT-01"),
    _c("eventos.recorrido", "Un evento solo franquea las transiciones validadas antes de él; una acción por evento solo "
       "se ejecuta si su etapa estaba activa antes y no sale con él", "provisional",
       "decisión del responsable, comparador 27-10-2026, 5.1 «situación anterior» (seleccionable, P-IMP-15), 5.2 B y 5.3 A", "REQ-EVT-03", "REQ-SEM-09"),
    _c("eventos.internos", "Flancos sobre actividad, variables internas o condiciones temporales", "no-soportada", "U-03", "REQ-EVT-03"),
    _c("eventos.franqueamiento", "Eventos de franqueamiento como disparadores", "no-soportada", "U-03", "REQ-EVT-03"),
    _c("lotes", "Lotes simultáneos y lotes ordenados con igual tiempo", "provisional", "P", "REQ-EVT-02"),
    _c("temporal.delay", "delay(d1,p,d2) ordinario con d1>0", "provisional", "I (U-01)", "REQ-TMP-02"),
    _c("temporal.delay-cero", "Tiempos de 0 s en un retardo: se quitan al compilar (0s/p es p; 0s/p/7s es p/7s; 8s/p/0s es "
       "8s/p)", "provisional", "decisión del responsable, chat 27-10-2026, 4.4 revisada (A)", "REQ-TMP-03"),
    _c("temporal.coincidencias", "Lote y vencimiento en el mismo instante: primero el vencimiento si el lote cambia su base, "
       "si no juntos; un rebote durante la desconexión la mantiene verdadera", "provisional",
       "decisión del responsable, comparador 27-10-2026, 4.1 A, 4.2 A y 4.3 A (cierra H-17)", "REQ-TMP-03"),
    _c("temporal.vencimientos-simultaneos", "Varios vencimientos en el mismo instante (independientes del orden)", "provisional", "I (U-01)", "REQ-TMP-02"),
    _c("temporal.duracion-etapa-inicial", "La duración de una etapa inicial cuenta desde τ=0 (oráculos T-12a/T-12c)", "provisional", "I; decisión del responsable, hoja 08 1.4 A", "REQ-TMP-02"),
    _c("temporal.reentrada-virtual", "Salida y reentrada en el mismo instante: la duración de la etapa no se interrumpe",
       "provisional", "decisión del responsable de producto, 25-10-2026 (P-IMP-18; cierra H-09)", "REQ-TMP-02"),
    _c("temporal.base-compuesta", "Base temporal distinta de entradas o active(etapa)", "no-soportada", "H-09", "REQ-TMP-02"),
    _c("temporal.elapsed", "Duración elapsed(etapa) ejecutable", "no-soportada",
       "no implementada en esta iteración; el valor con la etapa inactiva ya está decidido: 0 (decisión del responsable, comparador 27-10-2026, 4.5 A)", "REQ-TMP-02"),
    _c("acciones.continuas", "Disyunción de contribuciones continuas sobre situación efectiva", "provisional", "I (U-01)", "REQ-ACT-01"),
    _c("acciones.limitadas", "Acción continua limitada [t0, t0+d)", "provisional", "I (U-01)", "REQ-TMP-02"),
    _c("acciones.memorizadas", "Acciones memorizadas al activar, desactivar o por evento", "provisional", "I (U-01)", "REQ-ACT-02"),
    _c("acciones.activacion-condicionada", "Acción al activar/desactivar con condición adicional", "no-soportada",
       "no implementada en esta iteración", "REQ-ACT-02"),
    _c("acciones.conflicto", "Conflicto de escritura y dependencia cruzada: no compila si es seguro; si no, se detiene",
       "provisional", "P-IMP-16; decisión del responsable, hoja 08 2.1 C y 2.2 B", "REQ-ACT-03"),
    _c("acciones.lecturas-contexto", "Lo asignado en un instante se ve en ese mismo instante; vale la última asignación",
       "provisional", "decisión del responsable, hoja 08 2.3 A y 2.4 A", "REQ-ACT-05"),
    _c("acciones.salidas-continuas-leidas", "Leer salidas continuas en expresiones: valor según la situación del momento, "
       "también la inestable", "provisional", "decisión del responsable, comparador 27-10-2026, 8.2 C (cierra H-10)", "REQ-ACT-01"),
    _c("parciales.actividad", "activePartial sobre parcial sin hijos", "provisional", "I (U-01)", "REQ-JER-01"),
    _c("parciales.anidados", "Parcial dentro de otro: solo como recinto de una encapsulante o expansión de una macroetapa "
       "del parcial dueño; sin encapsulante no compila", "provisional", "decisión del responsable, chat 27-10-2026, 8.1 C (cierra H-08)", "REQ-JER-01", "REQ-MOD-07"),
    _c("jerarquia.estructura", "Edición, persistencia y validación de forzados, macroetapas y recintos", "provisional", "I/P", "REQ-MOD-07", "REQ-JER-03"),
    _c("jerarquia.forzado", "Forzado: explícito, actual, vacío e inicial; el destino no evoluciona mientras está vigente",
       "provisional", "I (U-01), documento 06 y LOC tabla 9; P-IMP-23", "REQ-JER-02", "REQ-JER-03"),
    _c("jerarquia.macroetapas", "Macroetapas: llegar activa la entrada; salir exige la salida; XM por la expansión",
       "provisional", "I (U-01), documento 06 y LOC tabla 11; P-IMP-23", "REQ-JER-04"),
    _c("jerarquia.forzado-momento", "Orden que entra en vigor cuando su destino franquea: el destino evoluciona y el "
       "forzado se aplica en la evolución siguiente", "provisional", "decisión del responsable, chat 27-10-2026, 7.2 B (coherente con 4.3 A y 7.6 B; cierra H-18)",
       "REQ-JER-06"),
    _c("jerarquia.forzado-tiempo", "Temporizadores de un parcial forzado: siguen contando", "provisional", "decisión del responsable, comparador 27-10-2026, 7.3 A",
       "REQ-JER-06"),
    _c("jerarquia.forzado-recinto", "Forzar un recinto con la encapsulante inactiva: el forzado se ignora mientras siga "
       "inactiva. Vaciar por forzado un recinto con la encapsulante activa no se preguntó y se detiene (U-08)", "provisional",
       "decisión del responsable, comparador 27-10-2026, 7.4 C", "REQ-JER-06"),
    _c("jerarquia.forzado-acciones", "Acciones al activar o desactivar de las etapas que cambia un forzado: se ejecutan",
       "provisional", "decisión del responsable, comparador 27-10-2026, 7.8 A (cierra H-24)", "REQ-JER-06", "REQ-ACT-02"),
    _c("jerarquia.macro-ramas", "Salir de una macroetapa con otras ramas activas: se desactivan todas las etapas de la "
       "expansión", "provisional", "decisión del responsable, comparador 27-10-2026, 7.5 A", "REQ-JER-06"),
    _c("jerarquia.macro-inicial", "Etapas iniciales dentro de una expansión: se admiten y están activas al arrancar",
       "provisional", "decisión del responsable, chat 27-10-2026, 7.7 A", "REQ-JER-04"),
    _c("jerarquia.encapsulacion-coincidencia", "Transición interior que franquea cuando se desactiva su encapsulante: "
       "primero actúa y después se desactiva", "provisional", "decisión del responsable, chat 27-10-2026, 7.6 B (coherente con 4.1 A y 4.3 A)", "REQ-JER-06"),
    _c("jerarquia.encapsulacion", "Encapsulación: al entrar, etapas con enlace de activación (al arrancar, las "
       "iniciales); al salir, se desactiva todo el contenido", "provisional",
       "I (U-01), documento 06 y LOC §7.4; P-IMP-23", "REQ-JER-05"),
    _c("jerarquia.encapsulacion-permanencia", "Encapsulante en permanencia activa: su contenido se mantiene",
       "provisional", "decisión del responsable, comparador 27-10-2026, 3.4 A", "REQ-JER-05", "REQ-SEM-05"),
    _c("escenario.predicado-parada", "Condición de parada por predicado observador", "no-soportada",
       "P: no implementada en esta iteración", "REQ-SIM-02"),
    _c("instantanea.recorrido","Instantánea exacta en mitad de un recorrido", "no-soportada", "P: D-INSTANTANEA-FASE", "REQ-SIM-04"),
]}


# Lecturas seleccionables de las cuestiones de la hoja 08 (P-IMP-15 y P-IMP-21). Cada alternativa está
# implementada para poder compararla en el comparador de decisiones. Los valores por defecto son lo que decidió
# el responsable (hoja 08, bloques 1 y 2, P-IMP-19 y P-IMP-20; comparador y chat, P-IMP-22 a P-IMP-27) y, para
# lo que siguiera abierto, «detener», porque el documento 12 prohíbe cerrar una U con un valor por defecto de
# implementación. Elegir otra lectura es una hipótesis explícita: queda en el perfil efectivo de la traza y de
# las instantáneas, y nunca es conformidad.
_STOP = "Detener: la cuestión sigue abierta"


def _opt(default: str, scope: str, values: dict[str, str]) -> dict[str, Any]:
    return {"default": default, "scope": scope, "values": values}


SEMANTIC_OPTIONS: dict[str, dict[str, Any]] = {
    "U-03": _opt("situacion-anterior", "U-03: receptividades con eventos de entrada en evoluciones posteriores del instante", {
        "detener": "Detener con D-SEM-PENDIENTE: no se elige",
        "situacion-anterior": "De uno en uno («situación anterior»): el flanco solo franquea las transiciones validadas "
                              "antes de él",
        "recorrido": "Por ciclo («recorrido»): el flanco vale en todo el recorrido del instante y puede atravesar "
                     "varias etapas inestables seguidas"}),
    "1.1": _opt("A", "U-09: acciones «al activar» de las etapas iniciales", {
        "A": "Se ejecutan al arrancar", "B": "No se ejecutan: la situación inicial no es una activación"}),
    "1.2": _opt("A", "U-09: situación inicial inestable", {
        "A": "Evoluciona en τ=0", "B": "Espera al primer cambio de entradas", "C": "No compila"}),
    "1.3": _opt("A", "U-09: temporizador sobre una entrada ya verdadera al arrancar", {
        "A": "Cuenta desde τ=0", "B": "Espera una subida real de la entrada"}),
    "1.5": _opt("A", "U-09: variable memorizada con valor inicial distinto de 0", {
        "A": "No compila (se usa una acción al activar)", "B": "Empieza con el valor declarado"}),
    "2.1": _opt("C", "U-05: varias asignaciones simultáneas a la misma variable", {
        "A": "Todas leen el valor anterior; si coinciden, una sola escritura",
        "B": "Se acumulan, una detrás de otra (orden de identificador)", "C": "Conflicto"}),
    "2.2": _opt("B", "U-05: dependencia cruzada entre asignaciones simultáneas", {
        "A": "Todas leen el estado anterior (intercambio)", "B": "Error: no compila o se detiene"}),
    "2.3": _opt("A", "U-05: receptividad que lee un valor asignado en el mismo instante", {
        "A": "Ve el valor nuevo", "B": "Ve el valor de antes del instante"}),
    "2.4": _opt("A", "U-05: asignaciones distintas sucesivas en el mismo instante", {
        "A": "Vale la última", "B": "Conflicto"}),
    "2.5": _opt("A", "U-05: salida continua que lee una memoria cambiada en el instante", {
        "A": "Usa el valor final del instante", "B": "Usa el valor de antes del instante"}),
    "3.1": _opt("A", "U-04: acciones al activar/desactivar de una etapa en permanencia activa", {
        "detener": _STOP, "A": "No se ejecuta ninguna", "B": "Se ejecutan las dos"}),
    "3.2": _opt("A", "U-04: temporizador de una etapa en permanencia activa o reactivada", {
        "detener": _STOP, "A": "Sigue contando", "B": "Vuelve a empezar"}),
    "3.3": _opt("A", "U-04 (H-05): acciones al activar una etapa que ya estaba activa", {
        "detener": _STOP, "A": "No se ejecutan", "B": "Se ejecutan"}),
    "4.1": _opt("A", "U-06: la base de un retardo cambia exactamente en su vencimiento", {
        "detener": _STOP, "A": "Primero vence el retardo", "B": "Primero cambia la entrada (cancela)"}),
    "4.2": _opt("A", "U-06: rebote durante el retardo de desconexión", {
        "detener": _STOP, "A": "La condición sigue verdadera sin interrupción",
        "B": "Se mantiene el plazo; después vuelve a contar el retardo de conexión"}),
    "4.3": _opt("A", "U-06: lote y vencimiento independientes en el mismo instante", {
        "detener": _STOP, "A": "Juntos en un solo instante", "B": "Primero el vencimiento", "C": "Primero el lote",
        "D": "Solo se detiene si el resultado depende del orden"}),
    "4.4": _opt("A", "U-06: retardo cero", {
        "detener": _STOP, "A": "El 0 s se quita: 0s/p es p y 0s/p/7s es p/7s", "B": "0s/p no compila"}),
    "5.2": _opt("B", "U-03: acción por evento en una etapa que se desactiva con ese mismo evento", {
        "detener": _STOP, "A": "Se ejecuta", "B": "No se ejecuta"}),
    "5.3": _opt("A", "U-03: acción por evento en una etapa que se activa con ese mismo evento", {
        "detener": _STOP, "A": "No se ejecuta", "B": "Se ejecuta"}),
    "6.1": _opt("A", "U-07: grafcet sin etapas iniciales", {
        "detener": _STOP, "A": "No compila", "B": "Arranca sin etapas activas"}),
    "6.2": _opt("A", "U-07: transición fuente con receptividad de nivel", {
        "detener": _STOP, "A": "No compila",
        "B": "Imposición continua: mientras sea verdadera, mantiene activas sus etapas siguientes"}),
    "6.3": _opt("A", "U-07: transición fuente con flanco en evoluciones posteriores del instante", {
        "detener": _STOP, "A": "Franquea una sola vez por flanco"}),
    "6.4": _opt("A", "U-07: transición sin etapas antes ni después", {
        "detener": _STOP, "A": "No compila", "B": "Se permite y no tiene efecto"}),
    "3.4": _opt("A", "U-04/U-08: encapsulante activada y desactivada a la vez", {
        "detener": _STOP, "A": "Su contenido se mantiene", "B": "Su contenido se reinicia con las etapas de activación"}),
    "7.2": _opt("B", "U-08 (H-18): orden que entra en vigor cuando su destino podría evolucionar", {
        "detener": _STOP, "A": "El forzado se aplica en esa misma evolución y gana",
        "B": "El destino evoluciona y el forzado se aplica en la evolución siguiente"}),
    "7.3": _opt("A", "U-08: temporizadores de un parcial forzado", {
        "detener": _STOP, "A": "Siguen contando", "B": "Se congelan mientras dura el forzado"}),
    "7.4": _opt("C", "U-08: forzar un recinto cuya encapsulante está inactiva", {
        "detener": _STOP, "A": "Error de diseño: se detiene con error", "B": "Se fuerza igualmente",
        "C": "El forzado se ignora mientras la encapsulante esté inactiva"}),
    "7.5": _opt("A", "U-08: salir de una macroetapa con ramas internas aún activas", {
        "detener": _STOP, "A": "Se desactivan todas las etapas de la expansión", "B": "Las ramas siguen activas",
        "C": "Error de diseño: se detiene con error"}),
    "7.6": _opt("B", "U-08: desactivar la encapsulante cuando franquea algo en su interior", {
        "detener": _STOP, "A": "Gana la desactivación: lo interior no tiene efecto",
        "B": "Primero actúa lo interior y después se desactiva"}),
    "7.7": _opt("A", "U-08: etapas iniciales dentro de una expansión", {
        "detener": _STOP, "A": "Se permiten: están activas al arrancar", "B": "No se permiten: no compila"}),
    "7.8": _opt("A", "U-08 (H-24): acciones de etapas activadas o desactivadas por un forzado", {
        "detener": _STOP, "A": "Se ejecutan", "B": "No se ejecutan"}),
    "8.1": _opt("C", "H-08: parcial dentro de otro (ownerRef del documento 09)", {
        "detener": _STOP, "A": "Cuenta también las etapas de los hijos", "B": "Solo las etapas propias",
        "C": "Sin encapsulante no se admite: no compila"}),
    "8.2": _opt("C", "H-10: leer una salida continua en una expresión", {
        "detener": _STOP, "A": "Prohibido: no compila", "B": "Valor de la situación estable anterior",
        "C": "Valor según la situación inestable del momento"}),
}


def normalize_options(options: dict[str, str] | None) -> dict[str, str]:
    out = {q: spec["default"] for q, spec in SEMANTIC_OPTIONS.items()}
    for q, value in (options or {}).items():
        if q not in SEMANTIC_OPTIONS or value not in SEMANTIC_OPTIONS[q]["values"]:
            raise ValueError(f"lectura no admitida: {q}={value!r}")
        out[q] = value
    return out


def profile_ref(options: dict[str, str]) -> dict[str, Any]:
    """Perfil efectivo de una ejecución: identidad del perfil más las lecturas elegidas."""
    return {"id": PROFILE_ID, "version": PROFILE_VERSION, "options": dict(sorted(options.items()))}


def sem_pending(question: str, message: str, element: str | None = None, **evidence: Any) -> Diagnostic:
    """Bloqueo por cuestión abierta: nunca se sustituye por un comportamiento por defecto."""
    return Diagnostic("D-SEM-PENDIENTE", message, element=element, question=question,
                      evidence={k: str(v) for k, v in evidence.items()})


def unsupported(capability: str, message: str, element: str | None = None) -> Diagnostic:
    cap = CAPABILITIES[capability]
    return Diagnostic("D-CAPACIDAD-NO-SOPORTADA", f"{message} [{capability}: {cap.reason}]", element=element,
                      question=cap.reason, evidence={"capacidad": capability})


# Cuestión de origen de las capacidades que el responsable ya decidió. Si se elige la lectura «detener», el
# caso vuelve a tratarse como abierto y se diagnostica con su U, no con la decisión.
CAP_QUESTION = {
    "situacion.inicial.vacia": "U-07", "transiciones.fuente-nivel": "U-07", "transiciones.fuente-repeticion": "U-07",
    "transiciones.sin-lados": "U-07", "permanencia.efectos": "U-04", "eventos.recorrido": "U-03",
    "temporal.delay-cero": "U-06", "temporal.coincidencias": "U-06", "jerarquia.encapsulacion-permanencia": "U-04",
    "jerarquia.macro-inicial": "U-08", "jerarquia.forzado-momento": "U-08", "jerarquia.encapsulacion-coincidencia": "U-08",
    "jerarquia.forzado-tiempo": "U-08", "jerarquia.forzado-recinto": "U-08", "jerarquia.forzado-acciones": "U-08",
    "jerarquia.macro-ramas": "U-08",
}


def blocked(capability: str, message: str, element: str | None = None) -> Diagnostic:
    """Diagnóstico de capacidad bloqueada: D-SEM-PENDIENTE si la motiva una U, D-CAPACIDAD-NO-SOPORTADA si no."""
    cap = CAPABILITIES[capability]
    if cap.reason.startswith("U-"):
        return sem_pending(cap.reason.split(" ")[0], f"{message} [{capability}]", element, capacidad=capability)
    if capability in CAP_QUESTION:
        return sem_pending(CAP_QUESTION[capability], f"{message} [{capability}]", element, capacidad=capability)
    return unsupported(capability, message, element)


def descriptor() -> dict[str, Any]:
    return {"id": PROFILE_ID, "version": PROFILE_VERSION,
            "capabilities": [{"id": c.id, "status": c.status, "reason": c.reason}
                             for c in sorted(CAPABILITIES.values(), key=lambda c: c.id)],
            "openQuestions": sorted(U_REGISTRY), "findings": sorted(FINDINGS)}
