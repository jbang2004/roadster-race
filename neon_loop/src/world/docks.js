// Docks district: corrugated warehouses, container yards, quay cranes, container fields, floodlight masts, moored boats, steam.
import { CANAL, DOCKS } from './params.js';
import { clamp, lerp, hash2, mulberry32 } from './util.js';
import { beam, container, BOX_COLS, addSteam, prism, capY, quadUp, triOut } from './prims.js';
import { addHalo } from './signs.js';

const rr = (rnd, a, b) => a + (b - a) * rnd();
const WALL_TINTS = [[.22, .3, .26], [.3, .22, .2], [.2, .26, .34], [.34, .34, .36], [.36, .3, .2], [.26, .3, .22], [.3, .2, .24]];
const SODIUM = [1.0, 0.56, 0.2];
const COLD = [0.7, 0.85, 1.0];

/** Wall segment helper with AO at the foot (uv in metres: along, up). */
function wallQ(g, ax, az, bx, bz, y0, y1, u0, tint, ao) {
  g.color(tint[0], tint[1], tint[2], ao);
  const dx = bx - ax, dz = bz - az, L = Math.hypot(dx, dz), nx = -dz / L, nz = dx / L;
  const i0 = g.vert(ax, y0, az, nx, 0, nz, u0, y0);
  g.vert(bx, y0, bz, nx, 0, nz, u0 + L, y0);
  g.color(tint[0], tint[1], tint[2], 1);
  g.vert(bx, y1, bz, nx, 0, nz, u0 + L, y1); g.vert(ax, y1, az, nx, 0, nz, u0, y1);
  g.quad(i0, i0 + 1, i0 + 2, i0 + 3);
}

