"""Piezas de la ventana de Propiedades rediseñada (E8): el comentario de una línea que crece y se estira, el pie con la etiqueta y el
comentario, y el conmutador de partes («Condición | Acción», «Evento | Acción»).

Son widgets sueltos, sin conocer la edición: la ventana (`flotantes.py`) y el panel (`propiedades.py`) los montan. Los colores y medidas
salen de `estilo.py` (P-IMP-140)."""
from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QWidget)

from . import estilo

LINEAS_COMENTARIO = 4  # lo que crece el comentario con su texto; más, se desplaza por dentro
LINEAS_ESTIRADO = 12  # lo más que lo estira el usuario desde la esquina
LADO_AGARRE = 12
LADO_MARCA = 8  # el cuadradito de color de cada botón del conmutador
LADO_AVISO = 7  # el punto de aviso
ANCHO_ETIQUETA = 62  # el campo de la etiqueta de la transición («t1», «T12»…), como en la maqueta


def una_linea(texto: str) -> str:
    """El texto del comentario en una sola línea: cada salto (pegado) pasa a un espacio."""
    return re.sub(r"[ \t]*(?:\r\n|\r|\n| | )[ \t]*", " ", texto)


class _Agarre(QWidget):
    """La esquina inferior derecha del comentario: se arrastra en vertical para estirarlo."""

    def __init__(self, campo: "CampoComentario") -> None:
        super().__init__(campo)
        self._campo = campo
        self._origen: tuple[int, int] | None = None
        self.setFixedSize(LADO_AGARRE, LADO_AGARRE)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Arrastre para estirar el comentario")

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(estilo.TINTA_2), 1))
        w, h = self.width() - 2, self.height() - 2
        for k in (4, 8):
            p.drawLine(QPointF(w, h - k), QPointF(w - k, h))
        p.end()

    def mousePressEvent(self, evento: Any) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self._origen = (int(evento.globalPosition().y()), self._campo.height())
            evento.accept()

    def mouseMoveEvent(self, evento: Any) -> None:  # noqa: N802
        if self._origen is not None:
            y0, h0 = self._origen
            self._campo.estirar(h0 + int(evento.globalPosition().y()) - y0)
            evento.accept()

    def mouseReleaseEvent(self, evento: Any) -> None:  # noqa: N802
        self._origen = None
        evento.accept()


class CampoComentario(QPlainTextEdit):
    """El comentario de una transición: una sola línea de texto, mostrada en varias si no cabe. Ajusta al ancho, crece con el texto (hasta
    `LINEAS_COMENTARIO`; después se desplaza por dentro) y se estira desde la esquina. Intro no escribe un salto (la ventana lo trata como
    confirmar), un salto pegado pasa a un espacio y `text()` es siempre una línea. Imita lo que Propiedades usa de un `QLineEdit`:
    `text`, `setText` y `editingFinished` (al perder el foco)."""

    editingFinished = Signal()
    una_linea = True  # lo lee `GestorFlotantes._intro`: Intro sin modificadores confirma, aunque sea un editor de varias líneas

    def __init__(self) -> None:
        super().__init__()
        self._alto_usuario = 0  # el alto al que lo estiró el usuario (0: el del texto)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTabChangesFocus(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._agarre = _Agarre(self)
        self.textChanged.connect(self._ajustar_alto)
        self._ajustar_alto()

    # -- la API de un campo de una línea
    def text(self) -> str:
        return self.toPlainText()

    def setText(self, texto: str) -> None:  # noqa: N802
        self.setPlainText(una_linea(texto))

    def insertFromMimeData(self, origen: Any) -> None:  # noqa: N802
        if origen.hasText():
            self.insertPlainText(una_linea(origen.text()))

    def keyPressEvent(self, evento: Any) -> None:  # noqa: N802
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            evento.accept()  # nunca un salto: Intro confirma (lo hace la ventana) y Mayús+Intro no hace nada
            return
        super().keyPressEvent(evento)

    def focusOutEvent(self, evento: Any) -> None:  # noqa: N802
        super().focusOutEvent(evento)
        self.editingFinished.emit()

    # -- el alto
    def _lineas(self) -> int:
        return max(1, round(self.document().size().height()))

    def alto_minimo(self) -> int:
        return max(estilo.ALTO_CONTROL_COMPACTO, self._alto_para(1))

    def _alto_para(self, lineas: int) -> int:
        fm = QFontMetrics(self.font())
        return fm.lineSpacing() * lineas + int(2 * self.document().documentMargin()) + 2 * self.frameWidth() + 2

    def alto_por_texto(self) -> int:
        return max(self.alto_minimo(), self._alto_para(min(self._lineas(), LINEAS_COMENTARIO)))

    def _ajustar_alto(self) -> None:
        alto = max(self.alto_por_texto(), self._alto_usuario)
        if self.height() != alto or self.minimumHeight() != alto or self.maximumHeight() != alto:
            self.setFixedHeight(alto)
        self._colocar_agarre()

    def estirar(self, alto: int) -> None:
        """Estirado por el usuario: entre lo que pide el texto y `LINEAS_ESTIRADO` líneas."""
        tope = self._alto_para(LINEAS_ESTIRADO)
        self._alto_usuario = 0 if alto <= self.alto_por_texto() else min(alto, tope)
        self._ajustar_alto()

    def _colocar_agarre(self) -> None:
        barra = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        self._agarre.move(max(0, self.width() - LADO_AGARRE - barra - 1), max(0, self.height() - LADO_AGARRE - 1))
        self._agarre.raise_()

    def resizeEvent(self, evento: Any) -> None:  # noqa: N802
        super().resizeEvent(evento)
        self._ajustar_alto()  # (el ajuste de línea cambia con el ancho)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(super().sizeHint().width(), max(self.alto_por_texto(), self._alto_usuario))


