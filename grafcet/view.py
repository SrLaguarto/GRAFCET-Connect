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

from collections import deque
from fractions import Fraction
from typing import Any, Callable

from .builder import M, scenario
from .diagnostics import Diagnostic, DiagnosticError
from .editor import _coord, new_presentation
from .engine import Session
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


def norm(m: dict[str, Any], top: bool = True) -> list[dict[str, Any]]:
    op = m["operator"]
    if op == "lit":
        lit = m["literal"]
        if lit["type"] == "bool":
            return [_seg("= 1" if top and lit["value"] else ("1" if lit["value"] else "0"))]
        if lit["type"] == "duration":
            return [_seg(_dur(int(lit["value"])))]
        return [_seg(lit["value"].replace(".", ","))]
    if op == "ref":
        return [_seg(m["reference"])]
    if op in ("active", "activePartial", "activeMacro"):
        return [_seg("X"), _seg(m["reference"], s=True)]
    if op in ("rise", "fall"):
        inner = m["operands"][0]
        body = norm(inner, False)
        if inner["operator"] not in ("ref", "active", "lit"):
            body = _paren(body)
        return [_seg("↑" if op == "rise" else "↓")] + body
    if op == "not":
        return [dict(s, o=True) for s in norm(m["operands"][0], False)]
    if op == "delay":  # t1/condición/t2 de la norma; un tiempo de 0 s no se escribe (respuesta 4.4 revisada)
        d1, base, d2 = m["operands"]
        out = norm(base, False)
        if int(d1["literal"]["value"]):
            out = norm(d1, False) + [_seg("/")] + out
        if int(d2["literal"]["value"]):
            out += [_seg("/")] + norm(d2, False)
        return out
    if op == "neg":
        return [_seg("−")] + norm(m["operands"][0], False)
    a, b = m["operands"]

    def side(x: dict[str, Any]) -> list[dict[str, Any]]:
        segs = norm(x, False)
        return _paren(segs) if _PREC.get(x["operator"], 9) < _PREC[op] else segs
    if op in _CMP:
        return [_seg("[")] + side(a) + [_seg(f" {_CMP[op]} ")] + side(b) + [_seg("]")]
    sym = {"and": "·", "or": " + ", **_ARITH}[op]
    return side(a) + [_seg(sym)] + side(b)


def t_s(us: str | int) -> str:
    return format_duration(int(us), "s", "es-ES")


def describe(r: dict[str, Any], texts: dict[str, str]) -> dict[str, str] | None:
    k = r["kind"]
    when = t_s(r.get("timeUs", 0))
    if k == "inicio":
        return {"kind": k, "time": when, "text": f"Inicio · S = {{{', '.join(r['situation'])}}}"}
    if k == "contexto":
        what = ", ".join(f"{v}={str(x).lower()}" for v, x in r["inputChanges"].items()) or "sin cambio de entradas"
        src = "vencimiento temporal" if r["stimulus"] == "vencimiento" else f"lote {r['origin']}"
        names = sorted({texts.get(e.split(".")[0], e) for e in r["events"]})
        ev = f" · eventos: {', '.join(names)}" if names else ""
        return {"kind": k, "time": when, "text": f"{src}: {what}{ev}"}
    if k == "evolucion":
        asg = "; ".join(f"{a['target']}:={a['value']}" for a in r["assignments"])
        if r["evolutionIndex"] == 0:
            return {"kind": k, "time": when, "text": f"Arranque: acciones al activar las etapas iniciales · {asg}"}
        perm = f" · permanece {', '.join(r['permanent'])}" if r["permanent"] else ""
        perm += f" · {', '.join(r['durationKept'])} reentra sin interrumpir su duración" if r.get("durationKept") else ""
        return {"kind": k, "time": when, "text": f"Evolución {r['evolutionIndex']}: franquea {{{', '.join(r['cleared'])}}}"
                f" → S = {{{', '.join(r['situation'])}}}{perm}" + (f" · {asg}" if asg else "")}
    if k == "estable":
        if "reason" in r:
            return None
        virt = f" · inestables: {', '.join(r['virtualSteps'])}" if r.get("virtualSteps") else ""
        hyp = "".join(f" · hipótesis {h['question']} ({h['reading']}) aplicada a {h['transition']}"
                      for h in r.get("hypotheses", []))
        return {"kind": k, "time": when, "text": f"Estable · S = {{{', '.join(r['situation'])}}}{virt}{hyp}"}
    if k in ("fallo", "limite"):
        d = r["diagnostics"][0]
        q = f" ({d['question']})" if d.get("question") else ""
        return {"kind": "fallo", "time": when, "text": f"{d['code']}{q}: {d['message']}"}
    return None


