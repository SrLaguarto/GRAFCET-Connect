"""Campos compactos y categorías en una fila para Propiedades flotante."""
from PySide6.QtCore import QEvent, QObject, QRect, Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QStyle, QStyleOptionButton

from . import estilo


def campos_transicion(panel, widget):
    layout = QGridLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(estilo.E2)
    layout.addWidget(QLabel("Etiqueta"), 0, 0)
    panel.t_etiqueta.setMaximumWidth(12 * estilo.E4)
    layout.addWidget(panel.t_etiqueta, 0, 1)
    layout.addWidget(panel.t_mostrar, 0, 2, Qt.AlignmentFlag.AlignLeft)
    layout.setColumnStretch(3, 1)
    layout.addWidget(QLabel("Comentario"), 1, 0)
    layout.addWidget(panel.t_comentario, 1, 1, 1, 3)


class CategoriasUnaFila(QObject):
    """Reduce solo huecos y rellenos; las cinco etiquetas mantienen su texto y su fuente."""

    def __init__(self, programador):
        super().__init__(programador)
        self.prog = programador
        self.ocupada = False
        self.firma = None
        self.ancho_minimo = 0
        self.no_cabe = False
        flujo = programador._flujo_carpetas
        flujo.una_fila = True
        flujo.sep = estilo.E1
        flujo.setContentsMargins(0, 0, 0, 0)
        self.viewport = programador._sc_carpetas.viewport()
        self.viewport.installEventFilter(self)
        for boton in programador.categorias.values():
            boton.installEventFilter(self)
        programador._sc_carpetas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def ajustar(self):
        if self.ocupada:
            return
        botones = list(self.prog.categorias.values())
        firma = (self.viewport.width(), tuple(b.font().key() for b in botones), estilo.ALTO_CONTROL_COMPACTO)
        if firma == self.firma:
            return
        self.ocupada = True
        try:
            for relleno in range(10, estilo.E1 - 1, -1):
                hoja = self.prog._hoja_categoria()
                hoja = hoja.replace("padding: 0 10px", f"padding: 0 {relleno}px")
                hoja = hoja.replace("padding: 0 9px", f"padding: 0 {relleno - 1}px")
                for boton in botones:
                    if boton.styleSheet() != hoja:
                        boton.setStyleSheet(hoja)
                    boton.setMinimumWidth(self.ancho_entero(boton))
                ancho = sum(b.minimumWidth() for b in botones) + estilo.E1 * (len(botones) - 1)
                self.ancho_minimo = ancho
                if ancho <= self.viewport.width():
                    break
            self.no_cabe = ancho > self.viewport.width()
            self.firma = firma
            self.prog._flujo_carpetas.invalidate()
            self.prog._ajustar_franja()
        finally:
            self.ocupada = False

    @staticmethod
    def ancho_entero(boton):
        opcion = QStyleOptionButton()
        boton.initStyleOption(opcion)
        ancho = boton.sizeHint().width()
        opcion.rect = QRect(0, 0, ancho, boton.height())
        contenido = boton.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, opcion, boton)
        # Qt reserva una celda de icono de su ancho más 8 px al dibujar la etiqueta.
        # El sizeHint nativo puede reservar menos; se mide el contenido completo, con 1 px de redondeo.
        pide = boton.fontMetrics().horizontalAdvance(boton.text()) + boton.iconSize().width() + 8 + 1
        return ancho + max(0, pide - contenido.width())

    def eventFilter(self, objeto, evento):  # noqa: N802
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.FontChange, QEvent.Type.StyleChange):
            if evento.type() != QEvent.Type.Resize:
                self.firma = None
            self.ajustar()
        return False
