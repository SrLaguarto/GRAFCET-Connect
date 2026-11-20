"""Orden de grupos y pegado, unión y separación de sus acciones."""
from __future__ import annotations

from typing import Any
from .. import orden_acciones
from ..geometria.base import ajustar
from ..diagrama import H, SX, posiciones


class _Grupos:
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

    def _colocacion_de(self, caja: dict[str, Any]) -> str:
        """La colocación de la etapa o del grupo al que pertenece una acción dibujada (una suelta sin grupo, en fila)."""
        clave = caja["etapa"] or caja.get("grupo") or ""
        return self.colocacion(clave) if clave else "fila"

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
        orden_acciones.colocar_tras(self.ed, sid, ids, objetivo)
        promovidas, ordenes = [], []
        for did in ids:
            es_orden = self.es_orden_suelta(did)
            if self._completar(did):  # (una orden completa pasa a `forces`, no a las acciones de la etapa)
                if es_orden:
                    ordenes.append(self.ed.model["forces"][-1]["id"])
                else:
                    promovidas.append(self.ed.model["actions"][-1]["id"])
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
        from ..vigencia_avisos import seleccion_actual
        self.seleccion_aviso = seleccion_actual(self)
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
