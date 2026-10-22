// Near-band ground (20 m tiles, subdivided near roads for the light bake), trench holes, sidewalks and promenades.
import { KIND, WALL_OFFSET } from '../track/track.js';
import { extrudeRun } from './extrude.js';
import { levelOfSample } from './ctx.js';
import { SIDEWALK, BARRIER_T, GROUND_Y, CANAL, TRENCH_WALL } from './params.js';
import { edgeY } from './barriers.js';

const CELL = 20;

/** Lateral slot test for trench holes: returns true if (x,z) lies inside the open trench (expanded by `margin`). */
export function inTrenchHole(ctx, x, z, margin = 0) {
  const T = ctx.T, f = T.field(x, z, ctx._fh ??= {});
  const i = f.i; if (i < 0) return false;
  if (T.kind[i] === KIND.TUNNEL || T.py[i] >= -0.04) return false;
  const u = (x - T.px[i]) * T.rx[i] + (z - T.pz[i]) * T.rz[i], rh = Math.hypot(T.rx[i], T.rz[i]);
  return Math.abs(u / rh) < T.hw[i] + WALL_OFFSET + TRENCH_WALL + 0.1 + margin;
}

export function buildGround(ctx) {
  const T = ctx.T, Bd = T.layout.bounds;
  const x0 = Math.floor(Bd.x0 / CELL) * CELL, x1 = Math.ceil(Bd.x1 / CELL) * CELL, z0 = Math.floor(Bd.z0 / CELL) * CELL, z1 = Math.ceil(Bd.z1 / CELL) * CELL;
  const y = GROUND_Y;
  const quad = (g, ax, az, bx, bz) => {
    const i0 = g.vert(ax, y, az, 0, 1, 0, ax, az); g.vert(ax, y, bz, 0, 1, 0, ax, bz);
    g.vert(bx, y, bz, 0, 1, 0, bx, bz); g.vert(bx, y, az, 0, 1, 0, bx, az);
    g.quad(i0, i0 + 1, i0 + 2, i0 + 3);
  };
  let tiles = 0;
  for (let x = x0; x < x1; x += CELL) for (let z = z0; z < z1; z += CELL) {
    const cx = x + CELL / 2, cz = z + CELL / 2;
    if (cx > CANAL.x0 && cx < CANAL.x1) continue;
    const d = ctx.dist(cx, cz);
    if (d > 175) continue;
    const g = ctx.geo('gnd', ctx.chunkAt(cx, cz));
    g.color(0.55, 0.57, 0.6, 1); g.lv(0);
    // trench hole?
    let hole = false;
    for (let a = 0; a <= 4 && !hole; a++) for (let b = 0; b <= 4 && !hole; b++) if (inTrenchHole(ctx, x + a * CELL / 4, z + b * CELL / 4, 1.5)) hole = true;
    tiles++;
    if (!hole && d > 40) { quad(g, x, z, x + CELL, z + CELL); continue; }
    const n = hole ? 10 : 4, s = CELL / n;
    for (let a = 0; a < n; a++) for (let b = 0; b < n; b++) {
      const ax = x + a * s, az = z + b * s, bx = ax + s, bz = az + s;
      if (hole && (inTrenchHole(ctx, ax, az, 1) || inTrenchHole(ctx, bx, az, 1) || inTrenchHole(ctx, ax, bz, 1) || inTrenchHole(ctx, bx, bz, 1) || inTrenchHole(ctx, (ax + bx) / 2, (az + bz) / 2, 1))) continue;
      quad(g, ax, az, bx, bz);
    }
  }
  ctx.stats.groundTiles = tiles;
}

export function buildSidewalks(ctx) {
  const T = ctx.T, N = T.N;
  // classify
  const mode = new Uint8Array(N);   // 0 none, 1 sidewalk, 2 trench promenade
  for (let i = 0; i < N; i++) {
    const k = T.kind[i], yR = edgeY(T, i);
    if (k === KIND.TRENCH || (k === KIND.GROUND && T.py[i] < -0.04)) mode[i] = 2;
    else if (k === KIND.GROUND && yR < 0.3 && yR > -0.04) mode[i] = 1;
  }
  const poly = (i) => {
    const B = T.hw[i] + WALL_OFFSET, m = mode[i], yR = edgeY(T, i), zn = T.zoneNames[T.zone[i]];
    if (m === 2) {
      const u0 = B + TRENCH_WALL + 0.1, u1 = u0 + 4.5, hs = -yR + 0.1, hg = -yR - 0.06;
      return [{ key: 'pave', pts: [[u0, hg], [u1, hg], [u1, hs], [u0, hs]], col: [0.7, 0.72, 0.76, 1] }];
    }
    const W = SIDEWALK[zn] ?? 5, u0 = B + BARRIER_T, u1 = u0 + W, hs = 0.15 - yR, hg = -0.06 - yR;
    return [{ key: 'pave', pts: [[u0, hg], [u1, hg], [u1, hs], [u0, hs]], col: [0.85, 0.86, 0.9, 1] }];
  };
  let a = -1;
  for (let i = 0; i <= N; i++) {
    const m = i < N ? mode[i] : 0;
    if (a >= 0 && (m !== mode[a])) { extrudeRun(ctx, poly, a, i, { lvlFn: (ii) => levelOfSample(T, ii) }); a = -1; }
    if (a < 0 && m > 0) a = i;
  }
}