/** A big corrugated warehouse in a frontage lot. Fills in the building record for the sign pass. */
export function placeWarehouse(ctx, b, rnd) {
  const { cx, cz, ex, ez, w, d } = b;
  const ch = ctx.chunkAt(cx, cz);
  const h = rr(rnd, 8, 12.5), ridge = rr(rnd, 1.4, 2.8);
  const tint = WALL_TINTS[Math.floor(rnd() * WALL_TINTS.length)];
  const nrm = [-ez[0], -ez[1]], right = [nrm[1], -nrm[0]];
  const P = (a, c, y) => [cx + ex[0] * a + ez[0] * c, y, cz + ex[1] * a + ez[1] * c];
  b.ch = ch; b.h = h + ridge; b.podH = 0; b.style = 3; b.warehouse = true; b.floorH = 6; b.bayW = 6; b.lit = .1; b.hue = .1; b.seed = rnd(); b.matKey = 'corr';
  const c4 = [P(-w / 2, -d / 2, 0), P(w / 2, -d / 2, 0), P(w / 2, d / 2, 0), P(-w / 2, d / 2, 0)];
  b.tiers = [{ w, d, off: 0, yb: 0, yt: h + ridge, corners: c4.map(p => [p[0], p[2]]) }];
  const g = ctx.geo('corr', ch); g.lv(0);
  // walls: 4 faces, subdivided horizontally (6 m) and vertically for the bake
  const ys = [0, 2.5, 5.5, h];
  let u0 = 0;
  for (let f = 0; f < 4; f++) {
    let a = c4[f], bb = c4[(f + 1) % 4];
    const mx = (a[0] + bb[0]) / 2 - cx, mz = (a[2] + bb[2]) / 2 - cz;
    if (-(bb[2] - a[2]) * mx + (bb[0] - a[0]) * mz < 0) { const t = a; a = bb; bb = t; }
    const L = Math.hypot(bb[0] - a[0], bb[2] - a[2]), ns = Math.max(1, Math.ceil(L / 6));
    for (let k = 0; k < ns; k++) {
      const t0 = k / ns, t1 = (k + 1) / ns;
      for (let r = 0; r < ys.length - 1; r++) wallQ(g, lerp(a[0], bb[0], t0), lerp(a[2], bb[2], t0), lerp(a[0], bb[0], t1), lerp(a[2], bb[2], t1), ys[r], ys[r + 1], u0 + L * t0, tint, r === 0 ? .55 : 1);
    }
    u0 += L;
    // gable triangles on the two short (±ex) faces: the faces whose outward normal is ±ex
    const nx = -(bb[2] - a[2]) / L, nz = (bb[0] - a[0]) / L;
    if (Math.abs(nx * ex[0] + nz * ex[1]) > .9) {
      g.color(tint[0] * .9, tint[1] * .9, tint[2] * .9, 1);
      triOut(g, [a[0], h, a[2]], [bb[0], h, bb[2]], [(a[0] + bb[0]) / 2, h + ridge, (a[2] + bb[2]) / 2], [nx, 0, nz]);
    }
  }
  // roof: two slopes with an overhang, ridge along ex; plus a ridge cap
  g.color(.2, .21, .24, 1);
  const ov = .5;
  quadUp(g, P(-w / 2 - ov, -d / 2 - ov, h - .2), P(w / 2 + ov, -d / 2 - ov, h - .2), P(w / 2 + ov, 0, h + ridge), P(-w / 2 - ov, 0, h + ridge), 1);
  quadUp(g, P(-w / 2 - ov, d / 2 + ov, h - .2), P(w / 2 + ov, d / 2 + ov, h - .2), P(w / 2 + ov, 0, h + ridge), P(-w / 2 - ov, 0, h + ridge), 1);
  const gp = ctx.geo('paint', ch); gp.lv(0); gp.color(.12, .13, .15, 1);
  { const rp = P(0, 0, h + ridge + .25); gp.box(rp[0], rp[1], rp[2], w * .7, .5, 1.1, Math.atan2(-ex[1], ex[0])); }
  // roller doors on the front (towards the road) + lintel + lamp. R(a, y, off): point on the front plane, `a` along the viewer's right.
  const R = (a, y, off = 0) => [cx + nrm[0] * (d / 2 + off) + right[0] * a, y, cz + nrm[1] * (d / 2 + off) + right[1] * a];
  const gs = ctx.geo('shut', ch); gs.lv(0);
  const ge = ctx.geo('em6', ch); ge.lv(0);
  const nd = Math.max(2, Math.floor(w / 10));
  const rotF = Math.atan2(-right[1], right[0]);
  for (let k = 0; k < nd; k++) {
    const a = (k + .5 - nd / 2) * (w / nd), dw = 4.4, dh = 4.8;
    const open = rnd() < .22;
    gs.color(open ? .08 : .34, open ? .08 : .36, open ? .09 : .4, 1);
    gs.quadUV(R(a - dw / 2, 0, .06), R(a + dw / 2, 0, .06), R(a + dw / 2, dh, .06), R(a - dw / 2, dh, .06), [[0, 0], [dw, 0], [dw, dh], [0, dh]]);
    if (open) {
      ge.color(1, .62, .3, 1);
      ge.quadP(R(a - dw / 2 + .3, .4, .08), R(a + dw / 2 - .3, .4, .08), R(a + dw / 2 - .3, dh * .75, .08), R(a - dw / 2 + .3, dh * .75, .08));
    }
    gp.color(.1, .11, .13, 1);
    { const lc = R(a, dh + .35, .2); gp.box(lc[0], lc[1], lc[2], dw + 1, .7, .3, rotF); }
    if (k % 2 === 0) {
      const lp = R(a, dh + .9, .5);
      ge.color(SODIUM[0], SODIUM[1], SODIUM[2], 1); ge.box(lp[0], lp[1], lp[2], .7, .14, .2, rotF);
      ctx.light({ pos: [lp[0] + nrm[0] * .6, lp[1] - .3, lp[2] + nrm[1] * .6], color: SODIUM, intensity: 150, range: 17, kind: 'street' }, 0);
      addHalo(ctx, ch, lp[0] + nrm[0] * .4, lp[1], lp[2] + nrm[1] * .4, 1.8, .5, .28, .1);
    }
  }
  // high strip windows on every face
  const gw = ctx.geo('em2', ch); gw.lv(0);
  for (let f = 0; f < 4; f++) {
    let a = c4[f], bb = c4[(f + 1) % 4];
    const mx = (a[0] + bb[0]) / 2 - cx, mz = (a[2] + bb[2]) / 2 - cz;
    if (-(bb[2] - a[2]) * mx + (bb[0] - a[0]) * mz < 0) { const t = a; a = bb; bb = t; }
    const L = Math.hypot(bb[0] - a[0], bb[2] - a[2]), dx = (bb[0] - a[0]) / L, dz = (bb[2] - a[2]) / L, nx = -dz, nz = dx;
    const nW = Math.floor(L / 4.4);
    for (let k = 0; k < nW; k++) {
      if (rnd() < .5) continue;
      const t0 = (k + .1) / nW * L, t1 = (k + .9) / nW * L;
      const col = rnd() < .6 ? [.09, .15, .14] : [.24, .15, .08];
      gw.color(col[0], col[1], col[2], 1);
      const p0 = [a[0] + dx * t0 + nx * .04, h - 2.6, a[2] + dz * t0 + nz * .04], p1 = [a[0] + dx * t1 + nx * .04, h - 2.6, a[2] + dz * t1 + nz * .04];
      gw.quadP(p0, p1, [p1[0], h - 1.5, p1[2]], [p0[0], h - 1.5, p0[2]]);
    }
  }
  // rooftop vents
  gp.color(.2, .21, .24, 1);
  for (let k = 0; k < 3; k++) { const c = P((k - 1) * w * .28 + rr(rnd, -2, 2), rr(rnd, -d * .2, d * .2), h + ridge * .5); if (rnd() < .7) gp.cyl(c[0], h + ridge * .35, c[2], .7, .7, 1.2, 8, true); }
}

