// Small geometry helpers shared by the dressing modules: oriented beams, containers, steam puffs.
import { mulberry32 } from './util.js';

/** Rectangular prism from a to b (3D points) with cross-section w × h; `up` orients h (default world Y). */
export function beam(g, a, b, w, h, up = [0, 1, 0], caps = true) {
  let dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2];
  const L = Math.hypot(dx, dy, dz); if (L < 1e-5) return;
  dx /= L; dy /= L; dz /= L;
  // side axis s = d × up ; real up u = s × d
  let sx = dy * up[2] - dz * up[1], sy = dz * up[0] - dx * up[2], sz = dx * up[1] - dy * up[0];
  let sl = Math.hypot(sx, sy, sz);
  if (sl < 1e-4) { sx = 1; sy = 0; sz = 0; sl = 1; }
  sx /= sl; sy /= sl; sz /= sl;
  const ux = sy * dz - sz * dy, uy = sz * dx - sx * dz, uz = sx * dy - sy * dx;
  const hw = w / 2, hh = h / 2;
  const C = (p, i, j) => [p[0] + sx * hw * i + ux * hh * j, p[1] + sy * hw * i + uy * hh * j, p[2] + sz * hw * i + uz * hh * j];
  const A = [C(a, -1, -1), C(a, 1, -1), C(a, 1, 1), C(a, -1, 1)], B = [C(b, -1, -1), C(b, 1, -1), C(b, 1, 1), C(b, -1, 1)];
  // side faces: (A0,A1)->bottom normal -u, (A1,A2) +s, (A2,A3) +u, (A3,A0) -s
  g.quadP(A[1], A[0], B[0], B[1], 0, 0);   // bottom (-u): edge a0→a1 reversed so the normal points to -u
  g.quadP(A[2], A[1], B[1], B[2], 0, 0);   // +s
  g.quadP(A[3], A[2], B[2], B[3], 0, 0);   // +u
  g.quadP(A[0], A[3], B[3], B[0], 0, 0);   // -s
  if (caps) { g.quadP(A[0], A[1], A[2], A[3]); g.quadP(B[3], B[2], B[1], B[0]); }
}

export const BOX_COLS = [[.5, .12, .08], [.12, .22, .5], [.1, .38, .22], [.62, .34, .08], [.5, .42, .12], [.34, .36, .4], [.55, .55, .56], [.34, .08, .14], [.08, .3, .38]];

/** Shipping container: length `len` along local x (rotated by ry about Y), centre-bottom at (cx, y0, cz). */
export function container(g, cx, y0, cz, len, ry, col, faces = 'xXzZY') {
  g.color(col[0], col[1], col[2], 1);
  g.box(cx, y0 + 1.295, cz, len, 2.59, 2.44, ry, faces.replace('Y', ''));
  if (faces.includes('Y')) { g.color(col[0] * .7, col[1] * .7, col[2] * .7, 1); g.box(cx, y0 + 1.295, cz, len, 2.59, 2.44, ry, 'Y'); }
}

/** Steam vent: n puffs rising `h` metres. Registered on the 'steam' geometry of the chunk. */
export function addSteam(ctx, ch, x, y, z, { n = 5, h = 5, size = 1.1, speed = 0.11, seed = 1 } = {}) {
  const g = ctx.geo('steam', ch); g.lv(0); g.color(1, 1, 1, 1);
  const rnd = mulberry32((Math.floor(x * 13) ^ Math.floor(z * 7) ^ seed) | 0);
  const cs = [[-1, -1, 0, 0], [1, -1, 1, 0], [1, 1, 1, 1], [-1, 1, 0, 1]];
  for (let k = 0; k < n; k++) {
    g.ex('aSt', (k + rnd() * .6) / n, speed * (.85 + rnd() * .3), h * (.8 + rnd() * .4));
    const i0 = g.n, sz = size * (.75 + rnd() * .5);
    for (const [ox, oy, u, v] of cs) { g.ex('aCorner', sz, ox, oy); g.vert(x, y, z, 0, 1, 0, u, v); }
    g.quad(i0, i0 + 1, i0 + 2, i0 + 3);
  }
  ctx.stats.steam = (ctx.stats.steam ?? 0) + 1;
}

