"""Valores reales de la API, con la conversión del motor y sin registros PLC."""
from fractions import Fraction

from .adaptador import Adaptador, ErrorConversion, MonitorEntradas, redondear_escolar, valores_cero
from grafcet.diagnostics import DiagnosticError
from grafcet.values import check_fits


def documento_sesion(config, sesion):
    return {"id": config.modelo, "variables": [
        {"id": vid, "name": v.name, "role": v.role, "type": {"kind": v.type.kind}}
        for vid, v in sesion.cm.variables.items()]}


def activas(config, documento, papel):
    variables = {v["id"]: v for v in documento["variables"]}
    return [u for u in config.uniones if not u.motivo and u.papel == papel and u.compatible(variables.get(u.variable))]


class MonitorDirecto(MonitorEntradas):
    def __init__(self, config, documento):
        config.validar(documento)
        self.config = config
        self.sesion = None
        self.documento = documento
        self.entradas = activas(config, documento, "input")
        self.salidas = []
        self.salidas_control = activas(config, documento, "output")
        self.redondeos = {}


class AdaptadorDirecto(Adaptador):
    def __init__(self, config, sesion):
        self.config = config
        self.sesion = sesion
        self.documento = documento_sesion(config, sesion)
        config.validar(self.documento)
        self.entradas = activas(config, self.documento, "input")
        self.salidas = activas(config, self.documento, "output")
        self.redondeos = {}

    def aplicar(self, muestra):
        self.entradas[:] = [u for u in self.entradas if not u.motivo]  # (una señal perdida con la conexión en marcha ya no llega)
        super().aplicar(muestra)

    @staticmethod
    def _registro_a_valor(senal, variable, raw):
        if type(raw) not in (int, float):
            raise ErrorConversion(f"El simulador de fábricas ha enviado un número inválido para «{variable.name}»")
        try:
            valor = Fraction(str(raw))
            usado = redondear_escolar(valor) if variable.type.kind == "int" else valor
            return check_fits(variable.type, usado)
        except (ValueError, OverflowError, DiagnosticError) as exc:
            mensaje = f"El valor {raw} no cabe en «{variable.name}». Revise sus decimales y dominio."
            raise ErrorConversion(mensaje) from exc

    def _anotar_redondeo(self, senal, variable, raw, valor):
        if variable.type.kind == "int" and Fraction(str(raw)) != valor:
            self.redondeos[senal.variable] = (Fraction(str(raw)), valor)

    def valores_salida(self, cero=False):
        if cero:
            return valores_cero(self.salidas)
        resultado = {}
        for union in self.salidas:
            vid = union.variable
            variable = self.sesion.cm.variables[vid]
            valor = (self.sesion.z.outputs[vid] if vid in self.sesion.cm.continuous_by_target
                     else self.sesion.z.values[vid])
            if union.tipo.lower() == "bit":
                if type(valor) is not bool:
                    raise ErrorConversion(f"«{variable.name}» requiere un valor booleano")
                resultado[vid] = valor
            elif union.tipo.lower() == "int":
                resultado[vid] = redondear_escolar(valor)
            else:
                resultado[vid] = float(valor)
        return resultado
