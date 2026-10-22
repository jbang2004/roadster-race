// The HDR frame pipeline. Owner: R.   (assembled by index.js → createRenderer)
//
//   light pool → road reflection (half res) → car probe slice
//   → WORLD pass  (camera layers DEFAULT + MAIN_ONLY)            ┐ same HalfFloat target + D32F depth,
//   → alpha reset (car mask := 0)                                │ sub-pixel jittered when TAA is on
//   → CAR pass    (camera layers CARS + LATE, light pool on)     ┘ depth-tested against the world, alpha := 1 on cars
//   → TAA (car-mask aware) → motion blur (cars excluded) → bloom + streaks → composite (tone map, grade, CA, vignette)
//   → final (FXAA or unsharp, grain, dither) → canvas
//
// LATE (layer 4) is R's extension to the layer set: transparent effects that must appear in front of cars (spray, smoke,
// sparks, light cones) are drawn in the car pass, after the cars, depth-tested against world and cars.
import * as THREE from 'three';
import { LAYER } from '../core/layers.js';
import { lights as lightRegistry } from '../core/lights.js';
import { G } from '../core/globals.js';
import { RF } from '../core/reflect.js';
import { fsPass, makeRT, FS_VERT } from './common.js';
import { TAAPass, MAX_CARS } from './taa.js';
import { BloomPass } from './bloom.js';
import { MotionBlurPass } from './motionBlur.js';
import { createCompositeMaterial, createFinalMaterial } from './composite.js';
import { LightPool } from './lightPool.js';
import { PlanarReflection } from './reflection.js';
import { CarProbe, buildEnvironment } from './environment.js';
import { GPUProfiler } from './profiler.js';
import { QUALITY } from './quality.js';

export const LAYER_LATE = 4;
export const MASK_WORLD = (1 << LAYER.DEFAULT) | (1 << LAYER.MAIN_ONLY);
export const MASK_CARS = (1 << LAYER.CARS) | (1 << LAYER_LATE);
const clamp = THREE.MathUtils.clamp;

const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _q = new THREE.Quaternion(), _e = new THREE.Euler(), _qs = new THREE.Quaternion();
const _m = new THREE.Matrix4(), _col = new THREE.Color(), _vs = new THREE.Vector2();

/** smooth 1-D noise from incommensurate sines (no allocation) */
const wob = (t, s) => Math.sin(t * 13.1 + s) * 0.5 + Math.sin(t * 27.7 + s * 2.3) * 0.3 + Math.sin(t * 51.3 + s * 4.1) * 0.2;

class Pulse {
  constructor() { this.peak = 0; this.age = 0; this.dur = 1; }
  hit(v, dur) { if (v >= this.value) { this.peak = v; this.age = 0; this.dur = Math.max(1e-3, dur); } }
  get value() { const k = Math.max(0, 1 - this.age / this.dur); return this.peak * k * k; }
  tick(dt) { this.age += dt; }
}

function makeParams(app, Q) {
  return {
    exposure: 1.0,
    tonemap: 'aces',                                  // 'aces' | 'agx'
    bloom: { strength: 0.8, threshold: 1.0, knee: 0.5, radius: 0.5, levels: Q.bloomLevels },
    streak: { strength: Q.streaks ? 0.22 : 0, threshold: 7, length: 0.6 },
    motionBlur: Q.mbTaps ? 0.6 : 0, mbMaxLen: 0.04,   // shutter fraction; max streak length in screen heights
    vignette: 0.38, grain: 0.028, chroma: 0.003, sharpen: 0.25,
    grade: { teal: 0.55, magenta: 0.35, contrast: 0.22, saturation: 1.06 },
    aa: Q.aa,                                         // 'taa' | 'fxaa'
    taaBlend: 0.1, taaGamma: 1.0, taaCarBlend: 0.22, taaCarGamma: 0.75, jitter: 1,
    reflection: { enabled: true },
    probe: { enabled: true },
    adaptive: !app.harness, targetFps: 58,
    debug: 'none',                                    // 'none' | 'bloom' | 'mask' | 'streak'
  };
}

