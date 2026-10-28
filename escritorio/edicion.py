"""Edición de un grafcet secuencial en el simulador (P-IMP-32, paso 3): crear etapas y transiciones, enlazarlas,
moverlas, borrarlas, editar etiquetas y receptividades, deshacer y rehacer, y guardar.

Toda la edición la hacen las operaciones de grafcet/editor.py (transacciones, deshacer y rehacer, diagnósticos):
este módulo solo traduce los gestos del ratón a esas operaciones y no toca el documento a mano. No pregunta
nada por sí mismo: los diálogos (receptividad, etiqueta, confirmación de borrado) son ganchos que pone la ventana,
así que se puede probar sin pantalla.
"""
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
from grafcet.editor import Editor, new_grafcet_document
from grafcet.ids import MAX_LABEL, valid_label
from grafcet.persistence import Project, add_document, new_project, save_project
from grafcet.profile import normalize_options
from grafcet.routing import project_on_link
from grafcet.timeutil import parse_duration
from grafcet.view import Vista, display_names, norm, layout_from_presentation, presentation_for, substitute

from .bloques import _dur_usuario, normalizar_duracion
from .diagrama import (ACT_LINK, ACT_MIN, FICHAS_ACCION, H, REJILLA, SX, TB, _distancia, ancla_en, anclas, barra,
                       elemento_en, enlaces, icono_accion, posiciones)

HERRAMIENTAS = ("seleccionar",)  # el ratón selecciona, mueve y enlaza; los elementos nuevos solo se colocan arrastrándolos
DY = 80  # distancia vertical entre una etapa y su transición (la de los ejemplos)
IMAN = 40  # a qué distancia horizontal (dos pasos de rejilla) un elemento movido se alinea con uno enlazado
IMAN_ACCION = 16  # a qué distancia de otra acción se pega una acción suelta (lado derecho, o inferior en columna)
TIPOS_ACCION = FICHAS_ACCION  # continua, condicionada, al activar, al desactivar, por evento (+ «limitada» de ficheros antiguos)
TEXTO_LIMITADA = "Condicionada (con límite de tiempo)"
CONTINUAS = ("continua", "condicionada", "limitada")  # los tipos de una acción continua
CON_CONDICION = ("condicionada", "limitada")  # las continuas con condición: se programa en el panel de opciones
DISPARADOR = {"activacion": "activation", "desactivacion": "deactivation", "evento": "event"}
RESERVADAS = {p.lower() for p in KEYWORDS | set(FUNCS_REF) | FUNCS_EXPR | {"delay"}}  # palabras de las fórmulas


COLOCACIONES = (("fila", "En fila, pegadas"), ("fila-separada", "En fila, separadas"), ("columna", "En columna"))
PARPADEO_MS, PARPADEO_PASOS = 250, 6  # tres parpadeos en 1,5 s: encendido al empezar y en los pasos 2 y 4
MARGEN_SOLAPE = 8  # un elemento no se coloca a menos de esto de la caja de otro (en unidades del dibujo)
MSG_SOLAPE = "No se puede poner encima de otro elemento"


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


