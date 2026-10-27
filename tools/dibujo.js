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

// M: modelo de la vista (etapas, macroetapas, transiciones, acciones, parciales); S: estado observado del motor
function drawDiagram(svg, M, S) {
  svg.innerHTML = "";
  svg.setAttribute("viewBox", "0 0 640 600");
  const pos = {};
  M.steps.forEach(s => pos[s.id] = {x:s.x+SX, y:s.y});
  (M.macros || []).forEach(m => pos[m.id] = {x:m.x+SX, y:m.y});
  const nodes = Object.values(pos);
  const minX = Math.min(...nodes.map(p=>p.x));
  // Enlace ascendente: por la izquierda del parcial de la transición, no de todo el dibujo
  const part = p => (p === "g" || p == null) ? "" : p, leftOf = {};
  M.steps.forEach(s => { const k = part(s.partial); leftOf[k] = Math.min(leftOf[k] ?? Infinity, pos[s.id].x); });
  (M.macros || []).forEach(m => { leftOf[""] = Math.min(leftOf[""] ?? Infinity, pos[m.id].x); });
  const situation = new Set(S.situation || []), virtual = new Set(S.virtual || []);
  const unstable = new Set(S.unstable || []);
  const cleared = new Set(S.lastCleared || []);
  const blk = S.blocked, reached = new Set(blk ? blk.reached : []);
  const frames = el("g", {}, svg), links = el("g", {}, svg), bars = el("g", {}, svg), steps = el("g", {}, svg);
  drawFrames(frames, M, pos);
  M.transitions.forEach(t => {
    const tx = t.x + SX, ty = t.y, ob = (S.transitions||{})[t.id] || {};
    const pre = t.pre.map(p => pos[p]), post = t.post.map(p => pos[p]);
    if (pre.length > 1) {   // sincronización: doble trazo sobre la transición
      const xs = pre.map(p=>p.x), yy = ty - 14;
      el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:yy, y2:yy, class:"dbl"}, links);
      el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:yy-4, y2:yy-4, class:"dbl"}, links);
      pre.forEach(p => el("path", {d:`M${p.x},${p.y+H} V${yy-4}`, class:"link"}, links));
      el("path", {d:`M${tx},${yy} V${ty}`, class:"link"}, links);
    } else pre.forEach(p => el("path", {d:`M${p.x},${p.y+H} V${(p.y+H+ty)/2} H${tx} V${ty}`, class:"link"}, links));
    const down = post.filter(p => p.y > ty), up = post.filter(p => p.y <= ty);
    if (down.length > 1) {  // divergencia simultánea: doble trazo bajo la transición
      const xs = down.map(p=>p.x), yy = ty + 14;
      el("path", {d:`M${tx},${ty} V${yy}`, class:"link"}, links);
      el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:yy, y2:yy, class:"dbl"}, links);
      el("line", {x1:Math.min(...xs)-8, x2:Math.max(...xs)+8, y1:yy+4, y2:yy+4, class:"dbl"}, links);
      down.forEach(p => el("path", {d:`M${p.x},${yy+4} V${p.y-H}`, class:"link"}, links));
    } else down.forEach(p => el("path", {d:`M${tx},${ty} V${(ty+p.y-H)/2} H${p.x} V${p.y-H}`, class:"link"}, links));
    up.forEach(p => {       // enlace ascendente con flecha
      const lx = Math.min(leftOf[part(t.partial)] ?? minX, tx) - 70, top = p.y - H - 16;
      el("path", {d:`M${tx},${ty} V${ty+14} H${lx} V${top} H${p.x} V${p.y-H}`, class:"link"}, links);
      const my = (ty + 14 + top) / 2;
      el("path", {d:`M${lx-5},${my+6} L${lx},${my-4} L${lx+5},${my+6} Z`, class:"arrow"}, links);
    });
    if (!pre.length) el("path", {d:`M${tx},${ty-16} V${ty}`, class:"link"}, links);    // transición fuente
    if (!post.length) el("path", {d:`M${tx},${ty} V${ty+16}`, class:"link"}, links);   // transición sumidero
    const cls = ["tr", ob.validated?"validated":"", ob.fireable?"fireable":"", cleared.has(t.id)?"cleared":"",
                 blk && blk.element === t.id ? "question" : ""].join(" ");
    const g = el("g", {class:cls}, bars);
    el("title", {}, g).textContent = `Transición ${t.id}: validada ${ob.validated?"sí":"no"}, receptividad ${ob.receptivity?"verdadera":"falsa"}` +
      (ob.forced ? "; su parcial está forzado y no evoluciona" : "");
    el("line", {x1:tx-TB, x2:tx+TB, y1:ty, y2:ty, class:"bar"}, g);
    txt(g, tx-TB-6, ty+5, `(${t.id})`, {"text-anchor":"end", class:"tdes"});
    segText(g, tx+TB+8, ty+5, t.cond, "tcond");
  });
  M.steps.forEach(s => {
    const p = pos[s.id], stale = !!blk && situation.has(s.id), act = !blk && situation.has(s.id);
    const cand = !!blk && reached.has(s.id) && !stale, vir = virtual.has(s.id) && !act;
    const uns = !vir && !act && !stale && !cand && unstable.has(s.id);
    const g = el("g", {class:`step ${act?"active":""} ${vir||uns?"virtual":""} ${stale?"stale":""} ${cand?"cand":""}`}, steps);
    const kind = {enclosing:" (encapsulante)", entry:" (entrada de la expansión)", exit:" (salida de la expansión)"}[s.kind] || "";
    el("title", {}, g).textContent = `Etapa ${s.id}${s.initial?" (inicial)":""}${kind}${s.partial?` · parcial ${s.partial}`:""}` +
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
    txt(g, p.x, p.y+3, s.id, {"text-anchor":"middle"});
    if (s.activation) txt(g, p.x-H-5, p.y+5, "*", {"text-anchor":"end", class:"amark-act"});
    if (act) el("circle", {cx:p.x, cy:p.y+12, r:3.5, class:"token"}, g);
    if (vir) txt(g, p.x, p.y+H+13, "inestable", {"text-anchor":"middle", class:"tag vtag"});
    if (uns) txt(g, p.x, p.y+H+13, "fue inestable", {"text-anchor":"middle", class:"tag vtag"});
    if (stale) txt(g, p.x, p.y+H+13, "último estable", {"text-anchor":"middle", class:"tag stag"});
    if (cand) txt(g, p.x, p.y+H+13, "alcanzada, sin confirmar", {"text-anchor":"middle", class:"tag ctag"});
    drawActions(g, p, s.actions, S);
  });
  (M.macros || []).forEach(m => {  // macroetapa: divisiones horizontales superior e inferior
    const p = pos[m.id], act = !!(S.macros || {})[m.id];
    const g = el("g", {class:`step macro ${act?"active":""}`}, steps);
    el("title", {}, g).textContent = `Macroetapa ${m.id} (expansión ${m.expansion}): ${act ? "activa (alguna etapa de su expansión)" : "inactiva"}`;
    el("rect", {x:p.x-H, y:p.y-H, width:2*H, height:2*H, class:"outer"}, g);
    el("line", {x1:p.x-H, x2:p.x+H, y1:p.y-H+MARK, y2:p.y-H+MARK, class:"hmark"}, g);
    el("line", {x1:p.x-H, x2:p.x+H, y1:p.y+H-MARK, y2:p.y+H-MARK, class:"hmark"}, g);
    txt(g, p.x, p.y+5, m.id, {"text-anchor":"middle"});
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
      txt(g, (b.x0 + b.x1) / 2, b.y0 + 5, pt.ownerStep, {"text-anchor":"middle", class:"framelabel"});
      txt(g, b.x0 + 30, b.y1 + 5, pt.label, {class:"framelabel"});
    } else {
      el("rect", {x:b.x0, y:b.y0, width:b.x1-b.x0, height:b.y1-b.y0, rx:16, class:"frame"}, g);
      txt(g, b.x1 - 30, b.y1 + 5, pt.label, {"text-anchor":"end", class:"framelabel"});
    }
  });
}

