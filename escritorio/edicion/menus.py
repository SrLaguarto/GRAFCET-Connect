"""Composición de los menús y despacho a las operaciones de la fachada."""
from __future__ import annotations

from typing import Any
from PySide6.QtCore import QPointF
from ..diagrama import cajas_parciales, elemento_en, orientaciones, icono_accion
from .constantes import COLOCACIONES, TEXTO_INICIAL, TEXTO_LIMITADA, TEXTO_ORDEN, TIPOS_ACCION, TIPOS_ETAPA


class _Menus:
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
        from ..propiedades import icono as icono_ficha  # (propiedades importa este módulo: no puede ir arriba)
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
        self.sel, self.accion = ([aid], aid) if suelta else ([sid], aid)
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
