import time
import unittest
import threading

from conexion.coordinador import Coordinador
from conexion.configuracion import Configuracion, Senal
from helpers import M, session
from test_modbus import servidor


def esperar(c, condicion, ejecutar=False):
    limite = time.monotonic() + 3
    while not condicion():
        c.tick(ejecutar)
        if time.monotonic() > limite:
            raise AssertionError((c.estado, c.mensaje, c.fase))
        time.sleep(.001)


class CicloTests(unittest.TestCase):
    def test_SFIO21_reinicio_descarta_lectura_pendiente_sin_cerrar_tcp(self):
        """REQ-SIM-04: reinicio de ejecución independiente del transporte externo."""
        bloquear, iniciada, liberar = threading.Event(), threading.Event(), threading.Event()
        def responder(p):
            if p[0] == 2:
                if bloquear.is_set():
                    iniciada.set()
                    liberar.wait(1)
                return b"\x02\x01\x01"
            return p[:5]
        with servidor(responder) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            cfg = Configuracion(puerto=sc.puerto, periodo_ms=20, timeout_ms=2000,
                                senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, session(m.compile()))
                esperar(c, lambda: c.estado == "conectado")
                socket = c.cliente._socket
                bloquear.set()
                esperar(c, iniciada.is_set)
                nueva = c.adaptador.sesion.restart("reinicio1")
                c.reiniciar(nueva)
                ultima = nueva.restart("reinicio2")
                c.reiniciar(ultima)
                liberar.set()
                esperar(c, lambda: not c.reiniciando)
                self.assertIs(c.cliente._socket, socket)
                self.assertIs(c.adaptador.sesion, ultima)
                self.assertEqual(c.estado, "conectado")
                self.assertFalse(ultima.z.values["sensor"])
                self.assertEqual(c.escritos, {"motor": False})
                esperar(c, lambda: c.escritos.get("motor") is True, True)
            finally:
                liberar.set()
                c.cerrar()

    def test_SFIO15_temporizacion_sin_cambios_sensor(self):
        """REQ-TMP-02: el reloj existente dispara salidas aunque la muestra no cambie."""
        with servidor(lambda p: b"\x02\x01\x01" if p[0] == 2 else p[:5]) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "delay(1s, sensor, 0s)")
            s = session(m.compile())
            cfg = Configuracion(puerto=sc.puerto, periodo_ms=20,
                                senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                esperar(c, lambda: s.z.values["sensor"], True)
                self.assertFalse(s.z.outputs["motor"])
                s.advance_to(1000000)  # representa el avance del único QTimer de la ventana
                esperar(c, lambda: c.escritos.get("motor") is True, True)
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO09_ciclo_pausa_diagnostico(self):
        """REQ-SIM-02: ciclo completo, pausa conserva y diagnóstico solicita cero."""
        peticiones = []
        def responder(p):
            peticiones.append(p)
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        with servidor(responder) as servidor_cliente:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            s = session(m.compile())
            cfg = Configuracion(puerto=servidor_cliente.puerto, periodo_ms=20,
                                senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                self.assertFalse(s.z.values["sensor"], "Conectar no ejecuta el motor")
                esperar(c, lambda: c.escritos.get("motor") is True, True)
                self.assertTrue(s.z.outputs["motor"])
                # Completar el intercambio pendiente sin ejecutar: no se publica cero al pausar.
                n = sum(p[0] == 15 for p in peticiones)
                for _ in range(60):
                    c.tick(False)
                    time.sleep(.001)
                self.assertEqual(n, sum(p[0] == 15 for p in peticiones))
                self.assertTrue(s.z.outputs["motor"])
                s.status = "error"  # simula el resultado de un diagnóstico, sin alterar oráculos
                esperar(c, lambda: c.estado == "diagnostico" and c.escritos.get("motor") is False)
                self.assertTrue(s.z.outputs["motor"], "Poner planta a cero no modifica motor")
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO30_pausar_vincular_y_observar_sin_cerrar_tcp(self):
        """REQ-SIM-02, REQ-SIM-04: Pausa conserva TCP, sigue leyendo las entradas y pone a cero todas las salidas asignadas;
        Play vincula una sesión al TCP existente; un diagnóstico pide cero; observar cambia el mapa de lectura; nada de eso
        reconecta."""
        escrituras = []
        def responder(p):
            if p[0] == 15:
                escrituras.append((int.from_bytes(p[1:3], "big"), p[6] & 1))
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        with servidor(responder) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            m.cont("E0", "motor", "sensor")
            cm = m.compile()
            cfg = Configuracion(puerto=sc.puerto, periodo_ms=20,
                                senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, None, documento=m.doc)  # sin sesión (Pausa): el cero de lo asignado y solo observa las entradas
                esperar(c, lambda: c.estado == "conectado")
                socket = c.cliente._socket
                self.assertEqual((c.adaptador.sesion, escrituras), (None, [(0, 0)]), "una sola escritura: el cero de motor")
                c.vincular(session(cm), cfg, m.doc)  # Play
                esperar(c, lambda: not c.reiniciando)
                esperar(c, lambda: c.escritos.get("motor") is True, True)
                n = len(escrituras)
                c.pausar()  # Pausa: el TCP se conserva y la lectura sigue, pero todo a 0 hasta un nuevo Play
                esperar(c, lambda: c.escritos == {"motor": False} and escrituras[-1] == (0, 0))
                for _ in range(60):
                    c.tick(False)
                    time.sleep(.001)
                self.assertEqual((len(escrituras), c.escritos, c.estado), (n + 1, {"motor": False}, "conectado"),
                                 "una sola escritura: el cero; después Pausa no escribe más")
                self.assertIsNone(c.adaptador.sesion)
                self.assertEqual([s.variable for s in c.adaptador.entradas], ["sensor"])
                self.assertIs(c.cliente._socket, socket)
                c.vincular(session(cm), cfg, m.doc)  # Play otra vez: sesión nueva, mismo TCP
                esperar(c, lambda: not c.reiniciando)
                esperar(c, lambda: c.escritos.get("motor") is True, True)
                c.pausar(diagnostico=True)  # estado seguro por un diagnóstico: cero, sin cerrar
                esperar(c, lambda: c.escritos == {"motor": False} and escrituras[-1] == (0, 0))
                self.assertEqual(c.estado, "conectado")
                c.observar(Configuracion(puerto=sc.puerto, periodo_ms=20, senales=[]), m.doc)  # otro modelo: mapa vacío
                self.assertEqual((c.adaptador.entradas, c.muestra), ([], {}))
                for _ in range(20):
                    c.tick(False)
                    time.sleep(.001)
                self.assertIs(c.cliente._socket, socket)
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO10_perdida_y_reconexion_manual(self):
        """REQ-ROB-01: pérdida de red detiene; reconectar no reanuda el motor."""
        responde = [True]
        def responder(p):
            return (b"\x02\x01\x01" if p[0] == 2 else p[:5]) if responde[0] else None
        with servidor(responder) as sc:
            m = M().var("sensor").step("E0", True)
            s = session(m.compile())
            cfg = Configuracion(puerto=sc.puerto, senales=[Senal("sensor", "discrete", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                responde[0] = False
                esperar(c, lambda: c.estado == "error")
                responde[0] = True
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                self.assertFalse(s.z.values["sensor"])
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO36_errores_de_red_habituales_con_frase_legible(self):
        """REQ-ROB-01, REQ-SIM-03: los fallos de socket habituales (WinError 10053, 10054, 10061, reinicio, tubería rota,
        tiempo agotado) llevan una primera frase corta en español, el aviso de salidas y qué hacer, y detrás el detalle
        técnico; solo cambia el texto: el estado sigue siendo «error» y la conexión se cierra."""
        import socket
        from conexion.coordinador import explicar_fallo
        from conexion.modbus import ErrorModbus

        def fallo(causa):
            try:
                try:
                    raise causa
                except OSError as exc:
                    raise ErrorModbus(str(exc)) from exc
            except ErrorModbus as exc:
                return exc
        casos = [
            (ConnectionAbortedError(10053, "Se ha anulado una conexión establecida por el software en su equipo host", None, 10053),
             "Factory I/O cerró o anuló la conexión (WinError 10053)"),
            (ConnectionResetError(10054, "Se ha forzado la interrupción de una conexión existente por el host remoto", None, 10054),
             "Factory I/O cerró o anuló la conexión (WinError 10054)"),
            (ConnectionRefusedError(10061, "No se puede establecer una conexión", None, 10061), "Factory I/O rechazó la conexión (WinError 10061)"),
            (ConnectionResetError(104, "Connection reset by peer"), "Factory I/O cerró o anuló la conexión"),
            (BrokenPipeError(32, "Broken pipe"), "Factory I/O cerró o anuló la conexión"),
            (socket.timeout("timed out"), "Factory I/O no ha respondido a tiempo"),
        ]
        for causa, frase in casos:
            self.assertTrue(explicar_fallo(fallo(causa)).startswith(frase), (causa, explicar_fallo(fallo(causa))))
        self.assertEqual(explicar_fallo(ErrorModbus("Tiempo de espera Modbus agotado")), "Factory I/O no ha respondido a tiempo")
        self.assertEqual(explicar_fallo(ErrorModbus("El servidor cerró la conexión")), "Factory I/O cerró la conexión")
        self.assertEqual(explicar_fallo(ErrorModbus("Cabecera MBAP inválida")), "", "lo desconocido sigue con el mensaje técnico")
        # de punta a punta: el servidor corta la conexión y el coordinador la declara en error con el texto legible
        responde = [True]

        def responder(p):
            return (b"" if p[0] == 2 else p[:5]) if responde[0] else None
        with servidor(responder) as sc:
            m = M().var("sensor").step("E0", True)
            s = session(m.compile())
            cfg = Configuracion(puerto=sc.puerto, senales=[Senal("sensor", "discrete", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                responde[0] = False
                esperar(c, lambda: c.estado == "error")
                self.assertTrue(c.mensaje.startswith("Factory I/O "), c.mensaje)
                self.assertIn(". Salidas no garantizadas. Pulsa Conectar para reanudar. Detalle: ", c.mensaje)
                self.assertFalse(c.activo)
            finally:
                c.cerrar()

    def test_SFIO51_conectar_sin_sesion_pone_a_cero_las_asignadas_una_vez_antes_de_leer_y_probar_no_escribe(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): Conectar sin sesión (Pausa) escribe exactamente un cero a cada coil y holding
        asignada, antes de la primera lectura y sin nada más; Probar conexión no escribe nada."""
        peticiones = []

        def responder(p):
            peticiones.append(p)
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        with servidor(responder) as sc:
            m = M().var("sensor").var("motor", "output").var("vel", "output", "decimal", scale=2).step("E0", True)
            cfg = Configuracion(puerto=sc.puerto, periodo_ms=20, senales=[
                Senal("sensor", "discrete", 0), Senal("motor", "coil", 2), Senal("vel", "holding", 4, "INT16")])
            c = Coordinador()
            try:
                c.iniciar(cfg, None, prueba=True, documento=m.doc)
                esperar(c, lambda: c.estado == "desconectado")
                self.assertEqual([p[0] for p in peticiones], [2], "probar solo lee las entradas")
                peticiones.clear()
                c.iniciar(cfg, None, documento=m.doc)
                esperar(c, lambda: c.estado == "conectado")
                esperar(c, lambda: sum(p[0] == 2 for p in peticiones) >= 3)
                self.assertEqual([p[0] for p in peticiones[:2]], [15, 16], "el cero va antes de la primera lectura")
                self.assertEqual({p[0] for p in peticiones[2:]}, {2}, "después, solo se leen las entradas")
                self.assertEqual((int.from_bytes(peticiones[0][1:3], "big"), peticiones[0][6] & 1), (2, 0))
                self.assertEqual((int.from_bytes(peticiones[1][1:3], "big"), int.from_bytes(peticiones[1][6:8], "big")), (4, 0))
                self.assertEqual(c.escritos, {"motor": False, "vel": 0})
                self.assertIn("salidas a cero", c.mensaje)
                self.assertEqual(c.adaptador.salidas, [], "sin sesión no controla nada")
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO52_desconectar_escribe_el_cero_antes_de_cerrar_el_tcp_y_si_la_red_falla_cierra_igual_con_aviso(self):
        """REQ-SIM-02, REQ-ROB-01: Desconectar con la conexión establecida escribe el cero de todas las salidas asignadas (coils
        y holding) ANTES de cerrar el TCP, también desde Play; si la red falla, se cierra igual y el mensaje dice que las
        salidas no están garantizadas; sin salidas asignadas no hay nada que avisar y, mientras aún se conecta, no hay garantía."""
        planta, vivo = {}, [True]

        def responder(p):
            if not vivo[0]:
                return None  # el servidor cae: corta la conexión
            if p[0] == 15:
                planta[("coil", int.from_bytes(p[1:3], "big"))] = p[6] & 1
            elif p[0] == 16:
                planta[("holding", int.from_bytes(p[1:3], "big"))] = int.from_bytes(p[6:8], "big")
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        with servidor(responder) as sc:
            m = M().var("sensor").var("motor", "output").var("vel", "output", "decimal", scale=2).step("E0", True)
            m.cont("E0", "motor", "sensor")
            m.stored("E0", "vel", "activation", "1.5")
            cm = m.compile()
            senales = [Senal("sensor", "discrete", 0), Senal("motor", "coil", 2), Senal("vel", "holding", 4, "INT16")]
            cfg = Configuracion(puerto=sc.puerto, periodo_ms=20, senales=senales)
            # desde Play, sin pasar antes por Pausa: la planta acaba a cero y el TCP, cerrado
            c = Coordinador()
            try:
                c.iniciar(cfg, session(cm))
                esperar(c, lambda: c.estado == "conectado")
                esperar(c, lambda: c.escritos.get("motor") is True, True)
                self.assertEqual((planta[("coil", 2)], planta[("holding", 4)]), (1, 150))
                cliente = c.cliente
                c.desconectar()
                self.assertEqual(c.estado, "cerrando")
                self.assertNotIn("conservar", c.mensaje)
                esperar(c, lambda: c.estado == "desconectado")
                self.assertEqual(planta, {("coil", 2): 0, ("holding", 4): 0})
                self.assertIsNone(cliente._socket)
                self.assertEqual((c.mensaje, c.escritos), ("Desconectado · salidas a cero", {"motor": False, "vel": 0}))
            finally:
                c.cerrar()
            # la red falla: se cierra igual, con el aviso
            c = Coordinador()
            try:
                c.iniciar(cfg, None, documento=m.doc)
                esperar(c, lambda: c.estado == "conectado")
                cliente = c.cliente
                vivo[0] = False
                c.desconectar()
                esperar(c, lambda: not c.activo)
                self.assertIsNone(cliente._socket)
                self.assertIn("salidas no garantizadas", c.mensaje.lower())
            finally:
                vivo[0] = True
                c.cerrar()
            # sin salidas asignadas: no se escribe nada y no hay aviso
            antes = dict(planta)
            c = Coordinador()
            try:
                c.iniciar(Configuracion(puerto=sc.puerto, periodo_ms=20, senales=[Senal("sensor", "discrete", 0)]), None,
                          documento=m.doc)
                esperar(c, lambda: c.estado == "conectado")
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
                self.assertEqual((c.mensaje, planta), ("Desconectado", antes))
            finally:
                c.cerrar()
            # todavía conectando: no se puede garantizar el cero
            c = Coordinador()
            try:
                c.iniciar(cfg, None, documento=m.doc)
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
                self.assertEqual(c.mensaje, "Desconectado · salidas no garantizadas")
            finally:
                c.cerrar()

    def test_SFIO58_vincular_ya_no_tiene_el_parametro_observar_despues(self):
        """REQ-SIM-04: limpieza: Reiniciar en Pausa ya no tiene una variante «observar después» (Pausa = sin sesión y todo a 0 lo
        decide la ventana): ni el parámetro de `vincular` ni su estado interno existen."""
        import inspect
        self.assertNotIn("observar_despues", inspect.signature(Coordinador.vincular).parameters)
        c = Coordinador()
        try:
            self.assertFalse(hasattr(c, "_observar_despues"))
        finally:
            c.cerrar()
