// Planar wet-road reflection. Owner: R.  Fills RF (src/core/reflect.js).
// The scene is rendered from the main camera mirrored about the road plane under the focus, with an oblique near plane
// that clips everything below the road, at reduced resolution into a mipmapped HDR target (the mip chain is the roughness
// blur). Two sub-passes like the main frame: world (DEFAULT + REFLECTION_ONLY), then cars (CARS, with the light pool).
import * as THREE from 'three';
import { LAYER } from '../core/layers.js';
import { RF } from '../core/reflect.js';
import { fsPass, postMaterial } from './common.js';

// The scene is rendered into an MSAA target, then copied through this pass into a mipmapped target: NaN/Inf
// (e.g. half-float overflow or a degenerate light in some world shader) would otherwise spread through the mip
// chain into big white/black blocks on the rough road near the camera. Also caps fireflies.
const SANITIZE_FRAG = /* glsl */`
uniform sampler2D tSrc;
varying vec2 vUv;
void main() {
  vec4 c = texture2D(tSrc, vUv);
  bool bad = any(notEqual(c.rgb, c.rgb)) || any(greaterThan(abs(c.rgb), vec3(6.0e4)));
  gl_FragColor = vec4(bad ? vec3(0.0) : min(c.rgb, vec3(48.0)), 1.0);
}`;

const MASK_WORLD = (1 << LAYER.DEFAULT) | (1 << LAYER.REFLECTION_ONLY);
const MASK_CARS = 1 << LAYER.CARS;
const _q = new THREE.Vector4(), _clip = new THREE.Vector4();
const _f = new THREE.Vector3(), _u = new THREE.Vector3(), _eye = new THREE.Vector3(), _cp = new THREE.Vector3(), _tg = new THREE.Vector3();
const _m = new THREE.Matrix4(), _plane = new THREE.Plane();
const _bias = new THREE.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);

export class PlanarReflection {
  constructor(renderer, { scale = 0.5, samples = 4, far = 6000, margin = 1.06 } = {}) {
    this.renderer = renderer;
    this.scale = scale; this.samples = samples; this.far = far; this.margin = margin;
    this.rt = null;
    this.cam = new THREE.PerspectiveCamera();
    this.cam.matrixAutoUpdate = false; this.cam.matrixWorldAutoUpdate = false;
    this.valid = false;
    this.w = 0; this.h = 0;
    this.enabled = true;
    this.calls = 0;
  }

  setSize(W, H) {
    const sc = Math.min(this.scale, Math.sqrt((this.maxPx ?? Infinity) / (W * H)));
    const w = Math.max(64, Math.round(W * sc)), h = Math.max(64, Math.round(H * sc));
    if (this.rt && w === this.w && h === this.h) return;
    this.w = w; this.h = h;
    this.rt?.dispose();
    this.rtMip?.dispose();
    this.rt = new THREE.WebGLRenderTarget(w, h, {
      type: THREE.HalfFloatType, format: THREE.RGBAFormat, depthBuffer: true, stencilBuffer: false,
      generateMipmaps: false, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
      samples: this.samples, wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping,
    });
    this.rt.texture.name = 'roadReflectionMSAA';
    this.rtMip = new THREE.WebGLRenderTarget(w, h, {
      type: THREE.HalfFloatType, format: THREE.RGBAFormat, depthBuffer: false, stencilBuffer: false,
      generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter,
      wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping,
    });
    this.rtMip.texture.name = 'roadReflection';
    this.sanitize ??= postMaterial({ name: 'reflSanitize', uniforms: { tSrc: { value: null } }, fragmentShader: SANITIZE_FRAG });
    this.sanitize.uniforms.tSrc.value = this.rt.texture;
    RF.tReflect.value = this.rtMip.texture;
    RF.uReflectLod.value = Math.min(6, Math.floor(Math.log2(Math.min(w, h))) - 2);
  }

