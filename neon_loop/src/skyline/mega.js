// Hero skyline: landmark towers and megastructures (twisting needle, twin gate with sky-bridge, LED megatower,
// pearl sphere tower, stepped arcology, stacked residential mega-block, broadcast mast, elevated rail + trains,
// cable-stayed bridge). Everything is built from façade instances (one shared material) plus a few tiny custom meshes.
import * as THREE from 'three';
import { mulberry32, lerp } from './util.js';
import { kUniforms, KGLSL } from './atmosphere.js';

const TINT = { warm: [1.0, 0.66, 0.36], cool: [0.55, 0.85, 1.0], mag: [1.0, 0.45, 0.85], vio: [0.7, 0.5, 1.0], teal: [0.35, 0.95, 0.9] };

/** Landmark catalogue: id, centre and the radius reserved (no ordinary lots inside). */
export const LANDMARKS = [
  { id: 'needle', x: -70, z: -1700, r: 80, h: 560, tint: 'cool', seed: 3 },
  { id: 'twin', x: -300, z: -1960, r: 150, h: 440, tint: 'warm', seed: 5 },
  { id: 'led', x: 285, z: -1480, r: 60, h: 410, tint: 'mag', seed: 7 },
  { id: 'pearl', x: 650, z: -2250, r: 110, h: 400, tint: 'vio', seed: 9 },
  { id: 'needle', x: 1750, z: -1450, r: 80, h: 470, tint: 'warm', seed: 11 },
  { id: 'led', x: 2450, z: -850, r: 60, h: 360, tint: 'cool', seed: 13 },
  { id: 'mast', x: 2650, z: 350, r: 70, h: 520, tint: 'warm', seed: 15 },
  { id: 'block', x: 1650, z: 1650, r: 330, h: 330, tint: 'warm', seed: 17 },
  { id: 'pearl', x: 150, z: 2450, r: 110, h: 360, tint: 'teal', seed: 19 },
  { id: 'block', x: -700, z: 1800, r: 340, h: 380, tint: 'mag', seed: 21 },
  { id: 'twin', x: -2050, z: 950, r: 150, h: 400, tint: 'cool', seed: 23 },
  { id: 'arcology', x: -2350, z: -300, r: 560, h: 640, tint: 'warm', seed: 25 },
  { id: 'needle', x: -1850, z: -1550, r: 80, h: 500, tint: 'vio', seed: 27 },
  { id: 'led', x: -1200, z: -2500, r: 60, h: 430, tint: 'teal', seed: 29 },
  { id: 'mast', x: 600, z: 3300, r: 70, h: 460, tint: 'cool', seed: 31 },
  { id: 'arcology', x: 3100, z: -2000, r: 560, h: 520, tint: 'mag', seed: 33 },
];
export const RAILS = [
  { x0: -3400, z0: 1480, x1: 3400, z1: 1480, y: 38 },
  { x0: -1750, z0: -3200, x1: -1750, z1: 3000, y: 52 },
];

export function reservedRects(bounds) {
  const out = LANDMARKS.map(l => ({ x0: l.x - l.r, x1: l.x + l.r, z0: l.z - l.r, z1: l.z + l.r }));
  out.push({ x0: -540, x1: 20, z0: -1430, z1: -870 });                          // hologram plaza
  out.push({ x0: 290, x1: 550, z0: bounds.z0 - 450, z1: bounds.z0 - 310 });   // cable bridge
  for (const R of RAILS) out.push({ x0: Math.min(R.x0, R.x1) - 14, x1: Math.max(R.x0, R.x1) + 14, z0: Math.min(R.z0, R.z1) - 14, z1: Math.max(R.z0, R.z1) + 14 });
  return out;
}

const SINK = -5;

function make(set, beacons) {
  const add = (kind, x, y0, z, w, h, d, yaw, style, lit, fh, mw, tint, seed) => set.add(kind, x, y0, z, w, h, d, yaw, style, lit, fh, mw, tint, seed);
  const beacon = (x, y, z, size, phase = 0, steady = 0, k = 1) => beacons?.push(x, y, z, size, phase, steady, k);
  return { add, beacon };
}

