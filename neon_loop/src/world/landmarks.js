// Landmarks: start/finish gantry (+ five start lamps), grandstands, trackside advertising, skybridge, expressway sign gantries, tunnel signs.
import * as THREE from 'three';
import { KIND, WALL_OFFSET } from '../track/track.js';
import { extrudeRun } from './extrude.js';
import { levelOfSample } from './ctx.js';
import { SIDEWALK, BARRIER_T } from './params.js';
import { mulberry32, hash2 } from './util.js';
import { CEIL_H } from './barriers.js';
import { addHalo } from './signs.js';

const roty = (ex, ez) => Math.atan2(-ez, ex);

function tbasis(T, i) {
  const th = Math.hypot(T.tx[i], T.tz[i]), rh = Math.hypot(T.rx[i], T.rz[i]);
  return { t: [T.tx[i] / th, T.tz[i] / th], r: [T.rx[i] / rh, T.rz[i] / rh], p: [T.px[i], T.py[i], T.pz[i]] };
}

/** Start/finish gantry. Returns { lamps: [{disc, halo}], go } meshes to be added to the world root (so they can be toggled). */
export function buildStartGantry(ctx, atlasBoard, root, defs) {
  const T = ctx.T, i = Math.round(T.startS), { t, r, p } = tbasis(T, i);
  const B = T.hw[i] + WALL_OFFSET, ch = ctx.chunkOfI(i);
  const gs = ctx.geo('steel', ch), ge = ctx.geo('em2', ch), gb = ctx.geo('board', ch);
  gs.lv(0); ge.lv(0);
  const ry = roty(r[0], r[1]);                      // box local x along r
  const ry2 = roty(t[0], t[1]);
  const P = (u, y, s = 0) => [p[0] + r[0] * u + t[0] * s, y, p[2] + r[1] * u + t[1] * s];
  const U0 = B + 1.9;
  gs.color(.16, .17, .2, 1);
  for (const sd of [1, -1]) {
    const c = P(sd * U0, 4.3);
    gs.box(c[0], c[1], c[2], 1.5, 8.2, 1.9, ry2);
    ge.color(.2, .9, 1, 1);
    const c2 = P(sd * (U0 - 0.97), 4.3, 0); ge.box(c2[0], c2[1], c2[2], 0.08, 7.6, 0.12, ry2);
  }
  const beamY = 8.35, beamL = 2 * U0 + 1.5;
  const bc = P(0, beamY);
  gs.color(.2, .21, .25, 1);
  gs.box(bc[0], bc[1], bc[2], beamL, 1.7, 1.5, ry);
  // underside light bars + side LED strips
  ge.color(.8, .9, 1, 1);
  const b2 = P(0, beamY - 0.88); ge.box(b2[0], b2[1], b2[2], beamL - 2, 0.06, 0.8, ry);
  ge.color(.2, .9, 1, 1);
  for (const s of [-0.78, 0.78]) { const b3 = P(0, beamY + 0.7, s); ge.box(b3[0], b3[1], b3[2], beamL - 0.4, 0.07, 0.06, ry); }
  // timing board above the beam, both sides
  const bw = 15, bh = bw * 0.25;
  const byc = beamY + 0.85 + 0.6 + bh / 2;
  for (const dir of [-1, 1]) {
    const s = dir * 0.78;
    const c = P(0, byc, s);
    const n = [t[0] * dir, t[1] * dir], right = [n[1], -n[0]];
    const hx = right[0] * bw / 2, hz = right[1] * bw / 2;
    gb.color(1, 1, 1, 1);
    gb.quadUV([c[0] - hx, c[1] - bh / 2, c[2] - hz], [c[0] + hx, c[1] - bh / 2, c[2] + hz], [c[0] + hx, c[1] + bh / 2, c[2] + hz], [c[0] - hx, c[1] + bh / 2, c[2] - hz], [[0, 0], [1, 0], [1, 1], [0, 1]]);
  }
  gs.color(.14, .15, .18, 1);
  const bb = P(0, byc, 0); gs.box(bb[0], bb[1], bb[2], bw + 0.4, bh + 0.4, 1.4, ry);
  for (const u of [-5.5, 5.5]) { const c = P(u, beamY + 1.2 + 0.5, 0); gs.box(c[0], c[1], c[2], 0.3, 1.2, 0.3, 0); }
  // lights
  for (const u of [-6, 0, 6]) ctx.light({ pos: P(u, beamY - 1.4), color: [.85, .92, 1], intensity: 320, range: 24, kind: 'sign', dir: [0, -1, 0], angle: 1.3, penumbra: .8 }, 0);
  ctx.light({ pos: P(0, byc, -6), color: [.5, .9, 1], intensity: 180, range: 22, kind: 'sign' }, 0);
  ctx.light({ pos: P(0, byc, 6), color: [.5, .9, 1], intensity: 180, range: 22, kind: 'sign' }, 0);
  // start lamps (separate meshes, toggled by world.setStartLights)
  const lamps = [];
  const discGeo = new THREE.CircleGeometry(0.46, 24);
  const matOn = new THREE.MeshBasicMaterial({ color: new THREE.Color(5, 0.1, 0.08) });
  const matOff = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.16, 0.012, 0.012) });
  const matGo = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.2, 9, 1.4) });
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(-t[0], 0, -t[1]));
  const haloGeoBase = [];
  for (let k = 0; k < 5; k++) {
    const u = -4 + k * 2, c = P(u, beamY - 0.1, -0.78 - 0.02);
    const housing = ctx.geo('steel', ch); housing.color(.05, .05, .06, 1);
    housing.box(c[0] + t[0] * 0.16, c[1], c[2] + t[1] * 0.16, 0.28, 1.15, 1.15, ry2);
    const disc = new THREE.Mesh(discGeo, matOff); disc.position.set(c[0], c[1], c[2]); disc.quaternion.copy(q); disc.layers.set(0); disc.name = 'startLamp' + k;
    root.add(disc);
    // halo sprite
    const hg = new THREE.BufferGeometry();
    const hp = [], hc = [], hu = [], hi = [];
    for (const [ox, oy, uu, vv] of [[-1, -1, 0, 0], [1, -1, 1, 0], [1, 1, 1, 1], [-1, 1, 0, 1]]) { hp.push(c[0], c[1], c[2]); hc.push(ox * 1, oy * 1, 0); hu.push(uu, vv); }
    hg.setAttribute('position', new THREE.Float32BufferAttribute(hp, 3)); hg.setAttribute('aCorner', new THREE.Float32BufferAttribute([3.2, -1, -1, 3.2, 1, -1, 3.2, 1, 1, 3.2, -1, 1], 3));
    hg.setAttribute('uv', new THREE.Float32BufferAttribute(hu, 2)); hg.setAttribute('color', new THREE.Float32BufferAttribute(new Array(16).fill(0).map((_, j) => j % 4 === 3 ? 1 : [1.0, .12, .08][j % 4] * 0.9), 4));
    hg.setIndex([0, 1, 2, 0, 2, 3]); hg.boundingSphere = new THREE.Sphere(new THREE.Vector3(c[0], c[1], c[2]), 6);
    const halo = new THREE.Mesh(hg, defs.halo.mat); halo.visible = false; halo.frustumCulled = true;
    root.add(halo);
    lamps.push({ disc, halo });
  }
  // red light spill from the lamps (registered once; only visible when R's pool turns them on)
  ctx.light({ pos: P(0, beamY - 1.5, -4), color: [1, .1, .05], intensity: 120, range: 22, kind: 'sign', flicker: 0 }, 0);
  return { lamps, matOn, matOff, matGo };
}

