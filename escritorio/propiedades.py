"""Paleta de elementos y panel de opciones del editor (P-IMP-32, P-IMP-43, P-IMP-44, P-IMP-47).

La paleta (izquierda) es una sola lista de fichas: etapa, transición, simultaneidad y «Acción» (la continua, con su
dibujo; otro tipo se elige con botón derecho sobre la acción, «Tipo de acción»). Sus fichas solo se colocan
arrastrándolas al dibujo, y un clic solo muestra su ayuda.

El panel de opciones (abajo, a todo el ancho, al editar) muestra y cambia la configuración de lo seleccionado, con dos
zonas: a la izquierda una columna estrecha con los campos y a la derecha lo ancho.
- Transición: etiqueta, si se muestra y comentario; a la derecha, el programador por bloques de la receptividad (con el
  texto de la fórmula, cómo se escribe y cómo se dibuja, y «Crear las que faltan» para las variables que no existen).
- Etapa: etiqueta, tipo, comentario y colocación de las acciones; a la derecha, la lista de sus acciones y sus botones.
- Acción: frase, variable (y límite de una acción antigua) a la izquierda (`PanelAccion`; el tipo se cambia con botón
  derecho sobre la acción); a la derecha el
  programador del valor de una memorizada y, si es condicionada o por evento, el de su condición o su evento.
- Enlace, barra de simultaneidad, varios elementos o nada: lo suyo, o la invitación a elegir un elemento.
Cada cambio se aplica al momento con las operaciones de Edicion / grafcet/editor.py (una operación de deshacer).
"""
from __future__ import annotations

import html
import re
from typing import Any, Callable

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from grafcet.routing import TALLO_E, TALLO_T
from grafcet.view import norm

from .acciones import PanelAccion
from .bloques import FlowLayout, Programador
from .diagrama import COL, H, TB, _html, ficha_accion
from .edicion import COLOCACIONES, CONTINUAS, Parpadeo

NARANJA = COL["glow"]
ANCHO_COLUMNA = 230  # la columna estrecha de campos del panel de opciones
NOMBRES = {"etapa": "Etapa", "transicion": "Transición", "simultaneidad": "Simultaneidad", "accion:continua": "Acción"}
AYUDAS = {"etapa": "Etapa: arrástrela al dibujo", "transicion": "Transición: arrástrela al dibujo",
          "simultaneidad": "Barra de simultaneidad (doble trazo, Y): une varias etapas a una transición, o una transición "
                           "a varias etapas. Se ensancha estirando de sus extremos. Las alternativas (O) no son un elemento: "
                           "se construyen con el ratón enlazando una etapa con una segunda transición, o arrastrando a un enlace.",
          "accion:continua": "Acción continua: se cumple mientras la etapa está activa. Arrástrela al dibujo (queda suelta, con «?»); "
                             "se une a una etapa arrastrando desde su punto de unión de la izquierda hasta la etapa, o pegándola al "
                             "lado de otra acción. Para otro tipo (condicionada, al activar, al desactivar, por evento), botón "
                             "derecho sobre la acción, «Tipo de acción»"}
COLOCABLES = tuple(NOMBRES)  # las fichas de la paleta: solo se colocan arrastrándolas al dibujo


