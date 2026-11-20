"""Genera o compara las capturas del editor, el simulador y el visor web."""
from argparse import ArgumentParser
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import which
from subprocess import run
from tempfile import TemporaryDirectory
import json
import os
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.entorno_v2_e0 import FIXTURES, GEMMA, RAIZ, SEGUNDO, TAMANO, archivo_referencia
from tools.entorno_v2_e0 import bombear, escribir_json, paso, play, ventana
from grafcet.ejemplos_aula import DIDACTICOS
from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QColor, QImage, QPainter

ESTADOS = ("edicion", "etapa", "accion", "errores", "sim_00", "sim_03", "sim_10", "web")
ENTRADAS_AULA = {
    "aula_marcha": ({"marcha": True}, {}, {"paro": True}),
    "aula_eleccion": ({"izquierda": True}, {}, {"fin": True, "izquierda": False}),
    "aula_simultaneidad": ({"marcha": True}, {"fin_izq": True}, {"fin_der": True, "marcha": False}),
    "aula_macro": ({"marcha": True}, {}, {"fin": True, "marcha": False}),
    "aula_encapsulada": ({"marcha": True}, {"fin": True}, {"paro": True}),
    "aula_temporizacion": ({"marcha": True}, {}, {}),
    "aula_repeticion": ({"marcha": True}, {"avance": True}, {"repetir": True, "avance": False}),
}


@dataclass(frozen=True)
class Fuente:
    nombre: str
    clave: str | None = None
    ruta: Path | None = None


def _fuentes(temporal):
    yield Fuente("fixtures/" + GEMMA.relative_to(FIXTURES).with_suffix("").as_posix(), ruta=GEMMA)
    for clave in DIDACTICOS:
        yield Fuente(f"aula/{clave}", clave=clave)
    for ruta in sorted(FIXTURES.rglob("*.grafnet")):
        if ruta != GEMMA:
            yield Fuente("fixtures/" + ruta.relative_to(FIXTURES).with_suffix("").as_posix(), ruta=ruta)
    yield Fuente("generado/referencia_100", ruta=archivo_referencia(temporal))