export function buildGrandstands(ctx) {
  const T = ctx.T, N = T.N, s0 = Math.round(T.startS) - 60, s1 = Math.round(T.startS) + 90;
  const poly = (i) => {
    const B = T.hw[i] + WALL_OFFSET, u0 = B + BARRIER_T + 0.2;
    const H = [.45, .9, 1.35, 1.8, 2.25], w = 1.1;
    const pts = [[u0, -0.1], [u0 + 5.5, -0.1], [u0 + 5.5, 2.25]];
    for (let k = 4; k >= 0; k--) { pts.push([u0 + k * w + w, H[k]]); pts.push([u0 + k * w, H[k]]); }
    // remove duplicate collinear: (u0+5.5,2.25) then (u0+5.5,2.25)
    const out = [pts[0], pts[1], pts[2]];
    for (let k = 3; k < pts.length; k++) { const a = out[out.length - 1]; if (Math.hypot(a[0] - pts[k][0], a[1] - pts[k][1]) > 1e-4) out.push(pts[k]); }
    return [{ key: 'crowd', pts: out, col: [1, 1, 1, 1] }];
  };
  extrudeRun(ctx, poly, s0, s1, { lvl: 0 });
  // railing along the top of the first row and the back
  extrudeRun(ctx, (i) => {
    const B = T.hw[i] + WALL_OFFSET, u0 = B + BARRIER_T + 0.2 + 5.5;
    return [{ key: 'steel', pts: [[u0 - .05, 2.25], [u0 + .05, 2.25], [u0 + .05, 3.3], [u0 - .05, 3.3]], col: [.3, .32, .36, 1] }];
  }, s0, s1, { lvl: 0 });
  // floodlight towers on the stands: lights
  for (let i = s0 + 10; i < s1; i += 40) for (const sd of [1, -1]) {
    const { r, p } = tbasis(T, i), B = T.hw[i] + WALL_OFFSET, u = sd * (B + BARRIER_T + 5.8);
    ctx.light({ pos: [p[0] + r[0] * u, 11, p[2] + r[1] * u], color: [.9, .95, 1], intensity: 520, range: 34, kind: 'street', dir: [-r[0] * sd * .6, -1, -r[1] * sd * .6], angle: 1.1, penumbra: .8 }, 0);
  }
}

