"""Una ventana de propiedades centrada, con lupa de la escena y paneles desplazables."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QLineF, QObject, QPoint, QPointF, QRect, QRectF, QSignalBlocker, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTextEdit,
    QBoxLayout, QFrame, QHBoxLayout, QLayout, QScrollArea, QSizePolicy, QStackedLayout, QToolButton, QVBoxLayout, QWidget,
)
from shiboken6 import isValid

from .interaccion_propiedades import ArrastrePropiedades
from . import estilo
from .diagrama import ANCLA, COL, EVOLUCION_HORIZONTAL, Z_BAR, Z_EDIT, orientaciones, posiciones
from .escena.escena import EscenaIncremental
from .escena.modelo_visual import construir
from .paneles import TituloSeccion, pintar_marcador
from .propiedades import ANCHO_COLUMNA, PanelPropiedades
from .elementos_lupa import ocultar_vecinos
from .medidas_propiedades import ancho_maximo, margen_horizontal
from .partes_propiedades import ConmutadorPartes, PiePropiedades

AMPLIACION_MAXIMA = 1.25
FRANJA_FRACCION = 0.25  # lo más alto que es la vista previa: una cuarta parte del alto del área de trabajo (E8)
MEDIO_TRAZO = 0.8  # la mitad del trazo de 1,6 px de las cajas del dibujo
SENAL_CONDICION = estilo.SENAL_CONDICION
SENAL_ACCION = estilo.SENAL_ACCION
ALFA_RESALTADO = 0.18

MARCO = 1  # el borde de la ventana: el layout empieza dentro de él

EVENTOS_FONDO = {
    QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
    QEvent.Type.Wheel, QEvent.Type.ContextMenu, QEvent.Type.KeyPress, QEvent.Type.KeyRelease,
    QEvent.Type.Shortcut, QEvent.Type.ShortcutOverride, QEvent.Type.DragEnter, QEvent.Type.DragMove,
    QEvent.Type.Drop, QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd,
}


class Lupa(QWidget):
    """Recorte de la escena real, sin las capas de edición de Z_EDIT en adelante. Solo responde a un clic en la marca o en la caja de una
    acción de dos partes (`parte_pulsada`): cambia la parte que se edita."""

    parte_pulsada = Signal(str)  # «formula» (la marca: condición o evento) o «accion» (la caja)

    def __init__(self, vista: Any) -> None:
        super().__init__()
        self.vista = vista
        self.origen = QRectF()
        self._escena = EscenaIncremental(self)  # aplica solo la diferencia del modelo visual, como el lienzo
        self._modelo = None
        self._dependencias = None
        self.elemento = None
        self.tallo_transicion: QLineF | None = None
        self.senales: list[tuple[QRectF, str, bool]] = []  # (zona de la escena, color, es la caja): la parte que se edita, en su color; la otra, en gris
        self.partes: list[tuple[QRectF, str]] = []  # (zona de la escena, parte) donde un clic cambia de parte
        self.recorte: list[QRectF] = []  # rectángulos de la escena que se pintan; vacío: todo lo que cae en `origen`
        self.margen = estilo.E2
        self.texto_esquina = ""  # «Etapa N» en la esquina inferior derecha en pastilla (.pv-badge-corner)
        self.pista_esquina = ""  # «Clic en la bandera o en la caja para alternar» en la izquierda (.pv-hint-corner)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def wheelEvent(self, evento: Any) -> None:  # noqa: N802
        evento.accept()

    def mousePressEvent(self, evento: Any) -> None:  # noqa: N802
        """Un clic sobre la marca o la caja de la acción elige esa parte (la caja gana si se solapan)."""
        evento.accept()
        if evento.button() != Qt.MouseButton.LeftButton or not self.partes or self.origen.isEmpty():
            return
        inversa, ok = self.transformar().inverted()
        if not ok:
            return
        punto = inversa.map(evento.position())
        for zona, parte in sorted(self.partes, key=lambda x: x[1] != "accion"):
            if zona.contains(punto):
                self.parte_pulsada.emit(parte)
                return

    def transformar(self) -> QTransform:
        if self.origen.isEmpty():
            return QTransform()
        margen = self.margen
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
        marco = QPainter(self)  # franja plana blanca `.pv-strip` con filete inferior de 1 px (sin tarjeta redondeada)
        marco.fillRect(self.rect(), QColor("#ffffff"))
        marco.setPen(QColor("#cdd6e0"))
        marco.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        marco.end()
        if self.origen.isEmpty():
            self._pintar_esquina()
            return
        escena = self._escena
        minimo = Z_BAR if self.tallo_transicion is not None else float("-inf")
        p = QPainter(self)
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
            if self.recorte:
                zona = QPainterPath()
                for r in self.recorte:
                    trozo = QPainterPath()
                    trozo.addRect(t.mapRect(r))
                    zona = zona.united(trozo)
                p.setClipPath(zona)
            escena.render(p, destino, self.origen, Qt.AspectRatioMode.IgnoreAspectRatio)
            p.setClipping(False)
            for rectangulo, color, es_caja in self.senales:
                zona = self.transformar().mapRect(rectangulo)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
                relleno = QColor(color)
                relleno.setAlphaF(0.14 if es_caja else 0.16)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(relleno)
                if es_caja:
                    p.drawRect(zona)
                    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(color), 2.0))
                    p.drawRect(zona)
                else:
                    p.drawRoundedRect(zona.adjusted(-4, -2, 4, 2), 4, 4)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        finally:
            for item in ocultos:
                item.show()
            p.end()
        self._pintar_esquina()

    def _pintar_esquina(self) -> None:
        if not self.texto_esquina and not self.pista_esquina:
            return
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        f = p.font()
        f.setPixelSize(11)
        if self.pista_esquina:
            f.setWeight(f.Weight.Normal)
            p.setFont(f)
            p.setPen(QColor("#5b6b7d"))
            p.drawText(self.rect().adjusted(12, 4, -12, -6),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self.pista_esquina)
        if self.texto_esquina:
            f.setWeight(f.Weight.DemiBold)
            p.setFont(f)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(self.texto_esquina) + 16
            th = fm.height() + 4
            rb = QRectF(self.width() - 12 - tw, self.height() - 6 - th, tw, th)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#eef2f6"))
            p.drawRoundedRect(rb, 4, 4)
            p.setPen(QColor("#4a5b6e"))
            p.drawText(rb, Qt.AlignmentFlag.AlignCenter, self.texto_esquina)
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
    """Contenedor plano blanco de borde a borde para el editor de bloques o los campos de la ventana."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("tarjetaFlotante")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._raiz = QVBoxLayout(self)
        self._raiz.setContentsMargins(0, 0, 0, 0)
        self._raiz.setSpacing(0)
        self.senal: str | None = None
        self.conmutador: QWidget | None = None
        self.titulo = TituloSenal()
        self.titulo.setObjectName("tituloPropiedades")
        self.titulo.hide()
        self.fila_titulo = QHBoxLayout()
        self.fila_titulo.setContentsMargins(0, 0, 0, 0)
        self.fila_titulo.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("scrollTarjeta")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumSize(0, 0)
        self._raiz.addWidget(self.scroll, 1)
        self.cuerpo = QWidget()
        self.cuerpo.setObjectName("cuerpoTarjeta")
        self.lay_cuerpo = QVBoxLayout(self.cuerpo)
        self.lay_cuerpo.setContentsMargins(0, 0, 0, 0)
        self.lay_cuerpo.setSpacing(0)
        self.scroll.setWidget(self.cuerpo)
        self.setMinimumSize(0, 0)

    def poner_margen(self, px: int) -> None:
        self.lay_cuerpo.setContentsMargins(px, px, px, px)

    def alto_titulo(self) -> int:
        return 0


