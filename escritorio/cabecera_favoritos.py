"""Reparto de la cabecera del dibujo y estado centrado en la fila de pestañas."""
from PySide6.QtCore import QEvent, QObject, QRect, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from PySide6.QtWidgets import QToolBar, QToolButton

from . import estilo
from .paneles import ChipModo


class EstadoModo(ChipModo):
    MARCO = 22  # espacio izquierdo: 10px padding + 6px punto + 6px hueco

    def __init__(self):
        self.color_modo = estilo.ACENTO
        self.modo_actual = "editar"
        super().__init__()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setObjectName("estadoModo")
        self.escalar()

    def escalar(self):
        self.setStyleSheet(
            f"background: transparent; border: none; color: {estilo.TINTA_2};"
            f"font-family: {estilo.FAMILIA_TITULO}; font-size: 11px; font-weight: 700;")
        fuente = QFont(estilo.FUENTE_TITULO)
        fuente.setPixelSize(11)
        fuente.setBold(True)
        fuente.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        self.setFont(fuente)
        self.setFixedHeight(24)

    def sizeHint(self) -> QSize:  # noqa: N802
        texto = self.elegida(self.tope)
        ancho = self.fontMetrics().horizontalAdvance(texto) + self.MARCO + 12
        return QSize(min(self.tope, max(ancho, 48)), self.height())

    def poner(self, modo, texto, ayuda):
        self.modo_actual = modo
        self.color_modo = {
            "editar": estilo.ACENTO, "lectura": estilo.TINTA_2, "simular": estilo.LED_CONSOLA,
            "aviso": estilo.AVISO, "error": estilo.ERROR,
        }.get(modo, estilo.TINTA_2)
        if self.text() != texto:
            self.setText(texto)
        self.setToolTip(ayuda)
        self.setAccessibleName(texto.capitalize())
        self.updateGeometry()
        self.update()

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        sim = self.modo_actual == "simular"
        fondo = QColor(21, 122, 53, 26) if sim else QColor(22, 38, 58, 12)
        tinta = QColor(estilo.SIMULACION_HOVER if sim else estilo.TINTA_2)
        r = QRectF(self.rect())
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(fondo)
        pintor.drawRoundedRect(r, estilo.R_S, estilo.R_S)
        pintor.setBrush(QColor(self.color_modo))
        dot_y = (self.height() - 6) / 2
        if sim:
            pintor.drawEllipse(QRectF(10, dot_y, 6, 6))
        else:
            pintor.drawRoundedRect(QRectF(10, dot_y, 6, 6), 1.5, 1.5)
        pintor.setFont(self.font())
        pintor.setPen(tinta)
        rect = QRect(self.MARCO, 0, max(1, self.width() - self.MARCO - 10), self.height())
        pintor.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.elegida(self.width()))
        pintor.end()


