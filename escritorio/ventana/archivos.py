"""Archivos: abrir, guardar, ejemplos, firma y la fuente del proyecto (lo de «Guardar como» y la carpeta de proyectos sigue en `escritorio/archivos.py`)."""
from __future__ import annotations

import copy
from ..edicion import Edicion, aviso_valores_iniciales, quitar_valores_iniciales
from ..mensajes import amable
from pathlib import Path
from typing import Any
from PySide6.QtWidgets import QFileDialog, QMessageBox
from conexion.configuracion import Configuracion
from grafcet.diagnostics import DiagnosticError
from grafcet.examples import EJEMPLOS
from grafcet.persistence import open_model
from grafcet.view import Vista, auto_layout, layout_from_presentation
from .constantes import ERRORES, TEXTOS_FIRMA, TITULO


class Archivos:
    """Archivos: abrir, guardar, ejemplos, firma y la fuente del proyecto (lo de «Guardar como» y la carpeta de proyectos sigue en `escritorio/archivos.py`). Sin estado propio: usa los atributos de `Ventana` (la fachada) y llama a los demás métodos a través de `self`."""

    # -- fuentes: ejemplo o modelo guardado ------------------------------------------------------------
    def cargar_ejemplo(self, key: str) -> None:
        if not self._salir_de_edicion():
            return
        self.fuente = {"tipo": "ejemplo", "clave": key}
        self._cargar()

    def abrir_ruta(self, ruta: Path) -> bool:
        contenedor = None
        try:
            ruta=Path(ruta)
            if ruta.suffix.lower()!='.grafnet':
                raise ValueError('Abre un proyecto .grafnet con sello válido. No se admiten carpetas ni archivos JSON sueltos.')
            contenedor=self._leer_grafnet_gui(ruta)
            op=open_model(contenedor.raiz)
        except (DiagnosticError, OSError, ValueError) as exc:
            if contenedor is not None:contenedor.cerrar()
            QMessageBox.warning(self, TITULO, f"No se pudo abrir {ruta}:\n\n{exc}")
            return False
        if not op.executable:
            if contenedor is not None:contenedor.cerrar()
            QMessageBox.warning(self, TITULO, "El modelo no se puede simular:\n\n"
                                + "\n".join(amable(d.message, d.code) for d in op.diagnostics))
            return False
        if not self._salir_de_edicion():
            if contenedor is not None:contenedor.cerrar()
            return False
        quitadas = quitar_valores_iniciales(op.doc)  # P-IMP-117: ninguna variable declara un valor inicial fuera del grafcet
        layout = layout_from_presentation(op.presentations[0]) if op.presentations else {}
        avisos = [str(d) for d in op.diagnostics]
        ayuda = (f"Modelo abierto de {ruta}. "
                 + ("Posiciones de su presentación." if layout else "Sin presentación: colocado automáticamente.")
                 + (" Avisos: " + "; ".join(avisos) if avisos else ""))
        proyecto = contenedor.raiz
        self.fuente = {"tipo": "fichero", "ruta": ruta, "doc": op.doc, "layout": layout, "titulo": op.title,
                       "ayuda": ayuda, "raiz": proyecto, "presentacion": op.presentations[0] if op.presentations else None}
        self.fuente["contenedor"] = contenedor
        self._cargar()
        if quitadas:
            if self.edicion is not None:
                self.edicion.ed.dirty = True  # guardar escribe el arreglo; abrir solo no firma ni guarda nada
            QMessageBox.information(self, TITULO, aviso_valores_iniciales(quitadas))
        self._recordar_carpeta(ruta)
        return True

    def abrir(self) -> None:
        try:inicial=str(self.carpeta_proyectos())
        except OSError as exc:QMessageBox.warning(self,"Abrir proyecto",str(exc));return
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", inicial, "Proyecto GRAFCET Connect (*.grafnet)")
        if ruta:
            self.abrir_ruta(Path(ruta))

    def _cargar(self) -> None:
        """Carga la fuente (ejemplo, modelo o lo que se edita) y deja el programa en Pausa: parado y editable, y sin estado
        (como tras Play y Pausa: ni etapas activas ni valores en las tablas; Play arranca la sesión). La conexión Modbus, si
        la hay, no se cierra: se conserva el TCP y las salidas pasan a 0 (Pausa)."""
        self._generacion_encuadre = getattr(self, "_generacion_encuadre", 0) + 1
        with self.candado:
            self.modbus.pausar()
        self._marcar_play(False)
        self._aviso_inestable_sesion = None
        self._avisos_ejecucion = []
        if self._errores_auto:
            self._marcar_errores(False, False)  # (lo marcó un Play fallido: otra fuente, otro aviso; lo que marcó el usuario se queda)
        f = self.fuente
        try:
            if f["tipo"] == "ejemplo":
                title, help_text, build = EJEMPLOS[f["clave"]]
                self.v = Vista(f["clave"], title, help_text, build, self.options)
            elif f["tipo"] == "editor":  # lo que se está editando, tal como está: cada simulación es una ejecución nueva
                e = self.edicion
                self.v = Vista(e.ed.model["id"], e.titulo, "Simulación del grafcet que se está editando.",
                               lambda: (copy.deepcopy(e.ed.model), e.layout()), self.options, presentation=e.ed.presentation)
            else:
                self.v = Vista(f["ruta"].stem, f["titulo"], f["ayuda"], lambda: (f["doc"], f["layout"]), self.options,
                               presentation=f.get("presentacion"))
        except ERRORES as exc:
            QMessageBox.warning(self, TITULO, f"No se pudo preparar la simulación:\n\n{exc}")
            return
        if f["tipo"] != "editor":
            self._ayuda = self.v.model["help"]
            self._proyecto = ("ejemplo", f["clave"]) if f["tipo"] == "ejemplo" else ("fichero", str(f["ruta"]))
        self.setWindowTitle(f"{self.v.model['title']} — {TITULO}")
        self.diagrama.ajustar()
        self._entradas()
        if self.edicion is None or f["tipo"] != "editor":  # siempre se abre editable: Play simula una copia compilada
            self._establecer_edicion(self._edicion_desde_fuente())
        self.solo_lectura = f["tipo"]=="ejemplo" or (f["tipo"]=="editor" and getattr(self,"solo_lectura",False))
        self.modo = "editar"
        self._cargar_config_modbus()
        self._poner_modo()
        self._sin_estado()  # la Vista nace con la sesión en la situación inicial: en Pausa no se enseña nada de ella
        self.refrescar()
        if not self.modbus.activo:
            self.rt.stop()

    def _indicar_firma(self, e) -> None:
        """Indicación permanente en la barra de estado si el archivo abierto no tiene la firma de esta versión."""
        firma = getattr(getattr(e, "contenedor", None), "firma", "valida")
        texto, ayuda = TEXTOS_FIRMA.get(firma, ("", ""))
        self.l_firma.setText(texto)
        self.l_firma.setToolTip(ayuda)
        self.l_firma.setVisible(bool(texto))

    def _titulo_ventana(self) -> None:
        e = self.edicion
        self._indicar_firma(e)
        if hasattr(self,"panel_planos"):
            if self.paginas_es.currentIndex()==2 and self.panel_planos.origen is not e and not self.panel_planos.cargando:self.panel_planos.mostrar()
            else:self.panel_planos.actualizar_titulo()
        if e is not None:
            nombre = getattr(e,"archivo",None)
            nombre = nombre.name if nombre else e.titulo
            self.setWindowTitle(f"{nombre}{' *' if e.ed.dirty else ''}{' (ejemplo · solo lectura)' if getattr(self,'solo_lectura',False) else ' (editando)' if self.modo == 'editar' else ''} — {TITULO}")

    def _salir_de_edicion(self) -> bool:
        """Antes de cargar otro modelo: si hay cambios sin guardar, pregunta. Quien carga sustituye la edición en curso."""
        if hasattr(self,"panel_planos"):self.panel_planos.aplicar()
        e = self.edicion
        if e is not None and e.ed.dirty:
            r = QMessageBox.question(self, TITULO, f"«{e.titulo}» tiene cambios sin guardar. ¿Guardarlos?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                     | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel or (r == QMessageBox.StandardButton.Save and not self.guardar()):
                return False
        return True

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        if self._salir_de_edicion():
            self._transicion_ui = True
            self.a_ejecutar.setChecked(False)
            self.rt.stop()
            self.ciclo.parar()  # el hilo de control antes que el cierre del coordinador
            with self.candado:
                self.modbus.cerrar()
            event.accept()
        else:
            event.ignore()

    def nuevo(self) -> None:
        if not self._salir_de_edicion():
            return
        self._empezar_edicion(Edicion.nuevo())
        self._cargar_config_modbus(self.edicion.ed.model)

    def _edicion_desde_fuente(self) -> Edicion:
        """Copia editable de lo que se está simulando (un ejemplo o un modelo abierto)."""
        f = self.fuente
        if f["tipo"] == "editor":
            return Edicion.desde(self.v.doc, auto_layout(self.v.doc), self.v.model["title"])
        if f["tipo"] == "ejemplo":
            title, _, build = EJEMPLOS[f["clave"]]
            m, layout = build()
            return Edicion.desde(m.doc, layout, title)
        e=Edicion.desde(f["doc"], f["layout"], f["titulo"], f.get("raiz"), f.get("presentacion"))
        if f.get("contenedor") is not None:self._adoptar_archivo(e,f["contenedor"])
        return e

    def _variables_sin_nombre(self) -> bool:
        """Si hay filas de variable sin nombre (solo de la interfaz): el aviso, el parpadeo de la fila y True; no se
        puede simular ni guardar con ellas."""
        if self.edicion is None or not self.variables.sin_nombre():
            return False
        self.edicion.mensaje = self.variables.avisar_sin_nombre()
        self.edicion.cambiado.emit()
        return True

    def _configuracion_para_guardar(self, doc: dict[str, Any]) -> Configuracion:
        if not getattr(self.panel_es,"conectado",False):
            self.panel_es.actualizar(doc)
            config = self.panel_es.obtener()
        else:
            # Guardar no cambia el mapa ni la lectura que están en uso por una conexión viva.
            config = copy.deepcopy(self.panel_es.config)
            config.quitar_obsoletas(doc)
            config.modelo = doc["id"]
            config.validar(doc)
        return config

    # -- guardar ------------------------------------------------------------------------------
    def guardar(self) -> bool:
        return self.guardar_proyecto()

    def guardar_en(self, destino: Path) -> None:
        if Path(destino).suffix.lower()!='.grafnet':
            raise ValueError('El proyecto debe guardarse como archivo .grafnet')
        if not self._guardar_archivo(destino):raise ValueError('No se guardó el proyecto')
