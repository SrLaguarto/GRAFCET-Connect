"""Campos compactos para Propiedades flotante."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel

from . import estilo


def campos_transicion(panel, widget):
    layout = QGridLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(estilo.E2)
    layout.addWidget(QLabel("Etiqueta"), 0, 0)
    panel.t_etiqueta.setMaximumWidth(12 * estilo.E4)
    layout.addWidget(panel.t_etiqueta, 0, 1)
    layout.setColumnStretch(3, 1)
    layout.addWidget(QLabel("Comentario"), 1, 0)
    layout.addWidget(panel.t_comentario, 1, 1, 1, 3)