/** Fenced container yard filling a frontage lot. */
export function placeYard(ctx, b, rnd) {
  const { cx, cz, ex, ez, w, d } = b;
  const ch = ctx.chunkAt(cx, cz);
  const nrm = [-ez[0], -ez[1]];
  const P = (a, c, y) => [cx + ex[0] * a + ez[0] * c, y, cz + ex[1] * a + ez[1] * c];
  const ry = Math.atan2(-ex[1], ex[0]);
  b.ch = ch; b.h = 3; b.podH = 0; b.yard = true; b.tiers = [{ w, d, off: 0, yb: 0, yt: 3, corners: [] }]; b.style = 3;
  const gv = ctx.geo('pave', ch); gv.lv(0); gv.color(.34, .35, .38, 1);
  const q = [P(-w / 2, -d / 2, .05), P(w / 2, -d / 2, .05), P(w / 2, d / 2, .05), P(-w / 2, d / 2, .05)];
  const nsx = Math.max(1, Math.ceil(w / 8)), nsz = Math.max(1, Math.ceil(d / 8));
  for (let i = 0; i < nsx; i++) for (let j = 0; j < nsz; j++) {
    const a0 = -w / 2 + w * i / nsx, a1 = -w / 2 + w * (i + 1) / nsx, c0 = -d / 2 + d * j / nsz, c1 = -d / 2 + d * (j + 1) / nsz;
    quadUp(gv, P(a0, c0, .05), P(a1, c0, .05), P(a1, c1, .05), P(a0, c1, .05), 1);
  }
  // low walls (sides + back; the front has a wide gate)
  const gc = ctx.geo('conc', ch); gc.lv(0); gc.color(.4, .42, .46, 1);
  const wallBox = (a, c, len, rot) => { const p = P(a, c, .55); gc.box(p[0], p[1], p[2], len, 1.1, .3, rot); };
  wallBox(0, d / 2 - .15, w, ry);
  const sideRot = Math.atan2(-ez[1], ez[0]);
  wallBox2(gc, P, -w / 2 + .15, 0, d, sideRot); wallBox2(gc, P, w / 2 - .15, 0, d, sideRot);
  const gate = Math.min(14, w * .4), ga = rr(rnd, -w * .15, w * .15);
  const lenL = (ga - gate / 2) - (-w / 2), lenR = (w / 2) - (ga + gate / 2);
  if (lenL > 1) wallBox(-w / 2 + lenL / 2, -d / 2 + .15, lenL, ry);
  if (lenR > 1) wallBox(w / 2 - lenR / 2, -d / 2 + .15, lenR, ry);
  // container blocks
  const gk = ctx.geo('corr', ch); gk.lv(0);
  const lenAlongX = rnd() < .5;
  const L = 12.19, Wd = 2.44, pitchW = Wd + .35, lane = 5.5;
  const inW = w - 4, inD = d - 8;
  const rowCol = BOX_COLS[Math.floor(rnd() * BOX_COLS.length)];
  if (lenAlongX) {
    const nCols = Math.max(0, Math.floor(inW / (L + 1)));
    for (let r = 0, c = -inD / 2 + 3; c < inD / 2 - 1; r++, c += pitchW) {
      if (r % 4 === 3) { c += lane - pitchW; continue; }
      for (let k = 0; k < nCols; k++) {
        if (rnd() < .2) continue;
        const a = (k - (nCols - 1) / 2) * (L + 1), nh = rnd() < .4 ? 1 : rnd() < .6 ? 2 : rnd() < .7 ? 3 : 4;
        const col = rnd() < .55 ? rowCol : BOX_COLS[Math.floor(rnd() * BOX_COLS.length)];
        for (let t = 0; t < nh; t++) { const p = P(a, c, 0); const v = .8 + rnd() * .35; container(gk, p[0], t * 2.59 + .05, p[2], L, ry, [col[0] * v, col[1] * v, col[2] * v], t === nh - 1 ? 'xXzZY' : 'xXzZ'); }
      }
    }
  } else {
    const nRows = Math.max(0, Math.floor(inD / (L + 1)));
    for (let r = 0, a = -inW / 2 + 2; a < inW / 2 - 1; r++, a += pitchW) {
      if (r % 4 === 3) { a += lane - pitchW; continue; }
      for (let k = 0; k < nRows; k++) {
        if (rnd() < .2) continue;
        const c = (k - (nRows - 1) / 2) * (L + 1) + 1.5, nh = rnd() < .4 ? 1 : rnd() < .6 ? 2 : rnd() < .7 ? 3 : 4;
        const col = rnd() < .55 ? rowCol : BOX_COLS[Math.floor(rnd() * BOX_COLS.length)];
        for (let t = 0; t < nh; t++) { const p = P(a, c, 0); const v = .8 + rnd() * .35; container(gk, p[0], t * 2.59 + .05, p[2], L, Math.atan2(-ez[1], ez[0]), [col[0] * v, col[1] * v, col[2] * v], t === nh - 1 ? 'xXzZY' : 'xXzZ'); }
      }
    }
  }
  // floodlight mast in the back corner
  const mp = P((rnd() < .5 ? -1 : 1) * (w / 2 - 2), d / 2 - 2, 0);
  floodMast(ctx, ch, mp[0], mp[2], nrm, 17, 700);
}
function wallBox2(gc, P, a, c, len, rot) { const p = P(a, c, .55); gc.box(p[0], p[1], p[2], len, 1.1, .3, rot); }

