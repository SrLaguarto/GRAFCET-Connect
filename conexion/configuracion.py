"""Mapa externo al documento GRAFCET; direcciones Modbus basadas en cero."""
from dataclasses import asdict, dataclass, field
from fractions import Fraction
import json
import os
from pathlib import Path
import tempfile

ARCHIVO = "conexion-factoryio.json"


@dataclass
class Senal:
    variable: str
    area: str  # discrete, coil, input-register, holding
    direccion: int
    formato: str = "BOOL"  # BOOL, INT16, UINT16
    escala: str = "1"  # valor del motor = valor de registro / escala


@dataclass
class Configuracion:
    host: str = "127.0.0.1"
    puerto: int = 502
    unidad: int = 1
    periodo_ms: int = 50
    timeout_ms: int = 500
    modelo: str = ""
    senales: list[Senal] = field(default_factory=list)

    def validar(self, doc: dict):
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("Falta la dirección del servidor")
        for valor, minimo, maximo in ((self.puerto, 1, 65535), (self.unidad, 0, 255),
                                      (self.periodo_ms, 20, 10000), (self.timeout_ms, 10, 10000)):
            if type(valor) is not int or not minimo <= valor <= maximo:
                raise ValueError("Puerto, unidad, periodo o timeout fuera de rango")
        if self.modelo and self.modelo != doc["id"]:
            raise ValueError("El mapa pertenece a otro modelo")
        variables = {v["id"]: v for v in doc["variables"]}
        ids, destinos = set(), set()
        for s in self.senales:
            v = variables.get(s.variable)
            if v is None or v["role"] not in ("input", "output") or s.variable in ids:
                raise ValueError("Variable inexistente, repetida o sin papel de E/S")
            ids.add(s.variable)
            if type(s.direccion) is not int or not 0 <= s.direccion <= 65535:
                raise ValueError("Dirección Modbus fuera de rango")
            permitidas = ("discrete", "coil", "input-register", "holding") if v["role"] == "input" else ("coil", "holding")
            if s.area not in permitidas:
                raise ValueError("Área incompatible con la dirección de la señal")
            digital = s.formato == "BOOL"
            if s.formato not in ("BOOL", "INT16", "UINT16") or digital != (s.area in ("discrete", "coil")):
                raise ValueError("Formato incompatible con el área")
            if (digital and v["type"]["kind"] != "bool") or (not digital and v["type"]["kind"] not in ("int", "decimal")):
                raise ValueError("Tipo de variable incompatible con la señal")
            try:
                escala = Fraction(s.escala)
            except (ValueError, ZeroDivisionError, TypeError):
                raise ValueError("Escala inválida") from None
            if escala <= 0 or (digital and escala != 1):
                raise ValueError("La escala debe ser positiva; BOOL requiere 1")
            destino = (s.area, s.direccion)
            if destino in destinos:
                raise ValueError("Dirección repetida en el mapa")
            destinos.add(destino)

    def guardar(self, ruta: Path, doc: dict):
        self.validar(doc)
        datos = {**asdict(self), "modelo": doc["id"], "version": 1}
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=ruta.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporal, ruta)
        finally:
            if os.path.exists(temporal):
                os.unlink(temporal)

    @classmethod
    def cargar(cls, ruta: Path, doc: dict):
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if datos.pop("version") != 1:
                raise ValueError("Versión de conexión desconocida")
            datos["senales"] = [Senal(**s) for s in datos["senales"]]
            config = cls(**datos)
            config.validar(doc)
            return config
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("Configuración de conexión inválida") from exc
