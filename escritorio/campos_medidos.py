"""Anchos numéricos compartidos; el espacio sobrante pertenece al formulario."""
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QLineEdit, QSizePolicy, QSpinBox,
                               QStyle, QStyleOptionComboBox, QTableWidget)

MARGEN_SPIN = 28  # flechas de 18 px, E1 a cada lado y dos bordes de 1 px
MARGEN_CIFRAS = 10  # E1 a cada lado y dos bordes; incluye los 2 px internos de QLineEdit
TOLERANCIA = 4  # redondeos de fuente/escala; no reserva una cifra ni un hueco de formulario


def texto_maximo(widget):
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        if widget.property("digitosColumna"):
            cifras = max(int(widget.property("digitosColumna")), len(str(abs(widget.value()))))
            return widget.prefix() + "8" * cifras + widget.suffix()
        valores = [widget.textFromValue(v) for v in (widget.minimum(), widget.maximum())]
        return max((widget.prefix() + v + widget.suffix() for v in valores),
                   key=widget.fontMetrics().horizontalAdvance)
    cifras = widget.property("cifrasNumericas")
    if cifras:
        return "8" * int(cifras)
    validador = widget.validator()
    if isinstance(validador, QIntValidator):
        return max((str(validador.bottom()), str(validador.top())), key=widget.fontMetrics().horizontalAdvance)
    return None


def ancho_numero(widget):
    if not isinstance(widget, (QSpinBox, QDoubleSpinBox, QLineEdit)):
        return None
    if isinstance(widget, QLineEdit) and isinstance(widget.parentWidget(), (QSpinBox, QDoubleSpinBox)):
        return None
    texto = texto_maximo(widget)
    if texto is None:
        return None
    margen = MARGEN_SPIN if isinstance(widget, (QSpinBox, QDoubleSpinBox)) else MARGEN_CIFRAS
    return widget.fontMetrics().horizontalAdvance(texto) + margen


def ajustar(widget):
    ancho = ancho_numero(widget)
    if ancho is not None and (widget.minimumWidth() != ancho or widget.maximumWidth() != ancho):
        widget.setFixedWidth(ancho)
        padre = widget.parentWidget()
        tabla = padre.parentWidget() if padre is not None else None
        if isinstance(tabla, QTableWidget):
            columna = tabla.property("columnaNumerica")
            if columna is not None:
                columna.programar()


class CamposMedidos(QObject):
    def eventFilter(self, objeto, evento):
        if isinstance(objeto, (QSpinBox, QDoubleSpinBox, QLineEdit)):
            if evento.type() in (QEvent.Type.Show, QEvent.Type.Polish, QEvent.Type.FontChange,
                                 QEvent.Type.StyleChange, QEvent.Type.LayoutRequest):
                ajustar(objeto)
                if isinstance(objeto, (QSpinBox, QDoubleSpinBox)) and not objeto.property("numeroConectado"):
                    objeto.setProperty("numeroConectado", True)
                    objeto.valueChanged.connect(self.cambio_numero)
        return False

    def cambio_numero(self, _valor):
        ajustar(self.sender())


def instalar():
    app = QApplication.instance()
    if app is not None and app.property("camposMedidos") is None:
        politica = CamposMedidos(app)
        app.setProperty("camposMedidos", politica)
        app.installEventFilter(politica)


def ajustar_boton(boton):
    boton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class ColumnaNumerica(QObject):
    """La columna sigue la medida actual del control también tras un cambio de fuente."""
    def __init__(self, tabla, columna):
        super().__init__(tabla)
        self.tabla = tabla
        self.columna = columna
        self._ajustando = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.medir)
        tabla.setProperty("columnaNumerica", self)
        for objeto in (tabla, tabla.viewport(), tabla.horizontalHeader()):
            objeto.installEventFilter(self)
        tabla.horizontalHeader().sectionResized.connect(self.cambio_columna)

    def cambio_columna(self, columna, _antes, _despues):
        if columna == self.columna:
            self.programar()

    def programar(self):
        if not self._ajustando:
            self.timer.start(0)

    def medir(self):
        self._ajustando = True
        try:
            tabla = self.tabla
            medidas = [tabla.horizontalHeader().sectionSizeFromContents(self.columna).width()]
            for row in range(tabla.rowCount()):
                ancho = ancho_numero(tabla.cellWidget(row, self.columna))
                if ancho is not None:
                    medidas.append(ancho)
            tabla.setColumnWidth(self.columna, max(medidas))
        finally:
            self._ajustando = False

    def eventFilter(self, objeto, evento):
        if evento.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange,
                             QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self.programar()
        return False


class ComboMedido(QComboBox):
    def __init__(self):
        super().__init__()
        from .estilo_listas import EstiloLista
        self._midiendo = False
        self._estilo_lista = EstiloLista("Fusion")
        self._estilo_lista.setParent(self)
        self.setStyle(self._estilo_lista)
        self.view().setTextElideMode(Qt.TextElideMode.ElideNone)

    def medir(self):
        if self._midiendo or self.count() == 0:
            return
        self._midiendo = True
        try:
            self.ensurePolished()
            self.view().setFont(self.font())
            texto = max(self.fontMetrics().horizontalAdvance(self.itemText(i)) for i in range(self.count()))
            opcion = QStyleOptionComboBox()
            self.initStyleOption(opcion)
            campo = self.style().subControlRect(
                QStyle.ComplexControl.CC_ComboBox, opcion, QStyle.SubControl.SC_ComboBoxEditField, self)
            extras = max(0, self.width() - campo.width())
            self.setFixedWidth(texto + extras + 2)
            self.view().setMinimumWidth(self.width())
            for i in range(self.count()):
                self.setItemData(i, self.itemText(i), Qt.ItemDataRole.ToolTipRole)
        finally:
            self._midiendo = False

    def changeEvent(self, evento):
        super().changeEvent(evento)
        if evento.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.medir()

    def showPopup(self):
        self.medir()
        super().showPopup()
