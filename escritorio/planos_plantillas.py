"""Coherencia y filtro de plantillas del panel derecho de PLANOS."""
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QMenu, QSizePolicy, QToolButton, QWidget

from . import estilo
from .importar_plantillas import formato_iso


def fila_plantilla(editor):
    fila = QWidget()
    lay = QHBoxLayout(fila)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(estilo.E2)
    editor.predeterminadas.setMinimumContentsLength(8)
    politica = editor.predeterminadas.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    editor.predeterminadas.setSizeAdjustPolicy(politica)
    editor.predeterminadas.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    lay.addWidget(editor.predeterminadas, 1)
    editor.b_opciones_plantilla = QToolButton()
    editor.b_opciones_plantilla.setText("▾")
    editor.b_opciones_plantilla.setFixedSize(estilo.ALTO_CONTROL, estilo.ALTO_CONTROL)  # (cuadrado, del alto del desplegable de al lado)
    editor.b_opciones_plantilla.setStyleSheet(  # con marco, como el desplegable: sin él parecía una flecha suelta
        f"QToolButton {{ padding:0; border:1px solid {estilo.BORDE_CONTROL}; border-radius:{estilo.R_S}px; "
        f"background:{estilo.SUPERFICIE}; color:{estilo.TINTA}; }}"
        f"QToolButton:hover {{ background:{estilo.HOVER}; }} QToolButton:pressed {{ background:{estilo.PULSADO}; }}"
        f"QToolButton[tecl=\"true\"]:focus {{ border:2px dashed {estilo.FOCO}; }}"
        "QToolButton::menu-indicator { image:none; width:0; }")
    editor.b_opciones_plantilla.setToolTip("Opciones de plantilla: importar, usar la estándar, editar o quitar")
    editor.b_opciones_plantilla.setAccessibleName("Opciones de plantilla")
    editor.b_opciones_plantilla.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu = QMenu(editor.b_opciones_plantilla)
    for accion in (editor.a_importar, editor.a_estandar, editor.a_editar_plantilla, editor.a_quitar_plantilla):
        menu.addAction(accion)
    editor.b_opciones_plantilla.setMenu(menu)
    lay.addWidget(editor.b_opciones_plantilla)
    return fila


class PlantillasHoja:
    def __init__(self, editor):
        self.e = editor
        self.cambio = False
        self.biblioteca = []
        self._firma = None
        self._cargar_biblioteca()
        self.alinear_con_plantilla()

    def _cargar_biblioteca(self):
        from .carpetas import asegurar_carpetas, cargar_plantilla
        from grafcet.plantillas_tecnicas import PREDETERMINADAS
        try:
            rutas = sorted(asegurar_carpetas()["plantillas"].rglob("*.json"))
            for ruta in rutas:
                if ruta.name == "plantilla.json" and ruta.parent.name in PREDETERMINADAS:
                    continue
                try:
                    plantilla = cargar_plantilla(ruta)
                    self.biblioteca.append((ruta.stem, str(ruta), formato_iso(*plantilla["size"])))
                except (OSError, ValueError):
                    continue
        except OSError:
            pass

    def alinear_con_plantilla(self):
        e = self.e
        if e.plantilla is None:
            return
        formato, orientacion = formato_iso(*e.plantilla["size"])
        for campo in (e.formato, e.orientacion):
            campo.blockSignals(True)
        e.formato.setCurrentText(formato)
        e.orientacion.setCurrentIndex(e.orientacion.findData(orientacion))
        e.formato.blockSignals(False)
        e.orientacion.blockSignals(False)

    def preparar(self):
        e = self.e
        formato, orientacion = e.formato.currentText(), e.orientacion.currentData()
        self.cambio = False
        if e.plantilla is None or formato_iso(*e.plantilla["size"]) != (formato, orientacion):
            if formato != "Personalizado":
                e.cargar_tecnica(formato, orientacion, 10.)
                e.offset = [0., 0.]
                e.margen.blockSignals(True)
                e.margen.setValue(10.)
                e.margen.blockSignals(False)
                self.cambio = True
        elif e.plantilla.get("source") == "GrafConnect":
            margen = e.margen.value()
            if abs(float(e.plantilla.get("margin_mm", 10)) - margen) > .001:
                e.cargar_tecnica(formato, orientacion, margen)
                self.cambio = True
        e.formato.setEnabled(True)
        e.orientacion.setEnabled(formato != "Personalizado")
        personalizado = e.formato.findText("Personalizado")
        if personalizado >= 0:
            e.formato.model().item(personalizado).setEnabled(formato == "Personalizado")
        self._filtrar(formato, orientacion)

    def _filtrar(self, formato, orientacion):
        e = self.e
        propia = e.plantilla is not None and e.plantilla.get("source") != "GrafConnect"
        firma = (formato, orientacion, propia, e.plantilla.get("source") if e.plantilla else "")
        if firma == self._firma:
            return
        self._firma = firma
        combo = e.predeterminadas
        combo.blockSignals(True)
        combo.clear()
        if propia:
            combo.addItem(e.plantilla.get("source", "Personalizada") + " — proyecto", None)
        if formato != "Personalizado":
            combo.addItem(formato + " " + orientacion + " — predeterminada", (formato, orientacion))
        for nombre, ruta, dimensiones in self.biblioteca:
            if dimensiones == (formato, orientacion):
                combo.addItem(nombre, ruta)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)
