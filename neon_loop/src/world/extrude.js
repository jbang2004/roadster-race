// Extrusion of 2D cross-section polygons along the track.
// A polygon is a list of [u, h] points, counter-clockwise with u = lateral (+ right of the centreline) and h = up from the road
// surface at the sample (road up vector, so banking is included). Side walls get flat normals; faces are emitted for every edge.
// `polys(i)` returns [{ key, pts, col?, vOff?, uvs? }] for the RIGHT side (u > 0); the left side is the mirror image.
import { CHUNK } from './ctx.js';

/**
 * ctx, polys(i) → polygons, i0..i1 (sample indices, may wrap past N), opts:
 *   sides: [1,-1] (default) | [0] (as given, not mirrored)
 *   lvl: light level for the bake (default from `lvlFn(i)` or 0), caps: true|false
 */
export function extrudeRun(ctx, polys, i0, i1, opts = {}) {
  const T = ctx.T, N = T.N, sides = opts.sides ?? [1, -1], caps = opts.caps ?? true, step = opts.step ?? 1;
  const lvlOf = opts.lvlFn ?? (() => opts.lvl ?? 0);
  for (const side of sides) {
    let st = [];
    const first = polys(((i0 % N) + N) % N);
    const np = first.length;
    const mirrorPts = (pts) => side < 0 ? pts.map(p => [-p[0], p[1]]).reverse() : pts;
    for (let ii = i0; ii < i1; ii += step) {
      const i = ((ii % N) + N) % N, j = (((ii + step) % N) + N) % N;
      const list = polys(i);
      const listB = step === 1 ? polys(j) : list;
      const ch = Math.floor(i / CHUNK);
      for (let k = 0; k < np; k++) {
        let pa = list[k], pb = listB[k] ?? pa;
        if (!pa || pa.pts.length < 3) continue;
        if (pb.pts.length < 3) pb = pa;
        const A = mirrorPts(pa.pts), B = mirrorPts(pb.pts);
        const g = ctx.geo(pa.key, ch);
        g.lv(lvlOf(i));
        const c = pa.col; if (c) g.color(c[0], c[1], c[2], c[3] ?? 1); else g.color(1, 1, 1, 1);
        if (pa.ex) for (const e in pa.ex) g.ex(e, ...pa.ex[e]);
        const n = A.length;
        // cumulative perimeter for v
        let v = pa.vOff ?? 0;
        const uvs = pa.uvs ?? 1;
        const s0 = ii * T.ds * uvs, s1 = (ii + step) * T.ds * uvs;
        for (let e = 0; e < n; e++) {
          const a0 = A[e], a1 = A[(e + 1) % n], b0 = B[e], b1 = B[(e + 1) % n];
          const du = a1[0] - a0[0], dh = a1[1] - a0[1], L = Math.hypot(du, dh);
          if (L < 1e-5) continue;
          const nu = dh / L, nh = -du / L;
          const nx = T.rx[i] * nu + T.ux[i] * nh, ny = T.ry[i] * nu + T.uy[i] * nh, nz = T.rz[i] * nu + T.uz[i] * nh;
          const jx = T.rx[j] * nu + T.ux[j] * nh, jy = T.ry[j] * nu + T.uy[j] * nh, jz = T.rz[j] * nu + T.uz[j] * nh;
          const q0 = g.vert(T.px[i] + T.rx[i] * a0[0] + T.ux[i] * a0[1], T.py[i] + T.ry[i] * a0[0] + T.uy[i] * a0[1], T.pz[i] + T.rz[i] * a0[0] + T.uz[i] * a0[1], nx, ny, nz, s0, v * uvs);
          const q1 = g.vert(T.px[j] + T.rx[j] * b0[0] + T.ux[j] * b0[1], T.py[j] + T.ry[j] * b0[0] + T.uy[j] * b0[1], T.pz[j] + T.rz[j] * b0[0] + T.uz[j] * b0[1], jx, jy, jz, s1, v * uvs);
          const q2 = g.vert(T.px[j] + T.rx[j] * b1[0] + T.ux[j] * b1[1], T.py[j] + T.ry[j] * b1[0] + T.uy[j] * b1[1], T.pz[j] + T.rz[j] * b1[0] + T.uz[j] * b1[1], jx, jy, jz, s1, (v + L) * uvs);
          const q3 = g.vert(T.px[i] + T.rx[i] * a1[0] + T.ux[i] * a1[1], T.py[i] + T.ry[i] * a1[0] + T.uy[i] * a1[1], T.pz[i] + T.rz[i] * a1[0] + T.uz[i] * a1[1], nx, ny, nz, s0, (v + L) * uvs);
          g.quad(q0, q1, q2, q3);
          v += L;
        }
      }
    }
    if (caps) {
      for (const [ii, dir] of [[i0, -1], [i1, 1]]) {
        const i = ((ii % N) + N) % N;
        const list = polys(i);
        for (let k = 0; k < np; k++) {
          const p = list[k]; if (!p || p.nocap || p.pts.length < 3) continue;
          const pts = mirrorPts(p.pts);
          const g = ctx.geo(p.key, Math.floor(((ii - (dir > 0 ? 1 : 0)) % N + N) % N / CHUNK));
          g.lv(lvlOf(i));
          const c = p.col; if (c) g.color(c[0], c[1], c[2], c[3] ?? 1); else g.color(1, 1, 1, 1);
          if (p.ex) for (const e in p.ex) g.ex(e, ...p.ex[e]);
          const nx = T.tx[i] * dir, ny = T.ty[i] * dir, nz = T.tz[i] * dir;
          const i0v = g.n;
          const order = dir < 0 ? pts : pts.slice().reverse();
          for (const q of order) {
            g.vert(T.px[i] + T.rx[i] * q[0] + T.ux[i] * q[1], T.py[i] + T.ry[i] * q[0] + T.uy[i] * q[1], T.pz[i] + T.rz[i] * q[0] + T.uz[i] * q[1], nx, ny, nz, q[0], q[1]);
          }
          for (let m = 1; m < order.length - 1; m++) g.tri(i0v, i0v + m, i0v + m + 1);
        }
      }
    }
  }
}
