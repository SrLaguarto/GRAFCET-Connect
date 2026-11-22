"""Conversión entre fórmulas, texto del panel y condiciones del modelo."""
from __future__ import annotations

from typing import Any
from grafcet.diagnostics import Diagnostic
from grafcet.notation import a_nucleo, a_usuario, etapas_ambiguas
from grafcet.view import norm
from ..bloques import sin_comillas


class _Formulas:
    def _texto_valido(self, texto: str, parcial: str | None = None) -> bool:
        """Si una condición o un evento escritos se interpretan (no están vacíos, ni a medias, ni usan variables que no
        existen), con los nombres del parcial dado (por defecto, el raíz)."""
        texto = texto.strip()
        return bool(texto) and self.ed.check_expression(self._n(texto), parcial or self.raiz) is None

    def _segmentos(self, texto: str, nombres: dict[str, str], top: bool = False) -> list[dict[str, Any]] | None:
        """Una condición, un valor o un evento escritos por el usuario, en la notación de la norma; el texto tal cual si no
        se interpreta; None si está vacío."""
        texto = texto.strip()
        if not texto:
            return None
        try:
            meaning, diag = self.ed._make_expr(self.ed.model, self._n(texto), None)
        except Exception:  # noqa: BLE001 - un texto a medias no debe romper el dibujo
            return [{"t": sin_comillas(texto)}]
        return [{"t": sin_comillas(texto)}] if diag is not None else norm(meaning["meaning"], top, nombres)

    def _texto(self, eid: str | None) -> str:
        return a_usuario(next(e["text"] for e in self.ed.model["expressions"] if e["id"] == eid)) if eid else ""

    def _parcial(self, ident: str) -> str:
        """El parcial al que pertenece una transición, o el de la etapa de una acción (del modelo o borrador); de lo demás, el
        raíz."""
        etapa = next((b.get("etapa") for b in self.ed.draft_actions() if b["id"] == ident), None)
        etapa = etapa or next((a["stepRef"] for a in self.ed.model["actions"] if a["id"] == ident), None)
        return self.parcial_de(etapa or ident)

    def comprobar(self, tid: str, texto: str) -> Any:
        """Diagnóstico de un texto de receptividad, o de la condición o el evento de una acción (None si se interpreta),
        sin cambiar el modelo."""
        return self.ed.check_expression(self._n(texto), self._parcial(tid))

    def condicion(self, tid: str, texto: str) -> Any:
        diag = self.ed.set_condition(tid, self._n(texto))
        self.cambia()
        return diag

    def significado(self, tid: str, texto: str) -> dict[str, Any]:
        """El significado (árbol de la expresión) de un texto de receptividad (o de condición o evento de una acción) que
        se interpreta, para dibujarlo."""
        return self.ed._make_expr(self.ed.model, self._n(texto), self._parcial(tid))[0]["meaning"]

    def vista_formula(self, texto: str, ident: str | None = None, booleana: bool = True) -> list[dict[str, Any]] | None:
        """Los segmentos con que se dibuja una fórmula (la receptividad de la transición `ident`, o la condición, el evento o el
        valor —con `booleana=False`— de la acción `ident`): la notación del dibujo (↑, ↓, sobrerrayado, · y +). None si está
        vacía o no se interpreta (entonces se ve tal cual la escribió el usuario)."""
        t = texto.strip()
        if not t:
            return None
        try:
            meaning, diag = self.ed._make_expr(self.ed.model, self._n(t, booleana), self._parcial(ident) if ident else None)
        except Exception:  # noqa: BLE001 - un texto a medias no debe romper el panel
            return None
        return None if diag is not None else norm(meaning["meaning"], booleana, self.nombres)

    def sin_declarar(self, tid: str, texto: str) -> list[str]:
        """Variables que usa la receptividad (o la condición o el evento de una acción) y todavía no existen."""
        return self.ed.undeclared_variables(self._n(texto), self._parcial(tid))

    def poner_condicion(self, tid: str, texto: str, crear: bool = False) -> Any:
        """Fija la receptividad; con crear, declara antes como entradas booleanas las variables que no existan
        (el panel de variables llega en el paso 4). Todo es una sola operación de deshacer."""
        if crear:
            for nombre in self.sin_declarar(tid, texto):
                motivo = self.motivo_nombre(nombre)
                if motivo:  # no se puede escribir tal cual en una fórmula: no se crea
                    self.rechazar(motivo, tid)
                    self.cambiado.emit()
                    return Diagnostic("D-FORMATO", motivo)
        with self.ed.group("receptividad"):
            if crear:
                for nombre in self.sin_declarar(tid, texto):
                    self.ed.add_variable(nombre, "input", {"kind": "bool"})
            return self.condicion(tid, texto)

    def texto_condicion(self, tid: str) -> str:
        """El texto guardado de la receptividad (la sintaxis del núcleo)."""
        t = next(t for t in self.ed.model["transitions"] if t["id"] == tid)
        return next(e["text"] for e in self.ed.model["expressions"] if e["id"] == t["conditionRef"])

    def texto_usuario(self, tid: str) -> str:
        """El mismo texto en la notación del usuario: ↑a, ↓a, X1."""
        return a_usuario(self.texto_condicion(tid))

    def _n(self, texto: str, booleana: bool = True) -> str:
        """Del texto escrito por el usuario (↑a, X1, 1/0, espacios sueltos) al del núcleo, con los espacios normalizados.
        `booleana=False` para un valor numérico (`n := 1`): el 1 y el 0 no pasan a true y false."""
        m = self.ed.model
        return a_nucleo(texto, (s["label"] for s in m["steps"]), (v["name"] for v in m["variables"]), booleana)

    def ambiguas(self, *textos: str) -> list[str]:
        """Los `X…` de los textos que pueden ser dos etapas (E1 y 1 a la vez)."""
        m = self.ed.model
        etapas, variables = [s["label"] for s in m["steps"]], [v["name"] for v in m["variables"]]
        return list(dict.fromkeys(x for t in textos for x in etapas_ambiguas(t, etapas, variables)))

    def aviso_ambiguas(self, *textos: str) -> str:
        """Aviso para el panel o el diálogo si algún `X…` puede ser dos etapas; vacío si no."""
        return " ".join(f"{x} puede ser la etapa E{x[1:]} o la etapa {x[1:]}: se usa E{x[1:]}; para la otra escriba "
                        f"active(`{x[1:]}`)." for x in self.ambiguas(*textos))
