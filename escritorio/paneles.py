"""Paneles plegables por cabecera o divisor, sin controles encima del dibujo."""
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QTextLayout, QTextOption
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGroupBox, QHeaderView, QLabel, QLayout, QSplitter, QSplitterHandle,
                               QSizePolicy, QStackedWidget, QStyle, QStyledItemDelegate, QStyleOptionComboBox, QStyleOptionGroupBox,
                               QStyleOptionToolButton, QStylePainter, QToolButton, QVBoxLayout, QWidget)

from . import estilo


LADO_MARCADOR = 9  # el cuadrado de etapa que abre cada título de sección


def pintar_marcador(p: QPainter, x: float, centro_y: float, color: str = estilo.ACENTO) -> None:
    """El cuadrado de la etapa vacía, del trazo de los iconos (1,75 px): el marcador de sección de todas las vistas."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 1.75, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(x + .9, centro_y - LADO_MARCADOR / 2 + .9, LADO_MARCADOR - 1.8, LADO_MARCADOR - 1.8)
    p.restore()


class TituloSeccion(QLabel):
    """El título de una sección (Elementos, Propiedades…) con el cuadrado de etapa delante: la misma marca en todas las vistas."""

    def __init__(self, texto: str = "", x_marcador: int = 0) -> None:
        super().__init__(texto)
        self.x_marcador = x_marcador  # dónde empieza el cuadrado, además del margen izquierdo del título
        self.setIndent(LADO_MARCADOR + 7)

    def paintEvent(self, evento) -> None:  # noqa: N802
        super().paintEvent(evento)
        p = QPainter(self)
        pintar_marcador(p, self.contentsMargins().left() + self.x_marcador, self.height() / 2)
        p.end()


class CajaSeccion(QGroupBox):
    """Un `QGroupBox` cuyo título lleva delante el cuadrado de etapa (el hueco lo deja la hoja global: `[seccion="true"]::title`)."""

    def __init__(self, titulo: str = "") -> None:
        super().__init__(titulo)
        self.setProperty("seccion", True)

    def paintEvent(self, evento) -> None:  # noqa: N802
        super().paintEvent(evento)
        opcion = QStyleOptionGroupBox()
        self.initStyleOption(opcion)
        r = self.style().subControlRect(QStyle.ComplexControl.CC_GroupBox, opcion, QStyle.SubControl.SC_GroupBoxLabel, self)
        p = QPainter(self)
        pintar_marcador(p, r.left() - 16, r.center().y())  # (el rectángulo del título es el del texto: el hueco de 22 px queda a su izquierda)
        p.end()


class BandaModo(QWidget):
    """La franja de color de lo alto de la tarjeta del dibujo (tinta al editar, verde al simular). Se lee como un **enlace** de la
    notación y no como una regla: un solo trazo, **una** barra de transición cerca del origen y, al final, la punta de la flecha de
    evolución. La ventana la sitúa dentro de las esquinas redondeadas de la tarjeta (`_AjustaBanda`): su remate no sobresale."""

    PUNTA = 12  # lo que mide la punta de la flecha de evolución, al final del enlace

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(estilo.SIMULACION if self.property("modo") == "simular" else estilo.EDICION))
        punta = min(self.PUNTA, max(0, w // 2))
        p.drawPolygon([QPointF(0, 0), QPointF(w - punta, 0), QPointF(w, h / 2), QPointF(w - punta, h), QPointF(0, h)])  # el enlace, que acaba en flecha
        p.setBrush(QColor(estilo.SUPERFICIE))
        p.drawRect(QRectF(34, 0, 3, h))  # la barra de la transición: un hueco que corta el enlace
        p.end()

class EtiquetaElidida(QLabel):
    """Texto de una línea que, si no cabe, acaba en «…» y lleva el texto entero en su ayuda emergente. Nunca fuerza el ancho de
    su fila: el mínimo es casi nulo y lo que pide (`sizeHint`) tiene un tope (`ancho_maximo`). `text()` devuelve el texto entero.
    `modo` es dónde se pone el «…» (por el final, o por el medio para nombres que se distinguen por su final)."""

    def __init__(self, texto: str = "", ancho_maximo: int = 420, modo: Qt.TextElideMode = Qt.TextElideMode.ElideRight) -> None:
        super().__init__()
        self.ancho_maximo = ancho_maximo
        self.modo = modo
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        if texto:
            self.setText(texto)

    def setText(self, texto: str) -> None:  # noqa: N802
        super().setText(texto)
        self.setToolTip(texto)
        self.updateGeometry()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(min(self.ancho_maximo, self.fontMetrics().horizontalAdvance(self.text()) + 4), super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(24, super().minimumSizeHint().height())

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        texto = self.fontMetrics().elidedText(self.text(), self.modo, self.width())
        p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto)
        p.end()


class ChipModo(EtiquetaElidida):
    """El chip del modo (EDICIÓN, SIMULACIÓN · ESTABLE…): texto en mayúsculas y, a la izquierda, un cuadrado que viene de la
    notación: la etapa sin marcar al editar, la etapa activa (rellena) al simular. El relleno y el borde los pone la hoja de estilo;
    `marcador` es «vacio» o «lleno».

    **El estado nunca se pierde**: el chip no cede ancho (su política es fija) y pide lo que mide su texto más largo que cabe en
    `tope`; el título del grafcet, que sí se elide, cede antes. Si ni así cabe, el chip cambia a un texto más corto con el mismo
    estado (`variantes`, de la más larga a la más corta: «SIMULACIÓN · EN RECORRIDO (SITUACIÓN INESTABLE)», «SIMULACIÓN · EN
    RECORRIDO», «SIM. · EN RECORRIDO», «EN RECORRIDO»): la ayuda emergente lleva siempre la descripción entera."""
    MARCO = 26 + 14  # el cuadrado de la izquierda y el relleno de la derecha

    def __init__(self) -> None:
        super().__init__(ancho_maximo=1000)
        self.marcador = "vacio"
        self.variantes: list[str] = []
        self.tope = 10 ** 6  # lo más ancho que puede pedir el chip (lo fija la ventana según su ancho)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    @staticmethod
    def _variantes(texto: str) -> list[str]:
        """El texto y sus versiones más cortas con el mismo estado: sin lo que va entre paréntesis, con el modo abreviado y solo el
        estado."""
        partes = texto.split(" · ")
        salida = [texto]
        if len(partes) > 1:
            estado = partes[-1]
            corto = estado.split(" (")[0]
            for v in (f"{partes[0]} · {corto}", f"{partes[0][:3]}. · {corto}", corto):
                if v not in salida:
                    salida.append(v)
        return salida

    def _ancho(self, texto: str) -> int:
        return self.fontMetrics().horizontalAdvance(texto) + self.MARCO

    def elegida(self, ancho: int | None = None) -> str:
        """La variante más larga que cabe en `ancho` (por omisión, en el tope); si ninguna cabe, la más corta."""
        limite = self.tope if ancho is None else ancho
        for v in self.variantes or [self.text()]:
            if self._ancho(v) <= limite:
                return v
        return (self.variantes or [self.text()])[-1]

    def _reajustar(self) -> None:
        if not self.variantes:
            return
        self.updateGeometry()  # (pide lo que mide su variante elegida; como mínimo, la más corta: nunca fija el ancho de la ventana)

    def fijar_tope(self, tope: int) -> None:
        if tope != self.tope:
            self.tope = tope
            self._reajustar()

    def setText(self, texto: str) -> None:  # noqa: N802
        QLabel.setText(self, texto)
        self.setToolTip("")
        self.variantes = self._variantes(texto)
        self._reajustar()
        self.updateGeometry()

    def event(self, evento) -> bool:  # noqa: N802
        resultado = super().event(evento)
        if evento.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.Polish, QEvent.Type.Show):
            self._reajustar()
        return resultado

    def fijar_marcador(self, marcador: str) -> None:
        if marcador != self.marcador:
            self.marcador = marcador
            self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802
        QFrame.paintEvent(self, evento)  # el relleno, el borde y el radio de la hoja de estilo
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        izquierda = 26
        libre = max(0, self.width() - izquierda - 12)
        texto = self.fontMetrics().elidedText(self.elegida(self.width()), Qt.TextElideMode.ElideRight, libre)
        p.drawText(QRect(izquierda, 0, self.width() - izquierda, self.height()),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto)
        lado = 10
        y = (self.height() - lado) // 2
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        lapiz = p.pen()
        lapiz.setWidth(2)
        p.setPen(lapiz)
        if self.marcador == "lleno":
            p.setBrush(self.palette().color(self.foregroundRole()))
        p.drawRect(QRect(11, y, lado - 1, lado - 1))
        p.end()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._ancho(self.elegida()), self.height() or 26)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._ancho(self.variantes[-1] if self.variantes else self.text()), self.height() or 26)

class ComboElidido(QComboBox):
    """Un desplegable cuyo texto actual, si no cabe, acaba en «…» (por el medio, para conservar el final que distingue una opción de
    otra) y lleva el texto entero en su ayuda emergente; la lista desplegada siempre lo enseña entero."""

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QStylePainter(self)
        opcion = QStyleOptionComboBox()
        self.initStyleOption(opcion)
        p.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opcion)
        campo = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, opcion, QStyle.SubControl.SC_ComboBoxEditField, self)
        texto = opcion.currentText
        if self.toolTip() != texto:
            self.setToolTip(texto)
        opcion.currentText = self.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideMiddle, max(24, campo.width() - 6))
        p.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opcion)


class CabeceraCompacta(QHeaderView):
    """Cabecera horizontal de las tablas estrechas de la simulación. La de Qt, con la hoja de estilo, reserva a cada lado un margen de
    4 px más el relleno y corta la cabecera («Va…», «Contribu…») cuando la columna aún tiene sitio para ella: esta pinta el
    texto a 4 px del borde (donde empieza el de las celdas) y solo lo elide si de verdad no cabe."""

    def paintSection(self, p: QPainter, rect: QRect, indice: int) -> None:  # noqa: N802
        if not rect.isValid():
            return
        p.save()
        p.fillRect(rect, QColor(estilo.SUPERFICIE_2))
        p.setPen(QColor(estilo.BORDE))
        p.drawLine(rect.bottomLeft(), rect.bottomRight())
        p.setPen(QColor(estilo.TINTA_2))
        fuente = QFont(self.font())
        fuente.setPixelSize(estilo.T_PEQUENA)  # la letra de las celdas de estas tablas
        fuente.setBold(False)
        p.setFont(fuente)
        texto = str(self.model().headerData(indice, self.orientation(), Qt.ItemDataRole.DisplayRole) or "")
        r = rect.adjusted(4, 0, -2, -1)
        p.drawText(r, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   p.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideRight, r.width()))
        p.restore()


class EtiquetaAyuda(QLabel):
    """Texto de ayuda de una fila: se parte por palabras hasta `lineas` líneas y, si aun así no cabe, la última acaba en «…»
    (el texto entero va en la ayuda emergente, que pone quien la usa). No impone su ancho a la fila: ocupa lo que sobra."""

    def __init__(self, lineas: int = 2) -> None:
        super().__init__()
        self.lineas = lineas
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def fijar_lineas(self, lineas: int) -> None:
        if lineas != self.lineas:
            self.lineas = lineas
            self.updateGeometry()
            self.update()

    def _renglones(self, ancho: int) -> list[tuple[int, int]]:
        capa = QTextLayout(self.text(), self.font())
        opcion = QTextOption()
        opcion.setWrapMode(QTextOption.WrapMode.WordWrap)
        capa.setTextOption(opcion)
        capa.beginLayout()
        trozos = []
        while True:
            linea = capa.createLine()
            if not linea.isValid():
                break
            linea.setLineWidth(max(40, ancho))
            trozos.append((linea.textStart(), linea.textLength()))
        capa.endLayout()
        return trozos

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, ancho: int) -> int:  # noqa: N802
        n = max(1, min(self.lineas, len(self._renglones(ancho)))) if self.text() else 1
        return n * self.fontMetrics().lineSpacing()  # dos líneas de 12 px caben en 32 px: la cabecera no cambia de alto al simular

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, self.heightForWidth(max(200, self.width())))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, self.fontMetrics().lineSpacing())

    def paintEvent(self, evento) -> None:  # noqa: N802
        texto, ancho = self.text(), self.width()
        if not texto or ancho < 20:
            return
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        fm = self.fontMetrics()
        trozos = self._renglones(ancho)
        n = min(self.lineas, len(trozos))
        alto = fm.lineSpacing()
        arriba = max(0, (self.height() - n * alto) // 2)
        for i in range(n):
            ini, largo = trozos[i]
            fin = len(texto) if i == n - 1 and len(trozos) > n else ini + largo
            linea = texto[ini:fin].rstrip()
            if i == n - 1 and len(trozos) > n:
                linea = fm.elidedText(texto[ini:], Qt.TextElideMode.ElideRight, ancho)
            p.drawText(QRect(0, arriba + i * alto, ancho, alto), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, linea)
        p.end()


class PilaActual(QStackedWidget):
    """El mínimo lo determina la página que se está usando."""
    def __init__(self):
        super().__init__()
        self.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.currentChanged.connect(lambda _: self.updateGeometry())

    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w is not None else QSize(0, 0)

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w is not None else QSize(0, 0)


class PestanaPanel(QToolButton):
    tirar = Signal(object)
    soltar = Signal(object)
    pulsar = Signal(object)
    def __init__(self, nombre, lateral):
        super().__init__()
        self.lateral = lateral
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setText(nombre)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Desplegar " + nombre)
        self.setToolTip("Desplegar " + nombre)

    def sizeHint(self):
        return QSize(26, 100) if self.lateral else QSize(100, 26)

    def minimumSizeHint(self):
        return QSize(26, 26)

    def setText(self, texto):
        super().setText(texto)
        self.setAccessibleName("Desplegar " + texto)
        self.setToolTip("Desplegar " + texto)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setDown(True);self.pulsar.emit(event.globalPosition());event.accept()
        else:super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:self.tirar.emit(event.globalPosition())
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setDown(False);self.soltar.emit(event.globalPosition());event.accept()
        else:super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(estilo.ACENTO_SUAVE if self.underMouse() else estilo.SUPERFICIE_2))
        teclado = self.hasFocus() and bool(self.property("tecl"))  # el anillo solo con el teclado (ver ventana._FocoTeclado)
        p.setPen(QColor(estilo.BORDE_CONTROL if teclado else estilo.BORDE));p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if teclado:
            borde = QColor(estilo.FOCO)
            borde.setAlpha(255)
            lapiz = p.pen()
            lapiz.setColor(borde)
            lapiz.setWidth(2)
            lapiz.setStyle(Qt.PenStyle.DashLine)
            p.setPen(lapiz)
            p.drawRect(self.rect().adjusted(2, 2, -3, -3))
        fuente = QFont(self.font())
        fuente.setPixelSize(estilo.T_BASE)
        fuente.setBold(True)
        p.setFont(fuente)
        p.setPen(QColor(estilo.ACENTO))
        if self.lateral:
            p.translate(self.width()/2, self.height()/2);p.rotate(-90)
            r = QRectF(-self.height()/2, -self.width()/2, self.height(), self.width())
        else:
            r = QRectF(self.rect())
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class PanelPlegable(QWidget):
    alternar = Signal()
    desplegar = Signal(int)
    GROSOR_PESTANA = 26

    def __init__(self, contenido, nombre, posicion, minimo):
        super().__init__()
        self.contenido, self.posicion = contenido, posicion
        self.minimo = minimo
        self.abierto = True
        self.pestana = PestanaPanel(nombre, posicion != "inferior")
        self.pestana.clicked.connect(self.alternar)
        self.pestana.pulsar.connect(self._iniciar_tiron)
        self.pestana.tirar.connect(self._seguir_tiron)
        self.pestana.soltar.connect(self._terminar_tiron)
        self._origen_tiron = None
        self.cerrar = BotonPlegar(contenido)  # (el chevron lo dibuja `BotonPlegar`; su texto «◂ ▸ ▴ ▾» es el de siempre)
        self.cerrar.setAutoRaise(True)
        self.cerrar.setFixedSize(32, 32)
        self.cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cerrar.setStyleSheet(f"QToolButton{{border:1px solid transparent;background:transparent;color:{estilo.ACENTO};border-radius:{estilo.R_S}px;}}"
                                  f"QToolButton:hover{{background:{estilo.ACENTO_SUAVE};}}QToolButton:pressed{{background:{estilo.PULSADO};}}"
                                  f"QToolButton[tecl=\"true\"]:focus{{border:2px dashed {estilo.FOCO};}}")
        self.cerrar.clicked.connect(self.alternar)
        contenido.installEventFilter(self)
        l = QVBoxLayout(self);l.setContentsMargins(0, 0, 0, 0);l.setSpacing(0)
        l.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        l.addWidget(contenido);l.addWidget(self.pestana)
        self.mostrar(True)

    def _iniciar_tiron(self, punto):
        self._origen_tiron = punto;self._ha_arrastrado = False
        self.grabMouse()

    def _seguir_tiron(self, punto):
        if self._origen_tiron is None:return
        delta = punto-self._origen_tiron
        d = delta.x() if self.posicion == "izquierdo" else -delta.x() if self.posicion == "derecho" else -delta.y()
        if abs(d) >= QApplication.startDragDistance():self._ha_arrastrado = True
        if self._ha_arrastrado and d > 0:self.desplegar.emit(max(self.minimo(),round(self.GROSOR_PESTANA+d)))

    def _terminar_tiron(self, punto):
        if self._origen_tiron is None:return
        self._seguir_tiron(punto);self.releaseMouse();self.pestana.setDown(False)
        if not self._ha_arrastrado:self.alternar.emit()
        self._origen_tiron = None

    def mouseMoveEvent(self, event):
        if self._origen_tiron is not None:self._seguir_tiron(event.globalPosition());event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._origen_tiron is not None:self._terminar_tiron(event.globalPosition());event.accept()
        else:super().mouseReleaseEvent(event)

    def mostrar(self, abierto):
        self.abierto = abierto
        self.contenido.setVisible(abierto)
        self.pestana.setVisible(not abierto)
        valor = self.minimo() if abierto else self.GROSOR_PESTANA
        if self.posicion == "inferior":
            self.setMinimumHeight(valor);self.setMaximumHeight(16777215 if abierto else valor)
        else:
            self.setMinimumWidth(valor)
            self.setMaximumWidth(valor if not abierto or self.posicion == "izquierdo" else 16777215)
        self.updateGeometry();self._situar_cierre()

    def eventFilter(self, objeto, evento):
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._situar_cierre()
        return super().eventFilter(objeto, evento)

    def _situar_cierre(self):
        self.cerrar.move(max(0, self.contenido.width()-36), 4)
        self.cerrar.raise_()


class _Tirador(QSplitterHandle):
    def mousePressEvent(self, evento):
        if evento.button() != Qt.MouseButton.LeftButton:
            self._inicio = None
            super().mousePressEvent(evento);return
        self._inicio = evento.globalPosition()
        self._plegado = False
        regla = self.splitter().reglas.get(self.splitter().indexOf(self))
        self._tamano = self.splitter().sizes()[regla[1]] if regla else 0
        self._abriendo = bool(regla and not regla[2].abierto)
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento):
        sp = self.splitter()
        regla = sp.reglas.get(sp.indexOf(self))
        if regla and getattr(self, "_inicio", None) is not None and evento.buttons() & Qt.MouseButton.LeftButton:
            nombre, indice, panel = regla
            delta = evento.globalPosition()-self._inicio
            d = delta.x() if sp.orientation() == Qt.Orientation.Horizontal else delta.y()
            solicitado = self._tamano + (d if indice == 0 else -d)
            if self._abriendo:
                if solicitado > panel.GROSOR_PESTANA+QApplication.startDragDistance():
                    sp.abrir.emit(nombre,max(panel.minimo(),round(solicitado)))
                evento.accept();return
            if panel.abierto and abs(d) >= QApplication.startDragDistance() and solicitado < panel.minimo():
                self._plegado = True
                panel.tamano_recordado = self._tamano
                sp.plegar.emit(nombre)
            if self._plegado or panel.posicion == "izquierdo":
                evento.accept();return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento):
        super().mouseReleaseEvent(evento)
        self._inicio = None


class DivisorPlegable(QSplitter):
    plegar = Signal(str)
    abrir = Signal(str, int)

    def __init__(self, orientacion):
        super().__init__(orientacion)
        self.reglas = {}
        self.setChildrenCollapsible(False)
        self.setHandleWidth(8)

    def createHandle(self):
        return _Tirador(self.orientation(), self)

    def configurar(self, tirador, nombre, indice, panel):
        self.reglas[tirador] = (nombre, indice, panel)


# -- nombres largos que se siguen distinguiendo ---------------------------------------------------------------------------
SEPARADORES = "_-. /:"  # donde un nombre se parte en palabras (sensor_final_carrera_10_avance)


def _comun(a: str, b: str) -> int:
    """Cuántos caracteres iguales tienen `a` y `b` al principio."""
    n, i = min(len(a), len(b)), 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


class ContextoNombres:
    """Los nombres de **una misma lista** (las entradas de la simulación, las filas de una tabla, los canales de un lado de E/S…), para
    acortarlos sin que dos acaben leyéndose igual.

    Un nombre largo que se elide por el medio o por el final pierde justo lo que lo distingue de sus hermanos
    («sensor_final_carrera_cilindro_10_avance» y «…_20_avance» acaban ambos en «sensor_f…0_avance»). Aquí se mira con qué vecino se
    parece más: lo que comparten al principio y al final (en palabras enteras) es lo que se quita, y se conserva el trozo que
    los distingue con su contexto: «…_10_avance» frente a «…_20_avance». Un nombre que cabe se ve entero; una lista de un solo
    nombre no tiene con quién compararse y se elide por el medio, como siempre."""

    def __init__(self, nombres=()) -> None:
        self._nombres: tuple[str, ...] = ()
        self._p: dict[str, int] = {}
        self._q: dict[str, int] = {}
        self._cache: dict[tuple, str] = {}
        self.fijar(nombres)

    def fijar(self, nombres) -> bool:
        """Pone los nombres de la lista; devuelve si eran otros que antes."""
        unicos = tuple(sorted({n for n in nombres if n}))
        if unicos == self._nombres:
            return False
        self._nombres, self._cache = unicos, {}
        p = dict.fromkeys(unicos, 0)  # lo que cada nombre comparte, al principio, con su vecino más parecido
        q = dict.fromkeys(unicos, 0)  # y al final
        for a, b in zip(unicos, unicos[1:]):
            c = _comun(a, b)
            p[a], p[b] = max(p[a], c), max(p[b], c)
        inversos = sorted(n[::-1] for n in unicos)
        for a, b in zip(inversos, inversos[1:]):
            c = _comun(a, b)
            a, b = a[::-1], b[::-1]
            q[a], q[b] = max(q[a], c), max(q[b], c)
        self._p, self._q = p, q
        return True

    @property
    def nombres(self) -> tuple[str, ...]:
        return self._nombres

    def _ventana(self, n: str) -> tuple[int, int]:
        """El trozo de `n` que lo distingue de sus hermanos, ampliado a palabras enteras: [a, b)."""
        largo = len(n)
        p, q = self._p[n], largo - self._q[n]
        a = 0
        for i in range(min(min(p, q), largo) - 1, -1, -1):
            if n[i] in SEPARADORES:
                a = i
                break
        b = largo
        for i in range(max(p, q), largo):
            if n[i] in SEPARADORES:
                b = i
                break
        return a, b

    def elidir(self, nombre: str, fm: QFontMetrics, ancho: int) -> str:
        """`nombre` para un hueco de `ancho` px con la letra de `fm`: entero si cabe y, si no, con «…» donde sobra, sin perder lo que lo
        distingue de los demás nombres de la lista."""
        clave = (nombre, ancho, fm.horizontalAdvance("Wmi_.0 "))
        texto = self._cache.get(clave)
        if texto is None:
            texto = self._cache[clave] = self._elidir(nombre, fm, max(ancho, 12))
        return texto

    def _elidir(self, n: str, fm: QFontMetrics, ancho: int) -> str:
        ancho_de = fm.horizontalAdvance
        if ancho_de(n) <= ancho:
            return n
        if len(self._nombres) < 2 or n not in self._p:
            return fm.elidedText(n, Qt.TextElideMode.ElideMiddle, ancho)
        largo = len(n)
        a, b = self._ventana(n)
        if a > 0 and ancho_de("…" + n[a:]) <= ancho:  # lo común del principio se quita y se enseña tanto del final como quepa
            s = a
            for i in range(a - 1, 0, -1):
                if n[i] in SEPARADORES:
                    if ancho_de("…" + n[i:]) > ancho:
                        break
                    s = i
            if ancho_de("…" + n[s:]) < 0.6 * ancho:  # queda mucho hueco (p. ej. «…_1»): se amplía letra a letra, para dar contexto
                while s > 1 and ancho_de("…" + n[s - 1:]) <= ancho:
                    s -= 1
            return "…" + n[s:]
        previo = "…" if a > 0 else ""

        def ventana(fin: int) -> str:
            return previo + n[a:fin] + ("…" if fin < largo else "")

        if ancho_de(ventana(b)) <= ancho:  # lo que distingue cabe, pero no el final entero: se enseña hasta donde quepa
            fin = b
            for i in range(b + 1, largo):
                if n[i] in SEPARADORES:
                    if ancho_de(ventana(i)) > ancho:
                        break
                    fin = i
            return ventana(fin)
        return previo + fm.elidedText(n[a:b], Qt.TextElideMode.ElideMiddle, max(12, ancho - ancho_de(previo)))

    def etiquetas(self, fm: QFontMetrics, ancho: int) -> dict[str, str]:
        """Cómo se ve cada nombre de la lista en un hueco de `ancho` px."""
        return {n: self.elidir(n, fm, ancho) for n in self._nombres}


class DelegadoNombres(QStyledItemDelegate):
    """Una columna de una tabla cuyo texto son nombres de una misma lista: los pinta con `ContextoNombres` (nunca dos iguales).
    La celda sigue teniendo el nombre entero (y lo lleva su ayuda emergente); solo se pinta más corto."""

    def __init__(self, padre, columnas=(0,)) -> None:
        super().__init__(padre)
        self.contexto = ContextoNombres()
        self.columnas = frozenset(columnas)

    def fijar(self, nombres) -> None:
        self.contexto.fijar(nombres)

    def initStyleOption(self, option, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        if index.column() in self.columnas and option.text:
            margen = 2 * (QApplication.style().pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 1)
            option.text = self.contexto.elidir(option.text, QFontMetrics(option.font), option.rect.width() - margen - 1)
            option.textElideMode = Qt.TextElideMode.ElideNone  # (ya cabe: Qt no vuelve a cortarlo)

    def texto_visible(self, tabla, fila: int, columna: int) -> str:
        """Lo que se ve ahora en esa celda de `tabla` (para comprobarlo sin mirar píxeles)."""
        from PySide6.QtWidgets import QStyleOptionViewItem
        indice = tabla.model().index(fila, columna)
        opcion = QStyleOptionViewItem()
        opcion.initFrom(tabla.viewport())
        opcion.rect = tabla.visualRect(indice)
        opcion.font = tabla.font()
        self.initStyleOption(opcion, indice)
        return opcion.text


class EtiquetaGrupos(QLabel):
    """Una frase hecha de grupos unidos por « · » («Clic: pulsar · Ctrl+clic: enclavar · Clic derecho: tipo»): si no cabe en una
    línea se parte **entre** grupos, nunca por dentro de uno. Un grupo corto es indivisible; uno largo (un aviso, un mensaje de error)
    se parte por palabras, como un texto normal. Pide lo que mide la frase en una línea y no menos que su grupo más ancho."""
    SEP = " · "
    ATOMICO = 36  # un grupo de hasta tantos caracteres no se parte por dentro (si cabe en el ancho)

    def __init__(self, texto: str = "", ancho_maximo: int = 10 ** 6) -> None:
        super().__init__()
        self.ancho_maximo = ancho_maximo
        self._grupos: list[str] = []
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setWordWrap(True)  # (para que el diseño pregunte por el alto según el ancho)
        if texto:
            self.setText(texto)

    def setText(self, texto: str) -> None:  # noqa: N802
        super().setText(texto)
        import re
        self._grupos = [g for g in re.split(r"\s+·\s+", texto.strip()) if g]
        self.updateGeometry()
        self.update()

    def _lineas(self, ancho: int) -> list[str]:
        ancho_de = self.fontMetrics().horizontalAdvance
        lineas: list[str] = []
        actual = ""
        for g in self._grupos:
            candidata = f"{actual}{self.SEP}{g}" if actual else g
            if ancho_de(candidata) <= ancho:
                actual = candidata
                continue
            if actual:
                lineas.append(actual)
                actual = ""
            if ancho_de(g) <= ancho:
                actual = g
                continue
            for palabra in g.split(" "):  # un grupo largo: por palabras
                candidata = f"{actual} {palabra}" if actual else palabra
                if not actual or ancho_de(candidata) <= ancho:
                    actual = candidata
                else:
                    lineas.append(actual)
                    actual = palabra
        if actual:
            lineas.append(actual)
        return lineas

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, ancho: int) -> int:  # noqa: N802
        return max(1, len(self._lineas(max(20, ancho)))) * self.fontMetrics().lineSpacing() + 2

    def sizeHint(self) -> QSize:  # noqa: N802
        ancho = min(self.ancho_maximo, self.fontMetrics().horizontalAdvance(self.SEP.join(self._grupos)) + 2)
        return QSize(ancho, self.heightForWidth(ancho))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        fm = self.fontMetrics()
        ancho = 0
        for g in self._grupos:
            ancho = max(ancho, fm.horizontalAdvance(g) if len(g) <= self.ATOMICO else max((fm.horizontalAdvance(w) for w in g.split(" ")), default=0))
        return QSize(min(ancho + 2, self.ancho_maximo), fm.lineSpacing() + 2)

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        alto = self.fontMetrics().lineSpacing()
        for i, linea in enumerate(self._lineas(self.width())):
            p.drawText(QRect(0, 1 + i * alto, self.width(), alto), int(self.alignment()) or int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), linea)
        p.end()


class BotonPlegar(QToolButton):
    """El botón que pliega o despliega un panel. Su texto es el de siempre («◂ ▸ ▴ ▾»: es lo que lo identifica) pero lo que se ve es un
    chevron de trazo, de 14 px de alto, centrado en un objetivo de 32 px: el glifo de texto no pasaba de 6 px."""

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QStylePainter(self)
        opcion = QStyleOptionToolButton()
        self.initStyleOption(opcion)
        opcion.text = ""
        p.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opcion)  # fondo, borde y anillo de foco de la hoja de estilo
        dx, dy = {"◂": (-1, 0), "▸": (1, 0), "▴": (0, -1), "▾": (0, 1)}.get(self.text(), (0, 0))
        if not (dx or dy):
            return
        color = QColor(self.palette().color(self.foregroundRole()))
        if not self.isEnabled():
            color = QColor(estilo.DESHABILITADO)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        cx, cy, largo, ancho = self.width() / 2, self.height() / 2, 7.0, 3.5  # el chevron mide 14 × 7 px
        punta = QPointF(cx + dx * ancho, cy + dy * ancho)
        trazo = QPainterPath(QPointF(cx - dx * ancho + dy * largo, cy - dy * ancho + dx * largo))
        trazo.lineTo(punta)
        trazo.lineTo(QPointF(cx - dx * ancho - dy * largo, cy - dy * ancho - dx * largo))
        p.drawPath(trazo)
