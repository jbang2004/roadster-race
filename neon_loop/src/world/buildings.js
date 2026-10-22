// City generator: frontage lots along every road (rows of buildings stepping back from the road), district styles, facade quads with
// per-vertex style attributes (see facade_mat.js), roofs with props. Everything merges into the chunked geometry of ctx.
import { KIND, WALL_OFFSET } from '../track/track.js';
import { mulberry32, hash2, clamp, lerp } from './util.js';
import { SIDEWALK, BARRIER_T, CANAL, DOCKS } from './params.js';
import { placeWarehouse, placeYard } from './docks.js';

// style ids: 0 glass curtain, 1 punched concrete, 2 brutalist slits, 3 industrial, 4 tenement, 5 LED tower, 6 shopfront
const ZONES = {
  boulevard: { w: [22, 38], d: [26, 42], h: [45, 150], hBack: [90, 230], styles: [[0, .62], [5, .1], [1, .2], [2, .08]], floor: [3.7, 4.3], bay: [2.6, 3.4], lit: [.1, .42], hues: [.5, .88, .76], pod: [.8, 5, 9], mat: 'bldgA', rows: 4, gap: [0, 10] },
  street: { w: [16, 30], d: [22, 34], h: [30, 85], hBack: [60, 160], styles: [[0, .3], [1, .45], [2, .1], [4, .15]], floor: [3.5, 4.0], bay: [2.8, 3.6], lit: [.15, .5], hues: [.5, .55, .1], pod: [.9, 4.5, 6], mat: 'bldgA', rows: 4, gap: [0, 8] },
  docks: { w: [28, 60], d: [26, 44], h: [9, 22], hBack: [16, 50], styles: [[3, .62], [1, .2], [2, .18]], floor: [5.5, 7.5], bay: [6, 9], lit: [.05, .22], hues: [.09, .5, .12], pod: [.15, 4.5, 5], mat: 'bldgC', rows: 4, gap: [2, 14] },
  ramp: { w: [18, 34], d: [22, 36], h: [26, 70], hBack: [50, 130], styles: [[1, .45], [0, .25], [3, .15], [2, .15]], floor: [3.5, 4.0], bay: [3, 3.8], lit: [.12, .4], hues: [.5, .88, .1], pod: [.5, 4.5, 6], mat: 'bldgA', rows: 4, gap: [2, 12] },
  expressway: { w: [20, 40], d: [24, 40], h: [28, 95], hBack: [60, 190], styles: [[0, .5], [1, .25], [2, .1], [5, .08], [4, .07]], floor: [3.6, 4.2], bay: [2.8, 3.4], lit: [.12, .45], hues: [.5, .88, .76, .55], pod: [.4, 5, 8], mat: 'bldgA', rows: 4, gap: [0, 18] },
  descent: { w: [18, 34], d: [22, 34], h: [20, 55], hBack: [40, 110], styles: [[1, .5], [0, .2], [3, .15], [2, .15]], floor: [3.5, 4.0], bay: [3, 3.8], lit: [.1, .35], hues: [.5, .1], pod: [.3, 4.5, 6], mat: 'bldgA', rows: 4, gap: [2, 12] },
  tunnel: { w: [24, 44], d: [26, 40], h: [30, 90], hBack: [60, 150], styles: [[0, .5], [1, .3], [2, .2]], floor: [3.6, 4.0], bay: [3, 3.6], lit: [.1, .35], hues: [.5, .88], pod: [.2, 4.5, 6], mat: 'bldgA', rows: 4, gap: [4, 16] },
  market: { w: [5, 9], d: [14, 22], h: [14, 30], hBack: [30, 90], styles: [[4, .75], [1, .25]], floor: [2.9, 3.3], bay: [2.4, 3.0], lit: [.35, .75], hues: [.06, .92, .35, .12], pod: [1.0, 3.6, 4.4], mat: 'bldgB', rows: 4, gap: [0, 0], deep: true },
};