function applyUrlParams(app, p) {
  const q = app.q;
  if (q.get('aa')) p.aa = q.get('aa');
  if (q.get('tm')) p.tonemap = q.get('tm');
  if (q.has('nomb')) p.motionBlur = 0;
  if (q.get('exp')) p.exposure = +q.get('exp');
  return p;
}

const DEBUG = { none: 0, bloom: 1, mask: 2, streak: 3 };

export class Pipeline {
  constructor(app, track) {
    this.app = app; this.r = app.renderer; this.scene = app.scene; this.camera = app.camera; this.track = track;
    const qn = ['high', 'medium', 'low'].includes(app.quality) ? app.quality : 'high';
    this.Q = { ...QUALITY[qn] };
    if (app.q.get('psize')) this.Q.probeSize = +app.q.get('psize');
    if (app.q.get('pfaces')) this.Q.probeFaces = +app.q.get('pfaces');
    if (app.q.get('refls')) this.Q.reflSamples = +app.q.get('refls');
    if (app.q.get('rscale')) this.Q.reflScale = +app.q.get('rscale');
    if (app.q.get('scale')) this.Q.sceneScale = +app.q.get('scale');
    if (app.q.get('pool')) { const [pn, sn] = app.q.get('pool').split(',').map(Number); this.Q.points = pn; this.Q.spots = sn ?? 0; }   // experiments
    this.qualityName = qn;
    this.params = applyUrlParams(app, makeParams(app, this.Q));
    this.harness = app.harness;

    this.W = 1; this.H = 1; this.SW = 1; this.SH = 1;
    this.scale = this.Q.sceneScale;
    this.rtScene = new THREE.WebGLRenderTarget(1, 1, {
      type: THREE.HalfFloatType, format: THREE.RGBAFormat, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
      depthBuffer: true, stencilBuffer: false, generateMipmaps: false,
      depthTexture: new THREE.DepthTexture(1, 1, THREE.FloatType),
    });
    this.rtScene.texture.name = 'hdrScene';
    this.rtLDR = makeRT(1, 1, { name: 'ldr', type: THREE.UnsignedByteType });
    this.taa = new TAAPass();
    this.mb = new MotionBlurPass();
    this.mb.setTaps(this.Q.mbTaps || 8);
    this.bloom = new BloomPass();
    this._comp = [null, null];            // composite variants by tone map: [agx, aces], built on demand
    this.finalFxaa = createFinalMaterial(true);
    this.finalSharp = createFinalMaterial(false);
    this.alphaReset = new THREE.ShaderMaterial({
      name: 'alphaReset', vertexShader: FS_VERT, fragmentShader: 'void main(){ gl_FragColor = vec4(0.0); }',
      depthTest: false, depthWrite: false, toneMapped: false,
      blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendEquationAlpha: THREE.AddEquation,
      blendSrc: THREE.ZeroFactor, blendDst: THREE.OneFactor, blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.ZeroFactor,
    });

    this.pool = new LightPool(this.scene, { points: this.Q.points, spots: this.Q.spots });
    this.refl = new PlanarReflection(this.r, { scale: this.Q.reflScale, samples: this.Q.reflSamples, far: this.Q.reflFar });
    this.refl.maxPx = this.Q.maxReflPx;
    this.probe = new CarProbe(this.r, { size: this.Q.probeSize, far: this.Q.probeFar ?? 700 });
    this.profiler = new GPUProfiler(this.r);
    if (app.q.has('perf')) this.perfMode = app.q.get('perf') === 'sync' ? 'sync' : 'query';

    // frame record
    this.F = {
      index: 0, viewProj: new THREE.Matrix4(), prevViewProj: new THREE.Matrix4(), camPos: new THREE.Vector3(), prevPos: new THREE.Vector3(),
      fwd: new THREE.Vector3(), prevFwd: new THREE.Vector3(0, 0, -1), near: 0.1, far: 6000, historyOk: false,
    };

    // focus / plane / cars
    this.focus = null;
    this._hint = -1; this._pr = {}; this._fr0 = {}; this._fr1 = {}; this._fr2 = {};
    this.plane = { p: new THREE.Vector3(0, 0, 0), n: new THREE.Vector3(0, 1, 0), s: 0, valid: false };
    this.carObjs = [];                 // explicit (setCars)
    this._autoCars = []; this._carState = new Map(); this._carData = [];
    this._interest = Array.from({ length: 1 + MAX_CARS }, () => ({ pos: new THREE.Vector3(), w: 1 }));
    this._nInterest = 0;
    this._focusPos = new THREE.Vector3();

    // fx
    this._fx = { flash: new Pulse(), flashCol: new THREE.Color(1, 1, 1), shakeE: 0, speed: 0, speedT: 0, t: 0 };
    this.fx = {
      shake: (a = 1) => { this._fx.shakeE = Math.min(2.5, Math.max(this._fx.shakeE, a)); },
      speed: (k) => { this._fx.speedT = clamp(k, 0, 1); },
      flash: (color = 0xffffff, seconds = 0.25) => {
        if (Array.isArray(color)) _col.setRGB(color[0], color[1], color[2]); else _col.set(color);
        this._fx.flashCol.copy(_col); this._fx.flash.hit(1, seconds);
      },
    };

    // adaptive resolution
    this._ft = 1 / 60; this._adaptT = 0; this._lastNow = performance.now();
    this._cpuMs = 0; this._calls = {}; this._tris = 0;
    this._frameStat = { world: 0, cars: 0, refl: 0, probe: 0, post: 0 };
    this._wrapCompile();
  }

