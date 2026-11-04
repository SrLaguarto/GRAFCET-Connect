"""Navegación de la vista: búsqueda compacta, filtros y lista textual, sin editar el modelo."""
from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                              QListWidget, QListWidgetItem, QToolButton, QVBoxLayout, QWidget)

PARCIAL_ITEM = 42


def registros(M, S):
    from .diagrama import SX, H, cajas_parciales, _ancho_accion, _geometria_acciones, parciales_dibujo
    nombres = M.get('names', {})
    activos, virtuales = set(S.get('situation') or []), set(S.get('virtual') or [])
    forzados = {f['target'] for f in S.get('forces', [])}
    salida = []
    def agregar(i, nombre, tipo, parcial, caja, estado=''):
        salida.append(dict(id=i, nombre=str(nombre), tipo=tipo, parcial=parcial or 'g', caja=caja,
                           texto=f'{tipo} {nombre}' + (f' · {estado}' if estado else '') +
                                 (f' · parcial {nombres.get(parcial, parcial)}' if parcial else '')))
    for tipo, clave in (('Etapa', 'steps'), ('Transición', 'transitions'), ('Macroetapa', 'macros')):
        for e in M.get(clave, []):
            estado = []
            if e.get('initial'): estado.append('inicial')
            if (e.get('partial') or 'g') in forzados: estado.append('parcial forzado')
            if e['id'] in activos: estado.append('activa')
            if e['id'] in virtuales: estado.append('transitoria')
            if tipo == 'Transición':
                estado += ['antes: ' + ', '.join(nombres.get(i, i) for i in e.get('pre', [])),
                           'después: ' + ', '.join(nombres.get(i, i) for i in e.get('post', []))]
                if S.get('transitions', {}).get(e['id'], {}).get('forced'): estado.append('parcial forzado')
            agregar(e['id'], e.get('label', nombres.get(e['id'], e['id'])), tipo, e.get('partial'),
                    QRectF(e['x']+SX-H, e['y']-H, 2*H, 2*H), ', '.join(estado))
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


class Navegacion(QFrame):
    def __init__(self, vista):
        super().__init__(); self.vista = vista; self.datos = []; self.actual = None
        self.setAccessibleName('Navegación del GRAFCET')
        self.setAccessibleDescription('Buscar y recorrer elementos; filtrar parciales sin alterar la simulación.')
        fila = QHBoxLayout(self); fila.setContentsMargins(0,0,0,0); fila.setSpacing(4)
        self.buscador = QFrame(); controles = QHBoxLayout(self.buscador); controles.setContentsMargins(0,0,0,0); controles.setSpacing(3)
        self.buscar = QLineEdit(); self.buscar.setFixedWidth(210); self.buscar.setPlaceholderText('Buscar… (Ctrl+F)')
        self.buscar.setAccessibleName('Buscar elemento por nombre')
        self.buscar.setAccessibleDescription('Intro o flecha abajo: siguiente resultado. Mayús+Intro o flecha arriba: anterior. Esc cierra.')
        self.buscar.installEventFilter(self); controles.addWidget(self.buscar)
        self.contador = QLabel('0/0'); self.contador.setMinimumWidth(28); controles.addWidget(self.contador)
        self.anterior = QToolButton(); self.anterior.setText('↑'); self.anterior.setToolTip('Resultado anterior (Mayús+Intro)')
        self.siguiente = QToolButton(); self.siguiente.setText('↓'); self.siguiente.setToolTip('Resultado siguiente (Intro)')
        self.cerrar = QToolButton(); self.cerrar.setText('×'); self.cerrar.setToolTip('Cerrar búsqueda (Esc)')
        for boton in (self.anterior,self.siguiente,self.cerrar):
            boton.setAccessibleName(boton.toolTip()); boton.setAccessibleDescription(boton.toolTip()); controles.addWidget(boton)
        fila.addWidget(self.buscador)
        self.aviso_corto=QToolButton(); self.aviso_corto.setToolTip('Ver filtro y lista de elementos'); fila.addWidget(self.aviso_corto)
        self.aviso_corto.clicked.connect(self.abrir_opciones)
        self.opciones=QDialog(self); self.opciones.setWindowTitle('Navegación del GRAFCET'); self.opciones.resize(600,300)
        l=QVBoxLayout(self.opciones); filtros=QHBoxLayout(); l.addLayout(filtros)
        self.parcial=QComboBox(); self.parcial.addItem('Todos los parciales',None); self.parcial.setAccessibleName('Parcial visible'); filtros.addWidget(self.parcial)
        self.modo=QComboBox(); self.modo.addItem('Atenuar el resto','atenuar'); self.modo.addItem('Mostrar solo este parcial','ocultar'); self.modo.setAccessibleName('Modo de filtro'); filtros.addWidget(self.modo)
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

    def actualizar(self, M, S):
        self.M, self.S = M, S; self.datos = registros(M, S)
        partes = dict.fromkeys([d['parcial'] for d in self.datos if d['parcial']])
        firma = tuple((pid, M.get('names', {}).get(pid, pid)) for pid in partes)
        if firma != getattr(self, '_partes', None):
            anterior = self.parcial.currentData(); self.parcial.blockSignals(True); self.parcial.clear()
            self.parcial.addItem('Todos los parciales', None)
            for pid, nombre in firma: self.parcial.addItem(str(nombre), pid)
            self.parcial.setCurrentIndex(max(0, self.parcial.findData(anterior))); self.parcial.blockSignals(False); self._partes = firma
        self._listar(); self.filtrar()

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

    def _listar(self,*args):
        texto=self.buscar.text().casefold().strip()
        self.resultados=[d for d in self.datos if texto and texto in d['nombre'].casefold()]
        ids=[d['id'] for d in self.resultados]
        self.indice=ids.index(self.actual) if self.actual in ids else (-1 if not ids else 0)
        self.contador.setText(f'{self.indice+1}/{len(ids)}')
        self.contador.setAccessibleName(f'Resultado {self.indice+1} de {len(ids)}')
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
        self.contador.setText(f'{self.indice+1}/{len(self.resultados)}')

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
        for item in self.vista.scene().items():
            fuera = bool(pid and item.data(PARCIAL_ITEM) and item.data(PARCIAL_ITEM) != pid)
            item.setVisible(not (fuera and modo == 'ocultar')); item.setOpacity(.18 if fuera and modo == 'atenuar' else 1)
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