const pickW = (rnd, list) => { let r = rnd(), a = 0; for (const [v, p] of list) { a += p; if (r <= a) return v; } return list[0][0]; };
const rr = (rnd, a, b) => a + (b - a) * rnd();
const TINTS = [[.5, .52, .58], [.58, .55, .5], [.45, .5, .56], [.62, .6, .58], [.4, .42, .48], [.55, .5, .46]];

export class Occ {
  constructor(bounds, cell = 2) { this.b = bounds; this.c = cell; this.w = Math.ceil((bounds.x1 - bounds.x0) / cell); this.h = Math.ceil((bounds.z1 - bounds.z0) / cell); this.a = new Uint8Array(this.w * this.h); }
  idx(x, z) { const gx = Math.floor((x - this.b.x0) / this.c), gz = Math.floor((z - this.b.z0) / this.c); return (gx < 0 || gz < 0 || gx >= this.w || gz >= this.h) ? -1 : gz * this.w + gx; }
  get(x, z) { const i = this.idx(x, z); return i < 0 ? 1 : this.a[i]; }
  rect(cx, cz, ex, ez, hw, hd, v, margin = 0) {            // mark oriented rect (ex,ez unit vectors)
    const R = Math.hypot(hw, hd) + margin;
    for (let x = cx - R; x <= cx + R; x += this.c * .5) for (let z = cz - R; z <= cz + R; z += this.c * .5) {
      const dx = x - cx, dz = z - cz, a = dx * ex[0] + dz * ex[1], b = dx * ez[0] + dz * ez[1];
      if (Math.abs(a) <= hw + margin && Math.abs(b) <= hd + margin) { const i = this.idx(x, z); if (i >= 0) this.a[i] = v; }
    }
  }
}

function rectFree(ctx, occ, cx, cz, ex, ez, hw, hd, minD) {
  for (let a = -1; a <= 1; a += 0.5) for (let b = -1; b <= 1; b += 0.5) {
    const x = cx + ex[0] * hw * a + ez[0] * hd * b, z = cz + ex[1] * hw * a + ez[1] * hd * b;
    if (occ.get(x, z)) return false;
    if (x > CANAL.x0 - 5 && x < CANAL.x1 + 5) return false;
    if (Math.abs(z - DOCKS.zc) < DOCKS.half + 30 && x > CANAL.x0 - DOCKS.apron && x < CANAL.x1 + DOCKS.apron) return false;
    if (ctx.dist(x, z) < minD) return false;
  }
  return true;
}

