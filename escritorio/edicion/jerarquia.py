"""Macroetapas, parciales, recintos, acciones de jerarquía y encuadre."""
from __future__ import annotations

from typing import Any, Callable
from PySide6.QtCore import QPointF, QRectF
from grafcet.diagnostics import DiagnosticError
from grafcet.ids import label_key
from grafcet.view import force_situation
from ..geometria.base import ajustar
from ..geometria.choques import EXP_DY, EXP_INTENTOS, MARGEN_SOLAPE
from ..diagrama import H, SX, VACIO_H, VACIO_W, cajas_parciales, posiciones
from .constantes import ENCUADRE, MSG_SIN_SITIO, MSG_SOLAPE_PARCIAL, RECINTO_DX, RECINTO_PASO, TIPOS_ETAPA


class _Jerarquia:
    def _etiqueta_libre(self, prefijo: str, usadas: set[str]) -> str:
        """M1, M2… (o G1, G2…): el primero cuyo nombre no está en `usadas` (claves de `label_key`)."""
        n = 1
        while label_key(f"{prefijo}{n}") in usadas:
            n += 1
        return f"{prefijo}{n}"

    def poner_macro(self, p: QPointF) -> str | None:
        """La ficha «Macroetapa» soltada en el dibujo: la macroetapa, en el parcial de su marco (`parcial_en`: dentro de un
        recinto o de otra expansión, queda anidada), con su expansión: un parcial nuevo con la etapa de entrada y la de
        salida, a la derecha en la primera columna libre, unidas a la macroetapa por los trazos discontinuos del dibujo. Se
        rellena soltando etapas y transiciones dentro de su zona. Una sola operación de deshacer. Devuelve el ID de la
        macroetapa, o None si no se pudo (el motivo, en el mensaje)."""
        x, y = self._modelo(p)
        parcial, xe = self.parcial_en(p), self._columna_expansion(x, y)
        if xe is None:
            self.rechazar(MSG_SIN_SITIO)
            self.cambiado.emit()
            return None
        m = self.ed.model
        etiqueta = self._etiqueta_libre("M", {label_key(a["label"]) for a in m["hierarchy"]["macros"] + m["partials"]})
        hecho: list[Any] = []

        def hacer() -> None:
            ids = self.ed.add_macro(parcial, etiqueta, at=(x, y))
            self.ed.move(ids.entry, xe, y)
            self.ed.move(ids.exit, xe, y + EXP_DY)
            hecho.append(ids)
        motivo = self._atomico("colocar macroetapa", hacer)
        if motivo:
            self.rechazar(motivo)
            self.cambiado.emit()
            return None
        ids = hecho[0]
        self.sel, self.accion = [ids.macro], None
        self.informar(f"Macroetapa {etiqueta} con su expansión a la derecha: de la entrada {self.nombres.get(ids.entry, '?')} "
                      f"a la salida {self.nombres.get(ids.exit, '?')}. Suelte etapas y transiciones dentro de ella para "
                      "rellenarla (botón derecho en la macroetapa, «Encuadrar la expansión», para verla).")
        self.cambiado.emit()
        return ids.macro

    def poner_parcial(self, p: QPointF) -> str | None:
        """La ficha «Grafcet parcial» soltada en un hueco del dibujo (o «Nuevo grafcet parcial aquí» del botón derecho): un
        grafcet parcial nuevo y vacío (`add_partial`, fuera de toda jerarquía), con el primer nombre libre G1, G2… y su marco vacío
        centrado en el punto (su posición se guarda en la presentación, como la de un recinto vacío); se rellena soltando etapas
        y transiciones dentro de él. Encima de un elemento o de otro marco no crea nada y avisa. Una sola operación de deshacer.
        Devuelve el ID del parcial, o None."""
        if self._huella_ficha("parcial", p):
            self.informar(MSG_SOLAPE_PARCIAL)
            self.cambiado.emit()
            return None
        x, y = self._esquina_parcial(p)
        m = self.ed.model
        nombre = self._etiqueta_libre("G", {label_key(a["label"]) for a in m["hierarchy"]["macros"] + m["partials"]})
        hecho: list[str] = []

        def hacer() -> None:
            pid = self.ed.add_partial(nombre)
            self.ed.move(pid, x, y)
            hecho.append(pid)
        motivo = self._atomico("colocar grafcet parcial", hacer, hueco=False)
        if motivo:
            self.rechazar(motivo)
            self.cambiado.emit()
            return None
        self.sel, self.accion = [hecho[0]], None
        self.informar(f"Grafcet parcial {nombre}: suelte etapas y transiciones dentro de su marco para rellenarlo; una orden de "
                      "forzado de otra etapa puede forzarlo («Forzado» en la paleta).")
        self.cambiado.emit()
        return hecho[0]

    def renombrar_parcial(self, pid: str) -> str | None:
        """«Renombrar…» en un grafcet parcial suelto (también el doble clic en su marco): pide el nombre, con el actual de
        propuesta, y lo cambia (`rename`: único entre los parciales; el texto de las fórmulas que lo nombran se actualiza).
        Una sola operación de deshacer. Devuelve el nombre nuevo, o None (cancelado, igual o rechazado)."""
        parte = next((q for q in self.ed.model["partials"] if q["id"] == pid), None)
        if parte is None or pid == self.raiz:
            return None
        actual = parte["label"]
        nuevo = self.pedir_texto("Renombrar el grafcet parcial", f"Nuevo nombre del grafcet parcial {actual}:", actual)
        if nuevo is None or nuevo.strip() == actual:
            return None
        nuevo = nuevo.strip()
        motivo = self._atomico("renombrar el grafcet parcial", lambda: self.ed.rename(pid, nuevo), hueco=False)
        if motivo:
            self.rechazar(motivo, pid)
            self.cambiado.emit()
            return None
        self.cambiado.emit()
        return nuevo

    def _es_parcial_suelto(self, ident: str) -> bool:
        """Si el ID es el de un parcial que no es el raíz, ni un recinto, ni una expansión: un grafcet parcial suelto."""
        return ident != self.raiz and self.ed.partial_roles().get(ident, {}).get("kind") == "root"

    def tipo_encapsulante(self, sid: str, encapsulante: bool = True) -> None:
        """«Encapsulante» (esquinas cortadas en el dibujo) o «Etapa» (si no tiene recintos) del submenú «Tipo de etapa»:
        `set_step_kind`, una operación de deshacer. El núcleo rechaza lo demás (la entrada o la salida de una
        expansión, o una encapsulante con recintos): el aviso en rojo y el parpadeo de la etapa."""
        motivo = self._atomico("convertir en encapsulante" if encapsulante else "devolver a ordinaria",
                               lambda: self.ed.set_step_kind(sid, "enclosing" if encapsulante else "ordinary"))
        if motivo:
            self.rechazar(motivo, sid)
        elif encapsulante:
            self.informar(f"La etapa {self._nom(sid)} es ahora una encapsulante: botón derecho, "
                          "«Añadir recinto…», para darle recintos.")
        self.cambiado.emit()

    def cambiar_tipo_etapa(self, ident: str, tipo: str) -> None:
        """«Tipo de etapa» (el submenú del botón derecho y las casillas del panel): `tipo` es «ordinary», «enclosing» o
        «macro». Entre etapa ordinaria y encapsulante, `tipo_encapsulante`. A macroetapa: `set_step_kind` crea la
        expansión con su entrada y su salida, que se colocan a la derecha como las de la ficha «Macroetapa»
        (`poner_macro`); de macroetapa a etapa, la expansión solo puede tener su entrada y su salida (si no, se
        rechaza: «vacíe la expansión antes»). El elemento conserva su ID, su nombre y su lugar. Una sola operación de
        deshacer; un rechazo del núcleo es el aviso en rojo y el parpadeo del elemento, y no cambia nada."""
        m = self.ed.model
        es_macro = any(x["id"] == ident for x in m["hierarchy"]["macros"])
        actual = "macro" if es_macro else next((s["kind"] for s in m["steps"] if s["id"] == ident), None)
        if actual == tipo:
            self.cambiado.emit()
            return
        if actual in ("ordinary", "enclosing") and tipo != "macro":
            self.tipo_encapsulante(ident, tipo == "enclosing")
            return
        x = y = xe = 0
        if tipo == "macro":
            px, py = posiciones(self.M)[ident]
            x, y = px - SX, py
            sitio = self._columna_expansion(x, y)
            if sitio is None:
                self.rechazar(MSG_SIN_SITIO, ident)
                self.cambiado.emit()
                return
            xe = sitio

        def hacer() -> None:
            self.ed.set_step_kind(ident, tipo)
            if tipo == "macro":
                info = self.ed.macro_info(ident)
                self.ed.move(info.entry, xe, y)
                self.ed.move(info.exit, xe, y + EXP_DY)
        motivo = self._atomico("convertir en macroetapa" if tipo == "macro" else "convertir en etapa", hacer)
        if motivo:
            self.rechazar(motivo, ident)
            self.cambiado.emit()
            return
        self.sel, self.accion = [ident], None
        if tipo == "macro":
            info = self.ed.macro_info(ident)
            self.informar(f"La etapa {self._nom(ident)} es ahora una macroetapa con su expansión a la derecha: de la "
                          f"entrada {self.nombres.get(info.entry, '?')} a la salida "
                          f"{self.nombres.get(info.exit, '?')}.")
        else:
            clase = "encapsulante" if tipo == "enclosing" else "ordinaria"
            self.informar(f"La macroetapa {self._nom(ident)} es ahora una etapa {clase}; su expansión vacía se borró.")
        self.cambiado.emit()

    def _sitio_recinto(self, sid: str) -> tuple[int, int]:
        """Dónde va el marco vacío de un recinto nuevo de la encapsulante `sid`: a la derecha de ella, a la altura de su
        parte de arriba y en el primer hueco libre (esquina superior izquierda, en coordenadas del modelo)."""
        ox, oy = posiciones(self.M)[sid]
        y0, m = ajustar(oy - H - 22), MARGEN_SOLAPE
        for k in range(EXP_INTENTOS):
            x0 = ajustar(ox + RECINTO_DX + k * (VACIO_W + RECINTO_PASO) - SX)
            if self._libre(QRectF(x0 + SX, y0, VACIO_W, VACIO_H + 20).adjusted(-m, -m, m, m)):  # +20: su nombre, debajo
                return x0, y0
        return ajustar(ox + RECINTO_DX - SX), y0

    def anadir_recinto(self, sid: str) -> str | None:
        """«Añadir recinto…» en una encapsulante: pide el nombre (G1, G2… propuesto: el primero libre entre los parciales y las
        macroetapas, como el de un grafcet parcial suelto) y crea el recinto (`new_enclosure`): un
        parcial vacío dentro del de la encapsulante, sin etapa de enlace de activación todavía. Se ve como un marco vacío a
        la derecha de la encapsulante (su posición se guarda en la presentación) y se rellena soltando etapas dentro de él.
        Una sola operación de deshacer. Devuelve el ID del parcial del recinto, o None (cancelado o rechazado)."""
        if not any(s["id"] == sid for s in self.ed.model["steps"]):
            return None
        m = self.ed.model
        usadas = {label_key(a["label"]) for a in m["hierarchy"]["macros"] + m["partials"]}
        nombre = self.pedir_texto("Añadir recinto", f"Nombre del recinto de la encapsulante {self._nom(sid)}:",
                                  self._etiqueta_libre("G", usadas))
        if nombre is None:
            return None
        nombre, hecho = nombre.strip(), []
        x, y = self._sitio_recinto(sid)

        def hacer() -> None:
            ids = self.ed.new_enclosure(sid, nombre)
            self.ed.move(ids.partial, x, y)
            hecho.append(ids)
        motivo = self._atomico("añadir recinto", hacer)
        if motivo:
            self.rechazar(motivo, sid)
            self.cambiado.emit()
            return None
        self.sel, self.accion = [hecho[0].partial], None
        self.informar(f"Recinto {nombre} de la encapsulante {self._nom(sid)}: suelte etapas dentro de su marco "
                      "para rellenarlo; botón derecho en una etapa suya, «Enlace de activación», la marca (*).")
        self.cambiado.emit()
        return hecho[0].partial

    def enlace_activacion(self, sid: str, marcar: bool | None = None) -> None:
        """Marca o desmarca (sin `marcar`, alterna) el enlace de activación de una etapa de un recinto (el «*» del dibujo):
        `set_activation`, una operación de deshacer. Una etapa que no es de un recinto lo rechaza el núcleo."""
        rol = self.ed.partial_roles().get(self.parcial_de(sid))
        actual = bool(rol and rol["kind"] == "enclosure" and sid in rol["activation"])
        on = (not actual) if marcar is None else marcar
        motivo = self._atomico("enlace de activación" if on else "quitar el enlace de activación",
                               lambda: self.ed.set_activation(sid, on))
        if motivo:
            self.rechazar(motivo, sid)
        self.cambiado.emit()

    def _caja_encuadre(self, ident: str) -> QRectF | None:
        """La caja del dibujo que se encuadra para mostrar un elemento: el marco de un parcial (un recinto, un grafcet parcial o
        la zona de una expansión, con su nombre debajo) o un cuadrado de ENCUADRE de semilado alrededor de una etapa o una
        macroetapa; None si no está dibujado."""
        b = cajas_parciales(self.M).get(ident)
        if b is not None:
            return QRectF(b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"]).adjusted(-10, -10, 10, 18)
        p = posiciones(self.M).get(ident)
        return QRectF(p[0] - ENCUADRE, p[1] - ENCUADRE, 2 * ENCUADRE, 2 * ENCUADRE) if p is not None else None

    def encuadrar(self, destino: list[str], texto: str = "") -> bool:
        """Encuadra `destino` (los ID de lo que se quiere ver: la expansión, la macroetapa, el recinto o la encapsulante): lo
        selecciona, encaja y centra en la vista su caja, o la de todos juntos (`VistaDiagrama.encuadrar`: el zoom que los hace
        caber con margen, sin pasar del tope de «Centrar todo»), lo resalta con el parpadeo naranja de la edición para que
        aparezca en primer plano y avisa con `texto`. Es solo navegación: no toca el modelo, el historial ni la marca de
        cambios. Devuelve si había algo dibujado que encuadrar."""
        cajas = [c for c in (self._caja_encuadre(i) for i in destino) if c is not None]
        if not cajas:
            return False
        r = cajas[0]
        for c in cajas[1:]:
            r = r.united(c)
        self.sel, self.accion = list(destino), None
        if texto:
            self.informar(texto)
        self.cambiado.emit()
        if hasattr(self.diagrama, "encuadrar"):
            self.diagrama.encuadrar(r)
        self.parpadear(destino, centrar=False)  # (la vista ya está encuadrada)
        return True

    def encuadrar_expansion(self, mid: str) -> bool:
        """«Encuadrar la expansión» (REQ-EDT-08, REQ-JER-07), también el doble clic en una macroetapa: encuadra la zona de su
        expansión (`encuadrar`) y deja su parcial seleccionado. Devuelve si la macroetapa tiene expansión."""
        try:
            info = self.ed.macro_info(mid)
        except DiagnosticError as exc:
            self.rechazar("; ".join(self.sust(d.message) for d in exc.diagnostics), mid)
            self.cambiado.emit()
            return False
        return self.encuadrar([info.partial], f"Expansión de la macroetapa {self._nom(mid)}: de la entrada "
                              f"{self.nombres.get(info.entry, '?')} a la salida {self.nombres.get(info.exit, '?')}.")

    def encuadrar_macroetapa(self, mid: str) -> bool:
        """«Encuadrar la macroetapa»: al revés que «Encuadrar la expansión», desde la entrada o la salida de una expansión o
        desde su zona."""
        return self.encuadrar([mid], self.descripcion_jerarquia(mid) or self.nombre(mid))

    def encuadrar_encapsulante(self, sid: str) -> bool:
        """«Encuadrar la encapsulante», desde una etapa de un recinto o desde su marco."""
        return self.encuadrar([sid], self.descripcion_jerarquia(sid) or self.nombre(sid))

    def encuadrar_recintos(self, sid: str) -> bool:
        """«Encuadrar el recinto» (o «los recintos», si la encapsulante tiene varios), desde la encapsulante: encuadra el marco
        de cada uno, juntos, y los deja seleccionados."""
        recintos = [r["partialRef"] for r in self.ed.model["hierarchy"]["enclosures"] if r["ownerStepRef"] == sid]
        nom = self.descripcion_jerarquia(recintos[0]) if len(recintos) == 1 else \
            f"Recintos de la encapsulante {self._nom(sid)}: {', '.join(self._nom(r) for r in recintos)}"
        return bool(recintos) and self.encuadrar(recintos, nom)

    def renombrar_macro(self, mid: str, nuevo: str | None = None) -> str | None:
        """Pide o aplica el nombre de la macroetapa, su expansión y sus E/S, en una sola operación."""
        mac = next((x for x in self.ed.model["hierarchy"]["macros"] if x["id"] == mid), None)
        if mac is None:
            return None
        actual = mac["label"]
        if nuevo is None:
            nuevo = self.pedir_texto("Renombrar la macroetapa", f"Nuevo nombre de la macroetapa {actual}:", actual)
        if nuevo is None or nuevo.strip() == actual:
            return None
        nuevo = nuevo.strip()
        motivo = self.cambiar_nombre_macro(mid, nuevo)
        if motivo:
            self.rechazar(motivo, mid)
            return None
        return nuevo

    def cambiar_nombre_macro(self, mid: str, nuevo: str) -> str | None:
        """Renombra M y solo las E/S que seguían su sufijo; un rechazo conserva íntegro el documento."""
        mac = next(x for x in self.ed.model["hierarchy"]["macros"] if x["id"] == mid)
        actual = mac["label"]
        info = self.ed.macro_info(mid)
        sufijo = actual.removeprefix("M")
        nuevo_sufijo = nuevo.removeprefix("M")
        arrastradas = []
        for sid, prefijo in ((info.entry, "E"), (info.exit, "S")):
            etapa = next(s for s in self.ed.model["steps"] if s["id"] == sid)
            if etapa["label"] == prefijo + sufijo:
                arrastradas.append((sid, prefijo + nuevo_sufijo))
        con_ella = next(p["label"] for p in self.ed.model["partials"] if p["id"] == info.partial) == actual

        def hacer() -> None:
            self.ed.rename(mid, nuevo)
            for sid, nombre in arrastradas:
                self.ed.rename(sid, nombre)
            if con_ella:
                self.ed.rename(info.partial, nuevo)

        motivo = self._atomico("renombrar la macroetapa", hacer)
        self.cambiado.emit()
        return motivo

    def acciones_jerarquia(self, ident: str) -> list[tuple[str, Callable[[], Any], bool | None]]:
        """Las acciones de jerarquía de una macroetapa, una etapa, un parcial con marco o una orden de forzado, como
        [(texto, función, estado)]: `estado` es None si es un botón, y True o False si es una casilla (marcada o no). Son las
        opciones del botón derecho (`menu`) y los botones de la ficha del panel de opciones (`ficha_jerarquia`): ninguna
        toca el modelo si no lo dice (encuadrar) y las demás son una operación de deshacer. Encuadrar lleva la vista al otro
        lado de una dependencia: de la macroetapa a su expansión y al revés, de la encapsulante a su(s) recinto(s) y al
        revés."""
        m = self.ed.model
        if any(x["id"] == ident for x in m["hierarchy"]["macros"]):
            return [*self._tipos_etapa(ident, "macro"),
                    ("Encuadrar la expansión", lambda: self.encuadrar_expansion(ident), None),
                    ("Renombrar…", lambda: self.renombrar_macro(ident), None)]
        if self.es_orden_suelta(ident):  # una orden sin completar: se configura y se quita
            return [("Configurar orden de forzado…", lambda: self.configurar_orden(ident), None),
                    ("Quitar orden de forzado", lambda: self.quitar_orden(ident), None)]
        if any(f["id"] == ident for f in m["forces"]):
            return [("Editar orden de forzado…", lambda: self.editar_orden(ident), None),
                    ("Quitar orden de forzado", lambda: self.quitar_orden(ident), None)]
        roles = self.ed.partial_roles()
        if ident in roles:  # un parcial con marco: a la encapsulante o a la macroetapa que lo contiene; un parcial suelto se renombra
            rol = roles[ident]
            if rol["kind"] == "enclosure":
                return [("Encuadrar la encapsulante", lambda: self.encuadrar_encapsulante(rol["ownerStep"]), None)]
            if rol["kind"] == "expansion":
                return [("Encuadrar la macroetapa", lambda: self.encuadrar_macroetapa(rol["macro"]), None)]
            return [("Renombrar…", lambda: self.renombrar_parcial(ident), None)] if self._es_parcial_suelto(ident) else []
        st = next((s for s in m["steps"] if s["id"] == ident), None)
        if st is None:
            return []
        out: list[tuple[str, Callable[[], Any], bool | None]] = []
        if st["kind"] in ("ordinary", "enclosing"):  # la entrada y la salida de una expansión no cambian de tipo
            out += self._tipos_etapa(ident, st["kind"])
        if st["kind"] == "enclosing":
            out.append(("Añadir recinto…", lambda: self.anadir_recinto(ident), None))
            recintos = [r for r in m["hierarchy"]["enclosures"] if r["ownerStepRef"] == ident]
            if recintos:
                out.append(("Encuadrar el recinto" if len(recintos) == 1 else "Encuadrar los recintos",
                            lambda: self.encuadrar_recintos(ident), None))
        rol = roles.get(st["partialRef"])
        if rol and rol["kind"] == "enclosure":  # una etapa de un recinto: su enlace de activación (casilla) y su encapsulante
            out.append(("Enlace de activación", lambda: self.enlace_activacion(ident), ident in rol["activation"]))
            out.append(("Encuadrar la encapsulante", lambda: self.encuadrar_encapsulante(rol["ownerStep"]), None))
        macro = next((x["ownerMacroRef"] for x in m["hierarchy"]["expansions"] if ident in (x["entryRef"], x["exitRef"])), None)
        if st["kind"] in ("entry", "exit") and macro is not None:  # la entrada y la salida de una expansión: a su macroetapa
            out.append(("Encuadrar la macroetapa", lambda: self.encuadrar_macroetapa(macro), None))
        if self._destinos_forzado(ident):
            out.append(("Forzar un parcial…", lambda: self.forzar(ident), None))
        return out

    def _tipos_etapa(self, ident: str, actual: str) -> list[tuple[str, Callable[[], Any], bool | None]]:
        """Los tipos de una etapa o de una macroetapa como casillas excluyentes (la del tipo `actual`, marcada)."""
        return [(texto, lambda t=tipo: self.cambiar_tipo_etapa(ident, t), tipo == actual)
                for tipo, texto, _ in TIPOS_ETAPA]

    def descripcion_jerarquia(self, ident: str) -> str:
        """Una línea con lo que un elemento es en la jerarquía, con nombres (nunca IDs): «Macroetapa M1 · expansión M1 ·
        entrada E1 · salida S1», «Recinto G1 de H · activación: K», «Orden: H fuerza G1 a {K}»…; vacío si no es de la
        jerarquía (una etapa ordinaria del raíz)."""
        m, nom = self.ed.model, self._nom
        if self.es_orden_suelta(ident):
            return self._descripcion_orden_suelta(self._borrador(ident))
        if any(x["id"] == ident for x in m["hierarchy"]["macros"]):
            try:
                x = self.ed.macro_info(ident)
            except DiagnosticError:
                return f"Macroetapa {nom(ident)}"
            return f"Macroetapa {nom(ident)} · expansión {nom(x.partial)} · entrada {nom(x.entry)} · salida {nom(x.exit)}"
        f = next((f for f in m["forces"] if f["id"] == ident), None)
        if f is not None:
            situacion = {"explicit": "a " + force_situation(f, self.nombres), "current": "a la situación actual",
                         "empty": "a la situación vacía", "initial": "a su situación inicial"}.get(f["targetKind"], "")
            return f"Orden: {nom(f['sourceStepRef'])} fuerza {nom(f['targetPartialRef'])} {situacion}".rstrip()
        roles = self.ed.partial_roles()
        rol = roles.get(ident)
        if rol and rol["kind"] == "enclosure":
            marcas = ", ".join(nom(x) for x in rol["activation"]) or "ninguna"
            return f"Recinto {nom(ident)} de {nom(rol['ownerStep'])} · activación: {marcas}"
        if rol and rol["kind"] == "expansion":
            return f"Expansión de la macroetapa {nom(rol['macro'])} · entrada {nom(rol['entry'])} · salida {nom(rol['exit'])}"
        if rol and self._es_parcial_suelto(ident):  # un grafcet parcial suelto, y quién lo fuerza
            desde = [nom(f["sourceStepRef"]) for f in m["forces"] if f["targetPartialRef"] == ident]
            return f"Grafcet parcial {nom(ident)}" + (f" · forzado desde {', '.join(dict.fromkeys(desde))}" if desde else "")
        st = next((s for s in m["steps"] if s["id"] == ident), None)
        if st is None:
            return ""
        partes = []
        if st["kind"] == "enclosing":
            recintos = [nom(r["partialRef"]) for r in m["hierarchy"]["enclosures"] if r["ownerStepRef"] == ident]
            partes.append(f"Encapsulante {nom(ident)} · " + (f"recintos: {', '.join(recintos)}" if recintos else "sin recintos"))
        elif st["kind"] in ("entry", "exit") and (x := next((x for x in m["hierarchy"]["expansions"]
                                                             if ident in (x["entryRef"], x["exitRef"])), None)):
            partes.append(f"{'Entrada' if st['kind'] == 'entry' else 'Salida'} de la expansión de la macroetapa "
                          f"{nom(x['ownerMacroRef'])}")
        rol = roles.get(st["partialRef"])
        if rol and rol["kind"] == "enclosure":
            partes.append(f"Del recinto {nom(st['partialRef'])} de {nom(rol['ownerStep'])} · "
                          + ("con" if ident in rol["activation"] else "sin") + " enlace de activación")
        return " · ".join(partes)

    def ficha_jerarquia(self, ident: str) -> dict[str, Any] | None:
        """Lo que muestra el panel de opciones de un elemento de jerarquía: {texto (su descripción, o vacío), botones
        (`acciones_jerarquia`)}; None si no hay ni una cosa ni la otra (por ejemplo, una transición)."""
        texto, botones = self.descripcion_jerarquia(ident), self.acciones_jerarquia(ident)
        return {"texto": texto, "botones": botones} if texto or botones else None
