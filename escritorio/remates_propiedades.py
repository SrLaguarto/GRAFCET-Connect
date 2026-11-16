"""Distribuciones compartidas por Propiedades inferior y flotante."""
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from . import estilo
from .bloques import FlowLayout
from .paneles import EtiquetaElidida


class AvisoFormula(EtiquetaElidida):
    def __init__(self):
        super().__init__(ancho_maximo=10 ** 6)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(0, self.fontMetrics().height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def texto_visible(self):
        texto = " ".join(self.text().splitlines())
        return self.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideRight, self.width())

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setFont(self.font())
        pintor.setPen(self.palette().color(self.foregroundRole()))
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
        pintor.drawText(self.rect(), flags, self.texto_visible())
        pintor.end()


class FlujoCategorias(FlowLayout):
    """Evita una última fila con una categoría suelta cuando caben repartidas en dos."""

    def _filas(self, ancho):
        filas = [[]]
        usado = 0
        for item in self._items:
            if item.widget() is not None and item.widget().isHidden():
                continue
            w = item.sizeHint().width()
            if filas[-1] and usado + self.sep + w > ancho:
                filas.append([])
                usado = 0
            usado += w + (self.sep if filas[-1] else 0)
            filas[-1].append(item)
        if len(filas) > 1 and len(filas[-1]) == 1 and len(filas[-2]) >= 3:
            anterior = filas[-2][-1]
            ultimo = filas[-1][0]
            if anterior.sizeHint().width() + self.sep + ultimo.sizeHint().width() <= ancho:
                filas[-1].insert(0, filas[-2].pop())
        return filas

    def _colocar(self, rect, solo_medir):
        y = rect.y()
        for fila in self._filas(rect.width()):
            x = rect.x()
            alto = max((item.sizeHint().height() for item in fila), default=0)
            for item in fila:
                tamano = item.sizeHint()
                if not solo_medir:
                    item.setGeometry(QRect(QPoint(x, y), tamano))
                x += tamano.width() + self.sep
            y += alto + self.sep
        return max(0, y - self.sep - rect.y())


class FilaValor(FlowLayout):
    """Selector y fichas centrados entre sí; el valor baja entero cuando falta ancho."""

    def __init__(self, parent):
        super().__init__(parent, estilo.E2)

    def sizeHint(self):
        items = [item for item in self._items if not item.widget().isHidden()]
        ancho = sum(item.sizeHint().width() for item in items) + self.sep * max(0, len(items) - 1)
        alto = max((item.sizeHint().height() for item in items), default=0)
        return QSize(ancho, alto)

    def _colocar(self, rect, solo_medir):
        items = [item for item in self._items if not item.widget().isHidden()]
        if not items:
            return 0
        anchos = [min(item.sizeHint().width(), rect.width()) for item in items]
        alturas = [item.sizeHint().height() for item in items]
        cabe = sum(anchos) + self.sep * (len(items) - 1) <= rect.width()
        x, y = rect.x(), rect.y()
        alto = max(alturas) if cabe else sum(alturas) + self.sep * (len(items) - 1)
        for item, ancho, altura in zip(items, anchos, alturas):
            arriba = y + (alto - altura) // 2 if cabe else y
            if not solo_medir:
                item.setGeometry(QRect(x, arriba, ancho, altura))
            if cabe:
                x += ancho + self.sep
            else:
                y += altura + self.sep
        return alto


class RematesAccion(QObject):
    """La explicación abarca el panel; la columna de campos admite el valor booleano a su lado."""

    def __init__(self, panel, raiz, ancho_columna):
        super().__init__(panel)
        self.panel = panel
        self.ancho_columna = ancho_columna
        self.activa = False
        self.cabecera = QWidget(panel)
        lay = QVBoxLayout(self.cabecera)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(estilo.E1)
        for etiqueta in (panel.accion.b_etapa, panel.accion.frase):
            panel.accion.layout().removeWidget(etiqueta)
            lay.addWidget(etiqueta)
        panel.accion.frase.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        raiz.insertWidget(raiz.indexOf(panel.cuerpo), self.cabecera)
        self.cabecera.hide()
        panel.cuerpo.installEventFilter(self)

    def mostrar(self, activa):
        self.activa = activa
        self.cabecera.setVisible(activa)
        self._columna()

    def _columna(self):
        p = self.panel
        ancho = self.ancho_columna
        if self.activa:
            ancho = max(ancho, p.accion.variable.width())
        if self.activa and not p.accion.caja_fichas.isHidden():
            selector = max(p.accion.variable.width(), p.accion.variable.sizeHint().width())
            pide = selector + p.accion.caja_fichas.sizeHint().width() + estilo.E2
            ancho = max(ancho, pide)
        ancho = min(ancho, max(self.ancho_columna, p.cuerpo.width()))
        if p.izq.width() != ancho:
            p.izq.setFixedWidth(ancho)

    def eventFilter(self, objeto, evento):
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            self._columna()
        return False
