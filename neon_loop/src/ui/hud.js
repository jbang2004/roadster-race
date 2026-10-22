// HUD: speed gauge, power bar, thruster gas, position / lap, lap times, mini-map, gaps, notifications, wrong-way, edge glow.
// DOM is built once; update() only writes values that changed.
import { fmtTimeParts, fmtGap, clamp, smooth, num, LIVERY_COLORS } from './format.js';
import { createMinimap } from './minimap.js';
import { THRUST } from '../game/params.js';

export function h(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}
const NS = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs = {}) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
const setText = (el, s) => { if (el._t !== s) { el._t = s; el.textContent = s; } };

// gauge geometry (viewBox 396 × 312)
const CX = 198, CY = 170, R = 154, A0 = 150, SWEEP = 240, VMAX = 360;
const pt = (deg, r) => [CX + r * Math.cos(deg * Math.PI / 180), CY + r * Math.sin(deg * Math.PI / 180)];
const ZONE_LABELS = {
  boulevard: ['霓虹大道', 'BOULEVARD'], street: ['办公峡谷', 'OFFICE CANYON'], docks: ['港口码头', 'DOCKS'], ramp: ['上行匝道', 'RAMP'],
  expressway: ['高架快速路', 'EXPRESSWAY'], descent: ['下坡路堑', 'DESCENT'], tunnel: ['海底隧道', 'TUNNEL'], market: ['九龙夜市', 'NIGHT MARKET'],
};
export { ZONE_LABELS };

