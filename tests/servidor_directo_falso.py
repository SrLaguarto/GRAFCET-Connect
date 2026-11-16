"""Servidor HTTP local aislado para las pruebas de conexión directa."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread


class ServidorDirecto:
    def __init__(self, senales):
        self.senales = deepcopy(senales)
        self.peticiones = []
        self.error = 0
        self.no_json = False
        self.rechazar = set()
        estado = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                self.responder()

            def do_PUT(self):
                self.responder()

            def responder(self):
                cantidad = int(self.headers.get("Content-Length", 0))
                datos = json.loads(self.rfile.read(cantidad)) if cantidad else None
                estado.peticiones.append((self.command, self.path, datos))
                codigo = estado.error or 200
                respuesta = []
                if self.path == "/api/tags":
                    respuesta = estado.senales
                elif self.path == "/api/tag/values":
                    por_id = {s["id"]: s for s in estado.senales}
                    for elemento in datos or []:
                        identidad = elemento if isinstance(elemento, str) else elemento["id"]
                        senal = por_id.get(identidad)
                        if senal is None:
                            respuesta.append({"id": identidad, "code": 404, "error": "no encontrada"})
                        elif self.command == "PUT":
                            if senal["kind"].lower() == "input" or identidad in estado.rechazar:
                                respuesta.append({"id": identidad, "code": 406, "error": "señal de entrada"})
                            else:
                                senal["value"] = elemento["value"]
                                respuesta.append({"id": identidad, "value": senal["value"]})
                        else:
                            respuesta.append({"id": identidad, "value": senal.get("value", False)})
                else:
                    codigo = 404
                cuerpo = b"no es JSON" if estado.no_json else json.dumps(respuesta).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.servidor.daemon_threads = True
        self.puerto = self.servidor.server_port
        self.hilo = Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.hilo.join(timeout=2)


def senal(identidad, nombre, tipo="Bit", papel="Input", direccion=0, valor=False):
    return {"id": identidad, "name": nombre, "type": tipo, "kind": papel, "address": direccion,
            "value": valor, "openCircuit": False, "shortCircuit": False, "isForced": False,
            "forcedValue": False}
