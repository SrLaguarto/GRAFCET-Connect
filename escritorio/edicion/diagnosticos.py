"""Avisos, resaltado, diagnóstico y parpadeo. Incluye la clase Parpadeo."""
from __future__ import annotations

import re
from typing import Any
from PySide6.QtCore import QObject, QTimer, Signal
from grafcet.ids import label_key
from grafcet.view import display_names, force_situation, substitute
from ..mensajes import amable, correccion_amable, mezcla_acciones
from ..bloques import sin_comillas
from ..diagrama import cajas_parciales, posiciones
from .constantes import INTERNO, MSG_ENCIMA, PARPADEO_MS, PARPADEO_PASOS

VALIDACIONES_RECORDADAS = 6
from .utilidades import sin_codigos


class Parpadeo(QObject):
    """Parpadeo naranja de lo que da error (REQ-EDT-09): un conjunto de ID (elementos del dibujo o filas de variables) que
    se enciende y se apaga unas veces con un temporizador. No sabe de aspecto: quien dibuja pregunta `activos()` y
    redibuja cuando `cambia` avisa. Sin pantalla, se comprueba el estado (`ids`, `fase`, `t.isActive()`)."""

    cambia = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.ids: set[str] = set()
        self.fase = False
        self.restan = 0
        self.t = QTimer(self)
        self.t.setInterval(PARPADEO_MS)
        self.t.timeout.connect(self.paso)

    def iniciar(self, ids: Any) -> None:
        """Empieza a parpadear con estos ID (si ya parpadeaba otra cosa, la sustituye)."""
        self.ids, self.fase, self.restan = set(ids), True, PARPADEO_PASOS
        self.t.start()
        self.cambia.emit()

    def paso(self) -> None:
        self.restan -= 1
        if self.restan <= 0:
            self.parar()
            return
        self.fase = not self.fase
        self.cambia.emit()

    def parar(self) -> None:
        self.t.stop()
        hubo = self.fase or bool(self.ids)
        self.ids, self.fase, self.restan = set(), False, 0
        if hubo:
            self.cambia.emit()

    def activos(self) -> set[str]:
        """Los que se dibujan en naranja ahora (vacío en la fase apagada)."""
        return set(self.ids) if self.fase else set()


