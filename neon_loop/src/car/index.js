// Car visuals (owner C).  CONTRACTS.md §Area entry points, C:
//   await loadCarAssets(app)
//   const visual = createCarVisual(app, { livery, isPlayer, envMap })
//   visual.object  (Object3D on layer CARS; the caller adds it to the scene), visual.sync(car, dt), visual.setEnvMap(tex), visual.dispose()
//   LIVERIES (8 entries, index 0 = the player's liquid silver with copper rims)
//
// Assets (tools/blender/build_game_car.py → public/assets/car): car_hi.glb (player + near cars), car_lod1.glb (≤ 60 k tris),
// car_lod2.glb (≤ 15 k tris), car_meta.json.  GLB frame: −X forward / +Z left; the visual wraps it so the car is −Z forward.
// LODs switch by camera distance with a dithered cross-fade (screen-door, no popping).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { LAYER, setLayer } from '../core/layers.js';
import { G } from '../core/globals.js';
import { url } from '../core/assets.js';
import { LIVERIES, liveryAtlas } from './liveries.js';
import { createMaterialSet, createBlurDiscMaterial } from './materials.js';
import { getLightPool } from './lightpool.js';
import { createJets } from './jets.js';

export { LIVERIES };

let ASSETS = null;
let loading = null;

/** Loads the three LOD GLBs and the meta file (once). Call before createCarVisual. */
export function loadCarAssets(app) {
  if (ASSETS) return Promise.resolve(ASSETS);
  if (loading) return loading;
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const base = 'assets/car/';
  // meshopt-compressed GLBs need WebAssembly; where a host's CSP blocks it, fall back to the uncompressed exports
  const ext = app?.q?.has('rawcar') ? Promise.resolve('.raw.glb') : MeshoptDecoder.ready.then(() => '.glb', () => '.raw.glb');
  // hosts that refuse .glb get the same bytes under an extra served extension (VITE_BIN_EXT, see tools/prep-publish.mjs)
  loading = ext.then(e => e + (import.meta.env.VITE_BIN_EXT ?? '')).then(e => Promise.all([
    loader.loadAsync(url(base + 'car_hi' + e)),
    loader.loadAsync(url(base + 'car_lod1' + e)),
    loader.loadAsync(url(base + 'car_lod2' + e)),
    fetch(url(base + 'car_meta.json')).then(r => r.json()),
  ])).then(([hi, l1, l2, meta]) => {
    ASSETS = { protos: [hi.scene, l1.scene, l2.scene], meta, blurGeo: null };
    return ASSETS;
  });
  return loading;
}

const WHEELS = ['FL', 'FR', 'RL', 'RR'];

