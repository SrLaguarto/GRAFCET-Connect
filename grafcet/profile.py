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
APP_VERSION = "0.1.0-dev"
NORMATIVE_BASE = {
    "standard": "IEC 60848",
    "edition": "3.0",
    "publication": "2013-02-27",
    "adoption": "UNE-EN 60848:2022",
}

U_REGISTRY = {
    "U-01": "Integridad, edición y correcciones de la fuente normativa",
    "U-02": "Terminología y referencias locales dudosas",
    "U-03": "Alcance causal de eventos",
    "U-04": "Permanencia activa y eventos internos",
    "U-05": "Lecturas y escrituras en un contexto causal",
    "U-06": "Fronteras temporales y rebotes",
    "U-07": "Construcciones fuente, vacías y persistentes",
    "U-08": "Interacciones jerárquicas",
    "U-09": "Inicialización semántica",
    "U-10": "Sistemas soportados y rendimiento",
    "U-11": "Ratificación de formato e intercambio",
    "U-12": "Aceptación del paquete y cobertura final",
}

# Cuestiones nuevas devueltas por la implementación (docs/01_Revision_de_coherencia.md)
FINDINGS = {
    "H-02": "Duración de etapa inicial frente a U-09",
    "H-05": "Activación de etapa ya activa no incluida en D (ampliación de U-04)",
    "H-07": "Valor inicial distinto de cero en variable memorizada (U-09)",
    "H-08": "Actividad de parcial con parciales anidados",
    "H-09": "Base temporal con salida y reentrada virtual o base compuesta",
    "H-10": "Lectura de salidas continuas en expresiones",
    "H-18": "Momento de aplicación del forzado en el recorrido (ampliación de U-08)",
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
    _c("situacion.inicial.vacia", "Arranque sin etapas iniciales", "no-soportada", "U-07", "REQ-SEM-01", "REQ-MOD-04"),
    _c("inicio.inestable", "Transición franqueable en la situación inicial", "no-soportada", "U-09", "REQ-SEM-01"),
    _c("inicio.acciones-activacion", "Acciones memorizadas al activar etapas iniciales", "no-soportada", "U-09", "REQ-ACT-02"),
    _c("inicio.memoria-no-nula", "Variable memorizada con valor inicial distinto de cero", "no-soportada", "U-09 (H-07)", "REQ-ACT-02"),
    _c("inicio.temporal-entrada-verdadera", "Condición temporal sobre entrada verdadera al iniciar", "no-soportada", "U-09", "REQ-TMP-02"),
    _c("permanencia.actividad", "Etapa activada y desactivada a la vez permanece activa", "provisional", "I (U-01)", "REQ-SEM-05"),
    _c("permanencia.efectos", "Acciones, eventos y tiempo de una etapa en permanencia activa o reactivada", "no-soportada", "U-04 (H-05)", "REQ-SEM-05", "REQ-EVT-03"),
    _c("transitorios", "Situaciones virtuales sin pulsos continuos; memorizadas conservadas", "provisional", "I (U-01)", "REQ-SEM-06"),
    _c("transiciones.sumidero", "Transición sin siguientes", "provisional", "I (U-01)", "REQ-MOD-04"),
    _c("transiciones.fuente-evento", "Transición fuente con receptividad de evento (primera evolución)", "provisional", "I (U-01); repetición U-07", "REQ-MOD-04"),
    _c("transiciones.fuente-nivel", "Transición fuente con receptividad de nivel", "no-soportada", "U-07", "REQ-MOD-04"),
    _c("transiciones.fuente-repeticion", "Transición fuente por evento en evoluciones posteriores del mismo contexto",
       "no-soportada", "U-07 (con U-03)", "REQ-MOD-04", "REQ-EVT-03"),
    _c("transiciones.sin-lados","Transición sin precedentes ni siguientes", "no-soportada", "U-07", "REQ-MOD-04"),
    _c("eventos.entradas", "Flancos sobre proposiciones de entradas en la primera evolución del contexto", "provisional", "I (U-01)", "REQ-EVT-01"),
    _c("eventos.recorrido", "Uso de un evento por transiciones validadas durante su propio recorrido", "no-soportada", "U-03", "REQ-EVT-03", "REQ-SEM-09"),
    _c("eventos.internos", "Flancos sobre actividad, variables internas o condiciones temporales", "no-soportada", "U-03", "REQ-EVT-03"),
    _c("eventos.franqueamiento", "Eventos de franqueamiento como disparadores", "no-soportada", "U-03", "REQ-EVT-03"),
    _c("lotes", "Lotes simultáneos y lotes ordenados con igual tiempo", "provisional", "P", "REQ-EVT-02"),
    _c("temporal.delay", "delay(d1,p,d2) ordinario con d1>0", "provisional", "I (U-01)", "REQ-TMP-02"),
    _c("temporal.delay-cero", "delay con d1=0", "no-soportada", "U-06", "REQ-TMP-03"),
    _c("temporal.coincidencias", "Vencimiento coincidente con lote, caída en el vencimiento, rebote", "no-soportada", "U-06", "REQ-TMP-03"),
    _c("temporal.vencimientos-simultaneos", "Varios vencimientos en el mismo instante (independientes del orden)", "provisional", "I (U-01)", "REQ-TMP-02"),
    _c("temporal.duracion-etapa-inicial", "La duración de una etapa inicial cuenta desde τ=0 (oráculos T-12a/T-12c)", "provisional", "I; tensión H-02", "REQ-TMP-02"),
    _c("temporal.reentrada-virtual", "Salida y reentrada virtual de etapa con dependencias temporales", "no-soportada", "H-09", "REQ-TMP-02"),
    _c("temporal.base-compuesta", "Base temporal distinta de entradas o active(etapa)", "no-soportada", "H-09", "REQ-TMP-02"),
    _c("temporal.elapsed", "Duración elapsed(etapa) ejecutable", "no-soportada", "U-06 (valor inactivo); no implementada", "REQ-TMP-02"),
    _c("acciones.continuas", "Disyunción de contribuciones continuas sobre situación efectiva", "provisional", "I (U-01)", "REQ-ACT-01"),
    _c("acciones.limitadas", "Acción continua limitada [t0, t0+d)", "provisional", "I (U-01)", "REQ-TMP-02"),
    _c("acciones.memorizadas", "Acciones memorizadas al activar, desactivar o por evento", "provisional", "I (U-01)", "REQ-ACT-02"),
    _c("acciones.activacion-condicionada", "Acción al activar/desactivar con condición adicional", "no-soportada",
       "no implementada; lectura en contexto U-05", "REQ-ACT-02"),
    _c("acciones.conflicto","Conflicto de escritura detenido con evidencia", "provisional", "P", "REQ-ACT-03"),
    _c("acciones.lecturas-contexto", "Lecturas de valores asignados en el mismo contexto causal", "no-soportada", "U-05", "REQ-ACT-05"),
    _c("acciones.salidas-continuas-leidas", "Leer salidas continuas en expresiones", "no-soportada", "H-10", "REQ-ACT-01"),
    _c("parciales.actividad", "activePartial sobre parcial sin hijos", "provisional", "I (U-01)", "REQ-JER-01"),
    _c("parciales.anidados", "activePartial sobre parcial con parciales hijos", "no-soportada", "H-08", "REQ-JER-01"),
    _c("jerarquia.estructura", "Edición, persistencia y validación de forzados, macroetapas y recintos", "provisional", "I/P", "REQ-MOD-07", "REQ-JER-03"),
    _c("jerarquia.forzado", "Ejecución de órdenes de forzado", "no-soportada", "no implementada en esta iteración; U-08 (H-18)", "REQ-JER-02"),
    _c("jerarquia.macroetapas", "Ejecución de macroetapas", "no-soportada", "no implementada en esta iteración; U-08", "REQ-JER-04"),
    _c("jerarquia.encapsulacion", "Ejecución de encapsulación", "no-soportada", "no implementada en esta iteración; U-08", "REQ-JER-05"),
    _c("escenario.predicado-parada", "Condición de parada por predicado observador", "no-soportada",
       "P: no implementada en esta iteración", "REQ-SIM-02"),
    _c("instantanea.recorrido","Instantánea exacta en mitad de un recorrido", "no-soportada", "P: D-INSTANTANEA-FASE", "REQ-SIM-04"),
]}


