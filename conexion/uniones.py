"""Identidad y compatibilidad de las uniones con el simulador de fábricas."""
from dataclasses import dataclass


TIPOS = {"bit": "bool", "int": "int", "float": "decimal"}
PAPELES = {"input": "input", "output": "output"}


@dataclass
class Union:
    variable: str
    id: str
    nombre: str
    tipo: str
    papel: str
    motivo: str = ""

    def compatible(self, variable):
        return (variable is not None and variable["role"] == self.papel
                and variable["type"]["kind"] == TIPOS.get(self.tipo.lower()))

    @property
    def area(self):
        return "directo"

    @property
    def direccion(self):
        return self.id

    @property
    def formato(self):
        return "BOOL" if self.tipo.lower() == "bit" else "REAL"

    @property
    def escala(self):
        return "1"
