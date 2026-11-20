"""Mide el editor y el simulador de escritorio Qt a 1366 × 768."""
from argparse import ArgumentParser, ArgumentTypeError
from copy import copy, deepcopy
from cProfile import Profile
from hashlib import sha256
from itertools import combinations
from math import ceil
from pathlib import Path
from pstats import Stats
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter_ns
import platform
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.entorno_v2_e0 import GEMMA, RAIZ, SEGUNDO, TAMANO, archivo_referencia
from tools.entorno_v2_e0 import bombear, escribir_json, paso, play, ventana
from PySide6.QtCore import QPointF, qVersion
from escritorio.bloques import nuevo
from escritorio.diagrama import posiciones
from grafcet.canonical import digest
from grafcet.engine import Stimulus

METAS = {"abrir": 2000, "anadir_accion": 50, "mover_etapa": 50, "deshacer": 50, "paso": 20}


class Medidas:
    def __init__(self, perfil):
        self.perfil = perfil
        self.muestras = {}
        self.perfiles = {}

    def tomar(self, nombre, operacion, *args, **kwargs):
        perfil = self.perfiles.get(nombre)
        if self.perfil and perfil is None:
            perfil = self.perfiles[nombre] = Profile()
        if perfil:
            perfil.enable()
        try:
            inicio = perf_counter_ns()
            resultado = operacion(*args, **kwargs)
            bombear()
            ms = (perf_counter_ns() - inicio) / 1e6
        finally:
            if perfil:
                perfil.disable()
        self.muestras.setdefault(nombre, []).append(ms)
        return resultado

    def resumir(self):
        resultado = {}
        for nombre, ms in self.muestras.items():
            fila = {"mediana_ms": median(ms), "p90_ms": sorted(ms)[ceil(0.9 * len(ms)) - 1], "muestras_ms": ms}
            if nombre in self.perfiles:
                perfil = Stats(self.perfiles[nombre])
                fila["perfil"] = {"total_ms": perfil.total_tt * 1000, "top15": _funciones(perfil)}
            resultado[nombre] = fila
        return resultado


def _funciones(perfil):
    ordenadas = sorted(perfil.stats.items(), key=lambda fila: fila[1][3], reverse=True)
    top = []
    for (archivo, linea, nombre), (_, n, propio, acumulado, _) in ordenadas[:15]:
        ruta = Path(archivo)
        if ruta.is_relative_to(RAIZ):
            archivo = ruta.relative_to(RAIZ).as_posix()
        elif ruta.is_absolute():
            archivo = ruta.name
        top.append({"archivo": archivo, "linea": linea, "funcion": nombre, "llamadas": n,
                    "propio_ms": propio * 1000, "acumulado_ms": acumulado * 1000})
    return top


def _anadir(w, medir):
    e = w.edicion
    accion = next((a for a in e.ed.model["actions"] if e.accion_en_id(a["id"])), None)
    if accion is None:
        raise ValueError("El proyecto necesita una acción dibujada para medir suelta desde un borde")
    cajas = [e.accion_en_id(a["id"]) for a in e.acciones(accion["stepRef"])]
    caja = max((c for c in cajas if c), key=lambda c: c["rect"][0] + c["rect"][2])
    x, y, ancho, alto = caja["rect"]
    origen = QPointF(x + ancho, y + alto / 2)
    destino = origen + QPointF(50, 0)
    w.diagrama.centrar_en(origen)
    e.seleccionar([])
    antes = {b["id"] for b in e.ed.draft_actions()}
    e.prensar(origen)
    e.mover(destino)
    bombear()
    if not e.enlace or e.enlace.get("nueva") != "der":
        raise RuntimeError("El borde de la acción no inició el arrastre de una acción nueva")
    medir("anadir_accion", e.soltar, destino)
    if not any(b["id"] not in antes and b.get("etapa") == accion["stepRef"] for b in e.ed.draft_actions()):
        raise RuntimeError("La suelta no añadió una acción unida a la etapa")
    _historial(e, medir)


