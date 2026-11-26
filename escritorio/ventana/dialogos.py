"""Diálogos de la ventana: «Forzar un parcial…» y «Acerca de»."""
from __future__ import annotations

import html
from .. import estilo, sello
from ..estilo_dialogos import PieDialogo, aplicar_escala_dialogo
from typing import Any
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QRadioButton, QVBoxLayout, QWidget)
from .constantes import ICONO_PROGRAMA, TITULO, URL_CODIGO, URL_FALLOS


class DialogoForzado(QDialog):
    """«Forzar un parcial…» y «Editar orden de forzado…»: el parcial destino (por su nombre), la forma de la orden (explícita, la
    situación actual, vacía o inicial) y, solo si es explícita, las etapas del destino que se imponen (selección múltiple por
    nombre). `datos` es lo que prepara `Edicion._datos_forzado`; el resultado (`resultado`) lleva los ID de lo elegido. No
    valida: si la orden no vale (una explícita sin etapas, un ciclo de forzado), lo dice la edición con el aviso en rojo."""

    def __init__(self, parent: QWidget, datos: dict[str, Any]) -> None:
        super().__init__(parent)
        aplicar_escala_dialogo(self)
        self.datos = datos
        actual = datos.get("actual")
        self.setWindowTitle("Editar orden de forzado" if actual else "Forzar un parcial")
        self.resize(420, 460)
        lay = QVBoxLayout(self)
        nota = QLabel(f"Orden de forzado de la etapa {html.escape(datos['origen'])}: mientras esa etapa esté activa, impone una "
                      "situación al parcial que elijas.")
        nota.setWordWrap(True)
        lay.addWidget(nota)
        form = QFormLayout()
        self.destino = QComboBox()
        for pid, nombre in datos["destinos"]:
            self.destino.addItem(nombre, pid)
        form.addRow("Parcial que se fuerza", self.destino)
        lay.addLayout(form)
        caja = QGroupBox("Situación que se impone")
        cl = QVBoxLayout(caja)
        self.grupo = QButtonGroup(self)
        self.formas: dict[str, QRadioButton] = {}
        for clave, texto in datos["formas"]:
            b = QRadioButton(texto)
            self.grupo.addButton(b)
            self.formas[clave] = b
            cl.addWidget(b)
        lay.addWidget(caja)
        self.l_etapas = QLabel("Etapas del parcial que quedan activas (solo en la forma Explícita):")
        self.l_etapas.setWordWrap(True)
        lay.addWidget(self.l_etapas)
        self.etapas = QListWidget()
        lay.addWidget(self.etapas, 1)
        lay.addWidget(PieDialogo().conectar(self))
        if actual:
            self.destino.setCurrentIndex(max(0, self.destino.findData(actual["destino"])))
        self.formas[actual["forma"] if actual and actual["forma"] in self.formas else "explicit"].setChecked(True)
        self._llenar(actual["etapas"] if actual else [])
        self.destino.currentIndexChanged.connect(lambda _: self._llenar([]))
        self.grupo.buttonToggled.connect(lambda *_: self._habilitar())

    def _llenar(self, marcadas: list[str]) -> None:
        """Las etapas del parcial elegido, con casilla, con las `marcadas` ya puestas."""
        self.etapas.clear()
        for sid, nombre in self.datos["etapas"].get(self.destino.currentData(), []):
            it = QListWidgetItem(nombre)
            it.setData(Qt.ItemDataRole.UserRole, sid)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if sid in marcadas else Qt.CheckState.Unchecked)
            self.etapas.addItem(it)
        self._habilitar()

    def _habilitar(self) -> None:
        explicita = self.formas["explicit"].isChecked()
        self.etapas.setEnabled(explicita)
        self.l_etapas.setEnabled(explicita)

    def resultado(self) -> dict[str, Any]:
        """Lo elegido: {destino: ID del parcial, forma: explicit|current|empty|initial, etapas: [ID] (solo las marcadas, y
        solo si la forma es explícita)}."""
        forma = next(k for k, b in self.formas.items() if b.isChecked())
        marcadas = [self.etapas.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.etapas.count())
                    if self.etapas.item(i).checkState() == Qt.CheckState.Checked] if forma == "explicit" else []
        return {"destino": self.destino.currentData(), "forma": forma, "etapas": marcadas}


