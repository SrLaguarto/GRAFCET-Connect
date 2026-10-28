"""Programador por bloques de receptividades y condiciones (P-IMP-38).

La expresión se ve como una fila de bloques: cada variable o etapa es un bloque de su color (entradas, salidas,
internas, etapas X, comparaciones, temporizadores), la negación es una barra encima del bloque o del grupo, los
flancos van delante (↑ ↓), · es Y y + es O, y los paréntesis cambian de color con el nivel. Los bloques se sacan de
los cajones (Entradas, Salidas, Internas, Etapas, Constantes) y se modifican con los botones o con el teclado.

Los bloques solo escriben el texto en la notación del usuario (↑a, X1, 3s/X1), que es lo que se guarda y lo que el
núcleo analiza como siempre (grafcet/notation.py y grafcet/expressions.py no cambian): una expresión se trocea en
bloques y los bloques se vuelven a juntar en el mismo texto.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLayout,
                               QLineEdit, QMenu, QSizePolicy, QToolButton, QVBoxLayout, QWidget, QWidgetItem)

from grafcet.notation import normalizar_espacios

# Colores de los bloques (relleno, borde y texto) por categoría, y de los paréntesis por nivel
COLORES = {"entrada": ("#dbeafe", "#1d4ed8"), "salida": ("#dcfce7", "#15803d"), "interna": ("#fef3c7", "#b45309"),
           "etapa": ("#ede9fe", "#6d28d9"), "comparacion": ("#ffedd5", "#c2410c"), "tiempo": ("#ccfbf1", "#0f766e"),
           "constante": ("#f1f5f9", "#475569"), "otro": ("#fee2e2", "#b91c1c")}
CATEGORIAS = {"entrada": "entrada", "salida": "salida", "interna": "variable interna", "etapa": "etapa activa (X)",
              "comparacion": "comparación", "tiempo": "temporización", "constante": "constante",
              "otro": "nombre que no existe"}
PARENTESIS = ["#2563eb", "#d97706", "#16a34a", "#c026d3", "#dc2626", "#0891b2"]
_DUR = r"\d+(?:[.,]\d+)?\s*(?:us|µs|μs|ms|s)\b"
_TIEMPO = re.compile(rf"(?:^|/)\s*{_DUR}\s*/|/\s*{_DUR}\s*$")
_SIMPLE = re.compile(r"[^\W\d]\w*(?:\.\w+)?")
_CMP = re.compile(r"^(.+?)\s*(>=|<=|!=|=|<|>)\s*(.+)$")


# -- bloques sin interfaz ---------------------------------------------------------------------------
def categoria(texto: str, roles: dict[str, str], etapas: set[str]) -> str:
    """De qué es un bloque: entrada, salida o interna (por el papel de la variable), etapa (X1), comparación,
    temporización, constante, u «otro» si el nombre no existe."""
    if _TIEMPO.search(texto):
        return "tiempo"
    if re.search(r"[<>=≠≤≥]", texto):
        return "comparacion"
    if texto in ("1", "0", "true", "false"):
        return "constante"
    if texto in etapas or texto.startswith("active("):
        return "etapa"
    return {"input": "entrada", "output": "salida", "internal": "interna"}.get(roles.get(texto, ""), "otro")


def trocear(texto: str, clase: Callable[[str], str] = lambda t: "otro") -> list[dict[str, Any]]:
    """Texto en la notación del usuario -> bloques: operandos (con su negación y su flanco), Y/O y paréntesis (un
    paréntesis que abre lleva la negación y el flanco de su grupo)."""
    t, out, i, neg, flanco = normalizar_espacios(texto), [], 0, False, ""
    while i < len(t):
        c = t[i]
        m = re.compile(r"(AND|OR)\b").match(t, i)
        if c == " ":
            i += 1
        elif m:
            out.append({"k": "op", "t": m.group(1)})
            i = m.end()
        elif re.compile(r"NOT\b").match(t, i):
            neg, i = not neg, i + 3
        elif c in "↑↓":
            flanco, i = c, i + 1
        elif c == "(":
            out.append({"k": "(", "neg": neg, "flanco": flanco})
            neg, flanco, i = False, "", i + 1
        elif c == ")":
            out.append({"k": ")"})
            i += 1
        else:  # un operando: hasta el AND, el OR o el paréntesis que cierra de su mismo nivel
            j, nivel = i, 0
            while j < len(t):
                if t[j] == "(":
                    nivel += 1
                elif t[j] == ")":
                    if nivel == 0:
                        break
                    nivel -= 1
                elif nivel == 0 and re.compile(r" (AND|OR)\b").match(t, j):
                    break
                j += 1
            cuerpo = t[i:j].strip()
            if neg and _TIEMPO.search(cuerpo) and not re.match(_DUR, cuerpo):
                cuerpo, neg = "NOT " + cuerpo, False  # «NOT marcha/2s» es el retardo de NOT marcha: va dentro
            out.append({"k": "atomo", "t": cuerpo, "cat": clase(cuerpo), "neg": neg, "flanco": flanco})
            neg, flanco, i = False, "", j
    return out


def juntar(bloques: list[dict[str, Any]]) -> str:
    """Bloques -> texto en la notación del usuario, con los espacios normalizados."""
    partes = []
    for b in bloques:
        if b["k"] == "op":
            partes.append(b["t"])
        elif b["k"] == ")":
            partes.append(")")
        elif b["k"] == "(":
            partes.append(("NOT " if b["neg"] else "") + b["flanco"] + "(")
        else:
            cuerpo = b["t"]
            if (b["neg"] or b["flanco"]) and not _SIMPLE.fullmatch(cuerpo):
                cuerpo = f"({cuerpo})"
            partes.append(("NOT " if b["neg"] else "") + b["flanco"] + cuerpo)
    return normalizar_espacios(" ".join(partes))


def _abre(b: dict[str, Any] | None) -> bool:
    return b is not None and b["k"] in ("atomo", "(")


def _cierra(b: dict[str, Any] | None) -> bool:
    return b is not None and b["k"] in ("atomo", ")")


class Expresion:
    """Los bloques de una expresión, con el punto de inserción (cursor, entre bloques) y la selección [a, b)."""

    def __init__(self, bloques: list[dict[str, Any]] | None = None) -> None:
        self.b: list[dict[str, Any]] = bloques or []
        self.cursor = len(self.b)
        self.sel: tuple[int, int] | None = None

    def texto(self) -> str:
        return juntar(self.b)

    def pareja(self, i: int) -> int:
        """El paréntesis que hace pareja con el de la posición i (o i, si no tiene)."""
        paso = 1 if self.b[i]["k"] == "(" else -1
        nivel, j = 0, i
        while 0 <= j < len(self.b):
            nivel += {"(": 1, ")": -1}.get(self.b[j]["k"], 0) * paso
            if nivel == 0:
                return j
            j += paso
        return i

    def niveles(self) -> list[int]:
        """Nivel de anidamiento de cada bloque (los paréntesis, el de su pareja)."""
        out, n = [], 0
        for b in self.b:
            if b["k"] == ")":
                n -= 1
            out.append(n)
            if b["k"] == "(":
                n += 1
        return out

    def _objetivo(self) -> tuple[int, int] | None:
        if self.sel:
            return self.sel
        return (self.cursor - 1, self.cursor) if self.cursor > 0 else None

    def _equilibrado(self, a: int, b: int) -> bool:
        n = 0
        for x in self.b[a:b]:
            n += {"(": 1, ")": -1}.get(x["k"], 0)
            if n < 0:
                return False
        return n == 0

    def insertar(self, nuevos: list[dict[str, Any]]) -> None:
        """Inserta en el cursor (tras la selección, si la hay). Entre dos operandos pone · (Y); un · o + junto a otro lo
        sustituye."""
        pos = self.sel[1] if self.sel else self.cursor
        antes, despues = (self.b[pos - 1] if pos > 0 else None), (self.b[pos] if pos < len(self.b) else None)
        nuevos = [dict(x) for x in nuevos]
        if len(nuevos) == 1 and nuevos[0]["k"] == "op":
            if antes is not None and antes["k"] == "op":
                antes["t"] = nuevos[0]["t"]
            elif despues is not None and despues["k"] == "op":
                despues["t"] = nuevos[0]["t"]
            elif _cierra(antes):
                self.b.insert(pos, nuevos[0])
                pos += 1
            self.cursor, self.sel = pos, None
            return
        if _abre(nuevos[0]) and _cierra(antes):
            nuevos.insert(0, {"k": "op", "t": "AND"})
        if _cierra(nuevos[-1]) and _abre(despues):
            nuevos.append({"k": "op", "t": "AND"})
        self.b[pos:pos] = nuevos
        self.cursor, self.sel = pos + len(nuevos), None

    def reemplazar(self, nuevos: list[dict[str, Any]]) -> None:
        """Sustituye la selección (o el bloque antes del cursor) por otros bloques."""
        obj = self._objetivo()
        if obj and self._equilibrado(*obj):
            del self.b[obj[0]:obj[1]]
            self.cursor, self.sel = obj[0], None
        self.insertar(nuevos)

    def quitar(self) -> None:
        """Quita la selección o el bloque antes del cursor; un paréntesis se lleva su pareja."""
        obj = self._objetivo()
        if obj is None:
            return
        a, b = obj
        fuera = set(range(a, b))
        for i in range(a, b):
            if self.b[i]["k"] in ("(", ")"):
                fuera.add(self.pareja(i))
        self.b = [x for i, x in enumerate(self.b) if i not in fuera]
        self.cursor, self.sel = a - len([i for i in fuera if i < a]), None
        self.limpiar()

    def limpiar(self) -> None:
        """Sin · ni + sueltos (al principio, al final, junto a un paréntesis o dos seguidos) ni paréntesis vacíos."""
        cambiado = True
        while cambiado:
            cambiado = False
            for i, x in enumerate(self.b):
                antes = self.b[i - 1] if i > 0 else None
                despues = self.b[i + 1] if i + 1 < len(self.b) else None
                if (x["k"] == "op" and (antes is None or despues is None or antes["k"] in ("(", "op")
                                        or despues["k"] == ")")) or \
                        (x["k"] == "(" and despues is not None and despues["k"] == ")"):
                    n = 2 if x["k"] == "(" else 1
                    del self.b[i:i + n]
                    if self.cursor > i:
                        self.cursor = max(i, self.cursor - n)
                    cambiado = True
                    break
                if _cierra(x) and _abre(despues):  # dos operandos seguidos: entre ellos, Y
                    self.b.insert(i + 1, {"k": "op", "t": "AND"})
                    if self.cursor > i:
                        self.cursor += 1
                    cambiado = True
                    break
        self.cursor = min(self.cursor, len(self.b))

    def envolver(self, neg: bool = False, flanco: str = "") -> bool:
        """Entre paréntesis la selección (o el bloque antes del cursor); sin nada, un par vacío con el cursor dentro."""
        obj = self._objetivo()
        if obj is None:
            self.insertar([{"k": "(", "neg": neg, "flanco": flanco}])
            self.b.insert(self.cursor, {"k": ")"})
            return True
        a, b = obj
        if not self._equilibrado(a, b) or all(x["k"] == "op" for x in self.b[a:b]):
            return False
        self.b.insert(b, {"k": ")"})
        self.b.insert(a, {"k": "(", "neg": neg, "flanco": flanco})
        self.cursor, self.sel = b + 2, (a, b + 2)
        return True

    def _modificar(self, campo: str, valor: Any) -> bool:
        """NOT o flanco sobre la selección: un operando o un grupo lo llevan; varios bloques, entre paréntesis."""
        obj = self._objetivo()
        if obj is None:
            return False
        a, b = obj
        if all(x["k"] == "op" for x in self.b[a:b]):
            return False
        if b - a == 1 and self.b[a]["k"] == ")":
            a = self.pareja(a)
            b = a + 1
        if b - a == 1 and self.b[a]["k"] in ("atomo", "("):
            x = self.b[a]
            x[campo] = (not x[campo]) if campo == "neg" else ("" if x[campo] == valor else valor)
            return True
        if self.b[a]["k"] == "(" and self.pareja(a) == b - 1:
            x = self.b[a]
            x[campo] = (not x[campo]) if campo == "neg" else ("" if x[campo] == valor else valor)
            return True
        return self.envolver(**{campo: True if campo == "neg" else valor})

    def negar(self) -> bool:
        return self._modificar("neg", True)

    def flanco(self, f: str) -> bool:
        return self._modificar("flanco", f)

    def alternar(self, i: int) -> None:
        """Un · pasa a + y al revés."""
        if self.b[i]["k"] == "op":
            self.b[i]["t"] = "OR" if self.b[i]["t"] == "AND" else "AND"


# -- dibujo e interacción -------------------------------------------------------------------------
_ALTO, _SEP, _BARRA = 26, 4, 4  # alto de un bloque, separación y altura de cada barra de negación


class LienzoBloques(QWidget):
    """Los bloques dibujados en filas que se parten al ancho disponible. Clic: selecciona un bloque (Mayús: amplía);
    en un · o + lo cambia; en un hueco, pone ahí el cursor. Teclado: ← →, Supr y Retroceso; doble clic en una
    comparación o temporización la edita."""

    cambiado = Signal()
    editar = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.e = Expresion()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(80)
        self.font_ = QFont()
        self.font_.setPixelSize(13)
        self._cajas: list[QRectF] = []
        self._huecos: list[tuple[float, float, float]] = []  # x, y de arriba y alto del hueco antes de cada bloque

    # -- geometría
    def _etiqueta(self, b: dict[str, Any]) -> str:
        if b["k"] == "op":
            return "·" if b["t"] == "AND" else "+"
        if b["k"] == "(":
            return b["flanco"] + "("
        if b["k"] == ")":
            return ")"
        t = b["t"].replace(">=", "≥").replace("<=", "≤").replace("!=", "≠")
        return b["flanco"] + t

    def _alturas(self) -> list[int]:
        """Cuántas barras de negación hay encima de cada bloque (la de un grupo, por encima de las de dentro)."""
        alto = [0] * len(self.e.b)
        for i, b in enumerate(self.e.b):
            if b["k"] == "atomo" and b["neg"]:
                alto[i] = 1
        for i in range(len(self.e.b) - 1, -1, -1):  # grupos de dentro afuera
            b = self.e.b[i]
            if b["k"] == "(" and b["neg"]:
                j = self.e.pareja(i)
                h = 1 + max(alto[i + 1:j] or [0])
                for k in range(i, j + 1):
                    alto[k] = max(alto[k], h)
        return alto

    def _maqueta(self, ancho: float) -> tuple[list[QRectF], list[tuple[float, float, float]], float]:
        fm = QFontMetricsF(self.font_)
        margen = _BARRA * (max(self._alturas() or [0]) + 1)
        x, y, cajas, huecos = 4.0, 4.0 + margen, [], []
        for b in self.e.b:
            w = fm.horizontalAdvance(self._etiqueta(b)) + (18 if b["k"] == "atomo" else 10)
            if b["k"] == "op":
                w = 22
            if x + w > ancho - 4 and x > 4:
                x, y = 4.0, y + _ALTO + _SEP + margen
            huecos.append((x - _SEP / 2, y, _ALTO))
            cajas.append(QRectF(x, y, w, _ALTO))
            x += w + _SEP
        huecos.append((x - _SEP / 2, y, _ALTO))
        return cajas, huecos, y + _ALTO + 4

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return max(44, int(self._maqueta(w)[2]))

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(240, self.heightForWidth(max(self.width(), 240)))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(80, 44)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.setMinimumHeight(self.heightForWidth(self.width()))

    def actualizar(self) -> None:
        self.setMinimumHeight(self.heightForWidth(max(self.width(), 80)))
        self.updateGeometry()
        self.update()

    # -- dibujo
    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        p.setPen(QPen(QColor("#c3c9d6"), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        cajas, huecos, _ = self._maqueta(self.width())
        self._cajas, self._huecos = cajas, huecos
        p.setFont(self.font_)
        if not self.e.b:
            p.setPen(QColor("#6b7385"))
            p.drawText(QRectF(self.rect()).adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                       "Vacía: saque bloques de los cajones (Entradas, Etapas…)")
        niveles, alturas = self.e.niveles(), self._alturas()
        sel = range(*self.e.sel) if self.e.sel else range(0)
        for i, (b, r) in enumerate(zip(self.e.b, cajas)):
            if b["k"] == "atomo":
                fondo, borde = COLORES.get(b["cat"], COLORES["otro"])
                p.setPen(QPen(QColor(borde), 2.4 if i in sel else 1.2))
                p.setBrush(QColor(fondo))
                p.drawRoundedRect(r, 6, 6)
                p.setPen(QColor(borde).darker(130))
                self._texto_atomo(p, b, r)
            elif b["k"] == "op":
                p.setPen(QPen(QColor("#1f6feb" if i in sel else "#9aa3b5"), 1.6 if i in sel else 1))
                p.setBrush(QColor("#f6f7fb"))
                p.drawEllipse(r.center(), 10, 10)
                f = QFont(self.font_)
                f.setBold(True)
                f.setPixelSize(16)
                p.setFont(f)
                p.setPen(QColor("#1d2330"))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._etiqueta(b))
                p.setFont(self.font_)
            else:
                color = QColor(PARENTESIS[niveles[i] % len(PARENTESIS)])
                if i in sel:
                    p.setPen(QPen(QColor("#1f6feb"), 1.4))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(r, 4, 4)
                f = QFont(self.font_)
                f.setBold(True)
                f.setPixelSize(19)
                p.setFont(f)
                p.setPen(color)
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._etiqueta(b))
                p.setFont(self.font_)
        # Barras de negación: encima del bloque, o encima de todo el grupo (fila a fila), por niveles
        p.setPen(QPen(QColor("#1d2330"), 2))
        for i, b in enumerate(self.e.b):
            if b["k"] == "atomo" and b["neg"]:
                r = cajas[i]
                y = r.top() - 3
                p.drawLine(QPointF(r.left() + 3, y), QPointF(r.right() - 3, y))
            elif b["k"] == "(" and b["neg"]:
                j = self.e.pareja(i)
                y_off = 3 + _BARRA * (alturas[i] - 1)
                tramo = [cajas[i]]
                for k in range(i + 1, j + 1):
                    if cajas[k].top() != tramo[-1].top():
                        self._barra(p, tramo, y_off)
                        tramo = []
                    tramo.append(cajas[k])
                self._barra(p, tramo, y_off)
        if self.hasFocus() and not self.e.sel:  # el cursor, entre bloques
            x, y, h = huecos[min(self.e.cursor, len(huecos) - 1)]
            p.setPen(QPen(QColor("#1f6feb"), 2))
            p.drawLine(QPointF(x, y + 2), QPointF(x, y + h - 2))
        p.end()

    @staticmethod
    def _barra(p: QPainter, tramo: list[QRectF], y_off: float) -> None:
        if tramo:
            y = tramo[0].top() - y_off
            p.drawLine(QPointF(tramo[0].left() + 2, y), QPointF(tramo[-1].right() - 2, y))

    def _texto_atomo(self, p: QPainter, b: dict[str, Any], r: QRectF) -> None:
        """El texto del bloque; una etapa X1 lleva el número en subíndice, como en la norma."""
        m = re.fullmatch(r"X(\w+)", b["t"]) if b["cat"] == "etapa" else None
        if not m:
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._etiqueta(b))
            return
        fm = QFontMetricsF(self.font_)
        pequeña = QFont(self.font_)
        pequeña.setPixelSize(10)
        fs = QFontMetricsF(pequeña)
        cabeza = b["flanco"] + "X"
        w = fm.horizontalAdvance(cabeza) + fs.horizontalAdvance(m.group(1))
        x = r.center().x() - w / 2
        base = r.center().y() + fm.ascent() / 2 - 1
        p.drawText(QPointF(x, base), cabeza)
        p.setFont(pequeña)
        p.drawText(QPointF(x + fm.horizontalAdvance(cabeza), base + 3), m.group(1))
        p.setFont(self.font_)

    # -- ratón y teclado
    def _bloque_en(self, pos: QPointF) -> int | None:
        return next((i for i, r in enumerate(self._cajas) if r.adjusted(-1, -2, 1, 2).contains(pos)), None)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self.setFocus()
        self._maqueta_si_falta()
        pos = event.position()
        i = self._bloque_en(pos)
        if i is None:
            fila = [(abs(x - pos.x()), k) for k, (x, y, h) in enumerate(self._huecos) if y - 6 <= pos.y() <= y + h + 6]
            self.e.cursor = min(fila)[1] if fila else len(self.e.b)
            self.e.sel = None
        elif self.e.b[i]["k"] == "op" and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.e.alternar(i)
            self.e.sel, self.e.cursor = None, i + 1
            self.cambiado.emit()
        elif event.modifiers() & Qt.KeyboardModifier.ShiftModifier and self.e.sel:
            a, b = self.e.sel
            self.e.sel = (min(a, i), max(b, i + 1))
            self.e.cursor = self.e.sel[1]
        else:
            self.e.sel, self.e.cursor = (i, i + 1), i + 1
        self.update()

    def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802
        i = self._bloque_en(event.position())
        if i is not None and self.e.b[i]["k"] == "atomo":
            self.editar.emit(i)

    def _maqueta_si_falta(self) -> None:
        if len(self._cajas) != len(self.e.b):
            self._cajas, self._huecos, _ = self._maqueta(self.width())

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        k = event.key()
        if k in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if k == Qt.Key.Key_Delete and not self.e.sel and self.e.cursor < len(self.e.b):
                self.e.sel = (self.e.cursor, self.e.cursor + 1)
            self.e.quitar()
            self.cambiado.emit()
        elif k == Qt.Key.Key_Left:
            self.e.cursor, self.e.sel = max(0, (self.e.sel[0] if self.e.sel else self.e.cursor) - (0 if self.e.sel else 1)), None
        elif k == Qt.Key.Key_Right:
            self.e.cursor, self.e.sel = min(len(self.e.b), (self.e.sel[1] if self.e.sel else self.e.cursor + 1)), None
        elif k in (Qt.Key.Key_Home, Qt.Key.Key_End):
            self.e.cursor, self.e.sel = (0 if k == Qt.Key.Key_Home else len(self.e.b)), None
        else:
            super().keyPressEvent(event)
            return
        self.actualizar()


# -- diálogos de comparación y temporización (también los usa el panel de propiedades) ----------------------
class _Dialogo(QDialog):
    def __init__(self, parent: QWidget | None, titulo: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.form = QFormLayout(self)

    def cerrar(self) -> None:
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        self.form.addRow(b)


def pedir_comparacion(parent: QWidget | None, numericas: list[str], previo: str = "") -> str | None:
    """Variable numérica, comparación y valor: «CT >= 3». Con `previo`, se edita esa comparación."""
    d = _Dialogo(parent, "Comparar")
    var = QComboBox()  # solo variables numéricas (enteros, analógicas, decimales)
    var.setEditable(True)
    var.addItems(numericas)
    op = QComboBox()
    for texto, sim in (("=", "="), ("≠", "!="), ("<", "<"), ("≤", "<="), (">", ">"), ("≥", ">=")):
        op.addItem(texto, sim)
    valor = QLineEdit("0")
    m = _CMP.match(previo)
    if m:
        var.setCurrentText(m.group(1).strip())
        op.setCurrentIndex(max(0, op.findData(m.group(2))))
        valor.setText(m.group(3).strip())
    elif previo:
        var.setCurrentText(previo)
    d.form.addRow("Variable", var)
    d.form.addRow("Comparación", op)
    d.form.addRow("Valor", valor)
    d.cerrar()
    if d.exec() == QDialog.DialogCode.Accepted and var.currentText().strip():
        return f"{var.currentText().strip()} {op.currentData()} {valor.text().strip() or '0'}"
    return None


def pedir_temporizacion(parent: QWidget | None, condiciones: list[str], previo: str = "") -> str | None:
    """t1/condición/t2 como en la norma («3s/X1», «X1/2s», «3s/NOT marcha/2s»); los tiempos de 0 s no se escriben."""
    d = _Dialogo(parent, "Temporizar")
    t1, cond, t2 = QLineEdit("3 s"), QComboBox(), QLineEdit("0 s")
    cond.setEditable(True)  # etapas (X), entradas y salidas del grafcet; también se puede escribir
    cond.addItems(condiciones)
    negar = QCheckBox("Negar la condición (NOT)")
    partes = [x.strip() for x in previo.split("/")] if _TIEMPO.search(previo) else []
    if partes:
        if re.fullmatch(_DUR, partes[0]):
            t1.setText(partes.pop(0))
        else:
            t1.setText("0 s")
        if partes and len(partes) > 1 and re.fullmatch(_DUR, partes[-1]):
            t2.setText(partes.pop())
        base = "/".join(partes)
        if base.startswith("NOT "):
            negar.setChecked(True)
            base = base[4:]
        cond.setCurrentText(base)
    elif previo:
        cond.setCurrentText(previo)
    d.form.addRow("Retardo a la conexión (t1)", t1)
    d.form.addRow("Condición", cond)
    d.form.addRow("", negar)
    d.form.addRow("Retardo a la desconexión (t2)", t2)
    d.cerrar()
    if d.exec() != QDialog.DialogCode.Accepted or not cond.currentText().strip():
        return None
    c = cond.currentText().strip()
    c = f"NOT {c}" if negar.isChecked() and not c.startswith("NOT ") else c
    cero = lambda x: x in ("", "0", "0 s", "0s")
    return "/".join(([] if cero(t1.text().strip()) else [re.sub(r"\s+", "", t1.text().strip())]) + [c]
                    + ([] if cero(t2.text().strip()) else [re.sub(r"\s+", "", t2.text().strip())]))


# -- el programador: cajones, botones y lienzo -------------------------------------------------------
class FlowLayout(QLayout):
    """Los controles uno tras otro, y a la línea siguiente cuando no caben: el panel se puede estrechar."""

    def __init__(self, parent: QWidget | None = None, sep: int = 4) -> None:
        super().__init__(parent)
        self._items: list[Any] = []
        self.sep = sep
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: Any) -> None:  # noqa: N802
        self._items.append(item)

    def addWidget(self, w: QWidget) -> None:  # noqa: N802
        self.addChildWidget(w)
        self.addItem(QWidgetItem(w))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int) -> Any:  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int) -> Any:  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return self._colocar(QRect(0, 0, w, 0), True)

    def setGeometry(self, r: QRect) -> None:  # noqa: N802
        super().setGeometry(r)
        self._colocar(r, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _colocar(self, r: QRect, solo_medir: bool) -> int:
        x, y, alto = r.x(), r.y(), 0
        for it in self._items:
            if it.widget() is not None and it.widget().isHidden():
                continue
            h = it.sizeHint()
            if x + h.width() > r.right() + 1 and alto > 0:
                x, y, alto = r.x(), y + alto + self.sep, 0
            if not solo_medir:
                it.setGeometry(QRect(QPoint(x, y), h))
            x += h.width() + self.sep
            alto = max(alto, h.height())
        return y + alto - r.y()


class Programador(QWidget):
    """Cajones con lo que se puede usar (entradas, salidas, internas, etapas, constantes), botones para combinar
    (· Y, + O, NOT, ↑, ↓, paréntesis, quitar, comparar, temporizar) y el lienzo con los bloques. `fuente()` devuelve
    las variables {nombre: (papel, tipo)} y las etapas (en notación X) del modelo en curso."""

    cambiado = Signal(str)

    def __init__(self, fuente: Callable[[], tuple[dict[str, tuple[str, str]], list[str]]]) -> None:
        super().__init__()
        self.fuente = fuente
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        cajones = QWidget()
        fc = FlowLayout(cajones)
        self.cajones: dict[str, QToolButton] = {}
        for clave, titulo in (("entrada", "Entradas"), ("salida", "Salidas"), ("interna", "Internas"),
                              ("etapa", "Etapas X"), ("constante", "Constantes")):
            b = QToolButton()
            b.setText(f"{titulo} ▾")
            b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            fondo, borde = COLORES[clave]
            b.setStyleSheet(f"QToolButton {{ background: {fondo}; border: 1px solid {borde}; border-radius: 5px; "
                            f"padding: 2px 6px; color: {borde} }} QToolButton::menu-indicator {{ image: none }}")
            menu = QMenu(b)
            menu.aboutToShow.connect(lambda c=clave, m=menu: self._llenar(c, m))
            b.setMenu(menu)
            fc.addWidget(b)
            self.cajones[clave] = b
        lay.addWidget(cajones)
        botones = QWidget()
        fb = FlowLayout(botones)
        self.botones: dict[str, QToolButton] = {}
        for clave, texto, tip, accion in (
                ("y", "· Y", "Y (AND) entre lo anterior y lo siguiente; sobre un · o + lo cambia", lambda: self._op("AND")),
                ("o", "+ O", "O (OR)", lambda: self._op("OR")),
                ("not", "NOT", "Negación: barra encima del bloque o del grupo seleccionado (otra vez: la quita)",
                 lambda: self._hacer(self.lienzo.e.negar)),
                ("sube", "↑", "Flanco ascendente del bloque o del grupo seleccionado", lambda: self._hacer(lambda: self.lienzo.e.flanco("↑"))),
                ("baja", "↓", "Flanco descendente", lambda: self._hacer(lambda: self.lienzo.e.flanco("↓"))),
                ("par", "( )", "Paréntesis alrededor de lo seleccionado (Mayús+clic para seleccionar varios bloques)",
                 lambda: self._hacer(self.lienzo.e.envolver)),
                ("quitar", "⌫", "Quitar el bloque seleccionado (o el de antes del cursor); un paréntesis, con su pareja",
                 lambda: self._hacer(self.lienzo.e.quitar)),
                ("comparar", "Comparar…", "Una variable numérica comparada con un valor: [CT ≥ 3]", self._comparar),
                ("temporizar", "Temporizar…", "Retardo como en la norma: 3s/X1, X1/2s", self._temporizar)):
            b = QToolButton()
            b.setText(texto)
            b.setToolTip(tip)
            b.clicked.connect(accion)
            fb.addWidget(b)
            self.botones[clave] = b
        lay.addWidget(botones)
        self.lienzo = LienzoBloques()
        self.lienzo.cambiado.connect(self._emitir)
        self.lienzo.editar.connect(self._editar)
        lay.addWidget(self.lienzo)

    # -- datos del modelo
    def _clase(self) -> Callable[[str], str]:
        variables, etapas = self.fuente()
        roles = {n: r for n, (r, _) in variables.items()}
        return lambda t: categoria(t, roles, set(etapas))

    def opciones(self, cajon: str) -> list[tuple[str, str]]:
        """(texto del menú, lo que se inserta) de un cajón. Las variables numéricas abren «Comparar…»."""
        variables, etapas = self.fuente()
        if cajon == "etapa":
            return [(x, x) for x in etapas]
        if cajon == "constante":
            return [("1 (siempre verdadera)", "1"), ("0 (siempre falsa)", "0")]
        papel = {"entrada": "input", "salida": "output", "interna": "internal"}[cajon]
        return [(n if t == "bool" else f"{n}  [comparar…]", n) for n, (r, t) in variables.items() if r == papel]

    def _llenar(self, cajon: str, menu: QMenu) -> None:
        menu.clear()
        ops = self.opciones(cajon)
        if not ops:
            a = menu.addAction("(no hay ninguna: créela en el panel Variables)")
            a.setEnabled(False)
        for texto, valor in ops:
            menu.addAction(texto, lambda v=valor, c=cajon: self.poner_bloque(v, c))

    # -- acciones
    def poner(self, texto: str) -> None:
        """Muestra un texto (el guardado, o lo escrito a mano); si es el mismo que ya hay, no toca cursor ni selección."""
        if normalizar_espacios(texto) == self.lienzo.e.texto():
            clase = self._clase()  # el mismo texto, pero una variable pudo crearse o cambiar de papel: su color
            for b in self.lienzo.e.b:
                if b["k"] == "atomo":
                    b["cat"] = clase(b["t"])
            self.lienzo.update()
            return
        self.lienzo.e = Expresion(trocear(texto, self._clase()))
        self.lienzo.actualizar()

    def texto(self) -> str:
        return self.lienzo.e.texto()

    def poner_bloque(self, valor: str, cajon: str | None = None) -> None:
        """Inserta un operando en el cursor; una variable numérica pasa antes por «Comparar…»."""
        variables, _ = self.fuente()
        if cajon in ("entrada", "salida", "interna") and variables.get(valor, ("", "bool"))[1] != "bool":
            valor = pedir_comparacion(self, self._numericas(), valor)
            if not valor:
                return
        self.lienzo.e.insertar([{"k": "atomo", "t": valor, "cat": self._clase()(valor), "neg": False, "flanco": ""}])
        self._emitir()

    def _op(self, op: str) -> None:
        e = self.lienzo.e
        if e.sel and e.sel[1] - e.sel[0] == 1 and e.b[e.sel[0]]["k"] == "op":
            e.b[e.sel[0]]["t"] = op
        else:
            e.insertar([{"k": "op", "t": op}])
        self._emitir()

    def _hacer(self, f: Callable[[], Any]) -> None:
        f()
        self._emitir()

    def _numericas(self) -> list[str]:
        return [n for n, (_, t) in self.fuente()[0].items() if t != "bool"]

    def _condiciones(self) -> list[str]:
        variables, etapas = self.fuente()
        return list(etapas) + [n for n, (r, t) in variables.items() if r in ("input", "output") and t == "bool"]

    def _seleccion(self) -> str:
        e = self.lienzo.e
        return juntar(e.b[e.sel[0]:e.sel[1]]) if e.sel else ""

    def _comparar(self) -> None:
        texto = pedir_comparacion(self, self._numericas(), self._seleccion() if _CMP.match(self._seleccion()) else "")
        if texto:
            self._colocar(texto, sustituir=bool(_CMP.match(self._seleccion())))

    def _temporizar(self) -> None:
        """Con un bloque o grupo seleccionado, lo temporiza (X1 pasa a 3s/X1)."""
        sel = self._seleccion()
        texto = pedir_temporizacion(self, self._condiciones(), sel)
        if texto:
            self._colocar(texto, sustituir=bool(sel))

    def _editar(self, i: int) -> None:
        b = self.lienzo.e.b[i]
        self.lienzo.e.sel = (i, i + 1)
        if b["cat"] == "comparacion":
            texto = pedir_comparacion(self, self._numericas(), b["t"])
        elif b["cat"] == "tiempo":
            texto = pedir_temporizacion(self, self._condiciones(), b["t"])
        else:
            return
        if texto:
            b["t"] = texto
            self._emitir()

    def _colocar(self, texto: str, sustituir: bool) -> None:
        nuevo = [{"k": "atomo", "t": texto, "cat": self._clase()(texto), "neg": False, "flanco": ""}]
        (self.lienzo.e.reemplazar if sustituir else self.lienzo.e.insertar)(nuevo)
        self._emitir()

    def _emitir(self) -> None:
        self.lienzo.actualizar()
        self.cambiado.emit(self.lienzo.e.texto())
