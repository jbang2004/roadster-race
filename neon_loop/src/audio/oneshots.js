// One-shot sounds: collisions (metal + glass), suspension thumps, countdown beeps, UI ticks, lap chimes.
// Each shot builds a tiny graph, schedules its envelope and disconnects itself when finished.
import { clamp, rand } from './util.js';

const MAX_VOICES = 14;
let live = 0;

function track(A, nodes, endT) {
  live++;
  const ms = Math.max(30, (endT - A.ctx.currentTime) * 1000 + 120);
  setTimeout(() => { live--; for (const n of nodes) { try { n.disconnect(); } catch { /* gone */ } } }, ms);
}
// attack/decay gain node scheduled at t0
function env(ctx, t0, peak, atk, dec, dest) {
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.linearRampToValueAtTime(Math.max(0.0001, peak), t0 + atk);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + atk + dec);
  g.connect(dest); return g;
}
function tone(A, nodes, dest, t0, type, f0, f1, peak, atk, dec) {
  const { ctx } = A, o = ctx.createOscillator(); o.type = type;
  o.frequency.setValueAtTime(f0, t0); if (f1 && f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, t0 + atk + dec);
  const g = env(ctx, t0, peak, atk, dec, dest); o.connect(g); o.start(t0); o.stop(t0 + atk + dec + 0.05); nodes.push(o, g); return o;
}
function noiseBurst(A, nodes, dest, t0, buf, filt, peak, atk, dec, off = Math.random() * 2) {
  const { ctx } = A, s = ctx.createBufferSource(); s.buffer = buf;
  let n = s; for (const f of filt) { const b = ctx.createBiquadFilter(); b.type = f[0]; b.frequency.setValueAtTime(f[1], t0); b.Q.value = f[2] ?? 1; if (f[3]) b.frequency.exponentialRampToValueAtTime(f[3], t0 + atk + dec); n.connect(b); n = b; nodes.push(b); }
  const g = env(ctx, t0, peak, atk, dec, dest); n.connect(g); s.start(t0, off); s.stop(t0 + atk + dec + 0.05); nodes.push(s, g);
}
function dest(A, nodes, pos) {
  if (!pos) return A.buses.impact;
  const p = A.ctx.createPanner(); p.panningModel = 'equalpower'; p.distanceModel = 'inverse'; p.refDistance = 7; p.maxDistance = 300; p.rolloffFactor = 1.3;
  p.positionX.value = pos.x; p.positionY.value = pos.y; p.positionZ.value = pos.z; p.connect(A.buses.impact); nodes.push(p); return p;
}

/** Heavy collision. mag 0..1 (impulse scaled), kind 'wall' | 'car', pos = world position for non-player cars. */
export function crash(A, { mag, kind = 'wall', pos = null, pan = 0 }) {
  if (live > MAX_VOICES) return;
  const { ctx } = A, t = ctx.currentTime + 0.005, m = clamp(mag, 0.03, 1), nodes = [];
  let d = dest(A, nodes, pos);
  if (!pos && Math.abs(pan) > 0.01) { const sp = ctx.createStereoPanner(); sp.pan.value = clamp(pan, -1, 1) * 0.7; sp.connect(d); nodes.push(sp); d = sp; }
  const car = kind === 'car';
  // body thud
  tone(A, nodes, d, t, 'sine', car ? 95 : 118, 36, 0.95 * m, 0.003, 0.22 + 0.25 * m);
  tone(A, nodes, d, t, 'triangle', car ? 190 : 230, 60, 0.35 * m, 0.002, 0.12 + 0.1 * m);
  // low rumble tail
  noiseBurst(A, nodes, d, t, A.noise.brown, [['lowpass', 220, 0.7]], 0.55 * m, 0.004, 0.55 + 0.9 * m);
  // metal crunch: swept band + crinkle grains
  noiseBurst(A, nodes, d, t, A.noise.white, [['bandpass', 2600, 1.3, 520]], 0.5 * m, 0.002, 0.18 + 0.32 * m);
  const grains = Math.round(3 + m * 9);
  for (let i = 0; i < grains; i++) {
    const g0 = t + 0.01 + Math.pow(Math.random(), 1.6) * (0.18 + 0.4 * m);
    noiseBurst(A, nodes, d, g0, A.noise.white, [['bandpass', rand(700, 3800), rand(3, 7)], ['highpass', 500, 0.7]], m * rand(0.18, 0.5), 0.001, rand(0.012, 0.05));
  }
  // sheet-metal ring (inharmonic partials)
  const base = car ? [180, 262, 421, 640] : [213, 331, 497, 783, 1129];
  for (const f of base) tone(A, nodes, d, t + rand(0, 0.015), 'triangle', f * rand(0.93, 1.08), 0, m * rand(0.05, 0.11), 0.002, rand(0.18, 0.55) * (0.6 + m));
  if (car) noiseBurst(A, nodes, d, t, A.noise.pink, [['bandpass', 1200, 1.1]], 0.4 * m, 0.003, 0.14);   // plastic crack
  // glass ticks
  if (m > 0.3) {
    const n = Math.round(2 + 5 * m);
    for (let i = 0; i < n; i++) tone(A, nodes, d, t + rand(0.01, 0.35), 'sine', rand(3200, 9200), 0, m * rand(0.04, 0.1), 0.0008, rand(0.02, 0.07));
  }
  track(A, nodes, t + 2.0);
}