def sem_pending(question: str, message: str, element: str | None = None, **evidence: Any) -> Diagnostic:
    """Bloqueo por cuestión abierta: nunca se sustituye por un comportamiento por defecto."""
    return Diagnostic("D-SEM-PENDIENTE", message, element=element, question=question,
                      evidence={k: str(v) for k, v in evidence.items()})


def unsupported(capability: str, message: str, element: str | None = None) -> Diagnostic:
    cap = CAPABILITIES[capability]
    return Diagnostic("D-CAPACIDAD-NO-SOPORTADA", f"{message} [{capability}: {cap.reason}]", element=element,
                      question=cap.reason, evidence={"capacidad": capability})


def blocked(capability: str, message: str, element: str | None = None) -> Diagnostic:
    """Diagnóstico de capacidad bloqueada: D-SEM-PENDIENTE si la motiva una U, D-CAPACIDAD-NO-SOPORTADA si no."""
    cap = CAPABILITIES[capability]
    if cap.reason.startswith("U-"):
        return sem_pending(cap.reason.split(" ")[0], f"{message} [{capability}]", element, capacidad=capability)
    return unsupported(capability, message, element)


def descriptor() -> dict[str, Any]:
    return {"id": PROFILE_ID, "version": PROFILE_VERSION,
            "capabilities": [{"id": c.id, "status": c.status, "reason": c.reason}
                             for c in sorted(CAPABILITIES.values(), key=lambda c: c.id)],
            "openQuestions": sorted(U_REGISTRY), "findings": sorted(FINDINGS)}
