// Trench dressing: wall-mounted sodium lamps, graffiti tags, (cable trays live in the barrier kit).
import { KIND, WALL_OFFSET } from '../track/track.js';
import { mulberry32 } from './util.js';
import { signQuad } from './signs.js';
import { addHalo } from './signs.js';
import { edgeY } from './barriers.js';

const SODIUM = [1.0, 0.56, 0.2];

export function buildTrench(ctx, graf) {
  const T = ctx.T, N = T.N, rnd = mulberry32(2323);
  const isTrench = (i) => T.kind[i] === KIND.TRENCH || (T.kind[i] === KIND.GROUND && T.py[i] < -0.04);
  const depth = (i) => -edgeY(T, i) + 1.0;           // retaining-wall height above the road edge
  let nL = 0, nG = 0, side = 0, nextG = 8;
  for (let i = 4; i < N - 4; i++) {
    if (!isTrench(i) || depth(i) < 3.6) continue;
    const th = Math.hypot(T.tx[i], T.tz[i]), rh = Math.hypot(T.rx[i], T.rz[i]);
    const t = [T.tx[i] / th, T.tz[i] / th], r = [T.rx[i] / rh, T.rz[i] / rh], B = T.hw[i] + WALL_OFFSET;
    const ch = ctx.chunkOfI(i);
    // wall lamps every 20 m, alternating sides
    if (i % 20 === 0) {
      const sd = (side++ & 1) ? 1 : -1, uW = sd * (B + .65), uH = sd * (B + .12);
      const wx = T.px[i] + T.rx[i] * uW, wz = T.pz[i] + T.rz[i] * uW, hx = T.px[i] + T.rx[i] * uH, hz = T.pz[i] + T.rz[i] * uH;
      const y = T.py[i] + T.ry[i] * uW + 4.4, yh = T.py[i] + T.ry[i] * uH + 4.4;
      const gs = ctx.geo('steel', ch); gs.lv(0); gs.color(.25, .27, .3, 1);
      const ry = Math.atan2(-(hz - wz), hx - wx);
      gs.box((wx + hx) / 2, (y + yh) / 2, (wz + hz) / 2, Math.hypot(hx - wx, hz - wz) + .1, .1, .1, ry);
      gs.box(hx, yh - .08, hz, .9, .14, .4, ry);
      const ge = ctx.geo('em40', ch); ge.lv(0); ge.color(SODIUM[0], SODIUM[1], SODIUM[2], 1);
      ge.box(hx, yh - .17, hz, .8, .03, .3, ry, 'y');
      ctx.light({ pos: [hx, yh - .35, hz], color: SODIUM, intensity: 420, range: 28, kind: 'street', dir: [0, -1, 0], angle: 1.25, penumbra: .7 }, 0);
      addHalo(ctx, ch, hx, yh - .25, hz, 2.6, .5, .28, .1);
      nL++;
    }
    // graffiti tags
    if (i >= nextG) {
      nextG = i + 14 + Math.floor(rnd() * 34);
      const sd = rnd() < .5 ? 1 : -1, w = 3 + rnd() * 3.2, h = w / 2, u = sd * (B + .645);
      const c = [T.px[i] + T.rx[i] * u, T.py[i] + T.ry[i] * u + 0.95 + h / 2 + rnd() * .2, T.pz[i] + T.rz[i] * u];
      const nrm = [-sd * r[0], -sd * r[1]], right = [nrm[1], -nrm[0]];
      if (depth(i) < 3.2 + h) continue;
      const g = ctx.geo('graf', ch); g.lv(0); g.color(1, 1, 1, 1);
      signQuad(g, [c[0] + nrm[0] * .02, c[1], c[2] + nrm[1] * .02], right, 0, w, h, graf.uv(Math.floor(rnd() * graf.cells)), nrm);
      nG++;
    }
  }
  ctx.stats.trenchLamps = nL; ctx.stats.graffiti = nG;
}
