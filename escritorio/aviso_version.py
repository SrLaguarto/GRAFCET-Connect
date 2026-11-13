"""El aviso de versión nueva: un diálogo emergente con el estilo de la aplicación (no se guarda nada al descartarlo)."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QSize, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from . import estilo
from .actualizaciones import url_segura

TITULO = "GRAFCET Connect"
ANCHO = 440


def _abrir_navegador(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


class DialogoVersionNueva(QDialog):
    """«Hay una versión nueva»: las versiones instalada y disponible, «Ahora no» (o Esc, o ✕) y «Descargar» (Intro).
    `abrir` es lo que abre la dirección (inyectable para las pruebas); la dirección pasa por `url_segura`."""

    def __init__(self, parent: QWidget | None, instalada: str, disponible: str, url: str = "", icono: Any = None,
                 abrir: Callable[[str], None] | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("avisoVersionNueva")
        self.setWindowTitle(TITULO)
        self.setFixedWidth(ANCHO)
        self.url = url
        self.abrir = abrir or _abrir_navegador
        self.setStyleSheet(f"""
QDialog#avisoVersionNueva {{ background:{estilo.SUPERFICIE}; }}
QLabel#tituloAviso {{ font-family:'{estilo.FUENTE_TITULO}'; font-size:18px; font-weight:600; color:{estilo.TINTA}; }}
QLabel#textoAviso {{ color:{estilo.TINTA_2}; font-size:13px; }}
QFrame#versiones {{ background:{estilo.SUPERFICIE_2}; border:1px solid {estilo.BORDE}; border-radius:{estilo.R_M}px; }}
QLabel#etiquetaVersion {{ color:{estilo.TINTA_2}; font-size:11px; }}
QLabel#versionInstalada {{ font-family:'{estilo.FUENTE_MONO}'; font-size:16px; color:{estilo.TINTA_2}; }}
QLabel#versionDisponible {{ font-family:'{estilo.FUENTE_MONO}'; font-size:16px; font-weight:700; color:{estilo.ACENTO}; }}
QLabel#flechaVersion {{ font-size:18px; color:{estilo.TINTA_2}; }}
QPushButton {{ min-height:{estilo.ALTO_CONTROL - 2}px; padding:0 16px; border-radius:{estilo.R_S}px; font-size:13px; }}
QPushButton#botonDescargar {{ background:{estilo.ACENTO}; color:white; border:1px solid {estilo.ACENTO}; font-weight:600; }}
QPushButton#botonAhoraNo {{ background:{estilo.SUPERFICIE}; color:{estilo.TINTA}; border:1px solid {estilo.BORDE}; }}
""")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(estilo.E6, estilo.E6, estilo.E6, estilo.E4)
        raiz.setSpacing(estilo.E3)
        cabecera = QHBoxLayout()
        cabecera.setSpacing(estilo.E3)
        self.l_icono = QLabel()
        if icono is not None:
            self.l_icono.setPixmap(QIcon(str(icono)).pixmap(QSize(40, 40)))
        self.l_icono.setFixedSize(40, 40)
        cabecera.addWidget(self.l_icono, 0, Qt.AlignmentFlag.AlignTop)
        columna = QVBoxLayout()
        columna.setSpacing(estilo.E1)
        self.l_titulo = QLabel("Hay una versión nueva")
        self.l_titulo.setObjectName("tituloAviso")
        self.l_texto = QLabel("GRAFCET Connect tiene una actualización disponible.")
        self.l_texto.setObjectName("textoAviso")
        columna.addWidget(self.l_titulo)
        columna.addWidget(self.l_texto)
        cabecera.addLayout(columna, 1)
        raiz.addLayout(cabecera)
        self.caja = QFrame()
        self.caja.setObjectName("versiones")
        interior = QHBoxLayout(self.caja)
        interior.setContentsMargins(estilo.E6, estilo.E3, estilo.E6, estilo.E3)
        self.rejilla = QGridLayout()
        self.rejilla.setHorizontalSpacing(20)
        self.rejilla.setVerticalSpacing(2)
        self.l_instalada, self.l_disponible = QLabel(instalada), QLabel(disponible)
        self.l_instalada.setObjectName("versionInstalada")
        self.l_disponible.setObjectName("versionDisponible")
        for columna_, etiqueta, numero in ((0, "Tiene instalada", self.l_instalada), (2, "Disponible", self.l_disponible)):
            rotulo = QLabel(etiqueta)
            rotulo.setObjectName("etiquetaVersion")
            self.rejilla.addWidget(rotulo, 0, columna_, Qt.AlignmentFlag.AlignHCenter)
            self.rejilla.addWidget(numero, 1, columna_, Qt.AlignmentFlag.AlignHCenter)
        flecha = QLabel("→")
        flecha.setObjectName("flechaVersion")
        self.rejilla.addWidget(flecha, 1, 1, Qt.AlignmentFlag.AlignCenter)
        interior.addLayout(self.rejilla)
        self.caja.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        raiz.addWidget(self.caja, 0, Qt.AlignmentFlag.AlignHCenter)
        raiz.addSpacing(estilo.E2)
        botones = QHBoxLayout()
        botones.addStretch(1)
        self.b_ahora_no = QPushButton("Ahora no")
        self.b_ahora_no.setObjectName("botonAhoraNo")
        self.b_descargar = QPushButton("Descargar")
        self.b_descargar.setObjectName("botonDescargar")
        self.b_descargar.setDefault(True)
        self.b_ahora_no.clicked.connect(self.reject)
        self.b_descargar.clicked.connect(self.descargar)
        botones.addWidget(self.b_ahora_no)
        botones.addWidget(self.b_descargar)
        raiz.addLayout(botones)

    def descargar(self) -> None:
        self.abrir(url_segura(self.url))
        self.accept()
