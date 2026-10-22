// Street lamps, expressway twin-head lamps, trench lamps, tunnel LED lines + jet fans, deck underside lights, barrier posts/delineators.
// Every lamp registers its light in the global registry (via ctx.light) with the light level used by the bake.
import * as THREE from 'three';
import { KIND, WALL_OFFSET } from '../track/track.js';
import { levelOfSample } from './ctx.js';
import { edgeY, kitOf, CEIL_H } from './barriers.js';
import { SIDEWALK, BARRIER_T } from './params.js';
import { hash2 } from './util.js';
import { extrudeRun } from './extrude.js';

const SODIUM = [1.0, 0.56, 0.2], WARM = [1.0, 0.82, 0.55], COOL = [0.78, 0.86, 1.0], CYAN = [0.4, 0.9, 1.0];

/** Add a pole lamp. base = [x,y,z]; toRoad = horizontal unit [dx,dz] pointing from the pole towards the road. */
export function addLamp(ctx, base, toRoad, o = {}) {
  const { H = 9, arm = 2.4, col = SODIUM, cd = 400, range = 30, lvl = 0, heads = 1, headSpacing = 1.4, chunk, kind = 'street', poleCol = [0.22, 0.24, 0.27] } = o;
  const [x, y, z] = base, [dx, dz] = toRoad, ch = chunk ?? ctx.chunkAt(x, z);
  const ry = Math.atan2(-dz, dx);
  const gs = ctx.geo('steel', ch); gs.lv(lvl); gs.color(poleCol[0], poleCol[1], poleCol[2], 1);
  gs.cyl(x, y, z, 0.17, 0.09, H, 10, true);
  gs.cyl(x, y, z, 0.3, 0.3, 0.35, 10, true);                                   // base collar
  // arm: slightly rising box from the pole top towards the road
  const ax = x + dx * arm * 0.5, az = z + dz * arm * 0.5;
  gs.box(ax, y + H + 0.12, az, arm, 0.1, 0.1, ry);
  const ge = ctx.geo('em40', ch); ge.lv(lvl);
  for (let k = 0; k < heads; k++) {
    const t = arm - k * headSpacing;
    const hx = x + dx * t, hz = z + dz * t, hy = y + H + 0.1;
    gs.color(0.3, 0.32, 0.36, 1);
    gs.box(hx, hy, hz, 0.95, 0.14, 0.38, ry);                                  // housing
    ge.color(col[0], col[1], col[2], 1);
    ge.quadP([hx - dx * 0.4 - dz * 0.16, hy - 0.075, hz - dz * 0.4 + dx * 0.16], [hx + dx * 0.4 - dz * 0.16, hy - 0.075, hz + dz * 0.4 + dx * 0.16],
      [hx + dx * 0.4 + dz * 0.16, hy - 0.075, hz + dz * 0.4 - dx * 0.16], [hx - dx * 0.4 + dz * 0.16, hy - 0.075, hz - dz * 0.4 - dx * 0.16]);
    ctx.light({ pos: [hx, hy - 0.2, hz], color: col, intensity: cd, range, kind, dir: [0, -1, 0], angle: 1.15, penumbra: 0.6 }, lvl);
    ctx.stats.lamps++;
  }
}

function frameAtI(T, i) { return { x: T.px[i], y: T.py[i], z: T.pz[i], rx: T.rx[i], ry: T.ry[i], rz: T.rz[i], tx: T.tx[i], tz: T.tz[i] }; }

