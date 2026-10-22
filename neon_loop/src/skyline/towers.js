// Tower layers: turns the lot plan into a handful of instanced meshes sharing the façade material,
// plus red aircraft-warning beacons (instanced billboards, blinking in sync groups).
import * as THREE from 'three';
import { createFacadeMaterial, makeBoxGeometry, makePrismGeometry, makeSphereGeometry, makeWedgeGeometry } from './facade.js';
import { KGLSL, kUniforms } from './atmosphere.js';
import { mulberry32, lerp, clamp } from './util.js';

const TINTS = [
  [[1.0, 0.68, 0.38], [1.0, 0.58, 0.28]],           // 0 warm
  [[0.55, 0.85, 1.0], [0.35, 0.95, 0.9]],           // 1 cool teal
  [[1.0, 0.45, 0.85], [0.7, 0.5, 1.0]],             // 2 magenta / violet
];
const SCALE = [1, 1.6, 2.5, 4.2];                    // window-module scale per level

/** Accumulates instances per geometry kind. */
export class InstanceSet {
  constructor() { this.kinds = { box: [], cyl: [], oct: [], sph: [], wedge: [] }; }
  add(kind, x, y, z, w, h, d, yaw, style, lit, fh, mw, tint, seed) {
    this.kinds[kind].push(x, y, z, w, h, d, yaw, style, lit, fh, mw, tint[0], tint[1], tint[2], seed);
  }
  get count() { return (this.kinds.box.length + this.kinds.cyl.length + this.kinds.oct.length + this.kinds.sph.length + this.kinds.wedge.length) / 15; }
}
const F = 15;

export function buildInstancedMeshes(set, material, name) {
  const geos = { box: makeBoxGeometry(), cyl: makePrismGeometry(20, true), oct: makePrismGeometry(8, false), sph: makeSphereGeometry(), wedge: makeWedgeGeometry(0.2) };
  const meshes = [];
  for (const kind of ['box', 'cyl', 'oct', 'sph', 'wedge']) {
    const a = set.kinds[kind], n = a.length / F;
    if (!n) continue;
    const g = geos[kind].clone();
    const mats = new Float32Array(n * 16), st = new Float32Array(n * 4), ti = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) {
      const o = i * F, x = a[o], y = a[o + 1], z = a[o + 2], w = a[o + 3], h = a[o + 4], d = a[o + 5], yaw = a[o + 6];
      const c = Math.cos(yaw), s = Math.sin(yaw), m = i * 16;
      mats[m] = c * w; mats[m + 1] = 0; mats[m + 2] = -s * w; mats[m + 3] = 0;
      mats[m + 4] = 0; mats[m + 5] = h; mats[m + 6] = 0; mats[m + 7] = 0;
      mats[m + 8] = s * d; mats[m + 9] = 0; mats[m + 10] = c * d; mats[m + 11] = 0;
      mats[m + 12] = x; mats[m + 13] = y; mats[m + 14] = z; mats[m + 15] = 1;
      st[i * 4] = a[o + 7]; st[i * 4 + 1] = a[o + 8]; st[i * 4 + 2] = a[o + 9]; st[i * 4 + 3] = a[o + 10];
      ti[i * 4] = a[o + 11]; ti[i * 4 + 1] = a[o + 12]; ti[i * 4 + 2] = a[o + 13]; ti[i * 4 + 3] = a[o + 14];
    }
    g.setAttribute('aStyle', new THREE.InstancedBufferAttribute(st, 4));
    g.setAttribute('aTint', new THREE.InstancedBufferAttribute(ti, 4));
    const im = new THREE.InstancedMesh(g, material, n);
    im.instanceMatrix = new THREE.InstancedBufferAttribute(mats, 16);
    im.frustumCulled = false; im.name = `${name}-${kind}`;
    meshes.push(im);
  }
  return meshes;
}

function pickStyle(r, level, H) {
  const u = r();
  if (H < 48) return u < 0.55 ? 4 : 1;
  if (u < 0.30) return 0;
  if (u < 0.56) return 1;
  if (u < 0.78) return 2;
  if (u < 0.78 + (H > 120 ? 0.06 : 0.0)) return 3;
  return u < 0.9 ? 0 : 4;
}

