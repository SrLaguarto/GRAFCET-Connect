"""Conexión directa real contra HTTP falso, con latencia controlada para SX."""
from time import monotonic, sleep

from PySide6.QtCore import QPointF
from PySide6.QtTest import QTest
from conexion.configuracion import Configuracion
from escritorio.traer_modelo import Propuestas, traer
from tools import hoja_contactos as HC
from servidor_directo_falso import ServidorDirecto, senal


def esperar(condicion, limite_s=5):
    limite = monotonic() + limite_s
    while not condicion():
        HC._bombear(1)
        sleep(.002)  # El servidor falso es Python: dejarle el GIL entre vueltas de la UI.
        if monotonic() >= limite:
            raise AssertionError("No terminó la operación del servidor falso")


def contexto(caso, numero=60, retardo=.02, conectar=True):
    HC.aplicacion()
    datos = [senal(str(i), f"Señal {i}", papel="Input" if i < numero // 2 else "Output")
             for i in range(numero)]
    servidor = ServidorDirecto(datos)
    handler = servidor.servidor.RequestHandlerClass
    original = handler.responder

    def responder(objeto):
        sleep(retardo)
        return original(objeto)
    handler.responder = responder
    c = HC.Contexto(1366, 768)
    caso.addCleanup(cerrar, c, servidor)
    c.mostrar()
    c.e.poner_etapa(QPointF(200, 200), inicial=True)
    p = c.w.panel_es
    config = Configuracion(host="127.0.0.1", puerto=servidor.puerto,
                           modo="directo", modelo=c.e.ed.model["id"], timeout_ms=2000)
    propuestas = Propuestas(c.e, config, datos)
    for fila in propuestas.filas:
        fila.marcada = True
    traer(propuestas, p.directa.historial)
    p.cargar(c.e.ed.model, config)
    p.directa.catalogo = datos
    p.directa.dibujar()
    c.w._proyecto_modbus = c.w._proyecto
    if conectar:
        c.w._conectar_modbus()
        esperar(lambda: c.w.modbus.estado in ("conectado", "error"))
        if c.w.modbus.estado != "conectado":
            raise AssertionError(f"Falló la conexión HTTP falsa: {c.w.modbus.mensaje}")
        QTest.qWait(300)
    return c, servidor


def cerrar(c, servidor):
    c.w._mostrar_panel("inferior", False)
    c.w.rt.stop()
    c.w._proxima_lectura.stop()
    c.w.ciclo.parar()  # (V2-E7: este cierre lo lleva la función a mano, sin el hilo de control)
    c.w.modbus.desconectar()
    limite = monotonic() + 5
    while c.w.modbus.activo and monotonic() < limite:
        c.w.modbus.tick()
        QTest.qWait(2)
    c.w.modbus.cerrar()
    c.w.modbus.executor.shutdown(wait=True)
    HC._bombear(2)
    c.cerrar()
    servidor.cerrar()
