"""La banda superior derecha del editor de bloques (`.op-ribbon` del diseño 2.0.1).

En modo booleano muestra:
  Insertar: [( … )] [Temporizador] [● = ≠ < ≥] | [1] [0]   ···   [Copiar] [Pegar] [↶] [↷] [Limpiar]

En modo valor numérico muestra:
  Insertar: [( … )] [+ Constante]                            ···   [Copiar] [Pegar] [↶] [↷] [Limpiar]

Cada botón de inserción admite clic (inserta en el carril o grupo activo) y arrastre (suelta en cualquier punto).
"""
from __future__ import annotations

import json
from typing import Any, Callable

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from . import estilo
from .arrastre_popup import ejecutar_arrastre
from .bloques import (_ARRASTRE, MIME, FlowLayout, Motor, nuevo, var)

# Mantenidos por compatibilidad con utilidades/pruebas que consultan las tablas de botones
BOTONES = {
    "operador": [
        ("( … )", "par", "Paréntesis: agrupa bloques. Con bloques elegidos, los envuelve; sin selección, abre un grupo nuevo."),
    ],
    "tiempo": [
        ("Temporizador", "temp", "Temporizador GRAFCET (t1/X/t2): retardo al activar y/o desactivar. Edita t1, variable y t2 in-situ."),
    ],
    "comparacion": [
        ("= ≠ < ≥", "cmp", "Compara una variable numérica con un valor: = ≠ < ≤ > ≥."),
    ],
    "constante": [
        ("1", "uno", "Constante siempre verdadera (1)."),
        ("0", "cero", "Constante siempre falsa (0)."),
    ],
    "aritm": [
        ("( … )", "par", "Paréntesis: agrupa una subexpresión aritmética."),
    ],
    "numero": [
        ("+ Constante", "num", "Inserta un número editable."),
    ],
}

_COLOR_PUNTO = {
    "cmp": "#0369a1",
}


def _icono_punto(color: str) -> QIcon:
    """Punto de color para el botón Comparación."""
    pm = QPixmap(16, 16)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(0, 0, 7, 7)
    p.end()
    return QIcon(pm)


