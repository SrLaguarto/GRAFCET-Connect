"""Catálogo de diagnósticos (documento 08) y códigos propuestos por la implementación.

Cada diagnóstico conserva código, gravedad, elemento, evidencia y una corrección
recomendada (REQ-EDT-09, REQ-SIM-08). Los códigos marcados con origen distinto de
"08" están citados en otros documentos o son propuestas P-IMP-01 (hallazgo H-01).
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any

# Gravedades: "error" impide iniciar; "bloqueo" impide iniciar por capacidad no
# cerrada; "pausa" detiene una ejecución conservando el contexto; "advertencia"
# solo informa.
CATALOGO: dict[str, tuple[str, str, str]] = {
    # código: (gravedad, origen, corrección recomendada)
    "D-REF": ("error", "08", "Reparar la referencia o la identidad afectada"),
    "D-ID": ("error", "08", "Corregir la identidad duplicada o inválida"),
    "D-TIPO": ("error", "08", "Corregir el tipo de los operandos o del destino"),
    "D-UNIDAD": ("error", "08", "Usar operandos de la misma dimensión"),
    "D-NUM": ("error", "08", "Corregir el rango, la precisión o el divisor"),
    "D-EXP-PENDIENTE": ("bloqueo", "08", "Completar la expresión con significado ejecutable"),
    "D-SEM-PENDIENTE": ("bloqueo", "08", "Cerrar la cuestión indicada; no se aproxima el comportamiento"),
    "D-LOTE": ("error", "08", "Declarar simultaneidad o secuencia de forma explícita"),
    "D-ESCRITURA-CONFLICTO": ("error", "08", "Modificar condiciones o diseño para evitar valores contradictorios"),
    "D-MODO-SALIDA": ("error", "08", "Separar las determinaciones continua y memorizada"),
    "D-FORZADO-CONFLICTO": ("bloqueo", "08", "Resolver el conflicto jerárquico entre órdenes"),
    "D-FORZADO-RECINTO": ("error", "hoja 08, 7.4", "No forzar un recinto mientras su encapsulante está inactiva"),
    "D-JERARQUIA-RAMA": ("error", "hoja 08, 7.5", "Sincronizar las ramas de la expansión antes de su etapa de salida"),
    "D-JERARQUIA-CICLO": ("bloqueo", "08", "Eliminar el ciclo de la relación jerárquica"),
    "D-LIM-EVOL": ("pausa", "08", "Inspeccionar el ciclo o ampliar el presupuesto explícitamente"),
    "D-TRAZA-LIM": ("pausa", "08", "Exportar la traza o ampliar el límite"),
    "D-INSTANTANEA-INCOMPATIBLE": ("error", "08", "Abrir la revisión y el perfil de origen"),
    "D-INSTANTANEA-FASE": ("error", "08", "Alcanzar una frontera compatible antes de guardar"),
    "D-FORMATO": ("error", "08", "Corregir versión, campo o estructura del documento"),
    "D-INTEGRIDAD": ("error", "08", "Recuperar una copia íntegra; solo se lee el prefijo verificado"),
    # Citados fuera del catálogo de 08 (H-01)
    "D-EXP-DIVERGENTE": ("bloqueo", "09", "Elegir explícitamente texto o significado; se conservan ambos"),
    "D-ESCRITURA-ROL": ("error", "05", "No escribir entradas ni actividades derivadas"),
    "D-TIPO-EVENTO": ("error", "11", "Describir el evento con una acción memorizada"),
    "D-PROPIETARIO": ("error", "11", "Asignar un único propietario coherente"),
    "D-RUTA": ("error", "09", "Usar rutas relativas dentro de la raíz del proyecto"),
    "D-LIM-DATOS": ("error", "10", "Reducir tamaño o profundidad, o ampliar el perfil"),
    # Propuestos por la implementación (P-IMP-01), pendientes de ratificación
    "D-ALTERNANCIA": ("error", "P-IMP-01", "Insertar la transición o etapa intermedia"),
    "D-NOMBRE-COLISION": ("error", "P-IMP-01", "Usar un nombre único en el ámbito"),
    "D-JERARQUIA-INICIAL": ("error", "P-IMP-01", "Hacer coherentes las etapas iniciales con sus encapsulantes"),
    "D-ENTRADA-SIN-VALOR": ("error", "P-IMP-01", "Declarar el valor inicial de la entrada en el escenario"),
    "D-CAPACIDAD-NO-SOPORTADA": ("bloqueo", "P-IMP-01", "Capacidad no disponible en este perfil; ver hallazgo citado"),
    "D-DEPENDENCIA-CRUZADA": ("error", "hoja 08, 2.2", "Separar las asignaciones en evoluciones distintas o usar una variable auxiliar"),
}

GRAVEDADES_QUE_IMPIDEN_INICIO = {"error", "bloqueo"}


@dataclass
class Diagnostic:
    code: str
    message: str
    element: str | None = None
    field: str | None = None
    question: str | None = None  # U-xx o H-xx cuando el bloqueo depende de una cuestión
    evidence: dict[str, Any] = dc_field(default_factory=dict)
    severity: str | None = None  # permite rebajar a "advertencia" un código del catálogo

    def __post_init__(self) -> None:
        if self.code not in CATALOGO:
            raise ValueError(f"código de diagnóstico desconocido: {self.code}")
        if self.severity is None:
            self.severity = CATALOGO[self.code][0]

    @property
    def correction(self) -> str:
        return CATALOGO[self.code][2]

    @property
    def blocks_start(self) -> bool:
        return self.severity in GRAVEDADES_QUE_IMPIDEN_INICIO

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "severity": self.severity, "message": self.message,
                             "correction": self.correction}
        if self.element is not None:
            d["element"] = self.element
        if self.field is not None:
            d["field"] = self.field
        if self.question is not None:
            d["question"] = self.question
        if self.evidence:
            d["evidence"] = self.evidence
        return d

    def __str__(self) -> str:
        loc = f" [{self.element}]" if self.element else ""
        q = f" ({self.question})" if self.question else ""
        return f"{self.code}{q}{loc}: {self.message}"


class DiagnosticError(Exception):
    """Excepción que transporta uno o varios diagnósticos."""

    def __init__(self, *diags: Diagnostic) -> None:
        super().__init__("; ".join(str(d) for d in diags))
        self.diagnostics = list(diags)


def has_blocking(diags: list[Diagnostic]) -> bool:
    return any(d.blocks_start for d in diags)


def codes(diags: list[Diagnostic]) -> list[str]:
    return [d.code for d in diags]