class VentanaFlotante(QFrame):
    """Ventana modal limpia de Propiedades (`.gc-dialog` 2.0.1):
    barra de título blanca + lupa edge-to-edge + subcabecera opcional + cuerpo plano + comentario (transición) + pie Aceptar/Cancelar."""

    cerrar_pedido = Signal()
    cancelar_pedido = Signal()

    def __init__(self, padre: QWidget, vista: QWidget) -> None:
        banderas = Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        super().__init__(padre, banderas)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setObjectName("ventanaFlotante")
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QFrame#ventanaFlotante {{ background: #ffffff; border: 1px solid #9aa9ba; border-radius: 10px; }}"
            f"QWidget#cabeceraFlotante {{ background: #ffffff; border: 0; border-top-left-radius: 10px; border-top-right-radius: 10px; }}"
            f"QFrame#lineaCabecera {{ background: #cdd6e0; border: 0; }}"
            f"QFrame#subcabeceraFlotante {{ background: #f6f8fb; border: 0; border-bottom: 1px solid #cdd6e0; }}"
            f"QFrame#tarjetaFlotante {{ background: #ffffff; border: 0; border-radius: 0; }}"
            f"QScrollArea#scrollTarjeta, QWidget#cuerpoTarjeta {{ background: #ffffff; border: 0; }}"
            f"QLineEdit#etiquetaInline {{ min-height: 22px; max-height: 24px; padding: 1px 6px; "
            f"border-radius: 4px; border: 1px solid #d8e0ea; background: #f6f8fb; color: #4a5a6d; font-weight: 600; }}"
            f"QLineEdit#etiquetaInline[readOnly='false'] {{ border-color: #cdd6e0; background: #ffffff; "
            f"color: #16263a; }}"
            f"QLineEdit#etiquetaInline[readOnly='false']:focus {{ background: #ffffff; "
            f"border-color: {estilo.ACENTO}; }}"
            f"QToolButton#cerrarFlotante {{ border: 0; border-radius: 5px; background: transparent; color: #4a5b6e; font-size: 14px; }}"
            f"QToolButton#cerrarFlotante:hover {{ background: #e4ecf3; color: #16263a; }}"
            f"QFrame#pieDialogoFlotante {{ background: #f6f8fb; border: 0; border-top: 1px solid #cdd6e0; "
            f"border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; }}"
            f"QPushButton#botonCancelarFlotante {{ min-height: 26px; max-height: 28px; background: #ffffff; color: #4a5b6e; "
            f"border: 1px solid #7b8a9c; border-radius: 5px; padding: 0 13px; font-size: 12px; font-weight: 600; }}"
            f"QPushButton#botonCancelarFlotante:hover {{ background: #e4ecf3; color: #16263a; }}"
            f"QPushButton#botonAceptarFlotante {{ min-height: 26px; max-height: 28px; background: {estilo.ACENTO}; color: #ffffff; "
            f"border: 1px solid {estilo.ACENTO_OSCURO}; border-radius: 5px; padding: 0 15px; font-size: 12px; font-weight: 600; }}"
            f"QPushButton#botonAceptarFlotante:hover {{ background: {estilo.ACENTO_OSCURO}; }}"
        )
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(MARCO, MARCO, MARCO, MARCO)
        raiz.setSpacing(0)

        # -- 1. Barra de título blanca (`.gc-titlebar`) --
        self.cabecera = QWidget()
        self.cabecera.setObjectName("cabeceraFlotante")
        self.cabecera.setFixedHeight(40)
        fila = QHBoxLayout(self.cabecera)
        fila.setContentsMargins(14, 0, 10, 0)
        fila.setSpacing(8)
        self.titulo = TituloSeccion()
        self.titulo.setObjectName("tituloPanel")
        fila.addWidget(self.titulo)

        self.caja_etiqueta = QWidget()
        self.caja_etiqueta.setStyleSheet("background: transparent;")
        el = QHBoxLayout(self.caja_etiqueta)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(7)
        sep = QLabel("|")
        sep.setStyleSheet("color: #cdd6e0; background: transparent;")
        l_et = QLabel("Etiqueta")
        l_et.setStyleSheet("color: #5b6b7d; font-size: 12px; background: transparent;")
        el.addWidget(sep)
        el.addWidget(l_et)
        self._lay_etiqueta = el
        self.caja_etiqueta.hide()
        fila.addWidget(self.caja_etiqueta)

        fila.addStretch(1)
        self.b_cerrar = QToolButton()
        self.b_cerrar.setObjectName("cerrarFlotante")
        self.b_cerrar.setText("✕")
        self.b_cerrar.setFixedSize(26, 26)
        self.b_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_cerrar.setAutoRaise(True)
        self.b_cerrar.setToolTip("Cancelar y cerrar (Esc)")
        self.b_cerrar.setAccessibleName("Cerrar la ventana de propiedades")
        self.b_cerrar.clicked.connect(self.cancelar_pedido)
        fila.addWidget(self.b_cerrar, 0, Qt.AlignmentFlag.AlignVCenter)
        raiz.addWidget(self.cabecera)

        self.linea = QFrame()
        self.linea.setObjectName("lineaCabecera")
        self.linea.setFixedHeight(1)
        raiz.addWidget(self.linea)

        # -- 2. Cuerpo sin márgenes exteriores (lupa + subcabecera + editor + comentario) --
        self.cuerpo = QWidget()
        self.cuerpo.setStyleSheet("background: #ffffff;")
        fila_cuerpo = QVBoxLayout(self.cuerpo)
        fila_cuerpo.setContentsMargins(0, 0, 0, 0)
        fila_cuerpo.setSpacing(0)

        self.lupa = Lupa(vista)
        fila_cuerpo.addWidget(self.lupa)

        # Subcabecera `.sub-header` (conmutador Evento|Acción o título Condición/Acción + selector variable destino)
        self.subcabecera = QFrame()
        self.subcabecera.setObjectName("subcabeceraFlotante")
        self.subcabecera.setFixedHeight(42)
        sh = QHBoxLayout(self.subcabecera)
        sh.setContentsMargins(14, 0, 14, 0)
        sh.setSpacing(10)

        self.conmutador = ConmutadorPartes([("formula", "Evento", estilo.ACENTO), ("accion", "Acción", estilo.ACENTO)])
        self.conmutador.hide()
        sh.addWidget(self.conmutador)

        self.l_sub_titulo = TituloSeccion("Condición", con_marcador=False)
        self.l_sub_titulo.setStyleSheet(f"font-family: {estilo.FAMILIA_TITULO}; font-size: 14px; font-weight: 600; color: {estilo.ACENTO}; background: transparent;")
        self.l_sub_titulo.hide()
        sh.addWidget(self.l_sub_titulo)

        sh.addStretch(1)

        self.caja_dest = QWidget()
        self.caja_dest.setStyleSheet("background: transparent;")
        dl = QHBoxLayout(self.caja_dest)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(7)
        self.l_dest = QLabel("Variable destino:")
        self.l_dest.setStyleSheet("color: #5b6b7d; font-size: 12px; background: transparent;")
        dl.addWidget(self.l_dest)
        self._lay_dest = dl
        self.caja_dest.hide()
        sh.addWidget(self.caja_dest)
        self.subcabecera.hide()
        fila_cuerpo.addWidget(self.subcabecera)

        self.columna = QWidget()
        self.paneles = QStackedLayout(self.columna)
        self.paneles.setContentsMargins(0, 0, 0, 0)
        self.condicion = PanelInterior()
        self.accion = PanelInterior()
        self.paneles.addWidget(self.condicion)
        self.paneles.addWidget(self.accion)
        self.paneles.setCurrentWidget(self.accion)
        self.conmutadores: dict[PanelInterior, ConmutadorPartes] = {self.condicion: self.conmutador}
        self.condicion.conmutador = self.conmutador
        self.accion.conmutador = self.conmutador
        fila_cuerpo.addWidget(self.columna, 1)

        self.pie = PiePropiedades()
        fila_cuerpo.addWidget(self.pie)
        self.pie.hide()
        raiz.addWidget(self.cuerpo, 1)

        # -- 3. Pie del diálogo (`.dialog-footer`: pista a la izquierda + Cancelar / Aceptar a la derecha) --
        self.pie_dialogo = QFrame()
        self.pie_dialogo.setObjectName("pieDialogoFlotante")
        self.pie_dialogo.setFixedHeight(44)
        pd = QHBoxLayout(self.pie_dialogo)
        pd.setContentsMargins(14, 0, 14, 0)
        pd.setSpacing(8)
        self.l_pie_pista = QLabel("Intro o clic fuera confirma · Esc cancela")
        self.l_pie_pista.setStyleSheet("color: #5b6b7d; font-size: 11px; background: transparent;")
        pd.addWidget(self.l_pie_pista)
        pd.addStretch(1)
        self.b_cancelar = QPushButton("Cancelar")
        self.b_cancelar.setObjectName("botonCancelarFlotante")
        self.b_cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_cancelar.setToolTip("Descartar los cambios de esta apertura y cerrar (Esc)")
        self.b_cancelar.setAccessibleName("Cancelar y cerrar la ventana de propiedades")
        self.b_cancelar.clicked.connect(self.cancelar_pedido)
        pd.addWidget(self.b_cancelar)
        self.b_aceptar = QPushButton("Aceptar")
        self.b_aceptar.setObjectName("botonAceptarFlotante")
        self.b_aceptar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_aceptar.setToolTip("Confirmar y cerrar (Intro)")
        self.b_aceptar.setAccessibleName("Aceptar y cerrar la ventana de propiedades")
        self.b_aceptar.clicked.connect(self.cerrar_pedido)
        pd.addWidget(self.b_aceptar)
        raiz.addWidget(self.pie_dialogo)
        self.hide()

    def poner_etiqueta(self, campo: QLineEdit) -> None:
        """Coloca el campo «Etiqueta» de la transición inline en la barra de título (`.lbl-inline`)."""
        campo.setObjectName("etiquetaInline")
        campo.setFixedWidth(56)
        campo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lay_etiqueta.addWidget(campo)

    def poner_variable_destino(self, selector: QWidget) -> None:
        """Adopta el selector de variable de la acción dentro de la subcabecera (`.dest-picker`)."""
        self._lay_dest.addWidget(selector)

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(QPen(QColor("#9aa9ba"), 1))
        pintor.setBrush(QColor("#ffffff"))
        pintor.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 10, 10)
        pintor.end()

    def escalar(self) -> None:
        self.cabecera.setFixedHeight(40)
        self.b_cancelar.setFixedHeight(28)
        self.b_aceptar.setFixedHeight(28)
        self.b_cerrar.setFixedSize(26, 26)


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
        self._franja = 0  # el alto de la vista previa en este momento
        self._parte = "formula"  # la parte que se edita de una acción de dos partes: «formula» (condición o evento) o «accion»
        self._parte_de: str | None = None  # la acción a la que corresponde `_parte`
        self.arrastre = None
        self._clic_fuera = False
        self._ocultando = False
        self.w.destroyed.connect(self._desmontar)

    def _desmontar(self) -> None:
        self.principal = None
        self._vigilar(False)

    def _al_destruir_principal(self) -> None:
        self.principal = None
        self._vigilar(False)

    def _crear(self) -> None:
        if self.principal is not None:
            return
        self.superficie = self.w.centralWidget()
        self.w.paginas_es.installEventFilter(self)
        self.superficie.installEventFilter(self)
        self.w.paginas_es.currentChanged.connect(self.actualizar)
        self.panel.setObjectName("panelPropiedadesFlotante")
        self.principal = VentanaFlotante(self.superficie, self.vista)
        self.principal.destroyed.connect(self._al_destruir_principal)
        self.arrastre = ArrastrePropiedades(self.principal, self.w)
        self.principal.accion.lay_cuerpo.addWidget(self.panel)
        self.principal.poner_etiqueta(self.panel.t_etiqueta)
        self.principal.pie.poner(None, None, self.panel.t_comentario)
        self.panel.accion._variable_adoptada = True
        self.principal.poner_variable_destino(self.panel.accion.variable)
        self.panel.show()
        self.panel.destino_bloques = self.principal.condicion.lay_cuerpo
        self.principal.cerrar_pedido.connect(self.cerrar)
        self.principal.cancelar_pedido.connect(lambda: self._cerrar(confirmar=False))
        self.panel.prog.franja_cambiada.connect(self.colocar)
        self.panel.accion.prog.franja_cambiada.connect(self.colocar)
        self.panel.alto_cambiado.connect(self.colocar)
        self.principal.lupa.parte_pulsada.connect(self.elegir_parte)
        for c in self.principal.conmutadores.values():
            c.elegida.connect(self.elegir_parte)
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
            self._parte = "formula"  # una sesión nueva empieza por la condición o el evento (salvo que se pida otra parte: `parte_pedida`)
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
            self.w.edicion.parte_pedida = None
        self.ocultar()

    def tras_gesto(self, antes: tuple, despues: tuple) -> None:
        if not self.activo() or not self.abierto:
            return
        mismo = despues == antes and bool(despues[0])
        sin_nada = not antes[0] and antes[1] is None and bool(despues[0])
        if not mismo and not sin_nada:
            self.cerrar()

    def hay_ventanas(self) -> bool:
        return self.principal is not None and isValid(self.principal) and self.principal.isVisible()

    def ocultar(self) -> None:
        if self.principal is not None and isValid(self.principal):
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
        if not isValid(self):
            return
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
        etiqueta = self.panel.t_etiqueta
        if (foco is etiqueta or receptor is etiqueta) and not etiqueta.isReadOnly():
            if evento.type() == QEvent.Type.ShortcutOverride:
                evento.accept()
                return True
            return False
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
        multilinea = isinstance(receptor, (QPlainTextEdit, QTextEdit)) and not getattr(receptor, "una_linea", False)  # (el comentario: una línea)
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
            self.principal.pie.setStyleSheet(w._hoja_escala + estilo.campos_compactos() + self.principal.pie._hoja())  # (el pie no cuelga del panel: sus campos, igual de altos)
            self.principal.pie.escalar()
            self.principal.escalar()
        self.panel_actual()
        p, v = self.panel, self.principal
        if p.pagina == "vacio":
            self.ocultar()
            return
        es_trans = p.pagina == "transicion"
        es_accion = p.pagina == "accion"
        clave_acc = p.accion.clave_tipo if es_accion else ""
        es_evento = es_accion and clave_acc == "evento"
        es_condicionada = es_accion and clave_acc == "condicionada"
        es_continua = es_accion and clave_acc == "continua"
        es_mem_simple = es_accion and clave_acc in ("activacion", "desactivacion")
        v.titulo.setText(p.titulo.text())
        v.caja_etiqueta.setVisible(es_trans)
        v.pie.setVisible(es_trans)
        # Margen 0 para editores de bloques / acciones de borde a borde; 14 px para formularios simples (etapa, enlace, barra…)
        margen_cuerpo = 0 if (es_trans or es_accion) else 14
        v.condicion.poner_margen(0)
        v.accion.poner_margen(margen_cuerpo)
        pedida, w_e = self.w.edicion.parte_pedida, self.w.edicion
        w_e.parte_pedida = None
        if es_condicionada:
            # Acción condicionada: Condición + «Activa variable» en la misma subcabecera (sin conmutador de pestañas)
            self._parte = "formula"
            v.subcabecera.show()
            v.conmutador.hide()
            v.l_sub_titulo.setText("Condición")
            v.l_sub_titulo.show()
            v.l_dest.setText("Activa variable:")
            v.caja_dest.show()
            p.l_bloques.hide()
        elif es_evento:
            if pedida in ("formula", "accion"):
                self._parte = pedida
            v.subcabecera.show()
            v.conmutador.botones["formula"].setText("Evento")
            v.conmutador.botones["formula"].setAccessibleName("Editar evento")
            v.conmutador.show()
            v.l_sub_titulo.hide()
            v.l_dest.setText("Variable destino:")
            p.l_bloques.hide()
        elif es_continua or es_mem_simple:
            v.subcabecera.show()
            v.conmutador.hide()
            v.l_sub_titulo.setText("Acción continua" if es_continua else "Acción")
            v.l_sub_titulo.show()
            v.l_dest.setText("Variable:" if es_continua else "Variable destino:")
            v.caja_dest.show()
        else:
            v.subcabecera.hide()
        tiene_cuerpo_continua = bool(p.accion.msg.text().strip())
        v.columna.setVisible(not es_continua or tiene_cuerpo_continua)
        self._mostrar_parte()
        if not v.isVisible():
            self.arrastre.movida = False
            self.arrastre.inicio = None
        v.show()
        self._vigilar(True)
        self.colocar()
        if not self._colocar_pendiente:
            self._colocar_pendiente = True
            QTimer.singleShot(0, self, self._colocar_diferido)

    def _mostrar_parte(self) -> None:
        v, p = self.principal, self.panel
        es_evento = p.pagina == "accion" and p.accion.clave_tipo == "evento"
        es_condicionada = p.pagina == "accion" and p.accion.clave_tipo == "condicionada"
        v.paneles.setCurrentWidget(v.condicion if (es_condicionada or (es_evento and self._parte == "formula")) else v.accion)
        if es_evento:
            v.conmutador.poner(self._parte)
            v.caja_dest.setVisible(self._parte == "accion")

    def elegir_parte(self, clave: str) -> None:
        """El usuario pide otra parte (el conmutador o un clic en la marca o la caja de la vista previa): se enseña su tarjeta y el foco pasa a ella."""
        if self.panel.pagina == "accion" and self.panel.accion.clave_tipo == "condicionada":
            return
        if clave == self._parte or not self.abierto or not self.panel._bloques_fuera:
            return
        self._parte = clave
        self._mostrar_parte()
        p = self.panel
        destino = p.prog.lienzo if clave == "formula" else (p.accion.prog.lienzo if not p.accion.caja_numerica.isHidden() else p.accion.panel_booleano)
        destino.setFocus(Qt.FocusReason.OtherFocusReason)
        self.colocar()

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
        if not isValid(self.w) or (self.principal is not None and not isValid(self.principal)):
            self.principal = None
            self._vigilar(False)
            return False
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
        """Alto fijo de la ventana fuera del editor central (cabecera, lupa, subcabecera, comentario y pie)."""
        v = self.principal
        sub = max(v.subcabecera.height(), v.subcabecera.sizeHint().height()) if not v.subcabecera.isHidden() else 0
        pie = v.pie.alto_nominal() if not v.pie.isHidden() else 0
        return v.cabecera.height() + 1 + self._franja + sub + pie + v.pie_dialogo.height() + 2 * MARCO

    def _disposicion(self, alto_franja: int) -> None:
        """La vista previa arriba, en franja de ancho completo, y debajo el editor."""
        v = self.principal
        v.lupa.margen = estilo.E2
        v.lupa.setMinimumWidth(0)
        v.lupa.setMaximumWidth(16777215)
        v.lupa.setFixedHeight(alto_franja)

    def _dimensionar(self, area: QRect) -> None:
        margen = margen_horizontal(area.width())
        disponible = area.adjusted(margen, estilo.E6, -margen, -estilo.E6)
        disponible.setWidth(min(disponible.width(), 920))
        es_continua = self.panel.pagina == "accion" and self.panel.accion.clave_tipo == "continua"
        es_editor = self.panel.pagina == "transicion" or (self.panel.pagina == "accion" and not es_continua)
        if es_editor:
            # Altura estable de 332 px para el cuerpo (.editor-grid / .stable-panel) para que nunca salte al cambiar de variable o pestaña
            alto_objetivo = self._marco_ventana() + 332
            self._tamano = QSize(disponible.width(), min(disponible.height(), max(alto_objetivo, 460)))
        else:
            sub_ancho = self.principal.subcabecera.sizeHint().width() + 2 * estilo.E3 if not self.principal.subcabecera.isHidden() else 0
            ancho = min(disponible.width(), max(min(40 * estilo.E4, disponible.width()), sub_ancho))
            tiene_cuerpo = not es_continua or bool(self.panel.accion.msg.text().strip())
            if tiene_cuerpo:
                campos = self.panel.izq.sizeHint().height()
                if self.panel.der.isVisibleTo(self.panel):
                    campos += self.panel.der.sizeHint().height() + estilo.E3
                contenido = max(self.panel.sizeHint().height(), campos) + 28
            else:
                contenido = 0
            alto = contenido + self._marco_ventana()
            self._tamano = QSize(ancho, min(alto, disponible.height()))

    def _componer(self) -> None:
        """Los editores ocupan todo el ancho sin márgenes internos; las fichas simples conservan columna."""
        v, p = self.principal, self.panel
        disponible = v.columna.width() - 4 * estilo.E2
        vertical = p.pagina in ("transicion", "accion") or disponible < 36 * estilo.E4
        direccion = QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight
        p.cuerpo.layout().setDirection(direccion)
        p.cuerpo.layout().setSpacing(0 if p.pagina in ("transicion", "accion") else estilo.E3)
        p.layout().setContentsMargins(0, 0, 0, 0)
        p.izq.setMinimumWidth(0 if vertical else ANCHO_COLUMNA)
        p.izq.setMaximumWidth(16777215 if vertical else ANCHO_COLUMNA)
        p.izq.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        if p.pagina == "accion" and p.accion.clave_tipo != "limitada":
            p.izq.setVisible(p.accion.clave_tipo == "continua" and bool(p.accion.msg.text().strip()))  # la variable ya vive en la subcabecera y el valor llena todo el panel
        p.cuerpo.layout().setAlignment(p.izq, Qt.AlignmentFlag.AlignTop)
        p.cuerpo.layout().setStretch(0, 0)
        p.cuerpo.layout().setStretch(1, 1)

    def _alto_franja(self, area: QRect, origen: QRectF) -> int:
        """El alto de la vista previa: el del elemento ampliado hasta el 125 % más su margen, con un mínimo y un tope proporcional al área."""
        v_margen = self.principal.lupa.margen
        minimo = estilo.ALTO_CONTROL + 2 * estilo.E3
        if origen.isEmpty():
            return minimo
        tope = max(minimo, round(area.height() * FRANJA_FRACCION))
        return max(minimo, min(round(origen.height() * AMPLIACION_MAXIMA) + 2 * v_margen, tope))

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
        """Resalta solo la parte activa (como la maqueta): en `formula`, tinte menta suave sobre la marca/expresión;
        en `accion`, tinte menta suave + borde turquesa de 2 px en la caja. La parte inactiva queda limpia sin velo gris."""
        v, p = self.principal, self.panel
        v.lupa.senales, v.lupa.partes = [], []
        if p._bloques_fuera:
            caja = self.w.edicion.accion_en_id(p.ident)
            if caja is not None:
                marca = QRectF(*caja["marca"]) if caja.get("marca") else None
                if marca is not None:
                    if self._parte == "formula":
                        v.lupa.senales.append((marca, SENAL_CONDICION, False))
                    v.lupa.partes.append((marca.adjusted(-estilo.E1, -estilo.E1, estilo.E1, estilo.E1), "formula"))
                if self._parte == "accion":
                    v.lupa.senales.append((QRectF(*caja["rect"]), SENAL_ACCION, True))
                v.lupa.partes.append((QRectF(*caja["rect"]), "accion"))
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
            zonas = self._zonas()
            origen = self._origen_lupa(zonas)
            self._franja = self._alto_franja(area, origen)
            self._disposicion(self._franja)
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
            self.arrastre.limitar()
            self.geometrias = {"principal": QRect(v.geometry())}
            v.lupa.preparar_dibujo(self.w.edicion.M, self.vista.dependencias)
            v.lupa.origen = self._origen_lupa(zonas)
            v.lupa.elemento = self.panel.ident
            v.lupa.tallo_transicion = self._tallo_transicion(v.lupa.origen)
            v.lupa.recorte = self._recorte(v.lupa.origen)
            v.lupa.texto_esquina = self.panel.accion.b_etapa.text() if self.panel.pagina == "accion" else ""
            v.lupa.pista_esquina = (
                "Clic en la bandera o en la caja para alternar"
                if self.panel.pagina == "accion" and self.panel.accion.clave_tipo == "evento" else ""
            )
            v.lupa.update()
            self._senales_lupa()
            v.raise_()
        finally:
            self._colocando = False
