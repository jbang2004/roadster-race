// Bloom + anamorphic streaks. Owner: R.
// Bright pass: firefly-safe (4 bilinear taps, Karis weights, clamp), Rec.709 luma soft knee at `threshold`. Then a
// dual-Kawase chain; the upsample accumulates progressively (up[d] = mip[d] + tent(up[d+1]) * spread) and is normalised
// by the total weight, so `strength` is the fraction of energy scattered and `radius` only moves it between tight and wide.
// Streaks: a much higher threshold, horizontal-only down/up chain (width halves, height stays) tinted blue-cyan.
import * as THREE from 'three';
import { postMaterial, fsPass, makeRT, POST_GLSL } from './common.js';

const BRIGHT_FRAG = /* glsl */`
${POST_GLSL}
uniform sampler2D tScene;
uniform vec2 uTexel;          // source texel
uniform float uThreshold, uKnee, uClampV;
varying vec2 vUv;
vec3 tap(vec2 o) { return min(texture(tScene, vUv + o * uTexel).rgb, vec3(uClampV)); }
void main() {
  vec3 a = tap(vec2(-1.0, -1.0)), b = tap(vec2(1.0, -1.0)), c = tap(vec2(-1.0, 1.0)), d = tap(vec2(1.0, 1.0));
  float wa = 1.0 / (1.0 + dot(a, NL_LUMA709)), wb = 1.0 / (1.0 + dot(b, NL_LUMA709));
  float wc = 1.0 / (1.0 + dot(c, NL_LUMA709)), wd = 1.0 / (1.0 + dot(d, NL_LUMA709));
  vec3 col = (a * wa + b * wb + c * wc + d * wd) / (wa + wb + wc + wd);
  float l = dot(col, NL_LUMA709);
  float k = max(l - uThreshold, 0.0); k = k * k / (k + uKnee);
  gl_FragColor = vec4(col * (k / max(l, 1e-4)), 1.0);
}
`;

const DOWN_FRAG = /* glsl */`
uniform sampler2D tSrc;
uniform vec2 uTexel;
varying vec2 vUv;
void main() {
  vec3 c = texture(tSrc, vUv).rgb * 4.0;
  c += texture(tSrc, vUv + vec2(-1.0, -1.0) * uTexel).rgb;
  c += texture(tSrc, vUv + vec2(1.0, -1.0) * uTexel).rgb;
  c += texture(tSrc, vUv + vec2(-1.0, 1.0) * uTexel).rgb;
  c += texture(tSrc, vUv + vec2(1.0, 1.0) * uTexel).rgb;
  gl_FragColor = vec4(c * 0.125, 1.0);
}
`;

const UP_FRAG = /* glsl */`
uniform sampler2D tCoarse, tFine;
uniform vec2 uTexel;          // coarse texel
uniform float uWeight;
varying vec2 vUv;
void main() {
  vec3 c = (texture(tCoarse, vUv + vec2(-1.0, 0.0) * uTexel).rgb + texture(tCoarse, vUv + vec2(1.0, 0.0) * uTexel).rgb
          + texture(tCoarse, vUv + vec2(0.0, -1.0) * uTexel).rgb + texture(tCoarse, vUv + vec2(0.0, 1.0) * uTexel).rgb) * 2.0;
  c += texture(tCoarse, vUv + vec2(-1.0, -1.0) * uTexel).rgb + texture(tCoarse, vUv + vec2(1.0, -1.0) * uTexel).rgb
     + texture(tCoarse, vUv + vec2(-1.0, 1.0) * uTexel).rgb + texture(tCoarse, vUv + vec2(1.0, 1.0) * uTexel).rgb;
  gl_FragColor = vec4(texture(tFine, vUv).rgb + c / 12.0 * uWeight, 1.0);
}
`;

// horizontal-only chain for the anamorphic streaks
const HDOWN_FRAG = /* glsl */`
uniform sampler2D tSrc;
uniform vec2 uTexel;
varying vec2 vUv;
void main() {
  vec3 c = texture(tSrc, vUv).rgb * 0.4;
  c += (texture(tSrc, vUv + vec2(-1.0, 0.0) * uTexel).rgb + texture(tSrc, vUv + vec2(1.0, 0.0) * uTexel).rgb) * 0.25;
  c += (texture(tSrc, vUv + vec2(-2.5, 0.0) * uTexel).rgb + texture(tSrc, vUv + vec2(2.5, 0.0) * uTexel).rgb) * 0.05;
  gl_FragColor = vec4(c, 1.0);
}
`;
const HUP_FRAG = /* glsl */`
uniform sampler2D tCoarse, tFine;
uniform vec2 uTexel;
uniform float uWeight;
varying vec2 vUv;
void main() {
  vec3 c = texture(tCoarse, vUv).rgb * 0.5
         + (texture(tCoarse, vUv + vec2(-1.0, 0.0) * uTexel).rgb + texture(tCoarse, vUv + vec2(1.0, 0.0) * uTexel).rgb) * 0.25;
  gl_FragColor = vec4(texture(tFine, vUv).rgb + c * uWeight, 1.0);
}
`;