  async init() {
    this.env = await buildEnvironment(this.app);
    this.probe.init();
    // prime the probe once (all faces) so cars have a sensible env map before the first frame
    this.scene.updateMatrixWorld(true);
    const fp = this._computeFocus(this._focusPos);
    this.probe.update(this.scene, _v.copy(fp).setY(fp.y + 1.3), 6);
  }

  // ------------------------------------------------------------------ public
  setFocus(obj) { this.focus = obj; this._hint = -1; this.plane.valid = false; }
  setCars(list) { this.carObjs = list ? list.filter(Boolean) : []; }
  setQuality() { /* presets are fixed at creation (light pool + reflection MSAA); live tweaks go through params */ }

  setSize() {
    this.r.getDrawingBufferSize(_vs);
    const W = Math.max(2, _vs.x | 0), H = Math.max(2, _vs.y | 0);
    this._W = W; this._H = H;
    this._applySizes(true);
  }

  _applySizes(all) {
    const W = this._W, H = this._H;
    // pixel budget: on big canvases the scene renders below native resolution and TAA upsamples it
    const cap = Math.min(1, Math.sqrt((this.Q.maxScenePx ?? Infinity) / (W * H)));
    const s = this.scale * cap;
    this.effScale = s;
    const SW = Math.max(2, Math.round(W * s)), SH = Math.max(2, Math.round(H * s));
    if (all || W !== this.W || H !== this.H) {
      this.rtLDR.setSize(W, H);
      this.mb.setSize(W, H);
      this.bloom.setSize(Math.max(2, Math.ceil(W / 2)), Math.max(2, Math.ceil(H / 2)));
      this.refl.setSize(W, H);
      this.finalFxaa.uniforms.uTexel.value.set(1 / W, 1 / H);
      this.finalSharp.uniforms.uTexel.value.set(1 / W, 1 / H);
      for (const m of this._comp) if (m) m.uniforms.uAspect.value = W / H;
    }
    if (all || SW !== this.SW || SH !== this.SH || W !== this.W || H !== this.H) {
      this.rtScene.setSize(SW, SH);
      this.taa.setSize(W, H, SW, SH);
    }
    this.W = W; this.H = H; this.SW = SW; this.SH = SH;
    this.app.renderScale = this.scale;            // informational: the scene render scale (the canvas stays full size)
  }

