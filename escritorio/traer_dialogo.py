"""Ventana modal de lectura, revisión e importación de E/S."""
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from conexion.http_directo import ClienteDirecto
from . import estilo
from .estilo_dialogos import CabeceraDialogo, PieDialogo, aplicar_escala_dialogo
from .interaccion_propiedades import ArrastrePropiedades
from .medidas_propiedades import ancho_maximo, margen_horizontal
from .paneles import EtiquetaElidida
from .traer_modelo import Propuestas, interna, nombre_visible, traer


class DialogoTraer(QDialog):
    def __init__(self, controlador):
        banderas = Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        super().__init__(controlador.panel, banderas)
        self.anfitrion = controlador.panel.window()
        self.controlador = controlador
        self.setWindowTitle("Traer E/S del simulador de fábricas")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        aplicar_escala_dialogo(self)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="traer-es")
        self.futuro = None
        self.propuestas = None
        self.tablas = []
        self.cambiando = False
        self.resumen = ""
        self.otra_escena = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(estilo.E2, estilo.E2, estilo.E2, estilo.E2)
        self.cabecera = CabeceraDialogo(self.windowTitle(), mostrar_cerrar=True)
        self.cabecera.cerrar_pedido.connect(self.reject)
        self.cabecera.boton_cerrar.setAccessibleName("Cerrar Traer E/S")
        self.titulo = self.cabecera.etiqueta_titulo
        layout.addWidget(self.cabecera)
        self.arrastre = ArrastrePropiedades(self, self.anfitrion)
        from .resumen_escena import ResumenEscena
        self.resumen_escena = ResumenEscena()
        self.estado = self.resumen_escena.etiqueta
        fila_aviso = QHBoxLayout()
        fila_aviso.addWidget(self.resumen_escena, 1)
        layout.addLayout(fila_aviso)
        from .ayuda_servidor_web import AyudaServidorWeb
        self.ayuda_servidor = AyudaServidorWeb(self.estado, fila_aviso, reintentar="Volver a leer")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.zona = QWidget()
        contenido = QVBoxLayout(self.zona)
        contenido.setContentsMargins(0, 0, 0, 0)
        self.grupos = QVBoxLayout()
        self.grupos.setContentsMargins(0, 0, 0, 0)
        contenido.addLayout(self.grupos)
        from .ayuda_lectura_es import AyudaLecturaES
        self.ayuda_lectura = AyudaLecturaES()
        contenido.addWidget(self.ayuda_lectura, 1)
        self.ayuda_servidor.texto_cambiado.connect(self.ayuda_lectura.actualizar)
        scroll.setWidget(self.zona)
        layout.addWidget(scroll, 1)
        pie = PieDialogo(texto_aceptar="Traer 0", alto_botones=estilo.ALTO_CONTROL)
        pie.rechazado.connect(self.reject)
        pie.aceptado.connect(self.importar)
        self.b_traer = pie.boton_aceptar
        self.b_leer = QPushButton("Volver a leer")
        self.b_leer.setAutoDefault(False)
        self.b_leer.setFixedHeight(estilo.ALTO_CONTROL)
        estilo.poner(self.b_leer, pieDialogo=estilo.ALTO_CONTROL == estilo.ALTO_ESTANDAR)
        pie.agregar_izquierda(self.b_leer)
        self.motivos = EtiquetaElidida()
        self.motivos.setWordWrap(False)
        self.motivos.setTextFormat(Qt.TextFormat.PlainText)
        self.motivos.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.motivos.setStyleSheet(f"color:{estilo.ERROR}")
        aviso = QHBoxLayout()
        aviso.addWidget(self.motivos, 1)
        self.b_corregir = QPushButton("Corregir nombres incompatibles")
        self.b_corregir.clicked.connect(self.corregir_nombres)
        aviso.addWidget(self.b_corregir)
        layout.addLayout(aviso)
        layout.addWidget(pie)
        self.b_leer.clicked.connect(self.leer)
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.recoger)
        self.finished.connect(self.cerrar_trabajo)
        self.leer()

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(QPen(QColor(estilo.ACENTO), 1))
        pintor.setBrush(QColor(estilo.FONDO))
        marco = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        pintor.drawRoundedRect(marco, estilo.R_M, estilo.R_M)
        pintor.end()

    def showEvent(self, evento):
        super().showEvent(evento)
        self.anfitrion.installEventFilter(self)
        QTimer.singleShot(0, self, self._centrar_en_ventana)

    def hideEvent(self, evento):
        self.anfitrion.removeEventFilter(self)
        super().hideEvent(evento)

    def eventFilter(self, objeto, evento):
        if objeto is self.anfitrion and evento.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            self.arrastre.limitar()
        return super().eventFilter(objeto, evento)

    def _centrar_en_ventana(self):
        if not self.isVisible():
            return
        anfitrion = self.anfitrion
        pantalla = anfitrion.screen().availableGeometry()
        area = pantalla
        if anfitrion.isVisible():
            cliente = QRect(anfitrion.mapToGlobal(QPoint()), anfitrion.size())
            area = cliente.intersected(pantalla)
        margen = margen_horizontal(area.width())
        espacio = area.adjusted(margen, estilo.E6, -margen, -estilo.E6)
        ancho = min(ancho_maximo(), espacio.width())
        alto = min(610, espacio.height())
        tamano = QSize(max(1, ancho), max(1, alto))
        self.setMaximumSize(tamano)
        self.resize(tamano)
        cuadro = QRect(QPoint(), self.size())
        cuadro.moveCenter(area.center())
        if anfitrion.isVisible():
            self.arrastre.limitar(cuadro.topLeft())
        else:
            self.move(cuadro.topLeft())
        self._repartir_columnas()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._repartir_columnas()

    def _repartir_columnas(self):
        for tabla, _ in self.tablas:
            ancho_vp = tabla.viewport().width()
            if ancho_vp <= 0:
                continue
            cab = tabla.horizontalHeader()
            fm = tabla.fontMetrics()
            pide_col1 = cab.sectionSizeFromContents(1).width()
            for r in range(tabla.rowCount()):
                it = tabla.item(r, 1)
                if it is not None and it.text():
                    pide_col1 = max(pide_col1, fm.horizontalAdvance(it.text()) + 16)
            fijas = tabla.columnWidth(0) + tabla.columnWidth(3) + tabla.columnWidth(4)
            disponible = max(120, ancho_vp - fijas)
            min_col2 = getattr(tabla, "_ancho_min_col2", 240)
            tabla.setColumnWidth(1, min(pide_col1, max(100, disponible - min_col2)))

    def _fuente_titulo(self):
        fuente = QFont(self.font())
        fuente.setPixelSize(estilo.T_PEQUENA)
        return fuente

    def cerrar_trabajo(self):
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def leer(self):
        if self.futuro is not None:
            return
        config = self.controlador.obtener()
        self.b_leer.setEnabled(False)
        self.b_traer.setEnabled(False)
        self.ayuda_lectura.hide()
        self.estado.setText(self.ayuda_servidor.mostrar(f"{config.host}:{config.puerto} · Leyendo señales…"))
        def trabajo():
            cliente = ClienteDirecto(config.host, config.puerto, timeout=config.timeout_ms / 1000)
            try:
                return cliente.catalogo()
            finally:
                cliente.cerrar()
        self.futuro = self.executor.submit(trabajo)
        self.timer.start()

    def recoger(self):
        if self.futuro is None or not self.futuro.done():
            return
        self.timer.stop()
        futuro, self.futuro = self.futuro, None
        self.b_leer.setEnabled(True)
        try:
            catalogo = futuro.result()
        except (ValueError, OSError) as exc:
            mensaje = self.ayuda_servidor.mostrar(str(exc))
            self.estado.setText(mensaje)
            if not self.tablas:
                self.ayuda_lectura.mostrar(mensaje, not self.ayuda_servidor.boton.isHidden())
            return
        from conexion.reconciliar import reconciliar
        anteriores = {u.variable: u.id for u in self.controlador.panel.config.uniones}
        avisos = reconciliar(self.controlador.panel.config, self.controlador.edicion.ed.model, catalogo)
        from .escena_modelo import contar_reunidas
        self.controlador.catalogo_leido = True
        self.controlador.reunidas_lectura = contar_reunidas(anteriores, self.controlador.panel.config)
        self.controlador.avisos_lectura = avisos
        from conexion.filtro_directo import actualizar
        actualizar(self.controlador.panel.config, catalogo)
        self.controlador.catalogo = catalogo
        self.controlador.dibujar()
        self.controlador.aplicar()
        self.propuestas = Propuestas(self.controlador.edicion, self.controlador.panel.config, catalogo)
        self.propuestas.avisos = avisos
        from .avisos_nombres import corregir_nombres
        corregir_nombres(self.propuestas)
        from .escena_modelo import resumen_lectura
        texto = resumen_lectura(self.controlador.panel.config, catalogo, self.controlador.reunidas_lectura)
        self.resumen_escena.fijar(texto, avisos)
        if self.otra_escena is not None:
            self.otra_escena.aviso.hide()
            self.otra_escena.rellenar()
        self.construir()

    def construir(self):
        self.tablas.clear()
        while self.grupos.count():
            item = self.grupos.takeAt(0)
            if item.widget() and item.widget() is not self.otra_escena:
                item.widget().deleteLater()
        escena = (
            [f for f in self.propuestas.filas if not interna(f.senal) and f.senal["kind"].lower() == "input"]
            + [f for f in self.propuestas.filas if not interna(f.senal) and f.senal["kind"].lower() == "output"]
        )
        internas = [f for f in self.propuestas.filas if interna(f.senal)]
        self.grupo("Señales de la escena", escena, False, leyenda_auto=True)
        self.grupo("Del propio simulador", internas, True)
        if self.otra_escena is None:
            from .otra_escena import OtraEscena
            self.otra_escena = OtraEscena(self.controlador)
            self.otra_escena.limpiada.connect(self.tras_limpiar)
        self.grupos.addWidget(self.otra_escena)
        self.grupos.addStretch()
        self._repartir_columnas()
        QTimer.singleShot(0, self, self._repartir_columnas)
        self.pintar()

    def tras_limpiar(self):
        from .escena_modelo import resumen_lectura
        controlador = self.controlador
        self.propuestas.config = controlador.panel.config
        texto = resumen_lectura(controlador.panel.config, controlador.catalogo, controlador.reunidas_lectura)
        detalles = [u.motivo for u in controlador.panel.config.uniones if u.motivo]
        self.resumen_escena.fijar(texto, detalles)
        self.construir()

    def grupo(self, nombre, filas, plegado, leyenda_auto=False):
        caja = QWidget(self.zona)
        layout = QVBoxLayout(caja)
        layout.setContentsMargins(0, estilo.E2, 0, 0)
        layout.setSpacing(estilo.E2)
        cabecera = QHBoxLayout()
        from .paleta_variables import TituloGrupo
        papel = "interna" if plegado else "escena"
        titulo = TituloGrupo(papel, self)
        titulo.setText(f"{nombre} · {len(filas)}")
        titulo.plegado = plegado
        todas = QPushButton("Marcar todas / ninguna")
        cabecera.addWidget(titulo)
        cabecera.addStretch()
        cabecera.addWidget(todas)
        layout.addLayout(cabecera)
        tabla = QTableWidget(len(filas), 5, caja)
        tabla.setHorizontalHeaderLabels(
            ["Usar", "Señal en el simulador", "Nombre de variable en GRAFCET Connect", "Sentido", "Tipo"]
        )
        tabla.verticalHeader().hide()
        from .traer_celdas import NombrePropuesto
        tabla.setItemDelegateForColumn(2, NombrePropuesto(tabla))
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(tabla)
        self.grupos.addWidget(caja)
        tabla.ensurePolished()
        cabecera_h = tabla.horizontalHeader()
        cabecera_h.ensurePolished()
        fm_cab = cabecera_h.fontMetrics()
        fm_cel = tabla.fontMetrics()
        tabla._ancho_min_col2 = fm_cab.horizontalAdvance("Nombre de variable en GRAFCET Connect") + 16
        ancho_sentido = max(76, fm_cab.horizontalAdvance("Sentido") + 16, fm_cel.horizontalAdvance("Entrada") + 20)
        ancho_tipo = max(84, fm_cab.horizontalAdvance("Tipo") + 16, fm_cel.horizontalAdvance("Booleana") + 20)
        tabla.setColumnWidth(3, ancho_sentido)
        tabla.setColumnWidth(4, ancho_tipo)
        self._poner_filas(tabla, filas)
        from .traer_celdas import ajustar_casillas
        ajustar_casillas(tabla)
        cabecera_h.ensurePolished()
        alto_cab = max(32, cabecera_h.height(), cabecera_h.sizeHint().height())
        alto_tabla = alto_cab + sum(tabla.rowHeight(r) for r in range(len(filas))) + 2 * tabla.frameWidth() + 6
        tabla.setMinimumHeight(min(300, max(48, alto_tabla)))
        tabla.setMaximumHeight(min(340, max(48, alto_tabla)))
        ancho = fm_cab.horizontalAdvance("Usar") + 2 * estilo.E2
        if any(f.ya for f in filas):
            ancho = max(ancho, fm_cel.horizontalAdvance("ya traída") + 2 * estilo.E2)
        tabla.setColumnWidth(0, ancho)
        tabla._repartir = self._repartir_columnas
        tabla.itemChanged.connect(lambda item: self.editar(tabla, filas, item))
        todas.clicked.connect(lambda: self.marcar(tabla, filas))
        titulo.clicked.connect(lambda: self.plegar(titulo, tabla, titulo.plegado))
        tabla.setVisible(not plegado)
        if leyenda_auto:
            w_ley = QWidget(caja)
            hl = QHBoxLayout(w_ley)
            hl.setContentsMargins(0, 2, 0, 2)
            hl.setSpacing(8)
            tag = QLabel("auto")
            tag.setObjectName("etiquetaAutoTraer")
            tag.setStyleSheet(
                f"background:{estilo.ACENTO_SUAVE}; color:{estilo.ACENTO_OSCURO}; "
                f"border:1px solid {estilo.ACENTO_BORDE}; border-radius:9px; "
                f"padding:1px 7px; font-size:11px; font-weight:700;"
            )
            desc = QLabel(
                "Los nombres con espacios, caracteres no válidos o duplicados se adaptan automáticamente "
                "(puedes retocarlos o pulsar Traer directamente)."
            )
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color:{estilo.TINTA_2}; font-size:{estilo.T_PEQUENA}px;")
            hl.addWidget(tag, 0, Qt.AlignmentFlag.AlignTop)
            hl.addWidget(desc, 1)
            layout.addWidget(w_ley)
            w_ley.setVisible(not plegado)
            tabla._leyenda = w_ley
            self.leyenda_auto = w_ley
        alto = estilo.ESCALAS[self.controlador.panel.escala]["ALTO_CONTROL"]
        titulo.setFixedHeight(alto)
        todas.setFixedHeight(alto)
        self.tablas.append((tabla, filas))
        if self.isVisible():
            caja.show()

    def _poner_filas(self, tabla, filas):
        from .traer_celdas import ROL_AUTO
        self.cambiando = True
        for row, fila in enumerate(filas):
            usar = QTableWidgetItem("ya traída" if fila.ya else "")
            usar.setFlags(Qt.ItemFlag.ItemIsEnabled)
            usar.setToolTip("ya traída" if fila.ya else "Traer esta señal")
            usar.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            usar.setForeground(QColor(estilo.TINTA_2))
            if not fila.ya:
                from .entradas_salidas import _CasillaCentrada
                casilla = _CasillaCentrada()
                casilla.setChecked(fila.marcada)
                casilla.toggled.connect(lambda on, fila=fila: self.cambiar_marcada(fila, on))
                tabla.setCellWidget(row, 0, casilla)
            tabla.setItem(row, 0, usar)
            senal = QTableWidgetItem(nombre_visible(fila.senal))
            senal.setFlags(Qt.ItemFlag.ItemIsEnabled)
            senal.setForeground(QColor(estilo.TINTA_2))
            senal.setToolTip(nombre_visible(fila.senal))
            tabla.setItem(row, 1, senal)
            nombre_item = QTableWidgetItem(fila.nombre)
            nombre_item.setData(ROL_AUTO, bool(fila.cambiado and not fila.ya))
            if fila.ya:
                nombre_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            tabla.setItem(row, 2, nombre_item)
            es_entrada = fila.senal["kind"].lower() == "input"
            sentido = QTableWidgetItem("Entrada" if es_entrada else "Salida")
            sentido.setFlags(Qt.ItemFlag.ItemIsEnabled)
            sentido.setForeground(QColor(estilo.ACENTO_OSCURO if es_entrada else estilo.SIMULACION))
            sentido.setToolTip("Entrada (sensor)" if es_entrada else "Salida (actuador)")
            tabla.setItem(row, 3, sentido)
            etiquetas_tipo = {"bit": "Booleana", "int": "Entera", "float": "Decimal"}
            tipo = QTableWidgetItem(etiquetas_tipo[fila.senal["type"].lower()])
            tipo.setFlags(Qt.ItemFlag.ItemIsEnabled)
            tipo.setToolTip(tipo.text())
            tabla.setItem(row, 4, tipo)
        self.cambiando = False

    @staticmethod
    def plegar(titulo, tabla, on):
        tabla.setVisible(on)
        if hasattr(tabla, "_leyenda"):
            tabla._leyenda.setVisible(on)
        titulo.plegado = not on
        titulo.setAccessibleName(f"{titulo.text()}: {'plegado' if titulo.plegado else 'desplegado'}")
        titulo.update()
        if on and getattr(tabla, "_repartir", None) is not None:
            QTimer.singleShot(0, tabla, tabla._repartir)

    def marcar(self, tabla, filas):
        marcar = not all(f.marcada or f.ya for f in filas)
        self.cambiando = True
        for row, fila in enumerate(filas):
            if not fila.ya:
                fila.marcada = marcar
                tabla.cellWidget(row, 0).setChecked(marcar)
        self.cambiando = False
        self.pintar()

    def cambiar_marcada(self, fila, on):
        fila.marcada = on
        if not self.cambiando:
            self.pintar()

    def editar(self, tabla, filas, item):
        if self.cambiando:
            return
        fila = filas[item.row()]
        if item.column() == 0:
            fila.marcada = item.checkState() == Qt.CheckState.Checked
        elif item.column() == 2:
            fila.nombre = item.text().strip()
            fila.cambiado = True
        self.pintar()

    def pintar(self):
        from .traer_celdas import ROL_AUTO
        self.propuestas.validar()
        self.cambiando = True
        for tabla, filas in self.tablas:
            for row, fila in enumerate(filas):
                item = tabla.item(row, 2)
                color = estilo.ERROR if fila.motivo else estilo.OK if fila.cambiado else estilo.TINTA
                if fila.ya:
                    color = estilo.TINTA_2
                item.setForeground(QColor(color))
                fondo = QBrush(QColor(estilo.NOMBRE_PENDIENTE_FONDO)) if fila.motivo else QBrush()
                item.setBackground(fondo)
                item.setData(ROL_AUTO, bool(fila.cambiado and not fila.ya))
                item.setData(Qt.ItemDataRole.StatusTipRole, "unir a la variable existente" if fila.existente else "")
                item.setToolTip(fila.motivo or ("Unir a la variable existente" if fila.existente else fila.nombre))
        self.cambiando = False
        numero = len(self.propuestas.elegidas())
        pendientes = self.propuestas.pendientes()
        sufijo = f" ({pendientes} por corregir)" if pendientes else ""
        self.b_traer.setText(f"Traer {numero}{sufijo}")
        self.b_traer.setEnabled(numero > 0 and pendientes == 0)
        from .avisos_nombres import resumen_nombres
        pendientes = [f for f in self.propuestas.elegidas() if f.motivo]
        self.motivos.setText(resumen_nombres(pendientes))
        detalle = "\n".join(f"{f.nombre}: {f.motivo}" for f in pendientes)
        self.motivos.setToolTip(f"{self.motivos.text()}\n{detalle}" if detalle else "")
        self.motivos.setVisible(bool(pendientes))
        self.b_corregir.setVisible(bool(pendientes))
        alto = estilo.ESCALAS[self.controlador.panel.escala]["ALTO_CONTROL"]
        for boton in self.findChildren(QPushButton):
            boton.setFixedHeight(alto)

    def corregir_nombres(self):
        from .avisos_nombres import corregir_nombres
        corregir_nombres(self.propuestas)
        self.cambiando = True
        for tabla, filas in self.tablas:
            for row, fila in enumerate(filas):
                tabla.item(row, 2).setText(fila.nombre)
        self.cambiando = False
        self.pintar()

    def importar(self):
        self.resumen = traer(self.propuestas, self.controlador.historial)
        self.controlador.panel.config = self.propuestas.config
        self.controlador.panel.actualizar(self.controlador.edicion.ed.model)
        self.controlador.aplicar()
        self.controlador.edicion.cambia()
        self.controlador.panel.estado.setText(self.resumen)
        panel = self.controlador.panel
        self.accept()
        if panel.config.modo == "directo" and panel.b_conectar.isEnabled():
            panel.b_conectar.click()
        self.controlador.mostrar_resumen(self.resumen)
