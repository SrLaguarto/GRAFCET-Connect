"""Ayudas completas con ajuste de línea y anchura limitada a la pantalla disponible."""
import html
import re

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QGuiApplication, QTextDocument
from PySide6.QtWidgets import QAbstractItemView, QApplication, QGraphicsView, QHeaderView, QToolTip, QWidget

from . import estilo

ANCHO_MAXIMO = 400


def ayuda_html(texto, nombre=None, ancho=ANCHO_MAXIMO):
    texto = re.sub(r"\S{25,}", lambda m: "\u200b".join(
        m.group()[i:i + 24] for i in range(0, len(m.group()), 24)), texto)
    contenido = html.escape(texto).replace("\n", "<br>")
    if nombre:
        contenido = "<b>" + html.escape(nombre) + "</b> — " + contenido
    return ('<qt><table width="' + str(max(80, ancho - 2 * estilo.E4))
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
        while item is not None:
            if item.toolTip():
                return item.toolTip()
            item = item.parentItem()
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
