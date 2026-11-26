"""El menú común de variable (E8, P10): la lista que se despliega al elegir la variable de una acción, en la ventana de Propiedades y sobre la
acción del dibujo.

Es la misma lista en los dos sitios: agrupada en «Salidas» y «Memorias», cada variable con la barra del color de su origen y, solo si el tipo
varía (no es booleana), su tipo corto («Ent», «Dec»); con más de `UMBRAL_FILTRO` variables se puede filtrar escribiendo. Sigue siendo el
desplegable nativo de Qt (con su ratón, su teclado y su Esc): aquí se comparten el delegado que lo pinta, su vista y la caja que lo abre.

Lo que se ofrece lo decide quien llena el desplegable (una continua, solo booleanas; una memorizada, de cualquier tipo): este módulo no
crea variables (P-IMP-46) ni elige el tipo."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QComboBox, QLabel, QSizePolicy, QStyle, QStyledItemDelegate,
                               QStyleOptionComboBox, QStyleOptionViewItem, QStylePainter, QToolTip)

from . import estilo
from .ayudas_emergentes import mostrar_ayuda

UMBRAL_FILTRO = 12  # con más variables que estas, el menú se puede filtrar escribiendo
MARGEN, ANCHO_BARRA, HUECO = 8, 3, 6  # margen de cada fila, barra de origen y hueco entre el nombre y el tipo
ROL_PAPEL = Qt.ItemDataRole.UserRole + 1  # «output»/«internal» (o «S»/«M»): el origen de la variable de la fila
ROL_TIPO = Qt.ItemDataRole.UserRole + 2  # el tipo corto que se enseña a su derecha (vacío: booleana, no varía)
GRUPOS = {"output": "Salidas", "internal": "Memorias"}
FILTRO = "Filtrar…"


def clave_papel(papel: str) -> str:
    """El origen en su clave larga: «S» -> output, «M» -> internal."""
    return {"S": "output", "M": "internal"}.get(papel, papel or "")


def color_papel(papel: str) -> str:
    """El color de la barra de origen: salida, verde de la simulación; memoria, ciruela."""
    return {"output": estilo.SIMULACION, "internal": estilo.ORIGEN_MEMORIA}.get(clave_papel(papel), estilo.TINTA_2)


def tipo_a_mostrar(tipo_corto: str) -> str:
    """El tipo se enseña donde varía: una booleana no lleva nada."""
    return "" if tipo_corto in ("", "Bool") else tipo_corto


def es_cabecera(indice: Any) -> bool:
    """Una fila de rótulo de grupo del modelo (sin dato y deshabilitada, con texto)."""
    return indice.data(Qt.ItemDataRole.UserRole) is None and bool((indice.data(Qt.ItemDataRole.DisplayRole) or "").strip())


def es_variable(indice: Any) -> bool:
    dato = indice.data(Qt.ItemDataRole.UserRole)
    return isinstance(dato, str) and bool(dato)


class DelegadoMenu(QStyledItemDelegate):
    """Pinta las filas del menú: rótulo de grupo, variable con su barra de origen y tipo corto, y el resto (el marcador «Elija la variable…»)
    como texto. Un modelo sin filas de rótulo (el desplegable sobre la acción) lleva el rótulo del grupo sobre la primera fila de cada origen."""

    def __init__(self, padre: Any = None, rotulos_propios: bool = False) -> None:
        super().__init__(padre)
        self.rotulos_propios = rotulos_propios  # el modelo no trae filas de rótulo: se dibujan sobre la primera variable de cada origen

    # -- qué es cada fila
    def _rotulo_sobre(self, indice: Any) -> str:
        """El rótulo de grupo que esta fila lleva encima (solo con `rotulos_propios`)."""
        if not self.rotulos_propios or not es_variable(indice):
            return ""
        grupo = clave_papel(indice.data(ROL_PAPEL) or "")
        if indice.row() > 0:
            antes = indice.model().index(indice.row() - 1, 0)
            if es_variable(antes) and clave_papel(antes.data(ROL_PAPEL) or "") == grupo:
                return ""
        return GRUPOS.get(grupo, "")

    def _alto_fila(self, fm: QFontMetrics) -> int:
        return max(estilo.ALTO_FILA_COMPACTA, fm.height() + 2 * estilo.E2)

    def sizeHint(self, opcion: Any, indice: Any) -> QSize:  # noqa: N802
        fm = opcion.fontMetrics
        alto = self._alto_fila(fm)
        if es_cabecera(indice):
            return QSize(0, fm.height() + estilo.E2 + estilo.E1)
        if self._rotulo_sobre(indice):
            alto += fm.height() + estilo.E1
        return QSize(0, alto)  # (sin ancho propio: la lista mide lo que pide `ancho_menu`)

    def hueco_nombre(self, fm: QFontMetrics, rect: QRect, tipo: str) -> int:
        """Lo que queda para el nombre en una fila: su ancho menos márgenes, barra y el tipo (con su hueco)."""
        return rect.width() - 2 * MARGEN - ANCHO_BARRA - estilo.E2 - (fm.horizontalAdvance(tipo) + HUECO if tipo else 0)

    def helpEvent(self, evento: Any, vista: Any, opcion: Any, indice: Any) -> bool:  # noqa: N802
        """La ayuda emergente solo sale si el nombre está acortado, y entonces lo da entero."""
        if evento.type() == QEvent.Type.ToolTip and es_variable(indice):
            nombre = indice.data(Qt.ItemDataRole.UserRole)
            tipo = tipo_a_mostrar(indice.data(ROL_TIPO) or "")
            if opcion.fontMetrics.horizontalAdvance(nombre) > self.hueco_nombre(opcion.fontMetrics, opcion.rect, tipo):
                mostrar_ayuda(evento.globalPos(), nombre, vista)
            else:
                QToolTip.hideText()
            return True
        return super().helpEvent(evento, vista, opcion, indice)

    def paint(self, p: QPainter, opcion: Any, indice: Any) -> None:
        opt = QStyleOptionViewItem(opcion)
        self.initStyleOption(opt, indice)
        fm = opt.fontMetrics
        habil = bool(indice.flags() & Qt.ItemFlag.ItemIsEnabled)
        p.save()
        p.fillRect(opt.rect, QColor("#ffffff"))  # fondo blanco sólido (evita popups negros en Windows sobre VentanaFlotante translúcida)
        p.setFont(opt.font)
        if es_cabecera(indice):
            p.setPen(QColor(estilo.TINTA_3))
            p.drawText(opt.rect.adjusted(MARGEN, 0, -MARGEN, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       (indice.data(Qt.ItemDataRole.DisplayRole) or "").strip())
            p.restore()
            return
        if not es_variable(indice):  # el marcador o «ninguna»: texto sin más
            p.setPen(QColor(estilo.TINTA_2 if habil else estilo.DESHABILITADO))
            p.drawText(opt.rect.adjusted(MARGEN, 0, -MARGEN, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       (indice.data(Qt.ItemDataRole.DisplayRole) or "").strip())
            p.restore()
            return
        fila = QRect(opt.rect)
        rotulo = self._rotulo_sobre(indice)
        if rotulo:
            p.setPen(QColor(estilo.TINTA_3))
            p.drawText(QRect(fila.left() + MARGEN, fila.top(), fila.width() - 2 * MARGEN, fm.height() + estilo.E1),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, rotulo)
            fila.setTop(fila.top() + fm.height() + estilo.E1)
        elegida = bool(opt.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)) and habil
        if elegida:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(estilo.ACENTO_SUAVE))
            p.drawRoundedRect(QRectF(fila).adjusted(3, 1, -3, -1), estilo.R_S, estilo.R_S)
        nombre = indice.data(Qt.ItemDataRole.UserRole)
        tipo = tipo_a_mostrar(indice.data(ROL_TIPO) or "")
        barra = QRectF(fila.left() + MARGEN, fila.top() + estilo.E2, ANCHO_BARRA, fila.height() - 2 * estilo.E2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color_papel(indice.data(ROL_PAPEL) or "") if habil else estilo.DESHABILITADO))
        p.drawRoundedRect(barra, 1.5, 1.5)
        x = fila.left() + MARGEN + ANCHO_BARRA + estilo.E2
        p.setPen(QColor(estilo.TINTA if habil else estilo.DESHABILITADO))
        corto = fm.elidedText(nombre, Qt.TextElideMode.ElideRight, max(0, self.hueco_nombre(fm, fila, tipo)))
        p.drawText(QRect(x, fila.top(), max(0, fila.right() - x), fila.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, corto)
        if tipo:
            p.setPen(QColor(estilo.ACENTO))
            p.drawText(fila.adjusted(0, 0, -MARGEN, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, tipo)
        p.restore()


class FiltroMenu(QObject):
    """El filtro de la lista del menú, enganchado a la vista nativa del desplegable (la vista de Qt hace de la lista de un desplegable lo que una
    suya no hace: elegir con el ratón, cerrar…). Con más de `UMBRAL_FILTRO` variables, lo que se escribe con la lista abierta la filtra: el rótulo
    «Filtrar…» de su cabecera lo muestra. Retroceso borra una letra. Con menos, las teclas son las de siempre (buscar por la inicial)."""

    def __init__(self, combo: "ComboMenu") -> None:
        super().__init__(combo)
        self.combo = combo
        self.filtro = ""
        self.etiqueta: QLabel | None = None  # el «Filtrar…» de la cabecera del menú (lo crea `ComboMenu._preparar_filtro`)
        combo.view().installEventFilter(self)

    def poner_filtro(self, texto: str) -> None:
        """Muestra solo las variables que contienen `texto` (sin distinguir mayúsculas) y los rótulos de los grupos que conservan alguna."""
        self.filtro = texto
        vista, modelo = self.combo.view(), self.combo.model()
        n = modelo.rowCount()
        visibles = [True] * n
        if texto:
            clave = texto.lower()
            for i in range(n):
                ind = modelo.index(i, 0)
                if es_variable(ind):
                    visibles[i] = clave in ind.data(Qt.ItemDataRole.UserRole).lower()
            for i in range(n):  # un rótulo sin variables visibles detrás (hasta el siguiente rótulo) se esconde
                if es_cabecera(modelo.index(i, 0)):
                    k, hay = i + 1, False
                    while k < n and not es_cabecera(modelo.index(k, 0)):
                        hay = hay or (visibles[k] and es_variable(modelo.index(k, 0)))
                        k += 1
                    visibles[i] = hay
        for i in range(n):
            if vista.isRowHidden(i) == visibles[i]:  # (solo se toca lo que cambia)
                vista.setRowHidden(i, not visibles[i])
        if self.etiqueta is not None:
            self.etiqueta.setText(texto or FILTRO)
            self.etiqueta.setStyleSheet(f"color: {estilo.TINTA if texto else estilo.TINTA_3}; background: {estilo.SUPERFICIE}; "
                                        f"border: 1px solid {estilo.BORDE_CONTROL}; border-radius: {estilo.R_S}px; padding: 1px {estilo.E2}px;")

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if evento.type() == QEvent.Type.KeyPress and self.combo.con_filtro()                 and not evento.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            texto = evento.text()
            if evento.key() == Qt.Key.Key_Backspace:
                self.poner_filtro(self.filtro[:-1])
                return True
            if texto and texto.isprintable() and (texto != " " or self.filtro):
                self.poner_filtro(self.filtro + texto)
                return True
        return False


def ancho_menu(combo: QComboBox) -> int:
    """El ancho de la lista desplegada: el del cuadro o, si un nombre no cabe, lo justo para el más largo (nombre, barra, tipo y márgenes)."""
    vista = combo.view()
    fm = vista.fontMetrics()
    pide = 0
    for i in range(combo.count()):
        ind = combo.model().index(i, 0)
        if es_variable(ind):
            tipo = tipo_a_mostrar(ind.data(ROL_TIPO) or "")
            pide = max(pide, fm.horizontalAdvance(ind.data(Qt.ItemDataRole.UserRole)) + 2 * MARGEN + ANCHO_BARRA + estilo.E2
                       + (fm.horizontalAdvance(tipo) + HUECO if tipo else 0))
        else:
            pide = max(pide, fm.horizontalAdvance((ind.data(Qt.ItemDataRole.DisplayRole) or "").strip()) + 2 * MARGEN)
    barra = vista.verticalScrollBar().sizeHint().width() if combo.count() > combo.maxVisibleItems() else 0
    return max(combo.width(), pide + barra + 2 * vista.frameWidth() + 2)


class ComboMenu(QComboBox):
    """Un desplegable con el menú común: su delegado y su filtro son los de este módulo (la vista es la nativa de Qt). Quien lo llena pone en
    cada fila el nombre (dato), el origen (`ROL_PAPEL`) y el tipo corto (`ROL_TIPO`)."""

    def __init__(self, parent: Any = None, rotulos_propios: bool = False) -> None:
        super().__init__(parent)
        self.delegado = DelegadoMenu(self.view(), rotulos_propios)
        self.view().setItemDelegate(self.delegado)
        self.view().setStyleSheet(
            f"QAbstractItemView {{ background: #ffffff; color: {estilo.TINTA}; border: 1px solid #7b8a9c; "
            f"outline: 0; selection-background-color: {estilo.ACENTO_SUAVE}; selection-color: {estilo.TINTA}; }}"
        )
        self.filtro_menu = FiltroMenu(self)

    def con_filtro(self) -> bool:
        """Retirado el rótulo/filtro superior por decisión de interfaz (`Cositas.docx`)."""
        return False

    def _preparar_filtro(self) -> None:
        """Con más de `UMBRAL_FILTRO` variables, el rótulo «Filtrar…» se pone sobre la lista; sin tantas, no hay."""
        f, marco = self.filtro_menu, self.view().parentWidget()
        if f.etiqueta is not None:
            f.etiqueta.hide()
        if f.filtro:
            f.poner_filtro("")
        if not self.con_filtro() or marco is None or marco.layout() is None:
            return
        if f.etiqueta is None:
            f.etiqueta = QLabel(FILTRO)
            f.etiqueta.setAccessibleName("Filtro de variables")
            f.etiqueta.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            f.etiqueta.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            f.etiqueta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            marco.layout().insertWidget(0, f.etiqueta, 0)
        f.etiqueta.setFixedHeight(max(24, f.etiqueta.fontMetrics().height() + 8))
        marco.layout().setStretchFactor(self.view(), 1)
        f.etiqueta.show()
        f.poner_filtro("")

    def showPopup(self) -> None:  # noqa: N802
        """La lista empieza donde el cuadro y mide lo que él (o lo justo para el nombre más largo): el ancho se fija antes de mostrarla, para que
        no se redimensione ya abierta."""
        ancho = ancho_menu(self)
        self.view().setMinimumWidth(ancho)
        self.view().doItemsLayout()
        self._preparar_filtro()
        marco = self.view().parentWidget()
        if marco is not None and marco.isWindow():
            marco.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            marco.setStyleSheet("background: #ffffff; border: 1px solid #7b8a9c;")
            marco.setFixedWidth(ancho)
        super().showPopup()
        if marco is not None and marco.isWindow() and marco.x() != self.mapToGlobal(QPoint(0, 0)).x():
            marco.move(self.mapToGlobal(QPoint(0, 0)).x(), marco.y())

    def hidePopup(self) -> None:  # noqa: N802
        if self.filtro_menu.filtro:
            self.filtro_menu.poner_filtro("")
        super().hidePopup()


def pintar_caja(combo: QComboBox, nombre: str, papel: str, parpadeando: bool = False, marcador: str = "") -> None:
    """La caja cerrada de la variable en la ventana: borde único según foco/aviso, barra de origen, nombre y flecha."""
    p = QStylePainter(combo)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    zona = QRectF(combo.rect()).adjusted(.5, .5, -.5, -.5)
    foco_tecl = combo.hasFocus() and bool(combo.property("tecl"))
    foco_raton = combo.hasFocus() and not foco_tecl
    if parpadeando:
        pluma, caja = QPen(QColor(estilo.AVISO_BORDE), 1.5), zona
    elif foco_tecl:
        pluma, caja = QPen(QColor(estilo.FOCO), 2, Qt.PenStyle.DashLine), zona.adjusted(.5, .5, -.5, -.5)
    elif foco_raton:
        pluma, caja = QPen(QColor(estilo.ACENTO), 1.5), zona
    else:
        pluma, caja = QPen(QColor(estilo.BORDE_CONTROL), 1.2), zona
    p.setPen(pluma)
    p.setBrush(QColor(estilo.AVISO_FONDO if parpadeando else estilo.SUPERFICIE if combo.isEnabled() else estilo.SUPERFICIE_2))
    p.drawRoundedRect(caja, estilo.R_S, estilo.R_S)
    x = zona.left() + estilo.E2 + 2
    if nombre:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color_papel(papel)))
        p.drawRoundedRect(QRectF(x, zona.top() + estilo.E2, ANCHO_BARRA, zona.height() - 2 * estilo.E2), 1.5, 1.5)
        x += ANCHO_BARRA + estilo.E2
    flecha = QRect(int(zona.right()) - 20, 0, 18, combo.height())
    opcion = QStyleOptionComboBox()
    combo.initStyleOption(opcion)
    opcion.currentText = ""
    opcion.rect = QRect(flecha)
    opcion.frame = False
    p.setPen(QColor(estilo.TINTA if nombre else estilo.TINTA_3))
    p.setFont(combo.font())
    texto = nombre or marcador
    corto = combo.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideRight, max(0, flecha.left() - int(x) - estilo.E2))
    p.drawText(QRect(int(x), 0, max(0, flecha.left() - int(x)), combo.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, corto)
    if corto != texto:
        combo.setToolTip(texto)
    else:
        combo.setToolTip("")
    p.setPen(QPen(QColor(estilo.TINTA_2), 1.6))
    cx, cy = flecha.center().x(), combo.height() / 2
    p.drawLine(QPoint(int(cx) - 4, int(cy) - 2), QPoint(int(cx), int(cy) + 2))
    p.drawLine(QPoint(int(cx), int(cy) + 2), QPoint(int(cx) + 4, int(cy) - 2))