class _Diagnosticos:
    @property
    def mensaje(self) -> str:
        return self._mensaje

    @mensaje.setter
    def mensaje(self, texto: str) -> None:
        # por defecto, un error o un rechazo
        self._mensaje, self.mensaje_info = sin_codigos(self.sin_internos(texto)), False
        self.vigencia_aviso.registrar()
        from ..vigencia_avisos import seleccion_actual
        self.seleccion_aviso = seleccion_actual(self)

    def informar(self, texto: str) -> None:
        """Un aviso informativo (no un error): se muestra sin el rojo de los rechazos."""
        self._mensaje, self.mensaje_info = sin_codigos(self.sin_internos(texto)), True
        self.vigencia_aviso.registrar()
        from ..vigencia_avisos import seleccion_actual
        self.seleccion_aviso = seleccion_actual(self)

    def texto_estado(self) -> tuple[str, bool]:
        """Lo que dice la barra de estado ahora: el mensaje de la última operación (con `mensaje_info`: informativo, no un error) y, si no
        hay ninguno, el de lo seleccionado, **calculado del estado de ahora** y no al cambiar la selección: una acción suelta dice cómo
        unirla mientras siga suelta (al unirla el texto se va y, al deshacer, vuelve)."""
        from ..vigencia_avisos import texto_estado
        return texto_estado(self)

    def _nombres_vivos(self) -> dict[str, str]:
        """El nombre visible de cada elemento del modelo tal como está ahora (no como se dibujó por última vez), con el de los
        enlaces en borrador («enlace en borrador 2→0»); los de la última vista siguen valiendo para lo que ya no está."""
        try:
            nombres = display_names(self.ed.model)
        except (KeyError, TypeError, AttributeError):
            nombres = {}
        for d in self.ed.model.get("draftLinks", []):
            nombres[d["id"]] = f"enlace en borrador {nombres.get(d['fromRef'], '?')}→{nombres.get(d['toRef'], '?')}"
        return {**self.nombres, **nombres}

    def sust(self, texto: str) -> str:
        """El texto de un diagnóstico del núcleo (mensaje, corrección, `DiagnosticError`) sin ID: el núcleo escribe los ID de
        los elementos y aquí se cambian por sus nombres (los de la última vista dibujada; el ID interno que falte, por el del
        modelo de ahora, y el que ya no existe se llama «un elemento»). Solo para lo que trae ID del núcleo: sustituye palabras
        enteras, así que un texto de la aplicación (que no los trae) no debe pasar por aquí; esos interpolan el nombre en origen
        (`_nom`). Quita las comillas invertidas de los nombres con espacios, que el usuario no ve."""
        if not texto:
            return texto
        return amable(sin_codigos(self.sin_internos(sin_comillas(substitute(texto, self.nombres)))))

    def sin_internos(self, texto: str) -> str:
        """Lo último que se hace con un mensaje antes de enseñarlo: cada ID interno que haya quedado en él (el que crea el
        editor, de la forma `s-<32 cifras hexadecimales>`) se cambia por el nombre de su elemento (el de la última vista; si no,
        el del modelo de ahora) o por «un elemento» si ya no existe. Solo toca esos ID: ni una palabra más del texto, de modo que
        el texto fijo de la aplicación no cambia aunque el ID de una variable de un fichero externo sea «a»."""
        if not texto or not INTERNO.search(texto):
            return texto
        dibujados, vivos = self.nombres, None

        def nombre(mo: re.Match[str]) -> str:
            nonlocal vivos
            ident = mo.group(0)
            n = dibujados.get(ident)
            if n is None:
                vivos = self._nombres_vivos() if vivos is None else vivos  # (solo si hace falta: recorre el modelo)
                n = vivos.get(ident)
            return "un elemento" if n is None or INTERNO.fullmatch(n) else n
        return INTERNO.sub(nombre, texto)

    def _nom(self, ident: str) -> str:
        """El nombre de un elemento para un texto de la aplicación, que lo interpola en origen en vez de sustituir después: el
        de la última vista dibujada o, si no está, el del modelo de ahora; el ID interno que ya no existe se llama «un elemento»
        y el que no es interno (el de un ejemplo o de un fichero externo) es su propio nombre."""
        n = self.nombres.get(ident)
        if n is None:
            n = self._nombres_vivos().get(ident)
        if n is None:
            return "un elemento" if INTERNO.fullmatch(ident) else ident
        return n

    def _validacion(self) -> Any:
        """El resultado de validar el modelo del editor. Los documentos del editor son inmutables (cada cambio crea otros: Editor._txn),
        así que mientras `ed.model` y `ed.presentation` sean los mismos objetos el resultado es el mismo y no se vuelve a calcular."""
        ed, memoria = self.ed, self._memo_validacion
        for modelo, presentacion, resultado in memoria:
            if modelo is ed.model and presentacion is ed.presentation:
                return resultado
        resultado = ed.validate()
        memoria.append((ed.model, ed.presentation, resultado))
        del memoria[:-VALIDACIONES_RECORDADAS]  # (deshacer y rehacer vuelven a documentos ya validados)
        return resultado

    def diagnosticos(self) -> list[dict[str, Any]]:
        """Los diagnósticos del modelo para el panel (REQ-EDT-09): código, texto con nombres, corrección y elemento."""
        out = []
        repetidas = self._grupos_repetidos()
        for grupo in repetidas:  # un solo aviso por número repetido, con todas sus etapas marcadas en el dibujo (P-IMP-118)
            n = len(grupo)
            etiqueta = self.ed.get(grupo[0])["label"]
            que = "número" if etiqueta.isdigit() else "nombre"
            mensaje = (f"Hay dos etapas con el {que} {etiqueta}: cambie una." if n == 2 else
                       f"Hay {n} etapas con el {que} {etiqueta}: deje solo una con ese {que}.")
            out.append({"code": "D-NOMBRE-COLISION", "message": mensaje,
                        "correction": "Cambie el número de una de las etapas marcadas (en Propiedades, o con doble clic en ella)",
                        "severity": "error", "blocks": True, "question": None, "element": grupo[0], "target": grupo[0],
                        "targets": list(grupo)})
        enrepetidas = {i for g in repetidas for i in g}
        for d in self._validacion().diagnostics:
            if d.code == "D-NOMBRE-COLISION" and d.element in enrepetidas:
                continue
            mensaje, correccion = self.sust(d.message), self.sust(correccion_amable(d.code, d.correction))
            evento = next((a for a in self.ed.model["actions"] if a.get("trigger", {}).get("kind") == "event" and d.element in (a["id"],a["trigger"].get("expressionRef"))), None)
            if d.code == "D-TIPO-EVENTO" and evento:
                texto = sin_comillas(self.texto_accion(evento["id"], "evento"))
                mensaje = (f"Acción por evento de {self._nom(evento['targetRef'])} en la etapa {self._nom(evento['stepRef'])}: "
                           f"el disparador «{texto}» debe ser un evento, no solo una condición booleana.")
                correccion = "Elija el evento que deba disparar la acción: flanco de subida (↑) o de bajada (↓) de la variable."
                mensaje += " Use un flanco de subida (↑) o de bajada (↓), según lo que necesite."
            if d.code == "D-EXP-PENDIENTE":
                mensaje = self._texto_expresion_pendiente(mensaje, self.dibujable(d.element))
            if d.code == "D-SIMULTANEIDAD":
                mensaje += self._lados_cruzados(d.element)
            if d.code == "D-MODO-SALIDA":
                mensaje = mezcla_acciones(self.ed.model, self.nombres, d.element)
            mensaje = sin_codigos(mensaje)
            out.append({"code": d.code, "message": mensaje, "correction": correccion,
                        "severity": d.severity, "blocks": d.blocks_start, "question": d.question,
                        "element": d.element, "target": evento["id"] if d.code == "D-TIPO-EVENTO" and evento else self.dibujable(d.element),
                        "completo": d.code in ("D-SIMULTANEIDAD", "D-BARRA-SUELTA", "D-MODO-SALIDA")
                        or (d.code == "D-ALTERNANCIA" and self._es_enlace_borrador(d.element))})
        if self.ignorados:
            out.append({"code": "AVISO", "severity": "advertencia", "blocks": False, "question": None, "element": None,
                        "target": None, "correction": "Se descartó al abrir; vuelva a colocar la acción si hacía falta",
                        "message": "Se ignoró un borrador de acción dañado" if self.ignorados == 1
                        else f"Se ignoraron {self.ignorados} borradores de acción dañados"})
        for b in self.ed.draft_actions():  # diagnósticos de la edición: los borradores no están en el modelo ejecutable
            suelta = not b.get("etapa")
            if b["tipo"] == "forzado":
                falta = self._faltan_orden(b)
                out.append({"code": "D-FORZADO-PENDIENTE", "severity": "bloqueo", "blocks": True, "question": None, "element": b["id"],
                            "target": b["id"],
                            "message": "Orden de forzado sin configurar suelta" if suelta else
                            f"Orden de forzado sin configurar en la etapa {self.nombre(b['etapa'])} ({', '.join(falta)})",
                            "correction": "Una la orden a una etapa con un enlace desde su punto de unión izquierdo"
                            if suelta else "Elija su parcial destino y su forma con «Configurar orden de forzado…» (botón derecho "
                            "en ella, o doble clic)"})
                continue
            out.append({"code": "D-ACCION-PENDIENTE", "severity": "bloqueo",
                        "blocks": True, "question": None, "element": b["id"], "target": b["id"],
                        "message": "Acción sin configurar suelta" if suelta else
                        f"Acción sin configurar en la etapa {self.nombre(b['etapa'])} "
                        f"({', '.join(self.faltan(self._datos_borrador(b), self._parcial_borrador(b)))})",
                        "correction": "Una la acción a una etapa con un enlace desde su punto de unión izquierdo"
                        if suelta else "Complete la acción con «Editar…» (botón derecho en ella)"})
        return out

    def _lados_cruzados(self, barra_id: str | None) -> str:
        """Si algo está unido a la barra por el lado contrario al que se ve (encima, por abajo; debajo, por arriba): una frase
        que lo dice, para añadir al aviso de la barra (su enlace da la vuelta en el dibujo); si no, vacío."""
        b = next((b for b in self.M.get("bars", []) if b["id"] == barra_id), None)
        if b is None:
            return ""
        pos = posiciones(self.M)
        mal = [(i, lado) for lado, ids in (("arriba", b["arriba"]), ("abajo", b["abajo"])) for i in ids
               if i in pos and (pos[i][1] > b["y"] if lado == "arriba" else pos[i][1] < b["y"])]
        if not mal:
            return ""
        quien = ", ".join(self._nom(i) for i, _ in mal)
        return (f" {quien} {'está' if len(mal) == 1 else 'están'} unida{'' if len(mal) == 1 else 's'} por el lado contrario al que "
                "se ve (su línea da la vuelta a la barra): quítela de la barra y vuelva a unirla desde su salida, si va antes de la "
                "barra, o a su entrada, si va después.")

    def _es_enlace_borrador(self, ident: str | None) -> bool:
        return any(d["id"] == ident for d in self.ed.model.get("draftLinks", []))

    def _texto_expresion_pendiente(self, mensaje: str, objetivo: str | None) -> str:
        """D-EXP-PENDIENTE en palabras normales: «la receptividad está vacía» o «no es válida: «texto»» (de una
        transición; de una acción, «la condición o el valor»)."""
        es_transicion = any(t["id"] == objetivo for t in self.ed.model["transitions"])
        que = "la receptividad" if es_transicion else "la condición o el valor"
        texto = re.search(r"«(.*)»", mensaje)
        if "sin significado" in mensaje and (texto is None or not texto.group(1).strip()):
            return f"{que} está vacía"
        return f"{que} no es válida" + (f": «{sin_comillas(texto.group(1))}»" if texto and texto.group(1).strip() else "")

    def dibujable(self, elemento: str | None) -> str | None:
        """El elemento del dibujo al que se refiere un diagnóstico (una receptividad, la transición que la usa)."""
        if elemento is None:
            return None
        m = self.ed.model
        if elemento in posiciones(self.M) or any(d["id"] == elemento for d in m["draftLinks"]) \
                or any(d["id"] == elemento for d in self.ed.draft_actions()):
            return elemento
        for t in m["transitions"]:
            if t["conditionRef"] == elemento:
                return t["id"]
        for a in m["actions"]:
            if a.get("trigger", {}).get("expressionRef") == elemento:
                return a["id"]
            if a["id"] == elemento or elemento in (a.get("conditionRef"), a.get("valueRef")):
                return a["stepRef"]
        for r in m["hierarchy"]["enclosures"]:  # un recinto: su encapsulante; una expansión: su macroetapa
            if r["id"] == elemento:
                return r["ownerStepRef"]
        for x in m["hierarchy"]["expansions"]:
            if x["id"] == elemento:
                return x["ownerMacroRef"]
        if any(f["id"] == elemento for f in m["forces"]):  # una orden de forzado: su caja, en la fila de su etapa
            return elemento
        return elemento if elemento in cajas_parciales(self.M) or any(b["id"] == elemento for b in self.M.get("bars", [])) else None

    def marcados(self) -> set[str]:
        return self.marcados_de(self.diagnosticos())

    @staticmethod
    def marcados_de(diags: list[dict[str, Any]]) -> set[str]:
        """Los elementos del dibujo que se marcan en rojo: el de cada diagnóstico que impide simular (un aviso puede
        marcar varios, como las etapas con el mismo número)."""
        return {t for d in diags if d["blocks"] for t in (d.get("targets") or [d["target"]]) if t}

    def _grupos_repetidos(self) -> list[list[str]]:
        """Las etapas de cada parcial que comparten número o nombre, agrupadas en el orden del modelo."""
        grupos: dict[tuple[str, str], list[str]] = {}
        for s in self.ed.model["steps"]:
            grupos.setdefault((s["partialRef"], label_key(s["label"])), []).append(s["id"])
        return [g for g in grupos.values() if len(g) > 1]

    def parpadear(self, ids: Any, centrar: bool = True) -> None:
        """Un error que se refiere a estos elementos (etapas, transiciones, barras, acciones, enlaces): parpadean en naranja
        y el primero se lleva a la vista si queda fuera."""
        ids = [i for i in dict.fromkeys(ids) if i]
        if not ids:
            return
        self.parpadeo.iniciar(ids)
        c = self.centro(ids[0]) if centrar else None
        if c is not None and hasattr(self.diagrama, "centrar_si_fuera"):
            self.diagrama.centrar_si_fuera(c)

    def rechazar(self, texto: str, *ids: str | None) -> None:
        """Un rechazo de una operación: el mensaje (en rojo) y el parpadeo de los elementos a los que se refiere."""
        self.mensaje = texto
        self.parpadear([i for i in ids if i])

    def _decir(self, motivo: str | None) -> None:
        """El mensaje tras una operación atómica: su motivo si falló; si no, el aviso de que quedó encima de algo (si es el
        caso) o nada."""
        self.mensaje = motivo or ""
        if not motivo and self._encima:
            self.informar(MSG_ENCIMA)

    def avisos_borrado(self, plan: dict[str, list[str]]) -> list[str]:
        """Lo que borrar deja cambiado en la jerarquía (`affectedHierarchy` del plan), con nombres: un recinto que pierde su
        enlace de activación en las etapas que se van y una orden de forzado que pierde etapas de su conjunto explícito
        («la orden G{B,C} de H pierde la etapa B»); si no le queda ninguna, que pasa a ser una orden explícita sin etapas, que
        fuerza el parcial a vacío. El borrado sigue siendo el de `delete` (se queda el conjunto reducido)."""
        m, nom, doomed = self.ed.model, self._nom, set(plan["elements"])
        afectados, out = set(plan["affectedHierarchy"]), []
        for x in m["hierarchy"]["enclosures"]:
            if x["id"] in afectados:
                perdidas = [s for s in x["activationRefs"] if s in doomed]
                out.append(f"el recinto {nom(x['partialRef'])} pierde su enlace de activación en "
                           f"{', '.join(nom(s) for s in perdidas)}")
        for f in m["forces"]:
            if f["id"] in afectados:
                perdidas = [s for s in f.get("targetSteps", []) if s in doomed]
                texto = (f"la orden {nom(f['targetPartialRef'])}{force_situation(f, self.nombres)} de {nom(f['sourceStepRef'])} "
                         f"pierde {'la etapa' if len(perdidas) == 1 else 'las etapas'} {', '.join(nom(s) for s in perdidas)}")
                if f["targetKind"] == "explicit" and len(perdidas) == len(set(f.get("targetSteps", []))):
                    texto += " y pasa a ser una orden explícita sin etapas: fuerza el parcial a vacío"
                out.append(texto)
        return out

    def resumen(self, diags: list[dict[str, Any]]) -> list[str]:
        """Lo que impide simular, en pocas líneas: las receptividades vacías o con errores de sintaxis, juntas."""
        malas = [d["target"] for d in diags if d["blocks"] and d["code"] == "D-EXP-PENDIENTE" and d["target"]]
        out = []
        if malas:
            nombres = [self.nombre(i) for i in dict.fromkeys(malas)]
            out.append("Receptividades vacías o con errores de sintaxis: " + ", ".join(nombres[:-1])
                       + (" y " if len(nombres) > 1 else "") + nombres[-1] + ".")
        out += [self.sust(d["message"])[:1].upper() + self.sust(d["message"])[1:]
                for d in diags if d["blocks"] and d["code"] != "D-EXP-PENDIENTE"]
        return out
