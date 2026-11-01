// Dibujo de un grafcet con la notación gráfica de la norma (tablas 1–11). Lo usan el banco de pruebas y el
// comparador de decisiones. Las proporciones y convenciones se tomaron por inspección visual de las imágenes de la
// norma aportadas por el usuario (fuente IMG del documento 02), también las jerárquicas: forzado «G{…}» en
// rectángulo doble, macroetapa con divisiones horizontales, encapsulante con las esquinas cortadas, «*» de enlace
// de activación, recinto y parciales enmarcados y expansión unida a su macroetapa. No se copia ningún activo; el
// contraste con una copia íntegra sigue pendiente (U-01).
const NS = "http://www.w3.org/2000/svg";
// Unidad: lado de la etapa = 2·H
const SX = 100;       // margen izquierdo del dibujo
const H = 22;         // semilado de la etapa cuadrada
const TB = 8;         // trazo de 16 px frente al lado de etapa de 44 px
const BARRA_GROSOR = 8;
const ACT_LINK = 26;  // enlace etapa–acción (≈0,6 del lado)
const ACT_MIN = 80;   // anchura mínima de una acción
const ACT_GAP = 36;   // entre cajas de acción de una fila separada
const ACT_BUS = 28;   // de la línea común de una fila separada, por debajo de las cajas
const ACT_COL = 12;   // separación mínima entre cajas de una columna (crece lo que piden sus marcas)
const ACT_CANAL = 7;  // de la derivación a la segunda columna de una matriz, por debajo de su fila
const MARK = 7;       // marcas internas de la encapsulante y divisiones de la macroetapa
const GROSOR_NEGADO = 1.25;  // grosor de la barra de una variable negada (el sobrerrayado del texto no se puede engrosar)
const TMR_EXTRA = 12;     // lo que sube por encima de la condición o el evento de una acción con temporizador
const MARGEN_MARCO_X = 26;  // lo que se separa el marco de un parcial de todo lo que dibuja de él, a izquierda y derecha...
const MARGEN_MARCO_Y = 22;  // ... y por arriba y por abajo (el mismo de siempre alrededor de sus etapas)
const TALLO_T = 24;       // tramo recto de una transición sin etapa anterior o siguiente (grafcet/routing.py)
const SIMUL = 14;         // de la transición al doble trazo de una simultaneidad

function el(tag, attrs={}, parent) { const e = document.createElementNS(NS, tag);
  for (const [k,v] of Object.entries(attrs)) e.setAttribute(k, v); if (parent) parent.appendChild(e); return e; }
function txt(parent, x, y, s, attrs={}) { const t = el("text", {x, y, ...attrs}, parent); t.textContent = s; return t; }
// Lo que sube un texto de ese tamaño por encima de su línea base (Arial: igual que en escritorio/diagrama.py)
function ascenso(size) { return Math.round(0.905 * size); }

// Principio o final (x) de un tramo de texto
function extremo(ts, fin) {
  try { const n = ts.getNumberOfChars(); if (n) return fin ? ts.getEndPositionOfChar(n - 1).x : ts.getStartPositionOfChar(0).x; } catch (e) { /* sin caracteres */ }
  const b = ts.getBBox();
  return fin ? b.x + b.width : b.x;
}

// Texto con segmentos {t, o: sobrerrayado (negación), s: subíndice}. La negación es una barra propia de GROSOR_NEGADO
// (class "neg"), arriba del texto, sobre cada tramo de segmentos negados seguidos
function segText(parent, x, y, segs, cls, anchor="start", truth={}) {
  const t = el("text", {x, y, class: cls, "text-anchor": anchor}, parent);
  (segs || []).forEach(s => {
    const sp = el("tspan", {}, t); sp.textContent = s.t;
    if ((s.eval || []).some(k => truth[k] === true)) sp.setAttribute("class", "verdadero");
    if (s.s) { sp.setAttribute("baseline-shift", "sub"); sp.setAttribute("font-size", "75%"); }
  });
  const ts = [...t.children], yb = y - ascenso(parseFloat(getComputedStyle(t).fontSize));
  for (let i = 0; i < ts.length; i++) {
    if (!segs[i].o) continue;
    let j = i;
    const verde = (segs[i].eval || []).some(k => truth[k] === true);
    while (j + 1 < ts.length && segs[j + 1].o && (segs[j + 1].eval || []).some(k => truth[k] === true) === verde) j++;
    el("line", {x1:extremo(ts[i], false), x2:extremo(ts[j], true), y1:yb, y2:yb, class:verde ? "neg verdadero" : "neg"}, parent);
    i = j;
  }
  return t;
}

