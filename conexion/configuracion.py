"""Mapa externo al documento GRAFCET; direcciones Modbus basadas en cero."""
from dataclasses import asdict, dataclass, field
from fractions import Fraction
import json
import os
import re
from pathlib import Path
import tempfile

ARCHIVO = "conexion-factoryio.json"
CONEXION_INICIAL = ("192.168.1.133", 502, 1)
CANALES_INICIALES = {a: {"offset": 0, "cantidad": 32 if a in ("discrete", "coil") else 12}
                     for a in ("discrete", "coil", "input-register", "holding")}
ETIQUETA_CANAL = {"discrete": "Entrada", "input-register": "Entrada numérica", "coil": "Salida", "holding": "Salida numérica"}
_IPV4 = re.compile(r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}")


def es_ipv4(texto) -> bool:
    """Cuatro números de 0 a 255 separados por puntos (sin ceros a la izquierda)."""
    return isinstance(texto, str) and _IPV4.fullmatch(texto) is not None


def normalizar_host(texto) -> str:
    """Un host guardado que no es IPv4: «localhost» pasa a 127.0.0.1 y cualquier otra cosa, a la dirección inicial."""
    if isinstance(texto, str):
        texto = texto.strip()
        if es_ipv4(texto):
            return texto
        partes = texto.split(".")
        if len(partes) == 4 and all(x.isdigit() and len(x) <= 3 for x in partes):
            sin_ceros = ".".join(str(int(x)) for x in partes)
            if es_ipv4(sin_ceros):
                return sin_ceros
        if texto.lower() == "localhost":
            return "127.0.0.1"
    return CONEXION_INICIAL[0]


def aviso_host(texto) -> str:
    """El aviso para un host guardado que no es IPv4 ni «localhost» (un nombre DNS, una IPv6…), que `normalizar_host` cambia
    por la dirección inicial: no se hace en silencio. Vacío si el host sirve (o no hay)."""
    if not isinstance(texto, str) or not (texto := texto.strip()) or es_ipv4(texto) or texto.lower() == "localhost" \
            or es_ipv4(normalizar_host(texto)) and normalizar_host(texto) != CONEXION_INICIAL[0]:
        return ""
    return f"La dirección guardada ({texto}) no es una IP. Escriba la IP del servidor."


@dataclass
class Senal:
    variable: str
    area: str  # discrete, coil, input-register, holding
    direccion: int
    formato: str = "BOOL"  # BOOL, INT16, UINT16
    escala: str | None = None  # valor del motor = valor de registro / escala

    def __post_init__(self):
        if self.escala is None:
            self.escala = "1" if self.formato == "BOOL" else "100"


