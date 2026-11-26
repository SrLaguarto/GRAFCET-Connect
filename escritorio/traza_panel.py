"""Cabecera y formato didáctico de la traza en pantalla (sin modificar la traza del núcleo)."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from . import estilo
from .paneles import CajaSeccion

_PATRON_EVENTO = re.compile(r"\b(rise|fall)\((?:'([^']*)'|([^)]+))\)")
_PATRON_TIEMPO = re.compile(r"^\s*([0-9][0-9.,]*\s*s)\s{3}(.*)$", re.S)


def partir_linea_traza(linea: str) -> tuple[str, str]:
    """Separa `(tiempo, cuerpo)` de una línea formateada como `f\"{time:>9}   {text}\"`."""
    mo = _PATRON_TIEMPO.match(linea)
    if mo:
        return mo.group(1).strip(), mo.group(2)
    return "", linea.strip()


def _traducir_eventos(crudo: str) -> str:
    """Convierte `rise('Caja en T1')` / `fall(p)` en `↑Caja en T1` / `↓p`."""
    partes: list[str] = []
    for trozo in crudo.split(", "):
        t = trozo.strip()
        mo = _PATRON_EVENTO.fullmatch(t)
        if mo:
            flecha = "↑" if mo.group(1) == "rise" else "↓"
            nombre = (mo.group(2) or mo.group(3) or "").strip().strip("`")
            partes.append(f"{flecha}{nombre}")
        else:
            partes.append(_PATRON_EVENTO.sub(
                lambda m: ("↑" if m.group(1) == "rise" else "↓") + (m.group(2) or m.group(3) or "").strip().strip("`"),
                t,
            ))
    etiqueta = "Flanco" if len(partes) == 1 else "Flancos"
    return f"{etiqueta} {', '.join(partes)}"


def _traducir_entradas(bloque: str) -> str:
    if bloque == "sin cambio de entradas":
        return "Sin cambio de entradas"
    out: list[str] = []
    for par in bloque.split(", "):
        if par.endswith("=true"):
            out.append(f"{par[:-5]} = 1")
        elif par.endswith("=false"):
            out.append(f"{par[:-6]} = 0")
        else:
            out.append(par)
    return ", ".join(out)


def _traducir_asignaciones(texto: str) -> str:
    texto = re.sub(r":=True\b", " := 1", texto)
    texto = re.sub(r":=False\b", " := 0", texto)
    texto = re.sub(r":=([^\s;]+)", r" := \1", texto)
    return texto


def formatear_texto_traza(cuerpo: str) -> str:
    """Traduce una entrada cruda de `Vista.state()['trace']` a notación GRAFCET en español."""
    texto = cuerpo.strip()
    if not texto:
        return ""
    if texto.startswith(("lote ", "vencimiento temporal: ")):
        if " · eventos: " in texto:
            cabeza, ev_crudo = texto.split(" · eventos: ", 1)
            sufijo = f" · {_traducir_eventos(ev_crudo)}"
        else:
            cabeza, sufijo = texto, ""
        prefijo, _, resto = cabeza.partition(": ")
        entradas = _traducir_entradas(resto.strip())
        if prefijo == "vencimiento temporal":
            if resto.strip() == "sin cambio de entradas":
                return "Temporizador vencido" + sufijo
            return f"Temporizador vencido · {entradas}{sufijo}"
        origen = prefijo[5:].strip()
        etiqueta = "Entradas" if origen == "manual" else f"Entradas ({origen})"
        return f"{etiqueta}: {entradas}{sufijo}"

    texto = texto.replace(" · S = {", " · Situación = {").replace(" → S = {", " → Situación = {")
    if texto.startswith("Inicio · S = {"):
        texto = "Inicio · Situación = {" + texto[len("Inicio · S = {"):]
    elif texto.startswith("Estable · S = {"):
        texto = "Estable · Situación = {" + texto[len("Estable · S = {"):]
    return _traducir_asignaciones(texto)


@lru_cache(maxsize=512)
def _partir_y_formatear(raw: str) -> tuple[str, str]:
    """Separa y traduce una entrada de la traza con caché para evitar reparseos repetidos."""
    tiempo, cuerpo = partir_linea_traza(raw)
    return tiempo, formatear_texto_traza(cuerpo)


class DelegadoTraza(QStyledItemDelegate):
    """Pinta cada línea de la traza con margen izquierdo de 16 px, cifras tabulares y notación GRAFCET."""

    MARGEN_IZQ = estilo.E4  # 16 px
    ANCHO_TIEMPO = 64
    HUECO = estilo.E3       # 12 px

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._cache_fuentes: tuple[tuple[str, int], Any, Any, QFontMetrics] | None = None
        self._cache_alto: dict[tuple[str, int, str, int], int] = {}

    def displayText(self, valor: Any, locale: Any) -> str:  # noqa: N802
        del locale
        tiempo, formateado = _partir_y_formatear(str(valor or ""))
        return f"{tiempo}  {formateado}".strip() if tiempo else formateado

    def _fuente_cuerpo(self, option: QStyleOptionViewItem) -> Any:
        f = estilo.fuente(estilo.T_PEQUENA)
        return f if f.pixelSize() > 0 else option.font

    def _fuentes(self, option: QStyleOptionViewItem) -> tuple[Any, Any, QFontMetrics]:
        clave = (estilo.ESCALA, estilo.T_PEQUENA)
        if self._cache_fuentes is None or self._cache_fuentes[0] != clave:
            f_cuerpo = self._fuente_cuerpo(option)
            f_tiempo = estilo.fuente_tabular(px=estilo.T_PEQUENA)
            self._cache_fuentes = (clave, f_cuerpo, f_tiempo, QFontMetrics(f_cuerpo))
        _, f_cuerpo, f_tiempo, fm = self._cache_fuentes
        return f_cuerpo, f_tiempo, fm

    def _ancho_cuerpo(self, total: int) -> int:
        return max(80, total - self.MARGEN_IZQ - self.ANCHO_TIEMPO - self.HUECO - 10)

    def sizeHint(self, option: QStyleOptionViewItem, index: Any) -> QSize:  # noqa: N802
        raw = str(index.data() or "")
        ancho_vista = option.rect.width()
        if ancho_vista <= 0 and option.widget is not None:
            ancho_vista = option.widget.viewport().width()
        ancho_cuerpo = self._ancho_cuerpo(ancho_vista if ancho_vista > 0 else 480)
        clave_alto = (raw, ancho_cuerpo, estilo.ESCALA, estilo.T_PEQUENA)
        alto = self._cache_alto.get(clave_alto)
        if alto is None:
            _, texto = _partir_y_formatear(raw)
            _, _, fm = self._fuentes(option)
            caja = fm.boundingRect(QRect(0, 0, ancho_cuerpo, 10000), Qt.TextFlag.TextWordWrap, texto)
            alto = max(fm.height() + 8, caja.height() + 8)
            if len(self._cache_alto) >= 512:
                self._cache_alto.clear()
            self._cache_alto[clave_alto] = alto
        return QSize(max(120, ancho_vista), alto)

    def paint(self, painter: Any, option: Any, index: Any) -> None:  # noqa: N802
        tiempo, texto = _partir_y_formatear(str(index.data() or ""))
        f_cuerpo, f_tiempo, _ = self._fuentes(option)
        fg = index.data(Qt.ItemDataRole.ForegroundRole)
        color_cuerpo = fg.color() if isinstance(fg, QColor) else QColor(estilo.TINTA)

        painter.save()
        if option.state & option.state.State_Selected:
            painter.fillRect(option.rect, QColor(estilo.ACENTO_SUAVE))
        x_t = option.rect.left() + self.MARGEN_IZQ
        x_c = x_t + self.ANCHO_TIEMPO + self.HUECO
        r_tiempo = QRect(x_t, option.rect.top() + 3, self.ANCHO_TIEMPO, max(16, option.rect.height() - 6))
        r_cuerpo = QRect(x_c, option.rect.top() + 3, max(40, option.rect.right() - x_c - 6), max(16, option.rect.height() - 6))

        if tiempo:
            painter.setFont(f_tiempo)
            painter.setPen(QColor(estilo.TINTA_3) if color_cuerpo == QColor(estilo.TINTA) else color_cuerpo)
            painter.drawText(r_tiempo, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), tiempo)

        painter.setFont(f_cuerpo)
        painter.setPen(color_cuerpo)
        painter.drawText(r_cuerpo, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), texto)
        painter.restore()


class CajaTraza(CajaSeccion):
    def __init__(self):
        super().__init__("Traza")
        self.setObjectName("cajaTraza")
        margen = 32 + 2 * estilo.E1
        self._regla_cabecera = (
            f"QGroupBox#cajaTraza {{margin-top:{margen}px; background:{estilo.SUPERFICIE};}}"
            f"QGroupBox#cajaTraza::title {{padding-top:{estilo.E2}px; padding-bottom:{estilo.E2}px; padding-left:{estilo.E4}px; color:{estilo.PRIMARIO};}}")
        self.setStyleSheet("")

    def setStyleSheet(self, hoja):  # noqa: N802
        """La actualización de escala conserva la reserva para el botón de cierre."""
        super().setStyleSheet(hoja.replace(self._regla_cabecera, "") + self._regla_cabecera)
