// Barriers along both sides of the whole lap. The collision face is at |u| = hw + WALL_OFFSET; every kit starts exactly there.
// Kits are chosen per sample from (kind, zone, road height) and extruded as runs (with end caps where the kit changes).
import { KIND, WALL_OFFSET } from '../track/track.js';
import { extrudeRun } from './extrude.js';
import { levelOfSample } from './ctx.js';
import { hash2 } from './util.js';

export const CEIL_H = 5.6;           // tunnel clear height
const GREY = [0.62, 0.64, 0.68], DARK = [0.34, 0.36, 0.40];

/** Road height at the barrier foot (right side, bank included). */
export function edgeY(T, i) { return T.py[i] + T.ry[i] * (T.hw[i] + WALL_OFFSET); }

export function kitOf(ctx, i) {
  const T = ctx.T, k = T.kind[i], z = T.zoneNames[T.zone[i]], yR = edgeY(T, i);
  if (k === KIND.TUNNEL) return 'tunnel';
  if (k === KIND.TRENCH || (k === KIND.GROUND && T.py[i] < -0.04)) return 'trench';
  if (k === KIND.BRIDGE) return 'bridge';
  if (k === KIND.ELEVATED) {
    if (yR < 5.0) return 'embank';
    const v = Math.floor(hash2(Math.floor(i / 72), 5) * 3);
    return 'expy' + v;
  }
  if (yR > 0.12) return 'embank';
  return 'jersey_' + z;
}

const EMPTY = { key: 'rib', pts: [] };
const jerseyPts = (B) => [[B, 0], [B + .65, 0], [B + .65, .85], [B + .25, .85], [B + .13, .5], [B, .16]];

function skirt(T, i, B, col) {
  const yR = edgeY(T, i);
  if (yR <= 0.02) return EMPTY;
  const h = yR + 0.02;
  return { key: 'rib', pts: [[B, -h], [B + .65, -h], [B + .65, 0.02], [B, 0.02]], col: [...col, 1], uvs: 1 };
}

