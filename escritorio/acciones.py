"""Opciones de una acción en el panel inferior (paso 4, P-IMP-38, P-IMP-43, P-IMP-44).

Una acción continua pone a 1 una variable booleana mientras la etapa está activa (y, si lleva condición, mientras la
condición se cumple). Una memorizada asigna un valor al activar la etapa, al desactivarla o con un evento mientras
está activa (por ejemplo CT := CT + 1 con ↑I02). Arriba, una frase explica la acción en lenguaje claro.

- La variable se elige en una lista (nunca entradas): una continua ofrece las salidas y memorias booleanas; una
  memorizada, las salidas y memorias de cualquier tipo, por papel. «Nueva variable…» la crea y la elige en la misma
  operación de deshacer que el cambio.
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

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from .bloques import COLORES, FlowLayout, Programador
from .diagrama import COL
from .edicion import CONTINUAS, DISPARADOR, TEXTO_LIMITADA, Edicion, Parpadeo
from .variables import PAPELES, TIPOS as TIPOS_VARIABLE, nombre_tipo

TIPOS = (("continua", "Continua: mientras la etapa está activa"),
         ("condicionada", "Condicionada: continua que exige una condición (se programa con bloques)"),
         ("activacion", "Memorizada al activar la etapa (↑)"),
         ("desactivacion", "Memorizada al desactivar la etapa (↓)"),
         ("evento", "Memorizada con un evento, mientras está activa (banderita; el evento se programa con bloques)"))
NUEVA = "\0nueva"  # el dato de la última opción de la lista de variables, «Nueva variable…»
PAPELES_NUEVA = tuple((clave, texto) for clave, texto in PAPELES if clave != "input")  # una acción no escribe entradas
ESTILO_FICHA = (f"QPushButton {{ background: {COLORES['comparacion']}; color: white; font-weight: 600; border: 2px solid "
                f"transparent; border-radius: 9px; padding: 5px 22px; }}"
                "QPushButton:checked { border: 3px solid #FFD43B; }")


class _ComboVariable(QComboBox):
    """Lista de variables: su texto (`currentText`) es el nombre de la variable elegida, no el de la fila; `setCurrentText`
    elige una variable por su nombre (el diálogo la pone en la lista si hace falta)."""

    def __init__(self) -> None:
        super().__init__()
        self.al_poner: Callable[[str], None] | None = None

    def currentText(self) -> str:  # noqa: N802
        d = self.currentData()
        return d if isinstance(d, str) and d != NUEVA else ""

    def setCurrentText(self, texto: str) -> None:  # noqa: N802
        if self.al_poner is not None:
            self.al_poner(texto)


class DialogoVariableNueva(QDialog):
    """«Nueva variable…»: nombre (con las reglas de nombres de las variables), papel (salida o memoria) y tipo. Si el
    nombre no vale, avisa y no se cierra."""

    def __init__(self, parent: QWidget | None, existentes: set[str], solo_booleana: bool = False) -> None:
        super().__init__(parent)
        self.existentes = existentes
        self.resultado: tuple[str, str, dict[str, Any]] | None = None
        self.setWindowTitle("Nueva variable")
        lay = QVBoxLayout(self)
        f = QFormLayout()
        lay.addLayout(f)
        self.nombre = QLineEdit()
        self.papel = QComboBox()
        for clave, texto in PAPELES_NUEVA:
            self.papel.addItem(texto, clave)
        self.tipo = QComboBox()
        for t, texto in TIPOS_VARIABLE:
            if t["kind"] == "bool" or not solo_booleana:  # una continua solo escribe booleanas
                self.tipo.addItem(texto, t)
        f.addRow("Nombre", self.nombre)
        f.addRow("Papel", self.papel)
        f.addRow("Tipo", self.tipo)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self.msg.setStyleSheet(f"color: {COL['err']}")
        lay.addWidget(self.msg)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

    def aceptar(self) -> None:
        nombre = self.nombre.text().strip()
        motivo = ("Escriba el nombre de la variable." if not nombre else Edicion.motivo_nombre(nombre)
                  or (f"Ya existe una variable «{nombre}»." if nombre in self.existentes else None))
        if motivo:
            self.msg.setText(motivo)
            return
        self.resultado = (nombre, self.papel.currentData(), dict(self.tipo.currentData()))
        self.accept()


class PanelAccion(QWidget):
    """Las opciones de la acción mostrada: frase, tipo, variable y límite (esta columna) y, en `caja_valor` (que la ventana
    del panel coloca a su lado), las plantillas y el programador del valor de una memorizada. Cada cambio se aplica en el
    acto con la edición; `mostrar(e, aid)` rellena los campos con lo que hay, sin tocar lo que se está escribiendo."""

    def __init__(self) -> None:
        super().__init__()
        self.e: Any = None
        self.aid: str | None = None
        self.sid: str | None = None
        self._llenando = False
        self._sync = False  # el texto del valor lo está escribiendo el programador
        self._elegida = ""
        self._rechazado: tuple[str, str] | None = None  # (acción, aviso): lo último escrito que no se pudo guardar
        self._firma: tuple | None = None
        self.al_volver: Callable[[], Any] | None = None  # la ventana vuelve a las opciones de la etapa
        self.parpadeo = Parpadeo(self)  # el campo que no vale parpadea en naranja
        self.parpadeo.cambia.connect(self._pintar)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.b_etapa = QPushButton()
        self.b_etapa.setToolTip("Volver a las opciones de la etapa")
        self.b_etapa.clicked.connect(lambda: self.al_volver and self.al_volver())
        lay.addWidget(self.b_etapa, 0, Qt.AlignmentFlag.AlignLeft)
        self.frase = QLabel()
        self.frase.setWordWrap(True)
        self.frase.setStyleSheet("font-weight: 600")
        lay.addWidget(self.frase)
        f = QFormLayout()
        f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        lay.addLayout(f)
        self.tipo = QComboBox()
        self.tipo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tipo.setMinimumContentsLength(8)
        self.tipo.activated.connect(self._elegir_tipo)
        f.addRow("Tipo", self.tipo)
        self.variable = _ComboVariable()
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
        # El valor de una memorizada: plantillas, y fichas 1/0 (booleana) o programador de valor (numérica)
        self.caja_valor = QWidget()
        vl = QVBoxLayout(self.caja_valor)
        vl.setContentsMargins(0, 0, 0, 0)
        self.fila_plantillas = QHBoxLayout()
        self.fila_plantillas.setContentsMargins(0, 0, 0, 0)
        self.plantillas: dict[str, QPushButton] = {}
        self.fila_plantillas.addWidget(QLabel("Plantillas"))  # una vez; los botones se ponen entre ella y el estiramiento
        self.fila_plantillas.addStretch(1)
        vl.addLayout(self.fila_plantillas)
        self.caja_fichas = QWidget()
        fl = QHBoxLayout(self.caja_fichas)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(QLabel("Valor :="))
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
                                ampliable=False, valor=True)
        self.prog.cambiado.connect(self._desde_bloques)
        self.prog.al_deshacer = lambda: self.e is not None and self.e.deshacer()  # Ctrl+Z deshace la operación
        self.prog.al_rehacer = lambda: self.e is not None and self.e.rehacer()
        nl.addWidget(self.prog, 1)
        fila = QHBoxLayout()
        self.valor = QLineEdit()  # el texto del valor: solo se ve; «Escribir a mano» lo deja editar
        self.valor.setReadOnly(True)
        self.valor.setPlaceholderText("el valor se arma con bloques (CT + 1, 5…)")
        self.valor.textChanged.connect(self._valor_cambiado)
        self.valor.textEdited.connect(lambda t: self.prog.poner(t))
        self.valor.editingFinished.connect(lambda: self._aplicar("valor"))
        self.manual = QCheckBox("Escribir a mano")
        self.manual.setToolTip("Dejar editar el texto del valor (CT + 1, 5…); lo escrito pasa a bloques")
        self.manual.toggled.connect(lambda on: self.valor.setReadOnly(not on))
        fila.addWidget(QLabel("Valor (:=)"))
        fila.addWidget(self.valor, 1)
        fila.addWidget(self.manual)
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
        if otra:
            self.manual.setChecked(False)
            self.valor.setReadOnly(True)
        if otra:  # otra acción: lo escrito sin confirmar en un campo se descarta (nunca se aplica a la nueva)
            for campo in (self.valor, self.limite):
                campo.blockSignals(True)
                campo.clearFocus()
                campo.blockSignals(False)
        self._llenando = True
        esperado = ["limitada" if (c == "condicionada" and d["tipo"] == "limitada") else c for c, _ in TIPOS]
        if [self.tipo.itemData(i) for i in range(self.tipo.count())] != esperado:
            self.tipo.clear()
            for clave, texto in TIPOS:
                if clave == "condicionada" and d["tipo"] == "limitada":  # la de un fichero antiguo lleva límite de tiempo
                    self.tipo.addItem(TEXTO_LIMITADA, "limitada")
                else:
                    self.tipo.addItem(texto, clave)
        self.tipo.setCurrentIndex(max(0, self.tipo.findData(d["tipo"])))
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
        self.b_etapa.setText(f"‹ Etapa {e.nombres.get(self.sid, self.sid)}" if self.sid else "")
        self._ajustar()
        if self._rechazado is None:
            self.prog.poner(self.valor.text())

    def _variables(self) -> dict[str, tuple[str, str]]:
        """Las variables del modelo {nombre: (papel, tipo)}."""
        return dict(self.e.fuente_bloques()[0]) if self.e is not None else {}

    def ofrecidas(self) -> list[str]:
        """Las variables que esta acción puede escribir: nunca entradas; una continua, solo booleanas."""
        continua = self.tipo.currentData() in CONTINUAS
        return [n for n, (papel, tipo) in self._variables().items() if papel != "input" and (tipo == "bool" or not continua)]

    def poner_variable(self, nombre: str) -> None:
        """Elige una variable por su nombre (si no existe, no hace nada) y lo aplica."""
        if nombre.strip() in self._variables():
            self._elegida = nombre.strip()
            self._rellenar_variables()
            self._aplicar("variable")

    def _rellenar_variables(self) -> None:
        """La lista: Salidas y luego Memorias (con su tipo), la variable elegida aunque no valga para este tipo (se avisa) y,
        al final, «Nueva variable…». Solo se rehace si cambió algo."""
        v, ofrecidas = self._variables(), self.ofrecidas()
        firma = (tuple(v.items()), self._elegida, self.tipo.currentData())
        if firma == self._firma:
            return
        self._firma = firma
        c = self.variable
        c.blockSignals(True)
        c.clear()
        if not self._elegida:
            c.addItem("Elija la variable…", "")
        for papel, titulo in (("output", "Salidas"), ("internal", "Memorias")):
            nombres = [n for n in ofrecidas if v[n][0] == papel]
            if nombres:
                c.addItem(titulo, None)
                c.model().item(c.count() - 1).setEnabled(False)
            for n in nombres:
                c.addItem(f"   {n}  ({nombre_tipo({'kind': v[n][1]})})", n)
        if self._elegida and self._elegida not in ofrecidas:  # una entrada, o no booleana en una continua
            c.addItem(f"{self._elegida}  (no se puede escribir aquí)", self._elegida)
        c.addItem("Nueva variable…", NUEVA)
        c.setCurrentIndex(max(0, c.findData(self._elegida)))
        c.blockSignals(False)

    def _tipo_variable(self) -> str:
        """El tipo (bool, int…) de la variable elegida; vacío si no hay."""
        return self._variables().get(self._elegida, ("", ""))[1]

    def _ajustar(self) -> None:
        """Muestra solo lo que pide el tipo y el de la variable; pone al día la lista, las plantillas y la frase."""
        clave = self.tipo.currentData()
        continua = clave in CONTINUAS
        for w in (self.l_limite, self.limite):
            w.setVisible(clave == "limitada")
        self._rellenar_variables()
        self.caja_valor.setVisible(not continua)
        booleana = self._tipo_variable() == "bool"
        self.caja_fichas.setVisible(not continua and booleana)
        self.caja_numerica.setVisible(not continua and not booleana)
        self.prog.refrescar()
        self._plantillas(booleana)
        self._previsualizar()

    def _plantillas(self, booleana: bool) -> None:
        """Las plantillas de un clic: «:= 1» y «:= 0» (booleana); «+1», «−1» y «:= 0» (numérica: V + 1, V - 1, 0)."""
        v = self._elegida or "V"
        opciones = ((":= 1", "1"), (":= 0", "0")) if booleana else (("+1", f"{v} + 1"), ("−1", f"{v} - 1"), (":= 0", "0"))
        if [(t, b.toolTip()) for t, b in self.plantillas.items()] == [(t, f"Valor: {val}") for t, val in opciones]:
            return
        for b in self.plantillas.values():
            self.fila_plantillas.removeWidget(b)
            b.hide()
            b.setParent(None)
            b.deleteLater()
        self.plantillas = {}
        for i, (texto, valor) in enumerate(opciones):
            b = QPushButton(texto)
            b.setToolTip(f"Valor: {valor}")
            b.clicked.connect(lambda _=False, valor=valor: self._poner_valor(valor))
            self.fila_plantillas.insertWidget(1 + i, b)
            self.plantillas[texto] = b

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
        nombre, tipo = self._elegida, self.tipo.currentData()
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
    def _elegir_tipo(self, _: int = 0) -> None:
        if self.e is not None and self.aid is not None:
            self.e.tipo_accion(self.aid, self.tipo.currentData())

    def _elegir_variable(self, _: int = 0) -> None:
        if self.variable.currentData() == NUEVA:
            if not self.nueva_variable():
                self._firma = None
                self._rellenar_variables()  # canceló: vuelve a la que había
            return
        self._elegida = self.variable.currentText()
        self._aplicar("variable")

    def nueva_variable(self, nombre: str | None = None, papel: str = "output", tipo: dict[str, Any] | None = None) -> bool:
        """«Nueva variable…»: pide nombre, papel y tipo (o los toma de los argumentos), la crea y la elige en la misma
        operación de deshacer. Devuelve si se hizo."""
        continua = self.tipo.currentData() in CONTINUAS
        if nombre is None:
            dlg = DialogoVariableNueva(self, set(self._variables()), solo_booleana=continua)
            if dlg.exec() != QDialog.DialogCode.Accepted or dlg.resultado is None:
                return False
            nombre, papel, tipo = dlg.resultado
        if continua and (tipo or {"kind": "bool"})["kind"] != "bool":
            return False  # una continua solo escribe booleanas
        self._elegida = nombre
        return self._aplicar("variable", (papel, dict(tipo or {"kind": "bool"})))

    def _poner_valor(self, texto: str) -> None:
        self.valor.setText(texto)
        self._aplicar("valor")

    def _desde_bloques(self, texto: str) -> None:
        self._sync = True
        self.valor.setText(texto)
        self._sync = False
        self._aplicar("valor")

    def _valor_cambiado(self, texto: str) -> None:
        """El texto del valor cambió (plantilla, ficha, bloques o a mano): las fichas siguen al texto y la frase también."""
        t = texto.strip()
        for v, b in self.fichas.items():
            b.setChecked(t == v)
        if not self._llenando and self.e is not None and self.aid is not None:
            self.frase.setText(self.frase_explicativa())

    def _aplicar(self, campo: str = "", crear: tuple[str, Any] | None = None) -> bool:
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
        motivo = self.e.cambiar_accion(self.aid, d, crear)
        if motivo:
            self._rechazado = (antes, motivo)
            self._previsualizar()
            self.parpadeo.iniciar({campo or "variable"})
            return False
        self._rechazado = None
        if self._reparo():  # la variable no vale para este tipo: se aplica, y el aviso (naranja) parpadea
            self.parpadeo.iniciar({"variable"})
        return True

    def _pintar(self) -> None:
        """Colorea de naranja el campo que parpadea mientras dura la fase encendida."""
        activos = self.parpadeo.activos()
        for clave, w in (("variable", self.variable), ("valor", self.valor), ("limite", self.limite)):
            w.setStyleSheet(f"background: {COL['glow']}" if clave in activos else "")
