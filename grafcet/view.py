"""Vista de un modelo en simulación: lo que dibujan el simulador de escritorio, el banco y el comparador.

Una `Vista` es un modelo (documento 09) con su sesión bajo unas lecturas dadas. Ofrece la estructura que se dibuja
(etapas, transiciones con su receptividad en la notación de la norma, acciones, jerarquía) y el estado observado del
motor; toda la semántica la decide grafcet/engine.py, sin aproximaciones. Si el modelo no compila, se dibuja lo que
se pueda y se listan los errores.

Notación: la de las tablas 1–11 de la norma, tomada por inspección visual de las imágenes aportadas por el usuario
(fuente IMG del documento 02): receptividad con ↑ ↓ · + y sobrerrayado, comparaciones entre corchetes y retardos
t1/condición/t2 sin los tiempos de 0 s (respuesta 4.4 revisada). No se copia ningún activo; el contraste con una
copia íntegra sigue pendiente (U-01).

Para un modelo abierto sin presentación, o con elementos sin posición, `auto_layout` los coloca por niveles.
"""
from __future__ import annotations

import re
from collections import deque
from fractions import Fraction
from typing import Any, Callable

from .builder import M, scenario
from .diagnostics import Diagnostic, DiagnosticError
from .editor import _coord, new_presentation
from .engine import Session, _Env
from . import expressions as ex
from .model import validate_model
from .timeutil import format_duration
from .values import format_value, parse_value

Layout = dict[str, tuple[float, float]]
# Construcción de una vista: el modelo (M o documento 09) y las posiciones que se conozcan (o None)
Build = Callable[[], tuple["M | dict[str, Any]", "Layout | None"]]

# --- Notación de la norma para mostrar expresiones -------------------------------------
# Segmento: {"t": texto, "o": sobrerrayado, "s": subíndice}

_CMP = {"eq": "=", "ne": "≠", "lt": "<", "le": "≤", "gt": ">", "ge": "≥"}
_ARITH = {"add": " + ", "sub": " − ", "mul": "·", "div": "/"}
_PREC = {"or": 1, "and": 2, **{c: 4 for c in _CMP}, "add": 5, "sub": 5, "mul": 6, "div": 6}


def _seg(t: str, **f: bool) -> dict[str, Any]:
    return {"t": t, **{k: True for k, v in f.items() if v}}


def _paren(segs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_seg("(")] + segs + [_seg(")")]


def _dur(us: int) -> str:
    return format_duration(us, "s", "es-ES").replace(" ", "")


_INTERNO = re.compile(r"[a-z]-[0-9a-f]{32}")  # el ID que crea grafcet.ids.IdGenerator: no es para mostrar


def force_situation(f: dict[str, Any], names: dict[str, str]) -> str:
    """La situación que impone una orden de forzado, como se dibuja: «{B,C}», «{*}», «{ }» o «{INIT}»."""
    return {"explicit": "{" + ",".join(names.get(i, i) for i in f.get("targetSteps", [])) + "}", "current": "{*}",
            "empty": "{ }", "initial": "{INIT}"}[f["targetKind"]]


def display_names(doc: dict[str, Any]) -> dict[str, str]:
    """Nombre visible de cada elemento: variable → name, etapa → label, parcial y macroetapa → label, transición →
    label si lo tiene o, si no, t1, t2… cuando su ID es interno. Un nombre repetido en otro parcial lleva el del parcial delante, como en el texto de las
    expresiones (grafcet/editor.py). Una expansión es «expansión de <macroetapa>», un recinto «recinto <parcial>» y una
    orden de forzado «orden G{…} de <etapa>», las tres solo si su ID es interno (el de un ejemplo o el de un modelo
    escrito a mano sigue siendo su nombre). El dibujo y las tablas nunca muestran los ID internos que crea el editor."""
    plabel = {p["id"]: p["label"] for p in doc["partials"]}
    out: dict[str, str] = {}
    for coll, key, scope in (("variables", "name", "scopeRef"), ("steps", "label", "partialRef")):
        for x in doc[coll]:
            same = [o for o in doc[coll] if o[key] == x[key]]
            out[x["id"]] = x[key] if len(same) == 1 else f"{plabel.get(x[scope], x[scope])}.{x[key]}"
    out.update({p["id"]: p["label"] for p in doc["partials"]})
    out.update({x["id"]: x.get("label", x["id"]) for x in doc["hierarchy"]["macros"]})
    out.update({x["id"]: f"expansión de {out.get(x['ownerMacroRef'], x['ownerMacroRef'])}"
                for x in doc["hierarchy"]["expansions"] if _INTERNO.fullmatch(x["id"])})
    out.update({x["id"]: f"recinto {plabel.get(x['partialRef'], x['partialRef'])}"
                for x in doc["hierarchy"]["enclosures"] if _INTERNO.fullmatch(x["id"])})
    for f in doc["forces"]:  # una forma desconocida no impide nombrar las demás (el modelo la diagnostica)
        if _INTERNO.fullmatch(f["id"]):
            try:
                sit = force_situation(f, out)
            except KeyError:
                sit = "{?}"
            out[f["id"]] = f"orden {plabel.get(f['targetPartialRef'], f['targetPartialRef'])}{sit} de "                            f"{out.get(f['sourceStepRef'], f['sourceStepRef'])}"
    taken = {t["label"] for t in doc["transitions"] if t.get("label")}
    for n, t in enumerate(doc["transitions"], 1):  # sin etiqueta, una transición del editor se numera: t1, t2…
        name = t.get("label")
        if not name and _INTERNO.fullmatch(t["id"]):
            k = n
            while f"t{k}" in taken:
                k += 1
            name = f"t{k}"
            taken.add(name)
        out[t["id"]] = name or t["id"]
    for a in doc["actions"]:  # una acción del editor se nombra por su etapa (columna «Contribuyen»)
        if _INTERNO.fullmatch(a["id"]) and a["stepRef"] in out:
            out[a["id"]] = out[a["stepRef"]]
    # Una referencia eliminada sigue siendo inválida, pero conserva el nombre escrito en sus bindings.
    # No se vuelve a enlazar por nombre: el diagnóstico debe seguir señalando la referencia ausente.
    for expression in doc.get("expressions", []):
        for alias, ident in expression.get("bindings", {}).items():
            if isinstance(alias, str) and isinstance(ident, str):
                out.setdefault(ident, alias)
    return out


