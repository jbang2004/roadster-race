// Offline audio self-test (browser): renders scripted scenarios through the real graph with an OfflineAudioContext
// and reports RMS / peak / NaN / click metrics per layer.
//   node tools/shot.mjs --scene ui --eval "import('/src/audio/selftest.js').then(m => m.run())" ...
import * as THREE from 'three';
import { bus } from '../core/bus.js';
import { getTrack } from '../track/track.js';
import { createAudio } from './index.js';

const SR = 44100;
const db = (x) => (x > 1e-9 ? +(20 * Math.log10(x)).toFixed(1) : -Infinity);

function mkCar(k, T, s, u) {
  const f = T.frameAt(s), pos = f.pos.clone().addScaledVector(f.r, u);
  return {
    id: k, name: 'car' + k, isPlayer: k === 0, position: pos, quaternion: new THREE.Quaternion(), velocity: new THREE.Vector3(), speed: 0,
    input: { throttle: 0, brake: 0, steer: 0, handbrake: 0 },
    wheels: Array.from({ length: 4 }, () => ({ compression: 0.03, grounded: true, skid: 0, slipAngle: 0, slipRatio: 0 })),
    motor: { rpm: 0, load: 0, power: 0 }, race: { place: k + 1, lapTimes: [], bestLap: 0 }, track: { i: T.indexAt(s), s, u, d: 0 },
  };
}
function setCar(c, T, kmh, rpm, thr, power, load) {
  c.speed = kmh / 3.6; c.input.throttle = thr; c.motor.rpm = rpm; c.motor.power = power; c.motor.load = load;
  const f = T.frameAt(c.track.s); c.velocity.copy(f.t).multiplyScalar(c.speed);
}

function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) { let bit = n >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit; if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; } }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const a = i + k, b = i + k + len / 2, tr = re[b] * cr - im[b] * ci, ti = re[b] * ci + im[b] * cr;
        re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti; const t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
      }
    }
  }
}

function analyse(buf, from = 0.5) {
  const L = buf.getChannelData(0), R = buf.getChannelData(1), s0 = Math.floor(from * buf.sampleRate), n = L.length - s0;
  let sum = 0, pk = 0, nan = 0, jump = 0;
  for (let i = s0; i < L.length; i++) {
    const a = L[i], b = R[i];
    if (!Number.isFinite(a) || !Number.isFinite(b)) { nan++; continue; }
    sum += a * a + b * b; pk = Math.max(pk, Math.abs(a), Math.abs(b));
    if (i > s0) jump = Math.max(jump, Math.abs(a - L[i - 1]));
  }
  const rms = Math.sqrt(sum / (2 * n));
  // click detector: per 512-sample block, max |first difference| relative to the block's RMS difference (tones ≈ 1.4–4, clicks ≫ 8)
  let click = 0;
  for (let b = s0 + 1; b + 512 < L.length; b += 512) {
    let m = 0, e = 0; for (let i = b; i < b + 512; i++) { const d = Math.abs(L[i] - L[i - 1]); m = Math.max(m, d); e += d * d; }
    const r = Math.sqrt(e / 512); if (r > 0.002) click = Math.max(click, m / r);
  }
  // band energies (mono, 16384-pt window from the middle)
  const N = 16384, mid = Math.max(s0, Math.floor(L.length / 2) - N / 2), re = new Float64Array(N), im = new Float64Array(N);
  for (let i = 0; i < N; i++) { const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N); re[i] = (L[mid + i] + R[mid + i]) * 0.5 * w; }
  fft(re, im);
  const bands = [0, 120, 400, 1500, 5000, 22050], e = new Array(5).fill(0);
  for (let k = 1; k < N / 2; k++) { const f = k * buf.sampleRate / N; for (let b = 0; b < 5; b++) if (f >= bands[b] && f < bands[b + 1]) e[b] += re[k] * re[k] + im[k] * im[k]; }
  const tot = e.reduce((a, b) => a + b, 0) || 1;
  return { renderX: +(buf.duration / (buf.renderMs / 1000)).toFixed(0), rmsDb: db(rms), peak: +pk.toFixed(3), peakDb: db(pk), nan, maxStep: +jump.toFixed(3), click: +click.toFixed(1), bandPct: e.map(x => Math.round(100 * x / tot)) };
}

