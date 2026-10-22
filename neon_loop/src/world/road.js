// Road surface ribbon: one strip per sample row, split by (chunk, zone, kind), out to the barrier face (hw + WALL_OFFSET).
import { WALL_OFFSET } from '../track/track.js';
import { CHUNK, levelOfSample } from './ctx.js';

const NC = 16;       // columns across the road

export function buildRoad(ctx) {
  const T = ctx.T, N = T.N;
  let cur = null, curKey = null, prevRow = -1;
  const row = (g, i, sOut) => {
    const hw = T.hw[i], B = hw + WALL_OFFSET, zk = T.zone[i] * 8 + T.kind[i];
    g.color(1, 1, 1, 1); g.ex('aRoad', 0, 0, hw, zk); g.lv(levelOfSample(T, i));
    const first = g.n;
    for (let c = 0; c <= NC; c++) {
      const u = -B + 2 * B * c / NC;
      const x = T.px[i] + T.rx[i] * u, y = T.py[i] + T.ry[i] * u, z = T.pz[i] + T.rz[i] * u;
      g.ex('aRoad', sOut, u, hw, zk);
      g.vert(x, y, z, T.ux[i], T.uy[i], T.uz[i], u, sOut);
    }
    return first;
  };
  for (let i = 0; i < N; i++) {
    const key = Math.floor(i / CHUNK) * 1000 + T.zone[i] * 8 + T.kind[i];
    const g = ctx.geo('road', Math.floor(i / CHUNK));
    if (key !== curKey) { curKey = key; cur = null; }
    if (!cur) cur = row(g, i, i);
    const nxt = row(g, i + 1 >= N ? 0 : i + 1, i + 1);
    // quads between row cur and nxt
    for (let c = 0; c < NC; c++) g.quad(cur + c, cur + c + 1, nxt + c + 1, nxt + c);
    cur = nxt;
    // next iteration continues in the same strip unless the key changes (then it re-creates its first row)
    const nk = i + 1 < N ? Math.floor((i + 1) / CHUNK) * 1000 + T.zone[i + 1] * 8 + T.kind[i + 1] : -1;
    if (nk !== curKey) cur = null;
  }
}