export class BloomPass {
  constructor() {
    this.levels = 6;
    this.mips = []; this.ups = [];
    for (let i = 0; i < 7; i++) {
      this.mips.push(makeRT(1, 1, { name: `bloomMip${i}` }));
      this.ups.push(makeRT(1, 1, { name: `bloomUp${i}` }));
    }
    this.bright = postMaterial({
      name: 'bloomBright', fragmentShader: BRIGHT_FRAG,
      uniforms: { tScene: { value: null }, uTexel: { value: new THREE.Vector2() }, uThreshold: { value: 1 }, uKnee: { value: 0.5 }, uClampV: { value: 80 } },
    });
    this.down = postMaterial({ name: 'bloomDown', fragmentShader: DOWN_FRAG, uniforms: { tSrc: { value: null }, uTexel: { value: new THREE.Vector2() } } });
    this.up = postMaterial({ name: 'bloomUp', fragmentShader: UP_FRAG, uniforms: { tCoarse: { value: null }, tFine: { value: null }, uTexel: { value: new THREE.Vector2() }, uWeight: { value: 0.7 } } });
    this.output = this.ups[0];

    // streaks (quarter res, horizontal chain)
    this.sMips = []; this.sUps = [];
    for (let i = 0; i < 5; i++) { this.sMips.push(makeRT(1, 1, { name: `streakMip${i}` })); this.sUps.push(makeRT(1, 1, { name: `streakUp${i}` })); }
    this.sBright = postMaterial({
      name: 'streakBright', fragmentShader: BRIGHT_FRAG,
      uniforms: { tScene: { value: null }, uTexel: { value: new THREE.Vector2() }, uThreshold: { value: 6 }, uKnee: { value: 4 }, uClampV: { value: 400 } },
    });
    this.hdown = postMaterial({ name: 'streakDown', fragmentShader: HDOWN_FRAG, uniforms: { tSrc: { value: null }, uTexel: { value: new THREE.Vector2() } } });
    this.hup = postMaterial({ name: 'streakUp', fragmentShader: HUP_FRAG, uniforms: { tCoarse: { value: null }, tFine: { value: null }, uTexel: { value: new THREE.Vector2() }, uWeight: { value: 0.8 } } });
    this.streakOut = this.sUps[0];
    this.sLevels = 5;
  }

  get texture() { return this.output.texture; }
  get streakTexture() { return this.streakOut.texture; }

  setSize(hw, hh) {
    let w = hw, h = hh;
    for (let i = 0; i < this.mips.length; i++) {
      this.mips[i].setSize(w, h); this.ups[i].setSize(w, h);
      w = Math.max(2, Math.round(w / 2)); h = Math.max(2, Math.round(h / 2));
    }
    // streaks start at half the bloom size (quarter of output) and only halve in x
    w = Math.max(2, Math.round(hw / 2)); h = Math.max(2, Math.round(hh / 2));
    for (let i = 0; i < this.sMips.length; i++) {
      this.sMips[i].setSize(w, h); this.sUps[i].setSize(w, h);
      w = Math.max(2, Math.round(w / 2));
    }
  }

  render(renderer, sceneTex, srcW, srcH, p) {
    const L = Math.max(2, Math.min(p.bloom.levels | 0, this.mips.length));
    const b = this.bright.uniforms;
    b.tScene.value = sceneTex;
    b.uTexel.value.set(1 / srcW, 1 / srcH);
    b.uThreshold.value = p.bloom.threshold; b.uKnee.value = p.bloom.knee;
    fsPass(renderer, this.bright, this.mips[0]);
    const d = this.down.uniforms;
    for (let i = 1; i < L; i++) {
      const src = this.mips[i - 1];
      d.tSrc.value = src.texture; d.uTexel.value.set(1 / src.width, 1 / src.height);
      fsPass(renderer, this.down, this.mips[i]);
    }
    const u = this.up.uniforms;
    const spread = 0.35 + 0.6 * p.bloom.radius;       // radius 0..1 → 0.35..0.95
    u.uWeight.value = spread;
    let tot = 0, wgt = 1; for (let i = 0; i < L; i++) { tot += wgt; wgt *= spread; }
    // normalisation is applied once at the end through the composite (see norm)
    this.norm = 1 / tot;
    let coarse = this.mips[L - 1];
    for (let i = L - 2; i >= 0; i--) {
      u.tCoarse.value = coarse.texture; u.tFine.value = this.mips[i].texture;
      u.uTexel.value.set(1 / coarse.width, 1 / coarse.height);
      fsPass(renderer, this.up, this.ups[i]);
      coarse = this.ups[i];
    }
    this.output = this.ups[0];

    if (p.streak.strength > 0.001) {
      const sb = this.sBright.uniforms;
      sb.tScene.value = sceneTex; sb.uTexel.value.set(2 / srcW, 2 / srcH);
      sb.uThreshold.value = p.streak.threshold; sb.uKnee.value = p.streak.threshold * 0.6;
      fsPass(renderer, this.sBright, this.sMips[0]);
      const hd = this.hdown.uniforms;
      const SL = this.sLevels;
      for (let i = 1; i < SL; i++) {
        const src = this.sMips[i - 1];
        hd.tSrc.value = src.texture; hd.uTexel.value.set(1 / src.width, 1 / src.height);
        fsPass(renderer, this.hdown, this.sMips[i]);
      }
      const hu = this.hup.uniforms;
      hu.uWeight.value = 0.55 + 0.4 * p.streak.length;
      let c = this.sMips[SL - 1];
      for (let i = SL - 2; i >= 0; i--) {
        hu.tCoarse.value = c.texture; hu.tFine.value = this.sMips[i].texture;
        hu.uTexel.value.set(1 / c.width, 1 / c.height);
        fsPass(renderer, this.hup, this.sUps[i]);
        c = this.sUps[i];
      }
      this.streakOut = this.sUps[0];
    }
  }

  dispose() {
    for (const rt of [...this.mips, ...this.ups, ...this.sMips, ...this.sUps]) rt.dispose();
    for (const m of [this.bright, this.down, this.up, this.sBright, this.hdown, this.hup]) m.dispose();
  }
}
