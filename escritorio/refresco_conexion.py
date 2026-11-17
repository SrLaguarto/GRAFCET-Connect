"""Presentación incremental de la conexión; la red sigue en el trabajador del coordinador."""
from copy import deepcopy
from time import perf_counter


class RefrescoConexion:
    def __init__(self, ventana):
        self.w = ventana
        self.estado = None
        self.ocupacion = None
        self.tiempos = None
        self.tablas = None

    def actualizar(self):
        w = self.w
        m = w.modbus
        ahora = perf_counter()
        arrastrando = w.edicion is not None and w.edicion.arrastre is not None
        periodo = .2 if arrastrando else .1
        if m.activo and ahora - w._ultimo_refresco_modbus < periodo:
            return
        w._ultimo_refresco_modbus = ahora
        p = w.panel_es
        estado = (m.estado, m.mensaje, p.escala, p.letra)
        if estado != self.estado:
            self.estado = estado
            w._recordar_conexion()
            p.mostrar_estado(m.estado, m.mensaje)
        if not m.activo:
            w._sincronizar_es()
        self._catalogo()
        ocupacion = (m.activo, p.directa.revision_dibujo, p.config.modo)
        if ocupacion != self.ocupacion:
            self.ocupacion = ocupacion
            p.ocupado(m.activo)
        tiempos = (m.medidas, m.ultima_parada)
        if tiempos != self.tiempos:
            self.tiempos = deepcopy(tiempos)
            p.mostrar_tiempos(*tiempos)
        p.mostrar_redondeos(m.adaptador.redondeos if m.adaptador else {})
        if w.modo == "simular" and w.paginas_es.currentIndex() == 0:
            w.refrescar()
        elif m.adaptador is not None:
            p.mostrar_muestra(m.muestra, m.adaptador.entradas, m.escritos,
                             getattr(m.adaptador, "salidas_control", []))

    def _catalogo(self):
        m = self.w.modbus
        # Preparar un catálogo o un mapa publica estructuras de Python desde el trabajador.
        # Se leen después de completar la petición; ningún QWidget pasa a ese hilo.
        if m.futuro is not None and m.fase in ("inicio", "mapa") and not m.futuro.done():
            return
        self.w.panel_es.directa.refrescar_catalogo(m.cliente)

    def tablas_cambiadas(self, modelo, estado):
        if self.w.panel_es.config.modo != "directo":
            return True
        firma = (id(modelo), estado.get("outputs"), estado.get("values"),
                 estado.get("temporal"), self.w._escala)
        if firma == self.tablas:
            return False
        self.tablas = deepcopy(firma)
        return True
