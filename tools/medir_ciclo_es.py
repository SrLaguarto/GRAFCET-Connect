"""Mide el ciclo de E/S por Modbus con la ventana real (V2-E7, paso 0): con un servidor de prueba local que apunta la hora de cada lectura y escritura.

Por cada proyecto, periodo y condición da:
  - intervalo entre lecturas (las del primer bloque de cada ciclo, función 2): mediana, P95 y máximo, en ms;
  - `leer_espera_ms` y `escribir_espera_ms` (lo que pasa entre que la red termina y la ventana lo atiende): mediana, P95 y máximo;
  - `ciclo_ms` (de que empieza la lectura a que termina la escritura): mediana, P95 y máximo;
  - cuántos refrescos y cuántos dibujos hizo la ventana, para saber que hubo dibujo (o que no lo hubo).

Proyectos: `linea` (`artifacts/escena_larga/Linea larga (Modbus).grafnet`, con su mapa) y `gemma` (la guía GEMMA con un mapa de prueba: una señal por
variable booleana de entrada y de salida). Condiciones: `sin_dibujo` (la página de E/S a la vista: no se redibuja el GRAFCET), `con_dibujo` (el
GRAFCET a la vista, con las entradas cambiando) y `con_carga` (como la anterior y con un proceso de cálculo por núcleo en otros procesos).
El servidor cambia entradas al azar cada 50 ms (menos Paro y Seta emergencia, que se quedan a 1) para que la situación cambie y haya dibujo.

  python tools/medir_ciclo_es.py --humo                                  # una prueba rápida, 3 s
  python tools/medir_ciclo_es.py --salida artifacts/v2_e7/medidas        # todo: 2 proyectos x 3 periodos x 3 condiciones x 10 s
  python tools/medir_ciclo_es.py --proyectos linea --periodos 10 --condiciones con_dibujo --segundos 20
"""
from argparse import SUPPRESS as argparse_suppress, ArgumentParser
from pathlib import Path
from random import Random
from statistics import median
import json
import os
import socketserver
import struct
import subprocess
import sys
import tempfile
import threading
import time

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

LINEA = RAIZ / "artifacts" / "escena_larga" / "Linea larga (Modbus).grafnet"
GEMMA = RAIZ / "tests" / "fixtures" / "referencia" / "guia_gemma.grafnet"
PROTEGIDAS = ("Paro", "Seta emergencia")  # contactos normalmente cerrados: a 1 siempre
CONDICIONES = ("sin_dibujo", "con_dibujo", "con_carga")


