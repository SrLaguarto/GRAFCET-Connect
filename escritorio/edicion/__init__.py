"""Fachada Qt del editor de escritorio y sus exportaciones históricas."""
from __future__ import annotations

import copy
import re
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from grafcet.diagnostics import Diagnostic, DiagnosticError
from grafcet.expressions import FUNCS_EXPR, FUNCS_REF, KEYWORDS
from grafcet.notation import a_nucleo, a_usuario, etapas_ambiguas, x_etapa
from grafcet.editor import Editor, Fragment, new_grafcet_document
from grafcet.ids import MAX_LABEL, label_key, valid_label
from grafcet.persistence import Project, add_document, new_project, save_project
from grafcet.profile import normalize_options
from grafcet.routing import project_on_link
from grafcet.timeutil import parse_duration
from grafcet.values import format_value, parse_type, parse_value, zero
from grafcet.view import (Vista, display_names, force_situation, norm, layout_from_presentation, presentation_for,
                         substitute)
from ..mensajes import amable, correccion_amable, mezcla_acciones
from .. import orden_acciones, pegado_acciones
from ..geometria import acciones as geo_acciones, choques as geo_choques, enlaces as geo_enlaces
from ..geometria import equidistancia as geo_equidistancia, textos as geo_textos
from ..geometria.acciones import BORDE_ACCION, IMAN_ACCION
from ..geometria.base import PASO, Rect, ajustar, esquina_parcial, punto_modelo
from ..geometria.choques import (
    BARRA_ALTO_MIN, DESPLAZA_MAX, DESPLAZA_PASADAS, EXP_DX, EXP_DY, EXP_INTENTOS, EXP_PASO, MARGEN_SOLAPE,
)
from ..geometria.enlaces import IMAN
from ..bloques import _dur_usuario, normalizar_duracion, sin_comillas
from ..anotaciones import en as anotacion_en, rect as rect_anotacion, importar_imagen, editar_texto
from ..diagrama import (
    ACT_LINK, ACT_MIN, EVOLUCION_HORIZONTAL, FICHAS_ACCION, H, RADIO_ANCLA, REJILLA, SX, TB, VACIO_H, VACIO_W,
    _distancia, _extra, _geometria_acciones, _Pintor, ancla_en, anclas, barra, caja_barra, cajas_parciales,
    elemento_en, enlaces, icono_accion, medida_comentario, orientaciones, posiciones, rects_comentarios, rects_textos_t,
)
from .modelo import _Modelo
from .seleccion import _Seleccion
from .gestos import _Gestos
from .arrastre import _Arrastre
from .colocacion import _Colocacion
from .interaccion_enlaces import _Enlaces
from .diagnosticos import _Diagnosticos
from .acciones import _Acciones
from .grupos import _Grupos
from .menus import _Menus
from .variables import _Variables
from .formulas import _Formulas
from .jerarquia import _Jerarquia
from .forzados import _Forzados
from .portapapeles import _Portapapeles
from .historial import _Historial
from .diagnosticos import Parpadeo
from .constantes import (
    CODIGOS, COLOCACIONES, CONTINUAS, CON_CONDICION, DISPARADOR, DY, ENCUADRE, FORMAS_FORZADO,
    HERRAMIENTAS, INTERNO, MARGEN_SUELTA, MAX_ETIQUETA_ETAPA, MSG_ACCION_SUELTA, MSG_ENCIMA,
    MSG_EQUIDISTANCIA, MSG_ORDEN_SIN_ETAPAS, MSG_ORDEN_SUELTA, MSG_SIN_DESTINO, MSG_SIN_SITIO, MSG_SOLAPE,
    MSG_SOLAPE_PARCIAL, PARPADEO_MS, PARPADEO_PASOS, RADIO_UNION, RADIO_UNION_MAX, RECINTO_DX,
    RECINTO_PASO, RESERVADAS, TEXTO_INICIAL, TEXTO_LIMITADA, TEXTO_ORDEN, TIPOS_ACCION, TIPOS_ETAPA,
    _CODIGO,
)
from .utilidades import aviso_valores_iniciales, quitar_comillas_vista, quitar_valores_iniciales, sin_codigos


