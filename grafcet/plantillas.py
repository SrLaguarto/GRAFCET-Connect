"""Representación transportable de plantillas: milímetros, origen superior izquierdo."""
import copy
import math


def numero(valor):
    if isinstance(valor,bool):raise ValueError('Medida de plantilla no válida')
    try:n=float(valor)
    except (TypeError,ValueError,OverflowError) as exc:raise ValueError('Medida de plantilla no válida') from exc
    if not math.isfinite(n) or abs(n)>1e7:raise ValueError('Medida de plantilla fuera de rango')
    return n


def validar_plantilla(datos):
    if datos is None:return None
    p=copy.deepcopy(datos)
    if not isinstance(p,dict) or p.get('version')!=1:raise ValueError('Plantilla no compatible')
    def vector(v,n):
        if not isinstance(v,(list,tuple)) or len(v)!=n:raise ValueError('Coordenadas de plantilla no válidas')
        return [numero(x) for x in v]
    p['size']=vector(p.get('size'),2)
    if any(not 10<=n<=2000 for n in p['size']):raise ValueError('Tamaño de plantilla fuera de rango (10–2000 mm)')
    if not isinstance(p.get('primitives'),list) or len(p['primitives'])>100000:raise ValueError('Primitivas de plantilla no válidas')
    for t in p['primitives']:
        if not isinstance(t,dict):raise ValueError('Primitiva de plantilla no válida')
        k=t.get('kind')
        if k=='line':t['points']=vector(t.get('points'),4)
        elif k=='arc':
            t['center']=vector(t.get('center'),2)
            for n in ('radius','start','span'):t[n]=numero(t[n])
            if t['radius']<=0:raise ValueError('Radio no válido')
        elif k=='path':
            if not isinstance(t.get('points'),list) or not 2<=len(t['points'])<=100000:raise ValueError('Curva no válida')
            t['points']=[vector(v,2) for v in t['points']]
        elif k=='text':
            for n in ('x','y','height','rotation'):t[n]=numero(t.get(n,0))
            if not .05<=t['height']<=500:raise ValueError('Altura de texto fuera de rango')
            if not isinstance(t.get('text'),str) or len(t['text'])>20000:raise ValueError('Texto no válido')
            if t.get('align','left') not in ('left','center','right') or t.get('valign','baseline') not in ('top','middle','bottom','baseline'):raise ValueError('Alineación no válida')
            for n in ('field','suggest','font'):
                if n in t and not isinstance(t[n],str):raise ValueError('Campo de texto no válido')
            if 'box' in t:t['box']=vector(t['box'],4)
            for n in ('width','stretch','max_height'):
                if n in t:
                    t[n]=numero(t[n])
                    if t[n]<=0:raise ValueError('Anchura de texto no válida')
        else:raise ValueError('Primitiva de plantilla desconocida')
        if 'weight' in t:
            t['weight']=numero(t['weight'])
            if not 0<t['weight']<=10:raise ValueError('Grosor de plantilla no válido')
    for k in ('zone','detected_zone'):
        if p.get(k) is not None:
            x,y,w,h=p[k]=vector(p[k],4)
            if x<0 or y<0 or w<5 or h<5 or x+w>p['size'][0]+.01 or y+h>p['size'][1]+.01:raise ValueError('La zona de dibujo debe quedar dentro de la hoja')
    for k in ('inner_frame','title_box'):
        if k in p:p[k]=vector(p[k],4)
    if 'margin_mm' in p:p['margin_mm']=numero(p['margin_mm'])
    fondo=p.get('background')
    if fondo is not None:
        if not isinstance(fondo,dict) or fondo.get('kind') not in ('png','svg') or not isinstance(fondo.get('data'),str):raise ValueError('Fondo de plantilla no válido')
        if len(fondo['data'])>80_000_000:raise ValueError('Fondo de plantilla demasiado grande')
    return p


def serializable(valor):
    """Los reales se guardan como cadenas, como exige el JSON canónico del proyecto."""
    if isinstance(valor,float):return format(valor,'.17g')
    if isinstance(valor,dict):return {k:serializable(v) for k,v in valor.items()}
    if isinstance(valor,(list,tuple)):return [serializable(v) for v in valor]
    return valor
