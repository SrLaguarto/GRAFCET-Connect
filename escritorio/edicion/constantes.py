"""Mensajes y constantes compartidos por la edición."""
from __future__ import annotations

import re
from grafcet.expressions import FUNCS_EXPR, FUNCS_REF, KEYWORDS
from ..geometria.base import PASO
from ..diagrama import FICHAS_ACCION, H


HERRAMIENTAS = ("seleccionar",)  # el ratón selecciona, mueve y enlaza; los elementos nuevos solo se colocan arrastrándolos
MAX_ETIQUETA_ETAPA = 4  # lo más largo que se escribe en la etiqueta de una etapa: más no cabe en su cuadro (lo ya guardado con más se abre igual)
DY = PASO  # distancia vertical estándar: tres pasos de rejilla entre etapa y transición
RADIO_UNION = 8  # a qué distancia (px al 100 %) dos puntos de unión libres compatibles se unen solos al soltar un elemento
RADIO_UNION_MAX = 12  # tope en unidades del dibujo: con zoom bajo no une lo que no está casi encima
TIPOS_ACCION = FICHAS_ACCION  # continua, condicionada, al activar, al desactivar, por evento (+ «limitada» de ficheros antiguos)
TEXTO_LIMITADA = "Condicionada (con límite de tiempo)"
TEXTO_ORDEN = "Orden de forzado"  # sexto tipo del submenú «Tipo de acción»: la acción pasa a ser una orden de forzado
TIPOS_ETAPA = (("ordinary", "Etapa", "etapa"), ("enclosing", "Encapsulante", "encapsulante"),
               ("macro", "Macroetapa", "macroetapa"))  # (tipo de `set_step_kind`, texto del menú, ficha de la paleta)
TEXTO_INICIAL = "Etapa inicial"  # la casilla (independiente de los tipos) del submenú «Tipo de etapa»
CONTINUAS = ("continua", "condicionada", "limitada")  # los tipos de una acción continua
CON_CONDICION = ("condicionada", "limitada")  # las continuas con condición: se programa en el panel de opciones
DISPARADOR = {"activacion": "activation", "desactivacion": "deactivation", "evento": "event"}
RESERVADAS = {p.lower() for p in KEYWORDS | set(FUNCS_REF) | FUNCS_EXPR | {"delay"}}  # palabras de las fórmulas
COLOCACIONES = (("fila", "En fila, pegadas"), ("fila-separada", "En fila, separadas"), ("matriz-2", "En matriz de 2"),
                ("columna", "En columna"))
PARPADEO_MS, PARPADEO_PASOS = 250, 6  # tres parpadeos en 1,5 s: encendido al empezar y en los pasos 2 y 4
MSG_SOLAPE = "No se puede poner encima de otro elemento"
MSG_ACCION_SUELTA = ("Acción suelta: arrástrela hasta una etapa (desde el punto de unión de su izquierda) para unirla, "
                     "o péguela al lado de otra acción.")
MSG_SOLAPE_PARCIAL = "Un grafcet parcial nuevo no se pone encima de otro elemento ni de otro marco: suéltelo en un hueco"
MSG_ENCIMA = "Las acciones quedan encima de otro elemento: apártelo"  # aviso (no error): no se pudo abrir hueco
RECINTO_DX = 140  # del centro de la encapsulante al borde izquierdo del marco de su recinto vacío
RECINTO_PASO = 40  # hueco entre dos marcos vacíos seguidos
ENCUADRE = 3 * H  # semilado del cuadrado que se encuadra alrededor de una etapa o macroetapa (la encapsulante, la macroetapa)
FORMAS_FORZADO = (("explicit", "Explícita"), ("current", "La situación actual"), ("empty", "Vacía"), ("initial", "Inicial"))
MARGEN_SUELTA = 2 * H  # lo que se agranda, a la derecha y debajo, la zona de suelta de un parcial no raíz: una etapa de ancho y de alto
MSG_SIN_SITIO = "No hay sitio libre a la derecha para la expansión: suelte la macroetapa en un hueco más despejado"
INTERNO = re.compile(r"(?<![\w-])[a-z]-[0-9a-f]{32}(?![\w-])")  # el ID que crea grafcet.ids.IdGenerator: no es para mostrar
_CODIGO = r"(?:[DUH]-[A-Z0-9][A-Z0-9-]*|REQ-[A-Z]+-[0-9]+|P-IMP-[0-9]+)"
CODIGOS = re.compile(rf"\s*\({_CODIGO}(?:\s*[,;]\s*{_CODIGO})*\)|\b{_CODIGO}\s*:\s*|\s*\b{_CODIGO}\b"
                     r"|\s*\[[a-z]+(?:[.-][a-z0-9]+)+\]")  # códigos internos y etiquetas de capacidad
MSG_ORDEN_SIN_ETAPAS = "Una orden explícita necesita al menos una etapa del parcial: elíjala, o use la forma «Vacía»."
MSG_SIN_DESTINO = "No hay otro parcial al que forzar: cree un recinto, una macroetapa o un grafcet parcial."
MSG_EQUIDISTANCIA = "No se puede equidistanciar: algo quedaría encima de otro elemento; apártelo antes"
MSG_ORDEN_SUELTA = ("Orden de forzado suelta: no se simula. Elija su parcial destino con doble clic (o en el panel de opciones) y "
                    "arrástrela hasta una etapa (desde el punto de unión de su izquierda) para unirla, o péguela al lado de otra acción.")