def substitute(text: str, names: dict[str, str]) -> str:
    """Sustituye en un texto (mensajes del motor) los ID internos por sus nombres visibles."""
    pairs = {i: n for i, n in names.items() if i != n}
    if not pairs:
        return text
    rx = re.compile(r"(?<!\w)(" + "|".join(re.escape(i) for i in sorted(pairs, key=len, reverse=True)) + r")(?!\w)")
    return rx.sub(lambda mo: pairs[mo.group(1)], text)


def norm(m: dict[str, Any], top: bool = True, names: dict[str, str] | None = None,
         key: str | None = None) -> list[dict[str, Any]]:
    """Notación estática; con `key`, añade referencias de lectura para el color de cada subexpresión."""
    names = names or {}
    op = m["operator"]
    def hijo(i: int) -> list[dict[str, Any]]:
        return norm(m["operands"][i], False, names, None if key is None else f"{key}.{i}")
    def lado(i: int) -> list[dict[str, Any]]:
        x = m["operands"][i]
        segs = hijo(i)
        return _paren(segs) if _PREC.get(x["operator"], 9) < _PREC[op] else segs
    if op == "lit":
        lit = m["literal"]
        if lit["type"] == "bool":
            out = [_seg("= 1" if top and lit["value"] else "1" if lit["value"] else "0")]
        elif lit["type"] == "duration":
            out = [_seg(_dur(int(lit["value"])))]
        else:
            out = [_seg(lit["value"].replace(".", ","))]
    elif op == "ref":
        out = [_seg(names.get(m["reference"], m["reference"]))]
    elif op in ("active", "activePartial", "activeMacro"):
        nombre = names.get(m["reference"], m["reference"])
        num = re.fullmatch(r"E(\d+)", nombre) if op == "active" else None
        out = [_seg("X"), _seg(num.group(1) if num else nombre, s=True)]
    elif op in ("rise", "fall"):
        cuerpo = hijo(0)
        if m["operands"][0]["operator"] not in ("ref", "active", "lit"):
            cuerpo = _paren(cuerpo)
        out = [_seg("↑" if op == "rise" else "↓")] + cuerpo
    elif op == "not":
        # La barra representa toda la negación: su color usa ese valor, no el del operando.
        out = [dict(s, o=True, eval=[key]) if key is not None else dict(s, o=True) for s in hijo(0)]
    elif op == "delay":
        d1, base, d2 = m["operands"]
        out = hijo(1)
        if int(d1["literal"]["value"]):
            out = hijo(0) + [_seg("/")] + out
        if int(d2["literal"]["value"]):
            out += [_seg("/")] + hijo(2)
    elif op == "neg":
        out = [_seg("−")] + hijo(0)
    elif op in _CMP:
        out = [_seg("[")] + lado(0) + [_seg(f" {_CMP[op]} ")] + lado(1) + [_seg("]")]
    else:
        out = lado(0) + [_seg({"and": "·", "or": " + ", **_ARITH}[op])] + lado(1)
    if key is not None and (op in (*_CMP, "delay", "ref", "active", "activePartial", "activeMacro", "rise", "fall")
                            or op == "lit" and m["literal"]["type"] == "bool"):
        out = [dict(s, eval=[*s.get("eval", []), key]) for s in out]
    return out


def _tiene_retardo(m: dict[str, Any]) -> bool:
    return m["operator"] == "delay" or any(_tiene_retardo(o) for o in m.get("operands", []))


def _con_retardo(e: dict[str, Any] | None) -> dict[str, bool]:
    """{"tmr": True} si la expresión de una condición o un evento lleva un retardo t1/condición/t2; el dibujo reserva
    sitio encima para el tiempo transcurrido del temporizador (no depende del estado: la disposición no cambia al simular)."""
    return {"tmr": True} if e is not None and e["mode"] == "executable" and _tiene_retardo(e["meaning"]) else {}


def t_s(us: str | int) -> str:
    return format_duration(int(us), "s", "es-ES")


def t_trunc(us: str | int) -> str:
    """Tiempo para mostrar: truncado a la baja a 2 decimales (el valor exacto no cambia, solo cómo se escribe)."""
    us = int(us)
    return t_s(us - us % 10_000)


