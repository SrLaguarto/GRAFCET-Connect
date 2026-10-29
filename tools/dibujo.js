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
const TB = 14;        // semilongitud del trazo de transición (≈0,65 del lado)
const ACT_LINK = 26;  // enlace etapa–acción (≈0,6 del lado)
const ACT_MIN = 80;   // anchura mínima de una acción
const ACT_GAP = 36;   // entre cajas de acción de una fila separada
const ACT_BUS = 28;   // de la línea común de una fila separada, por debajo de las cajas
const ACT_COL = 12;   // separación mínima entre cajas de una columna (crece lo que piden sus marcas)
const ACT_CANAL = 7;  // de la derivación a la segunda columna de una matriz, por debajo de su fila
const MARK = 7;       // marcas internas de la encapsulante y divisiones de la macroetapa

function el(tag, attrs={}, parent) { const e = document.createElementNS(NS, tag);
  for (const [k,v] of Object.entries(attrs)) e.setAttribute(k, v); if (parent) parent.appendChild(e); return e; }
function txt(parent, x, y, s, attrs={}) { const t = el("text", {x, y, ...attrs}, parent); t.textContent = s; return t; }
// Texto con segmentos {t, o: sobrerrayado (negación), s: subíndice}
function segText(parent, x, y, segs, cls, anchor="start") {
  const t = el("text", {x, y, class: cls, "text-anchor": anchor}, parent);
  (segs || []).forEach(s => {
    const sp = el("tspan", {}, t); sp.textContent = s.t;
    if (s.o) sp.setAttribute("text-decoration", "overline");
    if (s.s) { sp.setAttribute("baseline-shift", "sub"); sp.setAttribute("font-size", "75%"); }
  });
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

// Estado de los temporizadores de una expresión: «1,2 s / 3 s» mientras cuenta y «3 s ✓» al vencer (Vista.state().temporal)
function timerText(parent, x, y, ref, S) {
  Object.values(S.temporal || {}).filter(t => t.expr === ref && t.shown).forEach(t => {
    const e = txt(parent, x, y, t.shown, {class: `timer ${t.estado === "contando" ? "run" : "done"}`});
    x += e.getComputedTextLength() + 8;
  });
}

// M: modelo de la vista (etapas, macroetapas, transiciones, acciones, parciales); S: estado observado del motor
function drawDiagram(svg, M, S) {
  svg.innerHTML = "";
  svg.setAttribute("viewBox", "0 0 640 600");
  const pos = {};
  M.steps.forEach(s => pos[s.id] = {x:s.x+SX, y:s.y});
  (M.macros || []).forEach(m => pos[m.id] = {x:m.x+SX, y:m.y});
  const situation = new Set(S.situation || []), virtual = new Set(S.virtual || []);
  const unstable = new Set(S.unstable || []);
  const cleared = new Set(S.lastCleared || []);
  const blk = S.blocked, reached = new Set(blk ? blk.reached : []);
  const frames = el("g", {}, svg), links = el("g", {}, svg), bars = el("g", {}, svg), steps = el("g", {}, svg);
  drawFrames(frames, M, pos);
  M.transitions.forEach(t => {
    const tx = t.x + SX, ty = t.y, ob = (S.transitions||{})[t.id] || {};
    const pre = (t.preDib || t.pre).map(p => pos[p]), post = (t.postDib || t.post).map(p => pos[p]);
    if (t.simulPre) {
      const xs = [...pre.map(p=>p.x), tx], yy = ty - 14;
      [yy, yy-4].forEach(y => el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:y, y2:y, class:"dbl"}, links));
      el("path", {d:`M${tx},${yy} V${ty}`, class:"link"}, links);
    }
    if (t.simulPost) {
      const xs = [...post.map(p=>p.x), tx], yy = ty + 14;
      [yy, yy+4].forEach(y => el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:y, y2:y, class:"dbl"}, links));
      el("path", {d:`M${tx},${ty} V${yy}`, class:"link"}, links);
    }
    if (!pre.length) el("path", {d:`M${tx},${ty-24} V${ty}`, class:"link"}, links);    // transición fuente
    if (!post.length) el("path", {d:`M${tx},${ty} V${ty+24}`, class:"link"}, links);   // transición sumidero
    const cls = ["tr", ob.validated?"validated":"", ob.fireable?"fireable":"", cleared.has(t.id)?"cleared":"",
                 blk && blk.element === t.id ? "question" : ""].join(" ");
    const g = el("g", {class:cls}, bars);
    el("title", {}, g).textContent = `Transición ${t.label}: validada ${ob.validated?"sí":"no"}, receptividad ${ob.receptivity?"verdadera":"falsa"}` +
      (ob.forced ? "; su parcial está forzado y no evoluciona" : "");
    el("line", {x1:tx-TB, x2:tx+TB, y1:ty, y2:ty, class:"bar"}, g);
    if (t.showLabel !== false) txt(g, tx-TB-6, ty+5, `(${t.label})`, {"text-anchor":"end", class:"tdes"});
    const tc = segText(g, tx+TB+8, ty+5, t.cond, "tcond");
    timerText(g, tx+TB+8 + tc.getComputedTextLength() + (t.cond ? 10 : 0), ty+5, t.conditionRef, S);
    if (t.comment) {
      const prev = g.querySelectorAll(".timer, .tmr");
      const fin = Math.max(tx+TB+8 + tc.getComputedTextLength() + (t.cond ? 14 : 0), ...[...prev].map(n => n.getBBox().x + n.getBBox().width + 8));
      comentario(g, fin, ty, t.comment);
    }
  });
  // Exactamente los mismos recorridos que Qt y la detección del ratón.
  (M.links || []).forEach(e => {
    el("path", {d:e.pts.map((p,i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" "), class:"link"}, links);
    (e.arrows || []).forEach(a => el("path", {d:a.pts.map((p,i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ")+" Z", class:"arrow"}, links));
  });
  (M.bars || []).forEach(b => {
    const x = b.x + SX;
    [0, ...(b.kind === "Y" ? [4] : [])].forEach(dy => el("line", {x1:x, x2:x+b.ancho, y1:b.y+dy, y2:b.y+dy, class:"dbl"}, links));
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
    const xr = drawActions(g, p, s.actions, S, s.actionLayout);
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
  const b = svg.getBBox();
  svg.setAttribute("viewBox", `${b.x-14} ${b.y-14} ${b.width+28} ${b.height+28}`);
}

// Parciales según las figuras de la norma:
// - recinto (P43-02): marco de trazo continuo; arriba, la etapa encapsulante; abajo, el nombre del parcial;
// - parcial (P40-02): marco redondeado con su nombre abajo; un parcial hijo se dibuja dentro de su padre;
// - expansión de macroetapa (P47-03): sin marco; trazos discontinuos de la macroetapa a su entrada y a su salida.
function drawFrames(g, M, pos) {
  const parts = M.partials || [];
  const box = {};
  const own = pid => M.steps.filter(s => s.partial === pid).map(s => pos[s.id])
    .concat(M.transitions.filter(t => t.partial === pid).map(t => ({x: t.x + SX, y: t.y})));
  function frame(pid) {
    if (box[pid] !== undefined) return box[pid];
    const pts = own(pid);
    let b = pts.length ? {x0: Math.min(...pts.map(p => p.x)) - H - 26, x1: Math.max(...pts.map(p => p.x)) + H + 70,
                          y0: Math.min(...pts.map(p => p.y)) - H - 22, y1: Math.max(...pts.map(p => p.y)) + H + 22} : null;
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
      if (!m || !pos[m.entry] || !pos[m.exit]) return;
      const mp = pos[m.id], ep = pos[m.entry], sp = pos[m.exit];
      el("path", {d:`M${mp.x+H},${mp.y-H} L${ep.x-H},${ep.y-H} M${mp.x+H},${mp.y+H} L${sp.x-H},${sp.y+H}`, class:"expline"}, g);
      return;
    }
    const b = frame(pt.id);
    if (!b) return;
    if (pt.kind === "enclosure") {
      el("rect", {x:b.x0, y:b.y0, width:b.x1-b.x0, height:b.y1-b.y0, class:"frame enclosure"}, g);
      txt(g, (b.x0 + b.x1) / 2, b.y0 + 5, nameOf(M, pt.ownerStep), {"text-anchor":"middle", class:"framelabel"});
      txt(g, b.x0 + 30, b.y1 + 5, pt.label, {class:"framelabel"});
    } else {
      el("rect", {x:b.x0, y:b.y0, width:b.x1-b.x0, height:b.y1-b.y0, rx:16, class:"frame"}, g);
      txt(g, b.x1 - 30, b.y1 + 5, pt.label, {"text-anchor":"end", class:"framelabel"});
    }
  });
}

// Lo que sobresale la marca de una acción por encima y por debajo de su caja (condición, flecha, banderita)
function actionExtra(a) {
  if (a.kind === "continuous" && a.cond) return [20, 0];
  return {event:[24, 0], activation:[20, 0], deactivation:[0, 20]}[a.trigger] || [0, 0];
}

// Una acción con su caja (a la derecha de ax, centrada en cy) y sus marcas. El ancho es el de su texto y, si lleva
// condición o evento encima, el que éstos necesitan para no invadir a la caja vecina; las cajas de una columna miden
// lo mismo (el mayor), por eso se devuelven los rectángulos para ajustarlos al final.
function drawAction(g, ax, cy, a, S) {
  const on = a.kind === "continuous" ? !!(S.outputs && S.outputs[a.target] && S.outputs[a.target].value)
    : a.kind === "force" ? (S.forces || []).some(f => f.order === a.id) : false;
  const ga = el("g", {class:`act ${on?"on":""} ${a.kind === "force" ? "force" : ""}`}, g);
  const rect = el("rect", {x:ax, y:cy-H, height:2*H, width:ACT_MIN}, ga);
  const inner = a.kind === "force" ? el("rect", {x:ax+3, y:cy-H+3, height:2*H-6, width:ACT_MIN-6, class:"inner"}, ga) : null;
  const label = segText(ga, ax + 12, cy + 5, a.text, "atext");
  let w = Math.max(ACT_MIN, label.getComputedTextLength() + 24);
  const mx = ax + 12, top = cy - H, bottom = cy + H;
  if (a.kind === "continuous" && a.cond) {             // acción condicionada: trazo y condición
    el("line", {x1:mx, x2:mx, y1:top, y2:top-14, class:"amark"}, ga);
    const ac = segText(ga, mx+5, top-4, a.cond, "acond");
    w = Math.max(w, 12 + 5 + ac.getComputedTextLength() + 8);
    timerText(ga, mx+5 + ac.getComputedTextLength() + 8, top-4, a.condRef, S);
  } else if (a.trigger === "activation") {            // memorizada al activar: flecha hacia arriba
    el("line", {x1:mx, x2:mx, y1:top, y2:top-11, class:"amark"}, ga);
    el("path", {d:`M${mx-5},${top-10} L${mx},${top-19} L${mx+5},${top-10} Z`, class:"ahead"}, ga);
  } else if (a.trigger === "deactivation") {          // memorizada al desactivar: flecha hacia abajo
    el("line", {x1:mx, x2:mx, y1:bottom, y2:bottom+11, class:"amark"}, ga);
    el("path", {d:`M${mx-5},${bottom+10} L${mx},${bottom+19} L${mx+5},${bottom+10} Z`, class:"ahead"}, ga);
  } else if (a.trigger === "event") {                 // memorizada por evento: banderita y evento
    el("line", {x1:mx, x2:mx, y1:top, y2:top-20, class:"amark"}, ga);
    el("path", {d:`M${mx},${top-20} L${mx-9},${top-15} L${mx},${top-10} Z`, class:"ahead"}, ga);
    const ev = segText(ga, mx+5, top-11, a.event, "acond");
    w = Math.max(w, 12 + 5 + ev.getComputedTextLength() + 8);
    timerText(ga, mx+5 + ev.getComputedTextLength() + 8, top-11, a.condRef, S);
  }
  const ajustar = ancho => { rect.setAttribute("width", ancho); if (inner) inner.setAttribute("width", ancho - 6); };
  ajustar(w);
  return {w, ajustar};
}

// Acciones a la derecha de la etapa, del alto de la etapa. Cuatro colocaciones (figuras (1)–(3) de la norma): "fila"
// (por defecto; cajas contiguas, la representación (2)), "fila-separada" (cajas separadas, unidas a una línea común que
// sale de la etapa), "matriz-2" (cuadrícula de dos columnas, de izquierda a derecha y de arriba abajo; una barra vertical
// común a su izquierda con una derivación a cada fila: la de la segunda columna pasa por debajo de la caja de la primera y
// sube a la suya) y "columna" (una debajo de otra, unidas por una línea vertical que sale de la etapa)
function drawActions(g, p, actions, S, layout = "fila") {
  if (!actions.length) return;
  let ax = p.x + H + ACT_LINK;
  el("line", {x1:p.x+H, x2:ax, y1:p.y, y2:p.y, class:"link"}, g);
  const linea = d => el("path", {d, class:"link", fill:"none"}, g);
  if (layout === "columna") {
    const ys = [p.y];
    for (let i = 1; i < actions.length; i++)
      ys.push(ys[i-1] + 2*H + Math.max(ACT_COL, actionExtra(actions[i-1])[1] + actionExtra(actions[i])[0] + 4));
    const bx = p.x + H + ACT_LINK / 2;
    if (ys.length > 1) {
      linea(`M${bx},${p.y} V${ys[ys.length-1]}`);
      ys.slice(1).forEach(cy => linea(`M${bx},${cy} H${ax}`));
    }
    const cajas = actions.map((a, i) => drawAction(g, ax, ys[i], a, S));
    const ancho = Math.max(...cajas.map(c => c.w));
    cajas.forEach(c => c.ajustar(ancho));
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
    c1.forEach(c => c.ajustar(w1));
    const x2 = ax + w1 + ACT_GAP;
    const c2 = filas.map((f, n) => f.length > 1 ? drawAction(g, x2, ys[n], f[1], S) : null).filter(c => c);
    const w2 = c2.length ? Math.max(...c2.map(c => c.w)) : 0;
    c2.forEach(c => c.ajustar(w2));
    if (actions.length > 1) {
      linea(`M${bx},${p.y} V${filas[filas.length-1].length > 1 ? canales[canales.length-1] : ys[ys.length-1]}`);
      ys.slice(1).forEach(cy => linea(`M${bx},${cy} H${ax}`));
      filas.forEach((f, n) => { if (f.length > 1) linea(`M${bx},${canales[n]} H${x2-14} V${ys[n]} H${x2}`); });
    }
    return c2.length ? x2 + w2 : ax + w1;
  }
  if (layout === "fila-separada") {
    const entradas = [];
    actions.forEach((a, i) => {
      if (i) { ax += ACT_GAP; entradas.push(ax - 14); }
      ax += drawAction(g, ax, p.y, a, S).w;
    });
    if (entradas.length) {
      const bx = p.x + H + ACT_LINK / 2, yb = p.y + H + ACT_BUS;
      linea(`M${bx},${p.y} V${yb} H${entradas[entradas.length-1]}`);
      entradas.forEach(ex => linea(`M${ex},${yb} V${p.y} H${ex+14}`));
    }
    return ax;
  }
  actions.forEach(a => { ax += drawAction(g, ax, p.y, a, S).w; });
  return ax;
}
