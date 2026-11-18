"""Gestiona el plegado de Variables y la visibilidad de la traza."""


class VisibilidadPaneles:
    def __init__(self, ventana):
        self.v = ventana
        self.abiertos = {}
        for nombre in ("derecho", "inferior"):
            abierto = ventana.ajustes.value(f"paneles/{nombre}", nombre != "inferior", type=bool)
            self.abiertos[nombre] = abierto

        ventana.ajustes.remove("paneles/izquierdo")
        ventana.ajustes.remove("paneles/derecho/visible")
        self.traza_habilitada = ventana.ajustes.value("paneles/inferior/visible", self.abiertos["inferior"], type=bool)

    def activar_traza(self, visible):
        self.traza_habilitada = visible
        self.mostrar("inferior", visible)

    def mostrar(self, nombre, abierto, guardar=True):
        v = self.v
        if guardar:
            self.abiertos[nombre] = abierto
        v._desplegar_panel(nombre, abierto, guardar)
        if nombre == "derecho":
            return

        if guardar:
            self.traza_habilitada |= abierto
            v.ajustes.setValue("paneles/inferior/visible", self.traza_habilitada)
        v._plegables[nombre].setVisible(self.traza_habilitada and v.modo == "simular")
        v.a_inferior.blockSignals(True)
        v.a_inferior.setChecked(self.traza_habilitada)
        v.a_inferior.blockSignals(False)

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
