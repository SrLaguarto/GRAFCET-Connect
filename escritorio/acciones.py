"""Diálogo para añadir o cambiar una acción de una etapa (paso 4, P-IMP-38, P-IMP-43, P-IMP-44).

Una acción continua pone a 1 una variable booleana mientras la etapa está activa (y, si lleva condición, mientras la
condición se cumple). Una memorizada asigna un valor al activar la etapa, al desactivarla o con un evento mientras
está activa (por ejemplo CT := CT + 1 con ↑I02). Arriba, una frase explica la acción en lenguaje claro.

- La variable se elige en una lista (nunca entradas): una continua ofrece las salidas y memorias booleanas; una
  memorizada, las salidas y memorias de cualquier tipo, por papel. «Nueva variable…» la crea (se declara al aceptar,
  en la misma operación de deshacer que la acción).
- El valor de una memorizada se programa con un programador de valor tipo Scratch, como el de bloques pero más corto:
  una booleana elige entre las fichas «1» y «0»; una numérica arma `CT + 1`, `5` o `CT * 2 - 1` con un número,
  variables numéricas y los operadores +, −, ×, ÷. El texto sigue siendo lo que se guarda y lo que el núcleo analiza.
- La condición y el evento no se escriben aquí: el diálogo los muestra en una línea y «Programar con bloques abajo»
  cierra el diálogo y abre la pestaña «Bloques» con ellos (P-IMP-43).

Todo lo hace Edicion.poner_accion con las operaciones de grafcet/editor.py.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from grafcet.view import norm

from .bloques import COLORES, Programador
from .diagrama import COL, _html
from .edicion import CON_CONDICION, CONTINUAS, TEXTO_LIMITADA, Edicion
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


class DialogoAccion(QDialog):
    """Variable, tipo y valor de una acción, con su frase explicativa. La condición y el evento se programan con bloques
    en la pestaña «Bloques» del panel inferior (el diálogo los muestra y los conserva)."""

    def __init__(self, parent: QWidget | None, edicion: Any, sid: str, aid: str | None = None) -> None:
        super().__init__(parent)
        self.e, self.sid, self.aid = edicion, sid, aid
        self.etapa = edicion.nombres.get(sid, sid)
        suelta = sid is None
        self.setWindowTitle("Acción suelta" if suelta else f"{'Cambiar' if aid else 'Añadir'} acción — etapa {self.etapa}")
        self.setMinimumWidth(640)
        self.resize(700, 600)
        self._condicion, self._evento = "", ""  # lo que el diálogo no edita
        self._nueva: tuple[str, str, dict[str, Any]] | None = None  # la variable que «Nueva variable…» creará al aceptar
        self._elegida = ""
        self._sync = False  # el texto del valor lo está escribiendo el programador
        self.programar = False  # «Programar con bloques abajo» se pulsó
        self.al_programar: Callable[[], Any] | None = None  # la ventana abre la pestaña Bloques
        d = edicion.datos_accion(aid) if aid else {"tipo": "continua"}
        lay = QVBoxLayout(self)
        self.frase = QLabel()
        self.frase.setWordWrap(True)
        self.frase.setStyleSheet("font-weight: 600")
        lay.addWidget(self.frase)
        f = QFormLayout()
        f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        lay.addLayout(f)
        self.tipo = QComboBox()
        for clave, texto in TIPOS:
            if clave == "condicionada" and d["tipo"] == "limitada":  # la de un fichero antiguo lleva límite de tiempo
                self.tipo.addItem(TEXTO_LIMITADA, "limitada")
            else:
                self.tipo.addItem(texto, clave)
        self.tipo.currentIndexChanged.connect(self._ajustar)
        f.addRow("Tipo", self.tipo)
        self.variable = _ComboVariable()
        self.variable.al_poner = self.poner_variable
        self.variable.activated.connect(self._elegir_variable)
        f.addRow("Variable", self.variable)
        self.l_limite = QLabel("Límite de tiempo (3s, 500ms…; vacío: sin límite)")
        self.limite = QLineEdit()
        self.limite.setPlaceholderText("3s")
        f.addRow(self.l_limite, self.limite)
        # La condición o el evento que hay, en una línea, y el paso a la pestaña Bloques
        self.caja_cond = QWidget()
        hl = QHBoxLayout(self.caja_cond)
        hl.setContentsMargins(0, 0, 0, 0)
        self.l_cond = QLabel()
        self.l_cond.setTextFormat(Qt.TextFormat.RichText)
        self.l_cond.setWordWrap(True)
        hl.addWidget(self.l_cond, 1)
        self.b_programar = QPushButton("Programar con bloques abajo")
        self.b_programar.setToolTip("Cierra este diálogo y abre la pestaña Bloques con la condición o el evento de la acción")
        self.b_programar.clicked.connect(lambda: self.aceptar(programar=True))
        hl.addWidget(self.b_programar)
        lay.addWidget(self.caja_cond)
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
            b.clicked.connect(lambda _=False, v=v: self.valor.setText(v))
            self.grupo_fichas.addButton(b)
            self.fichas[v] = b
            fl.addWidget(b)
        fl.addStretch(1)
        vl.addWidget(self.caja_fichas)
        self.caja_numerica = QWidget()
        nl = QVBoxLayout(self.caja_numerica)
        nl.setContentsMargins(0, 0, 0, 0)
        self.prog = Programador(lambda: (self._variables(), self.e.fuente_bloques()[1]), ampliable=False, valor=True)
        self.prog.cambiado.connect(self._desde_bloques)
        nl.addWidget(self.prog, 1)
        fila = QHBoxLayout()
        self.valor = QLineEdit()  # el texto del valor: solo se ve; «Escribir a mano» lo deja editar
        self.valor.setReadOnly(True)
        self.valor.setPlaceholderText("el valor se arma con bloques (CT + 1, 5…)")
        self.manual = QCheckBox("Escribir a mano")
        self.manual.setToolTip("Dejar editar el texto del valor (CT + 1, 5…); lo escrito pasa a bloques")
        self.manual.toggled.connect(lambda on: self.valor.setReadOnly(not on))
        fila.addWidget(QLabel("Valor (:=)"))
        fila.addWidget(self.valor, 1)
        fila.addWidget(self.manual)
        nl.addLayout(fila)
        vl.addWidget(self.caja_numerica, 1)
        lay.addWidget(self.caja_valor, 1)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self._avisado: tuple | None = None  # los datos con que se mostró el aviso de «guardar como borrador»
        self.valor.textChanged.connect(self._valor_cambiado)
        self.limite.textChanged.connect(self._previsualizar)
        lay.addWidget(self.msg)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)
        if aid:
            self.tipo.blockSignals(True)
            self.tipo.setCurrentIndex(max(0, self.tipo.findData(d["tipo"])))
            self.tipo.blockSignals(False)
            self._elegida = d["variable"] if d["variable"] in self._variables() else ""
            self.valor.setText(d.get("valor", ""))
            self.limite.setText(d.get("limite", ""))
            self._condicion, self._evento = d.get("condicion", ""), d.get("evento", "")
        self._ajustar()

    # -- variables ---------------------------------------------------------------------------------
    def _variables(self) -> dict[str, tuple[str, str]]:
        """Las variables del modelo y, si «Nueva variable…» la pidió, la que se creará al aceptar."""
        v = dict(self.e.fuente_bloques()[0])
        if self._nueva and self._nueva[0] not in v:
            v[self._nueva[0]] = (self._nueva[1], self._nueva[2]["kind"])
        return v

    def ofrecidas(self) -> list[str]:
        """Las variables que esta acción puede escribir: nunca entradas; una continua, solo booleanas."""
        continua = self.tipo.currentData() in CONTINUAS
        return [n for n, (papel, tipo) in self._variables().items()
                if papel != "input" and (tipo == "bool" or not continua)]

    def poner_variable(self, nombre: str) -> None:
        """Elige una variable por su nombre (si no existe, queda sin elegir)."""
        self._elegida = nombre.strip() if nombre.strip() in self._variables() else ""
        self._ajustar()

    def _rellenar_variables(self) -> None:
        """La lista: Salidas y luego Memorias (con su tipo), la variable elegida aunque no valga para este tipo (se avisa
        al aceptar) y, al final, «Nueva variable…»."""
        v, ofrecidas = self._variables(), self.ofrecidas()
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

    def _elegir_variable(self, _: int = 0) -> None:
        if self.variable.currentData() == NUEVA:
            if not self.nueva_variable():
                self._rellenar_variables()  # canceló: vuelve a la que había
            return
        self._elegida = self.variable.currentText()
        self._ajustar()

    def nueva_variable(self, nombre: str | None = None, papel: str = "output", tipo: dict[str, Any] | None = None) -> bool:
        """«Nueva variable…»: pide nombre, papel y tipo (o los toma de los argumentos) y la elige; se declara al aceptar,
        en la misma operación que la acción. Devuelve si se eligió una."""
        continua = self.tipo.currentData() in CONTINUAS
        if nombre is None:
            dlg = DialogoVariableNueva(self, set(self._variables()), solo_booleana=continua)
            if dlg.exec() != QDialog.DialogCode.Accepted or dlg.resultado is None:
                return False
            nombre, papel, tipo = dlg.resultado
        if continua and (tipo or {"kind": "bool"})["kind"] != "bool":
            return False  # una continua solo escribe booleanas
        self._nueva = (nombre, papel, dict(tipo or {"kind": "bool"}))
        self._elegida = nombre
        self._ajustar()
        return True

    def _tipo_variable(self) -> str:
        """El tipo (bool, int…) de la variable elegida; vacío si no hay."""
        return self._variables().get(self._elegida, ("", ""))[1]

    # -- lo que se ve según el tipo ----------------------------------------------------------------------
    def _ajustar(self, _: int = 0) -> None:
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
        self._linea_condicion()
        self._previsualizar()

    def _plantillas(self, booleana: bool) -> None:
        """Las plantillas de un clic: «:= 1» y «:= 0» (booleana); «+1», «−1» y «:= 0» (numérica: V + 1, V - 1, 0)."""
        for b in self.plantillas.values():
            self.fila_plantillas.removeWidget(b)
            b.hide()
            b.setParent(None)
            b.deleteLater()
        self.plantillas = {}
        v = self._elegida or "V"
        opciones = ((":= 1", "1"), (":= 0", "0")) if booleana else (("+1", f"{v} + 1"), ("−1", f"{v} - 1"), (":= 0", "0"))
        for i, (texto, valor) in enumerate(opciones):
            b = QPushButton(texto)
            b.setToolTip(f"Valor: {valor}")
            b.clicked.connect(lambda _=False, valor=valor: self.valor.setText(valor))
            self.fila_plantillas.insertWidget(1 + i, b)
            self.plantillas[texto] = b

    def _linea_condicion(self) -> None:
        """«Condición: marcha·paro» (con el dibujo de la norma), «Evento: ↑I02» o «Condición: siempre (continua)»."""
        clave = self.tipo.currentData()
        evento = clave == "evento"
        self.caja_cond.setVisible(clave in CONTINUAS or evento)
        self.b_programar.setVisible(evento or clave in CON_CONDICION)
        texto = self._evento if evento else self._condicion
        if clave == "continua":
            self.l_cond.setText("Condición: siempre (continua)")
        elif not texto:
            self.l_cond.setText(f"{'Evento' if evento else 'Condición'}: sin programar "
                                "(hasta entonces la acción queda como borrador)")
        else:
            self.l_cond.setText(f"{'Evento' if evento else 'Condición'}: {self._dibujo(texto)}")

    def _dibujo(self, texto: str) -> str:
        """El texto de una condición o evento con el dibujo de la norma, si se interpreta; si no, el texto."""
        import html
        try:
            if self.e.comprobar(self.sid or "", texto) is None and not self.e.sin_declarar(self.sid or "", texto):
                return _html(norm(self.e.significado(self.sid or "", texto), True, self.e.nombres))
        except Exception:  # noqa: BLE001 - un texto a medias no debe romper el diálogo
            pass
        return html.escape(texto)

    def frase_explicativa(self) -> str:
        """La acción en lenguaje claro, según su tipo."""
        d = self.datos()
        etapa = f"la etapa {self.etapa}" if self.sid else "la etapa a la que se una"
        var = d["variable"] or "?"
        if d["tipo"] in CONTINUAS:
            cond = " (y se cumpla la condición)" if d["tipo"] in CON_CONDICION else ""
            lim = f", como mucho durante {d['limite']}" if d["tipo"] == "limitada" else ""
            return f"Mientras {etapa} esté activa{cond}{lim}, {var} vale 1."
        asignacion = f"{var} := {d['valor'] or '?'}"
        if d["tipo"] == "activacion":
            return f"Al activarse {etapa}: {asignacion}."
        if d["tipo"] == "desactivacion":
            return f"Al desactivarse {etapa}: {asignacion}."
        return f"Con cada {d['evento'] or 'evento sin programar'} mientras {etapa} está activa: {asignacion}."

    # -- el valor ----------------------------------------------------------------------------------------
    def _desde_bloques(self, texto: str) -> None:
        self._sync = True
        self.valor.setText(texto)
        self._sync = False

    def _valor_cambiado(self, texto: str) -> None:
        """El texto del valor cambió (plantilla, ficha, bloques o a mano): las fichas y los bloques lo siguen."""
        t = texto.strip()
        for v, b in self.fichas.items():
            b.setChecked(t == v)
        if not self._sync:
            self.prog.poner(texto)
        self._previsualizar()

    def _previsualizar(self) -> None:
        """La frase y el aviso si un X… del valor (o de la condición o el evento que ya tenía) puede ser dos etapas."""
        if not hasattr(self, "_avisado"):
            return
        self.frase.setText(self.frase_explicativa())
        d = self.datos()
        continua = d["tipo"] in CONTINUAS
        aviso = self.e.aviso_ambiguas(d["condicion"] if continua else "", d["evento"] if d["tipo"] == "evento" else "",
                                      d["valor"] if not continua else "")
        if self._avisado != tuple(d.items()):  # cambiar algo reinicia el aviso de «guardar como borrador»
            self._avisado = None
            self.msg.setText(aviso)
            self.msg.setStyleSheet(f"color: {COL['glow']}")

    def _crear_como(self) -> tuple[str, dict[str, Any]] | None:
        """Papel y tipo con que se declara la variable elegida, si es la de «Nueva variable…» y aún no existe."""
        n = self._nueva
        if n and self._elegida == n[0] and n[0] not in self.e.fuente_bloques()[0]:
            return n[1], n[2]
        return None

    def datos(self) -> dict[str, str]:
        tipo, limite = self.tipo.currentData(), self.limite.text().strip()
        condicion = "" if tipo == "continua" else self._condicion
        if tipo == "limitada" and not limite:  # quitar el límite: queda una condicionada (o una continua, sin condición)
            tipo = "condicionada" if condicion else "continua"
        return {"tipo": tipo, "variable": self.variable.currentText().strip(), "condicion": condicion,
                "valor": self.valor.text().strip(), "evento": self._evento, "limite": limite if tipo == "limitada" else ""}

    def _reparo(self) -> str:
        """Por qué la variable elegida no sirve para este tipo de acción (se guarda como borrador)."""
        nombre, tipo = self.variable.currentText().strip(), self.tipo.currentData()
        if nombre not in self._variables():
            return ""
        papel, kind = self._variables()[nombre]
        if papel == "input":
            return f"«{nombre}» es una entrada: una acción no puede escribirla"
        if tipo in CONTINUAS and kind != "bool":
            return f"una acción continua necesita una variable booleana y «{nombre}» no lo es"
        return ""

    def aceptar(self, programar: bool = False) -> None:
        reparo = self._reparo()
        if reparo and self._avisado != tuple(self.datos().items()):
            self._avisado = tuple(self.datos().items())
            self.msg.setText(f"{reparo}. Se guardará como borrador y la validación lo señalará; "
                             "pulse Aceptar otra vez para guardarla así.")
            self.msg.setStyleSheet(f"color: {COL['glow']}")
            return
        motivo = self.e.poner_accion(self.sid, self.datos(), self.aid, self._crear_como())
        if motivo:
            self.msg.setText(motivo)
            self.msg.setStyleSheet(f"color: {COL['err']}")
            return
        self.programar = programar
        if programar:
            self._señalar()
        self.accept()
        if programar and self.al_programar is not None:
            self.al_programar()

    def _señalar(self) -> None:
        """Deja señalada la acción guardada para que la pestaña Bloques programe su condición o su evento."""
        e = self.e
        if self.sid is None:  # suelta: ya la dejó señalada Edicion
            return
        acc = e.acciones(self.sid)
        if not acc:
            return
        e.accion = self.aid if any(a["id"] == self.aid for a in acc) else acc[-1]["id"]
        e.sel = [self.sid]
        e.cambiado.emit()
