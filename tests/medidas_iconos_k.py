"""Medidas de tinta con bordes antialias interpolados, independientes del DPR."""
from PySide6.QtCore import QSize


def limites(imagen, umbral=128):
    puntos = [(x, y) for y in range(imagen.height()) for x in range(imagen.width())
              if imagen.pixelColor(x, y).alpha() >= umbral]
    return (min(x for x, y in puntos), min(y for x, y in puntos),
            max(x for x, y in puntos) + 1, max(y for x, y in puntos) + 1)


def medir(modulo, lado, dpr):
    salida = {}
    imagenes = []
    for clave in modulo.PREDETERMINADOS:
        pixmap = modulo.icono_mini(clave).pixmap(QSize(lado, lado), dpr)
        imagen = pixmap.toImage()
        x0, y0, x1, y1 = limites(imagen)
        perfil = [max(imagen.pixelColor(x, y).alpha() for y in range(imagen.height()))
                  for x in range(imagen.width())]
        ocupadas = [x for x, alfa in enumerate(perfil) if alfa]
        izquierda, derecha = ocupadas[0], ocupadas[-1]
        borde_i = perfil[izquierda] / max(perfil[izquierda:izquierda + 5])
        borde_d = perfil[derecha] / max(perfil[max(0, derecha - 4):derecha + 1])
        ancho = (derecha - izquierda - 1 + borde_i + borde_d) / dpr
        salida[clave] = {"ancho_tinta": ancho, "alto_tinta": (y1 - y0) / dpr,
                         "limites_fisicos": [x0, y0, x1, y1],
                         "toca_borde": izquierda == 0 or derecha == imagen.width() - 1
                         or any(imagen.pixelColor(x, 0).alpha() or imagen.pixelColor(x, imagen.height() - 1).alpha()
                                for x in range(imagen.width()))}
        imagenes.append(imagen)
    return salida, imagenes


