"""Compatibilidad del `.grafnet` entre la 2.0 y la 1.x (V2-E6, regla 4 del plan): lo guardado por una se abre en la otra y el contenido es el mismo.

Para cada proyecto (los ejemplos del programa, los fixtures y GEMMA y Linea larga):

  1. la 2.0 guarda el proyecto (A) y la 1.x guarda el mismo proyecto (B), cada una con su propio código;
  2. cada versión abre A y B con su código y dice qué contiene (entradas del contenedor, huella del sello, firma, documentos);
  3. se comparan: el contenido que guardan las dos (entradas del ZIP menos los metadatos de fechas) y lo que cada una lee de lo que escribió la otra.

La 1.x **solo se ejecuta**, en subprocesos con `PYTHONDONTWRITEBYTECODE=1` y su carpeta como directorio de trabajo: no se escribe nada en ella.

  python tools/compatibilidad_grafnet.py --antigua C:/ruta/a/implementacion --salida artifacts/v2_e6/compatibilidad
"""
from argparse import ArgumentParser
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------------------------------------- trabajador
def trabajar(raiz: Path, orden: str, args: list[str]) -> dict:
    """Lo que ejecuta cada versión con su propio código: `crear`, `reguardar` y `leer`."""
    sys.path[0] = str(raiz)
    sys.dont_write_bytecode = True
    import copy
    from grafcet.contenedor import VERSION, SELLO, INFO, _leer_entradas, huella
    from grafcet.persistence import add_document, new_project
    from escritorio.proyecto_archivo import abrir_grafnet, guardar_grafnet
    from escritorio.sello import CLAVE, CLAVE_DESARROLLO, DESARROLLO
    if orden == "crear":
        from grafcet.editor import Editor
        from grafcet.examples import EJEMPLOS
        from grafcet.view import presentation_for
        clave, destino = args
        titulo, _, construir = EJEMPLOS[clave]
        m, layout = construir()
        doc = copy.deepcopy(m.doc)
        ed = Editor(doc, presentation_for(doc, layout))
        proyecto = new_project(ed.model["id"], titulo)
        add_document(proyecto, ed.model)
        add_document(proyecto, ed.presentation)
        guardar_grafnet(Path(destino), proyecto, CLAVE).cerrar()
        return {"ok": True}
    if orden == "reguardar":
        origen, destino = args
        abierto = abrir_grafnet(origen, CLAVE, "importar", None if DESARROLLO else CLAVE_DESARROLLO)
        try:
            guardar_grafnet(Path(destino), abierto.proyecto, CLAVE if abierto.sello_valido else None, abierto.raiz, None, abierto.info).cerrar()
        finally:
            abierto.cerrar()
        return {"ok": True}
    if orden == "leer":
        (archivo,) = args
        datos = Path(archivo).read_bytes()
        entradas = _leer_entradas(datos)
        abierto = abrir_grafnet(archivo, CLAVE, "importar", None if DESARROLLO else CLAVE_DESARROLLO)
        try:
            docs = {d: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                    for d, v in abierto.proyecto.documents.items()}
            return {"firma": abierto.firma, "firmado": bool(abierto.sello_valido), "huella": huella(entradas),
                    "entradas": {n: hashlib.sha256(b).hexdigest() for n, b in sorted(entradas.items()) if n not in (VERSION, SELLO, INFO)},
                    "metadatos": sorted(json.loads(entradas[INFO])) if INFO in entradas else None,
                    "documentos": docs, "modelos": len(abierto.proyecto.models()), "app": json.loads(entradas.get(INFO, b"{}")).get("version_guardado")}
        finally:
            abierto.cerrar()
    raise SystemExit(f"orden desconocida: {orden}")


