"""Anchos numéricos compartidos; el espacio sobrante pertenece al formulario."""
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
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
    """Una notificación diferida por cambio de fuente; no observa eventos de la aplicación."""
    fuentes_cambiadas = Signal()

    def __init__(self, app):
        super().__init__(app)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fuentes_cambiadas)

    def programar(self):
        if not self.timer.isActive():
            self.timer.start(0)


def instalar():
    app = QApplication.instance()
    if app is None:
        return None
    politica = app.property("camposMedidos")
    if politica is None:
        politica = CamposMedidos(app)
        app.setProperty("camposMedidos", politica)
    return politica


def notificar_fuentes():
    politica = instalar()
    if politica is not None:
        politica.programar()


class MedicionCampo(QObject):
    def __init__(self, campo):
        super().__init__(campo)
        self.campo = campo
        self.firma = None
        self.texto = None
        instalar().fuentes_cambiadas.connect(self.medir)
        if isinstance(campo, (QSpinBox, QDoubleSpinBox)):
            campo.valueChanged.connect(self.cambio_valor)
        QTimer.singleShot(0, self, self.medir)

    def medir(self):
        campo = self.campo
        campo.ensurePolished()
        texto = texto_maximo(campo)
        firma = (campo.font().key(), texto)
        if firma != self.firma:
            self.firma, self.texto = firma, texto
            ajustar(campo)

    def cambio_valor(self, _valor):
        if self.campo.property("digitosColumna") and texto_maximo(self.campo) != self.texto:
            self.medir()


def registrar(campo):
    medicion = campo.property("medicionCampo")
    if medicion is None:
        medicion = MedicionCampo(campo)
        campo.setProperty("medicionCampo", medicion)
    return medicion


class _CampoMedido:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._primera_medida = False
        self.medicion = registrar(self)

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self._primera_medida:
            self._primera_medida = True
            self.medicion.medir()


class SpinMedido(_CampoMedido, QSpinBox):
    pass


class DecimalMedido(_CampoMedido, QDoubleSpinBox):
    pass


class LineaMedida(_CampoMedido, QLineEdit):
    pass


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
        instalar().fuentes_cambiadas.connect(self.programar)
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


class ComboMedido(QComboBox):
    def __init__(self):
        super().__init__()
        self._midiendo = False
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
