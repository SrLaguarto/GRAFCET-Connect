"""Lectura y escritura por lotes, con un catálogo validado al conectar."""
import time

from .adaptador_directo import activas, documento_sesion
from .http_directo import ClienteDirecto, ErrorDirecto
from .reconciliar import reconciliar

REFRESCO_S = 1.0  # sin cambios, las salidas se reenvían igualmente cada segundo: si el simulador las pone a 0 por su
#                   cuenta (al reiniciar la escena), vuelven a su valor sin esperar a que cambien en el GRAFCET


class TransporteDirecto(ClienteDirecto):
    def __init__(self, config):
        super().__init__(config.host, config.puerto, config.unidad, config.timeout_ms / 1000)
        self.config = config
        self.ultimos = {}
        self.ultimo_envio = None
        self.senales = {}

    def preparar(self, adaptador, documento=None):
        if documento is None:
            documento = documento_sesion(adaptador.config, adaptador.sesion)
        self.config = adaptador.config
        catalogo = self.catalogo()
        self.senales = {s["id"]: s for s in catalogo}
        self.avisos.extend(reconciliar(adaptador.config, documento, catalogo))
        adaptador.entradas[:] = activas(adaptador.config, documento, "input")
        salidas = activas(adaptador.config, documento, "output")
        if adaptador.sesion is None:
            adaptador.salidas_control[:] = salidas
        else:
            adaptador.salidas[:] = salidas

    def permitida(self, union, papel):
        senal = self.senales.get(union.id)
        return (not union.motivo and senal is not None and union.papel == papel
                and senal["kind"].lower() == papel and senal["type"].lower() == union.tipo.lower())

    def perder(self, union):
        """Una señal unida ya no está en el simulador: su unión queda marcada y la conexión sigue con las demás."""
        self.senales.pop(union.id, None)
        if union.motivo != "señal no encontrada":
            union.motivo = "señal no encontrada"
            self.avisos.append(f"«{union.nombre}»: {union.motivo}")

    def leer(self, uniones):
        validas = [u for u in uniones if self.permitida(u, "input")]
        if not validas:
            return {}
        datos = self.pedir("GET", "/api/tag/values", [u.id for u in validas])
        if not isinstance(datos, list):
            raise ErrorDirecto("El servidor no parece el del simulador: valores inválidos")
        valores = {}
        vistos = set()
        for dato in datos:
            if not isinstance(dato, dict) or "id" not in dato:
                raise ErrorDirecto("Respuesta de valores inválida")
            if dato["id"] in vistos:
                raise ErrorDirecto("Señal repetida en la respuesta de valores")
            vistos.add(dato["id"])
            if dato.get("error") or dato.get("code", 200) >= 400:
                if dato["id"] not in {u.id for u in validas}:
                    raise ErrorDirecto(f"HTTP {dato.get('code', '?')}: no se pudo leer una señal")
                continue  # error de esa señal: se marca más abajo, como una ausente
            valores[dato["id"]] = dato.get("value")
        if not vistos <= {u.id for u in validas}:
            raise ErrorDirecto("El simulador de fábricas no ha enviado todas las entradas unidas")
        for union in validas:
            if union.id not in valores:  # con error o ausente de la respuesta
                self.perder(union)
        return {u.variable: valores[u.id] for u in validas if u.id in valores}

    def escribir(self, uniones, valores, forzar=False):
        validas = [u for u in uniones if u.variable in valores and self.permitida(u, "output")]
        ahora = time.monotonic()
        forzar = forzar or self.ultimo_envio is None or ahora - self.ultimo_envio >= REFRESCO_S
        cambios = [u for u in validas if forzar or self.ultimos.get(u.id) != valores[u.variable]]
        if not cambios:
            return {u.variable: valores[u.variable] for u in validas}
        cuerpo = [{"id": u.id, "value": valores[u.variable]} for u in cambios]
        try:
            datos = self.pedir("PUT", "/api/tag/values", cuerpo)
        except ErrorDirecto as exc:
            if "HTTP 406:" not in str(exc):
                raise
            self.avisos.append("HTTP 406: unión mal hecha; una entrada no puede usarse como salida")
            return {}
        if not isinstance(datos, list):
            raise ErrorDirecto("Respuesta de escritura inválida")
        self.ultimo_envio = ahora
        errores = {d.get("id"): d for d in datos if d.get("error") or d.get("code", 200) >= 400}
        for union in cambios:
            if union.id in errores:
                dato = errores[union.id]
                codigo = dato.get("code", "?")
                if codigo != 406:
                    self.perder(union)
                    continue
                union.motivo = "HTTP 406: unión mal hecha; una entrada no puede usarse como salida"
                self.avisos.append(f"«{union.nombre}»: {union.motivo}")
            else:
                self.ultimos[union.id] = valores[union.variable]
        return {u.variable: valores[u.variable] for u in validas if u.id not in errores}
