"""Panel «Variables» del editor: el diccionario del grafcet (REQ-EDT-07, paso 4, P-IMP-38, P-IMP-42).

Una fila por variable con tres columnas: nombre, papel (entrada, salida, memoria) y tipo (booleana, entera, decimal con
2 decimales). El valor inicial y la unidad que ya tuviera un fichero siguen en el modelo, pero no se muestran ni se
editan aquí; los usos de la variable no se listan, solo impiden quitarla (con su mensaje). Todo cambio pasa por Edicion
(rename, change_variable, add_variable, delete_variable del núcleo) y se deshace con Ctrl+Z; si no se puede, el motivo
sale debajo, la fila parpadea en naranja y la tabla vuelve a lo que hay.

«+ Entrada», «+ Salida» y «+ Memoria» (entrada, salida, memoria) añaden una fila **sin nombre**, solo de la interfaz: una variable no puede estar en el modelo sin
nombre. Al escribir un nombre válido se crea en el modelo (una operación de deshacer); si no es válido o está repetido,
se rechaza y la fila sigue en blanco. Con filas sin nombre, la ventana no deja simular ni guardar.
"""
from __future__ import annotations

from typing import Any

import re

from PySide6.QtCore import QEvent, QTimer, Qt, Signal, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QHeaderView, QLabel, QPushButton, QGridLayout, QSizePolicy,
                               QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import estilo
from .paneles import AIRE_LINEAS, CabeceraCompacta, ContextoNombres, ReparteColumnas, SALTO
from .diagrama import COL
from .edicion import Parpadeo

NOMBRE_MIN = 96  # lo menos que mide la columna del nombre a cualquier tamaño: «Papel» y «Tipo» se abrevian (o se desplaza la tabla) antes de que baje de ahí

PAPELES = (("input", "Entrada"), ("output", "Salida"), ("internal", "Memoria"))
# Los tipos que se ofrecen. Un fichero antiguo puede traer otros (decimal de 1 o 3 decimales, duración): se muestran con
# su tipo y siguen funcionando, pero si se cambia el tipo solo se elige entre estos.
TIPOS = (({"kind": "bool"}, "Booleana"), ({"kind": "int"}, "Entera"), ({"kind": "decimal", "scale": 2}, "Decimal (2)"))
COLUMNAS = ["Nombre", "Papel", "Tipo"]
SIN_NOMBRE = "Hay una variable sin nombre: escríbale un nombre o quítela"
NARANJA = "#ffd2ad"
def estilo_combo() -> str:
    return f"QComboBox {{ padding: 0px 1px 0px 3px; min-height: 24px; font-size: {estilo.T_PEQUENA}px; }} QComboBox::drop-down {{ width: 14px; }}"


ESTILO_COMBO = estilo_combo()


def _clave_tipo(t: dict[str, Any]) -> tuple[Any, ...]:
    return (t.get("kind"), str(t.get("scale")) if t.get("kind") == "decimal" else None)


ABREVIATURAS_PAPEL = {"Entrada": "Entr.", "Salida": "Sal.", "Memoria": "Mem."}


def abreviar_papel(texto: str) -> str:
    """El papel en pocas letras, sin dudas («Entr.», «Sal.», «Mem.»): la columna deja casi todo el ancho al nombre. La celda conserva el texto entero."""
    return ABREVIATURAS_PAPEL.get(texto, texto)


def abreviar_tipo(texto: str) -> str:
    """El tipo en pocas letras («Bool.», «Entera», «Dec. 2» por «Decimal (2)», «Dur.»). La celda conserva el texto entero y lo lleva en su ayuda."""
    if texto == "Booleana":
        return "Bool."
    if texto == "Duración":
        return "Dur."
    m = re.fullmatch(r"Decimal \((\d+)\)", texto)
    return f"Dec. {m.group(1)}" if m else texto


def nombre_tipo(t: dict[str, Any]) -> str:
    """El tipo en palabras: los que se ofrecen, y «Decimal (3)», «Duración»… los de un fichero antiguo."""
    for tt, texto in TIPOS:
        if _clave_tipo(tt) == _clave_tipo(t):
            return texto
    kind = t.get("kind")
    return {"decimal": f"Decimal ({t.get('scale')})", "duration": "Duración"}.get(kind, str(kind))


