"""Los botones de herramientas con icono y texto lo llevan juntos y centrados (guía C3).

Qt dibuja el icono y el texto de un `QToolButton` con `ToolButtonTextBesideIcon` pegados a la izquierda del área de contenido y deja
el sobrante a la derecha. La hoja de estilo no delega esa etiqueta en el estilo base (la pinta con `QCommonStyle`), pero sí le pasa a
este estilo, uno tras otro, el icono (`drawItemPixmap`) y el texto (`drawItemText`), con el botón como dispositivo del pintor. Aquí se
retiene el icono hasta recibir el texto y se pintan los dos como un único bloque (icono, separación, texto) centrado en el área de
contenido, que es la del texto más lo que ocupa su celda de icono. Todo lo demás lo delega.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleOptionMenuItem, QToolButton

from . import estilo

SEPARACION = 4  # entre el icono y el texto (lo que deja Qt)
RELLENO_ICONO = 8  # Qt reserva para el icono su ancho más 8 px (4 a cada lado)


def _boton_con_icono_y_texto(pintor: Any) -> QToolButton | None:
    dispositivo = pintor.device()
    if (isinstance(dispositivo, QToolButton) and dispositivo.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            and dispositivo.text() and not dispositivo.icon().isNull()):
        return dispositivo
    return None


class EstiloBotones(QProxyStyle):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self._icono: tuple[QRect, Any, Any] | None = None  # el icono retenido: celda, pixmap y botón

    def pixelMetric(self, metrica, opcion=None, widget=None):  # noqa: N802
        if metrica == QStyle.PixelMetric.PM_ToolBarExtensionExtent:
            return estilo.ALTO_CONTROL
        return super().pixelMetric(metrica, opcion, widget)

    def drawPrimitive(self, elemento: Any, opcion: Any, pintor: Any, widget: Any = None) -> None:  # noqa: N802
        """Una opción excluyente de un menú (grupo de acciones exclusivo) se marca con un punto de radio, no con la marca de verificación."""
        if (elemento == QStyle.PrimitiveElement.PE_IndicatorMenuCheckMark and isinstance(opcion, QStyleOptionMenuItem)
                and opcion.checkType == QStyleOptionMenuItem.CheckType.Exclusive):
            pintor.save()
            pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(opcion.palette.color(opcion.palette.ColorRole.Text))
            centro = QRectF(opcion.rect).center()
            pintor.drawEllipse(centro, 3.0, 3.0)
            pintor.restore()
            return
        super().drawPrimitive(elemento, opcion, pintor, widget)

    def drawItemPixmap(self, pintor: Any, rect: QRect, alineacion: int, pixmap: Any) -> None:  # noqa: N802
        boton = _boton_con_icono_y_texto(pintor)
        if boton is None or alineacion != int(Qt.AlignmentFlag.AlignCenter):
            super().drawItemPixmap(pintor, rect, alineacion, pixmap)
            return
        self._icono = (QRect(rect), pixmap, boton)

    def drawItemText(self, pintor: Any, rect: QRect, alineacion: int, paleta: Any, activo: bool, texto: str,  # noqa: N802
                     papel: Any = None) -> None:
        if self._icono is None and self._solo_texto(pintor.device()) and texto.count(chr(10)) == 0:
            rect = self._tinta_centrada(pintor, rect, alineacion, texto)  # (un texto suelto: se centra su tinta, no su avance)
        retenido, self._icono = self._icono, None
        if retenido is None or _boton_con_icono_y_texto(pintor) is not retenido[2]:
            if retenido is not None:  # (el icono no era de este texto: sale donde lo puso Qt)
                super().drawItemPixmap(pintor, retenido[0], int(Qt.AlignmentFlag.AlignCenter), retenido[1])
            super().drawItemText(pintor, rect, alineacion, paleta, activo, texto, *([] if papel is None else [papel]))
            return
        celda, pixmap, _ = retenido
        ancho_icono = round(pixmap.deviceIndependentSize().width())
        ancho_texto = pintor.fontMetrics().size(Qt.TextFlag.TextShowMnemonic, texto).width() + 1
        ancho_contenido = rect.right() - celda.left() + 1  # del borde izquierdo del icono al derecho del texto
        izquierda = celda.left() + (ancho_contenido - (ancho_icono + SEPARACION + ancho_texto)) // 2
        super().drawItemPixmap(pintor, QRect(izquierda, celda.top(), ancho_icono, celda.height()),
                               int(Qt.AlignmentFlag.AlignCenter), pixmap)
        zona = QRect(izquierda + ancho_icono + SEPARACION, rect.top(), ancho_texto, rect.height())
        super().drawItemText(pintor, zona, alineacion, paleta, activo, texto, *([] if papel is None else [papel]))

    @staticmethod
    def _solo_texto(boton: Any) -> bool:
        """Un botón de herramientas que solo lleva texto (también uno «solo icono» sin icono: Qt lo pinta como solo texto)."""
        if not isinstance(boton, QToolButton):
            return False
        forma = boton.toolButtonStyle()
        return forma == Qt.ToolButtonStyle.ToolButtonTextOnly or (forma == Qt.ToolButtonStyle.ToolButtonIconOnly and boton.icon().isNull())

    @staticmethod
    def _tinta_centrada(pintor: Any, rect: QRect, alineacion: int, texto: str) -> QRect:
        """El rectángulo desplazado lo que haga falta para que la tinta de un texto centrado (el signo ▾ de «Ayuda ▾» deja más hueco a un
        lado que a otro) quede a la misma distancia de los dos lados."""
        if not int(alineacion) & int(Qt.AlignmentFlag.AlignHCenter):
            return rect
        limpio = texto.replace("&", "")
        fm = pintor.fontMetrics()
        tinta = fm.tightBoundingRect(limpio)
        izquierdo = tinta.left()
        derecho = fm.horizontalAdvance(limpio) - (tinta.right() + 1)
        return rect.translated((derecho - izquierdo) // 2, 0)


def instalar(app: QApplication | None = None) -> None:
    """Pone el estilo sobre el de la aplicación, una sola vez."""
    app = app or QApplication.instance()
    if app is None or isinstance(app.style(), EstiloBotones):
        return
    app.setStyle(EstiloBotones(app.style().name()))
