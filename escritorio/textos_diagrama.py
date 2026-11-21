"""Textos reutilizables de la escena principal del diagrama."""
from collections import defaultdict

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsScene, QGraphicsTextItem


def texto_nuevo(html: str, color: QColor, fuente: QFont) -> QGraphicsTextItem:
    item = QGraphicsTextItem()
    item.document().setDocumentMargin(0)
    item.setFont(fuente)
    item.setDefaultTextColor(color)
    item.setHtml(html)
    return item


class EscenaDiagrama(QGraphicsScene):
    def __init__(self, padre) -> None:
        super().__init__(padre)
        self.vaciar_textos()

    def vaciar_textos(self) -> None:
        self._actuales: dict[tuple[str, int, str], list[QGraphicsTextItem]] = defaultdict(list)
        self._anteriores: dict[tuple[str, int, str], list[QGraphicsTextItem]] = {}

    def clear(self) -> None:
        self.vaciar_textos()
        super().clear()

    def comenzar_dibujo(self) -> None:
        # clear destruiría los documentos de texto, incluso si aún tenemos referencias a sus objetos.
        for grupo in self._actuales.values():
            for item in grupo:
                self.removeItem(item)
        self._anteriores = self._actuales
        self._actuales = defaultdict(list)
        super().clear()

    def texto(self, html: str, color: QColor, fuente: QFont) -> QGraphicsTextItem:
        clave = html, color.rgba(), fuente.key()
        anteriores = self._anteriores.get(clave)
        item = anteriores.pop() if anteriores else texto_nuevo(html, color, fuente)
        item.setVisible(True)   # un texto reutilizado no conserva el estado de otra pasada (el filtro de parcial lo dejaba oculto o atenuado)
        item.setOpacity(1.0)
        self._actuales[clave].append(item)
        return item

    def terminar_dibujo(self) -> None:
        self._anteriores.clear()