// ---------- recipes ----------
function needle(L, set, beacons) {
  const { add, beacon } = make(set, beacons);
  const t = TINT[L.tint], r = mulberry32(L.seed * 977);
  const H = L.h, n = 11, base = 26;
  add('box', L.x, SINK, L.z, 96, base - SINK, 96, 0, 4, 0.4, 4, 3.2, t, L.seed);
  let y = base, w = 54;
  const seq = [0, 2, 0, 3, 0, 2, 0, 0, 3, 2, 0];
  for (let i = 0; i < n; i++) {
    const hh = (H - base - 60) / n;
    const yaw = i * 0.13;
    const kind = i % 4 === 3 ? 'oct' : 'box';
    add(kind, L.x, y - 2, L.z, w, hh + 2, w, yaw, seq[i], 0.3, 4.2, 1.8, t, L.seed + i * 1.7);
    // vertical LED fins on the corners of every other tier
    if (i % 2 === 0) for (const [sx, sz] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) {
      const c = Math.cos(yaw), s = Math.sin(yaw), ox = sx * w * 0.5, oz = sz * w * 0.5;
      add('box', L.x + ox * c + oz * s, y, L.z - ox * s + oz * c, 1.6, hh, 1.6, yaw, 3, 0, 1, 1, t, L.seed + 40 + i);
    }
    y += hh; w *= 0.915;
  }
  add('box', L.x, y - 2, L.z, w * 0.8, 16, w * 0.8, 0.9, 3, 0, 1, 1, t, L.seed + 90);
  add('box', L.x, y + 12, L.z, 3.4, 56, 3.4, 0, 5, 0, 1, 1, t, 1);
  beacon(L.x, y + 70, L.z, 12, 0.5, 0, 1.4); beacon(L.x, y + 60, L.z + 3, 6, 0.5, 1, 0.5);
  return { top: y + 70 };
}

function twin(L, set, beacons) {
  const { add, beacon } = make(set, beacons);
  const t = TINT[L.tint], H = L.h, gap = 52, w = 58;
  const xs = [L.x - (gap + w) / 2, L.x + (gap + w) / 2];
  add('box', L.x, SINK, L.z, gap + 2 * w + 70, 22 - SINK, w + 60, 0, 4, 0.4, 4, 3.2, t, L.seed);
  xs.forEach((x, k) => {
    const hs = H * (k ? 0.92 : 1);
    add('box', x, 10, L.z, w, hs * 0.58, w, 0, 0, 0.3, 4, 1.7, t, L.seed + k);
    add('box', x, 10 + hs * 0.58 - 2, L.z, w * 0.8, hs * 0.26, w * 0.8, 0.0, 2, 0.15, 4, 1.7, t, L.seed + k + 3);
    add('box', x, 10 + hs * 0.84 - 4, L.z, w * 0.58, hs * 0.16, w * 0.58, 0, 3, 0, 1, 1, t, L.seed + k + 6);
    add('box', x, 10 + hs, L.z, 3, 60, 3, 0, 5, 0, 1, 1, t, 1);
    beacon(x, 10 + hs + 62, L.z, 10, k * 0.5, 0, 1.3);
  });
  // sky-bridges between the towers
  for (const [yy, hh] of [[H * 0.62, 18], [H * 0.34, 12]]) {
    add('box', L.x, yy, L.z, gap + 2, hh, 18, 0, 0, 0.8, 3.6, 1.6, [1, 0.8, 0.55], L.seed + 11);
    add('box', L.x, yy - 1.5, L.z, gap - 4, 1.5, 12, 0, 3, 0, 1, 1, t, L.seed + 12);
  }
  return { top: 10 + H + 60 };
}