  stats() {
    const g = this.profiler.snapshot();
    const post = (g.taa ?? 0) + (g.mb ?? 0) + (g.bloom ?? 0) + (g.comp ?? 0) + (g.final ?? 0);
    return {
      aa: this._useTaa ? 'taa' : 'fxaa', scene: [this.SW, this.SH], scale: +this.scale.toFixed(2), refl: [this.refl.w, this.refl.h],
      lights: this.pool.active, cpuMs: +this._cpuMs.toFixed(2), passCalls: { ...this._frameStat }, gpu: g, gpuPostMs: +post.toFixed(2),
      cars: this._carData.length,
    };
  }

  // ------------------------------------------------------------------ helpers
  _computeFocus(out) {
    if (this.focus) return this.focus.getWorldPosition(out);
    const c = this.camera;
    return out.set(0, 0, -12).applyMatrix4(c.matrixWorld);
  }

  _updatePlane(dt, fp) {
    const T = this.track, pl = this.plane;
    if (!T) { pl.p.set(fp.x, 0, fp.z); pl.n.set(0, 1, 0); pl.valid = true; return; }
    let pr = T.project(fp, this._hint, this._pr);
    if (this._hint < 0 || Math.abs(pr.d) > 9 || Math.abs(pr.u) > pr.hw + 60) pr = T.project(fp, -1, this._pr);
    this._hint = pr.i;
    const s = pr.s;
    const a = T.frameAt(s + 4, this._fr0), b = T.frameAt(s + 16, this._fr1), c = T.frameAt(s + 36, this._fr2);
    _v.copy(a.u).multiplyScalar(0.25).addScaledVector(b.u, 0.5).addScaledVector(c.u, 0.25).normalize();
    const tp = b.pos;
    if (!pl.valid || pl.p.distanceToSquared(tp) > 36 * 36) { pl.p.copy(tp); pl.n.copy(_v); pl.valid = true; }
    else {
      const k = 1 - Math.exp(-dt * 40);
      pl.p.lerp(tp, k); pl.n.lerp(_v, k).normalize();
    }
    pl.s = s;
  }

  _detectCars() {
    const out = this._autoCars; out.length = 0;
    const mask = 1 << LAYER.CARS;
    const test = (o, depth) => {
      if (o.isLight || o.isCamera) return;
      if (o.layers.mask === mask && !o.isMesh && o.children.length) {
        const box = new THREE.Box3().setFromObject(o);
        if (!box.isEmpty() && box.getSize(_v).length() < 14) { out.push(o); return; }
      }
      if (depth < 3) for (const c of o.children) test(c, depth + 1);
    };
    for (const c of this.scene.children) test(c, 0);
  }

  _updateCars(camPos) {
    let list = this.carObjs.length ? this.carObjs : this._autoCars;
    const f = this.focus;
    if (f) {
      let related = false;
      for (const o of list) { if (o === f) { related = true; break; } let a = f; while ((a = a.parent)) if (a === o) { related = true; break; } if (related) break; a = o; while ((a = a.parent)) if (a === f) { related = true; break; } if (related) break; }
      if (!related) list = list.concat([f]);
    }
    const data = this._carData; data.length = 0;
    const cand = this._cand ??= []; cand.length = 0;
    for (const o of list) {
      if (!o.visible || !o.parent) continue;
      let st = this._carState.get(o);
      if (!st) { st = { prev: o.matrixWorld.clone(), inv: new THREE.Matrix4(), center: new THREE.Vector3(), radius: 3.1, obj: o, d2: 0 }; this._carState.set(o, st); }
      st.center.set(0, 0.7, 0).applyMatrix4(o.matrixWorld);
      st.d2 = st.center.distanceToSquared(camPos);
      if (st.d2 < 400 * 400) cand.push(st);
    }
    cand.sort((x, y) => x.d2 - y.d2);
    for (let i = 0; i < Math.min(MAX_CARS, cand.length); i++) {
      const st = cand[i];
      st.inv.copy(st.obj.matrixWorld).invert();
      data.push(st);
    }
  }

