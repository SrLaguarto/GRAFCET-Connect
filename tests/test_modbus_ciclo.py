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
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, timeout_ms=2000,
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
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20,
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
            cfg = Configuracion(host="127.0.0.1", puerto=servidor_cliente.puerto, periodo_ms=20,
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
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20,
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
                c.observar(Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, senales=[]), m.doc)  # otro modelo: mapa vacío
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
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, senales=[Senal("sensor", "discrete", 0)])
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
             "El simulador de procesos cerró la conexión"),
            (ConnectionResetError(10054, "Se ha forzado la interrupción de una conexión existente por el host remoto", None, 10054),
             "El simulador de procesos cerró la conexión"),
            (ConnectionRefusedError(10061, "No se puede establecer una conexión", None, 10061), "El simulador de procesos no acepta la conexión"),
            (ConnectionResetError(104, "Connection reset by peer"), "El simulador de procesos cerró la conexión"),
            (BrokenPipeError(32, "Broken pipe"), "El simulador de procesos cerró la conexión"),
            (socket.timeout("timed out"), "El simulador de procesos no ha respondido a tiempo"),
        ]
        for causa, frase in casos:
            self.assertTrue(explicar_fallo(fallo(causa)).startswith(frase), (causa, explicar_fallo(fallo(causa))))
        self.assertEqual(explicar_fallo(ErrorModbus("Tiempo de espera Modbus agotado")), "El simulador de procesos no ha respondido a tiempo")
        self.assertEqual(explicar_fallo(ErrorModbus("El servidor cerró la conexión")), "El simulador de procesos cerró la conexión")
        self.assertEqual(explicar_fallo(ErrorModbus("La respuesta del simulador de procesos no es válida")), "", "lo desconocido sigue con el mensaje técnico")
        # de punta a punta: el servidor corta la conexión y el coordinador la declara en error con el texto legible
        responde = [True]

        def responder(p):
            return (b"" if p[0] == 2 else p[:5]) if responde[0] else None
        with servidor(responder) as sc:
            m = M().var("sensor").step("E0", True)
            s = session(m.compile())
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, senales=[Senal("sensor", "discrete", 0)])
            c = Coordinador()
            try:
                c.iniciar(cfg, s)
                esperar(c, lambda: c.estado == "conectado")
                responde[0] = False
                esperar(c, lambda: c.estado == "error")
                self.assertTrue(c.mensaje.startswith("El simulador de procesos cerró la conexión"), c.mensaje)
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
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, senales=[
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
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, senales=senales)
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
                c.iniciar(Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, senales=[Senal("sensor", "discrete", 0)]), None,
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

    def test_SFIO59_vincular_no_escribe_nada_hasta_leer_y_aplicar_las_entradas(self):
        """REQ-SIM-02, REQ-SIM-04 (P-IMP-60): Play (vincular) y Reiniciar en Play leen las entradas de la planta ANTES de
        escribir: la primera petición tras vincular es una lectura, no se escribe nada hasta aplicar esa lectura a la sesión
        nueva y calcular, y la primera escritura ya lleva el sensor (con el sensor a 1 nunca se escribe el motor de la
        situación inicial)."""
        eventos, sensor = [], [1]

        def responder(p):
            if p[0] == 2:
                eventos.append(("leer", sensor[0]))
                return bytes([2, 1, sensor[0]])
            eventos.extend(("escribir", int.from_bytes(p[1:3], "big") + i, (p[6 + i // 8] >> (i % 8)) & 1)
                           for i in range(int.from_bytes(p[3:5], "big")))
            return p[:5]
        with servidor(responder) as sc:
            # E0 (inicial): motor; con el sensor, E1: luz. Con el sensor ya a 1, la situación inicial no llega a escribirse
            m = M().var("sensor").var("motor", "output").var("luz", "output").step("E0", True).step("E1")
            m.trans("t1", ["E0"], ["E1"], "sensor").cont("E0", "motor").cont("E1", "luz")
            cm = m.compile()
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, senales=[
                Senal("sensor", "discrete", 0), Senal("motor", "coil", 0), Senal("luz", "coil", 1)])
            c = Coordinador()
            try:
                c.iniciar(cfg, None, documento=m.doc)  # Pausa: pone a cero lo asignado y observa las entradas
                esperar(c, lambda: c.estado == "conectado")
                esperar(c, lambda: sum(e[0] == "leer" for e in eventos) >= 3)
                # Play: vincular una sesión nueva
                n = len(eventos)
                c.vincular(session(cm), cfg, m.doc)
                self.assertTrue(c.reiniciando)
                esperar(c, lambda: c.escritos.get("luz") is True, True)
                nuevos = eventos[n:]
                self.assertEqual(nuevos[0][0], "leer", "la primera petición tras Play es una lectura")
                primera = next(i for i, e in enumerate(nuevos) if e[0] == "escribir")
                self.assertGreaterEqual(primera, 1)
                self.assertEqual({e[0] for e in nuevos[:primera]}, {"leer"}, "no se escribe nada antes de leer")
                self.assertEqual([e for e in nuevos if e[0] == "escribir"][:2], [("escribir", 0, 0), ("escribir", 1, 1)],
                                 "la primera escritura ya lleva el sensor: motor a 0 y luz a 1")
                self.assertNotIn(("escribir", 0, 1), nuevos, "la situación inicial (motor) nunca llega a la planta")
                # Reiniciar en Play: sesión nueva, que arranca en E0 (motor); con el sensor a 1 evoluciona a E1 antes de escribir
                esperar(c, lambda: c.en_marcha, True)
                n = len(eventos)
                c.reiniciar(c.adaptador.sesion.restart("reinicio"))
                self.assertTrue(c.reiniciando)
                esperar(c, lambda: not c.reiniciando and c.en_marcha, True)
                for _ in range(30):
                    c.tick(True)
                    time.sleep(.001)
                nuevos = eventos[n:]
                self.assertIn(("leer", 1), nuevos)
                self.assertIn(("escribir", 1, 1), nuevos)
                self.assertNotIn(("escribir", 0, 1), nuevos, "Reiniciar tampoco escribe antes de leer")
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO61_pausar_tras_detenerse_el_motor_no_repite_el_cero(self):
        """REQ-SIM-02, REQ-ROB-01 (P-IMP-60): cuando el motor se detiene por un diagnóstico, `tick` ya pide el cero a la planta;
        si entonces se llama a `pausar(diagnostico=True)` (lo que hace la ventana al verlo) no llega un segundo cero, esté el
        primero sin enviar (otra petición en vuelo), en vuelo o ya confirmado. Siempre queda en Pausa, conectado y a cero."""
        for caso in ("pendiente", "en vuelo", "confirmado"):
            with self.subTest(caso):
                escrituras = []
                freno_lectura, freno_cero, llegada, liberar = (threading.Event() for _ in range(4))

                def responder(p):
                    if p[0] == 15:
                        escrituras.append((int.from_bytes(p[1:3], "big"), p[6] & 1))
                        if freno_cero.is_set() and not p[6] & 1:  # el cero del diagnóstico queda en el cable
                            llegada.set()
                            liberar.wait(2)
                    elif p[0] == 2 and freno_lectura.is_set():  # una lectura queda en vuelo
                        llegada.set()
                        liberar.wait(2)
                    return b"\x02\x01\x01" if p[0] == 2 else p[:5]
                with servidor(responder) as sc:
                    m = M().var("sensor").var("motor", "output").step("E0", True)
                    m.cont("E0", "motor", "sensor")
                    s = session(m.compile())
                    cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, timeout_ms=3000,
                                        senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
                    c = Coordinador()
                    try:
                        c.iniciar(cfg, s)
                        esperar(c, lambda: c.estado == "conectado")
                        esperar(c, lambda: c.escritos.get("motor") is True, True)
                        n = len(escrituras)
                        if caso == "pendiente":
                            freno_lectura.set()
                            esperar(c, llegada.is_set, True)  # hay una lectura en vuelo: el cero no puede salir todavía
                        elif caso == "en vuelo":
                            freno_cero.set()
                        s.status = "error"  # el motor se detiene
                        if caso == "pendiente":
                            c.tick(True)
                            self.assertEqual((c.estado, c.cero_pendiente), ("diagnostico", True))
                        elif caso == "en vuelo":
                            esperar(c, llegada.is_set, True)
                            self.assertEqual((c.estado, c.fase), ("diagnostico", "cero"))
                        else:
                            esperar(c, lambda: c.mensaje.startswith("Motor detenido · cero confirmado"), True)
                        c.pausar(diagnostico=True)
                        liberar.set()
                        esperar(c, lambda: c.escritos == {"motor": False} and c.futuro is None)
                        for _ in range(60):
                            c.tick(False)
                            time.sleep(.001)
                        self.assertEqual(escrituras[n:].count((0, 0)), 1, f"un solo cero en el cable: {escrituras[n:]}")
                        self.assertEqual(escrituras[-1], (0, 0))
                        self.assertEqual((c.estado, c.adaptador.sesion, c.escritos), ("conectado", None, {"motor": False}))
                        self.assertNotIn("Motor detenido", c.mensaje)
                        c.desconectar()
                        esperar(c, lambda: c.estado == "desconectado")
                    finally:
                        liberar.set()
                        c.cerrar()

    def test_SFIO64_observar_pone_a_cero_las_salidas_del_mapa_nuevo_una_vez_por_canal(self):
        """REQ-SIM-02, REQ-SIM-03 (P-IMP-60): cambiar de modelo con la conexión viva (`observar`) pide también el cero de las
        salidas asignadas del mapa nuevo, unido al del mapa anterior con un solo cero por canal (aunque dos modelos llamen
        igual a una variable, una booleana y otra de registro); sin salidas en el mapa nuevo solo queda el cero del anterior."""
        peticiones = []

        def responder(p):
            peticiones.append(p)
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        escribe = lambda: [(p[0], int.from_bytes(p[1:3], "big")) for p in peticiones if p[0] in (15, 16)]  # noqa: E731
        with servidor(responder) as sc:
            a = M("a").var("sensor").var("motor", "output").var("bomba", "output").step("E0", True)
            b = M("b").var("sensor").var("luz", "output").var("motor", "output", "decimal", scale=2).var("otra", "output").step("E0", True)
            mapa_a = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, modelo="a", senales=[
                Senal("sensor", "discrete", 0), Senal("motor", "coil", 0), Senal("bomba", "coil", 2)])
            mapa_b = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, modelo="b", senales=[
                Senal("sensor", "discrete", 0), Senal("luz", "coil", 0), Senal("motor", "holding", 3, "INT16"),
                Senal("otra", "coil", 5)])
            vacio = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, modelo="a", senales=[Senal("sensor", "discrete", 0)])
            c = Coordinador()
            try:
                c.iniciar(mapa_a, None, documento=a.doc)
                esperar(c, lambda: c.estado == "conectado")
                self.assertEqual(sorted(escribe()), [(15, 0), (15, 2)], "Conectar: el cero del mapa A")
                peticiones.clear()
                c.pausar(diagnostico=True)  # lo que hace la ventana con el mapa anterior
                c.observar(mapa_b, b.doc)
                esperar(c, lambda: c.escritos == {"luz": False, "motor": 0, "otra": False})
                for _ in range(40):
                    c.tick(False)
                    time.sleep(.001)
                self.assertEqual(sorted(escribe()), [(15, 0), (15, 2), (15, 5), (16, 3)],
                                 "los dos mapas, un solo cero por canal (la coil 0 es de los dos)")
                self.assertEqual(c.estado, "conectado")
                # otro cambio de modelo, ahora a un mapa sin salidas: solo se pone a cero lo del mapa que se deja
                peticiones.clear()
                c.pausar(diagnostico=True)
                c.observar(vacio, a.doc)
                esperar(c, lambda: sorted(escribe()) == [(15, 0), (15, 5), (16, 3)])
                for _ in range(40):
                    c.tick(False)
                    time.sleep(.001)
                self.assertEqual(sorted(escribe()), [(15, 0), (15, 5), (16, 3)], "el mapa nuevo no trae salidas")
                c.desconectar()
                esperar(c, lambda: c.estado == "desconectado")
            finally:
                c.cerrar()

    def test_SFIO65_desconectar_con_la_red_caida_dice_que_se_ha_desconectado_sin_invitar_a_reconectar(self):
        """REQ-ROB-01, REQ-SIM-03 (P-IMP-67): si la red falla al desconectar, el aviso dice que se ha desconectado y que las
        salidas no están garantizadas (no «Pulsa Conectar para reanudar»); el estado sigue siendo «error» y la conexión se
        cierra. Un fallo de red que no es de «Desconectar» conserva su texto de siempre (SFIO36)."""
        vivo = [True]

        def responder(p):
            if not vivo[0]:
                return None  # el servidor cae: corta la conexión
            return b"\x02\x01\x01" if p[0] == 2 else p[:5]
        with servidor(responder) as sc:
            m = M().var("sensor").var("motor", "output").step("E0", True)
            cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
            for estado_previo in ("en Pausa", "en Play"):
                vivo[0] = True
                c = Coordinador()
                try:
                    c.iniciar(cfg, session(m.compile()) if estado_previo == "en Play" else None, documento=m.doc)
                    esperar(c, lambda: c.estado == "conectado")
                    cliente = c.cliente
                    vivo[0] = False
                    c.desconectar()
                    esperar(c, lambda: not c.activo)
                    self.assertEqual(c.estado, "error", estado_previo)
                    self.assertIsNone(cliente._socket, "se cierra igual")
                    self.assertTrue(c.mensaje.startswith("Desconectado · salidas no garantizadas"), c.mensaje)
                    self.assertNotIn("Pulsa Conectar", c.mensaje)
                    self.assertNotIn("reanudar", c.mensaje)
                    self.assertIn("Detalle: ", c.mensaje, "con una frase legible, el detalle técnico detrás")
                finally:
                    vivo[0] = True
                    c.cerrar()

    def test_SFIO68_desconectar_mientras_se_conecta_y_la_conexion_falla_no_habla_de_poner_a_cero_la_planta(self):
        """REQ-ROB-01, REQ-SIM-03 (P-IMP-69): si se pulsa Desconectar mientras se conecta (o se prueba) y la conexión se rechaza o
        agota el tiempo, nunca hubo conexión ni intento de cero: el aviso dice «Desconectado · no se llegó a conectar: …» con el
        motivo legible, sin «salidas no garantizadas» ni «poner a cero»; el estado sigue en «error». Si el fallo llega después de
        abrir el TCP, conserva el aviso de siempre (SFIO65); la prueba, que no escribe nada, no habla de salidas."""
        import socket
        from unittest import mock
        from conexion.modbus import ClienteModbus, ErrorModbus
        m = M().var("sensor").var("motor", "output").step("E0", True)
        senales = [Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)]

        def desconectar_conectando(cfg, sesion, prueba=False):
            c = Coordinador()
            try:
                c.iniciar(cfg, sesion, prueba=prueba, documento=m.doc)
                self.assertEqual(c.estado, "probando" if prueba else "conectando")
                c.desconectar()
                esperar(c, lambda: not c.activo)
                return c.estado, c.mensaje, c.cliente._socket
            finally:
                c.cerrar()
        # un puerto en el que no escucha nadie: rechazada, o sin respuesta a tiempo si el sistema no contesta
        with socket.socket() as libre:
            libre.bind(("127.0.0.1", 0))
            puerto = libre.getsockname()[1]
        cfg = Configuracion(host="127.0.0.1", puerto=puerto, periodo_ms=20, timeout_ms=300, senales=senales)
        for nombre, sesion, prueba in (("en Pausa", None, False), ("en Play", session(m.compile()), False), ("probando", None, True)):
            estado, mensaje, sock = desconectar_conectando(cfg, sesion, prueba)
            self.assertEqual(estado, "error", nombre)
            self.assertIsNone(sock, nombre)
            self.assertTrue(mensaje.startswith("Desconectado · no se llegó a conectar: "), f"{nombre}: {mensaje}")
            for prohibido in ("poner a cero", "no garantizadas", "Pulsa Conectar", "reanudar"):
                self.assertNotIn(prohibido, mensaje, nombre)
        # rechazada, con el motivo legible y el código
        causa = ConnectionRefusedError(10061, "El equipo de destino denegó expresamente la conexión")
        causa.winerror = 10061
        rechazo = ErrorModbus(f"No se pudo conectar: {causa}")
        rechazo.__cause__ = causa
        with mock.patch.object(ClienteModbus, "conectar", side_effect=rechazo):
            estado, mensaje, _ = desconectar_conectando(cfg, None, False)
        self.assertEqual(estado, "error")
        self.assertTrue(mensaje.startswith("Desconectado · no se llegó a conectar: El simulador de procesos no acepta la conexión"),
                        mensaje)
        self.assertIn("Detalle: ", mensaje)
        # el TCP se abre y luego el servidor corta (la escritura del cero falla): sí hubo conexión, y las salidas no se garantizan
        with servidor(lambda p: None) as sc:
            cfg2 = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, timeout_ms=500, senales=senales)
            estado, mensaje, _ = desconectar_conectando(cfg2, None, False)
            self.assertEqual(estado, "error")
            self.assertTrue(mensaje.startswith("Desconectado · salidas no garantizadas · no se pudo poner a cero la planta: "), mensaje)
            # la prueba que se corta tras abrir el TCP: no escribe nada, no habla de salidas
            estado, mensaje, _ = desconectar_conectando(cfg2, None, True)
            self.assertEqual(estado, "error")
            self.assertTrue(mensaje.startswith("Desconectado · la prueba de conexión se interrumpió: "), mensaje)
            self.assertNotIn("salidas", mensaje)

    def test_SFIO69_play_con_el_cero_de_pausa_ya_enviado_no_lo_repite_y_en_el_cable_va_cero_lectura_escritura(self):
        """REQ-SIM-02, REQ-SIM-04, REQ-ROB-01 (P-IMP-69): Pausa pide el cero; si llega Play (`vincular`) con ese cero enviado y sin
        confirmar, o aún sin enviar, en el cable hay un solo cero y después, por este orden, una lectura y la primera escritura (que
        ya lleva el sensor). El cero no se da por hecho si su respuesta no llega: la conexión se detiene con «Salidas no
        garantizadas» y no se escribe nada más."""
        for caso in ("enviado sin confirmar", "sin enviar", "no llega la respuesta"):
            with self.subTest(caso):
                eventos = []
                freno_cero, freno_lectura, llegada, liberar = (threading.Event() for _ in range(4))

                def responder(p):
                    if p[0] == 15:
                        eventos.append(("escribir", int.from_bytes(p[1:3], "big"), p[6] & 1))
                        if freno_cero.is_set() and not p[6] & 1:  # el cero de Pausa queda en el cable sin respuesta
                            llegada.set()
                            liberar.wait(2)
                    elif p[0] == 2:
                        eventos.append(("leer",))
                        if freno_lectura.is_set():  # una lectura queda en vuelo: el cero no puede salir todavía
                            llegada.set()
                            liberar.wait(2)
                    return b"\x02\x01\x01" if p[0] == 2 else p[:5]
                with servidor(responder) as sc:
                    m = M().var("sensor").var("motor", "output").step("E0", True)
                    m.cont("E0", "motor", "sensor")
                    cm = m.compile()
                    cfg = Configuracion(host="127.0.0.1", puerto=sc.puerto, periodo_ms=20, timeout_ms=250 if caso == "no llega la respuesta" else 3000,
                                        senales=[Senal("sensor", "discrete", 0), Senal("motor", "coil", 0)])
                    c = Coordinador()
                    try:
                        c.iniciar(cfg, session(cm))
                        esperar(c, lambda: c.estado == "conectado")
                        esperar(c, lambda: c.escritos.get("motor") is True, True)
                        if caso == "sin enviar":
                            freno_lectura.set()
                            esperar(c, llegada.is_set, True)
                        else:
                            freno_cero.set()
                        c.pausar()
                        if caso != "sin enviar":
                            esperar(c, llegada.is_set)
                            self.assertEqual((c.fase, c.futuro is not None), ("seguras", True), "el cero está en el cable")
                        n = len(eventos)
                        c.vincular(session(cm), cfg, m.doc)  # Play, con el cero de Pausa sin resolver
                        for _ in range(30):
                            c.tick(True)
                            time.sleep(.001)
                        self.assertEqual(len(eventos), n, "mientras el cero no se resuelve no sale nada más")
                        if caso == "no llega la respuesta":
                            esperar(c, lambda: c.estado == "error", True)
                            self.assertIn("Salidas no garantizadas", c.mensaje)
                            for _ in range(30):
                                c.tick(True)
                                time.sleep(.001)
                            self.assertNotIn(("escribir", 0, 1), eventos[n:], "tras el fallo no se escribe nada más")
                            continue
                        liberar.set()
                        esperar(c, lambda: c.escritos.get("motor") is True, True)
                        for _ in range(30):
                            c.tick(True)
                            time.sleep(.001)
                        nuevos = eventos[n - 1 if caso == "enviado sin confirmar" else n:]  # (el cero en vuelo ya estaba apuntado)
                        self.assertEqual(nuevos.count(("escribir", 0, 0)), 1, f"un solo cero en el cable: {nuevos}")
                        resto = nuevos[nuevos.index(("escribir", 0, 0)) + 1:]
                        self.assertEqual(resto[0], ("leer",), "tras el cero, lo primero es leer las entradas")
                        self.assertEqual(next(x for x in resto if x[0] == "escribir"), ("escribir", 0, 1),
                                         "y la primera escritura ya lleva el sensor")
                        self.assertNotIn(("escribir", 0, 0), resto)
                        self.assertEqual((c.estado, c.en_marcha), ("conectado", True))
                        c.desconectar()
                        esperar(c, lambda: c.estado == "desconectado")
                    finally:
                        liberar.set()
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