/** Pole with a lamp bar; registers two spot-ish lights angled down. */
export function floodMast(ctx, ch, x, z, toward, H = 24, cd = 900, range = 50) {
  const gs = ctx.geo('steel', ch); gs.lv(0); gs.color(.22, .24, .27, 1);
  gs.cyl(x, 0, z, .3, .16, H, 8, true);
  const perp = [-toward[1], toward[0]], ryP = Math.atan2(-perp[1], perp[0]);
  gs.box(x, H + .1, z, 3.2, .3, .5, ryP);
  const ge = ctx.geo('em40', ch); ge.lv(0); ge.color(1, .78, .5, 1);
  for (let k = -1; k <= 1; k += 2) ge.box(x + perp[0] * k * .95 + toward[0] * .35, H - .15, z + perp[1] * k * .95 + toward[1] * .35, .7, .12, .5, ryP);
  ctx.light({ pos: [x + toward[0] * 1.2, H - .4, z + toward[1] * 1.2], color: [1, .72, .42], intensity: cd, range, kind: 'street', dir: [0, -1, 0], angle: 1.2, penumbra: .7 }, 0);
  addHalo(ctx, ch, x + toward[0] * .6, H - .2, z + toward[1] * .6, 4.5, .5, .32, .16);
}

// ---------------------------------------------------------------------------------------------------------------------
/** Ship-to-shore quay crane. a = distance along the boom axis from the waterside legs (+ over the water). */
function crane(ctx, xw, zc, dirW, rnd, raised) {
  const ch = ctx.chunkAt(xw - dirW * 10, zc);
  const gp = ctx.geo('paint', ch); gp.lv(0);
  const ge = ctx.geo('em6', ch); ge.lv(0);
  const P = (a, y, zz) => [xw + dirW * a, y, zc + zz];
  const body = [[.5, .1, .06], [.1, .2, .42], [.52, .5, .46], [.55, .32, .06]][Math.floor(rnd() * 4)];
  const dark = [body[0] * .55, body[1] * .55, body[2] * .55];
  const GA = 18, GZ = 7.5, TOP = 27, BY = 29.5;
  gp.color(body[0], body[1], body[2], 1);
  for (const a of [0, -GA]) for (const zz of [-GZ, GZ]) beam(gp, P(a, 0, zz), P(a, TOP, zz), 1.15, 1.15);
  for (const zz of [-GZ, GZ]) {                               // side frames: sills, portal beams, X braces
    beam(gp, P(0, .6, zz), P(-GA, .6, zz), .8, .8);
    beam(gp, P(0, TOP, zz), P(-GA, TOP, zz), 1.2, 1.4);
    beam(gp, P(0, .6, zz), P(-GA, TOP, zz), .45, .45); beam(gp, P(-GA, .6, zz), P(0, TOP, zz), .45, .45);
  }
  for (const a of [0, -GA]) { beam(gp, P(a, .6, -GZ), P(a, .6, GZ), .8, .8); beam(gp, P(a, TOP, -GZ), P(a, TOP, GZ), 1.2, 1.4); }
  // boom girders (+ back reach)
  const tipA = 38, backA = -15, hingeA = 9;
  gp.color(dark[0] * 1.5, dark[1] * 1.5, dark[2] * 1.5, 1);
  for (const zz of [-3.2, 3.2]) {
    beam(gp, P(backA, BY, zz), P(hingeA, BY, zz), 1.3, 2.2);
    if (raised) beam(gp, P(hingeA, BY, zz), P(hingeA + 33 * Math.cos(1.0), BY + 33 * Math.sin(1.0), zz), 1.1, 1.8);
    else beam(gp, P(hingeA, BY, zz), P(tipA, BY, zz), 1.3, 2.2);
  }
  for (let a = backA + 2; a < hingeA; a += 6) beam(gp, P(a, BY, -3.2), P(a, BY, 3.2), .6, .8);
  if (!raised) for (let a = hingeA + 3; a < tipA; a += 6) beam(gp, P(a, BY, -3.2), P(a, BY, 3.2), .6, .8);
  // machinery house + A-frame + stays
  gp.color(body[0] * .8, body[1] * .8, body[2] * .8, 1);
  { const c = P(-5, BY + 3.1, 0); gp.box(c[0], c[1], c[2], 12, 3.6, 8.4, dirW > 0 ? 0 : 0); }
  gp.color(dark[0] * 1.4, dark[1] * 1.4, dark[2] * 1.4, 1);
  const apex = P(1, 47, 0);
  for (const zz of [-3.2, 3.2]) { beam(gp, P(-6, BY, zz), apex, .7, .7); beam(gp, P(9, BY, zz), apex, .7, .7); }
  gp.color(.1, .11, .13, 1);
  const tip = raised ? P(hingeA + 33 * Math.cos(1.0), BY + 33 * Math.sin(1.0), 0) : P(tipA, BY, 0);
  beam(gp, apex, tip, .22, .22); beam(gp, apex, P(backA, BY, 0), .22, .22);
  // trolley + spreader (+ a container on some)
  if (!raised) {
    const ta = rr(rnd, 14, 32), c = P(ta, BY - 1.8, 0);
    gp.color(.3, .3, .34, 1); gp.box(c[0], c[1], c[2], 3.4, 1.4, 7.4, 0);
    const sy = rr(rnd, 9, 24);
    gp.color(.1, .11, .13, 1);
    for (const zz of [-2.6, 2.6]) for (const dx of [-1.1, 1.1]) beam(gp, [c[0] + dx, BY - 2.4, c[2] + zz], [c[0] + dx, sy + 1.2, c[2] + zz], .08, .08);
    gp.color(.25, .26, .3, 1); gp.box(c[0], sy + .9, c[2], 2.6, .45, 12.3, 0);
    if (rnd() < .6) { const gk = ctx.geo('corr', ch); gk.lv(0); const col = BOX_COLS[Math.floor(rnd() * BOX_COLS.length)]; container(gk, c[0], sy - 1.95, c[2], 12.19, -Math.PI / 2, col); }
    const cab = P(ta + 2.4, BY - 3.4, 3.6);
    gp.color(.2, .22, .26, 1); gp.box(cab[0], cab[1], cab[2], 2.6, 2.2, 3, 0);
    ge.color(.9, .9, 1, 1); const cw = P(ta + 2.4, BY - 3.4, 3.6); ge.box(cw[0] - dirW * 1.32, cw[1] + .1, cw[2], .06, 1.2, 2.4, 0);
  }
  // lights: structure outline strips, red beacons, working lights
  ge.color(.55, .75, 1, 1);
  for (const a of [0, -GA]) for (const zz of [-GZ, GZ]) { const c = P(a, TOP / 2, zz); ge.box(c[0] + dirW * .6, c[1], c[2], .05, TOP * .9, .1, 0); }
  for (const zz of [-3.2, 3.2]) { const mid = raised ? (backA + hingeA) / 2 : (backA + tipA) / 2, len = raised ? hingeA - backA : tipA - backA; const c = P(mid, BY - 1.15, zz); ge.box(c[0], c[1], c[2], len, .08, .12, 0); }
  ge.color(1, .08, .04, 1);
  for (const p of [apex, tip]) ge.box(p[0], p[1] + .5, p[2], .45, .45, .45, 0);
  ctx.light({ pos: [apex[0], apex[1], apex[2]], color: [1, .1, .05], intensity: 80, range: 30, kind: 'sign' }, 0);
  addHalo(ctx, ch, apex[0], apex[1] + .5, apex[2], 4, .8, .06, .03); addHalo(ctx, ch, tip[0], tip[1] + .5, tip[2], 3, .8, .06, .03);
  const wl = P(2, BY - 2, 0);
  ctx.light({ pos: wl, color: [.85, .92, 1], intensity: 520, range: 46, kind: 'street', dir: [0, -1, 0], angle: 1.3, penumbra: .8 }, 0);
  ctx.light({ pos: P(22, BY - 2, 0), color: [.85, .92, 1], intensity: 380, range: 40, kind: 'street', dir: [0, -1, 0], angle: 1.3, penumbra: .8 }, 0);
}

