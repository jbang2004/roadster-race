// Vehicle FX (owner C): tyre spray and rooster-tail mist on the wet road (scaled by speed and G.uWet), light tyre smoke on
// wheelspin / lock-up, water splashes, and sparks / debris from `car:collision` and `car:scrape` (bus).
//   const fx = createVehicleFx(app);  fx.update(dt, race.cars)  every frame;  fx.dispose()
// Everything is GPU-evaluated analytic particles in ring buffers: 3 draw calls (mist+smoke, streaks, sparks).
// The mist is lit per particle from the nearest static lights (lights.nearest) and the cars' own head / tail / brake
// lights, so spray behind a car glows red under its brake lights and white in the beam of the car behind.
// Layer: LAYER.LATE (drawn by R after the car pass, depth-tested against world and cars).
import * as THREE from 'three';
import { JET_EXITS } from '../car/jets.js';
import { LAYER } from '../core/layers.js';
import { G } from '../core/globals.js';
import { bus } from '../core/bus.js';
import { lights as staticLights } from '../core/lights.js';
import { NL, MIST_VERT, MIST_FRAG, STREAK_VERT, STREAK_FRAG } from './shaders.js';

const AMB0 = new THREE.Color(0.16, 0.17, 0.23);
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const HEAD_CD = 5500, MAX_RANGE = 150;

function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

class Ring {
  constructor(n) {
    this.n = n; this.head = 0; this.dirty = false;
    this.aP0 = new Float32Array(n * 4).fill(0); this.aV0 = new Float32Array(n * 4); this.aPar = new Float32Array(n * 4);
    this.aCol = new Float32Array(n * 4); this.aKind = new Float32Array(n);
    for (let i = 0; i < n; i++) this.aP0[i * 4 + 3] = -1e6;            // never spawned
    const base = new THREE.PlaneGeometry(1, 1);
    const g = new THREE.InstancedBufferGeometry();
    g.index = base.index; g.setAttribute('position', base.attributes.position); g.setAttribute('uv', base.attributes.uv);
    const mk = (arr, size, name) => { const a = new THREE.InstancedBufferAttribute(arr, size); a.setUsage(THREE.DynamicDrawUsage); g.setAttribute(name, a); return a; };
    this.attrs = [mk(this.aP0, 4, 'aP0'), mk(this.aV0, 4, 'aV0'), mk(this.aPar, 4, 'aPar'), mk(this.aCol, 4, 'aCol'), mk(this.aKind, 1, 'aKind')];
    g.instanceCount = n;
    this.geometry = g;
  }
  spawn(px, py, pz, t0, vx, vy, vz, life, s0, s1, seed, gy, r, g, b, a, kind) {
    const i = this.head; this.head = (i + 1) % this.n;
    const o = i * 4;
    this.aP0[o] = px; this.aP0[o + 1] = py; this.aP0[o + 2] = pz; this.aP0[o + 3] = t0;
    this.aV0[o] = vx; this.aV0[o + 1] = vy; this.aV0[o + 2] = vz; this.aV0[o + 3] = life;
    this.aPar[o] = s0; this.aPar[o + 1] = s1; this.aPar[o + 2] = seed; this.aPar[o + 3] = gy;
    this.aCol[o] = r; this.aCol[o + 1] = g; this.aCol[o + 2] = b; this.aCol[o + 3] = a;
    this.aKind[i] = kind;
    this.dirty = true;
  }
  upload() { if (!this.dirty) return; for (const a of this.attrs) a.needsUpdate = true; this.dirty = false; }
  dispose() { this.geometry.dispose(); }
}

