"""Propiedades, acciones nuevas o existentes, borradores y promoción de acciones."""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Callable
from PySide6.QtCore import QPointF
from grafcet.notation import x_etapa
from grafcet.timeutil import parse_duration
from grafcet.view import display_names
from .. import orden_acciones
from ..geometria import acciones as geo_acciones
from ..geometria.base import ajustar
from ..bloques import _dur_usuario, normalizar_duracion, sin_comillas
from ..diagrama import ACT_LINK, ACT_MIN, H, SX, posiciones
from .constantes import COLOCACIONES, CONTINUAS, DISPARADOR, MSG_ACCION_SUELTA, MSG_ORDEN_SUELTA


class _Acciones:
    def poner_accion_suelta(self, p: QPointF, tipo: str = "continua", *, vista_actual: bool = False) -> str:
        """Una ficha de acción soltada en un punto: una acción suelta de ese tipo, sin variable todavía (se dibuja con «?»),
        con su punto de unión a la izquierda. Si toca el lado derecho (o el inferior, en columna) de otra acción, se pega
        a ella: pasa a su etapa o a su grupo. No abre ningún diálogo: se une a una etapa con un enlace y se completa con
        «Editar…» (P-IMP-41, P-IMP-43). Con `tipo` «forzado», una orden de forzado suelta (P-IMP-68), con su rectángulo doble y
        «G?{?}» hasta que se configura."""
        x, y = self._modelo(p)
        iman = self._buscar_iman([], x, y, ACT_MIN)
        did = ""
        destino: list[Any] = [(None, [])]

        def hacer() -> None:
            nonlocal did
            did = self.ed.add_draft_action((x, y), {"tipo": tipo})
            if iman:
                destino[0] = self._pegar([did], iman["objetivo"])
        motivo = self._atomico("colocar acción", hacer, hueco=bool(iman), vista_actual=vista_actual)
        if motivo:
            self.rechazar(motivo)
            self.cambiado.emit()
            return ""
        if iman:
            self._tras_pegar([did], *destino[0])
        else:
            self.sel, self.accion = [did], None
            self.informar(MSG_ORDEN_SUELTA if tipo == "forzado" else MSG_ACCION_SUELTA)
            self.cambiado.emit()
        return did

    def _es_borrador(self, ident: str | None) -> bool:
        return any(b["id"] == ident for b in self.ed.draft_actions())

    def _borrador(self, did: str) -> dict[str, Any]:
        return next(b for b in self.ed.draft_actions() if b["id"] == did)

    @staticmethod
    def _pos_borrador(b: dict[str, Any]) -> tuple[float, float]:
        return float(Fraction(str(b["x"]))), float(Fraction(str(b["y"])))

    def _etiqueta_etapa(self, sid: str | None) -> str:
        return next((s["label"] for s in self.ed.model["steps"] if s["id"] == sid), "")

    def _nombre_variable(self, vid: str | None) -> str:
        v = next((v for v in self.ed.model["variables"] if v["id"] == vid), None) if vid else None
        return v["name"] if v else ""

    def _datos_borrador(self, b: dict[str, Any]) -> dict[str, str]:
        """Un borrador en la notación del usuario, con los mismos campos que `datos_accion` (vacío: lo que falta). Una
        «continua» con condición (de una versión anterior) es una condicionada."""
        d = {"tipo": b["tipo"], "variable": self._nombre_variable(b.get("variable")),
             **{k: b.get(k, "") for k in ("condicion", "valor", "evento", "limite")}}
        if d["tipo"] == "continua" and d["condicion"].strip():
            d["tipo"] = "condicionada"
        return d

    def _parcial_borrador(self, b: dict[str, Any]) -> str:
        """El parcial en cuyo ámbito se leen los textos de un borrador: el de su etapa (el raíz, si está suelto)."""
        return self.parcial_de(b["etapa"]) if b.get("etapa") else self.raiz

    def faltan(self, d: dict[str, str], parcial: str | None = None) -> list[str]:
        """Lo que le falta a una acción (datos como `datos_accion`) para ser del modelo: la variable (o una booleana, si
        es continua), la condición de una condicionada, el valor de una memorizada, el evento de una por evento y el límite
        de una limitada. Una condición o un evento a medias (con huecos, o con variables que no existen) cuentan como
        faltantes. Sus textos se leen en el ámbito del `parcial` de la etapa de la acción (por defecto, el raíz)."""
        nombre, t = d.get("variable", "").strip(), d["tipo"]
        var = next((v for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None
        out = []
        if var is None or (t in CONTINUAS and var["type"]["kind"] != "bool"):
            out.append("variable")
        cond = d.get("condicion", "").strip()
        if (t == "condicionada" and not self._texto_valido(cond, parcial)) or (t == "limitada" and cond and not self._texto_valido(cond, parcial)):
            out.append("condición")  # la limitada puede no llevar condición, pero si la lleva ha de interpretarse
        if t in DISPARADOR and not d.get("valor", "").strip():
            out.append("valor")
        if t == "evento" and not self._texto_valido(d.get("evento", ""), parcial):
            out.append("evento")
        if t == "limitada" and not normalizar_duracion(d.get("limite", "")):
            out.append("límite")
        return out

    def _borradores(self) -> list[dict[str, Any]]:
        """Los borradores como los dibuja Vista (con el arrastre en curso aplicado), en el orden de su etapa o su grupo: lo
        mismo que una acción del modelo, con «?» en lo que falta. Las de un grupo suelto comparten la posición de la
        primera."""
        try:
            nombres = display_names(self.ed.model)
        except (KeyError, TypeError, AttributeError):
            nombres = {}
        a = self.arrastre
        movidos = set(a["ids"]) if a and a.get("tipo") == "borrador" else set()
        en_grupo = {i: (x + a["x"] - a["x0"], y + a["y"] - a["y0"]) for i, (x, y) in a["inicio"].items()
                    if a["tipos"][i] == "suelta"} if a and a.get("tipo") == "grupo" else {}
        ordenados = self._borradores_ordenados()
        primeras: dict[str, dict[str, Any]] = {}
        for b in ordenados:
            if b.get("grupo") and not b.get("etapa"):
                primeras.setdefault(b["grupo"], b)
        out = []
        for b in ordenados:
            d = self._datos_borrador(b)
            suelta = not b.get("etapa")
            primera = primeras.get(b["grupo"], b) if suelta and b.get("grupo") else b
            x, y = self._pos_borrador(primera)
            if b["id"] in movidos:
                x, y = a["x"], a["y"]
            elif b["id"] in en_grupo:
                x, y = en_grupo[b["id"]]
            if b["tipo"] == "forzado":  # una orden de forzado sin completar: su rectángulo doble con «G?{?}» hasta configurarla
                out.append({"id": b["id"], "x": x, "y": y, "etapa": b.get("etapa"), "borrador": True, "grupo": b.get("grupo"),
                            "cabeza": suelta and primera["id"] == b["id"], "target": b.get("destino"), "condRef": None,
                            "falta": self._faltan_orden(b), "kind": "force", "text": [{"t": self._texto_orden(b, nombres)}]})
                continue
            var = d["variable"] or "?"
            item: dict[str, Any] = {"id": b["id"], "x": x, "y": y, "etapa": b.get("etapa"), "borrador": True,
                                    "grupo": b.get("grupo"), "cabeza": suelta and primera["id"] == b["id"],
                                    "target": None, "condRef": None, "falta": self.faltan(d, self._parcial_borrador(b))}
            if d["tipo"] in CONTINUAS:
                cond = d["condicion"].strip()
                if cond in ("1", "true"):
                    cond = ""
                segmentos = self._segmentos(cond, nombres, True) if cond else None
                if d["tipo"] == "condicionada" and not cond:
                    segmentos = [{"t": "?"}]
                if d["tipo"] == "limitada":  # el límite se dibuja como en la norma: una condición más, NOT d/X
                    xe = x_etapa(self._etiqueta_etapa(b.get("etapa"))) if b.get("etapa") else "X?"
                    lim = f"NOT {d['limite'] or '?'}/{xe}"
                    segmentos = self._segmentos(f"({cond}) AND {lim}" if cond else lim, nombres, True)
                item.update(kind="continuous", text=[{"t": var}], cond=segmentos)
            else:
                valor = self._segmentos(d["valor"], nombres) or [{"t": "?"}]
                item.update(kind="stored", trigger=DISPARADOR[d["tipo"]], text=[{"t": f"{var} := "}] + valor,
                            event=(self._segmentos(d["evento"], nombres) or [{"t": "?"}]) if d["tipo"] == "evento" else None)
            out.append(item)
        return out

    def colocacion(self, sid: str) -> str:
        """Cómo se colocan las acciones de la etapa (o del grupo suelto): «fila» (por defecto), «fila-separada»,
        «matriz-2» o «columna»."""
        valor = self.ed.action_layouts().get(sid, "fila")
        return valor if valor in dict(COLOCACIONES) else "fila"

    def colocar_acciones(self, sid: str, valor: str) -> None:
        """Cambia la colocación de las acciones de una etapa o de un grupo suelto (operación de vista, se deshace)."""
        if valor == self.colocacion(sid):
            return
        motivo = self._atomico("colocación de las acciones", lambda: self.ed.set_action_layout(sid, valor))
        self._decir(motivo)
        if motivo:
            self.parpadear([sid])

    def datos_accion(self, aid: str) -> dict[str, str]:
        """Una acción (del modelo o borrador) en la notación del usuario: tipo (continua, condicionada, limitada,
        activacion, desactivacion, evento), variable, condición (continuas; vacía si es siempre), límite (limitada), valor
        (memorizada; 1/0 para una booleana) y evento. «limitada» (una condicionada con límite de tiempo) ya no se ofrece:
        solo la traen los ficheros antiguos."""
        if self._es_borrador(aid):
            return self._datos_borrador(self._borrador(aid))
        m = self.ed.model
        a = self.ed.get(aid)
        var = next((v for v in m["variables"] if v["id"] == a["targetRef"]), None)
        nombre = var["name"] if var else a["targetRef"]
        if a["mode"] == "continuous":
            cond = self._texto(a["conditionRef"])
            cond = "" if cond in ("1", "true") else cond
            limite = _dur_usuario(int(a["limitUs"])) if "limitUs" in a else ""
            return {"tipo": "limitada" if limite else "condicionada" if cond else "continua", "variable": nombre,
                    "condicion": cond, "limite": limite}
        trig = a["trigger"]
        valor = self._texto(a["valueRef"])
        if var and var["type"]["kind"] == "bool":
            valor = {"true": "1", "false": "0"}.get(valor, valor)
        return {"tipo": {"activation": "activacion", "deactivation": "desactivacion", "event": "evento"}[trig["kind"]],
                "variable": nombre, "valor": valor, "evento": self._texto(trig.get("expressionRef"))}

    def opciones_variable_accion(self, aid: str) -> list[tuple[str, Any, bool, str]]:
        """Las opciones del desplegable sobre una acción continua (texto, dato, habilitada, papel): solo lo que puede escribir una continua,
        las salidas booleanas y luego las memorias booleanas (cada grupo en el orden de la tabla de variables), sin cabeceras. El texto es
        «nombre  (S)» o «nombre  (M)»; el desplegable pinta el papel a la derecha. Sin ninguna, «Ninguna» desactivada. (Propiedades no usa esto:
        ofrece `acciones.opciones_variable`.)"""
        v = self.fuente_bloques()[0]
        out: list[tuple[str, Any, bool, str]] = []
        for papel, letra in (("output", "S"), ("internal", "M")):
            out += [(f"{n}  ({letra})", n, True, letra) for n, (p, tipo) in v.items() if p == papel and tipo == "bool"]
        return out or [("Ninguna", "", False, "")]

    def accion_en_id(self, aid: str) -> dict[str, Any] | None:
        """La caja dibujada de la acción `aid` (como `accion_en`), o None si no está dibujada."""
        return next((c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] == aid), None)

    def desplegar_variable(self, caja: dict[str, Any]) -> None:
        """Doble clic en una acción continua: un desplegable dentro de su rectángulo con las variables que puede escribir (solo se elige la variable; el resto, en Propiedades)."""
        aid = caja["id"]
        d = self.datos_accion(aid)
        self.diagrama.abrir_selector(caja["rect"], self.opciones_variable_accion(aid), d["variable"],
                                     lambda nombre: self.elegir_variable_accion(aid, nombre))

    def elegir_variable_accion(self, aid: str, nombre: str) -> None:
        """Se eligió una variable en el desplegable de la acción: el mismo cambio que en Propiedades (una operación de deshacer)."""
        d = dict(self.datos_accion(aid))
        if d["variable"] == nombre:
            return
        d["variable"] = nombre
        motivo = self.cambiar_accion(aid, d)
        if motivo:
            self.mensaje = motivo
            self.cambiado.emit()

    @staticmethod
    def resumen_accion(d: dict[str, str]) -> str:
        """Una línea para la lista de acciones de la etapa."""
        var = d["variable"] or "?"
        if d["tipo"] in CONTINUAS:
            lim = f" hasta {d.get('limite') or '?'}" if d["tipo"] == "limitada" else ""
            if d["tipo"] == "condicionada" or d.get("condicion"):
                return var + f"   si {sin_comillas(d.get('condicion')) or '?'}" + lim
            return var + "   (continua)" + lim
        cuando = {"activacion": "al activar ↑", "desactivacion": "al desactivar ↓",
                  "evento": f"con {sin_comillas(d.get('evento')) or '?'}"}[d["tipo"]]
        return f"{var} := {sin_comillas(d.get('valor')) or '?'}   ({cuando})"

    def acciones(self, sid: str) -> list[dict[str, str]]:
        """Las acciones de la etapa: las del modelo y, al final, las unidas a ella que aún no están completas."""
        st = next(s for s in self.ed.model["steps"] if s["id"] == sid)
        out = [dict(self.datos_accion(aid), id=aid) for aid in st["actionRefs"]]
        out += [dict(self._datos_borrador(b), id=b["id"], borrador=True)
                for b in self._borradores_ordenados() if b.get("etapa") == sid and b["tipo"] != "forzado"]
        return orden_acciones.ordenar(out, orden_acciones.ids_etapa(self.ed, sid))

    @staticmethod
    def _limite_us(texto: str) -> int | None:
        """«3s», «500ms»… -> µs; None si no es una duración o es 0."""
        t = normalizar_duracion(texto)
        return parse_duration(t.replace(",", ".")) if t else None

    def _crear_o_cambiar(self, sid: str, d: dict[str, str], aid: str | None, vid: str) -> None:
        """Escribe en el modelo la acción `d` (con su variable ya resuelta): nueva en la etapa, o la `aid` cambiada."""
        var = next(v for v in self.ed.model["variables"] if v["id"] == vid)
        booleana = var["type"]["kind"] == "bool"
        if d["tipo"] in CONTINUAS:
            cond = self._n(d.get("condicion", "")) or "true"
            limite = self._limite_us(d.get("limite", "")) if d["tipo"] == "limitada" else None
            if aid:
                self.ed.update_action(aid, vid, "continuous", condition=cond, limit_us=limite)
            else:
                self.ed.add_continuous_action(sid, vid, cond, limite)
            return
        valor = d["valor"].strip()
        # el valor de una booleana es true o false; el de una entera (n := 1) sigue siendo un número
        valor = self._n({"1": "true", "0": "false"}.get(valor, valor) if booleana else valor, booleana)
        trig = DISPARADOR[d["tipo"]]
        evento = self._n(d["evento"]) if trig == "event" else None
        if aid:
            self.ed.update_action(aid, vid, "stored", trigger=trig, value=valor, event=evento)
        else:
            self.ed.add_stored_action(sid, vid, trig, valor, evento)

    def poner_accion(self, sid: str | None, d: dict[str, str], aid: str | None = None,
                     crear: tuple[str, Any] | None = None) -> str | None:
        """Añade (o, con `aid`, cambia) una acción de la etapa con los datos de `datos_accion`. Si la variable no existe
        y se da `crear` (papel, tipo), se declara antes. Con el `aid` de un borrador, lo guarda (aunque le falten datos).
        Una condicionada o por evento sin su condición o su evento (se programan en el panel de opciones) queda como
        borrador unido a la etapa. Devuelve el motivo si no se pudo; nada cambia en ese caso."""
        if aid and self._es_borrador(aid):
            return self._poner_borrador(aid, d, crear)
        m, nombre = self.ed.model, d.get("variable", "").strip()
        var = next((v for v in m["variables"] if v["name"] == nombre), None)
        if not nombre:
            return "Elija la variable sobre la que actúa."
        if var is None and crear is None:
            return f"La variable «{nombre}» no existe."
        if var is None and (motivo := self.motivo_nombre(nombre)):
            return motivo
        if d["tipo"] in DISPARADOR and not d.get("valor", "").strip():
            return "Escriba el valor que se asigna (1 o 0 para una booleana; un número o una cuenta como CT + 1)."
        if d["tipo"] == "limitada" and normalizar_duracion(d.get("limite", "")) is None:
            return "Límite de tiempo no válido: escriba «3s», «500ms»…"
        if d["tipo"] == "limitada" and not self._limite_us(d.get("limite", "")):
            return "Escriba el límite de tiempo de la acción (por ejemplo 3s)."
        sin_texto = bool({"condición", "evento"} & set(self.faltan({**d, "variable": nombre}, self.parcial_de(sid))))

        def hacer() -> None:
            vid = var["id"] if var else self.ed.add_variable(nombre, crear[0], (crear[1] if isinstance(crear[1], dict) else {"kind": crear[1]}))
            if sin_texto:  # falta programar la condición o el evento: borrador unido a la etapa, al final de la fila
                if aid:
                    self.ed.delete([aid])
                px, py = posiciones(self.M)[sid]
                did = self.ed.add_draft_action((ajustar(px - SX + H + ACT_LINK), ajustar(py)), {"etapa": sid})
                self.ed.update_draft_action(did, **self._campos_borrador(d, vid))
            else:
                self._crear_o_cambiar(sid, d, aid, vid)
        motivo = self._atomico("acción", hacer)
        if motivo:
            self.parpadear([sid])
        if motivo is None and sid not in self.sel:
            self.sel = [sid]
            self.cambiado.emit()
        return motivo

    def cambiar_accion(self, aid: str, d: dict[str, str], crear: tuple[str, Any] | None = None) -> str | None:
        """Aplica los datos de una acción (del modelo o borrador; los de `datos_accion`) en el acto, como una operación de
        deshacer: lo que hace el panel de opciones con cada cambio. Con `crear` (papel, tipo), declara antes la variable si
        no existe. Si a la acción le falta algo (la variable, el valor, la condición, el evento…), queda como borrador unido
        a su etapa; si no, es una acción del modelo. Devuelve el motivo si no se pudo (un texto que no se interpreta, un
        nombre que no vale); nada cambia en ese caso."""
        if self._es_borrador(aid):
            return self._poner_borrador(aid, d, crear)
        sid = self.ed.get(aid)["stepRef"]
        nombre = d.get("variable", "").strip()
        var = next((v for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None
        if nombre and var is None and crear is None:
            return f"La variable «{nombre}» no existe."
        if nombre and var is None and (motivo := self.motivo_nombre(nombre)):
            return motivo
        motivo = self._revisar_textos(d, self.parcial_de(sid), nombre if var is None else None)
        if motivo:
            return motivo
        falta = set(self.faltan({**d, "variable": nombre if var else ""}, self.parcial_de(sid)))
        if var is None and nombre and (d["tipo"] not in CONTINUAS or (crear[1] if isinstance(crear[1], dict) else
                                                                      {"kind": crear[1]}).get("kind") == "bool"):
            falta.discard("variable")  # la variable que se va a crear sirve para esta acción
        nuevo = [aid]

        def hacer() -> None:
            vid = (var["id"] if var else self.ed.add_variable(nombre, crear[0], (crear[1] if isinstance(crear[1], dict)
                                                                                  else {"kind": crear[1]}))) if nombre else None
            if falta:
                nuevo[0] = self._a_borrador(aid, {**d, "variable": nombre}, sid, vid)
            else:
                self._crear_o_cambiar(sid, d, aid, vid)
        return self._atomico("acción", hacer, antes_de_notificar=self._seguir_accion(aid, nuevo))

    def _seguir_accion(self, aid: str, nuevo: list[str]) -> Callable[[], None]:
        """Conserva la selección al sustituir el ID de una acción, antes de actualizar Propiedades."""
        señalada, seleccion = self.accion == aid, list(self.sel)

        def seguir() -> None:
            if nuevo[0] != aid:
                self.sel = [nuevo[0] if i == aid else i for i in seleccion]
                if señalada:
                    self.accion = nuevo[0]

        return seguir

    def _revisar_textos(self, d: dict[str, str], parcial: str | None = None, nueva: str | None = None) -> str | None:
        """Por qué un texto de la acción (condición, valor, evento) no se interpreta en el ámbito del `parcial` de su etapa
        (por defecto, el raíz); None si todos sirven. `nueva` es la variable que se va a declarar con la misma operación
        (`crear`): todavía no existe, pero un texto que solo falla por ella (`K := K + 1`) sirve, como una vez unida la
        acción a su etapa; un texto mal escrito, o con otra variable inexistente, se sigue rechazando."""
        raiz = parcial or self.raiz
        for campo, usa, booleana, nombre in (("condicion", d["tipo"] in CONTINUAS, True, "La condición"),
                                             ("valor", d["tipo"] in DISPARADOR, False, "El valor"),
                                             ("evento", d["tipo"] == "evento", True, "El evento")):
            texto = d.get(campo, "").strip()
            if usa and texto:
                diag = self.ed.check_expression(self._n(texto, booleana), raiz)
                if diag is not None and nueva:
                    faltan = self.ed.undeclared_variables(self._n(texto, booleana), raiz)
                    if faltan and set(faltan) <= {nueva}:
                        continue
                if diag is not None:
                    return f"{nombre} no es válido: {self.sust(diag.message)}"
        if d["tipo"] == "limitada" and d.get("limite", "").strip() and normalizar_duracion(d["limite"]) is None:
            return "Límite de tiempo no válido: escriba «3s», «500ms»…"
        return None

    def _campos_borrador(self, d: dict[str, str], vid: str | None) -> dict[str, Any]:
        """Los campos de un borrador para `d` (en la notación del usuario): solo los que pide su tipo."""
        relevantes = {"condicion": d["tipo"] in CONTINUAS, "valor": d["tipo"] in DISPARADOR,
                      "evento": d["tipo"] == "evento", "limite": d["tipo"] == "limitada"}
        return {"tipo": d["tipo"], "variable": vid,
                **{k: (normalizar_duracion(d[k]) if k == "limite" else d.get(k, "").strip()) if relevantes[k] else ""
                   for k in relevantes}}

    def _poner_borrador(self, did: str, d: dict[str, str], crear: tuple[str, Any] | None) -> str | None:
        """Guarda los datos de un borrador (le pueden faltar); si está unido a una etapa y queda completo, pasa a ser una
        acción del modelo en la misma operación."""
        nombre = d.get("variable", "").strip()
        var = next((v for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None
        if nombre and var is None and crear is None:
            return f"La variable «{nombre}» no existe."
        if nombre and var is None and (motivo := self.motivo_nombre(nombre)):
            return motivo
        motivo = self._revisar_textos(d, self._parcial(did), nombre if var is None else None)
        if motivo:
            return motivo

        def hacer() -> None:
            vid = (var["id"] if var else self.ed.add_variable(nombre, crear[0], (crear[1] if isinstance(crear[1], dict) else {"kind": crear[1]}))) if nombre else None
            self.ed.update_draft_action(did, **self._campos_borrador(d, vid))
            self._completar(did)
        return self._atomico("acción", hacer, antes_de_notificar=lambda: self._seleccionar_tras_borrador(did))

    def _completar(self, did: str) -> bool:
        """Si el borrador está unido a una etapa y no le falta nada, lo pasa al modelo (dentro de una operación agrupada)."""
        b = self._borrador(did)
        if b["tipo"] == "forzado":  # una orden: unida a una etapa y con destino y forma (y etapas, si es explícita)
            if not b.get("etapa") or self._faltan_orden(b):
                return False
            etapas = list(b.get("etapas", [])) if b["forma"] == "explicit" else None
            self.ed.add_force(b["etapa"], b["destino"], b["forma"], etapas)  # (un ciclo de forzado lo rechaza el núcleo)
            self.ed.delete_draft_actions([did])
            return True
        d = self._datos_borrador(b)
        if not b.get("etapa") or self.faltan(d, self._parcial_borrador(b)):
            return False
        vid = next(v["id"] for v in self.ed.model["variables"] if v["name"] == d["variable"])
        orden = orden_acciones.ids_etapa(self.ed, b["etapa"])
        self._crear_o_cambiar(b["etapa"], d, None, vid)
        nuevo = self.ed.model["actions"][-1]["id"]
        self.ed.delete_draft_actions([did])
        orden_acciones.sustituir(self.ed, b["etapa"], orden, did, nuevo)
        return True

    def _tras_borrador(self, did: str) -> None:
        self._seleccionar_tras_borrador(did)
        self.cambiado.emit()

    def anadir_accion(self, sid: str) -> str:
        """«Añadir acción…» en una etapa: una acción continua unida a ella, sin variable todavía, y se abre Editar para
        completarla (si se cierra sin completar, queda con «?»)."""
        x, y = posiciones(self.M)[sid][0] - SX, posiciones(self.M)[sid][1]
        did = ""

        def hacer() -> None:
            nonlocal did
            did = self.ed.add_draft_action((ajustar(x + H + ACT_LINK), ajustar(y)), {"etapa": sid})
        motivo = self._atomico("añadir acción", hacer)
        if motivo:
            self.rechazar(motivo, sid)
            self.cambiado.emit()
            return ""
        self.sel, self.accion, self.ver_accion = [sid], did, True
        self.cambia()
        self.pedir_accion(sid, did)
        return did

    def _accion_por_borde(self, p: QPointF) -> dict[str, Any] | None:
        """La caja de acción de una etapa cuyo borde de tirar (`_borde_accion`) queda justo por fuera del punto, que no está
        sobre ninguna otra acción: el borde se agarra a los dos lados, como un punto de unión."""
        return next((c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if self._borde_accion(c, p)), None)

    def _borde_accion(self, caja: dict[str, Any], p: QPointF) -> str | None:
        return geo_acciones.borde_accion(caja, p.toTuple(), self.colocacion)

    def anadir_accion_tras(self, aid: str, borde: str) -> str:
        """Tirar del borde de una acción de una etapa (el derecho en fila, el inferior en columna; `_borde_accion`): una acción
        nueva, vacía («?», como «Añadir acción…»), de la misma etapa y a continuación de aquella. La colocación de las acciones
        no cambia nunca. Un solo paso de deshacer (P-IMP-115)."""
        caja = next((c for c in getattr(self.diagrama, "cajas_acciones", None) or [] if c["id"] == aid), None)
        sid = caja["etapa"] if caja else None
        if not sid:
            return ""
        x, y = posiciones(self.M)[sid][0] - SX, posiciones(self.M)[sid][1]
        did = ""

        def hacer() -> None:
            nonlocal did
            did = self.ed.add_draft_action((ajustar(x + H + ACT_LINK), ajustar(y)), {"etapa": sid})
            orden_acciones.colocar_tras(self.ed, sid, [did], aid)
            self.sel, self.accion, self.ver_accion = [sid], did, True
        motivo = self._atomico("nueva acción desde una acción", hacer, vista_actual=True)
        if motivo:
            self.rechazar(motivo, sid)
            self.cambiado.emit()
            return ""
        self.pedir_accion(sid, did)
        return did

    def tipo_accion(self, ident: str, tipo: str) -> None:
        """Cambia el tipo de una acción desde el botón derecho. Una acción completa conserva su ID y su lugar. Si el tipo
        pide datos que no hay (variable booleana, valor, condición, evento), la acción queda como borrador con «?» en lo
        que falta, con el tipo ya puesto: si falta la variable o el valor se abre Editar; la condición y el evento se
        programan en el panel de opciones, que se muestra al seleccionarla. Una «Continua» no lleva condición y sale del
        tipo «limitada» (de ficheros antiguos) sin su límite."""
        d = self.datos_accion(ident)
        if d["tipo"] == tipo or (d["tipo"] == "limitada" and tipo == "condicionada"):
            return
        parcial = self._parcial(ident)
        antes = set(self.faltan(d, parcial))
        d["tipo"] = tipo
        d["limite"] = ""
        if tipo == "continua":
            d["condicion"] = ""
        falta = self.faltan(d, parcial)
        if "variable" in falta:
            d["variable"] = ""  # no sirve para el tipo nuevo (o no había): se vuelve a elegir
        abrir = bool((set(falta) - antes) & {"variable", "valor"})
        if self._es_borrador(ident):
            sid = self._borrador(ident).get("etapa")
            motivo = self._atomico("tipo de acción", lambda: (
                self.ed.update_draft_action(ident, tipo=tipo, variable=self._id_variable(d["variable"]),
                                            condicion=d.get("condicion", ""), limite=""),
                self._completar(ident)))
            self._decir(motivo)
            if motivo:
                self.parpadear([ident])
            self._tras_borrador(ident)
            if motivo is None and self._es_borrador(ident) and abrir:
                self.pedir_accion(sid, ident)
            return
        sid = self.ed.get(ident)["stepRef"]
        if not falta:  # completa: se cambia en su sitio
            self._decir(self.poner_accion(sid, d, ident))
            self.cambiado.emit()
            return
        self.separar_como_borrador(ident, d, sid, abrir)

    def _a_borrador(self, aid: str, d: dict[str, str], sid: str, vid: str | None = None) -> str:
        """Una acción del modelo que ya no está completa pasa a ser un borrador unido a su etapa (al final de su fila), con
        los datos `d` (y la variable `vid`, si no se da, la de nombre `d["variable"]`). Devuelve su ID nuevo."""
        orden = orden_acciones.ids_etapa(self.ed, sid)
        px, py = posiciones(self.M)[sid]
        nuevo = self.ed.add_draft_action((ajustar(px - SX + H + ACT_LINK), ajustar(py)), {
            "tipo": d["tipo"], "etapa": sid, "variable": vid or self._id_variable(d["variable"]),
            **{k: d[k] for k in ("condicion", "valor", "evento", "limite") if d.get(k)}})
        self.ed.delete([aid])
        orden_acciones.sustituir(self.ed, sid, orden, aid, nuevo)
        return nuevo

    def separar_como_borrador(self, aid: str, d: dict[str, str], sid: str, abrir: bool = True) -> None:
        """Una acción del modelo a la que le faltan datos tras cambiar de tipo: pasa a ser un borrador unido a su etapa
        (al final de su fila); con `abrir`, se abre Editar."""
        nuevo = ""

        def hacer() -> None:
            nonlocal nuevo
            nuevo = self._a_borrador(aid, d, sid)
        motivo = self._atomico("tipo de acción", hacer)
        self._decir(motivo)
        if motivo:
            self.parpadear([aid])
        if motivo is None:
            self.sel, self.accion = [sid], nuevo
            self.cambiado.emit()
            if abrir:
                self.pedir_accion(sid, nuevo)

    def quitar_accion(self, aid: str) -> None:
        if self._es_borrador(aid):
            self.ed.delete_draft_actions([aid])
        else:
            self.ed.delete([aid])
        self.accion = None
        self.sel = [s for s in self.sel if s != aid]
        self.cambia()

    def mover_accion(self, aid: str, delta: int) -> None:
        sid = self._borrador(aid).get("etapa") if self._es_borrador(aid) else self.ed.get(aid)["stepRef"]
        if sid:
            self._decir(self._atomico("mover acción", lambda: orden_acciones.mover(self.ed, sid, aid, delta)))

    def titulo_accion(self, aid: str, campo: str) -> str:
        """«Condición de la acción Q00 (etapa 1)» o «Evento de la acción …»."""
        d = self.datos_accion(aid)
        b = next((b for b in self.ed.draft_actions() if b["id"] == aid), None)
        sid = b.get("etapa") if b else self.ed.get(aid)["stepRef"]
        donde = f"etapa {self._nom(sid)}" if sid else "suelta"
        return f"{'Evento' if campo == 'evento' else 'Condición'} de la acción {d['variable'] or '?'} ({donde})"

    def texto_accion(self, aid: str, campo: str) -> str:
        """La condición o el evento de una acción, en la notación del usuario."""
        return self.datos_accion(aid).get(campo, "")

    def poner_texto_accion(self, aid: str, campo: str, texto: str, crear: bool = False) -> str | None:
        """Escribe la condición (o el evento) de una acción: una operación de deshacer. Si con ello la acción queda
        completa (con variable, y unida a una etapa), pasa al modelo; si deja de estarlo (texto vacío, a medias o con
        variables que no existen), pasa a ser un borrador. Con `crear`, declara antes como entradas booleanas las variables
        que no existan. Devuelve el motivo si no se pudo (un nombre que no vale); nada cambia en ese caso."""
        texto = texto.strip()
        d = self.datos_accion(aid)
        d[campo] = texto
        if crear:
            for nombre in self.sin_declarar(aid, texto):
                motivo = self.motivo_nombre(nombre)
                if motivo:
                    self.rechazar(motivo, aid)
                    self.cambiado.emit()
                    return motivo
        nuevo = [aid]

        def hacer() -> None:
            if crear:
                for nombre in self.sin_declarar(aid, texto):
                    self.ed.add_variable(nombre, "input", {"kind": "bool"})
            if self._es_borrador(aid):
                self.ed.update_draft_action(aid, **{campo: texto})
                if self._completar(aid):
                    nuevo[0] = self.ed.model["actions"][-1]["id"]
                return
            sid = self.ed.get(aid)["stepRef"]
            if self.faltan(d, self.parcial_de(sid)):
                nuevo[0] = self._a_borrador(aid, d, sid)
            else:
                self._crear_o_cambiar(sid, d, aid, self._id_variable(d["variable"]))
        etiqueta = "condición de la acción" if campo == "condicion" else "evento de la acción"
        motivo = self._atomico(etiqueta, hacer, antes_de_notificar=self._seguir_accion(aid, nuevo))
        if motivo:
            self.mensaje = motivo
            self.cambiado.emit()
            return motivo
        return None
