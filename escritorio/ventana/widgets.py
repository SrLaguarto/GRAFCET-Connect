"""Controles propios de la ventana: botones de entrada, filtros de eventos y delegados de las tablas de estado."""
from __future__ import annotations

from .. import estilo
from ..laminas import VistaLamina
from ..paneles import ContextoNombres, LINEAS_NOMBRE, partir_nombre
from typing import Any
from PySide6.QtCore import QEvent, QObject, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QAbstractSpinBox, QApplication, QComboBox,
                               QLineEdit, QPlainTextEdit, QPushButton, QSizePolicy, QStyle, QStyleOptionButton,
                               QStylePainter, QStyledItemDelegate, QTabBar, QTableWidget, QTextEdit, QToolButton, QWidget)


def _ventana() -> type:
    """La clase `Ventana` (importada tarde: la ventana importa este módulo)."""
    from . import Ventana
    return Ventana


class _BotonEntrada(QPushButton):
    """El estado marcado sigue el valor de la entrada, no el automatismo checkable de Qt. Pulsada, enclavada o conmutada
    se distingue por la forma del icono (anillo, punto, candado, interruptor), por el texto («= 1») y por el relleno.
    Un nombre largo **se lee entero**: se parte por los «_» en dos o tres líneas (`ContextoNombres.lineas`) y el botón crece lo que
    haga falta, con « = 0 / = 1» pegado a la última línea; solo si ni en tres líneas cabe se elide por el medio. Nunca cambia el ancho de
    la ventana; el nombre entero va también en la ayuda y, con el foco, con el puntero encima o al pulsarla, en la línea de detalle. Mantener
    pulsado se comporta como siempre (P-IMP-75): la entrada sigue a 1 mientras dure. El foco es el de siempre: un clic lo da (y Espacio
    repite la pulsación); el anillo solo se ve con el teclado."""
    sobre = Signal(bool)  # el puntero entra (True) o sale (False): la línea de detalle dice el nombre entero

    def __init__(self) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setProperty("entrada", True)
        self.control = self.enclavado = self.liberar = self.interruptor = self.nc = False
        self.ayuda_base = ""
        self.contexto: ContextoNombres | None = None  # los nombres de las demás entradas: el elidido no confunde dos
        self.setMinimumHeight(estilo.ALTO_ENTRADA)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.indicar(False)

    def enterEvent(self, event: Any) -> None:  # noqa: N802
        super().enterEvent(event)
        self.sobre.emit(True)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.sobre.emit(False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(160, estilo.ALTO_ENTRADA)

    def nombre_completo(self) -> str:
        texto = self.text()
        return texto.rpartition(" = ")[0] or texto

    def _ancho_texto(self) -> int:
        """Lo que queda para el texto: el botón menos el relleno (10 px a cada lado), el borde (2) y el icono con su hueco."""
        return max(24, self.width() - 2 * 10 - 2 * 2 - self.iconSize().width() - 8)

    def lineas_visibles(self) -> list[str]:
        """El texto del botón en sus líneas: el **nombre entero**, partido por los «_» en las líneas que haga falta (hasta tres; solo si ni así
        cabe se elide por el medio) y, pegado al final de la última, « = valor»."""
        nombre, separador, valor = self.text().rpartition(" = ")
        if not separador:
            return [self.text()]
        sufijo = " = " + valor
        if self.contexto is not None:
            return self.contexto.lineas(nombre, self.fontMetrics(), self._ancho_texto(), LINEAS_NOMBRE, sufijo)
        return partir_nombre(nombre, self.fontMetrics(), self._ancho_texto(), sufijo)[:LINEAS_NOMBRE]

    def texto_visible(self) -> str:
        """El texto que se ve ahora en el botón (el nombre partido en sus líneas, separadas por «\\n», y « = valor»)."""
        return "\n".join(self.lineas_visibles())

    def ajustar_alto(self) -> None:
        """El botón mide lo que sus líneas: con una, el alto de siempre; con el nombre partido en dos o tres, una línea más por cada una (la
        fila crece lo necesario y el nombre se lee entero)."""
        n = len(self.lineas_visibles()) if self.width() >= 40 else 1
        alto = estilo.ALTO_ENTRADA + 2 + (n - 1) * self.fontMetrics().lineSpacing()
        if n == 1:
            self.setMinimumHeight(estilo.ALTO_ENTRADA)
            self.setMaximumHeight(16777215)
        elif self.minimumHeight() != alto or self.maximumHeight() != alto:
            self.setFixedHeight(alto)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.ajustar_alto()

    def setText(self, texto: str) -> None:  # noqa: N802
        super().setText(texto)
        nombre = self.nombre_completo()
        self.setToolTip(f"{nombre}\n{self.ayuda_base}" if self.ayuda_base else nombre)
        self.ajustar_alto()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self.control = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        super().mousePressEvent(event)
    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QStylePainter(self)
        opcion = QStyleOptionButton()
        self.initStyleOption(opcion)
        # (con el foco, la hoja de estilo pinta el anillo `[tecl="true"]:focus`: aquí no se toca el estado del foco)
        if " = " in opcion.text:
            lineas = self.lineas_visibles()
            if len(lineas) == 1:
                nombre, _, valor = self.text().rpartition(" = ")
                icono = QIcon(opcion.icon)
                tam_icono = QSize(opcion.iconSize)
                opcion.text = ""
                opcion.icon = QIcon()
                painter.drawControl(QStyle.ControlElement.CE_PushButton, opcion)
                contenido = self.rect().adjusted(12, 2, -12, -2)
                izq = contenido.left()
                if not icono.isNull():
                    rect_ico = QRect(izq, self.height() // 2 - tam_icono.height() // 2, tam_icono.width(), tam_icono.height())
                    icono.paint(painter, rect_ico, Qt.AlignmentFlag.AlignCenter)
                    izq += tam_icono.width() + 6
                cifra_txt = f"= {valor}"
                f_cifra = estilo.fuente(estilo.T_CIFRA, mono=True)
                f_cifra.setWeight(QFont.Weight.DemiBold)
                ancho_cifra = QFontMetrics(f_cifra).horizontalAdvance(cifra_txt)
                ancho_nombre = max(20, contenido.left() + contenido.width() - izq - ancho_cifra - 8)
                r_nombre = QRectF(izq, contenido.top(), ancho_nombre, contenido.height())
                painter.save()
                painter.setFont(self.font())
                painter.setPen(opcion.palette.buttonText().color())
                nombre_elidido = painter.fontMetrics().elidedText(nombre, Qt.TextElideMode.ElideMiddle, int(r_nombre.width()))
                painter.drawText(r_nombre, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), nombre_elidido)
                painter.setFont(f_cifra)
                painter.drawText(QRectF(contenido), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), cifra_txt)
                painter.restore()
                return
            opcion.text = "\n".join(lineas)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, opcion)

    def ancho_natural(self, texto: str | None = None) -> int:
        """Lo que mide el botón con el texto entero (en negrita, como lo pone la entrada activa)."""
        fuente = QFont(self.font())
        fuente.setBold(True)
        return 2 * 10 + 2 * 2 + self.iconSize().width() + 8 + QFontMetrics(fuente).horizontalAdvance(self.text() if texto is None else texto)

    def indicar(self, on: bool) -> None:
        estado = (self.interruptor, self.enclavado, on)
        if estado == getattr(self, "_indicador", None):
            return
        self._indicador = estado
        pm = QPixmap(48, 40)
        pm.setDevicePixelRatio(2)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(estilo.SIMULACION if on else estilo.TINTA_3)
        p.setPen(QPen(color, 1.6))
        if self.interruptor:
            p.drawRoundedRect(QRectF(1, 4, 20, 12), 6, 6)
            p.setBrush(color)
            p.drawEllipse(QPointF(15 if on else 7, 10), 3.4, 3.4)
        elif self.enclavado:
            p.drawArc(QRectF(7, 1, 8, 12), 0, 180 * 16)
            p.setBrush(QColor(estilo.SIMULACION_SUAVE))
            p.drawRoundedRect(QRectF(5, 8, 12, 9), 1.5, 1.5)
            p.drawLine(11, 11, 11, 14)
        else:
            p.setBrush(QColor(estilo.LED_CONSOLA) if on else Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(11, 10), 5.5, 5.5)
        p.end()
        self.setIconSize(QSize(24, 20))
        self.setIcon(QIcon(pm))

    def nextCheckState(self) -> None:  # noqa: N802
        pass  # refrescar() pone el valor confirmado por la simulación


