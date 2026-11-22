"""Prueba de choque de la conexión de E/S (V2-E7, paso 4).

Una ventana real conectada por Modbus a un servidor de prueba local (el de `tools/medir_ciclo_es.py`) y operaciones al azar, con semilla
fija, entre el hilo de control del ciclo, la pantalla y el motor:

  conectar y desconectar, Play, Stop y Reiniciar, editar y deshacer con la conexión viva, cambiar el mapa de E/S en vivo,
  abrir otro proyecto, cortar y restaurar la red del servidor, y cerrar la ventana con todo en marcha (se vuelve a abrir otra).

Con la guarda de hilos (`GRAFCONNECT_COMPROBAR_HILOS=1`, que esta herramienta activa) y un vigilante de cuelgues (`faulthandler`), tras cada
operación se comprueba:

  CON-1  ninguna excepción sin atender: ni en las operaciones (salvo avisos de la propia interfaz), ni en el hilo de control
         (`al_error`), ni en ningún otro hilo (`threading.excepthook`);
  CON-2  el hilo de control vive si y solo si hay conexión (con un margen de espera);
  CON-3  al cerrar la ventana no queda ningún hilo nuevo vivo (ni `control-es` ni el trabajador de red);
  CON-4  ninguna operación tarda más del tope (cuelgue): se vuelca la traza de todos los hilos y se sale con error.

La secuencia se guarda como datos y se puede repetir. Uso:

  python -X faulthandler tools/choque_conexion.py --proyecto gemma --semilla 13 --ops 300
  python -X faulthandler tools/choque_conexion.py --proyecto linea --semilla 13 --ops 60
  python -X faulthandler tools/choque_conexion.py --reproducir fallo.json

Solo ejecuta el programa; escribe únicamente el informe de fallo (artifacts/v2_e7/choque_conexion/).
"""
from argparse import ArgumentParser
from pathlib import Path
from random import Random
from shutil import copyfile
from tempfile import TemporaryDirectory
from time import perf_counter, sleep
from unittest.mock import patch
import faulthandler
import json
import os
import sys
import threading
import traceback

os.environ["GRAFCONNECT_COMPROBAR_HILOS"] = "1"
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.medir_ciclo_es as medida  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

SALIDA = Path(__file__).resolve().parents[1] / "artifacts" / "v2_e7" / "choque_conexion"
PESOS = (("conectar", 6), ("desconectar", 4), ("play", 5), ("stop", 4), ("reiniciar", 3), ("editar", 5), ("deshacer", 3),
         ("mapa", 3), ("abrir_otro", 2), ("cortar_red", 2), ("restaurar_red", 2), ("esperar", 4), ("cerrar_y_reabrir", 1))
EDICIONES = ("anadir_etapa", "anadir_transicion", "renombrar", "condicion", "borrar", "mover", "comentario")
TOPE_OPERACION_S = 90


class Fallo(Exception):
    def __init__(self, tipo, detalle, indice=None):
        super().__init__(f"{tipo}: {detalle}")
        self.tipo, self.detalle, self.indice = tipo, detalle, indice


def generar(semilla, n):
    azar = Random(semilla)
    nombres = [x for x, p in PESOS for _ in range(p)]
    return [{"op": azar.choice(nombres), "k": azar.randrange(10**6), "k2": azar.randrange(10**6), "v": azar.randrange(10**6),
             "dx": azar.randrange(-15, 16) * 20, "dy": azar.randrange(-15, 16) * 20, "espera": azar.choice((0.0, 0.05, 0.2, 0.6, 1.2))}
            for _ in range(n)]


def bombear(segundos):
    fin = perf_counter() + segundos
    while True:
        QApplication.processEvents()
        if perf_counter() >= fin:
            return
        sleep(0.002)


