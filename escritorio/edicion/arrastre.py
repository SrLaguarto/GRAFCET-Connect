"""Grupos móviles, imanes, cambio de marco y aplicación del movimiento."""
from __future__ import annotations

from typing import Any
from PySide6.QtCore import QPointF, QRectF
from .. import pegado_acciones
from ..geometria import acciones as geo_acciones, choques as geo_choques, enlaces as geo_enlaces
from ..diagrama import RADIO_ANCLA, SX, cajas_parciales, posiciones


class _Arrastre:
    def _iman(self, ident: str, x: float, moviendo: set[str] | frozenset[str] = frozenset()) -> float:
        return geo_enlaces.iman_etapa(self.M, ident, x, moviendo)

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

    def _semanticos_arrastre(self, a: dict[str, Any]) -> list[str]:
        """Las etapas, transiciones y macroetapas que lleva un arrastre simple o de grupo (las barras, las acciones sueltas y los
        textos no tienen parcial; las acciones unidas van con su etapa)."""
        if a.get("tipo") == "grupo":
            ids = [i for i in a["ids"] if a["tipos"].get(i) == "nodo"]
        elif a.get("tipo") is None:
            ids = [a["id"]]
        else:
            return []
        pos = posiciones(self.M)
        return [i for i in ids if i in pos]

    def _marco_destino_arrastre(self, a: dict[str, Any], p: QPointF) -> str | None:
        """El parcial a cuyo marco pasaría lo que se arrastra si se soltara con el puntero en `p`: el más pequeño de los marcos que
        contienen el puntero (sin margen), si es el de un grafcet parcial o el recinto de una encapsulante (no el raíz ni una
        expansión), no es de lo que se arrastra (ni está dentro de ello) y alguno de los elementos que se arrastran es de otro
        parcial. None si no: se mueve como siempre (en un hueco, dentro del mismo marco, o llevando marcos enteros)."""
        if a.get("tipo") not in (None, "grupo") or a.get("marcos") or not a.get("movido"):
            return None
        ids = self._semanticos_arrastre(a)
        if not ids:
            return None
        dentro = [((b["x1"] - b["x0"]) * (b["y1"] - b["y0"]), pid) for pid, b in cajas_parciales(self.M).items()
                  if pid != self.raiz and b["x0"] <= p.x() <= b["x1"] and b["y0"] <= p.y() <= b["y1"]]
        if not dentro:
            return None
        destino = min(dentro)[1]
        if (self.ed.partial_roles().get(destino, {}).get("kind") not in ("root", "enclosure")
                or all(self.parcial_de(i) == destino for i in ids)):
            return None
        modelo, propios, contenidos = self.ed.model, set(ids), set()
        while True:  # lo que se arrastra no cabe en un recinto o una expansión suyos (ni en lo que hay dentro)
            antes = (set(propios), set(contenidos))
            contenidos.update(x["partialRef"] for x in modelo["hierarchy"]["enclosures"] if x["ownerStepRef"] in propios)
            contenidos.update(x["partialRef"] for x in modelo["hierarchy"]["expansions"] if x["ownerMacroRef"] in propios)
            contenidos.update(q["id"] for q in modelo["partials"] if q.get("ownerRef") in contenidos)
            for coll in ("steps", "transitions"):
                propios.update(x["id"] for x in modelo[coll] if x["partialRef"] in contenidos)
            if (propios, contenidos) == antes:
                break
        return None if destino in contenidos else destino

    def _marcar_marco_destino(self, a: dict[str, Any], p: QPointF) -> str | None:
        """Mientras se arrastra: recuadra el marco donde pasaría a estar lo que se suelta (`_marco_destino_arrastre`); lo quita si
        no hay. Devuelve ese parcial."""
        destino = self._marco_destino_arrastre(a, p)
        if self.diagrama is not None and hasattr(self.diagrama, "marcar_destino"):
            self.diagrama.marcar_destino(cajas_parciales(self.M).get(destino) if destino else None)
        return destino

    def _soltar_en_marco(self, a: dict[str, Any], destino: str) -> bool:
        """Termina el arrastre de elementos a otro marco: los mismos pasos que cortar y pegar dentro de él (`copiar_fragmento`,
        `borrar`, `pegar_fragmento`: enlaces que cruzan el borde, nombres repetidos, etapa inicial… como allí), pegados donde se
        sueltan (con el desplazamiento del arrastre), en una sola operación de deshacer. Si algo falla, todo vuelve como estaba."""
        ids = list(a["ids"]) if a.get("tipo") == "grupo" else [a["id"]]
        dx, dy = a["x"] - a["x0"], a["y"] - a["y0"]
        n, rehacer, sucio = len(self.ed.undo_stack), list(self.ed.redo_stack), self.ed.dirty
        previo = (list(self.sel), self.accion, self.ver_accion)
        with self.ed.group("mover a otro marco"):
            frag = self.copiar_fragmento(ids)
            x0, y0 = self._esquina_fragmento(frag)
            self.sel, self.accion = list(ids), None
            hecho = self.borrar() and self.pegar_fragmento(frag, QPointF(x0 + dx + SX, y0 + dy), destino)
        if not hecho:
            while len(self.ed.undo_stack) > n:
                self.ed.undo()
            self.ed.redo_stack[:] = rehacer
            self.ed.dirty = sucio
            self.sel, self.accion, self.ver_accion = previo
            self.reconstruir()
            self.cambiado.emit()
        return True

    def _marcos_grupo(self, a: dict[str, Any]) -> list[QRectF]:
        return [QRectF(*r) for r in geo_choques.marcos_grupo(a)]

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

    def _buscar_iman(self, ids: list[str], x: float, y: float, ancho: float | None = None) -> dict[str, Any] | None:
        acciones = getattr(self.diagrama, "cajas_acciones", None) or []
        ordenes = getattr(self.diagrama, "cajas_ordenes", None) or []
        iman = geo_acciones.buscar_iman([*acciones, *ordenes], ids, x, y, self._colocacion_de)
        return {**iman, "linea": tuple(QPointF(*p) for p in iman["linea"])} if iman is not None else None

    def _iman_del_arrastre(self, arrastre, punto):
        ids = arrastre["ids"]
        if len(ids) > 1 and self.diagrama is not None:
            iman = pegado_acciones.iman_en_punto(self.diagrama.cajas_acciones, punto, RADIO_ANCLA, ids)
            if iman is not None:
                return iman
        return self._buscar_iman(ids, arrastre["x"], arrastre["y"])

    def mover_grupo(self, ids: list[str], x: float, y: float, unir: bool = False) -> None:
        """Mueve una acción suelta, con las que lleva pegadas, a la posición del modelo (x, y): una operación de deshacer.
        Con `unir` (al soltarla con el ratón), si su punto de unión queda muy cerca del de una etapa, se une a ella."""
        with self.ed.group("mover"):
            self.ed.update_draft_actions({i: {"x": x, "y": y} for i in ids})
            if unir:
                self._unir_cercanos(set(ids))
        self.cambia()