export function buildCity(ctx) {
  const T = ctx.T, N = T.N, rnd = mulberry32(2080), Bd = T.layout.bounds;
  const occ = ctx.occ = new Occ(Bd, 2);
  ctx.buildings = [];
  // frontage generation per zone run along each side; rows stepped back from the road
  const order = [];
  for (let row = 0; row < 4; row++) for (const side of [1, -1]) order.push([row, side]);
  for (const [row, side] of order) {
    let fi = 0;
    while (fi < N) {
      const i = Math.min(N - 1, Math.floor(fi));
      const zname = T.zoneNames[T.zone[i]], Z = ZONES[zname] ?? ZONES.street;
      if (row >= Z.rows) { fi += 20; continue; }
      const kind = T.kind[i];
      const curv = Math.abs(T.curv[i]);
      let w = rr(rnd, Z.w[0], Z.w[1]);
      if (curv > 1 / 90) w = Math.min(w, Z.deep ? 6 : 11); else if (curv > 1 / 180) w = Math.min(w, 20);
      const ic = Math.min(N - 1, Math.floor(i + w / 2));
      const hh = Math.hypot(T.rx[ic], T.rz[ic]);
      const rx = T.rx[ic] / hh * side, rz = T.rz[ic] / hh * side;     // away from the road
      const th = Math.hypot(T.tx[ic], T.tz[ic]), ex = [T.tx[ic] / th, T.tz[ic] / th], ez = [rx, rz];
      const B = T.hw[ic] + WALL_OFFSET;
      const elev = T.kind[ic] === KIND.ELEVATED && T.py[ic] > 5;
      const tun = T.kind[ic] === KIND.TUNNEL;
      let front = elev ? B + 0.7 + rr(rnd, 9, 20) : tun ? B + rr(rnd, 16, 26) : B + BARRIER_T + (SIDEWALK[zname] ?? 5);
      if (kind === KIND.TRENCH) front = B + 1.7 + 4.6 + rr(rnd, 1, 4);
      if (kind === KIND.BRIDGE) { fi += w; continue; }
      // rows behind: step back by the depth of the previous row; we simply offset by a per-row base and let occupancy sort it out
      const dn = rr(rnd, Z.d[0], Z.d[1]);
      const off = row * (Z.d[1] + 6 + 3 * (row & 1));
      let ok = false, cx, cz, wUse = w;
      for (const k of [1, .75, .5]) {
        wUse = w * k;
        const uc = front + off + dn / 2;
        const ic2 = Math.min(N - 1, Math.floor(i + wUse / 2));
        cx = T.px[ic2] + rx * uc; cz = T.pz[ic2] + rz * uc;
        if (rectFree(ctx, occ, cx, cz, ex, ez, wUse / 2, dn / 2, row === 0 ? (front - B + WALL_OFFSET) * 0.55 : 3.5)) { ok = true; break; }
      }
      const gapR = rr(rnd, Z.gap[0], Z.gap[1]);
      if (!ok || rnd() < (row === 0 ? 0.04 : 0.1)) { fi += Math.max(4, wUse * (ok ? 1 : 0.5)) + (ok ? gapR : 0); continue; }
      const hSpan = row === 0 ? Z.h : Z.hBack;
      let h = rr(rnd, hSpan[0], hSpan[1]);
      if (elev && row === 0) h = Math.min(h, rr(rnd, 20, 70));
      const dist = ctx.dist(cx, cz) ;
      const b = { cx, cz, ex, ez, w: wUse, d: dn, h, zone: zname, row, side, dist, i, Z, elev };
      occ.rect(cx, cz, ex, ez, wUse / 2, dn / 2, 1, 1.0);
      ctx.buildings.push(b);
      fi += wUse + gapR;
    }
  }
  for (const b of ctx.buildings) placeBuilding(ctx, b, rnd);
  ctx.stats.buildings = ctx.buildings.length;
}

// ---------------------------------------------------------------------------------------------------------------------
const ROWS_NEAR = [0, 3.2, 6.5, 11, 17, 26, 40, 60, 90, 140, 260];
const ROWS_FAR = [0, 12, 40, 90, 260];

function wall(g, ax, az, bx, bz, y0, y1, u0, tintArr, aoBottom) {
  const dx = bx - ax, dz = bz - az, L = Math.hypot(dx, dz); if (L < 1e-4) return;
  const nx = -dz / L, nz = dx / L;
  g.color(tintArr[0], tintArr[1], tintArr[2], aoBottom);
  const i0 = g.vert(ax, y0, az, nx, 0, nz, u0, y0);
  g.vert(bx, y0, bz, nx, 0, nz, u0 + L, y0);
  g.color(tintArr[0], tintArr[1], tintArr[2], 1);
  g.vert(bx, y1, bz, nx, 0, nz, u0 + L, y1); g.vert(ax, y1, az, nx, 0, nz, u0, y1);
  g.quad(i0, i0 + 1, i0 + 2, i0 + 3);
}

