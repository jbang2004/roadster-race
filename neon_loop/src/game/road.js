// Fast local road queries for the physics (hint-based walk along the track polyline, no allocation).
// Mirrors track.project() but is O(1) when the hint is close, which it always is for a moving car.
import { WALL_OFFSET } from '../track/track.js';

export class Road {
  constructor(track) {
    this.T = track;
    this.N = track.N;
    this.length = track.length;
    this.ds = track.ds;
    this.wall = WALL_OFFSET;
  }

  /** Nearest sample index to (x, y, z) without a hint (3D aware at crossovers). */
  seed(x, y, z) {
    return this.T.project({ x, y, z }).i;
  }

  /**
   * Probe the road at (x, z). hint = segment index near the answer. Fills `o`:
   *  i, t (segment, fraction), s, u (lateral offset, + right), y (surface height at lateral offset, clamped to the wall face),
   *  nx ny nz (surface normal), hw, rx rz (unit horizontal right vector), tx ty tz (road tangent), kind, curv, bank
   */
  probe(x, z, hint, o) {
    const T = this.T, N = this.N, px = T.px, pz = T.pz;
    let i = hint < 0 ? 0 : hint >= N ? hint % N : hint;
    let t = 0, prevMove = 0;
    for (let k = 0; k < 40; k++) {
      const j = i + 1 === N ? 0 : i + 1;
      const ex = px[j] - px[i], ez = pz[j] - pz[i];
      t = ((x - px[i]) * ex + (z - pz[i]) * ez) / (ex * ex + ez * ez);
      if (t < 0) {
        if (prevMove > 0) { t = 0; break; }     // nearest to the shared vertex
        i = i === 0 ? N - 1 : i - 1; prevMove = -1;
      } else if (t > 1) {
        if (prevMove < 0) { t = 1; break; }
        i = j; prevMove = 1;
      } else break;
    }
    if (t < 0) t = 0; else if (t > 1) t = 1;
    const j = i + 1 === N ? 0 : i + 1;
    const a = 1 - t;
    const cx = px[i] * a + px[j] * t, cz = pz[i] * a + pz[j] * t;
    const cy = T.py[i] * a + T.py[j] * t;
    const rx = T.rx[i] * a + T.rx[j] * t, ry = T.ry[i] * a + T.ry[j] * t, rz = T.rz[i] * a + T.rz[j] * t;
    const rh = Math.hypot(rx, rz);
    const hrx = rx / rh, hrz = rz / rh;
    const u = (x - cx) * hrx + (z - cz) * hrz;
    const hw = T.hw[i] * a + T.hw[j] * t;
    const lim = hw + this.wall;
    const uc = u > lim ? lim : u < -lim ? -lim : u;
    o.i = i; o.t = t; o.s = (i + t) * this.ds; o.u = u; o.hw = hw;
    o.y = cy + uc * ry / rh;
    const nx = T.ux[i] * a + T.ux[j] * t, ny = T.uy[i] * a + T.uy[j] * t, nz = T.uz[i] * a + T.uz[j] * t;
    const nl = Math.hypot(nx, ny, nz);
    o.nx = nx / nl; o.ny = ny / nl; o.nz = nz / nl;
    o.rx = hrx; o.rz = hrz;
    o.tx = T.tx[i] * a + T.tx[j] * t; o.ty = T.ty[i] * a + T.ty[j] * t; o.tz = T.tz[i] * a + T.tz[j] * t;
    o.kind = T.kind[i];
    o.curv = T.curv[i] * a + T.curv[j] * t;
    o.bank = T.bank[i] * a + T.bank[j] * t;
    return o;
  }
}

/** Deterministic small-scale road roughness (m): expansion joints on elevated / bridge sections, fine undulation elsewhere. */
export function roughness(s, u, kind) {
  let h = 0.0011 * Math.sin(s * 1.9 + u * 0.7) + 0.0008 * Math.sin(s * 4.7 + 1.3 + u * 1.9) + 0.0005 * Math.sin(s * 11.3 + u * 3.1);
  if (kind === 1 || kind === 4) {            // elevated deck / bridge: expansion joints every 30 m
    const f = (s % 30) / 30;
    if (f < 0.012) h -= 0.0045 * Math.sin(f / 0.012 * Math.PI);
  }
  return h;
}
