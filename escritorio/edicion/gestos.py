"""Eventos del lienzo, ciclo pulsar–mover–soltar, arrastre desde la paleta y vista previa."""
from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any
from PySide6.QtCore import QPointF, Qt
from grafcet.routing import project_on_link
from ..rutas_diagrama import rutas
from ..geometria import enlaces as geo_enlaces
from ..geometria.base import ajustar, punto_modelo
from ..anotaciones import rect as rect_anotacion
from ..diagrama import ACT_MIN, H, SX, ancla_en, anclas, barra, cajas_parciales, elemento_en, enlaces, posiciones
from .constantes import MSG_SOLAPE, MSG_SOLAPE_PARCIAL


class _Gestos:
    def _modelo(self, p: QPointF) -> tuple[int, int]:
        return punto_modelo(p.toTuple())

    def colocar(self, tipo: str, p: QPointF) -> None:
        """Un elemento de la paleta soltado en el dibujo: «etapa», «encapsulante», «macroetapa», «parcial», «transicion»,
        «simultaneidad», «forzado» o «accion:<tipo>» (continua, condicionada, activacion, desactivacion, evento; «accion» a secas
        es una continua). Si su caja quedaría encima de la de otro elemento (con un margen pequeño), no se coloca (un grafcet
        parcial tampoco, encima de otro marco); una acción que toca a otra se pega a ella. Una etapa, una encapsulante, una
        macroetapa o una transición pertenece al parcial en cuyo marco se suelta (`parcial_en`): una expansión, un recinto; fuera
        de todo marco, al raíz. Un «parcial» crea un grafcet parcial nuevo y vacío, con su marco (`poner_parcial`). Una orden de
        forzado se suelta como una acción (`poner_orden_ficha`): suelta, sin efecto en la simulación hasta que se configura y se
        une a una etapa; soltada sobre una etapa, se une a ella."""
        if tipo in ("texto","imagen"):
            self.poner_anotacion(tipo,p);return
        if tipo == "forzado":
            self.poner_orden_ficha(p)
            return
        if self._huella_ficha(tipo, p):
            self.informar(MSG_SOLAPE_PARCIAL if tipo == "parcial" else MSG_SOLAPE)
            self.cambiado.emit()
            return
        if tipo == "parcial":
            self.poner_parcial(p)
        elif tipo in ("etapa", "etapa_inicial", "encapsulante", "transicion"):
            with self.ed.group("colocar"):  # (con su enlace, si queda muy cerca de un punto de unión libre: un solo paso)
                if tipo == "transicion":
                    nuevo = self.poner_transicion(p)
                else:
                    nuevo = self.poner_etapa(p, inicial=tipo == "etapa_inicial", tipo="enclosing" if tipo == "encapsulante" else "ordinary")
                unido = self._unir_cercanos({nuevo}, vista_actual=True)
            if unido:
                self.cambia()
        elif tipo == "macroetapa":
            self.poner_macro(p)
        elif tipo in ("simultaneidad", "simultaneidad:apertura", "simultaneidad:cierre"):
            self.poner_barra(p, "Y")
        elif tipo == "accion" or tipo.startswith("accion:"):
            with self.ed.group("colocar acción"):
                did = self.poner_accion_suelta(p, tipo.partition(":")[2] or "continua", vista_actual=True)
                if did:
                    self._unir_cercanos({did}, vista_actual=True)

    def _zoom(self) -> float:
        escala = getattr(self.diagrama, "escala", None)
        return (escala() if callable(escala) else 1.0) or 1.0

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
        caja = (self.accion_en(p) or self._accion_por_borde(p)) if ident is None else None
        if caja and caja.get("suelta"):  # sobre una acción suelta: se ve el punto de unión de su grupo
            ident = caja["cabeza"]
        self.diagrama.marcar_anclas(anclas(self.M, ident or (cerca["id"] if cerca else "")), cerca)
        borde = self._borde_accion(caja, p) if caja else None
        if borde:  # en el borde derecho o inferior de una acción: el punto de donde se tira, y el cursor del sentido
            x, y, w, h = caja["rect"]
            punto = {"id": caja["id"], "lado": "nueva_" + borde,
                     "pos": QPointF(x + w, y + h / 2) if borde == "der" else QPointF(x + w / 2, y + h)}
            self.diagrama.marcar_anclas([punto], punto)
        vista = getattr(self.diagrama, "viewport", None)
        if callable(vista) and (borde or self._cursor_borde):
            vista().setCursor(Qt.CursorShape.SizeHorCursor if borde == "der" else Qt.CursorShape.SizeVerCursor if borde
                              else Qt.CursorShape.CrossCursor)
        self._cursor_borde = bool(borde)

    def prensar(self, p: QPointF, event: Any = None) -> bool:
        """Empieza el gesto del ratón y avisa a `tras_gesto(antes, despues)`: si pulsar ya cambia lo que mostraba el panel de
        opciones, la ventana lo esconde en ese momento (sin fijar), sin enseñar antes la página nueva."""
        self._clave_antes = self.clave_panel()
        if self.mensaje in (MSG_SOLAPE, MSG_SOLAPE_PARCIAL):  # el aviso de una ficha ya soltada no sigue a la vista
            self.mensaje = ""
            self.cambiado.emit()
        resultado = self._prensar(p, event)
        if self.tras_gesto is not None:
            self.tras_gesto(self._clave_antes, self.clave_panel())
        return resultado

    def soltar(self, p: QPointF, event: Any = None) -> bool:
        """Termina el gesto del ratón y avisa a `tras_gesto(antes, despues)` de lo que mostraba el panel de opciones al
        pulsar y de lo que muestra al soltar (lo que cambia al soltar, como una selección con lazo)."""
        antes, self._clave_antes = self._clave_antes, None
        resultado = self._soltar(p, event)
        if antes is not None and self.tras_gesto is not None:
            self.tras_gesto(antes, self.clave_panel())
        return resultado

    def _prensar(self, p: QPointF, event: Any = None) -> bool:
        ident = elemento_en(self.M, p)
        if event is not None and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            caja = (self.accion_en(p) or self.orden_en(p)) if ident is None else None
            objetivo = ident or (caja["id"] if caja else self.union_en(p))
            if objetivo:
                actual = [self.accion] if self._accion_para_quitar() else list(self.sel)
                if objetivo in actual:
                    actual.remove(objetivo)
                else:
                    actual.append(objetivo)
                self.seleccionar(actual)
                return True
        n = self.anotacion(ident)
        if n:
            if self._mayus(event):
                self.sel = [i for i in self.sel if i != ident] if ident in self.sel else self.sel+[ident]
                self.accion=None;self.cambiado.emit();return True
            if ident in self.sel and len(self.sel)>1:
                self.arrastre=self._arrastre_grupo(ident,p,([ident],None,False))
            else:
                r=rect_anotacion(n);tamano=ident in self.sel and (p-r.bottomRight()).manhattanLength()<=12
                self.sel,self.accion=[ident],None
                self.arrastre={"tipo":"tamano_anotacion" if tamano else "anotacion","id":ident,"original":dict(n),
                               "dx":p.x()-r.left(),"dy":p.y()-r.top(),"x":n["x"],"y":n["y"],"movido":False}
            self.cambiado.emit();return True
        punto = self._punto(p, ident)
        amplia = self._mayus(event)
        if punto and punto["lado"] == "izq":  # el punto de unión de una acción suelta (o de su grupo)
            self.sel, self.accion = self._ids_grupo(punto["id"]), None
            self.enlace = punto
            self.cambiado.emit()
            self.enlace = punto
            return True
        caja = (self.accion_en(p) or self._accion_por_borde(p)) if ident is None else None
        if caja:
            if caja.get("suelta") and not amplia and caja["id"] in self.sel and set(self.sel) - set(self._ids_grupo(caja["id"])):
                # una de las seleccionadas junto a otras cosas: no se deshace la selección, se mueven todas juntas
                self.accion = None
                ids = self._ids_grupo(caja["id"])
                self.arrastre = self._arrastre_grupo(ids[0], p, ([caja["id"]], caja["id"], True))
            elif caja.get("suelta"):  # se selecciona la caja pulsada y se mueve su grupo
                ids = self._ids_grupo(caja["id"])
                self.sel, self.accion = [caja["id"]], caja["id"]
                cab = self._borrador(ids[0])
                hx, hy = float(Fraction(str(cab["x"]))), float(Fraction(str(cab["y"])))
                self.arrastre = {"id": ids[0], "ids": ids, "tipo": "borrador", "dx": p.x() - (hx + SX), "dy": p.y() - hy,
                                 "x": hx, "y": hy, "movido": False}
            elif not amplia and len(self.sel) > 1 and caja["etapa"] in self.sel:
                # la acción de una etapa de una selección múltiple: se mueven todas juntas, con la etapa
                self.accion = None
                self.arrastre = self._arrastre_grupo(caja["etapa"], p, ([caja["etapa"]], caja["id"], True))
            elif caja.get("forzado"):  # una orden sin completar unida a una etapa: se selecciona ella, como una orden del modelo
                self.sel, self.accion = [caja["id"]], None
            elif amplia:  # Mayús incluye la etapa con sus acciones; copiar conserva el conjunto.
                self.sel = list(dict.fromkeys(self.sel + [caja["etapa"]]))
                self.accion, self.ver_accion = None, False
            else:  # La etapa es el contexto de propiedades; solo se resalta la acción.
                self.sel, self.accion, self.ver_accion = [caja["etapa"]], caja["id"], True
                borde = self._borde_accion(caja, p)
                if borde:  # del borde derecho o inferior, arrastrar saca una acción nueva a continuación de esta
                    self.enlace = {"id": caja["id"], "lado": "nueva_" + borde, "pos": p, "nueva": borde}
            enlace = self.enlace
            self.cambiado.emit()
            self.enlace = enlace  # (los que atienden el cambio pueden rehacer el estado del gesto)
            return True
        orden = self.orden_en(p) if ident is None and not punto else None
        if orden:  # una orden de forzado se selecciona (no se mueve ni se ordena: no es una acción)
            self.sel, self.accion = [orden["id"]], None
            self.cambiado.emit()
            return True
        union = self.union_en(p) if ident is None and not punto else None
        if union:  # el enlace de una etapa con sus acciones
            self.sel, self.accion = [union], None
            self.cambiado.emit()
            return True
        self.accion = None
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
                    self.arrastre = {"id": r["id"], "tipo": "tramo", "pts": r.get("routePts", r["pts"]), "handle": handle,
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
        if amplia and ident:  # Mayús añade a la selección (o la quita, si ya estaba) sin arrastrar
            self.sel = [i for i in self.sel if i != ident] if ident in self.sel else self.sel + [ident]
            self.cambiado.emit()
            return True
        if ident and not amplia and ident in self.sel and len(self.sel) > 1:
            # uno de varios seleccionados: no se deshace la selección; arrastrar los mueve a todos juntos (un clic sin mover
            # lo deja en solo ese, al soltar)
            self.arrastre = self._arrastre_grupo(ident, p, ([ident], None, False))
            if self.arrastre is not None:
                self.cambiado.emit()
                return True
        previa = list(self.sel) if amplia else []
        self.sel = [ident] if ident else previa
        if ident is None:  # un hueco: arrastrar dibuja el rectángulo de selección (el lazo)
            self.lazo = {"ini": p, "movido": False, "previa": previa}
        pos = posiciones(self.M).get(ident or "")
        b = self._barra(ident)
        if ident and "|" in ident:  # un enlace: agarrarlo y arrastrar mueve el tramo agarrado (no abre ninguna rama)
            self.arrastre = self._arrastre_tramo(ident, p)
        elif pos:
            self.arrastre = {"id": ident, "dx": p.x() - pos[0], "dy": p.y() - pos[1], "x": pos[0] - SX, "y": pos[1],
                             "x0": pos[0] - SX, "y0": pos[1], "movido": False}
        elif b:
            self.arrastre = {"id": ident, "tipo": "barra", "dx": p.x() - (b["x"] + SX), "dy": p.y() - b["y"],
                             "x": b["x"], "y": b["y"], "movido": False}
        elif ident in cajas_parciales(self.M) and (not next((q for q in self.M["partials"] if q["id"] == ident), {}).get("vacio")
                                                  or any(n.get("partialRef") == ident for n in self.M.get("annotations",[]))):
            self.arrastre = self._arrastre_grupo(ident, p, ([ident], None, False))
        elif vacio := next((q for q in self.M["partials"] if q["id"] == ident and q.get("vacio")), None):
            # el marco de un recinto sin etapas se mueve (su posición es lo único que lo define); el de un parcial con
            # etapas es el de ellas, y solo se selecciona
            self.arrastre = {"id": ident, "tipo": "marco", "dx": p.x() - (vacio["x"] + SX), "dy": p.y() - vacio["y"],
                             "x": vacio["x"], "y": vacio["y"], "movido": False}
        self.cambiado.emit()
        return True

    def mover(self, p: QPointF, event: Any = None) -> bool:
        a = self.arrastre
        if a and a.get("tipo") in ("anotacion","tamano_anotacion"):
            if a["tipo"] == "anotacion":
                a["x"],a["y"]=self._modelo(QPointF(p.x()-a["dx"],p.y()-a["dy"]))
            else:
                n=a["original"];w=max(20,p.x()-SX-n["x"]);h=max(20,p.y()-n["y"])
                if n["kind"] == "image":
                    k=max(w/n["width"],h/n["height"]);w,h=n["width"]*k,n["height"]*k
                a.update(width=w,height=h)
            a["movido"]=True;self.reconstruir();self.redibujar.emit();return True
        if a and a.get("tipo") in ("flecha", "tramo"):
            if (p-a["start"]).manhattanLength() < 3 and not a["movido"]:
                return True
            if a["tipo"] == "flecha":
                segment, ratio = project_on_link(a["pts"], p.toTuple())
                a["style"].setdefault("arrows", {}).setdefault(self.flecha, {}).update(segment=segment, ratio=str(ratio))
            else:
                marca = a["handle"]
                ruta = a["style"].get("route")
                anterior = a.setdefault("tramos0", (ruta or {}).get("tramos", {})) if marca.get("orient") else None

                def alinear(valor, vertical, rango):
                    return self._pegar_a_paralelo(valor, vertical, a["id"], rango)

                ajustada = geo_enlaces.ajustar_tramo(a["pts"], marca, ruta, anterior, p.toTuple(), alinear)
                if ajustada is not None:
                    a["style"]["route"] = ajustada
            a["movido"] = True
            self.reconstruir()
            self.redibujar.emit()
            return True
        if a and a.get("tipo") == "borrador":  # una acción suelta que se mueve (con las que lleva pegadas)
            x, y = self._modelo(QPointF(p.x() - a["dx"], p.y() - a["dy"]))
            if (x, y) != (a["x"], a["y"]):
                a.update(x=x, y=y, movido=True)
                self.reconstruir()
                self.redibujar.emit()
            if a["movido"] and self.diagrama is not None:  # si toca otra acción, el lado donde se pegaría
                iman = self._iman_del_arrastre(a, p)
                self.diagrama.marcar_iman(iman["linea"] if iman else None)
                self._marcar_solape(None if iman else a)
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
        if a and a.get("tipo") == "grupo":  # varios seleccionados que se mueven juntos
            if not a["movido"] and (p - a["start"]).manhattanLength() < 4:
                return True  # (sin mover todavía: aún puede ser un clic)
            x, y = self._modelo(QPointF(p.x() - a["dx"], p.y() - a["dy"]))
            x = self._iman(a["id"], x, set(a["ids"]))
            if (x, y) != (a["x"], a["y"]):
                a.update(x=x, y=y, movido=True)
                self.reconstruir()
                self.redibujar.emit()
            if a["movido"]:
                self._marcar_solape(None if self._marcar_marco_destino(a, p) else a)
            return True
        if a:
            x, y = self._modelo(QPointF(p.x() - a["dx"], p.y() - a["dy"]))
            x = self._iman(a["id"], x)
            if (x, y) != (a["x"], a["y"]):
                a.update(x=x, y=y, movido=True)
                self.reconstruir()
                self.redibujar.emit()
            if a["movido"]:
                self._marcar_solape(None if self._marcar_marco_destino(a, p) else a)
            return True
        if self.lazo:
            lz = self.lazo
            if not lz["movido"] and (p - lz["ini"]).manhattanLength() < 6:
                return True
            lz["movido"] = True
            sel = lz["previa"] + [i for i in self.dentro(lz["ini"], p) if i not in lz["previa"]]
            if sel != self.sel:
                self.sel = sel
                self.redibujar.emit()
            if self.diagrama is not None:
                self.diagrama.lazo(lz["ini"], p)
            return True
        if self.enlace and self.enlace.get("nueva"):  # de un borde de una acción: la acción nueva que saldrá
            if self.diagrama is not None:
                self.diagrama.trazo_provisional(self.enlace["pos"], p)
            return True
        if self.enlace and self.diagrama is not None:
            destino = self._destino(p, self.enlace)
            self.diagrama.trazo_provisional(self.enlace["pos"], destino["pos"] if destino else p)
            self.diagrama.marcar_anclas(anclas(self.M, destino["id"]) if destino else [], destino)
            return True
        if event is not None and not event.buttons():
            self.pasar(p)
        return False

    def _destino(self, p: QPointF, origen: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """El punto de unión al que llegaría un enlace soltado en p: el más cercano, o el de una acción suelta bajo el
        puntero. El de la derecha de una etapa solo vale para el enlace de una acción."""
        destino = ancla_en(self.M, p, sin_der=origen is not None and origen["lado"] != "izq")
        if destino is None and self._elemento_sin_marco(p) is None:
            caja = self.accion_en(p)
            if caja and caja.get("suelta"):
                destino = anclas(self.M, caja["cabeza"])[0]  # una acción de un grupo suelto: el grupo entero
        return destino

    def _soltar(self, p: QPointF, event: Any = None) -> bool:
        if self.lazo:
            lz, self.lazo = self.lazo, None
            if self.diagrama is not None:
                self.diagrama.lazo(None)
            if lz["movido"]:
                self.sel = lz["previa"] + [i for i in self.dentro(lz["ini"], p) if i not in lz["previa"]]
            self.cambiado.emit()
            return True
        if self.arrastre:
            a, self.arrastre = self.arrastre, None
            if self.diagrama is not None and hasattr(self.diagrama, "marcar_destino"):
                self.diagrama.marcar_destino(None)
            if a.get("tipo") in ("anotacion","tamano_anotacion"):
                if a["movido"]:
                    self.ed.update_annotation(a["id"],**{k:a[k] for k in ("x","y","width","height") if k in a})
                self.cambia();return True
            if a["movido"] and (destino := self._marco_destino_arrastre(a, p)):
                self._marcar_solape(None)
                return self._soltar_en_marco(a, destino)
            if a.get("tipo") == "grupo":
                return self._soltar_grupo(a)
            if a.get("tipo") == "borrador" and self.diagrama is not None:
                self.diagrama.marcar_iman(None)
            if a["movido"] and a.get("tipo") == "borrador":
                iman = self._iman_del_arrastre(a, p)
                if iman:  # tocaba otra acción: se pega a ella
                    self._marcar_solape(None)
                    self.reconstruir()
                    self.pegar(a["ids"], iman["objetivo"])
                    return True
                if self._hay_solape(a):
                    return self._devolver()
                self._marcar_solape(None)
                self.mover_grupo(a["ids"], a["x"], a["y"], unir=True)
                return True
            if a["movido"] and a.get("tipo") not in ("flecha", "tramo", "estirar") and self._hay_solape(a):
                return self._devolver()  # encima de otro elemento: vuelve a su sitio
            self._marcar_solape(None)
            if a["movido"]:  # un arrastre entero es una sola operación de deshacer
                if a.get("tipo") in ("flecha", "tramo"):
                    self.ed.set_link_style(a["id"], a["style"])
                elif a.get("tipo") == "estirar":
                    self.ed.resize_bar(a["id"], a["x"], a["ancho"])
                elif a.get("tipo") == "barra":
                    self.ed.move_bar(a["id"], a["x"], a["y"])
                else:
                    with self.ed.group("mover"):  # (y, si queda pegado a un punto de unión libre, su enlace: un solo paso)
                        self.ed.move(a["id"], a["x"], a["y"])
                        self._unir_cercanos({a["id"]})
            self.cambia()
            return True
        if self.enlace and self.enlace.get("nueva"):
            origen, self.enlace = self.enlace, None
            if self.diagrama is not None:
                self.diagrama.trazo_provisional(None)
            if (p - origen["pos"]).manhattanLength() > 8 / self._zoom():  # un clic sin arrastrar solo selecciona
                self.anadir_accion_tras(origen["id"], origen["nueva"])
            return True
        if self.enlace:
            origen, self.enlace = self.enlace, None
            if self.diagrama is not None:
                self.diagrama.trazo_provisional(None)
                self.diagrama.marcar_anclas([])
            destino = self._destino(p, origen)
            ident = self._elemento_sin_marco(p)
            if ident and "|" in ident and destino and (p - destino["pos"]).manhattanLength() > 5:
                destino = None  # sobre el trazo manda el enlace, no el halo de un tirador vecino
            if origen["lado"] in ("der", "izq") and (p - origen["pos"]).manhattanLength() <= 8 / self._zoom():
                return True
            if origen["lado"] == "der" and destino is None:
                if ident is None:
                    if (p - origen["pos"]).manhattanLength() > 8:
                        self.anadir_accion(origen["id"])
                    return True
                self.rechazar("Una acción se une a una etapa, no a una transición, una barra ni otra acción.", origen["id"])
                self.cambiado.emit()
                return True
            if origen["lado"] == "izq" and destino is None:  # de una acción suelta, solo a una etapa
                if ident is not None and any(s["id"] == ident for s in self.M["steps"]):
                    destino = sorted(anclas(self.M, ident), key=lambda a: (a["pos"] - p).manhattanLength())[0]
                else:
                    self.rechazar("Una acción se une a una etapa: suelte el enlace sobre ella.", origen["id"])
                    self.cambiado.emit()
                    return True
            if destino is None and ident and "|" in ident and ident.split("|")[2] in ("pre", "post"):
                self.unir_a_enlace(origen, ident)  # soltado sobre un enlace: una rama que se une ahí
                return True
            if destino and destino["id"] != origen["id"] and (enlace := self._enlace_del_punto(origen, destino)):
                self.unir_a_enlace(origen, enlace)  # soltado junto al tallo de una transición: el enlace que sale de él
                return True
            if destino is None and ident is None:  # soltado en un hueco: se abre una rama con el elemento que sigue
                self.crear_desde(origen, p)
                return True
            if destino is None:  # soltado sobre el cuerpo de un elemento: se une por su punto más cercano
                cerca = sorted((a for a in anclas(self.M, ident or "") if a["lado"] != "der" or origen["lado"] == "izq"),
                               key=lambda a: (a["pos"].x() - p.x()) ** 2 + (a["pos"].y() - p.y()) ** 2)
                destino = cerca[0] if cerca else None
                # desde una barra, sin apuntar a un punto concreto, cuenta dónde está el elemento: lo de encima emite hacia la
                # barra y lo de debajo recibe de ella (soltar en la mitad baja de la etapa de debajo no es unir su salida)
                barra_, pos = self._barra(origen["id"]), posiciones(self.M)
                if barra_ and ident in pos and abs(pos[ident][1] - barra_["y"]) > H:
                    lado = "abajo" if pos[ident][1] < barra_["y"] else "arriba"
                    destino = next((a for a in cerca if a["lado"] == lado), destino)
            if destino and destino["id"] != origen["id"]:
                self.unir(origen, destino)
            return True
        return False

    def _marcar_solape(self, a: dict[str, Any] | None) -> None:
        """Mientras se arrastra `a`: en rojo (y con el cursor de prohibido) lo que no se puede colocar donde está; sin
        arrastre (None), lo quita."""
        if self.diagrama is None or not hasattr(self.diagrama, "marcar_prohibido"):
            return
        malas = self._malas_arrastre(a) if a else []
        self.diagrama.marcar_prohibido(malas or None)

    def _devolver(self) -> bool:
        """Termina un arrastre que quedó encima de otro elemento: no se mueve; vuelve a su sitio con el aviso."""
        self._marcar_solape(None)
        self.informar(MSG_SOLAPE)
        self.cambia()
        return True

    def sobrevolar(self, ficha: str, p: QPointF) -> bool:
        """Una ficha que se arrastra desde la paleta pasa por encima del dibujo: una acción resalta el lado de la acción donde
        se pegaría al soltarla; si quedaría encima de otro elemento se ve en rojo y no se puede soltar (devuelve False). Una orden de
        forzado, sobre una etapa (o junto a su fila de acciones), resalta la etapa a la que se uniría; en otro sitio, como una acción."""
        if self.diagrama is None:
            return True
        if ficha == "forzado" and (sid := self._etapa_para_orden(p)) is not None:
            if hasattr(self.diagrama, "marcar_destino"):
                x, y = posiciones(self.M)[sid]
                self.diagrama.marcar_destino({"x0": x - H, "y0": y - H, "x1": x + H, "y1": y + H})
            self.diagrama.marcar_iman(None)
            if hasattr(self.diagrama, "marcar_prohibido"):
                self.diagrama.marcar_prohibido(None)
            return True
        iman = None
        if ficha == "accion" or ficha.startswith("accion:") or ficha == "forzado":
            x, y = self._modelo(p)
            iman = self._buscar_iman([], x, y, ACT_MIN)
        malas = self._huella_ficha(ficha, p)
        aviso = MSG_SOLAPE_PARCIAL if ficha == "parcial" else MSG_SOLAPE
        if malas and self.mensaje != aviso:
            self.informar(aviso)
            self.cambiado.emit()  # (vuelve a dibujar: las marcas se ponen después)
        elif not malas and self.mensaje == aviso:  # ya está sobre un hueco: el aviso no sigue diciendo lo contrario
            self.mensaje = ""
            self.cambiado.emit()
        if hasattr(self.diagrama, "marcar_destino"):  # lo que tiene parcial se recuadra en el marco donde caería (no en el raíz)
            cae = ficha in ("etapa", "encapsulante", "macroetapa", "transicion") and not malas
            self.diagrama.marcar_destino(cajas_parciales(self.M).get(self.parcial_en(p)) if cae else None)
        self.diagrama.marcar_iman(iman["linea"] if iman else None)
        if hasattr(self.diagrama, "marcar_prohibido"):
            self.diagrama.marcar_prohibido(malas or None)
        return not malas