// ---------------------------------------------------------------------------------------------------------------------
function boatBarge(ctx, cx, cz, sgn, rnd) {
  const ch = ctx.chunkAt(cx, cz), W = 7.4, L = 34, FB = 1.7, wl = CANAL.water, deck = wl + FB;
  const gp = ctx.geo('paint', ch); gp.lv(0);
  const hullC = [[.12, .12, .15], [.35, .08, .06], [.07, .16, .28], [.18, .2, .16]][Math.floor(rnd() * 4)];
  gp.color(hullC[0], hullC[1], hullC[2], 1);
  const pts = [[cx - W / 2, cz - sgn * L / 2], [cx - W / 2, cz + sgn * (L / 2 - W * .9)], [cx, cz + sgn * L / 2], [cx + W / 2, cz + sgn * (L / 2 - W * .9)], [cx + W / 2, cz - sgn * L / 2]];
  prism(gp, pts, wl - .4, deck, { top: false });
  gp.color(.16, .17, .2, 1); capY(gp, pts.map(p => [p[0], deck, p[1]]));
  // wheelhouse at the stern
  const hz = cz - sgn * (L / 2 - 4.2);
  gp.color(.55, .55, .58, 1); gp.box(cx, deck + 2.2, hz, 5.2, 4.2, 6.0, 0);
  gp.color(.3, .3, .34, 1); gp.box(cx, deck + 4.4, hz, 5.6, .3, 6.4, 0);
  gp.box(cx + 1, deck + 6.0, hz, .2, 3, .2, 0);
  const ge = ctx.geo('em2', ch); ge.lv(0); ge.color(.5, .35, .2, 1);
  ge.box(cx, deck + 3.3, hz + sgn * 3.02, 4.4, 1.0, .06, 0);
  ge.box(cx - 2.62, deck + 3.3, hz, .06, 1.0, 4.6, 0); ge.box(cx + 2.62, deck + 3.3, hz, .06, 1.0, 4.6, 0);
  const gr = ctx.geo('em6', ch); gr.lv(0);
  gr.color(1, .1, .05, 1); gr.box(cx - 2.8, deck + 4.2, hz + sgn * 2.8, .25, .25, .25, 0);
  gr.color(.1, 1, .3, 1); gr.box(cx + 2.8, deck + 4.2, hz + sgn * 2.8, .25, .25, .25, 0);
  gr.color(1, .95, .8, 1); gr.box(cx + 1, deck + 7.6, hz, .3, .3, .3, 0);
  ctx.light({ pos: [cx, deck + 3, hz + sgn * 3.8], color: [1, .72, .45], intensity: 90, range: 20, kind: 'street' }, 0);
  ctx.light({ pos: [cx + 1, deck + 7.6, hz], color: [.9, .95, 1], intensity: 60, range: 16, kind: 'street' }, 0);
  addHalo(ctx, ch, cx + 1, deck + 7.6, hz, 2.0, .45, .45, .4);
  addHalo(ctx, ch, cx - 2.8, deck + 4.2, hz + sgn * 2.8, 1.2, .5, .04, .02); addHalo(ctx, ch, cx + 2.8, deck + 4.2, hz + sgn * 2.8, 1.2, .03, .5, .12);
  // deck cargo
  const gk = ctx.geo('corr', ch); gk.lv(0);
  const rows = 5, ry = -Math.PI / 2;
  for (let k = 0; k < rows; k++) {
    const zz = cz + sgn * (L / 2 - 6.5 - k * 6.3);
    for (const xx of [-1.35, 1.35]) {
      const nh = rnd() < .2 ? 1 : rnd() < .5 ? 2 : 3;
      for (let t = 0; t < nh; t++) { const col = BOX_COLS[Math.floor(rnd() * BOX_COLS.length)]; container(gk, cx + xx, deck + t * 2.59, zz, 6.06, Math.PI / 2, col, t === nh - 1 ? 'xXzZY' : 'xXzZ'); }
    }
  }
}

