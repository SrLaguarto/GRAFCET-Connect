"""Constructor compacto de modelos y escenarios (documento 09).

Genera documentos reales con el formato del documento 09, que pasan por la misma validación, compilación y
sesión que cualquier modelo guardado. Lo usan los ejemplos del simulador, el comparador de decisiones y las
pruebas. Convención: el ID de cada etapa y variable coincide con su etiqueta, y las entradas booleanas valen
false salvo indicación (ficha común del documento 11).
"""
from __future__ import annotations

from typing import Any

from . import expressions as ex
from .diagnostics import DiagnosticError
from .editor import new_model_document
from .model import CompiledModel, ValidationResult, validate_model
from .profile import PROFILE_ID
from .scenario import Scenario, load_scenario

S = 1_000_000  # 1 s en µs


class M:
    def __init__(self, mid: str = "m") -> None:
        self.doc = new_model_document(mid)
        self.partial("g")
        self._n = 0

    def partial(self, pid: str, owner: str | None = None) -> "M":
        p = {"id": pid, "label": pid, "stepRefs": [], "transitionRefs": []}
        if owner:
            p["ownerRef"] = owner
        self.doc["partials"].append(p)
        return self

    def _p(self, pid: str) -> dict[str, Any]:
        return next(p for p in self.doc["partials"] if p["id"] == pid)

    def var(self, name: str, role: str = "input", kind: str = "bool", scale: int | None = None, unit: str = "",
            init: Any = None, domain: dict[str, Any] | None = None) -> "M":
        t: dict[str, Any] = {"kind": kind}
        if kind == "decimal":
            t["scale"] = scale or 0
        if init is None:
            init = False if kind == "bool" else "0"
        self.doc["variables"].append({"id": name, "name": name, "scopeRef": self.doc["id"], "role": role, "type": t,
                                      "unit": unit, "domain": domain or {}, "initialValue": init})
        return self

    def step(self, sid: str, initial: bool = False, kind: str = "ordinary", partial: str = "g") -> "M":
        self.doc["steps"].append({"id": sid, "label": sid, "partialRef": partial, "kind": kind, "initial": initial,
                                  "actionRefs": []})
        self._p(partial)["stepRefs"].append(sid)
        return self

    def expr(self, text: str, mode: str = "executable") -> str:
        self._n += 1
        eid = f"e{self._n}"
        if mode == "descriptive":
            self.doc["expressions"].append({"id": eid, "mode": "descriptive", "text": text, "bindings": {}})
            return eid
        known = {v["name"]: v["id"] for v in self.doc["variables"]}
        known.update({s["label"]: s["id"] for s in self.doc["steps"]})
        known.update({p["label"]: p["id"] for p in self.doc["partials"]})
        known.update({x["label"]: x["id"] for x in self.doc["hierarchy"]["macros"]})
        resolve, found = ex.recording_resolver(lambda k, n: known.get(n))
        meaning = ex.parse(text, resolve)
        self.doc["expressions"].append({"id": eid, "mode": "executable", "text": text, "meaning": meaning,
                                        "bindings": dict(found)})
        return eid

    def trans(self, tid: str, pre: list[str], post: list[str], cond: str, partial: str = "g",
              descriptive: bool = False) -> "M":
        eid = self.expr(cond, "descriptive" if descriptive else "executable")
        self.doc["transitions"].append({"id": tid, "partialRef": partial, "preRefs": list(pre), "postRefs": list(post),
                                        "conditionRef": eid})
        self._p(partial)["transitionRefs"].append(tid)
        return self

    def _attach(self, step: str, action: dict[str, Any]) -> None:
        self.doc["actions"].append(action)
        next(s for s in self.doc["steps"] if s["id"] == step)["actionRefs"].append(action["id"])

    def cont(self, step: str, target: str, cond: str = "true", limit_us: int | None = None, aid: str | None = None) -> "M":
        a = {"id": aid or f"a.{step}.{target}.{len(self.doc['actions'])}", "stepRef": step, "mode": "continuous",
             "targetRef": target, "conditionRef": self.expr(cond)}
        if limit_us is not None:
            a["limitUs"] = str(limit_us)
        self._attach(step, a)
        return self

    def stored(self, step: str, target: str, trigger: str, value: str, event: str | None = None,
               aid: str | None = None, sources: list[str] | None = None) -> "M":
        trig: dict[str, Any] = {"kind": trigger, "sourceRefs": sources or []}
        if event is not None:
            trig["expressionRef"] = self.expr(event)
        a = {"id": aid or f"a.{step}.{target}.{len(self.doc['actions'])}", "stepRef": step, "mode": "stored",
             "targetRef": target, "trigger": trig, "valueRef": self.expr(value)}
        self._attach(step, a)
        return self

    def macro(self, mid: str, expansion: str, entry: str, exit_: str, partial: str = "g") -> "M":
        """Macroetapa con su expansión (documento 09, hierarchy.macros y hierarchy.expansions)."""
        h = self.doc["hierarchy"]
        h["macros"].append({"id": mid, "label": mid, "partialRef": partial, "expansionRef": f"x{mid}"})
        h["expansions"].append({"id": f"x{mid}", "ownerMacroRef": mid, "partialRef": expansion, "entryRef": entry,
                                "exitRef": exit_})
        return self

    def enclosure(self, owner: str, partial: str, activation: list[str]) -> "M":
        self.doc["hierarchy"]["enclosures"].append({"id": f"enc{partial}", "ownerStepRef": owner, "partialRef": partial,
                                                    "activationRefs": list(activation)})
        return self

    def force(self, fid: str, source: str, target: str, kind: str, steps: list[str] | None = None) -> "M":
        f = {"id": fid, "sourceStepRef": source, "targetPartialRef": target, "targetKind": kind}
        if steps is not None:
            f["targetSteps"] = list(steps)
        self.doc["forces"].append(f)
        return self

    def validate(self, options: dict[str, str] | None = None) -> ValidationResult:
        return validate_model(self.doc, options)

    def compile(self, options: dict[str, str] | None = None) -> CompiledModel:
        res = self.validate(options)
        blocking = [d for d in res.diagnostics if d.blocks_start]
        if res.model is None or blocking:
            raise DiagnosticError(*(blocking or res.diagnostics))
        return res.model


def fmt(v: Any) -> Any:
    return v if isinstance(v, bool) else str(v)


def scenario(cm: CompiledModel, init: dict[str, Any] | None = None, batches: list[tuple[int, int, dict[str, Any]]] = (),
             horizon: int | None = None, max_contexts: int = 10_000, sid: str = "esc") -> Scenario:
    init_all = {v: False for v in cm.inputs if cm.variables[v].type.kind == "bool"}
    init_all.update({v: "0" for v in cm.inputs if cm.variables[v].type.kind != "bool"})
    init_all.update({k: fmt(v) for k, v in (init or {}).items()})
    doc = {"family": "scenario", "formatVersion": "0.1", "id": sid, "modelRevision": cm.revision,
           "semanticProfile": PROFILE_ID, "timeUnit": "us", "initialInputs": init_all,
           "batches": [{"id": f"b{i}", "timeUs": str(t), "ordinalAtTime": o, "origin": "escenario",
                        "changes": [{"variableRef": k, "value": fmt(v)} for k, v in ch.items()]}
                       for i, (t, o, ch) in enumerate(batches)],
           "stopCondition": {"maxContexts": max_contexts, **({"horizonUs": str(horizon)} if horizon is not None else {})}}
    sc, diags = load_scenario(doc, cm)
    if sc is None:
        raise DiagnosticError(*diags)
    return sc