class Banco:
    """La ventana, el servidor y el registro de lo que sale mal en otros hilos."""

    def __init__(self, proyecto, tmp):
        self.proyecto = proyecto
        self.tmp = tmp
        self.rutas = {"gemma": Path(tmp) / "gemma.grafnet", "linea": Path(tmp) / "linea.grafnet"}  # copias: el mapa en vivo se guarda en el proyecto
        copyfile(medida.GEMMA, self.rutas["gemma"])
        copyfile(medida.LINEA, self.rutas["linea"])
        self.servidor = medida.Servidor()
        self.errores: list[str] = []
        self.w = None
        self.base: set[int] = set()
        self.ventanas = 0

    def __enter__(self):
        self.servidor.__enter__()
        self.hook = threading.excepthook
        threading.excepthook = lambda a: self.errores.append(f"hilo {a.thread.name if a.thread else '?'}: " + "".join(
            traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback, limit=6)))
        self.base = {t.ident for t in threading.enumerate()}
        self.abrir_ventana()
        return self

    def __exit__(self, *_):
        try:
            self.cerrar_ventana()
        finally:
            threading.excepthook = self.hook
            self.servidor.__exit__()

    def abrir_ventana(self):
        from escritorio.ventana import Ventana
        self.ventanas += 1
        self.w = w = Ventana(QSettings(str(Path(self.tmp) / f"ajustes{self.ventanas}.ini"), QSettings.Format.IniFormat))
        original = w.ciclo.al_error

        def al_error(exc):
            self.errores.append("al_error del hilo de control: " + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=6)))
            original(exc)
        w.ciclo.al_error = al_error
        w.show()
        self.cargar(self.proyecto)

    def cargar(self, proyecto):
        self.proyecto = proyecto
        w = self.w
        if w.edicion is not None:
            w.edicion.ed.dirty = False
        if w.modbus.activo:
            w._desconectar_modbus()
        self.servidor.cortada = False
        anterior = (medida.LINEA, medida.GEMMA)
        medida.LINEA, medida.GEMMA = self.rutas["linea"], self.rutas["gemma"]
        try:
            medida.cargar_proyecto(w, proyecto, self.servidor, 10)
        finally:
            medida.LINEA, medida.GEMMA = anterior
        w.edicion.confirmar_borrado = lambda plan: True

    def cerrar_ventana(self):
        w, self.w = self.w, None
        if w is None:
            return
        if w.edicion is not None:
            w.edicion.ed.dirty = False
        w.close()
        w.deleteLater()
        fin = perf_counter() + 5
        vivos = []
        while perf_counter() < fin:
            QApplication.processEvents()
            vivos = [t for t in threading.enumerate() if t.ident not in self.base and t.is_alive()]
            if not vivos:
                return
            sleep(0.05)
        raise Fallo("CON-3", "hilos vivos tras cerrar la ventana: " + ", ".join(t.name for t in vivos))


def aviso_de_interfaz(exc):
    """Una operación que la propia interfaz rechaza con un aviso (por ejemplo, Play de un grafcet que no compila)."""
    return isinstance(exc, (RuntimeError, ValueError)) and "—" in str(exc)


