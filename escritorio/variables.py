"""Panel «Variables» del editor: el diccionario del grafcet (REQ-EDT-07, paso 4, P-IMP-38).

Una fila por variable: nombre, papel (entrada, salida, memoria), tipo (booleana, entera, decimal con su escala,
duración), valor inicial (solo las entradas: las demás empiezan en 0, hoja 08, 1.5), unidad y cuántos usos tiene.
Todo cambio pasa por Edicion (rename, change_variable, add_variable, delete_variable del núcleo) y se deshace con
Ctrl+Z; si no se puede, el motivo sale debajo y la tabla vuelve a lo que hay.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .diagrama import COL

PAPELES = (("input", "Entrada"), ("output", "Salida"), ("internal", "Memoria"))
TIPOS = (({"kind": "bool"}, "Booleana"), ({"kind": "int"}, "Entera"), ({"kind": "decimal", "scale": 1}, "Decimal ,0"),
         ({"kind": "decimal", "scale": 2}, "Decimal ,00"), ({"kind": "decimal", "scale": 3}, "Decimal ,000"),
         ({"kind": "duration"}, "Duración"))
COLUMNAS = ["Nombre", "Papel", "Tipo", "Inicial", "Unidad", "Usos"]


def _texto_inicial(v: dict[str, Any]) -> str:
    x = v["initialValue"]
    return ("1" if x else "0") if isinstance(x, bool) else str(x)


class PanelVariables(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.e: Any = None
        self._ids: list[str] = []
        self._clave = ""
        self._llenando = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().hide()
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cab.setStretchLastSection(True)
        self.tabla.itemChanged.connect(self._editado)
        lay.addWidget(self.tabla, 1)
        fila = QHBoxLayout()
        self.b_nueva = QPushButton("Nueva variable")
        self.b_nueva.clicked.connect(self.nueva)
        self.b_quitar = QPushButton("Quitar")
        self.b_quitar.setToolTip("Solo si no se usa en ninguna receptividad ni acción")
        self.b_quitar.clicked.connect(self.quitar)
        fila.addWidget(self.b_nueva)
        fila.addWidget(self.b_quitar)
        fila.addStretch(1)
        lay.addLayout(fila)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

    def mostrar(self, e: Any) -> None:
        """Rellena la tabla con las variables del modelo en curso (si no se está escribiendo en ella)."""
        self.e = e
        if e is None or self.tabla.state() == QAbstractItemView.State.EditingState:
            return
        vs = e.variables()
        clave = repr([(v["id"], v["name"], v["role"], v["type"], v["initialValue"], v.get("unit"), v["usos"]) for v in vs])
        if clave == self._clave:  # nada cambió: no se rehace la tabla (se hace en cada clic del dibujo)
            return
        self._clave = clave
        actual = self._ids[self.tabla.currentRow()] if 0 <= self.tabla.currentRow() < len(self._ids) else None
        self._llenando = True
        for r in range(self.tabla.rowCount()):
            for c in (1, 2):
                viejo = self.tabla.cellWidget(r, c)
                if viejo is not None:
                    self.tabla.removeCellWidget(r, c)
                    viejo.hide()
        self.tabla.setRowCount(len(vs))
        self._ids = [v["id"] for v in vs]
        for r, v in enumerate(vs):
            for c, texto in enumerate((v["name"], None, None, _texto_inicial(v), v.get("unit", ""), str(v["usos"]))):
                if texto is None:
                    continue
                it = QTableWidgetItem(texto)
                editable = c in (0, 4) or (c == 3 and v["role"] == "input")
                if not editable:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if c == 3:
                        it.setToolTip("Las salidas y memorias empiezan en 0; otro valor, con una acción «al activar» en la etapa inicial")
                self.tabla.setItem(r, c, it)
            papel = QComboBox()
            for clave, texto in PAPELES:
                papel.addItem(texto, clave)
            papel.setCurrentIndex(max(0, papel.findData(v["role"])))
            papel.activated.connect(lambda _=0, vid=v["id"], cb=papel: self._cambiar(vid, role=cb.currentData()))
            self.tabla.setCellWidget(r, 1, papel)
            tipo = QComboBox()
            for t, texto in TIPOS:
                tipo.addItem(texto, t)
            tipo.setCurrentIndex(next((i for i, (t, _) in enumerate(TIPOS) if t == {k: v["type"][k] for k in t}), 0))
            tipo.activated.connect(lambda _=0, vid=v["id"], cb=tipo: self._cambiar_tipo(vid, cb.currentData()))
            self.tabla.setCellWidget(r, 2, tipo)
        self._llenando = False
        if actual in self._ids:
            self.tabla.selectRow(self._ids.index(actual))

    def _resultado(self, motivo: str | None) -> None:
        self.msg.setText(motivo or "")
        self.msg.setStyleSheet(f"color: {COL['err']}" if motivo else "")
        if motivo:  # la tabla vuelve a lo que hay en el modelo
            self._clave = ""
            self.mostrar(self.e)

    def _cambiar(self, vid: str, **cambios: Any) -> None:
        self._resultado(self.e.cambiar_variable(vid, **cambios))

    def _cambiar_tipo(self, vid: str, tipo: dict[str, Any]) -> None:
        v = next(x for x in self.e.ed.model["variables"] if x["id"] == vid)
        inicial = {"bool": False}.get(tipo["kind"], "0")  # al cambiar de tipo, el valor inicial vuelve a 0
        self._cambiar(vid, type=dict(tipo), **({"initialValue": inicial} if v["role"] == "input" else {}))

    def _editado(self, it: QTableWidgetItem) -> None:
        if self._llenando or self.e is None:
            return
        vid, c, texto = self._ids[it.row()], it.column(), it.text().strip()
        if c == 0:
            self._resultado(self.e.cambiar_variable(vid, nombre=texto))
        elif c == 4:
            self._cambiar(vid, unit=texto)
        elif c == 3:
            v = next(x for x in self.e.ed.model["variables"] if x["id"] == vid)
            valor: Any = texto
            if v["type"]["kind"] == "bool":
                valor = texto.lower() in ("1", "true", "sí", "si", "verdadero")
            self._cambiar(vid, initialValue=valor)

    def nueva(self) -> None:
        """Una entrada booleana con el primer nombre libre (I00, I01…); se cambia en la propia tabla."""
        usados = {v["name"] for v in self.e.ed.model["variables"]}
        n = 0
        while f"I{n:02d}" in usados:
            n += 1
        self._resultado(self.e.nueva_variable(f"I{n:02d}"))
        self.mostrar(self.e)
        self.tabla.selectRow(self.tabla.rowCount() - 1)
        if self.isVisible():  # se escribe el nombre directamente
            self.tabla.editItem(self.tabla.item(self.tabla.rowCount() - 1, 0))

    def quitar(self) -> None:
        r = self.tabla.currentRow()
        if 0 <= r < len(self._ids):
            self._resultado(self.e.quitar_variable(self._ids[r]))
