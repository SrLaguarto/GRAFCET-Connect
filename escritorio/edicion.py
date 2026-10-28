"""Edición de un grafcet secuencial en el simulador (P-IMP-32, paso 3): crear etapas y transiciones, enlazarlas,
moverlas, borrarlas, editar etiquetas y receptividades, deshacer y rehacer, y guardar.

Toda la edición la hacen las operaciones de grafcet/editor.py (transacciones, deshacer y rehacer, diagnósticos):
este módulo solo traduce los gestos del ratón a esas operaciones y no toca el documento a mano. No pregunta
nada por sí mismo: los diálogos (receptividad, etiqueta, confirmación de borrado) son ganchos que pone la ventana,
así que se puede probar sin pantalla.
"""
from __future__ import annotations

import copy
import uuid
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QPointF, Signal

from grafcet.diagnostics import DiagnosticError
from grafcet.notation import a_nucleo, a_usuario, x_etapa
from grafcet.editor import Editor, new_grafcet_document
from grafcet.persistence import Project, add_document, new_project, save_project
from grafcet.profile import normalize_options
from grafcet.routing import project_on_link
from grafcet.view import Vista, display_names, layout_from_presentation, presentation_for, substitute

from .diagrama import REJILLA, SX, ancla_en, anclas, barra, elemento_en, enlaces, posiciones

HERRAMIENTAS = ("seleccionar", "etapa", "transicion", "simultaneidad")  # sin herramienta, el ratón selecciona, mueve y enlaza
DY = 80  # distancia vertical entre una etapa y su transición (la de los ejemplos)
IMAN = 40  # a qué distancia horizontal (dos pasos de rejilla) un elemento movido se alinea con uno enlazado


def ajustar(v: float) -> int:
    """Al punto de la rejilla más cercano."""
    return round(v / REJILLA) * REJILLA


