// Track: the circuit centreline, its frames and fast spatial queries. Shared by every area.
// See CONTRACTS.md §Track for the API. Built once: `const track = getTrack()`.
import * as THREE from 'three';
import { LAYOUT } from './layout.js';

/** Barrier collision face sits at |u| = hw + WALL_OFFSET (the road surface continues to it as a gutter). */
export const WALL_OFFSET = 0.5;
export const KIND = { GROUND: 0, ELEVATED: 1, TRENCH: 2, TUNNEL: 3, BRIDGE: 4 };
export const KIND_NAMES = ['ground', 'elevated', 'trench', 'tunnel', 'bridge'];
const FIELD_CELL = 2, FIELD_MAX = 80, HASH_CELL = 16;

let _track = null;
export function getTrack() { return _track ??= new Track(LAYOUT); }

export class Track {
  constructor(layout) {
    this.layout = layout;
    this.ds = layout.ds;
    this._buildCentreline();
    this._buildProfiles();
    this._buildFrames();
    this._buildHash();
    this._buildField();
    this.startS = this.project(new THREE.Vector3(layout.start.x, 0, layout.start.z)).s;
    this.laps = layout.laps;
  }

  // ---------- construction ----------
  _buildCentreline() {
    const V = this.layout.vertices, n = V.length;
    const pts = [];
    for (let k = 0; k < n; k++) {
      const P = V[(k - 1 + n) % n], C = V[k], Nx = V[(k + 1) % n];
      const a = norm2(C.x - P.x, C.z - P.z), b = norm2(Nx.x - C.x, Nx.z - C.z);
      const cross = a[0] * b[1] - a[1] * b[0], dot = a[0] * b[0] + a[1] * b[1];
      const th = Math.atan2(cross, dot);              // signed turn angle
      const tl = C.r * Math.tan(Math.abs(th) / 2);     // tangent length
      const p0 = [C.x - a[0] * tl, C.z - a[1] * tl];
      // arc centre: left normal of a is (a.z, -a.x)?? In XZ with -Z north, rotate a by +90° towards turn side.
      const sgn = Math.sign(th) || 1;
      const nrm = [-a[1] * sgn, a[0] * sgn];          // points to the inside of the turn
      const cx = p0[0] + nrm[0] * C.r, cz = p0[1] + nrm[1] * C.r;
      const segs = Math.max(2, Math.ceil(Math.abs(th) * C.r / 0.5));
      const a0 = Math.atan2(p0[1] - cz, p0[0] - cx);
      for (let j = 0; j <= segs; j++) {
        const ang = a0 + th * (j / segs);
        pts.push([cx + Math.cos(ang) * C.r, cz + Math.sin(ang) * C.r]);
      }
    }
    // densify straights + arcs to ~ds, cyclic
    let poly = resampleClosed(pts, this.ds);
    // Laplacian smoothing → curvature transitions
    const m = poly.length;
    let x = new Float64Array(m), z = new Float64Array(m);
    for (let i = 0; i < m; i++) { x[i] = poly[i][0]; z[i] = poly[i][1]; }
    for (let it = 0; it < this.layout.smoothIters; it++) {
      const nx = new Float64Array(m), nz = new Float64Array(m);
      for (let i = 0; i < m; i++) {
        const p = (i - 1 + m) % m, q = (i + 1) % m;
        nx[i] = 0.5 * x[i] + 0.25 * (x[p] + x[q]);
        nz[i] = 0.5 * z[i] + 0.25 * (z[p] + z[q]);
      }
      x = nx; z = nz;
    }
    poly = resampleClosed(Array.from({ length: m }, (_, i) => [x[i], z[i]]), this.ds);
    const N = this.N = poly.length;
    this.length = N * this.ds;
    this.px = new Float32Array(N); this.pz = new Float32Array(N); this.py = new Float32Array(N);
    for (let i = 0; i < N; i++) { this.px[i] = poly[i][0]; this.pz[i] = poly[i][1]; }
  }

