"""La nota de reutilización se ve sin pasar a formar parte del nombre editable."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from . import estilo


def ajustar_casillas(tabla):
    """La altura de la fila incluye la casilla real y el margen de su anillo de foco."""
    for fila in range(tabla.rowCount()):
        widget = tabla.cellWidget(fila, 0)
        minimo = tabla.fontMetrics().height()
        if widget is not None:
            widget.ensurePolished()
            widget.casilla.ensurePolished()
            minimo = max(minimo, widget.minimumSizeHint().height())
        tabla.setRowHeight(fila, max(estilo.ALTO_FILA, minimo + 2 * estilo.E1))


class NombrePropuesto(QStyledItemDelegate):
    def paint(self, pintor, opcion, indice):
        opt = QStyleOptionViewItem(opcion)
        self.initStyleOption(opt, indice)
        nota = indice.data(Qt.ItemDataRole.StatusTipRole)
        if nota:
            opt.text += " · " + nota
        estilo = opt.widget.style() if opt.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, pintor, opt.widget)