function boatTug(ctx, cx, cz, sgn, rnd) {
  const ch = ctx.chunkAt(cx, cz), W = 5.2, L = 15, FB = 1.2, wl = CANAL.water, deck = wl + FB;
  const gp = ctx.geo('paint', ch); gp.lv(0);
  const hc = [[.5, .12, .06], [.08, .14, .3], [.08, .3, .22]][Math.floor(rnd() * 3)];
  gp.color(hc[0], hc[1], hc[2], 1);
  const pts = [[cx - W / 2, cz - sgn * L / 2], [cx - W / 2, cz + sgn * (L / 2 - W * .8)], [cx, cz + sgn * L / 2], [cx + W / 2, cz + sgn * (L / 2 - W * .8)], [cx + W / 2, cz - sgn * L / 2]];
  prism(gp, pts, wl - .4, deck, { top: false });
  gp.color(.14, .15, .17, 1); capY(gp, pts.map(p => [p[0], deck, p[1]]));
  gp.color(.6, .6, .62, 1); gp.box(cx, deck + 1.5, cz - sgn * 1.5, 3.8, 3, 5.2, 0);
  gp.color(.3, .3, .34, 1); gp.box(cx, deck + 3.1, cz - sgn * 1.5, 4.1, .25, 5.5, 0);
  gp.color(.7, .15, .08, 1); gp.cyl(cx, deck + 3.2, cz - sgn * 3.2, .65, .5, 2.6, 10, true);
  gp.color(.05, .05, .06, 1); gp.cyl(cx, deck + 5.5, cz - sgn * 3.2, .52, .52, .35, 10, true);
  const ge = ctx.geo('em2', ch); ge.lv(0); ge.color(.5, .38, .22, 1);
  ge.box(cx, deck + 2.0, cz - sgn * 1.5 + sgn * 2.62, 3.2, .9, .06, 0);
  const gr = ctx.geo('em6', ch); gr.lv(0); gr.color(1, .95, .85, 1);
  gr.box(cx, deck + 3.5, cz + sgn * 1.2, .4, .3, .4, 0);
  ctx.light({ pos: [cx, deck + 3.2, cz + sgn * 2.0], color: [1, .85, .6], intensity: 110, range: 22, kind: 'street', dir: [0, -0.3, sgn], angle: 1.2, penumbra: .7 }, 0);
  addHalo(ctx, ch, cx, deck + 3.5, cz + sgn * 1.2, 1.8, .5, .45, .35);
}

