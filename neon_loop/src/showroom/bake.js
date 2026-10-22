// Floor light map: the irradiance on the studio floor with the car in it.  Monte-Carlo over the studio's rectangular area lights
// (stratified samples) and a cosine-weighted dome (ambient occlusion).  Every sample is a point light: the car is rendered once from it
// into a distance map, then one full-floor pass adds that sample's lit contribution.  Hundreds of samples = the physically soft shadow
// of the area lights (wide penumbra, contact darkening under the body) at no run-time cost: the floor shader just reads the result.
import * as THREE from 'three';

const FRAG = /* glsl */`
uniform sampler2D tDist;
uniform mat4 uLVP; uniform vec3 uLPos; uniform vec3 uCol; uniform vec4 uRect; uniform vec3 uLN; uniform float uArea; uniform int uMode; uniform float uBeam;
uniform vec4 uGobo; uniform vec2 uGoboRS; uniform float uGoboOn;
uniform vec4 uBandA, uBandB, uBandC; uniform float uBandOn;   // light band: hard 'flag' edge (point, inward normal), width, penumbra, far softness, end extents/softness        // floor mask of a gobo'd light: centre xz, radii, rotation (cos, sin), edge exponent in uGoboRS.y
varying vec2 vUv;
void main() {
  vec3 P = vec3(uRect.x + (vUv.x - 0.5) * uRect.z, 0.0, uRect.y + (vUv.y - 0.5) * uRect.z);
  vec3 toL = uLPos - P; float d2 = dot(toL, toL); float d = sqrt(d2); vec3 l = toL / d;
  if (l.y <= 0.0) { gl_FragColor = vec4(0.0); return; }
  float w = 1.0;
  // (pow(0, 0) is undefined in GLSL: it used to leave NaN texels, a white ring at the map edge)
  if (uMode == 0) { float cl = max(dot(-l, uLN), 0.0); w = l.y * cl * (uBeam > 0.0 ? pow(cl, uBeam) : 1.0) * uArea / d2; }
  if (uGoboOn > 0.5) { vec2 q = P.xz - uGobo.xy; float c = cos(uGoboRS.x), s = sin(uGoboRS.x); q = vec2(c * q.x + s * q.y, -s * q.x + c * q.y) / uGobo.zw; w *= exp(-pow(dot(q, q), uGoboRS.y)); }
  if (uBandOn > 0.5) {
    vec2 q = P.xz - uBandA.xy; float sd = dot(q, uBandA.zw), ud = dot(q, vec2(uBandA.w, -uBandA.z));
    w *= smoothstep(0.0, uBandB.y, sd) * (1.0 - smoothstep(uBandB.x - uBandB.z, uBandB.x, sd)) * exp(-max(sd, 0.0) / uBandB.w) * (1.0 - uBandC.w * smoothstep(uBandC.x, uBandC.y, ud)) * smoothstep(uBandC.x, uBandC.x + uBandC.z, ud) * (1.0 - smoothstep(uBandC.y - uBandC.z, uBandC.y, ud));
  }
  vec4 cp = uLVP * vec4(P, 1.0);
  float vis = 1.0;
  if (cp.w > 0.0) {
    vec2 uv = cp.xy / cp.w * 0.5 + 0.5;
    if (all(greaterThan(uv, vec2(0.0))) && all(lessThan(uv, vec2(1.0)))) {
      float dOcc = texture(tDist, uv).r;
      if (dOcc > 0.0 && dOcc < d - 0.012) vis = 0.0;
    }
  }
  gl_FragColor = vec4(uCol * w * vis, 1.0);
}`;
const VERT = /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

