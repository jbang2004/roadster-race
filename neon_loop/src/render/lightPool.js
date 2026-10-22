// Light pool: turns the strongest registered static lights near the focus (and near every known car) into a FIXED set of
// real PointLights/SpotLights on layer CARS only. The set is created once (adding or removing lights recompiles every
// shader); unused slots are parked at intensity 0. Selection has hysteresis and every slot fades in/out, so nothing pops.
// Owner: R.  See CONTRACTS.md §Lighting model.
import * as THREE from 'three';
import { LAYER } from '../core/layers.js';
import { lights } from '../core/lights.js';

const CELL = 24;
const REACH = 2;                     // cells searched around an interest point (≥ 48 m)
const FADE_IN = 0.22, FADE_OUT = 0.35;
const MIN_INTENSITY = 6;             // candela: weaker registrations (windows, sign glow) are not worth a real light
const _a = new THREE.Vector3();

export class LightPool {
  constructor(scene, { points = 16, spots = 8 } = {}) {
    this.root = new THREE.Group();
    this.root.name = 'lightPool';
    this.slots = [];
    const mk = (L, isSpot) => {
      L.layers.set(LAYER.CARS);
      L.intensity = 0; L.decay = 2; L.castShadow = false;
      L.position.set(0, -1000, 0);
      this.root.add(L);
      if (isSpot) { L.target.layers.set(LAYER.CARS); this.root.add(L.target); }
      this.slots.push({ light: L, spot: isSpot, rec: null, fade: 0, base: 0, want: false });
    };
    for (let i = 0; i < points; i++) mk(new THREE.PointLight(0xffffff, 0, 30, 2), false);
    for (let i = 0; i < spots; i++) mk(new THREE.SpotLight(0xffffff, 0, 30, Math.PI / 3, 0.5, 2), true);
    scene.add(this.root);
    this.nPoints = points; this.nSpots = spots;
    this.grid = new Map(); this._indexed = -1;
    this._cands = []; this._seen = new Set();
    this.active = 0;
    this.t = 0;
  }

  _index() {
    const L = lights.list;
    if (L.length === this._indexed) return;
    this.grid.clear();
    for (const l of L) {
      if (l.intensity < MIN_INTENSITY) continue;
      const k = (Math.floor(l.pos.x / CELL) * 73856093) ^ (Math.floor(l.pos.z / CELL) * 19349663);
      let c = this.grid.get(k); if (!c) this.grid.set(k, c = []); c.push(l);
    }
    this._indexed = L.length;
  }

  /** interest: [{ pos: Vector3, w }] — focus first. */
  update(dt, interest, n = interest.length) {
    this._index();
    this.t += dt;
    const cands = this._cands; cands.length = 0;
    const seen = this._seen; seen.clear();
    for (let ii = 0; ii < n; ii++) {
      const it = interest[ii];
      const cx = Math.floor(it.pos.x / CELL), cz = Math.floor(it.pos.z / CELL);
      for (let a = -REACH; a <= REACH; a++) for (let b = -REACH; b <= REACH; b++) {
        const c = this.grid.get(((cx + a) * 73856093) ^ ((cz + b) * 19349663));
        if (!c) continue;
        for (const l of c) {
          const d2 = l.pos.distanceToSquared(it.pos);
          const R = l.range > 0 ? l.range + 3 : 60;
          if (d2 > R * R) continue;
          // contribution estimate: inverse square with the same smooth range window three.js applies
          let win = 1; if (l.range > 0) { const q = d2 / (l.range * l.range); win = Math.max(0, 1 - q * q); win *= win; }
          const sc = it.w * l.intensity * win / (d2 + 4);
          if (sc <= 0) continue;
          if (seen.has(l.id)) { for (const e of cands) if (e.rec === l) { if (sc > e.sc) e.sc = sc; break; } continue; }
          seen.add(l.id);
          cands.push({ rec: l, sc });
        }
      }
    }
    cands.sort((x, y) => y.sc - x.sc);

    // rank lookup for hysteresis
    const capP = this.nPoints, capS = this.nSpots, cap = capP + capS;
    const rank = new Map();
    for (let i = 0; i < cands.length; i++) rank.set(cands[i].rec, i);
    const marginRank = cap + 6;
    const scoreCut = cands.length >= cap ? cands[cap - 1].sc * 0.55 : 0;

    // 1. current slots: keep while still ranked well enough
    const held = new Set();
    for (const s of this.slots) {
      s.want = false;
      if (!s.rec) continue;
      const r = rank.get(s.rec);
      if (r !== undefined && (r < marginRank || cands[r].sc > scoreCut)) { s.want = true; held.add(s.rec); }
    }
    // 2. assign free slots to the best new candidates (spot lights prefer spot slots, overflow uses point slots)
    for (let i = 0; i < cands.length && i < cap + 2; i++) {
      const rec = cands[i].rec;
      if (held.has(rec)) continue;
      const wantSpot = !!rec.dir;
      let slot = null;
      if (wantSpot) slot = this.slots.find(s => s.spot && !s.rec);
      if (!slot) slot = this.slots.find(s => !s.spot && !s.rec);
      if (!slot) continue;
      slot.rec = rec; slot.fade = 0; slot.want = true; held.add(rec);
      this._configure(slot);
    }
    // 3. fade + write
    let active = 0;
    for (const s of this.slots) {
      const L = s.light;
      if (!s.rec) { L.intensity = 0; continue; }
      const target = s.want ? 1 : 0;
      const rate = target > s.fade ? 1 / FADE_IN : 1 / FADE_OUT;
      s.fade = target > s.fade ? Math.min(1, s.fade + dt * rate) : Math.max(0, s.fade - dt * rate);
      if (!s.want && s.fade <= 0) { s.rec = null; L.intensity = 0; L.position.set(0, -1000, 0); continue; }
      const f = s.fade * s.fade * (3 - 2 * s.fade);
      let k = 1;
      const fl = s.rec.flicker;
      if (fl > 0) k = 1 - fl * (0.5 + 0.5 * Math.sin(this.t * 37.0 + s.rec.id * 12.9898) * Math.sin(this.t * 11.3 + s.rec.id * 4.1));
      L.intensity = s.rec.intensity * f * k;
      active++;
    }
    this.active = active;
  }

  _configure(s) {
    const r = s.rec, L = s.light;
    L.position.copy(r.pos);
    L.color.copy(r.color);
    L.distance = r.range || 0;
    if (s.spot) {
      if (r.dir) {
        L.angle = Math.min(r.angle, Math.PI / 2 - 0.01); L.penumbra = r.penumbra;
        L.target.position.copy(r.pos).add(r.dir);
      } else {
        // a point-type light that overflowed into a spot slot is never chosen (see update): spots only take spots
        L.angle = Math.PI / 2 - 0.01; L.penumbra = 1; L.target.position.copy(r.pos).add(_a.set(0, -1, 0));
      }
    }
  }

  /** Hide/show every pool light (used for the road-reflection car pass, which does not need them: a second, cheaper
   *  shader variant that is compiled once and then only switched). */
  setVisible(v) { for (const s of this.slots) s.light.visible = v; }

  dispose() { this.root.removeFromParent(); for (const s of this.slots) s.light.dispose?.(); }
}
