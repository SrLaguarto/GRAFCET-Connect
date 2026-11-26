"""Estilo visual v2 compartido por los diálogos de configuración de E/S externas."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from . import estilo


def hoja_dialogo_es() -> str:
    """Hoja v2 en tarjetas blancas sobre fondo gris frío para diálogos de conexión."""
    return (
        f"QDialog {{ background:{estilo.FONDO}; color:{estilo.TINTA}; }}"
        f"QFrame#tarjetaConfigES {{ background:{estilo.SUPERFICIE}; border:1px solid {estilo.BORDE};"
        f" border-radius:{estilo.R_M}px; }}"
        f"QFrame#tarjetaConfigES QLabel {{ background:transparent; color:{estilo.TINTA}; border:0; }}"
        f"QFrame#tarjetaConfigES QCheckBox {{ background:transparent; color:{estilo.TINTA}; }}"
        f"QFrame#tarjetaConfigES QLabel#tituloTarjetaConfigES {{ color:{estilo.ACENTO};"
        f" font-family:{estilo.FAMILIA_TITULO}; font-size:{estilo.T_SECCION}px; font-weight:700; }}"
        f"QFrame#tarjetaConfigES QLabel#ayudaTarjetaConfigES {{ color:{estilo.TINTA_2}; font-size:12px; }}"
        f"QPushButton#botonAvanzadoES {{ text-align:left; background:{estilo.SUPERFICIE_2};"
        f" color:{estilo.TINTA_2}; border:1px solid {estilo.BORDE_FUERTE};"
        f" border-radius:{estilo.R_S}px; font-weight:600; }}"
        f"QPushButton#botonAvanzadoES:hover {{ background:{estilo.HOVER}; color:{estilo.TINTA};"
        f" border-color:{estilo.BORDE_CONTROL}; }}"
        f"QPushButton#botonAvanzadoES:checked, QPushButton#botonAvanzadoES[abierto=\"true\"] {{"
        f" background:{estilo.ACENTO_SUAVE}; color:{estilo.ACENTO_OSCURO};"
        f" border-color:{estilo.ACENTO_BORDE}; }}"
        f"QTableWidget {{ background:{estilo.SUPERFICIE}; color:{estilo.TINTA};"
        f" gridline-color:{estilo.BORDE}; border:1px solid {estilo.BORDE}; border-radius:{estilo.R_S}px; }}"
        f"QHeaderView::section {{ background:{estilo.SUPERFICIE_2}; color:{estilo.TINTA_2};"
        f" padding:6px; border:0; border-bottom:1px solid {estilo.BORDE}; font-weight:600; }}"
    )


def crear_tarjeta(titulo: str, parent: QWidget | None = None, tooltip: str = "") -> tuple[QFrame, QVBoxLayout]:
    """Crea una tarjeta blanca v2 con su título de sección y márgenes seguros (`14/12 px`)."""
    tarjeta = QFrame(parent)
    tarjeta.setObjectName("tarjetaConfigES")
    lay = QVBoxLayout(tarjeta)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(estilo.E2)
    cabecera = QLabel(titulo, tarjeta)
    cabecera.setObjectName("tituloTarjetaConfigES")
    if tooltip:
        cabecera.setToolTip(tooltip)
    lay.addWidget(cabecera)
    return tarjeta, lay
