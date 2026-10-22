// Giant holograms: a swimming koi (lofted body, travelling-wave swim in the vertex shader) circling above a plaza,
// and a rotating ring-sigil crowning the landmark needle. Additive, scan-lined, flickering, fog-attenuated.
import * as THREE from 'three';
import { kUniforms, KGLSL } from './atmosphere.js';

const KOI_VERT = /* glsl */`
attribute vec4 aP;      // s (0 head .. 1.25 tail tip), angle, kind (0 body,1 tail,2 dorsal,3 pectoral), side
uniform float uLen;
varying vec3 vN; varying vec3 vRay; varying vec4 vP; varying float vWorldY;
${KGLSL}
void main() {
  float s = aP.x, ang = aP.y, kind = aP.z;
  vec3 p = position;
  float t = uK1.x;
  // travelling wave: amplitude grows toward the tail
  float amp = 0.035 * (0.15 + 1.6 * s * s);
  float wave = sin(s * 7.0 - t * 2.6) * amp;
  p.z += wave;
  if (kind > 2.5) p.y += sin(t * 2.6 + aP.w * 1.5) * 0.02 * aP.w;       // pectoral flap
  if (kind > 0.5 && kind < 1.5) p.z += sin(s * 7.0 - t * 2.6 + 0.8) * 0.02;
  vec3 wp = (modelMatrix * vec4(p * uLen, 1.0)).xyz;
  gl_Position = projectionMatrix * viewMatrix * vec4(wp, 1.0);
  vN = normalize(mat3(modelMatrix) * normal);
  vRay = wp - cameraPosition; vP = aP; vWorldY = wp.y;
}`;
const KOI_FRAG = /* glsl */`
varying vec3 vN; varying vec3 vRay; varying vec4 vP; varying float vWorldY;
${KGLSL}
void main() {
  vec3 V = normalize(-vRay), N = normalize(vN);
  float rim = pow(1.0 - abs(dot(N, V)), 1.7);
  float t = uK1.x;
  float scan = 0.5 + 0.5 * sin(vWorldY * 1.7 + vP.x * 6.0 - t * 7.0);
  float line = step(0.965, fract(vWorldY * 0.30 - t * 0.5));
  // kohaku-style patches: cyan body, magenta patches
  float pn = sin(vP.x * 11.0 + sin(vP.y * 2.0) * 1.5) * sin(vP.x * 5.0 - vP.y * 3.0 + 1.3) + 0.5 * sin(vP.x * 23.0 + vP.y * 5.0);
  float pat = smoothstep(0.15, 0.45, pn);
  vec3 cA = vec3(0.10, 0.85, 1.0), cB = vec3(1.0, 0.18, 0.55);
  vec3 base = mix(cA, cB, pat);
  vec2 q = vec2(vP.x * 28.0, vP.y * 5.0 + vP.x * 3.0);
  vec2 g = abs(fract(q) - 0.5);
  float scales = smoothstep(0.38, 0.5, g.x + g.y);
  float body = vP.z < 0.5 ? 1.0 : 0.0;
  float flick = 0.9 + 0.1 * sin(t * 23.0) * step(0.8, fract(sin(floor(t * 8.0) * 91.3) * 437.5));
  float a = 0.05 + 0.95 * rim + 0.30 * scales * body + 0.30 * scan * rim + line * 0.5;
  a *= (vP.z > 0.5 && vP.z < 1.5) ? 0.75 : 1.0;
  vec3 c = base * a * flick * 0.78 + vec3(0.9, 0.95, 1.0) * rim * rim * rim * 0.25;
  gl_FragColor = vec4(c * kFogT(vRay), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

function koiGeometry() {
  const P = [], N = [], A = [], I = [];
  const rings = 34, seg = 14;
  const radius = (s) => 0.064 * Math.pow(Math.sin(Math.PI * Math.pow(Math.min(s, 1), 0.52)), 0.9) * (1 - 0.62 * s) + 0.006;
  for (let i = 0; i <= rings; i++) {
    const s = i / rings, x = (0.5 - s) * 1.0, r = radius(s);
    for (let j = 0; j <= seg; j++) {
      const a = (j / seg) * Math.PI * 2;
      const y = Math.cos(a) * r * 0.85, z = Math.sin(a) * r * 0.75;
      P.push(x, y, z); N.push(0, Math.cos(a), Math.sin(a)); A.push(s, a, 0, 0);
    }
  }
  const row = seg + 1;
  for (let i = 0; i < rings; i++) for (let j = 0; j < seg; j++) { const a = i * row + j, b = a + row; I.push(a, b, a + 1, a + 1, b, b + 1); }
  // tail fin (two lobes), beyond s = 1
  const tb = P.length / 3;
  const tailPts = [[-0.5, 0, 0], [-0.5 - 0.20, 0.15, 0], [-0.5 - 0.12, 0.04, 0], [-0.5 - 0.27, 0.0, 0], [-0.5 - 0.12, -0.04, 0], [-0.5 - 0.20, -0.15, 0]];
  for (const [x, y, z] of tailPts) { P.push(x, y, z); N.push(0, 0, 1); A.push(1 + (-0.5 - x) * 1.0, 0, 1, 0); }
  I.push(tb, tb + 1, tb + 2, tb, tb + 2, tb + 3, tb, tb + 3, tb + 4, tb, tb + 4, tb + 5);
  // dorsal fin
  const db = P.length / 3, nd = 8;
  for (let i = 0; i <= nd; i++) {
    const s = 0.26 + (0.42 * i) / nd, h = 0.034 * Math.pow(Math.sin((Math.PI * i) / nd), 0.8);
    P.push(0.5 - s, radius(s) * 0.85, 0); N.push(0, 1, 0); A.push(s, 0, 2, 0);
    P.push(0.5 - s - 0.03, radius(s) * 0.85 + h, 0); N.push(0, 1, 0); A.push(s, 0, 2, 0);
  }
  for (let i = 0; i < nd; i++) { const a = db + i * 2; I.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
  // pectoral fins
  for (const side of [-1, 1]) {
    const pb = P.length / 3;
    const s0 = 0.2;
    const pts = [[0.5 - s0, -0.03, side * 0.05], [0.5 - s0 - 0.10, -0.06, side * 0.17], [0.5 - s0 - 0.20, -0.045, side * 0.12], [0.5 - s0 - 0.13, -0.02, side * 0.045]];
    for (const [x, y, z] of pts) { P.push(x, y, z); N.push(0, 1, 0); A.push(s0 + 0.05, 0, 3, side); }
    I.push(pb, pb + 1, pb + 2, pb, pb + 2, pb + 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
  g.setAttribute('aP', new THREE.Float32BufferAttribute(A, 4)); g.setIndex(I);
  return g;
}

const RING_VERT = /* glsl */`
varying vec3 vN; varying vec3 vRay; varying vec2 vUv; varying float vWY;
${KGLSL}
uniform vec4 uRing;      // centre xyz, radius
void main() {
  float t = uK1.x;
  float ang = atan(position.z, position.x);
  vec3 p = position;
  vec3 wp = vec3(uRing.x, uRing.y, uRing.z) + p * uRing.w;
  gl_Position = projectionMatrix * viewMatrix * vec4(wp, 1.0);
  vN = normal; vRay = wp - cameraPosition; vUv = uv; vWY = wp.y;
}`;
const RING_FRAG = /* glsl */`
varying vec3 vN; varying vec3 vRay; varying vec2 vUv; varying float vWY;
uniform float uHue;
${KGLSL}
void main() {
  float t = uK1.x;
  vec3 V = normalize(-vRay);
  float scan = 0.55 + 0.45 * sin(vWY * 2.3 - t * 8.0);
  float seg = step(0.15, fract(vUv.x * 36.0 - t * 0.5)) ;
  vec3 c = mix(vec3(0.1, 0.9, 1.0), vec3(1.0, 0.25, 0.8), 0.5 + 0.5 * sin(vUv.x * 6.28 + t * 0.7 + uHue));
  float flick = 0.9 + 0.1 * sin(t * 31.0);
  gl_FragColor = vec4(c * scan * seg * flick * 1.15 * kFogT(vRay), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function createHolograms() {
  const group = new THREE.Group(); group.name = 'K-holograms';
  // --- koi ---
  const koiMat = new THREE.ShaderMaterial({ vertexShader: KOI_VERT, fragmentShader: KOI_FRAG, uniforms: { ...kUniforms(), uLen: { value: 210 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
  const koi = new THREE.Mesh(koiGeometry(), koiMat); koi.frustumCulled = false; koi.renderOrder = 12; koi.name = 'K-koi';
  const koiGroup = new THREE.Group(); koiGroup.add(koi); group.add(koiGroup);
  const orbit = { cx: -260, cz: -1150, r: 230, alt: 250, speed: 0.045 };
  // --- ring sigil above the first needle ---
  const rings = [];
  const ringGeo = new THREE.TorusGeometry(1, 0.035, 8, 96);
  for (let k = 0; k < 3; k++) {
    const m = new THREE.ShaderMaterial({ vertexShader: RING_VERT, fragmentShader: RING_FRAG, uniforms: { ...kUniforms(), uRing: { value: new THREE.Vector4(-70, 640 + k * 26, -1700, 36 + k * 9) }, uHue: { value: k * 2 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
    const mesh = new THREE.Mesh(ringGeo, m); mesh.frustumCulled = false; mesh.renderOrder = 12; mesh.rotation.x = Math.PI / 2;
    // the shader positions in world space ignoring the object transform; rotate via geometry copy instead
    const g = ringGeo.clone(); g.rotateX(Math.PI / 2); mesh.geometry = g;
    rings.push(mesh); group.add(mesh);
  }
  return {
    group, orbit,
    update(dt, t) {
      const a = t * orbit.speed;
      const x = orbit.cx + Math.cos(a) * orbit.r, z = orbit.cz + Math.sin(a) * orbit.r;
      koiGroup.position.set(x, orbit.alt + Math.sin(t * 0.13) * 22, z);
      koiGroup.rotation.y = Math.atan2(Math.cos(a), Math.sin(a)) + Math.PI;   // head along the direction of travel
      koiGroup.rotation.z = Math.sin(t * 0.13) * 0.12;
    },
  };
}
