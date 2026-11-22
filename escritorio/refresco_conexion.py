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
        # E7: lo que el hilo de control puede estar cambiando se copia con el candado cogido; después se pinta sin él (nunca se retiene en un dibujo)
        with w.candado:
            copia = {"estado": m.estado, "mensaje": m.mensaje, "activo": m.activo, "medidas": dict(m.medidas),
                     "parada": deepcopy(m.ultima_parada), "muestra": dict(m.muestra), "escritos": dict(m.escritos),
                     "adaptador": m.adaptador is not None,
                     "redondeos": dict(m.adaptador.redondeos) if m.adaptador is not None else {},
                     "entradas": list(m.adaptador.entradas) if m.adaptador is not None else [],
                     "salidas_control": list(getattr(m.adaptador, "salidas_control", [])) if m.adaptador is not None else []}
            self._catalogo()
        estado = (copia["estado"], copia["mensaje"], p.escala, p.letra)
        if estado != self.estado:
            self.estado = estado
            w._recordar_conexion()
            p.mostrar_estado(copia["estado"], copia["mensaje"])
        if not copia["activo"]:
            w._sincronizar_es()
        ocupacion = (copia["activo"], p.directa.revision_dibujo, p.config.modo)
        if ocupacion != self.ocupacion:
            self.ocupacion = ocupacion
            p.ocupado(copia["activo"])
        tiempos = (copia["medidas"], copia["parada"])
        if tiempos != self.tiempos:
            self.tiempos = tiempos
            p.mostrar_tiempos(*tiempos)
        p.mostrar_redondeos(copia["redondeos"])
        if w.modo == "simular" and w.paginas_es.currentIndex() == 0:
            w.refrescar()
        elif copia["adaptador"]:
            p.mostrar_muestra(copia["muestra"], copia["entradas"], copia["escritos"], copia["salidas_control"])

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
        self.tablas = firma  # (sin copia: `Vista.state()` da objetos nuevos cada vez y nadie los cambia después)
        return True
