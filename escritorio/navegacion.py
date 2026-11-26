"""Navegación de la vista: búsqueda compacta, filtros y lista textual, sin editar el modelo."""
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from . import estilo
from .componentes_comunes import CabeceraDialogo, acotar_desplegable
from .estilo_dialogos import aplicar_escala_dialogo

PARCIAL_ITEM = 42


def _icono_lupa() -> QIcon:
    """Icono de lupa de un solo trazo a 2× DPR para la caja de búsqueda."""
    lado = 16
    pm = QPixmap(lado * 2, lado * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(estilo.TINTA_2), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawEllipse(QRectF(2.5, 2.5, 7.5, 7.5))
    p.drawLine(QPointF(8.8, 8.8), QPointF(13.2, 13.2))
    p.end()
    return QIcon(pm)


def registros_base(M):
    """Lo de los registros que solo depende del documento (identificador, nombre, tipo, parcial y caja de cada elemento; de las etapas,
    transiciones y macroetapas, también el propio elemento, para decir su estado): es lo caro y no cambia al simular."""
    from .diagrama import SX, H, cajas_parciales, _ancho_accion, _geometria_acciones, parciales_dibujo
    nombres = M.get('names', {})
    salida = []
    def agregar(i, nombre, tipo, parcial, caja, elemento=None):
        salida.append(dict(id=i, nombre=str(nombre), tipo=tipo, parcial=parcial or 'g', caja=caja, elemento=elemento, enparcial=parcial))
    for tipo, clave in (('Etapa', 'steps'), ('Transición', 'transitions'), ('Macroetapa', 'macros')):
        for e in M.get(clave, []):
            agregar(e['id'], e.get('label', nombres.get(e['id'], e['id'])), tipo, e.get('partial'),
                    QRectF(e['x']+SX-H, e['y']-H, 2*H, 2*H), e)
            if clave == 'steps':
                for a, x, y, w in _geometria_acciones(e['x']+SX, e['y'], e.get('actions', []), e.get('actionLayout', 'fila'))[0]:
                    agregar(a['id'], ''.join(t['t'] for t in a.get('text', [])), 'Acción', e.get('partial'), QRectF(x, y-H, w, 2*H))
    partes = parciales_dibujo(M)
    for b in M.get('bars', []):
        agregar(b['id'], b.get('label', 'Simultaneidad'), 'Barra', partes[b['id']], QRectF(b['x']+SX, b['y'], b['ancho'], 10))
    marcos = cajas_parciales(M)
    for p in M.get('partials', []):
        b = marcos.get(p['id'])
        if b: agregar(p['id'], p['label'], 'Parcial', p['id'], QRectF(b['x0'], b['y0'], b['x1']-b['x0'], b['y1']-b['y0']))
    for a in M.get('draftActions', []):
        if not a.get('etapa'):
            agregar(a['id'], ''.join(t['t'] for t in a.get('text', [])) or '?', 'Acción en borrador', a.get('partial'),
                    QRectF(a['x']+SX, a['y']-H, _ancho_accion(a), 2*H))
    return salida


def registros(M, S, base=None):
    """Los registros de la navegación (uno por elemento, con su texto y su caja). `base` es `registros_base(M)` si ya se calculó."""
    nombres = M.get('names', {})
    activos, virtuales = set(S.get('situation') or []), set(S.get('virtual') or [])
    forzados = {f['target'] for f in S.get('forces', [])}
    salida = []
    for b in (registros_base(M) if base is None else base):
        e, tipo, parcial = b['elemento'], b['tipo'], b['enparcial']
        estado = []
        if e is not None:
            if e.get('initial'): estado.append('inicial')
            if (e.get('partial') or 'g') in forzados: estado.append('parcial forzado')
            if e['id'] in activos: estado.append('activa')
            if e['id'] in virtuales: estado.append('transitoria')
            if tipo == 'Transición':
                estado += ['antes: ' + ', '.join(nombres.get(i, i) for i in e.get('pre', [])),
                           'después: ' + ', '.join(nombres.get(i, i) for i in e.get('post', []))]
                if S.get('transitions', {}).get(e['id'], {}).get('forced'): estado.append('parcial forzado')
        estado = ', '.join(estado)
        salida.append(dict(id=b['id'], nombre=b['nombre'], tipo=tipo, parcial=b['parcial'], caja=b['caja'],
                           texto=f"{tipo} {b['nombre']}" + (f' · {estado}' if estado else '') +
                                 (f' · parcial {nombres.get(parcial, parcial)}' if parcial else '')))
    return salida


class Navegacion(QFrame):
    def __init__(self, vista):
        super().__init__(); self.vista = vista; self.datos = []; self.actual = None
        self.setAccessibleName('Navegación del GRAFCET')
        self.setAccessibleDescription('Buscar y recorrer elementos; filtrar parciales sin alterar la simulación.')
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fila = QHBoxLayout(self); fila.setContentsMargins(0,0,0,0); fila.setSpacing(4)
        self.buscador = QFrame()
        self.buscador.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        controles = QHBoxLayout(self.buscador); controles.setContentsMargins(0,0,0,0); controles.setSpacing(4)
        self.buscar = QLineEdit(); self.buscar.setFixedWidth(210); self.buscar.setPlaceholderText('Buscar elemento… (Ctrl+F)')
        self._accion_lupa = self.buscar.addAction(_icono_lupa(), QLineEdit.ActionPosition.LeadingPosition)
        self.buscar.setAccessibleName('Buscar elemento por nombre')
        self.buscar.setAccessibleDescription('Intro o flecha abajo: siguiente resultado. Mayús+Intro o flecha arriba: anterior. Esc cierra.')
        self.buscar.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO)  # como los botones de al lado: la fila de la cabecera no cambia al abrirlo
        self.buscar.setStyleSheet(f'QLineEdit {{ min-height: 0px; padding: 0 8px 0 4px; }} QLineEdit:focus {{ border: 2px dashed {estilo.FOCO}; padding: 0 7px 0 3px; }}')
        self.buscar.installEventFilter(self); controles.addWidget(self.buscar)
        self.contador = QLabel('')
        self.contador.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.contador.hide()
        controles.addWidget(self.contador)
        self.anterior = QToolButton(); self.anterior.setText('↑'); self.anterior.setToolTip('Resultado anterior (Mayús+Intro)')
        self.siguiente = QToolButton(); self.siguiente.setText('↓'); self.siguiente.setToolTip('Resultado siguiente (Intro)')
        self.cerrar = QToolButton(); self.cerrar.setText('×'); self.cerrar.setToolTip('Cerrar búsqueda (Esc)')
        for boton in (self.anterior,self.siguiente,self.cerrar):
            boton.setAccessibleName(boton.toolTip()); boton.setAccessibleDescription(boton.toolTip()); controles.addWidget(boton)
            boton.setFixedSize(estilo.ALTO_CONTROL_COMPACTO, estilo.ALTO_CONTROL_COMPACTO)  # objetivos táctiles de 32 px
            boton.setStyleSheet(f'QToolButton {{ font-size: 16px; font-weight: 600; border: 1px solid {estilo.BORDE_CONTROL}; border-radius: {estilo.R_CONTROL}px; background: {estilo.SUPERFICIE}; }} '
                                f'QToolButton:hover {{ background: {estilo.HOVER}; }} QToolButton:disabled {{ color: {estilo.DESHABILITADO}; border-color: {estilo.BORDE}; }} '
                                f'QToolButton[tecl="true"]:focus {{ border: 2px dashed {estilo.FOCO}; }}')
        fila.addWidget(self.buscador)
        self.aviso_corto=QToolButton(); self.aviso_corto.setToolTip('Ver filtro y lista de elementos'); fila.addWidget(self.aviso_corto)
        self.aviso_corto.clicked.connect(self.abrir_opciones)
        self.opciones=QDialog(self); self.opciones.setWindowTitle('Navegación del GRAFCET'); self.opciones.resize(600,340)
        aplicar_escala_dialogo(self.opciones)
        raiz_opc=QVBoxLayout(self.opciones); raiz_opc.setContentsMargins(0,0,0,0); raiz_opc.setSpacing(0)
        self.cabecera_opciones=CabeceraDialogo('Navegación del GRAFCET', self.opciones,
                                               subtitulo='Filtra parciales y recorre elementos sin alterar la simulación',
                                               mostrar_cerrar=True)
        self.cabecera_opciones.cerrar_pedido.connect(self.opciones.close)
        raiz_opc.addWidget(self.cabecera_opciones)
        cuerpo_opc=QWidget(self.opciones)
        l=QVBoxLayout(cuerpo_opc); l.setContentsMargins(estilo.E4,estilo.E3,estilo.E4,estilo.E4); l.setSpacing(estilo.E2)
        raiz_opc.addWidget(cuerpo_opc, 1)
        filtros=QHBoxLayout(); filtros.setSpacing(estilo.E2); l.addLayout(filtros)
        self.parcial=QComboBox(); self.parcial.addItem('Todos los parciales',None); self.parcial.setAccessibleName('Parcial visible'); acotar_desplegable(self.parcial); filtros.addWidget(self.parcial)
        self.modo=QComboBox(); self.modo.addItem('Atenuar el resto','atenuar'); self.modo.addItem('Mostrar solo este parcial','ocultar'); self.modo.setAccessibleName('Modo de filtro'); acotar_desplegable(self.modo); filtros.addWidget(self.modo)
        self.b_lista=QToolButton(); self.b_lista.setText('Lista de elementos'); self.b_lista.setCheckable(True); l.addWidget(self.b_lista)
        self.aviso=QLabel(); self.aviso.setWordWrap(True); l.addWidget(self.aviso)
        self.lista=QListWidget(); self.lista.setAccessibleName('Lista estructural de elementos y relaciones')
        self.lista.setAccessibleDescription('Estados y relaciones de cada elemento. Intro selecciona.'); self.lista.hide(); l.addWidget(self.lista)
        self.buscar.textChanged.connect(self._buscar_cambio)
        self.buscar.returnPressed.connect(lambda:self.avanzar(-1 if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier else 1))
        self.anterior.clicked.connect(lambda:self.avanzar(-1)); self.siguiente.clicked.connect(lambda:self.avanzar(1)); self.cerrar.clicked.connect(self.cerrar_busqueda)
        self.lista.itemActivated.connect(self._activar); self.lista.itemClicked.connect(self._activar)
        self.b_lista.toggled.connect(self._listar)
        self.parcial.currentIndexChanged.connect(self.filtrar); self.modo.currentIndexChanged.connect(self.filtrar)
        self.buscador.hide(); self.aviso_corto.hide(); self.hide(); self.resultados=[]; self.indice=-1
        vista.navegacion = self

    @staticmethod
    def _del_estado(S):
        """De lo que da el estado, lo único que usan los registros (`registros`): activas, transitorias, parciales forzados y transiciones forzadas."""
        return (tuple(S.get('situation') or ()), tuple(S.get('virtual') or ()), tuple(f['target'] for f in S.get('forces', [])),
                tuple(i for i, t in (S.get('transitions') or {}).items() if t.get('forced')))

    def actualizar(self, M, S):
        self.M, self.S = M, S
        previo, clave = getattr(self, '_registrado', None), self._del_estado(S)
        if previo is None or previo[0] is not M or previo[1] != clave:  # (los registros solo cambian con el documento o con esto del estado)
            base = previo[2] if previo is not None and previo[0] is M else registros_base(M)  # (y lo caro, solo con el documento)
            self.datos = registros(M, S, base); self._registrado = (M, clave, base)
        partes = dict.fromkeys([d['parcial'] for d in self.datos if d['parcial']])
        firma = tuple((pid, M.get('names', {}).get(pid, pid)) for pid in partes)
        if firma != getattr(self, '_partes', None):
            anterior = self.parcial.currentData(); self.parcial.blockSignals(True); self.parcial.clear()
            self.parcial.addItem('Todos los parciales', None)
            for pid, nombre in firma: self.parcial.addItem(str(nombre), pid)
            self.parcial.setCurrentIndex(max(0, self.parcial.findData(anterior))); self.parcial.blockSignals(False); self._partes = firma
        self._listar(); self.filtrar()

    def escalar(self):
        """Con la escala de ahora (pantalla completa o no): el campo de búsqueda y sus botones miden el alto de control compacto."""
        self.buscar.setFixedHeight(estilo.ALTO_CONTROL_COMPACTO)
        for boton in (self.anterior, self.siguiente, self.cerrar):
            boton.setFixedSize(estilo.ALTO_CONTROL_COMPACTO, estilo.ALTO_CONTROL_COMPACTO)

    def abrir(self):
        self.show(); self.buscador.show(); self.buscar.setFocus(); self.buscar.selectAll()

    def cerrar_busqueda(self):
        self.buscar.clear(); self.buscador.hide(); self.setVisible(bool(self.parcial.currentData())); self.vista.setFocus()

    def abrir_opciones(self):
        self.opciones.show(); self.opciones.raise_(); self.opciones.activateWindow(); self.parcial.setFocus()

    def eventFilter(self,objeto,evento):
        if objeto is self.buscar:
            if evento.type()==QEvent.Type.ShortcutOverride and evento.key()==Qt.Key.Key_Escape:
                evento.accept(); return True
            if evento.type()==QEvent.Type.KeyPress:
                if evento.key()==Qt.Key.Key_Escape: self.cerrar_busqueda(); return True
                if evento.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down): self.avanzar(-1 if evento.key()==Qt.Key.Key_Up else 1); return True
        return super().eventFilter(objeto,evento)

    def _actualizar_contador(self, texto_buscado, total):
        if not texto_buscado:
            self.contador.setText('')
            self.contador.setAccessibleName('Sin búsqueda activa')
            self.contador.hide()
        elif total == 0:
            self.contador.setText('Sin resultados')
            self.contador.setAccessibleName('Sin resultados')
            self.contador.setStyleSheet(
                f'QLabel {{ font-size: 11px; font-weight: 600; color: {estilo.AVISO}; '
                f'background: {estilo.AVISO_FONDO}; border: 1px solid {estilo.AVISO_BORDE}; '
                f'border-radius: 9px; padding: 1px 8px; }}'
            )
            self.contador.show()
        else:
            self.contador.setText(f'{self.indice + 1}/{total}')
            self.contador.setAccessibleName(f'Resultado {self.indice + 1} de {total}')
            self.contador.setStyleSheet(
                f'QLabel {{ font-family: {estilo.FAMILIA_TABULAR}; font-size: {estilo.T_PEQUENA}px; '
                f'color: {estilo.TINTA_2}; background: transparent; border: 0; padding: 0 4px; }}'
            )
            self.contador.show()

    def _listar(self,*args):
        texto=self.buscar.text().casefold().strip()
        self.resultados=[d for d in self.datos if texto and texto in d['nombre'].casefold()]
        ids=[d['id'] for d in self.resultados]
        self.indice=ids.index(self.actual) if self.actual in ids else (-1 if not ids else 0)
        self._actualizar_contador(texto, len(ids))
        for boton in (self.anterior,self.siguiente): boton.setEnabled(bool(ids))
        self.lista.clear()
        if not self.b_lista.isChecked(): self.lista.hide(); return
        for d in self.datos:
            item=QListWidgetItem(d['texto']); item.setData(Qt.ItemDataRole.UserRole,d['id']); self.lista.addItem(item)
        self.lista.show()

    def _buscar_cambio(self,*args):
        self._listar()
        if self.resultados:
            self.indice=0; self._mostrar_resultado()

    def _mostrar_resultado(self):
        self.ir(self.resultados[self.indice]['id'],enfocar=False)
        self._actualizar_contador(self.buscar.text().casefold().strip(), len(self.resultados))

    def avanzar(self,paso):
        if self.resultados:
            self.indice=(self.indice+paso)%len(self.resultados); self._mostrar_resultado()

    def _activar(self, item): self.ir(item.data(Qt.ItemDataRole.UserRole))

    def ir(self, ident, enfocar=True):
        d = next((d for d in self.datos if d['id'] == ident), None)
        if d is None: return
        if self.parcial.currentData() and self.parcial.currentData() != d['parcial']: self.parcial.setCurrentIndex(0)
        self.actual = ident
        if self.vista.controlador: self.vista.controlador.seleccionar([ident])
        else:
            self.vista.seleccion_navegacion = {ident}
            M, S, _, marcados, naranja = self.vista._ultimo
            self.vista.mostrar(M, S, {ident}, marcados, naranja)
        self.vista.encuadrar(d['caja'].adjusted(-45,-45,45,45))
        if enfocar: self.vista.setFocus()
        self.vista.setAccessibleDescription(d['texto']+' · Ctrl+Tab sale del dibujo hacia los controles.')

    def recorrer(self, siguiente):
        pid = self.parcial.currentData()
        datos = [d for d in self.datos if not pid or self.modo.currentData() != 'ocultar' or d['parcial'] == pid]
        if not datos: return False
        seleccion = getattr(self.vista.controlador, 'sel', [])
        actual = seleccion[-1] if seleccion else self.actual
        ids = [d['id'] for d in datos]; k = ids.index(actual) if actual in ids else (-1 if siguiente else 0)
        self.ir(ids[(k+(1 if siguiente else -1)) % len(ids)]); return True

    def filtrar(self, *args):
        pid, modo = self.parcial.currentData(), self.modo.currentData()
        # Sin filtro, ni ahora ni antes, todo ítem de la escena está tal como se creó (visible y opaco): no hay nada que recorrer.
        if pid or getattr(self, '_filtrado', False):
            for item in self.vista.scene().items():
                fuera = bool(pid and item.data(PARCIAL_ITEM) and item.data(PARCIAL_ITEM) != pid)
                item.setVisible(not (fuera and modo == 'ocultar')); item.setOpacity(.18 if fuera and modo == 'atenuar' else 1)
        self._filtrado = bool(pid)
        cantidad = sum(d['parcial'] != pid for d in self.datos) if pid else 0
        self.aviso.setText((f'{cantidad} elementos '+('ocultos' if modo == 'ocultar' else 'atenuados')+' · El filtro solo afecta a la vista; se simula todo el GRAFCET.') if pid else '')
        self.aviso.setVisible(bool(pid))
        self.vista.filtro_parcial = pid if modo == 'ocultar' else None
        c = self.vista.controlador
        if c and pid and modo == 'ocultar':
            permitidos = {d['id'] for d in self.datos if d['parcial'] == pid}
            if any(i not in permitidos for i in c.sel): c.seleccionar([i for i in c.sel if i in permitidos])
        self.aviso_corto.setText(f'Filtro: {cantidad} '+('ocultos' if modo=='ocultar' else 'atenuados'))
        self.aviso_corto.setAccessibleName(self.aviso.text()); self.aviso_corto.setVisible(bool(pid))
        self.setVisible(not self.buscador.isHidden() or bool(pid))
