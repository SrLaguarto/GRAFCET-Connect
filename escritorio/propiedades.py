"""Paleta de elementos y panel de propiedades del editor (P-IMP-32).

La paleta (izquierda, arriba) elige la herramienta con un clic y coloca el elemento si se arrastra al dibujo. El
panel de propiedades (izquierda, abajo) muestra las opciones del elemento seleccionado: una etapa, su etiqueta y su
tipo; una transición, su etiqueta, si se dibuja, y su receptividad con botones para no tener que escribir la
sintaxis (flancos, negación, y, o, paréntesis, variables, etapas, comparaciones y temporizadores). Las variables
que no existen se ven en naranja. Todo lo que cambia lo hace con las operaciones de Edicion / grafcet/editor.py.
"""
from __future__ import annotations

import html
import re
from typing import Any

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QLabel,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from grafcet.routing import TALLO_E, TALLO_T
from grafcet.view import norm

from .bloques import FlowLayout, Programador
from .diagrama import COL, H, TB, _html
from .edicion import HERRAMIENTAS

NARANJA = COL["glow"]
NOMBRES = {"etapa": "Etapa", "transicion": "Transición", "simultaneidad": "Simultaneidad"}
AYUDAS = {"etapa": "Etapa: arrástrela al dibujo", "transicion": "Transición: arrástrela al dibujo",
          "simultaneidad": "Barra de simultaneidad (doble trazo, Y): une varias etapas a una transición, o una transición "
                           "a varias etapas. Se ensancha estirando de sus extremos. Las alternativas (O) no son un elemento: "
                           "se construyen con el ratón enlazando una etapa con una segunda transición, o arrastrando a un enlace."}
COLOCABLES = tuple(NOMBRES)  # sin «Seleccionar»: por defecto el ratón selecciona, mueve y enlaza


