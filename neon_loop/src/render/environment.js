// Static world environment + dynamic car probe. Owner: R.
//  * buildEnvironment: phHDRI('shanghai_bund') graded to night (cool, dim, fireflies clamped) → PMREM → scene.environment.
//  * CarProbe: a cube capture around the focus (world layers only, the cars themselves are not in it), refreshed one face
//    per frame, PMREM-filtered every other frame into a stable render target whose texture is `render.probe.texture`.
import * as THREE from 'three';
import { phHDRI } from '../core/assets.js';
import { LAYER } from '../core/layers.js';
import { RF } from '../core/reflect.js';
import { postMaterial, fsPass, makeRT } from './common.js';

const GRADE_FRAG = /* glsl */`
uniform sampler2D tHDR;
uniform vec3 uTint;
uniform float uGain, uClampV, uSat;
varying vec2 vUv;
void main() {
  vec3 c = texture(tHDR, vUv).rgb;
  c = min(c, vec3(uClampV));
  float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = mix(vec3(l), c, uSat);
  gl_FragColor = vec4(c * uTint * uGain, 1.0);
}`;

export async function buildEnvironment(app, { gain = 0.5, tint = [0.45, 0.65, 1.0], intensity = 0.35 } = {}) {
  const r = app.renderer;
  const hdr = await phHDRI('shanghai_bund');
  const w = 1024, h = 512;
  const rt = makeRT(w, h, { name: 'envGraded' });
  rt.texture.mapping = THREE.EquirectangularReflectionMapping;
  const mat = postMaterial({
    name: 'envGrade', fragmentShader: GRADE_FRAG,
    uniforms: { tHDR: { value: hdr }, uTint: { value: new THREE.Vector3(...tint) }, uGain: { value: gain }, uClampV: { value: 40 }, uSat: { value: 0.85 } },
  });
  fsPass(r, mat, rt);
  const pmrem = new THREE.PMREMGenerator(r);
  const env = pmrem.fromEquirectangular(rt.texture);
  pmrem.dispose();
  rt.dispose(); mat.dispose();
  app.scene.environment = env.texture;
  app.scene.environmentIntensity = intensity;
  return env;
}

const MASK_WORLD = (1 << LAYER.DEFAULT) | (1 << LAYER.MAIN_ONLY);

export class CarProbe {
  constructor(renderer, { size = 256, far = 700, every = 1, pmremEvery = 2 } = {}) {
    this.renderer = renderer;
    this.size = size; this.every = every; this.pmremEvery = pmremEvery;
    this.cube = new THREE.WebGLCubeRenderTarget(size, { type: THREE.HalfFloatType, generateMipmaps: false, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter });
    this.cube.texture.name = 'carProbeCube';
    this.cc = new THREE.CubeCamera(0.4, far, this.cube);
    for (const c of this.cc.children) c.layers.mask = MASK_WORLD;
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.out = null;
    this.face = 0; this.frame = 0; this.pending = 0;
    this.enabled = true;
    this.pos = new THREE.Vector3();
    this.texture = null;              // PMREM texture (stable once created)
    this.dirty = true;
    this._fallback = null;
  }

  /** Seed the probe's output with a render target of its own so `probe.texture` is valid immediately. */
  init(fallbackEnv) {
    // First conversion of the (empty) cube creates the stable output target; later calls reuse it.
    this.out = this.pmrem.fromCubemap(this.cube.texture);
    this.texture = this.out.texture;
    this._fallback = fallbackEnv;
  }

  /** Render `faces` faces (or all six with faces = 6) around `pos`. */
  update(scene, pos, faces = 1) {
    if (!this.enabled) return;
    const r = this.renderer;
    this.pos.copy(pos);
    this.cc.position.copy(pos);
    this.cc.updateMatrixWorld(true);
    const cam = this.cc.children;
    const bgs = scene.background;
    const reflOn = RF.uReflectOn.value;
    RF.uReflectOn.value = 0;                     // the road's planar reflection is only valid for the main view
    const ac = r.autoClear; r.autoClear = true;
    for (let i = 0; i < faces; i++) {
      const f = this.face;
      r.setRenderTarget(this.cube, f, 0);
      r.render(scene, cam[f]);
      this.face = (f + 1) % 6;
    }
    r.autoClear = ac;
    RF.uReflectOn.value = reflOn;
    this.cube.texture.needsPMREMUpdate = false;
    this.frame++;
    // PMREM filtering is the expensive part: once per full cycle of faces
    this.pending += faces;
    if (this.pending >= 6) { this.pending -= 6; this.pmrem.fromCubemap(this.cube.texture, this.out); }
    scene.background = bgs;
  }

  dispose() { this.cube.dispose(); this.out?.dispose(); this.pmrem.dispose(); }
}
