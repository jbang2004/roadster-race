// City plan for everything beyond W's band: road distance field, district map and the quad-tree of tower lots.
import { distanceField, hash2, mulberry32, clamp, lerp, smoothstep } from './util.js';

const CELL = 5;           // m, road-distance grid resolution
const PAD = 900;          // m around the track hull

/** Distance (m) from the nearest road edge, any level. Exact enough (±5 m) inside the grid, analytic outside. */
export function buildRoadField(track) {
  let x0 = 1e9, x1 = -1e9, z0 = 1e9, z1 = -1e9;
  for (let i = 0; i < track.N; i++) {
    x0 = Math.min(x0, track.px[i]); x1 = Math.max(x1, track.px[i]); z0 = Math.min(z0, track.pz[i]); z1 = Math.max(z1, track.pz[i]);
  }
  const gx0 = x0 - PAD, gz0 = z0 - PAD;
  const w = Math.ceil((x1 - x0 + 2 * PAD) / CELL), h = Math.ceil((z1 - z0 + 2 * PAD) / CELL);
  const seeds = new Uint8Array(w * h);
  let hwSum = 0;
  for (let i = 0; i < track.N; i++) {
    const cx = Math.floor((track.px[i] - gx0) / CELL), cz = Math.floor((track.pz[i] - gz0) / CELL);
    seeds[cz * w + cx] = 1; hwSum += track.hw[i];
  }
  const hwAvg = hwSum / track.N;
  const d = distanceField(seeds, w, h);
  // distance to nearest seed CELL → metres to road edge (cell-quantisation bias ≈ half a cell, hw ≈ avg half width)
  const k = CELL, bias = hwAvg + CELL * 0.35;
  const hull = { x0, x1, z0, z1 };
  function dist(x, z) {
    const fx = (x - gx0) / CELL - 0.5, fz = (z - gz0) / CELL - 0.5;
    if (fx < 0 || fz < 0 || fx >= w - 1 || fz >= h - 1) {
      // outside the grid: distance to the hull rectangle + the grid padding
      const dx = Math.max(hull.x0 - x, 0, x - hull.x1), dz = Math.max(hull.z0 - z, 0, z - hull.z1);
      return Math.hypot(dx, dz) - 150;
    }
    const ix = fx | 0, iz = fz | 0, tx = fx - ix, tz = fz - iz;
    const a = d[iz * w + ix], b = d[iz * w + ix + 1], c = d[(iz + 1) * w + ix], e = d[(iz + 1) * w + ix + 1];
    return ((a + (b - a) * tx) * (1 - tz) + (c + (e - c) * tx) * tz) * k - bias;
  }
  return { dist, hull, w, h, d, gx0, gz0, cell: CELL, bias };
}

// ---------- smooth 2D value noise for district variation ----------
function vnoise(x, z, seed) {
  const ix = Math.floor(x), iz = Math.floor(z), fx = x - ix, fz = z - iz;
  const sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
  const a = hash2(ix, iz, seed), b = hash2(ix + 1, iz, seed), c = hash2(ix, iz + 1, seed), e = hash2(ix + 1, iz + 1, seed);
  return (a + (b - a) * sx) * (1 - sz) + (c + (e - c) * sx) * sz;
}

// [x, z, radius, strength]: downtown clusters; the boulevard looks north into the biggest one
export const CLUSTERS = [
  [60, -2100, 1100, 1.0], [1700, -1700, 900, 0.8], [2800, 200, 1000, 0.65], [1500, 2100, 1000, 0.7],
  [-150, 2500, 1100, 0.45], [-2000, 900, 900, 0.55], [-2100, -1500, 1000, 0.85], [-3000, -300, 900, 0.5],
  [3600, -2600, 1100, 0.6], [-4200, 2600, 1100, 0.5], [900, -3600, 1200, 0.75], [-1400, 3600, 1100, 0.5],
];
/** 0..~1.6 height multiplier: downtown clusters, plus irregular low-frequency variation. */
export function districtHeight(x, z) {
  let v = 0.32;
  for (const [cx, cz, r, s] of CLUSTERS) { const d = Math.hypot(x - cx, z - cz) / r; v += s * Math.exp(-d * d * 1.2); }
  const n = vnoise(x / 700, z / 700, 5) * 0.65 + vnoise(x / 260, z / 260, 9) * 0.35;
  return v * (0.55 + 0.9 * n);
}
/** Which colour theme dominates here: 0 warm/sodium, 1 cyan-teal, 2 magenta-violet, 3 mixed. */
export function districtTheme(x, z) {
  const n = vnoise(x / 520 + 7.3, z / 520 - 2.1, 21);
  return n < 0.28 ? 0 : n < 0.55 ? 1 : n < 0.82 ? 2 : 3;
}