def describe(r: dict[str, Any], texts: dict[str, str], names: dict[str, str] | None = None) -> dict[str, str] | None:
    names = names or {}

    def lst(ids: list[str]) -> str:
        return ", ".join(names.get(i, i) for i in ids)
    k = r["kind"]
    when = t_s(r.get("timeUs", 0))
    if k == "inicio":
        return {"kind": k, "time": when, "text": f"Inicio · S = {{{lst(r['situation'])}}}"}
    if k == "contexto":
        what = ", ".join(f"{names.get(v, v)}={str(x).lower()}" for v, x in r["inputChanges"].items()) or "sin cambio de entradas"
        src = "vencimiento temporal" if r["stimulus"] == "vencimiento" else f"lote {r['origin']}"
        names = sorted({texts.get(e.split(".")[0], e) for e in r["events"]})
        ev = f" · eventos: {', '.join(names)}" if names else ""
        return {"kind": k, "time": when, "text": f"{src}: {what}{ev}"}
    if k == "evolucion":
        asg = "; ".join(f"{names.get(a['target'], a['target'])}:={a['value']}" for a in r["assignments"])
        if r["evolutionIndex"] == 0:
            return {"kind": k, "time": when, "text": f"Arranque: acciones al activar las etapas iniciales · {asg}"}
        perm = f" · permanece {lst(r['permanent'])}" if r["permanent"] else ""
        perm += f" · {lst(r['durationKept'])} reentra sin interrumpir su duración" if r.get("durationKept") else ""
        return {"kind": k, "time": when, "text": f"Evolución {r['evolutionIndex']}: franquea {{{lst(r['cleared'])}}}"
                f" → S = {{{lst(r['situation'])}}}{perm}" + (f" · {asg}" if asg else "")}
    if k == "estable":
        if "reason" in r:
            return None
        virt = f" · inestables: {lst(r['virtualSteps'])}" if r.get("virtualSteps") else ""
        hyp = "".join(f" · hipótesis {h['question']} ({h['reading']}) aplicada a {names.get(h['transition'], h['transition'])}"
                      for h in r.get("hypotheses", []))
        return {"kind": k, "time": when, "text": f"Estable · S = {{{lst(r['situation'])}}}{virt}{hyp}"}
    if k in ("fallo", "limite"):
        d = r["diagnostics"][0]
        q = f" ({d['question']})" if d.get("question") else ""
        return {"kind": "fallo", "time": when, "text": f"{d['code']}{q}: {substitute(d['message'], names)}"}
    return None


