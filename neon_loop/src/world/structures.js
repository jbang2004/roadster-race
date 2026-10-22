// Structures: elevated deck, piers, abutments, hump bridge, tunnel portals, canal (quay walls, water, culverts).
import * as THREE from 'three';
import { KIND, WALL_OFFSET } from '../track/track.js';
import { extrudeRun } from './extrude.js';
import { CHUNK } from './ctx.js';
import { CEIL_H } from './barriers.js';
import { CANAL, BARRIER_T } from './params.js';
import { hash2, mulberry32 } from './util.js';

const CONC = [0.55, 0.56, 0.6, 1], DARKC = [0.4, 0.41, 0.45, 1];

function runsOf(T, pred) {
  const N = T.N, out = [];
  let a = -1;
  for (let i = 0; i <= N; i++) {
    const ok = i < N && pred(i);
    if (ok && a < 0) a = i;
    if (!ok && a >= 0) { out.push([a, i]); a = -1; }
  }
  return out;
}

export function buildDeck(ctx) {
  const T = ctx.T;
  const decks = runsOf(T, (i) => T.kind[i] === KIND.ELEVATED && T.py[i] >= 5.0);
  ctx.decks = decks;
  for (const [i0, i1] of decks) {
    extrudeRun(ctx, (i) => {
      const W = T.hw[i] + WALL_OFFSET + 0.7;
      return [{ key: 'rib', pts: [[-(W - 1.7), -2.2], [W - 1.7, -2.2], [W, -0.7], [W, -0.04], [-W, -0.04], [-W, -0.7]], col: [0.6, 0.62, 0.66, 1], uvs: 0.8 }];
    }, i0, i1, { sides: [0], lvlFn: () => 0 });
    // underside: dark bearing strip + expansion joints every 36 m
    for (let i = i0 + 18; i < i1; i += 36) {
      const W = T.hw[i] + WALL_OFFSET + 0.7, ch = ctx.chunkOfI(i), g = ctx.geo('paint', ch);
      g.lv(0); g.color(0.03, 0.03, 0.035, 1);
      const ry = Math.atan2(-T.tz[i], T.tx[i]);
      g.box(T.px[i] + T.ux[i] * -2.19, T.py[i] - 2.19, T.pz[i] + T.uz[i] * -2.19, 0.3, 0.04, 2 * W - 3.4, ry);
    }
  }
  // abutments where the fill ends and the deck takes over
  for (const [i0, i1] of decks) {
    for (const [i, dir] of [[i0, 1], [i1 - 1, -1]]) {
      const W = T.hw[i] + WALL_OFFSET + 0.7, ch = ctx.chunkOfI(i), g = ctx.geo('conc', ch);
      g.lv(0); g.color(...DARKC);
      const ry = Math.atan2(-T.tz[i], T.tx[i]);
      const hgt = T.py[i] - 2.2 + 0.1;
      g.box(T.px[i] + T.tx[i] * dir * 0.9, hgt / 2, T.pz[i] + T.tz[i] * dir * 0.9, 1.8, hgt, 2 * W, ry);
    }
  }
}