# ------------------------------------------------------------------------------------------------------------- orquestador
def lanzar(raiz: Path, orden: str, *args: str) -> dict:
    entorno = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--trabajo", str(raiz), orden, *args],
                       cwd=raiz, env=entorno, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        return {"error": (r.stderr.strip().splitlines() or ["?"])[-1]}
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--trabajo":
        resultado = trabajar(Path(sys.argv[2]), sys.argv[3], sys.argv[4:])
        print(json.dumps(resultado, ensure_ascii=False))
        return 0
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--antigua", type=Path, required=True, help="carpeta de la 1.x (solo se ejecuta)")
    ap.add_argument("--salida", type=Path, required=True)
    args = ap.parse_args()
    antigua, nueva = args.antigua.resolve(), RAIZ
    sys.path.insert(0, str(RAIZ))
    from grafcet.examples import EJEMPLOS
    fuentes = {f"ejemplo/{k}": ("crear", k) for k in EJEMPLOS}
    for ruta in sorted((RAIZ / "tests" / "fixtures").rglob("*.grafnet")):
        fuentes[f"fixture/{ruta.relative_to(RAIZ / 'tests' / 'fixtures').as_posix()}"] = ("reguardar", str(ruta))
    args.salida = args.salida.resolve()
    args.salida.mkdir(parents=True, exist_ok=True)
    filas, fallos = [], 0
    for nombre, (como, origen) in fuentes.items():
        base = nombre.replace("/", "__")
        a, b = args.salida / f"{base}.2_0.grafnet", args.salida / f"{base}.1_x.grafnet"
        guardan = {"2.0": lanzar(nueva, como, origen, str(a)), "1.x": lanzar(antigua, como, origen, str(b))}
        fila = {"proyecto": nombre, "guardado": {v: ("error: " + r["error"] if "error" in r else "ok") for v, r in guardan.items()}}
        if all("error" not in r for r in guardan.values()):
            lee = {(quien, de): lanzar(raiz, "leer", str(ruta)) for quien, raiz in (("2.0", nueva), ("1.x", antigua))
                   for de, ruta in (("2.0", a), ("1.x", b))}
            fila["lee"] = {f"{q} lee lo de {d}": ("error: " + r["error"] if "error" in r else f"firma {r['firma']}") for (q, d), r in lee.items()}
            lecturas_a = [lee[("2.0", "2.0")], lee[("1.x", "2.0")]]
            lecturas_b = [lee[("2.0", "1.x")], lee[("1.x", "1.x")]]
            clave = ("entradas", "documentos", "huella", "firma")
            fila["cada_version_lee_igual_lo_de_la_otra"] = (all("error" not in r for r in (*lecturas_a, *lecturas_b))
                                                           and all(lecturas_a[0][k] == lecturas_a[1][k] for k in clave)
                                                           and all(lecturas_b[0][k] == lecturas_b[1][k] for k in clave))
            ra, rb = lee[("2.0", "2.0")], lee[("2.0", "1.x")]
            if "error" not in ra and "error" not in rb:
                fila["mismo_contenido_guardado"] = ra["entradas"] == rb["entradas"]
                if not fila["mismo_contenido_guardado"]:
                    fila["diferencias"] = sorted(n for n in set(ra["entradas"]) | set(rb["entradas"]) if ra["entradas"].get(n) != rb["entradas"].get(n))
                fila["firma_2_0_leida_por_1_x"] = lee[("1.x", "2.0")].get("firma")
                fila["firma_1_x_leida_por_2_0"] = lee[("2.0", "1.x")].get("firma")
        fallos += not (fila.get("cada_version_lee_igual_lo_de_la_otra") and fila.get("mismo_contenido_guardado"))
        filas.append(fila)
        print(f"{nombre}: lee igual {fila.get('cada_version_lee_igual_lo_de_la_otra')}, mismo contenido {fila.get('mismo_contenido_guardado')}", flush=True)
    (args.salida / "compatibilidad.json").write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"{len(filas)} proyectos; {fallos} con alguna diferencia (ver compatibilidad.json)")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