export function buildLamps(ctx) {
  const T = ctx.T, N = T.N;
  const zn = (i) => T.zoneNames[T.zone[i]];
  // ----- ground-level street lamps -----
  for (let i = 0; i < N; i++) {
    const z = zn(i), k = T.kind[i];
    if (k !== KIND.GROUND || edgeY(T, i) > 0.3 || edgeY(T, i) < -0.04) continue;
    let sp = 30, both = false, col = SODIUM, cd = 380, H = 9.5, arm = 2.6;
    if (z === 'boulevard') { sp = 34; both = true; col = COOL; cd = 450; H = 11; arm = 3.2; }
    else if (z === 'street') { sp = 30; col = [0.95, 0.9, 0.8]; cd = 380; H = 9; }
    else if (z === 'docks') { sp = 32; col = SODIUM; cd = 420; H = 10; }
    else if (z === 'market' || z === 'ramp' || z === 'descent') { sp = 36; col = WARM; cd = 300; H = 8; arm = 2.0; }
    else continue;
    if (i % sp !== 7) continue;
    const n = Math.floor(i / sp);
    for (const sd of both ? [1, -1] : [n & 1 ? 1 : -1]) {
      const B = T.hw[i] + WALL_OFFSET, u = sd * (B + BARRIER_T + 0.7);
      const px = T.px[i] + T.rx[i] * u, pz = T.pz[i] + T.rz[i] * u;
      const hh = Math.hypot(T.rx[i], T.rz[i]);
      addLamp(ctx, [px, 0.15, pz], [-sd * T.rx[i] / hh, -sd * T.rz[i] / hh], { H, arm, col, cd, lvl: 0, chunk: ctx.chunkOfI(i), kind: 'street' });
    }
  }
  // ----- expressway / ramp: twin-head lamps on tall poles behind the parapet -----
  let alt = 0;
  for (let i = 0; i < N; i += 20) {
    if (T.kind[i] !== KIND.ELEVATED || T.py[i] < 6) continue;
    const sd = (alt++ & 1) ? 1 : -1;
    const B = T.hw[i] + WALL_OFFSET, u = sd * (B + 0.3);
    const px = T.px[i] + T.rx[i] * u, py = T.py[i] + T.ry[i] * u + 1.0, pz = T.pz[i] + T.rz[i] * u;
    const hh = Math.hypot(T.rx[i], T.rz[i]);
    addLamp(ctx, [px, py, pz], [-sd * T.rx[i] / hh, -sd * T.rz[i] / hh], { H: 10.5, arm: 4.6, heads: 2, headSpacing: 2.2, col: SODIUM, cd: 400, range: 35, lvl: 1, chunk: ctx.chunkOfI(i), kind: 'street' });
  }
  // ----- trench: lamps on the wall tops -----
  for (let i = 0; i < N; i += 24) {
    if (!(T.kind[i] === KIND.TRENCH)) continue;
    for (const sd of [1, -1]) {
      const B = T.hw[i] + WALL_OFFSET + 1.7, u = sd * (B + 0.5);
      const px = T.px[i] + T.rx[i] * u, pz = T.pz[i] + T.rz[i] * u;
      const hh = Math.hypot(T.rx[i], T.rz[i]);
      addLamp(ctx, [px, 0.1, pz], [-sd * T.rx[i] / hh, -sd * T.rz[i] / hh], { H: 7.5, arm: 3.4, col: SODIUM, cd: 380, lvl: 0, chunk: ctx.chunkOfI(i), kind: 'street' });
    }
  }
}

/** Tunnel interior: continuous LED lines, light every 6 m, jet fans, emergency niches. */
export function buildTunnel(ctx) {
  const T = ctx.T, N = T.N;
  let a = -1;
  const runs = [];
  for (let i = 0; i <= N; i++) {
    const isT = i < N && T.kind[i] === KIND.TUNNEL;
    if (isT && a < 0) a = i;
    if (!isT && a >= 0) { runs.push([a, i]); a = -1; }
  }
  for (const [i0, i1] of runs) {
    // LED lines under the ceiling edges (both sides) + a dim centre strip
    extrudeRun(ctx, (i) => {
      const B = T.hw[i] + WALL_OFFSET - 1.25;
      return [{ key: 'em6', pts: [[B - .09, CEIL_H - .01], [B + .09, CEIL_H - .01], [B + .09, CEIL_H + .03], [B - .09, CEIL_H + .03]], col: [0.85, 0.92, 1.0, 1], nocap: true }];
    }, i0, i1, { lvl: 2, caps: false });
    extrudeRun(ctx, (i) => {
      const B = T.hw[i] + WALL_OFFSET;
      return [{ key: 'em6', pts: [[B - .01, 0.62], [B, 0.62], [B, 0.68], [B - .01, 0.68]], col: [0.8, 0.45, 0.1, 1], nocap: true }];
    }, i0, i1, { lvl: 2, caps: false });
    for (let i = i0 + 3; i < i1; i += 6) {
      const x = T.px[i], y = T.py[i] + CEIL_H - 0.3, z = T.pz[i];
      ctx.light({ pos: [x, y, z], color: [0.85, 0.92, 1.0], intensity: 60, range: 14, kind: 'tunnel' }, 2);
    }
    // jet fans: pairs every 60 m
    for (let i = i0 + 20; i < i1 - 10; i += 60) {
      const ch = ctx.chunkOfI(i), gs = ctx.geo('paint', ch); gs.lv(2); gs.color(0.01, 0.01, 0.012, 1);   // very dark: the fans hang within ~2 m of the ceiling LEDs, so baked light makes even a small albedo read pale
      const ry = Math.atan2(-T.tz[i], T.tx[i]);
      for (const u of [-2.0, 2.0]) {
        const cx = T.px[i] + T.rx[i] * u, cz = T.pz[i] + T.rz[i] * u, cy = T.py[i] + CEIL_H - 0.55;
        // fan body: horizontal cylinder along the tangent, approximated by an octagonal box stack
        gs.box(cx, cy, cz, 3.2, 0.9, 0.9, ry);
        gs.box(cx, cy, cz, 3.2, 0.65, 1.12, ry);
        gs.box(cx, cy + 0.62, cz, 0.3, 0.3, 0.3, ry);
        const ge = ctx.geo('em6', ch); ge.lv(2); ge.color(1.0, 0.25, 0.1, 1);
        ge.box(cx + T.tx[i] * 1.62, cy, cz + T.tz[i] * 1.62, 0.05, 0.3, 0.3, ry);
      }
    }
    // emergency niches: dark recess + green/red LEDs every 48 m on alternating sides
    for (let i = i0 + 24, n = 0; i < i1 - 10; i += 48, n++) {
      const sd = n & 1 ? 1 : -1, B = T.hw[i] + WALL_OFFSET;
      const ch = ctx.chunkOfI(i);
      const c = [T.px[i] + T.rx[i] * (sd * (B - 0.02)), T.py[i] + T.ry[i] * (sd * B), T.pz[i] + T.rz[i] * (sd * (B - 0.02))];
      const ry = Math.atan2(-T.tz[i], T.tx[i]);
      const g = ctx.geo('paint', ch); g.lv(2); g.color(0.04, 0.05, 0.06, 1);
      g.box(c[0], c[1] + 1.2, c[2], 2.4, 2.2, 0.06, ry);
      const ge = ctx.geo('em6', ch); ge.lv(2);
      ge.color(0.1, 1.0, 0.35, 1); ge.box(c[0] - sd * T.rx[i] * 0.06, c[1] + 2.45, c[2] - sd * T.rz[i] * 0.06, 0.9, 0.18, 0.04, ry);
      ge.color(1.0, 0.15, 0.1, 1); ge.box(c[0] - sd * T.rx[i] * 0.06, c[1] + 0.55, c[2] - sd * T.rz[i] * 0.06, 0.5, 0.35, 0.04, ry);
    }
  }
}

