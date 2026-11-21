"""Una ventana de propiedades centrada, con lupa de la escena y paneles desplazables."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QLineF, QObject, QPoint, QPointF, QRect, QRectF, QSignalBlocker, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QPlainTextEdit, QTextEdit,
    QBoxLayout, QFrame, QHBoxLayout, QLayout, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from .interaccion_propiedades import ArrastrePropiedades
from . import estilo
from .diagrama import ANCLA, COL, EVOLUCION_HORIZONTAL, Z_BAR, Z_EDIT, orientaciones, posiciones
from .escena.escena import EscenaIncremental
from .escena.modelo_visual import construir
from .paneles import TituloSeccion, pintar_marcador
from .propiedades import ANCHO_COLUMNA, PanelPropiedades
from .elementos_lupa import ocultar_vecinos
from .medidas_propiedades import ancho_maximo, margen_horizontal

AMPLIACION_MAXIMA = 1.25
MEDIO_TRAZO = 0.8  # la mitad del trazo de 1,6 px de las cajas del dibujo
SENAL_CONDICION = estilo.ACENTO
SENAL_ACCION = estilo.TINTA_2
ALFA_RESALTADO = 0.18

MARCO = 1  # el borde de la ventana: el layout empieza dentro de él

EVENTOS_FONDO = {
    QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
    QEvent.Type.Wheel, QEvent.Type.ContextMenu, QEvent.Type.KeyPress, QEvent.Type.KeyRelease,
    QEvent.Type.Shortcut, QEvent.Type.ShortcutOverride, QEvent.Type.DragEnter, QEvent.Type.DragMove,
    QEvent.Type.Drop, QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd,
}


class Lupa(QWidget):
    """Recorte no interactivo de la escena real, sin las capas de edición de Z_EDIT en adelante."""

    def __init__(self, vista: Any) -> None:
        super().__init__()
        self.vista = vista
        self.origen = QRectF()
        self._escena = EscenaIncremental(self)  # aplica solo la diferencia del modelo visual, como el lienzo
        self._modelo = None
        self._dependencias = None
        self.elemento = None
        self.tallo_transicion: QLineF | None = None
        self.senales: list[tuple[QRectF, str]] = []
        self.recorte: list[QRectF] = []  # rectángulos de la escena que se pintan; vacío: todo lo que cae en `origen`
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def wheelEvent(self, evento: Any) -> None:  # noqa: N802
        evento.accept()

    def transformar(self) -> QTransform:
        if self.origen.isEmpty():
            return QTransform()
        margen = estilo.E3
        ancho = max(1, self.width() - 2 * margen)
        alto = max(1, self.height() - 2 * margen)
        escala = min(AMPLIACION_MAXIMA, ancho / self.origen.width(), alto / self.origen.height())
        centro = self.origen.center()
        t = QTransform()
        t.translate(self.width() / 2, self.height() / 2)
        t.scale(escala, escala)
        t.translate(-centro.x(), -centro.y())
        return t

    def preparar_dibujo(self, modelo: dict[str, Any], dependencias: bool) -> None:
        if modelo is self._modelo and dependencias == self._dependencias:
            return
        self._escena.aplicar(construir(modelo, {}, None, None, None, dependencias))  # (si construir falla, la escena queda como estaba)
        self._modelo, self._dependencias = modelo, dependencias

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        marco = QPainter(self)  # la tarjeta de la vista previa: fondo suave, borde de 1 px y radio R_M, como las de los paneles
        marco.setRenderHint(QPainter.RenderHint.Antialiasing)
        marco.setPen(QPen(QColor(estilo.BORDE), 1))
        marco.setBrush(QColor(estilo.SUPERFICIE))
        marco.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), estilo.R_M, estilo.R_M)
        marco.end()
        if self.origen.isEmpty():
            return
        escena = self._escena
        minimo = Z_BAR if self.tallo_transicion is not None else float("-inf")
        p = QPainter(self)  # antes de ocultar: si falla, no quedan vecinos ocultos (la escena incremental no los rehace)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        ocultos = ocultar_vecinos(escena, self.elemento, Z_EDIT, minimo)
        try:
            t = self.transformar()
            destino = t.mapRect(self.origen)
            if self.tallo_transicion is not None:
                pen = QPen(QColor(COL["text"]), 1.6 * t.m11())
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                p.setPen(pen)
                p.drawLine(t.map(self.tallo_transicion))
            if self.recorte:  # solo el elemento: nada de las cajas vecinas que caen en el encuadre
                zona = QPainterPath()  # (la unión en un solo contorno: con rectángulos sueltos y bordes suavizados se vería una costura)
                for r in self.recorte:
                    trozo = QPainterPath()
                    trozo.addRect(t.mapRect(r))
                    zona = zona.united(trozo)
                p.setClipPath(zona)
            escena.render(p, destino, self.origen, Qt.AspectRatioMode.IgnoreAspectRatio)
            # El resaltado de cada parte, después del dibujo y multiplicando: el fondo blanco de la caja se tiñe (antes lo tapaba y
            # solo asomaba un halo por fuera) y los trazos y el texto siguen negros. La marca, con un poco de holgura; la caja, justa.
            p.setClipping(False)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            p.setPen(Qt.PenStyle.NoPen)
            for rectangulo, color in self.senales:
                relleno = QColor(color)
                relleno.setAlphaF(ALFA_RESALTADO)
                p.setBrush(relleno)
                zona = self.transformar().mapRect(rectangulo)
                if color == SENAL_ACCION:
                    p.drawRect(zona)
                else:
                    p.drawRoundedRect(zona.adjusted(-estilo.E1, -estilo.E1, estilo.E1, estilo.E1), estilo.R_M, estilo.R_M)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        finally:
            for item in ocultos:
                item.show()
            p.end()


class TituloSenal(TituloSeccion):
    """El cuadrado identifica la misma parte que la franja y el resaltado de la lupa."""

    def __init__(self) -> None:
        super().__init__()
        self.senal = estilo.ACENTO

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        QLabel.paintEvent(self, evento)
        p = QPainter(self)
        pintar_marcador(p, self.contentsMargins().left() + self.x_marcador, self.height() / 2, self.senal)
        p.end()


class PanelInterior(QFrame):
    """Una tarjeta: título dentro, arriba, y contenido desplazable. El mínimo del editor nunca agranda la ventana."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("tarjetaFlotante")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(estilo.E3, estilo.E3, estilo.E3, estilo.E3)  # (más el borde de 1 px de la hoja)
        raiz.setSpacing(estilo.E2)  # T3
        self.senal: str | None = None
        self.titulo = TituloSenal()
        self.titulo.setObjectName("tituloPropiedades")
        raiz.addWidget(self.titulo)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("scrollTarjeta")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumSize(0, 0)
        raiz.addWidget(self.scroll, 1)
        self.cuerpo = QWidget()
        self.cuerpo.setObjectName("cuerpoTarjeta")
        self.lay_cuerpo = QVBoxLayout(self.cuerpo)
        self.lay_cuerpo.setContentsMargins(0, 0, 0, 0)
        self.lay_cuerpo.setSpacing(0)
        self.lay_cuerpo.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.scroll.setWidget(self.cuerpo)
        self.setMinimumSize(0, 0)

    def indicar_parte(self, color: str | None) -> None:
        self.senal = color
        self.titulo.senal = color or estilo.ACENTO
        self.titulo.update()
        self.update()

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        super().paintEvent(evento)
        if self.senal is not None:
            p = QPainter(self)
            p.fillRect(QRect(1, estilo.R_M, 3, max(0, self.height() - 2 * estilo.R_M)), QColor(self.senal))
            p.end()

    def alto_necesario(self, justo: bool = False) -> int:
        """Altura del contenido al ancho real, incluido el pie de fórmula y la cabecera. `justo`: lo que pide el contenido en su mínimo (la
        tarjeta de una acción sin valor numérico: sin sumar el alto de las demás páginas del panel)."""
        self.lay_cuerpo.invalidate()
        ancho = max(1, self.scroll.viewport().width())
        contenido = self.cuerpo.minimumSizeHint().height() if justo else max(self.cuerpo.sizeHint().height(), self.cuerpo.minimumSizeHint().height())
        if self.lay_cuerpo.hasHeightForWidth() and not justo:
            contenido = max(contenido, self.lay_cuerpo.totalHeightForWidth(ancho))
        margenes = self.layout().contentsMargins()
        cabecera = self.titulo.sizeHint().height() + self.layout().spacing()
        return contenido + cabecera + margenes.top() + margenes.bottom() + estilo.E1 + 2  # (+2: el borde)


