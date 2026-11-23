"""Selección simple y múltiple, lazo, foco, zonas de Propiedades y detección de cajas en la vista."""
from __future__ import annotations

from typing import Any, Callable
from PySide6.QtCore import QPointF, QRectF, Qt
from ..anotaciones import rect as rect_anotacion
from ..diagrama import (
    H, _distancia, barra, caja_barra, cajas_parciales, elemento_en, enlaces, orientaciones, posiciones,
)
from .constantes import CON_CONDICION


class _Seleccion:
    parte_pedida: str | None = None  # la parte de una acción de dos partes que pidió el doble clic: «formula» (la marca) o «accion» (la caja); la ventana la consume

    def seleccionar(self, ids: list[str]) -> None:
        """Selecciona exactamente estos elementos (el panel de diagnósticos, «Ir a…»): ya no hay una acción señalada, así que
        Supr borra lo seleccionado y no una acción de antes."""
        self.sel = list(ids)
        self.accion = None
        self.ver_accion = False
        self.cambiado.emit()

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

    def clave_panel(self) -> tuple[tuple[str, ...], str | None]:
        """Lo que muestra el panel de opciones: lo seleccionado y la acción señalada (para saber si un gesto lo cambia)."""
        return tuple(self.sel), self.accion_activa()

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

    def _elemento_sin_marco(self, p: QPointF, cajas: dict[str, dict[str, float]] | None = None) -> str | None:
        """El elemento bajo el punto, salvo el marco de un parcial (su borde o su nombre, que se selecciona pero no es un
        elemento al que unir nada): para soltar un enlace, soltar ahí es soltar en un hueco."""
        ident = elemento_en(self.M, p, cajas)
        return None if ident is not None and any(q["id"] == ident for q in self.M["partials"]) else ident

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
        en_marca = False
        if not caja and (caja := self.marca_en(p)):  # doble clic en la marca (la banderita de la condición o el evento)
            en_marca = True
        if caja:  # doble clic en una acción: se edita (una orden sin completar, con el diálogo de la orden)
            self.parte_pedida = None
            if caja.get("forzado"):
                self.configurar_orden(caja["id"])
            elif self.datos_accion(caja["id"])["tipo"] == "continua" and hasattr(self.diagrama, "abrir_selector"):
                self.desplegar_variable(caja)  # una continua (sin condición, evento ni asignación): solo falta su variable, y se elige sobre la propia acción
            else:
                if self.datos_accion(caja["id"])["tipo"] in (*CON_CONDICION, "evento"):  # dos partes: se abre la que se pulsó
                    self.parte_pedida = "formula" if en_marca else "accion"
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
        elif any(x["id"] == ident for x in self.M.get("macros", [])):
            from ..interaccion_jerarquia import doble_macro
            doble_macro(self, ident, p)
        elif ident in cajas_parciales(self.M) and self._es_parcial_suelto(ident):  # en el marco de un parcial suelto: lo renombra
            self.renombrar_parcial(ident)
        return True

    def marca_en(self, p: QPointF) -> dict[str, Any] | None:
        """La caja de acción cuya marca (la banderita de su condición o su evento) está bajo el puntero."""
        for c in getattr(self.diagrama, "cajas_acciones", None) or []:
            if c.get("marca"):
                x, y, w, h = c["marca"]
                if x <= p.x() <= x + w and y <= p.y() <= y + h:
                    return c
        return None

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

    def seleccion_dibujo(self) -> set[str]:
        """Lo que se resalta en el dibujo: la selección y la acción señalada (también las acciones seleccionadas)."""
        etapa = {a["id"]: a["stepRef"] for a in self.ed.model["actions"]}
        etapa.update({b["id"]: b.get("etapa") for b in self.ed.draft_actions()})
        etapa.update({f["id"]: f["sourceStepRef"] for f in self.ed.model["forces"]})  # una orden seleccionada se resalta en su caja
        señalada = {self.accion} if self.accion in etapa and etapa[self.accion] in self.sel else set()
        seleccion = set(self.sel)
        if señalada and self._accion_para_quitar():
            seleccion.discard(etapa[self.accion])
        marcas = {f"accion:{i}" for i in (señalada | (set(self.sel) & set(etapa)))}
        if self.parte_editada is not None and self.parte_editada[0] == self.accion_activa():
            marcas.add(f"parte:{self.parte_editada[0]}:{self.parte_editada[1]}")
        return seleccion | marcas

    def _transiciones_sel(self, ids: list[str] | None = None) -> list[str]:
        """Las transiciones de `ids` (por defecto, la selección)."""
        todas = {t["id"] for t in self.M["transitions"]}
        return [i for i in dict.fromkeys(self.sel if ids is None else ids) if i in todas]

    def _seleccionar_tras_borrador(self, did: str) -> None:
        """Deja la selección donde el borrador esté ahora: en el modelo (la última acción de su etapa) o sigue siendo un
        borrador."""
        if self._es_borrador(did):
            b = self._borrador(did)
            self.sel, self.accion = [b.get("etapa") or did], did
        else:
            sid = next((a["stepRef"] for a in self.ed.model["actions"][-1:]), None)
            st = next((s for s in self.ed.model["steps"] if s["id"] == sid), None)
            self.sel, self.accion = ([sid], self.ed.model["actions"][-1]["id"]) if st else ([], None)

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

    def caja_seleccion(self, ids: list[str] | None = None) -> QRectF | None:
        """El rectángulo del dibujo que ocupa lo seleccionado (`sel`), con las cajas de cada elemento y un margen: la etapa, la
        macroetapa o la transición (con su texto) y, de una etapa, sus acciones y órdenes; una barra, una acción, una orden, el
        marco de un parcial, el recorrido de un enlace, el enlace de una etapa con sus acciones y un enlace en borrador. None si
        no hay nada seleccionado que esté dibujado. Es lo que encuadra «Centrar selección» (`VistaDiagrama.centrar_seleccion`).
        Con `ids`, la de esos elementos en vez de la selección."""
        elegidos = self.sel if ids is None else ids
        M, pos = self.M, posiciones(self.M)
        trans = orientaciones(M)
        acciones = {c["id"]: c for c in getattr(self.diagrama, "cajas_acciones", None) or []}
        ordenes = {c["id"]: c for c in getattr(self.diagrama, "cajas_ordenes", None) or []}
        marcos, rutas = cajas_parciales(M), {e["id"]: e["pts"] for e in enlaces(M)}
        uniones = {u["id"]: [q for tramo in u["trazos"] for q in tramo] for u in getattr(self.diagrama, "uniones_acciones", None) or []}
        textos = self._textos_transiciones() if any(i in trans for i in elegidos) else []
        puntos: list[QRectF] = []
        for ident in elegidos:
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

    def zonas_propiedades(self, ident: str | None, programable: tuple[str, str] | None = None) -> dict[str, QRectF]:
        """A qué partes del dibujo se unen las ventanas de Propiedades (modo flotante), cada una con su rectángulo del dibujo: «elemento» (la etapa,
        solo su figura; la transición, con sus textos; otro elemento, lo que ocupa) o, de una acción condicionada o por evento (`programable`, lo que da
        `accion_programable`), «condicion» (o «evento»: su marca, con el trazo y la banderita) y «accion» (su rectángulo). Vacío si no está dibujado."""
        if programable is not None:
            caja = next((c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] == programable[0]), None)
            if caja is None:
                return {}
            x, y, w, h = caja["rect"]
            marca = QRectF(*caja["marca"]) if caja.get("marca") else QRectF(x + 3, y - 20, 36, 20)
            return {programable[1]: marca.adjusted(-2, -2, 2, 2), "accion": QRectF(x, y, w, h).adjusted(-3, -3, 3, 3)}
        if not ident:
            return {}
        pos = posiciones(self.M)
        if ident in pos:
            x, y = pos[ident]
            trans = orientaciones(self.M)
            if ident in trans:  # el trazo y los textos de la transición (etiqueta y receptividad)
                caja = caja_barra(trans[ident], x, y)
                for r, tid in self._textos_transiciones():
                    if tid == ident:
                        caja = caja.united(r)
                return {"elemento": caja.adjusted(-3, -3, 3, 3)}
            return {"elemento": QRectF(x - H, y - H, 2 * H, 2 * H).adjusted(-3, -3, 3, 3)}
        caja = next((QRectF(*c["rect"]) for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] == ident), None)
        if caja is None:
            caja = self.caja_seleccion([ident])
        return {"elemento": caja} if caja is not None else {}

    def _accion_para_quitar(self) -> str | None:
        """La acción que Supr quita en vez de su etapa: la señalada (un clic en su caja, «Añadir…», una acción recién pegada)
        si su etapa es lo único seleccionado. None si no hay: se borra la selección. Para borrar la etapa hay que
        seleccionarla (un clic en ella deja de señalar la acción)."""
        etapa = next((a["stepRef"] for a in self.ed.model["actions"] if a["id"] == self.accion), None) \
            or next((b.get("etapa") for b in self.ed.draft_actions() if b["id"] == self.accion), None)
        return self.accion if etapa and self.sel == [etapa] else None
