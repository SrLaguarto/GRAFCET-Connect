"""Ayudas completas con ajuste de línea y anchura limitada a la pantalla disponible."""
import html
import re

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFontMetrics, QGuiApplication, QTextDocument
from PySide6.QtWidgets import QAbstractItemView, QApplication, QGraphicsView, QHeaderView, QToolTip, QWidget

from . import estilo

ANCHO_MAXIMO = 400


def ayuda_html(texto, nombre=None, ancho=ANCHO_MAXIMO):
    partido = re.sub(r"\S{25,}", lambda m: "\u200b".join(
        m.group()[i:i + 24] for i in range(0, len(m.group()), 24)), texto)
    contenido = html.escape(partido).replace("\n", "<br>")
    if nombre:
        contenido = "<b>" + html.escape(nombre) + "</b> — " + contenido
    celda = max(80, ancho - 2 * estilo.E4)
    plana = (f"{nombre} — {texto}" if nombre else texto).replace("\u200b", "")
    fm_tip = QFontMetrics(QToolTip.font())
    fm_est = QFontMetrics(estilo.fuente())
    largo = max(
        (max(fm_tip.horizontalAdvance(linea), fm_est.horizontalAdvance(linea)) for linea in plana.split("\n")),
        default=0,
    )
    if largo <= celda - 12:
        return f"<qt>{contenido}</qt>"
    return ('<qt><table width="' + str(celda)
            + '" cellpadding="0" cellspacing="0"><tr><td>' + contenido + '</td></tr></table></qt>')


def texto_plano(texto):
    documento = QTextDocument()
    documento.setHtml(texto)
    return documento.toPlainText()


def texto_del_control(objeto, evento):
    texto = objeto.toolTip()
    if texto:
        return texto
    padre = objeto.parentWidget()
    if isinstance(padre, QHeaderView):
        seccion = padre.logicalIndexAt(evento.pos())
        texto = padre.model().headerData(seccion, padre.orientation(), Qt.ItemDataRole.ToolTipRole)
        return texto if isinstance(texto, str) else ""
    if isinstance(padre, QAbstractItemView):
        texto = padre.indexAt(evento.pos()).data(Qt.ItemDataRole.ToolTipRole)
        return texto if isinstance(texto, str) else ""
    if isinstance(padre, QGraphicsView):
        item = padre.itemAt(evento.pos())
        if item is not None:
            if item.toolTip():
                return item.toolTip()
            # La ayuda de un ítem hijo (la nota de texto o de imagen) es la de su raíz. No se sube con `parentItem()`: en PySide6,
            # llamarlo en un ítem sin padre lo deja como propiedad de Python y, al morir su envoltorio, lo borra de la escena.
            raiz = item.topLevelItem()
            if raiz is not item and raiz.toolTip():
                return raiz.toolTip()
    return ""


def mostrar_ayuda(posicion, texto, objeto):
    pantalla = QGuiApplication.screenAt(posicion) or objeto.screen()
    ancho = min(ANCHO_MAXIMO, pantalla.availableGeometry().width() - 2 * estilo.E2)
    if texto.startswith('<qt><table width="'):
        texto = texto.replace('width="' + str(ANCHO_MAXIMO - 2 * estilo.E4) + '"',
                              'width="' + str(ancho - 2 * estilo.E4) + '"', 1)
    else:
        if texto.lstrip().startswith("<"):
            texto = texto_plano(texto)
        texto = ayuda_html(texto, ancho=ancho)
    QToolTip.showText(posicion, texto, objeto)


class AyudasAjustadas(QObject):
    def eventFilter(self, objeto, evento):
        if evento.type() != QEvent.Type.ToolTip or not isinstance(objeto, QWidget):
            return False
        texto = texto_del_control(objeto, evento)
        if not texto:
            return False
        mostrar_ayuda(evento.globalPos(), texto, objeto)
        evento.accept()
        return True


def instalar():
    app = QApplication.instance()
    if app is None or app.findChild(AyudasAjustadas, "ayudasAjustadas") is not None:
        return
    filtro = AyudasAjustadas(app)
    filtro.setObjectName("ayudasAjustadas")
    app.installEventFilter(filtro)