async function render({ seconds = 3, scenario, solo = null }) {
  const T = getTrack();
  const ctx = new OfflineAudioContext(2, Math.ceil(seconds * SR), SR);
  const cam = new THREE.PerspectiveCamera(); const cars = [mkCar(0, T, 600, 0)];
  for (let k = 1; k < 8; k++) cars.push(mkCar(k, T, 600 + (k % 2 ? 1 : -1) * (14 + k * 10), (k % 2 ? 1 : -1) * 3));
  const race = { cars, phase: 'racing', paused: false, camera: { mode: 'chase' } };
  const app = { camera: cam, add() {}, remove() {} };
  const audio = createAudio(app, race, { ctx });
  audio.debug.build(); if (solo) audio.debug.solo(solo);
  const place = () => { const f = T.frameAt(cars[0].track.s); cam.position.copy(cars[0].position).addScaledVector(f.t, -8).addScaledVector(f.u, 2.5); cam.lookAt(cars[0].position); cam.updateMatrixWorld(true); };
  const step = 1 / 60, n = Math.floor(seconds / step);
  const tick = (t) => {
    scenario(t, race, T, audio); place();
    for (const c of cars) { if (c.fixedPos) continue; const f = T.frameAt(c.track.s); c.position.copy(f.pos).addScaledVector(f.r, c.track.u); c.quaternion.copy(T.quatAt(c.track.s)); c.velocity.copy(f.t).multiplyScalar(c.speed); }
    audio.update(step);
  };
  tick(0);
  for (let k = 1; k < n; k++) { const t = k * step; ctx.suspend(t).then(() => { tick(ctx.currentTime); ctx.resume(); }); }
  const t0 = performance.now(); const buf = await ctx.startRendering(); buf.renderMs = performance.now() - t0;
  audio.dispose?.();
  return buf;
}

const ai = (race, T, kmh) => { for (let k = 1; k < 8; k++) { const c = race.cars[k]; c.speed = kmh / 3.6; c.motor.rpm = kmh / 3.6 / 0.39 * 9.55 * 8; c.motor.load = 0.7; c.input.throttle = 0.8; c.track.s += c.speed / 60 * 0.98; c.track.i = T.indexAt(c.track.s); } };
const adv = (c, T) => { c.track.s += c.speed / 60; c.track.i = T.indexAt(c.track.s); };

