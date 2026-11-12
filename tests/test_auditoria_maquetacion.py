"""Auditoría de maquetación (encargo 8 del rediseño): recorre las pantallas de `tools/hoja_contactos.py` a 1366×768, 2000×1250 y media pantalla
(960×1032) y mide las reglas de `docs/GUIA_MAQUETACION.md` (M1–M4, T1–T3, C1–C5, TB1–TB3, B1–B2). Cada regla es una prueba `SAUD…`; lo que no se puede
medir queda en la guía como regla de revisión. Una excepción vive en `EXCEPCIONES`, con su motivo: no se deja sin anotar."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from tools import hoja_contactos as HC
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractScrollArea, QAbstractSpinBox, QApplication, QCheckBox, QComboBox,
                                   QGroupBox, QHeaderView, QLabel, QLineEdit, QPushButton, QScrollBar, QSpinBox, QTableWidget, QToolBar,
                                   QToolButton, QWidget)
    from escritorio import estilo
    from escritorio.paneles import CajaSeccion, EtiquetaAyuda, EtiquetaElidida
    from test_alturas_controles import desbordes, solapes
    QT = True
except ImportError:  # sin PySide6
    QT = False

TAMANOS = ((1366, 768), (2000, 1250), (960, 1032))

# Excepciones revisables: (regla, subcadena del hallazgo, motivo). Un hallazgo que contenga la subcadena y sea de esa regla no falla.
EXCEPCIONES: list[tuple[str, str, str]] = [
    ("C1", "_BotonEntrada", "la entrada de la simulación crece con las líneas de su nombre largo (se parte por los «_» en 2 o 3 líneas; clase `_BotonEntrada`)"),
    ("C1", "selectorVariableAccion", "el selector de variable de la acción se dibuja como una caja de acción de 62 px, a propósito (`ALTO_SELECTOR` de acciones.py)"),
    ("C1", "QPushButton#[Encuadrar", "los botones de la ficha de jerarquía son más bajos (20 px) a propósito: varias filas en una columna estrecha sin que crezca el panel (comentario de `FichaJerarquia`)"),
    ("C1", "QPushButton#[Renombrar", "los botones de la ficha de jerarquía son más bajos (20 px) a propósito: varias filas en una columna estrecha sin que crezca el panel (comentario de `FichaJerarquia`)"),
    ("C5", "_SpinConfiguracion", "la dirección de la tabla avanzada ocupa su celda entera (TB1) y la columna la fija la cabecera «Dirección (base 0)», más ancha que 5 cifras y flechas"),
    ("M4", "«Entradas»", "las cajas de la columna de simulación (Entradas, Salidas y variables) llevan sus tablas de borde a borde: a 218 px de panel no caben las cuatro columnas con 16 px más de margen (SRED13); la guía M4 no las lista"),
    ("M4", "«Salidas y variables»", "ídem: la tabla de estado va de borde a borde del panel de simulación (SRED13)"),
    ("M4", "«Traza»", "ídem: la lista de la traza va de borde a borde"),
    ("M3", "BandaModo", "la franja de color del modo cubre el borde superior de la tarjeta del dibujo a propósito (decisión de diseño: recorta con las esquinas redondeadas, `_AjustaBanda`)"),
    ("TB1", "tabla columna 0", "la columna «Nombre» de Variables es la que se queda el sobrante de la tabla (columna declarada, como la última)"),
]

# Elementos flotantes declarados (M1/M2): se pintan a propósito sobre otro y no se cuentan como solape. Pares (nombre, nombre, motivo).
FLOTANTES: list[tuple[str, str, str]] = [
    ("barraZoom", "QWidget", "el recuadro del zoom flota sobre el dibujo cuando no cabe en la cabecera (M1: zoom sobre el dibujo)"),
    ("moduloPLC", "LienzoPLC", "el marco del PLC es una capa transparente, sin ratón, sobre las dos columnas (así los nombres quedan fuera)"),
    ("moduloPLC", "QWidget", "el marco del PLC es una capa transparente sobre sus canales"),
    ("moduloPLC", "QStackedWidget", "el marco del PLC es una capa transparente sobre su cabecera"),
    ("BotonPlegar", "TituloSeccion", "el tirador de plegado de un panel flota en la esquina de su cabecera, sobre el hueco que deja el título (que es más corto)"),
    ("BotonPlegar", "QScrollArea", "el tirador de plegado flota en la esquina superior del panel; el contenido deja su sitio libre arriba (cabecera de cada panel)"),
    ("BotonPlegar", "QWidget", "el tirador de plegado flota en la esquina de la cabecera del panel"),
    ("BotonPlegar", "PanelPropiedades", "el tirador de plegado flota en la esquina de la cabecera del panel"),
]
NOMBRES_FLOTANTES = {"barraZoom", "resumenDiagnosticos", "moduloPLC", "listaDiagnosticos", "indicadorDiagnosticos", "BotonPlegar"}


def permitida(regla: str, texto: str) -> bool:
    return any(r == regla and s in texto for r, s, _ in EXCEPCIONES)


def _desc(w: QWidget) -> str:
    t = w.text() if isinstance(w, (QAbstractButton, QLabel)) else ""
    return f"{type(w).__name__}#{w.objectName()}[{t[:30]}]"


def hijos_de(raiz: QWidget, clase=QWidget, *args):
    """Los descendientes de `raiz` que son de su misma ventana (`findChildren` cruza a los diálogos: cada uno se mide como su propia raíz)."""
    return [w for w in raiz.findChildren(clase, *args) if w.window() is raiz.window()]


def visibles(raiz: QWidget):
    for w in hijos_de(raiz):
        if w.isVisible() and w.width() > 0 and w.height() > 0 and not w.isWindow():
            yield w


def _en_vista_de_lista(w: QWidget, raiz: QWidget) -> bool:
    p = w.parentWidget()
    while p is not None and p is not raiz:
        if isinstance(p, QAbstractItemView):
            return True
        p = p.parentWidget()
    return False


def _contenido_desplazable(w: QWidget, raiz: QWidget) -> bool:
    p = w.parentWidget()
    while p is not None and p is not raiz:
        if isinstance(p.parentWidget(), QAbstractScrollArea) and p is p.parentWidget().viewport():
            return True
        p = p.parentWidget()
    return False


# ----------------------------------------------------------------------------------------------------------------- las reglas
def regla_M1(raiz):
    return [f"{d}" for d in desbordes(raiz, 0)]


def regla_M2(raiz):
    """Hermanos visibles que se solapan: los de un mismo layout (`solapes`) y los de un mismo padre fuera de layout (flotantes no declarados)."""
    out = [str(s) for s in solapes(raiz)]
    declarados = {x for a, b, _ in FLOTANTES for x in (a, b)} | NOMBRES_FLOTANTES
    for p in [raiz, *hijos_de(raiz)]:
        if not p.isVisible() or (isinstance(p.parentWidget(), QAbstractScrollArea) and p is p.parentWidget().viewport()):
            continue  # (el contenido de un área de desplazamiento se coloca por dentro de ella: sus widgets de celda sin colocar no cuentan)
        hijos = [h for h in p.children() if isinstance(h, QWidget) and h.isVisible() and not h.isWindow() and h.width() > 0 and h.height() > 0]
        if isinstance(p, QAbstractScrollArea):
            hijos = [h for h in hijos if h is not p.viewport() and not isinstance(h, QScrollBar) and not h.objectName().startswith("qt_")]
        for i, a in enumerate(hijos):
            for b in hijos[i + 1:]:
                r = a.geometry().intersected(b.geometry())
                if r.width() > 1 and r.height() > 1 and not ({a.objectName(), type(a).__name__} & declarados or {b.objectName(), type(b).__name__} & declarados):
                    out.append(f"{type(p).__name__}#{p.objectName()}: {_desc(a)}{a.geometry().getRect()} x {_desc(b)}{b.geometry().getRect()}")
        flot = [h for h in hijos if h.objectName() in NOMBRES_FLOTANTES or isinstance(p, QAbstractScrollArea)]
        for i, a in enumerate(flot):  # (los flotantes declarados tampoco se pisan entre sí: el zoom y el aviso de diagnósticos)
            for b in flot[i + 1:]:
                r = a.geometry().intersected(b.geometry())
                if r.width() > 1 and r.height() > 1 and a.objectName() in NOMBRES_FLOTANTES - {"BotonPlegar"} and b.objectName() in NOMBRES_FLOTANTES - {"BotonPlegar"}:
                    out.append(f"flotantes entre sí en {type(p).__name__}: {_desc(a)}{a.geometry().getRect()} x {_desc(b)}{b.geometry().getRect()}")
    return out


def _cajas_con_borde(raiz):
    return [w for w in visibles(raiz) if w.objectName() in ("panelDibujo", "panelElementos", "panelVariables", "panelPropiedades")]


def regla_M3(raiz):
    """Ningún hijo directo de una caja con borde toca su borde: queda al menos 1 px."""
    out = []
    for caja in _cajas_con_borde(raiz):
        interior = caja.rect().adjusted(1, 1, -1, -1)
        for h in caja.children():
            if isinstance(h, QWidget) and h.isVisible() and not h.isWindow() and h.width() > 0 and not interior.contains(h.geometry()):
                out.append(f"{_desc(caja)}{caja.rect().getRect()} ← {_desc(h)}{h.geometry().getRect()}")
    return out


def _secciones(raiz):
    return [w for w in visibles(raiz) if isinstance(w, CajaSeccion)]


def _margenes_caja(caja):
    hijos = [h for h in caja.children() if isinstance(h, QWidget) and h.isVisible() and not h.isWindow() and h.width() > 0]
    if not hijos:
        return None
    return min(h.x() for h in hijos), caja.width() - max(h.geometry().right() + 1 for h in hijos)


def regla_M4(raiz):
    """El contenido de una sección (caja con título) empieza a E2 del borde izquierdo y termina a E2 del derecho (±1; el borde cuenta 1)."""
    out = []
    for caja in _secciones(raiz):
        m = _margenes_caja(caja)
        if m is None:
            continue
        izq, der = m
        if abs(izq - (estilo.E2 + 1)) > 1 and abs(izq - estilo.E2) > 1 or abs(der - (estilo.E2 + 1)) > 1 and abs(der - estilo.E2) > 1:
            out.append(f"{_desc(caja)} «{caja.title()}»: margen izq {izq}, der {der} (E2={estilo.E2})")
    return out


def regla_T1(raiz):
    """El cuadrado y el texto del título de una sección están enteros dentro de la caja, con la misma sangría en todas."""
    out, sangrias = [], []
    for caja in _secciones(raiz):
        from PySide6.QtWidgets import QStyle, QStyleOptionGroupBox
        op = QStyleOptionGroupBox()
        caja.initStyleOption(op)
        r = caja.style().subControlRect(QStyle.ComplexControl.CC_GroupBox, op, QStyle.SubControl.SC_GroupBoxLabel, caja)
        cuadrado_izq = r.left() - 16 - 5
        if cuadrado_izq < 1 or r.right() > caja.width() - 1 or r.top() < 0:
            out.append(f"{_desc(caja)} «{caja.title()}»: título {r.getRect()} fuera de la caja {caja.rect().getRect()}")
        sangrias.append((r.left(), caja))
    if sangrias and max(s for s, _ in sangrias) - min(s for s, _ in sangrias) > 1:
        out.append("sangrías distintas: " + ", ".join(f"{c.title()}={s}" for s, c in sangrias))
    return out


def regla_T2(raiz):
    """Una sección con el contenido centrado (el marco del PLC) lleva su título centrado sobre él."""
    out = []
    for t in hijos_de(raiz, QLabel, "tituloPLC"):
        marco = raiz.findChild(QWidget, "moduloPLC")
        if t.isVisible() and marco is not None and marco.isVisible():
            ct = t.mapTo(raiz, QPoint(t.width() // 2, 0)).x()
            texto = t.fontMetrics().horizontalAdvance(t.text())
            if t.alignment() & Qt.AlignmentFlag.AlignHCenter:
                centro = ct
            else:
                centro = t.mapTo(raiz, QPoint(t.contentsMargins().left() + texto // 2, 0)).x()
            cm = marco.mapTo(raiz, QPoint(marco.width() // 2, 0)).x()
            if abs(centro - cm) > 2:
                out.append(f"título «{t.text()}» centrado en {centro}, marco en {cm}")
    return out


def regla_T3(raiz):
    """Entre el título de una sección y lo primero de ella quedan E2 (±2)."""
    out = []
    for caja in _secciones(raiz):
        from PySide6.QtWidgets import QStyle, QStyleOptionGroupBox
        op = QStyleOptionGroupBox()
        caja.initStyleOption(op)
        r = caja.style().subControlRect(QStyle.ComplexControl.CC_GroupBox, op, QStyle.SubControl.SC_GroupBoxLabel, caja)
        hijos = [h for h in caja.children() if isinstance(h, QWidget) and h.isVisible() and not h.isWindow() and h.height() > 0]
        if hijos:
            hueco = min(h.y() for h in hijos) - r.bottom() - 1
            if abs(hueco - estilo.E2) > 2:
                out.append(f"{_desc(caja)} «{caja.title()}»: hueco {hueco} bajo el título (E2={estilo.E2})")
    return out


def _alturas_token():
    return {estilo.ALTO_CONTROL, estilo.ALTO_CONTROL_COMPACTO, estilo.ALTO_BARRA, estilo.ALTO_BARRA_COMPACTA}


def regla_C1(raiz):
    """Botones, campos, desplegables y spinbox sueltos miden el alto de un token (±1)."""
    out = []
    for w in visibles(raiz):
        if not isinstance(w, (QPushButton, QLineEdit, QComboBox, QAbstractSpinBox)) or _en_vista_de_lista(w, raiz):
            continue
        if isinstance(w.parentWidget(), (QAbstractSpinBox, QComboBox)) or w.objectName().startswith("qt_"):
            continue
        if not any(abs(w.height() - a) <= 1 for a in _alturas_token()):
            out.append(f"{_desc(w)} mide {w.height()} (tokens {sorted(_alturas_token())})")
    return out


def _elidida(w):
    return isinstance(w, (EtiquetaElidida, EtiquetaAyuda))


def regla_C2(raiz):
    """El texto cabe entero; si se acorta con «…», lleva ayuda emergente."""
    out = []
    for w in visibles(raiz):
        if _en_vista_de_lista(w, raiz):
            continue
        if isinstance(w, QLabel) and w.text() and not w.wordWrap() and w.pixmap().isNull() if isinstance(w, QLabel) else False:
            if w.textFormat() == Qt.TextFormat.RichText or "<" in w.text():
                continue
            fm = w.fontMetrics()
            ancho = max(fm.horizontalAdvance(l) for l in w.text().split("\n"))
            if ancho > w.contentsRect().width() + 1:
                if _elidida(w) and w.toolTip():
                    continue
                out.append(f"{_desc(w)}: texto {ancho} px > {w.contentsRect().width()} px")
        elif isinstance(w, (QPushButton, QCheckBox)) and w.text():
            ancho = w.sizeHint().width()
            if ancho > w.width() + 1 and not w.toolTip():
                out.append(f"{_desc(w)}: pide {ancho} px, mide {w.width()}")
            elif ancho > w.width() + 1:
                out.append(f"{_desc(w)}: pide {ancho} px, mide {w.width()} (con ayuda)")
        elif isinstance(w, QToolButton) and w.text() and w.toolButtonStyle() != Qt.ToolButtonStyle.ToolButtonIconOnly:
            ancho = w.sizeHint().width()
            if ancho > w.width() + 1:
                out.append(f"{_desc(w)}: pide {ancho} px, mide {w.width()}")
        elif isinstance(w, QComboBox) and w.currentText() and not isinstance(w.parentWidget(), QAbstractItemView):
            fm = w.fontMetrics()
            if fm.horizontalAdvance(w.currentText()) + 24 + 8 > w.width() + 1 and w.currentIndex() >= 0 and not w.toolTip():
                out.append(f"{_desc(w)}: «{w.currentText()}» no cabe en {w.width()} px")
    for t in hijos_de(raiz, QTableWidget):
        if not t.isVisible():
            continue
        cab = t.horizontalHeader()
        for c in range(t.columnCount()):
            if t.isColumnHidden(c):
                continue
            it = t.horizontalHeaderItem(c)
            if getattr(cab, "abreviaturas", None):
                continue  # (cabecera que abrevia sus textos según el sitio: la medida de lo que se ve la lleva ella)
            pide = max((cab.fontMetrics().horizontalAdvance(l) for l in it.text().split(chr(10))), default=0) + 4 if it is not None else 0  # (una cabecera puede ir en dos líneas)
            if it is not None and it.text() and cab.sectionSize(c) < pide:
                out.append(f"cabecera «{it.text()}» de {t.objectName() or 'tabla'}: el texto pide {pide}, la columna mide {cab.sectionSize(c)}")
        fm = t.fontMetrics()
        for f in range(t.rowCount()):
            for c in range(t.columnCount()):
                it = t.item(f, c)
                if it is not None and it.text() and not t.isColumnHidden(c) and fm.horizontalAdvance(it.text()) + 12 > t.columnWidth(c) and not (it.toolTip() or it.data(Qt.ItemDataRole.UserRole)):
                    out.append(f"celda ({f},{c}) «{it.text()[:30]}» de {t.objectName() or 'tabla'}: se acorta sin ayuda emergente")
    return out


def regla_C3(raiz):
    """El contenido de un botón de ancho fijo va centrado (hueco izquierdo y derecho iguales ±3 px, medido sobre la imagen)."""
    out = []
    for w in visibles(raiz):
        if isinstance(w, (QPushButton, QToolButton)) and w.text() and w.minimumWidth() == w.maximumWidth() and not _en_vista_de_lista(w, raiz):
            img = w.grab().toImage()
            fondo = img.pixelColor(6, img.height() // 2)
            xs = [x for x in range(6, img.width() - 6) for y in range(6, img.height() - 6, 2) if _distinto(img.pixelColor(x, y), fondo)]
            if xs:
                izq, der = min(xs) - 0, img.width() - 1 - max(xs)
                if abs(izq - der) > 4:
                    out.append(f"{_desc(w)}: hueco izq {izq}, der {der} en {w.width()} px")
    return out


def _distinto(a, b, umbral=60):
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) > umbral


def regla_C4(raiz):
    """Un botón que ocupa casi el ancho de su caja deja el mismo margen a izquierda y derecha (±1)."""
    out = []
    for w in visibles(raiz):
        p = w.parentWidget()
        if isinstance(w, QPushButton) and p is not None and not isinstance(p, QAbstractItemView) and w.width() >= 0.8 * p.width() and not _en_vista_de_lista(w, raiz):
            izq, der = w.x(), p.width() - (w.x() + w.width())
            if abs(izq - der) > 1:
                out.append(f"{_desc(w)}: margen izq {izq}, der {der} en {p.width()} px")
    return out


def regla_C5(raiz):
    """Un campo numérico mide lo que pide su mayor valor más las flechas, sin hueco sobrante."""
    out = []
    for w in visibles(raiz):
        if isinstance(w, QSpinBox) and not isinstance(w.parentWidget(), QAbstractSpinBox):
            cifras = min(5, len(str(w.maximum())))
            justo = w.fontMetrics().horizontalAdvance("0" * cifras) + 44
            if w.width() > justo + 24:
                out.append(f"{_desc(w)} máx {w.maximum()}: mide {w.width()}, lo justo ≈ {justo}")
    return out


def regla_TB1(raiz):
    """Una columna no tiene hueco (mide lo que pide su contenido o cabecera, salvo la última); un control de celda la ocupa entera (≥ ancho − 4)."""
    out = []
    for t in hijos_de(raiz, QTableWidget):
        if not t.isVisible() or t.columnCount() == 0:
            continue
        cab = t.horizontalHeader()
        for f in range(t.rowCount()):
            for c in range(t.columnCount()):
                cw = t.cellWidget(f, c)
                if cw is not None and cw.isVisible() and cw.width() < t.columnWidth(c) - 4:
                    out.append(f"{t.objectName() or 'tabla'} ({f},{c}) {_desc(cw)}: {cw.width()} px en columna de {t.columnWidth(c)}")
        if t.rowCount() == 0:
            continue
        ultima = max(c for c in range(t.columnCount()) if not t.isColumnHidden(c))
        fm = t.fontMetrics()
        for c in range(t.columnCount()):
            if t.isColumnHidden(c) or c == ultima or cab.sectionResizeMode(c) == QHeaderView.ResizeMode.Stretch:
                continue
            pide = [cab.sectionSizeFromContents(c).width()]
            for f in range(t.rowCount()):
                it, cw = t.item(f, c), t.cellWidget(f, c)
                if it is not None and it.text():
                    pide.append(fm.horizontalAdvance(it.text()) + 16)
                if cw is not None:
                    pide.append(cw.sizeHint().width())
            if t.columnWidth(c) > max(pide) + 16:
                out.append(f"{t.objectName() or 'tabla'} columna {c}: mide {t.columnWidth(c)}, pide {max(pide)}")
    return out


def regla_TB2(raiz):
    """Una casilla de verificación va centrada en su columna (±2)."""
    out = []
    for t in hijos_de(raiz, QTableWidget):
        if not t.isVisible():
            continue
        for f in range(t.rowCount()):
            for c in range(t.columnCount()):
                cw = t.cellWidget(f, c)
                for cb in ([cw] if isinstance(cw, QCheckBox) else cw.findChildren(QCheckBox) if cw is not None else []):
                    if cb.isVisible() and not cb.text():
                        centro = cb.mapTo(t.viewport(), QPoint(cb.width() // 2, 0)).x()
                        col = t.columnViewportPosition(c) + t.columnWidth(c) // 2
                        if abs(centro - col) > 2:
                            out.append(f"{t.objectName() or 'tabla'} ({f},{c}): casilla en {centro}, columna centrada en {col}")
    return out


def regla_TB3(raiz, ancho):
    """Sin barra horizontal en las tablas de Configuración a 2000×1250; a menos, si no cabe, la tabla se desplaza (no se corta ninguna columna)."""
    out = []
    for t in hijos_de(raiz, QTableWidget):
        if t.isVisible() and t.horizontalScrollBar().isVisible() and ancho >= 2000:
            out.append(f"{t.objectName() or 'tabla'}: barra horizontal a {ancho} px")
    return out


def regla_B1(raiz):
    """La barra de edición separa sus grupos con separadores: | Deshacer·Rehacer | Cortar·Copiar·Pegar·Borrar | Añadir debajo·Dependencias·Errores."""
    out = []
    for tb in hijos_de(raiz, QToolBar, "barraEdicion"):
        acciones = tb.actions()
        seps = [i for i, a in enumerate(acciones) if a.isSeparator()]
        if len(seps) < 3:
            out.append(f"barraEdicion: {len(seps)} separadores (se esperan ≥ 3)")
        for a, b in zip(acciones, acciones[1:]):
            if a.isSeparator() and b.isSeparator():
                out.append("barraEdicion: dos separadores seguidos")
    return out


def regla_B2(raiz):
    """Al estrechar la ventana, ningún botón de las barras queda cortado: se oculta antes el texto que el botón."""
    out = []
    w = raiz
    if hasattr(w, "tb_edit") and hasattr(w, "tb_sim"):
        for barra in (w.tb_edit, w.tb_sim):
            for a in barra.actions():
                if a.isSeparator() or not a.isVisible():
                    continue
                wd = barra.widgetForAction(a)
                if wd is not None and wd.isVisible() and not barra.rect().contains(wd.geometry()):
                    out.append(f"{barra.objectName()}: {_desc(wd)}{wd.geometry().getRect()} fuera de {barra.rect().getRect()}")
        if w.tb_sim.width() + w.tb_edit.width() > w.herramientas_grafcet.width() + 1:
            out.append(f"las dos barras ({w.tb_sim.width()} + {w.tb_edit.width()}) no caben en la fila ({w.herramientas_grafcet.width()})")
    return out


REGLAS = {"M1": regla_M1, "M2": regla_M2, "M3": regla_M3, "M4": regla_M4, "T1": regla_T1, "T2": regla_T2, "T3": regla_T3,
          "C1": regla_C1, "C2": regla_C2, "C3": regla_C3, "C4": regla_C4, "C5": regla_C5, "TB1": regla_TB1, "TB2": regla_TB2, "B1": regla_B1, "B2": regla_B2}


@unittest.skipUnless(QT, "requiere PySide6")
class Auditoria(unittest.TestCase):
    hallazgos: dict[str, list[str]] = {}
    pantallas_vistas: set[tuple[str, int, int]] = set()

    @classmethod
    def setUpClass(cls):
        HC.aplicacion()
        cls.hallazgos = {r: [] for r in (*REGLAS, "TB3")}
        for ancho, alto in TAMANOS:
            for nombre, c in HC.recorrer(ancho, alto):
                cls.pantallas_vistas.add((nombre, ancho, alto))
                raices = [c.w, *(x for x in c.extras if x.isVisible())]
                for raiz in raices:
                    for regla, f in REGLAS.items():
                        if regla in ("B1", "B2") and raiz is not c.w:
                            continue
                        for h in f(raiz):
                            texto = f"{ancho}×{alto} · {nombre}: {h}"
                            if texto not in cls.hallazgos[regla]:  # (la ventana y su diálogo comparten descendientes en `findChildren`)
                                cls.hallazgos[regla].append(texto)
                    for h in regla_TB3(raiz, ancho):
                        cls.hallazgos["TB3"].append(f"{ancho}×{alto} · {nombre}: {h}")

    def _sin_hallazgos(self, regla):
        malos = [h for h in self.hallazgos[regla] if not permitida(regla, h)]
        self.assertEqual(malos, [], f"{regla}: {len(malos)} hallazgos\n" + "\n".join(malos[:40]))

    def test_SAUD00_se_recorren_todas_las_pantallas_a_los_tres_tamaños(self):
        """REQ-UX-01: la auditoría recorre cada pantalla de la hoja de contactos a 1366×768, 2000×1250 y 960×1032."""
        esperadas = {(n, a, h) for n, _ in HC.PANTALLAS for a, h in TAMANOS}
        self.assertEqual(self.pantallas_vistas, esperadas)
        for ancho, alto in TAMANOS:
            self.assertGreaterEqual(sum(1 for n, a, h in self.pantallas_vistas if (a, h) == (ancho, alto)), 21)

    def test_SAUD01_M1_nada_se_sale_de_su_caja(self):
        """REQ-UX-01 (guía M1): ningún control visible se sale del rectángulo de su padre."""
        self._sin_hallazgos("M1")

    def test_SAUD02_M2_nada_pisa_nada(self):
        """REQ-UX-01 (guía M2): dos hermanos visibles no se solapan (salvo los flotantes declarados); el zoom y el aviso de incidencias no se pisan."""
        self._sin_hallazgos("M2")

    def test_SAUD03_M3_el_borde_se_ve_entero(self):
        """REQ-UX-01 (guía M3): ningún hijo directo de una caja con borde toca su borde."""
        self._sin_hallazgos("M3")

    def test_SAUD04_M4_margen_interior_comun(self):
        """REQ-UX-01 (guía M4): el contenido de una sección empieza y acaba a E2 del borde."""
        self._sin_hallazgos("M4")

    def test_SAUD05_T1_titulo_con_cuadrado_entero_y_misma_sangria(self):
        """REQ-UX-01 (guía T1): el cuadrado y el texto del título de una sección están enteros y con la misma sangría."""
        self._sin_hallazgos("T1")

    def test_SAUD06_T2_titulo_de_seccion_centrada(self):
        """REQ-UX-01 (guía T2): el título del PLC va centrado sobre su marco."""
        self._sin_hallazgos("T2")

    def test_SAUD07_T3_hueco_bajo_el_titulo(self):
        """REQ-UX-01 (guía T3): entre el título y lo primero de la sección quedan E2."""
        self._sin_hallazgos("T3")

    def test_SAUD08_C1_alto_del_token(self):
        """REQ-UX-01 (guía C1): botones, campos, desplegables y spinbox sueltos miden un alto de token."""
        self._sin_hallazgos("C1")

    def test_SAUD09_C2_el_texto_cabe(self):
        """REQ-UX-01 (guía C2): botones, etiquetas, desplegables, cabeceras y celdas se leen enteros o se acortan con «…» y ayuda emergente."""
        self._sin_hallazgos("C2")

    def test_SAUD10_C3_contenido_centrado_en_botones_de_ancho_fijo(self):
        """REQ-UX-01 (guía C3): el contenido de un botón de ancho fijo va centrado."""
        self._sin_hallazgos("C3")

    def test_SAUD11_C4_boton_ancho_centrado(self):
        """REQ-UX-01 (guía C4): un botón del ancho de su caja deja el mismo margen a los dos lados."""
        self._sin_hallazgos("C4")

    def test_SAUD12_C5_ancho_justo_para_cifras(self):
        """REQ-UX-01 (guía C5): un campo numérico mide lo que pide su mayor valor más las flechas."""
        self._sin_hallazgos("C5")

    def test_SAUD13_TB1_columnas_sin_hueco(self):
        """REQ-UX-01 (guía TB1): ninguna columna con hueco; un control de celda ocupa la celda."""
        self._sin_hallazgos("TB1")

    def test_SAUD14_TB2_casillas_centradas(self):
        """REQ-UX-01 (guía TB2): las casillas de verificación van centradas en su columna."""
        self._sin_hallazgos("TB2")

    def test_SAUD15_TB3_sin_barra_horizontal_a_2000(self):
        """REQ-UX-01 (guía TB3): sin barra horizontal en las tablas a 2000×1250."""
        self._sin_hallazgos("TB3")

    def test_SAUD16_B1_separadores_de_zona(self):
        """REQ-UX-01 (guía B1): los grupos de la barra de edición van separados."""
        self._sin_hallazgos("B1")

    def test_SAUD17_B2_sin_cortes_al_estrechar(self):
        """REQ-UX-01 (guía B2): las barras de herramientas caben en su fila y no cortan ningún botón a ningún tamaño."""
        self._sin_hallazgos("B2")

    def test_SAUD18_las_excepciones_llevan_motivo(self):
        """REQ-UX-01: cada excepción y cada flotante declarados llevan su motivo."""
        for r, s, motivo in EXCEPCIONES:
            self.assertTrue(r in REGLAS and s and len(motivo) > 15, (r, s))
        for a, b, motivo in FLOTANTES:
            self.assertTrue(a and b and len(motivo) > 15, (a, b))


if __name__ == "__main__":
    unittest.main()