  _endCars() {
    for (const [o, st] of this._carState) { if (!o.parent) { this._carState.delete(o); continue; } st.prev.copy(o.matrixWorld); }
  }

  _applyShake(dt) {
    const fx = this._fx, cam = this.camera;
    fx.shakeE *= Math.exp(-dt * 4.5);
    if (fx.shakeE < 0.004) { fx.shakeE = 0; this._shaken = false; return; }
    const E = fx.shakeE, t = fx.t;
    this._savedPos = (this._savedPos ?? new THREE.Vector3()).copy(cam.position);
    this._savedQuat = (this._savedQuat ?? new THREE.Quaternion()).copy(cam.quaternion);
    _e.set(wob(t, 1.0) * 0.012 * E, wob(t, 7.7) * 0.012 * E, wob(t, 3.3) * 0.02 * E);
    _qs.setFromEuler(_e);
    cam.quaternion.multiply(_qs);
    _v2.set(wob(t, 11.1), wob(t, 5.5), wob(t, 2.2) * 0.5).multiplyScalar(0.05 * E).applyQuaternion(cam.quaternion);
    cam.position.add(_v2);
    this._shaken = true;
  }

  _endShake() {
    if (!this._shaken) return;
    this.camera.position.copy(this._savedPos); this.camera.quaternion.copy(this._savedQuat);
    this._shaken = false;
  }

  // ------------------------------------------------------------------ the frame
  render(dt) {
    const t0 = performance.now();
    const real = Math.min(Math.max((t0 - this._lastNow) / 1000, 0), 0.1);
    this._lastNow = t0;
    const prof = this.profiler;
    prof.mode = this.perfMode ?? 'off';
    this._begin(real);
    prof.begin('refl'); this._stageRefl();
    prof.begin('probe'); this._stageProbe();
    prof.begin('scene'); this._stageScene();
    this._post(real, this._useTaa);
    prof.end(); prof.frame();
    if (prof.mode !== 'off') this._gpu = prof.snapshot();
    this._end();
    this._cpuMs += (performance.now() - t0 - this._cpuMs) * 0.08;
  }

  /** fx, adaptive scale, shake, focus, plane, light pool, matrices, camera record */
  _begin(real) {
    const r = this.r, scene = this.scene, cam = this.camera, P = this.params, F = this.F, fx = this._fx;
    if (this._W === undefined) this.setSize();
    r.info.autoReset = false; r.info.reset();
    fx.t += real;
    fx.flash.tick(real);
    fx.speed += (fx.speedT - fx.speed) * Math.min(1, real * 5);
    if (P.adaptive) this._adapt(real);
    this._useTaa = P.aa === 'taa' || (this.effScale ?? this.scale) < 0.999;

    this._applyShake(real);
    scene.matrixWorldAutoUpdate = true;
    cam.updateMatrixWorld(true);
    const fp = this._computeFocus(this._focusPos);
    this._updatePlane(real, fp);
    if (F.index % 90 === 0 && !this.carObjs.length) this._detectCars();
    // light pool needs positions before the scene's matrices are refreshed
    let ni = 0;
    this._interest[ni].pos.copy(fp); this._interest[ni].w = 1; ni++;
    for (const st of this._carData) {
      if (ni >= this._interest.length) break;
      const d2 = st.center.distanceToSquared(fp);
      if (d2 < 2.0 || d2 > 160 * 160) continue;
      this._interest[ni].pos.copy(st.center); this._interest[ni].w = 0.55; ni++;
    }
    this._nInterest = ni;
    this.pool.update(real, this._interest, ni);
    scene.updateMatrixWorld(true);
    scene.matrixWorldAutoUpdate = false;
    this._updateCars(cam.getWorldPosition(_v));

    F.near = cam.near; F.far = cam.far;
    F.viewProj.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    F.camPos.setFromMatrixPosition(cam.matrixWorld);
    F.fwd.set(0, 0, -1).transformDirection(cam.matrixWorld);
    F.historyOk = F.index > 0 && F.camPos.distanceToSquared(F.prevPos) < 60 * 60 && F.fwd.dot(F.prevFwd) > 0.75;
    if (F.index === 0) F.prevViewProj.copy(F.viewProj);
    this._calls0 = r.info.render.calls;
  }

