"""Una sola ventana principal por usuario; las aperturas posteriores se envían por IPC local."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, QElapsedTimer, QLockFile, QStandardPaths, Qt, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import isValid

from grafcet.examples import EJEMPLOS

MAX_MENSAJE = 16384


def directorio_instancia():
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    if not base:
        raise OSError("No se pudo localizar la carpeta de datos del usuario")
    return Path(base) / "GRAFCET Connect" / "instancia"


def mensaje_apertura(modelo=None, ejemplo=None):
    return {"version": 1, "modelo": str(Path(modelo).expanduser().resolve()) if modelo else None,
            "ejemplo": ejemplo}


def validar_mensaje(datos):
    if not isinstance(datos, dict) or datos.get("version") != 1:
        raise ValueError("Solicitud de apertura no válida")
    modelo, ejemplo = datos.get("modelo"), datos.get("ejemplo")
    if modelo is not None and (not isinstance(modelo, str) or not modelo or len(modelo) > 8192):
        raise ValueError("Ruta no válida")
    if ejemplo is not None and (not isinstance(ejemplo, str) or ejemplo not in EJEMPLOS):
        raise ValueError("Ejemplo no válido")
    return {"modelo": modelo, "ejemplo": ejemplo}


class InstanciaUnica(QObject):
    def __init__(self, app, carpeta=None, aislada=False):
        super().__init__(app)
        self.app = app
        self.carpeta = Path(carpeta) if carpeta is not None else None
        self.aislada = aislada
        self.codigo = 0
        self.ventana = None
        self.candado = None
        self.nombre = ""
        self.cola = deque()
        self.procesando = False
        self.clientes = set()
        self.servidor = QLocalServer(self)
        self.servidor.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.servidor.newConnection.connect(self._aceptar)
        self.espera = QTimer(self)
        self.espera.setSingleShot(True)
        self.espera.timeout.connect(self._procesar)
        app.aboutToQuit.connect(self.cerrar)

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traza):
        self.cerrar()

    def iniciar(self, modelo=None, ejemplo=None):
        if self.aislada:
            return True
        try:
            self.carpeta = self.carpeta or directorio_instancia()
            self.carpeta.mkdir(parents=True, exist_ok=True)
            ruta = os.path.normcase(str(self.carpeta.resolve()))
            huella = hashlib.sha256(ruta.encode("utf-8")).hexdigest()[:24]
            self.nombre = "grafcet-connect-" + huella
            candado = QLockFile(str(self.carpeta / "ventana.lock"))
            candado.setStaleLockTime(0)
            for _ in range(3):
                if candado.tryLock(0):
                    self.candado = candado
                    QLocalServer.removeServer(self.nombre)
                    if not self.servidor.listen(self.nombre):
                        raise RuntimeError(self.servidor.errorString())
                    return True
                if candado.error() != QLockFile.LockError.LockFailedError:
                    raise OSError("No se pudo reservar la ventana de GRAFCET Connect")
                if self._enviar(mensaje_apertura(modelo, ejemplo)):
                    return False
            raise RuntimeError("La ventana abierta no responde. Inténtalo de nuevo cuando termine de cerrarse.")
        except (OSError, RuntimeError, ValueError) as exc:
            self.codigo = 2
            QMessageBox.warning(None, "GRAFCET Connect", str(exc))
            self.cerrar()
            return False

    def _enviar(self, pedido):
        socket = QLocalSocket()
        try:
            socket.connectToServer(self.nombre)
            if not socket.waitForConnected(3000):
                return False
            socket.write(json.dumps(pedido, ensure_ascii=False).encode("utf-8") + b"\n")
            socket.flush()
            reloj = QElapsedTimer()
            reloj.start()
            recibido = False
            while True:
                while socket.canReadLine():
                    respuesta = json.loads(bytes(socket.readLine()).decode("utf-8"))
                    if not isinstance(respuesta, dict):
                        raise RuntimeError("Respuesta de apertura no válida")
                    estado = respuesta.get("estado")
                    if estado == "terminado":
                        return True
                    if estado == "rechazado":
                        raise RuntimeError("La ventana abierta no ha podido aceptar la solicitud")
                    recibido = recibido or estado == "recibido"
                if socket.state() == QLocalSocket.LocalSocketState.UnconnectedState:
                    return False
                if not recibido and reloj.elapsed() > 10000:
                    raise RuntimeError("La ventana abierta no responde. No se abrirá otra ventana.")
                socket.waitForReadyRead(500)
        finally:
            socket.abort()

    def vincular(self, ventana):
        self.ventana = ventana
        self.espera.start(0)

    def _aceptar(self):
        while self.servidor.hasPendingConnections():
            socket = self.servidor.nextPendingConnection()
            self.clientes.add(socket)
            socket.readyRead.connect(lambda s=socket: self._leer(s))
            socket.disconnected.connect(lambda s=socket: self._retirar(s))
            QTimer.singleShot(10000, socket, lambda s=socket: self._sin_mensaje(s))
            self._leer(socket)

    def _sin_mensaje(self, socket):
        if isValid(socket) and not socket.property("recibido"):
            socket.abort()

    def _retirar(self, socket):
        self.clientes.discard(socket)
        socket.deleteLater()

    def _responder(self, socket, estado, cerrar=False):
        if not isValid(socket) or socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            return
        socket.write(json.dumps({"estado": estado}).encode("utf-8") + b"\n")
        socket.flush()
        if cerrar:
            socket.disconnectFromServer()

    def _leer(self, socket):
        if socket.property("recibido"):
            return
        if socket.bytesAvailable() > MAX_MENSAJE:
            self._responder(socket, "rechazado", True)
            return
        if not socket.canReadLine():
            return
        try:
            pedido = validar_mensaje(json.loads(bytes(socket.readLine()).decode("utf-8")))
        except (ValueError, UnicodeError):
            self._responder(socket, "rechazado", True)
            return
        socket.setProperty("recibido", True)
        self._responder(socket, "recibido")
        self.cola.append((socket, pedido))
        self._activar()
        if not self.procesando:
            self.espera.start(0)

    def _activar(self):
        w = self.ventana
        if w is None or not isValid(w):
            return
        if w.isMinimized():
            w.setWindowState(w.windowState() & ~Qt.WindowState.WindowMinimized)
        destino = QApplication.activeModalWidget() or w
        destino.raise_()
        destino.activateWindow()

    def _procesar(self):
        if self.procesando or not self.cola or self.ventana is None:
            return
        if not isValid(self.ventana):
            self.cerrar()
            return
        if QApplication.activeModalWidget() is not None:
            self.espera.start(100)
            return
        socket, pedido = self.cola.popleft()
        if not isValid(socket) or socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            self.espera.start(0)
            return
        self.procesando = True
        try:
            self._activar()
            if pedido["modelo"]:
                self.ventana.abrir_ruta(Path(pedido["modelo"]))
            elif pedido["ejemplo"]:
                self.ventana.cargar_ejemplo(pedido["ejemplo"])
            else:
                self.ventana.nuevo()
        finally:
            self._responder(socket, "terminado", True)
            self.procesando = False
            if self.cola:
                self.espera.start(0)

    def cerrar(self):
        self.ventana = None
        self.espera.stop()
        self.servidor.close()
        self.cola.clear()
        for socket in tuple(self.clientes):
            if isValid(socket):
                socket.abort()
        if self.candado is not None:
            self.candado.unlock()
            self.candado = None
