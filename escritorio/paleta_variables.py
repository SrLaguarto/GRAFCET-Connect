"""Paleta booleana agrupada; conserva el dibujo y el arrastre de PaletaBloques."""
from __future__ import annotations

import re
import unicodedata

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF
from PySide6.QtWidgets import QLabel, QLineEdit

from . import estilo
from .bloques import COLORES, PAPEL, PaletaBloques, etapa_visible, nuevo, var

GRUPOS = (("entrada", "Entradas"), ("etapa", "Etapas"), ("interna", "Memorias"), ("salida", "Salidas"))
MENSAJE_VACIO = "No hay variables ni etapas. Créelas en el panel Variables o añada etapas al dibujo."


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if not unicodedata.combining(c))


class PaletaVariables(PaletaBloques):
    geometria_cambiada = Signal()

    def __init__(self, fuente, grupo="", columna=False):
        self.grupos = []
        self._titulos = []
        self._todos = []
        self._ancho_titulos = 0
        self.filtro = None
        self.mensaje = None
        super().__init__(fuente, grupo, columna=columna)
        self.filtro = QLineEdit(self)
        self.filtro.setPlaceholderText("Filtrar…")
        self.filtro.setClearButtonEnabled(True)
        self.filtro.textChanged.connect(self._filtrar)
        self.mensaje = QLabel(MENSAJE_VACIO, self)
        self.mensaje.setWordWrap(True)
        self.mensaje.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.mensaje.setStyleSheet(f"color: {estilo.TINTA_2}; background: transparent; border: none;")
        self.cargar("variables")

    def cargar(self, clave):
        if clave != "variables":
            if self.filtro is not None:
                self.filtro.hide()
                self.mensaje.hide()
            self.grupos = []
            super().cargar(clave)
            return
        self.clave = clave
        self.motor.reiniciar()
        self._todos = []
        for papel, titulo in GRUPOS:
            if papel == "etapa":
                def por_numero(nombre):
                    if re.fullmatch(r"X\d+", nombre):
                        return (0, int(nombre[1:]), "")
                    return (1, 0, nombre.lower())
                etapas = sorted(dict.fromkeys(self.motor.etapas), key=por_numero)
                nodos = [nuevo("etapa", n=n) for n in etapas]
            else:
                nombres = (n for n, (r, t) in self.motor.vars.items() if r == PAPEL[papel] and t == "bool")
                nodos = [var(n, PAPEL[papel]) for n in sorted(nombres, key=self._orden)]
            self._todos.append((papel, titulo, nodos))
        self._filtrar()

    def _filtrar(self):
        if self.clave != "variables":
            return
        total = sum(len(nodos) for _, _, nodos in self._todos)
        texto = ""
        if self.filtro is not None:
            self.filtro.setVisible(self.clave == "variables" and total > 12)
            if total <= 12:
                self.filtro.blockSignals(True)
                self.filtro.clear()
                self.filtro.blockSignals(False)
            texto = sin_acentos(self.filtro.text())
        self.grupos = []
        self._raices = []
        for papel, titulo, nodos in self._todos:
            def nombre_visible(nodo):
                return etapa_visible(nodo["n"]) if nodo["k"] == "etapa" else nodo["n"]
            visibles = [n for n in nodos if texto in sin_acentos(nombre_visible(n))]
            if visibles:
                self.grupos.append((papel, titulo, len(self._raices), len(visibles)))
                self._raices.extend(visibles)
        if self.mensaje is not None:
            self.mensaje.setVisible(total == 0 and self.clave == "variables")
        self.invalidar()
        self.geometria_cambiada.emit()

    def _fuente_titulo(self):
        fuente = QFont(self.font())
        fuente.setPixelSize(estilo.T_PEQUENA)
        return fuente

    def _maqueta(self, ancho):
        if self.clave != "variables":
            return super()._maqueta(ancho)
        margen = estilo.E2
        x = float(margen)
        y = float(margen)
        self._titulos = []
        self._ancho_titulos = 0
        if self.filtro is not None and not self.filtro.isHidden():
            y += estilo.ALTO_CONTROL + estilo.E2
        if self.mensaje is not None and not self.mensaje.isHidden():
            alto = self.mensaje.heightForWidth(max(1, int(ancho - 2 * margen)))
            return [], y + alto + margen
        medidas = QFontMetricsF(self._fuente_titulo())
        alto_titulo = medidas.height()
        cajas = []
        for papel, titulo, inicio, cantidad in self.grupos:
            ancho_titulo = medidas.horizontalAdvance(titulo) + estilo.E4
            if self.una_fila:
                self._titulos.append((papel, titulo, QRectF(x, y, ancho_titulo, alto_titulo)))
                x += ancho_titulo + estilo.E2
            else:
                self._titulos.append((papel, titulo, QRectF(margen, y, ancho - 2 * margen, alto_titulo)))
                y += alto_titulo + estilo.E2
                x = float(margen)
            alto_fila = alto_titulo if self.una_fila else 0
            for i in range(inicio, inicio + cantidad):
                nodo = self._raices[i]
                ancho_caja = min(self.motor.natural(nodo, (i,)), ancho - 2 * margen)
                caja = self.motor.caja(nodo, (i,), ancho_caja)
                if x > margen and not self.una_fila and (self.columna or x + caja.w > ancho - margen):
                    x = float(margen)
                    y += alto_fila + estilo.E2
                    alto_fila = 0
                cajas.append((caja, x, y))
                x += caja.w + estilo.E2
                alto_fila = max(alto_fila, caja.h)
            if not self.una_fila:
                y += alto_fila + estilo.E3
        self._ancho_titulos = x + margen if self.una_fila else 0
        return cajas, y + (alto_fila if self.grupos and self.una_fila else 0) + margen

    def ancho_necesario(self, ancho):
        return max(super().ancho_necesario(ancho), self._ancho_titulos)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        margen = estilo.E2
        ancho = max(1, self.width() - 2 * margen)
        if self.filtro is not None:
            self.filtro.setGeometry(margen, margen, ancho, estilo.ALTO_CONTROL)
        if self.mensaje is not None:
            alto = self.mensaje.heightForWidth(ancho)
            self.mensaje.setGeometry(margen, margen, ancho, max(1, alto))
        if self.una_fila and self.clave == "variables" and not self._raices:
            self.geometria_cambiada.emit()

    def _extra(self, pintor):
        if self.clave != "variables":
            return
        pintor.setFont(self._fuente_titulo())
        for papel, titulo, rect in self._titulos:
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(COLORES[papel]))
            pintor.drawEllipse(QRectF(rect.x(), rect.center().y() - 3, 6, 6))
            pintor.setPen(QColor(estilo.TINTA_2))
            texto = rect.adjusted(estilo.E4, 0, 0, 0)
            pintor.drawText(texto, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, titulo)