function ledTower(L, set, beacons, screens) {
  const { add, beacon } = make(set, beacons);
  const t = TINT[L.tint], H = L.h;
  add('box', L.x, SINK, L.z, 88, 30 - SINK, 88, 0, 4, 0.4, 4, 3.2, t, L.seed);
  add('box', L.x, 24, L.z, 66, H * 0.7, 66, 0, 3, 0, 1, 1, t, L.seed + 1);        // the media body
  add('box', L.x, 24 + H * 0.7 - 2, L.z, 52, H * 0.3, 52, 0.2, 2, 0.12, 4, 1.7, t, L.seed + 2);
  for (const [sx, sz] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) add('box', L.x + sx * 34, 24, L.z + sz * 34, 3, H * 0.7, 3, 0, 7, 0, 1, 1, t, L.seed + 3);
  // giant media screen on the face looking at the track
  {
    const dxh = 50 - L.x, dzh = 80 - L.z, alongX = Math.abs(dxh) > Math.abs(dzh);
    const nx = alongX ? Math.sign(dxh) : 0, nz = alongX ? 0 : Math.sign(dzh);
    screens?.push({ x: L.x + nx * 33, y: 90, z: L.z + nz * 33, nx, nz, w: 52, h: 170, panel: L.seed % 16, bright: 2.4, phase: L.seed * 0.1 });
  }
  add('box', L.x, 22 + H, L.z, 2.6, 70, 2.6, 0, 5, 0, 1, 1, t, 1);
  beacon(L.x, 22 + H + 72, L.z, 11, 0.17, 0, 1.4);
  return { top: 22 + H + 70 };
}

function pearl(L, set, beacons) {
  const { add, beacon } = make(set, beacons);
  const t = TINT[L.tint], H = L.h;
  add('cyl', L.x, SINK, L.z, 64, 12 - SINK, 64, 0, 4, 0.4, 4, 3.2, t, L.seed);
  for (let k = 0; k < 3; k++) {       // tripod legs (vertical slabs)
    const a = (k / 3) * Math.PI * 2 + 0.4;
    add('box', L.x + Math.cos(a) * 20, 5, L.z + Math.sin(a) * 20, 9, H * 0.34, 9, -a, 7, 0, 1, 1, t, L.seed + k);
  }
  const y1 = H * 0.30, d1 = 84;
  add('sph', L.x, y1, L.z, d1, d1, d1, 0, 2, 0.2, 4, 2.4, t, L.seed + 7);
  add('cyl', L.x, y1 + d1 - 4, L.z, 16, H * 0.34, 16, 0, 7, 0, 1, 1, t, L.seed + 8);
  const y2 = y1 + d1 + H * 0.26, d2 = 52;
  add('sph', L.x, y2, L.z, d2, d2, d2, 0, 3, 0, 1, 1, t, L.seed + 9);
  add('cyl', L.x, y2 + d2 - 3, L.z, 8, H * 0.2, 8, 0, 5, 0, 1, 1, t, 1);
  add('box', L.x, y2 + d2 + H * 0.2 - 4, L.z, 2.4, 60, 2.4, 0, 5, 0, 1, 1, t, 1);
  beacon(L.x, y2 + d2 + H * 0.2 + 58, L.z, 10, 0.33, 0, 1.3);
  // glowing equatorial rings
  for (const [yy, dd] of [[y1 + d1 * 0.5 - 1.2, d1 + 3], [y2 + d2 * 0.5 - 1, d2 + 2]]) add('cyl', L.x, yy, L.z, dd, 2.4, dd, 0, 3, 0, 1, 1, t, L.seed + 20);
  return { top: y2 + d2 + H * 0.2 + 60 };
}

