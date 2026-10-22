// Camera rig: chase (spring-damped, lag, look-ahead, speed FOV, shake), hood, bumper, cinematic orbit and a TV trackside cam.
// Writes app.camera in `late` unless app.viewLocked. Emits camera:mode. Keeps the camera inside the road corridor
// (barrier faces) and below the tunnel ceiling.
import * as THREE from 'three';
import { KIND, WALL_OFFSET } from '../track/track.js';
import { CAR } from './params.js';

const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const damp = (cur, tgt, lambda, dt) => cur + (tgt - cur) * (1 - Math.exp(-lambda * dt));
export const CAMERA_MODES = ['chase', 'hood', 'bumper', 'orbit', 'tv'];

const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _v3 = new THREE.Vector3(), _q = new THREE.Quaternion(), _m = new THREE.Matrix4();
const _up = new THREE.Vector3(0, 1, 0);

export class CameraRig {
  constructor(app, race, track, road) {
    this.app = app; this.race = race; this.track = track; this.road = road;
    this.mode = 'chase';
    this.target = race.cars[0];
    this.enabled = true;
    this.cycleModes = ['chase', 'hood', 'bumper'];
    this.cfg = {
      chase: { dist: 5.9, height: 1.62, lookAhead: 8.5, lookHeight: 0.95, fovLow: 60, fovHigh: 74 },
      hood: { pos: [0, 1.30, -0.78], fov: 76, look: [0, 1.02, -30] },
      bumper: { pos: [0, 0.46, -2.62], fov: 82, look: [0, 0.42, -30] },
      orbit: { radius: 7.4, height: 1.9, speed: 0.17, fov: 42 },
      tv: { spacing: 190, fovMin: 14, fovMax: 52 },
    };
    // smoothed state
    this.pos = new THREE.Vector3(); this.look = new THREE.Vector3(); this.fov = 60; this.roll = 0;
    this.heading = 0; this.headingVel = 0;
    this.back = this.cfg.chase.dist; this.up = this.cfg.chase.height; this.lat = 0; this.lookLat = 0;
    this.shake = 0; this.shakeT = 0; this.impact = 0;
    this.orbitT = 0;
    this._snap = true;
    this._blend = 1; this._blendFrom = { pos: new THREE.Vector3(), quat: new THREE.Quaternion(), fov: 60 };
    this._out = { pos: new THREE.Vector3(), quat: new THREE.Quaternion(), fov: 60 };
    this._lastTarget = new THREE.Vector3();
    this._tv = { idx: -1, pos: new THREE.Vector3() };
    this._probe = {};
    this.fovBoost = 0;
    this.outputFov = 60;
    this.offs = [];
    const bus = app.bus;
    if (bus) {
      this.offs.push(bus.on('car:collision', (e) => {
        if (e.car !== this.target && e.other !== this.target) return;
        this.impact = Math.min(1.2, this.impact + clamp(Math.sqrt(e.impulse) / 160, 0.1, 1));
      }));
    }
  }

  dispose() { this.offs.forEach(o => o()); }

  setTarget(car) { this.target = car; this.snap(); }
  snap() { this._snap = true; }

  setMode(m, silent = false) {
    if (!CAMERA_MODES.includes(m) || m === this.mode) return;
    const prev = this.mode;
    // blend from the current output pose
    this._blendFrom.pos.copy(this._out.pos); this._blendFrom.quat.copy(this._out.quat); this._blendFrom.fov = this._out.fov;
    this._blend = 0;
    this.mode = m;
    if (m === 'chase') this.snap();
    if (m === 'orbit') this.orbitT = 0;
    if (m === 'tv') this._tv.idx = -1;
    if (!silent) this.app.bus?.emit('camera:mode', { mode: m, previous: prev });
  }
  cycle() {
    const list = this.cycleModes;
    const i = list.indexOf(this.mode);
    this.setMode(list[(i + 1) % list.length]);
  }