/** Trackside advertising boards (sign atlas) along the start straight. */
export function buildAdBoards(ctx, atlas) {
  const T = ctx.T, rnd = mulberry32(31), H = atlas.signs.filter(s => s.kind === 'h');
  const sA = Math.round(T.startS) - 230, sB = Math.round(T.startS) + 120;
  for (let i = sA; i < sB; i += 7) {
    const { t, r, p } = tbasis(T, i), B = T.hw[i] + WALL_OFFSET, ch = ctx.chunkOfI(i);
    const g = ctx.geo('sign', ch), gs = ctx.geo('steel', ch); gs.lv(0);
    for (const sd of [1, -1]) {
      if (rnd() < 0.15) continue;
      const u = sd * (B + BARRIER_T + 0.15);
      const d = H[Math.floor(rnd() * H.length)];
      const sw = 6.6, sh = 1.65, yc = 0.95 + sh / 2 + 0.05;
      const n = [-r[0] * sd, -r[1] * sd], right = [n[1], -n[0]];
      const c = [p[0] + r[0] * u, yc, p[2] + r[1] * u];
      const hx = right[0] * sw / 2, hz = right[1] * sw / 2;
      const k = 0.4 + rnd() * .2;
      g.color(k, k, k, 1); g.ex('aFl', rnd() * 6, 0);
      g.quadUV([c[0] - hx, c[1] - sh / 2, c[2] - hz], [c[0] + hx, c[1] - sh / 2, c[2] + hz], [c[0] + hx, c[1] + sh / 2, c[2] + hz], [c[0] - hx, c[1] + sh / 2, c[2] - hz], [[d.u0, d.v0], [d.u1, d.v0], [d.u1, d.v1], [d.u0, d.v1]]);
      gs.color(.1, .11, .13, 1);
      gs.box(c[0] - n[0] * 0.14, c[1], c[2] - n[1] * 0.14, sw + .2, sh + .2, .25, roty(right[0], right[1]));
      for (const e of [-sw / 2 + .2, sw / 2 - .2]) gs.box(c[0] + right[0] * e - n[0] * .2, c[1] - sh / 2 - .45, c[2] + right[1] * e - n[1] * .2, .12, .9, .12, 0);
    }
  }
}