__all__ = [
    "ACT_LINK", "ACT_MIN", "Any", "BARRA_ALTO_MIN", "BORDE_ACCION", "CODIGOS", "COLOCACIONES", "CONTINUAS",
    "CON_CONDICION", "Callable", "DESPLAZA_MAX", "DESPLAZA_PASADAS", "DISPARADOR", "DY", "Diagnostic",
    "DiagnosticError", "ENCUADRE", "EVOLUCION_HORIZONTAL", "EXP_DX", "EXP_DY", "EXP_INTENTOS", "EXP_PASO",
    "Edicion", "Editor", "FICHAS_ACCION", "FORMAS_FORZADO", "FUNCS_EXPR", "FUNCS_REF", "Fraction", "Fragment",
    "H", "HERRAMIENTAS", "IMAN", "IMAN_ACCION", "INTERNO", "KEYWORDS", "MARGEN_SOLAPE", "MARGEN_SUELTA",
    "MAX_ETIQUETA_ETAPA", "MAX_LABEL", "MSG_ACCION_SUELTA", "MSG_ENCIMA", "MSG_EQUIDISTANCIA",
    "MSG_ORDEN_SIN_ETAPAS", "MSG_ORDEN_SUELTA", "MSG_SIN_DESTINO", "MSG_SIN_SITIO", "MSG_SOLAPE",
    "MSG_SOLAPE_PARCIAL", "PARPADEO_MS", "PARPADEO_PASOS", "PASO", "Parpadeo", "Path", "Project", "QObject",
    "QPointF", "QRectF", "QTimer", "Qt", "RADIO_ANCLA", "RADIO_UNION", "RADIO_UNION_MAX", "RECINTO_DX",
    "RECINTO_PASO", "REJILLA", "RESERVADAS", "Rect", "SX", "Signal", "TB", "TEXTO_INICIAL", "TEXTO_LIMITADA",
    "TEXTO_ORDEN", "TIPOS_ACCION", "TIPOS_ETAPA", "VACIO_H", "VACIO_W", "Vista", "a_nucleo", "a_usuario",
    "add_document", "ajustar", "amable", "ancla_en", "anclas", "annotations", "anotacion_en", "aviso_valores_iniciales",
    "barra", "caja_barra", "cajas_parciales", "copy", "correccion_amable", "display_names", "editar_texto",
    "elemento_en", "enlaces", "esquina_parcial", "etapas_ambiguas", "force_situation", "format_value",
    "geo_acciones", "geo_choques", "geo_enlaces", "geo_equidistancia", "geo_textos", "icono_accion",
    "importar_imagen", "label_key", "layout_from_presentation", "medida_comentario", "mezcla_acciones",
    "new_grafcet_document", "new_project", "norm", "normalizar_duracion", "normalize_options", "orden_acciones",
    "orientaciones", "parse_duration", "parse_type", "parse_value", "pegado_acciones", "posiciones",
    "presentation_for", "project_on_link", "punto_modelo", "quitar_comillas_vista", "quitar_valores_iniciales",
    "re", "rect_anotacion", "rects_comentarios", "rects_textos_t", "save_project", "sin_codigos",
    "sin_comillas", "substitute", "uuid", "valid_label", "x_etapa", "zero",
]


