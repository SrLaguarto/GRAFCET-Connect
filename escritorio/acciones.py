"""Diálogo para añadir o cambiar una acción de una etapa (paso 4, P-IMP-38).

Una acción continua pone a 1 una variable booleana mientras la etapa está activa (y, si lleva condición, mientras
la condición se cumple). Una memorizada asigna un valor al activar la etapa, al desactivarla o con un evento mientras
está activa (por ejemplo CT := CT + 1 con ↑I02). La condición y el evento se escriben con el programador por bloques;
todo lo hace Edicion.poner_accion con las operaciones de grafcet/editor.py.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
                               QWidget)

from .bloques import Programador
from .diagrama import COL, _html

TIPOS = (("continua", "Continua: mientras la etapa está activa"),
         ("activacion", "Memorizada al activar la etapa (↑)"),
         ("desactivacion", "Memorizada al desactivar la etapa (↓)"),
         ("evento", "Memorizada con un evento, mientras está activa (banderita)"))
CREAR = (("output", "bool", "Salida booleana"), ("internal", "bool", "Memoria booleana"),
         ("internal", "int", "Memoria entera (contador)"), ("output", "int", "Salida entera"))


class DialogoAccion(QDialog):
    def __init__(self, parent: QWidget | None, edicion: Any, sid: str, aid: str | None = None) -> None:
        super().__init__(parent)
        self.e, self.sid, self.aid = edicion, sid, aid
        etapa = edicion.nombres.get(sid, sid)
        self.setWindowTitle(f"{'Cambiar' if aid else 'Añadir'} acción — etapa {etapa}")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        f = QFormLayout()
        f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        lay.addLayout(f)
        self.tipo = QComboBox()
        for clave, texto in TIPOS:
            self.tipo.addItem(texto, clave)
        self.tipo.currentIndexChanged.connect(self._ajustar)
        f.addRow("Tipo", self.tipo)
        self.variable = QComboBox()
        self.variable.setEditable(True)
        self.variable.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.variable.currentTextChanged.connect(self._ajustar)
        f.addRow("Variable", self.variable)
        self.crear = QComboBox()
        for papel, tipo, texto in CREAR:
            self.crear.addItem(texto, f"{papel}:{tipo}")
        self.l_crear = QLabel("No existe: crearla como")
        f.addRow(self.l_crear, self.crear)
        self.valor = QLineEdit()
        self.valor.setPlaceholderText("1, 0, 5, CT + 1…")
        self.l_valor = QLabel("Valor (:=)")
        f.addRow(self.l_valor, self.valor)
        self.l_cond = QLabel("Condición (vacía: siempre)")
        self.cond = Programador(edicion.fuente_bloques, historial=True)
        self.v_cond = QLabel()
        self.cond.cambiado.connect(self._previsualizar)
        f.addRow(self.l_cond)
        f.addRow(self.cond)
        f.addRow("En la norma", self.v_cond)
        self.l_evento = QLabel("Evento (por ejemplo ↑I02)")
        self.evento = Programador(edicion.fuente_bloques, historial=True)
        self.v_evento = QLabel()
        self.evento.cambiado.connect(self._previsualizar)
        f.addRow(self.l_evento)
        f.addRow(self.evento)
        f.addRow("En la norma", self.v_evento)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self._avisado: tuple | None = None  # los datos con que se mostró el aviso de «guardar como borrador»
        self.valor.textChanged.connect(self._previsualizar)
        lay.addWidget(self.msg)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)
        if aid:
            d = edicion.datos_accion(aid)
            self.tipo.setCurrentIndex(max(0, self.tipo.findData(d["tipo"])))
            self.variable.setCurrentText(d["variable"])
            self.valor.setText(d.get("valor", ""))
            self.cond.poner(d.get("condicion", ""))
            self.evento.poner(d.get("evento", ""))
        self._ajustar()

    def _variables(self) -> dict[str, tuple[str, str]]:
        return self.e.fuente_bloques()[0]

    def _ajustar(self) -> None:
        """Muestra solo lo que pide el tipo; la lista ofrece las variables que se pueden escribir (no las entradas;
        una continua, solo booleanas)."""
        clave = self.tipo.currentData()
        continua = clave == "continua"
        texto = self.variable.currentText()
        self.variable.blockSignals(True)
        self.variable.clear()
        for n, (papel, tipo) in self._variables().items():
            if papel != "input" and (tipo == "bool" or not continua):
                self.variable.addItem(n)
        self.variable.setCurrentText(texto)
        self.variable.blockSignals(False)
        existe = texto.strip() in self._variables()
        nueva = bool(texto.strip()) and not existe
        self.l_crear.setVisible(nueva)
        self.crear.setVisible(nueva)
        for w in (self.l_valor, self.valor):
            w.setVisible(not continua)
        for w in (self.l_cond, self.cond, self.v_cond):
            w.setVisible(continua)
        for w in (self.l_evento, self.evento, self.v_evento):
            w.setVisible(clave == "evento")
        booleana = (self._variables()[texto.strip()][1] if existe else self._crear_como()[1]) == "bool"
        self.valor.setPlaceholderText("1 o 0" if booleana else "5, CT + 1…")
        self._previsualizar()

    def _previsualizar(self) -> None:
        """La condición y el evento en la notación de la norma, y el aviso si un X… puede ser dos etapas."""
        if not hasattr(self, "_avisado"):
            return
        for programador, vista in ((self.cond, self.v_cond), (self.evento, self.v_evento)):
            vista.setText(_html(self.e.vista_norma(programador.texto())) or "<i>—</i>")
        d = self.datos()
        aviso = self.e.aviso_ambiguas(d["condicion"] if d["tipo"] == "continua" else "",
                                      d["evento"] if d["tipo"] == "evento" else "",
                                      d["valor"] if d["tipo"] != "continua" else "")
        if self._avisado != tuple(d.items()):  # cambiar algo reinicia el aviso de «guardar como borrador»
            self._avisado = None
            self.msg.setText(aviso)
            self.msg.setStyleSheet(f"color: {COL['glow']}")

    def _crear_como(self) -> tuple[str, str]:
        """Papel y tipo con que se crea la variable si no existe."""
        papel, tipo = (self.crear.currentData() or "output:bool").split(":")
        return papel, tipo

    def datos(self) -> dict[str, str]:
        return {"tipo": self.tipo.currentData(), "variable": self.variable.currentText().strip(),
                "condicion": self.cond.texto(), "valor": self.valor.text().strip(), "evento": self.evento.texto()}

    def _reparo(self) -> str:
        """Por qué la variable escrita a mano no sirve para este tipo de acción (se guarda como borrador)."""
        nombre, tipo = self.variable.currentText().strip(), self.tipo.currentData()
        if nombre not in self._variables():
            return ""
        papel, kind = self._variables()[nombre]
        if papel == "input":
            return f"«{nombre}» es una entrada: una acción no puede escribirla"
        if tipo == "continua" and kind != "bool":
            return f"una acción continua necesita una variable booleana y «{nombre}» no lo es"
        return ""

    def aceptar(self) -> None:
        nombre = self.variable.currentText().strip()
        crear = None if nombre in self._variables() else self._crear_como()
        reparo = self._reparo()
        if reparo and self._avisado != tuple(self.datos().items()):
            self._avisado = tuple(self.datos().items())
            self.msg.setText(f"{reparo}. Se guardará como borrador y la validación lo señalará; "
                             "pulse Aceptar otra vez para guardarla así.")
            self.msg.setStyleSheet(f"color: {COL['glow']}")
            return
        motivo = self.e.poner_accion(self.sid, self.datos(), self.aid, crear)
        if motivo:
            self.msg.setText(motivo)
            self.msg.setStyleSheet(f"color: {COL['err']}")
            return
        self.accept()