/** Skybridge across the boulevard. */
export function buildSkybridge(ctx) {
  const T = ctx.T;
  let i = -1;
  for (let k = 0; k < T.N; k++) if (T.kind[k] === KIND.GROUND && T.zoneNames[T.zone[k]] === 'boulevard' && Math.abs(T.pz[k] + 170) < 0.6 && Math.abs(T.px[k]) < 2) { i = k; break; }
  if (i < 0) return;
  const { t, r, p } = tbasis(T, i), B = T.hw[i] + WALL_OFFSET, SW = SIDEWALK.boulevard, ch = ctx.chunkOfI(i);
  const half = B + BARRIER_T + SW + 0.2, y = 23;
  const gs = ctx.geo('steel', ch), gc = ctx.geo('concD', ch), ge = ctx.geo('em6', ch), gg = ctx.geo('glass', ch);
  gs.lv(0); gc.lv(0); ge.lv(0); gg.lv(0);
  const ry = roty(r[0], r[1]), ry2 = roty(t[0], t[1]);
  const P = (u, yy, s = 0) => [p[0] + r[0] * u + t[0] * s, yy, p[2] + r[1] * u + t[1] * s];
  // tube: dark body + continuous glass band lit from inside + roof truss
  gs.color(.14, .15, .18, 1); const c0 = P(0, y); gs.box(c0[0], c0[1], c0[2], 2 * half, 3.6, 4.4, ry);
  ge.color(.7, .9, 1, 1);
  for (const s of [-2.23, 2.23]) { const c = P(0, y + .1, s); ge.box(c[0], c[1], c[2], 2 * half - 1.6, 1.4, 0.06, ry); }
  gs.color(.3, .32, .36, 1);
  for (let u = -half + 3; u < half; u += 6) { const c = P(u, y + 2.2); gs.box(c[0], c[1], c[2], .3, .4, 4.6, ry2 + 0); }
  // legs
  for (const sd of [1, -1]) {
    const c = P(sd * (B + BARRIER_T + 1.6), y / 2 - 0.9); gc.color(.45, .46, .5, 1); gc.box(c[0], c[1], c[2], 1.6, y - 1.8, 2.4, ry2);
  }
  for (const u of [-6, 6]) ctx.light({ pos: P(u, y - 2.3), color: [.7, .9, 1], intensity: 300, range: 26, kind: 'sign' }, 0);
}

/** Expressway overhead sign gantries. */
export function buildGantries(ctx, rs) {
  const T = ctx.T, N = T.N, rnd = mulberry32(900);
  let last = -1000, n = 0;
  const CH = [[0, 0], [1, 0], [0, 2], [2, 0], [1, 2], [3, 0], [2, 2], [3, 2]];
  for (let i = 40; i < N; i += 10) {
    if (!(T.kind[i] === KIND.ELEVATED && T.py[i] > 9) || i - last < 330) continue;
    last = i;
    const { t, r, p } = tbasis(T, i), B = T.hw[i] + WALL_OFFSET, ch = ctx.chunkOfI(i), y0 = T.py[i];
    const gs = ctx.geo('steel', ch), gr = ctx.geo('roadsign', ch); gs.lv(1); gr.lv(1);
    const ry = roty(r[0], r[1]), ry2 = roty(t[0], t[1]);
    const P = (u, yy, s = 0) => [p[0] + r[0] * u + t[0] * s, yy, p[2] + r[1] * u + t[1] * s];
    gs.color(.3, .32, .36, 1);
    for (const sd of [1, -1]) { const c = P(sd * (B + .25), y0 + 5.3); gs.box(c[0], c[1], c[2], .5, 10.6, .5, ry2); }
    const bc = P(0, y0 + 10.4); gs.box(bc[0], bc[1], bc[2], 2 * B + 1.4, .55, .7, ry);
    const bc2 = P(0, y0 + 9.2); gs.box(bc2[0], bc2[1], bc2[2], 2 * B + 1.4, .18, .18, ry);
    // 2-3 signs facing the oncoming traffic (normal -t)
    const cnt = 2 + (n & 1);
    for (let k = 0; k < cnt; k++) {
      const [c, rr_] = CH[(n * 3 + k * 5) % CH.length];
      const uv = rs.uv(c, rr_);
      const sw = 5.0, sh = 2.5, uc = (k - (cnt - 1) / 2) * (2 * B - 0.5) / cnt;
      const cc = P(uc, y0 + 7.0, -0.42);
      const nn = [-t[0], -t[1]], right = [nn[1], -nn[0]];
      const hx2 = right[0] * sw / 2, hz2 = right[1] * sw / 2;
      gr.color(1, 1, 1, 1);
      gr.quadUV([cc[0] - hx2, cc[1] - sh / 2, cc[2] - hz2], [cc[0] + hx2, cc[1] - sh / 2, cc[2] + hz2], [cc[0] + hx2, cc[1] + sh / 2, cc[2] + hz2], [cc[0] - hx2, cc[1] + sh / 2, cc[2] - hz2], [[uv.u0, uv.v0], [uv.u1, uv.v0], [uv.u1, uv.v1], [uv.u0, uv.v1]]);
      gs.color(.12, .13, .15, 1); const cb = P(uc, y0 + 7.0, -0.3); gs.box(cb[0], cb[1], cb[2], sw + .2, sh + .2, .22, ry);
      for (const e of [-1, 1]) { const ch2 = P(uc + e * sw * .35, y0 + 8.9, -0.35); gs.box(ch2[0], ch2[1], ch2[2], .1, 1.4, .1, 0); }
      ctx.light({ pos: P(uc, y0 + 8.6, -3), color: [.8, 1, .9], intensity: 140, range: 14, kind: 'sign' }, 1);
    }
    n++;
  }
}