class PiePropiedades(QWidget):
    """Lo que se usa poco, al pie de la ventana, bajo un filete de 1 px (como la maqueta v3): «Etiqueta [t1]» a la izquierda y «Comentario» con
    su campo a la derecha. Los rótulos van centrados con la primera línea de su campo. Los campos los crea el panel (`t_etiqueta`,
    `t_comentario`…) y aquí se colocan; el pie no sabe de ediciones."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("piePropiedades")
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, estilo.E3 + 1, 0, 0)  # (el filete y, bajo él, E3 de aire)
        raiz.setSpacing(estilo.E2)
        self._fila = raiz
        self.l_etiqueta = self._rotulo("Etiqueta")
        self.l_comentario = self._rotulo("Comentario")
        self.campos: tuple[QWidget, ...] = ()

    @staticmethod
    def _rotulo(texto: str) -> QLabel:
        r = QLabel(texto)
        r.setStyleSheet(f"color: {estilo.TINTA_2}; background: transparent")
        return r

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setPen(QColor(estilo.BORDE))
        p.drawLine(0, 0, self.width(), 0)
        p.end()

    def poner(self, etiqueta: QWidget, extra: QWidget | None, comentario: QWidget) -> None:
        """Coloca el campo de la etiqueta (con una casilla opcional detrás) y el del comentario."""
        self.campos = tuple(w for w in (etiqueta, extra, comentario) if w is not None)
        raiz = self._fila
        raiz.addWidget(self.l_etiqueta, 0, Qt.AlignmentFlag.AlignTop)
        etiqueta.setFixedWidth(ANCHO_ETIQUETA)
        raiz.addWidget(etiqueta, 0, Qt.AlignmentFlag.AlignTop)
        if extra is not None:
            raiz.addWidget(extra, 0, Qt.AlignmentFlag.AlignTop)
        raiz.addSpacing(estilo.E3)
        raiz.addWidget(self.l_comentario, 0, Qt.AlignmentFlag.AlignTop)
        raiz.addWidget(comentario, 1)
        for w in self.campos:
            w.show()
        self.escalar()

    def escalar(self) -> None:
        """Los rótulos miden lo que un campo de la escala activa, para quedar centrados con su primera línea."""
        for r in (self.l_etiqueta, self.l_comentario):
            r.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO)

    def alto_nominal(self) -> int:
        """Lo que mide el pie con el comentario de una línea (lo que se reserva a la ventana; si el comentario crece, el formulador cede)."""
        return estilo.ALTO_CONTROL + estilo.E3 + 1


class _BotonParte(QPushButton):
    """Un botón del conmutador (maqueta v3): lleva el cuadradito del color de su parte; el activo, relleno con ese color y letra blanca; el
    de abajo con el puntero encima, HOVER; uno desactivado, en DESHABILITADO."""

    def __init__(self, texto: str, color: str) -> None:
        super().__init__(texto)
        self.color = color
        self.aviso = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # (repinta al entrar y salir el puntero)

    def sizeHint(self) -> QSize:  # noqa: N802
        ancho = self.fontMetrics().horizontalAdvance(self.text()) + 4 * estilo.E3 + LADO_MARCA
        return QSize(ancho, estilo.ALTO_CONTROL_COMPACTO - 2 * estilo.E1 + 2)

    def paintEvent(self, evento: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        activo, habil = self.isChecked(), self.isEnabled()
        color = QColor(self.color if habil else estilo.DESHABILITADO)
        zona = QRectF(self.rect())
        if activo:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(zona, estilo.R_S, estilo.R_S)
        elif self.underMouse() and habil:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(estilo.HOVER))
            p.drawRoundedRect(zona, estilo.R_S, estilo.R_S)
        marca = QRectF(zona.left() + estilo.E3, zona.center().y() - LADO_MARCA / 2, LADO_MARCA, LADO_MARCA)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("white") if activo else color)
        p.drawRoundedRect(marca, 2, 2)
        p.setPen(QColor("white") if activo else QColor(estilo.TINTA_2 if habil else estilo.DESHABILITADO))
        fuente = self.font()
        fuente.setBold(True)
        p.setFont(fuente)
        texto = zona.adjusted(estilo.E3 + LADO_MARCA + estilo.E2 - 2, 0, -estilo.E3, 0)
        p.drawText(texto, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        if self.aviso:  # el punto de «a esta parte le falta algo», arriba a la derecha
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(estilo.AVISO_BORDE))
            p.drawEllipse(QPointF(zona.right() - 2 - LADO_AVISO / 2, zona.top() + 2 + LADO_AVISO / 2), LADO_AVISO / 2, LADO_AVISO / 2)
        if self.hasFocus():
            p.setPen(QPen(QColor(estilo.FOCO), 2, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(zona.adjusted(2, 2, -2, -2), estilo.R_S, estilo.R_S)
        p.end()


class ConmutadorPartes(QFrame):
    """Botones segmentados para elegir la parte que se edita: cada uno lleva el color de su parte y el activo va relleno. `elegida(clave)`
    avisa de un cambio hecho por el usuario; `poner` lo cambia sin avisar. `avisar(clave, True)` pone el punto de aviso."""

    elegida = Signal(str)

    def __init__(self, partes: list[tuple[str, str, str]]) -> None:
        """`partes`: (clave, texto, color) de cada parte, en orden."""
        super().__init__()
        self.setObjectName("conmutadorPartes")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame#conmutadorPartes {{ background: {estilo.SUPERFICIE}; border: 1px solid {estilo.BORDE_CONTROL}; "
                           f"border-radius: 6px; }}")
        fila = QHBoxLayout(self)
        fila.setContentsMargins(2, 2, 2, 2)
        fila.setSpacing(2)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        self.botones: dict[str, _BotonParte] = {}
        for clave, texto, color in partes:
            b = _BotonParte(texto, color)
            b.setAccessibleName(f"Editar {texto.lower()}")
            b.clicked.connect(lambda _=False, c=clave: self._pulsado(c))
            self._grupo.addButton(b)
            fila.addWidget(b)
            self.botones[clave] = b
        if self.botones:
            next(iter(self.botones.values())).setChecked(True)

    def _pulsado(self, clave: str) -> None:
        self.botones[clave].setChecked(True)
        self.elegida.emit(clave)

    def clave(self) -> str:
        return next((c for c, b in self.botones.items() if b.isChecked()), "")

    def poner(self, clave: str) -> None:
        if clave in self.botones:
            self.botones[clave].setChecked(True)
            for b in self.botones.values():
                b.update()

    def avisar(self, clave: str, falta: bool) -> None:
        b = self.botones.get(clave)
        if b is not None and b.aviso != falta:
            b.aviso = falta
            b.setToolTip("Falta algo en esta parte" if falta else "")
            b.update()
