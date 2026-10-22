// Car light pool. A forward renderer pays for every real light in every lit fragment of the world and car passes, so the
// cars do NOT each own a SpotLight: a small fixed pool of headlight spots + brake/reverse fill points is shared and
// handed to the cars nearest to the camera (the player first). The pool size is constant, so shaders never recompile;
// slots are handed over through a short fade so nothing pops. Every car (near or far) still writes its slot of
// G.uHead* so W's road shader lights correctly for all of them.
import * as THREE from 'three';
import { LAYER } from '../core/layers.js';
import { G, MAX_HEADLIGHTS } from '../core/globals.js';

const pools = new WeakMap();
export const HEAD_CD = 6000;             // BIBLE §3: low beam, spot 6000 cd, 25° cone, range 80 m
// A real low beam puts its peak just under the horizon and only a few % into the road 2–5 m ahead, so the near road is
// barely brighter than the road at 20 m. A three.js spot is flat across its cone, and with inverse-square falloff the
// patch in front of the bumper came out ~40× brighter than the road at 20 m (a white blob). Linear falloff (decay 1),
// a level axis and a 17° cone with a wide penumbra (full only within ~5°) approximate the low-beam pattern: the road
// under the bumper stays dark, the patch 3–6 m ahead is soft, and walls / cars 20 m ahead still get ~7 lux.
// W's road shader (HEADLIGHTS_FRAG) uses the same law and cone for the far cars.
export const HEAD_WORLD_CD = HEAD_CD * 0.025;
export const HEAD_COLOR = new THREE.Color(1.0, 0.955, 0.9);
const FILL_CD = 6;                       // brake fill (car pass only, decorative red spill on the diffuser)
// The world-pass spots follow BIBLE §3 (inverse square, 6000 cd): right for the road, barriers and signs. On the OTHER CARS
// that falloff is brutal (a car 4 m behind turns your tail into a white block), so the car pass gets its own, softer spots:
// decay 1 and a few tens of candela keep the follower's lights readable on your bodywork at any distance.
export const CAR_SPOT_CD = 12;

export function getLightPool(app) {
  let p = pools.get(app);
  if (!p) { p = new LightPool(app); pools.set(app, p); }
  return p;
}

class LightPool {
  constructor(app) {
    this.app = app;
    const q = app.quality;
    this.nSpots = q === 'low' ? 2 : q === 'medium' ? 3 : 4;        // world passes (road side furniture, walls, signs)
    this.nCarSpots = q === 'low' ? 1 : 2;                           // car pass only
    this.nFills = q === 'low' ? 0 : q === 'medium' ? 1 : 2;         // car pass only
    this.group = new THREE.Group(); this.group.name = 'CarLightPool';
    app.scene.add(this.group);
    this.spots = []; this.fills = [];
    for (let i = 0; i < this.nSpots; i++) {
      const l = new THREE.SpotLight(HEAD_COLOR, 0, 100, 0.30, 0.7, 1);    // cone matches HEADLIGHTS_FRAG; decay 1 (see HEAD_WORLD_CD)
      l.castShadow = false; l.layers.set(LAYER.DEFAULT); l.layers.enable(LAYER.MAIN_ONLY);     // world + reflection passes
      this.group.add(l, l.target);
      this.spots.push({ light: l, owner: null, gain: 0 });
    }
    this.cspots = [];
    for (let i = 0; i < this.nCarSpots; i++) {
      const l = new THREE.SpotLight(HEAD_COLOR, 0, 100, 0.35, 0.45, 1.0);
      l.castShadow = false; l.layers.set(LAYER.CARS);
      this.group.add(l, l.target);
      this.cspots.push({ light: l, owner: null, gain: 0 });
    }
    for (let i = 0; i < this.nFills; i++) {
      const l = new THREE.PointLight(0xff1810, 0, 14, 2);
      l.castShadow = false; l.layers.set(LAYER.CARS);     // fills only matter on the cars (R's light pool lights the world)
      this.group.add(l);
      this.fills.push({ light: l, owner: null, gain: 0 });
    }
    this.visuals = [];                       // registration order = G.uHead* slot
    this.frame = -1;
    this._tmp = new THREE.Vector3();
  }