  _nearestIndex2D(x, z) {
    let best = 0, bd = Infinity;
    for (let i = 0; i < this.N; i++) {
      const d = (this.px[i] - x) ** 2 + (this.pz[i] - z) ** 2;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  _keyed(keys, getVal) {
    // returns sorted [{i, v}] by index
    return keys.map(k => ({ i: this._nearestIndex2D(k.x, k.z), v: getVal(k), k })).sort((a, b) => a.i - b.i);
  }

  _buildProfiles() {
    const N = this.N, L = this.layout;
    // elevation: cyclic piecewise linear, then box smoothing (twice → C1)
    const ek = this._keyed(L.elevation, k => k.y);
    const y = new Float64Array(N);
    for (let a = 0; a < ek.length; a++) {
      const A = ek[a], B = ek[(a + 1) % ek.length];
      const span = (B.i - A.i + N) % N || N;
      for (let j = 0; j < span; j++) y[(A.i + j) % N] = A.v + (B.v - A.v) * (j / span);
    }
    const ys = boxSmoothCyclic(boxSmoothCyclic(y, Math.round(L.elevSmooth / this.ds / 2)), Math.round(L.elevSmooth / this.ds / 2));
    for (let i = 0; i < N; i++) this.py[i] = ys[i];

    // zones + widths (step function, widths smoothed)
    this.zoneNames = [...new Set(L.zones.map(z => z.zone))];
    this.zone = new Uint8Array(N);
    const zk = this._keyed(L.zones, k => k);
    const w = new Float64Array(N);
    for (let a = 0; a < zk.length; a++) {
      const A = zk[a], B = zk[(a + 1) % zk.length];
      const span = (B.i - A.i + N) % N || N;
      for (let j = 0; j < span; j++) {
        const i = (A.i + j) % N;
        this.zone[i] = this.zoneNames.indexOf(A.v.zone);
        w[i] = A.v.w;
      }
    }
    const ws = boxSmoothCyclic(boxSmoothCyclic(w, Math.round(L.widthSmooth / this.ds / 2)), Math.round(L.widthSmooth / this.ds / 2));
    this.hw = new Float32Array(N);
    for (let i = 0; i < N; i++) this.hw[i] = ws[i] / 2;

    // bank: gaussian bumps at apexes, sigma from local curvature extent
    this.bank = new Float32Array(N);
    for (const b of L.bank) {
      const c = this._nearestIndex2D(b.x, b.z);
      const sig = 60 / this.ds;
      for (let j = -4 * sig; j <= 4 * sig; j++) {
        const i = ((c + j) % N + N) % N;
        this.bank[i] += THREE.MathUtils.degToRad(b.deg) * Math.exp(-0.5 * (j / sig) ** 2);
      }
    }
  }

  _buildFrames() {
    const N = this.N, L = this.layout;
    const A = n => new Float32Array(n);
    this.tx = A(N); this.ty = A(N); this.tz = A(N);
    this.ux = A(N); this.uy = A(N); this.uz = A(N);
    this.rx = A(N); this.ry = A(N); this.rz = A(N);
    this.curv = A(N); this.grade = A(N); this.kind = new Uint8Array(N);
    const t = new THREE.Vector3(), u = new THREE.Vector3(), r = new THREE.Vector3(), Y = new THREE.Vector3(0, 1, 0);
    for (let i = 0; i < N; i++) {
      const p = (i - 1 + N) % N, q = (i + 1) % N;
      t.set(this.px[q] - this.px[p], this.py[q] - this.py[p], this.pz[q] - this.pz[p]).normalize();
      r.crossVectors(t, Y).normalize();          // horizontal right
      u.crossVectors(r, t).normalize();          // up (tilted with grade)
      const b = this.bank[i], cb = Math.cos(b), sb = Math.sin(b);
      const rx = r.x * cb + u.x * sb, ry = r.y * cb + u.y * sb, rz = r.z * cb + u.z * sb;
      const ux = u.x * cb - r.x * sb, uy = u.y * cb - r.y * sb, uz = u.z * cb - r.z * sb;
      this.tx[i] = t.x; this.ty[i] = t.y; this.tz[i] = t.z;
      this.rx[i] = rx; this.ry[i] = ry; this.rz[i] = rz;
      this.ux[i] = ux; this.uy[i] = uy; this.uz[i] = uz;
      this.grade[i] = t.y / Math.hypot(t.x, t.z);
    }
    // signed horizontal curvature (+ = turning left)
    for (let i = 0; i < N; i++) {
      const p = (i - 2 + N) % N, q = (i + 2) % N;
      const h0 = Math.atan2(this.tx[p], -this.tz[p]), h1 = Math.atan2(this.tx[q], -this.tz[q]);
      let dh = h1 - h0; dh = Math.atan2(Math.sin(dh), Math.cos(dh));
      this.curv[i] = -dh / (4 * this.ds);
    }
    // kinds
    const tunnelZ = this.zoneNames.indexOf('tunnel');
    const cn = L.canal;
    for (let i = 0; i < N; i++) {
      const y = this.py[i], x = this.px[i];
      let k = KIND.GROUND;
      if (this.zone[i] === tunnelZ && y < -4) k = KIND.TUNNEL;
      else if (y > 2.5) k = KIND.ELEVATED;
      else if (y < -1.0) k = KIND.TRENCH;
      else if (cn && x > cn.x0 - 8 && x < cn.x1 + 8) k = KIND.BRIDGE;
      this.kind[i] = k;
    }
  }

  _buildHash() {
    this.hash = new Map();
    for (let i = 0; i < this.N; i++) {
      const key = hkey(Math.floor(this.px[i] / HASH_CELL), Math.floor(this.pz[i] / HASH_CELL));
      let a = this.hash.get(key); if (!a) this.hash.set(key, a = []); a.push(i);
    }
  }

  _buildField() {
    const B = this.layout.bounds, c = FIELD_CELL;
    const W = this.fw = Math.ceil((B.x1 - B.x0) / c), H = this.fh = Math.ceil((B.z1 - B.z0) / c);
    this.fAll = new Float32Array(W * H).fill(FIELD_MAX);
    this.fGround = new Float32Array(W * H).fill(FIELD_MAX);
    this.fIdx = new Int32Array(W * H).fill(-1);
    for (let i = 0; i < this.N; i++) {
      const hw = this.hw[i], R = hw + FIELD_MAX, x = this.px[i], z = this.pz[i];
      const ground = this.kind[i] === KIND.GROUND || this.kind[i] === KIND.BRIDGE || this.kind[i] === KIND.TRENCH;
      const gx0 = Math.max(0, Math.floor((x - R - B.x0) / c)), gx1 = Math.min(W - 1, Math.ceil((x + R - B.x0) / c));
      const gz0 = Math.max(0, Math.floor((z - R - B.z0) / c)), gz1 = Math.min(H - 1, Math.ceil((z + R - B.z0) / c));
      for (let gz = gz0; gz <= gz1; gz++) {
        const cz = B.z0 + (gz + 0.5) * c, dz2 = (cz - z) ** 2;
        const row = gz * W;
        for (let gx = gx0; gx <= gx1; gx++) {
          const cx = B.x0 + (gx + 0.5) * c;
          const d = Math.sqrt((cx - x) ** 2 + dz2) - hw;
          const k = row + gx;
          if (d < this.fAll[k]) { this.fAll[k] = d; this.fIdx[k] = i; }
          if (ground && d < this.fGround[k]) this.fGround[k] = d;
        }
      }
    }
  }

  // ---------- queries ----------
  wrapIndex(i) { return ((i % this.N) + this.N) % this.N; }
  wrapS(s) { return ((s % this.length) + this.length) % this.length; }
  indexAt(s) { return this.wrapIndex(Math.floor(s / this.ds)); }

  /** Interpolated frame at arc length s. Writes into `out` (allocated if missing). */
  frameAt(s, out = {}) {
    s = this.wrapS(s);
    const f = s / this.ds, i = Math.floor(f) % this.N, j = (i + 1) % this.N, a = f - Math.floor(f);
    const L = (A) => A[i] + (A[j] - A[i]) * a;
    out.pos ??= new THREE.Vector3(); out.t ??= new THREE.Vector3(); out.u ??= new THREE.Vector3(); out.r ??= new THREE.Vector3();
    out.pos.set(L(this.px), L(this.py), L(this.pz));
    out.t.set(L(this.tx), L(this.ty), L(this.tz)).normalize();
    out.u.set(L(this.ux), L(this.uy), L(this.uz)).normalize();
    out.r.set(L(this.rx), L(this.ry), L(this.rz)).normalize();
    out.hw = L(this.hw); out.bank = L(this.bank); out.curv = L(this.curv);
    out.i = i; out.s = s; out.zone = this.zoneNames[this.zone[i]]; out.kind = this.kind[i];
    return out;
  }

  /** Point on the road surface at (s, lateral offset u). u>0 = right of the centreline. */
  pointAt(s, u, out = new THREE.Vector3()) {
    const f = this.frameAt(s, this._tmpF ??= {});
    return out.copy(f.pos).addScaledVector(f.r, u);
  }

  /**
   * Project a world position onto the road. With `hint` (a sample index from the previous call) the
   * search is local (±40 m) and cannot jump to the other level at the crossover. Without a hint the
   * nearest road in 3D is chosen. Writes into `out` and returns it:
   *   { i, s, u, y, hw, nx, ny, nz, d }   u = lateral offset (m, + right), y = road height at that point,
   *   n = road up normal, d = pos.y - y.
   */
  project(pos, hint = -1, out = {}) {
    const x = pos.x, z = pos.z;
    let bi = -1, bt = 0, bd = Infinity;
    const test = (i) => {
      const j = (i + 1) % this.N;
      const ax = this.px[i], az = this.pz[i], ex = this.px[j] - ax, ez = this.pz[j] - az;
      let tt = ((x - ax) * ex + (z - az) * ez) / (ex * ex + ez * ez);
      tt = tt < 0 ? 0 : tt > 1 ? 1 : tt;
      const qx = ax + ex * tt - x, qz = az + ez * tt - z;
      let d = qx * qx + qz * qz;
      if (hint < 0 && pos.y !== undefined) {
        const yy = this.py[i] + (this.py[j] - this.py[i]) * tt;
        d += 4 * (pos.y - yy) ** 2;
      }
      if (d < bd) { bd = d; bi = i; bt = tt; }
    };
    if (hint >= 0) {
      for (let k = -40; k <= 40; k++) test(this.wrapIndex(hint + k));
    } else {
      const cx = Math.floor(x / HASH_CELL), cz = Math.floor(z / HASH_CELL);
      for (let rad = 1; rad <= 12 && bi < 0; rad += 3) {
        for (let a = -rad; a <= rad; a++) for (let b = -rad; b <= rad; b++) {
          const lst = this.hash.get(hkey(cx + a, cz + b)); if (lst) for (const i of lst) test(i);
        }
      }
      if (bi < 0) for (let i = 0; i < this.N; i++) test(i);
    }
    const i = bi, j = (i + 1) % this.N, t = bt;
    const L = (A) => A[i] + (A[j] - A[i]) * t;
    const cxp = L(this.px), czp = L(this.pz), cyp = L(this.py);
    const rx = L(this.rx), ry = L(this.ry), rz = L(this.rz);
    const rh = Math.hypot(rx, rz);
    const u = ((x - cxp) * rx + (z - czp) * rz) / rh;
    out.i = i; out.s = (i + t) * this.ds; out.u = u;
    out.y = cyp + u * ry / rh;
    out.hw = L(this.hw);
    let nx = L(this.ux), ny = L(this.uy), nz = L(this.uz);
    const nl = Math.hypot(nx, ny, nz); out.nx = nx / nl; out.ny = ny / nl; out.nz = nz / nl;
    out.d = pos.y !== undefined ? pos.y - out.y : 0;
    out.kind = this.kind[i];
    return out;
  }

  /**
   * City placement field at (x, z): horizontal distance (m) from the nearest road EDGE
   * (negative = on the road). `all` counts every road level; `ground` only ground-level / trench /
   * bridge road (use it to keep expressway pillars off the streets). Clamped to 80 m. `i` = nearest sample.
   */
  field(x, z, out = {}) {
    const B = this.layout.bounds;
    const gx = Math.floor((x - B.x0) / FIELD_CELL), gz = Math.floor((z - B.z0) / FIELD_CELL);
    if (gx < 0 || gz < 0 || gx >= this.fw || gz >= this.fh) { out.all = FIELD_MAX; out.ground = FIELD_MAX; out.i = -1; return out; }
    const k = gz * this.fw + gx;
    out.all = this.fAll[k]; out.ground = this.fGround[k]; out.i = this.fIdx[k];
    return out;
  }

  /** Starting grid slot k (0 = pole). Returns { pos, quat, s, u }. Cars face +s; car local forward is -Z. */
  gridSlot(k) {
    const row = Math.floor(k / 2), side = k % 2 ? 1 : -1;
    const s = this.wrapS(this.startS - 8 - row * 9 - (side > 0 ? 4.5 : 0));
    const f = this.frameAt(s, {});
    const u = side * Math.min(3.2, f.hw * 0.4);
    const pos = this.pointAt(s, u);
    return { pos, quat: this.quatAt(s), s, u };
  }

  /** Orientation of a car sitting on the road at s (local -Z = travel direction, +X = right, +Y = road up). */
  quatAt(s, out = new THREE.Quaternion()) {
    const f = this.frameAt(s, this._tmpQ ??= {});
    const back = f.t.clone().negate();
    const m = new THREE.Matrix4().makeBasis(f.r, f.u, back);
    return out.setFromRotationMatrix(m);
  }

  /** Signed lap distance from a to b in (-L/2, L/2]. */
  deltaS(a, b) { let d = this.wrapS(b - a); if (d > this.length / 2) d -= this.length; return d; }
}

function norm2(x, z) { const l = Math.hypot(x, z); return [x / l, z / l]; }
function hkey(a, b) { return a * 73856093 ^ b * 19349663; }

function resampleClosed(pts, ds) {
  const n = pts.length, cum = [0];
  for (let i = 1; i <= n; i++) {
    const a = pts[i - 1], b = pts[i % n];
    cum.push(cum[i - 1] + Math.hypot(b[0] - a[0], b[1] - a[1]));
  }
  const total = cum[n], m = Math.round(total / ds), step = total / m, out = [];
  let k = 0;
  for (let j = 0; j < m; j++) {
    const s = j * step;
    while (cum[k + 1] < s) k++;
    const a = pts[k], b = pts[(k + 1) % n], t = (s - cum[k]) / (cum[k + 1] - cum[k] || 1);
    out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
  }
  return out;
}

function boxSmoothCyclic(a, h) {
  if (h < 1) return a;
  const n = a.length, out = new Float64Array(n);
  let acc = 0;
  for (let k = -h; k <= h; k++) acc += a[((k % n) + n) % n];
  for (let i = 0; i < n; i++) {
    out[i] = acc / (2 * h + 1);
    acc += a[(i + h + 1) % n] - a[((i - h) % n + n) % n];
  }
  return out;
}