class Edicion(QObject):
    cambiado = Signal()    # el modelo, la selección o los diagnósticos cambiaron: hay que redibujarlo todo
    redibujar = Signal()   # solo cambia el dibujo (un arrastre en curso)

    def __init__(self, ed: Editor, titulo: str, ruta: Path | None = None) -> None:
        super().__init__()
        self.ed, self.titulo, self.ruta = ed, titulo, ruta
        parciales = [p["id"] for p in ed.model["partials"]]
        self.raiz = "g" if "g" in parciales else parciales[0]
        self.herramienta = "seleccionar"
        self.sel: list[str] = []
        self.mensaje = ""
        self.opciones = normalize_options(None)
        self.diagrama: Any = None
        self.arrastre: dict[str, Any] | None = None  # id, desplazamiento del agarre, posición actual, si se movió
        self.enlace: dict[str, Any] | None = None    # punto de unión de origen de un enlace que se está trazando
        self.inicio_rama: dict[str, Any] | None = None  # clic selecciona el enlace; arrastrar abre una rama
        self.flecha = "flow"
        self.accion: str | None = None  # la acción señalada de la etapa seleccionada (clic en su caja)
        self.M: dict[str, Any] = {}
        # Ganchos de interfaz: la ventana los sustituye por diálogos
        self.pedir_condicion: Callable[[str], None] = lambda tid: None
        self.pedir_etiqueta: Callable[[str], None] = lambda ident: None
        self.pedir_accion: Callable[[str, str | None], None] = lambda sid, aid: None
        self.confirmar_borrado: Callable[[dict[str, list[str]]], bool] = lambda plan: True
        self.reconstruir()

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
                           hidden=ed.hidden_labels(), bars=self._barras(), link_styles=self.estilos_enlaces())
        self.M = self.vista.model
        self.nombres = self.M.get("names", {})
        vivos = set(posiciones(self.M)) | {d["id"] for d in self.M.get("drafts", [])} | {e["id"] for e in enlaces(self.M)} | {b["id"] for b in self.M.get("bars", [])}
        self.sel = [i for i in self.sel if i in vivos]

    def diagnosticos(self) -> list[dict[str, Any]]:
        """Los diagnósticos del modelo para el panel (REQ-EDT-09): código, texto con nombres, corrección y elemento."""
        out = []
        for d in self.ed.validate().diagnostics:
            out.append({"code": d.code, "message": substitute(d.message, self.nombres), "correction": d.correction,
                        "severity": d.severity, "blocks": d.blocks_start, "question": d.question,
                        "element": d.element, "target": self.dibujable(d.element)})
        return out

    def dibujable(self, elemento: str | None) -> str | None:
        """El elemento del dibujo al que se refiere un diagnóstico (una receptividad, la transición que la usa)."""
        if elemento is None:
            return None
        m = self.ed.model
        if elemento in posiciones(self.M) or any(d["id"] == elemento for d in m["draftLinks"]):
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
        if p is None:
            d = next((d for d in self.M.get("drafts", []) if d["id"] == ident), None)
            a, b = (posiciones(self.M).get(d["from"]), posiciones(self.M).get(d["to"])) if d else (None, None)
            p = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) if a and b else None
        return QPointF(*p) if p else None

    # -- gestos del ratón (los llama VistaDiagrama) ---------------------------------------------------
    def _modelo(self, p: QPointF) -> tuple[int, int]:
        return ajustar(p.x() - SX), ajustar(p.y())

    def colocar(self, tipo: str, p: QPointF) -> None:
        """Un elemento de la paleta soltado en el dibujo."""
        if tipo == "etapa":
            self.poner_etapa(p)
        elif tipo == "transicion":
            self.poner_transicion(p)
        elif tipo == "simultaneidad":
            self.poner_barra(p, "Y")

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
        self.diagrama.marcar_anclas(anclas(self.M, ident or (cerca["id"] if cerca else "")), cerca)

    def _barra(self, ident: str | None) -> dict[str, Any] | None:
        return next((b for b in self.M.get("bars", []) if b["id"] == ident), None)

    def prensar(self, p: QPointF, event: Any = None) -> bool:
        ident = elemento_en(self.M, p)
        h = self.herramienta
        punto = self._punto(p, ident)
        caja = self.accion_en(p) if ident is None else None
        if caja and h == "seleccionar":  # clic en una acción: se selecciona su etapa y se señala la acción
            self.sel, self.accion = [caja["etapa"]], caja["id"]
            self.cambiado.emit()
            return True
        self.accion = None
        if h == "seleccionar":
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
            self.sel = [ident] if ident else []
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
        elif ident:
            self.sel = [ident]
            self.cambiado.emit()
        else:
            if h == "etapa":
                self.poner_etapa(p)
            elif h == "transicion":
                self.poner_transicion(p)
            elif h == "simultaneidad":
                self.poner_barra(p, "Y")
            self.herramienta = "seleccionar"  # la herramienta vale para un elemento
            self.cambiado.emit()
        return True

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
            return True
        if self.enlace and self.diagrama is not None:
            destino = ancla_en(self.M, p)
            self.diagrama.trazo_provisional(self.enlace["pos"], destino["pos"] if destino else p)
            self.diagrama.marcar_anclas(anclas(self.M, destino["id"]) if destino else [], destino)
            return True
        if event is not None and not event.buttons():
            self.pasar(p)
        return False

    def soltar(self, p: QPointF, event: Any = None) -> bool:
        self.inicio_rama = None
        if self.arrastre:
            a, self.arrastre = self.arrastre, None
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
            destino = ancla_en(self.M, p)
            ident = elemento_en(self.M, p)
            if ident and "|" in ident and destino and (p - destino["pos"]).manhattanLength() > 5:
                destino = None  # sobre el trazo manda el enlace, no el halo de un tirador vecino
            if destino is None and ident and "|" in ident and ident.split("|")[2] in ("pre", "post"):
                self.unir_a_enlace(origen, ident)  # soltado sobre un enlace: una rama que se une ahí
                return True
            if destino is None and ident is None:  # soltado en un hueco: se abre una rama con el elemento que sigue
                self.crear_desde(origen, p)
                return True
            if destino is None:  # soltado sobre el cuerpo de un elemento: se une por su punto más cercano
                cerca = sorted(anclas(self.M, ident or ""), key=lambda a: (a["pos"].x() - p.x()) ** 2 + (a["pos"].y() - p.y()) ** 2)
                destino = cerca[0] if cerca else None
            if destino and destino["id"] != origen["id"]:
                self.unir(origen, destino)
            return True
        return False

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
            self.mensaje = "Una rama se une a un enlace que llega a una etapa (de una transición a su etapa siguiente)."
            self.cambiado.emit()
        elif any(t["id"] == src for t in self.M["transitions"]):
            self.conectar(src, sid)
        elif src == sid:
            self.mensaje = "Una etapa no salta a sí misma."
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
            self.mensaje = (f"«{self.nombres.get(base, base)}» ya tiene una etapa {'siguiente' if abajo else 'anterior'}: "
                            "para otra más hace falta una simultaneidad (elemento de la paleta); para una alternativa, "
                            "abra la rama desde la etapa.")
            self.cambiado.emit()
            return None
        if not es_paso and t is None:
            self.mensaje = "De una barra se enlaza con las etapas y transiciones existentes."
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
        self.mensaje = "Rama abierta: " + ("escriba la receptividad en las propiedades." if es_paso else "etapa nueva.")
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
        self.mensaje = tipo + ": escriba su receptividad en las propiedades."
        self.cambia()
        return tid

    def unir(self, origen: dict[str, Any], destino: dict[str, Any]) -> None:
        """Enlaza dos puntos de unión. Manda el punto del que se arrastra: el de abajo emite el enlace (va hacia el otro
        elemento) y el de arriba lo recibe (viene del otro). Si el enlace queda de abajo arriba, se dibuja con flecha. Con una
        barra, el elemento queda por encima o por debajo según el lado de la barra."""
        ba, bb = self._barra(origen["id"]), self._barra(destino["id"])
        if ba and bb:
            self.mensaje = "Una barra no se une a otra barra."
            self.cambiado.emit()
        elif ba or bb:
            barra_, otro = (origen, destino) if ba else (destino, origen)
            try:
                diag = self.ed.bar_link(barra_["id"], barra_["lado"], otro["id"])
                self.mensaje = f"{diag.code}: {substitute(diag.message, self.nombres)}" if diag else ""
            except DiagnosticError as exc:
                self.mensaje = "; ".join(substitute(d.message, self.nombres) for d in exc.diagnostics)
            self.cambia()
        elif origen["lado"] == "abajo":  # el punto de abajo emite el enlace
            self.conectar(origen["id"], destino["id"])
        else:  # el punto de arriba lo recibe: se arrastra de la entrada de un elemento a lo que va antes
            self.conectar(destino["id"], origen["id"])

    def doble(self, p: QPointF, event: Any = None) -> bool:
        caja = self.accion_en(p)
        if caja:  # doble clic en una acción: se edita
            self.pedir_accion(caja["etapa"], caja["id"])
            return True
        ident = elemento_en(self.M, p)
        if not ident:
            return False
        if any(t["id"] == ident for t in self.M["transitions"]):
            self.pedir_condicion(ident)
        elif any(s["id"] == ident for s in self.M["steps"]):
            self.pedir_etiqueta(ident)
        return True

    # -- acciones (P-IMP-38) ------------------------------------------------------------------------
    def accion_en(self, p: QPointF) -> dict[str, Any] | None:
        """La caja de acción bajo el puntero, tal como quedó en el dibujo ({id, etapa, rect})."""
        for c in getattr(self.diagrama, "cajas_acciones", None) or []:
            x, y, w, h = c["rect"]
            if x <= p.x() <= x + w and y <= p.y() <= y + h:
                return c
        return None

    def seleccion_dibujo(self) -> set[str]:
        """Lo que se resalta en el dibujo: la selección y la acción señalada."""
        a = next((x for x in self.ed.model["actions"] if x["id"] == self.accion), None)
        return set(self.sel) | ({f"accion:{a['id']}"} if a and a["stepRef"] in self.sel else set())

    def menu(self, p: QPointF) -> list[tuple[str, Callable[[], Any]]]:
        """Opciones del botón derecho sobre lo que hay debajo."""
        caja = self.accion_en(p)
        ident = caja["etapa"] if caja else elemento_en(self.M, p)
        if ident is None or not any(s["id"] == ident for s in self.M["steps"]):
            return []
        self.sel, self.accion = [ident], caja["id"] if caja else None
        self.cambiado.emit()
        out = [("Añadir acción…", lambda: self.pedir_accion(ident, None))]
        if caja:
            aid = caja["id"]
            out += [("Editar acción…", lambda: self.pedir_accion(ident, aid)),
                    ("Mover a la izquierda", lambda: self.mover_accion(aid, -1)),
                    ("Mover a la derecha", lambda: self.mover_accion(aid, 1)),
                    ("Quitar acción", lambda: self.quitar_accion(aid))]
        return out

    def _texto(self, eid: str | None) -> str:
        return a_usuario(next(e["text"] for e in self.ed.model["expressions"] if e["id"] == eid)) if eid else ""

    def datos_accion(self, aid: str) -> dict[str, str]:
        """Una acción en la notación del usuario: tipo (continua, activacion, desactivacion, evento), variable,
        condición (continua; vacía si es siempre), valor (memorizada; 1/0 para una booleana) y evento."""
        m = self.ed.model
        a = self.ed.get(aid)
        var = next((v for v in m["variables"] if v["id"] == a["targetRef"]), None)
        nombre = var["name"] if var else a["targetRef"]
        if a["mode"] == "continuous":
            cond = self._texto(a["conditionRef"])
            return {"tipo": "continua", "variable": nombre, "condicion": "" if cond == "true" else cond}
        trig = a["trigger"]
        valor = self._texto(a["valueRef"])
        if var and var["type"]["kind"] == "bool":
            valor = {"true": "1", "false": "0"}.get(valor, valor)
        return {"tipo": {"activation": "activacion", "deactivation": "desactivacion", "event": "evento"}[trig["kind"]],
                "variable": nombre, "valor": valor, "evento": self._texto(trig.get("expressionRef"))}

    @staticmethod
    def resumen_accion(d: dict[str, str]) -> str:
        """Una línea para la lista de acciones de la etapa."""
        if d["tipo"] == "continua":
            return d["variable"] + (f"   si {d['condicion']}" if d.get("condicion") else "   (continua)")
        cuando = {"activacion": "al activar ↑", "desactivacion": "al desactivar ↓",
                  "evento": f"con {d.get('evento') or '…'}"}[d["tipo"]]
        return f"{d['variable']} := {d.get('valor', '')}   ({cuando})"

    def acciones(self, sid: str) -> list[dict[str, str]]:
        st = next(s for s in self.ed.model["steps"] if s["id"] == sid)
        return [dict(self.datos_accion(aid), id=aid) for aid in st["actionRefs"]]

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

    def poner_accion(self, sid: str, d: dict[str, str], aid: str | None = None,
                     crear: tuple[str, str] | None = None) -> str | None:
        """Añade (o, con `aid`, cambia) una acción de la etapa con los datos de `datos_accion`. Si la variable no existe
        y se da `crear` (papel, tipo), se declara antes. Devuelve el motivo si no se pudo; nada cambia en ese caso."""
        m, nombre = self.ed.model, d.get("variable", "").strip()
        var = next((v for v in m["variables"] if v["name"] == nombre), None)
        if not nombre:
            return "Elija la variable sobre la que actúa."
        if var is None and crear is None:
            return f"La variable «{nombre}» no existe."
        if d["tipo"] != "continua" and not d.get("valor", "").strip():
            return "Escriba el valor que se asigna (1 o 0 para una booleana; un número o una cuenta como CT + 1)."
        if d["tipo"] == "evento" and not d.get("evento", "").strip():
            return "Una acción por evento necesita su evento (por ejemplo ↑I02)."
        booleana = (var["type"]["kind"] if var else crear[1]) == "bool"

        def hacer() -> None:
            vid = var["id"] if var else self.ed.add_variable(nombre, crear[0], {"kind": crear[1]})
            if d["tipo"] == "continua":
                cond = self._n(d.get("condicion", "")) or "true"
                if aid:
                    self.ed.update_action(aid, vid, "continuous", condition=cond)
                else:
                    self.ed.add_continuous_action(sid, vid, cond)
                return
            valor = d["valor"].strip()
            valor = self._n({"1": "true", "0": "false"}.get(valor, valor) if booleana else valor)
            trig = {"activacion": "activation", "desactivacion": "deactivation", "evento": "event"}[d["tipo"]]
            evento = self._n(d["evento"]) if trig == "event" else None
            if aid:
                self.ed.update_action(aid, vid, "stored", trigger=trig, value=valor, event=evento)
            else:
                self.ed.add_stored_action(sid, vid, trig, valor, evento)
        motivo = self._atomico("acción", hacer)
        if motivo is None and sid not in self.sel:
            self.sel = [sid]
            self.cambiado.emit()
        return motivo

    def quitar_accion(self, aid: str) -> None:
        self.ed.delete([aid])
        self.accion = None
        self.cambia()

    def mover_accion(self, aid: str, delta: int) -> None:
        self.ed.move_action(aid, delta)
        self.cambia()

    # -- variables (REQ-EDT-07, P-IMP-38) ------------------------------------------------------------
    def variables(self) -> list[dict[str, Any]]:
        """El diccionario: cada variable con cuántos usos tiene (expresiones y acciones que la escriben)."""
        m = self.ed.model
        return [dict(v, usos=len(self.ed.usages(v["id"])) + sum(a["targetRef"] == v["id"] for a in m["actions"]))
                for v in m["variables"]]

    def nueva_variable(self, nombre: str, papel: str = "input", tipo: dict[str, Any] | None = None) -> str | None:
        return self._atomico("crear variable", lambda: self.ed.add_variable(nombre, papel, tipo or {"kind": "bool"}))

    def cambiar_variable(self, vid: str, nombre: str | None = None, **cambios: Any) -> str | None:
        """Cambia nombre (y el texto de sus usos), papel, tipo, unidad o valor inicial, en una sola operación."""
        v = next(x for x in self.ed.model["variables"] if x["id"] == vid)

        def hacer() -> None:
            if nombre is not None and nombre != v["name"]:
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
                self.mensaje = (f"«{self.nombres.get(t['id'], t['id'])}» ya tiene una etapa {'anterior' if pre else 'siguiente'}: "
                                "varias en una misma transición son una simultaneidad; arrastre el elemento «Simultaneidad» "
                                "de la paleta junto al punto de unión de la transición.")
                self.cambiado.emit()
                return
        try:
            with self.ed.group("conectar"):
                diag = self.ed.connect(origen, destino)
                self._separar_ramas(origen, destino)
            self.mensaje = f"{diag.code}: {substitute(diag.message, self.nombres)}" if diag else ""
        except DiagnosticError as exc:
            self.mensaje = "; ".join(substitute(d.message, self.nombres) for d in exc.diagnostics)
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
        self.mensaje = "No se puede añadir nada debajo de este elemento."
        self.cambiado.emit()
        return None

    def borrar(self) -> bool:
        """Borra la selección; si arrastra otros elementos, antes lo consulta (REQ-EDT-05)."""
        if not self.sel:
            return False
        if self._barra(self.sel[0]):
            self.ed.delete_bar(self.sel[0])
            self.sel = []
            self.cambia()
            return True
        if "|" in self.sel[0]:  # un enlace: se quita el enlace, no los elementos
            tid, sid, rol = self.sel[0].split("|")
            if rol == "barra":
                self.ed.bar_unlink(tid, sid)
            else:
                self.ed.disconnect(tid, sid)
            self.sel = []
            self.cambia()
            return True
        plan = self.ed.plan_delete(self.sel)
        if (set(plan["elements"]) > set(self.sel) or plan["affectedTransitions"]) and not self.confirmar_borrado(plan):
            return False
        self.ed.delete(self.sel)
        self.sel = []
        self.cambia()
        return True

    def renombrar(self, ident: str, nuevo: str) -> str | None:
        """Cambia la etiqueta de una etapa o transición; devuelve el motivo si no se pudo."""
        try:
            self.ed.rename(ident, nuevo)
        except DiagnosticError as exc:
            return "; ".join(f"{d.message}. {d.correction}" for d in exc.diagnostics)
        self.cambia()
        return None

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

    def comprobar(self, tid: str, texto: str) -> Any:
        """Diagnóstico de un texto de receptividad (None si se interpreta), sin cambiar el modelo."""
        partial = next(t["partialRef"] for t in self.ed.model["transitions"] if t["id"] == tid)
        return self.ed.check_expression(self._n(texto), partial)

    def condicion(self, tid: str, texto: str) -> Any:
        diag = self.ed.set_condition(tid, self._n(texto))
        self.cambia()
        return diag

    def significado(self, tid: str, texto: str) -> dict[str, Any]:
        """El significado (árbol de la expresión) de un texto de receptividad que se interpreta, para dibujarlo."""
        partial = next(t["partialRef"] for t in self.ed.model["transitions"] if t["id"] == tid)
        return self.ed._make_expr(self.ed.model, self._n(texto), partial)[0]["meaning"]

    def sin_declarar(self, tid: str, texto: str) -> list[str]:
        """Variables que usa la receptividad y todavía no existen."""
        partial = next(t["partialRef"] for t in self.ed.model["transitions"] if t["id"] == tid)
        return self.ed.undeclared_variables(self._n(texto), partial)

    def poner_condicion(self, tid: str, texto: str, crear: bool = False) -> Any:
        """Fija la receptividad; con crear, declara antes como entradas booleanas las variables que no existan
        (el panel de variables llega en el paso 4). Todo es una sola operación de deshacer."""
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

    def _n(self, texto: str) -> str:
        """Del texto escrito por el usuario (↑a, X1, espacios sueltos) al del núcleo, con los espacios normalizados."""
        m = self.ed.model
        return a_nucleo(texto, (s["label"] for s in m["steps"]), (v["name"] for v in m["variables"]))

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
