"""Aísla las lecturas Python sin vaciar el entorno nativo compartido con Qt."""
from contextlib import contextmanager
import os
from unittest.mock import patch


@contextmanager
def entorno_aislado(cambios):
    valores = dict(os.environ)
    valores.update(cambios)
    with patch.object(os, "environ", valores):
        yield valores
