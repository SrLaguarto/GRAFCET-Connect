"""Fragmentos, pegado y borrado que usa la orden Cortar."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from grafcet.diagnostics import DiagnosticError
from grafcet.editor import Fragment
from grafcet.view import layout_from_presentation
from .. import orden_acciones, pegado_acciones
from ..geometria import choques as geo_choques
from ..geometria.base import ajustar
from ..diagrama import RADIO_ANCLA, SX, barra, cajas_parciales, posiciones


class _Portapapeles:
    @staticmethod
    def _esquina_fragmento(frag: Fragment) -> tuple[float, float]:
        """La esquina (x mínima, y mínima, en el modelo) de lo que copia un fragmento: la que `Editor.paste` lleva a `at`."""
        pts = [(float(x["x"]), float(x["y"])) for x in frag.layouts]
        pts += [(float(x["x"]), float(x["y"])) for k in ("barras", "draftActions") for x in frag.presentation.get(k, [])
                if not x.get("etapa")]
        pts += [(float(x["x"]), float(x["y"])) for x in frag.presentation.get("notes", []) if x.get("kind") in ("text", "image")]
        return (min(x for x, _ in pts), min(y for _, y in pts)) if pts else (0.0, 0.0)

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

    def objetivo_pegar_acciones(self, frag: Fragment, punto: QPointF, sobre_seleccion: bool = False):
        return pegado_acciones.objetivo(self, frag, punto, RADIO_ANCLA, sobre_seleccion)

    def pegar_fragmento(
        self, frag: Fragment, punto: QPointF, parcial: str | None = None, *, sobre_seleccion: bool = False,
    ) -> bool:
        """Pega en el destino o en un hueco de rejilla, con un solo deshacer."""
        objetivo = self.objetivo_pegar_acciones(frag, punto, sobre_seleccion) if parcial is None else None
        previo = (list(self.sel), self.accion, self.ver_accion, self.ed.dirty)
        ids, etapa, promovidas = [], None, []

        def pegar() -> None:
            nonlocal ids, etapa, promovidas
            destino = self._parcial(objetivo) if objetivo else parcial
            origen = (ajustar(punto.x() - SX), ajustar(punto.y()))
            nuevos = self.ed.paste(frag, destino or self.parcial_en(punto), at=origen)
            if objetivo:
                ids = pegado_acciones.acciones_copiadas(self.ed, frag, nuevos)
                etapa, promovidas = self._pegar(ids, objetivo)
            else:
                self._colocar_fragmento_libre(frag, punto, nuevos)
                self.sel = [nuevos[i] for i in frag.selected if i in nuevos]
                self.accion, self.ver_accion = None, False

        motivo = self._atomico("pegar", pegar, hueco=objetivo is not None)
        if motivo:
            self.sel, self.accion, self.ver_accion, self.ed.dirty = previo
            self.rechazar(motivo)
            self.cambiado.emit()
            return False
        if not objetivo or not self._encima:
            self.informar("Copia pegada")
        if objetivo:
            self._tras_pegar(ids, etapa, promovidas)
        else:
            self.cambiado.emit()
        return True

    def _colocar_fragmento_libre(self, frag: Fragment, punto: QPointF, nuevos: dict[str, str]) -> None:
        """Busca el hueco más cercano al puntero y conserva la geometría relativa."""
        propios = set(nuevos.values())
        seleccionados = {nuevos[i] for i in frag.selected if i in nuevos}
        borradores = [
            d for d in self.ed.draft_actions() if d["id"] in seleccionados and not d.get("etapa")
        ]
        if len(borradores) > 1 and len(borradores) == len(seleccionados):
            orden_acciones.agrupar_pegadas(self.ed, borradores)
        self.reconstruir()
        base = {i: xy for i, xy in layout_from_presentation(self.ed.presentation).items() if i in propios}
        base.update({b["id"]: (float(b["x"]), float(b["y"])) for b in self.ed.bars() if b["id"] in propios})
        base.update({d["id"]: (float(d["x"]), float(d["y"])) for d in self.ed.draft_actions()
                     if d["id"] in propios and not d.get("etapa")})
        base.update({n["id"]:(n["x"],n["y"]) for n in self.ed.annotations() if n["id"] in propios})
        anterior = (0, 0)
        candidatos = geo_choques.posiciones_hueco(punto.toTuple())
        while any(not ({a, b} <= propios) for a, b in self._pares_solape(propios)):
            dx, dy = next(candidatos)
            if (dx, dy) != anterior:
                rutas = self._rutas_con_grupo(propios, dx - anterior[0], dy - anterior[1])
                self.ed.move_many({i: (float(x) + dx, float(y) + dy) for i, (x, y) in base.items()}, rutas)
                anterior = dx, dy
                self.reconstruir()

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
