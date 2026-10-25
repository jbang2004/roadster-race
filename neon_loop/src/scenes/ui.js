// UI + audio test scene: a placeholder night backdrop, a mock `race` with animated fake car states, and harness hooks.
//   ?scene=ui[&screen=title|hud|countdown|pause|results][&s=<metres>][&nosound]
//   __ui.show('title'|'hud'|'countdown'|'pause'|'results', arg)   __ui.mock   __ui.audio   __ui.race
import * as THREE from 'three';
import { getTrack, KIND } from '../track/track.js';
import { loadGLTF } from '../core/assets.js';
import { bus } from '../core/bus.js';
import { createUI } from '../ui/index.js';
import { createAudio } from '../audio/index.js';
import { CAR } from '../game/params.js';

const NAMES = ['你 YOU', '陈暮雪', 'Kenji Mori', '朴智恩', 'Lucas Vale', '林夜航', 'Aiko Sato', 'Dmitri Volkov'];
const NAME_P = '玩家 · NEO';
const RAD = CAR.wheelR;        // the motor-speed estimate's reference wheel (the rear); the front wheels spin at CAR.wheelRF

export default async function (app) {
  const T = getTrack();
  const scene = app.scene;

  // ---------------------------------------------------------------- backdrop
  const sky = document.createElement('canvas'); sky.width = 4; sky.height = 256;
  { const g = sky.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
    gr.addColorStop(0, '#04060f'); gr.addColorStop(0.55, '#150f2e'); gr.addColorStop(0.8, '#3a1747'); gr.addColorStop(1, '#6a2a4a');
    g.fillStyle = gr; g.fillRect(0, 0, 4, 256); }
  const skyTex = new THREE.CanvasTexture(sky); skyTex.colorSpace = THREE.SRGBColorSpace;
  scene.background = skyTex;
  scene.fog = new THREE.FogExp2(0x1a1030, 0.0018);
  scene.add(new THREE.HemisphereLight(0x6f86c8, 0x0a0c14, 1.6));
  const moon = new THREE.DirectionalLight(0x9fb4ff, 1.1); moon.position.set(-200, 300, 100); scene.add(moon);
  const warm = new THREE.DirectionalLight(0xff7a9a, 0.5); warm.position.set(200, 60, -300); scene.add(warm);

  // road ribbon + neon wall strips
  {
    const N = T.N, pos = [], uv = [], idx = [];
    for (let i = 0; i <= N; i++) {
      const k = i % N, hw = T.hw[k] + 0.5;
      for (const side of [-1, 1]) {
        pos.push(T.px[k] + T.rx[k] * hw * side, T.py[k] + T.ry[k] * hw * side + 0.02, T.pz[k] + T.rz[k] * hw * side);
        uv.push(side < 0 ? 0 : 1, i * 0.1);
      }
      if (i < N) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx); g.computeVertexNormals();
    const rc = document.createElement('canvas'); rc.width = 64; rc.height = 256;
    { const c = rc.getContext('2d'); c.fillStyle = '#0a0d14'; c.fillRect(0, 0, 64, 256); c.fillStyle = '#c9d6e4';
      c.fillRect(31, 20, 2, 90); c.fillRect(31, 148, 2, 90); c.fillStyle = '#1a2230'; c.fillRect(0, 0, 3, 256); c.fillRect(61, 0, 3, 256); }
    const rt = new THREE.CanvasTexture(rc); rt.wrapS = rt.wrapT = THREE.RepeatWrapping; rt.colorSpace = THREE.SRGBColorSpace; rt.anisotropy = 8;
    scene.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({ map: rt, roughness: 0.28, metalness: 0.2, side: THREE.DoubleSide })));
    for (const side of [-1, 1]) {
      const wp = [], wi = [];
      for (let i = 0; i <= N; i++) {
        const k = i % N, o = (T.hw[k] + 0.55) * side;
        const x = T.px[k] + T.rx[k] * o, y = T.py[k] + T.ry[k] * o, z = T.pz[k] + T.rz[k] * o;
        wp.push(x, y + 0.35, z, x, y + 0.55, z);
        if (i < N) { const a = i * 2; wi.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
      }
      const wg = new THREE.BufferGeometry(); wg.setAttribute('position', new THREE.Float32BufferAttribute(wp, 3)); wg.setIndex(wi);
      scene.add(new THREE.Mesh(wg, new THREE.MeshBasicMaterial({ color: side < 0 ? 0xff49d6 : 0x3ee8ff, side: THREE.DoubleSide, fog: true })));
    }
    const B = T.layout.bounds;
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(B.x1 - B.x0 + 1000, B.z1 - B.z0 + 1000), new THREE.MeshStandardMaterial({ color: 0x07090e, roughness: 0.9 }));
    ground.rotation.x = -Math.PI / 2; ground.position.set((B.x0 + B.x1) / 2, -0.06, (B.z0 + B.z1) / 2); scene.add(ground);
  }
  // towers with lit windows
  {
    const wc = document.createElement('canvas'); wc.width = 128; wc.height = 256;
    const c = wc.getContext('2d'); c.fillStyle = '#05070c'; c.fillRect(0, 0, 128, 256);
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const pal = ['#ffd9a0', '#9fd8ff', '#ff9ad8', '#8ff3ff', '#ffe9c0'];
    for (let y = 4; y < 252; y += 8) for (let x = 4; x < 124; x += 8) if (rnd() < 0.14) { c.fillStyle = pal[(rnd() * pal.length) | 0]; c.globalAlpha = 0.35 + rnd() * 0.65; c.fillRect(x, y, 5, 5); }
    const wt = new THREE.CanvasTexture(wc); wt.colorSpace = THREE.SRGBColorSpace; wt.wrapS = wt.wrapT = THREE.RepeatWrapping; wt.repeat.set(2, 6);
    const mat = new THREE.MeshStandardMaterial({ color: 0x0c1020, roughness: 0.4, metalness: 0.6, emissive: 0xffffff, emissiveMap: wt, emissiveIntensity: 0.65 });
    const COUNT = 1800, im = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), mat, COUNT);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), sc = new THREE.Vector3(), tmp = {};
    let n = 0, guard = 0;
    while (n < COUNT && guard++ < 20000) {
      const s = rnd() * T.length, f = T.frameAt(s), side = rnd() < 0.5 ? -1 : 1;
      const off = f.hw + 10 + rnd() * 90, x = f.pos.x + f.r.x * off * side, z = f.pos.z + f.r.z * off * side;
      if (T.field(x, z, tmp).all < 7) continue;
      const w = 12 + rnd() * 26, d = 12 + rnd() * 26, hh = 25 + Math.pow(rnd(), 2.2) * 190;
      p.set(x, hh / 2 - 0.05, z); sc.set(w, hh, d); q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.atan2(f.t.x, f.t.z));
      im.setMatrixAt(n++, m.compose(p, q, sc));
    }
    im.count = n; im.frustumCulled = false; scene.add(im);
  }

  // ---------------------------------------------------------------- cars (visual)
  const gltf = await loadGLTF('assets/car/wedge_car.glb');
  const carObjs = [];
  for (let k = 0; k < 8; k++) {
    const g = new THREE.Group(); const m = gltf.scene.clone(true); m.rotation.y = -Math.PI / 2; g.add(m);
    if (k > 0) { // tint AI cars so they read as different cars
      const col = new THREE.Color(['#fff', '#1ee6ff', '#ff4fd8', '#ff3550', '#4d7bff', '#c8ff2e', '#ff8a1f', '#a66bff'][k]);
      m.traverse(o => { if (o.isMesh && o.material?.color && /body|paint/i.test(o.material.name || '')) { o.material = o.material.clone(); o.material.color.lerp(col, 0.7); } });
    }
    scene.add(g); carObjs.push(g);
  }

  // ---------------------------------------------------------------- mock race
  const mkCar = (k) => ({
    id: k, name: k === 0 ? NAME_P : NAMES[k], livery: k, isPlayer: k === 0, visual: null,
    position: new THREE.Vector3(), quaternion: new THREE.Quaternion(), velocity: new THREE.Vector3(), angularVelocity: new THREE.Vector3(), speed: 0,
    accel: new THREE.Vector3(),
    input: { throttle: 0, brake: 0, steer: 0, handbrake: 0 },
    wheels: Array.from({ length: 4 }, () => ({ steer: 0, spin: 0, spinRate: 0, compression: 0.02, suspensionTravel: 0, load: 4200, slipRatio: 0, slipAngle: 0, grounded: true, skid: 0, contact: new THREE.Vector3() })),
    motor: { rpm: 0, load: 0, power: 0 }, brakeTemp: 0.2, lights: { head: true, brake: 0, reverse: false },
    race: { lap: 1, lapS: 0, progress: 0, place: k + 1, lapTimes: [], bestLap: 0, lastLap: 0, finished: false, finishTime: 0, gapAhead: 0, gapBehind: 0 },
    track: { i: 0, s: 0, u: 0, d: 0 },
    _s: 0, _u: 0, _v: 0, _top: 0, _t0: 0, _lastLapT: 0, _seed: k * 7.31,
  });
  const cars = Array.from({ length: 8 }, (_, k) => mkCar(k));
  const race = {
    cars, phase: 'grid', paused: false, laps: 3, time: 0,
    camera: { mode: 'orbit', setMode(m) { this.mode = m; bus.emit('camera:mode', { mode: m }); } },
    start() { mock.reset(); race.phase = 'countdown'; bus.emit('race:phase', { phase: 'countdown' }); cdT = 0; cdN = 4; },
    reset() { mock.reset(); },
  };
  let cdT = 0, cdN = -1, autoFinishDelay = 0;
  const L = T.length;

  const mock = {
    reset() {
      race.phase = 'grid'; race.time = 0; cdN = -1;
      cars.forEach((c, k) => {
        const slot = T.gridSlot(k);
        c._s = slot.s; c._u = slot.u; c._v = 0; c._t0 = 0; c._lastLapT = 0;
        c._top = (k === 0 ? 86 : 79 + ((k * 37) % 9) * 1.1);
        Object.assign(c.race, { lap: 1, progress: slot.s - T.startS, lapS: 0, place: k + 1, lapTimes: [], bestLap: 0, lastLap: 0, finished: false, finishTime: 0 });
        c.speed = 0;
      });
      mock.step(0.001); poseAll();
    },
    /** Skip straight into a running race at lap distance s0 (player ahead of the pack by a little) and simulate `sim` seconds. */
    instant(s0 = 560, sim = 5) {
      mock.reset();
      race.phase = 'racing'; race.time = 20;
      cars.forEach((c, k) => {
        const lead = [3, 1, 0, 4, 2, 5, 6, 7][k];   // finishing order of the mock pack: player 4th
        c._s = T.wrapS(s0 - lead * 28 + (k % 2 ? 2 : -2)); c._u = (k % 2 ? 1 : -1) * 2.4; c._v = 62 + k;
        c.race.progress = L + T.wrapS(c._s - T.startS); c.race.lap = 2;
        c.race.lapTimes = []; c.race.bestLap = 0; c.race.lastLap = 0;
      });
      cars.forEach((c, k) => { c._lastLapT = 89.482; c.race.lapTimes = [89.482 + k * .4]; c.race.lastLap = c.race.lapTimes[0]; c.race.bestLap = 88.311 + k * .5; });
      race.time = 89.482 + 21.4;
      for (let i = 0; i < Math.round(sim / 0.05); i++) mock.step(0.05);
      poseAll(); return race.cars[0].speed;
    },
    finishAll() {
      mock.instant(300, 0.1);
      race.phase = 'finished';
      const order = [3, 1, 0, 4, 2, 5, 6, 7];
      cars.forEach((c, k) => {
        const rank = order.indexOf(k) ; const r = c.race;
        r.place = rank + 1; r.finished = true; r.finishTime = 262.4 + rank * 2.17 + (k === 0 ? 0.3 : 0.02 * k);
        r.lap = 3; r.lapTimes = [89.9 + rank * .5, 86.4 + rank * 0.6 + (k === 0 ? -0.6 : 0), 86.1 + rank * 0.4]; r.bestLap = Math.min(...r.lapTimes) - (k === 3 ? 0.8 : 0); r.lastLap = r.lapTimes[2];
      });
    },
    setSpeed(kmh) { cars[0]._v = kmh / 3.6; },
    step,
  };
  mock.step = step;

  function step(dt) {
    const prevP = cars.map(c => c.race.progress);
    race.time += race.phase === 'racing' ? dt : 0;
    cars.forEach((c, k) => {
      const racing = race.phase === 'racing' && !c.race.finished;
      const f = T.frameAt(c._s);
      // look-ahead curvature → target speed
      let kmax = 0; for (let d = 0; d <= 110; d += 22) kmax = Math.max(kmax, Math.abs(T.curv[T.indexAt(c._s + d)]));
      const vcorner = Math.min(c._top, Math.sqrt(16 / (kmax + 1e-4)) + 6);
      const wob = 1 + 0.045 * Math.sin(race.time * 0.37 + c._seed);
      const target = k === 0 && mock.hold != null && racing ? mock.hold / 3.6 : racing ? Math.min(c._top * wob, vcorner) : 0;
      const dv = target - c._v;
      let a = dv > 0 ? Math.min(dv * 1.4, 10.5 * (1 - c._v / 105)) : Math.max(dv * 1.8, -27);
      if (!racing) a = Math.max(-30, dv * 3);
      c._v = Math.max(0, c._v + a * dt);
      const ds = c._v * dt; c._s = T.wrapS(c._s + ds); c.race.progress += ds;
      const kk = T.curv[T.indexAt(c._s)];
      // fake car state
      const g = c.input;
      g.throttle = a > 0.5 ? Math.min(1, a / 9) : 0; g.brake = a < -6 ? Math.min(1, -a / 24) : 0; g.steer = Math.max(-1, Math.min(1, -kk * c._v * 0.9)); g.handbrake = 0;
      c.speed = c._v;
      const accKW = Math.max(-300, Math.min(1000, 1700 * a * c._v / 1000));
      c.motor.rpm = (c._v / (2 * Math.PI * RAD)) * 60 * 8.2 + (racing ? 600 : 0);
      c.motor.load = Math.max(0, Math.min(1, a / 9 + 0.15 * (c._v / 90)));
      c.motor.power = accKW;
      if (k === 0 && mock.regen) { c.motor.power = -240; c.motor.load = 0.05; g.throttle = 0; }
      c.lights.brake = g.brake;
      const lat = Math.abs(kk) * c._v * c._v / 9.81;
      c.wheels.forEach((w, i) => {
        w.spinRate = c._v / (i < 2 ? CAR.wheelRF : CAR.wheelR); w.spin += w.spinRate * dt; w.steer = g.steer * 0.12 * (i < 2 ? 1 : 0);
        const slide = Math.max(0, lat - 1.05);
        w.slipAngle = (kk > 0 ? -1 : 1) * Math.min(0.5, slide * 0.4 + lat * 0.03); w.slipRatio = Math.max(-0.3, Math.min(0.3, a * 0.012)) ;
        w.skid = Math.min(1, slide * 1.8 + Math.max(0, -a - 20) * 0.04); w.grounded = true;
        if (k === 0 && mock.skid > 0) { w.skid = mock.skid; w.slipAngle = 0.3 * mock.skid; }
        w.compression = 0.03 + 0.012 * Math.sin(race.time * 7 + i + c._seed) + (i < 2 ? 1 : -1) * 0.004 * a * 0.1; w.load = 4200 + (i < 2 ? -1 : 1) * a * 40;
      });
      c.track.i = T.indexAt(c._s); c.track.s = c._s; c.track.u = c._u; c.track.d = 0;
      c.race.lapS = T.wrapS(c._s - T.startS);
      // laps
      const lapNow = Math.floor(c.race.progress / L) + 1;
      if (racing && lapNow > c.race.lap) {
        const t = race.time - c._lastLapT; c._lastLapT = race.time;
        c.race.lapTimes.push(t); c.race.lastLap = t; if (!c.race.bestLap || t < c.race.bestLap) c.race.bestLap = t; c.race.lap = lapNow;
        const isBest = t <= c.race.bestLap;
        if (lapNow > race.laps) { c.race.finished = true; c.race.finishTime = race.time; c.race.lap = race.laps; c.race.place = cars.filter(o => o.race.finished).length;
          bus.emit('race:finish', { car: c, place: c.race.place, time: race.time }); if (c.isPlayer) race.phase = 'finished'; }
        else bus.emit('race:lap', { car: c, lap: lapNow - 1, time: t, best: isBest });
      }
    });
    // places + gaps
    const order = [...cars].sort((p, q) => (q.race.finished - p.race.finished) || (p.race.finished && q.race.finished ? p.race.finishTime - q.race.finishTime : q.race.progress - p.race.progress));
    order.forEach((c, i) => { if (!c.race.finished) c.race.place = i + 1; });
    order.forEach((c, i) => {
      const ah = order[i - 1], bh = order[i + 1];
      c.race.gapAhead = ah ? Math.max(0, (ah.race.progress - c.race.progress)) / Math.max(30, c._v) : 0;
      c.race.gapBehind = bh ? Math.max(0, (c.race.progress - bh.race.progress)) / Math.max(30, bh._v) : 0;
    });
    void prevP;
  }
  function poseAll() {
    cars.forEach((c, k) => {
      const f = T.frameAt(c._s);
      c.position.copy(f.pos).addScaledVector(f.r, c._u).addScaledVector(f.u, 0.02);
      T.quatAt(c._s, c.quaternion);
      c.velocity.copy(f.t).multiplyScalar(c._v);
      if (k === 0 && mock.wrongWay) { c.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI)); c.velocity.negate(); }
      carObjs[k].position.copy(c.position); carObjs[k].quaternion.copy(c.quaternion);
    });
  }

  // wiring: the lead's full.js does the equivalent
  bus.on('ui:start', ({ laps }) => { race.laps = laps; race.start(); });
  bus.on('ui:restart', () => race.start());
  bus.on('ui:quit', () => { mock.reset(); race.camera.mode = 'orbit'; });
  bus.on('ui:pause', ({ paused }) => { race.paused = paused; });

  mock.reset();
  const ui = createUI(app, race);
  const audio = app.q.has('nosound') ? null : createAudio(app, race);

  // sim + camera
  const sysMock = {
    update(dt) {
      if (race.paused) { poseAll(); return; }
      if (race.phase === 'countdown') {
        cdT += dt;
        const want = 3 - Math.floor(cdT / 1.0) ;
        if (cdN === 4 || (want < cdN && want >= 0)) { cdN = want; if (cdN >= 0) bus.emit('race:countdown', { n: cdN }); }
        if (cdT >= 3.0 && race.phase === 'countdown') { race.phase = 'racing'; bus.emit('race:phase', { phase: 'racing' }); }
      }
      step(dt); poseAll();
    },
  };
  app.add(sysMock);

  const cam = app.camera; const tmpV = new THREE.Vector3(), look = new THREE.Vector3(); let orbitA = 0.6, camPos = null;
  const sysCam = {
    late(dt) {
      const p = cars[0], f = T.frameAt(p._s);
      const mode = race.camera.mode;
      const screen = ui.screen;
      if (screen === 'title' || screen === 'results' || mode === 'orbit') {
        orbitA += dt * 0.12; const r = 10.5;
        tmpV.set(p.position.x + Math.sin(orbitA) * r, p.position.y + 1.7 + Math.sin(orbitA * 0.6) * 0.3, p.position.z + Math.cos(orbitA) * r);
        const toCam = tmpV.clone().sub(p.position).setY(0).normalize(), side = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), toCam);
        look.copy(p.position).add(new THREE.Vector3(0, 0.6, 0)).addScaledVector(side, screen === 'title' ? -3.6 : 0);
        cam.fov = 38;
      } else {
        const back = mode === 'hood' ? -0.6 : mode === 'bumper' ? 1.6 : 8.4, up = mode === 'hood' ? 1.15 : mode === 'bumper' ? 0.55 : 2.7;
        tmpV.copy(p.position).addScaledVector(f.t, -back).addScaledVector(f.u, up);
        look.copy(p.position).addScaledVector(f.t, 24).addScaledVector(f.u, 1.0);
        cam.fov = 60 + Math.min(14, p._v / 7);
      }
      if (!camPos) camPos = tmpV.clone();
      camPos.lerp(tmpV, 1 - Math.exp(-dt * (screen === 'hud' ? 14 : 4)));
      cam.position.copy(camPos); cam.lookAt(look); cam.updateProjectionMatrix();
    },
  };
  app.add(sysCam);
  app.viewLocked = false;

  if (app.q.has('lab')) buildLab();
  function buildLab() {
    const el = document.createElement('div');
    el.style.cssText = 'position:fixed;left:12px;top:12px;z-index:50;background:rgba(5,10,18,.86);border:1px solid #2a4a5a;border-radius:8px;padding:10px 12px;font:12px/1.5 ui-monospace,Menlo,monospace;color:#bfe;max-width:330px;pointer-events:auto';
    el.innerHTML = '<b>AUDIO LAB</b> (press any key first)<br>';
    const btn = (label, fn) => { const b = document.createElement('button'); b.textContent = label; b.style.cssText = 'margin:2px;padding:3px 7px;background:#0b1a24;color:#8ff;border:1px solid #2a5a6a;border-radius:4px;cursor:pointer'; b.onclick = () => { window.__audio?.unlock(); fn(); }; el.append(b); return b; };
    const sl = (label, min, max, val, fn) => { const d = document.createElement('div'); d.innerHTML = label + ' '; const i = document.createElement('input'); i.type = 'range'; i.min = min; i.max = max; i.value = val; i.style.width = '170px'; const o = document.createElement('span'); o.textContent = val; i.oninput = () => { o.textContent = i.value; fn(+i.value); }; d.append(i, o); el.append(d); };
    const A = () => window.__audio?.debug;
    const crashB = (imp, kind = 'wall') => () => bus.emit('car:collision', { car: cars[0], other: null, pos: cars[0].position, normal: { x: 1, y: 0, z: 0 }, impulse: imp, kind });
    btn('crash S', crashB(3000)); btn('crash M', crashB(12000)); btn('crash L', crashB(40000)); btn('car hit', crashB(15000, 'car'));
    btn('scrape 1s', () => { let n = 0; const id = setInterval(() => { bus.emit('car:scrape', { car: cars[0], pos: cars[0].position, normal: { x: 1, y: 0, z: 0 }, intensity: 0.8 }); if (++n > 60) clearInterval(id); }, 16); });
    btn('thump', () => A()?.trigger('thump', 0.8)); btn('siren', () => A()?.trigger('siren')); btn('PA', () => A()?.trigger('pa'));
    btn('3', () => bus.emit('race:countdown', { n: 3 })); btn('GO', () => bus.emit('race:countdown', { n: 0 })); btn('chime', () => A()?.trigger('chime', false)); btn('best', () => A()?.trigger('chime', true));
    el.append(document.createElement('br'));
    btn('start/stop sim', () => { if (race.phase === 'racing') { race.phase = 'grid'; } else { mock.instant(+(app.q.get('s') ?? 560), 2); ui.show('hud'); } });
    btn('regen', () => { mock.regen = !mock.regen; });
    for (const [n, s0] of [['boulevard', 300], ['underpass', 538], ['tunnel', 3700], ['market', 4200], ['expressway', 2500]]) btn(n, () => { const c = cars[0]; c._s = s0; c.race.progress = s0; });
    sl('speed km/h (hold)', 0, 330, 0, (v) => { mock.hold = v > 0 ? v : null; });
    sl('tyre slip', 0, 100, 0, (v) => { mock.skid = v / 100; });
    sl('volume', 0, 100, 80, (v) => { bus.emit('ui:volume', { volume: v / 100 }); });
    document.body.append(el);
  }

  window.__ui = {
    ui, race, mock, audio, T,
    show(name, arg) {
      if (name === 'title') { mock.reset(); race.camera.mode = 'orbit'; ui.show('title'); }
      else if (name === 'hud') { race.camera.mode = 'chase'; mock.instant(arg?.s ?? +(app.q.get('s') ?? 560), arg?.sim ?? 5); ui.show('hud'); }
      else if (name === 'countdown') { race.camera.mode = 'chase'; mock.reset(); ui.show('countdown', arg ?? 3); }
      else if (name === 'pause') { race.camera.mode = 'chase'; mock.instant(arg?.s ?? 560, 5); ui.show('hud'); ui.setPaused(true); }
      else if (name === 'results') { race.camera.mode = 'orbit'; mock.finishAll(); ui.show('results'); }
      return ui.screen;
    },
  };
  const first = app.q.get('screen'); if (first) window.__ui.show(first);

  poseAll();
  camPos = null;
  await app.ready();
}