  _end() {
    const F = this.F;
    this.scene.matrixWorldAutoUpdate = true;
    this._endShake();
    this._endCars();
    F.prevViewProj.copy(F.viewProj);
    F.prevPos.copy(F.camPos); F.prevFwd.copy(F.fwd);
    F.index++;
  }

  _stageRefl() {
    const r = this.r, P = this.params, F = this.F, scene = this.scene, cam = this.camera;
    const c0 = r.info.render.calls;
    const doRefl = P.reflection.enabled && (F.index % this.Q.reflEvery === 0 || !this.refl.valid);
    this.refl.enabled = P.reflection.enabled;
    if (doRefl && this.plane.valid) {
      // far cars are not worth their draw calls in the mirror image
      const hide = this._hide ??= []; hide.length = 0;
      for (const st of this._carData) if (st.d2 > 75 * 75 && st.obj.visible) { st.obj.visible = false; hide.push(st.obj); }
      this.pool.setVisible(false);
      this.refl.render(scene, cam, this.plane);
      this.pool.setVisible(true);
      for (const o of hide) o.visible = true;
    } else if (!P.reflection.enabled) RF.uReflectOn.value = 0;
    this._frameStat.refl = r.info.render.calls - c0;
  }

  _stageProbe() {
    const r = this.r, P = this.params, F = this.F;
    const c0 = r.info.render.calls;
    this.probe.enabled = P.probe.enabled;
    if (P.probe.enabled && this.probe.texture && F.index % this.Q.probeEvery === 0) {
      _v.copy(this._focusPos); _v.y += 1.3;
      this.probe.update(this.scene, _v, this.Q.probeFaces);
    }
    this._frameStat.probe = r.info.render.calls - c0;
  }

  /** world pass + car mask reset + car pass into rtScene */
  _stageScene() {
    const r = this.r, scene = this.scene, cam = this.camera, P = this.params;
    const savedMask = cam.layers.mask, bg = scene.background, oldAC = r.autoClear;
    const useTaa = this._useTaa;
    const c0 = r.info.render.calls;
    if (useTaa) this.taa.jitter(cam, this.SW, this.SH, P.jitter);
    r.setRenderTarget(this.rtScene);
    r.setClearColor(0x000000, 0);
    r.autoClear = true;
    cam.layers.mask = MASK_WORLD;
    r.render(scene, cam);
    const c1 = r.info.render.calls;
    fsPass(r, this.alphaReset, this.rtScene);
    scene.background = null;
    r.setRenderTarget(this.rtScene);
    r.autoClear = false;
    cam.layers.mask = MASK_CARS;
    r.render(scene, cam);
    scene.background = bg;
    cam.layers.mask = savedMask;
    r.autoClear = oldAC;
    if (useTaa) this.taa.restore();
    this._frameStat.world = c1 - c0; this._frameStat.cars = r.info.render.calls - c1;
  }


