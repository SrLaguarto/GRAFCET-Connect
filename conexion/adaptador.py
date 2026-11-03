"""Traducción de E/S. La sesión solo se toca desde su hilo propietario."""
from fractions import Fraction

from grafcet.values import check_fits, in_domain


class MonitorEntradas:
    """Lectura externa sin motor compilado; no puede escribir actuadores."""
    def __init__(self, config, documento):
        config.validar(documento)
        roles = {v["id"]: v["role"] for v in documento["variables"]}
        self.config = config
        self.sesion = None
        self.entradas = [s for s in config.senales if roles[s.variable] == "input"]
        self.salidas = []
        self.salidas_control = [s for s in config.senales if roles[s.variable] == "output"]

    @classmethod
    def desde_adaptador(cls, adaptador):
        monitor = object.__new__(cls)
        monitor.config = adaptador.config
        monitor.sesion = None
        monitor.entradas = list(adaptador.entradas)
        monitor.salidas = []
        monitor.salidas_control = list(adaptador.salidas or getattr(adaptador, "salidas_control", []))
        return monitor

    def valores_salida(self, cero=False):
        """Un monitor no controla nada: solo conoce el cero de las salidas asignadas (el que piden Pausa y Conectar)."""
        return valores_cero(self.salidas_control) if cero else {}


class Adaptador:
    def __init__(self, config, sesion):
        self.config, self.sesion = config, sesion
        self.entradas = [s for s in config.senales if sesion.cm.variables[s.variable].role == "input"]
        self.salidas = [s for s in config.senales if sesion.cm.variables[s.variable].role == "output"]

    def aplicar(self, muestra: dict):
        s = self.sesion
        if s.status != "pausada-estable":
            raise RuntimeError("El motor no está estable")
        if set(muestra) != {x.variable for x in self.entradas}:
            raise ValueError("Muestra de entradas incompleta")
        cambios = {}
        for senal in self.entradas:
            raw = muestra[senal.variable]
            v = s.cm.variables[senal.variable]
            if senal.formato == "BOOL":
                valor = check_fits(v.type, raw)
            else:
                if type(raw) is not int or not 0 <= raw <= 65535:
                    raise ValueError("Registro de entrada inválido")
                numero = raw - 65536 if senal.formato == "INT16" and raw >= 32768 else raw
                valor = check_fits(v.type, Fraction(numero) / Fraction(senal.escala))
            if not in_domain(v.type, v.domain, valor):
                raise ValueError(f"Entrada {v.name} fuera de dominio")
            if s.z.values[senal.variable] != valor:
                cambios[senal.variable] = valor
        if cambios:
            s.manual_input(cambios)
            s.step_external()

    def valores_salida(self, cero=False) -> dict:
        s = self.sesion
        resultado = {}
        for senal in self.salidas:
            vid = senal.variable
            valor = s.z.outputs[vid] if vid in s.cm.continuous_by_target else s.z.values[vid]
            if senal.formato == "BOOL":
                if type(valor) is not bool:
                    raise ValueError("Salida digital no booleana")
                resultado[vid] = False if cero else valor
            else:
                numero = Fraction(0 if cero else valor) * Fraction(senal.escala)
                minimo, maximo = (-32768, 32767) if senal.formato == "INT16" else (0, 65535)
                if numero.denominator != 1 or not minimo <= numero <= maximo:
                    raise ValueError(f"Salida {vid} no representable como {senal.formato}")
                resultado[vid] = int(numero) & 0xffff
        return resultado


def salidas_asignadas(adaptador):
    """Las salidas del mapa (coils y holding), haya programa en marcha o solo observación: el monitor no las controla, pero
    sabe cuáles son."""
    return list(adaptador.salidas or getattr(adaptador, "salidas_control", []))


def valores_cero(senales):
    """El cero de cada señal: False en las digitales y 0 en los registros."""
    return {s.variable: False if s.formato == "BOOL" else 0 for s in senales}


def _bloques(senales, bits, registros):
    """Solo direcciones contiguas de la misma área: nunca escribir huecos no asignados."""
    grupo = []
    for senal in sorted(senales, key=lambda s: (s.area, s.direccion)):
        limite = bits if senal.formato == "BOOL" else registros
        if grupo and (senal.area != grupo[-1].area or senal.direccion != grupo[-1].direccion + 1
                      or len(grupo) >= limite):
            yield grupo
            grupo = []
        grupo.append(senal)
    if grupo:
        yield grupo


def leer_entradas(cliente, senales):
    """Muestra completa; cada bloque contiguo se lee en una única petición."""
    muestra = {}
    for grupo in _bloques(senales, 2000, 125):
        s = grupo[0]
        valores = (cliente.leer_bits(s.direccion, len(grupo), entradas=s.area == "discrete")
                   if s.formato == "BOOL" else
                   cliente.leer_registros(s.direccion, len(grupo), entradas=s.area == "input-register"))
        if len(valores) != len(grupo):
            raise ValueError("Muestra Modbus incompleta")
        muestra.update((senal.variable, valor) for senal, valor in zip(grupo, valores))
    return muestra


def escribir_salidas(cliente, senales, valores):
    """Publica juntas las salidas contiguas, evitando estados parciales entre actuadores."""
    for grupo in _bloques(senales, 1968, 123):
        s = grupo[0]
        lote = [valores[senal.variable] for senal in grupo]
        if s.formato == "BOOL":
            cliente.escribir_coils(s.direccion, lote)
        else:
            cliente.escribir_registros(s.direccion, lote)
