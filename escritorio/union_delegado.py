"""Indicador vivo de cada unión, independiente del texto y del estado ámbar."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from . import estilo

ROL_VALOR = Qt.ItemDataRole.UserRole + 1
ROL_VARIABLE = Qt.ItemDataRole.UserRole + 2
ROL_TEXTO = Qt.ItemDataRole.UserRole + 3


class DelegadoUnion(QStyledItemDelegate):
    def paint(self, pintor, opcion, indice):
        opt = QStyleOptionViewItem(opcion)
        self.initStyleOption(opt, indice)
        opt.rect.adjust(17, 0, 0, 0)
        opt.text = opt.text.removeprefix("● ")
        estilo_widget = opt.widget.style() if opt.widget else QApplication.style()
        estilo_widget.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, pintor, opt.widget)
        activo = bool(indice.data(ROL_VALOR))
        pintor.save()
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(estilo.OK if activo else estilo.TINTA_3))
        pintor.drawEllipse(QPointF(opcion.rect.left() + 8, opcion.rect.center().y()), 3, 3)
        pintor.restore()