// Contact shadow: a soft dark footprint on the road (no shadow maps in this renderer), denser under the tyres so the car
// sits on the ground. Car frame: −Z forward, hubs at x ±0.885, z −1.487 / 1.61. Rendered in the main world pass only.
let SHADOW = null;
function contactShadow() {
  if (!SHADOW) {
    const geo = new THREE.PlaneGeometry(2.6, 5.4); geo.rotateX(-Math.PI / 2);
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
      vertexShader: /* glsl */`varying vec2 vP; void main() { vP = position.xz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: /* glsl */`
        varying vec2 vP;
        float rbox(vec2 p, vec2 b, float r) { vec2 q = abs(p) - b + r; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r; }
        void main() {
          vec2 p = vP - vec2(0.0, 0.06);
          float body = 1.0 - smoothstep(-0.30, 0.32, rbox(p, vec2(0.98, 2.32), 0.5));
          float core = 1.0 - smoothstep(-0.40, 0.05, rbox(p, vec2(0.78, 2.00), 0.4));
          float tyres = 0.0;
          for (int i = 0; i < 4; i++) {
            vec2 c = vec2(i == 0 || i == 2 ? -0.885 : 0.885, i < 2 ? -1.487 : 1.61);
            vec2 d = (vP - c) / vec2(0.19, 0.40);
            tyres = max(tyres, exp(-dot(d, d) * 1.4));
          }
          gl_FragColor = vec4(0.0, 0.0, 0.0, clamp(body * 0.42 + core * 0.33 + tyres * 0.4, 0.0, 0.9));
        }`,
    });
    SHADOW = { geo, mat };
  }
  const m = new THREE.Mesh(SHADOW.geo, SHADOW.mat);
  m.name = 'ContactShadow'; m.position.y = 0.045; m.renderOrder = -1; m.frustumCulled = true;
  m.layers.set(LAYER.MAIN_ONLY);
  return m;
}
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const DEG = Math.PI / 180;
// LOD switch distances (m, at 62° fov); hysteresis is applied on top
const LOD_D = { high: [28, 95], medium: [22, 80], low: [16, 60] };

/**
 * @param {object} app
 * @param {{livery?: number, isPlayer?: boolean, envMap?: THREE.Texture|null, forceLod?: number}} opts
 */
export function createCarVisual(app, { livery = 0, isPlayer = false, envMap = null, forceLod = -1, poolLights = true } = {}) {
  if (!ASSETS) throw new Error('createCarVisual: call await loadCarAssets(app) first');
  const L = LIVERIES[livery % LIVERIES.length];
  const quality = app.quality ?? 'high';

  const object = new THREE.Group(); object.name = 'CarVisual';
  const wrap = new THREE.Group(); wrap.name = 'GLBFrame'; wrap.rotation.y = -Math.PI / 2;     // GLB (−X fwd) → game (−Z fwd)
  object.add(wrap);

  // ---- shared uniform objects (all materials of this car point at these)
  const lodU = [0, 1, 2].map(() => ({ uLodT: { value: 1 }, uLodDir: { value: 0 } }));
  const carU = { uBead: { value: 0 }, uHeat: { value: 0 }, uWetK: { value: 0.5 }, uGlassAbs: { value: 0.6 }, uJet: { value: 0 } };
  const P = L.paint;
  const paintU = {
    uFlake: { value: P.flake }, uFlakeColor: { value: new THREE.Color(P.flakeColor) },
    uPearl: { value: P.pearl ? new THREE.Vector4(...P.pearl) : new THREE.Vector4(0, 0, 0, 0) },
    uPeel: { value: P.roughness < 0.1 ? 0.0012 : 0.002 }, uAccent: { value: new THREE.Color(L.rim.accent) },
    uPaintC: { value: new THREE.Color(P.color) },       // rim aero panels follow the body colour
  };
  const atlas = liveryAtlas(livery, ASSETS.meta, 8, quality === 'low' ? 0.5 : 1);

  const lods = [];
  const allMats = [];
  for (let lod = 0; lod < 3; lod++) {
    const shared = { lod: lodU[lod], car: carU, paint: paintU };
    const set = createMaterialSet(L, lod, shared, { env: envMap, atlas });
    const root = ASSETS.protos[lod].clone(true);
    root.name = 'LOD' + lod;
    const rec = { root, mats: set.mats, lamps: set.lamps, wheels: [], steering: null, steerQ0: null, blurs: [], wing: root.getObjectByName('Wing') };
    if (rec.wing) {
      // new meta.wing format (wing.deploy): the node is built STOWED = a copy of the shell's deck faces; the game hides it while stowed and shows it (plus the black
      // 'WingWell' recess on the same footprint) from the first frame of the deploy.  Old format (wing.stow only): deployed as built, folded into the deck.
      rec.wingP0 = rec.wing.position.clone();
      rec.wingY0 = rec.wing.position.y;
      rec.plates = rec.wing.getObjectByName(ASSETS.meta.wing?.plates?.node ?? 'WingPlates') ?? null;
      rec.well = ASSETS.meta.wing?.deploy ? root.getObjectByName(ASSETS.meta.wing?.well ?? 'WingWell') ?? null : null;
      if (ASSETS.meta.wing?.deploy) { rec.wing.visible = false; if (rec.well) rec.well.visible = false; }
      // wing.ends (the one-piece wing): per side a tip blade that slides out from under the panel's side edge, carrying the endplate (the rear-corner facet), which swings
      // out at the bottom about its top edge (axis in the wing's frame, origin on the hinge)
      rec.ends = (ASSETS.meta.wing?.ends?.parts ?? []).map(e => {
        const t = rec.wing.getObjectByName(e.tip), p = rec.wing.getObjectByName(e.end);
        return t && p ? { t, p, t0: t.position.clone(), q0: p.quaternion.clone(), out: new THREE.Vector3(...e.out), ax: new THREE.Vector3(...e.axis).normalize(), a: e.angle } : null;
      }).filter(Boolean);
    }
    root.traverse(o => {
      if (!o.isMesh) return;
      const nm = o.material.name;
      const m = set.mats[nm];
      if (!m) { console.warn('[car] no material for', nm); return; }
      o.material = m;
      o.frustumCulled = lod === 0 ? true : true;
      o.castShadow = false; o.receiveShadow = false;
    });
    for (const w of WHEELS) {
      const hub = root.getObjectByName('Wheel_' + w);
      const spin = root.getObjectByName('Spin_' + w);
      const wr = { hub, spin, baseY: hub ? hub.position.y : 0, left: w[1] === 'L' };
      const brake = root.getObjectByName('Brake_' + w);
      if (brake) brake.visible = lod === 0;       // seen through the open spokes; LOD1/2 have no brake node
      if (hub && lod < 2) {
        const bm = createBlurDiscMaterial({ lod: lodU[lod], car: carU, paint: paintU }, L.rim.accent);
        const disc = new THREE.Mesh(blurGeo(), bm);
        disc.name = 'Blur_' + w;
        disc.position.z = wr.left ? 0.1205 : -0.1205;
        if (!wr.left) disc.rotation.y = Math.PI;
        disc.renderOrder = 2; disc.frustumCulled = false;
        hub.add(disc);                              // child of the hub: it does not spin, the shader rotates the pattern
        wr.blur = bm; rec.blurs.push(bm);
      }
      rec.wheels.push(wr);
    }
    const st = root.getObjectByName('Steering');
    if (st) { rec.steering = st; rec.steerQ0 = st.quaternion.clone(); }
    const scr = set.mats.IntScreen; if (scr) { scr.emissive.set(0x1fb8ff); }
    allMats.push(...Object.values(set.mats));
    wrap.add(root);
    root.visible = false;
    lods.push(rec);
  }
  const jets = createJets();
  object.add(jets.mesh);
  setLayer(object, LAYER.CARS);
  object.add(contactShadow());     // world pass: darkens the road under the car (added after setLayer on purpose)

  // ---- LOD state
  const lodState = { cur: forceLod >= 0 ? forceLod : 0, prev: -1, t: 1, forced: forceLod };
  let lodInit = forceLod >= 0;
  const setLodVisible = () => {
    for (let i = 0; i < 3; i++) lods[i].root.visible = i === lodState.cur || i === lodState.prev;
  };
  setLodVisible();

  const pool = getLightPool(app);
  const visual = {
    object, livery, isPlayer, lods, get lod() { return lodState.cur; },
    _wantLights: true, _rank: 0, headSlot: -1,
    forceLod(i) { lodState.forced = i; if (i >= 0) { lodState.cur = i; lodState.prev = -1; lodState.t = 1; setLodVisible(); applyFade(); } },
    setEnvMap, sync, dispose, materials: allMats, uniforms: { car: carU, paint: paintU },
  };
  pool.register(visual);

  // temporaries
  const q = new THREE.Quaternion(), qa = new THREE.Quaternion(), qY = new THREE.Quaternion(), qE = new THREE.Quaternion();
  const v = new THREE.Vector3(), nose = new THREE.Vector3(), tail = new THREE.Vector3(), dir = new THREE.Vector3();
  const AX_Y = new THREE.Vector3(0, 1, 0);
  const lightState = { nose, tail, dir, head: 0, brake: 0, reverse: 0, roadFade: 1 };
  let headS = 0, brakeS = 0, revS = 0, heat = 0, wetS = 0, wingA = 0, wingS = 1, wingUp = false;
  const WS = ASSETS.meta.wing?.stow ?? { dy: 0, rotZ: 0, spanScale: 1 }, PS = ASSETS.meta.wing?.plates?.stow ?? {}, WD = ASSETS.meta.wing?.deploy ?? null;
  const EK = ASSETS.meta.wing?.ends?.k ?? [0.2, 0.9];

  function applyFade() {
    for (let i = 0; i < 3; i++) { lodU[i].uLodT.value = 1; lodU[i].uLodDir.value = 0; }
    if (lodState.prev >= 0) {
      lodU[lodState.cur].uLodT.value = lodState.t; lodU[lodState.cur].uLodDir.value = 0;
      lodU[lodState.prev].uLodT.value = lodState.t; lodU[lodState.prev].uLodDir.value = 1;
    }
  }

  function setEnvMap(tex) {
    for (const m of allMats) {
      if (!('envMap' in m)) continue;
      const had = !!m.envMap;
      m.envMap = tex ?? null;
      if (had !== !!tex) m.needsUpdate = true;
    }
    for (const rec of lods) for (const b of rec.blurs) { if (b.envMap !== (tex ?? null)) { b.envMap = tex ?? null; b.needsUpdate = true; } }
  }
  setEnvMap(envMap);

  function sync(car, dt = 0) {
    const cam = app.camera;
    // ---- pose (render pose, already interpolated by P)
    if (car.position) object.position.copy(car.position);
    if (car.quaternion) object.quaternion.copy(car.quaternion);
    object.updateMatrixWorld(true);

    // ---- LOD selection by camera distance (scaled by fov so zooming does not leave low LODs on screen)
    const dist = cam.position.distanceTo(object.position) * (cam.fov / 62);
    object.visible = dist < 1100;
    if (!object.visible) { visual._wantLights = false; return; }
    const th = LOD_D[quality] ?? LOD_D.high;
    visual._rank = dist - (isPlayer ? 1e4 : 0);
    visual._wantLights = dist < 160 || isPlayer;
    if (lodState.forced < 0) {
      const hy = lodState.cur === 0 ? 1.1 : lodState.cur === 1 ? 1.0 : 0.9;      // hysteresis
      let want = dist < th[0] * (lodState.cur === 0 ? 1.12 : 0.9) ? 0 : dist < th[1] * (lodState.cur === 2 ? 0.9 : 1.1) ? 1 : 2;
      if (isPlayer) want = Math.min(want, dist < 70 ? 0 : 1);
      if (!lodInit) { lodState.cur = want; lodInit = true; setLodVisible(); }
      else if (want !== lodState.cur && lodState.prev < 0) { lodState.prev = lodState.cur; lodState.cur = want; lodState.t = 0; setLodVisible(); }
    }
    if (lodState.prev >= 0) {
      lodState.t += (dt > 0 ? dt : 1 / 60) / 0.4;
      if (lodState.t >= 1) { lodState.prev = -1; lodState.t = 1; setLodVisible(); }
    }
    applyFade();

    // ---- environment-driven material state
    const speed = Math.abs(car.speed ?? 0);
    const wet = G.uWet.value, rain = G.uRain.value;
    carU.uBead.value = wet * clamp(0.12 + 0.75 * rain, 0, 1) * (1 - 0.85 * smooth(22, 70, speed)) * 0.9;
    carU.uWetK.value = wet * 0.8;
    const brkT = car.brakeTemp ?? 0;
    heat += (brkT - heat) * Math.min(1, (dt || 1 / 60) * 6);
    carU.uHeat.value = clamp(heat, 0, 1);

    // ---- lights
    const L_ = car.lights ?? { head: true, brake: 0, reverse: false };
    const k = Math.min(1, (dt || 1 / 60) * 14);
    headS += ((L_.head ? 1 : 0) - headS) * k;
    brakeS += ((L_.brake ?? 0) - brakeS) * Math.min(1, (dt || 1 / 60) * 22);
    revS += ((L_.reverse ? 1 : 0) - revS) * k;
    for (const rec of lods) {
      if (!rec.root.visible) continue;
      const la = rec.lamps;
      la.head.emissiveIntensity = 60 * headS;
      la.drl.emissiveIntensity = 48 * headS;
      la.tail.emissiveIntensity = (3.6 + 9 * brakeS) * headS + 0.15;
      la.brake.emissiveIntensity = 25 * brakeS + 0.12 * headS;
      la.reverse.emissiveIntensity = 14 * revS;
      la.side.emissiveIntensity = 1.6 * headS;
    }

    // ---- cold-gas thrusters: plumes + a cold glow in the nozzle bells
    const jetL = car.boost?.level ?? 0;
    carU.uJet.value = jetL;
    jets.update(jetL, car.boost?.gas ?? 1, app.time?.t ?? 0);

    // ---- active wing: stowed flush in the black deck panel when slow (as in the press photos), deployed from ~80 km/h,
    // and pitched up as an airbrake under hard braking at speed. Stow = drop, nose down, blade retracts sideways, plates fold.
    const h = dt || 1 / 60;
    if (speed > 22) wingUp = true; else if (speed < 13 && brakeS < 0.5) wingUp = false;
    wingS += ((wingUp ? 0 : 1) - wingS) * Math.min(1, h * 2.2);
    if (Math.abs(wingS - (wingUp ? 0 : 1)) < 1e-3) wingS = wingUp ? 0 : 1;
    const wingT = clamp(brakeS * 1.4 - 0.25, 0, 1) * smooth(18, 34, speed) * (1 - wingS);
    wingA += (wingT * 0.55 - wingA) * Math.min(1, h * (wingT * 0.55 > wingA ? 7 : 3));
    const sb = smooth(0, 1, wingS), sp = smooth(0, 0.6, wingS);       // (old format) the plates fold first and open last
    const dep = 1 - wingS, depOn = dep > 0.002, de = smooth(0, 1, dep);       // (new format) deploy 0 = stowed .. 1 = deployed
    const tipK = smooth(0, 0.65, dep), dropK = smooth(0.4, 1, dep);            // the tips slide out first, the endplates and struts drop last
    for (const rec of lods) {
      if (!rec.wing || !rec.root.visible) continue;
      if (WD) {
        // stowed: the shell's deck is all there is (Wing and WingWell hidden: no z-fighting in the common case).  Deploying: the well is fully present at once, the wing
        // (3 mm above its stowed copy so it never sinks into the well) rises and pitches (rotation.z > 0 = trailing edge up) from the deck pose.
        rec.wing.visible = depOn;
        if (rec.well) rec.well.visible = depOn;
        if (!depOn) continue;
        rec.wing.position.set(rec.wingP0.x + (WD.dx ?? 0) * de, rec.wingP0.y + WD.dy * de + 0.003, rec.wingP0.z);
        rec.wing.rotation.z = WD.rotZ * de + wingA;
        if (rec.plates) {
          rec.plates.scale.set(1, (PS.scaleY ?? 1) + (1 - (PS.scaleY ?? 1)) * dropK, (PS.scaleZ ?? 1) + (1 - (PS.scaleZ ?? 1)) * tipK);
          rec.plates.visible = dep > 0.03;
        }
        if (rec.ends.length) {
          const k = smooth(EK[0], EK[1], dep);
          for (const e of rec.ends) {
            e.t.position.copy(e.t0).addScaledVector(e.out, k);
            e.p.quaternion.copy(e.q0).premultiply(qE.setFromAxisAngle(e.ax, e.a * k));
          }
        }
        continue;
      }
      rec.wing.position.y = rec.wingY0 + WS.dy * sb;
      rec.wing.rotation.z = WS.rotZ * sb + wingA;
      rec.wing.scale.z = 1 + ((WS.spanScale ?? 1) - 1) * sb;
      if (rec.plates) {
        rec.plates.scale.set(1 + ((PS.scaleX ?? 1) - 1) * sp, 1 + ((PS.scaleY ?? 1) - 1) * sp, 1 + ((PS.scaleZ ?? 1) - 1) * sp);
        rec.plates.visible = sp < 0.99;
      }
    }

    // ---- wheels, steering wheel
    const ws = car.wheels;
    for (const rec of lods) {
      if (!rec.root.visible) continue;
      for (let i = 0; i < 4; i++) {
        const wr = rec.wheels[i]; if (!wr.hub) continue;
        const w = ws ? ws[i] : null;
        const trav = w ? clamp(w.suspensionTravel ?? 0, -0.14, 0.16) : 0;
        wr.hub.position.y = wr.baseY + trav;
        wr.hub.rotation.y = w ? -(w.steer ?? 0) : 0;
        const spinA = w ? (w.spin ?? 0) : 0;
        if (wr.spin) wr.spin.rotation.z = spinA;
        if (wr.blur) {
          const U = wr.blur.userData.U;
          const om = Math.abs(w ? (w.spinRate ?? 0) : 0);
          U.uSpin.value = spinA;
          U.uBlurW.value = om * 0.0095;
          U.uBlurA.value = 0.84 * smooth(16, 40, om);
        }
      }
      if (rec.steering) {
        const s = car.input ? car.input.steer : 0;
        qY.setFromAxisAngle(AX_Y, -s * 2.4);
        rec.steering.quaternion.copy(rec.steerQ0).multiply(qY);
      }
    }

    // ---- headlight data for the light pool and the road shader (nose centre, slightly ahead; car frame −Z forward)
    nose.set(0, 0.52, -2.55).applyQuaternion(object.quaternion).add(object.position);
    tail.set(0, 0.3, 3.5).applyQuaternion(object.quaternion).add(object.position);
    dir.set(0, 0, -1).applyQuaternion(object.quaternion).normalize();     // level axis: the cone's lower edge is the near cut-off
    lightState.head = headS; lightState.brake = brakeS; lightState.reverse = revS;
    lightState.roadFade = 1 - smooth(120, 200, dist);
    pool.begin(dt || 1 / 60);
    pool.apply(visual, lightState, poolLights);
  }

  function dispose() {
    pool.unregister(visual);
    for (const m of allMats) m.dispose();
    jets.dispose();
    for (const rec of lods) for (const b of rec.blurs) b.dispose();
    object.removeFromParent();
  }

  return visual;
}

function blurGeo() {
  if (!ASSETS.blurGeo) ASSETS.blurGeo = new THREE.RingGeometry(0.06, 0.30, 56, 1);
  return ASSETS.blurGeo;
}
