"""Edición de un grafcet secuencial en el simulador (P-IMP-32, paso 3): crear etapas y transiciones, enlazarlas,
moverlas, borrarlas, editar etiquetas y receptividades, deshacer y rehacer, y guardar.

Toda la edición la hacen las operaciones de grafcet/editor.py (transacciones, deshacer y rehacer, diagnósticos):
este módulo solo traduce los gestos del ratón a esas operaciones y no toca el documento a mano. No pregunta
nada por sí mismo: los diálogos (receptividad, etiqueta, confirmación de borrado) son ganchos que pone la ventana,
así que se puede probar sin pantalla.
"""
from __future__ import annotations

import copy
import heapq
import math
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

from .mensajes import amable, correccion_amable
from .bloques import _dur_usuario, normalizar_duracion
from .anotaciones import en as anotacion_en, rect as rect_anotacion, importar_imagen, editar_texto
from .diagrama import (ACT_LINK, ACT_MIN, FICHAS_ACCION, H, RADIO_ANCLA, REJILLA, SX, TB, VACIO_H, VACIO_W, _distancia, _extra,
                       _geometria_acciones, _Pintor, ancla_en, anclas, barra, caja_barra, cajas_parciales, elemento_en, enlaces,
                       orientaciones, rects_textos_t,
                       icono_accion, posiciones)

HERRAMIENTAS = ("seleccionar",)  # el ratón selecciona, mueve y enlaza; los elementos nuevos solo se colocan arrastrándolos
MAX_ETIQUETA_ETAPA = 4  # lo más largo que se escribe en la etiqueta de una etapa: más no cabe en su cuadro (lo ya guardado con más se abre igual)
DY = 60  # distancia vertical estándar: tres pasos de rejilla entre etapa y transición
IMAN = 40  # a qué distancia horizontal (dos pasos de rejilla) un elemento movido se alinea con uno enlazado
RADIO_UNION = 8  # a qué distancia (px al 100 %) dos puntos de unión libres compatibles se unen solos al soltar un elemento
RADIO_UNION_MAX = 12  # tope en unidades del dibujo: con zoom bajo no une lo que no está casi encima
BORDE_ACCION = RADIO_ANCLA  # a cada lado de los bordes derecho e inferior de una acción, de los que se tira para sacar otra: lo mismo que el radio de un punto de unión, en unidades del dibujo (crece con el zoom igual que él)
IMAN_ACCION = 16  # a qué distancia de otra acción se pega una acción suelta (lado derecho, o inferior en columna)
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
MARGEN_SOLAPE = 8  # un elemento no se coloca a menos de esto de la caja de otro (en unidades del dibujo)
MSG_SOLAPE = "No se puede poner encima de otro elemento"
MSG_SOLAPE_PARCIAL = "Un grafcet parcial nuevo no se pone encima de otro elemento ni de otro marco: suéltelo en un hueco"
MSG_ENCIMA = "Las acciones quedan encima de otro elemento: apártelo"  # aviso (no error): no se pudo abrir hueco
DESPLAZA_MAX = 600  # lo más que se desplaza a la derecha lo que estorba a las acciones de una etapa (P-IMP-48)
BARRA_ALTO_MIN = 4  # alto con el que una barra cuenta como obstáculo aunque se dibuje sin grosor (la «O»)
DESPLAZA_PASADAS = 4  # veces que se recalcula el hueco tras desplazar, por si sigue habiendo algo que estorba
# Jerarquías (P-IMP-23..27, REQ-EDT-08, REQ-JER-04, 05, 07): dónde se colocan la expansión de una macroetapa y el marco de un recinto
EXP_DX = 280   # de la macroetapa a la columna de su expansión (a la derecha, como en el ejemplo «macroetapa»)
EXP_DY = 320  # espacio inicial de edición de la expansión; independiente del paso entre elementos
EXP_PASO = 160  # si la columna no está libre, cuánto se corre a la derecha para probar otra
EXP_INTENTOS = 40
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


def sin_codigos(texto: str) -> str:
    """El texto sin códigos internos (D-…, U-…, H-…, REQ-…, P-IMP-…) ni etiquetas de capacidad entre corchetes:
    «D-REF: no existe X» es «no existe X»; el código sigue en el objeto diagnóstico, no en lo que se enseña."""
    if not texto:
        return texto
    return re.sub(r"\s{2,}", " ", CODIGOS.sub("", texto)).strip()


MSG_ORDEN_SIN_ETAPAS = "Una orden explícita necesita al menos una etapa del parcial: elíjala, o use la forma «Vacía»."
MSG_SIN_DESTINO = "No hay otro parcial al que forzar: cree un recinto, una macroetapa o un grafcet parcial."
MSG_EQUIDISTANCIA = "No se puede equidistanciar: algo quedaría encima de otro elemento; apártelo antes"
MSG_ORDEN_SUELTA = ("Orden de forzado suelta: no se simula. Elija su parcial destino con doble clic (o en el panel de opciones) y "
                    "arrástrela hasta una etapa (desde el punto de unión de su izquierda) para unirla, o péguela al lado de otra acción.")


class Parpadeo(QObject):
    """Parpadeo naranja de lo que da error (REQ-EDT-09): un conjunto de ID (elementos del dibujo o filas de variables) que
    se enciende y se apaga unas veces con un temporizador. No sabe de aspecto: quien dibuja pregunta `activos()` y
    redibuja cuando `cambia` avisa. Sin pantalla, se comprueba el estado (`ids`, `fase`, `t.isActive()`)."""

    cambia = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.ids: set[str] = set()
        self.fase = False
        self.restan = 0
        self.t = QTimer(self)
        self.t.setInterval(PARPADEO_MS)
        self.t.timeout.connect(self.paso)

    def iniciar(self, ids: Any) -> None:
        """Empieza a parpadear con estos ID (si ya parpadeaba otra cosa, la sustituye)."""
        self.ids, self.fase, self.restan = set(ids), True, PARPADEO_PASOS
        self.t.start()
        self.cambia.emit()

    def paso(self) -> None:
        self.restan -= 1
        if self.restan <= 0:
            self.parar()
            return
        self.fase = not self.fase
        self.cambia.emit()

    def parar(self) -> None:
        self.t.stop()
        hubo = self.fase or bool(self.ids)
        self.ids, self.fase, self.restan = set(), False, 0
        if hubo:
            self.cambia.emit()

    def activos(self) -> set[str]:
        """Los que se dibujan en naranja ahora (vacío en la fase apagada)."""
        return set(self.ids) if self.fase else set()


def ajustar(v: float) -> int:
    """Al punto de la rejilla más cercano."""
    return round(v / REJILLA) * REJILLA


def quitar_valores_iniciales(doc: dict[str, Any]) -> list[str]:
    """P-IMP-117: todas las variables empiezan en 0 (falso). Pone a cero los valores iniciales declarados en `doc` (un
    fichero hecho a mano o por otra herramienta) y devuelve una frase por variable cambiada, p. ej. «N empezaba en 3»."""
    quitadas = []
    for v in doc.get("variables", []):
        try:
            t = parse_type(v["type"])
            if parse_value(t, v["initialValue"]) == zero(t):
                continue
            antes = v["initialValue"]
            v["initialValue"] = format_value(t, zero(t))
        except (DiagnosticError, KeyError, TypeError, ValueError):
            continue  # un fichero mal formado lo informa la validación
        texto = {True: "verdadero", False: "falso"}.get(antes, antes)
        quitadas.append(f"{v['name']} empezaba en {texto}")
    return quitadas


def aviso_valores_iniciales(quitadas: list[str]) -> str:
    return (f"Valores iniciales quitados: {'; '.join(quitadas)}. En GRAFCET Connect todas las variables empiezan en 0; "
            "si la condición necesita un número, escríbalo en la receptividad (por ejemplo C = 3).")