class Vista:
    """Un modelo con su sesión bajo unas lecturas dadas: lo que se dibuja en una ventana o en un panel."""

    def __init__(self, key: str, title: str, help_text: str, build: Build,
                 options: dict[str, str], init: dict[str, Any] | None = None,
                 batches: list[tuple[int, int, dict[str, Any]]] = (), budget: int = 10_000) -> None:
        m, layout = build()
        doc = m.doc if isinstance(m, M) else m
        self.key, self.options, self.doc = key, options, doc
        res = validate_model(doc, options)
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
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            # Documento demasiado dañado para dibujarlo: no se dibuja nada y se listan los errores
            self.texts = {}
            self.model = {"key": key, "title": title, "help": help_text, "compilable": False, "steps": [],
                          "macros": [], "partials": [], "transitions": [], "inputs": [], "numericInputs": {}}

    def _structure(self, key: str, title: str, help_text: str, doc: dict[str, Any], compilable: bool,
                   layout: Layout | None) -> dict[str, Any]:
        layout = {**auto_layout(doc), **(layout or {})}
        exprs = {e["id"]: e for e in doc["expressions"]}
        self.texts = {eid: e["text"] for eid, e in exprs.items()}

        def disp(eid: str | None, top: bool = False) -> list[dict[str, Any]] | None:
            if eid is None:
                return None
            e = exprs[eid]
            return norm(e["meaning"], top) if e["mode"] == "executable" else [_seg(e["text"])]
        acts: dict[str, list[dict[str, Any]]] = {}
        for a in doc["actions"]:
            if a["mode"] == "continuous":
                cond = exprs[a["conditionRef"]]
                plain = cond["mode"] == "executable" and cond["meaning"] == {"operator": "lit", "literal": {"type": "bool", "value": True}}
                acts.setdefault(a["stepRef"], []).append({"kind": "continuous", "target": a["targetRef"],
                                                          "text": [_seg(a["targetRef"])],
                                                          "cond": None if plain else disp(a["conditionRef"])})
            else:
                trig = a["trigger"]
                acts.setdefault(a["stepRef"], []).append({
                    "kind": "stored", "target": a["targetRef"], "trigger": trig["kind"],
                    "text": [_seg(f"{a['targetRef']} := ")] + disp(a["valueRef"]),
                    "event": disp(trig.get("expressionRef"))})
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
            sit = {"explicit": "{" + ",".join(f.get("targetSteps", [])) + "}", "current": "{*}", "empty": "{ }",
                   "initial": "{INIT}"}[f["targetKind"]]
            acts.setdefault(f["sourceStepRef"], []).append({"kind": "force", "id": f["id"], "target": f["targetPartialRef"],
                                                           "text": [_seg(f"{labels[f['targetPartialRef']]}{sit}")]})
        return {
            "key": key, "title": title, "help": help_text, "compilable": compilable,
            "steps": [{"id": s["id"], "label": s["label"], "initial": s["initial"],
                       "x": layout[s["id"]][0], "y": layout[s["id"]][1],
                       "partial": None if s["partialRef"] == "g" else s["partialRef"], "kind": s["kind"],
                       "activation": s["id"] in marked, "actions": acts.get(s["id"], [])} for s in doc["steps"]],
            "macros": [{"id": x["id"], "x": layout[x["id"]][0], "y": layout[x["id"]][1], "expansion": e["partialRef"],
                        "entry": e["entryRef"], "exit": e["exitRef"]}
                       for x in hier["macros"] for e in hier["expansions"] if e["id"] == x["expansionRef"]],
            "partials": [{"id": p["id"], "label": p["label"], "owner": p.get("ownerRef"),
                          **kinds.get(p["id"], {"kind": "partial"})}
                         for p in doc["partials"] if p["id"] != "g" and p["stepRefs"]],
            "transitions": [{"id": t["id"], "label": t.get("label", t["id"]), "pre": t["preRefs"], "post": t["postRefs"],
                             "partial": t["partialRef"], "cond": disp(t["conditionRef"], top=True),
                             "x": layout[t["id"]][0], "y": layout[t["id"]][1]} for t in doc["transitions"]],
            "inputs": sorted(v["id"] for v in doc["variables"] if v["role"] == "input"),
            "numericInputs": {v["id"]: v["type"]["kind"] for v in doc["variables"]
                              if v["role"] == "input" and v["type"]["kind"] != "bool"},
        }

    def state(self) -> dict[str, Any]:
        s = self.s
        out: dict[str, Any] = {}
        if s is None:  # no compila: se dibuja la estructura y se listan los errores
            out.update({"status": "no-compilable", "diagnostics": [d.to_dict() for d in self.compile_diags],
                        "time": "—", "situation": [], "transitions": {}, "outputs": {}, "values": {}, "temporal": {},
                        "lastCleared": [], "trace": [], "nextEvent": None, "blocked": None})
            return out
        out.update({"status": s.status, "diagnostics": [d.to_dict() for d in (self.start_diags or s.diagnostics)[-2:]]})
        if s.z is None:
            return out
        obs = s.observe()
        evo = [r for r in s.trace.records if r["kind"] == "evolucion"]
        closed = next((r["kind"] for r in reversed(s.trace.records) if r["kind"] in ("estable", "fallo", "limite")), None)
        last_stable = next((r for r in reversed(s.trace.records) if r["kind"] == "estable" and "reason" not in r), None)
        out.update({
            "time": t_s(obs["timeUs"]), "timeUs": obs["timeUs"], "situation": obs["situation"],
            "macros": obs.get("macros", {}), "forces": obs.get("forces", []),
            "virtual": obs.get("recorrido", {}).get("virtualSituation"),
            "unstable": last_stable.get("virtualSteps", []) if last_stable and closed == "estable" else [],
            "transitions": obs["transitions"], "outputs": obs["outputs"],
            "values": {k: v for k, v in obs["values"].items()},
            "temporal": {k: {**v, "label": self.texts.get(k.split(".")[0], k),
                             "deadlineS": None if v["deadline"] == "inactive" else t_s(v["deadline"])}
                         for k, v in obs["temporal"].items()},
            "lastCleared": evo[-1]["cleared"] if evo and closed == "estable" else [],  # un contexto fallido no franquea
            "trace": [x for x in (describe(r, self.texts) for r in s.trace.records[-60:]) if x],
            "nextEvent": self._next(),
            "blocked": self._blocked(closed),
        })
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

    def _next(self) -> str | None:
        if self.s.status != "pausada-estable":
            return None
        nxt = self.s.next_stimulus()
        return t_s(nxt.time) if hasattr(nxt, "time") and nxt.kind == "vencimiento" else None

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

STEP_DY = 160     # entre una etapa y la siguiente; la transición queda a media altura (como en los ejemplos)
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