class _DelegadoCombo(QStyledItemDelegate):
    """Papel y Tipo se ven como texto; al editar la celda aparece el desplegable con las opciones. Al elegir, se aplica y
    el desplegable se cierra."""

    def __init__(self, panel: "PanelVariables") -> None:
        super().__init__(panel.tabla)
        self.panel = panel

    def initStyleOption(self, option: Any, index: Any) -> None:  # noqa: N802
        """Lo que se ve en la celda: el **nombre entero**, partido por los «_» en las líneas que haga falta (`ContextoNombres.lineas`: la fila
        crece lo necesario), y el papel y el tipo en palabras donde caben y abreviados donde no (la celda sigue teniendo el texto entero:
        lo leen las pruebas y la ayuda emergente)."""
        super().initStyleOption(option, index)
        if not option.text:
            return
        if index.column() == 0:
            margen = 2 * (QApplication.style().pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 1) + 2
            option.text = SALTO.join(self.panel.contexto.lineas(option.text, QFontMetrics(option.font), option.rect.width() - margen))
            option.textElideMode = Qt.TextElideMode.ElideNone
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.WrapText  # (las líneas son las de arriba)
        elif not self.panel.completo:
            option.text = (abreviar_papel if index.column() == 1 else abreviar_tipo)(option.text)

    def sizeHint(self, option: Any, index: Any) -> QSize:  # noqa: N802
        """Una línea: el alto de fila de siempre (26 px, 30 a pantalla completa); un nombre partido en varias, lo que miden sus líneas más un poco
        de aire arriba y abajo (varias líneas seguidas no se pegan a las de al lado)."""
        tam = super().sizeHint(option, index)
        alto = self.panel._alto_fila()
        if index.column() == 0:
            opcion = QStyleOptionViewItem(option)
            self.initStyleOption(opcion, index)
            lineas = opcion.text.count(SALTO) + 1
            if lineas > 1:
                alto = max(alto, lineas * QFontMetrics(opcion.font).lineSpacing() + 2 * AIRE_LINEAS + 2)
        tam.setHeight(alto)
        return tam

    def createEditor(self, parent: QWidget, option: Any, index: Any) -> QWidget:  # noqa: N802
        if index.column() == 0:
            return super().createEditor(parent, option, index)
        r, c = index.row(), index.column()
        cb = QComboBox(parent)
        cb.setFont(self.panel.fuente)
        cb.setStyleSheet(estilo_combo())
        actual = self.panel.dato_actual(r, c)
        for dato, texto in self.panel.opciones(r, c):
            cb.addItem(texto, dato)
        cb.view().setMinimumWidth(max(QFontMetrics(self.panel.fuente).horizontalAdvance(cb.itemText(i)) for i in range(cb.count())) + 36)  # la lista enseña el texto entero aunque la celda sea estrecha
        cb.setCurrentIndex(max(0, next((i for i in range(cb.count()) if _igual(cb.itemData(i), actual)), 0)))

        def elegido(_: int = 0) -> None:
            QTimer.singleShot(0, lambda: self.closeEditor.emit(cb))  # primero se cierra, luego se rehace la tabla
            self.panel.elegir(r, c, cb.currentData())
        cb.activated.connect(elegido)
        QTimer.singleShot(0, cb.showPopup)
        return cb

    def setEditorData(self, editor: QWidget, index: Any) -> None:  # noqa: N802
        if index.column() == 0:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: Any, index: Any) -> None:  # noqa: N802
        if index.column() == 0:
            super().setModelData(editor, model, index)


