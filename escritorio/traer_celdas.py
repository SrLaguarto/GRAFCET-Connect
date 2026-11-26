"""La nota de reutilización y la etiqueta «auto» se ven sin pasar a formar parte del nombre editable."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from . import estilo

ROL_AUTO = Qt.ItemDataRole.UserRole + 7


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
        es_auto = bool(indice.data(ROL_AUTO))
        editable = bool(indice.flags() & Qt.ItemFlag.ItemIsEditable)
        tiene_fondo_aviso = opt.backgroundBrush.style() != Qt.BrushStyle.NoBrush
        pintor.save()
        estilo_q = opt.widget.style() if opt.widget else QApplication.style()
        estilo_q.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, pintor, opt.widget)
        if editable and not tiene_fondo_aviso:
            caja = QRectF(opt.rect).adjusted(4, 3, -4, -3)
            pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pintor.setBrush(QColor(estilo.SUPERFICIE))
            pintor.setPen(QPen(QColor(estilo.BORDE_FUERTE), 1))
            pintor.drawRoundedRect(caja, 4, 4)
        texto = opt.text + (" · " + nota if nota else "")
        r_texto = opt.rect.adjusted(10 if editable else 6, 0, -8, 0)
        if es_auto and not tiene_fondo_aviso:
            fuente_tag = QFont(opt.font)
            px = opt.font.pixelSize()
            fuente_tag.setPixelSize(max(10, px - 1 if px > 0 else 11))
            fuente_tag.setBold(True)
            ancho_tag = QFontMetrics(fuente_tag).horizontalAdvance("auto") + 14
            alto_tag = min(18, max(15, opt.rect.height() - 10))
            x_tag = opt.rect.left() + opt.rect.width() - ancho_tag - 8
            y_tag = opt.rect.top() + (opt.rect.height() - alto_tag) // 2
            rect_tag = QRectF(x_tag, y_tag, ancho_tag, alto_tag)
            pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pintor.setBrush(QColor(estilo.ACENTO_SUAVE))
            pintor.setPen(QPen(QColor(estilo.ACENTO_BORDE), 1))
            pintor.drawRoundedRect(rect_tag, alto_tag / 2, alto_tag / 2)
            pintor.setFont(fuente_tag)
            pintor.setPen(QColor(estilo.ACENTO_OSCURO))
            pintor.drawText(rect_tag, int(Qt.AlignmentFlag.AlignCenter), "auto")
            r_texto.setRight(max(r_texto.left() + 20, x_tag - 6))
        fuente_txt = QFont(opt.font)
        if editable:
            fuente_txt.setWeight(QFont.Weight.DemiBold)
        pintor.setFont(fuente_txt)
        color_txt = opt.palette.color(QPalette.ColorRole.Text)
        fg = indice.data(Qt.ItemDataRole.ForegroundRole)
        if isinstance(fg, QColor):
            color_txt = fg
        elif isinstance(fg, QBrush):
            color_txt = fg.color()
        pintor.setPen(color_txt)
        elidido = QFontMetrics(fuente_txt).elidedText(texto, Qt.TextElideMode.ElideRight, max(16, r_texto.width()))
        pintor.drawText(r_texto, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), elidido)
        pintor.restore()

    def updateEditorGeometry(self, editor, opcion, _indice):
        editor.setGeometry(opcion.rect.adjusted(4, 3, -4, -3))
