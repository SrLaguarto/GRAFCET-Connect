"""Recentrar el dibujo cuando cambia el tamaño de la ventana principal.

Al maximizar, encajar a media pantalla, restaurar o arrastrar el borde, el dibujo vuelve a encajarse como con «Centrar
todo». Un temporizador de disparo único agrupa los cambios seguidos para no recalcular en cada píxel. Solo lo activa el
cambio de tamaño de la ventana: plegar o desplegar paneles no pasa por aquí.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QTimer

RETARDO_MS = 200


class Recentrado(QObject):
    """Llama a `centrar` una vez, `RETARDO_MS` después del último aviso de cambio de tamaño."""

    def __init__(self, centrar: Callable[[], None], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.temporizador = QTimer(self)
        self.temporizador.setSingleShot(True)
        self.temporizador.setInterval(RETARDO_MS)
        self.temporizador.timeout.connect(centrar)

    def solicitar(self) -> None:
        """Reinicia la cuenta atrás: el dibujo se centrará cuando el tamaño deje de cambiar."""
        self.temporizador.start()
