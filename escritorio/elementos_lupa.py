"""Propiedad de los ítems del dibujo para aislar un elemento en la lupa."""
DATO_PARCIAL = 42    # `data` de cada ítem del dibujo con el parcial al que pertenece (lo lee Navegacion.filtrar)
DATO_ELEMENTOS = 43


def ocultar_vecinos(escena, elemento, z_edicion, z_minimo=float("-inf")):
    items = escena.items()
    identificado = elemento is not None and any(elemento in (i.data(DATO_ELEMENTOS) or ()) for i in items)
    ocultos = [i for i in items if i.isVisible() and (
        not z_minimo <= i.zValue() < z_edicion or identificado and elemento not in (i.data(DATO_ELEMENTOS) or ())
    )]
    for item in ocultos:
        item.hide()
    return ocultos
