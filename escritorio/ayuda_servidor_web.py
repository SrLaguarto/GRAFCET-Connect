"""Ayuda de activación junto al aviso de conexión existente; solo tras un fallo de red directo."""
import re

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton

from conexion import servidor_web_simulador as servidor
from conexion.http_directo import AVISO_SIN_SERVIDOR
from . import estilo

HECHO = "Hecho. Reinicia el simulador y pulsa Conectar."
YA_ACTIVO = "Ábrelo o reinícialo, con el controlador en «Ninguno»."  # (su servidor web ya está activado en auto.cfg)
FALTA = "su servidor web no está activado."  # (el botón de al lado dice qué hacer)
MANUAL = "activa app.web_server = True en su auto.cfg y reinicia el simulador"


def no_responde(mensaje):
    """«No responde el simulador de fábricas (host:puerto).», sacado del aviso general: cuando se sabe qué pasa, el aviso
    dice solo eso, sin la explicación manual (consola, auto.cfg), que queda para cuando no se encuentra la carpeta."""
    dato = re.search(r"\(([^()]*:\d+)\)", mensaje)
    return AVISO_SIN_SERVIDOR + (f" ({dato.group(1)})" if dato else "")


class AyudaServidorWeb(QObject):
    texto_cambiado = Signal(str, bool)

    def __init__(self, etiqueta, layout, fila=None, al_activar=None, reintentar="Conectar"):
        super().__init__(etiqueta)
        self.al_activar = al_activar  # (deja de pintar el aviso como error: «Hecho» es una buena noticia)
        self.etiqueta = etiqueta
        self.fila = fila
        self.abierta = False
        self.ultimo = None
        self.texto = ""
        self.reintentar = reintentar
        self.boton = QPushButton("Activar el servidor web")
        self.boton.setFixedHeight(estilo.ALTO_CONTROL)
        self.boton.hide()
        layout.addWidget(self.boton)
        self.boton.clicked.connect(self.activar)

    def mostrar(self, mensaje, directo=True):
        relevante = directo and AVISO_SIN_SERVIDOR in mensaje
        self.boton.setFixedHeight(estilo.ALTO_CONTROL)
        if not relevante:
            self.boton.hide()
            self.ultimo = None
            if self.abierta and self.fila is not None and not self.etiqueta.nota:
                self.fila.hide()
            self.abierta = False
            return mensaje
        if self.fila is not None:
            self.fila.show()
        self.abierta = True
        if mensaje != self.ultimo:
            self.ultimo = mensaje
            self.texto = mensaje
            self.boton.hide()
            try:
                estado = servidor.estado()
            except (OSError, ValueError, UnicodeError) as exc:
                self.texto += f" No se pudo comprobar auto.cfg: {servidor.motivo_error(exc)}"
            else:
                if estado == "falta":
                    self.texto = no_responde(mensaje) + ": " + FALTA
                    self.boton.show()
                elif estado == "activo":
                    self.texto = no_responde(mensaje) + ". " + YA_ACTIVO
                elif estado in ("sin_carpeta", "varias"):
                    self.texto = no_responde(mensaje) + ": " + MANUAL + "."
        return self.texto

    def activar(self):
        resultado = servidor.activar()
        if resultado.correcto:
            self.texto = HECHO.replace("Conectar", self.reintentar)
            self.boton.hide()
            self.etiqueta.setStyleSheet(f"color:{estilo.TINTA}; font-weight:600")
            if self.al_activar is not None:
                self.al_activar()
        else:
            self.texto = resultado.motivo
        self.etiqueta.setText(self.texto)
        self.texto_cambiado.emit(self.texto, not self.boton.isHidden())
