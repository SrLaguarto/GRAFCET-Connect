"""Anclas libres, enlaces, vías manuales, saltos, retorno, giros y flechas."""
from __future__ import annotations

import copy
from typing import Any
from PySide6.QtCore import QPointF
from grafcet.diagnostics import DiagnosticError
from ..geometria import enlaces as geo_enlaces
from ..geometria.base import ajustar
from ..geometria.enlaces import IMAN
from ..diagrama import SX, anclas, enlaces, posiciones
from .constantes import DY, RADIO_UNION, RADIO_UNION_MAX


class _Enlaces:
    def estilos_enlaces(self) -> dict[str, Any]:
        styles = copy.deepcopy(self.ed.link_styles())
        if self.arrastre and self.arrastre.get("tipo") in ("flecha", "tramo"):
            styles[self.arrastre["id"]] = self.arrastre["style"]
        elif self.arrastre and self.arrastre.get("tipo") == "grupo":
            # los enlaces con sus dos extremos en lo que se mueve llevan su recorrido manual (alturas y carril absolutos) con
            # ellos, como se guardará al soltar; los de un extremo solo se recalculan con la posición nueva
            a = self.arrastre
            styles.update(self._rutas_con_grupo(set(a["ids"]), a["x"] - a["x0"], a["y"] - a["y0"]))
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

    def _unir_cercanos(self, ids: set[str], *, vista_actual: bool = False) -> bool:
        """Une el par de puntos libres compatibles más cercano, dentro del mismo paso de deshacer."""
        if not vista_actual:
            self.reconstruir()
        radio = min(RADIO_UNION / self._zoom(), RADIO_UNION_MAX)
        pos = posiciones(self.M)
        borradores = self.M.get("draftActions", [])
        presentes = set(pos) | {d["id"] for d in borradores}
        propios = [a for i in ids if i in presentes for a in anclas(self.M, i, pos) if self._ancla_libre(a)]
        if not propios:
            return False
        ajenos = [a for i in (*pos, *(d["id"] for d in borradores)) if i not in ids for a in anclas(self.M, i, pos)]
        menor = radio * radio
        mejor = None
        for punto in propios:
            for otro in ajenos:
                diferencia = punto["pos"] - otro["pos"]
                distancia = diferencia.x() ** 2 + diferencia.y() ** 2
                if distancia > menor or (distancia == menor and mejor is not None):
                    continue
                par = self._par_union(punto, otro)
                if par and self._ancla_libre(otro):
                    menor, mejor = distancia, par
        if mejor is None:
            return False
        self.unir(*mejor)
        return True

    @staticmethod
    def _num(v: float) -> str:
        return str(int(v)) if v == int(v) else str(v)

    def _pegar_a_paralelo(self, valor: float, vertical: bool, propio: str, rango: tuple[float, float]) -> float:
        return geo_enlaces.pegar_a_paralelo(enlaces(self.M), valor, vertical, propio, rango)

    def _arrastre_tramo(self, enlace: str, p: QPointF) -> dict[str, Any] | None:
        """Agarrar el cuerpo de un enlace y arrastrar mueve el tramo de su recorrido que se agarra (como su tirador, sin
        seleccionarlo antes): None si el punto no cae en un tramo movible (el primero y el último, que unen con la etapa o la
        transición, no se mueven; un enlace recto no tiene ninguno): entonces solo se selecciona."""
        tramo = geo_enlaces.tramo_en(enlaces(self.M), enlace, p.toTuple())
        if tramo is None:
            return None
        pts, marca = tramo
        return {"id": enlace, "tipo": "tramo", "pts": pts, "handle": marca, "movido": False,
                "start": p, "style": copy.deepcopy(self.ed.link_styles().get(enlace, {}))}

    def _barra(self, ident: str | None) -> dict[str, Any] | None:
        return next((b for b in self.M.get("bars", []) if b["id"] == ident), None)

    def _rutas_con_grupo(self, ids: set[str], dx: float, dy: float) -> dict[str, dict[str, Any]]:
        return geo_enlaces.rutas_con_grupo(self.ed.link_styles(), ids, dx, dy)

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
                          "abre la rama desde la etapa.", base)
            self.cambiado.emit()
            return None
        if not es_paso and t is None:
            self.rechazar("De una barra se enlaza con las etapas y transiciones existentes.", base)
            self.cambiado.emit()
            return None
        bx, by = posiciones(self.M)[base]
        if abs(p.x() - bx) <= IMAN:
            x = ajustar(bx - SX)
        paso = DY if abajo else -DY
        y = ajustar(by + paso)
        while self._ocupado(x, y):
            y += paso
        ed, parcial = self.ed, self.parcial_de(base)  # lo que nace de un elemento es de su parcial
        visibles = self.etiquetas_visibles()
        with ed.group("abrir rama"):
            if es_paso:
                nuevo, _ = ed.add_transition(parcial, "", [base] if abajo else [], [] if abajo else [base],
                                             at=(x, y))
                self.etiqueta_como_las_demas(nuevo, visibles, (x, y))
            else:
                nuevo = ed.add_step(parcial, ed.next_label("step"), at=(x, y))
                ed.connect(base, nuevo) if abajo else ed.connect(nuevo, base)
            # y, si su otro punto queda muy cerca de uno libre compatible, también se une (P-IMP-114)
            unido = self._unir_cercanos({nuevo})  # (ya rehízo la vista con el elemento en su sitio: si no unió nada, esa es la de ahora)
        self.sel = [nuevo]
        self.informar("Rama abierta: " + ("escribe la receptividad en las propiedades (doble clic en la transición)." if es_paso else "etapa nueva."))
        self.cambia(reconstruir=unido)
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
        visibles = self.etiquetas_visibles()
        with self.ed.group("crear transición"):
            tid, _ = self.ed.add_transition(self.parcial_de(ini), "", [ini], [fin], at=(tx, ty))
            self.etiqueta_como_las_demas(tid, visibles, (tx, ty))
        self.sel = [tid]
        self.informar("Transición nueva entre las dos etapas: escribe su receptividad en las propiedades (doble clic en ella).")
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
        visibles = self.etiquetas_visibles()
        with self.ed.group("crear transición"):
            tid, _ = self.ed.add_transition(self.parcial_de(origen), "", [origen], [destino], at=(x, y))
            self.etiqueta_como_las_demas(tid, visibles, (x, y))
        self.sel = [tid]
        tipo = "Repetición de secuencia" if pos[destino][1] <= pos[origen][1] else "Salto de secuencia"
        self.informar(tipo + ": escribe su receptividad en las propiedades (doble clic en ella).")
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

    def orientacion_transicion(self, tid: str) -> str:
        """El sentido de la evolución a través de la transición: «abajo» (por defecto), «derecha», «arriba» o «izquierda»."""
        valor = self.ed.transition_orientations().get(tid, "abajo")
        return valor if valor in self.ed.TRANSITION_ORIENTATIONS else "abajo"

    def girar_transiciones(self, sentido: int | str, transiciones: list[str] | None = None) -> bool:
        """«Girar en sentido horario» (positivo, o «horario»/«derecha») o «antihorario» (negativo, o «antihorario»/«izquierda») las transiciones
        seleccionadas (o `transiciones`): el sentido de la evolución a través de la transición pasa al siguiente a derechas
        (como las agujas del reloj en pantalla) abajo → izquierda → arriba → derecha → abajo, o al anterior a izquierdas. El
        trazo se coloca perpendicular a la evolución y el texto sigue horizontal. Es una operación de vista (no cambia el
        modelo ni la simulación) y una sola de deshacer. Devuelve si giró algo."""
        paso = 1 if sentido in ("horario", "derecha", "der") or (isinstance(sentido, int) and sentido > 0) else -1
        ids = self._transiciones_sel(transiciones)
        if not ids:
            self.informar("Selecciona una transición para girarla.")
            self.cambiado.emit()
            return False
        orden = self.ed.TRANSITION_ORIENTATIONS
        nuevos = {i: orden[(orden.index(self.orientacion_transicion(i)) + paso) % len(orden)] for i in ids}
        motivo = self._atomico("girar las transiciones", lambda: self.ed.set_transition_orientations(nuevos), hueco=False)
        self._decir(motivo)
        if motivo:
            self.parpadear(ids)
        return motivo is None

    def _separar_ramas(self, origen: str, destino: str) -> None:
        nueva = geo_enlaces.separar_ramas(self.ed.model["transitions"], posiciones(self.M), origen, destino)
        if nueva is not None:
            self.ed.move(*nueva)

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
                              "varias en una misma transición son una simultaneidad; arrastra el elemento «Simultaneidad» "
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
            self.mensaje = "Selecciona una etapa o una transición."
            self.cambiado.emit()
            return None
        ident = self.sel[0]
        x, y = posiciones(self.M)[ident][0] - SX, posiciones(self.M)[ident][1]
        ed, parcial = self.ed, self.parcial_de(ident)  # lo de debajo es del parcial de lo seleccionado
        if ident in self._pasos():
            visibles = self.etiquetas_visibles()
            with ed.group("añadir debajo"):
                tid, _ = ed.add_transition(parcial, "", [ident], at=(x, y + DY))
                self.etiqueta_como_las_demas(tid, visibles, (x, y + DY))
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
