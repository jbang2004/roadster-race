// Night-market dressing: awnings, hanging cables with string lights, food stalls with steam, AC units, pipes, street steam vents.
import { KIND, WALL_OFFSET } from '../track/track.js';
import { SIDEWALK, BARRIER_T } from './params.js';
import { mulberry32, clamp, lerp } from './util.js';
import { beam, addSteam, quadUp, quadDown } from './prims.js';
import { addHalo } from './signs.js';

const rr = (rnd, a, b) => a + (b - a) * rnd();
const PAIRS = [[[.55, .08, .06], [.6, .56, .5]], [[.08, .16, .5], [.6, .6, .62]], [[.08, .4, .2], [.62, .58, .4]], [[.62, .3, .05], [.62, .5, .12]], [[.5, .06, .3], [.12, .4, .5]], [[.5, .5, .1], [.1, .1, .12]]];
const BULB = [[1, .75, .4], [1, .35, .7], [.4, .9, 1], [.6, 1, .5], [1, .3, .2]];

function frame(T, i) {
  const th = Math.hypot(T.tx[i], T.tz[i]), rh = Math.hypot(T.rx[i], T.rz[i]);
  return { t: [T.tx[i] / th, T.tz[i] / th], r: [T.rx[i] / rh, T.rz[i] / rh], p: [T.px[i], T.py[i], T.pz[i]], hw: T.hw[i] };
}

/** Striped awning: top + underside quads (alternating stripes), valance, and a warm light strip underneath. */
function awning(ctx, ch, P0, P1, nrm, proj, yTop, yLow, pair, rnd, withLight) {
  const g = ctx.geo('paint', ch); g.lv(0);
  const L = Math.hypot(P1[0] - P0[0], P1[2] - P0[2]), n = Math.max(2, Math.round(L / .6)), ax = (P1[0] - P0[0]) / n, az = (P1[2] - P0[2]) / n;
  for (let k = 0; k < n; k++) {
    const c = pair[k & 1]; g.color(c[0], c[1], c[2], 1);
    const x0 = P0[0] + ax * k, z0 = P0[2] + az * k, x1 = x0 + ax, z1 = z0 + az;
    quadUp(g, [x0, yTop, z0], [x1, yTop, z1], [x1 + nrm[0] * proj, yLow, z1 + nrm[1] * proj], [x0 + nrm[0] * proj, yLow, z0 + nrm[1] * proj], 1);
    // underside (darker), reversed
    g.color(c[0] * .35, c[1] * .35, c[2] * .35, 1);
    quadDown(g, [x0, yTop - .03, z0], [x1, yTop - .03, z1], [x1 + nrm[0] * proj, yLow - .03, z1 + nrm[1] * proj], [x0 + nrm[0] * proj, yLow - .03, z0 + nrm[1] * proj], 1);
    // valance flap: faces outward (nrm)
    g.color(c[0], c[1], c[2], 1);
    const q0 = [x0 + nrm[0] * proj, yLow, z0 + nrm[1] * proj], q1 = [x1 + nrm[0] * proj, yLow, z1 + nrm[1] * proj];
    const nx = (q1[2] - q0[2]), nz = -(q1[0] - q0[0]);             // candidate normal of (q0→q1)×up
    const fw = nx * nrm[0] + nz * nrm[1] < 0;
    const a = fw ? q0 : q1, b = fw ? q1 : q0;
    g.quadP([a[0], yLow - .22, a[2]], [b[0], yLow - .22, b[2]], [b[0], yLow, b[2]], [a[0], yLow, a[2]], 0, 0);
  }
  const ge = ctx.geo('em2', ch); ge.lv(0); ge.color(.6, .38, .18, 1);
  const mx = (P0[0] + P1[0]) / 2 + nrm[0] * (proj - .1), mz = (P0[2] + P1[2]) / 2 + nrm[1] * (proj - .1);
  ge.box(mx, yLow - .08, mz, L - .3, .05, .09, Math.atan2(-(P1[2] - P0[2]), P1[0] - P0[0]), 'xXzZy');
  if (withLight) ctx.light({ pos: [mx + nrm[0] * .2, yLow - .35, mz + nrm[1] * .2], color: [1, .68, .38], intensity: 70, range: 9, kind: 'neon' }, 0);
}

