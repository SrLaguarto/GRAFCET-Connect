"""Traducción de E/S. La sesión solo se toca desde su hilo propietario."""
from fractions import Fraction

from grafcet.values import check_fits, in_domain


class MonitorEntradas:
    """Lectura externa sin motor compilado; no puede escribir actuadores."""
    def __init__(self, config, documento):
        config.validar(documento)
        roles = {v["id"]: v["role"] for v in documento["variables"]}
        if not config.senales or any(roles[s.variable] != "input" for s in config.senales):
            raise ValueError("La observación sin GRAFCET solo admite entradas")
        self.config = config
        self.sesion = None
        self.entradas = list(config.senales)
        self.salidas = []

    def valores_salida(self, cero=False):
        return {}


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


def leer_entradas(cliente, senales):
    """No publica muestras parciales si falla una de las lecturas."""
    return {s.variable: (cliente.leer_bits(s.direccion, entradas=s.area == "discrete")[0]
                         if s.formato == "BOOL" else
                         cliente.leer_registros(s.direccion, entradas=s.area == "input-register")[0])
            for s in senales}


def escribir_salidas(cliente, senales, valores):
    for s in senales:
        if s.formato == "BOOL":
            cliente.escribir_coils(s.direccion, [valores[s.variable]])
        else:
            cliente.escribir_registros(s.direccion, [valores[s.variable]])
