import os,sys,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_QPA_FONTDIR']='C:/Windows/Fonts'
sys.path.insert(0,str(Path.cwd()))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from escritorio.ventana import Ventana
app=QApplication([])
out=Path('artifacts/rediseno_visual_v2');out.mkdir(parents=True,exist_ok=True)
def settle():
 for _ in range(12):app.processEvents()
for width,height in ((1366,768),(1000,600)):
 with tempfile.TemporaryDirectory() as tmp:
  w=Ventana(QSettings(tmp+'/ui.ini',QSettings.Format.IniFormat),Path(tmp)/'recuperacion')
  w.resize(width,height);w.cargar_ejemplo('temporizada');w.show();settle()
  def snap(name):
   settle();assert (w.width(),w.height())==(width,height),(name,w.size())
   w.grab().save(str(out/f'{name}-{width}x{height}.png'))
  w.diagrama.ajustar();snap('editor')
  w.edicion.seleccionar([w.edicion.M['transitions'][0]['id']]);settle();w.diagrama.ajustar();snap('propiedades')
  w.paleta.scrollToBottom();settle();w.paleta.grab().save(str(out/f'paleta-{width}x{height}.png'))
  w._mostrar_pagina(True);snap('es')
  w.panel_es.abrir_configuracion();settle()
  w.panel_es.dialogo_config.grab().save(str(out/f'configuracion-{width}x{height}.png'));w.panel_es.dialogo_config.hide()
  from dataclasses import replace
  cfg=replace(w.panel_es.config,canales={a:{'offset':0,'cantidad':24 if a in ('discrete','coil') else 0} for a in ('discrete','coil','input-register','holding')})
  w.panel_es.cargar(w.panel_es.doc,cfg);snap('es-24canales')
  w.t_auto.stop();w.edicion=None;w.deleteLater();settle()
print(out.resolve())

# Dos programadores simultáneos: reutiliza el escenario de la prueba existente.
sys.path.insert(0, str(Path.cwd() / 'tests'))
from test_editor_escritorio import Interfaz
Interfaz.setUpClass()
for ancho, alto in ((1366, 768), (1000, 600)):
    caso = Interfaz('test_SEDI122_opciones_sin_controles_cortados_ni_solapes')
    caso.setUp()
    try:
        e, ids, ts, aid = caso._con_accion_por_evento()
        ventana = caso.w
        ventana.resize(ancho, alto)
        ventana.show()
        ventana.editar_accion(ids['0'], aid)
        settle()
        assert (ventana.width(), ventana.height()) == (ancho, alto)
        ventana.diagrama.ajustar()
        settle()
        ventana.grab().save(str(out / f'accion-evento-{ancho}x{alto}.png'))
    finally:
        caso.tearDown()
