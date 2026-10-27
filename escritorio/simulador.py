"""Arranque del simulador GRAFCET de escritorio (P-IMP-29).

Uso:  python escritorio/simulador.py [modelo] [--ejemplo CLAVE] [--captura PNG]
      o GRAFCET.exe [modelo] en la versión portable (tools/construir_ejecutable.py)
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from escritorio.ventana import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
