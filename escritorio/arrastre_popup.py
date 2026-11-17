"""Conserva la captura exterior de una ventana emergente tras el arrastre OLE de Windows."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid


def recuperar_captura(ventana):
    if QApplication.platformName() != "windows" or not isValid(ventana):
        return
    if not ventana.isVisible() or ventana.windowType() != Qt.WindowType.Popup:
        return
    if QApplication.activePopupWidget() is not ventana:
        return
    nativa = ventana.windowHandle()
    if nativa is not None:
        # OLE libera la captura del ratón; Qt conserva el popup pero no la recupera.
        # Se captura su QWindow para mantener el reparto normal de eventos entre sus hijos.
        nativa.setMouseGrabEnabled(True)


def ejecutar_arrastre(arrastre, ventana):
    try:
        return arrastre.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
    finally:
        recuperar_captura(ventana)
