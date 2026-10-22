// World helpers: seeded RNG, small math, and `Geo` — a growable geometry accumulator used for all merged world meshes.
import * as THREE from 'three';

export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function hash2(x, z, seed = 0) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(z | 0, 668265263) + Math.imul(seed | 0, 2147483647)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177); h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smoothstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
export const TAU = Math.PI * 2;

/**
 * Growable merged-geometry builder. Base attributes: position, normal, uv, color (RGBA8, normalised) + `lvl` (a light level used by
 * the bake, not uploaded). `extras` = { name: itemSize } adds float attributes whose "current" value is set with `ex(name, ...)`.
 * Set the current colour with `color()`; every vertex emitted afterwards uses it.
 */
export class Geo {
  constructor(extras = {}) {
    this.n = 0; this.ni = 0; this.cap = 2048; this.icap = 6144;
    this.pos = new Float32Array(this.cap * 3); this.nor = new Float32Array(this.cap * 3); this.uv = new Float32Array(this.cap * 2);
    this.col = new Uint8Array(this.cap * 4); this.lvl = new Uint8Array(this.cap);
    this.idx = new Uint32Array(this.icap);
    this.exn = Object.keys(extras);
    this.ex_ = {};
    for (const k of this.exn) this.ex_[k] = { size: extras[k], arr: new Float32Array(this.cap * extras[k]), cur: new Float32Array(extras[k]) };
    this.c = [255, 255, 255, 255]; this.curLvl = 0;
    this.bmin = [Infinity, Infinity, Infinity]; this.bmax = [-Infinity, -Infinity, -Infinity];
  }
  _grow() {
    const cap = this.cap * 2;
    const g = (a, k) => { const b = new a.constructor(cap * k); b.set(a); return b; };
    this.pos = g(this.pos, 3); this.nor = g(this.nor, 3); this.uv = g(this.uv, 2); this.col = g(this.col, 4); this.lvl = g(this.lvl, 1);
    for (const k of this.exn) { const e = this.ex_[k]; e.arr = g(e.arr, e.size); }
    this.cap = cap;
  }
  color(r, g, b, a = 1) {
    if (typeof r === 'object') { a = r.a ?? g ?? 1; b = r.b; g = r.g; r = r.r; }
    this.c[0] = Math.round(clamp(r, 0, 1) * 255); this.c[1] = Math.round(clamp(g, 0, 1) * 255);
    this.c[2] = Math.round(clamp(b, 0, 1) * 255); this.c[3] = Math.round(clamp(a, 0, 1) * 255);
    return this;
  }
  /** Set the current value of an extra attribute. */
  ex(name, ...v) { const c = this.ex_[name].cur; for (let i = 0; i < c.length; i++) c[i] = v[i] ?? 0; return this; }
  lv(l) { this.curLvl = l; return this; }
  vert(x, y, z, nx, ny, nz, u, v) {
    if (this.n >= this.cap) this._grow();
    const i = this.n++, i3 = i * 3;
    this.pos[i3] = x; this.pos[i3 + 1] = y; this.pos[i3 + 2] = z;
    this.nor[i3] = nx; this.nor[i3 + 1] = ny; this.nor[i3 + 2] = nz;
    this.uv[i * 2] = u; this.uv[i * 2 + 1] = v;
    const c = this.c, i4 = i * 4; this.col[i4] = c[0]; this.col[i4 + 1] = c[1]; this.col[i4 + 2] = c[2]; this.col[i4 + 3] = c[3];
    this.lvl[i] = this.curLvl;
    for (const k of this.exn) { const e = this.ex_[k]; const o = i * e.size; for (let j = 0; j < e.size; j++) e.arr[o + j] = e.cur[j]; }
    const b0 = this.bmin, b1 = this.bmax;
    if (x < b0[0]) b0[0] = x; if (y < b0[1]) b0[1] = y; if (z < b0[2]) b0[2] = z;
    if (x > b1[0]) b1[0] = x; if (y > b1[1]) b1[1] = y; if (z > b1[2]) b1[2] = z;
    return i;
  }
  tri(a, b, c) {
    if (this.ni + 3 > this.icap) { this.icap *= 2; const b2 = new Uint32Array(this.icap); b2.set(this.idx); this.idx = b2; }
    this.idx[this.ni++] = a; this.idx[this.ni++] = b; this.idx[this.ni++] = c;
  }
  quad(a, b, c, d) { this.tri(a, b, c); this.tri(a, c, d); }

