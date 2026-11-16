"""La nota de reutilización se ve sin pasar a formar parte del nombre editable."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem


class NombrePropuesto(QStyledItemDelegate):
    def paint(self, pintor, opcion, indice):
        opt = QStyleOptionViewItem(opcion)
        self.initStyleOption(opt, indice)
        nota = indice.data(Qt.ItemDataRole.StatusTipRole)
        if nota:
            opt.text += " · " + nota
        estilo = opt.widget.style() if opt.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, pintor, opt.widget)
