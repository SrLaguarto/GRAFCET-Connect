"""Hoja de contactos de la interfaz de escritorio: todas las pantallas que audita `tests/test_auditoria_maquetacion.py`, a cada tamaño.

    python tools/hoja_contactos.py CARPETA [ANCHOxALTO ...]

Escribe en CARPETA, por tamaño, `hoja_<ancho>x<alto>.png` (una miniatura de cada pantalla con su nombre debajo) y, en `<ancho>x<alto>/`, cada
pantalla suelta a tamaño real. Sin tamaños, los tres de la auditoría (1366×768, 2000×1250 y media pantalla, 960×1032). Usa la plataforma
`offscreen` de Qt y no toca el repositorio ni los ajustes del usuario (cada ventana lleva unos `QSettings` temporales).

`recorrer(ancho, alto)` es la fuente de las pantallas: la prueba de auditoría la usa para medirlas.
"""
from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("GRAFCONNECT_SIN_ACTUALIZAR", "1")

from PySide6.QtCore import QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QWidget  # noqa: E402

TAMANOS = ((1366, 768), (2000, 1250), (960, 1032))
SX = 100  # margen izquierdo del dibujo (escritorio.diagrama.SX)


def _bombear(n: int = 8) -> None:
    for _ in range(n):
        QApplication.processEvents()


def aplicacion() -> QApplication:
    return QApplication.instance() or QApplication([])


# ----------------------------------------------------------------------------------------------------- el grafcet de ejemplo
def grafcet_de_ejemplo(e: Any, con_error: bool = False) -> dict[str, Any]:
    """Un grafcet pequeño y realista: cinco variables, cuatro etapas con sus transiciones, una acción continua y una condicionada. Con
    `con_error`, una transición sin receptividad ni enlaces (un error que impide simular)."""
    for nombre, papel, tipo in (("marcha", "input", None), ("paro", "input", None), ("motor", "output", None), ("luz", "output", None),
                                ("aux", "internal", None)):
        e.nueva_variable(nombre, papel, tipo)
    ids = []
    for y, etapa in ((60, "0"), (140, None), (220, "1"), (300, None), (380, "2"), (460, None)):
        ids.append(e.poner_etapa(QPointF(SX, y)) if etapa is not None else e.poner_transicion(QPointF(SX, y)))
    e.tipo_etapa(ids[0], True)
    for k, ident in enumerate(ids):
        if k:
            e.conectar(ids[k - 1], ident)
    for ident, cond in zip((ids[1], ids[3], ids[5]), ("marcha", "paro", "NOT marcha")):
        e.poner_condicion(ident, cond)
    e.conectar(ids[5], ids[0])
    e.poner_accion(ids[2], {"variable": "motor", "tipo": "continua"})
    e.poner_accion(ids[4], {"variable": "luz", "tipo": "condicionada", "condicion": "marcha"})
    if con_error:
        e.ed.add_transition("g", "", label="t_sin_receptividad", at=(300, 200))
        e.cambia()
    return {"etapas": [ids[0], ids[2], ids[4]], "transiciones": [ids[1], ids[3], ids[5]]}


class Contexto:
    """Una ventana principal nueva y aislada, con un grafcet nuevo, y los diálogos que se abran desde ella."""

    def __init__(self, ancho: int, alto: int) -> None:
        aplicacion()
        from escritorio.ventana import Ventana
        self.tmp = tempfile.TemporaryDirectory()
        self.w = Ventana(QSettings(str(Path(self.tmp.name) / "a.ini"), QSettings.Format.IniFormat))
        self.w.nuevo()
        self.e = self.w.edicion
        self.e.ed.dirty = False
        self.e.confirmar_borrado = lambda plan: True
        self.e.pedir_texto = lambda titulo, etiqueta, actual: actual
        self.ids: dict[str, Any] = {}
        self.extras: list[QWidget] = []
        self.w.resize(ancho, alto)

    def mostrar(self) -> None:
        self.w.show()
        _bombear()

    def cerrar(self) -> None:
        for x in self.extras:
            x.close()
            x.deleteLater()
        self.w.a_ejecutar.setChecked(False)
        self.w.edicion = None  # sin preguntar al cerrar
        self.w.hide()
        self.w.deleteLater()
        _bombear(2)
        self.tmp.cleanup()


# ----------------------------------------------------------------------------------------------------- las pantallas
def _edicion(c: Contexto, error: bool = False) -> None:
    c.ids = grafcet_de_ejemplo(c.e, con_error=error)
    c.mostrar()


