"""Cliente Modbus TCP síncrono. Usar desde un único trabajador, nunca desde Qt."""
from __future__ import annotations

import socket
import struct
from time import monotonic


MOTIVOS_EXCEPCION = {1: "la operación no está permitida", 2: "esa dirección no existe en el servidor (revise las direcciones y el "
                     "número de canales)", 3: "valor o cantidad no admitidos"}


class ErrorModbus(Exception):
    """Fallo de transporte, protocolo o excepción del servidor."""


class ClienteModbus:
    def __init__(self, host: str, puerto: int = 502, unidad: int = 1, timeout: float = 1.0):
        if not host or not 1 <= puerto <= 65535 or not 0 <= unidad <= 255 or timeout <= 0:
            raise ValueError("Endpoint Modbus inválido")
        self.host, self.puerto, self.unidad, self.timeout = host, puerto, unidad, timeout
        self._socket: socket.socket | None = None
        self._transaccion = 0

    def conectar(self):
        self.cerrar()
        try:
            self._socket = socket.create_connection((self.host, self.puerto), self.timeout)
        except OSError as exc:
            raise ErrorModbus(f"No se pudo conectar: {exc}") from exc

    def cerrar(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def _recibir(self, cantidad: int) -> bytes:
        datos = bytearray()
        while len(datos) < cantidad:
            restante = self._limite - monotonic()
            if restante <= 0:
                raise ErrorModbus("Tiempo de espera Modbus agotado")
            self._socket.settimeout(restante)
            bloque = self._socket.recv(cantidad - len(datos))
            if not bloque:
                raise ErrorModbus("El servidor cerró la conexión")
            datos.extend(bloque)
        return bytes(datos)

    def _peticion(self, funcion: int, datos: bytes) -> bytes:
        if self._socket is None:
            raise ErrorModbus("No hay conexión con Factory I/O")
        self._transaccion = (self._transaccion + 1) & 0xffff
        cabecera = struct.pack(">HHHB", self._transaccion, 0, len(datos) + 2, self.unidad)
        try:
            self._limite = monotonic() + self.timeout
            self._socket.settimeout(self.timeout)
            self._socket.sendall(cabecera + bytes([funcion]) + datos)
            tid, protocolo, longitud, unidad = struct.unpack(">HHHB", self._recibir(7))
            if (tid, protocolo, unidad) != (self._transaccion, 0, self.unidad) or not 2 <= longitud <= 254:
                raise ErrorModbus("La respuesta de Factory I/O no es válida")
            respuesta = self._recibir(longitud - 1)
            if respuesta[0] == funcion | 0x80 and len(respuesta) == 2:
                raise ErrorModbus(f"Factory I/O ha rechazado la petición: {MOTIVOS_EXCEPCION.get(respuesta[1], 'error del servidor')}")
            if respuesta[0] != funcion:
                raise ErrorModbus("La respuesta de Factory I/O no es la esperada")
            return respuesta[1:]
        except (OSError, ErrorModbus) as exc:
            self.cerrar()  # nunca reutilizar un flujo que puede haber quedado desalineado
            raise ErrorModbus(str(exc)) from exc

    @staticmethod
    def _rango(direccion: int, cantidad: int, maximo: int):
        if not 0 <= direccion <= 65535 or not 1 <= cantidad <= maximo or direccion + cantidad > 65536:
            raise ValueError("Rango Modbus inválido")

    def leer_bits(self, direccion: int, cantidad: int = 1, *, entradas: bool = True) -> list[bool]:
        self._rango(direccion, cantidad, 2000)
        datos = self._peticion(2 if entradas else 1, struct.pack(">HH", direccion, cantidad))
        n = (cantidad + 7) // 8
        if len(datos) != n + 1 or datos[0] != n:
            self.cerrar()
            raise ErrorModbus("Factory I/O ha respondido con datos incompletos")
        return [bool(datos[1 + i // 8] & (1 << (i % 8))) for i in range(cantidad)]

    def escribir_coils(self, direccion: int, valores: list[bool]):
        self._rango(direccion, len(valores), 1968)
        if any(type(v) is not bool for v in valores):
            raise ValueError("Las coils requieren booleanos")
        n = (len(valores) + 7) // 8
        bits = bytearray(n)
        for i, valor in enumerate(valores):
            if valor:
                bits[i // 8] |= 1 << (i % 8)
        prefijo = struct.pack(">HH", direccion, len(valores))
        respuesta = self._peticion(15, prefijo + bytes([n]) + bits)
        if respuesta != prefijo:
            self.cerrar()
            raise ErrorModbus("Factory I/O no ha confirmado la escritura")

    def leer_registros(self, direccion: int, cantidad: int = 1, *, entradas: bool = True) -> list[int]:
        self._rango(direccion, cantidad, 125)
        datos = self._peticion(4 if entradas else 3, struct.pack(">HH", direccion, cantidad))
        if len(datos) != cantidad * 2 + 1 or datos[0] != cantidad * 2:
            self.cerrar()
            raise ErrorModbus("Factory I/O ha respondido con datos incompletos")
        return list(struct.unpack(f">{cantidad}H", datos[1:]))

    def escribir_registros(self, direccion: int, valores: list[int]):
        self._rango(direccion, len(valores), 123)
        if any(type(v) is not int or not 0 <= v <= 65535 for v in valores):
            raise ValueError("Los registros requieren enteros UINT16 de transporte")
        prefijo = struct.pack(">HH", direccion, len(valores))
        datos = struct.pack(f">{len(valores)}H", *valores)
        respuesta = self._peticion(16, prefijo + bytes([len(datos)]) + datos)
        if respuesta != prefijo:
            self.cerrar()
            raise ErrorModbus("Factory I/O no ha confirmado la escritura")