def _historial(e, medir):
    nuevo_estado = deepcopy(e.ed.presentation)
    if not medir("deshacer", e.deshacer) or e.ed.presentation == nuevo_estado:
        raise RuntimeError("Deshacer no retiró la acción añadida")
    if not medir("rehacer", e.rehacer) or e.ed.presentation != nuevo_estado:
        raise RuntimeError("Rehacer no recuperó la acción añadida")
    e.deshacer()
    bombear()


def _mover(w, medir, sid, delta):
    e = w.edicion
    antes = posiciones(e.M)[sid]
    origen = QPointF(*antes)
    destino = origen + delta
    w.diagrama.centrar_en(origen)
    e.seleccionar([])
    bombear()

    def arrastrar():
        e.prensar(origen)
        e.mover(destino)
        e.soltar(destino)

    medir("mover_etapa", arrastrar)
    if antes == posiciones(e.M)[sid]:
        raise RuntimeError(f"El arrastre no movió la etapa {e.nombres[sid]}: {e.mensaje}")
    e.deshacer()
    bombear()


def _equidistanciar(w, medir, sid, permitir_sin_cambio):
    e = w.edicion
    e.seleccionar([sid])
    bombear()
    movidos = medir("equidistanciar", e.equidistanciar, [sid])
    if movidos is None or (not movidos and not permitir_sin_cambio):
        raise RuntimeError(f"Equidistanciar la cadena de {e.nombres[sid]} no cambió posiciones: {e.mensaje}")
    if movidos:
        e.deshacer()
    bombear()


def _receptividad(w, medir):
    e = w.edicion
    tid = e.ed.model["transitions"][0]["id"]
    w.editar_condicion(tid)
    bombear()
    antes = e.texto_condicion(tid)
    soltar = w.props_activo().prog.lienzo.soltar
    if not medir("receptividad", soltar, (), nuevo("no")) or e.texto_condicion(tid) == antes:
        raise RuntimeError("Propiedades no cambió la receptividad")
    e.deshacer()
    e.seleccionar([])
    w.diagrama.ajustar()
    bombear()


def _situacion(vista):
    return vista.s.z.situation


def _estimulos(s):
    proximo = s.next_stimulus()
    if isinstance(proximo, Stimulus) and proximo.time > s.z.time:
        yield "avanzar", {"us": proximo.time - s.z.time}
    entradas = sorted(k for k, var in s.cm.variables.items() if var.role == "input" and var.type.kind == "bool")
    for cantidad in (1, 2):
        for grupo in combinations(entradas, cantidad):
            yield "fijar", {"cambios": {k: not s.z.values[k] for k in grupo}}


def _buscar_cambio(vista):
    """Busca hasta tres estímulos en sombra. El lote final se vuelve a ejecutar por Ventana."""
    antes = _situacion(vista)
    pendientes = [(vista, ())]
    intentos = 0
    for candidata, previos in pendientes:
        for op, args in _estimulos(candidata.s):
            if intentos == 256:
                return None
            intentos += 1
            prueba = copy(candidata)
            prueba.s = deepcopy(candidata.s, {id(candidata.s.cm): candidata.s.cm})
            prueba.act(op, args)
            if prueba.s.status != "pausada-estable":
                continue
            camino = (*previos, (op, args))
            if _situacion(prueba) != antes:
                return camino
            if len(camino) < 3:
                pendientes.append((prueba, camino))
    return None


def _entradas(texto):
    valores = {}
    for pareja in texto.split(","):
        nombre, separador, valor = pareja.partition("=")
        nombre, valor = nombre.strip(), valor.strip()
        if not separador or not nombre or valor not in ("0", "1"):
            raise ArgumentTypeError("Use nombres de entradas booleanas y valores 0 o 1, separados por comas")
        if nombre in valores:
            raise ArgumentTypeError(f"Entrada repetida: {nombre}")
        valores[nombre] = valor == "1"
    return valores


