"""La banda de categorías del programador por bloques (2.0, E8): Operadores, Temporizadores, Comparaciones y Constantes (en el
programador de un valor: Operadores y Constantes), con un botón por bloque. Cada botón admite **clic** (el bloque se pone en el hueco o el
bloque elegido o, sin elección, en el primer hueco libre) y **arrastre** (se suelta en el hueco que se quiera, como cualquier bloque).
La banda no sabe de la fórmula: crea el bloque y avisa (`insertar`); el programador decide dónde va.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from PySide6.QtCore import QEvent, QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QFont, QFontMetricsF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from . import estilo
from .arrastre_popup import ejecutar_arrastre
from .bloques import (_ARRASTRE, CATEGORIAS_BANDA, CATEGORIAS_BANDA_VALOR, MIME, FlowLayout, Motor, nuevo)

# (clave de la categoría) -> [(rótulo, qué bloque crea, ayuda)]; el bloque lo da `BandaBloques.nodo`
BOTONES = {
    "operador": [
        ("NOT", "no", "Negación (barra superior). Con una ficha elegida se aplica a ella; sin elección, deja un NOT esperando su variable. "
                      "El orden en que se pulsan NOT y los flancos es el orden en que se aplican. También se puede arrastrar."),
        ("↑", "sube", "Flanco de subida: se cumple solo en el instante en que la señal pasa de 0 a 1. También se puede arrastrar."),
        ("↓", "baja", "Flanco de bajada: se cumple solo en el instante en que la señal pasa de 1 a 0. También se puede arrastrar."),
        ("( … )", "par", "Paréntesis: agrupa lo que lleve dentro; con una ficha elegida, la envuelve. También se puede arrastrar."),
        ("Y", "y", "Y: se cumple cuando se cumplen todos sus operandos (el «+» añade otro). También se puede arrastrar."),
        ("O", "o", "O: se cumple cuando se cumple alguno de sus operandos (el «+» añade otro). También se puede arrastrar.")],
    "tiempo": [
        ("t/X", "retardo_activar", "Retardo al activarse (t/X): la señal X se da por verdadera t después de activarse. Se escribe t/X. "
                                   "También se puede arrastrar."),
        ("X/t", "retardo_desactivar", "Retardo al desactivarse (X/t): la señal X sigue verdadera t después de desactivarse. Se escribe X/t; "
                                      "con los dos tiempos, t1/X/t2. También se puede arrastrar.")],
    "comparacion": [
        ("= ≠ < ≥", "cmp", "Compara una variable numérica con un valor: = ≠ < ≤ > ≥. Se escribe entre corchetes: [CT ≥ 10]. "
                           "También se puede arrastrar.")],
    "constante": [
        ("1", "uno", "Siempre verdadera. Sin hueco elegido, es toda la fórmula; sobre un hueco, se combina con lo demás. "
                     "También se puede arrastrar."),
        ("0", "cero", "Siempre falsa. Sin hueco elegido, es toda la fórmula; sobre un hueco, se combina con lo demás. "
                      "También se puede arrastrar.")],
    "aritm": [
        ("+", "mas", "Suma. También se puede arrastrar."), ("−", "menos", "Resta. También se puede arrastrar."),
        ("×", "por", "Producto. También se puede arrastrar."), ("÷", "entre", "División. También se puede arrastrar."),
        ("( … )", "par", "Paréntesis: agrupa lo que lleve dentro; con una ficha elegida, la envuelve. También se puede arrastrar.")],
    "numero": [
        ("Número", "num", "Un número que se escribe con el teclado. También se puede arrastrar.")],
}
NOMBRES_COMPLETOS = {"operador": "Operadores", "aritm": "Operadores", "tiempo": "Temporizadores", "comparacion": "Comparaciones",
                     "constante": "Constantes", "numero": "Constantes"}  # los rótulos van abreviados; esto sale en su ayuda emergente
SIMBOLOS = frozenset({"no", "sube", "baja", "retardo_activar", "retardo_desactivar", "cmp", "uno", "cero", "mas", "menos", "por", "entre",
                      "num"})  # los que se rotulan con letra de cifras


class BotonCompacto(QPushButton):
    """Un botón de la banda o de sus herramientas: de tamaño fijo (la banda lo pone según su texto), que es también lo que pide."""

    tam: QSize | None = None

    def poner_tam(self, ancho: int, alto: int) -> None:
        """Su tamaño: fijo, y también por la hoja de estilo (la de los botones de la aplicación le pone un alto mínimo y, sin esto, a otra
        escala lo agrandaría)."""
        self.tam = QSize(ancho, alto)
        self.setFixedSize(self.tam)
        # la letra y el relleno con que se midió, también fuera de la banda (los botones del pie y de la franja del título)
        self.setStyleSheet(f"QPushButton {{ font-size: {estilo.T_PEQUENA}px; font-weight: 600; padding: 0 5px; }}")

    def event(self, ev: Any) -> bool:
        """La hoja de estilo, al pulirse el botón, le cambia el alto mínimo y deshace el tamaño fijo: se le vuelve a poner."""
        r = super().event(ev)
        if self.tam is not None and ev.type() in (QEvent.Type.Polish, QEvent.Type.StyleChange, QEvent.Type.ParentChange)                 and (self.minimumSize() != self.tam or self.maximumSize() != self.tam):
            self.setFixedSize(self.tam)
        return r

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.tam) if self.tam is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


class BotonBloque(BotonCompacto):
    """Un botón de la banda: clic o arrastre. `clave` dice qué bloque crea."""
    arrastrado = Signal()

    def __init__(self, banda: "BandaBloques", rotulo: str, clave: str, ayuda: str) -> None:
        super().__init__(rotulo)
        self.banda, self.clave = banda, clave
        self.setToolTip(ayuda)
        self.setAccessibleName(rotulo)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._origen: QPoint | None = None
        f = QFont(self.font())
        if clave in SIMBOLOS or clave == "par":
            f = QFont(estilo.FUENTE_MONO)
            f.setBold(True)
        if clave == "no":
            f.setOverline(True)
        f.setPixelSize(estilo.T_PEQUENA)
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


class _Flujo(FlowLayout):
    """El flujo de las categorías, con los márgenes de la banda."""

    def _colocar(self, r: QRect, solo_medir: bool) -> int:
        m = self.contentsMargins()
        return super()._colocar(r.adjusted(m.left(), m.top(), -m.right(), -m.bottom()), solo_medir) + m.top() + m.bottom()


class BandaBloques(QFrame):
    """La banda: un rótulo y sus botones por categoría, en una fila si caben y en varias si no (una categoría no se parte)."""
    insertar = Signal(object)  # se pulsó un botón: el nodo que crea
    alto_cambiado = Signal()  # la banda cambió de alto (al pasar de una fila a dos al cambiar el ancho)

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]], grupo: str, valor: bool = False) -> None:
        super().__init__()
        self.fuente, self.grupo, self.valor = fuente, grupo, valor
        self.setObjectName("bandaBloques")
        self.categorias: dict[str, QLabel] = {}  # el rótulo de cada categoría
        self.botones: dict[str, list[BotonBloque]] = {}
        self._herramientas: list[QPushButton] = []
        self._flujo = _Flujo(self, 6)
        self._flujo.setContentsMargins(estilo.E1 + 2, 4, estilo.E1 + 2, 4)
        for i, (clave, titulo) in enumerate(CATEGORIAS_BANDA_VALOR if valor else CATEGORIAS_BANDA):
            # una categoría es un solo elemento del flujo: su rótulo y sus botones, que saltan de fila juntos
            grupo_w = QFrame()
            grupo_w.setObjectName("categoriaBandaSep" if i else "categoriaBanda")
            lay = QHBoxLayout(grupo_w)
            lay.setContentsMargins(estilo.E1 + 2 if i else 0, 0, 0, 0)
            lay.setSpacing(3)
            rotulo = QLabel(titulo)
            rotulo.setObjectName("rotuloBanda")
            rotulo.setToolTip(NOMBRES_COMPLETOS[clave])
            self.categorias[clave] = rotulo
            lay.addWidget(rotulo)
            self.botones[clave] = []
            for texto, tipo, ayuda in BOTONES[clave]:
                b = BotonBloque(self, texto, tipo, ayuda)
                b.clicked.connect(lambda _=False, t=tipo: self.insertar.emit(self.nodo(t)))
                lay.addWidget(b)
                self.botones[clave].append(b)
            self._flujo.addWidget(grupo_w)
        self.escalar()

    def anadir_herramientas(self, botones: list[QPushButton], flujo: bool = True) -> None:
        """Las herramientas de la fórmula (Copiar fórmula, Pegar, Limpiar) van al final de la banda, sin rótulo y con el fondo blanco de
        los controles (los botones de bloques, el de las superficies hundidas)."""
        for b in botones:
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            b.setProperty("herramienta", True)
            self._herramientas.append(b)
            if flujo:
                self._flujo.addWidget(b)
        self.escalar()

    # -- qué crea cada botón
    def nodo(self, clave: str) -> dict[str, Any]:
        """El bloque nuevo de un botón. La comparación trae la primera variable numérica; los temporizadores, 3 s (como siempre)."""
        if clave == "retardo_activar":
            return nuevo("temp", t1="3s", t2="")
        if clave == "retardo_desactivar":
            return nuevo("temp", t1="", t2="3s")
        if clave == "uno":
            return nuevo("const", v=1)
        if clave == "cero":
            return nuevo("const", v=0)
        if clave in ("mas", "menos", "por", "entre"):
            return nuevo("ar", op={"mas": "+", "menos": "-", "por": "*", "entre": "/"}[clave])
        if clave == "cmp":
            numericas = [n for n, (_, t) in self.fuente()[0].items() if t != "bool"]
            return nuevo("cmp", n=numericas[0] if numericas else None)
        return nuevo(clave)

    def mime(self, nodo: dict[str, Any]) -> QMimeData:
        mime = QMimeData()
        mime.setData(MIME, json.dumps({"nodo": nodo, "grupo": self.grupo, "origen": None}).encode())
        return mime

    # -- aspecto y medidas
    def _hoja(self) -> str:
        return (f"#bandaBloques {{ background: {estilo.SUPERFICIE}; border: 1px solid {estilo.BORDE}; border-radius: {estilo.R_M}px; }}"
                f"#categoriaBandaSep {{ border-left: 1px solid {estilo.BORDE}; }}"
                f"#rotuloBanda {{ color: {estilo.TINTA_3}; font-size: {estilo.T_PEQUENA}px; font-weight: 600; background: transparent; "
                f"border: none; padding-right: 0; }}"
                f"QPushButton {{ min-height: {estilo.ALTO_BARRA_COMPACTA}px; max-height: {estilo.ALTO_BARRA_COMPACTA}px; padding: 0 5px; "
                f"background: {estilo.SUPERFICIE_2}; border: 1px solid {estilo.BORDE_CONTROL}; border-radius: {estilo.R_S}px; "
                f"color: {estilo.TINTA}; font-size: {estilo.T_PEQUENA}px; font-weight: 600; }}"
                f"QPushButton[herramienta=\"true\"] {{ background: {estilo.SUPERFICIE}; color: {estilo.TINTA_2}; }}"
                f"QPushButton:disabled {{ color: {estilo.DESHABILITADO}; border-color: {estilo.BORDE}; background: {estilo.SUPERFICIE}; }}"
                f"QPushButton:hover:enabled {{ border-color: {estilo.ACENTO}; background: {estilo.ACENTO_SUAVE}; color: {estilo.ACENTO_OSCURO}; }}"
                f"QPushButton:pressed {{ background: {estilo.ACENTO}; color: #FFFFFF; }}"
                f"QPushButton[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; padding: 0 {estilo.E2 - 1}px; }}")

    def escalar(self) -> None:
        """Cambió la escala de letra y de controles: la banda se mide otra vez."""
        self.setStyleSheet(self._hoja())
        alto = estilo.ALTO_BARRA_COMPACTA
        for b in [b for botones in self.botones.values() for b in botones] + self._herramientas:
            f = QFont(b.font())
            f.setPixelSize(estilo.T_PEQUENA)
            f.setWeight(QFont.Weight.DemiBold)
            b.setFont(f)
            # de ancho justo (la hoja global de botones les daría 46 px a todos) y de un alto de token
            b.poner_tam(max(round(QFontMetricsF(f).horizontalAdvance(b.text())) + 2 * 5 + 1, alto), alto)
        for r in self.categorias.values():
            f = QFont(r.font())
            f.setPixelSize(estilo.T_PEQUENA)
            r.setFont(f)
        self._flujo.invalidate()
        self.ajustar_alto(True)

    def ajustar_alto(self, forzar: bool = False) -> None:
        """La banda mide lo que sus filas: una si caben todas las categorías y, si no, las que hagan falta."""
        ancho = self.width() - 2 if self.width() > 80 else 10 ** 5
        alto = self._flujo.heightForWidth(max(ancho, 60)) + 2
        if forzar or alto != self.height() or alto != self.minimumHeight():
            cambio = alto != self.height()
            self.setFixedHeight(alto)
            if cambio:
                self.alto_cambiado.emit()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.ajustar_alto()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        self.ajustar_alto()