function arcology(L, set, beacons) {
  const { add, beacon } = make(set, beacons);
  const t = TINT[L.tint], r = mulberry32(L.seed * 31), H = L.h;
  const tiers = 13, W0 = L.r * 1.55;
  let y = SINK;
  add('box', L.x, SINK, L.z, W0 * 1.12, 26 - SINK, W0 * 0.82, 0, 7, 0, 1, 1, t, L.seed);
  y = 26;
  for (let i = 0; i < tiers; i++) {
    const f = 1 - i / (tiers + 1);
    const w = W0 * Math.pow(f, 0.85) , d = W0 * 0.62 * Math.pow(f, 0.85);
    const hh = (H - 26) / tiers + (i === 0 ? 10 : 0);
    const ox = (r() - 0.5) * 18;
    add('box', L.x + ox, y - 2, L.z, w, hh + 2, d, 0, i % 3 === 1 ? 1 : 0, 0.3, 3.8, i % 3 === 1 ? 6.4 : 2.6, t, L.seed + i);
    // terrace lip: glowing line + planted terrace
    add('box', L.x + ox, y + hh - 1.4, L.z, w + 6, 2.4, d + 6, 0, 7, 0, 1, 1, t, L.seed + 50 + i);
    // vertical mega-columns
    if (i < tiers - 2) for (const sx of [-0.46, -0.16, 0.16, 0.46]) add('box', L.x + ox + sx * w, y, L.z + d * 0.5 + 4, 10, hh, 10, 0, 7, 0, 1, 1, t, L.seed + 70 + i);
    y += hh;
  }
  // central LED slit on the front face
  add('box', L.x, 30, L.z + W0 * 0.31 + 12, 46, H * 0.62, 5, 0, 3, 0, 1, 1, t, L.seed + 99);
  add('box', L.x, y - 2, L.z, W0 * 0.1, 42, W0 * 0.06, 0, 3, 0, 1, 1, t, L.seed + 77);
  add('box', L.x, y + 40, L.z, 4, 90, 4, 0, 5, 0, 1, 1, t, 1);
  beacon(L.x, y + 134, L.z, 14, 0, 0, 1.4);
  for (const sx of [-0.4, 0.4]) beacon(L.x + sx * W0 * 0.16, y + 10, L.z, 9, 0.5, 0, 1.0);
  return { top: y + 130 };
}

function megaBlock(L, set, beacons) {
  const { add, beacon } = make(set, beacons);
  const t = TINT[L.tint], r = mulberry32(L.seed * 53), H = L.h;
  const nx = 18, ny = Math.round(H / 8.4), nz = 6, m = 7.6, gx = 9.2, gz = 11.4, gy = 8.4;
  const ox = L.x - (nx * gx) / 2, oz = L.z - (nz * gz) / 2;
  // structural cores
  for (const cx of [0.08, 0.38, 0.62, 0.92]) add('box', ox + cx * nx * gx, SINK, L.z, 14, H + 6 - SINK, nz * gz + 6, 0, 7, 0, 1, 1, t, L.seed + cx * 9);
  add('box', L.x, SINK, L.z, nx * gx + 10, 12 - SINK, nz * gz + 14, 0, 4, 0.4, 4, 3.2, t, L.seed);
  for (let j = 0; j < ny; j++) {
    const taper = 1 - 0.3 * Math.pow(j / ny, 2.2);
    for (let i = 0; i < nx; i++) {
      if (r() < 0.22 + 0.2 * (j / ny)) continue;
      for (let k = 0; k < nz; k++) {
        if (i > 0 && i < nx - 1 && k > 0 && k < nz - 1) continue;        // only the shell is visible
        if (r() < 0.18) continue;
        if (Math.abs(i - nx / 2 + 0.5) > (nx / 2) * taper) continue;
        const wl = 0.34 + 0.4 * r();
        add('box', ox + i * gx + gx / 2, 12 + j * gy, oz + k * gz + gz / 2, m, m * 0.96, m, 0, 6, wl, 7.4, 7.0, t, L.seed + i * 7.1 + j * 3.3 + k);
      }
    }
  }
  add('box', L.x, 12 + ny * gy, L.z, 3, 50, 3, 0, 5, 0, 1, 1, t, 1);
  beacon(L.x - 30, 12 + ny * gy + 52, L.z, 8, 0.2, 0, 1.2); beacon(L.x + 30, 12 + ny * gy + 8, L.z, 8, 0.2, 0, 1.2);
  return { top: 12 + ny * gy + 52 };
}

