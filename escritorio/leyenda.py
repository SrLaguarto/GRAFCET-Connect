"""«Ayuda > Leyenda del dibujo»: ventana no modal con lo que significa cada trazo y color, por secciones.

Cada entrada lleva una miniatura dibujada con el mismo código que el diagrama (`diagrama.dibujar`, sobre una escena
pequeña) junto a una frase corta. Las miniaturas se construyen con modelos mínimos y estados escritos a mano (no se
simula nada, salvo los temporizadores, que se leen de una simulación real de dos etapas). Los colores son los de `COL`
en el momento de abrir la ventana.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QGraphicsScene, QHBoxLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from grafcet.builder import M
from grafcet.view import Vista

from . import estilo
from .diagrama import COL, SX, dibujar

ESCALA = 0.9  # tamaño de las miniaturas respecto al dibujo
ANCHO_MINIATURA = 190  # columna de las imágenes: todas centradas en el mismo ancho
ALTO_MINIATURA = 120  # alto máximo de una miniatura (las que lo piden más se reducen)
RECUADRO = 4  # margen alrededor de lo dibujado

Region = tuple[float, float, float, float]  # x0, y0, x1, y1 en coordenadas de la escena (con el margen SX)
Escena = tuple[dict[str, Any], dict[str, Any], Region | None]  # modelo del dibujo, su estado y la zona que se enseña
Miniatura = Callable[[], Escena]


@dataclass(frozen=True)
class Entrada:
    titulo: str
    frase: str
    miniatura: Miniatura | None = None


def _modelo(m: M, posiciones: dict[str, tuple[int, int]]) -> dict[str, Any]:
    return Vista("leyenda", "", "", lambda: (m, posiciones), {}).model


def _region(x: float, y: float, ancho: float, alto: float) -> Region:
    """Una zona centrada en (x, y) del modelo (la escena lleva SX de margen a la izquierda)."""
    return (x + SX - ancho / 2, y - alto / 2, x + SX + ancho / 2, y + alto / 2)


def _una_etapa(inicial: bool = False, activa: bool = False, inestable: bool = False,
               kind: str = "ordinary") -> Escena:
    m = M().step("1", inicial, kind=kind)
    estado: dict[str, Any] = {"situation": ["1"] if activa else [], "virtual": ["1"] if inestable else []}
    return _modelo(m, {"1": (40, 40)}), estado, _region(40, 40, 120, 80)


def _etapa() -> Escena:
    return _una_etapa()


def _etapa_inicial() -> Escena:
    return _una_etapa(inicial=True)


def _etapa_activa() -> Escena:
    return _una_etapa(activa=True)


def _etapa_inestable() -> Escena:
    return _una_etapa(inestable=True)


def _transicion(franqueable: bool = False, recien: bool = False) -> Escena:
    m = M().var("marcha").step("1", True).step("2").trans("t1", ["1"], ["2"], "marcha")
    pos = {"1": (40, 40), "t1": (40, 120), "2": (40, 200)}
    estado: dict[str, Any] = {"situation": ["1"] if franqueable else ["2"] if recien else []}
    if franqueable:
        estado["transitions"] = {"t1": {"validated": True, "receptivity": True, "fireable": True}}
    if recien:
        estado["lastCleared"] = ["t1"]
    return _modelo(m, pos), estado, _region(75, 120, 230, 84)


def _transicion_reposo() -> Escena:
    return _transicion()


def _transicion_franqueable() -> Escena:
    return _transicion(franqueable=True)


def _transicion_reciente() -> Escena:
    return _transicion(recien=True)


def _accion(tipo: str, activa: bool = False) -> Escena:
    m = M().var("a").var("c").var("Q", "output").step("1", True)
    if tipo == "continua":
        m.cont("1", "Q", aid="x")
    elif tipo == "condicionada":
        m.cont("1", "Q", "c", aid="x")
    elif tipo == "evento":
        m.stored("1", "Q", "event", "1", event="rise(a)", aid="x")
    else:
        m.stored("1", "Q", "activation" if tipo == "activar" else "deactivation", "1", aid="x")
    estado: dict[str, Any] = {"situation": ["1"] if activa else []}
    if activa:
        estado.update({"activeActions": ["x"], "outputs": {"Q": {"value": True, "contributors": ["x"]}}})
    return _modelo(m, {"1": (40, 40)}), estado, _region(100, 40, 220, 100)


def _accion_continua() -> Escena:
    return _accion("continua")


def _accion_condicionada() -> Escena:
    return _accion("condicionada")


def _accion_activar() -> Escena:
    return _accion("activar")


def _accion_desactivar() -> Escena:
    return _accion("desactivar")


def _accion_evento() -> Escena:
    return _accion("evento")


def _salida_a_uno() -> Escena:
    return _accion("continua", activa=True)


def _macroetapa() -> Escena:
    m = M().partial("X").step("A", True).step("E1", kind="entry", partial="X").step("S1", kind="exit", partial="X")
    m.macro("M", "X", "E1", "S1").trans("t", ["A"], ["M"], "true")
    pos = {"A": (40, 40), "t": (40, 110), "M": (40, 180), "E1": (400, 100), "S1": (400, 240)}
    return _modelo(m, pos), {}, _region(40, 180, 120, 80)


def _encapsulante() -> Escena:
    m = M().partial("R").step("H", True, kind="enclosing").step("I", True, partial="R")
    m.enclosure("H", "R", ["I"])
    return _modelo(m, {"H": (40, 40), "I": (400, 40)}), {}, _region(40, 40, 120, 80)


def _recinto() -> Escena:
    m = M().partial("R").var("p").step("H", True, kind="enclosing").step("I", True, partial="R").step("J", partial="R")
    m.trans("v", ["I"], ["J"], "p", partial="R").enclosure("H", "R", ["I"])
    pos = {"H": (40, 40), "I": (170, 70), "v": (170, 150), "J": (170, 230)}
    return _modelo(m, pos), {}, (SX - 30, 0, SX + 260, 290)


def _enlace_activacion() -> Escena:
    m = M().partial("R").var("p").step("H", True, kind="enclosing").step("I", True, partial="R").step("J", partial="R")
    m.trans("v", ["I"], ["J"], "p", partial="R").enclosure("H", "R", ["J"])
    pos = {"H": (40, 40), "I": (170, 70), "v": (170, 150), "J": (170, 230)}
    return _modelo(m, pos), {}, (SX + 70, 180, SX + 270, 280)


def _orden_forzado() -> Escena:
    m = M().partial("G").step("H", True).step("A", True, partial="G").step("B", partial="G")
    m.force("F", "H", "G", "explicit", ["B"])
    pos = {"H": (40, 40), "A": (400, 40), "B": (400, 140)}
    estado = {"situation": ["H"], "forces": [{"order": "F"}], "activeActions": ["F"]}
    return _modelo(m, pos), estado, _region(110, 40, 250, 80)


def _temporizador(vencido: bool) -> Escena:
    m = M().var("fin").step("E1", True).step("E2")
    m.trans("t1", ["E1"], ["E2"], "delay(3 s, active(E1), 0 s) AND fin")
    vista = Vista("leyenda", "", "", lambda: (m, {"E1": (40, 40), "t1": (40, 120), "E2": (40, 200)}), {})
    vista.act("avanzar", {"us": 3_000_000 if vencido else 1_500_000})
    return vista.model, vista.state(), _region(120, 120, 270, 84)


def _temporizador_contando() -> Escena:
    return _temporizador(False)


def _temporizador_vencido() -> Escena:
    return _temporizador(True)


SECCIONES: tuple[tuple[str, tuple[Entrada, ...]], ...] = (
    ("Etapas", (
        Entrada("Etapa", "Un cuadrado con su nombre. Si no está activa, el borde es negro.", _etapa),
        Entrada("Etapa inicial", "Doble cuadrado: la etapa que está activa al empezar.", _etapa_inicial),
        Entrada("Etapa activa", "Borde y punto verdes, fondo verde claro: la etapa está activa ahora.",
                _etapa_activa),
        Entrada("Etapa inestable", "Borde morado discontinuo: está activa durante un tiempo nulo, sin llegar a "
                "ser estable. «Fue inestable» marca las del último momento.", _etapa_inestable),
    )),
    ("Transiciones", (
        Entrada("Transición en reposo", "Trazo negro con su receptividad a la derecha: todavía no se puede "
                "franquear.", _transicion_reposo),
        Entrada("Transición franqueable", "Trazo verde: sus etapas anteriores están activas y su receptividad es "
                "cierta, así que se franquea.", _transicion_franqueable),
        Entrada("Recién franqueada", "Trazo verde oscuro y más grueso: se acaba de franquear.", _transicion_reciente),
    )),
    ("Acciones", (
        Entrada("Acción continua", "Un rectángulo a la derecha de la etapa: la salida vale 1 mientras la etapa "
                "esté activa.", _accion_continua),
        Entrada("Acción condicionada", "El trazo con texto es la condición: la salida vale 1 si la etapa está "
                "activa y se cumple.", _accion_condicionada),
        Entrada("Al activar", "Flecha hacia arriba: se ejecuta una vez, cuando la etapa se activa.", _accion_activar),
        Entrada("Al desactivar", "Flecha hacia abajo: se ejecuta una vez, cuando la etapa se desactiva.",
                _accion_desactivar),
        Entrada("Por evento", "Banderita: se ejecuta cada vez que ocurre el evento (↑ subida, ↓ bajada), con la "
                "etapa activa.", _accion_evento),
        Entrada("Salida a 1", "Borde y fondo verdes: la acción está dando un 1 en este momento.", _salida_a_uno),
    )),
    ("Jerarquía y forzado", (
        Entrada("Macroetapa", "Cuadrado con dos rayas, arriba y abajo: representa otro grafcet (su expansión). Está "
                "activa mientras lo esté alguna etapa de la expansión.", _macroetapa),
        Entrada("Etapa encapsulante", "Cuadrado con las esquinas cortadas: al activarse pone en marcha un grafcet "
                "parcial.", _encapsulante),
        Entrada("Recinto", "Marco que rodea el grafcet parcial de una encapsulante: ella arriba, su nombre abajo.",
                _recinto),
        Entrada("Enlace de activación", "El asterisco junto a una etapa: se activa con la encapsulante. Los "
                "trazos discontinuos entre macroetapa y expansión, o entre encapsulante y recinto, solo se ven con "
                "«Mostrar dependencias».", _enlace_activacion),
        Entrada("Orden de forzado", "Rectángulo doble: mientras su etapa está activa, impone una situación a otro "
                "grafcet. {*} es la actual, {INIT} la inicial y { } la vacía.", _orden_forzado),
    )),
    ("Temporizadores", (
        Entrada("Temporizador contando", "Sobre la duración («3 s») aparece el tiempo que lleva contado.",
                _temporizador_contando),
        Entrada("Temporizador vencido", "Cuando se cumple el tiempo sale «3 s ✓».", _temporizador_vencido),
    )),
    ("Ratón y teclado", (
        Entrada("Ver el estado", "Pase el ratón por una etapa o una transición para ver su estado."),
        Entrada("Acercar y alejar", "La rueda del ratón (con o sin Ctrl) o el pellizco del panel táctil hacen zoom "
                "alrededor del puntero. Mayús + rueda desplaza en horizontal; con dos dedos del panel táctil, en los dos ejes. "
                "También se mueve arrastrándolo con el botón central."),
        Entrada("Encajar el dibujo", "«Centrar todo» (Ctrl+0) lo encaja entero; al simular, el doble clic también."),
        Entrada("Editar", "Doble clic en un elemento abre sus opciones abajo. Supr borra; Ctrl+Z y Ctrl+Y "
                "deshacen y rehacen."),
    )),
)


def textos() -> list[str]:
    """Todo el texto de la leyenda (títulos y frases), para quien lo quiera comprobar sin abrir la ventana."""
    salida: list[str] = []
    for seccion, entradas in SECCIONES:
        salida.append(seccion)
        for e in entradas:
            salida.extend((e.titulo, e.frase))
    return salida


def dibujo(entrada: Entrada) -> QPixmap | None:
    """La miniatura de la entrada, dibujada con `diagrama.dibujar`, o None si no lleva (ratón y teclado)."""
    if entrada.miniatura is None:
        return None
    modelo, estado, region = entrada.miniatura()
    escena = QGraphicsScene()
    dibujar(escena, modelo, estado, dependencias=False)
    if region:
        caja = QRectF(QPointF(region[0], region[1]), QPointF(region[2], region[3]))
    else:
        caja = escena.itemsBoundingRect().adjusted(-RECUADRO, -RECUADRO, RECUADRO, RECUADRO)
    pantalla = QApplication.primaryScreen()
    dpr = pantalla.devicePixelRatio() if pantalla else 1.0
    escala = min(ESCALA, ALTO_MINIATURA / caja.height(), ANCHO_MINIATURA / caja.width())
    pm = QPixmap(max(1, round(caja.width() * escala * dpr)), max(1, round(caja.height() * escala * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(QColor(COL["panel"]))
    p = QPainter(pm)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    escena.render(p, QRectF(0, 0, caja.width() * escala, caja.height() * escala), caja)
    p.end()
    return pm


def _fila(entrada: Entrada) -> QWidget:
    fila = QWidget()
    lay = QHBoxLayout(fila)
    lay.setContentsMargins(0, 4, 0, 4)
    imagen = QLabel()
    imagen.setFixedWidth(ANCHO_MINIATURA)
    imagen.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pm = dibujo(entrada)
    if pm is not None:
        imagen.setPixmap(pm)
        imagen.setStyleSheet(f"background: {COL['panel']}; border: 1px solid {estilo.BORDE}; border-radius: {estilo.R_S}px")
    lay.addWidget(imagen, 0, Qt.AlignmentFlag.AlignTop)
    texto = QLabel(f"<b>{entrada.titulo}</b><br>{entrada.frase}")
    texto.setWordWrap(True)
    texto.setTextFormat(Qt.TextFormat.RichText)
    lay.addWidget(texto, 1)
    return fila


def _seccion(titulo: str, entradas: tuple[Entrada, ...]) -> list[QWidget]:
    cabecera = QLabel(f"<h3>{titulo}</h3>")
    raya = QFrame()
    raya.setFrameShape(QFrame.Shape.HLine)
    raya.setFrameShadow(QFrame.Shadow.Sunken)
    return [cabecera, raya, *(_fila(e) for e in entradas)]


class Leyenda(QDialog):
    """La ventana de la leyenda: no modal, desplazable, con una sección por tema."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Leyenda del dibujo")
        self.resize(760, 620)
        self.setMinimumWidth(520)
        contenido = QWidget()
        lay = QVBoxLayout(contenido)
        for titulo, entradas in SECCIONES:
            for w in _seccion(titulo, entradas):
                lay.addWidget(w)
        lay.addStretch(1)
        self.zona = QScrollArea()
        self.zona.setWidgetResizable(True)
        self.zona.setFrameShape(QFrame.Shape.NoFrame)
        self.zona.setWidget(contenido)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(self.zona)