// Acciones a la derecha de la etapa, del alto de la etapa y contiguas (representación (2) de la norma)
function drawActions(g, p, actions, S) {
  if (!actions.length) return;
  let ax = p.x + H + ACT_LINK;
  el("line", {x1:p.x+H, x2:ax, y1:p.y, y2:p.y, class:"link"}, g);
  actions.forEach(a => {
    const on = a.kind === "continuous" ? !!(S.outputs && S.outputs[a.target] && S.outputs[a.target].value)
      : a.kind === "force" ? (S.forces || []).some(f => f.order === a.id) : false;
    const ga = el("g", {class:`act ${on?"on":""} ${a.kind === "force" ? "force" : ""}`}, g);
    const rect = el("rect", {x:ax, y:p.y-H, height:2*H, width:ACT_MIN}, ga);
    const inner = a.kind === "force" ? el("rect", {x:ax+3, y:p.y-H+3, height:2*H-6, width:ACT_MIN-6, class:"inner"}, ga) : null;
    const label = segText(ga, ax + 12, p.y + 5, a.text, "atext");
    const w = Math.max(ACT_MIN, label.getComputedTextLength() + 24);
    rect.setAttribute("width", w);
    if (inner) inner.setAttribute("width", w - 6);  // forzado: rectángulo doble
    const mx = ax + 12, top = p.y - H, bottom = p.y + H;
    if (a.kind === "continuous" && a.cond) {             // acción condicionada: trazo y condición
      el("line", {x1:mx, x2:mx, y1:top, y2:top-14, class:"amark"}, ga);
      segText(ga, mx+5, top-4, a.cond, "acond");
    } else if (a.trigger === "activation") {            // memorizada al activar: flecha hacia arriba
      el("line", {x1:mx, x2:mx, y1:top, y2:top-11, class:"amark"}, ga);
      el("path", {d:`M${mx-5},${top-10} L${mx},${top-19} L${mx+5},${top-10} Z`, class:"ahead"}, ga);
    } else if (a.trigger === "deactivation") {          // memorizada al desactivar: flecha hacia abajo
      el("line", {x1:mx, x2:mx, y1:bottom, y2:bottom+11, class:"amark"}, ga);
      el("path", {d:`M${mx-5},${bottom+10} L${mx},${bottom+19} L${mx+5},${bottom+10} Z`, class:"ahead"}, ga);
    } else if (a.trigger === "event") {                 // memorizada por evento: banderita y evento
      el("line", {x1:mx, x2:mx, y1:top, y2:top-20, class:"amark"}, ga);
      el("path", {d:`M${mx},${top-20} L${mx-9},${top-15} L${mx},${top-10} Z`, class:"ahead"}, ga);
      segText(ga, mx+5, top-11, a.event, "acond");
    }
    ax += w;
  });
}
