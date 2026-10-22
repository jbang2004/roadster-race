// K's test scene: the skyline + a stand-in for W's near band + a simple preview post (bloom + ACES).
// ?scene=skyline[&s=<m>][&view=top|aerial] Hooks: __skyline, __viewAt(s, back, up, ahead), __view(name)
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { getTrack, KIND } from '../track/track.js';
import { installAtmosphere, buildSkyline } from '../skyline/index.js';
import { lights } from '../core/lights.js';
import { G } from '../core/globals.js';
import { loadGLTF } from '../core/assets.js';
import { LAYER, setLayer } from '../core/layers.js';

export default async function (app) {
  const T = getTrack();
  const scene = app.scene;
  installAtmosphere(app);
  const skyline = await buildSkyline(app, T);
  app.add(skyline);
  window.__skyline = skyline; window.__track = T;

  // ---- stand-in near band ----
  const roadMat = new THREE.MeshStandardMaterial({ color: 0x15171c, roughness: 0.35, metalness: 0.0, side: THREE.DoubleSide });
  const N = T.N;
  const strip = (off0, off1, y, mat, kindFilter) => {
    const pos = [], idx = [];
    for (let i = 0; i <= N; i++) {
      const k = i % N, hw = T.hw[k];
      const ox = T.rx[k], oz = T.rz[k], rl = Math.hypot(ox, oz);
      const hx = ox / rl, hz = oz / rl;
      const yy = y ?? T.py[k] + 0.02;
      pos.push(T.px[k] + hx * (hw + off0) * -1, yy, T.pz[k] + hz * (hw + off0) * -1, T.px[k] + hx * (hw + off1), yy, T.pz[k] + hz * (hw + off1));
      if (i < N) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
    return new THREE.Mesh(g, mat);
  };
  // road ribbon
  {
    const pos = [], idx = [];
    for (let i = 0; i <= N; i++) {
      const k = i % N, hw = T.hw[k] + 0.5;
      for (const side of [-1, 1]) pos.push(T.px[k] + T.rx[k] * hw * side, T.py[k] + T.ry[k] * hw * side + 0.02, T.pz[k] + T.rz[k] * hw * side);
      if (i < N) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
    scene.add(new THREE.Mesh(g, roadMat));
  }
  // near ground (y=0) ±150 m around the road, stand-in for W
  const nearMat = new THREE.MeshStandardMaterial({ color: 0x0b0c10, roughness: 0.9, side: THREE.DoubleSide });
  {
    const pos = [], idx = [];
    for (let i = 0; i <= N; i++) {
      const k = i % N, hw = T.hw[k];
      const rl = Math.hypot(T.rx[k], T.rz[k]), hx = T.rx[k] / rl, hz = T.rz[k] / rl;
      for (const side of [-1, 1]) pos.push(T.px[k] + hx * (hw + 152) * side, 0, T.pz[k] + hz * (hw + 152) * side);
      if (i < N) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
    scene.add(new THREE.Mesh(g, nearMat));
  }
  // dark boxes in the near band
  {
    const blocks = [];
    const cell = 34;
    for (let x = -1100; x < 1200; x += cell) for (let z = -1000; z < 1100; z += cell) {
      const cx = x + cell / 2, cz = z + cell / 2;
      const d = skyline.roadDistance ? skyline.roadDistance(cx, cz) : T.field(cx, cz).all;
      if (d < 14 || d > 140) continue;
      const h = 8 + Math.abs(Math.sin(cx * 0.37 + cz * 0.91)) * 26 * (d > 30 ? 1 : 0.4);
      blocks.push([cx, cz, h]);
    }
    const geo = new THREE.BoxGeometry(1, 1, 1); geo.translate(0, 0.5, 0);
    const im = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: 0x0a0c12, roughness: 0.8, emissive: 0x050814 }), blocks.length);
    const m = new THREE.Matrix4();
    blocks.forEach(([x, z, h], i) => { m.compose(new THREE.Vector3(x, 0, z), new THREE.Quaternion(), new THREE.Vector3(cell - 10, h, cell - 10)); im.setMatrixAt(i, m); });
    scene.add(im);
  }
  // canal stand-in
  const cn = T.layout.canal, B = T.layout.bounds;
  const canal = new THREE.Mesh(new THREE.PlaneGeometry(cn.x1 - cn.x0, B.z1 - B.z0), new THREE.MeshStandardMaterial({ color: 0x06141f, roughness: 0.15 }));
  canal.rotation.x = -Math.PI / 2; canal.position.set((cn.x0 + cn.x1) / 2, cn.water, (B.z0 + B.z1) / 2); scene.add(canal);

  // test lamps along the boulevard (rain pick-up) + a fake pair of headlights on the camera (?head)
  for (let s = 0; s < 900; s += 28) for (const side of [-1, 1]) {
    const p = T.pointAt(s, side * (T.hw[Math.floor(s)] + 1.5)); p.y += 9;
    lights.add({ pos: p, color: [1.0, 0.6, 0.25], intensity: 450, range: 30, kind: 'street' });
  }
  if (app.q.has('head')) app.add({ late() {
    const c = app.camera, d = new THREE.Vector3(); c.getWorldDirection(d);
    G.uHeadCount.value = 2;
    for (let i = 0; i < 2; i++) {
      G.uHeadPos.value[i].copy(c.position).addScaledVector(d, 6).add(new THREE.Vector3(i ? 0.7 : -0.7, -1.9, 0));
      G.uHeadDir.value[i].copy(d); G.uHeadColor.value[i].set(6000, 5600, 5000);
    }
  } });

  // ?car: the player car at s (to judge the global ambient / moon lights on it; layer CARS is enabled on the camera)
  if (app.q.has('car')) {
    const gltf = await loadGLTF('assets/car/wedge_car.glb');
    const car = new THREE.Group(), m = gltf.scene.clone(); m.rotation.y = -Math.PI / 2; car.add(m);
    const cs = +(app.q.get('s') ?? 150);
    const slot = T.frameAt(cs); car.position.copy(slot.pos); car.quaternion.copy(T.quatAt(cs));
    setLayer(car, LAYER.CARS); scene.add(car); app.camera.layers.enable(LAYER.CARS);
    window.__car = car;
  }

  // ---- preview post ----
  app.camera.layers.enable(LAYER.MAIN_ONLY); app.camera.layers.enable(LAYER.LATE);     // R draws LATE (rain, splashes) after the car pass
  const r = app.renderer;
  r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = +(app.q.get('exp') ?? 1);
  const composer = new EffectComposer(r);
  const rp = new RenderPass(scene, app.camera);
  r.info.autoReset = false;
  let world = { calls: 0, tris: 0 };
  const rpRender = rp.render.bind(rp);
  rp.render = (...a) => { r.info.reset(); rpRender(...a); world = { calls: r.info.render.calls, tris: r.info.render.triangles }; };
  composer.addPass(rp);
  const bloom = new UnrealBloomPass(new THREE.Vector2(app.width, app.height), 0.55, 0.55, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  app.setPipeline({
    render(dt) { composer.render(dt); },
    setSize(w, h, pr) { composer.setPixelRatio(pr); composer.setSize(w, h); },
    stats() { return { calls: world.calls, tris: world.tris }; },
    dispose() { composer.dispose(); },
  });
  window.__bloom = bloom;

  // ---- views ----
  const tmp = new THREE.Vector3();
  window.__viewAt = (s, back = 9, up = 3.2, ahead = 30, fov = 62) => {
    const f = T.frameAt(s), a = T.frameAt(s + ahead);
    const p = f.pos.clone().addScaledVector(f.t, -back).addScaledVector(f.u, up);
    app.setView({ pos: p.toArray(), target: a.pos.clone().addScaledVector(a.u, 1.5).toArray(), fov });
  };
  window.__view = (name) => {
    const v = {
      boulevard: () => __viewAt(150, 9, 3.2, 40),
      expy: () => __viewAt(2500, 9, 3.4, 40),
      expy2: () => __viewAt(3050, 9, 3.4, 40),
      docks: () => __viewAt(1370, 9, 3.2, 40),
      market: () => { __viewAt(4100, 6, 2.4, 25); app.camera.rotateX(0.55); },
      aerial: () => app.setView({ pos: [-300, 420, 900], target: [100, 60, -900], fov: 60 }),
      top: () => { app.camera.far = 9000; app.setView({ pos: [50, 3500, 80], target: [50, 0, 79.9], fov: 50 }); },
    }[name]; v?.();
  };
  // ?drive=<m/s>[&s=<start>]: move the camera along the track (to judge rain streaks, speed feel)
  if (app.q.has('drive')) {
    let ds = +(app.q.get('s') ?? 150); const sp = +app.q.get('drive');
    app.add({ late(dt) { ds += sp * dt; window.__viewAt(ds, 9, 3.2, 40); } });
  }
  const view = app.q.get('view');
  if (view) window.__view(view); else window.__viewAt(+(app.q.get('s') ?? 150), 9, 3.2, 40);
  await app.ready();
}