export function createVehicleFx(app, { layer = LAYER.LATE, mistCount = 9000, streaks = 4096, sparks = 2048 } = {}) {
  const quality = app.quality ?? 'high';
  const qk = quality === 'low' ? 0.4 : quality === 'medium' ? 0.7 : 1;
  const rnd = mulberry32(20241018);
  const R = (a = 0, b = 1) => a + (b - a) * rnd();
  const group = new THREE.Group(); group.name = 'VehicleFx';
  app.scene.add(group);
  let T = 0;
  const tune = { spray: 1, sprayA: 1, tail: 1, tailA: 1, smoke: 1, size: 1, drops: 1, jet: 1, ambK: 3, lightK: 0.06 };

  const uni = {
    uTime: { value: 0 }, uStreak: { value: 0.045 },
    uKind: { value: [new THREE.Vector4(1.7, -0.5, 0.25, 2.2), new THREE.Vector4(0.8, 0.45, 0.7, 1.6), new THREE.Vector4(0.9, 0.55, 0.5, 1.5), new THREE.Vector4(1.3, -0.2, 0.3, 2.0),
      new THREE.Vector4(3.2, -0.25, 0.35, 3.4)] },
    uLPos: { value: Array.from({ length: NL }, () => new THREE.Vector4()) },
    uLCol: { value: Array.from({ length: NL }, () => new THREE.Vector4(0, 0, 0, -2)) },
    uLDir: { value: Array.from({ length: NL }, () => new THREE.Vector4(0, 0, -1, 0.95)) },
    uAmb: { value: new THREE.Color(0.012, 0.017, 0.03) }, uLK: { value: 0.06 },
  };
  const mkMat = (vs, fs, defines, blending) => {
    const m = new THREE.ShaderMaterial({
      vertexShader: vs, fragmentShader: fs, defines, transparent: true, depthWrite: false, depthTest: true, blending, premultipliedAlpha: blending === THREE.NormalBlending, fog: true,
      uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, uni]),
    });
    // share the same uniform value objects between the three materials
    for (const k of Object.keys(uni)) m.uniforms[k] = uni[k];
    return m;
  };
  const rings = {
    mist: new Ring(Math.floor(mistCount * qk)), streak: new Ring(Math.floor(streaks * qk)), spark: new Ring(Math.floor(sparks * qk)),
  };
  const mesh = (ring, mat, order) => {
    const m = new THREE.Mesh(ring.geometry, mat);
    m.frustumCulled = false; m.renderOrder = order; m.layers.set(layer); m.name = 'FX';
    group.add(m); return m;
  };
  const mistMat = mkMat(MIST_VERT, MIST_FRAG, {}, THREE.NormalBlending);
  const streakMat = mkMat(STREAK_VERT, STREAK_FRAG, {}, THREE.NormalBlending);
  const sparkMat = mkMat(STREAK_VERT, STREAK_FRAG, { SPARK: '' }, THREE.AdditiveBlending);
  const meshes = [mesh(rings.mist, mistMat, 20), mesh(rings.streak, streakMat, 21), mesh(rings.spark, sparkMat, 22)];

  // ------------------------------------------------------------------------------------- spawners
  const tintJet = [0.88, 0.93, 1.0], tintSpray = [0.86, 0.92, 1.0], tintSmoke = [0.78, 0.78, 0.8], tintDust = [0.55, 0.52, 0.5];
  const gy_ = (car, w) => (w && w.contact && Number.isFinite(w.contact.y) ? w.contact.y : car.position.y);
  const mist = (kind, p, v, life, s0, s1, a, tint, gy) => rings.mist.spawn(p.x, p.y, p.z, T, v.x, v.y, v.z, life, s0, s1, rnd(), gy, tint[0], tint[1], tint[2], a, kind);
  const drop = (p, v, life, w, a, gy, chip = 0, tint = tintSpray) => rings.streak.spawn(p.x, p.y, p.z, T, v.x, v.y, v.z, life, w, w, rnd(), gy, tint[0], tint[1], tint[2], a, chip);
  const spark = (p, v, life, w, hot, gy) => rings.spark.spawn(p.x, p.y, p.z, T, v.x, v.y, v.z, life, w, w, rnd(), gy, 9 * hot, 3.4 * hot * R(0.5, 1), 0.8 * hot * R(0.3, 1), 1, 0);

  const q = new THREE.Quaternion(), fwd = new THREE.Vector3(), right = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), vdir = new THREE.Vector3();
  const P = new THREE.Vector3(), V = new THREE.Vector3(), tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();
  const states = new WeakMap();
  const stateOf = (car) => { let s = states.get(car); if (!s) { s = { spray: [0, 0, 0, 0], smoke: [0, 0, 0, 0], tail: 0, splash: 0, drops: [0, 0, 0, 0], jet: 0, jetOn: 0 }; states.set(car, s); } return s; };
  const camPos = new THREE.Vector3(), camDir = new THREE.Vector3();

  function emitCar(car, dt) {
    const s = stateOf(car);
    const speed = Math.abs(car.speed ?? 0);
    q.copy(car.quaternion);
    fwd.set(0, 0, -1).applyQuaternion(q); right.set(1, 0, 0).applyQuaternion(q);
    // direction of travel (horizontal)
    vdir.copy(car.velocity ?? fwd); vdir.y = 0;
    if (vdir.lengthSq() < 0.5) vdir.copy(fwd).multiplyScalar(Math.sign(car.speed || 1)); vdir.normalize();
    const wet = clamp(G.uWet.value, 0, 1);
    const kv = smooth(5, 48, speed);
    const rainK = 0.55 + 0.45 * clamp(G.uRain.value * 2, 0, 1);

    for (let i = 0; i < 4; i++) {
      const w = car.wheels?.[i]; if (!w || w.grounded === false) continue;
      const front = i < 2, outward = (i % 2 ? 1 : -1);
      const gy = gy_(car, w);
      const slip = Math.max(Math.abs(w.slipRatio ?? 0), w.skid ?? 0);
      // ---- tyre spray
      const rate = wet * rainK * Math.pow(kv, 1.25) * (front ? 110 : 190) * (1 + 0.8 * slip) * qk * tune.spray;
      s.spray[i] += rate * dt;
      while (s.spray[i] >= 1) {
        s.spray[i] -= 1;
        P.copy(w.contact).addScaledVector(vdir, -R(0.05, 0.4)).addScaledVector(right, outward * R(-0.02, 0.16)).addScaledVector(up, 0.05 + R(0, 0.14));
        V.copy(vdir).multiplyScalar(speed * R(0.08, 0.2)).addScaledVector(right, outward * R(0.4, 2.4) * (front ? 1.4 : 0.8)).addScaledVector(up, R(0.8, 1.8) + speed * R(0, 0.045));
        mist(0, P, V, R(0.6, 1.2), R(0.14, 0.26) * tune.size, R(0.9, 1.7) * (front ? 0.85 : 1.1) * tune.size, R(0.2, 0.38) * tune.sprayA, tintSpray, gy);
        if (rnd() < 0.22 * qk * tune.drops) {      // fine droplets in the fan
          V.multiplyScalar(R(0.9, 1.8)).addScaledVector(up, R(1.0, 3.2));
          drop(P, V, R(0.45, 0.9), R(0.009, 0.017), 0.6, gy);
        }
      }
      // ---- smoke on wheelspin / lock-up
      const sm = smooth(0.22, 0.7, slip) * (0.35 + 0.65 * smooth(1.5, 14, speed));
      s.smoke[i] += sm * 85 * (1 - 0.3 * wet) * qk * tune.smoke * dt;
      while (s.smoke[i] >= 1) {
        s.smoke[i] -= 1;
        P.copy(w.contact).addScaledVector(up, 0.06).addScaledVector(right, R(-0.1, 0.1));
        V.copy(vdir).multiplyScalar(speed * R(0.35, 0.6)).addScaledVector(right, outward * R(0, 0.8)).addScaledVector(up, R(0.4, 1.1));
        mist(2, P, V, R(1.4, 2.6), R(0.25, 0.4), R(1.8, 3.0), R(0.10, 0.19), tintSmoke, gy);
      }
    }
    // ---- rooster tail: the wake behind the car lifts a sheet of mist
    const gyC = gy_(car, car.wheels?.[2]);
    s.tail += wet * rainK * Math.pow(smooth(16, 75, speed), 1.15) * 170 * qk * tune.tail * dt;
    while (s.tail >= 1) {
      s.tail -= 1;
      P.copy(car.position).addScaledVector(vdir, -R(2.1, 2.9)).addScaledVector(right, R(-0.85, 0.85)).addScaledVector(up, R(0.12, 0.45));
      V.copy(vdir).multiplyScalar(speed * R(0.1, 0.24)).addScaledVector(right, R(-1.4, 1.4)).addScaledVector(up, R(1.8, 3.0) + speed * R(0.01, 0.05));
      mist(1, P, V, R(1.3, 2.4), R(0.5, 0.9) * tune.size, R(2.4, 3.8) * tune.size, R(0.12, 0.24) * tune.tailA, tintSpray, gyC);
    }
    // ---- cold-gas thrusters: condensed vapour streaming out of the four nozzles (cold air + humid night = visible fog),
    // a puff when the valves crack open, and the blast kicking the standing water up off the road behind the car
    const jl = car.boost?.level ?? 0;
    if (jl > 0.02) {
      const back = tmp2.set(0, 0, 1).applyQuaternion(q);
      const burst = s.jetOn < 0.05 ? 1 : 0; s.jetOn = 1;
      s.jet += 110 * jl * qk * tune.jet * dt + burst * 14 * qk;
      const cv = car.velocity;
      while (s.jet >= 1) {
        s.jet -= 1;
        const e = JET_EXITS[(rnd() * 4) | 0];
        P.copy(e).applyQuaternion(q).add(car.position).addScaledVector(back, R(0.02, 0.25));
        V.copy(back).multiplyScalar(R(10, 22) * (0.5 + 0.5 * jl)).addScaledVector(right, R(-1.5, 1.5)).addScaledVector(up, R(-1.2, 1.2));
        if (cv) V.add(cv);
        mist(4, P, V, R(0.35, 0.7), R(0.06, 0.1), R(0.8, 1.4), R(0.14, 0.26) * (0.4 + 0.6 * jl) * (0.6 + 0.4 * wet), tintJet, gyC);
      }
      if (wet > 0.05 && rnd() < wet * jl * 26 * qk * dt * 4) {      // blast spray off the wet road
        P.copy(car.position).addScaledVector(back, R(3.0, 4.5)).addScaledVector(right, R(-0.6, 0.6)).addScaledVector(up, 0.08);
        V.copy(back).multiplyScalar(R(4, 9)).addScaledVector(right, R(-1.5, 1.5)).addScaledVector(up, R(1.2, 2.6));
        if (cv) V.addScaledVector(cv, 0.4);
        mist(0, P, V, R(0.5, 0.9), R(0.25, 0.4), R(1.0, 1.7), R(0.08, 0.16) * tune.sprayA, tintSpray, gyC);
      }
    } else s.jetOn = Math.max(0, s.jetOn - dt * 2);

    // ---- water splashes (puddles): bursts of droplets
    s.splash += wet * smooth(8, 60, speed) * 2.2 * dt;
    while (s.splash >= 1) {
      s.splash -= 1;
      const wi = (rnd() * 4) | 0, w = car.wheels?.[wi]; if (!w) continue;
      const outward = (wi % 2 ? 1 : -1), gy = gy_(car, w);
      const nd = Math.floor(R(8, 16) * qk) + 2;
      for (let k = 0; k < nd; k++) {
        P.copy(w.contact).addScaledVector(up, 0.05).addScaledVector(right, outward * R(0, 0.2));
        V.copy(vdir).multiplyScalar(speed * R(0.1, 0.45)).addScaledVector(right, outward * R(1.0, 5.0)).addScaledVector(up, R(2.5, 6.5));
        drop(P, V, R(0.5, 1.0), R(0.012, 0.03), 0.75, gy);
      }
      for (let k = 0; k < 3; k++) {
        P.copy(w.contact).addScaledVector(up, 0.1);
        V.copy(vdir).multiplyScalar(speed * 0.15).addScaledVector(right, outward * R(0.6, 2.2)).addScaledVector(up, R(1.2, 2.4));
        mist(0, P, V, R(0.7, 1.2), R(0.3, 0.45), R(1.3, 2.1), R(0.1, 0.18), tintSpray, gy);
      }
    }
  }

  // ------------------------------------------------------------------------------------- bus events
  const toV = (o, out) => o?.isVector3 ? out.copy(o) : Array.isArray(o) ? out.set(o[0], o[1], o[2]) : out.set(o?.x ?? 0, o?.y ?? 0, o?.z ?? 0);
  const N = new THREE.Vector3(), Tg = new THREE.Vector3(), Bt = new THREE.Vector3();
  function frame(n) { // tangent frame around the surface normal
    Tg.set(Math.abs(n.y) < 0.9 ? 0 : 1, Math.abs(n.y) < 0.9 ? 1 : 0, 0).cross(n).normalize(); Bt.copy(n).cross(Tg);
  }
  function burst(e, scale) {
    toV(e.pos, P); toV(e.normal, N); if (N.lengthSq() < 1e-4) N.set(0, 1, 0); N.normalize();
    const gy = e.car?.position?.y ?? P.y - 0.4;
    const impulse = e.impulse ?? 4000;
    frame(N);
    const wall = (e.kind ?? 'wall') === 'wall';
    const ns = Math.floor(clamp(impulse / 280, 10, 260) * scale * (wall ? 1 : 0.5) * qk);
    const sp = clamp(3 + impulse / 6000, 3, 12);
    const carV = e.car?.velocity;
    for (let i = 0; i < ns; i++) {
      V.copy(N).multiplyScalar(R(0.5, 1.4) * sp * 0.5).addScaledVector(Tg, R(-1, 1) * sp).addScaledVector(Bt, R(-1, 1) * sp).addScaledVector(up, R(0.4, 2.4));
      if (carV) V.addScaledVector(carV, 0.35);
      spark(P, V, R(0.35, 1.1), R(0.016, 0.04), R(0.8, 1.7), gy);
    }
    const nd = Math.floor(clamp(impulse / 3500, 2, 24) * scale * qk);
    for (let i = 0; i < nd; i++) {
      V.copy(N).multiplyScalar(R(1, 4)).addScaledVector(Tg, R(-3, 3)).addScaledVector(Bt, R(-3, 3)).addScaledVector(up, R(1, 4));
      const g = R(0.04, 0.2); const tint = rnd() < 0.5 ? [g, g, g * 1.05] : [0.55 * g * 4, 0.56 * g * 4, 0.6 * g * 4];
      drop(P, V, R(0.8, 1.6), R(0.014, 0.034), 0.95, gy, 1, tint);
    }
    const np = Math.floor(clamp(impulse / 6000, 1, 8) * scale);
    for (let i = 0; i < np; i++) {
      V.copy(N).multiplyScalar(R(0.4, 1.6)).addScaledVector(Tg, R(-1, 1)).addScaledVector(Bt, R(-1, 1)).addScaledVector(up, R(0.3, 1.2));
      mist(3, P, V, R(0.8, 1.6), R(0.25, 0.4), R(1.2, 2.2), R(0.12, 0.22), tintDust, gy);
    }
  }
  const offs = [
    bus.on('car:collision', e => burst(e, 1)),
    bus.on('car:scrape', e => {
      toV(e.pos, P); toV(e.normal, N); if (N.lengthSq() < 1e-4) N.set(0, 1, 0); N.normalize(); frame(N);
      const gy = e.car?.position?.y ?? P.y - 0.4;
      const k = clamp(e.intensity ?? 0.5, 0, 1);
      const n = Math.floor(k * 30 * qk + rnd());
      const fw = e.car?.velocity;
      for (let i = 0; i < n; i++) {
        V.copy(N).multiplyScalar(R(0.2, 1.5)).addScaledVector(Tg, R(-1, 1) * 2).addScaledVector(Bt, R(-1, 1) * 2).addScaledVector(up, R(0.2, 1.6));
        if (fw) V.addScaledVector(fw, R(0.1, 0.4));
        spark(P, V, R(0.25, 0.8), R(0.012, 0.026), R(0.8, 1.5), gy);
      }
      if (rnd() < k * 0.5) { V.copy(N).multiplyScalar(0.8).addScaledVector(up, 0.5); mist(3, P, V, R(0.7, 1.2), 0.2, R(0.9, 1.5), 0.1, tintDust, gy); }
    }),
  ];

  // ------------------------------------------------------------------------------------- lights for the particles
  const cand = [];
  const cpool = Array.from({ length: 40 }, () => ({ pos: new THREE.Vector3(), col: new THREE.Vector3(), dir: new THREE.Vector3(), cosO: -2, cosI: 0.9, range: 0, w: 0, spot: false }));
  let cn = 0;
  const addCand = (pos, col, spot = null, range = 0) => {
    if (cn >= cpool.length) return;
    const c = cpool[cn++]; c.pos.copy(pos); c.col.copy(col); c.range = range;
    c.spot = !!spot;
    if (spot) { c.dir.copy(spot.dir); c.cosO = spot.cosO; c.cosI = spot.cosI; }
  };
  const ref = new THREE.Vector3();
  function gatherLights(cars) {
    cn = 0;
    app.camera.getWorldPosition(camPos); app.camera.getWorldDirection(camDir);
    ref.copy(camPos).addScaledVector(camDir, 12);
    for (const car of cars) {
      if (!car.position || car.position.distanceTo(camPos) > 110) continue;
      q.copy(car.quaternion);
      const L = car.lights;
      if (L?.head !== false) {
        tmp.set(0, 0.55, -2.5).applyQuaternion(q).add(car.position);
        tmp2.set(0, -0.025, -1).applyQuaternion(q);
        V.set(1, 0.955, 0.9).multiplyScalar(HEAD_CD);
        addCand(tmp, V, { dir: tmp2, cosO: Math.cos(0.4), cosI: Math.cos(0.18) }, 90);
      }
      const br = L?.brake ?? 0;
      tmp.set(0, 0.8, 2.6).applyQuaternion(q).add(car.position);
      V.set(1, 0.07, 0.05).multiplyScalar(10 + 150 * br);
      addCand(tmp, V, null, 20);
    }
    const near = staticLights.nearest(ref, NL, null, 70);
    for (const l of near) addCand(l.pos, V.set(l.color.r, l.color.g, l.color.b).multiplyScalar(l.intensity), null, l.range || 0);
    // keep the NL most relevant at the reference point (selection, no allocation)
    for (let i = 0; i < cn; i++) { const c = cpool[i]; c.w = (c.col.x + c.col.y + c.col.z) / (c.pos.distanceToSquared(ref) + 4) * (c.spot ? 1.4 : 1); }
    for (let i = 0; i < NL; i++) {
      let best = -1, bw = -1;
      for (let j = 0; j < cn; j++) { const c = cpool[j]; if (c.w > bw) { bw = c.w; best = j; } }
      const lp = uni.uLPos.value[i], lc = uni.uLCol.value[i], ld = uni.uLDir.value[i];
      if (best >= 0) {
        const c = cpool[best]; c.w = -1;
        lp.set(c.pos.x, c.pos.y, c.pos.z, c.range);
        lc.set(c.col.x, c.col.y, c.col.z, c.spot ? c.cosO : -2);
        ld.set(c.dir.x, c.dir.y, c.dir.z, c.cosI);
      } else { lp.set(0, 0, 0, 0); lc.set(0, 0, 0, -2); }
    }
  }

  // ------------------------------------------------------------------------------------- public
  const fx = {
    group, meshes,
    /** dt: seconds; cars: array of Car state (CONTRACTS §Car state) */
    update(dt, cars) {
      app.camera.getWorldPosition(camPos);
      if (dt > 0) {
        T += dt;
        for (const car of cars) {
          if (!car || !car.position || !car.quaternion) continue;
          if (car.position.distanceTo(camPos) > MAX_RANGE) continue;
          emitCar(car, dt);
        }
      }
      uni.uTime.value = T;
      uni.uLK.value = tune.lightK;
      const fog = app.scene.fog;
      if (fog && fog.color) uni.uAmb.value.copy(fog.color).multiplyScalar(tune.ambK).add(AMB0);
      gatherLights(cars);
      for (const k in rings) rings[k].upload();
    },
    /** ambient scatter colour for the mist (linear); K may call this when the sky changes */
    setAmbient(c) { uni.uAmb.value.copy(c); },
    uniforms: uni, tune,
    /** direct spawns, for scripted effects: sparks / dust at a point */
    burst(pos, normal, impulse = 8000, kind = 'wall', car = null) { burst({ pos, normal, impulse, kind, car }, 1); },
    stats() { return { mist: rings.mist.n, streak: rings.streak.n, spark: rings.spark.n, time: T }; },
    dispose() {
      offs.forEach(f => f());
      for (const k in rings) rings[k].dispose();
      for (const m of [mistMat, streakMat, sparkMat]) m.dispose();
      group.removeFromParent();
    },
  };
  return fx;
}