function mast(L, set, beacons) {
  const { add, beacon } = make(set, beacons);
  const t = TINT[L.tint], H = L.h;
  add('cyl', L.x, SINK, L.z, 42, 24 - SINK, 42, 0, 4, 0.4, 4, 3.2, t, L.seed);
  add('cyl', L.x, 20, L.z, 18, H * 0.62, 18, 0, 7, 0, 1, 1, t, L.seed + 1);
  add('cyl', L.x, 20 + H * 0.62 - 2, L.z, 9, H * 0.2, 9, 0, 7, 0, 1, 1, t, L.seed + 2);
  for (const [yy, d] of [[H * 0.32, 44], [H * 0.55, 30]]) {
    add('sph', L.x, yy, L.z, d, d * 0.8, d, 0, 2, 0.25, 4, 2.4, t, L.seed + yy);
    add('cyl', L.x, yy + d * 0.4 - 0.6, L.z, d + 6, 1.4, d + 6, 0, 3, 0, 1, 1, t, L.seed + 5);
  }
  add('box', L.x, 20 + H * 0.82, L.z, 2.6, H * 0.18 + 60, 2.6, 0, 5, 0, 1, 1, t, 1);
  beacon(L.x, 20 + H + 62, L.z, 12, 0.67, 0, 1.4); beacon(L.x, 20 + H * 0.62 + 6, L.z, 8, 0.67, 0, 1.0);
  return { top: 20 + H + 60 };
}

const RECIPES = { needle, twin, led: ledTower, pearl, arcology, block: megaBlock, mast };

export function emitLandmarks(set, beacons, screens) {
  const tops = [];
  for (const L of LANDMARKS) tops.push({ ...L, ...RECIPES[L.id](L, set, beacons, screens) });
  return tops;
}

// ---------- rail viaducts (beam + piers via façade instances) and trains (CPU-moved instances) ----------
export function emitRails(set, beacons) {
  const t = TINT.cool;
  for (const R of RAILS) {
    const dx = R.x1 - R.x0, dz = R.z1 - R.z0, L = Math.hypot(dx, dz), ux = dx / L, uz = dz / L;
    const yaw = Math.atan2(-uz, ux) + Math.PI / 2;       // box local +z along the line
    const seg = 160;
    for (let s = 0; s < L; s += seg) {
      const len = Math.min(seg, L - s), cx = R.x0 + ux * (s + len / 2), cz = R.z0 + uz * (s + len / 2);
      for (const off of [-4.2, 4.2]) {       // twin track beams
        const ox = -uz * off, oz = ux * off;
        set.add('box', cx + ox, R.y - 2.6, cz + oz, 5.2, 2.6, len + 0.4, yaw, 7, 0, 1, 1, t, s);
        set.add('box', cx + ox, R.y - 3.1, cz + oz, 4.0, 0.5, len, yaw, 3, 0, 1, 1, t, s * 0.1 + off);
      }
      set.add('box', cx, R.y - 6.2, cz, 14.5, 1.0, len, yaw, 7, 0, 1, 1, t, s + 3);
    }
    for (let s = 20; s < L; s += 44) {
      const px = R.x0 + ux * s, pz = R.z0 + uz * s;
      set.add('box', px, SINK, pz, 4, R.y - 6 - SINK, 4, yaw, 7, 0, 1, 1, t, s);
    }
  }
}

/** Trains: instanced façade cars moved on the CPU (a dozen matrices per frame). */
export function createTrains(facadeMaterial, makeBoxGeometry) {
  const cars = 7, perRail = 2, total = cars * perRail * RAILS.length;
  const geo = makeBoxGeometry().clone();
  const st = new Float32Array(total * 4), ti = new Float32Array(total * 4);
  for (let i = 0; i < total; i++) { st.set([8, 0.9, 3, 3], i * 4); ti.set([1, 0.9, 0.7, i * 0.37], i * 4); }
  geo.setAttribute('aStyle', new THREE.InstancedBufferAttribute(st, 4));
  geo.setAttribute('aTint', new THREE.InstancedBufferAttribute(ti, 4));
  const im = new THREE.InstancedMesh(geo, facadeMaterial, total);
  im.frustumCulled = false; im.name = 'K-trains';
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), sc = new THREE.Vector3(3.1, 3.4, 18.4), up = new THREE.Vector3(0, 1, 0);
  return {
    mesh: im,
    update(dt, t) {
      let k = 0;
      RAILS.forEach((R, ri) => {
        const dx = R.x1 - R.x0, dz = R.z1 - R.z0, L = Math.hypot(dx, dz), ux = dx / L, uz = dz / L;
        const yaw = Math.atan2(-uz, ux) + Math.PI / 2;
        q.setFromAxisAngle(up, yaw);
        for (let tr = 0; tr < perRail; tr++) {
          const dir = tr ? -1 : 1, speed = 34 + ri * 6;
          const head = ((t * speed * dir + tr * L * 0.5 + ri * 777) % L + L) % L;
          for (let c = 0; c < cars; c++) {
            const s = ((head - dir * c * 20.2) % L + L) % L, off = tr ? 4.2 : -4.2;
            p.set(R.x0 + ux * s - uz * off, R.y, R.z0 + uz * s + ux * off);
            m.compose(p, q, sc); im.setMatrixAt(k++, m);
          }
        }
      });
      im.instanceMatrix.needsUpdate = true;
    },
  };
}