/** Suspension thump (hard compression change / landing). k 0..1 */
export function thump(A, k, pan = 0) {
  if (live > MAX_VOICES) return;
  const { ctx } = A, t = ctx.currentTime + 0.003, nodes = [], kk = clamp(k, 0.05, 1);
  let d = A.buses.impact;
  if (Math.abs(pan) > 0.01) { const sp = ctx.createStereoPanner(); sp.pan.value = clamp(pan, -1, 1) * 0.5; sp.connect(d); nodes.push(sp); d = sp; }
  tone(A, nodes, d, t, 'sine', 84, 40, 0.55 * kk, 0.003, 0.15 + 0.1 * kk);
  noiseBurst(A, nodes, d, t, A.noise.brown, [['lowpass', 260, 0.7]], 0.42 * kk, 0.003, 0.1 + 0.08 * kk);
  if (kk > 0.5) noiseBurst(A, nodes, d, t, A.noise.pink, [['bandpass', 900, 1]], 0.12 * kk, 0.002, 0.05);
  track(A, nodes, t + 0.6);
}

/** Countdown beep: 3,2,1 = low tick, GO = bright chord. */
export function beep(A, go) {
  const { ctx } = A, t = ctx.currentTime + 0.004, nodes = [], d = A.buses.ui;
  if (!go) {
    tone(A, nodes, d, t, 'sine', 880, 0, 0.30, 0.006, 0.22);
    tone(A, nodes, d, t, 'triangle', 1760, 0, 0.05, 0.004, 0.12);
    tone(A, nodes, d, t, 'sine', 220, 0, 0.12, 0.006, 0.18);
    track(A, nodes, t + 0.4);
  } else {
    for (const [f, g] of [[1318.5, 0.26], [1975.5, 0.18], [2637, 0.1], [659.3, 0.12]]) tone(A, nodes, d, t, 'sine', f, 0, g, 0.008, 0.7);
    tone(A, nodes, d, t, 'triangle', 330, 0, 0.12, 0.01, 0.5);
    noiseBurst(A, nodes, d, t, A.noise.white, [['highpass', 3000, 0.7]], 0.06, 0.01, 0.4);
    track(A, nodes, t + 1.0);
  }
}

/** Lap chime; best=true plays a brighter triple. */
export function chime(A, best = false) {
  const { ctx } = A, t = ctx.currentTime + 0.004, nodes = [], d = A.buses.ui;
  const seq = best ? [[987.8, 0], [1318.5, 0.09], [1975.5, 0.18]] : [[987.8, 0], [1480, 0.1]];
  for (const [f, dt] of seq) { tone(A, nodes, d, t + dt, 'sine', f, 0, 0.17, 0.004, best ? 0.7 : 0.45); tone(A, nodes, d, t + dt, 'sine', f * 2.01, 0, 0.04, 0.004, 0.25); }
  track(A, nodes, t + 1.2);
}

/** Soft ascending sweep when you gain a place, descending when you lose one. */
export function place(A, up) {
  const { ctx } = A, t = ctx.currentTime + 0.004, nodes = [];
  noiseBurst(A, nodes, A.buses.ui, t, A.noise.pink, [['bandpass', up ? 500 : 2400, 2, up ? 2600 : 500]], 0.12, 0.05, 0.3);
  tone(A, nodes, A.buses.ui, t, 'sine', up ? 660 : 520, up ? 990 : 390, 0.1, 0.01, 0.2);
  track(A, nodes, t + 0.6);
}

/** UI feedback. name: move | adjust | select | back | start */
export function uiSound(A, name, dir = 1) {
  const { ctx } = A, t = ctx.currentTime + 0.002, nodes = [], d = A.buses.ui;
  if (name === 'move') { tone(A, nodes, d, t, 'sine', 2600, 2100, 0.09, 0.001, 0.03); noiseBurst(A, nodes, d, t, A.noise.white, [['highpass', 5000, 0.7]], 0.03, 0.001, 0.012); }
  else if (name === 'adjust') { tone(A, nodes, d, t, 'sine', dir > 0 ? 1700 : 1350, dir > 0 ? 2000 : 1100, 0.1, 0.002, 0.05); }
  else if (name === 'select') { tone(A, nodes, d, t, 'sine', 1200, 0, 0.1, 0.002, 0.05); tone(A, nodes, d, t + 0.05, 'sine', 1800, 0, 0.11, 0.002, 0.09); }
  else if (name === 'back') { tone(A, nodes, d, t, 'sine', 900, 0, 0.1, 0.002, 0.05); tone(A, nodes, d, t + 0.05, 'sine', 600, 0, 0.1, 0.002, 0.1); }
  else if (name === 'start') { [[440, 0], [660, 0.07], [880, 0.14], [1320, 0.21]].forEach(([f, dt]) => tone(A, nodes, d, t + dt, 'triangle', f, 0, 0.12, 0.004, 0.25)); }
  track(A, nodes, t + 0.8);
}
