"""Importadores opcionales; el resultado no depende de las bibliotecas de importación."""
import base64
import ctypes
import math
from pathlib import Path
import re
import unicodedata
from grafcet.plantillas import validar_plantilla

ISO={'A0':(841,1189),'A1':(594,841),'A2':(420,594),'A3':(297,420),'A4':(210,297),'A5':(148,210)}


def formato_iso(w,h):
    for nombre,(a,b) in ISO.items():
        if abs(w-a)<1 and abs(h-b)<1:return nombre,'vertical'
        if abs(w-b)<1 and abs(h-a)<1:return nombre,'horizontal'
    return 'Personalizado','horizontal' if w>=h else 'vertical'


def campo(nombre):
    n=''.join(c for c in unicodedata.normalize('NFD',nombre.lower()) if not unicodedata.combining(c))
    n=re.sub(r'[^a-z0-9]','',n).removeprefix('swtc')
    aliases={'titulo':('titulo','title','drawingtitle','swtitle','descripcion','description'),
      'proyecto':('proyecto','project','projectname'), 'autor':('autor','author','drawnby','dibujado','dibujadopor','swauthor'),
      'centro':('centro','empresa','company','organization'), 'fecha':('fecha','date','swcreateddate','drawndate'),
      'revision':('revision','rev','swrevision'), 'escala':('escala','scale','swsheetscale'),
      'hoja':('hoja','sheet','sheetnumber','swsheet','swsheetnumber','numerodehoja'), 'libre':('libre','free'),'comprobado':('comprobado','comprobadopor','checkedby'),
      'fecha_comprobado':('fechacomprobado','fechadecomprobacion','checkeddate'),
      'firma_autor':('firmaautor','firmadibujado'),'firma_comprobado':('firmacomprobado',),
      'numero':('numero','number','drawingnumber'),'sustituye':('sustituye','sustituyea','replaces'),
      'sustituido_por':('sustituidopor','replacedby')}
    return next((k for k,v in aliases.items() if n in v),'@'+nombre)


def propuestas(p):
    textos=[t for t in p['primitives'] if t['kind']=='text']
    for t in textos:
        s=t['text'].strip()
        if t.get('field'):continue
        if re.fullmatch(r'HOJA\s*\d+\s*(?:DE|/)\s*\d+',s,re.I):t.update(suggest='hoja',suggest_prefix=re.match(r'HOJA\s*',s,re.I)[0])
        elif re.fullmatch(r'ESCALA\s*:?\s*\d+(?:[.,]\d+)?\s*:\s*\d+(?:[.,]\d+)?',s,re.I):t.update(suggest='escala',suggest_prefix=re.match(r'ESCALA\s*:?\s*',s,re.I)[0])
        elif re.fullmatch(r'(Dibujo|Drawing)\s*\d+',s,re.I) and any('TÍTULO' in u['text'].upper() or 'TITULO' in u['text'].upper() or 'TITLE' in u['text'].upper() for u in textos if math.hypot(u['x']-t['x'],u['y']-t['y'])<40):t['suggest']='titulo'
    return p


