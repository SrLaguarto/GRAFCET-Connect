"""Opciones de una acción en el panel inferior (paso 4, P-IMP-38, P-IMP-43, P-IMP-44).

Una acción continua pone a 1 una variable booleana mientras la etapa está activa (y, si lleva condición, mientras la
condición se cumple). Una memorizada asigna un valor al activar la etapa, al desactivarla o con un evento mientras
está activa (por ejemplo CT := CT + 1 con ↑I02). Arriba, una frase explica la acción en lenguaje claro.

- La variable se elige en una lista (nunca entradas): una continua ofrece las salidas y memorias booleanas; una
  memorizada, las salidas y memorias de cualquier tipo, por papel. Aquí no se crean variables: se crean en la tabla de
  variables (y sus botones Nueva E, S y M); sin ninguna que valga, la lista lo dice (P-IMP-46).
- El tipo de la acción no se cambia aquí: se cambia con botón derecho sobre la acción, «Tipo de acción».
- El valor de una memorizada se programa con un programador de valor tipo Scratch, como el de bloques pero más corto:
  una booleana elige entre las fichas «1» y «0»; una numérica arma `CT + 1`, `5` o `CT * 2 - 1` con un número,
  variables numéricas y los operadores +, −, ×, ÷. El texto sigue siendo lo que se guarda y lo que el núcleo analiza.
- La condición y el evento los programa con bloques el panel de opciones (junto a este panel, en su parte de bloques).

No hay Aceptar: cada cambio se aplica al momento, como una operación de deshacer (Edicion.cambiar_accion y
Edicion.tipo_accion con las operaciones de grafcet/editor.py). Si a la acción le falta algo, queda como borrador; si la
variable elegida no vale para este tipo, el aviso sale en naranja y parpadea. Las listas de variables se ponen al día en
cada cambio del modelo (el panel se rellena con cada `cambiado` de la edición).
"""
from __future__ import annotations

from html import escape as _escapar
from typing import Any, Callable

from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QTextDocument
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget, QStylePainter, QStyleOptionComboBox, QStyleOptionFrame, QStyle)

from . import estilo
from .bloques import COLORES, Programador, sin_comillas
from .diagrama import COL, _html
from .edicion import CONTINUAS, DISPARADOR, Edicion, Parpadeo
from .variables import nombre_tipo

SIN_VARIABLES = "(sin variables: créelas en la tabla de variables)"  # la lista de variables, si no hay ninguna que valga
ALTO_SELECTOR = 62  # alto del selector de variable (dibujado como una caja de acción); nada debe dejarlo por debajo
ESTILO_FICHA = (f"QPushButton {{ background: {COLORES['comparacion']}; color: white; font-weight: 600; border: 2px solid "
                f"transparent; border-radius: {estilo.R_M}px; padding: 4px 24px; }}"
                f"QPushButton:checked {{ border: 3px solid {estilo.AVISO_BORDE}; }}")



def opciones_variable(v: dict[str, tuple[str, str]], ofrecidas: list[str], elegida: str) -> list[tuple[str, Any, bool]]:
    """Lo que lista el campo de variable de una acción (el de Propiedades y el desplegable sobre la acción del dibujo): (texto, dato, habilitado).
    Salidas y luego Memorias (con su tipo) y la variable elegida aunque no valga para este tipo (se avisa). Nada elegido: «Elija…» o, si no hay
    ninguna que ofrecer, a dónde ir a crearlas."""
    out: list[tuple[str, Any, bool]] = []
    if not elegida:
        out.append(("Elija la variable…" if ofrecidas else SIN_VARIABLES, "", bool(ofrecidas)))
    for papel, titulo in (("output", "Salidas"), ("internal", "Memorias")):
        nombres = [n for n in ofrecidas if v[n][0] == papel]
        if nombres:
            out.append((titulo, None, False))
        for n in nombres:
            out.append((f"   {n}  ({nombre_tipo({'kind': v[n][1]})})", n, True))
    if elegida and elegida not in ofrecidas:  # una entrada, o no booleana en una continua
        out.append((f"{elegida}  (no se puede escribir aquí)", elegida, True))
    return out