/** Emit all pieces of one lot into `set`; push beacons into `beacons` ([x,y,z,size,phase,steady]). */
export function emitLot(lot, set, beacons, screens) {
  const r = mulberry32(lot.seed);
  const { x, z, level } = lot; let { w, d, h } = lot;
  const sc = SCALE[level];
  let style = lot.style ?? pickStyle(r, level, h);
  const theme = lot.theme === 3 ? Math.floor(r() * 3) : lot.theme;
  const tint = TINTS[theme][r() < 0.7 ? 0 : 1];
  const kindU = r();
  let kind = kindU < 0.66 ? 'box' : kindU < 0.80 ? 'oct' : 'cyl';
  if (kind !== 'box') { const m = Math.min(w, d); w = d = m; }
  const yaw = level >= 2 && r() < 0.4 ? (r() - 0.5) * 0.7 : 0;
  const base = -4;      // sink below the ground so there is never a seam
  const litBase = lot.lit ?? (style === 0 ? 0.14 : style === 1 ? 0.18 : style === 2 ? 0.07 : 0.1);
  const lit = clamp(litBase * (0.5 + r() * 1.3), 0.04, 0.55);
  const fhOf = (s) => (s === 1 ? 3.2 : 3.9) * Math.sqrt(sc) * (s === 6 ? 1.6 : 1);
  const mwOf = (s) => (s === 0 || s === 2 ? 1.6 : 3.2) * sc;
  const fh = fhOf(style), mw = mwOf(style);
  const seed = r() * 100;
  // tiers
  const tall = h > 110;
  const nT = tall ? (r() < 0.45 ? 1 : r() < 0.6 ? 2 : 3) : 1;
  let y0 = base, wCur = w, dCur = d, hLeft = h - base;
  let topY = h;
  // ~13% of tall single-tier boxes get a slanted roof (own RNG stream so the rest of the plan is unchanged)
  const rw = mulberry32((lot.seed ^ 0x9e3779b1) >>> 0);
  const isWedge = nT === 1 && kind === 'box' && h > 115 && level <= 2 && rw() < 0.13;
  let wedgeBack = [0, 0];
  if (isWedge) {
    const k = Math.floor(rw() * 4), yw = yaw + k * Math.PI * 0.5, odd = k & 1;
    set.add('wedge', x, y0, z, odd ? d : w, h - base, odd ? w : d, yw, style, lit, fh, mw, tint, seed);
    wedgeBack = [-Math.sin(yw), -Math.cos(yw)];                       // world direction of the high (back) edge
    const dEff = odd ? w : d;
    wedgeBack = [wedgeBack[0] * dEff * 0.38, wedgeBack[1] * dEff * 0.38];
  } else if (nT === 1) {
    set.add(kind, x, y0, z, w, h - base, d, yaw, style, lit, fh, mw, tint, seed);
  } else {
    const fr = nT === 2 ? [0.62, 1] : [0.45, 0.78, 1];
    let prev = base;
    for (let t = 0; t < nT; t++) {
      const top = fr[t] * h;
      const shrink = Math.pow(lerp(0.66, 0.84, r()), t);
      const tw = w * shrink, td = d * shrink;
      const ox = t ? (r() - 0.5) * (w - tw) * 0.7 : 0, oz = t ? (r() - 0.5) * (d - td) * 0.7 : 0;
      const ts = t && r() < 0.3 ? (style === 3 ? 2 : 3) : style;     // crowns of a different character
      set.add(kind, x + ox, prev, z + oz, tw, top - prev, td, yaw, ts === 3 && t === 0 ? style : ts, lit, fhOf(ts), mwOf(ts), tint, seed + t * 3.7);
      prev = top - 2;
    }
  }
  // giant LED screen on the face that looks towards the track
  const top0 = nT === 1 ? h : h * (nT === 2 ? 0.62 : 0.45);
  if (screens && kind === 'box' && yaw === 0 && level <= 1 && top0 > 110 && r() < 0.24) {
    const dxh = 50 - x, dzh = 80 - z, alongX = Math.abs(dxh) > Math.abs(dzh);
    const nx = alongX ? Math.sign(dxh) : 0, nz = alongX ? 0 : Math.sign(dzh), faceW = alongX ? d : w;
    const portrait = r() < 0.4;
    const sw = portrait ? Math.min(faceW * 0.45, 24 * sc) : faceW * 0.72, sh = portrait ? Math.min((top0 - 50) * 0.8, sw * 3.4) : sw * 0.5;
    const yb = 42 + r() * Math.max(0, top0 - 50 - sh);
    if (sh > 8 && yb + sh < top0 - 4) screens.push({ x: x + nx * (w / 2), y: yb, z: z + nz * (d / 2), nx, nz, w: sw, h: sh, panel: Math.floor(r() * 16), bright: 1.4 + r() * 1.0, phase: r() });
  }
  // podium with shops at street level
  if (h > 120 && level <= 1 && r() < 0.8) {
    const pw = Math.min(w * 1.4, lot.cell * 0.94), pd = Math.min(d * 1.4, lot.cell * 0.94);
    set.add('box', x, base, z, pw, 20 + r() * 16 - base, pd, yaw, 4, 0.35, fhOf(4), mwOf(4), tint, seed + 9.1);
  }
  // roof structure + antenna
  const ox = (r() - 0.5) * w * 0.3, oz = (r() - 0.5) * d * 0.3;
  if (r() < 0.6) {
    const rh = lerp(4, 12, r()) * Math.sqrt(sc);
    if (!isWedge) { set.add('box', x + ox, h - 1, z + oz, w * 0.42, rh + 1, d * 0.42, yaw, 5, 0, 1, 1, tint, seed); topY = h + rh; }
  }
  if (h > 140 && r() < 0.55) {
    const mh = h * lerp(0.05, 0.16, r()), mt = Math.max(1.2, 0.9 * sc);
    if (isWedge) set.add('box', x + wedgeBack[0], h - 1, z + wedgeBack[1], mt, mh + 1, mt, 0, 5, 0, 1, 1, tint, seed);
    else set.add('box', x + ox * 0.5, topY - 1, z + oz * 0.5, mt, mh + 1, mt, 0, 5, 0, 1, 1, tint, seed);
    topY += mh;
  }
  if (h > 100 && beacons) {
    const cnt = h > 250 && w > 40 ? 4 : 1;
    const steady = r() < 0.25;
    const phase = Math.floor(r() * 6) / 6;
    for (let k = 0; k < cnt; k++) {
      let bx = cnt === 1 ? x + ox * 0.5 : x + (k & 1 ? 1 : -1) * w * 0.42, bz = cnt === 1 ? z + oz * 0.5 : z + (k & 2 ? 1 : -1) * d * 0.42;
      if (isWedge) { bx = x + wedgeBack[0]; bz = z + wedgeBack[1]; if (k > 0) continue; }
      beacons.push(bx, cnt === 1 ? topY + 1.5 : h + 1.2, bz, 3 + sc * 2.5, phase, steady ? 1 : 0, 1.0);
    }
  }
  return { topY };
}