def icono(h: str) -> QIcon:
    """Dibujo del elemento, para reconocerlo en la paleta (con el trazo de la norma: etapa cuadrada, transición, barras,
    y la caja de una acción con su enlace a la izquierda, como la dibuja el diagrama)."""
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
    elif h.startswith("accion:"):
        p.drawLine(2, 32, 14, 32)
        p.drawRect(QRectF(14, 14, 48, 36))
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
    transición; el centro del trazo superior de la barra; el centro del lado izquierdo de una acción)."""
    if h.startswith("accion:"):
        return ficha_accion(h.partition(":")[2], escala, dpr, 0.85)
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
    """La lista de fichas del grafcet (etapa, transición, simultaneidad y acción). Las fichas solo se colocan
    arrastrándolas al dibujo; un clic en una ficha no hace nada salvo mostrar su ayuda (señal `ayuda`)."""

    ayuda = Signal(str)
    REJILLA = QSize(92, 96)
    ICONO = QSize(80, 64)
    FILAS = 2
    CLAVES: tuple[str, ...] = COLOCABLES

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)  # iconos grandes con su nombre: se ven y se arrastran
        self.setIconSize(self.ICONO)
        self.setGridSize(self.REJILLA)
        self.setMovement(QListView.Movement.Static)  # Static desactiva el arrastre: se activa después
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        for h in self.CLAVES:
            it = QListWidgetItem(icono(h), self.nombre(h))
            it.setData(Qt.ItemDataRole.UserRole, h)
            it.setToolTip(self.texto_ayuda(h))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.addItem(it)
        self.setCurrentRow(-1)
        self.itemClicked.connect(lambda it: self.ayuda.emit(self.texto_ayuda(it.data(Qt.ItemDataRole.UserRole))))
        self.setMaximumHeight(self.FILAS * self.REJILLA.height() + 2 * self.frameWidth() + 2)
        # Siempre dos columnas: sin barras de desplazamiento (la de la derecha se comería parte del ancho y las fichas
        # pasarían a una sola columna)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @staticmethod
    def nombre(h: str) -> str:
        return NOMBRES[h]

    @staticmethod
    def texto_ayuda(h: str) -> str:
        return AYUDAS[h]

    def ancho_minimo(self) -> int:
        """El ancho que piden las dos columnas de fichas: su rejilla, el marco y 2 de holgura (con menos, el modo de iconos
        pasa a una sola columna)."""
        return 2 * self.gridSize().width() + 2 * self.frameWidth() + 2

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


def _formulario(w: QWidget) -> QFormLayout:
    """Formulario arriba de la columna y que se estrecha: si no cabe, el rótulo va encima del campo."""
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
    """Las opciones del elemento seleccionado, con campos editables (el panel «Opciones» de abajo)."""

    def __init__(self) -> None:
        super().__init__()
        self.e: Any = None
        self.ident: str | None = None
        self._llenando = False
        self._anterior: tuple | None = None  # lo que programaron los bloques la última vez (para volver al texto de solo lectura)
        self._objetivo: tuple | None = None  # lo que programan los bloques: ("transicion", ID) o ("accion", ID, campo)
        self.pagina = "vacio"
        self.parpadeo_crear = Parpadeo(self)  # «Crear las que faltan» parpadea si un nombre no vale
        self.parpadeo_crear.cambia.connect(self._pintar_crear)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-weight: 600")
        lay.addWidget(self.titulo)
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(10)
        lay.addLayout(cuerpo, 1)
        # Izquierda, la columna estrecha de campos; derecha, lo ancho (lista de acciones, programadores, enlace, barra)
        self.izq = QStackedWidget()
        self.izq.setFixedWidth(ANCHO_COLUMNA)
        self.izq.addWidget(QWidget())  # 0: nada que mostrar en la columna
        self.izq.addWidget(self._etapa())  # 1
        self.izq.addWidget(self._transicion())  # 2
        self.accion = PanelAccion()  # 3
        self.izq.addWidget(self.accion)
        cuerpo.addWidget(self.izq)
        self.der = QStackedWidget()
        self.der.addWidget(self._vacio())  # 0
        self.der.addWidget(self._lista_acciones())  # 1
        self.der.addWidget(self._programacion())  # 2
        self.der.addWidget(self._enlace())  # 3
        self.der.addWidget(self._barra())  # 4
        cuerpo.addWidget(self.der, 1)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

    # -- páginas -----------------------------------------------------------------------------------
    def _programacion(self) -> QWidget:
        """Lo ancho de una transición o una acción: a la izquierda el programador del valor de una acción memorizada y,
        a su derecha, el programador por bloques de la receptividad de una transición o de la condición (o el evento) de una
        acción, con su texto, cómo se escribe, cómo se dibuja y «Crear las que faltan»."""
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)
        hl.addWidget(self.accion.caja_valor, 1)
        self.pagina_bloques = QWidget()
        hl.addWidget(self.pagina_bloques, 1)
        lay = QVBoxLayout(self.pagina_bloques)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.l_bloques = QLabel()
        self.l_bloques.setStyleSheet(f"color: {COL['muted']}")
        lay.addWidget(self.l_bloques)
        self.prog = Programador(lambda: self.e.fuente_bloques() if self.e is not None else ({}, []))
        self.prog.cambiado.connect(self._desde_bloques)
        self.prog.al_deshacer = lambda: self.e is not None and self.e.deshacer()  # Ctrl+Z en la ventana ampliada
        self.prog.al_rehacer = lambda: self.e is not None and self.e.rehacer()
        lay.addWidget(self.prog, 1)
        # Debajo del área, toda la receptividad: el texto de la fórmula (solo se ve; «Escribir a mano» lo deja editar), cómo
        # se escribe, cómo se dibuja, el estado y «Crear las que faltan»
        self.caja_formula = QWidget()
        g = QGridLayout(self.caja_formula)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(2)
        self.t_texto = QLineEdit()
        self.t_texto.setReadOnly(True)
        self.t_texto.setPlaceholderText("la fórmula se arma con bloques")
        self.t_texto.textEdited.connect(self._escrito)
        self.t_texto.editingFinished.connect(self._aplicar)
        self.t_manual = QCheckBox("Escribir a mano")
        self.t_manual.setToolTip("Dejar editar el texto de la fórmula (↑a AND NOT b, X1, 3s/X1…); lo escrito pasa a bloques")
        self.t_manual.toggled.connect(self._manual)
        self.t_vista = QLabel()
        self.t_vista.setWordWrap(True)
        self.t_vista.setTextFormat(Qt.TextFormat.RichText)
        self.t_dibujo = QLabel()
        self.t_dibujo.setTextFormat(Qt.TextFormat.RichText)
        self.t_dibujo.setWordWrap(True)
        self.t_estado = QLabel()
        self.t_estado.setWordWrap(True)
        self.t_crear = QPushButton("Crear las que faltan")
        self.t_crear.setToolTip("Declarar como entradas booleanas las variables que se usan y no existen")
        self.t_crear.clicked.connect(self._crear)
        g.addWidget(QLabel("Fórmula"), 0, 0)
        g.addWidget(self.t_texto, 0, 1)
        g.addWidget(self.t_manual, 0, 2)
        g.addWidget(QLabel("Escrito"), 1, 0)
        g.addWidget(self.t_vista, 1, 1, 1, 2)
        g.addWidget(QLabel("Se dibuja"), 2, 0)
        g.addWidget(self.t_dibujo, 2, 1, 1, 2)
        g.addWidget(self.t_estado, 3, 0, 1, 2)
        g.addWidget(self.t_crear, 3, 2)
        g.setColumnStretch(1, 1)
        lay.addWidget(self.caja_formula)
        self._ver_bloques(None)
        return w

    def _ver_bloques(self, titulo: str | None) -> None:
        """El programador de la transición o de la acción (condición o evento), o nada si no hay que programar."""
        self.pagina_bloques.setVisible(titulo is not None)
        self.l_bloques.setText(titulo or "")

    def objetivo_bloques(self) -> tuple | None:
        """Lo que programan los bloques ahora: ("transicion", ID) o ("accion", ID, «condicion» o «evento»)."""
        return self._objetivo

    def _guardado(self) -> str:
        """El texto guardado de lo que programan los bloques (receptividad, condición o evento), en la notación del usuario."""
        o = self._objetivo
        return self.e.texto_usuario(o[1]) if o[0] == "transicion" else self.e.texto_accion(o[1], o[2])

    TEXTO_VACIO = "Haga clic en un elemento del dibujo para ver y cambiar sus opciones."

    def _vacio(self) -> QWidget:
        self.l_vacio = QLabel(self.TEXTO_VACIO)
        self.l_vacio.setWordWrap(True)
        self.l_vacio.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.l_vacio.setStyleSheet(f"color: {COL['muted']}")
        return self.l_vacio

    def _etapa(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.s_etiqueta = QLineEdit()
        self.s_etiqueta.editingFinished.connect(lambda: self._renombrar(self.s_etiqueta))
        self.s_tipo = _desplegable()
        self.s_tipo.addItem("Normal", False)
        self.s_tipo.addItem("Inicial", True)
        self.s_tipo.activated.connect(lambda _: self.e.tipo_etapa(self.ident, self.s_tipo.currentData()))
        self.s_comentario = QLineEdit()
        self.s_comentario.setPlaceholderText("sin comentario")
        self.s_comentario.setToolTip("Comentario de la etapa: se dibuja entre comillas a su derecha (no entra en la simulación)")
        self.s_comentario.editingFinished.connect(lambda: self._comentar(self.s_comentario))
        self.s_colocacion = _desplegable()
        for valor, texto in COLOCACIONES:
            self.s_colocacion.addItem(texto, valor)
        self.s_colocacion.setToolTip("Cómo se colocan las acciones de la etapa en el dibujo")
        self.s_colocacion.activated.connect(lambda _: self.e.colocar_acciones(self.ident, self.s_colocacion.currentData()))
        f.addRow("Etiqueta", self.s_etiqueta)
        f.addRow("Tipo", self.s_tipo)
        f.addRow("Comentario", self.s_comentario)
        f.addRow("Colocación", self.s_colocacion)
        return w

    def _lista_acciones(self) -> QWidget:
        """Lo ancho de una etapa: la lista de sus acciones y los botones para añadir, editar, quitar y mover."""
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        izq = QVBoxLayout()
        izq.addWidget(QLabel("Acciones"))
        self.s_acciones = QListWidget()
        self.s_acciones.setWordWrap(True)
        self.s_acciones.itemDoubleClicked.connect(lambda it: self._editar(it.data(Qt.ItemDataRole.UserRole)))
        self.s_acciones.currentItemChanged.connect(self._accion_señalada)
        izq.addWidget(self.s_acciones, 1)
        hl.addLayout(izq, 1)
        col = QVBoxLayout()
        col.addSpacing(18)
        for texto, tip, accion in (("Añadir…", "Añadir una acción a la etapa (también con el botón derecho en la etapa)",
                                    self._anadir),
                                   ("Editar…", "Abrir las opciones de la acción elegida (o doble clic en ella)",
                                    lambda: self._editar(self._elegida())),
                                   ("Quitar", "Quitar la acción elegida", lambda: self._elegida() and self.e.quitar_accion(self._elegida())),
                                   ("◀", "Más a la izquierda en el dibujo", lambda: self._elegida() and self.e.mover_accion(self._elegida(), -1)),
                                   ("▶", "Más a la derecha", lambda: self._elegida() and self.e.mover_accion(self._elegida(), 1))):
            b = QPushButton(texto)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=accion: f())
            col.addWidget(b)
        col.addStretch(1)
        hl.addLayout(col)
        return w

    def _elegida(self) -> str | None:
        it = self.s_acciones.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _anadir(self) -> None:
        """«Añadir…»: una acción continua unida a la etapa, sin variable todavía; sus opciones se abren en el panel."""
        if self.e is not None and self.ident:
            self.e.anadir_accion(self.ident)

    def _editar(self, aid: str | None) -> None:
        if self.e is not None and self.ident and aid:
            self.e.pedir_accion(self.ident, aid)

    def _accion_señalada(self, it: Any, _: Any = None) -> None:
        """Elegir una acción en la lista la resalta en el dibujo."""
        aid = it.data(Qt.ItemDataRole.UserRole) if it else None
        if self.e is not None and aid != self.e.accion and not self._llenando:
            self.e.accion, self.e.ver_accion = aid, False
            self.e.cambiado.emit()

    def _transicion(self) -> QWidget:
        w = QWidget()
        f = _formulario(w)
        self.t_etiqueta = QLineEdit()
        self.t_etiqueta.editingFinished.connect(lambda: self._renombrar(self.t_etiqueta))
        self.t_mostrar = QCheckBox("Mostrar etiqueta")
        self.t_mostrar.setToolTip("Dibujar la etiqueta (t1) junto a la transición")
        self.t_mostrar.clicked.connect(lambda on: self.e.mostrar_etiqueta(self.ident, on))
        self.t_comentario = QLineEdit()
        self.t_comentario.setPlaceholderText("sin comentario")
        self.t_comentario.setToolTip("Comentario de la transición: se dibuja entre comillas a la derecha de su receptividad "
                                     "(no entra en la simulación)")
        self.t_comentario.editingFinished.connect(lambda: self._comentar(self.t_comentario))
        f.addRow("Etiqueta", self.t_etiqueta)
        f.addRow(self.t_mostrar)
        f.addRow("Comentario", self.t_comentario)
        return w

    def _desde_bloques(self, texto: str) -> None:
        """Cada cambio en los bloques escribe el texto y se aplica (una operación de deshacer)."""
        self.t_texto.setText(texto)
        self._previsualizar()
        self._aplicar()

    def _escrito(self) -> None:
        self.prog.poner(self.t_texto.text())
        self._previsualizar()

    def _manual(self, on: bool) -> None:
        """«Escribir a mano»: marcada, el texto de la fórmula se puede editar; desmarcada, vuelve a ser de solo lectura."""
        self.t_texto.setReadOnly(not on)
        if on:
            self.t_texto.setFocus()
        elif self._objetivo is not None and self.e is not None:
            self._aplicar()

    def _enlace(self) -> QWidget:
        w = QWidget()
        f = QVBoxLayout(w)
        self.l_enlace = QLabel()
        self.l_enlace.setWordWrap(True)
        f.addWidget(self.l_enlace)
        self.f_tipo = QComboBox()
        self.f_tipo.setMaximumWidth(260)
        self.f_tipo.currentIndexChanged.connect(self._elegir_flecha)
        f.addWidget(self.f_tipo)
        self.f_visible = QCheckBox("Mostrar flecha")
        self.f_visible.clicked.connect(lambda on: self.e.ajustar_flecha(visible=on))
        f.addWidget(self.f_visible)
        fila = QHBoxLayout()
        self.f_auto = QPushButton("Flecha automática")
        self.f_auto.setToolTip("Restablecer la flecha: su sitio y si se ve, como los pone el programa")
        self.f_auto.clicked.connect(lambda: self.e.restablecer_flecha())
        fila.addWidget(self.f_auto)
        q = QPushButton("Quitar el enlace")
        q.clicked.connect(lambda: self.e.borrar())
        fila.addWidget(q)
        fila.addStretch(1)
        f.addLayout(fila)
        f.addStretch(1)
        return w

    def _elegir_flecha(self) -> None:
        if self.e is not None and self.f_tipo.currentData():
            self.e.flecha = self.f_tipo.currentData()
            self.mostrar(self.e)

    def _barra(self) -> QWidget:
        w = QWidget()
        f = QVBoxLayout(w)
        self.b_tipo = QLabel("Simultaneidad (doble trazo, Y)")
        self.b_tipo.setWordWrap(True)
        self.b_unidos = QLabel()
        self.b_unidos.setWordWrap(True)
        q = QPushButton("Quitar la barra")
        q.clicked.connect(lambda: self.e.borrar())
        ayuda = QLabel("Arrastre de un extremo para ensancharla; de un punto de unión sale un enlace.")
        ayuda.setWordWrap(True)
        f.addWidget(QLabel("<b>Tipo</b>"))
        f.addWidget(self.b_tipo)
        f.addWidget(QLabel("<b>Unidos</b>"))
        f.addWidget(self.b_unidos)
        f.addWidget(ayuda)
        fila = QHBoxLayout()
        fila.addWidget(q)
        fila.addStretch(1)
        f.addLayout(fila)
        f.addStretch(1)
        return w

    # -- estado ------------------------------------------------------------------------------------
    def mostrar(self, e: Any) -> None:
        """Rellena el panel con el elemento seleccionado (o lo vacía); respeta el campo que se está escribiendo."""
        self.e = e
        if e is not None:
            self.prog.refrescar()  # las variables pudieron cambiar (panel Variables, panel de la acción, «Crear las que faltan»)
        sel = e.sel if e is not None else []
        vivo = sel[0] if len(sel) == 1 else None
        aid = e.accion_activa() if e is not None else None
        kind = ("accion" if aid else
                "enlace" if "|" in vivo else
                "barra" if any(b["id"] == vivo for b in e.M.get("bars", [])) else
                "etapa" if any(s["id"] == vivo for s in e.M["steps"]) else
                "transicion" if any(t["id"] == vivo for t in e.M["transitions"]) else None) if (vivo or aid) else None
        ident = aid if kind == "accion" else vivo if kind else None
        if (kind, ident) != (getattr(self, "_mostrado", None)):  # otro elemento: lo escrito sin confirmar se descarta
            for campo in (self.s_etiqueta, self.s_comentario, self.t_etiqueta, self.t_comentario):
                campo.blockSignals(True)
                campo.clearFocus()
                campo.blockSignals(False)
        self._mostrado = (kind, ident)
        self.ident = ident
        self.pagina = kind or "vacio"  # qué opciones se muestran: etapa, transicion, accion, enlace, barra o vacio
        etapa_a = e.nombres.get(e.etapa_accion(aid), "") if kind == "accion" else ""
        titulo = {"etapa": f"Etapa {e.nombres.get(vivo)}", "transicion": f"Transición {e.nombres.get(vivo)}",
                  "enlace": f"Enlace {e.nombre(vivo)}" if vivo else "", "barra": e.nombre(vivo) if vivo else "",
                  "accion": f"Acción {(e.datos_accion(aid)['variable'] or '?') if aid else ''}" + (f" · etapa {etapa_a}" if etapa_a else " · suelta"),
                  None: "" if len(sel) < 2 else f"{len(sel)} elementos seleccionados"}[kind] if e is not None else ""
        self.titulo.setText(f"Opciones · {titulo}" if titulo else "Opciones")
        self.izq.setCurrentIndex({None: 0, "etapa": 1, "transicion": 2, "accion": 3, "enlace": 0, "barra": 0}[kind])
        self.izq.setVisible(kind in ("etapa", "transicion", "accion"))
        self.l_vacio.setText("Enlace de la etapa con sus acciones: Supr (o botón derecho, «Eliminar el enlace») las separa de la "
                             "etapa; quedan sueltas e independientes, cada una donde estaba."
                             if len(sel) == 1 and sel[0].startswith("enlaceacc:") else self.TEXTO_VACIO)
        acc = e.accion_programable() if e is not None else None
        self._objetivo = (("transicion", vivo) if kind == "transicion" else ("accion", *acc) if acc and kind == "accion" else None)
        self._ver_bloques(None if self._objetivo is None else
                          f"Receptividad de la transición {e.nombres.get(vivo, vivo)}" if kind == "transicion" else
                          e.titulo_accion(acc[0], acc[1]))
        if kind == "accion":
            self.accion.mostrar(e, aid)
            memorizada = self.accion.clave_tipo not in CONTINUAS
            self.der.setCurrentIndex(2 if (memorizada or self._objetivo is not None) else 0)
            if not (memorizada or self._objetivo is not None):
                self.l_vacio.setText("Acción continua: vale 1 mientras la etapa está activa, y no lleva nada más. Cambie el tipo "
                                     "(botón derecho sobre la acción, «Tipo de acción») para añadirle una condición, o para que "
                                     "asigne un valor.")
        else:
            self.accion.caja_valor.setVisible(False)
        if self._objetivo is not None:
            if self._objetivo != self._anterior:  # otro objetivo: el texto vuelve a ser de solo lectura
                self.t_manual.blockSignals(True)
                self.t_manual.setChecked(False)
                self.t_manual.blockSignals(False)
                self.t_texto.setReadOnly(True)
                self.t_texto.blockSignals(True)  # sin «editingFinished»: aún tiene el texto del objetivo anterior
                self.t_texto.clearFocus()
                self.t_texto.blockSignals(False)
            guardado = self._guardado()
            self._poner(self.t_texto, guardado)
            self.prog.poner(guardado)
            self._previsualizar()
        self._anterior = self._objetivo
        if kind == "etapa":
            s = next(s for s in e.M["steps"] if s["id"] == vivo)
            self._poner(self.s_etiqueta, s["label"])
            self._poner(self.s_comentario, e.comentario(vivo))
            self.s_tipo.setCurrentIndex(1 if s["initial"] else 0)
            self.s_colocacion.setCurrentIndex(max(0, self.s_colocacion.findData(e.colocacion(vivo))))
            self.der.setCurrentIndex(1)
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
            self._poner(self.t_comentario, e.comentario(vivo))
            self.t_mostrar.setChecked(t.get("showLabel", True))
            self.der.setCurrentIndex(2)
        elif kind == "barra":
            b = next(b for b in e.M["bars"] if b["id"] == vivo)
            self.b_unidos.setText(f"Por encima: {', '.join(e.nombre(i) for i in b['arriba']) or '—'}<br>"
                                  f"Por debajo: {', '.join(e.nombre(i) for i in b['abajo']) or '—'}")
            self.der.setCurrentIndex(4)
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
            self.der.setCurrentIndex(3)
        elif kind is None:
            self.der.setCurrentIndex(0)
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

    def _comentar(self, campo: QLineEdit) -> None:
        """El comentario de la etapa o transición mostrada: una operación de deshacer al confirmar."""
        if self.ident is None or self.e is None or self.e.sel != [self.ident] or self.ident not in self.e.nombres:
            return  # (el editingFinished puede llegar tarde: el elemento ya no es el mostrado, o ya no existe)
        self.e.poner_comentario(self.ident, campo.text())

    def _renombrar(self, campo: QLineEdit) -> None:
        if self.ident is None or self.e.sel != [self.ident] or self.ident not in self.e.nombres \
                or campo.text().strip() == self.e.nombres.get(self.ident):
            return  # (el editingFinished puede llegar tarde: el elemento ya no es el mostrado, o ya no existe)
        motivo = self.e.renombrar(self.ident, campo.text().strip())
        if motivo:
            self.msg.setText(motivo)
            self.msg.setStyleSheet(f"color: {COL['err']}")
            campo.setText(self.e.nombres.get(self.ident, ""))

    # -- receptividad ------------------------------------------------------------------------------
    def _previsualizar(self) -> None:
        e, o, texto = self.e, self._objetivo, self.t_texto.text().strip()
        if e is None or o is None:
            return
        ident = o[1]
        tr = o[0] == "transicion"
        cosa = "Receptividad" if tr else "Condición" if o[2] == "condicion" else "Evento"
        faltan = e.sin_declarar(ident, texto) if texto else []
        pintado = html.escape(texto)
        for n in faltan:  # las variables que no existen, en naranja
            pintado = re.sub(rf"(?<![\w.]){re.escape(html.escape(n))}(?![\w.])",
                             f'<span style="color:{NARANJA};font-weight:600">{html.escape(n)}</span>', pintado)
        self.t_vista.setText(pintado or "<i>vacía</i>")
        self.t_crear.setVisible(bool(faltan))
        self.t_dibujo.setText("")
        if not texto:
            self.t_estado.setText("Vacía: la transición no compila." if tr else
                                  f"Vacía: sin {'condición' if o[2] == 'condicion' else 'evento'}, la acción no se simula.")
            self.t_estado.setStyleSheet(f"color: {COL['err'] if tr else COL['muted']}")
        elif faltan:
            self.t_estado.setText(f"No existen: {', '.join(faltan)}.")
            self.t_estado.setStyleSheet(f"color: {NARANJA}")
        else:
            d = e.comprobar(ident, texto)
            if d is None:
                aviso = e.aviso_ambiguas(texto)
                self.t_estado.setText(f"{cosa} {'correcta' if cosa != 'Evento' else 'correcto'}." + (f" {aviso}" if aviso else ""))
                self.t_estado.setStyleSheet(f"color: {NARANJA if aviso else COL['ok']}")
                self.t_dibujo.setText(_html(norm(e.significado(ident, texto), True, e.nombres)))
            else:
                self.t_estado.setText(f"Error de sintaxis: {d.message}. {d.correction}")
                self.t_estado.setStyleSheet(f"color: {COL['err']}")

    def _aplicar(self) -> None:
        o = self._objetivo
        if o is None or self.t_texto.text().strip() == self._guardado():
            return  # (al cambiar la selección, el campo oculto pierde el foco con el texto del objetivo anterior)
        if o[0] == "transicion":
            self.e.poner_condicion(o[1], self.t_texto.text().strip(), crear=False)
        else:
            self.e.poner_texto_accion(o[1], o[2], self.t_texto.text().strip())

    def _crear(self) -> None:
        o = self._objetivo
        if o is None:
            return
        texto = self.t_texto.text().strip()
        if o[0] == "transicion":
            resultado = self.e.poner_condicion(o[1], texto, crear=True)
            motivo = resultado.message if getattr(resultado, "code", "") == "D-FORMATO" else None
        else:
            motivo = self.e.poner_texto_accion(o[1], o[2], texto, crear=True)
        if motivo:  # un nombre que no se puede escribir en una fórmula: mensaje y parpadeo
            self.t_estado.setText(motivo)
            self.t_estado.setStyleSheet(f"color: {COL['err']}")
            self.parpadeo_crear.iniciar({"crear"})

    def _pintar_crear(self) -> None:
        self.t_crear.setStyleSheet(f"background: {NARANJA}" if self.parpadeo_crear.activos() else "")