def _con_seleccion(que: str) -> Callable[[Contexto], None]:
    def preparar(c: Contexto) -> None:
        _edicion(c)
        e, w = c.e, c.w
        if que == "etapa":
            sel = [c.ids["etapas"][0]]
        elif que == "transicion":
            sel = [c.ids["transiciones"][0]]
        elif que == "accion":
            aid = next(a["id"] for a in e.ed.model["actions"] if e.datos_accion(a["id"])["tipo"] == "condicionada")
            sel = [aid]
        elif que == "macroetapa":
            sel = [e.poner_macro(QPointF(SX + 300, 120))]
        else:  # varios
            sel = [c.ids["etapas"][0], c.ids["transiciones"][0]]
        e.seleccionar(sel)
        w._abrir_opciones()
        _bombear(10)
    return preparar


def _props_plegado(c: Contexto) -> None:
    _edicion(c)
    c.e.seleccionar([c.ids["etapas"][0]])
    c.w._abrir_opciones()
    _bombear(6)
    c.w._mostrar_panel("inferior", False)
    _bombear(8)


def _simulacion(c: Contexto) -> None:
    _edicion(c)
    c.w.cambiar_modo("simular")
    _bombear(10)


def _variables(n: int) -> Callable[[Contexto], None]:
    def preparar(c: Contexto) -> None:
        if n:
            for k in range(n):
                c.e.nueva_variable(f"variable_{k + 1}", ("input", "output", "internal")[k % 3])
        c.mostrar()
        c.w._mostrar_panel("derecho", True)
        _bombear(8)
    return preparar


def _es(conectado: bool) -> Callable[[Contexto], None]:
    def preparar(c: Contexto) -> None:
        _edicion(c)
        c.w.mostrar_es()
        _bombear(8)
        if conectado:
            c.w.panel_es.mostrar_estado("conectado", "Conectado")
            _bombear(8)
    return preparar


def _configuracion(c: Contexto) -> None:
    for n, papel in (("marcha", "input"), ("paro", "input"), ("motor", "output")):
        c.e.nueva_variable(n, papel)
    c.mostrar()
    c.w.mostrar_es()
    _bombear(8)
    p = c.w.panel_es
    p.abrir_configuracion()
    p._alternar_avanzado()
    _bombear(10)
    c.extras.append(p.dialogo_config)


def _planos(con_hoja: bool) -> Callable[[Contexto], None]:
    def preparar(c: Contexto) -> None:
        from PySide6.QtTest import QTest
        from escritorio.carpetas import predeterminada
        from grafcet.laminas import ajustes_lamina
        _edicion(c)
        barra = c.w.pestanas_vistas
        QTest.mouseClick(barra, Qt.MouseButton.LeftButton, pos=barra.tabRect(1).center())
        _bombear(8)
        if con_hoja:
            plan = c.e.ed.add_sheet_plan("Plano de pruebas")
            ident = c.e.ed.add_plan_page(plan, ajustes_lamina({"plantilla": predeterminada()}))
            c.e.ed.set_page_graphics(ident, [{"refs": [c.ids["etapas"][0]], "porcentaje": 100., "offset_mm": [0., 0.]}])
            c.e.cambia()
            QTest.mouseClick(barra, Qt.MouseButton.LeftButton, pos=barra.tabRect(0).center())
            QTest.mouseClick(barra, Qt.MouseButton.LeftButton, pos=barra.tabRect(1).center())
            _bombear(10)
    return preparar


def _dialogo(cual: str) -> Callable[[Contexto], None]:
    def preparar(c: Contexto) -> None:
        _edicion(c)
        w = c.w
        if cual == "propiedades_archivo":
            from escritorio import propiedades_archivo
            d = propiedades_archivo.PropiedadesArchivo(propiedades_archivo.recopilar(c.e, True), w)
        elif cual == "ajustes_simulacion":
            from escritorio.ventana import Lecturas
            d = Lecturas(w, w.options)
        elif cual == "leyenda":
            from escritorio.leyenda import Leyenda
            d = Leyenda(w)
        else:
            from escritorio.ventana import AcercaDe
            d = AcercaDe(w)
        d.show()
        d.raise_()
        _bombear(10)
        c.extras.append(d)
    return preparar


def _buscar(c: Contexto) -> None:
    _edicion(c)
    c.w.buscar_elemento()
    _bombear(8)


