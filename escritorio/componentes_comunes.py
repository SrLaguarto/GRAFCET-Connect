"""Componentes visuales comunes reutilizables de GRAFCET Connect 2.0 (propuesta #10, tanda T0b).

Reúne las cuatro piezas compartidas entre Consola, Variables, Propiedades, E/S, diálogos del sistema y Planos:
1. Pastilla booleana `0` / `1` con cifras tabulares (`PastillaBooleana` y `pintar_pastilla_booleana`).
2. Barra semántica de papel de variable `3,5 × 16 px` (`BarraPapel`, `pintar_barra_papel`, `pixmap_barra_papel`, `icono_barra_papel`).
3. Cabecera y pie estándar de diálogo con orden `Cancelar | Aceptar` (`CabeceraDialogo`, `PieDialogo`, `normalizar_botones_dialogo`).
4. Desplegables acotados a `300 px` con desplazamiento vertical (`acotar_desplegable`, `DesplegableAcotado`).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import estilo


# -- 1. Pastilla booleana 0 / 1 ------------------------------------------------------------------------------------

def colores_pastilla_booleana(valor: bool | int) -> tuple[str, str, str]:
    """Devuelve `(fondo, borde, texto)` para el estado booleano `0` o `1`."""
    if bool(valor):
        return estilo.BOOL_1_FONDO, estilo.BOOL_1_BORDE, estilo.BOOL_1_TEXTO
    return estilo.BOOL_0_FONDO, estilo.BOOL_0_BORDE, estilo.BOOL_0_TEXTO


def pintar_pastilla_booleana(
    pintor: QPainter,
    rect: QRect | QRectF,
    valor: bool | int,
    *,
    ancho_min: float = 24.0,
    alto: float = 20.0,
    px_fuente: int = 12,
) -> QRectF:
    """Dibuja una pastilla booleana `0` o `1` centrada dentro de `rect` y devuelve la caja pintada."""
    activo = bool(valor)
    fondo, borde, tinta = colores_pastilla_booleana(activo)
    r = QRectF(rect)
    h = min(alto, max(14.0, r.height()))
    w = min(max(ancho_min, h + 4.0), max(ancho_min, r.width()))
    if r.width() < w:
        w = max(14.0, r.width())
    caja = QRectF(
        r.left() + (r.width() - w) / 2.0,
        r.top() + (r.height() - h) / 2.0,
        w,
        h,
    ).adjusted(0.5, 0.5, -0.5, -0.5)
    radio = caja.height() / 2.0

    pintor.save()
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(QPen(QColor(borde), 1.0))
    pintor.setBrush(QColor(fondo))
    pintor.drawRoundedRect(caja, radio, radio)
    pintor.setFont(estilo.fuente_tabular(px=px_fuente, negrita=True))
    pintor.setPen(QColor(tinta))
    pintor.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), "1" if activo else "0")
    pintor.restore()
    return caja


class PastillaBooleana(QWidget):
    """Indicador compacto en cápsula que muestra `0` o `1` con cifras tabulares."""

    def __init__(self, valor: bool | int = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._valor = bool(valor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._actualizar_accesibilidad()

    @property
    def valor(self) -> bool:
        return self._valor

    def texto(self) -> str:
        return "1" if self._valor else "0"

    def poner_valor(self, valor: bool | int) -> None:
        nuevo = bool(valor)
        if nuevo != self._valor:
            self._valor = nuevo
            self._actualizar_accesibilidad()
            self.update()

    def _actualizar_accesibilidad(self) -> None:
        self.setAccessibleDescription(self.texto())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(26, 20)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(24, 20)

    def paintEvent(self, evento: QPaintEvent) -> None:  # noqa: N802
        del evento
        p = QPainter(self)
        pintar_pastilla_booleana(p, self.rect(), self._valor)
        p.end()


# -- 2. Barra semántica de papel de variable (3,5 × 16 px) ---------------------------------------------------------

def pintar_barra_papel(
    pintor: QPainter,
    x: float,
    centro_y: float,
    papel: str | None,
    *,
    ancho: float = estilo.BARRA_PAPEL_ANCHO,
    alto: float = estilo.BARRA_PAPEL_ALTO,
    radio: float = estilo.BARRA_PAPEL_RADIO,
) -> QRectF:
    """Dibuja la barra vertical `3,5 × 16 px` del papel de una variable centrada en `centro_y`."""
    caja = QRectF(float(x), float(centro_y) - alto / 2.0, ancho, alto)
    pintor.save()
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(estilo.color_papel_variable(papel)))
    pintor.drawRoundedRect(caja, radio, radio)
    pintor.restore()
    return caja


def pixmap_barra_papel(
    papel: str | None,
    *,
    ancho: float = estilo.BARRA_PAPEL_ANCHO,
    alto: float = estilo.BARRA_PAPEL_ALTO,
    margen_h: int = 2,
) -> QPixmap:
    """Genera un `QPixmap` nítido a 2× con la barra de papel de variable."""
    w_logico = max(6, int(round(ancho + 2 * margen_h)))
    h_logico = max(18, int(round(alto + 2)))
    pm = QPixmap(w_logico * 2, h_logico * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    pintar_barra_papel(p, (w_logico - ancho) / 2.0, h_logico / 2.0, papel, ancho=ancho, alto=alto)
    p.end()
    return pm


def icono_barra_papel(papel: str | None) -> QIcon:
    """Icono reutilizable con la barra `3,5 × 16 px` para celdas de tabla o listas."""
    return QIcon(pixmap_barra_papel(papel))


class BarraPapel(QWidget):
    """Widget ligero que pinta la barra vertical `3,5 × 16 px` del papel de una variable."""

    def __init__(self, papel: str | None = "input", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._papel = estilo.clave_papel_variable(papel)
        self.setFixedSize(6, 18)

    @property
    def papel(self) -> str:
        return self._papel

    def color(self) -> str:
        return estilo.color_papel_variable(self._papel)

    def poner_papel(self, papel: str | None) -> None:
        nuevo = estilo.clave_papel_variable(papel)
        if nuevo != self._papel:
            self._papel = nuevo
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(6, 18)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(6, 18)

    def paintEvent(self, evento: QPaintEvent) -> None:  # noqa: N802
        del evento
        p = QPainter(self)
        pintar_barra_papel(p, (self.width() - estilo.BARRA_PAPEL_ANCHO) / 2.0, self.height() / 2.0, self._papel)
        p.end()


# -- 3. Cabecera y pie estándar de diálogo (Cancelar | Aceptar) ----------------------------------------------------

def hoja_componentes_dialogo() -> str:
    """Reglas QSS para la cabecera y el pie estándar de diálogo."""
    return (
        f"QFrame#cabeceraDialogoComun {{ background:{estilo.SUPERFICIE}; border:0;"
        f" border-bottom:1px solid {estilo.DIVISOR_PANEL}; }}"
        f"QLabel#tituloDialogoComun {{ font-family:{estilo.FAMILIA_TITULO}; font-size:{estilo.T_SECCION}px;"
        f" font-weight:700; color:{estilo.TINTA}; background:transparent; border:0; }}"
        f"QLabel#subtituloDialogoComun {{ font-size:{estilo.T_PEQUENA}px; color:{estilo.TINTA_2};"
        f" background:transparent; border:0; }}"
        f"QToolButton#cerrarDialogoComun {{ border:1px solid transparent; border-radius:{estilo.R_CONTROL}px;"
        f" background:transparent; padding:2px; }}"
        f"QToolButton#cerrarDialogoComun:hover {{ background:{estilo.HOVER}; }}"
        f"QFrame#pieDialogoComun {{ background:{estilo.SUPERFICIE_PIE_DIALOGO}; border:0;"
        f" border-top:1px solid {estilo.DIVISOR_PANEL}; }}"
        f"QLabel#ayudaPieDialogoComun {{ font-size:{estilo.T_PEQUENA}px; color:{estilo.TINTA_3};"
        f" background:transparent; border:0; }}"
        f"QPushButton[pieDialogo=\"true\"] {{ min-height:{estilo.ALTO_ESTANDAR - 2}px;"
        f" max-height:{estilo.ALTO_ESTANDAR - 2}px; border-radius:{estilo.R_CONTROL}px; padding:0 14px; }}"
        f"QPushButton[pieDialogo=\"true\"][tecl=\"true\"]:focus {{ min-height:{estilo.ALTO_ESTANDAR - 4}px;"
        f" max-height:{estilo.ALTO_ESTANDAR - 4}px; padding:0 13px; }}"
    )


class _BarraAcentoCabecera(QWidget):
    """Barra vertical petróleo en la cabecera estándar de diálogo."""

    def __init__(self, color: str = estilo.PRIMARIO, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(6, 18)

    def paintEvent(self, evento: QPaintEvent) -> None:  # noqa: N802
        del evento
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._color))
        caja = QRectF((self.width() - estilo.BARRA_PAPEL_ANCHO) / 2.0, (self.height() - 16.0) / 2.0,
                      estilo.BARRA_PAPEL_ANCHO, 16.0)
        p.drawRoundedRect(caja, estilo.BARRA_PAPEL_RADIO, estilo.BARRA_PAPEL_RADIO)
        p.end()


class CabeceraDialogo(QFrame):
    """Cabecera limpia de diálogo con barra de acento, título, subtítulo opcional y botón de cierre opcional."""

    cerrar_pedido = Signal()

    def __init__(
        self,
        titulo: str,
        parent: QWidget | None = None,
        *,
        subtitulo: str = "",
        mostrar_cerrar: bool = False,
        barra_acento: bool = True,
        color_acento: str = estilo.PRIMARIO,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cabeceraDialogoComun")
        self.setStyleSheet(hoja_componentes_dialogo())

        fila = QHBoxLayout(self)
        fila.setContentsMargins(16, 10, 14, 10)
        fila.setSpacing(8)

        self.barra: QWidget | None = None
        if barra_acento:
            self.barra = _BarraAcentoCabecera(color_acento, self)
            fila.addWidget(self.barra, 0, Qt.AlignmentFlag.AlignVCenter)

        textos = QVBoxLayout()
        textos.setContentsMargins(0, 0, 0, 0)
        textos.setSpacing(2)
        self.etiqueta_titulo = QLabel(titulo, self)
        self.etiqueta_titulo.setObjectName("tituloDialogoComun")
        textos.addWidget(self.etiqueta_titulo)

        self.etiqueta_subtitulo = QLabel(subtitulo, self)
        self.etiqueta_subtitulo.setObjectName("subtituloDialogoComun")
        self.etiqueta_subtitulo.setWordWrap(True)
        self.etiqueta_subtitulo.setVisible(bool(subtitulo))
        textos.addWidget(self.etiqueta_subtitulo)
        fila.addLayout(textos, 1)

        self.boton_cerrar: QToolButton | None = None
        if mostrar_cerrar:
            cerrar = QToolButton(self)
            cerrar.setObjectName("cerrarDialogoComun")
            cerrar.setIcon(estilo.icono("cerrar", estilo.TINTA_2, tam=18))
            cerrar.setIconSize(QSize(18, 18))
            cerrar.setFixedSize(28, 28)
            cerrar.setToolTip("Cerrar")
            cerrar.setAccessibleName("Cerrar")
            cerrar.clicked.connect(self.cerrar_pedido.emit)
            fila.addWidget(cerrar, 0, Qt.AlignmentFlag.AlignVCenter)
            self.boton_cerrar = cerrar

    def poner_titulo(self, titulo: str) -> None:
        self.etiqueta_titulo.setText(titulo)

    def poner_subtitulo(self, subtitulo: str) -> None:
        self.etiqueta_subtitulo.setText(subtitulo)
        self.etiqueta_subtitulo.setVisible(bool(subtitulo))


def _estilizar_boton_pie(boton: QPushButton, *, primario: bool = False, alto: int = estilo.ALTO_ESTANDAR) -> None:
    boton.setMinimumHeight(alto)
    boton.setFixedHeight(alto)
    boton.setMinimumWidth(max(88, boton.sizeHint().width() + 8))
    estilo.poner(boton, primario=primario, pieDialogo=(alto == estilo.ALTO_ESTANDAR))
    if alto != estilo.ALTO_ESTANDAR:
        boton.setStyleSheet(
            f"min-height:{max(16, alto - 2)}px; max-height:{max(16, alto - 2)}px; border-radius:{estilo.R_CONTROL}px;"
        )


class PieDialogo(QFrame):
    """Pie estándar de diálogo con ayuda opcional a la izquierda y `Cancelar | Aceptar` a la derecha."""

    aceptado = Signal()
    rechazado = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        texto_aceptar: str = "Aceptar",
        texto_cancelar: str = "Cancelar",
        mostrar_cancelar: bool = True,
        texto_ayuda: str = "",
        alto_botones: int = estilo.ALTO_ESTANDAR,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pieDialogoComun")
        self.setStyleSheet(hoja_componentes_dialogo())

        self._fila = QHBoxLayout(self)
        self._fila.setContentsMargins(16, 10, 16, 10)
        self._fila.setSpacing(10)

        self._zona_izquierda = QHBoxLayout()
        self._zona_izquierda.setContentsMargins(0, 0, 0, 0)
        self._zona_izquierda.setSpacing(8)
        self.etiqueta_ayuda = QLabel(texto_ayuda, self)
        self.etiqueta_ayuda.setObjectName("ayudaPieDialogoComun")
        self.etiqueta_ayuda.setVisible(bool(texto_ayuda))
        self._zona_izquierda.addWidget(self.etiqueta_ayuda)
        self._fila.addLayout(self._zona_izquierda)
        self._fila.addStretch(1)

        self.boton_cancelar = QPushButton(texto_cancelar, self)
        self.boton_cancelar.setAutoDefault(False)
        self.boton_cancelar.setDefault(False)
        _estilizar_boton_pie(self.boton_cancelar, primario=False, alto=alto_botones)
        self.boton_cancelar.setVisible(mostrar_cancelar)
        self.boton_cancelar.clicked.connect(self.rechazado.emit)
        self._fila.addWidget(self.boton_cancelar)

        self.boton_aceptar = QPushButton(texto_aceptar, self)
        self.boton_aceptar.setDefault(True)
        self.boton_aceptar.setAutoDefault(True)
        _estilizar_boton_pie(self.boton_aceptar, primario=True, alto=alto_botones)
        self.boton_aceptar.clicked.connect(self.aceptado.emit)
        self._fila.addWidget(self.boton_aceptar)

    def poner_ayuda(self, texto: str) -> None:
        self.etiqueta_ayuda.setText(texto)
        self.etiqueta_ayuda.setVisible(bool(texto))

    def agregar_izquierda(self, widget: QWidget) -> None:
        """Añade un control auxiliar en el extremo izquierdo del pie (por ejemplo, «Probar conexión»)."""
        self._zona_izquierda.addWidget(widget)

    def conectar(self, dialogo: QDialog) -> PieDialogo:
        """Conecta `aceptado` y `rechazado` a `dialogo.accept` y `dialogo.reject`."""
        self.aceptado.connect(dialogo.accept)
        self.rechazado.connect(dialogo.reject)
        return self


def normalizar_botones_dialogo(
    caja: QDialogButtonBox,
    *,
    texto_aceptar: str | None = "Aceptar",
    texto_cancelar: str | None = "Cancelar",
    alto_botones: int = estilo.ALTO_ESTANDAR,
) -> tuple[QPushButton | None, QPushButton | None]:
    """Aplica textos en español, altura `32 px`, acento primario y orden visual `Cancelar | Aceptar` a un `QDialogButtonBox`."""
    aceptar: QPushButton | None = None
    cancelar: QPushButton | None = None
    otros: list[QPushButton] = []

    for boton in caja.buttons():
        if not isinstance(boton, QPushButton):
            continue
        rol = caja.buttonRole(boton)
        if rol == QDialogButtonBox.ButtonRole.AcceptRole and aceptar is None:
            aceptar = boton
        elif rol == QDialogButtonBox.ButtonRole.RejectRole and cancelar is None:
            cancelar = boton
        else:
            otros.append(boton)

    if cancelar is not None:
        if texto_cancelar is not None:
            cancelar.setText(texto_cancelar)
        cancelar.setDefault(False)
        cancelar.setAutoDefault(False)
        _estilizar_boton_pie(cancelar, primario=False, alto=alto_botones)

    if aceptar is not None:
        if texto_aceptar is not None:
            aceptar.setText(texto_aceptar)
        aceptar.setDefault(True)
        aceptar.setAutoDefault(True)
        _estilizar_boton_pie(aceptar, primario=True, alto=alto_botones)

    for boton in otros:
        _estilizar_boton_pie(boton, primario=False, alto=alto_botones)

    lay = caja.layout()
    if isinstance(lay, QHBoxLayout) and aceptar is not None and cancelar is not None:
        # En Windows `WinLayout` coloca `Aceptar` a la izquierda; reordenamos el layout a `... | Cancelar | Aceptar`.
        while lay.count():
            lay.takeAt(0)
        for boton in otros:
            lay.addWidget(boton)
        lay.addStretch(1)
        lay.addWidget(cancelar)
        lay.addWidget(aceptar)
        lay.activate()

    return cancelar, aceptar


# -- 4. Desplegables acotados a 300 px -----------------------------------------------------------------------------

class _FiltroDesplegableAcotado(QObject):
    """Asegura que tanto la vista como su contenedor emergente respeten `max_alto` al abrirse."""

    def __init__(self, vista: QAbstractItemView, max_alto: int) -> None:
        super().__init__(vista)
        self._vista = vista
        self.max_alto = max_alto

    def aplicar(self) -> None:
        self._vista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._vista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._vista.setMaximumHeight(self.max_alto)
        contenedor = self._vista.parentWidget()
        if contenedor is not None and contenedor is not self._vista.window():
            contenedor.setMaximumHeight(self.max_alto + 2)
        ventana = self._vista.window()
        if ventana is not None and ventana.windowFlags() & Qt.WindowType.Popup:
            ventana.setMaximumHeight(self.max_alto + 2)
            if ventana.height() > self.max_alto + 2:
                ventana.resize(ventana.width(), self.max_alto + 2)

    def eventFilter(self, vigilado: QObject, evento: QEvent) -> bool:  # noqa: N802
        del vigilado
        if evento.type() in (QEvent.Type.Show, QEvent.Type.PolishRequest, QEvent.Type.LayoutRequest):
            self.aplicar()
        return False


def acotar_desplegable(
    control: QComboBox | QAbstractItemView,
    max_alto: int = estilo.ALTO_MAX_DESPLEGABLE,
) -> QComboBox | QAbstractItemView:
    """Limita la altura desplegada de un `QComboBox` o `QAbstractItemView` a `max_alto` px (`300 px`) con barra vertical."""
    alto = max(80, int(max_alto))
    if isinstance(control, QComboBox):
        alto_fila = max(24, estilo.ALTO_FILA or 30)
        control.setMaxVisibleItems(max(3, (alto - 4) // alto_fila))
        vista = control.view()
    else:
        vista = control

    vista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    vista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    vista.setMaximumHeight(alto)

    filtro = getattr(vista, "_filtro_acotado_gc", None)
    if isinstance(filtro, _FiltroDesplegableAcotado):
        filtro.max_alto = alto
        filtro.aplicar()
    else:
        filtro = _FiltroDesplegableAcotado(vista, alto)
        setattr(vista, "_filtro_acotado_gc", filtro)
        vista.installEventFilter(filtro)
        filtro.aplicar()
    return control


class DesplegableAcotado(QComboBox):
    """`QComboBox` cuya lista desplegable nunca supera `max_alto` (`300 px`) y activa scroll vertical."""

    def __init__(self, parent: QWidget | None = None, *, max_alto: int = estilo.ALTO_MAX_DESPLEGABLE) -> None:
        super().__init__(parent)
        self._max_alto = max(80, int(max_alto))
        acotar_desplegable(self, self._max_alto)

    @property
    def max_alto_desplegable(self) -> int:
        return self._max_alto

    def poner_max_alto_desplegable(self, max_alto: int) -> None:
        self._max_alto = max(80, int(max_alto))
        acotar_desplegable(self, self._max_alto)

    def showPopup(self) -> None:  # noqa: N802
        acotar_desplegable(self, self._max_alto)
        super().showPopup()
        filtro = getattr(self.view(), "_filtro_acotado_gc", None)
        if isinstance(filtro, _FiltroDesplegableAcotado):
            filtro.aplicar()