/** Tunnel portal signs + exit signs inside. */
export function buildTunnelSigns(ctx, rs) {
  const T = ctx.T, N = T.N;
  const runs = [];
  let a = -1;
  for (let i = 0; i <= N; i++) {
    const isT = i < N && T.kind[i] === KIND.TUNNEL;
    if (isT && a < 0) a = i;
    if (!isT && a >= 0) { runs.push([a, i]); a = -1; }
  }
  for (const [i0, i1] of runs) {
    // portal sign (facing approach)
    for (const [i, dir] of [[i0, 1], [i1 - 1, -1]]) {
      if (dir < 0) continue;
      const { t, r, p } = tbasis(T, i), B = T.hw[i] + WALL_OFFSET, ch = ctx.chunkOfI(i);
      const gr = ctx.geo('roadsign', ch); gr.lv(0);
      const uv = rs.uv(1, 0);
      const n = [-t[0] * dir, -t[1] * dir], right = [n[1], -n[0]], w = 4.4, hh = 2.2;
      const c = [p[0] + n[0] * 0.05, T.py[i] + CEIL_H - 1.0 + 0.95, p[2] + n[1] * 0.05];
      // mount slightly in front of the headwall face (the face is at the portal sample)
      const hx = right[0] * w / 2, hz = right[1] * w / 2;
      gr.color(1, 1, 1, 1);
      gr.quadUV([c[0] - hx, c[1] - hh / 2, c[2] - hz], [c[0] + hx, c[1] - hh / 2, c[2] + hz], [c[0] + hx, c[1] + hh / 2, c[2] + hz], [c[0] - hx, c[1] + hh / 2, c[2] - hz], [[uv.u0, uv.v0], [uv.u1, uv.v0], [uv.u1, uv.v1], [uv.u0, uv.v1]]);
      ctx.light({ pos: [c[0] + n[0] * 3, c[1] + 1, c[2] + n[1] * 3], color: [.8, 1, .9], intensity: 160, range: 14, kind: 'sign' }, 0);
    }
    // exit signs on alternating walls
    for (let i = i0 + 40, k = 0; i < i1 - 15; i += 80, k++) {
      const { t, r, p } = tbasis(T, i), B = T.hw[i] + WALL_OFFSET, ch = ctx.chunkOfI(i), sd = k & 1 ? 1 : -1;
      const gr = ctx.geo('roadsign', ch); gr.lv(2);
      const uv = rs.uv(k % 3 === 0 ? 0 : k % 3, 3);
      const n = [-r[0] * sd, -r[1] * sd], right = [n[1], -n[0]], w = 1.8, hh = 0.9;
      const c = [p[0] + r[0] * sd * (B - 0.04), T.py[i] + 3.6, p[2] + r[1] * sd * (B - 0.04)];
      const hx = right[0] * w / 2, hz = right[1] * w / 2;
      // face the oncoming traffic by rotating the board 35° towards -t
      const ang = 0.0;
      gr.color(1, 1, 1, 1);
      gr.quadUV([c[0] - hx, c[1] - hh / 2, c[2] - hz], [c[0] + hx, c[1] - hh / 2, c[2] + hz], [c[0] + hx, c[1] + hh / 2, c[2] + hz], [c[0] - hx, c[1] + hh / 2, c[2] - hz], [[uv.u0, uv.v0], [uv.u1, uv.v0], [uv.u1, uv.v1], [uv.u0, uv.v1]]);
    }
  }
}