def _identificar_entradas(modelo, entradas):
    cambios = {}
    for nombre, valor in (entradas or {}).items():
        ids = [v["id"] for v in modelo["variables"]
               if v["name"] == nombre and v["role"] == "input" and v["type"]["kind"] == "bool"]
        if len(ids) != 1:
            raise ValueError(f"El nombre {nombre!r} debe identificar una única entrada booleana")
        cambios[ids[0]] = valor
    return cambios


def _pasos_simulacion(w, medir, pasos, periodico):
    cambios = []
    for _ in range(pasos):
        antes = _situacion(w.v)
        guion = (("avanzar", {"us": SEGUNDO}),) if periodico else _buscar_cambio(w.v)
        if not guion:
            return cambios, f"Solo se pudieron guionizar {len(cambios)} de {pasos} cambios de situación"
        for op, args in guion[:-1]:
            paso(w, op, **args)
            bombear()
        op, args = guion[-1]
        medir("paso", paso, w, op, **args)
        despues = _situacion(w.v)
        if antes == despues:
            raise RuntimeError(f"El paso {len(cambios) + 1} no cambió la situación")
        cambios.append({"estimulos": list(guion), "situacion": sorted(despues)})
    return cambios, None


def _simulacion(w, medir, pasos, periodico, entradas):
    medir("play", play, w)
    try:
        if entradas:
            paso(w, "fijar", cambios=entradas)
            bombear()
        resultado = _pasos_simulacion(w, medir, pasos, periodico)
    finally:
        if w.modo == "simular":
            medir("stop", w.a_ejecutar.trigger)
    if w.modo != "editar":
        raise RuntimeError("Stop no volvió a edición")
    return resultado


def _cadena_externa(w):
    e = w.edicion
    sin_cambios = None
    for cadena in e.ed.chains():
        sid = cadena[0]
        movidos = e.equidistanciar([sid])
        if movidos:
            e.deshacer()
            bombear()
            return sid
        if movidos == [] and sin_cambios is None:
            sin_cambios = sid
    if sin_cambios:
        return sin_cambios
    raise RuntimeError("No se encontró una cadena que se pueda equidistanciar")


def medir_proyecto(ruta, *, calentamientos=3, repeticiones=9, pasos=50, perfil=False, periodico=False, entradas=None):
    if calentamientos < 0 or repeticiones < 1 or pasos < 1:
        raise ValueError("Se requiere al menos una repetición y un paso de simulación")
    muestras = Medidas(perfil)
    calientes = Medidas(False)
    cadena = None
    with ventana() as w:
        total = calentamientos + repeticiones
        for i in range(total):
            medir = (calientes if i < calentamientos else muestras).tomar
            if not medir("abrir", w.abrir_ruta, ruta):
                raise RuntimeError(f"No se pudo abrir {ruta}")
            e = w.edicion
            sid = e.ed.model["steps"][0]["id"]
            if cadena is None:
                iniciales = _identificar_entradas(e.ed.model, entradas)
                if ruta == GEMMA:
                    cadena = next(s["id"] for s in e.ed.model["steps"] if s["label"] == "100")
                else:
                    cadena = sid if periodico else _cadena_externa(w)
                fuente = {"revision_modelo": e.ed.revision, "sha256_presentacion": digest(e.ed.presentation),
                          "etapas": len(e.ed.model["steps"]), "transiciones": len(e.ed.model["transitions"]),
                          "acciones": len(e.ed.model["actions"]), "parciales": len(e.ed.model["partials"]),
                          "etapa_arrastrada": e.nombres[sid], "cadena_equidistanciada": e.nombres[cadena]}
                if ruta == GEMMA:
                    fuente["sha256_archivo"] = sha256(GEMMA.read_bytes()).hexdigest()
            _anadir(w, medir)
            _mover(w, medir, sid, QPointF(-80, 0))
            _equidistanciar(w, medir, cadena, permitir_sin_cambio=not periodico)
            _receptividad(w, medir)
            pasos_vuelta = 0
            if i == calentamientos - 1:
                pasos_vuelta = min(10, pasos)
            elif i == total - 1:
                pasos_vuelta = pasos
            cambios, motivo = _simulacion(w, medir, pasos_vuelta, periodico, iniciales)
    simulacion = {"estado": ("parcial" if cambios else "no medida") if motivo else "medida",
                  "solicitados": pasos, "medidos": len(cambios), "entradas": entradas or {}}
    if motivo:
        simulacion["motivo"] = motivo
    return {"fuente": fuente, "operaciones": muestras.resumir(), "cambios_situacion": cambios, "simulacion": simulacion}


