// Cold-gas thruster jets: four translucent plumes from the gold nozzles in the diffuser (the Roadster's SpaceX package).
// Nothing burns: compressed air leaves the nozzles under-expanded, so the plume is a pale blue-white core with a few shock
// diamonds at the exit that widens and thins into the wake. Rendered as a volume: each jet is a capped cylinder drawn by
// its back faces (one fragment per covered pixel), and the fragment integrates a Gaussian density tube along the view ray,
// windowed around the ray's closest approach to the jet axis so a thin core is never stepped over. Additive light, the car
// pass's coverage alpha is left alone. Brightness mixes the peak density on the ray (view-independent: the core reads the
// same from the side as end-on) with a little of the integral (a column seen down its axis is denser). 4 hulls, 1 draw call.
import * as THREE from 'three';

// nozzle exits in the car frame (−Z forward, +X right, +Y up): see tools/blender/regions/rear.py JET_Y / JET_Z (0.578: r81 / 012 ring centres) / JET_X (2.318 = the lip face; exit plane 2 cm behind it)
export const JET_EXITS = [-0.405, -0.135, 0.135, 0.405].map(x => new THREE.Vector3(x, 0.578, 2.338));      // JET_X 2.318 (round 2: the rings are recessed under the crossbeam) + 2 cm
const Z0 = 2.346, LEN = 1.9, HULL_R = 0.34, SIDES = 14;

let GEO = null;
function hullGeometry() {
  if (GEO) return GEO;
  const pos = [], cen = [], idx = [];
  for (const e of JET_EXITS) {
    const base = pos.length / 3;
    for (const z of [Z0, Z0 + LEN]) for (let k = 0; k < SIDES; k++) {
      const a = (k / SIDES) * Math.PI * 2;
      pos.push(e.x + HULL_R * Math.cos(a), e.y + HULL_R * Math.sin(a), z); cen.push(e.x, e.y);
    }
    pos.push(e.x, e.y, Z0, e.x, e.y, Z0 + LEN); cen.push(e.x, e.y, e.x, e.y);
    const c0 = base + 2 * SIDES, c1 = c0 + 1;
    for (let k = 0; k < SIDES; k++) {
      const a = base + k, b = base + (k + 1) % SIDES, c = a + SIDES, d = b + SIDES;
      idx.push(a, b, d, a, d, c);                   // side (outward winding)
      idx.push(c0, b, a, c1, c, d);                 // caps
    }
  }
  GEO = new THREE.BufferGeometry();
  GEO.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  GEO.setAttribute('aC', new THREE.Float32BufferAttribute(cen, 2));
  GEO.setIndex(idx);
  GEO.computeBoundingSphere();
  return GEO;
}

const VERT = /* glsl */`
attribute vec2 aC;
uniform float uLen;
varying vec3 vLP; varying vec3 vCam; varying vec2 vC;
void main() {
  vec3 p = position;
  p.z = ${Z0.toFixed(3)} + (p.z - ${Z0.toFixed(3)}) * uLen / ${LEN.toFixed(3)};
  vLP = p; vC = aC;
  vCam = (inverse(modelMatrix) * vec4(cameraPosition, 1.0)).xyz;
  gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(p, 1.0);
}`;
const FRAG = /* glsl */`
uniform float uJet; uniform float uTime; uniform float uGas; uniform float uLen;
varying vec3 vLP; varying vec3 vCam; varying vec2 vC;
const float Z0 = ${Z0.toFixed(3)}, HR = ${HULL_R.toFixed(3)};
float spread(float z) { return 0.022 + 0.085 * z; }
float dens(vec3 p) {
  float z = p.z - Z0;
  if (z < 0.0 || z > uLen) return 0.0;
  float s = spread(z);
  vec2 d = p.xy - vC;
  float core = exp(-dot(d, d) / (s * s)) * pow(0.022 / s, 1.1);
  float shock = 1.0 + 1.8 * pow(0.5 + 0.5 * cos(z * 78.0 - 0.4), 6.0) * exp(-z * 8.0);     // ~8 cm diamond spacing
  float turb = 0.72 + 0.28 * sin(z * 21.0 - uTime * 64.0 + (d.x - d.y) * 40.0);
  return core * shock * mix(1.0, turb, smoothstep(0.05, 0.4, z)) * smoothstep(uLen, uLen * 0.45, z) * smoothstep(0.0, 0.012, z);
}
void main() {
  vec3 ro = vCam, rd = vLP - vCam;
  float tEnd = length(rd); rd /= tEnd;
  // entry into the hull (infinite cylinder ∩ z slab)
  vec2 oc = ro.xy - vC; float a = dot(rd.xy, rd.xy), b = dot(oc, rd.xy), c = dot(oc, oc) - HR * HR;
  float t0 = 0.0;
  if (a > 1e-6) { float disc = b * b - a * c; if (disc > 0.0) t0 = max(t0, (-b - sqrt(disc)) / a); }
  if (abs(rd.z) > 1e-5) { float za = (Z0 - ro.z) / rd.z, zb = (Z0 + uLen - ro.z) / rd.z; t0 = max(t0, min(za, zb)); }
  float t1 = tEnd;
  // window around the closest approach to the axis: ±3 tube widths
  if (a > 1e-6) {
    float ts = clamp(-b / a, t0, t1);
    float w = 3.2 * spread(clamp(ro.z + rd.z * ts - Z0, 0.0, uLen)) / sqrt(a);
    t0 = max(t0, ts - w); t1 = min(t1, ts + w);
  }
  if (t1 <= t0) discard;
  const int N = 16;
  float dt = (t1 - t0) / float(N);
  float j = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233)) + uTime * 7.1) * 43758.5453);
  float I = 0.0, M = 0.0;
  for (int i = 0; i < N; i++) { float d = dens(ro + rd * (t0 + (float(i) + j) * dt)); I += d; M = max(M, d); }
  I *= dt;
  float k = uJet * (0.5 + 0.5 * smoothstep(0.0, 0.25, uGas));
  float x = (0.8 * M + 2.5 * I) * k;
  float e = 1.0 - exp(-x);
  if (e < 0.003) discard;
  vec3 col = mix(vec3(0.42, 0.64, 1.0), vec3(0.94, 0.98, 1.0), smoothstep(0.4, 1.4, x));
  gl_FragColor = vec4(col * e * 0.9, 0.0);
}`;

/** -> { mesh, update(level, gas, time) }  (mesh is a child of the car visual's object, car frame) */
export function createJets() {
  const U = { uJet: { value: 0 }, uTime: { value: 0 }, uGas: { value: 1 }, uLen: { value: LEN } };
  const mat = new THREE.ShaderMaterial({
    uniforms: U, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, depthTest: true,
    side: THREE.BackSide, toneMapped: false,
    // pure light added to the colour; the car pass keeps its coverage mask in alpha, so alpha is left untouched
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
    blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneFactor,
  });
  const mesh = new THREE.Mesh(hullGeometry(), mat);
  mesh.name = 'ThrusterJets'; mesh.renderOrder = 3; mesh.visible = false;
  return {
    mesh, uniforms: U,
    update(level, gas, time) {
      U.uJet.value = level; U.uGas.value = gas; U.uTime.value = time;
      U.uLen.value = LEN * (0.4 + 0.6 * level);       // the plume grows as the valves open
      mesh.visible = level > 0.01;
    },
    dispose() { mat.dispose(); },
  };
}
