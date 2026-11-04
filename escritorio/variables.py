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

from PySide6.QtCore import QEvent, QTimer, Qt, Signal, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHeaderView, QLabel, QPushButton, QGridLayout, QSizePolicy,
                               QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .diagrama import COL
from .edicion import Parpadeo

PAPELES = (("input", "Entrada"), ("output", "Salida"), ("internal", "Memoria"))
# Los tipos que se ofrecen. Un fichero antiguo puede traer otros (decimal de 1 o 3 decimales, duración): se muestran con
# su tipo y siguen funcionando, pero si se cambia el tipo solo se elige entre estos.
TIPOS = (({"kind": "bool"}, "Booleana"), ({"kind": "int"}, "Entera"), ({"kind": "decimal", "scale": 2}, "Decimal (2)"))
COLUMNAS = ["Nombre", "Papel", "Tipo"]
SIN_NOMBRE = "Hay una variable sin nombre: escríbale un nombre o quítela"
NARANJA = "#ffd2ad"
ESTILO_COMBO = "QComboBox { padding: 0px 1px 0px 3px; } QComboBox::drop-down { width: 11px; }"


def _clave_tipo(t: dict[str, Any]) -> tuple[Any, ...]:
    return (t.get("kind"), str(t.get("scale")) if t.get("kind") == "decimal" else None)


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

    def createEditor(self, parent: QWidget, option: Any, index: Any) -> QWidget:  # noqa: N802
        if index.column() == 0:
            return super().createEditor(parent, option, index)
        r, c = index.row(), index.column()
        cb = QComboBox(parent)
        cb.setFont(self.panel.fuente)
        cb.setStyleSheet(ESTILO_COMBO)
        actual = self.panel.dato_actual(r, c)
        for dato, texto in self.panel.opciones(r, c):
            cb.addItem(texto, dato)
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


class PanelVariables(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.e: Any = None
        self._e_vista: Any = None
        self._filas: list[dict[str, Any]] = []  # una por fila: {id, papel, tipo, n}; id es None en las que no tienen nombre
        self._pend: list[dict[str, Any]] = []   # las filas sin nombre (solo de la interfaz)
        self._n = 0
        self._clave = ""
        self._llenando = False
        self.parpadeo = Parpadeo(self)  # la fila que parpadea en naranja tras un error
        self.parpadeo.cambia.connect(self._pintar)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabla = _Tabla(0, len(COLUMNAS))
        self.tabla.suprimir.connect(self.quitar_seleccion)
        self.tabla.setStyleSheet("QHeaderView::section { padding: 2px 3px; }")
        self.fuente = QFont(self.tabla.font())  # letra pequeña: el panel es estrecho
        self.fuente.setPixelSize(11)
        self.tabla.setFont(self.fuente)
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(20)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # el nombre se lleva lo que sobra
        cab.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # Papel y Tipo, a su texto más largo (se fija abajo)
        cab.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        fm = QFontMetrics(self.fuente)
        self.tabla.setColumnWidth(1, max(fm.horizontalAdvance(t) for _, t in PAPELES + (("", "Papel"),)) + 8)
        self.tabla.setColumnWidth(2, max(fm.horizontalAdvance(t) for _, t in TIPOS + (({}, "Tipo"),)) + 8)
        cab.setMinimumSectionSize(20)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # los nombres largos se elidén
        self.tabla.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tabla.setItemDelegate(_DelegadoCombo(self))
        self.tabla.clicked.connect(self._clic)
        self.tabla.setMinimumHeight(24)
        self.tabla.itemChanged.connect(self._editado)
        self.tabla.horizontalHeader().geometriesChanged.connect(self._ajustar_tabla)
        lay.addWidget(self.tabla)
        cont = QWidget()
        fila = QGridLayout(cont)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(3)
        fila.setColumnStretch(0, 1)
        fila.setColumnStretch(1, 1)
        fm = QFontMetrics(self.fuente)
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
        for i, b in enumerate((*self.b_nuevas.values(), self.b_quitar)):
            b.setFont(self.fuente)
            b.setMinimumWidth(fm.horizontalAdvance(b.text()) + 16)
            b.setStyleSheet("QPushButton { padding: 4px 6px; min-width: 0px; }")
            b.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
            fila.addWidget(b, i // 2, i % 2)
        lay.addWidget(cont)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addStretch(1)

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
        self._filas = [{"id": v["id"], "papel": v["role"], "tipo": v["type"], "n": 0} for v in vs] + self._pend
        self.tabla.setRowCount(len(self._filas))
        for r, f in enumerate(self._filas):
            nombre = next((v["name"] for v in vs if v["id"] == f["id"]), "")
            self.tabla.setItem(r, 0, QTableWidgetItem(nombre))
            self.tabla.item(r, 0).setToolTip(nombre)  # el nombre entero, aunque la celda lo elida
            for c in (1, 2):
                it = QTableWidgetItem(self.texto(r, c))
                it.setToolTip("Clic para cambiarlo")
                self.tabla.setItem(r, c, it)
        self._llenando = False
        if actual is not None and actual in [f["id"] for f in self._filas]:
            self.tabla.selectRow([f["id"] for f in self._filas].index(actual))
        self._ajustar_tabla()
        self._pintar()

    def _ajustar_tabla(self):
        alto = min(320, self.tabla.horizontalHeader().height()
                   + sum(self.tabla.rowHeight(r) for r in range(self.tabla.rowCount()))
                   + 2 * self.tabla.frameWidth())
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
        v = next(x for x in self.e.ed.model["variables"] if x["id"] == f["id"])
        inicial = {"bool": False}.get(tipo["kind"], "0")  # al cambiar de tipo, el valor inicial vuelve a 0
        self._resultado(self.e.cambiar_variable(f["id"], type=dict(tipo),
                                                **({"initialValue": inicial} if v["role"] == "input" else {})), f)

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
