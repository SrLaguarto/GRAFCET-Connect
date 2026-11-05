"""Traducción de E/S. La sesión solo se toca desde su hilo propietario."""
from decimal import Decimal
from fractions import Fraction

from grafcet.diagnostics import DiagnosticError
from grafcet.values import check_fits, in_domain


class ErrorConversion(ValueError):
    """Un valor leído o por escribir que no cabe en su variable o en su registro. El texto ya está escrito para el
    usuario (nombra la variable y el valor, sin códigos): se enseña tal cual."""


def texto_numero(valor) -> str:
    """Un número con coma decimal española y sin ceros de más: 1,3; 2,345; 40."""
    f = Fraction(valor)
    if f.denominator == 1:
        return str(f.numerator)
    texto = format(Decimal(f.numerator) / Decimal(f.denominator), "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _tipo_legible(tipo) -> str:
    if tipo.kind == "int":
        return "Entera"
    if tipo.kind == "decimal":
        return f"Decimal ({tipo.scale} decimales)"
    return "de otro tipo"


def _decimales_de_escala(escala):
    """Los decimales que admite un registro con esa escala (100 → 2); None si no es una potencia de 10."""
    texto = str(escala)
    return len(texto) - 1 if texto.isdigit() and texto[0] == "1" and set(texto[1:]) <= {"0"} else None


def _entrada_no_cabe(variable, numero) -> ErrorConversion:
    """El texto cuando un valor que manda la planta no es representable en el tipo de la variable de entrada."""
    cabecera = (f"La entrada «{variable.name}» es {_tipo_legible(variable.type)}, "
                f"pero el simulador de procesos ha enviado {texto_numero(numero)}.")
    if variable.type.kind == "int" and Fraction(numero).denominator != 1:
        return ErrorConversion(cabecera + " Cámbiela a Decimal (2 decimales) en Variables.")
    if variable.type.kind == "decimal":
        return ErrorConversion(cabecera + " Aumente los decimales de la variable en Variables.")
    return ErrorConversion(cabecera + " Ese valor no cabe en la variable.")


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
            raise ErrorConversion("El simulador de procesos no ha enviado todas las entradas asignadas")
        cambios = {}
        for senal in self.entradas:
            raw = muestra[senal.variable]
            v = s.cm.variables[senal.variable]
            if senal.formato == "BOOL":
                valor = check_fits(v.type, raw)
            else:
                valor = self._registro_a_valor(senal, v, raw)
            if not in_domain(v.type, v.domain, valor):
                raise ErrorConversion(f"La entrada «{v.name}» ha recibido {texto_numero(valor)}, que está fuera de los "
                                      "valores que permite su dominio.")
            if s.z.values[senal.variable] != valor:
                cambios[senal.variable] = valor
        if cambios:
            s.manual_input(cambios)
            s.step_external()

    @staticmethod
    def _registro_a_valor(senal, v, raw):
        """El valor del motor que representa un registro leído (con signo si es INT16, dividido por la escala)."""
        if type(raw) is not int or not 0 <= raw <= 65535:
            raise ErrorConversion(f"El simulador de procesos ha enviado un registro no válido para la entrada «{v.name}»")
        numero = raw - 65536 if senal.formato == "INT16" and raw >= 32768 else raw
        leido = Fraction(numero) / Fraction(senal.escala)
        try:
            return check_fits(v.type, leido)
        except DiagnosticError:
            raise _entrada_no_cabe(v, leido) from None

    @staticmethod
    def _valor_a_registro(senal, nombre, valor):
        """El registro (16 bits) que lleva una salida del motor; si no cabe, un error que dice por qué."""
        escala = Fraction(senal.escala)
        numero = Fraction(valor) * escala
        if numero.denominator != 1:
            decimales = _decimales_de_escala(escala)
            motivo = (f"el registro del simulador de procesos solo admite {decimales} decimales" if decimales is not None else
                      f"no se puede escribir en el registro con la escala {texto_numero(escala)}")
            raise ErrorConversion(f"La salida «{nombre}» vale {texto_numero(valor)} y {motivo}. "
                                  "Reduzca los decimales de la variable en Variables.")
        minimo, maximo = (-32768, 32767) if senal.formato == "INT16" else (0, 65535)
        if not minimo <= numero <= maximo:
            raise ErrorConversion(f"La salida «{nombre}» vale {texto_numero(valor)} y se sale del rango del registro "
                                  f"(de {texto_numero(minimo / escala)} a {texto_numero(maximo / escala)}).")
        return int(numero) & 0xffff

    def valores_salida(self, cero=False) -> dict:
        s = self.sesion
        resultado = {}
        for senal in self.salidas:
            vid = senal.variable
            valor = s.z.outputs[vid] if vid in s.cm.continuous_by_target else s.z.values[vid]
            if senal.formato == "BOOL":
                if type(valor) is not bool:
                    nombre = s.cm.variables[vid].name
                    raise ErrorConversion(f"La salida «{nombre}» debería ser verdadera o falsa, pero vale {texto_numero(valor)}")
                resultado[vid] = False if cero else valor
            else:
                resultado[vid] = self._valor_a_registro(senal, s.cm.variables[vid].name, 0 if cero else valor)
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