def zona_detectada(p):
    """Marco rectangular y, conservadoramente, la franja situada sobre el cajetín."""
    hs=[];vs=[]
    for t in p['primitives']:
        if t['kind']!='line':continue
        x,y,u,v=t['points']
        if abs(y-v)<.1:hs.append((min(x,u),max(x,u),y))
        if abs(x-u)<.1:vs.append((x,min(y,v),max(y,v)))
    candidatos=[]
    for a,b,y in hs:
        if b-a<30:continue
        for c,d,v in hs:
            if v-y<30 or abs(a-c)>.2 or abs(b-d)>.2:continue
            if all(any(abs(x-e)<.2 and q<=y+.2 and r>=v-.2 for x,q,r in vs) for e in (a,b)):
                candidatos.append((a,y,b-a,v-y))
    if not candidatos:return
    x,y,w,h=max(candidatos,key=lambda r:r[2]*r[3])
    interiores=[r for r in candidatos if r[0]>x+1 and r[1]>y+1 and r[0]+r[2]<x+w-1 and r[1]+r[3]<y+h-1 and r[2]*r[3]>w*h*.7]
    if interiores:x,y,w,h=max(interiores,key=lambda r:r[2]*r[3])
    p['inner_frame']=[x,y,w,h]
    cajetines=[r for r in candidatos if r[1]>=y+h*.55 and abs(r[0]+r[2]-x-w)<.3 and abs(r[1]+r[3]-y-h)<.3 and r[2]*r[3]<w*h*.4]
    for a,b,v in hs:
        if a>=x-.3 and abs(b-x-w)<.3 and y+h*.55<v<y+h-2 and any(abs(e-a)<.3 and q<=v+.3 and r>=y+h-.3 for e,q,r in vs):
            cajetines.append((a,v,x+w-a,y+h-v))
    if cajetines:p['title_box']=list(max(cajetines,key=lambda r:r[2]*r[3]))
    rect=[max(0,x+2),max(0,y+2),w-4,h-4]
    if rect[2]>=5 and rect[3]>=5:p['detected_zone']=rect


