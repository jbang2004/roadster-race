// Temporal anti-aliasing with a car mask. Owner: R.
// Halton(2,3) sub-pixel jitter on the scene projection, camera reprojection from the closest depth of the 3x3, 5-tap
// Catmull-Rom history, YCoCg variance clip in a Karis-tonemapped space. The scene target's alpha is the CAR MASK
// (0 world / 1 car). Masked pixels do NOT use the camera reprojection (a moving car would ghost): they are
// reprojected with the car's own rigid motion (current world->local, local->previous world, per car, up to 8) and, when
// the history there was not a car, the history is rejected. The resolve also writes the mask to alpha for motion blur.
//   taa.jitter(camera, W, H) → offsets camera.projectionMatrix (pair with restore())
//   taa.render(renderer, sceneTex, depthTex, frame, params, cars)
import * as THREE from 'three';
import { postMaterial, fsPass, makeRT, POST_GLSL, halton } from './common.js';

export const MAX_CARS = 8;

const FRAG = /* glsl */`
${POST_GLSL}
#define MAX_CARS ${MAX_CARS}
uniform sampler2D tCur, tHist, tDepth;
uniform mat4 uInvViewProj, uPrevViewProj;
uniform vec2 uTexel, uSize;     // history (output) texel / size
uniform vec2 uCurTexel, uJit;   // current (scene) texel; this frame's jitter in UV
uniform float uValid, uBlend, uGamma, uCarBlend, uCarGamma;
uniform int uCarN;
uniform vec4 uCarC[MAX_CARS];          // xyz centre, w radius^2
uniform mat4 uCarInv[MAX_CARS];        // current world -> car local
uniform mat4 uCarPrev[MAX_CARS];       // car local -> previous world
varying vec2 vUv;

vec3 tm(vec3 c) { return c / (1.0 + max(c.r, max(c.g, c.b))); }
vec3 itm(vec3 c) { return c / max(1.0 - max(c.r, max(c.g, c.b)), 1e-3); }

vec3 historyCatmullRom(vec2 uv) {
  vec2 sp = uv * uSize;
  vec2 t1 = floor(sp - 0.5) + 0.5;
  vec2 f = sp - t1;
  vec2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
  vec2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
  vec2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
  vec2 w3 = f * f * (-0.5 + 0.5 * f);
  vec2 w12 = w1 + w2;
  vec2 t0 = (t1 - 1.0) * uTexel, t3 = (t1 + 2.0) * uTexel, t12 = (t1 + w2 / w12) * uTexel;
  vec3 r = texture(tHist, vec2(t12.x, t0.y)).rgb * (w12.x * w0.y)
         + texture(tHist, vec2(t0.x, t12.y)).rgb * (w0.x * w12.y)
         + texture(tHist, vec2(t12.x, t12.y)).rgb * (w12.x * w12.y)
         + texture(tHist, vec2(t3.x, t12.y)).rgb * (w3.x * w12.y)
         + texture(tHist, vec2(t12.x, t3.y)).rgb * (w12.x * w3.y);
  float ws = w12.x * w0.y + w0.x * w12.y + w12.x * w12.y + w3.x * w12.y + w12.x * w3.y;
  return max(r / ws, vec3(0.0));
}

void main() {
  vec2 cuv = vUv + uJit;
  vec4 curS = texture(tCur, cuv);
  vec3 cur = min(curS.rgb, vec3(2000.0));
  float maskC = curS.a;
  vec3 cy = nl_toYCoCg(tm(cur));
  vec3 m1 = cy, m2 = cy * cy;
  float zMin = texture(tDepth, cuv).x; vec2 zOff = vec2(0.0);
  float maskMax = maskC;
  for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
    if (x == 0 && y == 0) continue;
    vec2 o = vec2(float(x), float(y));
    vec4 s = texture(tCur, cuv + o * uCurTexel);
    vec3 c = nl_toYCoCg(tm(s.rgb));
    m1 += c; m2 += c * c;
    maskMax = max(maskMax, s.a);
    float z = texture(tDepth, cuv + o * uCurTexel).x;
    if (z < zMin) { zMin = z; zOff = o; }
  }
  vec3 mean = m1 / 9.0;
  vec3 sigma = sqrt(abs(m2 / 9.0 - mean * mean));
  bool carish = maskMax > 0.5;
  float gamma = carish ? uCarGamma : uGamma;
  vec3 ext = gamma * sigma + vec3(1e-4);

  vec2 uvz = vUv + zOff * uCurTexel;
  vec4 wp = uInvViewProj * vec4(uvz * 2.0 - 1.0, zMin * 2.0 - 1.0, 1.0);
  wp /= wp.w;
  if (carish && uCarN > 0) {
    // rigid-body reprojection with the car this pixel belongs to
    int best = -1; float bd = 1e9;
    for (int i = 0; i < MAX_CARS; i++) {
      if (i >= uCarN) break;
      vec3 d = wp.xyz - uCarC[i].xyz; float d2 = dot(d, d);
      if (d2 < uCarC[i].w && d2 < bd) { bd = d2; best = i; }
    }
    if (best >= 0) {
      vec4 lp = uCarInv[best] * vec4(wp.xyz, 1.0);
      wp = vec4((uCarPrev[best] * lp).xyz, 1.0);
    }
  }
  vec4 pc = uPrevViewProj * wp;
  vec2 puv = pc.xy / pc.w * 0.5 + 0.5;
  vec2 hUv = vUv + (puv - uvz);
  bool off = pc.w <= 0.0 || any(lessThan(hUv, vec2(0.0))) || any(greaterThan(hUv, vec2(1.0)));

  vec3 hist = historyCatmullRom(hUv);
  float maskH = texture(tHist, hUv).a;
  vec3 hy = nl_toYCoCg(tm(hist));
  vec3 v = hy - mean; vec3 a = abs(v / ext);
  float mm = max(a.x, max(a.y, a.z));
  if (mm > 1.0) hy = mean + v / mm;

  float k = (carish ? uCarBlend : uBlend) * (1.0 + clamp(mm - 1.0, 0.0, 1.0));
  // history that was not the same kind of surface (car vs. world) is not trusted
  k = mix(k, max(k, 0.6), clamp(abs(maskH - maskC) * 2.0, 0.0, 1.0));
  if (off || uValid < 0.5) k = 1.0;
  vec3 res = mix(hy, cy, clamp(k, 0.0, 1.0));
  gl_FragColor = vec4(itm(max(nl_fromYCoCg(res), vec3(0.0))), maskC);
}
`;

