// Flying traffic (GPU-animated craft on collision-free lanes with nav lights + light streaks), searchlight beams
// that stab into the clouds, and slow advertising blimps.
import * as THREE from 'three';
import { KGLSL, kUniforms, makeFogUniforms } from './atmosphere.js';
import { mulberry32 } from './util.js';
import { ATLAS_GLSL } from './ads.js';

// ---------- lot spatial hash (for collision-free lanes) ----------
class LotHash {
  constructor(lots) {
    this.cell = 200; this.map = new Map();
    for (const l of lots) {
      const r = Math.hypot(l.w, l.d) / 2 + 20;
      for (let x = Math.floor((l.x - r) / this.cell); x <= Math.floor((l.x + r) / this.cell); x++)
        for (let z = Math.floor((l.z - r) / this.cell); z <= Math.floor((l.z + r) / this.cell); z++) {
          const k = x * 100003 + z; let a = this.map.get(k); if (!a) this.map.set(k, a = []); a.push(l);
        }
    }
  }
  /** top of anything within `pad` m of (x,z) */
  topAt(x, z, pad = 14) {
    const a = this.map.get(Math.floor(x / this.cell) * 100003 + Math.floor(z / this.cell)); if (!a) return 0;
    let top = 0;
    for (const l of a) if (Math.abs(x - l.x) < l.w / 2 + pad && Math.abs(z - l.z) < l.d / 2 + pad) top = Math.max(top, l.h + 14);
    return top;
  }
}

// ---------- craft ----------
const CRAFT_COMMON = /* glsl */`
attribute vec4 aA;   // lane start xyz, length
attribute vec4 aB;   // dir.x, dir.z, speed, phase
attribute vec4 aC;   // lateral offset, wobble, size, hue
vec3 craftPos(out vec3 fwd, out float fade) {
  float L = aA.w;
  float s = fract(aB.w + uK1.x * aB.z / L);
  vec3 d = vec3(aB.x, 0.0, aB.y);
  vec3 perp = vec3(-aB.y, 0.0, aB.x);
  vec3 p = aA.xyz + d * (s * L) + perp * aC.x;
  p.y += sin(uK1.x * 0.9 + aB.w * 40.0) * aC.y;
  fwd = d;
  fade = smoothstep(0.0, 0.02, s) * smoothstep(1.0, 0.98, s);
  return p;
}
vec3 hueColor(float h) { return clamp(abs(fract(h + vec3(0.0, 0.6667, 0.3333)) * 6.0 - 3.0) - 1.0, 0.0, 1.0); }
`;

const BODY_VERT = /* glsl */`
${KGLSL}
${CRAFT_COMMON}
varying vec3 vN; varying vec3 vC; varying float vUnder;
#include <fog_pars_vertex>
void main() {
  vec3 fwd; float fade; vec3 c = craftPos(fwd, fade);
  vec3 right = vec3(-fwd.z, 0.0, fwd.x);
  float sz = aC.z * fade;
  vec3 wp = c + (right * position.x + vec3(0.0, 1.0, 0.0) * position.y + fwd * position.z) * sz;
  vec4 mvPosition = viewMatrix * vec4(wp, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  vN = right * normal.x + vec3(0.0, 1.0, 0.0) * normal.y + fwd * normal.z;
  vC = hueColor(aC.w);
  vUnder = position.y;
  #include <fog_vertex>
}`;
const BODY_FRAG = /* glsl */`
varying vec3 vN; varying vec3 vC; varying float vUnder;
#include <fog_pars_fragment>
void main() {
  vec3 V = normalize(-vFogRay), N = normalize(vN);
  float fres = 0.05 + 0.95 * pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 4.0);
  vec3 R = reflect(-V, N);
  vec3 sky = kFogColor(normalize(vec3(R.x, abs(R.y) + 0.05, R.z))) * 1.8;
  vec3 col = vec3(0.012, 0.013, 0.018) + sky * fres * 0.7;
  col += vC * 1.6 * smoothstep(-0.2, -0.8, N.y);            // underglow
  gl_FragColor = vec4(col, 1.0);
  #include <fog_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const LIGHT_VERT = /* glsl */`
