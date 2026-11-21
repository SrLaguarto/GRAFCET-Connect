"""Ventana del simulador GRAFCET de escritorio (P-IMP-29, P-IMP-30): primera versión portable para Windows.

Simula un ejemplo o un modelo guardado (proyecto o documento de modelo, documento 09) con el dibujo de la
norma. Entradas, tiempo real (como un autómata: los retardos son temporizadores que cuentan solos), evolución a
evolución, traza, salidas, variables y temporizadores. Toda la
semántica la decide grafcet/engine.py con el perfil provisional: la ventana no aproxima nada y los bloqueos por
cuestiones U se muestran tal cual. No es el editor. Basado en IEC 60848.
"""
from __future__ import annotations
# Todo lo que importaba el módulo `ventana.py` sigue disponible aquí (las pruebas y otros módulos lo leen desde `escritorio.ventana`).
# flake8: noqa: F401
import copy
import html
import json
import os
import re
from time import perf_counter
from math import ceil
from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, Signal, QEvent, QElapsedTimer, QSettings, Qt, QTimer, QSize, QRectF, QPointF, QPoint, QUrl
from PySide6.QtGui import (QDesktopServices, QCursor, QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter,
                           QPainterPath, QPen, QPixmap, QFont, QFontMetrics)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
                               QScrollArea, QSplitter, QStackedWidget, QTabBar, QTableWidget, QTableWidgetItem,
                               QToolBar, QToolButton, QVBoxLayout, QWidget, QStyle, QMenu, QTextEdit, QPlainTextEdit, QAbstractSpinBox,
                               QSizePolicy, QStylePainter, QStyleOptionButton, QAbstractButton, QAbstractScrollArea, QStyledItemDelegate)
from .. import recursos_ui  # Registra los iconos vectoriales incorporados.
from .. import estilo
from .. import estilo_botones
from ..idioma import instalar as instalar_idioma
from ..ayudas_emergentes import instalar as instalar_ayudas
from ..laminas import VistaLamina
from ..estilo import _trazos_reinicio  # noqa: F401  (las pruebas lo leen desde aquí)
from .. import propiedades_archivo
from .. import actualizaciones
from ..aviso_version import DialogoVersionNueva
from grafcet.diagnostics import DiagnosticError
from grafcet.engine import Session
from grafcet.examples import EJEMPLOS
from grafcet.persistence import open_model
from grafcet.profile import APP_VERSION, SEMANTIC_OPTIONS, normalize_options
from grafcet.timeutil import parse_duration
from grafcet.view import Vista, auto_layout, layout_from_presentation, t_trunc
from ..diagrama import COL, VistaDiagrama, imagen
from ..edicion import HERRAMIENTAS, Edicion, aviso_valores_iniciales, quitar_valores_iniciales, sin_codigos
from ..propiedades import FichaJerarquia, PanelPropiedades, Paleta
from ..flotantes import GestorFlotantes
from ..paleta_variables import PaletaVariables
from ..navegacion import Navegacion
from ..leyenda import Leyenda
from ..mensajes import amable, motivo_parada, partir
from ..paneles import (PanelPlegable, DivisorPlegable, PilaActual, EtiquetaAyuda, EtiquetaElidida, BandaModo,
                      CajaSeccion, TituloSeccion, CabeceraCompacta, ContextoNombres, DelegadoNombres, EtiquetaGrupos, ReparteColumnas,
                      partir_nombre, LINEAS_NOMBRE)
from ..variables import PanelVariables
from ..entradas_salidas import CONEXION_INICIAL, PanelES
from conexion.configuracion import ARCHIVO, CANALES_INICIALES, Configuracion, aviso_host, normalizar_host
from conexion.coordinador import Coordinador
from ..archivos import ArchivosProyecto
from .. import sello
from .constantes import (ALTO_TRAZA, ANCHO_DERECHO, ANCHO_DERECHO_BASE, ARRIBA_CAJA, ARRIBA_VARIABLES, AVISO, AYUDA_EDICION,
                         ERRORES, ESPERA_ARRANQUE, ESPERA_ESCALA, ESTADOS, HUECO_FRANJA, ICONO_PROGRAMA, NOMBRE_HERRAMIENTA,
                         NOMBRE_MIN_TABLA, TEXTOS_FIRMA, TICK_MS, TITULO, TRAZA, UMBRAL_DERECHO, URL_CODIGO, URL_FALLOS,
                         _q_key)