def _icono_temporizador() -> QIcon:
    """Trazo del juego de la aplicación a 2×. Su original revisable está en recursos/temporizador.svg."""
    lado = estilo.E4
    pm = QPixmap(2 * lado, 2 * lado)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(lado / 24, lado / 24)
    p.setPen(QPen(QColor(estilo.TINTA), 1.75, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawEllipse(QRectF(4, 6, 16, 16))
    p.drawLine(QPointF(9, 2), QPointF(15, 2))
    p.drawLine(QPointF(12, 2), QPointF(12, 6))
    p.drawLine(QPointF(18, 8), QPointF(20, 6))
    aguja = QPainterPath(QPointF(12, 10))
    aguja.lineTo(12, 14)
    aguja.lineTo(15, 14)
    p.drawPath(aguja)
    p.end()
    return QIcon(pm)


class BotonCompacto(QPushButton):
    """Botón compacto de altura fija (26 px) para la cinta de inserción y la barra contextual."""

    tam: QSize | None = None

    def poner_tam(self, ancho: int, alto: int) -> None:
        self.tam = QSize(ancho, alto)
        self.setFixedSize(self.tam)

    def event(self, ev: Any) -> bool:
        r = super().event(ev)
        if self.tam is not None and ev.type() in (QEvent.Type.Polish, QEvent.Type.StyleChange, QEvent.Type.ParentChange) \
                and (self.minimumSize() != self.tam or self.maximumSize() != self.tam):
            self.setFixedSize(self.tam)
        return r

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.tam) if self.tam is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


class BotonBloque(BotonCompacto):
    """Un botón de inserción de la cinta: clic o arrastre."""
    arrastrado = Signal()

    def __init__(self, banda: "BandaBloques", rotulo: str, clave: str, ayuda: str) -> None:
        super().__init__(rotulo)
        self.banda, self.clave = banda, clave
        self.setToolTip(ayuda)
        self.setAccessibleName(rotulo)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._origen: QPoint | None = None
        if clave == "temp":
            self.setIcon(_icono_temporizador())
            self.setIconSize(QSize(estilo.E4, estilo.E4))
        elif clave in _COLOR_PUNTO:
            self.setIcon(_icono_punto(_COLOR_PUNTO[clave]))
            self.setIconSize(QSize(8, 8))
        f = QFont(self.font())
        if clave in ("par", "uno", "cero"):
            f = QFont(estilo.FUENTE_MONO)
            f.setBold(True)
        f.setPixelSize(12)
        self.setFont(f)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origen = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if self._origen is not None and event.buttons() & Qt.MouseButton.LeftButton \
                and (event.position().toPoint() - self._origen).manhattanLength() >= 6:
            self._origen = None
            self.setDown(False)
            self._arrastrar()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        self._origen = None
        super().mouseReleaseEvent(event)

    def _arrastrar(self) -> None:
        nodo = self.banda.nodo(self.clave)
        mime = self.banda.mime(nodo)
        drag = QDrag(self)
        drag.setMimeData(mime)
        motor = Motor(self.banda.fuente)
        motor.botones = False
        drag.setPixmap(motor.pixmap(nodo, 240, self.devicePixelRatioF()))
        drag.setHotSpot(QPoint(12, 12))
        _ARRASTRE["resuelto"] = False
        ejecutar_arrastre(drag, self.window())
        self.setDown(False)
        self.arrastrado.emit()


class BandaBloques(QFrame):
    """Cinta fija `.op-ribbon` encima del carril de bloques: inserción a la izquierda, herramientas a la derecha.
    Se adapta en 1 o 2 filas automáticamente cuando el emergente se estrecha (p. ej. a media pantalla)."""
    insertar = Signal(object)
    alto_cambiado = Signal()

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str, valor: bool = False) -> None:
        super().__init__()
        self.fuente, self.grupo, self.valor = fuente, grupo, valor
        self.setObjectName("bandaBloques")
        self.categorias: dict[str, QLabel] = {}
        self.botones: dict[str, list[BotonBloque]] = {}
        self._herramientas: list[QPushButton] = []
        self._en_dos_filas: bool | None = None

        from PySide6.QtWidgets import QVBoxLayout
        self._vlay = QVBoxLayout(self)
        self._vlay.setContentsMargins(10, 6, 10, 6)
        self._vlay.setSpacing(5)

        self._fila1 = QHBoxLayout()
        self._fila1.setContentsMargins(0, 0, 0, 0)
        self._fila1.setSpacing(5)
        self._vlay.addLayout(self._fila1)

        self._fila2 = QHBoxLayout()
        self._fila2.setContentsMargins(0, 0, 0, 0)
        self._fila2.setSpacing(5)
        self._vlay.addLayout(self._fila2)

        self._caja_ins = QWidget(self)
        self._lay_ins = QHBoxLayout(self._caja_ins)
        self._lay_ins.setContentsMargins(0, 0, 0, 0)
        self._lay_ins.setSpacing(5)

        self.l_prefijo = QLabel("Insertar:")
        self.l_prefijo.setObjectName("rotuloBanda")
        self._lay_ins.addWidget(self.l_prefijo)

        claves = ("aritm", "numero") if valor else ("operador", "tiempo", "comparacion", "constante")
        for clave in claves:
            self.categorias[clave] = self.l_prefijo
            if clave == "constante":
                sep = QFrame()
                sep.setObjectName("sepBanda")
                sep.setFixedSize(1, 18)
                self._lay_ins.addWidget(sep)
            self.botones[clave] = []
            for texto, tipo, ayuda in BOTONES[clave]:
                b = BotonBloque(self, texto, tipo, ayuda)
                b.clicked.connect(lambda _=False, t=tipo: self.insertar.emit(self.nodo(t)))
                self._lay_ins.addWidget(b)
                self.botones[clave].append(b)

        self._caja_herr = QWidget(self)
        self._lay_herr = QHBoxLayout(self._caja_herr)
        self._lay_herr.setContentsMargins(0, 0, 0, 0)
        self._lay_herr.setSpacing(4)

        self._fila1.addWidget(self._caja_ins)
        self._fila1.addStretch(1)
        self._fila1.addWidget(self._caja_herr)
        self._en_dos_filas = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.escalar()

    def fijar_prefijo(self, texto: str) -> None:
        """Actualiza el rótulo izquierdo (p. ej. `CT :=` en modo valor numérico o `Insertar:`)."""
        self.l_prefijo.setText(texto)
        self.ajustar_alto()

    def anadir_herramientas(self, botones: list[QPushButton], flujo: bool = True) -> None:
        """Coloca las herramientas (Copiar, Pegar, ↶, ↷, Limpiar) en el extremo derecho de la cinta."""
        for b in botones:
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            b.setProperty("herramienta", True)
            if b not in self._herramientas:
                self._herramientas.append(b)
            if flujo:
                self._lay_herr.addWidget(b)
        self.escalar()

    def nodo(self, clave: str) -> dict[str, Any]:
        """Crea el bloque correspondiente a un botón de la cinta (incluye claves heredadas para compatibilidad)."""
        variables, etapas = self.fuente()
        if clave in ("temp", "retardo_activar", "retardo_desactivar"):
            import re
            por_num = lambda x: (0, int(x[1:]), "") if re.fullmatch(r"X\d+", x) else (1, 0, x.lower())  # noqa: E731
            etapas_ord = sorted(dict.fromkeys(etapas), key=por_num)
            if etapas_ord:
                base = nuevo("etapa", n=etapas_ord[0])
            else:
                primera = next((n for n, (r, t) in variables.items() if t == "bool" and r == "input"), None) \
                    or next((n for n, (_, t) in variables.items() if t == "bool"), None)
                base = var(primera, variables[primera][0]) if primera else None
            if clave == "retardo_desactivar":
                return nuevo("temp", t1="", t2="3s", a=base)
            return nuevo("temp", t1="5s" if clave == "temp" else "3s", t2="", a=base)
        if clave == "uno":
            return nuevo("const", v=1)
        if clave == "cero":
            return nuevo("const", v=0)
        if clave == "num":
            return nuevo("num", v="1")
        if clave in ("mas", "menos", "por", "entre"):
            return nuevo("ar", op={"mas": "+", "menos": "-", "por": "*", "entre": "/"}[clave])
        if clave == "cmp":
            numericas = [n for n, (_, t) in variables.items() if t != "bool"]
            return nuevo("cmp", n=numericas[0] if numericas else None, op=">=", v="10")
        return nuevo(clave)

    def mime(self, nodo: dict[str, Any]) -> QMimeData:
        mime = QMimeData()
        mime.setData(MIME, json.dumps({"nodo": nodo, "grupo": self.grupo, "origen": None}).encode())
        return mime

    def _hoja(self) -> str:
        return (f"QFrame#bandaBloques {{ background: #f6f8fb; border: 0; border-bottom: 1px solid #cdd6e0; border-radius: 0; }}"
                f"QFrame#sepBanda {{ background: #d2dce6; border: 0; }}"
                f"QLabel#rotuloBanda {{ color: #5b6b7d; font-size: 11.5px; font-weight: 600; background: transparent; border: 0; }}"
                f"QFrame#bandaBloques QPushButton {{ min-height: 24px; max-height: 26px; min-width: 0; padding: 0 8px; "
                f"background: #ffffff; border: 1px solid #c3cedb; border-radius: 4px; "
                f"color: #16263a; font-size: 12px; font-weight: 600; }}"
                f"QFrame#bandaBloques QPushButton[herramienta=\"true\"] {{ background: #f8fafc; color: #4a5b6e; "
                f"font-size: 11.5px; font-weight: 500; padding: 0 7px; }}"
                f"QFrame#bandaBloques QPushButton:disabled {{ color: #a0aec0; border-color: #dde4ec; background: #f8fafc; }}"
                f"QFrame#bandaBloques QPushButton:hover:enabled {{ border-color: {estilo.ACENTO}; background: #cfeee6; color: {estilo.ACENTO_OSCURO}; }}"
                f"QFrame#bandaBloques QPushButton:pressed {{ background: {estilo.ACENTO}; color: #ffffff; }}"
                f"QFrame#bandaBloques QPushButton[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; }}")

    def escalar(self) -> None:
        self.setStyleSheet(self._hoja())
        alto = 26
        for b in [b for botones in self.botones.values() for b in botones]:
            f = QFont(b.font())
            f.setPixelSize(12)
            f.setWeight(QFont.Weight.DemiBold)
            b.setFont(f)
            icono_w = b.iconSize().width() + estilo.E1 if not b.icon().isNull() else 0
            ancho = max(round(QFontMetricsF(f).horizontalAdvance(b.text())) + 20 + icono_w, alto)
            b.poner_tam(ancho, alto)
        for b in self._herramientas:
            f = QFont(b.font())
            f.setPixelSize(12 if len(b.text()) <= 2 else 11)
            f.setWeight(QFont.Weight.Medium)
            b.setFont(f)
            ancho = max(round(QFontMetricsF(f).horizontalAdvance(b.text())) + 18, alto)
            b.poner_tam(ancho, alto)
        self.ajustar_alto(True)

    def _ancho_necesario_una_fila(self) -> int:
        return self._caja_ins.sizeHint().width() + self._caja_herr.sizeHint().width() + 28

    def _aplicar_filas(self, dos_filas: bool) -> None:
        if dos_filas == self._en_dos_filas:
            return
        self._en_dos_filas = dos_filas
        for lay in (self._fila1, self._fila2):
            while lay.count():
                lay.takeAt(0)
        if dos_filas:
            self._fila1.addWidget(self._caja_ins)
            self._fila1.addStretch(1)
            self._fila2.addWidget(self._caja_herr)
            self._fila2.addStretch(1)
        else:
            self._fila1.addWidget(self._caja_ins)
            self._fila1.addStretch(1)
            self._fila1.addWidget(self._caja_herr)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        w = max(self._caja_ins.sizeHint().width(), self._caja_herr.sizeHint().width()) + 20
        return QSize(min(w, 380), self.height() or 39)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._ancho_necesario_una_fila(), self.height() or 39)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.ajustar_alto()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        self.ajustar_alto()

    def ajustar_alto(self, forzar: bool = False) -> None:
        ancho = self.width()
        dos_filas = ancho > 0 and ancho < self._ancho_necesario_una_fila()
        self._aplicar_filas(dos_filas)
        alto = 70 if dos_filas else 39
        if forzar or self.height() != alto:
            cambio = alto != self.height()
            self.setFixedHeight(alto)
            if cambio:
                self.alto_cambiado.emit()
