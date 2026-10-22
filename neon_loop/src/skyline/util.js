// Small shared helpers for the skyline area: seeded RNG, tileable noise texture, distance field.
import * as THREE from 'three';

export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/** Integer hash of two ints + seed → [0,1). */
export function hash2(x, z, seed = 0) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(z | 0, 668265263) + Math.imul(seed | 0, 2147483647)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177); h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smoothstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

// ---------- tileable noise ----------
function fbmTile(size, baseCells, octaves, gain, rng, ridged = false) {
  const out = new Float32Array(size * size);
  let amp = 1;
  for (let o = 0; o < octaves; o++) {
    const cells = baseCells << o;
    const lat = new Float32Array(cells * cells);
    for (let i = 0; i < lat.length; i++) lat[i] = rng();
    const inv = cells / size;
    const xs0 = new Int32Array(size), xs1 = new Int32Array(size), sxs = new Float32Array(size);
    for (let x = 0; x < size; x++) {
      const fx = x * inv, x0 = fx | 0, t = fx - x0;
      xs0[x] = x0 % cells; xs1[x] = (x0 + 1) % cells; sxs[x] = t * t * t * (t * (t * 6 - 15) + 10);
    }
    for (let y = 0; y < size; y++) {
      const fy = y * inv, y0 = fy | 0, ty = fy - y0, sy = ty * ty * ty * (ty * (ty * 6 - 15) + 10);
      const r0 = (y0 % cells) * cells, r1 = ((y0 + 1) % cells) * cells;
      const row = y * size;
      for (let x = 0; x < size; x++) {
        const sx = sxs[x];
        const a = lat[r0 + xs0[x]], b = lat[r0 + xs1[x]], c = lat[r1 + xs0[x]], d = lat[r1 + xs1[x]];
        const v = (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy;
        out[row + x] += amp * (ridged ? 1 - Math.abs(2 * v - 1) : v);
      }
    }
    amp *= gain;
  }
  // normalise to 0..1 (2nd..98th percentile stretch)
  const sorted = Float32Array.from(out).sort();
  const lo = sorted[(sorted.length * 0.02) | 0], hi = sorted[(sorted.length * 0.98) | 0];
  const k = 1 / Math.max(hi - lo, 1e-6);
  for (let i = 0; i < out.length; i++) out[i] = clamp((out[i] - lo) * k, 0, 1);
  return out;
}

/** 4-channel tileable noise: R large fbm, G mid fbm, B ridged/billow, A fine fbm. RGBA8, repeat, mipmapped. */
export function makeNoiseTexture(size = 512, seed = 7) {
  const rng = mulberry32(seed);
  const r = fbmTile(size, 4, 6, 0.52, rng), g = fbmTile(size, 8, 5, 0.5, rng),
    b = fbmTile(size, 6, 5, 0.5, rng, true), a = fbmTile(size, 32, 3, 0.5, rng);
  const data = new Uint8Array(size * size * 4);
  for (let i = 0; i < size * size; i++) {
    data[i * 4] = r[i] * 255; data[i * 4 + 1] = g[i] * 255; data[i * 4 + 2] = b[i] * 255; data[i * 4 + 3] = a[i] * 255;
  }
  const tex = new THREE.DataTexture(data, size, size, THREE.RGBAFormat, THREE.UnsignedByteType);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.magFilter = THREE.LinearFilter; tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.generateMipmaps = true; tex.anisotropy = 4;
  tex.colorSpace = THREE.NoColorSpace; tex.needsUpdate = true;
  return tex;
}

// ---------- Euclidean distance transform on a grid (Felzenszwalb & Huttenlocher) ----------
function edt1d(f, n, d, v, z) {
  let k = 0; v[0] = 0; z[0] = -1e20; z[1] = 1e20;
  for (let q = 1; q < n; q++) {
    let s;
    while (true) {
      const p = v[k];
      s = ((f[q] + q * q) - (f[p] + p * p)) / (2 * q - 2 * p);
      if (s <= z[k]) k--; else break;
      if (k < 0) { k = 0; break; }
    }
    k++; v[k] = q; z[k] = s; z[k + 1] = 1e20;
  }
  k = 0;
  for (let q = 0; q < n; q++) {
    while (z[k + 1] < q) k++;
    const p = v[k]; d[q] = (q - p) * (q - p) + f[p];
  }
}
/** seeds: Uint8Array(w*h) with 1 = seed cell. Returns Float32Array of distance in cells. */
export function distanceField(seeds, w, h) {
  const INF = 1e12, g = new Float32Array(w * h);
  for (let i = 0; i < g.length; i++) g[i] = seeds[i] ? 0 : INF;
  const n = Math.max(w, h), f = new Float32Array(n), d = new Float32Array(n), v = new Int32Array(n), z = new Float32Array(n + 1);
  for (let x = 0; x < w; x++) {
    for (let y = 0; y < h; y++) f[y] = g[y * w + x];
    edt1d(f, h, d, v, z);
    for (let y = 0; y < h; y++) g[y * w + x] = d[y];
  }
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) f[x] = g[y * w + x];
    edt1d(f, w, d, v, z);
    for (let x = 0; x < w; x++) g[y * w + x] = Math.sqrt(d[x]);
  }
  return g;
}
