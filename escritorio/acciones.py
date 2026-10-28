"""Diálogo para añadir o cambiar una acción de una etapa (paso 4, P-IMP-38).

Una acción continua pone a 1 una variable booleana mientras la etapa está activa (y, si lleva condición, mientras
la condición se cumple). Una memorizada asigna un valor al activar la etapa, al desactivarla o con un evento mientras
está activa (por ejemplo CT := CT + 1 con ↑I02). La condición y el evento no se escriben aquí: se programan con bloques
en la pestaña «Bloques» del panel inferior (P-IMP-43). Todo lo hace Edicion.poner_accion con las operaciones de
grafcet/editor.py.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
                               QWidget)

from .diagrama import COL
from .edicion import CONTINUAS, TEXTO_LIMITADA, Parpadeo

TIPOS = (("continua", "Continua: mientras la etapa está activa"),
         ("condicionada", "Condicionada: continua que exige una condición (se programa en la pestaña Bloques)"),
         ("activacion", "Memorizada al activar la etapa (↑)"),
         ("desactivacion", "Memorizada al desactivar la etapa (↓)"),
         ("evento", "Memorizada con un evento, mientras está activa (banderita; el evento se programa en la pestaña Bloques)"))
CREAR = (("output", "bool", "Salida booleana"), ("internal", "bool", "Memoria booleana"),
         ("internal", "int", "Memoria entera (contador)"), ("output", "int", "Salida entera"))


class DialogoAccion(QDialog):
    """Variable, tipo, valor y límite de tiempo de una acción. La condición y el evento no se escriben aquí: se programan
    con bloques en la pestaña «Bloques» del panel inferior al seleccionar la acción (el diálogo los conserva)."""

    def __init__(self, parent: QWidget | None, edicion: Any, sid: str, aid: str | None = None) -> None:
        super().__init__(parent)
        self.e, self.sid, self.aid = edicion, sid, aid
        etapa = edicion.nombres.get(sid, sid)
        suelta = sid is None
        self.setWindowTitle("Acción suelta" if suelta else f"{'Cambiar' if aid else 'Añadir'} acción — etapa {etapa}")
        self.setMinimumWidth(620)
        self.resize(660, 330)
        self._condicion, self._evento = "", ""  # lo que el diálogo no edita
        d = edicion.datos_accion(aid) if aid else {"tipo": "continua"}
        lay = QVBoxLayout(self)
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
        self.variable = QComboBox()
        self.variable.setEditable(True)
        self.variable.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.variable.currentTextChanged.connect(self._ajustar)
        f.addRow("Variable", self.variable)
        self.parpadeo = Parpadeo(self)  # la variable parpadea si su nombre no vale
        self.parpadeo.cambia.connect(lambda: self.variable.setStyleSheet(
            f"QComboBox {{ background: {COL['glow']} }}" if self.parpadeo.activos() else ""))
        self.crear = QComboBox()
        for papel, tipo, texto in CREAR:
            self.crear.addItem(texto, f"{papel}:{tipo}")
        self.l_crear = QLabel("No existe: crearla como")
        f.addRow(self.l_crear, self.crear)
        self.l_limite = QLabel("Límite de tiempo (3s, 500ms…; vacío: sin límite)")
        self.limite = QLineEdit()
        self.limite.setPlaceholderText("3s")
        f.addRow(self.l_limite, self.limite)
        self.valor = QLineEdit()
        self.valor.setPlaceholderText("1, 0, 5, CT + 1…")
        self.l_valor = QLabel("Valor (:=)")
        f.addRow(self.l_valor, self.valor)
        self.l_bloques = QLabel("La condición (o el evento) se programa con bloques en la pestaña «Bloques» del panel "
                                "inferior, al seleccionar la acción.")
        self.l_bloques.setWordWrap(True)
        self.l_bloques.setStyleSheet(f"color: {COL['muted']}")
        f.addRow(self.l_bloques)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self._avisado: tuple | None = None  # los datos con que se mostró el aviso de «guardar como borrador»
        self.valor.textChanged.connect(self._previsualizar)
        self.limite.textChanged.connect(self._previsualizar)
        lay.addWidget(self.msg)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)
        if aid:
            self.tipo.setCurrentIndex(max(0, self.tipo.findData(d["tipo"])))
            self.variable.setCurrentText(d["variable"])
            self.valor.setText(d.get("valor", ""))
            self.limite.setText(d.get("limite", ""))
            self._condicion, self._evento = d.get("condicion", ""), d.get("evento", "")
        self._ajustar()

    def _variables(self) -> dict[str, tuple[str, str]]:
        return self.e.fuente_bloques()[0]

    def _ajustar(self) -> None:
        """Muestra solo lo que pide el tipo; la lista ofrece las variables que se pueden escribir (no las entradas;
        una continua, solo booleanas)."""
        clave = self.tipo.currentData()
        continua = clave in CONTINUAS
        for w in (self.l_limite, self.limite):
            w.setVisible(clave == "limitada")
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
        self.l_bloques.setVisible(clave in ("condicionada", "limitada", "evento"))
        booleana = (self._variables()[texto.strip()][1] if existe else self._crear_como()[1]) == "bool"
        self.valor.setPlaceholderText("1 o 0" if booleana else "5, CT + 1…")
        self._previsualizar()

    def _previsualizar(self) -> None:
        """El aviso si un X… del valor (o de la condición o el evento que ya tenía) puede ser dos etapas."""
        if not hasattr(self, "_avisado"):
            return
        d = self.datos()
        continua = d["tipo"] in CONTINUAS
        aviso = self.e.aviso_ambiguas(d["condicion"] if continua else "", d["evento"] if d["tipo"] == "evento" else "",
                                      d["valor"] if not continua else "")
        if self._avisado != tuple(d.items()):  # cambiar algo reinicia el aviso de «guardar como borrador»
            self._avisado = None
            self.msg.setText(aviso)
            self.msg.setStyleSheet(f"color: {COL['glow']}")

    def _crear_como(self) -> tuple[str, str]:
        """Papel y tipo con que se crea la variable si no existe."""
        papel, tipo = (self.crear.currentData() or "output:bool").split(":")
        return papel, tipo

    def datos(self) -> dict[str, str]:
        tipo, limite = self.tipo.currentData(), self.limite.text().strip()
        condicion = "" if tipo == "continua" else self._condicion
        if tipo == "limitada" and not limite:  # quitar el límite: queda una condicionada (o una continua, sin condición)
            tipo = "condicionada" if condicion else "continua"
        return {"tipo": tipo, "variable": self.variable.currentText().strip(), "condicion": condicion,
                "valor": self.valor.text().strip(), "evento": self._evento, "limite": limite if tipo == "limitada" else ""}

    def _reparo(self) -> str:
        """Por qué la variable escrita a mano no sirve para este tipo de acción (se guarda como borrador)."""
        nombre, tipo = self.variable.currentText().strip(), self.tipo.currentData()
        if nombre not in self._variables():
            return ""
        papel, kind = self._variables()[nombre]
        if papel == "input":
            return f"«{nombre}» es una entrada: una acción no puede escribirla"
        if tipo in CONTINUAS and kind != "bool":
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
            if "nombre de variable" in motivo:  # el nombre no se puede escribir en una fórmula
                self.parpadeo.iniciar({"variable"})
            return
        self.accept()