function boatSampan(ctx, cx, cz, sgn, rnd) {
  const ch = ctx.chunkAt(cx, cz), W = 2.7, L = 9.5, wl = CANAL.water, deck = wl + .75;
  const gp = ctx.geo('paint', ch); gp.lv(0);
  gp.color(.18, .12, .08, 1);
  const pts = [[cx - W / 2, cz - sgn * L / 2], [cx - W / 2 * .8, cz + sgn * (L / 2 - 2)], [cx, cz + sgn * L / 2], [cx + W / 2 * .8, cz + sgn * (L / 2 - 2)], [cx + W / 2, cz - sgn * L / 2]];
  prism(gp, pts, wl - .3, deck, { top: false });
  gp.color(.3, .22, .14, 1); capY(gp, pts.map(p => [p[0], deck, p[1]]));
  // canopy tent
  const tcol = [[.4, .08, .06], [.08, .2, .3], [.3, .3, .32]][Math.floor(rnd() * 3)];
  gp.color(tcol[0], tcol[1], tcol[2], 1);
  const tz = cz - sgn * 1.3;
  quadUp(gp, [cx - W / 2 + .1, deck + .1, tz - 2.2], [cx - W / 2 + .1, deck + .1, tz + 2.2], [cx, deck + 1.55, tz + 2.2], [cx, deck + 1.55, tz - 2.2], 1);
  quadUp(gp, [cx + W / 2 - .1, deck + .1, tz - 2.2], [cx + W / 2 - .1, deck + .1, tz + 2.2], [cx, deck + 1.55, tz + 2.2], [cx, deck + 1.55, tz - 2.2], 1);
  const ge = ctx.geo('em6', ch); ge.lv(0);
  const lc = [[1, .25, .1], [1, .6, .2], [.3, .9, 1], [1, .3, .7]][Math.floor(rnd() * 4)];
  ge.color(lc[0], lc[1], lc[2], 1);
  gp.color(.1, .08, .06, 1); gp.cyl(cx, deck, cz + sgn * (L / 2 - 1.3), .05, .05, 2.2, 5, true);
  ge.box(cx, deck + 2.1, cz + sgn * (L / 2 - 1.3), .35, .5, .35, 0);
  addHalo(ctx, ch, cx, deck + 2.1, cz + sgn * (L / 2 - 1.3), 2.6, lc[0] * .45, lc[1] * .45, lc[2] * .45);
  ctx.light({ pos: [cx, deck + 2.0, cz + sgn * (L / 2 - 1.3)], color: lc, intensity: 45, range: 10, kind: 'neon' }, 0);
}

// ---------------------------------------------------------------------------------------------------------------------
/** Quay furniture, cranes, container fields, masts, boats, steam. */
export function buildQuays(ctx) {
  const rnd = mulberry32(4711);
  const { zc, half } = DOCKS;
  const sides = [{ dirIn: -1, xq: CANAL.x0 - 1.35 }, { dirIn: 1, xq: CANAL.x1 + 1.35 }];
  const gk = (x, z) => ctx.geo('corr', ctx.chunkAt(x, z));
  for (const S of sides) {
    const X = (d) => S.xq + S.dirIn * d;
    const toward = [-S.dirIn, 0];                       // towards the water
    // rails + quay-edge bollards
    for (const sgn of [-1, 1]) {
      const z0 = zc + sgn * 24, z1 = zc + sgn * (half - 10);
      for (const d of [2.5, 20.5]) {
        const ch = ctx.chunkAt(X(d), (z0 + z1) / 2), g = ctx.geo('steel', ch); g.lv(0); g.color(.3, .3, .33, 1);
        g.box(X(d), .06, (z0 + z1) / 2, .25, .1, Math.abs(z1 - z0), 0);
      }
      for (let z = z0; Math.abs(z - zc) < half - 10; z += sgn * 11) {
        const ch = ctx.chunkAt(X(1.0), z), g = ctx.geo('paint', ch); g.lv(0); g.color(.5, .38, .08, 1);
        g.cyl(X(1.0), 0.1, z, .22, .2, .55, 8, true);
      }
    }
    const zsC = (S.dirIn < 0 ? [62, 116, 170] : [88, 142, 196]).flatMap(o => [zc - o, zc + o]), zsM = (S.dirIn < 0 ? [38, 90, 143, 196] : [40, 115, 169]).flatMap(o => [zc - o, zc + o]);
    // container fields (landside), rows along z
    const fieldCols = [27.3, 30.1, 32.9, 39.1, 41.9];
    for (const sgn of [-1, 1]) {
      let rowN = 0;
      for (let z = zc + sgn * 30; Math.abs(z - zc) < half - 12; z += sgn * 12.9, rowN++) {
        const blockSeed = hash2(Math.floor(z / 40), S.dirIn, 5);
        for (const d of fieldCols) {
          if (rnd() < .24) continue;
          const nh = Math.min(5, 1 + Math.floor((blockSeed * 2 + rnd() * 3) * (hash2(Math.floor(d), Math.floor(z / 13), 9) * 1.2 + .3)));
          const col = rnd() < .6 ? BOX_COLS[Math.floor(blockSeed * BOX_COLS.length)] : BOX_COLS[Math.floor(rnd() * BOX_COLS.length)];
          const g = gk(X(d), z);
          for (let t = 0; t < nh; t++) { const v = .78 + rnd() * .4; container(g, X(d), t * 2.59 - .04, z, 12.19, -Math.PI / 2, [col[0] * v, col[1] * v, col[2] * v], t === nh - 1 ? 'xXzZY' : 'xXzZ'); }
        }
        // quay row under the cranes: a few low stacks
        if (rnd() < .32 && !zsC.some(c => Math.abs(c - z) < 11) && !zsM.some(c => Math.abs(c - z) < 5)) {
          const d = 11 + rnd() * 2, nh = rnd() < .6 ? 1 : 2, g = gk(X(d), z), col = BOX_COLS[Math.floor(rnd() * BOX_COLS.length)];
          for (let t = 0; t < nh; t++) container(g, X(d), t * 2.59 - .04, z, 12.19, -Math.PI / 2, col, t === nh - 1 ? 'xXzZY' : 'xXzZ');
        }
      }
    }
    // cranes
    const zs = S.dirIn < 0 ? [62, 116, 170] : [88, 142, 196];
    for (const off of zs) for (const sgn of [-1, 1]) {
      const z = zc + sgn * off;
      if (Math.abs(z - zc) > half - 14) continue;
      crane(ctx, X(2.5), z, -S.dirIn, rnd, rnd() < .35);
    }
    // floodlight masts between the cranes + steam vents on the quay
    const mz = S.dirIn < 0 ? [38, 90, 143, 196] : [40, 115, 169];
    for (const off of mz) for (const sgn of [-1, 1]) {
      const z = zc + sgn * off; if (Math.abs(z - zc) > half - 8) continue;
      floodMast(ctx, ctx.chunkAt(X(14), z), X(14), z, toward, 26, 900, 55);
    }
    for (let k = 0; k < 6; k++) {
      const z = zc + (rnd() < .5 ? -1 : 1) * rr(rnd, 34, half - 30), d = rr(rnd, 5, 8);
      addSteam(ctx, ctx.chunkAt(X(d), z), X(d), .05, z, { n: 6, h: 6, size: 1.4, speed: .1, seed: k });
    }
  }
  // boats along both quays (clear of the bridge)
  const berths = [];
  for (let off = 52; off < half - 20; off += 40 + Math.floor(rnd() * 26)) for (const sgn of [-1, 1]) berths.push([zc + sgn * off, sgn]);
  for (const [z, sgn] of berths) {
    for (const side of [-1, 1]) {
      if (rnd() < .3) continue;
      const kind = rnd(), cxs = side < 0 ? CANAL.x0 + 4.6 + rnd() * .8 : CANAL.x1 - 4.6 - rnd() * .8, dir = rnd() < .5 ? 1 : -1;
      if (kind < .38) boatBarge(ctx, cxs, z + rr(rnd, -6, 6), dir, rnd);
      else if (kind < .62) boatTug(ctx, side < 0 ? CANAL.x0 + 3.6 : CANAL.x1 - 3.6, z + rr(rnd, -8, 8), dir, rnd);
      else { boatSampan(ctx, side < 0 ? CANAL.x0 + 2.4 : CANAL.x1 - 2.4, z, dir, rnd); if (rnd() < .6) boatSampan(ctx, side < 0 ? CANAL.x0 + 2.4 : CANAL.x1 - 2.4, z + 11, dir, rnd); }
    }
  }
}

