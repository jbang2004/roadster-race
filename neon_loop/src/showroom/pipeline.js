// Showroom frame pipeline (borrows R's post passes read-only: bloom, composite = AgX/ACES + grade, final = FXAA/unsharp + grain).
//
//   moving camera / animation:  1 frame per frame, 4x MSAA HDR target, no jitter  -> bloom -> tone map -> FXAA          (60 fps)
//   camera at rest:             progressive accumulation: each frame renders one more sub-pixel-jittered sample (Halton 2,3), plus a
//                               jittered position on the lens when depth of field is on (photo mode), and the running mean is kept in a
//                               float target (HDR, linear). After `samples` frames the picture is a clean 4 x N-times supersampled
//                               render and the GPU goes idle until something changes.
//   planar reflection of the car for the glossy floor: its own (mirrored-camera) render, mipmapped, rendered with the same jitter.
import * as THREE from 'three';
import { postMaterial, fsPass, makeRT, halton } from '../render/common.js';
import { BloomPass } from '../render/bloom.js';
import { createCompositeMaterial, createFinalMaterial } from '../render/composite.js';

const ACC_FRAG = /* glsl */`
uniform sampler2D tPrev, tCur; uniform float uW;
varying vec2 vUv;
void main() {
  vec3 c = min(texture(tCur, vUv).rgb, vec3(1500.0));
  vec3 p = texture(tPrev, vUv).rgb;
  gl_FragColor = vec4(uW >= 1.0 ? c : mix(p, c, uW), 1.0);
}`;

const _v = new THREE.Vector3(), _m = new THREE.Matrix4();