class UbicaModo(QObject):
    def __init__(self, etiqueta, fila, pestanas, luz, menu_cluster=None, estuche=None):
        super().__init__(fila)
        self.etiqueta = etiqueta
        self.fila = fila
        self.pestanas = pestanas
        self.luz = luz
        self.menu_cluster = menu_cluster
        self.estuche = estuche or pestanas
        self._pendiente = False
        self._barras = []
        etiqueta.setParent(fila)
        etiqueta.show()
        for widget in filter(None, (fila, pestanas, luz, etiqueta, menu_cluster, estuche)):
            widget.installEventFilter(self)
        self.ajustar()

    def eventFilter(self, objeto, evento):
        tipos = (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest, QEvent.Type.FontChange,
                 QEvent.Type.DynamicPropertyChange)
        if objeto is self.fila and evento.type() == QEvent.Type.Resize:
            for barra in self._barras_toolbar():
                if barra.objectName() not in ("barraEdicion", "barraSimulacion", "barraVistaDer"):
                    continue
                for accion in barra.actions():
                    if accion.isSeparator():
                        accion.setVisible(True)
        if evento.type() in tipos and not self._pendiente:
            self._pendiente = True
            QTimer.singleShot(0, self.fila, self.ajustar)
        return False

    def ajustar(self):
        try:
            self._extensiones()
            fusion = bool(self.fila.property("fusion"))
            lay = self.fila.layout()
            self.etiqueta.setVisible(not fusion)
            if self.menu_cluster is not None:
                self.menu_cluster.setVisible(not fusion)
            if fusion:
                lay.setEnabled(True)
                lay.setContentsMargins(estilo.E2, 2, estilo.E2, 2)
                lay.setSpacing(estilo.E2)
                return
            w_fila = max(1, self.fila.width())
            h_fila = max(1, self.fila.height())
            # Posición manual precisa de las 3 zonas (izquierda: menú, centro: chip de modo, derecha: estuche vistas)
            if self.menu_cluster is not None and self.estuche is not None:
                lay.setEnabled(False)
                if self.menu_cluster.layout() is not None:
                    self.menu_cluster.layout().activate()
                w_menu = self.menu_cluster.sizeHint().width()
                h_menu = self.menu_cluster.sizeHint().height()
                if self.estuche.layout() is not None:
                    self.estuche.layout().activate()
                w_estuche = self.estuche.sizeHint().width()
                h_estuche = self.estuche.sizeHint().height()
                self.etiqueta.fijar_tope(max(60, w_fila - w_estuche - 24))
                w_chip = self.etiqueta.sizeHint().width()
                h_chip = self.etiqueta.height()
                x_estuche = max(10, w_fila - 10 - w_estuche)
                x_ideal = (w_fila - w_chip) // 2
                min_chip = 10 + w_menu + estilo.E2
                max_chip = x_estuche - estilo.E2 - w_chip
                if min_chip <= x_ideal <= max_chip:
                    x_chip = x_ideal
                    w_menu_real = w_menu
                elif min_chip <= max_chip:
                    x_chip = max(min_chip, min(x_ideal, max_chip))
                    w_menu_real = w_menu
                else:
                    w_menu_real = max(32, min(w_menu, x_estuche - 2 * estilo.E2 - w_chip - 10))
                    x_chip = max(10 + w_menu_real + estilo.E2, x_estuche - estilo.E2 - w_chip)
                self.menu_cluster.setGeometry(10, (h_fila - h_menu) // 2, w_menu_real, h_menu)
                self.etiqueta.setGeometry(x_chip, (h_fila - h_chip) // 2, w_chip, h_chip)
                self.estuche.setGeometry(x_estuche, (h_fila - h_estuche) // 2, w_estuche, h_estuche)
                return
            w_luz = max(self.luz.minimumWidth(), self.luz.sizeHint().width())
            w_nav = self.pestanas.sizeHint().width() + estilo.E2 + w_luz
            self.etiqueta.fijar_tope(max(1, w_fila - w_nav - 3 * estilo.E2))
            w_est = self.etiqueta.sizeHint().width()
            x_ideal = (w_fila - w_nav) // 2
            x_max = w_fila - estilo.E2 - w_est - estilo.E2 - w_nav
            x_nav = max(estilo.E2, min(x_ideal, x_max))
            if lay.contentsMargins().left() != x_nav:
                lay.setContentsMargins(x_nav, 0, estilo.E2, 0)
            lay.activate()
            izquierda = self.luz.geometry().right() + 1 + estilo.E2
            derecha = w_fila - estilo.E2
            disponible = max(1, derecha - izquierda)
            self.etiqueta.fijar_tope(disponible)
            ancho = min(self.etiqueta.sizeHint().width(), disponible)
            x = max(izquierda, derecha - ancho)
            alto = self.etiqueta.height()
            self.etiqueta.setGeometry(x, (h_fila - alto) // 2, ancho, alto)
        finally:
            self._pendiente = False

    def _barras_toolbar(self):
        if not self._barras:
            self._barras = self.fila.window().findChildren(QToolBar)
        return self._barras

    def _extensiones(self):
        hoja = ("QToolButton { padding:0; min-width:0; min-height:0; border:none; }"
                f"QToolButton:hover {{ background:{estilo.HOVER}; }}")
        barras = self._barras_toolbar()
        for barra in barras:
            for boton in barra.findChildren(QToolButton, "qt_toolbar_ext_button"):
                if boton.styleSheet() != hoja:
                    boton.setStyleSheet(hoja)
                    boton.setFixedWidth(estilo.ALTO_CONTROL - 2)
                    boton.setToolTip("Más herramientas")
        for barra in barras:
            if barra.objectName() not in ("barraEdicion", "barraSimulacion"):
                continue
            acciones = barra.actions()
            visibles = [i for i, accion in enumerate(acciones) if not accion.isSeparator()
                        and barra.widgetForAction(accion).isVisible()]
            for i, accion in enumerate(acciones):
                if accion.isSeparator() and accion.isVisible():
                    accion.setVisible(any(j < i for j in visibles) and any(j > i for j in visibles))



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
        minimo = d.ancho_barra(True) + nav + 4 * estilo.E2
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
        visible = self.editable()
        barra.setVisible(visible)
        ancho = d.parentWidget().width() - 2 * estilo.E2
        nav = v.navegacion.sizeHint().width() + estilo.E2 if v.navegacion.isVisibleTo(v) else 0
        barra.compacta = False
        favoritos = barra.sizeHint().width() if visible else 0
        if d.barra_integrada:
            compacto = ancho - favoritos - nav - 4 * estilo.E2 < d.ancho_barra(False)
            d.solo_iconos(compacto)
            disponible = ancho - favoritos - nav - 4 * estilo.E2
            ancho_zoom = d.ancho_barra(True)
            if d.l_zoom.isHidden():
                ancho_zoom += d.l_zoom.sizeHint().width()
            porcentaje = not compacto or disponible >= ancho_zoom
            d.porcentaje_zoom.mostrar(porcentaje)
            barra.compacta = not porcentaje
            favoritos = barra.sizeHint().width() if visible else 0
        else:
            d.porcentaje_zoom.mostrar(True)
        zoom = d.barra.sizeHint().width() + estilo.E2 if d.barra_integrada else 0
        libre = max(0, ancho - zoom - nav - 3 * estilo.E2)
        barra.setMaximumWidth(min(favoritos, libre))
        barra._disponer()
        self._ajustar_ayuda(max(0, libre - favoritos))

    def _ajustar_ayuda(self, libre):
        v = self.v
        texto = v.ayuda.text()
        if texto != self._texto_ayuda:
            self._texto_ayuda = texto
        v.ayuda_pantalla.actualizar(texto, libre)