  register(vis) {
    let i = this.visuals.indexOf(null);
    if (i < 0) i = this.visuals.length;
    if (i >= MAX_HEADLIGHTS) { vis.headSlot = -1; return; }
    this.visuals[i] = vis; vis.headSlot = i;
  }

  unregister(vis) {
    if (vis.headSlot >= 0) this.visuals[vis.headSlot] = null;
    for (const s of this.spots) if (s.owner === vis) { s.owner = null; s.gain = 0; s.light.intensity = 0; }
    for (const s of this.cspots) if (s.owner === vis) { s.owner = null; s.gain = 0; s.light.intensity = 0; }
    for (const s of this.fills) if (s.owner === vis) { s.owner = null; s.gain = 0; s.light.intensity = 0; }
    let n = 0;
    this.visuals.forEach((v, i) => { if (v) n = i + 1; });
    G.uHeadCount.value = n;
    if (vis.headSlot >= 0) G.uHeadColor.value[vis.headSlot].set(0, 0, 0);
  }

  /** once per frame (first sync call): re-rank the cars by distance to the camera and hand out / take back slots. */
  begin(dt) {
    const frame = this.app.time.frame;
    if (frame === this.frame) return;
    this.frame = frame;
    const live = this.visuals.filter(v => v && v.object.visible && v._wantLights);
    live.sort((a, b) => a._rank - b._rank);
    this._assign(this.spots, live.slice(0, this.nSpots), dt);
    this._assign(this.cspots, live.slice(0, this.nCarSpots), dt);
    this._assign(this.fills, live.slice(0, this.nFills), dt);
  }

  _assign(slots, wanted, dt) {
    const want = new Set(wanted);
    for (const s of slots) {                  // release the ones that fell out of the ranking (fade first)
      if (s.owner && !want.has(s.owner)) { s.gain = Math.max(0, s.gain - dt * 5); if (s.gain === 0) s.owner = null; }
    }
    const owned = new Set(slots.map(s => s.owner));
    for (const v of wanted) {
      if (owned.has(v)) continue;
      const free = slots.find(s => !s.owner);
      if (free) { free.owner = v; free.gain = 0; owned.add(v); }
    }
    for (const s of slots) {
      if (s.owner && want.has(s.owner)) s.gain = Math.min(1, s.gain + dt * 4);
      if (!s.owner) s.light.intensity = 0;
    }
  }

  /** the owner writes its light transforms / intensities while syncing */
  apply(vis, st, withLights = true) {
    if (withLights) for (const s of this.spots) if (s.owner === vis) {
      const l = s.light;
      l.position.copy(st.nose);
      l.target.position.copy(st.nose).addScaledVector(st.dir, 20);
      l.intensity = HEAD_WORLD_CD * st.head * s.gain * this.qScale;
    }
    if (withLights) for (const s of this.cspots) if (s.owner === vis) {
      const l = s.light;
      l.position.copy(st.nose);
      l.target.position.copy(st.nose).addScaledVector(st.dir, 20);
      l.intensity = CAR_SPOT_CD * st.head * s.gain;
    }
    if (withLights) for (const s of this.fills) if (s.owner === vis) {
      const l = s.light;
      l.position.copy(st.tail);
      const b = st.brake, r = st.reverse;
      l.color.setRGB(1.0, 0.07 + r * 0.8, 0.05 + r * 0.8);
      l.intensity = (FILL_CD * b + 0.35 * st.head + 6 * r) * s.gain;
    }
    // road shader data (all cars)
    if (vis.headSlot >= 0) {
      const i = vis.headSlot;
      G.uHeadPos.value[i].copy(st.nose);
      G.uHeadDir.value[i].copy(st.dir);
      const k = HEAD_CD * st.head * st.roadFade;
      G.uHeadColor.value[i].set(HEAD_COLOR.r * k, HEAD_COLOR.g * k, HEAD_COLOR.b * k);
      let n = 0;
      this.visuals.forEach((v, j) => { if (v) n = j + 1; });
      G.uHeadCount.value = n;
    }
  }
  get qScale() { return this.app.quality === 'low' ? 0.9 : 1; }
}
