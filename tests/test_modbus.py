"""Pruebas locales del transporte, sin Factory I/O ni dependencias externas."""
import socketserver
import struct
import threading
import time
import unittest
from contextlib import contextmanager

from conexion.modbus import ClienteModbus, ErrorModbus


@contextmanager
def servidor(responder, transformar=None):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            def recibir(n):
                datos = b""
                while len(datos) < n:
                    try:
                        parte = self.request.recv(n - len(datos))
                    except OSError:
                        return None
                    if not parte:
                        return None
                    datos += parte
                return datos
            while True:
                cabecera = recibir(7)
                if cabecera is None:
                    return
                tid, _, n, unidad = struct.unpack(">HHHB", cabecera)
                pdu = recibir(n - 1)
                if pdu is None:
                    return
                respuesta = responder(pdu)
                if respuesta is None:
                    return
                datos = struct.pack(">HHHB", tid, 0, len(respuesta) + 1, unidad) + respuesta
                if transformar:
                    datos = transformar(datos)
                try:
                    for octeto in datos:  # obliga al cliente a soportar fragmentación TCP
                        self.request.sendall(bytes([octeto]))
                except OSError:
                    return
    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
    with Server(("127.0.0.1", 0), Handler) as srv:
        hilo = threading.Thread(target=srv.serve_forever, daemon=True)
        hilo.start()
        cliente = ClienteModbus("127.0.0.1", srv.server_address[1], timeout=.3)
        try:
            cliente.conectar()
            yield cliente
        finally:
            cliente.cerrar()
            srv.shutdown()
            hilo.join()


class ModbusTests(unittest.TestCase):
    def test_SFIO14_mbap_y_timeout(self):
        """REQ-ROB-01: cabecera incoherente y servidor silencioso no bloquean el cliente."""
        for posicion, valor in ((1, 99), (3, 1), (6, 99), (4, 1)):
            def alterar(datos):
                b = bytearray(datos)
                b[posicion] = valor
                return bytes(b)
            with self.subTest(posicion=posicion), servidor(lambda p: b"\x02\x01\x01", alterar) as c:
                with self.assertRaises(ErrorModbus):
                    c.leer_bits(0)
        def lento(p):
            time.sleep(.2)
            return b"\x02\x01\x01"
        with servidor(lento) as c:
            c.timeout = .03
            inicio = time.monotonic()
            with self.assertRaises(ErrorModbus):
                c.leer_bits(0)
            self.assertLess(time.monotonic() - inicio, .15)

    def test_SFIO01_digitales_fragmentacion(self):
        """REQ-SIM-02: E/S externas por transporte separado del motor."""
        peticiones = []
        def respuesta(pdu):
            peticiones.append(pdu)
            return bytes([pdu[0], 2, 0x85, 1]) if pdu[0] in (1, 2) else pdu[:5]
        with servidor(respuesta) as c:
            esperado = [True, False, True, False, False, False, False, True, True]
            self.assertEqual(c.leer_bits(7, 9), esperado)
            self.assertEqual(c.leer_bits(7, 9, entradas=False), esperado)
            c.escribir_coils(3, esperado)
        self.assertEqual(peticiones[-1], b"\x0f\x00\x03\x00\x09\x02\x85\x01")

    def test_SFIO02_errores_y_reconexion(self):
        """REQ-ROB-01: rechaza respuestas defectuosas sin reutilizar el flujo."""
        for respuesta in (b"\x82\x02", b"\x02\x02\x01", b"\x03\x01\x01", None):
            with self.subTest(respuesta=respuesta), servidor(lambda p: respuesta) as c:
                with self.assertRaises(ErrorModbus):
                    c.leer_bits(0)
                with self.assertRaises(ErrorModbus):
                    c.leer_bits(0)
                c.conectar()

    def test_SFIO03_limites_y_confirmacion(self):
        """REQ-ROB-01: direcciones, booleanos y confirmación de escritura."""
        with servidor(lambda p: b"\x0f\x00\x00\x00\x02") as c:
            for direccion, cantidad in ((-1, 1), (65535, 2), (0, 0), (0, 2001)):
                with self.assertRaises(ValueError):
                    c.leer_bits(direccion, cantidad)
            with self.assertRaises(ValueError):
                c.escribir_coils(0, [1])
            with self.assertRaises(ErrorModbus):
                c.escribir_coils(0, [True])