export class TAAPass {
  constructor() {
    this.rt = [makeRT(1, 1, { name: 'taaA' }), makeRT(1, 1, { name: 'taaB' })];
    this.cur = 0;
    this.valid = false;
    this.index = 0;
    this.offset = new THREE.Vector2();
    this._saved = new THREE.Matrix4();
    this._savedInv = new THREE.Matrix4();
    this._cam = null;
    const carC = Array.from({ length: MAX_CARS }, () => new THREE.Vector4());
    const carInv = Array.from({ length: MAX_CARS }, () => new THREE.Matrix4());
    const carPrev = Array.from({ length: MAX_CARS }, () => new THREE.Matrix4());
    this.mat = postMaterial({
      name: 'taa', fragmentShader: FRAG,
      uniforms: {
        tCur: { value: null }, tHist: { value: null }, tDepth: { value: null },
        uInvViewProj: { value: new THREE.Matrix4() }, uPrevViewProj: { value: new THREE.Matrix4() },
        uTexel: { value: new THREE.Vector2() }, uSize: { value: new THREE.Vector2() },
        uCurTexel: { value: new THREE.Vector2() }, uJit: { value: new THREE.Vector2() },
        uValid: { value: 0 }, uBlend: { value: 0.1 }, uGamma: { value: 1.0 }, uCarBlend: { value: 0.25 }, uCarGamma: { value: 0.8 },
        uCarN: { value: 0 }, uCarC: { value: carC }, uCarInv: { value: carInv }, uCarPrev: { value: carPrev },
      },
    });
  }
  get texture() { return this.rt[this.cur].texture; }
  setSize(w, h, sw = w, sh = h) {
    const same = w === this.w && h === this.h;
    for (const rt of this.rt) rt.setSize(w, h);
    this.w = w; this.h = h; this.sw = sw; this.sh = sh;
    if (!same) this.valid = false;                 // a scene-resolution change keeps the output-resolution history
  }

  jitter(camera, W, H, scale = 1) {
    this.index = (this.index + 1) % 8;
    this.offset.set((halton(this.index + 1, 2) - 0.5) * scale, (halton(this.index + 1, 3) - 0.5) * scale);
    this._cam = camera;
    this._saved.copy(camera.projectionMatrix);
    this._savedInv.copy(camera.projectionMatrixInverse);
    const e = camera.projectionMatrix.elements;
    e[8] += 2 * this.offset.x / W;
    e[9] += 2 * this.offset.y / H;
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  }
  restore() {
    if (!this._cam) return;
    this._cam.projectionMatrix.copy(this._saved);
    this._cam.projectionMatrixInverse.copy(this._savedInv);
    this._cam = null;
  }

  /** `cars`: [{ center: Vector3, radius, inv: Matrix4 (world->local now), prev: Matrix4 (local->previous world) }] */
  render(renderer, sceneTex, depthTex, frame, params, cars) {
    const prev = this.cur; this.cur ^= 1;
    const u = this.mat.uniforms;
    u.tCur.value = sceneTex; u.tDepth.value = depthTex; u.tHist.value = this.rt[prev].texture;
    u.uInvViewProj.value.copy(frame.viewProj).invert();
    u.uPrevViewProj.value.copy(frame.prevViewProj);
    u.uTexel.value.set(1 / this.w, 1 / this.h); u.uSize.value.set(this.w, this.h);
    const sw = this.sw ?? this.w, sh = this.sh ?? this.h;
    u.uCurTexel.value.set(1 / sw, 1 / sh);
    u.uJit.value.set(this.offset.x / sw, this.offset.y / sh);
    u.uValid.value = this.valid && frame.historyOk ? 1 : 0;
    u.uBlend.value = params.taaBlend;
    u.uGamma.value = params.taaGamma;
    u.uCarBlend.value = params.taaCarBlend;
    u.uCarGamma.value = params.taaCarGamma;
    const n = Math.min(MAX_CARS, cars?.length ?? 0);
    u.uCarN.value = n;
    for (let i = 0; i < n; i++) {
      const c = cars[i];
      u.uCarC.value[i].set(c.center.x, c.center.y, c.center.z, c.radius * c.radius);
      u.uCarInv.value[i].copy(c.inv);
      u.uCarPrev.value[i].copy(c.prev);
    }
    fsPass(renderer, this.mat, this.rt[this.cur]);
    this.valid = true;
  }
  dispose() { for (const rt of this.rt) rt.dispose(); this.mat.dispose(); }
}