  /** advance the rig; writes app.camera when allowed */
  update(dt) {
    if (!this.enabled) return;
    const c = this.target; if (!c) return;
    dt = Math.min(dt, 0.1);
    if (dt <= 0) { this._write(); return; }
    // teleport detection (respawn / restart)
    if (c.position.distanceToSquared(this._lastTarget) > 400) this._snap = true;
    this._lastTarget.copy(c.position);
    this.shakeT += dt;
    this.impact *= Math.exp(-5.5 * dt);
    switch (this.mode) {
      case 'chase': this._chase(c, dt); break;
      case 'hood': this._rigid(c, this.cfg.hood, dt); break;
      case 'bumper': this._rigid(c, this.cfg.bumper, dt); break;
      case 'orbit': this._orbit(c, dt); break;
      case 'tv': this._tvCam(c, dt); break;
    }
    // transition blend
    if (this._blend < 1) {
      this._blend = Math.min(1, this._blend + dt / 0.55);
      const k = smooth(0, 1, this._blend);
      this._out.pos.lerpVectors(this._blendFrom.pos, this._out.pos, k);
      this._out.quat.slerpQuaternions(this._blendFrom.quat, this._out.quat, k);
      this._out.fov = this._blendFrom.fov + (this._out.fov - this._blendFrom.fov) * k;
    }
    this._write();
  }

  _write() {
    const app = this.app;
    if (app.viewLocked) return;
    const cam = app.camera;
    cam.position.copy(this._out.pos);
    cam.quaternion.copy(this._out.quat);
    if (Math.abs(cam.fov - this._out.fov) > 0.01) { cam.fov = this._out.fov; cam.updateProjectionMatrix(); }
    this.outputFov = this._out.fov;
  }

  // ------------------------------------------------------------------ helpers
  _shakeOffset(speed, v, extra = 1) {
    // deterministic multi-sine shake; amplitude grows with speed², impacts add a burst
    const t = this.shakeT;
    const a = (0.0011 + 0.0034 * Math.pow(clamp(speed / 90, 0, 1), 2)) * extra;
    const b = this.impact * 0.1;
    const sx = Math.sin(t * 61.0) * 0.55 + Math.sin(t * 97.3 + 1.1) * 0.45;
    const sy = Math.sin(t * 53.7 + 2.0) * 0.55 + Math.sin(t * 83.1 + 0.4) * 0.45;
    const sz = Math.sin(t * 71.9 + 0.7);
    v.x = sx * (a + b); v.y = sy * (a * 0.9 + b); v.z = sz * a * 0.4;
    return this.impact * 0.045 * Math.sin(t * 47.0) + a * 0.35 * Math.sin(t * 59.0);       // extra roll (rad)
  }

  _clampToRoad(p, margin = 0.45, ceiling = true) {
    // re-seed the local search from the car after a snap/teleport (a stale hint pins the camera to the old road)
    const ti = this.target.track.i, N = this.track.N;
    let hint = this._probe.i ?? ti;
    if (this._snap || Math.min(Math.abs(hint - ti), N - Math.abs(hint - ti)) > 60) hint = ti;
    const pr = this.road.probe(p.x, p.z, hint, this._probe);
    const lim = pr.hw + WALL_OFFSET - margin;
    if (Math.abs(pr.u) > lim) {
      const over = pr.u - Math.sign(pr.u) * lim;
      p.x -= pr.rx * over; p.z -= pr.rz * over;
    }
    const minY = pr.y + 0.35;
    if (p.y < minY) p.y = minY;
    if (ceiling && pr.kind === KIND.TUNNEL) p.y = Math.min(p.y, pr.y + 3.4);
    return pr;
  }

  _lookQuat(pos, look, roll, out) {
    _m.lookAt(pos, look, _up);
    out.setFromRotationMatrix(_m);
    if (roll) { _q.setFromAxisAngle(_v3.set(0, 0, 1), roll); out.multiply(_q); }
  }