export function createHUD(root, track) {
  const el = h('div', 'nl-hud');
  const edge = h('div', 'nl-edge'), edge2 = h('div', 'nl-edge2'), flash = h('div', 'nl-flash');
  root.prepend(edge, edge2);
  root.append(flash);

  // ---- top-left: position + lap ----
  const tl = h('div', 'blk tl');
  const pos = h('div', 'stat pos', `<div class="cap"><span class="zh">位置</span>POSITION</div><div class="big num"><b>1</b><i>/8</i></div>`);
  const lap = h('div', 'stat lap', `<div class="cap"><span class="zh">圈数</span>LAP</div><div class="big num"><b>1</b><i>/3</i></div>`);
  tl.append(pos, lap);
  const posB = pos.querySelector('b'), posI = pos.querySelector('i'), lapB = lap.querySelector('b'), lapI = lap.querySelector('i');

  // ---- top-right: timing ----
  const tr = h('div', 'blk tr');
  tr.innerHTML = `
    <div class="cap"><span class="zh">当前圈</span>CURRENT</div>
    <div class="cur num"><span class="a">0:00</span><small class="b">.000</small></div>
    <div class="rule"></div>
    <div class="row last"><div class="cap"><span class="zh">上一圈</span>LAST</div><div class="v num"><span class="a">--:--</span><small class="b">.---</small></div></div>
    <div class="row best"><div class="cap"><span class="zh">最快圈</span>BEST</div><div class="v num"><span class="a">--:--</span><small class="b">.---</small></div></div>`;
  const q = (s) => tr.querySelector(s);
  const curA = q('.cur .a'), curB = q('.cur .b'), lastA = q('.last .a'), lastB = q('.last .b'), bestA = q('.best .a'), bestB = q('.best .b'), bestV = q('.best .v');

  // ---- bottom-left: minimap + district ----
  const bl = h('div', 'blk bl');
  const mapwrap = h('div', 'mapwrap');
  const map = createMinimap(track);
  mapwrap.append(map.canvas);
  const mapzone = h('div', 'mapzone', `<span class="zh">霓虹大道</span><span class="en">BOULEVARD</span>`);
  bl.append(mapwrap, mapzone);
  const zoneZh = mapzone.querySelector('.zh'), zoneEn = mapzone.querySelector('.en');

  // ---- bottom-right: speed gauge + power ----
  const br = h('div', 'blk br');
  const gauge = h('div', 'gauge');
  const sv = svg('svg', { viewBox: '0 0 396 312' });
  const defs = svg('defs');
  const grad = svg('linearGradient', { id: 'nlg', gradientUnits: 'userSpaceOnUse', x1: 64, y1: 0, x2: 332, y2: 0 });
  for (const [o, c] of [[0, '#2ad8ff'], [0.55, '#bff8ff'], [0.82, '#ffffff'], [1, '#ff49d6']]) grad.append(svg('stop', { offset: o, 'stop-color': c }));
  defs.append(grad); sv.append(defs);
  const [ax, ay] = pt(A0, R), [bx, by] = pt(A0 + SWEEP, R);
  const arcD = `M ${ax.toFixed(2)} ${ay.toFixed(2)} A ${R} ${R} 0 1 1 ${bx.toFixed(2)} ${by.toFixed(2)}`;
  sv.append(svg('path', { d: arcD, fill: 'none', stroke: 'rgba(170,225,245,.13)', 'stroke-width': 3, 'stroke-linecap': 'round' }));
  const glowP = svg('path', { d: arcD, fill: 'none', stroke: 'url(#nlg)', 'stroke-width': 13, 'stroke-linecap': 'round', opacity: .16, pathLength: 100 });
  const arcP = svg('path', { d: arcD, fill: 'none', stroke: 'url(#nlg)', 'stroke-width': 3.2, 'stroke-linecap': 'round', pathLength: 100 });
  for (const p of [glowP, arcP]) { p.style.strokeDasharray = '100 200'; p.style.strokeDashoffset = '100'; }
  const ticks = [];
  for (let v = 0; v <= VMAX; v += 20) {
    const major = v % 60 === 0, a = A0 + (v / VMAX) * SWEEP;
    const [x1, y1] = pt(a, R - 9), [x2, y2] = pt(a, R - (major ? 19 : 14));
    const t = svg('line', { x1, y1, x2, y2, stroke: 'rgba(190,230,248,.30)', 'stroke-width': major ? 1.6 : 1 });
    sv.append(t); ticks.push({ el: t, v, lit: false });
    if (major) {
      const [lx, ly] = pt(a, R + 17);
      const tx = svg('text', { x: lx, y: ly + 3.5, 'text-anchor': 'middle', fill: 'rgba(205,234,248,.66)', 'font-size': 11, 'font-weight': 400, 'letter-spacing': '.04em' });
      tx.setAttribute('font-family', 'ui-sans-serif, -apple-system, "SF Pro Display", sans-serif'); tx.textContent = String(v);
      sv.append(tx);
    }
  }
  const tip = svg('circle', { r: 4.2, fill: '#fff', cx: ax, cy: ay });
  tip.style.filter = 'drop-shadow(0 0 5px #3ee8ff)';
  sv.append(glowP, arcP, tip);
  gauge.append(sv);
  const readout = h('div', 'readout', `<div class="spd num">0</div><div class="unit"><span class="mode">D</span><span class="en">KM/H</span><span class="zh">时速</span></div>`);
  const drive = readout.querySelector('.mode');
  gauge.append(readout);
  const spdEl = readout.querySelector('.spd');
  const power = h('div', 'power', `
    <div class="hd"><div class="cap pw"><span class="zh">功率</span>POWER</div><div class="kw num"><span>0</span><small>KW</small></div></div>
    <div class="bar"><div class="f drv"></div><div class="f reg"></div><div class="zero"></div></div>`);
  const pwCap = power.querySelector('.cap'), kwEl = power.querySelector('.kw span');
  const drv = power.querySelector('.drv'), reg = power.querySelector('.reg'), zero = power.querySelector('.zero');
  const DRIVE_MAX = 1000, REGEN_MAX = 300, zeroPct = REGEN_MAX / (DRIVE_MAX + REGEN_MAX) * 100;
  zero.style.left = zeroPct + '%';
  drv.style.left = zeroPct + '%'; drv.style.width = (100 - zeroPct) + '%';
  reg.style.left = '0'; reg.style.width = zeroPct + '%';
  // cold-gas tank: seconds of thrust left, one tick per second of valve time
  const gas = h('div', 'gas', `
    <div class="hd"><div class="cap"><span class="zh">冷气推进</span>THRUST</div><div class="sec num"><span>4.0</span><small>S</small></div></div>
    <div class="bar"><div class="f"></div>${Array.from({ length: Math.round(THRUST.duration) - 1 }, (_, i) => `<i style="left:${(i + 1) / THRUST.duration * 100}%"></i>`).join('')}</div>`);
  const gasF = gas.querySelector('.f'), gasS = gas.querySelector('.sec span');
  br.append(gauge, power, gas);

  // ---- bottom-centre: gaps ----
  const gaps = h('div', 'blk gaps');
  const mkGap = (cls, arrow, zh, en) => h('div', `gap ${cls} none`, `<span class="arr">${arrow}</span><span class="cap" style="margin:0"><span class="zh" style="margin-right:6px">${zh}</span></span><span class="sw"></span><span class="nm zh">—</span><span class="t num">--.--</span>`);
  const gapA = mkGap('a', '▲', '前车'), gapB = mkGap('b', '▼', '后车');
  gaps.append(gapA, gapB);
  const ga = { nm: gapA.querySelector('.nm'), t: gapA.querySelector('.t'), sw: gapA.querySelector('.sw') };
  const gb = { nm: gapB.querySelector('.nm'), t: gapB.querySelector('.t'), sw: gapB.querySelector('.sw') };

  // ---- notifications ----
  const notes = h('div', 'blk notes');
  const note = h('div', 'note', `<div class="cap"></div><div class="main zh"></div><div class="sub zh"></div><div class="ln"></div>`);
  notes.append(note);
  const nCap = note.querySelector('.cap'), nMain = note.querySelector('.main'), nSub = note.querySelector('.sub');
  const queue = []; let cur = null, curT = 0;
  function showNote(n) {
    cur = n; curT = n.ms / 1000; el.classList.add('note-on');
    note.className = 'note ' + (n.kind || '');
    nCap.textContent = n.en || ''; nMain.textContent = n.zh || ''; nSub.textContent = n.sub || '';
    nSub.style.display = n.sub ? '' : 'none';
    note.style.setProperty('--dur', curT + 's');
    void note.offsetWidth; note.classList.add('show');
  }
  /** n: { kind:'rec'|'up'|'dn'|'fin'|'dist'|'', zh, en, sub?, ms=2800, prio=1 } */
  function notify(n) {
    n = { ms: 2800, prio: 1, ...n };
    if (cur && n.prio > cur.prio) { queue.unshift(n); showNote(queue.shift()); return; }
    if (!cur) { showNote(n); return; }
    if (n.prio <= 0 && queue.length) return;                 // low-priority chatter never piles up
    queue.push(n); if (queue.length > 3) queue.splice(0, queue.length - 3);
  }
  const wrong = h('div', 'blk wrong', `<div class="cap">警告 WARNING</div><div class="main zh">逆行</div><div class="cap" style="margin-top:6px">WRONG WAY</div>`);
  const toast = h('div', 'blk toast', `<span class="cap"></span><span class="zh">—</span>`);
  const toastV = toast.querySelector('.zh'), toastC = toast.querySelector('.cap'); let toastT = 0;

  el.append(...['tl', 'tr', 'bl', 'br', 'bc', 'nt'].map(k => h('div', 'scrim ' + k)), tl, tr, bl, br, gaps, notes, wrong, toast);
  root.append(el);

  let lastBest = null, lastLit = -1, flashV = 0, lastPos = 0, lastLap = 0, lastTotal = 0, zoneIdx = -1;

  function update(dt, S) {
    const p = S.player; if (!p) return;
    const kmh = Math.abs(num(p.speed)) * 3.6;
    // speed
    setText(spdEl, String(Math.round(kmh)));
    const pct = clamp(kmh / VMAX, 0, 1) * 100;
    const off = (100 - pct).toFixed(2);
    if (arcP._o !== off) {
      arcP._o = off; arcP.style.strokeDashoffset = off; glowP.style.strokeDashoffset = off;
      const [tx, ty] = pt(A0 + (pct / 100) * SWEEP, R); tip.setAttribute('cx', tx.toFixed(1)); tip.setAttribute('cy', ty.toFixed(1));
    }
    const lit = Math.floor(kmh / 20 + 0.001);
    if (lit !== lastLit) { lastLit = lit; for (const t of ticks) { const on = t.v <= lit * 20 && kmh > 0.5; if (on !== t.lit) { t.lit = on; t.el.setAttribute('stroke', on ? 'rgba(210,248,255,.95)' : 'rgba(190,230,248,.30)'); } } }
    const rev = num(p.speed) < -0.8; setText(drive, rev ? 'R' : 'D'); drive.classList.toggle('r', rev);
    // power
    const kw = num(p.motor?.power);
    const dv = clamp(kw / DRIVE_MAX, 0, 1), rv = clamp(-kw / REGEN_MAX, 0, 1);
    const dvS = dv.toFixed(3), rvS = rv.toFixed(3);
    if (drv._v !== dvS) { drv._v = dvS; drv.style.transform = `scaleX(${dvS})`; }
    if (reg._v !== rvS) { reg._v = rvS; reg.style.transform = `scaleX(${rvS})`; }
    setText(kwEl, String(Math.round(Math.abs(kw))));
    const isReg = kw < -2;
    if (pwCap._c !== isReg) { pwCap._c = isReg; pwCap.classList.toggle('reg', isReg); pwCap.innerHTML = isReg ? '<span class="zh">回收</span>REGEN' : '<span class="zh">功率</span>POWER'; }

    // thruster gas
    const g = clamp(num(p.boost?.gas, 1), 0, 1), jl = num(p.boost?.level);
    const gS = g.toFixed(3); if (gasF._v !== gS) { gasF._v = gS; gasF.style.transform = `scaleX(${gS})`; }
    setText(gasS, (g * THRUST.duration).toFixed(1));
    const gst = jl > 0.05 ? 'on' : g < 0.02 ? 'empty' : g < 0.25 ? 'low' : g < 0.999 ? 'fill' : '';
    if (gas._s !== gst) { gas._s = gst; gas.className = 'gas' + (gst ? ' ' + gst : ''); }

    // position / lap
    const place = p.race?.place ?? 1, total = S.total, laps = S.laps, lapN = Math.min(p.race?.lap ?? 1, laps);
    if (place !== lastPos) {
      setText(posB, String(place));
      if (lastPos && S.racing) { posB.classList.remove('up', 'dn'); void posB.offsetWidth; posB.classList.add(place < lastPos ? 'up' : 'dn'); }
      lastPos = place;
    }
    if (total !== lastTotal) { lastTotal = total; setText(posI, '/' + total); }
    if (lapN !== lastLap) { lastLap = lapN; setText(lapB, String(lapN)); }
    setText(lapI, '/' + laps);

    // times
    const [ca, cb] = fmtTimeParts(S.curLap); setText(curA, ca); setText(curB, cb);
    const [la, lb] = fmtTimeParts(p.race?.lastLap > 0 ? p.race.lastLap : null); setText(lastA, la); setText(lastB, lb);
    const bestNow = p.race?.bestLap > 0 && Number.isFinite(p.race.bestLap) ? p.race.bestLap : null;
    const [ba, bb] = fmtTimeParts(bestNow); setText(bestA, ba); setText(bestB, bb);
    if (bestNow !== lastBest) { if (lastBest != null && bestNow != null && bestNow < lastBest) { bestV.classList.remove('flash'); void bestV.offsetWidth; bestV.classList.add('flash'); } lastBest = bestNow; }

    // gaps
    const ahead = S.carAhead, behind = S.carBehind;
    gapA.classList.toggle('none', !ahead); gapB.classList.toggle('none', !behind);
    setText(ga.nm, ahead ? ahead.name ?? '—' : '—'); setText(gb.nm, behind ? behind.name ?? '—' : '—');
    setText(ga.t, ahead ? fmtGap(Math.abs(num(p.race?.gapAhead, NaN)), true) : '--.--'); setText(gb.t, behind ? fmtGap(-Math.abs(num(p.race?.gapBehind, NaN)), true) : '--.--');
    if (ahead) ga.sw.style.background = LIVERY_COLORS[ahead.livery ?? 1] ?? '#fff';
    if (behind) gb.sw.style.background = LIVERY_COLORS[behind.livery ?? 1] ?? '#fff';

    // district
    const zi = track.zone[clamp(p.track?.i ?? 0, 0, track.N - 1) | 0];
    if (zi !== zoneIdx) {
      const first = zoneIdx < 0; zoneIdx = zi;
      const z = ZONE_LABELS[track.zoneNames[zi]] ?? ['—', '—'];
      setText(zoneZh, z[0]); setText(zoneEn, z[1]);
      if (!first && S.racing) notify({ kind: 'dist', zh: z[0], en: z[1], ms: 2600, prio: 0 });
    }

    // notification clock
    if (cur) { curT -= dt; if (curT <= 0) { cur = null; note.classList.remove('show'); if (queue.length) showNote(queue.shift()); else el.classList.remove('note-on'); } }
    wrong.classList.toggle('on', S.wrongWay);
    if (toastT > 0) { toastT -= dt; if (toastT <= 0) toast.classList.remove('on'); }

    // atmospherics
    const eo = smooth(120, 330, kmh) * 0.9 + (S.boost || 0);
    const eS = eo.toFixed(2); if (edge._o !== eS) { edge._o = eS; edge.style.opacity = eS; }
    const bo = clamp(num(p.input?.brake), 0, 1) * smooth(50, 180, kmh) * 0.85;
    const bS = bo.toFixed(2); if (edge2._o !== bS) { edge2._o = bS; edge2.style.opacity = bS; }
    if (flashV > 0.01) { flashV *= Math.exp(-dt * 4.5); flash.style.opacity = flashV.toFixed(3); } else if (flashV !== 0) { flashV = 0; flash.style.opacity = '0'; }
    map.draw(S.cars, p, S.time);
  }

  return {
    el, update, notify, map,
    resize() { const r = mapwrap.getBoundingClientRect(); if (r.width > 8) map.resize(r.width, r.height); },
    toast(capZh, capEn, text) { toastC.innerHTML = `<span class="zh">${capZh}</span>${capEn}`; toastV.textContent = text; toast.classList.add('on'); toastT = 1.8; },
    hit(k) { flashV = Math.max(flashV, clamp(k, 0.12, 0.75)); },
    setVisible(v, dim = false) { el.classList.toggle('on', v); el.classList.toggle('dim', dim); },
    resetNotes() { queue.length = 0; cur = null; note.classList.remove('show'); el.classList.remove('note-on'); },
  };
}
