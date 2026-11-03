"""Ajustes de láminas en la presentación; no contienen semántica del GRAFCET."""
import copy
import math

FORMATOS = {'A4':(210.0,297.0),'A3':(297.0,420.0),'A2':(420.0,594.0),'A1':(594.0,841.0),'A0':(841.0,1189.0),'A5':(148.0,210.0)}
CAMPOS = ('titulo','proyecto','autor','centro','fecha','revision','escala','hoja','libre','comprobado','fecha_comprobado','firma_autor','firma_comprobado','numero','sustituye','sustituido_por')


def ajustes_lamina(datos=None):
    d={'version':1,'formato':'A4','orientacion':'vertical','margen_mm':10.0,
       'modo':'escala','escala':1.0,'unidad_mm':25.4/96,'con_estado':False,
       'plantilla':None,'offset_mm':[0.,0.],
       'campos':{k:('{n} de {m}' if k=='hoja' else '') for k in CAMPOS}}
    if datos is not None:
        if not isinstance(datos,dict):raise ValueError('Ajustes de lámina no válidos')
        if not isinstance(datos.get('campos',{}),dict):raise ValueError('Campos del cajetín no válidos')
        d.update(copy.deepcopy(datos))
        d['campos']={**{k:('{n} de {m}' if k=='hoja' else '') for k in CAMPOS},**datos.get('campos',{})}
    if type(d['version']) is not int or d['version']!=1:raise ValueError('Versión de láminas no compatible')
    if not isinstance(d['formato'],str) or d['formato'] not in (*FORMATOS,'Personalizado') or d['orientacion'] not in ('vertical','horizontal') or d['modo'] not in ('ajustar','escala'):
        raise ValueError('Formato, orientación o colocación de lámina no válidos')
    for k,lo,hi in (('margen_mm',5,40),('escala',.01,10000)):
        if isinstance(d[k],bool):raise ValueError('Valor numérico de lámina no válido')
        try:d[k]=float(d[k])
        except (TypeError,ValueError,OverflowError) as exc:raise ValueError('Valor numérico de lámina no válido') from exc
        if not math.isfinite(d[k]) or not lo<=d[k]<=hi:raise ValueError('Valor numérico de lámina fuera de rango')
    if d['unidad_mm'] is not None:
        if isinstance(d['unidad_mm'],bool):raise ValueError('Referencia física de escala no válida')
        try:d['unidad_mm']=float(d['unidad_mm'])
        except (TypeError,ValueError,OverflowError) as exc:raise ValueError('Referencia física de escala no válida') from exc
        if not math.isfinite(d['unidad_mm']) or not .001<=d['unidad_mm']<=100:raise ValueError('Referencia física de escala no válida')
    if not isinstance(d['con_estado'],bool):raise ValueError('Estado de simulación no válido')
    if any(not isinstance(v,str) or len(v)>1000 for v in d['campos'].values()):raise ValueError('Campos del cajetín no válidos')
    from .plantillas import validar_plantilla,numero
    if not isinstance(d['offset_mm'],(list,tuple)) or len(d['offset_mm'])!=2:raise ValueError('Colocación de lámina no válida')
    d['offset_mm']=[numero(v) for v in d['offset_mm']]
    d['plantilla']=validar_plantilla(d['plantilla'])
    if d['formato']=='Personalizado' and d['plantilla'] is None:raise ValueError('El formato personalizado necesita una plantilla')
    return d
