"""Constantes de la ventana de escritorio (textos, medidas y tablas de estado)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from grafcet.diagnostics import DiagnosticError

TITULO = "GRAFCET Connect"
URL_CODIGO = "https://github.com/SrLaguarto/GRAFCET-Connect"  # dónde está el código (diálogo «Acerca de»)
URL_FALLOS = "https://github.com/SrLaguarto/GRAFCET-Connect/issues"  # dónde se comunica un fallo o una sugerencia
ICONO_PROGRAMA = Path(__file__).resolve().parents[1] / "recursos" / "grafcet_connect.ico"
HUECO_FRANJA = 0  # la franja de modo va arriba de la ventana, no dentro del recuadro del dibujo
ANCHO_DERECHO = 270  # el panel derecho desde UMBRAL_DERECHO px de ancho de ventana (P10: «Papel» y «Tipo» enteros, tablas de estado con sus cuatro columnas)
UMBRAL_DERECHO = 1280
ANCHO_DERECHO_BASE = 218  # las columnas de Variables mantienen su ancho mínimo
NOMBRE_MIN_TABLA = 96  # la columna del nombre de las tablas (estado de la simulación) mide al menos esto a cualquier tamaño: las demás se compactan antes
ARRIBA_CAJA = 1  # margen superior del contenido de una sección: con el hueco del título deja E2 entre el título y lo primero (T3)
ARRIBA_VARIABLES = 4  # (el título de Variables es más grande)
ALTO_TRAZA = 220  # altura inicial del panel de traza
ESPERA_ESCALA = 120  # ms sin cambios de tamaño de la ventana antes de aplicar la escala nueva (una sola vez por ráfaga de `resizeEvent`)
ESPERA_ARRANQUE = 600  # ms desde el primer `show` en los que la escala se aplica sin esperar (la ventana se maximiza al arrancar)
TICK_MS = 100  # tiempo real: cada cuánto se avanza el tiempo lógico
AYUDA_EDICION = {
    "seleccionar": "Clic selecciona un elemento (doble clic o Intro abre sus propiedades); arrastrarlo lo mueve (a la "
                   "rejilla, y no encima de otro elemento); de un punto de unión (arriba o abajo de una etapa o transición, "
                   "a la derecha de una etapa) sale un enlace. Supr borra; Ctrl+Z y Ctrl+Y deshacen y rehacen. Los "
                   "elementos y las acciones nuevos se arrastran desde la paleta de la izquierda; otro tipo de acción, con botón derecho "
                   "sobre ella. Para quitar un bloque, arrástrelo fuera o pulse Supr.",
}
NOMBRE_HERRAMIENTA = {"seleccionar": "Seleccionar"}
AVISO = "Conforme a IEC 60848"
TEXTOS_FIRMA = {
    "sin_firma": ("Archivo sin firma",
                  "Este archivo no se guardó con esta versión de GRAFCET Connect o se modificó fuera del programa. "
                  "Se puede usar con normalidad; al guardarlo seguirá sin firma."),
    "desarrollo": ("Archivo de la versión de desarrollo (sin firma de esta versión)",
                   "Este archivo está firmado con la clave de la versión de desarrollo, no con la de esta versión. "
                   "Se puede usar con normalidad; al guardarlo seguirá sin firma de esta versión."),
}
ESTADOS = {"pausada-estable": ("estable", "ok"), "pausada-recorrido": ("en recorrido (situación inestable)", "virt"),
           "error": ("detenido por diagnóstico", "err"), "no-compilable": ("no compilable", "err"),
           "finalizada": ("finalizada", "ok"), "preparada": ("preparada", "muted"), "ejecutando": ("ejecutando", "muted")}
TRAZA = {"fallo": "err", "evolucion": "accent", "contexto": "muted"}
ERRORES = (DiagnosticError, RuntimeError, ValueError, KeyError)


def _q_key(q: str) -> list[Any]:
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"[.-]", q)]  # números antes que letras
