"""Descriptores del dibujo y su grabadora, sin Qt.

`Grabadora` tiene la misma superficie que `diagrama._Pintor` (`line`, `poly`, `rect`, `circle`, `text`, `comentario`, `pen`,
`seg`, `ancho`, `limites`, `ascenso`, `notas`) pero, en lugar de crear ítems, anota **descriptores**: tuplas inmutables y
comparables por igualdad. Lo que necesita Qt para medir (anchura y alto de un texto, límites de sus segmentos, ascenso) entra
como `Servicios`, igual que `medir=` en `geometria/`.

Un descriptor es una tupla cuyo primer elemento es su tipo:

  ("linea", x1, y1, x2, y2, pluma, z, tip, parcial, elementos)
  ("camino", puntos, pluma, relleno, z, tip, parcial, elementos)
  ("rect", x, y, w, h, pluma, relleno, radio, z, tip, parcial, elementos)
  ("elipse", cx, cy, r, relleno, z, tip, parcial, elementos)
  ("texto", contenido, color, (tamano, negrita, mono), x, arriba, z, tip, parcial, elementos)
  ("comentario", texto, ancho, x, y, z, parcial, elementos)
  ("nota", datos, seleccionada, parcial, elementos)

`pluma` es `("pluma", color, grosor, discontinuo)` o None (sin trazo); `relleno` es el nombre de un color o None. Los colores
van por nombre (los resuelve quien realiza el dibujo).

Cada elemento del modelo pasa a ser el grupo actual con `entrar(clave)`, donde `clave` es `(tipo, id)`. `secuencia` conserva el orden exacto
en que se anotó todo (el de dibujo: fija el apilado) y `objetos` agrupa los descriptores por clave.
"""
from dataclasses import dataclass
from typing import Any, Callable

Clave = tuple[str, ...]
Descriptor = tuple[Any, ...]


@dataclass(frozen=True)
class Servicios:
    contenido: Callable[[Any, Any], str]                  # (segmentos, verdaderos) -> texto enriquecido
    negados: Callable[[Any], list]                        # segmentos -> tramos [i, j) negados
    medir: Callable[[str, int, bool, bool], tuple[float, float]]      # (contenido, tamano, negrita, mono) -> (ancho, alto)
    limites_de: Callable[[str, int, bool, bool, Any], list[float]]    # idem + segmentos -> posiciones de cada segmento
    ancho: Callable[..., float]
    limites: Callable[..., list[float]]
    ascenso: Callable[..., float]
    ascenso_texto: Callable[[int, bool, bool], float]       # ascenso de la fuente con la que se dibuja (la monoespaciada incluida)
    alto_comentario: Callable[[str, float], float]
    grosor_negado: float
    ancho_comentario: float


def pluma(color: str, grosor: float = 1.6, discontinuo: tuple[float, float] | None = None) -> tuple[Any, ...]:
    return ("pluma", color, grosor, discontinuo)