class Edicion(QObject):
    cambiado = Signal()    # el modelo, la selección o los diagnósticos cambiaron: hay que redibujarlo todo
    redibujar = Signal()   # solo cambia el dibujo (un arrastre en curso)

    def __init__(self, ed: Editor, titulo: str, ruta: Path | None = None) -> None:
        super().__init__()
        self.ed, self.titulo, self.ruta = ed, titulo, ruta
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
        self._encima: list[str] = []  # etapas o grupos cuyas acciones quedaron encima de algo en la última operación atómica
        self.opciones = normalize_options(None)
        self.diagrama: Any = None
        self.parpadeo = Parpadeo(self)  # lo que parpadea en naranja tras un error
        self.parpadeo.cambia.connect(self.redibujar)
        self.arrastre: dict[str, Any] | None = None  # id, desplazamiento del agarre, posición actual, si se movió
        self.enlace: dict[str, Any] | None = None    # punto de unión de origen de un enlace que se está trazando
        self.flecha = "flow"
        self.accion: str | None = None  # la acción señalada de la etapa seleccionada (clic en su caja)
        self.ver_accion = False  # las opciones muestran la acción señalada de la etapa (no la etapa): clic en su caja, Editar…
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

    def _sanear_borradores(self) -> int:
        """Al abrir: descarta los borradores de acción dañados (no son un diccionario, sin id, de tipo desconocido, con la
        posición ausente o no numérica) y devuelve cuántos. Una etapa inexistente deja el borrador suelto; una variable
        inexistente, con «?». Una orden de forzado sin completar (tipo «forzado») pierde el destino o las etapas que no existen."""
        p, m = self.ed.presentation, self.ed.model
        if "draftActions" not in p:
            return 0
        crudos = p["draftActions"] if isinstance(p["draftActions"], list) else []
        buenos, malos = [], 0 if isinstance(p["draftActions"], list) else 1
        etapas, variables = {s["id"] for s in m["steps"]}, {v["id"] for v in m["variables"]}
        parciales = {q["id"] for q in m["partials"]}
        for b in crudos:
            try:
                ok = isinstance(b, dict) and isinstance(b.get("id"), str) and b.get("tipo") in Editor.DRAFT_TIPOS
                if ok:
                    float(Fraction(str(b["x"]))), float(Fraction(str(b["y"])))
            except (KeyError, ValueError, ZeroDivisionError):
                ok = False
            if not ok:
                malos += 1
                continue
            for k in ("variable", "condicion", "valor", "evento", "limite", "etapa", "grupo", "destino", "forma"):
                if k in b and not isinstance(b[k], str):
                    del b[k]
            if "etapas" in b and not (isinstance(b["etapas"], list) and all(isinstance(i, str) for i in b["etapas"])):
                del b["etapas"]
            if "orden" in b and (not isinstance(b["orden"], int) or isinstance(b["orden"], bool)):
                del b["orden"]
            if b.get("etapa") not in etapas:
                b.pop("etapa", None)
            if b.get("variable") not in variables:
                b.pop("variable", None)
            if b.get("destino") not in parciales:  # una orden de forzado sin completar: lo que ya no existe, se quita
                b.pop("destino", None)
            if b.get("forma") not in Editor.DRAFT_FORMAS:
                b.pop("forma", None)
            if "etapas" in b:
                b["etapas"] = [i for i in b["etapas"] if i in etapas]
                if not b["etapas"]:
                    del b["etapas"]
            buenos.append(b)
        p["draftActions"] = buenos
        return malos

    @property
    def mensaje(self) -> str:
        return self._mensaje

    @mensaje.setter
    def mensaje(self, texto: str) -> None:
        # por defecto, un error o un rechazo
        self._mensaje, self.mensaje_info = sin_codigos(self.sin_internos(texto)), False

    def informar(self, texto: str) -> None:
        """Un aviso informativo (no un error): se muestra sin el rojo de los rechazos."""
        self._mensaje, self.mensaje_info = sin_codigos(self.sin_internos(texto)), True

    def _nombres_vivos(self) -> dict[str, str]:
        """El nombre visible de cada elemento del modelo tal como está ahora (no como se dibujó por última vez), con el de los
        enlaces en borrador («enlace en borrador 2→0»); los de la última vista siguen valiendo para lo que ya no está."""
        try:
            nombres = display_names(self.ed.model)
        except (KeyError, TypeError, AttributeError):
            nombres = {}
        for d in self.ed.model.get("draftLinks", []):
            nombres[d["id"]] = f"enlace en borrador {nombres.get(d['fromRef'], '?')}→{nombres.get(d['toRef'], '?')}"
        return {**getattr(self, "nombres", {}), **nombres}

    def sust(self, texto: str) -> str:
        """El texto de un diagnóstico del núcleo (mensaje, corrección, `DiagnosticError`) sin ID: el núcleo escribe los ID de
        los elementos y aquí se cambian por sus nombres (los de la última vista dibujada; el ID interno que falte, por el del
        modelo de ahora, y el que ya no existe se llama «un elemento»). Solo para lo que trae ID del núcleo: sustituye palabras
        enteras, así que un texto de la aplicación (que no los trae) no debe pasar por aquí; esos interpolan el nombre en origen
        (`_nom`)."""
        if not texto:
            return texto
        return amable(sin_codigos(self.sin_internos(substitute(texto, getattr(self, "nombres", {})))))

    def sin_internos(self, texto: str) -> str:
        """Lo último que se hace con un mensaje antes de enseñarlo: cada ID interno que haya quedado en él (el que crea el
        editor, de la forma `s-<32 cifras hexadecimales>`) se cambia por el nombre de su elemento (el de la última vista; si no,
        el del modelo de ahora) o por «un elemento» si ya no existe. Solo toca esos ID: ni una palabra más del texto, de modo que
        el texto fijo de la aplicación no cambia aunque el ID de una variable de un fichero externo sea «a»."""
        if not texto or not INTERNO.search(texto):
            return texto
        dibujados, vivos = getattr(self, "nombres", {}), None

        def nombre(mo: re.Match[str]) -> str:
            nonlocal vivos
            ident = mo.group(0)
            n = dibujados.get(ident)
            if n is None:
                vivos = self._nombres_vivos() if vivos is None else vivos  # (solo si hace falta: recorre el modelo)
                n = vivos.get(ident)
            return "un elemento" if n is None or INTERNO.fullmatch(n) else n
        return INTERNO.sub(nombre, texto)

    def _nom(self, ident: str) -> str:
        """El nombre de un elemento para un texto de la aplicación, que lo interpola en origen en vez de sustituir después: el
        de la última vista dibujada o, si no está, el del modelo de ahora; el ID interno que ya no existe se llama «un elemento»
        y el que no es interno (el de un ejemplo o de un fichero externo) es su propio nombre."""
        n = self.nombres.get(ident)
        if n is None:
            n = self._nombres_vivos().get(ident)
        if n is None:
            return "un elemento" if INTERNO.fullmatch(ident) else ident
        return n

    # -- creación ----------------------------------------------------------------------------------
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

    # -- lo que se dibuja --------------------------------------------------------------------------
    def layout(self) -> dict[str, tuple[float, float]]:
        lay = layout_from_presentation(self.ed.presentation)
        a = self.arrastre
        if a and a.get("tipo") in (None, "marco"):  # una etapa o macroetapa, o el marco de un recinto vacío
            lay[a["id"]] = (a["x"], a["y"])
        elif a and a.get("tipo") == "grupo":  # varios seleccionados que se mueven juntos: cada uno, con el mismo desplazamiento
            dx, dy = a["x"] - a["x0"], a["y"] - a["y0"]
            lay.update({i: (x + dx, y + dy) for i, (x, y) in a["inicio"].items() if a["tipos"][i] in ("nodo", "marco")})
        return lay

    def _barras(self) -> list[dict[str, Any]]:
        """Las barras de la presentación, con el arrastre en curso aplicado."""
        out = copy.deepcopy(self.ed.bars())
        a = self.arrastre
        for b in out:
            if a and a["id"] == b["id"] and a.get("tipo") == "estirar":
                b["x"], b["ancho"] = str(a["x"]), str(a["ancho"])
            elif a and a["id"] == b["id"] and a.get("tipo") == "barra":
                b["x"], b["y"] = str(a["x"]), str(a["y"])
            elif a and a.get("tipo") == "grupo" and a["tipos"].get(b["id"]) == "barra":
                x0, y0 = a["inicio"][b["id"]]
                b["x"], b["y"] = str(x0 + a["x"] - a["x0"]), str(y0 + a["y"] - a["y0"])
        return out

    def reconstruir(self) -> None:
        """Rehace la estructura que se dibuja (Vista) a partir del modelo y las posiciones actuales."""
        ed = self.ed
        self.vista = Vista(ed.model["id"], self.titulo, "", lambda: (ed.model, self.layout()), self.opciones,
                           hidden=ed.hidden_labels(), bars=self._barras(), link_styles=self.estilos_enlaces(),
                           draft_actions=self._borradores(), action_layouts=ed.action_layouts(),
                           comments=ed.comments(), orientations=ed.transition_orientations())
        self.M = self.vista.model
        self.M["annotations"] = self.ed.annotations()
        if self.arrastre:
            a = self.arrastre
            for n in self.M["annotations"]:
                if a.get("tipo") in ("anotacion","tamano_anotacion") and a["id"] == n["id"]:
                    n.update({k:a[k] for k in ("x","y","width","height") if k in a})
                elif a.get("tipo") == "grupo" and n["id"] in a["inicio"]:
                    x,y=a["inicio"][n["id"]];n.update(x=x+a["x"]-a["x0"],y=y+a["y"]-a["y0"])
        self.nombres = self.M.get("names", {})
        self._marcos_vacios()
        vivos = set(posiciones(self.M)) | {d["id"] for d in self.M.get("drafts", [])} | {e["id"] for e in enlaces(self.M)} | {b["id"] for b in self.M.get("bars", [])}
        vivos |= {n["id"] for n in self.M.get("annotations",[])}
        self.nombres.update({n["id"]:("Texto" if n["kind"] == "text" else n.get("name","Imagen")) for n in self.M.get("annotations",[])})
        self.nombres.update({b["id"]: b["label"] for b in self.M.get("bars", [])})  # los avisos de una barra la llaman «Simultaneidad 2»
        vivos |= set(cajas_parciales(self.M))  # los parciales con marco (un recinto, una expansión) también se seleccionan
        vivos |= {f["id"] for f in ed.model["forces"]}  # y las órdenes de forzado
        vivos |= {a["id"] for a in ed.model["actions"]} | {d["id"] for d in ed.draft_actions()}
        vivos |= {f"enlaceacc:{s['id']}" for s in self.M["steps"]
                  if s["actions"] or any(d.get("etapa") == s["id"] for d in self.M.get("draftActions", []))}
        self.sel = [i for i in self.sel if i in vivos]
        if self.accion not in vivos:  # la acción señalada ya no existe (se deshizo, cambió de ID al completarse…)
            self.accion = None

    def _marcos_vacios(self) -> None:
        """Un recinto sin etapas (el que acaba de crear «Añadir recinto…») no lo dibuja Vista, que solo lleva los parciales con
        etapas: aquí se anota en `M["partials"]` con `vacio`, para que el dibujo le ponga un marco vacío que se vea, se
        seleccione y reciba lo que se suelte dentro. Su esquina superior izquierda es la que se guardó en la presentación al
        crearlo (la posición del ID del parcial); sin ella, queda a la derecha de su encapsulante. Lo mismo para un grafcet
        parcial suelto sin etapas (el que crea la ficha «Grafcet parcial»), que no es recinto ni expansión: su marco es el
        redondeado de los parciales, en la posición guardada (sin ella, no se dibuja). Solo lo hace el editor: el banco y el
        simulador no dibujan un parcial sin etapas."""
        m, pos, lay = self.ed.model, posiciones(self.M), self.layout()
        puestos = {p["id"] for p in self.M.get("partials", [])}
        jerarquicos = ({e["partialRef"] for e in m["hierarchy"]["enclosures"]}
                       | {x["partialRef"] for x in m["hierarchy"]["expansions"]})
        for parte in m["partials"]:  # un parcial suelto sin etapas, ni transiciones, ni recinto o expansión: su marco redondeado
            pid = parte["id"]
            if pid != self.raiz and pid not in puestos and pid not in jerarquicos and pid in lay \
                    and not parte["stepRefs"] and not parte["transitionRefs"]:
                x, y = lay[pid]
                self.M.setdefault("partials", []).append({"id": pid, "label": parte["label"], "owner": parte.get("ownerRef"),
                                                          "kind": "partial", "vacio": True, "x": x, "y": y})
        huecos: dict[str, int] = {}
        for e in m["hierarchy"]["enclosures"]:
            pid, dueno = e["partialRef"], e["ownerStepRef"]
            parte = next((p for p in m["partials"] if p["id"] == pid), None)
            if pid in puestos or parte is None:
                continue
            k = huecos[dueno] = huecos.get(dueno, -1) + 1
            if pid in lay:
                x, y = lay[pid]
            elif dueno in pos:
                x = ajustar(pos[dueno][0] + RECINTO_DX + k * (VACIO_W + RECINTO_PASO) - SX)
                y = ajustar(pos[dueno][1] - H - 22)
            else:
                continue
            self.M.setdefault("partials", []).append({"id": pid, "label": parte["label"], "owner": parte.get("ownerRef"),
                                                      "kind": "enclosure", "ownerStep": dueno, "vacio": True, "x": x, "y": y})

    def diagnosticos(self) -> list[dict[str, Any]]:
        """Los diagnósticos del modelo para el panel (REQ-EDT-09): código, texto con nombres, corrección y elemento."""
        out = []
        repetidas = self._grupos_repetidos()
        for grupo in repetidas:  # un solo aviso por número repetido, con todas sus etapas marcadas en el dibujo (P-IMP-118)
            n = len(grupo)
            etiqueta = self.ed.get(grupo[0])["label"]
            que = "número" if etiqueta.isdigit() else "nombre"
            mensaje = (f"Hay dos etapas con el {que} {etiqueta}: cambie una." if n == 2 else
                       f"Hay {n} etapas con el {que} {etiqueta}: deje solo una con ese {que}.")
            out.append({"code": "D-NOMBRE-COLISION", "message": mensaje,
                        "correction": "Cambie el número de una de las etapas marcadas (en Propiedades, o con doble clic en ella)",
                        "severity": "error", "blocks": True, "question": None, "element": grupo[0], "target": grupo[0],
                        "targets": list(grupo)})
        enrepetidas = {i for g in repetidas for i in g}
        for d in self.ed.validate().diagnostics:
            if d.code == "D-NOMBRE-COLISION" and d.element in enrepetidas:
                continue
            mensaje, correccion = self.sust(d.message), self.sust(correccion_amable(d.code, d.correction))
            evento = next((a for a in self.ed.model["actions"] if a.get("trigger", {}).get("kind") == "event" and d.element in (a["id"],a["trigger"].get("expressionRef"))), None)
            if d.code == "D-TIPO-EVENTO" and evento:
                texto = self.texto_accion(evento["id"], "evento")
                mensaje = (f"Acción por evento de {self._nom(evento['targetRef'])} en la etapa {self._nom(evento['stepRef'])}: "
                           f"el disparador «{texto}» debe ser un evento, no solo una condición booleana.")
                correccion = "Elija el evento que deba disparar la acción: flanco de subida (↑) o de bajada (↓) de la variable."
                mensaje += " Use un flanco de subida (↑) o de bajada (↓), según lo que necesite."
            if d.code == "D-EXP-PENDIENTE":
                mensaje = self._texto_expresion_pendiente(mensaje, self.dibujable(d.element))
            if d.code == "D-SIMULTANEIDAD":
                mensaje += self._lados_cruzados(d.element)
            mensaje = sin_codigos(mensaje)
            out.append({"code": d.code, "message": mensaje, "correction": correccion,
                        "severity": d.severity, "blocks": d.blocks_start, "question": d.question,
                        "element": d.element, "target": evento["id"] if d.code == "D-TIPO-EVENTO" and evento else self.dibujable(d.element),
                        "completo": d.code in ("D-SIMULTANEIDAD", "D-BARRA-SUELTA") or (d.code == "D-ALTERNANCIA" and self._es_enlace_borrador(d.element))})
        if self.ignorados:
            out.append({"code": "AVISO", "severity": "advertencia", "blocks": False, "question": None, "element": None,
                        "target": None, "correction": "Se descartó al abrir; vuelva a colocar la acción si hacía falta",
                        "message": "Se ignoró un borrador de acción dañado" if self.ignorados == 1
                        else f"Se ignoraron {self.ignorados} borradores de acción dañados"})
        for b in self.ed.draft_actions():  # diagnósticos de la edición: los borradores no están en el modelo ejecutable
            suelta = not b.get("etapa")
            if b["tipo"] == "forzado":
                falta = self._faltan_orden(b)
                out.append({"code": "D-FORZADO-PENDIENTE", "severity": "bloqueo", "blocks": True, "question": None, "element": b["id"],
                            "target": b["id"],
                            "message": "Orden de forzado sin configurar suelta" if suelta else
                            f"Orden de forzado sin configurar en la etapa {self.nombre(b['etapa'])} ({', '.join(falta)})",
                            "correction": "Una la orden a una etapa con un enlace desde su punto de unión izquierdo"
                            if suelta else "Elija su parcial destino y su forma con «Configurar orden de forzado…» (botón derecho "
                            "en ella, o doble clic)"})
                continue
            out.append({"code": "D-ACCION-PENDIENTE", "severity": "bloqueo",
                        "blocks": True, "question": None, "element": b["id"], "target": b["id"],
                        "message": "Acción sin configurar suelta" if suelta else
                        f"Acción sin configurar en la etapa {self.nombre(b['etapa'])} "
                        f"({', '.join(self.faltan(self._datos_borrador(b), self._parcial_borrador(b)))})",
                        "correction": "Una la acción a una etapa con un enlace desde su punto de unión izquierdo"
                        if suelta else "Complete la acción con «Editar…» (botón derecho en ella)"})
        return out

    def _lados_cruzados(self, barra_id: str | None) -> str:
        """Si algo está unido a la barra por el lado contrario al que se ve (encima, por abajo; debajo, por arriba): una frase
        que lo dice, para añadir al aviso de la barra (su enlace da la vuelta en el dibujo); si no, vacío."""
        b = next((b for b in self.M.get("bars", []) if b["id"] == barra_id), None)
        if b is None:
            return ""
        pos = posiciones(self.M)
        mal = [(i, lado) for lado, ids in (("arriba", b["arriba"]), ("abajo", b["abajo"])) for i in ids
               if i in pos and (pos[i][1] > b["y"] if lado == "arriba" else pos[i][1] < b["y"])]
        if not mal:
            return ""
        quien = ", ".join(self._nom(i) for i, _ in mal)
        return (f" {quien} {'está' if len(mal) == 1 else 'están'} unida{'' if len(mal) == 1 else 's'} por el lado contrario al que "
                "se ve (su línea da la vuelta a la barra): quítela de la barra y vuelva a unirla desde su salida, si va antes de la "
                "barra, o a su entrada, si va después.")

    def _es_enlace_borrador(self, ident: str | None) -> bool:
        return any(d["id"] == ident for d in self.ed.model.get("draftLinks", []))

    def _texto_expresion_pendiente(self, mensaje: str, objetivo: str | None) -> str:
        """D-EXP-PENDIENTE en palabras normales: «la receptividad está vacía» o «no es válida: «texto»» (de una
        transición; de una acción, «la condición o el valor»)."""
        es_transicion = any(t["id"] == objetivo for t in self.ed.model["transitions"])
        que = "la receptividad" if es_transicion else "la condición o el valor"
        texto = re.search(r"«(.*)»", mensaje)
        if "sin significado" in mensaje and (texto is None or not texto.group(1).strip()):
            return f"{que} está vacía"
        return f"{que} no es válida" + (f": «{texto.group(1)}»" if texto and texto.group(1).strip() else "")

    def dibujable(self, elemento: str | None) -> str | None:
        """El elemento del dibujo al que se refiere un diagnóstico (una receptividad, la transición que la usa)."""
        if elemento is None:
            return None
        m = self.ed.model
        if elemento in posiciones(self.M) or any(d["id"] == elemento for d in m["draftLinks"]) \
                or any(d["id"] == elemento for d in self.ed.draft_actions()):
            return elemento
        for t in m["transitions"]:
            if t["conditionRef"] == elemento:
                return t["id"]
        for a in m["actions"]:
            if a.get("trigger", {}).get("expressionRef") == elemento:
                return a["id"]
            if a["id"] == elemento or elemento in (a.get("conditionRef"), a.get("valueRef")):
                return a["stepRef"]
        for r in m["hierarchy"]["enclosures"]:  # un recinto: su encapsulante; una expansión: su macroetapa
            if r["id"] == elemento:
                return r["ownerStepRef"]
        for x in m["hierarchy"]["expansions"]:
            if x["id"] == elemento:
                return x["ownerMacroRef"]
        if any(f["id"] == elemento for f in m["forces"]):  # una orden de forzado: su caja, en la fila de su etapa
            return elemento
        return elemento if elemento in cajas_parciales(self.M) or any(b["id"] == elemento for b in self.M.get("bars", [])) else None

    def marcados(self) -> set[str]:
        return self.marcados_de(self.diagnosticos())

    @staticmethod
    def marcados_de(diags: list[dict[str, Any]]) -> set[str]:
        """Los elementos del dibujo que se marcan en rojo: el de cada diagnóstico que impide simular (un aviso puede
        marcar varios, como las etapas con el mismo número)."""
        return {t for d in diags if d["blocks"] for t in (d.get("targets") or [d["target"]]) if t}

    def _grupos_repetidos(self) -> list[list[str]]:
        """Las etapas de cada parcial que comparten número o nombre, agrupadas en el orden del modelo."""
        grupos: dict[tuple[str, str], list[str]] = {}
        for s in self.ed.model["steps"]:
            grupos.setdefault((s["partialRef"], label_key(s["label"])), []).append(s["id"])
        return [g for g in grupos.values() if len(g) > 1]

    def cambia(self) -> None:
        self.reconstruir()
        self.cambiado.emit()

    # -- selección ---------------------------------------------------------------------------------
    def seleccionar(self, ids: list[str]) -> None:
        """Selecciona exactamente estos elementos (el panel de diagnósticos, «Ir a…»): ya no hay una acción señalada, así que
        Supr borra lo seleccionado y no una acción de antes."""
        self.sel = list(ids)
        self.accion = None
        self.ver_accion = False
        self.cambiado.emit()

    def estilos_enlaces(self) -> dict[str, Any]:
        styles = copy.deepcopy(self.ed.link_styles())
        if self.arrastre and self.arrastre.get("tipo") in ("flecha", "tramo"):
            styles[self.arrastre["id"]] = self.arrastre["style"]
        return styles

    def ajustar_flecha(self, **cambios: Any) -> None:
        if len(self.sel) != 1:
            return
        ident = self.sel[0]
        style = copy.deepcopy(self.ed.link_styles().get(ident, {}))
        style.setdefault("arrows", {}).setdefault(self.flecha, {}).update(cambios)
        self.ed.set_link_style(ident, style)
        self.cambia()

    def restablecer_flecha(self) -> None:
        """Quita el ajuste manual de la flecha elegida del enlace seleccionado (el recorrido se recoloca a mano)."""
        if len(self.sel) != 1:
            return
        ident = self.sel[0]
        style = copy.deepcopy(self.ed.link_styles().get(ident, {}))
        style.get("arrows", {}).pop(self.flecha, None)
        self.ed.set_link_style(ident, style)
        self.cambia()

    def centro(self, ident: str) -> QPointF | None:
        n=self.anotacion(ident)
        p = rect_anotacion(n).center().toTuple() if n else posiciones(self.M).get(ident)
        caja = next((c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] == ident), None)
        if p is None and caja:  # una acción (sus cajas están dibujadas)
            x, y, w, h = caja["rect"]
            p = (x + w / 2, y + h / 2)
        barra_ = next((b for b in self.M.get("bars", []) if b["id"] == ident), None)
        if p is None and barra_:
            bx, by, w, h = barra(barra_)
            p = (bx + w / 2, by + h / 2)
        if p is None:
            d = next((d for d in self.M.get("drafts", []) if d["id"] == ident), None)
            a, b = (posiciones(self.M).get(d["from"]), posiciones(self.M).get(d["to"])) if d else (None, None)
            p = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) if a and b else None
        if p is None and (orden := next((c for c in getattr(self.diagrama, "cajas_ordenes", None) or [] if c["id"] == ident), None)):
            x, y, w, h = orden["rect"]  # una orden de forzado: el centro de su caja
            p = (x + w / 2, y + h / 2)
        if p is None and (caja_p := cajas_parciales(self.M).get(ident)):  # un parcial: el centro de su marco
            p = ((caja_p["x0"] + caja_p["x1"]) / 2, (caja_p["y0"] + caja_p["y1"]) / 2)
        return QPointF(*p) if p else None

    def parpadear(self, ids: Any, centrar: bool = True) -> None:
        """Un error que se refiere a estos elementos (etapas, transiciones, barras, acciones, enlaces): parpadean en naranja
        y el primero se lleva a la vista si queda fuera."""
        ids = [i for i in dict.fromkeys(ids) if i]
        if not ids:
            return
        self.parpadeo.iniciar(ids)
        c = self.centro(ids[0]) if centrar else None
        if c is not None and hasattr(self.diagrama, "centrar_si_fuera"):
            self.diagrama.centrar_si_fuera(c)

    def rechazar(self, texto: str, *ids: str | None) -> None:
        """Un rechazo de una operación: el mensaje (en rojo) y el parpadeo de los elementos a los que se refiere."""
        self.mensaje = texto
        self.parpadear([i for i in ids if i])

    # -- gestos del ratón (los llama VistaDiagrama) ---------------------------------------------------
    def _modelo(self, p: QPointF) -> tuple[int, int]:
        return ajustar(p.x() - SX), ajustar(p.y())

    def anotacion(self, ident):
        return next((n for n in self.M.get("annotations",[]) if n["id"] == ident),None)

    def poner_anotacion(self, tipo, p):
        datos={"text":"Texto","font":"Arial","size":18,"color":"#172e4d"}
        if tipo == "imagen":
            try:datos=importar_imagen(self.diagrama.window() if self.diagrama else None)
            except (OSError,ValueError) as exc:self.informar(str(exc));return None
            if datos is None:return None
        ident=self.ed.add_annotation("text" if tipo == "texto" else "image",self._modelo(p),partialRef=self.parcial_en(p),**datos)
        self.sel,self.accion=[ident],None;self.cambia();return ident

    def editar_anotacion(self, ident):
        n=self.anotacion(ident)
        if not n:return
        try:datos=editar_texto(n,self.diagrama.window() if self.diagrama else None) if n["kind"] == "text" else importar_imagen(self.diagrama.window() if self.diagrama else None)
        except (OSError,ValueError) as exc:self.informar(str(exc));return
        if datos is not None:self.ed.update_annotation(ident,**datos);self.cambia()

    def colocar(self, tipo: str, p: QPointF) -> None:
        """Un elemento de la paleta soltado en el dibujo: «etapa», «encapsulante», «macroetapa», «parcial», «transicion»,
        «simultaneidad», «forzado» o «accion:<tipo>» (continua, condicionada, activacion, desactivacion, evento; «accion» a secas
        es una continua). Si su caja quedaría encima de la de otro elemento (con un margen pequeño), no se coloca (un grafcet
        parcial tampoco, encima de otro marco); una acción que toca a otra se pega a ella. Una etapa, una encapsulante, una
        macroetapa o una transición pertenece al parcial en cuyo marco se suelta (`parcial_en`): una expansión, un recinto; fuera
        de todo marco, al raíz. Un «parcial» crea un grafcet parcial nuevo y vacío, con su marco (`poner_parcial`). Una orden de
        forzado se suelta como una acción (`poner_orden_ficha`): suelta, sin efecto en la simulación hasta que se configura y se
        une a una etapa; soltada sobre una etapa, se une a ella."""
        if tipo in ("texto","imagen"):
            self.poner_anotacion(tipo,p);return
        if tipo == "forzado":
            self.poner_orden_ficha(p)
            return
        if self._huella_ficha(tipo, p):
            self.informar(MSG_SOLAPE_PARCIAL if tipo == "parcial" else MSG_SOLAPE)
            self.cambiado.emit()
            return
        if tipo == "parcial":
            self.poner_parcial(p)
        elif tipo in ("etapa", "etapa_inicial", "encapsulante", "transicion"):
            with self.ed.group("colocar"):  # (con su enlace, si queda muy cerca de un punto de unión libre: un solo paso)
                if tipo == "transicion":
                    nuevo = self.poner_transicion(p)
                else:
                    nuevo = self.poner_etapa(p, inicial=tipo == "etapa_inicial", tipo="enclosing" if tipo == "encapsulante" else "ordinary")
                self._unir_cercanos({nuevo})
            self.cambia()
        elif tipo == "macroetapa":
            self.poner_macro(p)
        elif tipo in ("simultaneidad", "simultaneidad:apertura", "simultaneidad:cierre"):
            self.poner_barra(p, "Y")
        elif tipo == "accion" or tipo.startswith("accion:"):
            with self.ed.group("colocar acción"):
                did = self.poner_accion_suelta(p, tipo.partition(":")[2] or "continua")
                if did:
                    self._unir_cercanos({did})

    # -- unión automática al soltar (P-IMP-114) --------------------------------------------------------------
    def _zoom(self) -> float:
        escala = getattr(self.diagrama, "escala", None)
        return (escala() if callable(escala) else 1.0) or 1.0

    def _ancla_libre(self, a: dict[str, Any]) -> bool:
        """Si el punto de unión `a` (de `anclas`) está libre: una transición, sin etapa anterior (arriba) o siguiente
        (abajo); una etapa, sin transición que llegue a ella (arriba) o salga de ella (abajo) y, a la derecha, sin acciones;
        el de una acción suelta, siempre."""
        M, ident, lado = self.M, a["id"], a["lado"]
        t = next((t for t in M["transitions"] if t["id"] == ident), None)
        if t is not None:
            return not t["pre" if lado == "arriba" else "post"]
        if lado == "izq":
            return True
        if lado == "der":
            return not any(s["id"] == ident and s["actions"] for s in M["steps"]) and not any(
                d.get("etapa") == ident for d in M.get("draftActions", []))
        clave = "post" if lado == "arriba" else "pre"
        return not any(ident in u[clave] for u in M["transitions"])

    def _par_union(self, a: dict[str, Any], b: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Los dos puntos, en el orden de `unir` (el que emite, de abajo, primero), si forman un par válido: salida de
        transición con entrada de etapa, salida de etapa con entrada de transición, o el punto de una acción suelta con el
        de las acciones de una etapa. Cualquier otro: None."""
        pasos, trans = self._pasos(), {t["id"] for t in self.M["transitions"]}
        for x, y in ((a, b), (b, a)):
            if x["lado"] == "izq" and y["lado"] == "der" and y["id"] in pasos and x["id"] not in pasos | trans:
                return x, y
            if x["lado"] == "abajo" and y["lado"] == "arriba" and (
                    (x["id"] in trans and y["id"] in pasos) or (x["id"] in pasos and y["id"] in trans)):
                return x, y
        return None

    def _unir_cercanos(self, ids: set[str]) -> bool:
        """Al soltar `ids` (recién creados o movidos): si un punto de unión libre de alguno queda a RADIO_UNION o menos (a
        la escala del dibujo) de un punto libre compatible de otro elemento (no de los soltados con él), los une como si se
        hubiera trazado el enlace (`unir`), dentro del mismo paso de deshacer. Elige el par más cercano; sin par válido, nada.
        Devuelve si unió algo (P-IMP-114)."""
        self.reconstruir()
        radio = min(RADIO_UNION / self._zoom(), RADIO_UNION_MAX)
        pos = posiciones(self.M)
        propios = [a for i in ids if i in pos or any(d["id"] == i for d in self.M.get("draftActions", []))
                   for a in anclas(self.M, i) if self._ancla_libre(a)]
        ajenos = [a for i in [*pos, *(d["id"] for d in self.M.get("draftActions", []))] if i not in ids
                  for a in anclas(self.M, i) if self._ancla_libre(a)]
        mejor: tuple[float, tuple[dict[str, Any], dict[str, Any]]] | None = None
        for a in propios:
            for b in ajenos:
                d = ((a["pos"].x() - b["pos"].x()) ** 2 + (a["pos"].y() - b["pos"].y()) ** 2) ** 0.5
                par = self._par_union(a, b) if d <= radio else None
                if par and (mejor is None or d < mejor[0]):
                    mejor = (d, par)
        if mejor is None:
            return False
        self.unir(*mejor[1])
        return True

    def poner_accion_suelta(self, p: QPointF, tipo: str = "continua") -> str:
        """Una ficha de acción soltada en un punto: una acción suelta de ese tipo, sin variable todavía (se dibuja con «?»),
        con su punto de unión a la izquierda. Si toca el lado derecho (o el inferior, en columna) de otra acción, se pega
        a ella: pasa a su etapa o a su grupo. No abre ningún diálogo: se une a una etapa con un enlace y se completa con
        «Editar…» (P-IMP-41, P-IMP-43). Con `tipo` «forzado», una orden de forzado suelta (P-IMP-68), con su rectángulo doble y
        «G?{?}» hasta que se configura."""
        x, y = self._modelo(p)
        iman = self._buscar_iman([], x, y, ACT_MIN)
        did = ""
        destino: list[Any] = [(None, [])]

        def hacer() -> None:
            nonlocal did
            did = self.ed.add_draft_action((x, y), {"tipo": tipo})
            if iman:
                destino[0] = self._pegar([did], iman["objetivo"])
        motivo = self._atomico("colocar acción", hacer)
        if motivo:
            self.rechazar(motivo)
            self.cambiado.emit()
            return ""
        if iman:
            self._tras_pegar([did], *destino[0])
        else:
            self.sel, self.accion = [did], None
            self.informar(MSG_ORDEN_SUELTA if tipo == "forzado" else
                          "Acción suelta: arrástrela hasta una etapa (desde el punto de unión de su izquierda) para unirla, "
                          "o péguela al lado de otra acción.")
            self.cambiado.emit()
        return did

    def _punto(self, p: QPointF, ident: str | None) -> dict[str, Any] | None:
        """El punto de unión bajo el puntero, salvo sobre el trazo de una transición: agarrarla la mueve, no saca una rama."""
        if ident and any(t["id"] == ident for t in self.M["transitions"]):
            return None
        return ancla_en(self.M, p)

    def pasar(self, p: QPointF) -> None:
        """Sin pulsar: marca los puntos de unión del elemento bajo el puntero y resalta el más cercano."""
        if self.diagrama is None:
            return
        ident = elemento_en(self.M, p)
        cerca = self._punto(p, ident)
        caja = (self.accion_en(p) or self._accion_por_borde(p)) if ident is None else None
        if caja and caja.get("suelta"):  # sobre una acción suelta: se ve el punto de unión de su grupo
            ident = caja["cabeza"]
        self.diagrama.marcar_anclas(anclas(self.M, ident or (cerca["id"] if cerca else "")), cerca)
        borde = self._borde_accion(caja, p) if caja else None
        if borde:  # en el borde derecho o inferior de una acción: el punto de donde se tira, y el cursor del sentido
            x, y, w, h = caja["rect"]
            punto = {"id": caja["id"], "lado": "nueva_" + borde,
                     "pos": QPointF(x + w, y + h / 2) if borde == "der" else QPointF(x + w / 2, y + h)}
            self.diagrama.marcar_anclas([punto], punto)
        vista = getattr(self.diagrama, "viewport", None)
        if callable(vista) and (borde or getattr(self, "_cursor_borde", False)):
            vista().setCursor(Qt.CursorShape.SizeHorCursor if borde == "der" else Qt.CursorShape.SizeVerCursor if borde
                              else Qt.CursorShape.CrossCursor)
        self._cursor_borde = bool(borde)

    @staticmethod
    def _num(v: float) -> str:
        return str(int(v)) if v == int(v) else str(v)

    @staticmethod
    def _rango_tramo(pts: list[Any], i: int, vertical: bool) -> tuple[float, float]:
        """Lo que ocupa el tramo i de un recorrido a lo largo del otro eje (y si es vertical, x si es horizontal)."""
        e = 1 if vertical else 0
        return min(pts[i][e], pts[i + 1][e]), max(pts[i][e], pts[i + 1][e])

    def _pegar_a_paralelo(self, valor: float, vertical: bool, propio: str, rango: tuple[float, float]) -> float:
        """Al colocar a mano un tramo (P-IMP-118): si la posición de la rejilla lo deja a media rejilla (10) o menos de un tramo
        paralelo de OTRO enlace que de verdad coincide con él a lo largo del otro eje (`rango` y el del otro se cortan, con 4 de
        margen), queda exactamente en la coordenada de ese tramo (solo hacia el solape, nunca para apartarse); si no, la
        posición de la rejilla. `vertical`: el tramo es vertical (su x); si no, su y."""
        eje = 0 if vertical else 1
        mejor = None
        for r in enlaces(self.M):
            if r["id"] == propio:
                continue
            for u, v in zip(r["pts"], r["pts"][1:]):
                lo, hi = min(u[1 - eje], v[1 - eje]), max(u[1 - eje], v[1 - eje])
                if u != v and u[eje] == v[eje] and abs(u[eje] - valor) <= REJILLA / 2                         and max(lo, rango[0]) <= min(hi, rango[1]) + 4:
                    if mejor is None or abs(u[eje] - valor) < abs(mejor - valor):
                        mejor = u[eje]
        return valor if mejor is None else mejor

    def _arrastre_tramo(self, enlace: str, p: QPointF) -> dict[str, Any] | None:
        """Agarrar el cuerpo de un enlace y arrastrar mueve el tramo de su recorrido que se agarra (como su tirador, sin
        seleccionarlo antes): None si el punto no cae en un tramo movible (el primero y el último, que unen con la etapa o la
        transición, no se mueven; un enlace recto no tiene ninguno): entonces solo se selecciona."""
        for r in enlaces(self.M):
            if r["id"] != enlace:
                continue
            pts = r["pts"]
            for h in r["handles"]:
                i = h["segment"]
                if _distancia(p, pts[i], pts[i + 1]) <= 7:
                    return {"id": r["id"], "tipo": "tramo", "pts": r.get("routePts", r["pts"]), "handle": h, "movido": False,
                            "start": p, "style": copy.deepcopy(self.ed.link_styles().get(r["id"], {}))}
        return None

    def _barra(self, ident: str | None) -> dict[str, Any] | None:
        return next((b for b in self.M.get("bars", []) if b["id"] == ident), None)

    def clave_panel(self) -> tuple[tuple[str, ...], str | None]:
        """Lo que muestra el panel de opciones: lo seleccionado y la acción señalada (para saber si un gesto lo cambia)."""
        return tuple(self.sel), self.accion_activa()

    def prensar(self, p: QPointF, event: Any = None) -> bool:
        """Empieza el gesto del ratón y avisa a `tras_gesto(antes, despues)`: si pulsar ya cambia lo que mostraba el panel de
        opciones, la ventana lo esconde en ese momento (sin fijar), sin enseñar antes la página nueva."""
        self._clave_antes = self.clave_panel()
        if self.mensaje in (MSG_SOLAPE, MSG_SOLAPE_PARCIAL):  # el aviso de una ficha ya soltada no sigue a la vista
            self.mensaje = ""
            self.cambiado.emit()
        resultado = self._prensar(p, event)
        if self.tras_gesto is not None:
            self.tras_gesto(self._clave_antes, self.clave_panel())
        return resultado

    def soltar(self, p: QPointF, event: Any = None) -> bool:
        """Termina el gesto del ratón y avisa a `tras_gesto(antes, despues)` de lo que mostraba el panel de opciones al
        pulsar y de lo que muestra al soltar (lo que cambia al soltar, como una selección con lazo)."""
        antes, self._clave_antes = self._clave_antes, None
        resultado = self._soltar(p, event)
        if antes is not None and self.tras_gesto is not None:
            self.tras_gesto(antes, self.clave_panel())
        return resultado

    def _prensar(self, p: QPointF, event: Any = None) -> bool:
        ident = elemento_en(self.M, p)
        n = self.anotacion(ident)
        if n:
            if self._mayus(event):
                self.sel = [i for i in self.sel if i != ident] if ident in self.sel else self.sel+[ident]
                self.accion=None;self.cambiado.emit();return True
            if ident in self.sel and len(self.sel)>1:
                self.arrastre=self._arrastre_grupo(ident,p,([ident],None,False))
            else:
                r=rect_anotacion(n);tamano=ident in self.sel and (p-r.bottomRight()).manhattanLength()<=12
                self.sel,self.accion=[ident],None
                self.arrastre={"tipo":"tamano_anotacion" if tamano else "anotacion","id":ident,"original":dict(n),
                               "dx":p.x()-r.left(),"dy":p.y()-r.top(),"x":n["x"],"y":n["y"],"movido":False}
            self.cambiado.emit();return True
        punto = self._punto(p, ident)
        amplia = self._mayus(event)
        if punto and punto["lado"] == "izq":  # el punto de unión de una acción suelta (o de su grupo)
            self.sel, self.accion = self._ids_grupo(punto["id"]), None
            self.enlace = punto
            self.cambiado.emit()
            self.enlace = punto
            return True
        caja = (self.accion_en(p) or self._accion_por_borde(p)) if ident is None else None
        if caja:
            if caja.get("suelta") and not amplia and caja["id"] in self.sel and set(self.sel) - set(self._ids_grupo(caja["id"])):
                # una de las seleccionadas junto a otras cosas: no se deshace la selección, se mueven todas juntas
                self.accion = None
                ids = self._ids_grupo(caja["id"])
                self.arrastre = self._arrastre_grupo(ids[0], p, (ids, caja["id"], False))
            elif caja.get("suelta"):  # una acción suelta se selecciona y se mueve, con las que lleva pegadas
                ids = self._ids_grupo(caja["id"])
                self.sel, self.accion = ids, caja["id"]
                cab = self._borrador(ids[0])
                hx, hy = float(Fraction(str(cab["x"]))), float(Fraction(str(cab["y"])))
                self.arrastre = {"id": ids[0], "ids": ids, "tipo": "borrador", "dx": p.x() - (hx + SX), "dy": p.y() - hy,
                                 "x": hx, "y": hy, "movido": False}
            elif not amplia and len(self.sel) > 1 and caja["etapa"] in self.sel:
                # la acción de una etapa de una selección múltiple: se mueven todas juntas, con la etapa
                self.accion = None
                self.arrastre = self._arrastre_grupo(caja["etapa"], p, ([caja["etapa"]], caja["id"], True))
            elif caja.get("forzado"):  # una orden sin completar unida a una etapa: se selecciona ella, como una orden del modelo
                self.sel, self.accion = [caja["id"]], None
            elif amplia:  # Mayús incluye la etapa con sus acciones; copiar conserva el conjunto.
                self.sel = list(dict.fromkeys(self.sel + [caja["etapa"]]))
                self.accion, self.ver_accion = None, False
            else:  # La etapa es el contexto de propiedades; solo se resalta la acción.
                self.sel, self.accion, self.ver_accion = [caja["etapa"]], caja["id"], True
                borde = self._borde_accion(caja, p)
                if borde:  # del borde derecho o inferior, arrastrar saca una acción nueva a continuación de esta
                    self.enlace = {"id": caja["id"], "lado": "nueva_" + borde, "pos": p, "nueva": borde}
            enlace = self.enlace
            self.cambiado.emit()
            self.enlace = enlace  # (los que atienden el cambio pueden rehacer el estado del gesto)
            return True
        orden = self.orden_en(p) if ident is None and not punto else None
        if orden:  # una orden de forzado se selecciona (no se mueve ni se ordena: no es una acción)
            self.sel, self.accion = [orden["id"]], None
            self.cambiado.emit()
            return True
        union = self.union_en(p) if ident is None and not punto else None
        if union:  # el enlace de una etapa con sus acciones
            self.sel, self.accion = [union], None
            self.cambiado.emit()
            return True
        self.accion = None
        rutas = enlaces(self.M)
        # Las flechas se pueden agarrar directamente; los tiradores solo aparecen al seleccionar.
        for r in rutas:
            for f in r["arrows"]:
                if (p-QPointF(*f["pos"])).manhattanLength() <= 12:
                    self.sel, self.flecha = [r["id"]], f["key"]
                    self.arrastre = {"id": r["id"], "tipo": "flecha", "pts": r["pts"], "movido": False,
                                     "start": p, "style": copy.deepcopy(self.ed.link_styles().get(r["id"], {}))}
                    self.cambiado.emit()
                    return True
        for r in rutas:
            if r["id"] not in self.sel:
                continue
            for handle in r["handles"]:
                if (p-QPointF(*handle["pos"])).manhattanLength() <= 12:
                    self.arrastre = {"id": r["id"], "tipo": "tramo", "pts": r.get("routePts", r["pts"]), "handle": handle,
                                     "movido": False, "start": p,
                                     "style": copy.deepcopy(self.ed.link_styles().get(r["id"], {}))}
                    return True
        for b in (self._barra(i) for i in self.sel):  # tiradores de los extremos de una barra seleccionada: se estira
            if b:
                bx, by, w, hh = barra(b)
                for lado, cx in (("izq", bx), ("der", bx + w)):
                    if abs(p.x() - cx) <= 9 and abs(p.y() - (by + hh / 2)) <= 10:
                        self.arrastre = {"id": b["id"], "tipo": "estirar", "lado": lado, "x": b["x"], "ancho": b["ancho"],
                                         "movido": False}
                        return True
        if punto:  # de un punto de unión sale directamente el enlace
            self.enlace = punto
            self.sel = [punto["id"]]
            self.cambiado.emit()
            self.enlace = punto
            return True
        if amplia and ident:  # Mayús añade a la selección (o la quita, si ya estaba) sin arrastrar
            self.sel = [i for i in self.sel if i != ident] if ident in self.sel else self.sel + [ident]
            self.cambiado.emit()
            return True
        if ident and not amplia and ident in self.sel and len(self.sel) > 1:
            # uno de varios seleccionados: no se deshace la selección; arrastrar los mueve a todos juntos (un clic sin mover
            # lo deja en solo ese, al soltar)
            self.arrastre = self._arrastre_grupo(ident, p, ([ident], None, False))
            if self.arrastre is not None:
                self.cambiado.emit()
                return True
        previa = list(self.sel) if amplia else []
        self.sel = [ident] if ident else previa
        if ident is None:  # un hueco: arrastrar dibuja el rectángulo de selección (el lazo)
            self.lazo = {"ini": p, "movido": False, "previa": previa}
        pos = posiciones(self.M).get(ident or "")
        b = self._barra(ident)
        if ident and "|" in ident:  # un enlace: agarrarlo y arrastrar mueve el tramo agarrado (no abre ninguna rama)
            self.arrastre = self._arrastre_tramo(ident, p)
        elif pos:
            self.arrastre = {"id": ident, "dx": p.x() - pos[0], "dy": p.y() - pos[1], "x": pos[0] - SX, "y": pos[1],
                             "movido": False}
        elif b:
            self.arrastre = {"id": ident, "tipo": "barra", "dx": p.x() - (b["x"] + SX), "dy": p.y() - b["y"],
                             "x": b["x"], "y": b["y"], "movido": False}
        elif ident in cajas_parciales(self.M) and (not next((q for q in self.M["partials"] if q["id"] == ident), {}).get("vacio")
                                                  or any(n.get("partialRef") == ident for n in self.M.get("annotations",[]))):
            self.arrastre = self._arrastre_grupo(ident, p, ([ident], None, False))
        elif vacio := next((q for q in self.M["partials"] if q["id"] == ident and q.get("vacio")), None):
            # el marco de un recinto sin etapas se mueve (su posición es lo único que lo define); el de un parcial con
            # etapas es el de ellas, y solo se selecciona
            self.arrastre = {"id": ident, "tipo": "marco", "dx": p.x() - (vacio["x"] + SX), "dy": p.y() - vacio["y"],
                             "x": vacio["x"], "y": vacio["y"], "movido": False}
        self.cambiado.emit()
        return True

    @staticmethod
    def _mayus(event: Any) -> bool:
        return event is not None and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

    def dentro(self, a: QPointF, b: QPointF) -> list[str]:
        """Lo que queda entero dentro del rectángulo (a, b): etapas, macroetapas, transiciones, barras, acciones y marcos."""
        r = QRectF(a, b).normalized()
        out = []
        giros = orientaciones(self.M)
        for ident, (x, y) in posiciones(self.M).items():
            caja = caja_barra(giros[ident], x, y) if ident in giros else QRectF(x - H, y - H, 2 * H, 2 * H)
            if r.contains(caja):
                out.append(ident)
        for bar in self.M.get("bars", []):
            bx, by, w, h = barra(bar)
            if r.contains(QRectF(bx, by, w, h)):
                out.append(bar["id"])
        for c in getattr(self.diagrama, "cajas_acciones", None) or []:
            if r.contains(QRectF(*c["rect"])):
                out.append(c["id"])
        for ident, caja in cajas_parciales(self.M).items():
            if r.contains(QRectF(caja["x0"], caja["y0"], caja["x1"] - caja["x0"], caja["y1"] - caja["y0"])):
                out.append(ident)
        out += [n["id"] for n in self.M.get("annotations",[]) if r.contains(rect_anotacion(n))]
        return out

    def _iman(self, ident: str, x: float, moviendo: set[str] | frozenset[str] = frozenset()) -> float:
        """Al mover una etapa o una transición cerca de la vertical de un elemento enlazado con ella (a IMAN o menos), se
        alinea con él: el enlace queda recto, sin la S de un desplazamiento de un par de puntos de rejilla. Con varios
        elementos que se mueven juntos (`moviendo`), solo cuentan los enlazados que se quedan donde están."""
        pos = posiciones(self.M)
        enlazados = set()
        for t in self.M["transitions"]:
            pasos = set(t.get("preDib", t["pre"])) | set(t.get("postDib", t["post"]))
            if t["id"] == ident:
                enlazados |= pasos
            elif ident in pasos:
                enlazados.add(t["id"])
        xs = [pos[o][0] - SX for o in enlazados if o in pos and o not in moviendo]
        cerca = min(xs, key=lambda v: abs(v - x), default=None)
        return cerca if cerca is not None and 0 < abs(cerca - x) <= IMAN else x

    def mover(self, p: QPointF, event: Any = None) -> bool:
        a = self.arrastre
        if a and a.get("tipo") in ("anotacion","tamano_anotacion"):
            if a["tipo"] == "anotacion":
                a["x"],a["y"]=self._modelo(QPointF(p.x()-a["dx"],p.y()-a["dy"]))
            else:
                n=a["original"];w=max(20,p.x()-SX-n["x"]);h=max(20,p.y()-n["y"])
                if n["kind"] == "image":
                    k=max(w/n["width"],h/n["height"]);w,h=n["width"]*k,n["height"]*k
                a.update(width=w,height=h)
            a["movido"]=True;self.reconstruir();self.redibujar.emit();return True
        if a and a.get("tipo") in ("flecha", "tramo"):
            if (p-a["start"]).manhattanLength() < 3 and not a["movido"]:
                return True
            if a["tipo"] == "flecha":
                segment, ratio = project_on_link(a["pts"], p.toTuple())
                a["style"].setdefault("arrows", {}).setdefault(self.flecha, {}).update(segment=segment, ratio=str(ratio))
            else:
                pts, handle = a["pts"], a["handle"]
                if handle.get("orient"):  # enlace de una transición girada: se corre el tramo, en perpendicular a su eje
                    i = handle["segment"]
                    vertical = pts[i][0] == pts[i + 1][0]
                    previo = a.setdefault("tramos0", a["style"].get("route", {}).get("tramos", {}))  # lo guardado al pulsar
                    valido = isinstance(previo, dict) and str(previo.get("n")) == str(len(pts))
                    d0 = float(previo.get(str(i), 0)) if valido else 0.0
                    destino = self._pegar_a_paralelo(ajustar(p.x() if vertical else p.y()), vertical, a["id"], self._rango_tramo(pts, i, vertical))
                    nuevo = dict(previo) if valido else {}
                    desplazamiento = d0 + destino - pts[i][0 if vertical else 1]
                    nuevo.update({"n": str(len(pts)), str(i): str(int(desplazamiento)) if desplazamiento == int(desplazamiento)
                                  else str(desplazamiento)})
                    a["style"]["route"] = {**a["style"].get("route", {}), "tramos": nuevo}
                elif len(pts) == 6:
                    route = a["style"].setdefault("route", {"laneX": str(pts[2][0]-SX),
                                                            "exitY": str(pts[1][1]), "entryY": str(pts[3][1])})
                    key = {1: "exitY", 2: "laneX", 3: "entryY"}[handle.get("routeSegment", handle["segment"])]
                    vertical = key == "laneX"
                    k = handle.get("routeSegment", handle["segment"])
                    v = self._pegar_a_paralelo(ajustar(p.x() if vertical else p.y()), vertical, a["id"],
                                               self._rango_tramo(pts, k, vertical))
                    route[key] = self._num(v - SX if vertical else v)
                elif len(pts) == 4:
                    a["style"]["route"] = {"middleY": self._num(self._pegar_a_paralelo(
                        ajustar(p.y()), False, a["id"], self._rango_tramo(pts, handle["segment"], False)))}
            a["movido"] = True
            self.reconstruir()
            self.redibujar.emit()
            return True
        if a and a.get("tipo") == "borrador":  # una acción suelta que se mueve (con las que lleva pegadas)
            x, y = self._modelo(QPointF(p.x() - a["dx"], p.y() - a["dy"]))
            if (x, y) != (a["x"], a["y"]):
                a.update(x=x, y=y, movido=True)
                self.reconstruir()
                self.redibujar.emit()
            if a["movido"] and self.diagrama is not None:  # si toca otra acción, el lado donde se pegaría
                iman = self._buscar_iman(a["ids"], a["x"], a["y"])
                self.diagrama.marcar_iman(iman["linea"] if iman else None)
                self._marcar_solape(None if iman else a)
            return True
        if a and a.get("tipo") == "estirar":
            gx = ajustar(p.x() - SX)
            b = self._barra(a["id"])
            x0, x1 = (b["x"], b["x"] + b["ancho"])
            if a["lado"] == "izq":
                x0 = min(gx, x1 - 40)
            else:
                x1 = max(gx, x0 + 40)
            if (x0, x1 - x0) != (a["x"], a["ancho"]):
                a.update(x=x0, ancho=x1 - x0, movido=True)
                self.reconstruir()
                self.redibujar.emit()
            return True
        if a and a.get("tipo") == "grupo":  # varios seleccionados que se mueven juntos
            if not a["movido"] and (p - a["start"]).manhattanLength() < 4:
                return True  # (sin mover todavía: aún puede ser un clic)
            x, y = self._modelo(QPointF(p.x() - a["dx"], p.y() - a["dy"]))
            x = self._iman(a["id"], x, set(a["ids"]))
            if (x, y) != (a["x"], a["y"]):
                a.update(x=x, y=y, movido=True)
                self.reconstruir()
                self.redibujar.emit()
            if a["movido"]:
                self._marcar_solape(a)
            return True
        if a:
            x, y = self._modelo(QPointF(p.x() - a["dx"], p.y() - a["dy"]))
            x = self._iman(a["id"], x)
            if (x, y) != (a["x"], a["y"]):
                a.update(x=x, y=y, movido=True)
                self.reconstruir()
                self.redibujar.emit()
            if a["movido"]:
                self._marcar_solape(a)
            return True
        if self.lazo:
            lz = self.lazo
            if not lz["movido"] and (p - lz["ini"]).manhattanLength() < 6:
                return True
            lz["movido"] = True
            sel = lz["previa"] + [i for i in self.dentro(lz["ini"], p) if i not in lz["previa"]]
            if sel != self.sel:
                self.sel = sel
                self.redibujar.emit()
            if self.diagrama is not None:
                self.diagrama.lazo(lz["ini"], p)
            return True
        if self.enlace and self.enlace.get("nueva"):  # de un borde de una acción: la acción nueva que saldrá
            if self.diagrama is not None:
                self.diagrama.trazo_provisional(self.enlace["pos"], p)
            return True
        if self.enlace and self.diagrama is not None:
            destino = self._destino(p, self.enlace)
            self.diagrama.trazo_provisional(self.enlace["pos"], destino["pos"] if destino else p)
            self.diagrama.marcar_anclas(anclas(self.M, destino["id"]) if destino else [], destino)
            return True
        if event is not None and not event.buttons():
            self.pasar(p)
        return False

    def _elemento_sin_marco(self, p: QPointF) -> str | None:
        """El elemento bajo el punto, salvo el marco de un parcial (su borde o su nombre, que se selecciona pero no es un
        elemento al que unir nada): para soltar un enlace, soltar ahí es soltar en un hueco."""
        ident = elemento_en(self.M, p)
        return None if ident is not None and any(q["id"] == ident for q in self.M["partials"]) else ident

    def _destino(self, p: QPointF, origen: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """El punto de unión al que llegaría un enlace soltado en p: el más cercano, o el de una acción suelta bajo el
        puntero. El de la derecha de una etapa solo vale para el enlace de una acción."""
        destino = ancla_en(self.M, p, sin_der=origen is not None and origen["lado"] != "izq")
        if destino is None and self._elemento_sin_marco(p) is None:
            caja = self.accion_en(p)
            if caja and caja.get("suelta"):
                destino = anclas(self.M, caja["cabeza"])[0]  # una acción de un grupo suelto: el grupo entero
        return destino

    def _soltar(self, p: QPointF, event: Any = None) -> bool:
        if self.lazo:
            lz, self.lazo = self.lazo, None
            if self.diagrama is not None:
                self.diagrama.lazo(None)
            if lz["movido"]:
                self.sel = lz["previa"] + [i for i in self.dentro(lz["ini"], p) if i not in lz["previa"]]
            self.cambiado.emit()
            return True
        if self.arrastre:
            a, self.arrastre = self.arrastre, None
            if a.get("tipo") in ("anotacion","tamano_anotacion"):
                if a["movido"]:
                    self.ed.update_annotation(a["id"],**{k:a[k] for k in ("x","y","width","height") if k in a})
                self.cambia();return True
            if a.get("tipo") == "grupo":
                return self._soltar_grupo(a)
            if a.get("tipo") == "borrador" and self.diagrama is not None:
                self.diagrama.marcar_iman(None)
            if a["movido"] and a.get("tipo") == "borrador":
                iman = self._buscar_iman(a["ids"], a["x"], a["y"])
                if iman:  # tocaba otra acción: se pega a ella
                    self._marcar_solape(None)
                    self.reconstruir()
                    self.pegar(a["ids"], iman["objetivo"])
                    return True
                if self._hay_solape(a):
                    return self._devolver()
                self._marcar_solape(None)
                self.mover_grupo(a["ids"], a["x"], a["y"], unir=True)
                return True
            if a["movido"] and a.get("tipo") not in ("flecha", "tramo", "estirar") and self._hay_solape(a):
                return self._devolver()  # encima de otro elemento: vuelve a su sitio
            self._marcar_solape(None)
            if a["movido"]:  # un arrastre entero es una sola operación de deshacer
                if a.get("tipo") in ("flecha", "tramo"):
                    self.ed.set_link_style(a["id"], a["style"])
                elif a.get("tipo") == "estirar":
                    self.ed.resize_bar(a["id"], a["x"], a["ancho"])
                elif a.get("tipo") == "barra":
                    self.ed.move_bar(a["id"], a["x"], a["y"])
                else:
                    with self.ed.group("mover"):  # (y, si queda pegado a un punto de unión libre, su enlace: un solo paso)
                        self.ed.move(a["id"], a["x"], a["y"])
                        self._unir_cercanos({a["id"]})
            self.cambia()
            return True
        if self.enlace and self.enlace.get("nueva"):
            origen, self.enlace = self.enlace, None
            if self.diagrama is not None:
                self.diagrama.trazo_provisional(None)
            if (p - origen["pos"]).manhattanLength() > 8 / self._zoom():  # un clic sin arrastrar solo selecciona
                self.anadir_accion_tras(origen["id"], origen["nueva"])
            return True
        if self.enlace:
            origen, self.enlace = self.enlace, None
            if self.diagrama is not None:
                self.diagrama.trazo_provisional(None)
                self.diagrama.marcar_anclas([])
            destino = self._destino(p, origen)
            ident = self._elemento_sin_marco(p)
            if ident and "|" in ident and destino and (p - destino["pos"]).manhattanLength() > 5:
                destino = None  # sobre el trazo manda el enlace, no el halo de un tirador vecino
            if origen["lado"] == "der" and destino is None:
                if ident is None:
                    if (p - origen["pos"]).manhattanLength() > 8:
                        self.anadir_accion(origen["id"])
                    return True
                self.rechazar("Una acción se une a una etapa, no a una transición, una barra ni otra acción.", origen["id"])
                self.cambiado.emit()
                return True
            if origen["lado"] == "izq" and destino is None:  # de una acción suelta, solo a una etapa
                if ident is not None and any(s["id"] == ident for s in self.M["steps"]):
                    destino = sorted(anclas(self.M, ident), key=lambda a: (a["pos"] - p).manhattanLength())[0]
                else:
                    self.rechazar("Una acción se une a una etapa: suelte el enlace sobre ella.", origen["id"])
                    self.cambiado.emit()
                    return True
            if destino is None and ident and "|" in ident and ident.split("|")[2] in ("pre", "post"):
                self.unir_a_enlace(origen, ident)  # soltado sobre un enlace: una rama que se une ahí
                return True
            if destino and destino["id"] != origen["id"] and (enlace := self._enlace_del_punto(origen, destino)):
                self.unir_a_enlace(origen, enlace)  # soltado junto al tallo de una transición: el enlace que sale de él
                return True
            if destino is None and ident is None:  # soltado en un hueco: se abre una rama con el elemento que sigue
                self.crear_desde(origen, p)
                return True
            if destino is None:  # soltado sobre el cuerpo de un elemento: se une por su punto más cercano
                cerca = sorted((a for a in anclas(self.M, ident or "") if a["lado"] != "der" or origen["lado"] == "izq"),
                               key=lambda a: (a["pos"].x() - p.x()) ** 2 + (a["pos"].y() - p.y()) ** 2)
                destino = cerca[0] if cerca else None
                # desde una barra, sin apuntar a un punto concreto, cuenta dónde está el elemento: lo de encima emite hacia la
                # barra y lo de debajo recibe de ella (soltar en la mitad baja de la etapa de debajo no es unir su salida)
                barra_, pos = self._barra(origen["id"]), posiciones(self.M)
                if barra_ and ident in pos and abs(pos[ident][1] - barra_["y"]) > H:
                    lado = "abajo" if pos[ident][1] < barra_["y"] else "arriba"
                    destino = next((a for a in cerca if a["lado"] == lado), destino)
            if destino and destino["id"] != origen["id"]:
                self.unir(origen, destino)
            return True
        return False

    # -- no colocar un elemento encima de otro ---------------------------------------------------------------
    def _elementos(self) -> list[tuple[str, QRectF, str]]:
        """La caja de cada elemento que no puede quedar tapado, tal como está dibujado (etapas, macroetapas, transiciones,
        barras, acciones y grupos de acciones; no cuentan los comentarios ni los enlaces): (ID, caja, etapa de la acción)."""
        trans = orientaciones(self.M)
        out = [(i, caja_barra(trans[i], x, y) if i in trans else QRectF(x - H, y - H, 2 * H, 2 * H), "")
               for i, (x, y) in posiciones(self.M).items()]
        out += [(b["id"], QRectF(*barra(b)), "") for b in self.M.get("bars", [])]
        out += [(c["id"], QRectF(*c["rect"]), c["etapa"] or "")
                for c in getattr(self.diagrama, "cajas_acciones", None) or []]
        out += [(c["id"], QRectF(*c["rect"]), c["etapa"]) for c in getattr(self.diagrama, "cajas_ordenes", None) or []]
        return out

    def _solapa(self, huella: list[QRectF], propios: set[str]) -> list[QRectF]:
        """Las cajas de `huella` que quedan a menos de MARGEN_SOLAPE de otro elemento (no cuentan los `propios`, ni las
        acciones de una etapa que se mueve)."""
        m = MARGEN_SOLAPE
        otros = [r for i, r, etapa in self._elementos() if i not in propios and etapa not in propios]
        return [h for h in huella if any(h.adjusted(-m, -m, m, m).intersects(r) for r in otros)]

    # -- las acciones de una etapa tampoco se quedan encima de otro elemento: se aparta lo que estorba (P-IMP-48) ----
    def _colocadas(self) -> list[dict[str, Any]]:
        """Dónde quedan las acciones de cada etapa y de cada grupo suelto según el modelo y su colocación, sin esperar a
        que se dibujen: {id, etapa, grupo, rect, extra: lo que sobresalen sus marcas por arriba y por abajo}."""
        M, pos, out = self.M, posiciones(self.M), []
        unidas = M.get("draftActions", [])

        def anotar(acciones: list[dict[str, Any]], x: float, y: float, disposicion: str, suelto: bool, etapa: str,
                   grupo: str) -> None:
            for a, ax, cy, w in _geometria_acciones(x, y, acciones, disposicion, suelto)[0]:
                out.append({"id": a.get("id", ""), "etapa": etapa, "grupo": grupo, "rect": (ax, cy - H, w, 2 * H),
                            "extra": _extra(a)})
        for s in M["steps"]:
            acciones = s["actions"] + [d for d in unidas if d.get("etapa") == s["id"]]
            if acciones:
                anotar(acciones, *pos[s["id"]], s.get("actionLayout", "fila"), False, s["id"], "")
        grupos: dict[str, list[dict[str, Any]]] = {}
        for d in unidas:
            if not d.get("etapa"):
                grupos.setdefault(d.get("grupo") or d["id"], []).append(d)
        for g, miembros in grupos.items():
            anotar(miembros, miembros[0]["x"] + SX, miembros[0]["y"], (M.get("actionLayouts") or {}).get(g, "fila"),
                   True, "", g)
        return out

    def _textos_transiciones(self) -> list[tuple[QRectF, str]]:
        """Lo que ocupan los textos de las transiciones (su etiqueta a la izquierda y su receptividad a la derecha), con la
        transición a la que pertenecen."""
        out = []
        for t in self.M["transitions"]:
            tx, ty = t["x"] + SX, t["y"]
            out += [(r, t["id"]) for r in rects_textos_t(t, tx, ty) if r is not None]
        return out

    def _situacion(self, clave: str) -> tuple[float, float, list[dict[str, Any]], bool] | None:
        """Dónde empiezan (x, y en el dibujo) y cuáles son las acciones de la etapa o del grupo suelto `clave`, y si es un
        grupo suelto; None si no tiene ninguna (con el modelo ya rehecho: `reconstruir`)."""
        M = self.M
        unidas = M.get("draftActions", [])
        if any(s["id"] == clave for s in M["steps"]):
            paso = next(s for s in M["steps"] if s["id"] == clave)
            acciones = paso["actions"] + [d for d in unidas if d.get("etapa") == clave]
            return (*posiciones(M)[clave], acciones, False) if acciones else None
        acciones = [d for d in unidas if not d.get("etapa") and (d.get("grupo") or d["id"]) == clave]
        return (acciones[0]["x"] + SX, acciones[0]["y"], acciones, True) if acciones else None

    def _choques(self, clave: str, disposicion: str) -> list[tuple[QRectF, float, float, float]]:
        """Con qué choca la colocación `disposicion` de las acciones de la etapa (o del grupo suelto) `clave`: las etapas,
        transiciones, barras, textos de transición y acciones de lo demás que quedan a menos de MARGEN_SOLAPE de sus cajas, o
        que sus trazos cruzan. Cada choque: (caja del obstáculo, `ancla`, `izq`, hasta dónde llega por la derecha lo suyo que
        toca, con el margen). `ancla` es la referencia con la que `_desplazar` decide qué se mueve: el centro x de la etapa
        o transición que lleva el obstáculo (una acción, el de su etapa; un texto, el de su transición), de modo que toda
        una columna se mueve junta; para una barra o un grupo suelto, su borde izquierdo (se mueven si ese borde llega al
        corte). `izq` es el borde izquierdo de ese mismo elemento, solo para saber si el obstáculo empieza antes que las
        acciones (`_despejar`). Las barras cuentan con un alto mínimo (BARRA_ALTO_MIN) aunque midan 0. Vacío: cabe."""
        sit = self._situacion(clave)
        if sit is None:
            return []
        x, y, acciones, suelto = sit
        m = MARGEN_SOLAPE
        cajas, trazos = _geometria_acciones(x, y, acciones, disposicion, suelto)
        huella = [QRectF(ax, cy - H - _extra(a)[0], w, 2 * H + _extra(a)[0] + _extra(a)[1]).adjusted(-m, -m, m, m)
                  for a, ax, cy, w in cajas]
        lineas = [QRectF(min(x1, x2) - 1, min(y1, y2) - 1, abs(x2 - x1) + 2, abs(y2 - y1) + 2).adjusted(0, 0, m, 0)
                  for tramo in trazos for (x1, y1), (x2, y2) in zip(tramo, tramo[1:])]
        trans = orientaciones(self.M)
        pos = posiciones(self.M)
        obstaculos: list[tuple[QRectF, float, float]] = []
        for i, (px, py) in pos.items():
            if i != clave:
                r = caja_barra(trans[i], px, py) if i in trans else QRectF(px - H, py - H, 2 * H, 2 * H)
                obstaculos.append((r, px, r.left()))
        for b in self.M.get("bars", []):
            bx, by, bw, bh = barra(b)
            r = QRectF(bx, by - (BARRA_ALTO_MIN - bh) / 2, bw, BARRA_ALTO_MIN) if bh < BARRA_ALTO_MIN else QRectF(bx, by, bw, bh)
            obstaculos.append((r, bx, bx))  # (QRectF.intersects es falso con alto 0: una barra «O» nunca estorbaría)
        otras = [c for c in self._colocadas() if clave not in (c["etapa"], c["grupo"])]
        izq_grupo: dict[str, float] = {}
        for c in otras:
            if not c["etapa"]:
                izq_grupo[c["grupo"]] = min(izq_grupo.get(c["grupo"], c["rect"][0]), c["rect"][0])
        for c in otras:
            if c["etapa"]:
                obstaculos.append((QRectF(*c["rect"]), pos[c["etapa"]][0], pos[c["etapa"]][0] - H))
            else:
                obstaculos.append((QRectF(*c["rect"]), izq_grupo[c["grupo"]], izq_grupo[c["grupo"]]))
        obstaculos += [(r, pos[tid][0], pos[tid][0] - TB) for r, tid in self._textos_transiciones()]
        out = []
        for r, ancla, izq in obstaculos:
            toca = [h.right() for h in huella if h.intersects(r)] + [ln.right() for ln in lineas if ln.intersects(r)]
            if toca:
                out.append((r, ancla, izq, max(toca)))
        return out

    def _desplazar(self, corte: float, d: int, propio: str) -> None:
        """Mueve `d` a la derecha, con operaciones del editor, todo lo que está en `corte` o a su derecha (en el dibujo).
        La referencia de cada elemento es la misma que la `ancla` de `_choques`: el centro x de una etapa, macroetapa o
        transición (así una columna entera se mueve junta, aunque su obstáculo sea una transición y no una etapa) y el
        borde izquierdo de una barra o de un grupo suelto (menos el grupo `propio`); una barra que empieza antes del corte
        y acaba después se ensancha. Las acciones de una etapa y los textos van con ella. También las vías de los enlaces
        con recorrido propio."""
        ed, pos = self.ed, posiciones(self.M)
        for i, (px, py) in pos.items():
            if px >= corte:
                ed.move(i, px - SX + d, py)
        for b in ed.bars():
            izq, ancho = Fraction(str(b["x"])), Fraction(str(b["ancho"]))
            if izq + SX >= corte:
                ed.move_bar(b["id"], izq + d, b["y"])
            elif izq + SX + ancho > corte:  # empieza antes del corte y acaba después: sigue llegando a lo que se movió
                ed.resize_bar(b["id"], izq, ancho + d)
        sueltas = {s["id"]: {"x": Fraction(str(s["x"])) + d} for s in ed.draft_actions()
                   if not s.get("etapa") and (s.get("grupo") or s["id"]) != propio and Fraction(str(s["x"])) + SX >= corte}
        if sueltas:
            ed.update_draft_actions(sueltas)
        for lid, estilo in list(ed.link_styles().items()):
            via = estilo.get("route", {}).get("laneX") if isinstance(estilo, dict) else None
            if via is not None and float(via) + SX >= corte:
                nuevo = copy.deepcopy(estilo)
                nuevo["route"]["laneX"] = str(int(float(via) + d)) if float(via) == int(float(via)) else str(float(via) + d)
                ed.set_link_style(lid, nuevo)

    def _despejar(self, clave: str) -> bool:
        """Que las acciones de la etapa (o del grupo suelto) `clave`, con la colocación elegida, no queden encima de otro
        elemento. Si ya caben, no hace nada. Si no, abre hueco: desplaza a la derecha, con sus enlaces, todo lo que empieza
        donde empieza el primer obstáculo o más allá (`_desplazar`), lo justo para dejar el margen y en pasos de rejilla, hasta
        DESPLAZA_MAX. Si no se consigue (el obstáculo está a la izquierda de la etapa o debajo de ella, o pide más de
        DESPLAZA_MAX), deshace lo desplazado y lo deja como está. Devuelve si cabe. Va dentro de una operación atómica."""
        self.reconstruir()
        disposicion = self.colocacion(clave)
        choques = self._choques(clave, disposicion)
        if not choques:
            return True
        x, _, _, suelto = self._situacion(clave)
        n, rehacer, total = len(self.ed.undo_stack), list(self.ed.redo_stack), 0
        for _ in range(DESPLAZA_PASADAS):
            corte = min(ancla for _, ancla, _, _ in choques)
            if min(izq for _, _, izq, _ in choques) < (x if suelto else x + H):
                break  # un obstáculo empieza antes que las acciones: no se aparta a la derecha
            d = math.ceil(max(derecha - r.left() for r, _, _, derecha in choques) / REJILLA) * REJILLA
            total += d
            if total > DESPLAZA_MAX:
                break
            self._desplazar(corte, d, clave)
            self.reconstruir()
            choques = self._choques(clave, disposicion)
            if not choques:
                return True
        while len(self.ed.undo_stack) > n:  # no se pudo: ningún desplazamiento a medias
            self.ed.undo()
        self.ed.redo_stack[:] = rehacer  # (lo deshecho no se puede rehacer: la pila de rehacer, como estaba)
        self.reconstruir()
        return False

    def _firmas(self) -> dict[str, tuple[Any, ...]]:
        """Por cada etapa y grupo suelto con acciones, dónde y de qué tamaño quedan sus cajas (con el modelo ya rehecho);
        cambia si se añade, se quita, se ensancha o se coloca de otro modo alguna de sus acciones."""
        out: dict[str, list[Any]] = {}
        for c in self._colocadas():
            out.setdefault(c["etapa"] or c["grupo"], []).append((c["id"], *(round(v, 1) for v in c["rect"]), *c["extra"]))
        return {k: tuple(v) for k, v in out.items()}

    def _asegurar_hueco(self, antes: dict[str, tuple[Any, ...]]) -> list[str]:
        """Tras una edición (dentro de su operación atómica): las etapas y grupos sueltos cuyas acciones cambiaron respecto a
        `antes` (`_firmas`) se despejan (`_despejar`), y también las etapas que pasan a tener acciones. Un grupo suelto que
        no estaba en `antes` (las acciones que se acaban de separar de su etapa) no se despeja: se queda donde estaba.
        Devuelve los que no se pudieron: sus acciones quedan encima de algo."""
        self.reconstruir()
        despues = self._firmas()
        etapas = {s["id"] for s in self.M["steps"]}
        return [k for k, v in despues.items()
                if (k in antes or k in etapas) and antes.get(k) != v and not self._despejar(k)]

    def _huella_arrastre(self, a: dict[str, Any]) -> list[QRectF]:
        """Las cajas de lo que se está moviendo, en su posición actual: el elemento y, de una etapa, sus acciones; de un
        grupo de acciones sueltas, cada una."""
        if a.get("tipo") == "borrador":
            return [QRectF(*c["rect"]) for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] in a["ids"]]
        if a.get("tipo") == "marco":  # el marco vacío, con su nombre debajo
            return [QRectF(a["x"] + SX, a["y"], VACIO_W, VACIO_H + 20)]
        if a.get("tipo") == "grupo":  # todo lo que se mueve: los elementos con sus acciones, las barras, las sueltas y los marcos
            moviendo = set(a["ids"])
            return [r for i, r, etapa in self._elementos() if i in moviendo or etapa in moviendo] + self._marcos_grupo(a)
        mio = [(i, r) for i, r, _ in self._elementos() if i == a["id"]]
        acciones = [QRectF(*c["rect"]) for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["etapa"] == a["id"]]
        return [r for _, r in mio] + acciones

    def _malas_arrastre(self, a: dict[str, Any]) -> list[QRectF]:
        """Las cajas de lo que se arrastra que quedan encima de otro elemento (el marco de un recinto vacío, además, no se
        pone encima del marco de otro parcial)."""
        propios = set(a["ids"]) if a.get("tipo") in ("borrador", "grupo") else {a["id"]}
        huella = self._huella_arrastre(a)
        malas = self._solapa(huella, propios)
        if a.get("tipo") == "marco" and not malas:
            otros = [QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"])
                     for pid, b in cajas_parciales(self.M).items() if pid != a["id"]]
            malas = [h for h in huella if any(self._toca(h, o) for o in otros)]
        if a.get("tipo") == "grupo" and not malas:  # los marcos vacíos que se mueven tampoco van encima del marco de otro parcial
            otros = [QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"])
                     for pid, b in cajas_parciales(self.M).items() if pid not in propios and pid not in a.get("marcos", [])]
            malas = [h for h in self._marcos_grupo(a) if any(self._toca(h, o) for o in otros)]
        return malas

    def _hay_solape(self, a: dict[str, Any]) -> bool:
        return bool(self._malas_arrastre(a))

    # -- mover varios elementos seleccionados a la vez ----------------------------------------------------------------
    def _arrastre_grupo(self, ident: str, p: QPointF, pendiente: tuple[list[str], str | None, bool]) -> dict[str, Any] | None:
        """El arrastre de lo seleccionado que se puede mover, agarrado por `ident` (uno de ellos): etapas, macroetapas,
        transiciones, barras, marcos de recintos vacíos y acciones sueltas (cada grupo suelto entero). Las acciones unidas a
        una etapa y las órdenes de forzado van con su etapa, y el marco de un parcial con etapas es el de ellas: no se
        mueven por separado. `pendiente` es la selección en que queda (selección, acción señalada, si se muestra) si se suelta
        sin haberse movido (un clic). None si `ident` no es de lo que se mueve."""
        pos = posiciones(self.M)
        inicio: dict[str, tuple[float, float]] = {}
        tipos: dict[str, str] = {}
        ids = set(self.sel)
        modelo = self.ed.model
        marcos = ids & {q["id"] for q in self.M["partials"]}
        if marcos:
            # Clausura de pertenencia: también los hijos, expansiones y recintos contenidos.
            while True:
                antes = set(ids)
                for coll in ("steps", "transitions"):
                    ids.update(x["id"] for x in modelo[coll] if x["partialRef"] in ids)
                for x in modelo["hierarchy"]["macros"]:
                    if x["partialRef"] in ids:
                        ids.add(x["id"])
                for x in modelo["hierarchy"]["expansions"]:
                    if x["ownerMacroRef"] in ids:
                        ids.add(x["partialRef"])
                for x in modelo["hierarchy"]["enclosures"]:
                    if x["ownerStepRef"] in ids:
                        ids.add(x["partialRef"])
                ids.update(q["id"] for q in modelo["partials"] if q.get("ownerRef") in ids)
                ids.update(n["id"] for n in self.M.get("annotations",[]) if n.get("partialRef") in ids)
                if ids == antes:
                    break
            cajas = cajas_parciales(self.M)
            zonas = [QRectF(cajas[i]["x0"], cajas[i]["y0"], cajas[i]["x1"] - cajas[i]["x0"],
                            cajas[i]["y1"] - cajas[i]["y0"]) for i in marcos if i in cajas]
            for bid, r, etapa in self._elementos():
                if any(z.contains(r) for z in zonas):
                    if self._barra(bid) or (self._es_borrador(bid) and not self._borrador(bid).get("etapa")):
                        ids.add(bid)
        for i in sorted(ids):
            if n := self.anotacion(i):
                inicio[i],tipos[i]=(n["x"],n["y"]),"anotacion"
            elif i in pos:
                inicio[i], tipos[i] = (pos[i][0] - SX, pos[i][1]), "nodo"
            elif (b := self._barra(i)) is not None:
                inicio[i], tipos[i] = (b["x"], b["y"]), "barra"
            elif (q := next((q for q in self.M["partials"] if q["id"] == i and q.get("vacio")), None)) is not None:
                inicio[i], tipos[i] = (q["x"], q["y"]), "marco"
            elif self._es_borrador(i) and not self._borrador(i).get("etapa"):
                grupo = self._ids_grupo(i)
                for j in grupo:
                    inicio[j], tipos[j] = self._pos_borrador(self._borrador(grupo[0])), "suelta"
        if ident in inicio:
            x0, y0 = inicio[ident]
        elif inicio and (caja := cajas_parciales(self.M).get(ident)) is not None:
            # El lazo selecciona también el marco con contenido. Agarrarlo mueve sus elementos una sola vez;
            # el marco deriva de ellos y no lleva una segunda posición independiente.
            x0, y0 = next(iter(inicio.values()))
        else:
            return None
        return {"id": ident, "tipo": "grupo", "ids": list(inicio), "inicio": inicio, "tipos": tipos, "start": p,
                "dx": p.x() - (x0 + SX), "dy": p.y() - y0, "x": x0, "y": y0, "x0": x0, "y0": y0, "movido": False,
                "pendiente": pendiente, "marcos": list(ids & {q["id"] for q in self.M["partials"]})}

    def _marcos_grupo(self, a: dict[str, Any]) -> list[QRectF]:
        """Dónde quedan, en el dibujo, los marcos vacíos que se mueven con el grupo (con su nombre debajo)."""
        dx, dy = a["x"] - a["x0"], a["y"] - a["y0"]
        return [QRectF(x + dx + SX, y + dy, VACIO_W, VACIO_H + 20) for i, (x, y) in a["inicio"].items() if a["tipos"][i] == "marco"]

    @staticmethod
    def _sumar(valor: Any, d: float) -> Any:
        """Un valor de coordenada del estilo de un enlace (un texto) con `d` más; sin cambio si no es un número."""
        try:
            v = float(valor) + d
        except (TypeError, ValueError):
            return valor
        return str(int(v)) if v == int(v) else str(v)

    def _rutas_con_grupo(self, ids: set[str], dx: float, dy: float) -> dict[str, dict[str, Any]]:
        """El estilo nuevo de los enlaces con sus dos extremos en `ids` (lo que se mueve): su recorrido manual, en coordenadas
        absolutas (laneX, exitY, entryY, middleY), se desplaza con ellos. Los de un solo extremo movido se quedan como están,
        igual que al mover un elemento con `Editor.move`."""
        out: dict[str, dict[str, Any]] = {}
        for lid, estilo in self.ed.link_styles().items():
            extremos = lid.split("|")[:2]
            ruta = estilo.get("route") if isinstance(estilo, dict) else None
            if isinstance(ruta, dict) and len(extremos) == 2 and all(e in ids for e in extremos):
                nuevo = copy.deepcopy(estilo)
                for clave, d in (("laneX", dx), ("exitY", dy), ("entryY", dy), ("middleY", dy)):
                    if clave in nuevo["route"]:
                        nuevo["route"][clave] = self._sumar(nuevo["route"][clave], d)
                out[lid] = nuevo
        return out

    def mover_teclado(self, dx, dy):
        if not self.sel: return False
        a = self._arrastre_grupo(self.sel[0], QPointF(), (list(self.sel), self.accion, self.ver_accion))
        if a is None: return False
        a.update(x=a['x0']+dx, y=a['y0']+dy, movido=True)
        return self._soltar_grupo(a, unir=False)  # con las flechas no se une solo: es un ajuste fino

    def _soltar_grupo(self, a: dict[str, Any], unir: bool = True) -> bool:
        """Termina el arrastre de varios seleccionados: sin haberse movido (un clic), la selección se queda en el elemento
        pulsado; encima de algo que no se mueve, vuelven a su sitio; si no, se mueven todos con una sola operación de
        deshacer, con las rutas de los enlaces entre ellos."""
        self._marcar_solape(None)
        if not a["movido"]:
            self.sel, self.accion, self.ver_accion = a["pendiente"]
        elif (a["x"], a["y"]) != (a["x0"], a["y0"]):
            if self._hay_solape(a):
                return self._devolver()
            dx, dy = a["x"] - a["x0"], a["y"] - a["y0"]
            with self.ed.group("mover"):
                self.ed.move_many({i: (x + dx, y + dy) for i, (x, y) in a["inicio"].items()},
                                  self._rutas_con_grupo(set(a["ids"]), dx, dy))
                if unir:
                    self._unir_cercanos(set(a["ids"]))
        self.cambia()
        return True

    def _marcar_solape(self, a: dict[str, Any] | None) -> None:
        """Mientras se arrastra `a`: en rojo (y con el cursor de prohibido) lo que no se puede colocar donde está; sin
        arrastre (None), lo quita."""
        if self.diagrama is None or not hasattr(self.diagrama, "marcar_prohibido"):
            return
        malas = self._malas_arrastre(a) if a else []
        self.diagrama.marcar_prohibido(malas or None)

    def _devolver(self) -> bool:
        """Termina un arrastre que quedó encima de otro elemento: no se mueve; vuelve a su sitio con el aviso."""
        self._marcar_solape(None)
        self.informar(MSG_SOLAPE)
        self.cambia()
        return True

    def _huella_ficha(self, tipo: str, p: QPointF) -> list[QRectF]:
        """Las cajas, ya solapadas con otro elemento, de lo que se colocaría al soltar una ficha de la paleta en p (vacío si
        cabe: una acción que se pega a otra no cuenta)."""
        x, y = self._modelo(p)
        if tipo in ("texto","imagen"):return []
        if tipo in ("etapa", "etapa_inicial", "encapsulante", "macroetapa"):
            caja = QRectF(x + SX - H, y - H, 2 * H, 2 * H)
        elif tipo == "transicion":
            caja = QRectF(x + SX - TB, y - 2, 2 * TB, 4)
        elif tipo in ("simultaneidad", "simultaneidad:apertura", "simultaneidad:cierre"):
            caja = QRectF(ajustar(x - 60) + SX, y, 120, 4)
        elif tipo == "parcial":  # su marco vacío con el nombre debajo: ni encima de un elemento ni (con un margen) de otro marco
            x0, y0 = self._esquina_parcial(p)
            caja = QRectF(x0 + SX, y0, VACIO_W, VACIO_H + 20)
            m = MARGEN_SOLAPE
            otros = [QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"]) for b in cajas_parciales(self.M).values()]
            return self._solapa([caja], set()) or ([caja] if any(self._toca(caja.adjusted(-m, -m, m, m), o) for o in otros) else [])
        elif tipo == "accion" or tipo.startswith("accion:") or tipo == "forzado":
            if self._buscar_iman([], x, y, ACT_MIN):
                return []
            caja = QRectF(x + SX, y - H, ACT_MIN, 2 * H)
        else:
            return []
        return self._solapa([caja], set())

    def _enlace_del_punto(self, origen: dict[str, Any], destino: dict[str, Any]) -> str | None:
        """Soltar la salida de una transición sobre la salida de otra que ya tiene su etapa siguiente (o la entrada sobre la
        entrada de una que ya tiene su etapa anterior) es unirse a ese enlace, como si se soltara sobre él: una convergencia
        (O) en esa etapa. Cerca del tallo de la transición, su punto de unión gana al enlace que sale de él (P-IMP-118).
        Devuelve el ID de ese enlace, o None si no es el caso (entonces son dos transiciones seguidas: un borrador)."""
        ts = {t["id"] for t in self.M["transitions"]}
        if origen["id"] not in ts or destino["id"] not in ts or origen["lado"] != destino["lado"]:
            return None
        rol = {"abajo": "post", "arriba": "pre"}.get(origen["lado"])
        propios = [e["id"] for e in enlaces(self.M) if e["tid"] == destino["id"] and e["rol"] == rol]
        return propios[0] if rol and len(propios) == 1 else None

    def unir_a_enlace(self, origen: dict[str, Any], enlace: str) -> None:
        """Arrastrar de un punto de unión al **enlace** de una transición con su etapa siguiente construye una rama
        (alternativa, O) que se une ahí: de una transición, su etapa siguiente pasa a ser la de ese enlace (la rama
        vuelve y lleva flecha hacia abajo); de una etapa, un salto de secuencia: una transición nueva de la etapa a
        la que llega el enlace, por el lado."""
        tid, sid, rol = enlace.split("|")
        src = origen["id"]
        recibe = origen["lado"] == "arriba"
        if recibe and rol == "pre":
            if any(t["id"] == src for t in self.M["transitions"]):
                self.conectar(sid, src)
            elif src != sid:
                self.saltar(sid, src)
            return
        if not recibe and rol == "pre" and src in self._pasos():  # una etapa a una transición que ya tiene etapa anterior
            if src == sid:
                self.rechazar("Una etapa no puede llegar a la transición que sale de ella.", src)
                self.cambiado.emit()
            else:
                self.borrador_simultaneidad(src, tid)
        elif recibe or rol != "post":
            self.rechazar("Una rama se une a un enlace que llega a una etapa (de una transición a su etapa siguiente).",
                          src, enlace)
            self.cambiado.emit()
        elif any(t["id"] == src for t in self.M["transitions"]):
            self.conectar(src, sid)
        elif src == sid:
            self.rechazar("Una etapa no salta a sí misma.", src)
            self.cambiado.emit()
        elif src in self._pasos():
            self.saltar(src, sid)

    def crear_desde(self, origen: dict[str, Any], p: QPointF) -> str | None:
        """Arrastrar de un punto de unión a un hueco crea lo que sigue y lo enlaza: de una etapa, una transición (una rama
        nueva si ya tenía otra); de una transición, una etapa. Hacia arriba, lo que va antes."""
        base, abajo = origen["id"], origen["lado"] == "abajo"
        x, y = self._modelo(p)
        es_paso = base in self._pasos()  # una macroetapa se enlaza como una etapa
        t = next((t for t in self.ed.model["transitions"] if t["id"] == base), None)
        if t is not None and t["postRefs" if abajo else "preRefs"]:
            self.rechazar(f"«{self._nom(base)}» ya tiene una etapa {'siguiente' if abajo else 'anterior'}: "
                          "para otra más hace falta una simultaneidad (elemento de la paleta); para una alternativa, "
                          "abra la rama desde la etapa.", base)
            self.cambiado.emit()
            return None
        if not es_paso and t is None:
            self.rechazar("De una barra se enlaza con las etapas y transiciones existentes.", base)
            self.cambiado.emit()
            return None
        ed, parcial = self.ed, self.parcial_de(base)  # lo que nace de un elemento es de su parcial
        with ed.group("abrir rama"):
            if es_paso:
                nuevo, _ = ed.add_transition(parcial, "", [base] if abajo else [], [] if abajo else [base], at=(x, y),
                                             label=ed.next_label("transition"))
            else:
                nuevo = ed.add_step(parcial, ed.next_label("step"), at=(x, y))
                ed.connect(base, nuevo) if abajo else ed.connect(nuevo, base)
            self._unir_cercanos({nuevo})  # y, si su otro punto queda muy cerca de uno libre compatible, también se une (P-IMP-114)
        self.sel = [nuevo]
        self.informar("Rama abierta: " + ("escriba la receptividad en las propiedades (doble clic en la transición)." if es_paso else "etapa nueva."))
        self.cambia()
        return nuevo

    def _ocupado(self, x: float, y: float, margen: float = 45) -> bool:
        """Si ya hay una etapa, macroetapa o transición a menos de `margen` del punto del modelo (x, y), a lo ancho y a lo alto
        (para no colocar encima una transición nueva)."""
        return any(abs(px - SX - x) < margen and abs(py - y) < margen for px, py in posiciones(self.M).values())

    def enlazar_etapas(self, origen: dict[str, Any], destino: dict[str, Any]) -> None:
        """Arrastrar de una etapa a otra etapa existente las une **con una transición nueva en medio** (receptividad
        pendiente): del punto de abajo de la que se arrastra a la otra, o, si se arrastra del punto de arriba, de la otra a
        ella. Si la otra queda debajo con sitio entre las dos, la transición va en medio; si queda al mismo nivel o encima
        es un salto o una repetición de secuencia (`saltar`), con su enlace de retorno."""
        ini, fin = (origen["id"], destino["id"]) if origen["lado"] == "abajo" else (destino["id"], origen["id"])
        if ini == fin:
            self.rechazar("Una etapa no salta a sí misma.", ini)
            self.cambiado.emit()
            return
        pos = posiciones(self.M)
        ty = ajustar((pos[ini][1] + pos[fin][1]) / 2)
        tx = pos[ini][0] - SX
        if pos[fin][1] - pos[ini][1] < 2 * DY or self._ocupado(tx, ty):
            self.saltar(ini, fin)
            return
        tid, _ = self.ed.add_transition(self.parcial_de(ini), "", [ini], [fin], at=(tx, ty),
                                        label=self.ed.next_label("transition"))
        self.sel = [tid]
        self.informar("Transición nueva entre las dos etapas: escriba su receptividad en las propiedades (doble clic en ella).")
        self.cambia()

    def saltar(self, origen: str, destino: str) -> str:
        """Salto de secuencia: una transición nueva (receptividad pendiente) de la etapa origen a la etapa destino, junto
        a las transiciones que se saltan."""
        pos = posiciones(self.M)
        x = min(pos[origen][0], pos[destino][0]) - SX - 160
        ocupados = {tuple(p) for p in self.layout().values()}
        y = ajustar(pos[origen][1] + DY)
        while (x, y) in ocupados:
            x -= 160
        tid, _ = self.ed.add_transition(self.parcial_de(origen), "", [origen], [destino], at=(x, y),
                                        label=self.ed.next_label("transition"))
        self.sel = [tid]
        tipo = "Repetición de secuencia" if pos[destino][1] <= pos[origen][1] else "Salto de secuencia"
        self.informar(tipo + ": escriba su receptividad en las propiedades (doble clic en ella).")
        self.cambia()
        return tid

    def _lado_en_barra(self, barra_: dict[str, Any], otro: dict[str, Any]) -> str:
        """Por qué lado de la barra queda unido el elemento `otro`: lo da su punto de unión, no la punta de la barra elegida ni
        dónde está dibujado. El punto de abajo del elemento emite hacia la barra (queda por `arriba` de ella) y el de arriba
        recibe de la barra (queda por `abajo`). Así una etapa encima de la barra se une por arriba si se arrastra desde su
        salida, aunque se suelte en la punta inferior de la barra (P-IMP-125), y por abajo si se arrastra a su entrada
        (un retorno o una divergencia hacia atrás, que se dibuja cruzando la barra). Sin punto de arriba o de abajo, manda la
        punta de la barra."""
        return {"abajo": "arriba", "arriba": "abajo"}.get(otro["lado"], barra_["lado"])

    def unir(self, origen: dict[str, Any], destino: dict[str, Any]) -> None:
        """Enlaza dos puntos de unión. Manda el punto del que se arrastra: el de abajo emite el enlace (va hacia el otro
        elemento) y el de arriba lo recibe (viene del otro). Si el enlace queda de abajo arriba, se dibuja con flecha. Con una
        barra, el lado lo da el punto de unión del elemento: el de abajo emite hacia la barra (queda por arriba de ella) y el de
        arriba recibe de ella (queda por abajo), sea cual sea la punta de la barra elegida y dónde esté dibujado
        (`_lado_en_barra`)."""
        if {origen["lado"], destino["lado"]} & {"izq", "der"}:  # una acción suelta con una etapa
            acc = next((x for x in (origen, destino) if x["lado"] == "izq"), None)
            otro = destino if acc is origen else origen
            if acc is not None and otro["lado"] != "izq" and any(s["id"] == otro["id"] for s in self.M["steps"]):
                self.unir_accion(acc["id"], otro["id"])
            else:
                self.rechazar("Una acción se une a una etapa, no a una transición, una barra ni otra acción.",
                              origen["id"], destino["id"])
                self.cambiado.emit()
            return
        ba, bb = self._barra(origen["id"]), self._barra(destino["id"])
        if ba and bb:
            self.rechazar("Una barra no se une a otra barra.", origen["id"], destino["id"])
            self.cambiado.emit()
        elif ba or bb:
            barra_, otro = (origen, destino) if ba else (destino, origen)
            lado = self._lado_en_barra(barra_, otro)
            try:
                diag = self.ed.bar_link(barra_["id"], lado, otro["id"])
                self.mensaje = f"{diag.code}: {self.sust(diag.message)}" if diag else ""
                if lado != barra_["lado"] and not diag:
                    self.informar(f"«{self._nom(otro['id'])}» {'sale hacia la barra' if lado == 'arriba' else 'recibe de la barra'}: "
                                  f"se ha unido por {'arriba' if lado == 'arriba' else 'abajo'}.")
            except DiagnosticError as exc:
                self.rechazar("; ".join(self.sust(d.message) for d in exc.diagnostics), barra_["id"], otro["id"])
            self.cambia()
        elif origen["id"] in self._pasos() and destino["id"] in self._pasos():
            self.enlazar_etapas(origen, destino)  # de etapa a etapa, siempre con una transición en medio
        elif origen["lado"] == "abajo":  # el punto de abajo emite el enlace
            self.conectar(origen["id"], destino["id"], borrador=True)
        else:  # el punto de arriba lo recibe: se arrastra de la entrada de un elemento a lo que va antes
            self.conectar(destino["id"], origen["id"], borrador=True)

    def explicito(self, f: Callable[..., Any], *args: Any) -> Any:
        """Ejecuta una petición de opciones hecha por el usuario: el panel inferior se despliega aunque esté plegado
        (P-IMP-118). Las peticiones que salen de otras operaciones (una acción nueva, una transición recién soltada)
        no lo abren si está plegado."""
        self.pedido_explicito = True
        try:
            return f(*args)
        finally:
            self.pedido_explicito = False

    def doble(self, p: QPointF, event: Any = None) -> bool:
        return self.explicito(self._doble, p, event)

    def _doble(self, p: QPointF, event: Any = None) -> bool:
        if n := self.anotacion(elemento_en(self.M,p)):
            self.editar_anotacion(n["id"]);return True
        caja = self.accion_en(p)
        if caja:  # doble clic en una acción: se edita (una orden sin completar, con el diálogo de la orden)
            if caja.get("forzado"):
                self.configurar_orden(caja["id"])
            else:
                self.pedir_accion(caja["etapa"] or None, caja["id"])
            return True
        orden = self.orden_en(p)
        if orden:  # doble clic en una orden de forzado: se edita (el mismo diálogo que «Editar orden de forzado…»)
            self.editar_orden(orden["id"])
            return True
        ident = elemento_en(self.M, p)
        if not ident:
            return False
        if any(t["id"] == ident for t in self.M["transitions"]):
            self.pedir_condicion(ident)
        elif any(s["id"] == ident for s in self.M["steps"]):
            self.pedir_etiqueta(ident)
        elif any(x["id"] == ident for x in self.M.get("macros", [])):  # doble clic en una macroetapa: encuadra su expansión
            self.encuadrar_expansion(ident)
        elif ident in cajas_parciales(self.M) and self._es_parcial_suelto(ident):  # en el marco de un parcial suelto: lo renombra
            self.renombrar_parcial(ident)
        return True

    # -- acciones (P-IMP-38, P-IMP-41, P-IMP-43) ---------------------------------------------------------------
    # Una acción unida a una etapa y completa es una acción del modelo. Una suelta, o unida a una etapa pero sin
    # variable (o sin el valor, la condición, el evento o el límite que su tipo pide), es un borrador de la presentación
    # (grafcet/editor.py, `draft_actions`): se dibuja como cualquier acción, con «?» en lo que falta, y no se simula.
    # Varias acciones sueltas pegadas forman un grupo (`grupo` y `orden` del borrador) que se mueve y se une junto.
    def accion_en(self, p: QPointF) -> dict[str, Any] | None:
        """La caja de acción bajo el puntero, tal como quedó en el dibujo ({id, etapa, rect, borrador, suelta, grupo,
        cabeza})."""
        for c in getattr(self.diagrama, "cajas_acciones", None) or []:
            x, y, w, h = c["rect"]
            if x <= p.x() <= x + w and y <= p.y() <= y + h:
                return c
        return None

    def orden_en(self, p: QPointF) -> dict[str, Any] | None:
        """La caja de la orden de forzado bajo el puntero, tal como quedó en el dibujo ({id, etapa, rect})."""
        for c in getattr(self.diagrama, "cajas_ordenes", None) or []:
            x, y, w, h = c["rect"]
            if x <= p.x() <= x + w and y <= p.y() <= y + h:
                return c
        return None

    def union_en(self, p: QPointF) -> str | None:
        """El enlace de una etapa con sus acciones bajo el puntero («enlaceacc:ID de la etapa»), tal como quedó dibujado."""
        for u in getattr(self.diagrama, "uniones_acciones", None) or []:
            for tramo in u["trazos"]:
                if any(_distancia(p, a, b) <= 6 for a, b in zip(tramo, tramo[1:])):
                    return u["id"]
        return None

    def _es_borrador(self, ident: str | None) -> bool:
        return any(b["id"] == ident for b in self.ed.draft_actions())

    def _borrador(self, did: str) -> dict[str, Any]:
        return next(b for b in self.ed.draft_actions() if b["id"] == did)

    def _borradores_ordenados(self) -> list[dict[str, Any]]:
        """Los borradores en el orden en que se dibujan dentro de su etapa o de su grupo: por `orden`; los que no lo tienen,
        por orden de creación y después de los que sí."""
        crudos = self.ed.draft_actions()
        return [b for _, b in sorted(enumerate(crudos), key=lambda t: (t[1].get("orden", 10 ** 6 + t[0]), t[0]))]

    def _ids_grupo(self, did: str) -> list[str]:
        """Una acción suelta y las que lleva pegadas (su grupo), en orden; una unida a una etapa, solo ella."""
        b = self._borrador(did)
        if b.get("etapa") or not b.get("grupo"):
            return [did]
        return [x["id"] for x in self._borradores_ordenados() if x.get("grupo") == b["grupo"] and not x.get("etapa")]

    @staticmethod
    def _pos_borrador(b: dict[str, Any]) -> tuple[float, float]:
        return float(Fraction(str(b["x"]))), float(Fraction(str(b["y"])))

    def _etiqueta_etapa(self, sid: str | None) -> str:
        return next((s["label"] for s in self.ed.model["steps"] if s["id"] == sid), "")

    def _nombre_variable(self, vid: str | None) -> str:
        v = next((v for v in self.ed.model["variables"] if v["id"] == vid), None) if vid else None
        return v["name"] if v else ""

    def _datos_borrador(self, b: dict[str, Any]) -> dict[str, str]:
        """Un borrador en la notación del usuario, con los mismos campos que `datos_accion` (vacío: lo que falta). Una
        «continua» con condición (de una versión anterior) es una condicionada."""
        d = {"tipo": b["tipo"], "variable": self._nombre_variable(b.get("variable")),
             **{k: b.get(k, "") for k in ("condicion", "valor", "evento", "limite")}}
        if d["tipo"] == "continua" and d["condicion"].strip():
            d["tipo"] = "condicionada"
        return d

    def seleccion_dibujo(self) -> set[str]:
        """Lo que se resalta en el dibujo: la selección y la acción señalada (también las acciones seleccionadas)."""
        etapa = {a["id"]: a["stepRef"] for a in self.ed.model["actions"]}
        etapa.update({b["id"]: b.get("etapa") for b in self.ed.draft_actions()})
        etapa.update({f["id"]: f["sourceStepRef"] for f in self.ed.model["forces"]})  # una orden seleccionada se resalta en su caja
        señalada = {self.accion} if self.accion in etapa and etapa[self.accion] in self.sel else set()
        seleccion = set(self.sel)
        if señalada and self._accion_para_quitar():
            seleccion.discard(etapa[self.accion])
        return seleccion | {f"accion:{i}" for i in (señalada | (set(self.sel) & set(etapa)))}

    def _parcial_borrador(self, b: dict[str, Any]) -> str:
        """El parcial en cuyo ámbito se leen los textos de un borrador: el de su etapa (el raíz, si está suelto)."""
        return self.parcial_de(b["etapa"]) if b.get("etapa") else self.raiz

    def _texto_valido(self, texto: str, parcial: str | None = None) -> bool:
        """Si una condición o un evento escritos se interpretan (no están vacíos, ni a medias, ni usan variables que no
        existen), con los nombres del parcial dado (por defecto, el raíz)."""
        texto = texto.strip()
        return bool(texto) and self.ed.check_expression(self._n(texto), parcial or self.raiz) is None

    def faltan(self, d: dict[str, str], parcial: str | None = None) -> list[str]:
        """Lo que le falta a una acción (datos como `datos_accion`) para ser del modelo: la variable (o una booleana, si
        es continua), la condición de una condicionada, el valor de una memorizada, el evento de una por evento y el límite
        de una limitada. Una condición o un evento a medias (con huecos, o con variables que no existen) cuentan como
        faltantes. Sus textos se leen en el ámbito del `parcial` de la etapa de la acción (por defecto, el raíz)."""
        nombre, t = d.get("variable", "").strip(), d["tipo"]
        var = next((v for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None
        out = []
        if var is None or (t in CONTINUAS and var["type"]["kind"] != "bool"):
            out.append("variable")
        cond = d.get("condicion", "").strip()
        if (t == "condicionada" and not self._texto_valido(cond, parcial)) or (t == "limitada" and cond and not self._texto_valido(cond, parcial)):
            out.append("condición")  # la limitada puede no llevar condición, pero si la lleva ha de interpretarse
        if t in DISPARADOR and not d.get("valor", "").strip():
            out.append("valor")
        if t == "evento" and not self._texto_valido(d.get("evento", ""), parcial):
            out.append("evento")
        if t == "limitada" and not normalizar_duracion(d.get("limite", "")):
            out.append("límite")
        return out

    def _segmentos(self, texto: str, nombres: dict[str, str], top: bool = False) -> list[dict[str, Any]] | None:
        """Una condición, un valor o un evento escritos por el usuario, en la notación de la norma; el texto tal cual si no
        se interpreta; None si está vacío."""
        texto = texto.strip()
        if not texto:
            return None
        try:
            meaning, diag = self.ed._make_expr(self.ed.model, self._n(texto), None)
        except Exception:  # noqa: BLE001 - un texto a medias no debe romper el dibujo
            return [{"t": texto}]
        return [{"t": texto}] if diag is not None else norm(meaning["meaning"], top, nombres)

    def _borradores(self) -> list[dict[str, Any]]:
        """Los borradores como los dibuja Vista (con el arrastre en curso aplicado), en el orden de su etapa o su grupo: lo
        mismo que una acción del modelo, con «?» en lo que falta. Las de un grupo suelto comparten la posición de la
        primera."""
        try:
            nombres = display_names(self.ed.model)
        except (KeyError, TypeError, AttributeError):
            nombres = {}
        a = self.arrastre
        movidos = set(a["ids"]) if a and a.get("tipo") == "borrador" else set()
        en_grupo = {i: (x + a["x"] - a["x0"], y + a["y"] - a["y0"]) for i, (x, y) in a["inicio"].items()
                    if a["tipos"][i] == "suelta"} if a and a.get("tipo") == "grupo" else {}
        ordenados = self._borradores_ordenados()
        primeras: dict[str, dict[str, Any]] = {}
        for b in ordenados:
            if b.get("grupo") and not b.get("etapa"):
                primeras.setdefault(b["grupo"], b)
        out = []
        for b in ordenados:
            d = self._datos_borrador(b)
            suelta = not b.get("etapa")
            primera = primeras.get(b["grupo"], b) if suelta and b.get("grupo") else b
            x, y = self._pos_borrador(primera)
            if b["id"] in movidos:
                x, y = a["x"], a["y"]
            elif b["id"] in en_grupo:
                x, y = en_grupo[b["id"]]
            if b["tipo"] == "forzado":  # una orden de forzado sin completar: su rectángulo doble con «G?{?}» hasta configurarla
                out.append({"id": b["id"], "x": x, "y": y, "etapa": b.get("etapa"), "borrador": True, "grupo": b.get("grupo"),
                            "cabeza": suelta and primera["id"] == b["id"], "target": b.get("destino"), "condRef": None,
                            "falta": self._faltan_orden(b), "kind": "force", "text": [{"t": self._texto_orden(b, nombres)}]})
                continue
            var = d["variable"] or "?"
            item: dict[str, Any] = {"id": b["id"], "x": x, "y": y, "etapa": b.get("etapa"), "borrador": True,
                                    "grupo": b.get("grupo"), "cabeza": suelta and primera["id"] == b["id"],
                                    "target": None, "condRef": None, "falta": self.faltan(d, self._parcial_borrador(b))}
            if d["tipo"] in CONTINUAS:
                cond = d["condicion"].strip()
                if cond in ("1", "true"):
                    cond = ""
                segmentos = self._segmentos(cond, nombres, True) if cond else None
                if d["tipo"] == "condicionada" and not cond:
                    segmentos = [{"t": "?"}]
                if d["tipo"] == "limitada":  # el límite se dibuja como en la norma: una condición más, NOT d/X
                    xe = x_etapa(self._etiqueta_etapa(b.get("etapa"))) if b.get("etapa") else "X?"
                    lim = f"NOT {d['limite'] or '?'}/{xe}"
                    segmentos = self._segmentos(f"({cond}) AND {lim}" if cond else lim, nombres, True)
                item.update(kind="continuous", text=[{"t": var}], cond=segmentos)
            else:
                valor = self._segmentos(d["valor"], nombres) or [{"t": "?"}]
                item.update(kind="stored", trigger=DISPARADOR[d["tipo"]], text=[{"t": f"{var} := "}] + valor,
                            event=(self._segmentos(d["evento"], nombres) or [{"t": "?"}]) if d["tipo"] == "evento" else None)
            out.append(item)
        return out

    # -- pegar acciones y mover grupos
    def _colocacion_de(self, caja: dict[str, Any]) -> str:
        """La colocación de la etapa o del grupo al que pertenece una acción dibujada (una suelta sin grupo, en fila)."""
        clave = caja["etapa"] or caja.get("grupo") or ""
        return self.colocacion(clave) if clave else "fila"

    def _buscar_iman(self, ids: list[str], x: float, y: float, ancho: float | None = None) -> dict[str, Any] | None:
        """Si una acción suelta (la primera de `ids`, con su lado izquierdo en el punto del modelo (x, y)) toca el lado
        derecho de otra acción, o el inferior si va en columna, a menos de IMAN_ACCION: la acción a cuya espalda se pegaría
        ({objetivo, lado, linea: el lado que se resalta}). Las acciones de `ids` no cuentan."""
        cajas = [*(getattr(self.diagrama, "cajas_acciones", None) or []), *(getattr(self.diagrama, "cajas_ordenes", None) or [])]
        if ancho is None:
            propia = next((c for c in cajas if ids and c["id"] == ids[0]), None)
            ancho = propia["rect"][2] if propia else ACT_MIN
        izq, arriba = x + SX, y - H
        mejor: tuple[float, dict[str, Any]] | None = None
        for c in cajas:
            if c["id"] in ids:
                continue
            tx, ty, tw, th = c["rect"]
            candidatos = []
            dx, dy = abs(izq - (tx + tw)), abs(y - (ty + th / 2))
            if dx <= IMAN_ACCION and dy <= H:  # al lado derecho
                candidatos.append((dx + dy, "der", (QPointF(tx + tw, ty), QPointF(tx + tw, ty + th))))
            hueco = arriba - (ty + th)
            if self._colocacion_de(c) == "columna" and -IMAN_ACCION <= hueco <= IMAN_ACCION + 12 and abs(izq - tx) <= tw / 2:
                candidatos.append((abs(hueco) + abs(izq - tx), "abajo", (QPointF(tx, ty + th), QPointF(tx + tw, ty + th))))
            for puntos, lado, linea in candidatos:
                if mejor is None or puntos < mejor[0]:
                    mejor = (puntos, {"objetivo": c["id"], "lado": lado, "linea": linea})
        return mejor[1] if mejor else None

    def sobrevolar(self, ficha: str, p: QPointF) -> bool:
        """Una ficha que se arrastra desde la paleta pasa por encima del dibujo: una acción resalta el lado de la acción donde
        se pegaría al soltarla; si quedaría encima de otro elemento se ve en rojo y no se puede soltar (devuelve False). Una orden de
        forzado, sobre una etapa (o junto a su fila de acciones), resalta la etapa a la que se uniría; en otro sitio, como una acción."""
        if self.diagrama is None:
            return True
        if ficha == "forzado" and (sid := self._etapa_para_orden(p)) is not None:
            if hasattr(self.diagrama, "marcar_destino"):
                x, y = posiciones(self.M)[sid]
                self.diagrama.marcar_destino({"x0": x - H, "y0": y - H, "x1": x + H, "y1": y + H})
            self.diagrama.marcar_iman(None)
            if hasattr(self.diagrama, "marcar_prohibido"):
                self.diagrama.marcar_prohibido(None)
            return True
        iman = None
        if ficha == "accion" or ficha.startswith("accion:") or ficha == "forzado":
            x, y = self._modelo(p)
            iman = self._buscar_iman([], x, y, ACT_MIN)
        malas = self._huella_ficha(ficha, p)
        aviso = MSG_SOLAPE_PARCIAL if ficha == "parcial" else MSG_SOLAPE
        if malas and self.mensaje != aviso:
            self.informar(aviso)
            self.cambiado.emit()  # (vuelve a dibujar: las marcas se ponen después)
        elif not malas and self.mensaje == aviso:  # ya está sobre un hueco: el aviso no sigue diciendo lo contrario
            self.mensaje = ""
            self.cambiado.emit()
        if hasattr(self.diagrama, "marcar_destino"):  # lo que tiene parcial se recuadra en el marco donde caería (no en el raíz)
            cae = ficha in ("etapa", "encapsulante", "macroetapa", "transicion") and not malas
            self.diagrama.marcar_destino(cajas_parciales(self.M).get(self.parcial_en(p)) if cae else None)
        self.diagrama.marcar_iman(iman["linea"] if iman else None)
        if hasattr(self.diagrama, "marcar_prohibido"):
            self.diagrama.marcar_prohibido(malas or None)
        return not malas

    def mover_grupo(self, ids: list[str], x: float, y: float, unir: bool = False) -> None:
        """Mueve una acción suelta, con las que lleva pegadas, a la posición del modelo (x, y): una operación de deshacer.
        Con `unir` (al soltarla con el ratón), si su punto de unión queda muy cerca del de una etapa, se une a ella."""
        with self.ed.group("mover"):
            self.ed.update_draft_actions({i: {"x": x, "y": y} for i in ids})
            if unir:
                self._unir_cercanos(set(ids))
        self.cambia()

    def _pegar_a_grupo(self, ids: list[str], objetivo: dict[str, Any]) -> None:
        """Pega las acciones sueltas `ids` (en orden) detrás de la suelta `objetivo`: en su grupo, que se crea si era una sola."""
        g = objetivo.get("grupo") or self.ed.ids.new("grupo")
        previos = self._ids_grupo(objetivo["id"]) if objetivo.get("grupo") else [objetivo["id"]]
        x, y = self._pos_borrador(self._borrador(previos[0]))
        previos = [i for i in previos if i not in ids]
        k = previos.index(objetivo["id"]) + 1
        orden = previos[:k] + list(ids) + previos[k:]
        self.ed.update_draft_actions({i: {"grupo": g, "orden": n, "x": x, "y": y, "etapa": None} for n, i in enumerate(orden)})

    def _pegar_a_etapa(self, ids: list[str], sid: str, objetivo: str | None) -> list[str]:
        """Une las acciones sueltas `ids` (en orden) a la etapa, detrás de la acción `objetivo` (al final, sin objetivo). Las
        completas pasan al modelo (se devuelven sus ID, también el de una orden de forzado completa); las demás quedan como
        borradores unidos a la etapa."""
        previos = [b["id"] for b in self._borradores_ordenados() if b.get("etapa") == sid and b["id"] not in ids]
        k = previos.index(objetivo) + 1 if objetivo in previos else 0 if objetivo else len(previos)
        orden = previos[:k] + list(ids) + previos[k:]
        self.ed.update_draft_actions({i: {"etapa": sid, "grupo": None, "orden": n} for n, i in enumerate(orden)})
        promovidas, ordenes = [], []
        for did in ids:
            es_orden = self.es_orden_suelta(did)
            if self._completar(did):  # (una orden completa pasa a `forces`, no a las acciones de la etapa)
                if es_orden:
                    ordenes.append(self.ed.model["forces"][-1]["id"])
                else:
                    promovidas.append(self.ed.get(sid)["actionRefs"][-1])
        refs = self.ed.get(sid)["actionRefs"]
        if promovidas and objetivo in refs:  # detrás de la acción del modelo a cuya espalda se pegó
            final = [r for r in refs if r not in promovidas]
            final[final.index(objetivo) + 1:final.index(objetivo) + 1] = promovidas
            for n, aid in enumerate(final):
                actual = self.ed.get(sid)["actionRefs"].index(aid)
                if actual != n:
                    self.ed.move_action(aid, n - actual)
        return promovidas + ordenes

    def _pegar(self, ids: list[str], objetivo: str) -> tuple[str | None, list[str]]:
        """Pega las acciones sueltas `ids` detrás de la acción `objetivo` (del modelo, o un borrador de una etapa o de un
        grupo suelto). Devuelve la etapa a la que quedan unidas (None si quedan en un grupo suelto) y las que pasaron al
        modelo."""
        b = next((x for x in self.ed.draft_actions() if x["id"] == objetivo), None)
        if b is not None and not b.get("etapa"):
            self._pegar_a_grupo(ids, b)
            return None, []
        if b is not None:
            sid = b["etapa"]
        else:  # una acción o una orden de forzado del modelo
            elemento = self.ed.get(objetivo)
            sid = elemento.get("stepRef") or elemento["sourceStepRef"]
        return sid, self._pegar_a_etapa(ids, sid, objetivo)

    def pegar(self, ids: list[str], objetivo: str) -> None:
        """Pega una acción suelta (o un grupo) detrás de otra acción: pasa a su etapa o a su grupo, en una sola operación
        de deshacer."""
        destino: list[Any] = [(None, [])]
        motivo = self._atomico("pegar acciones", lambda: destino.__setitem__(0, self._pegar(ids, objetivo)))
        self._decir(motivo)
        if motivo:
            self.parpadear(ids)
            self.cambiado.emit()
            return
        self._tras_pegar(ids, *destino[0])

    def _tras_pegar(self, ids: list[str], sid: str | None, promovidas: list[str] = ()) -> None:
        """Deja la selección en lo pegado y, si es una sola acción que aún necesita su variable o su valor, abre Editar."""
        vivos = [i for i in ids if self._es_borrador(i)]
        ordenes = [i for i in promovidas if any(o["id"] == i for o in self.ed.model["forces"])]  # las que pasaron a `forces`
        if sid is None:  # quedaron en un grupo suelto
            self.sel, self.accion = self._ids_grupo(ids[0]), ids[0]
        elif vivos:
            self.sel, self.accion = ([vivos[0]], None) if self.es_orden_suelta(vivos[0]) else ([sid], vivos[0])
        elif ordenes and len(ordenes) == len(promovidas):
            self.sel, self.accion = [ordenes[0]], None
        else:
            acciones = [i for i in promovidas if i not in ordenes]
            self.sel, self.accion = [sid], (acciones[0] if acciones else self.ed.get(sid)["actionRefs"][-1])
        self.cambiado.emit()
        if len(ids) == 1 and vivos and sid and self.es_orden_suelta(vivos[0]):  # a elegir su destino: las opciones de la orden
            self.pedir_accion(None, vivos[0])
        elif len(ids) == 1 and vivos and sid and set(self.faltan(self._datos_borrador(self._borrador(vivos[0])), self.parcial_de(sid))) & {"variable", "valor"}:
            self.pedir_accion(sid, vivos[0])

    def unir_accion(self, did: str, sid: str) -> None:
        """Une una acción suelta (con las que lleva pegadas) a una etapa, al final de sus acciones. Las completas pasan a
        ser acciones del modelo; las que no, quedan unidas como borradores y, si es una sola, se abre Editar."""
        if not self._es_borrador(did):
            return
        ids = self._ids_grupo(did)
        promovidas: list[str] = []
        motivo = self._atomico("unir acciones a la etapa", lambda: promovidas.extend(self._pegar_a_etapa(ids, sid, None)))
        self._decir(motivo)
        if motivo:
            self.parpadear(ids)
            self.cambiado.emit()
            return
        self._tras_pegar(ids, sid, promovidas)

    # -- el enlace de una etapa con sus acciones
    def _separar_todas(self, sid: str) -> list[str]:
        """Las acciones de la etapa dejan de estar unidas a ella: quedan sueltas e independientes (sin grupo), cada una
        donde estaba y sin solaparse. Una acción del modelo pasa a ser un borrador con todos sus datos. Devuelve sus ID
        nuevos."""
        cajas = [c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["etapa"] == sid]
        ordenes = [c for c in getattr(self.diagrama, "cajas_ordenes", None) or [] if c["etapa"] == sid]  # las órdenes del modelo
        if not cajas and not ordenes:
            return []
        orden = [c["id"] for c in cajas]
        sitio = {c["id"]: (round(c["rect"][0] - SX), round(c["rect"][1] + H)) for c in cajas}
        nuevos: dict[str, str] = {}
        for aid in orden:
            if not self._es_borrador(aid):
                datos = self.datos_accion(aid)
                nuevos[aid] = self.ed.add_draft_action(sitio[aid], {
                    "tipo": datos["tipo"], "variable": self.ed.get(aid)["targetRef"],
                    **{k: datos[k] for k in ("condicion", "valor", "evento", "limite") if datos.get(k)}})
        cambios = {aid: {"etapa": None, "grupo": None, "orden": None, "x": sitio[aid][0], "y": sitio[aid][1]}
                   for aid in orden if self._es_borrador(aid)}
        if cambios:
            self.ed.update_draft_actions(cambios)
        modelo = [aid for aid in orden if aid in nuevos]
        if modelo:
            self.ed.delete(modelo)
        for c in ordenes:  # una orden de forzado del modelo pasa a ser una orden suelta con todos sus datos
            fuerza = next(o for o in self.ed.model["forces"] if o["id"] == c["id"])
            datos = {"tipo": "forzado", "destino": fuerza["targetPartialRef"], "forma": fuerza["targetKind"],
                     "etapas": list(fuerza.get("targetSteps", []))}
            nuevos[c["id"]] = self.ed.add_draft_action((round(c["rect"][0] - SX), round(c["rect"][1] + H)), datos)
            self.ed.delete_force(c["id"])
            orden.append(c["id"])
        return [nuevos.get(aid, aid) for aid in orden]

    def eliminar_enlace_acciones(self, sid: str) -> None:
        """«Eliminar el enlace»: separa las acciones de la etapa (una sola operación de deshacer)."""
        ids: list[str] = []
        motivo = self._atomico("eliminar el enlace de las acciones", lambda: ids.extend(self._separar_todas(sid)))
        self._decir(motivo)
        if motivo:
            self.parpadear([sid])
        elif ids:
            self.sel, self.accion = ids, None
        self.cambiado.emit()

    def separar_accion(self, aid: str) -> None:
        """Separa una acción de su etapa, o de su grupo suelto: vuelve a ser suelta, a la derecha de lo que dejó. Una acción
        del modelo pasa a ser un borrador (con todos sus datos)."""
        cajas = getattr(self.diagrama, "cajas_acciones", None) or []
        borrador = self._es_borrador(aid)
        b = self._borrador(aid) if borrador else None
        sid = b.get("etapa") if b else self.ed.get(aid)["stepRef"]
        grupo = b.get("grupo") if b and not sid else None
        propia = next((c for c in cajas if c["id"] == aid), None)
        fila = [c for c in cajas if (c["etapa"] == sid if sid else c.get("grupo") == grupo)]
        if propia and fila:
            final = max(c["rect"][0] + c["rect"][2] for c in fila)
            at = (round(final + 40 - SX), round(propia["rect"][1] + H))
        else:
            px, py = posiciones(self.M)[sid]
            at = (ajustar(px - SX + 140), ajustar(py))
        if borrador:
            def hacer() -> None:
                self.ed.update_draft_actions({aid: {"etapa": None, "grupo": None, "orden": None, "x": at[0], "y": at[1]}})
            nuevo = aid
        else:
            datos = self.datos_accion(aid)
            ref = self.ed.get(aid)["targetRef"]
            nuevo = ""

            def hacer() -> None:
                nonlocal nuevo
                nuevo = self.ed.add_draft_action(at, {"tipo": datos["tipo"], "variable": ref,
                                                      **{k: datos[k] for k in ("condicion", "valor", "evento", "limite")
                                                         if datos.get(k)}})
                self.ed.delete([aid])
        motivo = self._atomico("separar acción", hacer)
        self._decir(motivo)
        if motivo:
            self.parpadear([aid])
        if motivo is None:
            self.sel, self.accion = [nuevo], None
            self.cambiado.emit()

    # -- menús
    def menu(self, p: QPointF) -> list[tuple[str, Any]]:
        """Opciones del botón derecho sobre lo que hay debajo: en una etapa, la colocación de sus
        acciones; en una acción (suelta o unida), su tipo (submenú con iconos, marcado el actual), «Editar…», separarla y
        «Quitar»; en el enlace de una etapa con sus acciones, «Eliminar el enlace». Jerarquía (P-IMP-23..27; las mismas
        opciones son los botones del panel de opciones, `acciones_jerarquia`): una etapa o una macroetapa ofrece el
        submenú «Tipo de etapa» (con icono: «Etapa», «Encapsulante» y «Macroetapa», excluyentes y con el actual marcado,
        y la casilla «Etapa inicial», que no vale para una macroetapa; no sale en la entrada ni en la salida de una
        expansión); una encapsulante, «Añadir recinto…»; una etapa de un recinto, «Enlace de activación» (casilla
        marcada o no) y «Encuadrar la encapsulante»; la entrada y la salida
        de una expansión, «Encuadrar la macroetapa»; cualquier etapa, «Forzar un parcial…» si hay otro parcial; una encapsulante
        con recintos, «Encuadrar el recinto» (o «los recintos»); una macroetapa, «Encuadrar la expansión» y «Renombrar…»; el
        marco de un recinto, «Encuadrar la encapsulante»; el de un grafcet parcial suelto, «Renombrar…»; una orden de forzado,
        «Tipo de acción» (con «Orden de forzado» marcado: elegir otro la convierte en una acción de la misma etapa),
        «Editar orden de forzado…» y «Quitar orden de forzado» (una sin completar: «Configurar orden de forzado…», «Separar de la
        etapa» o «del grupo» y «Quitar orden de forzado»). Una etapa, una macroetapa, una transición, un enlace o una barra
        de una cadena de elementos enlazados ofrecen, al final, «Equidistanciar alturas de la cadena» (y, si están entre varios
        seleccionados, «Equidistanciar la selección»); el hueco, «Nuevo grafcet parcial aquí», «Equidistanciar todo el lienzo» (y
        «…la selección» si hay varios seleccionados). Ninguna de estas opciones tiene atajo de teclado, como tampoco «Añadir
        acción…» (la paleta y el botón derecho son del ratón)."""
        self.menu_marcadas, self.menu_desmarcadas = set(), set()
        caja = self.accion_en(p)
        if caja:
            return self._menu_accion(caja)
        orden = self.orden_en(p)
        if orden:  # una orden de forzado: se selecciona y ofrece editarla o quitarla
            self.sel, self.accion = [orden["id"]], None
            self.cambiado.emit()
            return self._menu_tipo_orden(orden["id"]) + [("-", None)] + self._menu_desde(orden["id"])
        ident = elemento_en(self.M, p)
        if ident is None:
            union = self.union_en(p)
            if union:
                self.sel, self.accion = [union], None
                self.cambiado.emit()
                return [("Eliminar el enlace", lambda: self.eliminar_enlace_acciones(union.split(":", 1)[1]))]
            return self._menu_lienzo(p)
        if self.anotacion(ident):
            if ident not in self.sel:self.sel=[ident]
            self.accion=None;self.cambiado.emit()
            return [("Editar texto…" if self.anotacion(ident)["kind"]=="text" else "Cambiar imagen…",lambda:self.editar_anotacion(ident)),
                    ("Eliminar",self.borrar)]
        en_varios = ident in self.sel and len(self.sel) > 1  # el botón derecho en uno de varios seleccionados no los deshace
        if ident in {x["id"] for x in self.M.get("macros", [])} or ident in cajas_parciales(self.M):
            if not (en_varios and ident not in cajas_parciales(self.M)):
                self.sel, self.accion = [ident], None  # una macroetapa o el marco de un parcial: se selecciona
            self.cambiado.emit()
            equi = [] if ident in cajas_parciales(self.M) else self._menu_equidistancia(ident, en_varios)
            return self._menu_desde(ident) + ([("-", None)] + equi if equi else [])
        equi = self._menu_equidistancia(ident, en_varios)
        if ident in orientaciones(self.M):  # una transición: girarla (y, si está en una cadena, equidistanciar)
            if not en_varios:
                self.sel, self.accion = [ident], None
            self.cambiado.emit()
            return self._menu_giro(ident) + ([("-", None)] + equi if equi else [])
        if not any(s["id"] == ident for s in self.M["steps"]):  # un enlace, una barra
            flecha = self._menu_flecha(ident) if not en_varios else []
            if equi or flecha:
                if not en_varios:
                    self.sel, self.accion = [ident], None
                self.cambiado.emit()
            return flecha + ([("-", None)] if flecha and equi else []) + equi
        if not en_varios:
            self.sel, self.accion = [ident], None
        self.cambiado.emit()
        self.menu_marcadas = {dict(COLOCACIONES)[self.colocacion(ident)]}
        opciones = self._menu_desde(ident)
        return [("Colocación de las acciones", [(texto, lambda v=v: self.colocar_acciones(ident, v))
                                                for v, texto in COLOCACIONES])] \
\
            + ([("-", None)] + opciones if opciones else []) + ([("-", None)] + equi if equi else [])

    def flecha_visible(self, ident: str) -> bool | None:
        """Si el enlace `ident` se dibuja ahora con su flecha de recorrido; None si no es un enlace."""
        ruta = next((r for r in enlaces(self.M) if r["id"] == ident), None)
        return None if ruta is None else any(f["key"] == "flow" for f in ruta["arrows"])

    def alternar_flecha(self, ident: str) -> bool:
        """«Mostrar flecha» / «Quitar flecha» del enlace `ident`: fija a mano `linkStyles[ident].arrows.flow.visible` (sin la
        clave, la decide el programa: enlaces que suben, transiciones giradas). Una sola operación de deshacer; solo
        presentación. Devuelve si cambió algo."""
        visible = self.flecha_visible(ident)
        if visible is None:
            return False
        style = copy.deepcopy(self.ed.link_styles().get(ident, {}))
        style.setdefault("arrows", {}).setdefault("flow", {})["visible"] = not visible
        self.ed.set_link_style(ident, style)
        self.cambia()
        return True

    def _menu_flecha(self, ident: str) -> list[tuple[str, Any]]:
        """Solo la opción que cambia el estado actual: «Mostrar flecha» si el enlace no la lleva, «Quitar flecha» si la lleva."""
        visible = self.flecha_visible(ident)
        if visible is None:
            return []
        return [("Quitar flecha" if visible else "Mostrar flecha", lambda: self.alternar_flecha(ident))]

    def _menu_giro(self, tid: str) -> list[tuple[str, Any]]:
        """«Girar en sentido antihorario» y «Girar en sentido horario» de una transición: si está entre varias seleccionadas,
        giran todas."""
        ids = self._transiciones_sel() if tid in self.sel else [tid]
        return [("Girar en sentido antihorario", lambda: self.girar_transiciones(-1, ids)),
                ("Girar en sentido horario", lambda: self.girar_transiciones(1, ids))]

    def orientacion_transicion(self, tid: str) -> str:
        """El sentido de la evolución a través de la transición: «abajo» (por defecto), «derecha», «arriba» o «izquierda»."""
        valor = self.ed.transition_orientations().get(tid, "abajo")
        return valor if valor in self.ed.TRANSITION_ORIENTATIONS else "abajo"

    def _transiciones_sel(self, ids: list[str] | None = None) -> list[str]:
        """Las transiciones de `ids` (por defecto, la selección)."""
        todas = {t["id"] for t in self.M["transitions"]}
        return [i for i in dict.fromkeys(self.sel if ids is None else ids) if i in todas]

    def girar_transiciones(self, sentido: int | str, transiciones: list[str] | None = None) -> bool:
        """«Girar en sentido horario» (positivo, o «horario»/«derecha») o «antihorario» (negativo, o «antihorario»/«izquierda») las transiciones
        seleccionadas (o `transiciones`): el sentido de la evolución a través de la transición pasa al siguiente a derechas
        (como las agujas del reloj en pantalla) abajo → izquierda → arriba → derecha → abajo, o al anterior a izquierdas. El
        trazo se coloca perpendicular a la evolución y el texto sigue horizontal. Es una operación de vista (no cambia el
        modelo ni la simulación) y una sola de deshacer. Devuelve si giró algo."""
        paso = 1 if sentido in ("horario", "derecha", "der") or (isinstance(sentido, int) and sentido > 0) else -1
        ids = self._transiciones_sel(transiciones)
        if not ids:
            self.informar("Seleccione una transición para girarla.")
            self.cambiado.emit()
            return False
        orden = self.ed.TRANSITION_ORIENTATIONS
        nuevos = {i: orden[(orden.index(self.orientacion_transicion(i)) + paso) % len(orden)] for i in ids}
        motivo = self._atomico("girar las transiciones", lambda: self.ed.set_transition_orientations(nuevos), hueco=False)
        self._decir(motivo)
        if motivo:
            self.parpadear(ids)
        return motivo is None

    def _menu_equidistancia(self, ident: str, en_varios: bool = False) -> list[tuple[str, Any]]:
        """«Equidistanciar alturas de la cadena» si `ident` está en una (etapas, macroetapas, transiciones y barras enlazados)
        y «Equidistanciar la selección» si es uno de varios seleccionados cuyas cadenas hay."""
        pos = self._posiciones_modelo()
        out: list[tuple[str, Any]] = []
        if self.ed.chains([ident], pos):
            out.append(("Equidistanciar alturas de la cadena", lambda: self.equidistanciar([ident])))
        if en_varios and self.ed.chains(self.sel, pos):
            seleccion = list(self.sel)
            out.append(("Equidistanciar la selección", lambda: self.equidistanciar(seleccion)))
        return out

    def _menu_lienzo(self, p: QPointF) -> list[tuple[str, Any]]:
        """Equidistanciar la selección o todo el lienzo si hay cadenas. Los parciales se crean desde la paleta."""
        pos = self._posiciones_modelo()
        equi: list[tuple[str, Any]] = []
        if len(self.sel) > 1 and self.ed.chains(self.sel, pos):
            seleccion = list(self.sel)
            equi.append(("Equidistanciar la selección", lambda: self.equidistanciar(seleccion)))
        if self.ed.chains(None, pos):
            equi.append(("Equidistanciar todo el lienzo", lambda: self.equidistanciar(None)))
        return equi

    def _menu_desde(self, ident: str) -> list[tuple[str, Any]]:
        """Las acciones de jerarquía de un elemento como opciones de menú (las casillas, con su marca en `menu_marcadas`
        o `menu_desmarcadas`). Los tipos de una etapa o de una macroetapa (casillas de `acciones_jerarquia`) van
        juntos en el submenú «Tipo de etapa», con el icono de su ficha de la paleta y, en una etapa, la casilla
        «Etapa inicial»."""
        from .propiedades import icono as icono_ficha  # (propiedades importa este módulo: no puede ir arriba)
        out: list[tuple[str, Any]] = []
        tipos: list[tuple[str, Any, Any]] = []
        fichas = {texto: ficha for _, texto, ficha in TIPOS_ETAPA}
        for texto, funcion, estado in self.acciones_jerarquia(ident):
            if texto in fichas:
                tipos.append((texto, funcion, icono_ficha(fichas[texto])))
            else:
                out.append((texto, funcion))
            if estado is not None:
                (self.menu_marcadas if estado else self.menu_desmarcadas).add(texto)
        if tipos:
            st = next((s for s in self.ed.model["steps"] if s["id"] == ident), None)
            if st is not None:
                inicial = bool(st["initial"])
                tipos.insert(1, (TEXTO_INICIAL, lambda: self.tipo_etapa(ident, not inicial),
                                 icono_ficha("etapa_inicial")))  # el orden: Etapa, Etapa inicial, Encapsulante, Macroetapa
                if inicial:
                    self.menu_marcadas.add(TEXTO_INICIAL)
            out.insert(0, ("Tipo de etapa", tipos))
        return out

    def _menu_tipo_orden(self, oid: str) -> list[tuple[str, Any]]:
        """El submenú «Tipo de acción» de una orden de forzado (del modelo o sin completar): los cinco tipos de acción
        con su icono y «Orden de forzado», marcada. Elegir un tipo de acción la convierte en una acción de su misma
        etapa."""
        sub = [(texto, lambda t=t: self.orden_a_accion(oid, t), icono_accion(t)) for t, texto in TIPOS_ACCION]
        sub.append((TEXTO_ORDEN, lambda: None, icono_accion("forzado")))
        self.menu_marcadas.add(TEXTO_ORDEN)
        return [("Tipo de acción", sub)]

    def _menu_orden_suelta(self, caja: dict[str, Any]) -> list[tuple[str, Any]]:
        """El menú de una orden de forzado sin completar (suelta, o unida a una etapa sin destino): configurarla (el diálogo de
        la orden), separarla de su etapa o de su grupo, y quitarla."""
        did, sid = caja["id"], caja["etapa"] or None
        grupo = self._ids_grupo(did) if not sid else [did]
        self.sel, self.accion = (grupo, did) if not sid else ([did], None)
        self.cambiado.emit()
        out: list[tuple[str, Any]] = [*self._menu_tipo_orden(did), ("-", None),
                                      ("Configurar orden de forzado…", lambda: self.configurar_orden(did))]
        if sid:
            out.append(("Separar de la etapa", lambda: self.separar_accion(did)))
        elif len(grupo) > 1:
            self.menu_marcadas.add(dict(COLOCACIONES)[self.colocacion(caja["grupo"])])
            out.append(("Separar del grupo", lambda: self.separar_accion(did)))
            out.append(("Colocación de las acciones", [(texto, lambda v=v: self.colocar_acciones(caja["grupo"], v))
                                                       for v, texto in COLOCACIONES]))
        out.append(("Quitar orden de forzado", lambda: self.quitar_orden(did)))
        return out

    def _menu_accion(self, caja: dict[str, Any]) -> list[tuple[str, Any]]:
        if caja.get("forzado"):
            return self._menu_orden_suelta(caja)
        aid, sid, suelta = caja["id"], caja["etapa"] or None, bool(caja.get("suelta"))
        grupo = self._ids_grupo(aid) if suelta else [aid]
        self.sel, self.accion = (grupo, aid) if suelta else ([sid], aid)
        self.ver_accion = True  # botón derecho en una acción: se selecciona, y sus opciones salen abajo
        self.cambiado.emit()
        actual = self.datos_accion(aid)["tipo"]
        textos = dict(TIPOS_ACCION)
        if actual == "limitada":  # la de un fichero antiguo: una condicionada con límite de tiempo
            textos["condicionada"] = TEXTO_LIMITADA
        sub = [(textos[t], lambda t=t: self.tipo_accion(aid, t), icono_accion(t)) for t, _ in TIPOS_ACCION]
        sub.append((TEXTO_ORDEN, lambda: self.accion_a_orden(aid), icono_accion("forzado")))
        self.menu_marcadas = {textos["condicionada" if actual == "limitada" else actual]}
        out: list[tuple[str, Any]] = [("Tipo de acción", sub), ("-", None),
                                      ("Editar…", lambda: self.explicito(self.pedir_accion, sid, aid))]
        if sid:
            out.append(("Separar de la etapa", lambda: self.separar_accion(aid)))
        elif len(grupo) > 1:
            out.append(("Separar del grupo", lambda: self.separar_accion(aid)))
            self.menu_marcadas.add(dict(COLOCACIONES)[self.colocacion(caja["grupo"])])
            out.append(("Colocación de las acciones", [(texto, lambda v=v: self.colocar_acciones(caja["grupo"], v))
                                                       for v, texto in COLOCACIONES]))
        if sid and not caja.get("borrador"):
            columna = self.colocacion(sid) == "columna"
            out += [("Mover arriba" if columna else "Mover a la izquierda", lambda: self.mover_accion(aid, -1)),
                    ("Mover abajo" if columna else "Mover a la derecha", lambda: self.mover_accion(aid, 1))]
        out.append(("Quitar", lambda: self.quitar_accion(aid)))
        return out

    def colocacion(self, sid: str) -> str:
        """Cómo se colocan las acciones de la etapa (o del grupo suelto): «fila» (por defecto), «fila-separada»,
        «matriz-2» o «columna»."""
        valor = self.ed.action_layouts().get(sid, "fila")
        return valor if valor in dict(COLOCACIONES) else "fila"

    def colocar_acciones(self, sid: str, valor: str) -> None:
        """Cambia la colocación de las acciones de una etapa o de un grupo suelto (operación de vista, se deshace)."""
        if valor == self.colocacion(sid):
            return
        motivo = self._atomico("colocación de las acciones", lambda: self.ed.set_action_layout(sid, valor))
        self._decir(motivo)
        if motivo:
            self.parpadear([sid])

    def _texto(self, eid: str | None) -> str:
        return a_usuario(next(e["text"] for e in self.ed.model["expressions"] if e["id"] == eid)) if eid else ""

    def datos_accion(self, aid: str) -> dict[str, str]:
        """Una acción (del modelo o borrador) en la notación del usuario: tipo (continua, condicionada, limitada,
        activacion, desactivacion, evento), variable, condición (continuas; vacía si es siempre), límite (limitada), valor
        (memorizada; 1/0 para una booleana) y evento. «limitada» (una condicionada con límite de tiempo) ya no se ofrece:
        solo la traen los ficheros antiguos."""
        if self._es_borrador(aid):
            return self._datos_borrador(self._borrador(aid))
        m = self.ed.model
        a = self.ed.get(aid)
        var = next((v for v in m["variables"] if v["id"] == a["targetRef"]), None)
        nombre = var["name"] if var else a["targetRef"]
        if a["mode"] == "continuous":
            cond = self._texto(a["conditionRef"])
            cond = "" if cond in ("1", "true") else cond
            limite = _dur_usuario(int(a["limitUs"])) if "limitUs" in a else ""
            return {"tipo": "limitada" if limite else "condicionada" if cond else "continua", "variable": nombre,
                    "condicion": cond, "limite": limite}
        trig = a["trigger"]
        valor = self._texto(a["valueRef"])
        if var and var["type"]["kind"] == "bool":
            valor = {"true": "1", "false": "0"}.get(valor, valor)
        return {"tipo": {"activation": "activacion", "deactivation": "desactivacion", "event": "evento"}[trig["kind"]],
                "variable": nombre, "valor": valor, "evento": self._texto(trig.get("expressionRef"))}

    @staticmethod
    def resumen_accion(d: dict[str, str]) -> str:
        """Una línea para la lista de acciones de la etapa."""
        var = d["variable"] or "?"
        if d["tipo"] in CONTINUAS:
            lim = f" hasta {d.get('limite') or '?'}" if d["tipo"] == "limitada" else ""
            if d["tipo"] == "condicionada" or d.get("condicion"):
                return var + f"   si {d.get('condicion') or '?'}" + lim
            return var + "   (continua)" + lim
        cuando = {"activacion": "al activar ↑", "desactivacion": "al desactivar ↓",
                  "evento": f"con {d.get('evento') or '?'}"}[d["tipo"]]
        return f"{var} := {d.get('valor') or '?'}   ({cuando})"

    def acciones(self, sid: str) -> list[dict[str, str]]:
        """Las acciones de la etapa: las del modelo y, al final, las unidas a ella que aún no están completas."""
        st = next(s for s in self.ed.model["steps"] if s["id"] == sid)
        out = [dict(self.datos_accion(aid), id=aid) for aid in st["actionRefs"]]
        return out + [dict(self._datos_borrador(b), id=b["id"], borrador=True)
                      for b in self._borradores_ordenados() if b.get("etapa") == sid and b["tipo"] != "forzado"]

    def _atomico(self, etiqueta: str, fn: Callable[[], Any], hueco: bool = True) -> str | None:
        """Varias operaciones como una sola de deshacer; si una falla, no queda ninguna y se devuelve el motivo. Con `hueco`
        (lo normal), lo que ensanchó o añadió acciones aparta lo que estorba; sin él, la operación ya cuida de dónde pone
        las cosas."""
        n, rehacer = len(self.ed.undo_stack), list(self.ed.redo_stack)
        self._encima = []
        try:
            with self.ed.group(etiqueta):
                self.reconstruir()
                antes = self._firmas()
                fn()
                self._encima = self._asegurar_hueco(antes) if hueco else []  # lo que ensanchó o añadió acciones aparta lo que estorba
        except DiagnosticError as exc:
            self._encima = []
            while len(self.ed.undo_stack) > n:
                self.ed.undo()
            self.ed.redo_stack[:] = rehacer  # (como estaba, aunque fn haya hecho varias operaciones)
            self.reconstruir()  # (una operación pudo haber rehecho la vista a medias)
            return "; ".join(self.sust(d.message) for d in exc.diagnostics)
        self.cambia()
        if self._encima:  # no se pudo abrir hueco: se deja como está, con un aviso que no es un error
            self.informar(MSG_ENCIMA)
            self.parpadear(self._encima)
        return None

    def _decir(self, motivo: str | None) -> None:
        """El mensaje tras una operación atómica: su motivo si falló; si no, el aviso de que quedó encima de algo (si es el
        caso) o nada."""
        self.mensaje = motivo or ""
        if not motivo and self._encima:
            self.informar(MSG_ENCIMA)

    @staticmethod
    def _limite_us(texto: str) -> int | None:
        """«3s», «500ms»… -> µs; None si no es una duración o es 0."""
        t = normalizar_duracion(texto)
        return parse_duration(t.replace(",", ".")) if t else None

    def _crear_o_cambiar(self, sid: str, d: dict[str, str], aid: str | None, vid: str) -> None:
        """Escribe en el modelo la acción `d` (con su variable ya resuelta): nueva en la etapa, o la `aid` cambiada."""
        var = next(v for v in self.ed.model["variables"] if v["id"] == vid)
        booleana = var["type"]["kind"] == "bool"
        if d["tipo"] in CONTINUAS:
            cond = self._n(d.get("condicion", "")) or "true"
            limite = self._limite_us(d.get("limite", "")) if d["tipo"] == "limitada" else None
            if aid:
                self.ed.update_action(aid, vid, "continuous", condition=cond, limit_us=limite)
            else:
                self.ed.add_continuous_action(sid, vid, cond, limite)
            return
        valor = d["valor"].strip()
        # el valor de una booleana es true o false; el de una entera (n := 1) sigue siendo un número
        valor = self._n({"1": "true", "0": "false"}.get(valor, valor) if booleana else valor, booleana)
        trig = DISPARADOR[d["tipo"]]
        evento = self._n(d["evento"]) if trig == "event" else None
        if aid:
            self.ed.update_action(aid, vid, "stored", trigger=trig, value=valor, event=evento)
        else:
            self.ed.add_stored_action(sid, vid, trig, valor, evento)

    @staticmethod
    def motivo_nombre(nombre: str) -> str | None:
        """Por qué un nombre no puede ser el de una variable en la interfaz: no se podría escribir en una fórmula (palabra
        reservada, espacios o símbolos, solo cifras o parecido a una duración) o se confundiría con la actividad de una
        etapa (X1). None si sirve. Un nombre que empieza por cifra (1M1, 2S3: nomenclatura industrial) vale si lleva alguna
        letra; en las fórmulas se escribe entre comillas invertidas (`1M1`), como cualquier nombre que no sea una palabra
        simple, y el resto de la interfaz lo muestra sin ellas (P-IMP-46). El núcleo sigue admitiendo cualquier nombre
        entre comillas invertidas, en ficheros antiguos."""
        if nombre.strip().lower() in RESERVADAS:
            return f'"{nombre}" no puede ser nombre de variable: es una palabra de las fórmulas'
        if re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:us|µs|μs|ms|s)", nombre):
            return (f'"{nombre}" no puede ser nombre de variable: se leería como una duración (3s, 500ms…); '
                    "añada alguna letra más, como 1S2")
        if re.fullmatch(r"\d+(?:[.,]\d+)?", nombre):
            return f'"{nombre}" no puede ser nombre de variable: es solo un número; añada alguna letra, como 1M1'
        if not (re.fullmatch(r"[^\W\d]\w*(?:\.\w+)?", nombre)
                or re.fullmatch(r"\d\w*", nombre) and re.search(r"[^\W\d_]", nombre)):
            return (f'"{nombre}" no puede ser nombre de variable: debe empezar por una letra o _ (o por una cifra, si lleva '
                    "alguna letra, como 1M1) y no llevar espacios ni símbolos")
        if re.fullmatch(r"X\d+", nombre):
            return f'"{nombre}" no puede ser nombre de variable: se confundiría con la actividad de la etapa {nombre[1:]}'
        return None

    def poner_accion(self, sid: str | None, d: dict[str, str], aid: str | None = None,
                     crear: tuple[str, Any] | None = None) -> str | None:
        """Añade (o, con `aid`, cambia) una acción de la etapa con los datos de `datos_accion`. Si la variable no existe
        y se da `crear` (papel, tipo), se declara antes. Con el `aid` de un borrador, lo guarda (aunque le falten datos).
        Una condicionada o por evento sin su condición o su evento (se programan en el panel de opciones) queda como
        borrador unido a la etapa. Devuelve el motivo si no se pudo; nada cambia en ese caso."""
        if aid and self._es_borrador(aid):
            return self._poner_borrador(aid, d, crear)
        m, nombre = self.ed.model, d.get("variable", "").strip()
        var = next((v for v in m["variables"] if v["name"] == nombre), None)
        if not nombre:
            return "Elija la variable sobre la que actúa."
        if var is None and crear is None:
            return f"La variable «{nombre}» no existe."
        if var is None and (motivo := self.motivo_nombre(nombre)):
            return motivo
        if d["tipo"] in DISPARADOR and not d.get("valor", "").strip():
            return "Escriba el valor que se asigna (1 o 0 para una booleana; un número o una cuenta como CT + 1)."
        if d["tipo"] == "limitada" and normalizar_duracion(d.get("limite", "")) is None:
            return "Límite de tiempo no válido: escriba «3s», «500ms»…"
        if d["tipo"] == "limitada" and not self._limite_us(d.get("limite", "")):
            return "Escriba el límite de tiempo de la acción (por ejemplo 3s)."
        sin_texto = bool({"condición", "evento"} & set(self.faltan({**d, "variable": nombre}, self.parcial_de(sid))))

        def hacer() -> None:
            vid = var["id"] if var else self.ed.add_variable(nombre, crear[0], (crear[1] if isinstance(crear[1], dict) else {"kind": crear[1]}))
            if sin_texto:  # falta programar la condición o el evento: borrador unido a la etapa, al final de la fila
                if aid:
                    self.ed.delete([aid])
                px, py = posiciones(self.M)[sid]
                did = self.ed.add_draft_action((ajustar(px - SX + H + ACT_LINK), ajustar(py)), {"etapa": sid})
                self.ed.update_draft_action(did, **self._campos_borrador(d, vid))
            else:
                self._crear_o_cambiar(sid, d, aid, vid)
        motivo = self._atomico("acción", hacer)
        if motivo:
            self.parpadear([sid])
        if motivo is None and sid not in self.sel:
            self.sel = [sid]
            self.cambiado.emit()
        return motivo

    def cambiar_accion(self, aid: str, d: dict[str, str], crear: tuple[str, Any] | None = None) -> str | None:
        """Aplica los datos de una acción (del modelo o borrador; los de `datos_accion`) en el acto, como una operación de
        deshacer: lo que hace el panel de opciones con cada cambio. Con `crear` (papel, tipo), declara antes la variable si
        no existe. Si a la acción le falta algo (la variable, el valor, la condición, el evento…), queda como borrador unido
        a su etapa; si no, es una acción del modelo. Devuelve el motivo si no se pudo (un texto que no se interpreta, un
        nombre que no vale); nada cambia en ese caso."""
        if self._es_borrador(aid):
            return self._poner_borrador(aid, d, crear)
        sid = self.ed.get(aid)["stepRef"]
        nombre = d.get("variable", "").strip()
        var = next((v for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None
        if nombre and var is None and crear is None:
            return f"La variable «{nombre}» no existe."
        if nombre and var is None and (motivo := self.motivo_nombre(nombre)):
            return motivo
        motivo = self._revisar_textos(d, self.parcial_de(sid), nombre if var is None else None)
        if motivo:
            return motivo
        falta = set(self.faltan({**d, "variable": nombre if var else ""}, self.parcial_de(sid)))
        if var is None and nombre and (d["tipo"] not in CONTINUAS or (crear[1] if isinstance(crear[1], dict) else
                                                                      {"kind": crear[1]}).get("kind") == "bool"):
            falta.discard("variable")  # la variable que se va a crear sirve para esta acción
        nuevo = [aid]

        def hacer() -> None:
            vid = (var["id"] if var else self.ed.add_variable(nombre, crear[0], (crear[1] if isinstance(crear[1], dict)
                                                                                  else {"kind": crear[1]}))) if nombre else None
            if falta:
                nuevo[0] = self._a_borrador(aid, {**d, "variable": nombre}, sid, vid)
            else:
                self._crear_o_cambiar(sid, d, aid, vid)
        señalada, seleccion = self.accion == aid, list(self.sel)
        motivo = self._atomico("acción", hacer)
        if motivo:
            return motivo
        if nuevo[0] != aid:  # pasó a borrador: la selección la sigue
            self.sel = [nuevo[0] if i == aid else i for i in seleccion]
            self.accion = nuevo[0] if señalada else self.accion
            self.cambiado.emit()
        return None

    def _revisar_textos(self, d: dict[str, str], parcial: str | None = None, nueva: str | None = None) -> str | None:
        """Por qué un texto de la acción (condición, valor, evento) no se interpreta en el ámbito del `parcial` de su etapa
        (por defecto, el raíz); None si todos sirven. `nueva` es la variable que se va a declarar con la misma operación
        (`crear`): todavía no existe, pero un texto que solo falla por ella (`K := K + 1`) sirve, como una vez unida la
        acción a su etapa; un texto mal escrito, o con otra variable inexistente, se sigue rechazando."""
        raiz = parcial or self.raiz
        for campo, usa, booleana, nombre in (("condicion", d["tipo"] in CONTINUAS, True, "La condición"),
                                             ("valor", d["tipo"] in DISPARADOR, False, "El valor"),
                                             ("evento", d["tipo"] == "evento", True, "El evento")):
            texto = d.get(campo, "").strip()
            if usa and texto:
                diag = self.ed.check_expression(self._n(texto, booleana), raiz)
                if diag is not None and nueva:
                    faltan = self.ed.undeclared_variables(self._n(texto, booleana), raiz)
                    if faltan and set(faltan) <= {nueva}:
                        continue
                if diag is not None:
                    return f"{nombre} no es válido: {self.sust(diag.message)}"
        if d["tipo"] == "limitada" and d.get("limite", "").strip() and normalizar_duracion(d["limite"]) is None:
            return "Límite de tiempo no válido: escriba «3s», «500ms»…"
        return None

    def _campos_borrador(self, d: dict[str, str], vid: str | None) -> dict[str, Any]:
        """Los campos de un borrador para `d` (en la notación del usuario): solo los que pide su tipo."""
        relevantes = {"condicion": d["tipo"] in CONTINUAS, "valor": d["tipo"] in DISPARADOR,
                      "evento": d["tipo"] == "evento", "limite": d["tipo"] == "limitada"}
        return {"tipo": d["tipo"], "variable": vid,
                **{k: (normalizar_duracion(d[k]) if k == "limite" else d.get(k, "").strip()) if relevantes[k] else ""
                   for k in relevantes}}

    def _poner_borrador(self, did: str, d: dict[str, str], crear: tuple[str, Any] | None) -> str | None:
        """Guarda los datos de un borrador (le pueden faltar); si está unido a una etapa y queda completo, pasa a ser una
        acción del modelo en la misma operación."""
        nombre = d.get("variable", "").strip()
        var = next((v for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None
        if nombre and var is None and crear is None:
            return f"La variable «{nombre}» no existe."
        if nombre and var is None and (motivo := self.motivo_nombre(nombre)):
            return motivo
        motivo = self._revisar_textos(d, self._parcial(did), nombre if var is None else None)
        if motivo:
            return motivo

        def hacer() -> None:
            vid = (var["id"] if var else self.ed.add_variable(nombre, crear[0], (crear[1] if isinstance(crear[1], dict) else {"kind": crear[1]}))) if nombre else None
            self.ed.update_draft_action(did, **self._campos_borrador(d, vid))
            self._completar(did)
        motivo = self._atomico("acción", hacer)
        if motivo is None:
            self._tras_borrador(did)
        return motivo

    def _completar(self, did: str) -> bool:
        """Si el borrador está unido a una etapa y no le falta nada, lo pasa al modelo (dentro de una operación agrupada)."""
        b = self._borrador(did)
        if b["tipo"] == "forzado":  # una orden: unida a una etapa y con destino y forma (y etapas, si es explícita)
            if not b.get("etapa") or self._faltan_orden(b):
                return False
            etapas = list(b.get("etapas", [])) if b["forma"] == "explicit" else None
            self.ed.add_force(b["etapa"], b["destino"], b["forma"], etapas)  # (un ciclo de forzado lo rechaza el núcleo)
            self.ed.delete_draft_actions([did])
            return True
        d = self._datos_borrador(b)
        if not b.get("etapa") or self.faltan(d, self._parcial_borrador(b)):
            return False
        vid = next(v["id"] for v in self.ed.model["variables"] if v["name"] == d["variable"])
        self._crear_o_cambiar(b["etapa"], d, None, vid)
        self.ed.delete_draft_actions([did])
        return True

    def _tras_borrador(self, did: str) -> None:
        """Deja la selección donde el borrador esté ahora: en el modelo (la última acción de su etapa) o sigue siendo un
        borrador."""
        if self._es_borrador(did):
            b = self._borrador(did)
            self.sel, self.accion = ([b["etapa"]], did) if b.get("etapa") else (self._ids_grupo(did), did)
        else:
            sid = next((a["stepRef"] for a in self.ed.model["actions"][-1:]), None)
            st = next((s for s in self.ed.model["steps"] if s["id"] == sid), None)
            self.sel, self.accion = ([sid], st["actionRefs"][-1]) if st else ([], None)
        self.cambiado.emit()

    def anadir_accion(self, sid: str) -> str:
        """«Añadir acción…» en una etapa: una acción continua unida a ella, sin variable todavía, y se abre Editar para
        completarla (si se cierra sin completar, queda con «?»)."""
        x, y = posiciones(self.M)[sid][0] - SX, posiciones(self.M)[sid][1]
        did = ""

        def hacer() -> None:
            nonlocal did
            did = self.ed.add_draft_action((ajustar(x + H + ACT_LINK), ajustar(y)), {"etapa": sid})
        motivo = self._atomico("añadir acción", hacer)
        if motivo:
            self.rechazar(motivo, sid)
            self.cambiado.emit()
            return ""
        self.sel, self.accion, self.ver_accion = [sid], did, True
        self.cambia()
        self.pedir_accion(sid, did)
        return did

    def _accion_por_borde(self, p: QPointF) -> dict[str, Any] | None:
        """La caja de acción de una etapa cuyo borde de tirar (`_borde_accion`) queda justo por fuera del punto, que no está
        sobre ninguna otra acción: el borde se agarra a los dos lados, como un punto de unión."""
        return next((c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if self._borde_accion(c, p)), None)

    def _borde_accion(self, caja: dict[str, Any], p: QPointF) -> str | None:
        """«der» o «abajo» si el punto está en el borde de la caja de una acción de una etapa del que se tira para sacar otra
        acción; None si no. Se agarra a los dos lados del borde, a BORDE_ACCION del dibujo (lo mismo que un punto de unión, y
        a cualquier zoom), sin pasar de un tercio del lado de la caja por dentro, para que el cuerpo siga agarrándose para
        seleccionar y mover. Depende de la colocación de las acciones de la etapa, que nunca cambia por esto: en «fila» y «fila
        separada», solo el borde derecho; en «columna», solo el inferior (la nueva va debajo); en «matriz 2», ninguno."""
        if not caja.get("etapa") or caja.get("forzado") or caja.get("suelta"):
            return None
        x, y, w, h = caja["rect"]
        colocacion = self.colocacion(caja["etapa"])
        if colocacion in ("fila", "fila-separada"):
            dentro = min(BORDE_ACCION, w / 3)
            return "der" if y <= p.y() <= y + h and x + w - dentro <= p.x() <= x + w + BORDE_ACCION else None
        if colocacion == "columna":
            dentro = min(BORDE_ACCION, h / 3)
            return "abajo" if x <= p.x() <= x + w and y + h - dentro <= p.y() <= y + h + BORDE_ACCION else None
        return None  # matriz de 2: la acción nueva no tiene un sitio evidente, se añade desde la etapa

    def anadir_accion_tras(self, aid: str, borde: str) -> str:
        """Tirar del borde de una acción de una etapa (el derecho en fila, el inferior en columna; `_borde_accion`): una acción
        nueva, vacía («?», como «Añadir acción…»), de la misma etapa y a continuación de aquella. La colocación de las acciones
        no cambia nunca. Un solo paso de deshacer (P-IMP-115). Una acción sin completar se coloca justo detrás; si la de la que
        se tira es del modelo, queda al final de las de su etapa (las sin completar van después de las completas)."""
        caja = next((c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] == aid), None)
        sid = caja["etapa"] if caja else None
        if not sid:
            return ""
        x, y = posiciones(self.M)[sid][0] - SX, posiciones(self.M)[sid][1]
        did = ""

        def hacer() -> None:
            nonlocal did
            did = self.ed.add_draft_action((ajustar(x + H + ACT_LINK), ajustar(y)), {"etapa": sid})
            if self._es_borrador(aid):
                self._pegar_a_etapa([did], sid, aid)
        motivo = self._atomico("nueva acción desde una acción", hacer)
        if motivo:
            self.rechazar(motivo, sid)
            self.cambiado.emit()
            return ""
        self.sel, self.accion, self.ver_accion = [sid], did, True
        self.cambia()
        self.pedir_accion(sid, did)
        return did

    def tipo_accion(self, ident: str, tipo: str) -> None:
        """Cambia el tipo de una acción desde el botón derecho. Una acción completa conserva su ID y su lugar. Si el tipo
        pide datos que no hay (variable booleana, valor, condición, evento), la acción queda como borrador con «?» en lo
        que falta, con el tipo ya puesto: si falta la variable o el valor se abre Editar; la condición y el evento se
        programan en el panel de opciones, que se muestra al seleccionarla. Una «Continua» no lleva condición y sale del
        tipo «limitada» (de ficheros antiguos) sin su límite."""
        d = self.datos_accion(ident)
        if d["tipo"] == tipo or (d["tipo"] == "limitada" and tipo == "condicionada"):
            return
        parcial = self._parcial(ident)
        antes = set(self.faltan(d, parcial))
        d["tipo"] = tipo
        d["limite"] = ""
        if tipo == "continua":
            d["condicion"] = ""
        falta = self.faltan(d, parcial)
        if "variable" in falta:
            d["variable"] = ""  # no sirve para el tipo nuevo (o no había): se vuelve a elegir
        abrir = bool((set(falta) - antes) & {"variable", "valor"})
        if self._es_borrador(ident):
            sid = self._borrador(ident).get("etapa")
            motivo = self._atomico("tipo de acción", lambda: (
                self.ed.update_draft_action(ident, tipo=tipo, variable=self._id_variable(d["variable"]),
                                            condicion=d.get("condicion", ""), limite=""),
                self._completar(ident)))
            self._decir(motivo)
            if motivo:
                self.parpadear([ident])
            self._tras_borrador(ident)
            if motivo is None and self._es_borrador(ident) and abrir:
                self.pedir_accion(sid, ident)
            return
        sid = self.ed.get(ident)["stepRef"]
        if not falta:  # completa: se cambia en su sitio
            self._decir(self.poner_accion(sid, d, ident))
            self.cambiado.emit()
            return
        self.separar_como_borrador(ident, d, sid, abrir)

    def _id_variable(self, nombre: str) -> str | None:
        return next((v["id"] for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None

    def _a_borrador(self, aid: str, d: dict[str, str], sid: str, vid: str | None = None) -> str:
        """Una acción del modelo que ya no está completa pasa a ser un borrador unido a su etapa (al final de su fila), con
        los datos `d` (y la variable `vid`, si no se da, la de nombre `d["variable"]`). Devuelve su ID nuevo."""
        px, py = posiciones(self.M)[sid]
        nuevo = self.ed.add_draft_action((ajustar(px - SX + H + ACT_LINK), ajustar(py)), {
            "tipo": d["tipo"], "etapa": sid, "variable": vid or self._id_variable(d["variable"]),
            **{k: d[k] for k in ("condicion", "valor", "evento", "limite") if d.get(k)}})
        self.ed.delete([aid])
        return nuevo

    def separar_como_borrador(self, aid: str, d: dict[str, str], sid: str, abrir: bool = True) -> None:
        """Una acción del modelo a la que le faltan datos tras cambiar de tipo: pasa a ser un borrador unido a su etapa
        (al final de su fila); con `abrir`, se abre Editar."""
        nuevo = ""

        def hacer() -> None:
            nonlocal nuevo
            nuevo = self._a_borrador(aid, d, sid)
        motivo = self._atomico("tipo de acción", hacer)
        self._decir(motivo)
        if motivo:
            self.parpadear([aid])
        if motivo is None:
            self.sel, self.accion = [sid], nuevo
            self.cambiado.emit()
            if abrir:
                self.pedir_accion(sid, nuevo)

    def quitar_accion(self, aid: str) -> None:
        if self._es_borrador(aid):
            self.ed.delete_draft_actions([aid])
        else:
            self.ed.delete([aid])
        self.accion = None
        self.sel = [s for s in self.sel if s != aid]
        self.cambia()

    def mover_accion(self, aid: str, delta: int) -> None:
        if self._es_borrador(aid):
            return  # los borradores van al final de la fila, en el orden en que se unieron
        self._decir(self._atomico("mover acción", lambda: self.ed.move_action(aid, delta)))

    # -- la condición y el evento de una acción, en el panel de opciones (P-IMP-43)
    def accion_activa(self) -> str | None:
        """La acción cuyas opciones se muestran: una acción suelta seleccionada (o la única seleccionada), o la señalada de la
        etapa seleccionada si se abrió (clic en su caja, «Editar…»). None si lo que se muestra es otra cosa."""
        vivas = {a["id"]: a["stepRef"] for a in self.ed.model["actions"]}
        vivas.update({b["id"]: b.get("etapa") for b in self.ed.draft_actions() if b["tipo"] != "forzado"})  # (una orden no es una acción)
        if self.accion in vivas and (self.accion in self.sel or (self.ver_accion and vivas[self.accion] in self.sel)):
            return self.accion
        if len(self.sel) == 1 and self.sel[0] in vivas:
            return self.sel[0]
        return None

    def accion_programable(self) -> tuple[str, str] | None:
        """La acción cuya condición o evento se programa con bloques en el panel de opciones: la que muestra `accion_activa`
        si es condicionada (condición) o por evento (evento); (ID, «condicion» o «evento»). None si no hay."""
        aid = self.accion_activa()
        if aid is None:
            return None
        tipo = self.datos_accion(aid)["tipo"]
        return (aid, "evento" if tipo == "evento" else "condicion") if tipo in (*CON_CONDICION, "evento") else None

    def etapa_accion(self, aid: str) -> str | None:
        """La etapa a la que está unida la acción (del modelo o borrador); None si es suelta."""
        b = next((b for b in self.ed.draft_actions() if b["id"] == aid), None)
        return (b.get("etapa") if b else self.ed.get(aid)["stepRef"]) or None

    def titulo_accion(self, aid: str, campo: str) -> str:
        """«Condición de la acción Q00 (etapa 1)» o «Evento de la acción …»."""
        d = self.datos_accion(aid)
        b = next((b for b in self.ed.draft_actions() if b["id"] == aid), None)
        sid = b.get("etapa") if b else self.ed.get(aid)["stepRef"]
        donde = f"etapa {self._nom(sid)}" if sid else "suelta"
        return f"{'Evento' if campo == 'evento' else 'Condición'} de la acción {d['variable'] or '?'} ({donde})"

    def texto_accion(self, aid: str, campo: str) -> str:
        """La condición o el evento de una acción, en la notación del usuario."""
        return self.datos_accion(aid).get(campo, "")

    def poner_texto_accion(self, aid: str, campo: str, texto: str, crear: bool = False) -> str | None:
        """Escribe la condición (o el evento) de una acción: una operación de deshacer. Si con ello la acción queda
        completa (con variable, y unida a una etapa), pasa al modelo; si deja de estarlo (texto vacío, a medias o con
        variables que no existen), pasa a ser un borrador. Con `crear`, declara antes como entradas booleanas las variables
        que no existan. Devuelve el motivo si no se pudo (un nombre que no vale); nada cambia en ese caso."""
        texto = texto.strip()
        d = self.datos_accion(aid)
        d[campo] = texto
        if crear:
            for nombre in self.sin_declarar(aid, texto):
                motivo = self.motivo_nombre(nombre)
                if motivo:
                    self.rechazar(motivo, aid)
                    self.cambiado.emit()
                    return motivo
        nuevo = [aid]

        def hacer() -> None:
            if crear:
                for nombre in self.sin_declarar(aid, texto):
                    self.ed.add_variable(nombre, "input", {"kind": "bool"})
            if self._es_borrador(aid):
                self.ed.update_draft_action(aid, **{campo: texto})
                if self._completar(aid):
                    nuevo[0] = self.ed.model["actions"][-1]["id"]
                return
            sid = self.ed.get(aid)["stepRef"]
            if self.faltan(d, self.parcial_de(sid)):
                nuevo[0] = self._a_borrador(aid, d, sid)
            else:
                self._crear_o_cambiar(sid, d, aid, self._id_variable(d["variable"]))
        señalada, seleccion = self.accion == aid, list(self.sel)
        motivo = self._atomico("condición de la acción" if campo == "condicion" else "evento de la acción", hacer)
        if motivo:
            self.mensaje = motivo
            self.cambiado.emit()
            return motivo
        if nuevo[0] != aid:  # cambió de ID (pasó al modelo o salió de él): la selección la sigue
            self.sel = [nuevo[0] if i == aid else i for i in seleccion]
            self.accion = nuevo[0] if señalada else self.accion
            self.cambiado.emit()
        return None

    # -- variables (REQ-EDT-07, P-IMP-38) ------------------------------------------------------------
    def variables(self) -> list[dict[str, Any]]:
        """El diccionario: cada variable con cuántos usos tiene (expresiones y acciones que la escriben)."""
        m = self.ed.model
        return [dict(v, usos=len(self.ed.usages(v["id"])) + sum(a["targetRef"] == v["id"] for a in m["actions"]))
                for v in m["variables"]]

    def nueva_variable(self, nombre: str, papel: str = "input", tipo: dict[str, Any] | None = None) -> str | None:
        """Crea una variable (una operación de deshacer); devuelve el motivo si el nombre no es válido o está repetido."""
        def hacer() -> None:
            motivo = self.motivo_nombre(nombre) if nombre.strip() else None
            if motivo:
                raise DiagnosticError(Diagnostic("D-FORMATO", motivo))
            if not valid_label(nombre):  # como al renombrar
                raise DiagnosticError(Diagnostic("D-FORMATO", f"nombre inválido: de 1 a {MAX_LABEL} caracteres"))
            self.ed.add_variable(nombre, papel, tipo or {"kind": "bool"})
        return self._atomico("crear variable", hacer)

    def cambiar_variable(self, vid: str, nombre: str | None = None, **cambios: Any) -> str | None:
        """Cambia nombre (y el texto de sus usos), papel, tipo, unidad o valor inicial, en una sola operación."""
        v = next(x for x in self.ed.model["variables"] if x["id"] == vid)

        def hacer() -> None:
            if nombre is not None and nombre != v["name"]:
                motivo = self.motivo_nombre(nombre) if nombre.strip() else None
                if motivo:
                    raise DiagnosticError(Diagnostic("D-FORMATO", motivo))
                self.ed.rename(vid, nombre)
            if cambios:
                self.ed.change_variable(vid, **cambios)
        return self._atomico("cambiar variable", hacer)

    def quitar_variable(self, vid: str) -> str | None:
        return self._atomico("quitar variable", lambda: self.ed.delete_variable(vid))

    def fuente_bloques(self) -> tuple[dict[str, tuple[str, str]], list[str]]:
        """Lo que ofrece el programador por bloques: variables {nombre: (papel, tipo)} y etapas en notación X."""
        m = self.ed.model
        return ({v["name"]: (v["role"], v["type"]["kind"]) for v in m["variables"]}, [x_etapa(s["label"]) for s in m["steps"]])

    # -- el parcial de lo que se crea (P-IMP-23, P-IMP-27) --------------------------------------------------
    # Lo que se suelta dentro del marco de un parcial (un recinto, la expansión de una macroetapa) es de ese parcial; fuera
    # de todo marco, del raíz. Una transición o una etapa que nace de otra (arrastrando de su punto de unión, «Añadir
    # debajo», un salto) es del parcial de aquella. Mover un elemento a otro marco es solo de presentación: no cambia su
    # parcial. Las barras y las acciones sueltas no tienen parcial (son presentación); una acción unida es de su etapa.
    def parcial_en(self, p: QPointF) -> str:
        """El parcial en cuyo marco cae el punto del dibujo (el más pequeño, si hay varios). La expansión de una macroetapa
        no se dibuja con marco, pero cuenta como el rectángulo de sus etapas y transiciones. Si no cae en ningún marco pero
        sí en el margen que se le da a un parcial que no es el raíz (MARGEN_SUELTA, a su derecha y debajo: sitio para la etapa
        o la transición que sigue), es de ese parcial; con varios márgenes a la vez, el del más cercano. El margen nunca
        quita lo que cae dentro del marco de otro parcial. En cualquier otro punto, el raíz."""
        x, y, cajas = p.x(), p.y(), cajas_parciales(self.M)
        dentro = [((b["x1"] - b["x0"]) * (b["y1"] - b["y0"]), pid) for pid, b in cajas.items()
                  if b["x0"] <= x <= b["x1"] and b["y0"] <= y <= b["y1"]]
        if dentro:
            return min(dentro)[1]
        cerca = [(max(0.0, x - b["x1"]) ** 2 + max(0.0, y - b["y1"]) ** 2,  # lo que dista del marco; el más cercano manda
                  (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]), pid)
                 for pid, b in cajas.items()
                 if pid != self.raiz and b["x0"] <= x <= b["x1"] + MARGEN_SUELTA and b["y0"] <= y <= b["y1"] + MARGEN_SUELTA]
        return min(cerca)[2] if cerca else self.raiz

    def parcial_de(self, ident: str) -> str:
        """El parcial de una etapa, una transición o una macroetapa (el raíz si no se conoce)."""
        m = self.ed.model
        for x in m["steps"] + m["transitions"] + m["hierarchy"]["macros"]:
            if x["id"] == ident:
                return x["partialRef"]
        return self.raiz

    def _pasos(self) -> set[str]:
        """Las etapas y las macroetapas: lo que se enlaza con las transiciones como una etapa."""
        return {s["id"] for s in self.M["steps"]} | {x["id"] for x in self.M.get("macros", [])}

    # -- operaciones -------------------------------------------------------------------------------
    def poner_etapa(self, p: QPointF, inicial: bool = False, tipo: str = "ordinary") -> str:
        """Una etapa (o, con `tipo` «enclosing», una encapsulante) en el punto dado, en el parcial de su marco."""
        sid = self.ed.add_step(self.parcial_en(p), self.ed.next_label("step"), inicial, tipo, at=self._modelo(p))
        self.sel = [sid]
        self.cambia()
        return sid

    def poner_transicion(self, p: QPointF, pedir: bool = False) -> str:
        """Una transición sin receptividad (pendiente: D-EXP-PENDIENTE) en el punto dado, en el parcial de su marco. La
        receptividad se escribe después, en el panel de propiedades o con doble clic."""
        tid, _ = self.ed.add_transition(self.parcial_en(p), "", at=self._modelo(p), label=self.ed.next_label("transition"))
        self.sel = [tid]
        self.cambia()
        if pedir:
            self.pedir_condicion(tid)
        return tid

    def nombre(self, ident: str) -> str:
        """Nombre visible de un elemento o de un enlace («E0 → t1»)."""
        barra_ = next((b for b in self.M.get("bars", []) if b["id"] == ident), None)
        if barra_:
            return barra_["label"]
        if self.es_orden_suelta(ident):
            return f"orden de forzado {self._texto_orden(self._borrador(ident), self._nombres_vivos())}"
        if self._es_borrador(ident) or any(a["id"] == ident for a in self.ed.model["actions"]):
            d = self.datos_accion(ident)
            return f"acción {d['variable'] or '?'}" + ("" if self._es_borrador(ident) else
                                                      f" ({self.nombres.get(self.ed.get(ident)['stepRef'], '')})")
        if ident.startswith("enlaceacc:"):
            sid = ident.split(":", 1)[1]
            return f"enlace de las acciones de la etapa {self._nom(sid)}"
        if any(p["id"] == ident for p in self.ed.model["partials"]):  # un parcial con marco: «recinto G1» o «expansión de M1»
            rol = self.ed.partial_roles()[ident]
            if rol["kind"] == "enclosure":
                return f"recinto {self._nom(ident)}"
            if rol["kind"] == "expansion":
                return f"expansión de {self._nom(rol['macro'])}"
        if "|" in ident:
            tid, sid, rol = ident.split("|")
            if rol == "barra":
                b = next((b for b in self.M.get("bars", []) if b["id"] == tid), None)
                return f"{self._nom(sid)} — {b['label'] if b else 'barra'}"
            a, b = (sid, tid) if rol == "pre" else (tid, sid)
            return f"{self._nom(a)} → {self._nom(b)}"
        return self._nom(ident)

    def poner_barra(self, p: QPointF, tipo: str) -> str:
        """Una barra de simultaneidad (Y, doble trazo) o de alternativa (O, trazo simple) centrada en el punto dado."""
        x, y = self._modelo(p)
        bid = self.ed.add_bar(tipo, (ajustar(x - 60), y))
        self.sel = [bid]
        self.cambia()
        return bid

    # -- jerarquías: macroetapas, encapsulantes y recintos (P-IMP-23..27; REQ-EDT-08, REQ-JER-04, 05, 07) --------------
    # Todo va por las operaciones de grafcet/editor.py (add_macro, set_step_kind, new_enclosure, set_activation): un rechazo
    # del núcleo (un diagnóstico) se muestra como cualquier otro, con el parpadeo naranja, y no deja nada a medias.
    @staticmethod
    def _toca(a: QRectF, b: QRectF) -> bool:
        """Si dos rectángulos se tocan o se cruzan (también con alto 0, como una barra de alternativa)."""
        return a.left() <= b.right() and b.left() <= a.right() and a.top() <= b.bottom() and b.top() <= a.bottom()

    def _libre(self, zona: QRectF) -> bool:
        """Si la zona del dibujo no toca ningún elemento (etapas, macroetapas, transiciones, barras, acciones) ni marco."""
        if any(self._toca(zona, r) for _, r, _ in self._elementos()):
            return False
        return not any(self._toca(zona, QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"]))
                       for b in cajas_parciales(self.M).values())

    def _columna_expansion(self, x: int, y: int) -> int | None:
        """La columna (x del modelo) de la expansión de una macroetapa colocada en (x, y): a EXP_DX de ella y, si esa zona no
        está libre (con el margen de los marcos), cada vez más a la derecha. La entrada va a la altura de la macroetapa y la
        salida EXP_DY más abajo. None si no hay hueco en EXP_INTENTOS columnas."""
        m = MARGEN_SOLAPE
        for k in range(EXP_INTENTOS):
            xe = x + EXP_DX + k * EXP_PASO
            zona = QRectF(xe + SX - H - 26, y - H - 22, 2 * H + 96, EXP_DY + 2 * H + 44).adjusted(-m, -m, m, m)
            if self._libre(zona):
                return xe
        return None

    def _etiqueta_libre(self, prefijo: str, usadas: set[str]) -> str:
        """M1, M2… (o G1, G2…): el primero cuyo nombre no está en `usadas` (claves de `label_key`)."""
        n = 1
        while label_key(f"{prefijo}{n}") in usadas:
            n += 1
        return f"{prefijo}{n}"

    def poner_macro(self, p: QPointF) -> str | None:
        """La ficha «Macroetapa» soltada en el dibujo: la macroetapa, en el parcial de su marco (`parcial_en`: dentro de un
        recinto o de otra expansión, queda anidada), con su expansión: un parcial nuevo con la etapa de entrada y la de
        salida, a la derecha en la primera columna libre, unidas a la macroetapa por los trazos discontinuos del dibujo. Se
        rellena soltando etapas y transiciones dentro de su zona. Una sola operación de deshacer. Devuelve el ID de la
        macroetapa, o None si no se pudo (el motivo, en el mensaje)."""
        x, y = self._modelo(p)
        parcial, xe = self.parcial_en(p), self._columna_expansion(x, y)
        if xe is None:
            self.rechazar(MSG_SIN_SITIO)
            self.cambiado.emit()
            return None
        m = self.ed.model
        etiqueta = self._etiqueta_libre("M", {label_key(a["label"]) for a in m["hierarchy"]["macros"] + m["partials"]})
        hecho: list[Any] = []

        def hacer() -> None:
            ids = self.ed.add_macro(parcial, etiqueta, at=(x, y))
            self.ed.move(ids.entry, xe, y)
            self.ed.move(ids.exit, xe, y + EXP_DY)
            hecho.append(ids)
        motivo = self._atomico("colocar macroetapa", hacer)
        if motivo:
            self.rechazar(motivo)
            self.cambiado.emit()
            return None
        ids = hecho[0]
        self.sel, self.accion = [ids.macro], None
        self.informar(f"Macroetapa {etiqueta} con su expansión a la derecha: de la entrada {self.nombres.get(ids.entry, '?')} "
                      f"a la salida {self.nombres.get(ids.exit, '?')}. Suelte etapas y transiciones dentro de ella para "
                      "rellenarla (botón derecho en la macroetapa, «Encuadrar la expansión», para verla).")
        self.cambiado.emit()
        return ids.macro

    def _esquina_parcial(self, p: QPointF) -> tuple[int, int]:
        """La esquina superior izquierda (x, y del modelo, en la rejilla) del marco de un grafcet parcial nuevo soltado en p: el
        marco queda centrado en el punto, como una etapa."""
        return ajustar(p.x() - SX - VACIO_W / 2), ajustar(p.y() - VACIO_H / 2)

    def poner_parcial(self, p: QPointF) -> str | None:
        """La ficha «Grafcet parcial» soltada en un hueco del dibujo (o «Nuevo grafcet parcial aquí» del botón derecho): un
        grafcet parcial nuevo y vacío (`add_partial`, fuera de toda jerarquía), con el primer nombre libre G1, G2… y su marco vacío
        centrado en el punto (su posición se guarda en la presentación, como la de un recinto vacío); se rellena soltando etapas
        y transiciones dentro de él. Encima de un elemento o de otro marco no crea nada y avisa. Una sola operación de deshacer.
        Devuelve el ID del parcial, o None."""
        if self._huella_ficha("parcial", p):
            self.informar(MSG_SOLAPE_PARCIAL)
            self.cambiado.emit()
            return None
        x, y = self._esquina_parcial(p)
        m = self.ed.model
        nombre = self._etiqueta_libre("G", {label_key(a["label"]) for a in m["hierarchy"]["macros"] + m["partials"]})
        hecho: list[str] = []

        def hacer() -> None:
            pid = self.ed.add_partial(nombre)
            self.ed.move(pid, x, y)
            hecho.append(pid)
        motivo = self._atomico("colocar grafcet parcial", hacer, hueco=False)
        if motivo:
            self.rechazar(motivo)
            self.cambiado.emit()
            return None
        self.sel, self.accion = [hecho[0]], None
        self.informar(f"Grafcet parcial {nombre}: suelte etapas y transiciones dentro de su marco para rellenarlo; una orden de "
                      "forzado de otra etapa puede forzarlo («Forzado» en la paleta).")
        self.cambiado.emit()
        return hecho[0]

    def renombrar_parcial(self, pid: str) -> str | None:
        """«Renombrar…» en un grafcet parcial suelto (también el doble clic en su marco): pide el nombre, con el actual de
        propuesta, y lo cambia (`rename`: único entre los parciales; el texto de las fórmulas que lo nombran se actualiza).
        Una sola operación de deshacer. Devuelve el nombre nuevo, o None (cancelado, igual o rechazado)."""
        parte = next((q for q in self.ed.model["partials"] if q["id"] == pid), None)
        if parte is None or pid == self.raiz:
            return None
        actual = parte["label"]
        nuevo = self.pedir_texto("Renombrar el grafcet parcial", f"Nuevo nombre del grafcet parcial {actual}:", actual)
        if nuevo is None or nuevo.strip() == actual:
            return None
        nuevo = nuevo.strip()
        motivo = self._atomico("renombrar el grafcet parcial", lambda: self.ed.rename(pid, nuevo), hueco=False)
        if motivo:
            self.rechazar(motivo, pid)
            self.cambiado.emit()
            return None
        self.cambiado.emit()
        return nuevo

    def _es_parcial_suelto(self, ident: str) -> bool:
        """Si el ID es el de un parcial que no es el raíz, ni un recinto, ni una expansión: un grafcet parcial suelto."""
        return ident != self.raiz and self.ed.partial_roles().get(ident, {}).get("kind") == "root"

    def tipo_encapsulante(self, sid: str, encapsulante: bool = True) -> None:
        """«Encapsulante» (esquinas cortadas en el dibujo) o «Etapa» (si no tiene recintos) del submenú «Tipo de etapa»:
        `set_step_kind`, una operación de deshacer. El núcleo rechaza lo demás (la entrada o la salida de una
        expansión, o una encapsulante con recintos): el aviso en rojo y el parpadeo de la etapa."""
        motivo = self._atomico("convertir en encapsulante" if encapsulante else "devolver a ordinaria",
                               lambda: self.ed.set_step_kind(sid, "enclosing" if encapsulante else "ordinary"))
        if motivo:
            self.rechazar(motivo, sid)
        elif encapsulante:
            self.informar(f"La etapa {self._nom(sid)} es ahora una encapsulante: botón derecho, "
                          "«Añadir recinto…», para darle recintos.")
        self.cambiado.emit()

    def cambiar_tipo_etapa(self, ident: str, tipo: str) -> None:
        """«Tipo de etapa» (el submenú del botón derecho y las casillas del panel): `tipo` es «ordinary», «enclosing» o
        «macro». Entre etapa ordinaria y encapsulante, `tipo_encapsulante`. A macroetapa: `set_step_kind` crea la
        expansión con su entrada y su salida, que se colocan a la derecha como las de la ficha «Macroetapa»
        (`poner_macro`); de macroetapa a etapa, la expansión solo puede tener su entrada y su salida (si no, se
        rechaza: «vacíe la expansión antes»). El elemento conserva su ID, su nombre y su lugar. Una sola operación de
        deshacer; un rechazo del núcleo es el aviso en rojo y el parpadeo del elemento, y no cambia nada."""
        m = self.ed.model
        es_macro = any(x["id"] == ident for x in m["hierarchy"]["macros"])
        actual = "macro" if es_macro else next((s["kind"] for s in m["steps"] if s["id"] == ident), None)
        if actual == tipo:
            self.cambiado.emit()
            return
        if actual in ("ordinary", "enclosing") and tipo != "macro":
            self.tipo_encapsulante(ident, tipo == "enclosing")
            return
        x = y = xe = 0
        if tipo == "macro":
            px, py = posiciones(self.M)[ident]
            x, y = px - SX, py
            sitio = self._columna_expansion(x, y)
            if sitio is None:
                self.rechazar(MSG_SIN_SITIO, ident)
                self.cambiado.emit()
                return
            xe = sitio

        def hacer() -> None:
            self.ed.set_step_kind(ident, tipo)
            if tipo == "macro":
                info = self.ed.macro_info(ident)
                self.ed.move(info.entry, xe, y)
                self.ed.move(info.exit, xe, y + EXP_DY)
        motivo = self._atomico("convertir en macroetapa" if tipo == "macro" else "convertir en etapa", hacer)
        if motivo:
            self.rechazar(motivo, ident)
            self.cambiado.emit()
            return
        self.sel, self.accion = [ident], None
        if tipo == "macro":
            info = self.ed.macro_info(ident)
            self.informar(f"La etapa {self._nom(ident)} es ahora una macroetapa con su expansión a la derecha: de la "
                          f"entrada {self.nombres.get(info.entry, '?')} a la salida "
                          f"{self.nombres.get(info.exit, '?')}.")
        else:
            clase = "encapsulante" if tipo == "enclosing" else "ordinaria"
            self.informar(f"La macroetapa {self._nom(ident)} es ahora una etapa {clase}; su expansión vacía se borró.")
        self.cambiado.emit()

    def _sitio_recinto(self, sid: str) -> tuple[int, int]:
        """Dónde va el marco vacío de un recinto nuevo de la encapsulante `sid`: a la derecha de ella, a la altura de su
        parte de arriba y en el primer hueco libre (esquina superior izquierda, en coordenadas del modelo)."""
        ox, oy = posiciones(self.M)[sid]
        y0, m = ajustar(oy - H - 22), MARGEN_SOLAPE
        for k in range(EXP_INTENTOS):
            x0 = ajustar(ox + RECINTO_DX + k * (VACIO_W + RECINTO_PASO) - SX)
            if self._libre(QRectF(x0 + SX, y0, VACIO_W, VACIO_H + 20).adjusted(-m, -m, m, m)):  # +20: su nombre, debajo
                return x0, y0
        return ajustar(ox + RECINTO_DX - SX), y0

    def anadir_recinto(self, sid: str) -> str | None:
        """«Añadir recinto…» en una encapsulante: pide el nombre (G1, G2… propuesto: el primero libre entre los parciales y las
        macroetapas, como el de un grafcet parcial suelto) y crea el recinto (`new_enclosure`): un
        parcial vacío dentro del de la encapsulante, sin etapa de enlace de activación todavía. Se ve como un marco vacío a
        la derecha de la encapsulante (su posición se guarda en la presentación) y se rellena soltando etapas dentro de él.
        Una sola operación de deshacer. Devuelve el ID del parcial del recinto, o None (cancelado o rechazado)."""
        if not any(s["id"] == sid for s in self.ed.model["steps"]):
            return None
        m = self.ed.model
        usadas = {label_key(a["label"]) for a in m["hierarchy"]["macros"] + m["partials"]}
        nombre = self.pedir_texto("Añadir recinto", f"Nombre del recinto de la encapsulante {self._nom(sid)}:",
                                  self._etiqueta_libre("G", usadas))
        if nombre is None:
            return None
        nombre, hecho = nombre.strip(), []
        x, y = self._sitio_recinto(sid)

        def hacer() -> None:
            ids = self.ed.new_enclosure(sid, nombre)
            self.ed.move(ids.partial, x, y)
            hecho.append(ids)
        motivo = self._atomico("añadir recinto", hacer)
        if motivo:
            self.rechazar(motivo, sid)
            self.cambiado.emit()
            return None
        self.sel, self.accion = [hecho[0].partial], None
        self.informar(f"Recinto {nombre} de la encapsulante {self._nom(sid)}: suelte etapas dentro de su marco "
                      "para rellenarlo; botón derecho en una etapa suya, «Enlace de activación», la marca (*).")
        self.cambiado.emit()
        return hecho[0].partial

    def enlace_activacion(self, sid: str, marcar: bool | None = None) -> None:
        """Marca o desmarca (sin `marcar`, alterna) el enlace de activación de una etapa de un recinto (el «*» del dibujo):
        `set_activation`, una operación de deshacer. Una etapa que no es de un recinto lo rechaza el núcleo."""
        rol = self.ed.partial_roles().get(self.parcial_de(sid))
        actual = bool(rol and rol["kind"] == "enclosure" and sid in rol["activation"])
        on = (not actual) if marcar is None else marcar
        motivo = self._atomico("enlace de activación" if on else "quitar el enlace de activación",
                               lambda: self.ed.set_activation(sid, on))
        if motivo:
            self.rechazar(motivo, sid)
        self.cambiado.emit()

    # -- encuadrar: llevar a la vista lo que está al otro lado de una dependencia (REQ-EDT-08, REQ-JER-07) ----------------
    def _caja_encuadre(self, ident: str) -> QRectF | None:
        """La caja del dibujo que se encuadra para mostrar un elemento: el marco de un parcial (un recinto, un grafcet parcial o
        la zona de una expansión, con su nombre debajo) o un cuadrado de ENCUADRE de semilado alrededor de una etapa o una
        macroetapa; None si no está dibujado."""
        b = cajas_parciales(self.M).get(ident)
        if b is not None:
            return QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"]).adjusted(-10, -10, 10, 18)
        p = posiciones(self.M).get(ident)
        return QRectF(p[0] - ENCUADRE, p[1] - ENCUADRE, 2 * ENCUADRE, 2 * ENCUADRE) if p is not None else None

    def encuadrar(self, destino: list[str], texto: str = "") -> bool:
        """Encuadra `destino` (los ID de lo que se quiere ver: la expansión, la macroetapa, el recinto o la encapsulante): lo
        selecciona, encaja y centra en la vista su caja, o la de todos juntos (`VistaDiagrama.encuadrar`: el zoom que los hace
        caber con margen, sin pasar del tope de «Centrar todo»), lo resalta con el parpadeo naranja de la edición para que
        aparezca en primer plano y avisa con `texto`. Es solo navegación: no toca el modelo, el historial ni la marca de
        cambios. Devuelve si había algo dibujado que encuadrar."""
        cajas = [c for c in (self._caja_encuadre(i) for i in destino) if c is not None]
        if not cajas:
            return False
        r = cajas[0]
        for c in cajas[1:]:
            r = r.united(c)
        self.sel, self.accion = list(destino), None
        if texto:
            self.informar(texto)
        self.cambiado.emit()
        if hasattr(self.diagrama, "encuadrar"):
            self.diagrama.encuadrar(r)
        self.parpadear(destino, centrar=False)  # (la vista ya está encuadrada)
        return True

    def encuadrar_expansion(self, mid: str) -> bool:
        """«Encuadrar la expansión» (REQ-EDT-08, REQ-JER-07), también el doble clic en una macroetapa: encuadra la zona de su
        expansión (`encuadrar`) y deja su parcial seleccionado. Devuelve si la macroetapa tiene expansión."""
        try:
            info = self.ed.macro_info(mid)
        except DiagnosticError as exc:
            self.rechazar("; ".join(self.sust(d.message) for d in exc.diagnostics), mid)
            self.cambiado.emit()
            return False
        return self.encuadrar([info.partial], f"Expansión de la macroetapa {self._nom(mid)}: de la entrada "
                              f"{self.nombres.get(info.entry, '?')} a la salida {self.nombres.get(info.exit, '?')}.")

    def encuadrar_macroetapa(self, mid: str) -> bool:
        """«Encuadrar la macroetapa»: al revés que «Encuadrar la expansión», desde la entrada o la salida de una expansión o
        desde su zona."""
        return self.encuadrar([mid], self.descripcion_jerarquia(mid) or self.nombre(mid))

    def encuadrar_encapsulante(self, sid: str) -> bool:
        """«Encuadrar la encapsulante», desde una etapa de un recinto o desde su marco."""
        return self.encuadrar([sid], self.descripcion_jerarquia(sid) or self.nombre(sid))

    def encuadrar_recintos(self, sid: str) -> bool:
        """«Encuadrar el recinto» (o «los recintos», si la encapsulante tiene varios), desde la encapsulante: encuadra el marco
        de cada uno, juntos, y los deja seleccionados."""
        recintos = [r["partialRef"] for r in self.ed.model["hierarchy"]["enclosures"] if r["ownerStepRef"] == sid]
        nom = self.descripcion_jerarquia(recintos[0]) if len(recintos) == 1 else \
            f"Recintos de la encapsulante {self._nom(sid)}: {', '.join(self._nom(r) for r in recintos)}"
        return bool(recintos) and self.encuadrar(recintos, nom)

    def renombrar_macro(self, mid: str) -> str | None:
        """«Renombrar…» en una macroetapa: pide el nombre y cambia el de la macroetapa y, si se llamaba igual que ella (lo que
        pone la ficha «Macroetapa»), el de su expansión, para que el nombre siga único; el texto de las fórmulas que la usan
        se actualiza (`rename`). Una sola operación de deshacer. Devuelve el nuevo nombre, o None."""
        mac = next((x for x in self.ed.model["hierarchy"]["macros"] if x["id"] == mid), None)
        if mac is None:
            return None
        actual = mac["label"]
        nuevo = self.pedir_texto("Renombrar la macroetapa", f"Nuevo nombre de la macroetapa {actual}:", actual)
        if nuevo is None or nuevo.strip() == actual:
            return None
        nuevo = nuevo.strip()

        def hacer() -> None:
            info = self.ed.macro_info(mid)
            con_ella = next(p["label"] for p in self.ed.model["partials"] if p["id"] == info.partial) == actual
            self.ed.rename(mid, nuevo)
            if con_ella:
                self.ed.rename(info.partial, nuevo)
        motivo = self._atomico("renombrar la macroetapa", hacer)
        if motivo:
            self.rechazar(motivo, mid)
            self.cambiado.emit()
            return None
        self.cambiado.emit()
        return nuevo

    # -- la ficha de jerarquía: lo que el botón derecho y el panel de opciones ofrecen de un mismo elemento ---------------
    def acciones_jerarquia(self, ident: str) -> list[tuple[str, Callable[[], Any], bool | None]]:
        """Las acciones de jerarquía de una macroetapa, una etapa, un parcial con marco o una orden de forzado, como
        [(texto, función, estado)]: `estado` es None si es un botón, y True o False si es una casilla (marcada o no). Son las
        opciones del botón derecho (`menu`) y los botones de la ficha del panel de opciones (`ficha_jerarquia`): ninguna
        toca el modelo si no lo dice (encuadrar) y las demás son una operación de deshacer. Encuadrar lleva la vista al otro
        lado de una dependencia: de la macroetapa a su expansión y al revés, de la encapsulante a su(s) recinto(s) y al
        revés."""
        m = self.ed.model
        if any(x["id"] == ident for x in m["hierarchy"]["macros"]):
            return [*self._tipos_etapa(ident, "macro"),
                    ("Encuadrar la expansión", lambda: self.encuadrar_expansion(ident), None),
                    ("Renombrar…", lambda: self.renombrar_macro(ident), None)]
        if self.es_orden_suelta(ident):  # una orden sin completar: se configura y se quita
            return [("Configurar orden de forzado…", lambda: self.configurar_orden(ident), None),
                    ("Quitar orden de forzado", lambda: self.quitar_orden(ident), None)]
        if any(f["id"] == ident for f in m["forces"]):
            return [("Editar orden de forzado…", lambda: self.editar_orden(ident), None),
                    ("Quitar orden de forzado", lambda: self.quitar_orden(ident), None)]
        roles = self.ed.partial_roles()
        if ident in roles:  # un parcial con marco: a la encapsulante o a la macroetapa que lo contiene; un parcial suelto se renombra
            rol = roles[ident]
            if rol["kind"] == "enclosure":
                return [("Encuadrar la encapsulante", lambda: self.encuadrar_encapsulante(rol["ownerStep"]), None)]
            if rol["kind"] == "expansion":
                return [("Encuadrar la macroetapa", lambda: self.encuadrar_macroetapa(rol["macro"]), None)]
            return [("Renombrar…", lambda: self.renombrar_parcial(ident), None)] if self._es_parcial_suelto(ident) else []
        st = next((s for s in m["steps"] if s["id"] == ident), None)
        if st is None:
            return []
        out: list[tuple[str, Callable[[], Any], bool | None]] = []
        if st["kind"] in ("ordinary", "enclosing"):  # la entrada y la salida de una expansión no cambian de tipo
            out += self._tipos_etapa(ident, st["kind"])
        if st["kind"] == "enclosing":
            out.append(("Añadir recinto…", lambda: self.anadir_recinto(ident), None))
            recintos = [r for r in m["hierarchy"]["enclosures"] if r["ownerStepRef"] == ident]
            if recintos:
                out.append(("Encuadrar el recinto" if len(recintos) == 1 else "Encuadrar los recintos",
                            lambda: self.encuadrar_recintos(ident), None))
        rol = roles.get(st["partialRef"])
        if rol and rol["kind"] == "enclosure":  # una etapa de un recinto: su enlace de activación (casilla) y su encapsulante
            out.append(("Enlace de activación", lambda: self.enlace_activacion(ident), ident in rol["activation"]))
            out.append(("Encuadrar la encapsulante", lambda: self.encuadrar_encapsulante(rol["ownerStep"]), None))
        macro = next((x["ownerMacroRef"] for x in m["hierarchy"]["expansions"] if ident in (x["entryRef"], x["exitRef"])), None)
        if st["kind"] in ("entry", "exit") and macro is not None:  # la entrada y la salida de una expansión: a su macroetapa
            out.append(("Encuadrar la macroetapa", lambda: self.encuadrar_macroetapa(macro), None))
        if self._destinos_forzado(ident):
            out.append(("Forzar un parcial…", lambda: self.forzar(ident), None))
        return out

    def _tipos_etapa(self, ident: str, actual: str) -> list[tuple[str, Callable[[], Any], bool | None]]:
        """Los tipos de una etapa o de una macroetapa como casillas excluyentes (la del tipo `actual`, marcada)."""
        return [(texto, lambda t=tipo: self.cambiar_tipo_etapa(ident, t), tipo == actual)
                for tipo, texto, _ in TIPOS_ETAPA]

    def descripcion_jerarquia(self, ident: str) -> str:
        """Una línea con lo que un elemento es en la jerarquía, con nombres (nunca IDs): «Macroetapa M1 · expansión M1 ·
        entrada E1 · salida S1», «Recinto G1 de H · activación: K», «Orden: H fuerza G1 a {K}»…; vacío si no es de la
        jerarquía (una etapa ordinaria del raíz)."""
        m, nom = self.ed.model, self._nom
        if self.es_orden_suelta(ident):
            return self._descripcion_orden_suelta(self._borrador(ident))
        if any(x["id"] == ident for x in m["hierarchy"]["macros"]):
            try:
                x = self.ed.macro_info(ident)
            except DiagnosticError:
                return f"Macroetapa {nom(ident)}"
            return f"Macroetapa {nom(ident)} · expansión {nom(x.partial)} · entrada {nom(x.entry)} · salida {nom(x.exit)}"
        f = next((f for f in m["forces"] if f["id"] == ident), None)
        if f is not None:
            situacion = {"explicit": "a " + force_situation(f, self.nombres), "current": "a la situación actual",
                         "empty": "a la situación vacía", "initial": "a su situación inicial"}.get(f["targetKind"], "")
            return f"Orden: {nom(f['sourceStepRef'])} fuerza {nom(f['targetPartialRef'])} {situacion}".rstrip()
        roles = self.ed.partial_roles()
        rol = roles.get(ident)
        if rol and rol["kind"] == "enclosure":
            marcas = ", ".join(nom(x) for x in rol["activation"]) or "ninguna"
            return f"Recinto {nom(ident)} de {nom(rol['ownerStep'])} · activación: {marcas}"
        if rol and rol["kind"] == "expansion":
            return f"Expansión de la macroetapa {nom(rol['macro'])} · entrada {nom(rol['entry'])} · salida {nom(rol['exit'])}"
        if rol and self._es_parcial_suelto(ident):  # un grafcet parcial suelto, y quién lo fuerza
            desde = [nom(f["sourceStepRef"]) for f in m["forces"] if f["targetPartialRef"] == ident]
            return f"Grafcet parcial {nom(ident)}" + (f" · forzado desde {', '.join(dict.fromkeys(desde))}" if desde else "")
        st = next((s for s in m["steps"] if s["id"] == ident), None)
        if st is None:
            return ""
        partes = []
        if st["kind"] == "enclosing":
            recintos = [nom(r["partialRef"]) for r in m["hierarchy"]["enclosures"] if r["ownerStepRef"] == ident]
            partes.append(f"Encapsulante {nom(ident)} · " + (f"recintos: {', '.join(recintos)}" if recintos else "sin recintos"))
        elif st["kind"] in ("entry", "exit") and (x := next((x for x in m["hierarchy"]["expansions"]
                                                             if ident in (x["entryRef"], x["exitRef"])), None)):
            partes.append(f"{'Entrada' if st['kind'] == 'entry' else 'Salida'} de la expansión de la macroetapa "
                          f"{nom(x['ownerMacroRef'])}")
        rol = roles.get(st["partialRef"])
        if rol and rol["kind"] == "enclosure":
            partes.append(f"Del recinto {nom(st['partialRef'])} de {nom(rol['ownerStep'])} · "
                          + ("con" if ident in rol["activation"] else "sin") + " enlace de activación")
        return " · ".join(partes)

    def ficha_jerarquia(self, ident: str) -> dict[str, Any] | None:
        """Lo que muestra el panel de opciones de un elemento de jerarquía: {texto (su descripción, o vacío), botones
        (`acciones_jerarquia`)}; None si no hay ni una cosa ni la otra (por ejemplo, una transición)."""
        texto, botones = self.descripcion_jerarquia(ident), self.acciones_jerarquia(ident)
        return {"texto": texto, "botones": botones} if texto or botones else None

    # -- órdenes de forzado (LOC tabla 9; P-IMP-23, P-IMP-26, P-IMP-68): «Forzar un parcial…», la ficha, editarla y quitarla ------
    # Una orden del modelo (`forces`) está unida a una etapa y completa. La ficha «Forzado» (y «Configurar orden…») trabaja con
    # una orden sin completar, que como las acciones sin completar es un borrador de la presentación (tipo «forzado»: destino,
    # forma y etapas): suelta, o unida a una etapa pero sin destino o sin forma, no se simula; completa y unida a una etapa, pasa
    # al modelo con `add_force` (`_completar`) y, al separarla de su etapa, vuelve a ser un borrador suelto.
    def es_orden_suelta(self, ident: str | None) -> bool:
        """Si el ID es el de una orden de forzado sin completar (un borrador de tipo «forzado»), suelta o unida a una etapa."""
        return any(b["id"] == ident and b["tipo"] == "forzado" for b in self.ed.draft_actions())

    @staticmethod
    def _faltan_orden(b: dict[str, Any]) -> list[str]:
        """Lo que le falta a una orden de forzado sin completar para pasar al modelo: el parcial destino, la forma y, si es
        explícita, las etapas del destino que quedan activas (también hace falta que esté unida a una etapa: eso no se lista)."""
        out = [] if b.get("destino") else ["parcial destino"]
        if not b.get("forma"):
            out.append("forma")
        elif b["forma"] == "explicit" and not b.get("etapas"):
            out.append("etapas")
        return out

    @staticmethod
    def _texto_orden(b: dict[str, Any], nombres: dict[str, str]) -> str:
        """Lo que se escribe en la caja de una orden de forzado sin completar, como la del modelo («G1{B,C}», «G1{*}», «G1{ }»,
        «G1{INIT}»): «G?{?}» mientras no se elige el parcial destino y la forma, «G1{?}» si es explícita y aún sin etapas."""
        destino = nombres.get(b["destino"], "G?") if b.get("destino") else "G?"
        forma = b.get("forma")
        if forma == "explicit":
            situacion = force_situation({"targetKind": "explicit", "targetSteps": b["etapas"]}, nombres) if b.get("etapas") else "{?}"
        elif forma in Editor.DRAFT_FORMAS:
            situacion = force_situation({"targetKind": forma}, nombres)
        else:
            situacion = "{?}"
        return destino + situacion

    def _descripcion_orden_suelta(self, b: dict[str, Any]) -> str:
        """Una línea para el panel de opciones de una orden sin completar: dónde está, lo que dice y por qué no se simula."""
        donde = f"unida a la etapa {self.nombre(b['etapa'])}" if b.get("etapa") else "suelta (sin unir a una etapa)"
        falta = self._faltan_orden(b)
        return (f"Orden de forzado {donde} · {self._texto_orden(b, self._nombres_vivos())} · "
                + (f"falta: {', '.join(falta)}" if falta else "completa") + " · no se simula"
                + ("" if b.get("etapa") else ": hay que unirla a una etapa" if not falta else " hasta que esté unida a una etapa y completa"))

    def _destinos_forzado(self, sid: str | None) -> list[tuple[str, str]]:
        """Los parciales a los que una etapa puede forzar: todos menos el suyo, como (ID, nombre). Una orden que aún no está
        unida a una etapa no sabe cuál será: no se ofrece el destino que formaría un ciclo con la etapa de cualquier otro
        parcial (con un solo parcial, ninguno; tampoco uno desde el que ya se fuerza, directa o indirectamente, a todos los
        demás). Lo que dependa de la etapa concreta a la que se una, lo sigue rechazando el núcleo al unirla (D-JERARQUIA-CICLO)."""
        m = self.ed.model
        todos = [p["id"] for p in m["partials"]]
        if sid:
            propio = self.parcial_de(sid)
            return [(p, self.nombre(p)) for p in todos if p != propio]
        de = {s["id"]: s["partialRef"] for s in m["steps"]}
        fuerza: dict[str, set[str]] = {}  # parcial de la etapa que da la orden -> parciales que fuerza
        for f in m["forces"]:
            if f["sourceStepRef"] in de:
                fuerza.setdefault(de[f["sourceStepRef"]], set()).add(f["targetPartialRef"])

        def alcanza(q: str) -> set[str]:  # los parciales que q fuerza, directa o indirectamente
            vistos, pila = set(), [q]
            while pila:
                for r in fuerza.get(pila.pop(), ()):
                    if r not in vistos:
                        vistos.add(r)
                        pila.append(r)
            return vistos
        return [(q, self.nombre(q)) for q in todos if any(p != q and p not in alcanza(q) for p in todos)]

    def _datos_forzado(self, sid: str | None, orden: dict[str, Any] | None = None,
                       borrador: dict[str, Any] | None = None) -> dict[str, Any]:
        """Lo que se le enseña al diálogo de la orden (con nombres; los ID solo para devolver la elección): la etapa de
        origen, los parciales destino, las etapas de cada uno y, al editar, los valores actuales (los de la orden del modelo
        `orden` o los de lo ya elegido en la orden sin completar `borrador`; sin nada elegido, `actual` es None)."""
        m = self.ed.model
        destinos = self._destinos_forzado(sid)
        etapas = {pid: [(s["id"], self.nombres.get(s["id"], s["label"])) for s in m["steps"] if s["partialRef"] == pid]
                  for pid, _ in destinos}
        actual = None
        if orden is not None:
            actual = {"destino": orden["targetPartialRef"], "forma": orden["targetKind"], "etapas": list(orden.get("targetSteps", []))}
        elif borrador is not None and any(borrador.get(k) for k in ("destino", "forma", "etapas")):
            actual = {"destino": borrador.get("destino"), "forma": borrador.get("forma"), "etapas": list(borrador.get("etapas", []))}
        return {"origen": self._nom(sid) if sid else "a la que se una", "destinos": destinos, "etapas": etapas,
                "formas": list(FORMAS_FORZADO), "actual": actual}

    def forzar(self, sid: str) -> str | None:
        """«Forzar un parcial…» en una etapa: pide (`pedir_forzado`) el parcial destino, la forma (explícita, la situación
        actual, vacía o inicial) y, si es explícita, las etapas del destino, y crea la orden vinculada a la etapa
        (`add_force`): una sola operación de deshacer. Devuelve el ID de la orden, o None (cancelado o rechazado: el núcleo
        no admite ciclos de forzado, D-JERARQUIA-CICLO; el aviso en rojo y el parpadeo de la etapa)."""
        datos = self._datos_forzado(sid)
        if not datos["destinos"]:
            self.rechazar(MSG_SIN_DESTINO, sid)
            self.cambiado.emit()
            return None
        eleccion = self.pedir_forzado(datos)
        return None if eleccion is None else self._poner_orden(sid, None, eleccion)

    def editar_orden(self, fid: str) -> str | None:
        """«Editar orden de forzado…»: el mismo diálogo, con los valores actuales (`set_force`); una sola operación de
        deshacer."""
        f = next((f for f in self.ed.model["forces"] if f["id"] == fid), None)
        if f is None:
            return None
        eleccion = self.pedir_forzado(self._datos_forzado(f["sourceStepRef"], f))
        return None if eleccion is None else self._poner_orden(f["sourceStepRef"], fid, eleccion)

    def accion_a_orden(self, aid: str) -> str | None:
        """«Orden de forzado» en el submenú «Tipo de acción» de una acción (del modelo o sin completar): el mismo
        diálogo de «Forzar un parcial…» y, al aceptarlo, la acción se quita y se crea la orden de forzado en su
        lugar, en la misma etapa (`_poner_orden` con `quitar`), todo en una sola operación de deshacer. Cancelar no
        cambia nada; sin otro parcial al que forzar, se rechaza con el aviso en rojo. Una acción suelta (sin etapa)
        pasa a ser una orden suelta sin completar o, si el diálogo la completa, sigue suelta (hasta unirla a una
        etapa). Devuelve el ID de la orden, o None."""
        sid = self.etapa_accion(aid)
        datos = self._datos_forzado(sid)
        if not datos["destinos"]:
            self.rechazar(MSG_SIN_DESTINO, aid)
            self.cambiado.emit()
            return None
        eleccion = self.pedir_forzado(datos)
        if eleccion is None:
            return None
        if sid:
            return self._poner_orden(sid, None, eleccion, quitar=aid)
        forma = eleccion.get("forma")
        etapas = list(eleccion.get("etapas") or []) if forma == "explicit" else None
        if forma == "explicit" and not etapas:
            self.rechazar(MSG_ORDEN_SIN_ETAPAS, aid)
            self.cambiado.emit()
            return None
        motivo = self._atomico("convertir acción en orden de forzado", lambda: self.ed.update_draft_action(
            aid, tipo="forzado", variable=None, condicion="", valor="", evento="", limite="",
            destino=eleccion.get("destino"), forma=forma, etapas=etapas))
        if motivo:
            self.rechazar(motivo, aid)
            self.cambiado.emit()
            return None
        self._tras_borrador(aid)
        self.informar(self._descripcion_orden_suelta(self._borrador(aid)) + ".")
        return aid

    def orden_a_accion(self, fid: str, tipo: str) -> str | None:
        """Un tipo de acción en el submenú «Tipo de acción» de una orden de forzado (del modelo o sin completar): la
        orden se convierte en una acción de ese tipo de la misma etapa. Como en `tipo_accion` de una acción a la que
        le falta algo, la acción nueva es un borrador unido a la etapa con «?» en lo que falta (la variable, el
        valor…) y se abre su editor (`pedir_accion`) para escribirlo; quitar la orden y crear la acción es una sola
        operación de deshacer. La orden suelta (sin etapa) pasa a ser una acción suelta. Devuelve el ID de la acción,
        o None si se rechazó."""
        nuevo: list[str] = []
        if self.es_orden_suelta(fid):
            sid = self._borrador(fid).get("etapa")
            motivo = self._atomico("convertir orden de forzado en acción", lambda: self.ed.update_draft_action(
                fid, tipo=tipo, destino=None, forma=None, etapas=None))
            nuevo.append(fid)
        else:
            f = next((f for f in self.ed.model["forces"] if f["id"] == fid), None)
            if f is None:
                return None
            sid = f["sourceStepRef"]
            px, py = posiciones(self.M)[sid]

            def hacer() -> None:
                self.ed.delete_force(fid)
                nuevo.append(self.ed.add_draft_action((ajustar(px - SX + H + ACT_LINK), ajustar(py)),
                                                      {"tipo": tipo, "etapa": sid}))
            motivo = self._atomico("convertir orden de forzado en acción", hacer)
        if motivo:
            self.rechazar(motivo, fid)
            self.cambiado.emit()
            return None
        self.sel = [sid] if sid else self._ids_grupo(nuevo[0])
        self.accion, self.ver_accion = nuevo[0], True
        self.cambia()
        self.pedir_accion(sid, nuevo[0])
        return nuevo[0]

    def _poner_orden(self, sid: str, fid: str | None, eleccion: dict[str, Any],
                     quitar: str | None = None) -> str | None:
        """Crea (sin `fid`) o cambia la orden de forzado de la etapa con lo elegido en el diálogo. Con `quitar`, la
        acción (del modelo o sin completar) de ese ID se quita en la misma operación de deshacer: así una acción pasa
        a ser una orden."""
        forma = eleccion.get("forma")
        etapas = list(eleccion.get("etapas") or []) if forma == "explicit" else None
        if forma == "explicit" and not etapas:
            self.rechazar("Una orden explícita necesita al menos una etapa del parcial: elíjala, o use la forma «Vacía».",
                          fid or sid)
            self.cambiado.emit()
            return None
        hecho: list[str] = []

        def hacer() -> None:
            if quitar is not None and self._es_borrador(quitar):
                self.ed.delete_draft_actions([quitar])
            elif quitar is not None:
                self.ed.delete([quitar])
            if fid is None:
                hecho.append(self.ed.add_force(sid, eleccion.get("destino"), forma, etapas))
            else:
                self.ed.set_force(fid, target_partial=eleccion.get("destino"), kind=forma, steps=etapas)
                hecho.append(fid)
        etiqueta = "convertir acción en orden de forzado" if quitar else "crear orden de forzado"
        motivo = self._atomico(etiqueta if fid is None else "editar orden de forzado", hacer)
        if motivo:
            self.rechazar(motivo, fid or sid)
            self.cambiado.emit()
            return None
        self.sel, self.accion = [hecho[0]], None
        self.informar(self.descripcion_jerarquia(hecho[0]) + ".")
        self.cambiado.emit()
        return hecho[0]

    def configurar_orden(self, did: str) -> str | None:
        """«Configurar orden de forzado…» (también el doble clic en una orden sin completar y el botón de su panel): el diálogo
        de la orden (`pedir_forzado`: parcial destino, forma y, si es explícita, etapas), con lo ya elegido. Lo elegido se guarda
        en el borrador; si además está unida a una etapa y completa, pasa al modelo con `add_force`, todo en una sola operación
        de deshacer (un ciclo de forzado lo rechaza el núcleo y no cambia nada). Una explícita sin etapas queda sin completar.
        Devuelve el ID de la orden (el del borrador, o el de la orden del modelo), o None (cancelado o rechazado)."""
        if not self.es_orden_suelta(did):
            return None
        b = self._borrador(did)
        datos = self._datos_forzado(b.get("etapa"), borrador=b)
        if not datos["destinos"]:
            self.rechazar(MSG_SIN_DESTINO, did)
            self.cambiado.emit()
            return None
        eleccion = self.pedir_forzado(datos)
        return None if eleccion is None else self._poner_orden_suelta(did, eleccion)

    def _poner_orden_suelta(self, did: str, eleccion: dict[str, Any]) -> str | None:
        """Guarda lo elegido en el diálogo en la orden sin completar y, si queda completa y unida a una etapa, la pasa al modelo."""
        forma = eleccion.get("forma")
        etapas = list(eleccion.get("etapas") or []) if forma == "explicit" else None

        def hacer() -> None:
            self.ed.update_draft_action(did, destino=eleccion.get("destino"), forma=forma, etapas=etapas)
            self._completar(did)
        n = len(self.ed.model["forces"])
        motivo = self._atomico("configurar orden de forzado", hacer)
        if motivo:
            self.rechazar(motivo, did)
            self.cambiado.emit()
            return None
        if self.es_orden_suelta(did):  # sigue sin completar: sin etapa, o sin lo que le falta
            self.sel, self.accion = [did], None
            self.informar(self._descripcion_orden_suelta(self._borrador(did)) + ".")
            self.cambiado.emit()
            return did
        nueva = self.ed.model["forces"][-1]["id"] if len(self.ed.model["forces"]) > n else None
        if nueva is not None:
            self.sel, self.accion = [nueva], None
            self.informar(self.descripcion_jerarquia(nueva) + ".")
        self.cambiado.emit()
        return nueva

    def quitar_orden(self, fid: str) -> bool:
        """«Quitar orden de forzado» (`delete_force`; una sin completar, `delete_draft_actions`): una sola operación de
        deshacer."""
        if self.es_orden_suelta(fid):
            motivo = self._atomico("quitar orden de forzado", lambda: self.ed.delete_draft_actions([fid]))
        else:
            motivo = self._atomico("quitar orden de forzado", lambda: self.ed.delete_force(fid))
        if motivo:
            self.rechazar(motivo, fid)
        else:
            self.sel = [i for i in self.sel if i != fid]
        self.cambiado.emit()
        return motivo is None

    def _etapa_para_orden(self, p: QPointF) -> str | None:
        """La etapa a la que se uniría una orden de forzado soltada en p (la ficha «Forzado»): la etapa bajo el puntero, la
        de la acción o la orden bajo el puntero y la de una fila de acciones a cuyo lado derecho se suelta (a menos de
        IMAN_ACCION, el mismo criterio con que la ficha «Acción» se pega a otra). None si no hay: sobre un hueco, una
        transición, una macroetapa, una barra, un enlace o una acción suelta."""
        ident = elemento_en(self.M, p)
        if ident is not None:
            return ident if any(s["id"] == ident for s in self.M["steps"]) else None
        cajas = [*(getattr(self.diagrama, "cajas_acciones", None) or []), *(getattr(self.diagrama, "cajas_ordenes", None) or [])]
        for c in cajas:
            x, y, w, h = c["rect"]
            if c["etapa"] and (x <= p.x() <= x + w and y <= p.y() <= y + h
                               or abs(p.x() - (x + w)) <= IMAN_ACCION and abs(p.y() - (y + h / 2)) <= H):
                return c["etapa"]
        return None

    def poner_orden_ficha(self, p: QPointF) -> str | None:
        """La ficha «Forzado» soltada en p, como la ficha «Acción»: en un hueco, una orden de forzado suelta (un borrador, con
        su rectángulo doble y «G?{?}») que no se simula; soltada sobre una etapa, o junto a su fila de acciones, se une a ella
        (`_poner_orden_unida`); junto a otra acción suelta, se pega a ella. Se configura con `configurar_orden` y se une a una
        etapa con el mismo gesto que una acción. Encima de otro elemento no se coloca y avisa. Devuelve el ID de la orden, o None."""
        sid = self._etapa_para_orden(p)
        if sid is not None:
            return self._poner_orden_unida(sid)
        if self._huella_ficha("forzado", p):
            self.informar(MSG_SOLAPE)
            self.cambiado.emit()
            return None
        return self.poner_accion_suelta(p, "forzado") or None

    def _poner_orden_unida(self, sid: str) -> str | None:
        """Una orden de forzado sin completar unida a la etapa `sid`, al final de su fila de acciones (como «Añadir acción…»):
        una operación de deshacer; queda seleccionada y se abren sus opciones para elegir el parcial destino. Sin él, no se
        simula."""
        px, py = posiciones(self.M)[sid]
        hecho: list[str] = []

        def hacer() -> None:
            hecho.append(self.ed.add_draft_action((ajustar(px - SX + H + ACT_LINK), ajustar(py)), {"tipo": "forzado", "etapa": sid}))
        motivo = self._atomico("colocar orden de forzado", hacer)
        if motivo:
            self.rechazar(motivo, sid)
            self.cambiado.emit()
            return None
        did = hecho[0]
        self.sel, self.accion = [did], None
        self.informar(self._descripcion_orden_suelta(self._borrador(did)) + ".")
        self.cambiado.emit()
        self.pedir_accion(None, did)
        return did

    # -- el rectángulo de lo seleccionado, para «Centrar selección» (REQ-EDT-02) ------------------------------------
    def caja_seleccion(self) -> QRectF | None:
        """El rectángulo del dibujo que ocupa lo seleccionado (`sel`), con las cajas de cada elemento y un margen: la etapa, la
        macroetapa o la transición (con su texto) y, de una etapa, sus acciones y órdenes; una barra, una acción, una orden, el
        marco de un parcial, el recorrido de un enlace, el enlace de una etapa con sus acciones y un enlace en borrador. None si
        no hay nada seleccionado que esté dibujado. Es lo que encuadra «Centrar selección» (`VistaDiagrama.centrar_seleccion`)."""
        M, pos = self.M, posiciones(self.M)
        trans = orientaciones(M)
        acciones = {c["id"]: c for c in getattr(self.diagrama, "cajas_acciones", None) or []}
        ordenes = {c["id"]: c for c in getattr(self.diagrama, "cajas_ordenes", None) or []}
        marcos, rutas = cajas_parciales(M), {e["id"]: e["pts"] for e in enlaces(M)}
        uniones = {u["id"]: [q for tramo in u["trazos"] for q in tramo] for u in getattr(self.diagrama, "uniones_acciones", None) or []}
        textos = self._textos_transiciones() if any(i in trans for i in self.sel) else []
        puntos: list[QRectF] = []
        for ident in self.sel:
            if n := self.anotacion(ident):
                puntos.append(rect_anotacion(n))
            elif ident in pos:
                x, y = pos[ident]
                puntos.append(caja_barra(trans[ident], x, y) if ident in trans else QRectF(x - H, y - H, 2 * H, 2 * H))
                puntos += [QRectF(*c["rect"]) for c in (*acciones.values(), *ordenes.values()) if c["etapa"] == ident]
                puntos += [r for r, tid in textos if tid == ident]
            elif (b := self._barra(ident)) is not None:
                puntos.append(QRectF(*barra(b)))
            elif ident in acciones or ident in ordenes:
                puntos.append(QRectF(*(acciones.get(ident) or ordenes[ident])["rect"]))
            elif ident in marcos:
                c = marcos[ident]
                puntos.append(QRectF(c["x0"], c["y0"], c["x1"] - c["x0"], c["y1"] - c["y0"]))
            elif ident in uniones or ident in rutas:
                for qx, qy in uniones.get(ident) or rutas[ident]:
                    puntos.append(QRectF(qx, qy, 0, 0))
            elif (d := next((d for d in M.get("drafts", []) if d["id"] == ident), None)) is not None and d["from"] in pos and d["to"] in pos:
                puntos += [QRectF(*pos[d["from"]], 0, 0), QRectF(*pos[d["to"]], 0, 0)]
        if not puntos:
            return None
        x0, y0 = min(r.left() for r in puntos), min(r.top() for r in puntos)
        x1, y1 = max(r.right() for r in puntos), max(r.bottom() for r in puntos)
        return QRectF(x0, y0, x1 - x0, y1 - y0).adjusted(-12, -12, 12, 12)

    # -- equidistanciar alturas: la distancia estándar entre niveles, mayor donde las acciones lo piden -----------------
    def _posiciones_modelo(self) -> dict[str, tuple[float, float]]:
        """La posición (x, y) del modelo de cada etapa, macroetapa y transición, tal como se dibuja (también las que no
        tienen posición guardada)."""
        return {i: (x - SX, y) for i, (x, y) in posiciones(self.M).items()}

    def _extensiones(self) -> dict[str, tuple[float, float]]:
        """Cuánto sobresale, por encima y por debajo de su centro, lo que acompaña a una etapa (sus acciones y órdenes de
        forzado con sus marcas) y a una transición (su texto): lo que pide `Editor.equidistribute` para que no se solapen
        con el nivel siguiente. La etapa sin acciones no figura: cabe en la distancia estándar."""
        pos = posiciones(self.M)
        out: dict[str, tuple[float, float]] = {t["id"]: (12.0, 12.0) for t in self.M["transitions"]}
        for c in self._colocadas():
            if c["etapa"]:
                y, (_, ry, _, rh), extra = pos[c["etapa"]][1], c["rect"], c["extra"]
                arriba, abajo = y - (ry - extra[0]), (ry + rh + extra[1]) - y
                previo = out.get(c["etapa"], (float(H), float(H)))
                out[c["etapa"]] = (max(previo[0], arriba), max(previo[1], abajo))
        return out

    def _pares_solape(self, propios: set[str]) -> set[tuple[str, str]]:
        """Las parejas de elementos, con al menos uno de `propios`, cuyas cajas quedan a menos de MARGEN_SOLAPE (etapas,
        macroetapas, transiciones y sus textos, barras, y las acciones y órdenes, que cuentan como de su etapa), según el
        modelo y sin esperar a que se dibuje."""
        M, m = self.M, MARGEN_SOLAPE
        trans = orientaciones(M)
        cajas: list[tuple[str, QRectF]] = [
            (i, caja_barra(trans[i], x, y) if i in trans else QRectF(x - H, y - H, 2 * H, 2 * H))
            for i, (x, y) in posiciones(M).items()]
        for b in M.get("bars", []):
            bx, by, bw, bh = barra(b)
            cajas.append((b["id"], QRectF(bx, by - (BARRA_ALTO_MIN - bh) / 2, bw, BARRA_ALTO_MIN) if bh < BARRA_ALTO_MIN
                          else QRectF(bx, by, bw, bh)))
        cajas += [(c["etapa"] or c["grupo"], QRectF(*c["rect"])) for c in self._colocadas()]
        cajas += [(tid, r) for r, tid in self._textos_transiciones()]
        out: set[tuple[str, str]] = set()
        for n, (i, r) in enumerate(cajas):
            for j, s in cajas[n + 1:]:
                if i != j and (i in propios or j in propios) and r.adjusted(-m, -m, m, m).intersects(s):
                    out.add((min(i, j), max(i, j)))
        return out

    def equidistanciar(self, ids: list[str] | None = None) -> list[str] | None:
        """«Equidistanciar alturas de la cadena», «…de la selección» o «…de todo el lienzo» (con `ids` None):
        `Editor.equidistribute` con la distancia estándar DY entre etapas y transiciones, que aumenta donde las acciones de
        una etapa lo piden (`_extensiones`). Una sola operación de deshacer, solo presentación: el modelo no cambia. Si con
        ello algo quedara encima de otro elemento que antes no tocaba, no cambia nada y se avisa. Devuelve los ID de lo que
        se movió (vacío si ya estaba así, o no hay cadenas), o None si se rechazó."""
        self.reconstruir()
        pos = self._posiciones_modelo()
        cadenas = self.ed.chains(ids, pos)
        if not cadenas:
            self.informar("No hay una cadena de elementos enlazados que equidistanciar")
            self.cambiado.emit()
            return []
        propios = {i for c in cadenas for i in c}
        antes, sucio = self._pares_solape(propios), self.ed.dirty
        movidos: list[str] = []

        def hacer() -> None:
            movidos.extend(self.ed.equidistribute(ids, DY, self._extensiones(), MARGEN_SOLAPE, REJILLA, pos))
            self.reconstruir()
            if self._pares_solape(propios) - antes:
                raise DiagnosticError(Diagnostic("D-FORMATO", MSG_EQUIDISTANCIA))
        motivo = self._atomico("equidistanciar alturas", hacer, hueco=False)
        if motivo:
            self.ed.dirty = sucio  # lo que se deshizo no cuenta como un cambio sin guardar
            self.mensaje = motivo
            self.cambiado.emit()
            return None
        self.informar("Alturas equidistanciadas" if movidos else "Las alturas ya estaban equidistanciadas")
        self.cambiado.emit()
        return movidos

    def _separar_ramas(self, origen: str, destino: str) -> None:
        """Una etapa con dos transiciones (o dos transiciones hacia una etapa) es una alternativa: si la transición que se
        acaba de enlazar quedó justo encima de una hermana, se aparta a un lado para que se vea la rama."""
        ts = {t["id"]: t for t in self.ed.model["transitions"]}
        pos = posiciones(self.M)
        t = ts.get(destino) or ts.get(origen)
        if t is None or t["id"] not in pos:
            return
        etapa = origen if t["id"] == destino else destino
        hermanas = [o for o in ts.values() if o["id"] != t["id"] and o["id"] in pos
                    and (etapa in o["preRefs"] if t["id"] == destino else etapa in o["postRefs"])]
        if any(abs(pos[o["id"]][0] - pos[t["id"]][0]) < 40 for o in hermanas):
            x = max(pos[o["id"]][0] for o in hermanas) - SX + 160
            self.ed.move(t["id"], x, pos[t["id"]][1])

    def conectar(self, origen: str, destino: str, borrador: bool = False) -> None:
        """Etapa→transición o transición→etapa; entre dos del mismo tipo queda como borrador (D-ALTERNANCIA), también entre
        dos transiciones que ya tienen etapas. Una segunda etapa anterior en una transición es una simultaneidad: se
        rechaza, salvo con `borrador` (el enlace trazado con el ratón), que lo deja como borrador no ejecutable
        (D-SIMULTANEIDAD) en vez de un enlace de modelo de apariencia válida."""
        m = self.ed.model
        ids_t = {t["id"] for t in m["transitions"]}
        t = next((t for t in m["transitions"] if t["id"] in (origen, destino)), None) if len({origen, destino} & ids_t) == 1 else None
        if t is not None:
            v = next(v for v in self.M["transitions"] if v["id"] == t["id"])
            pre = destino == t["id"]
            refs, otra = (t["preRefs"], origen) if pre else (t["postRefs"], destino)
            if refs and otra not in refs and not v["simulPre" if pre else "simulPost"]:
                if borrador and pre and origen in self._pasos():
                    self.borrador_simultaneidad(origen, t["id"])
                    return
                self.rechazar(f"«{self._nom(t['id'])}» ya tiene una etapa {'anterior' if pre else 'siguiente'}: "
                              "varias en una misma transición son una simultaneidad; arrastre el elemento «Simultaneidad» "
                              "de la paleta junto al punto de unión de la transición.", t["id"], origen, destino)
                self.cambiado.emit()
                return
        try:
            with self.ed.group("conectar"):
                diag = self.ed.connect(origen, destino)
                self._separar_ramas(origen, destino)
            self.mensaje = f"{diag.code}: {self.sust(diag.message)}" if diag else ""
        except DiagnosticError as exc:
            self.rechazar("; ".join(self.sust(d.message) for d in exc.diagnostics), origen, destino)
        self.cambia()

    def borrador_simultaneidad(self, etapa: str, transicion: str) -> None:
        """Una etapa que llega a una transición que ya tiene otra etapa anterior: no se crea un enlace del modelo (serían dos
        etapas anteriores sin la barra de simultaneidad), sino un enlace de borrador, en rojo discontinuo, que se puede
        quitar o deshacer y que impide simular (P-IMP-118)."""
        try:
            diag = self.ed.draft_link(etapa, transicion)
        except DiagnosticError as exc:
            self.rechazar("; ".join(self.sust(d.message) for d in exc.diagnostics), etapa, transicion)
            self.cambiado.emit()
            return
        self.mensaje = self.sust(diag.message) if diag else ""
        self.cambia()

    def anadir_debajo(self) -> str | None:
        """Con una etapa seleccionada: transición y etapa enlazadas debajo. Con una transición: la etapa que sigue."""
        if len(self.sel) != 1 or self.sel[0] not in posiciones(self.M):
            self.mensaje = "Seleccione una etapa o una transición."
            self.cambiado.emit()
            return None
        ident = self.sel[0]
        x, y = posiciones(self.M)[ident][0] - SX, posiciones(self.M)[ident][1]
        ed, parcial = self.ed, self.parcial_de(ident)  # lo de debajo es del parcial de lo seleccionado
        if ident in self._pasos():
            with ed.group("añadir debajo"):
                tid, _ = ed.add_transition(parcial, "", [ident], at=(x, y + DY), label=ed.next_label("transition"))
                nid = ed.add_step(parcial, ed.next_label("step"), at=(x, y + 2 * DY))
                ed.connect(tid, nid)
            self.sel = [nid]
            self.cambia()
            return nid
        if any(t["id"] == ident for t in self.M["transitions"]):
            with ed.group("añadir debajo"):
                nid = ed.add_step(parcial, ed.next_label("step"), at=(x, y + DY))
                ed.connect(ident, nid)
            self.sel = [nid]
            self.cambia()
            return nid
        self.rechazar("No se puede añadir nada debajo de este elemento.", ident)
        self.cambiado.emit()
        return None

    def _accion_para_quitar(self) -> str | None:
        """La acción que Supr quita en vez de su etapa: la señalada (un clic en su caja, «Añadir…», una acción recién pegada)
        si su etapa es lo único seleccionado. None si no hay: se borra la selección. Para borrar la etapa hay que
        seleccionarla (un clic en ella deja de señalar la acción)."""
        etapa = next((a["stepRef"] for a in self.ed.model["actions"] if a["id"] == self.accion), None) \
            or next((b.get("etapa") for b in self.ed.draft_actions() if b["id"] == self.accion), None)
        return self.accion if etapa and self.sel == [etapa] else None

    def copiar_fragmento(self, seleccion=None) -> Fragment:
        """Copia la selección efectiva, incluida una acción señalada, con sus coordenadas visibles."""
        aid = self._accion_para_quitar() if seleccion is None else None
        ids = ([aid] if aid else list(self.sel)) if seleccion is None else list(seleccion)
        frag = self.ed.copy(ids)
        # Las acciones sueltas y las barras vacías no tienen propietario semántico: se toma su contención gráfica.
        cajas = cajas_parciales(self.M)
        extra = set()
        for parcial in frag.entities.get("partials", []):
            caja = cajas.get(parcial["id"])
            if caja is None:
                continue
            rect = QRectF(caja["x0"], caja["y0"], caja["x1"] - caja["x0"], caja["y1"] - caja["y0"])
            extra.update(c["id"] for c in self._colocadas() if not c["etapa"] and rect.contains(QRectF(*c["rect"])))
            extra.update(bar["id"] for bar in self.M.get("bars", []) if rect.contains(QRectF(*barra(bar))))
        if extra:
            frag = self.ed.copy(list(dict.fromkeys(ids + sorted(extra))))
            frag.selected = ids
        chosen = {x["id"] for items in frag.entities.values() for x in items}
        layouts = {x["elementRef"] for x in frag.layouts}
        pos = posiciones(self.M)
        for ident in chosen - layouts:
            if ident in pos:
                x, y = pos[ident]
                frag.layouts.append({"elementRef": ident, "viewRef": self.ed.presentation["views"][0]["id"],
                                     "x": str(x - SX), "y": str(y)})
        cajas = {c["id"]: c for c in [*self._colocadas(), *(getattr(self.diagrama, "cajas_ordenes", None) or [])]}
        for d in frag.presentation.get("draftActions", []):
            if not d.get("etapa") and d["id"] in cajas and not self._es_borrador(d["id"]):
                x, y, w, h = cajas[d["id"]]["rect"]
                d["x"], d["y"] = str(x - SX), str(y + h / 2)
        return frag

    def pegar_fragmento(self, frag: Fragment, punto: QPointF) -> bool:
        """Pega en la posición libre de rejilla más cercana al puntero, en una sola operación de deshacer."""
        previo = (list(self.sel), self.accion, self.ver_accion, self.ed.dirty)
        nuevos: dict[str, str] = {}
        def pegar() -> None:
            nuevos.update(self.ed.paste(frag, self.parcial_en(punto), at=(ajustar(punto.x() - SX), ajustar(punto.y()))))
            self.reconstruir()
            propios = set(nuevos.values())
            base = {i: xy for i, xy in layout_from_presentation(self.ed.presentation).items() if i in propios}
            base.update({b["id"]: (float(b["x"]), float(b["y"])) for b in self.ed.bars() if b["id"] in propios})
            base.update({d["id"]: (float(d["x"]), float(d["y"])) for d in self.ed.draft_actions()
                         if d["id"] in propios and not d.get("etapa")})
            base.update({n["id"]:(n["x"],n["y"]) for n in self.ed.annotations() if n["id"] in propios})
            origen = (ajustar(punto.x() - SX), ajustar(punto.y()))
            cola, vistos, anterior = [(0, 0, 0)], {(0, 0)}, (0, 0)
            while any(not ({a, b} <= propios) for a, b in self._pares_solape(propios)):
                _, ix, iy = heapq.heappop(cola)
                for nx, ny in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
                    if (nx, ny) not in vistos:
                        vistos.add((nx, ny))
                        distancia = ((origen[0] + nx * REJILLA - (punto.x() - SX)) ** 2
                                     + (origen[1] + ny * REJILLA - punto.y()) ** 2)
                        heapq.heappush(cola, (distancia, nx, ny))
                dx, dy = ix * REJILLA, iy * REJILLA
                if (dx, dy) != anterior:
                    rutas = self._rutas_con_grupo(propios, dx - anterior[0], dy - anterior[1])
                    self.ed.move_many({i: (float(x) + dx, float(y) + dy) for i, (x, y) in base.items()}, rutas)
                    anterior = dx, dy
                    self.reconstruir()
            self.sel = [nuevos[i] for i in frag.selected if i in nuevos]
            self.accion, self.ver_accion = None, False
        motivo = self._atomico("pegar", pegar, hueco=False)
        if motivo:
            self.sel, self.accion, self.ver_accion, self.ed.dirty = previo
            self.rechazar(motivo)
            self.cambiado.emit()
            return False
        self.informar("Copia pegada")
        self.cambiado.emit()
        return True

    def borrar(self) -> bool:
        """Borra la selección (una sola operación de deshacer); si arrastra otros elementos, antes lo consulta (REQ-EDT-05).
        Si hay una acción señalada de una etapa (clic en su caja) o una orden de forzado seleccionada, quita solo eso."""
        if not self.sel:
            return False
        aid = self._accion_para_quitar()
        if aid:  # una acción señalada de su etapa: se quita ella sola, no la etapa
            self.quitar_accion(aid)
            return True
        if len(self.sel) == 1 and any(f["id"] == self.sel[0] for f in self.ed.model["forces"]):  # una orden: solo ella
            return self.quitar_orden(self.sel[0])
        sel = list(self.sel)
        barras = [i for i in sel if self._barra(i)]
        uniones = [i for i in sel if "|" in i]  # un enlace: se quita el enlace, no los elementos
        sueltas = [i for i in sel if self._es_borrador(i)]
        enlaces_acc = [i for i in sel if i.startswith("enlaceacc:")]  # el enlace de una etapa con sus acciones
        resto = [i for i in sel if i not in barras and i not in uniones and i not in sueltas and i not in enlaces_acc]
        if resto:
            plan = self.ed.plan_delete(resto)
            parciales = {p["id"] for p in self.ed.model["partials"]}
            # El alcance jerárquico se confirma también cuando el lazo ya incluye todo su contenido.
            necesita = (set(plan["elements"]) > set(resto) or plan["affectedTransitions"] or plan["affectedHierarchy"]
                        or any(len(self.ed.plan_delete([i])["elements"]) > 1 for i in resto if i in parciales))
            if necesita and not self.confirmar_borrado(plan):
                return False
        # los borradores unidos a una etapa que se borra se van con ella
        sueltas += [b["id"] for b in self.ed.draft_actions() if b.get("etapa") in resto and b["id"] not in sueltas]
        separadas: list[str] = []
        n, rehacer, sucio = len(self.ed.undo_stack), list(self.ed.redo_stack), self.ed.dirty
        try:
            with self.ed.group("borrar"):
                for u in enlaces_acc:
                    separadas += self._separar_todas(u.split(":", 1)[1])
                if sueltas:
                    self.ed.delete_draft_actions(sueltas)
                for b in barras:
                    self.ed.delete_bar(b)
                for u in uniones:
                    tid, sid, rol = u.split("|")
                    if rol == "barra":
                        self.ed.bar_unlink(tid, sid)
                    else:
                        self.ed.disconnect(tid, sid)
                if resto:
                    self.ed.delete(resto)
        except DiagnosticError as exc:  # el núcleo no lo permite (la entrada o la salida de una expansión sola…): nada cambia
            while len(self.ed.undo_stack) > n:
                self.ed.undo()
            self.ed.redo_stack[:] = rehacer
            self.ed.dirty = sucio  # lo que se deshizo no cuenta como un cambio sin guardar
            self.reconstruir()
            self.rechazar("; ".join(self.sust(d.message) for d in exc.diagnostics), *resto)
            self.cambiado.emit()
            return False
        self.sel, self.accion = separadas, None  # las acciones que se separaron de su etapa quedan seleccionadas
        self.cambia()
        return True

    def avisos_borrado(self, plan: dict[str, list[str]]) -> list[str]:
        """Lo que borrar deja cambiado en la jerarquía (`affectedHierarchy` del plan), con nombres: un recinto que pierde su
        enlace de activación en las etapas que se van y una orden de forzado que pierde etapas de su conjunto explícito
        («la orden G{B,C} de H pierde la etapa B»); si no le queda ninguna, que pasa a ser una orden explícita sin etapas, que
        fuerza el parcial a vacío. El borrado sigue siendo el de `delete` (se queda el conjunto reducido)."""
        m, nom, doomed = self.ed.model, self._nom, set(plan["elements"])
        afectados, out = set(plan["affectedHierarchy"]), []
        for x in m["hierarchy"]["enclosures"]:
            if x["id"] in afectados:
                perdidas = [s for s in x["activationRefs"] if s in doomed]
                out.append(f"el recinto {nom(x['partialRef'])} pierde su enlace de activación en "
                           f"{', '.join(nom(s) for s in perdidas)}")
        for f in m["forces"]:
            if f["id"] in afectados:
                perdidas = [s for s in f.get("targetSteps", []) if s in doomed]
                texto = (f"la orden {nom(f['targetPartialRef'])}{force_situation(f, self.nombres)} de {nom(f['sourceStepRef'])} "
                         f"pierde {'la etapa' if len(perdidas) == 1 else 'las etapas'} {', '.join(nom(s) for s in perdidas)}")
                if f["targetKind"] == "explicit" and len(perdidas) == len(set(f.get("targetSteps", []))):
                    texto += " y pasa a ser una orden explícita sin etapas: fuerza el parcial a vacío"
                out.append(texto)
        return out

    def renombrar(self, ident: str, nuevo: str) -> str | None:
        """Cambia la etiqueta de una etapa o transición; devuelve el motivo si no se pudo. La de una etapa admite `MAX_ETIQUETA_ETAPA` caracteres
        (más no cabe en su cuadro); lo ya guardado con más se abre y se dibuja como siempre."""
        if len(nuevo) > MAX_ETIQUETA_ETAPA and any(s["id"] == ident for s in self.ed.model["steps"]):
            return f"El nombre de una etapa admite {MAX_ETIQUETA_ETAPA} caracteres como máximo; más no cabe en su cuadro."
        try:
            self.ed.rename(ident, nuevo, repetida=True)  # un número repetido se admite como borrador (P-IMP-118)
        except DiagnosticError as exc:
            self.parpadear([ident])
            return "; ".join(f"{self.sust(d.message).rstrip('.')}. {self.sust(d.correction)}" for d in exc.diagnostics)
        self.cambia()
        return None

    def comentario(self, ident: str) -> str:
        """El comentario de una etapa o transición (vacío si no tiene)."""
        return self.ed.comments().get(ident, "")

    def poner_comentario(self, ident: str, texto: str) -> None:
        """Pone el comentario de una etapa o transición (vacío lo quita): una operación de vista, que se deshace."""
        if texto.strip() == self.comentario(ident) or ident not in self.nombres:
            return
        self.ed.set_comment(ident, texto)
        self.cambia()

    def tipo_etapa(self, sid: str, inicial: bool) -> None:
        self.ed.set_initial(sid, inicial)
        self.cambia()

    def tipo_barra(self, bid: str, tipo: str) -> None:
        self.ed.set_bar_kind(bid, tipo)
        self.cambia()

    def mostrar_etiqueta(self, tid: str, visible: bool) -> None:
        x, y = posiciones(self.M)[tid][0] - SX, posiciones(self.M)[tid][1]
        self.ed.set_label_visible(tid, visible, (x, y))
        self.cambia()

    def resumen(self, diags: list[dict[str, Any]]) -> list[str]:
        """Lo que impide simular, en pocas líneas: las receptividades vacías o con errores de sintaxis, juntas."""
        malas = [d["target"] for d in diags if d["blocks"] and d["code"] == "D-EXP-PENDIENTE" and d["target"]]
        out = []
        if malas:
            nombres = [self.nombre(i) for i in dict.fromkeys(malas)]
            out.append("Receptividades vacías o con errores de sintaxis: " + ", ".join(nombres[:-1])
                       + (" y " if len(nombres) > 1 else "") + nombres[-1] + ".")
        out += [self.sust(d["message"])[:1].upper() + self.sust(d["message"])[1:]
                for d in diags if d["blocks"] and d["code"] != "D-EXP-PENDIENTE"]
        return out

    def _parcial(self, ident: str) -> str:
        """El parcial al que pertenece una transición, o el de la etapa de una acción (del modelo o borrador); de lo demás, el
        raíz."""
        etapa = next((b.get("etapa") for b in self.ed.draft_actions() if b["id"] == ident), None)
        etapa = etapa or next((a["stepRef"] for a in self.ed.model["actions"] if a["id"] == ident), None)
        return self.parcial_de(etapa or ident)

    def comprobar(self, tid: str, texto: str) -> Any:
        """Diagnóstico de un texto de receptividad, o de la condición o el evento de una acción (None si se interpreta),
        sin cambiar el modelo."""
        return self.ed.check_expression(self._n(texto), self._parcial(tid))

    def condicion(self, tid: str, texto: str) -> Any:
        diag = self.ed.set_condition(tid, self._n(texto))
        self.cambia()
        return diag

    def significado(self, tid: str, texto: str) -> dict[str, Any]:
        """El significado (árbol de la expresión) de un texto de receptividad (o de condición o evento de una acción) que
        se interpreta, para dibujarlo."""
        return self.ed._make_expr(self.ed.model, self._n(texto), self._parcial(tid))[0]["meaning"]

    def vista_formula(self, texto: str, ident: str | None = None, booleana: bool = True) -> list[dict[str, Any]] | None:
        """Los segmentos con que se dibuja una fórmula (la receptividad de la transición `ident`, o la condición, el evento o el
        valor —con `booleana=False`— de la acción `ident`): la notación del dibujo (↑, ↓, sobrerrayado, · y +). None si está
        vacía o no se interpreta (entonces se ve tal cual la escribió el usuario)."""
        t = texto.strip()
        if not t:
            return None
        try:
            meaning, diag = self.ed._make_expr(self.ed.model, self._n(t, booleana), self._parcial(ident) if ident else None)
        except Exception:  # noqa: BLE001 - un texto a medias no debe romper el panel
            return None
        return None if diag is not None else norm(meaning["meaning"], booleana, self.nombres)

    def sin_declarar(self, tid: str, texto: str) -> list[str]:
        """Variables que usa la receptividad (o la condición o el evento de una acción) y todavía no existen."""
        return self.ed.undeclared_variables(self._n(texto), self._parcial(tid))

    def poner_condicion(self, tid: str, texto: str, crear: bool = False) -> Any:
        """Fija la receptividad; con crear, declara antes como entradas booleanas las variables que no existan
        (el panel de variables llega en el paso 4). Todo es una sola operación de deshacer."""
        if crear:
            for nombre in self.sin_declarar(tid, texto):
                motivo = self.motivo_nombre(nombre)
                if motivo:  # no se puede escribir tal cual en una fórmula: no se crea
                    self.rechazar(motivo, tid)
                    self.cambiado.emit()
                    return Diagnostic("D-FORMATO", motivo)
        with self.ed.group("receptividad"):
            if crear:
                for nombre in self.sin_declarar(tid, texto):
                    self.ed.add_variable(nombre, "input", {"kind": "bool"})
            return self.condicion(tid, texto)

    def deshacer(self) -> str | None:
        if not self.ed.undo_stack:
            return None
        label = self.ed.undo()
        self.cambia()
        return label

    def rehacer(self) -> str | None:
        if not self.ed.redo_stack:
            return None
        label = self.ed.redo()
        self.cambia()
        return label

    def texto_condicion(self, tid: str) -> str:
        """El texto guardado de la receptividad (la sintaxis del núcleo)."""
        t = next(t for t in self.ed.model["transitions"] if t["id"] == tid)
        return next(e["text"] for e in self.ed.model["expressions"] if e["id"] == t["conditionRef"])

    def texto_usuario(self, tid: str) -> str:
        """El mismo texto en la notación del usuario: ↑a, ↓a, X1."""
        return a_usuario(self.texto_condicion(tid))

    def _n(self, texto: str, booleana: bool = True) -> str:
        """Del texto escrito por el usuario (↑a, X1, 1/0, espacios sueltos) al del núcleo, con los espacios normalizados.
        `booleana=False` para un valor numérico (`n := 1`): el 1 y el 0 no pasan a true y false."""
        m = self.ed.model
        return a_nucleo(texto, (s["label"] for s in m["steps"]), (v["name"] for v in m["variables"]), booleana)

    def ambiguas(self, *textos: str) -> list[str]:
        """Los `X…` de los textos que pueden ser dos etapas (E1 y 1 a la vez)."""
        m = self.ed.model
        etapas, variables = [s["label"] for s in m["steps"]], [v["name"] for v in m["variables"]]
        return list(dict.fromkeys(x for t in textos for x in etapas_ambiguas(t, etapas, variables)))

    def aviso_ambiguas(self, *textos: str) -> str:
        """Aviso para el panel o el diálogo si algún `X…` puede ser dos etapas; vacío si no."""
        return " ".join(f"{x} puede ser la etapa E{x[1:]} o la etapa {x[1:]}: se usa E{x[1:]}; para la otra escriba "
                        f"active(`{x[1:]}`)." for x in self.ambiguas(*textos))

    def vista_norma(self, texto: str) -> list[dict[str, Any]] | None:
        """Segmentos de la notación de la norma de una condición o evento que se interpreta (vacío o con error: None)."""
        if not texto.strip():
            return None
        try:
            meaning, diag = self.ed._make_expr(self.ed.model, self._n(texto), None)
        except Exception:  # un texto a medias no debe romper el diálogo
            return None
        return None if diag is not None else norm(meaning["meaning"], True, self.nombres)

    # -- guardar -----------------------------------------------------------------------------------
    def proyecto(self) -> Project:
        project = copy.deepcopy(self.proyecto_base) if getattr(self,"proyecto_base",None) else new_project(self.ed.model["id"], self.titulo)
        add_document(project, self.ed.model)
        add_document(project, self.ed.presentation)
        return project

    def guardar(self, destino: Path) -> None:
        save_project(destino, self.proyecto())
        self.ruta = destino
        self.ed.dirty = False
