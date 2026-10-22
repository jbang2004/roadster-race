// World build context: chunked merged geometry per material, light registration (with a "level" for the bake), track sample access.
import * as THREE from 'three';
import { lights } from '../core/lights.js';
import { Geo } from './util.js';
import { KIND } from '../track/track.js';

export const CHUNK = 100;   // metres of track per chunk (index = floor(i / CHUNK) for track-aligned geometry)

/** Light level of a road sample: 0 = street level (incl. canal/trench), 1 = expressway deck, 2 = tunnel. */
export function levelOfSample(T, i) {
  const k = T.kind[i];
  if (k === KIND.TUNNEL) return 2;
  if (k === KIND.ELEVATED && T.py[i] > 7) return 1;
  if (k === KIND.GROUND && T.py[i] > 7) return 1;
  return 0;
}

export class Ctx {
  constructor(app, track, defs) {
    this.app = app; this.T = track; this.defs = defs;       // defs: key → { extras, bake, layer, ... }
    this.buckets = new Map();                                // `${key}|${chunk}` → Geo
    this.lightMeta = [];                                     // lights added by the world (with lvl)
    this.nChunks = Math.ceil(track.N / CHUNK);
    this.stats = { lamps: 0 };
    this._buildDist();
  }
  /** Coarse (10 m) distance-to-road grid over the whole bounds, to 220 m (field() is clamped to 80 m). */
  _buildDist() {
    const T = this.T, B = T.layout.bounds, c = 10, W = Math.ceil((B.x1 - B.x0) / c), H = Math.ceil((B.z1 - B.z0) / c);
    const d = new Float32Array(W * H).fill(220), idx = new Int32Array(W * H).fill(-1);
    const R = 230;
    for (let i = 0; i < T.N; i += 2) {
      const x = T.px[i], z = T.pz[i], hw = T.hw[i];
      const gx0 = Math.max(0, Math.floor((x - R - B.x0) / c)), gx1 = Math.min(W - 1, Math.ceil((x + R - B.x0) / c));
      const gz0 = Math.max(0, Math.floor((z - R - B.z0) / c)), gz1 = Math.min(H - 1, Math.ceil((z + R - B.z0) / c));
      for (let gz = gz0; gz <= gz1; gz++) {
        const cz = B.z0 + (gz + .5) * c, dz2 = (cz - z) ** 2;
        for (let gx = gx0; gx <= gx1; gx++) {
          const cx = B.x0 + (gx + .5) * c;
          const dd = Math.sqrt((cx - x) ** 2 + dz2) - hw;
          const k = gz * W + gx;
          if (dd < d[k]) { d[k] = dd; idx[k] = i; }
        }
      }
    }
    this.D = { W, H, c, x0: B.x0, z0: B.z0, d, idx };
  }
  /** Approximate distance from (x,z) to the nearest road edge (any level), up to 220 m. Exact (2 m grid) within 80 m. */
  dist(x, z) {
    const f = this.T.field(x, z, this._fd ??= {});
    if (f.all < 79) return f.all;
    const D = this.D, gx = Math.floor((x - D.x0) / D.c), gz = Math.floor((z - D.z0) / D.c);
    if (gx < 0 || gz < 0 || gx >= D.W || gz >= D.H) return 220;
    return D.d[gz * D.W + gx];
  }
  /** Index of the nearest road sample (coarse beyond 80 m). */
  nearI(x, z) {
    const f = this.T.field(x, z, this._fi ??= {});
    if (f.i >= 0) return f.i;
    const D = this.D, gx = Math.floor((x - D.x0) / D.c), gz = Math.floor((z - D.z0) / D.c);
    if (gx < 0 || gz < 0 || gx >= D.W || gz >= D.H) return 0;
    return Math.max(0, D.idx[gz * D.W + gx]);
  }
  chunkOfI(i) { return Math.floor(this.T.wrapIndex(i) / CHUNK); }
  /** Chunk of the road sample nearest to a world position (city objects). */
  chunkAt(x, z) { return this.chunkOfI(this.nearI(x, z)); }
  geo(key, chunk) {
    const k = key + '|' + chunk;
    let g = this.buckets.get(k);
    if (!g) {
      const d = this.defs[key];
      if (!d) throw new Error('unknown material key ' + key);
      g = new Geo(d.extras ?? {}); g.key = key; g.chunk = chunk; this.buckets.set(k, g);
    }
    return g;
  }
  /** Register a static light in the global registry, remembering its light level for the bake. */
  light(o, lvl = 0) {
    const rec = lights.add(o); rec.lvl = lvl; this.lightMeta.push(rec); return rec;
  }
}
