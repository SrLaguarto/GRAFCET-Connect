"""Creación, edición y borrado de órdenes de forzado."""
from __future__ import annotations

from typing import Any
from PySide6.QtCore import QPointF
from grafcet.editor import Editor
from grafcet.view import force_situation
from ..geometria.acciones import IMAN_ACCION
from ..geometria.base import ajustar
from ..diagrama import ACT_LINK, H, SX, elemento_en, posiciones
from .constantes import FORMAS_FORZADO, MSG_ORDEN_SIN_ETAPAS, MSG_SIN_DESTINO, MSG_SOLAPE


class _Forzados:
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