class Edicion(
    QObject, _Modelo, _Seleccion, _Gestos, _Arrastre, _Colocacion, _Enlaces,
    _Diagnosticos, _Acciones, _Grupos, _Menus, _Variables,
    _Formulas, _Jerarquia, _Forzados, _Portapapeles, _Historial,
):
    cambiado = Signal()    # el modelo, la selección o los diagnósticos cambiaron: hay que redibujarlo todo

    redibujar = Signal()   # solo cambia el dibujo (un arrastre en curso)

    realces = Signal()     # solo cambian los realces (un paso del parpadeo): no toca el resto del dibujo ni lo provisional

    def __init__(self, ed: Editor, titulo: str, ruta: Path | None = None) -> None:
        super().__init__()
        self.ed, self.titulo, self.ruta = ed, titulo, ruta
        self.proyecto_base: Project | None = None
        self.nombres: dict[str, str] = {}
        self._cursor_borde = False
        self.archivo: Path | None = None  # el .grafnet de donde viene o donde se guardó
        self.contenedor: Any = None  # su ProyectoArchivo (área temporal, sello y huella)
        self.info_archivo: dict | None = None  # metadatos de ese archivo ({} si es anterior a la 1.0); None: sin guardar
        self.puede_firmarse = True  # False si se abrió sin firma válida: Guardar y Guardar como lo dejan sin firma
        self.autor_archivo: str | None = None  # autor puesto a mano; None: el del archivo o el recordado en preferencias
        self.ignorados = self._sanear_borradores()
        self.enlaces_quitados = len(ed.cleaned_draft_link_ids)
        self.barras_limpiadas = ed.cleaned_bar_refs  # uniones de barra a elementos que ya no existen, quitadas al abrir
        parciales = [p["id"] for p in ed.model["partials"]]
        self.raiz = "g" if "g" in parciales else parciales[0]
        self.herramienta = "seleccionar"
        self.sel: list[str] = []
        self._mensaje, self.mensaje_info = "", False
        self.seleccion_aviso = ((), None)
        from ..vigencia_avisos import VigenciaAviso
        self.vigencia_aviso = VigenciaAviso(self.ed)
        self._previas: tuple[Any, ...] = ()  # ver `_choques`
        self._encima: list[str] = []  # etapas o grupos cuyas acciones quedaron encima de algo en la última operación atómica
        self.opciones = normalize_options(None)
        self.diagrama: Any = None
        self.parpadeo = Parpadeo(self)  # lo que parpadea en naranja tras un error
        self.parpadeo.cambia.connect(self.realces)
        self._memo_validacion: list[tuple[Any, ...]] = []  # (modelo, presentación, resultado) de las últimas validaciones: ver `_validacion`
        self.arrastre: dict[str, Any] | None = None  # id, desplazamiento del agarre, posición actual, si se movió
        self.enlace: dict[str, Any] | None = None    # punto de unión de origen de un enlace que se está trazando
        self.flecha = "flow"
        self.accion: str | None = None  # la acción señalada de la etapa seleccionada (clic en su caja)
        self.ver_accion = False  # las opciones muestran la acción señalada de la etapa (no la etapa): clic en su caja, Editar…
        self.parte_editada: tuple[str, str] | None = None  # (acción, «condicion», «evento» o «accion»): lo que se edita ahora en Propiedades; se resalta en el dibujo
        self.lazo: dict[str, Any] | None = None  # rectángulo de selección que se está trazando desde un hueco
        self.menu_marcadas: set[str] = set()     # opciones del último menú que van marcadas (el tipo actual de una acción)
        self.menu_desmarcadas: set[str] = set()  # opciones del último menú que son casillas sin marcar (enlace de activación)
        self.M: dict[str, Any] = {}
        # Ganchos de interfaz: la ventana los sustituye por diálogos
        self.pedir_condicion: Callable[[str], None] = lambda tid: None
        self.pedir_etiqueta: Callable[[str], None] = lambda ident: None
        self.pedir_accion: Callable[[str, str | None], None] = lambda sid, aid: None
        self.pedido_explicito = False  # True mientras el usuario pide las opciones (doble clic, Intro, «Editar…»)
        self._clave_antes: tuple | None = None  # lo que mostraba el panel de opciones al pulsar el ratón (`clave_panel`)
        self.tras_gesto: Callable[[tuple, tuple], None] | None = None  # (antes, después) al pulsar y al soltar en el dibujo
        self.confirmar_borrado: Callable[[dict[str, list[str]]], bool] = lambda plan: True
        # (título, rótulo, propuesta) -> el texto escrito, o None si se cancela; sin ventana, vale la propuesta
        self.pedir_texto: Callable[[str, str, str], str | None] = lambda titulo, etiqueta, actual: actual
        # datos de la orden (`_datos_forzado`) -> {"destino": ID del parcial, "forma": explicit|current|empty|initial,
        # "etapas": [ID]} o None si se cancela; sin ventana, una orden nueva se cancela y una que se edita no cambia
        self.pedir_forzado: Callable[[dict[str, Any]], dict[str, Any] | None] = lambda datos: datos["actual"]
        self.reconstruir()

    @classmethod
    def nuevo(cls) -> "Edicion":
        return cls(Editor(new_grafcet_document(f"grafcet-{uuid.uuid4().hex[:8]}")), "Grafcet nuevo")

    @classmethod
    def desde(cls, doc: dict[str, Any], layout: dict[str, tuple[float, float]], titulo: str, ruta: Path | None = None,
              presentacion: dict[str, Any] | None = None) -> "Edicion":
        """Copia editable de un modelo (un ejemplo o uno abierto); el original no se toca."""
        doc = copy.deepcopy(doc)
        return cls(Editor(doc, copy.deepcopy(presentacion) if presentacion else presentation_for(doc, layout)),
                   titulo, ruta)

    @property
    def _alto_minimo_barra(self) -> int:
        return BARRA_ALTO_MIN

    @property
    def _desplazamiento_maximo(self) -> int:
        return DESPLAZA_MAX