PANTALLAS: list[tuple[str, Callable[[Contexto], None]]] = [
    ("edicion", _edicion),
    ("edicion_con_errores", lambda c: (_edicion(c, True), c.w.b_errores.setChecked(True), _bombear(8))),
    ("simulacion", _simulacion),
    ("props_etapa", _con_seleccion("etapa")),
    ("props_transicion", _con_seleccion("transicion")),
    ("props_accion_condicionada", _con_seleccion("accion")),
    ("props_macroetapa", _con_seleccion("macroetapa")),
    ("props_varios", _con_seleccion("varios")),
    ("props_plegado", _props_plegado),
    ("variables_vacia", _variables(0)),
    ("variables_12", _variables(12)),
    ("es_desconectada", _es(False)),
    ("es_conectada", _es(True)),
    ("configuracion_avanzada", _configuracion),
    ("planos_sin_hoja", _planos(False)),
    ("planos_con_hoja", _planos(True)),
    ("dialogo_propiedades_archivo", _dialogo("propiedades_archivo")),
    ("dialogo_ajustes_simulacion", _dialogo("ajustes_simulacion")),
    ("dialogo_leyenda", _dialogo("leyenda")),
    ("dialogo_acerca", _dialogo("acerca")),
    ("buscar_elemento", _buscar),
]


@contextmanager
def _sin_cuadros() -> Iterator[None]:
    """Ningún cuadro de mensaje bloquea: la auditoría no los abre, y si algo los pide se contesta lo más inocuo."""
    from PySide6.QtWidgets import QMessageBox
    with mock.patch.object(QMessageBox, "warning"), mock.patch.object(QMessageBox, "information"), \
            mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        yield


def recorrer(ancho: int, alto: int, nombres: list[str] | None = None) -> Iterator[tuple[str, Contexto]]:
    """Cada pantalla, ya preparada, en una ventana nueva de `ancho`×`alto`; al pedir la siguiente se cierra la anterior."""
    with _sin_cuadros():
        for nombre, preparar in PANTALLAS:
            if nombres and nombre not in nombres:
                continue
            c = Contexto(ancho, alto)
            try:
                preparar(c)
                yield nombre, c
            finally:
                c.cerrar()


def imagenes(c: Contexto) -> list[QImage]:
    """La ventana principal y, si hay, cada diálogo abierto (cada uno a su tamaño real)."""
    return [c.w.grab().toImage(), *(x.grab().toImage() for x in c.extras if x.isVisible())]


def _hoja(tarjetas: list[tuple[str, QImage]], ancho_tarjeta: int = 640, columnas: int = 3) -> QImage:
    margen, rotulo = 16, 34
    filas = []
    for i in range(0, len(tarjetas), columnas):
        grupo = tarjetas[i:i + columnas]
        alto = max(im.height() * ancho_tarjeta // max(1, im.width()) for _, im in grupo)
        filas.append((grupo, alto))
    total = sum(alto + rotulo + margen for _, alto in filas) + margen
    hoja = QImage(columnas * (ancho_tarjeta + margen) + margen, total, QImage.Format.Format_RGB32)
    hoja.fill(QColor("#9aa5b1"))
    p = QPainter(hoja)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    y = margen
    for grupo, alto in filas:
        for j, (nombre, im) in enumerate(grupo):
            x = margen + j * (ancho_tarjeta + margen)
            h = im.height() * ancho_tarjeta // max(1, im.width())
            p.drawImage(x, y, im.scaled(ancho_tarjeta, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
            p.setPen(QColor("white"))
            p.drawText(x, y + alto + 4, ancho_tarjeta, rotulo - 4, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, nombre)
        y += alto + rotulo + margen
    p.end()
    return hoja


def generar(carpeta: Path, tamanos: tuple[tuple[int, int], ...] = TAMANOS) -> list[Path]:
    """Una hoja por tamaño y cada pantalla suelta a tamaño real; devuelve las rutas de las hojas."""
    aplicacion()
    carpeta.mkdir(parents=True, exist_ok=True)
    hojas = []
    for ancho, alto in tamanos:
        sueltas = carpeta / f"{ancho}x{alto}"
        sueltas.mkdir(exist_ok=True)
        tarjetas = []
        for nombre, c in recorrer(ancho, alto):
            for k, im in enumerate(imagenes(c)):
                etiqueta = nombre if k == 0 else f"{nombre}_{k}"
                im.save(str(sueltas / f"{etiqueta}.png"))
                tarjetas.append((f"{etiqueta}  ({im.width()}×{im.height()})", im))
        ruta = carpeta / f"hoja_{ancho}x{alto}.png"
        _hoja(tarjetas, ancho_tarjeta=640 if ancho < 1500 else 720).save(str(ruta))
        hojas.append(ruta)
    return hojas


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    tamanos = tuple(tuple(int(x) for x in a.lower().replace("×", "x").split("x")) for a in argv[1:]) or TAMANOS
    for ruta in generar(Path(argv[0]), tamanos):  # type: ignore[arg-type]
        print(ruta)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