/** Neon company boards above the warehouse doors. */
export function buildDockSigns(ctx, atlas, signQuad) {
  const rnd = mulberry32(777);
  const Hs = atlas.signs.filter(s => s.kind === 'h' && ['amber', 'green', 'cyan', 'red', 'white'].includes(s.pal));
  const COL = { cyan: [.3, .9, 1], magenta: [1, .25, .8], violet: [.6, .35, 1], amber: [1, .6, .2], green: [.3, 1, .5], red: [1, .25, .15], white: [.8, .9, 1] };
  for (const b of ctx.buildings) {
    if (!b.warehouse || b.dist > 90) continue;
    const ch = b.ch, nrm = [-b.ez[0], -b.ez[1]], right = [nrm[1], -nrm[0]];
    const d = Hs[Math.floor(rnd() * Hs.length)];
    const sw = clamp(b.w * .32, 6, 10), sh = sw / 4, yc = b.h - 1.6 - sh / 2 - 1.2;
    const c = [b.cx + nrm[0] * (b.d / 2 + .25), yc, b.cz + nrm[1] * (b.d / 2 + .25)];
    const g = ctx.geo('sign', ch); g.lv(0); g.color(.9, .9, .9, 1); g.ex('aFl', rnd() * 6, rnd() < .3 ? 1 : 0);
    signQuad(g, c, right, 0, sw, sh, d, nrm);
    const gh = ctx.geo('steel', ch); gh.lv(0); gh.color(.1, .11, .13, 1);
    gh.box(c[0] - nrm[0] * .12, c[1], c[2] - nrm[1] * .12, sw + .2, sh + .2, .24, Math.atan2(-right[1], right[0]));
    const col = COL[d.pal];
    ctx.light({ pos: [c[0] + nrm[0] * 1.5, c[1] - .5, c[2] + nrm[1] * 1.5], color: col, intensity: 80, range: 13, kind: 'neon' }, 0);
    addHalo(ctx, ch, c[0] + nrm[0] * .4, c[1], c[2] + nrm[1] * .4, sw * .8, col[0] * .2, col[1] * .2, col[2] * .2);
  }
}