class VentanaFlotante(QFrame):
    """Un marco sobre el área de trabajo completa: vista previa discreta y editores amplios."""

    cerrar_pedido = Signal()

    def __init__(self, padre: QWidget, vista: QWidget) -> None:
        # Popup recibe el clic exterior antes del bloqueo modal; NoMouseReplay evita que llegue al fondo.
        banderas = Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        super().__init__(padre, banderas)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setObjectName("ventanaFlotante")
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QFrame#ventanaFlotante {{ background: {estilo.FONDO}; "
            f"border: 1px solid {estilo.ACENTO}; border-radius: {estilo.R_M}px; }}"
            f"QFrame#lineaCabecera {{ background: {estilo.BORDE}; border: 0; border-radius: 0; }}"
            f"QFrame#tarjetaFlotante {{ background: {estilo.SUPERFICIE_2}; "
            f"border: 1px solid {estilo.BORDE}; border-radius: {estilo.R_M}px; }}"
            # dentro de una tarjeta no queda otro fondo gris: el área desplazable y los subpaneles de Propiedades son transparentes
            f"QScrollArea#scrollTarjeta, QWidget#cuerpoTarjeta {{ background: transparent; }}"
        )
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        self.cabecera = QWidget()
        self.cabecera.setObjectName("cabeceraFlotante")
        fila = QHBoxLayout(self.cabecera)
        fila.setContentsMargins(estilo.E4 - MARCO, estilo.E2, estilo.E2, estilo.E2)
        fila.setSpacing(estilo.E2)
        self.titulo = TituloSeccion()
        self.titulo.setObjectName("tituloPanel")  # el título de sección normal de la aplicación
        fila.addWidget(self.titulo, 1)
        self.b_cerrar = QToolButton()
        self.b_cerrar.setText("✕")
        self.b_cerrar.setCursor(Qt.CursorShape.ArrowCursor)
        self.b_cerrar.setAutoRaise(True)
        self.b_cerrar.setToolTip("Cerrar")
        self.b_cerrar.setAccessibleName("Cerrar la ventana de propiedades")
        self.b_cerrar.clicked.connect(self.cerrar_pedido)
        fila.addWidget(self.b_cerrar, 0, Qt.AlignmentFlag.AlignVCenter)
        raiz.addWidget(self.cabecera)
        self.linea = QFrame()
        self.linea.setObjectName("lineaCabecera")
        self.linea.setFixedHeight(1)
        raiz.addWidget(self.linea)
        self.cuerpo = QWidget()
        fila_cuerpo = QHBoxLayout(self.cuerpo)
        fila_cuerpo.setContentsMargins(estilo.E4 - MARCO, estilo.E4, estilo.E4 - MARCO, estilo.E4 - MARCO)
        fila_cuerpo.setSpacing(estilo.E6)
        self.lupa = Lupa(vista)
        fila_cuerpo.addWidget(self.lupa)
        self.columna = QWidget()
        paneles = QVBoxLayout(self.columna)
        paneles.setContentsMargins(0, 0, 0, 0)
        paneles.setSpacing(estilo.E3)
        self.condicion = PanelInterior()
        self.accion = PanelInterior()
        paneles.addWidget(self.condicion, 1)
        paneles.addWidget(self.accion, 1)
        fila_cuerpo.addWidget(self.columna, 1)
        raiz.addWidget(self.cuerpo, 1)
        self.hide()

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(QPen(QColor(estilo.ACENTO), 1))
        pintor.setBrush(QColor(estilo.FONDO))
        pintor.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), estilo.R_M, estilo.R_M)
        pintor.end()

    def escalar(self) -> None:
        self.cabecera.setFixedHeight(estilo.ALTO_CONTROL + 2 * estilo.E2)
        self.b_cerrar.setFixedSize(estilo.ALTO_CONTROL, estilo.ALTO_CONTROL)