def _guardar(imagen, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if imagen.isNull() or not imagen.save(str(ruta), "PNG"):
        raise OSError(f"No se pudo guardar la captura {ruta}")


def _qt(w, ruta):
    bombear()
    lienzo = w.diagrama.grab().toImage()
    imagen = QImage(*TAMANO, QImage.Format.Format_RGB32)
    imagen.fill(QColor("#f6f7f9"))
    with QPainter(imagen) as pintor:
        pintor.drawImage((imagen.width() - lienzo.width()) // 2, (imagen.height() - lienzo.height()) // 2, lienzo)
    _guardar(imagen, ruta)


def _ajustar(w):
    bombear()
    w.diagrama.ajustar()
    bombear()


def _edicion(w, carpeta, estados, omitidos):
    e = w.edicion
    _ajustar(w)
    if "edicion" in estados:
        _qt(w, carpeta / "edicion.png")
    etapa = next(iter(e.ed.model["steps"]), None)
    candidatos = [a["id"] for a in e.ed.model["actions"]] + [b["id"] for b in e.ed.draft_actions()]
    accion = next((aid for aid in candidatos if e.accion_en_id(aid)), None)
    for estado, ident in (("etapa", etapa["id"] if etapa else None), ("accion", accion)):
        if estado in estados and ident:
            e.seleccionar([ident])
            w.diagrama.centrar_seleccion()
            _qt(w, carpeta / f"{estado}.png")
        elif estado in estados:
            omitidos[estado] = "El proyecto carece de un elemento seleccionable de este tipo."
    e.seleccionar([])
    if "errores" in estados:
        w.b_errores.setChecked(True)
        _ajustar(w)
        _qt(w, carpeta / "errores.png")
        w.b_errores.setChecked(False)


def _simulacion(w, fuente, carpeta, estados, omitidos, navegador, temporal):
    pedidos = [n for n in (0, 3, 10) if f"sim_{n:02}" in estados]
    web = "web" in estados and navegador is not None
    if "web" in estados and not web:
        omitidos["web"] = "No se encontró un navegador compatible con la captura local en modo headless."
    if not pedidos and not web:
        return
    bloqueos = [d["message"] for d in w.edicion.diagnosticos() if d["blocks"]]
    if bloqueos:
        for n in pedidos:
            omitidos[f"sim_{n:02}"] = " | ".join(bloqueos)
        if web:
            _web(navegador, temporal, w.edicion.M, w.v.state(), carpeta / "web.png")
        return
    play(w)
    _ajustar(w)
    entradas = ENTRADAS_AULA.get(fuente.clave, ())
    ids = {v["name"]: v["id"] for v in w.v.doc["variables"] if v["role"] == "input"}
    for n in range(max([0, *pedidos, 3 if web else 0]) + 1):
        if n:
            if n <= len(entradas) and entradas[n - 1]:
                cambios = {ids[nombre]: valor for nombre, valor in entradas[n - 1].items()}
                paso(w, "fijar", cambios=cambios)
            else:
                paso(w, us=SEGUNDO)
        if n in pedidos:
            _qt(w, carpeta / f"sim_{n:02}.png")
        if n == 3 and web:
            _web(navegador, temporal, w.v.model, w.v.state(), carpeta / "web.png")
    w.a_ejecutar.trigger()
    bombear()


def _navegador():
    configurado = os.environ.get("GRAFCET_E0_NAVEGADOR")
    if configurado:
        ruta = Path(configurado).resolve(strict=True)
        if not ruta.is_file():
            raise ValueError("GRAFCET_E0_NAVEGADOR debe apuntar al ejecutable")
        return ruta
    candidatos = [Path(ruta) for nombre in ("chromium", "chromium-browser") if (ruta := which(nombre))]
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if directorio := os.environ.get(variable):
            candidatos.extend(Path(directorio) / ruta for ruta in (
                "Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe",
                "Chromium/Application/chrome.exe",
            ))
    return next((ruta for ruta in candidatos if ruta.is_file()), None)


def _web(navegador, temporal, modelo, estado, destino):
    # Página estática y CSP sin recursos remotos, incluso al dibujar etiquetas importadas.
    css = (RAIZ / "tools" / "dibujo.css").read_text(encoding="utf-8")
    dibujo = (RAIZ / "tools" / "dibujo.js").read_text(encoding="utf-8")
    datos = json.dumps([modelo, estado], ensure_ascii=True).replace("<", "\\u003c")
    ancho, alto = TAMANO
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'style-src \'unsafe-inline\'; script-src \'unsafe-inline\'">'
        f'<style>{css}\nhtml {{ color-scheme: light; }} '
        f'svg.grafcet {{ width: {ancho}px; height: {alto}px; }}</style>'
        '<svg id="lienzo" class="grafcet"></svg>'
        f'<script>{dibujo}\ndrawDiagram(document.getElementById("lienzo"), ...{datos});'
        'document.body.dataset.capturado = "ok";</script>'
    )
    pagina = temporal / "captura.html"
    pagina.write_text(html, encoding="utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    comando = [
        str(navegador), "--headless", "--disable-gpu", "--disable-background-networking",
        "--disable-component-update", "--disable-sync", "--disable-extensions", "--no-first-run",
        "--no-default-browser-check", "--host-resolver-rules=MAP * ~NOTFOUND", "--proxy-server=http://127.0.0.1:9",
        "--force-device-scale-factor=1", f"--window-size={ancho},{alto}", f"--user-data-dir={temporal / 'navegador'}",
        "--dump-dom", f"--screenshot={destino.resolve()}", pagina.as_uri(),
    ]
    proceso = run(comando, capture_output=True, timeout=45, check=False)
    imagen = QImage(str(destino))
    if proceso.returncode or b'data-capturado="ok"' not in proceso.stdout or imagen.size().toTuple() != TAMANO:
        detalle = proceso.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"El visor web no produjo la captura esperada de {destino.name}. {detalle}")


def _capturas(fuente, carpeta, estados, navegador, temporal):
    omitidos = {}
    with ventana() as w:
        if fuente.clave:
            w.cargar_ejemplo(fuente.clave)
        elif not w.abrir_ruta(fuente.ruta):
            raise RuntimeError(f"No se pudo abrir {fuente.ruta}")
        w.edicion.parpadeo.parar()
        if set(estados).intersection(ESTADOS[:4]):
            _edicion(w, carpeta, estados, omitidos)
        _simulacion(w, fuente, carpeta, estados, omitidos, navegador, temporal)
    metadatos = {"omitidos": omitidos}
    if fuente.ruta and fuente.ruta.is_relative_to(FIXTURES):
        metadatos["origen"] = fuente.ruta.relative_to(RAIZ).as_posix()
        metadatos["sha256_origen"] = _huella(fuente.ruta)
    return metadatos


