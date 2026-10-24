"""Banco de pruebas interactivo del núcleo (no es la interfaz del producto).

Sirve en http://127.0.0.1:8765 una página que dibuja un ejemplo y deja cambiar
entradas, avanzar el tiempo lógico y avanzar evolución a evolución. Toda la semántica
la decide grafcet/engine.py, perfil provisional: no hay aproximaciones en la página y
los bloqueos por cuestiones U se muestran tal cual. Solo biblioteca estándar, sin red
externa (escucha únicamente en 127.0.0.1).

Uso:  python tools/banco_de_pruebas.py [--port 8765] [--abrir]
      o doble clic en «Probar banco de pruebas.bat»
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from helpers import M, scenario  # noqa: E402  (constructor de modelos con el formato del documento 09)

from grafcet.diagnostics import DiagnosticError  # noqa: E402
from grafcet.engine import Session  # noqa: E402
from grafcet.profile import SEMANTIC_OPTIONS, normalize_options  # noqa: E402
from grafcet.timeutil import format_duration  # noqa: E402

PAGE = Path(__file__).with_name("banco_de_pruebas.html")


def ej_temporizada() -> tuple[M, dict]:
    m = M().var("marcha").var("fin").var("motor", "output").var("luz", "output").var("ciclos", "internal", "int")
    m.step("E0", True).step("E1").step("E2")
    m.trans("t1", ["E0"], ["E1"], "marcha").trans("t2", ["E1"], ["E2"], "delay(3 s, active(E1), 0 s)")
    m.trans("t3", ["E2"], ["E0"], "fin")
    m.cont("E1", "motor").cont("E2", "luz").stored("E2", "ciclos", "activation", "ciclos + 1")
    return m, {"E0": (220, 60), "t1": (220, 130), "E1": (220, 200), "t2": (220, 270), "E2": (220, 340), "t3": (220, 410)}


def ej_paralelo() -> tuple[M, dict]:
    m = M().var("p").var("q").var("r").var("s")
    for sid in "ABCDEF":
        m.step(sid, sid == "A")
    m.trans("t1", ["A"], ["B", "C"], "p").trans("t2", ["B"], ["D"], "q").trans("t3", ["C"], ["E"], "r")
    m.trans("t4", ["D", "E"], ["F"], "s").trans("t5", ["F"], ["A"], "NOT s")
    return m, {"A": (220, 50), "t1": (220, 110), "B": (130, 180), "C": (310, 180), "t2": (130, 245), "t3": (310, 245),
               "D": (130, 310), "E": (310, 310), "t4": (220, 380), "F": (220, 450), "t5": (220, 515)}


def ej_contador() -> tuple[M, dict]:
    m = M().var("pulso").var("borrar").var("alarma", "output").var("n", "internal", "int")
    m.step("A", True).step("B")
    m.stored("A", "n", "event", "n + 1", event="rise(pulso)").cont("A", "alarma", "n >= 3")
    m.trans("t1", ["A"], ["B"], "borrar").trans("t2", ["B"], ["A"], "NOT borrar").stored("B", "n", "activation", "0")
    return m, {"A": (220, 60), "t1": (220, 140), "B": (220, 220), "t2": (220, 300)}


def ej_bloqueo_u03() -> tuple[M, dict]:
    m = M().var("p").var("reinicio").step("A", True).step("B").step("C")
    m.trans("t", ["A"], ["B"], "rise(p)").trans("u", ["B"], ["C"], "rise(p)").trans("v", ["C"], ["A"], "reinicio")
    return m, {"A": (220, 60), "t": (220, 130), "B": (220, 200), "u": (220, 270), "C": (220, 340), "v": (220, 410)}


def ej_conflicto() -> tuple[M, dict]:
    m = M().var("p").var("z", "internal", "int").step("A", True).step("B").step("C")
    m.trans("t", ["A"], ["B", "C"], "p")
    m.stored("B", "z", "activation", "1", aid="aB").stored("C", "z", "activation", "2", aid="aC")
    return m, {"A": (220, 60), "t": (220, 130), "B": (130, 210), "C": (310, 210)}


EJEMPLOS: dict[str, tuple[str, str, Callable[[], tuple[M, dict]]]] = {
    "temporizada": ("Secuencia con temporización", "Pulse «marcha»: E1 activa el motor; a los 3 s pasa a E2 (luz, "
                    "ciclos+1). «fin» vuelve a E0. Pruebe a soltar «marcha» y poner «fin»=1 antes de los 3 s: E2 se "
                    "recorre virtualmente (sin luz, pero ciclos+1 se conserva). Si deja «marcha»=1, el recorrido volvería "
                    "a entrar en E1 en el mismo instante: es el hallazgo H-09 y el motor se detiene.", ej_temporizada),
    "paralelo": ("Paralelismo y sincronización", "p divide en dos ramas; q y r avanzan cada una; s solo franquea t4 "
                 "cuando D y E están activas a la vez.", ej_paralelo),
    "contador": ("Contador por eventos", "Cada subida de «pulso» suma 1 a n (acción por evento). Pulsar sin soltar no "
                 "cuenta dos veces. Con n ≥ 3 se enciende «alarma». «borrar» pone n a 0.", ej_contador),
    "bloqueo-u03": ("Bloqueo por U-03", "Dos transiciones seguidas con rise(p). ¿Una subida de p deja la situación "
                    "en B o en C? Es la cuestión abierta U-03. Por defecto el motor se detiene y no elige; en «Opciones de "
                    "interpretación» puede probar cada lectura como hipótesis (también con «reinicio»=1).", ej_bloqueo_u03),
    "conflicto": ("Conflicto de escritura", "p activa B y C a la vez; B escribe z:=1 y C z:=2. El motor no elige: "
                  "D-ESCRITURA-CONFLICTO con ambos autores.", ej_conflicto),
}


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
        perm = f" · permanece {', '.join(r['permanent'])}" if r["permanent"] else ""
        return {"kind": k, "time": when, "text": f"Evolución {r['evolutionIndex']}: franquea {{{', '.join(r['cleared'])}}}"
                f" → S = {{{', '.join(r['situation'])}}}{perm}" + (f" · {asg}" if asg else "")}
    if k == "estable":
        if "reason" in r:
            return None
        virt = f" · virtuales: {', '.join(r['virtualSteps'])}" if r.get("virtualSteps") else ""
        hyp = "".join(f" · hipótesis {h['question']} ({h['reading']}) aplicada a {h['transition']}"
                      for h in r.get("hypotheses", []))
        return {"kind": k, "time": when, "text": f"Estable · S = {{{', '.join(r['situation'])}}}{virt}{hyp}"}
    if k in ("fallo", "limite"):
        d = r["diagnostics"][0]
        q = f" ({d['question']})" if d.get("question") else ""
        return {"kind": "fallo", "time": when, "text": f"{d['code']}{q}: {d['message']}"}
    return None


class Banco:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.options = normalize_options(None)  # por defecto, U-03 detiene (P-IMP-15)
        self.load("temporizada")

    def load(self, key: str) -> None:
        title, help_text, build = EJEMPLOS[key]
        m, layout = build()
        cm = m.compile()
        self.key, self.cm = key, cm
        self.s = Session(cm, scenario(cm, max_contexts=1_000_000), options=self.options)
        self.start_diags = self.s.start()
        texts = {e["id"]: e["text"] for e in m.doc["expressions"]}
        self.texts = texts
        acts = {}
        for a in m.doc["actions"]:
            if a["mode"] == "continuous":
                acts.setdefault(a["stepRef"], []).append(f"{a['targetRef']}" + (
                    "" if texts[a["conditionRef"]] == "true" else f" si {texts[a['conditionRef']]}"))
            else:
                trig = {"activation": "al activar", "deactivation": "al desactivar"}.get(
                    a["trigger"]["kind"], f"en {texts.get(a['trigger'].get('expressionRef'), 'evento')}")
                acts.setdefault(a["stepRef"], []).append(f"{a['targetRef']}:={texts[a['valueRef']]} ({trig})")
        self.model = {
            "key": key, "title": title, "help": help_text,
            "steps": [{"id": s["id"], "initial": s["initial"], "x": layout[s["id"]][0], "y": layout[s["id"]][1],
                       "actions": acts.get(s["id"], [])} for s in m.doc["steps"]],
            "transitions": [{"id": t["id"], "pre": t["preRefs"], "post": t["postRefs"], "cond": texts[t["conditionRef"]],
                             "x": layout[t["id"]][0], "y": layout[t["id"]][1]} for t in m.doc["transitions"]],
            "inputs": sorted(cm.inputs),
        }

    def state(self) -> dict[str, Any]:
        s = self.s
        out: dict[str, Any] = {"status": s.status, "diagnostics": [d.to_dict() for d in (self.start_diags or s.diagnostics)[-2:]],
                               "options": self.options,
                               "optionSpecs": {q: {"default": v["default"], "values": v["values"]} for q, v in SEMANTIC_OPTIONS.items()}}
        if s.z is None:
            return out
        obs = s.observe()
        evo = [r for r in s.trace.records if r["kind"] == "evolucion"]
        closed = next((r["kind"] for r in reversed(s.trace.records) if r["kind"] in ("estable", "fallo", "limite")), None)
        out.update({
            "time": t_s(obs["timeUs"]), "timeUs": obs["timeUs"], "situation": obs["situation"],
            "virtual": obs.get("recorrido", {}).get("virtualSituation"),
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

    def act(self, op: str, body: dict[str, Any]) -> dict[str, Any]:
        s = self.s
        if op == "cargar":
            self.load(body.get("ejemplo", self.key))
        elif op == "reiniciar":
            self.load(self.key)
        elif op == "opciones":
            self.options = normalize_options(body.get("options"))  # cambia el perfil efectivo: ejecución nueva
            self.load(self.key)
        elif op == "entrada":
            var = body["var"]
            s.manual_input({var: not s.z.values[var]})
            s.step_evolution() if body.get("paso") else s.step_external()
        elif op == "avanzar":
            s.advance_to(s.z.time + int(body["us"]))
        elif op == "evolucion":
            s.step_evolution()
        elif op == "estabilizar":
            s.run_to_stable()
        else:
            raise ValueError(f"operación desconocida: {op}")
        return {"model": self.model, "state": self.state()}


BANCO: Banco | None = None


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
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/estado":
            with BANCO.lock:
                self._json({"model": BANCO.model, "state": BANCO.state(),
                            "examples": [{"key": k, "title": v[0]} for k, v in EJEMPLOS.items()]})
        else:
            self._send(404, b"no encontrado", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/api/"):
            self._send(404, b"no encontrado", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        with BANCO.lock:
            try:
                self._json(BANCO.act(self.path[5:], body))
            except (DiagnosticError, RuntimeError, ValueError, KeyError) as exc:
                self._json({"error": str(exc), "model": BANCO.model, "state": BANCO.state()}, 400)

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


def main() -> None:
    global BANCO
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--abrir", action="store_true", help="abrir el navegador cuando el servidor esté listo")
    args = ap.parse_args()
    BANCO = Banco()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Banco de pruebas en {url}  (cierre esta ventana o pulse Ctrl+C para detenerlo)", flush=True)
    if args.abrir:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
