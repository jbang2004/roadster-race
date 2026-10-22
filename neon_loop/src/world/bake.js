// Static light bake: evaluates every registered light (src/core/lights.js) at each vertex of the world meshes
// (three.js physical falloff: I·cosθ / d² × (1 − (d/range)⁴)², spot cones) and stores the irradiance in the `aLit` attribute.
// Lights carry a `lvl` (0 street, 1 expressway deck, 2 tunnel) so lamps never light across the deck or through the ground.
import * as THREE from 'three';

const CELL = 48;
const ck = (a, b) => (a * 73856093) ^ (b * 19349663);

export class LightGrid {
  constructor(list) {
    this.map = new Map();
    this.lights = [];
    for (const l of list) {
      const range = l.range && l.range > 0 ? l.range : 60;
      const d = {
        x: l.pos.x, y: l.pos.y, z: l.pos.z, r: l.color.r * l.intensity, g: l.color.g * l.intensity, b: l.color.b * l.intensity,
        range, lvl: l.lvl ?? 0, spot: !!l.dir, dx: l.dir ? l.dir.x : 0, dy: l.dir ? l.dir.y : 0, dz: l.dir ? l.dir.z : 0,
        cosO: Math.cos(l.angle ?? 1), cosI: Math.cos((l.angle ?? 1) * (1 - (l.penumbra ?? 0.5))), rec: l,
      };
      this.lights.push(d);
      const x0 = Math.floor((d.x - range) / CELL), x1 = Math.floor((d.x + range) / CELL);
      const z0 = Math.floor((d.z - range) / CELL), z1 = Math.floor((d.z + range) / CELL);
      for (let a = x0; a <= x1; a++) for (let b = z0; b <= z1; b++) {
        const k = ck(a, b); let c = this.map.get(k); if (!c) this.map.set(k, c = []); c.push(d);
      }
    }
  }
  cell(x, z) { return this.map.get(ck(Math.floor(x / CELL), Math.floor(z / CELL))); }
}

/** Returns Float32Array(n*3) of irradiance (E, same units as I/d²). */
export function bakeGeo(geo, grid, opts = {}) {
  const n = geo.n, out = new Float32Array(n * 3), pos = geo.pos, nor = geo.nor, lvl = geo.lvl;
  const k = opts.gain ?? 1, omni = geo.key === 'steam';
  for (let v = 0; v < n; v++) {
    const x = pos[v * 3], y = pos[v * 3 + 1], z = pos[v * 3 + 2], nx = nor[v * 3], ny = nor[v * 3 + 1], nz = nor[v * 3 + 2], vl = lvl[v];
    const c = grid.cell(x, z); if (!c) continue;
    let R = 0, G = 0, B = 0;
    for (let j = 0; j < c.length; j++) {
      const L = c[j];
      if (L.lvl !== vl && !(L.lvl === 1 && vl === 0 && y > 8)) continue;
      const dx = L.x - x, dy = L.y - y, dz = L.z - z;
      let d2 = dx * dx + dy * dy + dz * dz;
      const rr = L.range * L.range; if (d2 >= rr) continue;
      if (d2 < 16) d2 = 16;
      const d = Math.sqrt(d2), inv = 1 / d;
      let ndl = omni ? 1 : (nx * dx + ny * dy + nz * dz) * inv; if (ndl <= 0) continue;
      let f = ndl / d2; const q = d2 / rr; f *= (1 - q * q) * (1 - q * q);
      if (L.spot) {
        const ca = -(L.dx * dx + L.dy * dy + L.dz * dz) * inv;
        if (ca <= L.cosO) continue;
        const t = Math.min(1, (ca - L.cosO) / Math.max(L.cosI - L.cosO, 1e-4)); f *= t * t * (3 - 2 * t);
      }
      R += L.r * f; G += L.g * f; B += L.b * f;
    }
    out[v * 3] = R * k; out[v * 3 + 1] = G * k; out[v * 3 + 2] = B * k;
  }
  return out;
}

export function litAttribute(arr) { return new THREE.BufferAttribute(arr, 3); }
