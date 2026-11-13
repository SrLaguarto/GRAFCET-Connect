"""Paleta booleana agrupada; conserva el dibujo y el arrastre de PaletaBloques."""
from __future__ import annotations

import re
import unicodedata
import weakref

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit

from . import estilo
from .bloques import COLORES, PAPEL, PaletaBloques, etapa_visible, nuevo, var

GRUPOS = (("entrada", "Entradas"), ("etapa", "Etapas"), ("interna", "Memorias"), ("salida", "Salidas"))
MENSAJE_VACIO = "No hay variables ni etapas. Créelas en el panel Variables o añada etapas al dibujo."
CLAVE_PLEGADOS = "formulador/plegados"  # los grupos plegados, por su papel («entrada,salida»): lo comparten todas las paletas


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if not unicodedata.combining(c))


class TituloGrupo(QAbstractButton):
    """El subtítulo de un grupo de la paleta («▾ Entradas»): un clic, Espacio o Intro lo pliega o lo despliega. El triángulo lleva el color
    del papel; con el teclado (Tab) se ve el foco."""

    def __init__(self, papel, paleta):
        super().__init__(paleta)
        self.papel, self.paleta, self.plegado = papel, paleta, False
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def keyPressEvent(self, evento):  # noqa: N802
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            return
        super().keyPressEvent(evento)

    def sizeHint(self):  # noqa: N802
        medidas = QFontMetricsF(self.paleta._fuente_titulo())
        return QSize(int(medidas.horizontalAdvance(self.text())) + estilo.E4 + estilo.E2, int(medidas.height()))

    def paintEvent(self, evento):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cy = self.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLORES[self.papel]))
        if self.plegado:  # ▸
            p.drawPolygon(QPolygonF([QPointF(1, cy - 4), QPointF(1, cy + 4), QPointF(7, cy)]))
        else:  # ▾
            p.drawPolygon(QPolygonF([QPointF(0, cy - 3), QPointF(8, cy - 3), QPointF(4, cy + 3)]))
        p.setFont(self.paleta._fuente_titulo())
        p.setPen(QColor(estilo.TINTA_2))
        p.drawText(QRectF(estilo.E4, 0, self.width() - estilo.E4, self.height()),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.text())
        if self.hasFocus():
            p.setPen(QPen(QColor(estilo.FOCO), 2, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        p.end()


class PaletaVariables(PaletaBloques):
    geometria_cambiada = Signal()
    ajustes = None  # los ajustes de la aplicación (`QSettings`), que pone la ventana: ahí se recuerdan los grupos plegados
    _instancias = weakref.WeakSet()

    def __init__(self, fuente, grupo="", columna=False):
        self._ajustes = type(self).ajustes
        self._plegados_locales = set()  # sin ajustes (una paleta suelta): solo en esta paleta
        self._botones_titulo = {}
        self._efectivos = set()  # los plegados que de verdad lo están ahora (con filtro escrito, los grupos con coincidencias se ven)
        self._titulos = []
        type(self)._instancias.add(self)
        self.grupos = []
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

    # -- grupos plegables
    def plegados(self):
        if self._ajustes is None:
            return set(self._plegados_locales)
        valor = self._ajustes.value(CLAVE_PLEGADOS, "")
        if isinstance(valor, (list, tuple)):
            valor = ",".join(str(v) for v in valor)
        return {p for p in str(valor or "").split(",") if p in {g for g, _ in GRUPOS}}

    def alternar(self, papel):
        """Pliega o despliega un grupo y lo recuerda; las demás paletas de la misma aplicación lo siguen."""
        nuevos = self.plegados() ^ {papel}
        if self._ajustes is None:
            self._plegados_locales = nuevos
        else:
            self._ajustes.setValue(CLAVE_PLEGADOS, ",".join(g for g, _ in GRUPOS if g in nuevos))
            self._ajustes.sync()
        for otra in list(type(self)._instancias):
            if otra is self or (self._ajustes is not None and otra._ajustes is self._ajustes):
                otra._filtrar()

    def _colocar_titulos(self):
        activos = set()
        for papel, titulo, rect in self._titulos:
            boton = self._botones_titulo.get(papel)
            if boton is None:
                boton = self._botones_titulo[papel] = TituloGrupo(papel, self)
                boton.clicked.connect(lambda _=False, p=papel: self.alternar(p))
            boton.setText(titulo)
            boton.plegado = papel in self._efectivos
            boton.setAccessibleName(f"{titulo}: {'plegado' if boton.plegado else 'desplegado'}")
            boton.setGeometry(rect.toRect())
            boton.show()
            boton.update()
            activos.add(papel)
        for papel, boton in self._botones_titulo.items():
            if papel not in activos:
                boton.hide()

    def _calcular(self, ancho):
        super()._calcular(ancho)
        if self.clave != "variables":
            self._titulos = []
        self._colocar_titulos()

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
        self._efectivos = set() if texto else self.plegados()
        for papel, titulo, nodos in self._todos:
            def nombre_visible(nodo):
                return etapa_visible(nodo["n"]) if nodo["k"] == "etapa" else nodo["n"]
            visibles = [n for n in nodos if texto in sin_acentos(nombre_visible(n))]
            if visibles:
                if papel in self._efectivos:  # plegado: el título sigue, sin fichas
                    self.grupos.append((papel, titulo, len(self._raices), 0))
                    continue
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
        return  # los subtítulos son botones (`TituloGrupo`), no se pintan aquí
