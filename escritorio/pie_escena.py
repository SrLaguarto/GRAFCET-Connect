"""El pie de E/S conserva la ayuda ancha al añadir la limpieza junto al contador."""
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget
from shiboken6 import delete


class PieEscena(QObject):
    def __init__(self, panel, boton):
        pie = panel.ayuda_vacio.parentWidget()
        super().__init__(pie)
        self.pie = pie
        self.ayuda = panel.ayuda_vacio
        self.estrecho = None
        viejo = pie.layout()
        margenes = viejo.contentsMargins()
        espaciado = viejo.spacing()
        self.leyenda = QWidget(pie)
        leyenda = QHBoxLayout(self.leyenda)
        leyenda.setContentsMargins(0, 0, 0, 0)
        leyenda.setSpacing(espaciado)
        while viejo.count():
            item = viejo.takeAt(0)
            if item.widget() not in (self.ayuda, panel.resumen):
                if item.widget() is not None:
                    item.widget().setParent(self.leyenda)
                leyenda.addItem(item)
        delete(viejo)
        self.cuentas = QWidget(pie)
        cuentas = QHBoxLayout(self.cuentas)
        cuentas.setContentsMargins(0, 0, 0, 0)
        cuentas.setSpacing(espaciado)
        cuentas.addWidget(panel.resumen)
        cuentas.addWidget(boton)
        self.rejilla = QGridLayout(pie)
        self.rejilla.setContentsMargins(margenes)
        self.rejilla.setSpacing(espaciado)
        pie.installEventFilter(self)
        self.disponer()

    def disponer(self):
        estrecho = self.pie.width() < 900
        if self.estrecho == estrecho:
            return
        self.estrecho = estrecho
        for widget in (self.leyenda, self.ayuda, self.cuentas):
            self.rejilla.removeWidget(widget)
        for col in range(3):
            self.rejilla.setColumnStretch(col, 0)
        self.rejilla.addWidget(self.leyenda, 0, 0)
        if estrecho:
            self.rejilla.addWidget(self.cuentas, 0, 1)
            self.rejilla.addWidget(self.ayuda, 1, 0, 1, 2)
            self.rejilla.setColumnStretch(1, 1)
        else:
            self.rejilla.addWidget(self.ayuda, 0, 1)
            self.rejilla.addWidget(self.cuentas, 0, 2)
            self.rejilla.setColumnStretch(1, 1)

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Type.Resize:
            self.disponer()
        return False
