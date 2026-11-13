"""Reparto de la cabecera del dibujo y estado centrado en la fila de pestañas."""
from PySide6.QtCore import QEvent, QObject, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter

from . import estilo
from .paneles import ChipModo


class EstadoModo(ChipModo):
    MARCO = estilo.E4

    def __init__(self):
        self.color_modo = estilo.ACENTO
        super().__init__()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setObjectName("estadoModo")
        self.escalar()

    def escalar(self):
        self.setStyleSheet(
            f"background: transparent; border: none; color: {estilo.TINTA_2};"
            f"font-size: {estilo.T_PEQUENA}px; font-weight: 600;")
        fuente = QFont(self.font())
        fuente.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        self.setFont(fuente)
        self.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO)

    def poner(self, modo, texto, ayuda):
        self.color_modo = {
            "editar": estilo.ACENTO, "lectura": estilo.TINTA_2, "simular": estilo.SIMULACION,
            "aviso": estilo.AVISO, "error": estilo.ERROR,
        }.get(modo, estilo.TINTA_2)
        if self.text() != texto:
            self.setText(texto)
        self.setToolTip(ayuda)
        self.setAccessibleName(texto.capitalize())
        self.update()

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setFont(self.font())
        pintor.setPen(QColor(estilo.TINTA_2))
        rect = QRect(self.MARCO, 0, self.width() - self.MARCO, self.height())
        pintor.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.elegida(self.width()))
        pintor.fillRect(QRect(0, (self.height() - estilo.E2) // 2, estilo.E2, estilo.E2), QColor(self.color_modo))
        pintor.end()


class UbicaModo(QObject):
    def __init__(self, etiqueta, fila, pestanas, luz):
        super().__init__(fila)
        self.etiqueta = etiqueta
        self.fila = fila
        self.pestanas = pestanas
        self.luz = luz
        self._pendiente = False
        etiqueta.setParent(fila)
        etiqueta.show()
        for widget in (fila, pestanas, luz, etiqueta):
            widget.installEventFilter(self)
        self.ajustar()

    def eventFilter(self, objeto, evento):
        tipos = (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest, QEvent.Type.FontChange)
        if evento.type() in tipos and not self._pendiente:
            self._pendiente = True
            QTimer.singleShot(0, self.fila, self.ajustar)
        return False

    def ajustar(self):
        self._pendiente = False
        izquierda = self.pestanas.geometry().right() + estilo.E2
        derecha = self.luz.x() - estilo.E2
        self.etiqueta.fijar_tope(max(1, derecha - izquierda))
        ancho = self.etiqueta.sizeHint().width()
        x = (self.fila.width() - ancho) // 2
        if x < izquierda or x + ancho > derecha:
            x = izquierda
        alto = self.etiqueta.height()
        self.etiqueta.setGeometry(x, (self.fila.height() - alto) // 2, ancho, alto)


class CabeceraFavoritos:
    def __init__(self, ventana):
        self.v = ventana
        self._texto_ayuda = None

    def editable(self):
        return self.v.modo == "editar" and not self.v.solo_lectura

    def integrar_zoom(self):
        v = self.v
        v._zoom_pendiente = False
        d = v.diagrama
        nav = v.navegacion.sizeHint().width() if v.navegacion.isVisibleTo(v) else 0
        ancho = d.parentWidget().width() - 2 * estilo.E2
        minimo = d.ancho_barra(True) + nav + 4 * estilo.E2 + v.b_ayuda.sizeHint().width()
        if self.editable():
            minimo += v.favoritos.minimumSizeHint().width()
        d.integrar_barra(v._cab if ancho >= minimo else None)
        v._alto_cabecera = max(v._alto_cabecera, estilo.ALTO_CONTROL_COMPACTO, d.barra.sizeHint().height())
        v.ayuda.setMinimumHeight(v._alto_cabecera)
        self.ajustar()
        # La nueva escala queda repartida antes de volver; ningún pintado posterior cambia el alto del lienzo.
        d.parentWidget().layout().activate()

    def ajustar(self):
        v = self.v
        d = v.diagrama
        barra = v.favoritos
        barra.setVisible(self.editable())
        ancho = d.parentWidget().width() - 2 * estilo.E2
        nav = v.navegacion.sizeHint().width() + estilo.E2 if v.navegacion.isVisibleTo(v) else 0
        ayuda = v.b_ayuda.sizeHint().width() + estilo.E2
        favoritos = barra.sizeHint().width() if self.editable() else 0
        if d.barra_integrada:
            compacto = ancho - favoritos - nav - ayuda - 3 * estilo.E2 < d.ancho_barra(False)
            d.solo_iconos(compacto)
        zoom = d.barra.sizeHint().width() + estilo.E2 if d.barra_integrada else 0
        libre = max(0, ancho - zoom - nav - ayuda - 3 * estilo.E2)
        barra.setMaximumWidth(min(favoritos, libre))
        barra._disponer()
        self._ajustar_ayuda(max(0, libre - favoritos))

    def _ajustar_ayuda(self, libre):
        v = self.v
        texto = v.ayuda.text()
        if texto != self._texto_ayuda:
            self._texto_ayuda = texto
            v._ayuda_abierta = False
        abierta = v._ayuda_abierta and bool(texto)
        error = bool(texto) and estilo.ERROR in v.ayuda.styleSheet()
        v.ayuda.mostrar_texto = error and not abierta and libre >= estilo.E6 * 4
        v.ayuda.update()
        v.b_ayuda.setText("Ayuda ▴" if abierta else "Ayuda ▾")
        v.b_ayuda.setToolTip("Recoger la ayuda" if abierta else "Leer la ayuda entera")
        v.b_ayuda.setVisible(bool(texto))
        v.ayuda_larga.setText(texto if abierta else "")
        v.ayuda_larga.setVisible(abierta)