/** Deck underside lights (sodium, pointing down) so the boulevard under the expressway is lit from above. */
export function buildUndersideLights(ctx) {
  const T = ctx.T, N = T.N;
  for (let i = 0; i < N; i += 14) {
    if (T.kind[i] !== KIND.ELEVATED || T.py[i] < 8) continue;
    // only where the ground below is not a road other than... (all of the deck: cheap enough)
    for (const u of [-4, 4]) {
      const x = T.px[i] + T.rx[i] * u, z = T.pz[i] + T.rz[i] * u, y = T.py[i] - 2.3;
      const ch = ctx.chunkOfI(i);
      const ge = ctx.geo('em16', ch); ge.lv(0); ge.color(1.0, 0.66, 0.3, 1);
      const ry = Math.atan2(-T.tz[i], T.tx[i]);
      ge.box(x, y, z, 0.9, 0.08, 0.3, ry, 'y');
      ctx.light({ pos: [x, y - 0.3, z], color: [1.0, 0.66, 0.3], intensity: 350, range: 24, kind: 'street', dir: [0, -1, 0], angle: 1.2, penumbra: 0.7 }, 0);
    }
  }
}

/** Sound-wall posts and delineators. */
export function buildPosts(ctx) {
  const T = ctx.T, N = T.N;
  for (let i = 0; i < N; i++) {
    const kit = kitOf(ctx, i);
    const ch = ctx.chunkOfI(i), B = T.hw[i] + WALL_OFFSET;
    const ry = Math.atan2(-T.tz[i], T.tx[i]);
    if ((kit === 'expy0' || kit === 'expy1' || kit === 'expy2') && i % 3 === 0) {
      const top = kit === 'expy1' ? 3.5 : kit === 'expy2' ? 1.9 : 4.14;
      const g = ctx.geo('steel', ch); g.lv(levelOfSample(T, i)); g.color(0.36, 0.38, 0.42, 1);
      for (const sd of [1, -1]) {
        const u = sd * (B + 0.16);
        g.box(T.px[i] + T.rx[i] * u, T.py[i] + T.ry[i] * u + 1.1 + (top - 1.1) / 2, T.pz[i] + T.rz[i] * u, 0.14, top - 1.1, 0.22, ry);
      }
    }
    if (kit === 'bridge' && i % 3 === 0) {
      const g = ctx.geo('steel', ch); g.lv(0); g.color(0.3, 0.34, 0.4, 1);
      for (const sd of [1, -1]) {
        const u = sd * (B + 0.15);
        g.box(T.px[i] + T.rx[i] * u, T.py[i] + T.ry[i] * u + 0.7, T.pz[i] + T.rz[i] * u, 0.12, 1.4, 0.12, ry);
      }
    }
    // delineators on the barrier top (white right, amber left)
    if (i % 8 === 4 && (kit.startsWith('jersey_') || kit === 'embank' || kit.startsWith('expy'))) {
      const top = kit.startsWith('expy') ? 1.12 : 0.85, lv = levelOfSample(T, i);
      for (const sd of [1, -1]) {
        const u = sd * (B + (kit.startsWith('expy') ? 0.08 : 0.3));
        const g = ctx.geo('em2', ch); g.lv(lv);
        if (sd > 0) g.color(1, 1, 1, 1); else g.color(1, 0.55, 0.1, 1);
        g.box(T.px[i] + T.rx[i] * u, T.py[i] + T.ry[i] * u + top + 0.06, T.pz[i] + T.rz[i] * u, 0.22, 0.1, 0.06, ry);
      }
    }
  }
}