  // ------------------------------------------------------------------ chase
  _chase(c, dt) {
    const cfg = this.cfg.chase, v = c.velocity, spd = Math.hypot(v.x, v.z);
    const alongSpeed = c.speed;
    // heading: blend the body heading with the velocity direction when moving fast (so slides look good)
    _v.set(0, 0, -1).applyQuaternion(c.quaternion); _v.y = 0;
    const bodyHead = Math.atan2(_v.x, -_v.z);
    let targetHead = bodyHead;
    if (spd > 7 && alongSpeed > 0) {
      const velHead = Math.atan2(v.x, -v.z);
      let d = velHead - bodyHead; d = Math.atan2(Math.sin(d), Math.cos(d));
      targetHead = bodyHead + d * 0.55 * smooth(7, 24, spd);
    } else if (alongSpeed < -2) targetHead = bodyHead;       // reversing: stay behind the car
    if (this._snap) { this.heading = targetHead; this.headingVel = 0; }
    // critically damped angle spring
    let err = targetHead - this.heading; err = Math.atan2(Math.sin(err), Math.cos(err));
    const w = 5.2 + 2.0 * smooth(0, 40, spd);
    this.headingVel += (err * w * w - 2 * w * this.headingVel) * dt;
    this.heading += this.headingVel * dt;

    // offsets (in the heading frame): stretch back under acceleration, pull in under braking
    const aF = -c.accel.z;                          // forward specific acceleration
    const tBack = cfg.dist + 0.021 * spd + clamp(aF, -14, 12) * 0.075;     // stretches back on the throttle, closes in under braking
    const tUp = cfg.height + 0.0035 * spd - clamp(aF, -14, 12) * 0.004;
    const yawRate = -c.angularVelocity.y;           // + = turning right
    const tLat = clamp(-yawRate * 0.9, -1.6, 1.6) * smooth(5, 25, spd);   // camera swings to the outside of the corner
    if (this._snap) { this.back = tBack; this.up = tUp; this.lat = tLat; }
    this.back = damp(this.back, tBack, 4.2, dt);
    this.up = damp(this.up, tUp, 5.0, dt);
    this.lat = damp(this.lat, tLat, 2.4, dt);

    const sh = Math.sin(this.heading), ch = Math.cos(this.heading);
    // heading frame: forward = (sh, -ch), right = (ch, sh)
    const cx = c.position.x, cy = c.position.y, cz = c.position.z;
    let px = cx - sh * this.back + ch * this.lat;
    let pz = cz + ch * this.back + sh * this.lat;
    let py = cy + this.up;
    // vertical lag against the car's own height (bridge crests / ramps)
    if (this._snap) this.chaseY = py;
    this.chaseY = damp(this.chaseY ?? py, py, 9, dt);
    py = this.chaseY;
    _v2.set(px, py, pz);
    const pr = this._clampToRoad(_v2, 0.4);

    // look-ahead
    const la = cfg.lookAhead + 0.07 * spd;
    this.lookLat = damp(this.lookLat, clamp(-yawRate * 3.2, -3.2, 3.2) * smooth(4, 20, spd), 3.0, dt);
    let lx = cx + sh * la + ch * this.lookLat, lz = cz - ch * la + sh * this.lookLat, ly = cy + cfg.lookHeight + (pr ? 0 : 0);
    // follow the road slope a bit: look at road height ahead
    const lpr = this.road.probe(lx, lz, pr.i, this._probe2 ??= {});
    ly = Math.max(ly, lpr.y + 0.35) * 0.5 + (cy + cfg.lookHeight) * 0.5;
    if (this._snap) this.look.set(lx, ly, lz);
    this.look.x = damp(this.look.x, lx, 9, dt); this.look.y = damp(this.look.y, ly, 7, dt); this.look.z = damp(this.look.z, lz, 9, dt);

    // shake
    const roll0 = this._shakeOffset(spd, _v, 1);
    _v2.add(_v);
    const gLat = c.accel.x / 9.81;
    const roll = damp(this.roll, clamp(-gLat * 0.014, -0.035, 0.035) + roll0, 6, dt);
    this.roll = roll;
    // FOV
    const sp01 = smooth(0, 88, spd);
    const tFov = cfg.fovLow + (cfg.fovHigh - cfg.fovLow) * Math.pow(sp01, 0.85) + clamp(aF, 0, 12) * 0.12;
    if (this._snap) this.fov = tFov;
    this.fov = damp(this.fov, tFov, 3.2, dt);
    this._out.pos.copy(_v2);
    this._lookQuat(_v2, this.look, roll, this._out.quat);
    this._out.fov = this.fov + this._thrustKick(c, 6, dt);
    this._snap = false;
  }

  // the thrusters kick the view open quickly and let it settle back slowly (degrees)
  _thrustKick(c, deg, dt) {
    const want = deg * clamp(c.boost?.level ?? 0, 0, 1);
    if (this._snap) this.fovBoost = want;
    this.fovBoost = damp(this.fovBoost, want, want > this.fovBoost ? 7 : 2.2, dt);
    return this.fovBoost;
  }

  // ------------------------------------------------------------------ hood / bumper
  _rigid(c, cfg, dt) {
    _v.set(cfg.pos[0], cfg.pos[1], cfg.pos[2]).applyQuaternion(c.quaternion).add(c.position);
    _v2.set(cfg.look[0], cfg.look[1], cfg.look[2]).applyQuaternion(c.quaternion).add(c.position);
    const spd = Math.abs(c.speed);
    const roll0 = this._shakeOffset(spd, _v3, 1.4);
    _v.add(_v3);
    this._out.pos.copy(_v);
    // keep the horizon level-ish: use the car's own up (it pitches / rolls with the body), reduced by 35 %
    _v3.set(0, 1, 0).applyQuaternion(c.quaternion).lerp(_up, 0.35).normalize();
    _m.lookAt(_v, _v2, _v3);
    this._out.quat.setFromRotationMatrix(_m);
    if (roll0) { _q.setFromAxisAngle(_v3.set(0, 0, 1), roll0); this._out.quat.multiply(_q); }
    const sp01 = smooth(0, 88, spd);
    const tFov = cfg.fov + 7 * sp01;
    this.fov = this._snap ? tFov : damp(this.fov, tFov, 3.5, dt);
    this._out.fov = this.fov + this._thrustKick(c, 3, dt);
    this._snap = false;
  }

