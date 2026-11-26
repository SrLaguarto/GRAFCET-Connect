"""Utilidades de escala, cabecera y pie común (`Cancelar | Aceptar`) para los diálogos de la aplicación."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QGridLayout, QInputDialog, QLabel, QMessageBox

from . import estilo
from .componentes_comunes import (
    CabeceraDialogo,
    PieDialogo,
    hoja_componentes_dialogo,
    normalizar_botones_dialogo,
)

__all__ = [
    "CabeceraDialogo",
    "PieDialogo",
    "aplicar_escala_dialogo",
    "hoja_componentes_dialogo",
    "normalizar_botones_dialogo",
]


def aplicar_escala_dialogo(dialogo) -> None:
    """Aplica la hoja global en la escala vigente conservando reglas locales previas del diálogo."""
    propia = dialogo.property("_hoja_propia_dialogo")
    if propia is None:
        propia = dialogo.styleSheet()
        dialogo.setProperty("_hoja_propia_dialogo", propia)
    dialogo.setStyleSheet(estilo.hoja_global() + hoja_componentes_dialogo() + propia)


class _EstiloDialogosQt(QObject):
    """Viste los diálogos que crean las funciones estáticas de Qt en los puntos de uso existentes."""

    def eventFilter(self, cuadro, evento):  # noqa: N802
        if evento.type() == QEvent.Type.Show:
            if isinstance(cuadro, QMessageBox):
                _estilizar_mensaje(cuadro)
            elif isinstance(cuadro, QInputDialog) and cuadro.windowTitle().startswith("Renombrar"):
                caja = cuadro.findChild(QDialogButtonBox)
                if caja is not None:
                    aplicar_escala_dialogo(cuadro)
                    normalizar_botones_dialogo(caja)
        return False


def instalar_dialogos_qt() -> None:
    app = QApplication.instance()
    if app is not None and app.findChild(_EstiloDialogosQt) is None:
        app.installEventFilter(_EstiloDialogosQt(app))


def _estilizar_mensaje(cuadro: QMessageBox) -> None:
    aplicar_escala_dialogo(cuadro)
    rejilla = cuadro.layout()
    if isinstance(rejilla, QGridLayout):
        margen = estilo.E4 + estilo.E1
        rejilla.setContentsMargins(margen, margen, margen, margen)
        _poner_titular(cuadro, rejilla)
    QTimer.singleShot(0, cuadro, lambda: _ordenar_mensaje(cuadro))


def _ordenar_mensaje(cuadro: QMessageBox) -> None:
    if not cuadro.isVisible():
        return
    caja = cuadro.findChild(QDialogButtonBox)
    if caja is None:
        return
    botones = caja.buttons()
    auxiliar = (QDialogButtonBox.ButtonRole.ActionRole, QDialogButtonBox.ButtonRole.HelpRole)
    opciones = [boton for boton in botones if caja.buttonRole(boton) not in auxiliar]
    primario = cuadro.defaultButton()
    if primario not in opciones:
        primario = next((boton for boton in opciones if boton.isDefault()), opciones[0] if opciones else None)
    for boton in botones:
        boton.setFixedHeight(estilo.ALTO_ESTANDAR)
        estilo.poner(boton, pieDialogo=True, primario=(boton is primario))
    if primario is not None:
        fila = caja.layout()
        fila.removeWidget(primario)
        fila.addWidget(primario)
    rejilla = cuadro.layout()
    rejilla.activate()
    cuadro.setFixedSize(cuadro.size().expandedTo(rejilla.totalMinimumSize()))


def _poner_titular(cuadro: QMessageBox, rejilla: QGridLayout) -> None:
    titulo = cuadro.windowTitle()
    if not titulo:
        return
    titular = cuadro.findChild(QLabel, "titularMensaje")
    if titular is None:
        titular = QLabel(cuadro)
        titular.setObjectName("titularMensaje")
        titular.setTextFormat(Qt.TextFormat.PlainText)
        titular.setWordWrap(True)
        titular.setStyleSheet(f"font-size:{estilo.T_SECCION}px; font-weight:700; color:{estilo.TINTA}")
    titular.setText(titulo)
    if rejilla.indexOf(titular) >= 0:
        return
    posiciones = [rejilla.getItemPosition(i) for i in range(rejilla.count())]
    elementos = [rejilla.takeAt(0) for _ in posiciones]
    for elemento, (fila, columna, alto, ancho) in zip(elementos, posiciones):
        rejilla.addItem(elemento, fila + 1, columna, alto, ancho)
    rejilla.addWidget(titular, 0, 0, 1, rejilla.columnCount())
