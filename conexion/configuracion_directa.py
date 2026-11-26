"""Validación del destino HTTP y de las identidades guardadas."""
import ipaddress
import re


def validar(config, doc):
    from .filtro_directo import validar as validar_filtro
    validar_filtro(config)
    host = config.host
    if not isinstance(host, str) or not host or host != host.strip():
        raise ValueError("Falta el servidor del simulador de fábricas")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        patron = r"(?=.{1,253}\Z)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?"
        if not re.fullmatch(patron, host) or ".." in host:
            raise ValueError("Servidor inválido: escribe un nombre o una dirección IP, sin ruta ni protocolo")
    for valor, minimo, maximo in ((config.puerto, 1, 65535), (config.periodo_ms, 5, 10000),
                                 (config.timeout_ms, 10, 10000)):
        if type(valor) is not int or not minimo <= valor <= maximo:
            raise ValueError("Puerto, periodo o tiempo de espera fuera de rango")
    if config.modelo and config.modelo != doc["id"]:
        raise ValueError("El mapa pertenece a otro modelo")
    variables, senales = set(), set()
    for union in config.uniones:
        if not all(isinstance(x, str) and x for x in (union.variable, union.id, union.nombre)):
            raise ValueError("Unión sin identidad o nombre")
        if union.tipo.lower() not in ("bit", "int", "float") or union.papel not in ("input", "output"):
            raise ValueError("Tipo o papel de señal desconocido")
        if union.variable in variables or union.id in senales:
            raise ValueError("Variable o señal repetida en las uniones")
        variables.add(union.variable)
        senales.add(union.id)
