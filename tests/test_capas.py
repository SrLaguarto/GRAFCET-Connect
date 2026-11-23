"""SCAP01..SCAP04: las capas del programa (docs/ARQUITECTURA.md, sección 1) se cumplen en las importaciones de cada fichero."""
import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

QT = ("PySide6", "PyQt5", "PyQt6", "shiboken6", "shiboken2", "PySide2")


def importados(ruta: Path) -> set[str]:
    """Nombres completos de los módulos que importa un fichero (las importaciones relativas se resuelven contra su paquete)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    paquete = list(ruta.relative_to(RAIZ).with_suffix("").parts[:-1])
    salida: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            salida.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete[:len(paquete) - (nodo.level - 1)]
                salida.add(".".join(base + ([nodo.module] if nodo.module else [])))
                salida.update(".".join(base + ([nodo.module] if nodo.module else []) + [a.name]) for a in nodo.names)
            elif nodo.module:
                salida.add(nodo.module)
                salida.update(f"{nodo.module}.{a.name}" for a in nodo.names)
    return salida


def usa(modulos: set[str], prohibidos: tuple[str, ...]) -> list[str]:
    return sorted(m for m in modulos if any(m == p or m.startswith(p + ".") for p in prohibidos))


def fuera_de_regla(ficheros: list[Path], prohibidos: tuple[str, ...]) -> list[str]:
    assert ficheros, "no hay ficheros que comprobar"
    return [f"{f.relative_to(RAIZ)} importa {', '.join(malos)}" for f in ficheros if (malos := usa(importados(f), prohibidos))]


def py(carpeta: str) -> list[Path]:
    return sorted(p for p in (RAIZ / carpeta).rglob("*.py") if "__pycache__" not in p.parts)


class Capas(unittest.TestCase):
    def test_SCAP01_el_nucleo_no_importa_escritorio_conexion_tools_ni_qt(self):
        """REQ-ARQ-01: `grafcet/` solo usa la biblioteca estándar y no importa `escritorio`, `conexion`, `tools` ni Qt."""
        self.assertEqual(fuera_de_regla(py("grafcet"), ("escritorio", "conexion", "tools") + QT), [])

    def test_SCAP02_conexion_no_importa_escritorio_tools_ni_qt(self):
        """REQ-ARQ-01: `conexion/` no importa `escritorio`, `tools` ni Qt."""
        self.assertEqual(fuera_de_regla(py("conexion"), ("escritorio", "tools") + QT), [])

    def test_SCAP03_las_piezas_sin_qt_de_escritorio_no_importan_qt(self):
        """REQ-ARQ-01: `escritorio/geometria/` y `descriptores.py`, `diferencia.py` y `modelo_visual.py` de la escena no importan Qt."""
        escena = RAIZ / "escritorio" / "escena"
        ficheros = py("escritorio/geometria") + [escena / n for n in ("descriptores.py", "diferencia.py", "modelo_visual.py")]
        self.assertEqual(fuera_de_regla(ficheros, QT), [])

    def test_SCAP04_el_programa_no_importa_tools(self):
        """REQ-ARQ-01: nada de `grafcet/`, `conexion/` ni `escritorio/` importa `tools/`."""
        self.assertEqual(fuera_de_regla(py("grafcet") + py("conexion") + py("escritorio"), ("tools",)), [])


if __name__ == "__main__":
    unittest.main()