  // ------------------------------------------------------------------ cinematic orbit
  _orbit(c, dt) {
    const cfg = this.cfg.orbit;
    this.orbitT += dt;
    const t = this.orbitT;
    // start looking at the front 3/4 of the car
    _v.set(0, 0, -1).applyQuaternion(c.quaternion); _v.y = 0;
    const head = Math.atan2(_v.x, -_v.z);
    const ang = head + 0.62 + t * cfg.speed + Math.sin(t * 0.31) * 0.25;
    const r = cfg.radius + Math.sin(t * 0.23) * 0.9 + Math.min(3, Math.abs(c.speed) * 0.05);
    const h = cfg.height + Math.sin(t * 0.19 + 1) * 0.55;
    // ang is measured from the car's forward: position = car + R(ang) * (0, h, -r)
    const px = c.position.x + Math.sin(ang) * r, pz = c.position.z - Math.cos(ang) * r;
    _v2.set(px, c.position.y + h, pz);
    this._clampToRoad(_v2, 0.35);
    this.look.set(c.position.x, c.position.y + 0.62, c.position.z);
    this._out.pos.copy(_v2);
    this._lookQuat(_v2, this.look, 0, this._out.quat);
    this.fov = damp(this.fov, cfg.fov, 2, dt);
    this._out.fov = this._snap ? cfg.fov : this.fov;
    this._snap = false;
  }

  // ------------------------------------------------------------------ TV trackside
  _tvCam(c, dt) {
    const cfg = this.cfg.tv, T = this.track;
    const s = c.track.s;
    const sp = Math.max(8, Math.abs(c.speed));
    // station ahead: spaced every `spacing` metres, at least 28 m + 0.7 s of travel ahead
    const minAhead = 28 + sp * 0.7;
    let idx = Math.ceil((s + minAhead) / cfg.spacing);
    if (this._tv.idx < 0 || idx !== this._tv.idx && T.deltaS(this._tv.idx * cfg.spacing, s) > 6 || idx < this._tv.idx - 1) {
      this._tv.idx = idx;
      const ss = T.wrapS(idx * cfg.spacing);
      const f = T.frameAt(ss);
      const side = (idx % 2 === 0) ? 1 : -1;
      // trackside behind the barrier; in tunnels / trenches (solid rock or retaining walls) tuck in beside the barrier instead
      const enclosed = f.kind === KIND.TUNNEL || f.kind === KIND.TRENCH;
      const u = side * (enclosed ? f.hw - 0.7 : f.hw + WALL_OFFSET + 1.4);
      T.pointAt(ss, u, this._tv.pos);
      this._tv.pos.y += enclosed ? 1.3 + (idx % 3) * 0.25 : 1.9 + (idx % 3) * 0.7;
      this._tvSnap = true;
    }
    const dx = c.position.x - this._tv.pos.x, dy = c.position.y - this._tv.pos.y, dz = c.position.z - this._tv.pos.z;
    const dist = Math.hypot(dx, dy, dz);
    // aim slightly ahead of the car
    _v.set(c.velocity.x, 0, c.velocity.z).multiplyScalar(0.12).add(c.position); _v.y = c.position.y + 0.55;
    if (this._tvSnap) { this.look.copy(_v); this._tvSnap = false; }
    this.look.x = damp(this.look.x, _v.x, 7, dt); this.look.y = damp(this.look.y, _v.y, 7, dt); this.look.z = damp(this.look.z, _v.z, 7, dt);
    const tFov = clamp(2 * Math.atan(6.5 / Math.max(dist, 8)) * 57.2958, cfg.fovMin, cfg.fovMax);
    this.fov = damp(this.fov, tFov, 5, dt);
    _v2.copy(this._tv.pos);
    const roll0 = this._shakeOffset(0, _v3, 0.5) * 0.2;
    this._out.pos.copy(_v2);
    this._lookQuat(_v2, this.look, roll0, this._out.quat);
    this._out.fov = this.fov;
    this._snap = false;
  }
}
