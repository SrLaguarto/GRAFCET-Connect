"""Integración del cambio de proyecto con el transporte que está activo."""


def preparar_carga(ventana, config):
    coordinador = ventana.modbus
    desconectar = False
    with ventana.candado:
        if not coordinador.activo or coordinador.adaptador is None:
            return
        modo = config.modo if config else "modbus"
        if modo != coordinador.adaptador.config.modo:
            coordinador.desconectar()
            desconectar = True
    if desconectar:
        ciclo = getattr(ventana, "ciclo", None)
        if ciclo is not None:
            ciclo.despertar()