class TablaConsola(QTableWidget):
    """Tabla de consola de simulación: pinta cada fila como tarjeta limpia sin ocultar columnas ni datos."""

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        vp_w = self.viewport().width()
        fila_sel = self.currentRow()
        for r in range(self.rowCount()):
            y = self.rowViewportPosition(r)
            h = self.rowHeight(r)
            if y + h < 0 or y > self.viewport().height() or h <= 4:
                continue
            val_item = self.item(r, 2) if self.columnCount() > 2 else None
            es_salida_activa = (
                self.columnCount() == 4
                and self.item(r, 1) is not None
                and self.item(r, 1).text() == "salida continua"
                and val_item is not None
                and val_item.text() == "ON"
            )
            seleccionada = r == fila_sel and self.selectionModel() is not None and self.selectionModel().isRowSelected(r)
            if seleccionada:
                borde, fondo = estilo.ACENTO, estilo.ACENTO_SUAVE
            elif es_salida_activa:
                borde, fondo = estilo.SIMULACION_BORDE, estilo.SIMULACION_SUAVE
            else:
                borde, fondo = estilo.BORDE, estilo.SUPERFICIE_2
            rect = QRectF(1.5, y + 2.5, max(4, vp_w - 3), max(4, h - 5))
            p.setPen(QPen(QColor(borde), 1))
            p.setBrush(QColor(fondo))
            p.drawRoundedRect(rect, 5, 5)
        p.end()
        super().paintEvent(event)