class CajaFormula(QLineEdit):
    """El cuadro de texto de una fórmula (la receptividad de una transición, la condición, el evento o el valor de una acción).
    No se edita (la fórmula se arma con bloques): si se interpreta, se ve con la notación del dibujo (↑ y ↓, la negación como
    sobrerrayado, · y +), la misma que `diagrama._html`; si no, el texto tal cual. Es un QLineEdit de solo lectura y sin foco:
    `text()` es siempre el texto del usuario que arman los bloques."""

    def __init__(self) -> None:
        super().__init__()
        self.formato: Callable[[str], str | None] | None = None  # texto -> HTML con la notación del dibujo (None: se ve tal cual)
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def html_mostrado(self) -> str | None:
        """El HTML con que se ve ahora la fórmula, o None si se ve el texto tal cual (vacía o no se interpreta)."""
        if not self.text().strip() or self.formato is None:
            return None
        try:
            return self.formato(self.text())
        except Exception:  # noqa: BLE001 - un texto a medias no debe romper el pintado
            return None

    def paintEvent(self, evento) -> None:  # noqa: N802
        html = self.html_mostrado()
        if html is None and "`" in self.text():  # a medias o sin interpretar: el texto, sin las comillas de los nombres con espacios
            html = _escapar(sin_comillas(self.text()))
        if html is None:
            super().paintEvent(evento)
            return
        p = QPainter(self)
        opcion = QStyleOptionFrame()
        self.initStyleOption(opcion)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_PanelLineEdit, opcion, p, self)
        zona = self.style().subElementRect(QStyle.SubElement.SE_LineEditContents, opcion, self).adjusted(3, 0, -3, 0)
        doc = QTextDocument()
        doc.setDefaultFont(self.font())
        doc.setDocumentMargin(0)
        doc.setHtml(f'<span style="color:{self.palette().text().color().name()}">{html}</span>')
        p.setClipRect(zona)
        p.translate(zona.left(), zona.top() + (zona.height() - doc.size().height()) / 2)
        doc.drawContents(p)


