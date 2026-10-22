// Static light registry. World / skyline register every light they place (street lamps, neon fill,
// tunnel strips, sign glow). Nothing here is rendered: the render area's light pool turns the nearest
// ones into real three.js lights each frame, and the road bakes use the full list.
// Units: three.js physical lights, intensity in candela, decay 2. See docs/BIBLE.md §Light scale.
import * as THREE from 'three';

const CELL = 32;
const grid = new Map();
const key = (x, z) => (Math.floor(x / CELL) * 73856093) ^ (Math.floor(z / CELL) * 19349663);

export const lights = {
  list: [],
  /**
   * o: { pos: Vector3|[x,y,z], color: Color|hex|[r,g,b], intensity (cd), range (m, 0 = infinite),
   *      kind: 'street'|'neon'|'sign'|'tunnel'|'window'|'other', dir?: Vector3 (spot axis), angle?, penumbra?,
   *      flicker?: 0..1 }
   * Returns the record (has .id).
   */
  add(o) {
    const pos = o.pos.isVector3 ? o.pos.clone() : new THREE.Vector3(...o.pos);
    const color = o.color instanceof THREE.Color ? o.color.clone() : Array.isArray(o.color) ? new THREE.Color(...o.color) : new THREE.Color(o.color ?? 0xffffff);
    const rec = { id: this.list.length, pos, color, intensity: o.intensity ?? 100, range: o.range ?? 30, kind: o.kind ?? 'other',
      dir: o.dir ? (o.dir.isVector3 ? o.dir.clone() : new THREE.Vector3(...o.dir)).normalize() : null,
      angle: o.angle ?? Math.PI / 3, penumbra: o.penumbra ?? 0.5, flicker: o.flicker ?? 0 };
    this.list.push(rec);
    const k = key(pos.x, pos.z); let c = grid.get(k); if (!c) grid.set(k, c = []); c.push(rec);
    return rec;
  },
  /** The n lights with the largest (intensity / distance²) at `p`, optionally filtered. */
  nearest(p, n = 8, filter = null, radius = 120) {
    const out = [];
    const r = Math.ceil(radius / CELL);
    const cx = Math.floor(p.x / CELL), cz = Math.floor(p.z / CELL);
    for (let a = -r; a <= r; a++) for (let b = -r; b <= r; b++) {
      const c = grid.get(((cx + a) * 73856093) ^ ((cz + b) * 19349663)); if (!c) continue;
      for (const l of c) {
        if (filter && !filter(l)) continue;
        const d2 = l.pos.distanceToSquared(p);
        if (l.range && d2 > (l.range * 1.5) ** 2) continue;
        out.push([l.intensity / Math.max(d2, 1), l]);
      }
    }
    out.sort((x, y) => y[0] - x[0]);
    return out.slice(0, n).map(e => e[1]);
  },
  clear() { this.list.length = 0; grid.clear(); },
};