  /**
   * Wall-clock GPU cost per section in ms, measured the way that is trustworthy on ANGLE/Metal: run the section n times
   * back to back, then force completion by reading one pixel of the last target it wrote (best of 3 batches).
   * Blocks the main thread (debug only).  → { frame, refl, probe, scene, post, taa, mb, bloom, comp, final, ... }
   */
  benchmark(n = 20) {
    const r = this.r, gl = r.getContext(), P = this.params, F = this.F;
    const u8 = new Uint8Array(4), u16 = new Uint16Array(4);
    const sync = (rt, face = 0) => {
      if (!rt) { r.setRenderTarget(null); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, u8); return; }
      try { r.readRenderTargetPixels(rt, 0, 0, 1, 1, rt.texture.type === THREE.UnsignedByteType ? u8 : u16, face); }
      catch (e) { gl.finish(); }
    };
    const time = (fn, rt, face) => {
      fn(); sync(rt, face);
      let best = Infinity;
      for (let rep = 0; rep < 3; rep++) {
        const t0 = performance.now();
        for (let i = 0; i < n; i++) fn();
        sync(rt, face);
        best = Math.min(best, (performance.now() - t0) / n);
      }
      return +best.toFixed(3);
    };
    const out = {};
    const keepIndex = F.index, saved = this.perfMode; this.perfMode = undefined;
    this._begin(1 / 60);
    F.historyOk = true;
    const useTaa = this._useTaa, real = 1 / 60;
    F.index = 0;                                         // probe slices run on index 0
    out.empty = time(() => {}, null);
    // whole frame with the camera moving 1 m per call (≈ 60 m/s) so motion blur and TAA do real work
    const cam = this.camera, c0 = cam.position.clone(), fw = new THREE.Vector3(0, 0, -1).applyQuaternion(cam.quaternion);
    let flip = 0; const savedSpeed = this._fx.speedT, savedMb = P.motionBlur;
    this._fx.speed = 1; this._fx.speedT = 1;
    const mover = () => { cam.position.copy(c0).addScaledVector(fw, (flip++ % 2) * 1.0); this.render(1 / 60); };
    out.frame = time(mover, null);
    P.motionBlur = 0; out.frameNoMB = time(mover, null); P.motionBlur = savedMb;
    cam.position.copy(c0); this._fx.speedT = savedSpeed;
    this._begin(1 / 60); F.index = 1; F.historyOk = true;
    out.refl = time(() => this._stageRefl(), this.refl.rt);
    out.probe = time(() => { F.index = 0; this._stageProbe(); F.index = 1; }, this.probe.cube, 0);
    out.scene = time(() => this._stageScene(), this.rtScene);
    const tex0 = this.rtScene.texture;
    out.taa = useTaa ? time(() => this.taa.render(r, tex0, this.rtScene.depthTexture, F, P, this._carData), this.taa.rt[this.taa.cur]) : 0;
    const tt = useTaa ? this.taa.texture : tex0;
    const pvp = F.prevViewProj.clone();
    _m.makeTranslation(0.3, 0, -1.2).multiply(this.camera.matrixWorldInverse); F.prevViewProj.multiplyMatrices(this.camera.projectionMatrix, _m);
    out.mb = this.Q.mbTaps ? time(() => this.mb.render(r, tt, this.rtScene.depthTexture, F, 0.5, P.mbMaxLen), this.mb.rt) : 0;
    F.prevViewProj.copy(pvp);
    out.bloom = time(() => this.bloom.render(r, tt, this.W, this.H, P), this.bloom.ups[0]);
    const cmat = this._comp[P.tonemap === 'agx' ? 0 : 1] ?? (this._comp[1] = createCompositeMaterial(1)); const cu = cmat.uniforms; cu.tScene.value = tt; cu.tBloom.value = this.bloom.texture; cu.tStreak.value = this.bloom.streakTexture;
    out.comp = time(() => fsPass(r, cmat, this.rtLDR), this.rtLDR);
    const fm = useTaa ? this.finalSharp : this.finalFxaa; fm.uniforms.tLDR.value = this.rtLDR.texture;
    out.final = time(() => fsPass(r, fm, null), null);
    out.post = +((out.taa ?? 0) + out.mb + out.bloom + out.comp + out.final).toFixed(3);
    out.W = this.W; out.H = this.H; out.scene_px = [this.SW, this.SH];
    F.index = keepIndex;
    this._end(); F.index = keepIndex;
    this.perfMode = saved;
    return out;
  }

  _post(real, useTaa) {
    const r = this.r, P = this.params, F = this.F, prof = this.profiler, fx = this._fx;
    let tex = this.rtScene.texture;
    prof.begin('taa');
    if (useTaa) {
      this.taa.render(r, tex, this.rtScene.depthTexture, F, P, this._carData);
      tex = this.taa.texture;
    }
    // motion blur (strength follows speed; skipped when it cannot be visible)
    const mbk = P.motionBlur * (0.3 + 0.7 * fx.speed);
    prof.begin('mb');
    if (mbk > 0.02 && this.Q.mbTaps > 0 && F.index > 0 && F.historyOk) {
      this.mb.setTaps(this.Q.mbTaps);
      this.mb.render(r, tex, this.rtScene.depthTexture, F, mbk * 0.5 * (1 / 60) / Math.max(real, 1 / 240), P.mbMaxLen);
      tex = this.mb.texture;
    }
    prof.begin('bloom');
    this.bloom.render(r, tex, this.W, this.H, P);

    prof.begin('comp');
    const ck = P.tonemap === 'agx' ? 0 : 1;
    const cm = this._comp[ck] ??= createCompositeMaterial(ck);
    cm.uniforms.uAspect.value = this.W / this.H;
    const u = cm.uniforms;
    u.tScene.value = tex; u.tBloom.value = this.bloom.texture; u.tStreak.value = this.bloom.streakTexture;
    u.uBloom.value = P.bloom.strength * (this.bloom.norm ?? 0.2);
    u.uStreak.value = P.streak.strength;
    u.uExposure.value = P.exposure;
    u.uCA.value = P.chroma * (0.6 + 1.6 * fx.speed);
    u.uVig.value = P.vignette * (1 + 0.35 * fx.speed);
    u.uTeal.value = P.grade.teal; u.uMagenta.value = P.grade.magenta; u.uContrast.value = P.grade.contrast; u.uSat.value = P.grade.saturation;
    const fl = fx.flash.value;
    u.uFlash.value.set(fx.flashCol.r, fx.flashCol.g, fx.flashCol.b, fl * 0.8);
    u.uDebug.value = DEBUG[P.debug] ?? 0;
    fsPass(r, cm, this.rtLDR);

    prof.begin('final');
    const fm = useTaa ? this.finalSharp : this.finalFxaa;
    const fu = fm.uniforms;
    fu.tLDR.value = this.rtLDR.texture;
    fu.uSharpen.value = useTaa ? P.sharpen : P.sharpen * 0.8;
    fu.uGrain.value = P.grain; fu.uFrame.value = F.index;
    fsPass(r, fm, null);
    this._frameStat.post = r.info.render.calls - this._calls0 - this._frameStat.refl - this._frameStat.probe - this._frameStat.world - this._frameStat.cars;
  }

  /** Adaptive resolution: keeps the frame rate by moving the scene render scale (TAA reconstructs the full-res image). */
  _adapt(real) {
    this._ft += (real - this._ft) * 0.05;
    this._adaptT += real;
    if (this._adaptT < 0.6) return;
    this._adaptT = 0;
    const target = 1 / this.params.targetFps, min = this.Q.minScale, max = this.Q.sceneScale;
    let s = this.scale;
    if (this._ft > target * 1.12) s -= 0.06;
    else if (this._ft < target * 0.88) s += 0.03;
    s = clamp(s, min, max);
    if (Math.abs(s - this.scale) > 1e-3) { this.scale = s; this._applySizes(false); }
  }

  /** app.ready() compiles with no target bound, which would build the canvas variants; bind the HDR target instead. */
  _wrapCompile() {
    const r = this.r, self = this;
    if (r.__nlCompileWrapped) return;
    r.__nlCompileWrapped = true;
    const orig = r.compileAsync.bind(r);
    r.compileAsync = async (scene, camera, target) => {
      const prev = r.getRenderTarget(), mask = camera.layers.mask;
      if (self._W === undefined) self.setSize();
      try {
        r.setRenderTarget(self.rtScene);
        camera.layers.mask = MASK_WORLD;
        return await orig(scene, camera, target);
      } finally { r.setRenderTarget(prev); camera.layers.mask = mask; }
    };
  }

  dispose() {
    for (const o of [this.rtScene, this.rtLDR, this.taa, this.mb, this.bloom, this.pool, this.refl, this.probe]) o.dispose?.();
    for (const m of [...this._comp, this.finalFxaa, this.finalSharp, this.alphaReset]) m?.dispose();
  }
}
