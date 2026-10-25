"""Banco de pruebas interactivo del núcleo (no es la interfaz del producto).

Sirve en http://127.0.0.1:8765 una página que dibuja un ejemplo y deja cambiar
entradas, avanzar el tiempo lógico y avanzar evolución a evolución. Toda la semántica
la decide grafcet/engine.py, con el perfil provisional: la página no hace aproximaciones
y los bloqueos por cuestiones U se muestran tal cual. Solo usa la biblioteca estándar y
no sale a la red (escucha únicamente en 127.0.0.1).

El dibujo sigue la notación gráfica de la norma (tablas 1–7): etapa cuadrada, transición
como trazo corto con designación entre paréntesis, receptividad con ↑ ↓ · + y
sobrerrayado, y acciones del alto de la etapa con trazo de condición, flecha de
activación o desactivación, o banderita de evento. Las proporciones se tomaron por
inspección visual de las imágenes de la norma aportadas por el usuario; no se copia
ningún activo.

El comparador de decisiones (/comparar, P-IMP-21) ejecuta el ejemplo de cada cuestión abierta una vez
por lectura, lado a lado, y guarda la elección del responsable en docs/decisiones.json.

Uso:  python tools/banco_de_pruebas.py [--port 8765] [--abrir] [--comparar]
      o doble clic en «Probar banco de pruebas.bat» o «Comparar decisiones.bat»
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import M, scenario  # noqa: E402  (constructor de modelos con el formato del documento 09)

from grafcet.diagnostics import DiagnosticError  # noqa: E402
from grafcet.engine import Session  # noqa: E402
from grafcet.profile import SEMANTIC_OPTIONS, normalize_options  # noqa: E402
from grafcet.timeutil import format_duration  # noqa: E402

from decisiones import CATALOGO, POR_ID, RESPUESTAS_HOJA_08  # noqa: E402

HERE = Path(__file__).resolve().parent
DECISIONES = ROOT / "docs" / "decisiones.json"
COMPARADOR_PRESUPUESTO = 1_000  # evoluciones por contexto en cada panel del comparador
# Las páginas se leen una vez al arrancar: así un servidor en marcha sirve siempre las páginas de su misma
# versión. Si se releyeran en cada petición, un servidor antiguo entregaría páginas nuevas con datos antiguos.
STATIC = {path: ((HERE / name).read_bytes(), ctype) for path, name, ctype in (
    ("/", "banco_de_pruebas.html", "text/html; charset=utf-8"),
    ("/index.html", "banco_de_pruebas.html", "text/html; charset=utf-8"),
    ("/comparar", "comparador.html", "text/html; charset=utf-8"),
    ("/dibujo.js", "dibujo.js", "text/javascript; charset=utf-8"),
    ("/dibujo.css", "dibujo.css", "text/css; charset=utf-8"))}


def ej_temporizada() -> tuple[M, dict]:
    m = M().var("marcha").var("fin").var("motor", "output").var("luz", "output").var("ciclos", "internal", "int")
    m.step("E0", True).step("E1").step("E2")
    m.trans("t1", ["E0"], ["E1"], "marcha").trans("t2", ["E1"], ["E2"], "delay(3 s, active(E1), 0 s)")
    m.trans("t3", ["E2"], ["E0"], "fin")
    m.cont("E1", "motor").cont("E2", "luz").stored("E2", "ciclos", "activation", "ciclos + 1")
    return m, {"E0": (220, 60), "t1": (220, 140), "E1": (220, 220), "t2": (220, 300), "E2": (220, 380), "t3": (220, 460)}


def ej_arranque() -> tuple[M, dict]:
    m = M().var("parar").var("motor", "output").var("n", "internal", "int")
    m.step("E0", True).step("E1").step("E2")
    m.stored("E0", "n", "activation", "5").cont("E1", "motor")
    m.trans("t1", ["E0"], ["E1"], "n = 5").trans("t2", ["E1"], ["E2"], "parar")
    return m, {"E0": (220, 60), "t1": (220, 140), "E1": (220, 220), "t2": (220, 300), "E2": (220, 380)}


def ej_paralelo() -> tuple[M, dict]:
    m = M().var("p").var("q").var("r").var("s")
    for sid in "ABCDEF":
        m.step(sid, sid == "A")
    m.trans("t1", ["A"], ["B", "C"], "p").trans("t2", ["B"], ["D"], "q").trans("t3", ["C"], ["E"], "r")
    m.trans("t4", ["D", "E"], ["F"], "s").trans("t5", ["F"], ["A"], "NOT s")
    return m, {"A": (220, 50), "t1": (220, 115), "B": (150, 190), "C": (290, 190), "t2": (150, 260), "t3": (290, 260),
               "D": (150, 330), "E": (290, 330), "t4": (220, 405), "F": (220, 480), "t5": (220, 545)}


def ej_contador() -> tuple[M, dict]:
    m = M().var("pulso").var("borrar").var("alarma", "output").var("n", "internal", "int")
    m.step("A", True).step("B")
    m.cont("A", "alarma", "n >= 3").stored("A", "n", "event", "n + 1", event="rise(pulso)")
    m.trans("t1", ["A"], ["B"], "borrar").trans("t2", ["B"], ["A"], "NOT borrar").stored("B", "n", "activation", "0")
    return m, {"A": (220, 70), "t1": (220, 150), "B": (220, 230), "t2": (220, 310)}


def ej_bloqueo_u03() -> tuple[M, dict]:
    m = M().var("p").var("reinicio").step("A", True).step("B").step("C")
    m.trans("t", ["A"], ["B"], "rise(p)").trans("u", ["B"], ["C"], "rise(p)").trans("v", ["C"], ["A"], "reinicio")
    return m, {"A": (220, 60), "t": (220, 140), "B": (220, 220), "u": (220, 300), "C": (220, 380), "v": (220, 460)}


def ej_conflicto() -> tuple[M, dict]:
    m = M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C")
    m.trans("t", ["A"], ["B", "C"], "p")
    m.stored("B", "z", "activation", "1", aid="aB").stored("C", "z", "activation", "2", aid="aC")
    return m, {"A": (220, 60), "t": (220, 130), "B": (150, 215), "C": (330, 215)}


def ej_conflicto_ejecucion() -> tuple[M, dict]:
    m = M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C", True).step("D")
    m.trans("t", ["A"], ["B"], "p").trans("u", ["C"], ["D"], "p")
    m.stored("B", "z", "activation", "1", aid="aB").stored("D", "z", "activation", "2", aid="aD")
    return m, {"A": (150, 60), "t": (150, 140), "B": (150, 220), "C": (330, 60), "u": (330, 140), "D": (330, 220)}


EJEMPLOS: dict[str, tuple[str, str, Callable[[], tuple[M, dict]]]] = {
    "temporizada": ("Secuencia con temporización", "Pulse «marcha»: E1 activa el motor; a los 3 s pasa a E2 (luz, "
                    "ciclos+1). «fin» vuelve a E0. Pruebe a soltar «marcha» y poner «fin»=1 antes de los 3 s: E2 es "
                    "una etapa inestable (sin luz, pero ciclos+1 se ejecuta). Con «marcha»=1 y «fin»=1, E1 sale y vuelve "
                    "a entrar en el mismo instante sin interrumpir su duración (P-IMP-18): el temporizador sigue vencido, "
                    "el ciclo se repite sin fin en tiempo cero y el motor lo corta con D-LIM-EVOL.", ej_temporizada),
    "arranque": ("Arranque con acción inicial", "Al arrancar se ejecuta n := 5 en la etapa inicial E0 (hoja 08, "
                 "1.1) y t1 ve ese valor en el mismo instante (2.3), así que el grafcet evoluciona en τ = 0 (1.2): "
                 "E0 queda inestable y se arranca en E1 con el motor en marcha.", ej_arranque),
    "paralelo": ("Paralelismo y sincronización", "p divide en dos ramas; q y r avanzan cada una; s solo franquea t4 "
                 "cuando D y E están activas a la vez.", ej_paralelo),
    "contador": ("Contador por eventos", "Cada subida de «pulso» suma 1 a n (acción por evento). Pulsar sin soltar no "
                 "cuenta dos veces. Con n ≥ 3 se enciende «alarma». «borrar» pone n a 0.", ej_contador),
    "bloqueo-u03": ("Bloqueo por U-03", "Dos transiciones seguidas con ↑p. ¿Una subida de p deja la situación "
                    "en B o en C? Es la cuestión abierta U-03. Por defecto el motor se detiene y no elige; en «Opciones de "
                    "interpretación» puede probar cada lectura como hipótesis (también con «reinicio»=1).", ej_bloqueo_u03),
    "conflicto": ("Conflicto de escritura al compilar", "t activa B y C en la misma evolución; B escribe z:=1 y C z:=2. "
                  "Es un conflicto seguro: el programa no puede compilarse.", ej_conflicto),
    "conflicto-ejecucion": ("Conflicto de escritura en ejecución", "t y u son independientes, pero ambas dependen de p: "
                            "al subir p se activan B y D a la vez y escriben valores distintos en z. Solo se sabe al "
                            "ejecutar: D-ESCRITURA-CONFLICTO, sin elegir valor.", ej_conflicto_ejecucion),
}

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
    if op == "delay":
        d1, base, d2 = m["operands"]
        out = norm(d1, False) + [_seg("/")] + norm(base, False)
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
    """Un modelo con su sesión bajo unas lecturas dadas: lo que la página dibuja en un panel."""

    def __init__(self, key: str, title: str, help_text: str, build: Callable[[], tuple[M, dict]],
                 options: dict[str, str], init: dict[str, Any] | None = None,
                 batches: list[tuple[int, int, dict[str, Any]]] = (), budget: int = 10_000) -> None:
        m, layout = build()
        self.key, self.options = key, options
        res = m.validate(options)
        self.compile_diags = [d for d in res.diagnostics if d.blocks_start]
        self.s: Session | None = None
        self.start_diags: list = []
        if res.can_simulate:
            cm = res.model
            self.s = Session(cm, scenario(cm, init, batches, max_contexts=1_000_000), budget=budget, options=options)
            self.start_diags = self.s.start()
        exprs = {e["id"]: e for e in m.doc["expressions"]}
        self.texts = {eid: e["text"] for eid, e in exprs.items()}

        def disp(eid: str | None, top: bool = False) -> list[dict[str, Any]] | None:
            if eid is None:
                return None
            e = exprs[eid]
            return norm(e["meaning"], top) if e["mode"] == "executable" else [_seg(e["text"])]
        acts: dict[str, list[dict[str, Any]]] = {}
        for a in m.doc["actions"]:
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
        self.model = {
            "key": key, "title": title, "help": help_text, "compilable": res.can_simulate,
            "steps": [{"id": s["id"], "initial": s["initial"], "x": layout[s["id"]][0], "y": layout[s["id"]][1],
                       "partial": None if s["partialRef"] == "g" else s["partialRef"],
                       "actions": acts.get(s["id"], [])} for s in m.doc["steps"]],
            "transitions": [{"id": t["id"], "pre": t["preRefs"], "post": t["postRefs"],
                             "cond": disp(t["conditionRef"], top=True),
                             "x": layout[t["id"]][0], "y": layout[t["id"]][1]} for t in m.doc["transitions"]],
            "inputs": sorted(v["id"] for v in m.doc["variables"] if v["role"] == "input"),
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


class Banco:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.options = normalize_options(None)  # por defecto: decisiones del responsable y, lo abierto, detener
        self.load("temporizada")

    def load(self, key: str) -> None:
        title, help_text, build = EJEMPLOS[key]
        self.key = key
        self.v = Vista(key, title, help_text, build, self.options)
        self.model = self.v.model

    def state(self) -> dict[str, Any]:
        return {**self.v.state(), "options": self.options,
                "optionSpecs": {q: {"default": v["default"], "values": v["values"]} for q, v in SEMANTIC_OPTIONS.items()}}

    def act(self, op: str, body: dict[str, Any]) -> dict[str, Any]:
        if op == "cargar":
            self.load(body.get("ejemplo", self.key))
        elif op == "reiniciar":
            self.load(self.key)
        elif op == "opciones":
            self.options = normalize_options(body.get("options"))  # cambia el perfil efectivo: ejecución nueva
            self.load(self.key)
        else:
            self.v.act(op, body)
        return {"model": self.model, "state": self.state()}


class Comparador:
    """Comparador de decisiones (P-IMP-21): el mismo ejemplo, una vez por lectura, con el mismo guion.

    La elección se guarda en docs/decisiones.json; no cambia el motor. Cada respuesta se incorpora después
    como lectura por defecto, con su prueba y su referencia, igual que las de los bloques 1 y 2."""

    def __init__(self, path: Path = DECISIONES) -> None:
        self.path = path
        self.load(CATALOGO[0].id)

    # -- respuestas guardadas
    def answers(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))["decisiones"]
        except FileNotFoundError:
            return {}

    def choose(self, did: str, value: str, comment: str = "") -> None:
        d = POR_ID[did]
        texts = dict(d.choices)
        if value != "abierta" and value not in texts:
            raise ValueError(f"opción desconocida para {did}: {value}")
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            doc = nuevo_registro()
        doc["decisiones"][did] = {"eleccion": value, "texto": texts.get(value, "Dejar abierta"),
                                  "pregunta": d.title, "origen": "comparador", "fecha": date.today().isoformat(),
                                  "comentario": comment.strip()}
        doc["decisiones"] = dict(sorted(doc["decisiones"].items(), key=lambda kv: [int(x) for x in kv[0].split(".")]))
        guardar_registro(self.path, doc)

    # -- ejemplo en curso
    def load(self, did: str) -> None:
        d = POR_ID[did]
        self.d, self.k = d, 0
        self.panels: list[tuple[str, Vista | None, str | None]] = []
        if not d.simulable:
            return
        for value, _ in d.choices:
            opts = normalize_options({**d.base, d.option: value})
            self.panels.append((value, Vista(d.id, d.title, d.example, d.build, opts, d.init, d.batches,
                                             budget=COMPARADOR_PRESUPUESTO), None))

    def step(self) -> None:
        if self.k >= len(self.d.script):
            raise RuntimeError("el guion del ejemplo ya terminó; pulse «Repetir» para empezar de nuevo")
        st = self.d.script[self.k]
        self._each(st["op"], st)
        self.k += 1

    def _each(self, op: str, body: dict[str, Any]) -> None:
        panels = []
        for value, v, _ in self.panels:
            note = None
            if v.s is None:
                note = "no compila: no se ejecuta"
            elif v.s.status != "pausada-estable":
                note = "detenido: el paso no se aplica"
            else:
                try:
                    v.act(op, body)
                except (DiagnosticError, RuntimeError, ValueError, KeyError) as exc:
                    note = str(exc)
            panels.append((value, v, note))
        self.panels = panels

    def free(self, op: str, body: dict[str, Any]) -> None:
        """Entrada o avance libre, igual en todos los paneles (fuera del guion)."""
        if op == "entrada":
            for _, v, _ in self.panels:
                if v.s is not None and v.s.status == "pausada-estable":
                    v.act("fijar", {"cambios": {body["var"]: not v.s.z.values[body["var"]]}})
            self.panels = [(value, v, None) for value, v, _ in self.panels]
        elif op == "avanzar":
            self._each("avanzar", body)
        else:
            raise ValueError(f"operación desconocida: {op}")

    def view(self) -> dict[str, Any]:
        d = self.d
        answers = self.answers()
        texts = dict(d.choices)
        return {
            "catalog": [{"id": x.id, "block": x.block, "title": x.title, "simulable": x.simulable,
                         "answer": answers.get(x.id, {}).get("eleccion")} for x in CATALOGO],
            "decision": {"id": d.id, "block": d.block, "title": d.title, "question": d.question, "example": d.example,
                         "note": d.note, "simulable": d.simulable, "choices": [{"value": v, "text": t} for v, t in d.choices],
                         "base": [{"question": q, "value": v, "text": SEMANTIC_OPTIONS[q]["values"][v]} for q, v in d.base.items()],
                         "answer": answers.get(d.id)},
            "script": [{"text": x["texto"], "done": i < self.k} for i, x in enumerate(d.script)],
            "stepIndex": self.k,
            "panels": [{"value": value, "text": texts[value], "expect": d.expect.get(value, ""), "note": note,
                        "model": v.model, "state": v.state()} for value, v, note in self.panels],
            "file": str(self.path.relative_to(ROOT) if self.path.is_relative_to(ROOT) else self.path).replace("\\", "/"),
        }

    def act(self, op: str, body: dict[str, Any]) -> dict[str, Any]:
        if op == "cargar":
            self.load(body["id"])
        elif op == "repetir":
            self.load(self.d.id)
        elif op == "paso":
            self.step()
        elif op in ("entrada", "avanzar"):
            self.free(op, body)
        elif op == "elegir":
            self.choose(body["id"], body["value"], body.get("comentario", ""))
        else:
            raise ValueError(f"operación desconocida: {op}")
        return self.view()


def nuevo_registro() -> dict[str, Any]:
    """Registro de respuestas precargado con las de la hoja 08 (bloques 1 y 2)."""
    decisiones = {}
    for did, (value, comment) in RESPUESTAS_HOJA_08.items():
        d = POR_ID[did]
        decisiones[did] = {"eleccion": value, "texto": dict(d.choices)[value], "pregunta": d.title,
                           "origen": "hoja 08", "fecha": "2026-10-25", "comentario": comment}
    return {"formato": "decisiones-0.1",
            "nota": "Respuestas del responsable a las cuestiones abiertas. Una respuesta no es conformidad ni cita una "
                    "cláusula: el contraste normativo sigue pendiente (U-01). Cada una se implementa después como "
                    "lectura por defecto, con su prueba y su referencia (P-IMP-21).",
            "decisiones": decisiones}


def guardar_registro(path: Path, doc: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


BANCO: Banco | None = None
COMPARADOR: Comparador | None = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        if self.path in STATIC:
            body, ctype = STATIC[self.path]
            self._send(200, body, ctype)
        elif self.path == "/api/estado":
            with BANCO.lock:
                self._json({"model": BANCO.model, "state": BANCO.state(),
                            "examples": [{"key": k, "title": v[0]} for k, v in EJEMPLOS.items()]})
        elif self.path == "/api/cmp/estado":
            with BANCO.lock:
                self._json(COMPARADOR.view())
        else:
            self._send(404, b"no encontrado", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/api/"):
            self._send(404, b"no encontrado", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        with BANCO.lock:
            if self.path.startswith("/api/cmp/"):
                try:
                    self._json(COMPARADOR.act(self.path[9:], body))
                except (DiagnosticError, RuntimeError, ValueError, KeyError) as exc:
                    self._json({"error": str(exc), **COMPARADOR.view()}, 400)
                return
            try:
                self._json(BANCO.act(self.path[5:], body))
            except (DiagnosticError, RuntimeError, ValueError, KeyError) as exc:
                self._json({"error": str(exc), "model": BANCO.model, "state": BANCO.state()}, 400)

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


def main() -> None:
    global BANCO, COMPARADOR
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--abrir", action="store_true", help="abrir el navegador cuando el servidor esté listo")
    ap.add_argument("--comparar", action="store_true", help="abrir directamente el comparador de decisiones")
    args = ap.parse_args()
    BANCO = Banco()
    if not DECISIONES.exists():
        guardar_registro(DECISIONES, nuevo_registro())
    COMPARADOR = Comparador()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}" + ("/comparar" if args.comparar else "")
    print(f"Banco de pruebas en {url}  (cierre esta ventana o pulse Ctrl+C para detenerlo)", flush=True)
    if args.abrir:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
