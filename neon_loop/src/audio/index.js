// NEON LOOP audio — fully procedural WebAudio. `createAudio(app, race, opts?) → audio`.
//
//   audio.unlock()        resume/create the context — call on the first user gesture (also self-installs gesture listeners)
//   audio.setVolume(v)    master 0..1        audio.mute(b)          master mute
//   audio.setMusic(on)    darksynth bed      audio.ctx / audio.ready
//
// Reads  : race.cars[*] (motor.rpm/load/power, speed, wheels[], input, track.i, position, velocity), race.phase,
//          race.paused, race.camera.mode, app.camera (listener), core/globals G.uRain / G.uWet.
// Listens: race:countdown, race:lap, race:finish, car:collision, car:scrape, ui:sfx, ui:volume, ui:mute, ui:music.
// opts.ctx lets tests inject an OfflineAudioContext (no gesture listeners, no timers are needed then).
import { bus } from '../core/bus.js';
import { G } from '../core/globals.js';
import { getTrack, KIND } from '../track/track.js';
import { clamp, smooth, ramp, rampGain, safe, makeNoise, makeIR, softClipCurve } from './util.js';
import { createDriveUnit, createTyres, createWind, createThruster, createScrape, createAiVoice } from './voices.js';
import { createAmbience } from './ambience.js';
import { createMusic } from './music.js';
import { crash, thump, beep, chime, place, uiSound } from './oneshots.js';

const BUSES = {          // name: reverb send
  engine: 0.55, tyre: 0.5, wind: 0.1, impact: 1.0, ai: 0.9, amb: 0.45, music: 0.16, ui: 0.0,
};
const RPM_REF = 18000;    // motor.rpm that maps to the top of the whine range