export function buildPiers(ctx) {
  const T = ctx.T, rnd = mulberry32(77);
  const tmp = {};
  const groundFree = (x, z, margin) => T.field(x, z, tmp).ground > margin;
  ctx.piers = [];
  for (const [i0, i1] of ctx.decks) {
    let s = i0 + 14;
    while (s < i1 - 6) {
      let i = s, ok = false;
      for (const d of [0, 3, -3, 6, -6, 9, -9, 12, -12, 15, -15, 18]) {
        const j = s + d; if (j < i0 + 4 || j > i1 - 4) continue;
        const x = T.px[j], z = T.pz[j];
        if (!groundFree(x, z, 4.0)) continue;
        if (!groundFree(x + T.tx[j] * 1.5, z + T.tz[j] * 1.5, 3.0) || !groundFree(x - T.tx[j] * 1.5, z - T.tz[j] * 1.5, 3.0)) continue;
        if ((x > CANAL.x0 - 4 && x < CANAL.x0) || (x > CANAL.x1 && x < CANAL.x1 + 4)) continue;
        i = j; ok = true; break;
      }
      if (ok) ctx.piers.push(i);
      s = (ok ? i : s) + 30 + Math.floor(rnd() * 5);
    }
  }
  for (const i of ctx.piers) {
    const W = T.hw[i] + WALL_OFFSET + 0.7, ch = ctx.chunkOfI(i), g = ctx.geo('conc', ch);
    g.lv(0); g.color(...CONC);
    const ry = Math.atan2(-T.tz[i], T.tx[i]);
    const x = T.px[i], z = T.pz[i];
    const inCanal = x > CANAL.x0 && x < CANAL.x1, base = inCanal ? CANAL.bed : 0;
    const top = T.py[i] - 2.2;
    // cap beam (hammerhead) + flare + column
    const capH = 1.7;
    g.box(x, top - capH / 2, z, 2.6, capH, 2 * W - 2.0, ry);
    g.box(x, top - capH - 1.1, z, 2.2, 2.2, 5.2, ry);
    const colH = top - capH - 2.2 - base;
    if (colH > 0.2) g.box(x, base + colH / 2, z, 2.0, colH, 3.0, ry);
    // footing
    g.box(x, base + 0.3, z, 3.6, 0.6, 4.4, ry);
  }
}

/** Hump bridge over the canal (BRIDGE kind): arched girder underside. */
export function buildBridges(ctx) {
  const T = ctx.T;
  for (const [i0, i1] of runsOf(T, (i) => T.kind[i] === KIND.BRIDGE)) {
    extrudeRun(ctx, (i) => {
      const t = (i - i0) / Math.max(1, i1 - i0), d = 0.9 + 1.6 * Math.pow(2 * t - 1, 2), W = T.hw[i] + WALL_OFFSET + 0.7;
      return [{ key: 'conc', pts: [[-(W - .8), -d], [W - .8, -d], [W, -0.5], [W, -0.04], [-W, -0.04], [-W, -0.5]], col: [0.5, 0.52, 0.56, 1] }];
    }, i0, i1, { sides: [0], lvlFn: () => 0 });
  }
}

/** Tunnel portals / headwalls at both ends. */
export function buildPortals(ctx) {
  const T = ctx.T, N = T.N;
  for (const [i0, i1] of runsOf(T, (i) => T.kind[i] === KIND.TUNNEL)) {
    for (const [i, dir] of [[i0, 1], [i1 - 1, -1]]) {
      const B = T.hw[i] + WALL_OFFSET, ch = ctx.chunkOfI(i), g = ctx.geo('conc', ch);
      g.lv(0); g.color(0.5, 0.52, 0.56, 1);
      const ry = Math.atan2(-T.tz[i], T.tx[i]);
      const ty = T.py[i], thick = 2.4, topY = 2.1;
      const cx = T.px[i] + T.tx[i] * dir * thick * 0.5 - T.tx[i] * dir * 0.0, cz = T.pz[i] + T.tz[i] * dir * thick * 0.5;
      const wingW = 7.5;
      // wings (left/right of the opening) from road-0.6 to topY
      const hWing = topY - (ty - 0.6);
      for (const sd of [1, -1]) {
        const u = sd * (B + wingW / 2 - 0.0);
        g.box(cx + T.rx[i] * u, (ty - 0.6) + hWing / 2, cz + T.rz[i] * u, thick, hWing, wingW, ry);
      }
      // lintel above the opening
      const lh = topY - (ty + CEIL_H - 1.2);
      if (lh > 0) g.box(cx, ty + CEIL_H - 1.2 + lh / 2, cz, thick, lh, 2 * B, ry);
    }
  }
}

