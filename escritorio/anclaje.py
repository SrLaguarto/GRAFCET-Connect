"""Anclaje del dibujo al área cliente, independiente de los paneles y las barras."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF


class AnclajeVentana(QObject):
    """Restaura el ancla durante cambios de geometría, sin diferirlo al siguiente fotograma."""

    def __init__(self, vista):
        super().__init__(vista)
        self.vista = vista
        self.posicion = None
        self.geometria = None
        self.corrigiendo = False
        self.observados = []
        vista.installEventFilter(self)
        vista.viewport().installEventFilter(self)
        vista.horizontalScrollBar().valueChanged.connect(self.desplazado)
        vista.verticalScrollBar().valueChanged.connect(self.desplazado)

    def conectar(self):
        actual = self.vista.parentWidget()
        while actual is not None:
            if actual not in self.observados:
                actual.installEventFilter(self)
                self.observados.append(actual)
            actual = actual.parentWidget()
        self.registrar()

    def _geometria(self):
        v = self.vista
        origen = v.viewport().mapTo(v.window(), QPoint())
        return origen, v.viewport().size(), v.window().size()

    def _posicion(self):
        origen = self.vista.viewport().mapTo(self.vista.window(), QPoint())
        return self.vista.viewportTransform().map(QPointF()) + QPointF(origen)

    def registrar(self):
        if not self.corrigiendo:
            self.posicion = self._posicion()
            self.geometria = self._geometria()

    def desplazado(self):
        # Un cambio de valor por arrastre/rueda es deliberado. El ajuste de rangos
        # durante un cambio de geometría no sustituye el ancla anterior.
        if self._geometria() == self.geometria:
            self.registrar()

    def activo(self):
        v = self.vista
        return v._manual and not v._ajuste_pendiente and v._encuadrando is None and v.isVisible()

    def restaurar(self, forzar=False):
        if self.corrigiendo:
            return
        if self.posicion is None or not self.activo():
            self.registrar()
            return
        v = self.vista
        nueva = self._geometria()
        if nueva == self.geometria and not forzar:
            return
        if self._posicion() == self.posicion:
            self.geometria = nueva
            return
        self.corrigiendo = True
        try:
            local = self.posicion - QPointF(nueva[0])
            actual = v.viewportTransform().map(QPointF())
            esquina = v._a_escena(actual - local)
            # Ampliar primero el rango: ni setSceneRect ni las barras pueden
            # recortar el destino antes de situar el dibujo.
            v._actualizar_escena(esquina)
            v._situar(QPointF(), local)
            self.geometria = self._geometria()
        finally:
            self.corrigiendo = False

    def eventFilter(self, objeto, evento):  # noqa: N802
        tipo = evento.type()
        if tipo in (QEvent.Type.Move, QEvent.Type.Resize):
            if objeto is not self.vista.viewport():
                self.restaurar()
        elif tipo == QEvent.Type.Paint and objeto is self.vista.viewport():
            # Última geometría de los ancestros y del viewport, antes de que Qt
            # pinte la escena. También cubre un Move sin Resize de la vista.
            self.restaurar()
        return False
