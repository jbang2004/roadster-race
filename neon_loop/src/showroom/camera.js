// Orbit camera for the showroom: inertia + damping, zoom to the point under the cursor, limited pan, preset flights, idle turntable,
// mouse / touch (one finger orbit, two fingers pinch + pan) / keyboard. The camera never enters the car (SDF of the body, see hull.js)
// and never goes below the floor.
import * as THREE from 'three';

const clamp = THREE.MathUtils.clamp;
const TAU = Math.PI * 2;
const ease = (t) => t * t * t * (t * (t * 6 - 15) + 10);
const wrapPi = (a) => { a = (a + Math.PI) % TAU; if (a < 0) a += TAU; return a - Math.PI; };

export const LIMITS = {
  dist: [0.2, 12.5], pitch: [-0.05, 1.5], floorY: 0.13, hullMargin: 0.34, maxR: 11.5, maxY: 12.6,
  pan: { min: new THREE.Vector3(-2.3, 0.08, -3.4), max: new THREE.Vector3(2.3, 1.7, 3.4) },
};

export class OrbitRig {
  /** camera: PerspectiveCamera, dom: the canvas, hull: buildHull() result */
  constructor(camera, dom, hull) {
    this.camera = camera; this.dom = dom; this.hull = hull;
    this.yaw = -0.8; this.pitch = 0.18; this.dist = 8.5; this.fov = 30;
    this.target = new THREE.Vector3(0, 0.55, -0.2);
    this.goal = { dist: this.dist, target: this.target.clone(), fov: this.fov };
    this.vYaw = 0; this.vPitch = 0;
    this.anim = null;
    this.idle = 0; this.autoSpeed = 0; this.autoOn = true; this.autoDelay = 5; this.autoRate = 0.11;
    this.enabled = true;
    this.margin = LIMITS.hullMargin;
    this.aspect = 16 / 9;
    this.listeners = [];
    this.onInput = null;                         // called on any user input (the scene resets idle timers)
    this.pointers = new Map();
    this.last = { x: 0, y: 0 };
    this.gesture = null;
    this.keys = new Set();
    this.eye = new THREE.Vector3();
    this._bind();
  }

  // ------------------------------------------------------------------------------------------ presets
  /** fly to a view given in world coordinates (pos / target), fov in degrees. dur seconds. */
  flyTo(pos, target, fov, dur = 1.1, margin = LIMITS.hullMargin) {
    const t = new THREE.Vector3().fromArray(target);
    const d = new THREE.Vector3().fromArray(pos).sub(t);
    const dist = d.length();
    const to = { yaw: Math.atan2(d.x, d.z), pitch: Math.asin(clamp(d.y / dist, -1, 1)), dist, target: t, fov };
    const from = { yaw: this.yaw, pitch: this.pitch, dist: this.dist, target: this.target.clone(), fov: this.fov };
    to.yaw = from.yaw + wrapPi(to.yaw - from.yaw);
    this.anim = { from, to, t: 0, dur: Math.max(dur, 1e-3) };
    this.margin = margin;
    this.vYaw = this.vPitch = 0;
    this.idle = 0;
  }
  /** set instantly (screenshots) */
  jumpTo(pos, target, fov, margin = LIMITS.hullMargin) {
    this.flyTo(pos, target, fov, 1, margin);
    this.anim.t = 1;
    this._step(0);
    this.anim = null;
  }

