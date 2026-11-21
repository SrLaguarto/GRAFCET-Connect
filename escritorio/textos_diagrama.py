"""El texto enriquecido de una figura del dibujo."""
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsTextItem


def texto_nuevo(html: str, color: QColor, fuente: QFont) -> QGraphicsTextItem:
    item = QGraphicsTextItem()
    item.document().setDocumentMargin(0)
    item.setFont(fuente)
    item.setDefaultTextColor(color)
    item.setHtml(html)
    return item