def _huella(ruta):
    return sha256(ruta.read_bytes()).hexdigest()


def _inventario(carpeta):
    return {p.relative_to(carpeta).as_posix(): _huella(p) for p in sorted(carpeta.rglob("*.png"))}


def generar(carpeta, *, fuentes=None, estados=ESTADOS):
    """Las capturas pertenecen a una ejecución. Se exige una carpeta nueva o vacía."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    if any(carpeta.iterdir()):
        raise ValueError(f"El destino de las capturas debe estar vacío: {carpeta}")
    navegador = _navegador() if "web" in estados else None
    with TemporaryDirectory(prefix="imagenes-e0-") as tmp:
        temporal = Path(tmp)
        proyectos = {}
        for fuente in _fuentes(temporal) if fuentes is None else fuentes:
            try:
                proyectos[fuente.nombre] = _capturas(fuente, carpeta / fuente.nombre, estados, navegador, temporal)
            except (OSError, ValueError, RuntimeError) as exc:
                raise RuntimeError(f"No se pudo capturar {fuente.nombre}: {exc}") from exc
    manifiesto = {"ventana_px": TAMANO, "escala_dispositivo": 1, "qt": qVersion(), "proyectos": proyectos,
                  "imagenes": _inventario(carpeta)}
    escribir_json(carpeta / "manifiesto.json", manifiesto)
    return manifiesto


def _diferencia(a, b):
    izquierda, derecha = QImage(str(a)), QImage(str(b))
    ancho = max(izquierda.width(), derecha.width(), 1)
    alto = max(izquierda.height(), derecha.height(), 1)
    salida = QImage(ancho, alto, QImage.Format.Format_RGB32)
    salida.fill(QColor("#ff00ff"))
    if not izquierda.isNull() and not derecha.isNull():
        w, h = min(izquierda.width(), derecha.width()), min(izquierda.height(), derecha.height())
        with QPainter(salida) as pintor:
            pintor.drawImage(0, 0, izquierda.copy(0, 0, w, h))
            pintor.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
            pintor.drawImage(0, 0, derecha.copy(0, 0, w, h))
    return salida


def comparar(a, b, salida=None):
    a, b = Path(a).resolve(), Path(b).resolve()
    if not a.is_dir() or not b.is_dir():
        raise ValueError("Las dos carpetas de capturas deben existir")
    salida = Path(salida).resolve() if salida is not None else b.with_name(b.name + "_diferencias")
    if salida.is_relative_to(a) or salida.is_relative_to(b):
        raise ValueError("Las diferencias deben quedar fuera de las carpetas comparadas")
    previas, actuales = _inventario(a), _inventario(b)
    distintos = {n: "añadida" if n not in previas else "ausente" if n not in actuales else "modificada"
                 for n in sorted(previas.keys() | actuales.keys()) if previas.get(n) != actuales.get(n)}
    for nombre in distintos:
        _guardar(_diferencia(a / nombre, b / nombre), salida / nombre)
    return distintos


def main():
    parser = ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="modo", required=True)
    sub.add_parser("generar").add_argument("carpeta", type=Path)
    comparacion = sub.add_parser("comparar")
    comparacion.add_argument("a", type=Path)
    comparacion.add_argument("b", type=Path)
    comparacion.add_argument("--salida", type=Path)
    args = parser.parse_args()
    if args.modo == "generar":
        datos = generar(args.carpeta)
        print(f"{len(datos['imagenes'])} PNG en {args.carpeta}")
        for nombre, proyecto in datos["proyectos"].items():
            for estado, motivo in proyecto["omitidos"].items():
                print(f"{nombre}/{estado}: omitida. {motivo}")
        return 0
    distintas = comparar(args.a, args.b, args.salida)
    for nombre, estado in distintas.items():
        print(f"{nombre}: {estado}")
    print(f"{len(distintas)} imágenes distintas")
    return int(bool(distintas))


if __name__ == "__main__":
    sys.exit(main())