class Servidor:
    """Un esclavo Modbus mínimo: coils, entradas discretas y registros en memoria; apunta (hora, función) de cada petición."""

    def __init__(self, protegidas: set[int] | None = None, semilla: int = 7) -> None:
        self.coils = bytearray(65536)
        self.discretas = bytearray(65536)
        self.registros = [0] * 65536
        self.peticiones: list[tuple[float, int, int]] = []  # (hora, función, dirección)
        self.escrituras: list[tuple[float, int]] = []
        self.protegidas = protegidas or set()
        self.activas: list[int] = []  # direcciones de entradas discretas que cambia el servidor
        self.azar = Random(semilla)
        self._parar = threading.Event()
        servidor = self

        class Manejador(socketserver.BaseRequestHandler):
            def handle(self):
                def recibir(n):
                    datos = b""
                    while len(datos) < n:
                        try:
                            parte = self.request.recv(n - len(datos))
                        except OSError:
                            return None
                        if not parte:
                            return None
                        datos += parte
                    return datos
                self.request.setsockopt(6, 1, 1)  # TCP_NODELAY
                while True:
                    cabecera = recibir(7)
                    if cabecera is None:
                        return
                    tid, _, n, unidad = struct.unpack(">HHHB", cabecera)
                    pdu = recibir(n - 1)
                    if pdu is None:
                        return
                    respuesta = servidor.responder(pdu)
                    try:
                        self.request.sendall(struct.pack(">HHHB", tid, 0, len(respuesta) + 1, unidad) + respuesta)
                    except OSError:
                        return

        class Escucha(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.srv = Escucha(("127.0.0.1", 0), Manejador)
        self.puerto = self.srv.server_address[1]
        self.hilos = [threading.Thread(target=self.srv.serve_forever, daemon=True), threading.Thread(target=self._cambiar, daemon=True)]

    def responder(self, pdu: bytes) -> bytes:
        ahora = time.perf_counter()
        f = pdu[0]
        if f in (1, 2):
            d, c = struct.unpack(">HH", pdu[1:5])
            self.peticiones.append((ahora, f, d))
            fuente = self.coils if f == 1 else self.discretas
            n = (c + 7) // 8
            datos = bytearray(n)
            for i in range(c):
                if fuente[d + i]:
                    datos[i // 8] |= 1 << (i % 8)
            return bytes([f, n]) + bytes(datos)
        if f in (3, 4):
            d, c = struct.unpack(">HH", pdu[1:5])
            self.peticiones.append((ahora, f, d))
            return bytes([f, 2 * c]) + struct.pack(f">{c}H", *self.registros[d:d + c])
        if f == 15:
            d, c = struct.unpack(">HH", pdu[1:5])
            self.escrituras.append((ahora, f))
            for i in range(c):
                self.coils[d + i] = 1 if pdu[6 + i // 8] & (1 << (i % 8)) else 0
            return pdu[:5]
        if f == 16:
            d, c = struct.unpack(">HH", pdu[1:5])
            self.escrituras.append((ahora, f))
            self.registros[d:d + c] = list(struct.unpack(f">{c}H", pdu[6:6 + 2 * c]))
            return pdu[:5]
        if f == 5:
            self.escrituras.append((ahora, f))
            self.coils[struct.unpack(">H", pdu[1:3])[0]] = 1 if pdu[3] else 0
            return pdu
        return bytes([f | 0x80, 1])

    def _cambiar(self):
        """Cada 50 ms cambia una entrada discreta al azar: la situación cambia y la ventana tiene algo que dibujar."""
        while not self._parar.wait(0.05):
            if self.activas:
                d = self.azar.choice(self.activas)
                self.discretas[d] ^= 1

    def __enter__(self):
        for h in self.hilos:
            h.start()
        return self

    def __exit__(self, *_):
        self._parar.set()
        self.srv.shutdown()
        self.srv.server_close()


    def configurar(self) -> None:
        """(Sin efecto aquí: el servidor está en este proceso y `activas` y `discretas` ya se han puesto.)"""

    def recoger(self) -> list[tuple[float, int, int]]:
        return list(self.peticiones)


class ServidorAparte:
    """El mismo servidor, pero en otro proceso (como el simulador de planta de verdad): no comparte el GIL con la ventana. Se arranca con
    `python medir_ciclo_es.py --servir`, que imprime el puerto, espera una línea con las entradas que debe cambiar y, al cerrarse su entrada, devuelve
    las peticiones con su hora (`perf_counter` es el mismo reloj del sistema en los dos procesos)."""

    def __init__(self) -> None:
        self.activas: list[int] = []
        self.discretas: dict[int, int] = {}
        self.peticiones: list = []
        self.escrituras: list = []

    def __enter__(self):
        self.proceso = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "--servir"], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, text=True, cwd=str(RAIZ))
        self.puerto = int(self.proceso.stdout.readline())
        return self

    def configurar(self) -> None:
        self.proceso.stdin.write(json.dumps({"activas": self.activas, "altas": [d for d, v in self.discretas.items() if v]}) + "\n")
        self.proceso.stdin.flush()

    def recoger(self) -> list[tuple[float, int, int]]:
        if self.proceso.poll() is None:
            self.proceso.stdin.close()
            datos = json.loads(self.proceso.stdout.read())
            self.proceso.wait(timeout=10)
            self.peticiones = [tuple(x) for x in datos["peticiones"]]
        return self.peticiones

    def __exit__(self, *_):
        if self.proceso.poll() is None:
            self.proceso.kill()


def servir() -> int:
    """El proceso del servidor aparte (ver `ServidorAparte`)."""
    with Servidor() as s:
        print(s.puerto, flush=True)
        cfg = json.loads(sys.stdin.readline())
        s.activas = cfg["activas"]
        for d in cfg["altas"]:
            s.discretas[d] = 1
        sys.stdin.read()  # hasta que el que mide cierre la entrada
        print(json.dumps({"peticiones": s.peticiones}), flush=True)
    return 0


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[int(p * (len(ordenados) - 1))] if ordenados else float("nan")


def resumen(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0}
    return {"n": len(valores), "mediana": round(median(valores), 3), "p95": round(percentil(valores, 0.95), 3), "max": round(max(valores), 3)}


class Registro(dict):
    """`Coordinador.medidas` que además guarda cada valor que se le asigna (la clase solo guarda el último)."""

    def __init__(self, *a, historia=None, **k):
        super().__init__(*a, **k)
        self.historia = historia if historia is not None else {}

    def __setitem__(self, clave, valor):
        self.historia.setdefault(clave, []).append(valor)
        super().__setitem__(clave, valor)


def instalar_registro():
    from conexion.coordinador import Coordinador
    historia: dict[str, list[float]] = {}

    def leer(self):
        return self.__dict__["_medidas_reg"]

    def poner(self, valor):
        self.__dict__["_medidas_reg"] = Registro(valor, historia=historia)
    Coordinador.medidas = property(leer, poner)
    return historia


def cargar_proyecto(w, proyecto: str, servidor: Servidor, periodo: int):
    """Abre el proyecto en la ventana y deja la conexión Modbus apuntando al servidor de prueba, sin conectar todavía."""
    from conexion.configuracion import Configuracion, Senal
    if proyecto == "linea":
        assert w.abrir_ruta(LINEA), "no se pudo abrir Linea larga (Modbus)"
        config = w.panel_es.obtener()
    else:
        assert w.abrir_ruta(GEMMA), "no se pudo abrir GEMMA"
        variables = w.edicion.ed.model["variables"]
        senales, di, co = [], 0, 0
        for v in variables:
            if v["type"]["kind"] != "bool":
                continue
            if v["role"] == "input":
                senales.append(Senal(v["id"], "discrete", di))
                di += 1
            elif v["role"] == "output":
                senales.append(Senal(v["id"], "coil", co))
                co += 1
        config = Configuracion(senales=senales)
    config.host, config.puerto, config.periodo_ms, config.modo = "127.0.0.1", servidor.puerto, periodo, "modbus"
    nombre = {v["id"]: v["name"] for v in w.edicion.ed.model["variables"]}  # (las señales llevan el ID de la variable)
    servidor.activas = [s.direccion for s in config.senales if s.area == "discrete" and nombre.get(s.variable) not in PROTEGIDAS]
    for s in config.senales:
        if s.area == "discrete" and nombre.get(s.variable) in PROTEGIDAS:
            servidor.discretas[s.direccion] = 1
    w.panel_es.cargar(w.edicion.ed.model, config)
    return config


def medir(proyecto: str, periodo: int, condicion: str, segundos: float, calentamiento: float = 1.0, aparte: bool = False) -> dict:
    from PySide6.QtCore import QEventLoop, QSettings, QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    historia = instalar_registro()
    from escritorio.ventana import Ventana
    cargas = []
    with tempfile.TemporaryDirectory() as tmp, (ServidorAparte() if aparte else Servidor()) as servidor:
        w = Ventana(QSettings(str(Path(tmp) / "ajustes.ini"), QSettings.Format.IniFormat))
        cuenta = {"refrescos": 0, "dibujos": 0}
        try:
            cargar_proyecto(w, proyecto, servidor, periodo)
            servidor.configurar()
            w.show()
            original_refrescar, original_mostrar = w.refrescar, w.diagrama.mostrar

            def refrescar(*a, **k):
                cuenta["refrescos"] += 1
                return original_refrescar(*a, **k)

            def mostrar(*a, **k):
                cuenta["dibujos"] += 1
                return original_mostrar(*a, **k)
            w.refrescar, w.diagrama.mostrar = refrescar, mostrar
            w._conectar_modbus()
            fin = time.monotonic() + 10
            while not (w.modbus.estado == "conectado" and w.modbus.futuro is None):
                app.processEvents()
                time.sleep(0.001)
                if time.monotonic() > fin:
                    raise RuntimeError("no conectó: " + w.modbus.mensaje)
            if condicion == "con_carga":
                for _ in range(max(2, os.cpu_count() or 2)):
                    cargas.append(subprocess.Popen([sys.executable, "-c", "while True: pass"]))
                time.sleep(0.3)
            w.a_ejecutar.setChecked(True)
            w._mostrar_pagina(condicion == "sin_dibujo")  # (después de Play: la página que se mide)
            bucle = QEventLoop()
            QTimer.singleShot(int((calentamiento + segundos) * 1000), bucle.quit)
            marca = time.perf_counter() + calentamiento
            QTimer.singleShot(int(calentamiento * 1000), lambda: (historia.clear(), servidor.peticiones.clear(), servidor.escrituras.clear(), cuenta.update(refrescos=0, dibujos=0)))
            bucle.exec()
            # un ciclo empieza siempre por la misma lectura (función y dirección): esa es la marca del ciclo
            vistas = [(t, f, d) for t, f, d in servidor.recoger() if t >= marca]
            lecturas = [t for t, f, d in vistas if vistas and (f, d) == (vistas[0][1], vistas[0][2])]
            intervalos = [(b - a) * 1000 for a, b in zip(lecturas, lecturas[1:])]
            return {"proyecto": proyecto, "periodo_ms": periodo, "condicion": condicion, "segundos": segundos,
                    "intervalo_entre_lecturas_ms": resumen(intervalos), "leer_espera_ms": resumen(historia.get("leer_espera_ms", [])),
                    "escribir_espera_ms": resumen(historia.get("escribir_espera_ms", [])), "ciclo_ms": resumen(historia.get("ciclo_ms", [])),
                    "refrescos": cuenta["refrescos"], "dibujos": cuenta["dibujos"], "pagina_es": bool(w.a_es.isChecked()), "lecturas": len(lecturas), "estado": w.modbus.estado, "mensaje": w.modbus.mensaje}
        finally:
            for c in cargas:
                c.kill()
            w.a_ejecutar.setChecked(False)
            if w.edicion is not None:
                w.edicion.ed.dirty = False
            try:
                w._desconectar_modbus()
            except Exception:  # noqa: BLE001  (limpieza: la medida ya está tomada)
                pass
            for _ in range(50):
                app.processEvents()
                time.sleep(0.002)
            w.close()
            w.deleteLater()
            app.processEvents()


def tabla(filas: list[dict]) -> str:
    cab = ("| Proyecto | Periodo | Condición | Intervalo mediana | P95 | máx. | leer_espera P95 | escribir_espera P95 | ciclo mediana | ciclo P95 | refrescos / dibujos |\n"
           "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    lineas = [cab]
    for f in filas:
        i, le, ee, ci = f["intervalo_entre_lecturas_ms"], f["leer_espera_ms"], f["escribir_espera_ms"], f["ciclo_ms"]
        g = lambda d, k: d.get(k, "–")  # noqa: E731
        lineas.append(f"| {f['proyecto']} | {f['periodo_ms']} ms | {f['condicion']} | {g(i, 'mediana')} | {g(i, 'p95')} | {g(i, 'max')} | {g(le, 'p95')} | "
                      f"{g(ee, 'p95')} | {g(ci, 'mediana')} | {g(ci, 'p95')} | {f['refrescos']} / {f['dibujos']} |")
    return "\n".join(lineas)


def main() -> int:
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--proyectos", default="linea,gemma")
    ap.add_argument("--periodos", default="5,10,20")
    ap.add_argument("--condiciones", default=",".join(CONDICIONES))
    ap.add_argument("--segundos", type=float, default=10)
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--servidor-aparte", action="store_true", help="el servidor de prueba en otro proceso (sin compartir el GIL con la ventana)")
    ap.add_argument("--servir", action="store_true", help=argparse_suppress)
    ap.add_argument("--humo", action="store_true", help="una sola medida corta de GEMMA a 10 ms, sin y con dibujo (para saber que funciona)")
    args = ap.parse_args()
    if args.servir:
        return servir()
    if args.humo:
        proyectos, periodos, condiciones, segundos = ["gemma"], [10], ["sin_dibujo", "con_dibujo"], 3.0
    else:
        proyectos, periodos = args.proyectos.split(","), [int(p) for p in args.periodos.split(",")]
        condiciones, segundos = args.condiciones.split(","), args.segundos
    filas = []
    for proyecto in proyectos:
        for periodo in periodos:
            for condicion in condiciones:
                fila = medir(proyecto, periodo, condicion, segundos, aparte=args.servidor_aparte)
                filas.append(fila)
                print(json.dumps({k: fila[k] for k in ("proyecto", "periodo_ms", "condicion", "intervalo_entre_lecturas_ms", "refrescos", "dibujos", "estado")}, ensure_ascii=False), flush=True)
    texto = tabla(filas)
    print("\n" + texto)
    if args.salida:
        args.salida.mkdir(parents=True, exist_ok=True)
        (args.salida / "ciclo_es.json").write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        (args.salida / "ciclo_es.md").write_text(texto + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