export function polysFor(ctx, kit, i) {
  const T = ctx.T, B = T.hw[i] + WALL_OFFSET, yR = edgeY(T, i);
  const out = [];
  if (kit.startsWith('jersey_') || kit === 'embank' || kit === 'trench') {
    const z = kit.startsWith('jersey_') ? kit.slice(7) : T.zoneNames[T.zone[i]];
    const col = z === 'docks' ? [0.62, 0.58, 0.5] : z === 'market' ? [0.5, 0.5, 0.52] : z === 'boulevard' ? [0.72, 0.74, 0.8] : GREY;
    out.push({ key: 'conc', pts: jerseyPts(B), col: [...col, 1] });
    if (z === 'boulevard' || z === 'street' || z === 'docks') out.push({ key: 'em6', pts: [[B + .28, .85], [B + .42, .85], [B + .42, .875], [B + .28, .875]], col: z === 'boulevard' ? [0.2, 0.9, 1.0, 1] : z === 'street' ? [1.0, 0.3, 0.8, 1] : [1.0, 0.6, 0.15, 1], nocap: true });
    out.push(kit !== 'trench' ? skirt(T, i, B, DARK) : EMPTY);
    if (kit === 'trench') {
      const hTop = -yR + 1.0;
      out.push({ key: 'rib', pts: [[B + .65, 0], [B + 1.7, 0], [B + 1.7, hTop], [B + .65, hTop]], col: [0.55, 0.56, 0.6, 1] });
      out.push({ key: 'conc', pts: [[B + .55, hTop - .35], [B + 1.8, hTop - .35], [B + 1.8, hTop + .1], [B + .55, hTop + .1]], col: [0.7, 0.72, 0.76, 1] });
      if (hTop > 3.4) {          // cable trays on the retaining wall (steel shelf + cable bundle + coloured tie)
        out.push({ key: 'steel', pts: [[B + .3, 2.4], [B + .65, 2.4], [B + .65, 2.55], [B + .3, 2.55]], col: [0.38, 0.4, 0.44, 1] });
        out.push({ key: 'paint', pts: [[B + .38, 2.55], [B + .63, 2.55], [B + .63, 2.8], [B + .38, 2.8]], col: [0.04, 0.04, 0.05, 1] });
        out.push({ key: 'paint', pts: [[B + .44, 2.8], [B + .58, 2.8], [B + .58, 2.88], [B + .44, 2.88]], col: [0.7, 0.2, 0.08, 1] });
      } else out.push(EMPTY, EMPTY, EMPTY);
    }
    return out;
  }
  if (kit.startsWith('expy')) {
    const v = +kit.slice(4);
    out.push({ key: 'conc', pts: [[B, 0], [B + .55, 0], [B + .55, 1.12], [B + .1, 1.12], [B, 1.0]], col: [0.7, 0.72, 0.76, 1] });
    out.push({ key: 'em6', pts: [[B - .015, .5], [B, .5], [B, .56], [B - .015, .56]], col: [0.2, 0.85, 1.0, 1], nocap: true });
    if (v === 0) {
      out.push({ key: 'glass', pts: [[B + .12, 1.12], [B + .18, 1.12], [B + .18, 4.0], [B + .12, 4.0]], col: [0.7, 0.85, 0.9, 1] });
      out.push({ key: 'steel', pts: [[B + .08, 4.0], [B + .24, 4.0], [B + .24, 4.14], [B + .08, 4.14]], col: [0.5, 0.52, 0.56, 1] });
    } else if (v === 1) {
      out.push({ key: 'paint', pts: [[B + .12, 1.12], [B + .2, 1.12], [B + .2, 3.4], [B + .12, 3.4]], col: [0.2, 0.28, 0.3, 1] });
      out.push({ key: 'steel', pts: [[B + .08, 3.4], [B + .26, 3.4], [B + .26, 3.52], [B + .08, 3.52]], col: [0.5, 0.52, 0.56, 1] });
    } else {
      out.push({ key: 'steel', pts: [[B + .12, 1.4], [B + .2, 1.4], [B + .2, 1.5], [B + .12, 1.5]], col: [0.55, 0.57, 0.6, 1] });
      out.push({ key: 'steel', pts: [[B + .12, 1.75], [B + .2, 1.75], [B + .2, 1.85], [B + .12, 1.85]], col: [0.55, 0.57, 0.6, 1] });
    }
    return out;
  }
  if (kit === 'bridge') {
    out.push({ key: 'conc', pts: [[B, 0], [B + .5, 0], [B + .5, .6], [B, .6]], col: [0.6, 0.62, 0.66, 1] });
    out.push({ key: 'steel', pts: [[B + .1, .95], [B + .2, .95], [B + .2, 1.05], [B + .1, 1.05]], col: [0.4, 0.45, 0.5, 1] });
    out.push({ key: 'steel', pts: [[B + .1, 1.22], [B + .2, 1.22], [B + .2, 1.34], [B + .1, 1.34]], col: [0.4, 0.45, 0.5, 1] });
    out.push({ key: 'em6', pts: [[B + .1, .6], [B + .4, .6], [B + .4, .62], [B + .1, .62]], col: [0.5, 0.2, 0.05, 1], nocap: true });
    return out;
  }
  if (kit === 'tunnel') {
    const hc = CEIL_H;
    out.push({ key: 'tile', pts: [[B, 0], [B + .4, 0], [B + .4, hc], [B - 1.2, hc], [B, hc - 1.2]], col: [0.5, 0.58, 0.66, 1] });
    out.push({ key: 'conc', pts: [[B, 0], [B + .02, 0], [B + .02, .32], [B, .32]], col: [0.5, 0.5, 0.52, 1], nocap: true });
    return out;
  }
  return out;
}

export function buildBarriers(ctx) {
  const T = ctx.T, N = T.N;
  const kits = new Array(N);
  for (let i = 0; i < N; i++) kits[i] = kitOf(ctx, i);
  let start = 0; while (start < N && kits[start] === kits[(start - 1 + N) % N]) start++;
  if (start >= N) start = 0;
  let i0 = start;
  for (let n = 1; n <= N; n++) {
    const i = start + n;
    if (n === N || kits[i % N] !== kits[i0 % N]) {
      const kit = kits[i0 % N];
      extrudeRun(ctx, (ii) => polysFor(ctx, kit, ii), i0, i, { lvlFn: (ii) => levelOfSample(T, ii) });
      i0 = i;
    }
  }
  // tunnel ceiling slab (central, not mirrored)
  const kT = ctx.T.kind;
  let a = -1;
  for (let i = 0; i <= N; i++) {
    const isT = i < N && kT[i] === KIND.TUNNEL;
    if (isT && a < 0) a = i;
    if (!isT && a >= 0) {
      extrudeRun(ctx, (ii) => {
        const B = T.hw[ii] + WALL_OFFSET - 1.2, hc = CEIL_H;
        return [{ key: 'conc', pts: [[-B, hc], [B, hc], [B, hc + .6], [-B, hc + .6]], col: [0.34, 0.36, 0.4, 1] }];
      }, a, i, { sides: [0], lvl: 2 });
      a = -1;
    }
  }
}
