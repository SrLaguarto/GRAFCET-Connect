"""Distingue un panel oculto desde Ver de un panel plegado en su borde."""


class VisibilidadPaneles:
    def __init__(self, ventana):
        self.v = ventana
        self.habilitados = {}
        self.abiertos = {}
        for nombre in ("izquierdo", "derecho", "inferior"):
            abierto = ventana.ajustes.value(f"paneles/{nombre}", nombre != "inferior", type=bool)
            self.habilitados[nombre] = ventana.ajustes.value(self.clave(nombre), abierto, type=bool)
            self.abiertos[nombre] = abierto

    @staticmethod
    def clave(nombre):
        return f"paneles/{nombre}/visible"

    def esta_abierto(self, nombre):
        return self.habilitados[nombre] and self.abiertos[nombre]

    def desde_menu(self, nombre, visible):
        self.habilitados[nombre] = visible
        self.v.ajustes.setValue(self.clave(nombre), visible)
        self.mostrar(nombre, visible)

    def mostrar(self, nombre, abierto, guardar=True):
        v = self.v
        if guardar:
            self.abiertos[nombre] = abierto
            if abierto:
                self.habilitados[nombre] = True
            v.ajustes.setValue(self.clave(nombre), self.habilitados[nombre])
        v._desplegar_panel(nombre, abierto, guardar)
        editar = v.modo == "editar" and v.edicion is not None and not v.solo_lectura
        permitido = nombre != "izquierdo" or editar
        permitido = permitido and not (nombre == "inferior" and v.flot.activo())
        v._plegables[nombre].setVisible(self.habilitados[nombre] and permitido)
        accion = v._accion_panel(nombre)
        accion.blockSignals(True)
        accion.setChecked(self.habilitados[nombre])
        accion.blockSignals(False)
        if nombre == "inferior" and v.flot.activo():
            v.flot.actualizar()

    def alternar(self, nombre):
        self.mostrar(nombre, not self.v._plegables[nombre].abierto)

    def reponer_modo(self, nombre, editar, guardado):
        abierto = self.abiertos[nombre]
        if nombre == "inferior":
            if not editar:
                abierto = False
            elif guardado is not None:
                abierto = self.abiertos[nombre] = guardado["inferior"]
        self.mostrar(nombre, abierto, guardar=False)

    def restaurar(self):
        for nombre, abierto in self.abiertos.items():
            self.mostrar(nombre, abierto, guardar=False)