export function createAudio(app, race, opts = {}) {
  const track = getTrack();
  const injected = !!opts.ctx;
  let A = null;                                   // built lazily (needs an AudioContext)
  const state = { volume: 0.8, muted: false, music: true, rpmRef: opts.rpmRef ?? RPM_REF };
  let drive, tyres, wind, thrust, scrapeP, scrapeAI, amb, music, aiVoices = [];
  let envW = { short: 0.1, deck: 0, tunnel: 0 }, cabin = 0, pauseK = 0, frame = 0, time = 0;
  let under = null;
  const scr = new Map();                           // car.id → { k, t, pos }
  const last = { thump: 0, crash: 0 };
  const prevComp = [0, 0, 0, 0], prevGround = [true, true, true, true];
  let rpmSeen = 0;

  // ------------------------------------------------------------------ graph
  function build() {
    const ctx = opts.ctx ?? new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' });
    const mix = ctx.createGain();
    const pauseLP = ctx.createBiquadFilter(); pauseLP.type = 'lowpass'; pauseLP.frequency.value = 20000; pauseLP.Q.value = 0.6;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -15; comp.knee.value = 18; comp.ratio.value = 3.5; comp.attack.value = 0.006; comp.release.value = 0.22;
    const clip = ctx.createWaveShaper(); clip.curve = softClipCurve(1.25); clip.oversample = '2x';
    const vol = ctx.createGain(); vol.gain.value = 0;
    mix.connect(pauseLP); pauseLP.connect(comp); comp.connect(clip); clip.connect(vol); vol.connect(ctx.destination);

    // reverb: three convolvers whose *inputs* are crossfaded (tails ring out naturally)
    const revIn = ctx.createGain();
    const irs = {
      short: makeIR(ctx, { dur: 0.55, pre: 0.004, lpHi: 5200, lpLo: 1400, early: [[0.011, 0.5], [0.023, 0.35], [0.041, 0.22]] }),
      deck: makeIR(ctx, { dur: 1.35, pre: 0.012, lpHi: 3800, lpLo: 700, early: [[0.015, 0.7], [0.031, 0.5], [0.052, 0.4], [0.083, 0.3]], flutter: [0.047, 0.5] }),
      tunnel: makeIR(ctx, { dur: 2.7, pre: 0.02, lpHi: 6500, lpLo: 1100, early: [[0.02, 0.6], [0.045, 0.5], [0.07, 0.45]], flutter: [0.062, 0.45] }),
    };
    const rev = {};
    for (const k in irs) {
      const inG = ctx.createGain(); inG.gain.value = 0; const cv = ctx.createConvolver(); cv.buffer = irs[k];
      revIn.connect(inG); inG.connect(cv); cv.connect(mix); rev[k] = { inG, cv };
    }
    const buses = {}, gates = {};
    for (const name in BUSES) {
      const b = ctx.createGain(), gate = ctx.createGain(), send = ctx.createGain(); send.gain.value = BUSES[name];
      b.connect(gate); gate.connect(mix); gate.connect(send); send.connect(revIn);
      buses[name] = b; gates[name] = gate;
    }
    const noise = { white: makeNoise(ctx, 'white', 4), pink: makeNoise(ctx, 'pink', 5), brown: makeNoise(ctx, 'brown', 6) };
    A = { ctx, buses, gates, noise, mix, vol, pauseLP, rev, comp };
    drive = createDriveUnit(A); tyres = createTyres(A); wind = createWind(A); thrust = createThruster(A);
    scrapeP = createScrape(A, false); scrapeAI = createScrape(A, true);
    amb = createAmbience(A); music = createMusic(A);
    const n = Math.max(0, (race?.cars?.length ?? 8) - 1);
    aiVoices = Array.from({ length: n }, () => createAiVoice(A));
    music.setEnabled(state.music, ctx.currentTime); applyVolume();
    computeUnderpasses();
  }

  function applyVolume() {
    if (!A) return;
    const v = state.muted ? 0 : Math.pow(clamp(state.volume, 0, 1), 1.6) * 1.1;
    ramp(A.vol.gain, v, A.ctx.currentTime, 0.12);
  }

  function computeUnderpasses() {
    const N = track.N, u = new Uint8Array(N), elev = [];
    for (let i = 0; i < N; i++) if (track.kind[i] === KIND.ELEVATED) elev.push(i);
    for (let i = 0; i < N; i++) {
      if (track.kind[i] === KIND.ELEVATED || track.kind[i] === KIND.TUNNEL) continue;
      const x = track.px[i], z = track.pz[i], y = track.py[i];
      for (let k = 0; k < elev.length; k += 2) {
        const j = elev[k], dx = track.px[j] - x, dz = track.pz[j] - z;
        if (dx * dx + dz * dz < (track.hw[j] + 5) ** 2 && track.py[j] - y > 5) { u[i] = 1; break; }
      }
    }
    const d = new Uint8Array(N);                   // dilate ±14 m so the cavity builds before / lingers after the deck
    for (let i = 0; i < N; i++) if (u[i]) for (let k = -14; k <= 14; k++) d[(i + k + N) % N] = 1;
    under = d;
  }

  // ------------------------------------------------------------------ unlock
  function unlock() {
    try {
      if (!A) build();
      if (A.ctx.state === 'suspended') A.ctx.resume();
    } catch (e) { console.warn('[audio] unlock failed', e); }
    return A?.ctx.state;
  }
  const gestures = ['pointerdown', 'keydown', 'touchend', 'mousedown'];
  const onGesture = () => { unlock(); if (A && A.ctx.state === 'running') for (const g of gestures) window.removeEventListener(g, onGesture, true); };
  if (!injected && typeof window !== 'undefined') for (const g of gestures) window.addEventListener(g, onGesture, true);

  // ------------------------------------------------------------------ events
  const offs = [
    bus.on('ui:volume', ({ volume }) => { state.volume = safe(volume, state.volume); applyVolume(); }),
    bus.on('ui:mute', ({ muted }) => { state.muted = !!muted; applyVolume(); }),
    bus.on('ui:music', ({ on }) => { state.music = !!on; if (A) music.setEnabled(state.music, A.ctx.currentTime); }),
    bus.on('ui:sfx', ({ name, dir }) => {
      if (!A) return;
      if (name === 'place-up' || name === 'place-down') place(A, name === 'place-up'); else uiSound(A, name, dir);
    }),
    bus.on('race:countdown', ({ n }) => { if (A) beep(A, n === 0); }),
    bus.on('race:lap', ({ car, time: t, best }) => {
      if (!A || !car?.isPlayer) return;
      const bl = car.race?.bestLap; chime(A, best === true || (typeof best === 'number' ? t <= best + 1e-3 : bl > 0 && t <= bl + 1e-3) && (car.race?.lapTimes?.length ?? 2) > 1);
    }),
    bus.on('race:finish', ({ car }) => { if (A && car?.isPlayer) chime(A, true); }),
    bus.on('car:collision', (e) => onCollision(e)),
    bus.on('car:scrape', (e) => { if (e?.car) scr.set(e.car.id ?? 0, { k: clamp(safe(e.intensity), 0, 1), t: time, pos: e.pos, car: e.car }); }),
  ];

  const camPos = { x: 0, y: 0, z: 0 }, camR = { x: 1, y: 0, z: 0 };
  function onCollision(e) {
    if (!A || !e || A.ctx.state !== 'running' && !injected) return;
    const mag = Math.pow(clamp(safe(e.impulse) / 15000, 0.02, 1), 0.65);
    const isP = e.car?.isPlayer || e.other?.isPlayer;
    if (time - last.crash < 0.06 && mag < 0.5) return;
    last.crash = time;
    if (isP) {
      const px = e.pos ? (e.pos.x - camPos.x) * camR.x + (e.pos.z - camPos.z) * camR.z : 0;
      crash(A, { mag, kind: e.kind, pan: clamp(px / 4, -1, 1) });
    } else if (e.pos) {
      const dx = e.pos.x - camPos.x, dz = e.pos.z - camPos.z;
      if (dx * dx + dz * dz < 260 * 260) crash(A, { mag: mag * 0.9, kind: e.kind, pos: e.pos });
    }
  }

  // ------------------------------------------------------------------ per-frame
  const tmp = { x: 0, y: 0, z: 0 };
  function updateListener(cam) {
    const L = A.ctx.listener, e = cam.matrixWorld.elements;
    camPos.x = e[12]; camPos.y = e[13]; camPos.z = e[14];
    const fx = -e[8], fy = -e[9], fz = -e[10], ux = e[4], uy = e[5], uz = e[6];
    camR.x = e[0]; camR.y = e[1]; camR.z = e[2];
    if (L.positionX) {
      L.positionX.value = camPos.x; L.positionY.value = camPos.y; L.positionZ.value = camPos.z;
      L.forwardX.value = fx; L.forwardY.value = fy; L.forwardZ.value = fz; L.upX.value = ux; L.upY.value = uy; L.upZ.value = uz;
    } else { L.setPosition(camPos.x, camPos.y, camPos.z); L.setOrientation(fx, fy, fz, ux, uy, uz); }
  }

  let lastReal = 0;
  function update(dt) {
    if (!A || A.ctx.state === 'closed') return;
    // smoothing / timers use REAL elapsed time: the game may freeze its own clock (dt = 0) while paused
    const rn = injected ? 0 : performance.now();
    dt = injected ? clamp(safe(dt, 1 / 60), 0, 0.1) : clamp(lastReal ? (rn - lastReal) / 1000 : 1 / 60, 0, 0.1);
    lastReal = rn; time += dt; frame++;
    const ctx = A.ctx, now = ctx.currentTime;
    const cam = app?.camera; if (cam) { cam.updateMatrixWorld?.(); if (cam.matrixWorld) updateListener(cam); }
    const cars = race?.cars ?? [], p = cars[0];
    const paused = !!race?.paused, phase = race?.phase ?? 'grid';

    // --- environment (reverb / ambience) -------------------------------------------------
    let tun = 0, und = 0, trn = 0, mkt = 0, zone = 'boulevard', i = 0;
    if (p) {
      i = clamp((p.track?.i ?? 0) | 0, 0, track.N - 1);
      const k = p.track?.kind ?? track.kind[i];
      tun = k === KIND.TUNNEL ? 1 : 0; trn = k === KIND.TRENCH ? 1 : 0; und = under && under[i] ? 1 : 0;
      zone = track.zoneNames[track.zone[i]]; mkt = zone === 'market' ? 1 : 0;
    }
    const tgt = { short: 0.12 + 0.2 * mkt + 0.12 * trn - 0.08 * und - 0.12 * tun, deck: 0.6 * und + 0.28 * trn, tunnel: 0.9 * tun };
    const a = 1 - Math.exp(-dt / 0.5);
    for (const k in envW) { envW[k] += (Math.max(0, tgt[k]) - envW[k]) * a; rampGain(A.rev[k].inG.gain, envW[k], now, 0.08); }

    // --- pause / camera -------------------------------------------------------------------
    pauseK += ((paused ? 1 : 0) - pauseK) * (1 - Math.exp(-dt / 0.12));
    ramp(A.pauseLP.frequency, 20000 * Math.pow(0.034, pauseK), now, 0.05);
    const duck = 1 - 0.85 * pauseK, mode = race?.camera?.mode;
    cabin += (((mode === 'hood' || mode === 'bumper') ? 1 : 0) - cabin) * (1 - Math.exp(-dt / 0.3));
    const dryBoost = 1 + 0.2 * tun;
    ramp(A.buses.engine.gain, duck * dryBoost, now, 0.08); ramp(A.buses.tyre.gain, duck, now, 0.08);
    ramp(A.buses.wind.gain, duck, now, 0.08); ramp(A.buses.impact.gain, 1 - 0.7 * pauseK, now, 0.08);
    ramp(A.buses.ai.gain, 1 - 0.8 * pauseK, now, 0.08);
    // music follows the phase
    const mlev = paused ? 0.2 : phase === 'racing' ? 0.3 : phase === 'countdown' ? 0.32 : phase === 'finished' ? 0.5 : 0.6;
    music.setLevel(mlev, now, 0.9); music.tick(now);

    // --- player ---------------------------------------------------------------------------
    const raining = safe(G.uRain?.value, 0.3), wet = safe(G.uWet?.value, 1);
    if (p) {
      const spd = Math.abs(safe(p.speed)), m = p.motor ?? {};
      const rpm = Number.isFinite(m.rpm) ? m.rpm : spd / 0.39 * 9.55 * 8;
      rpmSeen = Math.max(rpmSeen, rpm); if (rpmSeen > state.rpmRef * 1.15) state.rpmRef = rpmSeen / 1.05;
      const thr = clamp(safe(p.input?.throttle), 0, 1);
      const load = clamp(Math.max(safe(m.load), thr * 0.85), 0, 1);
      const racing = phase !== 'grid';
      drive.update(now, { rpmN: racing || rpm > 100 ? rpm / state.rpmRef : 0, load, throttle: thr, power: safe(m.power), cabin, duck: 0 });
      // tyres
      let skF = 0, skR = 0, slipLat = 0;
      const W = p.wheels ?? [];
      for (let w = 0; w < W.length; w++) {
        const wh = W[w], g = wh.grounded === false ? 0 : 1;
        const sk = Math.max(safe(wh.skid), 0.7 * smooth(0.12, 0.36, Math.abs(safe(wh.slipAngle))), 0.8 * smooth(0.18, 0.5, Math.abs(safe(wh.slipRatio)))) * g;
        if (w < 2) skF = Math.max(skF, sk); else skR = Math.max(skR, sk);
        slipLat = Math.max(slipLat, smooth(0.08, 0.35, Math.abs(safe(wh.slipAngle))));
        // suspension thumps
        const comp = safe(wh.compression), rate = (comp - prevComp[w]) / Math.max(dt, 1e-3); prevComp[w] = comp;
        const landed = wh.grounded !== false && !prevGround[w]; prevGround[w] = wh.grounded !== false;
        if ((rate > 1.7 || landed) && time - last.thump > 0.11 && spd > 3) {
          last.thump = time; thump(A, clamp(landed ? 0.5 : (rate - 1.7) / 3.5, 0.1, 1) * clamp(spd / 40, 0.3, 1), (w % 2 ? 0.3 : -0.3));
        }
      }
      tyres.update(now, { v: spd, wet: clamp(wet * (0.55 + 0.45 * raining), 0, 1), skidF: skF, skidR: skR, slipAng: slipLat });
      wind.update(now, { v: spd, cabin });
      thrust.update(now, { level: safe(p.boost?.level), gas: safe(p.boost?.gas, 1), cabin });
      // scrape
      let sp = scr.get(p.id ?? 0), sk = 0;
      if (sp && time - sp.t < 0.14) sk = sp.k;
      scrapeP.update(now, sk, clamp(spd / 80, 0, 1));
      // nearest AI scrape (positional)
      let best = null, bk = 0;
      for (const [id, s] of scr) { if (id === (p.id ?? 0) || time - s.t > 0.14 || !s.pos) continue; const d2 = (s.pos.x - camPos.x) ** 2 + (s.pos.z - camPos.z) ** 2; if (d2 < 250 * 250 && s.k > bk) { best = s; bk = s.k; } }
      scrapeAI.update(now, best ? best.k : 0, 0.6, best ? best.pos : null);
      for (const [id, s] of scr) if (time - s.t > 1) scr.delete(id);
    }

    // --- AI cars (positional, 30 Hz round-robin) ---------------------------------------------
    for (let k = 1; k < cars.length && k - 1 < aiVoices.length; k++) {
      if ((frame + k) % 2) continue;
      const c = cars[k], v = aiVoices[k - 1]; if (!c?.position) continue;
      const dx = c.position.x - camPos.x, dy = c.position.y - camPos.y, dz = c.position.z - camPos.z;
      const dist = Math.hypot(dx, dy, dz) + 1e-3;
      const lv = p?.velocity ?? tmp, cv = c.velocity ?? tmp;
      const closing = -(((cv.x ?? 0) - (lv.x ?? 0)) * dx + ((cv.y ?? 0) - (lv.y ?? 0)) * dy + ((cv.z ?? 0) - (lv.z ?? 0)) * dz) / dist;
      const rpm = Number.isFinite(c.motor?.rpm) ? c.motor.rpm : Math.abs(safe(c.speed)) / 0.39 * 9.55 * 8;
      v.update(now, c, (phase === 'grid' ? 0 : rpm) / state.rpmRef, dist, closing, c.position, Math.max(safe(c.motor?.load), clamp(safe(c.input?.throttle), 0, 1) * 0.85));
    }

    // --- ambience ----------------------------------------------------------------------------
    const city = ({ boulevard: 1, street: 1.05, docks: 0.8, ramp: 0.7, expressway: 0.5, descent: 0.6, tunnel: 0.3, market: 1.2 }[zone] ?? 1) * (1 - 0.4 * tun);
    amb.update(now, { rain: raining, city, tunnel: tun, under: Math.max(und, trn * 0.5), dt, listener: camPos });
  }

  const sys = { update };
  if (app?.add) app.add(sys);

  const audio = {
    unlock, update,
    setVolume(v) { state.volume = clamp(safe(v, 0.8), 0, 1); applyVolume(); },
    mute(b) { state.muted = !!b; applyVolume(); },
    setMusic(on) { state.music = !!on; if (A) music.setEnabled(state.music, A.ctx.currentTime); },
    setRpmRange(max) { state.rpmRef = Math.max(2000, safe(max, RPM_REF)); },
    get ctx() { return A?.ctx ?? null; },
    get ready() { return !!A && A.ctx.state === 'running'; },
    get state() { return { ...state, ctx: A?.ctx.state ?? 'none', env: { ...envW } }; },
    /** test hooks: build against the injected ctx and expose the graph */
    debug: {
      build() { if (!A) build(); return A; },
      get A() { return A; },
      solo(name) { if (!A) return; for (const k in A.gates) A.gates[k].gain.value = (!name || k === name) ? 1 : 0; },
      env() { return { ...envW }; },
      underRanges() { const r = []; let a = -1; for (let i = 0; i <= track.N; i++) { const on = under && under[i % track.N]; if (on && a < 0) a = i; if (!on && a >= 0) { r.push([a, i - 1]); a = -1; } } return r; },
      trigger(kind, ...a) {
        if (!A) return;
        if (kind === 'crash') crash(A, a[0]); else if (kind === 'thump') thump(A, a[0]); else if (kind === 'beep') beep(A, a[0]);
        else if (kind === 'chime') chime(A, a[0]); else if (kind === 'ui') uiSound(A, a[0]);
        else if (kind === 'siren' || kind === 'pa') amb.trigger(kind, A.ctx.currentTime, camPos);
      },
    },
    dispose() {
      offs.forEach(o => o()); for (const g of gestures) window.removeEventListener(g, onGesture, true);
      if (app?.remove) app.remove(sys);
      if (A && !injected) A.ctx.close();
    },
  };
  if (!injected && typeof window !== 'undefined') window.__audio = audio;
  return audio;
}
