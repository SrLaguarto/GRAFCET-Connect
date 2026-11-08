"""Comprueba los contrastes WCAG 2.x de las parejas de colores de `escritorio/estilo.py`.

Uso, desde la raíz del repositorio:  python propuesta/herramientas/contrastes.py

Texto (y su fondo): 4,5:1 como mínimo. Bordes de control, foco y marcas gráficas: 3:1 como mínimo. Lo deshabilitado queda
exento (WCAG 1.4.3), y se lista aparte. Termina con código 1 si alguna pareja exigida no llega. No necesita pantalla ni Qt.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def tokens() -> dict[str, str]:
    """Las constantes de color de estilo.py, leídas sin importar Qt."""
    arbol = ast.parse((RAIZ / "escritorio" / "estilo.py").read_text(encoding="utf-8"))
    valores: dict[str, str] = {}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1 and isinstance(nodo.targets[0], ast.Name):
            try:
                v = ast.literal_eval(nodo.value)
            except (ValueError, SyntaxError):
                if isinstance(nodo.value, ast.Name) and nodo.value.id in valores:
                    v = valores[nodo.value.id]
                else:
                    continue
            if isinstance(v, str) and (v.startswith("#") or v == "white"):
                valores[nodo.targets[0].id] = "#ffffff" if v == "white" else v
    return valores


def luminancia(color: str) -> float:
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (primer plano, fondo, mínimo, dónde se usa)
PAREJAS = [
    ("TINTA", "SUPERFICIE", 4.5, "texto principal sobre tarjetas y paneles"),
    ("TINTA", "FONDO", 4.5, "texto sobre el fondo de la ventana"),
    ("TINTA", "SUPERFICIE_2", 4.5, "texto en cabeceras y zonas hundidas"),
    ("TINTA_2", "SUPERFICIE", 4.5, "texto secundario"),
    ("TINTA_2", "FONDO", 4.5, "texto secundario sobre la ventana"),
    ("TINTA_2", "SUPERFICIE_2", 4.5, "texto secundario en cabeceras de tabla"),
    ("TINTA_3", "SUPERFICIE", 4.5, "ayudas discretas"),
    ("TINTA_3", "FONDO", 4.5, "ayudas discretas sobre la ventana"),
    ("ACENTO", "SUPERFICIE", 4.5, "texto de acento (títulos de sección, pestaña plegada)"),
    ("ACENTO", "SUPERFICIE_2", 4.5, "texto de acento en la pestaña plegada de un panel"),
    ("ACENTO", "FONDO", 4.5, "texto de acento sobre la ventana"),
    ("BLANCO", "ACENTO", 4.5, "Play y botones primarios"),
    ("TINTA", "ACENTO_SUAVE", 4.5, "texto de lo seleccionado o activo"),
    ("ACENTO", "ACENTO_SUAVE", 4.5, "texto de acento sobre lo activo"),
    ("BLANCO", "EDICION", 4.5, "chip EDICIÓN"),
    ("BLANCO", "SIMULACION", 4.5, "chip SIMULACIÓN EN CURSO"),
    ("TINTA", "SIMULACION_SUAVE", 4.5, "texto sobre la fila de herramientas al simular"),
    ("BLANCO", "TINTA", 4.5, "Stop y ayudas emergentes"),
    ("OK", "SUPERFICIE", 4.5, "texto de estado correcto"),
    ("AVISO", "AVISO_FONDO", 4.5, "texto de aviso (ámbar)"),
    ("AVISO", "SUPERFICIE", 4.5, "texto de aviso sobre blanco"),
    ("ERROR", "SUPERFICIE", 4.5, "texto de error"),
    ("ERROR", "ERROR_FONDO", 4.5, "texto de error sobre su fondo"),
    ("BLANCO", "ERROR", 4.5, "chip de error"),
    ("BORDE_CONTROL", "SUPERFICIE", 3.0, "borde de un control sobre una tarjeta"),
    ("BORDE_CONTROL", "FONDO", 3.0, "borde de un control sobre la ventana"),
    ("FOCO", "SUPERFICIE", 3.0, "anillo de foco sobre una tarjeta"),
    ("FOCO", "FONDO", 3.0, "anillo de foco sobre la ventana"),
    ("FOCO", "ACENTO_SUAVE", 3.0, "anillo de foco sobre un control activo"),
    ("BLANCO", "ACENTO_OSCURO", 3.0, "anillo de foco del botón Play (sobre el acento)"),
    ("ACENTO", "SUPERFICIE", 3.0, "borde de un control activo"),
    ("EDICION", "SUPERFICIE", 3.0, "franja del modo edición"),
    ("SIMULACION", "SUPERFICIE", 3.0, "franja del modo simulación"),
    ("LUZ_CONECTADA", "SUPERFICIE", 3.0, "luz de conexión: conectada"),
    ("LUZ_DESCONECTADA", "SUPERFICIE", 3.0, "luz de conexión: desconectada"),
    ("LUZ_ERROR", "SUPERFICIE", 3.0, "luz de conexión: error"),
]
EXENTAS = [("DESHABILITADO", "SUPERFICIE", "texto deshabilitado (exento)"), ("DESHABILITADO", "SUPERFICIE_2", "idem sobre fondo hundido")]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    t = tokens()
    t["LUZ_CONECTADA"], t["LUZ_DESCONECTADA"], t["LUZ_ERROR"] = "#17803d", "#6f7f92", "#c62828"
    fallos = 0
    print(f"{'primer plano':<18}{'fondo':<18}{'ratio':>7}  {'mín.':>5}  uso")
    for fg, bg, minimo, uso in PAREJAS:
        r = contraste(t[fg], t[bg])
        marca = "" if r >= minimo else "   <-- NO LLEGA"
        fallos += r < minimo
        print(f"{fg:<18}{bg:<18}{r:>7.2f}  {minimo:>5}  {uso}{marca}")
    print("\nExentas (deshabilitado):")
    for fg, bg, uso in EXENTAS:
        print(f"{fg:<18}{bg:<18}{contraste(t[fg], t[bg]):>7.2f}  {uso}")
    print(f"\n{len(PAREJAS) - fallos}/{len(PAREJAS)} parejas cumplen")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