// ---------------- canal ----------------
export function buildCanal(ctx, { culvert = false } = {}) {   // K's far-field canal continues beyond the bounds, so the ends stay open by default
  const T = ctx.T, Bd = T.layout.bounds, z0 = Bd.z0, z1 = Bd.z1;
  const { x0, x1, bed } = CANAL;
  const SEG = 8, ROWS = 4;
  for (let z = z0; z < z1; z += SEG) {
    const zb = Math.min(z + SEG, z1), zm = (z + zb) / 2;
    const ch = ctx.chunkAt(x0 + 40, zm), g = ctx.geo('conc', ch);
    g.lv(0); g.color(0.46, 0.5, 0.52, 1);
    // west wall (face towards +x), east wall (face towards -x), subdivided rows for the bake
    for (let r = 0; r < ROWS; r++) {
      const ya = bed + (0 - bed) * r / ROWS, yb = bed + (0 - bed) * (r + 1) / ROWS;
      g.quadP([x0, ya, zb], [x0, ya, z], [x0, yb, z], [x0, yb, zb], 0, ya);        // west wall, normal +x
      g.quadP([x1, ya, z], [x1, ya, zb], [x1, yb, zb], [x1, yb, z], 0, ya);        // east wall, normal -x
    }
    // coping slabs
    g.color(0.62, 0.64, 0.68, 1);
    g.box(x0 - 0.45, -0.1, zm, 1.7, 0.4, zb - z, 0, 'xXyYzZ');
    g.box(x1 + 0.45, -0.1, zm, 1.7, 0.4, zb - z, 0, 'xXyYzZ');
  }
  // culvert walls at the ends of the dressed area (canal continues into the dark)
  for (const [zz, dir] of culvert ? [[z0, 1], [z1, -1]] : []) {
    const ch = ctx.chunkAt((x0 + x1) / 2, zz), g = ctx.geo('conc', ch);
    g.lv(0); g.color(0.42, 0.44, 0.48, 1);
    const wid = x1 - x0 + 6, hgt = 8.2;
    g.box((x0 + x1) / 2, bed + hgt / 2 - 0.2, zz - dir * 1.5, wid, hgt, 3.0, 0);
    const p = ctx.geo('paint', ch); p.lv(0); p.color(0.004, 0.005, 0.006, 1);
    // arch opening (dark): half-ellipse polygon facing the canal
    const cx = (x0 + x1) / 2, yb0 = bed + 0.2, yTop = -0.8, rw = (x1 - x0) / 2 - 3;
    const pts = [];
    for (let k = 0; k <= 16; k++) { const a = Math.PI * k / 16; pts.push([cx + Math.cos(a) * rw, yb0 + (yTop - yb0 - 3.5) + Math.sin(a) * 3.5 + 0.0]); }
    const poly = [[cx + rw, yb0, zz + dir * 0.02], ...pts.map(q => [q[0], q[1], zz + dir * 0.02]), [cx - rw, yb0, zz + dir * 0.02]];
    const n = [0, 0, dir];
    // CCW from the front (viewer at +dir*z): order x decreasing when dir>0?
    const ordered = dir > 0 ? poly : poly.slice().reverse();
    p.poly(ordered, n, [1, 0, 0], [0, 1, 0]);
    // cap the top of the wall so it reads as a solid
  }
}

/** Water surface (one plane per 100 m chunk, subdivided for the bake). */
export function buildWater(ctx) {
  const T = ctx.T, Bd = T.layout.bounds, z0 = Bd.z0, z1 = Bd.z1;
  const { x0, x1, water } = CANAL;
  const CS = 8;
  for (let z = z0; z < z1; z += CS) {
    const zb = Math.min(z + CS, z1), ch = ctx.chunkAt(x0 + 40, (z + zb) / 2), g = ctx.geo('water', ch);
    g.lv(0); g.color(1, 1, 1, 1);
    const nx = 8, sx = (x1 - x0 + 0.4) / nx;
    for (let a = 0; a < nx; a++) {
      const ax = x0 - 0.2 + a * sx, bx = ax + sx;
      const i0 = g.vert(ax, water, z, 0, 1, 0, ax, z); g.vert(ax, water, zb, 0, 1, 0, ax, zb);
      g.vert(bx, water, zb, 0, 1, 0, bx, zb); g.vert(bx, water, z, 0, 1, 0, bx, z);
      g.quad(i0, i0 + 1, i0 + 2, i0 + 3);
    }
  }
}