def tabla(proyectos):
    lineas = ["| Proyecto | Operación | n | Mediana (ms) | P90 (ms) | Meta (ms) |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for proyecto, datos in proyectos.items():
        for operacion, fila in datos["operaciones"].items():
            n = len(fila["muestras_ms"])
            meta = f"< {METAS[operacion]}" if operacion in METAS else "—"
            lineas.append(
                f"| {proyecto} | {operacion} | {n} | {fila['mediana_ms']:.2f} | {fila['p90_ms']:.2f} | {meta} |"
            )
        if "paso" not in datos["operaciones"]:
            lineas.append(f"| {proyecto} | paso (no medido) | 0 | — | — | < {METAS['paso']} |")
    for proyecto, datos in proyectos.items():
        sim = datos["simulacion"]
        if sim.get("motivo"):
            lineas.extend(("", f"**{proyecto}** · Simulación {sim['estado']}. {sim['motivo']}."))
    return "\n".join(lineas) + "\n"


def tabla_perfiles(proyectos):
    lineas = ["", "## Perfil por operación"]
    for proyecto, datos in proyectos.items():
        for operacion, fila in datos["operaciones"].items():
            lineas.extend((
                "", f"### {proyecto} · {operacion}", "",
                "| Función | Origen | Llamadas | Tiempo propio (ms) | Tiempo acumulado (ms) |",
                "| --- | --- | ---: | ---: | ---: |",
            ))
            for f in fila["perfil"]["top15"]:
                origen = f"{f['archivo']}:{f['linea']}" if f["linea"] else f["archivo"]
                lineas.append(f"| `{f['funcion']}` | `{origen}` | {f['llamadas']} | "
                              f"{f['propio_ms']:.2f} | {f['acumulado_ms']:.2f} |")
    return "\n".join(lineas) + "\n"


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", action="store_true")
    parser.add_argument("--proyecto", type=Path)
    parser.add_argument("--entradas", type=_entradas, metavar="NOMBRE=1,OTRO=0",
                        help="entradas booleanas fijadas juntas tras Play, antes de medir los pasos")
    parser.add_argument("--salida", type=Path, default=RAIZ / "artifacts" / "v2_e0" / "medidas")
    args = parser.parse_args()
    if args.entradas and not args.proyecto:
        parser.error("--entradas requiere --proyecto")
    with TemporaryDirectory(prefix="rendimiento-e0-") as carpeta:
        fuentes = [(args.proyecto.resolve(), False)] if args.proyecto else [
            (GEMMA, True), (archivo_referencia(Path(carpeta)), True),
        ]
        proyectos = {}
        for ruta, periodico in fuentes:
            print(f"Midiendo {ruta.stem}…", flush=True)
            proyectos[ruta.stem] = medir_proyecto(
                ruta, perfil=args.perfil, periodico=periodico or ruta == GEMMA, entradas=args.entradas,
            )
    args.salida.mkdir(parents=True, exist_ok=True)
    nombre = "rendimiento_perfil" if args.perfil else "rendimiento"
    datos = {"entorno": {"ventana_px": TAMANO, "qt": qVersion(), "python": platform.python_version(),
                         "sistema": platform.system(), "procesador": platform.processor()},
             "perfil": args.perfil, "calentamientos_edicion": 3, "calentamientos_paso": 10,
             "metas_mediana_ms": METAS, "proyectos": proyectos}
    resumen = tabla(proyectos)
    escribir_json(args.salida / f"{nombre}.json", datos)
    markdown = resumen + tabla_perfiles(proyectos) if args.perfil else resumen
    (args.salida / f"{nombre}.md").write_text(markdown, encoding="utf-8", newline="\n")
    print(resumen)


if __name__ == "__main__":
    main()