class Vista:
    """Un modelo con su sesión bajo unas lecturas dadas: lo que se dibuja en una ventana o en un panel."""

    def __init__(self, key: str, title: str, help_text: str, build: Build,
                 options: dict[str, str], init: dict[str, Any] | None = None,
                 batches: list[tuple[int, int, dict[str, Any]]] = (), budget: int = 10_000,
                 hidden: frozenset[str] | set[str] = frozenset(), bars: list[dict[str, Any]] | None = None,
                 presentation: dict[str, Any] | None = None, link_styles: dict[str, Any] | None = None,
                 draft_actions: list[dict[str, Any]] | None = None,
                 action_layouts: dict[str, str] | None = None, comments: dict[str, str] | None = None) -> None:
        m, layout = build()
        # comentarios de etapas y transiciones (presentación: nunca entran en el significado ni en la simulación)
        self.comments = {n["elementRef"]: n["text"] for n in (presentation or {}).get("notes", [])
                         if isinstance(n, dict) and n.get("kind") == "comment" and isinstance(n.get("text"), str)
                         and n["text"] and isinstance(n.get("elementRef"), str)} if comments is None else dict(comments)
        self.draft_actions = draft_actions or []  # acciones sueltas o sin completar, ya con su texto (editor; no se simulan)
        self.hidden = set(hidden)  # transiciones cuya etiqueta no se dibuja (presentación)
        self.bars = bars or []     # barras de simultaneidad y de alternativa (presentación)
        if presentation is not None:
            self.hidden = {l["elementRef"] for l in presentation.get("elementLayouts", []) if l.get("labelVisible") is False}
            self.bars = presentation.get("barras", [])
        styles = link_styles if link_styles is not None else (presentation or {}).get("linkStyles", {})
        crudos = action_layouts if action_layouts is not None else (presentation or {}).get("actionLayouts", {})
        # colocación de las acciones de cada etapa (presentación); lo que no se conoce vale «fila»
        self.action_layouts = {k: v for k, v in (crudos if isinstance(crudos, dict) else {}).items()
                               if v in ("fila", "fila-separada", "matriz-2", "columna")}
        doc = m.doc if isinstance(m, M) else m
        self.key, self.options, self.doc = key, options, doc
        self.texts: dict[str, str] = {}
        self.where: dict[str, str] = {}
        try:
            self.names = display_names(doc)
        except (KeyError, TypeError, AttributeError):
            self.names = {}  # documento dañado: se muestran los ID tal cual
        res = validate_model(doc, options)
        from .routing import validar_barras
        res.diagnostics.extend(validar_barras(doc, self.bars))
        self.compile_diags = [d for d in res.diagnostics if d.blocks_start]
        self.s: Session | None = None
        self.start_diags: list = []
        if res.can_simulate:
            cm = res.model
            # Entradas: su valor inicial del modelo, salvo lo que fije el guion
            start = {v["id"]: v["initialValue"] for v in doc["variables"] if v["role"] == "input"}
            start.update(init or {})
            self.s = Session(cm, scenario(cm, start, batches, max_contexts=1_000_000), budget=budget, options=options)
            self.start_diags = self.s.start()
        try:
            self.model = self._structure(key, title, help_text, doc, res.can_simulate, layout)
            from .annotations import visual_notes
            self.model["annotations"] = visual_notes(presentation or {})
            self.model["linkStyles"] = styles
            self.model["draftActions"] = self.draft_actions
            self.model["actionLayouts"] = self.action_layouts  # colocación de las acciones de cada etapa o grupo suelto
            from .routing import enlaces
            self.model["links"] = enlaces(self.model)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            # Documento demasiado dañado para dibujarlo: no se dibuja nada y se listan los errores
            self.texts = {}
            self.model = {"key": key, "names": self.names, "title": title, "help": help_text, "compilable": False, "steps": [],
                          "macros": [], "partials": [], "transitions": [], "inputs": [], "numericInputs": {}}

    def _structure(self, key: str, title: str, help_text: str, doc: dict[str, Any], compilable: bool,
                   layout: Layout | None) -> dict[str, Any]:
        layout = {**auto_layout(doc), **(layout or {})}
        exprs = {e["id"]: e for e in doc["expressions"]}
        self.texts = {eid: e["text"] for eid, e in exprs.items()}
        names = self.names
        self.where = {t["conditionRef"]: f"transición {names[t['id']]}" for t in doc["transitions"]}

        def disp(eid: str | None, top: bool = False, color: bool = True) -> list[dict[str, Any]] | None:
            if eid is None:
                return None
            e = exprs[eid]
            return norm(e["meaning"], top, names, eid if color else None) if e["mode"] == "executable" else [_seg(e["text"])]
        acts: dict[str, list[dict[str, Any]]] = {}
        for a in doc["actions"]:
            if a["mode"] == "continuous":
                cond = exprs[a["conditionRef"]]
                plain = cond["mode"] == "executable" and cond["meaning"] == {"operator": "lit", "literal": {"type": "bool", "value": True}}
                acts.setdefault(a["stepRef"], []).append({"kind": "continuous", "id": a["id"], "target": a["targetRef"],
                                                          "text": [_seg(names.get(a["targetRef"], a["targetRef"]))],
                                                          "cond": self._cond_limitada(a, plain, disp),
                                                          "condRef": a["conditionRef"], **_con_retardo(cond)})
                self.where.setdefault(a["conditionRef"], f"acción {names.get(a['targetRef'], a['targetRef'])} "
                                                         f"({names.get(a['stepRef'], a['stepRef'])})")
            else:
                trig = a["trigger"]
                acts.setdefault(a["stepRef"], []).append({
                    "kind": "stored", "id": a["id"], "target": a["targetRef"], "trigger": trig["kind"],
                    "text": [_seg(f"{names.get(a['targetRef'], a['targetRef'])} := ")] + disp(a["valueRef"], color=False),
                    "event": disp(trig.get("expressionRef")), "condRef": trig.get("expressionRef"),
                    **_con_retardo(exprs.get(trig.get("expressionRef")))})
                if trig.get("expressionRef"):
                    self.where.setdefault(trig["expressionRef"], f"evento de {names.get(a['targetRef'], a['targetRef'])} "
                                                                 f"({names.get(a['stepRef'], a['stepRef'])})")
        orden = {aid: i for st in doc["steps"] for i, aid in enumerate(st["actionRefs"])}
        for lista in acts.values():  # de izquierda a derecha, en el orden de la etapa
            lista.sort(key=lambda a: orden.get(a["id"], 0))
        # Jerarquía, con la notación de las figuras de la norma (tablas 8–11; imágenes P40-02, P42-02..05,
        # P43-01, P43-02, P44-01, P45-01, P47-01..03): orden de forzado «G12{8,9,11}» en rectángulo doble, «*» de
        # enlace de activación, recinto con su encapsulante y su nombre, expansión unida a su macroetapa
        hier = doc["hierarchy"]
        marked = {sid for e in hier["enclosures"] for sid in e["activationRefs"]}
        labels = {p["id"]: p["label"] for p in doc["partials"]}
        kinds: dict[str, dict[str, Any]] = {x["partialRef"]: {"kind": "expansion", "macro": x["ownerMacroRef"]}
                                            for x in hier["expansions"]}
        kinds.update({e["partialRef"]: {"kind": "enclosure", "ownerStep": e["ownerStepRef"]} for e in hier["enclosures"]})
        for f in doc["forces"]:
            sit = force_situation(f, names)
            acts.setdefault(f["sourceStepRef"], []).append({"kind": "force", "id": f["id"], "target": f["targetPartialRef"],
                                                           "text": [_seg(f"{labels[f['targetPartialRef']]}{sit}")]})
        # Barras: solo las que tienen elementos existentes; las parejas que enlazan se dibujan por la barra, no directas
        vivos = ({s["id"] for s in doc["steps"]} | {t["id"] for t in doc["transitions"]}
                 | {x["id"] for x in hier["macros"]})  # una macroetapa se une a una barra como una etapa
        barras, cubiertos = [], set()
        for n, b in enumerate(self.bars, 1):
            arriba = [i for i in b.get("arriba", []) if i in vivos]
            abajo = [i for i in b.get("abajo", []) if i in vivos]
            barras.append({"id": b["id"], "kind": b["kind"], "x": float(Fraction(b["x"])), "y": float(Fraction(b["y"])),
                           "ancho": float(Fraction(b["ancho"])), "arriba": arriba, "abajo": abajo,
                           "label": f"{'Simultaneidad' if b['kind'] == 'Y' else 'Alternativa'} {n}"})
            tr = {t["id"] for t in doc["transitions"]}
            for a_ in arriba:
                for z in abajo:
                    if a_ in tr and z not in tr:
                        cubiertos.add((a_, z, "post"))
                    elif z in tr and a_ not in tr:
                        cubiertos.add((z, a_, "pre"))
        return {
            "key": key, "title": title, "help": help_text, "compilable": compilable, "names": names, "bars": barras,
            "steps": [{"id": s["id"], "label": s["label"], "initial": s["initial"],
                       "x": layout[s["id"]][0], "y": layout[s["id"]][1],
                       "partial": None if s["partialRef"] == "g" else s["partialRef"], "kind": s["kind"],
                       "activation": s["id"] in marked, "actions": acts.get(s["id"], []),
                       "actionLayout": self.action_layouts.get(s["id"], "fila"),
                       **({"comment": self.comments[s["id"]]} if s["id"] in self.comments else {})} for s in doc["steps"]],
            "macros": [{"id": x["id"], "x": layout[x["id"]][0], "y": layout[x["id"]][1], "expansion": e["partialRef"],
                        "entry": e["entryRef"], "exit": e["exitRef"],
                        "partial": None if x["partialRef"] == "g" else x["partialRef"]}
                       for x in hier["macros"] for e in hier["expansions"] if e["id"] == x["expansionRef"]],
            "partials": [{"id": p["id"], "label": p["label"], "owner": p.get("ownerRef"),
                          **kinds.get(p["id"], {"kind": "partial"})}
                         for p in doc["partials"] if p["id"] != "g" and p["stepRefs"]],
            "transitions": [{"id": t["id"], "label": names[t["id"]], "showLabel": t["id"] not in self.hidden,
                             "preDib": [s for s in t["preRefs"] if (t["id"], s, "pre") not in cubiertos],
                             "postDib": [s for s in t["postRefs"] if (t["id"], s, "post") not in cubiertos],
                             "simulPre": len([s for s in t["preRefs"] if (t["id"], s, "pre") not in cubiertos]) > 1,
                             "simulPost": len([s for s in t["postRefs"] if (t["id"], s, "post") not in cubiertos]) > 1,
                             "pre": t["preRefs"], "post": t["postRefs"],
                             "partial": t["partialRef"], "cond": disp(t["conditionRef"], top=True),
                             "conditionRef": t["conditionRef"], **_con_retardo(exprs.get(t["conditionRef"])),
                             "x": layout[t["id"]][0], "y": layout[t["id"]][1],
                             **({"comment": self.comments[t["id"]]} if t["id"] in self.comments else {})}
                            for t in doc["transitions"]],
            "drafts": [{"id": d["id"], "from": d["fromRef"], "to": d["toRef"]} for d in doc.get("draftLinks", [])],
            "inputs": sorted((v["id"] for v in doc["variables"] if v["role"] == "input"), key=lambda i: (names[i], i)),
            "numericInputs": {v["id"]: v["type"]["kind"] for v in doc["variables"]
                              if v["role"] == "input" and v["type"]["kind"] != "bool"},
        }

    def _cond_limitada(self, a: dict[str, Any], plain: bool, disp: Callable[..., Any]) -> Any:
        """Condición que se dibuja en una acción continua. Una limitada en el tiempo se dibuja como en la norma: su límite
        es una condición más, NOT d/X (X, la etapa de la acción); con condición c, «c · NOT d/X». Solo dibujo: el modelo
        guarda `limitUs` y el motor no cambia."""
        base = None if plain else disp(a["conditionRef"])
        if "limitUs" not in a:
            return base
        lit = lambda v: {"operator": "lit", "literal": {"type": "duration", "value": str(v)}}  # noqa: E731
        m = {"operator": "not", "operands": [{"operator": "delay", "operands": [
            lit(int(a["limitUs"])), {"operator": "active", "reference": a["stepRef"]}, lit(0)]}]}
        c = next((e for e in self.doc["expressions"] if e["id"] == a["conditionRef"]), None)
        limite = norm(m, False, self.names, f"@limit:{a['id']}")
        if base is not None and c is not None and c["mode"] == "executable" and c["meaning"]["operator"] == "or":
            base = _paren(base)
        return limite if base is None else base + [_seg("·")] + limite

    def _verdades(self, eventos: dict[str, bool] | None = None) -> dict[str, bool]:
        """Lectura pura de los nodos con el mismo entorno efectivo que Session.observe()."""
        if self.s is None or self.s.z is None:
            return {}
        env = _Env(self.s.cm, self.s.z, eventos, self.s.options)
        valores = {}
        for expresion in self.s.cm.exprs.values():
            pendientes = [expresion.node]
            while pendientes:
                nodo = pendientes.pop()
                pendientes.extend(nodo.kids)
                if nodo.op not in (*_CMP, "delay", "ref", "active", "activePartial", "activeMacro", "lit", "rise", "fall", "not", "and", "or"):
                    continue
                try:
                    valor = ex.evaluate(nodo, env)
                except (DiagnosticError, KeyError, ArithmeticError):
                    continue  # un cálculo no definido no se presenta como verdadero
                if type(valor) is bool:
                    valores[nodo.key] = valor
        # El límite de una acción se presenta como NOT d/X, aunque no sea un nodo compilado.
        w = self.s.z
        for a in self.doc["actions"]:
            if "limitUs" not in a:
                continue
            key = f"@limit:{a['id']}.0"
            sid = a["stepRef"]
            activa = env.active(sid)
            now = w.frozen.get(self.s.cm.steps[sid].partial, w.time)
            valores[key] = activa and now - w.since.get(sid, now) >= int(a["limitUs"])
            valores[key + ".1"] = activa
            valores[f"@limit:{a['id']}"] = not valores[key]
        return valores

    def state(self) -> dict[str, Any]:
        s = self.s
        out: dict[str, Any] = {"truth": {}}
        if s is None:  # no compila: se dibuja la estructura y se listan los errores
            out.update({"status": "no-compilable", "diagnostics": [self._diag(d) for d in self.compile_diags],
                        "time": "—", "situation": [], "transitions": {}, "outputs": {}, "values": {}, "temporal": {},
                        "lastCleared": [], "trace": [], "nextEvent": None, "blocked": None})
            return out
        out.update({"status": s.status, "diagnostics": [self._diag(d) for d in (self.start_diags or s.diagnostics)[-2:]]})
        if s.z is None:
            return out
        obs = s.observe()
        evo = [r for r in s.trace.records if r["kind"] == "evolucion"]
        closed = next((r["kind"] for r in reversed(s.trace.records) if r["kind"] in ("estable", "fallo", "limite")), None)
        last_stable = next((r for r in reversed(s.trace.records) if r["kind"] == "estable" and "reason" not in r), None)
        contexto = next((r for r in reversed(s.trace.records) if r["kind"] == "contexto"), None)
        mismo_instante = contexto is not None and int(contexto["timeUs"]) == int(obs["timeUs"])
        recientes = []
        if mismo_instante:
            for r in reversed(s.trace.records):
                if r["kind"] == "contexto":
                    break
                recientes.extend(a for asignacion in r.get("assignments", []) for a in asignacion.get("authors", []))
        acciones = {a for o in obs["outputs"].values() for a in o.get("contributors", [])}
        if closed == "estable":
            acciones.update(recientes)
        acciones.update(f["order"] for f in obs.get("forces", []))
        out.update({
            "activeActions": sorted(acciones),
            "truth": self._verdades({k: True for k in contexto.get("events", [])} if mismo_instante and closed == "estable" else None),
            "time": t_s(obs["timeUs"]), "timeUs": obs["timeUs"], "situation": obs["situation"],
            "macros": obs.get("macros", {}), "forces": obs.get("forces", []),
            "virtual": obs.get("recorrido", {}).get("virtualSituation"),
            "unstable": last_stable.get("virtualSteps", []) if last_stable and closed == "estable" else [],
            "transitions": obs["transitions"], "outputs": obs["outputs"],
            "values": {k: v for k, v in obs["values"].items()},
            "variableReadouts": {k: ("1" if v else "0") if isinstance(v, bool) else str(v).replace(".", ",")
                                 for k, v in obs["values"].items()},
            "temporal": self._ocurrencias({k: self._temporizador(k, v, obs["timeUs"])
                                           for k, v in obs["temporal"].items()}),
            "lastCleared": evo[-1]["cleared"] if evo and closed == "estable" else [],  # un contexto fallido no franquea
            "trace": [x for x in (describe(r, self.texts, self.names) for r in s.trace.records[-60:]) if x],
            "nextEvent": self._next(), "nextEventUs": self._next_us(),
            "blocked": self._blocked(closed),
        })
        return out

    def _diag(self, d: Any) -> dict[str, Any]:
        """Diagnóstico para mostrar: el elemento sigue siendo su ID (el dibujo lo busca), el texto (también el de la
        evidencia) usa nombres."""
        x = d.to_dict()
        out = {**x, **{k: substitute(x[k], self.names) for k in ("message", "correction") if isinstance(x.get(k), str)}}
        if isinstance(x.get("evidence"), dict):
            out["evidence"] = {k: substitute(v, self.names) if isinstance(v, str) else v for k, v in x["evidence"].items()}
        return out

    def _blocked(self, closed: str | None) -> dict[str, Any] | None:
        """Contexto rechazado: hasta dónde el recorrido está determinado y qué elemento queda en cuestión
        (documento 04, fila «Incidencia»: diagnóstico con valores candidatos, nunca estable por omisión)."""
        if self.s.status != "error" or closed != "fallo":
            return None
        rec = next(r for r in reversed(self.s.trace.records) if r["kind"] == "fallo")
        if "situationCandidate" not in rec:
            return None
        d = rec["diagnostics"][0]
        return {"reached": rec["situationCandidate"], "proposed": rec.get("proposedSet", []),
                "element": d.get("element"), "question": d.get("question"), "lastStable": sorted(self.s.z.situation)}

    def _ocurrencias(self, temporal: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Añade a cada temporizador `nth`: cuál de las apariciones de su `token` (la duración como se escribe en la
        receptividad, «3s») en el texto de su expresión es la suya, para que el dibujo ponga el tiempo transcurrido
        encima de esa duración. Los retardos de una expresión se escriben en el orden de su árbol y cada uno escribe su
        t1 y su t2, salvo los que valen 0 s."""
        por_expr: dict[str, list[str]] = {}
        for k, t in temporal.items():
            por_expr.setdefault(t["expr"], []).append(k)
        for claves in por_expr.values():
            vistos: dict[str, int] = {}  # cuántas veces se ha escrito ya cada duración en esta expresión
            for k in sorted(claves, key=lambda c: [int(n) for n in c.split(".")[1:]]):
                spec, t = self.s.cm.temporals[k], temporal[k]
                escritas = []
                for d in (spec.d1, spec.d2):
                    if d:
                        escritas.append(vistos.get(_dur(d), 0))
                        vistos[_dur(d)] = vistos.get(_dur(d), 0) + 1
                t["nth"] = escritas[-1 if t["off"] else 0] if escritas else 0
        return temporal

    def _temporizador(self, key: str, v: dict[str, Any], now: int) -> dict[str, Any]:
        """Un retardo t1/condición/t2 como temporizador: dónde está, en qué estado, cuánto lleva y su preset (el de
        conexión mientras cuenta o ya venció; el de desconexión mientras se mantiene tras desaparecer la base). `shown` es
        lo que se dibuja encima de la duración: solo el tiempo transcurrido mientras cuenta, «3,00 s ✓» al vencer y nada
        antes de empezar."""
        spec = self.s.cm.temporals[key]
        expr = key.split(".")[0]
        phase = v["phase"]
        off = phase == "off_pending"
        preset = spec.d2 if off else spec.d1
        counting = phase in ("on_pending", "off_pending")
        done = phase == "on"
        lleva = int(now) - int(v["intervalStart"]) if counting else (spec.d1 if done else None)
        estado = "contando" if counting else "vencido" if done else "parado"
        shown = ""
        if counting:
            shown = f"{lleva // 1000000},{(lleva % 1000000) // 10000:02d} s"
        elif done and spec.d1:
            shown = f"{spec.d1 // 1000000},{(spec.d1 % 1000000) // 10000:02d} s ✓"
        return {**v, "label": self.texts.get(expr, key), "expr": expr, "where": self.where.get(expr, expr),
                "deadlineS": None if v["deadline"] == "inactive" else t_s(v["deadline"]),
                "estado": estado, "lleva": "—" if lleva is None else t_trunc(lleva), "preset": t_s(preset),
                "shown": shown, "off": off, "token": _dur(preset), "nth": 0}

    def _next_us(self) -> int | None:
        if self.s.status != "pausada-estable":
            return None
        nxt = self.s.next_stimulus()
        return int(nxt.time) if hasattr(nxt, "time") and nxt.kind == "vencimiento" else None

    def _next(self) -> str | None:
        us = self._next_us()
        return None if us is None else t_s(us)

    def act(self, op: str, body: dict[str, Any]) -> None:
        if self.s is None:
            raise RuntimeError("el programa no puede compilarse; corrija los errores indicados")
        if op == "entrada":
            var = body["var"]
            self.s.manual_input({var: not self.s.z.values[var]})
            self.s.step_evolution() if body.get("paso") else self.s.step_external()
        elif op == "valor":  # entrada numérica escrita por el usuario (admite coma decimal)
            var = body["var"]
            self.s.manual_input({var: input_value(self.s.cm.variables[var].type, body["texto"])})
            self.s.step_evolution() if body.get("paso") else self.s.step_external()
        elif op == "fijar":  # guion del comparador: fija entradas y procesa todo lo que ocurre en ese instante
            changes = {k: v for k, v in body["cambios"].items() if self.s.z.values.get(k) != v}
            if changes:
                self.s.manual_input(changes)
            self.s.advance_to(self.s.z.time)
        elif op == "avanzar":
            self.s.advance_to(self.s.z.time + int(body["us"]))
        elif op == "hasta":
            self.s.advance_to(max(int(body["us"]), self.s.z.time))
        elif op == "evolucion":
            self.s.step_evolution()
        elif op == "estabilizar":
            self.s.run_to_stable()
        else:
            raise ValueError(f"operación desconocida: {op}")


def input_value(t: Any, text: str) -> Any:
    """Valor de una entrada escrito a mano: «3», «-2», «2,5» o «2.5»; con el tipo y la escala de la variable."""
    raw = text.strip().replace(",", ".")
    try:
        f = Fraction(raw)
    except (ValueError, ZeroDivisionError):
        raise DiagnosticError(Diagnostic("D-TIPO", f"«{text}» no es un número")) from None
    if t.kind == "bool":
        raise DiagnosticError(Diagnostic("D-TIPO", "la entrada es booleana: se cambia con su botón"))
    if t.kind in ("int", "duration") and f.denominator != 1:
        raise DiagnosticError(Diagnostic("D-TIPO", f"«{text}» no es un entero"))
    if t.kind == "decimal" and (f * 10**t.scale).denominator != 1:
        raise DiagnosticError(Diagnostic("D-TIPO", f"«{text}» tiene más decimales que la escala ({t.scale})"))
    return parse_value(t, format_value(t, f))  # forma canónica; parse_value comprueba el rango


# --- Posiciones ------------------------------------------------------------------------------

STEP_DY = 120     # entre etapas: la transición queda a 60 (tres pasos de rejilla)
BRANCH_DX = 150   # entre ramas
PARTIAL_GAP = 260  # entre parciales, para que quepan las acciones


def auto_layout(doc: dict[str, Any]) -> Layout:
    """Coloca por niveles las etapas, macroetapas y transiciones de cada parcial: las etapas iniciales arriba y
    cada transición bajo sus etapas anteriores. Es un dibujo de reserva para modelos sin presentación: no
    pretende la disposición que elegiría una persona."""
    hier = doc.get("hierarchy") or {}
    nodes = [(s["id"], s.get("partialRef"), s.get("initial") or s.get("kind") == "entry") for s in doc.get("steps", [])]
    nodes += [(x["id"], x.get("partialRef"), False) for x in hier.get("macros", [])]
    trans = doc.get("transitions", [])
    order = [p["id"] for p in doc.get("partials", [])]
    order = [p for p in order if p == "g"] + [p for p in order if p != "g"]
    out: Layout = {}
    x0 = 60.0
    for pid in order + [None]:
        mine = [n for n in nodes if (n[1] == pid if pid is not None else n[1] not in order)]
        if not mine:
            continue
        ids = [n[0] for n in mine]
        succ: dict[str, list[str]] = {i: [] for i in ids}
        for t in trans:
            for a in t.get("preRefs", []):
                if a in succ:
                    succ[a] += [b for b in t.get("postRefs", []) if b in succ and b not in succ[a]]
        rank: dict[str, int] = {}
        roots = [n[0] for n in mine if n[2]] or ids[:1]
        while len(rank) < len(ids):
            base = max(rank.values(), default=-1) + 1
            queue = deque()
            for r in roots:
                if r not in rank:
                    rank[r] = base
                    queue.append(r)
            while queue:
                a = queue.popleft()
                for b in succ[a]:
                    if b not in rank:
                        rank[b] = rank[a] + 1
                        queue.append(b)
            roots = [i for i in ids if i not in rank][:1]
        rows: dict[int, list[str]] = {}
        for i in ids:
            rows.setdefault(rank[i], []).append(i)
        width = max(len(r) for r in rows.values())
        cx = x0 + (width - 1) * BRANCH_DX / 2
        for k, row in rows.items():
            for j, i in enumerate(row):
                out[i] = (cx + (j - (len(row) - 1) / 2) * BRANCH_DX, 60.0 + k * STEP_DY)
        # Cada transición, bajo sus etapas anteriores (o sobre las siguientes si no tiene); las que salen de las
        # mismas etapas se reparten a lo ancho
        groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for t in trans:
            if t.get("id") in out:
                continue
            pre = [p for p in t.get("preRefs", []) if p in out and p in succ]
            post = [p for p in t.get("postRefs", []) if p in out and p in succ]
            if pre or post:
                groups.setdefault(tuple(pre) if pre else ("→",) + tuple(post), []).append(t)
        for key, ts in groups.items():
            for j, t in enumerate(ts):
                ref = [p for p in t.get("preRefs", []) if p in out] or [p for p in t.get("postRefs", []) if p in out]
                x = sum(out[p][0] for p in ref) / len(ref) + (j - (len(ts) - 1) / 2) * BRANCH_DX
                y = (max(out[p][1] for p in ref) + STEP_DY / 2) if key[0] != "→" else (min(out[p][1] for p in ref) - STEP_DY / 2)
                out[t["id"]] = (x, y)
        x0 += (width - 1) * BRANCH_DX + PARTIAL_GAP + 2 * 44
    for t in trans:  # sin etapas conocidas: abajo a la izquierda, para que al menos se vean
        out.setdefault(t["id"], (60.0, 60.0 + (len(out) + 1) * STEP_DY / 2))
    return out


def layout_from_presentation(pres: dict[str, Any], view: str | None = None) -> Layout:
    """Posiciones de una presentación (documento 09, elementLayouts); por defecto, las de su primera vista."""
    views = [v["id"] for v in pres.get("views", [])]
    view = view or (views[0] if views else None)
    out: Layout = {}
    for lay in pres.get("elementLayouts", []):
        if view is None or lay.get("viewRef") == view:
            try:
                out[lay["elementRef"]] = (float(Fraction(lay["x"])), float(Fraction(lay["y"])))
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue  # posición ilegible: el elemento se coloca solo
    return out


def presentation_for(doc: dict[str, Any], layout: Layout) -> dict[str, Any]:
    """Presentación con las posiciones dadas, en la vista principal (el formato de grafcet/editor.py)."""
    pres = new_presentation(doc["id"])
    view = pres["views"][0]["id"]
    known = {s["id"] for s in doc["steps"]} | {t["id"] for t in doc["transitions"]}
    known |= {x["id"] for x in doc["hierarchy"]["macros"]}
    pres["elementLayouts"] = [{"elementRef": i, "viewRef": view, "x": _coord(x), "y": _coord(y)}
                              for i, (x, y) in layout.items() if i in known]
    return pres