export class ShowroomPipeline {
  constructor(app, { scene, camera, cyclo, params = {} }) {
    this.app = app; this.r = app.renderer; this.scene = scene; this.camera = camera; this.cyclo = cyclo;
    const r = this.r;
    this.params = {
      exposure: 1.0, tonemap: 'agx', contrast: 0.16, saturation: 1.02, vignette: 0.3, grain: 0.012, sharpen: 0.2,
      bloom: { strength: 1.0, threshold: 9, knee: 4, radius: 0.55, levels: 6 }, streak: { strength: 0, threshold: 7, length: 0.6 },
      samples: 96, reflScale: 0.75, jitter: 1.0,
      dof: { on: false, aperture: 0.0, focus: 6.0 },
      ...params,
    };
    this.hdrType = (r.extensions.has('EXT_color_buffer_float') && r.extensions.has('OES_texture_float_linear')) ? THREE.FloatType : THREE.HalfFloatType;
    this.W = 2; this.H = 2;
    this.rtScene = new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, samples: 4, depthBuffer: true, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, generateMipmaps: false });
    this.rtScene.texture.name = 'srScene';
    this.acc = [0, 1].map(i => { const t = makeRT(2, 2, { type: this.hdrType, name: 'srAcc' + i }); return t; });
    this.accIdx = 0;
    this.rtRefl = new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, samples: 4, depthBuffer: true, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter });
    this.rtRefl.texture.name = 'srRefl';
    this.rtLDR = makeRT(2, 2, { name: 'srLDR', type: THREE.UnsignedByteType });
    this.bloom = new BloomPass();
    this.accMat = postMaterial({ name: 'srAcc', fragmentShader: ACC_FRAG, uniforms: { tPrev: { value: null }, tCur: { value: null }, uW: { value: 1 } } });
    this.comp = { agx: createCompositeMaterial(0), aces: createCompositeMaterial(1) };
    this.finalFxaa = createFinalMaterial(true); this.finalSharp = createFinalMaterial(false);
    this.vcam = new THREE.PerspectiveCamera();
    this.n = 0;                                  // samples accumulated
    this.dirty = true;
    this.frame = 0;
    this._prevCam = new THREE.Matrix4(); this._prevFov = 0; this._prevAspect = 0; this._moving = true;
    this.sig = '';
    this.fade = 0;                               // 0..1 blackout (preset switches)
    this.lastFrameRendered = true;
    this._calls = 0; this._tris = 0;
    this.visibleUpdate = null;
    // quality governor: level 0 = full, 1 = lighter while moving, 2 = lightest. While the camera moves the scene is rendered at `scaleMoving` of the resolution (the
    // final pass upsamples it) and, at the lightest level, without the planar reflection and with 2x MSAA; the moment the camera rests the full resolution comes back and
    // the progressive accumulation converges to the same clean picture.
    this.LEVELS = [
      { scale: 1, refl: 0.75, msaa: 4, reflMoving: true },
      { scale: 0.75, refl: 0.55, msaa: 4, reflMoving: true },
      { scale: 0.58, refl: 0.4, msaa: 2, reflMoving: false },
    ];
    this.level = 0; this.locked = false; this.scaleMoving = 1; this._scale = 1; this._css = [2, 2, 1]; this._ema = 1 / 60; this._slow = 0; this._still = 0;
  }

  setLevel(l) {
    l = Math.max(0, Math.min(2, l | 0)); const L = this.LEVELS[l];
    this.level = l; this.scaleMoving = L.scale; this.params.reflScale = L.refl;
    if (this.rtScene.samples !== L.msaa) { this.rtScene.samples = L.msaa; this.rtScene.dispose(); }
    this._resize(Math.round(this._css[0] * this._css[2] * this._scale), Math.round(this._css[1] * this._css[2] * this._scale));
    this.dirty = true;
  }
  // (only called from render(), which draws right after: _resize() must not leave `dirty` set, or the next frame counts as 'moved' and flips the scale back, forever)
  _setScale(s) { this._scale = s; this._resize(Math.round(this._css[0] * this._css[2] * s), Math.round(this._css[1] * this._css[2] * s)); this.dirty = false; }

  markDirty() { this.dirty = true; }
  get converged() { return this.n >= this.params.samples; }

  setSize(w, h, pr) {
    this._css = [w, h, pr];
    this._resize(Math.round(w * pr * this._scale), Math.round(h * pr * this._scale));
  }

  _resize(w, h) {
    const W = Math.max(2, w), H = Math.max(2, h);
    this.W = W; this.H = H;
    this.rtScene.setSize(W, H);
    for (const a of this.acc) a.setSize(W, H);
    const rw = Math.max(2, Math.round(W * this.params.reflScale)), rh = Math.max(2, Math.round(H * this.params.reflScale));
    this.rtRefl.setSize(rw, rh);
    this.rtLDR.setSize(W, H);
    this.bloom.setSize(Math.max(2, Math.ceil(W / 2)), Math.max(2, Math.ceil(H / 2)));
    for (const m of Object.values(this.comp)) m.uniforms.uAspect.value = W / H;
    for (const m of [this.finalFxaa, this.finalSharp]) m.uniforms.uTexel.value.set(1 / W, 1 / H);
    this.dirty = true;
  }

  stats() {
    return { level: this.level, scale: +this._scale.toFixed(2), acc: this.n, samples: this.params.samples, converged: this.converged, scene: [this.W, this.H], hdr: this.hdrType === THREE.FloatType ? 'f32' : 'f16', rendered: this.lastFrameRendered };
  }

  // ------------------------------------------------------------------------------------------------ jittered camera
  _applyJitter(cam, jx, jy, W, H) {
    const e = cam.projectionMatrix.elements;
    e[8] += 2 * jx / W; e[9] += 2 * jy / H;
    cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
  }

  /** the camera of this sample: sub-pixel offset + a point on the lens. returns a restore() */
  _beginSample(n) {
    const cam = this.camera, P = this.params;
    const saved = { proj: cam.projectionMatrix.clone(), inv: cam.projectionMatrixInverse.clone(), pos: cam.position.clone() };
    let jx = 0, jy = 0;
    if (n > 0) { jx = (halton(n, 2) - 0.5) * P.jitter; jy = (halton(n, 3) - 0.5) * P.jitter; }
    this._applyJitter(cam, jx, jy, this.W, this.H);
    this._jit = [jx, jy];
    if (P.dof.on && P.dof.aperture > 0 && n > 0) {
      // point on the lens (concentric disk mapping of Halton 5,7); shift the frustum so the focus plane stays put
      const a = 2 * halton(n, 5) - 1, b = 2 * halton(n, 7) - 1;
      let rr, th;
      if (a === 0 && b === 0) { rr = 0; th = 0; } else if (Math.abs(a) > Math.abs(b)) { rr = a; th = (Math.PI / 4) * (b / a); } else { rr = b; th = Math.PI / 2 - (Math.PI / 4) * (a / b); }
      const lx = rr * Math.cos(th) * P.dof.aperture, ly = rr * Math.sin(th) * P.dof.aperture;
      const f = P.dof.focus;
      cam.matrixWorld.extractBasis(_v, _m0, _m1); // right, up, back
      cam.position.addScaledVector(_v, lx).addScaledVector(_m0, ly);
      const e = cam.projectionMatrix.elements;
      e[8] -= lx * e[0] / f; e[9] -= ly * e[5] / f;
      cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
      cam.updateMatrixWorld(true);
    }
    return () => { cam.projectionMatrix.copy(saved.proj); cam.projectionMatrixInverse.copy(saved.inv); cam.position.copy(saved.pos); cam.updateMatrixWorld(true); };
  }

  _renderReflection(jit) {
    const r = this.r, cam = this.camera, vc = this.vcam, cy = this.cyclo;
    if (!cy.uniforms.uReflOn.value) return;
    // mirrored camera (reflect position, direction and up across y = 0)
    const pos = cam.position, fwd = _v.set(0, 0, -1).applyQuaternion(cam.quaternion), up = _up.set(0, 1, 0).applyQuaternion(cam.quaternion);
    vc.position.set(pos.x, -pos.y, pos.z);
    vc.up.set(up.x, -up.y, up.z);
    vc.lookAt(pos.x + fwd.x, -(pos.y + fwd.y), pos.z + fwd.z);
    vc.layers.mask = cam.layers.mask;                // the car lives on layer 3: the mirror camera has to see the same layers as the main one
    vc.fov = cam.fov; vc.aspect = cam.aspect; vc.near = cam.near; vc.far = cam.far;
    vc.updateProjectionMatrix(); vc.updateMatrixWorld(true);
    // lookup matrix: the unjittered projection (the texture is jittered, the lookup is not, so the jitter averages out as anti-aliasing)
    cy.uniforms.uReflVP.value.multiplyMatrices(vc.projectionMatrix, vc.matrixWorldInverse);
    if (jit) this._applyJitter(vc, jit[0], jit[1], this.rtRefl.width, this.rtRefl.height);
    cy.uniforms.uReflK.value = this.rtRefl.height / (2 * Math.tan(THREE.MathUtils.degToRad(cam.fov) / 2));
    cy.uniforms.uReflPx.value.set(1 / this.rtRefl.width, 1 / this.rtRefl.height);
    const bg = this.scene.background; this.scene.background = null;
    this.cycloMesh.visible = false;
    r.setRenderTarget(this.rtRefl);
    r.setClearColor(0x000000, 0); r.autoClear = true;
    r.render(this.scene, vc);
    this.cycloMesh.visible = true;
    this.scene.background = bg;
  }

  // ------------------------------------------------------------------------------------------------ the frame
  render(dt = 1 / 60) {
    const r = this.r, cam = this.camera, P = this.params, scene = this.scene;
    r.info.autoReset = false; r.info.reset();
    cam.updateMatrixWorld(true);
    // --- did anything move?
    let moved = this.dirty;
    if (!moved) {
      const a = cam.matrixWorld.elements, b = this._prevCam.elements;
      for (let i = 0; i < 16; i++) if (Math.abs(a[i] - b[i]) > 1e-6) { moved = true; break; }
      if (cam.fov !== this._prevFov || cam.aspect !== this._prevAspect) moved = true;
    }
    this._prevCam.copy(cam.matrixWorld); this._prevFov = cam.fov; this._prevAspect = cam.aspect;
    this.dirty = false;
    this._moving = moved;
    // quality governor
    if (moved) {
      this._still = 0;
      if (this._scale !== this.scaleMoving) this._setScale(this.scaleMoving);
      this._ema += (Math.min(dt, 0.2) - this._ema) * 0.06;
      this._slow = this._ema > 0.026 ? this._slow + 1 : Math.max(0, this._slow - 1);
      if (this._slow > 40 && this.level < 2 && !this.locked) { this.setLevel(this.level + 1); this._slow = 0; this._ema = 1 / 60; }
    } else if (this._scale !== 1 && ++this._still >= 3) { this._setScale(1); this.n = 0; }
    if (moved) this.n = 0;
    const need = this.n < P.samples || moved;
    this.lastFrameRendered = need;
    if (need) {
      const n = this.n;                              // 0 = the unjittered base sample
      this.frame++;
      const restore = this._beginSample(moved ? 0 : n);
      const reflQ = !moved || this.LEVELS[this.level].reflMoving;
      this.cyclo.uniforms.uReflQ.value = reflQ ? 1 : 0;
      if (reflQ) this._renderReflection(this._jit);
      r.setRenderTarget(this.rtScene); r.setClearColor(0x000000, 1); r.autoClear = true;
      this.cyclo.uniforms.uFrame.value = this.frame;
      r.render(scene, cam);
      restore();
      // accumulate
      const rd = this.acc[this.accIdx], wr = this.acc[this.accIdx ^ 1];
      const am = this.accMat.uniforms; am.tPrev.value = rd.texture; am.tCur.value = this.rtScene.texture; am.uW.value = 1 / (n + 1);
      fsPass(r, this.accMat, wr);
      this.accIdx ^= 1; this.n = n + 1;
      this._post(moved || this.n < 6);
    } else if (this._forcePost || this.fade > 0) { this._post(false); }
    this._forcePost = false;
    this._calls = r.info.render.calls; this._tris = r.info.render.triangles;
  }

  _post(useFxaa) {
    const r = this.r, P = this.params;
    const src = this.acc[this.accIdx].texture;
    const pb = { bloom: P.bloom, streak: P.streak };
    this.bloom.render(r, src, this.W, this.H, pb);
    const cm = this.comp[P.tonemap === 'aces' ? 'aces' : 'agx'], u = cm.uniforms;
    u.tScene.value = src; u.tBloom.value = this.bloom.texture; u.tStreak.value = this.bloom.streakTexture;
    u.uBloom.value = P.bloom.strength * (this.bloom.norm ?? 0.2); u.uStreak.value = 0;
    u.uExposure.value = P.exposure; u.uCA.value = 0; u.uVig.value = P.vignette; u.uTeal.value = 0; u.uMagenta.value = 0;
    u.uContrast.value = P.contrast; u.uSat.value = P.saturation; u.uFlash.value.set(0, 0, 0, 0);
    fsPass(r, cm, this.rtLDR);
    const fm = useFxaa ? this.finalFxaa : this.finalSharp, fu = fm.uniforms;
    fu.tLDR.value = this.rtLDR.texture; fu.uSharpen.value = P.sharpen; fu.uGrain.value = P.grain; fu.uFrame.value = this.frame; fu.uFade.value = this.fade;
    fsPass(r, fm, null);
  }

  /** redraw the last accumulated image (fade changes, exposure changes) without rendering the scene */
  repost() { this._forcePost = true; }

  dispose() {
    for (const t of [this.rtScene, this.rtRefl, this.rtLDR, ...this.acc]) t.dispose();
    this.bloom.dispose(); this.accMat.dispose();
    for (const m of [...Object.values(this.comp), this.finalFxaa, this.finalSharp]) m.dispose();
  }
}
const _m0 = new THREE.Vector3(), _m1 = new THREE.Vector3(), _up = new THREE.Vector3();