class AcercaDe(QDialog):
    """«Acerca de GRAFCET Connect»: icono, versión, licencia, enlace al código, botón para comunicar un fallo y Cerrar. Los
    enlaces se abren con `QDesktopServices` (`abrir`)."""

    ACENTO = estilo.ACENTO

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from .. import VERSION
        self.setWindowTitle(f"Acerca de {TITULO}")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QDialog {{ background: {estilo.FONDO} }} QLabel {{ color: {estilo.TINTA} }}")
        aplicar_escala_dialogo(self)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        cab = QHBoxLayout()
        icono = QLabel()
        icono.setPixmap(QIcon(str(ICONO_PROGRAMA)).pixmap(64, 64))
        cab.addWidget(icono)
        titulo = QLabel(f"<span style='font-size:{estilo.T_TITULO + 4}px; font-weight:600; color:{self.ACENTO}'>{TITULO}</span><br>"
                        f"Versión {VERSION}{' · versión de desarrollo' if sello.DESARROLLO else ''}<br>"
                        "Editor y simulador GRAFCET · Basado en IEC 60848")
        cab.addWidget(titulo, 1)
        lay.addLayout(cab)
        self.l_licencia = QLabel(f"{TITULO} es software libre y de código abierto, publicado con la licencia GPL-3.0. "
                                 f"Su código está en <a href=\"{URL_CODIGO}\">GitHub</a>.<br><br>"
                                 "Para usarlo en un producto o servicio que no pueda cumplir la GPL-3.0, el "
                                 "autor ofrece licencias comerciales: pídelas a través de GitHub.")
        self.l_licencia.setWordWrap(True)
        self.l_licencia.linkActivated.connect(self.abrir)
        lay.addWidget(self.l_licencia)
        self.l_fallos = QLabel("Si encuentras un fallo o tienes una sugerencia, puedes comunicarlo en GitHub:")
        self.l_fallos.setWordWrap(True)
        lay.addWidget(self.l_fallos)
        self.b_fallo = QPushButton("Comunicar un fallo")
        self.b_fallo.setStyleSheet(f"QPushButton {{ background: {self.ACENTO}; color: white; font-weight: 600; "
                                   f"border: 1px solid transparent; border-radius: {estilo.R_S}px; padding: 0 14px }}")  # (el borde transparente deja el alto de control de la hoja global)
        self.b_fallo.clicked.connect(lambda: self.abrir(URL_FALLOS))
        fila = QHBoxLayout()
        fila.addWidget(self.b_fallo)
        fila.addStretch(1)
        lay.addLayout(fila)
        garantia = QLabel("Este programa se ofrece sin ninguna garantía. Las licencias, la propia y las de las "
                          "bibliotecas incluidas, están en la carpeta «licencias». Interfaz con Qt for Python "
                          "(PySide6), bajo licencia LGPL v3.")
        garantia.setWordWrap(True)
        garantia.setStyleSheet(f"color: {estilo.TINTA_2}; font-size: 12px")
        lay.addWidget(garantia)
        cerrar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cerrar.rejected.connect(self.reject)
        cerrar.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        lay.addWidget(cerrar)

    def abrir(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))


def _icono_grafcet() -> QIcon:
    """Esquema de etapa, transición y etapa (el dibujo GRAFCET), para el botón que vuelve desde la vista de E/S."""
    return estilo.icono_grafcet()


def _icono_barra(tipo: str, color: str = estilo.TINTA) -> QIcon:
    """Iconos de línea propios para los controles de la aplicación (no son notación GRAFCET); de un solo trazo (estilo.py)."""
    return estilo.icono(tipo, color)
