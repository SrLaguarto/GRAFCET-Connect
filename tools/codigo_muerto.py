"""Código muerto de `escritorio/` (V2-E6): funciones, métodos, clases, constantes y módulos cuyo nombre no aparece en ningún otro sitio.

Sin dependencias: `ast` para las definiciones y una búsqueda de nombres para los usos. Cuenta como uso **cualquier aparición del nombre**
en el código, las pruebas, las herramientas y los textos del proyecto (llamadas, atributos, `getattr` con texto, señales conectadas,
`patch` en pruebas, cadenas): si el nombre sale más veces que sus propias definiciones, se da por usado. Es deliberadamente benévola:
solo señala lo que no tiene ninguna otra aparición, y la lista se revisa a mano antes de borrar nada.

No cuentan como muertos los nombres «dunder» ni los que sobrescriben un método de Qt (`closeEvent`, `paintEvent`, `sizeHint`…), que
llama Qt sin que el nombre aparezca. Los módulos se dan por usados si algún fichero importa su nombre (o lo nombra en un texto).

  python tools/codigo_muerto.py                # lista en pantalla
  python tools/codigo_muerto.py --salida X.md  # y la escribe
"""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import ast
import io
import re
import sys
import tokenize

RAIZ = Path(__file__).resolve().parents[1]
DEFINIDOS = ("escritorio",)                      # dónde se buscan definiciones
USOS = ("escritorio", "tools", "tests", "grafcet", "conexion", "spec")  # dónde se buscan usos (código)
TEXTOS = ("*.js", "*.css", "*.html", "*.bat", "*.iss", "*.md", "*.txt", "*.json", "*.toml", "*.cfg", "*.spec")
OMITIR = {"__pycache__", "artifacts", ".git", "docs", "propuesta", "build", "dist"}


def ficheros(patron: str, carpetas: tuple[str, ...]) -> list[Path]:
    salida = []
    for c in carpetas:
        base = RAIZ / c
        if base.is_dir():
            salida += [p for p in base.rglob(patron) if not (OMITIR & set(p.relative_to(RAIZ).parts))]
    return sorted(set(salida))


def palabras(texto: str) -> Counter:
    return Counter(re.findall(r"[^\W\d]\w*", texto))


def nombres_qt() -> set[str]:
    """Todo nombre de método o atributo de las clases de Qt (lo que una subclase puede sobrescribir)."""
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:  # sin Qt no se pueden distinguir las sobrescrituras
        return set()
    nombres = set()
    for modulo in (QtCore, QtGui, QtWidgets):
        for clase in vars(modulo).values():
            if isinstance(clase, type):
                nombres.update(dir(clase))
    return nombres


def main() -> int:
    ap = ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--salida", type=Path)
    args = ap.parse_args()
    cuenta: Counter = Counter()
    for patron in ("*.py", *TEXTOS):
        for f in ficheros(patron, USOS + ("tools",)) + [p for p in RAIZ.glob(patron)]:
            try:
                cuenta.update(palabras(f.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    qt = nombres_qt()
    definiciones: dict[str, list[tuple[str, str, int]]] = {}
    for f in ficheros("*.py", DEFINIDOS):
        rel = f.relative_to(RAIZ).as_posix()
        arbol = ast.parse(f.read_text(encoding="utf-8"))

        def anota(nombre: str, clase: str, linea: int) -> None:
            definiciones.setdefault(nombre, []).append((rel, clase, linea))
        for nodo in arbol.body:
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                anota(nodo.name, "función", nodo.lineno)
            elif isinstance(nodo, ast.ClassDef):
                anota(nodo.name, "clase", nodo.lineno)
                for m in nodo.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        anota(m.name, f"método de {nodo.name}", m.lineno)
                    elif isinstance(m, ast.Assign):
                        for t in m.targets:
                            if isinstance(t, ast.Name):
                                anota(t.id, f"atributo de {nodo.name}", m.lineno)
            elif isinstance(nodo, ast.Assign):
                for t in nodo.targets:
                    if isinstance(t, ast.Name):
                        anota(t.id, "constante", nodo.lineno)
            elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
                anota(nodo.target.id, "constante", nodo.lineno)
    muertos = []
    for nombre, sitios in sorted(definiciones.items()):
        if nombre.startswith("__") and nombre.endswith("__"):
            continue
        if nombre in qt and any("método" in c for _, c, _ in sitios):
            continue
        # cada definición aporta una aparición del nombre; todo lo que pase de ahí es otro uso
        if cuenta[nombre] <= len(sitios):
            muertos.extend((nombre, *s) for s in sitios)
    # módulos
    modulos = []
    for f in ficheros("*.py", DEFINIDOS):
        if f.stem == "__init__":
            continue
        veces = sum(1 for g in ficheros("*.py", USOS) if g != f and re.search(rf"\b{re.escape(f.stem)}\b", g.read_text(encoding="utf-8", errors="replace")))
        veces += sum(1 for patron in TEXTOS for g in RAIZ.glob(patron) if re.search(rf"\b{re.escape(f.stem)}\b", g.read_text(encoding="utf-8", errors="replace")))
        if veces == 0:
            modulos.append(f.relative_to(RAIZ).as_posix())
    salida = io.StringIO()
    print(f"# Código muerto de escritorio/ ({len(definiciones)} nombres definidos)\n", file=salida)
    print(f"## Definiciones sin otra aparición ({len(muertos)})\n", file=salida)
    for nombre, rel, clase, linea in muertos:
        print(f"- `{nombre}` · {clase} · {rel}:{linea}", file=salida)
    print(f"\n## Módulos que nadie nombra ({len(modulos)})\n", file=salida)
    for m in modulos:
        print(f"- {m}", file=salida)
    texto = salida.getvalue()
    sys.stdout.buffer.write(texto.encode("utf-8"))
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