def icono(h: str) -> QIcon:
    """Dibujo del elemento, para reconocerlo en la paleta (con el trazo de la norma: etapa cuadrada, transición, barras)."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(COL["text"]), 2))
    if h == "etapa":
        p.drawLine(32, 2, 32, 14)
        p.drawRect(QRectF(16, 14, 32, 32))
        p.drawLine(32, 46, 32, 62)
    elif h == "transicion":
        p.drawLine(32, 2, 32, 62)
        p.setPen(QPen(QColor(COL["text"]), 4))
        p.drawLine(20, 32, 44, 32)
    else:
        p.drawLine(16, 2, 16, 26)
        p.drawLine(48, 2, 48, 26)
        p.drawLine(4, 28, 60, 28)
        if h == "simultaneidad":
            p.drawLine(4, 34, 60, 34)
        p.drawLine(32, 36 if h == "simultaneidad" else 30, 32, 62)
    p.end()
    return QIcon(pm)


def figura(h: str, escala: float = 1.0, dpr: float = 1.0) -> tuple[QPixmap, QPoint]:
    """El elemento tal como quedará en el dibujo, al zoom del dibujo, para llevarlo pegado al puntero al arrastrarlo
    desde la paleta, y el punto que va bajo el puntero: el que se coloca donde se suelta (el centro de la etapa o de la
    transición; el centro del trazo superior de la barra)."""
    m = 4  # margen, en píxeles
    if h == "etapa":
        w, alto, cx, cy = 2 * H, 2 * H + 2 * TALLO_E, H, TALLO_E + H
    elif h == "transicion":
        w, alto, cx, cy = 2 * TB, 2 * TALLO_T, TB, TALLO_T
    else:
        w, alto, cx, cy = 120, 4 + 2 * TALLO_E, 60, TALLO_E
    pm = QPixmap(round((w * escala + 2 * m) * dpr), round((alto * escala + 2 * m) * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(0.85)
    p.translate(m, m)
    p.scale(escala, escala)
    p.setPen(QPen(QColor(COL["text"]), 1.6))
    if h == "etapa":
        p.fillRect(QRectF(0, TALLO_E, 2 * H, 2 * H), QColor(COL["accent_soft"]))
        p.drawRect(QRectF(0, TALLO_E, 2 * H, 2 * H))
        p.drawLine(QPointF(H, 0), QPointF(H, TALLO_E))
        p.drawLine(QPointF(H, TALLO_E + 2 * H), QPointF(H, alto))
    elif h == "transicion":
        p.drawLine(QPointF(TB, 0), QPointF(TB, alto))
        p.setPen(QPen(QColor(COL["muted"]), 2.4))
        p.drawLine(QPointF(0, TALLO_T), QPointF(2 * TB, TALLO_T))
    else:
        for x in (30, 90):
            p.drawLine(QPointF(x, 0), QPointF(x, TALLO_E))
        p.drawLine(QPointF(0, TALLO_E), QPointF(120, TALLO_E))
        p.drawLine(QPointF(0, TALLO_E + 4), QPointF(120, TALLO_E + 4))
        p.drawLine(QPointF(60, TALLO_E + 4), QPointF(60, alto))
    p.end()
    return pm, QPoint(round(cx * escala + m), round(cy * escala + m))


class Paleta(QListWidget):
    """Elementos del grafcet. Se arrastran al dibujo, o se hace clic y después en el lienzo (una vez)."""

    elegida = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.setViewMode(QListView.ViewMode.IconMode)  # iconos grandes con su nombre: se ven y se arrastran
        self.setIconSize(QSize(56, 56))
        self.setGridSize(QSize(92, 96))
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        for h in COLOCABLES:
            it = QListWidgetItem(icono(h), NOMBRES[h])
            it.setData(Qt.ItemDataRole.UserRole, h)
            it.setToolTip(AYUDAS[h])
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.addItem(it)
        self.setCurrentRow(-1)
        self.currentItemChanged.connect(lambda it, _: it and self.elegida.emit(it.data(Qt.ItemDataRole.UserRole)))
        self.setMaximumHeight(210)

    escala = staticmethod(lambda: 1.0)  # zoom del dibujo; lo pone la ventana

    def startDrag(self, actions: Any) -> None:  # noqa: N802
        """Se arrastra el elemento mismo, al tamaño con que se verá en el dibujo, no el icono de la lista."""
        it = self.currentItem()
        if it is None:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData([it]))
        pm, punto = figura(it.data(Qt.ItemDataRole.UserRole), self.escala(), self.devicePixelRatioF())
        drag.setPixmap(pm)
        drag.setHotSpot(punto)
        drag.exec(Qt.DropAction.CopyAction)

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:  # noqa: N802
        m = QMimeData()
        m.setText(items[0].data(Qt.ItemDataRole.UserRole))
        return m

    def elegir(self, h: str) -> None:
        """Sincroniza la lista con la herramienta; sin herramienta, nada marcado."""
        fila = next((i for i in range(self.count()) if self.item(i).data(Qt.ItemDataRole.UserRole) == h), -1)
        if self.currentRow() != fila:
            self.blockSignals(True)
            self.setCurrentRow(fila)
            self.blockSignals(False)


def _formulario(w: QWidget) -> QFormLayout:
    """Formulario arriba de la página y que se estrecha: si no cabe, el rótulo va encima del campo."""
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    f = QFormLayout()
    f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    lay.addLayout(f)
    lay.addStretch(1)
    return f


def _desplegable() -> QComboBox:
    """Desplegable que no impone su ancho al panel."""
    c = QComboBox()
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(6)
    return c


class PanelPropiedades(QWidget):
    """Las opciones del elemento seleccionado, con campos editables."""

    def __init__(self) -> None:
        super().__init__()
        self.e: Any = None
        self.ident: str | None = None
        self._llenando = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-weight: 600")
        lay.addWidget(self.titulo)
        self.pila = QStackedWidget()
        lay.addWidget(self.pila, 1)
        self.pila.addWidget(self._vacio())
        self.pila.addWidget(self._etapa())
        self.pila.addWidget(self._transicion())
        self.pila.addWidget(self._enlace())
        self.pila.addWidget(self._barra())
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

    # -- páginas -----------------------------------------------------------------------------------
    def _vacio(self) -> QWidget:
        w = QLabel("Haga clic en un elemento del dibujo para ver y cambiar sus opciones.")
        w.setWordWrap(True)
        w.setAlignment(Qt.AlignmentFlag.AlignTop)
        w.setStyleSheet(f"color: {COL['muted']}")
        return w

    def _etapa(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.s_etiqueta = QLineEdit()
        self.s_etiqueta.editingFinished.connect(lambda: self._renombrar(self.s_etiqueta))
        self.s_tipo = _desplegable()
        self.s_tipo.addItem("Normal", False)
        self.s_tipo.addItem("Inicial", True)
        self.s_tipo.activated.connect(lambda _: self.e.tipo_etapa(self.ident, self.s_tipo.currentData()))
        f.addRow("Etiqueta", self.s_etiqueta)
        f.addRow("Tipo", self.s_tipo)
        f.addRow(QLabel("Acciones"))
        self.s_acciones = QListWidget()
        self.s_acciones.setWordWrap(True)
        self.s_acciones.setMaximumHeight(140)
        self.s_acciones.itemDoubleClicked.connect(lambda it: self._accion(it.data(Qt.ItemDataRole.UserRole)))
        self.s_acciones.currentItemChanged.connect(self._accion_señalada)
        f.addRow(self.s_acciones)
        fila = QWidget()
        fl = FlowLayout(fila)
        for texto, tip, accion in (("Añadir…", "Añadir una acción a la etapa (también con el botón derecho en la etapa)",
                                    lambda: self._accion(None)),
                                   ("Editar…", "Cambiar la acción elegida (o doble clic en ella)", lambda: self._accion(self._elegida())),
                                   ("Quitar", "Quitar la acción elegida", lambda: self._elegida() and self.e.quitar_accion(self._elegida())),
                                   ("◀", "Más a la izquierda en el dibujo", lambda: self._elegida() and self.e.mover_accion(self._elegida(), -1)),
                                   ("▶", "Más a la derecha", lambda: self._elegida() and self.e.mover_accion(self._elegida(), 1))):
            b = QPushButton(texto)
            b.setToolTip(tip)
            b.clicked.connect(accion)
            fl.addWidget(b)
        f.addRow(fila)
        return w

    def _elegida(self) -> str | None:
        it = self.s_acciones.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _accion(self, aid: str | None) -> None:
        if self.e is not None and self.ident:
            self.e.pedir_accion(self.ident, aid)

    def _accion_señalada(self, it: Any, _: Any = None) -> None:
        """Elegir una acción en la lista la resalta en el dibujo."""
        aid = it.data(Qt.ItemDataRole.UserRole) if it else None
        if self.e is not None and aid != self.e.accion and not self._llenando:
            self.e.accion = aid
            self.e.cambiado.emit()

    def _transicion(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.t_etiqueta = QLineEdit()
        self.t_etiqueta.editingFinished.connect(lambda: self._renombrar(self.t_etiqueta))
        self.t_mostrar = QCheckBox("Mostrar etiqueta")
        self.t_mostrar.setToolTip("Dibujar la etiqueta (t1) junto a la transición")
        self.t_mostrar.clicked.connect(lambda on: self.e.mostrar_etiqueta(self.ident, on))
        f.addRow("Etiqueta", self.t_etiqueta)
        f.addRow(self.t_mostrar)
        f.addRow(QLabel("Receptividad (bloques)"))
        self.prog = Programador(lambda: self.e.fuente_bloques() if self.e is not None else ({}, []))
        self.prog.cambiado.connect(self._desde_bloques)
        self.prog.al_deshacer = lambda: self.e is not None and self.e.deshacer()  # Ctrl+Z en la ventana ampliada
        self.prog.al_rehacer = lambda: self.e is not None and self.e.rehacer()
        f.addRow(self.prog)
        self.t_texto = QLineEdit()
        self.t_texto.setPlaceholderText("o escríbala: ↑a AND NOT b, X1, 3s/X1…")
        self.t_texto.textEdited.connect(self._escrito)
        self.t_texto.editingFinished.connect(self._aplicar)
        f.addRow("Texto", self.t_texto)
        self.t_vista = QLabel()
        self.t_vista.setWordWrap(True)
        self.t_vista.setTextFormat(Qt.TextFormat.RichText)
        f.addRow("Escrito", self.t_vista)
        self.t_dibujo = QLabel()
        self.t_dibujo.setTextFormat(Qt.TextFormat.RichText)
        self.t_dibujo.setWordWrap(True)
        f.addRow("Se dibuja", self.t_dibujo)
        self.t_crear = QPushButton("Crear las que faltan")
        self.t_crear.setToolTip("Declarar como entradas booleanas las variables que se usan y no existen")
        self.t_crear.clicked.connect(self._crear)
        f.addRow(self.t_crear)
        return w

    def _desde_bloques(self, texto: str) -> None:
        """Cada cambio en los bloques escribe el texto y se aplica (una operación de deshacer)."""
        self.t_texto.setText(texto)
        self._previsualizar()
        self._aplicar()

    def _escrito(self) -> None:
        self.prog.poner(self.t_texto.text())
        self._previsualizar()

    def _enlace(self) -> QWidget:
        w = QWidget()
        f = QVBoxLayout(w)
        self.l_enlace = QLabel()
        self.l_enlace.setWordWrap(True)
        f.addWidget(self.l_enlace)
        self.f_tipo = QComboBox()
        self.f_tipo.currentIndexChanged.connect(self._elegir_flecha)
        f.addWidget(self.f_tipo)
        self.f_visible = QCheckBox("Mostrar flecha")
        self.f_visible.clicked.connect(lambda on: self.e.ajustar_flecha(visible=on))
        f.addWidget(self.f_visible)
        self.f_auto = QPushButton("Flecha automática")
        self.f_auto.setToolTip("Restablecer la flecha: su sitio y si se ve, como los pone el programa")
        self.f_auto.clicked.connect(lambda: self.e.restablecer_flecha())
        f.addWidget(self.f_auto)
        q = QPushButton("Quitar el enlace")
        q.clicked.connect(lambda: self.e.borrar())
        f.addWidget(q)
        f.addStretch(1)
        return w

    def _elegir_flecha(self) -> None:
        if self.e is not None and self.f_tipo.currentData():
            self.e.flecha = self.f_tipo.currentData()
            self.mostrar(self.e)

    def _barra(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.b_tipo = QLabel("Simultaneidad (doble trazo, Y)")
        self.b_tipo.setWordWrap(True)
        self.b_unidos = QLabel()
        self.b_unidos.setWordWrap(True)
        q = QPushButton("Quitar la barra")
        q.clicked.connect(lambda: self.e.borrar())
        ayuda = QLabel("Arrastre de un extremo para ensancharla; de un punto de unión sale un enlace.")
        ayuda.setWordWrap(True)
        f.addRow("Tipo", self.b_tipo)
        f.addRow("Unidos", self.b_unidos)
        f.addRow(ayuda)
        f.addRow(q)
        return w

    # -- estado ------------------------------------------------------------------------------------
    def mostrar(self, e: Any) -> None:
        """Rellena el panel con el elemento seleccionado (o lo vacía); respeta el campo que se está escribiendo."""
        self.e = e
        sel = e.sel if e is not None else []
        vivo = sel[0] if len(sel) == 1 else None
        kind = ("enlace" if "|" in vivo else
                "barra" if any(b["id"] == vivo for b in e.M.get("bars", [])) else
                "etapa" if any(s["id"] == vivo for s in e.M["steps"]) else
                "transicion" if any(t["id"] == vivo for t in e.M["transitions"]) else None) if vivo else None
        self.ident = vivo if kind else None
        self.titulo.setText({"etapa": f"Etapa {e.nombres.get(vivo)}", "transicion": f"Transición {e.nombres.get(vivo)}",
                             "enlace": f"Enlace {e.nombre(vivo)}" if vivo else "", "barra": e.nombre(vivo) if vivo else "",
                             None: "Propiedades" if len(sel) < 2 else f"{len(sel)} elementos seleccionados"}[kind]
                            if e is not None else "Propiedades")
        self.pila.setCurrentIndex({None: 0, "etapa": 1, "transicion": 2, "enlace": 3, "barra": 4}[kind])
        if kind == "etapa":
            s = next(s for s in e.M["steps"] if s["id"] == vivo)
            self._poner(self.s_etiqueta, s["label"])
            self.s_tipo.setCurrentIndex(1 if s["initial"] else 0)
            self._llenando = True
            self.s_acciones.clear()
            for d in e.acciones(vivo):
                it = QListWidgetItem(e.resumen_accion(d))
                it.setData(Qt.ItemDataRole.UserRole, d["id"])
                self.s_acciones.addItem(it)
                if d["id"] == e.accion:
                    self.s_acciones.setCurrentItem(it)
            if not self.s_acciones.count():
                it = QListWidgetItem("Sin acciones: «Añadir…» o botón derecho en la etapa")
                it.setFlags(Qt.ItemFlag.NoItemFlags)
                self.s_acciones.addItem(it)
            self._llenando = False
        elif kind == "transicion":
            t = next(t for t in e.M["transitions"] if t["id"] == vivo)
            self._poner(self.t_etiqueta, t["label"])
            self.t_mostrar.setChecked(t.get("showLabel", True))
            self._poner(self.t_texto, e.texto_usuario(vivo))
            self.prog.poner(e.texto_usuario(vivo))
            self._previsualizar()
        elif kind == "barra":
            b = next(b for b in e.M["bars"] if b["id"] == vivo)
            self.b_unidos.setText(f"Por encima: {', '.join(e.nombre(i) for i in b['arriba']) or '—'}<br>"
                                  f"Por debajo: {', '.join(e.nombre(i) for i in b['abajo']) or '—'}")
        elif kind == "enlace":
            tid, sid, rol = vivo.split("|")
            self.l_enlace.setText(f"{e.nombre(vivo)}<br>Arrastre la flecha a lo largo del enlace. "
                                  "Arrastre los cuadrados para recolocar los tramos. "
                                  "La flecha sigue el sentido del enlace; los ajustes de dibujo no cambian la "
                                  "simulación.")
            from .diagrama import enlaces
            ruta = next(r for r in enlaces(e.M) if r["id"] == vivo)
            kinds = ruta.get("arrowKinds", ["flow"])
            if e.flecha not in kinds:
                e.flecha = kinds[0]
            self.f_tipo.blockSignals(True)
            self.f_tipo.clear()
            for key in kinds:
                self.f_tipo.addItem("Flecha de recorrido" if key == "flow" else "Flecha de unión", key)
            self.f_tipo.setCurrentIndex(kinds.index(e.flecha))
            self.f_tipo.blockSignals(False)
            visible = any(a["key"] == e.flecha for a in ruta["arrows"])
            self.f_visible.setChecked(visible)
        self.msg.setText("")

    @staticmethod
    def _poner(campo: QLineEdit, texto: str) -> None:
        if not campo.hasFocus() and campo.text() != texto:
            campo.setText(texto)

    def _insertar(self, texto: str) -> None:
        if self.ident is None:
            return
        self.t_texto.setFocus()
        self.t_texto.insert(f" {texto.strip()} ")  # siempre un espacio delante y otro detrás; los sobrantes se quitan al guardar
        self.prog.poner(self.t_texto.text())
        self._previsualizar()

    def _prefijar(self, prefijo: str) -> None:
        """NOT, ↑ o ↓ delante del texto seleccionado: si no es un solo nombre, entre paréntesis; sin selección, solo el
        prefijo."""
        sel = self.t_texto.selectedText().strip()
        if sel:
            self._insertar(prefijo + (sel if re.fullmatch(r"[\w.]+", sel) else f"({sel})"))
        else:
            self._insertar(prefijo)

    def _renombrar(self, campo: QLineEdit) -> None:
        if self.ident is None or campo.text().strip() == self.e.nombres.get(self.ident):
            return
        motivo = self.e.renombrar(self.ident, campo.text().strip())
        if motivo:
            self.msg.setText(motivo)
            self.msg.setStyleSheet(f"color: {COL['err']}")
            campo.setText(self.e.nombres.get(self.ident, ""))

    # -- receptividad ------------------------------------------------------------------------------
    def _previsualizar(self) -> None:
        e, tid, texto = self.e, self.ident, self.t_texto.text().strip()
        if e is None or tid is None:
            return
        faltan = e.sin_declarar(tid, texto) if texto else []
        pintado = html.escape(texto)
        for n in faltan:  # las variables que no existen, en naranja
            pintado = re.sub(rf"(?<![\w.]){re.escape(html.escape(n))}(?![\w.])",
                             f'<span style="color:{NARANJA};font-weight:600">{html.escape(n)}</span>', pintado)
        self.t_vista.setText(pintado or "<i>vacía</i>")
        self.t_crear.setVisible(bool(faltan))
        self.t_dibujo.setText("")
        if not texto:
            self.msg.setText("Vacía: la transición no compila.")
            self.msg.setStyleSheet(f"color: {COL['err']}")
        elif faltan:
            self.msg.setText(f"No existen: {', '.join(faltan)}.")
            self.msg.setStyleSheet(f"color: {NARANJA}")
        else:
            d = e.comprobar(tid, texto)
            if d is None:
                aviso = e.aviso_ambiguas(texto)
                self.msg.setText("Receptividad correcta." + (f" {aviso}" if aviso else ""))
                self.msg.setStyleSheet(f"color: {NARANJA if aviso else COL['ok']}")
                self.t_dibujo.setText(_html(norm(e.significado(tid, texto), True, e.nombres)))
            else:
                self.msg.setText(f"Error de sintaxis: {d.message}. {d.correction}")
                self.msg.setStyleSheet(f"color: {COL['err']}")

    def _aplicar(self) -> None:
        if self.ident is None or self.t_texto.text().strip() == self.e.texto_usuario(self.ident):
            return
        self.e.poner_condicion(self.ident, self.t_texto.text().strip(), crear=False)

    def _crear(self) -> None:
        if self.ident is not None:
            self.e.poner_condicion(self.ident, self.t_texto.text().strip(), crear=True)