@dataclass
class Configuracion:
    host: str = CONEXION_INICIAL[0]
    puerto: int = 502
    unidad: int = 1
    periodo_ms: int = 20
    timeout_ms: int = 500
    modelo: str = ""
    senales: list[Senal] = field(default_factory=list)
    canales: dict[str, dict[str, int]] = field(default_factory=dict)

    def fijar_escalas_simulador(self):
        for s in self.senales:
            s.escala = "1" if s.formato == "BOOL" else "100"

    def validar(self, doc: dict):
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("Falta la dirección del servidor")
        if not es_ipv4(self.host.strip()):
            raise ValueError("La dirección del servidor debe ser una IP de cuatro números entre 0 y 255 (por ejemplo, 192.168.1.133)")
        for valor, minimo, maximo in ((self.puerto, 1, 65535), (self.unidad, 0, 255),
                                      (self.periodo_ms, 5, 10000), (self.timeout_ms, 10, 10000)):
            if type(valor) is not int or not minimo <= valor <= maximo:
                raise ValueError("Puerto, unidad, periodo o timeout fuera de rango")
        if self.modelo and self.modelo != doc["id"]:
            raise ValueError("El mapa pertenece a otro modelo")
        if not isinstance(self.canales, dict):
            raise ValueError("Configuración de canales inválida")
        for area, rango in self.canales.items():
            if area not in ("discrete", "coil", "input-register", "holding") or not isinstance(rango, dict):
                raise ValueError("Área de canales inválida")
            inicio, cantidad = rango.get("offset"), rango.get("cantidad")
            limite = 256 if area in ("discrete", "coil") else 64
            if type(inicio) is not int or type(cantidad) is not int or not 0 <= inicio <= 65535 or not 0 <= cantidad <= limite or inicio + cantidad > 65536:
                raise ValueError(f"Offset o cantidad fuera de rango en {area}")
        variables = {v["id"]: v for v in doc["variables"]}
        ids, destinos = set(), set()
        for s in self.senales:
            v = variables.get(s.variable)
            if v is None or v["role"] not in ("input", "output") or s.variable in ids:
                raise ValueError("Variable inexistente, repetida o sin papel de E/S")
            ids.add(s.variable)
            if type(s.direccion) is not int or not 0 <= s.direccion <= 65535:
                raise ValueError("Dirección Modbus fuera de rango")
            if s.area in self.canales:
                rango = self.canales[s.area]
                if not rango["offset"] <= s.direccion < rango["offset"] + rango["cantidad"]:
                    raise ValueError(f"{v['name']} queda fuera de los canales configurados; quita o mueve su asignación antes de reducirlos")
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

    def quitar_obsoletas(self, doc: dict) -> list[str]:
        """Quita del mapa las asignaciones que ya no casan con el modelo: la variable ya no existe o no es de entrada/salida,
        o su papel o su tipo ya no encajan con el área. Devuelve un texto por cada una quitada. Lo que es defecto del propio
        mapa (área o formato desconocidos, formato que no casa con el área, direcciones o variables repetidas…) no se toca:
        eso lo rechaza `validar`. De una variable que ya no existe solo queda su ID, que no se enseña: el aviso la nombra por su
        canal."""
        variables = {v["id"]: v for v in doc["variables"]}
        validas, quitadas = [], []
        for s in self.senales:
            v = variables.get(s.variable)
            canal = f"{ETIQUETA_CANAL.get(s.area, s.area)} {s.direccion}"
            if v is None:
                quitadas.append(f"la variable de {canal} ya no existe")
            elif v["role"] not in ("input", "output"):
                quitadas.append(f"«{v['name']}» ya no es de entrada ni de salida")
            elif self._no_encaja(s, v):
                quitadas.append(f"«{v['name']}» ya no encaja en {canal}")
            else:
                validas.append(s)
        self.senales = validas
        return quitadas

    @staticmethod
    def _no_encaja(s: Senal, v: dict) -> bool:
        if s.area not in ETIQUETA_CANAL or s.formato not in ("BOOL", "INT16", "UINT16"):
            return False
        if s.area not in (("discrete", "coil", "input-register", "holding") if v["role"] == "input" else ("coil", "holding")):
            return True
        digital = s.formato == "BOOL"
        if digital != (s.area in ("discrete", "coil")):
            return False
        return v["type"]["kind"] != "bool" if digital else v["type"]["kind"] not in ("int", "decimal")

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
    def cargar(cls, ruta: Path, doc: dict, avisos: list[str] | None = None):
        """Lee el mapa guardado. Las asignaciones de variables que ya no existen (o cuyo papel o tipo ya no encajan) se
        descartan y, si se pasa `avisos`, se añade a la lista un texto por cada una; el resto del mapa se conserva. Un JSON
        corrupto o de formato inválido se rechaza con ValueError."""
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if datos.pop("version") != 1:
                raise ValueError("Versión de conexión desconocida")
            datos.pop("modo", None)  # restos del modo servidor, ya retirado
            datos.pop("escucha", None)
            datos["senales"] = [Senal(**s) for s in datos["senales"]]
            config = cls(**datos)
            aviso = aviso_host(config.host)
            config.host = normalizar_host(config.host)  # un mapa antiguo con «localhost» u otro nombre sigue cargando
            config.aviso_host = aviso  # (no es un campo: no se guarda; el panel lo enseña hasta que se escriba otra IP)
            quitadas = config.quitar_obsoletas(doc)
            config.validar(doc)
            if avisos is not None:
                avisos.extend(quitadas)
            return config
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("Configuración de conexión inválida") from exc