// Nombre visible de una variable, etapa, parcial, macroetapa o transición: los ID internos del editor no se muestran
// Comentario de una etapa o transición: entre comillas tipográficas, en cursiva y discreto, a la derecha de x, centrado
// en yc y ajustado a líneas de como mucho ANCHO_COMENTARIO (igual que escritorio/diagrama.py)
const ANCHO_COMENTARIO = 190;
function comentario(g, x, yc, texto) {
  const t = el("text", {x, y: yc, class: "comentario"}, g);
  const palabras = `\u201c${texto}\u201d`.split(/\s+/), lineas = [];
  let linea = "";
  palabras.forEach(pal => {
    const prueba = linea ? linea + " " + pal : pal;
    t.textContent = prueba;
    if (linea && t.getComputedTextLength() > ANCHO_COMENTARIO) { lineas.push(linea); linea = pal; } else linea = prueba;
  });
  lineas.push(linea);
  t.textContent = "";
  const alto = 14, y0 = yc - (lineas.length - 1) * alto / 2 + 4;
  lineas.forEach((l, i) => { const ts = el("tspan", {x, y: y0 + i * alto}, t); ts.textContent = l; });
}

function nameOf(M, id) { return ((M && M.names) || {})[id] ?? id; }

// Estado de los temporizadores de una expresión (Vista.state().temporal): el tiempo transcurrido «0,50 s» mientras cuenta
// y «3,00 s ✓» al vencer, alineado al extremo de la duración del temporizador (la nth-ésima aparición de su «token» en
// el texto `tx`, escrito con los segmentos `segs`; si no se encuentra, encima de todo el texto) y por encima de su barra
// si está negada. `y` es la línea base del texto. Devuelve hasta dónde llega por la derecha (0 si no dibuja nada).
function timerText(parent, tx, segs, y, ref, S) {
  const size = parseFloat(getComputedStyle(tx).fontSize);
  let derecha = 0;
  Object.values(S.temporal || {}).filter(t => t.expr === ref && t.shown).forEach(t => {
    const sitios = (segs || []).map((s, i) => s.t === t.token ? i : -1).filter(i => i >= 0);
    const i = sitios[t.nth || 0];
    const caja = i === undefined ? tx.getBBox() : tx.children[i].getBBox();
    const negado = i === undefined ? (segs || []).some(s => s.o) : !!segs[i].o;
    const base = y - ascenso(size) - (negado ? 3 : 1), off = !!t.off;
    const x = caja.x + (off ? caja.width : 0);
    const grupo = el("g", {class: `timer-state ${t.estado === "contando" ? "run" : "done"}`}, parent);
    const texto = txt(grupo, x, base - 1, t.shown, {"text-anchor": off ? "end" : "start", class: "timer"});
    derecha = Math.max(derecha, off ? x : x + texto.getComputedTextLength());
  });
  return derecha;
}

// M: modelo de la vista (etapas, macroetapas, transiciones, acciones, parciales); S: estado observado del motor;
// opciones.dependencias (apagada por defecto, como `dependencias` de escritorio/diagrama.py): dibuja los trazos discontinuos
// que unen una macroetapa con su expansión y una encapsulante con sus recintos. No cambia nada más del dibujo.
function coloresElementos(M,S) {
  const activos = new Set(S.blocked ? [] : S.situation || []), roles={};
  Object.entries(S.macros || {}).forEach(([k,v])=>{if(v) activos.add(k);});
  activos.forEach(k=>roles[k]="active");
  M.transitions.forEach(t=>{const ob=(S.transitions||{})[t.id]||{};if(ob.fireable||(ob.validated&&(ob.receptivity||(S.truth||{})[t.conditionRef]===true)))roles[t.id]="active";});
  (S.lastCleared||[]).forEach(k=>roles[k]="history");
  const tids=new Set(M.transitions.map(t=>t.id));
  (M.bars||[]).forEach(b=>{
    const vecinos=[...b.arriba,...b.abajo], ts=vecinos.filter(k=>tids.has(k));
    const colores=(ts.length ? ts : vecinos).map(k=>roles[k]);
    if(colores.includes("active")||colores.includes("history")) roles[b.id]=colores.includes("active")?"active":"history";
  });
  (M.partials||[]).forEach(p=>{
    if(activos.has(p.ownerStep)||[...M.steps,...M.macros||[]].some(e=>e.partial===p.id&&activos.has(e.id)))roles[p.id]="active";
  });
  return roles;
}

function colorEnlace(M, roles, e) {
  if(e.rol==="pre") return roles[e.tid] || roles[e.sid] || "";
  if(e.rol==="barra") {
    const b=M.bars.find(b=>b.id===e.tid);
    return (b.arriba.includes(e.sid) ? roles[e.sid] : roles[e.tid]) || "";
  }
  return roles[e.tid] || "";
}