class Grabadora:
    def __init__(self, servicios: Servicios) -> None:
        self.sv = servicios
        self.verdaderos: set[str] = set()
        self.parcial: str | None = None
        self.elementos: tuple[str, ...] = ()
        self.secuencia: list[tuple[Clave, Descriptor]] = []
        self.objetos: dict[Clave, list[Descriptor]] = {}
        self.actual: Clave = ("sin_grupo",)

    # --- grupos
    def entrar(self, clave: Clave) -> Clave:
        """Lo que se anote desde ahora pertenece al objeto `clave`; devuelve el grupo anterior (para volver a él con `entrar`)."""
        previo, self.actual = self.actual, clave
        self.objetos.setdefault(clave, [])
        return previo

    def _anotar(self, descriptor: Descriptor) -> None:
        self.secuencia.append((self.actual, descriptor))
        self.objetos.setdefault(self.actual, []).append(descriptor)

    @property
    def orden(self) -> tuple[Clave, ...]:
        """Las claves en el orden en que aparece su primer descriptor."""
        return tuple(dict.fromkeys(c for c, _ in self.secuencia))

    # --- medidas y utilidades (las mismas que `_Pintor`)
    pen = staticmethod(pluma)

    def seg(self, t: str) -> list[dict[str, Any]]:
        return [{"t": t}]

    def ancho(self, *args: Any, **kw: Any) -> float:
        return self.sv.ancho(*args, **kw)

    def limites(self, *args: Any, **kw: Any) -> list[float]:
        return self.sv.limites(*args, **kw)

    def ascenso(self, *args: Any, **kw: Any) -> float:
        return self.sv.ascenso(*args, **kw)

    # --- primitivas
    def _marca(self) -> tuple[Any, Any]:
        return self.parcial, tuple(self.elementos)

    def line(self, x1: float, y1: float, x2: float, y2: float, pen: Any, z: float, tip: str | None = None) -> None:
        self._anotar(("linea", x1, y1, x2, y2, pen, z, tip, *self._marca()))

    def poly(self, pts: list[tuple[float, float]], pen: Any, z: float, fill: str | None = None, tip: str | None = None) -> None:
        self._anotar(("camino", tuple((float(x), float(y)) for x, y in pts), pen, fill, z, tip, *self._marca()))

    def rect(self, x: float, y: float, w: float, h: float, pen: Any, z: float, fill: str | None = None,
             tip: str | None = None, radius: float = 0) -> None:
        self._anotar(("rect", x, y, w, h, pen, fill, radius, z, tip, *self._marca()))

    def circle(self, cx: float, cy: float, r: float, fill: str, z: float, tip: str | None = None) -> None:
        self._anotar(("elipse", cx, cy, r, fill, z, tip, *self._marca()))

    def text(self, x: float, y: float, segs: list[dict[str, Any]] | None, size: int, color: str, z: float,
             anchor: str = "start", tip: str | None = None, bold: bool = False, halo: bool = False, mono: bool = False) -> float:
        if not segs:
            return 0.0
        sv = self.sv
        contenido = sv.contenido(segs, self.verdaderos)
        w, h = sv.medir(contenido, size, bold, mono)
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        top = y - sv.ascenso_texto(size, bold, mono)
        self._anotar(("texto", contenido, color, (size, bold, mono), x0, top, z + 0.02, tip, *self._marca()))
        tramos = sv.negados(segs)
        if tramos:
            lim = sv.limites_de(contenido, size, bold, mono, segs)
            for i, j in tramos:
                while i < j:
                    verde = any(k in self.verdaderos for k in segs[i].get("eval", []))
                    fin = i + 1
                    while fin < j and any(k in self.verdaderos for k in segs[fin].get("eval", [])) == verde:
                        fin += 1
                    self.line(x0 + lim[i], top, x0 + lim[fin], top,
                              self.pen("true_text" if verde else color, sv.grosor_negado), z + 0.03, tip)
                    i = fin
        if halo:
            self.rect(x0 - 3, top - 1, w + 6, h + 2, None, z + 0.01, "panel")
        return w

    def comentario(self, x: float, yc: float, texto: str, z: float, ancho: float | None = None) -> None:
        ancho = self.sv.ancho_comentario if ancho is None else ancho
        alto = self.sv.alto_comentario(texto, ancho)
        self._anotar(("comentario", texto, ancho, x, yc - alto / 2, z + 0.02, *self._marca()))

    def notas(self, M: dict[str, Any], seleccion: set[str]) -> None:
        for n in M.get("annotations", []):
            previo = self.entrar(("nota", n["id"]))
            self._anotar(("nota", _congelar(n), n["id"] in seleccion, *self._marca()))
            self.entrar(previo)


def _congelar(valor: Any) -> Any:
    if isinstance(valor, dict):
        return tuple(sorted((k, _congelar(v)) for k, v in valor.items()))
    if isinstance(valor, (list, tuple)):
        return tuple(_congelar(v) for v in valor)
    return valor