def importar_dxf(ruta,campos=True):
    try:import ezdxf
    except ImportError as exc:raise ValueError('Para importar DXF se necesita ezdxf') from exc
    from ezdxf import bbox,path,units
    try:
        doc=ezdxf.readfile(ruta);espacio=doc.modelspace()
        if not len(espacio):raise ValueError('El DXF está vacío')
        factor=units.conversion_factor(doc.units or units.MM,units.MM)
        caja=bbox.extents(espacio)
        if not caja.has_data:raise ValueError('El DXF no contiene geometría utilizable')
        lo=doc.header.get('$EXTMIN');hi=doc.header.get('$EXTMAX')
        if lo is not None and hi is not None and formato_iso((hi[0]-lo[0])*factor,(hi[1]-lo[1])*factor)[0]!='Personalizado':
            ox,oy=lo[0],lo[1];w,h=(hi[0]-ox)*factor,(hi[1]-oy)*factor
        else:
            ox,oy=caja.extmin.x,caja.extmin.y;w,h=caja.size.x*factor,caja.size.y*factor
        iso,orientacion=formato_iso(w,h)
        if iso!='Personalizado':
            w,h=ISO[iso]
            if orientacion=='horizontal':w,h=h,w
        p={'version':1,'source':'DXF','size':[w,h],'primitives':[],'zone':None,'warnings':[]}
        def xy(v):return [(v[0]-ox)*factor,h-(v[1]-oy)*factor]
        def entidades(es,prof=0):
            if prof>16:raise ValueError('Bloques DXF anidados en exceso')
            for e in es:
                if e.dxftype()=='INSERT':
                    if e.mcount>1:yield from entidades(e.multi_insert(),prof+1);continue
                    yield from e.attribs
                    # Los ATTRIB sustituyen a ATTDEF; los no asignados conservan su valor por defecto.
                    vistos={a.dxf.tag.casefold() for a in e.attribs}
                    virtuales=list(e.virtual_entities(skipped_entity_callback=lambda ent,reason:p['warnings'].append('Entidad de bloque omitida: '+ent.dxftype()+' ('+reason+')')))
                    for a in e.block().query('ATTDEF'):
                        if a.dxf.tag.casefold() not in vistos:
                            a=a.copy();a.transform(e.matrix44());virtuales.append(a)
                    yield from entidades(virtuales,prof+1)
                else:yield e
        omitidos=set()
        for e in entidades(espacio):
            k=e.dxftype();color=e.dxf.get('true_color',None)
            if color is not None:color='#%06x'%color
            else:
                aci=e.dxf.get('color',256)
                if aci==256:aci=doc.layers.get(e.dxf.layer).dxf.color
                color='#000000' if aci in (0,7,256) else '#%02x%02x%02x'%tuple(ezdxf.colors.aci2rgb(abs(aci)))
            peso=e.dxf.get('lineweight',-1);estilo={'color':color,'weight':peso/100 if peso>0 else .25}
            if k=='LINE':p['primitives'].append({'kind':'line','points':xy(e.dxf.start)+xy(e.dxf.end),**estilo})
            elif k in ('CIRCLE','ARC') and abs(e.dxf.extrusion.z-1)<1e-6:
                p['primitives'].append({'kind':'arc','center':xy(e.dxf.center),'radius':e.dxf.radius*factor,'start':0 if k=='CIRCLE' else e.dxf.start_angle,'span':360 if k=='CIRCLE' else (e.dxf.end_angle-e.dxf.start_angle)%360,**estilo})
            elif k in ('LWPOLYLINE','POLYLINE','ELLIPSE','SPLINE','CIRCLE','ARC'):
                curva=path.make_path(e);puntos=[xy(v) for v in curva.flattening(.05/factor)]
                if len(puntos)>=2:p['primitives'].append({'kind':'path','points':puntos,**estilo})
            elif k in ('TEXT','MTEXT','ATTDEF','ATTRIB'):
                mtext=k=='MTEXT';s=e.plain_text(fast=False) if mtext else e.plain_text()
                if not s.strip():continue
                if mtext:
                    pos=e.dxf.insert;altura=e.dxf.char_height;giro=e.get_rotation();a=e.dxf.attachment_point-1
                    align=('left','center','right')[a%3];valign=('top','middle','bottom')[a//3];ancho=(e.dxf.width or 0)*factor
                else:
                    ali,pos,fin=e.get_placement();n=ali.name;ajuste=n.lower() if n in ('ALIGNED','FIT') else ''
                    angulo_ajustado=math.degrees(math.atan2(fin.y-pos.y,fin.x-pos.x)) if ajuste else None
                    if fin is not None and n in ('ALIGNED','FIT'):
                        pos=(pos+fin)/2;align='center';ancho=(fin-pos).magnitude*2*factor
                    else:align='center' if 'CENTER' in n or n=='MIDDLE' else 'right' if 'RIGHT' in n else 'left';ancho=0
                    valign='top' if 'TOP' in n else 'middle' if 'MIDDLE' in n else 'bottom' if 'BOTTOM' in n else 'baseline'
                    pos=e.ocs().to_wcs(pos);altura=e.dxf.height;giro=angulo_ajustado if angulo_ajustado is not None else e.dxf.rotation
                if mtext:direccion=e.ucs().ux
                else:direccion=e.ocs().to_wcs((math.cos(math.radians(giro)),math.sin(math.radians(giro)),0))
                giro=math.degrees(math.atan2(direccion.y,direccion.x))
                x,y=xy(pos);fuente=doc.styles.get(e.dxf.get('style','Standard')).dxf.get('font','Arial')
                shx=fuente.lower().endswith('.shx');fuente=Path(fuente.replace('\\','/')).stem
                if fuente.lower().endswith(('simplex','txt','iso','isocp')):fuente='Consolas'
                elif fuente.lower().startswith('roman'):fuente='Times New Roman'
                elif shx:fuente='Consolas'
                elif not fuente or fuente.lower() in ('standard','arial','arialmt'):fuente='Arial'
                t={'kind':'text','text':s,'x':x,'y':y,'height':altura*factor,'rotation':-giro,'align':align,'valign':valign,'font':fuente,'color':color}
                if ancho>0:t['width']=ancho
                if not mtext and ajuste:t['fit']=ajuste
                if not mtext:
                    t['stretch']=e.dxf.get('width',1.)
                    flags=e.dxf.get('text_generation_flag',0);t['mirror_x']=bool(flags&2);t['mirror_y']=bool(flags&4)^(e.dxf.extrusion.z<0)
                if campos and k in ('ATTDEF','ATTRIB'):t['field']=campo(e.dxf.tag)
                prp=re.search(r'\$(?:PRP|PRPSHEET):\s*"([^"]+)"',s,re.I)
                if campos and prp:t.update(field=campo(prp[1]),prefix=s[:prp.start()],suffix=s[prp.end():],text='')
                p['primitives'].append(t)
            else:omitidos.add(k)
        if omitidos:p['warnings'].append('Entidades no soportadas omitidas: '+', '.join(sorted(omitidos)))
        if not p['primitives']:raise ValueError('El DXF no contiene entidades soportadas')
        zona_detectada(p);return validar_plantilla(propuestas(p) if campos else p)
    except (OSError,ValueError):raise
    except Exception as exc:raise ValueError('DXF no válido: '+str(exc)) from exc


def abrir_pdf(ruta):
    try:import pypdfium2 as pdf
    except ImportError as exc:raise ValueError('Para importar PDF se necesita pypdfium2') from exc
    try:
        doc=pdf.PdfDocument(ruta)
        if doc.get_metadata_dict().get('Encryption') or pdf.raw.FPDF_GetSecurityHandlerRevision(doc)>=0:
            doc.close();raise ValueError('El PDF está cifrado; guarda una copia sin cifrar para usarla como plantilla')
        if len(doc)==0:doc.close();raise ValueError('El PDF está vacío')
        return doc
    except pdf.PdfiumError as exc:raise ValueError('PDF no válido o cifrado; se necesita un PDF sin contraseña') from exc


def paginas_pdf(ruta):
    doc=abrir_pdf(ruta)
    try:return len(doc)
    finally:doc.close()


def importar_pdf(ruta,pagina=0):
    doc=abrir_pdf(ruta)
    import pypdfium2 as pdf
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    from PySide6.QtGui import QImage
    try:
        if not 0<=pagina<len(doc):raise ValueError('Página PDF inexistente')
        page=doc[pagina];w,h=page.get_size();mm=25.4/72
        if not list(page.get_objects()):raise ValueError('La página PDF está vacía')
        if w*h*(300/72)**2>160_000_000:raise ValueError('Página demasiado grande para importar a 300 ppp')
        p={'version':1,'source':'PDF','size':[w*mm,h*mm],'primitives':[],'zone':None,'warnings':[]}
        tp=page.get_textpage();borrar=[];geometria=[];rot=page.get_rotation();l,b,r,t=page.get_bbox()
        def punto(x,y):
            x,y=x-l,t-y;ww,hh=r-l,t-b
            if rot==90:x,y=hh-y,x
            elif rot==180:x,y=ww-x,hh-y
            elif rot==270:x,y=y,ww-x
            return x*mm,y*mm
        def mult(a,b):
            A,B,C,D,E,F=a;g,h,i,j,k,l=b
            return (A*g+C*h,B*g+D*h,A*i+C*j,B*i+D*j,A*k+C*l+E,B*k+D*l+F)
        def coord(m,x,y):a,b,c,d,e,f=m;return a*x+c*y+e,b*x+d*y+f
        def recorrer(form=None,nivel=0,padre=(1,0,0,1,0,0)):
            if nivel>15:raise ValueError('PDF con objetos anidados en exceso')
            for obj in page.get_objects(form=form,level=nivel,max_depth=nivel+1,textpage=tp):
                matriz=mult(padre,obj.get_matrix().get())
                if obj.type==pdf.raw.FPDF_PAGEOBJ_FORM:recorrer(obj,nivel+1,matriz)
                elif obj.type==pdf.raw.FPDF_PAGEOBJ_PATH:
                    inicio=anterior=None
                    for j in range(pdf.raw.FPDFPath_CountSegments(obj)):
                        seg=pdf.raw.FPDFPath_GetPathSegment(obj,j);sx,sy=ctypes.c_float(),ctypes.c_float()
                        if not pdf.raw.FPDFPathSegment_GetPoint(seg,ctypes.byref(sx),ctypes.byref(sy)):continue
                        q=punto(*coord(matriz,sx.value,sy.value));tipo=pdf.raw.FPDFPathSegment_GetType(seg)
                        if tipo==pdf.raw.FPDF_SEGMENT_MOVETO:inicio=q
                        elif tipo==pdf.raw.FPDF_SEGMENT_LINETO and anterior:geometria.append({'kind':'line','points':list(anterior)+list(q)})
                        anterior=q
                        if pdf.raw.FPDFPathSegment_GetClose(seg) and inicio:geometria.append({'kind':'line','points':list(q)+list(inicio)})
                elif obj.type==pdf.raw.FPDF_PAGEOBJ_TEXT:
                    contenido=obj.extract()
                    if not contenido.strip():continue
                    if '\ufffd' in contenido:
                        aviso='Algunos textos no se pudieron decodificar y permanecen en el fondo sin ser editables'
                        if aviso not in p['warnings']:p['warnings'].append(aviso)
                        continue
                    # La caja del objeto ya incluye su matriz local, pero no la de sus formularios padres.
                    x0,y0,x1,y1=obj.get_bounds();caja=[punto(*coord(padre,x,y)) for x,y in ((x0,y0),(x0,y1),(x1,y0),(x1,y1))]
                    angulo=-math.degrees(math.atan2(matriz[1],matriz[0]))+rot
                    angulo=(angulo+180)%360-180
                    # Conservar la línea base transformada, no el borde variable de cada glifo.
                    x,y=punto(matriz[4],matriz[5])
                    altura=max(.05,obj.get_font_size()*math.hypot(matriz[0],matriz[1])*mm*.72)
                    rgba=[ctypes.c_uint() for _ in range(4)];ok=pdf.raw.FPDFPageObj_GetFillColor(obj,*[ctypes.byref(c) for c in rgba])
                    color='#%02x%02x%02x'%tuple(c.value for c in rgba[:3]) if ok else '#000000'
                    p['primitives'].append({'kind':'text','text':contenido,'x':x,'y':y,'height':altura,'rotation':angulo,'align':'left','valign':'baseline','font':'Arial','color':color,'box':[min(q[0] for q in caja),min(q[1] for q in caja),max(q[0] for q in caja),max(q[1] for q in caja)]})
                    borrar.append(obj)
        try:recorrer()
        finally:tp.close()
        for obj in borrar:page.remove_obj(obj);obj.close()
        if borrar:
            page.gen_content();p['warnings'].append('Los textos extraíbles son editables. Si hay otros textos convertidos en trazos o imágenes, permanecen en el fondo y no son editables')
        else:p['warnings'].append('No se han podido extraer textos: si están convertidos en trazos o imágenes, permanecerán en el fondo y no serán editables')
        bitmap=page.render(scale=300/72,rev_byteorder=True)
        try:
            formato=QImage.Format.Format_RGBA8888 if bitmap.n_channels==4 else QImage.Format.Format_RGB888
            imagen=QImage(bitmap.buffer,bitmap.width,bitmap.height,bitmap.stride,formato).copy()
            datos=QByteArray();buffer=QBuffer(datos);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            if not imagen.save(buffer,'PNG'):raise ValueError('No se pudo generar el fondo PDF')
            buffer.close();p['background']={'kind':'png','data':base64.b64encode(bytes(datos)).decode('ascii'),'dpi':300,'page':pagina+1}
        finally:bitmap.close()
        deteccion={'primitives':geometria};zona_detectada(deteccion)
        for k in ('detected_zone','inner_frame','title_box'):
            if deteccion.get(k):p[k]=deteccion[k]
        p['primitives']=agrupar_textos_pdf(p['primitives'])
        return validar_plantilla(propuestas(p))
    except (OSError,ValueError):raise
    except Exception as exc:raise ValueError('No se pudo importar el PDF: '+str(exc)) from exc
    finally:doc.close()


def agrupar_textos_pdf(textos):
    # Qt y otros productores emiten un objeto por glifo. Agrupar solo vecinos
    # de la misma línea y tamaño; no unir columnas ni rótulos distantes.
    salida=[]
    for t in textos:
        unir=False
        if salida:
            anterior=salida[-1];rad=math.radians(t['rotation']);u=(math.cos(rad),math.sin(rad));v=(-u[1],u[0])
            dx,dy=t['x']-anterior['x'],t['y']-anterior['y']
            proy=lambda caja:[x*u[0]+y*u[1] for x,y in ((caja[0],caja[1]),(caja[0],caja[3]),(caja[2],caja[1]),(caja[2],caja[3]))]
            hueco=min(proy(t['box']))-max(proy(anterior['box']))
            unir=abs(t['rotation']-anterior['rotation'])<.1 and abs(t['height']-anterior['height'])<t['height']*.05 and abs(dx*v[0]+dy*v[1])<t['height']*.18 and -t['height']*.3<=hueco<t['height']*.9
        if unir:
            separador=' ' if hueco>t['height']*.3 and not anterior['text'].endswith(' ') and not t['text'].startswith(' ') else ''
            anterior['text']+=separador+t['text'];a,b=anterior['box'],t['box'];anterior['box']=[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]
        else:salida.append(t)
    return salida


def importar_svg(ruta):
    from PySide6.QtSvg import QSvgRenderer
    import xml.etree.ElementTree as ET
    datos=Path(ruta).read_bytes()
    try:raiz=ET.fromstring(datos)
    except ET.ParseError as exc:raise ValueError('SVG no válido') from exc
    visibles={'path','rect','circle','ellipse','line','polyline','polygon','image','text','use'}
    if not QSvgRenderer(datos).isValid() or not any(e.tag.split('}')[-1] in visibles for e in raiz.iter()):raise ValueError('SVG vacío o no válido')
    if any(e.tag.split('}')[-1] in ('script','foreignObject') or any(v and not v.startswith(('#','data:')) for k,v in e.attrib.items() if k.split('}')[-1]=='href') for e in raiz.iter()):raise ValueError('El SVG debe ser autónomo, sin enlaces a archivos externos ni scripts')
    def medida(s):
        m=re.fullmatch(r'\s*([\d.]+)(mm|cm|in|pt|px)?\s*',s or '')
        return float(m[1])*{'mm':1,'cm':10,'in':25.4,'pt':25.4/72,'px':25.4/96,None:25.4/96}[m[2]] if m else None
    w,h=medida(raiz.get('width')),medida(raiz.get('height'))
    if w is None or h is None:
        size=QSvgRenderer(datos).defaultSize();w,h=size.width()*25.4/96,size.height()*25.4/96
    return validar_plantilla({'version':1,'source':'SVG','size':[w,h],'primitives':[],'background':{'kind':'svg','data':base64.b64encode(datos).decode('ascii')},'warnings':[],'zone':None})


def importar(ruta,pagina=0,campos=True):
    ext=Path(ruta).suffix.lower()
    if ext=='.dwg':raise ValueError('DWG no está soportado. Guarda o exporta el dibujo como DXF desde tu programa de CAD')
    if ext=='.slddrt':raise ValueError('SLDDRT es un formato propietario. Exporta el formato de hoja como DXF')
    if ext=='.dxf':return importar_dxf(ruta,campos=campos)
    if ext=='.pdf':return importar_pdf(ruta,pagina)
    if ext=='.svg':return importar_svg(ruta)
    raise ValueError('Plantilla no soportada: elige DXF, PDF o SVG')