const SCENARIOS = {
  idle: { seconds: 2.5, fn: (t, r, T) => { setCar(r.cars[0], T, 0, 0, 0, 0, 0); r.phase = 'grid'; } },
  cruise120: { seconds: 3, fn: (t, r, T) => { setCar(r.cars[0], T, 120, 6000, 0.4, 120, 0.4); adv(r.cars[0], T); } },
  flatout300: { seconds: 3, fn: (t, r, T) => { setCar(r.cars[0], T, 300, 17000, 1, 900, 1); adv(r.cars[0], T); } },
  liftoffRegen: { seconds: 3, fn: (t, r, T) => { setCar(r.cars[0], T, 240, 15000, 0, -220, 0.1); adv(r.cars[0], T); } },
  slide: { seconds: 3, fn: (t, r, T) => { const c = r.cars[0]; setCar(c, T, 150, 9500, 0.6, 300, 0.6); adv(c, T); for (const w of c.wheels) { w.skid = 0.85; w.slipAngle = 0.28; } } },
  tunnel: { seconds: 3, fn: (t, r, T) => { const c = r.cars[0]; setCar(c, T, 160, 9500, 0.5, 250, 0.5); c.track.s = 3700; c.track.i = T.indexAt(3700); } },
  sweep: { seconds: 5, fn: (t, r, T) => { const k = Math.min(1, t / 4.5); setCar(r.cars[0], T, k * 320, k * 17500, 1, 900 * (1 - 0.3 * k), 1); adv(r.cars[0], T); } },
  crashes: { seconds: 4, fn: (t, r, T) => {
    setCar(r.cars[0], T, 100, 7000, 0.5, 100, 0.5); adv(r.cars[0], T);
    for (const [tt, imp] of [[0.7, 3000], [1.6, 12000], [2.6, 40000]]) if (Math.abs(t - tt) < 1 / 120) bus.emit('car:collision', { car: r.cars[0], other: null, pos: r.cars[0].position, normal: { x: 1, y: 0, z: 0 }, impulse: imp, kind: 'wall' });
  } },
  scrape: { seconds: 3, fn: (t, r, T) => { setCar(r.cars[0], T, 90, 5000, 0.5, 80, 0.5); adv(r.cars[0], T); if (t > 0.8 && t < 2.2) bus.emit('car:scrape', { car: r.cars[0], pos: r.cars[0].position, normal: { x: 1, y: 0, z: 0 }, intensity: 0.8 }); } },
  oneshots: { seconds: 5, fn: (t, r, T, audio) => {
    setCar(r.cars[0], T, 0, 0, 0, 0, 0); r.phase = 'grid';
    const at = (tt, f) => { if (Math.abs(t - tt) < 1 / 120) f(); };
    at(0.2, () => audio.debug.trigger('siren')); at(0.3, () => audio.debug.trigger('pa'));
    at(0.5, () => bus.emit('race:countdown', { n: 3 })); at(1.0, () => bus.emit('race:countdown', { n: 0 }));
    at(1.6, () => audio.debug.trigger('chime', false)); at(2.0, () => audio.debug.trigger('chime', true));
    for (const [k, n] of [[2.4, 'move'], [2.5, 'select'], [2.6, 'back'], [2.7, 'start'], [2.9, 'adjust']]) at(k, () => bus.emit('ui:sfx', { name: n, dir: 1 }));
    at(3.2, () => bus.emit('ui:sfx', { name: 'place-up' })); at(3.6, () => bus.emit('ui:sfx', { name: 'place-down' }));
    at(4.0, () => audio.debug.trigger('thump', 0.8));
  } },
  full: { seconds: 4, fn: (t, r, T) => {
    const c = r.cars[0]; setCar(c, T, 230, 14500, 0.9, 700, 0.9); adv(c, T); ai(r, T, 225);
    for (const w of c.wheels) { w.skid = t > 1.5 ? 0.5 : 0; w.slipAngle = t > 1.5 ? 0.2 : 0.02; }
    if (Math.abs(t - 2.5) < 1 / 120) bus.emit('car:collision', { car: c, other: null, pos: c.position, normal: { x: 1, y: 0, z: 0 }, impulse: 15000, kind: 'wall' });
    if (Math.abs(t - 0.4) < 1 / 120) bus.emit('race:countdown', { n: 0 });
  } },
};

export async function run(which = null) {
  const out = { scenarios: {}, layers: {} };
  for (const [name, s] of Object.entries(SCENARIOS)) {
    if (which && !which.includes(name)) continue;
    const buf = await render({ seconds: s.seconds, scenario: s.fn });
    out.scenarios[name] = analyse(buf);
  }
  if (!which || which.includes('layers')) {
    for (const layer of ['engine', 'tyre', 'wind', 'impact', 'ai', 'amb', 'music', 'ui']) {
      const buf = await render({ seconds: SCENARIOS.full.seconds, scenario: SCENARIOS.full.fn, solo: layer });
      out.layers[layer] = analyse(buf);
    }
    const buf = await render({ seconds: SCENARIOS.full.seconds, scenario: SCENARIOS.full.fn });
    out.layers.MIX = analyse(buf);
  }
  const bad = [...Object.entries(out.scenarios), ...Object.entries(out.layers)].filter(([, v]) => v.nan > 0 || v.peak > 1.0);
  out.ok = bad.length === 0; out.bad = bad.map(b => b[0]);
  return out;
}