class GestorFlotantes(QObject):
    """Organiza la única ventana de propiedades y su apertura explícita."""

    def __init__(self, ventana: Any) -> None:
        super().__init__(ventana)
        self.w = ventana
        self.vista = ventana.diagrama
        self.superficie = None
        self.panel: PanelPropiedades = ventana._props
        self._panel_pendiente = True
        self._sesion = None
        self.abierto = False
        self.principal: VentanaFlotante | None = None
        self.geometrias: dict[str, QRect] = {}
        self._escala = None
        self._colocando = False
        self._colocar_pendiente = False
        self._vigilando = False
        self._tamano = QSize()
        self.arrastre = None
        self._clic_fuera = False
        self._ocultando = False

    def _crear(self) -> None:
        if self.principal is not None:
            return
        self.superficie = self.w.centralWidget()
        self.w.paginas_es.installEventFilter(self)
        self.superficie.installEventFilter(self)
        self.w.paginas_es.currentChanged.connect(self.actualizar)
        self.panel.setObjectName("panelPropiedadesFlotante")
        self.principal = VentanaFlotante(self.superficie, self.vista)
        self.arrastre = ArrastrePropiedades(self.principal, self.w)
        self.principal.accion.lay_cuerpo.addWidget(self.panel)
        self.panel.show()
        self.panel.destino_bloques = self.principal.condicion.lay_cuerpo
        self.principal.cerrar_pedido.connect(self.cerrar)
        self.panel.prog.franja_cambiada.connect(self.colocar)
        self.panel.accion.prog.franja_cambiada.connect(self.colocar)
        self.panel.alto_cambiado.connect(self.colocar)
        self.vista.vista_cambiada.connect(self.colocar)
        self.panel.setEnabled(self.activo())

    def panel_actual(self) -> PanelPropiedades:
        """Prepara los controles cuando se consultan sin abrir la ventana."""
        if self._panel_pendiente and self.w.edicion is not None:
            self.panel.mostrar(self.w.edicion)
            self._panel_pendiente = False
        return self.panel

    def activo(self) -> bool:
        w = self.w
        return (
            w.modo == "editar"
            and w.edicion is not None and not w.solo_lectura and w.paginas_es.currentIndex() == 0
        )

    def abrir(self, explicito: bool = True) -> None:
        if not self.activo() or (not explicito and not self.abierto):
            return
        if not self.abierto:
            from .sesion_propiedades import SesionPropiedades
            self._sesion = SesionPropiedades(self.w.edicion)
        self.abierto = True
        self.actualizar()

    def cerrar(self) -> None:
        self._cerrar(confirmar=True)

    def _cerrar(self, confirmar: bool) -> None:
        if not self.abierto:
            return
        sesion, self._sesion = self._sesion, None
        foco = QApplication.focusWidget()
        if self.principal is not None and isinstance(foco, (QLineEdit, QPlainTextEdit, QTextEdit)):
            if foco.window() is self.principal:
                if confirmar:
                    foco.clearFocus()
                else:
                    with QSignalBlocker(foco):
                        foco.clearFocus()
        self.abierto = False
        if sesion is not None and sesion.edicion is self.w.edicion:
            sesion.terminar(confirmar)
        if self.w.edicion is not None:
            self.w.edicion.parte_editada = None
        self.ocultar()

    def tras_gesto(self, antes: tuple, despues: tuple) -> None:
        if not self.activo() or not self.abierto:
            return
        mismo = despues == antes and bool(despues[0])
        sin_nada = not antes[0] and antes[1] is None and bool(despues[0])
        if not mismo and not sin_nada:
            self.cerrar()

    def hay_ventanas(self) -> bool:
        return self.principal is not None and self.principal.isVisible()

    def ocultar(self) -> None:
        if self.principal is not None:
            self._ocultando = True
            try:
                self.principal.hide()
            finally:
                self._ocultando = False
        self.geometrias = {}
        if not self._clic_fuera:
            self._vigilar(False)

    def _vigilar(self, on: bool) -> None:
        """Mientras la ventana está abierta, la aplicación nos pasa las teclas Esc (antes que a nadie): la cierran, como su ✕."""
        app = QApplication.instance()
        if app is None or on == self._vigilando:
            return
        self._vigilando = on
        (app.installEventFilter if on else app.removeEventFilter)(self)

    @staticmethod
    def _cancela_con_esc(foco: Any) -> bool:
        """¿Tiene el foco algo a medias que Esc cancela (el campo abierto sobre una pieza de los bloques, el desplegable sobre el dibujo)?"""
        return foco is not None and (hasattr(foco, "cancelado") or hasattr(foco, "cerrado"))

    def _esc(self, evento: Any, receptor: QObject) -> bool:
        """Esc primero cierra un desplegable abierto y, en Propiedades, cancela la sesión."""
        if QApplication.activePopupWidget() not in (None, self.principal):
            return False
        foco = QApplication.focusWidget()
        if foco is not None and foco.window() not in (self.w, self.principal):
            if not isinstance(receptor, QWidget) or receptor.window() not in (self.w, self.principal):
                return False
            foco = receptor  # el foco global puede seguir en el contenedor del popup que acaba de cerrarse
        if evento.type() == QEvent.Type.ShortcutOverride:
            evento.accept()  # (el atajo de Esc de la ventana, que deselecciona, no salta: llega la tecla)
        else:
            self._cerrar(confirmar=False)
        return True

    def _intro(self, evento: Any, receptor: QObject) -> bool:
        if QApplication.activePopupWidget() not in (None, self.principal):
            return False
        if not isinstance(receptor, QWidget) or receptor.window() is not self.principal:
            return False
        modificadores = evento.modifiers()
        multilinea = isinstance(receptor, (QPlainTextEdit, QTextEdit))
        if modificadores != (Qt.KeyboardModifier.ControlModifier if multilinea else Qt.KeyboardModifier.NoModifier):
            return False
        if self._cancela_con_esc(receptor):
            return False
        if evento.type() == QEvent.Type.ShortcutOverride:
            evento.accept()
        else:
            self.cerrar()
        return True

    def actualizar(self) -> None:
        self._panel_pendiente = True
        w = self.w
        if not self.activo():
            self.ocultar()
            return
        if not self.abierto:
            self.ocultar()
            return
        self._crear()
        if self._escala != (w._hoja_escala, estilo.ESCALA):
            self._escala = (w._hoja_escala, estilo.ESCALA)
            self.panel.escalar(w._hoja_escala)
            self.principal.escalar()
        self.panel_actual()
        p, v = self.panel, self.principal
        if p.pagina == "vacio":
            self.ocultar()
            return
        dividida = p._bloques_fuera
        v.titulo.setText(p.titulo.text())
        v.condicion.setVisible(dividida)
        v.condicion.indicar_parte(SENAL_CONDICION if dividida else None)
        v.accion.indicar_parte(SENAL_ACCION if dividida else None)
        v.accion.titulo.setText("Acción" if dividida else p.titulo.text().removeprefix("Propiedades · "))
        if dividida:
            evento = p.objetivo_bloques()[2] == "evento"
            v.titulo.setText("Propiedades · Acción por evento" if evento else "Propiedades · Acción condicionada")
            v.condicion.titulo.setText("Evento" if evento else "Condición")
            p.l_bloques.hide()
        if not v.isVisible():
            self.arrastre.movida = False
            self.arrastre.inicio = None
        v.show()
        self._vigilar(True)
        self.colocar()
        if not self._colocar_pendiente:  # (una sola recolocación diferida aunque se refresque varias veces en la misma vuelta)
            self._colocar_pendiente = True
            QTimer.singleShot(0, self, self._colocar_diferido)

    def _colocar_diferido(self) -> None:
        self._colocar_pendiente = False
        self.colocar()

    def _bloquear_fondo(self, objeto: QObject, evento: Any) -> bool:
        """También rechaza eventos enviados directamente, que eluden la modalidad nativa de Qt."""
        if evento.type() not in EVENTOS_FONDO or not self.hay_ventanas():
            return False
        actual = objeto
        while actual is not None:
            if actual is self.principal:
                return False
            actual = actual.parent()
        actual = objeto
        while actual is not None and actual is not self.w:
            actual = actual.parent()
        if actual is None:
            return False
        evento.accept()
        return True

    def _fuera(self, evento: Any) -> bool:
        tipo = evento.type()
        if self._clic_fuera and tipo == QEvent.Type.MouseButtonRelease:
            self._clic_fuera = False
            if not self.hay_ventanas():
                self._vigilar(False)
            return True
        if tipo != QEvent.Type.MouseButtonPress or not self.hay_ventanas():
            return False
        punto = evento.globalPosition().toPoint()
        popup = QApplication.activePopupWidget()
        cerrar_popup = popup not in (None, self.principal)
        if cerrar_popup and popup.frameGeometry().contains(punto):
            return False
        mascara = self.principal.mask()
        visible = mascara.isEmpty() or mascara.contains(punto - self.principal.pos())
        dentro = visible and self.principal.geometry().contains(punto)
        if dentro and not cerrar_popup:
            return False
        self._clic_fuera = True
        if cerrar_popup:
            popup.hide()
        elif not dentro:
            self.cerrar()
        return True

    def eventFilter(self, objeto: QObject, evento: Any) -> bool:  # noqa: N802
        tipo = evento.type()
        if objeto is self.principal and tipo == QEvent.Type.Hide and not self._ocultando:
            self.cerrar()
        if objeto is self.w and tipo in (QEvent.Type.Hide, QEvent.Type.Close):
            self.ocultar()
            return False
        if self._vigilando and not self._clic_fuera and not self.principal.isVisible():
            self._vigilar(False)
        if self._fuera(evento):
            return True
        if tipo in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            es_esc = evento.key() == Qt.Key.Key_Escape and not evento.modifiers()
            if es_esc and self.hay_ventanas() and self._esc(evento, objeto):
                return True
            intro = evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            if intro and self.hay_ventanas() and self._intro(evento, objeto):
                return True
            return self._bloquear_fondo(objeto, evento)
        if self._bloquear_fondo(objeto, evento):
            return True
        if tipo in (QEvent.Type.Resize, QEvent.Type.Move) and objeto in (self.w, self.superficie, self.w.paginas_es):
            self.colocar()  # (el filtro de la aplicación, mientras la ventana está abierta, ve todos los objetos)
        return False

    def _area(self) -> QRect:
        """Toda el área de trabajo de la aplicación, incluidas las columnas laterales."""
        pagina = self.w.paginas_es
        return QRect(pagina.mapToGlobal(QPoint()), pagina.size())

    def _zonas(self) -> list[tuple[PanelInterior, QRectF]]:
        e, p, v = self.w.edicion, self.panel, self.principal
        if p._bloques_fuera:
            objetivo = p.objetivo_bloques()
            z = e.zonas_propiedades(None, programable=(objetivo[1], objetivo[2]))
            return [(v.condicion, z[objetivo[2]]), (v.accion, z["accion"])] if z else []
        z = e.zonas_propiedades(p.ident)
        return [(v.accion, z["elemento"])] if z else []

    def _marco_ventana(self) -> int:
        """Lo que la ventana gasta sin contar las tarjetas: cabecera, su línea, márgenes del cuerpo y borde."""
        v = self.principal
        return v.cabecera.height() + 1 + 2 * estilo.E4 + 2 * MARCO

    def _marco_tarjeta(self) -> int:
        """Lo que una tarjeta gasta sin contar su contenido: borde, márgenes y título con su hueco."""
        t = self.principal.accion.titulo.sizeHint().height()
        return t + estilo.E2 + 2 * estilo.E3 + 2

    def _dimensionar(self, area: QRect) -> None:
        margen = margen_horizontal(area.width())
        disponible = area.adjusted(margen, estilo.E6, -margen, -estilo.E6)
        disponible.setWidth(min(disponible.width(), ancho_maximo()))
        necesita_formulador = (
            self.panel.pagina == "transicion" or self.panel._bloques_fuera
            or self.panel.accion.caja_numerica.isVisibleTo(self.panel)
        )
        if necesita_formulador:
            # Con dos tarjetas se conserva el alto de apertura, también al aparecer el formulador numérico.
            alto = disponible.height() if self.panel._bloques_fuera else self._alto_formulador(disponible)
            self._tamano = QSize(disponible.width(), alto)
        else:
            ancho = min(40 * estilo.E4, disponible.width())
            campos = self.panel.izq.sizeHint().height()
            if self.panel.der.isVisibleTo(self.panel):
                campos += self.panel.der.sizeHint().height() + estilo.E3
            contenido = max(self.panel.sizeHint().height(), campos)
            alto = contenido + self._marco_ventana() + self._marco_tarjeta() + estilo.E1
            self._tamano = QSize(ancho, min(alto, disponible.height()))

    def _alto_formulador(self, disponible: QRect) -> int:
        """Alto acotado para una ventana con un solo formulador."""
        p = self.panel
        filas = 11 if estilo.ESCALA == "grande" else 9
        contenido = max(p.minimumSizeHint().height(), (filas + 2) * estilo.ALTO_CONTROL)
        tope = max(1, disponible.height() - estilo.E6)
        alto = contenido + self._marco_ventana() + self._marco_tarjeta()
        return min(tope, round(alto * 1.2) if p.pagina == "transicion" else alto)

    def _componer(self) -> None:
        """La vista previa cede sitio al formulador; los campos se apilan solo si falta ancho."""
        v, p = self.principal, self.panel
        v.lupa.setFixedWidth(min(12 * estilo.E4, max(8 * estilo.E4, v.width() // 6)))
        disponible = v.columna.width() - 4 * estilo.E2
        vertical = p.pagina == "transicion" or disponible < 36 * estilo.E4
        direccion = QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight
        p.cuerpo.layout().setDirection(direccion)
        p.cuerpo.layout().setSpacing(estilo.E3)
        p.layout().setContentsMargins(0, 0, 0, 0)
        ancho_campos = max(ANCHO_COLUMNA, p.accion.variable.width()) if p.pagina == "accion" else ANCHO_COLUMNA
        if p.pagina == "accion" and not p.accion.caja_fichas.isHidden():
            ancho_campos = max(ancho_campos, p.accion.disposicion_variable.sizeHint().width())
        p.izq.setMinimumWidth(0 if vertical else ancho_campos)
        p.izq.setMaximumWidth(16777215 if vertical else ancho_campos)
        p.izq.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        p.cuerpo.layout().setAlignment(p.izq, Qt.AlignmentFlag.AlignTop)
        p.cuerpo.layout().setStretch(0, 0)
        p.cuerpo.layout().setStretch(1, 1)
        for interior in (v.condicion, v.accion):
            interior.setMinimumHeight(0)
            interior.setMaximumHeight(16777215)
        v.columna.layout().setStretch(0, 1)
        v.columna.layout().setStretch(1, 1)

    def _repartir_paneles(self) -> None:
        """Reserva contenido real antes de repartir el espacio libre entre los dos editores."""
        v, p = self.principal, self.panel
        if not p._bloques_fuera:
            return
        superior = v.condicion.alto_necesario()
        inferior = v.accion.alto_necesario(justo=not p.accion.caja_numerica.isVisibleTo(p))
        separacion = v.columna.layout().spacing()
        requerido = superior + inferior + separacion
        if requerido <= v.columna.height():
            v.condicion.setMinimumHeight(superior)
            v.accion.setMinimumHeight(inferior)
            if not p.accion.caja_numerica.isVisibleTo(p):
                v.accion.setMaximumHeight(inferior)
                v.columna.layout().setStretch(1, 0)
        v.columna.layout().activate()

    def _origen_lupa(self, zonas: list[tuple[PanelInterior, QRectF]]) -> QRectF:
        origen = QRectF()
        for _, r in zonas:
            origen = origen.united(r)
        caja = self.w.edicion.accion_en_id(self.panel.ident)
        if caja is not None and caja.get("marca"):
            origen = origen.united(QRectF(*caja["marca"]))
        return origen.adjusted(-estilo.E2, -estilo.E2, estilo.E2, estilo.E2)

    def _tallo_transicion(self, origen: QRectF) -> QLineF | None:
        if self.panel.pagina != "transicion":
            return None
        modelo = self.w.edicion.M
        ident = self.panel.ident
        centro = posiciones(modelo).get(ident)
        if centro is None:
            return None
        x, y = centro
        radio = ANCLA / 2
        if orientaciones(modelo)[ident] in EVOLUCION_HORIZONTAL:
            return QLineF(max(origen.left(), x - radio), y, min(origen.right(), x + radio), y)
        return QLineF(x, max(origen.top(), y - radio), x, min(origen.bottom(), y + radio))

    def _recorte(self, origen: QRectF) -> list[QRectF]:
        """Lo que pinta la lupa de una acción: su caja, su marca y, si es la primera unida a la etapa, el trazo de unión."""
        if self.panel.pagina == "transicion":
            return []
        e = self.w.edicion
        caja = e.accion_en_id(self.panel.ident)
        if caja is None:
            return self._recorte_elemento(e, origen)
        x, y, w, h = caja["rect"]
        sitios = [QRectF(x, y, w, h).adjusted(-MEDIO_TRAZO, -MEDIO_TRAZO, MEDIO_TRAZO, MEDIO_TRAZO)]  # hasta el borde exterior del trazo
        if caja.get("marca"):
            sitios.append(QRectF(*caja["marca"]).adjusted(-1, -1, 1, 1))
        if not caja.get("suelta") and caja.get("cabeza") == caja["id"]:
            sitios.append(QRectF(origen.left(), y + h / 2 - 2, x - origen.left() + MEDIO_TRAZO, 4))
        return sitios

    def _recorte_elemento(self, e: Any, origen: QRectF) -> list[QRectF]:
        """Conserva la caja de la etapa y los tramos cortos que salen de ella."""
        ident = self.panel.ident
        z = e.zonas_propiedades(ident).get("elemento")
        pos = posiciones(e.M)
        if z is None or ident not in pos:
            return []
        x, y = pos[ident]
        grosor = 2.0
        return [
            QRectF(z),
            QRectF(x - grosor, origen.top(), 2 * grosor, z.top() - origen.top() + 1),
            QRectF(x - grosor, z.bottom() - 1, 2 * grosor, origen.bottom() - z.bottom() + 1),
            QRectF(z.right() - 1, y - grosor, origen.right() - z.right() + 1, 2 * grosor),
        ]

    def _senales_lupa(self) -> None:
        v, p = self.principal, self.panel
        v.lupa.senales = []
        if p._bloques_fuera:
            caja = self.w.edicion.accion_en_id(p.ident)
            if caja is not None:
                if caja.get("marca"):
                    v.lupa.senales.append((QRectF(*caja["marca"]), SENAL_CONDICION))
                v.lupa.senales.append((QRectF(*caja["rect"]), SENAL_ACCION))
        v.lupa.update()

    def colocar(self) -> None:
        if self.principal is None or self._colocando or not self.principal.isVisible() or self.w.edicion is None:
            return
        if self.w.refrescando:  # `refrescar_edicion` acaba en `actualizar`, que recoloca: no se hace dos veces por cambio
            return
        self._colocando = True
        try:
            v = self.principal
            area = self._area()
            self._dimensionar(area)
            lugar = QRect(v.pos(), self._tamano)
            if not self.arrastre.movida:
                lugar.moveCenter(area.center())
            v.setGeometry(lugar)
            v.layout().activate()
            v.cuerpo.layout().activate()
            self._componer()
            v.cuerpo.layout().activate()
            v.columna.layout().activate()
            self._repartir_paneles()
            self.arrastre.limitar()
            self.geometrias = {"principal": QRect(v.geometry())}
            zonas = self._zonas()
            v.lupa.preparar_dibujo(self.w.edicion.M, self.vista.dependencias)
            v.lupa.origen = self._origen_lupa(zonas)
            v.lupa.elemento = self.panel.ident
            v.lupa.tallo_transicion = self._tallo_transicion(v.lupa.origen)
            v.lupa.recorte = self._recorte(v.lupa.origen)
            v.lupa.update()
            self._senales_lupa()
            v.raise_()
        finally:
            self._colocando = False
