// Dibujo de un grafcet con la notación gráfica de la norma (tablas 1–7). Lo usan el banco de pruebas y el
// comparador de decisiones. Las proporciones se tomaron por inspección visual de las imágenes de la norma
// aportadas por el usuario; no se copia ningún activo.
const NS = "http://www.w3.org/2000/svg";
// Unidad: lado de la etapa = 2·H
const SX = 100;       // margen izquierdo del dibujo
const H = 22;         // semilado de la etapa cuadrada
const TB = 14;        // semilongitud del trazo de transición (≈0,65 del lado)
const ACT_LINK = 26;  // enlace etapa–acción (≈0,6 del lado)
const ACT_MIN = 80;   // anchura mínima de una acción

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

// M: modelo de la vista (etapas, transiciones, acciones); S: estado observado del motor
function drawDiagram(svg, M, S) {
  svg.innerHTML = "";
  svg.setAttribute("viewBox", "0 0 640 600");
  const pos = {}; M.steps.forEach(s => pos[s.id] = {x:s.x+SX, y:s.y});
  const minX = Math.min(...M.steps.map(s=>s.x)) + SX;
  const situation = new Set(S.situation || []), virtual = new Set(S.virtual || []);
  const unstable = new Set(S.unstable || []);
  const cleared = new Set(S.lastCleared || []);
  const blk = S.blocked, reached = new Set(blk ? blk.reached : []);
  const links = el("g", {}, svg), bars = el("g", {}, svg), steps = el("g", {}, svg);
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
      const lx = minX - 70, top = p.y - H - 16;
      el("path", {d:`M${tx},${ty} V${ty+14} H${lx} V${top} H${p.x} V${p.y-H}`, class:"link"}, links);
      const my = (ty + 14 + top) / 2;
      el("path", {d:`M${lx-5},${my+6} L${lx},${my-4} L${lx+5},${my+6} Z`, class:"arrow"}, links);
    });
    if (!pre.length) el("path", {d:`M${tx},${ty-16} V${ty}`, class:"link"}, links);    // transición fuente
    if (!post.length) el("path", {d:`M${tx},${ty} V${ty+16}`, class:"link"}, links);   // transición sumidero
    const cls = ["tr", ob.validated?"validated":"", ob.fireable?"fireable":"", cleared.has(t.id)?"cleared":"",
                 blk && blk.element === t.id ? "question" : ""].join(" ");
    const g = el("g", {class:cls}, bars);
    el("title", {}, g).textContent = `Transición ${t.id}: validada ${ob.validated?"sí":"no"}, receptividad ${ob.receptivity?"verdadera":"falsa"}`;
    el("line", {x1:tx-TB, x2:tx+TB, y1:ty, y2:ty, class:"bar"}, g);
    txt(g, tx-TB-6, ty+5, `(${t.id})`, {"text-anchor":"end", class:"tdes"});
    segText(g, tx+TB+8, ty+5, t.cond, "tcond");
  });
  M.steps.forEach(s => {
    const p = pos[s.id], stale = !!blk && situation.has(s.id), act = !blk && situation.has(s.id);
    const cand = !!blk && reached.has(s.id) && !stale, vir = virtual.has(s.id) && !act;
    const uns = !vir && !act && !stale && !cand && unstable.has(s.id);
    const g = el("g", {class:`step ${act?"active":""} ${vir||uns?"virtual":""} ${stale?"stale":""} ${cand?"cand":""}`}, steps);
    el("title", {}, g).textContent = `Etapa ${s.id}${s.initial?" (inicial)":""}${s.partial?` · parcial ${s.partial}`:""}: ` +
      (stale ? "último estado estable conservado" : cand ? "alcanzada antes del punto en cuestión, sin confirmar" :
       act ? "activa" : vir ? "inestable (en recorrido)" : uns ? "fue inestable en el último instante" : "inactiva");
    el("rect", {x:p.x-H, y:p.y-H, width:2*H, height:2*H, class:"outer"}, g);
    if (s.initial) el("rect", {x:p.x-H+4, y:p.y-H+4, width:2*H-8, height:2*H-8, fill:"none"}, g);
    txt(g, p.x, p.y+3, s.id, {"text-anchor":"middle"});
    if (s.partial) txt(g, p.x-H, p.y-H-5, s.partial, {class:"tag ptag"});
    if (act) el("circle", {cx:p.x, cy:p.y+12, r:3.5, class:"token"}, g);
    if (vir) txt(g, p.x, p.y+H+13, "inestable", {"text-anchor":"middle", class:"tag vtag"});
    if (uns) txt(g, p.x, p.y+H+13, "fue inestable", {"text-anchor":"middle", class:"tag vtag"});
    if (stale) txt(g, p.x, p.y+H+13, "último estable", {"text-anchor":"middle", class:"tag stag"});
    if (cand) txt(g, p.x, p.y+H+13, "alcanzada, sin confirmar", {"text-anchor":"middle", class:"tag ctag"});
    drawActions(g, p, s.actions, S);
  });
  const b = svg.getBBox();
  svg.setAttribute("viewBox", `${b.x-14} ${b.y-14} ${b.width+28} ${b.height+28}`);
}

// Acciones a la derecha de la etapa, del alto de la etapa y contiguas (representación (2) de la norma)
function drawActions(g, p, actions, S) {
  if (!actions.length) return;
  let ax = p.x + H + ACT_LINK;
  el("line", {x1:p.x+H, x2:ax, y1:p.y, y2:p.y, class:"link"}, g);
  actions.forEach(a => {
    const on = a.kind === "continuous" && S.outputs && S.outputs[a.target] && S.outputs[a.target].value;
    const ga = el("g", {class:`act ${on?"on":""}`}, g);
    const rect = el("rect", {x:ax, y:p.y-H, height:2*H, width:ACT_MIN}, ga);
    const label = segText(ga, ax + 12, p.y + 5, a.text, "atext");
    const w = Math.max(ACT_MIN, label.getComputedTextLength() + 24);
    rect.setAttribute("width", w);
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
