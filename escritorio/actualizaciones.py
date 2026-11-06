"""Aviso de versión nueva (nivel 1): consulta la última publicación de GitHub, sin instalar nada.

La consulta va en un hilo aparte (nunca bloquea la interfaz), con 5 s de espera y sin reintentos. Solo se envía la petición HTTP
con el agente «GRAFCET-Connect/<versión>»: ningún dato personal ni del proyecto. Si falla por cualquier motivo (sin Internet,
proxy, límite de peticiones, JSON roto), en el arranque no se hace nada; la comprobación manual sí informa.

Ajustes (QSettings): `actualizaciones/al_arrancar` (bool, por defecto sí) y `actualizaciones/ignorada` (la última versión que
el usuario descartó con «Ahora no»; en el arranque no se vuelve a avisar de ella).

El acceso a la red es inyectable (`obtener(url, agente, espera) -> str`) para que las pruebas no toquen Internet. El arranque
no consulta si la variable de entorno GRAFCONNECT_SIN_ACTUALIZAR tiene algún valor, ni con --captura ni con las opciones
--prueba-*; esa decisión se toma en `escritorio.ventana.main`.
"""
from __future__ import annotations

import json
import re
import threading
from typing import Any, Callable, NamedTuple
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QSettings, Signal

from . import VERSION

URL_ULTIMA = "https://api.github.com/repos/SrLaguarto/GRAFCET-Connect/releases/latest"
ESPERA_S = 5
CLAVE_AL_ARRANCAR = "actualizaciones/al_arrancar"
CLAVE_IGNORADA = "actualizaciones/ignorada"
VARIABLE_SIN_ACTUALIZAR = "GRAFCONNECT_SIN_ACTUALIZAR"


class Resultado(NamedTuple):
    estado: str  # "nueva" | "al_dia" | "fallo"
    version: str = ""
    url: str = ""


PREFIJO_URL = "https://github.com/SrLaguarto/GRAFCET-Connect/"
URL_PUBLICACIONES = PREFIJO_URL + "releases/latest"


def url_segura(url: Any) -> str:
    """La URL de la publicación solo se abre si es del repositorio del proyecto (https://github.com/SrLaguarto/GRAFCET-Connect/);
    cualquier otra (o vacía) se cambia por la página de la última publicación."""
    return url if isinstance(url, str) and url.startswith(PREFIJO_URL) else URL_PUBLICACIONES


def numeros_version(texto: Any) -> tuple[int, ...] | None:
    """«v1.0.2» -> (1, 0, 2). None si no es una versión numérica con puntos."""
    if not isinstance(texto, str):
        return None
    texto = texto.strip()
    if texto[:1] in ("v", "V"):
        texto = texto[1:]
    if not re.fullmatch(r"\d+(\.\d+)*", texto):
        return None
    return tuple(int(p) for p in texto.split("."))


def es_mas_nueva(candidata: Any, actual: str = VERSION) -> bool:
    """Compara como tuplas numéricas, rellenando con ceros (1.0 == 1.0.0)."""
    a, b = numeros_version(candidata), numeros_version(actual)
    if a is None or b is None:
        return False
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def interpretar(texto: Any, actual: str = VERSION) -> Resultado:
    """Convierte la respuesta JSON de GitHub en un resultado; cualquier defecto es «fallo»."""
    try:
        datos = json.loads(texto)
        etiqueta, url = datos["tag_name"], datos.get("html_url", "")
        if numeros_version(etiqueta) is None or not isinstance(url, str):
            return Resultado("fallo")
    except (ValueError, TypeError, KeyError, AttributeError):
        return Resultado("fallo")
    version = etiqueta.strip().lstrip("vV")
    return Resultado("nueva" if es_mas_nueva(etiqueta, actual) else "al_dia", version, url)


def obtener_http(url: str, agente: str, espera: float) -> str:
    peticion = Request(url, headers={"User-Agent": agente, "Accept": "application/vnd.github+json"})
    with urlopen(peticion, timeout=espera) as respuesta:  # noqa: S310 (URL fija, https)
        return respuesta.read().decode("utf-8")


def consultar(obtener: Callable[[str, str, float], str] | None = None, actual: str = VERSION) -> Resultado:
    """Una consulta síncrona (se ejecuta en el hilo): nunca lanza."""
    try:
        return interpretar((obtener or obtener_http)(URL_ULTIMA, f"GRAFCET-Connect/{actual}", ESPERA_S), actual)
    except Exception:  # sin red, proxy, límite de peticiones, certificado… todo cuenta como «no se pudo»
        return Resultado("fallo")


def al_arrancar_activo(ajustes: QSettings) -> bool:
    return ajustes.value(CLAVE_AL_ARRANCAR, True, type=bool)


def ignorada(ajustes: QSettings) -> str:
    return str(ajustes.value(CLAVE_IGNORADA, "") or "")


def ignorar(ajustes: QSettings, version: str) -> None:
    ajustes.setValue(CLAVE_IGNORADA, version)
    ajustes.sync()


class Comprobador(QObject):
    """Lanza la consulta en un hilo y entrega `resultado(manual, Resultado)` en el hilo de la interfaz."""
    resultado = Signal(bool, object)

    def __init__(self, parent: QObject | None = None, obtener: Callable[[str, str, float], str] | None = None,
                 sincrono: bool = False) -> None:
        super().__init__(parent)
        self.obtener = obtener
        self.sincrono = sincrono  # las pruebas lo piden para no esperar al hilo
        self.hilo: threading.Thread | None = None
        self._cerrojo = threading.Lock()
        self._en_marcha = False
        self._manual_pendiente = False  # una comprobación manual pedida con otra en marcha: su resultado se enseña con mensaje

    def comprobar(self, manual: bool = False) -> None:
        if self.sincrono:
            self.resultado.emit(manual, consultar(self.obtener))
            return
        with self._cerrojo:
            if self._en_marcha:
                self._manual_pendiente = self._manual_pendiente or manual  # no se lanza otra: la que corre contesta por las dos
                return
            self._en_marcha, self._manual_pendiente = True, False

        def trabajo() -> None:
            r = consultar(self.obtener)
            with self._cerrojo:
                como_manual, self._manual_pendiente, self._en_marcha = manual or self._manual_pendiente, False, False
            try:
                self.resultado.emit(como_manual, r)
            except RuntimeError:
                pass  # la ventana ya no existe

        self.hilo = threading.Thread(target=trabajo, name="comprobar-actualizaciones", daemon=True)
        self.hilo.start()
