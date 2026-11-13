"""Una ventana de propiedades centrada, con lupa de la escena y paneles desplazables."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout, QFrame, QHBoxLayout, QLayout, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from . import estilo
from .diagrama import COL, Z_EDIT, caja_barra, orientaciones, posiciones
from .paneles import TituloSeccion
from .propiedades import ANCHO_COLUMNA, PanelPropiedades

AMPLIACION_MAXIMA = 1.25
MEDIO_TRAZO = 0.8  # la mitad del trazo de 1,6 px de las cajas del dibujo
MARCO = 1  # el borde de la ventana: el layout empieza dentro de él


class Lupa(QWidget):
    """Recorte no interactivo de la escena real, sin las capas de edición de Z_EDIT en adelante."""

    def __init__(self, vista: Any) -> None:
        super().__init__()
        self.vista = vista
        self.origen = QRectF()
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

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        marco = QPainter(self)  # la tarjeta de la vista previa: fondo suave, borde de 1 px y radio R_M, como las de los paneles
        marco.setRenderHint(QPainter.RenderHint.Antialiasing)
        marco.setPen(QPen(QColor(estilo.BORDE), 1))
        marco.setBrush(QColor(estilo.SUPERFICIE))
        marco.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), estilo.R_M, estilo.R_M)
        marco.end()
        if self.origen.isEmpty():
            return
        escena = self.vista.scene()
        ocultos = [i for i in escena.items() if i.isVisible() and i.zValue() >= Z_EDIT]
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        try:
            for item in ocultos:
                item.hide()
            destino = self.transformar().mapRect(self.origen)
            if self.recorte:  # solo el elemento: nada de las cajas vecinas que caen en el encuadre
                t = self.transformar()
                zona = QPainterPath()  # (la unión en un solo contorno: con rectángulos sueltos y bordes suavizados se vería una costura)
                for r in self.recorte:
                    trozo = QPainterPath()
                    trozo.addRect(t.mapRect(r))
                    zona = zona.united(trozo)
                p.setClipPath(zona)
            escena.render(p, destino, self.origen, Qt.AspectRatioMode.IgnoreAspectRatio)
        finally:
            for item in ocultos:
                item.show()
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
        self.titulo = TituloSeccion()
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
        super().__init__(padre)
        self.setObjectName("ventanaFlotante")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QFrame#ventanaFlotante {{ background: {estilo.SUPERFICIE}; "
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
        fila_cuerpo.setSpacing(estilo.E6)  # el hueco por el que cruzan las líneas de puntos
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
        self.enlaces = _Enlaces(self.cuerpo)
        self.hide()

    def escalar(self) -> None:
        self.cabecera.setFixedHeight(estilo.ALTO_CONTROL + 2 * estilo.E2)
        self.b_cerrar.setFixedSize(estilo.ALTO_CONTROL, estilo.ALTO_CONTROL)


class _Enlaces(QFrame):
    """Una línea por parte del elemento ampliado, hasta el borde de su panel."""

    def __init__(self, padre: QWidget) -> None:
        super().__init__(padre)
        self.setObjectName("enlacesFlotantes")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.pares: list[tuple[QRectF, QRectF]] = []
        self.inicios: list[QPointF] = []  # dónde sale cada línea (en coordenadas del cuerpo)
        self.finales: list[QPointF] = []  # dónde acaba cada línea: en el borde izquierdo de su tarjeta

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        lapiz = QPen(QColor(COL["accent"]), 1.2)
        lapiz.setDashPattern([5 / 1.2, 4 / 1.2])
        p.setPen(lapiz)
        for inicio, fin in zip(self.inicios, self.finales):
            p.drawLine(inicio, fin)
        p.end()


class GestorFlotantes(QObject):
    """Conserva el estado de la barra inferior y organiza una única ventana al usarla."""

    def __init__(self, ventana: Any) -> None:
        super().__init__(ventana)
        self.w = ventana
        self.vista = ventana.diagrama
        self.superficie = None
        self.panel: PanelPropiedades | None = None
        self.principal: VentanaFlotante | None = None
        self.enlaces: _Enlaces | None = None
        self.geometrias: dict[str, QRect] = {}
        self._escala = None
        self._colocando = False
        self._vigilando = False
        self._tamano = QSize()

    def _crear(self) -> None:
        if self.panel is not None:
            return
        self.superficie = self.w.centralWidget()
        self.w.paginas_es.installEventFilter(self)
        self.superficie.installEventFilter(self)
        self.w.paginas_es.currentChanged.connect(self.actualizar)
        self.panel = PanelPropiedades(flotante=True)
        self.panel.setObjectName("panelPropiedadesFlotante")
        self.principal = VentanaFlotante(self.superficie, self.vista)
        self.enlaces = self.principal.enlaces
        self.principal.accion.lay_cuerpo.addWidget(self.panel)
        self.panel.destino_bloques = self.principal.condicion.lay_cuerpo
        self.principal.cerrar_pedido.connect(lambda: self.w._mostrar_panel("inferior", False))
        self.panel.prog.franja_cambiada.connect(self.colocar)
        self.panel.accion.prog.franja_cambiada.connect(self.colocar)
        self.panel.alto_cambiado.connect(self.colocar)
        self.vista.vista_cambiada.connect(self.colocar)
        self.panel.setEnabled(self.w.props.isEnabled())

    def activo(self) -> bool:
        w = self.w
        return (
            w.modo_propiedades == "flotante" and w.modo == "editar"
            and w.edicion is not None and not w.solo_lectura and w.paginas_es.currentIndex() == 0
        )

    def hay_ventanas(self) -> bool:
        return self.principal is not None and self.principal.isVisible()

    def ocultar(self) -> None:
        if self.principal is not None:
            self.principal.hide()
        self.geometrias = {}
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

    def _esc(self, evento: Any) -> bool:
        """Esc con la ventana abierta: si hay un desplegable abierto, o un campo con algo que Esc cancela, o el foco está en otra ventana, lo
        suyo primero; si no, cierra la ventana (también con el foco en el dibujo: sin deseleccionar a la vez)."""
        if QApplication.activePopupWidget() is not None:
            return False
        foco = QApplication.focusWidget()
        if foco is not None and foco.window() is not self.w:
            return False
        if self._cancela_con_esc(foco):
            return False
        if evento.type() == QEvent.Type.ShortcutOverride:
            evento.accept()  # (el atajo de Esc de la ventana, que deselecciona, no salta: llega la tecla)
        else:
            self.w._mostrar_panel("inferior", False)
        return True

    def actualizar(self) -> None:
        w = self.w
        if not self.activo() or not w.a_inferior.isChecked():
            self.ocultar()
            return
        self._crear()
        if self._escala != (w._hoja_escala, estilo.ESCALA):
            self._escala = (w._hoja_escala, estilo.ESCALA)
            self.panel.escalar(w._hoja_escala)
            self.principal.escalar()
        self.panel.mostrar(w.edicion)
        p, v = self.panel, self.principal
        if p.pagina == "vacio":
            self.ocultar()
            return
        dividida = p._bloques_fuera
        v.titulo.setText(p.titulo.text())
        v.condicion.setVisible(dividida)
        v.accion.titulo.setText("Acción" if dividida else p.titulo.text().removeprefix("Propiedades · "))
        if dividida:
            evento = p.objetivo_bloques()[2] == "evento"
            v.titulo.setText("Propiedades · Acción por evento" if evento else "Propiedades · Acción condicionada")
            v.condicion.titulo.setText("Evento" if evento else "Condición")
            p.l_bloques.hide()
        v.show()
        self._vigilar(True)
        self.colocar()
        QTimer.singleShot(0, self.colocar)

    def eventFilter(self, objeto: QObject, evento: Any) -> bool:  # noqa: N802
        tipo = evento.type()
        if self._vigilando and not self.principal.isVisible():  # (la ventana se cerró, o su aplicación: deja de vigilar)
            self._vigilar(False)
        if tipo in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            if (evento.key() == Qt.Key.Key_Escape and not evento.modifiers() and self.hay_ventanas() and self._esc(evento)):
                return True
            return False
        if tipo in (QEvent.Type.Resize, QEvent.Type.Move) and (objeto is self.superficie or objeto is self.w.paginas_es):
            self.colocar()  # (el filtro de la aplicación, mientras la ventana está abierta, ve todos los objetos)
        return False

    def _area(self) -> QRect:
        """Toda el área de trabajo de la aplicación, incluidas las columnas laterales."""
        pagina = self.w.paginas_es
        return QRect(pagina.mapTo(self.superficie, QPoint()), pagina.size())

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
        v = self.principal
        margen = max(2 * estilo.E6, area.width() // (16 * estilo.E2) * estilo.E2)
        disponible = area.adjusted(margen, estilo.E6, -margen, -estilo.E6)
        necesita_formulador = (
            self.panel.pagina == "transicion" or self.panel._bloques_fuera
            or self.panel.accion.caja_numerica.isVisibleTo(self.panel)
        )
        if necesita_formulador:
            alto = self._alto_formuladores(disponible)
            self._tamano = QSize(disponible.width(), alto)
        else:
            ancho = min(40 * estilo.E4, disponible.width())
            campos = self.panel.izq.sizeHint().height()
            if self.panel.der.isVisibleTo(self.panel):
                campos += self.panel.der.sizeHint().height() + estilo.E3
            contenido = max(self.panel.sizeHint().height(), campos)
            alto = contenido + self._marco_ventana() + self._marco_tarjeta() + estilo.E1
            self._tamano = QSize(ancho, min(alto, disponible.height()))

    def _alto_formuladores(self, disponible: QRect) -> int:
        """Todo el alto libre para los bloques de una condición, un evento o una receptividad; con un valor numérico de por medio, la mitad."""
        p, v = self.panel, self.principal
        previa = min(12 * estilo.E4, max(8 * estilo.E4, disponible.width() // 6))
        vertical = disponible.width() - previa - 5 * estilo.E4 < 36 * estilo.E4
        numerica = p.accion.caja_numerica.isVisibleTo(p)
        cantidad = 2 if p._bloques_fuera and numerica else 1
        if not numerica:  # transición, condición o evento: los bloques ven el máximo de variables (sin la fila «Fórmula» ni la frase sobra alto)
            return disponible.height()
        fijos = self._marco_ventana() + cantidad * (self._marco_tarjeta() + 2 * estilo.E3)
        if p._bloques_fuera and not numerica:
            fijos += p.sizeHint().height() + 4 * estilo.E2
        elif vertical and p.izq.isVisibleTo(p):
            fijos += p.izq.sizeHint().height() + estilo.E3
        minimo = fijos + cantidad * 8 * estilo.E4
        alto = max(minimo, (disponible.height() + fijos) // 2)
        return min(alto, disponible.height())

    def _componer(self) -> None:
        """La vista previa cede sitio al formulador; los campos se apilan solo si falta ancho."""
        v, p = self.principal, self.panel
        v.lupa.setFixedWidth(min(12 * estilo.E4, max(8 * estilo.E4, v.width() // 6)))
        disponible = v.columna.width() - 4 * estilo.E2
        vertical = disponible < 36 * estilo.E4
        direccion = QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight
        p.cuerpo.layout().setDirection(direccion)
        p.cuerpo.layout().setSpacing(estilo.E3)
        p.layout().setContentsMargins(0, 0, 0, 0)
        p.izq.setMinimumWidth(0 if vertical else ANCHO_COLUMNA)
        p.izq.setMaximumWidth(16777215 if vertical else ANCHO_COLUMNA)
        p.izq.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        p.cuerpo.layout().setAlignment(p.izq, Qt.AlignmentFlag.AlignTop)
        p.cuerpo.layout().setStretch(0, 0)
        p.cuerpo.layout().setStretch(1, 1)
        for interior in (v.condicion, v.accion):
            interior.setMinimumHeight(0)
            interior.setMaximumHeight(16777215)
        v.columna.layout().setStretch(0, 1)
        v.columna.layout().setStretch(1, 1)

    def _repartir_paneles(self, area: QRect) -> None:
        """Reserva contenido real antes de repartir el espacio libre entre los dos editores."""
        v, p = self.principal, self.panel
        if not p._bloques_fuera:
            return
        superior = v.condicion.alto_necesario()
        inferior = v.accion.alto_necesario(justo=not p.accion.caja_numerica.isVisibleTo(p))
        separacion = v.columna.layout().spacing()
        requerido = superior + inferior + separacion
        falta = max(0, requerido - v.columna.height())
        if falta:
            alto = min(v.height() + falta, area.height() - 2 * estilo.E6)
            lugar = QRect(v.pos(), QSize(v.width(), alto))
            lugar.moveCenter(area.center())
            v.setGeometry(lugar)
            v.layout().activate()
            v.cuerpo.layout().activate()
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

    def _recorte(self, origen: QRectF) -> list[QRectF]:
        """Lo que pinta la lupa de una acción: su caja, su marca y, si es la primera unida a la etapa, el trazo de unión."""
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
        """Lo que pinta la lupa de una transición (su trazo, su barra y sus textos) o de una etapa (su caja): con los muñones del enlace hasta
        el borde del encuadre, y nada de las etapas, transiciones o acciones vecinas. Otros elementos, sin recorte."""
        ident = self.panel.ident
        z = e.zonas_propiedades(ident).get("elemento")
        pos = posiciones(e.M)
        if z is None or ident not in pos:
            return []
        x, y = pos[ident]
        grosor = 2.0  # (el trazo del enlace: 1,6 px, con holgura)
        sitios = [QRectF(z)]
        trans = orientaciones(e.M)
        vertical = True  # el enlace va arriba y abajo
        if ident in trans:
            barra = caja_barra(trans[ident], x, y)
            vertical = barra.width() > barra.height()
        if vertical:
            sitios.append(QRectF(x - grosor, origen.top(), 2 * grosor, z.top() - origen.top() + 1))
            sitios.append(QRectF(x - grosor, z.bottom() - 1, 2 * grosor, origen.bottom() - z.bottom() + 1))
        else:
            sitios.append(QRectF(origen.left(), y - grosor, z.left() - origen.left() + 1, 2 * grosor))
            sitios.append(QRectF(z.right() - 1, y - grosor, origen.right() - z.right() + 1, 2 * grosor))
        if ident not in trans:  # la etapa puede llevar su enlace a la acción: un muñón corto a su derecha
            sitios.append(QRectF(z.right() - 1, y - grosor, origen.right() - z.right() + 1, 2 * grosor))
        return sitios

    def colocar(self) -> None:
        if self.principal is None or self._colocando or not self.principal.isVisible():
            return
        self._colocando = True
        try:
            v = self.principal
            area = self._area()
            self._dimensionar(area)
            lugar = QRect(area.topLeft(), self._tamano)
            lugar.moveCenter(area.center())
            v.setGeometry(lugar)
            v.layout().activate()
            v.cuerpo.layout().activate()
            self._componer()
            v.cuerpo.layout().activate()
            v.columna.layout().activate()
            self._repartir_paneles(area)
            self.geometrias = {"principal": QRect(v.geometry())}
            zonas = self._zonas()
            v.lupa.origen = self._origen_lupa(zonas)
            v.lupa.recorte = self._recorte(v.lupa.origen)
            v.lupa.update()
            self.enlaces.setGeometry(v.cuerpo.rect())
            self.enlaces.pares = []
            self.enlaces.finales = []
            self.enlaces.inicios = []
            caja = self.w.edicion.accion_en_id(self.panel.ident) if self.panel._bloques_fuera else None
            for panel, r in (zonas if len(zonas) == 2 else []):  # (las líneas de puntos, solo con dos paneles: condición o evento, y acción)
                parte = v.lupa.transformar().mapRect(r).translated(v.lupa.pos())
                destino = QRectF(panel.rect()).translated(panel.mapTo(v.cuerpo, panel.rect().topLeft()))
                self.enlaces.pares.append((parte, destino))
                if panel is v.condicion and caja is not None and caja.get("marca"):  # sale de la esquina superior izquierda de la marca
                    esquina = v.lupa.transformar().map(QPointF(*caja["marca"][:2])) + QPointF(v.lupa.pos())
                    self.enlaces.inicios.append(esquina)
                else:
                    self.enlaces.inicios.append(QPointF(parte.right(), parte.center().y()))
                # termina sobre el borde izquierdo de la tarjeta, a la altura de su título (sin entrar en las esquinas redondeadas)
                y = panel.titulo.mapTo(v.cuerpo, panel.titulo.rect().center()).y()
                y = min(max(y, destino.top() + estilo.R_M), destino.bottom() - estilo.R_M)
                self.enlaces.finales.append(QPointF(destino.left(), y))
            self.enlaces.raise_()
            self.enlaces.update()
            v.raise_()
        finally:
            self._colocando = False
