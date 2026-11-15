"""Arranque del simulador GRAFCET de escritorio (P-IMP-29).

Uso:  python escritorio/simulador.py [modelo] [--ejemplo CLAVE] [--captura PNG]
      o GRAFCET.exe [modelo] en la versión portable (tools/construir_ejecutable.py)
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main(argv=None):
    from escritorio.arranque_servidor_web import despachar
    resultado = despachar(argv)
    if resultado is not None:
        return resultado
    from escritorio.ventana import main as abrir_ventana
    return abrir_ventana(argv)

if __name__ == "__main__":
    sys.exit(main())