  // ------------------------------------------------------------------------------------------ input
  _bind() {
    const el = this.dom;
    el.style.touchAction = 'none';
    const on = (t, fn, o) => { el.addEventListener(t, fn, o); this.listeners.push([el, t, fn, o]); };
    const onWin = (t, fn) => { window.addEventListener(t, fn); this.listeners.push([window, t, fn]); };
    on('contextmenu', (e) => e.preventDefault());
    on('pointerdown', (e) => {
      if (!this.enabled) return;
      el.setPointerCapture?.(e.pointerId);
      this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t0: performance.now(), button: e.button, type: e.pointerType });
      this._touched();
      if (this.pointers.size === 1) {
        const pan = e.button === 2 || e.button === 1 || e.shiftKey || e.ctrlKey || e.altKey;
        this.gesture = { mode: pan ? 'pan' : 'orbit', moved: 0 };
        this.vYaw = this.vPitch = 0;
        this.anim = null;
      } else if (this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()];
        this.gesture = { mode: 'pinch', d0: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2, moved: 0 };
        this.anim = null;
      }
    });
    on('pointermove', (e) => {
      const p = this.pointers.get(e.pointerId);
      this.last.x = e.clientX; this.last.y = e.clientY;
      if (!p || !this.gesture) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;
      const g = this.gesture;
      g.moved += Math.abs(dx) + Math.abs(dy);
      if (g.mode === 'orbit' && this.pointers.size === 1) {
        const k = 2.9 / Math.max(this.dom.clientHeight, 300);
        this.yaw -= dx * k; this.pitch += dy * k;
        this.vYaw = -dx * k * 60 * 0.6 + this.vYaw * 0.4; this.vPitch = dy * k * 60 * 0.6 + this.vPitch * 0.4;
        this._touched();
      } else if (g.mode === 'pan' && this.pointers.size === 1) {
        this._pan(dx, dy); this._touched();
      } else if (g.mode === 'pinch' && this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        if (g.d0 > 4 && d > 4) { this._zoomAt(g.d0 / d, mx, my, true); }
        this._pan(mx - g.mx, my - g.my);
        g.d0 = d; g.mx = mx; g.my = my; this._touched();
      }
    });
    const up = (e) => {
      const p = this.pointers.get(e.pointerId);
      if (p) {
        const tap = performance.now() - p.t0 < 320 && Math.hypot(e.clientX - p.x0, e.clientY - p.y0) < 8 && this.gesture && this.pointers.size === 1;
        this.pointers.delete(e.pointerId);
        if (tap) { this._tap(e, p); }
      }
      if (this.pointers.size === 0) this.gesture = null;
      else if (this.pointers.size === 1) { this.gesture = { mode: 'orbit', moved: 99 }; this.vYaw = this.vPitch = 0; }
    };
    on('pointerup', up); on('pointercancel', up);
    on('wheel', (e) => {
      if (!this.enabled) return;
      e.preventDefault();
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      this._zoomAt(Math.exp(clamp(dy, -240, 240) * 0.0011), e.clientX, e.clientY, false);
      this.anim = null; this._touched();
    }, { passive: false });
    onWin('keydown', (e) => { if (e.metaKey || e.ctrlKey || e.altKey) return; const tg = e.target; if (tg && /INPUT|TEXTAREA|SELECT/.test(tg.tagName)) return; this.keys.add(e.code); if (this._isNav(e.code)) { this._touched(); } });
    onWin('keyup', (e) => this.keys.delete(e.code));
    onWin('blur', () => this.keys.clear());
    this._lastTap = { t: 0, x: 0, y: 0 };
  }
  _isNav(c) { return ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'KeyA', 'KeyD', 'KeyW', 'KeyS', 'Equal', 'Minus', 'NumpadAdd', 'NumpadSubtract', 'PageUp', 'PageDown'].includes(c); }
  _touched() { this.idle = 0; this.autoSpeed = 0; this.onInput?.(); }

  _tap(e, p) {
    const now = performance.now();
    const dbl = now - this._lastTap.t < 360 && Math.hypot(e.clientX - this._lastTap.x, e.clientY - this._lastTap.y) < 24;
    this._lastTap = { t: now, x: e.clientX, y: e.clientY };
    if (dbl) { this._lastTap.t = 0; this.onDoubleTap?.(e.clientX, e.clientY); }
    else this.onTap?.(e.clientX, e.clientY, p?.type);
  }

  _rayAt(cx, cy) {
    const r = this.dom.getBoundingClientRect();
    const nx = ((cx - r.left) / r.width) * 2 - 1, ny = -(((cy - r.top) / r.height) * 2 - 1);
    const o = this.camera.position.clone();
    const d = new THREE.Vector3(nx, ny, 0.5).unproject(this.camera).sub(o).normalize();
    return { o, d };
  }
  /** point on the car (visual hull) or on the floor under screen position, or null */
  pick(cx, cy) {
    const { o, d } = this._rayAt(cx, cy);
    const hit = this.hull.march(o, d, 40, 0.03);
    if (hit) return hit;
    if (d.y < -1e-3) { const t = -o.y / d.y; if (t > 0 && t < 40) return o.clone().addScaledVector(d, t); }
    return null;
  }

  _zoomAt(f, cx, cy, fromPinch) {
    const g = this.goal;
    const nd = clamp(g.dist * f, LIMITS.dist[0], LIMITS.dist[1]);
    const real = nd / g.dist;
    if (real < 1) {
      const { o, d } = this._rayAt(cx, cy);
      const hit = this.hull.march(o, d, 40, 0.03);
      if (hit) {
        const k = (1 - real) * 0.85;
        g.target.lerp(hit, k);
      }
    } else if (real > 1) {
      // zooming out drifts the orbit centre back to the car
      const home = HOME;
      g.target.lerp(home, clamp((real - 1) * 1.1, 0, 0.5));
    }
    g.dist = nd;
    this._clampTarget(g.target);
  }

  _pan(dx, dy) {
    const cam = this.camera;
    const h = this.dom.clientHeight || 600;
    const s = 2 * this.dist * Math.tan(THREE.MathUtils.degToRad(this.fov) / 2) / h;
    const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
    this.goal.target.addScaledVector(right, -dx * s).addScaledVector(up, dy * s);
    this._clampTarget(this.goal.target);
    this.target.copy(this.goal.target);
    this.anim = null;
  }
  _clampTarget(t) { t.clamp(LIMITS.pan.min, LIMITS.pan.max); return t; }

  /** move the orbit centre to a world point (double tap) */
  focusOn(p, dist = null, dur = 0.9) {
    const to = this._clampTarget(p.clone());
    const from = { yaw: this.yaw, pitch: this.pitch, dist: this.dist, target: this.target.clone(), fov: this.fov };
    const nd = dist ?? clamp(this.dist * 0.55, 0.9, 5);
    this.anim = { from, to: { yaw: this.yaw, pitch: this.pitch, dist: nd, target: to, fov: this.fov }, t: 0, dur };
  }

  // ------------------------------------------------------------------------------------------ per frame
  _step(dt) {
    const cam = this.camera;
    // keyboard
    const K = this.keys;
    if (K.size && this.enabled) {
      const ky = (K.has('ArrowLeft') || K.has('KeyA') ? 1 : 0) - (K.has('ArrowRight') || K.has('KeyD') ? 1 : 0);
      const kp = (K.has('ArrowUp') || K.has('KeyW') ? -1 : 0) + (K.has('ArrowDown') || K.has('KeyS') ? 1 : 0);
      const kz = (K.has('Minus') || K.has('NumpadSubtract') || K.has('PageDown') ? 1 : 0) - (K.has('Equal') || K.has('NumpadAdd') || K.has('PageUp') ? 1 : 0);
      if (ky || kp) { this.vYaw += ky * dt * 5.5; this.vPitch += kp * dt * 4; this.anim = null; this._touched(); }
      if (kz) { this.goal.dist = clamp(this.goal.dist * Math.exp(kz * dt * 1.4), LIMITS.dist[0], LIMITS.dist[1]); this.anim = null; this._touched(); }
    }
    if (this.anim) {
      const a = this.anim; a.t += dt / a.dur;
      const k = ease(clamp(a.t, 0, 1));
      this.yaw = a.from.yaw + (a.to.yaw - a.from.yaw) * k;
      this.pitch = a.from.pitch + (a.to.pitch - a.from.pitch) * k;
      this.dist = Math.exp(Math.log(a.from.dist) + (Math.log(a.to.dist) - Math.log(a.from.dist)) * k);
      this.target.lerpVectors(a.from.target, a.to.target, k);
      this.fov = a.from.fov + (a.to.fov - a.from.fov) * k;
      this.goal.dist = this.dist; this.goal.target.copy(this.target); this.goal.fov = this.fov;
      if (a.t >= 1) this.anim = null;
    } else {
      // inertia
      this.yaw += this.vYaw * dt; this.pitch += this.vPitch * dt;
      const damp = this.pointers.size ? 0 : Math.exp(-dt * 4.2);
      if (!this.pointers.size) { this.vYaw *= damp; this.vPitch *= damp; }
      if (Math.abs(this.vYaw) < 1e-4) this.vYaw = 0;
      if (Math.abs(this.vPitch) < 1e-4) this.vPitch = 0;
      // damped approach to the goals (zoom, centre, fov)
      const k = 1 - Math.exp(-dt * 9);
      this.dist += (this.goal.dist - this.dist) * k;
      this.target.lerp(this.goal.target, k);
      this.fov += (this.goal.fov - this.fov) * k;
      // idle turntable
      this.idle += dt;
      const want = this.autoOn && this.enabled && this.idle > this.autoDelay && !this.pointers.size && !this.autoBlocked ? this.autoRate : 0;
      this.autoSpeed += (want - this.autoSpeed) * (1 - Math.exp(-dt * (want ? 0.8 : 8)));
      this.yaw += this.autoSpeed * dt;
    }
    this.pitch = clamp(this.pitch, LIMITS.pitch[0], LIMITS.pitch[1]);
    this.dist = clamp(this.dist, LIMITS.dist[0], LIMITS.dist[1]);

    // narrow screens: widen the frame so the whole car fits
    const asp = this.aspect;
    const nar = Math.max(1, 1.45 / Math.max(asp, 0.2));
    let tanHalf = Math.tan(THREE.MathUtils.degToRad(this.fov) / 2) * Math.pow(nar, 0.5);
    const distK = Math.pow(nar, 0.42);
    let dist = this.dist * (this.anim && this.anim.to.dist < 3 ? 1 : distK);
    // camera position, floor + body collision (push out along the ray from the orbit centre)
    const cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
    const dir = _dir.set(Math.sin(this.yaw) * cp, sp, Math.cos(this.yaw) * cp);
    if (dir.y * dist + this.target.y < LIMITS.floorY) {
      // lower the pitch limit so the camera stays above the floor
      const sMin = (LIMITS.floorY - this.target.y) / Math.max(dist, 1e-3);
      const pMin = Math.asin(clamp(sMin, -1, 1));
      this.pitch = Math.max(this.pitch, pMin); this.vPitch = Math.max(this.vPitch, 0);
      const cp2 = Math.cos(this.pitch), sp2 = Math.sin(this.pitch);
      dir.set(Math.sin(this.yaw) * cp2, sp2, Math.cos(this.yaw) * cp2);
    }
    // the camera stays inside the studio tub (wall at r = 13.6 m, ceiling 14 m): when a narrow screen pushes it further out, stop at the wall and widen the lens instead
    {
      const distReq = dist;
      const a = dir.x * dir.x + dir.z * dir.z;
      if (a > 1e-4) {
        const b = 2 * (this.target.x * dir.x + this.target.z * dir.z), c = this.target.x * this.target.x + this.target.z * this.target.z - LIMITS.maxR * LIMITS.maxR;
        dist = Math.min(dist, (-b + Math.sqrt(Math.max(b * b - 4 * a * c, 0))) / (2 * a));
      }
      if (dir.y > 1e-3) dist = Math.min(dist, (LIMITS.maxY - this.target.y) / dir.y);
      if (dist < distReq) tanHalf *= distReq / Math.max(dist, 1e-3);
    }
    const fovEff = Math.min(2 * Math.atan(tanHalf) * 180 / Math.PI, 78);
    const eye = this.eye;
    eye.copy(this.target).addScaledVector(dir, dist);
    let guard = 0;
    while (guard++ < 60) {
      const d = this.hull.distance(eye);
      if (d >= this.margin) break;
      dist += Math.max((this.margin - d) * 0.8, 0.012);
      eye.copy(this.target).addScaledVector(dir, dist);
    }
    if (dist > this.dist * distK + 1e-3 && !this.anim) this.goal.dist = Math.max(this.goal.dist, dist / distK), this.dist = Math.max(this.dist, dist / distK);
    eye.y = Math.max(eye.y, LIMITS.floorY);
    cam.position.copy(eye);
    cam.up.set(0, 1, 0);
    cam.lookAt(this.target);
    if (Math.abs(cam.fov - fovEff) > 1e-4) { cam.fov = fovEff; cam.updateProjectionMatrix(); }
  }

  update(dt) { this._step(Math.min(dt, 0.05)); }

  setAspect(a) { this.aspect = a; this.camera.aspect = a; this.camera.updateProjectionMatrix(); }

  dispose() { for (const [el, t, fn, o] of this.listeners) el.removeEventListener(t, fn, o); this.listeners.length = 0; }
}
const HOME = new THREE.Vector3(0, 0.55, -0.2);
const _dir = new THREE.Vector3();