// ---------- beacons ----------
const BEACON_VERT = /* glsl */`
attribute vec4 aPosSize;   // xyz, size (m)
attribute vec4 aParam;     // x phase, y steady, z intensity, w colour (0 red, 1 white, 2 green, 3 cyan)
varying vec2 vQ;
varying vec3 vRay;
varying vec4 vP;
void main() {
  vec4 mv = viewMatrix * vec4(aPosSize.xyz, 1.0);
  float dist = length(mv.xyz);
  float size = max(aPosSize.w, dist * 0.0036);
  mv.xy += position.xy * size;
  gl_Position = projectionMatrix * mv;
  vQ = position.xy * 2.0;
  vRay = aPosSize.xyz - cameraPosition;
  vP = aParam;
}`;
const BEACON_FRAG = /* glsl */`
varying vec2 vQ; varying vec3 vRay; varying vec4 vP;
${KGLSL}
void main() {
  float r2 = dot(vQ, vQ);
  if (r2 > 1.0) discard;
  float t = uK1.x;
  float ph = fract(t / 1.8 + vP.x);
  float flash = smoothstep(0.0, 0.04, ph) * (1.0 - smoothstep(0.20, 0.30, ph));
  float on = mix(flash, 0.75 + 0.25 * sin(t * 2.0 + vP.x * 20.0), vP.y);
  float core = exp(-r2 * 14.0), halo = 0.07 / (0.12 + r2 * 3.0);
  vec3 c = vP.w < 0.5 ? vec3(1.0, 0.04, 0.02) : vP.w < 1.5 ? vec3(1.0, 0.92, 0.85) : vP.w < 2.5 ? vec3(0.1, 1.0, 0.2) : vec3(0.1, 0.8, 1.0);
  float T = kFogT(vRay);
  float vis = mix(T, 1.0, 0.18);       // beacons stay readable through the haze
  gl_FragColor = vec4(c * (core * 14.0 + halo * 2.0) * on * vP.z * vis * (1.0 - r2), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function createBeaconMesh(data, name = 'K-beacons') {
  const n = data.length / 7;
  const g = new THREE.InstancedBufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute([-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0], 3));
  g.setIndex([0, 1, 2, 0, 2, 3]);
  const ps = new Float32Array(n * 4), pr = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    const o = i * 7;
    ps[i * 4] = data[o]; ps[i * 4 + 1] = data[o + 1]; ps[i * 4 + 2] = data[o + 2]; ps[i * 4 + 3] = data[o + 3];
    pr[i * 4] = data[o + 4]; pr[i * 4 + 1] = data[o + 5]; pr[i * 4 + 2] = data[o + 6]; pr[i * 4 + 3] = 0;   // colour channel: 0 = aircraft red
  }
  g.setAttribute('aPosSize', new THREE.InstancedBufferAttribute(ps, 4));
  g.setAttribute('aParam', new THREE.InstancedBufferAttribute(pr, 4));
  g.instanceCount = n;
  const m = new THREE.ShaderMaterial({
    vertexShader: BEACON_VERT, fragmentShader: BEACON_FRAG, uniforms: kUniforms(),
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
  });
  const mesh = new THREE.Mesh(g, m);
  mesh.frustumCulled = false; mesh.name = name; mesh.renderOrder = 10;
  return mesh;
}
export { createFacadeMaterial };
