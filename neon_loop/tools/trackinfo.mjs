// Prints circuit statistics. Usage: node tools/trackinfo.mjs
import { getTrack, KIND_NAMES } from '../src/track/track.js';
const t0 = Date.now();
const T = getTrack();
console.log(`built in ${Date.now() - t0} ms: N=${T.N} length=${T.length.toFixed(0)} m startS=${T.startS.toFixed(1)}`);
// corners: local min radius in runs where |curv| > 1/400
let runs = [], cur = null;
for (let i = 0; i < T.N; i++) {
  const k = T.curv[i];
  if (Math.abs(k) > 1 / 400) { if (!cur) cur = { i0: i, kmax: 0, sign: Math.sign(k) }; cur.kmax = Math.max(cur.kmax, Math.abs(k)); cur.i1 = i; }
  else if (cur) { runs.push(cur); cur = null; }
}
if (cur) runs.push(cur);
for (const r of runs) console.log(`corner s=${r.i0}-${r.i1} ${r.sign > 0 ? 'L' : 'R'} minR=${(1 / r.kmax).toFixed(1)} m zone=${T.zoneNames[T.zone[r.i0]]} y=${T.py[r.i0].toFixed(1)}`);
let gmax = 0, gi = 0; for (let i = 0; i < T.N; i++) if (Math.abs(T.grade[i]) > gmax) { gmax = Math.abs(T.grade[i]); gi = i; }
console.log(`max grade ${(gmax * 100).toFixed(1)}% at s=${gi} y=${T.py[gi].toFixed(1)}`);
const kc = {}; for (let i = 0; i < T.N; i++) kc[KIND_NAMES[T.kind[i]]] = (kc[KIND_NAMES[T.kind[i]]] ?? 0) + 1; console.log('kinds (m):', kc);
const zc = {}; for (let i = 0; i < T.N; i++) zc[T.zoneNames[T.zone[i]]] = (zc[T.zoneNames[T.zone[i]]] ?? 0) + 1; console.log('zones (m):', zc);
// vertical curvature extremes
let vmin = 0, vmax = 0; for (let i = 0; i < T.N; i++) { const p = T.wrapIndex(i - 5), q = T.wrapIndex(i + 5); const k = (T.grade[q] - T.grade[p]) / 10; vmin = Math.min(vmin, k); vmax = Math.max(vmax, k); }
console.log(`vertical radius: crest ${(-1 / vmin).toFixed(0)} m, dip ${(1 / vmax).toFixed(0)} m`);
// crossover clearance: samples whose XZ is within the other road footprint at different height
let clr = Infinity; for (let i = 0; i < T.N; i += 2) for (let j = 0; j < T.N; j += 2) { if (Math.abs(i - j) < 200 || Math.abs(i - j) > T.N - 200) continue; const dx = T.px[i] - T.px[j], dz = T.pz[i] - T.pz[j]; if (dx * dx + dz * dz < (T.hw[i] + T.hw[j]) ** 2) clr = Math.min(clr, Math.abs(T.py[i] - T.py[j])); }
console.log(`min vertical separation where footprints overlap: ${clr.toFixed(1)} m`);
const g = T.gridSlot(0), g7 = T.gridSlot(7); console.log('grid0', g.pos.toArray().map(v => v.toFixed(1)), 'grid7', g7.pos.toArray().map(v => v.toFixed(1)));
const pr = T.project({ x: 0, y: 0.5, z: 30 }); console.log('project(0,0.5,30) → y', pr.y.toFixed(2), 'u', pr.u.toFixed(2), T.zoneNames[T.zone[pr.i]]);
const pr2 = T.project({ x: 0, y: 14.5, z: 30 }); console.log('project(0,14.5,30) → y', pr2.y.toFixed(2), 'u', pr2.u.toFixed(2), T.zoneNames[T.zone[pr2.i]]);
const f = T.field(0, 100); console.log('field(0,100)', f, 'field(60,100)', T.field(60, 100));
