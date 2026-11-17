"""Regresión aislada: las pruebas de claves no deben borrar el entorno de Qt."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication
import test_contenedor_grafnet as contenedor


def main():
    app = QApplication([])
    nombres = ("QT_QPA_PLATFORM", "QT_QPA_FONTDIR", "GRAFCONNECT_SIN_ACTUALIZAR")
    esperado = {nombre: os.environ.get(nombre) for nombre in nombres}
    medidas = []
    obtener = contenedor.obtener_clave

    def observar(*args, **kwargs):
        actual = {nombre: os.environ.get(nombre) for nombre in nombres}
        assert actual == esperado, f"La prueba de clave altera el entorno de Qt: {actual}"
        fuente = QFont("Segoe UI")
        fuente.setPixelSize(11)
        fm = QFontMetrics(fuente)
        estrecha = fm.horizontalAdvance("iiii")
        ancha = fm.horizontalAdvance("WWWW")
        assert estrecha < ancha, "Qt está usando métricas de sustitución en vez de los glifos reales"
        medidas.append({"estrecha": estrecha, "ancha": ancha, "alto": fm.height()})
        return obtener(*args, **kwargs)

    caso = contenedor.Contenedores("test_SGFN07_construccion_exige_clave_y_no_deja_modulo_en_repositorio")
    resultado = unittest.TestResult()
    entorno_nativo = os.environ
    with patch.object(entorno_nativo, "clear", wraps=entorno_nativo.clear) as vaciar:
        with patch.object(contenedor, "obtener_clave", side_effect=observar):
            caso.run(resultado)
    vaciar.assert_not_called()
    assert os.environ is entorno_nativo
    assert resultado.wasSuccessful(), str(resultado.failures + resultado.errors)
    assert len(medidas) == 2
    print(json.dumps({"entorno_conservado": True, "medidas": medidas}))
    app.processEvents()


if __name__ == "__main__":
    main()