/** Draw a spectrogram of a scenario to a full-screen canvas (for visual inspection via the screenshot harness). */
export async function spectro(name, solo = null) {
  const s = SCENARIOS[name]; const buf = await render({ seconds: s.seconds, scenario: s.fn, solo });
  const L = buf.getChannelData(0), R = buf.getChannelData(1), N = 2048, hop = 256, frames = Math.floor((L.length - N) / hop);
  const W = 1500, H = 640, cv = document.createElement('canvas'); cv.width = W + 100; cv.height = H + 60;
  cv.style.cssText = 'position:fixed;left:0;top:0;z-index:99999;background:#000';
  const g = cv.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, cv.width, cv.height);
  const re = new Float64Array(N), im = new Float64Array(N), fmin = 40, fmax = 16000;
  const img = g.createImageData(W, H);
  const colors = (v) => { v = Math.max(0, Math.min(1, v)); const r = Math.min(255, 255 * Math.pow(v, 0.8) * 1.6), gg = Math.min(255, 255 * Math.pow(Math.max(0, v - 0.35) / 0.65, 1.1)), b = 255 * Math.max(0, Math.sin(Math.PI * Math.min(1, v * 1.2))) * (1 - Math.max(0, v - 0.6)); return [r, gg, b]; };
  for (let x = 0; x < W; x++) {
    const fr = Math.min(frames - 1, Math.floor(x / W * frames)), o = fr * hop;
    for (let i = 0; i < N; i++) { const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N); re[i] = (L[o + i] + R[o + i]) * 0.5 * w; im[i] = 0; }
    fft(re, im);
    for (let y = 0; y < H; y++) {
      const f = fmin * Math.pow(fmax / fmin, 1 - y / (H - 1)), k = Math.round(f / (buf.sampleRate / N));
      const mag = Math.sqrt(re[k] * re[k] + im[k] * im[k]) / N * 4, dbv = 20 * Math.log10(mag + 1e-7);
      const [r, gg, b] = colors((dbv + 105) / 62), p = (y * W + x) * 4; img.data[p] = r; img.data[p + 1] = gg; img.data[p + 2] = b; img.data[p + 3] = 255;
    }
  }
  g.putImageData(img, 60, 10);
  g.fillStyle = '#9ab'; g.font = '13px monospace';
  for (const f of [50, 100, 200, 500, 1000, 2000, 5000, 10000]) { const y = 10 + (1 - Math.log(f / fmin) / Math.log(fmax / fmin)) * (H - 1); g.fillText(f >= 1000 ? f / 1000 + 'k' : f, 12, y + 4); g.fillRect(55, y, 5, 1); }
  for (let t = 0; t <= s.seconds; t++) g.fillText(t + 's', 60 + t / s.seconds * W - 8, H + 30);
  g.fillText(name + (solo ? ' / ' + solo : ''), 70, H + 50);
  document.body.append(cv);
  return analyse(buf);
}

/** Positional audio check: one AI car 15 m to the right (then left) of the camera; reports L/R RMS (dB) of the AI bus. */
export async function panTest() {
  const out = {};
  for (const side of [1, -1]) {
    const T = getTrack();
    const buf = await render({ seconds: 2, solo: 'ai', scenario: (t, r) => {
      const p = r.cars[0]; setCar(p, T, 0, 0, 0, 0, 0);
      const f = T.frameAt(p.track.s);
      for (let k = 1; k < 8; k++) {
        const c = r.cars[k]; c.fixedPos = true; c.speed = k === 1 ? 70 : 0; c.motor.rpm = k === 1 ? 12000 : 0; c.motor.load = 0.8; c.input.throttle = 0.9;
        const base = p.position.clone().addScaledVector(f.t, -8).addScaledVector(f.u, 2.5);   // = camera position
        if (k === 1) c.position.copy(base).addScaledVector(f.r, 15 * side).addScaledVector(f.t, 8); else c.position.copy(base).addScaledVector(f.t, 900);
        c.velocity.set(0, 0, 0);
      }
    } });
    const L = buf.getChannelData(0), R = buf.getChannelData(1); let l = 0, rr = 0;
    for (let i = 22050; i < L.length; i++) { l += L[i] * L[i]; rr += R[i] * R[i]; }
    out[side > 0 ? 'right' : 'left'] = { L: db(Math.sqrt(l / (L.length - 22050))), R: db(Math.sqrt(rr / (L.length - 22050))) };
  }
  return out;
}
