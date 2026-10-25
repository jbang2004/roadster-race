// Test scene for area C: a wet night studio/street with lamps and neon strips, the player car + AI liveries, a synthetic
// Car-state animator (circle, brake, steer, skid) and harness hooks.
//   ?scene=car[&freeze][&lod=0|1|2][&n=3 (number of AI)][&sim=circle|static|brake|skid|lineup][&rain=0.3]
//   hooks: __cam(pos, target, fov) · __view(name) · __chase(back, up, side) · __sim.run(sec) · __sim.set({...}) · __lineup()
//   with ?freeze the app clock is stopped; advance the simulation deterministically with __sim.run(seconds).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { Pass } from 'three/addons/postprocessing/Pass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { phHDRI, phTextureSet } from '../core/assets.js';
import { LAYER } from '../core/layers.js';
import { G } from '../core/globals.js';
import { lights } from '../core/lights.js';
import { bus } from '../core/bus.js';
import { loadCarAssets, createCarVisual, LIVERIES } from '../car/index.js';

export default async function (app) {
  const scene = app.scene, renderer = app.renderer, camera = app.camera;
  camera.layers.enable(LAYER.CARS); camera.layers.enable(LAYER.LATE);
  camera.far = 2000;
  G.uRain.value = +(app.q.get('rain') ?? 0.35);
  G.uWet.value = 1;

  // ---------------------------------------------------------------- environment
  const hdr = await phHDRI('shanghai_bund');
  const pmrem = new THREE.PMREMGenerator(renderer);
  const hdrEnv = pmrem.fromEquirectangular(hdr).texture;
  scene.environment = hdrEnv; scene.environmentIntensity = 0.8; renderer.toneMappingExposure = 0.55;
  scene.background = hdr; scene.backgroundIntensity = 0.8; scene.backgroundBlurriness = 0.02;
  scene.fog = new THREE.FogExp2(0x0a0c18, 0.006);
  const hemi = new THREE.HemisphereLight(0x4a68a0, 0x101014, 0.04); hemi.layers.enable(LAYER.CARS); scene.add(hemi);
  // dynamic probe like R's render.probe: a cube render target of the world (cars/fx are not on layer 0)
  const probeRT = new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter });
  const probeCam = new THREE.CubeCamera(0.2, 400, probeRT);
  scene.add(probeCam);

  // ---------------------------------------------------------------- wet road with planar reflection
  const asphalt = await phTextureSet('asphalt_02');
  const mkTex = (t, rep) => { const c = t.clone(); c.repeat.set(rep, rep); c.needsUpdate = true; return c; };
  const refl = new Reflector(new THREE.PlaneGeometry(400, 400), { textureWidth: 1024, textureHeight: 1024, clipBias: 0.002, multisample: 4 });
  refl.rotation.x = -Math.PI / 2; refl.position.y = -0.004;
  refl.material.colorWrite = false; refl.material.depthWrite = false;      // we only use its render target
  refl.layers.set(LAYER.DEFAULT);
  scene.add(refl);
  const reflTex = refl.getRenderTarget().texture;
  const roadMat = new THREE.MeshStandardMaterial({
    map: mkTex(asphalt.map, 60), normalMap: mkTex(asphalt.normalMap, 60), roughnessMap: mkTex(asphalt.armMap, 60), color: 0x707070, roughness: 1.0, metalness: 0,
    envMapIntensity: 0.6,
  });
  roadMat.normalScale.set(0.7, 0.7);
  roadMat.onBeforeCompile = (sh) => {
    sh.uniforms.tRefl = { value: reflTex }; sh.uniforms.reflMat = { value: refl.material.uniforms.textureMatrix.value };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvWP = (modelMatrix * vec4(position, 1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP; uniform sampler2D tRefl; uniform mat4 reflMat;')
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>\nroughnessFactor = clamp(roughnessFactor * 0.6, 0.12, 1.0);`)
      .replace('#include <opaque_fragment>', `
        { vec4 rc = reflMat * vec4(vWP + normal.xyz * 0.0, 1.0); vec2 ruv = rc.xy / rc.w;
          vec3 V = normalize(vViewPosition); float nv = clamp(dot(normalize(vNormal), V), 0.0, 1.0);
          float fr = 0.03 + 0.97 * pow(1.0 - nv, 5.0);
          vec3 rcol = texture2D(tRefl, ruv + normal.xz * 0.012).rgb;
          outgoingLight += rcol * (0.05 + fr * 0.9) * 0.9; }
        #include <opaque_fragment>`);
  };
  const road = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), roadMat);
  road.rotation.x = -Math.PI / 2; scene.add(road);

  // ---------------------------------------------------------------- set dressing: lamps, neon strips, wall
  const emissive = (c, k) => new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(k), toneMapped: false });
  const LAMPS = app.q.get('lamps') !== '0';
  const addLamp = (x, z, h = 9, col = 0xffa850) => {
    if (!LAMPS) return;
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.1, h, 8), new THREE.MeshStandardMaterial({ color: 0x14151a, roughness: 0.6, metalness: 0.5 }));
    pole.position.set(x, h / 2, z); scene.add(pole);
    const arm = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.08, 0.1), pole.material); arm.position.set(x - Math.sign(x) * 1.1, h, z); scene.add(arm);
    const head = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.12, 0.3), emissive(col, 5)); head.position.set(x - Math.sign(x) * 2.2, h - 0.08, z); scene.add(head);
    const pl = new THREE.PointLight(col, 140, 30, 2); pl.position.set(head.position.x, h - 0.5, z); pl.layers.enable(LAYER.CARS); scene.add(pl);
    lights.add({ pos: pl.position, color: col, intensity: 140, range: 30, kind: 'street' });
  };
  for (let i = -3; i <= 3; i++) { addLamp(-10.5, i * 26 + 4); addLamp(10.5, i * 26 - 9); }
  const neon = (x, y, z, w, h, d, col, k = 9, light = 90) => {
    if (!LAMPS) return;
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), emissive(col, k)); m.position.set(x, y, z); scene.add(m);
    if (light) { const pl = new THREE.PointLight(col, light, 14, 2); pl.layers.enable(LAYER.CARS); pl.position.set(x - Math.sign(x) * 0.8, y, z); scene.add(pl); lights.add({ pos: pl.position, color: col, intensity: light, range: 14, kind: 'neon' }); }
  };
  // wall behind the car with neon strips (gives the clear coat something sharp to reflect)
  const wall = new THREE.Mesh(new THREE.BoxGeometry(0.5, 14, 160), new THREE.MeshStandardMaterial({ color: 0x0b0c10, roughness: 0.8 }));
  wall.position.set(-15, 7, 0); scene.add(wall);
  const wall2 = wall.clone(); wall2.position.x = 15; scene.add(wall2);
  for (let i = -5; i <= 5; i++) {
    neon(-14.6, 5.5 + (i % 2) * 2.2, i * 11, 0.15, 0.2, 7, i % 3 === 0 ? 0xff2fb0 : 0x18d8ff, 2.2, i % 2 ? 22 : 0);
    neon(14.6, 4.0 + (i % 2) * 3, i * 11 + 4, 0.15, 6, 0.3, i % 3 === 1 ? 0x9a5cff : 0xff7a2a, 2.0, i % 2 ? 0 : 22);
  }
  neon(-14.6, 1.0, 0, 0.12, 0.12, 150, 0x18d8ff, 3, 0);
  neon(14.6, 0.8, 0, 0.12, 0.12, 150, 0xff2fb0, 3, 0);

  // ---------------------------------------------------------------- pipeline with bloom (stand-in for R)
  const rt = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: 4 });
  const composer = new EffectComposer(renderer, rt);
  // two scene passes like R's pipeline: world (DEFAULT + MAIN_ONLY) then cars + LATE fx (CARS + LATE), same depth buffer
  class LayerPass extends Pass {
    constructor(mask, first) { super(); this.mask = mask; this.first = first; this.needsSwap = false; }
    render(r, writeBuffer, readBuffer) {
      const m = camera.layers.mask, ac = r.autoClear;
      camera.layers.mask = this.mask; r.autoClear = false;
      r.setRenderTarget(readBuffer);
      if (this.first) r.clear(true, true, true);
      const bg = scene.background; if (!this.first) scene.background = null;     // the sky is drawn once, in the world pass
      r.render(scene, camera);
      scene.background = bg;
      camera.layers.mask = m; r.autoClear = ac;
    }
  }
  composer.addPass(new LayerPass((1 << LAYER.DEFAULT) | (1 << LAYER.MAIN_ONLY), true));
  composer.addPass(new LayerPass((1 << LAYER.CARS) | (1 << LAYER.LATE), false));
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.22, 0.3, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  let probeAcc = 0;
  app.setPipeline({
    render(dt) {
      probeAcc += dt;
      probeCam.position.copy(focus.position).setY(1.2);
      if (!probeCam.userData.done || probeAcc > 0.05) { probeAcc = 0; probeCam.userData.done = true; probeCam.update(renderer, scene); }
      composer.render(dt);
    },
    setSize(w, h, pr) { composer.setPixelRatio(pr); composer.setSize(w, h); bloom.resolution.set(w, h); },
  });
  const focus = new THREE.Object3D();

  // ---------------------------------------------------------------- cars + synthetic Car state
  const { meta } = await loadCarAssets(app);
  const env = app.q.get('env') === 'hdri' ? hdrEnv : probeRT.texture;
  const forceLod = app.q.has('lod') ? +app.q.get('lod') : -1;
  const nAI = +(app.q.get('n') ?? 2);
  const cars = [];
  const mkWheel = () => ({ steer: 0, spin: 0, spinRate: 0, compression: 0, suspensionTravel: 0, load: 4000, slipRatio: 0, slipAngle: 0, grounded: true, skid: 0, contact: new THREE.Vector3() });
  function mkCar(i, liv, isPlayer) {
    const c = {
      id: i, name: LIVERIES[liv].name, livery: liv, isPlayer, visual: null,
      position: new THREE.Vector3(), quaternion: new THREE.Quaternion(), velocity: new THREE.Vector3(), angularVelocity: new THREE.Vector3(),
      speed: 0, accel: new THREE.Vector3(), input: { throttle: 0, brake: 0, steer: 0, handbrake: 0 },
      wheels: [mkWheel(), mkWheel(), mkWheel(), mkWheel()], motor: { rpm: 0, load: 0, power: 0 }, brakeTemp: 0,
      lights: { head: true, brake: 0, reverse: false }, race: {}, track: {},
      sim: { heading: 0, yawRate: 0, beta: 0, v: 0, R: 20, phase: 0, t0: 0, cx: 0, cz: 0, ang: 0 },
    };
    c.visual = createCarVisual(app, { livery: liv, isPlayer, envMap: env, forceLod, poolLights: app.q.get('poollights') !== '0' });
    scene.add(c.visual.object);
    return c;
  }
  cars.push(mkCar(0, 0, true));
  for (let i = 0; i < nAI; i++) cars.push(mkCar(i + 1, 1 + (i % 7), false));
  focus.position.copy(cars[0].position);

  // fx (may not exist yet while the other half of the area is being written)
  let fx = null;
  try { const m = await import('../fx/index.js'); fx = m.createVehicleFx(app); } catch (e) { console.warn('fx not available', e.message); }

  // ---- the simulator -------------------------------------------------------------------------------------------
  const SIM = { mode: app.q.get('sim') ?? 'circle', t: 0, speedKmh: null };
  const tmpE = new THREE.Euler(), tmpV = new THREE.Vector3();
  const WB = 3.097;
  const hubs = ['FL', 'FR', 'RL', 'RR'].map(w => [meta.hubs[w][1], meta.hubs[w][0]]);   // [x(right), z(forward -)] (car_meta.json: build frame x rear, y right)
  const WR = ['F', 'F', 'R', 'R'].map(a => (typeof meta.tyreRadius === 'number' ? meta.tyreRadius : meta.tyreRadius[a]));      // per wheel (2026-10-25: front 0.353, rear 0.39)
  const rnd = (x) => Math.sin(x * 12.9898) * 43758.5453 % 1;

  function script(t, c, k) {
    // returns throttle, brake, steer, handbrake, skid-flag for the loop (20 s)
    const T = SIM.mode === 'static' ? 0 : (t % 22);
    if (SIM.mode === 'brake') return t % 12 < 4 ? [1, 0, 0.0, 0] : [0, 1, 0, 0];
    if (SIM.mode === 'skid') return t % 14 < 3 ? [1, 0, 0.9, 0] : [t % 14 < 9 ? 0.9 : 0.2, 0, 0.9, t % 14 < 9 ? 1 : 0];
    if (SIM.mode === 'static') return [0, 0, 0, 0];
    if (T < 6) return [1, 0, 0.18 + 0.1 * Math.sin(T), 0];
    if (T < 8) return [0, 1, 0.1, 0];
    if (T < 12) return [0.6, 0, Math.sin((T - 8) * 1.6) * 0.9, 0];
    if (T < 17) return [0.9, 0, 0.55, T > 13 ? 1 : 0];
    return [0.4, 0, 0.12, 0];
  }

  function stepCar(c, h, t, idx) {
    const s = c.sim;
    let [thr, brk, str, hb] = script(t + idx * 3.7, c, idx);
    if (!c.isPlayer && SIM.mode === 'circle') { thr = Math.min(1, 0.9); brk = 0; str = 0.12 + 0.03 * idx; hb = 0; }
    const aLong = thr * (s.v < 20 ? 9 : s.v < 60 ? 5 : 1.2) - brk * 11 - s.v * s.v * 0.0006 - 0.3 * (s.v > 0.5);
    s.v = Math.max(0, s.v + aLong * h);
    if (SIM.speedKmh != null && c.isPlayer) s.v = SIM.speedKmh / 3.6;
    const steerAng = str * 0.4 / (1 + s.v * 0.05);
    const targetYaw = s.v * Math.tan(steerAng) / WB * (hb > 0.5 ? 1.8 : 1);
    s.yawRate += (targetYaw - s.yawRate) * Math.min(1, h * 5);
    s.beta += ((hb > 0.5 ? -0.42 * Math.sign(str || 1) : 0) - s.beta) * Math.min(1, h * 3);
    s.heading += s.yawRate * h;
    const course = s.heading + s.beta * 0;
    // heading 0 => car faces −Z; position integrates along the velocity direction (heading + beta)
    const vd = s.heading - s.beta * 0.0;
    c.velocity.set(-Math.sin(vd - 0) * s.v, 0, -Math.cos(vd) * s.v);
    // slip: the body points ahead of its velocity during skids
    if (hb > 0.5) { const sa = s.beta; c.velocity.set(-Math.sin(s.heading + sa) * s.v, 0, -Math.cos(s.heading + sa) * s.v); }
    c.position.addScaledVector(c.velocity, h);
    const aLat = s.yawRate * s.v;
    // body pitch / roll from accelerations (physics owns the body; this fakes it)
    const aL = aLong;
    const pitch = THREE.MathUtils.clamp(aL * 0.0032, -0.05, 0.04), roll = THREE.MathUtils.clamp(aLat * 0.0028, -0.06, 0.06);
    s.pitch = (s.pitch ?? 0) + (pitch - (s.pitch ?? 0)) * Math.min(1, h * 6);
    s.roll = (s.roll ?? 0) + (roll - (s.roll ?? 0)) * Math.min(1, h * 6);
    tmpE.set(s.pitch, s.heading, s.roll, 'YXZ');
    c.quaternion.setFromEuler(tmpE);
    c.position.y = 0.0 + 0.0;
    c.speed = s.v; c.accel.set(aLat, 0, -aL);
    c.input.throttle = thr; c.input.brake = brk; c.input.steer = str; c.input.handbrake = hb;
    c.lights.brake = brk > 0.05 ? Math.min(1, 0.4 + brk) : 0; c.lights.reverse = false; c.lights.head = true;
    c.brakeTemp += ((brk * Math.min(1, s.v / 40) * 1.0) - c.brakeTemp) * Math.min(1, h * (brk > 0.05 ? 0.9 : 0.25));
    c.motor.rpm = s.v * 160; c.motor.load = thr; c.motor.power = thr * 600 * Math.min(1, s.v / 20) - brk * 200;
    for (let i = 0; i < 4; i++) {
      const w = c.wheels[i], front = i < 2, right = i % 2;
      const rollC = (right ? -1 : 1) * s.roll * 0.9 * Math.abs(hubs[i][0]) * 0.7;    // right wheel: roll>0 lifts the right body side → wheel relatively compresses less
      const pitchC = (front ? 1 : -1) * -s.pitch * 1.5 * 0.6;
      const bump = 0.004 * Math.sin(t * 31 + i * 1.7 + s.v * 0.4) * Math.min(1, s.v / 15);
      w.compression = THREE.MathUtils.clamp(rollC + pitchC + bump, -0.06, 0.08);
      w.suspensionTravel = w.compression;
      w.steer = front ? str * 0.4 / (1 + s.v * 0.05) : 0;
      w.spinRate = s.v / WR[i] * (hb > 0.5 && !front ? 0.15 : 1) * (brk > 0.9 && s.v < 12 ? 0.3 : 1);
      w.spin += w.spinRate * h;
      w.slipRatio = (thr > 0.9 && s.v < 12 && !front) ? 0.5 : (brk > 0.9 ? -0.4 : 0);
      w.skid = hb > 0.5 ? 0.9 : (brk > 0.95 && s.v > 10 ? 0.6 : (w.slipRatio > 0.3 ? 0.5 : 0));
      w.slipAngle = hb > 0.5 ? s.beta : 0;
      w.load = 3500 + (front ? 1 : -1) * -aL * 60 + (right ? 1 : -1) * aLat * 80;
      // contact point: hub position transformed to the road
      tmpV.set(hubs[i][0], 0, hubs[i][1]).applyQuaternion(c.quaternion).add(c.position);
      w.contact.copy(tmpV);
    }
  }
  const startPose = [[0, 0, 0], [-4.2, 0, -9], [4.2, 0, 14], [-9, 0, 22], [9, 0, 30], [-4, 0, 38], [5, 0, 46], [0, 0, 54]];
  function resetSim() {
    cars.forEach((c, i) => {
      c.position.set(...startPose[i]); c.sim.heading = 0; c.sim.v = 0; c.sim.yawRate = 0; c.sim.beta = 0; c.sim.pitch = 0; c.sim.roll = 0;
      c.brakeTemp = 0; for (const w of c.wheels) w.spin = 0;
    });
    SIM.t = 0;
  }
  resetSim();
  if (SIM.mode === 'circle' || SIM.mode === 'brake' || SIM.mode === 'skid') { cars[0].position.set(0, 0, 40); for (let i = 1; i < cars.length; i++) cars[i].position.set(startPose[i][0], 0, 40 + startPose[i][2] * 0.6 - 10); }

  let carsOnFrame = -1;
  function advance(h) {
    SIM.t += h;
    cars.forEach((c, i) => stepCar(c, h, SIM.t, i));
    for (const c of cars) c.visual.sync(c, h);
    fx?.update(h, cars);
    focus.position.copy(cars[0].position);
  }
  app.add({
    update(dt) {
      if (dt <= 0) { cars.forEach(c => c.visual.sync(c, 0)); return; }
      const n = Math.max(1, Math.round(dt * 120 / 2));
      const h = dt / n;
      for (let k = 0; k < n; k++) { SIM.t += h; cars.forEach((c, i) => stepCar(c, h, SIM.t, i)); }
      for (const c of cars) c.visual.sync(c, dt);
      fx?.update(dt, cars);
      focus.position.copy(cars[0].position);
      if (SIM.follow) followCam();
    },
  });

  // ---------------------------------------------------------------- camera hooks
  window.__cam = (p, t, fov = 40) => { SIM.follow = false; app.setView({ pos: p, target: t, fov }); };
  const player = cars[0];
  // views relative to the player car in its own frame (car local: +X right, −Z forward)
  const VIEWS = {
    q34: [[-5.8, 1.5, -5.6], [0, 0.55, 0], 38], q34r: [[5.8, 1.5, 5.6], [0, 0.55, 0], 38], side: [[-9, 0.7, 0.2], [0, 0.6, 0], 22], front: [[0, 1.0, -8], [0, 0.55, 0], 30],
    rear: [[0, 1.2, 8], [0, 0.6, 0], 30], top: [[0.01, 9, 0.5], [0, 0.5, 0], 36], nose: [[-2.4, 0.9, -5.2], [0, 0.45, -2.3], 28], tail: [[2.6, 1.0, 5.4], [0, 0.6, 2.2], 30],
    wheelF: [[-3.4, 0.45, -3.6], [-0.9, 0.38, -1.49], 24], wheelR: [[3.6, 0.5, 3.4], [0.9, 0.38, 1.6], 24], dash: [[0, 1.05, 0.9], [0, 0.85, -1.6], 70],
    cabin: [[2.2, 2.6, 1.5], [0, 0.6, 0], 50], roof: [[0.4, 3.2, 2.0], [0, 0.9, -0.2], 46], high: [[-3.5, 2.8, -3.0], [0, 0.7, -0.2], 40],
  };
  const qv = new THREE.Vector3(), qt = new THREE.Vector3();
  window.__view = (name, who = 0) => {
    SIM.follow = false;
    const c = cars[who], [p, t, fov] = VIEWS[name];
    qv.set(...p).applyQuaternion(c.quaternion).add(c.position);
    qt.set(...t).applyQuaternion(c.quaternion).add(c.position);
    app.setView({ pos: qv.toArray(), target: qt.toArray(), fov });
  };
  const followCam = () => {
    const c = cars[0], f = SIM.follow;
    qv.set(f.side, f.up, f.back).applyQuaternion(c.quaternion).add(c.position);
    qt.set(0, 0.8, -4).applyQuaternion(c.quaternion).add(c.position);
    app.setView({ pos: qv.toArray(), target: qt.toArray(), fov: f.fov });
  };
  window.__chase = (back = 7.5, up = 2.4, side = 0, fov = 60) => { SIM.follow = { back, up, side, fov }; followCam(); };
  window.__sim = {
    state: SIM, cars, fx,
    run(sec, h = 1 / 60) { const n = Math.round(sec / h); for (let i = 0; i < n; i++) advance(h); return { t: SIM.t, v: cars[0].speed, p: cars[0].position.toArray() }; },
    set(o) { Object.assign(SIM, o); },
    reset() { resetSim(); },
    setPlayer(o) { Object.assign(cars[0].sim, o); },
    stats: () => app.stats(),
  };
  window.__lineup = (spacing = 3.4, lod = -1) => {
    cars.forEach((c, i) => { c.sim.v = 0; c.position.set((i - (cars.length - 1) / 2) * spacing, 0, 0); c.sim.heading = 0; c.quaternion.identity(); });
  };
  window.__lod = (n) => cars.forEach(c => c.visual.forceLod(n));
  window.__livery = (i, who = 0) => { /* rebuild the visual with another livery */
    const c = cars[who]; scene.remove(c.visual.object); c.visual.dispose();
    c.livery = i; c.visual = createCarVisual(app, { livery: i, isPlayer: c.isPlayer, envMap: env, forceLod });
    scene.add(c.visual.object);
  };
  window.__bus = bus;
  window.__app = app;
  __view('q34');
  if (SIM.mode === 'static') { cars.forEach(c => c.visual.sync(c, 0)); }
  await app.ready();
}