export function buildMarket(ctx) {
  const T = ctx.T, N = T.N, rnd = mulberry32(6001);
  const SW = SIDEWALK.market;
  const zn = (i) => T.zoneNames[T.zone[i]];
  // ---------------- per-building dressing ----------------
  let nAw = 0;
  for (const b of ctx.buildings) {
    if (b.zone !== 'market' || b.row !== 0 || b.dist > 90 || !b.tiers) continue;
    const ch = b.ch, nrm = [-b.ez[0], -b.ez[1]], right = [nrm[1], -nrm[0]];
    const fc = [b.cx + nrm[0] * b.d / 2, b.cz + nrm[1] * b.d / 2];
    const F = (a, y, off = 0) => [fc[0] + right[0] * a + nrm[0] * off, y, fc[1] + right[1] * a + nrm[1] * off];
    // awning over the shopfront
    if (rnd() < .8) {
      const aw = clamp(b.w - .5 - rnd() * 1.2, 2.2, b.w - .3), off = (rnd() - .5) * (b.w - aw);
      const pair = PAIRS[Math.floor(rnd() * PAIRS.length)];
      awning(ctx, ch, F(off - aw / 2, 3.15, .03), F(off + aw / 2, 3.15, .03), nrm, 1.55 + rnd() * .35, 3.15, 2.6, pair, rnd, nAw++ % 3 === 0);
    }
    // AC units + pipes on the street facade
    const gs = ctx.geo('steel', ch); gs.lv(0);
    const nA = 2 + Math.floor(rnd() * 5), floors = Math.max(1, Math.floor((Math.min(b.h, b.tiers[0].yt) - b.podH) / b.floorH));
    const rot = Math.atan2(-right[1], right[0]);
    for (let k = 0; k < nA; k++) {
      const a = (rnd() - .5) * (b.w - 1.4), y = b.podH + .9 + b.floorH * Math.floor(rnd() * floors) + (rnd() < .5 ? 0 : .8);
      if (y > b.h - 2) continue;
      const c = F(a, y, .25);
      gs.color(.34, .36, .4, 1); gs.box(c[0], c[1], c[2], .9, .6, .45, rot);
      const f = F(a, y, .5); gs.color(.05, .05, .06, 1); gs.box(f[0], f[1], f[2], .6, .42, .04, rot);
      if (rnd() < .3) { gs.color(.2, .2, .22, 1); const br = F(a + .55, y - .5, .2); gs.box(br[0], br[1], br[2], .05, 1.6, .05, rot); }
    }
    if (rnd() < .7) {
      const a = (rnd() - .5) * (b.w - 1), c = F(a, 0, .12);
      gs.color(.16, .16, .18, 1); gs.cyl(c[0], 0, c[2], .08, .08, Math.min(b.h - 1, 6 + rnd() * 14), 6, true);
    }
  }
  // ---------------- per-track dressing ----------------
  let a0 = -1;
  const runs = [];
  for (let i = 0; i <= N; i++) {
    const m = i < N && zn(i) === 'market' && T.kind[i] === KIND.GROUND;
    if (m && a0 < 0) a0 = i;
    if (!m && a0 >= 0) { runs.push([a0, i]); a0 = -1; }
  }
  let nStr = 0, nStall = 0;
  for (const [i0, i1] of runs) {
    // hanging cables across the street
    for (let i = i0 + 8; i < i1 - 8; i += Math.floor(rr(rnd, 10, 17))) {
      const f = frame(T, i), B = f.hw + WALL_OFFSET + BARRIER_T + SW + 0.12;
      const ch = ctx.chunkOfI(i);
      const ptL = [f.p[0] - f.r[0] * (B + 1.2), f.p[2] - f.r[1] * (B + 1.2)], ptR = [f.p[0] + f.r[0] * (B + 1.2), f.p[2] + f.r[1] * (B + 1.2)];
      if (!ctx.occ.get(ptL[0], ptL[1]) || !ctx.occ.get(ptR[0], ptR[1])) continue;
      const yL = rr(rnd, 7.5, 12.5), yR = rr(rnd, 7.5, 12.5);
      const A = [f.p[0] - f.r[0] * B, yL, f.p[2] - f.r[1] * B], C = [f.p[0] + f.r[0] * B, yR, f.p[2] + f.r[1] * B];
      const g = ctx.geo('paint', ch); g.lv(0); g.color(.03, .03, .035, 1);
      const nC = 2 + Math.floor(rnd() * 3), strings = rnd() < .35;
      for (let c = 0; c < nC; c++) {
        const so = (c - (nC - 1) / 2) * .22, sag = rr(rnd, .5, 1.3), dy = rr(rnd, -.25, .25);
        const S = 6; let prev = null;
        for (let k = 0; k <= S; k++) {
          const t = k / S, p = [lerp(A[0], C[0], t) + f.t[0] * so, lerp(A[1], C[1], t) - 4 * sag * t * (1 - t) + dy, lerp(A[2], C[2], t) + f.t[1] * so];
          if (prev) beam(g, prev, p, .05, .05, [0, 1, 0], false);
          prev = p;
        }
        if (strings && c === 0) {
          const ge = ctx.geo('em6', ch); ge.lv(0);
          const Ls = 2 * B, nb = Math.floor(Ls / 1.15), c1 = BULB[Math.floor(rnd() * BULB.length)], c2 = BULB[Math.floor(rnd() * BULB.length)];
          for (let k = 1; k < nb; k++) {
            const t = k / nb, p = [lerp(A[0], C[0], t) + f.t[0] * so, lerp(A[1], C[1], t) - 4 * sag * t * (1 - t) + dy - .12, lerp(A[2], C[2], t) + f.t[1] * so];
            const cc = k & 1 ? c1 : c2; ge.color(cc[0], cc[1], cc[2], 1); ge.box(p[0], p[1], p[2], .13, .17, .13, 0);
            if (k % 3 === 0) addHalo(ctx, ch, p[0], p[1], p[2], .9, cc[0] * .22, cc[1] * .22, cc[2] * .22);
          }
          const cm = BULB[Math.floor(rnd() * 2)];
          ctx.light({ pos: [(A[0] + C[0]) / 2, (A[1] + C[1]) / 2 - sag - .6, (A[2] + C[2]) / 2], color: cm, intensity: 85, range: 14, kind: 'neon' }, 0);
          nStr++;
        }
      }
    }
    // food stalls on the sidewalk with steam
    for (let i = i0 + 14; i < i1 - 14; i += Math.floor(rr(rnd, 20, 30))) {
      const f = frame(T, i), sd = rnd() < .5 ? 1 : -1, FU = f.hw + WALL_OFFSET + BARRIER_T + SW;
      const u = sd * (FU - 0.85);
      const x = f.p[0] + f.r[0] * u, z = f.p[2] + f.r[1] * u, py = 0.15;
      if (!ctx.occ.get(x + f.r[0] * sd * 1.3, z + f.r[1] * sd * 1.3) || T.curv[i] * T.curv[i] > 1 / (90 * 90)) continue;
      const ch = ctx.chunkOfI(i), rot = Math.atan2(-f.t[1], f.t[0]);
      const gp = ctx.geo('paint', ch); gp.lv(0); gp.color(.26, .26, .3, 1);
      gp.box(x, py + .45, z, 2.1, .9, .9, rot);
      const gs = ctx.geo('steel', ch); gs.lv(0); gs.color(.55, .56, .6, 1); gs.box(x, py + .93, z, 2.15, .06, .95, rot, 'Y');
      const pair = PAIRS[Math.floor(rnd() * PAIRS.length)], nrm = [-f.r[0] * sd, -f.r[1] * sd];   // towards the road
      // canopy: slopes down towards the road
      const hx = f.t[0] * 1.3, hz = f.t[1] * 1.3, back = [x - nrm[0] * .6, z - nrm[1] * .6], front = [x + nrm[0] * 1.15, z + nrm[1] * 1.15];
      const gc = ctx.geo('paint', ch); gc.lv(0);
      for (let k = 0; k < 4; k++) {
        const c = pair[k & 1]; gc.color(c[0], c[1], c[2], 1);
        const s0 = -1 + k * .5, s1 = s0 + .5;
        quadUp(gc, [back[0] + hx * s0, py + 2.35, back[1] + hz * s0], [back[0] + hx * s1, py + 2.35, back[1] + hz * s1], [front[0] + hx * s1, py + 2.05, front[1] + hz * s1], [front[0] + hx * s0, py + 2.05, front[1] + hz * s0], 1);
      }
      gs.color(.2, .2, .22, 1);
      for (const s of [-1.3, 1.3]) gs.box(front[0] + f.t[0] * s, py + 1.03, front[1] + f.t[1] * s, .06, 2.05, .06, 0);
      const ge = ctx.geo('em6', ch); ge.lv(0);
      for (let k = -2; k <= 2; k++) { ge.color(1, .72, .4, 1); ge.box(x + nrm[0] * .85 + f.t[0] * k * .5, py + 1.95, z + nrm[1] * .85 + f.t[1] * k * .5, .12, .12, .12, 0); }
      for (const s of [-1, 1]) { ge.color(1, .15, .08, 1); const lp = [front[0] + f.t[0] * s * .9, py + 1.75, front[1] + f.t[1] * s * .9]; ge.box(lp[0], lp[1], lp[2], .22, .3, .22, 0); addHalo(ctx, ch, lp[0], lp[1], lp[2], 1.0, .35, .04, .02); }
      ctx.light({ pos: [x + nrm[0] * .9, py + 1.9, z + nrm[1] * .9], color: [1, .66, .36], intensity: 75, range: 9, kind: 'neon' }, 0);
      addSteam(ctx, ch, x + f.t[0] * .3, py + 1.0, z + f.t[1] * .3, { n: 5, h: 3.2, size: .55, speed: .17, seed: nStall });
      nStall++;
    }
  }
  // steam vents in the gutters (street, docks, market, boulevard)
  for (let i = 40; i < N; i += 83 + Math.floor(rnd() * 40)) {
    const z = zn(i); if (T.kind[i] !== KIND.GROUND || !(z === 'market' || z === 'street' || z === 'docks' || z === 'boulevard')) continue;
    const f = frame(T, i), sd = rnd() < .5 ? 1 : -1, u = sd * (f.hw - .6);
    addSteam(ctx, ctx.chunkOfI(i), f.p[0] + f.r[0] * u, .08, f.p[2] + f.r[1] * u, { n: 6, h: 6.5, size: 1.5, speed: .09, seed: i });
  }
  ctx.stats.awnings = nAw; ctx.stats.stalls = nStall; ctx.stats.strings = nStr;
}