def operacion(b, r):
    w, op = b.w, r["op"]
    if op == "conectar":
        if not w.modbus.activo:
            w._conectar_modbus()
    elif op == "desconectar":
        w._desconectar_modbus()
    elif op == "play":
        e = w.edicion
        while w.modo != "simular" and e is not None and e.ed.undo_stack and not e.ed.validate().can_simulate:  # deshace hasta un estado simulable
            e.deshacer()
        w.a_ejecutar.setChecked(True)
    elif op == "stop":
        w.a_ejecutar.setChecked(False)
    elif op == "reiniciar":
        if w.a_reiniciar.isEnabled():
            w.a_reiniciar.trigger()
    elif op in ("editar", "deshacer"):
        if w.modo == "simular":
            w.a_ejecutar.setChecked(False)
        if w.modo == "simular" or w.edicion is None:
            return
        from tools import choque_escena as ce
        reg = dict(r)
        reg["op"] = "deshacer" if op == "deshacer" else EDICIONES[r["v"] % len(EDICIONES)]
        ce.aplicar(w, reg)
    elif op == "mapa":
        config = w.panel_es.obtener()
        por_area: dict[str, list] = {}
        for s in config.senales:
            por_area.setdefault(s.area, []).append(s)
        areas = [a for a in sorted(por_area) if len(por_area[a]) >= 2]
        if areas:
            lista = por_area[areas[r["k"] % len(areas)]]
            i, j = r["k2"] % len(lista), (r["k2"] // 7 + 1) % len(lista)
            if i != j:
                lista[i].direccion, lista[j].direccion = lista[j].direccion, lista[i].direccion
                w._persistir_mapa_modbus(config)
    elif op == "abrir_otro":
        b.cargar("linea" if b.proyecto == "gemma" else "gemma")
    elif op == "cortar_red":
        b.servidor.cortada = True
    elif op == "restaurar_red":
        b.servidor.cortada = False
    elif op == "cerrar_y_reabrir":
        w.a_ejecutar.setChecked(True)
        b.cerrar_ventana()
        b.abrir_ventana()
    bombear(r["espera"])


def comprobar(b, momento):
    if b.errores:
        raise Fallo("CON-1", f"{momento}: " + b.errores[0])
    w = b.w
    fin = perf_counter() + 3
    while True:
        QApplication.processEvents()
        activo, vivo = bool(w.modbus.activo), bool(w.ciclo.vivo)
        if activo == vivo:
            break
        if perf_counter() > fin:
            raise Fallo("CON-2", f"{momento}: la conexión {'activa' if activo else 'inactiva'} y el hilo de control {'vivo' if vivo else 'parado'}")
        sleep(0.02)
    if b.errores:
        raise Fallo("CON-1", f"{momento}: " + b.errores[0])


AVISOS: list[str] = []


def _aviso(_, titulo, mensaje, *args, **kwargs):
    """Los avisos de la interfaz (no se puede simular, etc.) se cuentan y se aceptan: no son fallos."""
    AVISOS.append(f"{titulo} — {mensaje}")
    return QMessageBox.StandardButton.Ok


def ejecutar(proyecto, secuencia, verbose=False):
    try:
        return _ejecutar(proyecto, secuencia, verbose)
    except Fallo as f:  # (un fallo al cerrar el banco, al salir del `with`)
        return f


def _ejecutar(proyecto, secuencia, verbose):
    QApplication.instance() or QApplication([])
    with (patch.object(QMessageBox, "warning", _aviso), patch.object(QMessageBox, "critical", _aviso),
          patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok),
          patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard),
          TemporaryDirectory(prefix="choque-conexion-") as tmp):
        with Banco(proyecto, tmp) as b:
            for i, r in enumerate(secuencia):
                faulthandler.dump_traceback_later(TOPE_OPERACION_S, exit=True)  # CON-4
                try:
                    try:
                        operacion(b, r)
                    except Fallo as f:
                        f.indice = i
                        return f
                    except Exception as exc:  # noqa: BLE001
                        if not aviso_de_interfaz(exc):
                            return Fallo("EXC", f"{r['op']}: {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=6)}", i)
                    try:
                        comprobar(b, f"tras {r['op']}")
                    except Fallo as f:
                        f.indice = i
                        return f
                finally:
                    faulthandler.cancel_dump_traceback_later()
                if verbose:
                    print(i, r["op"], b.w.modbus.estado, flush=True)
            try:  # el final: todo en marcha y se cierra la ventana
                faulthandler.dump_traceback_later(TOPE_OPERACION_S, exit=True)
                if not b.w.modbus.activo:
                    b.w._conectar_modbus()
                    bombear(1.0)
                b.w.a_ejecutar.setChecked(True)
                bombear(0.5)
                b.cerrar_ventana()
            except Fallo as f:
                f.indice = len(secuencia)
                return f
            finally:
                faulthandler.cancel_dump_traceback_later()
    return None


def main():
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--proyecto", choices=("gemma", "linea"), default="gemma")
    ap.add_argument("--semilla", type=int, default=13)
    ap.add_argument("--ops", type=int, default=100)
    ap.add_argument("--reproducir", type=Path)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.reproducir:
        datos = json.loads(args.reproducir.read_text(encoding="utf-8"))
        proyecto, semilla, secuencia = datos["proyecto"], datos["semilla"], datos["secuencia"]
    else:
        proyecto, semilla, secuencia = args.proyecto, args.semilla, generar(args.semilla, args.ops)
    inicio = perf_counter()
    f = ejecutar(proyecto, secuencia, args.verbose)
    dur = perf_counter() - inicio
    if f is None:
        print(f"{proyecto} semilla {semilla}: {len(secuencia)} operaciones, sin fallos ({dur:.0f} s); avisos de la interfaz aceptados: {len(AVISOS)}")
        return 0
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / f"fallo_{proyecto}_{semilla}.json"
    ruta.write_text(json.dumps({"proyecto": proyecto, "semilla": semilla, "tipo": f.tipo, "indice": f.indice, "detalle": f.detalle,
                                "secuencia": secuencia}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    op = secuencia[f.indice]["op"] if f.indice is not None and f.indice < len(secuencia) else "cierre"
    print(f"{proyecto} semilla {semilla}: FALLO {f.tipo} en la operación {f.indice} ({op})\n{f.detalle}\n-> {ruta}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
