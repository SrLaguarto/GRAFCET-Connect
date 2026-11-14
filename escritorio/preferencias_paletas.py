"""Preferencias y migración de las dos paletas de elementos."""
from PySide6.QtGui import QAction

MIGRACION = "paletas/favoritos_principal_v1"
VISIBLE = "favoritos/visible"


def migrar(ajustes):
    if ajustes.value(MIGRACION, False, type=bool):
        return
    ajustes.setValue("paneles/izquierdo", False)
    ajustes.setValue(VISIBLE, True)
    ajustes.setValue(MIGRACION, True)


class PreferenciasPaletas:
    def __init__(self, ventana, menu):
        self.v = ventana
        migrar(ventana.ajustes)
        ventana.a_izquierdo.setText("Panel de elementos")
        self.accion = QAction("Barra de favoritos", ventana)
        self.accion.setCheckable(True)
        self.accion.setChecked(ventana.ajustes.value(VISIBLE, True, type=bool))
        self.accion.toggled.connect(self.cambiar)
        menu.addAction(self.accion)

    def inicial(self, nombre):
        if nombre == "izquierdo":
            return self.v.ajustes.value("paneles/izquierdo", False, type=bool)
        return nombre != "inferior" or self.v._inferior_al_arrancar

    def visible(self):
        return self.accion.isChecked() and self.v._cabecera_favoritos.editable()

    def cambiar(self, visible):
        self.v.ajustes.setValue(VISIBLE, visible)
        self.v._cabecera_favoritos.integrar_zoom()
        self.v._orden_tab()

    def foco(self):
        v = self.v
        botones = []
        if v.favoritos.isVisibleTo(v):
            botones = [v.favoritos.botones[h] for h in v.favoritos._visibles]
            if v.favoritos.desborde.isVisible():
                botones.append(v.favoritos.desborde)
        if v.paleta.isVisibleTo(v):
            botones.append(v.paleta)
        return botones