export const LEVELS = [
  { cell: 72, minC: 190, name: 'A' },      // 190 m +
  { cell: 144, minC: 700, name: 'B' },
  { cell: 288, minC: 1750, name: 'C' },
  { cell: 576, minC: 3600, name: 'D' },
];
const RANGE = 6912;   // half extent of the lot lattice (12 × 576)

/**
 * Walk the quad-tree and return the lots (one main tower each).
 * lot: { x, z, w, d, h, level, rng-seed, theme, hm } — footprints already inset from the cell.
 */
export function planLots(track, field, canal, bounds, reserved = []) {
  const lots = [];
  const D = LEVELS[3].cell;
  const nD = Math.ceil(RANGE / D);
  const skip = (x, z, hx, hz) => {
    // canal strip stays free of towers (it continues out of the dressed area to the horizon)
    if (x + hx > canal.x0 - 14 && x - hx < canal.x1 + 14) return true;
    for (const r of reserved) if (x + hx > r.x0 && x - hx < r.x1 && z + hz > r.z0 && z - hz < r.z1) return true;
    return false;
  };
  const visit = (level, cx, cz) => {
    const L = LEVELS[level], half = L.cell / 2;
    const cd = field.dist(cx, cz);
    if (level > 0 && cd < L.minC) {   // too close for this scale: split into four
      const q = L.cell / 4;
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) visit(level - 1, cx + sx * q, cz + sz * q);
      return;
    }
    if (level === 0 && cd < L.minC) return;   // reserved for W
    emit(level, cx, cz, cd);
  };
  const emit = (level, cx, cz, cd) => {
    const L = LEVELS[level];
    // far cells are split into several lots so the silhouette is jagged instead of a few giant slabs
    const k = [1, 1, 2, 3][level], cell = L.cell / k;
    for (let a = 0; a < k; a++) for (let b = 0; b < k; b++) {
      emitLot(level, cell, cx - L.cell / 2 + (a + 0.5) * cell, cz - L.cell / 2 + (b + 0.5) * cell);
    }
  };
  const emitLot = (level, cell, cx, cz) => {
    const ix = Math.round((cx - cell / 2) / cell), iz = Math.round((cz - cell / 2) / cell);
    const r = mulberry32(hash2(ix, iz, 100 + level) * 4294967296 | 0);
    const dh = districtHeight(cx, cz);
    // height by level (taller further out so the horizon is always filled), modulated by the district
    const base = [55, 110, 190, 270][level], span = [160, 300, 430, 540][level];
    let h = base * (0.5 + 0.7 * dh) + span * dh * Math.pow(r(), 1.6);
    if (r() < [0.14, 0.10, 0.05, 0.02][level]) h = 14 + r() * 36;                   // low-rise / plaza
    if (r() < 0.03 * (0.5 + dh)) h *= 1.5;                                             // occasional supertall
    h = clamp(h, 14, 900);
    const fw = lerp(0.46, 0.88, r()), fd = lerp(0.46, 0.88, r());
    let w = cell * fw, d = cell * fd;
    const mod = [3.2, 5, 8, 14][level] * (level >= 2 ? 0.7 : 1);
    w = Math.max(mod * 4, Math.round(w / mod) * mod); d = Math.max(mod * 4, Math.round(d / mod) * mod);
    const jx = (cell - w) * 0.5 * (r() * 2 - 1) * 0.9, jz = (cell - d) * 0.5 * (r() * 2 - 1) * 0.9;
    const x = cx + jx, z = cz + jz;
    if (skip(x, z, w / 2 + (level ? 0 : 6), d / 2 + (level ? 0 : 6))) return;
    // level-A towers must stay clear of W's band: check footprint corners
    if (level <= 1) {
      for (const [ox, oz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) if (field.dist(x + ox * w / 2, z + oz * d / 2) < 160) return;
    }
    lots.push({ x, z, w, d, h, level, cell, seed: (r() * 4294967296) >>> 0, dh, theme: districtTheme(cx, cz) });
  };
  for (let a = -nD; a < nD; a++) for (let b = -nD; b < nD; b++) visit(3, a * D + D / 2, b * D + D / 2);
  return lots;
}
