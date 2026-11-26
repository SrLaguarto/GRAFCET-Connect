"""API HTTP del servidor elegido, sin proxies ni redirecciones."""
import http.client
import json


class ErrorDirecto(ValueError):
    pass


AVISO_SIN_SERVIDOR = "El simulador de fábricas no responde"


def sin_servidor(host, puerto):
    return (AVISO_SIN_SERVIDOR + f" ({host}:{puerto}): activa su servidor web (app.web_server = True en su auto.cfg) "
            "y abre el simulador con el controlador en «Ninguno».")  # (una línea: los avisos de dos líneas se hacían muy largos)


class ClienteDirecto:
    def __init__(self, host="localhost", puerto=7410, unidad=1, timeout=0.5):
        self.host = host
        self.puerto = puerto
        self.unidad = unidad
        self.timeout = timeout
        self.conexion = None
        self.peticiones = 0
        self.avisos = []

    def conectar(self):
        self.conexion = http.client.HTTPConnection(self.host, self.puerto, timeout=self.timeout)

    def cerrar(self):
        if self.conexion is not None:
            self.conexion.close()
            self.conexion = None

    def pedir(self, metodo, ruta, datos=None):
        if self.conexion is None:
            self.conectar()
        cuerpo = None if datos is None else json.dumps(datos, allow_nan=False).encode("utf-8")
        try:
            self.peticiones += 1
            self.conexion.request(metodo, ruta, cuerpo, {"Content-Type": "application/json"})
            respuesta = self.conexion.getresponse()
            contenido = respuesta.read(4 * 1024 * 1024 + 1)
            if not 200 <= respuesta.status < 300:
                raise ErrorDirecto(f"HTTP {respuesta.status}: {respuesta.reason}")
        except (OSError, http.client.HTTPException) as exc:
            self.cerrar()
            raise ErrorDirecto(sin_servidor(self.host, self.puerto)) from exc
        try:
            if len(contenido) > 4 * 1024 * 1024:
                raise ValueError("Respuesta demasiado grande")
            return json.loads(contenido)
        except (ValueError, UnicodeError) as exc:
            raise ErrorDirecto("El servidor no parece el del simulador: respuesta que no es JSON válido") from exc

    def catalogo(self):
        datos = self.pedir("GET", "/api/tags")
        if not isinstance(datos, list):
            raise ErrorDirecto("El servidor no parece el del simulador: falta la lista de señales")
        ids = set()
        for senal in datos:
            if not isinstance(senal, dict) or not all(isinstance(senal.get(k), str)
                                                     for k in ("id", "name", "type", "kind")):
                raise ErrorDirecto("Catálogo de señales inválido")
            if (not senal["id"] or senal["id"] in ids or senal["type"].lower() not in ("bit", "int", "float")
                    or senal["kind"].lower() not in ("input", "output")):
                raise ErrorDirecto("Identidad, tipo o papel de señal inválido")
            ids.add(senal["id"])
        from .catalogo_directo import interna, nombre_visible
        for senal in datos:
            senal["_nombre_original"] = senal["name"]
            senal["_sistema"] = interna(senal)
            senal["name"] = nombre_visible(senal)
        return datos
