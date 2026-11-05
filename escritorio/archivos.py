"""Operaciones del archivo único .grafnet de la ventana."""
from pathlib import Path
from PySide6.QtWidgets import QFileDialog,QMessageBox
from conexion.configuracion import ARCHIVO
from grafcet.diagnostics import DiagnosticError
from . import sello
from .propiedades_archivo import autor_para_guardar
from .proyecto_archivo import abrir_grafnet,guardar_grafnet


class ArchivosProyecto:
    def _leer_grafnet_gui(self,ruta):
        return abrir_grafnet(ruta,sello.CLAVE,sello.POLITICA_SELLO,None if sello.DESARROLLO else sello.CLAVE_DESARROLLO)

    def guardar_como(self):
        if getattr(self,"solo_lectura",False):return False
        e=self.edicion
        if e is None or self._variables_sin_nombre():return False
        actual=getattr(e,'archivo',None)
        from .carpetas import asegurar_carpetas,nombre_proyecto
        try:inicial=actual or asegurar_carpetas()['grafcet']/nombre_proyecto(e.titulo)
        except OSError as exc:QMessageBox.warning(self,'Guardar proyecto',str(exc));return False
        ruta,_=QFileDialog.getSaveFileName(self,'Guardar proyecto como',str(inicial),'Proyecto GRAFCET Connect (*.grafnet)')
        if not ruta:return False
        destino=Path(ruta)
        if destino.suffix.lower()!='.grafnet':
            destino=destino.with_name(destino.name+'.grafnet')
            if destino.exists() and QMessageBox.question(self,'Sobrescribir proyecto',f'{destino.name} ya existe. ¿Sobrescribirlo?')!=QMessageBox.StandardButton.Yes:return False
        return self._guardar_archivo(destino)

    def guardar_proyecto(self):
        if getattr(self,"solo_lectura",False):return False
        e=self.edicion
        archivo=getattr(e,'archivo',None)
        return self._guardar_archivo(archivo) if archivo else self.guardar_como()

    def _guardar_archivo(self,destino):
        if getattr(self,"solo_lectura",False):return False
        if hasattr(self,"panel_planos"):self.panel_planos.aplicar()
        e=self.edicion
        if e is None or self._variables_sin_nombre():return False
        try:
            config=self._configuracion_para_guardar(e.ed.model)
            archivo=guardar_grafnet(destino,e.proyecto(),sello.CLAVE if e.puede_firmarse else None,e.ruta,
                                    lambda raiz:config.guardar(raiz/ARCHIVO,e.ed.model),
                                    e.info_archivo,autor_para_guardar(e))
        except (OSError,ValueError,DiagnosticError) as exc:
            QMessageBox.warning(self,'Guardar proyecto',f'No se pudo guardar:\n\n{exc}');return False
        self._adoptar_archivo(e,archivo)
        e.ed.dirty=False
        self._recordar_parametros(config);self._titulo_ventana()
        if self.modo=="editar":self.titulo.setText(e.titulo)
        self.statusBar().showMessage(f'Proyecto guardado en {destino}',10000)
        return True

    @staticmethod
    def _adoptar_archivo(e,archivo):
        e.contenedor=archivo;e.archivo=archivo.archivo;e.info_archivo=dict(archivo.info);e.autor_archivo=None
        e.puede_firmarse=archivo.firma=='valida'  # un archivo abierto sin firma válida sigue sin firma al guardarlo
        e.ruta=archivo.raiz;e.proyecto_base=archivo.proyecto
