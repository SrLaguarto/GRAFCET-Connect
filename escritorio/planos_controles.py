"""Barra de PLANOS y propiedades de su gráfico seleccionado."""
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QMenu, QPushButton,
                               QToolBar, QToolButton, QWidget)
from PySide6.QtCore import Qt

from . import estilo

AVISO_NO_CABE = (
    "El GRAFCET no cabe en esta hoja. Cambie el tamaño de la hoja a uno más grande "
    "(p. ej. A3) o la orientación."
)


def comprobar_cabe(modelo, ajustes):
    """Rechaza antes de crear la hoja una selección que necesita recorte o varias páginas."""
    from .laminas import DocumentoLaminas
    try:
        documento = DocumentoLaminas(modelo, {}, ajustes)
    except ValueError as exc:
        raise ValueError(AVISO_NO_CABE) from exc
    if documento.total != 1:
        raise ValueError(AVISO_NO_CABE)


class ControlesPlanos:
    def __init__(self, pagina, raiz):
        self.p = pagina
        self._barra(raiz)
        self._grafico()

    def _barra(self, raiz):
        p = self.p
        p.compacto = False
        p.barra = QToolBar("Planos")
        p.barra.setObjectName("barraPlanos")
        p.barra.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        p.barra_hoja = p.barra
        p.a_hoja = p.barra.addAction("+ Añadir hoja", p.nueva_hoja)
        p.barra.removeAction(p.a_hoja)
        p.a_nueva = p.barra.addAction("Traer GRAFCET", p.traer)
        p.a_centrar = p.barra.addAction("Centrar GRAFCET", lambda: p.editor and p.editor.centrar())
        p.a_texto = p.barra.addAction("Añadir texto", lambda: p.editor and p.editor.anadir_texto())
        p.barra.addSeparator()
        p.a_exportar = p.barra.addAction("Exportar…", lambda: p.editor and p.editor.exportar())
        p.a_imprimir = p.barra.addAction("Imprimir…", lambda: p.editor and p.editor.imprimir())
        p.barra.addSeparator()
        p.a_menos = p.barra.addAction("−", lambda: p.zoom(1 / 1.15))
        p.zoom_combo = QComboBox()
        p.zoom_combo.setMinimumWidth(110)
        p.zoom_combo.addItem("Ajustar hoja", None)
        for n in (50, 75, 100, 125, 150, 200):
            p.zoom_combo.addItem(str(n) + " %", n / 100)
        p.barra.addWidget(p.zoom_combo)
        p.a_mas_zoom = p.barra.addAction("+", lambda: p.zoom(1.15))
        p.zoom_combo.currentIndexChanged.connect(p.elegir_zoom)
        self.menu_mas = QMenu(p.barra)
        self.b_mas = QToolButton()
        self.b_mas.setText("Más")
        self.b_mas.setToolTip("Contenido y salida del plano")
        self.b_mas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.b_mas.setMenu(self.menu_mas)
        self.menu_mas.aboutToShow.connect(self._rellenar_mas)
        self.acc_mas = p.barra.addWidget(self.b_mas)
        self.acc_mas.setVisible(False)
        raiz.addWidget(p.barra)

    def _grafico(self):
        p = self.p
        p.propiedades_grafico = QWidget(p)
        p.propiedades_grafico.hide()
        form = QFormLayout(p.propiedades_grafico)
        form.addRow(QLabel("GRAFCET seleccionado"))
        p.tamano = QDoubleSpinBox()
        p.tamano.setRange(50, 200)
        p.tamano.setSingleStep(10)
        p.tamano.setDecimals(0)
        p.tamano.setSuffix(" %")
        p.tamano.setValue(100)
        p.tamano.setToolTip("Tamaño impreso (50–200 %), independiente del zoom")
        p.tamano.valueChanged.connect(p.cambiar_tamano)
        form.addRow("Tamaño", p.tamano)
        p.b_eliminar_grafico = QPushButton("Eliminar del plano")
        p.b_eliminar_grafico.clicked.connect(p.eliminar_grafico)
        form.addRow(p.b_eliminar_grafico)

    def _rellenar_mas(self):
        self.menu_mas.clear()
        for accion in self.secundarias():
            copia = self.menu_mas.addAction(accion.text(), accion.trigger)
            copia.setEnabled(accion.isEnabled())

    def secundarias(self):
        p = self.p
        return (p.a_centrar, p.a_texto, p.a_exportar, p.a_imprimir)

    def compactar(self):
        p = self.p
        for accion in self.secundarias():
            accion.setVisible(not p.compacto)
        self.acc_mas.setVisible(p.compacto)
        acciones = p.barra.actions()
        # Cada separador solo se ve si hay contenido a ambos lados hasta el siguiente grupo.
        for i, accion in enumerate(acciones):
            if accion.isSeparator():
                siguiente = []
                for otra in acciones[i + 1:]:
                    if otra.isSeparator():
                        break
                    siguiente.append(otra)
                accion.setVisible(any(a.isVisible() for a in siguiente))
        p.scroll_hojas.setMinimumWidth(112 if p.compacto else 150)
        p.scroll_hojas.setMaximumWidth(150 if p.compacto else 215)
        if p.editor is not None:
            pila = p.editor.propiedades
            pila.setFixedWidth(232 if p.compacto else 290)
            for i in range(pila.count()):
                pila.widget(i).setFixedWidth(228 if p.compacto else 286)