  /** Render. plane = { p: Vector3, n: Vector3 (unit, up) }. Returns true when RF was updated. */
  render(scene, camera, plane, passCamera = null) {
    const r = this.renderer;
    if (!this.enabled || !this.rt) { RF.uReflectOn.value = 0; this.valid = false; return false; }
    camera.getWorldPosition(_cp);
    const n = plane.n, p = plane.p;
    const dist = (_cp.x - p.x) * n.x + (_cp.y - p.y) * n.y + (_cp.z - p.z) * n.z;
    if (dist < 0.08) { RF.uReflectOn.value = 0; this.valid = false; return false; }

    // mirrored camera (a proper rotation: forward and up reflected, right recomputed by lookAt)
    _eye.copy(_cp).addScaledVector(n, -2 * dist);
    _f.set(0, 0, -1).transformDirection(camera.matrixWorld);
    _u.set(0, 1, 0).transformDirection(camera.matrixWorld);
    _f.addScaledVector(n, -2 * _f.dot(n));
    _u.addScaledVector(n, -2 * _u.dot(n));
    _tg.copy(_eye).add(_f);
    const cam = this.cam;
    cam.position.copy(_eye); cam.up.copy(_u);
    _m.lookAt(_eye, _tg, _u);
    cam.matrixWorld.copy(_m).setPosition(_eye);
    cam.matrixWorldInverse.copy(cam.matrixWorld).invert();
    cam.quaternion.setFromRotationMatrix(_m);

    // projection: the main camera's, slightly widened, far reduced
    cam.near = camera.near; cam.far = Math.min(camera.far, this.far);
    cam.fov = camera.fov; cam.aspect = camera.aspect;
    cam.projectionMatrix.copy(camera.projectionMatrix);
    // un-jittered main projection (TAA offsets live in elements 8/9)
    cam.projectionMatrix.elements[8] = 0; cam.projectionMatrix.elements[9] = 0;
    cam.projectionMatrix.elements[0] /= this.margin; cam.projectionMatrix.elements[5] /= this.margin;
    const P = cam.projectionMatrix;
    // plane lifted a hair so road-level debris does not z-fight with the mirror line
    // texture matrix: bias * projection * view, rows 0,1,3 → uv; row 2 carries the plane
    const tm = RF.uReflectMatrix.value;
    tm.copy(_bias).multiply(P).multiply(cam.matrixWorldInverse);
    const e = tm.elements;
    e[2] = n.x; e[6] = n.y; e[10] = n.z; e[14] = -n.dot(p);
    // oblique near plane (Lengyel): clip = plane in camera space, facing the camera side that keeps geometry above the road
    const pl = _plane.setFromNormalAndCoplanarPoint(n, _tg.copy(p).addScaledVector(n, 0.02));
    pl.applyMatrix4(cam.matrixWorldInverse);
    _clip.set(pl.normal.x, pl.normal.y, pl.normal.z, pl.constant);
    const pe = P.elements;
    _q.x = (Math.sign(_clip.x) + pe[8]) / pe[0];
    _q.y = (Math.sign(_clip.y) + pe[9]) / pe[5];
    _q.z = -1.0;
    _q.w = (1.0 + pe[10]) / pe[14];
    _clip.multiplyScalar(2.0 / _clip.dot(_q));
    pe[2] = _clip.x; pe[6] = _clip.y; pe[10] = _clip.z + 1.0; pe[14] = _clip.w;
    cam.projectionMatrixInverse.copy(P).invert();

    // render
    const bg = scene.background;
    r.setRenderTarget(this.rt);
    r.setClearColor(0x000000, 0);
    r.autoClear = true;
    cam.layers.mask = MASK_WORLD;
    r.render(scene, cam);
    // cars (separate pass: they see the light pool; depth-tested against the world)
    scene.background = null;
    r.autoClear = false;
    cam.layers.mask = MASK_CARS;
    r.render(scene, cam);
    r.autoClear = true;
    scene.background = bg;
    fsPass(r, this.sanitize, this.rtMip);          // resolve + sanitize; three builds the mip chain after this render
    RF.uReflectOn.value = 1;
    this.valid = true;
    return true;
  }

  dispose() { this.rt?.dispose(); this.rtMip?.dispose(); this.sanitize?.dispose(); RF.uReflectOn.value = 0; }
}