const DIST_VERT = /* glsl */`varying vec3 vW; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const DIST_FRAG = /* glsl */`uniform vec3 uLP; varying vec3 vW; void main() { gl_FragColor = vec4(distance(vW, uLP), 0.0, 0.0, 1.0); }`;

const EXTENT = 28;                                 // light map covers 28 x 28 m, centred on the car

function hash(i) { let x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }

export class FloorBake {
  constructor(renderer, size = 2048, distSize = 1024) {
    this.r = renderer; this.size = size;
    this.rt = new THREE.WebGLRenderTarget(size, size, { type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false });
    this.rt.texture.name = 'floorLight';
    this.dist = new THREE.WebGLRenderTarget(distSize, distSize, { type: THREE.FloatType, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, depthBuffer: true });
    this.distMat = new THREE.ShaderMaterial({ uniforms: { uLP: { value: new THREE.Vector3() } }, vertexShader: DIST_VERT, fragmentShader: DIST_FRAG, side: THREE.DoubleSide });
    this.mat = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, depthTest: false, depthWrite: false, transparent: false,
      blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
      blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneFactor,
      uniforms: { tDist: { value: this.dist.texture }, uLVP: { value: new THREE.Matrix4() }, uLPos: { value: new THREE.Vector3() }, uCol: { value: new THREE.Vector3() },
        uRect: { value: new THREE.Vector4(0, 0, EXTENT, 0) }, uLN: { value: new THREE.Vector3(0, -1, 0) }, uArea: { value: 1 }, uMode: { value: 0 }, uBeam: { value: 0 },
        uBandA: { value: new THREE.Vector4() }, uBandB: { value: new THREE.Vector4() }, uBandC: { value: new THREE.Vector4() }, uBandOn: { value: 0 },
        uGobo: { value: new THREE.Vector4() }, uGoboRS: { value: new THREE.Vector2() }, uGoboOn: { value: 0 } },
    });
    const tri = new THREE.BufferGeometry();
    tri.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
    tri.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
    this.quad = new THREE.Mesh(tri, this.mat); this.quad.frustumCulled = false;
    this.qScene = new THREE.Scene(); this.qScene.add(this.quad);
    this.qCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    this.cam = new THREE.PerspectiveCamera(30, 1, 0.5, 100);
    this.cam.layers.set(3);                         // CARS: the body, wheels, glass, wing (not the studio)
    this.samples = []; this.done = 0;
    this.extent = EXTENT;
  }
  get texture() { return this.rt.texture; }
  get rect() { return new THREE.Vector4(0, 0, EXTENT, 0); }

  /** rects: lightRects(preset); ambient: [r,g,b] dome radiance; nDome: AO samples */
  start(rects, ambient, nDome = 192, scale = 1) {
    const list = [];
    for (const r of rects) {
      const n = Math.max(8, Math.round(r.count * scale));
      const g = Math.max(1, Math.round(Math.sqrt(n * (r.w / r.h))));      // grid cells across x / y
      const gy = Math.max(1, Math.round(n / g));
      const total = g * gy, A = 4 * r.ax.length() * r.ay.length();
      for (let b = 0; b < gy; b++) for (let a = 0; a < g; a++) {
        const k = list.length;
        const u = ((a + hash(k * 2)) / g) * 2 - 1, v = ((b + hash(k * 2 + 1)) / gy) * 2 - 1;
        const pos = r.c.clone().addScaledVector(r.ax, u).addScaledVector(r.ay, v);
        list.push({ mode: 0, pos, col: r.L.clone().multiplyScalar(r.kF ?? 1).divideScalar(total), n: r.n, area: A, beam: r.beam, gobo: r.gobo ?? null, band: r.band ?? null });
      }
    }
    if (ambient && (ambient[0] + ambient[1] + ambient[2]) > 0) {
      const phi = Math.PI * (3 - Math.sqrt(5));
      for (let i = 0; i < nDome; i++) {
        const yv = (i + 0.5) / nDome;                      // cosine-weighted hemisphere: y = sqrt(1 - u)
        const cy = Math.sqrt(yv), sy = Math.sqrt(1 - yv), a = i * phi;
        const dir = new THREE.Vector3(Math.cos(a) * sy, cy, Math.sin(a) * sy);
        list.push({ mode: 1, pos: dir.multiplyScalar(60), col: new THREE.Vector3(...ambient).multiplyScalar(Math.PI / nDome), n: new THREE.Vector3(0, -1, 0), area: 1, beam: 0 });
      }
    }
    this.samples = list; this.done = 0;
    this.r.setRenderTarget(this.rt); const ca = this.r.getClearAlpha(), cc = new THREE.Color(); this.r.getClearColor(cc);
    this.r.setClearColor(0x000000, 0); this.r.clear(true, false, false); this.r.setClearColor(cc, ca);
    this.r.setRenderTarget(null);
    return list.length;
  }

  get progress() { return this.samples.length ? this.done / this.samples.length : 1; }
  get finished() { return this.done >= this.samples.length; }

  /** process samples until `ms` have passed (or all are done). `scene` holds the car (layer 3) and nothing else on that layer. */
  step(scene, ms = 8, center = new THREE.Vector3(0, 0.6, 0)) {
    if (this.finished) return true;
    const r = this.r, t0 = performance.now();
    const old = { rt: r.getRenderTarget(), om: scene.overrideMaterial, bg: scene.background, ac: r.autoClear };
    const cc = new THREE.Color(); r.getClearColor(cc); const ca = r.getClearAlpha();
    const cam = this.cam, U = this.mat.uniforms;
    while (this.done < this.samples.length && (performance.now() - t0) < ms) {
      const s = this.samples[this.done++];
      // distance map of the car from the sample point
      const dist = s.pos.distanceTo(center);
      cam.position.copy(s.pos); cam.up.set(0, 1, 0); if (Math.abs(s.pos.clone().sub(center).normalize().y) > 0.98) cam.up.set(0, 0, -1);
      cam.lookAt(center);
      cam.fov = THREE.MathUtils.radToDeg(2 * Math.asin(Math.min(0.99, 3.3 / Math.max(dist, 3.4)))) + 1.0;
      cam.near = Math.max(0.3, dist - 4.0); cam.far = dist + 4.0; cam.aspect = 1;
      cam.updateProjectionMatrix(); cam.updateMatrixWorld(true);
      this.distMat.uniforms.uLP.value.copy(s.pos);
      scene.overrideMaterial = this.distMat; scene.background = null;
      r.setRenderTarget(this.dist); r.setClearColor(0x000000, 0); r.autoClear = true;
      r.render(scene, cam);
      // add this sample's lit floor
      U.uLVP.value.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
      U.uLPos.value.copy(s.pos); U.uCol.value.copy(s.col); U.uLN.value.copy(s.n); U.uArea.value = s.area; U.uMode.value = s.mode; U.uBeam.value = s.beam;
      const bd = s.band; U.uBandOn.value = bd ? 1 : 0;
      if (bd) { const nl = Math.hypot(bd.n[0], bd.n[1]); U.uBandA.value.set(bd.p0[0], bd.p0[1], bd.n[0] / nl, bd.n[1] / nl); U.uBandB.value.set(bd.width, bd.edge ?? 0.06, bd.farSoft ?? 3, bd.fall ?? 1e4); U.uBandC.value.set(bd.u0, bd.u1, bd.endSoft ?? 3, bd.endGrad ?? 0); }
      const g = s.gobo; U.uGoboOn.value = g ? 1 : 0; if (g) { U.uGobo.value.set(g.c[0], g.c[1], g.r[0], g.r[1]); U.uGoboRS.value.set(THREE.MathUtils.degToRad(g.rot ?? 0), g.soft ?? 1); }
      scene.overrideMaterial = old.om;
      r.setRenderTarget(this.rt); r.autoClear = false;
      r.render(this.qScene, this.qCam);
    }
    scene.overrideMaterial = old.om; scene.background = old.bg;
    r.setRenderTarget(old.rt); r.autoClear = old.ac; r.setClearColor(cc, ca);
    return this.finished;
  }

  dispose() { this.rt.dispose(); this.dist.dispose(); this.mat.dispose(); this.distMat.dispose(); }
}