class _ComboVariable(QComboBox):
    """Lista de variables: su texto (`currentText`) es el nombre de la variable elegida, no el de la fila; `setCurrentText`
    elige una variable por su nombre."""

    def __init__(self) -> None:
        super().__init__()
        self.al_poner: Callable[[str], None] | None = None

    def paintEvent(self, _evento):
        p = QStylePainter(self)
        p.setRenderHint(p.RenderHint.Antialiasing)
        caja = QRectF(26, 7, max(40,self.width()-28), self.height()-14)
        p.setPen(QPen(QColor(COL["text"]),1.6))
        p.setBrush(QColor(COL["glow"] if self.property("parpadeando") else COL["panel"]))
        p.drawLine(0,self.height()//2,26,self.height()//2)
        p.drawRect(caja)
        opcion = QStyleOptionComboBox();self.initStyleOption(opcion)
        opcion.rect = QRect(32,11,max(20,self.width()-40),self.height()-22)
        opcion.frame = False
        opcion.currentText = self.currentData() or "?"
        p.drawComplexControl(QStyle.ComplexControl.CC_ComboBox,opcion)
        p.drawControl(QStyle.ControlElement.CE_ComboBoxLabel,opcion)

    def currentText(self) -> str:  # noqa: N802
        d = self.currentData()
        return d if isinstance(d, str) else ""

    def setCurrentText(self, texto: str) -> None:  # noqa: N802
        if self.al_poner is not None:
            self.al_poner(texto)


class PanelAccion(QWidget):
    """Las opciones de la acción mostrada: frase, tipo, variable y límite (esta columna) y, en `caja_valor` (que la ventana
    del panel coloca a su lado), las fichas y el programador del valor de una memorizada. Cada cambio se aplica en el
    acto con la edición; `mostrar(e, aid)` rellena los campos con lo que hay, sin tocar lo que se está escribiendo."""

    def __init__(self) -> None:
        super().__init__()
        self.e: Any = None
        self.aid: str | None = None
        self.sid: str | None = None
        self._llenando = False
        self._sync = False  # el texto del valor lo está escribiendo el programador
        self._elegida = ""
        self.clave_tipo = ""  # el tipo de la acción mostrada (continua, activacion…): se cambia con botón derecho sobre ella
        self._rechazado: tuple[str, str] | None = None  # (acción, aviso): lo último escrito que no se pudo guardar
        self._firma: tuple | None = None
        self.parpadeo = Parpadeo(self)  # el campo que no vale parpadea en naranja
        self.parpadeo.cambia.connect(self._pintar)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.b_etapa = QLabel()  # solo informa de la etapa de la acción; no lleva a ninguna parte
        self.b_etapa.setStyleSheet(f"color: {estilo.TINTA_2}")
        lay.addWidget(self.b_etapa, 0, Qt.AlignmentFlag.AlignLeft)
        self.frase = QLabel()
        self.frase.setWordWrap(True)
        self.frase.setStyleSheet("font-weight: 600")
        lay.addWidget(self.frase)
        f = QFormLayout()
        f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        lay.addLayout(f)
        self.variable = _ComboVariable()
        self.variable.setMinimumHeight(ALTO_SELECTOR)
        self.variable.setObjectName("selectorVariableAccion")
        # Su hoja de estilo no se toca más (el parpadeo lo pinta `paintEvent`): sustituirla deja el min-height:18px
        # general
        self.variable.setStyleSheet(f"QComboBox#selectorVariableAccion {{ min-height:{ALTO_SELECTOR}px; padding:0; }}")
        self.variable.setAccessibleName("Variable de la acción")
        self.variable.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.variable.setMinimumContentsLength(8)
        self.variable.al_poner = self.poner_variable
        self.variable.activated.connect(self._elegir_variable)
        f.addRow("Variable", self.variable)
        self.l_limite = QLabel("Límite de tiempo (3s, 500ms…)")
        self.limite = QLineEdit()
        self.limite.setPlaceholderText("3s")
        self.limite.editingFinished.connect(lambda: self._aplicar("limite"))
        f.addRow(self.l_limite, self.limite)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addStretch(1)
        # El valor de una memorizada: fichas 1/0 (booleana) o programador de valor (numérica)
        self.caja_valor = QWidget()
        vl = QVBoxLayout(self.caja_valor)
        vl.setContentsMargins(0, 0, 0, 0)
        self.caja_fichas = QWidget()
        fl = QHBoxLayout(self.caja_fichas)
        fl.setContentsMargins(0, 0, 0, 0)
        self.l_fichas = QLabel("? :=")  # «Q :=»: la variable de la acción
        fl.addWidget(self.l_fichas)
        self.grupo_fichas = QButtonGroup(self)
        self.fichas: dict[str, QPushButton] = {}
        for v in ("1", "0"):
            b = QPushButton(v)
            b.setCheckable(True)
            b.setStyleSheet(ESTILO_FICHA)
            b.clicked.connect(lambda _=False, v=v: self._poner_valor(v))
            self.grupo_fichas.addButton(b)
            self.fichas[v] = b
            fl.addWidget(b)
        fl.addStretch(1)
        vl.addWidget(self.caja_fichas)
        self.caja_numerica = QWidget()
        nl = QVBoxLayout(self.caja_numerica)
        nl.setContentsMargins(0, 0, 0, 0)
        self.prog = Programador(lambda: (self._variables(), self.e.fuente_bloques()[1] if self.e is not None else []),
                                valor=True)
        self.prog.cambiado.connect(self._desde_bloques)
        self.prog.al_deshacer = lambda: self.e is not None and self.e.deshacer()  # Ctrl+Z deshace la operación
        self.prog.al_rehacer = lambda: self.e is not None and self.e.rehacer()
        nl.addWidget(self.prog, 1)
        fila = QHBoxLayout()
        self.valor = CajaFormula()  # el valor, con la notación del dibujo; se arma con los bloques
        self.valor.formato = self._formato_valor
        self.valor.setPlaceholderText("el valor se arma con bloques (CT + 1, 5…)")
        self.valor.textChanged.connect(self._valor_cambiado)
        self.l_valor = QLabel("? :=")  # «Q :=», sin paréntesis; «? :=» mientras no hay variable
        fila.addWidget(self.l_valor)
        fila.addWidget(self.valor, 1)
        nl.addLayout(fila)
        vl.addWidget(self.caja_numerica, 1)

    # -- rellenar ----------------------------------------------------------------------------------
    def mostrar(self, e: Any, aid: str) -> None:
        """Rellena los campos con la acción `aid` (la edición ya la tiene como está). No toca el campo que se está escribiendo
        ni lo escrito que no se pudo guardar (un valor a medias), y pone al día la lista de variables y el programador."""
        otra = aid != self.aid
        self.e, self.aid = e, aid
        self.sid = e.etapa_accion(aid)
        d = e.datos_accion(aid)
        if self._rechazado is not None and (otra or self._rechazado[0] != aid):
            self._rechazado = None
        if otra:  # otra acción: lo escrito sin confirmar en un campo se descarta (nunca se aplica a la nueva)
            for campo in (self.valor, self.limite):
                campo.blockSignals(True)
                campo.clearFocus()
                campo.blockSignals(False)
        self._llenando = True
        self.clave_tipo = d["tipo"]
        self._elegida = d["variable"] if d["variable"] in self._variables() else ""
        if self._rechazado is None:
            if not self.valor.hasFocus() and self.valor.text() != d.get("valor", ""):
                self.valor.setText(d.get("valor", ""))
            if not self.limite.hasFocus() and self.limite.text() != d.get("limite", ""):
                self.limite.setText(d.get("limite", ""))
        self._llenando = False
        if otra:
            self._valor_cambiado(self.valor.text())
        self.b_etapa.setVisible(bool(self.sid))
        self.b_etapa.setText(f"Etapa {e.nombres.get(self.sid, self.sid)}" if self.sid else "")
        self._ajustar()
        if self._rechazado is None:
            self.prog.poner(self.valor.text())

    def _variables(self) -> dict[str, tuple[str, str]]:
        """Las variables del modelo {nombre: (papel, tipo)}."""
        return dict(self.e.fuente_bloques()[0]) if self.e is not None else {}

    def ofrecidas(self) -> list[str]:
        """Las variables que esta acción puede escribir: nunca entradas; una continua, solo booleanas."""
        continua = self.clave_tipo in CONTINUAS
        return [n for n, (papel, tipo) in self._variables().items() if papel != "input" and (tipo == "bool" or not continua)]

    def poner_variable(self, nombre: str) -> None:
        """Elige una variable por su nombre (si no existe, no hace nada) y lo aplica."""
        if nombre.strip() in self._variables():
            self._elegida = nombre.strip()
            self._rellenar_variables()
            self._aplicar("variable")

    def _rellenar_variables(self) -> None:
        """La lista: Salidas y luego Memorias (con su tipo) y la variable elegida aunque no valga para este tipo (se avisa).
        Sin ninguna que valga ni elegida, un texto que manda a la tabla de variables (aquí no se crean). Solo se rehace si
        cambió algo."""
        v, ofrecidas = self._variables(), self.ofrecidas()
        firma = (tuple(v.items()), self._elegida, self.clave_tipo)
        if firma == self._firma:
            return
        self._firma = firma
        self.variable.setToolTip(SIN_VARIABLES if not ofrecidas else "Seleccione la salida o memoria de la acción")
        c = self.variable
        c.blockSignals(True)
        c.clear()
        for texto, dato, habilitado in opciones_variable(v, ofrecidas, self._elegida):
            c.addItem(texto, dato)
            if not habilitado:
                c.model().item(c.count() - 1).setEnabled(False)
        c.setCurrentIndex(max(0, c.findData(self._elegida)))
        c.blockSignals(False)

    def _tipo_variable(self) -> str:
        """El tipo (bool, int…) de la variable elegida; vacío si no hay."""
        return self._variables().get(self._elegida, ("", ""))[1]

    def _ajustar(self) -> None:
        """Muestra solo lo que pide el tipo y el de la variable; pone al día la lista y la frase."""
        clave = self.clave_tipo
        continua = clave in CONTINUAS
        for w in (self.l_limite, self.limite):
            w.setVisible(clave == "limitada")
        self._rellenar_variables()
        for etiqueta in (self.l_valor, self.l_fichas):
            etiqueta.setText(f"{self._elegida or '?'} :=")
        self.caja_valor.setVisible(not continua)
        booleana = self._tipo_variable() == "bool"
        self.caja_fichas.setVisible(not continua and booleana)
        self.caja_numerica.setVisible(not continua and not booleana)
        self.prog.refrescar()
        self._previsualizar()

    def _formato_valor(self, texto: str) -> str | None:
        """El valor con la notación del dibujo (el de `Edicion._segmentos`); None si no se interpreta."""
        if self.e is None or self.aid is None:
            return None
        segmentos = self.e.vista_formula(texto, self.aid, booleana=False)
        return None if segmentos is None else _html(segmentos)

    def frase_explicativa(self) -> str:
        """La acción en lenguaje claro, según su tipo."""
        d = self.datos()
        etapa = f"la etapa {self.e.nombres.get(self.sid, self.sid)}" if self.sid else "la etapa a la que se una"
        var = d["variable"] or "?"
        if d["tipo"] in CONTINUAS:
            cond = " (y se cumpla la condición)" if d["tipo"] in ("condicionada", "limitada") else ""
            lim = f", como mucho durante {d['limite']}" if d["tipo"] == "limitada" else ""
            return f"Mientras {etapa} esté activa{cond}{lim}, {var} vale 1."
        asignacion = f"{var} := {d['valor'] or '?'}"
        if d["tipo"] == "activacion":
            return f"Al activarse {etapa}: {asignacion}."
        if d["tipo"] == "desactivacion":
            return f"Al desactivarse {etapa}: {asignacion}."
        return f"Con cada {d['evento'] or 'evento sin programar'} mientras {etapa} está activa: {asignacion}."

    def _previsualizar(self) -> None:
        """La frase y el aviso: lo último que no se pudo guardar, la variable que no vale para este tipo o un X… del valor,
        la condición o el evento que puede ser dos etapas (todo en naranja)."""
        if self.e is None or self.aid is None:
            return
        self.frase.setText(self.frase_explicativa())
        if self._rechazado is not None:
            aviso = self._rechazado[1]
        else:
            d = self.datos()
            continua = d["tipo"] in CONTINUAS
            reparo = self._reparo()
            aviso = " ".join(x for x in (
                f"{reparo}. La validación lo señalará." if reparo else "",
                self.e.aviso_ambiguas(d.get("condicion", "") if continua else "", d.get("evento", "") if d["tipo"] == "evento" else "",
                                      d.get("valor", "") if not continua else "")) if x)
        self.msg.setText(aviso)
        self.msg.setStyleSheet(f"color: {COL['glow']}")
        self.msg.setVisible(bool(aviso))

    def _reparo(self) -> str:
        """Por qué la variable elegida no sirve para este tipo de acción (la validación lo señalará)."""
        nombre, tipo = self._elegida, self.clave_tipo
        if nombre not in self._variables():
            return ""
        papel, kind = self._variables()[nombre]
        if papel == "input":
            return f"«{nombre}» es una entrada: una acción no puede escribirla"
        if tipo in CONTINUAS and kind != "bool":
            return f"una acción continua necesita una variable booleana y «{nombre}» no lo es"
        return ""

    # -- los datos ---------------------------------------------------------------------------------
    def datos(self) -> dict[str, str]:
        """La acción como la dejan los campos: lo que no se edita aquí (la condición y el evento, que son de los bloques) es
        lo guardado."""
        d = dict(self.e.datos_accion(self.aid))
        d["variable"] = self._elegida
        if d["tipo"] in DISPARADOR:
            d["valor"] = self.valor.text().strip()
        if d["tipo"] == "limitada":
            limite = self.limite.text().strip()
            d["limite"] = limite
            if not limite:  # quitar el límite: queda una condicionada (o una continua, sin condición)
                d["tipo"] = "condicionada" if d.get("condicion") else "continua"
        return d

    # -- cambios (cada uno se aplica en el acto) ---------------------------------------------------
    def _elegir_variable(self, _: int = 0) -> None:
        self._elegida = self.variable.currentText()
        self._aplicar("variable")

    def _poner_valor(self, texto: str) -> None:
        self.valor.setText(texto)
        self._aplicar("valor")

    def _desde_bloques(self, texto: str) -> None:
        self._sync = True
        self.valor.setText(texto)
        self._sync = False
        self._aplicar("valor")

    def _valor_cambiado(self, texto: str) -> None:
        """El texto del valor cambió (ficha, bloques o a mano): las fichas siguen al texto y la frase también."""
        t = texto.strip()
        for v, b in self.fichas.items():
            b.setChecked(t == v)
        if not self._llenando and self.e is not None and self.aid is not None:
            self.frase.setText(self.frase_explicativa())

    def _aplicar(self, campo: str = "") -> bool:
        """Aplica lo que hay en los campos a la acción, como una operación de deshacer. Si no se puede (un valor a medias,
        un nombre que no vale), el motivo sale en naranja, parpadea el campo y no cambia nada. Devuelve si se aplicó."""
        if self._llenando or self.e is None or self.aid is None:
            return False
        d = self.datos()
        if d["tipo"] in DISPARADOR and campo != "valor":
            d["valor"] = self.e.datos_accion(self.aid).get("valor", "")  # solo cambia lo que se tocó
        if campo == "valor" and d["tipo"] not in DISPARADOR:
            return False
        antes = self.aid
        motivo = self.e.cambiar_accion(self.aid, d)
        if motivo:
            self._rechazado = (antes, motivo)
            self._previsualizar()
            self.parpadeo.iniciar({campo or "variable"})
            return False
        self._rechazado = None
        self._previsualizar()  # (la edición ya repintó el panel con el aviso de antes: una acción suelta sigue siendo borrador)
        if self._reparo():  # la variable no vale para este tipo: se aplica, y el aviso (naranja) parpadea
            self.parpadeo.iniciar({"variable"})
        return True

    def _pintar(self) -> None:
        """Colorea de naranja el campo que parpadea mientras dura la fase encendida."""
        activos = self.parpadeo.activos()
        for clave, w in (("variable", self.variable), ("valor", self.valor), ("limite", self.limite)):
            w.setProperty("parpadeando", clave in activos)
            if w is not self.variable:  # el selector se pinta solo con la propiedad: ver ALTO_SELECTOR
                w.setStyleSheet(f"background: {COL['glow']}" if clave in activos else "")
            w.update()
