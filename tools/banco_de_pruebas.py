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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grafcet.diagnostics import DiagnosticError  # noqa: E402
from grafcet.examples import EJEMPLOS  # noqa: E402  (ejemplos y vista: los mismos que el simulador de escritorio)
from grafcet.profile import SEMANTIC_OPTIONS, normalize_options  # noqa: E402
from grafcet.view import Vista, describe, norm, t_s  # noqa: E402,F401

from decisiones import CATALOGO, POR_ID, RESPUESTAS_HOJA_08, RESPUESTAS_INCORPORADAS  # noqa: E402

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

    def comment(self, did: str, comment: str) -> None:
        """Guarda solo el comentario; si aún no hay elección, la entrada queda sin elegir (eleccion = None)."""
        d = POR_ID[did]
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            doc = nuevo_registro()
        entry = doc["decisiones"].setdefault(did, {"eleccion": None, "texto": "Sin elegir", "pregunta": d.title,
                                                   "origen": "comparador", "fecha": date.today().isoformat()})
        entry["comentario"] = comment.strip()
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
            "applied": RESPUESTAS_INCORPORADAS.get(d.id),
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
        elif op == "comentar":
            self.comment(body["id"], body.get("comentario", ""))
            return {"ok": True}
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
