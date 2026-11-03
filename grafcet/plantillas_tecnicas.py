"""Plantillas técnicas propias, en milímetros, sin recursos externos ni dependencias."""
import math
from .plantillas import validar_plantilla

PREDETERMINADAS={'A4_vertical':(210.,297.),'A3_horizontal':(420.,297.),'A3_vertical':(297.,420.)}
ANCHO_CAJETIN,ALTO_CAJETIN=180.,36.


def plantilla_tecnica(ancho,alto,margen=10.):
    w,h,m=float(ancho),float(alto),float(margen)
    # Referencias del responsable: interior 20/10/10/10, banda exterior de 5 mm.
    izquierda,arriba=m+10,m
    interior=[izquierda,arriba,w-izquierda-m,h-2*m]
    if interior[2]<ANCHO_CAJETIN or interior[3]<ALTO_CAJETIN+15:
        raise ValueError('El marco no deja espacio para el cajetín de 180 × 36 mm; reduce el margen o elige una hoja mayor')
    x,y= w-m-ANCHO_CAJETIN,h-m-ALTO_CAJETIN
    p={'version':1,'source':'GrafConnect','size':[w,h],'margin_mm':m,
       'inner_frame':interior,'title_box':[x,y,ANCHO_CAJETIN,ALTO_CAJETIN],
       'zone':None, 'primitives':[],'warnings':[]}
    def linea(a,b,c,d,peso=.25):p['primitives'].append({'kind':'line','points':[a,b,c,d],'weight':peso,'color':'#000000'})
    def rect(a,b,c,d,peso=.35):
        for u,v,q,r in ((a,b,a+c,b),(a+c,b,a+c,b+d),(a+c,b+d,a,b+d),(a,b+d,a,b)):linea(u,v,q,r,peso)
    def texto(s,a,b,altura=2.2,align='left',field=None,width=None):
        t={'kind':'text','text':s,'x':a,'y':b,'height':altura,'rotation':0.,'align':align,'valign':'top','font':'Arial','color':'#000000'}
        if field:t['field']=field
        if width:t['width']=width;t['max_height']=max(2.,altura*2.3)
        p['primitives'].append(t);return t
    rect(izquierda-5,arriba-5,interior[2]+10,interior[3]+10,.18);rect(*interior)
    columnas=max(1,math.ceil(interior[2]/50));filas=max(1,math.ceil(interior[3]/50))
    apaisado=w>h
    for i in range(columnas):
        a=izquierda+i*interior[2]/columnas;centro=a+interior[2]/columnas/2
        texto(str(i+1),centro,arriba-4.2,2.5,'center')
        if apaisado:texto(str(i+1),centro,h-m+.8,2.5,'center')
        if i:
            linea(a,arriba-5,a,arriba,.18)
            if apaisado:linea(a,h-m,a,h-m+5,.18)
    for i in range(filas):
        b=arriba+i*interior[3]/filas;centro=b+interior[3]/filas/2
        texto(chr(65+i),w-m+2.5,centro-1.5,2.5,'center')
        if apaisado:texto(chr(65+i),izquierda-2.5,centro-1.5,2.5,'center')
        if i:
            linea(w-m,b,w-m+5,b,.18)
            if apaisado:linea(izquierda-5,b,izquierda,b,.18)
    # Marcas de centrado de las imágenes de referencia.
    linea(izquierda-5,h/2,izquierda+5,h/2,.4);linea(w-m-5,h/2,w-m+5,h/2,.4)
    if apaisado:linea(w/2,arriba-5,w/2,arriba+5,.4);linea(w/2,h-m-5,w/2,h-m+5,.4)
    rect(x,y,180,36)
    # Cabecera izquierda: 20 + 18 + 22 + 30; razón social en los 90 restantes.
    linea(x,y+18,x+180,y+18)
    for a in (20,38,60,90):linea(x+a,y,x+a,y+18)
    linea(x,y+6,x+90,y+6);linea(x,y+12,x+60,y+12)
    linea(x+20,y+18,x+20,y+36);linea(x+120,y+18,x+120,y+36)
    for b in (24,30):linea(x+120,y+b,x+180,y+b)
    for s,a in (('Fecha',20),('Nombre',38),('Firmas',60)):texto(s,x+a+1,y+1,2.)
    texto('Dibujado',x+1,y+7,2.);texto('Comprobado',x+1,y+13,2.)
    texto('',x+21,y+7,2.,field='fecha',width=16);texto('',x+39,y+7,2.,field='autor',width=20)
    texto('',x+21,y+13,2.,field='fecha_comprobado',width=16);texto('',x+39,y+13,2.,field='comprobado',width=20)
    texto('',x+61,y+7,2.,field='firma_autor',width=28);texto('',x+61,y+13,2.,field='firma_comprobado',width=28)
    texto('Razón social',x+91,y+1,2.);t=texto('',x+135,y+7,3.,'center','centro',88);t['max_height']=9.
    texto('Escala',x+1,y+19,2.);t=texto('',x+10,y+25,2.5,'center','escala',18);t['max_height']=8.
    texto('Nombre plano',x+21,y+19,2.);t=texto('',x+70,y+23,3.,'center','titulo',98);t['max_height']=8.
    for s,b,f in (('Número',18,'numero'),('Sustituye a',24,'sustituye'),('Sustituido por',30,'sustituido_por')):
        texto(s,x+121,y+b+.5,1.7);t=texto('',x+147,y+b+.5,2.,field=f,width=31);t['max_height']=5.
    return validar_plantilla(p)


def sin_rotulos_auxiliares(plantilla):
    """Retira solo los rótulos propios antiguos; no cambia plantillas externas ni la biblioteca."""
    import copy
    p=copy.deepcopy(plantilla)
    if p and p.get('source')=='GrafConnect':
        p['primitives']=[t for t in p['primitives'] if t.get('field') not in ('proyecto','hoja')]
        marco=p.get('inner_frame');cajetin=p.get('title_box');zona=p.get('zone')
        if marco and cajetin and zona:
            x,y,w,h=map(float,marco);anterior=[x+2,y+2,w-4,float(cajetin[1])-y-4]
            if all(abs(float(a)-b)<.01 for a,b in zip(zona,anterior)):p['zone']=None
    return p