class _Tabla(QTableWidget):
    def sizeHint(self):  # noqa: N802
        tam = super().sizeHint()
        return QSize(tam.width(), getattr(self, "alto_filas", tam.height()))

    """La tabla de variables. Supr, con la tabla enfocada y sin una celda en edición, pide quitar las filas seleccionadas;
    con el editor de una celda abierto, Supr es del editor (borra texto)."""

    suprimir = Signal()

    def _es_supr(self, ev: Any) -> bool:
        solo = (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier)  # el Supr del teclado numérico lleva el segundo
        return (ev.key() == Qt.Key.Key_Delete and ev.modifiers() in solo
                and self.state() != QAbstractItemView.State.EditingState)

    def event(self, ev: Any) -> bool:  # noqa: N802
        # Supr es también el atajo «Borrar la selección» de la ventana (el dibujo): con el foco aquí es de la tabla
        if ev.type() == QEvent.Type.ShortcutOverride and self._es_supr(ev):
            ev.accept()
            return True
        return super().event(ev)

    def keyPressEvent(self, ev: Any) -> None:  # noqa: N802
        if self._es_supr(ev):
            ev.accept()
            self.suprimir.emit()
            return
        super().keyPressEvent(ev)


def _igual(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return _clave_tipo(a) == _clave_tipo(b)
    return a == b


class _Aviso(QLabel):
    """El aviso de debajo de la tabla: solo se ve (y solo ocupa alto) cuando tiene texto."""

    def setText(self, texto: str) -> None:  # noqa: N802
        super().setText(texto)
        self.setVisible(bool(texto))


class PanelVariables(QWidget):
    detalle = Signal(str)  # la línea de detalle de la fila actual (nombre entero, papel y tipo): la ventana la pone en su barra de estado

    def __init__(self) -> None:
        super().__init__()
        self.e: Any = None
        self._e_vista: Any = None
        self._filas: list[dict[str, Any]] = []  # una por fila: {id, papel, tipo, n}; id es None en las que no tienen nombre
        self._pend: list[dict[str, Any]] = []   # las filas sin nombre (solo de la interfaz)
        self._n = 0
        self._clave = ""
        self._llenando = False
        self.contexto = ContextoNombres()  # los nombres de la tabla: partidos por los «_», nunca dos que se lean igual
        self.completo = False  # «Papel» y «Tipo» en palabras (hay sitio con el nombre en sus 96 px) o abreviados («Entr.», «Bool.»): `ReparteColumnas`
        self.parpadeo = Parpadeo(self)  # la fila que parpadea en naranja tras un error
        self.parpadeo.cambia.connect(self._pintar)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabla = _Tabla(0, len(COLUMNAS))
        self.tabla.setHorizontalHeader(CabeceraCompacta(Qt.Orientation.Horizontal, self.tabla))  # (su texto, sin márgenes de más: «Nombre» entero)
        self.tabla.suprimir.connect(self.quitar_seleccion)
        self.tabla.setStyleSheet(self._hoja_tabla())
        self.fuente = QFont(estilo.FUENTE)  # (con la familia explícita: al medir, la tabla aún no tiene la letra de la hoja de estilo)
        self.fuente.setPixelSize(estilo.T_PEQUENA)  # letra algo menor: el panel es estrecho
        self.tabla.setFont(self.fuente)
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(self._alto_fila())  # filas de 26 px (30 a pantalla completa): caben cinco con sus botones a 1366×768 y Propiedades abierto
        self.tabla.verticalHeader().setMinimumSectionSize(self._alto_fila())  # (un nombre partido en dos o tres líneas hace crecer su fila: `_alturas_filas`)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        cab = self.tabla.horizontalHeader()
        cab.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cab.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # el nombre se lleva lo que sobra (`ReparteColumnas` le da, como poco, sus 96 px)
        cab.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # Papel y Tipo, enteros o abreviados («Entr.», «Bool.»): lo justo (se fija abajo)
        cab.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._anchos_columnas()
        cab.setMinimumSectionSize(20)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # los nombres largos se elidén; si ni así cabe, barra
        self.tabla.setMinimumWidth(168)  # por debajo, el panel que la contiene se desplaza en vez de aplastar las columnas
        self.tabla.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # (el delegado ya elide el nombre conservando lo que lo distingue)
        self.tabla.setItemDelegate(_DelegadoCombo(self))
        self.tabla.setMouseTracking(True)  # pasar el ratón por una fila pone su nombre entero en la línea de detalle
        self.tabla.entered.connect(lambda indice: self._detallar(indice.row()))
        self.tabla.viewport().installEventFilter(self)
        self.tabla.clicked.connect(self._clic)
        self.tabla.setMinimumHeight(24)
        self.tabla.itemChanged.connect(self._editado)
        self.tabla.currentCellChanged.connect(lambda fila, *_: self._detallar(fila))
        self.tabla.horizontalHeader().geometriesChanged.connect(self._ajustar_tabla)
        self.ancho_nominal = 0  # el ancho útil de la tabla con el panel como se abre (lo pone la ventana con el ancho de sus paneles laterales); 0: el de ahora
        self.reparto = ReparteColumnas(self.tabla, 0, NOMBRE_MIN, self._planes, self._elegir_plan, self._ajustar_tabla,
                                       lambda: self.ancho_nominal or self.tabla.viewport().width())
        lay.addWidget(self.tabla)
        cont = self.cont = QWidget()
        cont.setStyleSheet(self._hoja_botones())
        fila = QGridLayout(cont)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(estilo.E1)
        fila.setColumnStretch(0, 1)
        fila.setColumnStretch(1, 1)
        self.b_nuevas: dict[str, QPushButton] = {}
        for papel, texto, tip in (("input", "+ Entrada", "Nueva entrada"), ("output", "+ Salida", "Nueva salida"),
                                  ("internal", "+ Memoria", "Nueva memoria")):
            b = QPushButton(texto)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, p=papel: self.nueva(p))
            self.b_nuevas[papel] = b
        self.b_quitar = QPushButton("Eliminar")
        self.b_quitar.setToolTip("Solo si no se usa en ninguna receptividad ni acción")
        self.b_quitar.clicked.connect(self.quitar)
        for i, b in enumerate((*self.b_nuevas.values(), self.b_quitar)):  # botones de la hoja global: 36 px de alto, texto entero
            b.setMinimumWidth(self._ancho_boton(b.text()))
            b.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
            fila.addWidget(b, i // 2, i % 2)
        lay.addWidget(cont)
        self.msg = _Aviso()  # sin texto no ocupa alto: así con Propiedades abierto a 1366×768 el panel no necesita barra por fuera
        self.msg.setWordWrap(True)
        self.msg.hide()
        lay.addWidget(self.msg)
        lay.addStretch(1)

    @staticmethod
    def _alto_fila() -> int:
        return estilo.ALTO_FILA_COMPACTA - 2

    @staticmethod
    def _hoja_botones() -> str:
        """Los botones de este panel miden 32 px (36 a pantalla completa): con Propiedades abierto, a 1366×768, el panel de
        Variables no tiene alto para los de 36 de la hoja global y se le pondría una barra de desplazamiento por fuera."""
        alto = estilo.ALTO_CONTROL_COMPACTO
        return (f"QPushButton {{ min-height: {alto - 2}px; }} "
                f"QPushButton[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; min-height: {alto - 4}px; padding: 0 11px; }}")

    @staticmethod
    def _hoja_tabla() -> str:
        # (sin marco propio: los 4 px del marco transparente de la hoja global son del nombre; el anillo de foco sale con el teclado)
        # (el editor de una celda —el nombre, la lista de papel o de tipo— no pasa del alto de su fila: con los 32 px de la hoja global se salía por abajo y,
        # en la última fila, el visor de la tabla le cortaba el marco de foco)
        return (f"QHeaderView::section {{ padding: 4px 4px; text-align: left; }} QTableWidget {{ font-size: {estilo.T_PEQUENA}px; border: 0; }} "
                f"QTableWidget QLineEdit, QTableWidget QComboBox {{ min-height: 0; padding-top: 0; padding-bottom: 0; }} "
                f"QTableWidget[tecl=\"true\"]:focus {{ border: 2px dashed {estilo.FOCO}; }}")

    def _planes(self) -> list[dict[str, Any]]:
        """Los dos repartos de las columnas, del más completo al más compacto: «Papel» y «Tipo» en palabras («Entrada», «Booleana»: miden lo que su
        texto más largo o su cabecera) y abreviados («Entr.», «Bool.»). El nombre manda: `ReparteColumnas` elige el primero que le deja
        sus 96 px, así que las palabras enteras salen donde caben (a pantalla completa, o con el panel ensanchado) y las abreviaturas donde no."""
        fm = QFontMetrics(self.fuente)

        def ancho(textos: list[str], cabecera: str, forma: Any) -> int:  # (el texto más los 3 px de margen de la celda a cada lado, y 2 px de holgura)
            return max([fm.horizontalAdvance(forma(t)) + 8 for t in textos] + [fm.horizontalAdvance(cabecera) + 8])
        papeles, tipos = [t for _, t in PAPELES], [t for _, t in TIPOS]
        return [{"anchos": {1: ancho(papeles, "Papel", str), 2: ancho(tipos, "Tipo", str)}, "completo": True},
                {"anchos": {1: ancho(papeles, "Papel", abreviar_papel), 2: ancho(tipos, "Tipo", abreviar_tipo)}, "completo": False}]

    def _elegir_plan(self, plan: dict[str, Any]) -> None:
        self.completo = plan["completo"]

    def fijar_ancho_nominal(self, ancho_panel: int) -> None:
        """El ancho de los paneles laterales (lo da la ventana): con él se decide si «Papel» y «Tipo» van en palabras (a pantalla completa) o
        abreviados; ensanchar el panel a mano solo da más ancho al nombre."""
        nuevo = max(0, ancho_panel - 30)  # (los márgenes del panel, el marco de la tabla y su barra vertical)
        if nuevo != self.ancho_nominal:
            self.ancho_nominal = nuevo
            self.reparto.aplicar()

    def _anchos_columnas(self) -> None:
        """Papel y Tipo, al principio y al cambiar la letra: los anchos de las abreviaturas (que es lo que cabe a 1366) y, si ya se ha repartido el
        ancho de la tabla, el reparto de verdad."""
        anchos = self._planes()[1]["anchos"]
        self.tabla.setColumnWidth(1, anchos[1])
        self.tabla.setColumnWidth(2, anchos[2])
        reparto = getattr(self, "reparto", None)
        if reparto is not None:
            reparto.aplicar()

    def eventFilter(self, objeto: Any, evento: Any) -> bool:  # noqa: N802
        if objeto is self.tabla.viewport() and evento.type() == QEvent.Type.Leave:
            self._detallar(self.tabla.currentRow())  # el ratón se va: vuelve el detalle de la fila elegida (o nada)
        return False

    def escalar(self) -> None:
        """Cambió la escala de letra y de controles: la tabla (letra, alto de fila, columnas) y los botones se miden otra vez."""
        self.tabla.setStyleSheet(self._hoja_tabla())
        self.fuente.setPixelSize(estilo.T_PEQUENA)
        self.tabla.setFont(self.fuente)
        self.tabla.verticalHeader().setDefaultSectionSize(self._alto_fila())
        self.tabla.verticalHeader().setMinimumSectionSize(self._alto_fila())
        self.cont.setStyleSheet(self._hoja_botones())
        self._anchos_columnas()
        self.contexto._cache.clear()
        for b in (*self.b_nuevas.values(), self.b_quitar):
            b.setMinimumWidth(self._ancho_boton(b.text()))
        self._ajustar_tabla()

    @staticmethod
    def _ancho_boton(texto: str) -> int:
        """Lo que mide un botón de la hoja global con ese texto (su letra explícita, no la de la plataforma) y su relleno."""
        return QFontMetrics(estilo.fuente()).horizontalAdvance(texto) + 24

    # -- la tabla ---------------------------------------------------------------------------------
    @staticmethod
    def _clave_fila(f: dict[str, Any]) -> str:
        return f["id"] or f"sin-nombre:{f['n']}"

    def mostrar(self, e: Any) -> None:
        """Rellena la tabla con las variables del modelo en curso y, al final, las filas sin nombre (si no se está
        escribiendo en ella)."""
        if e is not self._e_vista:  # otra edición: las filas sin nombre de la anterior no cuentan
            self._e_vista, self._pend, self._clave = e, [], ""
        self.e = e
        if e is None or self.tabla.state() == QAbstractItemView.State.EditingState:
            return
        vs = e.variables()
        clave = repr([(v["id"], v["name"], v["role"], v["type"]) for v in vs]
                     + [(f["n"], f["papel"], f["tipo"]) for f in self._pend])
        if clave == self._clave:  # nada cambió: no se rehace la tabla (se hace en cada clic del dibujo)
            return
        self._clave = clave
        actual = self._filas[self.tabla.currentRow()]["id"] if 0 <= self.tabla.currentRow() < len(self._filas) else None
        self._llenando = True
        self.contexto.fijar([v["name"] for v in vs])
        self._filas = [{"id": v["id"], "papel": v["role"], "tipo": v["type"], "n": 0} for v in vs] + self._pend
        self.tabla.setRowCount(len(self._filas))
        for r, f in enumerate(self._filas):
            nombre = next((v["name"] for v in vs if v["id"] == f["id"]), "")
            self.tabla.setItem(r, 0, QTableWidgetItem(nombre))
            self.tabla.item(r, 0).setToolTip(nombre)  # el nombre entero, aunque la celda lo elida
            for c in (1, 2):
                it = QTableWidgetItem(self.texto(r, c))
                it.setToolTip(f"{it.text()} · clic para cambiarlo")  # (la celda lo enseña abreviado: aquí va entero)
                self.tabla.setItem(r, c, it)
        self._llenando = False
        if actual is not None and actual in [f["id"] for f in self._filas]:
            self.tabla.selectRow([f["id"] for f in self._filas].index(actual))
        self._ajustar_tabla()
        self._pintar()

    def _detallar(self, fila: int) -> None:
        """Con una fila elegida (con el ratón o con las flechas), su nombre entero, papel y tipo: así un nombre elidido se lee sin
        pasar el ratón por encima."""
        if 0 <= fila < len(self._filas) and self._filas[fila]["id"] is not None and self.tabla.item(fila, 0) is not None:
            self.detalle.emit(" · ".join(self.tabla.item(fila, c).text() for c in range(3)))
        else:
            self.detalle.emit("")

    def _alturas_filas(self) -> None:
        """Cada fila mide su alto de siempre (26 px, 30 a pantalla completa) y, si su nombre va partido en varias líneas, lo que miden sus líneas más un
        poco de aire: con otro ancho de columna, otra vez."""
        t, d = self.tabla, self.tabla.itemDelegate()
        opcion = QStyleOptionViewItem()
        opcion.initFrom(t.viewport())
        opcion.font = t.font()
        opcion.rect.setSize(QSize(t.columnWidth(0) - (1 if t.showGrid() else 0), self._alto_fila()))  # (la celda mide 1 px menos que la columna: la línea de la rejilla)
        for r in range(t.rowCount()):
            alto = d.sizeHint(opcion, t.model().index(r, 0)).height()
            if t.rowHeight(r) != alto:
                t.setRowHeight(r, alto)

    alto_maximo = 320  # lo más alto que mide la tabla (con más filas, se desplaza ella); la ventana lo baja si el panel es bajo (`fijar_alto_maximo`)

    def fijar_alto_maximo(self, px: int) -> None:
        """F10: con el panel bajo, la tabla mide como mucho lo que deja el panel: ella se desplaza y el panel no (una sola barra vertical).
        Nunca menos de unas tres filas ni más de 320 px."""
        nuevo = max(min(px, 320), 3 * self._alto_fila() + self.tabla.horizontalHeader().height() + 2 * self.tabla.frameWidth())
        if nuevo != self.alto_maximo:
            self.alto_maximo = nuevo
            self._ajustar_tabla()

    def _ajustar_tabla(self):
        self._alturas_filas()
        alto = min(self.alto_maximo, self.tabla.horizontalHeader().height()
                   + sum(self.tabla.rowHeight(r) for r in range(self.tabla.rowCount()))
                   + 2 * self.tabla.frameWidth()
                   + (self.tabla.horizontalScrollBar().height() if self.tabla.horizontalScrollBar().isVisible() else 0))
        if alto != getattr(self.tabla, "alto_filas", None):
            self.tabla.alto_filas = alto
            self.tabla.setFixedHeight(alto)
            self.tabla.updateGeometry()

    def texto(self, r: int, c: int) -> str:
        """Lo que se ve en la celda de la fila r: el papel o el tipo en palabras."""
        f = self._filas[r]
        return dict(PAPELES).get(f["papel"], f["papel"]) if c == 1 else nombre_tipo(f["tipo"])

    def dato_actual(self, r: int, c: int) -> Any:
        f = self._filas[r]
        return f["papel"] if c == 1 else f["tipo"]

    def opciones(self, r: int, c: int) -> list[tuple[Any, str]]:
        """Lo que se puede elegir en la celda: los papeles; los tres tipos y, antes, el de un fichero antiguo si lo tiene
        (se ve, pero elegirlo no cambia nada)."""
        if c == 1:
            return [(clave, texto) for clave, texto in PAPELES]
        out = [(t, texto) for t, texto in TIPOS]
        actual = self._filas[r]["tipo"]
        if not any(_clave_tipo(t) == _clave_tipo(actual) for t, _ in TIPOS):
            out.insert(0, (actual, nombre_tipo(actual)))
        return out

    def elegir(self, r: int, c: int, dato: Any) -> None:
        """Se eligió un papel o un tipo en la fila r (una operación de deshacer)."""
        if not 0 <= r < len(self._filas):
            return
        f = self._filas[r]
        if c == 1:
            self._cambiar(f, role=dato)
        else:
            self._cambiar_tipo(f, dato)
        self._diferir(self._reconstruir)

    def _clic(self, index: Any) -> None:
        if index.column() in (1, 2):
            self.tabla.editItem(self.tabla.item(index.row(), index.column()))

    # -- parpadeo ---------------------------------------------------------------------------------
    def parpadear(self, *filas: dict[str, Any]) -> None:
        """Las filas parpadean en naranja y la primera se lleva a la vista."""
        self.parpadeo.iniciar([self._clave_fila(f) for f in filas])
        if filas[0] in self._filas and self.tabla.item(self._filas.index(filas[0]), 0) is not None:
            self.tabla.scrollToItem(self.tabla.item(self._filas.index(filas[0]), 0))

    def _pintar(self) -> None:
        """Colorea de naranja la fila que parpadea mientras dura la fase encendida."""
        activos = self.parpadeo.activos()
        self._llenando = True  # cambiar el fondo de una celda también avisa de «celda cambiada»
        for r, f in enumerate(self._filas):
            on = self._clave_fila(f) in activos
            for c in range(3):
                it = self.tabla.item(r, c)
                if it is not None:
                    it.setBackground(QBrush(QColor(NARANJA)) if on else QBrush())
        self._llenando = False

    # -- cambios ------------------------------------------------------------------------------------
    def _diferir(self, fn: Any) -> None:
        """Hacerlo ya, o cuando acabe la edición en curso de una celda (no se rehace la tabla bajo el editor abierto)."""
        if self.tabla.state() == QAbstractItemView.State.EditingState:
            QTimer.singleShot(0, fn)
        else:
            fn()

    def _reconstruir(self) -> None:
        self._clave = ""
        self.mostrar(self.e)

    def _resultado(self, motivo: str | None, f: dict[str, Any] | None = None) -> None:
        self.msg.setText(motivo or "")
        self.msg.setStyleSheet(f"color: {COL['err']}" if motivo else "")
        if motivo:  # la fila parpadea y la tabla vuelve a lo que hay en el modelo
            if f is not None:
                self.parpadear(f)
            self._diferir(self._reconstruir)

    def _cambiar(self, f: dict[str, Any], **cambios: Any) -> None:
        if f["id"] is None:  # sin nombre: solo se recuerda para cuando se cree
            f["papel"] = cambios.get("role", f["papel"])
            self._clave = ""
            return
        self._resultado(self.e.cambiar_variable(f["id"], **cambios), f)

    def _cambiar_tipo(self, f: dict[str, Any], tipo: dict[str, Any]) -> None:
        if _clave_tipo(tipo) == _clave_tipo(f["tipo"]):
            return  # el que ya tiene (también el de un fichero antiguo)
        if f["id"] is None:
            f["tipo"] = dict(tipo)
            self._clave = ""
            return
        # al cambiar de tipo, el valor inicial vuelve a 0 (cambiar_variable lo hace siempre)
        self._resultado(self.e.cambiar_variable(f["id"], type=dict(tipo)), f)

    def _editado(self, it: QTableWidgetItem) -> None:
        if self._llenando or self.e is None or it.column() != 0 or not 0 <= it.row() < len(self._filas):
            return
        f, texto = self._filas[it.row()], it.text().strip()
        if f["id"] is not None:
            self._resultado(self.e.cambiar_variable(f["id"], nombre=texto), f)
            return
        if not texto:  # sigue sin nombre
            return
        pos = self._pend.index(f)
        self._pend.remove(f)  # se crea en el modelo: deja de ser una fila de la interfaz
        motivo = self.e.nueva_variable(texto, f["papel"], dict(f["tipo"]))
        if motivo is None:
            f["id"] = next(v["id"] for v in self.e.ed.model["variables"] if v["name"] == texto)
            self._resultado(None)
            return
        self._pend.insert(pos, f)
        self.msg.setText(motivo)
        self.msg.setStyleSheet(f"color: {COL['err']}")
        self.parpadear(f)
        self._diferir(lambda: self._en_blanco(f))

    def _en_blanco(self, f: dict[str, Any]) -> None:
        """La fila rechazada vuelve a quedar en blanco, con el cursor en el nombre."""
        if f not in self._filas:
            return
        r = self._filas.index(f)
        self._llenando = True
        self.tabla.item(r, 0).setText("")
        self._llenando = False
        if self.isVisible():
            self.tabla.editItem(self.tabla.item(r, 0))

    # -- botones y comprobaciones ----------------------------------------------------------------------
    def nueva(self, papel: str = "input") -> None:
        """Una fila sin nombre (booleana, con el papel dado: entrada por omisión), con el cursor en el nombre; la variable no existe en el modelo hasta
        que se escribe un nombre válido."""
        self._n += 1
        f = {"id": None, "papel": papel, "tipo": {"kind": "bool"}, "n": self._n}
        self._pend.append(f)
        self.msg.setText("")
        self.msg.setStyleSheet("")
        self._reconstruir()
        self.tabla.selectRow(self.tabla.rowCount() - 1)
        if self.isVisible():  # se escribe el nombre directamente
            self.tabla.setFocus()
            self.tabla.editItem(self.tabla.item(self.tabla.rowCount() - 1, 0))

    def quitar(self) -> None:
        """El botón «Quitar»: la variable de la fila actual."""
        r = self.tabla.currentRow()
        if 0 <= r < len(self._filas):
            self._quitar_filas([self._filas[r]])

    def quitar_seleccion(self) -> None:
        """Supr: las variables de las filas seleccionadas, como si se pulsara «Quitar» en cada una (mismas comprobaciones,
        mismos avisos). Solo al editar: sin edición o con el panel desactivado no hace nada."""
        if self.e is None or not self.isEnabled():
            return
        filas = sorted({i.row() for i in self.tabla.selectionModel().selectedRows()})
        self._quitar_filas([self._filas[r] for r in filas if 0 <= r < len(self._filas)])

    def _quitar_filas(self, filas: list[dict[str, Any]]) -> None:
        """Quita cada fila: una sin nombre solo sale de la interfaz; una variable pasa por el núcleo, que rechaza la que está
        en uso (se muestra su motivo y la fila parpadea; si son varias las rechazadas, el motivo es el de la primera)."""
        rechazadas: list[tuple[dict[str, Any], str]] = []
        sin_nombre = False
        for f in filas:
            if f["id"] is None:  # sin nombre: no está en el modelo, solo se quita la fila
                self._pend.remove(f)
                sin_nombre = True
            else:
                motivo = self.e.quitar_variable(f["id"])
                if motivo:
                    rechazadas.append((f, motivo))
        if rechazadas:
            self._resultado(rechazadas[0][1], rechazadas[0][0])
            if len(rechazadas) > 1:
                self.parpadear(*(f for f, _ in rechazadas))
        else:
            self._resultado(None)
        if sin_nombre:
            self._reconstruir()

    def sin_nombre(self) -> int:
        """Cuántas filas siguen sin nombre."""
        return len(self._pend)

    def avisar_sin_nombre(self) -> str:
        """Muestra el aviso de que hay una variable sin nombre y hace parpadear la primera; devuelve el aviso."""
        self.msg.setText(SIN_NOMBRE)
        self.msg.setStyleSheet(f"color: {COL['err']}")
        if self._pend:
            self.parpadear(*self._pend)
        return SIN_NOMBRE