function faceWalls(ctx, ch, matKey, corners, cxm, czm, y0, y1, fac, fac2, tint, near, u0s, podFace) {
  const g = ctx.geo(matKey, ch);
  const rows = near ? ROWS_NEAR : ROWS_FAR;
  for (let f = 0; f < 4; f++) {
    let a = corners[f], b = corners[(f + 1) % 4];
    const dx = b[0] - a[0], dz = b[1] - a[1], mx = (a[0] + b[0]) / 2 - cxm, mz = (a[1] + b[1]) / 2 - czm;
    if (-dz * mx + dx * mz < 0) { const t = a; a = b; b = t; }              // outward-facing winding
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const nseg = near ? Math.max(1, Math.ceil(L / 6)) : 1;
    // breakpoints in y
    const ys = [y0];
    for (const r of rows) if (r > y0 + .5 && r < y1 - .5) ys.push(r);
    ys.push(y1);
    for (let k = 0; k < nseg; k++) {
      const t0 = k / nseg, t1 = (k + 1) / nseg;
      const ax = lerp(a[0], b[0], t0), az = lerp(a[1], b[1], t0), bx = lerp(a[0], b[0], t1), bz = lerp(a[1], b[1], t1);
      for (let r = 0; r < ys.length - 1; r++) {
        const yy0 = ys[r], yy1 = ys[r + 1];
        const isPod = podFace && f === podFace.f && yy1 <= fac2.podH + 0.01;
        g.ex('aFac', isPod ? 6 : fac[0], fac[1], fac[2], isPod ? fac[3] * 1.6 : fac[3]);
        g.ex('aFac2', fac2.y0, fac2.lit, fac2.hue, fac2.podH);
        wall(g, ax, az, bx, bz, yy0, yy1, u0s[f] + L * t0, tint, yy0 <= 0.01 ? 0.55 : 1);
      }
    }
  }
}

function placeBuilding(ctx, b, rnd) {
  const { cx, cz, ex, ez, w, d, h, zone, row, Z } = b;
  const ch = ctx.chunkAt(cx, cz);
  const near = b.dist < 75;
  if (zone === 'docks' && row <= 1) { const r0 = rnd(); if (r0 < .5) return placeWarehouse(ctx, b, rnd); if (r0 < .8) return placeYard(ctx, b, rnd); }
  const seed = rnd();
  const style = pickW(rnd, Z.styles);
  const floorH = rr(rnd, Z.floor[0], Z.floor[1]), bayW = rr(rnd, Z.bay[0], Z.bay[1]);
  const lit = rr(rnd, Z.lit[0], Z.lit[1]);
  const hue = Z.hues[Math.floor(rnd() * Z.hues.length)];
  const tint = TINTS[Math.floor(rnd() * TINTS.length)];
  const podH = row === 0 && rnd() < Z.pod[0] ? rr(rnd, Z.pod[1], Z.pod[2]) : 0;
  let matKey = Z.mat;
  if (zone === 'market' && rnd() < .3) matKey = 'bldgA';
  if (zone === 'street' && rnd() < .15) matKey = 'bldgB';
  const lv = 0;
  const y0 = podH;
  // tiers
  const tiers = [];
  let tw = w, td = d, yb = 0, off = 0;
  const nT = h > 70 ? 3 : h > 38 ? 2 : 1;
  for (let k = 0; k < nT; k++) {
    const top = k === nT - 1 ? h : yb + (h - yb) * rr(rnd, .5, .72);
    tiers.push({ w: tw, d: td, off, yb, yt: top });
    yb = top; const inset = rr(rnd, 1.5, 4) * 2; tw = Math.max(8, tw - inset); td = Math.max(10, td - inset); off += rr(rnd, 0, (d - td) * .5);
  }
  b.tiers = tiers; b.podH = podH; b.style = style; b.hue = hue; b.seed = seed; b.floorH = floorH; b.bayW = bayW; b.lit = lit; b.matKey = matKey; b.ch = ch;
  let u0 = 0;
  for (let k = 0; k < tiers.length; k++) {
    const T_ = tiers[k];
    const tcx = cx + ez[0] * T_.off, tcz = cz + ez[1] * T_.off;
    const corners = [
      [tcx - ex[0] * T_.w / 2 - ez[0] * T_.d / 2, tcz - ex[1] * T_.w / 2 - ez[1] * T_.d / 2],
      [tcx + ex[0] * T_.w / 2 - ez[0] * T_.d / 2, tcz + ex[1] * T_.w / 2 - ez[1] * T_.d / 2],
      [tcx + ex[0] * T_.w / 2 + ez[0] * T_.d / 2, tcz + ex[1] * T_.w / 2 + ez[1] * T_.d / 2],
      [tcx - ex[0] * T_.w / 2 + ez[0] * T_.d / 2, tcz - ex[1] * T_.w / 2 + ez[1] * T_.d / 2],
    ];
    T_.corners = corners;
    const fac = [style, seed, floorH, bayW];
    const fac2 = { y0: k === 0 ? y0 : T_.yb, lit, hue, podH: k === 0 ? podH : 0 };
    // which face is the front? the one facing -ez (towards the road): corners 0→1
    const podFace = k === 0 && podH > 0 ? { f: 0 } : null;
    // face indices: wall() orientation is auto-fixed, so find front by position: the edge whose midpoint is nearest the road (−ez side)
    faceWalls(ctx, ch, matKey, corners, tcx, tcz, T_.yb, T_.yt, fac, fac2, tint, near, [0, T_.w, T_.w + T_.d, 2 * T_.w + T_.d], podFace);
    // roof
    const g = ctx.geo('conc', ch); g.lv(lv); g.color(.3, .31, .34, 1);
    {
      const c = corners, nY = (c[1][1] - c[0][1]) * (c[2][0] - c[1][0]) - (c[1][0] - c[0][0]) * (c[2][1] - c[1][1]);
      const ord = nY > 0 ? [0, 1, 2, 3] : [3, 2, 1, 0];
      g.poly(ord.map(q => [c[q][0], T_.yt, c[q][1]]), [0, 1, 0], [1, 0, 0], [0, 0, 1]);
    }
    // parapet
    parapet(g, corners, T_.yt, 0.9, 0.35);
    if (near && k === tiers.length - 1) roofProps(ctx, ch, T_, tcx, tcz, ex, ez, rnd, h);
    u0 += 2 * (T_.w + T_.d);
  }
  // red beacon on tall towers
  if (h > 80) {
    const T_ = tiers[tiers.length - 1];
    const tcx = cx + ez[0] * T_.off, tcz = cz + ez[1] * T_.off;
    const gs = ctx.geo('steel', ch); gs.color(.3, .3, .34, 1); gs.lv(lv);
    const mast = 6 + rnd() * 10;
    gs.cyl(tcx, T_.yt, tcz, 0.35, 0.12, mast, 6, true);
    const ge = ctx.geo('em16', ch); ge.lv(lv); ge.color(1, .08, .05, 1);
    ge.box(tcx, T_.yt + mast + 0.2, tcz, 0.5, 0.5, 0.5, 0);
  }
}