class _DelegadoValorConsola(QStyledItemDelegate):
    """Pinta el valor «ON» de salidas continuas activas como una micro-pastilla verde discreta."""

    def paint(self, painter: Any, option: Any, index: Any) -> None:
        texto = str(index.data() or "")
        modelo = index.model()
        es_continua = False
        if modelo is not None:
            es_continua = str(modelo.index(index.row(), 1).data() or "") == "salida continua"
        if texto == "ON" and es_continua:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            fuente = QFont(option.font)
            fuente.setFamily(estilo.FUENTE_MONO)
            fuente.setBold(True)
            px = fuente.pixelSize()
            if px > 0:
                fuente.setPixelSize(max(10, px - 1))
            painter.setFont(fuente)
            fm = QFontMetrics(fuente)
            w = min(option.rect.width() - 4, fm.horizontalAdvance("ON") + 12)
            h = min(option.rect.height() - 6, max(16, fm.height() + 4))
            x = option.rect.left() + max(0, (option.rect.width() - w) // 2)
            y = option.rect.top() + max(0, (option.rect.height() - h) // 2)
            pill = QRectF(x, y, w, h)
            painter.setPen(QPen(QColor(estilo.SIMULACION_BORDE), 1))
            painter.setBrush(QColor("#dcfce7"))
            painter.drawRoundedRect(pill, h / 2, h / 2)
            painter.setPen(QColor(estilo.SIMULACION))
            painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), "ON")
            painter.restore()
            return
        super().paint(painter, option, index)


class _AjustaBanda(QObject):
    """Mantiene la franja de modo pegada al borde superior de la tarjeta del dibujo, a todo su ancho."""
    def __init__(self, tarjeta: QWidget, banda: QWidget) -> None:
        super().__init__(tarjeta)
        self.tarjeta, self.banda = tarjeta, banda

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            margen = estilo.R_M + 2  # dentro de las esquinas redondeadas de la tarjeta: el remate de la flecha no sobresale
            self.banda.setGeometry(margen, 0, max(0, self.tarjeta.width() - 2 * margen), 4)
            self.banda.raise_()
        return False


class _SalidaRaton(QObject):
    """Avisa de que el puntero sale del área visible de una tabla (para que la línea de detalle deje de hablar de la fila de debajo)."""

    def __init__(self, padre: QObject, al_salir: Any) -> None:
        super().__init__(padre)
        self.al_salir = al_salir

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() == QEvent.Type.Leave:
            self.al_salir()
        return False


class _VigilaAlto(QObject):
    """Llama a `fn` cada vez que cambia el tamaño de `objetivo`."""

    def __init__(self, objetivo: QWidget, fn: Callable[[], None]) -> None:
        super().__init__(objetivo)
        self.fn = fn
        objetivo.installEventFilter(self)

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() == QEvent.Type.Resize:
            self.fn()
        return False


class _DelegadoAbreviado(QStyledItemDelegate):
    """Enseña un texto corto en lugar del entero («continua» por «salida continua», «memoria» por «memorizada»): la celda sigue
    teniendo el texto entero (y lo lleva en su ayuda y en la línea de detalle), solo se pinta más corto para que la columna se lea.
    Con `corto` (la tabla no tiene sitio ni para la primera abreviatura) se pinta la más corta: «cont.», «mem.»."""

    def __init__(self, abreviaturas: dict[str, str], padre: QObject, cortas: dict[str, str] | None = None) -> None:
        super().__init__(padre)
        self.abreviaturas = abreviaturas
        self.cortas = cortas or abreviaturas
        self.corto = False

    def displayText(self, valor: Any, locale: Any) -> str:  # noqa: N802
        texto = str(valor)
        return (self.cortas if self.corto else self.abreviaturas).get(texto, texto)


class _AjustaCabecera(QObject):
    """Reparte favoritos, ayuda, zoom y buscador cuando cambia la tarjeta del dibujo."""
    def __init__(self, tarjeta: QWidget, ventana: Any) -> None:
        super().__init__(tarjeta)
        self.tarjeta, self.ventana = tarjeta, ventana

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self.ventana._ajustar_cabecera()
            self.ventana._zoom_diferido()  # (el alto del dibujo cambió, o se abrió el buscador: puede que el zoom deba ir en la cabecera o flotar)
        return False


