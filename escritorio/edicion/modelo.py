"""Preparación de la vista y del modelo editable, persistencia y altas sencillas."""
from __future__ import annotations

import copy
from fractions import Fraction
from pathlib import Path
from typing import Any
from PySide6.QtCore import QPointF
from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Editor
from grafcet.persistence import Project, add_document, new_project, save_project
from grafcet.view import Vista, layout_from_presentation
from .. import orden_acciones
from ..rutas_diagrama import rutas
from ..geometria.base import ajustar
from ..anotaciones import importar_imagen, editar_texto
from ..diagrama import H, SX, VACIO_W, cajas_parciales, enlaces, posiciones
from .constantes import MARGEN_SUELTA, MAX_ETIQUETA_ETAPA, RECINTO_DX, RECINTO_PASO
from .utilidades import quitar_comillas_vista


class _Modelo:
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
        rutas.preparar(self.M)
        orden_acciones.aplicar_vista(self.M, ed)
        quitar_comillas_vista(self.M)
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

    def cambia(self, reconstruir: bool = True) -> None:
        if self.vigencia_aviso.cambio():
            self._mensaje, self.mensaje_info = "", False
        if reconstruir:
            self.reconstruir()
        self.cambiado.emit()

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

    def proyecto(self) -> Project:
        project = copy.deepcopy(self.proyecto_base) if self.proyecto_base else new_project(self.ed.model["id"], self.titulo)
        add_document(project, self.ed.model)
        add_document(project, self.ed.presentation)
        return project

    def guardar(self, destino: Path) -> None:
        save_project(destino, self.proyecto())
        self.ruta = destino
        self.ed.dirty = False