function parapet(g, c, y, hgt, th) {
  for (let k = 0; k < 4; k++) {
    const a = c[k], b = c[(k + 1) % 4];
    const mx = (a[0] + b[0]) / 2, mz = (a[1] + b[1]) / 2, L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const ang = Math.atan2(-(b[1] - a[1]), b[0] - a[0]);
    // centre of the four corners
    const ccx = (c[0][0] + c[1][0] + c[2][0] + c[3][0]) / 4, ccz = (c[0][1] + c[1][1] + c[2][1] + c[3][1]) / 4;
    const dx = ccx - mx, dz = ccz - mz, dl = Math.hypot(dx, dz) || 1;
    g.box(mx + dx / dl * th * 0.5, y + hgt / 2, mz + dz / dl * th * 0.5, L, hgt, th, ang, 'xXyYzZ');
  }
}

function roofProps(ctx, ch, T_, tcx, tcz, ex, ez, rnd, h) {
  const g = ctx.geo('steel', ch); g.color(.35, .37, .4, 1);
  const n = Math.floor(rr(rnd, 1, 4.5));
  for (let k = 0; k < n; k++) {
    const a = rr(rnd, -.35, .35) * T_.w, b = rr(rnd, -.35, .35) * T_.d;
    const x = tcx + ex[0] * a + ez[0] * b, z = tcz + ex[1] * a + ez[1] * b, ry = Math.atan2(-ex[1], ex[0]);
    const kind = rnd();
    if (kind < .5) g.box(x, T_.yt + 1.0, z, rr(rnd, 1.5, 4), 1.2, rr(rnd, 1.5, 3), ry);                // HVAC
    else if (kind < .8) { g.color(.3, .26, .22, 1); g.cyl(x, T_.yt, z, 1.5, 1.5, 2.6, 10, true); g.color(.35, .37, .4, 1); }   // water tank
    else g.box(x, T_.yt + 1.5, z, 0.2, 3.0, 0.2, ry);                                                       // antenna
  }
}