${KGLSL}
${CRAFT_COMMON}
attribute float aK;
varying vec2 vQ; varying vec3 vRay; varying vec3 vCol; varying float vOn;
void main() {
  vec3 fwd; float fade; vec3 c = craftPos(fwd, fade);
  float sz = aC.z;
  vec3 off = aK < 0.5 ? fwd * 2.4 * sz : aK < 1.5 ? -fwd * 2.4 * sz : aK < 2.5 ? vec3(0.0, 1.1 * sz, 0.0) : vec3(0.0, -0.55 * sz, 0.0);
  vec3 wp = c + off;
  vec4 mv = viewMatrix * vec4(wp, 1.0);
  float dist = length(mv.xyz);
  float size = max(aK < 0.5 ? 1.3 * sz : aK < 2.5 ? 0.8 * sz : 2.2 * sz, dist * 0.0026);
  mv.xy += position.xy * size;
  gl_Position = projectionMatrix * mv;
  vQ = position.xy * 2.0;
  vRay = wp - cameraPosition;
  vec3 hc = hueColor(aC.w);
  vCol = aK < 0.5 ? vec3(1.0, 0.95, 0.85) * 5.0 : aK < 1.5 ? vec3(1.0, 0.05, 0.03) * 4.0 : aK < 2.5 ? vec3(1.0) * 9.0 : hc * 2.2;
  float st = fract(uK1.x * 0.9 + aB.w * 7.0);
  vOn = (aK > 1.5 && aK < 2.5 ? step(st, 0.12) : 1.0) * fade;
}`;
const LIGHT_FRAG = /* glsl */`
varying vec2 vQ; varying vec3 vRay; varying vec3 vCol; varying float vOn;
${KGLSL}
void main() {
  float r2 = dot(vQ, vQ);
  if (r2 > 1.0) discard;
  float g = exp(-r2 * 9.0) + 0.05 / (0.1 + r2 * 4.0);
  float vis = mix(kFogT(vRay), 1.0, 0.10);
  gl_FragColor = vec4(vCol * g * vOn * vis * (1.0 - r2), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const TRAIL_VERT = /* glsl */`
${KGLSL}
${CRAFT_COMMON}
varying float vT; varying vec3 vRay; varying vec3 vCol; varying float vX; varying float vF;
void main() {
  vec3 fwd; float fade; vec3 c = craftPos(fwd, fade);
  float sz = aC.z;
  float len = clamp(aB.z * 0.40, 8.0, 30.0);
  vec3 a = c - fwd * 2.3 * sz, b = a - fwd * len;
  vec3 wp0 = mix(a, b, position.y);
  vec3 toCam = normalize(cameraPosition - wp0);
  vec3 side = normalize(cross(fwd, toCam));
  float dist = distance(cameraPosition, wp0);
  float w = max(0.45 * sz, dist * 0.0012);
  vec3 wp = wp0 + side * position.x * w;
  vec4 mv = viewMatrix * vec4(wp, 1.0);
  gl_Position = projectionMatrix * mv;
  vT = position.y; vX = position.x * 2.0;
  vRay = wp0 - cameraPosition;
  vCol = mix(vec3(1.0, 0.07, 0.04), hueColor(aC.w), step(0.55, fract(aC.w * 5.0 + aB.w))) * 1.6;
  vF = fade * min(1.0, 0.45 * sz / (dist * 0.0012 + 1e-3));
}`;
const TRAIL_FRAG = /* glsl */`
varying float vT; varying vec3 vRay; varying vec3 vCol; varying float vX; varying float vF;
${KGLSL}
void main() {
  float a = pow(1.0 - vT, 1.6) * (1.0 - abs(vX) * abs(vX));
  gl_FragColor = vec4(vCol * a * vF * mix(kFogT(vRay), 1.0, 0.08), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

function craftGeometry() {
  const g = new THREE.BoxGeometry(1.9, 0.75, 4.6, 1, 1, 2);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    let x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    if (z > 2.0) { x *= 0.30; y = y > 0 ? y * 0.25 : y * 0.7; }       // nose
    else if (z < -2.0) { x *= 0.8; }
    else if (y > 0) { y += 0.3; x *= 0.82; }                           // cabin bump
    p.setXYZ(i, x, y, z);
  }
  const ng = g.toNonIndexed(); ng.deleteAttribute('uv'); ng.computeVertexNormals();
  return ng;
}

/**
 * lots: tower lots for collision checks. Returns { group, update }.
 */
export function createTraffic(app, lots, opts = {}) {
  const rng = mulberry32(2024);
  const hash = new LotHash(lots);
  const centre = { x: 50, z: 80 };
  // ---------- lanes ----------
  const lanes = [];
  const wantLanes = opts.lanes ?? 30;
  for (let attempt = 0; attempt < 9000 && lanes.length < wantLanes; attempt++) {
    // mostly axis-aligned "aerial boulevards" along the street lattice, some diagonal
    const axis = rng() < 0.7;
    const th = axis ? (rng() < 0.5 ? 0 : Math.PI / 2) + (rng() - 0.5) * 0.02 : rng() * Math.PI;
    const dx = Math.cos(th), dz = Math.sin(th);
    const b = axis ? Math.round(((rng() - 0.5) * 2800) / 72) * 72 : (rng() - 0.5) * 2600;
    const u = rng();
    const alt = u < 0.55 ? 40 + rng() * 130 : u < 0.85 ? 170 + rng() * 170 : 340 + rng() * 280;
    const L = 8400;
    const sx = centre.x - dz * b - dx * L / 2, sz = centre.z + dx * b - dz * L / 2;
    let ok = true;
    for (let t = 0; t < L && ok; t += 12) {
      const px = sx + dx * t, pz = sz + dz * t;
      if (Math.hypot(px - centre.x, pz - centre.z) > 2600) continue;      // beyond that the fog hides any intersection
      if (hash.topAt(px, pz) > alt - 2) ok = false;
    }
    if (!ok) continue;
    const sign = rng() < 0.5 ? 1 : -1;
    lanes.push({ sx: sign > 0 ? sx : sx + dx * L, sz: sign > 0 ? sz : sz + dz * L, dx: dx * sign, dz: dz * sign, alt, L, speed: 22 + rng() * 42 });
  }
  // ---------- craft instances ----------
  const A = [], B = [], C = [];
  for (const ln of lanes) {
    const n = Math.round(ln.L / (320 + rng() * 520));
    const sub = rng() < 0.5 ? [0] : [-9, 9];
    const hueBase = rng();
    for (let k = 0; k < n; k++) {
      const off = sub[k % sub.length];
      A.push(ln.sx, ln.alt + (rng() - 0.5) * 6, ln.sz, ln.L);
      B.push(ln.dx, ln.dz, ln.speed * (0.9 + rng() * 0.2), (k + rng() * 0.6) / n);
      C.push(off + (rng() - 0.5) * 3, 0.15 + rng() * 0.5, 0.9 + rng() * 0.9, rng() < 0.6 ? 0.5 + rng() * 0.2 : (hueBase + rng() * 0.2) % 1);
    }
  }
  const N = A.length / 4;
  const group = new THREE.Group(); group.name = 'K-traffic';
  const instAttr = (arr, rep = 1) => {
    const out = new Float32Array(arr.length * rep);
    if (rep === 1) out.set(arr); else for (let i = 0; i < arr.length / 4; i++) for (let r = 0; r < rep; r++) out.set(arr.slice(i * 4, i * 4 + 4), (i * rep + r) * 4);
    return new THREE.InstancedBufferAttribute(out, 4);
  };

  // bodies
  const bg = new THREE.InstancedBufferGeometry().copy(craftGeometry());
  bg.setAttribute('aA', instAttr(A)); bg.setAttribute('aB', instAttr(B)); bg.setAttribute('aC', instAttr(C)); bg.instanceCount = N;
  const bodyMat = new THREE.ShaderMaterial({ vertexShader: BODY_VERT, fragmentShader: BODY_FRAG, uniforms: makeFogUniforms(), fog: true });
  const bodies = new THREE.Mesh(bg, bodyMat); bodies.frustumCulled = false; bodies.name = 'K-craft';
  group.add(bodies);

  // lights: 4 billboards per craft
  const quad = [-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0];
  const lg = new THREE.InstancedBufferGeometry();
  lg.setAttribute('position', new THREE.Float32BufferAttribute(quad, 3)); lg.setIndex([0, 1, 2, 0, 2, 3]);
  lg.setAttribute('aA', instAttr(A, 4)); lg.setAttribute('aB', instAttr(B, 4)); lg.setAttribute('aC', instAttr(C, 4));
  const kk = new Float32Array(N * 4); for (let i = 0; i < N * 4; i++) kk[i] = i % 4;
  lg.setAttribute('aK', new THREE.InstancedBufferAttribute(kk, 1)); lg.instanceCount = N * 4;
  const addMat = (v, f, extra = {}) => new THREE.ShaderMaterial({ vertexShader: v, fragmentShader: f, uniforms: kUniforms(), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, ...extra });
  const lightsMesh = new THREE.Mesh(lg, addMat(LIGHT_VERT, LIGHT_FRAG)); lightsMesh.frustumCulled = false; lightsMesh.renderOrder = 11; lightsMesh.name = 'K-craft-lights';
  group.add(lightsMesh);

  // trails
  const tg = new THREE.InstancedBufferGeometry();
  tg.setAttribute('position', new THREE.Float32BufferAttribute([-0.5, 0, 0, 0.5, 0, 0, 0.5, 1, 0, -0.5, 1, 0], 3)); tg.setIndex([0, 1, 2, 0, 2, 3]);
  tg.setAttribute('aA', instAttr(A)); tg.setAttribute('aB', instAttr(B)); tg.setAttribute('aC', instAttr(C)); tg.instanceCount = N;
  const trails = new THREE.Mesh(tg, addMat(TRAIL_VERT, TRAIL_FRAG, { side: THREE.DoubleSide })); trails.frustumCulled = false; trails.renderOrder = 11; trails.name = 'K-craft-trails';
  group.add(trails);

  return { group, lanes, craftCount: N, hash, update() {} };
}

// ---------- searchlights ----------
const BEAM_VERT = /* glsl */`
attribute vec4 aBase;   // xyz base, length
attribute vec4 aDir;    // az0, tilt, azSpeed, radius at the far end
varying float vY; varying vec3 vN; varying vec3 vRay;
${KGLSL}
void main() {
  float az = aDir.x + uK1.x * aDir.z;
  float st = sin(aDir.y), ct = cos(aDir.y);
  vec3 a = vec3(st * cos(az), ct, st * sin(az));
  vec3 u = normalize(cross(a, vec3(0.0, 1.0, 0.0))); vec3 v = cross(a, u);
  vec2 rd = normalize(normal.xz + 1e-5);
  float rad = mix(1.4, aDir.w, position.y);
  vec3 radial = u * rd.x + v * rd.y;
  vec3 wp = aBase.xyz + a * (position.y * aBase.w) + radial * rad;
  vec4 mv = viewMatrix * vec4(wp, 1.0);
  gl_Position = projectionMatrix * mv;
  vY = position.y; vN = radial; vRay = wp - cameraPosition;
}`;
const BEAM_FRAG = /* glsl */`
varying float vY; varying vec3 vN; varying vec3 vRay;
${KGLSL}
void main() {
  vec3 V = normalize(-vRay);
  float f = abs(dot(normalize(vN), V));
  float core = pow(f, 1.8);
  float a = core * pow(1.0 - vY, 1.4) * smoothstep(0.0, 0.03, vY);
  vec3 c = vec3(0.62, 0.82, 1.0) * 0.40;
  gl_FragColor = vec4(c * a * kFogT(vRay) * 1.0, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
const SPOT_VERT = /* glsl */`
attribute vec4 aBase; attribute vec4 aDir;
varying vec2 vQ; varying vec3 vRay;
${KGLSL}
void main() {
  float az = aDir.x + uK1.x * aDir.z;
  float st = sin(aDir.y), ct = cos(aDir.y);
  vec3 a = vec3(st * cos(az), ct, st * sin(az));
  vec3 c = aBase.xyz + a * aBase.w;
  vec4 mv = viewMatrix * vec4(c, 1.0);
  float size = max(aDir.w * 5.0, length(mv.xyz) * 0.01);
  mv.xy += position.xy * size;
  gl_Position = projectionMatrix * mv;
  vQ = position.xy * 2.0; vRay = c - cameraPosition;
}`;
const SPOT_FRAG = /* glsl */`
varying vec2 vQ; varying vec3 vRay;
${KGLSL}
void main() {
  float r2 = dot(vQ, vQ); if (r2 > 1.0) discard;
  float g = exp(-r2 * 4.5);
  gl_FragColor = vec4(vec3(0.62, 0.82, 1.0) * g * 0.45 * mix(kFogT(vRay), 1.0, 0.12), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function createSearchlights(lots, rng = mulberry32(77)) {
  // pick tall towers 900–3000 m from the middle, spread around the compass
  const cand = lots.filter(l => l.h > 190 && l.level >= 1 && Math.hypot(l.x - 50, l.z - 80) > 900 && Math.hypot(l.x - 50, l.z - 80) < 3200);
  const picks = [];
  const sectors = 6;
  for (let s = 0; s < sectors; s++) {
    const inS = cand.filter(l => { const a = (Math.atan2(l.z - 80, l.x - 50) + Math.PI) / (Math.PI * 2); return Math.floor(a * sectors) === s; });
    if (inS.length) picks.push(inS[Math.floor(rng() * inS.length)]);
  }
  const n = picks.length;
  const base = new Float32Array(n * 4), dir = new Float32Array(n * 4);
  picks.forEach((l, i) => {
    base.set([l.x, l.h + 6, l.z, 2100 + rng() * 300], i * 4);
    dir.set([rng() * 6.28, 0.28 + rng() * 0.22, (rng() < 0.5 ? -1 : 1) * (0.05 + rng() * 0.07), 40 + rng() * 25], i * 4);
  });
  const cone = new THREE.CylinderGeometry(1, 1, 1, 14, 1, true); cone.translate(0, 0.5, 0);
  const g = new THREE.InstancedBufferGeometry().copy(cone);
  g.setAttribute('aBase', new THREE.InstancedBufferAttribute(base, 4)); g.setAttribute('aDir', new THREE.InstancedBufferAttribute(dir, 4)); g.instanceCount = n;
  const mat = new THREE.ShaderMaterial({ vertexShader: BEAM_VERT, fragmentShader: BEAM_FRAG, uniforms: kUniforms(), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
  const beams = new THREE.Mesh(g, mat); beams.frustumCulled = false; beams.renderOrder = 9; beams.name = 'K-searchlights';
  const sg = new THREE.InstancedBufferGeometry();
  sg.setAttribute('position', new THREE.Float32BufferAttribute([-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0], 3)); sg.setIndex([0, 1, 2, 0, 2, 3]);
  sg.setAttribute('aBase', g.attributes.aBase); sg.setAttribute('aDir', g.attributes.aDir); sg.instanceCount = n;
  const spots = new THREE.Mesh(sg, new THREE.ShaderMaterial({ vertexShader: SPOT_VERT, fragmentShader: SPOT_FRAG, uniforms: kUniforms(), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
  spots.frustumCulled = false; spots.renderOrder = 9; spots.name = 'K-searchlight-spots';
  const group = new THREE.Group(); group.add(beams, spots); group.name = 'K-searchlights-group';
  return { group, picks };
}

// ---------- blimps ----------
const BLIMP_VERT = /* glsl */`
attribute vec3 aUV;     // u (0..1 along the body), v (0..1 around), kind (0 body, 1 screen)
varying vec3 vN; varying vec3 vP; varying vec2 vUv; varying float vKind; varying vec3 vWp;
#include <fog_pars_vertex>
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vec4 mvPosition = viewMatrix * wp;
  gl_Position = projectionMatrix * mvPosition;
  vN = normalize(mat3(modelMatrix) * normal);
  vP = position; vUv = aUV.xy; vKind = aUV.z; vWp = wp.xyz;
  #include <fog_vertex>
}`;
const BLIMP_FRAG = /* glsl */`
uniform sampler2D tAds; uniform float uPanel;
varying vec3 vN; varying vec3 vP; varying vec2 vUv; varying float vKind; varying vec3 vWp;
#include <fog_pars_fragment>
${ATLAS_GLSL}
void main() {
  vec3 V = normalize(-vFogRay), N = normalize(vN);
  vec3 R = reflect(-V, N);
  float fres = 0.04 + 0.96 * pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 4.0);
  vec3 col;
  if (vKind < 0.5) {
    vec3 up = kHorizon(normalize(N.xz + 1e-4)) * 1.2 * smoothstep(0.2, -0.9, N.y);        // lit from the city below
    col = vec3(0.020, 0.021, 0.026) + up * 2.0 + kFogColor(normalize(vec3(R.x, abs(R.y) + 0.05, R.z))) * fres * 0.8;
    float seam = step(0.5, abs(sin(vUv.x * 60.0))) * 0.0;
    col += vec3(1.0, 0.1, 0.1) * 0.0;
  } else {
    float t = uK1.x;
    float pnl = floor(mod(t / 7.0 + uPanel, 16.0));
    vec2 uv = vec2(vUv.x, vUv.y);
    float glitch = step(0.985, fract(sin(floor(t * 9.0) * 91.7) * 437.58)) * 0.03;
    vec3 ad = adPanel(tAds, pnl, uv + vec2(glitch, 0.0));
    float scan = 0.85 + 0.15 * sin(vUv.y * 300.0 + t * 8.0);
    col = ad * 2.4 * scan;
    col = mix(col, adPanel(tAds, mod(pnl + 1.0, 16.0), uv) * 2.4, smoothstep(6.0, 7.0, mod(t, 7.0)));
  }
  gl_FragColor = vec4(col, 1.0);
  #include <fog_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

function blimpGeometry(L = 92, R = 17) {
  // body: ellipsoid (u along the length, v around), plus a flat LED screen band on both flanks
  const segU = 36, segV = 20;
  const P = [], N = [], UV = [], I = [];
  for (let i = 0; i <= segU; i++) {
    const u = i / segU, ang = (u - 0.5) * Math.PI; const r = Math.cos(ang) * R, x = Math.sin(ang) * L / 2;
    for (let j = 0; j <= segV; j++) {
      const v = j / segV, a = v * Math.PI * 2;
      const y = Math.cos(a) * r, z = Math.sin(a) * r;
      P.push(x, y, z); const n = new THREE.Vector3(Math.sin(ang) * (R / (L / 2)) * 0 + x / (L / 2) * 0.35, y / R, z / R).normalize(); N.push(n.x, n.y, n.z);
      UV.push(u, v, 0);
    }
  }
  const row = segV + 1;
  for (let i = 0; i < segU; i++) for (let j = 0; j < segV; j++) {
    const a = i * row + j, b = a + row;
    I.push(a, a + 1, b, a + 1, b + 1, b);
  }
  // screens: a slightly raised patch on each flank (z = ±), covers u 0.18..0.82, v around the side
  const addScreen = (sign) => {
    const base = P.length / 3, su = 24, sv = 8;
    for (let i = 0; i <= su; i++) {
      const u = 0.17 + (0.66 * i) / su, ang = (u - 0.5) * Math.PI, r = Math.cos(ang) * R * 1.012, x = Math.sin(ang) * L / 2;
      for (let j = 0; j <= sv; j++) {
        const t = j / sv, a = (0.5 + (t - 0.5) * 0.5) * Math.PI * (sign > 0 ? 1 : -1);   // ±(45°..135°) from top
        const y = Math.cos(a) * r, z = Math.sin(a) * r;
        P.push(x, y, z); N.push(0, y / R, z / R); UV.push((i / su), 1 - t, 1);
      }
    }
    const rw = sv + 1;
    for (let i = 0; i < su; i++) for (let j = 0; j < sv; j++) {
      const a = base + i * rw + j, b = a + rw;
      if (sign > 0) I.push(a, a + 1, b, a + 1, b + 1, b); else I.push(a, b, a + 1, a + 1, b, b + 1);
    }
  };
  addScreen(1); addScreen(-1);
  // tail fins + gondola
  const fin = (ax, ay, az, sx, sy, sz) => {
    const base = P.length / 3;
    const h = [[-.5, -.5, -.5], [.5, -.5, -.5], [.5, .5, -.5], [-.5, .5, -.5], [-.5, -.5, .5], [.5, -.5, .5], [.5, .5, .5], [-.5, .5, .5]];
    for (const [x, y, z] of h) { P.push(ax + x * sx, ay + y * sy, az + z * sz); N.push(0, 1, 0); UV.push(0, 0, 0); }
    const f = [[0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [3, 2, 6, 7], [4, 5, 1, 0]];
    for (const q of f) I.push(base + q[0], base + q[1], base + q[2], base + q[0], base + q[2], base + q[3]);
  };
  fin(-L * 0.42, R * 0.9, 0, L * 0.12, R * 1.2, 1.0); fin(-L * 0.42, -R * 0.9, 0, L * 0.12, R * 1.2, 1.0);
  fin(-L * 0.42, 0, R * 0.9, L * 0.12, 1.0, R * 1.2); fin(-L * 0.42, 0, -R * 0.9, L * 0.12, 1.0, R * 1.2);
  fin(4, -R - 2, 0, 18, 4, 6);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
  g.setAttribute('aUV', new THREE.Float32BufferAttribute(UV, 3)); g.setIndex(I);
  return g;
}

export function createBlimps(adTex, lots, rng = mulberry32(31)) {
  const hash = new LotHash(lots);
  const geo = blimpGeometry();
  const group = new THREE.Group(); group.name = 'K-blimps';
  const list = [];
  const specs = [
    { cx: 40, cz: -300, a: 1300, b: 900, alt: 330, speed: 7, ang0: 0.5, panel: 0 },
    { cx: -300, cz: 150, a: 1500, b: 1100, alt: 440, speed: 6, ang0: 3.6, panel: 5 },
    { cx: 300, cz: 400, a: 1000, b: 1400, alt: 280, speed: -5.5, ang0: 2.0, panel: 10 },
  ];
  for (const sp of specs) {
    // lower the orbit until it clears the towers
    let alt = sp.alt;
    for (let tries = 0; tries < 40; tries++) {
      let top = 0;
      for (let k = 0; k < 360; k++) { const an = (k / 360) * Math.PI * 2; top = Math.max(top, hash.topAt(sp.cx + Math.cos(an) * sp.a, sp.cz + Math.sin(an) * sp.b, 40)); }
      if (top + 20 < alt) break; alt = Math.max(alt, top + 40);
      if (alt > 720) break;
    }
    const mat = new THREE.ShaderMaterial({ vertexShader: BLIMP_VERT, fragmentShader: BLIMP_FRAG, fog: true, side: THREE.DoubleSide,
      uniforms: makeFogUniforms({ tAds: { value: adTex }, uPanel: { value: sp.panel } }) });
    const mesh = new THREE.Mesh(geo, mat); mesh.frustumCulled = false; mesh.name = 'K-blimp';
    group.add(mesh); list.push({ mesh, ...sp, alt });
  }
  const update = (dt, t) => {
    for (const b of list) {
      const ang = b.ang0 + (t * b.speed) / ((b.a + b.b) / 2);
      const x = b.cx + Math.cos(ang) * b.a, z = b.cz + Math.sin(ang) * b.b;
      const dx = -Math.sin(ang) * b.a * Math.sign(b.speed), dz = Math.cos(ang) * b.b * Math.sign(b.speed);
      b.mesh.position.set(x, b.alt + Math.sin(t * 0.07 + b.ang0) * 6, z);
      b.mesh.rotation.y = Math.atan2(-dz, dx);       // body length axis is +x
    }
  };
  return { group, update, list };
}