class _FocoTeclado(QObject):
    """Un filtro por aplicación para el teclado.

    (1) **El anillo de foco solo se ve si la última entrada fue del teclado.** Qt da el foco por sí solo (al ocultarse el control
    que lo tenía, al cambiar de página, al abrir un panel…) y lo hace con el motivo «Tab», así que el motivo no sirve para saber
    si hay un teclado de por medio. El filtro recuerda la última entrada: una tecla de navegación (Tab, flechas, Espacio,
    Intro, Esc…) la pasa a «teclado» y un clic, la rueda o un toque la pasan a «ratón». El control con el foco lleva la propiedad
    `tecl` (cierta solo con el teclado) y la hoja global y las locales pintan el anillo con `[tecl="true"]:focus`; con la entrada
    cambiada a ratón, el que lo tenía lo pierde al instante. Los campos de texto no dependen de esto: en ellos se escribe y su
    foco se ve siempre.
    (2) Un botón con el foco se activa también con Intro, como con Espacio.
    (3) Los botones de la ventana no toman el foco con el ratón.
    (4) Soltar Ctrl suelta las entradas enclavadas con Ctrl+clic (antes lo hacía otro filtro: con uno solo, la aplicación hace una
    llamada menos por cada evento, que son decenas de miles al reconstruir la vista de E/S)."""
    TECLAS = frozenset((Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                        Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Space,
                        Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape))
    PUNTERO = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.Wheel, QEvent.Type.TouchBegin,
               QEvent.Type.TabletPress)
    CON_ANILLO = (QAbstractButton, QTabBar, QAbstractScrollArea, VistaLamina,
                  QComboBox, QAbstractSpinBox, QLineEdit)  # los controles cuyo anillo depende del teclado

    def __init__(self, padre: QObject | None = None) -> None:
        super().__init__(padre)
        self.teclado = False  # arrancar con el ratón: ningún anillo hasta la primera tecla de navegación

    def _marcar_foco(self, valor: bool) -> None:
        foco = QApplication.focusWidget()
        if foco is not None and isinstance(foco, self.CON_ANILLO):
            estilo.poner(foco, tecl=valor)

    INTERES = frozenset((*PUNTERO, QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.FocusIn, QEvent.Type.FocusOut, QEvent.Type.Show))

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        tipo = evento.type()
        if tipo not in self.INTERES:  # (el filtro ve todos los eventos de la aplicación: casi todos se descartan aquí, sin más)
            return False
        if tipo == QEvent.Type.KeyRelease:
            if evento.key() == Qt.Key.Key_Control and not evento.isAutoRepeat():  # soltar Ctrl suelta las entradas enclavadas con Ctrl+clic
                while objeto is not None:
                    if isinstance(objeto, _ventana()):
                        objeto._soltar_enclavados()
                        break
                    objeto = objeto.parent()
            return False
        if tipo in self.PUNTERO:
            if self.teclado:
                self.teclado = False
                self._marcar_foco(False)
        elif tipo == QEvent.Type.KeyPress and evento.key() in self.TECLAS:
            en_texto = isinstance(objeto, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit))
            es_tab = evento.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
            if (not en_texto or es_tab) and not self.teclado and (
                    es_tab or not evento.modifiers() & (
                        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                        | Qt.KeyboardModifier.MetaModifier)):
                self.teclado = True
                self._marcar_foco(True)
        elif tipo == QEvent.Type.FocusIn and isinstance(objeto, self.CON_ANILLO):
            estilo.poner(objeto, tecl=self.teclado)
        elif tipo == QEvent.Type.FocusOut and isinstance(objeto, self.CON_ANILLO):
            estilo.poner(objeto, tecl=False)
        if (tipo == QEvent.Type.KeyPress and evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not evento.modifiers() and isinstance(objeto, (QPushButton, QToolButton)) and objeto.hasFocus()
                and objeto.isEnabled() and isinstance(objeto.window(), _ventana())):
            objeto.animateClick()
            return True
        if (tipo == QEvent.Type.Show and isinstance(objeto, (QPushButton, QToolButton))
              and objeto.focusPolicy() in (Qt.FocusPolicy.StrongFocus, Qt.FocusPolicy.NoFocus) and not objeto.isCheckable()
              and isinstance(objeto.window(), _ventana())):
            objeto.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return False


class _RespuestaModbus(QObject):
    lista = Signal()

    def notificar(self):
        # El trabajador solo despierta al propietario; nunca toca Qt ni la sesión.
        try:
            self.lista.emit()
        except RuntimeError:
            pass  # La ventana puede haberse destruido mientras terminaba la red.