class Edicion(QObject):
    cambiado = Signal()    # el modelo, la selección o los diagnósticos cambiaron: hay que redibujarlo todo
    redibujar = Signal()   # solo cambia el dibujo (un arrastre en curso)

    def __init__(self, ed: Editor, titulo: str, ruta: Path | None = None) -> None:
        super().__init__()
        self.ed, self.titulo, self.ruta = ed, titulo, ruta
        self.ignorados = self._sanear_borradores()
        parciales = [p["id"] for p in ed.model["partials"]]
        self.raiz = "g" if "g" in parciales else parciales[0]
        self.herramienta = "seleccionar"
        self.sel: list[str] = []
        self._mensaje, self.mensaje_info = "", False
        self.opciones = normalize_options(None)
        self.diagrama: Any = None
        self.parpadeo = Parpadeo(self)  # lo que parpadea en naranja tras un error
        self.parpadeo.cambia.connect(self.redibujar)
        self.arrastre: dict[str, Any] | None = None  # id, desplazamiento del agarre, posición actual, si se movió
        self.enlace: dict[str, Any] | None = None    # punto de unión de origen de un enlace que se está trazando
        self.inicio_rama: dict[str, Any] | None = None  # clic selecciona el enlace; arrastrar abre una rama
        self.flecha = "flow"
        self.accion: str | None = None  # la acción señalada de la etapa seleccionada (clic en su caja)
        self.ver_accion = False  # las opciones muestran la acción señalada de la etapa (no la etapa): clic en su caja, Editar…
        self.lazo: dict[str, Any] | None = None  # rectángulo de selección que se está trazando desde un hueco
        self.menu_marcadas: set[str] = set()     # opciones del último menú que van marcadas (el tipo actual de una acción)
        self.M: dict[str, Any] = {}
        # Ganchos de interfaz: la ventana los sustituye por diálogos
        self.pedir_condicion: Callable[[str], None] = lambda tid: None
        self.pedir_etiqueta: Callable[[str], None] = lambda ident: None
        self.pedir_accion: Callable[[str, str | None], None] = lambda sid, aid: None
        self.confirmar_borrado: Callable[[dict[str, list[str]]], bool] = lambda plan: True
        self.reconstruir()

    def _sanear_borradores(self) -> int:
        """Al abrir: descarta los borradores de acción dañados (no son un diccionario, sin id, de tipo desconocido, con la
        posición ausente o no numérica) y devuelve cuántos. Una etapa inexistente deja el borrador suelto; una variable
        inexistente, con «?»."""
        p, m = self.ed.presentation, self.ed.model
        if "draftActions" not in p:
            return 0
        crudos = p["draftActions"] if isinstance(p["draftActions"], list) else []
        buenos, malos = [], 0 if isinstance(p["draftActions"], list) else 1
        etapas, variables = {s["id"] for s in m["steps"]}, {v["id"] for v in m["variables"]}
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
            for k in ("variable", "condicion", "valor", "evento", "limite", "etapa", "grupo"):
                if k in b and not isinstance(b[k], str):
                    del b[k]
            if "orden" in b and (not isinstance(b["orden"], int) or isinstance(b["orden"], bool)):
                del b["orden"]
            if b.get("etapa") not in etapas:
                b.pop("etapa", None)
            if b.get("variable") not in variables:
                b.pop("variable", None)
            buenos.append(b)
        p["draftActions"] = buenos
        return malos

    @property
    def mensaje(self) -> str:
        return self._mensaje

    @mensaje.setter
    def mensaje(self, texto: str) -> None:
        self._mensaje, self.mensaje_info = texto, False  # por defecto, un error o un rechazo

    def informar(self, texto: str) -> None:
        """Un aviso informativo (no un error): se muestra sin el rojo de los rechazos."""
        self._mensaje, self.mensaje_info = texto, True

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
        if self.arrastre and self.arrastre.get("tipo") is None:
            lay[self.arrastre["id"]] = (self.arrastre["x"], self.arrastre["y"])
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
        return out

    def reconstruir(self) -> None:
        """Rehace la estructura que se dibuja (Vista) a partir del modelo y las posiciones actuales."""
        ed = self.ed
        self.vista = Vista(ed.model["id"], self.titulo, "", lambda: (ed.model, self.layout()), self.opciones,
                           hidden=ed.hidden_labels(), bars=self._barras(), link_styles=self.estilos_enlaces(),
                           draft_actions=self._borradores(), action_layouts=ed.action_layouts(),
                           comments=ed.comments())
        self.M = self.vista.model
        self.nombres = self.M.get("names", {})
        vivos = set(posiciones(self.M)) | {d["id"] for d in self.M.get("drafts", [])} | {e["id"] for e in enlaces(self.M)} | {b["id"] for b in self.M.get("bars", [])}
        vivos |= {a["id"] for a in ed.model["actions"]} | {d["id"] for d in ed.draft_actions()}
        vivos |= {f"enlaceacc:{s['id']}" for s in self.M["steps"]
                  if s["actions"] or any(d.get("etapa") == s["id"] for d in self.M.get("draftActions", []))}
        self.sel = [i for i in self.sel if i in vivos]
        if self.accion not in vivos:  # la acción señalada ya no existe (se deshizo, cambió de ID al completarse…)
            self.accion = None

    def diagnosticos(self) -> list[dict[str, Any]]:
        """Los diagnósticos del modelo para el panel (REQ-EDT-09): código, texto con nombres, corrección y elemento."""
        out = []
        for d in self.ed.validate().diagnostics:
            out.append({"code": d.code, "message": substitute(d.message, self.nombres), "correction": d.correction,
                        "severity": d.severity, "blocks": d.blocks_start, "question": d.question,
                        "element": d.element, "target": self.dibujable(d.element)})
        if self.ignorados:
            out.append({"code": "AVISO", "severity": "advertencia", "blocks": False, "question": None, "element": None,
                        "target": None, "correction": "Se descartó al abrir; vuelva a colocar la acción si hacía falta",
                        "message": "Se ignoró un borrador de acción dañado" if self.ignorados == 1
                        else f"Se ignoraron {self.ignorados} borradores de acción dañados"})
        for b in self.ed.draft_actions():  # avisos de la edición (no son diagnósticos del núcleo): no impiden simular
            suelta = not b.get("etapa")
            out.append({"code": "AVISO", "severity": "advertencia", "blocks": False, "question": None, "element": b["id"],
                        "target": b["id"],
                        "message": "Acción sin etapa: no se simula" if suelta else
                        f"Acción de la etapa {self.nombres.get(b['etapa'], b['etapa'])} sin completar "
                        f"({', '.join(self.faltan(self._datos_borrador(b)))}): no se simula",
                        "correction": "Una la acción a una etapa con un enlace desde su punto de unión izquierdo"
                        if suelta else "Complete la acción con «Editar…» (botón derecho en ella)"})
        return out

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
            if a["id"] == elemento or elemento in (a.get("conditionRef"), a.get("valueRef")):
                return a["stepRef"]
        return None

    def marcados(self) -> set[str]:
        return {d["target"] for d in self.diagnosticos() if d["blocks"] and d["target"]}

    def cambia(self) -> None:
        self.reconstruir()
        self.cambiado.emit()

    # -- selección ---------------------------------------------------------------------------------
    def seleccionar(self, ids: list[str]) -> None:
        self.sel = list(ids)
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
        p = posiciones(self.M).get(ident)
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

    def colocar(self, tipo: str, p: QPointF) -> None:
        """Un elemento de la paleta soltado en el dibujo: «etapa», «transicion», «simultaneidad» o «accion:<tipo>»
        (continua, condicionada, activacion, desactivacion, evento; «accion» a secas es una continua). Si su caja quedaría
        encima de la de otro elemento (con un margen pequeño), no se coloca; una acción que toca a otra se pega a ella."""
        if self._huella_ficha(tipo, p):
            self.informar(MSG_SOLAPE)
            self.cambiado.emit()
            return
        if tipo == "etapa":
            self.poner_etapa(p)
        elif tipo == "transicion":
            self.poner_transicion(p)
        elif tipo == "simultaneidad":
            self.poner_barra(p, "Y")
        elif tipo == "accion" or tipo.startswith("accion:"):
            self.poner_accion_suelta(p, tipo.partition(":")[2] or "continua")

    def poner_accion_suelta(self, p: QPointF, tipo: str = "continua") -> str:
        """Una ficha de acción soltada en un punto: una acción suelta de ese tipo, sin variable todavía (se dibuja con «?»),
        con su punto de unión a la izquierda. Si toca el lado derecho (o el inferior, en columna) de otra acción, se pega
        a ella: pasa a su etapa o a su grupo. No abre ningún diálogo: se une a una etapa con un enlace y se completa con
        «Editar…» (P-IMP-41, P-IMP-43)."""
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
            self.informar("Acción suelta: arrástrela hasta una etapa (desde el punto de unión de su izquierda) para unirla, "
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
        caja = self.accion_en(p) if ident is None else None
        if caja and caja.get("suelta"):  # sobre una acción suelta: se ve el punto de unión de su grupo
            ident = caja["cabeza"]
        self.diagrama.marcar_anclas(anclas(self.M, ident or (cerca["id"] if cerca else "")), cerca)

    def _barra(self, ident: str | None) -> dict[str, Any] | None:
        return next((b for b in self.M.get("bars", []) if b["id"] == ident), None)

    def prensar(self, p: QPointF, event: Any = None) -> bool:
        ident = elemento_en(self.M, p)
        punto = self._punto(p, ident)
        amplia = self._mayus(event)
        if punto and punto["lado"] == "izq":  # el punto de unión de una acción suelta (o de su grupo)
            self.sel, self.accion = self._ids_grupo(punto["id"]), None
            self.enlace = punto
            self.cambiado.emit()
            self.enlace = punto
            return True
        caja = self.accion_en(p) if ident is None else None
        if caja:
            if caja.get("suelta"):  # una acción suelta se selecciona y se mueve, con las que lleva pegadas
                ids = self._ids_grupo(caja["id"])
                self.sel, self.accion = ids, caja["id"]
                cab = self._borrador(ids[0])
                hx, hy = float(Fraction(str(cab["x"]))), float(Fraction(str(cab["y"])))
                self.arrastre = {"id": ids[0], "ids": ids, "tipo": "borrador", "dx": p.x() - (hx + SX), "dy": p.y() - hy,
                                 "x": hx, "y": hy, "movido": False}
            else:  # clic en una acción: se selecciona su etapa y se señala la acción (sus opciones, en el panel inferior)
                self.sel, self.accion, self.ver_accion = [caja["etapa"]], caja["id"], True
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
                    self.arrastre = {"id": r["id"], "tipo": "tramo", "pts": r["pts"], "handle": handle,
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
        previa = list(self.sel) if amplia else []
        self.sel = [ident] if ident else previa
        if ident is None:  # un hueco: arrastrar dibuja el rectángulo de selección (el lazo)
            self.lazo = {"ini": p, "movido": False, "previa": previa}
        if ident and "|" in ident and ident.split("|")[2] in ("pre", "post"):
            _, sid, rol = ident.split("|")
            self.inicio_rama = {"id": sid, "lado": "abajo" if rol == "pre" else "arriba", "pos": p}
        pos = posiciones(self.M).get(ident or "")
        b = self._barra(ident)
        if pos:
            self.arrastre = {"id": ident, "dx": p.x() - pos[0], "dy": p.y() - pos[1], "x": pos[0] - SX, "y": pos[1],
                             "movido": False}
        elif b:
            self.arrastre = {"id": ident, "tipo": "barra", "dx": p.x() - (b["x"] + SX), "dy": p.y() - b["y"],
                             "x": b["x"], "y": b["y"], "movido": False}
        self.cambiado.emit()
        return True

    @staticmethod
    def _mayus(event: Any) -> bool:
        return event is not None and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

    def dentro(self, a: QPointF, b: QPointF) -> list[str]:
        """Lo que queda entero dentro del rectángulo (a, b): etapas, macroetapas, transiciones, barras y acciones."""
        r = QRectF(a, b).normalized()
        out = []
        for ident, (x, y) in posiciones(self.M).items():
            es_t = any(t["id"] == ident for t in self.M["transitions"])
            caja = QRectF(x - TB, y - 2, 2 * TB, 4) if es_t else QRectF(x - H, y - H, 2 * H, 2 * H)
            if r.contains(caja):
                out.append(ident)
        for bar in self.M.get("bars", []):
            bx, by, w, h = barra(bar)
            if r.contains(QRectF(bx, by, w, h)):
                out.append(bar["id"])
        for c in getattr(self.diagrama, "cajas_acciones", None) or []:
            if r.contains(QRectF(*c["rect"])):
                out.append(c["id"])
        return out

    def _iman(self, ident: str, x: float) -> float:
        """Al mover una etapa o una transición cerca de la vertical de un elemento enlazado con ella (a IMAN o menos), se
        alinea con él: el enlace queda recto, sin la S de un desplazamiento de un par de puntos de rejilla."""
        pos = posiciones(self.M)
        enlazados = set()
        for t in self.M["transitions"]:
            pasos = set(t.get("preDib", t["pre"])) | set(t.get("postDib", t["post"]))
            if t["id"] == ident:
                enlazados |= pasos
            elif ident in pasos:
                enlazados.add(t["id"])
        xs = [pos[o][0] - SX for o in enlazados if o in pos]
        cerca = min(xs, key=lambda v: abs(v - x), default=None)
        return cerca if cerca is not None and 0 < abs(cerca - x) <= IMAN else x

    def mover(self, p: QPointF, event: Any = None) -> bool:
        if self.inicio_rama and (p - self.inicio_rama["pos"]).manhattanLength() > 8:
            self.enlace, self.inicio_rama = self.inicio_rama, None
        a = self.arrastre
        if a and a.get("tipo") in ("flecha", "tramo"):
            if (p-a["start"]).manhattanLength() < 3 and not a["movido"]:
                return True
            if a["tipo"] == "flecha":
                segment, ratio = project_on_link(a["pts"], p.toTuple())
                a["style"].setdefault("arrows", {}).setdefault(self.flecha, {}).update(segment=segment, ratio=str(ratio))
            else:
                pts, handle = a["pts"], a["handle"]
                if len(pts) == 6:
                    route = a["style"].setdefault("route", {"laneX": str(pts[2][0]-SX),
                                                            "exitY": str(pts[1][1]), "entryY": str(pts[3][1])})
                    key = {1: "exitY", 2: "laneX", 3: "entryY"}[handle["segment"]]
                    route[key] = str(ajustar(p.x()-SX if key == "laneX" else p.y()))
                elif len(pts) == 4:
                    a["style"]["route"] = {"middleY": str(ajustar(p.y()))}
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
        if self.enlace and self.diagrama is not None:
            destino = self._destino(p, self.enlace)
            self.diagrama.trazo_provisional(self.enlace["pos"], destino["pos"] if destino else p)
            self.diagrama.marcar_anclas(anclas(self.M, destino["id"]) if destino else [], destino)
            return True
        if event is not None and not event.buttons():
            self.pasar(p)
        return False

    def _destino(self, p: QPointF, origen: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """El punto de unión al que llegaría un enlace soltado en p: el más cercano, o el de una acción suelta bajo el
        puntero. El de la derecha de una etapa solo vale para el enlace de una acción."""
        destino = ancla_en(self.M, p, sin_der=origen is not None and origen["lado"] != "izq")
        if destino is None and elemento_en(self.M, p) is None:
            caja = self.accion_en(p)
            if caja and caja.get("suelta"):
                destino = anclas(self.M, caja["cabeza"])[0]  # una acción de un grupo suelto: el grupo entero
        return destino

    def soltar(self, p: QPointF, event: Any = None) -> bool:
        self.inicio_rama = None
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
                self.mover_grupo(a["ids"], a["x"], a["y"])
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
                    self.ed.move(a["id"], a["x"], a["y"])
            self.cambia()
            return True
        if self.enlace:
            origen, self.enlace = self.enlace, None
            if self.diagrama is not None:
                self.diagrama.trazo_provisional(None)
                self.diagrama.marcar_anclas([])
            destino = self._destino(p, origen)
            ident = elemento_en(self.M, p)
            if ident and "|" in ident and destino and (p - destino["pos"]).manhattanLength() > 5:
                destino = None  # sobre el trazo manda el enlace, no el halo de un tirador vecino
            if origen["lado"] == "der" and destino is None:  # del lado derecho de una etapa, solo a una acción suelta
                self.rechazar("De una etapa sale el enlace a una acción suelta: suelte el enlace sobre ella."
                              if ident is None else
                              "Una acción se une a una etapa, no a una transición, una barra ni otra acción.", origen["id"])
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
            if destino is None and ident is None:  # soltado en un hueco: se abre una rama con el elemento que sigue
                self.crear_desde(origen, p)
                return True
            if destino is None:  # soltado sobre el cuerpo de un elemento: se une por su punto más cercano
                cerca = sorted((a for a in anclas(self.M, ident or "") if a["lado"] != "der" or origen["lado"] == "izq"),
                               key=lambda a: (a["pos"].x() - p.x()) ** 2 + (a["pos"].y() - p.y()) ** 2)
                destino = cerca[0] if cerca else None
            if destino and destino["id"] != origen["id"]:
                self.unir(origen, destino)
            return True
        return False

    # -- no colocar un elemento encima de otro ---------------------------------------------------------------
    def _elementos(self) -> list[tuple[str, QRectF, str]]:
        """La caja de cada elemento que no puede quedar tapado, tal como está dibujado (etapas, macroetapas, transiciones,
        barras, acciones y grupos de acciones; no cuentan los comentarios ni los enlaces): (ID, caja, etapa de la acción)."""
        trans = {t["id"] for t in self.M["transitions"]}
        out = [(i, QRectF(x - TB, y - 2, 2 * TB, 4) if i in trans else QRectF(x - H, y - H, 2 * H, 2 * H), "")
               for i, (x, y) in posiciones(self.M).items()]
        out += [(b["id"], QRectF(*barra(b)), "") for b in self.M.get("bars", [])]
        out += [(c["id"], QRectF(*c["rect"]), c["etapa"] or "")
                for c in getattr(self.diagrama, "cajas_acciones", None) or []]
        return out

    def _solapa(self, huella: list[QRectF], propios: set[str]) -> list[QRectF]:
        """Las cajas de `huella` que quedan a menos de MARGEN_SOLAPE de otro elemento (no cuentan los `propios`, ni las
        acciones de una etapa que se mueve)."""
        m = MARGEN_SOLAPE
        otros = [r for i, r, etapa in self._elementos() if i not in propios and etapa not in propios]
        return [h for h in huella if any(h.adjusted(-m, -m, m, m).intersects(r) for r in otros)]

    def _huella_arrastre(self, a: dict[str, Any]) -> list[QRectF]:
        """Las cajas de lo que se está moviendo, en su posición actual: el elemento y, de una etapa, sus acciones; de un
        grupo de acciones sueltas, cada una."""
        if a.get("tipo") == "borrador":
            return [QRectF(*c["rect"]) for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] in a["ids"]]
        mio = [(i, r) for i, r, _ in self._elementos() if i == a["id"]]
        acciones = [QRectF(*c["rect"]) for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["etapa"] == a["id"]]
        return [r for _, r in mio] + acciones

    def _hay_solape(self, a: dict[str, Any]) -> bool:
        propios = set(a["ids"]) if a.get("tipo") == "borrador" else {a["id"]}
        return bool(self._solapa(self._huella_arrastre(a), propios))

    def _marcar_solape(self, a: dict[str, Any] | None) -> None:
        """Mientras se arrastra `a`: en rojo (y con el cursor de prohibido) lo que no se puede colocar donde está; sin
        arrastre (None), lo quita."""
        if self.diagrama is None or not hasattr(self.diagrama, "marcar_prohibido"):
            return
        malas = self._solapa(self._huella_arrastre(a), set(a["ids"]) if a.get("tipo") == "borrador" else {a["id"]}) if a else []
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
        if tipo == "etapa":
            caja = QRectF(x + SX - H, y - H, 2 * H, 2 * H)
        elif tipo == "transicion":
            caja = QRectF(x + SX - TB, y - 2, 2 * TB, 4)
        elif tipo == "simultaneidad":
            caja = QRectF(ajustar(x - 60) + SX, y, 120, 4)
        elif tipo == "accion" or tipo.startswith("accion:"):
            if self._buscar_iman([], x, y, ACT_MIN):
                return []
            caja = QRectF(x + SX, y - H, ACT_MIN, 2 * H)
        else:
            return []
        return self._solapa([caja], set())

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
        if recibe or rol != "post":
            self.rechazar("Una rama se une a un enlace que llega a una etapa (de una transición a su etapa siguiente).",
                          src, enlace)
            self.cambiado.emit()
        elif any(t["id"] == src for t in self.M["transitions"]):
            self.conectar(src, sid)
        elif src == sid:
            self.rechazar("Una etapa no salta a sí misma.", src)
            self.cambiado.emit()
        elif any(s["id"] == src for s in self.M["steps"]):
            self.saltar(src, sid)

    def crear_desde(self, origen: dict[str, Any], p: QPointF) -> str | None:
        """Arrastrar de un punto de unión a un hueco crea lo que sigue y lo enlaza: de una etapa, una transición (una rama
        nueva si ya tenía otra); de una transición, una etapa. Hacia arriba, lo que va antes."""
        base, abajo = origen["id"], origen["lado"] == "abajo"
        x, y = self._modelo(p)
        es_paso = any(s["id"] == base for s in self.M["steps"])
        t = next((t for t in self.ed.model["transitions"] if t["id"] == base), None)
        if t is not None and t["postRefs" if abajo else "preRefs"]:
            self.rechazar(f"«{self.nombres.get(base, base)}» ya tiene una etapa {'siguiente' if abajo else 'anterior'}: "
                          "para otra más hace falta una simultaneidad (elemento de la paleta); para una alternativa, "
                          "abra la rama desde la etapa.", base)
            self.cambiado.emit()
            return None
        if not es_paso and t is None:
            self.rechazar("De una barra se enlaza con las etapas y transiciones existentes.", base)
            self.cambiado.emit()
            return None
        ed = self.ed
        with ed.group("abrir rama"):
            if es_paso:
                nuevo, _ = ed.add_transition(self.raiz, "", [base] if abajo else [], [] if abajo else [base], at=(x, y),
                                             label=ed.next_label("transition"))
            else:
                nuevo = ed.add_step(self.raiz, ed.next_label("step"), at=(x, y))
                ed.connect(base, nuevo) if abajo else ed.connect(nuevo, base)
        self.sel = [nuevo]
        self.informar("Rama abierta: " + ("escriba la receptividad en las propiedades." if es_paso else "etapa nueva."))
        self.cambia()
        return nuevo

    def saltar(self, origen: str, destino: str) -> str:
        """Salto de secuencia: una transición nueva (receptividad pendiente) de la etapa origen a la etapa destino, junto
        a las transiciones que se saltan."""
        pos = posiciones(self.M)
        x = min(pos[origen][0], pos[destino][0]) - SX - 160
        ocupados = {tuple(p) for p in self.layout().values()}
        y = ajustar(pos[origen][1] + DY)
        while (x, y) in ocupados:
            x -= 160
        tid, _ = self.ed.add_transition(self.raiz, "", [origen], [destino], at=(x, y), label=self.ed.next_label("transition"))
        self.sel = [tid]
        tipo = "Repetición de secuencia" if pos[destino][1] <= pos[origen][1] else "Salto de secuencia"
        self.informar(tipo + ": escriba su receptividad en las propiedades.")
        self.cambia()
        return tid

    def unir(self, origen: dict[str, Any], destino: dict[str, Any]) -> None:
        """Enlaza dos puntos de unión. Manda el punto del que se arrastra: el de abajo emite el enlace (va hacia el otro
        elemento) y el de arriba lo recibe (viene del otro). Si el enlace queda de abajo arriba, se dibuja con flecha. Con una
        barra, el elemento queda por encima o por debajo según el lado de la barra."""
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
            try:
                diag = self.ed.bar_link(barra_["id"], barra_["lado"], otro["id"])
                self.mensaje = f"{diag.code}: {substitute(diag.message, self.nombres)}" if diag else ""
            except DiagnosticError as exc:
                self.rechazar("; ".join(substitute(d.message, self.nombres) for d in exc.diagnostics),
                              barra_["id"], otro["id"])
            self.cambia()
        elif origen["lado"] == "abajo":  # el punto de abajo emite el enlace
            self.conectar(origen["id"], destino["id"])
        else:  # el punto de arriba lo recibe: se arrastra de la entrada de un elemento a lo que va antes
            self.conectar(destino["id"], origen["id"])

    def doble(self, p: QPointF, event: Any = None) -> bool:
        caja = self.accion_en(p)
        if caja:  # doble clic en una acción: se edita
            self.pedir_accion(caja["etapa"] or None, caja["id"])
            return True
        ident = elemento_en(self.M, p)
        if not ident:
            return False
        if any(t["id"] == ident for t in self.M["transitions"]):
            self.pedir_condicion(ident)
        elif any(s["id"] == ident for s in self.M["steps"]):
            self.pedir_etiqueta(ident)
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
        señalada = {self.accion} if self.accion in etapa and etapa[self.accion] in self.sel else set()
        return set(self.sel) | {f"accion:{i}" for i in (señalada | (set(self.sel) & set(etapa)))}

    def _texto_valido(self, texto: str) -> bool:
        """Si una condición o un evento escritos se interpretan (no están vacíos, ni a medias, ni usan variables que no
        existen)."""
        texto = texto.strip()
        return bool(texto) and self.ed.check_expression(self._n(texto), self.raiz) is None

    def faltan(self, d: dict[str, str]) -> list[str]:
        """Lo que le falta a una acción (datos como `datos_accion`) para ser del modelo: la variable (o una booleana, si
        es continua), la condición de una condicionada, el valor de una memorizada, el evento de una por evento y el límite
        de una limitada. Una condición o un evento a medias (con huecos, o con variables que no existen) cuentan como
        faltantes."""
        nombre, t = d.get("variable", "").strip(), d["tipo"]
        var = next((v for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None
        out = []
        if var is None or (t in CONTINUAS and var["type"]["kind"] != "bool"):
            out.append("variable")
        cond = d.get("condicion", "").strip()
        if (t == "condicionada" and not self._texto_valido(cond)) or (t == "limitada" and cond and not self._texto_valido(cond)):
            out.append("condición")  # la limitada puede no llevar condición, pero si la lleva ha de interpretarse
        if t in DISPARADOR and not d.get("valor", "").strip():
            out.append("valor")
        if t == "evento" and not self._texto_valido(d.get("evento", "")):
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
            var = d["variable"] or "?"
            item: dict[str, Any] = {"id": b["id"], "x": x, "y": y, "etapa": b.get("etapa"), "borrador": True,
                                    "grupo": b.get("grupo"), "cabeza": suelta and primera["id"] == b["id"],
                                    "target": None, "condRef": None, "falta": self.faltan(d)}
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
        cajas = getattr(self.diagrama, "cajas_acciones", None) or []
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
        se pegaría al soltarla; si quedaría encima de otro elemento se ve en rojo y no se puede soltar (devuelve False)."""
        if self.diagrama is None:
            return True
        iman = None
        if ficha == "accion" or ficha.startswith("accion:"):
            x, y = self._modelo(p)
            iman = self._buscar_iman([], x, y, ACT_MIN)
        malas = self._huella_ficha(ficha, p)
        if malas and self.mensaje != MSG_SOLAPE:
            self.informar(MSG_SOLAPE)
            self.cambiado.emit()  # (vuelve a dibujar: las marcas se ponen después)
        self.diagrama.marcar_iman(iman["linea"] if iman else None)
        if hasattr(self.diagrama, "marcar_prohibido"):
            self.diagrama.marcar_prohibido(malas or None)
        return not malas

    def mover_grupo(self, ids: list[str], x: float, y: float) -> None:
        """Mueve una acción suelta, con las que lleva pegadas, a la posición del modelo (x, y): una operación de deshacer."""
        self.ed.update_draft_actions({i: {"x": x, "y": y} for i in ids})
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
        completas pasan al modelo (se devuelven sus ID); las demás quedan como borradores unidos a la etapa."""
        previos = [b["id"] for b in self._borradores_ordenados() if b.get("etapa") == sid and b["id"] not in ids]
        k = previos.index(objetivo) + 1 if objetivo in previos else 0 if objetivo else len(previos)
        orden = previos[:k] + list(ids) + previos[k:]
        self.ed.update_draft_actions({i: {"etapa": sid, "grupo": None, "orden": n} for n, i in enumerate(orden)})
        promovidas = []
        for did in ids:
            if self._completar(did):
                promovidas.append(self.ed.get(sid)["actionRefs"][-1])
        refs = self.ed.get(sid)["actionRefs"]
        if promovidas and objetivo in refs:  # detrás de la acción del modelo a cuya espalda se pegó
            final = [r for r in refs if r not in promovidas]
            final[final.index(objetivo) + 1:final.index(objetivo) + 1] = promovidas
            for n, aid in enumerate(final):
                actual = self.ed.get(sid)["actionRefs"].index(aid)
                if actual != n:
                    self.ed.move_action(aid, n - actual)
        return promovidas

    def _pegar(self, ids: list[str], objetivo: str) -> tuple[str | None, list[str]]:
        """Pega las acciones sueltas `ids` detrás de la acción `objetivo` (del modelo, o un borrador de una etapa o de un
        grupo suelto). Devuelve la etapa a la que quedan unidas (None si quedan en un grupo suelto) y las que pasaron al
        modelo."""
        b = next((x for x in self.ed.draft_actions() if x["id"] == objetivo), None)
        if b is not None and not b.get("etapa"):
            self._pegar_a_grupo(ids, b)
            return None, []
        sid = b["etapa"] if b is not None else self.ed.get(objetivo)["stepRef"]
        return sid, self._pegar_a_etapa(ids, sid, objetivo)

    def pegar(self, ids: list[str], objetivo: str) -> None:
        """Pega una acción suelta (o un grupo) detrás de otra acción: pasa a su etapa o a su grupo, en una sola operación
        de deshacer."""
        destino: list[Any] = [(None, [])]
        motivo = self._atomico("pegar acciones", lambda: destino.__setitem__(0, self._pegar(ids, objetivo)))
        self.mensaje = motivo or ""
        if motivo:
            self.parpadear(ids)
            self.cambiado.emit()
            return
        self._tras_pegar(ids, *destino[0])

    def _tras_pegar(self, ids: list[str], sid: str | None, promovidas: list[str] = ()) -> None:
        """Deja la selección en lo pegado y, si es una sola acción que aún necesita su variable o su valor, abre Editar."""
        vivos = [i for i in ids if self._es_borrador(i)]
        if sid is None:  # quedaron en un grupo suelto
            self.sel, self.accion = self._ids_grupo(ids[0]), ids[0]
        elif vivos:
            self.sel, self.accion = [sid], vivos[0]
        else:
            self.sel, self.accion = [sid], (promovidas[0] if promovidas else self.ed.get(sid)["actionRefs"][-1])
        self.cambiado.emit()
        if len(ids) == 1 and vivos and sid and set(self.faltan(self._datos_borrador(self._borrador(vivos[0])))) & {"variable", "valor"}:
            self.pedir_accion(sid, vivos[0])

    def unir_accion(self, did: str, sid: str) -> None:
        """Une una acción suelta (con las que lleva pegadas) a una etapa, al final de sus acciones. Las completas pasan a
        ser acciones del modelo; las que no, quedan unidas como borradores y, si es una sola, se abre Editar."""
        if not self._es_borrador(did):
            return
        ids = self._ids_grupo(did)
        promovidas: list[str] = []
        motivo = self._atomico("unir acciones a la etapa", lambda: promovidas.extend(self._pegar_a_etapa(ids, sid, None)))
        self.mensaje = motivo or ""
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
        if not cajas:
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
        return [nuevos.get(aid, aid) for aid in orden]

    def eliminar_enlace_acciones(self, sid: str) -> None:
        """«Eliminar el enlace»: separa las acciones de la etapa (una sola operación de deshacer)."""
        ids: list[str] = []
        motivo = self._atomico("eliminar el enlace de las acciones", lambda: ids.extend(self._separar_todas(sid)))
        self.mensaje = motivo or ""
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
        self.mensaje = motivo or ""
        if motivo:
            self.parpadear([aid])
        if motivo is None:
            self.sel, self.accion = [nuevo], None
            self.cambiado.emit()

    # -- menús
    def menu(self, p: QPointF) -> list[tuple[str, Any]]:
        """Opciones del botón derecho sobre lo que hay debajo: en una etapa, «Añadir acción…» y la colocación de sus
        acciones; en una acción (suelta o unida), su tipo (submenú con iconos, marcado el actual), «Editar…», separarla y
        «Quitar»; en el enlace de una etapa con sus acciones, «Eliminar el enlace». El forzado no se ofrece."""
        self.menu_marcadas = set()
        caja = self.accion_en(p)
        if caja:
            return self._menu_accion(caja)
        ident = elemento_en(self.M, p)
        if ident is None:
            union = self.union_en(p)
            if union:
                self.sel, self.accion = [union], None
                self.cambiado.emit()
                return [("Eliminar el enlace", lambda: self.eliminar_enlace_acciones(union.split(":", 1)[1]))]
        if ident is None or not any(s["id"] == ident for s in self.M["steps"]):
            return []
        self.sel, self.accion = [ident], None
        self.cambiado.emit()
        self.menu_marcadas = {dict(COLOCACIONES)[self.colocacion(ident)]}
        return [("Añadir acción…", lambda: self.anadir_accion(ident)),
                ("Colocación de las acciones", [(texto, lambda v=v: self.colocar_acciones(ident, v))
                                                for v, texto in COLOCACIONES])]

    def _menu_accion(self, caja: dict[str, Any]) -> list[tuple[str, Any]]:
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
        self.menu_marcadas = {textos["condicionada" if actual == "limitada" else actual]}
        out: list[tuple[str, Any]] = [("Tipo de acción", sub), ("-", None),
                                      ("Editar…", lambda: self.pedir_accion(sid, aid))]
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
        """Cómo se colocan las acciones de la etapa (o del grupo suelto): «fila» (por defecto), «fila-separada» o
        «columna»."""
        valor = self.ed.action_layouts().get(sid, "fila")
        return valor if valor in dict(COLOCACIONES) else "fila"

    def colocar_acciones(self, sid: str, valor: str) -> None:
        """Cambia la colocación de las acciones de una etapa o de un grupo suelto (operación de vista, se deshace)."""
        if valor == self.colocacion(sid):
            return
        self.ed.set_action_layout(sid, valor)
        self.cambia()

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
                      for b in self._borradores_ordenados() if b.get("etapa") == sid]

    def _atomico(self, etiqueta: str, fn: Callable[[], Any]) -> str | None:
        """Varias operaciones como una sola de deshacer; si una falla, no queda ninguna y se devuelve el motivo."""
        n, r = len(self.ed.undo_stack), len(self.ed.redo_stack)
        try:
            with self.ed.group(etiqueta):
                fn()
        except DiagnosticError as exc:
            while len(self.ed.undo_stack) > n:
                self.ed.undo()
            del self.ed.redo_stack[r:]
            return "; ".join(substitute(d.message, self.nombres) for d in exc.diagnostics)
        self.cambia()
        return None

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
        """Por qué un nombre no puede ser el de una variable en la interfaz: no se podría escribir tal cual en una fórmula
        (palabra reservada, espacios o símbolos, no empieza por letra) o se confundiría con la actividad de una etapa (X1).
        None si sirve. El núcleo sigue admitiendo cualquier nombre entre comillas invertidas, en ficheros antiguos."""
        if nombre.strip().lower() in RESERVADAS:
            return f'"{nombre}" no puede ser nombre de variable: es una palabra de las fórmulas'
        if not re.fullmatch(r"[^\W\d]\w*(?:\.\w+)?", nombre):
            return (f'"{nombre}" no puede ser nombre de variable: debe empezar por una letra o _ y no llevar espacios ni '
                    "símbolos")
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
        sin_texto = bool({"condición", "evento"} & set(self.faltan({**d, "variable": nombre})))

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
        motivo = self._revisar_textos(d)
        if motivo:
            return motivo
        falta = set(self.faltan({**d, "variable": nombre if var else ""}))
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

    def _revisar_textos(self, d: dict[str, str]) -> str | None:
        """Por qué un texto de la acción (condición, valor, evento) no se interpreta; None si todos sirven."""
        raiz = self.raiz
        for campo, usa, booleana, nombre in (("condicion", d["tipo"] in CONTINUAS, True, "La condición"),
                                             ("valor", d["tipo"] in DISPARADOR, False, "El valor"),
                                             ("evento", d["tipo"] == "evento", True, "El evento")):
            texto = d.get(campo, "").strip()
            if usa and texto:
                diag = self.ed.check_expression(self._n(texto, booleana), raiz)
                if diag is not None:
                    return f"{nombre} no es válido: {substitute(diag.message, self.nombres)}"
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
        motivo = self._revisar_textos(d)
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
        d = self._datos_borrador(b)
        if not b.get("etapa") or self.faltan(d):
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
        did = self.ed.add_draft_action((ajustar(x + H + ACT_LINK), ajustar(y)), {"etapa": sid})
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
        antes = set(self.faltan(d))
        d["tipo"] = tipo
        d["limite"] = ""
        if tipo == "continua":
            d["condicion"] = ""
        falta = self.faltan(d)
        if "variable" in falta:
            d["variable"] = ""  # no sirve para el tipo nuevo (o no había): se vuelve a elegir
        abrir = bool((set(falta) - antes) & {"variable", "valor"})
        if self._es_borrador(ident):
            sid = self._borrador(ident).get("etapa")
            motivo = self._atomico("tipo de acción", lambda: (
                self.ed.update_draft_action(ident, tipo=tipo, variable=self._id_variable(d["variable"]),
                                            condicion=d.get("condicion", ""), limite=""),
                self._completar(ident)))
            self.mensaje = motivo or ""
            if motivo:
                self.parpadear([ident])
            self._tras_borrador(ident)
            if motivo is None and self._es_borrador(ident) and abrir:
                self.pedir_accion(sid, ident)
            return
        sid = self.ed.get(ident)["stepRef"]
        if not falta:  # completa: se cambia en su sitio
            self.mensaje = self.poner_accion(sid, d, ident) or ""
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
        self.mensaje = motivo or ""
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
        self.ed.move_action(aid, delta)
        self.cambia()

    # -- la condición y el evento de una acción, en el panel de opciones (P-IMP-43)
    def accion_activa(self) -> str | None:
        """La acción cuyas opciones se muestran: una acción suelta seleccionada (o la única seleccionada), o la señalada de la
        etapa seleccionada si se abrió (clic en su caja, «Editar…»). None si lo que se muestra es otra cosa."""
        vivas = {a["id"]: a["stepRef"] for a in self.ed.model["actions"]}
        vivas.update({b["id"]: b.get("etapa") for b in self.ed.draft_actions()})
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
        donde = f"etapa {self.nombres.get(sid, sid)}" if sid else "suelta"
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
            if self.faltan(d):
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

    # -- operaciones -------------------------------------------------------------------------------
    def poner_etapa(self, p: QPointF, inicial: bool = False) -> str:
        sid = self.ed.add_step(self.raiz, self.ed.next_label("step"), inicial, at=self._modelo(p))
        self.sel = [sid]
        self.cambia()
        return sid

    def poner_transicion(self, p: QPointF, pedir: bool = False) -> str:
        """Una transición sin receptividad (pendiente: D-EXP-PENDIENTE) en el punto dado. La receptividad se escribe
        después, en el panel de propiedades o con doble clic."""
        tid, _ = self.ed.add_transition(self.raiz, "", at=self._modelo(p), label=self.ed.next_label("transition"))
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
        if self._es_borrador(ident) or any(a["id"] == ident for a in self.ed.model["actions"]):
            d = self.datos_accion(ident)
            return f"acción {d['variable'] or '?'}" + ("" if self._es_borrador(ident) else
                                                      f" ({self.nombres.get(self.ed.get(ident)['stepRef'], '')})")
        if ident.startswith("enlaceacc:"):
            sid = ident.split(":", 1)[1]
            return f"enlace de las acciones de la etapa {self.nombres.get(sid, sid)}"
        if "|" in ident:
            tid, sid, rol = ident.split("|")
            if rol == "barra":
                b = next((b for b in self.M.get("bars", []) if b["id"] == tid), None)
                return f"{self.nombres.get(sid, sid)} — {b['label'] if b else 'barra'}"
            a, b = (sid, tid) if rol == "pre" else (tid, sid)
            return f"{self.nombres.get(a, a)} → {self.nombres.get(b, b)}"
        return self.nombres.get(ident, ident)

    def poner_barra(self, p: QPointF, tipo: str) -> str:
        """Una barra de simultaneidad (Y, doble trazo) o de alternativa (O, trazo simple) centrada en el punto dado."""
        x, y = self._modelo(p)
        bid = self.ed.add_bar(tipo, (ajustar(x - 60), y))
        self.sel = [bid]
        self.cambia()
        return bid

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

    def conectar(self, origen: str, destino: str) -> None:
        """Etapa→transición o transición→etapa; entre dos del mismo tipo queda como borrador (D-ALTERNANCIA)."""
        m = self.ed.model
        t = next((t for t in m["transitions"] if t["id"] in (origen, destino)), None)
        if t is not None:
            v = next(v for v in self.M["transitions"] if v["id"] == t["id"])
            pre = destino == t["id"]
            refs, otra = (t["preRefs"], origen) if pre else (t["postRefs"], destino)
            if refs and otra not in refs and not v["simulPre" if pre else "simulPost"]:
                self.rechazar(f"«{self.nombres.get(t['id'], t['id'])}» ya tiene una etapa {'anterior' if pre else 'siguiente'}: "
                              "varias en una misma transición son una simultaneidad; arrastre el elemento «Simultaneidad» "
                              "de la paleta junto al punto de unión de la transición.", t["id"], origen, destino)
                self.cambiado.emit()
                return
        try:
            with self.ed.group("conectar"):
                diag = self.ed.connect(origen, destino)
                self._separar_ramas(origen, destino)
            self.mensaje = f"{diag.code}: {substitute(diag.message, self.nombres)}" if diag else ""
        except DiagnosticError as exc:
            self.rechazar("; ".join(substitute(d.message, self.nombres) for d in exc.diagnostics), origen, destino)
        self.cambia()

    def anadir_debajo(self) -> str | None:
        """Con una etapa seleccionada: transición y etapa enlazadas debajo. Con una transición: la etapa que sigue."""
        if len(self.sel) != 1 or self.sel[0] not in posiciones(self.M):
            self.mensaje = "Seleccione una etapa o una transición."
            self.cambiado.emit()
            return None
        ident = self.sel[0]
        x, y = posiciones(self.M)[ident][0] - SX, posiciones(self.M)[ident][1]
        ed = self.ed
        if any(s["id"] == ident for s in self.M["steps"]):
            with ed.group("añadir debajo"):
                tid, _ = ed.add_transition(self.raiz, "", [ident], at=(x, y + DY), label=ed.next_label("transition"))
                nid = ed.add_step(self.raiz, ed.next_label("step"), at=(x, y + 2 * DY))
                ed.connect(tid, nid)
            self.sel = [nid]
            self.cambia()
            return nid
        if any(t["id"] == ident for t in self.M["transitions"]):
            with ed.group("añadir debajo"):
                nid = ed.add_step(self.raiz, ed.next_label("step"), at=(x, y + DY))
                ed.connect(ident, nid)
            self.sel = [nid]
            self.cambia()
            return nid
        self.rechazar("No se puede añadir nada debajo de este elemento.", ident)
        self.cambiado.emit()
        return None

    def borrar(self) -> bool:
        """Borra la selección (una sola operación de deshacer); si arrastra otros elementos, antes lo consulta (REQ-EDT-05)."""
        if not self.sel:
            return False
        sel = list(self.sel)
        barras = [i for i in sel if self._barra(i)]
        uniones = [i for i in sel if "|" in i]  # un enlace: se quita el enlace, no los elementos
        sueltas = [i for i in sel if self._es_borrador(i)]
        enlaces_acc = [i for i in sel if i.startswith("enlaceacc:")]  # el enlace de una etapa con sus acciones
        resto = [i for i in sel if i not in barras and i not in uniones and i not in sueltas and i not in enlaces_acc]
        if resto:
            plan = self.ed.plan_delete(resto)
            if (set(plan["elements"]) > set(resto) or plan["affectedTransitions"]) and not self.confirmar_borrado(plan):
                return False
        # los borradores unidos a una etapa que se borra se van con ella
        sueltas += [b["id"] for b in self.ed.draft_actions() if b.get("etapa") in resto and b["id"] not in sueltas]
        separadas: list[str] = []
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
        self.sel, self.accion = separadas, None  # las acciones que se separaron de su etapa quedan seleccionadas
        self.cambia()
        return True

    def renombrar(self, ident: str, nuevo: str) -> str | None:
        """Cambia la etiqueta de una etapa o transición; devuelve el motivo si no se pudo."""
        try:
            self.ed.rename(ident, nuevo)
        except DiagnosticError as exc:
            self.parpadear([ident])
            return "; ".join(f"{d.message}. {d.correction}" for d in exc.diagnostics)
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
            nombres = [self.nombres.get(i, i) for i in dict.fromkeys(malas)]
            out.append("Receptividades vacías o con errores de sintaxis: " + ", ".join(nombres[:-1])
                       + (" y " if len(nombres) > 1 else "") + nombres[-1] + ".")
        out += [f"{d['code']}: {d['message']}" for d in diags if d["blocks"] and d["code"] != "D-EXP-PENDIENTE"]
        return out

    def _parcial(self, ident: str) -> str:
        """El parcial al que pertenece una transición; el de una acción (o de lo demás), el raíz."""
        return next((t["partialRef"] for t in self.ed.model["transitions"] if t["id"] == ident), self.raiz)

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
        project = new_project(self.ed.model["id"], self.titulo)
        add_document(project, self.ed.model)
        add_document(project, self.ed.presentation)
        return project

    def guardar(self, destino: Path) -> None:
        save_project(destino, self.proyecto())
        self.ruta = destino
        self.ed.dirty = False