  /** Flat quad p0..p3 (CCW seen from the front). uv in metres: u along p0→p1, v along p0→p3 (+ u0,v0). Returns first vertex index. */
  quadP(p0, p1, p2, p3, u0 = 0, v0 = 0, uvScale = 1) {
    const ax = p1[0] - p0[0], ay = p1[1] - p0[1], az = p1[2] - p0[2], bx = p3[0] - p0[0], by = p3[1] - p0[1], bz = p3[2] - p0[2];
    let nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
    const nl = Math.hypot(nx, ny, nz) || 1; nx /= nl; ny /= nl; nz /= nl;
    const L1 = Math.hypot(ax, ay, az) * uvScale, L3 = Math.hypot(bx, by, bz) * uvScale;
    const i0 = this.vert(p0[0], p0[1], p0[2], nx, ny, nz, u0, v0);
    this.vert(p1[0], p1[1], p1[2], nx, ny, nz, u0 + L1, v0);
    this.vert(p2[0], p2[1], p2[2], nx, ny, nz, u0 + L1, v0 + L3);
    this.vert(p3[0], p3[1], p3[2], nx, ny, nz, u0, v0 + L3);
    this.quad(i0, i0 + 1, i0 + 2, i0 + 3);
    return i0;
  }
  /** Quad with explicit uv per corner [[u,v]×4]. */
  quadUV(p0, p1, p2, p3, uv) {
    const ax = p1[0] - p0[0], ay = p1[1] - p0[1], az = p1[2] - p0[2], bx = p3[0] - p0[0], by = p3[1] - p0[1], bz = p3[2] - p0[2];
    let nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
    const nl = Math.hypot(nx, ny, nz) || 1; nx /= nl; ny /= nl; nz /= nl;
    const i0 = this.vert(p0[0], p0[1], p0[2], nx, ny, nz, uv[0][0], uv[0][1]);
    this.vert(p1[0], p1[1], p1[2], nx, ny, nz, uv[1][0], uv[1][1]);
    this.vert(p2[0], p2[1], p2[2], nx, ny, nz, uv[2][0], uv[2][1]);
    this.vert(p3[0], p3[1], p3[2], nx, ny, nz, uv[3][0], uv[3][1]);
    this.quad(i0, i0 + 1, i0 + 2, i0 + 3);
    return i0;
  }
  /**
   * Axis box rotated about Y by `ry` around its centre. faces: string of any of "+x -x +y -y +z -z" letters (default all).
   * Side-face uv: (metres along face, metres up); top/bottom: (x, z) local metres. opts.uo/vo offsets, opts.uvs scale.
   */
  box(cx, cy, cz, sx, sy, sz, ry = 0, faces = 'xXyYzZ', o = {}) {
    const c = Math.cos(ry), s = Math.sin(ry), hx = sx / 2, hy = sy / 2, hz = sz / 2, k = o.uvs ?? 1, uo = o.uo ?? 0, vo = o.vo ?? 0;
    const P = (x, y, z) => [cx + x * c + z * s, cy + y, cz - x * s + z * c];
    // faces: X=+x  x=-x  Y=+y  y=-y  Z=+z  z=-z  (use letters: 'X' '+x' ...). We accept 'xXyYzZ' = -x,+x,-y,+y,-z,+z
    if (faces.includes('X')) this.quadUV(P(hx, -hy, hz), P(hx, -hy, -hz), P(hx, hy, -hz), P(hx, hy, hz), [[uo, vo], [uo + sz * k, vo], [uo + sz * k, vo + sy * k], [uo, vo + sy * k]]);
    if (faces.includes('x')) this.quadUV(P(-hx, -hy, -hz), P(-hx, -hy, hz), P(-hx, hy, hz), P(-hx, hy, -hz), [[uo, vo], [uo + sz * k, vo], [uo + sz * k, vo + sy * k], [uo, vo + sy * k]]);
    if (faces.includes('Z')) this.quadUV(P(-hx, -hy, hz), P(hx, -hy, hz), P(hx, hy, hz), P(-hx, hy, hz), [[uo, vo], [uo + sx * k, vo], [uo + sx * k, vo + sy * k], [uo, vo + sy * k]]);
    if (faces.includes('z')) this.quadUV(P(hx, -hy, -hz), P(-hx, -hy, -hz), P(-hx, hy, -hz), P(hx, hy, -hz), [[uo, vo], [uo + sx * k, vo], [uo + sx * k, vo + sy * k], [uo, vo + sy * k]]);
    if (faces.includes('Y')) this.quadUV(P(-hx, hy, hz), P(hx, hy, hz), P(hx, hy, -hz), P(-hx, hy, -hz), [[uo, vo], [uo + sx * k, vo], [uo + sx * k, vo + sz * k], [uo, vo + sz * k]]);
    if (faces.includes('y')) this.quadUV(P(-hx, -hy, -hz), P(hx, -hy, -hz), P(hx, -hy, hz), P(-hx, -hy, hz), [[uo, vo], [uo + sx * k, vo], [uo + sx * k, vo + sz * k], [uo, vo + sz * k]]);
  }
  /** Vertical cylinder (smooth normals), base at y, height h. caps: top cap only if `top`. */
  cyl(cx, y, cz, r0, r1, h, seg = 12, top = true, o = {}) {
    const i0 = this.n, k = o.uvs ?? 1;
    const dr = r0 - r1, nl = Math.hypot(h, dr);
    for (let j = 0; j <= seg; j++) {
      const a = j / seg * TAU, ca = Math.cos(a), sa = Math.sin(a);
      const nx = ca * h / nl, nz = sa * h / nl, ny = dr / nl, u = j / seg * TAU * Math.max(r0, r1) * k;
      this.vert(cx + ca * r0, y, cz + sa * r0, nx, ny, nz, u, 0);
      this.vert(cx + ca * r1, y + h, cz + sa * r1, nx, ny, nz, u, nl * k);
    }
    for (let j = 0; j < seg; j++) { const a = i0 + j * 2; this.quad(a, a + 2, a + 3, a + 1); }
    if (top && r1 > 0) {
      const t0 = this.vert(cx, y + h, cz, 0, 1, 0, 0, 0);
      for (let j = 0; j <= seg; j++) { const a = j / seg * TAU; this.vert(cx + Math.cos(a) * r1, y + h, cz + Math.sin(a) * r1, 0, 1, 0, Math.cos(a) * r1, Math.sin(a) * r1); }
      for (let j = 0; j < seg; j++) this.tri(t0, t0 + 2 + j, t0 + 1 + j);
    }
  }
  /** Fan-triangulate a convex polygon given as [[x,y,z],…] (CCW from the front) with a given normal and planar uv from (ua,va) axes. */
  poly(pts, n, uAxis, vAxis, u0 = 0, v0 = 0) {
    const i0 = this.n;
    for (const p of pts) this.vert(p[0], p[1], p[2], n[0], n[1], n[2], u0 + p[0] * uAxis[0] + p[1] * uAxis[1] + p[2] * uAxis[2], v0 + p[0] * vAxis[0] + p[1] * vAxis[1] + p[2] * vAxis[2]);
    for (let i = 1; i < pts.length - 1; i++) this.tri(i0, i0 + i, i0 + i + 1);
  }
  get empty() { return this.n === 0; }
  toGeometry(extraAttrs = {}) {
    const g = new THREE.BufferGeometry();
    const n = this.n;
    g.setAttribute('position', new THREE.BufferAttribute(this.pos.slice(0, n * 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nor.slice(0, n * 3), 3));
    g.setAttribute('uv', new THREE.BufferAttribute(this.uv.slice(0, n * 2), 2));
    g.setAttribute('color', new THREE.BufferAttribute(this.col.slice(0, n * 4), 4, true));
    for (const k of this.exn) { const e = this.ex_[k]; g.setAttribute(k, new THREE.BufferAttribute(e.arr.slice(0, n * e.size), e.size)); }
    for (const k in extraAttrs) g.setAttribute(k, extraAttrs[k]);
    g.setIndex(new THREE.BufferAttribute(this.idx.slice(0, this.ni), 1));
    const b = new THREE.Box3(new THREE.Vector3(...this.bmin), new THREE.Vector3(...this.bmax));
    g.boundingBox = b; g.boundingSphere = b.getBoundingSphere(new THREE.Sphere());
    return g;
  }
}

/** Value noise (for build-time randomisation): deterministic 2D smooth noise in [0,1). */
export function vnoise(x, z, seed = 0) {
  const xi = Math.floor(x), zi = Math.floor(z), fx = x - xi, fz = z - zi;
  const sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
  const a = hash2(xi, zi, seed), b = hash2(xi + 1, zi, seed), c = hash2(xi, zi + 1, seed), d = hash2(xi + 1, zi + 1, seed);
  return (a + (b - a) * sx) * (1 - sz) + (c + (d - c) * sx) * sz;
}
