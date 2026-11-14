"""Los botones estándar de Qt (Aceptar, Cancelar, Guardar, Sí, No…) en español, sin archivos de traducción externos.

Qt pone esos textos desde el contexto «QPlatformTheme». Un texto que no está en la tabla devuelve None: Qt usa entonces su
texto original. (Devolver una cadena vacía dejaba el botón en blanco: el «OK» de los diálogos de texto salía vacío.)"""
from PySide6.QtCore import QTranslator
from PySide6.QtWidgets import QApplication

NOMBRE = "botonesGuardadoEspanol"
TEXTOS = {
    "OK": "Aceptar", "Cancel": "Cancelar", "Save": "Guardar", "Discard": "Descartar", "Don't Save": "No guardar",
    "Save All": "Guardar todo", "Open": "Abrir", "Close": "Cerrar", "Apply": "Aplicar", "Reset": "Restablecer",
    "Restore Defaults": "Restaurar valores predeterminados", "Help": "Ayuda", "Yes": "Sí", "No": "No",
    "Yes to All": "Sí a todo", "No to All": "No a todo", "Abort": "Anular", "Retry": "Reintentar", "Ignore": "Ignorar",
}


class BotonesEspanol(QTranslator):
    def isEmpty(self):  # noqa: N802
        return False

    def translate(self, contexto, texto, desambiguacion=None, n=-1):
        if contexto == "QPlatformTheme":
            return TEXTOS.get(texto.replace("&", ""))  # (None si no está: Qt deja su texto original, nunca un botón en blanco)
        return None


def instalar():
    app = QApplication.instance()
    if app is None or app.findChild(BotonesEspanol, NOMBRE) is not None:
        return
    traductor = BotonesEspanol(app)
    traductor.setObjectName(NOMBRE)
    app.installTranslator(traductor)