// ---------- cable-stayed bridge over the canal north of the dressed area ----------
const CABLE_VERT = /* glsl */`
attribute float aT;
varying float vT; varying vec3 vRay;
${KGLSL}
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * viewMatrix * wp;
  vT = aT; vRay = wp.xyz - cameraPosition;
}`;
const CABLE_FRAG = /* glsl */`
varying float vT; varying vec3 vRay;
${KGLSL}
void main() {
  float t = uK1.x;
  float pulse = 0.55 + 0.45 * sin(vT * 30.0 - t * 2.5);
  vec3 c = vec3(0.35, 0.65, 1.0) * (0.25 + 0.6 * pulse);
  gl_FragColor = vec4(c * kFogT(vRay) * 0.7, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function createCableBridge(set, beacons, canal, bounds) {
  const cx = (canal.x0 + canal.x1) / 2, z = bounds.z0 - 380, span = 90;
  const add = (...a) => set.add(...a);
  const t = TINT.cool;
  const yDeck = 34, pylonH = 150;
  // deck + side lights
  add('box', cx, yDeck - 3, z, span + 140, 3.2, 26, 0, 7, 0, 1, 1, t, 3);
  add('box', cx, yDeck - 3.4, z, span + 130, 0.5, 20, 0, 3, 0, 1, 1, t, 4);
  // approach piers on both banks
  for (const sx of [-1, 1]) {
    const px = cx + sx * (span / 2 + 22);
    add('box', px, SINK, z - 9, 7, pylonH + 12 - SINK, 5, 0, 7, 0, 1, 1, t, 5);
    add('box', px, SINK, z + 9, 7, pylonH + 12 - SINK, 5, 0, 7, 0, 1, 1, t, 6);
    add('box', px, yDeck + 44, z, 9, 5, 28, 0, 7, 0, 1, 1, t, 7);
    add('box', px, yDeck + 88, z, 8, 4, 22, 0, 3, 0, 1, 1, t, 8);
    beacons?.push(px, pylonH + 16, z - 9, 6, 0.1, 0, 1.0); beacons?.push(px, pylonH + 16, z + 9, 6, 0.1, 0, 1.0);
  }
  // cables
  const pts = [], tt = [];
  for (const sx of [-1, 1]) {
    const px = cx + sx * (span / 2 + 22);
    for (const sz of [-9, 9]) for (let k = 1; k <= 12; k++) {
      const dxo = k * 11 + 8;
      for (const dir of [-1, 1]) {
        pts.push(px, pylonH + 8 - k * 3.2, z + sz, px + dir * dxo, yDeck - 2.8, z + sz * 1.35); tt.push(k / 12, k / 12);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); g.setAttribute('aT', new THREE.Float32BufferAttribute(tt, 1));
  const lines = new THREE.LineSegments(g, new THREE.ShaderMaterial({ vertexShader: CABLE_VERT, fragmentShader: CABLE_FRAG, uniforms: kUniforms(), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
  lines.frustumCulled = false; lines.name = 'K-cables'; lines.renderOrder = 8;
  return { lines, z };
}