from .dialogos import AcercaDe, DialogoForzado, _icono_barra, _icono_grafcet
from .widgets import (_AjustaBanda, _AjustaCabecera, _BotonEntrada, _DelegadoAbreviado, _FocoTeclado, _RespuestaModbus,
                      _SalidaRaton, _VigilaAlto)
from .menus import Menus
from .archivos import Archivos
from .simulacion import Simulacion
from .es import ConexionES
from .modos import Modos
from .vista import VistaVentana


class Ventana(Menus, Archivos, Simulacion, ConexionES, Modos, VistaVentana, ArchivosProyecto, QMainWindow):
    """La ventana principal: la fachada. Crea y conecta los controles y el estado compartido, y hereda las piezas (`archivos`, `simulacion`, `es`, `modos`, `vista`, `menus`), que son clases sin estado propio."""

    def __init__(self, ajustes: QSettings | None = None, obtener=None) -> None:
        instalar_idioma()
        instalar_ayudas()
        estilo_botones.instalar()  # (iconos y textos de los botones de herramientas, centrados; una sola vez)
        super().__init__()
        self.setWindowTitle(TITULO)
        self.resize(1360, 860)
        # Preferencias de la interfaz (paneles plegados) en un .ini del usuario, sin tocar el registro
        self.ajustes = ajustes or QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "GRAFCET", "Simulador")
        PaletaVariables.ajustes = self.ajustes  # (los grupos plegados de la paleta de variables se recuerdan en estos ajustes)
        self.options = normalize_options(None)  # por defecto: decisiones del responsable y, lo abierto, detener
        self.fuente: dict[str, Any] = {}
        self.v: Vista | None = None
        self.claves_entradas: tuple[str, ...] = ()
        self.botones: dict[str, QPushButton] = {}
        self.campos: dict[str, QLineEdit] = {}
        self.rt = QTimer(self)
        self.rt.setTimerType(Qt.TimerType.PreciseTimer)
        self.rt.setInterval(TICK_MS)
        self.rt.timeout.connect(self._tick)
        self.reloj = QElapsedTimer()
        self.edicion: Edicion | None = None
        self._arrancando = False  # el primer instante tras mostrarse la ventana por primera vez: la escala se aplica sin esperas
        self._arranque_hecho = False
        self._escala_lista = False  # verdadero solo mientras se aplica la escala que esperaba el final de la ráfaga de cambios de tamaño
        self._espera_escala = QTimer(self)
        self._espera_escala.setSingleShot(True)
        self._espera_escala.timeout.connect(self._escala_tras_la_rafaga)
        self._escala = "normal"  # la escala de letra y de controles de ahora (estilo.escala_para): cambia sola con el tamaño
        self._previa_traza: list[tuple[str, str]] | None = None  # lo que enseña la traza (texto y tipo de cada fila)
        self._previo_tablas: tuple[Any, ...] | None = None  # filas y aspecto con los que se dejaron las tablas de estado (`_variables`)
        estilo.activar_escala("normal")
        self._muy_estrecho = False
        self._ancho_forzado = 0  # por debajo de este ancho «Reiniciar» va como icono (lo fija `_vigilar_barra` si no cabe con texto)
        self._compacto = (False, False)  # (estrecho, bajo): lo fija el tamaño de la ventana (estilo.tamano_compacto)
        self._manual_paneles: dict[str, bool] = {}  # paneles que el usuario ha plegado o desplegado a mano: no se tocan solos
        self._auto_plegados: set[str] = set()  # paneles que el modo compacto ha plegado solo (y volverá a abrir)
        self.modo = "editar"  # solo cambia con Play (simular) y Pausa (editar)
        self.solo_lectura = False
        self._respuesta_modbus = _RespuestaModbus(self)
        self._respuesta_modbus.lista.connect(self._tick, Qt.ConnectionType.QueuedConnection)
        self.modbus = Coordinador(self._respuesta_modbus.notificar)
        self._proxima_lectura = QTimer(self)
        self._proxima_lectura.setSingleShot(True)
        self._proxima_lectura.setTimerType(Qt.TimerType.PreciseTimer)
        self._proxima_lectura.timeout.connect(self._tick)
        from ..refresco_conexion import RefrescoConexion
        self.refresco_conexion = RefrescoConexion(self)
        self._ultimo_refresco_modbus = 0.0
        self._marca_reloj_ns = 0
        self._resto_reloj_ns = 0
        self._transicion_ui = False  # Play/Pausa en curso: los cambios que él mismo provoca no lo repiten
        self._aviso_inestable_sesion = None  # sesión de la que ya se avisó (un solo aviso por episodio)
        self._popup_inestable = None
        self._marcas_diagnostico: set[str] = set()
        self._errores_auto = False  # «Mostrar errores» lo marcó un Play fallido (no el usuario)
        self._avisos_ejecucion: list[tuple[str, str]] = []  # por qué se paró el motor (texto, ayuda): entre los avisos al editar
        self._ayuda = ""  # ayuda del ejemplo o modelo abierto, para mostrarla al simular lo que aún no se ha editado
        self._proyecto: Any = None  # qué proyecto hay abierto (los ID de modelo no lo distinguen: todos los ejemplos son «m»)
        self._proyecto_modbus: Any = None  # de qué proyecto es el mapa que tiene cargado el panel de E/S
        self._n_nuevos = 0
        self._tipos_entrada: dict[tuple[Any, str], bool] = {}
        self._bajo_raton: Any = None  # lo que tiene el puntero encima y la línea de detalle cuenta: una entrada, o (tabla, fila)
        self._alto_cabecera = 0
        self._zoom_pendiente = False  # hay una revisión (diferida) de dónde van los controles del zoom
        self._hoja_escala = ""  # la hoja de la escala grande que llevan las partes de la ventana ("" en la normal)
        self._es_pendiente = False  # E/S y Propiedades aún llevan la escala de antes (se ponen al mostrarlos)
        self._entradas_nc = {}
        self._portapapeles = None
        self._menus()
        self._interfaz()
        self.diagrama.menu_portapapeles = self._menu_portapapeles
        QApplication.instance().focusChanged.connect(self._actualizar_portapapeles)
        QApplication.instance().focusChanged.connect(self._detalle_del_foco)
        app = QApplication.instance()
        if not hasattr(app, "_foco_teclado"):
            app._foco_teclado = _FocoTeclado(app)
            app.installEventFilter(app._foco_teclado)
        self.panel_es = PanelES()
        self._parametros_recordados = self._leer_parametros_recordados()
        self._conexion_recordada = tuple(self._parametros_recordados[k] for k in ("host", "puerto", "unidad"))
        self.panel_es.conexion_defecto = self._conexion_recordada
        self.panel_es.aviso_host_defecto = getattr(self, "_aviso_host_recordado", "")
        self.panel_es.parametros_defecto = copy.deepcopy(self._parametros_recordados)
        central = self.takeCentralWidget()
        self.paginas_es = QStackedWidget()
        self.paginas_es.addWidget(central)
        self.paginas_es.addWidget(self.panel_es)
        from ..planos import PaginaPlanos
        self.panel_planos=PaginaPlanos(self)
        self.paginas_es.addWidget(self.panel_planos)  # PLANOS se pinta su propia tarjeta (`PaginaPlanos.paintEvent`)
        contenedor=QWidget();disposicion=QVBoxLayout(contenedor);disposicion.setContentsMargins(0,0,0,0);disposicion.setSpacing(0)
        self.pestanas_vistas=QTabBar();self.pestanas_vistas.setExpanding(False);self.pestanas_vistas.setDrawBase(True)
        for texto in ('GRAFCET','PLANOS','E/S externas'):self.pestanas_vistas.addTab(texto)
        self.pestanas_vistas.setTabVisible(2,False)  # a E/S se entra por la luz de conexión (`luz_es`); el índice 2 solo marca la página
        self.pestanas_vistas.setObjectName("pestanasVistas")  # su aspecto lo da la hoja global (estilo.py)
        self.pestanas_vistas.setUsesScrollButtons(False)  # son dos pestañas: nunca flechas de desplazamiento
        self.pestanas_vistas.setAccessibleName("Vista: GRAFCET, PLANOS")
        # La fila de arriba: las pestañas a la izquierda y, a la derecha del todo, la luz de la conexión externa (`luz_es`)
        self.fila_pestanas=QWidget();self.fila_pestanas.setObjectName('filaPestanas');self.fila_pestanas.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.fila_pestanas.setMinimumWidth(1)  # su contenido (con textos) no fija el mínimo de la ventana: «Reiniciar» y la luz pasan a icono y texto corto al estrecharse
        fila_p=QHBoxLayout(self.fila_pestanas);fila_p.setContentsMargins(estilo.E2,0,estilo.E2,0);fila_p.setSpacing(0)
        fila_p.addWidget(self.pestanas_vistas);fila_p.addStretch(1)
        disposicion.addWidget(self.fila_pestanas)
        self.aviso_traer=QWidget();self.aviso_traer.setObjectName('avisoSeleccionPlanos')
        self._estilo_aviso_traer()
        fila=QHBoxLayout(self.aviso_traer);fila.setContentsMargins(12,estilo.E2,12,estilo.E2);fila.setSpacing(estilo.E2);fila.addWidget(QLabel('PLANOS · Selecciona el GRAFCET para la hoja'))
        self.b_confirmar_traer=QPushButton('Añadir selección a la hoja');self.b_confirmar_traer.setObjectName('confirmarSeleccionHoja');fila.addWidget(self.b_confirmar_traer);cancelar=QPushButton('Cancelar');fila.addWidget(cancelar);fila.addStretch(1)
        self.b_confirmar_traer.clicked.connect(self.confirmar_traer);cancelar.clicked.connect(self.cancelar_traer)
        self.destino_traer=None;self.aviso_traer.hide();disposicion.addWidget(self.paginas_es,1);disposicion.addWidget(self.aviso_traer)
        self.setCentralWidget(contenedor)
        self.pestanas_vistas.currentChanged.connect(lambda i:self.mostrar_es() if i==2 else self._mostrar_pagina('planos' if i==1 else False))
        self.panel_es.volver.connect(lambda: self._mostrar_pagina(False))
        self.panel_es.detalle.connect(self._detallar)  # el nombre entero de lo que señala el puntero en E/S, en la barra de estado
        self.panel_es.conectar.connect(self._conectar_modbus)
        self.panel_es.probar.connect(lambda: self._conectar_modbus(prueba=True))
        self.panel_es.desconectar.connect(self._desconectar_modbus)
        self.panel_es.guardar.connect(self._guardar_config_modbus)
        self.panel_es.cargar_archivo.connect(self._abrir_config_modbus)
        self.panel_es.aplicar.connect(self._persistir_mapa_modbus)
        self._barra_herramientas()
        self._paneles()
        self.panel_es.estado_cambiado.connect(self._luz_es)
        self._version_nueva: actualizaciones.Resultado | None = None
        self._dialogo_version: DialogoVersionNueva | None = None
        self.comprobador = actualizaciones.Comprobador(self, obtener)
        self.comprobador.resultado.connect(self._resultado_actualizacion)
        self.nuevo()
        self._cargar_config_modbus(self.edicion.ed.model)
        for nombre in ("derecho", "inferior"):
            self._mostrar_panel(nombre, self.visibilidad_paneles.abiertos[nombre], guardar=False)
        self._accesibilidad()
        self._configurar_foco()
        self._estilos_locales()
        self._foco_inicial = False
        # La hoja de la ventana es siempre la de la escala normal; en la escala grande la hoja entera (con las letras y los alto de control
        # grandes) va en las partes de la ventana, y en la vista de E/S solo cuando se muestra: así cruzar 1600×900 no repasa los más de mil
        # widgets de las filas de E/S (era lo que congelaba la interfaz ≈ 700 ms). El que está más cerca manda sobre el de la ventana.
        self._destinos_hoja = [self.menuBar(), self.statusBar(), self.fila_pestanas, self.herramientas_grafcet, self.split,
                               self.inferior.widget(0)]  # (la vista de E/S, Propiedades y PLANOS, al mostrarlas; el aviso de PLANOS lleva su hoja propia)
        self._planos_pendiente = False


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="GRAFCET", description=TITULO)
    ap.add_argument("modelo", nargs="?", help="archivo .grafnet")
    ap.add_argument("--ejemplo", choices=list(EJEMPLOS), help=argparse.SUPPRESS)
    ap.add_argument("--captura", metavar="PNG", help="guardar una captura de la ventana y salir (comprobación)")
    ap.add_argument("--prueba-contenedor",action="store_true",help=argparse.SUPPRESS)
    ap.add_argument("--prueba-distribucion", metavar="GRAFNET", help=argparse.SUPPRESS)
    ap.add_argument("--prueba-propiedades", metavar="TXT", help=argparse.SUPPRESS)
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    if args.prueba_contenedor:
        from ..proyecto_archivo import comprobar_contenedor
        comprobar_contenedor()
        return 0
    if args.prueba_distribucion:
        # Comprobación de construcción: clave de distribución (no la de desarrollo) y que abre su propio ejemplo.
        from grafcet.contenedor import sello_valido
        datos = Path(args.prueba_distribucion).read_bytes()
        return 0 if not sello.DESARROLLO and sello_valido(datos, sello.CLAVE) else 3
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(TITULO)
    app.setWindowIcon(QIcon(str(ICONO_PROGRAMA)))
    from ..instancia_unica import InstanciaUnica
    with InstanciaUnica(app, aislada=bool(args.captura or args.prueba_propiedades)) as instancia:
        if not instancia.iniciar(args.modelo, args.ejemplo):
            return instancia.codigo
        from ..errores import instalar as instalar_avisos_de_error
        instalar_avisos_de_error()
        from ..carpetas import asegurar_carpetas
        ajustes = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "GRAFCET", "Simulador")
        try:
            rutas = asegurar_carpetas()
            from ..ejemplos_archivos import instalar_ejemplos
            instalar_ejemplos(rutas["grafcet"], ajustes)
        except OSError as exc:
            QMessageBox.warning(None, "Carpetas de GRAFCET Connect", str(exc))
        w = Ventana(ajustes)
        instancia.vincular(w)
        if args.prueba_propiedades:
            # Comprobación de construcción: el diálogo Propiedades del archivo se monta en el ejecutable.
            import traceback
            try:
                propiedades_archivo.PropiedadesArchivo(propiedades_archivo.recopilar(w.edicion, True), w)
                Path(args.prueba_propiedades).write_text("ok", encoding="utf-8")
                return 0
            except Exception:
                Path(args.prueba_propiedades).write_text(traceback.format_exc(), encoding="utf-8")
                return 4
        if args.ejemplo:
            w.cargar_ejemplo(args.ejemplo)
        if args.modelo and not w.abrir_ruta(Path(args.modelo)):
            return 1 if args.captura else 0
        if args.captura:
            w.show()  # (la captura de comprobación conserva el tamaño de siempre)
        else:
            # La aplicación arranca siempre maximizada; al restaurar, la ventana se comporta como siempre. En Windows el
            # sistema muestra un instante la ventana con su tamaño normal antes de maximizarla (el «amago» de ventana
            # pequeña): se abre transparente y se hace opaca cuando ya está maximizada.
            w.setWindowOpacity(0.0)
            w.showMaximized()
            QTimer.singleShot(0, w, lambda: w.setWindowOpacity(1.0))
        if (not args.captura and not os.environ.get(actualizaciones.VARIABLE_SIN_ACTUALIZAR)
                and actualizaciones.al_arrancar_activo(w.ajustes)):
            QTimer.singleShot(1500, w.buscar_actualizaciones)  # con la ventana ya a la vista; en un hilo, sin bloquear
        if args.captura:
            def capturar_y_salir():
                w.grab().save(args.captura)
                app.quit()
            QTimer.singleShot(300, capturar_y_salir)
        return app.exec()