/** Vertical prism from a convex plan polygon [[x,z],…]: outward side walls (uv in metres) between y0 and y1, optional top cap. */
export function prism(g, pts, y0, y1, { top = true, rows = 1 } = {}) {
  let cx = 0, cz = 0; for (const p of pts) { cx += p[0]; cz += p[1]; } cx /= pts.length; cz /= pts.length;
  let u0 = 0;
  for (let k = 0; k < pts.length; k++) {
    let a = pts[k], b = pts[(k + 1) % pts.length];
    const mx = (a[0] + b[0]) / 2 - cx, mz = (a[1] + b[1]) / 2 - cz;
    if (-(b[1] - a[1]) * mx + (b[0] - a[0]) * mz < 0) { const t = a; a = b; b = t; }
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    for (let r = 0; r < rows; r++) {
      const ya = y0 + (y1 - y0) * r / rows, yb = y0 + (y1 - y0) * (r + 1) / rows;
      g.quadP([a[0], ya, a[1]], [b[0], ya, b[1]], [b[0], yb, b[1]], [a[0], yb, a[1]], u0, ya);
    }
    u0 += L;
  }
  if (top) capY(g, pts.map(p => [p[0], y1, p[1]]));
}
/** Horizontal cap with the normal pointing up (fan, convex). */
export function capY(g, p3) {
  const n = p3.length; let ny = 0;
  for (let i = 0; i < n; i++) { const a = p3[i], b = p3[(i + 1) % n]; ny += (a[2] - b[2]) * (a[0] + b[0]); }
  // shoelace sign in xz: positive → order is such that the normal is +y when reversed
  const pts = ny > 0 ? p3 : p3.slice().reverse();
  g.poly(pts, [0, 1, 0], [1, 0, 0], [0, 0, 1]);
}
/** Quad whose normal is forced to have a positive y component (roof planes). */
export function quadUp(g, p0, p1, p2, p3, uvs = 1) {
  const ax = p1[0] - p0[0], ay = p1[1] - p0[1], az = p1[2] - p0[2], bx = p3[0] - p0[0], by = p3[1] - p0[1], bz = p3[2] - p0[2];
  const ny = az * bx - ax * bz;
  if (ny >= 0) g.quadP(p0, p1, p2, p3, 0, 0, uvs); else g.quadP(p0, p3, p2, p1, 0, 0, uvs);
}
/** Triangle with the normal forced to point along `out` (xz outward). */
export function triOut(g, p0, p1, p2, out) {
  const ax = p1[0] - p0[0], ay = p1[1] - p0[1], az = p1[2] - p0[2], bx = p2[0] - p0[0], by = p2[1] - p0[1], bz = p2[2] - p0[2];
  let nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
  const l = Math.hypot(nx, ny, nz) || 1;
  if (nx * out[0] + ny * out[1] + nz * out[2] < 0) { const t = p1; p1 = p2; p2 = t; nx = -nx; ny = -ny; nz = -nz; }
  const i0 = g.vert(p0[0], p0[1], p0[2], nx / l, ny / l, nz / l, p0[0] + p0[2], p0[1]);
  g.vert(p1[0], p1[1], p1[2], nx / l, ny / l, nz / l, p1[0] + p1[2], p1[1]);
  g.vert(p2[0], p2[1], p2[2], nx / l, ny / l, nz / l, p2[0] + p2[2], p2[1]);
  g.tri(i0, i0 + 1, i0 + 2);
}

/** Quad whose normal is forced to have a negative y component (undersides). */
export function quadDown(g, p0, p1, p2, p3, uvs = 1) {
  const ax = p1[0] - p0[0], az = p1[2] - p0[2], bx = p3[0] - p0[0], bz = p3[2] - p0[2];
  const ny = az * bx - ax * bz;
  if (ny <= 0) g.quadP(p0, p1, p2, p3, 0, 0, uvs); else g.quadP(p0, p3, p2, p1, 0, 0, uvs);
}
