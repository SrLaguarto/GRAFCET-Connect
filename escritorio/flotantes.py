"""Propiedades flotante (Ver > «Propiedades: flotante»): las opciones del elemento se editan en una ventana sobre el dibujo, junto al elemento.

No es una ventana del sistema: es un marco hijo de la vista del dibujo, con cabecera (título, «Fijar» y cerrar), y el mismo contenido que la barra
inferior (`PanelPropiedades`, creado aquí la primera vez que se usa). Se coloca sola, **sin mover ni cambiar de tamaño a mano y sin recordar nada**:
a la derecha del elemento si cabe, si no a la izquierda (y si tampoco, encima o debajo), dentro del lienzo y sin tapar el elemento; con el tamaño
que pide su contenido. Unas líneas de puntos con el aspecto de «Mostrar dependencias» la unen al elemento, como una lupa: dos líneas desde las
esquinas del elemento hasta las de la ventana (las tangentes que no cruzan ni uno ni otra). Al cambiar el zoom, desplazar el dibujo, cambiar su
tamaño o mover el elemento, ventana y líneas se vuelven a colocar con el mismo cálculo.

Una acción condicionada (o por evento) abre **dos** ventanas, una encima de otra: «Condición» (o «Evento»), unida a la marca de la condición, con su
programador por bloques, y «Acción», unida al rectángulo de la acción, con lo demás. Una acción continua no abre ninguna: el doble clic despliega su
variable sobre ella, y si se selecciona con la ventana abierta por otro elemento, solo muestra la frase que lo explica.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLayout, QToolButton, QVBoxLayout, QWidget

from . import estilo
from .diagrama import COL
from .paneles import TituloSeccion
from .propiedades import PanelPropiedades

HUECO = 24       # separación entre el elemento y su ventana
SEPARACION = 8   # entre dos ventanas apiladas
MARGEN = 8       # lo mínimo que queda entre una ventana y el borde del lienzo
ANCHO_MIN, ANCHO_MAX = 300, 780


def _esquinas(r: QRectF) -> list[QPointF]:
    return [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]


def tangentes(a: QRectF, b: QRectF) -> list[tuple[QPointF, QPointF]]:
    """Las líneas «de lupa» entre dos rectángulos que no se tocan: los lados del casco convexo de sus ocho esquinas que unen una de `a` con una de
    `b` (dos, las que no cruzan ni uno ni otro). Vacío si se tocan."""
    if a.intersects(b):
        return []
    puntos = sorted({(p.x(), p.y(), k) for k, r in enumerate((a, b)) for p in _esquinas(r)})
    vistos: dict[tuple[float, float], int] = {}
    for x, y, k in puntos:
        vistos[(x, y)] = -1 if (x, y) in vistos and vistos[(x, y)] != k else k
    pts = sorted((x, y, k) for (x, y), k in vistos.items() if k >= 0)

    def cruz(o: Any, p: Any, q: Any) -> float:
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    casco: list[Any] = []
    for fase in (pts, pts[::-1]):
        mitad: list[Any] = []
        for p in fase:
            while len(mitad) >= 2 and cruz(mitad[-2], mitad[-1], p) <= 0:
                mitad.pop()
            mitad.append(p)
        casco += mitad[:-1]
    return [(QPointF(p[0], p[1]), QPointF(q[0], q[1])) for p, q in zip(casco, casco[1:] + casco[:1]) if p[2] != q[2]]


def colocar(area: QRect, elemento: QRect, opciones: list[list[QSize]]) -> list[QRect]:
    """Dónde va cada ventana (de arriba abajo, apiladas) junto al `elemento`, dentro de `area` y sin tapar el elemento: a su derecha, centradas en él; si
    no cabe, a su izquierda; si tampoco, debajo o encima; si apiladas no caben, cada una por su lado. `opciones` da, de cada ventana, los tamaños que
    admite por orden de preferencia (el que pide su contenido, otros más anchos y bajos y, al final, el mínimo): se prueba el primero de todas, luego
    el segundo… Si nada cabe sin tapar el elemento, a la derecha y metidas en el área, con el último."""
    prohibido = elemento.adjusted(-4, -4, 4, 4)

    def dentro(rs: list[QRect]) -> bool:
        return all(area.contains(r) for r in rs) and not any(r.intersects(prohibido) for r in rs)             and not any(a.intersects(b) for i, a in enumerate(rs) for b in rs[i + 1:])

    def apiladas(ts: list[QSize]) -> list[QRect] | None:
        n = len(ts)
        ancho = max(t.width() for t in ts)
        total = sum(t.height() for t in ts) + SEPARACION * (n - 1)

        def pila(x0: int, y0: int, derecha: bool) -> list[QRect]:
            out, y = [], y0
            for t in ts:
                out.append(QRect(x0 + (ancho - t.width() if derecha else 0), y, t.width(), t.height()))
                y += t.height() + SEPARACION
            return out

        y_c = min(max(elemento.center().y() - total // 2, area.top()), max(area.top(), area.bottom() + 1 - total))
        x_c = min(max(elemento.center().x() - ancho // 2, area.left()), max(area.left(), area.right() + 1 - ancho))
        for rs in (pila(elemento.right() + 1 + HUECO, y_c, False), pila(elemento.left() - HUECO - ancho, y_c, True),
                   pila(x_c, elemento.bottom() + 1 + HUECO, False), pila(x_c, elemento.top() - HUECO - total, False)):
            if dentro(rs):
                return rs
        return None

    def sueltas(ts: list[QSize]) -> list[QRect] | None:
        puestas: list[QRect] = []
        for t in ts:
            xs = [elemento.right() + 1 + HUECO, elemento.left() - HUECO - t.width(), elemento.center().x() - t.width() // 2,
                  area.left(), area.right() + 1 - t.width()]
            ys = [elemento.center().y() - t.height() // 2, elemento.bottom() + 1 + HUECO, elemento.top() - HUECO - t.height(),
                  area.top(), area.bottom() + 1 - t.height()]
            ys += [o.bottom() + 1 + SEPARACION for o in puestas] + [o.top() - SEPARACION - t.height() for o in puestas]
            sitio = next((QRect(x, y, t.width(), t.height()) for x in xs for y in ys
                          if area.contains(QRect(x, y, t.width(), t.height())) and not QRect(x, y, t.width(), t.height()).intersects(prohibido)
                          and not any(QRect(x, y, t.width(), t.height()).intersects(o) for o in puestas)), None)
            if sitio is None:
                return None
            puestas.append(sitio)
        return puestas

    for nivel in range(max(len(o) for o in opciones)):
        ts = [o[min(nivel, len(o) - 1)] for o in opciones]
        for intento in (apiladas, sueltas):
            rs = intento(ts)
            if rs is not None:
                return rs
    # sin sitio libre: la colocación que menos tapa el elemento (con las ventanas apiladas, dentro del área y sin pisarse entre sí)
    mejor: tuple[int, list[QRect]] | None = None
    for nivel in range(max(len(o) for o in opciones)):
        ts = [o[min(nivel, len(o) - 1)] for o in opciones]
        ancho = max(t.width() for t in ts)
        total = sum(t.height() for t in ts) + SEPARACION * (len(ts) - 1)
        y_c = min(max(elemento.center().y() - total // 2, area.top()), max(area.top(), area.bottom() + 1 - total))
        for x0 in (elemento.right() + 1 + HUECO, elemento.left() - HUECO - ancho):
            x0 = min(max(x0, area.left()), max(area.left(), area.right() + 1 - ancho))
            y, rs = y_c, []
            for t in ts:
                rs.append(QRect(x0, y, t.width(), t.height()))
                y += t.height() + SEPARACION
            tapado = sum(max(0, r.intersected(prohibido).width()) * max(0, r.intersected(prohibido).height()) for r in rs)
            if mejor is None or tapado < mejor[0]:
                mejor = (tapado, rs)
    return mejor[1]


class VentanaFlotante(QFrame):
    """Un marco sobre el dibujo: cabecera (título, «Fijar», cerrar) y el contenido que se le ponga en `lay_cuerpo`."""
    cerrar_pedido = Signal()
    fijar_pedido = Signal(bool)

    def __init__(self, vista: QWidget, estilo_fijar: str) -> None:
        super().__init__(vista)
        self.setObjectName("ventanaFlotante")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame#ventanaFlotante {{ background: {estilo.SUPERFICIE}; border: 1px solid {estilo.ACENTO}; "
                           f"border-radius: {estilo.R_M}px; }}")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(1, 1, 1, 1)
        raiz.setSpacing(0)
        self.cabecera = QWidget()
        self.cabecera.setObjectName("cabeceraFlotante")
        fila = QHBoxLayout(self.cabecera)
        fila.setContentsMargins(estilo.E2, 2, estilo.E1, 2)
        fila.setSpacing(estilo.E2)
        self.titulo = TituloSeccion(x_marcador=4)
        fila.addWidget(self.titulo, 1)
        self.t_fijar = QToolButton()
        self.t_fijar.setText("Fijar")
        self.t_fijar.setCheckable(True)
        self.t_fijar.setAutoRaise(True)
        self.t_fijar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.t_fijar.setToolTip("Mantiene abierta esta ventana. Sin fijar, se esconde al hacer clic fuera del elemento.")
        self.t_fijar.setStyleSheet(estilo_fijar)
        self.t_fijar.clicked.connect(self.fijar_pedido)
        fila.addWidget(self.t_fijar)
        self.b_cerrar = QToolButton()
        self.b_cerrar.setText("✕")
        self.b_cerrar.setAutoRaise(True)
        self.b_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_cerrar.setToolTip("Cerrar")
        self.b_cerrar.setAccessibleName("Cerrar la ventana de propiedades")
        self.b_cerrar.setStyleSheet(f"QToolButton{{border:1px solid transparent;border-radius:{estilo.R_S}px;background:transparent;"
                                    f"color:{estilo.TINTA};padding:0 8px;}}QToolButton:hover{{background:{estilo.HOVER};}}"
                                    f"QToolButton[tecl=\"true\"]:focus{{border:2px dashed {estilo.FOCO};padding:0 7px;}}")
        self.b_cerrar.clicked.connect(self.cerrar_pedido)
        fila.addWidget(self.b_cerrar)
        raiz.addWidget(self.cabecera)
        self.cuerpo = QWidget()
        self.lay_cuerpo = QVBoxLayout(self.cuerpo)
        self.lay_cuerpo.setContentsMargins(estilo.E2, 0, estilo.E2, estilo.E2)
        self.lay_cuerpo.setSpacing(0)
        raiz.addWidget(self.cuerpo, 1)
        self.hide()

    def escalar(self) -> None:
        alto = estilo.ALTO_CONTROL_COMPACTO
        self.cabecera.setFixedHeight(alto + 4)
        self.t_fijar.setFixedHeight(alto)
        self.b_cerrar.setFixedHeight(alto)

    def tamanos_para(self, area: QSize) -> list[QSize]:
        """Los tamaños que admite, por orden de preferencia: lo que pide su contenido (ancho entre `ANCHO_MIN` y `ANCHO_MAX`, y el alto que pide a ese
        ancho), el mismo contenido más ancho (y más bajo) y, al final, lo mínimo que admite; ninguno pasa del área."""
        for lay in self.findChildren(QLayout):  # (el contenido acaba de cambiar de página: que las medidas no sean las de antes)
            lay.invalidate()
        self.layout().invalidate()
        self.layout().activate()
        hijo = self.lay_cuerpo
        pide, minimo = hijo.totalSizeHint(), hijo.totalMinimumSize()
        contenido = hijo.itemAt(0).widget()
        m, borde = self.layout().contentsMargins(), self.contentsMargins()  # (lo que se lleva el marco: su margen y el borde)
        extra = QSize(m.left() + m.right() + borde.left() + borde.right(), m.top() + m.bottom() + borde.top() + borde.bottom())

        def medida(ancho: int) -> QSize:
            mc = hijo.contentsMargins()
            interior = ancho - mc.left() - mc.right()
            lay0 = contenido.layout()  # (lo que pide el contenido a ese ancho: las frases se parten, y con ello cambia su alto)
            h0 = lay0.totalHeightForWidth(interior) if lay0 is not None and lay0.hasHeightForWidth() else 0
            alto = max(h0, contenido.sizeHint().height(), contenido.minimumSizeHint().height()) + mc.top() + mc.bottom()
            t = QSize(ancho + extra.width(), alto + self.cabecera.height() + extra.height())
            return QSize(min(t.width(), area.width() - 2 * MARGEN), min(t.height(), area.height() - 2 * MARGEN))

        pref = min(max(pide.width(), minimo.width(), ANCHO_MIN), ANCHO_MAX)
        out = [medida(pref)]
        out += [medida(a) for a in range(pref + 120, ANCHO_MAX + 1, 120)]
        out.append(medida(max(minimo.width(), 220)))
        return out


class _Enlaces(QFrame):
    """La capa transparente (sin ratón) sobre el dibujo donde se trazan las líneas de puntos entre cada ventana y su elemento."""

    def __init__(self, vista: QWidget) -> None:
        super().__init__(vista)
        self.setObjectName("enlacesFlotantes")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.pares: list[tuple[QRectF, QRectF]] = []
        self.hide()

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        lapiz = QPen(QColor(COL["accent"]), 1.2)  # el aspecto de «Mostrar dependencias»: punteado y fino
        lapiz.setDashPattern([5 / 1.2, 4 / 1.2])
        p.setPen(lapiz)
        for parte, ventana in self.pares:
            for a, b in tangentes(parte, ventana):
                p.drawLine(a, b)
        p.end()


class GestorFlotantes(QObject):
    """Las ventanas flotantes de Propiedades de una `Ventana`: crea el panel y los marcos al usarlos, los muestra, rellena y coloca."""

    def __init__(self, ventana: Any) -> None:
        super().__init__(ventana)
        self.w = ventana
        self.vista = ventana.diagrama
        self.panel: PanelPropiedades | None = None
        self.principal: VentanaFlotante | None = None  # el panel entero: o toda la edición del elemento, o («Acción») lo que no es la condición
        self.otra: VentanaFlotante | None = None       # «Condición» o «Evento»: el programador por bloques de una acción
        self.enlaces: _Enlaces | None = None
        self.geometrias: dict[str, QRect] = {}  # lo último colocado, por ventana («principal», «otra»), en coordenadas del dibujo
        self._escala = None
        self._colocando = False

    # -- creación ---------------------------------------------------------------------------------------------------
    def _crear(self) -> None:
        if self.panel is not None:
            return
        w = self.w
        self.enlaces = _Enlaces(self.vista)
        self.panel = PanelPropiedades(flotante=True)
        self.panel.setObjectName("panelPropiedadesFlotante")
        fijar = w.props.t_fijar.styleSheet()
        self.principal = VentanaFlotante(self.vista, fijar)
        self.otra = VentanaFlotante(self.vista, fijar)
        self.principal.lay_cuerpo.addWidget(self.panel)
        self.panel.destino_bloques = self.otra.lay_cuerpo
        for v in (self.principal, self.otra):
            v.cerrar_pedido.connect(lambda: w._mostrar_panel("inferior", False))
            v.fijar_pedido.connect(w.props.t_fijar.setChecked)
        w.props.t_fijar.toggled.connect(self._fijar_cambiado)
        self.panel.prog.franja_cambiada.connect(self.colocar)
        self.panel.accion.prog.franja_cambiada.connect(self.colocar)
        self.panel.alto_cambiado.connect(self.colocar)
        self.vista.vista_cambiada.connect(self.colocar)
        self.panel.setEnabled(w.props.isEnabled())

    def _fijar_cambiado(self, fijo: bool) -> None:
        for v in (self.principal, self.otra):
            if v is not None:
                v.t_fijar.setChecked(fijo)

    # -- estado -----------------------------------------------------------------------------------------------------
    def activo(self) -> bool:
        """¿Está el modo flotante en vigor? (modo «flotante» elegido y editando)"""
        w = self.w
        return w.modo_propiedades == "flotante" and w.modo == "editar" and w.edicion is not None and not getattr(w, "solo_lectura", False)

    def hay_ventanas(self) -> bool:
        return self.principal is not None and self.principal.isVisible()

    def ocultar(self) -> None:
        if self.panel is None:
            return
        for v in (self.principal, self.otra):
            v.hide()
        self.enlaces.hide()
        self.geometrias = {}

    def actualizar(self) -> None:
        """Rellena el panel con lo seleccionado y muestra o esconde las ventanas según toque (abierto, algo que mostrar) y las coloca."""
        w = self.w
        e = w.edicion
        if not self.activo() or not w.a_inferior.isChecked():
            self.ocultar()
            return
        self._crear()
        if self._escala != (w._hoja_escala, estilo.ESCALA):
            self._escala = (w._hoja_escala, estilo.ESCALA)
            self.panel.escalar(w._hoja_escala)
            for v in (self.principal, self.otra):
                v.escalar()
        self.panel.mostrar(e)
        p = self.panel
        if p.pagina == "vacio" and not p.continua:  # nada que editar (nada o varios elementos seleccionados)
            self.ocultar()
            return
        dividida = p._bloques_fuera
        self.principal.titulo.setText(p.titulo.text())
        if dividida:
            self.principal.titulo.setText("Propiedades · Acción")
            self.otra.titulo.setText("Propiedades · " + ("Evento" if p.objetivo_bloques()[2] == "evento" else "Condición"))
        self.principal.t_fijar.setChecked(w._fijado())
        self.otra.t_fijar.setChecked(w._fijado())
        self.principal.show()
        self.otra.setVisible(dividida)
        self.enlaces.show()
        self.colocar()
        QTimer.singleShot(0, self.colocar)  # (otra vez cuando el contenido ya se ha repartido: lo que pide cambia con la página nueva)

    # -- colocación -------------------------------------------------------------------------------------------------
    def _area(self) -> QRect:
        """El lienzo (lo que se ve del dibujo, sin la barra del zoom si flota sobre él), en coordenadas de la propia vista del dibujo."""
        v = self.vista
        area = QRect(v.viewport().geometry())
        barra = v.barra
        if not v.barra_integrada and barra.isVisible() and barra.parent() is v:
            area.setTop(max(area.top(), barra.geometry().bottom() + 4))
        return area

    def _zonas(self) -> list[tuple[VentanaFlotante, QRectF]]:
        """(ventana, parte del dibujo a la que se une, en coordenadas de la vista del dibujo) de cada ventana visible."""
        e, p, v = self.w.edicion, self.panel, self.vista

        def a_vista(r: QRectF) -> QRectF:
            return QRectF(v.mapFromScene(r).boundingRect()).translated(v.viewport().pos())

        if p._bloques_fuera:
            objetivo = p.objetivo_bloques()
            z = e.zonas_propiedades(None, programable=(objetivo[1], objetivo[2]))
            return [(self.otra, a_vista(z[objetivo[2]])), (self.principal, a_vista(z["accion"]))] if z else []
        z = e.zonas_propiedades(p.ident)
        return [(self.principal, a_vista(z["elemento"]))] if z else []

    def colocar(self) -> None:
        """Pone cada ventana visible junto a su elemento y traza las líneas."""
        if self.panel is None or self._colocando or not self.principal.isVisible():
            return
        self._colocando = True
        try:
            area = self._area()
            zonas = self._zonas()
            ventanas = [self.otra, self.principal] if self.otra.isVisible() else [self.principal]
            opciones = [v.tamanos_para(area.size()) for v in ventanas]
            union = QRectF()
            for _, r in zonas:
                union = union.united(r) if not union.isNull() else QRectF(r)
            if union.isNull():
                union = QRectF(area.right() - 4, area.center().y(), 1, 1)
            elemento = union.toAlignedRect()
            lugares = colocar(area, elemento, opciones)
            self.geometrias = {}
            for clave, v, lugar in zip(("otra", "principal") if len(ventanas) == 2 else ("principal",), ventanas, lugares):
                if v.geometry() != lugar:
                    v.setGeometry(lugar)
                v.raise_()
                self.geometrias[clave] = lugar
            origen = self.vista.viewport().geometry()
            self.enlaces.setGeometry(origen)
            self.enlaces.pares = [(r.translated(-origen.topLeft()), QRectF(v.geometry()).translated(-origen.topLeft())) for v, r in zonas]
            self.enlaces.update()
        finally:
            self._colocando = False