function drawDiagram(svg, M, S, opciones = {}) {
  const dependencias = !!opciones.dependencias;
  svg.innerHTML = "";
  svg.setAttribute("viewBox", "0 0 640 600");
  const pos = {};
  M.steps.forEach(s => pos[s.id] = {x:s.x+SX, y:s.y});
  (M.macros || []).forEach(m => pos[m.id] = {x:m.x+SX, y:m.y});
  const situation = new Set(S.situation || []), virtual = new Set(S.virtual || []);
  const unstable = new Set(S.unstable || []);
  const cleared = new Set(S.lastCleared || []);
  const blk = S.blocked, reached = new Set(blk ? blk.reached : []);
  const frames = el("g", {}, svg), annotations = el("g", {}, svg), links = el("g", {}, svg), bars = el("g", {}, svg), steps = el("g", {}, svg);
  (M.annotations || []).forEach(n => {
    const x=n.x+SX, y=n.y, w=n.width, h=n.height;
    if(n.kind === "image") {
      el("image",{x,y,width:w,height:h,href:n.data,preserveAspectRatio:"xMidYMid meet"},annotations);
    } else if(n.kind === "text") {
      const box=el("foreignObject",{x,y,width:w,height:h},annotations);
      const text=document.createElementNS("http://www.w3.org/1999/xhtml","div");
      text.setAttribute("style",`white-space:pre-wrap;overflow-wrap:anywhere;overflow:hidden;box-sizing:border-box;padding:4px;width:100%;height:100%;font-family:${n.font||"Arial"};font-size:${n.size||18}px;color:${n.color||"#172e4d"}`);
      text.textContent=n.text||"";box.appendChild(text);
    }
  });
  const roles = coloresElementos(M,S);
  const geo = {trans: {}, acc: {}};  // lo que ocupa cada transición (con sus textos) y las acciones de cada etapa: lo piden los marcos
  M.transitions.forEach(t => {
    const tx = t.x + SX, ty = t.y, ob = (S.transitions||{})[t.id] || {}, rol = roles[t.id] || "";
    const pre = (t.preDib || t.pre).map(p => pos[p]), post = (t.postDib || t.post).map(p => pos[p]);
    if (t.simulPre) {
      const xs = [...pre.map(p=>p.x), tx], yy = ty - 14;
      el("rect", {x:Math.min(...xs)-8,y:yy-BARRA_GROSOR+1,width:Math.max(...xs)-Math.min(...xs)+16,height:BARRA_GROSOR-2,class:"sync-gap"}, bars);
      [yy, yy-BARRA_GROSOR].forEach(y => el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:y, y2:y, class:"dbl " + rol}, bars));
      el("path", {d:`M${tx},${yy} V${ty}`, class:"link " + rol}, links);
    }
    if (t.simulPost) {
      const xs = [...post.map(p=>p.x), tx], yy = ty + 14;
      el("rect", {x:Math.min(...xs)-8,y:yy+1,width:Math.max(...xs)-Math.min(...xs)+16,height:BARRA_GROSOR-2,class:"sync-gap"}, bars);
      [yy, yy+BARRA_GROSOR].forEach(y => el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:y, y2:y, class:"dbl " + rol}, bars));
      el("path", {d:`M${tx},${ty} V${yy}`, class:"link " + rol}, links);
    }
    if (!pre.length) el("path", {d:`M${tx},${ty-24} V${ty}`, class:"link " + rol}, links);    // transición fuente
    if (!post.length) el("path", {d:`M${tx},${ty} V${ty+24}`, class:"link " + rol}, links);   // transición sumidero
    const cls = ["tr", roles[t.id] || "", ob.validated?"validated":"", ob.fireable?"fireable":"", cleared.has(t.id)?"cleared":"",
                 blk && blk.element === t.id ? "question" : ""].join(" ");
    const g = el("g", {class:cls}, bars);
    el("title", {}, g).textContent = `Transición ${t.label}: validada ${ob.validated?"sí":"no"}, receptividad ${ob.receptivity?"verdadera":"falsa"}` +
      (ob.forced ? "; su parcial está forzado y no evoluciona" : "");
    el("line", {x1:tx-TB, x2:tx+TB, y1:ty, y2:ty, class:"bar"}, g);
    const tl = t.showLabel !== false ? txt(g, tx-TB-6, ty+5, `(${t.label})`, {"text-anchor":"end", class:"tdes"}) : null;
    const tc = segText(g, tx+TB+8, ty+5, t.cond, "tcond", "start", S.truth || {});
    geo.trans[t.id] = cajaTransicion(t, tx, ty, pre.filter(q => q), post.filter(q => q), tl ? tl.getComputedTextLength() : null,
                                     t.cond && t.cond.length ? tc.getComputedTextLength() : null);
    const derecha = timerText(g, tc, t.cond, ty+5, t.conditionRef, S);
    if (t.comment) {  // a la derecha de la receptividad y del estado de su temporizador
      const fin = Math.max(tx+TB+8 + tc.getComputedTextLength() + (t.cond ? 14 : 0), derecha ? derecha + 8 : 0);
      comentario(g, fin, ty, t.comment);
    }
  });
  // Exactamente los mismos recorridos que Qt y la detección del ratón.
  (M.links || []).forEach(e => {
    const rol = colorEnlace(M, roles, e);
    el("path", {d:e.pts.map((p,i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" "), class:"link " + rol}, links);
    (e.arrows || []).forEach(a => el("path", {d:a.pts.map((p,i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ")+" Z", class:"arrow " + rol}, links));
  });
  (M.bars || []).forEach(b => {
    const x = b.x + SX, rol = roles[b.id] || "";
    if(b.kind === "Y") el("rect", {x,y:b.y+1,width:b.ancho,height:BARRA_GROSOR-2,class:"sync-gap"}, bars);
    [0, ...(b.kind === "Y" ? [BARRA_GROSOR] : [])].forEach(dy => el("line", {x1:x, x2:x+b.ancho, y1:b.y+dy, y2:b.y+dy, class:"dbl " + rol}, bars));
  });
  M.steps.forEach(s => {
    const p = pos[s.id], stale = !!blk && situation.has(s.id), act = !blk && situation.has(s.id);
    const cand = !!blk && reached.has(s.id) && !stale, vir = virtual.has(s.id) && !act;
    const uns = !vir && !act && !stale && !cand && unstable.has(s.id);
    const g = el("g", {class:`step ${act?"active":""} ${vir||uns?"virtual":""} ${stale?"stale":""} ${cand?"cand":""}`}, steps);
    const kind = {enclosing:" (encapsulante)", entry:" (entrada de la expansión)", exit:" (salida de la expansión)"}[s.kind] || "";
    el("title", {}, g).textContent = `Etapa ${s.label}${s.initial?" (inicial)":""}${kind}${s.partial?` · parcial ${nameOf(M, s.partial)}`:""}` +
      `${s.activation?" · enlace de activación":""}: ` +
      (stale ? "último estado estable conservado" : cand ? "alcanzada antes del punto en cuestión, sin confirmar" :
       act ? "activa" : vir ? "inestable (en recorrido)" : uns ? "fue inestable en el último instante" : "inactiva");
    el("rect", {x:p.x-H, y:p.y-H, width:2*H, height:2*H, class:"outer"}, g);
    if (s.initial) el("rect", {x:p.x-H+4, y:p.y-H+4, width:2*H-8, height:2*H-8, fill:"none"}, g);
    if (s.kind === "enclosing") {  // encapsulante (P43-01, P44-01): esquinas cortadas en diagonal; si es inicial, las del cuadrado interior
      const h = s.initial ? H - 4 : H, c = Math.round(0.22 * 2 * h);
      const x0 = p.x - h, x1 = p.x + h, y0 = p.y - h, y1 = p.y + h;
      el("path", {d:`M${x0+c},${y0} L${x0},${y0+c} M${x1-c},${y0} L${x1},${y0+c} M${x0},${y1-c} L${x0+c},${y1} M${x1},${y1-c} L${x1-c},${y1}`,
                  class:"hmark"}, g);
    }
    txt(g, p.x, p.y+3, s.label, {"text-anchor":"middle"});
    if (s.activation) txt(g, p.x-H-5, p.y+5, "*", {"text-anchor":"end", class:"amark-act"});
    if (act) el("circle", {cx:p.x, cy:p.y+12, r:3.5, class:"token"}, g);
    if (vir) txt(g, p.x, p.y+H+13, "inestable", {"text-anchor":"middle", class:"tag vtag"});
    if (uns) txt(g, p.x, p.y+H+13, "fue inestable", {"text-anchor":"middle", class:"tag vtag"});
    if (stale) txt(g, p.x, p.y+H+13, "último estable", {"text-anchor":"middle", class:"tag stag"});
    if (cand) txt(g, p.x, p.y+H+13, "alcanzada, sin confirmar", {"text-anchor":"middle", class:"tag ctag"});
    const xr = drawActions(g, Object.assign({id:s.id},p), s.actions, S, s.actionLayout, geo.acc[s.id] = []);
    if (s.comment) comentario(g, (xr ?? p.x + H) + 10, p.y, s.comment);  // a la derecha de la etapa o de su última acción
  });
  (M.macros || []).forEach(m => {  // macroetapa: divisiones horizontales superior e inferior
    const p = pos[m.id], act = !!(S.macros || {})[m.id];
    const g = el("g", {class:`step macro ${act?"active":""}`}, steps);
    el("title", {}, g).textContent = `Macroetapa ${nameOf(M, m.id)} (expansión ${nameOf(M, m.expansion)}): ${act ? "activa (alguna etapa de su expansión)" : "inactiva"}`;
    el("rect", {x:p.x-H, y:p.y-H, width:2*H, height:2*H, class:"outer"}, g);
    el("line", {x1:p.x-H, x2:p.x+H, y1:p.y-H+MARK, y2:p.y-H+MARK, class:"hmark"}, g);
    el("line", {x1:p.x-H, x2:p.x+H, y1:p.y+H-MARK, y2:p.y+H-MARK, class:"hmark"}, g);
    txt(g, p.x, p.y+5, nameOf(M, m.id), {"text-anchor":"middle"});
  });
  drawFrames(frames, M, pos, dependencias, geo, roles);  // (al final, con todo medido; el grupo de los marcos va el primero: queda debajo)
  const b = svg.getBBox();
  svg.setAttribute("viewBox", `${b.x-14} ${b.y-14} ${b.width+28} ${b.height+28}`);
}

// Lo que ocupa una transición en el dibujo ([x0, y0, x1, y1]): el trazo (y su tramo recto si no tiene etapa anterior o siguiente),
// su designación a la izquierda (ancho wl), su receptividad a la derecha (ancho wc) y el doble trazo de una simultaneidad
function cajaTransicion(t, tx, ty, pre, post, wl, wc) {
  let r = [tx - TB, ty - (pre.length ? 0 : TALLO_T), tx + TB, ty + (post.length ? 0 : TALLO_T)];
  const unir = (x0, y0, x1, y1) => { r = [Math.min(r[0], x0), Math.min(r[1], y0), Math.max(r[2], x1), Math.max(r[3], y1)]; };
  if (wl !== null) unir(tx - TB - 6 - wl, ty - 12, tx - TB - 6, ty + 9);
  if (wc !== null) unir(tx + TB + 8, ty - 12, tx + TB + 8 + wc, ty + 9);
  if (t.simulPre) { const xs = [...pre.map(q => q.x), tx]; unir(Math.min(...xs) - 8, ty - SIMUL - BARRA_GROSOR, Math.max(...xs) + 8, ty - SIMUL); }
  if (t.simulPost) { const xs = [...post.map(q => q.x), tx]; unir(Math.min(...xs) - 8, ty + SIMUL, Math.max(...xs) + 8, ty + SIMUL + BARRA_GROSOR); }
  return r;
}

// Parciales según las figuras de la norma:
// - recinto (P43-02): marco de trazo continuo; arriba, el nombre de la encapsulante y, abajo, el del parcial, los dos a caballo
//   del trazo (el fondo del color del lienzo de `framelabel` lo corta y deja leerlos);
// - parcial (P40-02): marco redondeado con su nombre abajo; un parcial hijo se dibuja dentro de su padre;
// - expansión de macroetapa (P47-03): sin marco; trazos discontinuos de la macroetapa a su entrada y a su salida.
// Esos trazos son las dependencias: solo se dibujan con `dependencias`, y con ellas también los dos que unen una encapsulante
// con las esquinas del lado del marco de cada uno de sus recintos que mira hacia ella (`dependenciasRecinto`).
// El marco rodea todo lo que se dibuja del parcial (`contenidoParciales`) con el margen de siempre, y como mínimo lo de siempre
// alrededor de sus etapas y transiciones: el mismo cálculo que `cajas_parciales` de escritorio/diagrama.py.

// Los dos trazos de dependencia ([[origen], [destino]] cada uno) de una encapsulante centrada en (ox, oy) a su recinto de marco b:
// cada uno llega a una esquina del lado del marco que mira hacia ella (el de la mayor diferencia entre centros; en empate, el
// vertical) y sale de la esquina de la encapsulante más cercana a esa esquina (en una encapsulante cortada, el punto medio de la
// diagonal; en una inicial, la esquina del cuadrado exterior). Igual que `_dependencias_recinto` de escritorio/diagrama.py.
function dependenciasRecinto(b, ox, oy, inicial) {
  const dx = ox - (b.x0 + b.x1) / 2, dy = oy - (b.y0 + b.y1) / 2;
  let destinos;
  if (Math.abs(dy) >= Math.abs(dx)) { const y = dy <= 0 ? b.y0 : b.y1; destinos = [[b.x0, y], [b.x1, y]]; }
  else { const x = dx < 0 ? b.x0 : b.x1; destinos = [[x, b.y0], [x, b.y1]]; }
  const c = inicial ? H : H - Math.round(0.22 * 2 * H) / 2;
  const esquinas = [[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([sx, sy]) => [ox + sx * c, oy + sy * c]);
  const d2 = (e, d) => (e[0] - d[0]) ** 2 + (e[1] - d[1]) ** 2;
  return destinos.map(d => [esquinas.reduce((m, e) => d2(e, d) < d2(m, d) ? e : m), d]);
}

// Por parcial, [x0, y0, x1, y1] de todo lo que se dibuja de él, sin márgenes: sus etapas y macroetapas, sus transiciones con sus
// textos, las acciones y órdenes unidas a sus etapas (con lo que sobresalen sus marcas y los trazos que las unen), los
// recorridos de sus enlaces (también los de retorno) y las barras que unen elementos suyos. No cuenta lo que cambia al simular
// (el tiempo de un temporizador, las etiquetas «inestable») ni los comentarios.
function contenidoParciales(M, pos, geo) {
  const out = {}, de = {};
  const anotar = (pid, x0, y0, x1, y1) => {
    if (!pid) return;
    const b = out[pid];
    if (!b) out[pid] = [x0, y0, x1, y1];
    else { b[0] = Math.min(b[0], x0); b[1] = Math.min(b[1], y0); b[2] = Math.max(b[2], x1); b[3] = Math.max(b[3], y1); }
  };
  M.steps.forEach(s => {
    const p = pos[s.id];
    de[s.id] = s.partial;
    anotar(s.partial, p.x - H, p.y - H, p.x + H, p.y + H);
    (geo.acc[s.id] || []).forEach(r => anotar(s.partial, ...r));
  });
  (M.macros || []).forEach(m => { const p = pos[m.id]; de[m.id] = m.partial; anotar(m.partial, p.x - H, p.y - H, p.x + H, p.y + H); });
  M.transitions.forEach(t => { de[t.id] = t.partial; if (geo.trans[t.id]) anotar(t.partial, ...geo.trans[t.id]); });
  (M.links || []).forEach(e => {  // el enlace es del parcial de su transición (el de una barra, del de su elemento)
    const pid = de[e.rol === "barra" ? e.sid : e.tid];
    e.pts.forEach(q => anotar(pid, q[0], q[1], q[0], q[1]));
  });
  (M.bars || []).forEach(b => {
    const x = b.x + SX, h = b.kind === "Y" ? BARRA_GROSOR : 0;
    [...b.arriba, ...b.abajo].forEach(i => anotar(de[i], x, b.y, x + b.ancho, b.y + h));
  });
  return out;
}

function dependenciaCajas(a, b, superior=true, lado=b.x-a.x) {
  const dx = b.x - a.x, dy = b.y - a.y;
  if (lado === 0) {
    const k = dx || dy ? Math.min(.5, H / Math.max(Math.abs(dx), Math.abs(dy))) : 0;
    return [{x:a.x+dx*k,y:a.y+dy*k},{x:b.x-dx*k,y:b.y-dy*k}];
  }
  const hx = lado > 0 ? H : -H, hy = superior ? -H : H;
  return [{x:a.x+hx,y:a.y+hy},{x:b.x-hx,y:b.y+hy}];
}

function drawFrames(g, M, pos, dependencias, geo, roles={}) {
  const parts = M.partials || [];
  const box = {};
  const dibujado = contenidoParciales(M, pos, geo);
  const own = pid => M.steps.filter(s => s.partial === pid).map(s => pos[s.id])
    .concat((M.macros || []).filter(m => m.partial === pid).map(m => pos[m.id]))
    .concat(M.transitions.filter(t => t.partial === pid).map(t => ({x: t.x + SX, y: t.y})));
  function frame(pid) {
    if (box[pid] !== undefined) return box[pid];
    const pts = own(pid);
    let b = pts.length ? {x0: Math.min(...pts.map(p => p.x)) - H - 26, x1: Math.max(...pts.map(p => p.x)) + H + 70,
                          y0: Math.min(...pts.map(p => p.y)) - H - 22, y1: Math.max(...pts.map(p => p.y)) + H + 22} : null;
    if (dibujado[pid]) {  // todo lo que se dibuja de él queda dentro, con margen
      const [x0, y0, x1, y1] = dibujado[pid];
      const e = {x0: x0 - MARGEN_MARCO_X, x1: x1 + MARGEN_MARCO_X, y0: y0 - MARGEN_MARCO_Y, y1: y1 + MARGEN_MARCO_Y};
      b = b ? {x0: Math.min(b.x0, e.x0), x1: Math.max(b.x1, e.x1), y0: Math.min(b.y0, e.y0), y1: Math.max(b.y1, e.y1)} : e;
    }
    parts.filter(c => c.owner === pid && c.kind === "partial").forEach(c => {
      const cb = frame(c.id);
      if (!cb) return;
      const e = {x0: cb.x0 - 12, x1: cb.x1 + 12, y0: cb.y0 - 12, y1: cb.y1 + 16};
      b = b ? {x0: Math.min(b.x0, e.x0), x1: Math.max(b.x1, e.x1), y0: Math.min(b.y0, e.y0), y1: Math.max(b.y1, e.y1)} : e;
    });
    return (box[pid] = b);
  }
  parts.forEach(pt => {
    if (pt.kind === "expansion") {
      const m = (M.macros || []).find(x => x.id === pt.macro);
      if (!dependencias || !m || !pos[m.entry] || !pos[m.exit]) return;
      const mp = pos[m.id], ep = pos[m.entry], sp = pos[m.exit];
      [ep, sp].forEach((p, i) => {
        const [a, b] = dependenciaCajas(mp, p, i === 0, (ep.x + sp.x) / 2 - mp.x);
        el("path", {d: `M${a.x},${a.y} L${b.x},${b.y}`, class:"expline " + (roles[m.id] || "")}, g);
      });
      return;
    }
    const b = frame(pt.id);
    if (!b) return;
    if (pt.kind === "enclosure") {
      if (dependencias && pos[pt.ownerStep]) {
        const o = pos[pt.ownerStep], dueno = M.steps.find(s => s.id === pt.ownerStep);
        dependenciasRecinto(b, o.x, o.y, !!(dueno && dueno.initial)).forEach(([desde, hasta]) =>
          el("path", {d:`M${desde[0]},${desde[1]} L${hasta[0]},${hasta[1]}`, class:"expline " + (roles[pt.id] || "")}, g));
      }
      el("rect", {x:b.x0, y:b.y0, width:b.x1-b.x0, height:b.y1-b.y0, class:"frame enclosure " + (roles[pt.id] || "")}, g);
      // el nombre de la encapsulante, a la izquierda a caballo del trazo de arriba, y el del recinto, a la izquierda del de abajo: el fondo
      // del color del lienzo de `framelabel` corta el trazo y deja leerlos; igual en escritorio/diagrama.py
      txt(g, b.x0 + 30, b.y0 + 5, nameOf(M, pt.ownerStep), {class:"framelabel " + (roles[pt.id] || "")});
      txt(g, b.x0 + 30, b.y1 + 5, pt.label, {class:"framelabel " + (roles[pt.id] || "")});
    } else {
      el("rect", {x:b.x0, y:b.y0, width:b.x1-b.x0, height:b.y1-b.y0, rx:16, class:"frame " + (roles[pt.id] || "")}, g);
      txt(g, b.x0 + 30, b.y1 + 5, pt.label, {class:"framelabel " + (roles[pt.id] || "")});
    }
  });
}

// Lo que sobresale la marca de una acción por encima y por debajo de su caja (condición, flecha, banderita) y el tiempo
// transcurrido de su temporizador, que va encima de la condición o del evento (a.tmr)
function actionExtra(a) {
  if (a.kind === "continuous" && a.cond) return [20 + (a.tmr ? TMR_EXTRA : 0), 0];
  const [arriba, abajo] = {event:[24, 0], activation:[20, 0], deactivation:[0, 20]}[a.trigger] || [0, 0];
  return [arriba + (a.tmr && a.trigger === "event" ? TMR_EXTRA : 0), abajo];
}

// Una acción con su caja (a la derecha de ax, centrada en cy) y sus marcas. El ancho es el de su texto y, si lleva
// condición o evento encima, el que éstos necesitan para no invadir a la caja vecina; las cajas de una columna miden
// lo mismo (el mayor), por eso se devuelven los rectángulos para ajustarlos al final.
function drawAction(g, ax, cy, a, S) {
  const on = "activeActions" in S ? S.activeActions.includes(a.id) && !a.borrador : a.kind === "continuous" ? !!(S.outputs && S.outputs[a.target] && S.outputs[a.target].value)
    : a.kind === "force" ? (S.forces || []).some(f => f.order === a.id) : false;
  const ga = el("g", {class:`act ${on?"on":""} ${a.kind === "force" ? "force" : ""}`}, g);
  const rect = el("rect", {x:ax, y:cy-H, height:2*H, width:ACT_MIN}, ga);
  const inner = a.kind === "force" ? el("rect", {x:ax+3, y:cy-H+3, height:2*H-6, width:ACT_MIN-6, class:"inner"}, ga) : null;
  const label = segText(ga, ax + 12, cy + 5, a.text, "atext");
  const valor = (S.variableReadouts || {})[a.target];
  if(a.kind === "stored" && valor !== undefined) {
    const nombre = a.text[0].t.split(":=")[0].replace(/\s+$/, "");
    const ancho = label.getSubStringLength ? label.getSubStringLength(0,nombre.length)
      : label.children[0].getBBox().width * nombre.length / a.text[0].t.length;
    el("text", {x:ax+12+ancho/2, y:cy-10, class:"variable-value", "text-anchor":"middle"}, ga).textContent = valor;
  }
  let w = Math.max(ACT_MIN, label.getComputedTextLength() + 24);
  const mx = ax + 12, top = cy - H, bottom = cy + H;
  if (a.kind === "continuous" && a.cond) {             // acción condicionada: trazo y condición
    el("line", {x1:mx, x2:mx, y1:top, y2:top-14, class:"amark"}, ga);
    const ac = segText(ga, mx+5, top-4, a.cond, "acond", "start", S.truth || {});
    w = Math.max(w, 12 + 5 + ac.getComputedTextLength() + 8);
    timerText(ga, ac, a.cond, top-4, a.condRef, S);
  } else if (a.trigger === "activation") {            // memorizada al activar: flecha hacia arriba
    el("line", {x1:mx, x2:mx, y1:top, y2:top-11, class:"amark"}, ga);
    el("path", {d:`M${mx-5},${top-10} L${mx},${top-19} L${mx+5},${top-10} Z`, class:"ahead"}, ga);
  } else if (a.trigger === "deactivation") {          // memorizada al desactivar: flecha hacia abajo
    el("line", {x1:mx, x2:mx, y1:bottom, y2:bottom+11, class:"amark"}, ga);
    el("path", {d:`M${mx-5},${bottom+10} L${mx},${bottom+19} L${mx+5},${bottom+10} Z`, class:"ahead"}, ga);
  } else if (a.trigger === "event") {                 // memorizada por evento: banderita y evento
    el("line", {x1:mx, x2:mx, y1:top, y2:top-20, class:"amark"}, ga);
    el("path", {d:`M${mx},${top-20} L${mx-9},${top-15} L${mx},${top-10} Z`, class:"ahead"}, ga);
    const ev = segText(ga, mx+5, top-11, a.event, "acond", "start", S.truth || {});
    w = Math.max(w, 12 + 5 + ev.getComputedTextLength() + 8);
    timerText(ga, ev, a.event, top-11, a.condRef, S);
  }
  const ajustar = ancho => { rect.setAttribute("width", ancho); if (inner) inner.setAttribute("width", ancho - 6); };
  ajustar(w);
  if (g._contornosActivos) g.appendChild(g._contornosActivos);
  if (on) {
    const capa = g._contornosActivos || (g._contornosActivos = el("g", {class:"active-outlines"}, g));
    const borde = el("rect", {x:ax, y:cy-H, height:2*H, width:w}, capa);
    const original = ajustar;
    return {w, ajustar: ancho => { original(ancho); borde.setAttribute("width", ancho); }};
  }
  return {w, ajustar};
}

// Acciones a la derecha de la etapa, del alto de la etapa. Cuatro colocaciones (figuras (1)–(3) de la norma): "fila"
// (por defecto; cajas contiguas, la representación (2)), "fila-separada" (cajas separadas, unidas a una línea común que
// sale de la etapa), "matriz-2" (cuadrícula de dos columnas, de izquierda a derecha y de arriba abajo; una barra vertical
// común a su izquierda con una derivación a cada fila: la de la segunda columna pasa por debajo de la caja de la primera y
// sube a la suya) y "columna" (una debajo de otra, unidas por una línea vertical que sale de la etapa). En `rects` anota
// ([x0, y0, x1, y1]) lo que ocupa cada caja con sus marcas y los puntos de los trazos que las unen: lo piden los marcos
function drawActions(g, p, actions, S, layout = "fila", rects = []) {
  if (!actions.length) return;
  let ax = p.x + H + ACT_LINK;
  const punto = (x, y) => rects.push([x, y, x, y]);
  const caja = (x, cy, w, a) => { const [arriba, abajo] = actionExtra(a); rects.push([x, cy - H - arriba, x + w, cy + H + abajo]); };
  el("line", {x1:p.x+H, x2:ax, y1:p.y, y2:p.y, class:"link " + ((S.situation||[]).includes(p.id) && !S.blocked ? "active" : "")}, g);
  punto(p.x + H, p.y);
  punto(ax, p.y);
  const linea = pts => {
    pts.forEach(q => punto(q[0], q[1]));
    el("path", {d:pts.map((q, i) => `${i ? "L" : "M"}${q[0]},${q[1]}`).join(" "), class:"link " + ((S.situation||[]).includes(p.id) && !S.blocked ? "active" : ""), fill:"none"}, g);
  };
  if (layout === "columna") {
    const ys = [p.y];
    for (let i = 1; i < actions.length; i++)
      ys.push(ys[i-1] + 2*H + Math.max(ACT_COL, actionExtra(actions[i-1])[1] + actionExtra(actions[i])[0] + 4));
    const bx = p.x + H + ACT_LINK / 2;
    if (ys.length > 1) {
      linea([[bx, p.y], [bx, ys[ys.length-1]]]);
      ys.slice(1).forEach(cy => linea([[bx, cy], [ax, cy]]));
    }
    const cajas = actions.map((a, i) => drawAction(g, ax, ys[i], a, S));
    const ancho = Math.max(...cajas.map(c => c.w));
    cajas.forEach((c, i) => { c.ajustar(ancho); caja(ax, ys[i], ancho, actions[i]); });
    return ax + ancho;
  }
  if (layout === "matriz-2") {
    const filas = [];
    for (let i = 0; i < actions.length; i += 2) filas.push(actions.slice(i, i + 2));
    const alto = (f, k) => Math.max(...f.map(a => actionExtra(a)[k]));
    const ys = [p.y], canales = [];
    filas.forEach((f, n) => {
      if (n) ys.push(ys[n-1] + 2*H + Math.max(ACT_COL, alto(filas[n-1], 1) + alto(f, 0) + 2*ACT_CANAL));
      canales.push(ys[n] + H + alto(f, 1) + ACT_CANAL);
    });
    const bx = p.x + H + ACT_LINK / 2;
    const c1 = filas.map((f, n) => drawAction(g, ax, ys[n], f[0], S));
    const w1 = Math.max(...c1.map(c => c.w));
    c1.forEach((c, n) => { c.ajustar(w1); caja(ax, ys[n], w1, filas[n][0]); });
    const x2 = ax + w1 + ACT_GAP;
    const c2 = filas.map((f, n) => f.length > 1 ? drawAction(g, x2, ys[n], f[1], S) : null);
    const w2 = Math.max(0, ...c2.filter(c => c).map(c => c.w));
    c2.forEach((c, n) => { if (c) { c.ajustar(w2); caja(x2, ys[n], w2, filas[n][1]); } });
    if (actions.length > 1) {
      linea([[bx, p.y], [bx, filas[filas.length-1].length > 1 ? canales[canales.length-1] : ys[ys.length-1]]]);
      ys.slice(1).forEach(cy => linea([[bx, cy], [ax, cy]]));
      filas.forEach((f, n) => { if (f.length > 1) linea([[bx, canales[n]], [x2-14, canales[n]], [x2-14, ys[n]], [x2, ys[n]]]); });
    }
    return c2.some(c => c) ? x2 + w2 : ax + w1;
  }
  if (layout === "fila-separada") {
    const entradas = [];
    actions.forEach((a, i) => {
      if (i) { ax += ACT_GAP; entradas.push(ax - 14); }
      const w = drawAction(g, ax, p.y, a, S).w;
      caja(ax, p.y, w, a);
      ax += w;
    });
    if (entradas.length) {
      const bx = p.x + H + ACT_LINK / 2, yb = p.y + H + ACT_BUS;
      linea([[bx, p.y], [bx, yb], [entradas[entradas.length-1], yb]]);
      entradas.forEach(ex => linea([[ex, yb], [ex, p.y], [ex+14, p.y]]));
    }
    return ax;
  }
  actions.forEach(a => { const w = drawAction(g, ax, p.y, a, S).w; caja(ax, p.y, w, a); ax += w; });
  return ax;
}
