"""Barra de PLANOS y propiedades de su gráfico seleccionado."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton,
                               QSizePolicy, QStyle, QStyleOptionComboBox, QStylePainter, QToolBar,
                               QToolButton, QWidget)

from . import estilo
from .campos_medidos import DecimalMedido

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


class ComboZoom(QComboBox):
    """Centra el valor seleccionado y el porcentaje de un zoom libre en el campo."""

    def paintEvent(self, evento):
        opcion = QStyleOptionComboBox()
        self.initStyleOption(opcion)
        pintor = QStylePainter(self)
        tipo = QStyle.ComplexControl.CC_ComboBox
        pintor.drawComplexControl(tipo, opcion)
        zona = self.style().subControlRect(tipo, opcion, QStyle.SubControl.SC_ComboBoxEditField, self)
        flecha = self.style().subControlRect(tipo, opcion, QStyle.SubControl.SC_ComboBoxArrow, self)
        margen = flecha.width() + estilo.E1
        # Reserva el mismo margen a ambos lados para centrar en toda la caja.
        zona.setLeft(opcion.rect.left() + margen)
        zona.setRight(opcion.rect.right() - margen)
        if self.currentIndex() < 0:
            texto, papel = self.placeholderText(), QPalette.ColorRole.PlaceholderText
        else:
            texto, papel = opcion.currentText, QPalette.ColorRole.ButtonText
        texto = opcion.fontMetrics.elidedText(texto, Qt.TextElideMode.ElideRight, zona.width())
        pintor.drawItemText(zona, int(Qt.AlignmentFlag.AlignCenter), opcion.palette, self.isEnabled(), texto, papel)


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
        p.a_hoja = QAction("+ Añadir otra hoja", p)
        p.a_hoja.triggered.connect(p.nueva_hoja)
        p.a_nueva = p.barra.addAction("Traer GRAFCET", p.traer)
        p.a_centrar = p.barra.addAction("Centrar GRAFCET", lambda: p.editor and p.editor.centrar())
        p.a_texto = p.barra.addAction("Añadir texto", lambda: p.editor and p.editor.anadir_texto())
        p.barra.addSeparator()
        p.a_exportar = p.barra.addAction("Exportar…", lambda: p.editor and p.editor.exportar())
        p.a_imprimir = p.barra.addAction("Imprimir…", lambda: p.editor and p.editor.imprimir())
        self.menu_mas = QMenu(p.barra)
        self.b_mas = QToolButton()
        self.b_mas.setText("Más")
        self.b_mas.setToolTip("Contenido y salida del plano")
        self.b_mas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.b_mas.setMenu(self.menu_mas)
        self.menu_mas.aboutToShow.connect(self._rellenar_mas)
        self.acc_mas = p.barra.addWidget(self.b_mas)
        self.acc_mas.setVisible(False)
        p.barra.addSeparator()
        p._espaciador_barra = QWidget(p.barra)
        p._espaciador_barra.setStyleSheet("background: transparent;")
        p._espaciador_barra.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.acc_espaciador = p.barra.addWidget(p._espaciador_barra)
        p.caja_zoom = QFrame(p.barra)
        p.caja_zoom.setObjectName("barraZoomPlanos")
        zl = QHBoxLayout(p.caja_zoom)
        zl.setContentsMargins(3, 1, 3, 1)
        zl.setSpacing(2)
        p.a_menos = QAction("−", p)
        p.a_menos.setToolTip("Alejar")
        p.a_menos.triggered.connect(lambda: p.zoom(1 / 1.15))
        p.b_menos_zoom = QToolButton(p.caja_zoom)
        p.b_menos_zoom.setObjectName("pasoZoomPlanos")
        p.b_menos_zoom.setDefaultAction(p.a_menos)
        p.zoom_combo = ComboZoom(p.caja_zoom)
        p.zoom_combo.setMinimumWidth(106)
        p.zoom_combo.addItem("Ajustar hoja", None)
        for n in (50, 75, 100, 125, 150, 200):
            p.zoom_combo.addItem(str(n) + " %", n / 100)
        p.zoom_combo.currentIndexChanged.connect(p.elegir_zoom)
        p.a_mas_zoom = QAction("+", p)
        p.a_mas_zoom.setToolTip("Acercar")
        p.a_mas_zoom.triggered.connect(lambda: p.zoom(1.15))
        p.b_mas_zoom = QToolButton(p.caja_zoom)
        p.b_mas_zoom.setObjectName("pasoZoomPlanos")
        p.b_mas_zoom.setDefaultAction(p.a_mas_zoom)
        p.b_encajar_zoom = QToolButton(p.caja_zoom)
        p.b_encajar_zoom.setObjectName("encajarZoomPlanos")
        p.b_encajar_zoom.setIcon(estilo.icono("ajustar", estilo.TINTA, tam=18))
        p.b_encajar_zoom.setIconSize(QSize(18, 18))
        p.b_encajar_zoom.setToolTip("Ajustar hoja")
        p.b_encajar_zoom.setAccessibleName("Ajustar hoja")
        p.b_encajar_zoom.clicked.connect(
            lambda: p.zoom_combo.setCurrentIndex(0) if p.zoom_combo.currentIndex() != 0 else p.elegir_zoom(0)
        )
        for widget in (p.b_menos_zoom, p.zoom_combo, p.b_mas_zoom, p.b_encajar_zoom):
            zl.addWidget(widget)
        self.acc_zoom = p.barra.addWidget(p.caja_zoom)
        raiz.addWidget(p.barra)

    def _grafico(self):
        p = self.p
        p.propiedades_grafico = QWidget(p)
        p.propiedades_grafico.setObjectName("propiedadesGraficoPlanos")
        p.propiedades_grafico.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        p.propiedades_grafico.hide()
        form = QFormLayout(p.propiedades_grafico)
        form.setContentsMargins(12, 12, 12, 12)
        form.setVerticalSpacing(estilo.E2)
        titulo = QLabel("GRAFCET seleccionado")
        titulo.setObjectName("tituloPropiedadesGrafico")
        form.addRow(titulo)
        p.tamano = DecimalMedido()
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
        from .campos_medidos import ajustar_boton
        ajustar_boton(p.b_eliminar_grafico)
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
                accion.setVisible(any(a.isVisible() and a is not self.acc_espaciador for a in siguiente))
        p.scroll_hojas.setMinimumWidth(112 if p.compacto else 150)
        p.scroll_hojas.setMaximumWidth(150 if p.compacto else 215)
        if p.editor is not None:
            pila = p.editor.propiedades
            from .planos_plantillas import ancho_panel
            ancho = 232 if p.compacto else ancho_panel(p.editor)
            pila.setFixedWidth(ancho)
            for i in range(pila.count()):
                pila.widget(i).setFixedWidth(ancho - 4)
